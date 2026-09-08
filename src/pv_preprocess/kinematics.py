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

REV.49 — 발주처가 물었다. **"반전기를 패널 바로 위에 설치하면 어떻게 되나."**
링 하단(2,440)이 고정 픽업면(1,880) 위 560 mm 라 드럼을 적층 **바로 위**에 세울 수
있었고, 그러면 수평셔틀 1,850 이 통째로 없어진다. 로봇과 그 하류 전부가 같은
1,850 을 상류로 오며 전장이 58,050 → 56,200 이 됐다. 경로는 ㄱ자에서 **ㅣ자**가
됐다 — 링 밑을 지나는 구간이 없으니 REV.26 의 결함이 생길 자리 자체가 없다.
대신 새 조건 둘이 생긴다. 승강캐리지(2,720)는 케이지 안지름(2,580)보다 길어
링 구멍 **안으로** 오르내려야 하고(`carriage_bore_clearance_mm`), 지게차가 팔레트를
링 **밑으로** 밀어 넣으므로 헤드가드가 링 하단 아래여야 한다(`ring_over_forklift_mm`).
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

#: 캐리어 원점 기준 패널 상면 (mm). 3D 실측값이다.
PANEL_TOP_OFFSET_MM = 38


# ── 오픈센터 엔드링 ──────────────────────────────────────────────────────
#: 토러스 중심선 반경과 단면 반경 (mm) → ⌀1,980 외곽, ⌀1,620 통과 구멍.
RING_R_MM = 900
RING_TUBE_MM = 90

#: 두 엔드링의 축방향 간격 (mm). 케이지 안지름 = 이 값 − 단면 2배.
RING_PITCH_MM = 2760

#: 반전축이 플랜트 어느 축에 눕는가 — **설계의 현재 값**이다.
#:
#: "Z" (라인 가로) 다. 지게차가 패널을 장변 방향으로 넣으므로 장변이 Z 에 눕고,
#: 반전축은 그 장변과 나란해야 한다 (`PANEL_LONG_ALONG` 참조). 그림은 이 값을
#: `axis_is_z()` · `plan_xz()` 로 읽어서 스스로 돈다 — 리터럴로 다시 적지 않는다.
FLIP_AXIS_ALONG = "Z"

#: 통합 설계도 3D 의 **메시**가 아직 옛 방향(축 X)으로 그려져 있으면 그 사유.
#: 닫히면 None 이다.
#:
#: 리터럴은 전부 맞췄고(밴드·셀 외형·크레인·소음·케이블·케이싱) 시험도 통과하지만,
#: 3D 는 손으로 짠 형상이라 리터럴만으로는 안 돈다. **파이썬은 통과하는데 그림은
#: 옛 설계인 상태**가 이 저장소가 가장 경계하는 것이라(REV.26·§24) 값으로 남긴다.
#:
#: 생성 뷰(상세도 평면·입면, 운전 콘솔 평면·측면·단면)는 **돌았다** — `plan_xz`
#: 계열을 읽어 스스로 회전한다. 남은 것은 손으로 짠 3D 하나다.
#:
#: 돌릴 때 손대야 하는 자리 (docs/drawings/pv-preprocess-plant.html):
#:   • 베이 원점  `var yn=[new C(...,-1.6), new C(...,1.6)]` → ∓1.815
#:   • 페데스털   `It=jn.x+2.15` → `+2`
#:   • 포탈 `s` 4건 — 절대좌표라 회전식을 직접 먹인다:
#:       크기 (sx,sy,sz) → (sz,sy,sx),  자리 [i.x+I, y, i.z+zc] → [i.x−zc, y, i.z+I]
#:   • 베이 원점에 놓인 그룹 `n`·`d`·`f`·`m` — `rotation.y = Math.PI/2` 하나면 자식이 따라온다
#:   • `wr`(리프트)·`Is`(비전보) 는 절대좌표라 포탈과 같은 식으로 옮긴다
SCENE_AXIS_OPEN: str | None = (
    "통합 설계도의 3D 메시가 아직 축 X 를 가정한다 — 손으로 짠 형상이라 리터럴만으로는 "
    "안 돈다. 수치(밴드·셀 외형·베이 중심·페데스털·크레인·소음·케이블·케이싱)는 전부 "
    "축 Z 로 맞췄고 시험이 지킨다. 생성 뷰(상세도 평면·입면, 운전 콘솔 평면·측면·단면)도 "
    "모델 상수를 읽어 이미 돌았다. 제작 도면집이 부품 좌표를 이 3D 에서 받으므로, "
    "3D 를 돌리기 전에는 카세트 부품 좌표를 옮기지 않는다."
)


