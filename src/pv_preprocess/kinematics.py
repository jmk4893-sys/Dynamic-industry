"""반전기 투입 기구학 — 패널이 지나가는 자리의 단일 출처.

발주처 지적은 한 줄이었다. **"태양광 패널이 반전기에 투입될 때 반전기와
간섭이 생겨."**

재 보니 사실이었고, 그동안 못 잡은 이유가 셋이었다.

1. **간섭 스윕이 시점을 11개만 봤다.** 투입은 t 10.5–13.3 s 에 일어나는데 그
   사이를 t=12 한 점으로만 훑었다. 관통이 가장 깊은 t 11.5 는 표본 사이로
   빠졌다.
2. **엔드링을 바운딩박스로 쟀다.** 오픈센터 링은 가운데가 뚫려 있어서 박스가
   겹쳐도 통과일 수 있고, 겹치지 않아도 관통일 수 있다. 축 기준 반경으로
   재야 답이 나온다.
3. **패널이 규격보다 컸다.** 3D 의 알루미늄 프레임이 2,500 × 1,400 유리
   **바깥**에 붙어 있어 조립체가 2,615 × 1,515 였다 — 규격의 두 변이 각각
   115 mm 씩 크다. 실제 모듈은 프레임이 곧 외곽이다.

세 눈을 다 뜨고 보니 패널이 링 단면을 **최대 88 mm** 파고들고 있었다.

원인은 경로였다. 패널이 x 로 1,810 mm 나아가면서 동시에 y 로 1,030 mm 올라가는
**대각선**이라, 링 축을 향해 들어가는 대신 링의 아래 팔을 훑고 올라갔다.
그러면서 케이지 안에 자리를 잡을 때에만 축과 동심이 됐다.

고친 것은 세 가지다.

* 경로를 **ㄱ자**로 바꿨다 — 링 밑을 수평으로 지나간 뒤, 두 링 사이에서
  수직으로 올린다. 링 평면을 지나는 동안 높이가 변하지 않는 것이 요점이다.
* 반전축을 3,300 → **3,430 mm** 로 올렸다. 캐리지 상단(2,180)과 링 하단
  사이가 130 mm 뿐이라 이송면이 링에 22 mm 까지 붙어 있었다 — 우연이지
  설계값이 아니었다. 260 mm 로 벌려 위아래 각각 110 mm 대를 준다.
* 패널 프레임을 규격 안으로 넣었다. 이제 조립체가 2,500 × 1,400 이다.

여기에 클램프가 하나 더 걸렸다. 4점 단장 클램프의 조(jaw)가 링 림(반경 983)에
붙어 있어서 **물어야 할 패널에서 660 mm 떨어져 있었고**, 반전 뒤 하강할 때
패널이 그 조를 지나갔다. 조를 패널 장변 프레임 자리로 옮기고 z 여닫이 행정
187.5 mm 를 줬다 — 무는 자리 ∓672.5, 여는 자리 ∓860.

`tools/check_clearance.mjs` 가 이 값들을 기하로 검사한다. 여기서는 **왜 그
값인지**를 정의하고, 도면 리터럴과 대조한다.
"""

from __future__ import annotations

from . import layout

# ── 패널 — 공정물의 실치수 ───────────────────────────────────────────────
#: 최대 모듈 외곽 (mm). 프레임이 곧 외곽이다 — 유리 바깥에 프레임을 덧붙이면
#: 안 된다. REV.26 까지 3D 가 그렇게 그려 조립체가 2,615 × 1,515 였다.
PANEL_MM: tuple[int, int] = (2500, 1400)

#: 프레임 높이와 정션박스 돌출 (mm). 정션박스는 프레임 밑으로 내려온다.
PANEL_FRAME_H_MM = 75
PANEL_JBOX_DROP_MM = 142

#: 캐리어 원점 기준 패널 상·하면 (mm). 3D 실측값이다.
PANEL_TOP_OFFSET_MM = 38
PANEL_BOTTOM_OFFSET_MM = 6


