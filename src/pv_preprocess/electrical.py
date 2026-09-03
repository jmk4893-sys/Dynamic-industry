"""전처리 플랜트 전기 인입 — 부하 집계와 인입 규격 산정.

설계도의 전기 인입도(PV-PLANT-EL-1005)가 이 계산과 어긋나지 않는지
`tests/test_pv_preprocess.py` 가 검사한다.

부하값의 출처는 두 가지다.

* **명시값** — 셀 GA 시트의 유틸리티 란에 이미 적혀 있던 값
  (JBR-201 약 6.5 kW, AFR HPU-601 7.5 kW, 집진 1,000 + 350 m³/h).
* **계획값** — 그 외 셀은 구성 기기에서 잡은 계획 부하다. OEM 하중도·전동기 명판이
  확정되면 바꿔야 하며, 그때 이 파일만 고치면 도면과 테스트가 같이 따라온다.

**수전 방식은 부하와 부지 여건에서 파생한다.** 세 번 바뀌었고, 세 번 다
숫자가 먼저 바뀐 결과다.

* REV.22 — 계약전력 67.9 kW. 저압 3Φ 4W 380/220 V 직결이 맞았다.
* REV.23 — 유리제거셀 IR 뱅크 175 kW 가 들어와 계약전력 268.2 kW.
  한전 저압 공급 상한 100 kW 를 넘어 22.9 kV 자체 수전 + 수전변압기.
* REV.24 — **부지에 1,200 kW 인입이 이미 있다**(발주처 확인). 그러면 이
  플랜트는 수전설비를 세우는 주체가 아니라 그 계통에 물리는 **부하 하나**다
  (계약전력 기준 22.4 %). 세울 큐비클도 수전실도 없어진다.

REV.23 의 판정 자체는 틀리지 않았다 — 그 설비를 **우리가 새로 세울 필요가
없어졌을 뿐**이라, 부지 인입이 없어지거나 모자라면 그대로 되돌아간다.
그래서 고압 수전 계산과 큐비클 표는 지우지 않고 남겨 둔다.

전압·변압기·차단기·케이블·전기실 면적이 전부 이 판정에서 따라 나오므로,
부하나 부지 여건이 다시 바뀌면 여기만 고치면 도면과 테스트가 같이 따라온다.

역률 0.90 은 서보·인버터에 라인리액터를 다는 전제이며, 고조파 실측 전에는
확정값이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 저압 배전 전압 (V, 선간). 변압기 2차이자 플랜트 내부 배전 전압이다.
SUPPLY_VOLTAGE_V = 380

# ── 수전 방식 ────────────────────────────────────────────────────────────
# REV.24: **부지에 1,200 kW 인입이 이미 있다**(발주처 확인). 그러면 이 플랜트는
# 자기 수전설비를 세우는 것이 아니라 **기존 계통에서 분기하는 부하 하나**다.
# 한전 협의·MOF·VCB·고압 인입 케이블·수전실이 전부 부지 쪽에 이미 있다.
#
# REV.23 에서 자체 수전을 설계했던 근거(계약전력 268.2 kW ≥ 저압 상한 100 kW)는
# 그대로 유효하다 — 다만 그 수전설비를 **우리가 새로 세울 필요가 없을 뿐**이다.
# 부지 인입이 없어지거나 용량이 모자라면 그 설계로 되돌아가야 하므로 남겨 둔다.

#: 부지에 이미 들어와 있는 인입 용량 (kW). 발주처 확인값.
SITE_SERVICE_KW = 1200.0

#: 한전 저압 공급 상한 (kW, 계약전력). 자체 수전을 세울 때만 쓰인다.
LOW_VOLTAGE_LIMIT_KW = 100.0

#: 고압 수전 전압 (V, 선간) — 22.9 kV 배전 계통.
HV_SUPPLY_VOLTAGE_V = 22_900

#: 표준 변압기 용량 (kVA).
TRANSFORMER_RATINGS_KVA = (100, 150, 200, 300, 500, 750, 1000)

#: 변압기 목표 부하율 — 수요 피상전력이 이 비율 안에 들도록 용량을 고른다.
TRANSFORMER_LOAD_FACTOR = 0.80

#: 한전 기준역률과 개선 목표역률. 기준 미달은 할증, 초과는 감액이다.
BASE_POWER_FACTOR = 0.90
TARGET_POWER_FACTOR = 0.95

#: 표준 콘덴서 뱅크 용량 (kVar).
CAPACITOR_STEPS_KVAR = (10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100)

#: 저압 케이블 허용전류 (mm² → A). 3심 XLPE 동도체·트레이 포설 기준.
LV_CABLE_AMPACITY_A: dict[int, int] = {
    35: 133, 50: 160, 70: 204, 95: 248, 120: 287,
    150: 331, 185: 380, 240: 450, 300: 514,
}

#: 고압 인입 케이블 최소 규격 (mm²) — 전류가 아니라 기계적 강도로 정해진다.
HV_CABLE_MIN_MM2 = 60

#: 저압 케이블 임피던스 (mm² → (R, X) Ω/km). R 은 90 °C 도체 기준, X 는 3심 XLPE.
#: 분기 거리를 정하는 것은 허용전류가 아니라 **전압강하**라서 필요하다.
LV_CABLE_IMPEDANCE: dict[int, tuple[float, float]] = {
    35: (0.6680, 0.0850), 50: (0.4930, 0.0830), 70: (0.3420, 0.0820),
    95: (0.2470, 0.0810), 120: (0.1960, 0.0800), 150: (0.1590, 0.0800),
    185: (0.1280, 0.0790), 240: (0.0961, 0.0790), 300: (0.0777, 0.0780),
}

#: 분기 회로 허용 전압강하 (%). 간선 3 % 는 내선규정 관례다.
FEEDER_VOLTAGE_DROP_PCT = 3.0

#: **분기 전압** — 기존 부지 계통의 어느 지점에서 따느냐.
#: True 면 부지 저압 배전반(380 V)에서 바로 딴다: 변압기도 수전실도 없다.
#: 다만 저압은 거리가 전압강하로 묶이므로 `lv_tap_max_length_m()` (240 mm² 기준
#: 162 m) 안이어야 성립한다. 그보다 멀면 False 로 두어 22.9 kV 로 따고
#: 플랜트 옆에 국소 변압기(unit substation)를 세운다.
#: **부지 배전반까지의 실거리가 확정되면 이 한 줄만 고치면 된다.**
TAP_AT_LOW_VOLTAGE = True

#: 계획 역률. 라인리액터 적용 전제 — 고조파 실측으로 확정한다.
POWER_FACTOR = 0.90

#: 주 차단기 표준 트립 정격 (A) 과 표준 프레임 (A).
#: REV.23 에서 유리제거셀 IR 뱅크 175 kW 가 들어오며 100 AT 로는 못 받는다 —
#: 사다리를 실제 배전 표준까지 늘리고, 프레임도 트립에서 파생시킨다.
BREAKER_TRIPS_A = (63, 80, 100, 125, 160, 200, 250, 320, 400, 500, 630)
BREAKER_FRAMES_A = (100, 125, 225, 400, 630, 800)

#: 계약 전력 여유율. 증설·동시 기동 여유를 본다.
CONTRACT_MARGIN = 1.35


@dataclass(frozen=True)
class Feeder:
    """주 분전반에서 나가는 피더 하나."""

    tag: str
    panel: str
    served: str
    installed_kw: float
    diversity: float
    breaker_at: int
    cable: str
    source: str

    @property
    def demand_kw(self) -> float:
        return self.installed_kw * self.diversity


#: 주 분전반(MDB-101) 피더. 순서가 인입도의 위→아래 순서다.
FEEDERS: tuple[Feeder, ...] = (
    Feeder("F1", "LP-AFU", "LFT-101A/B 유압 승강(HPU-101) · BFC-101A/B 반전 · CD-101 포획빔 · 투입 비전",
           12.0, 0.70, 40, "4C×10 mm² Cu", "계획"),
    Feeder("F2", "LP-RB", "RB-101 로봇 제어반 · EOAT 진공 · PT-101 정렬정반",
           9.0, 0.60, 32, "4C×6 mm² Cu", "계획"),
    Feeder("F3", "LP-JBR", "JBR-201 3헤드·X/Y 브리지·비전",
           6.5, 0.80, 20, "4C×4 mm² Cu", "GA 명시"),
    Feeder("F4", "LP-AFR", "HPU-601 7.5 kW · 장축 LM 캐리지 4축",
           11.5, 0.70, 32, "4C×10 mm² Cu", "GA 명시(HPU)"),
    Feeder("F5", "LP-GLASS", "SG-301 양측 연마 · CV-102 이송 · GI-301/302 통합 광학검사",
           9.0, 0.70, 32, "4C×6 mm² Cu", "계획"),
    Feeder("F6", "LP-GBR", "GBR-301 수평셔틀 서보 · 도킹 도크",
           4.0, 0.50, 16, "4C×4 mm² Cu", "계획"),
    Feeder("F7", "LP-DX", "DX-601 집진 1,000 m³/h · JBR 국소집진 350 m³/h",
           11.0, 0.90, 32, "4C×6 mm² Cu", "GA 명시(풍량)"),
    Feeder("F8", "LP-CTRL", "안전 PLC · 비전 LAN · 제어반 UPS · 조명",
           5.0, 1.00, 20, "4C×4 mm² Cu", "계획"),
    # ── REV.23 유리제거셀(GRM-401) 통합 ──────────────────────────────────
    # IR 뱅크가 이 플랜트에서 가장 큰 부하다. 60등 × 2.92 kW = 175 kW 로 종전
    # 플랜트 설치 전력 68 kW 의 2.6 배다. 한 피더에 몰면 차단기가 주차단기와
    # 맞먹으므로 앱의 램프라인 구성대로 3 라인씩 두 뱅크로 나눈다.
    # 수용률 0.75 는 JIT 순차가열 전제다 — C1 200 °C … C5 160 °C 로 단마다
    # 온도가 다르므로 60등이 동시에 만출력으로 물리지 않는다. **계획값**이라
    # 시운전 전류 실측으로 확정해야 하고, 1.0 이면 수요가 43.75 kW 늘어난다.
    Feeder("F9", "LP-GRM-IRA", "GRM-401 IR 뱅크 A (라인 1–3 · 30등 × 2.92 kW)",
           87.5, 0.75, 200, "4C×70 mm² Cu", "계획(순차가열 수용률)"),
    Feeder("F10", "LP-GRM-IRB", "GRM-401 IR 뱅크 B (라인 4–6 · 30등 × 2.92 kW)",
           87.5, 0.75, 200, "4C×70 mm² Cu", "계획(순차가열 수용률)"),
    Feeder("F11", "LP-GRM-MEC",
           "LI-101 승강 2축 · TS-101 포크 · EX-101/RT-101 · TDM-201 X/Z · WR-101 · GR-201/DS-301",
           14.0, 0.65, 40, "4C×10 mm² Cu", "계획"),
    Feeder("F12", "LP-GRM-EXH", "IR 배기 · CV-301 슈레더 투입부 집진",
           9.0, 0.90, 32, "4C×6 mm² Cu", "계획"),
    # ── REV.25 스마트 팩토리 계층 ────────────────────────────────────────
    # 설치 kW 는 `smart.py` 가 랙 탑재물·계측기 목록에서 산정한 값이다.
    # 여기에는 리터럴로 적고 테스트가 둘을 대조한다 — electrical 은 어떤
    # 내부 모듈도 import 하지 않는다는 규약을 지키기 위해서다(순환 방지).
    Feeder("F13", "LP-IT", "SVR-902 랙 2면(코어망·히스토리안·MES·엣지추론 GPU·UPS) "
           "· 랙실 항온항습 · MCR-901 관제실",
           10.3, 0.85, 32, "4C×6 mm² Cu", "계획(smart.it_installed_kw)"),
    Feeder("F14", "LP-INST", "존별 엣지 캐비닛 7면 · 무선 AP 5대 · 신규 계측기 46점 "
           "· 라인스캔 조명",
           4.5, 0.90, 20, "4C×4 mm² Cu", "계획(smart.instrument_installed_kw)"),
)


def installed_kw() -> float:
    """설치(접속) 전력 합계."""
    return sum(feeder.installed_kw for feeder in FEEDERS)


def demand_kw() -> float:
    """수용률을 반영한 수요 전력."""
    return sum(feeder.demand_kw for feeder in FEEDERS)


def demand_current_a() -> float:
    """수요 전력에 대응하는 인입 선전류 (A)."""
    return demand_kw() * 1000 / (3 ** 0.5 * SUPPLY_VOLTAGE_V * POWER_FACTOR)


def contract_kva() -> float:
    """계약 전력 (kVA). 수요 피상전력에 여유율을 곱한다."""
    return demand_kw() / POWER_FACTOR * CONTRACT_MARGIN


def main_breaker_at() -> int:
    """주 차단기 트립 (A) — 수요 전류 위의 표준 정격."""
    for rating in BREAKER_TRIPS_A:
        if rating >= demand_current_a() * 1.1:
            return rating
    raise ValueError("수요 전류가 표준 정격을 넘는다 — 인입 재검토 필요")


def main_breaker_frame_a() -> int:
    """주 차단기 프레임 (A) — 트립을 담는 가장 작은 표준 프레임."""
    trip = main_breaker_at()
    for frame in BREAKER_FRAMES_A:
        if frame >= trip:
            return frame
    raise ValueError("트립이 표준 프레임을 넘는다 — 인입 재검토 필요")


def breaker_headroom_kw() -> float:
    """지금 차단기를 그대로 두고 더 실을 수 있는 수요 (kW).

    REV.25 에서 스마트 팩토리 부하 12.8 kW 가 붙으며 이 여유가 크게 줄었다.
    "아직 400 AT 안에 든다"는 말과 "여유가 얼마 남았다"는 말은 다르다 —
    다음에 부하를 붙일 때 차단기·주회로·케이블이 통째로 한 단 올라가는지를
    미리 알 수 있어야 한다.
    """
    limit_a = main_breaker_at() / 1.1
    limit_kw = limit_a * 3 ** 0.5 * SUPPLY_VOLTAGE_V * POWER_FACTOR / 1000
    return round(limit_kw - demand_kw(), 1)


#: 하위 호환 이름. 프레임은 이제 수요에서 파생한다.
MAIN_BREAKER_FRAME_A = main_breaker_frame_a()


# ── 인입 확정 (REV.23) ────────────────────────────────────────────────────
# 여기부터가 "인입을 확정한다"는 것의 실체다. 계약전력이 저압 한계를 넘으면
# 전압·변압기·차단기·케이블·설치 면적이 전부 따라 바뀐다.


def contract_kw() -> float:
    """계약 전력 (kW) — 한전 저압/고압 판정의 기준이 되는 값."""
    return round(demand_kw() * CONTRACT_MARGIN, 1)


def needs_high_voltage() -> bool:
    """**자체 수전을 세운다면** 고압이어야 하는가.

    부지 인입이 이미 있으면 이 판정은 실행되지 않는다 — 다만 부지 인입이
    없어졌을 때 무엇으로 돌아가야 하는지를 남겨 두는 값이다.
    """
    return contract_kw() >= LOW_VOLTAGE_LIMIT_KW


# ── 기존 부지 인입에서 분기 (REV.24) ──────────────────────────────────────


def site_headroom_kw() -> float:
    """부지 인입에서 이 플랜트를 빼고 남는 여유 (kW)."""
    return round(SITE_SERVICE_KW - contract_kw(), 1)


def site_utilisation_pct() -> float:
    """이 플랜트가 부지 인입에서 차지하는 비율 (%, 계약전력 기준)."""
    return round(contract_kw() / SITE_SERVICE_KW * 100.0, 1)


def worst_case_kw() -> float:
    """설치 전력이 전부 동시에 물리는 최악 (kW) — 수용률이 전부 1.0 일 때."""
    return round(installed_kw(), 1)


def fits_site_service(service_kw: float | None = None) -> bool:
    """최악의 경우에도 부지 인입 안에 드는가.

    재는 자는 계약전력이 아니라 **설치 전력**이다. 계약은 여유율을 곱한
    행정값이고, 부지 계통을 실제로 흐르는 최악은 수용률이 전부 1.0 이 될
    때의 설치 전력이다. `service_kw` 로 다른 인입 용량을 넣어 보면 이
    기준이 실제로 작동하는지 확인할 수 있다.
    """
    service = SITE_SERVICE_KW if service_kw is None else service_kw
    return worst_case_kw() <= service


def taps_existing_service(service_kw: float | None = None) -> bool:
    """자체 수전을 세우지 않고 기존 계통에서 분기하는가.

    인입이 있다고 무조건 분기하는 것이 아니다 — 최악에도 그 안에 들어야
    한다. 모자라면 이 플랜트는 자기 수전설비를 세워야 한다.
    """
    service = SITE_SERVICE_KW if service_kw is None else service_kw
    return service > 0.0 and fits_site_service(service)


def supply_method() -> str:
    if taps_existing_service():
        return (f"기존 부지 인입 {SITE_SERVICE_KW:,.0f} kW 에서 분기 "
                f"(이 플랜트 {site_utilisation_pct():g} %)")
    return "고압 22.9 kV 수전 + 수전변압기" if needs_high_voltage() else "저압 380 V 직결 인입"


def lv_tap_max_length_m(size_mm2: int | None = None,
                        drop_pct: float = FEEDER_VOLTAGE_DROP_PCT) -> float:
    """저압 분기로 갈 수 있는 최대 거리 (m).

    저압으로 끌면 거리를 정하는 것은 허용전류가 아니라 전압강하다.
    ΔV = √3·I·L·(R·cosφ + X·sinφ) 를 허용 강하로 되푼 값이다.
    이 거리를 넘으면 케이블을 키우거나 고압으로 분기해 국소 변압기를 둔다.
    """
    size = lv_main_cable_mm2() if size_mm2 is None else size_mm2
    r, x = LV_CABLE_IMPEDANCE[size]
    sin_phi = (1.0 - POWER_FACTOR ** 2) ** 0.5
    drop_per_km = 3 ** 0.5 * demand_current_a() * (r * POWER_FACTOR + x * sin_phi)
    allowed_v = SUPPLY_VOLTAGE_V * drop_pct / 100.0
    return round(allowed_v / drop_per_km * 1000.0, 1)


def apparent_demand_kva() -> float:
    """수요 피상전력 (kVA) — 변압기 부하율의 분자."""
    return round(demand_kw() / POWER_FACTOR, 1)


def transformer_required_kva(apparent_kva: float | None = None,
                             contract: float | None = None) -> float:
    """변압기가 담아야 하는 용량 (kVA) — 두 기준 중 큰 쪽.

    ① 목표 부하율 안에 수요 피상전력이 들어올 것
    ② 계약 피상전력을 흘릴 수 있을 것
    """
    a = apparent_demand_kva() if apparent_kva is None else apparent_kva
    c = contract_kva() if contract is None else contract
    return max(a / TRANSFORMER_LOAD_FACTOR, c)


def transformer_sizing_basis(apparent_kva: float | None = None,
                             contract: float | None = None) -> str:
    """둘 중 어느 기준이 용량을 정했는가 — 바뀌면 설계 근거가 바뀐 것이다."""
    a = apparent_demand_kva() if apparent_kva is None else apparent_kva
    c = contract_kva() if contract is None else contract
    return "계약 피상전력" if c >= a / TRANSFORMER_LOAD_FACTOR else "목표 부하율"


def transformer_kva(apparent_kva: float | None = None,
                    contract: float | None = None) -> int:
    """수전변압기 표준 용량 (kVA) — 필요 용량 위의 가장 작은 표준 용량."""
    need = transformer_required_kva(apparent_kva, contract)
    for rating in TRANSFORMER_RATINGS_KVA:
        if rating >= need:
            return rating
    raise ValueError("수요가 표준 변압기 용량을 넘는다 — 뱅크 분할 검토 필요")


def transformer_load_pct() -> float:
    """수요 피상전력 기준 변압기 부하율 (%)."""
    return round(apparent_demand_kva() / transformer_kva() * 100.0, 1)


def capacitor_kvar() -> int:
    """역률을 기준 0.90 → 목표 0.95 로 올리는 콘덴서 뱅크 (kVar, 표준 단계)."""
    import math

    def tan_phi(pf: float) -> float:
        return math.tan(math.acos(pf))

    need = demand_kw() * (tan_phi(BASE_POWER_FACTOR) - tan_phi(TARGET_POWER_FACTOR))
    for step in CAPACITOR_STEPS_KVAR:
        if step >= need:
            return step
    raise ValueError("필요 콘덴서가 표준 단계를 넘는다 — 뱅크 분할 검토 필요")


def hv_incoming_current_a() -> float:
    """고압 인입 선전류 (A) — 계약 피상전력을 22.9 kV 로 나눈 값."""
    return round(contract_kva() * 1000 / (3 ** 0.5 * HV_SUPPLY_VOLTAGE_V), 2)


def lv_cable_mm2(current_a: float) -> int:
    """그 전류를 받는 가장 작은 저압 표준 케이블 단면적 (mm²)."""
    for size, ampacity in sorted(LV_CABLE_AMPACITY_A.items()):
        if ampacity >= current_a:
            return size
    raise ValueError("전류가 표준 케이블 허용전류를 넘는다 — 병렬 포설 검토 필요")


def lv_main_cable_mm2() -> int:
    """변압기 2차 → MDB-101 주회로 단면적 (mm²).

    수요 전류가 아니라 **주 차단기 정격**을 받아야 한다 — 차단기가 떨어지기
    전에 케이블이 먼저 타면 보호가 성립하지 않는다.
    """
    return lv_cable_mm2(main_breaker_at())


#: 22.9 kV 급 VCB 표준 정격 (A). 전류가 7.5 A 라도 이보다 작은 기기는 없다 —
#: 고압 차단기는 전류가 아니라 차단용량·절연계급으로 정해진다.
VCB_RATING_A = 630


def incoming_cable_spec() -> str:
    """분기 케이블 사양 문자열 — 도면 인입도와 같은 값이어야 한다."""
    if taps_existing_service() and TAP_AT_LOW_VOLTAGE:
        return f"4C×{lv_main_cable_mm2()} mm² Cu (부지 저압 배전반 분기)"
    return f"CNCV-W 22.9 kV 1C×{HV_CABLE_MIN_MM2} mm² × 3"


#: 자체 수전설비 큐비클 열 — 폭(mm)·용도. 부지 인입이 없을 때만 선다.
SUBSTATION_CUBICLES: tuple[tuple[int, str], ...] = (
    (1000, "인입 LBS·전력퓨즈·피뢰기"),
    (1000, "계기용 변성기·VCB 주차단"),
    (1600, "몰드 변압기 (2차 380/220 V)"),
    (1000, "저압 ACB·역률개선 콘덴서"),
)

#: 고압 분기용 국소 변압기반 — 계량·주차단은 부지 쪽에 이미 있으므로 2면뿐이다.
UNIT_SUBSTATION_CUBICLES: tuple[tuple[int, str], ...] = (
    (1600, "몰드 변압기 (2차 380/220 V)"),
    (1000, "저압 ACB·역률개선 콘덴서"),
)

#: 큐비클 깊이와 높이 (mm).
SUBSTATION_CUBICLE_DEPTH_MM = 1500
SUBSTATION_CUBICLE_HEIGHT_MM = 2300

#: 전면 조작·인출 이격과 후면 점검 이격 (mm). 전기설비 유지보수 기준.
SUBSTATION_FRONT_CLEARANCE_MM = 1500
SUBSTATION_REAR_CLEARANCE_MM = 600


def substation_cubicles() -> tuple[tuple[int, str], ...]:
    """이 플랜트가 실제로 세워야 하는 큐비클 열.

    저압 분기면 아무것도 안 세운다(부지 배전반에서 차단기 하나 딴다).
    고압 분기면 변압기반 2면. 부지 인입이 없어야 자체 수전 4면이 된다.
    """
    if taps_existing_service():
        return () if TAP_AT_LOW_VOLTAGE else UNIT_SUBSTATION_CUBICLES
    return SUBSTATION_CUBICLES if needs_high_voltage() else ()


def substation_room_mm() -> tuple[int, int, int]:
    """전기실 소요 면적 (폭, 깊이, 높이 mm) — 큐비클 열 + 전후 이격.

    이 방은 공정 존이 아니라 구획된 전기실이다. 장비 밴드 안에 넣으면 안 된다.
    큐비클이 없으면 (0, 0, 0) — 세울 방이 없다는 뜻이다.
    """
    cubicles = substation_cubicles()
    if not cubicles:
        return (0, 0, 0)
    width = sum(w for w, _ in cubicles)
    depth = (SUBSTATION_CUBICLE_DEPTH_MM
             + SUBSTATION_FRONT_CLEARANCE_MM + SUBSTATION_REAR_CLEARANCE_MM)
    return (width, depth, SUBSTATION_CUBICLE_HEIGHT_MM + 700)


def incomer_summary() -> dict[str, object]:
    """인입 확정 요약 — 도면 인입도(EL-1005)가 이 값을 그대로 써야 한다."""
    room = substation_room_mm()
    tap_lv = taps_existing_service() and TAP_AT_LOW_VOLTAGE
    return {
        "method": supply_method(),
        "taps_site": taps_existing_service(),
        "tap_low_voltage": tap_lv,
        "site_service_kw": SITE_SERVICE_KW,
        "site_utilisation_pct": site_utilisation_pct(),
        "site_headroom_kw": site_headroom_kw(),
        "worst_case_kw": worst_case_kw(),
        "lv_tap_max_m": lv_tap_max_length_m(),
        "high_voltage": needs_high_voltage(),
        "hv_voltage_v": HV_SUPPLY_VOLTAGE_V if not tap_lv else SUPPLY_VOLTAGE_V,
        "lv_voltage_v": SUPPLY_VOLTAGE_V,
        "installed_kw": round(installed_kw(), 1),
        "demand_kw": round(demand_kw(), 2),
        "contract_kw": contract_kw(),
        "contract_kva": round(contract_kva(), 1),
        "apparent_kva": apparent_demand_kva(),
        "transformer_kva": 0 if tap_lv else transformer_kva(),
        # 저압 분기라 지금은 변압기가 없지만, 한계 거리를 넘어 고압 분기로 갈
        # 때의 용량은 도면 주기에 적혀 있어야 한다 — 그때 얼마짜리를 세우는지가
        # 실측 거리 판단의 대가이기 때문이다.
        "unit_transformer_kva": transformer_kva(),
        "transformer_basis": "—" if tap_lv else transformer_sizing_basis(),
        "transformer_load_pct": 0.0 if tap_lv else transformer_load_pct(),
        "capacitor_kvar": capacitor_kvar(),
        "breaker_headroom_kw": breaker_headroom_kw(),
        "hv_current_a": 0.0 if tap_lv else hv_incoming_current_a(),
        "lv_current_a": round(demand_current_a(), 1),
        "vcb_a": 0 if tap_lv else VCB_RATING_A,
        "main_breaker": f"{main_breaker_frame_a()}AF/{main_breaker_at()}AT",
        "lv_main_cable_mm2": lv_main_cable_mm2(),
        "incoming_cable": incoming_cable_spec(),
        "substation_room_mm": list(room),
    }
