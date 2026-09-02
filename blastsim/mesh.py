"""직육면체 암반의 3D 사면체(비정렬) 메쉬 생성 — 원통형 천공홀 포함.

목적
----
FDM(fdm.py) 은 정렬 격자, DEM(lattice.py/frag.py) 은 입자를 쓰므로 천공홀처럼
'도메인 크기의 1/300' 인 형상을 그대로 담을 수 없다. 이 모듈은 그런 국부 형상을
기하학적으로 재현해야 할 때(공벽 압력 재하면 추출, 유한요소 해석기 연계,
파쇄 초기 균열면 정의) 쓰는 **비정렬 사면체 메쉬** 생성기다.

생성 전략
---------
1. **크기장(sizing field)** h(x) 를 천공홀 표면까지의 부호거리 d(x) 로 정의한다.

       h(x) = min( h_far,  h_near + growth * max(d(x), 0) )

   d=0(공벽)에서 h_near, 멀어질수록 growth 기울기로 성장해 h_far 로 포화한다.
   인접 요소 크기비는 대략 (1 + growth) 이므로 growth 0.3~0.6 이 표준적이다.

2. **레벨 격자 배치.** h 를 h_near·2^k 로 양자화해 레벨을 나누고, 각 레벨이
   지배하는 껍질(shell) 영역에만 간격 h_k 의 격자를 깐다. 격자점은 셀 크기의
   ±30% 로 난수 요동(jitter)을 주므로 결과 사면체는 규칙성이 없는 **불규칙
   메쉬**가 된다. 레벨을 세밀→성긴 순으로 삽입하면서 이미 채택된 점에서
   fill·h 이내인 후보를 KD-트리로 걸러 blue-noise 에 가까운 분포를 만든다.
   (전 영역에 h_near 격자를 깔면 20m 정육면체 × 20mm 간격 = 10^9 점이 되어
    불가능하다. 레벨 분할이 이 문제를 푸는 핵심이다.)

3. **경계 점군.** 8개 꼭짓점 → 12개 모서리 → 6개 면 → 내부 순으로 삽입한다.
   면 위 점은 면 안에서만(모서리 위 점은 모서리 방향으로만) 요동시키므로
   직육면체의 평면성이 정확히 유지되고, 볼록包(convex hull) 이 정확히 원래
   직육면체가 된다.

4. **천공홀.** 공벽에 원주 링(축방향 h_near 간격, 링마다 반칸씩 엇갈림)과
   축선 점을 먼저(보호 점군으로) 깔아 원통면을 점군으로 표현한다.

5. **Delaunay 사면체화.** 도메인이 볼록하므로 3D Delaunay(Qhull) 의 결과가
   그대로 직육면체를 빈틈없이 채운다 — 별도의 경계 복원이 필요 없다.
   면 위 점들은 동일 평면상에 있어 퇴화(degenerate)를 일으키므로 Qhull 의
   'QJ'(joggle, 상대오차 ~1e-11 = 20m 도메인에서 0.2nm) 로 제거한다.

6. **영역 분류.** 사면체 무게중심이 원통 내부면 REGION_HOLE, 아니면 REGION_ROCK.
   두 영역 사이의 삼각형면이 곧 **공벽(재하면)** 이다.

검증 가능한 불변량
-----------------
  * 전체 사면체 부피 합 = 직육면체 부피 (볼록包 충전)
  * 천공홀 영역 부피 ≈ pi R^2 L
  * 공벽 면적 ≈ pi D L + pi R^2  (내접 다각형이므로 원주 분할수 n 에서
    (n/pi)·sin(pi/n) 배만큼 과소평가된다 — n=12 이면 -1.1%)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import Delaunay, cKDTree

REGION_ROCK = 0
REGION_HOLE = 1

# 사면체의 4개 면 (마주보는 절점 번호 순서)
_FACES = np.array([[1, 2, 3], [0, 3, 2], [0, 1, 3], [0, 2, 1]])
# 6개 모서리와, 그 모서리를 공유하는 두 면
_EDGE_FACES = [(2, 3), (1, 3), (1, 2), (0, 3), (0, 2), (0, 1)]


# ---------------------------------------------------------------------------
# 기하 정의
# ---------------------------------------------------------------------------
@dataclass
class BoxDomain:
    """해석 영역 직육면체. 좌표계는 lattice.py 와 동일 (z=0 이 지표)."""

    x_range: tuple[float, float] = (-10.0, 10.0)
    y_range: tuple[float, float] = (-10.0, 10.0)
    z_range: tuple[float, float] = (-20.0, 0.0)

    @classmethod
    def from_size(cls, width: float, length: float, depth: float) -> "BoxDomain":
        """폭(x) · 세로(y) · 깊이(z) 로 생성. 상면이 z=0, 평면 중심이 원점."""
        return cls((-width / 2, width / 2), (-length / 2, length / 2), (-depth, 0.0))

    @property
    def lo(self) -> np.ndarray:
        return np.array([self.x_range[0], self.y_range[0], self.z_range[0]])

    @property
    def hi(self) -> np.ndarray:
        return np.array([self.x_range[1], self.y_range[1], self.z_range[1]])

    @property
    def size(self) -> np.ndarray:
        return self.hi - self.lo

    @property
    def volume(self) -> float:
        return float(np.prod(self.size))


@dataclass
class Borehole:
    """원통형 천공홀. collar 에서 axis 방향으로 length 만큼 뚫린 원통."""

    collar: tuple[float, float, float] = (0.0, 0.0, 0.0)
    axis: tuple[float, float, float] = (0.0, 0.0, -1.0)
    length: float = 12.0
    diameter: float = 0.075

    @property
    def radius(self) -> float:
        return 0.5 * self.diameter

    @property
    def unit_axis(self) -> np.ndarray:
        u = np.asarray(self.axis, dtype=float)
        n = np.linalg.norm(u)
        if n == 0.0:
            raise ValueError("천공 방향 axis 가 영벡터입니다")
        return u / n

    @property
    def toe(self) -> np.ndarray:
        return np.asarray(self.collar, float) + self.unit_axis * self.length

    @property
    def volume(self) -> float:
        return math.pi * self.radius ** 2 * self.length

    @property
    def wall_area(self) -> float:
        """공벽(측면) + 공저(바닥) 면적 [m^2]."""
        return math.pi * self.diameter * self.length + math.pi * self.radius ** 2

    def distance(self, p: np.ndarray) -> np.ndarray:
        """원통(마개 포함) 까지의 부호거리 — 내부가 음수."""
        d = np.atleast_2d(p) - np.asarray(self.collar, float)
        u = self.unit_axis
        t = d @ u                                  # 축방향 좌표
        rho = np.linalg.norm(d - t[:, None] * u, axis=1)
        a = rho - self.radius                      # 반경방향 초과
        b = np.abs(t - self.length / 2) - self.length / 2   # 축방향 초과
        outside = np.hypot(np.maximum(a, 0.0), np.maximum(b, 0.0))
        inside = np.minimum(np.maximum(a, b), 0.0)
        return outside + inside


@dataclass
class MeshConfig:
    """메쉬 생성 파라미터.

    h_near  : 공벽에서의 목표 요소 크기 [m]. 기본값은 원주를 n_theta 등분한
              간격에 맞춘다 (None 이면 자동).
    h_far   : 원거리 요소 크기 [m]
    growth  : 크기장 기울기 dh/dd — 인접 요소 크기비 ≈ 1+growth
    n_theta : 공벽 원주 분할수
    fill    : 점 채택 최소거리 계수 (accept if dist > fill*h)
    jitter  : 격자점 요동 크기 (셀 간격 대비)
    seed    : 난수 시드 — 동일 시드는 동일 메쉬를 재현한다
    sliver_tol : 퇴화 사면체 제거 기준 V < sliver_tol * l_max^3
                 (정사면체는 V = 0.1179 l^3 이므로 1e-9 는 8자릿수 아래)
    """

    h_near: float | None = None
    h_far: float = 1.0
    growth: float = 0.5
    n_theta: int = 12
    fill: float = 0.7
    jitter: float = 0.3
    seed: int = 0
    sliver_tol: float = 1e-9


#: 사전 정의 프리셋 — CLI/GUI 의 '해석 정밀도' 와 같은 감각으로 쓴다.
MESH_PRESETS: dict[str, MeshConfig] = {
    "빠름": MeshConfig(h_far=2.0, growth=1.0, n_theta=8),
    "보통": MeshConfig(h_far=1.0, growth=0.6, n_theta=12),
    "정밀": MeshConfig(h_far=0.6, growth=0.35, n_theta=16),
}


# ---------------------------------------------------------------------------
# 메쉬 자료구조
# ---------------------------------------------------------------------------
@dataclass
class TetMesh:
    """사면체 메쉬. points (N,3), tets (M,4), region (M,)."""

    points: np.ndarray
    tets: np.ndarray
    region: np.ndarray
    domain: BoxDomain
    hole: Borehole
    config: MeshConfig = field(default_factory=MeshConfig)
    n_dropped: int = 0          # 생성 중 제거한 퇴화(영부피) 사면체 수

    # ---- 기본 량 --------------------------------------------------------
    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_tets(self) -> int:
        return len(self.tets)

    @property
    def corners(self) -> np.ndarray:
        """(M,4,3) 사면체 절점 좌표."""
        return self.points[self.tets]

    def volumes(self) -> np.ndarray:
        """사면체 부피 [m^3] (부호 없음)."""
        c = self.corners
        m = c[:, 1:] - c[:, :1]
        return np.abs(np.linalg.det(m)) / 6.0

    def centroids(self) -> np.ndarray:
        return self.corners.mean(axis=1)

    def edge_lengths(self) -> np.ndarray:
        """(M,6) 6개 모서리 길이."""
        c = self.corners
        i, j = np.triu_indices(4, k=1)
        return np.linalg.norm(c[:, i] - c[:, j], axis=2)

    # ---- 품질 ------------------------------------------------------------
    def quality(self) -> np.ndarray:
        """평균비(mean-ratio) 품질 q = 12·(3V)^(2/3) / sum(l^2).

        정사면체에서 q=1, 퇴화 사면체에서 q→0 이다. 실용 기준은 q>0.1
        (사용 가능), q>0.3 (양호).
        """
        v = self.volumes()
        l2 = (self.edge_lengths() ** 2).sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            q = 12.0 * np.cbrt((3.0 * v) ** 2) / l2
        return np.nan_to_num(q, nan=0.0, posinf=0.0)

    def dihedral_angles(self) -> np.ndarray:
        """(M,6) 이면각 [deg]. 정사면체는 70.53°, 슬라이버는 0/180 에 근접."""
        c = self.corners
        normals = np.empty((len(c), 4, 3))
        for f in range(4):
            a, b, d = (c[:, _FACES[f, k]] for k in range(3))
            n = np.cross(b - a, d - a)
            # 마주보는 절점 반대쪽(외향)으로 정렬
            sign = np.sign(np.einsum("ij,ij->i", n, a - c[:, f]))
            normals[:, f] = n * np.where(sign == 0, 1.0, sign)[:, None]
        norm = np.linalg.norm(normals, axis=2, keepdims=True)
        normals /= np.where(norm == 0, 1.0, norm)

        ang = np.empty((len(c), 6))
        for e, (f1, f2) in enumerate(_EDGE_FACES):
            dot = np.einsum("ij,ij->i", normals[:, f1], normals[:, f2])
            ang[:, e] = np.degrees(np.arccos(np.clip(-dot, -1.0, 1.0)))
        return ang

    # ---- 면(facet) 추출 ---------------------------------------------------
    def _facet_table(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """모든 사면체 면을 정렬해 (고유면, 소속 사면체 인덱스, 등장횟수) 반환."""
        faces = self.tets[:, _FACES].reshape(-1, 3)
        faces = np.sort(faces, axis=1)
        uniq, inv, cnt = np.unique(faces, axis=0, return_inverse=True,
                                   return_counts=True)
        owner = np.repeat(np.arange(self.n_tets), 4)
        return uniq, inv, cnt, owner

    def boundary_facets(self, region: int | None = None) -> np.ndarray:
        """영역(또는 전체)의 외부 경계 삼각형 (K,3)."""
        sel = slice(None) if region is None else (self.region == region)
        tets = self.tets[sel]
        faces = np.sort(tets[:, _FACES].reshape(-1, 3), axis=1)
        uniq, cnt = np.unique(faces, axis=0, return_counts=True)
        return uniq[cnt == 1]

    def hole_wall_facets(self) -> np.ndarray:
        """천공홀 영역과 암반 영역이 맞닿는 삼각형 = 공벽 재하면 (K,3)."""
        uniq, inv, cnt, owner = self._facet_table()
        reg = self.region[owner]
        # 내부면(2회 등장) 중 양쪽 영역이 다른 것
        n_uniq = len(uniq)
        has_rock = np.zeros(n_uniq, dtype=bool)
        has_hole = np.zeros(n_uniq, dtype=bool)
        np.logical_or.at(has_rock, inv, reg == REGION_ROCK)
        np.logical_or.at(has_hole, inv, reg == REGION_HOLE)
        return uniq[(cnt == 2) & has_rock & has_hole]

    def cut_polygons(self, axis: int = 1, value: float = 0.0
                     ) -> tuple[list[np.ndarray], np.ndarray]:
        """평면(axis=value)으로 자른 정확한 단면 다각형과 각 다각형의 영역.

        사면체를 평면으로 자르면 절점 부호 분포에 따라 삼각형(1:3 분할) 또는
        사각형(2:2 분할)이 나온다. 두 경우를 나눠 벡터화 계산한 뒤 사각형만
        무게중심 기준 각도로 정렬한다(단면은 항상 볼록).
        """
        e = np.array([(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)])
        c = self.corners
        s = c[:, :, axis] - value
        pos = s > 0
        n_pos = pos.sum(axis=1)
        plane = [i for i in range(3) if i != axis]

        polys: list[np.ndarray] = []
        regions: list[np.ndarray] = []
        for n_cross, sel in ((3, np.isin(n_pos, (1, 3))), (4, n_pos == 2)):
            idx = np.flatnonzero(sel)
            if len(idx) == 0:
                continue
            si, sj = s[idx][:, e[:, 0]], s[idx][:, e[:, 1]]
            hit = np.flatnonzero(((si > 0) != (sj > 0)).ravel())
            ei = hit % 6
            row = np.repeat(np.arange(len(idx)), n_cross)
            a, bb = e[ei, 0], e[ei, 1]
            sa, sb = s[idx][row, a], s[idx][row, bb]
            t = sa / (sa - sb)
            pa, pb = c[idx][row, a], c[idx][row, bb]
            pts = (pa + t[:, None] * (pb - pa))[:, plane].reshape(-1, n_cross, 2)
            if n_cross == 4:                       # 사각형은 각도 정렬 필요
                d = pts - pts.mean(axis=1, keepdims=True)
                order = np.argsort(np.arctan2(d[:, :, 1], d[:, :, 0]), axis=1)
                pts = np.take_along_axis(pts, order[:, :, None], axis=1)
            polys.extend(pts)
            regions.append(self.region[idx])
        return polys, (np.concatenate(regions) if regions else np.zeros(0, np.int8))

    def facet_areas(self, facets: np.ndarray) -> np.ndarray:
        p = self.points[facets]
        return 0.5 * np.linalg.norm(
            np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)

    # ---- 부분 메쉬 --------------------------------------------------------
    def subset(self, region: int) -> "TetMesh":
        """해당 영역의 사면체만 남긴 메쉬 (절점 재번호)."""
        keep = self.region == region
        tets = self.tets[keep]
        used = np.unique(tets)
        remap = np.full(self.n_points, -1, dtype=np.int64)
        remap[used] = np.arange(len(used))
        return TetMesh(self.points[used], remap[tets], self.region[keep],
                       self.domain, self.hole, self.config)

    # ---- 내보내기 ---------------------------------------------------------
    def write_vtk(self, path: str) -> str:
        """레거시 VTK(ASCII) — ParaView/VisIt 에서 바로 열린다."""
        n, m = self.n_points, self.n_tets
        with open(path, "w", encoding="ascii") as f:
            f.write("# vtk DataFile Version 3.0\n")
            f.write("blastsim tetrahedral mesh\nASCII\nDATASET UNSTRUCTURED_GRID\n")
            f.write(f"POINTS {n} double\n")
            np.savetxt(f, self.points, fmt="%.9g")
            f.write(f"\nCELLS {m} {5 * m}\n")
            np.savetxt(f, np.hstack([np.full((m, 1), 4), self.tets]), fmt="%d")
            f.write(f"\nCELL_TYPES {m}\n")
            np.savetxt(f, np.full(m, 10), fmt="%d")
            f.write(f"\nCELL_DATA {m}\nSCALARS region int 1\nLOOKUP_TABLE default\n")
            np.savetxt(f, self.region, fmt="%d")
            f.write("SCALARS quality double 1\nLOOKUP_TABLE default\n")
            np.savetxt(f, self.quality(), fmt="%.5f")
        return path

    def write_msh(self, path: str) -> str:
        """Gmsh 2.2 (ASCII) — 물리그룹 1=암반, 2=천공홀."""
        with open(path, "w", encoding="ascii") as f:
            f.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")
            f.write("$PhysicalNames\n2\n3 1 \"rock\"\n3 2 \"borehole\"\n"
                    "$EndPhysicalNames\n")
            f.write(f"$Nodes\n{self.n_points}\n")
            idx = np.arange(1, self.n_points + 1)[:, None]
            np.savetxt(f, np.hstack([idx, self.points]), fmt="%d %.9g %.9g %.9g")
            f.write(f"$EndNodes\n$Elements\n{self.n_tets}\n")
            tag = np.where(self.region == REGION_HOLE, 2, 1)[:, None]
            eid = np.arange(1, self.n_tets + 1)[:, None]
            rows = np.hstack([eid, np.full_like(eid, 4), np.full_like(eid, 2),
                              tag, tag, self.tets + 1])
            np.savetxt(f, rows, fmt="%d")
            f.write("$EndElements\n")
        return path

    # ---- 요약 -------------------------------------------------------------
    def summary(self) -> str:
        v = self.volumes()
        q = self.quality()
        ang = self.dihedral_angles()
        wall = self.hole_wall_facets()
        v_hole = float(v[self.region == REGION_HOLE].sum())
        a_wall = float(self.facet_areas(wall).sum())
        sz = self.domain.size
        lines = [
            "사면체 메쉬 요약",
            "─" * 58,
            f"  영역        : {sz[0]:g} x {sz[1]:g} x {sz[2]:g} m "
            f"(체적 {self.domain.volume:,.0f} m³)",
            f"  천공홀      : Ø{self.hole.diameter * 1000:g} mm x "
            f"{self.hole.length:g} m",
            f"  절점 / 요소 : {self.n_points:,} / {self.n_tets:,} "
            f"(퇴화 {self.n_dropped:,}개 제거)",
            f"  요소 크기   : {self.edge_lengths().min():.4f} ~ "
            f"{self.edge_lengths().max():.3f} m",
            f"  체적 합     : {v.sum():,.4f} m³ "
            f"(오차 {abs(v.sum() / self.domain.volume - 1) * 100:.2e} %)",
            f"  천공홀 체적 : {v_hole * 1e6:,.1f} cm³ "
            f"(이론 {self.hole.volume * 1e6:,.1f} cm³, "
            f"{v_hole / self.hole.volume * 100:.1f} %)",
            f"  공벽 면적   : {a_wall:.4f} m² "
            f"(이론 {self.hole.wall_area:.4f} m², "
            f"{a_wall / self.hole.wall_area * 100:.1f} %) / 삼각형 {len(wall):,}개",
            f"  품질 q      : 평균 {q.mean():.3f}, 중앙 {np.median(q):.3f}, "
            f"1%tile {np.percentile(q, 1):.3f}, 최소 {q.min():.4f} "
            f"(q>0.1: {(q > 0.1).mean() * 100:.2f} %)",
            f"  이면각      : 최소 {ang.min():.2f}°, 최대 {ang.max():.2f}° "
            f"(정사면체 70.53°)",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 점군 생성
# ---------------------------------------------------------------------------
class _PointBuilder:
    """크기장에 맞춰 레벨별로 점을 깔고 KD-트리로 중복을 거르는 누산기."""

    def __init__(self, domain: BoxDomain, hole: Borehole, cfg: MeshConfig) -> None:
        self.domain, self.hole, self.cfg = domain, hole, cfg
        self.h_near = cfg.h_near or max(
            1e-4, math.pi * hole.diameter / max(4, cfg.n_theta))
        self.h_far = max(self.h_near, cfg.h_far)
        self.rng = np.random.default_rng(cfg.seed)
        self._acc: list[np.ndarray] = []

        sizes = []
        h = self.h_near
        while h < self.h_far * (1 - 1e-9):
            sizes.append(h)
            h *= 2.0
        sizes.append(self.h_far)
        self.sizes = np.array(sizes)

    # -- 크기장 ------------------------------------------------------------
    def hsize(self, p: np.ndarray) -> np.ndarray:
        d = np.maximum(self.hole.distance(p), 0.0)
        return np.minimum(self.h_far, self.h_near + self.cfg.growth * d)

    def level(self, p: np.ndarray) -> np.ndarray:
        i = np.searchsorted(self.sizes, self.hsize(p), side="right") - 1
        return np.clip(i, 0, len(self.sizes) - 1)

    def band_extent(self, lv: int) -> float:
        """레벨 lv 가 지배하는 영역의 공벽 기준 최대 거리."""
        if lv >= len(self.sizes) - 1:
            return float(np.max(self.domain.size))
        return (self.sizes[lv + 1] - self.h_near) / max(self.cfg.growth, 1e-9)

    # -- 삽입 --------------------------------------------------------------
    def add(self, pts: np.ndarray, spacing: float, protect: bool = False) -> int:
        if len(pts) == 0:
            return 0
        if self._acc and not protect:
            tree = cKDTree(np.vstack(self._acc))
            pts = pts[tree.query(pts, k=1)[0] > self.cfg.fill * spacing]
        if len(pts):
            self._acc.append(np.ascontiguousarray(pts, dtype=float))
        return len(pts)

    @property
    def points(self) -> np.ndarray:
        return np.vstack(self._acc) if self._acc else np.zeros((0, 3))

    # -- 격자 도우미 --------------------------------------------------------
    def _cells(self, lo: float, hi: float, h: float) -> np.ndarray:
        n = max(int(math.ceil((hi - lo) / h)), 1)
        return lo + (np.arange(n) + 0.5) * (hi - lo) / n

    def _jitter(self, pts: np.ndarray, h: float, axes: tuple[int, ...]) -> np.ndarray:
        out = pts.copy()
        for a in axes:
            out[:, a] += self.rng.uniform(-self.cfg.jitter * h,
                                          self.cfg.jitter * h, len(pts))
        return out

    def _clip_box(self, pts: np.ndarray, margin: float = 0.0) -> np.ndarray:
        lo, hi = self.domain.lo + margin, self.domain.hi - margin
        return pts[np.all(pts >= lo, axis=1) & np.all(pts <= hi, axis=1)]

    def _hole_bbox(self, ext: float) -> tuple[np.ndarray, np.ndarray]:
        ends = np.vstack([np.asarray(self.hole.collar, float), self.hole.toe])
        r = self.hole.radius + ext
        lo = np.maximum(ends.min(axis=0) - r, self.domain.lo)
        hi = np.minimum(ends.max(axis=0) + r, self.domain.hi)
        return lo, hi


def _hole_points(hole: Borehole, h: float, n_theta: int,
                 rng: np.random.Generator) -> np.ndarray:
    """공벽 원주 링 + 축선 점. 링은 한 칸씩 엇갈려 규칙성을 없앤다."""
    u = hole.unit_axis
    ref = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(u, ref)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)

    n_ax = max(2, int(round(hole.length / h)) + 1)
    t = np.linspace(0.0, hole.length, n_ax)
    collar = np.asarray(hole.collar, float)
    axis_pts = collar + t[:, None] * u

    th0 = np.arange(n_theta) * (2 * math.pi / n_theta)
    rings = []
    for k, tk in enumerate(t):
        th = th0 + (k % 2) * (math.pi / n_theta)
        c = collar + tk * u
        rings.append(c + hole.radius * (np.cos(th)[:, None] * e1
                                        + np.sin(th)[:, None] * e2))
    return np.vstack([axis_pts, np.vstack(rings)])


# ---------------------------------------------------------------------------
# 메쉬 생성
# ---------------------------------------------------------------------------
def build_points(domain: BoxDomain, hole: Borehole, cfg: MeshConfig) -> np.ndarray:
    """크기장에 맞춘 비정렬 점군 생성 (꼭짓점 → 공벽 → 모서리 → 면 → 내부)."""
    b = _PointBuilder(domain, hole, cfg)
    lo, hi = domain.lo, domain.hi

    # 1) 8 꼭짓점 — 볼록包가 정확히 직육면체가 되도록 반드시 포함
    grid = np.array(np.meshgrid(*[[lo[i], hi[i]] for i in range(3)],
                                indexing="ij")).reshape(3, -1).T
    b.add(grid, 0.0, protect=True)

    # 2) 공벽 링 + 축선 (보호 점군)
    b.add(b._clip_box(_hole_points(hole, b.h_near, cfg.n_theta, b.rng)),
          0.0, protect=True)

    # 3) 12 모서리 — 모서리 방향으로만 요동
    for lv, h in enumerate(b.sizes):
        for a in range(3):
            o1, o2 = [i for i in range(3) if i != a]
            for v1 in (lo[o1], hi[o1]):
                for v2 in (lo[o2], hi[o2]):
                    s = b._cells(lo[a], hi[a], h)
                    p = np.empty((len(s), 3))
                    p[:, a], p[:, o1], p[:, o2] = s, v1, v2
                    p = b._jitter(p, h, (a,))
                    p = b._clip_box(p)
                    b.add(p[b.level(p) == lv], h)

    # 4) 6 면 — 면 안에서만 요동 (평면성 유지)
    for lv, h in enumerate(b.sizes):
        ext = b.band_extent(lv)
        for a in range(3):
            o1, o2 = [i for i in range(3) if i != a]
            for v in (lo[a], hi[a]):
                bl, bh = b._hole_bbox(ext)
                s1 = b._cells(max(lo[o1], bl[o1]), min(hi[o1], bh[o1]), h)
                s2 = b._cells(max(lo[o2], bl[o2]), min(hi[o2], bh[o2]), h)
                g1, g2 = np.meshgrid(s1, s2, indexing="ij")
                p = np.empty((g1.size, 3))
                p[:, a], p[:, o1], p[:, o2] = v, g1.ravel(), g2.ravel()
                p = b._jitter(p, h, (o1, o2))
                p = b._clip_box(p)
                b.add(p[b.level(p) == lv], h)

    # 5) 내부 — 경계에서 0.35h 이상 떨어뜨려 슬라이버를 억제
    for lv, h in enumerate(b.sizes):
        bl, bh = b._hole_bbox(b.band_extent(lv))
        axes = [b._cells(bl[i], bh[i], h) for i in range(3)]
        g = np.meshgrid(*axes, indexing="ij")
        p = np.stack([x.ravel() for x in g], axis=1)
        p = b._jitter(p, h, (0, 1, 2))
        p = b._clip_box(p, margin=0.35 * h)
        b.add(p[b.level(p) == lv], h)

    return b.points


def drop_degenerate(points: np.ndarray, tets: np.ndarray,
                    tol: float = 1e-9) -> tuple[np.ndarray, int]:
    """영부피 사면체 제거.

    직육면체 면 위 점들은 정확히 동일 평면에 있어 Delaunay 가 그 평면 안에
    누운 '납작한' 사면체를 만든다. 부피가 0 이므로 제거해도 영역 충전과 체적
    합은 그대로이고, 대신 요소 품질 지표(이면각·q)가 의미를 되찾는다.
    판정은 크기에 무관하도록 V < tol * l_max^3 으로 한다.
    """
    c = points[tets]
    v = np.abs(np.linalg.det(c[:, 1:] - c[:, :1])) / 6.0
    i, j = np.triu_indices(4, k=1)
    lmax = np.linalg.norm(c[:, i] - c[:, j], axis=2).max(axis=1)
    keep = v > tol * lmax ** 3
    return np.ascontiguousarray(tets[keep]), int((~keep).sum())


def build_tet_mesh(domain: BoxDomain | None = None,
                   hole: Borehole | None = None,
                   config: MeshConfig | str = "보통") -> TetMesh:
    """직육면체 + 원통형 천공홀의 사면체 메쉬를 생성한다.

    Parameters
    ----------
    domain : 해석 영역 (기본 20 x 20 x 20 m)
    hole   : 천공홀 (기본 Ø75 mm x 12 m, 상면 중앙에서 연직)
    config : MeshConfig 또는 MESH_PRESETS 의 키 ("빠름"/"보통"/"정밀")
    """
    domain = domain or BoxDomain.from_size(20.0, 20.0, 20.0)
    hole = hole or Borehole()
    if isinstance(config, str):
        if config not in MESH_PRESETS:
            raise KeyError(f"알 수 없는 프리셋: {config} — {list(MESH_PRESETS)}")
        config = MESH_PRESETS[config]

    pts = build_points(domain, hole, config)
    # QJ: 면 위 공면점(coplanar) 퇴화를 미세 요동으로 제거. 요동은 상대 1e-11
    # 수준이라 좌표 자체는 원본 그대로 쓰고 연결정보만 얻는다.
    tri = Delaunay(pts, qhull_options="QJ Pp")
    tets = np.ascontiguousarray(tri.simplices, dtype=np.int64)
    tets, n_dropped = drop_degenerate(pts, tets, config.sliver_tol)

    mesh = TetMesh(pts, tets, np.zeros(len(tets), dtype=np.int8), domain, hole,
                   config, n_dropped=n_dropped)
    inside = hole.distance(mesh.centroids()) < 0.0
    mesh.region = np.where(inside, REGION_HOLE, REGION_ROCK).astype(np.int8)
    return mesh
