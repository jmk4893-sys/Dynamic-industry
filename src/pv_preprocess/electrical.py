"""전처리 플랜트 전기 인입 — 부하 집계와 인입 규격 산정.

설계도의 전기 인입도(PV-PLANT-EL-1005)가 이 계산과 어긋나지 않는지
`tests/test_pv_preprocess.py` 가 검사한다.

부하값의 출처는 두 가지다.

* **명시값** — 셀 GA 시트의 유틸리티 란에 이미 적혀 있던 값
  (JBR-201 약 6.5 kW, AFR HPU-601 7.5 kW, 집진 1,000 + 350 m³/h).
* **계획값** — 그 외 셀은 구성 기기에서 잡은 계획 부하다. OEM 하중도·전동기 명판이
  확정되면 바꿔야 하며, 그때 이 파일만 고치면 도면과 테스트가 같이 따라온다.

**수전 방식은 계약전력에서 파생한다.** REV.22 까지는 계약전력 67.9 kW 라 저압
3Φ 4W 380/220 V 직결이 맞았지만, REV.23 에서 유리제거셀 IR 뱅크 175 kW 가
들어오며 계약전력이 268.2 kW 가 됐다 — 한전 저압 공급 상한 100 kW 를 넘어
**22.9 kV 고압 수전 + 수전변압기**로 바뀐다. 전압·변압기·차단기·케이블·수전실
면적이 전부 이 판정에서 따라 나오므로, 부하가 다시 바뀌면 여기만 고치면 된다.

역률 0.90 은 서보·인버터에 라인리액터를 다는 전제이며, 고조파 실측 전에는
확정값이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 저압 배전 전압 (V, 선간). 변압기 2차이자 플랜트 내부 배전 전압이다.
SUPPLY_VOLTAGE_V = 380

# ── 수전 방식 ────────────────────────────────────────────────────────────
# REV.23 유리제거셀이 들어오며 계약전력이 268.2 kW 가 됐다. 한전 저압 공급은
# 계약전력 100 kW 미만이므로 **저압 직결 인입이 성립하지 않는다** — 22.9 kV
# 고압 수전 + 수전변압기로 바꿔야 한다. 전처리만일 때(계약전력 67.9 kW)는
# 저압이 맞았고, 그래서 REV.22 까지의 도면은 틀린 것이 아니라 전제가 바뀐 것이다.

#: 한전 저압 공급 상한 (kW, 계약전력). 이 값 이상이면 고압 수전이다.
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


#: 하위 호환 이름. 프레임은 이제 수요에서 파생한다.
MAIN_BREAKER_FRAME_A = main_breaker_frame_a()


# ── 인입 확정 (REV.23) ────────────────────────────────────────────────────
# 여기부터가 "인입을 확정한다"는 것의 실체다. 계약전력이 저압 한계를 넘으면
# 전압·변압기·차단기·케이블·설치 면적이 전부 따라 바뀐다.


def contract_kw() -> float:
    """계약 전력 (kW) — 한전 저압/고압 판정의 기준이 되는 값."""
    return round(demand_kw() * CONTRACT_MARGIN, 1)


def needs_high_voltage() -> bool:
    """저압 직결로 받을 수 있는가. False 면 22.9 kV 수전이다."""
    return contract_kw() >= LOW_VOLTAGE_LIMIT_KW


def supply_method() -> str:
    return "고압 22.9 kV 수전 + 수전변압기" if needs_high_voltage() else "저압 380 V 직결 인입"


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
    """인입 케이블 사양 문자열 — 도면 인입도와 같은 값이어야 한다."""
    if needs_high_voltage():
        return f"CNCV-W 22.9 kV 1C×{HV_CABLE_MIN_MM2} mm² × 3"
    return f"4C×{lv_cable_mm2(main_breaker_at())} mm² Cu"


#: 수전설비 큐비클 열 — 폭(mm)·용도. 고압 수전일 때만 선다.
SUBSTATION_CUBICLES: tuple[tuple[int, str], ...] = (
    (1000, "인입 LBS·전력퓨즈·피뢰기"),
    (1000, "계기용 변성기·VCB 주차단"),
    (1600, "몰드 변압기 (2차 380/220 V)"),
    (1000, "저압 ACB·역률개선 콘덴서"),
)

#: 큐비클 깊이와 높이 (mm).
SUBSTATION_CUBICLE_DEPTH_MM = 1500
SUBSTATION_CUBICLE_HEIGHT_MM = 2300

#: 전면 조작·인출 이격과 후면 점검 이격 (mm). 전기설비 유지보수 기준.
SUBSTATION_FRONT_CLEARANCE_MM = 1500
SUBSTATION_REAR_CLEARANCE_MM = 600


def substation_room_mm() -> tuple[int, int, int]:
    """수전실 소요 면적 (폭, 깊이, 높이 mm) — 큐비클 열 + 전후 이격.

    이 방은 공정 존이 아니라 구획된 전기실이다. 장비 밴드 안에 넣으면 안 된다.
    """
    if not needs_high_voltage():
        return (0, 0, 0)
    width = sum(w for w, _ in SUBSTATION_CUBICLES)
    depth = (SUBSTATION_CUBICLE_DEPTH_MM
             + SUBSTATION_FRONT_CLEARANCE_MM + SUBSTATION_REAR_CLEARANCE_MM)
    return (width, depth, SUBSTATION_CUBICLE_HEIGHT_MM + 700)


def incomer_summary() -> dict[str, object]:
    """인입 확정 요약 — 도면 인입도(EL-1005)가 이 값을 그대로 써야 한다."""
    room = substation_room_mm()
    return {
        "method": supply_method(),
        "high_voltage": needs_high_voltage(),
        "hv_voltage_v": HV_SUPPLY_VOLTAGE_V if needs_high_voltage() else SUPPLY_VOLTAGE_V,
        "lv_voltage_v": SUPPLY_VOLTAGE_V,
        "installed_kw": round(installed_kw(), 1),
        "demand_kw": round(demand_kw(), 2),
        "contract_kw": contract_kw(),
        "contract_kva": round(contract_kva(), 1),
        "apparent_kva": apparent_demand_kva(),
        "transformer_kva": transformer_kva(),
        "transformer_basis": transformer_sizing_basis(),
        "transformer_load_pct": transformer_load_pct(),
        "capacitor_kvar": capacitor_kvar(),
        "hv_current_a": hv_incoming_current_a(),
        "lv_current_a": round(demand_current_a(), 1),
        "vcb_a": VCB_RATING_A,
        "main_breaker": f"{main_breaker_frame_a()}AF/{main_breaker_at()}AT",
        "lv_main_cable_mm2": lv_main_cable_mm2(),
        "incoming_cable": incoming_cable_spec(),
        "substation_room_mm": list(room),
    }
