"""천장크레인 CRN-901 — 설치·정비 인양의 단일 출처.

발주처가 **천장고 12,000 mm** 를 확인해 주고 **5 t** 로 정해 주셨다. 그러면
남는 것은 "5 t 가 맞는가"와 "12,000 안에서 후크가 어디까지 올라가는가" 다.

**후크 높이는 천장고가 아니다.** 크레인 자신의 두께를 빼고 남는 값이다 —
이 구분을 안 하면 12 m 천장을 보고 12 m 를 들 수 있다고 적게 된다.

    천장 (건물 보 하면)                 12,000
     − 크레인 최상단과 보 사이 여유        300
     − 거더 + 트롤리 (레일 상면 위)        950
    ────────────────────────────────────────
    = 주행레일 상면 (TOR)               10,750
     − C 치수 (레일 상면 → 후크 최상단)  1,050
    ────────────────────────────────────────
    = 후크 최고 높이                     9,700

인양에 필요한 높이는 물건 높이만이 아니다. 슬링과 후크 블록이 물건 **위**로
차지하는 높이를 더해야 하고, 바닥에서 띄울 높이도 있어야 한다. 그래서
`required_hook_mm()` 이 넷을 다 더한다.

**들어 올린 채로 설치된 설비 위를 넘지 않는다**는 것이 이 크레인의 전제다.
넘으려면 최고 고정점(5,150) + 통과여유 + 물건 + 슬링 + 후크블록이 필요해
12,450 이 되어 12 m 천장에 안 들어간다. 반입은 통로(Y 7,100–8,300)를 따라
제자리 옆까지 가서 내리고, **하류(GRM)부터 세워 상류로 온다** — 그러면 넘을
일이 생기지 않는다. 크레인 사양이 아니라 시공 순서로 푸는 문제다.

주행거더를 받치는 것은 **건물 철골**이다. 이 플랜트의 공급 범위가 아니라
`mounting.UNSUPPORTED_BY_DESIGN` 에 근거와 함께 넣었다. 대신 건물 쪽에
요구하는 값(TOR·스팬·주행 반력)을 여기서 내보낸다 — 인터페이스는 숫자로
넘겨야 한다.

중량은 **개략 산출한 계획값**이다. 단면과 재질에서 나왔고 벤더 GA 가 오면
그 값으로 바뀐다. 그래도 지금 필요한 판단 — 5 t 가 최중량 단품을 얼마나
여유 있게 받느냐 — 은 이 정밀도로 충분하다.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── 발주처 확인값 ────────────────────────────────────────────────────────
#: 설치 현장 천장고 (mm) — 건물 보 하면까지. 발주처 확인.
CEILING_MM = 12_000

#: 크레인 용량 (t) — 발주처 지정.
CAPACITY_T = 5.0


# ── 높이 계통 ────────────────────────────────────────────────────────────
#: 크레인 최상단과 건물 보 하면 사이 여유 (mm). 지붕 처짐·시공 오차를 받는다.
ROOF_CLEARANCE_MM = 300

#: 주행레일 상면 위로 크레인이 차지하는 높이 (mm) — 거더 + 트롤리.
#: 5 t · 스팬 8.8 m 단일거더 기준 계획값.
CRANE_ABOVE_RAIL_MM = 950

#: C 치수 — 주행레일 상면에서 후크 최상단까지 (mm). 호이스트 사양값.
HOOK_APPROACH_MM = 1_050

#: 인양 부속이 물건 위로 차지하는 높이 (mm).
SLING_MM = 2_000          # 2점 슬링 60°, 폭 2.9 m 기준
HOOK_BLOCK_MM = 500
GROUND_LIFT_MM = 200      # 바닥에서 띄우는 높이


# ── 평면 계통 ────────────────────────────────────────────────────────────
#: 장비 밴드 폭 (mm) — layout.MACHINE_BAND_Y_MM 와 같아야 한다.
MACHINE_BAND_MM = 7_100

#: 트롤리 끝단 접근 여유 (mm). 레일 중심에서 후크가 이만큼은 못 간다.
TROLLEY_APPROACH_MM = 600

#: 주행 끝단 접근 여유 (mm).
BRIDGE_APPROACH_MM = 700

#: 주행거더 스팬 (mm). 장비 밴드를 후크가 끝까지 덮어야 한다.
SPAN_MM = 8_800

#: 주행거더 길이 (mm). 플랜트 전장을 덮는다.
RUNWAY_MM = 60_800


# ── 인양 대상 ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Lift:
    """크레인이 실제로 드는 것 하나."""

    name: str
    station: str
    mass_kg: int          # 개략 산출 계획값
    height_mm: int        # 인양물 자체 높이
    basis: str            # 어떻게 나온 값인가


#: 설치·정비에서 크레인이 드는 것. 중량은 단면·재질에서 개략 산출한
#: **계획값**이며 벤더 GA 가 오면 바뀐다. 최중량이 용량을 정한다.
LIFTS: tuple[Lift, ...] = (
    Lift("BFC 반전 카세트 (Bay 1식)", "bfc", 1_980, 4_500,
         "엔드링 2 × ⌀180 t10 파이프 237 kg · 포탈기둥 4 × 180×240 t8 · "
         "크로스빔 2 · 조 2 · 서보·감속기 2 · 베어링블록 2"),
    Lift("GRM-401 5단 단열랙 M1-101", "grm", 1_700, 3_000,
         "프레임 800 · 데크 5 × 80 · IR 램프 60등과 반사판 300 · 단열재 200"),
    Lift("AFR-101 셀 베이스 프레임", "afr", 1_290, 450,
         "180×180 t8 각형강관 11.4 m × 2본 985 kg + 횡부재 305 kg"),
    Lift("AFR CL-221 클램프 포탈 1조", "afr", 700, 2_130,
         "150×150 t9 기둥 4본 × 2.13 m (39.8 kg/m) · 크로스헤드 2 · 타이빔 2"),
    Lift("VG-101 독립 방진 비전보 조립체", "afu", 620, 5_150,
         "보 3.8 m + 독립 기둥 2본 × 4.95 m · 방진 마운트"),
    Lift("HPU-601 유압 파워유닛", "afr", 450, 1_500,
         "펌프·전동기 120 · 유조 200 L 오일 174 · 강판 유조 80 · 부속 76"),
    Lift("MDB-101 주 분전반", "afr", 400, 2_100,
         "큐비클 강판 · ACB 400 AF · 역률개선 35 kVar"),
    Lift("VAC-101 진공 스키드", "afu", 320, 1_620,
         "리시버 2기 × 90 · 무급유 펌프 2대 × 55 · 스키드 프레임 30"),
)


# ── 파생값 ───────────────────────────────────────────────────────────────
def capacity_kg() -> int:
    return int(CAPACITY_T * 1000)


def rail_top_mm() -> int:
    """주행레일 상면 (TOR). 천장에서 크레인 자신의 두께를 뺀 값이다."""
    return CEILING_MM - ROOF_CLEARANCE_MM - CRANE_ABOVE_RAIL_MM


def hook_height_mm() -> int:
    """후크가 올라갈 수 있는 최고 높이. **천장고가 아니다.**"""
    return rail_top_mm() - HOOK_APPROACH_MM


def required_hook_mm(lift: Lift) -> int:
    """이 물건을 들려면 후크가 어디까지 올라가야 하는가.

    물건 높이만 보면 슬링과 후크 블록을 빠뜨린다 — 둘 다 물건 **위**에
    있으므로 후크는 그만큼 더 올라가야 한다.
    """
    return lift.height_mm + SLING_MM + HOOK_BLOCK_MM + GROUND_LIFT_MM


def governing_lift() -> Lift:
    """용량을 정하는 인양 — 가장 무거운 것."""
    return max(LIFTS, key=lambda item: item.mass_kg)


def tallest_lift() -> Lift:
    """후크 높이를 정하는 인양 — 가장 높이 올려야 하는 것."""
    return max(LIFTS, key=required_hook_mm)


def capacity_margin() -> float:
    """최중량 단품 대비 용량 배수. 벤더 GA 미확정분을 받는 여유다."""
    return round(capacity_kg() / governing_lift().mass_kg, 2)


def hook_margin_mm() -> int:
    """가장 높이 드는 인양에 대해 남는 후크 높이."""
    return hook_height_mm() - required_hook_mm(tallest_lift())


def carry_over_hook_mm(tallest_fixed_mm: int, pass_clearance_mm: int = 300) -> int:
    """설치된 설비 **위로** 넘길 때 필요한 후크 높이.

    이 값이 `hook_height_mm()` 를 넘으면 넘길 수 없다 — 그래서 반입 동선을
    통로로 잡고 하류부터 세운다.
    """
    return (tallest_fixed_mm + pass_clearance_mm + governing_lift().height_mm
            + SLING_MM + HOOK_BLOCK_MM)


def hook_reach_z_mm() -> int:
    """후크가 라인 중심에서 좌우로 닿는 거리. 장비 밴드를 덮어야 한다."""
    return SPAN_MM // 2 - TROLLEY_APPROACH_MM


def covers_machine_band(span_mm: int | None = None) -> bool:
    """후크가 장비 밴드 양끝까지 닿는가.

    인자를 열어 둔 것은, 지금 스팬이 이미 맞아서 검사 코드가 죽어도 아무도
    모르는 일을 막기 위해서다.
    """
    span = SPAN_MM if span_mm is None else span_mm
    return span // 2 - TROLLEY_APPROACH_MM >= MACHINE_BAND_MM // 2


def fits_under_ceiling(ceiling_mm: int | None = None) -> bool:
    """크레인 최상단이 천장 밑에 여유를 두고 들어가는가."""
    c = CEILING_MM if ceiling_mm is None else ceiling_mm
    return rail_top_mm() + CRANE_ABOVE_RAIL_MM + ROOF_CLEARANCE_MM <= c


def clears_plant(tallest_fixed_mm: int) -> int:
    """거더 하면과 플랜트 최고 고정점 사이 여유."""
    return rail_top_mm() - tallest_fixed_mm


# ── 전기 ─────────────────────────────────────────────────────────────────
#: 구동부 설치 전력 (kW). 5 t · 양정 9.7 m · 승강 5.0/0.8 m/min 기준 계획값.
HOIST_KW = 5.5
TROLLEY_KW = 0.4
BRIDGE_KW = 0.4
BRIDGE_DRIVES = 2

#: 수용률. **설치·정비 전용**이라 생산 중에는 돌지 않는다 — 설비 위에서
#: 인양하는 것 자체가 안전상 금지이므로 공정 부하와 동시에 걸리지 않는다.
DIVERSITY = 0.20


def installed_kw() -> float:
    return round(HOIST_KW + TROLLEY_KW + BRIDGE_KW * BRIDGE_DRIVES, 1)


def demand_kw() -> float:
    return round(installed_kw() * DIVERSITY, 2)


def summary() -> dict[str, object]:
    """도면 표제란·검토서에 그대로 넣는 값."""
    gov, tall = governing_lift(), tallest_lift()
    return {
        "capacityT": CAPACITY_T,
        "ceilingMm": CEILING_MM,
        "railTopMm": rail_top_mm(),
        "hookHeightMm": hook_height_mm(),
        "spanMm": SPAN_MM,
        "runwayMm": RUNWAY_MM,
        "hookReachMm": hook_reach_z_mm(),
        "governing": gov.name,
        "governingKg": gov.mass_kg,
        "capacityMargin": capacity_margin(),
        "tallest": tall.name,
        "requiredHookMm": required_hook_mm(tall),
        "hookMarginMm": hook_margin_mm(),
        "installedKw": installed_kw(),
        "demandKw": demand_kw(),
    }