def scene_axis_is_registered() -> bool:
    """3D 메시가 모델 방향을 따라왔는가."""
    return SCENE_AXIS_OPEN is None

#: 패널 장변이 놓이는 플랜트 축. **"Z" 다 — 발주처 확인값이다.**
#:
#: 지게차가 패널을 **장변 방향으로** 투입한다. 팔레트 위 패널의 장변 2,500 이
#: 라인 진행방향(X)이 아니라 가로(Z)에 놓인다는 뜻이다.
#:
#: 반전축은 **패널 장변과 나란해야** 한다 — 축이 단변과 나란하면 링 통과 구멍이
#: 2,500 을 삼켜야 해서 반경이 810 → 1,250 이 되고 링이 통째로 커진다. 둘이 같이
#: 돌면 카세트 기준 기하는 **하나도 안 바뀐다**: 케이지 안지름 2,580 이 여전히
#: 장변을 받고(`cage_axial_clearance_mm`), 구멍 Ø1,620 이 여전히 단변을 받는다
#: (`bore_clearance_mm`). 바뀌는 것은 플랜트 안에서 카세트가 놓이는 방향뿐이고,
#: 그 대가는 **셀 폭**으로 나온다 (`afu_width_from_bays_mm`).
PANEL_LONG_ALONG = "Z"


# ── 포탈 발자국 ─────────────────────────────────────────────────────────
#: 포탈 기둥 중심의 **축방향** 위치 (mm, ∓). 링 바깥면(∓1,470)보다 밖이어야
#: 크로스빔이 링을 타고 넘지 않는다. 이 값이 카세트의 축방향 폭을 정하고,
#: 축을 돌리면 그 폭이 곧 셀 폭 소요가 된다 — OI-06 의 두 안이 갈리는 자리다.
PORTAL_COLUMN_AXIS_MM = 1600

#: 기둥 단면 (축방향, 축직각) mm — 제작 패키지 BFC-COL-01 (박스빔 240×180).
PORTAL_COLUMN_SECTION_MM = (180, 240)

#: 기둥 중심의 **축직각** 위치 (mm). 대칭이 아니다 — 카세트가 도킹면 쪽으로
#: 물러나 있다. **바닥 레벨 발자국**은 이 값이 정한다: 페데스털이 카세트를
#: 비켜설 수 있는지는 여기로 재야 하고, 크로스빔(높이 3,320)으로 재면 460 을
#: 헛되이 밀어내 그만큼 로봇 도달이 모자라진다.
PORTAL_COLUMN_CROSS_MM = (-1290, 950)

#: 크로스빔 스팬 (mm, 축직각). 기둥보다 길어 양쪽으로 내민다 — 지지롤러·구동·
#: 볼스크루가 여기 매달린다. 머리 위 발자국은 이 값이 정한다.
CROSSBEAM_SPAN_MM = 2660

#: 중앙 백투백벽 두께 · 외측 안전벽 두께 · 그 바깥 정비통로 (mm).
CENTRE_WALL_T_MM = 250
OUTER_WALL_T_MM = 150
MAINTENANCE_AISLE_MM = 600

#: 반전축 높이 (mm). REV.26 은 3,300 이었다 — 링 하단이 이송면에 22 mm 까지
#: 붙어 있었다. 130 올려 캐리지 상단과의 틈을 130 → 260 mm 로 벌린다.
FLIP_AXIS_MM = 3430


# ── 투입 경로 ────────────────────────────────────────────────────────────
#: 고정 픽업면 (mm) — LFT-101 이 30장 적층 최상단을 늘 이 높이에 맞춘다. afu 셀의
#: 이송 높이가 곧 이 값이다.
PICK_FACE_MM = layout.STATIONS["afu"].transfer_height_mm

