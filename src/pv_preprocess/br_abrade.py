# -*- coding: utf-8 -*-
"""BR-305 백시트 면 연마 유닛 — **부유선별에 들어갈 먹이를 깨끗하게 만든다.**

`sg_grind` 의 면 연마 절은 「에너지는 걸림돌이 아니다」까지 답하고 멈춰
있었다. 이 모듈은 그 다음 물음 — 그러면 그 기계는 어떻게 생겼는가 — 을 받는다.

**목적을 두 번 틀리게 잡았다가 고쳤다.** 처음에는 「불소를 열 앞에서 걷어
배가스의 HF 를 막는다」로 세웠는데 그것은 덤이었다. 다음에는 목적을 하류
**부유선별**로 옳게 잡았지만 **기구를 반대로 적었다** — 「불소는 표면에너지가
낮아 저절로 떠서 정광에 올라온다」고 썼다. 현장은 반대다. 기구는 `separation`
이 정본이고 요지는 —

  · 백시트는 물보다 무겁고(PET 1.38 · PVF 1.42), 파쇄 조각이 부상 상한
    1 mm 보다 커서 기포가 못 들어 올린다. 그래서 **가라앉는다.**
  · 가라앉는 곳이 하필 **실리콘이 있는 침강분**이다. 값나가는 쪽을 더럽힌다.
  · EVA 는 물보다 가벼워 스스로 뜬다 — 불순물이지만 저 혼자 갈라진다.

그러니 **파쇄 전에, 붙어 있는 채로** 걷어내야 한다. 그것이 이 유닛이다.
그리고 빼야 하는 것은 불소층만이 아니라 **백시트 전체**다 — PET 심재도 같은
행선지다.

목적이 바뀌면서 판정 기준 두 개가 같이 바뀌었다.

  ① **에너지 장부는 판정 기준이 아니다.** 하류 열박리가 짧아지는 것
     (−2.41 MJ/장)은 여전히 참이지만 덤이다. 이 유닛의 값은 정광 품위에서
     나오지 전기값에서 나오지 않는다. `energy_ledger_is_not_the_criterion()`.
  ② **잔존 백시트는 0 이어야 한다.** 불소가 목적이었다면 5 % 남는 것은
     5 % 짜리 문제였다. 부유선별에서는 남은 조각이 파쇄돼 정광을 통째로
     버린다 — 선형이 아니다. 그래서 깊이 공차가 **한쪽으로 닫혀야** 한다:
     가장 얕게 깎이는 자리에서도 백시트가 다 없어져야 한다.

그리고 이 목적에서 보면 연마에는 **되돌아오는 칼**이 있다.

  연마는 백시트를 없애는 것이 아니라 **더 고운 가루로 바꾼다.** 파쇄 조각은
  mm 급이지만 연마 분진은 수십 µm 급이고, 부유선별에서 38 µm 이하 미립자는
  가장 다루기 나쁜 것이다 — 굵은 알갱이에 달라붙어(slime coating) 그쪽 회수를
  막고, 거품 점도를 올려 맥석이 정광으로 딸려 올라가며, 시약을 많이 먹는다.
  **그러니 집진 포집률은 안전 항목이 아니라 품질 사양이다.** 안 잡힌 가루는
  자기가 대신한 필름보다 g 당 더 해롭다. `fines_that_escape_are_the_risk()`.

세 가지 기계적 결론은 목적이 바뀌어도 그대로다 — 깊이를 면에서 잡아야 하고,
열 판정이 δ/a < 1 이며, 헤드는 늘릴수록 나빠진다.

지금 라인은 이 유닛을 **안 세운다.** 이 모듈은 「세운다면 무엇을 사야 하고
무엇이 깨지는가」를 값으로 들고 있는 자리다.

    PYTHONPATH=src python -c "from pv_preprocess import br_abrade; print(br_abrade.summary())"
"""

from __future__ import annotations

import math

from . import campaign, separation, sg_grind
from .afr_units import Part, Unit

#: 유닛 태그와 라인에서의 자리.
UNIT_TAG = "BR-305"
#: 앞뒤 유닛 — 프레임이 빠진 뒤여야 벨트가 면에 닿고, 열이 오기 전이어야
#: 불소를 걷는 뜻이 있다. 그래서 자리가 이 둘 사이로 **정해진다**.
UPSTREAM_TAG, DOWNSTREAM_TAG = "AFR-101", "SG-301"

# ── 벗겨야 할 것과 남겨야 할 것 ─────────────────────────────────────────
#: 백시트 두께 (mm) — `sg_grind` 가 정본이다.
BACKSHEET_T_MM = sg_grind.BACKSHEET_T_MM
#: 백시트 바로 밑 EVA 층 두께 (mm) — **계획값**이고 저장소에 근거가 없다.
#: 이 값이 곧 「더 파도 되는 여유」다. 셀에 닿으면 은·실리콘이 분말로 섞여
#: 폴리머 회수물을 버린다.
BACK_EVA_T_MM = 0.45
#: 실제로 걷는 깊이 (mm). 백시트보다 **일부러 깊다** — 면이 완전히 평평하지
#: 않아 정확히 0.32 만 걷으면 낮은 자리에 백시트가 남고, 남은 조각이 파쇄돼
#: 부유선별 정광을 버린다. 근거는 `minimum_safe_depth_mm()` 이고 그 위에
#: 여유를 얹은 값이다 — 깊을수록 잔존은 안전해지지만 **미분이 늘어난다.**
#: 이 두 힘이 맞서는 자리가 이 유닛의 진짜 설계점이다.
TARGET_DEPTH_MM = 0.45

