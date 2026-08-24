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
            "",
            "-" * 78,
            "  환산거리 회귀 (지발당 최대장약량 W = %.1f kg)" % w,
            "-" * 78,
            f"  DEM 해석   : {law}",
            f"  참조 경험식 : {ref}",
            f"  폭원효율 보정배수 eta_cal = {self.calibration_factor(target):.2f}  "
            f"(1.0 이면 해석이 경험식과 일치)",
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