# ── 오픈센터 엔드링 ──────────────────────────────────────────────────────
#: 토러스 중심선 반경과 단면 반경 (mm) → ⌀1,980 외곽, ⌀1,620 통과 구멍.
RING_R_MM = 900
RING_TUBE_MM = 90

#: 두 엔드링의 축방향 간격 (mm). 케이지 안지름 = 이 값 − 단면 2배.
RING_PITCH_MM = 2760

#: 반전축 높이 (mm). REV.26 은 3,300 이었다 — 링 하단이 이송면에 22 mm 까지
#: 붙어 있었다. 130 올려 캐리지 상단과의 틈을 130 → 260 mm 로 벌린다.
FLIP_AXIS_MM = 3430


# ── 투입 경로 ────────────────────────────────────────────────────────────
#: 승강캐리지 상단 (mm). 패널은 이 위를 지나야 한다.
CARRIAGE_TOP_MM = 2180

#: 수평 이송 높이 (mm). 캐리지 상단과 링 하단 사이 260 mm 창의 가운데다.
TRANSFER_MM = 2290

#: 로봇 인계 높이 (mm). 반전이 끝나면 여기까지 내린다.
HANDOVER_MM = 2100

#: 경로 구간 — (시각 s, 이름, 높이가 변하는가). 링 평면을 가로지르는 구간에서
#: 높이가 변하면 패널이 링의 팔을 훑는다. 그것이 REV.26 의 결함이었다.
PATH: tuple[tuple[float, float, str, bool], ...] = (
    (7.5, 8.8, "캐리지에서 이송면까지 승강", True),
    (8.8, 10.5, "이송면 대기", False),
    (10.5, 12.1, "링 밑을 수평 통과 — 높이 불변", False),
    (12.1, 13.3, "두 링 사이에서 수직 승강", True),
    (13.3, 20.8, "반전축 유지·180° 반전", False),
    (20.8, 24.0, "두 링 사이에서 인계 높이까지 하강", True),
)

#: 링 평면을 가로지르는 구간의 이름. 이 구간은 높이가 변하면 안 된다.
CROSSING_PHASE = "링 밑을 수평 통과 — 높이 불변"


# ── 4점 단장 클램프 조 ───────────────────────────────────────────────────
#: 무는 자리와 여는 자리 (mm, 반전축 기준 z). 무는 자리는 패널 장변 프레임의
#: 중심이고, 여는 자리는 패널 반폭(700) 밖이라 승강 경로를 비운다.
JAW_CLOSED_Z_MM = 672.5
JAW_OPEN_Z_MM = 860.0

#: 조의 패드 폭 (mm). 여는 자리에서 이 절반만큼 패널 쪽으로 나온다.
JAW_PAD_W_MM = 180


# ── AFR 상부 클램프 포탈 ─────────────────────────────────────────────────
#: 상부 클램프 1기당 체결력 (kN) 과 기수. 이 반력을 받을 구조가 없었다.
AFR_CLAMP_KN = 3.0
AFR_CLAMP_UNITS = 4

#: 단축 유압 인출축 1축당 인출력 (kN) 과 축수. 클램프는 이 반작용을 누른다.
AFR_PULL_KN = 25.0
AFR_PULL_AXES = 2

#: 포탈 기둥의 z 위치 (mm). 남은 틈에서 정해진다 — 패널 통과 폭(±700),
#: 정렬 셔틀(±1,100), LA-401 LM 레일(±1,040) **밖**이고 안전가드(±2,330)
#: **안쪽**이어야 한다.
AFR_PORTAL_Z_MM = 1450
AFR_PORTAL_OBSTACLES_MM: tuple[tuple[str, int], ...] = (
    ("패널 통과 폭", 700),
    ("AFR-SH-01 정렬 셔틀", 1100),
    ("LA-401 35급 듀얼 LM레일", 1040),
)
AFR_GUARD_Z_MM = 2330