# ── 벨트와 헤드 — 시판 광폭 벨트 연마기 규격 ────────────────────────────
#: 벨트 폭 (mm). 패널 폭 1,400 을 받아야 하고, 실증 설비 개구부 1,300 은
#: 그래서 못 쓴다 (`sg_grind.panel_fits_face_abrader()` 가 거짓인 이유).
BELT_WIDTH_MM = 1_600.0
#: 직렬 헤드 수. 위의 ③ 때문에 **늘릴 수 없다** — `heads_are_thermally_sound()`.
HEADS = 2
#: 헤드별 입도 — 앞은 거칠게 걷고 뒤가 고르게 마무리한다. 오픈코트라야
#: 칩이 빠져 벨트가 안 먹는다.
GRITS = ("P60", "P100")
#: 접촉 드럼 지름 (mm). 접촉호 길이를 정하고, 그것이 열 계산에 그대로 든다.
CONTACT_DRUM_D_MM = 250.0
#: 벨트 주속 (m/s) — 금속용(25~30)보다 느리다. 폴리머는 빠르면 녹는다.
BELT_SPEED_M_S = 12.0

# ── 이송 — 라인 택트가 정한다 ───────────────────────────────────────────
#: 판 앞뒤로 더 가야 하는 거리 (mm) — 판이 접촉 드럼을 완전히 벗어나야 한다.
PASS_LEAD_MM = 300.0
#: 물림·정착·반출 인덱스 (s).
INDEX_S = 4.0
#: 택트 대비 남겨 둘 여유 (s). 이 유닛이 **새 병목이 되면 안 된다.**
TAKT_MARGIN_S = 2.0

# ── 깊이를 면에서 잡는 장치 ─────────────────────────────────────────────
#: 분할 압반 세그먼트 피치 (mm) — 좁을수록 면을 잘 따라간다.
PLATEN_SEGMENT_MM = 30.0
#: 세그먼트 추종 오차 (mm) — **계획값**. 벤더 실측으로 바뀐다.
PLATEN_FOLLOW_MM = 0.08
#: 정반을 기준으로 잡았다면 쌓였을 공차 (mm) — 유리 두께 ±0.20 과
#: 라미네이션 두께 ±0.15 의 합. 비교용으로만 둔다.
BED_REFERENCE_TOL_MM = 0.35

# ── 열 — 이 유닛을 정하는 자리 ──────────────────────────────────────────
#: 백시트 폴리머 열확산율 (mm²/s) — PET/PVF 대표값.
THERMAL_DIFFUSIVITY_MM2_S = 0.09
#: 비에너지 (J/mm³) — `sg_grind` 가 정본이고 역산한 추정치다.
ABRADE_J_MM3 = sg_grind.BACKSHEET_ABRADE_J_MM3
#: 폴리머 밀도 (g/mm³) 와 비열 (J/g·K).
DENSITY_G_MM3 = sg_grind.BACKSHEET_DENSITY_G_MM3
SPECIFIC_HEAT_J_G_K = 1.2
#: 갈아낸 일 중 **소재 쪽에 남는** 몫 — **계획값**. 거친 오픈코트로 크게 깎아
#: 낼수록 칩이 열을 가져가 이 값이 내려간다. 실측 전까지 보수적으로 잡는다.
HEAT_PARTITION = 0.35
#: 백시트 폴리머의 낮은 쪽 융점 (°C) 과 주위 온도.
MELT_C = sg_grind.BACKSHEET_MELT_C
AMBIENT_C = 20.0

# ── 집진 — 덕트 반송속도에서 나온다 ─────────────────────────────────────
#: 지관 지름 (mm) 과 반송속도 (m/s). 폴리머 분진은 가라앉으면 덕트에 쌓여
#: 그 자체가 연료가 되므로 반송속도를 못 낮춘다.
DUCT_D_MM = 150.0
DUCT_VELOCITY_M_S = 22.0
#: 헤드 하나가 무는 지관 간격 (mm) — 벨트 폭을 이 간격으로 나눈다.
OUTLET_PITCH_MM = 400.0
#: 집진 포집률 — **계획값**이고, 이 유닛에서 가장 무거운 한 개다.
#: 안 잡힌 가루는 면에 남아 그대로 파쇄로 간다. 부유선별에서 그것은
#: 자기가 대신한 필름보다 g 당 더 해롭다 (미립자라서).
DUST_CAPTURE = 0.995
#: 부유선별이 성가셔지기 시작하는 입도 (µm) — 이 아래가 미립자 영역이다.
#: 충돌·부착 효율이 떨어지고 slime coating 과 entrainment 가 커진다.
FINES_THRESHOLD_UM = 38.0


# ── 자리와 시간 ─────────────────────────────────────────────────────────
def pass_length_mm() -> float:
    """한 장이 지나야 하는 거리 (mm) — 판 길이에 리드를 더한다."""
    return round(float(campaign.PANEL_LENGTH_MM) + PASS_LEAD_MM, 1)


def occupancy_s() -> float:
    """이 유닛의 장당 점유 (s) — 택트에서 여유를 뺀 값으로 잡는다."""
    return round(campaign.ideal_takt_s() - TAKT_MARGIN_S, 2)


def belt_time_s() -> float:
    """그중 실제로 벨트 밑을 지나는 시간 (s)."""
    return round(occupancy_s() - INDEX_S, 2)


def feed_mm_s() -> float:
    """요구되는 이송속도 (mm/s) — 택트가 정하지 벤더가 정하지 않는다."""
    return round(pass_length_mm() / belt_time_s(), 1)


