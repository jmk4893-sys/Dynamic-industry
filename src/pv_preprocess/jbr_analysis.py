"""JBR-201 수치 해석 — 곱해 보는 것에서 **푸는** 것으로.

`jbr_fabrication` 의 검산은 값을 곱해 본다. 보 하나를 양단 지지로 놓고 48EI/L³ 를
쓰는 식이다. 그것으로 잡히는 소견도 있었지만(브리지 처짐·승강 실린더), 그 방식이
구조적으로 못 보는 것이 셋 있다.

  ① **기둥이 같이 흔들리는 것** — 브리지를 단순보로 보면 지점이 안 움직인다고 놓는
     것이다. 실제로는 X 캐리지가 기둥 위에 있고, 브리지가 설 때 프레임 전체가
     흔들린다(sway). 1 차 모드가 보 굽힘이 아니라 프레임 흔들림일 수 있다.
  ② **하중 이력** — 대수 검산은 최악 한 점만 본다. 피로는 최악값이 아니라 **이력**이
     정한다. 도면집이 「FEA 피로 케이스 없음」을 미결로 적어 둔 자리다.
  ③ **시간** — 공압 실린더가 그 행정을 그 시간에 내는가는 P·A 로 안 나온다. 챔버가
     차는 데 시간이 걸리고, 그 시간이 순차 배분 4.0 s 를 깨는지가 관문이다.

그래서 여기서는 푼다. 강성행렬을 세워 Gauss 소거로 풀고, 일반화 고유치를 Cholesky
+ Jacobi 로 뽑고, 하중 이력을 ASTM E1049 레인플로로 세어 Miner 로 누적하고, 실린더
충전을 RK4 로 적분한다.

**표준 라이브러리만 쓴다** — 저장소 규약이고, 해석기가 numpy 유무로 갈리면 CI 에서
증명할 수 없다. 대신 모든 풀이에 닫힌 해 대조를 붙여 시험이 그 자리를 지킨다.

값은 전부 `jbr_fabrication` 과 통합 설계도의 운동식에서 온다. 여기서 새로 정한 치수는
없다 — 모르는 것(정격 작업 박리력)은 인자로 받아 밴드로 답한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import campaign
from . import catch as _catch          # 쿠션 가정 — 투입 쪽과 한 벌만 둔다
from . import jbr_fabrication as jf

# ── 재료 ────────────────────────────────────────────────────────────────
#: 강재 탄성계수 (MPa). `bridge_mode` 가 쓰는 206,000 과 같은 값이다.
E_STEEL = 206_000.0
#: 강재 밀도 (kg/mm³).
RHO_STEEL = 7.85e-6
#: S355 항복 (MPa).
FY_STEEL = 355.0


# ── 운동식 거울 ─────────────────────────────────────────────────────────
#: 통합 설계도 `wt()` 의 순차 운동식에서 이 해석이 쓰는 값만 옮겨 놓은 것.
#:
#: **원본은 통합 설계도다.** 해석기가 HTML 을 파싱하면 CI 에서 도면 없이 못 돌고,
#: 도면이 해석기를 import 하면 순환이 된다. 그래서 저장소의 다른 거울들과 같은
#: 방식을 쓴다 — 여기 값을 두고, 시험이 원본 파서와 **한 자리씩 대조**한다
#: (`test_the_motion_mirror_matches_the_plant`). 원본이 움직이면 시험이 먼저 깨진다.
SEQUENCE: dict[str, object] = {
    "slot": 7.0,                 # 박스 한 개 칸 (s) — REV.58 에서 4.0 → 7.0
    "slotFrom": 20.0,            # 첫 칸 시작 (s)
    "sinkZ": -1.05,              # 슈트 투하 z (m)
    "shear": (2.5, 4.1),         # 칸 안 박리 구간 (s)
    "openWide": 0.62,            # 칼날 벌린 자리 (m)
    "openShut": 0.26,            # 칼날 문 자리 (m)
    "place": (0.0, 2.0),         # 헤드 Y 이송 (s) — 축 한계를 지키는 길이
    "boxLift": (4.7, 4.9),       # 그리퍼 상승 (s)
    "boxSlide": (4.9, 6.9),      # 슈트까지 이송 (s) — 축 한계를 지키는 길이
    "sinkY": (1.175, 1.075),     # 그리퍼가 놓는 높이 → 호퍼 바닥 (m)
    "discharge": {"highY": 1.075, "restY": 0.155},   # 호퍼 → 수거함 (m)
}


# ── 선형대수 — 표준 라이브러리만 ─────────────────────────────────────────
def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """부분 피벗 Gauss 소거. a 는 파괴되지 않는다 (복사해 쓴다)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError(f"특이 행렬 — {col} 열에서 피벗이 0 이다 (구속이 모자란다)")
        m[col], m[piv] = m[piv], m[col]
        inv = 1.0 / m[col][col]
        for r in range(col + 1, n):
            f = m[r][col] * inv
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / m[r][r]
    return x


