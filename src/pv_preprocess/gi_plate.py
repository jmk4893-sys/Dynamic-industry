# -*- coding: utf-8 -*-
"""GI-303 롤러 창 위의 패널 — **초점이 사는가**를 수치로 푸는 모델.

`gi_optics` 는 심도 5.8 mm 가 「통과 중 판 휨 3 mm」 를 덮는다고 했다. 그 3 mm 는
**가정**이었다. 이 모듈은 그 가정을 셋으로 갈라 각각을 계산하거나 출처를 댄다.

    처짐 = 자중 처짐 (계산) + 앞끝 외팔 (계산) + 롤러 흔들림 (카탈로그)
         + 동적 되튐 (계산) + **판 자체의 휨 (남는 몫 → 반입 조건)**

같은 해석이 **유리 깨짐** 패널에도 답한다. 캠페인은 깨진 유리를 그대로 태우고
(R-B 로 분류될 뿐 GBR-301 까지 같은 롤러를 탄다), 유리가 쪼개지면 라미네이트의
휨강성은 봉지층·백시트 몫만 남는다. 남은 유리 강성의 몫 κ 를 **지어내지 않고**,
처짐이 심도를 벗어나는 κ* 와 보호창을 치는 κ* 를 유한요소로 **푼다** — 실물
깨진 판이 어디에 있는지는 시험이 정한다.

푸는 것

  ① 단면 — 유리 3.2 / 봉지층 / 백시트 0.32 의 **변환단면** (유리면이 아래).
  ② 정적 — 롤러 꼭대기에 받쳐진 연속보 (`beam.py` 유한요소). 받침 사이는 창
     150 이 아니라 **피치 240** 이다. 앞끝이 창을 건널 때는 외팔보.
  ③ 모드 — 받쳐진 띠의 1차 고유진동수 대 롤러 통과·회전 가진.
  ④ 과도 — 앞끝이 다음 롤러에 얹히는 순간의 되튐 (Newmark-β).
  ⑤ 광학 결합 — 정확한 얇은렌즈 초점흐림 c(Δz) 와 이송 흐림 v·t_exp 를 합쳐
     **유효 화소**를 낸다. 아리스·실란트 띠가 몇 화소로 보이는가가 처짐의 함수다.

값의 출처: 층 두께·자중은 `afr`·`frames`·`sg_grind`, 광학·롤러는 `gi_optics`,
유한요소는 `beam`. 여기서 새로 정한 것은 폴리머 층의 탄성계수·유리 강도·롤러
흔들림 셋뿐이고 전부 카탈로그 계획값이다.

    PYTHONPATH=src python -c "from pv_preprocess import gi_plate; print(gi_plate.summary())"
"""

from __future__ import annotations

import functools
import math

from . import afr, beam, frames, gi_optics, sg_grind
from .afr_units import Part, Unit

# ── 층 구성 — 다른 모듈이 정한 것 ──────────────────────────────────────
#: 유리 두께 (mm)·탄성계수 (MPa) — `afr` 가 정본.
GLASS_T_MM = float(afr.LAMINATE_T_MM)
GLASS_E_MPA = float(afr.GLASS_E_MPA)
#: 라미네이트 전체 두께 (mm) — `frames` 가 정본.
STACK_T_MM = float(frames.LAMINATE_STACK_MM)
#: 백시트 두께 (mm) — `sg_grind` 가 정본.
BACKSHEET_T_MM = float(sg_grind.BACKSHEET_T_MM)
#: 면적당 질량 (kg/m²) — `afr` 가 정본. 자중은 여기서만 나온다.
AREAL_KG_M2 = float(afr.LAMINATE_KG_M2)

# ── 여기서 정한 카탈로그 계획값 ─────────────────────────────────────────
#: 백시트 (PET 계) 탄성계수 (MPa).
BACKSHEET_E_MPA = 3_000.0
#: 봉지층 (EVA + 셀) 탄성계수 (MPa) — 셀은 깨진 조각이라 강성에 안 넣는다.
ENCAP_E_MPA = 10.0
#: 판유리 굽힘강도 (MPa) — 처짐 응력이 이보다 작아야 판이 롤러 위에서 안 깨진다.
GLASS_STRENGTH_MPA = 45.0
#: 롤러 원주 흔들림 TIR (mm) — 가공 컨베이어 롤러의 통상 공차.
ROLLER_RUNOUT_MM = 0.10
#: 라미네이트 감쇠비 — 봉지층이 폴리머라 강재보다 크다.
DAMPING_RATIO = 0.05

# ── 유한요소 이산화 ─────────────────────────────────────────────────────
#: 요소 길이 (mm). 피치 240 과 창 150 이 모두 나눠떨어져 절점이 롤러·창에 앉는다.
EL_MM = 30.0
#: 정적·모드 해석에 세우는 스팬 수 — 가운데 스팬이 창이고 양옆이 연속성을 준다.
SPANS = 5
#: 앞끝 외팔 해석에서 뒤에 남는 스팬 수 — 2 에서 6 까지 끝 처짐이 2 % 안에서 수렴한다.
ENTRY_SPANS = 3
#: 스캔선 자리 — 창 가운데, 곧 롤러 접촉선에서 피치의 절반 (mm).
SCAN_FROM_ROLLER_MM = 120.0
#: 얹힘 해석에서 롤러를 대신하는 끝 스프링의 배율 — 외팔 끝 강성의 몇 배인가.
#: 재료 상수가 아니라 「굳은 롤러」를 흉내내는 수치 장치다. 100 이면 끝이 램프를
#: 1 % 안에서 따라가고, 그 모드가 1차의 10 배라 걸음 폭 안에 든다.
TIP_SPRING_FACTOR = 100.0

# ── 이송·롤러 — `gi_optics` 가 정본 ─────────────────────────────────────
PITCH_MM = float(gi_optics.ROLLER_PITCH_MM)
ROLLER_D_MM = float(gi_optics.ROLLER_D_MM)
TRANSPORT_MM_S = float(gi_optics.TRANSPORT_MM_S)


# ── ① 단면 ──────────────────────────────────────────────────────────────
def encap_t_mm() -> float:
    """봉지층 두께 (mm) — 전체에서 유리와 백시트를 뺀 나머지."""
    return round(STACK_T_MM - GLASS_T_MM - BACKSHEET_T_MM, 4)