#: 안전분리 상승 (mm). 분리헤드가 한 장을 진공으로 물고 이만큼 올라오는 동안
#: 진공 A/B·두께·중량·높이로 겹장을 확인한다. 올라선 높이(대기면)에서 포획빔이
#: 프레임 밑으로 전개된다. REV.48 까지 대기면은 2,290 리터럴이었다 — 링 밑을
#: 수평으로 지나던 "이송면" 이다. 지날 링이 없어졌으니 픽업면에서 파생한다.
SEPARATION_MM = 370

#: 로봇 인계 높이 (mm). 반전이 끝나면 여기까지 내린다.
HANDOVER_MM = 2100

#: 승강캐리지 레일 — 반전축 기준 z ∓672.5 (패널 장변 프레임 중심선), 캐리어 원점
#: 아래 120. 캐리지는 2,720 으로 두 엔드링 안지름(2,580)보다 **길어서**, 링 평면을
#: 지날 때 링 구멍(반경 810) **안으로** 지나가야 한다.
CARRIAGE_RAIL_Z_MM = 672.5
CARRIAGE_RAIL_DROP_MM = 120
CARRIAGE_MM = 2720

#: FL-101 헤드가드 상단 (mm, 3D 실측). 지게차가 팔레트를 링 밑으로 밀어 넣는다.
FORKLIFT_GUARD_TOP_MM = 2165

#: 경로 구간 — (시각 s, 이름, 높이가 변하는가, X 로 움직이는가). REV.49 부터 수평
#: 구간이 **없다**. 드럼이 적층 바로 위에 서므로 패널은 픽업면에서 반전축까지 두 링
#: 사이를 수직으로만 오른다 — 링 평면을 가로지르며 올라가던 REV.26 의 결함이 생길
#: 자리 자체가 없다. 그 사실을 검사가 붙잡고 있어야 하므로 X 이동을 항으로 둔다.
PATH: tuple[tuple[float, float, str, bool, bool], ...] = (
    (7.5, 8.8, "픽업면에서 대기면까지 안전분리 상승", True, False),
    (8.8, 10.5, "대기면 — 포획빔 전개 대기", False, False),
    (10.5, 13.3, "두 링 사이에서 반전축까지 수직 승강", True, False),
    (13.3, 20.8, "반전축 유지·180° 반전", False, False),
    (20.8, 24.0, "두 링 사이에서 인계 높이까지 하강", True, False),
)


# ── 4점 단장 클램프 조 ───────────────────────────────────────────────────
#: 무는 자리와 여는 자리 (mm, 반전축 기준 z). 무는 자리는 패널 장변 프레임의
#: 중심이고, 여는 자리는 패널 반폭(700) 밖이라 승강 경로를 비운다.
JAW_CLOSED_Z_MM = 672.5
JAW_OPEN_Z_MM = 860.0

#: 조의 패드 폭 (mm). 여는 자리에서 이 절반만큼 패널 쪽으로 나온다.
JAW_PAD_W_MM = 180

#: 패드 길이 (mm, 패널 장변 방향). 제작 패키지 BFC-PAD-01 의 L 과 같아야 한다 —
#: `fabrication.geometry_checks()` 가 그것을 본다.
JAW_PAD_L_MM = 180

#: 패드가 프레임 플랜지에 무는 폭 (mm). **발주처 확정값이다.**
#:
#: 이 값이 없으면 접촉 면적이 안 나오고, 면적이 없으면 면압이 안 나오고, 면압이
#: 없으면 패드 경도를 못 고른다 — 그래서 이것이 패드 발주를 막고 있었다.
#:
#: 값이 정해지자 **패드 면이 평면이면 안 된다**는 것이 따라 나왔다. 패드는 폭
#: 180 이라 무는 자리에서 z 582.5…762.5 를 덮는데, 프레임은 패널 가장자리
#: (반폭 700)에서 안쪽으로 이 값만큼뿐이다. 나머지 92 는 **유리 위**고 62.5 는
#: 패널 밖 허공이다. 그래서 접촉면을 이 폭만큼만 남기고 파낸다.
JAW_PAD_CONTACT_MM = 25.0

