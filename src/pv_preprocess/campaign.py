"""60장 연속 투입 캠페인 — 3분류 판정, 파이프라인 연속 운전, 버퍼 분류.

한 장 추적(124.03 s 종단 체류)만으로는 연속 운전이 보이지 않는다. 이 모듈은
팔레트 두 개(각 30장)를 실제로 흘렸을 때 각 셀이 언제 무엇을 쥐고 있는지를
이산사건으로 만든다.

투입 비전 3분류 (요청 그대로)

* **전손** — 완전히 파손돼 못 쓰는 패널. 투입 비전(VS-101A/B)이 걸러
  BFC 가 반전 없이 인계높이로 내리고 RB-101 이 PT-101 대신 리젝트 랙
  (AFU-RJ-101, 페데스털 양옆)에 놓는다. 라인에 들어가지 않는다.
* **유리 깨짐** — 유리만 깨진 패널. 공정에 **그대로 태운다**. 정션박스 제거와
  알루미늄 프레임 제거를 정상품과 똑같이 거친 뒤, GBR-301 이 **파손 유리
  버퍼(R-B)** 로 분류 적재한다.
* **정상** — **정상 유리 버퍼(R-A)** 로 적재한다.

연속 운전 (파이프라인)

각 셀은 자기 일이 끝나는 즉시 다음 장을 받는다. 특히 **로봇팔은 JBR-201 에
패널을 넘기는 순간 바로 다음 장을 투입한다** — JBR 이 끝나기를 기다리지
않는다. 셀 사이 축적구간(JB-201, 4,900 mm)이 한 장을 물고 있어 이 중첩이
성립하며, 그래서 라인 택트는 종단 체류시간이 아니라 병목 셀의 점유시간이다.

* 투입부(FL/LFT/BFC/RB-101 → PT-101 → JB-201 인계) `INFEED_S`
* JBR-201 정션박스·케이블 제거 `JBR_S` ← **병목**
* AFR-101 이후 (프레임 분리 → CV-102 → SG-301 → GI-301/302 → GBR-301) `AFR_S`
* 전손 배출은 투입부만 `INFEED_REJECT_S` 쓰고 병목을 비켜간다.

번들 인코딩 — 한 글자가 한 장이다.

* ``U`` 정상·유리면 위 → BFC 180° 반전 후 투입, R-A 적재
* ``D`` 정상·유리면 아래 → 반전 생략, R-A 적재
* ``u``/``d`` 유리 깨짐(같은 방향) → 그대로 투입, **R-B** 적재
* ``X`` 전손 → 투입 비전 리젝트

도면(`docs/drawings/pv-preprocess-plant.html`)의 CAMPAIGN 리터럴이 이 값과
어긋나면 `tests/test_pv_preprocess.py` 가 잡는다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 투입부 점유 (s) — 픽업·판정·반전·로봇 투입·정렬·인계까지
INFEED_S = 40.0

#: JBR-201 점유 (s) — 라인 병목
JBR_S = 45.0

#: AFR-101 이후 후단 점유 (s) — 프레임 분리·이송·연마·검사·버퍼 적재
AFR_S = 39.03

#: 전손 배출이 투입부만 쓰는 시간 (s) — 픽업·판정·반전 생략 하강·로봇 랙 배출·복귀
INFEED_REJECT_S = 15.0

#: JBR 진입 후 스토퍼·측면 정렬이 작동하기까지 (s).
#: 영상 스테이지 "JBR-201 · 스토퍼·측면 정렬" 이 48.0 s 에 시작하고 JBR 진입이 40.0 s 이므로 8.0 s.
JBR_STOPPER_OFFSET_S = 8.0

#: 축적구간 JB-201 길이 (mm) 와 그것이 함의하는 이송 속도.
#: 스토퍼까지 4,900 mm 를 8.0 s 에 가므로 612.5 mm/s 다.
ACCUMULATOR_MM = 4900.0
PANEL_LENGTH_MM = 2500.0


def transfer_speed_mm_s() -> float:
    """이송 속도 — 스토퍼 오프셋이 함의하는 값. 새로 정하지 않는다."""
    return ACCUMULATOR_MM / JBR_STOPPER_OFFSET_S


def accumulator_clear_s() -> float:
    """앞 장의 꼬리가 축적구간 입구를 벗어나는 시각 (s).

    종전에는 **스토퍼가 물릴 때까지(8.0 s)** 기다려 다음 장을 놓았다. 그러나
    다음 장이 들어와도 되는 조건은 스토퍼가 아니라 **입구가 비었는가**이고,
    정렬은 축적구간이 물고 있는 동안 끝난다. 인터록을 하류 확인이 아니라
    입구 비움에 걸면 그 차이만큼 대기가 사라진다.
    """
    return round(PANEL_LENGTH_MM / transfer_speed_mm_s(), 2)


#: 후단 인계 설계 여유 (장/h). 유리제거셀 능력에서 이만큼을 남긴다.
#: §21 에서 정한 값 그대로다 — **줄이지 않았다.**
#:
#: 이 한 줄이 성능률과 인계 안전여유를 맞바꾸는 자리다. 0.5 로 줄이면 성능률이
#: 0.925 → 0.951 로 올라 세계 최상급 기준을 넘지만, 후단이 조금만 처져도 버퍼가
#: 차고 라인이 선다. 점수를 위해 안전여유를 태우는 것은 개선이 아니므로 그대로
#: 두고, 성능률 격차는 **후단 능력을 올려야 닫힌다**고 적는다(발주처 결정 항목).
HANDOFF_MARGIN_PER_H = 2.4


def downstream_limited_takt_s() -> float:
    """후단이 받을 수 있는 속도에서 나오는 택트 (s).

    앞단이 아무리 빨라도 유리제거셀이 못 받으면 버퍼가 차고 결국 선다.
    그래서 페이스의 상한은 후단 능력이지 앞단 기구가 아니다.
    """
    # `handoff.summary()` 를 부르면 순환한다 — 그것이 다시 캠페인을 읽기 때문이다.
    # 필요한 것은 후단 **능력**뿐이고 그 값은 캠페인과 무관하다.
    from . import handoff
    allowed_ra = handoff.downstream_rate().line_per_h - HANDOFF_MARGIN_PER_H
    return round(3600.0 / (allowed_ra / normal_ratio()), 2)


def pace_offset_s() -> float:
    """페이스를 세 제약에서 낸다면 얼마가 되는가 (s) — **분석용이다.**

    ① 축적구간 입구 비움 4.08  ② 병목 셀 점유  ③ 후단 인계 능력

    지금 라인은 ①이 아니라 스토퍼 확인(8.0 s)으로 다음 장을 놓는다. ①로 바꾸면
    앞단은 44.08 s 로 돌 수 있지만, 그래도 후단이 더 늦으므로 실제 페이스는
    안 빨라진다 — **묶고 있는 것은 인터록이 아니라 유리제거셀이다.**

    그래서 지금은 택트를 건드리지 않는다. 후단 능력이 올라가는 날 이 함수가
    얼마까지 당길 수 있는지 말해 준다.
    """
    return round(max(accumulator_clear_s(),
                     JBR_S - INFEED_S,
                     downstream_limited_takt_s() - INFEED_S), 2)


def normal_ratio() -> float:
    """R-A 로 가는 비율. 캠페인 구성에서 나온다 — 반입물이 바뀌면 페이스도 바뀐다."""
    rows = panels_by_pattern()
    return sum(1 for c in rows if c == "정상") / len(rows)


def panels_by_pattern() -> tuple[str, ...]:
    """번들 패턴에서 장별 상태만 뽑는다 (시뮬레이션 없이)."""
    out = []
    for _, _, pattern in BUNDLE_PATTERNS:
        for mark in pattern:
            out.append("전손" if mark == "X"
                       else ("유리 깨짐" if mark.islower() else "정상"))
    return tuple(out)


#: 방출 보류 (s). 0 이면 라인이 제 속도로 돈다. 후단이 못 따라올 때 이 값만
#: 키워 택트를 늘린다 — 셀 점유시간은 그대로 두고 로봇이 손을 늦게 떼는 것이다.
RELEASE_HOLD_S = 0.0

#: 팔레트 한 장당 매수
PALLET_PANELS = 30

#: 지게차 호출 임계 — 활성 리프트 잔량이 이 값이 되면 부른다.
#: 전환 임계가 아니다. 활성 리프트는 끝까지 쓰고, 비는 순간 대기 리프트가 받는다.
FORKLIFT_CALL_REMAINING = 2

#: 팔레트 교환 소요 (s) — 대기 리프트가 급전하는 동안 이뤄져 택트에 더해지지 않는다
PALLET_SWAP_S = 180.0

#: 판정 → 버퍼 캐리지. GBR-301 은 R-A·R-B·HOLD 캐리지를 갖고 있다.
BUFFER_OF = {"정상": "R-A", "유리 깨짐": "R-B", "전손": "—"}

#: 버퍼 캐리지 이름
BUFFER_LABELS = {"R-A": "정상 유리 버퍼", "R-B": "파손 유리 버퍼", "HOLD": "재검사 대기"}

#: 번들 구성. U/D=정상(위/아래), u/d=유리 깨짐, X=전손
BUNDLE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("1번 번들", "LFT-101A", "UDDUUDuDUDDXUDDUdUDDUUDDUdUDUD"),
    ("2번 번들", "LFT-101B", "DUUDdUDDUUDUDXUUDDUuDUDDUUDDUD"),
)


@dataclass(frozen=True)
class Panel:
    """캠페인 한 장과 각 셀의 점유 구간."""

    index: int          # 1…60 전체 순번
    bundle: int         # 1 | 2
    bundle_index: int   # 번들 안 순번 1…30
    lift: str
    face: str           # 'GLASS_UP' | 'GLASS_DOWN'
    condition: str      # '정상' | '유리 깨짐' | '전손'
    action: str         # '반전 투입' | '바이패스 투입' | '투입 리젝트'
    buffer: str         # 'R-A' | 'R-B' | '—'
    infeed_start: float
    infeed_end: float
    jbr_start: float    # 전손은 두 값 모두 infeed_end 로 둔다 (점유 없음)
    jbr_end: float
    afr_start: float
    afr_end: float

    @property
    def rejected(self) -> bool:
        return self.condition == "전손"

    @property
    def flips(self) -> bool:
        return self.action == "반전 투입"

    @property
    def done_s(self) -> float:
        return self.infeed_end if self.rejected else self.afr_end


@dataclass(frozen=True)
class ForkliftEvent:
    """지게차 동작 하나."""

    at_s: float
    lift: str
    kind: str           # '초기 적재' | '호출' | '팔레트 교환'
    note: str


def _decode(mark: str) -> tuple[str, str]:
    if mark == "X":
        return "GLASS_UP", "전손"
    face = "GLASS_UP" if mark.upper() == "U" else "GLASS_DOWN"
    return face, "유리 깨짐" if mark.islower() else "정상"


def panels(hold_s: float = RELEASE_HOLD_S) -> tuple[Panel, ...]:
    """60장 로스터 — 셀별 점유를 이산사건으로 잡는다.

    **다음 장 투입 시점은 앞 장의 JBR 스토퍼·자세교정이 작동하는 순간이다.**
    그때 축적구간이 비고 정렬이 확정되므로 로봇이 바로 다음 장을 내려놓을 수
    있다. 이 규칙이 라인 택트를 정한다 — 영상의 반복 주기와 같은 값이다.
    """
    rows: list[Panel] = []
    infeed_free = jbr_free = afr_free = 0.0
    release_gate = 0.0
    index = 0
    for bundle_no, (_, lift, pattern) in enumerate(BUNDLE_PATTERNS, start=1):
        for slot, mark in enumerate(pattern, start=1):
            face, condition = _decode(mark)
            index += 1
            # 앞 장이 축적구간 입구를 비우면 다음 장을 내려놓는다. 종전에는
            # 스토퍼가 물릴 때까지 기다렸고, 그 차이가 인터록 대기였다.
            start = max(infeed_free, release_gate)
            if condition == "전손":
                end = start + INFEED_REJECT_S
                infeed_free = end
                rows.append(Panel(index, bundle_no, slot, lift, face, condition,
                                  "투입 리젝트", BUFFER_OF[condition],
                                  round(start, 2), round(end, 2), round(end, 2),
                                  round(end, 2), round(end, 2), round(end, 2)))
                continue
            end = start + INFEED_S
            infeed_free = end
            jbr_start = max(end, jbr_free)
            jbr_end = jbr_start + JBR_S
            jbr_free = jbr_end
            release_gate = jbr_start + JBR_STOPPER_OFFSET_S + hold_s
            afr_start = max(jbr_end, afr_free)
            afr_end = afr_start + AFR_S
            afr_free = afr_end
            action = "반전 투입" if face == "GLASS_UP" else "바이패스 투입"
            rows.append(Panel(index, bundle_no, slot, lift, face, condition, action,
                              BUFFER_OF[condition], round(start, 2), round(end, 2),
                              round(jbr_start, 2), round(jbr_end, 2),
                              round(afr_start, 2), round(afr_end, 2)))
    return tuple(rows)


def forklift_events() -> tuple[ForkliftEvent, ...]:
    """지게차 동작 — 초기 두 곳 투입, 그다음은 비는 즉시 재투입."""
    events = [
        ForkliftEvent(0.0, "LFT-101A", "초기 적재", "1번 번들 30장 · 우선 급전"),
        ForkliftEvent(0.0, "LFT-101B", "초기 적재", "2번 번들 30장 · 대기"),
    ]
    rows = panels()
    for bundle_no, (_, lift, pattern) in enumerate(BUNDLE_PATTERNS, start=1):
        mine = [p for p in rows if p.bundle == bundle_no]
        call = mine[len(pattern) - FORKLIFT_CALL_REMAINING - 1]
        events.append(ForkliftEvent(
            call.infeed_end, lift, "호출",
            f"잔량 {FORKLIFT_CALL_REMAINING}장 — 다음 팔레트 대기 위치로"))
        events.append(ForkliftEvent(
            mine[-1].infeed_end, lift, "팔레트 교환",
            f"빈 팔레트 반출 후 새 번들 투입 ({PALLET_SWAP_S:.0f} s, 대기 리프트가 급전 중)"))
    return tuple(sorted(events, key=lambda e: (e.at_s, e.lift)))


def remaining_after(index: int) -> dict[str, int]:
    """index 장을 소비한 뒤 리프트별 잔량."""
    counts = {lift: PALLET_PANELS for _, lift, _ in BUNDLE_PATTERNS}
    for panel in panels()[:index]:
        counts[panel.lift] -= 1
    return counts


def buffer_counts() -> dict[str, int]:
    """캐리지별 적재 매수 — 분류가 정확한지 보는 값."""
    counts = {"R-A": 0, "R-B": 0}
    for panel in panels():
        if panel.buffer in counts:
            counts[panel.buffer] += 1
    return counts


def condition_counts() -> dict[str, int]:
    counts = {"정상": 0, "유리 깨짐": 0, "전손": 0}
    for panel in panels():
        counts[panel.condition] += 1
    return counts


def peak_wip() -> int:
    """동시에 라인 위에 있는 최대 매수 — 연속 운전이 실제로 겹치는지."""
    marks: list[tuple[float, int]] = []
    for panel in panels():
        marks.append((panel.infeed_start, 1))
        marks.append((panel.done_s, -1))
    marks.sort()
    live = peak = 0
    for _, delta in marks:
        live += delta
        peak = max(peak, live)
    return peak


def grm_equivalent_s() -> float:
    """유리제거셀의 **장당 환산** 점유 (s).

    GRM 은 R-A(정상 유리)만 받는다. 그 셀의 한 장 주기는 3600/능력 이지만,
    라인 한 장당으로 환산하려면 R-A 로 가는 비율을 곱해야 한다 — 깨진 유리와
    전손은 이 셀을 지나지 않기 때문이다.
    """
    from . import handoff
    return round(3600.0 / handoff.downstream_rate().line_per_h * normal_ratio(), 2)


def cell_occupancy_s() -> tuple[tuple[str, float], ...]:
    """셀별 장당 점유 (s). **유리제거셀이 여기 들어 있어야 한다.**

    §21 에서 GRM-401 을 플랜트 안으로 들여왔는데 병목 후보에는 안 들어가
    있었다. 그래서 이상 택트가 JBR 45.0 s 로 잡혔고, 실제로 라인을 묶는 것이
    무엇인지 가려져 있었다.
    """
    return (("투입부", INFEED_S), ("JBR-201", JBR_S), ("AFR-101 후단", AFR_S),
            ("GRM-401 유리제거", grm_equivalent_s()))


def ideal_takt_s() -> float:
    """이상 택트 — 가장 느린 셀의 장당 점유. 성능률의 분자다."""
    return max(row[1] for row in cell_occupancy_s())


def bottleneck() -> str:
    """가장 오래 점유하는 셀 — 택트를 정하는 자리."""
    return max(cell_occupancy_s(), key=lambda row: row[1])[0]


def release_takt_s(hold_s: float = RELEASE_HOLD_S) -> float:
    """다음 장 투입 주기 — 앞 장이 JBR 에 들어가 스토퍼가 작동하기까지.

    영상의 반복 주기와 같은 값이라 화면과 계산이 어긋나지 않는다.
    """
    return INFEED_S + JBR_STOPPER_OFFSET_S + hold_s


def summary(hold_s: float = RELEASE_HOLD_S) -> dict[str, float]:
    rows = panels(hold_s)
    processed = [p for p in rows if not p.rejected]
    run_s = max(p.done_s for p in rows)
    conditions = condition_counts()
    return {
        "panels": len(rows),
        "normal": conditions["정상"],
        "cracked": conditions["유리 깨짐"],
        "scrap": conditions["전손"],
        "flipped": sum(1 for p in processed if p.flips),
        "bypassed": sum(1 for p in processed if not p.flips),
        "run_s": round(run_s, 2),
        "run_min": round(run_s / 60.0, 1),
        "throughput_per_h": round(len(processed) / (run_s / 3600.0), 1),
        "takt_s": round((max(p.jbr_end for p in processed)
                         - min(p.jbr_start for p in processed)) / len(processed), 2),
        "peak_wip": peak_wip(),
        "forklift_loads": sum(1 for e in forklift_events()
                              if e.kind in ("초기 적재", "팔레트 교환")),
    }


def bundle_condition_counts() -> tuple[dict[str, int], ...]:
    """번들별 판정 매수 — 요청은 1번 유리깨짐 3장, 2번 2장이다."""
    out = []
    for bundle_no, _ in enumerate(BUNDLE_PATTERNS, start=1):
        counts = {"정상": 0, "유리 깨짐": 0, "전손": 0}
        for panel in panels():
            if panel.bundle == bundle_no:
                counts[panel.condition] += 1
        out.append(counts)
    return tuple(out)
