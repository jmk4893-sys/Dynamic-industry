# -*- coding: utf-8 -*-
"""SG-301 엣지 연마 — **어떻게 갈리는가**를 푸는 모델.

AFR-101 이 프레임을 뜯어내면 라미네이트의 네 변에 유리 절단면이 그대로 남는다.
SG-301 은 그 변을 다이아몬드 형상휠로 훑어 **잔사를 걷고 모서리를 죽인다**.
통합 설계도에서 이 장비는 상자 두 개(`SG-301` 몸체와 `SG-3T` 횡행 헤드)였고,
"어떻게 작동하는가" 는 부품표 글자에만 있었다 — 3,000 rpm, 300 mm/s, 2.2 kW.

이 모듈은 그 세 수를 **서로 견준다.** 연마는 세 가지가 동시에 맞아야 성립한다:

1. **동력** — 제거하는 부피에 비에너지를 곱한 값이 스핀들 정격 안에 들어야 한다.
2. **영역** — 등가 칩두께가 연성-취성 한계 어디에 서는가가 표면이 갈릴지
   깨질지를 정한다.
3. **시간** — 세 면(장변 2 · 단변 2)의 점유 합이 AFR 정반 점유 안에 들어야 한다.

풀어 보면 셋이 서로를 묶는다. 그래서 통과속도 300 mm/s 는 컨베이어가 정한
값이 아니라 **스핀들이 정한 값**이고 (한계 대비 여유 6 %), 갈린 면은 취성
파괴면이라 (한계의 20 배) 모서리를 죽이는 아리스가 선택이 아니라 필수다.

    PYTHONPATH=src python -c "from pv_preprocess import sg_grind; print(sg_grind.summary())"

값의 출처는 셋으로 갈라 적는다 — 다른 모듈에서 온 것, 카탈로그 계획값,
그리고 물성 문헌값. 계획값은 시운전 run-at-rate(R-04)이 덮어쓴다.
"""

from __future__ import annotations

import math

from . import afr, campaign, frames, recipe, reliability
from .afr_units import Part, Unit

# ── 스핀들·휠 — 카탈로그 계획값 ─────────────────────────────────────────
#: 다이아몬드 형상휠 외경 (mm). 3,000 rpm 에서 주속 23.6 m/s 가 나오는 크기다 —
#: 유리 연삭의 통상 주속대(20–35 m/s)에 들어간다.
WHEEL_D_MM = 150.0
#: 휠 폭 (mm) 과 사용 한계 외경 (mm). 한계까지 반경 8 mm 를 쓴다.
WHEEL_W_MM = 25.0
WHEEL_SPENT_D_MM = 134.0
#: 휠 보어 (mm) — 스핀들 아버.
WHEEL_BORE_MM = 32.0
#: 다이아몬드 입도 (µm) — D91(170/200 mesh) 상당, 메탈본드.
GRIT_UM = 91.0

#: 스핀들 회전수 (rpm)·정격 (kW)·대수. 통합 설계도 `MTR-SG-SP` 와 집진 DS-01 의
#: 정본이 여기다 — 장변 2 대가 동기, 단변 1 대가 횡행한다.
SPINDLE_RPM = 3_000.0
SPINDLE_KW = 2.2
SPINDLE_COUNT = 3
LONG_HEADS = 2
SHORT_HEADS = 1
#: 인버터 구동 스핀들에서 실제로 절삭에 쓰이는 몫 — 기계손실·여유.
SPINDLE_EFFICIENCY = 0.80

#: 연마재가 폴리머에 닿아도 되는 주속의 통상 상한 (m/s). 폴리머는 마찰열을
#: 못 흘려 이 위에서는 접촉점이 융점을 넘고 녹은 살이 결합제를 메운다.
POLYMER_RUB_LIMIT_M_S = 5.0

#: 라미네이트 두께 편차 (mm) — 반입물 공차, 계획값.
LAMINATE_TOL_MM = 0.20
#: 롤러 상면 평면도 + 판 휨 (mm) — 계획값.
ROLLER_PLANE_TOL_MM = 0.30
#: 면을 누를 때 셀이 견디는 접촉압 (MPa) 과 패드 접촉 길이 (mm) — 계획값.
FACE_SAFE_MPA = 0.05
FACE_PAD_LEN_MM = 40.0

# ── 갈아내는 형상 — 계획값 ──────────────────────────────────────────────
#: 유리 두께 (mm) — `afr.LAMINATE_T_MM` 이 정본이다.
GLASS_T_MM = float(afr.LAMINATE_T_MM)
#: 라미네이트 적층 두께 (mm) — 유리 + EVA/셀 + 백시트. `frames` 가 정본이다.
STACK_T_MM = float(frames.LAMINATE_STACK_MM)
#: 백시트 두께 (mm) — PVF/PET/PVF 3층의 계획값. 저장소에 값이 없어 여기서 정한다.
BACKSHEET_T_MM = 0.32
#: 백시트 폴리머의 낮은 쪽 융점 (°C) — PVF. 이 위로 문지르면 녹아 휠에 먹는다.
BACKSHEET_MELT_C = 200.0
#: 백시트 폴리머 밀도 (g/mm³) — PVF/PET 3층의 대표값. 분진 질량에만 쓴다.
BACKSHEET_DENSITY_G_MM3 = 1.78e-3
#: 백시트–EVA 계면의 파괴에너지 (N/mm). 한때 근거 없이 0.5 로 두었는데
#: **문헌값의 4~20 분의 1 이었다** — 신품 180° 박리가 60~100 N/cm(6~10 N/mm)
#: 이고 습열 300 h 뒤에도 20 N/cm(2 N/mm)다. 정본을 `br_peel.INTERFACES` 로
#: 옮겼다. 거기에는 계면이 여럿이고, 어느 면에서 뜯느냐가 20 배를 가른다.

# ── 면 연마 라인 — 남의 설비에서 가져온 상수 ────────────────────────────
#
#   아래 다섯은 이 라인의 설계값이 아니라 **바깥에서 돌아가는 설비**의 값이다.
#   면 전체를 갈아내는 공법이 실재하는지가 먼저 걸리는 물음이라 그것부터 적는다.
#
#   ① CEA 가 개발하고 ENVIE 2E Aquitaine 이 2025-07 부터 돌리는 연마 라인
#      (EVERPV). 넓은 연마 벨트를 고속으로 돌려 유리 위의 층을 **분말**로
#      걷어낸다. 1 만 장 넘게 처리해 유리 100 t 을 잔사 없는 컬릿으로 냈다.
#      → 면 전체 연마는 가설이 아니라 가동 중인 공법이다.
#   ② Leoben 의 밀링 연구. 백시트를 **먼저** 떼면 뒤따르는 열박리 시간이
#      모든 온도에서 45 % 넘게 줄고, 고형 잔사가 줄며 배가스가 순해진다.
#      → 면을 걷는 값은 순증이 아니다. 하류에서 돌려받는다.
#
#   그래서 이 절은 면 연마를 이 라인에 얹는 **추가 부하**로 세지 않는다.
#   자기 정반·자기 택트를 갖는 **대안 아키텍처**로 놓고, 쓰는 값과
#   돌려받는 값을 함께 센다.

#: 면 연마 설비의 장당 정반 점유 (s) — 실증 라인 1 장/분.
FACE_ABRADE_TACT_S = 60.0
#: 그 라인의 이송속도 (mm/s) — 2.3 m/min.
FACE_ABRADE_FEED_MM_S = 38.3
#: 그 라인이 받는 패널 폭 상한 (mm) — 기계 개구부. 이 라인의 패널이 넘는다.
FACE_ABRADE_OPENING_MM = 1_300.0
#: 면 연마의 비에너지 (J/mm³) — **역산한 추정치**다. 벨트 모터 정격이 공개돼
#: 있지 않아, 태양광 재활용 공정 전체가 130~300 kWh/t 안에서 돈다는 보고된
#: 범위를 연마 한 단계에 배분해 얻었다. 실측 전력이 오면 여기만 고친다.
#: 실란트의 `SEALANT_ABRADE_J_MM3` 와 자릿수가 다른 것이 맞다 — 그쪽은 경화
#: 실리콘을 좁은 띠에서 긁어내는 값이고, 이쪽은 무른 폴리머를 넓은 벨트로
#: 얕게 걷어내는 값이다. 띠의 상수를 면에 그대로 빌려 쓰면 위로 크게 틀린다.
BACKSHEET_ABRADE_J_MM3 = 1.6
#: 백시트를 먼저 걷었을 때 하류 열박리에서 돌려받는 몫. 보고된 값이
#: "모든 온도에서 45 % 넘게 감소" 이므로 그 경계값을 쓴다 — 낮게 잡은 쪽이다.
BACKSHEET_FIRST_HEAT_SAVING = 0.45

# ── 프레임이 남기고 간 실란트 — `frames` 의 슬롯 치수가 정본 ───────────
#: 프레임 슬롯이 라미네이트 **면**을 덮는 폭 (mm). 인발은 응집파괴라 이 폭만큼
#: 실란트가 면에 남는다 — 변에만 남는 것이 아니다.
SEALANT_BAND_MM = float(frames.SLOT_LIP_MM)
#: 면당 실란트 두께 (mm) — 슬롯이 적층보다 이만큼씩 높다.
SEALANT_FACE_T_MM = float(frames.SEALANT_T_MM)
#: 인발 뒤 라미네이트 쪽에 남는 몫 — 응집파괴면이 가운데 근처에서 갈린다는 계획값.
#: **관찰 전 값이다.** 위험을 1.0(전량 잔류) 쪽으로 잡아 뒀는데, 현장은 반대쪽이
#: 맞다고 한다 — `SEALANT_PARTS_WITH_THE_FRAME` 아래를 본다. 이 상수와 폭
#: `SEALANT_BAND_MM` 은 **그대로 둔다**: SR-302 의 날 폭·슈·부품표가 여기에
#: 걸려 있고, 유닛을 지울지는 아직 발주처 몫이다. 관찰값은 옆에 따로 적는다.
SEALANT_RETAINED = 0.5

# ── 현장 관찰 — 인발 뒤 면에 남는 것은 띠가 아니라 선이다 ────────────────
#
#   발주처 관찰: **실란트는 거의 전부 알루미늄 프레임에 붙어서 떨어지고,
#   면에는 아주 얇은 선 모양으로만 남는다.**
#
#   이것이 두 가지를 동시에 부정한다 —
#
#   ① **파괴면.** 응집파괴(실란트 가운데가 갈린다)가 아니라 **계면파괴**다.
#      갈라지는 자리가 실란트 속이 아니라 실란트–라미네이트 경계다. 그래서
#      남는 몫이 `SEALANT_RETAINED` 0.5 보다 훨씬 작다.
#   ② **형상.** 슬롯 립이 면을 20 mm 덮고 있었어도 남는 것이 그 폭 전체를
#      덮지 않는다. 립 끝에서 전단된 자리에 **선**으로 남는다. 넓이가 아니라
#      길이만 둘레를 따라간다.
#
#   ①만 맞고 ②가 틀리면 (얇지만 20 mm 폭) 이야기가 다르다 — 그래서 둘을
#   따로 적었다. 두 값 다 **실측 전**이고, 아래 두 상수가 그 자리다.
#: 실란트가 프레임 쪽으로 떨어지는가 — 발주처 현장 관찰. 내가 정한 값이 아니다.
SEALANT_PARTS_WITH_THE_FRAME = True
#: 그래서 파괴가 응집이 아니라 계면인가 — ① 의 기록.
SEALANT_FAILURE_IS_INTERFACIAL = True
#: 남는 것이 띠가 아니라 선인가 — ② 의 기록.
RESIDUE_IS_A_LINE = True
#: 그 선의 폭 (mm) — **실측 전 계획값.** 립 끝에서 전단된 자리라 보고 잡았다.
#: 이 값은 첨두 동력을 바꾸지 않는다 (`br_abrade` 가 그 쪽을 센다) — 바꾸는 것은
#: 첨두가 **얼마나 오래**인가, 즉 관성이 받아 줄 수 있는 에너지다.
RESIDUE_LINE_W_MM = 2.0
#: 그 선의 높이 (mm) — **실측 전 계획값.** "아주 얇은" 을 원래 1.5 mm 의
#: 1/7 쯤으로 읽었다. 첨두 동력을 정하는 것은 **이 값 하나**다.
RESIDUE_LINE_H_MM = 0.2
#: 아리스(모따기) 다리 길이 (mm) · 각도 (°). 45° 한 곳 — 유리의 **바깥면 쪽**
#: 모서리만 죽인다. 반대쪽 모서리는 EVA 와 만나므로 거기까지 파면 폴리머가
#: 휠에 먹는다. 연마 높이 공차 ±0.10 mm 가 있는 이유가 이것이다.
ARRIS_MM = 0.5
ARRIS_DEG = 45.0
ARRIS_COUNT = 1
#: 공정이 아리스를 **요구하는가** — 발주처 확인 결과 거짓이다.
#:
#: 위 세 수는 아리스를 **어떻게** 만드는가이고 이것은 **왜** 만드는가다. 후보로
#: 셋을 들었고 셋 다 아니라고 돌아왔다 — ① 취급 안전 · ② 파편 억제 ·
#: ③ 하류 유리 제거(GRM-401)가 날카로운 변을 싫어한다. 받은 값이고 내가 정한
#: 것이 아니다.
#:
#: `arris_is_required()` 와 섞지 않는다. 그쪽은 **「간다면 필수」**(칩두께가
#: 연성한계를 넘으니 파단면이 서고, 파단면이면 모서리를 죽여야 한다)이고
#: 이쪽은 **「갈 이유」** 다. 앞의 것은 조건문의 귀결, 뒤의 것은 전건이다.
ARRIS_REQUIRED_BY_PLANT = False
#: 변 끝면에서 걷어내는 살 (mm) — 프레임 인발이 남긴 잔사와 미세 파단면.
STOCK_MM = 0.03

#: 휠 홈의 위쪽 여유 (mm) — 유리 바깥면 위로 남기는 틈.
GROOVE_CLEAR_MM = 0.3
#: 홈 아래 어깨의 **도피** (mm) — 유리/EVA 계면보다 이만큼 밑에 선다.
#: 어깨가 계면 위로 올라가면 유리대 아랫부분이 안 갈리고, 너무 내려가면 EVA 를
#: 문다. 그래서 도피는 연마 높이 공차보다 커야 한다.
GROOVE_RELIEF_MM = 0.15
#: 연마 높이 세팅 공차 (mm) — 통합 설계도 GA 의 `연마 높이 ±0.10` 이 정본.
HEIGHT_TOL_MM = 0.10
#: 홈 깊이 (mm) — 유리 변이 이만큼 물린다.
GROOVE_ROOT_MM = 6.0
#: 플랜지가 유리대 위·아래로 더 나오는 높이 (mm).
GROOVE_LIP_MM = 1.2
#: 홈 바닥 뒤 림 살 두께 (mm).
GROOVE_BODY_MM = 2.5

# ── 유리 물성 — 문헌값 (소다석회) ───────────────────────────────────────
#: 탄성계수 (GPa)·경도 (GPa)·파괴인성 (MPa·m^0.5).
GLASS_E_GPA = 72.0
GLASS_H_GPA = 5.5
GLASS_KC_MPA_M05 = 0.75
#: 비연삭에너지 (J/mm³) — 취성영역 다이아몬드 연삭의 계획값. **이 값이 이
#: 모듈에서 가장 불확실하다** — 30 이면 통과속도를 265 mm/s 로 내려야 한다.
SPECIFIC_ENERGY_J_MM3 = 25.0
#: 연삭 접선력/법선력 비 — 유리·다이아몬드의 통상값.
FORCE_RATIO = 0.35

#: 휠 교체 주기 (개월) — `reliability` SP-03 예비품 계획.
WHEEL_SERVICE_MONTHS = 4
#: 휠 교체 주기 안에 지나가는 장수는 `reliability` 가 정한다. 여기에 수를 베껴
#: 두었더니 REV.59 가 가용률을 고쳐 283,487 → 282,727 로 움직였는데 이 상수만
#: 옛 수로 남았다 — 그래서 베끼지 않고 부른다.

#: 접촉 단면에 세우는 판 안쪽 길이 (mm) — 림 단면과 눈에 비슷하게 잡는다.
SECTION_DEPTH_MM = 26.0

#: 횡행 레일 두 줄의 중심 거리 (mm) — 캐리지가 모멘트를 받으려면 갈라져야 한다.
RAIL_SPAN_MM = 220.0

#: 줄지어 놓는 부품의 간격 (mm) — 반출롤러 피치와, 접촉 단면에 세우는 입자 간격.
ROW_PITCH_MM = {"roll": 200.0, "grit": 26.0}

#: 유닛별 기본 시점 방향 (시점 반경의 배수). 접촉부는 **단면**이라 스윕 축(x)을
#: 거의 따라 봐야 형상이 옆모습으로 읽힌다 — 비스듬히 보면 슬래브 하나가 된다.
VIEW_DIR = {
    # 통과기는 **이송 방향(x)을 따라** 봐야 양쪽 헤드가 좌우로 갈려 한눈에 든다.
    # 비스듬히 보면 가까운 헤드가 화면을 먹고 먼 헤드가 작아진다.
    "long": (1.15, 0.62, 0.22),
    "short": (1.05, 0.60, 0.35),
    # 접촉부는 스윕 축 쪽에서 봐야 단면이 읽히되, 완전히 축을 따라가면 두 몸이
    # 겹쳐 보인다 — 살짝 틀어 홈과 유리대가 갈리게 한다.
    "contact": (1.45, 0.52, 0.55),
    # 스크레이퍼는 이송축(x)을 따라 늘어선 순서 — 날 → 리드 → 휠 — 이 보여야
    # 하므로 옆에서 본다.
    "scraper": (0.45, 0.70, 1.25),
}

#: 접촉부 확대도의 배율 — 실제 0.5 mm 아리스는 휠 Ø150 옆에서 안 보인다.
#: `afr_peel` 의 표시 과장과 같은 성격이고, 형상은 실제 그대로다.
CONTACT_MAG = 20.0


# ── 집진 — `dust` 가 정본이라 부른다 ────────────────────────────────────
def dust_flow_m3h() -> int:
    """SG-301 국소집진 풍량 (m³/h).

    여기에 1,000 을 베껴 두었더니 후드가 한 대 몫에서 두 대 몫으로 늘 때
    이 상수만 옛 수로 남았다. `dust` 의 DS-01 이 정본이므로 부른다.
    """
    from . import dust
    return [s.flow_m3h for s in dust.STREAMS if s.tag == "DS-01"][0]


# ── 운동학 ──────────────────────────────────────────────────────────────
def wheel_speed_m_s() -> float:
    """휠 주속 v_s = πDn/60 (m/s)."""
    return round(math.pi * WHEEL_D_MM * SPINDLE_RPM / 60_000.0, 3)


def speed_ratio(feed_mm_s: float) -> float:
    """속도비 q = v_s / v_w — 연삭이 절삭과 갈리는 자리다."""
    return round(wheel_speed_m_s() * 1_000.0 / feed_mm_s, 1)


def long_feed_mm_s() -> float:
    """장변 통과 속도 (mm/s) — `campaign` 이 정본."""
    return float(campaign.SG_PASS_MM_S)


def short_feed_mm_s() -> float:
    """단변 횡행 속도 (mm/s) — `campaign` 이 정본."""
    return float(campaign.SG_SWEEP_MM_S)


# ── 갈아내는 단면 ───────────────────────────────────────────────────────
def arris_face_mm() -> float:
    """아리스 경사면의 폭 (mm) — 45° 면은 다리보다 √2 배 길다."""
    return round(ARRIS_MM / math.cos(math.radians(90.0 - ARRIS_DEG)), 4)


def contact_width_mm() -> float:
    """휠이 유리에 닿는 폭 a_p (mm) — 끝면 + 아리스 경사면."""
    return round(GLASS_T_MM + ARRIS_COUNT * arris_face_mm(), 4)


def removal_area_mm2() -> float:
    """변 1 mm 당 걷어내는 단면적 A (mm²) — 끝면 살 + 아리스 삼각형.

    형상휠은 한 번에 최종 단면을 만든다. 그러니 제거량은 '절입 깊이'가 아니라
    **단면적**이다 — 아리스 삼각형이 끝면 살보다 크다는 것이 여기서 드러난다.

    홈 바닥은 도피만큼 EVA 도 스치지만 그 몫은 **동력에 안 넣는다.** 폴리머의
    비절삭에너지는 유리의 두 자리 아래이고, EVA 가 문제되는 것은 힘이 아니라
    휠에 먹어 붙는 오염이다. 그것은 도피와 높이 공차로 막는다.
    """
    return round(STOCK_MM * GLASS_T_MM + ARRIS_COUNT * ARRIS_MM ** 2 / 2.0, 6)


def relief_covers_tolerance() -> bool:
    """홈 아래 어깨 도피가 연마 높이 공차를 덮는가 — 덮어야 유리대를 다 문다."""
    return GROOVE_RELIEF_MM > HEIGHT_TOL_MM


def eva_skim_mm() -> float:
    """가장 나쁜 세팅에서 홈이 스치는 EVA 두께 (mm)."""
    return round(GROOVE_RELIEF_MM + HEIGHT_TOL_MM, 4)


def arris_share() -> float:
    """제거 단면에서 아리스가 차지하는 몫 — 동력을 무엇이 먹는가."""
    return round(ARRIS_COUNT * ARRIS_MM ** 2 / 2.0 / removal_area_mm2(), 4)


def equivalent_depth_mm() -> float:
    """등가 절입 a_e = A / a_p (mm) — 단면을 접촉폭에 고르게 편 깊이."""
    return round(removal_area_mm2() / contact_width_mm(), 6)


def contact_length_mm() -> float:
    """접촉 호 길이 l_c = √(a_e · D) (mm)."""
    return round(math.sqrt(equivalent_depth_mm() * WHEEL_D_MM), 4)


# ── 동력 ────────────────────────────────────────────────────────────────
def removal_rate_mm3_s(feed_mm_s: float) -> float:
    """재료 제거율 Q = A · v_w (mm³/s)."""
    return round(removal_area_mm2() * feed_mm_s, 4)


