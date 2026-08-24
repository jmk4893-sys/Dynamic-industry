"""전체 해석 흐름을 묶는 드라이버.

    암반 + 폭약 + 발파패턴  ->  격자 자동생성  ->  폭원 하중  ->  시간적분
    ->  PPV/주파수 산출  ->  경험식·규제기준 대비 검토  ->  그림/보고서
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

from . import empirical, plots, sensors
from .explosives import Explosive
from .lattice import Lattice
from .pattern import BlastPattern
from .rock import Rock
from .solver import DEMSolver, Result, SolverConfig
from .source import BlastSource, SourceConfig


@dataclass
class DomainConfig:
    """해석 영역 및 격자 해상도 설정."""

    margin: float = 15.0            # 발파공/계측점 외곽 최소 여유 [m]
    lateral_factor: float = 0.60    # 측방 반폭 >= factor * 최원거리 (기하감쇠 확보)
    depth_factor: float = 0.60      # 모델 심도 >= factor * 최원거리
    depth: float | None = None      # 모델 심도 [m] (None = 자동)
    spacing: float | None = None    # 입자간격 [m] (None = 자동)
    max_frequency: float = 100.0    # 해상 목표 최대주파수 [Hz]
    max_particles: int = 400_000    # 계산량 상한
    min_spacing: float = 0.5


def auto_spacing(rock: Rock, pattern: BlastPattern, cfg: DomainConfig,
                 extent: tuple[float, float, float]) -> float:
    """해상도 요구와 계산량 상한을 함께 만족하는 입자간격 산정."""
    d_res = rock.s_velocity / (10.0 * cfg.max_frequency)      # 파장당 10요소
    d_geo = min(pattern.burden, pattern.spacing) / 2.0        # 공 배치 해상
    d = max(cfg.min_spacing, min(d_res, d_geo))
    lx, ly, lz = extent
    while (lx / d + 1) * (ly / d + 1) * (lz / d + 1) > cfg.max_particles:
        d *= 1.12
    return d


@dataclass
class BlastSimulation:
    """암발파 진동전파 3D DEM 해석."""

    rock: Rock
    explosive: Explosive
    pattern: BlastPattern
    sensor_points: np.ndarray
    sensor_names: list[str]
    domain: DomainConfig = field(default_factory=DomainConfig)
    source_cfg: SourceConfig = field(default_factory=SourceConfig)
    solver_cfg: SolverConfig = field(default_factory=SolverConfig)

    lattice: Lattice = field(init=False, default=None)
    source: BlastSource = field(init=False, default=None)
    solver: DEMSolver = field(init=False, default=None)
    result: Result = field(init=False, default=None)
    records: list = field(init=False, default_factory=list)
    calibration: float = field(init=False, default=1.0)

    # ---- 모델 구성 -------------------------------------------------------
    def build(self) -> "BlastSimulation":
        hp = self.pattern.positions()
        sp = np.atleast_2d(self.sensor_points)
        cx, cy = self.source_center
        r_max = float(np.hypot(sp[:, 0] - cx, sp[:, 1] - cy).max())

        allx = np.concatenate([hp[:, 0], sp[:, 0]])
        ally = np.concatenate([hp[:, 1], sp[:, 1]])
        m = self.domain.margin

        # 측방 반폭이 부족하면 파가 측면 경계에 '스치듯' 입사한다. 점성 흡수경계는
        # 이 경우 흡수율이 급격히 떨어져 반사파가 직접파에 실려오고, 결과적으로
        # 기하감쇠가 과소평가된다(감쇠지수 n 이 비정상적으로 작아짐).
        half = max(self.domain.lateral_factor * r_max, m)
        x_range = (float(min(allx.min() - m, cx - half)), float(max(allx.max() + m, cx + half)))
        y_range = (float(min(ally.min() - m, cy - half)), float(max(ally.max() + m, cy + half)))

        hole_depth = self.pattern.bench_height + self.pattern.subdrill
        depth = self.domain.depth or max(
            2.0 * hole_depth, self.domain.depth_factor * r_max, 20.0)

        extent = (x_range[1] - x_range[0], y_range[1] - y_range[0], depth)
        d = self.domain.spacing or auto_spacing(self.rock, self.pattern, self.domain, extent)

        self.lattice = Lattice(self.rock, x_range, y_range, depth, d)
        self.source = BlastSource(self.lattice, self.pattern, self.explosive, self.source_cfg)
        self.solver = DEMSolver(self.lattice, self.source, self.solver_cfg)
        return self

    @property
    def source_center(self) -> tuple[float, float]:
        hp = self.pattern.positions()
        return (float(hp[:, 0].mean()), float(hp[:, 1].mean()))

    # ---- 실행 ------------------------------------------------------------
    def run(self) -> "BlastSimulation":
        if self.lattice is None:
            self.build()
        if not self.solver_cfg.duration or self.solver_cfg.duration <= 0:
            self.solver_cfg.duration = self._auto_duration()
        self.result = self.solver.run(self.sensor_points, self.sensor_names)
        self.records = sensors.build_records(self.result, self.source_center)
        return self

    def _auto_duration(self) -> float:
        """마지막 공 기폭 + 최원거리 계측점 도달 + 여유."""
        sp = np.atleast_2d(self.sensor_points)
        cx, cy = self.source_center
        rmax = float(np.hypot(sp[:, 0] - cx, sp[:, 1] - cy).max())
        travel = rmax / self.rock.r_velocity
        return self.pattern.total_duration + travel + 25.0 * self.explosive.decay_time + 0.05

    # ---- 후처리 ----------------------------------------------------------
    def fitted_law(self) -> empirical.ScaledDistanceLaw:
        d = [r.distance for r in self.records]
        v = [r.ppv for r in self.records]
        return empirical.fit_law(d, v, self.pattern.max_charge_per_delay)

    def calibration_factor(self, target: str = "kr_mean") -> float:
        """해석 PPV 를 목표 경험식에 맞추는 폭원 효율 보정배수."""
        return empirical.calibrate_efficiency(
            [r.distance for r in self.records], [r.ppv for r in self.records],
            self.pattern.max_charge_per_delay, empirical.SD_LAWS[target],
        )

    def _frequency_note(self) -> str:
        """탁월주파수가 격자 해상한계에 붙어 있으면 신뢰할 수 없음을 알린다."""
        f_grid = self.lattice.max_frequency
        f_obs = max(r.dominant_frequency for r in self.records)
        if f_obs < 0.8 * f_grid:
            return f"  (격자 해상한계 {f_grid:.0f} Hz — 관측 탁월주파수가 그 아래이므로 유효)"
        return (
            f"  [!] 탁월주파수({f_obs:.0f} Hz)가 격자 해상한계({f_grid:.0f} Hz)에 근접합니다.\n"
            f"      주파수 값은 신뢰하지 마십시오. PPV 는 저주파가 지배하므로 상대적으로 덜 민감합니다.\n"
            f"      개선: 격자를 조밀하게(--grid, --max-freq) 하거나, 절리 산란에 의한 고주파\n"
            f"      감쇠를 --damp-band 상한을 낮춰 근사하십시오 (예: --damp-band 10 60).")

    def apply_calibration(self, target: str = "kr_mean", factor: float | None = None) -> float:
        """폭원 전달효율 eta 를 보정해 계측결과를 재척도한다.

        모델은 폭원 세기에 **선형**이므로(본드 파괴가 없는 한) 속도 이력에 배수를
        곱하는 것으로 eta 를 바꾼 재해석과 동일하다. 본드가 파괴된 경우에는
        비선형이므로 eta 를 직접 지정해 재해석해야 한다.
        """
        if self.result.broken_bonds > 0:
            print(f"  [경고] 본드 {self.result.broken_bonds:,}개가 파괴되어 모델이 비선형입니다. "
                  f"SourceConfig(efficiency=...) 로 재해석하세요.")
        f = float(factor if factor is not None else self.calibration_factor(target))
        for r in self.records:
            r.velocity = r.velocity * f
        if self.result.surface_ppv is not None:
            self.result.surface_ppv = self.result.surface_ppv * f
        for k in list(self.result.snapshots):
            self.result.snapshots[k] = self.result.snapshots[k] * f
        self.calibration *= f
        return f

    def report(self, target: str = "kr_mean") -> str:
        r = self.records
        w = self.pattern.max_charge_per_delay
        law = self.fitted_law()
        ref = empirical.SD_LAWS[target]
        near = min(r, key=lambda x: x.distance)
        far = max(r, key=lambda x: x.distance)

        lines = [
            "=" * 78,
            "  암발파 진동전파 3D DEM 해석 결과 보고",
            "=" * 78,
            self.rock.summary(), "",
            self.explosive.summary(self.pattern.charge_dia, self.pattern.hole_dia), "",
            self.pattern.summary(), "",
            self.lattice.summary(), "",
            self.source.summary(), "",
            self.solver.summary(),
            f"  해석시간 = {self.solver_cfg.duration * 1000:.0f} ms, "
            f"소요시간 = {self.result.wall_time:.1f} s, "
            f"파괴본드 = {self.result.broken_bonds:,} / {self.result.total_bonds:,} "
            f"({100 * self.result.broken_bonds / max(1, self.result.total_bonds):.2f}%)",
            "",
            "-" * 78,
            "  계측점별 진동 결과",
            "-" * 78,
            sensors.table(r),
            self._frequency_note(),
            "",
            "-" * 78,
            "  환산거리 회귀 (지발당 최대장약량 W = %.1f kg)" % w,
            "-" * 78,
            f"  DEM 해석   : {law}",
            f"  참조 경험식 : {ref}",
            f"  감쇠지수 비교: DEM n = {law.n:.2f}  vs  경험식 n = {ref.n:.2f}  "
            f"({'양호' if abs(law.n - ref.n) < 0.3 else '차이 큼 — 격자/감쇠 재검토'})",
            "",]
        if abs(self.calibration - 1.0) < 1e-9:
            lines += [
                f"  [!] 폭원 미보정 상태입니다. 경험식 대비 보정배수 eta_cal = "
                f"{self.calibration_factor(target):.2f}",
                "      등가공동 폭원은 공벽(수십 mm)의 파쇄·가스침투·자유면 이완 같은",
                "      비탄성 결합과정을 압력감쇠식으로 치환하므로 절대 진폭에 큰 불확실성이",
                "      있습니다. 절대값이 필요하면 시험발파 실측으로 eta 를 보정하십시오",
                "      (--calibrate 또는 sim.apply_calibration()).",
                "      * 감쇠지수 n 과 패턴 변경의 '상대 효과'는 보정과 무관하게 유효합니다.",
            ]
        else:
            lines += [f"  폭원 보정 적용됨: eta = {self.calibration:.2f} (기준 {ref.name})"]
        lines += [
            "",
            "-" * 78,
            f"  규제기준 검토  (최근접 계측점 {near.name}, D = {near.distance:.0f} m)",
            "-" * 78,
            empirical.regulation_table(near.ppv),
            "",
            "  [허용 이격거리 / 허용 장약량]",
        ]
        for name, lim in empirical.REGULATION:
            sd = law.safe_distance(w, lim)
            wa = law.allowable_charge(near.distance, lim)
            lines.append(f"   {name:<22s} 최소이격 {sd:7.1f} m   또는  "
                         f"D={near.distance:.0f}m 에서 지발당 {wa:7.2f} kg 이하")
        lines += [
            "",
            f"  최원거리 {far.name} (D={far.distance:.0f} m): PPV {far.ppv:.2f} mm/s, "
            f"탁월주파수 {far.dominant_frequency:.0f} Hz",
            "=" * 78,
        ]
        return "\n".join(lines)

    def save_figures(self, outdir: str = "output", target: str = "kr_mean") -> list[str]:
        os.makedirs(outdir, exist_ok=True)
        p = lambda n: os.path.join(outdir, n)
        laws = {k: v for k, v in empirical.SD_LAWS.items() if k in (target, "usbm")}
        files = []
        plots.plot_layout(self.lattice, self.pattern, self.records, p("1_layout.png"))
        plots.plot_source(self.explosive, self.source, p("2_source.png"))
        plots.plot_waveforms(self.records, p("3_waveforms.png"))
        plots.plot_spectra(self.records, p("4_spectra.png"))
        plots.plot_ppv_distance(self.records, self.pattern.max_charge_per_delay,
                                laws, p("5_ppv_distance.png"))
        plots.plot_surface_ppv(self.result, self.pattern, self.records, p("6_surface_ppv.png"))
        plots.plot_snapshots(self.result, self.pattern, p("7_snapshots.png"))
        for n in ("1_layout.png", "2_source.png", "3_waveforms.png", "4_spectra.png",
                  "5_ppv_distance.png", "6_surface_ppv.png", "7_snapshots.png"):
            if os.path.exists(p(n)):
                files.append(p(n))
        return files

    def save_csv(self, path: str) -> None:
        """계측 결과 CSV 저장."""
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("sensor,x,y,z,distance_m,PPV_mm_s,PVS_mm_s,Vx,Vy,Vz,"
                    "freq_Hz,disp_mm,acc_g,scaled_distance\n")
            w = self.pattern.max_charge_per_delay
            for r in self.records:
                c = r.ppv_components
                f.write(f"{r.name},{r.position[0]:.2f},{r.position[1]:.2f},{r.position[2]:.2f},"
                        f"{r.distance:.2f},{r.ppv:.4f},{r.pvs:.4f},{c[0]:.4f},{c[1]:.4f},"
                        f"{c[2]:.4f},{r.dominant_frequency:.1f},{r.peak_displacement:.5f},"
                        f"{r.peak_acceleration:.5f},{r.distance / w ** 0.5:.3f}\n")