#: 크로스헤드 하면 (mm) — 상부 클램프 실린더 상단과 같아야 매달린다.
#:
#: 이 높이는 **이송면 위에 쌓인 것들의 합**이지 임의의 값이 아니다. 이송면
#: 위로 프레임 하면 부상 2.5, 알루미늄 프레임 75, 정반 100, 클램프 몸통
#: 상단까지 727.5 — 합 855 mm 다. REV.44 까지 1,950 이라는 리터럴이었고,
#: 이송면을 1,095 → 950 으로 내리자 클램프가 크로스헤드에서 145 mm 떨어져
#: 공중에 매달렸다 (하중경로 검사가 잡았다). 쌓임의 단일 출처는
#: tools/build_afr.py 이며, 시험이 그 결과와 이 값을 견준다.
AFR_CLAMP_STACK_MM = 855
AFR_CROSSHEAD_SOFFIT_MM = layout.LINE_TRANSFER_MM + AFR_CLAMP_STACK_MM
AFR_CLAMP_TOP_MM = AFR_CROSSHEAD_SOFFIT_MM

#: 크로스헤드 단면 높이 — 포탈 기둥 전장은 하면 + 이것이다.
AFR_CROSSHEAD_DEPTH_MM = 180
AFR_PORTAL_HEIGHT_MM = AFR_CROSSHEAD_SOFFIT_MM + AFR_CROSSHEAD_DEPTH_MM

#: 포탈 기둥 1본당 앵커.
AFR_PORTAL_COLUMNS = 4
AFR_PORTAL_ANCHORS_PER_COLUMN = 4
AFR_PORTAL_BOLT = "M20"


# ── 검사 도구와 공유하는 목록 ────────────────────────────────────────────
#: 공정 중인 물건. tools/check_clearance.mjs 의 WORKPIECES 와 같아야 한다.
WORKPIECES: tuple[str, ...] = (
    "태양광 패널", "적재 패널", "팔레트 패널", "JBOX 제거상태",
    "정션박스 형상", "검출 정션박스", "알루미늄 프레임", "박리 유리",
)

#: 설계상 접촉 — 무는·받는·미는 부재다. 겹치는 것이 정상이다.
DESIGN_CONTACTS: tuple[str, ...] = (
    "클램프", "조", "스토퍼", "롤러", "지지", "진공", "포크", "손목", "푸셔", "패드",
    "컨베이어", "셔틀", "캐리지", "레일", "적재대", "리프트", "팔레트", "랙",
    "가위날", "노즐", "센서", "케이블", "슬라이드", "호스", "균열감시",
    "프레임", "정반", "베드", "브래킷", "유압", "인발", "기준 슈", "RB-101", "포획빔",
    "칼날", "박리 계면",
)

#: 통과 개구 — 공정물이 지나가라고 낸 구멍인데 3D 는 판으로 그린다.
PASS_THROUGH: tuple[str, ...] = (
    "가드", "게이트", "터널", "커튼", "개구", "슈트", "존", "참조", "투영", "스캔선", "바닥",
)


# ── 파생값 ───────────────────────────────────────────────────────────────
def ring_bore_r_mm() -> float:
    """링 통과 구멍의 반경 — 패널은 이 원 안으로만 지나갈 수 있다."""
    return RING_R_MM - RING_TUBE_MM


def ring_outer_r_mm() -> float:
    return RING_R_MM + RING_TUBE_MM


def ring_bottom_mm() -> float:
    """링의 가장 낮은 점. 수평 이송은 이 밑으로 지나가야 한다."""
    return FLIP_AXIS_MM - ring_outer_r_mm()


def cage_clear_span_mm() -> float:
    """두 엔드링 안쪽 면 사이 — 패널이 여기 들어가 앉는다."""
    return RING_PITCH_MM - 2 * RING_TUBE_MM


def under_ring_clearance_mm(transfer_mm: float | None = None) -> float:
    """수평 이송 중 패널 상면과 링 하단 사이 여유."""
    t = TRANSFER_MM if transfer_mm is None else transfer_mm
    return ring_bottom_mm() - (t + PANEL_TOP_OFFSET_MM)


