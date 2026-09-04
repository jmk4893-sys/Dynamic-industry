"""FAT · SAT — 검수 항목이 모델에서 나온다.

검수 프로토콜을 따로 쓰면 도면과 어긋난다. 도면이 REV.36 인데 검수서는
REV.28 의 값을 들고 있는 일이 실제로 흔하고, 그러면 현장에서 "도면이 맞나
검수서가 맞나" 로 하루가 간다.

그래서 여기서는 항목마다 **어느 모듈의 어느 값을 확인하는지**를 적는다.
`expected` 는 리터럴이 아니라 호출이다 — 모델이 바뀌면 검수 기준이 따라
바뀌고, 어긋날 수가 없다.

FAT 와 SAT 를 가르는 기준은 하나다. **공장에서 확인할 수 있는가.**

* 단품 성능·안전 회로·정지시간은 공장에서 된다 → FAT
* 공정 흐름·처리량·유리 회수율·환기·소음은 라인이 다 서고 물건이 흘러야
  된다 → SAT
* 그 사이에 하나가 더 있다 — **run-at-rate**. 설비는 다 서 있고 성능도
  나오는데, 발주처 실제 반입물로 정격 속도를 유지할 수 있는지는 또 다른
  물음이다. 캠페인 구성비(정상 53 · 깨짐 5 · 전손 2)가 현장과 다르면
  §26 의 라벨 공급도 §44 의 가용률도 통째로 달라진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import (access, acoustics, air, campaign, crane, dust, electrical, handoff,
               mounting, reliability, safety, seismic, thermal)

FAT = "FAT"
SAT = "SAT"
RAR = "run-at-rate"

STAGES: tuple[str, ...] = (FAT, SAT, RAR)


@dataclass(frozen=True)
class Item:
    """검수 항목 하나."""

    tag: str
    stage: str
    subject: str
    method: str
    source: str                     # 어느 모듈의 어느 값인가
    expected: Callable[[], object]  # 리터럴이 아니라 호출이다
    tolerance: str
    blocking: bool                  # 불합격이면 인수를 막는가

    def value(self) -> object:
        return self.expected()


def items() -> tuple[Item, ...]:
    """검수 항목. 기대값이 파생이라 상수가 아니라 함수다."""
    return (
        # ── FAT — 공장에서 확인 가능한 것 ────────────────────────────────
        Item("F-01", FAT, "안전 정지시간", "JB-SF-008 시험포트 · 분해능 ≤1 ms",
             "safety.stop_chain_ms", lambda: safety.stop_chain_ms(),
             f"≤ {safety.tightest_opening().budget_ms} ms (최소 예산)", True),
        Item("F-02", FAT, "안전기능 동작", "기능별 강제 고장 주입 · 이중채널 단선",
             "safety.SAFETY_FUNCTIONS", lambda: len(safety.SAFETY_FUNCTIONS),
             "전 기능 안전측 정지 · 재기동 금지 확인", True),
        Item("F-03", FAT, "안전 I/O 점수", "단자대 대조 · FSoE 노드 스캔",
             "safety.summary['inputs']", lambda: safety.summary()["inputs"],
             f"입력 {safety.summary()['inputs']} · 출력 {safety.summary()['outputs']} · "
             f"FSoE {safety.summary()['fsoeNodes']} 노드 인식", True),
        Item("F-04", FAT, "서보 축 동작·STO", "축별 위치결정 반복정밀도 · STO 차단 확인",
             "safety.sto_nodes", lambda: safety.sto_nodes(),
             f"{safety.sto_nodes()}축 전부 · 반복정밀도는 축별 사양", True),
        Item("F-05", FAT, "압축공기 공급", "무부하 FAD 실측 · 리시버 강하시험",
             "air.compressor_fad_nl_min", lambda: air.compressor_fad_nl_min(),
             f"≥ {air.required_fad_nl_min()} NL/min · 기동 ≤ {air.MAX_STARTS_PER_H} 회/h", True),
        Item("F-06", FAT, "압축공기 누설률", "야간 무부하 압력강하 · FL-901",
             "air.LEAKAGE_MARGIN", lambda: air.LEAKAGE_MARGIN,
             f"≤ {air.LEAKAGE_MARGIN * 100:g} % — 넘으면 컴프레서 선정이 틀린 것이 "
             "아니라 배관이 샌다", False),
        Item("F-07", FAT, "전력 수요", "분전반별 실측 · 동시 최악 조건",
             "electrical.demand_kw", lambda: electrical.demand_kw(),
             f"≤ {electrical.coincident_worst_case_kw()} kW (동시 최악)", True),
        Item("F-08", FAT, "앵커 시공", "토크 검사 · 인발시험 표본",
             "mounting.total_anchors", lambda: mounting.total_anchors(),
             f"{mounting.total_anchors()}본 전수 토크 · 5 % 인발시험", True),
        Item("F-09", FAT, "크레인 인양", "정격하중 시험 · 후크 최고높이 실측",
             "crane.hook_height_mm", lambda: crane.hook_height_mm(),
             f"후크 {crane.hook_height_mm():,} mm · 정격 {crane.CAPACITY_T:g} t", True),
        Item("F-10", FAT, "반입 개구 통과", "최대 모듈 실물 통과",
             "crane.entry_opening_mm", lambda: crane.ENTRY_OPENING_MM,
             f"폭 여유 {crane.entry_width_margin_mm():,} mm · 저상 대차 높이 확인", True),

        # ── SAT — 라인이 서야 되는 것 ────────────────────────────────────
        Item("S-01", SAT, "택트", "연속 60장 캠페인 · 공정시계",
             "campaign.summary['takt_s']", lambda: campaign.summary()["takt_s"],
             f"≤ {campaign.summary()['takt_s']:.1f} s", True),
        Item("S-02", SAT, "처리량", "60장 캠페인 실측",
             "campaign.summary['throughput_per_h']",
             lambda: campaign.summary()["throughput_per_h"],
             f"≥ {campaign.summary()['throughput_per_h']} 장/h", True),
        Item("S-03", SAT, "유리제거 완료시간", "정상 53장 기준",
             "handoff.summary['downstream_per_h']",
             lambda: handoff.summary()["downstream_per_h"],
             f"≥ {handoff.summary()['downstream_per_h']} 장/h — 후단이 전단을 "
             "못 받으면 버퍼가 찬다", True),
        Item("S-04", SAT, "버퍼 완충", "후단 강제정지 · 전단 지속시간 측정",
             "handoff.buffer_ride_through_h",
             lambda: handoff.buffer_ride_through_h(),
             f"≥ {handoff.buffer_ride_through_h()} h — §44 가용률이 이 값 위에 선다", True),
        Item("S-05", SAT, "환기·열수지", "정상운전 3 h · 실내온도 상승",
             "thermal.required_airflow_m3h",
             lambda: thermal.required_airflow_m3h(),
             f"{thermal.required_airflow_m3h():,} m³/h 에서 "
             f"ΔT {thermal.ROOM_DELTA_T_C:g} K 이내 · 후드 포집률이 전제", True),
        Item("S-06", SAT, "소음", "근접·통로 실측 (A특성)",
             "acoustics.worst_aisle_dba", lambda: acoustics.worst_aisle_dba()[1],
             f"통로 ≤ {acoustics.AISLE_LIMIT_DBA:g} dBA · 근접은 "
             f"≤ {acoustics.NEAR_FIELD_LIMIT_DBA:g} dBA (보호구 기준)", True),
        Item("S-07", SAT, "집진 성능", "풍량·차압·포집률",
             "dust.counted_flow_m3h", lambda: dust.counted_flow_m3h(),
             f"{dust.counted_flow_m3h():,} m³/h — 풍량 미확정 "
             f"{len(dust.unquantified_streams())} 건이 더해지면 이 값이 바뀐다", True),
        Item("S-08", SAT, "분진 시료 채취", "혼합 분진 채취 → EN 14034 시험 의뢰",
             "dust.REQUIRED_TESTS", lambda: len(dust.REQUIRED_TESTS),
             "시험 결과가 벤트 설계를 정한다 — SAT 에서 시료만 뜬다", True),
        Item("S-09", SAT, "고소 접근", "이동식 작업대 진입 · 고정점 하중시험",
             "access.ANCHOR_POINT_KN", lambda: access.ANCHOR_POINT_KN,
             f"고정점 {access.ANCHOR_POINT_KN:g} kN · 통로 유효 "
             f"{access.AISLE_CLEAR_MM:,} mm 유지 확인", True),
        Item("S-10", SAT, "내진 앵커 배정", "미배정 3대 앵커군 시공 확인",
             "seismic.unanchored", lambda: len(seismic.unanchored()),
             f"0 이어야 한다 — 지금 {len(seismic.unanchored())}", True),

        # ── run-at-rate — 실제 반입물로 ─────────────────────────────────
        Item("R-01", RAR, "반입물 구성비", "발주처 실제 반입 200장 분류",
             "campaign.condition_counts", lambda: campaign.condition_counts(),
             "정상 53 : 깨짐 5 : 전손 2 (60장 기준) — 다르면 §26·§44 가 바뀐다", True),
        Item("R-02", RAR, "정격 유지", "8 h 연속 · 가용률 실측",
             "reliability.TARGET_AVAILABILITY",
             lambda: reliability.TARGET_AVAILABILITY,
             f"≥ {reliability.TARGET_AVAILABILITY} — 계약값이지 물리값이 아니다", True),
        Item("R-03", RAR, "연간 환산", "실측 가용률 × 운전시간",
             "reliability.annual_panels", lambda: reliability.annual_panels(),
             f"{reliability.annual_panels():,} 장/년 — §26 의 라벨 공급이 여기 비례한다", False),
        Item("R-04", RAR, "마모율 실측", "칼날·연마휠·핫나이프 마모량",
             "reliability.spares_pending",
             lambda: len(reliability.spares_pending()),
             "수명 미확정 5종을 여기서 채운다 — 예비품 발주의 근거", True),
        Item("R-05", RAR, "누설·무부하 소비", "무부하 시간대 공압 소비",
             "air.average_nl_min", lambda: air.average_nl_min(),
             "AI-03 이 이 데이터로 누설을 산출한다", False),
    )


def by_stage(stage: str) -> tuple[Item, ...]:
    if stage not in STAGES:
        raise ValueError(f"알 수 없는 단계: {stage}")
    return tuple(i for i in items() if i.stage == stage)


def blocking(stage: str | None = None) -> tuple[Item, ...]:
    rows = items() if stage is None else by_stage(stage)
    return tuple(i for i in rows if i.blocking)


def sources() -> tuple[str, ...]:
    """검수가 확인하는 모델 값들 — 중복 없이."""
    return tuple(sorted({i.source for i in items()}))


def every_item_has_a_source(rows: tuple[Item, ...] | None = None) -> bool:
    """근거 없는 검수 항목은 협상 대상이 된다 — 그러면 검수가 아니다.

    목록을 인자로 받는 이유는 §37 의 변이 시험 때문이다. 인자가 없으면
    시험이 `return True` 로 바꾼 것과 진짜 검사를 구분하지 못한다 — 근거가
    빠진 항목을 넣어 보고 False 가 나오는지를 봐야 검사가 산다.
    """
    return all(i.source and "." in i.source for i in (items() if rows is None else rows))


def open_at_handover() -> tuple[Item, ...]:
    """인수 시점에 아직 답이 없을 항목 — 미리 알고 시작해야 한다."""
    return tuple(i for i in items()
                 if i.tag in ("S-08", "S-10", "R-04"))


def summary() -> dict[str, object]:
    return {
        "items": len(items()),
        "fat": len(by_stage(FAT)),
        "sat": len(by_stage(SAT)),
        "runAtRate": len(by_stage(RAR)),
        "blocking": len(blocking()),
        "sources": len(sources()),
        "openAtHandover": len(open_at_handover()),
        "stopTimeMs": safety.stop_chain_ms(),
        "stopBudgetMs": safety.tightest_opening().budget_ms,
        "taktS": campaign.summary()["takt_s"],
        "throughputPerH": campaign.summary()["throughput_per_h"],
        "demandKw": electrical.demand_kw(),
        "airflowM3h": thermal.required_airflow_m3h(),
        "annualPanels": reliability.annual_panels(),
    }
