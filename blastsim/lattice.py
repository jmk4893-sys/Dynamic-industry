"""3D DEM 격자(bonded-particle lattice) 생성.

모델 개요
---------
단순입방(simple cubic) 격자에 1차 이웃(축방향 6개)과 2차 이웃(면대각 12개)을
중심력(central-force) 본드로 연결한다. 본드 강성을 k1 = k2 = k 로 두면
격자가 정확히 **등방 탄성체**가 된다 (아래 유도 참조).

강성텐서 (affine 가정, V = d^3, 입자당 본드는 배위수의 절반)
    C_ijkl = (1/V) * sum_bond  k * L^2 * n_i n_j n_k n_l

  1차 이웃(3본드/입자, L=d)      : C11 += k/d
  2차 이웃(6본드/입자, L=sqrt2 d): C11 += 2k/d,  C12 += k/d,  C44 += k/d

  합계  C11 = 3k/d,  C12 = k/d,  C44 = k/d
  등방조건 C44 = (C11-C12)/2 가 k1=k2 에서 자동 만족된다.

따라서
    lambda = mu = k/d   ->   nu = 0.25 (고정),  E = 2.5 k/d
    k = 0.4 * E * d
    Vp = sqrt(3k/(d*rho)),  Vs = sqrt(k/(d*rho)),  Vp/Vs = sqrt(3)

한계: 중심력 본드만 쓰므로 Cauchy 관계에 의해 nu 는 0.25 로 고정된다.
      (0.20~0.30 범위 암반에는 실용적으로 충분)

구현 노트
---------
격자가 규칙적이므로 본드를 '인덱스 배열'이 아니라 **배열 슬라이스 쌍**으로
표현한다. 오프셋 (di,dj,dk) 인 모든 본드는 하나의 슬라이스 연산으로 처리되어
fancy indexing / bincount 없이 계산되고, 3~5배 빠르다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .rock import Rock

# (di, dj, dk) 오프셋 — 중복 없이 각 본드를 한 번만 생성
_OFFSETS_1ST = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
_OFFSETS_2ND = [(1, 1, 0), (1, -1, 0), (1, 0, 1), (1, 0, -1), (0, 1, 1), (0, 1, -1)]


def _slice_pair(shape: tuple[int, int, int], off: tuple[int, int, int]):
    """오프셋 off 로 연결된 입자쌍을 가리키는 슬라이스 (A쪽, B쪽)."""
    a, b = [], []
    for n, d in zip(shape, off):
        if d >= 0:
            a.append(slice(0, n - d)); b.append(slice(d, n))
        else:
            a.append(slice(-d, n)); b.append(slice(0, n + d))
    return tuple(a), tuple(b)


@dataclass
class BondGroup:
    """동일한 방향/길이를 갖는 본드 묶음 = 격자 배열의 슬라이스 쌍."""

    offset: tuple[int, int, int]
    sa: tuple                  # A쪽 슬라이스 (i,j,k)
    sb: tuple                  # B쪽 슬라이스
    normal: np.ndarray         # 단위방향벡터 (3,)
    length: float              # 초기 본드 길이 [m]
    stiffness: float           # 본드 강성 [N/m]
    shape: tuple[int, int, int] = ()          # 본드 격자 형상
    axes: tuple = field(default=(), repr=False)   # normal 의 비영 성분
    active: np.ndarray = field(default=None, repr=False)     # 미파괴 여부
    breakable: np.ndarray = field(default=None, repr=False)  # 파괴 허용 여부

    def __post_init__(self) -> None:
        self.axes = tuple(int(c) for c in np.flatnonzero(self.normal))
        if self.active is None:
            self.active = np.ones(self.shape, dtype=np.float64)   # 1.0 / 0.0
        if self.breakable is None:
            self.breakable = np.ones(self.shape, dtype=bool)

    def __len__(self) -> int:
        return int(np.prod(self.shape))


class Lattice:
    """정육면체 영역을 채우는 3D 입자 격자.

    좌표계: z = 0 이 지표(자유면), z < 0 이 암반 내부.
    경계조건: 상단(z=0) 자유면, 나머지 5면은 점성 흡수경계(Lysmer-Kuhlemeyer).
    """

    def __init__(
        self,
        rock: Rock,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        depth: float,
        spacing: float,
    ) -> None:
        self.rock = rock
        self.d = float(spacing)
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        self.depth = float(depth)

        self.nx = max(3, int(round((self.x1 - self.x0) / self.d)) + 1)
        self.ny = max(3, int(round((self.y1 - self.y0) / self.d)) + 1)
        self.nz = max(3, int(round(self.depth / self.d)) + 1)
        self.shape = (self.nx, self.ny, self.nz)
        self.n = self.nx * self.ny * self.nz

        # 본드 강성 및 입자 질량
        self.k = 0.4 * rock.young * self.d
        self.m = rock.density * self.d ** 3

        self.protected = np.zeros(self.shape, dtype=bool)
        self._build_positions()
        self._build_bonds()
        self._build_boundaries()

    # ---- 격자 생성 -------------------------------------------------------
    def _build_positions(self) -> None:
        self.xs = self.x0 + np.arange(self.nx) * self.d
        self.ys = self.y0 + np.arange(self.ny) * self.d
        self.zs = -self.depth + np.arange(self.nz) * self.d   # zs[-1] = 0 (지표)
        X, Y, Z = np.meshgrid(self.xs, self.ys, self.zs, indexing="ij")
        self.pos = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        self.mass = np.full(self.n, self.m)

    def _build_bonds(self) -> None:
        self.bonds: list[BondGroup] = []
        for offs, nfac in ((_OFFSETS_1ST, 1.0), (_OFFSETS_2ND, np.sqrt(2.0))):
            for off in offs:
                sa, sb = _slice_pair(self.shape, off)
                shp = tuple(s.stop - s.start for s in sa)
                vec = np.array(off, dtype=float)
                self.bonds.append(BondGroup(
                    offset=off, sa=sa, sb=sb, normal=vec / np.linalg.norm(vec),
                    length=self.d * nfac, stiffness=self.k, shape=shp,
                ))

    def _build_boundaries(self) -> None:
        """흡수경계: (슬라이스, 외향법선 축). 상단(z=0)은 자유면이므로 제외."""
        full = slice(None)
        self.boundary = [
            ((0, full, full), 0),              # -x
            ((self.nx - 1, full, full), 0),    # +x
            ((full, 0, full), 1),              # -y
            ((full, self.ny - 1, full), 1),    # +y
            ((full, full, 0), 2),              # -z (하부)
        ]
        idx = np.arange(self.n).reshape(self.shape)
        self.surface_idx = idx[:, :, self.nz - 1].ravel().copy()

    # ---- 탄성코어 --------------------------------------------------------
    def protect(self, idx: np.ndarray) -> None:
        """지정 입자를 '본드 파괴 금지'로 표시.

        등가공동 모델에서 폭원 근방의 비탄성 거동(파쇄·균열)은 이미 압력
        반경감쇠식에 반영되어 있다. 그 영역의 본드까지 파괴시키면 입자가
        모든 구속을 잃고 자유비산해 비물리적 속도가 발생하므로 보호한다.
        """
        flat = self.protected.reshape(-1)
        flat[np.asarray(idx, dtype=np.int64)] = True
        for g in self.bonds:
            g.breakable = ~(self.protected[g.sa] | self.protected[g.sb])

    def cylinder_indices(self, x: float, y: float, z_lo: float, z_hi: float,
                         radius: float) -> np.ndarray:
        """연직 원기둥 안에 드는 입자의 평탄 인덱스."""
        r = np.hypot(self.pos[:, 0] - x, self.pos[:, 1] - y)
        return np.flatnonzero((r <= radius) & (self.pos[:, 2] >= z_lo) & (self.pos[:, 2] <= z_hi))

    # ---- 물성/수치 파라미터 ---------------------------------------------
    @property
    def n_bonds(self) -> int:
        return sum(len(g) for g in self.bonds)

    @property
    def critical_dt(self) -> float:
        """무감쇠 임계 시간간격 dt_c = d / (sqrt(2) * Vp).

        격자 최대 고유진동수 omega_max ~ 2*sqrt(6k/m) 로부터 dt_c = 2/omega_max.
        """
        return self.d / (np.sqrt(2.0) * self.rock.p_velocity)

    @property
    def omega_max(self) -> float:
        return 2.0 / self.critical_dt

    @property
    def max_frequency(self) -> float:
        """격자가 해상 가능한 최대 주파수 [Hz] — 파장당 10요소(S파) 기준."""
        return self.rock.s_velocity / (10.0 * self.d)

    def nearest(self, points: np.ndarray) -> np.ndarray:
        """임의 좌표에 가장 가까운 입자의 평탄 인덱스."""
        pts = np.atleast_2d(np.asarray(points, dtype=float))
        i = np.clip(np.round((pts[:, 0] - self.x0) / self.d), 0, self.nx - 1).astype(int)
        j = np.clip(np.round((pts[:, 1] - self.y0) / self.d), 0, self.ny - 1).astype(int)
        k = np.clip(np.round((pts[:, 2] + self.depth) / self.d), 0, self.nz - 1).astype(int)
        return (i * self.ny + j) * self.nz + k

    def memory_mb(self) -> float:
        return (self.n * 3 * 8 * 3 + self.n_bonds * 9) / 1e6

    def summary(self) -> str:
        return (
            f"[DEM 격자] {self.nx} x {self.ny} x {self.nz} = {self.n:,} 입자, "
            f"{self.n_bonds:,} 본드\n"
            f"  영역 x[{self.x0:.0f}, {self.x1:.0f}]  y[{self.y0:.0f}, {self.y1:.0f}]  "
            f"z[-{self.depth:.0f}, 0] m,  입자간격 d = {self.d:.2f} m\n"
            f"  본드강성 k = {self.k / 1e9:.2f} GN/m,  입자질량 = {self.m:,.0f} kg\n"
            f"  임계 dt = {self.critical_dt * 1e6:.1f} us,  "
            f"해상 최대주파수 ≈ {self.max_frequency:.0f} Hz,  메모리 ≈ {self.memory_mb():.0f} MB"
        )