#: 프레임 상면이 유리면보다 솟은 높이 (mm). **가정이다** — 프레임 단면표가 오면
#: 확인한다. 릴리프 깊이는 이 값과 패드 압축량의 합보다 커야 유리에 안 닿는다.
PANEL_FRAME_GLASS_STEP_MM = 4.0

#: 패드 접촉면을 뺀 나머지를 파내는 깊이 (mm). 단차 4 + 압축량 약 3 위에
#: 여유를 둔 값이다 — 이보다 얕으면 눌린 패드가 유리에 닿는다.
JAW_PAD_RELIEF_MM = 8.0

#: 조 개폐 실린더 (BFC-JCY-01) 안지름 (mm) 과 공압 작동 압력 (MPa).
#: 조 1대에 2본이 붙고 패드도 2매다.
JAW_CYLINDER_BORE_MM = 63.0
JAW_AIR_MPA = 0.5


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
    """링의 가장 낮은 점. 적층·지게차가 이 밑에 있다."""
    return FLIP_AXIS_MM - ring_outer_r_mm()


def cage_clear_span_mm() -> float:
    """두 엔드링 안쪽 면 사이 — 패널이 여기 들어가 앉는다."""
    return RING_PITCH_MM - 2 * RING_TUBE_MM


def dwell_mm() -> int:
    """대기면 — 안전분리 상승이 끝나는 높이. 3D 의 pvTv 다."""
    return PICK_FACE_MM + SEPARATION_MM


def ring_over_stack_mm() -> float:
    """적층 최상단 유리면과 링 하단 사이 여유. 드럼이 적층 위에 서는 조건이다."""
    return ring_bottom_mm() - (PICK_FACE_MM + PANEL_TOP_OFFSET_MM)


def ring_over_forklift_mm() -> float:
    """지게차 헤드가드와 링 하단 사이 여유 — 팔레트 교환은 링 밑에서 일어난다."""
    return ring_bottom_mm() - FORKLIFT_GUARD_TOP_MM


# ── 카세트 발자국과 베이 배치 ───────────────────────────────────────────
def cassette_axis_extent_mm() -> float:
    """반전축 방향 카세트 폭 (mm) — 기둥 바깥면에서 바깥면까지.

    회전 뒤 이 값이 **플랜트 Z** 로 눕고, 베이 두 개가 이 폭을 하나씩 먹는다.
    폭이 모자라는 이유가 전부 여기 있다.
    """
    return 2 * (PORTAL_COLUMN_AXIS_MM + PORTAL_COLUMN_SECTION_MM[0] / 2)


def cassette_cross_extent_mm() -> float:
    """반전축 직각 방향 카세트 폭 (mm) — 크로스빔이 정한다 (높이 3,320)."""
    return float(CROSSBEAM_SPAN_MM)


def crossbeam_cross_extent_mm() -> tuple[float, float]:
    """크로스빔의 축직각 범위 (mm) — 기둥 두 본의 **가운데**에 걸린다.

    기둥이 대칭이 아니므로(∓ 가 아니라 −1,290/+950) 빔도 대칭이 아니다. 빔은
    기둥 중심의 중점에 걸리고 스팬 `CROSSBEAM_SPAN_MM` 을 좌우로 반씩 내민다 —
    기둥 바깥면(`cassette_floor_extent_mm`)보다 양쪽으로 90 씩 더 나온다.
    """
    mid = sum(PORTAL_COLUMN_CROSS_MM) / 2
    half = CROSSBEAM_SPAN_MM / 2
    return (mid - half, mid + half)


def crossbeam_overhang_mm() -> float:
    """크로스빔이 기둥 바깥면 밖으로 내미는 길이 (mm) — 지지롤러·구동이 앉는다."""
    lo, hi = cassette_floor_extent_mm()
    b0, b1 = crossbeam_cross_extent_mm()
    return min(lo - b0, b1 - hi)


