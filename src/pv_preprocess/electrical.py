"""전처리 플랜트 전기 인입 — 부하 집계와 인입 규격 산정.

설계도의 전기 인입도(PV-PLANT-EL-1005)가 이 계산과 어긋나지 않는지
`tests/test_pv_preprocess.py` 가 검사한다.

부하값의 출처는 두 가지다.

* **명시값** — 셀 GA 시트의 유틸리티 란에 이미 적혀 있던 값
  (JBR-201 약 6.5 kW, AFR HPU-601 7.5 kW, 집진 1,000 + 350 m³/h).
* **계획값** — 그 외 셀은 구성 기기에서 잡은 계획 부하다. OEM 하중도·전동기 명판이
  확정되면 바꿔야 하며, 그때 이 파일만 고치면 도면과 테스트가 같이 따라온다.

전압은 3Φ 4W 380/220 V. 역률 0.90 은 서보·인버터에 라인리액터를 다는 전제이며,
고조파 실측 전에는 확정값이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 인입 전압 (V, 선간)
SUPPLY_VOLTAGE_V = 380

#: 계획 역률. 라인리액터 적용 전제 — 고조파 실측으로 확정한다.
POWER_FACTOR = 0.90

#: 주 차단기 프레임/트립 (A)
MAIN_BREAKER_FRAME_A = 125

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
    Feeder("F1", "LP-AFU", "LFT-101A/B 서보 승강 · BFC-101A/B 반전 · CD-101 포획빔 · 투입 비전",
           12.0, 0.70, 40, "4C×10 mm² Cu", "계획"),
    Feeder("F2", "LP-RB", "RB-101 로봇 제어반 · EOAT 진공 · PT-101 정렬정반",
           9.0, 0.60, 32, "4C×6 mm² Cu", "계획"),
    Feeder("F3", "LP-JBR", "JBR-201 3헤드·X/Y 브리지·비전",
           6.5, 0.80, 20, "4C×4 mm² Cu", "GA 명시"),
    Feeder("F4", "LP-AFR", "HPU-601 7.5 kW · 장축 LM 캐리지 4축",
           11.5, 0.70, 32, "4C×10 mm² Cu", "GA 명시(HPU)"),
    Feeder("F5", "LP-GLASS", "SG-301 양측 연마 · CV-102/GI-301 · GI-302 광학",
           9.0, 0.70, 32, "4C×6 mm² Cu", "계획"),
    Feeder("F6", "LP-GBR", "GBR-301 수평셔틀 서보 · 도킹 도크",
           4.0, 0.50, 16, "4C×4 mm² Cu", "계획"),
    Feeder("F7", "LP-DX", "DX-601 집진 1,000 m³/h · JBR 국소집진 350 m³/h",
           11.0, 0.90, 32, "4C×6 mm² Cu", "GA 명시(풍량)"),
    Feeder("F8", "LP-CTRL", "안전 PLC · 비전 LAN · 제어반 UPS · 조명",
           5.0, 1.00, 20, "4C×4 mm² Cu", "계획"),
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
    for rating in (63, 80, 100, 125):
        if rating >= demand_current_a() * 1.1:
            return rating
    raise ValueError("수요 전류가 주 차단기 프레임을 넘는다 — 인입 재검토 필요")