def layers(glass_share: float = 1.0) -> tuple[tuple[str, float, float, float], ...]:
    """(이름, 두께, 탄성계수, 아랫면 y) — 유리면이 아래 (y = 0) 다.

    `glass_share` 는 남은 유리 강성의 몫이다. 1 은 성한 유리, 0 은 완전히
    쪼개져 조각이 강성을 하나도 안 내는 경우다. 질량은 그대로다 — 조각도 무겁다.
    """
    e_glass = GLASS_E_MPA * glass_share
    return (
        ("유리", GLASS_T_MM, e_glass, 0.0),
        ("봉지층", encap_t_mm(), ENCAP_E_MPA, GLASS_T_MM),
        ("백시트", BACKSHEET_T_MM, BACKSHEET_E_MPA, GLASS_T_MM + encap_t_mm()),
    )


def transformed_section(glass_share: float = 1.0) -> dict[str, float]:
    """폭 1 mm 띠의 변환단면 — 기준 탄성계수는 성한 유리다.

    층마다 E_i/E_유리 만큼 폭을 늘려 한 재료로 본다. 중립축은 그 가중 도심이고
    EI 는 각 층의 자기 관성 + 평행축 항의 합이다.
    """
    ls = layers(glass_share)
    ea = sum(t * e for _, t, e, _ in ls)
    if ea <= 0.0:
        raise ValueError("강성이 0 인 단면")
    na = sum(t * e * (y0 + t / 2.0) for _, t, e, y0 in ls) / ea
    ei = sum(e * (t ** 3 / 12.0 + t * (y0 + t / 2.0 - na) ** 2) for _, t, e, y0 in ls)
    return {"ei_n_mm2": ei, "na_mm": na, "ea_n": ea,
            "i_glass_eq_mm4": ei / GLASS_E_MPA}


def ei_n_mm2(glass_share: float = 1.0) -> float:
    """폭 1 mm 띠의 휨강성 (N·mm²)."""
    return transformed_section(glass_share)["ei_n_mm2"]


def polymer_share_of_stiffness() -> float:
    """성한 판에서 폴리머 층이 내는 휨강성의 몫 — 유리가 거의 전부다."""
    return round(ei_n_mm2(0.0) / ei_n_mm2(1.0), 5)


def agrees_with_the_glass_only_strip() -> bool:
    """`afr` 의 유리 단독 띠(t³/12)와 몇 % 안에서 같은가 — 두 모델이 한 판이다."""
    glass_only = GLASS_E_MPA * afr.laminate_strip_i_mm4()
    return abs(ei_n_mm2(1.0) / glass_only - 1.0) < 0.10


def line_load_n_mm() -> float:
    """폭 1 mm 띠의 자중 (N/mm) — `afr.laminate_line_load_n_per_mm()` 과 같다."""
    return AREAL_KG_M2 * 9.81 / 1e6


def section(glass_share: float = 1.0) -> beam.Section:
    """유한요소용 단면 — 폭 1 mm 띠. 응력 기준면은 유리 아랫면(인장면)이다."""
    t = transformed_section(glass_share)
    area = STACK_T_MM                                   # mm² per mm width
    density = AREAL_KG_M2 * 1e-9 / area                 # tonne/mm³ — 선질량이 자중과 맞게
    return beam.Section(GLASS_E_MPA, t["i_glass_eq_mm4"], area, t["na_mm"],
                        density, GLASS_STRENGTH_MPA)


# ── ② 정적 — 롤러 위의 연속보 ───────────────────────────────────────────
def support_span_mm() -> float:
    """받침 사이 거리 (mm) — 롤러 꼭대기 접촉선 사이, 곧 피치다."""
    return PITCH_MM


def scan_offset_elements() -> int:
    n = SCAN_FROM_ROLLER_MM / EL_MM
    if abs(n - round(n)) > 1e-9:
        raise SystemExit("요소 길이가 스캔선 자리를 나누지 못한다")
    return int(round(n))


def elements_per_span() -> int:
    n = PITCH_MM / EL_MM
    if abs(n - round(n)) > 1e-9:
        raise SystemExit("요소 길이가 피치를 나누지 못한다")
    return int(round(n))


def strip(glass_share: float = 1.0, spans: int = SPANS,
          overhang_mm: float = 0.0) -> tuple[beam.Beam, tuple[int, ...]]:
    """롤러 위의 띠와 롤러가 앉는 절점 — 앞끝 외팔은 `overhang_mm` 로 낸다."""
    per = elements_per_span()
    n_over = overhang_mm / EL_MM
    if abs(n_over - round(n_over)) > 1e-9:
        raise SystemExit("요소 길이가 외팔 길이를 나누지 못한다")
    n_el = spans * per + int(round(n_over))
    b = beam.Beam(section(glass_share), n_el * EL_MM, n_el)
    rollers = tuple(i * per for i in range(spans + 1))
    return b, rollers


def _roller_dofs(rollers: tuple[int, ...]) -> dict[int, float]:
    return {node * beam.DOF_PER_NODE: 0.0 for node in rollers}


def sag_profile(glass_share: float = 1.0) -> tuple[tuple[float, float], ...]:
    """(x mm, 처짐 mm — 아래가 양수) 롤러 위 띠의 자중 처짐. 가운데 스팬이 창이다."""
    b, rollers = strip(glass_share)
    u = b.solve_static(prescribed=_roller_dofs(rollers), udl_n_mm=-line_load_n_mm())
    return tuple((b.x(i), -w) for i, w in enumerate(b.deflection(u)))


