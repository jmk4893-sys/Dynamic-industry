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

# ── 행 중심 — 두 문서가 250 mm 갈려 있던 자리 ────────────────────────────
#
# GA 시트는 ∓2,350(캐리지·마스트·포크 배치와 흐름 2번 문구), 3D 는 ∓2,100 이었다.
# 어느 검사도 안 잡았는데, **재 보니 둘 다 무언가를 깨고 있었다.**
#
#   R=2,350  외측 마스트 ↔ 가드 기둥 여유 0 mm · 유리가 데크 롤러 밖으로 170 mm
#   R=2,100  내측 마스트가 HOLD 마스트를 100 mm 파고든다 (3D 실측)
#
# 그래서 값을 고르는 대신 **창을 낸다.** 세 제약이 R 을 양쪽에서 조인다.
#
#   ① 내측 마스트가 HOLD 마스트를 비켜야 한다     R ≥ 2,250
#   ② 외측 마스트가 가드 기둥을 비켜야 한다        R ≤ 2,300
#   ③ 분기 끝에서 유리가 데크 롤러 위에 다 있어야   롤러가 R+700 까지 와야 한다
#
# ①②가 [2,250, 2,300] 을 남기고, ③은 그 값에 맞춰 **데크 롤러를 늘리라고**
# 말한다 (종전 ∓2,880 은 R ≤ 2,180 만 받쳐 창과 겹치지 않는다). 상한을 잡는다.

#: 가드 기둥 중심·단면 (mm) — 3D 실측. afr·post 와 같은 ∓3,500 포락선 선이다.
GUARD_Z_MM, GUARD_POST_MM = 3500.0, 100.0
#: HOLD 행 마스트 중심 (mm) 과 마스트 z 단면 — GA 시트 MSO-H/MSI-H.
HOLD_MAST_Z_MM, MAST_SECTION_MM = 1000.0, 200.0
#: 마스트 X 깊이와 전고 (mm) — GA 시트 `[160, 2650, 200]`. 포크가 뻗는 X 가 약축이다.
MAST_DEPTH_MM, MAST_TOP_MM = 160.0, 2650.0
#: 행 중심에서 트윈마스트까지 (mm) — GA 시트가 두 문서에서 같게 쓰는 값이다.
MAST_OFFSET_MM = 1000.0
#: 유리 폭(단변, z)과 장변(x) (mm) — `kinematics.PANEL_MM` 과 같은 값이다.
GLASS_W_MM, GLASS_L_MM = 1400.0, 2500.0
#: 부재 사이 최소 여유 (mm). 0 을 쓰면 «닿아 있다»가 설계값이 된다.
MIN_CLEARANCE_MM = 50.0

# ── 선반과 포크가 같은 20 mm 를 놓고 다투고 있었다 ──────────────────────
#
# 슬롯 선반 레일은 z ±730 · 폭 55 라 ±702.5…757.5 를 차지했고, 유리 가장자리는
# ±700 이다. **유리가 어느 레일에도 안 닿는다** — 2.5 mm 가 비어 있었다. 캐리지
# 밑면이 80 mm 떠 있던 REV.47 과 같은 종류의 끊긴 하중 경로인데, 이번에는
# 강체 적분을 돌려야 보인다 (`gbr_dynamics` · `pv-gbr-physics.html`).
#
# 레일을 유리 밑으로 들이면 콤포크와 부딪친다. 콤포크는 ±620 · 폭 120 이라
# ±560…680 을 쓰고, 레일이 유리를 물려면 ±700 안쪽으로 와야 하는데 그 사이에
# 남는 것은 **20 mm** 뿐이다. 둘 다 그 띠에 못 들어간다.
#
# 그래서 셋을 한 줄로 세운다 — 기둥(하중 경로) → 레일(유리 받침) → 포크(들어감).
#
#   ① 레일 바깥은 기둥에 물려야 한다        레일 바깥 ≥ 기둥 안쪽 면
#   ② 레일 안쪽은 유리를 `SHELF_BEARING_MM` 만큼 물어야 한다
#   ③ 포크 바깥면은 레일 안쪽에서 최소 여유만큼 물러나야 한다
#
# ②③이 포크 중심의 상한을 낸다. 하한은 유리 굽힘인데 3.2 mm 유리는 ±410 (등모멘트
# 최적)까지 내려가도 2.7 MPa 라 구속이 아니다 — 그래서 **상한을 잡는다.** 가장자리에
# 가까울수록 안착에서 지지선이 덜 움직이고 유리가 덜 흔들린다.

