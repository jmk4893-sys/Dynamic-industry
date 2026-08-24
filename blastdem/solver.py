"""명시적 시간적분 DEM 솔버 (중앙차분 / leapfrog).

지배방정식
    m*a = F_bond + F_visc + F_source + F_absorb + F_massdamp

본드 탄성력   f = k * ((u_j - u_i) . n0) * n0          (미소변형 선형화)
본드 점성력   f = beta * k * ((v_j - v_i) . n0) * n0   (강성비례 감쇠)
질량 감쇠     f = -alpha * m * v                       (질량비례 감쇠)
흡수경계      f = -(rho*Vp*A) v_n - (rho*Vs*A) v_t     (Lysmer-Kuhlemeyer)
본드파괴      eps > eps_t   -> 인장파괴(본드 제거)
              eps < -eps_c  -> 압축항복(힘 상한 = 파쇄대 에너지 소산)

Rayleigh 감쇠 C = alpha*M + beta*K
    zeta(f) = alpha/(2*omega) + beta*omega/2
    목표 감쇠비 zeta 를 두 주파수 f1, f2 에서 만족시키면
        alpha = 2*zeta*w1*w2/(w1+w2),   beta = 2*zeta/(w1+w2)

**강성비례 항(beta)이 왜 필수인가**: 질량비례 감쇠만 쓰면 zeta ∝ 1/omega 라
저주파를 더 감쇠시킨다. 실제 암반은 반대로 고주파가 빨리 감쇠하며, 격자가
해상하지 못하는 고주파 수치잡음도 남는다. beta 항이 이 둘을 함께 처리한다.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from .lattice import Lattice
from .source import BlastSource


@dataclass
class SolverConfig:
    duration: float = 0.5          # 해석 시간 [s] (0 = 자동)
    cfl: float = 0.25              # 시간간격 안전계수 (dt = cfl * dt_critical)
    damping_f1: float = 10.0       # Rayleigh 감쇠 기준주파수 하한 [Hz]
    damping_f2: float = 120.0      # Rayleigh 감쇠 기준주파수 상한 [Hz]
    allow_breakage: bool = True    # 본드 파괴 허용
    absorbing: bool = True         # 흡수경계 사용
    record_every: int = 1          # 계측 샘플링 간격 (스텝)
    snapshot_times: list[float] = field(default_factory=list)  # 파면 저장 시각 [s]
    progress: bool = True


@dataclass
class Result:
    """해석 결과 컨테이너."""

    time: np.ndarray                      # (nt,) [s]
    velocity: np.ndarray                  # (nt, n_sensor, 3) [m/s]
    sensor_pos: np.ndarray                # (n_sensor, 3)
    sensor_names: list[str]
    broken_bonds: int
    total_bonds: int
    snapshots: dict[float, np.ndarray] = field(default_factory=dict)  # t -> 표면 |v|
    surface_pos: np.ndarray | None = None
    surface_ppv: np.ndarray | None = None   # 지표 입자별 최대 |v| [m/s]
    dt: float = 0.0
    wall_time: float = 0.0
    peak_domain_velocity: float = 0.0


class DEMSolver:
    def __init__(
        self,
        lattice: Lattice,
        source: BlastSource,
        config: SolverConfig | None = None,
    ) -> None:
        self.lat = lattice
        self.src = source
        self.cfg = config or SolverConfig()

        rock = lattice.rock
        # Rayleigh 감쇠 계수
        w1 = 2.0 * math.pi * self.cfg.damping_f1
        w2 = 2.0 * math.pi * self.cfg.damping_f2
        z = rock.damping_ratio
        self.alpha = 2.0 * z * w1 * w2 / (w1 + w2)
        self.beta = 2.0 * z / (w1 + w2)

        # 강성비례 감쇠는 임계 dt 를 줄인다:
        #   dt_c = (2/w_max) * (sqrt(1+zmax^2) - zmax)
        wmax = lattice.omega_max
        zmax = self.alpha / (2.0 * wmax) + self.beta * wmax / 2.0
        self.dt_critical = (2.0 / wmax) * (math.sqrt(1.0 + zmax ** 2) - zmax)
        self.dt = self.cfg.cfl * self.dt_critical

        # 흡수경계 감쇠계수 [N*s/m]
        area = lattice.d ** 2
        self.c_n = rock.density * rock.p_velocity * area
        self.c_t = rock.density * rock.s_velocity * area
        # 본드 파괴 변형률
        self.eps_t = rock.tensile_strain
        self.eps_c = rock.compressive_strain

    def damping_ratio_at(self, freq: float) -> float:
        w = 2.0 * math.pi * freq
        return self.alpha / (2.0 * w) + self.beta * w / 2.0

    # ---- 내력 계산 -------------------------------------------------------
    def _bond_forces(self, u: np.ndarray, v: np.ndarray, force: np.ndarray) -> int:
        """본드 탄성력 + 강성비례 점성력을 force 에 누적. 규칙격자라 전부 슬라이스."""
        broken = 0
        bk = self.beta
        for g in self.lat.bonds:
            sa, sb, nrm = g.sa, g.sb, g.normal
            # 신장량 delta = (u_j - u_i).n0, 신장속도 ddot = (v_j - v_i).n0
            delta = ddot = None
            for c in g.axes:
                w = nrm[c]
                du = (u[sb + (c,)] - u[sa + (c,)]) * w
                dv = (v[sb + (c,)] - v[sa + (c,)]) * w
                delta = du if delta is None else delta + du
                ddot = dv if ddot is None else ddot + dv

            if self.cfg.allow_breakage:
                strain = delta / g.length
                fail = (g.active > 0) & g.breakable & (strain > self.eps_t)
                if fail.any():
                    g.active[fail] = 0.0
                    broken += int(fail.sum())
                # 압축 항복: 힘 상한 (파쇄대 에너지 소산)
                np.clip(delta, -self.eps_c * g.length, None, out=delta)
                delta *= g.active
                ddot *= g.active

            f = g.stiffness * (delta + bk * ddot)
            for c in g.axes:
                w = f * nrm[c]
                force[sa + (c,)] += w
                force[sb + (c,)] -= w
        return broken

    def _absorbing(self, v: np.ndarray, force: np.ndarray) -> None:
        for sl, axis in self.lat.boundary:
            for c in range(3):
                coeff = self.c_n if c == axis else self.c_t
                force[sl + (c,)] -= coeff * v[sl + (c,)]

    # ---- 시간적분 --------------------------------------------------------
    def run(self, sensor_points: np.ndarray, sensor_names: list[str] | None = None) -> Result:
        lat, cfg = self.lat, self.cfg
        shape3 = lat.shape + (3,)
        u = np.zeros(shape3)
        v = np.zeros(shape3)
        force = np.zeros(shape3)
        # 평탄 뷰 — 폭원 하중/계측은 평탄 인덱스를 쓴다 (복사 아님)
        uf, vf, ff = u.reshape(-1, 3), v.reshape(-1, 3), force.reshape(-1, 3)
        inv_m = 1.0 / lat.m

        s_idx = lat.nearest(sensor_points)
        names = sensor_names or [f"S{i + 1}" for i in range(len(s_idx))]

        n_steps = max(1, int(round(cfg.duration / self.dt)))
        n_rec = n_steps // cfg.record_every + 1
        rec_t = np.zeros(n_rec)
        rec_v = np.zeros((n_rec, s_idx.size, 3))
        snapshots: dict[float, np.ndarray] = {}
        snap_todo = sorted(cfg.snapshot_times)

        free = ~lat.protected               # 탄성코어 밖 = 진동해석 유효영역
        surf_ppv = np.zeros((lat.nx, lat.ny))
        broken, peak, ri = 0, 0.0, 0
        t0 = time.time()

        for step in range(n_steps):
            t = step * self.dt

            force.fill(0.0)
            broken += self._bond_forces(u, v, force)
            self.src.apply(ff, t)
            if cfg.absorbing:
                self._absorbing(v, force)
            force -= (self.alpha * lat.m) * v

            # leapfrog: v(t+dt/2), u(t+dt)
            v += force * (inv_m * self.dt)
            u += v * self.dt

            if step % cfg.record_every == 0 and ri < n_rec:
                rec_t[ri] = t
                rec_v[ri] = vf[s_idx]
                ri += 1

            vs = np.sqrt(v[:, :, -1, 0] ** 2 + v[:, :, -1, 1] ** 2 + v[:, :, -1, 2] ** 2)
            np.maximum(surf_ppv, vs, out=surf_ppv)
            if snap_todo and t >= snap_todo[0]:
                snapshots[snap_todo.pop(0)] = vs.ravel().copy()

            vmax = float(np.abs(v[free]).max())
            peak = max(peak, vmax)
            if not np.isfinite(vmax) or vmax > 1e4:
                raise RuntimeError(
                    f"해석 발산 (step {step}, t={t * 1e3:.1f} ms, vmax={vmax:.3g} m/s). "
                    f"cfl 값을 낮추세요 (현재 {cfg.cfl})."
                )
            if cfg.progress and step % max(1, n_steps // 20) == 0:
                print(f"\r  해석중 {100.0 * step / n_steps:5.1f}%  t={t * 1e3:6.1f} ms  "
                      f"vmax={vmax * 1000:8.2f} mm/s  파괴본드={broken:,}", end="", flush=True)

        if cfg.progress:
            print(f"\r  해석완료 100.0%  ({time.time() - t0:.1f} s)" + " " * 34)

        return Result(
            time=rec_t[:ri], velocity=rec_v[:ri], sensor_pos=lat.pos[s_idx],
            sensor_names=names, broken_bonds=broken, total_bonds=lat.n_bonds,
            snapshots=snapshots, surface_pos=lat.pos[lat.surface_idx],
            surface_ppv=surf_ppv.ravel(), dt=self.dt,
            wall_time=time.time() - t0, peak_domain_velocity=peak,
        )

    def summary(self) -> str:
        f_hi = self.lat.max_frequency
        return (
            f"[솔버] dt = {self.dt * 1e6:.1f} us (임계 {self.dt_critical * 1e6:.1f} us, "
            f"CFL={self.cfg.cfl}),  스텝수 = {max(1, int(self.cfg.duration / self.dt)):,}\n"
            f"  Rayleigh 감쇠 alpha = {self.alpha:.2f} 1/s, beta = {self.beta * 1e6:.2f} us  "
            f"(zeta={self.lat.rock.damping_ratio} @ {self.cfg.damping_f1:.0f}-"
            f"{self.cfg.damping_f2:.0f} Hz)\n"
            f"  감쇠비: {self.cfg.damping_f1:.0f}Hz {self.damping_ratio_at(self.cfg.damping_f1):.3f} / "
            f"50Hz {self.damping_ratio_at(50):.3f} / "
            f"{f_hi:.0f}Hz(격자한계) {self.damping_ratio_at(f_hi):.3f}\n"
            f"  본드파괴 {'ON' if self.cfg.allow_breakage else 'OFF'}, "
            f"흡수경계 {'ON' if self.cfg.absorbing else 'OFF'}"
        )