@functools.lru_cache(maxsize=None)
def window_sag_mm(glass_share: float = 1.0) -> float:
    """창 가운데의 자중 처짐 (mm) — 연속보라 단순지지보다 작다."""
    b, rollers = strip(glass_share)
    u = b.solve_static(prescribed=_roller_dofs(rollers), udl_n_mm=-line_load_n_mm())
    mid = rollers[len(rollers) // 2 - 1], rollers[len(rollers) // 2]
    w = b.deflection(u)
    return max(-w[i] for i in range(mid[0], mid[1] + 1))


def simply_supported_sag_mm(glass_share: float = 1.0) -> float:
    """단순지지 한 스팬이면 (5wL⁴/384EI) — 연속보 값의 상한이자 닫힌해 대조."""
    L = support_span_mm()
    return 5.0 * line_load_n_mm() * L ** 4 / (384.0 * ei_n_mm2(glass_share))


def continuity_factor() -> float:
    """연속보 처짐 ÷ 단순지지 처짐 — 이웃 스팬이 얼마나 붙잡아 주는가."""
    return round(window_sag_mm() / simply_supported_sag_mm(), 4)


def window_stress_mpa() -> float:
    """롤러 위 유리 아랫면의 굽힘응력 (MPa) — 받침 위가 최대다."""
    b, rollers = strip()
    u = b.solve_static(prescribed=_roller_dofs(rollers), udl_n_mm=-line_load_n_mm())
    return round(b.max_stress_mpa(u), 4)


def glass_survives_the_rollers() -> bool:
    return window_stress_mpa() < GLASS_STRENGTH_MPA


def entry_reach_mm() -> float:
    """앞끝이 다음 롤러에 닿기 직전의 외팔 길이 (mm) — 받침 사이 거리다."""
    return support_span_mm()


def entry_sag_mm(glass_share: float = 1.0, reach_mm: float | None = None) -> float:
    """앞끝이 창을 건너는 동안의 **끝** 처짐 (mm) — 뒤 롤러들이 붙잡은 외팔보.

    끝은 다음 롤러에 부딪히는 자리라 얹힘 해석이 쓴다. 초점이 보는 것은 끝이
    아니라 스캔선이다 — 그쪽은 `entry_scan_sag_mm` 이다.
    """
    reach = entry_reach_mm() if reach_mm is None else reach_mm
    b, rollers = strip(glass_share, ENTRY_SPANS, reach)
    u = b.solve_static(prescribed=_roller_dofs(rollers), udl_n_mm=-line_load_n_mm())
    return -b.deflection(u)[-1]


@functools.lru_cache(maxsize=None)
def entry_scan_sweep(glass_share: float = 1.0) -> tuple[tuple[float, float], ...]:
    """(외팔 길이 mm, 스캔선 처짐 mm) — 앞끝이 스캔선을 지나 다음 롤러에 닿기까지.

    스캔선은 롤러에서 `SCAN_FROM_ROLLER_MM` 앞에 있다. 앞끝이 거기 오기 전에는
    볼 것이 없고, 지나서 다음 롤러에 닿을 때(외팔 = 피치)까지 처짐이 자란다.
    """
    out = []
    reach = SCAN_FROM_ROLLER_MM
    node_off = scan_offset_elements()
    while reach <= entry_reach_mm() + 1e-9:
        b, rollers = strip(glass_share, ENTRY_SPANS, reach)
        u = b.solve_static(prescribed=_roller_dofs(rollers), udl_n_mm=-line_load_n_mm())
        out.append((reach, -b.deflection(u)[rollers[-1] + node_off]))
        reach += EL_MM
    return tuple(out)


def entry_scan_sag_mm(glass_share: float = 1.0) -> float:
    """앞끝이 지나가는 동안 **스캔선이 보는** 최대 처짐 (mm) — 예산에 드는 값."""
    return max(w for _, w in entry_scan_sweep(glass_share))


def cantilever_closed_form_mm(reach_mm: float) -> float:
    """외팔보 자중 처짐 wL⁴/8EI — 뒤가 고정단이면 이 값이다 (하한).

    롤러 위의 판은 뒤가 고정단이 아니라 회전한다 — 그래서 실제는 이보다 크다.
    """
    return line_load_n_mm() * reach_mm ** 4 / (8.0 * ei_n_mm2())


# ── ③ 모드 — 받쳐진 띠의 고유진동수 대 롤러 가진 ──────────────────────
def fundamental_hz(glass_share: float = 1.0) -> float:
    """롤러에 받쳐진 띠의 1차 고유진동수 (Hz)."""
    b, rollers = strip(glass_share)
    return b.fundamental_hz(tuple(_roller_dofs(rollers)))


def pinned_span_closed_form_hz() -> float:
    """단순지지 한 스팬의 1차 f = (π/2L²)√(EI/ρA) — 연속보의 최저 모드가 이것이다."""
    sec = section()
    L = support_span_mm()
    return (math.pi / (2.0 * L * L)) * math.sqrt(sec.ei / sec.rho_a)


def roller_pass_hz() -> float:
    """롤러를 하나 지나는 주기 — 피치 가진 (Hz)."""
    return TRANSPORT_MM_S / PITCH_MM


def roller_spin_hz() -> float:
    """롤러 자전 (Hz) — 흔들림이 이 주기로 판을 든다. 미끄럼 없이 ω = v/r."""
    return TRANSPORT_MM_S / (math.pi * ROLLER_D_MM)


def forcing_hz() -> float:
    """가진 중 높은 쪽 (Hz)."""
    return max(roller_pass_hz(), roller_spin_hz())


def frequency_ratio() -> float:
    """고유진동수 ÷ 가진 — 이 비가 크면 판은 롤러를 **준정적으로** 따라간다."""
    return round(fundamental_hz() / forcing_hz(), 1)


def runout_amplification() -> float:
    """롤러 흔들림에 대한 동적 배율 1/|1−r²|, r = 가진/고유 — 1 에 가까우면 그냥 따라간다."""
    r = forcing_hz() / fundamental_hz()
    return round(1.0 / abs(1.0 - r * r), 6)


def rides_the_rollers_quasi_statically() -> bool:
    """배율이 1 % 안이면 흔들림을 정적 항으로 더해도 된다."""
    return abs(runout_amplification() - 1.0) < 0.01


def runout_sag_mm() -> float:
    """롤러 흔들림이 판에 주는 높이 변화 (mm) — TIR 에 동적 배율을 곱한 값."""
    return round(ROLLER_RUNOUT_MM * runout_amplification(), 4)


# ── ④ 과도 — 앞끝이 다음 롤러에 얹히는 순간 ─────────────────────────────
class _CaughtStrip(beam.Beam):
    """끝에 스프링이 달린 띠 — 롤러가 받쳐 주는 것을 **움직이는 바닥**으로 본다."""

    def __init__(self, section: beam.Section, length_mm: float, elements: int,
                 tip_k_n_mm: float) -> None:
        super().__init__(section, length_mm, elements)
        self.tip_k = tip_k_n_mm

    def stiffness(self) -> list[list[float]]:
        k = super().stiffness()
        dof = (self.n_node - 1) * beam.DOF_PER_NODE
        k[dof][dof] += self.tip_k
        return k


def landing_lift_mm() -> float:
    """앞끝이 롤러 옆면에 처음 닿는 자리에서 꼭대기까지 오르는 높이 — 곧 끝 처짐."""
    return entry_sag_mm()


def landing_approach_mm() -> float:
    """끝이 롤러 원호에 닿는 자리에서 꼭대기까지의 수평 거리 (mm) — x = √(2Rδ)."""
    return math.sqrt(2.0 * ROLLER_D_MM / 2.0 * landing_lift_mm())


def landing_ramp_s() -> float:
    """끝이 원호를 타고 꼭대기까지 들려 올라가는 시간 (s) — 계단이 아니라 램프다.

    처져 있던 끝은 롤러 **꼭대기**가 아니라 그 앞 옆면에 먼저 닿는다. 원호 위에서
    처짐 깊이만큼 되돌아간 자리다. 거기서 꼭대기까지 이송이 끌어올리므로, 끝은
    그 거리를 가는 시간 동안 램프로 올라간다.
    """
    return landing_approach_mm() / TRANSPORT_MM_S


def landing_ramp_in_periods() -> float:
    """램프가 1차 주기의 몇 배인가 — 1 을 넘으면 되튐이 계단 충격보다 훨씬 작다."""
    return round(landing_ramp_s() * fundamental_hz(), 2)


@functools.lru_cache(maxsize=None)
def landing_transient(steps: int = 360, cycles: float = 6.0
                      ) -> tuple[tuple[float, float], ...]:
    """(t s, 스캔선 처짐 mm — 초점면 기준, 아래 양수) 앞끝이 롤러에 얹히면서.

    외팔로 처져 있던 앞끝 밑에서 롤러 옆면이 램프로 올라와 끝을 꼭대기까지
    든다. 끝의 스프링은 재료가 아니라 「굳은 롤러」를 흉내내는 수치 장치이고,
    바닥이 움직이는 것은 힘 k·y_r(t) 로 들어간다. 하중이 도착 시각에서 읽히므로
    (`beam.newmark`) 램프가 한 걸음 밀리지 않는다.
    """
    reach = entry_reach_mm()
    per = elements_per_span()
    n_el = ENTRY_SPANS * per + int(round(reach / EL_MM))
    tip_k = TIP_SPRING_FACTOR * 3.0 * ei_n_mm2() / reach ** 3
    b = _CaughtStrip(section(), n_el * EL_MM, n_el, tip_k)
    rollers = tuple(i * per for i in range(ENTRY_SPANS + 1))
    pre = _roller_dofs(rollers)
    tip = (b.n_node - 1) * beam.DOF_PER_NODE
    lift = landing_lift_mm()
    # 초기 자세: 바닥이 끝 처짐 자리에 있어 스프링이 힘을 안 낸다 — 정적 외팔.
    w = b.udl_vector(-line_load_n_mm())
    f0 = w[:]
    f0[tip] += tip_k * (-lift)
    u0 = b.solve_static(loads={tip: tip_k * (-lift)}, prescribed=pre,
                        udl_n_mm=-line_load_n_mm())
    f1 = b.fundamental_hz(tuple(pre))
    ramp = landing_ramp_s()
    dt = (ramp + cycles / f1) / steps

    def force(step: int, t: float) -> list[float]:
        y_r = -lift * (1.0 - min(1.0, t / ramp))     # 바닥이 −lift 에서 0 으로 오른다
        f = w[:]
        f[tip] += tip_k * y_r
        return f

    hist = beam.newmark(b, steps, dt, force, prescribed=pre,
                        damping_ratio=DAMPING_RATIO, u0=u0)
    scan = (rollers[-1] + scan_offset_elements()) * beam.DOF_PER_NODE
    return tuple((round(i * dt, 6), -h[scan]) for i, h in enumerate(hist))


def landing_excursion_mm() -> float:
    """얹히는 동안 스캔선이 초점면에서 벗어나는 최대 (mm) — 위아래 다 잰다."""
    return max(abs(w) for _, w in landing_transient())


def landing_overshoot_mm() -> float:
    """정적 자리(연속보 처짐)를 지나쳐 되튀는 크기 (mm) — 램프라 작다."""
    rest = window_sag_mm()
    return max(rest - w for _, w in landing_transient())


def landing_settles_within_s() -> float:
    """되튐이 흔들림 공차의 1/10 안으로 잦아드는 시각 (s) — 램프 시작부터."""
    hist = landing_transient()
    rest = window_sag_mm()
    tol = ROLLER_RUNOUT_MM / 10.0
    last = 0.0
    for t, w in hist:
        if abs(w - rest) > tol:
            last = t
    return round(last, 4)


def scan_line_dwell_s() -> float:
    """창 가운데가 한 롤러 피치를 지나는 시간 (s) — 되튐이 이 안에 잦아들어야 한다."""
    return PITCH_MM / TRANSPORT_MM_S


def landing_is_quiet_before_the_scan() -> bool:
    return landing_settles_within_s() < scan_line_dwell_s()


# ── ⑤ 광학 결합 — 처짐이 화소가 되기까지 ──────────────────────────────
def cameras() -> int:
    return gi_optics.cameras_below()


def defocus_blur_mm(dz_mm: float, cams: int | None = None) -> float:
    """물체면 흐림원 지름 (mm) — 정확한 얇은렌즈. 초점면에서 Δz 벗어난 자리.

    u = f(1+1/m) 에 초점을 맞춘 렌즈가 u+Δz 의 점을 v' 에 맺는다. 센서는 v 에
    있으니 지름 D = f/N 의 원뿔이 |v−v'| 만큼 못 미쳐 지름 D·|v−v'|/v' 로
    퍼진다. 그것을 배율로 나누면 물체면에서의 흐림이다. Δz → 0 에서
    m·Δz/(N(1+m)) 로 가고, `gi_optics.depth_of_field_mm` 의 2Nc(1+m)/m² 와 같은
    식이다 — 심도 끝에서 흐림이 정확히 c/m 이 되는지를 시험이 본다.
    """
    n = cams or cameras()
    f, N = gi_optics.LENS_F_MM, gi_optics.F_NUMBER
    m = gi_optics.magnification(n)
    u = f * (1.0 + 1.0 / m)
    v = f * (1.0 + m)
    uu = u + dz_mm
    if uu <= f:
        return float("inf")
    vv = 1.0 / (1.0 / f - 1.0 / uu)
    return (f / N) * abs(v - vv) / vv / m


def blur_at_dof_edge_is_the_criterion() -> bool:
    """심도 끝(±DOF/2)에서 흐림이 c/m 인가 — 두 식이 한 광학인지."""
    n = cameras()
    want = gi_optics.CIRCLE_OF_CONFUSION_MM / gi_optics.magnification(n)
    got = defocus_blur_mm(gi_optics.depth_of_field_mm(n) / 2.0, n)
    return abs(got / want - 1.0) < 0.03


def motion_blur_mm() -> float:
    """이송 흐림 (mm) — 노광 동안 판이 가는 거리. 이송 방향에만 든다."""
    return round(TRANSPORT_MM_S * gi_optics.exposure_us() * 1e-6, 5)


def motion_blur_px() -> float:
    return round(motion_blur_mm() / gi_optics.RESOLUTION_MM, 3)


def effective_pixel_mm(dz_mm: float = 0.0, along: bool = True) -> float:
    """유효 화소 (mm) — 화소·초점흐림·이송흐림을 제곱합으로 합친다."""
    px = gi_optics.RESOLUTION_MM
    terms = [px * px, defocus_blur_mm(dz_mm) ** 2]
    if along:
        terms.append(motion_blur_mm() ** 2)
    return math.sqrt(sum(terms))


def feature_px(size_mm: float, dz_mm: float = 0.0, along: bool = True) -> float:
    """어떤 결함이 몇 유효 화소로 보이는가."""
    return round(size_mm / effective_pixel_mm(dz_mm, along), 2)


def arris_px(dz_mm: float = 0.0, along: bool = True) -> float:
    return feature_px(float(sg_grind.ARRIS_MM), dz_mm, along)


def arris_is_measurable(dz_mm: float = 0.0) -> bool:
    """아리스가 이송·교차 양쪽에서 확실판정 화소 수 이상인가."""
    k = gi_optics.PIXELS_PER_FEATURE
    return arris_px(dz_mm, True) >= k and arris_px(dz_mm, False) >= k


def smallest_feature_mm(dz_mm: float = 0.0, along: bool = True) -> float:
    return round(gi_optics.PIXELS_PER_FEATURE * effective_pixel_mm(dz_mm, along), 3)


def motion_blur_costs_more_than_sag() -> bool:
    """이송 흐림이 자중 처짐의 초점흐림보다 큰가 — 어느 쪽이 화질을 정하는가."""
    return motion_blur_mm() > defocus_blur_mm(window_sag_mm())


# ── 예산 — 3 mm 는 어디로 가는가 ────────────────────────────────────────
def transient_envelope_mm() -> float:
    """앞끝이 지나가고 얹히는 **한 사건** 동안 스캔선이 초점면에서 벗어나는 최대 (mm).

    앞끝 처짐과 얹힘 되튐은 더하는 것이 아니다 — 같은 사건의 앞뒤라 둘 중 큰
    쪽이 포락선이다. 정상 자중 처짐은 그 안에 이미 들어 있다.
    """
    return max(entry_scan_sag_mm(), landing_excursion_mm(), window_sag_mm())


def sag_budget_mm() -> dict[str, float]:
    """`gi_optics.PANEL_BOW_MM` 를 항목으로 가른다 — 남는 몫이 판 자체의 휨이다.

    자중·앞끝·되튐은 한 포락선으로 들어가고(더하지 않는다), 롤러 흔들림은 그 위에
    더한다. 남는 것이 판이 스스로 휘어 있어도 되는 몫 — 반입 조건이다.
    """
    gravity = window_sag_mm()
    entry = entry_scan_sag_mm()
    landing = landing_excursion_mm()
    envelope = max(gravity, entry, landing)
    runout = runout_sag_mm()
    return {
        "allowance": float(gi_optics.PANEL_BOW_MM),
        "gravity": round(gravity, 4),
        "entry": round(entry, 4),
        "landing": round(landing, 4),
        "envelope": round(envelope, 4),
        "runout": round(runout, 4),
        "warp": round(float(gi_optics.PANEL_BOW_MM) - envelope - runout, 3),
    }


def warp_allowance_mm() -> float:
    """중고 패널이 이보다 평평해야 한다 (mm) — 가정이 아니라 **반입 조건**이 된다."""
    return sag_budget_mm()["warp"]


def budget_is_flatness_not_gravity() -> bool:
    """예산의 대부분이 판 휨에 남는가 — 자중·앞끝·되튐은 문제가 아니라는 뜻."""
    b = sag_budget_mm()
    return b["warp"] / b["allowance"] > 0.8


def budget_fits_the_depth_of_field() -> bool:
    return sag_budget_mm()["allowance"] <= gi_optics.depth_of_field_mm(cameras())


# ── 유리 깨짐 — 남은 강성의 문턱 ────────────────────────────────────────
def cover_gap_mm() -> float:
    """판 밑면에서 보호창까지 (mm) — `gi_optics` 형상과 같은 값."""
    return float(gi_optics.COVER_GAP_MM)


def dof_half_mm() -> float:
    return gi_optics.depth_of_field_mm(cameras()) / 2.0


def _share_where_sag_is(target_mm: float) -> float:
    """창 처짐이 `target_mm` 이 되는 유리 강성 몫 — 이분법. 처짐은 κ 에 단조감소다.

    변환단면은 층이 평면을 유지한 채 함께 휜다고 본다(전단 결합). 그래서 강성이
    거의 없는 유리층도 두꺼워서 백시트와 멀리 떨어진 만큼 평행축 항으로 샌드위치
    강성을 낸다 — 문턱 κ* 가 작게 나오는 이유다. 조각난 유리가 봉지층을 통해 그
    전단을 실제로 전하는지는 이 모델이 답하지 못한다. 폴리머만 남는 κ = 0 이
    비관 쪽 한계다.
    """
    if window_sag_mm(1.0) >= target_mm:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if window_sag_mm(mid) > target_mm:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-7:
            break
    return 0.5 * (lo + hi)


def glass_share_for_focus() -> float:
    """이보다 유리 강성이 남으면 처짐이 심도 안이다."""
    return round(_share_where_sag_is(dof_half_mm()), 5)


def glass_share_for_cover() -> float:
    """이보다 유리 강성이 남으면 보호창을 안 친다."""
    return round(_share_where_sag_is(cover_gap_mm()), 5)


def a_fully_crazed_panel_hits_the_cover() -> bool:
    """유리가 강성을 하나도 안 내면 보호창을 치는가."""
    return window_sag_mm(0.0) > cover_gap_mm()


def a_cracked_panel_still_focuses() -> bool:
    """유리 강성이 **거의 다** 남아야 하는 것이 아니다 — 문턱이 몇 % 면 균열 몇 줄은 괜찮다."""
    return glass_share_for_focus() < 0.05


# ── 브라우저 물리엔진이 받는 상수 ──────────────────────────────────────
def physics_si() -> dict[str, float]:
    """XPBD 가 받는 SI 상수 — 폭 1 m 띠 기준. m·kg·s·N."""
    n = cameras()
    return {
        "ei": round(ei_n_mm2(1.0) * 1e-6 * 1e3, 4),         # N·m² per m width
        "eiPolymer": round(ei_n_mm2(0.0) * 1e-6 * 1e3, 6),
        "rhoA": AREAL_KG_M2,                                  # kg/m per m width
        "pitchM": PITCH_MM / 1000.0,
        "rollerRM": ROLLER_D_MM / 2000.0,
        "windowM": gi_optics.roller_window_mm() / 1000.0,
        "coverGapM": cover_gap_mm() / 1000.0,
        "dofM": gi_optics.depth_of_field_mm(n) / 1000.0,
        "bowM": float(gi_optics.PANEL_BOW_MM) / 1000.0,
        "transportMS": TRANSPORT_MM_S / 1000.0,
        "runoutM": ROLLER_RUNOUT_MM / 1000.0,
        "spinHz": round(roller_spin_hz(), 4),
        "magnification": gi_optics.magnification(n),
        "fNumber": float(gi_optics.F_NUMBER),
        "lensFM": gi_optics.LENS_F_MM / 1000.0,
        "exposureS": round(gi_optics.exposure_us() * 1e-6, 9),
        "pixelM": gi_optics.RESOLUTION_MM / 1000.0,
        "sagIntactM": round(window_sag_mm() / 1000.0, 9),
        "sagFocusM": round(window_sag_mm(glass_share_for_focus()) / 1000.0, 7),
        "entryScanSagM": round(entry_scan_sag_mm() / 1000.0, 7),
        "shareFocus": glass_share_for_focus(),
        "shareCover": glass_share_for_cover(),
        "f1Hz": round(fundamental_hz(), 2),
        "damping": DAMPING_RATIO,
        # 화면이 띠를 세우는 데 쓰는 것 — 형상은 여기서만 나온다
        "nodes": STRIP_NODES,
        "segM": EL_MM / 1000.0,
        "stripLenM": strip_length_mm() / 1000.0,
        "drawnWM": DRAWN_STRIP_W_MM / 1000.0,
        "stackM": STACK_T_MM / 1000.0,
        "rollerZM": [round(z / 1000.0, 4) for z in drawn_roller_z_mm()],
        "mag": PHYSICS_MAG,
        "substeps": SUBSTEPS,
        "iterations": ITERATIONS,
        "eiTable": ei_table_si(),
    }


# ── 브라우저 물리 유닛의 형상 ───────────────────────────────────────────
#: 물리 유닛의 배율 — 창 확대도와 같다. 심도 5.8 이 화면에서 보여야 한다.
PHYSICS_MAG = float(gi_optics.WINDOW_MAG)
#: 화면에 세우는 롤러 수 — 가운데 스팬이 창이고 양옆 두 스팬씩이 판을 받친다.
DRAWN_ROLLERS = 6
#: XPBD 띠의 마디 수 — 요소 길이가 유한요소와 같고, 길이가 정확히 다섯 스팬이라
#: 양끝을 롤러에 앉히면 유한요소의 `window_sag_mm` 과 **같은 형상**이 된다.
STRIP_NODES = SPANS * int(PITCH_MM / EL_MM) + 1
#: 화면에 그리는 띠의 폭 (mm) — 모델은 폭 1 mm 띠고, 보이라고 이만큼 잘라 그린다.
DRAWN_STRIP_W_MM = 300.0
#: 한 프레임의 서브스텝·반복. XPBD 는 반복이 아니라 **서브스텝**으로 수렴한다 —
#: 한 서브스텝에 중력이 떨어뜨리는 g·h² 가 평형 처짐보다 작아야 한다. 8 서브스텝이면
#: 43 µm 를 떨어뜨리는데 성한 판의 평형은 5.5 µm 라 35 배 무른 판이 됐다.
#: 128 서브스텝이면 성한 판이 6.6 µm (유한요소 5.5), 64 면 11.6 — 둘 다 심도의 0.4 %
#: 아래지만 「같은 판」이라 말하려면 굳은 쪽에서도 자릿수가 맞아야 한다.
#:
#: 수렴한 뒤에도 XPBD 는 유한요소보다 **9 % 무르다** (κ = 0.01 · κ_focus 에서 같은 비).
#: 30 mm 마디의 2차 차분 곡률이 Hermite 요소보다 굽힘을 조금 덜 세는 이산화 편향이고,
#: 서브스텝을 늘려도 안 변한다 — 브라우저 검사가 그 폭 안에서 둘을 견준다.
SUBSTEPS = 128
ITERATIONS = 4


def strip_length_mm() -> float:
    """XPBD 띠 길이 (mm) — 마디 간격이 유한요소 요소 길이와 같다."""
    return (STRIP_NODES - 1) * EL_MM


def drawn_roller_z_mm() -> tuple[float, ...]:
    """화면에 세우는 롤러의 z (mm) — 창이 z = 0 에 오도록 반 피치씩 어긋난다."""
    half = DRAWN_ROLLERS / 2.0
    return tuple((k - half + 0.5) * PITCH_MM for k in range(DRAWN_ROLLERS))


def physics_unit() -> Unit:
    """롤러 위의 판 — 브라우저가 XPBD 로 실시간 적분한다.

    여기 부품은 서 있는 것들뿐이다. 띠는 화면이 `physics_si()` 로 만든다 —
    자리·질량·강성이 전부 모델값이고 화면에 손으로 쓴 수가 없다.
    """
    mag, n = PHYSICS_MAG, cameras()
    d = ROLLER_D_MM * mag
    parts: list[Part] = []
    for i, z in enumerate(drawn_roller_z_mm()):
        parts.append(Part(
            f"phrl{i}", "CV-102 이송롤러", 1, "cyl",
            (d, DRAWN_STRIP_W_MM * mag + 200.0, d), (0.0, -d / 2.0, z * mag),
            "우레탄 피복 강관", axis="x",
            role=f"피치 {PITCH_MM:.0f} 로 판을 꼭대기 한 줄씩 받친다. 흔들림 "
                 f"{ROLLER_RUNOUT_MM} mm 가 자전 {roller_spin_hz():.2f} Hz 로 판을 든다 — "
                 f"판의 1차 {fundamental_hz():.0f} Hz 가 그 {frequency_ratio():.0f} 배라 "
                 "판은 롤러를 준정적으로 따라간다.",
            color="dark", explode=(0.0, -160.0, 0.0),
            spec=f"Ø{ROLLER_D_MM:.0f} · 피치 {PITCH_MM:.0f} · TIR {ROLLER_RUNOUT_MM}",
            catalog="CV-102-RL"))
    dof = gi_optics.depth_of_field_mm(n)
    parts.append(Part(
        "phdof", "심도 포락선", 1, "box",
        (DRAWN_STRIP_W_MM * mag + 400.0, dof * mag, RESOLUTION_DRAW_MM * mag),
        (0.0, 0.0, 0.0), "—",
        role=f"초점면 ±{dof / 2:.1f} mm — 판 밑면이 이 안에 있으면 흐림이 화소 두 개 "
             f"아래다. 성한 판은 {window_sag_mm() * 1000:.0f} µm 밖에 안 처져 한가운데 있다.",
        color="cyan", explode=(0.0, 0.0, 0.0),
        spec=f"DOF {dof} mm · 자중 처짐 {window_sag_mm():.4f} mm"))
    parts.append(Part(
        "phline", "스캔선", 1, "box",
        (DRAWN_STRIP_W_MM * mag + 400.0, 2.0, gi_optics.RESOLUTION_MM * mag),
        (0.0, -1.0, 0.0), "—",
        role=f"여기서 밑면 높이를 읽어 흐림을 낸다 — 초점흐림 c(Δz) 에 이송 흐림 "
             f"{motion_blur_mm() * 1000:.0f} µm 를 제곱합한다.",
        color="amber", explode=(0.0, -40.0, 0.0),
        spec=f"폭 {gi_optics.RESOLUTION_MM} mm"))
    parts.append(Part(
        "phcover", "보호창", 1, "box",
        (DRAWN_STRIP_W_MM * mag + 400.0, gi_optics.COVER_GLASS_T_MM * mag,
         gi_optics.roller_window_mm() * mag - 20.0 * mag),
        (0.0, -(cover_gap_mm() + gi_optics.COVER_GLASS_T_MM / 2.0) * mag, 0.0),
        "강화유리 / 반사방지",
        role=f"판 밑면에서 {cover_gap_mm():.0f} mm 아래. 유리 강성이 "
             f"{glass_share_for_cover() * 100:.3f} % 아래로 떨어진 판은 여기를 친다 — "
             f"폴리머만 남으면 {window_sag_mm(0.0):.0f} mm 처진다.",
        color="glass", explode=(0.0, -120.0, 0.0),
        spec=f"틈 {cover_gap_mm():.0f} mm · t{gi_optics.COVER_GLASS_T_MM:.0f}",
        catalog="GI-303-WD"))
    return Unit(
        key="plate", name=f"롤러 위의 판 · 물리엔진 ({mag:.0f} 배)",
        sheet="PV-GI-303-DYN-5401",
        envelope_mm=(DRAWN_STRIP_W_MM * mag + 400.0, 2.0 * cover_gap_mm() * mag + 200.0,
                     (DRAWN_ROLLERS * PITCH_MM + ROLLER_D_MM) * mag),
        view_r_mm=(DRAWN_ROLLERS * PITCH_MM + ROLLER_D_MM) * mag,
        principle=(
            ("① 성한 판은 평평하다",
             f"자중 처짐이 창에서 **{window_sag_mm() * 1000:.1f} µm** — 심도 "
             f"{dof} mm 의 {window_sag_mm() / dof * 100:.2f} % 다. 유리가 있는 한 "
             "가라앉을 이유가 없다."),
            ("② 앞끝이 창을 건넌다",
             f"앞끝이 스캔선을 지나 다음 롤러에 닿기까지 외팔로 처진다 — 스캔선이 보는 "
             f"최대가 **{entry_scan_sag_mm():.3f} mm**. 끝은 롤러 꼭대기가 아니라 옆면에 "
             f"{landing_approach_mm():.1f} mm 앞서 닿고 램프로 들려 올라간다."),
            ("③ 얹히는 되튐은 작다",
             f"램프가 1차 주기의 {landing_ramp_in_periods()} 배라 되튐이 "
             f"**{landing_overshoot_mm() * 1000:.1f} µm** 뿐이고 "
             f"{landing_settles_within_s() * 1000:.0f} ms 안에 잦아든다. 계단으로 잡았다면 "
             "앞끝 처짐보다 컸을 값이다."),
            ("④ 유리가 깨지면 문턱이 있다",
             f"유리 강성이 **{glass_share_for_focus() * 100:.3f} %** 아래면 심도를 벗어나고 "
             f"**{glass_share_for_cover() * 100:.3f} %** 아래면 보호창을 친다. 슬라이더로 "
             "κ 를 내려 보라 — 균열 몇 줄은 괜찮고 잘게 쪼개진 판이 문제다."),
            ("⑤ 남는 예산이 반입 조건이다",
             f"{float(gi_optics.PANEL_BOW_MM)} mm 중 자중·앞끝·되튐의 포락선 "
             f"{transient_envelope_mm():.3f} 과 흔들림 {runout_sag_mm()} 을 빼면 "
             f"**{warp_allowance_mm()} mm** 가 남는다 — 중고 판이 이보다 평평해야 한다."),
        ),
        parts=tuple(parts))


#: 심도 포락선을 그릴 때의 이송 방향 두께 (mm) — 스캔선 자리를 표시하는 띠다.
RESOLUTION_DRAW_MM = 8.0
#: 물리 유닛의 기본 시점 — 옆에서 조금 위. 처짐이 곡선으로 보여야 한다.
VIEW_DIR: tuple[float, float, float] = (0.32, 0.20, 1.0)
#: 브라우저에 넘기는 EI(κ) 표의 κ 표본 — 변환단면이 κ 에 선형이 아니라 표로 준다.
EI_TABLE_SHARES: tuple[float, ...] = (0.0, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 0.01, 0.03, 0.1, 0.3, 1.0)


def ei_table_si() -> list[list[float]]:
    """(κ, EI N·m² per m width) — 화면이 슬라이더 κ 에서 보간한다."""
    return [[k, round(ei_n_mm2(k) * 1e-3, 6)] for k in EI_TABLE_SHARES]


# ── 못 닫는 것 ───────────────────────────────────────────────────────────
def open_questions() -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    b = sag_budget_mm()
    out.append((
        "중고 패널의 휨이 반입 조건 안인지 실측 전이다",
        f"심도가 덮는 {b['allowance']} mm 중 자중·앞끝·되튐의 포락선 {b['envelope']} 과 "
        f"롤러 흔들림 {b['runout']} 이 쓰는 것은 {b['allowance'] - b['warp']:.2f} mm "
        f"뿐이라 **{b['warp']} mm** 가 판 자체의 "
        "휨에 남는다. 이것은 가정이 아니라 **반입 조건**이다 — 25 년 옥외에 있던 "
        "판이 이보다 평평한지는 표본을 재야 안다."))
    out.append((
        "깨진 유리에 남는 강성이 어디쯤인지 실측 전이다",
        f"처짐이 심도 안에 들려면 유리 강성이 **{glass_share_for_focus() * 100:.2f} %** "
        f"만 남아도 되고, 보호창을 안 치려면 **{glass_share_for_cover() * 100:.2f} %** "
        "면 된다. 균열 몇 줄은 괜찮다는 뜻이지만, 이 문턱은 조각난 유리가 봉지층을 "
        "통해 전단을 전한다는 전제(평면유지) 위의 값이다. 폴리머만 남는 비관 한계에서는 "
        f"창 처짐이 **{window_sag_mm(0.0):.0f} mm** 로 보호창 {cover_gap_mm():.0f} mm 를 "
        "친다 — 잘게 쪼개진 판이 두 한계 사이 어디인지는 실물을 롤러에 올려 봐야 안다."))
    if motion_blur_costs_more_than_sag():
        out.append((
            "화질을 정하는 것은 처짐이 아니라 이송 흐림이다",
            f"노광 {gi_optics.exposure_us():.0f} µs 동안 판이 {motion_blur_mm() * 1000:.0f} µm "
            f"를 가서 이송 방향 흐림이 화소의 **{motion_blur_px() * 100:.0f} %** 다. "
            "자중 처짐의 초점흐림은 그 자릿수 아래다. 줄이려면 노광을 줄여야 하고, "
            "그러면 조명이 그만큼 밝아야 한다 — `gi_optics` 미결 3 과 같은 수 하나에 걸린다."))
    return tuple(out)


def summary() -> dict[str, object]:
    b = sag_budget_mm()
    t = transformed_section()
    return {
        "eiNmm2": round(t["ei_n_mm2"], 1),
        "neutralAxisMm": round(t["na_mm"], 4),
        "polymerShare": polymer_share_of_stiffness(),
        "supportSpanMm": support_span_mm(),
        "windowSagMm": round(window_sag_mm(), 5),
        "simplySupportedSagMm": round(simply_supported_sag_mm(), 5),
        "continuityFactor": continuity_factor(),
        "entryTipSagMm": round(entry_sag_mm(), 5),
        "entryScanSagMm": round(entry_scan_sag_mm(), 5),
        "windowStressMpa": window_stress_mpa(),
        "f1Hz": round(fundamental_hz(), 2),
        "rollerPassHz": round(roller_pass_hz(), 4),
        "rollerSpinHz": round(roller_spin_hz(), 4),
        "frequencyRatio": frequency_ratio(),
        "runoutAmplification": runout_amplification(),
        "landingRampS": round(landing_ramp_s(), 5),
        "landingRampPeriods": landing_ramp_in_periods(),
        "landingExcursionMm": round(landing_excursion_mm(), 5),
        "landingOvershootMm": round(landing_overshoot_mm(), 5),
        "landingSettlesS": landing_settles_within_s(),
        "transientEnvelopeMm": round(transient_envelope_mm(), 5),
        "scanDwellS": round(scan_line_dwell_s(), 3),
        "motionBlurMm": motion_blur_mm(),
        "motionBlurPx": motion_blur_px(),
        "arrisPxAlong": arris_px(0.0, True),
        "arrisPxAcross": arris_px(0.0, False),
        "arrisPxAtDofEdge": arris_px(dof_half_mm(), True),
        "budget": b,
        "warpAllowanceMm": b["warp"],
        "shareForFocus": glass_share_for_focus(),
        "shareForCover": glass_share_for_cover(),
        "crazedHitsCover": a_fully_crazed_panel_hits_the_cover(),
        "openQuestions": [list(q) for q in open_questions()],
    }
