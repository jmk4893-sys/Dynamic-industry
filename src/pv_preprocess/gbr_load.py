"""GBR-301 슬롯 적재기 사이클 — 버퍼가 라인을 따라오는가.

이 셀에는 **점유시간을 내는 모델이 없었다.** 서보 세 축(`AXIS-GBR-X` 수평셔틀
주행 · `AXIS-GBR-LF` 슬롯 로더 승강 · `AXIS-GBR-FK` 슬롯 로더 포크)은 일람에
있고 GA 시트가 행정을 다 적어 두었는데, 그것들이 한 장을 넣는 데 몇 초가 걸리는지
아무도 계산하지 않았다. 그래서 두 가지가 가려져 있었다.

1. **버퍼가 병목 후보에 없었다.** `campaign.cell_occupancy_s()` 는 투입부·JBR·
   AFR 후단·GRM 넷만 봤다 — §21 에서 GRM 이 빠져 있어 이상 택트가 잘못 잡혔던
   것과 같은 종류의 공백이다. 버퍼가 택트보다 느리면 라인이 서는데 그것을
   확인할 자리가 없었다.
2. **영상의 적재 시간에 근거가 없었다.** 통합 설계도는 후단 마지막 칸 10.3 s 중
   진도 .92…1.0 (0.82 s)을 적재에 준다. 그 값이 어디서 왔는지 적힌 곳이 없다.

행정은 **전부 GA 시트 `PV-GBR-301-GA-5201` 과 3D 형상에서 온다.** 새로 정한 것은
이송 프로파일 셋뿐이고, 그 셋은 벤더 확정 항목으로 밝혀 둔다 — `campaign.SG_PASS_MM_S`
와 같은 취급이다. 값이 바뀌어도 결론(택트 안에 들어온다)이 뒤집히려면 두 배 이상
느려져야 한다.

**영상은 여기 맞춰 고치지 않는다.** 필름의 시각표는 종단 체류 130.03 s 를 나누는
연출이고, 그것을 실제 사이클로 늘리면 다른 영상이 된다. 대신 두 값의 격차를
`compression()` 으로 드러내고 시험이 그것을 기록한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ── 행정 (mm) — GA 시트와 3D 형상에서 온다 ───────────────────────────────

#: 데크 롤러 Z 분기 — 행 중심까지. 3D 의 행 좌표(`Kn={A:-2.1,B:2.1}`) 다.
#:
#: **GA 시트는 이 값을 2,350 으로 적는다** (흐름 2번 「데크 롤러 Z 분기 2,350」,
#: 캐리지 배치도 z ∓2,350). 3D 는 ∓2,100 이고 둘 다 가드 ∓3,550 안에 들어와
#: 어느 검사도 잡지 않는다 — 250 mm 갈린 채로 남아 있다. 사이클은 **영상과
#: 견주는 값**이므로 3D 쪽을 쓰고, 갈린 것은 시험이 기록한다.
BRANCH_MM = 2100.0

#: 픽업면 (mm) — 셔틀 데크 이송면. `layout.LINE_TRANSFER_MM` 위 3 mm 가 유리 상면.
PICKUP_MM = 953.0

#: 슬롯 높이 (mm) — GA 시트 `levels` 의 SLOT-1 / SLOT-25.
SLOT_FIRST_MM, SLOT_LAST_MM = 340.0, 2236.0

#: 콤포크 픽업 들어올림 (mm) — GA 흐름 3번 「콤포크 +15 픽업」.
FORK_PICK_MM = 15.0

#: 포크 X 신장 (mm) — GA 흐름 4번 「포크 X+ 3,200 신장·선단받이 결합」.
FORK_STROKE_MM = 3200.0

#: 슬롯 레일 안착 소하강 (mm) — GA 흐름 5번 「소하강 12 레일 안착」.
SET_DOWN_MM = 12.0

# ── 이송 프로파일 — **여기만 새로 정한 값이다 (벤더 확정 항목)** ─────────
#: 서보 이송 속도 (mm/s). 유리 한 장을 문 콤포크·마스트·데크 롤러에 공통으로 쓴다.
SERVO_V_MM_S = 500.0
#: 서보 가감속 (mm/s²).
SERVO_A_MM_S2 = 800.0
#: 정지마다 드는 정착·확인 (s) — 도킹핀·슬롯 점유·돌출 센서를 읽는 시간.
STOP_SETTLE_S = 0.3


@dataclass(frozen=True)
class Step:
    """사이클 한 동작."""

    tag: str
    axis: str
    stroke_mm: float
    seconds: float


def move_s(stroke_mm: float,
           v_mm_s: float = SERVO_V_MM_S,
           a_mm_s2: float = SERVO_A_MM_S2) -> float:
    """사다리꼴 프로파일 이동 시간 (s). 짧으면 삼각형으로 떨어진다."""
    if stroke_mm <= 0:
        return 0.0
    if stroke_mm <= v_mm_s ** 2 / a_mm_s2:          # 정속 구간이 없다
        return round(2 * math.sqrt(stroke_mm / a_mm_s2), 4)
    return round(v_mm_s / a_mm_s2 + stroke_mm / v_mm_s, 4)


def lift_mm(slot: int = 25) -> float:
    """픽업면에서 그 슬롯까지의 승강 행정 (mm). 25 번이 가장 멀다."""
    if not 1 <= slot <= 25:
        raise ValueError("슬롯은 1…25 다")
    pitch = (SLOT_LAST_MM - SLOT_FIRST_MM) / 24.0
    return abs(SLOT_FIRST_MM + pitch * (slot - 1) - PICKUP_MM)


def steps(slot: int = 25) -> tuple[Step, ...]:
    """한 장을 넣는 동작 순서 — GA 시트 흐름 2…5 와 복귀.

    직렬이다. 포크가 신장한 채로 마스트가 움직이면 2.9 m 외팔보가 슬롯 레일을
    긁으므로 겹칠 수 없고(그래서 TG-813 선단받이가 있다), Z 분기는 유리가
    데크 위에 있을 때만 가능하다.
    """
    lift = lift_mm(slot)
    plan = (
        ("데크 롤러 Z 분기 (행 중심)", "AXIS-GBR-X", BRANCH_MM),
        ("콤포크 픽업 들어올림", "AXIS-GBR-LF", FORK_PICK_MM),
        ("마스트 승강 (슬롯 정렬)", "AXIS-GBR-LF", lift),
        ("포크 X 신장·선단받이 결합", "AXIS-GBR-FK", FORK_STROKE_MM),
        ("소하강 레일 안착", "AXIS-GBR-LF", SET_DOWN_MM),
        ("포크 복귀", "AXIS-GBR-FK", FORK_STROKE_MM),
        ("마스트 픽업면 복귀", "AXIS-GBR-LF", lift + FORK_PICK_MM - SET_DOWN_MM),
    )
    return tuple(Step(tag, axis, mm, round(move_s(mm) + STOP_SETTLE_S, 4))
                 for tag, axis, mm in plan)


def cycle_s(slot: int = 25) -> float:
    """한 장 적재 사이클 (s). 기본값은 **가장 먼 슬롯**이라 최악값이다."""
    return round(sum(s.seconds for s in steps(slot)), 2)


def line_equivalent_s() -> float:
    """라인 한 장당 환산 점유 (s).

    전손은 투입부에서 걸러져 이 셀에 오지 않으므로, 라인 한 장당으로 환산할 때는
    실제로 버퍼를 지나는 비율을 곱한다 — `campaign.grm_equivalent_s()` 와 같은 규약이다.
    """
    from . import campaign
    rows = campaign.panels_by_pattern()
    passing = sum(1 for c in rows if c != "전손") / len(rows)
    return round(cycle_s() * passing, 2)


def takt_margin_s() -> float:
    """택트에서 사이클을 뺀 여유 (s). 음수면 **버퍼가 라인을 못 따라온다.**"""
    from . import campaign
    return round(campaign.release_takt_s() - line_equivalent_s(), 2)


def keeps_up() -> bool:
    """버퍼가 택트 안에 들어오는가."""
    return takt_margin_s() > 0


def film_load_s() -> float:
    """통합 설계도 영상이 적재에 준 시간 (s).

    후단 마지막 칸(`Cr`…`Lr`)의 진도 .92…1.0 이다. 그 칸 길이는 AFR 후단 점유에서
    나오므로 여기서 리터럴로 다시 적지 않는다.
    """
    from . import campaign
    span = campaign.AFR_S - FILM_LAST_STAGE_START_S
    return round(span * (1.0 - FILM_LOAD_FROM_V), 3)


#: 영상의 후단 마지막 칸이 시작하는 시각 (s, 셀 로컬) — 도면의 `Cr` 이다.
FILM_LAST_STAGE_START_S = 28.7319148936
#: 그 칸 안에서 적재가 시작하는 진도 — 도면의 `X` 이징이 서는 자리.
FILM_LOAD_FROM_V = 0.92


def compression() -> float:
    """영상이 적재를 몇 배로 압축했는가 — 사이클 ÷ 영상 시간."""
    return round(cycle_s() / film_load_s(), 1)


def summary() -> dict[str, float | bool]:
    return {
        "cycle_s": cycle_s(),
        "cycle_best_s": cycle_s(1),
        "line_equivalent_s": line_equivalent_s(),
        "takt_margin_s": takt_margin_s(),
        "keeps_up": keeps_up(),
        "film_load_s": film_load_s(),
        "compression": compression(),
    }
