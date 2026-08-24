"""설계 기준 (Design Basis) — 태양광 셀 Ag 회수 부선 설비.

**본 기준은 참고문헌 [1][2] (``references.py``) 의 실증 데이터로 보정했다.**
이전 판(문헌 없이 일반 광물부선 관행으로 추정)과 달라진 핵심은 다음과 같다.

1. Ag 는 대부분 회수 가능하다. TIMA 해리도 분석에서 Si 기지 내부에 갇힌
   난용성 Ag 는 거의 없고, 박리만으로도 전면 전극이 상당 부분 노출된다.
   회분식 실증 회수율이 97.6 %, 연속 실증은 ~100 % 다.
2. 황화(Na2S)·pH 조정·억제제가 **필요 없다**. 디티오포스핀산계 포수제
   (AEROPHINE 3418A) 가 금속 Ag 표면에 직접 선택 흡착한다 (ToF-SIMS 로
   Ag 위 신호가 주변 대비 ~100배). 자연 pH 에서 운전한다.
3. 부선이 매우 빠르다. 회분식 1분에 80 %, 3분에 90 %. 연속 실증의 기액
   체류시간은 **1분**이다.
4. 급광에 Cu 는 사실상 없다 (0.013 wt%). 리본은 상류 박리 공정에서
   제거되므로 Cu 는 부산물이 아니라 미량 원소다.
5. 급기는 훨씬 적다 (Jg 0.2~0.35 cm/s). 동반 혼입을 억제하기 위함이다.

상류 공정 전제: 프레임·정션박스 해체 → 박리로 셀 분획 분리 →
습식 로드밀 분쇄 (P80 66 um) → 본 설비. 셀 분획은 모듈 질량의 약 4.7 %.
"""

from __future__ import annotations

from . import references as ref
from .feed import Component, FeedSpec
from .kinetics import ComponentKinetics
from .reagents import Reagent
from .sizing import CellGeometry

# --------------------------------------------------------------------------
# 급광
# --------------------------------------------------------------------------
#: 박리된 c-Si 셀 분획의 대표 조성 (건조 고체 기준 질량분율).
#: Ag·Cu·Pb 는 [2] 및 [1] Table 2 의 실측 assay, Al 은 후면 전극 페이스트
#: 기준 추정, 나머지는 Si 웨이퍼와 미량 잔재.
CELL_FRACTION = (
    Component("Si", 0.88200, 2.33),
    Component("Al", 0.10000, 2.70),
    Component("Ag", 0.00590, 10.49),
    Component("Pb", 0.00096, 11.34),
    Component("Cu", 0.00013, 8.96),
    Component("Other", 0.01101, 2.20),
)

#: 설계 고체 농도. 연속 실증은 2 wt%(원료 부족 때문), 회분식은 7 wt% 에서
#: 검증됐다. 저자들은 30 wt% 까지 가능하다고 보지만 PV 원료로는 미검증이므로,
#: **검증된 7 wt% 를 설계점으로 잡고 상향 여유를 남긴다.**
DESIGN_SOLIDS_WT = 0.07

FEED = FeedSpec(
    components=CELL_FRACTION,
    average_tph=0.30,
    peak_tph=0.50,
    solids_mass_fraction=DESIGN_SOLIDS_WT,
    p80_micron=ref.CONTINUOUS_TRIAL.p80_micron,
    deslime_cut_micron=0.0,  # 탈니 없음 — 문헌 공정은 전량 부선한다
)

#: 성분별 비중 — 흐름의 체적유량 계산용.
SPECIFIC_GRAVITY = {c.name: c.specific_gravity for c in CELL_FRACTION}

# --------------------------------------------------------------------------
# 부선 거동 — [1] 의 회분식 데이터에 맞춘 2속도 모델
# --------------------------------------------------------------------------
#: 아래 속도상수는 **회분식(batch)** 기준이다. 실기 연속 셀에서는 통상
#: 배치 대비 속도가 떨어지므로 아래 계수를 곱해 보수적으로 쓴다.
#: 기계식 셀의 표준 스케일업 관행(체류시간 2~2.5배)에 해당한다.
PLANT_SCALE_FACTOR = 0.8

