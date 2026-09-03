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
