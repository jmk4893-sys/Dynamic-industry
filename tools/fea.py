"""3차원 골조 해석기 — 직접강성법.

상용 FEA 패키지가 없으므로 필요한 것만 직접 짠다. 이 설비의 구조 질문은
전부 **뼈대(frame)** 질문이다 — 문형이 추력에 얼마나 밀리는가, 크로스빔이
얼마나 처지는가, 기둥이 좌굴하는가, 갠트리의 1차 고유진동수가 칼날
가감속과 겹치는가. 이 넷은 보요소로 정확히 풀린다.

풀리지 않는 것도 분명히 해 둔다 — 용접부 국부응력, 접촉, 판의 국부좌굴,
3차원 응력집중은 이 해석기로 못 본다. 그것은 상세설계에서 상용 FEA 로
확인할 항목이고, 보고서에 그렇게 적는다.

**검증 없는 해석기는 계산기가 아니라 난수 발생기다.** 그래서 이 파일은
닫힌해가 있는 문제 넷으로 스스로를 검증한다 (validate()).

    절점 6자유도  [ux, uy, uz, rx, ry, rz]
    요소 12×12   축력 · 비틀림 · 두 축 휨
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np


class Sec(NamedTuple):
    """단면 성질. mm 계열로 통일한다 — 도면이 mm 이므로."""
    A: float        # mm²
    Iy: float       # mm⁴ (약축 · x-z 평면 휨)
    Iz: float       # mm⁴ (강축 · x-y 평면 휨)
    J: float        # mm⁴ 비틀림 상수
    E: float = 205_000.0     # MPa (N/mm²)
    G: float = 79_000.0      # MPa
    rho: float = 7.85e-9     # t/mm³ → N·s²/mm⁴ 환산은 아래에서


def hsec(h, b, tw, tf) -> Sec:
    """H 형강 단면 성질."""
    A = 2 * b * tf + (h - 2 * tf) * tw
    Iz = (b * h ** 3 - (b - tw) * (h - 2 * tf) ** 3) / 12
    Iy = (2 * tf * b ** 3 + (h - 2 * tf) * tw ** 3) / 12
    J = (2 * b * tf ** 3 + (h - 2 * tf) * tw ** 3) / 3
    return Sec(A, Iy, Iz, J)


def boxsec(h, b, t) -> Sec:
    """각형강관 단면 성질. 비틀림은 Bredt 박판 폐단면."""
    A = h * b - (h - 2 * t) * (b - 2 * t)
    Iz = (b * h ** 3 - (b - 2 * t) * (h - 2 * t) ** 3) / 12
    Iy = (h * b ** 3 - (h - 2 * t) * (b - 2 * t) ** 3) / 12
    Am = (h - t) * (b - t)
    J = 4 * Am ** 2 * t / (2 * ((h - t) + (b - t)))
    return Sec(A, Iy, Iz, J)


def rectsec(b, h) -> Sec:
    """직사각 단면 (판·봉)."""
    A = b * h
    Iz = b * h ** 3 / 12
    Iy = h * b ** 3 / 12
    a, c = max(b, h) / 2, min(b, h) / 2
    J = a * c ** 3 * (16 / 3 - 3.36 * c / a * (1 - c ** 4 / (12 * a ** 4)))
    return Sec(A, Iy, Iz, J)


def circsec(d) -> Sec:
    I = math.pi * d ** 4 / 64
    return Sec(math.pi * d ** 2 / 4, I, I, 2 * I)


def _local_k(L: float, s: Sec) -> np.ndarray:
    """국부좌표 12×12 강성행렬 (Euler-Bernoulli)."""
    E, G, A, Iy, Iz, J = s.E, s.G, s.A, s.Iy, s.Iz, s.J
    k = np.zeros((12, 12))
    # 축력
    k[0, 0] = k[6, 6] = E * A / L
    k[0, 6] = k[6, 0] = -E * A / L
    # 비틀림
    k[3, 3] = k[9, 9] = G * J / L
    k[3, 9] = k[9, 3] = -G * J / L
    # x-y 평면 휨 (Iz, DOF v=1,5 / 7,11)
    a = 12 * E * Iz / L ** 3
    b = 6 * E * Iz / L ** 2
    c = 4 * E * Iz / L
    d = 2 * E * Iz / L
    k[1, 1] = k[7, 7] = a
    k[1, 7] = k[7, 1] = -a
    k[1, 5] = k[5, 1] = k[1, 11] = k[11, 1] = b
    k[5, 7] = k[7, 5] = k[7, 11] = k[11, 7] = -b
    k[5, 5] = k[11, 11] = c
    k[5, 11] = k[11, 5] = d
    # x-z 평면 휨 (Iy, DOF w=2,4 / 8,10) — 부호가 반대다
    a = 12 * E * Iy / L ** 3
    b = 6 * E * Iy / L ** 2
    c = 4 * E * Iy / L
    d = 2 * E * Iy / L
    k[2, 2] = k[8, 8] = a
    k[2, 8] = k[8, 2] = -a
    k[2, 4] = k[4, 2] = k[2, 10] = k[10, 2] = -b
    k[4, 8] = k[8, 4] = k[8, 10] = k[10, 8] = b
    k[4, 4] = k[10, 10] = c
    k[4, 10] = k[10, 4] = d
    return k


def _rot(p1, p2, roll=0.0) -> np.ndarray:
    """국부→전역 방향여현 3×3. roll 은 부재축 둘레 회전(도)."""
    v = np.array(p2, float) - np.array(p1, float)
    L = np.linalg.norm(v)
    ex = v / L
    up = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(ex, up)) > 0.999:            # 수직 부재
        up = np.array([1.0, 0.0, 0.0])
    ey = np.cross(up, ex)
    ey /= np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    if roll:
        c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
        ey, ez = c * ey + s * ez, -s * ey + c * ez
    return np.vstack([ex, ey, ez])


class Frame:
    """절점과 부재로 이루어진 골조. 단위는 mm · N."""

    def __init__(self):
        self.nodes: list[tuple] = []
        self.elems: list[tuple] = []       # (n1, n2, Sec, roll)
        self.fix: dict[int, tuple] = {}    # node → 6개 불리언 (구속=True)
        self.load: dict[int, np.ndarray] = {}   # node → 6성분 하중

    def node(self, x, y, z) -> int:
        self.nodes.append((float(x), float(y), float(z)))
        return len(self.nodes) - 1

    def beam(self, n1, n2, sec: Sec, roll=0.0) -> int:
        self.elems.append((n1, n2, sec, roll))
        return len(self.elems) - 1

    def support(self, n, ux=True, uy=True, uz=True, rx=True, ry=True, rz=True):
        self.fix[n] = (ux, uy, uz, rx, ry, rz)

    def force(self, n, fx=0.0, fy=0.0, fz=0.0, mx=0.0, my=0.0, mz=0.0):
        self.load[n] = self.load.get(n, np.zeros(6)) + np.array(
            [fx, fy, fz, mx, my, mz], float)

    # ── 조립 ───────────────────────────────────────────────────────────
    def _dofs(self, n) -> list[int]:
        return list(range(6 * n, 6 * n + 6))

    def _assemble(self):
        N = 6 * len(self.nodes)
        K = np.zeros((N, N))
        for n1, n2, s, roll in self.elems:
            p1, p2 = self.nodes[n1], self.nodes[n2]
            L = math.dist(p1, p2)
            R = _rot(p1, p2, roll)
            T = np.zeros((12, 12))
            for i in range(4):
                T[3 * i:3 * i + 3, 3 * i:3 * i + 3] = R
            ke = T.T @ _local_k(L, s) @ T
            d = self._dofs(n1) + self._dofs(n2)
            K[np.ix_(d, d)] += ke
        return K

    def _free(self) -> list[int]:
        fixed = set()
        for n, f in self.fix.items():
            for i, c in enumerate(f):
                if c:
                    fixed.add(6 * n + i)
        return [i for i in range(6 * len(self.nodes)) if i not in fixed]

    def solve(self) -> np.ndarray:
        """절점 변위 (N×6). mm · rad."""
        K = self._assemble()
        F = np.zeros(6 * len(self.nodes))
        for n, v in self.load.items():
            F[self._dofs(n)] += v
        free = self._free()
        u = np.zeros(6 * len(self.nodes))
        u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
        return u.reshape(-1, 6)

    def member_forces(self) -> list[np.ndarray]:
        """부재 국부 단면력 12성분 — [N,Vy,Vz,T,My,Mz] × 2단."""
        u = self.solve().reshape(-1)
        out = []
        for n1, n2, s, roll in self.elems:
            p1, p2 = self.nodes[n1], self.nodes[n2]
            L = math.dist(p1, p2)
            R = _rot(p1, p2, roll)
            T = np.zeros((12, 12))
            for i in range(4):
                T[3 * i:3 * i + 3, 3 * i:3 * i + 3] = R
            d = self._dofs(n1) + self._dofs(n2)
            out.append(_local_k(L, s) @ T @ u[d])
        return out

    # ── 고유진동 ───────────────────────────────────────────────────────
    def modes(self, extra_mass: dict[int, float] | None = None, n=3):
        """1차부터 n차까지 고유진동수 Hz.

        질량은 부재 자중을 절점에 반씩 얹는 집중질량이다(lumped). 병진
        자유도에만 질량이 있으므로 회전 자유도는 **정적 축약(Guyan)** 으로
        없앤다.

            K_red = K_tt − K_tr · K_rr⁻¹ · K_rt

        질량 없는 자유도를 그냥 지우면 그것을 구속한 것이 되어 구조가
        훨씬 뻣뻣해진다 — 처음에 그렇게 짰다가 캔틸레버 1차 진동수가
        닫힌해의 15 배로 나왔다. 검증이 그것을 잡았다.
        """
        K = self._assemble()
        N = 6 * len(self.nodes)
        M = np.zeros(N)
        for n1, n2, s, _roll in self.elems:
            L = math.dist(self.nodes[n1], self.nodes[n2])
            m = s.A * L * 7.85e-9 / 2          # t (= N·s²/mm)
            for nd in (n1, n2):
                M[6 * nd:6 * nd + 3] += m
        if extra_mass:
            for nd, kg in extra_mass.items():
                M[6 * nd:6 * nd + 3] += kg / 1000 / 3   # kg → t, 3축 분배
        free = self._free()
        t = [i for i in free if M[i] > 0]      # 질량이 있는 병진 자유도
        r = [i for i in free if M[i] <= 0]     # 질량 없는 자유도 — 축약한다
        Ktt = K[np.ix_(t, t)]
        if r:
            Krr = K[np.ix_(r, r)]
            Krt = K[np.ix_(r, t)]
            Ktt = Ktt - Krt.T @ np.linalg.solve(Krr, Krt)
        s_ = 1.0 / np.sqrt(M[t])
        A = (Ktt * s_).T * s_
        w2 = np.linalg.eigvalsh((A + A.T) / 2)
        w2 = w2[w2 > 1e-9]
        return [math.sqrt(v) / (2 * math.pi) for v in np.sort(w2)[:n]]


# ── 좌굴 (개별 부재) ───────────────────────────────────────────────────
def euler_buckling(sec: Sec, L: float, k: float = 1.0) -> float:
    """오일러 좌굴하중 N. k 는 유효길이계수 (양단고정 0.5 · 캔틸레버 2.0)."""
    return math.pi ** 2 * sec.E * min(sec.Iy, sec.Iz) / (k * L) ** 2


def slenderness(sec: Sec, L: float, k: float = 1.0) -> float:
    """세장비 λ = kL/r."""
    r = math.sqrt(min(sec.Iy, sec.Iz) / sec.A)
    return k * L / r


# ── 판 휨 (등분포 · 4변 고정) ──────────────────────────────────────────
def plate_deflection(a: float, b: float, t: float, q: float,
                     E: float = 205_000.0, nu: float = 0.3) -> float:
    """4변 고정 직사각판 중앙 처짐 mm. q 는 MPa (N/mm²).

    Timoshenko 표의 α 를 종횡비로 보간한다. 리브 사이 한 칸을 이렇게 본다 —
    판 전체를 한 판으로 보면 리브가 하는 일을 못 센다.
    """
    D = E * t ** 3 / (12 * (1 - nu ** 2))
    r = max(a, b) / min(a, b)
    tab = {1.0: 0.00126, 1.2: 0.00172, 1.4: 0.00207, 1.6: 0.00230,
           1.8: 0.00245, 2.0: 0.00254, 3.0: 0.00260}
    ks = sorted(tab)
    r = min(max(r, ks[0]), ks[-1])
    for i in range(len(ks) - 1):
        if ks[i] <= r <= ks[i + 1]:
            f = (r - ks[i]) / (ks[i + 1] - ks[i])
            al = tab[ks[i]] + f * (tab[ks[i + 1]] - tab[ks[i]])
            break
    return al * q * min(a, b) ** 4 / D


def plate_stress(a: float, b: float, t: float, q: float) -> float:
    """4변 고정 직사각판 최대 휨응력 MPa (장변 중앙 지점부)."""
    r = max(a, b) / min(a, b)
    tab = {1.0: 0.3078, 1.2: 0.3834, 1.4: 0.4356, 1.6: 0.4680,
           1.8: 0.4872, 2.0: 0.4974, 3.0: 0.5000}
    ks = sorted(tab)
    r = min(max(r, ks[0]), ks[-1])
    for i in range(len(ks) - 1):
        if ks[i] <= r <= ks[i + 1]:
            f = (r - ks[i]) / (ks[i + 1] - ks[i])
            be = tab[ks[i]] + f * (tab[ks[i + 1]] - tab[ks[i]])
            break
    return be * q * min(a, b) ** 2 / t ** 2


# ── 검증 ───────────────────────────────────────────────────────────────
def validate() -> list[tuple[str, float, float, float]]:
    """닫힌해가 있는 문제로 해석기를 검증한다.

    (이름, 해석값, 닫힌해, 상대오차) 목록. 검증 없는 해석기는 계산기가
    아니라 난수 발생기다 — 이 함수가 통과하지 않으면 아래 결과를 믿지 않는다.
    """
    out = []
    s = rectsec(100, 100)
    E, I, A = s.E, s.Iz, s.A
    L, P = 3000.0, 10_000.0

    # ① 캔틸레버 단부하중 — δ = PL³/3EI
    f = Frame()
    a, b = f.node(0, 0, 0), f.node(L, 0, 0)
    f.beam(a, b, s)
    f.support(a)
    f.force(b, fy=-P)
    got = abs(f.solve()[b][1])
    want = P * L ** 3 / (3 * E * I)
    out.append(("캔틸레버 단부하중 처짐", got, want, abs(got - want) / want))

    # ② 캔틸레버 축력 — δ = PL/EA
    f = Frame()
    a, b = f.node(0, 0, 0), f.node(L, 0, 0)
    f.beam(a, b, s)
    f.support(a)
    f.force(b, fx=P)
    got = abs(f.solve()[b][0])
    want = P * L / (E * A)
    out.append(("캔틸레버 축방향 신장", got, want, abs(got - want) / want))

    # ③ 양단고정 중앙집중 — δ = PL³/192EI
    f = Frame()
    a = f.node(0, 0, 0)
    m = f.node(L / 2, 0, 0)
    b = f.node(L, 0, 0)
    f.beam(a, m, s)
    f.beam(m, b, s)
    f.support(a)
    f.support(b)
    f.force(m, fy=-P)
    got = abs(f.solve()[m][1])
    want = P * L ** 3 / (192 * E * I)
    out.append(("양단고정 중앙집중 처짐", got, want, abs(got - want) / want))

    # ④ 단순지지 등분포 (절점하중 근사) — δ = 5wL⁴/384EI
    n = 20
    w = 5.0                                   # N/mm
    f = Frame()
    ns = [f.node(L * i / n, 0, 0) for i in range(n + 1)]
    for i in range(n):
        f.beam(ns[i], ns[i + 1], s)
    f.support(ns[0], ux=True, uy=True, uz=True, rx=True, ry=False, rz=False)
    f.support(ns[-1], ux=False, uy=True, uz=True, rx=True, ry=False, rz=False)
    for i, nd in enumerate(ns):
        share = w * L / n * (0.5 if i in (0, n) else 1.0)
        f.force(nd, fy=-share)
    got = abs(f.solve()[ns[n // 2]][1])
    want = 5 * w * L ** 4 / (384 * E * I)
    out.append(("단순지지 등분포 처짐", got, want, abs(got - want) / want))

    # ⑤ 캔틸레버 1차 고유진동수 — f = 0.5596·√(EI/(mL⁴))
    f = Frame()
    ns = [f.node(L * i / 10, 0, 0) for i in range(11)]
    for i in range(10):
        f.beam(ns[i], ns[i + 1], s)
    f.support(ns[0])
    got = f.modes(n=1)[0]
    mlin = A * 7.85e-9                        # t/mm
    want = 0.5596 * math.sqrt(E * I / (mlin * L ** 4))
    out.append(("캔틸레버 1차 고유진동수", got, want, abs(got - want) / want))

    return out


if __name__ == "__main__":
    print("=" * 74)
    print("골조 해석기 검증 — 닫힌해 대조")
    print("=" * 74)
    ok = True
    for name, got, want, err in validate():
        flag = "OK" if err < 0.03 else "★ 오차 과다"
        ok &= err < 0.03
        print(f"  {name:24s} 해석 {got:12.5f}  닫힌해 {want:12.5f}  오차 {err:6.2%}  {flag}")
    print("=" * 74)
    print("검증 통과 — 이 해석기의 결과를 쓸 수 있다" if ok else "★ 검증 실패 — 결과를 쓰지 않는다")
    print("=" * 74)
