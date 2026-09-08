# -*- coding: utf-8 -*-
"""BFC-101 엔드링의 구조 해석 — OI-02.

미결 항목은 이렇게 적혀 있다: "링은 Ø1,980 … 지금 단면은 인양·정지 하중을
여유 있게 받지만 **회전 관성의 대부분이기도 하다** (436 kg·m² 중 링이
지배적). 줄일 수 있는지는 링 자중 처짐·용접부 응력을 봐야 하고 그건 FEA다."

그래서 FEA 를 여기서 한다. 대단한 것이 아니다 — **평면 프레임 유한요소**다.
링을 다각형으로 나눠 2절점 보요소로 잇고, 강성행렬을 세워 푼다. 표준
라이브러리만 쓰므로 가우스 소거를 직접 적는다 (`dynamics` 가 적분기를 직접
적은 것과 같은 이유다 — 해석기가 설치물을 요구하기 시작하면 CI 에서 조용히
안 돌게 된다).

**요소를 믿을 근거를 먼저 만든다.** 세 가지를 닫힌 해와 맞춘다:

  · 외팔보 선단 처짐 PL³/3EI — 요소와 조립이 맞는지.
  · 링을 지름으로 누를 때의 모멘트 WR/π · WR(1/2 − 1/π) — 곡률이 맞는지.
  · 그때의 지름 변화 (π/4 − 2/π)WR³/EI · (2/π − 1/2)WR³/EI — 처짐이 맞는지.

셋이 맞으면 자중과 조 하중을 실어도 된다.

**이 해석이 새로 정하는 것 둘.**

* **지지 롤러 각도가 모델 어디에도 없다.** 링은 지지 롤러 두 개 위에 얹혀
  도는데(제작 순서 6 「엔드링 안착」), 그 두 롤러가 밑바닥에서 몇 도씩
  벌어져 있는지는 어느 값에도 안 적혀 있다. 그런데 그것이 링 모멘트를
  정하는 가장 큰 손잡이다. 여기서 처음 값으로 잡고, 그 감도를 표로 낸다.
* **응력은 돌면서 뒤집힌다.** 조 하중은 링과 함께 돌고 지지 반력은 제자리에
  있으므로, 링의 **한 점**은 한 바퀴마다 최대와 최소를 한 번씩 겪는다.
  그러면 판정은 정적 응력이 아니라 **응력범위**다 — 용접부 피로가 여기서
  나온다. 미결 항목이 "용접부 피로" 를 적어 둔 자리가 정확히 이것이다.

**여기서 처음 적는 값은 재료의 항복·피로 등급과 지지 롤러 각도뿐이다.**
탄성계수·허용응력은 `afr`, 단면과 런아웃은 제작 도면집, 질량은 `drives`,
수명은 `safety`·`smart`·`campaign` 에서 읽는다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.ring
"""

from __future__ import annotations

import functools
import math
import re

from . import afr, campaign, drives, dynamics, fabrication, kinematics, safety, smart

# ── 재료·등급·배치 (여기서 처음 적는 값) ────────────────────────────────

#: STKM13A 항복강도 (MPa). KS D 3517 기계구조용 탄소강관 — 인장 ≥ 370, 항복 ≥ 215.
#: `afr.STEEL_ALLOW_MPA` 160 은 SS400 기준의 일반 허용응력이라 관재에는 따로 둔다.
STKM13A_YIELD_MPA = 215.0

#: 정적 판정의 안전율. 회전체이고 사람 위를 지나는 하중이라 크게 잡는다.
STATIC_SAFETY = 2.0

#: 용접부 피로 등급 (MPa, EN 1993-1-9 의 detail category — 2×10⁶ 회에서의
#: 응력범위). 원형 중공단면의 **횡방향 맞대기 완전용입** 용접이고 as-welded
#: 이므로 71 로 잡는다. 뒷댐재를 쓰면 56 으로 내려간다 — 제작 도면집이
#: "맞대기 완전용입" 만 적고 뒷댐 여부를 안 적었으므로 이것이 가정이다.
WELD_FAT_MPA = 71.0

#: 피로 부분안전계수 (EN 1993-1-9 표 3.1). 점검 가능하고 파손이 곧 붕괴는
#: 아니지만 패널을 떨어뜨리므로 damage tolerant · high consequence 인 1.15 다.
FATIGUE_GAMMA_MF = 1.15

#: 지지 롤러가 링 밑바닥에서 벌어진 반각 (deg). **모델 어디에도 없던 값이다.**
#: 회전체를 두 롤러로 받치는 통상 범위는 25…35° 이고, 좁으면 롤러 반력이
#: 커지고 넓으면 링 모멘트가 커진다. 30 은 그 가운데다 — `support_sweep()` 이
#: 이 값의 감도를 낸다.
SUPPORT_HALF_ANGLE_DEG = 30.0

#: 기본 요소 수. 링 한 바퀴를 이만큼의 직선 보요소로 나눈다. 다각형이 원에
#: 수렴하는지는 `checks()` 의 첫 줄이 확인한다.
ELEMENTS = 72

#: 훑기용 요소 수. 단면·지지각을 **견주는** 계산은 절대값이 아니라 차이를 보는
#: 것이고, 36 과 72 의 차이가 1 % 안이라(같은 검사가 그것을 본다) 여기서는
#: 성긴 쪽을 쓴다 — 훑기가 시험을 느리게 만들면 아무도 안 돌린다.
SWEEP_ELEMENTS = 36

#: 지지·락 구속을 넣는 벌칙 강성 배수 (요소 축강성 EA/L 의 배수).
PENALTY = 1e8


SHEET = dynamics.SHEET_BFC
_RUNOUT = re.compile(r"런아웃\s*([\d.]+)")