def cutting_power_w(feed_mm_s: float) -> float:
    """절삭 동력 P = e_c · Q (W)."""
    return round(SPECIFIC_ENERGY_J_MM3 * removal_rate_mm3_s(feed_mm_s), 1)


def spindle_available_w() -> float:
    """스핀들이 절삭에 내줄 수 있는 동력 (W)."""
    return round(SPINDLE_KW * 1_000.0 * SPINDLE_EFFICIENCY, 1)


def utilisation(feed_mm_s: float) -> float:
    """스핀들 이용률 — 1 을 넘으면 그 속도로는 못 간다."""
    return round(cutting_power_w(feed_mm_s) / spindle_available_w(), 4)


def max_feed_mm_s() -> float:
    """스핀들 정격이 허용하는 최대 이송 (mm/s)."""
    return round(spindle_available_w() / (SPECIFIC_ENERGY_J_MM3 * removal_area_mm2()), 1)


def feed_margin() -> float:
    """설계 통과속도가 그 한계에서 얼마나 떨어져 있는가 (비율)."""
    return round(max_feed_mm_s() / long_feed_mm_s() - 1.0, 4)


def feed_is_spindle_bound() -> bool:
    """통과속도를 정한 것이 스핀들인가 — 여유 15 % 미만이면 그렇다."""
    return feed_margin() < 0.15


def specific_energy_that_stalls() -> float:
    """설계 속도를 못 내게 만드는 비에너지 (J/mm³) — 불확실성의 크기."""
    return round(spindle_available_w() / removal_rate_mm3_s(long_feed_mm_s()), 2)


# ── 연성·취성 영역 ──────────────────────────────────────────────────────
def chip_thickness_mm(feed_mm_s: float) -> float:
    """등가 칩두께 h_eq = a_e · v_w / v_s (mm)."""
    return round(equivalent_depth_mm() * feed_mm_s / 1_000.0 / wheel_speed_m_s(), 8)


def ductile_limit_mm() -> float:
    """연성-취성 한계 절입 d_c = 0.15 (E/H)(K_c/H)² (mm) — Bifano 식.

    유리에서 이 값보다 얇게 깎으면 소성으로 흐르고, 두꺼우면 균열로 떨어진다.
    """
    e_pa, h_pa = GLASS_E_GPA * 1e9, GLASS_H_GPA * 1e9
    kc_pa = GLASS_KC_MPA_M05 * 1e6
    return round(0.15 * (e_pa / h_pa) * (kc_pa / h_pa) ** 2 * 1_000.0, 8)


def brittleness_ratio(feed_mm_s: float) -> float:
    """칩두께가 연성한계의 몇 배인가."""
    return round(chip_thickness_mm(feed_mm_s) / ductile_limit_mm(), 2)


def is_brittle(feed_mm_s: float) -> bool:
    """갈린 면이 파단면인가."""
    return brittleness_ratio(feed_mm_s) > 1.0


def arris_is_required() -> bool:
    """아리스가 선택이 아니라 필수인가 — 취성 파단면이면 모서리를 죽여야 한다."""
    return is_brittle(long_feed_mm_s())


# ── 공정은 아리스를 요구하지 않는다 — 물리 주장과 다른 명제다 ───────────
def the_arris_has_no_requirement() -> tuple[str, ...]:
    """위 판정이 판정한 것이 무엇이었는지 — 공정 요구가 아니었다.

    `arris_is_required()` 는 공정을 읽지 않는다. 읽는 것은 통과속도 하나이고,
    그 속도의 칩두께가 연성한계의 몇 배인가만 본다. 그래서 그것이 참인 것은
    **「갈면 파단면이 나오니 모서리를 죽여야 한다」** 이다 — 가는 것을 전제한
    필수, 즉 자기참조다.

    전제가 빠지면 결론이 뒤집히는 것이 아니라 **물음이 사라진다.** 그러니
    여기서 `arris_is_required()` 를 거짓으로 바꾸지 않는다. 물리는 그대로다 —
    300 mm/s 로 유리를 갈면 면은 여전히 파단면이다. 바뀐 것은 **갈 이유**다.
    """
    lf = long_feed_mm_s()
    return (
        f"물리 주장 · `arris_is_required()` = {arris_is_required()} — 칩두께 "
        f"{chip_thickness_mm(lf) * 1_000:.3f} µm 가 연성한계 "
        f"{ductile_limit_mm() * 1_000:.4f} µm 의 {brittleness_ratio(lf)} 배다. "
        "**간다면** 파단면이고, 파단면이면 모서리를 죽여야 한다.",
        f"공정 요구 · `ARRIS_REQUIRED_BY_PLANT` = {ARRIS_REQUIRED_BY_PLANT} — "
        "후보 셋(취급 안전 · 파편 억제 · 하류 유리 제거)이 다 아니라고 돌아왔다.",
        "두 명제는 독립이다. 앞은 조건문의 귀결이고 뒤는 그 조건문을 부를 "
        "이유다. 이유가 없으면 귀결이 거짓이 되는 게 아니라 **전건이 안 선다** — "
        "엣지 연마를 할 까닭이 없어진다.",
        "그래서 이 함수는 판정을 안 내린다. SG-301 이 남는가는 발주처가 "
        "정할 일이고, 여기 적는 것은 그 결정이 무엇을 건드리는지다.",
    )


def what_the_absent_arris_releases() -> tuple[tuple[str, str], ...]:
    """아리스를 안 만든다면 이 모듈의 무엇이 풀리는가 — 값으로 센다.

    아리스는 이 모듈에서 가장 많은 것을 정한 형상이다. 단면적의 절반 이상이고,
    통과속도의 상한이고, 휠 어깨가 있는 이유이고, 실란트와 부딪치는 이유다.
    그것이 빠지면 네 가지가 같이 풀린다.
    """
    lf = long_feed_mm_s()
    stock_only = round(STOCK_MM * GLASS_T_MM, 6)
    return (
        ("제거 단면이 절반 이하로 줄어든다",
         f"{removal_area_mm2()} mm² 중 {arris_share() * 100:.0f} % 가 아리스 "
         f"삼각형이다. 끝면 살만 남기면 {stock_only} mm² — "
         f"{removal_area_mm2() / stock_only:.1f} 분의 1 이다."),
        ("통과속도를 스핀들이 안 정한다",
         f"지금 300 mm/s 는 스핀들이 정한 값이다 — 이용률 "
         f"{utilisation(lf) * 100:.1f} %, 여유 {feed_margin() * 100:.1f} %. "
         f"단면이 줄면 같은 정격이 {round(max_feed_mm_s() * removal_area_mm2() / stock_only):,.0f} "
         f"mm/s 까지 내주고 이용률은 {utilisation(lf) * stock_only / removal_area_mm2() * 100:.0f} % "
         "로 떨어진다. 그러면 속도를 정하는 것은 컨베이어다."),
        ("휠 어깨가 있을 이유가 없어진다",
         f"45° 어깨 한 곳은 아리스를 만드는 면이다 (`ARRIS_COUNT` = {ARRIS_COUNT}). "
         "반대쪽을 안 죽인 것도 그쪽이 EVA 와 만나기 때문이었다. 아리스가 없으면 "
         "홈은 그냥 평행 슬롯이고, 높이 공차가 형상을 좌우하지 않는다."),
        ("실란트와의 「둘 다는 안 된다」가 사라진다",
         f"`wheel_can_reach_the_glass_edge()` 가 거짓인 이유는 **어깨가 유리 "
         f"모서리에 닿아야 아리스가 생긴다**는 것이었다. 그 어깨가 면 위로 "
         f"{flange_reach_mm()} mm 걸쳐 나오고 그 구간이 통째로 띠 "
         f"{SEALANT_BAND_MM:.0f} mm 안이라 부딪쳤다. 닿을 필요가 없어지면 "
         f"여유를 실란트보다 벌려도 잃을 것이 없다 — `sealant_must_go_first_mm()` "
         f"의 {sealant_must_go_first_mm()} mm 가 근거를 잃는다."),
        ("끝면 살 0.03 mm 는 **같이 풀리지 않는다**",
         f"`STOCK_MM` = {STOCK_MM} 의 근거는 아리스가 아니라 프레임 인발이 남긴 "
         "잔사와 미세 파단면이다. 그것을 걷을 필요가 있는지는 별개의 물음이고 "
         "발주처가 아니라고 한 셋에 들어 있지 않았다. 여기서 같이 지우지 않는다."),
    )


def the_scrapers_reason_was_the_wheel() -> tuple[str, ...]:
    """SR-302 의 근거가 이 모듈에 무엇으로 적혀 있었는가 — 휠이었다.

    아리스가 빠지면 휠이 빠지고, 휠이 빠지면 이 두 문장이 같이 빠진다. 그것을
    발견이라고 적어 둔다 — 스크레이퍼를 지우자는 뜻이 아니라, **적혀 있던
    근거가 그것뿐이었다**는 뜻이다.
    """
    return (
        "`sealant_must_go_first_mm()` — 「휠이 들어가려면 띠에서 최소한 "
        "걷어내야 하는 폭」.",
        "`scraper_unit()` — 「휠보다 앞서 가며 실란트 띠를 걷는다」.",
        "둘 다 주어가 휠이다. 실란트가 나가야 하는 이유로 이 모듈이 적어 둔 "
        "것은 **휠의 접근**뿐이었다.",
        "실란트는 네 관문(유리 · 구리 · EVA · 백시트)에 없고 "
        "`separation.COMPONENTS` 에 행도 없다. 그러니 부유선별 쪽에서 오는 "
        "요구도 지금 모델에는 없다.",
        "그래도 실란트는 나가야 한다 — 근거가 휠에서 **BR-305 의 벨트**로 "
        "옮겨간다. 그쪽은 `br_abrade.the_belt_meets_silicone_first()` 가 센다 "
        "(이 모듈은 br_abrade 를 import 할 수 없다 — 그쪽이 이쪽을 읽는다).",
        f"**발주처가 이 걸음을 살렸다** (`SCRAPER_KEPT_BY_PLANT` = "
        f"{SCRAPER_KEPT_BY_PLANT}) — 실란트 → 백시트 연마 → 유리 제거. "
        "그러니 SR-302 는 남는다. 다만 **남는 근거가 바뀌었다**는 것이 "
        "이 절의 요지다.",
    )


def the_scraper_outlives_its_host() -> tuple[str, ...]:
    """SR-302 는 남는데 그것을 태우고 있던 휠은 목적이 없다 — 거처가 열린다.

    이 모듈에서 SR-302 는 **SG-301 헤드에 달린 부품**이다. 옵션이 아니라
    동승이라 리드가 `cycle()` 안에 있고 `occupancy_s()` 가 그것을 물고 있다.
    그 전제가 「휠이 간다」였다.

    발주처가 날은 살렸고 아리스는 요구하지 않았다. 두 답이 **서로 다른 방향**을
    가리킨다 — 걸음은 남고 그 걸음을 태울 것은 근거를 잃었다. 그래서 여기서
    판정하지 않고, 무엇이 열리는지만 적는다.
    """
    return (
        f"**날은 남는다** — `SCRAPER_KEPT_BY_PLANT` = {SCRAPER_KEPT_BY_PLANT}.",
        f"**휠은 목적이 없다** — `ARRIS_REQUIRED_BY_PLANT` = "
        f"{ARRIS_REQUIRED_BY_PLANT}. 남는 후보는 끝면 살 {STOCK_MM} mm 뿐이다.",
        f"**리드 {BLADE_LEAD_MM:.0f} mm 는 휠 때문에 있었다** — 「휠이 오기 전에 "
        f"그 자리가 비어 있어야 한다」. 동승이던 동안 그것이 "
        f"{lead_cost_if_shared_s()} s 를 가져갔고, 캐리어가 나가면서 SG-301 "
        f"에서 빠졌다(지금 실리는 리드 {scraper_lead_cost_s()} s). **그 "
        f"{lead_cost_if_shared_s()} s 가 날의 점유가 되는 것이 아니다** — "
        "남는 통과는 연마 통과가 아니라 긁는 통과라 다시 풀어야 한다. "
        "이 값을 그대로 쓰면 안 된다.",
        f"**발주처가 자기 캐리어로 정했다** — `campaign.SCRAPER_ON_ITS_OWN_CARRIER` "
        f"= {campaign.SCRAPER_ON_ITS_OWN_CARRIER}. 그래서 리드가 SG-301 에서 "
        f"빠지고 점유가 {occupancy_s()} s 로, 여유가 {slack_s()} s 로 늘었다. "
        "대신 **날 자신의 운동학**이 새 입력으로 들어왔다 — "
        "`the_own_carrier_frees_the_feed()`.",
    )


def the_band_requirement_widened() -> tuple[float, float, float]:
    """띠에서 걷어야 하는 폭이 (휠 기준, 벨트 기준, 날 폭) — 단위 mm.

    근거가 휠에서 벨트로 옮겨가면서 요구가 넓어진다. 휠은 어깨가 들어갈 만큼만
    필요했고, 벨트는 면을 통째로 지나가므로 띠 전체가 나가야 한다.

    **공구를 안 바꿔도 된다** — 날 폭이 애초에 어깨가 아니라 띠를 기준으로
    잡혀 있었기 때문이다(`BLADE_WIDTH_MM = SEALANT_BAND_MM + 4`).
    """
    return (sealant_must_go_first_mm(), float(SEALANT_BAND_MM), BLADE_WIDTH_MM)


def the_blade_already_covers_the_wider_requirement() -> bool:
    """넓어진 요구를 지금 날이 덮는가 — 덮어야 공구 변경이 없다."""
    _, needed, have = the_band_requirement_widened()
    return have >= needed


def what_the_absent_arris_leaves_open() -> tuple[tuple[str, str], ...]:
    """아리스 요구가 없다는 사실이 **열어 놓는** 것 — 내가 답하지 않는다."""
    return (
        ("자기 캐리어의 운동학",
         f"거처는 정해졌다(`campaign.SCRAPER_ON_ITS_OWN_CARRIER` = "
         f"{campaign.SCRAPER_ON_ITS_OWN_CARRIER}). 열린 것은 그 캐리어가 **몇 "
         f"헤드로 얼마나 빨리** 가는가다 — 여유 {slack_s()} s 에 들어가려면 "
         f"{feed_that_fits_the_slack_mm_s():.0f} mm/s(직렬) 또는 "
         f"{feed_that_fits_the_slack_mm_s(True):.0f} mm/s(SG 배치)가 필요하고, "
         "동력은 어느 쪽도 문제가 아니다."),
        ("이 걸음이 어느 스테이션에 서는가",
         f"파지는 정해졌다 — **진공 테이블**이 면내 {table_friction_kn()} kN 으로 "
         f"끄는 힘 {tangential_total_n()} N 의 {table_margin_over_drag():,.0f} 배를 "
         f"버틴다(그리퍼 패드는 대체됐다). 대신 흡착 "
         f"{campaign.VACUUM_CYCLE_S:.0f} s 가 여유를 먹어 필요 이송이 "
         f"{feed_that_fits_the_slack_mm_s():.0f} mm/s 로 올라갔다. **SG-301 과 "
         "같은 스테이션에 서는지 자기 스테이션을 갖는지**가 그 수를 통째로 "
         "바꾸는데 안 들었다 — `the_table_takes_time_back()`."),
        ("SG-301 이 남는가",
         "엣지 연마의 목적이 아리스였다면 목적이 없어진다. 남는 후보는 끝면 "
         f"살 {STOCK_MM} mm 뿐이고 그것은 단면의 "
         f"{(1 - arris_share()) * 100:.0f} % 다. 이 모듈을 지우는 것은 큰 "
         "정리다 — DS-01 분진 용량이 `LONG_HEADS` 를 읽고, 계약 동력이 "
         "스핀들 3 대를 물고, sg-closeup 도면이 이 단면을 그린다. 발주처 "
         "결정 없이 손대지 않는다."),
        ("실란트가 어디로 가는가",
         f"한 장에 {sealant_volume_per_panel_mm3():,.0f} mm³ 로 유리 제거량의 "
         f"{sealant_ratio_to_glass()} 배인데 `separation` 에 행이 없다. 파쇄로 "
         "들어가면 뜨는지 가라앉는지가 안 정해져 있다 — 실리콘은 표면에너지가 "
         "낮아 불소 폴리머처럼 시약 없이 뜰 소지가 있으나, 추측으로 행을 "
         "만들지 않는다."),
        ("끝면 살을 걷을 필요가 있는가",
         "아리스와 별개의 물음이다. 필요하면 형상휠이 아니라 훨씬 작은 "
         "설비로 되고, 필요 없으면 SG-301 의 마지막 근거도 없어진다."),
    )


# ── 힘 ──────────────────────────────────────────────────────────────────
def tangential_force_n(feed_mm_s: float) -> float:
    """접선력 F_t = P / v_s (N)."""
    return round(cutting_power_w(feed_mm_s) / wheel_speed_m_s(), 2)


def normal_force_n(feed_mm_s: float) -> float:
    """법선력 F_n = F_t / µ (N) — 컴플라이언스 축이 이 힘을 붙든다."""
    return round(tangential_force_n(feed_mm_s) / FORCE_RATIO, 1)


def contact_pressure_mpa(feed_mm_s: float) -> float:
    """접촉면 평균압 (MPa) — F_n / (l_c · a_p)."""
    return round(normal_force_n(feed_mm_s) / (contact_length_mm() * contact_width_mm()), 2)


# ── 휠 마모 ─────────────────────────────────────────────────────────────
def wheel_wear_volume_mm3() -> float:
    """사용 한계까지 쓸 수 있는 휠 체적 (mm³) — 홈 단면이 반경으로 닳는다."""
    d_mean = (WHEEL_D_MM + WHEEL_SPENT_D_MM) / 2.0
    radial = (WHEEL_D_MM - WHEEL_SPENT_D_MM) / 2.0
    return round(math.pi * d_mean * contact_width_mm() * radial, 1)


def panels_per_service() -> int:
    """교체 주기 안에 지나가는 장수."""
    return round(reliability.annual_panels() * WHEEL_SERVICE_MONTHS / 12.0)


def glass_volume_per_panel_mm3(edge_mm: float) -> float:
    """헤드 1 대가 한 장에서 걷어내는 유리 체적 (mm³)."""
    return round(removal_area_mm2() * edge_mm, 2)


def long_edge_mm() -> float:
    """장변 헤드 1 대가 한 장에서 가는 길이 (mm)."""
    return float(campaign.PANEL_LENGTH_MM)


def short_edge_mm() -> float:
    """단변 헤드 1 대가 한 장에서 가는 길이 (mm) — 앞·뒤 두 변."""
    return 2.0 * float(campaign.PANEL_WIDTH_MM)


def implied_g_ratio() -> int:
    """교체 주기가 요구하는 연삭비 G = 제거 유리체적 / 마모 휠체적.

    예비품 계획이 4 개월이라고 적어 둔 것에서 **역산**한 값이다. 벤더값이
    이보다 낮으면 주기가 짧아진다 — 그래서 R-04(마모율 실측)가 있다.
    """
    worst = max(long_edge_mm(), short_edge_mm())
    total = glass_volume_per_panel_mm3(worst) * panels_per_service()
    return round(total / wheel_wear_volume_mm3())


def radial_wear_um_per_panel() -> float:
    """장당 반경 마모 (µm) — 컴플라이언스 제어가 매 장 보상해야 하는 양."""
    worst = max(long_edge_mm(), short_edge_mm())
    worn = glass_volume_per_panel_mm3(worst) / implied_g_ratio()
    d_mean = (WHEEL_D_MM + WHEEL_SPENT_D_MM) / 2.0
    return round(worn / (math.pi * d_mean * contact_width_mm()) * 1_000.0, 4)


# ── 프레임이 남기고 간 것 — 실란트 띠와 백시트 ──────────────────────────
def panel_is_glass_down() -> bool:
    """기본 레시피에서 위를 향하는 면이 백시트인가 — 유리는 아래다."""
    base = [s for s in recipe.STRUCTURES if s.code == "GLASS_BACKSHEET"][0]
    return base.top == "백시트"


def sealant_left_t_mm() -> float:
    """인발 뒤 면에 남는 실란트 두께 (mm)."""
    return round(SEALANT_FACE_T_MM * SEALANT_RETAINED, 4)


def sealant_area_mm2() -> float:
    """한 면·한 변 1 mm 당 남는 실란트 단면적 (mm²) — 띠 폭 × 남은 두께."""
    return round(SEALANT_BAND_MM * sealant_left_t_mm(), 4)


# ── 관찰된 선 — 같은 물음을 관찰값으로 다시 센다 ─────────────────────────
def residue_line_area_mm2() -> float:
    """한 면·한 변 1 mm 당 남는 실란트 단면적 (mm²) — **관찰된 선** 쪽 값."""
    return round(RESIDUE_LINE_W_MM * RESIDUE_LINE_H_MM, 4)


def residue_line_face_area_mm2() -> float:
    """선이 한 면에서 덮는 면적 (mm²) — 네 변 둘레, 모서리 겹침을 뺀다."""
    w = RESIDUE_LINE_W_MM
    perimeter = 2.0 * (float(campaign.PANEL_LENGTH_MM) + float(campaign.PANEL_WIDTH_MM))
    return round(perimeter * w - 4.0 * w ** 2, 1)


def residue_line_volume_per_panel_mm3(faces: int = 2) -> float:
    """한 장에서 면에 남는 실란트 부피 (mm³) — 관찰된 선 쪽."""
    return round(residue_line_face_area_mm2() * RESIDUE_LINE_H_MM * faces, 1)


def residue_share_of_the_band() -> float:
    """관찰된 선이 관찰 전 띠 가정의 몇 분의 몇인가 — 단면적 비."""
    return round(residue_line_area_mm2() / sealant_area_mm2(), 4)


def the_band_assumption_was_the_worst_case() -> bool:
    """띠 가정이 관찰보다 무거운 쪽이었는가 — 관찰이 설계를 **풀어 주는** 방향인가.

    참이면 지금까지 계산한 모든 실란트 값(부피·동력·시간)이 상한이고, 관찰은
    그 상한을 낮춘다. 거짓이면 반대로 다시 세워야 한다 — 그래서 이름과 반환을
    같은 쪽으로 묶어 둔다.
    """
    return residue_line_area_mm2() < sealant_area_mm2()