def feed_m_min() -> float:
    """같은 값을 m/min 으로 — 실증 라인 2.3 m/min 과 견주라고 둔다."""
    return round(feed_mm_s() * 60.0 / 1_000.0, 2)


def is_not_the_new_bottleneck() -> bool:
    """이 유닛을 넣어도 라인 택트가 안 늘어나는가."""
    return occupancy_s() <= campaign.ideal_takt_s()


# ── 깊이 — 창(窓)이 있고, 그 창을 어디서 잡느냐 ─────────────────────────
def depth_window_mm() -> tuple[float, float]:
    """걷어도 되는 깊이의 아래·위 (mm).

    아래는 백시트를 다 걷는 깊이, 위는 셀에 닿기 직전이다. 이 사이가
    설계가 쓸 수 있는 전부다.
    """
    return (BACKSHEET_T_MM, round(BACKSHEET_T_MM + BACK_EVA_T_MM, 3))


def depth_window_half_mm() -> float:
    """그 창의 반폭 (mm) — 공차가 이 안에 들어야 한다."""
    lo, hi = depth_window_mm()
    return round((hi - lo) / 2.0, 4)


def minimum_safe_depth_mm() -> float:
    """잔존 백시트를 0 으로 만드는 **최소** 절입 (mm).

    압반이 면을 ±오차만큼 따라가므로, 가장 얕게 깎이는 자리에서도 백시트가
    다 없어지려면 지령 절입이 백시트 두께보다 그 오차만큼 깊어야 한다.
    부유선별이 목적이면 이 값이 **하한이지 목표가 아니다** — 이보다 얕으면
    설계가 아예 성립하지 않는다.
    """
    return round(BACKSHEET_T_MM + PLATEN_FOLLOW_MM, 3)


def min_depth_cut_mm() -> float:
    """실제로 가장 얕게 깎이는 자리의 절입 (mm)."""
    return round(TARGET_DEPTH_MM - PLATEN_FOLLOW_MM, 3)


def max_depth_cut_mm() -> float:
    """실제로 가장 깊게 깎이는 자리의 절입 (mm)."""
    return round(TARGET_DEPTH_MM + PLATEN_FOLLOW_MM, 3)


def no_backsheet_survives() -> bool:
    """가장 얕은 자리에서도 백시트가 다 없어지는가 — **이쪽이 진짜 사양이다.**

    부유선별에서 잔존은 선형 문제가 아니다. 남은 조각이 파쇄되면 저절로
    뜨는 폴리머가 되어 정광을 통째로 버린다.
    """
    return min_depth_cut_mm() >= BACKSHEET_T_MM


def no_cell_is_touched() -> bool:
    """가장 깊은 자리에서도 셀에 안 닿는가 — 닿으면 은·실리콘을 가루로 버린다."""
    return max_depth_cut_mm() <= depth_window_mm()[1]


def tolerance_closes_both_ways() -> bool:
    """공차가 양쪽으로 다 닫히는가 — 이 유닛이 성립하는 조건."""
    return no_backsheet_survives() and no_cell_is_touched()


def depth_margin_over_minimum_mm() -> float:
    """하한 위로 얹은 여유 (mm) — 벨트 마모·면 굴곡이 먹는 몫이다."""
    return round(TARGET_DEPTH_MM - minimum_safe_depth_mm(), 3)


def target_is_inside_the_window() -> bool:
    """실제 절입이 창 안에 있는가."""
    lo, hi = depth_window_mm()
    return lo <= TARGET_DEPTH_MM <= hi


def bed_reference_would_miss() -> bool:
    """정반을 기준으로 잡으면 창을 넘는가.

    참이다. SR-302 가 띠에서 만난 것과 **같은 벽**이고, 답도 같다 —
    깊이를 면에서 잡는다. 다만 띠에서는 슈 하나면 됐고 면에서는 폭
    1,400 을 따라가야 하므로 분할 압반이 든다.
    """
    return BED_REFERENCE_TOL_MM > depth_window_half_mm()


def face_reference_fits() -> bool:
    """면에서 잡으면 창 안에 드는가."""
    return PLATEN_FOLLOW_MM <= depth_window_half_mm()


def depth_margin_ratio() -> float:
    """면 기준 추종 오차 대비 창 반폭의 배수 — 클수록 안전하다."""
    return round(depth_window_half_mm() / PLATEN_FOLLOW_MM, 2)


def platen_segments() -> int:
    """분할 압반 세그먼트 수 — 패널 폭을 피치로 나눈다."""
    return int(math.ceil(float(campaign.PANEL_WIDTH_MM) / PLATEN_SEGMENT_MM))


# ── 열 — 데워진 살이 칩으로 나가는가 ────────────────────────────────────
def depth_per_head_mm() -> float:
    """헤드 하나가 걷는 깊이 (mm)."""
    return round(TARGET_DEPTH_MM / HEADS, 4)


def contact_arc_mm(depth_mm: float | None = None) -> float:
    """접촉호 길이 (mm) = √(드럼지름 × 절입)."""
    a = depth_per_head_mm() if depth_mm is None else depth_mm
    return round(math.sqrt(CONTACT_DRUM_D_MM * a), 4)


def contact_time_s(depth_mm: float | None = None) -> float:
    """한 점이 접촉호 밑에 머무는 시간 (s)."""
    return round(contact_arc_mm(depth_mm) / feed_mm_s(), 5)