#: 캐리지 기둥 중심·단면 (mm) — 3D 실측 (`[.1,2.32,.1]` at z ±760).
POST_Z_MM, POST_MM = 760.0, 100.0
#: 밀폐형 캐리지 측면 패널 중심·두께 (mm) — 3D 실측 (`[2.7,2.18,.035]` at z ±820).
SKIN_Z_MM, SKIN_T_MM = 820.0, 35.0
#: 슬롯 선반이 유리를 무는 폭 (mm) — 부재 사이 최소 여유와 같은 값을 쓴다.
SHELF_BEARING_MM = MIN_CLEARANCE_MM


def shelf_edges_mm() -> tuple[float, float]:
    """슬롯 선반 레일의 (안쪽, 바깥쪽) z (mm) — ①②가 그대로 낸다.

    바깥은 기둥 바깥까지 가되 밀폐형 캐리지의 측면 패널을 뚫지는 못한다. 패널은
    같은 캐리지 골조에 붙은 외피라 **맞닿는 것이 접합**이다 — 움직이는 부재
    사이의 여유(`MIN_CLEARANCE_MM`)를 여기에 또 쓰지 않는다.
    """
    return (GLASS_W_MM / 2 - SHELF_BEARING_MM,
            min(POST_Z_MM + POST_MM / 2, SKIN_Z_MM - SKIN_T_MM / 2))


#: 선반 레일 중심과 z 폭 (mm) — 위 두 모서리에서 나온다.
SHELF_Z_MM = sum(shelf_edges_mm()) / 2
SHELF_W_MM = shelf_edges_mm()[1] - shelf_edges_mm()[0]
#: 선반 레일 두께 (mm) — 3D 실측.
SHELF_T_MM = 25.0

#: 콤포크 길이와 z 폭 (mm) — GA 시트 `[2600, 95, 120]`.
FORK_LEN_MM, FORK_W_MM = 2600.0, 120.0
#: 텔레스코픽 단 수 — GA 「2 단 텔레스코픽 콤포크」.
FORK_STAGES = 2
#: 콤포크와 **다른 슬롯의 유리** 사이 최소 여유 (mm).
#:
#: 부재 사이의 50(`MIN_CLEARANCE_MM`)을 여기에 쓰면 슬롯 피치 79 안에 어떤 포크도
#: 안 들어간다 — 그 여유를 지키려면 피치가 125 는 돼야 하고 슬롯이 25 에서 16 으로
#: 준다. 25 슬롯을 지키는 쪽을 골랐고, 그 대가가 이 값이다. 벤더 확정 항목이다.
GLASS_CLEARANCE_MM = 5.0

#: 콤포크 깊이 (mm) — **슬롯 피치가 정한다.**
#:
#: GA 는 95 를 적었는데 그것은 슬롯 피치 79 보다 크다. 포크는 목표 슬롯에 들어가
#: 유리를 놓고 빠지는데, 그 사이 포크 몸통이 **한 칸 아래 유리** 위를 지나야 한다.
#: 남는 높이는 피치에서 유리 두께·여유·놓아 주는 하강만큼을 뺀 것이고, 거기에
#: 선단 처짐까지 들어가야 한다 (`gbr_dynamics.fork_depth_window_mm()`):
#:
#:     깊이 + 선단처짐 ≤ 피치 − 유리두께 − 여유 − 정지오차
#:
#: 95 는 처짐 없이도 이미 넘는다. 2 단 텔레스코픽으로 제대로 풀면(단 사이 겹침이
#: 1,000 mm 라 실제 외팔은 1,600 mm 다) 60 에서 처짐 3.1 mm · 응력 10.5 MPa 로
#: 창 안에 들어간다. `gbr_dynamics.fork_depth_ok()` 가 그것을 본다.
FORK_H_MM = 60.0


def fork_stage_travel_mm() -> float:
    """한 단이 미끄러져 나가는 거리 (mm) — 단들이 같이 나눠 낸다."""
    return FORK_STROKE_MM / FORK_STAGES