def what_the_field_observation_removes() -> tuple[str, ...]:
    """관찰이 무엇을 지우고 무엇을 남기는가 — 값이 아니라 **판단**을 적는다."""
    from . import br_abrade
    return (
        f"**부피가 {1.0 / residue_share_of_the_band():,.0f} 분의 1 로 준다.** "
        f"단면적 {sealant_area_mm2()} → {residue_line_area_mm2()} mm²/mm, "
        f"한 장 {sealant_volume_per_panel_mm3():,.0f} → "
        f"{residue_line_volume_per_panel_mm3():,.0f} mm³ "
        f"(`the_band_assumption_was_the_worst_case()` = "
        f"{the_band_assumption_was_the_worst_case()}).",
        f"**긁는 쪽의 근거가 약해진다.** 긁는 힘은 Gc × 폭이라 폭이 "
        f"{SEALANT_BAND_MM:.0f} → {RESIDUE_LINE_W_MM:.0f} mm 로 줄면 같은 비율로 "
        f"준다. 6.3 W 가 더 작아지는 것은 좋은 일이지만, **그만한 일을 하려고 "
        f"캐리어 한 대를 세우는가**가 되물어진다 — 발주처 몫이다.",
        f"**첨두 동력은 폭이 아니라 높이가 정한다.** 선이 가로변을 건널 때는 "
        f"폭 {campaign.PANEL_WIDTH_MM:.0f} mm 전체가 동시에 물리므로 "
        f"`br_abrade.cross_line_peak_kw()` 는 폭에 무관하다. 폭이 줄이는 것은 "
        f"첨두의 **길이**, 곧 관성이 받아야 하는 에너지다.",
        f"**그래도 선은 남는다.** 관찰은 「거의」 떨어진다는 것이고 「전부」가 "
        f"아니다. 잔존 0 사양(`br_abrade.why_the_vision_is_needed()`)이 "
        f"백시트에 걸려 있는 것과 같은 이유로, 선도 비전이 봐야 한다.",
        f"**두 값이 실측 전이다.** 선 폭 {RESIDUE_LINE_W_MM} mm 와 높이 "
        f"{RESIDUE_LINE_H_MM} mm 는 관찰을 숫자로 옮긴 계획값이다. 높이가 "
        f"동력을, 폭이 시간을 정하므로 **둘 다 재야** 설비가 정해진다.",
    )


def sealant_volume_per_panel_mm3(faces: int = 2) -> float:
    """한 장에서 면에 남는 실란트 부피 (mm³) — 네 변 둘레 × 면 수."""
    perimeter = 2.0 * (float(campaign.PANEL_LENGTH_MM) + float(campaign.PANEL_WIDTH_MM))
    return round(sealant_area_mm2() * perimeter * faces, 1)


def sealant_ratio_to_glass() -> float:
    """면 실란트가 유리 제거량의 몇 배인가 — 무엇이 진짜 작업량인지의 답."""
    glass = removal_area_mm2() * 2.0 * (float(campaign.PANEL_LENGTH_MM)
                                        + float(campaign.PANEL_WIDTH_MM))
    return round(sealant_volume_per_panel_mm3() / glass, 1)


def flange_reach_mm() -> float:
    """휠 어깨(플랜지)가 라미네이트 **면** 위로 걸쳐 나오는 길이 (mm)."""
    return float(GROOVE_ROOT_MM)


def sealant_stands_proud_mm() -> float:
    """실란트가 홈 여유보다 얼마나 더 두꺼운가 (mm) — 양수면 부딪친다."""
    return round(sealant_left_t_mm() - GROOVE_CLEAR_MM, 4)


def wheel_can_reach_the_glass_edge() -> bool:
    """실란트 띠가 있는 채로 휠이 유리 모서리에 닿을 수 있는가.

    아리스는 어깨가 **유리 모서리에 닿아야** 만들어진다. 그런데 어깨는 면 위로
    `flange_reach_mm()` 만큼 걸쳐 나오고, 그 구간은 통째로 실란트 띠
    (`SEALANT_BAND_MM` 폭) 안이다. 실란트가 홈 여유보다 두꺼우면 어깨가 모서리에
    닿기 전에 실란트에 먼저 얹힌다.

    여유를 실란트보다 크게 벌리면 실란트는 피하지만 그때는 어깨가 모서리에서
    떨어져 **아리스가 안 만들어진다** — 둘 다는 성립하지 않는다.
    """
    if flange_reach_mm() > SEALANT_BAND_MM:
        return True                                 # 띠보다 어깨가 길면 바깥에서 닿는다
    return sealant_stands_proud_mm() <= 0.0


def sealant_must_go_first_mm() -> float:
    """휠이 들어가려면 띠에서 최소한 걷어내야 하는 폭 (mm)."""
    return 0.0 if wheel_can_reach_the_glass_edge() else round(flange_reach_mm(), 3)


# ── 백시트를 건드리면 무엇이 깨지는가 ───────────────────────────────────
def rubbing_speed_ratio() -> float:
    """휠 주속이 폴리머 접촉의 통상 상한(5 m/s)의 몇 배인가.

    폴리머는 마찰열을 못 흘린다 — 이 배수만큼 빠르면 접촉점이 융점을 넘어
    녹은 폴리머가 결합제 사이를 메운다(loading). 그러면 유리도 못 깎는다.
    """
    return round(wheel_speed_m_s() / POLYMER_RUB_LIMIT_M_S, 1)


def wheel_may_touch_the_backsheet() -> bool:
    """다이아몬드 휠로 백시트를 긁어도 되는가."""
    return rubbing_speed_ratio() <= 1.0


def depth_stack_mm() -> float:
    """기계 프레임을 기준으로 깊이를 잡을 때 쌓이는 공차 (mm, 최악합).

    라미네이트 두께 편차 + 롤러 상면·판 휨 + 헤드 세팅. 힘 제어가 아니라
    **위치 제어**로 면을 깎으면 이만큼이 그대로 깊이 오차가 된다.
    """
    return round(LAMINATE_TOL_MM + ROLLER_PLANE_TOL_MM + HEIGHT_TOL_MM, 4)


def position_control_is_safe() -> bool:
    """위치 제어로 면을 깎아도 백시트가 남는가 — 공차합이 백시트보다 얇아야 한다."""
    return depth_stack_mm() < BACKSHEET_T_MM


def backsheet_margin_mm() -> float:
    """공차합에서 백시트 두께를 뺀 값 (mm) — 양수면 그만큼 파고든다."""
    return round(depth_stack_mm() - BACKSHEET_T_MM, 4)


def safe_face_force_n() -> float:
    """면을 누를 수 있는 힘 (N) — 셀이 견디는 접촉압 × 패드 면적."""
    area = SEALANT_BAND_MM * FACE_PAD_LEN_MM
    return round(FACE_SAFE_MPA * area, 1)


def face_force_ratio() -> float:
    """유리 변을 미는 힘이 면에 허용된 힘의 몇 배인가."""
    return round(normal_force_n(long_feed_mm_s()) / safe_face_force_n(), 1)


def dust_stream_stays_inert() -> bool:
    """DS-01 이 '불연' 인 채로 있어도 되는가 — 폴리머를 안 깎아야 참이다."""
    return not wheel_may_touch_the_backsheet()


def max_gc_the_face_limit_allows() -> float:
    """면 허용 압착력이 감당하는 실란트 Gc 상한 (N/mm).

    긁는 힘은 Gc × 띠 폭이다. 그 힘이 허용 압착력을 넘으면 셀이 먼저 상한다.
    """
    return round((safe_face_force_n() - shoe_friction_n()) / SEALANT_BAND_MM, 3)


def gc_margin() -> float:
    """계획값 Gc 가 그 상한에서 얼마나 떨어져 있는가 (배)."""
    return round(max_gc_the_face_limit_allows() / sealant_gc_n_mm(), 2)


def blade_life_is_known() -> bool:
    """날 수명이 정해져 있는가 — 예비품 계획에 들어가려면 필요하다."""
    return False


def open_questions() -> tuple[tuple[str, str], ...]:
    """이 모델이 **못 닫는** 것 — 닫으려면 무엇이 있어야 하는가.

    선언이 아니라 계산이다. SR-302 가 들어오면서 네 항목이 스스로 닫혔고,
    그 자리에 **새로 생긴 불확실성**이 들어왔다 — 공구를 정하면 그 공구의
    물성이 새 입력이 되기 때문이다.
    """
    out: list[tuple[str, str]] = []
    if not wheel_can_reach_the_glass_edge() and not face_residue_has_a_tool():
        out.append((
            "휠이 유리 모서리에 못 닿는다",
            f"실란트 띠가 홈 여유보다 {sealant_stands_proud_mm()} mm 두꺼운데 "
            "그것을 걷을 공구가 없다."))
    if not face_residue_has_a_tool():
        out.append((
            "면 실란트를 걷을 공구가 없다",
            f"한 장에 {sealant_volume_per_panel_mm3():,.0f} mm³ 로 유리 제거량의 "
            f"{sealant_ratio_to_glass()} 배인데 부품표에 걷을 것이 없다."))
    if not backsheet_survives_scraping():
        out.append((
            "백시트가 남는다는 보장이 없다",
            f"깊이 오차 {blade_assembly_tol_mm()} mm 가 백시트 {BACKSHEET_T_MM} mm "
            "보다 얇아야 한다."))
    if not dust_stream_unchanged_by_scraping():
        out.append((
            "집진 흐름이 바뀐다",
            "폴리머가 분진으로 들어오면 DS-01 의 '불연' 선언이 거짓이 된다."))
    if not sequential_is_affordable():
        out.append((
            "순차 연마가 정반 점유를 넘는다",
            f"점유 {occupancy_s()} s (날 리드 {scraper_lead_cost_s()} s 포함) 가 "
            f"AFR {campaign.AFR_S} s 를 넘는다."))
    if not heads_agree_with_the_dust_model():
        out.append((
            "집진이 동시에 도는 헤드 수만큼 잡혀 있지 않다",
            f"장변 {LONG_HEADS} 대가 같은 통과에서 함께 가는데 집진이 그만큼을 "
            "안 잡았다. 첨두에서 포집이 모자란다."))

    # ── 공구를 정하면서 **새로 들어온** 불확실성 ─────────────────────────
    out.append((
        "실란트 Gc 가 실측 전 계획값이다",
        f"긁는 힘은 Gc × 띠 폭이다. 지금 Gc {sealant_gc_n_mm()} N/mm 에서 "
        f"{scrape_force_n():.0f} N 이고, 면 허용 압착력 {safe_face_force_n():.0f} N 은 "
        f"Gc **{max_gc_the_face_limit_allows()} N/mm** 까지 감당한다 — 여유 "
        f"{gc_margin()} 배. 실란트 시험이 그보다 높게 나오면 띠를 나눠 두 번 "
        "긁거나 슈 압착을 다시 잡아야 한다. 같은 값이 인발 쪽도 움직이는데 "
        "`afr_peel.stability()` 는 아니다 — 정상박리력 P = q_max/2β 는 강도와 "
        "기초강성으로만 정해져 Gc 가 안 들어간다. Gc 가 바꾸는 것은 `bond()` 의 "
        "δ_f 를 거친 유한요소 쪽(최대응력·박리 전선)과 화면의 `bondSep` 이다. "
        "그리고 거기가 먼저 걸린다 — Gc 1.2 에서 이미 설계 인발력으로 전선이 "
        "안 나간다(2,400 → 0 mm). 면 허용 상한 1.75 보다 낮으니 시험값이 오면 "
        "스크레이퍼보다 인발을 먼저 본다."))
    out.append((
        "인발 뒤 면에 남는 몫이 실측 전 값이다",
        f"응집파괴가 가운데쯤에서 갈린다고 보고 {SEALANT_RETAINED:.0%} 를 썼다. "
        f"전량이 남으면 띠 두께가 {SEALANT_FACE_T_MM} mm 로 두 배가 되고 긁는 "
        f"힘은 그대로지만(계면 일이라 두께와 무관) 부스러기 부피가 두 배다 — "
        "회수함 용량이 그만큼 든다."))
    if the_back_face_band_has_no_tool():
        out.append((
            "백시트면 띠를 걷을 공구가 없다",
            f"날이 {BLADE_FACES} 면에 서는데 잔사는 {RESIDUE_FACES} 면에 "
            f"남는다 — 한 장에 "
            f"{sealant_volume_per_panel_mm3(faces=1):,.0f} mm³ 가 공구 없이 "
            "남고 그 면이 BR-305 의 벨트가 지나가는 면이다. "
            "`how_the_faces_were_made_to_add_up()`."))
    if GRIP_ADOPTED:
        out.append((
        "그리퍼 패드 마찰이 실측 전 계획값이다",
        f"물어야 하는 힘이 끄는 힘 ÷ 마찰이라 패드 면적이 여기에 반비례로 "
        f"걸린다. {GRIP_FRICTION:g} 에서 {grip_pad_area_needed_mm2():,.0f} mm² "
        f"인데 슈의 {SHOE_FRICTION:g} 까지 떨어지면 "
        f"{round(tangential_total_n() * GRIP_SAFETY / SHOE_FRICTION / FACE_SAFE_MPA):,.0f} mm² "
        f"다. 성립이 깨지는 값은 {friction_below_which_the_pad_outgrows_the_panel()} "
        "라 한참 아래이니 **치수 문제이지 성립 문제는 아니다.**"))
        out.append((
        "그리퍼 패드 배치를 안 들었다",
        f"단변 통과에서 모멘트가 {grip_moment_n_m()} N·m 선다. 장수와 간격이 "
        f"정해져야 한 장의 값이 나온다 — 예로 네 장을 "
        f"1,000 mm 벌리면 {grip_pad_force_n(4, 1000.0)} N, 두 장이면 "
        f"{grip_pad_force_n(2, 1000.0)} N 이다. **예시이지 배치가 아니다.**"))
        out.append((
        "한쪽으로 누르는지 양쪽으로 무는지 안 들었다",
        f"한쪽이면 {grip_force_needed_n()} N 의 반력을 반출롤러가 받아야 하고, "
        "양쪽이면 슈처럼 판 안에서 닫히되 아래 패드가 롤러 사이에 들어가야 "
        "한다. 둘이 서로 다른 부품표를 부른다."))
    if BLADE_FACES >= 2 and not BLADES_ARE_OPPOSED:
        out.append((
            "두 날이 마주 보지 않는다",
            f"압착 {SHOE_SPRING_N:.0f} N 이 상쇄가 아니라 우력이 되어 판을 "
            "비튼다. 요크 한 몸으로 같은 자리에서 잡아야 한다."))
    if not table_inset_clears_the_blade():
        out.append((
            "테이블이 아래 날을 막는다",
            f"물림 {TABLE_INSET_MM:.0f} mm 가 날 폭 {BLADE_WIDTH_MM:.0f} mm 보다 "
            "좁아 아래 면 띠에 못 닿는다."))
    out.append((
        "흡착 배기·해제가 여유를 먹는다",
        f"진공 테이블을 쓰면 {campaign.VACUUM_CYCLE_S:.0f} s (계획값)가 먼저 "
        f"빠져 쓸 수 있는 시간이 {slack_s()} → {scraper_time_left_s()} s 가 "
        f"된다. 필요한 이송이 {feed_that_fits_the_slack_mm_s():.0f} mm/s "
        f"(SG 배치 {feed_that_fits_the_slack_mm_s(True):.0f})로 올라간다 — "
        "`the_table_takes_time_back()`."))
    if the_carrier_is_its_own() and not scraper_fits_the_slack():
        out.append((
            "자기 캐리어의 통과가 여유에 안 들어간다",
            f"물려받은 이송 {long_feed_mm_s():.0f} mm/s 로 직렬이면 "
            f"{scraper_serial_time_s(long_feed_mm_s())} s 인데 여유는 "
            f"{slack_s()} s 다. 들어가려면 "
            f"{feed_that_fits_the_slack_mm_s():.0f} mm/s 가 필요하고 동력은 "
            f"{scraper_power_at_w(feed_that_fits_the_slack_mm_s()):.0f} W 로 "
            "문제가 아니다 — 캐리지가 그 속도를 내는지가 미결이다."))
    if SCRAPER_KEPT_BY_PLANT and not ARRIS_REQUIRED_BY_PLANT:
        out.append((
            "날은 남는데 그것을 태운 휠은 요구가 없다",
            f"SR-302 는 헤드 동승이 전제인데 숙주의 목적이 없어졌다. 리드 "
            f"{BLADE_LEAD_MM:.0f} mm ({scraper_lead_cost_s()} s) 도 휠 때문에 "
            "있었다. 캐리어를 정하기 전에는 이 유닛의 점유가 안 풀린다."))
    if not ARRIS_REQUIRED_BY_PLANT:
        out.append((
            "아리스를 요구하는 공정이 없다",
            f"공정 요구가 없는데 단면의 {arris_share() * 100:.0f} % 와 통과속도 "
            f"상한(이용률 {utilisation(long_feed_mm_s()) * 100:.1f} %)을 그것이 "
            "정하고 있다. SG-301 이 남는가가 먼저 정해져야 이 모듈의 수들이 "
            "의미를 갖는다 — `what_the_absent_arris_leaves_open()`."))
    if not blade_life_is_known():
        out.append((
            "날 수명이 없다",
            f"한 장에 둘레 {2 * (campaign.PANEL_LENGTH_MM + campaign.PANEL_WIDTH_MM):,.0f} mm "
            f"를 긁는다. PEEK 날이 몇 장을 가는지는 벤더값이고, 나오기 전에는 "
            "예비품(R-04 마모율 실측)에 넣을 수량이 안 나온다."))
    return tuple(out)


def two_pass_occupancy_s() -> float:
    """장변을 한 변씩 두 번 지나갈 때의 점유 (s)."""
    extra = float(campaign.PANEL_LENGTH_MM) / long_feed_mm_s()
    return round(occupancy_s() + extra, 2)


def heads_agree_with_the_dust_model() -> bool:
    """집진이 **동시에 도는 헤드 수**만큼 풍량을 잡고 있는가.

    한때 두 모델이 서로 다른 말을 했다 — 캠페인은 두 장변을 한 번의 통과로
    세어 동시를 전제했고, 집진은 '동시에 도는 헤드가 없다' 며 한 대 몫만
    잡았다. 발주처가 동시로 정해 집진 쪽을 고쳤고, 이제 이 술어가 그것을
    **확인한다** — 선언이 아니라 계산이라 다시 갈라지면 미결로 되살아난다.
    """
    from . import dust
    return dust.SG_SIMULTANEOUS_HOODS >= LONG_HEADS



# ── SR-302 잔사 스크레이퍼 — 띠를 걷는 공구 ─────────────────────────────
# 휠은 이 띠를 못 지난다(`wheel_can_reach_the_glass_edge()`). 그러면 무엇으로
# 걷는가. 후보가 둘이고, **에너지가 답을 정한다.**
#
#   갈아낸다 — 부피 일이다. e_c × (띠 단면 × 이송) = 36 kW.
#   긁어낸다 — 계면 일이다. Gc × 띠 폭 = 16 N, 동력으로는 5 W 도 안 된다.
#
# 7,500 배다. 갈아내는 쪽은 스핀들을 열여섯 대 달아도 모자라고, 폴리머를 갈면
# 휠이 막히고 DS-01 의 '불연' 선언까지 깨진다. 긁어내면 부스러기가 고체로 나와
# 집진 흐름 자체가 안 바뀐다. 그래서 **긁는다.**

#: 날 재질과 경도 (GPa). 유리(5.5)보다 훨씬 무르므로 유리를 긁을 수 없고,
#: 경화 실란트(≈0.02)보다는 단단해 그것을 떼어 낸다.
BLADE_MATERIAL = "PEEK"
BLADE_HARDNESS_GPA = 0.24
SEALANT_HARDNESS_GPA = 0.02
#: 날 폭 (mm) — 띠보다 넓어야 한쪽으로 치우쳐도 다 걷는다.
BLADE_WIDTH_MM = SEALANT_BAND_MM + 4.0
#: 날 경사각 (°) 과 날끝 반경 (mm). 무딘 날은 밀고 지나가고, 너무 날카로우면
#: 라미네이트를 파고든다.
BLADE_RAKE_DEG = 25.0
BLADE_EDGE_R_MM = 0.2
#: 접촉 슈 길이 (mm) — 라미네이트 면에 얹혀 **깊이를 면에서 잡는다.**
#: 기계 프레임을 기준으로 잡으면 공차합이 백시트보다 두꺼워진다.
SHOE_LEN_MM = 60.0
#: 슈를 누르는 스프링 힘 (N) — 면 허용 압착력 안에 들어야 한다.
SHOE_SPRING_N = 25.0
#: 슈와 라미네이트 사이 마찰계수 (PEEK-유리, 건식).
SHOE_FRICTION = 0.2
#: 날이 휠보다 앞서 가는 거리 (mm) — 휠이 오기 전에 그 자리가 비어 있어야 한다.
#: 휠 반경보다 커야 하고, 여유를 둔다. 이 리드가 통과 거리를 늘려 라인 점유에
#: 그대로 실리므로 값은 `campaign` 이 쥔다 — 두 곳에 적으면 갈라진다.
BLADE_LEAD_MM = campaign.SG_BLADE_LEAD_MM
#: 띠를 화면에 세울 때의 두께 과장 — 0.75 mm 는 800 mm 옆에서 안 보인다.
BAND_DISPLAY_MAG = 20.0

#: 걷은 실란트를 갈아내려 했다면 필요했을 비에너지 (J/mm³) — 계획값.
#: 이 값은 **쓰지 않는다.** 긁는 쪽과 견주려고만 둔다.
SEALANT_ABRADE_J_MM3 = 8.0

#: 발주처가 **「SR-302 를 살린 안」**을 골랐다 — 실란트 제거를 백시트 연마로
#: 갈음하지 않고 둘을 차례로 세운다: 실란트 → 백시트 연마 → 유리 제거.
#:
#: 받은 값이고 내가 정한 것이 아니다. 이 걸음이 남는다는 것과 **그 걸음이
#: 어디에 실리는가**는 다른 물음이다 — 후자는 아직 안 들었다
#: (`the_scraper_outlives_its_host()`).
SCRAPER_KEPT_BY_PLANT = True