def thermal_skin_mm(depth_mm: float | None = None) -> float:
    """그동안 열이 파고드는 깊이 (mm) = √(α × 접촉시간)."""
    return round(math.sqrt(THERMAL_DIFFUSIVITY_MM2_S * contact_time_s(depth_mm)), 4)


def skin_to_depth_ratio(depth_mm: float | None = None) -> float:
    """가열층 δ 를 절입 a 로 나눈 값 — **1 보다 작아야 한다.**

    작으면 데워진 살이 통째로 칩이 되어 나가고 밑은 안 데워진다.
    1 을 넘으면 열이 남은 라미네이트로 들어간다.
    """
    a = depth_per_head_mm() if depth_mm is None else depth_mm
    return round(thermal_skin_mm(depth_mm) / a, 3)


def heat_leaves_with_the_chip() -> bool:
    """데워진 살이 칩으로 나가는가 — 이 유닛의 열 판정."""
    return skin_to_depth_ratio() < 1.0


def flash_rise_k() -> float:
    """절삭면 flash 온도 상승 (K) — 칩 **전체**가 아니라 가열층의 값이다.

    칩은 어차피 버리는 물건이라 녹아도 아깝지 않다. 문제는 **녹은 것이
    벨트에 붙는 것**이다. 그래서 이 값은 폐기물 온도가 아니라 오픈코트 선정과
    에어나이프·벨트 주속의 근거다. 융점을 넘는 것이 정상이고, 넘기 때문에
    그 셋이 옵션이 아니라 필수가 된다.
    """
    a = depth_per_head_mm()
    return round(HEAT_PARTITION * ABRADE_J_MM3 * a
                 / (DENSITY_G_MM3 * SPECIFIC_HEAT_J_G_K * thermal_skin_mm()), 1)


def flash_reaches_melt() -> bool:
    """flash 가 융점에 닿는가 — 닿으므로 오픈코트·에어나이프가 필수다."""
    return AMBIENT_C + flash_rise_k() >= MELT_C


def max_heads_thermally_allowed() -> int:
    """δ < a 를 지키는 헤드 수의 **상한**.

    헤드 수의 한계가 아래가 아니라 위에 있다는 것이 이 설계에서 가장
    뒤집힌 대목이다. 헤드를 늘리면 절입이 얇아지는데 가열층은 그만큼
    안 줄어서, 어느 수를 넘으면 열이 밑으로 들어간다.
    """
    n = 1
    while n < 24:
        a = TARGET_DEPTH_MM / (n + 1)
        skin = math.sqrt(THERMAL_DIFFUSIVITY_MM2_S
                         * math.sqrt(CONTACT_DRUM_D_MM * a) / feed_mm_s())
        if skin >= a:
            return n
        n += 1
    return n


def heads_are_thermally_sound() -> bool:
    """지금 헤드 수가 그 상한 안에 있는가."""
    return HEADS <= max_heads_thermally_allowed()


# ── 동력 ────────────────────────────────────────────────────────────────
def removal_rate_mm3_s() -> float:
    """제거율 (mm³/s) = 폭 × 절입 × 이송."""
    return round(float(campaign.PANEL_WIDTH_MM) * TARGET_DEPTH_MM * feed_mm_s(), 1)


def total_power_kw() -> float:
    """절삭 동력 합 (kW)."""
    return round(removal_rate_mm3_s() * ABRADE_J_MM3 / 1_000.0, 1)


def power_per_head_kw() -> float:
    """헤드 한 대가 무는 절삭 동력 (kW)."""
    return round(total_power_kw() / HEADS, 1)


def motor_rating_kw(efficiency: float = 0.75) -> float:
    """헤드당 모터 정격 (kW) — 절삭 동력을 구동 효율로 나눈다."""
    return round(power_per_head_kw() / efficiency, 1)


def energy_per_panel_j() -> float:
    """한 장에 드는 일 (J)."""
    return round(float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
                 * TARGET_DEPTH_MM * ABRADE_J_MM3, 1)


# ── 분진 ────────────────────────────────────────────────────────────────
def swarf_volume_mm3() -> float:
    """한 장에서 나오는 부스러기 부피 (mm³)."""
    return round(float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
                 * TARGET_DEPTH_MM, 1)


def swarf_kg_per_panel() -> float:
    """같은 것의 질량 (kg/장)."""
    return round(swarf_volume_mm3() * DENSITY_G_MM3 / 1_000.0, 2)


def swarf_kg_per_h() -> float:
    """라인 속도로 환산한 값 (kg/h) — 집진기가 실제로 받을 물건."""
    from . import handoff
    return round(swarf_kg_per_panel() * handoff.downstream_rate().line_per_h, 1)


def outlets_per_head() -> int:
    """헤드 하나가 무는 지관 수 — 벨트 폭을 피치로 나눈다."""
    return int(math.ceil(BELT_WIDTH_MM / OUTLET_PITCH_MM))


def hood_flow_m3h() -> int:
    """이 유닛이 요구하는 집진 풍량 (m³/h) — 지관 단면 × 반송속도 × 개수."""
    area = math.pi * (DUCT_D_MM / 2_000.0) ** 2
    per_outlet = area * DUCT_VELOCITY_M_S * 3_600.0
    return int(round(per_outlet * outlets_per_head() * HEADS))


def flow_ratio_to_existing() -> float:
    """지금 집진 집계의 몇 배인가."""
    from . import dust
    return round(hood_flow_m3h() / dust.counted_flow_m3h(), 2)


def fits_existing_collector() -> bool:
    """지금 집진기에 얹을 수 있는가 — 거짓이면 별도 계통이다."""
    return flow_ratio_to_existing() <= 1.0


