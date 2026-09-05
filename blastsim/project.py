"""통합 해석 드라이버 — 하나의 입력으로 진동·파쇄·비산·영상을 모두 만든다.

    입력(암반·폭약·패턴·자유면·전색)
        ├─ FDM  : 원거리 진동  -> PPV, 주파수, 규제검토, 지표 진동 등고선/영상
        └─ DEM  : 근거리 파쇄·비산 -> 파쇄입도, 이동·적재, 비산거리, 영상

GUI(gui.py)와 CLI 가 모두 이 클래스를 쓴다.
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field

import numpy as np

from . import empirical, fdm, plots, sensors
from .explosives import get_explosive
from .fdm import BenchGeometry, CavitySource, FDMConfig, FDMModel, FDMSolver
from .frag import BlastLoad, FragConfig, FragModel, FragSolver
from .pattern import BlastPattern
from .rock import get_rock
from .source import SourceConfig

# 품질 프리셋 — 격자/입자 해상도와 해석시간을 함께 조절한다
# DEM 은 본드가 살아 있는 한 dt 가 sqrt(m/k) 에 묶인다. 그래서 DEM 으로 푸는 구간
# (throw)은 파쇄와 초기 이동이 끝나는 시점까지만 잡고, 그 뒤는 각 파쇄체를 강체로
# 보는 탄도 단계로 넘긴다 (frag.FragSolver._ballistic).
QUALITY_PRESETS: dict[str, dict] = {
    "빠름": dict(fdm_max_freq=60.0, fdm_max_cells=400_000, particle=0.60,
                 bond_phase=0.06, throw=0.12, frag_total=1.40, fps=20.0),
    "보통": dict(fdm_max_freq=100.0, fdm_max_cells=1_200_000, particle=0.45,
                 bond_phase=0.08, throw=0.15, frag_total=1.60, fps=25.0),
    "정밀": dict(fdm_max_freq=140.0, fdm_max_cells=3_000_000, particle=0.32,
                 bond_phase=0.10, throw=0.20, frag_total=2.00, fps=30.0),
}


@dataclass
class ProjectConfig:
    """해석 전체 입력."""

    # --- 암반 ---
    rock_key: str = "granite"
    vp: float | None = None                 # 현장 탄성파속도로 E 재산정
    damping_ratio: float | None = None
    poisson: float = 0.25

    # --- 폭약 ---
    explosive_key: str = "emulsion"
    hole_dia_mm: float = 76.0
    charge_dia_mm: float | None = None      # None = 완전결합
    charge_kg: float | None = None          # None = 장약장으로 자동

    # --- 발파 패턴 ---
    burden: float = 3.0
    spacing: float = 3.5
    bench_height: float = 10.0
    n_rows: int = 2
    n_cols: int = 5
    stemming: float | None = None
    subdrill: float | None = None
    delay_hole_ms: float = 25.0
    delay_row_ms: float = 65.0

    # --- 조건 ---
    full_stemming: bool = True              # 완전 전색
    two_free_face: bool = True              # 2자유면 (상부면 + 벤치면)
    face_angle_deg: float = 0.0

    # --- 계측 ---
    distances: list[float] = field(default_factory=lambda: [30.0, 50.0, 80.0, 120.0])
    azimuth_deg: float = 0.0

    # --- 해석 선택 ---
    quality: str = "보통"
    run_vibration: bool = True
    run_fragmentation: bool = True
    make_video: bool = True
    calibrate: bool = True
    law: str = "kr_mean"
    efficiency: float = 1.0
    gas_efficiency: float = 0.25
    outdir: str = "output"


class BlastProject:
    """하나의 발파 조건에 대한 전체 해석."""

    def __init__(self, cfg: ProjectConfig) -> None:
        self.cfg = cfg
        self.q = QUALITY_PRESETS.get(cfg.quality, QUALITY_PRESETS["보통"])
        self.vib: dict = {}
        self.frag: dict = {}
        self.videos: list[str] = []
        self._build()

    # ---- 모델 구성 ---------------------------------------------------------
    def _build(self) -> None:
        c = self.cfg
        rock = get_rock(c.rock_key)
        if c.damping_ratio is not None:
            rock.damping_ratio = c.damping_ratio
        if c.vp:
            rock.young = rock.density * c.vp ** 2 / 1.2
        rock.poisson = c.poisson
        self.rock = rock

        exp = get_explosive(c.explosive_key)
        self.explosive = exp

        hole_d = c.hole_dia_mm / 1000.0
        charge_d = (c.charge_dia_mm / 1000.0) if c.charge_dia_mm else hole_d
        stem = c.stemming
        if c.charge_kg:
            depth = c.bench_height + (c.subdrill if c.subdrill is not None
                                      else 0.30 * c.burden)
            need = exp.charge_length(c.charge_kg, charge_d)
            stem = max(max(0.5, 15.0 * hole_d), depth - need)

        self.pattern = BlastPattern(
            exp, burden=c.burden, spacing=c.spacing, bench_height=c.bench_height,
            hole_dia=hole_d, charge_dia=charge_d, n_rows=c.n_rows, n_cols=c.n_cols,
            subdrill=c.subdrill, stemming=stem,
            delay_hole=c.delay_hole_ms / 1000.0, delay_row=c.delay_row_ms / 1000.0,
        )
        self.face_x = self.pattern.origin[0] - c.burden
        self.source_cfg = SourceConfig(efficiency=c.efficiency)

    @property
    def source_center(self) -> tuple[float, float]:
        hp = self.pattern.positions()
        return float(hp[:, 0].mean()), float(hp[:, 1].mean())

    # ---- FDM 진동 ----------------------------------------------------------
    def vibration_model(self) -> tuple:
        """계측점 배치와 FDM 격자를 함께 결정한다.

        흡수층(Cerjan 스펀지)은 해석영역 "밖"의 여유분이어야 한다. 계측점이 그
        안에 들어가면 인위적으로 감쇠된 값을 읽게 되고, 그러면 감쇠지수도 폭원
        보정계수도 함께 틀어진다. 스펀지 두께는 nb*h 로 격자간격에 비례하는데
        h 는 셀 예산에 따라 정해지므로, 둘을 함께 풀어야 한다.

        returns: (model, pts, names)
        """
        c, q = self.cfg, self.q
        cx, cy = self.source_center
        th = math.radians(c.azimuth_deg)
        pts, names = sensors.line_array((cx, cy), (math.cos(th), math.sin(th)),
                                        c.distances)
        r_max = max(c.distances)
        hp = self.pattern.positions()
        nb = fdm.SPONGE_CELLS
        half = max(0.45 * r_max, 20.0)   # 측방 반폭 (경계 스침입사 방지)

        def _grid(h: float):
            pad = (nb + 2) * h           # 스펀지 두께 + 여유 2셀
            x = (min(hp[:, 0].min() - 10.0, pts[:, 0].min() - pad, cx - half - pad),
                 max(hp[:, 0].max() + 10.0, pts[:, 0].max() + pad, cx + half + pad))
            y = (min(hp[:, 1].min() - 10.0, pts[:, 1].min() - pad, cy - half - pad),
                 max(hp[:, 1].max() + 10.0, pts[:, 1].max() + pad, cy + half + pad))
            # 바닥 스펀지도 표면파의 침투심도(~1파장)를 침범하면 안 된다
            dz = max(2.0 * (c.bench_height + self.pattern.subdrill),
                     0.45 * r_max, 25.0) + pad
            # FDMModel 은 지표 위에 진공층(n_air)을 더 쌓는다
            n_air = max(fdm.HALO + 2, 4)
            cells = (((x[1] - x[0]) / h + 1) * ((y[1] - y[0]) / h + 1)
                     * (dz / h + 1 + n_air))
            return x, y, dz, cells

        # 해상 주파수 요구와 함께, 격자가 발파공 배치를 표현할 수 있어야 한다.
        # 등가공동 반경이 격자간격에 비례하므로 h 가 저항선만큼 커지면 폭원이
        # 패턴 전체로 번져 버린다.
        h = min(self.rock.s_velocity / 6.0 / q["fdm_max_freq"],
                min(c.burden, c.spacing) / 2.0)
        x_range, y_range, depth, cells = _grid(h)
        while cells > q["fdm_max_cells"]:
            h *= 1.12
            x_range, y_range, depth, cells = _grid(h)

        geom = BenchGeometry(bench_height=c.bench_height, face_x=self.face_x,
                            face_angle=c.face_angle_deg,
                            two_free_face=c.two_free_face)
        model = FDMModel(self.rock, x_range, y_range, depth, h, geometry=geom,
                         poisson=c.poisson)
        return model, pts, names

    def run_vibration(self, log=print) -> dict:
        c, q = self.cfg, self.q
        cx, cy = self.source_center
        r_max = max(c.distances)
        model, pts, names = self.vibration_model()
        src = CavitySource(model, self.pattern.holes, self.explosive, self.source_cfg)

        w = model.sponge_weight(pts)
        if float(w.min()) < 0.999:
            bad = [f"{n}({wi:.3f})" for n, wi in zip(names, w) if wi < 0.999]
            log("  [경고] 계측점이 흡수층 안에 있습니다: " + ", ".join(bad)
                + "\n         해당 기록은 인위적으로 감쇠되어 감쇠지수·보정계수를"
                  " 왜곡합니다. --distances 를 줄이거나 --quality 를 낮추십시오.")

        travel = r_max / self.rock.r_velocity
        dur = (self.pattern.total_duration + travel
               + 12.0 * self.explosive.decay_time + 0.03)
        snaps = list(np.linspace(0.005, dur * 0.95, 40)) if c.make_video else []
        fcfg = FDMConfig(duration=dur, max_frequency=q["fdm_max_freq"],
                         snapshot_times=snaps, progress=True)
        solver = FDMSolver(model, src, fcfg)

        log(model.summary()); log(src.summary()); log(solver.summary()); log("")
        res = solver.run(pts, names)
        recs = sensors.build_records(res, (cx, cy))

        cal = 1.0
        if c.calibrate:
            cal = empirical.calibrate_efficiency(
                [r.distance for r in recs], [r.ppv for r in recs],
                self.pattern.max_charge_per_delay, empirical.SD_LAWS[c.law])
            for r in recs:
                r.velocity = r.velocity * cal
            res.surface_ppv = res.surface_ppv * cal
            for k in list(res.snapshots):
                res.snapshots[k] = res.snapshots[k] * cal

        self.vib = {"model": model, "source": src, "solver": solver, "result": res,
                    "records": recs, "calibration": cal}
        return self.vib

    # ---- DEM 파쇄·비산 -----------------------------------------------------
    def run_fragmentation(self, log=print) -> dict:
        c, q = self.cfg, self.q
        # DEM 하중창(throw_phase)이 기폭열보다 짧으면 뒤쪽 공은 아예 터지지 않는다.
        # 프리셋은 패턴을 모르므로 여기서 늘려 준다 — 조용히 공을 잃느니 느린 편이
        # 낫다. 마지막 기폭 뒤 20 ms 는 그 공의 파쇄가 진행되도록 남겨 둔다.
        last = max((h.delay for h in self.pattern.holes), default=0.0)
        throw = q["throw"]
        if last + 0.020 > throw:
            throw = last + 0.020
            log(f"  [조정] 기폭열이 {last * 1e3:.0f} ms 까지 이어져 DEM 하중창을 "
                f"{q['throw'] * 1e3:.0f} -> {throw * 1e3:.0f} ms 로 늘렸습니다 "
                f"(늘리지 않으면 뒤쪽 공이 터지지 않습니다).")
        fcfg = FragConfig(
            particle_size=q["particle"], bond_phase=q["bond_phase"],
            throw_phase=throw, total_duration=max(q["frag_total"], throw + 0.20),
            snapshot_fps=q["fps"],
            stemming_full=c.full_stemming, gas_efficiency=c.gas_efficiency,
            progress=True,
        )
        model = FragModel(self.rock, self.pattern, fcfg, face_x=self.face_x)
        load = BlastLoad(model, self.explosive, fcfg, self.source_cfg)
        solver = FragSolver(model, load, fcfg)

        log(model.summary()); log(load.summary()); log(solver.summary()); log("")
        res = solver.run()
        stats = fragmentation_stats(res, model)
        stats["kuz_ram"] = kuz_ram(self.pattern, self.rock, self.explosive)
        self.frag = {"model": model, "load": load, "solver": solver,
                     "result": res, "stats": stats}
        return self.frag

    # ---- 영상 --------------------------------------------------------------
    def make_videos(self, log=print) -> list[str]:
        """영상 생성. 하나가 실패해도 나머지와 보고서·그래프는 살린다."""
        from . import render
        out = []
        os.makedirs(self.cfg.outdir, exist_ok=True)
        jobs = []
        if self.frag:
            jobs.append(("파쇄·비산", lambda: render.animate_fragmentation(
                self.frag["result"],
                os.path.join(self.cfg.outdir, "frag_video.mp4"),
                fps=min(30.0, self.q["fps"]))))
        if self.vib and self.vib["result"].snapshots:
            jobs.append(("지표 진동", lambda: render.animate_vibration(
                self.vib["result"], self.pattern,
                os.path.join(self.cfg.outdir, "vibration_video.mp4"))))
        for name, fn in jobs:
            try:
                out.append(fn())
            except Exception as exc:                      # noqa: BLE001
                log(f"  [건너뜀] {name} 영상 생성 실패: "
                    f"{type(exc).__name__}: {str(exc)[:200]}")
        self.videos = out
        return out

    # ---- 전체 실행 ---------------------------------------------------------
    def run_all(self, log=print) -> dict:
        t0 = time.time()
        os.makedirs(self.cfg.outdir, exist_ok=True)
        log(self.rock.summary()); log("")
        log(self.explosive.summary(self.pattern.charge_dia, self.pattern.hole_dia))
        log("")
        log(self.pattern.summary()); log("")
        if self.cfg.run_vibration:
            log("=" * 70); log("  [1] FDM 원거리 진동해석"); log("=" * 70)
            self.run_vibration(log)
        if self.cfg.run_fragmentation:
            log("=" * 70); log("  [2] DEM 근거리 파쇄·비산해석"); log("=" * 70)
            self.run_fragmentation(log)
        # 보고서·그래프를 영상보다 **먼저** 저장한다. 영상 생성은 가장 느리고
        # 가장 잘 깨지는 단계라, 여기서 죽으면 몇십 분짜리 해석 결과가 통째로
        # 날아간다. (개별 영상 실패는 make_videos 안에서 따로 막는다.)
        self.save(log)
        if self.cfg.make_video:
            log("=" * 70); log("  [3] 영상 생성"); log("=" * 70)
            self.make_videos(log)
            if self.videos:
                self.save(log)          # 영상 목록을 보고서에 반영
        log(f"\n총 소요시간 {time.time() - t0:.1f} s,  결과: {self.cfg.outdir}/")
        return {"vibration": self.vib, "fragmentation": self.frag,
                "videos": self.videos}

    # ---- 출력 --------------------------------------------------------------
    def report(self) -> str:
        c = self.cfg
        lines = ["=" * 78,
                 "  발파 통합 해석 보고 (FDM 진동 + DEM 파쇄·비산)",
                 "=" * 78,
                 self.rock.summary(), "",
                 self.explosive.summary(self.pattern.charge_dia, self.pattern.hole_dia),
                 "", self.pattern.summary(), "",
                 f"  자유면: {'2자유면 (상부면 + 벤치면)' if c.two_free_face else '1자유면 (상부면)'}"
                 f",  벤치면 x = {self.face_x:.1f} m",
                 f"  전색: {'완전 전색' if c.full_stemming else '부분 전색'}", ""]

        if self.vib:
            recs = self.vib["records"]
            near = min(recs, key=lambda r: r.distance)
            law = empirical.fit_law([r.distance for r in recs], [r.ppv for r in recs],
                                    self.pattern.max_charge_per_delay)
            lines += ["-" * 78, "  [1] 원거리 진동 (FDM)", "-" * 78,
                      self.vib["model"].summary(), "",
                      sensors.table(recs), "",
                      self._frequency_note(recs),
                      f"  해석 회귀식 : {law}",
                      f"  참조 경험식 : {empirical.SD_LAWS[c.law]}",
                      f"  폭원 보정계수 eta = {self.vib['calibration']:.2f}"
                      + ("  (경험식에 맞춤)" if c.calibrate else "  (미보정)"), "",
                      empirical.regulation_table(near.ppv), ""]

        if self.frag:
            s = self.frag["stats"]
            kr = s["kuz_ram"]
            r = self.frag["result"]
            lines += ["-" * 78, "  [2] 근거리 파쇄·비산 (DEM)", "-" * 78,
                      self.frag["model"].summary(), "",
                      self.frag["load"].summary(), "",
                      f"  파괴본드 {r.broken:,} / {r.total_bonds:,} "
                      f"({100 * s['broken_frac']:.1f}%)  <- 손상도 지표",
                      "",
                      "  [파쇄 입도 — Kuz-Ram 경험모델]",
                      f"    X50 (50% 통과)  = {kr['X50']:.2f} m",
                      f"    X80 (80% 통과)  = {kr['X80']:.2f} m",
                      f"    Rosin-Rammler   : Xc = {kr['Xc']:.2f} m, 균등지수 n = {kr['n']:.2f}"
                      f"  (암반계수 A = {kr['A']:.1f})",
                      f"    과대석(>1 m) 비율 = {kr['oversize_1m']:.1%}",
                      ""] + (
            [f"  [파쇄 입도 — DEM 연결성분]",
             f"    X50 = {s['X50']:.2f} m, X80 = {s['X80']:.2f} m, "
             f"최대 {s['X_max']:.2f} m ({s['mass_max'] / 1000:.1f} t)", ""]
            if s["size_reliable"] else
            ["  [파쇄 입도 — DEM 연결성분: 신뢰할 수 없음]",
             f"    본드 파괴율 {s['broken_frac']:.0%} 로는 입도를 셀 수 없습니다.",
             "    본드망에서 덩어리를 세는 것은 본드 퍼콜레이션 문제인데, 배위수 12~16",
             "    격자는 본드를 90% 넘게 끊어야 비로소 쪼개집니다(44% 파괴에서도 여전히",
             "    100%가 한 덩어리). 위 Kuz-Ram 값을 쓰십시오.",
             f"    (참고로 연결성분이 주는 값: X50 = {s['X50']:.1f} m — 과대)", ""]
        ) + [
                      "  [이동 · 비산]",
                      f"    저항선 영역 평균 이동 = {s['burden_mean']:.2f} m,  "
                      f"1 m 초과 {s['burden_moved']:.0%},  자유면 밖으로 "
                      f"{s['out_face']:.0%}",
                      f"    이동한 암반 평균 이동 = {s['throw_mean']:.2f} m "
                      f"(최대 {s['throw_max']:.1f} m,  전체 자유입자의 "
                      f"{s['moved_frac']:.0%}가 이동)",
                      f"    최대 입자속도        = {s['v_max']:.1f} m/s "
                      f"(평균 {s['v_mean']:.1f} m/s)",
                      f"    비산 최원거리        = {s['flyrock_range']:.1f} m "
                      f"(자유면 기준)",
                      f"    비산 위험 입자       = {s['n_flyrock']:,}개 "
                      f"({s['flyrock_frac']:.2%})",
                      f"    권장 대피거리        = {s['safe_distance']:.0f} m "
                      f"(비산거리 x 2 안전율)", ""]

        if self.videos:
            lines += ["-" * 78, "  [3] 생성 영상", "-" * 78]
            lines += [f"    {v}" for v in self.videos]
            lines += [""]
        lines.append("=" * 78)
        return "\n".join(lines)

    def _frequency_note(self, recs) -> str:
        """탁월주파수가 격자 해상한계에 붙었는지 알린다.

        균질 탄성 모델에는 절리 산란감쇠가 없어서 고주파가 살아남고, 그 결과
        탁월주파수가 격자 상한 근처에 붙는다. 실제 원거리 계측은 보통 10~80 Hz
        이므로, 이 값으로 주파수 기준 규제를 검토하면 안 된다.
        """
        f_grid = self.vib["model"].max_frequency
        hi = [r for r in recs if r.dominant_frequency > 0.7 * f_grid]
        if not hi:
            return "  탁월주파수는 격자 해상한계 아래에 있다 — 해석값으로 볼 수 있다.\n"
        names = ", ".join(f"{r.name} {r.dominant_frequency:.0f} Hz" for r in hi)
        return ("  [경고] 탁월주파수가 격자 해상한계"
                f" {f_grid:.0f} Hz 에 붙어 있습니다 ({names}).\n"
                "         균질 탄성 모델에 절리 산란감쇠가 없어 고주파가 과대평가된\n"
                "         것입니다. 실제 원거리 계측은 보통 10~80 Hz 입니다.\n"
                "         규제 검토는 주파수가 아니라 PPV 기준으로 하십시오.\n")

    def save(self, log=print) -> list[str]:
        out = self.cfg.outdir
        os.makedirs(out, exist_ok=True)
        files = []
        rep = os.path.join(out, "report.txt")
        with open(rep, "w", encoding="utf-8") as f:
            f.write(self.report() + "\n")
        files.append(rep)

        if self.vib:
            recs = self.vib["records"]
            w = self.pattern.max_charge_per_delay
            laws = {self.cfg.law: empirical.SD_LAWS[self.cfg.law]}
            plots.plot_waveforms(recs, os.path.join(out, "vib_waveforms.png"))
            plots.plot_spectra(recs, os.path.join(out, "vib_spectra.png"))
            plots.plot_ppv_distance(recs, w, laws, os.path.join(out, "vib_ppv.png"))
            plots.plot_surface_ppv(self.vib["result"], self.pattern, recs,
                                   os.path.join(out, "vib_surface.png"))
            csv = os.path.join(out, "sensors.csv")
            with open(csv, "w", encoding="utf-8-sig") as f:
                f.write("sensor,x,y,z,distance_m,PPV_mm_s,PVS_mm_s,Vx,Vy,Vz,"
                        "freq_Hz,disp_mm,acc_g,scaled_distance\n")
                for r in recs:
                    c_ = r.ppv_components
                    f.write(f"{r.name},{r.position[0]:.2f},{r.position[1]:.2f},"
                            f"{r.position[2]:.2f},{r.distance:.2f},{r.ppv:.4f},"
                            f"{r.pvs:.4f},{c_[0]:.4f},{c_[1]:.4f},{c_[2]:.4f},"
                            f"{r.dominant_frequency:.1f},{r.peak_displacement:.5f},"
                            f"{r.peak_acceleration:.5f},{r.distance / w ** 0.5:.3f}\n")
            files += [csv]

        if self.frag:
            from .plots import plot_blast_behavior, plot_fragmentation, plot_muckpile
            plot_fragmentation(self.frag["result"], self.frag["stats"],
                               os.path.join(out, "frag_size.png"))
            plot_muckpile(self.frag["result"], os.path.join(out, "frag_muckpile.png"))
            plot_blast_behavior(self.frag["result"], self.frag["model"],
                                self.frag["load"],
                                os.path.join(out, "frag_behavior.png"))

        for n in sorted(os.listdir(out)):
            if n.endswith((".png", ".mp4", ".gif")):
                files.append(os.path.join(out, n))
        log(f"  저장 완료: {out}/ ({len(files)}개 파일)")
        return files


# ---------------------------------------------------------------------------
def kuz_ram(pattern, rock, explosive) -> dict:
    """Kuz-Ram 파쇄입도 예측 — 발파 실무의 표준 경험모델.

        X50 [cm] = A * K^(-0.8) * Q^(1/6) * (115/RWS)^(19/30)
        n        = (2.2 - 14B/D) * sqrt((1+S/B)/2) * (1-W/B) * (L/H)

    A(암반계수)는 7(연암) ~ 13(경암·괴상). 여기서는 UCS 로부터 환산한다.
    DEM 연결성분 해석이 퍼콜레이션 때문에 못 주는 값을 이 모델이 채운다.
    """
    B, S, H = pattern.burden, pattern.spacing, pattern.bench_height
    D_mm = pattern.hole_dia * 1000.0
    Q = pattern.charge_per_hole
    K = pattern.powder_factor
    L = pattern.holes[0].charge_length
    A = float(np.clip(7.0 + 6.0 * (rock.ucs / 1e6 - 30.0) / 170.0, 7.0, 13.0))

    x50 = A * K ** -0.8 * Q ** (1.0 / 6.0) * (115.0 / explosive.rws) ** (19.0 / 30.0)
    x50 /= 100.0                                     # cm -> m

    w_acc = 0.1                                      # 천공 정밀도 표준편차 [m]
    n = ((2.2 - 14.0 * B / D_mm) * math.sqrt((1.0 + S / B) / 2.0)
         * (1.0 - w_acc / B) * (L / H))
    n = float(np.clip(n, 0.7, 2.2))
    xc = x50 / (math.log(2.0) ** (1.0 / n))          # Rosin-Rammler 특성입경
    x80 = xc * (math.log(5.0)) ** (1.0 / n)
    oversize = math.exp(-((1.0 / xc) ** n))          # >1 m 비율
    return {"A": A, "X50": x50, "X80": x80, "Xc": xc, "n": n,
            "oversize_1m": oversize}


def fragmentation_stats(result, model) -> dict:
    """파쇄 입도 · 이동 · 비산 통계."""
    size, mass = result.fragment_size, result.fragment_mass
    order = np.argsort(size)
    s_sorted, m_sorted = size[order], mass[order]
    cum = np.cumsum(m_sorted) / max(m_sorted.sum(), 1e-12)

    def passing(frac: float) -> float:
        return float(np.interp(frac, cum, s_sorted))

    x50, x80 = passing(0.50), passing(0.80)

    # Rosin-Rammler  P = 1 - exp(-(x/Xc)^n)
    ok = (cum > 0.02) & (cum < 0.98) & (s_sorted > 0)
    if ok.sum() >= 3:
        y = np.log(-np.log(1.0 - cum[ok]))
        x = np.log(s_sorted[ok])
        n_rr, b = np.polyfit(x, y, 1)
        xc = float(np.exp(-b / n_rr)) if n_rr else x50
    else:
            n_rr, xc = 1.0, x50
    over_lim = 1.0
    oversize = float(m_sorted[s_sorted > over_lim].sum() / max(m_sorted.sum(), 1e-12))

    free = ~model.fixed
    disp = np.linalg.norm(result.pos - result.pos0, axis=1)
    moved = free & (disp > 0.5 * model.d)
    throw_mean = float(disp[moved].mean()) if moved.any() else 0.0
    throw_max = float(disp[free].max()) if free.any() else 0.0
    moved_frac = float(moved.sum() / max(int(free.sum()), 1))

    # 저항선 영역(자유면 ~ 첫 열, 굴착선 위)만 따로 본다. 전체 자유입자에는
    # 배후 암반이 섞여 있어 평균이 희석된다.
    pat = model.pattern
    x_first = min(h.x for h in pat.holes)
    burden_zone = (free & (model.pos0[:, 0] < x_first)
                   & (model.pos0[:, 2] > model.toe_z))
    if burden_zone.any():
        bd = disp[burden_zone]
        burden_mean = float(bd.mean())
        burden_moved = float((bd > 1.0).mean())
        out_face = float((result.pos[burden_zone, 0] < model.face_x).mean())
    else:
        burden_mean = burden_moved = out_face = 0.0

    v = result.peak_speed
    v_max = float(v[free].max()) if free.any() else 0.0
    v_mean = float(v[moved].mean()) if moved.any() else 0.0

    # 비산: 최적 사출각(45도) 가정한 탄도 도달거리로 보수적으로 본다
    g = 9.81
    ranges = v[free] ** 2 / g                       # v^2 sin(2*45)/g = v^2/g
    fly_thresh = 20.0                               # m/s 이상을 비산 위험으로 본다
    n_fly = int((v[free] > fly_thresh).sum())
    fly_range = float(np.percentile(ranges, 99.9)) if ranges.size else 0.0
    # 본드 연결성분으로 파쇄체를 세는 것은 본드 퍼콜레이션 문제다. 배위수 12~16
    # 격자에서는 본드를 90% 넘게 끊어야 비로소 덩어리가 쪼개지므로(44% 파괴에서는
    # 여전히 100% 가 하나의 클러스터), 그 미만에서는 입도값이 의미가 없다.
    broken_frac = result.broken / max(result.total_bonds, 1)
    reliable = broken_frac >= 0.90
    return {
        "broken_frac": broken_frac, "size_reliable": reliable,
        "X50": x50, "X80": x80, "X_max": float(size.max()),
        "mass_max": float(mass.max()), "Xc": xc, "n_rr": float(n_rr),
        "oversize": oversize, "oversize_limit": over_lim,
        "throw_mean": throw_mean, "throw_max": throw_max,
        "moved_frac": moved_frac, "burden_mean": burden_mean,
        "burden_moved": burden_moved, "out_face": out_face,
        "v_max": v_max, "v_mean": v_mean,
        "flyrock_range": fly_range, "n_flyrock": n_fly,
        "flyrock_frac": n_fly / max(int(free.sum()), 1),
        "safe_distance": 2.0 * fly_range,
        "cum": cum, "size_sorted": s_sorted,
    }