def sealant_gc_n_mm() -> float:
    """실란트 접착 파괴에너지 (N/mm) — `afr_peel` 이 정본. 인발 해석과 같은 값이다."""
    from . import afr_peel
    return float(afr_peel.SEALANT_GC_N_MM)


def scrape_force_n() -> float:
    """띠를 계면에서 떼는 힘 (N) = Gc × 띠 폭.

    스크레이핑은 **계면 일**이다 — 부피를 갈아 없애는 것이 아니라 붙어 있는
    면을 떼어 내는 것이므로, 두께가 아니라 폭에 비례한다.
    """
    return round(sealant_gc_n_mm() * SEALANT_BAND_MM, 2)


def shoe_friction_n() -> float:
    """슈가 면 위를 미끄러지며 내는 마찰 (N)."""
    return round(SHOE_SPRING_N * SHOE_FRICTION, 2)


def scrape_total_force_n() -> float:
    """**한 날**이 이송 방향으로 내야 하는 힘 (N) — 계면 + 슈 마찰.

    날이 두 장이므로 캐리어가 끌어야 하는 것은 이 값이 아니라
    `tangential_total_n()` 이다. 이 함수와 `scrape_power_w()` 는 **한 면 기준**
    으로 남겨 둔다 — 갈아내는 쪽(`abrade_power_w()`)도 한 면 값이라 그래야
    `scrape_beats_abrade_by()` 의 비교가 같은 것끼리의 비교로 선다.
    """
    return round(scrape_force_n() + shoe_friction_n(), 2)


# ── 두 날 — 법선은 상쇄되고 접선은 더해진다 ─────────────────────────────
#: 두 날이 판을 사이에 두고 **같은 자리에서 마주 보는가** — 발주처가 「양면
#: 동시」로 정했으므로 참이다. 이 값이 법선력의 상쇄를 켜고 끈다.
#:
#: 조건은 **같은 자리**다. 주행 방향으로 어긋나 있으면 두 압착력이 상쇄가
#: 아니라 **우력**이 되어 판을 비튼다. 요크(C 형) 한 몸으로 잡아야 성립한다.
BLADES_ARE_OPPOSED = True


def tangential_total_n() -> float:
    """캐리어가 끌어야 하는 이송 방향 힘 (N) — 날 수만큼 **더해진다.**

    두 날이 같은 방향으로 가므로 각자의 계면력과 슈 마찰이 같은 쪽으로 걸린다.
    마주 본다고 상쇄되는 것은 법선이지 접선이 아니다.
    """
    return round(scrape_total_force_n() * BLADE_FACES, 2)


def normal_net_on_panel_n() -> float:
    """판이 실제로 받는 알짜 압착력 (N) — 마주 보면 0 이다.

    한 장일 때는 슈가 한쪽에서 누르고 그 반력을 반출롤러가 받아야 했다.
    두 장이 마주 보면 두 힘이 판 안에서 닫혀 **바깥으로 나가지 않는다.**
    """
    return 0.0 if (BLADES_ARE_OPPOSED and BLADE_FACES >= 2) else float(SHOE_SPRING_N)


def clamp_force_n() -> float:
    """마주 보는 두 슈가 판을 무는 힘 (N) — 한쪽 압착력 그대로다."""
    return float(SHOE_SPRING_N) if (BLADES_ARE_OPPOSED and BLADE_FACES >= 2) else 0.0


# ── 그리퍼 — 주행 방향 합력을 판이 아니라 그리퍼가 받는다 ───────────────
#
#   두 날이 마주 보면서 법선은 닫혔지만 접선 `tangential_total_n()` 은 남는다.
#   판이 그만큼 끌리므로 무엇이든 그것을 붙들어야 한다. **발주처가 그리퍼로
#   정했다.**
#
#   붙드는 방법이 둘인데 하나가 막혀 있다. **기계적 스토퍼**는 변을 짚어야
#   하는데 날이 도는 곳이 바로 변이고, 캐리어가 네 변을 돌면 끄는 방향이
#   네 번 바뀌므로 네 변을 다 짚어야 한다 — 날과 자리를 다툰다. 그래서
#   **면을 물어 마찰로 잡는다.**

# ── 진공 테이블 — BR-305 와 같은 방식을 이 걸음에도 쓴다 ────────────────
#
#   BR-305 에서 채택한 진공 테이블을 SR-302 에도 쓴다(발주처 결정). 그런데
#   이 걸음에는 **BR-305 에 없는 제약**이 하나 있다 —
#
#     날이 **두 장**이고 **양면**을 긁는다. 테이블이 아래 면을 덮으면
#     아래 날이 띠에 못 닿는다.
#
#   그래서 테이블을 변에서 안쪽으로 **물려야** 한다. 물린 만큼 무는 면적이
#   줄지만, 버텨야 하는 힘이 42 N 뿐이라 그 손해는 문제가 안 된다.

#: 테이블이 변에서 물러나는 거리 (mm) — 아래 날이 들어갈 자리를 낸다.
#: `BLADE_WIDTH_MM` 보다 커야 한다(`the_table_must_clear_the_band()`).
TABLE_INSET_MM = 40.0
#: 그리퍼 패드로 잡는 안을 채택했는가 — **진공 테이블이 대신하므로 아니다.**
#: 값을 지우지 않는 이유는 그것이 「면 허용 압착력 안에서 어떻게 잡을 것인가」
#: 의 답이었고, 진공이 그 물음을 없앴다는 것이 판단 근거이기 때문이다.
GRIP_ADOPTED = False

#: 그리퍼 패드와 라미네이트 사이 마찰계수 — 계획값.
#:
#: **슈의 `SHOE_FRICTION` 을 빌려 오면 안 된다.** 그쪽은 PEEK 를 **미끄러지라고**
#: 고른 값(0.2)이고 이쪽은 **잡으라고** 고르는 값이다. 엘라스토머 패드가 유리·
#: 폴리머에 닿을 때의 통상대(0.5~1.0)에서 보수적으로 잡았다. 실측 전 값이고
#: 여기에 패드 면적이 반비례로 걸린다.
GRIP_FRICTION = 0.6
#: 마찰 파지의 안전율 — 계획값. 미끄러지면 판이 날 밑에서 밀린다.
GRIP_SAFETY = 2.0


def grip_force_needed_n() -> float:
    """미끄러지지 않으려면 물어야 하는 힘 (N) = 끄는 힘 × 안전율 / 마찰계수."""
    return round(tangential_total_n() * GRIP_SAFETY / GRIP_FRICTION, 1)


def grip_pad_area_needed_mm2() -> float:
    """그 힘을 면 허용 접촉압 안에서 주려면 필요한 패드 면적 (mm²).

    **면 한계는 힘의 한계가 아니라 압력의 한계다.** 그래서 「몇 N 까지 되는가」가
    아니라 「몇 mm² 를 깔아야 하는가」로 답이 나온다 — 넓히면 얼마든 물 수 있다.
    """
    return round(grip_force_needed_n() / FACE_SAFE_MPA, 1)


def grip_pad_side_mm() -> float:
    """정사각 패드 한 장으로 받는다면 한 변 (mm) — 크기 감을 잡는 값."""
    return round(math.sqrt(grip_pad_area_needed_mm2()), 1)


def grip_must_sit_inboard_mm() -> float:
    """패드가 변에서 최소한 물러나야 하는 거리 (mm) — 실란트 띠 폭.

    띠 위에 얹으면 두 가지가 깨진다. 걷어내야 할 것을 눌러 밀착시키고,
    마찰 계획값이 유리·폴리머가 아니라 **실리콘 위**의 값이 된다.
    """
    return float(SEALANT_BAND_MM)


def grip_moment_n_m(long_edge: bool = False) -> float:
    """끄는 힘이 판 중심에 대해 만드는 모멘트 (N·m).

    날은 변에서 끌고 그리퍼는 안쪽에서 잡으므로 힘만 받는 것이 아니다.
    단변을 지날 때 팔이 가장 길다 — 힘의 작용선이 중심에서 판 길이의 절반만큼
    떨어진다.
    """
    arm_mm = (float(campaign.PANEL_WIDTH_MM) if long_edge
              else float(campaign.PANEL_LENGTH_MM)) / 2.0
    return round(tangential_total_n() * arm_mm / 1_000.0, 2)


def grip_pad_force_n(pads: int, spacing_mm: float) -> float:
    """패드 배치를 정하면 한 장이 받는 최악 힘 (N) — 직접분 + 우력분.

    **배치를 정하는 함수가 아니다.** 몇 장을 얼마나 벌려 놓느냐가 정해지면
    그때 한 장의 값이 나온다는 것을 보이는 함수다.
    """
    if pads < 1 or spacing_mm <= 0.0:
        return float("inf")
    direct = tangential_total_n() / pads
    couple = grip_moment_n_m() * 1_000.0 / spacing_mm
    return round(direct + couple, 1)


def the_face_limit_turns_force_into_area() -> tuple[str, ...]:
    """그리퍼가 받는다고 정하면 무엇이 정해지는가 — 힘이 아니라 넓이다."""
    return (
        f"**끄는 힘은 {tangential_total_n()} N** 이다 (두 날의 계면력 + 슈 마찰). "
        f"안전율 {GRIP_SAFETY:g} 에 마찰 {GRIP_FRICTION:g} 이면 물어야 하는 힘이 "
        f"**{grip_force_needed_n()} N** 이다.",
        f"**면은 그 힘을 못 막는다 — 압력을 막는다.** 허용 {FACE_SAFE_MPA} MPa "
        f"로 {grip_force_needed_n()} N 을 주려면 패드가 "
        f"**{grip_pad_area_needed_mm2():,.0f} mm²** 필요하다 (정사각이면 한 변 "
        f"{grip_pad_side_mm():.0f} mm). 넓히면 얼마든 물 수 있으니 이것은 "
        "한계가 아니라 **치수**다.",
        f"**마찰계수가 그 넓이를 정한다.** {GRIP_FRICTION:g} 에서 "
        f"{grip_pad_area_needed_mm2():,.0f} mm² 인데 슈의 "
        f"{SHOE_FRICTION:g}(미끄러지라고 고른 값)로 떨어지면 "
        f"{round(tangential_total_n() * GRIP_SAFETY / SHOE_FRICTION / FACE_SAFE_MPA):,.0f} mm² "
        "가 된다. 패드 재질이 이 유닛에서 가장 민감한 계획값이다.",
        f"**힘만 받는 것이 아니다.** 날이 변에서 끌고 패드는 안쪽에 있으므로 "
        f"모멘트가 선다 — 단변 통과에서 {grip_moment_n_m()} N·m, 장변에서 "
        f"{grip_moment_n_m(long_edge=True)} N·m. 패드를 몇 장 얼마나 벌리느냐가 "
        f"한 장의 값을 정한다 (`grip_pad_force_n()`).",
        f"**패드는 변에서 {grip_must_sit_inboard_mm():.0f} mm 안쪽에 서야 한다** — "
        "실란트 띠 위에 얹으면 걷어낼 것을 눌러 붙이고, 마찰 계획값도 "
        "유리·폴리머가 아니라 실리콘 위의 값이 된다.",
    )


def grip_is_sized_by_area_not_force() -> bool:
    """면 한계가 넓이 문제인가 — 패드를 넓힐 수 있으면 참이다.

    패널 한 면보다 커져야 한다면 그때는 진짜 한계다.
    """
    face = float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
    return grip_pad_area_needed_mm2() < face


def friction_below_which_the_pad_outgrows_the_panel() -> float:
    """패드가 판 면보다 커지는 마찰계수 (–) — 아래로 내려가면 파지가 성립 안 한다."""
    face = float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
    return round(tangential_total_n() * GRIP_SAFETY / (FACE_SAFE_MPA * face), 5)


def table_inset_clears_the_blade() -> bool:
    """물린 거리가 아래 날이 들어갈 만큼인가."""
    return TABLE_INSET_MM >= BLADE_WIDTH_MM


def table_held_area_mm2() -> float:
    """테이블이 실제로 무는 면적 (mm²) — 변에서 물린 안쪽만."""
    length = float(campaign.PANEL_LENGTH_MM) - 2.0 * TABLE_INSET_MM
    width = float(campaign.PANEL_WIDTH_MM) - 2.0 * TABLE_INSET_MM
    return round(length * width, 1)


def table_area_share() -> float:
    """판 면적 중 무는 몫 — 물린 만큼 준다."""
    whole = float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
    return round(table_held_area_mm2() / whole, 4)


def table_hold_kn() -> float:
    """그 면적이 내는 흡착력 (kN) — 셈은 `campaign` 이 한다."""
    return campaign.vacuum_hold_kn(table_held_area_mm2())


def table_friction_kn() -> float:
    """미끄러지기 전까지 버티는 면내 힘 (kN)."""
    return campaign.vacuum_friction_kn(table_held_area_mm2())


def table_margin_over_drag() -> float:
    """두 날이 끄는 힘의 몇 배를 버티는가."""
    return round(table_friction_kn() * 1_000.0 / tangential_total_n(), 1)


def the_table_must_clear_the_band() -> tuple[str, ...]:
    """진공 테이블을 이 걸음에 붙일 때의 **유일한 기하 제약**.

    BR-305 는 백시트 면 하나만 건드리므로 테이블이 반대 면을 통째로 물어도
    된다. 이 걸음은 **양면**이라 그게 안 된다.
    """
    return (
        f"**날이 {BLADE_FACES} 장이고 양면을 긁는다.** 테이블이 아래 면을 덮으면 "
        "아래 날이 띠에 못 닿는다 — BR-305 에는 없던 제약이다.",
        f"**그래서 테이블을 변에서 {TABLE_INSET_MM:.0f} mm 물린다.** 날 폭 "
        f"{BLADE_WIDTH_MM:.0f} mm 보다 커야 하고 "
        f"(`table_inset_clears_the_blade()` = {table_inset_clears_the_blade()}), "
        f"띠 폭 {SEALANT_BAND_MM:.0f} mm 는 그 안에 든다.",
        f"**무는 면적이 {table_area_share():.1%} 로 준다** — "
        f"{table_held_area_mm2():,.0f} mm². 그래도 흡착 {table_hold_kn()} kN, "
        f"면내 {table_friction_kn()} kN 이라 끄는 힘 {tangential_total_n()} N 의 "
        f"**{table_margin_over_drag():,.0f} 배**다. 물린 손해는 문제가 안 된다.",
        "**요크는 변을 감싸야 한다.** 두 날이 마주 보려면 판 둘레를 C 형으로 "
        "타야 하고, 물린 구간이 그 자리를 낸다 — 물림이 두 가지 일을 한다.",
    )


def the_vacuum_replaces_the_pads() -> tuple[str, ...]:
    """그리퍼 패드가 왜 빠지는가 — 지우지 않고 근거로 남긴다."""
    return (
        f"**패드는 「면 허용 압착력 안에서 어떻게 잡을 것인가」의 답이었다** — "
        f"물 힘 {grip_force_needed_n()} N 을 허용 압력 {FACE_SAFE_MPA} MPa 로 "
        f"주려면 넓이 {grip_pad_area_needed_mm2():,.0f} mm² 가 들었다.",
        f"**진공은 그 물음을 없앤다.** 접촉압이 "
        f"{campaign.vacuum_contact_mpa()} MPa 로 허용의 "
        f"{campaign.vacuum_contact_mpa() / FACE_SAFE_MPA:.1f} 배이고, 무는 면이 "
        "**유리**라 셀 기준을 쓸 일도 없다.",
        f"**모멘트도 같이 없어진다.** 패드였다면 단변 통과에서 "
        f"{grip_moment_n_m()} N·m 를 장수와 간격으로 받아야 했는데 — 그 배치가 "
        "미결이었다 — 진공은 면 전체에 퍼져 우력이 한곳에 몰리지 않는다.",
        f"**패드 값은 살려 둔다** (`GRIP_ADOPTED` = {GRIP_ADOPTED}). 진공이 "
        "안 되는 자리가 나오면 돌아올 자리이고, 그때 마찰 계획값 "
        f"{GRIP_FRICTION:g} 와 넓이가 근거가 된다.",
    )


def the_shoes_oppose_each_other() -> tuple[str, ...]:
    """두 장으로 가면서 힘이 어떻게 갈리는가 — 한쪽은 닫히고 한쪽은 는다."""
    return (
        f"**법선은 상쇄된다.** 한 장일 때 슈 압착 {SHOE_SPRING_N:.0f} N 의 반력을 "
        f"판 반대쪽이 받아야 했다. 마주 보면 판이 받는 알짜가 "
        f"{normal_net_on_panel_n():.0f} N 이고, 대신 {clamp_force_n():.0f} N 으로 "
        "**무는** 상태가 된다 — 힘이 판 안에서 닫힌다.",
        f"**접선은 더해진다.** 두 날이 같은 방향으로 가므로 "
        f"{scrape_total_force_n()} N 씩 같은 쪽으로 걸려 "
        f"**{tangential_total_n()} N** 이다. 마주 본다고 없어지지 않는다 — "
        f"발주처가 **그리퍼가 받는 것**으로 정했고, 그러면 물어야 하는 힘이 "
        f"{grip_force_needed_n()} N, 패드가 "
        f"{grip_pad_area_needed_mm2():,.0f} mm² 다 "
        "(`the_face_limit_turns_force_into_area()`).",
        f"**면 허용은 한쪽씩 본다.** 슈 하나가 주는 접촉압 "
        f"{shoe_pressure_mpa()} MPa 와 압착 {SHOE_SPRING_N:.0f} N 은 그대로이고 "
        f"허용 {safe_face_force_n():.0f} N 안에 있다 "
        f"(`shoe_is_gentle_enough()` = {shoe_is_gentle_enough()}). 두 장이라고 "
        "한 면이 두 배로 눌리는 것이 아니다.",
        "**성립 조건은 같은 자리다.** 주행 방향으로 어긋나면 상쇄가 아니라 "
        "**우력**이 되어 판을 비튼다 — 요크 한 몸으로 잡아야 한다. "
        f"`BLADES_ARE_OPPOSED` = {BLADES_ARE_OPPOSED} 가 그 전제다.",
    )


def scrape_power_w(feed_mm_s: float) -> float:
    """긁는 데 드는 동력 (W)."""
    return round(scrape_total_force_n() * feed_mm_s / 1_000.0, 2)


def abrade_power_w(feed_mm_s: float) -> float:
    """같은 띠를 **갈아냈다면** 들었을 동력 (W) — 쓰지 않는 쪽의 값."""
    return round(SEALANT_ABRADE_J_MM3 * sealant_area_mm2() * feed_mm_s, 1)


def scrape_beats_abrade_by() -> int:
    """긁는 쪽이 몇 배 싼가 — 공구 선택의 근거."""
    feed = long_feed_mm_s()
    return round(abrade_power_w(feed) / scrape_power_w(feed))


def scraping_fits_the_spindle() -> bool:
    """긁는 동력이 연마 스핀들 한 대 안에 드는가 — 별도 동력원이 필요 없다."""
    return scrape_power_w(long_feed_mm_s()) <= spindle_available_w()


def abrading_fits_the_spindle() -> bool:
    """갈아내는 쪽은 어떤가 — 거짓이어야 이 선택이 설명된다."""
    return abrade_power_w(long_feed_mm_s()) <= spindle_available_w()


def shoe_pressure_mpa() -> float:
    """슈가 라미네이트에 주는 접촉압 (MPa) — 셀 허용값 안에 있어야 한다."""
    return round(SHOE_SPRING_N / (BLADE_WIDTH_MM * SHOE_LEN_MM), 4)


def shoe_is_gentle_enough() -> bool:
    """슈 압착이 면 허용 압착력·접촉압 안에 드는가."""
    return SHOE_SPRING_N <= safe_face_force_n() and shoe_pressure_mpa() <= FACE_SAFE_MPA


def blade_cannot_scratch_glass() -> bool:
    """날이 유리를 긁을 수 있는가 — 무른 것은 단단한 것을 못 긁는다."""
    return BLADE_HARDNESS_GPA < GLASS_H_GPA


def blade_can_shear_the_sealant() -> bool:
    """그런데 실란트는 뗄 수 있는가."""
    return BLADE_HARDNESS_GPA > SEALANT_HARDNESS_GPA


def depth_is_referenced_to_the_panel() -> bool:
    """깊이를 기계 프레임이 아니라 **판 면**에서 잡는가.

    슈가 라미네이트에 얹혀 있으므로 두께 편차·롤러 평면도가 깊이에 안 들어온다.
    남는 것은 슈-날 조립 공차뿐이고 그것은 백시트보다 훨씬 얇다.
    """
    return SHOE_LEN_MM > 0.0 and SHOE_SPRING_N > 0.0


def blade_assembly_tol_mm() -> float:
    """슈 기준일 때 남는 깊이 오차 (mm) — 날끝 반경이 사실상의 하한이다."""
    return round(BLADE_EDGE_R_MM, 4)


def backsheet_survives_scraping() -> bool:
    """긁고 나서 백시트가 남는가 — 슈 기준 오차가 백시트보다 얇아야 한다."""
    return depth_is_referenced_to_the_panel() and blade_assembly_tol_mm() < BACKSHEET_T_MM


def debris_is_solid() -> bool:
    """부스러기가 분진이 아니라 고체로 나오는가 — 집진 흐름이 안 바뀐다."""
    return True


def dust_stream_unchanged_by_scraping() -> bool:
    """DS-01 의 '불연' 선언이 그대로 서는가."""
    return debris_is_solid() and not wheel_may_touch_the_backsheet()


def the_carrier_is_its_own() -> bool:
    """날이 자기 캐리어를 갖는가 — 발주처 결정. 정본은 `campaign` 이다."""
    return bool(campaign.SCRAPER_ON_ITS_OWN_CARRIER)


def lead_cost_if_shared_s() -> float:
    """**같은 캐리지였다면** 리드가 가져갔을 시간 (s) — 반사실값.

    리드가 있었던 이유는 휠이다 — 휠이 오기 전에 그 자리가 비어 있어야 했다.
    장변은 통과 한 번에 리드만큼 더 가고, 단변은 횡행 두 번에 각각 더 간다.
    날이 자기 캐리어로 나간 지금 이 시간은 SG-301 에서 **빠졌다.**
    """
    long_extra = BLADE_LEAD_MM / long_feed_mm_s()
    short_extra = 2.0 * BLADE_LEAD_MM / short_feed_mm_s()
    return round(long_extra + short_extra, 3)