def combustible_fraction_after() -> float:
    """이 유닛을 얹었을 때의 가연 풍량 비율 — 지금은 0.149 다.

    이 유닛의 흐름은 **전량 폴리머**라 분자에도 분모에도 통째로 들어간다.
    """
    from . import dust
    listed = dust.listed_streams()
    total = sum(x.flow_m3h for x in listed) + hood_flow_m3h()
    burnable = sum(x.flow_m3h for x in listed if x.combustible) + hood_flow_m3h()
    return round(burnable / total, 3)


def gate_this_unit_owns() -> str:
    """이 유닛이 맡은 관문 — 넷 중 하나다."""
    return "backsheet"


def breaks_the_inert_premise() -> bool:
    """가연분이 소수에서 **다수**로 넘어가는가 — 넘어가면 보호 방식이 바뀐다.

    DS-01 이 '불연' 으로 서 있는 것은 유리분이 주성분이기 때문이다. 이 유닛이
    들어오면 그 전제가 뒤집힌다 — 집진기는 더 이상 「가연분이 섞인 유리 집진기」
    가 아니라 「폴리머 집진기」다.
    """
    return combustible_fraction_after() > 0.5


# ── 부유선별 — 이 유닛의 값도 위험도 여기서 나온다 ──────────────────────
#
#   백시트를 붙은 채로 걷는 이유는 파쇄 뒤 실리콘과 같은 침강분에 안 들어가게
#   하기 위해서다. 그런데 연마는 그것을 **없애는 것이 아니라 가루로 바꾼다.**
#   잡히면 문제가 사라지고, 안 잡히면 그대로 남는다 — 그 갈림이 포집률이다.

def escaped_fines_g_per_panel() -> float:
    """집진에 안 잡혀 면에 남는 가루 (g/장) — 그대로 파쇄로 간다."""
    return round(swarf_kg_per_panel() * (1.0 - DUST_CAPTURE) * 1_000.0, 1)


def uncut_backsheet_g_per_panel() -> float:
    """이 유닛이 없었다면 파쇄로 갔을 백시트 (g/장) — 견줄 대상."""
    return round(float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
                 * BACKSHEET_T_MM * DENSITY_G_MM3, 1)


def polymer_reduction_ratio() -> float:
    """선별조로 가는 폴리머가 몇 분의 일로 줄었는가 — **질량 기준**이다."""
    return round(uncut_backsheet_g_per_panel() / escaped_fines_g_per_panel(), 1)


def capture_needed_for(residual_g: float) -> float:
    """잔류를 목표치 이하로 누르려면 필요한 포집률.

    사양을 거꾸로 세우는 자리다 — 선별 회로가 견디는 잔류량이 정해지면
    집진 포집률이 그 값에서 **결정되지**, 벤더 카탈로그에서 오지 않는다.
    """
    return round(1.0 - residual_g / (swarf_kg_per_panel() * 1_000.0), 5)


def fines_that_escape_are_the_risk() -> tuple[str, ...]:
    """왜 잡힌 가루가 아니라 **안 잡힌 가루**가 이 유닛의 위험인가."""
    return (
        f"질량으로는 크게 이긴다 — 실리콘 쪽으로 가는 폴리머가 "
        f"{uncut_backsheet_g_per_panel():,.0f} g/장에서 "
        f"{escaped_fines_g_per_panel():,.1f} g/장으로 "
        f"{polymer_reduction_ratio():,.0f} 분의 일이 된다.",
        "**밀도는 안 바뀐다.** 조각이든 가루든 물보다 무거운 것은 그대로이므로 "
        "안 잡힌 몫은 조각일 때와 같은 침강분으로 간다. 연마는 오염을 없애는 게 "
        "아니라 **잡히는 만큼만** 없앤다.",
        "그래서 선별 회로가 견디는 잔류량을 먼저 정해야 한다 — 그러면 포집률이 "
        "`capture_needed_for()` 로 **역산된다.** 질량비만 보고 「142 분의 "
        "일이니 됐다」고 할 일이 아니다.",
        f"입도가 {FINES_THRESHOLD_UM:.0f} µm 아래로 내려가면 방향이 불확실해진다 "
        "— 그 영역에서는 소수성이 살아나 오히려 뜰 수도 있고, 굵은 알갱이에 "
        "달라붙을 수도 있다. `separation.would_fines_float_instead()` 가 그 "
        "물음을 적어 두었고, **파쇄 전에 걷으면 답할 필요가 없다.**",
    )


def overshoot_into_eva_goes_the_other_way() -> bool:
    """백시트보다 깊이 판 몫이 실리콘 쪽으로 가는가 — 안 간다.

    EVA 는 물보다 가벼워 뜨므로 방향이 반대다. **공짜라는 뜻은 아니다** —
    EVA 도 관문 넷 중 하나다. 다만 백시트가 남는 것보다는 훨씬 낫고,
    그래서 절입에 여유를 줄 수 있다. `separation` 이 정본이다.
    """
    return separation.eva_escape_goes_the_other_way()


# ── 이 유닛이 무엇을 옮기는가 ───────────────────────────────────────────
def downstream_heat_saved_j() -> float:
    """하류 열박리에서 돌려받는 열 (J/장) — `sg_grind` 가 정본이다."""
    return sg_grind.downstream_heat_saved_j()


def net_energy_j() -> float:
    """순 에너지 (J/장) = 이 유닛이 쓰는 값 − 하류가 돌려주는 값."""
    return round(energy_per_panel_j() - downstream_heat_saved_j(), 1)