def cassette_floor_extent_mm() -> tuple[float, float]:
    """바닥 레벨 발자국의 축직각 범위 (mm) — 기둥만. 크로스빔은 머리 위다.

    페데스털이 카세트를 비켜설 수 있는지는 **이 값**으로 본다. 크로스빔으로
    재면 460 을 헛되이 밀어내고, 그만큼 로봇 도달이 모자라진다.
    """
    lo, hi = PORTAL_COLUMN_CROSS_MM
    half = PORTAL_COLUMN_SECTION_MM[1] / 2
    return (lo - half, hi + half)


def axis_is_z() -> bool:
    """반전축이 라인 가로(Z)에 눕는가 — 그림이 이 한 줄로 갈린다."""
    return FLIP_AXIS_ALONG == "Z"


def plan_xz(axial: float, cross: float) -> tuple[float, float]:
    """(축방향, 축직각) 오프셋을 평면의 (X, Z) 로 옮긴다.

    카세트 기준 치수는 방향과 무관하다 — 어느 축에 눕느냐만 다르다. 도면 코드가
    `pick ∓1,600` 같은 리터럴을 쓰면 축을 돌려도 그림이 안 돈다. 그래서 축을
    읽는 자리를 여기 하나로 모은다.
    """
    return (cross, axial) if axis_is_z() else (axial, cross)


def panel_half_xz_mm() -> tuple[float, float]:
    """평면에서 패널의 반폭 (X, Z). 장변은 언제나 반전축과 나란하다."""
    return plan_xz(PANEL_MM[0] / 2, PANEL_MM[1] / 2)


def ring_half_xz_mm() -> tuple[float, float]:
    """평면에서 엔드링 하나의 반폭 (X, Z) — 축방향은 관 두께, 직각은 외경."""
    return plan_xz(RING_TUBE_MM, ring_outer_r_mm())


def ring_plane_offsets_mm() -> tuple[float, float]:
    """두 링 평면의 축방향 위치 (∓)."""
    return (-RING_PITCH_MM / 2, RING_PITCH_MM / 2)


def column_half_xz_mm() -> tuple[float, float]:
    """평면에서 포탈 기둥 하나의 반폭 (X, Z)."""
    a, c = PORTAL_COLUMN_SECTION_MM
    return plan_xz(a / 2, c / 2)


def column_offsets_xz_mm(bay_sign: int) -> tuple[tuple[float, float], ...]:
    """기둥 4본의 평면 오프셋 (X, Z) — 베이 부호를 받는다.

    축직각 자리는 대칭이 아니다(−1,290 / +950). 그 비대칭이 **베이를 가르는
    방향**에 있을 때만 베이마다 거울상이 된다 — 축이 Z 면 비대칭이 X(공정방향)로
    가므로 두 베이가 같은 자리를 쓴다. 하류면이 `cassette_floor_extent_mm()[1]`
    이고 페데스털 여유가 거기서 나온다.
    """
    out = []
    for a in (-PORTAL_COLUMN_AXIS_MM, PORTAL_COLUMN_AXIS_MM):
        for c in PORTAL_COLUMN_CROSS_MM:
            cc = c if axis_is_z() else (c if bay_sign < 0 else -c)
            out.append(plan_xz(a, cc))
    return tuple(out)


def cell_span_extent_mm() -> float:
    """셀 **폭(Z)** 방향에 놓이는 카세트 치수 (mm) — 반전축 방향이 정한다.

    축이 X 면 좁은 쪽(크로스빔 2,660)이 폭에 눕고, Z 면 넓은 쪽(기둥 3,380)이
    눕는다. 회전의 대가가 전부 이 한 줄에서 갈린다.
    """
    return (cassette_axis_extent_mm() if FLIP_AXIS_ALONG == "Z"
            else cassette_cross_extent_mm())


def bay_pitch_mm() -> float:
    """두 베이 중심 사이 최소 거리 (mm) — 폭에 눕는 카세트 치수 + 중앙벽."""
    return cell_span_extent_mm() + CENTRE_WALL_T_MM


def min_bay_centre_z_mm() -> float:
    """베이 중심 z 의 하한 (mm, ∓). `layout.BFC_PICKUP_Z_MM` 이 이보다 밖이어야
    두 카세트가 중앙벽을 사이에 두고 겹치지 않는다."""
    return bay_pitch_mm() / 2


