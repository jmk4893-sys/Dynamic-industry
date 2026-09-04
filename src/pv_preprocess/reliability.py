"""가동률과 예비품 — 연간 숫자가 무엇 위에 서 있는가.

§25 는 연 308,138 장을 적었고, §26 은 그 장수에서 AI 착수 1.2개월을 냈고,
저장 3년 63.9 TB 도 거기서 나왔다. 그 숫자들이 전부 한 줄 위에 서 있다 —
`smart.panels_per_h() × 4,125 h`. **가용률이 1.0 이라는 뜻이다.** 아무 설비도
고장 나지 않는다는 전제인데, 그 전제는 어디에도 적혀 있지 않았다.

MTBF 를 지어낼 수는 없다. 벤더 실적이 있어야 나오는 값이고, 없는 값을 적으면
그 순간 이 파일이 거짓이 된다(§43 의 Kst 와 같다). 그래서 **물음을 뒤집는다.**

    MTBF 를 모르니 가용률을 구할 수 없다
    → 그렇다면 **가용률을 정하고, 각 계통이 쓸 수 있는 정지시간을 나눈다**
    → 그 예산과 정비시간(MTTR)이 **요구 MTBF** 를 낸다

요구 MTBF 는 발주 사양에 적을 수 있는 값이다. 실적을 못 재는 자리에서
설계가 할 수 있는 일은 그것을 **요구로 바꾸는 것**이다.

버퍼가 여기 끼어든다. 직렬 사슬에 난 구멍이고, 그 구멍이 얼마나 값어치가
있는지도 값으로 낸다.

## 버퍼가 흡수하는지는 선언할 값이 아니다

종전에는 계통마다 `buffered=True/False` 를 적어 두었는데, 그것이 틀렸다.
CV·SG·GI 후단 계통을 "버퍼가 흡수한다" 고 적었지만 그 계통은 버퍼 **상류**에
있다 — 상류 정지를 버퍼가 막으려면 버퍼에 **재고**가 있어야 하는데, 모델의
완충시간은 `슬롯 ÷ 유입` 이라 빈 버퍼를 전제하고 있었다. 빈 버퍼는 상류
정지를 하나도 못 막는다. 적어 둔 흡수가 모델에 없었던 것이다.

그래서 `buffered` 를 파생으로 바꿨다. 계통이 버퍼의 **어느 쪽**에 있는지만
적고(`buffer_side`), 그쪽 방향의 완충시간이 그 계통의 MTTR 보다 긴지를
계산해서 판정한다. 이러면 완충시간이 줄거나 MTTR 이 늘면 흡수가 저절로
풀린다 — 적어 둔 값은 그렇게 안 풀린다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import air, handoff, maintain, safety, smart

# ── 목표 ─────────────────────────────────────────────────────────────────
#: 목표 가용률. **계약값이지 물리값이 아니다** — 발주처와 합의할 자리이고,
#: 0.92 는 이 규모 라인의 관례적 출발점이다. 이 한 줄이 아래 전부를 정한다.
TARGET_AVAILABILITY = 0.92

#: 연간 운전시간 (h) — smart 가 발주처 확인값에서 낸다.
def operating_hours() -> float:
    return smart.OPERATING_HOURS_PER_YEAR


def downtime_budget_h(availability: float | None = None) -> float:
    """목표를 지키려면 연간 몇 시간까지 서도 되는가.

    목표를 인자로 받는 이유는 §36 에서 배운 것 때문이다 — 값이 같은지만 보는
    시험은 식을 상수로 바꿔도 통과한다. 갈아 끼울 수 있어야 관계를 확인한다.
    """
    target = TARGET_AVAILABILITY if availability is None else availability
    return round(operating_hours() * (1 - target), 1)


# ── 계통 ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Block:
    """신뢰도 블록 하나.

    `share` 는 정지시간 예산의 배분율이다. 균등 배분이 아닌 이유는 계통마다
    부품 수와 마모부 수가 다르기 때문이고, 그 근거를 `basis` 에 적는다.
    """

    tag: str
    name: str
    share: float            # 정지시간 예산 배분율
    mttr_h: float           # 라인 복귀시간 — maintain.py 가 설계 기능에서 낸다
    redundant: bool
    #: 버퍼의 어느 쪽에 있는가. 'stock' 은 상류 — 버퍼 재고가 후단을 계속
    #: 돌린다. 'headroom' 은 후단 — 버퍼 여유공간이 전단을 계속 돌린다.
    #: ``None`` 은 버퍼가 못 막는 자리다 (버퍼 자신, 그리고 유틸리티).
    buffer_side: str | None
    basis: str

    @property
    def buffered(self) -> bool:
        """버퍼가 이 계통의 정지를 흡수하는가. **선언이 아니라 계산이다.**

        완충시간이 MTTR 보다 짧으면 흡수가 안 된다 — 버퍼가 바닥나거나 꽉 찬
        뒤에는 라인이 선다. 그래서 두 값을 여기서 비교한다.
        """
        ride = ride_through_of(self.buffer_side)
        return ride is not None and ride >= self.mttr_h

    def downtime_h(self, availability: float | None = None) -> float:
        return round(downtime_budget_h(availability) * self.share, 2)

    @property
    def base_mttr_h(self) -> float:
        """정비성 개선 **전**의 현장 수리시간. 조달 사양의 기준선이다."""
        return maintain.PROFILE_BY_TAG[self.tag].base_h

    def failures_per_year(self, availability: float | None = None) -> float:
        """연간 고장 횟수. **개선 전 MTTR 로 나눈다.**

        고장률은 설비의 성질이라 정비 방식이 바꾸는 값이 아니다. 개선된 MTTR 로
        나누면 "여섯 배 더 자주 고장 나도 된다" 는 허가가 되어 요구 MTBF 가
        엉뚱하게 느슨해진다 — 조달 사양이 그렇게 흔들리면 안 된다.
        짧아진 복구시간은 `achievable_availability()` 로만 돌린다.
        """
        return round(self.downtime_h(availability) / self.base_mttr_h, 2)

    def required_mtbf_h(self, availability: float | None = None) -> int:
        """발주 사양에 적을 값 — 이만큼은 버텨야 예산 안에 든다."""
        return int(operating_hours() / max(self.failures_per_year(availability), 1e-9))


#: 정지시간 예산 배분과 흡수 구조. **MTTR 은 여기 적지 않는다** —
#: `maintain.py` 가 설계 기능(온보드 진단·정비 접근·교환 모듈·자동 복귀·
#: 도킹 레일)에서 낸다. 숫자를 여기 적으면 "MTTR 을 줄이겠다" 가 숫자를 고쳐
#: 적는 일이 되어 버린다.
_SHARES: tuple[tuple[str, str, float, bool, str | None, str], ...] = (
    ("RB-AFU", "AFU-101 투입·듀얼 리프트·비전", 0.10, True, "stock",
     "지게차 인터페이스라 외란이 많다. 다만 **이미 2식이다** — LFT-101A/B 리프트, "
     "VS-101A/B 비전, EOAT 진공 A/B. 한쪽이 서도 절반 속도로 돈다. "
     "종전 모델이 이 이중화를 세지 않아 단일고장으로 잡혀 있었다"),
    ("RB-BFC", "BFC-101A/B 반전·셔틀·승강", 0.12, True, "stock",
     "Bay 2식이라 한쪽이 서도 절반 속도로 돈다 — 완전정지는 공통부(포탈·유압)뿐"),
    ("RB-ROBOT", "RB-101 로봇·EOAT", 0.08, False, "stock",
     "OEM 로봇 본체는 견고하다. 마모는 EOAT 진공 패드와 그리퍼 쪽. "
     "버퍼 상류라 재고가 도는 동안 후단이 안 선다"),
    ("RB-JBR", "JBR-201 3헤드 제거", 0.20, False, "stock",
     "**마모부가 가장 많다** — 칼날·가위·에어나이프·프로브. 헤드 3개가 직렬. "
     "이중화는 셀을 한 벌 더 사는 일이라 재고 완충으로 받는다"),
    ("RB-AFR", "AFR-101 프레임 분리·클램프", 0.15, False, "stock",
     "25 kN 인발은 부하가 크다. 유압·LM 캐리지·힘센서가 정지 원인. "
     "버퍼 상류이고 MTTR 0.49 h 가 배출 완충 안에 든다"),
    ("RB-POST", "CV-102·SG-301·GI-301/302 유리 후단", 0.12, False, "stock",
     "연마휠 교체가 잦다. **버퍼 상류**라 재고가 흡수한다 — 종전에는 흡수한다고 "
     "적어 두고도 모델에 재고가 없었다"),
    ("RB-GBR", "GBR-301 버퍼·적재", 0.06, True, None,
     "셔틀·슬롯 로더. **버퍼 자신이라 버퍼가 못 막는다.** 대신 적재 컬럼이 "
     "R-A·HOLD·R-B 3열이고 캐리지 배분이 레시피라, 한 열의 포크·승강이 서면 "
     "다른 열이 그 유리를 받는다 — 절반 속도로 돈다. 3열을 다 막는 것은 수평주행 "
     "하나뿐이라 같은 레일에 구동을 둘 걸었다. 공통으로 남는 것은 레일과 데크 "
     "구조다(BFC 의 포탈·유압과 같은 성격)"),
    ("RB-GRM", "GRM-401 IR·탠덤 박리", 0.12, False, "headroom",
     "IR 램프 60개와 핫나이프. 램프 1개 고장은 감속 운전이라 완전정지가 아니다. "
     "버퍼 하류라 여유공간이 흡수한다 — 전단이 그 동안 계속 돈다"),
    ("RB-UTIL", "유틸리티 — 공압·진공·집진·유압", 0.05, True, None,
     "컴프레서 1운전 1예비·진공 2기라 단일고장이 라인을 안 세운다. "
     "다만 집진이 서면 SG-301 이 못 돈다"),
)

BLOCKS: tuple[Block, ...] = tuple(
    Block(tag, name, share, maintain.mttr_h(tag), redundant, side, basis)
    for tag, name, share, redundant, side, basis in _SHARES
)


def blocks_share_sums_to_one() -> bool:
    return abs(sum(b.share for b in BLOCKS) - 1.0) < 1e-9


def redundant_blocks() -> tuple[Block, ...]:
    return tuple(b for b in BLOCKS if b.redundant)


def buffered_blocks() -> tuple[Block, ...]:
    return tuple(b for b in BLOCKS if b.buffered)


def governing_block(availability: float | None = None) -> Block:
    """정지시간을 가장 많이 쓰는 계통 — 예비품과 정비계획이 여기서 시작한다."""
    return max(BLOCKS, key=lambda b: b.downtime_h(availability))


def tightest_mtbf_block(availability: float | None = None) -> Block:
    """요구 MTBF 가 가장 높은 계통 — 발주가 가장 어려운 자리다."""
    return max(BLOCKS, key=lambda b: b.required_mtbf_h(availability))


# ── 버퍼가 내는 구멍 ─────────────────────────────────────────────────────
#: 버퍼 방향별 완충시간을 내는 자리. `Block.buffered` 가 이것을 쓴다.
#: **두 방향은 같은 슬롯을 나눠 쓴다** — 한쪽을 키우면 한쪽이 준다.
RIDE_THROUGH_H = {
    "stock": handoff.buffer_drain_ride_through_h,      # 상류 정지 → 재고가 후단을 돌린다
    "headroom": handoff.buffer_ride_through_h,         # 후단 정지 → 여유공간이 전단을 돌린다
}


def ride_through_of(side: str | None) -> float | None:
    """그 방향의 완충시간 (h). 버퍼가 못 막는 자리면 ``None``."""
    getter = RIDE_THROUGH_H.get(side) if side is not None else None
    return None if getter is None else getter()


def buffer_ride_through_h() -> float:
    """버퍼가 **후단** 정지를 얼마나 버티는가 — handoff 가 단일 출처다."""
    return handoff.buffer_ride_through_h()


def buffered_downtime_h(availability: float | None = None) -> float:
    """버퍼가 흡수하는 정지시간 (h/년).

    한 번 서는 시간이 버틸 수 있는 시간보다 짧아야 흡수된다. 후단 계통의
    MTTR 이 그보다 길면 버퍼는 **부분만** 벌어 준다 — 그 부분이 이 값이다.
    """
    total = 0.0
    for block in buffered_blocks():
        ride = ride_through_of(block.buffer_side)
        absorbed = min(block.mttr_h, ride if ride is not None else 0.0)
        total += absorbed * block.failures_per_year(availability)
    return round(total, 2)


def availability_without_buffer(availability: float | None = None) -> float:
    """버퍼가 없었다면 같은 고장률에서 가용률이 얼마였을까."""
    lost = downtime_budget_h(availability) + buffered_downtime_h(availability)
    return round(1 - lost / operating_hours(), 4)


# ── 연간 숫자가 무엇 위에 서 있는가 ──────────────────────────────────────
#: 정비성 개선 전의 계획 MTTR (h). 요구 MTBF 는 이 값 위에서 정해졌다.
#: 개선분을 어디로 돌릴지 계산하려면 출발점이 남아 있어야 한다.
BASE_MTTR_H: dict[str, float] = {p.tag: p.base_h for p in maintain.PROFILES}


def failures_per_year_at_base(tag: str, availability: float | None = None) -> float:
    """정비성 개선 **전** 기준의 연간 고장 횟수.

    고장률은 설비의 성질이지 정비 방식이 바꾸는 값이 아니다. 그래서 개선 뒤에도
    이 횟수를 그대로 두고, 짧아진 복구시간을 **가용률로** 돌린다.
    """
    block = next(b for b in BLOCKS if b.tag == tag)
    return block.failures_per_year(availability)


def achievable_availability(availability: float | None = None) -> float:
    """정비성 개선이 만드는 가용률.

    예산을 고정한 채 MTTR 만 낮추면 "여섯 배 더 자주 고장 나도 된다" 는 허가로
    읽힌다 — 그것은 개선이 아니다. 고장 횟수를 그대로 두고 복구시간만 짧아진
    것으로 계산해야 개선분이 보인다.

    버퍼도 여기서 다시 계산된다. MTTR 이 그 방향의 완충시간보다 짧아지면
    **버퍼가 흡수하는 비율이 100 % 가 된다** — 짧은 정지는 라인을 아예 못 세운다.
    """
    stopped = 0.0
    for b in BLOCKS:
        n = failures_per_year_at_base(b.tag, availability)
        per_stop = b.mttr_h
        if b.buffered:
            ride = ride_through_of(b.buffer_side)
            per_stop = max(0.0, per_stop - (ride if ride is not None else 0.0))
        stopped += n * per_stop
    return round(1 - stopped / operating_hours(), 4)


def maintainability_gain(availability: float | None = None) -> dict[str, float]:
    """정비성 개선의 값어치 — 가용률과 연간 장수로."""
    target = TARGET_AVAILABILITY if availability is None else availability
    got = achievable_availability(availability)
    return {
        "contract": target,
        "achievable": got,
        "gainPoints": round((got - target) * 100, 2),
        "extraPanels": annual_panels(got) - annual_panels(target),
    }


def nominal_annual_panels() -> int:
    """가용률을 안 본 장수 — §25·§26 이 쓰는 값."""
    return round(smart.panels_per_h() * operating_hours())


def annual_panels(availability: float | None = None) -> int:
    """가용률을 얹은 장수."""
    factor = TARGET_AVAILABILITY if availability is None else availability
    return round(nominal_annual_panels() * factor)


def annual_shortfall() -> int:
    """가용률을 안 본 것과 본 것의 차이 — 라벨·저장·매출이 전부 여기 비례한다."""
    return nominal_annual_panels() - annual_panels()


# ── 예비품 ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Spare:
    """마모품 한 종류.

    `per_year` 가 None 이면 소요를 아직 못 낸다는 뜻이다 — 수명이 벤더값이거나
    시운전 실측이라야 나오는 것들이다. 그 사실을 0 으로 덮지 않는다.
    """

    tag: str
    name: str
    block: str
    qty_installed: int
    per_year: float | None
    lead_weeks: int
    basis: str

    def stock(self, weeks: int | None = None) -> int | None:
        """권장 재고 — 조달기간 소요 + 1개(단일고장 대비). 소요를 모르면 None."""
        if self.per_year is None:
            return None
        weeks = self.lead_weeks if weeks is None else weeks
        return max(1, round(self.per_year * weeks / 52 + 1))


def _pulses_per_year() -> float:
    """DX-601 탈진 펄스 횟수 — 밸브 수와 간격에서 나온다."""
    return air.pulse_valves() * (60 / air.PULSE_INTERVAL_MIN) * operating_hours()


#: 필터백 1장이 덮는 여과 면적 (m²). 표준 백 Ø160 × 2,000 대략값.
BAG_AREA_M2 = 1.0

#: 필터백 수명 (년). 유리분은 연마성이 강해 통상보다 짧게 잡는다.
BAG_LIFE_YEARS = 2.0

#: 펄스 다이어프램 수명 (사이클). 표준 다이어프램 밸브의 관례값.
DIAPHRAGM_LIFE_CYCLES = 1_000_000


def filter_bags() -> int:
    return max(1, round(air.filter_area_m2() / BAG_AREA_M2))


def SPARES() -> tuple[Spare, ...]:
    """마모품 일람. 파생값이 있어 상수가 아니라 함수다."""
    panels = annual_panels()
    return (
        Spare("SP-01", "SKD11 교체형 칼날 카세트 (JBR)", "RB-JBR", 3, None, 6,
              "패널당 절단 길이는 알지만 **칼날 수명(장수)이 없다** — "
              "시운전 run-at-rate 에서 마모량을 재야 나온다"),
        Spare("SP-02", "핫나이프 (TDM-201 탠덤)", "RB-GRM", 2, None, 8,
              "60 mm/s 로 EVA 를 가른다. 수명은 GRM 벤더값"),
        Spare("SP-03", "연마휠 (SG-301)", "RB-POST", 2, None, 4,
              "유리 엣지 연마. 마모 보상이 컴플라이언스 제어에 있으므로 "
              "보상량 한계가 곧 교체 시점이다 — 그 한계도 벤더값"),
        Spare("SP-04", "집진 필터백", "RB-UTIL", filter_bags(),
              round(filter_bags() / BAG_LIFE_YEARS, 1), 6,
              f"여과 {air.filter_area_m2():g} m² ÷ 백 {BAG_AREA_M2:g} m² = {filter_bags()}장, "
              f"수명 {BAG_LIFE_YEARS:g} 년. 유리분이 연마성이라 짧게 잡는다"),
        Spare("SP-05", "펄스 다이어프램 밸브", "RB-UTIL", air.pulse_valves(),
              round(_pulses_per_year() / DIAPHRAGM_LIFE_CYCLES, 2), 8,
              f"밸브당 연 {_pulses_per_year() / air.pulse_valves():,.0f} 회 작동. "
              "다이어프램 수명 100만 회 기준"),
        Spare("SP-06", "EOAT 진공 패드", "RB-ROBOT", 8, round(panels / 200_000 * 8, 1), 4,
              "패널마다 물었다 놓는다. 패드 수명 20만 사이클 기준 — 계획값"),
        Spare("SP-07", "안전 뮤팅 센서", "RB-JBR",
              next(d.qty * 2 for d in safety.SAFETY_DEVICES if d.tag == "JB-SF-009"),
              None, 10,
              f"연 {safety.cycles_per_year():,} 회 작동. B10d 가 있어야 T10d 가 나온다 — "
              f"200만 밑이면 사명시간 {safety.MISSION_TIME_YEARS} 년 안에 정기교체 대상"),
        Spare("SP-08", "유압유·리턴 필터 (HPU-101·601)", "RB-AFR", 2, 2.0, 4,
              "연 1회 교환 × 2기. 오일쿨러가 붙어 있어 열화가 느리지만 "
              "인발 부하가 커서 관례보다 짧게 잡는다"),
        Spare("SP-09", "컴프레서 흡입필터·오일세퍼레이터", "RB-UTIL",
              air.COMPRESSOR_UNITS, float(air.COMPRESSOR_UNITS), 4,
              "1운전 1예비지만 교대 운전이므로 두 대 다 소모된다"),
        Spare("SP-10", "IR 램프 (GRM-401)", "RB-GRM", handoff.LAMP_COUNT, None, 12,
              f"{handoff.LAMP_COUNT}개 뱅크. 램프 1개 고장은 감속 운전이라 "
              "완전정지가 아니지만, 누적되면 처리량이 내려간다. 수명은 벤더값"),
    )


def spares_with_rate() -> tuple[Spare, ...]:
    return tuple(s for s in SPARES() if s.per_year is not None)


def spares_pending() -> tuple[Spare, ...]:
    """수명을 아직 모르는 것 — 시운전이나 벤더가 채운다."""
    return tuple(s for s in SPARES() if s.per_year is None)


def initial_stock() -> dict[str, int]:
    """초기 예비품 — 소요를 아는 것만."""
    return {s.tag: s.stock() for s in spares_with_rate()}


def summary() -> dict[str, object]:
    worst = governing_block()
    tight = tightest_mtbf_block()
    return {
        "targetAvailability": TARGET_AVAILABILITY,
        "operatingHours": operating_hours(),
        "downtimeBudgetH": downtime_budget_h(),
        "blocks": len(BLOCKS),
        "redundant": len(redundant_blocks()),
        "buffered": len(buffered_blocks()),
        "governing": worst.tag,
        "governingDowntimeH": worst.downtime_h(),
        "governingFailures": worst.failures_per_year(),
        "tightestMtbf": tight.tag,
        "tightestMtbfH": tight.required_mtbf_h(),
        "rideThroughH": buffer_ride_through_h(),
        "bufferedDowntimeH": buffered_downtime_h(),
        "availabilityWithoutBuffer": availability_without_buffer(),
        "worstMttrH": max(b.mttr_h for b in BLOCKS),
        "worstBaseMttrH": max(b.base_mttr_h for b in BLOCKS),
        "achievableAvailability": achievable_availability(),
        "maintainGainPoints": maintainability_gain()["gainPoints"],
        "maintainExtraPanels": maintainability_gain()["extraPanels"],
        "nominalPanels": nominal_annual_panels(),
        "annualPanels": annual_panels(),
        "shortfall": annual_shortfall(),
        "spares": len(SPARES()),
        "sparesPending": len(spares_pending()),
        "filterBags": filter_bags(),
    }
