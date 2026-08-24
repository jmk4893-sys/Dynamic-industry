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
from .sizing import CellGeometry
from .kinetics import ComponentKinetics
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
#: 러퍼 단독(Phase 1) 구성에서 최대 처리량 기준 목표 유효 체류시간 (분).
#: 스캐빈저가 없으므로 통상 러퍼(4~6분)보다 길게 잡았다. 스캐빈저를 붙인
#: 뒤에는 순환부하만큼 유량이 늘어 실제 체류시간이 8.5분 수준으로 내려가는데,
#: 이는 스캐빈저가 있는 러퍼의 정상적인 duty 다.
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
    # Ag: 황화 후 잔티에이트로 잘 부상한다. 다만 Ag 노출면이 큰 입자(속부선)와
    # 소결 접합면이 겨우 드러난 복합입자(지연부선)의 거동 차이가 크고,
    # Ag 가 Si 내부에 완전히 갇힌 12% 는 원리적으로 부상 불가.
    "Ag": ComponentKinetics("Ag", 0.55, 1.20, 0.33, 0.12, entrainment_factor=0.55),
    # 금속 Cu (리본): 황화 후 부상성 양호, 대부분 속부선.
    "Cu": ComponentKinetics("Cu", 0.75, 1.60, 0.20, 0.20, entrainment_factor=0.50),
    # 땜납(Sn/Pb) 피복 리본 파편.
    "SnPb": ComponentKinetics("SnPb", 0.65, 1.40, 0.25, 0.15, entrainment_factor=0.50),
    # Al (BSF/프레임 잔재): 부동태 산화막으로 대부분 비부선.
    "Al": ComponentKinetics("Al", 0.12, 0.60, 0.18, 0.05, entrainment_factor=0.50),
    # Si: 규산소다로 억제. 혼입은 사실상 전량 수분 동반(entrainment).
    "Si": ComponentKinetics("Si", entrainment_factor=0.55),
    "Glass": ComponentKinetics("Glass", entrainment_factor=0.50),
    # 잔류 유기물(EVA/백시트 char): 본질적으로 소수성이라 거의 전량 속부선.
    # 열처리를 산화분위기로 완전히 수행하지 못하면 정광을 크게 희석한다.
    "Polymer": ComponentKinetics("Polymer", 0.85, 2.00, 0.05, 0.30, entrainment_factor=0.60),
}

#: 성분별 비중 — 회로 계산에서 흐름의 체적유량을 구할 때 쓴다.
SPECIFIC_GRAVITY = {c.name: c.specific_gravity for c in CELL_FRACTION}

# --------------------------------------------------------------------------
# 약제 계통
# --------------------------------------------------------------------------
#: 투입량은 모두 **신급광 건조 고체 1 t 당** 유효성분 g 수다 (순환류 제외).
#: 포수제·기포제는 러퍼와 스캐빈저에 분할 투입한다 — 스캐빈저 급광은 이미
#: 속부선 분획이 빠져나간 지연부선 위주라, 신선한 포수제를 다시 걸어줘야
#: 부상 속도가 회복된다 (SCAVENGER_COLLECTOR_BOOST 의 근거).
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
        name="Sodium silicate (클리너 보강)",
        role="분산/억제제",
        dose_g_per_t=100.0,
        solution_strength=0.10,
        solution_sg=1.08,
        addition_point="FC-103 급광박스",
        note="클리너에서 Si 재부상을 막는 소량 보강 투입.",
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
        name="PAX (potassium amyl xanthate) — 러퍼",
        role="포수제 (주)",
        dose_g_per_t=85.0,
        solution_strength=0.02,
        solution_sg=1.00,
        addition_point="CT-2",
        note="2% 수용액으로 매일 신규 조제 (48h 이내 사용). pH 9 이상 유지.",
    ),
    Reagent(
        name="PAX — 스캐빈저 분할 투입",
        role="포수제 (주)",
        dose_g_per_t=35.0,
        solution_strength=0.02,
        solution_sg=1.00,
        addition_point="FC-102 급광박스",
        note="지연부선 분획의 부상 속도 회복용. 러퍼에 한꺼번에 넣으면 "
        "포수제 과잉으로 맥석까지 부상해 러퍼 정광 품위가 무너진다.",
    ),
    Reagent(
        name="Dithiophosphinate (Aerophine 3418A 상당) — 러퍼",
        role="포수제 (보조)",
        dose_g_per_t=28.0,
        solution_strength=0.01,
        solution_sg=1.01,
        addition_point="CT-2",
        note="Ag 선택성 보강. 잔티에이트 단독 대비 Ag 회수율 3~6%p 개선.",
    ),
    Reagent(
        name="Dithiophosphinate — 스캐빈저 분할 투입",
        role="포수제 (보조)",
        dose_g_per_t=12.0,
        solution_strength=0.01,
        solution_sg=1.01,
        addition_point="FC-102 급광박스",
        note="러퍼와 동일 비율로 분할. 분할 투입으로 1회 투입량이 작아져 5% 가 아닌 1% 수용액으로 조제해야 정량펌프 유량이 확보된다.",
    ),
    Reagent(
        name="MIBC — 러퍼",
        role="기포제",
        dose_g_per_t=20.0,
        solution_strength=0.01,
        solution_sg=1.00,
        addition_point="FC-101 급광박스",
        note="취성 거품 형성 — 미립 금속 정광에 적합. 과잉 시 맥석 혼입 증가. "
        "원액 소요량이 정량펌프 최소 토출량보다 작으므로 1% 수용액으로 "
        "희석 투입한다 (20 degC 수용해도 약 17 g/L).",
    ),
    Reagent(
        name="MIBC — 스캐빈저",
        role="기포제",
        dose_g_per_t=10.0,
        solution_strength=0.01,
        solution_sg=1.00,
        addition_point="FC-102 급광박스",
        note="스캐빈저는 얕은 거품층·고급기 운전이라 기포제를 별도로 건다. "
        "클리너에는 기포제를 넣지 않는다 (거품이 질겨지면 배수가 안 됨).",
    ),
)