def fork_stage_spans_mm() -> tuple[tuple[float, float], ...]:
    """완전 신장에서 각 단이 차지하는 x 구간 (mm) — 접힌 자리에서 밀려 나간다."""
    step = fork_stage_travel_mm()
    lo = DECK_LEN_MM / 2 - FORK_LEN_MM / 2
    return tuple((lo + step * (k + 1), lo + FORK_LEN_MM + step * (k + 1))
                 for k in range(FORK_STAGES))


def fork_overlap_mm() -> tuple[float, float]:
    """밑단과 안단이 겹치는 x 구간 (mm) — 여기가 안단의 지지점 둘이다."""
    (_, base_hi), (inner_lo, _) = fork_stage_spans_mm()
    return inner_lo, base_hi


def fork_offset_max_mm() -> float:
    """③이 내는 콤포크 중심의 상한 (mm)."""
    return shelf_edges_mm()[0] - MIN_CLEARANCE_MM - FORK_W_MM / 2


#: 행 중심에서 콤포크까지 (mm) — 상한을 잡는다. 종전 620 은 선반과 겹쳤다.
FORK_OFFSET_MM = fork_offset_max_mm()


def fork_offset_ok() -> bool:
    return FORK_OFFSET_MM <= fork_offset_max_mm()


def fork_lines_mm() -> tuple[float, float]:
    """콤포크가 유리를 받치는 z 선 (mm)."""
    return -FORK_OFFSET_MM, FORK_OFFSET_MM


def shelf_bearing_lines_mm() -> tuple[float, float]:
    """슬롯 선반이 유리를 받치는 z 선 (mm) — 보수적으로 **안쪽 모서리**로 본다."""
    inner = shelf_edges_mm()[0]
    return -inner, inner


def row_z_window_mm() -> tuple[float, float]:
    """행 중심이 들어갈 수 있는 구간 (mm) — 마스트 두 제약이 낸다."""
    lo = HOLD_MAST_Z_MM + MAST_SECTION_MM + MIN_CLEARANCE_MM + MAST_OFFSET_MM
    hi = (GUARD_Z_MM - GUARD_POST_MM / 2 - MIN_CLEARANCE_MM
          - MAST_SECTION_MM / 2 - MAST_OFFSET_MM)
    return lo, hi


#: 채택한 행 중심 (mm) — 창의 상한이다. 위로 갈수록 HOLD 쪽이 넉넉해지고
#: 아래로 갈수록 가드 쪽이 넉넉해지는데, HOLD 행은 5장짜리라 사람이 드나드는
#: 쪽(가드)의 최소치를 지키는 편을 골랐다. `row_z_ok()` 가 창 안인지 본다.
ROW_Z_MM = 2300.0


def row_z_ok() -> bool:
    lo, hi = row_z_window_mm()
    return lo <= ROW_Z_MM <= hi


def deck_roller_reach_mm() -> float:
    """데크 Z 분기 롤러가 닿아야 하는 z (mm) — 분기 끝의 유리 바깥 모서리."""
    return ROW_Z_MM + GLASS_W_MM / 2


def clearances_mm() -> dict[str, float]:
    """채택값에서 남는 여유 (mm). 음수는 파고든 것이다."""
    return {
        "내측 마스트↔HOLD 마스트":
            (ROW_Z_MM - MAST_OFFSET_MM - MAST_SECTION_MM / 2)
            - (HOLD_MAST_Z_MM + MAST_SECTION_MM / 2),
        "외측 마스트↔가드 기둥":
            (GUARD_Z_MM - GUARD_POST_MM / 2)
            - (ROW_Z_MM + MAST_OFFSET_MM + MAST_SECTION_MM / 2),
    }


#: 데크 롤러 Z 분기 행정 — 행 중심까지.
BRANCH_MM = ROW_Z_MM

#: 픽업면 (mm) — 셔틀 데크 이송면. `layout.LINE_TRANSFER_MM` 위 3 mm 가 유리 상면.
PICKUP_MM = 953.0

#: 슬롯 높이 (mm) — GA 시트 `levels` 의 SLOT-1 / SLOT-25.
SLOT_FIRST_MM, SLOT_LAST_MM = 340.0, 2236.0

#: 콤포크 픽업 들어올림 (mm) — GA 흐름 3번 「콤포크 +15 픽업」.
FORK_PICK_MM = 15.0

#: 포크 X 신장 (mm) — GA 흐름 4번 「포크 X+ 3,200 신장·선단받이 결합」.
FORK_STROKE_MM = 3200.0