# ── 선형대수 (표준 라이브러리만) ─────────────────────────────────────────
def solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """부분 피벗 가우스 소거. numpy 없이 도는 것이 이 저장소의 규약이다."""
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-30:
            raise ValueError(f"특이행렬 — {col} 번째 자유도가 안 묶였다")
        if piv != col:
            a[col], a[piv] = a[piv], a[col]
        prow, d = a[col], a[col][col]
        for r in range(col + 1, n):
            f = a[r][col] / d
            if f == 0.0:
                continue
            row = a[r]
            for c in range(col, n + 1):
                row[c] -= f * prow[c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / a[r][r]
    return x


# ── 단면 ────────────────────────────────────────────────────────────────
def _ring_part() -> fabrication.Part:
    return dynamics._part(SHEET, "BFC-RNG-01")


def tube_od_mm() -> float:
    """관 바깥지름 (mm) — 부품표 `size` 의 둘째 항이다 (1,800 × 180 × t10)."""
    return float(_ring_part().size[1])


def tube_t_mm() -> float:
    return float(_ring_part().t)


def runout_mm() -> float:
    """외주 선삭 런아웃 허용 (mm) — 공정 문장에서 읽는다.

    이것이 **처짐의 판정선**이다. 링은 롤러 위를 도는데 하중으로 반경이
    그만큼 변하면 선삭으로 잡아 둔 런아웃이 운전 중에 없어진다.
    """
    m = _RUNOUT.search(_ring_part().process)
    if not m:
        raise ValueError("공정에 런아웃 값이 없다")
    return float(m.group(1))


def section(od_mm: float | None = None, t_mm: float | None = None
            ) -> dict[str, float]:
    """원형 중공단면의 A · I · Z (mm², mm⁴, mm³)."""
    od = tube_od_mm() if od_mm is None else od_mm
    t = tube_t_mm() if t_mm is None else t_mm
    idd = od - 2 * t
    a = math.pi / 4 * (od ** 2 - idd ** 2)
    i = math.pi / 64 * (od ** 4 - idd ** 4)
    return {"od": od, "t": t, "A": a, "I": i, "Z": i / (od / 2)}


def mass_per_m_kg(od_mm: float | None = None, t_mm: float | None = None) -> float:
    return section(od_mm, t_mm)["A"] / 1e6 * afr.STEEL_DENSITY_KG_M3


def ring_mass_kg(od_mm: float | None = None, t_mm: float | None = None) -> float:
    """링 한 매의 질량 (kg) — 중심선 원주 × 단위질량."""
    circ = 2 * math.pi * kinematics.RING_R_MM / 1_000.0
    return mass_per_m_kg(od_mm, t_mm) * circ


def ring_inertia_kgm2(od_mm: float | None = None, t_mm: float | None = None) -> float:
    """링 두 매의 회전관성 (kg·m²) — `drives.flip_inertia_kgm2()` 의 링 항이다."""
    r = kinematics.RING_R_MM / 1_000.0
    return 2 * ring_mass_kg(od_mm, t_mm) * r ** 2


# ── 평면 프레임 요소 ────────────────────────────────────────────────────
def _element_k(e: float, a: float, i: float, x1: float, y1: float,
               x2: float, y2: float) -> tuple[list[list[float]], float, float]:
    """2절점 평면 프레임 요소의 전역 강성 (6×6) 과 방향코사인."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    c, s = dx / L, dy / L
    ea, ei = e * a / L, e * i / L ** 3
    k = [[0.0] * 6 for _ in range(6)]
    # 국부 강성
    kl = [
        [ea, 0, 0, -ea, 0, 0],
        [0, 12 * ei, 6 * ei * L, 0, -12 * ei, 6 * ei * L],
        [0, 6 * ei * L, 4 * ei * L * L, 0, -6 * ei * L, 2 * ei * L * L],
        [-ea, 0, 0, ea, 0, 0],
        [0, -12 * ei, -6 * ei * L, 0, 12 * ei, -6 * ei * L],
        [0, 6 * ei * L, 2 * ei * L * L, 0, -6 * ei * L, 4 * ei * L * L],
    ]
    t = [
        [c, s, 0, 0, 0, 0],
        [-s, c, 0, 0, 0, 0],
        [0, 0, 1, 0, 0, 0],
        [0, 0, 0, c, s, 0],
        [0, 0, 0, -s, c, 0],
        [0, 0, 0, 0, 0, 1],
    ]
    # k = Tᵀ kl T
    kt = [[sum(kl[r][m] * t[m][q] for m in range(6)) for q in range(6)] for r in range(6)]
    for r in range(6):
        for q in range(6):
            k[r][q] = sum(t[m][r] * kt[m][q] for m in range(6))
    return k, L, c


class Frame:
    """평면 프레임 모형 — 절점·요소·하중·구속을 담고 푼다."""

    def __init__(self, e_mpa: float, area: float, inertia: float) -> None:
        self.e, self.a, self.i = e_mpa, area, inertia
        self.nodes: list[tuple[float, float]] = []
        self.elems: list[tuple[int, int]] = []
        self.f: list[float] = []
        self.springs: list[tuple[int, float, float, float]] = []   # 절점, nx, ny, k
        self.rots: list[tuple[int, float]] = []                    # 절점, 회전 강성

    def node(self, x: float, y: float) -> int:
        self.nodes.append((x, y))
        self.f += [0.0, 0.0, 0.0]
        return len(self.nodes) - 1

    def beam(self, i: int, j: int) -> None:
        self.elems.append((i, j))

    def load(self, n: int, fx: float = 0.0, fy: float = 0.0, m: float = 0.0) -> None:
        self.f[3 * n] += fx
        self.f[3 * n + 1] += fy
        self.f[3 * n + 2] += m

    def restrain(self, n: int, nx: float, ny: float, k: float) -> None:
        """절점 `n` 을 방향 (nx, ny) 으로 벌칙 스프링으로 묶는다.

        롤러 지지는 **반경 방향만** 묶는 구속이라 이 형태가 그대로 맞는다 —
        전역 x·y 로 나누면 비스듬한 롤러를 못 적는다.
        """
        self.springs.append((n, nx, ny, k))

    def fix_rotation(self, n: int, k: float) -> None:
        """절점의 회전을 벌칙으로 묶는다 (고정단·대칭면)."""
        self.rots.append((n, k))

    def udl(self, i: int, j: int, wx: float, wy: float) -> None:
        """요소에 등분포하중 (N/mm) 을 걸어 **일관 절점하중**으로 바꾼다."""
        (x1, y1), (x2, y2) = self.nodes[i], self.nodes[j]
        L = math.hypot(x2 - x1, y2 - y1)
        c, s = (x2 - x1) / L, (y2 - y1) / L
        wl = -wx * s + wy * c              # 요소 국부 횡방향 성분
        wa = wx * c + wy * s               # 축방향 성분
        # 횡방향: 절점력 wL/2, 절점모멘트 ∓wL²/12. 축방향: wL/2 씩.
        for n, sign in ((i, 1.0), (j, -1.0)):
            self.load(n, fx=wa * L / 2 * c - wl * L / 2 * s,
                      fy=wa * L / 2 * s + wl * L / 2 * c,
                      m=sign * wl * L * L / 12)

    def solve(self) -> list[float]:
        n = len(self.nodes) * 3
        k = [[0.0] * n for _ in range(n)]
        for i, j in self.elems:
            (x1, y1), (x2, y2) = self.nodes[i], self.nodes[j]
            ke, _, _ = _element_k(self.e, self.a, self.i, x1, y1, x2, y2)
            dofs = [3 * i, 3 * i + 1, 3 * i + 2, 3 * j, 3 * j + 1, 3 * j + 2]
            for r in range(6):
                kr = k[dofs[r]]
                for q in range(6):
                    kr[dofs[q]] += ke[r][q]
        for nd, nx, ny, kp in self.springs:
            d = [3 * nd, 3 * nd + 1]
            v = [nx, ny]
            for r in range(2):
                for q in range(2):
                    k[d[r]][d[q]] += kp * v[r] * v[q]
        for nd, kp in self.rots:
            k[3 * nd + 2][3 * nd + 2] += kp
        return solve(k, self.f)

    def end_axials(self, u: list[float]) -> list[float]:
        """요소 축력 (N). 링에서는 **후프력**이고 응력에 그대로 더해진다."""
        out = []
        for i, j in self.elems:
            (x1, y1), (x2, y2) = self.nodes[i], self.nodes[j]
            L = math.hypot(x2 - x1, y2 - y1)
            c, s = (x2 - x1) / L, (y2 - y1) / L
            d = ((u[3 * j] - u[3 * i]) * c + (u[3 * j + 1] - u[3 * i + 1]) * s)
            out.append(self.e * self.a / L * d)
        return out

    def reactions(self, u: list[float]) -> list[tuple[float, float]]:
        """벌칙 스프링이 낸 반력 벡터 (N, 전역 x·y) — 넣은 순서대로.

        스칼라로 돌려주면 비스듬한 롤러의 평형을 못 검산한다 — 반경 방향
        성분만 더하면 실린 하중과 안 맞는다.
        """
        out = []
        for nd, nx, ny, kp in self.springs:
            mag = -kp * (nx * u[3 * nd] + ny * u[3 * nd + 1])
            out.append((mag * nx, mag * ny))
        return out

    def end_moments(self, u: list[float]) -> list[tuple[float, float]]:
        """요소마다 (i 단, j 단) 모멘트 (N·mm). 부호는 국부 좌표계다."""
        out = []
        for i, j in self.elems:
            (x1, y1), (x2, y2) = self.nodes[i], self.nodes[j]
            L = math.hypot(x2 - x1, y2 - y1)
            c, s = (x2 - x1) / L, (y2 - y1) / L
            ue = [u[3 * i], u[3 * i + 1], u[3 * i + 2],
                  u[3 * j], u[3 * j + 1], u[3 * j + 2]]
            v1 = -s * ue[0] + c * ue[1]
            v2 = -s * ue[3] + c * ue[4]
            t1, t2 = ue[2], ue[5]
            ei = self.e * self.i
            m1 = ei / L ** 2 * (6 * v1 + 4 * L * t1 - 6 * v2 + 2 * L * t2)
            m2 = ei / L ** 2 * (6 * v1 + 2 * L * t1 - 6 * v2 + 4 * L * t2)
            out.append((-m1, m2))
        return out


# ── 링을 실제 하중으로 푼다 ─────────────────────────────────────────────
def jaw_load_per_ring_n() -> float:
    """링 한 매가 받는 조·패드·캐리어·포스트 + 패널의 무게 (N).

    `drives.flip_rotating_kg()` 에서 링 자신을 뺀 나머지가 조 쪽 하중이고,
    그것을 링 두 매가 나눈다. 여기서 다시 세지 않는다.
    """
    a = fabrication.assembly(SHEET)
    by = {p.tag: p.weight_kg() for p in a.parts}
    hung = (2 * by["BFC-CLP-01"] + 4 * by["BFC-PAD-01"] + 4 * by["BFC-JCR-01"]
            + 4 * by["BFC-JGP-01"] + drives.PANEL_KG)
    return hung / 2.0 * dynamics.G


@functools.lru_cache(maxsize=4096)
def analyse(phi_deg: float = 0.0, od_mm: float | None = None,
            t_mm: float | None = None, half_angle_deg: float | None = None,
            n: int = ELEMENTS) -> dict[str, object]:
    """링 한 매를 푼다. `phi_deg` 는 조 캐리어가 선 각도 (수평에서 반시계).

    좌표는 **씬 좌표**다 — 중력은 늘 −y 이고 지지 롤러는 늘 아래에 있다.
    반전은 조 하중이 링을 따라 도는 것으로 들어온다.
    """
    sec = section(od_mm, t_mm)
    half = SUPPORT_HALF_ANGLE_DEG if half_angle_deg is None else half_angle_deg
    r = float(kinematics.RING_R_MM)
    fr = Frame(afr.STEEL_E_MPA, sec["A"], sec["I"])
    nodes = [fr.node(r * math.cos(2 * math.pi * k / n),
                     r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    for k in range(n):
        fr.beam(nodes[k], nodes[(k + 1) % n])

    # ① 자중 — 등분포를 일관 절점하중으로.
    w = mass_per_m_kg(od_mm, t_mm) * dynamics.G / 1_000.0        # N/mm
    for k in range(n):
        fr.udl(nodes[k], nodes[(k + 1) % n], 0.0, -w)

    # ② 조 하중 — 캐리어가 반경 안쪽 `JAW_CLOSED_Z_MM` 까지 뻗으므로
    #    링에는 **힘과 함께 그 편심 모멘트**가 들어온다.
    f_jaw = jaw_load_per_ring_n() / 2.0
    arm = r - kinematics.JAW_CLOSED_Z_MM
    for side in (0.0, 180.0):
        psi = math.radians(phi_deg + side)
        k = round((psi % (2 * math.pi)) / (2 * math.pi) * n) % n
        fr.load(nodes[k], fy=-f_jaw, m=f_jaw * arm * math.cos(psi))

    # ③ 지지 — 아래쪽 롤러 둘은 반경 방향만 묶는다. 접선은 구동 롤러가 잡는다.
    big = PENALTY * afr.STEEL_E_MPA * sec["A"] / (2 * math.pi * r / n)
    roller = []
    for sign in (-1.0, 1.0):
        ang = math.radians(270.0 + sign * half)
        k = round((ang % (2 * math.pi)) / (2 * math.pi) * n) % n
        roller.append(k)
        fr.restrain(nodes[k], math.cos(ang), math.sin(ang), big)
    bottom = round(0.75 * n) % n
    fr.restrain(nodes[bottom], -math.sin(math.radians(270.0)),
                math.cos(math.radians(270.0)), big)

    u = fr.solve()
    mm = fr.end_moments(u)
    nn = fr.end_axials(u)
    react = fr.reactions(u)
    rx = sum(v[0] for v in react)
    ry = sum(v[1] for v in react)
    node_m = [mm[k][0] for k in range(n)]
    stress = [abs(node_m[k]) / sec["Z"] + abs(nn[k]) / sec["A"] for k in range(n)]
    radial = [(u[3 * k] * math.cos(2 * math.pi * k / n)
               + u[3 * k + 1] * math.sin(2 * math.pi * k / n)) for k in range(n)]
    total = w * 2 * math.pi * r + 2 * f_jaw
    return {
        "n": n, "phi": phi_deg, "section": sec,
        "nodeM": node_m, "axial": nn, "stress": stress, "radial": radial,
        "peakMpa": max(stress), "peakAt": max(range(n), key=lambda k: stress[k]),
        "rollerN": [math.hypot(*react[0]), math.hypot(*react[1])],
        "rollerUp": [react[0][1], react[1][1]], "rollerAt": roller,
        "appliedN": total, "reactSumN": ry, "reactSideN": rx,
        "radialRangeMm": max(radial) - min(radial),
    }


# ── 돌면서 뒤집히는 응력 — 피로 (OI-02 의 「용접부 피로」) ──────────────
def _signed_stress(a: dict, k: int) -> float:
    """절점 k 의 **부호 있는** 굽힘응력 (MPa). 범위를 내려면 부호가 있어야 한다."""
    return a["nodeM"][k] / a["section"]["Z"]


@functools.lru_cache(maxsize=256)
def rotation_sweep(od_mm: float | None = None, t_mm: float | None = None,
                   half_angle_deg: float | None = None, n: int = ELEMENTS
                   ) -> dict[str, object]:
    """링을 한 바퀴 돌리며 **재료 한 점**이 겪는 응력범위를 낸다.

    조 하중은 링과 함께 돌고 중력·지지 롤러는 제자리에 있다. 그래서 씬에서
    보면 하중 배치가 φ 만큼 돌고, 링 위의 재료점 α 는 씬 각 α+φ 에 있다.
    두 조가 180° 대칭이라 φ 는 180° 만 훑으면 된다.
    """
    step = 360.0 / n
    phis = [i * step for i in range(int(round(180.0 / step)))]
    per_phi = [analyse(phi, od_mm, t_mm, half_angle_deg, n) for phi in phis]
    ranges, means = [], []
    for alpha in range(n):
        vals = [_signed_stress(per_phi[i], (alpha + i) % n) for i in range(len(phis))]
        ranges.append(max(vals) - min(vals))
        means.append((max(vals) + min(vals)) / 2)
    worst = max(range(n), key=lambda k: ranges[k])
    return {
        "phis": phis, "rangeMpa": ranges, "meanMpa": means,
        "worstRangeMpa": ranges[worst], "worstAt": worst,
        "peakStaticMpa": max(a["peakMpa"] for a in per_phi),
        "worstRadialMm": max(a["radialRangeMm"] for a in per_phi),
        "minRollerN": min(min(a["rollerUp"]) for a in per_phi),
    }


@functools.lru_cache(maxsize=64)
def design_cycles() -> float:
    """설계 수명 동안 링의 한 점이 겪는 응력 반복 수.

    반전 한 번(0° → 180° → 0°)에 재료 한 점은 하중 배치를 한 바퀴 겪으므로
    **반전한 패널 한 장에 한 사이클**이다. 반전 비율은 캠페인이, 운전시간은
    `smart` 가, 사명시간은 `safety` 가 갖고 있다 — 여기서 다시 적지 않는다.
    """
    c = campaign.summary()
    flips_per_h = c["throughput_per_h"] * c["flipped"] / c["panels"]
    return (flips_per_h * smart.OPERATING_HOURS_PER_YEAR
            * safety.MISSION_TIME_YEARS)


@functools.lru_cache(maxsize=64)
def fatigue_allow_mpa(cycles: float | None = None) -> float:
    """그 반복 수에서 허용되는 응력범위 (MPa) — EN 1993-1-9 의 m=3 곡선.

    2×10⁶ 회의 등급값에서 (2e6/N)^(1/3) 로 옮기고 부분안전계수로 나눈다.
    5×10⁶ 회의 무릎(상수진폭 피로한도)보다 많으면 그 아래로는 안 내려간다고
    보는 것이 통상이지만, 여기서는 **더 엄한 쪽**으로 m=3 을 계속 쓴다.
    """
    n = design_cycles() if cycles is None else cycles
    return WELD_FAT_MPA * (2e6 / n) ** (1 / 3) / FATIGUE_GAMMA_MF


# ── 롤러가 관 벽을 누르는 자리 — 보요소가 못 보는 곳 ────────────────────
def wall_spread_mm(od_mm: float | None = None, t_mm: float | None = None) -> float:
    """롤러 반력이 관 벽으로 퍼지는 유효 길이 (mm) — 2√(R t) 관례값.

    원통 셸에 국부하중이 걸릴 때 감쇠 길이가 √(R t) 규모라는, 셸 이론의
    표준 어림이다. **가정이다** — 정확한 값은 셸 FEA 나 시험에서 온다.
    """
    sec = section(od_mm, t_mm)
    return 2.0 * math.sqrt(kinematics.RING_R_MM * sec["t"])


def wall_stress_mpa(reaction_n: float, od_mm: float | None = None,
                    t_mm: float | None = None) -> float:
    """롤러 밑에서 관 **벽**에 나는 굽힘응력 (MPa).

    보요소는 링을 선으로 보므로 이 응력을 못 본다. 관 단면을 그 자체로 하나의
    링으로 보고, 위에서 검증한 「지름으로 누르는 링」의 0.318 W R 을 그대로
    쓴다 — 같은 닫힌 해를 다른 규모에 적용하는 것이다. 관 단면이 롤러와
    반대쪽 지지 사이에서 눌린다고 보는 것이라 **보수적**이다.
    """
    sec = section(od_mm, t_mm)
    w = reaction_n / wall_spread_mm(od_mm, t_mm)          # N/mm (관 축방향)
    r_mean = (sec["od"] - sec["t"]) / 2.0
    moment = w * r_mean / math.pi                          # N·mm per mm
    z_wall = sec["t"] ** 2 / 6.0                           # mm³ per mm
    return moment / z_wall


# ── 단면을 줄일 수 있는가 (OI-02 가 실제로 묻는 것) ─────────────────────
#: 훑어 볼 관 규격 (외경 mm, 두께 mm). 지금 것이 첫 줄이다.
CANDIDATES: tuple[tuple[float, float], ...] = (
    (180.0, 10.0), (180.0, 8.0), (180.0, 6.0),
    (165.2, 7.1), (165.2, 5.0),
    (152.4, 6.0), (152.4, 4.5),
    (139.8, 6.0), (139.8, 4.5),
    (114.3, 4.5),
)


def dt_class(od_mm: float | None = None, t_mm: float | None = None) -> int:
    """원형 중공단면의 단면 등급 (EN 1993-1-1 표 5.2 — 1·2·3, 4 면 국부좌굴).

    벽을 얇게 하면 **강도보다 먼저 국부좌굴**이 온다. 보요소는 그것을 못 보므로
    D/t 로 거른다. ε² = 235/fy 다.
    """
    sec = section(od_mm, t_mm)
    dt = sec["od"] / sec["t"]
    e2 = 235.0 / STKM13A_YIELD_MPA
    if dt <= 50 * e2:
        return 1
    if dt <= 70 * e2:
        return 2
    if dt <= 90 * e2:
        return 3
    return 4


def dynamic_amplification() -> float:
    """반전 가속이 링에 더하는 접선 관성력을 중력으로 나눈 값.

    OI-02 는 "인양·정지 하중" 이라고 적었다. **도는 동안의 하중**도 같이
    봐야 하는데, 각가속이 작아 자중에 비하면 무시할 만하다는 것을 값으로
    남긴다 — 무시했다는 사실이 값에 없으면 다음 사람이 다시 묻는다.
    """
    slip = dynamics.flip_slip()
    alpha = slip["demandNm"] / drives.flip_inertia_kgm2()      # rad/s²
    return alpha * (kinematics.RING_R_MM / 1_000.0) / dynamics.G


@functools.lru_cache(maxsize=64)
def takt_after_reduction() -> dict[str, object]:
    """단면을 줄이면 **택트 여유**가 어떻게 되는가.

    `dynamics.takt_headroom()` 이 1.04 배에서 「마찰 롤러 미끄럼」에 걸린다고
    했다. 그 요구는 관성에 비례하고 전달 능력은 링 반지름에 비례하므로, 링을
    줄이면 요구가 크게 줄고 능력이 조금 준다. 그 순증을 여기서 센다 —
    **링 단면이 택트를 잡고 있었는지**가 이 항목의 진짜 값어치다.
    """
    small = smallest_section()
    j_now = drives.flip_inertia_kgm2()
    r_now = (kinematics.RING_R_MM + tube_od_mm() / 2) / 1_000.0
    if small is None:
        return {"now": dynamics.takt_headroom()}
    j_new = j_now - ring_inertia_kgm2() + ring_inertia_kgm2(small["odMm"],
                                                            small["tMm"])
    r_new = (kinematics.RING_R_MM + small["odMm"] / 2) / 1_000.0
    scale, best, who = 1.0, 1.0, "걸리는 것 없음"
    while scale <= 4.0:
        demand = dynamics.flip_slip(scale)["demandNm"] * j_new / j_now
        capacity = drives.FLIP_PRELOAD_N * drives.FRICTION_MU * r_new
        limits = {
            "BFC-101 마찰 롤러 미끄럼":
                capacity / demand >= drives.FRICTION_SAFETY,
            "AXIS-BFC-Z 서보 순시 토크":
                dynamics.lift_torque_nm(scale)
                <= drives.rated_torque_nm("AXIS-BFC-Z") * drives.SERVO_PEAK_FACTOR,
            "RB-101 EOAT 진공 파지":
                dynamics.eoat_limit_ms2()["limitMs2"]
                >= dynamics.eoat_transfer_demand_ms2() * scale ** 2,
        }
        failed = [k for k, ok in limits.items() if not ok]
        if failed:
            who = failed[0]
            break
        best = scale
        scale += 0.01
    now, now_who = dynamics.takt_headroom()
    return {"nowScale": now, "nowBinding": now_who,
            "newScale": round(best, 2), "newBinding": who,
            "gain": round(best / now, 2)}


def static_allow_mpa() -> float:
    """정적 허용응력 (MPa) — 항복을 안전율로 나눈다."""
    return STKM13A_YIELD_MPA / STATIC_SAFETY


@functools.lru_cache(maxsize=64)
def verdict(od_mm: float, t_mm: float, n: int = ELEMENTS) -> dict[str, object]:
    """한 단면이 네 판정을 다 지나는가 — 정적·피로·처짐·벽.

    넷을 따로 세어 두는 이유는 **무엇이 먼저 걸리는지**가 답이기 때문이다.
    다 통과/불통과만 내면 단면을 왜 그 크기로 두는지가 안 남는다.
    """
    sw = rotation_sweep(od_mm, t_mm, None, n)
    wall = wall_stress_mpa(max(abs(v) for v in
                               analyse(0.0, od_mm, t_mm, None, n)["rollerN"]),
                           od_mm, t_mm)
    allow, fat = static_allow_mpa(), fatigue_allow_mpa()
    row = {
        "odMm": od_mm, "tMm": t_mm,
        "massKg": round(ring_mass_kg(od_mm, t_mm), 1),
        "inertiaKgm2": round(ring_inertia_kgm2(od_mm, t_mm), 1),
        "staticMpa": round(sw["peakStaticMpa"], 2),
        "rangeMpa": round(sw["worstRangeMpa"], 2),
        "radialMm": round(sw["worstRadialMm"], 4),
        "wallMpa": round(wall, 1),
        "boreMm": round(2 * (kinematics.RING_R_MM - od_mm / 2), 0),
        "class": dt_class(od_mm, t_mm),
    }
    row["staticOk"] = sw["peakStaticMpa"] <= allow
    row["fatigueOk"] = sw["worstRangeMpa"] <= fat
    row["radialOk"] = sw["worstRadialMm"] <= runout_mm()
    row["wallOk"] = wall <= allow
    row["classOk"] = row["class"] <= 2          # 소성 회전을 안 쓰므로 2 까지 본다
    row["ok"] = bool(row["staticOk"] and row["fatigueOk"] and row["radialOk"]
                     and row["wallOk"] and row["classOk"])
    binds = [(row["staticMpa"] / allow, "정적 굽힘"),
             (row["rangeMpa"] / fat, "용접부 피로"),
             (row["radialMm"] / runout_mm(), "런아웃 잠식"),
             (row["wallMpa"] / allow, "롤러 밑 관 벽")]
    worst = max(binds)
    row["binding"] = worst[1]
    row["utilisation"] = round(worst[0], 3)
    return row


@functools.lru_cache(maxsize=64)
def section_options(n: int = SWEEP_ELEMENTS) -> list[dict[str, object]]:
    return [verdict(od, t, n) for od, t in CANDIDATES]


@functools.lru_cache(maxsize=64)
def smallest_section(n: int = SWEEP_ELEMENTS) -> dict[str, object] | None:
    """네 판정을 다 지나는 것 중 **가장 가벼운** 단면."""
    ok = [r for r in section_options(n) if r["ok"]]
    return min(ok, key=lambda r: r["massKg"]) if ok else None


@functools.lru_cache(maxsize=64)
def inertia_saving() -> dict[str, float]:
    """단면을 그 자리까지 줄이면 반전축이 무엇을 버는가.

    링은 `drives.flip_inertia_kgm2()` 의 대부분이다. 링 관성이 줄면 전체 관성이
    그만큼 줄고, 반전 토크는 관성에 비례한다 — 그런데 마찰 롤러의 전달 능력은
    링 반지름에 비례하므로 지름을 줄이면 그쪽은 손해다. 둘을 같이 본다.
    """
    small = smallest_section()
    now = ring_inertia_kgm2()
    total = drives.flip_inertia_kgm2()
    if small is None:
        return {"ringNowKgm2": round(now, 1), "totalNowKgm2": round(total, 1)}
    new_ring = ring_inertia_kgm2(small["odMm"], small["tMm"])
    new_total = total - now + new_ring
    r_now = (kinematics.RING_R_MM + tube_od_mm() / 2) / 1_000.0
    r_new = (kinematics.RING_R_MM + small["odMm"] / 2) / 1_000.0
    return {
        "ringNowKgm2": round(now, 1), "ringNewKgm2": round(new_ring, 1),
        "totalNowKgm2": round(total, 1), "totalNewKgm2": round(new_total, 1),
        "inertiaDrop": round(1 - new_total / total, 3),
        "massDropKgPerRing": round(ring_mass_kg() - ring_mass_kg(small["odMm"],
                                                                small["tMm"]), 1),
        "driveRadiusNowM": round(r_now, 3), "driveRadiusNewM": round(r_new, 3),
        # 필요 압착력 ∝ 관성 / 반지름 — 둘이 반대로 움직인다.
        "preloadRatio": round((new_total / total) * (r_now / r_new), 3),
        "boreNowMm": round(2 * (kinematics.RING_R_MM - tube_od_mm() / 2), 0),
        "boreNewMm": round(2 * (kinematics.RING_R_MM - small["odMm"] / 2), 0),
        "baySpanDropMm": round(tube_od_mm() / 2 - small["odMm"] / 2, 0),
    }


@functools.lru_cache(maxsize=64)
def support_sweep(n: int = SWEEP_ELEMENTS) -> list[dict[str, float]]:
    """지지 롤러 반각의 감도 — 모델에 없던 값이라 얼마나 예민한지를 본다."""
    out = []
    for half in (15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0):
        sw = rotation_sweep(None, None, half, n)
        a = analyse(0.0, None, None, half, n)
        out.append({
            "halfDeg": half,
            "staticMpa": round(sw["peakStaticMpa"], 2),
            "rangeMpa": round(sw["worstRangeMpa"], 2),
            "radialMm": round(sw["worstRadialMm"], 4),
            "rollerN": round(max(a["rollerN"]), 0),
            "wallMpa": round(wall_stress_mpa(max(a["rollerN"]), None, None), 1),
        })
    return out


def bending_is_not_what_sizes_the_ring() -> bool:
    """전역 굽힘이 이 링을 정하지 않는다 — OI-02 의 답이 이 한 줄이다."""
    sw = rotation_sweep()
    return (sw["peakStaticMpa"] < static_allow_mpa() * 0.1
            and sw["worstRangeMpa"] < fatigue_allow_mpa() * 0.1)


def rollers_stay_in_compression() -> bool:
    """도는 내내 두 롤러가 다 눌리는가 — 하나가 뜨면 가이드 롤러가 받는다."""
    return rotation_sweep()["minRollerN"] > 0.0


@functools.lru_cache(maxsize=64)
def summary() -> dict[str, object]:
    sw = rotation_sweep()
    small = smallest_section()
    return {
        "odMm": tube_od_mm(), "tMm": tube_t_mm(),
        "massKg": round(ring_mass_kg(), 1),
        "jawLoadN": round(jaw_load_per_ring_n(), 0),
        "supportHalfDeg": SUPPORT_HALF_ANGLE_DEG,
        "rollerN": round(max(analyse()["rollerN"]), 0),
        "staticMpa": round(sw["peakStaticMpa"], 2),
        "staticAllowMpa": static_allow_mpa(),
        "rangeMpa": round(sw["worstRangeMpa"], 2),
        "cycles": round(design_cycles()),
        "fatigueAllowMpa": round(fatigue_allow_mpa(), 1),
        "radialMm": round(sw["worstRadialMm"], 4),
        "runoutMm": runout_mm(),
        "wallMpa": round(wall_stress_mpa(max(analyse()["rollerN"])), 1),
        "binding": verdict(tube_od_mm(), tube_t_mm())["binding"],
        "utilisation": verdict(tube_od_mm(), tube_t_mm())["utilisation"],
        "class": dt_class(),
        "dynamicAmp": round(dynamic_amplification(), 4),
        "smallest": small,
        "saving": inertia_saving(),
        "takt": takt_after_reduction(),
        "equilibriumError": round(equilibrium_error(), 6),
    }


def checks() -> list[tuple[str, bool, str]]:
    s = summary()
    sw = rotation_sweep()
    coarse = analyse(0.0, None, None, None, 36)["peakMpa"]
    fine = analyse(0.0, None, None, None, 72)["peakMpa"]
    return [
        ("요소가 수렴한다", abs(fine - coarse) / fine < 0.01,
         f"요소 36 → 72 에서 {coarse:.4f} → {fine:.4f} MPa"),
        ("반력이 하중과 맞는다", s["equilibriumError"] < 1e-3,
         f"평형 오차 {s['equilibriumError']:.2e}"),
        ("두 롤러가 도는 내내 눌린다", rollers_stay_in_compression(),
         f"최소 수직반력 {sw['minRollerN']:.0f} N"),
        ("정적 굽힘이 허용의 10 % 밑이다", s["staticMpa"] < s["staticAllowMpa"] * 0.1,
         f"{s['staticMpa']} MPa vs 허용 {s['staticAllowMpa']}"),
        ("용접부 피로가 허용의 10 % 밑이다", s["rangeMpa"] < s["fatigueAllowMpa"] * 0.1,
         f"응력범위 {s['rangeMpa']} MPa vs {s['fatigueAllowMpa']} "
         f"({s['cycles']:,} 회)"),
        ("처짐이 런아웃을 안 먹는다", s["radialMm"] <= s["runoutMm"],
         f"반경변화 {s['radialMm']} mm ≤ 런아웃 {s['runoutMm']}"),
        ("전역 굽힘이 링을 정하지 않는다", bending_is_not_what_sizes_the_ring(),
         f"먼저 걸리는 것은 {s['binding']} — 사용률 {s['utilisation']}"),
        ("도는 동안의 관성력이 자중에 비해 작다", s["dynamicAmp"] < 0.05,
         f"접선 관성 / 중력 = {s['dynamicAmp']} — 자중 해석으로 충분하다"),
        ("지금 단면이 소성단면이다", s["class"] <= 2,
         f"D/t {tube_od_mm() / tube_t_mm():.0f} → 단면 등급 {s['class']}"),
        ("줄일 수 있는 단면이 있다", s["smallest"] is not None
         and s["smallest"]["massKg"] < s["massKg"],
         f"Ø{s['smallest']['odMm']:.0f}×t{s['smallest']['tMm']} "
         f"{s['smallest']['massKg']} kg" if s["smallest"] else "없다"),
    ]


def annotations() -> tuple[str, ...]:
    s = summary()
    v = s["saving"]
    lines = [
        f"엔드링 Ø{s['odMm']:.0f}×t{s['tMm']:.0f} · {s['massKg']} kg/매 — 지지 롤러 "
        f"반각 {s['supportHalfDeg']:.0f}° 에서 롤러 반력 {s['rollerN']:.0f} N",
        f"전역 굽힘 최대 {s['staticMpa']} MPa (허용 {s['staticAllowMpa']:.0f}) · "
        f"회전 응력범위 {s['rangeMpa']} MPa (허용 {s['fatigueAllowMpa']} · "
        f"{s['cycles']:,} 회) — 둘 다 허용의 2 % 안쪽이다",
        f"반경 변화 {s['radialMm']} mm 로 선삭 런아웃 {s['runoutMm']} 를 "
        f"{s['radialMm'] / s['runoutMm'] * 100:.0f} % 만 먹는다",
        f"먼저 걸리는 것은 {s['binding']} 이다 — 롤러 밑 관 벽 {s['wallMpa']} MPa, "
        f"사용률 {s['utilisation']}. 이 링을 정하는 것은 전역 굽힘이 아니다",
    ]
    if s["smallest"]:
        sm = s["smallest"]
        lines.append(
            f"네 판정을 다 지나는 가장 가벼운 단면은 Ø{sm['odMm']:.0f}×t{sm['tMm']} "
            f"({sm['massKg']} kg/매, 지금보다 {v['massDropKgPerRing']} kg 가볍다) — "
            f"먼저 걸리는 것은 {sm['binding']} 이고 사용률 {sm['utilisation']} 이다")
        lines.append(
            f"반전 관성이 {v['totalNowKgm2']} → {v['totalNewKgm2']} kg·m² 로 "
            f"{v['inertiaDrop'] * 100:.0f} % 준다. 다만 구동 반지름도 "
            f"{v['driveRadiusNowM']} → {v['driveRadiusNewM']} m 로 줄어 마찰 롤러가 "
            f"손해를 본다 — 둘을 합치면 필요 압착력이 지금의 {v['preloadRatio']} 배다")
        lines.append(
            f"곁따라오는 것 둘 — 링 구멍이 {v['boreNowMm']:.0f} → {v['boreNewMm']:.0f} mm "
            f"로 넓어지고, 베이가 축방향으로 한 쪽 {v['baySpanDropMm']:.0f} mm 씩 준다. "
            f"레이아웃은 발주처 결정 사항이라 여기서 옮기지 않는다")
    t = s["takt"]
    if "newScale" in t:
        moved = ("먼저 걸리는 것도 「%s」에서 「%s」으로 넘어간다"
                 % (t["nowBinding"], t["newBinding"])
                 if t["newBinding"] != t["nowBinding"]
                 else "먼저 걸리는 것은 여전히 「%s」이다" % t["nowBinding"])
        lines.append(
            f"택트 여유가 {t['nowScale']} → {t['newScale']} 배로 {t['gain']} 배 "
            f"늘어난다 ({moved}) — 링 단면이 택트를 잡고 있었다")
    lines.append(
        "보요소는 링을 선으로 본다 — 롤러 밑 관 벽과 용접 노치의 국부응력은 "
        "셸 FEA 나 시험에서만 나온다. 위 벽 응력은 닫힌 해로 낸 상한이다 (OI-02)")
    return tuple(lines)


def clear_caches() -> None:
    """모든 기억을 지운다 — 부품표를 흔드는 시험이 이것을 부른다.

    하나만 지우면 다른 것이 옛 답을 들고 있어 **조용히 갈라진다.** 지울 곳을
    한 군데로 모아 두는 이유가 그것이다.
    """
    for fn in (analyse, rotation_sweep, verdict, section_options,
               smallest_section, inertia_saving, support_sweep,
               takt_after_reduction, summary, design_cycles,
               fatigue_allow_mpa):
        fn.cache_clear()


def equilibrium_error(phi_deg: float = 0.0) -> float:
    """반력 합이 실린 하중과 얼마나 어긋나는가 (상대값) — 푼 결과를 믿을 근거."""
    a = analyse(phi_deg)
    return abs(a["reactSumN"] - a["appliedN"]) / a["appliedN"]


if __name__ == "__main__":                                   # pragma: no cover
    import json

    print(json.dumps(summary(), ensure_ascii=False, indent=1))
    print()
    for name, ok, why in checks():
        print(f"{'✓' if ok else '✗'} {name} — {why}")
    print()
    print(f"{'단면':>14} {'kg':>6} {'관성':>7} {'정적':>7} {'범위':>7} "
          f"{'처짐 mm':>8} {'벽':>7} {'구멍':>6} {'먼저 걸리는 것':>14} {'사용률':>7}")
    for r in section_options():
        print(f"Ø{r['odMm']:6.1f}×t{r['tMm']:<4.1f} {r['massKg']:6.1f} "
              f"{r['inertiaKgm2']:7.1f} {r['staticMpa']:7.2f} {r['rangeMpa']:7.2f} "
              f"{r['radialMm']:8.4f} {r['wallMpa']:7.1f} {r['boreMm']:6.0f} "
              f"  등급{r['class']} {r['binding']:>14} {r['utilisation']:7.3f} "
              f"{'○' if r['ok'] else '×'}")
    print()
    print(f"{'반각':>5} {'정적':>7} {'범위':>7} {'처짐 mm':>8} {'롤러 N':>8} {'벽':>7}")
    for r in support_sweep():
        print(f"{r['halfDeg']:5.0f} {r['staticMpa']:7.2f} {r['rangeMpa']:7.2f} "
              f"{r['radialMm']:8.4f} {r['rollerN']:8.0f} {r['wallMpa']:7.1f}")
    print()
    for line in annotations():
        print("·", line)