def break_even_depth_mm() -> float:
    """에너지 장부가 0 이 되는 절입 (mm).

    **이것은 판정 기준이 아니다.** 한때 그렇게 읽고 「채택이 0.02 mm 에서
    갈린다」고 적었는데, 그것은 이 유닛의 목적을 불소 배가스로 잘못 잡았을
    때의 이야기였다. 목적이 부유선별 먹이라면 값은 정광 품위에서 나오고
    전기값은 잔돈이다. 남겨 두는 이유는 하나 — 깊이를 키울 때 무엇이
    같이 커지는지 보려고.
    """
    area = float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
    return round(downstream_heat_saved_j() / (area * ABRADE_J_MM3), 3)


def depth_headroom_mm() -> float:
    """손익분기까지 남은 깊이 (mm) — 음수면 이미 넘었다."""
    return round(break_even_depth_mm() - TARGET_DEPTH_MM, 3)


def pays_for_itself() -> bool:
    """에너지만 놓고 보면 남는가 — **채택 판정이 아니다.**"""
    return net_energy_j() <= 0.0


def energy_ledger_is_not_the_criterion() -> tuple[str, ...]:
    """왜 이 장부로 채택을 정하면 안 되는가 — 한 번 그렇게 틀렸으므로 적어 둔다."""
    return (
        f"장부는 {net_energy_j()/1e6:+.2f} MJ/장이고 손익분기 절입은 "
        f"{break_even_depth_mm()} mm 다. 실제 절입 {TARGET_DEPTH_MM} mm 와 "
        f"{abs(depth_headroom_mm())} mm 차이라 **아슬아슬해 보인다.**",
        "그 아슬아슬함이 결정을 내리는 것처럼 읽히면 안 된다. 전기 "
        f"{abs(net_energy_j())/3.6e6:.2f} kWh/장은 잔돈이고, 이 유닛이 사는 것은 "
        "**정광 품위**다 — 저절로 뜨는 폴리머를 파쇄 전에 막는 값이다.",
        "그리고 하류 열박리 절감분은 목적이 아니라 덤이다. 목적이 그것이었다면 "
        "잔존 5 % 는 5 % 짜리 문제였겠지만, 부유선별에서는 남은 조각 하나가 "
        "정광을 통째로 버린다 — 그래서 `no_backsheet_survives()` 가 사양이다.",
    )


def back_face_sealant_mm3() -> float:
    """이 유닛이 덤으로 걷어 가는 뒷면 실란트 띠 부피 (mm³/장).

    백시트를 면째로 걷으면 그 면의 프레임 실란트 띠도 같이 걷힌다 —
    SR-302 가 뒷면에서 할 일이 없어진다는 뜻이다. 앞면(유리 쪽) 띠는
    그대로 남으므로 SR-302 가 없어지지는 않는다.
    """
    return sg_grind.sealant_volume_per_panel_mm3(faces=1)


def what_it_moves() -> tuple[str, ...]:
    """이 유닛이 **없애는 것이 아니라 옮기는 것** — 결정 항목이 여기 있다."""
    from . import dust
    return (
        f"**폴리머를 실리콘에서 집진기로 옮긴다.** 그것이 목적이다 — 파쇄 전에 "
        f"걷으면 가라앉는 백시트가 실리콘과 같은 침강분에 안 들어온다. 그쪽으로 "
        f"가는 폴리머가 {uncut_backsheet_g_per_panel():,.0f} → "
        f"{escaped_fines_g_per_panel():,.1f} g/장이 된다.",
        f"**다만 안 잡힌 몫은 그대로 남는다.** 밀도가 안 바뀌므로 가루가 되어도 "
        f"같은 침강분으로 간다. 그래서 포집률 {DUST_CAPTURE:.1%} 가 안전 항목이 "
        "아니라 **품질 사양**이고, 이 유닛에서 가장 무거운 계획값이다.",
        f"**불소는 굴뚝에서 실내로 옮겨진다.** 열박리가 백시트를 안 태우니 HF 가 "
        f"배가스로 안 가는 대신, 같은 불소가 {swarf_kg_per_h():,.1f} kg/h 의 "
        f"가연성 분진으로 실내 집진기에 쌓인다. `dust` 가 이미 「방폭벤트를 "
        f"옥내로 열 수 없다」고 적어 둔 그 집진기다.",
        f"**집진 계통이 성격째 바뀐다.** 풍량 {hood_flow_m3h():,} m³/h 는 지금 "
        f"집계의 {flow_ratio_to_existing()} 배라 못 얹고, 가연 풍량 비율이 "
        f"{dust.combustible_flow_fraction():.3f} 에서 "
        f"{combustible_fraction_after():.3f} 로 넘어간다. 채택 조건은 동력이 "
        "아니라 **별도 계통 + 불활성화 또는 옥외 이설**이다.",
    )


