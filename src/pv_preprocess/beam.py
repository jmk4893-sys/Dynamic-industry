# -*- coding: utf-8 -*-
"""보의 휨을 푸는 수치해석 핵심 — 유한요소 · 탄성지지 · 시간적분 · 접착 파괴.

`frames.py` 는 외팔보 닫힌식(δ = FL³/3EI) 하나로 프레임의 휨을 답했다. 그 식은
**자유 길이를 미리 알아야** 쓸 수 있는데, 인발에서 자유 길이는 결과다 — 롤러가
당기면 접착이 어디까지 떨어지는지가 풀려야 나온다. 게다가 닫힌식은 한 점의 값만
주고 **모양**을 주지 않아서, 3D 는 그 값을 상수로 받아 마디마다 옮겨 놓는 수밖에
없었다 (장변 10 토막 · 단변 6 토막이 각각 평행이동했다). 프레임은 토막이 아니라
연속체이고, 실제로 휘는 것은 접착 전선 부근의 **한 구간**이다.

그래서 여기서 푸는 것은 다음이다.

    EI·w'''' + k(x)·w = q(x)          (정적, Winkler 탄성지지 위의 보)
    ρA·ẅ + C·ẇ + EI·w'''' + k(x)·w = q(x, t)   (동적)

방법은 2절점 Hermite 보 요소다. 절점마다 처짐 w 와 회전 θ 두 자유도를 두고,
형상함수가 3차라 **집중하중에서는 절점값이 정해와 같다** — 요소를 늘려도 값이
변하지 않는 것이 검증에서 보인다. 분포하중·탄성지지에서는 수렴을 확인한다.

접착 파괴는 절점 해제(node release) 방식이다. 풀고 → 지지반력이 접착 강도를
넘은 요소를 떼고 → 다시 푼다. 전선은 되돌아가지 않는다 (단조 전진).

의존성이 없다. `numpy` 는 이 저장소의 필수 의존성이 아니고(`pyproject.toml` 의
`dependencies = []`), 검사는 `python -m unittest` 로 돈다. 그래서 조밀행렬
LU 분해까지 여기서 직접 쓴다 — 자유도 수백이라 이것으로 충분하다.

단위 (일관계)
    길이 mm · 힘 N · 응력 MPa(N/mm²) · 시간 s · 질량 tonne(N·s²/mm)
    E [MPa] · I [mm⁴] → EI [N·mm²]
    선질량 ρA [tonne/mm] = [kg/mm] × 1e-3
    지지계수 k [N/mm per mm] = [N/mm²]
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: 절점 자유도 — 처짐 w, 회전 θ.
DOF_PER_NODE = 2

#: 해제 반복이 이 횟수를 넘으면 수렴하지 않은 것으로 본다.
MAX_RELEASE_STEPS = 4_000

#: 고유진동수 역반복의 수렴 판정과 상한.
EIG_TOL = 1e-10
EIG_MAX_ITER = 500


# ── 선형대수 (조밀 LU) ───────────────────────────────────────────────────
def lu_factor(a: list[list[float]]) -> tuple[list[list[float]], list[int]]:
    """부분 피벗 LU 분해. `a` 를 제자리에서 고치지 않고 사본을 돌려준다."""
    n = len(a)
    m = [row[:] for row in a]
    piv = list(range(n))
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(m[i][k]))
        if abs(m[p][k]) < 1e-300:
            raise ValueError(f"특이행렬 — {k} 번 자유도가 구속되지 않았다")
        if p != k:
            m[k], m[p] = m[p], m[k]
            piv[k], piv[p] = piv[p], piv[k]
        inv = 1.0 / m[k][k]
        mk = m[k]
        for i in range(k + 1, n):
            mi = m[i]
            f = mi[k] * inv
            if f == 0.0:
                continue
            mi[k] = f
            for j in range(k + 1, n):
                mi[j] -= f * mk[j]
    return m, piv


def lu_solve(lu: list[list[float]], piv: list[int], b: list[float]) -> list[float]:
    n = len(lu)
    x = [b[piv[i]] for i in range(n)]
    for i in range(1, n):                       # 전진대입 (L 의 대각은 1)
        xi, li = x[i], lu[i]
        for j in range(i):
            xi -= li[j] * x[j]
        x[i] = xi
    for i in range(n - 1, -1, -1):              # 후진대입
        xi, li = x[i], lu[i]
        for j in range(i + 1, n):
            xi -= li[j] * x[j]
        x[i] = xi / li[i]
    return x


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    lu, piv = lu_factor(a)
    return lu_solve(lu, piv, b)


# ── 단면과 접착면 ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Section:
    """보 단면 — 휨강성·축강성·선질량과 응력 계산에 필요한 거리."""

    e_mpa: float          # 탄성계수
    i_mm4: float          # 단면 2차 모멘트 (휨 방향)
    area_mm2: float       # 단면적
    c_mm: float           # 중립축에서 최외단까지
    density_t_mm3: float  # 밀도 [tonne/mm³]
    yield_mpa: float      # 항복강도

    @property
    def ei(self) -> float:
        """휨강성 [N·mm²]."""
        return self.e_mpa * self.i_mm4

    @property
    def ea(self) -> float:
        """축강성 [N]."""
        return self.e_mpa * self.area_mm2

    @property
    def rho_a(self) -> float:
        """선질량 [tonne/mm]."""
        return self.density_t_mm3 * self.area_mm2

    @property
    def weight_n_mm(self) -> float:
        """자중 분포하중 [N/mm] — g = 9,810 mm/s²."""
        return self.rho_a * 9_810.0

    def stress_mpa(self, moment_n_mm: float) -> float:
        return abs(moment_n_mm) * self.c_mm / self.i_mm4


@dataclass(frozen=True)
class Foundation:
    """접착면을 Winkler 탄성지지로 본다 — 단위길이당 스프링.

    실란트 비드를 두께 `t`, 폭 `b`, 탄성계수 `E` 의 층으로 보면 단위길이당
    강성은 k = E·b/t 다. 강도는 접착 인장강도 × 폭이고, 파괴에너지는
    그 둘에서 나오는 삼각형 응집영역 넓이다 (G_c = ½·σ_max·δ_max·b).
    """

    e_mpa: float          # 접착층 탄성계수
    width_mm: float       # 접착 폭
    thickness_mm: float   # 접착층 두께
    strength_mpa: float   # 접착 인장강도

    @property
    def k_n_mm2(self) -> float:
        """단위길이당 지지계수 [N/mm per mm]."""
        return self.e_mpa * self.width_mm / self.thickness_mm

    @property
    def strength_n_mm(self) -> float:
        """단위길이당 파괴 견인력 [N/mm]."""
        return self.strength_mpa * self.width_mm

    @property
    def break_deflection_mm(self) -> float:
        """지지가 끊어지는 처짐 [mm]."""
        return self.strength_n_mm / self.k_n_mm2

    #: 단위 접착면적당 파괴에너지 [N/mm]. 응집영역의 **꼬리 길이**를 정한다.
    gc_n_mm2: float = 0.0

    def gc_n_mm(self) -> float:
        """단위길이당 파괴에너지 [N·mm/mm]."""
        if self.gc_n_mm2:
            return self.gc_n_mm2 * self.width_mm
        return 0.5 * self.strength_n_mm * self.break_deflection_mm

    def separation_mm(self) -> float:
        """완전 분리 변위 δ_f — 이중선형 응집영역의 끝. G_c = ½·q_max·δ_f."""
        return max(2.0 * self.gc_n_mm() / self.strength_n_mm,
                   self.break_deflection_mm * 1.0000001)

    def damage_stiffness(self, delta_mm: float) -> float:
        """이중선형 연화의 **할선강성** [N/mm²] — 벌림 δ 에서 유효 지지계수.

        δ ≤ δ₀ 는 손상 전이고, δ₀ 와 δ_f 사이가 연화 구간이다. 이 구간이 있어야
        균열이 한 요소씩 안정하게 나아간다 — 강도만으로 자르면 (요소를 지우면)
        강성이 계단으로 떨어져 균열이 통째로 달아난다.

        δ 는 **벌림**이다: 양수가 접착면이 열리는 쪽이고, 음수는 실란트를 유리
        쪽으로 누르는 쪽이다. 눌러서는 접착이 뜯기지 않으므로 닫히는 쪽은 손상이
        없다 — 크기만 보면(abs) 보가 시소처럼 기울 때 **반대쪽 끝이 눌리는 것**을
        박리로 읽어 접착이 전선과 떨어진 곳에서 끊긴다.
        """
        d0, df = self.break_deflection_mm, self.separation_mm()
        d = delta_mm
        if d <= d0:                       # 닫히는 쪽(음수)도 여기로 온다
            return self.k_n_mm2
        if d >= df:
            return 0.0
        return self.strength_n_mm * (df - d) / ((df - d0) * d)

    def beta_1_mm(self, section: Section) -> float:
        """탄성지지 보의 특성값 β [1/mm] — β = (k / 4EI)^¼."""
        return (self.k_n_mm2 / (4.0 * section.ei)) ** 0.25

    def decay_length_mm(self, section: Section) -> float:
        """휨이 잦아드는 특성길이 1/β [mm] — 화면에서 보이는 구간의 크기다."""
        return 1.0 / self.beta_1_mm(section)


# ── 요소 행렬 ────────────────────────────────────────────────────────────
def element_stiffness(ei: float, length: float) -> list[list[float]]:
    """Hermite 보 요소 강성 [w1, θ1, w2, θ2]."""
    l, l2, l3 = length, length * length, length ** 3
    c = ei / l3
    return [
        [12 * c, 6 * l * c, -12 * c, 6 * l * c],
        [6 * l * c, 4 * l2 * c, -6 * l * c, 2 * l2 * c],
        [-12 * c, -6 * l * c, 12 * c, -6 * l * c],
        [6 * l * c, 2 * l2 * c, -6 * l * c, 4 * l2 * c],
    ]


def _consistent(length: float, factor: float) -> list[list[float]]:
    """일관 질량·지지 행렬의 공통 형태 (같은 형상함수에서 나온다)."""
    l, l2 = length, length * length
    c = factor * length / 420.0
    return [
        [156 * c, 22 * l * c, 54 * c, -13 * l * c],
        [22 * l * c, 4 * l2 * c, 13 * l * c, -3 * l2 * c],
        [54 * c, 13 * l * c, 156 * c, -22 * l * c],
        [-13 * l * c, -3 * l2 * c, -22 * l * c, 4 * l2 * c],
    ]


def element_mass(rho_a: float, length: float) -> list[list[float]]:
    """일관 질량행렬 [tonne 계]."""
    return _consistent(length, rho_a)


def element_foundation(k_n_mm2: float, length: float) -> list[list[float]]:
    """Winkler 지지의 일관 강성 — 질량행렬과 같은 형태다."""
    return _consistent(length, k_n_mm2)


def element_udl(w_n_mm: float, length: float) -> list[float]:
    """등분포하중의 등가 절점하중."""
    l = length
    return [w_n_mm * l / 2.0, w_n_mm * l * l / 12.0,
            w_n_mm * l / 2.0, -w_n_mm * l * l / 12.0]


# ── 보 ───────────────────────────────────────────────────────────────────
class Beam:
    """등간격 절점의 Euler–Bernoulli 보.

    `bonded[i]` 가 참인 요소만 탄성지지를 갖는다. 접착이 떨어지면 거짓이 된다.
    """

    def __init__(self, section: Section, length_mm: float, elements: int,
                 foundation: Foundation | None = None) -> None:
        if elements < 1:
            raise ValueError("요소는 1개 이상이어야 한다")
        self.section = section
        self.length = float(length_mm)
        self.n_el = int(elements)
        self.le = self.length / self.n_el
        self.n_node = self.n_el + 1
        self.ndof = self.n_node * DOF_PER_NODE
        self.foundation = foundation
        self.bonded = [foundation is not None] * self.n_el
        #: 요소별 유효 지지계수 [N/mm²]. 손상이 진행하면 줄고 되돌아가지 않는다.
        self.k_eff = [foundation.k_n_mm2 if foundation else 0.0
                      for _ in range(self.n_el)]

    # 좌표 ---------------------------------------------------------------
    def x(self, node: int) -> float:
        return node * self.le

    def node_at(self, x_mm: float) -> int:
        """가장 가까운 절점 번호."""
        return max(0, min(self.n_node - 1, int(round(x_mm / self.le))))

    # 행렬 ---------------------------------------------------------------
    def _assemble(self, per_element) -> list[list[float]]:
        n = self.ndof
        big = [[0.0] * n for _ in range(n)]
        for e in range(self.n_el):
            ke = per_element(e)
            if ke is None:
                continue
            base = e * DOF_PER_NODE
            for i in range(4):
                bi = big[base + i]
                kei = ke[i]
                for j in range(4):
                    bi[base + j] += kei[j]
        return big

    def stiffness(self) -> list[list[float]]:
        ei, le = self.section.ei, self.le
        ke = element_stiffness(ei, le)

        def per(e: int):
            if self.foundation is None or not self.bonded[e] or self.k_eff[e] <= 0.0:
                return ke
            kf = element_foundation(self.k_eff[e], le)
            return [[ke[i][j] + kf[i][j] for j in range(4)] for i in range(4)]

        return self._assemble(per)

    def element_deflection(self, u: list[float]) -> list[float]:
        """요소 중앙 처짐 [mm] — 손상 판정과 지지반력이 함께 쓴다."""
        out = []
        for e in range(self.n_el):
            b = e * DOF_PER_NODE
            out.append(0.5 * (u[b] + u[b + 2]) + self.le * (u[b + 1] - u[b + 3]) / 8.0)
        return out

    def update_damage(self, u: list[float], opening_sign: float = 1.0) -> bool:
        """처짐에서 손상을 갱신한다. 강성이 실제로 줄었으면 True.

        `opening_sign` 은 접착이 **열리는** 처짐의 부호다. 구동단이 음의 방향으로
        당기면 −1 을 준다 — 그래야 벌림이 양수로 들어가 응집법칙이 제 쪽을 본다.
        """
        if self.foundation is None:
            return False
        changed = False
        for e, d in enumerate(o * opening_sign
                              for o in self.element_deflection(u)):
            if not self.bonded[e]:
                continue
            k = self.foundation.damage_stiffness(d)
            if k < self.k_eff[e] - 1e-12:          # 손상은 되돌아가지 않는다
                self.k_eff[e] = k
                changed = True
            if k <= 0.0:
                self.bonded[e] = False
        return changed

    def mass(self) -> list[list[float]]:
        me = element_mass(self.section.rho_a, self.le)
        return self._assemble(lambda e: me)

    def udl_vector(self, w_n_mm: float) -> list[float]:
        f = [0.0] * self.ndof
        fe = element_udl(w_n_mm, self.le)
        for e in range(self.n_el):
            base = e * DOF_PER_NODE
            for i in range(4):
                f[base + i] += fe[i]
        return f

    # 풀이 ---------------------------------------------------------------
    def solve_static(self, loads: dict[int, float] | None = None,
                     prescribed: dict[int, float] | None = None,
                     udl_n_mm: float = 0.0) -> list[float]:
        """정적 해 — `loads` 는 자유도별 하중, `prescribed` 는 자유도별 강제변위."""
        k = self.stiffness()
        f = self.udl_vector(udl_n_mm) if udl_n_mm else [0.0] * self.ndof
        for dof, value in (loads or {}).items():
            f[dof] += value
        return self._solve_with_bc(k, f, prescribed or {})

    def _solve_with_bc(self, k: list[list[float]], f: list[float],
                       prescribed: dict[int, float]) -> list[float]:
        """강제변위를 행·열 소거로 넣는다 (벌칙법을 쓰지 않는다 — 조건수가 나빠진다)."""
        n = self.ndof
        rhs = f[:]
        for dof, value in prescribed.items():
            if value:
                col = [k[i][dof] for i in range(n)]
                for i in range(n):
                    rhs[i] -= col[i] * value
        for dof, value in prescribed.items():
            for j in range(n):
                k[dof][j] = 0.0
                k[j][dof] = 0.0
            k[dof][dof] = 1.0
            rhs[dof] = value
        return solve(k, rhs)

    # 결과 후처리 ---------------------------------------------------------
    def deflection(self, u: list[float]) -> list[float]:
        return [u[i * DOF_PER_NODE] for i in range(self.n_node)]

    def rotation(self, u: list[float]) -> list[float]:
        return [u[i * DOF_PER_NODE + 1] for i in range(self.n_node)]

    def moments(self, u: list[float]) -> list[float]:
        """요소 중앙 굽힘모멘트 [N·mm] — M = EI·w''."""
        ei, l = self.section.ei, self.le
        out = []
        for e in range(self.n_el):
            b = e * DOF_PER_NODE
            w1, t1, w2, t2 = u[b], u[b + 1], u[b + 2], u[b + 3]
            # 요소 중앙(ξ=0.5)의 2차 도함수.
            out.append(ei * ((6 - 12 * 0.5) / l ** 2 * (w1 - w2)
                             + (4 - 6 * 0.5) / l * t1 + (2 - 6 * 0.5) / l * t2))
        return out

    def max_stress_mpa(self, u: list[float]) -> float:
        return max((self.section.stress_mpa(m) for m in self.moments(u)),
                   default=0.0)

    def foundation_traction(self, u: list[float]) -> list[float]:
        """요소별 접착 견인력 [N/mm] — 요소 중앙 처짐 × 지지계수."""
        if self.foundation is None:
            return [0.0] * self.n_el
        mids = self.element_deflection(u)
        return [self.k_eff[e] * mids[e] if self.bonded[e] else 0.0
                for e in range(self.n_el)]

    def strain_energy(self, u: list[float]) -> float:
        """변형에너지 ½uᵀKu [N·mm] — 에너지 검증용."""
        k = self.stiffness()
        return 0.5 * sum(u[i] * sum(k[i][j] * u[j] for j in range(self.ndof))
                         for i in range(self.ndof))

    # 고유진동 ------------------------------------------------------------
    def fundamental_hz(self, prescribed: tuple[int, ...] = ()) -> float:
        """최저 고유진동수 [Hz] — 역반복(inverse power iteration)."""
        k = self.stiffness()
        m = self.mass()
        free = [d for d in range(self.ndof) if d not in set(prescribed)]
        kk = [[k[i][j] for j in free] for i in free]
        mm = [[m[i][j] for j in free] for i in free]
        lu, piv = lu_factor(kk)
        n = len(free)
        x = [1.0] * n
        lam = 0.0
        for _ in range(EIG_MAX_ITER):
            mx = [sum(mm[i][j] * x[j] for j in range(n)) for i in range(n)]
            y = lu_solve(lu, piv, mx)
            norm = math.sqrt(sum(v * v for v in y))
            if norm == 0.0:
                return 0.0
            y = [v / norm for v in y]
            my = [sum(mm[i][j] * y[j] for j in range(n)) for i in range(n)]
            num = sum(y[i] * sum(kk[i][j] * y[j] for j in range(n)) for i in range(n))
            den = sum(y[i] * my[i] for i in range(n))
            new = num / den
            if lam and abs(new - lam) <= EIG_TOL * abs(new):
                lam = new
                break
            lam, x = new, y
        return math.sqrt(max(lam, 0.0)) / (2.0 * math.pi)


# ── 접착 파괴 (절점 해제) ────────────────────────────────────────────────
@dataclass(frozen=True)
class PeelState:
    """한 번의 인발 자세 — 처짐장과 그때의 힘·응력·전선 위치."""

    x_mm: tuple[float, ...]
    w_mm: tuple[float, ...]
    front_mm: float           # 접착이 살아 있는 첫 자리
    reaction_n: float         # 강제변위 자리에서 받는 반력
    max_stress_mpa: float
    released_elements: int

    @property
    def max_deflection_mm(self) -> float:
        return max(abs(v) for v in self.w_mm)


def peel(beam: Beam, driver_node: int, driver_mm: float,
         udl_n_mm: float = 0.0, from_left: bool = True,
         force_cap_n: float | None = None) -> PeelState:
    """구동단이 접착을 벗긴다 — 견인력이 강도를 넘은 요소를 단조로 뗀다.

    되돌아가지 않는다: 전선은 구동단 쪽에서만 전진한다. 실제 박리도 그렇고,
    그렇게 두지 않으면 해가 요소 사이를 오가며 수렴하지 않는다.

    구동단은 **행정과 용량을 함께 가진 실물 액추에이터**다. 목표 변위
    `driver_mm` 까지 밀되, 그러려면 `force_cap_n` 을 넘는 힘이 드는 자세에서는
    힘으로 갈아탄다. 이 전환이 있어야 stick–slip 이 나온다 — 용량을 무한히 두면
    프레임이 한 번에 통째로 떨어지고, 변위만 두면 접착이 영원히 안 끊어진다.
    """
    if beam.foundation is None:
        raise ValueError("접착이 없는 보에는 박리가 없다")
    limit = beam.foundation.strength_n_mm
    driver_dof = driver_node * DOF_PER_NODE
    order = range(beam.n_el) if from_left else range(beam.n_el - 1, -1, -1)

    def _solve() -> tuple[list[float], float]:
        """변위제어로 풀고, 용량을 넘으면 힘제어로 다시 푼다."""
        uu = beam.solve_static(prescribed={driver_dof: driver_mm}, udl_n_mm=udl_n_mm)
        k = beam.stiffness()
        r = sum(k[driver_dof][j] * uu[j] for j in range(beam.ndof))
        if force_cap_n is None or abs(r) <= force_cap_n:
            return uu, r
        f = math.copysign(force_cap_n, driver_mm or r)
        return beam.solve_static(loads={driver_dof: f}, udl_n_mm=udl_n_mm), f

    u: list[float] = []
    reaction = 0.0
    for _ in range(MAX_RELEASE_STEPS):
        u, reaction = _solve()
        # 이중선형 연화 — 강도만으로 자르지 않고 할선강성을 줄여 나간다. 이것이
        # 있어야 균열이 한 요소씩 나아가고, 없으면 강성이 계단으로 떨어져 통째로
        # 달아난다 (응집영역 길이가 β⁻¹ 과 같은 자릿수라 실제로 지배한다).
        if not beam.update_damage(u, math.copysign(1.0, driver_mm or 1.0)):
            break
    else:                                      # pragma: no cover - 안전망
        raise RuntimeError("접착 손상이 수렴하지 않았다")
    del limit

    w = beam.deflection(u)
    front = beam.length if from_left else 0.0
    for e in order:
        if beam.bonded[e]:
            front = beam.x(e) if from_left else beam.x(e + 1)
            break
    return PeelState(
        x_mm=tuple(beam.x(i) for i in range(beam.n_node)),
        w_mm=tuple(w),
        front_mm=front,
        reaction_n=reaction,
        max_stress_mpa=beam.max_stress_mpa(u),
        released_elements=sum(1 for b in beam.bonded if not b),
    )


# ── 시간적분 (Newmark-β) ─────────────────────────────────────────────────
def newmark(beam: Beam, steps: int, dt: float,
            force, prescribed: dict[int, float] | None = None,
            damping_ratio: float = 0.02, u0: list[float] | None = None,
            v0: list[float] | None = None,
            beta: float = 0.25, gamma: float = 0.5) -> list[list[float]]:
    """평균가속도법 (β=¼, γ=½) — 무조건 안정이라 큰 dt 를 쓸 수 있다.

    `force(step, t)` 는 그 시각의 하중벡터를 준다 — `step` 은 0…`steps` 이고
    돌려주는 이력 `out[step]` 과 같은 시각을 가리킨다. 감쇠는 Rayleigh 로 두되
    1차 모드에서 주어진 감쇠비가 되도록 질량비례 항만 쓴다 (a₀ = 2ζω₁).
    `u0`·`v0` 로 초기 상태를 준다 — 접착이 끊어진 뒤의 **되튐**은 휘어 있던
    자세에서 시작하므로 초기변위가 곧 그 물리다.
    """
    k, m = beam.stiffness(), beam.mass()
    fixed = dict(prescribed or {})
    w1 = 2.0 * math.pi * beam.fundamental_hz(tuple(fixed))
    a0 = 2.0 * damping_ratio * w1
    n = beam.ndof
    c = [[a0 * m[i][j] for j in range(n)] for i in range(n)]

    c0 = 1.0 / (beta * dt * dt)
    c1 = gamma / (beta * dt)
    eff = [[k[i][j] + c0 * m[i][j] + c1 * c[i][j] for j in range(n)] for i in range(n)]
    for dof in fixed:
        for j in range(n):
            eff[dof][j] = 0.0
            eff[j][dof] = 0.0
        eff[dof][dof] = 1.0
    lu, piv = lu_factor(eff)

    u = list(u0) if u0 is not None else [0.0] * n
    v = list(v0) if v0 is not None else [0.0] * n
    for dof, value in fixed.items():
        u[dof] = value
        v[dof] = 0.0
    # 초기 가속도는 운동방정식에서 나온다 — 0 으로 두면 첫 걸음에 없는 충격이 생긴다.
    f0 = force(0, 0.0)
    resid = [f0[i] - sum(k[i][j] * u[j] + c[i][j] * v[j] for j in range(n))
             for i in range(n)]
    m_bc = [row[:] for row in m]
    for dof in fixed:
        for j in range(n):
            m_bc[dof][j] = 0.0
            m_bc[j][dof] = 0.0
        m_bc[dof][dof] = 1.0
        resid[dof] = 0.0
    a = lu_solve(*lu_factor(m_bc), resid)
    out = [u[:]]
    for step in range(steps):
        # 이 걸음이 푸는 평형은 **도착 시각** t_{n+1} 의 것이다. 출발 시각의 하중을
        # 넣으면 하중이 통째로 한 걸음 밀려, t=0 에 0 이고 그 뒤 걸리는 하중은
        # 첫 걸음 동안 보를 못 움직인다. out[i] 와 force(i, i·dt) 가 같은 시각이다.
        f = force(step + 1, (step + 1) * dt)
        rhs = [0.0] * n
        for i in range(n):
            mi, ci = m[i], c[i]
            acc = 0.0
            for j in range(n):
                acc += mi[j] * (c0 * u[j] + v[j] / (beta * dt)
                                + a[j] * (0.5 / beta - 1.0))
                acc += ci[j] * (c1 * u[j] + v[j] * (gamma / beta - 1.0)
                                + a[j] * dt * (gamma / (2.0 * beta) - 1.0))
            rhs[i] = f[i] + acc
        for dof, value in fixed.items():
            rhs[dof] = value
        u_new = lu_solve(lu, piv, rhs)
        a_new = [c0 * (u_new[i] - u[i]) - v[i] / (beta * dt)
                 - a[i] * (0.5 / beta - 1.0) for i in range(n)]
        v_new = [v[i] + dt * ((1.0 - gamma) * a[i] + gamma * a_new[i])
                 for i in range(n)]
        u, v, a = u_new, v_new, a_new
        out.append(u[:])
    return out
