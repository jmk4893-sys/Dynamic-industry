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
12,970 이 되어 12 m 천장에 안 들어간다.

그래서 **하류(GRM)부터 세워 상류(AFU)로 온다** — 공정 흐름의 반대다.
이유는 반입 동선이 곧 **아직 안 세운 장비 밴드**이기 때문이다.

REV.28 에서 여기에 "반입은 통로(Y 7,100–8,300)를 따라" 라고 적었는데
**틀렸다.** 통로는 공칭 1,200 이고 MDB·엣지 캐비닛이 깊이 300 을 먹어 유효
900 이다. 최중량 인양인 BFC 반전 카세트는 폭 **2,900** 이라 900 짜리 통로를
지날 수 없다. 통로는 사람이 다니는 길이지 반입 동선이 아니다.

실제 반입 동선은 폭 7,100 의 **장비 밴드 그 자체**이고, 그것이 순서를 정하는
이유다 — 세우는 순간 동선이 사라지는 길이라 **먼 쪽부터 소비해야** 한다.
문(지게차 진입측 = AFU 상류)에서 가까운 것을 먼저 세우면 그 뒤로 아무것도
못 들어간다. 크레인 사양이 아니라 시공 순서로 푸는 문제다.

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

from . import layout

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

#: 슬링 각 (수평에서, °). 60° 보다 눕히면 다리 장력이 급히 커진다 —
#: 인양 규약의 하한이라 여기가 기하의 기준이다.
SLING_ANGLE_DEG = 60.0

#: 슬링 폭 (mm) — 목록에서 가장 넓은 것이 높이를 정한다. BFC 반전 카세트의
#: 폭 2,900 이다(길이 5,100 방향은 스프레더 빔으로 받아 높이를 안 키운다).
SLING_SPREAD_MM = 2_900

#: 후크 블록 높이 (mm). 5 t 정격 블록이라 인양물 중량과 무관하게 같다.
HOOK_BLOCK_MM = 500

#: 바닥에서 띄우는 높이 (mm).
GROUND_LIFT_MM = 200

#: 인양 부속 자중 (kg) — 4점 와이어로프 슬링 · 샤클 · 스프레더 빔.
#: **후크에 걸리는 것은 물건만이 아니다.** 정격 5 t 은 이 자중까지 받는
#: 값이라, 실을 수 있는 물건은 그만큼 줄어든다. 개략 계획값.
LIFTING_GEAR_KG = 150


