# -*- coding: utf-8 -*-
"""BR-305 백시트 면 연마 유닛 — **부유선별에 들어갈 먹이를 깨끗하게 만든다.**

`sg_grind` 의 면 연마 절은 「에너지는 걸림돌이 아니다」까지 답하고 멈춰
있었다. 이 모듈은 그 다음 물음 — 그러면 그 기계는 어떻게 생겼는가 — 을 받는다.

**목적을 두 번 틀리게 잡았다가 고쳤다.** 처음에는 「불소를 열 앞에서 걷어
배가스의 HF 를 막는다」로 세웠는데 그것은 덤이었다. 다음에는 목적을 하류
**부유선별**로 옳게 잡았지만 **기구를 반대로 적었다** — 「불소는 표면에너지가
낮아 저절로 떠서 정광에 올라온다」고 썼다. 현장은 반대다. 기구는 `separation`
이 정본이고 요지는 —

  · 백시트는 급광에서 **가라앉는다**(관측). 왜 그런지는 `separation` 이
    모른다고 적어 둔다 — 그 자리에서 두 번 틀렸다. 설계는 답에 안 걸린다.
  · 가라앉는 쪽이 **실리콘**이다. 그래서 이 유닛이 지키는 것은 실리콘 순도다.
  · 뜨는 쪽은 **은정광**이고 거기로 가는 것은 EVA 다 — 이 유닛 소관이 아니라
    DG-HK60 관문이다. 제품마다 오염원이 다르다는 것이 `separation` 의 요지다.

## 순서가 정해졌다 — **연마(백시트) → 칼날(셀모듈)** (발주처 결정)

한때 이 유닛과 `br_peel`(BR-306)이 **같은 자리를 두고 겨루는 대안**이었다.
발주처가 그 구도를 없앴다: **연마가 백시트를 걷고, 그 다음 칼날이 셀모듈을
유리에서 뗀다.** 둘은 경쟁이 아니라 **순차**이고 서로 다른 관문을 맡는다.

고른 이유가 이 유닛의 물리에 있다 — **연마는 면접촉이라 기준면이 생긴다.**
칼날이 EVA 안에 멈추려면 0.45 mm 띠 안을 **재서** 지켜야 하는데, 연마는
압반이 면을 타므로 깊이가 **접촉**으로 잡힌다. `why_this_beats_peeling()` 이
그 비교를 든다. 그리고 그것은 슈처럼 **붙이는 것이 아니라 기구 그 자체**다.

그 뒤 발주처가 앞 걸음도 정했다: **실란트 제거를 이 유닛으로 갈음하지 않고**
그대로 둔다. 그래서 순서는 세 걸음이다 — **실란트(SR-302) → 백시트(이 유닛) →
유리**. 이 유닛에게 그것이 중요한 이유는 하나다: 인발이 면에 남긴 실란트 띠가
백시트보다 0.43 mm 솟아 있어 **벨트가 백시트보다 그것을 먼저 만나는데**, 압반
추종 0.08 mm 로는 그 단차를 못 따라간다. 그 문제를 기계가 아니라 **순서가**
닫는다 — `the_order_is_necessary_but_not_sufficient()`.

**다만 순서만으로는 아직 안 닫혔다.** 그 날은 유리면(아래) 띠를 걷는데 이
유닛의 벨트가 지나가는 면은 백시트면(위)이다. 고칠 자리가 공정 순서에서
**공구 배치**로 좁아진 것이고, 그 배치는 안 들었다.

**판정은 내가 만들지 않았다** — 발주처가 정한 것을 받아 적는다.

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
#: 프레임이 떨어지는 자리 — 벨트가 면에 닿으려면 프레임이 먼저 빠져야 한다.
#: 앞 걸음과는 **다른 사실**이다. 한때 한 상수가 둘을 겸했다.
FRAME_REMOVED_AT = "AFR-101"

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

# ── 지지·파지 — 진공 테이블 ─────────────────────────────────────────────
#
#   외부에서 온 갠트리 사양서가 **진공 테이블**을 들고 왔고, 검토 결과 채택할
#   만하다 (`docs/br-305-gantry-review.md`). 이 유닛에 중요한 것은 셋이다.
#
#   ① **폭 방향 굴곡이 없어진다.** 롤러로 선(線) 지지하면 판이 처지고 굽는데
#      면으로 빨아 당기면 그게 없어진다. 그래서 깊이를 **한 축**으로 잡을 수
#      있게 되고, 폭 1,400 을 더듬던 분할 압반 47 조각이 필요 없어진다.
#   ② **파지가 통째로 풀린다.** 앞 걸음(SR-302)이 끄는 힘도, 이 유닛 벨트의
#      접선력도 세 자릿수 여유로 버틴다. 무는 면이 **유리**라 셀 허용 접촉압을
#      쓸 필요도 없다.
#   ③ **그런데 두께 공차는 못 없앤다.** 이게 갈림길이다 — 아래 기준면 절 참조.

#: 이 유닛이 판을 받치고 잡는 방식.
SUPPORT = "진공 테이블"
#: 진공도·마찰·사이클은 **`campaign` 이 정본**이다 — SR-302 가 같은 방식을
#: 쓰므로 두 곳에 적으면 갈라진다. 여기서는 받아 쓴다.
VACUUM_KPA = campaign.VACUUM_KPA
TABLE_FRICTION = campaign.TABLE_FRICTION
#: 판이 서고 헤드가 가는가 — 진공 테이블은 판을 세워야 성립한다.
PANEL_MOVES = False
#: 갠트리 양끝 오버트래블 (mm) — 헤드가 판 밖에서 가·감속할 자리.
GANTRY_OVERTRAVEL_MM = 400.0
#: 프레임이 행정 밖으로 더 나가는 길이 (mm, 한쪽).
FRAME_END_MM = 450.0
#: 흡착 배기 + 해제에 드는 시간 (s) — `campaign` 이 정본. 판이 서므로 이 시간이
#: 통과 시간에서 빠진다. 아래 `vacuum_budget_s()` 가 상한을 낸다.
VACUUM_CYCLE_S = campaign.VACUUM_CYCLE_S

# ── 깊이 기준 — 윗면을 잰다 ─────────────────────────────────────────────
#: 변위센서 + Z축 추종의 합 오차 (mm) — **계획값**.
#: 테이블 높이가 아니라 **백시트 윗면**을 재는 경우의 값이다.
Z_SENSOR_TOL_MM = 0.05

# ── 잔존 검사 — 갈고 나서 정말 없는지 본다 ──────────────────────────────
#: 비전 화소 크기 (mm/px) 와 검출에 필요한 화소 수 — **계획값**.
#: 사양서가 맞고 이 모델이 빠뜨렸던 것이다. 잔존 0 을 **요구만** 하고
#: 확인할 수단이 없었다.
VISION_PIXEL_MM = 0.5
VISION_MIN_PATCH_PX = 9

# ── 깊이를 면에서 잡는 장치 ─────────────────────────────────────────────
#: 분할 압반 세그먼트 피치 (mm) — 좁을수록 면을 잘 따라간다.
PLATEN_SEGMENT_MM = 30.0
#: 세그먼트 추종 오차 (mm) — **계획값**. 벤더 실측으로 바뀐다.
PLATEN_FOLLOW_MM = 0.08
#: 분할 압반을 채택했는가 — **진공 테이블이 그 일을 대신하므로 아니다.**
#: 지우지 않는 이유는 이것이 「폭 1,400 의 굴곡을 어떻게 따라갈 것인가」에
#: 대한 답이었고, 진공 테이블이 그 물음 자체를 없앴다는 것이 판단 근거이기
#: 때문이다. `the_platen_is_replaced_by_the_table()`.
PLATEN_ADOPTED = False
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
#: 부선 급광 입도 창 (µm) — `separation` 실측이 정본이고 여기서 안 정한다.
#: 한때 「38 µm 아래가 특별히 해롭다」고 적었는데, **급광은 전부가 미분이다** —
#: 안 잡힌 분진은 같은 창으로 들어가 같은 쪽으로 갈 뿐이다.
def feed_window_um() -> tuple[float, float]:
    """부선 급광 입도 창 (µm)."""
    return separation.feed_window_um()


# ── 자리와 시간 ─────────────────────────────────────────────────────────
def pass_length_mm() -> float:
    """한 장이 지나야 하는 거리 (mm) — 판 길이에 리드를 더한다."""
    return round(float(campaign.PANEL_LENGTH_MM) + PASS_LEAD_MM, 1)


def occupancy_s() -> float:
    """이 유닛의 장당 점유 (s) — 택트에서 여유를 뺀 값으로 잡는다."""
    return round(campaign.ideal_takt_s() - TAKT_MARGIN_S, 2)


def belt_time_s() -> float:
    """그중 실제로 벨트 밑을 지나는 시간 (s).

    판이 서므로(`PANEL_MOVES` = False) 흡착 배기와 해제가 여기서 빠진다.
    through-feed 였을 때는 이 시간이 없었다.
    """
    vac = 0.0 if PANEL_MOVES else VACUUM_CYCLE_S
    return round(occupancy_s() - INDEX_S - vac, 2)


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


# ── 진공 테이블 — 무엇을 없애고 무엇을 못 없애는가 ──────────────────────
def table_area_mm2() -> float:
    """흡착 면적 (mm²) — 판 한 면 전체."""
    return round(float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM), 1)


def vacuum_hold_kn() -> float:
    """테이블이 판을 당기는 힘 (kN) — 셈은 `campaign` 이 하고 면적만 준다."""
    return campaign.vacuum_hold_kn(table_area_mm2())


def vacuum_contact_mpa() -> float:
    """그때 유리면이 받는 접촉압 (MPa) — 진공도 그 자체다."""
    return campaign.vacuum_contact_mpa()


def vacuum_friction_hold_kn() -> float:
    """미끄러지기 전까지 버티는 면내 힘 (kN)."""
    return campaign.vacuum_friction_kn(table_area_mm2())


def vacuum_margin_over(force_n: float) -> float:
    """그 힘의 몇 배를 버티는가 — 얼마나 넉넉한지가 요지다."""
    if force_n <= 0.0:
        return float("inf")
    return round(vacuum_friction_hold_kn() * 1_000.0 / force_n, 1)


def belt_tangential_n() -> float:
    """이 유닛 벨트가 판을 끄는 힘 (N) = 절삭 동력 / 벨트 주속."""
    return round(total_power_kw() * 1_000.0 / BELT_SPEED_M_S, 1)


def what_the_vacuum_table_replaces() -> tuple[str, ...]:
    """진공 테이블이 사 주는 것 — 값으로 센다."""
    from . import sg_grind as sg
    return (
        f"**파지가 통째로 풀린다.** 진공 {VACUUM_KPA:.0f} kPa 로 "
        f"{vacuum_hold_kn()} kN 을 당기고 마찰 {TABLE_FRICTION:g} 면 면내 "
        f"{vacuum_friction_hold_kn()} kN 을 버틴다 — 앞 걸음 SR-302 가 끄는 "
        f"{sg.tangential_total_n()} N 의 "
        f"**{vacuum_margin_over(sg.tangential_total_n()):,.0f} 배**, 이 유닛 "
        f"벨트 접선력 {belt_tangential_n():,.0f} N 의 "
        f"**{vacuum_margin_over(belt_tangential_n()):,.0f} 배**다.",
        f"**셀 허용치를 안 쓴다.** 무는 면이 유리라 접촉압 "
        f"{vacuum_contact_mpa()} MPa 를 셀 기준 "
        f"{sg.FACE_SAFE_MPA} MPa 와 견줄 필요가 없다 — 견주어도 "
        f"{vacuum_contact_mpa() / sg.FACE_SAFE_MPA:.1f} 배로 그 안이다.",
        f"**그리퍼 패드 계산이 사라진다.** SR-302 에서 패드 "
        f"{sg.grip_pad_area_needed_mm2():,.0f} mm² 를 깔아 풀던 문제가 테이블 "
        "하나로 없어진다.",
        f"**분할 압반 {platen_segments()} 조각이 필요 없어진다** — 폭 방향 "
        "굴곡을 테이블이 펴 주므로 깊이를 한 축으로 잡는다. "
        "`the_platen_is_replaced_by_the_table()`.",
    )


def the_table_flattens_but_does_not_thin() -> tuple[str, ...]:
    """진공 테이블이 **못** 없애는 것 — 여기가 이 안의 갈림길이다.

    테이블은 판을 **펴** 준다. 휨·굴곡·지지 평면도가 없어진다. 그런데
    `BED_REFERENCE_TOL_MM` 은 그런 것이 아니라 **재료 두께 공차**다 —
    유리 두께 ±0.20 과 라미네이션 ±0.15. 진공은 판을 얇게도 두껍게도
    못 만든다.

    그래서 **테이블 면을 기준으로 Z 를 내리면 창을 못 지킨다.**
    """
    return (
        f"**없애는 것** — 휨·굴곡·지지 평면도. 그래서 한 축 Z 로 충분해지고 "
        f"분할 압반 {platen_segments()} 조각이 빠진다.",
        f"**못 없애는 것** — 재료 두께 공차 {BED_REFERENCE_TOL_MM} mm "
        "(유리 ±0.20 + 라미네이션 ±0.15). 진공은 두께를 못 바꾼다.",
        f"**그래서 테이블 기준은 여전히 안 된다** — 창 반폭 "
        f"{depth_window_half_mm()} 대비 "
        f"**{table_reference_margin()} 배**로 1 을 못 넘는다 "
        f"(`table_reference_fits()` = {table_reference_fits()}).",
        f"**윗면을 재면 든다** — 센서+추종 {Z_SENSOR_TOL_MM} mm 로 여유 "
        f"**{measured_reference_margin()} 배** "
        f"(`measured_reference_fits()` = {measured_reference_fits()}).",
    )


def table_reference_margin() -> float:
    """테이블 면을 기준으로 잡을 때의 여유 배수 — 1 을 넘어야 든다."""
    return round(depth_window_half_mm() / BED_REFERENCE_TOL_MM, 2)


def table_reference_fits() -> bool:
    """테이블 기준으로 창에 드는가 — **안 든다.**"""
    return BED_REFERENCE_TOL_MM <= depth_window_half_mm()


def measured_reference_margin() -> float:
    """윗면을 재서 따라갈 때의 여유 배수."""
    return round(depth_window_half_mm() / Z_SENSOR_TOL_MM, 2)


def measured_reference_fits() -> bool:
    """재서 잡으면 창에 드는가."""
    return Z_SENSOR_TOL_MM <= depth_window_half_mm()


def why_the_height_measurement_is_not_optional() -> tuple[str, ...]:
    """Z축 높이 측정이 부가 기능이 아니라 **전제**라는 것.

    받은 사양서에 「자동 높이 측정 및 표면 추종(Z축 제어)」가 특징 목록의
    한 줄로 들어 있다. 맞게 본 것인데 **왜 필수인지**가 안 적혀 있어
    옵션처럼 읽힌다. 그러면 원가를 줄일 때 제일 먼저 빠진다.
    """
    return (
        f"**빠듯한 것을 메우는 장치가 아니다.** 테이블 기준으로는 여유가 "
        f"{table_reference_margin()} 배로 **1 미만**이다 — 빠듯한 게 아니라 "
        "아예 못 든다.",
        "**테이블 높이 기준 제어로는 안 된다.** 재야 하는 것은 테이블에서 "
        "백시트 윗면까지가 아니라 **백시트 윗면 그 자체**다.",
        f"**재면 여유가 {measured_reference_margin()} 배**가 되어 분할 압반의 "
        f"{depth_margin_ratio()} 배보다도 낫다 — 다만 센서값이 계획값이다.",
        "**그래서 이 항목은 원가 절감 대상이 아니다.** 빼면 기계가 성립하지 "
        "않는다.",
    )


def the_single_z_axis_needs_the_table() -> tuple[str, ...]:
    """한 축 Z 와 진공 테이블은 **짝**이다 — 하나만 있으면 성립 안 한다."""
    return (
        "**한 축 Z 는 평면만 따라간다.** 폭 방향 굴곡은 못 따라간다.",
        f"**그 굴곡을 테이블이 편다.** 그래서 한 축으로 되는 것이고, 안 펴지면 "
        f"다시 분할 압반 {platen_segments()} 조각이 든다.",
        "**둘 중 하나만 있으면 안 된다** — 테이블만 있으면 두께 공차에 걸리고, "
        "측정만 있으면 굴곡에 걸린다.",
        "**그러므로 이 안의 사활은 하나다: 진공 흡착 상태에서 판이 실제로 "
        "얼마나 펴지는가.** 시험 한 번이면 나오는 값이고, 그 전에는 한 축으로 "
        "충분한지 못 정한다. **추측해서 정하지 않는다.**",
    )


def the_platen_is_replaced_by_the_table() -> tuple[str, ...]:
    """분할 압반을 왜 안 쓰는가 — 지우지 않고 근거로 남긴다."""
    return (
        f"**압반은 「폭 {campaign.PANEL_WIDTH_MM:,.0f} 의 굴곡을 어떻게 "
        f"따라갈 것인가」의 답이었다** — 피치 {PLATEN_SEGMENT_MM:.0f} mm 로 "
        f"{platen_segments()} 조각, 헤드 {HEADS} 대면 "
        f"{platen_segments() * HEADS} 개다.",
        f"**진공 테이블은 그 물음 자체를 없앤다.** 판을 펴 놓으면 따라갈 굴곡이 "
        f"없다 — `PLATEN_ADOPTED` = {PLATEN_ADOPTED}.",
        f"**다만 추종 {PLATEN_FOLLOW_MM} mm 라는 값은 살려 둔다.** 테이블이 "
        "판을 못 편다는 것이 시험에서 나오면 돌아올 자리이고, 그때 여유 "
        f"{depth_margin_ratio()} 배가 근거가 된다.",
    )


# ── 판이 서면 시간이 어떻게 갈리는가 ────────────────────────────────────
def gantry_stroke_mm() -> float:
    """갠트리가 왕복해야 하는 거리 (mm).

    판이 서 있으므로 **헤드가 판을 다 건너야 한다.** 뒤쪽 헤드가 판 끝을
    지나려면 앞쪽 헤드는 이미 헤드 간격만큼 더 나가 있어야 하고, 양끝에
    오버트래블이 든다.
    """
    return round(float(campaign.PANEL_LENGTH_MM) + HEAD_PITCH_MM
                 + 2.0 * GANTRY_OVERTRAVEL_MM, 1)


def machine_length_mm() -> float:
    """그래서 기계가 차지하는 길이 (mm) — 행정에 갠트리 폭과 프레임이 붙는다."""
    return round(gantry_stroke_mm() + 2.0 * FRAME_END_MM, 1)


def the_gantry_is_why_the_machine_is_long() -> tuple[str, ...]:
    """판을 세운 값 — 기계 길이로 돌아온다."""
    return (
        f"**판이 서므로 헤드가 건넌다.** 행정이 판 길이 "
        f"{campaign.PANEL_LENGTH_MM:,.0f} 에 헤드 간격 {HEAD_PITCH_MM:,.0f} 과 "
        f"오버트래블 {GANTRY_OVERTRAVEL_MM:,.0f}×2 를 더해 "
        f"**{gantry_stroke_mm():,.0f} mm** 다.",
        f"**기계 길이가 {machine_length_mm():,.0f} mm** 로 판 길이의 "
        f"{machine_length_mm() / float(campaign.PANEL_LENGTH_MM):.1f} 배가 된다. "
        "through-feed 는 판이 지나가므로 이 길이가 안 들었다 — 진공 테이블이 "
        "사 온 것의 또 다른 값이다.",
        f"**통과 거리는 행정이 아니다.** 벨트가 실제로 물고 가는 것은 판 길이 "
        f"+ 리드 = {pass_length_mm():,.0f} mm 이고, 시간은 그쪽에서 나온다.",
    )


def vacuum_budget_s(max_feed_m_min: float = 5.0) -> float:
    """기계 이송 상한을 지키면서 흡착·해제에 쓸 수 있는 시간 (s).

    판이 서므로 배기·해제 시간이 통과 시간에서 **빠진다.** 그만큼 이송이
    빨라져야 하는데, 이송에는 기계 상한이 있다. 그 둘이 만나는 자리가
    흡착 사이클의 예산이다.
    """
    max_mm_s = max_feed_m_min * 1_000.0 / 60.0
    need_s = pass_length_mm() / max_mm_s
    return round(occupancy_s() - INDEX_S - need_s, 2)


def vacuum_cycle_fits(max_feed_m_min: float = 5.0) -> bool:
    """계획한 흡착 사이클이 그 예산 안에 드는가."""
    return VACUUM_CYCLE_S <= vacuum_budget_s(max_feed_m_min)


def what_standing_the_panel_costs() -> tuple[str, ...]:
    """판을 세우면 무엇을 내주는가 — through-feed 와의 차이."""
    return (
        f"**흡착·해제 시간이 통과에서 빠진다.** 점유 {occupancy_s()} s 에서 "
        f"정착 {INDEX_S:.0f} s 와 흡착 {VACUUM_CYCLE_S:.0f} s 를 빼면 실제로 "
        f"가는 시간이 {belt_time_s()} s 이고, 그래서 이송이 "
        f"**{feed_mm_s()} mm/s ({feed_m_min()} m/min)** 로 올라간다.",
        f"**예산은 {vacuum_budget_s()} s 다** — 이송 상한 5 m/min 을 지키면서 "
        f"쓸 수 있는 흡착 시간이 그만큼이다 "
        f"(`vacuum_cycle_fits()` = {vacuum_cycle_fits()}).",
        "**through-feed 는 이 시간이 없었다.** 판이 계속 가므로 배기도 해제도 "
        "없다 — 진공 테이블이 사 온 것의 값이 여기다.",
        f"**흡착 사이클은 실측 전 계획값이다.** {VACUUM_CYCLE_S:.0f} s 를 넘으면 "
        "이송 상한에 먼저 걸리고, 그러면 이 유닛이 라인 병목이 된다.",
    )


# ── 잔존 검사 — 갈고 나서 정말 없는지 ───────────────────────────────────
def vision_min_patch_mm2() -> float:
    """비전이 잡아내는 최소 잔존 조각 (mm²)."""
    return round(VISION_MIN_PATCH_PX * VISION_PIXEL_MM ** 2, 3)


def residual_patch_mass_g(area_mm2: float) -> float:
    """그 넓이만큼 백시트가 남았을 때의 질량 (g)."""
    return round(area_mm2 * BACKSHEET_T_MM * DENSITY_G_MM3, 4)


def patch_that_weighs_like_the_leak_mm2() -> float:
    """이미 집진에서 새고 있는 양과 **같은 무게**가 되는 잔존 넓이 (mm²).

    이 값이 비전의 잣대다. 이보다 작은 조각은 지금도 새고 있는 분진보다
    가볍다 — 그것까지 잡으라고 요구하면 집진 쪽이 먼저 어긋난다.
    """
    return round(escaped_fines_g_per_panel()
                 / (BACKSHEET_T_MM * DENSITY_G_MM3), 1)


def vision_sees_what_matters() -> bool:
    """비전 분해능이 그 잣대보다 고운가."""
    return vision_min_patch_mm2() < patch_that_weighs_like_the_leak_mm2()


def why_the_vision_is_needed() -> tuple[str, ...]:
    """잔존 검사가 왜 드는가 — 이 모델이 빠뜨렸던 자리다.

    이 유닛은 「잔존 백시트 0」을 사양으로 **요구만** 했고 확인할 수단이
    없었다. 받은 갠트리 사양서의 공정 흐름도에 그 단계가 들어 있었고,
    그쪽이 맞다.
    """
    marker = patch_that_weighs_like_the_leak_mm2()
    return (
        "**잔존은 선형 손해가 아니다.** 5 % 남으면 5 % 짜리 문제가 아니라, "
        "남은 조각이 파쇄돼 정광을 통째로 버린다. 그래서 사양이 0 이다.",
        f"**그런데 0 인지 볼 수단이 없었다.** 깊이 제어가 창 안에 든다는 것과 "
        f"실제로 다 걷혔다는 것은 다른 명제다 — 벨트 마모·띠 잔사·흡착 "
        "들뜸이 다 그 사이에 끼어든다.",
        f"**잣대는 이미 새는 분진이다.** 집진이 놓치는 "
        f"{escaped_fines_g_per_panel()} g/장 과 같은 무게가 되는 잔존 조각이 "
        f"**{marker:,.0f} mm² (한 변 {marker ** 0.5:.0f} mm)** 다. 그보다 작은 "
        "조각을 잡으라고 하면 집진 쪽이 먼저 어긋난다.",
        f"**분해능은 문제가 아니다.** 화소 {VISION_PIXEL_MM} mm 로 "
        f"{VISION_MIN_PATCH_PX} 화소면 {vision_min_patch_mm2()} mm² 를 잡는다 — "
        f"잣대의 **{marker / vision_min_patch_mm2():,.0f} 분의 일**이다.",
        "**문제는 커버리지와 처분이다.** 면 전체를 보는가, 그리고 잡히면 "
        "**되돌려 한 번 더 가는가 버리는가** — 둘 다 안 들었다. "
        "**추측해서 정하지 않는다.**",
    )


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


# ── 순서 — 연마(백시트) → 칼날(셀모듈) ─────────────────────────────────
#
#   **발주처가 정한 순서다.** 이 유닛이 백시트 관문을 닫고, 그 다음 칼날이
#   셀모듈을 유리에서 뗀다. 한때 `br_peel`(BR-306)과 같은 자리를 두고 겨루는
#   대안이었는데 그 구도가 없어졌다 — 둘은 서로 다른 관문을 맡는다.

#: 이 유닛 **앞**에 오는 것 — 발주처가 「SR-302 를 살린 안」을 골랐다.
#: 실란트 제거를 백시트 연마로 갈음하지 **않고** 둘을 차례로 세운다.
PRIOR_UNIT = "SR-302 잔사 스크레이퍼 (실란트 띠)"
#: 이 유닛 다음에 오는 것 — 계단형 핫나이프가 셀모듈을 유리에서 뗀다.
NEXT_UNIT = "계단형 핫나이프 (셀모듈 ↔ 유리)"

#: 발주처가 정한 공정 순서. **세 걸음이고 이 유닛이 가운데다.**
#: 유리 제거가 `NEXT_UNIT` 과 같은 기계인지 GRM-401 이 따로 서는지는
#: 아직 안 들었다 — `what_this_order_leaves_open()` 이 그것을 든다.
LINE_ORDER = ("AFR-101 정치", PRIOR_UNIT, "BR-305 백시트 연마", "유리 제거")
#: 이 유닛이 `LINE_ORDER` 에서 서는 자리.
LINE_INDEX = LINE_ORDER.index("BR-305 백시트 연마")


def _tag(step: str) -> str:
    """공정 이름에서 태그를 뽑는다 — 「SR-302 잔사 …」 → 「SR-302」."""
    head = step.split(" ", 1)[0]
    return head if "-" in head else step


#: 앞뒤 걸음 — **`LINE_ORDER` 에서 계산한다.** 한때 이 둘이 "AFR-101", "SG-301"
#: 로 박혀 있었는데 발주처가 순서를 정하면서 어긋났다. 상수로 두면 또 어긋난다.
UPSTREAM_TAG = _tag(LINE_ORDER[LINE_INDEX - 1])
DOWNSTREAM_TAG = _tag(LINE_ORDER[LINE_INDEX + 1])


def the_order_is_grind_then_peel() -> tuple[str, ...]:
    """정해진 순서와 각자가 맡는 관문 — 경쟁이 아니라 순차다.

    이것은 세 걸음 중 **뒤 둘**이다. 앞에 실란트가 한 걸음 더 서는 것이
    `the_order_is_sealant_then_grind_then_glass()` 이다.
    """
    from . import separation
    return (
        f"**① 이 유닛(연마)** — 백시트를 면에서 걷어 **{gate_this_unit_owns()}** "
        "관문을 닫는다. 압반이 면을 타므로 깊이가 접촉으로 잡힌다.",
        f"**② {NEXT_UNIT}** — 백시트가 없어진 판에서 셀모듈을 유리에서 뗀다. "
        "칼날 랜드가 **유리를 타므로** 그쪽도 접촉 기준이다.",
        "**두 유닛이 각자 기준면을 가진다.** 연마는 판 면, 칼날은 유리 — "
        "둘 다 재지 않고 **닿아서** 멈춘다. 그것이 이 순서의 요지다.",
        f"관문 소유는 `separation.gate_owner()` 가 정본이다 — 백시트는 "
        f"{separation.gate_owner('backsheet')}, 유리는 "
        f"{separation.gate_owner('glass')}.",
    )


def the_order_is_sealant_then_grind_then_glass() -> tuple[str, ...]:
    """발주처가 고른 세 걸음 — 실란트 → 백시트 → 유리.

    두 안이 있었다. 실란트 제거를 이 유닛으로 **갈음하는** 안과, 실란트를
    그대로 두고 이 유닛을 **그 뒤에 세우는** 안. 발주처가 뒤쪽을 골랐다.

    갈음하는 안이 아니라는 것이 이 유닛에 중요하다 — 실란트가 남은 면을
    벨트가 지나가면 띠가 먼저 닿기 때문이다(`the_belt_meets_silicone_first()`).
    그 문제를 **기계가 아니라 순서가** 닫는다.
    """
    return (
        f"**① {PRIOR_UNIT}** — 프레임 인발이 면에 남긴 띠를 긁어낸다. "
        f"슈가 **백시트 면에 얹혀** 깊이를 잡는다.",
        f"**② BR-305 (이 유닛)** — 띠가 없어진 면을 벨트가 지나가며 백시트를 "
        f"걷고 **{gate_this_unit_owns()}** 관문을 닫는다.",
        f"**③ 유리 제거** — {NEXT_UNIT}. 백시트가 없어진 판에서 셀모듈을 "
        "유리에서 뗀다.",
        "**세 걸음이 전부 접촉으로 멈춘다.** 스크레이퍼는 슈가 백시트를, 연마는 "
        "압반이 판 면을, 칼날은 랜드가 유리를 탄다 — 어느 것도 재지 않는다.",
        f"**① 이 ② 의 면도 걷는다.** 한때 날이 유리면에만 서서 백시트면 띠가 "
        f"남았는데, 발주처가 날을 두 장으로 정해 양면을 같은 바퀴에 걷는다 — "
        f"`the_sealant_is_gone_before_the_belt()` = "
        f"{the_sealant_is_gone_before_the_belt()}.",
    )


def the_scraper_comes_first() -> bool:
    """앞 걸음이 이 유닛보다 앞에 서는가 — 순서만 본다."""
    return PRIOR_UNIT in LINE_ORDER and (
        LINE_ORDER.index(PRIOR_UNIT) < LINE_ORDER.index("BR-305 백시트 연마"))


def the_sealant_is_gone_before_the_belt() -> bool:
    """벨트가 오기 전에 띠가 걷혀 있는가 — **순서만으로는 안 된다.**

    처음에 이 술어를 순서만으로 썼다. 틀렸다. 순서는 **필요**하고 충분하지
    않다 — 걷는 면이 맞아야 한다.

    SR-302 의 날은 **유리면(아래)** 띠를 걷는다. 반출롤러가 변에서 물러나 그
    자리를 아래에 내주기 때문이다. 그런데 이 유닛의 벨트가 지나가는 면은
    **백시트면(위)** 이고, 그쪽 띠는 공구가 없다
    (`sg_grind.the_back_face_band_has_no_tool()`).

    그래서 지금은 거짓이고, 그것이 맞다. 날이 위 면도 걷게 되면 참이 된다.
    """
    return the_scraper_comes_first() and not sg_grind.the_back_face_band_has_no_tool()


def the_order_is_necessary_but_not_sufficient() -> tuple[str, ...]:
    """0.43 mm 단차를 무엇이 닫는가 — 순서가 필요하고, 그것만으로는 모자란다.

    이 유닛은 그 단차에 대해 **아무것도 할 수 없다.** 압반 추종은 0.08 mm 이고
    그것을 키우면 깊이 제어가 같이 풀린다. 그러니 닫는 것은 앞 걸음이다.

    다만 앞 걸음이 **서 있는 것**과 **이 유닛이 만나는 면을 걷는 것**은 다른
    조건이다. 지금 날은 유리면에 서고 벨트는 백시트면을 지나간다.
    """
    return (
        f"**단차는 {sealant_step_over_backsheet_mm()} mm 이고 추종은 "
        f"{PLATEN_FOLLOW_MM} mm 다** — {sealant_step_vs_platen_follow()} 배. "
        "이 유닛 안에서 고칠 수 있는 값이 아니다.",
        f"**순서는 맞다** — `the_scraper_comes_first()` = "
        f"{the_scraper_comes_first()}. 기계를 더 사는 것이 아니라 순서가 "
        "닫는 쪽이다.",
        f"**면도 맞았다** — `the_sealant_is_gone_before_the_belt()` = "
        f"{the_sealant_is_gone_before_the_belt()}. 한때 날이 유리면(아래)에만 "
        "서고 벨트는 백시트면(위)을 지나가 **순서가 맞는데도 안 닫혀 있었다.** "
        f"발주처가 날을 {sg_grind.BLADE_FACES} 장으로 정하면서 두 조건이 "
        "다 섰다.",
        "**그러니 두 조건을 곱으로 둔다.** 순서만 보면 한때 참이었던 것이 "
        "참으로 남아 같은 오독을 다시 낳는다 — 앞 걸음이 **서 있는 것**과 "
        "**이 유닛이 만나는 면을 걷는 것**은 다른 조건이다.",
        "**그리고 이 순서는 취향이 아니다.** 뒤집으면 벨트가 실리콘을 먼저 "
        "만나는 것이 확정이다 — 날이 몇 장이든 걷을 기회 자체가 뒤로 간다.",
        "**되돌아가는 쪽도 막혀 있다** — 연마를 먼저 하면 스크레이퍼의 슈가 "
        f"얹힐 백시트가 없어져 EVA {BACK_EVA_T_MM} mm 면에 앉는다. 그 면이 "
        "가열에서 어떻게 거동하는지는 아직 모르는 항목이다.",
    )


def the_scrape_error_lands_on_a_layer_that_leaves() -> tuple[str, ...]:
    """이 순서가 스크레이퍼에게 사 주는 것 — 깊이 오차가 어차피 없어질 층에 떨어진다.

    `why_this_beats_peeling()` 의 ② 와 같은 모양이다. 실패가 되돌릴 수 있는
    쪽에 서면 공차를 싸게 살 수 있다.
    """
    tol = sg_grind.blade_assembly_tol_mm()
    return (
        f"**날 깊이 오차 {tol} mm 가 백시트 {BACKSHEET_T_MM} mm 안에 있다** — "
        f"여유 {round(BACKSHEET_T_MM - tol, 3)} mm "
        f"(`sg_grind.backsheet_survives_scraping()` = "
        f"{sg_grind.backsheet_survives_scraping()}).",
        "**넘쳐도 이 유닛이 그 자리를 걷는다.** 스크레이퍼가 백시트를 파고들어도 "
        "그 층은 다음 걸음에서 통째로 없어진다 — 급광에 없던 것을 새로 만들지 "
        "않는다.",
        "**뒤집힌 순서에서는 이 논증이 없다.** 연마 뒤에 긁으면 오차가 EVA 에 "
        "떨어지고 그 밑이 셀이다. 사라질 층이 아니다.",
    )


def the_band_must_go_whole_now() -> tuple[str, ...]:
    """요구 폭이 6 → 20 mm 로 넓어진다 — 그런데 날이 이미 그것을 덮는다.

    휠이 근거였을 때 필요한 것은 **어깨가 들어갈 만큼**이었다
    (`sg_grind.sealant_must_go_first_mm()`). 벨트가 근거가 되면 면을 통째로
    지나가므로 **띠 전체**가 나가야 한다.
    """
    need_for_wheel = sg_grind.sealant_must_go_first_mm()
    band = float(sg_grind.SEALANT_BAND_MM)
    return (
        f"**휠 기준 요구는 {need_for_wheel} mm** 였다 — 플랜지가 면 위로 "
        "걸쳐 나오는 길이만큼.",
        f"**벨트 기준 요구는 띠 전체 {band:.0f} mm** 다. 벨트는 면을 다 지나가니 "
        "부분만 걷어도 남은 자리에서 같은 단차를 만난다.",
        f"**날 폭 {sg_grind.BLADE_WIDTH_MM:.0f} mm 가 이미 그것을 덮는다** "
        f"(띠 + {sg_grind.BLADE_WIDTH_MM - band:.0f} mm). 요구가 "
        f"{band / need_for_wheel:.1f} 배로 넓어졌는데 공구를 안 바꿔도 된다 — "
        "날 폭이 애초에 휠 어깨가 아니라 **띠**를 기준으로 잡혀 있었기 때문이다.",
    )


def why_this_beats_peeling() -> tuple[str, ...]:
    """백시트를 칼날로 뜯는 대신 연마로 걷는 이유 — 넷이다.

    `br_peel` 이 그 대안을 계산해 두었고, 값은 그쪽이 정본이다. 여기서는
    **이 유닛이 이기는 이유**만 든다.
    """
    from . import br_peel
    lo, hi = depth_window_mm()
    band = round(hi - lo, 3)
    return (
        f"**① 기준면을 잴 수 있다.** 띠 {band:g} mm 를 칼날은 슈 기준 "
        f"{br_peel.depth_control_mm():g} mm 로(여유 "
        f"{br_peel.depth_margin_ratio():.2f} 배) 지켜야 하는데, 연마는 윗면을 "
        f"**재서** {Z_SENSOR_TOL_MM:g} mm 로 여유 "
        f"{measured_reference_margin():.2f} 배다. 칼날은 슈를 **붙여야** 하고 "
        "못 붙는 자리가 있을 수 있는데, 연마는 판을 진공으로 펴 놓고 위에서 "
        "재므로 붙일 것이 없다.",
        f"**② 실패가 되돌릴 수 있는 쪽이다.** 얕으면 백시트가 남는데 그것은 "
        f"**면에서 보이고 한 패스 더 돌리면 된다** — 연마는 점진적이다. 깊으면 "
        f"여유 {hi - max_depth_cut_mm():.2f} mm 가 있고 넘쳐도 EVA 라 "
        "`overshoot_into_eva_adds_nothing()` 이 든 대로 급광에 없던 것을 "
        "새로 만들지 않는다. 칼날은 얕으면 **틈이 안 생겨 아예 성립하지 않는다.**",
        f"**③ 약한 면 덫이 안 걸린다.** 칼날·구부림은 `{br_peel.weakest_interface().key}`"
        f"({br_peel.weakest_interface().gc_aged_n_mm:g} N/mm)가 먼저 갈라져 PET "
        f"심재를 남기는데(`br_peel.the_weak_plane_is_a_trap()`), **연마는 면을 "
        "고르지 않는다** — 깊이 위의 모든 것을 걷는다. 약한 면이 어디 있든 무관하다.",
        "**④ 온도 충돌이 없다.** 자르기는 차갑게·떼기는 뜨겁게가 한 유닛에서 "
        "부딪히는데, 연마와 박리가 다른 스테이션이면 각자 온도를 가진다 "
        "(`br_peel.cutting_and_peeling_want_opposite_temperatures()`).",
    )


def the_gate_leak_narrows_by() -> float:
    """백시트 관문의 누출이 몇 배 좁아지는가 = 1 / (1 − 포집률).

    갈아서 다 걷으면 남는 것은 **못 잡은 분진**뿐이다. 백시트가 통째로
    급광에 들어가는 것(100 %)과 견주면 그만큼 좁아진다.
    """
    return round(1.0 / (1.0 - DUST_CAPTURE), 1)


def the_leak_still_lands_on_the_silicon() -> bool:
    """좁아진 누출도 **실리콘에 떨어지는가** — 떨어진다.

    그래서 `the_gate_leak_narrows_by()` 가 충분한지는 **실리콘 순도 사양**이
    정하고, 그 값은 이 모델에 없다. 포집률이 실측인지 설계 목표인지도 모른다.
    """
    return this_units_dust_lands_on_the_silicon()


def what_this_order_leaves_open() -> tuple[str, ...]:
    """순서가 정해져도 남는 것 — 지어내지 않는다."""
    return (
        f"**포집률 {DUST_CAPTURE:.1%} 가 실측인지 설계 목표인지 모른다.** 목표라면 "
        f"실제는 낮을 것이고 누출이 그만큼 늘어난다. 관문이 "
        f"{the_gate_leak_narrows_by():.0f} 배 좁아진다는 값이 여기 걸려 있다.",
        "**좁아진 누출이 충분한지 모른다** — 실리콘 순도 사양을 안 들었다. "
        "이 순서의 유일한 사활이다.",
        "**백시트를 걷은 뒤 드러난 EVA 면**이 칼날 랜드·그리퍼에 어떻게 작용하는지 "
        "모른다. 랜드는 유리를 타야 하는데 반대쪽 면이 가열에서 점착성이면 "
        "반송과 그리핑이 달라진다.",
        f"**{NEXT_UNIT} 가 유리 관문의 기존 주인과 어떤 관계인지 안 들었다** — "
        "같은 기계인지, 앞에 서는지. `separation.gate_owner('glass')` 는 아직 "
        "옛 주인을 든다. **추측해서 바꾸지 않는다.**",
        f"**{PRIOR_UNIT} 의 거처는 정해졌다** — 발주처가 자기 캐리어로 정했고 "
        f"(`campaign.SCRAPER_ON_ITS_OWN_CARRIER`) SG-301 에서 리드가 빠졌다. "
        "열린 것은 그 캐리어가 **몇 헤드로 얼마나 빨리** 가는가다 — 동력은 "
        "어느 속도에서도 문제가 아니고 캐리지와 슈가 정한다. "
        "`sg_grind.the_own_carrier_frees_the_feed()`.",
        f"**그 날이 이 유닛의 면을 걷는 것은 정해졌다** — 날 "
        f"{sg_grind.BLADE_FACES} 장이 마주 보고 같은 바퀴에 양면을 걷는다. "
        f"열린 것은 **판을 무엇이 붙잡는가**다: 법선은 상쇄되지만(알짜 "
        f"{sg_grind.normal_net_on_panel_n():.0f} N) 접선이 더해져 "
        f"{sg_grind.tangential_total_n()} N 이 주행 방향으로 걸린다. "
        "`sg_grind.the_shoes_oppose_each_other()`.",
    )


# ── 실란트 — 근거가 휠에서 이 벨트로 옮겨왔다 ───────────────────────────
#
#   SG-301 의 아리스가 공정 요구가 아니라고 확인되면서
#   (`sg_grind.ARRIS_REQUIRED_BY_PLANT`) 실란트를 먼저 걷어야 하는 근거가
#   한쪽을 잃었다. SR-302 를 부른 이유로 그 모듈에 적혀 있던 것은
#   **휠의 접근**뿐이었다. 휠이 없어지면 그 이유도 없어진다.
#
#   그런데 실란트는 여전히 나가야 한다 — 이번엔 이 유닛 때문이다. 띠는
#   라미네이트 **면** 위에 있고, 이 유닛의 벨트가 지나가는 면이 바로 그 면이다.

def sealant_step_over_backsheet_mm() -> float:
    """실란트 띠가 백시트보다 얼마나 솟아 있는가 (mm) — 벨트가 먼저 만나는 높이."""
    return round(sg_grind.sealant_left_t_mm() - BACKSHEET_T_MM, 4)


def sealant_step_vs_platen_follow() -> float:
    """그 단차가 정반(플래튼) 추종의 몇 배인가 — 1 을 넘으면 못 따라간다."""
    return round(sealant_step_over_backsheet_mm() / PLATEN_FOLLOW_MM, 2)


def sealant_band_face_area_mm2() -> float:
    """띠가 한 면에서 덮는 면적 (mm²) — 네 변 둘레 띠, 모서리 겹침을 뺀다."""
    b = float(sg_grind.SEALANT_BAND_MM)
    perimeter = 2.0 * (float(campaign.PANEL_LENGTH_MM) + float(campaign.PANEL_WIDTH_MM))
    return round(perimeter * b - 4.0 * b ** 2, 1)


def sealant_band_face_share() -> float:
    """면에서 띠가 차지하는 몫 — 작다는 것이 안심이 안 되는 이유는 높이다."""
    return round(sealant_band_face_area_mm2()
                 / sg_grind.backsheet_face_area_mm2(), 4)


def the_belt_meets_silicone_first() -> tuple[str, ...]:
    """휠이 없어도 실란트가 나가야 하는 이유 — 벨트가 백시트보다 이걸 먼저 만난다.

    이 근거는 아리스와 독립이다. 아리스가 없어도, SG-301 이 없어도 성립한다 —
    이 유닛의 벨트가 지나가는 면이 띠가 남아 있는 면이기 때문이다.

    **지금 라인에서 이것은 살아 있는 결함이 아니다.** 발주처가 실란트를 앞
    걸음으로 세웠으므로(`the_sealant_is_gone_before_the_belt()`) 벨트가 올 때
    띠는 없다. 이 함수가 세는 것은 **왜 그 걸음이 앞에 서야 하는가**이고,
    그 걸음을 빼면 이 수들이 그대로 돌아온다.
    """
    return (
        f"**띠가 백시트보다 {sealant_step_over_backsheet_mm()} mm 솟아 있다.** "
        f"인발 뒤 면에 남는 실란트 {sg_grind.sealant_left_t_mm()} mm 는 백시트 "
        f"{BACKSHEET_T_MM} mm 의 "
        f"{sg_grind.sealant_left_t_mm() / BACKSHEET_T_MM:.2f} 배다. 벨트는 "
        "제일 높은 것을 먼저 만난다 — 백시트가 아니라 실리콘이다.",
        f"**정반이 그 단차를 못 따라간다.** 추종 {PLATEN_FOLLOW_MM} mm 의 "
        f"{sealant_step_vs_platen_follow()} 배다. 단차가 목표 절입 "
        f"{TARGET_DEPTH_MM} mm 의 "
        f"{sealant_step_over_backsheet_mm() / TARGET_DEPTH_MM * 100:.0f} % 라 "
        "띠 위에서는 깊이 제어가 성립하지 않는다 — 면 기준이 띠를 기준으로 "
        "잡히기 때문이다.",
        f"**면적이 작은 것이 위안이 안 된다.** 띠는 한 면의 "
        f"{sealant_band_face_share() * 100:.1f} % "
        f"({sealant_band_face_area_mm2():,.0f} mm²) 뿐이지만 네 변 둘레를 "
        "따라가므로 모든 통과가 그것을 건넌다. 넓이가 아니라 **높이와 위치**가 "
        "문제다.",
        f"**갈아서 걷는 쪽도 비싸다.** 경화 실리콘의 비에너지 "
        f"{sg_grind.SEALANT_ABRADE_J_MM3} J/mm³ 는 백시트 {ABRADE_J_MM3} J/mm³ 의 "
        f"{sg_grind.SEALANT_ABRADE_J_MM3 / ABRADE_J_MM3:.0f} 배다. 긁는 쪽이 "
        f"가는 쪽보다 {sg_grind.scrape_beats_abrade_by():,} 배 싸다는 SG-301 의 "
        "계산은 그대로 살아 있다 — 바뀐 것은 그 앞에 서는 이유뿐이다.",
        "그래서 결론은 스크레이퍼를 지우자가 아니라 **근거가 옮겨왔다**다. "
        "SR-302 를 부르는 것은 휠이 아니라 이 벨트다.",
    )


def the_sealant_has_no_destination() -> tuple[str, ...]:
    """걷은 실란트가 어디로 가는지 이 모델은 모른다 — 지어내지 않는다."""
    return (
        f"한 장에 {sg_grind.sealant_volume_per_panel_mm3():,.0f} mm³ 다 — "
        f"SG-301 유리 제거량의 {sg_grind.sealant_ratio_to_glass()} 배.",
        f"네 관문(유리 · 구리 · EVA · 백시트)에 실란트가 없다. "
        f"`separation.COMPONENTS` 에 행도 없다 — {len(separation.COMPONENTS)} 개 "
        "성분 어디에도 안 들어 있다.",
        "긁어낸 부스러기가 고형이라 (`sg_grind.debris_is_solid()`) 회수함으로 "
        "가면 그만이다. 문제는 **안 걷힌 몫**이 파쇄로 들어갔을 때 부유선별에서 "
        "뜨는지 가라앉는지다. 실리콘은 표면에너지가 낮아 불소 폴리머처럼 시약 "
        "없이 뜰 소지가 있으나, 추측으로 행을 만들지 않는다.",
    )


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
        f"**어차피 같은 창으로 들어간다.** 급광이 "
        f"{feed_window_um()[0]:.0f}~{feed_window_um()[1]:.0f} µm 이므로 안 잡힌 "
        "몫도 분쇄를 거쳐 그 창에 들어가고, 백시트가 가는 쪽으로 간다. "
        "연마는 오염을 없애는 게 아니라 **잡히는 만큼만** 없앤다.",
        "그래서 선별 회로가 견디는 잔류량을 먼저 정해야 한다 — 그러면 포집률이 "
        "`capture_needed_for()` 로 **역산된다.** 질량비만 보고 「142 분의 "
        "일이니 됐다」고 할 일이 아니다.",
        "「미분이라 특별히 더 해롭다」는 이야기가 **아니다** — 급광은 전부가 "
        "미분이다. 안 잡힌 분진은 그냥 **안 걷힌 백시트**이고, 그 이상도 "
        "이하도 아니다. `separation.grinding_finer_is_not_a_way_out()`.",
    )


def overshoot_into_eva_adds_nothing() -> bool:
    """백시트보다 깊이 판 몫이 급광에 EVA 를 **더하는가** — 안 더한다.

    **한때 「방향이 반대라 덜 아프다」고 적었는데 정반대였다.** EVA 가 가는
    쪽(뜨는 쪽)에 **은정광이 있다** — 거기는 83 배로 줄어든 작은 흐름이라
    섞인 것이 품위를 가장 크게 깎는다. 방향이 반대인 것은 위안이 아니다.

    그래도 절입 여유는 괜찮다. 이유가 다를 뿐이다 — 더 판 EVA 는 **판 안에
    원래 있던 것**이고, 잡히면 라인 밖으로 나가고 안 잡혀도 하류
    DG-HK60 이 원래 맡던 몫으로 돌아갈 뿐이다. **급광에 없던 EVA 를
    새로 만들지 않는다**는 것이 여유의 근거다.
    """
    return not separation.by_key("eva").belongs_in_feed


def eva_lands_on_the_silver() -> bool:
    """샌 EVA 가 어느 제품에 떨어지는가 — 은이다. `separation` 이 정본이다."""
    return separation.eva_lands_on_the_silver()


def this_units_dust_lands_on_the_silicon() -> bool:
    """이 유닛이 못 잡은 백시트 분진은 어느 제품에 떨어지는가 — 실리콘이다."""
    keys = {c.key for c in separation.contaminates("silicon")}
    return separation.gate_component_keys("backsheet") <= keys


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
        f"**백시트를 실리콘에서 집진기로 옮긴다.** 그것이 목적이다 — 파쇄 전에 "
        f"걷으면 가라앉는 백시트가 실리콘과 같은 쪽에 안 들어온다. 그쪽으로 "
        f"가는 폴리머가 {uncut_backsheet_g_per_panel():,.0f} → "
        f"{escaped_fines_g_per_panel():,.1f} g/장이 된다. **은은 이 유닛이 "
        "지키는 대상이 아니다** — 은은 뜨고 백시트는 가라앉는다.",
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
        f"**진공 흡착 상태의 판 평탄도를 모른다 — 이 안의 사활이다.** 한 축 Z "
        f"추종은 폭 방향 굴곡을 못 따라가고, 그 굴곡을 테이블이 펴 준다는 것이 "
        f"전제다. 안 펴지면 분할 압반 {platen_segments() * HEADS} 개가 돌아오고 "
        f"(`PLATEN_ADOPTED` 가 참이 된다) 부품이 다시 네 배가 된다. 시험 한 "
        "번이면 나오는 값이다.",
        f"**변위센서+Z 추종 합 오차 {Z_SENSOR_TOL_MM} mm 가 계획값이다.** 창 "
        f"반폭 {depth_window_half_mm()} 대비 여유 "
        f"{measured_reference_margin()} 배인데, 이 값이 "
        f"{depth_window_half_mm()} 를 넘으면 기계가 성립하지 않는다 — "
        "테이블 기준으로는 이미 안 되기 때문에 물러설 자리가 없다.",
        f"**흡착 배기·해제 {VACUUM_CYCLE_S:.0f} s 가 계획값이다.** 판이 서므로 "
        f"이 시간이 통과에서 빠지고 이송이 {feed_m_min()} m/min 으로 올라간다. "
        f"예산은 {vacuum_budget_s()} s 이고(이송 상한 5 m/min 기준) 넘으면 이 "
        "유닛이 라인 병목이 된다.",
        "**비전이 면 전체를 보는지, 잡히면 어떻게 하는지 안 들었다.** 분해능은 "
        f"잣대의 {patch_that_weighs_like_the_leak_mm2() / vision_min_patch_mm2():,.0f} "
        "분의 일이라 문제가 아니다 — 커버리지와 처분(되돌림/폐기)이 미결이다.",
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
# ── 3D 배치 — BOM 을 자리로 편다 ─────────────────────────────────────────
#
#   한때 부품이 전부 (0, y, 0) 에 쌓여 있었다. 수량과 규격만 맞으면 되는
#   **부품표**였기 때문인데, 그것을 그대로 세우면 두 헤드가 겹치고 아무것도
#   안 보인다. 그래서 자리를 준다 — 이송은 **x**, 벨트 폭은 **z**, 위가 **y** 다.
#
#   기준면은 **판 윗면 y = 0** 이다. 벨트가 그 위에 얹히고 이송 롤러가 밑을
#   받치므로, 부호만 보고도 무엇이 판을 누르고 무엇이 받치는지 읽힌다.

#: 줄지어 세우는 부품의 간격 (mm) — 3D 가 수량을 자리로 펼 때 쓴다.
ROW_PITCH_MM = {"feed": 520.0, "duct": 200.0}

#: 연마 벨트 두께 (mm) — 배킹 + 연마층. 한때 부품표에 숫자로만 박혀 있었다.
BELT_T_MM = 8.0
#: 헤드 두 대의 이송 방향 간격 (mm) — ±이 값에 서고 `mirror=('x',)` 로 편다.
HEAD_PITCH_MM = 1_400.0
#: 접촉부 확대 배율 — 절입 0.45 mm 를 5.5 mm 적층 옆에서 읽으려면 이만큼 키운다.
CONTACT_MAG = 60.0

#: 유닛별 기본 시점. 기계는 이송축을 비스듬히 봐야 두 헤드가 갈려 보이고,
#: 접촉부는 폭 방향(z)에서 봐야 층이 단면으로 읽힌다.
VIEW_DIR = {
    "br305": (1.05, 0.88, 1.05),
    "contact": (0.35, 0.55, 1.35),
}


def unit() -> Unit:
    """BR-305 기계 전경 — 판이 롤러에 실려 두 헤드를 지난다.

    부품 수량은 부품표 그대로이고, 자리는 위 좌표계로 준다. 두 헤드는
    `mirror=('x',)` 로 ±`HEAD_PITCH_MM`/2 에 선다.
    """
    w = BELT_WIDTH_MM
    hx = HEAD_PITCH_MM / 2.0
    t = sg_grind.STACK_T_MM                          # 적층 두께 — sg_grind 정본
    belt_y = BELT_T_MM / 2.0                                 # 벨트가 판 위에 얹힌다
    drum_y = BELT_T_MM + CONTACT_DRUM_D_MM / 2.0
    parts: list[Part] = [
        Part("frame", "본체 프레임", 1, "box",
             (machine_length_mm(), 1_500.0, w + 400.0),
             (0.0, 480.0, 0.0), "용접구조용강",
             "헤드·압반·이송을 한 몸에 잡는다. 화면에서는 **포락선**으로만 "
             "세운다 — 채우면 안이 안 보인다.",
             color="ghost", explode=(0.0, 900.0, 0.0),
             spec=f"{machine_length_mm():,.0f} × 1,500 × {w + 400.0:,.0f} — "
                  f"갠트리 행정 {gantry_stroke_mm():,.0f} 이 길이를 정한다",
             catalog=f"{UNIT_TAG}-FR-01"),
        Part("panel", "라미네이트 (백시트가 위)", 1, "box",
             (float(campaign.PANEL_LENGTH_MM), t, float(campaign.PANEL_WIDTH_MM)),
             (0.0, -t / 2.0, 0.0), f"유리 t{sg_grind.GLASS_T_MM} + EVA·백시트",
             f"**윗면이 y = 0** 이고, 진공 테이블에 물려 **서 있다.** 움직이는 "
             f"것은 갠트리다 — 헤드가 {feed_mm_s():.1f} mm/s 로 건너며 두 대가 "
             f"차례로 같은 자리를 지난다. 통과 거리 {pass_length_mm():,.0f} mm, "
             f"점유 {occupancy_s()} s.",
             color="aluminum", explode=(0.0, -700.0, 0.0),
             spec=f"{campaign.PANEL_LENGTH_MM:,.0f} × {campaign.PANEL_WIDTH_MM:,.0f} "
                  f"× {t}", catalog="—"),
        Part("table", "진공 테이블 (유리면 지지)", 1, "box",
             (float(campaign.PANEL_LENGTH_MM) + 200.0, 180.0,
              float(campaign.PANEL_WIDTH_MM) + 200.0),
             (0.0, -t - 90.0, 0.0), "알루미늄 + 실링 패드",
             f"판을 **면으로** 빨아 당긴다. 진공 {VACUUM_KPA:.0f} kPa 로 "
             f"{vacuum_hold_kn()} kN, 면내로 {vacuum_friction_hold_kn()} kN 을 "
             f"버틴다 — 벨트 접선력 {belt_tangential_n():,.0f} N 의 "
             f"{vacuum_margin_over(belt_tangential_n()):,.0f} 배다. 무는 면이 "
             f"유리라 접촉압 {vacuum_contact_mpa()} MPa 가 셀 허용치와 무관하다. "
             "**이 테이블이 판을 펴 주는 것이 한 축 Z 제어의 전제다.**",
             color="frame", explode=(0.0, -420.0, 0.0),
             spec=f"{VACUUM_KPA:.0f} kPa · {vacuum_hold_kn()} kN · 접촉압 "
                  f"{vacuum_contact_mpa()} MPa", catalog=f"{UNIT_TAG}-VT-01"),
        Part("zprobe", "윗면 변위센서 + Z 추종", HEADS, "cyl",
             (60.0, 180.0, 60.0), (hx + 420.0, 140.0, 0.0), "레이저 변위센서",
             axis="y",
             role=f"**백시트 윗면을 직접 잰다.** 테이블 높이를 기준으로 잡으면 "
                  f"재료 두께 공차 {BED_REFERENCE_TOL_MM} mm 가 남아 창 반폭 "
                  f"{depth_window_half_mm()} 의 {table_reference_margin()} 배 — "
                  f"**못 든다.** 윗면을 재면 센서+추종 {Z_SENSOR_TOL_MM} mm 로 "
                  f"여유가 {measured_reference_margin()} 배가 된다. 이 부품은 "
                  "**옵션이 아니라 이 기계가 성립하는 조건**이다.",
             mirror=("x",), color="orange", explode=(0.0, 360.0, 0.0),
             spec=f"합 오차 {Z_SENSOR_TOL_MM} mm · 여유 "
                  f"{measured_reference_margin()} 배", catalog=f"{UNIT_TAG}-ZP-01"),
        Part("belt", "연마 벨트", HEADS, "box", (760.0, BELT_T_MM, w),
             (hx, belt_y, 0.0), "산화알루미늄 오픈코트",
             f"폴리머를 칩으로 걷어낸다 — 오픈코트라야 안 먹는다. 화면에 세운 "
             f"것은 **접촉 주행분**이고 고리 전체는 2,400 mm 다. 주속 "
             f"{BELT_SPEED_M_S:.0f} m/s 가 이송 {feed_mm_s():.1f} mm/s 의 "
             f"{BELT_SPEED_M_S * 1_000.0 / feed_mm_s():,.0f} 배라 한 자리를 "
             "그만큼 여러 번 지나간다.",
             mirror=("x",), color="dark", explode=(0.0, 260.0, 0.0),
             spec=f"{'/'.join(GRITS)} · 고리 2,400 × {w:.0f} · 주속 "
                  f"{BELT_SPEED_M_S:.0f} m/s", catalog=f"{UNIT_TAG}-BT-01"),
        Part("drum", "접촉 드럼", HEADS, "cyl",
             (CONTACT_DRUM_D_MM, w, CONTACT_DRUM_D_MM), (hx, drum_y, 0.0),
             "강 + 고무 라이닝",
             f"벨트를 면에 눌러 절입을 만든다. 접촉 호가 "
             f"{contact_arc_mm()} mm 이고 그 안에 판이 머무는 시간이 "
             f"{contact_time_s() * 1_000:.2f} ms 다 — 열이 안 퍼지고 칩으로 "
             "나가는 근거가 이 짧음이다.", axis="z",
             mirror=("x",), color="steel", explode=(0.0, 620.0, 0.0),
             spec=f"Ø{CONTACT_DRUM_D_MM:.0f} × {w:.0f}",
             catalog=f"{UNIT_TAG}-DR-01"),
        Part("vision", "잔존 백시트 검사 비전", 1, "box", (240.0, 160.0, w),
             (-hx - 700.0, 320.0, 0.0), "라인스캔 카메라 + 조명",
             role=f"갈고 나서 **정말 없는지** 본다. 깊이가 창 안에 들었다는 "
                  f"것과 다 걷혔다는 것은 다른 명제다 — 벨트 마모·띠 잔사·흡착 "
                  f"들뜸이 그 사이에 낀다. 화소 {VISION_PIXEL_MM} mm 로 "
                  f"{vision_min_patch_mm2()} mm² 를 잡는데, 잣대는 집진이 이미 "
                  f"놓치는 {escaped_fines_g_per_panel()} g 과 같은 무게가 되는 "
                  f"{patch_that_weighs_like_the_leak_mm2():,.0f} mm² 다 — "
                  f"{patch_that_weighs_like_the_leak_mm2() / vision_min_patch_mm2():,.0f} "
                  "분의 일이라 분해능은 문제가 아니다. **커버리지와 처분이 "
                  "미결이다.**",
             color="chrome", explode=(0.0, 420.0, 0.0),
             spec=f"{VISION_PIXEL_MM} mm/px · 최소 {vision_min_patch_mm2()} mm²",
             catalog=f"{UNIT_TAG}-VS-01"),
        Part("airknife", "냉각 에어나이프", HEADS, "box", (40.0, 40.0, w),
             (hx - 400.0, 40.0, 0.0), "알루미늄",
             "접촉 직후를 식혀 녹은 칩이 벨트에 붙는 것을 막는다. 드럼 "
             f"**나가는 쪽**에 선다 — 들어가는 쪽에 두면 아직 안 깎인 면을 "
             "식힌다.", mirror=("x",), color="aluminum",
             explode=(0.0, 200.0, 0.0), spec=f"40 × 40 × {w:.0f}",
             catalog=f"{UNIT_TAG}-AK-01"),
        Part("hood", "집진 후드", HEADS, "box", (420.0, 400.0, w),
             (hx - 620.0, 240.0, 0.0), "강판",
             f"벨트 나가는 쪽을 감싸 분진을 잡는다. 한 장에 "
             f"{swarf_kg_per_panel()} kg 이 나오고 후드가 "
             f"{hood_flow_m3h():,} m³/h 로 끌어낸다 — 포집률 {DUST_CAPTURE:.1%} "
             "는 안전 항목이 아니라 **품질 사양**이다.",
             mirror=("x",), color="shroud", explode=(0.0, 520.0, 0.0),
             spec=f"420 × 400 × {w:.0f} · {hood_flow_m3h():,} m³/h",
             catalog=f"{UNIT_TAG}-HD-01"),
        Part("duct", "집진 지관", outlets_per_head() * HEADS, "cylrow",
             (DUCT_D_MM, 420.0, DUCT_D_MM), (0.0, 640.0, 0.0), "강관",
             f"분진을 반송속도 위로 끌어낸다 — 느리면 덕트에 쌓여 그것이 "
             f"연료다. 헤드당 {outlets_per_head()} 개씩 "
             f"{outlets_per_head() * HEADS} 개가 "
             f"{DUCT_VELOCITY_M_S:.0f} m/s 를 지킨다.", axis="y",
             color="chrome", explode=(0.0, 700.0, 0.0),
             spec=f"Ø{DUCT_D_MM:.0f} · {DUCT_VELOCITY_M_S:.0f} m/s",
             catalog=f"{UNIT_TAG}-DT-01"),
        Part("gantry", "갠트리 빔 (X 왕복)", 1, "box",
             (520.0, 260.0, float(campaign.PANEL_WIDTH_MM) + 900.0),
             (0.0, 420.0, 0.0), "용접 각관",
             f"헤드 {HEADS} 대를 싣고 **판 위를 건넌다.** 판은 진공 테이블에 "
             f"물려 서 있으므로 움직이는 것은 이쪽이다 — 행정은 판 길이 "
             f"{campaign.PANEL_LENGTH_MM:,.0f} 에 헤드 간격 "
             f"{HEAD_PITCH_MM:,.0f} 과 오버트래블을 더한 값이고, 그래서 기계 "
             "길이가 판의 두 배 넘게 든다.",
             color="steel", explode=(0.0, 560.0, 0.0),
             spec=f"행정 {gantry_stroke_mm():,.0f} mm · {feed_mm_s():.1f} mm/s",
             catalog=f"{UNIT_TAG}-GT-01"),
        Part("motor", "헤드 주모터", HEADS, "cyl", (320.0, 520.0, 320.0),
             (hx, 300.0, w / 2.0 + 260.0), "IE3 3상유도",
             f"벨트를 돌린다. 헤드당 절삭 {power_per_head_kw()} kW 라 정격이 "
             f"{motor_rating_kw():.0f} kW 이고 두 대 합이 "
             f"{total_power_kw()} kW 다 — 벨트 폭 밖에 세워 집진 통로를 "
             "안 막는다.", axis="y",
             mirror=("x",), color="dark", explode=(0.0, 0.0, 520.0),
             spec=f"{motor_rating_kw():.0f} kW · Ø320 × 520",
             catalog=f"{UNIT_TAG}-MT-01"),
    ]
    return Unit(
        key="br305",
        name=f"{UNIT_TAG} 백시트 면 연마 유닛 — 진공 테이블 · 2 헤드",
        sheet=f"PV-{UNIT_TAG}-ASM-5101",
        envelope_mm=(machine_length_mm(), 1_500.0, w + 400.0),
        view_r_mm=2_300.0,
        principle=(
            ("① 흡착", f"진공 테이블이 유리면을 {VACUUM_KPA:.0f} kPa 로 빨아 "
                       f"당겨 판을 **펴고 잡는다** ({vacuum_hold_kn()} kN). 프레임은 "
                       f"{FRAME_REMOVED_AT} 에서 이미 빠졌으므로 면이 트여 있고, "
                       f"실란트 띠도 앞 걸음 {UPSTREAM_TAG} 가 걷어 놨다 — "
                       "안 걷혔으면 띠가 벨트를 먼저 맞는다."),
            ("② 측정", f"변위센서가 **백시트 윗면을 직접 잰다.** 테이블 높이를 "
                       f"기준으로 잡으면 재료 두께 공차 {BED_REFERENCE_TOL_MM} mm 가 "
                       f"남아 창 반폭 {depth_window_half_mm()} 의 "
                       f"{table_reference_margin()} 배 — **못 든다.** 재면 "
                       f"{measured_reference_margin()} 배가 된다."),
            ("③ 1 단 절삭", f"거친 벨트({GRITS[0]})가 절입 "
                            f"{depth_per_head_mm():.3f} mm 를 걷는다. 데워진 살이 "
                            f"그대로 칩이 되어 나간다 (δ/a = {skin_to_depth_ratio()})."),
            ("④ 한 축 추종", f"Z 축 하나가 잰 높이를 따라간다. 폭 방향 굴곡은 "
                          f"**테이블이 펴서 없앴으므로** 분할 압반 "
                          f"{platen_segments() * HEADS} 개가 필요 없다 — 둘은 "
                          "짝이고, 테이블이 못 펴면 압반이 돌아온다."),
            ("⑤ 2 단 절삭", f"고운 벨트({GRITS[1]})가 남은 절입을 걷는다. 가장 얕은 "
                            f"자리도 {min_depth_cut_mm()} mm 라 백시트 "
                            f"{BACKSHEET_T_MM} mm 가 **어디에도 안 남는다** — "
                            "남으면 파쇄돼 선별조로 간다."),
            ("⑥ 포집", f"후드가 {swarf_kg_per_panel()} kg/장을 "
                       f"{hood_flow_m3h():,} m³/h 로 끌어낸다. 포집률 "
                       f"{DUST_CAPTURE:.1%} 를 못 지키면 남은 가루가 필름보다 "
                       "**더 나쁜 형태**로 파쇄에 실린다 — 여기가 품질 사양이다."),
            ("⑦ 잔존 검사", f"비전이 면 전체를 훑어 **정말 없는지** 본다. "
                          f"{vision_min_patch_mm2()} mm² 를 잡는데 잣대는 집진이 "
                          f"놓치는 {escaped_fines_g_per_panel()} g 과 같은 무게인 "
                          f"{patch_that_weighs_like_the_leak_mm2():,.0f} mm² 다. "
                          "잡히면 되돌리는지 버리는지는 **안 들었다.**"),
            ("⑧ 인계", f"폴리머가 빠진 판이 {DOWNSTREAM_TAG} 로 간다. 파쇄 뒤 "
                       f"부유선별에 들어가는 폴리머가 "
                       f"{polymer_reduction_ratio():,.0f} 분의 일이 된다."),
        ),
        parts=tuple(parts))


def contact_unit() -> Unit:
    """벨트–적층 접촉부 — 배율 `CONTACT_MAG` 배. 0.45 mm 를 눈에 보이게 세운다.

    이 유닛만 배율이 걸린다. 적층이 5.5 mm 인데 걷는 것은 0.45 mm 라, 실제
    비율로 그리면 **깎는 층이 선 하나**가 된다. 그래서 키운다 — 키운 것은
    치수가 아니라 **화면**이고, 값은 전부 모델에서 온다.

    **두께(y)만 키운다.** 폭·깊이는 그대로다. 3D 연장이 배율을 스윕 단면에만
    먹이고 상자에는 안 먹이므로, 층을 상자로 세우는 이 유닛은 배율을 **부품
    치수에 직접 넣는다** — `sg_grind` 가 실란트 띠를 20 배로 그리는 것과 같은
    방식이다. 그래서 화면의 세로 치수는 읽으면 안 되고, 읽을 것은 **비율**이다.

    **공구(벨트·압반)는 배율을 안 먹인다.** 벨트 8 mm 를 60 배 키우면 480 mm 가
    되어 적층 전체보다 두꺼워진다. 실치수는 이름과 규격에 적는다.
    """
    m = CONTACT_MAG
    lo, hi = depth_window_mm()
    back_eva = BACK_EVA_T_MM
    cells = (sg_grind.STACK_T_MM - sg_grind.GLASS_T_MM
             - back_eva - BACKSHEET_T_MM)
    span = 900.0                                    # 화면에 세우는 폭
    # 층을 아래에서 위로 쌓는다 — 판 윗면이 y = 0 이므로 전부 음수다.
    y_back = -BACKSHEET_T_MM / 2.0 * m
    y_beva = (-BACKSHEET_T_MM - back_eva / 2.0) * m
    y_cell = (-BACKSHEET_T_MM - back_eva - cells / 2.0) * m
    y_glass = (-BACKSHEET_T_MM - back_eva - cells
               - sg_grind.GLASS_T_MM / 2.0) * m
    parts = (
        Part("cbacksheet", f"백시트 t{BACKSHEET_T_MM} (걷는 것)", 1, "box",
             (span, BACKSHEET_T_MM * m, 300.0), (0.0, y_back, 0.0),
             "불소층 + PET 심재",
             f"**이 층이 관문이다.** 목표 절입 {TARGET_DEPTH_MM} mm 가 이 "
             f"{BACKSHEET_T_MM} mm 를 넘어야 하고, 가장 얕은 자리도 "
             f"{min_depth_cut_mm()} mm 라 어디에도 안 남는다.",
             color="orange", explode=(0.0, 320.0, 0.0),
             spec=f"t{BACKSHEET_T_MM} · 창 {lo}~{hi} mm", catalog="—"),
        Part("cbackeva", f"배면 EVA t{back_eva} (넘쳐도 되는 층)", 1, "box",
             (span, back_eva * m, 300.0), (0.0, y_beva, 0.0), "EVA",
             f"백시트를 다 걷고도 {round(hi - TARGET_DEPTH_MM, 3)} mm 가 남는 "
             "여유층이다. 넘쳐 들어가도 급광에 없던 것을 새로 만들지 않는다 — "
             "`overshoot_into_eva_adds_nothing()`.",
             color="rubber", explode=(0.0, 180.0, 0.0),
             spec=f"t{back_eva} · 여유 {round(hi - TARGET_DEPTH_MM, 3)} mm",
             catalog="—"),
        Part("ccell", "셀 + 전면 EVA (건드리면 안 되는 층)", 1, "box",
             (span, cells * m, 300.0), (0.0, y_cell, 0.0), "실리콘 셀 + EVA",
             f"여기까지 내려가면 은과 실리콘이 깨진다. 창 상한 {hi} mm 가 "
             "이 면 위에서 닫히는 이유다.",
             color="dark", explode=(0.0, -160.0, 0.0),
             spec=f"t{round(cells, 3)}", catalog="—"),
        Part("cglass", f"유리 t{sg_grind.GLASS_T_MM}", 1, "box",
             (span, sg_grind.GLASS_T_MM * m, 300.0), (0.0, y_glass, 0.0),
             "소다석회",
             "이 유닛은 유리를 안 건드린다. 유리는 다음 걸음 "
             f"({DOWNSTREAM_TAG}) 이 맡는다.",
             color="ghost", explode=(0.0, -420.0, 0.0),
             spec=f"t{sg_grind.GLASS_T_MM}", catalog="—"),
        # 공구는 배율을 안 먹인다 — 벨트 8 mm 를 60 배 키우면 480 mm 가 되어
        # 적층 전체(330 mm)보다 두꺼워진다. 읽히는 크기로 그리고 실치수는 적는다.
        Part("cbelt", f"연마 벨트 (접촉 단면 · 실제 t{BELT_T_MM:.0f})", 1, "box",
             (span, 120.0, 300.0), (0.0, 60.0, 0.0),
             "산화알루미늄 오픈코트",
             f"판 **위에서** 내려온다. 절입 {TARGET_DEPTH_MM} mm 만큼 층을 "
             f"먹으면 그 살이 칩이 되어 나간다 — 열침투 "
             f"{thermal_skin_mm()} mm 가 절입의 "
             f"{skin_to_depth_ratio()} 배라 데워진 살이 그대로 떨어진다.",
             color="steel", explode=(0.0, 260.0, 0.0),
             spec=f"실제 t{BELT_T_MM} · {'/'.join(GRITS)} · 그림은 공구 배율 없음",
             catalog="—"),
        Part("czprobe", "윗면 변위센서 (Z 추종)", 1, "box",
             (160.0, 200.0, 300.0), (span / 2.0 - 120.0, 220.0, 0.0),
             "레이저 변위센서",
             f"**백시트 윗면을 직접 잰다.** 테이블 면을 기준으로 잡으면 재료 "
             f"두께 공차 {BED_REFERENCE_TOL_MM} mm 가 남아 창 반폭 "
             f"{depth_window_half_mm()} 의 {table_reference_margin()} 배로 "
             f"**못 든다** — 진공은 판을 펴 줄 뿐 두께를 못 바꾼다. 재면 "
             f"{Z_SENSOR_TOL_MM} mm 라 여유가 {measured_reference_margin()} 배다.",
             color="orange", explode=(0.0, 420.0, 0.0),
             spec=f"합 오차 {Z_SENSOR_TOL_MM} · 여유 {measured_reference_margin()} 배",
             catalog=f"{UNIT_TAG}-ZP-01"),
        Part("ctable", "진공 테이블 면 (유리면 지지)", 1, "box",
             (span, 90.0, 300.0), (0.0, y_glass - sg_grind.GLASS_T_MM / 2.0 * m - 45.0,
                                   0.0), "알루미늄 + 실링 패드",
             f"판을 **면으로** 당겨 편다. 그래서 폭 방향 굴곡이 없어지고 깊이를 "
             f"한 축으로 잡을 수 있다 — 분할 압반 {platen_segments() * HEADS} 개가 "
             f"여기서 빠졌다. 다만 **두께 공차는 못 없앤다.**",
             color="frame", explode=(0.0, -520.0, 0.0),
             spec=f"{VACUUM_KPA:.0f} kPa · {vacuum_hold_kn()} kN",
             catalog=f"{UNIT_TAG}-VT-01"),
        Part("cchip", "걷힌 칩", 1, "box",
             (span / 3.0, TARGET_DEPTH_MM * m, 300.0),
             (-span / 2.0 + span / 6.0, 150.0, 0.0),
             "불소·PET 가루",
             f"한 장에 {swarf_kg_per_panel()} kg 이 이 두께에서 나온다. **없애는 "
             f"것이 아니라 가루로 바꾼다** — 포집 {DUST_CAPTURE:.1%} 를 놓친 "
             f"몫 {escaped_fines_g_per_panel()} g 은 필름보다 나쁜 형태로 "
             "파쇄에 실린다.",
             color="rubber", explode=(0.0, 640.0, 0.0),
             spec=f"{swarf_kg_per_panel()} kg/장 · 누출 "
                  f"{escaped_fines_g_per_panel()} g", catalog="—"),
    )
    return Unit(
        key="contact",
        name=f"벨트–적층 접촉부 (배율 {CONTACT_MAG:.0f} 배)",
        sheet=f"PV-{UNIT_TAG}-DET-5102",
        envelope_mm=(span, 700.0, 300.0), view_r_mm=680.0,
        principle=(
            ("① 층", f"위에서 백시트 {BACKSHEET_T_MM} · 배면 EVA {back_eva} · "
                     f"셀+전면 EVA {round(cells, 3)} · 유리 "
                     f"{sg_grind.GLASS_T_MM} 다. "
                     f"걷어야 할 것은 맨 위 {BACKSHEET_T_MM} mm 뿐이다. "
                     f"**두께만 {CONTACT_MAG:.0f} 배로 그렸다** — 폭은 그대로라 "
                     "화면의 세로는 읽지 말고 층 사이 비율을 읽는다."),
            ("② 창", f"그래서 깊이 창이 **{lo}~{hi} mm** 다 — 아래로는 백시트를 "
                     f"다 걷어야 하고 위로는 셀에 닿기 전에 멈춰야 한다. 폭 "
                     f"{round(hi - lo, 3)} mm."),
            ("③ 기준면", f"**윗면을 잰다.** 진공 테이블이 판을 펴 주지만 재료 "
                        f"두께 공차 {BED_REFERENCE_TOL_MM} mm 는 그대로 남아 "
                        f"테이블 기준으로는 {table_reference_margin()} 배 — "
                        f"못 든다. 윗면을 재면 {Z_SENSOR_TOL_MM} mm 로 "
                        f"{measured_reference_margin()} 배다."),
            ("④ 절삭", f"벨트가 절입 {TARGET_DEPTH_MM} mm 를 먹는다. 접촉 호 "
                       f"{contact_arc_mm()} mm 를 {contact_time_s() * 1_000:.2f} ms "
                       f"에 지나므로 열침투가 {thermal_skin_mm()} mm — 절입의 "
                       f"{skin_to_depth_ratio()} 배라 데워진 살이 그대로 칩이 된다."),
            ("⑤ 남기지 않는다", f"가장 얕게 깎이는 자리도 {min_depth_cut_mm()} mm "
                            f"라 백시트가 **어디에도 안 남는다**. 가장 깊은 자리는 "
                            f"{max_depth_cut_mm()} mm 로 창 상한 {hi} 아래다."),
            ("⑥ 가루로 바뀐다", f"걷힌 살은 없어지는 것이 아니라 "
                           f"{swarf_kg_per_panel()} kg/장의 가루가 된다. 포집을 "
                           f"놓친 {escaped_fines_g_per_panel()} g 이 이 유닛의 "
                           "진짜 위험이다 — 미립자는 필름보다 나쁘다."),
        ),
        parts=parts)


def units() -> tuple[Unit, ...]:
    """도면이 세우는 유닛 — 기계 전경과 접촉부."""
    return (unit(), contact_unit())


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
