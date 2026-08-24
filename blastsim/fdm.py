"""3D 유한차분(FDM) 탄성파 전파 해석 — 발파진동 원거리 해석용.

수치기법
--------
엇갈림 격자(staggered grid) 속도-응력 정식화 (Virieux 1986, Levander 1988).
공간 4차 / 시간 2차. 격자형 DEM(lattice.py) 대비 이점:

  * 파장당 요소수가 절반(약 5~6개)이면 되므로 3D 에서 격자수가 1/8
  * 포아송비를 자유롭게 지정할 수 있다 (DEM 격자는 nu=0.25 고정)
  * 임계 dt 가 약 2.5배 커서 스텝수가 준다

장 배치 (i,j,k 는 셀 인덱스, 실제 위치는 엇갈림)
    sxx,syy,szz : (i,   j,   k  )
    vx          : (i+½, j,   k  )
    vy          : (i,   j+½, k  )
    vz          : (i,   j,   k+½)
    sxy         : (i+½, j+½, k  )
    sxz         : (i+½, j,   k+½)
    syz         : (i,   j+½, k+½)

지배방정식
    rho dv/dt   = div(sigma) + f
    dsigma/dt   = lambda tr(D) I + 2 mu D          (D = 변형률속도)

자유면 — 진공 정식화(vacuum formulation)
    암반 밖 셀에 lambda = mu = 0, rho = 0 을 주면 그 경계가 자동으로 자유면이 된다.
    응력 미러링(stress imaging)보다 정확도는 조금 낮지만, **2자유면 벤치처럼 꺾인
    경계를 그대로 표현**할 수 있어 이 문제에 적합하다. 정확도 보완을 위해
    Moczo 방식의 유효매질 평균(전단계수 조화평균, 밀도 산술평균)을 쓴다.

흡수경계 — Cerjan 스펀지 층 (자유면에는 적용하지 않는다)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from .rock import Rock

# 4차 엇갈림 차분 계수
C1, C2 = 9.0 / 8.0, -1.0 / 24.0
_STENCIL_SUM = C1 + abs(C2)      # 안정조건에 쓰이는 계수합
HALO = 2                          # 4차 스텐실이 필요로 하는 여유 셀


def _core(shape: tuple[int, int, int]) -> tuple:
    """차분이 유효한 내부 영역 슬라이스."""
    return tuple(slice(HALO, n - HALO) for n in shape)


def _shift(base: tuple, axis: int, off: int) -> tuple:
    """core 슬라이스를 한 축으로 off 만큼 이동."""
    s = list(base)
    sl = s[axis]
    s[axis] = slice(sl.start + off, sl.stop + off)
    return tuple(s)


def d_plus(f: np.ndarray, axis: int, core: tuple, inv_h: float) -> np.ndarray:
    """전방 엇갈림 4차 미분  (f[i+1]-f[i]) 중심."""
    return (C1 * (f[_shift(core, axis, 1)] - f[core])
            + C2 * (f[_shift(core, axis, 2)] - f[_shift(core, axis, -1)])) * inv_h


def d_minus(f: np.ndarray, axis: int, core: tuple, inv_h: float) -> np.ndarray:
    """후방 엇갈림 4차 미분  (f[i]-f[i-1]) 중심."""
    return (C1 * (f[core] - f[_shift(core, axis, -1)])
            + C2 * (f[_shift(core, axis, 1)] - f[_shift(core, axis, -2)])) * inv_h


# ---------------------------------------------------------------------------
@dataclass
class BenchGeometry:
    """2자유면 벤치 형상.

    z = 0 이 벤치 상부면, z = -bench_height 가 하부 소단(자유면 앞쪽 바닥).
    x >= face_x 는 벤치 본체, x < face_x 는 이미 굴착된 하부 공간.

        z=0  ─────────────┐
                          │ ← 벤치면 (제2자유면, 수직 또는 경사)
        z=-H ─────────────┘
             x < face_x     x >= face_x

    Attributes
    ----------
    bench_height : 벤치고 H [m]
    face_x       : 벤치면(자유면)의 x 좌표 [m]
    face_angle   : 사면 경사각 [deg]. 0 이면 수직면.
                   양수면 상부가 앞으로 나온 오버행이 아니라 뒤로 눕는다.
    two_free_face: False 면 상부면만 자유면(1자유면)으로 둔다.
    full_space   : True 면 자유면이 없는 무한체. 파속·분산 검증 전용.
    """

    bench_height: float = 10.0
    face_x: float = 0.0
    face_angle: float = 0.0
    two_free_face: bool = True
    full_space: bool = False        # True 면 자유면 없는 무한체 (검증용)

    def solid_mask(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray) -> np.ndarray:
        """암반이 존재하는 셀 = True."""
        if self.full_space:
            return np.ones(X.shape, dtype=bool)
        if not self.two_free_face:
            return Z <= 0.0
        # 경사면: 깊이 z 에서의 면 위치 (z<0 이므로 -Z 가 깊이)
        shift = np.tan(math.radians(self.face_angle)) * (-Z)
        return (Z <= 0.0) & (X >= self.face_x - shift) | (Z <= -self.bench_height)


#: 흡수경계(Cerjan 스펀지) 기본 두께 [셀].  계측점은 반드시 이 층 밖에 두어야
#: 한다 — 안쪽에 두면 인위적으로 감쇠된 값을 읽는다.
SPONGE_CELLS = 20
SPONGE_ALPHA = 0.30


@dataclass
class FDMConfig:
    """FDM 해석 설정."""

    spacing: float | None = None     # 격자간격 [m] (None = 자동)
    max_frequency: float = 120.0     # 해상 목표 최대주파수 [Hz]
    damping_freq: float = 60.0       # 목표 감쇠비를 만족시킬 기준주파수 [Hz]
    points_per_wavelength: float = 6.0   # 4차 격자는 5~6개면 충분
    max_cells: int = 3_000_000
    cfl: float = 0.75                # dt = cfl * dt_max
    sponge_cells: int = SPONGE_CELLS   # 흡수층 두께 [셀]
    sponge_alpha: float = SPONGE_ALPHA  # 흡수 강도 (층 전체 기준)
    duration: float = 0.5
    record_every: int = 1
    snapshot_times: list[float] = field(default_factory=list)
    progress: bool = True


class FDMModel:
    """엇갈림 격자 3D 탄성파 모델."""

    def __init__(
        self,
        rock: Rock,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        depth: float,
        spacing: float,
        geometry: BenchGeometry | None = None,
        poisson: float | None = None,
        sponge_cells: int = SPONGE_CELLS,
        sponge_alpha: float = SPONGE_ALPHA,
        air_cells: int = 4,
    ) -> None:
        self.rock = rock
        self.h = float(spacing)
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        self.depth = float(depth)
        self.geom = geometry or BenchGeometry(two_free_face=False)
        # FDM 은 DEM 격자와 달리 포아송비를 자유롭게 쓸 수 있다
        self.nu = rock.poisson if poisson is None else float(poisson)

        # 진공 정식화에서 자유면이 성립하려면 지표 위에 진공 셀이 있어야 한다.
        # 4차 스텐실이 2셀을 보므로 최소 HALO+2 층을 둔다.
        self.n_air = max(HALO + 2, int(air_cells))

        self.nx = max(8, int(round((self.x1 - self.x0) / self.h)) + 1)
        self.ny = max(8, int(round((self.y1 - self.y0) / self.h)) + 1)
        self.nz = max(8, int(round(self.depth / self.h)) + 1) + self.n_air
        self.shape = (self.nx, self.ny, self.nz)
        self.n = self.nx * self.ny * self.nz

        self.xs = self.x0 + np.arange(self.nx) * self.h
        self.ys = self.y0 + np.arange(self.ny) * self.h
        # z = 0 이 지표. 위쪽 n_air 층은 진공.
        self.zs = -self.depth + np.arange(self.nz) * self.h
        self.k_surface = self.nz - 1 - self.n_air              # zs[k_surface] = 0

        self._build_material()
        self._build_sponge(sponge_cells, sponge_alpha)

    # ---- 재료 --------------------------------------------------------------
    @property
    def mu(self) -> float:
        return self.rock.young / (2.0 * (1.0 + self.nu))

    @property
    def lam(self) -> float:
        return self.rock.young * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))

    @property
    def vp(self) -> float:
        return math.sqrt((self.lam + 2.0 * self.mu) / self.rock.density)

    @property
    def vs(self) -> float:
        return math.sqrt(self.mu / self.rock.density)

    def _build_material(self) -> None:
        X, Y, Z = np.meshgrid(self.xs, self.ys, self.zs, indexing="ij")
        self.solid = self.geom.solid_mask(X, Y, Z)
        s = self.solid.astype(np.float64)

        rho = self.rock.density * s
        mu = self.mu * s
        lam = self.lam * s

        # 법선응력 셀 (i,j,k) 에서는 그대로 사용
        self.lam2mu = lam + 2.0 * mu
        self.lam_ = lam
        self.mu_ = mu

        # 속도점 밀도 = 산술평균 (Moczo 유효매질)
        self.rho_x = self._avg_shift(rho, 0)
        self.rho_y = self._avg_shift(rho, 1)
        self.rho_z = self._avg_shift(rho, 2)

        # 전단응력점 전단계수 = 4점 조화평균 (하나라도 진공이면 0 -> 자유면)
        self.mu_xy = self._harm4(mu, 0, 1)
        self.mu_xz = self._harm4(mu, 0, 2)
        self.mu_yz = self._harm4(mu, 1, 2)

    @staticmethod
    def _avg_shift(a: np.ndarray, axis: int) -> np.ndarray:
        """(a[i] + a[i+1]) / 2 — 마지막 층은 자기 값 유지."""
        out = a.copy()
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[axis] = slice(0, -1)
        sl1[axis] = slice(1, None)
        out[tuple(sl0)] = 0.5 * (a[tuple(sl0)] + a[tuple(sl1)])
        return out

    @staticmethod
    def _harm4(a: np.ndarray, ax1: int, ax2: int) -> np.ndarray:
        """전단응력점의 네 이웃 조화평균. 하나라도 0(진공)이면 0 -> 자유면 조건."""
        out = np.zeros_like(a)
        s1 = [slice(None)] * 3
        s1[ax1] = slice(0, -1)
        s1[ax2] = slice(0, -1)
        i0 = tuple(s1)
        sA = list(s1); sA[ax1] = slice(1, None); sA = tuple(sA)
        sB = list(s1); sB[ax2] = slice(1, None); sB = tuple(sB)
        sC = list(s1); sC[ax1] = slice(1, None); sC[ax2] = slice(1, None); sC = tuple(sC)

        vals = (a[i0], a[sA], a[sB], a[sC])
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = sum(np.where(v > 0.0, 1.0 / np.maximum(v, 1e-300), np.inf) for v in vals)
            out[i0] = np.where(np.isfinite(inv), 4.0 / inv, 0.0)
        return out

    # ---- 흡수경계 ----------------------------------------------------------
    def _build_sponge(self, nb: int, alpha: float) -> None:
        """Cerjan 스펀지. 자유면(상부면, 벤치면)에는 적용하지 않는다."""
        nb = int(min(nb, min(self.shape) // 3))
        w = np.ones(self.shape)
        if nb <= 0:
            self.sponge = w
            return
        # d=0 이 최외곽. 안쪽으로 갈수록 1.0 에 수렴하는 완만한 프로파일이라야
        # 스펀지 입구에서의 인위적 반사가 생기지 않는다.
        d = np.arange(nb)
        taper = np.exp(-((alpha * (nb - d) / nb) ** 2))
        # x, y 는 양쪽, z 는 아래쪽만 (위쪽은 자유면/진공).
        # 무한체 검증 모드에서는 z 위쪽에도 흡수경계가 필요하다.
        z_both = bool(getattr(self.geom, "full_space", False))
        for axis, both in ((0, True), (1, True), (2, z_both)):
            for side in ((0, 1) if both else (0,)):
                sl = [slice(None)] * 3
                for m in range(nb):
                    sl[axis] = m if side == 0 else self.shape[axis] - 1 - m
                    np.multiply(w[tuple(sl)], taper[m], out=w[tuple(sl)])
        self.sponge = w

    def sponge_weight(self, pts: np.ndarray) -> np.ndarray:
        """주어진 좌표에서의 스펀지 가중치(1.0 = 흡수층 밖).

        계측점이 흡수층 안에 들어가면 그 기록은 인위적으로 감쇠된 값이라
        감쇠지수도 보정계수도 모두 틀어진다. 해석 전에 확인하기 위한 것.
        """
        pts = np.atleast_2d(np.asarray(pts, dtype=float))
        i = np.clip(np.rint((pts[:, 0] - self.x0) / self.h).astype(int), 0, self.nx - 1)
        j = np.clip(np.rint((pts[:, 1] - self.y0) / self.h).astype(int), 0, self.ny - 1)
        k = np.clip(np.rint((pts[:, 2] + self.depth) / self.h).astype(int), 0, self.nz - 1)
        return self.sponge[i, j, k]

    # ---- 수치 파라미터 ------------------------------------------------------
    @property
    def dt_max(self) -> float:
        """4차 3D 안정조건  dt <= h / (Vp * sqrt(3) * (C1+|C2|))."""
        return self.h / (self.vp * math.sqrt(3.0) * _STENCIL_SUM)

    @property
    def max_frequency(self) -> float:
        """해상 최대주파수 [Hz] — 파장당 6요소(S파) 기준."""
        return self.vs / (6.0 * self.h)

    def nearest(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        pts = np.atleast_2d(np.asarray(points, dtype=float))
        i = np.clip(np.round((pts[:, 0] - self.x0) / self.h), 0, self.nx - 1).astype(int)
        j = np.clip(np.round((pts[:, 1] - self.y0) / self.h), 0, self.ny - 1).astype(int)
        k = np.clip(np.round((pts[:, 2] + self.depth) / self.h), 0, self.nz - 1).astype(int)
        return i, j, k

    def memory_mb(self) -> float:
        return self.n * 8 * 17 / 1e6

    def summary(self) -> str:
        vac = 100.0 * (1.0 - self.solid.mean())
        return (
            f"[FDM 격자] {self.nx} x {self.ny} x {self.nz} = {self.n:,} 셀"
            f"  (진공 {vac:.0f}%)\n"
            f"  영역 x[{self.x0:.0f}, {self.x1:.0f}]  y[{self.y0:.0f}, {self.y1:.0f}]  "
            f"z[-{self.depth:.0f}, 0] m,  격자간격 h = {self.h:.2f} m\n"
            f"  Vp = {self.vp:,.0f} m/s,  Vs = {self.vs:,.0f} m/s,  nu = {self.nu:.2f}"
            f"  (DEM 격자와 달리 자유 지정 가능)\n"
            f"  지표 k = {self.k_surface} (위 {self.n_air}층 진공 = 자유면)\n"
            f"  임계 dt = {self.dt_max * 1e6:.1f} us,  해상 최대주파수 ≈ "
            f"{self.max_frequency:.0f} Hz,  메모리 ≈ {self.memory_mb():.0f} MB"
        )


# ---------------------------------------------------------------------------
@dataclass
class FDMResult:
    time: np.ndarray                       # (nt,)
    velocity: np.ndarray                   # (nt, n_sensor, 3) [m/s]
    sensor_pos: np.ndarray
    sensor_names: list[str]
    surface_ppv: np.ndarray | None = None  # (nx*ny,) 지표 최대 |v|
    surface_pos: np.ndarray | None = None
    snapshots: dict = field(default_factory=dict)
    dt: float = 0.0
    wall_time: float = 0.0
    peak_velocity: float = 0.0


class CavitySource:
    """등가공동 압력원 — 공동 셀의 법선응력에 -dP 를 주입한다.

    압력 P 인 공동은 그 내부 응력이 sigma_ii = -P 인 상태와 같으므로,
    매 스텝 압력 증분만큼 법선응력을 밀어 넣으면 공동 벽이 주변 암반을 민다.
    (탄성해 u_r = P a^3 / (4 mu r^2) 와 대조 검증됨 — tests 참조)
    """

    def __init__(self, model: FDMModel, holes, explosive, source_cfg) -> None:
        self.m = model
        self.exp = explosive
        self.cfg = source_cfg
        self.cells: list[np.ndarray] = []   # (i,j,k) 인덱스 배열
        self.delay: list[float] = []
        self.pressure: list[float] = []
        self._prev: list[float] = []
        self._build(holes)

    def _build(self, holes) -> None:
        m = self.m
        X, Y, Z = np.meshgrid(m.xs, m.ys, m.zs, indexing="ij")
        r_eq = self.cfg.cavity_factor * m.h
        for h in holes:
            if h.charge_length <= 0 or h.charge_weight <= 0:
                continue
            r = np.hypot(X - h.x, Y - h.y)
            sel = (r <= r_eq * 1.05) & (Z >= h.z_bottom) & (Z <= h.charge_top) & m.solid
            idx = np.flatnonzero(sel.ravel())
            if idx.size == 0:
                continue
            self.cells.append(idx)
            self.delay.append(h.delay)
            self.pressure.append(self._equivalent_pressure(h, r_eq))
            self._prev.append(0.0)

    def _equivalent_pressure(self, hole, r_eq: float) -> float:
        c = self.cfg
        r_h = hole.hole_dia / 2.0
        r_c = c.crush_ratio * r_h
        p_b = self.exp.borehole_pressure(hole.charge_dia, hole.hole_dia)
        p = p_b * (r_h / r_c) ** c.alpha_crush
        if r_eq > r_c:
            p *= (r_c / r_eq) ** c.alpha_elastic
        return c.efficiency * p

    def apply(self, sxx, syy, szz, t: float) -> None:
        """법선응력 배열(평탄 뷰)에 압력 증분을 주입."""
        for n, (idx, t0, p0) in enumerate(zip(self.cells, self.delay, self.pressure)):
            dt_ = t - t0
            if dt_ <= 0.0 or dt_ > 12.0 * self.exp.decay_time:
                if self._prev[n] != 0.0 and dt_ > 0:
                    dp = -self._prev[n]
                    self._prev[n] = 0.0
                    for a in (sxx, syy, szz):
                        a[idx] -= dp
                continue
            p = p0 * float(self.exp.pressure_history(np.array([dt_]))[0])
            dp = p - self._prev[n]
            self._prev[n] = p
            if dp != 0.0:
                for a in (sxx, syy, szz):
                    a[idx] -= dp          # 압축이 음의 수직응력

    def summary(self) -> str:
        if not self.cells:
            return "[폭원] 하중 셀 없음"
        n = sum(c.size for c in self.cells)
        f_lo, f_hi = self.exp.corner_frequencies
        f_grid = self.m.max_frequency
        lost = self.exp.energy_fraction_above(f_grid)
        return (
            f"[폭원] 등가공동 반경 {self.cfg.cavity_factor * self.m.h:.2f} m, "
            f"등가압력 {self.pressure[0] / 1e6:.1f} MPa (eta={self.cfg.efficiency:.2f})\n"
            f"  하중 셀 {n:,}개 / {len(self.cells)}공\n"
            f"  폭원 평탄대역 {f_lo:.0f}~{f_hi:.0f} Hz, 격자 해상한계 {f_grid:.0f} Hz"
            f"  ->  격자가 버리는 방사에너지 {lost * 100:.0f}%"
        )


class FDMSolver:
    """엇갈림 격자 속도-응력 시간적분."""

    def __init__(self, model: FDMModel, source, config: FDMConfig | None = None) -> None:
        self.m = model
        self.src = source
        self.cfg = config or FDMConfig()
        self.core = _core(model.shape)
        self.inv_h = 1.0 / model.h

        # Kelvin-Voigt 점성 (= 강성비례 감쇠).  sigma = C:eps + beta*C:eps_dot
        #   zeta(f) = pi * f * beta   ->   beta = zeta / (pi * f_ref)
        # 저주파는 거의 감쇠되지 않고 고주파일수록 강하게 감쇠되므로, 실제 암반의
        # 거동과 격자 상한 부근 수치잡음을 함께 처리한다. (DEM 솔버와 동일한 취지)
        self.beta = model.rock.damping_ratio / (math.pi * self.cfg.damping_freq)
        # 점성항은 안정 dt 를 줄인다: dt <= dt_e*(sqrt(1+zm^2) - zm), zm = beta/dt_e
        dt_e = model.dt_max
        zm = self.beta / (2.0 * dt_e)
        self.dt_max_damped = dt_e * (math.sqrt(1.0 + zm * zm) - zm)
        self.dt = self.cfg.cfl * self.dt_max_damped

        m = model
        # dt 를 미리 곱해 둔 계수 (진공 셀은 0 이므로 자동으로 자유면)
        inv = lambda a: np.where(a > 0.0, 1.0 / np.maximum(a, 1e-300), 0.0)
        self.cvx = self.dt * inv(m.rho_x)
        self.cvy = self.dt * inv(m.rho_y)
        self.cvz = self.dt * inv(m.rho_z)
        self.c_l2m = self.dt * m.lam2mu
        self.c_lam = self.dt * m.lam_
        self.c_mxy = self.dt * m.mu_xy
        self.c_mxz = self.dt * m.mu_xz
        self.c_myz = self.dt * m.mu_yz

        # 증분 버퍼 (Kelvin-Voigt 점성항에 재사용)
        cs = tuple(sl.stop - sl.start for sl in self.core)
        self._inc = [np.empty(cs) for _ in range(6)]

    # ---- 시간적분 ----------------------------------------------------------
    def run(self, sensor_points, sensor_names=None) -> FDMResult:
        m, cfg, core = self.m, self.cfg, self.core
        z = lambda: np.zeros(m.shape)
        vx, vy, vz = z(), z(), z()
        sxx, syy, szz, sxy, sxz, syz = z(), z(), z(), z(), z(), z()
        flat = {n: a.reshape(-1) for n, a in
                (("sxx", sxx), ("syy", syy), ("szz", szz))}

        si, sj, sk = m.nearest(sensor_points)
        names = sensor_names or [f"S{i + 1}" for i in range(si.size)]

        n_steps = max(1, int(round(cfg.duration / self.dt)))
        n_rec = n_steps // cfg.record_every + 1
        rec_t = np.zeros(n_rec)
        rec_v = np.zeros((n_rec, si.size, 3))
        ks = m.k_surface
        surf_ppv = np.zeros((m.nx, m.ny))
        snaps: dict[float, np.ndarray] = {}
        todo = sorted(cfg.snapshot_times)

        ih, sp = self.inv_h, m.sponge
        peak, ri = 0.0, 0
        t0 = time.time()

        for step in range(n_steps):
            t = step * self.dt

            # --- 응력 증분 ---
            #   d(sxx)/dt = (lam+2mu) dvx/dx + lam (dvy/dy + dvz/dz)
            #             = lam*div + 2mu*dvx/dx
            dvx_dx = d_minus(vx, 0, core, ih)
            dvy_dy = d_minus(vy, 1, core, ih)
            dvz_dz = d_minus(vz, 2, core, ih)
            div = dvx_dx + dvy_dy + dvz_dz
            c_lam, c2mu = self.c_lam[core], self.c_l2m[core] - self.c_lam[core]
            i_xx, i_yy, i_zz, i_xy, i_xz, i_yz = self._inc
            np.multiply(c_lam, div, out=i_xx); i_xx += c2mu * dvx_dx
            np.multiply(c_lam, div, out=i_yy); i_yy += c2mu * dvy_dy
            np.multiply(c_lam, div, out=i_zz); i_zz += c2mu * dvz_dz
            np.multiply(self.c_mxy[core],
                        d_plus(vx, 1, core, ih) + d_plus(vy, 0, core, ih), out=i_xy)
            np.multiply(self.c_mxz[core],
                        d_plus(vx, 2, core, ih) + d_plus(vz, 0, core, ih), out=i_xz)
            np.multiply(self.c_myz[core],
                        d_plus(vy, 2, core, ih) + d_plus(vz, 1, core, ih), out=i_yz)

            # 탄성 응력 갱신 + 점성 응력 가산 (다음 속도갱신에만 쓰고 되돌린다)
            bdt = self.beta / self.dt
            for a, inc in ((sxx, i_xx), (syy, i_yy), (szz, i_zz),
                           (sxy, i_xy), (sxz, i_xz), (syz, i_yz)):
                a[core] += (1.0 + bdt) * inc

            self.src.apply(flat["sxx"], flat["syy"], flat["szz"], t)

            # --- 속도 갱신 ---
            vx[core] += self.cvx[core] * (d_plus(sxx, 0, core, ih)
                                          + d_minus(sxy, 1, core, ih)
                                          + d_minus(sxz, 2, core, ih))
            vy[core] += self.cvy[core] * (d_minus(sxy, 0, core, ih)
                                          + d_plus(syy, 1, core, ih)
                                          + d_minus(syz, 2, core, ih))
            vz[core] += self.cvz[core] * (d_minus(sxz, 0, core, ih)
                                          + d_minus(syz, 1, core, ih)
                                          + d_plus(szz, 2, core, ih))

            # 점성 성분 제거 -> 저장되는 것은 탄성 응력
            for a, inc in ((sxx, i_xx), (syy, i_yy), (szz, i_zz),
                           (sxy, i_xy), (sxz, i_xz), (syz, i_yz)):
                a[core] -= bdt * inc

            # --- 흡수경계 (Cerjan 스펀지) ---
            for a in (vx, vy, vz, sxx, syy, szz, sxy, sxz, syz):
                a *= sp

            # --- 기록 ---
            if step % cfg.record_every == 0 and ri < n_rec:
                rec_t[ri] = t
                rec_v[ri, :, 0] = vx[si, sj, sk]
                rec_v[ri, :, 1] = vy[si, sj, sk]
                rec_v[ri, :, 2] = vz[si, sj, sk]
                ri += 1

            vs = np.sqrt(vx[:, :, ks] ** 2 + vy[:, :, ks] ** 2 + vz[:, :, ks] ** 2)
            np.maximum(surf_ppv, vs, out=surf_ppv)
            if todo and t >= todo[0]:
                snaps[todo.pop(0)] = vs.ravel().copy()

            vmax = float(np.abs(vz).max())
            peak = max(peak, vmax)
            if not np.isfinite(vmax) or vmax > 1e4:
                raise RuntimeError(
                    f"FDM 발산 (step {step}, t={t * 1e3:.1f} ms, vmax={vmax:.3g} m/s). "
                    f"cfl 을 낮추세요 (현재 {cfg.cfl}).")
            if cfg.progress and step % max(1, n_steps // 20) == 0:
                print(f"\r  FDM {100.0 * step / n_steps:5.1f}%  t={t * 1e3:6.1f} ms  "
                      f"vmax={vmax * 1000:8.2f} mm/s", end="", flush=True)

        if cfg.progress:
            print(f"\r  FDM 완료 100.0%  ({time.time() - t0:.1f} s)" + " " * 30)

        X, Y = np.meshgrid(m.xs, m.ys, indexing="ij")
        spos = np.column_stack([X.ravel(), Y.ravel(), np.zeros(X.size)])
        pos = np.column_stack([m.xs[si], m.ys[sj], m.zs[sk]])
        return FDMResult(time=rec_t[:ri], velocity=rec_v[:ri], sensor_pos=pos,
                         sensor_names=list(names), surface_ppv=surf_ppv.ravel(),
                         surface_pos=spos, snapshots=snaps, dt=self.dt,
                         wall_time=time.time() - t0, peak_velocity=peak)

    def summary(self) -> str:
        zeta = lambda f: math.pi * f * self.beta
        return (f"[FDM 솔버] dt = {self.dt * 1e6:.1f} us "
                f"(무감쇠 임계 {self.m.dt_max * 1e6:.1f} us -> 점성 포함 "
                f"{self.dt_max_damped * 1e6:.1f} us, CFL={self.cfg.cfl}),  스텝수 = "
                f"{max(1, int(self.cfg.duration / self.dt)):,}\n"
                f"  공간 4차 / 시간 2차,  스펀지 {self.cfg.sponge_cells}셀\n"
                f"  Kelvin-Voigt 감쇠 beta = {self.beta * 1e6:.1f} us "
                f"(zeta={self.m.rock.damping_ratio} @ {self.cfg.damping_freq:.0f} Hz)  ->  "
                f"10Hz {zeta(10):.4f} / 50Hz {zeta(50):.4f} / "
                f"{self.m.max_frequency:.0f}Hz {zeta(self.m.max_frequency):.3f}")