def scraper_lead_cost_s() -> float:
    """SG-301 순환에 **실제로 실리는** 리드 비용 (s) — 자기 캐리어면 0 이다."""
    return 0.0 if the_carrier_is_its_own() else lead_cost_if_shared_s()


def occupancy_without_scraper_s() -> float:
    """날을 뺀 SG-301 점유 (s).

    한때 이 함수는 **쓰지 않는 쪽의 값**이었다 — 날이 헤드에 달린 부품이라
    리드가 `cycle()` 안에 있었고, 날 없는 점유를 광고하면 도면이 없는 기계의
    택트를 파는 셈이었다.

    발주처가 날을 자기 캐리어로 옮겨서 이제 `occupancy_s()` 가 **이미** 날 없는
    점유다. 두 값이 같아졌다. 리드가 얼마였는지는 `lead_cost_if_shared_s()` 가
    들고 있다.
    """
    return round(occupancy_s() - scraper_lead_cost_s(), 2)


# ── 자기 캐리어 — 발주처가 날의 거처를 정했다 ───────────────────────────
#
#   동승이 전제였을 때 날의 값은 **리드뿐**이었다. 장비가 안 늘고 통과 거리만
#   길어졌으니까. 캐리어가 따로 서면 그 회계가 통째로 바뀐다 — 리드가 SG-301
#   에서 빠지고, 대신 **날 자신의 운동학**이 새 입력이 된다.
#
#   그 운동학에서 하나는 계산되고 둘은 안 된다. 계산되는 것은 **동력이 한계가
#   아니라는 것**이고, 안 되는 것은 **캐리지가 얼마나 빠른가**와 **몇 면을
#   긁는가**다. 뒤 둘은 여기서 지어내지 않는다.

#: 날이 긁는 면의 수 — 발주처 결정으로 **두 장, 양면 동시**다.
#:
#: 한때 한 장이었고 유리면(아래)에만 섰다. 반출롤러가 변에서 물러나 그 자리를
#: 아래에 내주기 때문이었는데, 정작 BR-305 의 벨트가 지나가는 것은 백시트면
#: (위)이라 잔사 절반이 공구 없이 남았다. 캐리어가 따로 서면서 어느 면으로
#: 들어갈지가 자유로워졌고, 발주처가 두 장으로 정했다.
#:
#: **동시**라는 것이 시간과 힘을 가른다 — 두 날이 한 캐리어에 실려 같이 도니
#: 주행은 한 바퀴 그대로이고(`the_second_blade_costs_no_time()`), 법선력은
#: 마주 보아 상쇄되며 접선력만 더해진다(`the_shoes_oppose_each_other()`).
BLADE_FACES = 2
#: 실란트가 남는 면의 수 — 인발이 양쪽 슬롯 립을 다 남긴다.
RESIDUE_FACES = 2


def scraper_travel_mm() -> float:
    """캐리어가 **주행하는** 거리 (mm) — 둘레 한 바퀴. 날 수와 무관하다.

    두 날이 같은 캐리어에 마주 보고 실리므로 한 바퀴에 두 면이 다 걷힌다.
    시간을 정하는 것은 이쪽이지 아래 `scraper_path_mm()` 이 아니다.
    """
    return round(2.0 * (float(campaign.PANEL_LENGTH_MM)
                        + float(campaign.PANEL_WIDTH_MM)), 1)


def scraper_path_mm(faces: int = BLADE_FACES) -> float:
    """날이 **긁는** 길이 합 (mm) — 면마다 둘레 하나다.

    날 폭 `BLADE_WIDTH_MM` 이 띠 폭보다 넓으므로 한 변에 통과 한 번이면 된다
    (`the_blade_already_covers_the_wider_requirement()`).

    **이것은 주행 거리가 아니다.** 두 날이 동시에 가므로 주행은
    `scraper_travel_mm()` 한 바퀴뿐이다. 이 값이 재는 것은 걷히는 양이고,
    부스러기 회수함과 날 수명이 이쪽에 걸린다.
    """
    return round(scraper_travel_mm() * faces, 1)


def travel_if_one_blade_did_both_faces_mm() -> float:
    """한 장으로 두 면을 **차례로** 걷는다면 주행했을 거리 (mm) — 두 바퀴."""
    return round(scraper_travel_mm() * RESIDUE_FACES, 1)


def the_second_blade_costs_no_time() -> bool:
    """날을 늘려도 주행이 안 느는가 — 「동시」라는 말의 값이 이것이다.

    한 장으로 두 면을 하려면 두 바퀴다. 두 장이 마주 보고 같이 돌면 한 바퀴다.
    날이 하나 늘어난 값으로 **주행 한 바퀴**를 산다.
    """
    return scraper_travel_mm() < travel_if_one_blade_did_both_faces_mm()


def time_the_second_blade_saves_s(feed_mm_s: float) -> float:
    """두 번째 날이 아껴 주는 시간 (s) — 한 바퀴 몫."""
    saved = travel_if_one_blade_did_both_faces_mm() - scraper_travel_mm()
    return round(saved / feed_mm_s, 2)


def scraper_serial_time_s(feed_mm_s: float) -> float:
    """캐리어가 네 변을 **차례로** 돌 때의 시간 (s) — 상한이다.

    **주행 거리에서 나온다**(`scraper_travel_mm()`) — 날이 몇 장인지는 안
    들어간다. 두 날이 마주 보고 같이 가므로 면을 늘려도 이 값이 안 변한다.
    변끼리의 병렬이 하나도 없는 경우라 실제는 이보다 짧다.
    """
    long_t = 2.0 * float(campaign.PANEL_LENGTH_MM) / feed_mm_s
    short_t = 2.0 * float(campaign.PANEL_WIDTH_MM) / feed_mm_s
    return round(long_t + short_t, 2)


def scraper_time_like_sg_heads_s(feed_mm_s: float) -> float:
    """SG-301 과 같은 헤드 배치(장변 2 동기 · 단변 1 횡행)로 갈 때의 시간 (s).

    **배치를 정한 것이 아니라** 지금 있는 배치를 빌려 견주는 값이다. 캐리어의
    헤드 수는 아직 안 들었다.
    """
    long_t = float(campaign.PANEL_LENGTH_MM) / feed_mm_s
    short_t = 2.0 * float(campaign.PANEL_WIDTH_MM) / feed_mm_s
    return round(long_t + short_t, 2)


def scraper_power_at_w(feed_mm_s: float) -> float:
    """그 이송에서 **캐리어**가 내야 하는 동력 (W) — 합력 × 속도.

    날 수만큼 더해진 `tangential_total_n()` 을 쓴다. 한 면 기준은
    `scrape_power_w()` 쪽이다.
    """
    return round(tangential_total_n() * feed_mm_s / 1_000.0, 1)


def scraper_time_left_s() -> float:
    """흡착·해제를 빼고 **실제로 긁을 수 있는** 시간 (s).

    진공 테이블을 쓰면 판을 세우고 빨아 당겼다 놓는 시간이 든다. 그 시간이
    SG-301 이 남긴 여유에서 먼저 빠진다 — 캐리어가 같은 스테이션에 선다면.
    """
    return round(slack_s() - campaign.VACUUM_CYCLE_S, 2)


def feed_that_fits_the_slack_mm_s(like_sg_heads: bool = False) -> float:
    """SG-301 이 남긴 여유 안에 날이 들어가려면 필요한 이송 (mm/s).

    리드가 빠져 여유가 `slack_s()` 로 늘었는데, 진공 테이블이 흡착 시간을
    도로 가져간다. 남는 것이 `scraper_time_left_s()` 이고 그 안에 날의 통과가
    들어가면 캐리어가 같은 스테이션에 서도 된다.
    """
    slack = scraper_time_left_s()
    if slack <= 0.0:
        return float("inf")
    p, w = float(campaign.PANEL_LENGTH_MM), float(campaign.PANEL_WIDTH_MM)
    distance = (p + 2.0 * w) if like_sg_heads else (2.0 * p + 2.0 * w)
    return round(distance / slack, 1)


def the_table_takes_time_back() -> tuple[str, ...]:
    """진공 테이블이 파지를 사 주는 대신 시간을 가져간다 — 공짜가 아니다."""
    return (
        f"**여유가 {slack_s()} s 에서 {scraper_time_left_s()} s 로 준다** — 흡착 "
        f"배기·해제 {campaign.VACUUM_CYCLE_S:.0f} s 가 먼저 빠진다.",
        f"**그만큼 필요한 이송이 올라간다** — 한 날 직렬이면 "
        f"{feed_that_fits_the_slack_mm_s():.0f} mm/s, SG 헤드 배치를 빌리면 "
        f"{feed_that_fits_the_slack_mm_s(like_sg_heads=True):.0f} mm/s 다.",
        f"**동력은 여전히 문제가 아니다** — 그 이송에서도 "
        f"{scraper_power_at_w(feed_that_fits_the_slack_mm_s()):.0f} W 로 스핀들 "
        f"가용의 {scraper_power_at_w(feed_that_fits_the_slack_mm_s()) / spindle_available_w():.1%} "
        "다. 한계는 캐리지와 슈다.",
        "**이 값들은 캐리어가 SG-301 과 같은 스테이션에 선다는 전제다.** 자기 "
        "스테이션을 가지면 여유가 SG 의 것이 아니라 택트에서 나오고 수가 통째로 "
        "달라진다 — **그 자리는 안 들었다.**",
    )


def the_own_carrier_frees_the_feed() -> tuple[str, ...]:
    """캐리어가 따로 서면 이송을 무엇이 정하는가 — 스핀들이 아니다.

    동승일 때 날은 휠의 이송으로 갔다. 그 이송은 **스핀들이 정한 값**이고
    (`feed_is_spindle_bound()`), 날에게는 그것을 따를 이유가 없었다 —
    긁는 것은 계면 일이라 동력이 자릿수로 작다.
    """
    lf = long_feed_mm_s()
    return (
        f"**물려받은 이송 {lf:.0f} mm/s 에서 긁는 동력은 "
        f"{scraper_power_at_w(lf)} W** 다. 스핀들 가용 "
        f"{spindle_available_w():.0f} W 의 "
        f"{scraper_power_at_w(lf) / spindle_available_w():.2%} — 이송을 정한 것이 "
        "날이 아니었다.",
        f"**10 배로 올려도 {scraper_power_at_w(lf * 10):.0f} W** 다. 힘이 "
        f"{scrape_total_force_n()} N 로 고정이라 동력은 속도에 선형이고, 그 "
        "선형이 어디서도 한계에 안 닿는다. **동력은 한계가 아니다.**",
        f"**여유에 들어가려면 {feed_that_fits_the_slack_mm_s():.0f} mm/s** 다 "
        f"(한 날 직렬). SG-301 헤드 배치를 빌리면 "
        f"{feed_that_fits_the_slack_mm_s(like_sg_heads=True):.0f} mm/s 로 내려간다.",
        f"그 이송에서도 동력은 "
        f"{scraper_power_at_w(feed_that_fits_the_slack_mm_s()):.0f} W 다. "
        "**그러니 한계는 동력이 아니라 캐리지와 슈다** — 얼마나 빨리 가도 슈가 "
        "면을 놓치지 않는지, 부스러기가 제때 빠지는지. 둘 다 이 모델에 없다.",
    )


def scraper_fits_the_slack(feed_mm_s: float | None = None,
                           like_sg_heads: bool = False) -> bool:
    """그 이송에서 날의 통과가 SG-301 이 남긴 여유 안에 들어가는가."""
    feed = long_feed_mm_s() if feed_mm_s is None else feed_mm_s
    t = (scraper_time_like_sg_heads_s(feed) if like_sg_heads
         else scraper_serial_time_s(feed))
    return t <= scraper_time_left_s()


def the_back_face_band_has_no_tool() -> bool:
    """백시트면 띠를 걷을 공구가 있는가 — **없다.** 날이 한 장이고 유리면에 선다.

    이것은 캐리어를 옮기려고 리드가 걸린 자리를 훑다가 나온 것이다. 도면이
    말하는 것과 계산이 세는 것이 다르다 —

      · `srband` 의 역할: 「폭 20 × 두께 0.75 가 **유리면에** 남아 있다」
      · `srglass` 의 역할: 「유리면이 아래라 **걷어야 할 띠도 아래에** 있고,
        반출롤러가 변에서 150 mm 물러나 그 자리를 낸다」
      · 그런데 `sealant_volume_per_panel_mm3()` 은 **두 면**을 센다.

    날이 유리면(아래) 띠를 걷는데, **BR-305 의 벨트가 만나는 것은 백시트면
    (위) 띠**다. 그러니 순서만으로는 벨트 앞이 안 치워진다 — 날이 위 면도
    걷어야 한다. 지난 기록에서 이 구분을 안 했다.

    이름이 「없다」이므로 **없을 때 참**이다.
    """
    return BLADE_FACES < RESIDUE_FACES


def how_the_faces_were_made_to_add_up() -> tuple[str, ...]:
    """면 수가 안 맞던 것이 어떻게 맞춰졌는가 — 문제와 답을 같이 남긴다.

    지우지 않고 적어 두는 이유는 값이 거기서 나오기 때문이다. 왜 두 장인지는
    「한 장이면 절반이 공구 없이 남는다」는 사실이 근거다.
    """
    one = sealant_volume_per_panel_mm3(faces=1)
    both = sealant_volume_per_panel_mm3(faces=RESIDUE_FACES)
    return (
        f"**한때 날이 1 면(유리면)이고 잔사는 {RESIDUE_FACES} 면이었다.** "
        f"한 면 {one:,.0f} mm³ 가 걷히고 {both - one:,.0f} mm³ 가 남았는데, "
        "남는 쪽이 하필 **BR-305 의 벨트가 지나가는 백시트면**이었다.",
        f"**걷히는 쪽이 유리면이었던 이유는 기구다** — 반출롤러가 변에서 "
        f"{EDGE_OVERHANG_MM:.0f} mm 물러나 아래에서 날이 들어갈 자리를 냈다. "
        "위 면은 그 자리를 안 만들어 줬고, 휠 헤드에 동승하는 한 그쪽을 "
        "따라갈 수밖에 없었다.",
        f"**자기 캐리어가 그것을 풀었고 발주처가 두 장으로 정했다** — "
        f"`BLADE_FACES` = {BLADE_FACES}, "
        f"`the_back_face_band_has_no_tool()` = "
        f"{the_back_face_band_has_no_tool()}. 이제 한 장에 {both:,.0f} mm³ 가 "
        "다 걷힌다.",
        f"**시간이 안 늘었다** — 두 날이 마주 보고 같이 도니 주행은 한 바퀴 "
        f"{scraper_travel_mm():,.0f} mm 그대로다. 한 장으로 두 면을 하려면 "
        f"{travel_if_one_blade_did_both_faces_mm():,.0f} mm 였다.",
    )


def face_residue_has_a_tool() -> bool:
    """면 실란트를 걷을 공구가 있는가 — SR-302 가 그것이다.

    한때 없었다. 레시피는 '백시트 접촉 압력' 을 선언하는데 AFR 스테이션
    부품표에는 클램프 패드뿐이었다. 이제 조건으로 확인한다 — 걷을 수 있고,
    유리를 안 긁고, 백시트를 남기고, 동력이 든다면 참이다.

    **이 술어는 「공구가 존재하는가」이고 「몇 면을 걷는가」가 아니다.** 날은
    한 장이고 유리면에 선다 — 백시트면 띠는 공구가 없다
    (`the_back_face_band_has_no_tool()`). 이 참을 「두 면이 다 걷힌다」로 읽으면
    안 된다.
    """
    return (blade_can_shear_the_sealant() and blade_cannot_scratch_glass()
            and backsheet_survives_scraping() and shoe_is_gentle_enough()
            and scraping_fits_the_spindle())


def wheel_can_reach_after_scraping() -> bool:
    """띠를 걷고 나면 휠이 유리 모서리에 닿는가 — 날 폭이 어깨 길이를 덮으면 된다."""
    return BLADE_WIDTH_MM >= flange_reach_mm()


# ── 면 전체를 벗긴다면 — 띠에서 나온 답을 면으로 키운다 ─────────────────
#
#   띠 20 mm 에서 답이 한 번 나왔다 (`scrape_beats_abrade_by()`). 같은 물음을
#   백시트 **면 전체**로 키우면 어떻게 되는가.
#
#   다만 면은 띠의 확대판이 아니다. 두 가지를 틀리기 쉬워 여기 적어 둔다 —
#
#   ① **택트.** 면을 걷는 설비는 이 라인에 붙는 헤드가 아니라 자기 정반을
#      갖는 별도 설비다. 그러니 이 라인의 `campaign.AFR_S` 로 나누면 안 되고
#      `FACE_ABRADE_TACT_S` 로 나눠야 한다. 앞의 것으로 나누면 동력이
#      한 자릿수 부풀어 "말도 안 되는 값" 이 나온다.
#   ② **부호.** 면을 걷는 값은 순증이 아니다. 불소 백시트가 먼저 빠지면
#      하류 열박리가 짧아지고 배가스가 순해진다 — `downstream_heat_saved_j()`.
#      돌려받는 쪽을 빼지 않고 재면 이 공법은 항상 진다.
#
#   지금 설계는 면을 안 건드리므로 (`wheel_may_touch_the_backsheet()` 가 거짓)
#   이 절은 **판단 근거**이지 부품표에 걸리는 값이 아니다. 여기서 나온 답이
#   「에너지는 걸림돌이 아니다」 였으므로, 그 다음 물음 — 그러면 그 기계는
#   어떻게 생겼는가 — 은 `br_abrade` (BR-305) 가 받는다.
#
#   **다만 이 절의 하류 열 절감분을 면 연마의 값으로 읽으면 안 된다.** 면을
#   걷는 목적은 배가스의 불소가 아니라 **부유선별 먹이**다 — 불소 폴리머는
#   표면에너지가 낮아 시약 없이도 떠서, 파쇄돼 선별조에 들어오면 화학으로
#   못 막고 정광 품위를 버린다. 열 절감분은 덤이고, 그렇게 보면 걸리는 것도
#   동력이 아니라 **잔존 0 사양과 집진 포집률**이다. `br_abrade` 가 그 쪽을 센다.

def backsheet_face_area_mm2() -> float:
    """백시트 한 면의 넓이 (mm²) — 패널 외형 그대로."""
    return round(float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM), 1)


def backsheet_face_volume_mm3() -> float:
    """면 전체를 갈아 없앨 때의 부피 (mm³)."""
    return round(backsheet_face_area_mm2() * BACKSHEET_T_MM, 1)


def backsheet_abrade_energy_j() -> float:
    """면 전체를 갈아내는 일 (J/장) — **부피 일**이라 두께가 그대로 곱해진다.

    비에너지는 면 고유의 `BACKSHEET_ABRADE_J_MM3` 를 쓴다. 띠에서 쓰는
    `SEALANT_ABRADE_J_MM3` 를 빌려 오면 안 된다 — 경화 실리콘을 좁게 긁는
    값이라 무른 폴리머를 넓게 걷는 이쪽보다 다섯 배쯤 높다.
    """
    return round(backsheet_face_volume_mm3() * BACKSHEET_ABRADE_J_MM3, 1)


def backsheet_abrade_power_w() -> float:
    """그 일을 **면 연마 설비 자기 택트** 안에 끝내려면 드는 동력 (W).

    이 라인의 AFR 택트가 아니다 — 별도 설비이므로 `FACE_ABRADE_TACT_S` 다.
    """
    return round(backsheet_abrade_energy_j() / FACE_ABRADE_TACT_S, 1)


def backsheet_abrade_power_kw() -> float:
    """같은 값을 kW 로 — 시판 연마 설비 정격과 바로 견주라고 둔다."""
    return round(backsheet_abrade_power_w() / 1_000.0, 1)


def backsheet_peel_gc_n_mm() -> float:
    """백시트–EVA 계면의 파괴에너지 (N/mm) — `br_peel` 이 정본이다.

    노후값을 쓴다. 우리가 받는 것은 20 년 된 패널이고, 접착은 세월이
    갈수록 **약해진다.**
    """
    from . import br_peel
    return next(i for i in br_peel.INTERFACES
                if i.key == "backsheet_eva").gc_aged_n_mm


def backsheet_peel_force_n() -> float:
    """면 전체를 계면에서 벗기는 힘 (N) = Gc × 패널 폭.

    두께에 안 걸린다 — 띠에서 쓴 것과 같은 **계면 일**이다. 다만 이 값은
    백시트를 **통째로 EVA 에서** 뜯을 때의 것이다. `br_peel` 이 보여 주듯
    백시트 안쪽에서 불소 외피만 벗기면 20 분의 1 로 내려간다.

    그리고 이 값은 연마와 견주기 위한 **폭 전체 합**이지 그리퍼 사양이
    아니다. 실제 유닛은 칼날 여러 장이 띠를 나눠 문다 —
    한 장이 받는 값은 `br_peel.peel_force_per_blade_n()` 이 든다.
    """
    return round(backsheet_peel_gc_n_mm() * float(campaign.PANEL_WIDTH_MM), 1)


def backsheet_peel_energy_j() -> float:
    """면 전체를 벗기는 일 (J/장) = 힘 × 패널 길이."""
    return round(backsheet_peel_force_n() * float(campaign.PANEL_LENGTH_MM) / 1_000.0, 1)


def backsheet_peel_power_w() -> float:
    """같은 것을 이 라인 이송속도로 벗길 때의 동력 (W)."""
    return round(backsheet_peel_force_n() * long_feed_mm_s() / 1_000.0, 2)


def peel_beats_abrade_by() -> int:
    """벗기는 쪽이 몇 배 싼가 — **장당 일**로 센다.

    띠의 `scrape_beats_abrade_by()` 는 같은 이송속도에서 동력으로 쟀지만
    면에서는 두 공법이 이송속도를 공유하지 않는다. 동력비를 그대로 쓰면
    설비가 느린 것까지 공법 탓으로 세게 되므로 여기서는 일로 견준다.
    """
    return round(backsheet_abrade_energy_j() / backsheet_peel_energy_j())