def sling_height_mm(spread_mm: int | None = None,
                    angle_deg: float | None = None) -> int:
    """인양 부속 중 **슬링**이 물건 위로 차지하는 높이 (mm).

    상수로 적어 두면 각도와 어긋나도 아무도 모른다 — REV.28 까지 "2점 슬링
    60° · 폭 2.9 m 기준" 이라 적어 놓고 값은 2,000 이었는데, 그 값이 되려면
    각이 54° 여야 한다. 눕은 쪽이라 다리 장력을 과소평가하는 방향이었다.
    이제 폭과 각에서 직접 낸다 (10 mm 단위 올림).
    """
    import math
    spread = SLING_SPREAD_MM if spread_mm is None else spread_mm
    angle = SLING_ANGLE_DEG if angle_deg is None else angle_deg
    height = spread / 2 * math.tan(math.radians(angle))
    return int(-(-height // 10) * 10)


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


# ── 반입 동선 ────────────────────────────────────────────────────────────
#: 반입 진입측 존. **발주처 확인 — 출입구는 투입방향(상류 AFU)이고 건축이
#: 이미 그렇게 설계돼 있다.** 지게차 진입측과 같은 곳이라
#: `mounting.MOUNTING_OF["afu"]` 가 앵커를 여유 있게 잡는 근거와도 맞는다.
#:
#: 확인 전에는 그 앵커 근거에서 미루어 잡은 값이었다. 추정이 맞았지만
#: 추정이었다는 사실이 중요하다 — 설치 순서 전체가 여기서 나오므로,
#: 문이 반대쪽이면 순서도 통째로 뒤집힌다(`install_order` 가 그렇게 만든다).
ENTRY_ZONE = "afu"


def install_order(entry_zone: str | None = None) -> tuple[str, ...]:
    """설치 순서 — 공정 흐름의 **반대**.

    반입 동선이 아직 안 세운 장비 밴드라서, 세우는 순간 그만큼 길이 사라진다.
    문에서 먼 쪽부터 세워 문 쪽으로 물러나야 매 단계 동선이 남는다.
    """
    keys = [zone.key for zone in layout.build_zones()]
    entry = ENTRY_ZONE if entry_zone is None else entry_zone
    if keys.index(entry) * 2 < len(keys):
        return tuple(reversed(keys))
    return tuple(keys)


def haul_width_mm() -> int:
    """반입 동선의 폭 (mm) — 아직 비어 있는 장비 밴드."""
    return layout.MACHINE_BAND_Y_MM


def widest_module_mm() -> int:
    """반입 동선이 통과시켜야 하는 최대 폭 (mm).

    최중량 인양이 속한 셀의 폭이다. 이 값이 순서 규칙의 근거이므로
    셀 외형에서 파생시킨다 — 손으로 적으면 셀이 넓어져도 안 따라온다.
    """
    return layout.STATIONS[governing_lift().station].envelope[1]


def entry_opening_min_mm() -> tuple[int, int]:
    """반입 개구가 최소한 통과시켜야 하는 (폭, 높이) mm.

    **개구 치수를 정하는 값이 아니라 하한이다.** 실제 치수는 분할 반입
    계획에 달렸다 — 무엇이 통짜로 오고 무엇이 안에서 조립되는지는 벤더
    몫이라 여기서 정하지 않는다. "통짜로 온다면 이만큼은 필요하다" 만
    내보내고, 운반대 높이·리깅 여유는 시공사가 얹는다.
    """
    return widest_module_mm(), max(lift.height_mm for lift in LIFTS)


def aisle_can_haul(aisle_clear_mm: int) -> bool:
    """통로가 반입 동선이 될 수 있는가.

    유효폭을 인자로 받는 것은 순환 참조를 피하기 위해서다 —
    `wiring.aisle_clear_width_mm()` 가 그 값을 만들고 wiring 이 이 모듈을 읽는다.
    """
    return aisle_clear_mm >= widest_module_mm()


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
    Lift("BFC 반전 카세트 (Bay 1식)", "bfc", 2_500, 4_500,
         "**발주처 확인 — 2,500 kg 이상.** 단면·재질에서 낸 개략값은 1,980 "
         "이었다(엔드링 2 × ⌀180 t10 파이프 237 kg · 포탈기둥 4 × 180×240 t8 · "
         "크로스빔 2 · 조 2 · 서보·감속기 2 · 베어링블록 2). 26 % 낮게 잡았던 "
         "셈이라 확인값을 하한으로 쓴다 — 벤더 GA 가 오면 그 값으로 바꾼다"),
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
    return (lift.height_mm + sling_height_mm() + HOOK_BLOCK_MM
            + GROUND_LIFT_MM)


def hook_load_kg(lift: Lift) -> int:
    """후크에 실제로 걸리는 하중 (kg) — 물건 + 인양 부속."""
    return lift.mass_kg + LIFTING_GEAR_KG


def max_lift_kg() -> int:
    """이 크레인으로 들 수 있는 **물건**의 상한 (kg).

    정격에서 인양 부속 자중을 뺀 값이다. "2,500 kg 이상" 처럼 위가 열린
    확인값을 받았을 때, 어디까지 올라가면 5 t 이 안 되는지가 이 숫자다.
    """
    return capacity_kg() - LIFTING_GEAR_KG


def governing_lift() -> Lift:
    """용량을 정하는 인양 — 가장 무거운 것."""
    return max(LIFTS, key=lambda item: item.mass_kg)


def tallest_lift() -> Lift:
    """후크 높이를 정하는 인양 — 가장 높이 올려야 하는 것."""
    return max(LIFTS, key=required_hook_mm)


def capacity_margin() -> float:
    """최중량 **후크 하중** 대비 용량 배수.

    재는 자를 물건 중량이 아니라 후크 하중으로 잡는다 — 정격이 받는 것은
    물건이 아니라 후크에 걸린 전부다. 이 구분이 없으면 부속 자중만큼
    여유를 실제보다 크게 적게 된다.
    """
    return round(capacity_kg() / hook_load_kg(governing_lift()), 2)


def fits_capacity(mass_kg: int | None = None) -> bool:
    """이 중량이 5 t 안에 드는가. 인자를 열어 둔 것은 경계를 시험하기 위해서다."""
    mass = governing_lift().mass_kg if mass_kg is None else mass_kg
    return mass + LIFTING_GEAR_KG <= capacity_kg()


def hook_margin_mm() -> int:
    """가장 높이 드는 인양에 대해 남는 후크 높이."""
    return hook_height_mm() - required_hook_mm(tallest_lift())


def carry_over_hook_mm(tallest_fixed_mm: int, pass_clearance_mm: int = 300) -> int:
    """설치된 설비 **위로** 넘길 때 필요한 후크 높이.

    이 값이 `hook_height_mm()` 를 넘으면 넘길 수 없다 — 그래서 반입 동선을
    통로로 잡고 하류부터 세운다.
    """
    return (tallest_fixed_mm + pass_clearance_mm + governing_lift().height_mm
            + sling_height_mm() + HOOK_BLOCK_MM)


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
        "hookLoadKg": hook_load_kg(gov),
        "maxLiftKg": max_lift_kg(),
        "capacityMargin": capacity_margin(),
        "tallest": tall.name,
        "requiredHookMm": required_hook_mm(tall),
        "hookMarginMm": hook_margin_mm(),
        "installOrder": list(install_order()),
        "entryZone": ENTRY_ZONE,
        "haulWidthMm": haul_width_mm(),
        "widestModuleMm": widest_module_mm(),
        "entryOpeningMinMm": list(entry_opening_min_mm()),
        "installedKw": installed_kw(),
        "demandKw": demand_kw(),
    }