def over_carriage_clearance_mm(transfer_mm: float | None = None) -> float:
    """수평 이송 중 패널 하면과 승강캐리지 상단 사이 여유."""
    t = TRANSFER_MM if transfer_mm is None else transfer_mm
    return (t + PANEL_BOTTOM_OFFSET_MM) - CARRIAGE_TOP_MM


def bore_clearance_mm() -> float:
    """반전축에 앉았을 때 패널 모서리와 통과 구멍 사이 여유 (반경 방향).

    패널 단면의 반대각선이 통과 구멍 반경보다 작아야 한다.
    """
    half_w = PANEL_MM[1] / 2
    half_h = PANEL_FRAME_H_MM / 2
    return ring_bore_r_mm() - (half_w**2 + half_h**2) ** 0.5


def cage_axial_clearance_mm() -> float:
    """패널 끝과 엔드링 안쪽 면 사이 여유 (한쪽).

    REV.26 은 프레임이 규격 밖에 붙어 조립체가 2,615 였고, 케이지 안지름
    2,580 보다 **길어서** 애초에 들어가지 않았다 (−17.5 mm).
    """
    return (cage_clear_span_mm() - PANEL_MM[0]) / 2


def jaw_open_clearance_mm() -> float:
    """조를 열었을 때 패드 안쪽 면과 패널 옆면 사이 여유.

    이 값이 양수여야 반전 뒤 패널이 두 링 사이로 내려갈 수 있다.
    """
    return (JAW_OPEN_Z_MM - JAW_PAD_W_MM / 2) - PANEL_MM[1] / 2


def jaw_stroke_mm() -> float:
    return JAW_OPEN_Z_MM - JAW_CLOSED_Z_MM


def crossing_is_level(path: tuple[tuple[float, float, str, bool], ...] | None = None) -> bool:
    """링 평면을 가로지르는 구간에서 높이가 변하지 않는가.

    REV.26 의 결함이 정확히 이것이었다 — 가로지르면서 올라갔다. 인자를 열어
    둔 것은, 지금 경로가 이미 맞아서 검사 코드가 죽어도 아무도 모르는 일을
    막기 위해서다(§24·§25 에서 세 번 겪었다).
    """
    p = PATH if path is None else path
    for _t0, _t1, name, climbs in p:
        if name == CROSSING_PHASE and climbs:
            return False
    return True


def afr_clamp_reaction_kn() -> float:
    """포탈이 받아야 하는 하향 반력 — 상부 클램프 4기의 합."""
    return AFR_CLAMP_KN * AFR_CLAMP_UNITS


def afr_portal_anchor_total() -> int:
    return AFR_PORTAL_COLUMNS * AFR_PORTAL_ANCHORS_PER_COLUMN


def afr_portal_is_clear(z_mm: float | None = None) -> bool:
    """포탈 기둥이 통과 폭·셔틀·LM 레일 밖이고 가드 안쪽인가."""
    z = AFR_PORTAL_Z_MM if z_mm is None else z_mm
    return all(z > limit for _name, limit in AFR_PORTAL_OBSTACLES_MM) and z < AFR_GUARD_Z_MM


def summary() -> dict[str, object]:
    """도면 표제란·검토서에 그대로 넣는 값."""
    return {
        "panelMm": list(PANEL_MM),
        "flipAxisMm": FLIP_AXIS_MM,
        "transferMm": TRANSFER_MM,
        "ringBoreMm": round(ring_bore_r_mm() * 2),
        "ringBottomMm": round(ring_bottom_mm()),
        "underRingMm": round(under_ring_clearance_mm()),
        "overCarriageMm": round(over_carriage_clearance_mm()),
        "boreClearMm": round(bore_clearance_mm()),
        "cageAxialMm": round(cage_axial_clearance_mm()),
        "jawStrokeMm": round(jaw_stroke_mm(), 1),
        "jawOpenClearMm": round(jaw_open_clearance_mm()),
        "afrClampKn": afr_clamp_reaction_kn(),
        "afrPortalZMm": AFR_PORTAL_Z_MM,
        "afrPortalAnchors": afr_portal_anchor_total(),
    }