def backsheet_dust_kg_per_panel() -> float:
    """갈아냈을 때 나오는 폴리머 분진 (kg/장).

    이 값만은 택트에도 비에너지에도 안 걸린다 — 부피 × 밀도뿐이다.
    상수를 어떻게 고치든 집진이 받아야 할 물건의 크기는 이대로 남는다.
    """
    return round(backsheet_face_volume_mm3() * BACKSHEET_DENSITY_G_MM3 / 1_000.0, 2)


def face_abrade_pass_s() -> float:
    """이 라인의 패널이 실증 라인 이송속도로 한 번 지나는 시간 (s)."""
    return round(float(campaign.PANEL_LENGTH_MM) / FACE_ABRADE_FEED_MM_S, 1)


def face_abrade_tact_covers_this_panel() -> bool:
    """실증 라인의 장당 택트 안에 이 패널이 한 번 지나가는가.

    거짓이다. 개구부(`panel_fits_face_abrader()`)와 같은 이야기를 다른 쪽에서
    본 것이다 — 실증 설비는 이 라인보다 작은 패널에 맞춰 세워져 있다.
    공법이 아니라 설비 크기가 다르다는 뜻이고, 그래서 대수를 세야 한다.
    """
    return face_abrade_pass_s() <= FACE_ABRADE_TACT_S


def face_abrade_line_per_h() -> float:
    """면 연마 설비 한 대의 처리량 (장/h)."""
    return round(3_600.0 / FACE_ABRADE_TACT_S, 1)


def face_abraders_needed() -> int:
    """이 라인 속도를 따라가려면 면 연마 설비가 몇 대 필요한가."""
    from . import handoff
    return int(math.ceil(handoff.downstream_rate().line_per_h / face_abrade_line_per_h()))


def backsheet_dust_kg_per_h() -> float:
    """분진을 라인 속도로 환산한 값 (kg/h) — 집진이 받을 물건의 크기."""
    from . import handoff
    return round(backsheet_dust_kg_per_panel() * handoff.downstream_rate().line_per_h, 1)


def panel_fits_face_abrader() -> bool:
    """이 라인의 패널이 실증 연마 설비 개구부에 들어가는가.

    거짓이다 — 공법이 아니라 **치수**가 걸린다. 실증 설비 개구부가 이
    라인의 패널 폭보다 좁다는 뜻이지, 공법이 틀렸다는 뜻이 아니다.
    """
    return float(campaign.PANEL_WIDTH_MM) <= FACE_ABRADE_OPENING_MM


def downstream_heat_j_per_panel() -> float:
    """하류 열박리가 한 장에 넣는 열 (J) — `handoff` 가 정본이다."""
    from . import handoff
    return round(handoff.downstream_rate().heat_per_panel_mj * 1e6, 1)


def downstream_heat_saved_j() -> float:
    """백시트를 먼저 걷어서 하류에서 돌려받는 열 (J/장).

    불소원이 빠지면 열박리가 짧아진다. 이 몫을 세지 않으면 면 연마는
    장부상 언제나 손해로 나온다 — 그것이 이 절의 앞선 오류였다.
    """
    return round(downstream_heat_j_per_panel() * BACKSHEET_FIRST_HEAT_SAVING, 1)


def face_abrade_net_j() -> float:
    """면 연마의 **순** 에너지 (J/장) = 쓰는 값 − 돌려받는 값.

    음수면 걷어내는 쪽이 라인 전체 에너지를 줄인다.
    """
    return round(backsheet_abrade_energy_j() - downstream_heat_saved_j(), 1)


def face_abrading_pays_for_itself() -> bool:
    """면 연마가 제 값을 하는가 — 하류에서 돌려받는 열이 제 소비보다 큰가.

    참이라고 이 라인이 그리로 가야 한다는 뜻은 아니다. 에너지는 걸림돌이
    아니라는 뜻이고, 판단은 분진·설비 대수·개구부 폭에서 갈린다.
    """
    return face_abrade_net_j() <= 0.0


# ── 순환 — 동시인가 순차인가 ────────────────────────────────────────────
def cycle() -> tuple[dict[str, object], ...]:
    """한 장의 연마 순환 (s) — 유리의 운동 상태가 상(相)을 가른다.

    장변은 유리가 **움직여야** 갈리고 단변은 유리가 **서 있어야** 훑을 수 있다.
    두 상태는 배타적이라 동시가 성립하지 않는다 — 그래서 점유가 더해진다.
    """
    # 날이 자기 캐리어로 나갔으므로 통과 거리는 판 치수 그대로다. 동승이면
    # 판 + 리드였다 — 켜고 끄는 것은 `campaign.SCRAPER_ON_ITS_OWN_CARRIER` 다.
    lead = campaign.sg_blade_lead_mm()
    sweep = (float(campaign.PANEL_WIDTH_MM) + lead) / short_feed_mm_s()
    stroke = float(campaign.SG_HEAD_STROKE_S)
    passing = (float(campaign.PANEL_LENGTH_MM) + lead) / long_feed_mm_s()
    index = float(campaign.SG_INDEX_S) / 2.0
    phases = (
        ("앞단변", "정지", SHORT_HEADS, round(sweep + stroke, 3)),
        ("정착", "정지", 0, index),
        ("장변 통과", "이송 300 mm/s", LONG_HEADS, round(passing, 4)),
        ("정착", "정지", 0, index),
        ("뒷단변", "정지", SHORT_HEADS, round(sweep + stroke, 3)),
    )
    out, t = [], 0.0
    for name, motion, heads, dur in phases:
        out.append({"phase": name, "motion": motion, "heads": heads,
                    "start": round(t, 3), "dur": dur, "end": round(t + dur, 3)})
        t += dur
    return tuple(out)


def occupancy_s() -> float:
    """반출롤러 점유 (s) — `campaign.sg_occupancy_s()` 와 같아야 한다."""
    return round(sum(float(p["dur"]) for p in cycle()), 2)


def simultaneous_occupancy_s() -> float:
    """장변과 단변이 **동시**라면 걸렸을 시간 (s) — 되지 않는 쪽의 값."""
    c = cycle()
    short = sum(float(p["dur"]) for p in c if p["phase"].endswith("단변"))
    long = sum(float(p["dur"]) for p in c if p["phase"] == "장변 통과")
    index = sum(float(p["dur"]) for p in c if p["phase"] == "정착")
    return round(max(short, long) + index, 2)


def sequential_cost_s() -> float:
    """순차로 푸는 값 (s) — 동시 대비 더 드는 시간."""
    return round(occupancy_s() - simultaneous_occupancy_s(), 2)


def slack_s() -> float:
    """AFR 정반 점유 대비 남는 시간 (s) — 순차를 감당하는 근거."""
    return round(float(campaign.AFR_S) - occupancy_s(), 2)


def sequential_is_affordable() -> bool:
    """순차로 풀어도 택트가 안 깎이는가."""
    return slack_s() >= 0.0


# ── 단면 다각형 — 3D 가 그대로 스윕한다 ─────────────────────────────────
def edge_outline_before() -> tuple[tuple[float, float], ...]:
    """연마 **전** 라미네이트 변의 단면 (mm) — 원점은 유리 바깥면 모서리.

    u 는 판 안쪽(+)/바깥(−), v 는 두께 방향. 유리대가 위, EVA·백시트가 아래다.
    """
    depth = SECTION_DEPTH_MM                        # 단면을 낼 판 안쪽 길이
    eva = STACK_T_MM - GLASS_T_MM
    return (
        (0.0, 0.0), (0.0, GLASS_T_MM), (-depth, GLASS_T_MM),
        (-depth, -eva), (0.0, -eva),
    )


def edge_outline_after() -> tuple[tuple[float, float], ...]:
    """연마 **후** 단면 (mm) — 유리대만 물러나고 위 모서리가 죽었다.

    EVA·백시트 변은 그 자리에 남는다. 홈 바닥이 닿는 곳은 유리대와 도피 구간뿐이고,
    라미네이트 변선을 기준으로 보면 유리가 살 두께만큼 안으로 들어앉는다.
    """
    depth = SECTION_DEPTH_MM
    eva = STACK_T_MM - GLASS_T_MM
    s, a = STOCK_MM, ARRIS_MM
    return (
        (-s, 0.0), (-s, GLASS_T_MM - a), (-s - a, GLASS_T_MM),
        (-depth, GLASS_T_MM), (-depth, -eva), (0.0, -eva), (0.0, 0.0),
    )


def removed_outline() -> tuple[tuple[float, float], ...]:
    """걷어내는 살의 단면 (mm) — 면적이 `removal_area_mm2()` 와 같아야 한다.

    유리대(0 ≤ v ≤ t)만 센다. 도피 구간의 EVA 는 여기 안 들어간다 —
    `removal_area_mm2()` 의 주기 참고.
    """
    s, a = STOCK_MM, ARRIS_MM
    return (
        (0.0, 0.0), (0.0, GLASS_T_MM), (-s - a, GLASS_T_MM),
        (-s, GLASS_T_MM - a), (-s, 0.0),
    )


def wheel_groove_outline() -> tuple[tuple[float, float], ...]:
    """휠 림의 반경 단면 (mm) — 원점은 **홈 바닥**이자 유리 끝면, u 가 판 안쪽(−).

    **어깨가 하나뿐인 형상휠이다.** 위쪽에는 45° 로 깎인 플랜지가 걸쳐 나와 유리
    바깥 모서리에 아리스를 만들고, 그 아래는 끝면을 미는 바닥면뿐이다. 유리대보다
    아래는 **비어 있다** — 라미네이트(EVA·백시트)가 유리 밑으로 이어지므로 거기에
    플랜지를 두면 폴리머를 문다. 그 대신 바닥면이 계면보다 도피만큼 더 내려와
    유리대를 남김없이 민다.

    이것이 연마 높이 공차가 ±0.10 mm 인 이유다. 낮으면 어깨가 유리대를 파고
    아리스가 제자리를 벗어나고, 높으면 모서리에 아리스가 안 선다. 도피가
    공차보다 커야 어느 쪽으로 틀려도 유리대가 다 갈린다.
    """
    top = GLASS_T_MM + GROOVE_CLEAR_MM
    bot = -GROOVE_RELIEF_MM
    return (
        (0.0, bot),                                 # 바닥면 아래 끝 — 도피
        (0.0, top - ARRIS_MM),                      # 바닥면 — 끝면 살을 민다
        (-ARRIS_MM, top),                           # 45° 어깨 — 아리스를 만든다
        (-GROOVE_ROOT_MM, top),                     # 플랜지 안쪽 면
        (-GROOVE_ROOT_MM, top + GROOVE_LIP_MM),     # 플랜지 끝
        (GROOVE_BODY_MM, top + GROOVE_LIP_MM),
        (GROOVE_BODY_MM, bot - GROOVE_LIP_MM),      # 림 몸통
        (0.0, bot - GROOVE_LIP_MM),
    )


def groove_solid_mm2() -> float:
    """림 단면의 살 면적 (mm²) — 플랜지 띠 + 몸통에서 아리스 모따기를 뺀 값."""
    top = GLASS_T_MM + GROOVE_CLEAR_MM
    bot = -GROOVE_RELIEF_MM
    flange = (GROOVE_ROOT_MM + GROOVE_BODY_MM) * GROOVE_LIP_MM
    bodyband = GROOVE_BODY_MM * ((top - bot) + GROOVE_LIP_MM)
    # 45° 어깨의 쐐기는 **살이다** — 유리 모서리를 파고 들어가 아리스를 만드는
    # 바로 그 부분이므로 더한다. 빼면 형상이 거꾸로 된다.
    return round(flange + bodyband + ARRIS_MM ** 2 / 2.0, 6)


def flange_clears_laminate() -> bool:
    """플랜지가 유리 밑 라미네이트를 안 무는가 — 어깨가 하나뿐이라 항상 참이다.

    선언이 아니라 형상에서 읽는다: 단면에서 v < 0 (유리/EVA 계면 아래) 인 점의
    u 가 하나도 음수가 아니어야 한다 — 음수면 판 안쪽으로 살이 뻗은 것이다.
    """
    return all(u >= 0.0 for u, v in wheel_groove_outline() if v < 0.0)


def sealant_outline_glass_face() -> tuple[tuple[float, float], ...]:
    """유리면에 남은 실란트 띠의 단면 (mm) — 면 위로 솟아 있다.

    이 띠가 휠 어깨가 들어갈 자리를 차지한다. 어깨는 면 위로
    `flange_reach_mm()` 만큼 걸쳐 나오는데 그 구간이 통째로 이 띠 안이다.
    """
    band, th = SEALANT_BAND_MM, sealant_left_t_mm()
    return ((0.0, GLASS_T_MM), (0.0, GLASS_T_MM + th),
            (-band, GLASS_T_MM + th), (-band, GLASS_T_MM))


def sealant_outline_back_face() -> tuple[tuple[float, float], ...]:
    """백시트면에 남은 실란트 띠의 단면 (mm) — 반대 면에도 같은 폭으로 남는다."""
    band, th = SEALANT_BAND_MM, sealant_left_t_mm()
    eva = STACK_T_MM - GLASS_T_MM
    return ((0.0, -eva), (0.0, -eva - th), (-band, -eva - th), (-band, -eva))


def flange_band_overlap_mm2() -> float:
    """휠 어깨와 유리면 실란트 띠가 겹치는 단면적 (mm²) — 0 이 아니면 부딪친다."""
    over = sealant_stands_proud_mm()
    if over <= 0.0:
        return 0.0
    return round(min(flange_reach_mm(), SEALANT_BAND_MM) * over, 6)


def polygon_area_mm2(points: tuple[tuple[float, float], ...]) -> float:
    """신발끈 공식 — 부호 없는 면적 (mm²)."""
    n = len(points)
    two_a = sum(points[i][0] * points[(i + 1) % n][1]
                - points[(i + 1) % n][0] * points[i][1] for i in range(n))
    return round(abs(two_a) / 2.0, 6)


# ── 유닛 — 부품 확대도가 그리는 것 ──────────────────────────────────────
#: 유리가 반출롤러 밖으로 내밀리는 길이 (mm) — 휠이 변을 물 자리를 낸다.
#: 롤러가 변까지 뻗어 있으면 휠과 부딪친다.
EDGE_OVERHANG_MM = 150.0

#: 인피드 행정 (mm) — 대기 자리에서 접촉까지. 힘 제어라 위치가 아니라 힘으로 멈춘다.
INFEED_STROKE_MM = 60.0


def contact_standoff_mm() -> float:
    """접촉 순간의 휠 중심–변 거리 (mm) — 휠 반경 그대로다."""
    return WHEEL_D_MM / 2.0


def head_park_mm() -> float:
    """대기 자리의 휠 중심–변 거리 (mm) — 접촉 거리 + 인피드 행정."""
    return round(contact_standoff_mm() + INFEED_STROKE_MM, 3)


def _spindle_parts(prefix: str, y0: float) -> list[Part]:
    """스핀들 한 대 — 모터·하우징·아버·휠. 두 헤드가 같은 것을 쓴다."""
    hub = WHEEL_BORE_MM + 36.0
    return [
        Part(f"{prefix}mot", "연마 스핀들 모터", 1, "cyl", (128.0, 190.0, 128.0),
             (0.0, y0 + 285.0, 0.0), "IE3 3상 / 인버터", axis="y",
             role=f"휠을 {SPINDLE_RPM:,.0f} rpm 으로 돌린다. 정격 {SPINDLE_KW} kW 중 "
                  f"절삭에 쓰는 몫은 {spindle_available_w():.0f} W 다.",
             color="dark", explode=(0, 320, 0),
             spec=f"{SPINDLE_KW} kW · {SPINDLE_RPM:,.0f} rpm · 인버터",
             catalog="MTR-SG-SP"),
        Part(f"{prefix}hsg", "스핀들 하우징 (앵귤러 콘택트 2열)", 1, "cyl",
             (120.0, 190.0, 120.0), (0.0, y0 + 95.0, 0.0), "주철 / P4 베어링",
             axis="y",
             role=f"법선력 {normal_force_n(long_feed_mm_s()):.0f} N 을 받는다. "
                  "여기가 흔들리면 그대로 유리 흠집이다 — VIB-903 이 감시한다.",
             color="steel", explode=(0, 180, 0), spec="Ø120 × 190 · P4 2열",
             catalog="SG-SP-101"),
        Part(f"{prefix}arb", "아버 · 플랜지 · 고정너트", 1, "cyl",
             (hub, 34.0, hub), (0.0, y0 + 6.0, 0.0), "SCM440 담금질",
             axis="y",
             role="휠을 보어로 물고 축방향으로 조인다.",
             color="chrome", explode=(0, 110, 0),
             spec=f"보어 Ø{WHEEL_BORE_MM:.0f} · 플랜지 Ø{hub:.0f}",
             catalog="SG-SP-102"),
        Part(f"{prefix}whl", "다이아몬드 형상휠", 1, "cyl",
             (WHEEL_D_MM, WHEEL_W_MM, WHEEL_D_MM),
             (0.0, y0 - float(WHEEL_W_MM) / 2 + 6.0, 0.0),
             f"메탈본드 D{GRIT_UM:.0f}", axis="y",
             role=f"주속 {wheel_speed_m_s()} m/s 로 홈이 유리 변을 감싼다. 홈 어깨가 "
                  f"아리스 {ARRIS_MM} 를 만들고 바닥이 끝면 살 {STOCK_MM} 를 걷는다.",
             color="orange", explode=(0, -30, 0),
             spec=f"Ø{WHEEL_D_MM:.0f} × {WHEEL_W_MM:.0f} · 보어 Ø{WHEEL_BORE_MM:.0f} · "
                  f"한계 Ø{WHEEL_SPENT_D_MM:.0f}",
             catalog="SP-03"),
    ]


def long_unit() -> Unit:
    """장변 통과 연마 유닛 — 헤드는 서 있고 유리가 지나간다."""
    half = float(campaign.PANEL_WIDTH_MM) / 2.0
    slab = 1_400.0                                  # 화면에 세우는 유리 조각 길이
    y0 = 0.0                                        # 유리면
    feed = long_feed_mm_s()
    #: 헤드 축선은 변에서 대기 거리만큼 물러나 선다 — 인피드가 그만큼 들어가면
    #: 휠 바깥면이 변에 정확히 닿는다. 눈대중으로 놓으면 붙지도 파고들지도 않는다.
    park = half + head_park_mm()
    parts: list[Part] = [
        Part("col", "헤드 칼럼", LONG_HEADS, "box", (160.0, 620.0, 160.0),
             (0.0, 310.0, park + 260.0), "SS275 각관",
             role="스핀들 두 대를 반출롤러 위 몸체에 매단다.",
             mirror=("z",), color="frame", explode=(0, 0, 300),
             spec="160 × 160 × t6", catalog="SG-301"),
        Part("slide", "컴플라이언스 인피드 슬라이드", LONG_HEADS, "box",
             (240.0, 150.0, 260.0), (0.0, 150.0, park + 120.0), "LM 2열 / 서보",
             role=f"휠을 변 쪽으로 밀어 법선력 {normal_force_n(feed):.0f} N 을 "
                  f"일정하게 유지한다. 휠이 닳으면 장당 {radial_wear_um_per_panel()} µm "
                  "씩 따라 들어간다 — 그것이 '마모 보상' 이다.",
             mirror=("z",), color="steel", explode=(0, 0, 190),
             spec=f"{SPINDLE_COUNT} 축 중 2 · 0.4 kW · 힘 제어", catalog="AXIS-SG-P"),
        Part("load", "인피드 로드셀", LONG_HEADS, "cyl", (56.0, 40.0, 56.0),
             (0.0, 150.0, park + 40.0), "스트레인게이지", axis="z",
             role=f"법선력을 재서 슬라이드에 돌려준다. 설계 {normal_force_n(feed):.0f} N.",
             mirror=("z",), color="chrome", explode=(0, 0, 120),
             spec=f"0–1 kN · 설계점 {normal_force_n(feed):.0f} N", catalog="SG-FS-201"),
        Part("hood", "국소 집진 후드", LONG_HEADS, "box", (300.0, 220.0, 240.0),
             (0.0, 30.0, park - 15.0), "SUS304 t1.5",
             role="유리분과 휠 마모분을 휠 회전 방향에서 받는다. 휠을 감싸므로 "
                  "**반투명으로 그린다** — 실물은 막혀 있다. 이 후드가 서면 연마가 "
                  "선다 — DX-601 은 예비기가 없다.",
             mirror=("z",), color="shroud", explode=(0, -160, 120),
             spec="포집 Ø100 · DS-01 1,000 m³/h · 반투명 표시", catalog="DUCT-S"),
        Part("duct", "집진 지관", LONG_HEADS, "cyl", (100.0, 420.0, 100.0),
             (0.0, 300.0, park + 65.0), "SUS304 나선덕트", axis="y",
             role="후드에서 존 경계를 지나 DX-601 로 간다.",
             mirror=("z",), color="steel", explode=(0, 260, 220),
             spec="Ø100 나선 · 반송풍속 ≥ 20 m/s", catalog="DUCT-S"),
        Part("glass", "라미네이트 (연마 대상 · 참고 표시)", 1, "box",
             (slab, STACK_T_MM, float(campaign.PANEL_WIDTH_MM)),
             (0.0, -STACK_T_MM / 2, 0.0), f"유리 t{GLASS_T_MM} + EVA·백시트",
             role=f"{feed:.0f} mm/s 로 지나간다. 헤드는 안 움직인다 — 길이 "
                  f"{campaign.PANEL_LENGTH_MM:,.0f} 를 지나는 데 "
                  f"{campaign.PANEL_LENGTH_MM / feed:.2f} s.",
             color="ghost", explode=(0, -240, 0),
             spec=f"적층 {STACK_T_MM} (유리 {GLASS_T_MM}) · 폭 "
                  f"{campaign.PANEL_WIDTH_MM:,.0f}", catalog="—"),
        Part("roll", "반출롤러 (연마 통과 이송)", 7, "cylrow",
             (76.0, float(campaign.PANEL_WIDTH_MM) - 2 * EDGE_OVERHANG_MM, 76.0),
             (0.0, -STACK_T_MM - 38.0, 0.0), "강관 / PU 코팅", axis="z",
             role=f"유리를 {feed:.0f} mm/s 로 민다. 롤러는 변에서 "
                  f"{EDGE_OVERHANG_MM:.0f} mm 물러나 끝나 유리가 그만큼 **내밀린다** — "
                  "그래야 휠이 변을 밖에서 문다.",
             color="rubber", explode=(0, -300, 0),
             spec=f"Ø76 × 7 본 @200 · 길이 "
                  f"{campaign.PANEL_WIDTH_MM - 2 * EDGE_OVERHANG_MM:,.0f} · "
                  f"{feed:.0f} mm/s", catalog="MTR-AFR-CV"),
    ]
    for p in _spindle_parts("l", y0):
        parts.append(Part(p.key, p.name, LONG_HEADS, p.shape, p.size,
                          (p.pos[0], p.pos[1], park), p.material, p.role,
                          axis=p.axis, mirror=("z",), color=p.color, spec=p.spec,
                          explode=p.explode, catalog=p.catalog))
    return Unit(
        key="long", name="장변 통과 연마 헤드 (고정 2 대 · 유리가 지나간다)",
        sheet="PV-SG-301-ASM-5201",
        envelope_mm=(slab, 720.0, 2 * (park + 340.0)),
        view_r_mm=1_300.0,
        principle=(
            ("① 높이 맞춤", f"휠 홈을 유리대 {GLASS_T_MM} mm 에 **±0.10 mm** 로 맞춘다. "
                         "낮으면 EVA 를 물어 폴리머가 휠에 먹고, 높으면 아리스가 안 난다. "
                         "이 공차가 이 장비에서 가장 빡빡한 수다."),
            ("② 인피드 접촉", f"슬라이드가 휠을 변 쪽으로 밀어 법선력 "
                          f"{normal_force_n(feed):.0f} N 에서 멈춘다. 위치가 아니라 "
                          f"**힘**으로 멈추므로 휠이 닳아도 접촉이 유지된다."),
            ("③ 통과 연마", f"유리가 {feed:.0f} mm/s 로 들어온다. 휠은 제자리에서 "
                         f"{wheel_speed_m_s()} m/s 로 돌아 속도비 "
                         f"{speed_ratio(feed):.0f} : 1 이다. 변 1 mm 마다 단면 "
                         f"**{removal_area_mm2()} mm²** 가 떨어진다 — 그중 "
                         f"{arris_share() * 100:.0f} % 가 아리스 삼각형이다."),
            ("④ 동력 한계", f"제거율 {removal_rate_mm3_s(feed)} mm³/s 에 비에너지 "
                         f"{SPECIFIC_ENERGY_J_MM3:.0f} J/mm³ 를 곱하면 "
                         f"**{cutting_power_w(feed):.0f} W** 다. 스핀들이 내주는 "
                         f"{spindle_available_w():.0f} W 의 **{utilisation(feed) * 100:.0f} %** — "
                         f"한계 통과속도가 {max_feed_mm_s():.0f} mm/s 라 여유가 "
                         f"{feed_margin() * 100:.0f} % 뿐이다. **300 mm/s 는 컨베이어가 아니라 "
                         "스핀들이 정한 값이다.**"),
            ("⑤ 두 변 동시", f"장변 2 대는 **서로 동시**다 — 같은 유리의 양쪽 변을 같은 "
                          f"이송으로 갈므로 동기가 저절로 맞는다. 단변과는 동시가 안 된다: "
                          f"장변은 유리가 움직여야 갈리고 단변은 서 있어야 훑는다."),
        ),
        parts=tuple(parts))