#: 슬롯 진입 시 유리 하면이 레일 상면 위에 뜨는 높이 (mm) — GA 흐름 5번의 12 다.
SET_DOWN_APPROACH_MM = 12.0

#: 슬롯 레일 안착 소하강 (mm) — **12 로는 포크가 안 떨어진다.**
#:
#: 12 는 「유리를 레일에 닿게 하는」 거리다. 그런데 유리는 레일에 닿는 순간
#: 늘어져서, 포크가 무는 z ±540 자리는 레일면보다 5.6 mm 더 내려간다
#: (`gbr_dynamics.glass_sag_at_fork_mm()`). 거기까지 안 내려가면 포크가 유리를
#: 그대로 문 채 후퇴해 유리를 끌고 나온다. 필요한 하강은
#:
#:     접근 12 + 유리 처짐 5.56 + 정지오차 1.0 = 18.56
#:
#: 이고 그 위 첫 정수를 잡는다. `gbr_dynamics.set_down_releases_the_fork()` 가 본다.
SET_DOWN_MM = 19.0

# ── 셀 X 사슬 (mm) — 3D 의 bDeck/bGap/bCar/bPitch 와 같은 값이다 ─────────
#: 셔틀 데크 길이.
DECK_LEN_MM = 3200.0
#: 데크와 도크 사이 틈 — `layout.BUFFER_DOCK_GAP_MM` 이 정본이다.
DOCK_GAP_MM = 225.0
#: 카세트 캐리지 길이와 모듈 피치.
CARRIAGE_LEN_MM, CARRIAGE_PITCH_MM = 2750.0, 2900.0


def mast_x_mm() -> float:
    """트윈마스트(=승강 캐리지) 중심 x (mm) — 데크–도크 틈 한가운데다."""
    return DECK_LEN_MM + DOCK_GAP_MM / 2


def fork_tip_x_mm() -> float:
    """완전 신장한 콤포크 선단 x (mm). 접힌 선단에서 행정만큼 나간다."""
    return DECK_LEN_MM / 2 + FORK_LEN_MM / 2 + FORK_STROKE_MM


def fork_free_length_mm() -> float:
    """신장한 콤포크의 자유 길이 (mm) — 승강 캐리지에서 선단까지의 외팔보다."""
    return fork_tip_x_mm() - mast_x_mm()


def slot_center_x_mm() -> float:
    """도크 캐리지(첫 모듈) 중심 x (mm)."""
    return DECK_LEN_MM + DOCK_GAP_MM + CARRIAGE_LEN_MM / 2


def glass_span_on_fork_mm() -> tuple[float, float]:
    """유리가 포크 위에 얹히는 구간 (mm) — 외팔보 뿌리에서 잰다."""
    root = mast_x_mm()
    mid = slot_center_x_mm()
    return mid - GLASS_L_MM / 2 - root, mid + GLASS_L_MM / 2 - root


def slot_pitch_mm() -> float:
    """슬롯 피치 (mm) — 첫·끝 슬롯 높이와 슬롯 수가 낸다."""
    from . import handoff
    return (SLOT_LAST_MM - SLOT_FIRST_MM) / (handoff.SLOTS_PER_CARRIAGE - 1)


#: TG-813 선단받이와 콤포크 밑면 사이 틈 (mm).
#:
#: 3D 는 12.5 였는데 그것이 소하강 12 보다 겨우 0.5 크다 — 처짐이 조금이라도
#: 있으면 **소하강 도중에 포크가 이 레일에 얹힌다.** `gbr_dynamics.tg_gap_window_mm()`
#: 이 하한(처짐 + 소하강)을 내고, 그 위로는 한계가 없다: 「유리가 선반을 긁기 전에
#: 받는다」를 걸면 틈 ≤ 소하강이 나와 하한과 모순이라, 이 부재는 슬롯 진입을
#: 받쳐 줄 수 없다. 계산이 「받쳐 줄 필요도 없다」를 함께 말하므로 (처짐이 예산의
#: 절반도 안 된다) 남는 역할은 **과대처짐 걸림쇠**다. 하한 위로 넉넉히 잡는다.
TG_GAP_MM = 25.0

#: 정지 위치 허용오차 (mm) — `servos.AXIS-GBR-X` 의 「분기 정지 ±1.0 mm」.
STOP_TOLERANCE_MM = 1.0

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