def bays_clear_each_other() -> bool:
    return layout.BFC_PICKUP_Z_MM >= min_bay_centre_z_mm()


def afu_width_from_bays_mm() -> float:
    """베이 배치가 요구하는 afu 셀 폭 (mm).

    중앙벽 절반 + 카세트 + 외측벽 + 정비통로, 그 2배다. 회전 전에는 카세트의
    **좁은 쪽**(2,660)이 폭에 놓여 7,100 으로 됐다. 회전하면 넓은 쪽(3,380)이
    폭에 놓이므로 이만큼 필요하다 — 이것이 회전의 대가다.
    """
    return 2 * (CENTRE_WALL_T_MM / 2 + cell_span_extent_mm()
                + OUTER_WALL_T_MM + MAINTENANCE_AISLE_MM)


def outer_wall_z_mm() -> float:
    """외측 안전벽 중심의 z (mm, ∓) — 카세트 바깥면에 붙는다."""
    return CENTRE_WALL_T_MM / 2 + cell_span_extent_mm() + OUTER_WALL_T_MM / 2


def maintenance_aisle_mm() -> float:
    """실제로 남는 정비통로 (mm) — 셀 폭에서 역산한다."""
    half = layout.STATIONS["afu"].envelope[1] / 2
    return half - (CENTRE_WALL_T_MM / 2 + cell_span_extent_mm() + OUTER_WALL_T_MM)


def bays_fit_the_cell() -> bool:
    """두 베이 + 벽 + 정비통로가 afu 셀 폭 안에 드는가."""
    return maintenance_aisle_mm() >= MAINTENANCE_AISLE_MM


def flip_axis_matches_the_panel() -> bool:
    """반전축이 패널 장변과 나란한가 — 어긋나면 링 구멍이 장변을 삼켜야 한다."""
    return FLIP_AXIS_ALONG == PANEL_LONG_ALONG


def carriage_crosses_the_rings() -> bool:
    """캐리지가 케이지보다 길어 링 평면을 지나는가."""
    return CARRIAGE_MM > cage_clear_span_mm()


def carriage_bore_clearance_mm() -> float:
    """캐리지 레일과 링 구멍 사이 여유 (반경 방향).

    레일은 축에서 z 672.5 · y −120 에 있다 — 그 반경이 구멍 반경 810 안이어야
    캐리지가 링을 뚫지 않고 오르내린다.
    """
    r = (CARRIAGE_RAIL_Z_MM**2 + CARRIAGE_RAIL_DROP_MM**2) ** 0.5
    return ring_bore_r_mm() - r


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


def jaw_pad_land_z_mm() -> tuple[float, float]:
    """패드 접촉면(랜드)의 안쪽·바깥쪽 z (mm, 패널 중심 기준).

    랜드는 프레임 위에만 앉아야 한다. 프레임의 바깥면이 곧 패널 가장자리이므로
    랜드를 **가장자리에 맞춰** 안쪽으로 접촉폭만큼 낸다 — 이보다 안쪽으로
    옮기면 유리에 올라탄다. 이 배치는 플랜지가 접촉폭 이상이라는 뜻이고,
    발주처가 접촉폭을 25 로 준 것이 그 전제다.
    """
    outer = PANEL_MM[1] / 2
    return (outer - JAW_PAD_CONTACT_MM, outer)


def jaw_pad_land_offset_mm() -> float:
    """랜드 중심이 패드 중심에서 바깥으로 밀린 양 (mm).

    조가 무는 자리(패드 중심)는 672.5 인데 랜드 중심은 687.5 다. 랜드를 패드
    한가운데 두면 유리 위로 15 밀려 앉는다 — **패드는 편심 랜드로 만든다.**
    조 행정과 캐리어는 그대로 두고 패드 하나만 바꾸면 되기 때문이다.
    """
    lo, hi = jaw_pad_land_z_mm()
    return (lo + hi) / 2 - JAW_CLOSED_Z_MM