def short_unit() -> Unit:
    """단변 횡행 연마 유닛 — 유리는 서 있고 헤드가 폭을 훑는다."""
    width = float(campaign.PANEL_WIDTH_MM)
    rail = 1_900.0
    feed = short_feed_mm_s()
    #: 앞단변이 x = 0 에 선다. 헤드는 그만큼 물러나 있다가 인피드로 붙는다.
    park = -head_park_mm()
    parts: list[Part] = [
        Part("rail", "횡행 레일 (z · 폭 1,400 행정)", 2, "box",
             (60.0, 40.0, rail), (RAIL_SPAN_MM / 2, 520.0, 0.0),
             "35급 프로파일 레일",
             role=f"헤드가 폭 {width:,.0f} 를 건너간다. 유리는 그동안 선다.",
             mirror=("x",), color="chrome", explode=(0, 190, 0),
             spec=f"길이 {rail:,.0f} · 행정 {width:,.0f}", catalog="SG-3T"),
        Part("car", "횡행 캐리지", 1, "box", (420.0, 120.0, 380.0),
             (0.0, 440.0, 0.0), "S355 용접 / LM 블록 4",
             role=f"스핀들을 싣고 {feed:.0f} mm/s 로 건넌다. 편도 "
                  f"{width / feed:.1f} s.",
             color="steel", explode=(0, 260, 0),
             spec=f"{feed:.0f} mm/s · 0.4 kW 서보", catalog="AXIS-SG-T"),
        Part("belt", "횡행 구동 벨트·풀리", 2, "cyl", (90.0, 70.0, 90.0),
             (0.0, 520.0, rail / 2 - 60.0), "HTD8M / 서보", axis="z",
             role="양 끝 풀리가 캐리지를 끌고 되돌린다.",
             mirror=("z",), color="dark", explode=(0, 190, 190),
             spec="HTD8M 폭 30", catalog="AXIS-SG-T"),
        Part("zsl", "인피드 슬라이드 (x)", 1, "box", (200.0, 130.0, 240.0),
             (park - 25.0, 330.0, 0.0), "LM 2열 / 서보",
             role=f"휠을 앞·뒤 단변 쪽으로 밀어 법선력 {normal_force_n(feed):.0f} N "
                  "을 유지한다.",
             color="steel", explode=(-220, 0, 0),
             spec=f"{SPINDLE_COUNT} 축 중 1 · 0.4 kW", catalog="AXIS-SG-P"),
        Part("hood", "횡행 집진 후드", 1, "box", (260.0, 200.0, 280.0),
             (park + 55.0, 40.0, 0.0), "SUS304 t1.5",
             role="캐리지를 따라 같이 건너간다 — 후드가 헤드를 떠나면 유리분이 "
                  "라미네이트 위에 떨어진다. 휠을 감싸므로 **반투명으로 그린다**.",
             color="shroud", explode=(0, -170, 0),
             spec="포집 Ø100 · 캐리지 동행 · 반투명 표시", catalog="DUCT-S"),
        Part("glass", "라미네이트 앞단변 (참고 표시)", 1, "box",
             (700.0, STACK_T_MM, width), (350.0, -STACK_T_MM / 2, 0.0),
             f"유리 t{GLASS_T_MM} + EVA·백시트",
             role="정지 상태다. 스토퍼가 변을 레일 밑 기준선에 세운다.",
             color="ghost", explode=(240, -220, 0),
             spec=f"폭 {width:,.0f} · 적층 {STACK_T_MM}", catalog="—"),
        Part("stop", "단변 기준 스토퍼", 2, "box", (50.0, 90.0, 120.0),
             (-40.0, -60.0, width / 2 - 200.0), "S45C / PU 패드",
             role="변을 휠 홈 높이에 맞춰 세운다. 정착 오차가 그대로 아리스 폭이 "
                  "된다.",
             mirror=("z",), color="rubber", explode=(-160, -120, 0),
             spec="정착 ±0.5", catalog="SG-3T"),
    ]
    for p in _spindle_parts("s", 0.0):
        parts.append(Part(p.key, p.name, SHORT_HEADS, p.shape, p.size,
                          (park, p.pos[1], p.pos[2]), p.material, p.role,
                          axis=p.axis, color=p.color, spec=p.spec,
                          explode=p.explode, catalog=p.catalog))
    return Unit(
        key="short", name="단변 횡행 연마 헤드 (1 대 · 유리는 선다)",
        sheet="PV-SG-3T-5301",
        envelope_mm=(940.0, 700.0, rail),
        view_r_mm=1_050.0,
        principle=(
            ("① 유리 정지", f"앞단변이 스토퍼에 닿아 선다. 장변 통과와 달리 "
                         "**이송이 멈춰야** 헤드가 변을 따라갈 수 있다 — 이것이 두 연마가 "
                         "동시에 못 되는 이유다."),
            ("② 헤드 하강·인피드", f"캐리지가 휠을 변 높이로 내리고 앞으로 밀어 "
                              f"{normal_force_n(feed):.0f} N 에서 멈춘다. 하강·상승에 "
                              f"{campaign.SG_HEAD_STROKE_S:.1f} s 가 든다."),
            ("③ 횡행 연마", f"캐리지가 폭 {width:,.0f} 를 {feed:.0f} mm/s 로 건넌다 "
                         f"({width / feed:.1f} s). 이송이 느린 만큼 스핀들 이용률은 "
                         f"**{utilisation(feed) * 100:.0f} %** 로 장변보다 여유가 있다."),
            ("④ 뒷단변", f"장변 통과가 끝나면 뒷단변이 같은 자리에 선다. 같은 헤드가 "
                      f"한 번 더 훑는다 — 그래서 단변 상(相)이 순환에 두 번 든다."),
            ("⑤ 순환 합계", f"앞단변 {cycle()[0]['dur']} + 장변 {cycle()[2]['dur']} + "
                         f"뒷단변 {cycle()[4]['dur']} + 정착 {campaign.SG_INDEX_S} = "
                         f"**{occupancy_s()} s**. 동시라면 {simultaneous_occupancy_s()} s "
                         f"였을 것이고, 순차로 푸는 값이 {sequential_cost_s()} s 다. "
                         f"AFR 정반 점유 {campaign.AFR_S} s 안에 "
                         f"{slack_s()} s 가 남으므로 택트는 안 깎인다."),
        ),
        parts=tuple(parts))


def contact_unit() -> Unit:
    """휠–유리 접촉부 — 실제 형상 그대로, 배율만 20 배."""
    mag = CONTACT_MAG
    feed = long_feed_mm_s()
    length = 260.0                                  # 화면에 세우는 변 길이
    parts = (
        Part("edge", "연마 전 변 단면", 1, "polyBefore",
             (length, STACK_T_MM * mag, 0.0), (0.0, 0.0, 0.0),
             f"유리 t{GLASS_T_MM} · EVA/백시트 t{STACK_T_MM - GLASS_T_MM:.1f}",
             role="프레임을 뜯어낸 직후의 변. 유리 절단면이 그대로 서 있고 위 모서리가 "
                  "날카롭다.",
             color="frame", explode=(0, 0, -260),
             spec=f"적층 {STACK_T_MM} · 유리대 {GLASS_T_MM}", catalog="—"),
        Part("cutaway", "걷어내는 살", 1, "polyRemoved",
             (length, GLASS_T_MM * mag, 0.0), (0.0, 0.0, 0.0), "제거 유리",
             role=f"끝면 살 {STOCK_MM} 와 아리스 삼각형이다. 단면적 "
                  f"**{removal_area_mm2()} mm²** — 그중 {arris_share() * 100:.0f} % 가 "
                  "아리스라 동력을 먹는 것은 모따기 쪽이다.",
             color="orange", explode=(0, 220, 0),
             spec=f"A = {removal_area_mm2()} mm² · 살 {STOCK_MM} · 아리스 {ARRIS_MM}",
             catalog="—"),
        Part("done", "연마 후 변 단면", 1, "polyAfter",
             (length, STACK_T_MM * mag, 0.0), (0.0, 0.0, 0.0),
             f"유리 t{GLASS_T_MM}",
             role=f"끝면이 {STOCK_MM} 물러나고 위 모서리에 {ARRIS_MM} × "
                  f"{ARRIS_DEG:.0f}° 아리스가 섰다. GI-302 가 이 단면을 본다.",
             color="aluminum", explode=(0, 0, 260),
             spec=f"아리스 {ARRIS_MM} × {ARRIS_DEG:.0f}° × {ARRIS_COUNT} 곳",
             catalog="—"),
        Part("sealG", "유리면 잔사 실란트 띠", 1, "polySealG",
             (length, sealant_left_t_mm() * mag, SEALANT_BAND_MM * mag),
             (0.0, 0.0, 0.0), f"실란트 (프레임 접착 잔사)",
             role=f"프레임 슬롯이 면을 {SEALANT_BAND_MM:.0f} mm 덮고 있었고, 인발이 "
                  f"응집파괴라 {sealant_left_t_mm()} mm 가 면에 남는다. **이 띠가 휠 "
                  f"어깨가 들어갈 자리를 차지한다** — 어깨는 면 위로 "
                  f"{flange_reach_mm():.0f} mm 걸쳐 나오는데 그 구간이 통째로 띠 안이다.",
             color="orange", explode=(0, 300, -180),
             spec=f"폭 {SEALANT_BAND_MM:.0f} × 두께 {sealant_left_t_mm()} · "
                  f"홈 여유보다 **{sealant_stands_proud_mm()} mm 두껍다**",
             catalog="—"),
        Part("sealB", "백시트면 잔사 실란트 띠", 1, "polySealB",
             (length, sealant_left_t_mm() * mag, SEALANT_BAND_MM * mag),
             (0.0, 0.0, 0.0), "실란트 (프레임 접착 잔사)",
             role=f"반대 면에도 같은 폭으로 남는다. 한 장에 두 면 합쳐 "
                  f"**{sealant_volume_per_panel_mm3():,.0f} mm³** — 유리에서 걷는 양의 "
                  f"**{sealant_ratio_to_glass()} 배**다. 이쪽을 걷을 공구가 이 장비에 없다.",
             color="rubber", explode=(0, -300, -180),
             spec=f"폭 {SEALANT_BAND_MM:.0f} × 두께 {sealant_left_t_mm()} · "
                  f"허용 압착력 {safe_face_force_n():.0f} N (변의 1/{face_force_ratio():.0f})",
             catalog="—"),
        Part("rim", "휠 림 단면 (홈)", 1, "polyWheel",
             (length, 0.0, 0.0), (0.0, 0.0, 0.0), f"메탈본드 D{GRIT_UM:.0f}",
             role=f"홈이 변을 감싼다. 위 어깨 {ARRIS_DEG:.0f}° 가 아리스를 만들고 "
                  "바닥이 끝면을 걷는다. 아래 어깨는 평평하다 — EVA 를 물면 안 된다.",
             color="dark", explode=(0, 0, 300),
             spec=f"Ø{WHEEL_D_MM:.0f} 림 · 홈 깊이 {GROOVE_ROOT_MM} · "
                  f"위 여유 {GROOVE_CLEAR_MM} · 아래 도피 {GROOVE_RELIEF_MM} · "
                  f"입도 D{GRIT_UM:.0f}",
             catalog="SP-03"),
        Part("grit", "다이아몬드 입자", 9, "gritrow",
             (GRIT_UM / 1_000.0 * mag * 3, GRIT_UM / 1_000.0 * mag * 3,
              GRIT_UM / 1_000.0 * mag * 3),
             (0.0, GLASS_T_MM * mag / 2, -GRIT_UM / 1_000.0 * mag * 1.5),
             f"다이아몬드 D{GRIT_UM:.0f}",
             role=f"입자 하나가 지나며 떼는 두께가 등가 칩두께 "
                  f"**{chip_thickness_mm(feed) * 1_000:.2f} µm** 다. 연성한계 "
                  f"{ductile_limit_mm() * 1_000:.3f} µm 의 "
                  f"**{brittleness_ratio(feed):.0f} 배**라 유리는 흐르지 않고 "
                  "**깨져서** 떨어진다.",
             color="chrome", explode=(0, 160, 0),
             spec=f"D{GRIT_UM:.0f} (≈{GRIT_UM:.0f} µm) · 메탈본드", catalog="—"),
    )
    return Unit(
        key="contact", name=f"휠–유리 접촉부 (실제 형상 · {mag:.0f} 배 확대)",
        sheet="PV-SG-301-DET-5401",
        envelope_mm=(length, (STACK_T_MM + 2 * GROOVE_LIP_MM) * mag,
                     (SECTION_DEPTH_MM + GROOVE_BODY_MM) * mag),
        view_r_mm=300.0,
        principle=(
            ("① 홈이 변을 문다", f"홈 열림은 유리대 {GLASS_T_MM} 에 상·하 여유 0.3 씩을 "
                            f"더한 값이다. 변이 그 안으로 들어가면 세 면 — 끝면과 위 "
                            f"모따기면, 그리고 아래 도피면 — 이 한 번에 잡힌다."),
            ("② 끝면 살", f"바닥이 끝면에서 {STOCK_MM} mm 를 걷는다. 프레임 인발이 남긴 "
                       f"잔사와 미세 파단면이 여기서 없어진다. 연마 **전** 검사 헤드였던 "
                       f"GI-301 은 REV.50 통합(V-4)에서 은퇴해, 잔사는 연마 **뒤**에 "
                       f"GI-302(백시트 쪽)·GI-303(유리 쪽)만 본다 — 전/후 비교가 없으니 "
                       f"공정창이 고정이어야 한다는 뜻이고, 그 전제가 서려면 면에 남는 몫 "
                       f"({SEALANT_RETAINED:.0%} 계획값)이 실측돼야 한다."),
            ("③ 아리스", f"위 어깨가 {ARRIS_MM} × {ARRIS_DEG:.0f}° 모따기를 만든다. 단면적으로는 "
                      f"이쪽이 {arris_share() * 100:.0f} % 라 **동력의 대부분을 모따기가 "
                      f"먹는다.** 아래 모서리는 안 건드린다 — EVA 와 만나는 쪽이다."),
            ("④ 취성 절삭", f"입자 하나가 떼는 등가 칩두께는 "
                        f"{chip_thickness_mm(feed) * 1_000:.2f} µm 이고 연성한계 "
                        f"d_c = 0.15(E/H)(K_c/H)² = {ductile_limit_mm() * 1_000:.3f} µm "
                        f"의 **{brittleness_ratio(feed):.0f} 배**다. 그러니 유리는 소성으로 "
                        f"흐르지 않고 미세균열로 떨어진다 — 갈린 면은 **파단면**이다."),
            ("⑤ 왜 아리스인가", "파단면에는 균열이 남는다. 날카로운 모서리에 남으면 그 "
                          "균열이 응력 집중을 받아 자란다. 모따기는 장식이 아니라 "
                          "**균열 끝을 응력이 낮은 자리로 옮기는 일**이다 — 취성으로 갈 수밖에 "
                          "없으니 모서리를 죽여야 한다."),
            ("⑥ 그런데 못 닿는다", f"프레임이 남기고 간 실란트 띠가 면을 "
                            f"{SEALANT_BAND_MM:.0f} mm 덮고 있고 두께가 "
                            f"{sealant_left_t_mm()} mm 다. 홈 여유 {GROOVE_CLEAR_MM} 보다 "
                            f"**{sealant_stands_proud_mm()} mm 두꺼워** 어깨가 유리 모서리에 "
                            f"닿기 전에 실란트에 먼저 얹힌다 (겹침 단면 "
                            f"{flange_band_overlap_mm2()} mm²). 여유를 실란트보다 벌리면 "
                            "어깨가 모서리에서 떨어져 아리스가 안 선다 — **둘 다는 안 된다.** "
                            f"띠에서 최소 {sealant_must_go_first_mm():.0f} mm 를 먼저 걷어야 "
                            "하고, 그 공구는 이 장비에 없다."),
        ),
        parts=parts)