def cholesky(a: list[list[float]]) -> list[list[float]]:
    """대칭 양정치 A = L Lᵀ. 질량행렬이 양정치가 아니면 여기서 걸린다."""
    n = len(a)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = a[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 0.0:
                    raise ValueError("질량행렬이 양정치가 아니다 — 질량 없는 자유도가 남았다")
                L[i][j] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    return L


def jacobi_eigen(a: list[list[float]], sweeps: int = 100,
                 tol: float = 1e-12) -> tuple[list[float], list[list[float]]]:
    """대칭 행렬의 고유치·고유벡터 — 순환 Jacobi 회전.

    고유치는 오름차순으로 정렬해 돌려준다. 고유벡터는 열이 아니라 **행**으로 준다
    (v[k] 가 k 번째 모드형상) — 쓰는 쪽이 헷갈리지 않게.
    """
    n = len(a)
    m = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(sweeps):
        off = math.sqrt(sum(m[i][j] ** 2 for i in range(n) for j in range(n) if i != j))
        if off < tol:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(m[p][q]) < 1e-300:
                    continue
                theta = (m[q][q] - m[p][p]) / (2.0 * m[p][q])
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    mkp, mkq = m[k][p], m[k][q]
                    m[k][p] = c * mkp - s * mkq
                    m[k][q] = s * mkp + c * mkq
                for k in range(n):
                    mpk, mqk = m[p][k], m[q][k]
                    m[p][k] = c * mpk - s * mqk
                    m[q][k] = s * mpk + c * mqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    pairs = sorted(range(n), key=lambda i: m[i][i])
    vals = [m[i][i] for i in pairs]
    vecs = [[v[r][i] for r in range(n)] for i in pairs]
    return vals, vecs


# ── 단면 ────────────────────────────────────────────────────────────────
def rhs_section(w_mm: float, h_mm: float, t_mm: float) -> dict[str, float]:
    """각관 단면 — 바깥에서 안쪽을 뺀다. h 가 굽힘 방향(강축) 높이다."""
    wi, hi = w_mm - 2 * t_mm, h_mm - 2 * t_mm
    area = w_mm * h_mm - wi * hi
    inertia = (w_mm * h_mm ** 3 - wi * hi ** 3) / 12.0
    return {"w": w_mm, "h": h_mm, "t": t_mm, "area_mm2": area,
            "inertia_mm4": inertia, "modulus_mm3": inertia / (h_mm / 2.0),
            "mass_kg_m": area * RHO_STEEL * 1000.0}


# ── 평면 뼈대 유한요소 ───────────────────────────────────────────────────
@dataclass(frozen=True)
class Member:
    """2 절점 평면 뼈대 요소 — 절점당 자유도 셋 (u, v, θ)."""
    a: int
    b: int
    section: dict[str, float]
    name: str = ""


@dataclass
class Frame:
    """평면 뼈대. 좌표는 mm, 하중은 N·N·mm."""
    nodes: list[tuple[float, float]]
    members: list[Member]
    fixed: dict[int, tuple[bool, bool, bool]] = field(default_factory=dict)
    #: 절점 하중 {절점: (Fx, Fy, M)}
    loads: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    #: 절점에 매단 집중질량 {절점: kg} — 모드 해석에서만 쓴다.
    masses: dict[int, float] = field(default_factory=dict)

    @property
    def ndof(self) -> int:
        return 3 * len(self.nodes)

    def geometry(self, m: Member) -> tuple[float, float, float]:
        (x1, y1), (x2, y2) = self.nodes[m.a], self.nodes[m.b]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        return L, dx / L, dy / L


def _rotation(c: float, s: float) -> list[list[float]]:
    T = [[0.0] * 6 for _ in range(6)]
    for k in (0, 3):
        T[k][k] = c
        T[k][k + 1] = s
        T[k + 1][k] = -s
        T[k + 1][k + 1] = c
        T[k + 2][k + 2] = 1.0
    return T


def _local_k(L: float, area: float, inertia: float) -> list[list[float]]:
    """국부 강성 — 축력 + Euler-Bernoulli 굽힘."""
    ea, ei = E_STEEL * area / L, E_STEEL * inertia
    k = [[0.0] * 6 for _ in range(6)]
    k[0][0] = k[3][3] = ea
    k[0][3] = k[3][0] = -ea
    b = [[12 * ei / L ** 3, 6 * ei / L ** 2, -12 * ei / L ** 3, 6 * ei / L ** 2],
         [6 * ei / L ** 2, 4 * ei / L, -6 * ei / L ** 2, 2 * ei / L],
         [-12 * ei / L ** 3, -6 * ei / L ** 2, 12 * ei / L ** 3, -6 * ei / L ** 2],
         [6 * ei / L ** 2, 2 * ei / L, -6 * ei / L ** 2, 4 * ei / L]]
    idx = (1, 2, 4, 5)
    for i, ii in enumerate(idx):
        for j, jj in enumerate(idx):
            k[ii][jj] = b[i][j]
    return k


def _local_m(L: float, area: float, _inertia: float = 0.0) -> list[list[float]]:
    """일관 질량행렬 (Archer). 집중질량으로 하면 고차 모드가 틀어진다.

    단면 2 차 모멘트는 안 쓰지만 `_assemble` 이 강성행렬과 같은 꼴로 부르므로 받는다.
    """
    mu = area * RHO_STEEL * L          # kg
    m = [[0.0] * 6 for _ in range(6)]
    m[0][0] = m[3][3] = mu / 3.0
    m[0][3] = m[3][0] = mu / 6.0
    b = [[156.0, 22 * L, 54.0, -13 * L],
         [22 * L, 4 * L * L, 13 * L, -3 * L * L],
         [54.0, 13 * L, 156.0, -22 * L],
         [-13 * L, -3 * L * L, -22 * L, 4 * L * L]]
    idx = (1, 2, 4, 5)
    for i, ii in enumerate(idx):
        for j, jj in enumerate(idx):
            m[ii][jj] = mu / 420.0 * b[i][j]
    return m


def _assemble(frame: Frame, local) -> list[list[float]]:
    n = frame.ndof
    G = [[0.0] * n for _ in range(n)]
    for mem in frame.members:
        L, c, s = frame.geometry(mem)
        kl = local(L, mem.section["area_mm2"], mem.section["inertia_mm4"])
        T = _rotation(c, s)
        # kg = Tᵀ kl T
        tmp = [[sum(kl[i][k] * T[k][j] for k in range(6)) for j in range(6)] for i in range(6)]
        kg = [[sum(T[k][i] * tmp[k][j] for k in range(6)) for j in range(6)] for i in range(6)]
        dofs = [3 * mem.a, 3 * mem.a + 1, 3 * mem.a + 2,
                3 * mem.b, 3 * mem.b + 1, 3 * mem.b + 2]
        for i, di in enumerate(dofs):
            for j, dj in enumerate(dofs):
                G[di][dj] += kg[i][j]
    return G


def _free_dofs(frame: Frame) -> list[int]:
    free = []
    for node in range(len(frame.nodes)):
        held = frame.fixed.get(node, (False, False, False))
        for k in range(3):
            if not held[k]:
                free.append(3 * node + k)
    return free


def frame_solve(frame: Frame) -> dict[str, object]:
    """K d = F 를 풀고 절점 변위와 부재 단부력을 돌려준다."""
    K = _assemble(frame, _local_k)
    free = _free_dofs(frame)
    F = [0.0] * frame.ndof
    for node, (fx, fy, mz) in frame.loads.items():
        F[3 * node] += fx
        F[3 * node + 1] += fy
        F[3 * node + 2] += mz
    Kr = [[K[i][j] for j in free] for i in free]
    Fr = [F[i] for i in free]
    dr = solve(Kr, Fr)
    d = [0.0] * frame.ndof
    for i, dof in enumerate(free):
        d[dof] = dr[i]

    members = []
    for mem in frame.members:
        L, c, s = frame.geometry(mem)
        T = _rotation(c, s)
        dofs = [3 * mem.a, 3 * mem.a + 1, 3 * mem.a + 2,
                3 * mem.b, 3 * mem.b + 1, 3 * mem.b + 2]
        dg = [d[i] for i in dofs]
        dl = [sum(T[i][j] * dg[j] for j in range(6)) for i in range(6)]
        kl = _local_k(L, mem.section["area_mm2"], mem.section["inertia_mm4"])
        fl = [sum(kl[i][j] * dl[j] for j in range(6)) for i in range(6)]
        m_end = max(abs(fl[2]), abs(fl[5]))
        sigma = m_end / mem.section["modulus_mm3"] + abs(fl[0]) / mem.section["area_mm2"]
        members.append({"name": mem.name, "length_mm": L,
                        "axial_n": fl[0], "shear_n": fl[1],
                        "moment_nmm": m_end, "stress_mpa": sigma})
    return {"disp": d, "members": members,
            "max_stress_mpa": max(m["stress_mpa"] for m in members)}


def frame_modes(frame: Frame, count: int = 4) -> list[dict[str, object]]:
    """일반화 고유치 K φ = ω² M φ — Cholesky 로 표준형으로 만들고 Jacobi 로 푼다."""
    K = _assemble(frame, _local_k)
    M = _assemble(frame, _local_m)
    for node, kg in frame.masses.items():
        for k in range(2):                      # 병진 두 방향에만 얹는다
            M[3 * node + k][3 * node + k] += kg
    free = _free_dofs(frame)
    Kr = [[K[i][j] for j in free] for i in free]
    Mr = [[M[i][j] for j in free] for i in free]
    L = cholesky(Mr)
    n = len(free)
    # A = L⁻¹ K L⁻ᵀ — 전진·후진 대입으로 만든다 (역행렬을 만들지 않는다).
    Y = [[0.0] * n for _ in range(n)]
    for col in range(n):
        for i in range(n):
            Y[i][col] = (Kr[i][col] - sum(L[i][k] * Y[k][col] for k in range(i))) / L[i][i]
    A = [[0.0] * n for _ in range(n)]
    for row in range(n):
        for i in range(n):
            A[row][i] = (Y[row][i] - sum(L[i][k] * A[row][k] for k in range(i))) / L[i][i]
    A = [[(A[i][j] + A[j][i]) / 2.0 for j in range(n)] for i in range(n)]   # 대칭화
    vals, vecs = jacobi_eigen(A)
    out = []
    for i in range(min(count, n)):
        w2 = max(vals[i], 0.0)
        # 강성 mm 단위 (N/mm), 질량 kg → ω² 를 rad²/s² 로 맞추려면 1000 을 곱한다.
        f = math.sqrt(w2 * 1000.0) / (2.0 * math.pi)
        shape = [0.0] * frame.ndof
        for j, dof in enumerate(free):
            shape[dof] = vecs[i][j]
        peak = max(abs(x) for x in shape) or 1.0
        out.append({"mode": i + 1, "f_hz": f,
                    "shape": [x / peak for x in shape],
                    "kind": _mode_kind(frame, shape)})
    return out


def _mode_kind(frame: Frame, shape: list[float]) -> str:
    """모드가 흔들림인지 굽힘인지 — 수평 성분이 이기면 흔들림이다."""
    horiz = max(abs(shape[3 * i]) for i in range(len(frame.nodes)))
    vert = max(abs(shape[3 * i + 1]) for i in range(len(frame.nodes)))
    return "sway" if horiz > vert else "bending"


# ── 이 셀의 뼈대 ─────────────────────────────────────────────────────────
#: 브리지 스팬 (mm) — `build_jbr_fab` 이 `bridge_mode` 에 넘기는 값과 같다.
BRIDGE_SPAN_MM = 2_500.0
#: 브리지 각관 150×100×8 을 강축으로 세운 것.
BRIDGE_SECTION = rhs_section(100.0, 150.0, 8.0)
#: 베이스 기둥 각관 100×100×6.
COLUMN_SECTION = rhs_section(100.0, 100.0, 6.0)
#: 기둥 높이 (mm) — 셀 외형 높이 2,800 에서 브리지 상부 여유를 뺀 값.
COLUMN_HEIGHT_MM = 2_300.0


def bridge_frame(head_frac: float = 0.5, vertical_n: float = 0.0,
                 horizontal_n: float = 0.0, head_kg: float | None = None) -> Frame:
    """브리지 포탈 — 기둥 둘과 브리지 하나. 헤드는 스팬 위 한 점에 선다.

    `bridge_mode` 는 브리지만 양단 **단순지지**로 봤다. 그것은 기둥이 무한강성이라는
    뜻이다. 여기서는 기둥을 같이 세워 흔들림 모드가 나오게 한다.
    """
    if head_kg is None:
        head_kg = jf.moving_mass_kg()
    x = BRIDGE_SPAN_MM * head_frac
    nodes = [(0.0, 0.0), (0.0, COLUMN_HEIGHT_MM),
             (x, COLUMN_HEIGHT_MM),
             (BRIDGE_SPAN_MM, COLUMN_HEIGHT_MM), (BRIDGE_SPAN_MM, 0.0)]
    members = [Member(0, 1, COLUMN_SECTION, "기둥 좌"),
               Member(1, 2, BRIDGE_SECTION, "브리지 좌구간"),
               Member(2, 3, BRIDGE_SECTION, "브리지 우구간"),
               Member(3, 4, COLUMN_SECTION, "기둥 우")]
    return Frame(nodes=nodes, members=members,
                 fixed={0: (True, True, True), 4: (True, True, True)},
                 loads={2: (horizontal_n, -vertical_n, 0.0)},
                 masses={2: head_kg})


def bridge_fea(head_frac: float = 0.5, working_kn: float = 0.0) -> dict[str, object]:
    """가감속 관성력과 박리 반력을 얹고 푼다.

    박리 반력이 **닫힌 고리**라 앵커로 안 새는 것은 맞지만(`FORCE_LOOP_CLOSES_INSIDE`),
    그 고리가 브리지를 지나가므로 브리지 자신은 그 힘을 받는다. 대수 검산은 그것을
    안 봤다 — 관성력만 봤다.
    """
    head_kg = jf.moving_mass_kg()
    inertia_n = head_kg * jf.X_DECEL_MS2
    weight_n = head_kg * 9.80665
    peel_n = working_kn * 1000.0
    frame = bridge_frame(head_frac, vertical_n=weight_n + peel_n,
                         horizontal_n=inertia_n, head_kg=head_kg)
    res = frame_solve(frame)
    d = res["disp"]
    return {"head_frac": head_frac, "working_kn": working_kn,
            "head_kg": head_kg, "inertia_n": inertia_n, "peel_n": peel_n,
            "deflection_mm": abs(d[3 * 2 + 1]), "sway_mm": abs(d[3 * 2]),
            "max_stress_mpa": res["max_stress_mpa"],
            "utilisation": res["max_stress_mpa"] / FY_STEEL,
            "members": res["members"]}


#: 헤드 datum 공차 (mm) — 도면집이 브리지 처짐을 재는 기준.
DATUM_TOL_MM = 0.10


def bridge_modal() -> dict[str, object]:
    """포탈 모드. 1 차가 굽힘인지 흔들림인지가 이 해석의 요점이다."""
    modes = frame_modes(bridge_frame(0.5), count=4)
    closed = jf.bridge_mode((100.0, 150.0), 8.0, BRIDGE_SPAN_MM,
                            jf.moving_mass_kg(), jf.X_DECEL_MS2)
    first = modes[0]
    return {"modes": [{"mode": m["mode"], "f_hz": round(m["f_hz"], 2),
                       "kind": m["kind"]} for m in modes],
            "f1_hz": first["f_hz"], "f1_kind": first["kind"],
            "closed_form_hz": closed["f_hz"],
            "closed_form_is_optimistic": first["f_hz"] < closed["f_hz"]}


# ── 레인플로 + Miner ─────────────────────────────────────────────────────
def rainflow(series: list[float]) -> list[tuple[float, float, float]]:
    """ASTM E1049 3 점 레인플로. (진폭범위, 평균, 사이클수) 를 돌려준다.

    반 사이클은 0.5 로 센다 — 잔여 스택을 버리면 하중 이력의 큰 것부터 사라진다.
    """
    if len(series) < 2:
        return []
    # 극값만 남긴다.
    pts = [series[0]]
    for i in range(1, len(series) - 1):
        a, b, c = series[i - 1], series[i], series[i + 1]
        if (b - a) * (c - b) <= 0.0 and b != a:
            pts.append(b)
    pts.append(series[-1])

    out: list[tuple[float, float, float]] = []
    stack: list[float] = []
    for p in pts:
        stack.append(p)
        # 마지막 세 점 X·Y·Z 에서 |Z−Y| ≥ |Y−X| 이면 안쪽 쌍 (X, Y) 가 닫힌 사이클이다.
        # **두 점을 다 빼야 한다** — Y 만 빼면 X 가 다음 점과 다시 짝지어져 과다 계수된다.
        while len(stack) >= 3:
            x, y, z = stack[-3], stack[-2], stack[-1]
            r1, r2 = abs(y - x), abs(z - y)
            if r2 < r1 - 1e-12:
                break
            out.append((r1, (x + y) / 2.0, 1.0))
            del stack[-3:-1]
    for i in range(len(stack) - 1):
        out.append((abs(stack[i + 1] - stack[i]),
                    (stack[i] + stack[i + 1]) / 2.0, 0.5))
    return [c for c in out if c[0] > 1e-9]


#: EC3 용접 상세 등급 (FAT) — 브리지 하부 플랜지의 횡방향 필릿 이음.
#: 상세가 확정되기 전의 관례 선택이고, 이 등급이 바뀌면 수명이 세제곱으로 움직인다.
FAT_CLASS_MPA = 71.0
#: 일정진폭 피로한계 knee (5×10⁶) 와 절단한계 (10⁸).
FAT_KNEE_CYCLES = 5e6
FAT_CUTOFF_CYCLES = 1e8


def sn_cycles(range_mpa: float, fat: float = FAT_CLASS_MPA) -> float:
    """EC3 S-N — knee 아래 m=3, 위 m=5, cutoff 아래는 손상 없음."""
    if range_mpa <= 0.0:
        return math.inf
    d_knee = fat * (2e6 / FAT_KNEE_CYCLES) ** (1.0 / 3.0)
    d_cut = d_knee * (FAT_KNEE_CYCLES / FAT_CUTOFF_CYCLES) ** (1.0 / 5.0)
    if range_mpa < d_cut:
        return math.inf
    if range_mpa >= d_knee:
        return 2e6 * (fat / range_mpa) ** 3
    return FAT_KNEE_CYCLES * (d_knee / range_mpa) ** 5


def miner(cycles: list[tuple[float, float, float]],
          fat: float = FAT_CLASS_MPA) -> float:
    """Miner 누적 손상 — 이력 한 벌당."""
    return sum(n / sn_cycles(r, fat) for r, _mean, n in cycles if math.isfinite(sn_cycles(r, fat)))


# ── 하중 이력 — 운동식에서 낸다 ──────────────────────────────────────────
#: 한 판이 지나는 동안 브리지가 겪는 사건. (시각 s, 헤드 위치 0–1, 수직 하중 kN, 수평 g)
#: 시각은 통합 설계도 운동식의 것이고, 여기서는 그 사이를 잘라 응력 이력을 만든다.
def stress_history(working_kn: float, samples_per_slot: int = 24) -> list[float]:
    """한 판(정션박스 3 개) 동안 브리지 임계 상세의 응력 이력 (MPa).

    순차가 되면서 헤드가 박스마다 Y 로 오가고 슈트까지 왕복한다 — 그때마다 하중
    위치가 바뀐다. 위치가 바뀌면 같은 힘이라도 굽힘모멘트가 달라지므로, **순차는
    3 헤드 동시보다 이력이 길다.** 그것이 피로에서 갚아야 할 값이다.
    """
    mo = SEQUENCE
    hist: list[float] = []
    for box in range(jf.BOXES_PER_PANEL):
        for i in range(samples_per_slot):
            tau = mo["slot"] * i / samples_per_slot
            frac = _head_frac(box, tau)
            load = working_kn if mo["shear"][0] <= tau < mo["shear"][1] else 0.0
            hist.append(bridge_fea(frac, load)["max_stress_mpa"])
    hist.append(hist[0])
    return hist


def _head_frac(box: int, tau: float) -> float:
    """칸 안 상대시각에서 헤드가 스팬의 어디에 있는가 (0–1).

    박스 z 는 −0.5 · −0.04 · +0.42 (기본 시나리오), 슈트는 −1.05 다. 스팬 2,500 에
    맞춰 0–1 로 정규화한다.
    """
    zs = (-0.5, -0.04, 0.42)
    sink = -1.05
    span_lo, span_hi = -1.25, 1.25
    def f(z: float) -> float:
        return (z - span_lo) / (span_hi - span_lo)
    mo = SEQUENCE
    z_box, z_sink = zs[box % len(zs)], sink
    if tau < mo["place"][1]:
        w = tau / mo["place"][1]
        z_from = sink if box else 0.0
        return f(z_from + (z_box - z_from) * w)
    if tau < mo["boxSlide"][0]:
        return f(z_box)
    if tau < mo["boxSlide"][1]:
        w = (tau - mo["boxSlide"][0]) / (mo["boxSlide"][1] - mo["boxSlide"][0])
        return f(z_box + (z_sink - z_box) * w)
    return f(z_sink)


def panels_per_year(takt_s: float | None = None, hours: float = 8_000.0) -> float:
    """연간 판 수 — 택트는 `campaign` 이 잰 값, 연 8,000 h.

    REV.59 까지 여기에 48.47 이 리터럴로 있었다. 택트가 48.59 로 움직였는데 피로
    수명만 옛 택트 위에 서 있던 것이다 — 값이 작아 결과는 안 변했지만, 손으로 옮긴
    숫자는 그런 식으로 낡는다. 이제 앞단이 바뀌면 여기도 같이 바뀐다.
    """
    if takt_s is None:
        takt_s = campaign.summary()["takt_s"]
    return 3600.0 / takt_s * hours


def fatigue_life(working_kn: float, fat: float = FAT_CLASS_MPA) -> dict[str, float | bool]:
    """레인플로 + Miner 로 브리지 임계 상세의 수명을 낸다."""
    hist = stress_history(working_kn)
    cycles = rainflow(hist)
    damage = miner(cycles, fat)
    per_year = panels_per_year()
    d_year = damage * per_year
    return {"working_kn": working_kn, "fat_class": fat,
            "peak_mpa": max(hist), "range_mpa": max(hist) - min(hist),
            "cycle_bins": len(cycles),
            "counted_cycles": sum(n for _r, _m, n in cycles),
            "damage_per_panel": damage, "panels_per_year": per_year,
            "damage_per_year": d_year,
            "years": math.inf if d_year <= 0.0 else 1.0 / d_year,
            "infinite_life": d_year <= 0.0}


# ── 공압 실린더 동특성 ───────────────────────────────────────────────────
#: 공기 상수.
R_AIR = 287.05
T_AIR_K = 293.15
GAMMA = 1.4
#: 임계 압력비 (choked).
P_CRIT = 0.528
#: 밸브·배관 유효 단면적 (mm²) — 통상 3/8" 밸브 + 8 mm 배관.
VALVE_AREA_MM2 = 12.0
#: 실린더 마찰 (N) — 통상 씰 마찰. 보어에 비례해 잡는다.
FRICTION_N_PER_MM2 = 0.0012
#: 데드볼륨 (행정 환산 mm).
DEAD_LENGTH_MM = 15.0


def _mass_flow(p_up: float, p_down: float, area_mm2: float) -> float:
    """오리피스 질량유량 (kg/s). p 는 절대압 Pa."""
    if p_up <= p_down:
        return 0.0
    a = area_mm2 * 1e-6
    ratio = p_down / p_up
    c = a * p_up / math.sqrt(R_AIR * T_AIR_K)
    if ratio <= P_CRIT:
        return c * math.sqrt(GAMMA) * (2.0 / (GAMMA + 1.0)) ** ((GAMMA + 1.0) / (2.0 * (GAMMA - 1.0)))
    return c * math.sqrt(2.0 * GAMMA / (GAMMA - 1.0)
                         * (ratio ** (2.0 / GAMMA) - ratio ** ((GAMMA + 1.0) / GAMMA)))


def cylinder_dynamics(bore_mm: float, stroke_mm: float, supply_mpa: float,
                      load_kn: float, moving_kg: float = 12.0,
                      dt: float = 2e-4, t_max: float = 6.0,
                      valve_area_mm2: float = VALVE_AREA_MM2,
                      v_cap_mms: float | None = None) -> dict[str, object]:
    """실린더가 그 행정을 **언제** 내는가 — 챔버 충전을 시간 적분한다.

    P·A 는 정상상태 힘이다. 챔버가 차기 전에는 그 힘이 없으므로, 짧은 행정을 빨리
    내야 하는 축에서는 충전시간이 관문이 된다. 순차 배분 4.0 s 안의 박리 1.6 s 가
    바로 그 자리다.

    `v_cap_mms` 는 **미터아웃**(배기 교축)의 1 차 모형이다 — 교축은 속도를 그 값에서
    붙든다. 부하가 0 이 되는 구간(접근 공주행 · 박리 뒤)에서 실린더는 유량이 허락하는
    속도까지 그냥 달리므로, 이 상한이 없으면 끝단 에너지가 쿠션 등급을 수십 배 넘는다.
    상한이 있으면 그 속도가 곧 행정 시간을 정한다 — 그래서 미는 힘이 아니라 **멈추는
    힘**이 시간을 잡는 자리가 생긴다.

    상태: x(피스톤 위치 mm) · v(속도 mm/s) · p(구동측 절대압 Pa).
    """
    area_m2 = math.pi / 4.0 * (bore_mm * 1e-3) ** 2
    p_sup = supply_mpa * 1e6 + 101_325.0
    p_atm = 101_325.0
    friction = FRICTION_N_PER_MM2 * math.pi / 4.0 * bore_mm ** 2
    load_n = load_kn * 1000.0
    x, v, p = 0.0, 0.0, p_atm
    t = 0.0
    trace: list[tuple[float, float, float, float]] = [(0.0, 0.0, 0.0, p / 1e6)]
    t_reach: float | None = None
    t_start: float | None = None
    v_end = 0.0

    def deriv(x_: float, v_: float, p_: float) -> tuple[float, float, float]:
        vol = area_m2 * (x_ + DEAD_LENGTH_MM) * 1e-3
        mdot = _mass_flow(p_sup, p_, valve_area_mm2)
        # 등온 충전 + 부피 변화 (dp = (RT·ṁ − p·V̇)/V)
        vdot = area_m2 * v_ * 1e-3
        pdot = (R_AIR * T_AIR_K * mdot - p_ * vdot) / vol
        force = (p_ - p_atm) * area_m2 - load_n - math.copysign(friction, v_ if abs(v_) > 1e-6 else 1.0)
        if x_ <= 0.0 and force < 0.0:
            return 0.0, 0.0, pdot
        if v_cap_mms is not None and v_ >= v_cap_mms and force > 0.0:
            # 교축이 남는 힘을 배압으로 받는다 — 속도는 상한에 머물고 가속은 0 이다.
            # (적분 뒤에만 자르면 매 스텝 상한 위로 재가속했다 잘려 유효 속도가 7 % 빠르다.)
            return v_cap_mms, 0.0, pdot
        return v_, force / moving_kg * 1000.0, pdot

    steps = int(t_max / dt)
    for _ in range(steps):
        k1 = deriv(x, v, p)
        k2 = deriv(x + dt / 2 * k1[0], v + dt / 2 * k1[1], p + dt / 2 * k1[2])
        k3 = deriv(x + dt / 2 * k2[0], v + dt / 2 * k2[1], p + dt / 2 * k2[2])
        k4 = deriv(x + dt * k3[0], v + dt * k3[1], p + dt * k3[2])
        x += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        v += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        p += dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
        p = min(p, p_sup)
        if v_cap_mms is not None and v > v_cap_mms:
            v = v_cap_mms
        if x < 0.0:
            x, v = 0.0, 0.0
        t += dt
        if t_start is None and x > 0.0:
            t_start = t
        if len(trace) < 4000 and len(trace) * (t_max / dt / 4000) <= t / dt:
            trace.append((t, x, v, p / 1e6))
        if t_reach is None and x >= stroke_mm:
            t_reach = t
            v_end = v
            break
    steady_kn = (p_sup - p_atm) * area_m2 / 1000.0
    return {"bore_mm": bore_mm, "stroke_mm": stroke_mm, "supply_mpa": supply_mpa,
            "load_kn": load_kn, "moving_kg": moving_kg,
            "t_stroke_s": t_reach, "reached": t_reach is not None,
            "t_start_s": t_start, "v_end_mms": v_end, "v_cap_mms": v_cap_mms,
            "steady_force_kn": steady_kn,
            "static_margin": steady_kn / max(load_kn, 1e-9),
            "v_peak_mms": max(r[2] for r in trace) if trace else 0.0,
            "trace": trace}


# ── 완충 — 미는 힘이 아니라 멈추는 힘 ──────────────────────────────────
def cushion_allow_j(bore_mm: float) -> float:
    """표준 에어쿠션이 먹는 운동에너지 (J).

    투입 쪽 `catch.CUSHION_ALLOW_J`(Ø40 기준 1.0 J — **가정**, 벤더 확인 필요)를 보어
    면적비로 올린 것이다. 같은 가정을 두 벌 두지 않는다 — 저쪽이 카탈로그 값으로
    바뀌면 여기도 같이 바뀐다. 작게 잡는 쪽이 보수적이다.
    """
    return _catch.CUSHION_ALLOW_J * (bore_mm / 40.0) ** 2


#: 유압식 쇼크업소버 한 본이 먹는 에너지 (J) — `catch` 와 같은 소형 등급.
SHOCK_ABSORBER_J = _catch.SHOCK_ABSORBER_J


#: 박리 창 — 운동식의 shear 구간 길이 (s).
def peel_window_s() -> float:
    lo, hi = SEQUENCE["shear"]
    return hi - lo


def peel_dynamics(working_kn: float, bore_mm: float = 80.0,
                  supply_mpa: float = 0.5,
                  speed_cap_mms: float | None = None) -> dict[str, object]:
    """박리 실린더가 박리 창 안에 행정을 내는가 — 4.0 s 배분의 실제 관문.

    REV.60 부터 부품표 JB-HD-002 의 **미터아웃 설정**을 그대로 얹는다. REV.59 까지는
    교축 없이 풀어 「2 kN 에서 0.85 s, 여유 0.75 s」였는데, 그 실린더는 부품표가
    225 mm/s 로 조여 둔 것이었다 — 해석이 부품표를 안 읽고 있었다. 설정값은 상한이고
    ±공차가 있으므로 판정은 **공차 하한(느린 쪽)** 에서 한다. 빠른 쪽은 창을 넘길
    일이 없고 끝단 에너지만 본다.
    """
    stroke = (SEQUENCE["openWide"] - SEQUENCE["openShut"]) * 1000.0
    cap = jf.PEEL_SPEED_MMS if speed_cap_mms is None else speed_cap_mms
    slow = cap * (1.0 - jf.PEEL_SPEED_TOL)
    res = cylinder_dynamics(bore_mm, stroke, supply_mpa, working_kn, v_cap_mms=cap)
    low = cylinder_dynamics(bore_mm, stroke, supply_mpa, working_kn, v_cap_mms=slow)
    win = peel_window_s()
    res["window_s"] = win
    res["speed_cap_mms"] = cap
    res["speed_low_mms"] = slow
    res["t_slow_s"] = low["t_stroke_s"]
    res["fits_nominal"] = bool(res["t_stroke_s"] is not None and res["t_stroke_s"] <= win)
    res["fits"] = bool(low["t_stroke_s"] is not None and low["t_stroke_s"] <= win)
    res["slack_s"] = None if low["t_stroke_s"] is None else round(win - low["t_stroke_s"], 3)
    res["ke_end_j"] = 0.5 * res["moving_kg"] * (res["v_end_mms"] / 1000.0) ** 2
    res["cushion_j"] = cushion_allow_j(bore_mm)
    res["cushion_ok"] = res["ke_end_j"] <= res["cushion_j"]
    return res


def peel_throttle(working_kn: float = 2.0) -> dict[str, object]:
    """미터아웃 설정이 창을 지키는가 — **창이 요구하는 평균값에 설정을 맞추면 여유가 0 이다.**

    창 1.6 s 에 360 mm 면 평균 225 mm/s 다. 설정을 거기에 두면 시동 지연(챔버 충전)이
    그대로 초과분이 되고, 공차 하한(−10 %)에서는 무부하로도 1.78 s 가 나온다. 설정은
    그 위에 있어야 하고, 위로 올릴수록 끝단 에너지가 오르므로 쿠션이 상한을 정한다.
    두 상한 사이에 설정값이 있어야 한다 — 그 자리를 이 함수가 낸다.
    """
    stroke = (SEQUENCE["openWide"] - SEQUENCE["openShut"]) * 1000.0
    win = peel_window_s()
    need = stroke / win
    at_need = peel_dynamics(working_kn, speed_cap_mms=need)
    now = peel_dynamics(working_kn)
    free = cylinder_dynamics(80.0, stroke, 0.5, 0.0)
    return {"working_kn": working_kn, "stroke_mm": stroke, "window_s": win,
            "need_mms": round(need, 1),
            "cap_mms": jf.PEEL_SPEED_MMS, "tol": jf.PEEL_SPEED_TOL,
            "low_mms": round(now["speed_low_mms"], 1),
            "t_at_need_s": at_need["t_slow_s"], "fits_at_need": at_need["fits"],
            "t_s": now["t_stroke_s"], "t_slow_s": now["t_slow_s"],
            "fits": now["fits"], "slack_s": now["slack_s"],
            "ke_end_j": round(now["ke_end_j"], 2),
            "cushion_j": round(now["cushion_j"], 2), "cushion_ok": now["cushion_ok"],
            "free_run_v_mms": round(free["v_peak_mms"]),
            "free_run_ke_j": round(0.5 * free["moving_kg"] * (free["v_peak_mms"] / 1000.0) ** 2, 1)}


# ── 이송 프로파일 — 운동식이 요구하는 가속도 ────────────────────────────
#: 갠트리 축이 실제로 낼 수 있는 가속도 (m/s²). 이 저장소가 X 축에 쓰는 값과 같다.
#: 헤드 Y 축은 더 가벼우므로 넉넉히 잡아도 이 값의 두 배 안쪽이다.
AXIS_ACCEL_LIMIT_MS2 = jf.X_DECEL_MS2
#: smoothstep 의 피크 가속도 계수 — a_peak = 6·d/t².
SMOOTHSTEP_ACCEL = 6.0


def move_profile(distance_mm: float, seconds: float) -> dict[str, float]:
    """smoothstep 한 번이 요구하는 피크 속도·가속도."""
    d = distance_mm / 1000.0
    if seconds <= 0.0:
        return {"distance_mm": distance_mm, "seconds": seconds,
                "v_peak_mms": math.inf, "a_peak_ms2": math.inf, "g": math.inf}
    return {"distance_mm": distance_mm, "seconds": seconds,
            "v_peak_mms": 1.5 * distance_mm / seconds,
            "a_peak_ms2": SMOOTHSTEP_ACCEL * d / seconds ** 2,
            "g": SMOOTHSTEP_ACCEL * d / seconds ** 2 / 9.80665}


#: 기본 시나리오(triple-wide)의 박스 z (m) — 통합 설계도 `scenarios` 에서 온다.
BOX_Z_M = (-0.5, -0.04, 0.42)


def traverse_check(accel_limit: float | None = None) -> dict[str, object]:
    """순차 운동식의 이송 구간이 **실제로 낼 수 있는 가속도인가.**

    이것이 이 해석에서 가장 무거운 질문이다. 3D 는 어떤 가속도든 그려 준다 —
    시간과 거리를 주면 보간할 뿐이라, 6 g 짜리 이송도 부드럽게 재생된다. 화면이
    말이 되면 기계도 된다고 믿기 쉬운 자리다.
    """
    lim = AXIS_ACCEL_LIMIT_MS2 if accel_limit is None else accel_limit
    mo = SEQUENCE
    place_s = mo["place"][1] - mo["place"][0]
    slide_s = mo["boxSlide"][1] - mo["boxSlide"][0]
    sink = mo["sinkZ"]
    rows = []
    for i, z in enumerate(BOX_Z_M):
        prev = sink if i else 0.0                  # 첫 칸은 원점에서, 이후는 슈트에서
        rows.append(("배치", i + 1, abs(z - prev) * 1000.0, place_s))
        rows.append(("슈트 이송", i + 1, abs(sink - z) * 1000.0, slide_s))
    out = []
    for kind, box, dist, secs in rows:
        p = move_profile(dist, secs)
        p.update({"kind": kind, "box": box, "limit_ms2": lim,
                  "ok": p["a_peak_ms2"] <= lim,
                  "over": p["a_peak_ms2"] / lim})
        out.append(p)
    worst = max(out, key=lambda r: r["a_peak_ms2"])
    return {"limit_ms2": lim, "moves": out,
            "worst": worst, "worst_g": worst["g"], "worst_over": worst["over"],
            "feasible": all(r["ok"] for r in out),
            "failing": sum(1 for r in out if not r["ok"]), "total": len(out)}


def slot_budget(accel_limit: float | None = None) -> dict[str, object]:
    """가속도 한계를 지키면 칸 하나가 **최소 몇 초**인가.

    이송 구간은 t = √(6d/a) 로 되돌려 풀고, 나머지(파지·박리·유지·재개방·상승·투하)는
    운동식의 값을 그대로 쓴다. 박리는 실린더 동특성이 정하므로 여기서는 창 길이를
    그대로 둔다.
    """
    lim = AXIS_ACCEL_LIMIT_MS2 if accel_limit is None else accel_limit
    mo = SEQUENCE
    fixed = ((mo["shear"][1] - mo["shear"][0])          # 박리
             + (mo["boxLift"][1] - mo["boxLift"][0])    # 그리퍼 상승
             + (mo["slot"] - mo["boxSlide"][1])         # 투하
             + (mo["boxSlide"][0] - mo["shear"][1]))    # 유지 + 재개방
    grip = mo["shear"][0] - mo["place"][1]              # 그리퍼 하강·흡착
    worst_place = max(abs(z - (SEQUENCE["sinkZ"] if i else 0.0))
                      for i, z in enumerate(BOX_Z_M)) * 1000.0
    worst_slide = max(abs(SEQUENCE["sinkZ"] - z) for z in BOX_Z_M) * 1000.0
    t_place = math.sqrt(SMOOTHSTEP_ACCEL * worst_place / 1000.0 / lim)
    t_slide = math.sqrt(SMOOTHSTEP_ACCEL * worst_slide / 1000.0 / lim)
    need = t_place + grip + fixed + t_slide
    return {"limit_ms2": lim, "slot_now_s": mo["slot"],
            "t_place_s": round(t_place, 2), "t_grip_s": round(grip, 2),
            "t_fixed_s": round(fixed, 2), "t_slide_s": round(t_slide, 2),
            "need_s": round(need, 2), "over_s": round(need - mo["slot"], 2),
            "fits": need <= mo["slot"],
            "panel_s": round(need * jf.BOXES_PER_PANEL, 2)}


# ── 승강 · 원점 복귀 — 창 1.8 s 를 누가 채우는가 ─────────────────────────
#: 「헤드 z 원점 복귀·승강 상승」에 배분된 창 (s) — 통합 설계도 스테이지 41–42.8.
#: 원본은 스테이지 표다. 시험이 대조한다 (`test_the_homing_window_mirror_matches_the_plant`).
HOME_WINDOW_S = 1.8


def homing_time_s() -> float:
    """헤드 Y 축이 슈트에서 원점으로 — 축 한계 smoothstep 의 최소 시간."""
    return math.sqrt(SMOOTHSTEP_ACCEL * abs(SEQUENCE["sinkZ"]) / AXIS_ACCEL_LIMIT_MS2)


def lift_dynamics(direction: str = "up", speed_cap_mms: float | None = None,
                  stroke_mm: float | None = None) -> dict[str, object]:
    """승강 실린더(Ø63 × 2)를 시간 적분한다 — 박리와 같은 모형으로, 양쪽 끝을 본다.

    두 실린더는 등가 보어 √2·Ø63 하나로 놓는다 — 면적·마찰·데드볼륨·밸브 단면이
    전부 두 배가 되는 것과 같다. 상승은 자중이 부하이고 하강은 자중이 가세한다.
    """
    lc = jf.lift_check()
    count = jf.LIFT_COUNT
    bore = jf.LIFT_BORE_MM * math.sqrt(count)
    stroke = jf.LIFT_STROKE_MM if stroke_mm is None else stroke_mm
    load = lc["need_kn"] * (1.0 if direction == "up" else -1.0)
    res = cylinder_dynamics(bore, stroke, jf.AIR_MPA_MIN, load, moving_kg=lc["moving_kg"],
                            valve_area_mm2=VALVE_AREA_MM2 * count,
                            v_cap_mms=speed_cap_mms, t_max=10.0)
    ke = 0.5 * lc["moving_kg"] * (res["v_end_mms"] / 1000.0) ** 2
    res.update({"direction": direction, "count": count,
                "ke_end_j": ke, "ke_per_cylinder_j": ke / count,
                "cushion_j": cushion_allow_j(jf.LIFT_BORE_MM),
                "cushion_ok": ke / count <= cushion_allow_j(jf.LIFT_BORE_MM)})
    return res


def lift_budget() -> dict[str, object]:
    """승강이 창 안에 드는가 — 미는 힘이 아니라 **멈추는 힘**이 시간을 정한다.

    `jf.lift_check()` 는 이용률 0.59 로 힘이 남는다고 답했고 그것은 맞다. 그런데 부하
    1.85 kN 에 3.12 kN 을 걸면 남는 힘이 그대로 가속이 되어, 420 행정 끝에 188 kg 이
    0.5 m/s 로 닿는다 — 실린더당 12 J, 표준 쿠션(Ø63 ≈ 2.5 J, 가정)의 다섯 배다.
    쿠션이 먹을 수 있는 속도로 조이면 그 속도가 행정 시간을 정하고, 그 시간이 창
    1.8 s 를 꽉 채운다. 창 안의 다른 일(Y 원점 복귀 1.59 s)과 병행이라도, 이제
    관문은 승강이다. 손잡이는 힘이 아니라 **행정**(하드스톱 JB-MZ-003)이나
    **업소버**다 — 여기서 어느 쪽인지 정하지 않는다. 필요한 상승량이 모델에 없다.
    """
    lc = jf.lift_check()
    m = lc["moving_kg"]
    count = jf.LIFT_COUNT
    cushion = cushion_allow_j(jf.LIFT_BORE_MM)
    v_cushion = math.sqrt(2.0 * cushion * count / m) * 1000.0      # mm/s, 실린더당 쿠션 등급
    v_shock = math.sqrt(2.0 * SHOCK_ABSORBER_J * count / m) * 1000.0
    free = lift_dynamics("up")
    cush = lift_dynamics("up", v_cushion)
    shock = lift_dynamics("up", v_shock)
    down = lift_dynamics("down", v_cushion)
    window = HOME_WINDOW_S
    homing = homing_time_s()
    t_c = cush["t_stroke_s"]
    stroke_fit = max(0.0, (window - (cush["t_start_s"] or 0.0)) * v_cushion)
    return {"window_s": window, "homing_s": round(homing, 2), "homing_fits": homing <= window,
            "moving_kg": m, "count": count, "stroke_mm": jf.LIFT_STROKE_MM,
            "cushion_j": round(cushion, 2), "shock_j": SHOCK_ABSORBER_J,
            "free_t_s": free["t_stroke_s"], "free_v_mms": round(free["v_end_mms"]),
            "free_ke_per_cylinder_j": round(free["ke_per_cylinder_j"], 1),
            "free_over_cushion": round(free["ke_per_cylinder_j"] / cushion, 1),
            "cushion_speed_mms": round(v_cushion), "t_cushion_s": t_c,
            "fits_cushion": bool(t_c is not None and t_c <= window),
            "shock_speed_mms": round(v_shock), "t_shock_s": shock["t_stroke_s"],
            "fits_shock": bool(shock["t_stroke_s"] is not None and shock["t_stroke_s"] <= window),
            "t_down_cushion_s": down["t_stroke_s"],
            "stroke_that_fits_mm": round(stroke_fit),
            "binding": "승강" if (t_c is None or t_c > homing) else "원점 복귀"}


# ── 진공 유지력 ─────────────────────────────────────────────────────────
#: 그리퍼 진공 (kPa, 게이지 음압) 과 컵 유효 면적.
VACUUM_KPA = 60.0
CUP_COUNT = 4
CUP_DIAMETER_MM = 40.0
#: 마찰계수 (고무 컵 – 플라스틱 정션박스 상면).
CUP_FRICTION = 0.5
#: 진공 유지 안전율 (수직 2.0 · 수평 4.0 이 통상).
VACUUM_SAFETY_V = 2.0
VACUUM_SAFETY_H = 4.0


#: 정션박스 외형 (m, x·z·높이) — 물리 화면의 박스와 같은 값이고 질량도 여기서 나온다.
BOX_SIZE_M = (0.30, 0.21, 0.055)


def box_volume_l() -> float:
    return BOX_SIZE_M[0] * BOX_SIZE_M[1] * BOX_SIZE_M[2] * 1000.0


def box_mass_kg(sx: float = BOX_SIZE_M[0], sz: float = BOX_SIZE_M[1],
                h: float = BOX_SIZE_M[2]) -> float:
    """정션박스 질량 — 폴리머 하우징 + 다이오드·리본. 밀도 1,150 kg/m³ 에 충전율 0.45."""
    return sx * sz * h * 1_150.0 * 0.45


def vacuum_hold(accel_ms2: float | None = None) -> dict[str, float | bool]:
    """헤드가 박스를 슈트까지 옮기는 동안 컵이 놓치지 않는가.

    기본값은 이송 여섯 구간 중 **최악**(`traverse_check`)이다. REV.59 까지는 가운데
    박스(−0.04) 의 슈트 이송 1.5 m/s² 를 손으로 셈해 넣고 있었다 — 바깥 박스는
    2.2 m/s² 다. 수직 조건이 지배해 판정은 안 변했지만, 최악을 안 보는 검산은
    조건이 바뀌는 순간 거짓 통과가 된다.
    """
    if accel_ms2 is None:
        accel_ms2 = traverse_check()["worst"]["a_peak_ms2"]
    m = box_mass_kg()
    area = CUP_COUNT * math.pi / 4.0 * (CUP_DIAMETER_MM * 1e-3) ** 2
    hold_n = VACUUM_KPA * 1000.0 * area
    need_v = m * 9.80665 * VACUUM_SAFETY_V
    need_h = m * accel_ms2 * VACUUM_SAFETY_H / CUP_FRICTION
    return {"box_kg": round(m, 3), "accel_ms2": round(accel_ms2, 2),
            "hold_n": round(hold_n, 1), "need_vertical_n": round(need_v, 1),
            "need_horizontal_n": round(need_h, 1),
            "margin": round(hold_n / max(need_v, need_h), 2),
            "ok": hold_n >= max(need_v, need_h)}


# ── 로드 좌굴 ───────────────────────────────────────────────────────────
def rod_buckling(rod_mm: float, free_length_mm: float, load_kn: float,
                 end_factor: float = 2.0) -> dict[str, float | bool]:
    """실린더 로드 좌굴 — Euler 와 Johnson 중 세장비가 정하는 쪽을 쓴다.

    end_factor 2.0 은 한쪽 고정·한쪽 자유(외팔)다. 실린더는 그 사이라 보수적으로 잡는다.
    """
    i_mm4 = math.pi * rod_mm ** 4 / 64.0
    area = math.pi / 4.0 * rod_mm ** 2
    r_gyr = math.sqrt(i_mm4 / area)
    le = end_factor * free_length_mm
    slender = le / r_gyr
    slender_c = math.sqrt(2.0 * math.pi ** 2 * E_STEEL / FY_STEEL)
    if slender >= slender_c:
        p_cr = math.pi ** 2 * E_STEEL * i_mm4 / le ** 2
        mode = "Euler"
    else:
        p_cr = area * (FY_STEEL - (FY_STEEL * slender / (2 * math.pi)) ** 2 / E_STEEL)
        mode = "Johnson"
    return {"rod_mm": rod_mm, "free_length_mm": free_length_mm,
            "slenderness": round(slender, 1), "transition": round(slender_c, 1),
            "mode": mode, "p_cr_kn": round(p_cr / 1000.0, 1),
            "load_kn": load_kn, "safety": round(p_cr / 1000.0 / max(load_kn, 1e-9), 2),
            "ok": p_cr / 1000.0 >= 2.0 * load_kn}


# ── 낙하 동역학 — 물리엔진의 기준해 ──────────────────────────────────────
#: 반발계수 (폴리머 하우징 – 강판 수거함).
RESTITUTION = 0.28
#: 중력.
G = 9.80665


def drop_reference(h0_m: float, h_rest_m: float, e: float = RESTITUTION,
                   bounces: int = 6) -> dict[str, object]:
    """자유낙하 + 반발 — 해석해. 물리엔진이 이것과 맞아야 한다.

    첫 접촉 시각 √(2h/g), 이후 n 번째 반발 체공 2·e^n·v0/g. 엔진이 시간·속도를
    이 값과 맞추지 못하면 적분기나 접촉 처리가 틀린 것이다.
    """
    h = h0_m - h_rest_m
    v0 = math.sqrt(2.0 * G * h)
    t_first = math.sqrt(2.0 * h / G)
    times = [t_first]
    t = t_first
    for n in range(1, bounces + 1):
        t += 2.0 * (e ** n) * v0 / G
        times.append(t)
    t_settle = t_first + 2.0 * e * v0 / G / (1.0 - e) if e < 1.0 else math.inf
    return {"drop_m": h, "impact_v_ms": v0, "t_first_s": t_first,
            "contact_times_s": times, "t_settle_s": t_settle,
            "impact_energy_j": 0.5 * box_mass_kg() * v0 ** 2,
            "restitution": e}


def hopper_drop() -> dict[str, object]:
    """호퍼 바닥 플랩이 열려 박스 세 개가 수거함으로 떨어지는 구간."""
    d = SEQUENCE["discharge"]
    return drop_reference(d["highY"], d["restY"])


def gripper_drop() -> dict[str, object]:
    """헤드가 진공을 끊고 박스를 호퍼에 떨구는 구간 — 훨씬 짧다."""
    sink = SEQUENCE["sinkY"]
    return drop_reference(sink[0], sink[1])


# ── 수거함 채움 — 「비움 주기 미결」을 숫자로 ──────────────────────────────
#: 수거함 **명목 용량** (L) — 부품표 JB-WH-002 「용량 90 L」. 외형 580×640×480 의 총부피는
#: 176 L 라, 부품표의 90 은 절반쯤을 쓸 수 있다고 본 값이다. 시험이 통합 설계도 부품표와 대조한다.
BIN_CAPACITY_L = 90.0

#: 수거함 **안치수** (m, x·z·테두리 높이) — 물리 화면이 통합 설계도 `part('BIN')` 에서 판 두께를
#: 빼고 낸 값의 거울. 시험이 `build_jbr_physics.scene()["bin"]` 과 대조한다.
BIN_INNER_M = (0.577, 0.637, 0.48)

#: **물리엔진이 잰 것** — 같은 수거함에 패널을 계속 넣으면 몇 장째에 차는가 (더미가
#: 테두리에 닿거나 박스가 밖으로 나가는 장의 **앞 장**). 산술은 상한(완전 충전)만 주고,
#: 실제 쌓임은 굴러 눕는 자세가 정한다. `node tools/check_jbr_bin.mjs` 가 다시 재서
#: 여기와 대조한다 — **손으로 고치지 말 것.** 엔진이 결정적이라 값이 재현된다.
#: 투하 자리가 매번 같은 세 줄이라 실제보다 가지런히 쌓인다 — 이 값은 낙관 쪽이다.
BIN_ENGINE: dict[str, float | int] = {"panels": 13, "boxes": 39, "fill_m": 0.471}


def bin_fill() -> dict[str, object]:
    """수거함이 몇 분마다 차는가.

    부품표는 폭을 1,320 → 640 으로 줄이며 「비움 주기는 미결」이라 적었다. 미결일 이유가
    없다 — 박스 부피·패널당 개수·처리량이 다 있다. 명목 90 L 를 완전 충전해도 26 개,
    패널 8.7 장, **72 장/h 에서 7 분**이다. 물리엔진으로 실제로 쌓아 보면 테두리까지
    13 장(충전율 78 %) — 11 분. 어느 자로 재도 분 단위다. 스토퍼 해제 조건이 「수거함
    정상」이므로 찬 수거함은 라인을 세운다 — 시간당 대여섯 번에서 여덟 번.
    """
    thr = campaign.summary()["throughput_per_h"]
    per = jf.BOXES_PER_PANEL
    box_l = box_volume_l()
    dense_boxes = BIN_CAPACITY_L / box_l
    dense_panels = dense_boxes / per
    gross_l = BIN_INNER_M[0] * BIN_INNER_M[1] * BIN_INNER_M[2] * 1000.0
    gross_panels = gross_l / box_l / per

    def minutes(panels: float) -> float:
        return panels / thr * 60.0

    eng = BIN_ENGINE["panels"]
    fill = BIN_ENGINE["fill_m"]
    packing = (BIN_ENGINE["boxes"] * box_l / 1000.0
               / (BIN_INNER_M[0] * BIN_INNER_M[1] * fill)) if fill else 0.0
    return {"capacity_l": BIN_CAPACITY_L, "box_l": round(box_l, 2),
            "inner_m": BIN_INNER_M, "gross_l": round(gross_l, 1),
            "throughput_per_h": thr, "boxes_per_panel": per,
            "dense_boxes": round(dense_boxes, 1), "dense_panels": round(dense_panels, 1),
            "dense_minutes": round(minutes(dense_panels), 1),
            "dense_empties_per_h": round(thr / dense_panels, 1),
            "gross_panels": round(gross_panels, 1),
            "gross_minutes": round(minutes(gross_panels), 1),
            "engine_panels": eng, "engine_boxes": BIN_ENGINE["boxes"],
            "engine_fill_m": fill, "engine_packing": round(packing, 2),
            "engine_minutes": round(minutes(eng), 1) if eng else None,
            "engine_empties_per_h": round(thr / eng, 1) if eng else None}


# ── 한 판 ───────────────────────────────────────────────────────────────
def report(working_kn: float = 5.0) -> dict[str, object]:
    """모든 해석을 한 번에 — 도면집과 시험이 같은 함수를 본다."""
    return {
        "fea_mid": bridge_fea(0.5, working_kn),
        "fea_sink": bridge_fea(_head_frac(0, 3.95), working_kn),
        "modal": bridge_modal(),
        "fatigue": {kn: fatigue_life(kn) for kn in (2.0, 5.0, 15.0)},
        "peel": {kn: peel_dynamics(kn) for kn in (2.0, 5.0, 15.0)},
        "peel_throttle": peel_throttle(),
        "lift": lift_budget(),
        "vacuum": vacuum_hold(),
        "buckling": rod_buckling(25.0, 420.0, jf.BLADE_THRUST_KN),
        "hopper_drop": hopper_drop(),
        "gripper_drop": gripper_drop(),
        "bin": bin_fill(),
    }
