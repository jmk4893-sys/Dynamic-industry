"""60장 연속 투입 캠페인 — 번들 2개, 파손품 혼입, 방향 혼재.

한 장 추적(124.03 s 종단 체류)만으로는 연속 운전이 보이지 않는다. 이 모듈은
팔레트 두 개(각 30장)를 실제로 흘렸을 때 무엇이 언제 일어나는지를 만든다.

시나리오 (요청 그대로)

* 지게차가 **두 곳(LFT-101A·B)에 먼저 투입**한다.
* 활성 리프트가 비면 **바로 그 자리에 새 팔레트를 투입**한다. 잔량
  `FORKLIFT_CALL_REMAINING` 장에서 지게차를 호출해 두므로 교환이 라인을
  세우지 않는다 — 대기 리프트가 이어받는다.
* 1번 번들은 **파손 3장**, 2번 번들은 **파손 2장**. 두 번들 모두 유리면
  방향이 뒤섞여 있어 장마다 반전 여부가 갈린다.

시간 모델

* 통과품은 병목인 JBR-201 택트 `TAKT_S`(45 s)를 점유한다. 화면의 124.03 s 는
  종단 체류시간이지 택트가 아니다 — 셀 사이 축적구간이 공정을 중첩한다.
* 파손품은 투입 비전(VS-101A/B)에서 걸러져 BFC 로 들어가지 않으므로 JBR 을
  점유하지 않는다. 투입부만 `INFEED_REJECT_S` 동안 쓴다.
* 팔레트 교환은 대기 리프트가 급전하는 동안 이뤄지므로 택트에 더해지지 않는다.

번들 인코딩 — 한 글자가 한 장이다.

* ``U`` 유리면 위(정상) → BFC 180° 반전 후 투입
* ``D`` 유리면 아래(정상) → 반전 생략(바이패스)
* ``u``/``d`` 같은 방향의 **파손품** → 투입 비전 판정으로 리젝트 랙 배출

도면(`docs/drawings/pv-preprocess-plant.html`)의 CAMPAIGN_* 리터럴이 이 값과
어긋나면 `tests/test_pv_preprocess.py` 가 잡는다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 병목(JBR-201) 택트 (s) — 통과품 한 장이 라인을 점유하는 시간
TAKT_S = 45.0

#: 파손품이 투입부만 점유하는 시간 (s) — 픽업·판정·리젝트 랙 배출·복귀
INFEED_REJECT_S = 15.0

#: 팔레트 한 장당 매수
PALLET_PANELS = 30

#: 지게차 호출 임계 — 활성 리프트 잔량이 이 값이 되면 부른다.
#: 전환 임계가 아니다. 활성 리프트는 끝까지 쓰고, 비는 순간 대기 리프트가 받는다.
FORKLIFT_CALL_REMAINING = 2

#: 팔레트 교환 소요 (s) — 대기 리프트가 급전하는 동안 이뤄져 택트에 더해지지 않는다
PALLET_SWAP_S = 180.0

#: 번들 구성. 대문자=정상, 소문자=파손, U=유리면 위(반전), D=유리면 아래(바이패스)
BUNDLE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("1번 번들", "LFT-101A", "UDDUUDuDUDDUUDDUdUDDUUDDUdUDUD"),
    ("2번 번들", "LFT-101B", "DUUDdUDDUUDUDDUUDDUuDUDDUUDDUD"),
)


@dataclass(frozen=True)
class Panel:
    """캠페인 한 장."""

    index: int          # 1…60 전체 순번
    bundle: int         # 1 | 2
    bundle_index: int   # 번들 안 순번 1…30
    lift: str
    face: str           # 'GLASS_UP' | 'GLASS_DOWN'
    broken: bool
    action: str         # '반전 투입' | '바이패스 투입' | '투입 리젝트'
    start_s: float
    end_s: float

    @property
    def flips(self) -> bool:
        return self.action == "반전 투입"


@dataclass(frozen=True)
class ForkliftEvent:
    """지게차 동작 하나."""

    at_s: float
    lift: str
    kind: str           # '초기 적재' | '호출' | '팔레트 교환'
    note: str


def _decode(mark: str) -> tuple[str, bool]:
    face = "GLASS_UP" if mark.upper() == "U" else "GLASS_DOWN"
    return face, mark.islower()


def panels() -> tuple[Panel, ...]:
    """60장 로스터와 각 장의 점유 구간."""
    rows: list[Panel] = []
    clock = 0.0
    index = 0
    for bundle_no, (_, lift, pattern) in enumerate(BUNDLE_PATTERNS, start=1):
        for slot, mark in enumerate(pattern, start=1):
            face, broken = _decode(mark)
            if broken:
                action, span = "투입 리젝트", INFEED_REJECT_S
            elif face == "GLASS_UP":
                action, span = "반전 투입", TAKT_S
            else:
                action, span = "바이패스 투입", TAKT_S
            index += 1
            rows.append(Panel(index, bundle_no, slot, lift, face, broken,
                              action, round(clock, 1), round(clock + span, 1)))
            clock += span
    return tuple(rows)


def forklift_events() -> tuple[ForkliftEvent, ...]:
    """지게차 동작 — 초기 두 곳 투입, 그다음은 비는 즉시 재투입."""
    events = [
        ForkliftEvent(0.0, "LFT-101A", "초기 적재", "1번 번들 30장 · 우선 급전"),
        ForkliftEvent(0.0, "LFT-101B", "초기 적재", "2번 번들 30장 · 대기"),
    ]
    rows = panels()
    for bundle_no, (_, lift, pattern) in enumerate(BUNDLE_PATTERNS, start=1):
        in_bundle = [p for p in rows if p.bundle == bundle_no]
        call = in_bundle[len(pattern) - FORKLIFT_CALL_REMAINING - 1]
        last = in_bundle[-1]
        events.append(ForkliftEvent(
            call.end_s, lift, "호출",
            f"잔량 {FORKLIFT_CALL_REMAINING}장 — 다음 팔레트 대기 위치로"))
        events.append(ForkliftEvent(
            last.end_s, lift, "팔레트 교환",
            f"빈 팔레트 반출 후 새 번들 투입 ({PALLET_SWAP_S:.0f} s, 대기 리프트가 급전 중)"))
    return tuple(sorted(events, key=lambda e: (e.at_s, e.lift)))


def active_lift_at(index: int) -> str:
    """전체 순번 index(1-based)의 급전 리프트."""
    return panels()[index - 1].lift


def remaining_after(index: int) -> dict[str, int]:
    """index 장을 소비한 뒤 리프트별 잔량."""
    counts = {lift: PALLET_PANELS for _, lift, _ in BUNDLE_PATTERNS}
    for panel in panels()[:index]:
        counts[panel.lift] -= 1
    return counts


def summary() -> dict[str, float]:
    rows = panels()
    passed = [p for p in rows if not p.broken]
    run_s = rows[-1].end_s
    return {
        "panels": len(rows),
        "broken": len(rows) - len(passed),
        "flipped": sum(1 for p in passed if p.flips),
        "bypassed": sum(1 for p in passed if not p.flips),
        "run_s": run_s,
        "run_min": round(run_s / 60.0, 1),
        "throughput_per_h": round(len(passed) / (run_s / 3600.0), 1),
        "forklift_loads": sum(1 for e in forklift_events()
                              if e.kind in ("초기 적재", "팔레트 교환")),
    }


def bundle_broken_counts() -> tuple[int, ...]:
    """번들별 파손 매수 — 요청은 1번 3장, 2번 2장이다."""
    return tuple(sum(1 for c in pattern if c.islower())
                 for _, _, pattern in BUNDLE_PATTERNS)