FLOAT_MODELS = {
    # Ag: [1] 회분식 곡선 R(1min)=0.80, R(3min)=0.90, R(inf)=0.976 에 맞춤.
    # 비부선 2.4 % 는 TIMA 상 사실상 봉입된 극소량.
    "Ag": ComponentKinetics("Ag", 0.820, 2.60, 0.156, 0.30, entrainment_factor=0.35),
    # Cu: [1] Table 2 회수율 81.4 % @ 3 min 에 맞춤.
    "Cu": ComponentKinetics("Cu", 0.680, 2.20, 0.220, 0.30, entrainment_factor=0.35),
    # Pb: [1] Table 2 회수율 20.9 % @ 3 min. 땜납 잔재로 부상성이 낮다.
    "Pb": ComponentKinetics("Pb", 0.150, 1.50, 0.100, 0.25, entrainment_factor=0.35),
    # Si·Al·기타: 진부선 없음. 정광 혼입은 전량 수분 동반.
    "Si": ComponentKinetics("Si", entrainment_factor=0.35),
    "Al": ComponentKinetics("Al", entrainment_factor=0.35),
    "Other": ComponentKinetics("Other", entrainment_factor=0.40),
}

# --------------------------------------------------------------------------
# 1안 (주설계) — 세척수 bias 연속 부선조 1단
# --------------------------------------------------------------------------
#: [2] 의 실증 flux 를 그대로 유지하고 단면적만 키우는 flux 상사 스케일업.
RFC_TAG = "FC-101"
RFC_DUTY = "1단 연속 부선조 (세척수 bias)"

#: 양의 bias flux. 클수록 품위가 오르고 회수율이 미세하게 떨어진다.
RFC_BIAS_FLUX_CM_S = 0.25

#: 경사판(inclined channel) — 미광부 침강 강화.
RFC_CHANNEL_ANGLE_DEG = 70.0
RFC_CHANNEL_SPACING_MM = 12.0

#: 실증에서 관측된 맥석 회수율 (정광 중 비 Ag 고체 / 급광 중 비 Ag 고체).
#: 세척수 bias 덕분에 회분식 기계식 셀(2.2 %)의 약 1/3.5 수준이다.
RFC_GANGUE_RECOVERY = 0.0064

#: 실증 정상상태의 Ag 회수율. 미광 assay 가 검출한계 이하였다.
RFC_AG_RECOVERY = 0.997

# --------------------------------------------------------------------------
# 2안 (대안) — 기계식 러퍼 + 클리너
# --------------------------------------------------------------------------
#: 회분식 최적 부선시간 3분 x 스케일업 2배.
ROUGHER_RESIDENCE_MIN = 6.0
CLEANER_RESIDENCE_MIN = 6.0

GAS_HOLDUP = 0.15
FREEBOARD_M = 0.06
HEIGHT_TO_WIDTH = 1.15

#: [1] 의 운전 조건 — 기계식 셀은 급기를 매우 낮게 가져간다.
MECHANICAL_JG_CM_S = {"FC-201": 0.30, "FC-202": 0.20}
MECHANICAL_JG_RANGE_CM_S = {"FC-201": (0.15, 0.45), "FC-202": (0.10, 0.35)}
MECHANICAL_TIP_SPEED_M_S = {"FC-201": 5.3, "FC-202": 4.5}
MECHANICAL_WATER_RECOVERY = {"FC-201": 0.06, "FC-202": 0.04}
IMPELLER_DIAMETER_RATIO = 0.35
IMPELLER_POWER_NUMBER = 4.2
BUBBLE_D32_MM = 0.8


def _cell(
    width_m: float,
    shell_height_m: float,
    froth_depth_m: float,
    gas_holdup: float,
    freeboard_m: float = FREEBOARD_M,
) -> CellGeometry:
    return CellGeometry(
        width_m=width_m,
        shell_height_m=shell_height_m,
        lip_height_m=shell_height_m - freeboard_m,
        froth_depth_m=froth_depth_m,
        gas_holdup=gas_holdup,
    )


#: 러퍼 FC-201 / 클리너 FC-202 확정 치수.
#: 7 wt% 운전은 슬러리 체적이 커서 기계식 셀이 크게 나온다 —
#: 이것이 2안이 1안보다 불리한 핵심 이유다.
ROUGHER_CELL = _cell(0.80, 0.92, 0.075, GAS_HOLDUP)