def open_questions() -> tuple[str, ...]:
    """실측이 와야 닫히는 것 — 계획값으로 세운 자리를 숨기지 않는다."""
    return (
        f"**선별 회로가 견디는 잔류량이 정해져 있지 않다.** 그것이 정해져야 "
        f"포집률이 역산된다 — 지금 계획값 {DUST_CAPTURE:.1%} 로는 "
        f"{escaped_fines_g_per_panel()} g/장이 남는다. 1 g/장까지 눌러야 하면 "
        f"포집률 {capture_needed_for(1.0):.3%} 가 필요하고, 그것은 집진기 사양이 "
        "아니라 **후드 설계와 면 청소(브러시·에어나이프)의 문제**다.",
        "**분진 입도 분포를 모른다.** 38 µm 아래가 몇 %인지가 부유선별에 주는 "
        "해로움을 정하는데, 그것은 입도·벨트 주속·이송이 함께 정한다. 시험 "
        "연마 한 번이면 나오는 값이고, 이 유닛에서 가장 먼저 재야 할 것이다.",
        f"**비에너지 {ABRADE_J_MM3} J/mm³ 가 역산값이다.** 벨트 모터 정격이 "
        f"공개돼 있지 않아 공정 전체 130~300 kWh/t 에서 배분해 얻었다. 이 값이 "
        f"두 배면 동력도 두 배({total_power_kw()*2:.1f} kW)이고 칩 온도도 두 배 "
        f"오른다 — 열 판정이 먼저 뒤집힌다.",
        f"**열 분배율 {HEAT_PARTITION} 이 계획값이다.** 거친 오픈코트로 크게 "
        f"깎을수록 내려간다. 다만 이 유닛의 판정은 온도가 아니라 δ/a 라 "
        f"분배율에 안 걸린다 — 분배율이 움직이는 것은 벨트 수명 쪽이다.",
        f"**백시트 밑 EVA {BACK_EVA_T_MM} mm 가 계획값이다.** 이것이 곧 창의 "
        f"넓이라 실측이 얇으면 창이 좁아지고, 분할 압반 추종 오차 "
        f"{PLATEN_FOLLOW_MM} mm 의 여유({depth_margin_ratio()} 배)가 그만큼 준다.",
        "**분할 압반 추종 오차가 벤더 값이다.** 면을 얼마나 따라가는지는 "
        "세그먼트 피치와 공압 응답이 정하고, 그것이 이 유닛의 핵심 사양이다.",
        "**분진 폭발 시험(Kst·MIE·MIT)이 없다.** 폴리머 전량 흐름이라 "
        "`dust` 의 St 등급 판정이 통째로 다시 서야 한다.",
    )


# ── 부품 ────────────────────────────────────────────────────────────────
def unit() -> Unit:
    """BR-305 의 부품 구성 — 헤드 하나 기준으로 세고 수량으로 곱한다."""
    w = BELT_WIDTH_MM
    parts: list[Part] = [
        Part("frame", "본체 프레임", 1, "box", (3_400.0, 2_200.0, w + 400.0),
             (0.0, 0.0, 0.0), "용접구조용강",
             "헤드·압반·이송을 한 몸에 잡는다", catalog=f"{UNIT_TAG}-FR-01"),
        Part("drum", "접촉 드럼", HEADS, "cyl",
             (CONTACT_DRUM_D_MM, w, CONTACT_DRUM_D_MM), (0.0, 900.0, 0.0),
             "강 + 고무 라이닝", "벨트를 면에 눌러 절입을 만든다", axis="y",
             spec=f"Ø{CONTACT_DRUM_D_MM:.0f} × {w:.0f}",
             catalog=f"{UNIT_TAG}-DR-01"),
        Part("belt", "연마 벨트", HEADS, "box", (2_400.0, 8.0, w),
             (0.0, 1_000.0, 0.0), "산화알루미늄 오픈코트",
             "폴리머를 칩으로 걷어낸다 — 오픈코트라야 안 먹는다",
             spec=f"{'/'.join(GRITS)} · 주속 {BELT_SPEED_M_S:.0f} m/s",
             catalog=f"{UNIT_TAG}-BT-01"),
        Part("platen", "분할 압반 세그먼트", platen_segments() * HEADS, "box",
             (PLATEN_SEGMENT_MM, 60.0, 90.0), (0.0, 860.0, 0.0),
             "강 + 흑연포",
             "면을 따라가며 깊이를 **면에서** 잡는다 — 정반 기준은 창을 넘는다",
             spec=f"피치 {PLATEN_SEGMENT_MM:.0f} mm · 추종 ±{PLATEN_FOLLOW_MM} mm",
             catalog=f"{UNIT_TAG}-PL-01"),
        Part("motor", "헤드 주모터", HEADS, "cyl", (320.0, 520.0, 320.0),
             (0.0, 1_500.0, 0.0), "IE3 3상유도",
             "벨트를 돌린다", axis="y",
             spec=f"{motor_rating_kw():.0f} kW", catalog=f"{UNIT_TAG}-MT-01"),
        Part("feed", "이송 롤러", 6, "cyl", (120.0, w, 120.0),
             (0.0, 780.0, 0.0), "강 + 폴리우레탄",
             "판을 물어 정속으로 보낸다", axis="y",
             spec=f"{feed_mm_s():.0f} mm/s", catalog=f"{UNIT_TAG}-FD-01"),
        Part("hood", "집진 후드", HEADS, "box", (420.0, 400.0, w),
             (0.0, 1_180.0, 0.0), "강판",
             "벨트 나가는 쪽을 감싸 분진을 잡는다", catalog=f"{UNIT_TAG}-HD-01"),
        Part("duct", "집진 지관", outlets_per_head() * HEADS, "cyl",
             (DUCT_D_MM, 700.0, DUCT_D_MM), (0.0, 1_500.0, 0.0), "강관",
             "분진을 반송속도 위로 끌어낸다 — 느리면 덕트에 쌓여 그것이 연료다",
             axis="y", spec=f"Ø{DUCT_D_MM:.0f} · {DUCT_VELOCITY_M_S:.0f} m/s",
             catalog=f"{UNIT_TAG}-DT-01"),
        Part("airknife", "냉각 에어나이프", HEADS, "box", (40.0, 40.0, w),
             (0.0, 1_020.0, 0.0), "알루미늄",
             "접촉 직후를 식혀 녹은 칩이 벨트에 붙는 것을 막는다",
             catalog=f"{UNIT_TAG}-AK-01"),
    ]
    return Unit(
        key="br305",
        name=f"{UNIT_TAG} 백시트 면 연마 유닛",
        sheet=f"PV-{UNIT_TAG}-ASM-5101",
        envelope_mm=(3_400.0, 2_200.0, w + 400.0),
        view_r_mm=2_200.0,
        principle=(
            ("① 물림", "이송 롤러가 판을 물어 정속으로 보낸다. 프레임은 "
                       f"{UPSTREAM_TAG} 에서 이미 빠졌으므로 면이 트여 있다."),
            ("② 1 단 절삭", f"거친 벨트({GRITS[0]})가 절입 "
                            f"{depth_per_head_mm():.3f} mm 를 걷는다. 데워진 살이 "
                            f"그대로 칩이 되어 나간다 (δ/a = {skin_to_depth_ratio()})."),
            ("③ 면 추종", f"분할 압반 {platen_segments()} 조각이 면을 따라가며 "
                          "깊이를 **면에서** 잡는다 — 정반 기준은 창을 넘는다."),
            ("④ 2 단 절삭", f"고운 벨트({GRITS[1]})가 남은 절입을 걷는다. 가장 얕은 "
                            f"자리도 {min_depth_cut_mm()} mm 라 백시트 "
                            f"{BACKSHEET_T_MM} mm 가 **어디에도 안 남는다** — "
                            "남으면 파쇄돼 선별조로 간다."),
            ("⑤ 포집", f"후드가 {swarf_kg_per_panel()} kg/장을 "
                       f"{hood_flow_m3h():,} m³/h 로 끌어낸다. 포집률 "
                       f"{DUST_CAPTURE:.1%} 를 못 지키면 남은 가루가 필름보다 "
                       "**더 나쁜 형태**로 파쇄에 실린다 — 여기가 품질 사양이다."),
            ("⑥ 인계", f"폴리머가 빠진 판이 {DOWNSTREAM_TAG} 로 간다. 파쇄 뒤 "
                       f"부유선별에 들어가는 폴리머가 "
                       f"{polymer_reduction_ratio():,.0f} 분의 일이 된다."),
        ),
        parts=tuple(parts))


