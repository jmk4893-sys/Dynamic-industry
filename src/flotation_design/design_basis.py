"""설계 기준 (Design Basis) — 태양광 패널 재활용 Ag/Cu 회수용 단단 부선기.

전제 공정 (본 부선기의 상류):
    1. 프레임/정션박스 해체 → 2. 유리 박리(기계식 또는 산화분위기 열처리
    500 degC, EVA 완전 산화) → 3. 셀 분획 파쇄·분쇄 P80 = 75 um
    → 4. 사이클론 탈니(deslime) 10 um 미만 분리 → 5. 본 부선기

Ag 는 스크린 인쇄·소성으로 Si 표면(에미터)에 유리프릿을 매개로 고착되어
있어 분쇄만으로 완전 해리되지 않는다. 다만 부선은 '입자 표면'의 젖음성으로
분리하는 공정이므로, Si 를 코어로 하고 Ag 가 표면에 노출된 복합입자도
정광으로 부상한다. 따라서 본 설계는 완전 해리를 전제하지 않고
'Ag 노출 복합입자의 부상'을 목표로 하며, 미해리분에 기인하는 회수 상한을
``r_max`` 로 명시한다.
"""

from __future__ import annotations

from .feed import Component, FeedSpec
from .kinetics import FloatComponentModel
from .reagents import Reagent

# --------------------------------------------------------------------------
# 급광
# --------------------------------------------------------------------------
#: 유리 박리 후 '셀 분획'의 대표 조성 (건조 고체 기준 질량분율).
#: Ag 0.45 wt% = 4,500 g/t 는 60셀 모듈(셀+금속 분획 약 0.8 kg, Ag 약 5 g)
#: 기준값이며, 유리 미분 혼입률에 따라 실제 값은 크게 달라진다.
CELL_FRACTION = (
    Component("Si", 0.6200, 2.33),
    Component("Glass", 0.1800, 2.50),
    Component("Cu", 0.0800, 8.96),
    Component("Al", 0.0800, 2.70),
    Component("Ag", 0.0045, 10.49),
    Component("SnPb", 0.0120, 7.40),
    Component("Polymer", 0.0235, 1.20),
)

FEED = FeedSpec(
    components=CELL_FRACTION,
    average_tph=0.30,
    peak_tph=0.50,
    solids_mass_fraction=0.25,
    p80_micron=75.0,
    deslime_cut_micron=10.0,
)

# --------------------------------------------------------------------------
# 셀 설계 파라미터
# --------------------------------------------------------------------------
#: 최대 처리량(0.5 t/h) 기준 목표 유효 체류시간 (분).
#: 단단 구성이라 스캐빈저가 없으므로 통상 러퍼(4~6분)보다 길게 잡는다.
TARGET_RESIDENCE_AT_PEAK_MIN = 10.0

GAS_HOLDUP = 0.15
FROTH_DEPTH_M = 0.075
FREEBOARD_M = 0.06
HEIGHT_TO_WIDTH = 1.15

#: 제작 확정 치수 (계산값 반올림).
CELL_WIDTH_M = 0.70
CELL_SHELL_HEIGHT_M = 0.81

IMPELLER_DIAMETER_RATIO = 0.35
IMPELLER_TIP_SPEED_M_S = 5.5
IMPELLER_POWER_NUMBER = 4.2

JG_DESIGN_CM_S = 1.0
BUBBLE_D32_MM = 1.2

WATER_RECOVERY = 0.12