# --------------------------------------------------------------------------
# 조건조
# --------------------------------------------------------------------------
CONDITIONER_STAGES = (
    ("CT-1", "pH 조정 + 분산/억제제 + 황화제", 5.0),
    ("CT-2", "포수제 (PAX + dithiophosphinate)", 3.0),
)


# --------------------------------------------------------------------------
# 회로 구성 (러퍼 - 스캐빈저 - 클리너)
# --------------------------------------------------------------------------
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


#: 러퍼 FC-101 — Phase 1 에서 확정한 셀을 그대로 쓴다.
ROUGHER_CELL = _cell(CELL_WIDTH_M, CELL_SHELL_HEIGHT_M, FROTH_DEPTH_M, GAS_HOLDUP)

#: 스캐빈저 FC-102 — 러퍼와 **동일 동체**. 예비품·구동부를 공용화하기 위함이며,
#: 계산상 필요 체적(0.289 m3)이 러퍼(0.281 m3)와 거의 같아 자연스럽다.
#: 다만 회수 위주 duty 이므로 거품층을 얕게(50 mm) 가져가고 급기를 늘린다.
SCAVENGER_CELL = _cell(CELL_WIDTH_M, CELL_SHELL_HEIGHT_M, 0.050, GAS_HOLDUP)

#: 클리너 FC-103 — 품위 위주 duty. 거품층을 깊게(150 mm) 가져가 배수(drainage)를
#: 유도하고, 급기와 기공률을 낮춘다. 폭 450 mm 는 체류시간이 아니라
#: **제작·운전상 실용 하한**(거품 안정성, 런더 접근)으로 결정했다.
CLEANER_CELL = _cell(0.45, 0.62, 0.150, 0.12)

#: 셀별 설계 표면기체속도 Jg (cm/s) 와 제어 범위.
CELL_JG_CM_S = {"FC-101": 1.0, "FC-102": 1.2, "FC-103": 0.6}
CELL_JG_RANGE_CM_S = {"FC-101": (0.6, 1.4), "FC-102": (0.8, 1.6), "FC-103": (0.3, 0.9)}

#: 셀별 로터 주속 (m/s). 클리너는 기포 이탈(detachment)을 줄이려 낮게 운전한다.
CELL_TIP_SPEED_M_S = {"FC-101": 5.5, "FC-102": 5.5, "FC-103": 4.5}

#: 급광 물 중 정광(거품)으로 넘어가는 비율. entrainment 를 일으키는 것은 이 물뿐이다.
CELL_WATER_RECOVERY = {"FC-101": 0.12, "FC-102": 0.10, "FC-103": 0.06}

#: 러퍼 급광 목표 고체 농도 (순환류 포함).
ROUGHER_FEED_SOLIDS = 0.25

#: 클리너 급광 희석 목표 — 러퍼 정광은 32 % 수준으로 진해서 그대로 넣으면
#: 거품이 무거워지고 entrainment 가 커진다.
CLEANER_FEED_SOLIDS = 0.18

#: 클리너 거품 세척수 (m3/h). 거품층 위에서 아래로 흘러 동반 맥석을 씻어낸다.
CLEANER_WASH_WATER_M3H = 0.25

#: 스캐빈저 포수제 분할 투입 효과 — 지연부선 분획 속도상수에 곱하는 계수.
#: 배치 부선시험(단계별 약제 추가)으로 확정해야 하는 가정값이다.
SCAVENGER_COLLECTOR_BOOST = 1.4

#: (태그, 역할, 셀 형상) — 회로 구성 순서대로.
CIRCUIT_CELLS = (
    ("FC-101", "러퍼 (Rougher)", ROUGHER_CELL),
    ("FC-102", "스캐빈저 (Scavenger)", SCAVENGER_CELL),
    ("FC-103", "클리너 (Cleaner)", CLEANER_CELL),
)