def summary() -> dict[str, object]:
    """이 유닛을 한 눈에 — 도면 리터럴과 시험이 같은 값을 본다."""
    lo, hi = depth_window_mm()
    return {
        "tag": UNIT_TAG,
        "between": f"{UPSTREAM_TAG} → {DOWNSTREAM_TAG}",
        "occupancyS": occupancy_s(),
        "beltTimeS": belt_time_s(),
        "feedMmS": feed_mm_s(),
        "feedMMin": feed_m_min(),
        "isNotTheNewBottleneck": is_not_the_new_bottleneck(),
        "targetDepthMm": TARGET_DEPTH_MM,
        "depthWindowMm": [lo, hi],
        "minimumSafeDepthMm": minimum_safe_depth_mm(),
        "depthMarginOverMinimumMm": depth_margin_over_minimum_mm(),
        "minDepthCutMm": min_depth_cut_mm(),
        "maxDepthCutMm": max_depth_cut_mm(),
        "noBacksheetSurvives": no_backsheet_survives(),
        "noCellIsTouched": no_cell_is_touched(),
        "toleranceClosesBothWays": tolerance_closes_both_ways(),
        "bedReferenceWouldMiss": bed_reference_would_miss(),
        "faceReferenceFits": face_reference_fits(),
        "depthMarginRatio": depth_margin_ratio(),
        "platenSegments": platen_segments(),
        "heads": HEADS,
        "depthPerHeadMm": depth_per_head_mm(),
        "thermalSkinMm": thermal_skin_mm(),
        "skinToDepthRatio": skin_to_depth_ratio(),
        "heatLeavesWithTheChip": heat_leaves_with_the_chip(),
        "maxHeadsThermallyAllowed": max_heads_thermally_allowed(),
        "headsAreThermallySound": heads_are_thermally_sound(),
        "flashRiseK": flash_rise_k(),
        "flashReachesMelt": flash_reaches_melt(),
        "totalPowerKw": total_power_kw(),
        "motorRatingKw": motor_rating_kw(),
        "energyPerPanelJ": energy_per_panel_j(),
        "swarfKgPerPanel": swarf_kg_per_panel(),
        "uncutBacksheetGPerPanel": uncut_backsheet_g_per_panel(),
        "escapedFinesGPerPanel": escaped_fines_g_per_panel(),
        "polymerReductionRatio": polymer_reduction_ratio(),
        "swarfKgPerH": swarf_kg_per_h(),
        "hoodFlowM3h": hood_flow_m3h(),
        "flowRatioToExisting": flow_ratio_to_existing(),
        "fitsExistingCollector": fits_existing_collector(),
        "combustibleFractionAfter": combustible_fraction_after(),
        "breaksTheInertPremise": breaks_the_inert_premise(),
        "backFaceSealantMm3": back_face_sealant_mm3(),
        "breakEvenDepthMm": break_even_depth_mm(),
        "depthHeadroomMm": depth_headroom_mm(),
        "netEnergyJ": net_energy_j(),
        "paysForItself": pays_for_itself(),
        "partCount": sum(p.qty for p in unit().parts),
    }