# --------------------------------------------------------------------------
# 성분별 부선 거동 (실험실 배치 부선시험으로 확정 필요한 가정값)
# --------------------------------------------------------------------------
FLOAT_MODELS = {
    # Ag: 황화 후 잔티에이트로 잘 부상하나, Si 와의 미해리 복합입자 중
    # Ag 가 표면에 전혀 노출되지 않은 분율(약 12%)은 원리적으로 회수 불가.
    "Ag": FloatComponentModel("Ag", k_per_min=0.45, r_max=0.88, entrainment_factor=0.55),
    # 금속 Cu (리본): 황화 후 부상성 양호.
    "Cu": FloatComponentModel("Cu", k_per_min=0.80, r_max=0.95, entrainment_factor=0.50),
    # 땜납(Sn/Pb) 피복 리본 파편.
    "SnPb": FloatComponentModel("SnPb", k_per_min=0.70, r_max=0.90, entrainment_factor=0.50),
    # Al (BSF/프레임 잔재): 부동태 산화막으로 부상성 낮음.
    "Al": FloatComponentModel("Al", k_per_min=0.12, r_max=0.30, entrainment_factor=0.50),
    # Si: 규산소다로 억제. 혼입은 사실상 전량 수분 동반(entrainment).
    "Si": FloatComponentModel("Si", k_per_min=0.0, r_max=0.0, entrainment_factor=0.55),
    "Glass": FloatComponentModel("Glass", k_per_min=0.0, r_max=0.0, entrainment_factor=0.50),
    # 잔류 유기물(EVA/백시트 char): 본질적으로 소수성이라 거의 전량 부상.
    # 열처리를 산화분위기로 완전히 수행하지 못하면 정광을 크게 희석한다.
    "Polymer": FloatComponentModel("Polymer", k_per_min=1.20, r_max=0.90, entrainment_factor=0.60),
}

# --------------------------------------------------------------------------
# 약제 계통
# --------------------------------------------------------------------------
REAGENTS = (
    Reagent(
        name="Na2CO3 (소다회)",
        role="pH 조정제",
        dose_g_per_t=800.0,
        solution_strength=0.10,
        solution_sg=1.10,
        addition_point="CT-1",
        note="pH 9.0~9.5 유지. 석회(Ca2+)는 Ag 부상을 억제하므로 사용 금지.",
    ),
    Reagent(
        name="Sodium silicate (규산소다, modulus 2.4)",
        role="분산/억제제",
        dose_g_per_t=400.0,
        solution_strength=0.10,
        solution_sg=1.08,
        addition_point="CT-1",
        note="Si·유리 미분 억제 및 슬라임 코팅 방지.",
    ),
    Reagent(
        name="Na2S-9H2O",
        role="황화제",
        dose_g_per_t=350.0,
        solution_strength=0.10,
        solution_sg=1.08,
        addition_point="CT-1 (분할 투입)",
        note="금속 Ag/Cu 표면을 황화하여 포수제 흡착을 유도. ORP -450~-520 mV "
        "(Ag/AgCl) 로 폐루프 제어. 과잉 투입 시 오히려 억제됨.",
    ),
    Reagent(
        name="PAX (potassium amyl xanthate)",
        role="포수제 (주)",
        dose_g_per_t=120.0,
        solution_strength=0.02,
        solution_sg=1.00,
        addition_point="CT-2",
        note="2% 수용액으로 매일 신규 조제 (48h 이내 사용). pH 9 이상 유지.",
    ),
    Reagent(
        name="Dithiophosphinate (Aerophine 3418A 상당)",
        role="포수제 (보조)",
        dose_g_per_t=40.0,
        solution_strength=0.05,
        solution_sg=1.02,
        addition_point="CT-2",
        note="Ag 선택성 보강. 잔티에이트 단독 대비 Ag 회수율 3~6%p 개선.",
    ),
    Reagent(
        name="MIBC",
        role="기포제",
        dose_g_per_t=30.0,
        solution_strength=0.01,
        solution_sg=1.00,
        addition_point="셀 급광박스",
        note="취성 거품 형성 — 미립 금속 정광에 적합. 과잉 시 맥석 혼입 증가. "
        "원액 소요량이 정량펌프 최소 토출량보다 작으므로 1% 수용액으로 "
        "희석 투입한다 (20 degC 수용해도 약 17 g/L).",
    ),
)

# --------------------------------------------------------------------------
# 조건조
# --------------------------------------------------------------------------
CONDITIONER_STAGES = (
    ("CT-1", "pH 조정 + 분산/억제제 + 황화제", 5.0),
    ("CT-2", "포수제 (PAX + dithiophosphinate)", 3.0),
)