def jaw_pad_land_is_inside_the_pad() -> bool:
    """랜드가 패드 면 안에 들어오는가 — 벗어나면 패드를 키워야 한다."""
    lo, hi = jaw_pad_land_z_mm()
    return (JAW_CLOSED_Z_MM - JAW_PAD_W_MM / 2 <= lo
            and hi <= JAW_CLOSED_Z_MM + JAW_PAD_W_MM / 2)


def jaw_pad_contact_area_mm2() -> float:
    """패드 1매의 접촉 면적 (mm²)."""
    return JAW_PAD_CONTACT_MM * JAW_PAD_L_MM


def jaw_clamp_force_n() -> float:
    """패드 1매가 받는 압착력 (N).

    조 1대에 실린더 2본·패드 2매라 지레비가 1:1 이면 실린더 1본이 패드 1매를
    맡는다. **지레비는 아직 안 정해졌다** (실린더 장착 위치 = 미결 OI-03) —
    1:1 은 그 결정 전의 기준값이고, 실린더를 조의 안쪽에 달면 면압이 이보다
    커진다.
    """
    return 3.141592653589793 / 4 * JAW_CYLINDER_BORE_MM ** 2 * JAW_AIR_MPA


def jaw_pad_pressure_mpa() -> float:
    """패드 접촉면의 면압 (MPa) — 압착력 ÷ 접촉 면적."""
    return jaw_clamp_force_n() / jaw_pad_contact_area_mm2()


def jaw_pad_compression_mm() -> float:
    """면압에서 나오는 패드 압축량 (mm).

    PU 70A 의 압축 탄성률을 6 MPa 로 잡는다 (쇼어 A 70 의 통상 범위 5–8).
    두께 50 이 이 변형률만큼 준다.
    """
    return 50.0 * (jaw_pad_pressure_mpa() / 6.0)


def jaw_pad_clears_the_glass() -> bool:
    """눌린 패드가 유리에 안 닿는가 — 릴리프 > 단차 + 압축량."""
    return JAW_PAD_RELIEF_MM > PANEL_FRAME_GLASS_STEP_MM + jaw_pad_compression_mm()


def lift_is_vertical(path: tuple[tuple[float, float, str, bool, bool], ...] | None = None) -> bool:
    """경로 어느 구간도 X 로 움직이지 않는가 — 드럼이 적층 위에 선다는 뜻이다.

    REV.26 의 결함은 링 평면을 가로지르며 올라간 것이었고 REV.27 은 그 구간을
    수평으로 눕혀 고쳤다. REV.49 는 가로지르는 구간 자체를 없앴다. 인자를 열어
    둔 것은, 지금 경로가 이미 맞아서 검사 코드가 죽어도 아무도 모르는 일을
    막기 위해서다(§24·§25 에서 세 번 겪었다).
    """
    p = PATH if path is None else path
    return not any(travels for _t0, _t1, _name, _climbs, travels in p)


def path_is_continuous(path: tuple[tuple[float, float, str, bool, bool], ...] | None = None) -> bool:
    """구간이 빈틈·겹침 없이 이어지는가 — 3D 공정시계(hM)의 분기와 같은 시각이다."""
    p = PATH if path is None else path
    return all(a[1] == b[0] for a, b in zip(p, p[1:]))


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
        "pickFaceMm": PICK_FACE_MM,
        "dwellMm": dwell_mm(),
        "ringBoreMm": round(ring_bore_r_mm() * 2),
        "ringBottomMm": round(ring_bottom_mm()),
        "ringOverStackMm": round(ring_over_stack_mm()),
        "ringOverForkliftMm": round(ring_over_forklift_mm()),
        "carriageBoreMm": round(carriage_bore_clearance_mm()),
        "boreClearMm": round(bore_clearance_mm()),
        "cageAxialMm": round(cage_axial_clearance_mm()),
        "jawStrokeMm": round(jaw_stroke_mm(), 1),
        "jawOpenClearMm": round(jaw_open_clearance_mm()),
        "afrClampKn": afr_clamp_reaction_kn(),
        "afrPortalZMm": AFR_PORTAL_Z_MM,
        "afrPortalAnchors": afr_portal_anchor_total(),
    }