#: 러퍼는 동일 셀 2기 직렬(뱅크). 같은 총 체적이라도 직렬 분할이
#: 단일 완전혼합조보다 Ag 회수율이 5.6 %p 높다.
ROUGHER_CELLS_IN_SERIES = 2
CLEANER_CELL = _cell(0.45, 0.62, 0.150, 0.12)

MECHANICAL_CELLS = (
    ("FC-201", "러퍼 (Rougher)", ROUGHER_CELL),
    ("FC-202", "클리너 (Cleaner)", CLEANER_CELL),
)

#: 클리너 급광 희석 목표와 세척수.
CLEANER_FEED_SOLIDS = 0.05
CLEANER_WASH_WATER_M3H = 0.25

# --------------------------------------------------------------------------
# 약제 — pH 조정제·황화제·억제제 없음
# --------------------------------------------------------------------------
#: [2] 에 따라 **습식 분쇄 원료 기준 300 g/t** 를 쓴다. 건조 원료의 최적
#: 투입량은 150 g/t 였으나, 습식 분쇄물은 거품 형성이 부족해 2배가 필요했다.
#: 실기는 습식 분쇄물을 그대로 쓰므로 300 g/t 가 설계값이다.
REAGENTS = (
    Reagent(
        name="AEROPHINE 3418A (sodium diisobutyl dithiophosphinate)",
        role="포수제",
        dose=300.0,
        solution_strength=0.10,
        solution_sg=1.02,
        addition_point="CT-1 조건조",
        basis="solids",
        note="금속 Ag 표면에 직접 선택 흡착한다 (ToF-SIMS: Ag 위 신호가 "
        "주변 대비 약 100배). **황화 전처리가 필요 없다.**",
    ),
    Reagent(
        name="AEROFLOAT 242 (dithiophosphate + thiourea 촉진제)",
        role="촉진제",
        dose=300.0,
        solution_strength=0.10,
        solution_sg=1.02,
        addition_point="CT-1 조건조",
        basis="solids",
        note="3418A 와 병용해 Ag 포집을 보강한다. 건조 원료 기준 최적은 "
        "150 g/t 였으나 습식 분쇄물에는 300 g/t 가 필요했다.",
    ),
    Reagent(
        name="MIBC",
        role="기포제",
        dose=30.0,
        solution_strength=1.00,
        solution_sg=0.81,
        addition_point="급광박스",
        basis="water",
        note="연속 운전에서 거품 안정화를 위해 별도 기포제로 투입. "
        "물 기준 30 ppm 이므로 고체 농도를 올리면 t 당 소요량이 줄어든다. "
        "수용해도가 약 17 g/L 라 희석하면 정량펌프 유량이 20 L/h 까지 커지므로 "
        "**원액 투입**하고, 소용량 정량펌프에 검량통(calibration column)을 단다.",
    ),
)

#: pH 는 조정하지 않는다 — [1][2] 모두 자연 pH 에서 운전했다.
PH_CONTROL = None

# --------------------------------------------------------------------------
# 조건조
# --------------------------------------------------------------------------
#: 약제 접촉 시간. [1] 의 ToF-SIMS 조건조는 1 h 였으나 이는 표면분석용
#: 과잉 조건이고, 부선 시험 자체는 통상적인 수 분 조건조로 수행됐다.
CONDITIONER_STAGES = (
    ("CT-1", "포수제 + 촉진제 (3418A / AEROFLOAT 242)", 5.0),
)


#: 부상한 Ag 1 kg 이 **같은 입자의 일부로** 달고 올라가는 맥석의 kg.
#: Ag 는 Si 웨이퍼에 소결된 전극이므로, 표면이 소수성이 되어 부상해도
#: Si 코어를 함께 끌고 온다. 수분 동반과 달리 세척수로 제거되지 않으며,
#: **정광 품위의 물리적 상한 1/(1+r) 을 만든다.**
#: 연속 실증 정광이 48.8 wt% Ag 에서 멈춘 것, 회분식 러퍼+클리너가
#: 46.7 wt% 에서 멈춘 것이 모두 이 상한으로 설명된다 (1/(1+1.1) = 47.6 %).
COMPOSITE_CARRY_RATIO = 1.1