def scraper_unit() -> Unit:
    """SR-302 잔사 스크레이퍼 — 휠보다 앞서 가며 실란트 띠를 걷는다."""
    lf = long_feed_mm_s()
    lead = BLADE_LEAD_MM
    # 날과 휠이 원점을 사이에 두고 서게 자리를 옮긴다 — 리드가 이 유닛의
    # 주제이므로 그 간격이 화면 한가운데 와야 한다.
    hx = lead / 2.0
    # 라미네이트 중립면 (y) — 아래쪽 세트를 이 면에 대해 거울상으로 놓는다.
    mid = -STACK_T_MM / 2 - 8.0
    parts = (
        Part("srarm", "스크레이퍼 아암 (컴플라이언스)", 1, "box", (260.0, 90.0, 150.0),
             (hx, 168.0, 0.0), "S355 / 평행 링크",
             role=f"날을 면 쪽으로 {SHOE_SPRING_N:.0f} N 으로 누른다. 위치가 아니라 "
                  "**힘**으로 누르므로 판 두께가 흔들려도 깊이가 안 바뀐다.",
             color="frame", explode=(0, 200, 0),
             spec=f"평행 링크 · 스프링 {SHOE_SPRING_N:.0f} N", catalog="SR-302"),
        Part("srspr", "압착 스프링", 1, "cyl", (34.0, 90.0, 34.0),
             (hx, 92.0, 0.0), "SUS 압축 스프링", axis="y",
             role=f"허용 면 압착력 {safe_face_force_n():.0f} N 의 "
                  f"{SHOE_SPRING_N / safe_face_force_n():.0%} 만 쓴다. 셀이 먼저 상하면 "
                  "안 되기 때문이다.",
             color="chrome", explode=(0, 150, 0),
             spec=f"{SHOE_SPRING_N:.0f} N · 접촉압 {shoe_pressure_mpa()} MPa",
             catalog="SR-302"),
        Part("srshoe", "기준 슈", 1, "box", (SHOE_LEN_MM, 12.0, BLADE_WIDTH_MM),
             (hx + 18.0, 8.0, 0.0), "PEEK",
             role="라미네이트 면에 얹혀 **깊이를 판에서 잡는다.** 기계 프레임을 "
                  f"기준으로 잡으면 공차합 {depth_stack_mm()} mm 가 백시트 "
                  f"{BACKSHEET_T_MM} mm 를 넘어 뚫는다 — 그래서 슈다.",
             color="aluminum", explode=(0, -120, 0),
             spec=f"{SHOE_LEN_MM:.0f} × {BLADE_WIDTH_MM:.0f} · 남는 오차 "
                  f"{blade_assembly_tol_mm()} mm", catalog="SR-302"),
        Part("srbld", "PEEK 스크레이퍼 날", 1, "box",
             (16.0, 22.0, BLADE_WIDTH_MM), (hx - 40.0, 2.0, 0.0), BLADE_MATERIAL,
             role=f"경도 {BLADE_HARDNESS_GPA} GPa 로 유리({GLASS_H_GPA} GPa)를 **못 긁고** "
                  f"경화 실란트({SEALANT_HARDNESS_GPA} GPa)는 뗀다. 계면을 떼는 일이라 "
                  f"필요한 힘이 Gc × 폭 = **{scrape_force_n():.0f} N** 뿐이다.",
             color="orange", explode=(-140, -60, 0),
             spec=f"폭 {BLADE_WIDTH_MM:.0f} · 경사 {BLADE_RAKE_DEG:.0f}° · 날끝 R"
                  f"{BLADE_EDGE_R_MM}", catalog="SR-302"),
        Part("srchip", "부스러기 슈트", 1, "box", (90.0, 120.0, 90.0),
             (hx - 78.0, 66.0, 0.0), "SUS304 t1.5",
             role="걷힌 실란트가 **고체 부스러기**로 떨어진다 — 분진이 아니라서 "
                  "집진 흐름에 폴리머가 안 들어가고 DS-01 의 '불연' 선언이 그대로 선다.",
             color="dark", explode=(-90, 140, 0),
             spec="고체 회수 · 집진 미연결", catalog="SR-302"),
        Part("srband", "걷어내는 실란트 띠", 1, "box",
             (300.0, sealant_left_t_mm() * BAND_DISPLAY_MAG, SEALANT_BAND_MM),
             (hx + 250.0, -sealant_left_t_mm() * BAND_DISPLAY_MAG / 2, 0.0),
             "실란트 잔사",
             role=f"폭 {SEALANT_BAND_MM:.0f} × 두께 {sealant_left_t_mm()} 가 유리면에 "
                  f"남아 있다. 한때 이것을 걷는 이유가 **휠 어깨**였다 — 띠가 "
                  f"있으면 어깨가 유리 모서리에 못 닿았다. 지금 이유는 "
                  f"**BR-305 의 벨트**다: 띠가 백시트보다 "
                  f"{sealant_left_t_mm() - BACKSHEET_T_MM:.2f} mm 솟아 벨트가 그것을 "
                  f"먼저 만난다. 그런데 벨트가 지나가는 것은 **반대 면**이라 "
                  f"거기까지 걷는 배치가 아직 없다. (두께는 보이라고 "
                  f"{BAND_DISPLAY_MAG:.0f} 배로 그렸다)",
             color="rubber", explode=(180, -140, 0),
             spec=f"{SEALANT_BAND_MM:.0f} × {sealant_left_t_mm()} · 표시 두께 "
                  f"{BAND_DISPLAY_MAG:.0f} 배",
             catalog="—"),
        # ── 아래쪽 세트 — 라미네이트 중립면(y = mid)에 대한 거울상 ──────
        Part("srarm2", "스크레이퍼 아암 · 아래", 1, "box", (260.0, 90.0, 150.0),
             (hx, 2 * mid - 168.0, 0.0), "S355 / 평행 링크",
             role=f"위 아암과 **같은 자리에서 마주 본다.** 그래야 압착 "
                  f"{SHOE_SPRING_N:.0f} N 이 판 안에서 닫혀 알짜가 "
                  f"{normal_net_on_panel_n():.0f} N 이 된다 — 주행 방향으로 "
                  "어긋나면 우력이 되어 판을 비튼다. 요크 한 몸이어야 하는 "
                  "이유가 이것이다.",
             color="frame", explode=(0, -200, 0),
             spec=f"평행 링크 · 스프링 {SHOE_SPRING_N:.0f} N · 위와 대향",
             catalog="SR-302"),
        Part("srspr2", "압착 스프링 · 아래", 1, "cyl", (34.0, 90.0, 34.0),
             (hx, 2 * mid - 92.0, 0.0), "SUS 압축 스프링", axis="y",
             role=f"위 스프링과 같은 {SHOE_SPRING_N:.0f} N 이다. 두 배로 "
                  f"누르는 것이 아니라 **무는** 것이라 한 면이 받는 압착은 "
                  f"그대로 {SHOE_SPRING_N:.0f} N 이고 허용 "
                  f"{safe_face_force_n():.0f} N 안에 있다.",
             color="chrome", explode=(0, -150, 0),
             spec=f"{SHOE_SPRING_N:.0f} N · 무는 힘 {clamp_force_n():.0f} N",
             catalog="SR-302"),
        Part("srshoe2", "기준 슈 · 아래", 1, "box",
             (SHOE_LEN_MM, 12.0, BLADE_WIDTH_MM), (hx + 18.0, 2 * mid - 8.0, 0.0),
             "PEEK",
             role="아래 면에 얹혀 그쪽 깊이를 잡는다. 두 슈가 판을 물면 "
                  "깊이 기준이 **판 두께 그 자체**가 되어 한쪽 면의 흔들림이 "
                  "반대쪽 깊이로 안 넘어간다.",
             color="aluminum", explode=(0, 120, 0),
             spec=f"{SHOE_LEN_MM:.0f} × {BLADE_WIDTH_MM:.0f} · 남는 오차 "
                  f"{blade_assembly_tol_mm()} mm", catalog="SR-302"),
        Part("srbld2", "PEEK 스크레이퍼 날 · 아래", 1, "box",
             (16.0, 22.0, BLADE_WIDTH_MM), (hx - 40.0, 2 * mid - 2.0, 0.0),
             BLADE_MATERIAL,
             role=f"반대 면 띠를 **같은 바퀴에** 걷는다. 계면력은 위와 같은 "
                  f"{scrape_force_n():.0f} N 인데 **같은 방향**이라 접선은 "
                  f"더해져 캐리어가 끄는 힘이 {tangential_total_n()} N 이다.",
             color="orange", explode=(-140, 60, 0),
             spec=f"폭 {BLADE_WIDTH_MM:.0f} · 경사 {BLADE_RAKE_DEG:.0f}° · 날끝 R"
                  f"{BLADE_EDGE_R_MM}", catalog="SR-302"),
        Part("srchip2", "부스러기 슈트 · 아래", 1, "box", (90.0, 120.0, 90.0),
             (hx - 78.0, 2 * mid - 66.0, 0.0), "SUS304 t1.5",
             role=f"아래 면 부스러기를 받는다. 두 슈트가 한 장에서 받는 양이 "
                  f"{sealant_volume_per_panel_mm3():,.0f} mm³ — 한 장일 때의 "
                  "두 배라 회수함 용량도 두 배다.",
             color="dark", explode=(-90, -140, 0),
             spec="고체 회수 · 집진 미연결", catalog="SR-302"),
        Part("srband2", "걷어내는 실란트 띠 · 백시트면", 1, "box",
             (300.0, sealant_left_t_mm() * BAND_DISPLAY_MAG, SEALANT_BAND_MM),
             (hx + 250.0, 2 * mid + sealant_left_t_mm() * BAND_DISPLAY_MAG / 2, 0.0),
             "실란트 잔사",
             role=f"반대 면에도 같은 폭으로 남는다. **이쪽이 BR-305 의 벨트가 "
                  f"지나가는 면**이라 여기를 안 걷으면 띠가 백시트보다 "
                  f"{sealant_left_t_mm() - BACKSHEET_T_MM:.2f} mm 솟은 채로 "
                  f"벨트를 맞는다. (두께는 보이라고 {BAND_DISPLAY_MAG:.0f} 배로 "
                  "그렸다)",
             color="rubber", explode=(180, 140, 0),
             spec=f"{SEALANT_BAND_MM:.0f} × {sealant_left_t_mm()} · 표시 두께 "
                  f"{BAND_DISPLAY_MAG:.0f} 배",
             catalog="—"),
        Part("srwhl", "다이아몬드 형상휠 (같은 캐리지였을 때)", 1, "cyl",
             (WHEEL_D_MM, WHEEL_W_MM, WHEEL_D_MM), (-hx, -6.5, 0.0),
             f"메탈본드 D{GRIT_UM:.0f}", axis="y",
             role=f"동승이던 동안 날이 지나간 자리를 {lead:.0f} mm 뒤에서 받았다. "
                  f"장비가 안 늘고 순환만 {lead_cost_if_shared_s()} s 늘었다. "
                  f"**지금은 같은 캐리지가 아니다** — 발주처가 날을 자기 캐리어로 "
                  f"옮겨서 이 휠은 날을 기다리지 않고, 그 리드가 SG-301 에서 "
                  f"빠졌다(실리는 리드 {scraper_lead_cost_s()} s). 그리고 이 휠 "
                  f"자체도 목적이 없다 — 아리스 공정 요구가 없다.",
             color="ghost", explode=(240, 0, 0),
             spec=f"Ø{WHEEL_D_MM:.0f} · 동승이었다면 리드 {lead:.0f} mm",
             catalog="SP-03"),
        Part("srtable", "진공 테이블 (변에서 물려 선다)", 1, "box",
             (620.0, 90.0, float(campaign.PANEL_WIDTH_MM) - 2 * TABLE_INSET_MM),
             (hx + 180.0, mid - STACK_T_MM / 2 - 45.0, 0.0),
             "알루미늄 + 실링 패드",
             role=f"판을 **유리면에서** 빨아 당겨 잡는다. 변에서 "
                  f"{TABLE_INSET_MM:.0f} mm 물러나 **아래 날이 들어갈 자리**를 "
                  f"낸다 — 날 폭 {BLADE_WIDTH_MM:.0f} mm 보다 넓어야 하고, "
                  f"BR-305 에는 없던 제약이다(그쪽은 한 면만 건드린다). 무는 "
                  f"면적이 {table_area_share():.1%} 로 줄어도 면내 "
                  f"{table_friction_kn()} kN 이라 끄는 힘 {tangential_total_n()} N "
                  f"의 {table_margin_over_drag():,.0f} 배다. **그리퍼 패드 "
                  f"{grip_pad_area_needed_mm2():,.0f} mm² 가 이것으로 대체됐다.**",
             color="frame", explode=(0, -420, 0),
             spec=f"{campaign.VACUUM_KPA:.0f} kPa · {table_hold_kn()} kN · "
                  f"변에서 {TABLE_INSET_MM:.0f} 물림", catalog="SR-302"),
        Part("srglass", "라미네이트 (유리면이 아래)", 1, "box",
             (820.0, STACK_T_MM, 240.0), (0.0, -STACK_T_MM / 2 - 8.0, 0.0),
             f"유리 t{GLASS_T_MM} + EVA·백시트",
             role=f"진공 테이블에 물려 **서 있다** — 도는 것은 캐리어다. "
                  f"유리면이 아래라 **이 날이 걷는 띠도 "
                  f"아래에** 있고, 테이블이 변에서 {TABLE_INSET_MM:.0f} mm 물러나 "
                  f"그 자리를 낸다. 위 면(백시트) 띠는 위 날이 **같은 바퀴에** "
                  f"걷는다 — 잔사 {RESIDUE_FACES} 면을 날 {BLADE_FACES} 장이 "
                  "동시에 맡는다.",
             color="ghost", explode=(0, -260, 0),
             spec=f"적층 {STACK_T_MM} · 내밀림 {EDGE_OVERHANG_MM:.0f}", catalog="—"),
    )
    return Unit(
        key="scraper", name="SR-302 잔사 스크레이퍼 (자기 캐리어 · 양면 동시 · 진공 테이블)",
        sheet="PV-SR-302-ASM-5501",
        envelope_mm=(900.0, 500.0, 300.0), view_r_mm=560.0,
        principle=(
            ("① 왜 필요한가", f"프레임이 남기고 간 실란트 띠가 면을 "
                          f"{SEALANT_BAND_MM:.0f} mm 덮고 두께가 {sealant_left_t_mm()} mm 다. "
                          f"한때 이유가 휠이었다 — 어깨가 면 위로 "
                          f"{flange_reach_mm():.0f} mm 걸쳐 나오니 띠를 먼저 걷지 "
                          f"않으면 유리 모서리에 닿지도 못했다. 아리스 공정 요구가 "
                          f"없어지면서 그 이유가 빠지고, 지금 이유는 **BR-305 의 "
                          f"벨트**다: 띠가 백시트보다 "
                          f"{sealant_left_t_mm() - BACKSHEET_T_MM:.2f} mm 솟아 압반 "
                          f"추종으로는 못 따라간다. 요구 폭도 어깨 몫 "
                          f"{sealant_must_go_first_mm():.0f} mm 에서 **띠 전체 "
                          f"{SEALANT_BAND_MM:.0f} mm** 로 넓어졌다 — 날 폭 "
                          f"{BLADE_WIDTH_MM:.0f} mm 가 이미 덮는다."),
            ("② 왜 긁는가", f"같은 띠를 **갈아냈다면** "
                        f"{abrade_power_w(lf) / 1000:,.0f} kW 가 든다 — 부피 일이기 "
                        f"때문이다. **긁으면** 계면 일이라 Gc × 폭 = "
                        f"{scrape_force_n():.0f} N, 동력으로는 {scrape_power_w(lf)} W 다. "
                        f"**{scrape_beats_abrade_by():,} 배** 차이라 선택의 여지가 없다."),
            ("③ 왜 PEEK 인가", f"경도 {BLADE_HARDNESS_GPA} GPa 는 유리 {GLASS_H_GPA} GPa "
                          f"보다 무르므로 **유리를 못 긁는다.** 경화 실란트 "
                          f"{SEALANT_HARDNESS_GPA} GPa 보다는 단단해 그것은 뗀다. "
                          "금속 날이면 제품 면에 흠을 낸다."),
            ("④ 왜 슈로 받는가", f"기계 프레임을 기준으로 깊이를 잡으면 공차합이 "
                            f"{depth_stack_mm()} mm 인데 백시트가 {BACKSHEET_T_MM} mm 다 — "
                            f"뚫는다. 슈가 라미네이트에 얹혀 **판 면에서** 깊이를 잡으면 "
                            f"남는 오차가 날끝 반경 {blade_assembly_tol_mm()} mm 뿐이다. "
                            f"압착도 {SHOE_SPRING_N:.0f} N 으로 허용 "
                            f"{safe_face_force_n():.0f} N 의 "
                            f"{SHOE_SPRING_N / safe_face_force_n():.0%} 만 쓴다."),
            ("⑤ 값은 캐리어다", f"한때 날이 휠보다 {lead:.0f} mm 앞서 가는 부품이었고 "
                          f"값이 리드 {lead_cost_if_shared_s()} s 뿐이었다. 발주처가 "
                          f"**자기 캐리어**로 정해서 그 리드가 SG-301 에서 빠졌다 — "
                          f"점유 {occupancy_s()} s, AFR 정반 {campaign.AFR_S} s 안에 "
                          f"{slack_s()} s 여유. 대신 **날 자신의 운동학**이 값이 "
                          f"된다: 경로 {scraper_path_mm():,.0f} mm 를 여유 안에 "
                          f"가려면 {feed_that_fits_the_slack_mm_s():.0f} mm/s 이고 "
                          f"그때 동력은 "
                          f"{scraper_power_at_w(feed_that_fits_the_slack_mm_s()):.0f} W "
                          "다 — 한계는 동력이 아니라 캐리지와 슈다."),
            ("⑥ 아직 안 맞는 것", f"날이 **{BLADE_FACES} 면**(유리면)에 서는데 잔사는 "
                            f"**{RESIDUE_FACES} 면**에 남는다. 백시트면 "
                            f"{sealant_volume_per_panel_mm3(faces=1):,.0f} mm³ 가 "
                            f"공구 없이 남고 그것이 **BR-305 의 벨트가 지나가는 "
                            f"면**이다. 캐리어가 따로 서면 어느 면으로 들어갈지 "
                            f"자유롭지만 그 배치는 아직 안 들었다."),
        ),
        parts=parts)


def units() -> tuple[Unit, ...]:
    return (long_unit(), short_unit(), contact_unit(), scraper_unit())


def summary() -> dict[str, object]:
    lf, sf = long_feed_mm_s(), short_feed_mm_s()
    return {
        "wheelSpeedMS": wheel_speed_m_s(),
        "contactWidthMm": contact_width_mm(),
        "removalAreaMm2": removal_area_mm2(),
        "arrisShare": arris_share(),
        "equivalentDepthMm": equivalent_depth_mm(),
        "contactLengthMm": contact_length_mm(),
        "longPass": {"feedMmS": lf, "rateMm3S": removal_rate_mm3_s(lf),
                     "powerW": cutting_power_w(lf), "utilisation": utilisation(lf)},
        "shortSweep": {"feedMmS": sf, "rateMm3S": removal_rate_mm3_s(sf),
                       "powerW": cutting_power_w(sf), "utilisation": utilisation(sf)},
        "availableW": spindle_available_w(),
        "maxFeedMmS": max_feed_mm_s(),
        "feedMargin": feed_margin(),
        "feedIsSpindleBound": feed_is_spindle_bound(),
        "stallingSpecificEnergy": specific_energy_that_stalls(),
        "chipUm": round(chip_thickness_mm(lf) * 1_000, 4),
        "ductileLimitUm": round(ductile_limit_mm() * 1_000, 5),
        "brittlenessRatio": brittleness_ratio(lf),
        "arrisIsRequired": arris_is_required(),
        "arrisRequiredByPlant": ARRIS_REQUIRED_BY_PLANT,
        "scraperKeptByPlant": SCRAPER_KEPT_BY_PLANT,
        "scraperOwnCarrier": the_carrier_is_its_own(),
        "leadCostIfSharedS": lead_cost_if_shared_s(),
        "scraperPathMm": scraper_path_mm(),
        "feedToFitSlackMmS": feed_that_fits_the_slack_mm_s(),
        "scraperFitsTheSlack": scraper_fits_the_slack(),
        "backFaceBandHasNoTool": the_back_face_band_has_no_tool(),
        "bladeFaces": BLADE_FACES,
        "scraperTravelMm": scraper_travel_mm(),
        "tangentialTotalN": tangential_total_n(),
        "normalNetOnPanelN": normal_net_on_panel_n(),
        "clampForceN": clamp_force_n(),
        "gripAdopted": GRIP_ADOPTED,
        "tableInsetMm": TABLE_INSET_MM,
        "tableHoldKn": table_hold_kn(),
        "tableMarginOverDrag": table_margin_over_drag(),
        "scraperTimeLeftS": scraper_time_left_s(),
        "gripForceNeededN": grip_force_needed_n(),
        "gripPadAreaMm2": grip_pad_area_needed_mm2(),
        "gripPadSideMm": grip_pad_side_mm(),
        "gripMomentNm": grip_moment_n_m(),
        "gripInboardMm": grip_must_sit_inboard_mm(),
        "normalForceN": normal_force_n(lf),
        "contactPressureMpa": contact_pressure_mpa(lf),
        "reliefCoversTolerance": relief_covers_tolerance(),
        "evaSkimMm": eva_skim_mm(),
        "glassDown": panel_is_glass_down(),
        "sealantBandMm": SEALANT_BAND_MM,
        "sealantLeftMm": sealant_left_t_mm(),
        "sealantPerPanelMm3": sealant_volume_per_panel_mm3(),
        "sealantVsGlass": sealant_ratio_to_glass(),
        "wheelReachesEdge": wheel_can_reach_the_glass_edge(),
        "sealantProudMm": sealant_stands_proud_mm(),
        "flangeOverlapMm2": flange_band_overlap_mm2(),
        "mustClearFirstMm": sealant_must_go_first_mm(),
        "rubbingRatio": rubbing_speed_ratio(),
        "wheelMayTouchBacksheet": wheel_may_touch_the_backsheet(),
        "dustStaysInert": dust_stream_stays_inert(),
        "depthStackMm": depth_stack_mm(),
        "positionControlSafe": position_control_is_safe(),
        "backsheetMarginMm": backsheet_margin_mm(),
        "safeFaceForceN": safe_face_force_n(),
        "faceForceRatio": face_force_ratio(),
        "headsAgreeWithDust": heads_agree_with_the_dust_model(),
        "twoPassOccupancyS": two_pass_occupancy_s(),
        "openQuestions": [list(q) for q in open_questions()],
        "scrapeForceN": scrape_force_n(),
        "scrapePowerW": scrape_power_w(lf),
        "abradePowerW": abrade_power_w(lf),
        "scrapeBeatsAbradeBy": scrape_beats_abrade_by(),
        "backsheetFaceVolumeMm3": backsheet_face_volume_mm3(),
        "backsheetAbradePowerW": backsheet_abrade_power_w(),
        "backsheetPeelForceN": backsheet_peel_force_n(),
        "backsheetPeelPowerW": backsheet_peel_power_w(),
        "peelBeatsAbradeBy": peel_beats_abrade_by(),
        "backsheetPeelEnergyJ": backsheet_peel_energy_j(),
        "backsheetAbradePowerKw": backsheet_abrade_power_kw(),
        "backsheetDustKgPerPanel": backsheet_dust_kg_per_panel(),
        "backsheetDustKgPerH": backsheet_dust_kg_per_h(),
        "faceAbradePassS": face_abrade_pass_s(),
        "faceAbradeTactCoversThisPanel": face_abrade_tact_covers_this_panel(),
        "faceAbradeLinePerH": face_abrade_line_per_h(),
        "faceAbradersNeeded": face_abraders_needed(),
        "panelFitsFaceAbrader": panel_fits_face_abrader(),
        "downstreamHeatSavedJ": downstream_heat_saved_j(),
        "faceAbradeNetJ": face_abrade_net_j(),
        "faceAbradingPaysForItself": face_abrading_pays_for_itself(),
        "shoePressureMpa": shoe_pressure_mpa(),
        "bladeAssemblyTolMm": blade_assembly_tol_mm(),
        "backsheetSurvives": backsheet_survives_scraping(),
        "faceToolExists": face_residue_has_a_tool(),
        "scraperLeadCostS": scraper_lead_cost_s(),
        "occupancyWithoutScraperS": occupancy_without_scraper_s(),
        "maxGcNMm": max_gc_the_face_limit_allows(),
        "gcMargin": gc_margin(),
        "impliedGRatio": implied_g_ratio(),
        "radialWearUmPerPanel": radial_wear_um_per_panel(),
        "occupancyS": occupancy_s(),
        "simultaneousS": simultaneous_occupancy_s(),
        "sequentialCostS": sequential_cost_s(),
        "slackS": slack_s(),
        "units": [{"key": u.key, "name": u.name, "sheet": u.sheet,
                   "partKinds": len(u.parts),
                   "partCount": sum(p.qty for p in u.parts),
                   "steps": len(u.principle)} for u in units()],
    }
