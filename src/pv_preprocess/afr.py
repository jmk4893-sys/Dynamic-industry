"""AFR-101 알루미늄 프레임 제거 기구 — 정반·실린더·쇠막대·스토퍼·이송·인발.

발주처가 기구를 한 문단으로 다시 설명했고, 3D 가 그것을 그리고 있지 않았다.

    "위에서 아래로 내려오는 사각 정반은 600 × 1,400, 두께 100 이다. 정반 **안에**
     실린더가 들어가고, 실린더가 단변쪽으로 나오면서 단변을 밀어낸다. 600 의 양변
     에서 양끝에서 50 떨어진 자리의 실린더 둘이 **하나의 쇠막대**에 연결되어 쇠막대
     전체가 알루미늄을 밀어낸다. 밀려난 단변 알루미늄은 **스토퍼**에 걸려 선다.
     알루미늄이 다 제거되면 정반에 **길게 홈이 파인 곳**으로 톱니바퀴 컨베이어가
     아래에서 위로 올라와 패널을 이송해 간다. 장변은 롤러가 **알루미늄 홈으로
     들어가 걸쳐서** 바깥으로 당기고, LM 가이드를 타고 이동하면서 계속 당긴다.
     양쪽에서 쭉 당기면 프레임이 휘지 않고 직선으로 그대로 떨어진다."

세 치수(600 × 1,400 × 100)와 한 배치(양끝에서 50)가 주어졌다. 나머지는 거기서
따라 나온다 — 그리고 따라 나오는 값 중 둘은 기존 도면 수치를 **무효로 만든다**:

* **두께 100 이 보어를 정한다.** 실린더가 정반 *안에* 들어가려면 배럴 외경이
  100 − 2×(정반 살) − 2×(포켓 여유) 를 못 넘는다. 도면의 Ø125 는 배럴만 150 대라
  100 두께 정반에 애초에 안 들어간다. 여기서 나오는 최대 보어는 Ø63 이고, 정반당
  2본이면 70 bar 릴리프 안에서 25 kN 을 44 bar 로 낸다.
* **홈 폭이 롤러 수를 정한다.** 장변 압출재 홈에 들어갈 수 있는 롤러는 지름·높이가
  홈보다 작아야 하고, 그 크기로 1,200 N 을 한 점에서 받으면 알루미늄이 소성
  압흔을 남긴다. 구름접촉 항복(p_max = σ_y/(2×0.300))에 설계계수를 얹어 역산하면
  캐리지당 롤러가 몇 개 필요한지가 나온다.

그리고 발주처 문장의 마지막 한 줄 — "휘지 않고 직선으로" — 은 이 기구가 기존
표현과 다른 지점이다. 기존 3D 는 롤러가 접착 전선보다 220 mm **앞서** 달리는
그림이라 프레임이 40배 과장으로 휘었다. 롤러가 홈에 걸려 전선과 **같이** 가면
자유 길이는 0 에 수렴하고, 남는 것은 이미 떨어진 뒷부분의 **자중 처짐**뿐이다.
그 자중 처짐을 계산하면 0.6 mm — 화면에서 직선이다. 발주처 말이 맞다.
"""

from __future__ import annotations

import math

from . import frames, kinematics

# ── 정반 (발주처 지정 치수) ──────────────────────────────────────────────
#: 사각 정반 (mm) — 가로(패널 장축 X) × 세로(패널 단축 Z) × 두께.
PLATEN_X_MM = 600
PLATEN_Z_MM = 1400
PLATEN_T_MM = 100

#: 정반은 단변마다 하나씩, 위에서 아래로 내려온다.
PLATEN_COUNT = 2
#: 정반이 들려야 하는 여유 (mm) — 체인이 든 패널 위로 이만큼 더 뜬다.
PLATEN_CLEAR_MM = 60
#: 승강 속도 (mm/s) — 정반 하강·상승 축.
PLATEN_SPEED_MM_S = 125.0

#: 정반은 통짜 강괴가 아니라 리브 웰드먼트다 — 안에 실린더 포켓이 들어가야 하고,
#: 통짜로 만들면 4점 클램프가 자기 무게도 못 든다 (아래 clamp_holds_the_platen).
#: 상·하판 두께와 리브 두께·피치에서 강재 점유율이 나온다.
PLATEN_SKIN_T_MM = 12
PLATEN_RIB_T_MM = 12
PLATEN_RIB_PITCH_MM = 200

#: 정반 재질 — S355 강. 밀도는 3D 질량과 반력 계산에 쓴다.
STEEL_DENSITY_KG_M3 = 7850.0
STEEL_E_MPA = 210_000.0
STEEL_ALLOW_MPA = 160.0

# ── 실린더 (정반 안에 들어간다) ─────────────────────────────────────────
#: 정반 살두께 최소 (mm) — 포켓 위아래로 남겨야 하는 강재.
MIN_PLATEN_WALL_MM = 8
#: 포켓과 배럴 사이 조립 여유 (mm, 편측).
POCKET_CLEAR_MM = 2
#: 유압 실린더 배럴 살두께 (mm, 편측) — 70 bar 급 인발실린더 통상값.
BARREL_WALL_MM = 8

#: ISO 6431/6020-2 표준 보어 계열 (mm). 여기서 고른다 — 임의 치수를 쓰지 않는다.
ISO_BORES_MM: tuple[int, ...] = (32, 40, 50, 63, 80, 100, 125, 160, 200)
#: 보어에 대응하는 로드경 (mm).
ISO_RODS_MM: dict[int, int] = {32: 18, 40: 22, 50: 28, 63: 36, 80: 45,
                               100: 56, 125: 70, 160: 90, 200: 110}

#: 실린더 행정 (mm) — 원본 도면값을 유지한다.
CYL_STROKE_MM = 250
#: 인발 속도 (mm/s) — 원본 도면값.
CYL_SPEED_MM_S = 30.0

#: 정반 하나에 들어가는 실린더 수 — 발주처: "60 의 양변에서" 둘.
CYL_PER_PLATEN = 2
#: 실린더가 정반 양끝(1,400 방향)에서 안쪽으로 들어온 거리 (mm) — 발주처 지정.
CYL_INSET_MM = 50

#: HPU-601 릴리프 (bar). 작동압은 이 아래여야 한다.
HPU_RELIEF_BAR = 70.0
#: 작동압 안전여유 배수 — 릴리프 대비 이만큼 밑에서 정격을 내야 한다.
PRESSURE_MARGIN = 1.3

# ── 쇠막대 (실린더 둘을 하나로 묶는다) ──────────────────────────────────
#: 쇠막대 폭 (mm). 높이는 파생값이다 — 로드 축에서 프레임 밑면까지 닿아야 한다.
BAR_W_MM = 60
#: 쇠막대 처짐 허용 — 스팬의 1/n. 이 값을 넘으면 가운데가 뒤처져 단변이 비틀린다.
BAR_SAG_LIMIT_RATIO = 1000

# ── 스토퍼 ──────────────────────────────────────────────────────────────
#: 프레임이 라미네이트 모서리를 완전히 벗어나는 데 필요한 여유 (mm).
FRAME_RELEASE_CLEAR_MM = 45
#: 스토퍼 캐치 립 깊이 (mm) — 밀려온 프레임이 넘어가지 않고 걸리는 깊이.
STOPPER_LIP_MM = 25
#: 스토퍼 판 두께 (mm).
STOPPER_T_MM = 60
#: 스토퍼 기수 (단변 하나당).
STOPPER_PER_EDGE = 2
#: 스토퍼의 z 위치 (mm) — 정렬 스토퍼(±660)·LM 레일(±980)과 겹치지 않는 자리.
STOPPER_Z_MM = 250

# ── 정반에 파인 긴 홈과 톱니 컨베이어 ────────────────────────────────────
#: 12구역 지지패드 격자 — 칸은 x (mm). 열(z)은 파생값이다: 바깥 열이 장변
#: 프레임 밑으로 들어가면 유리가 아니라 프레임을 받게 되고, 프레임이 빠져나갈 때
#: 패드에 걸린다. 그래서 프레임 안쪽으로 물러나야 한다.
SUPPORT_COLS_X_MM: tuple[int, ...] = (-900, -300, 300, 900)
#: 바깥 패드와 장변 프레임 안쪽면 사이 여유 (mm).
PAD_EDGE_CLEAR_MM = 15
SUPPORT_PAD_X_MM = 500
SUPPORT_PAD_Z_MM = 340
SUPPORT_PAD_T_MM = 70

#: 긴 홈 (mm) — 폭과 길이. 패널(2,500)보다 길어야 체인이 앞뒤로 물고 나간다.
SLOT_W_MM = 80
SLOT_L_MM = 2800

#: 톱니 컨베이어 — ISO 08B-1 롤러체인, 스프로킷 잇수.
CHAIN_PITCH_MM = 12.7
SPROCKET_TEETH = 17
#: 체인 상면이 패널 하면 아래에 대기하는 거리와, 들어 올리는 높이 (mm).
CHAIN_PARK_MM = 10
CHAIN_LIFT_MM = 40
#: 반출 속도 (mm/s).
CHAIN_SPEED_MM_S = 300.0

#: 무프레임 라미네이트 — 유리 두께·면밀도·허용 굽힘응력.
LAMINATE_T_MM = 3.2
LAMINATE_KG_M2 = 11.0
GLASS_E_MPA = 70_000.0
GLASS_ALLOW_MPA = 30.0

# ── 장변 인발 롤러 ──────────────────────────────────────────────────────
#: 장변 압출재 바깥면 홈 (mm) — 열림 높이(Y) × 깊이(Z).
GROOVE_H_MM = 20
GROOVE_D_MM = 14
#: 홈 안에서 롤러가 쓰는 여유 (mm, 편측).
ROLLER_CLEAR_MM = 2

#: 규격 트랙롤러(스터드형 캠팔로워) 계열 — (외경, 폭) mm. 임의 치수를 만들지 않고
#: 여기서 고른다. 롤러 축은 수직(Y)이라 **폭이 홈 열림 높이**에 걸리고, 외경은
#: 홈 바닥까지 닿아 프레임을 바깥으로 미는 면을 만든다.
TRACK_ROLLERS_MM: tuple[tuple[int, int], ...] = (
    (16, 11), (19, 12), (22, 12), (26, 12), (30, 14), (32, 14),
    (35, 18), (40, 20), (47, 24), (52, 24),
)
#: 외경 상한 배수 — 롤러가 홈 밖으로 나오는 양이 홈 깊이를 넘으면 하중선이
#: 프로파일 면에서 너무 떨어져 압출재를 비튼다.
ROLLER_PROTRUSION_RATIO = 2

#: 롤러 재질 조합 — 경화강 롤러가 6063 알루미늄 홈 벽을 구른다.
ROLLER_E_MPA = 210_000.0
ROLLER_NU = 0.30
ALU_E_MPA = frames.YOUNGS_MODULUS_MPA
ALU_NU = 0.33
#: 선접촉 구름에서 최대접촉압 p_max 의 첫 항복 배수 — τ_max = 0.300·p_max,
#: Tresca 항복 τ = σ_y/2 → p_max(항복) = σ_y / (2 × 0.300).
HERTZ_SHEAR_COEFF = 0.300
#: 구름접촉 설계계수 — 압흔이 남으면 홈이 커져 롤러가 빠진다.
ROLLER_DESIGN_FACTOR = 1.25

#: LM 캐리지 — 장변 한 변당 기수와 전체 행정 (mm).
CARRIAGE_PER_SIDE = 2
LM_STROKE_MM = 1300
#: LM 주행속도 (mm/s) — 원본 도면값.
LM_SPEED_MM_S = 235.0
#: LM 레일 z (mm).
LM_RAIL_Z_MM = 980

#: 장변 프레임을 바깥으로 당기는 거리 (mm). 단변과 같은 이탈 조건을 쓴다.
#: (프레임 폭 + 이탈 여유)

# ── 프레임 단면 (3D 가 그리는 외형) ─────────────────────────────────────
#: 프레임 겉치수 (mm) — 폭(패널 안쪽으로 물리는 방향) × 높이. 높이는 모듈 단면
#: 높이(kinematics)를 그대로 쓴다 — 3D 가 105 로 그리는 바람에 프레임 윗면이
#: 유리면보다 70 mm 솟아 있었고, 그러면 정반이 내려올 자리가 없다.
FRAME_W_MM = 75
FRAME_H_MM = kinematics.PANEL_FRAME_H_MM


# ── 정반 파생값 ──────────────────────────────────────────────────────────
def platen_steel_fraction() -> float:
    """정반 단면에서 강재가 차지하는 비율 — 상·하판 + 코어의 직교 리브."""
    core = PLATEN_T_MM - 2 * PLATEN_SKIN_T_MM
    skin = 2 * PLATEN_SKIN_T_MM / PLATEN_T_MM
    rib = 2 * (PLATEN_RIB_T_MM / PLATEN_RIB_PITCH_MM) * (core / PLATEN_T_MM)
    return round(skin + rib, 3)


def platen_solid_mass_kg() -> float:
    """통짜로 만들었을 때의 질량 — 왜 리브로 가는지 보이는 비교값."""
    v = (PLATEN_X_MM * PLATEN_Z_MM * PLATEN_T_MM) / 1e9
    return round(v * STEEL_DENSITY_KG_M3, 1)


def platen_mass_kg() -> float:
    """정반 1매 질량 — 리브 웰드먼트 기준."""
    return round(platen_solid_mass_kg() * platen_steel_fraction(), 1)


def platen_weight_kn() -> float:
    return round(platen_mass_kg() * 9.81 / 1000.0, 2)


def clamp_capacity_kn() -> float:
    """정반 1매를 매다는 클램프 실린더 용량 — 4점 클램프를 정반당 둘로 나눈다."""
    return round(kinematics.AFR_CLAMP_KN * kinematics.AFR_CLAMP_UNITS
                 / PLATEN_COUNT, 2)


def clamp_net_kn() -> float:
    """정반 자중을 뺀, 실제로 패널을 누르는 힘."""
    return round(clamp_capacity_kn() - platen_weight_kn(), 2)


def clamp_holds_the_platen() -> bool:
    """클램프가 정반을 들고도 패널을 누를 힘이 남는가."""
    return clamp_net_kn() > 0


def platen_assembly_drop_mm() -> int:
    """정반 조립체에서 가장 낮은 것 — 쇠막대 밑면이 유리면보다 이만큼 아래다.

    쇠막대는 프레임 밑면까지 내려와야 단변을 옆면 전체로 민다. 그래서 정반이
    들려야 하는 높이는 판 두께가 아니라 **이 막대 밑면**이 정한다.
    """
    return FRAME_H_MM


def platen_lift_mm() -> int:
    """정반 승강 행정 — 체인이 들어 올린 패널 위로 조립체 전체가 빠져야 한다."""
    return CHAIN_LIFT_MM + platen_assembly_drop_mm() + PLATEN_CLEAR_MM


def platen_descent_time_s() -> float:
    return round(platen_lift_mm() / PLATEN_SPEED_MM_S, 2)


def chain_rise_time_s() -> float:
    return round(chain_rise_mm() / PLATEN_SPEED_MM_S, 2)


def push_reaction_kn() -> float:
    """실린더가 밀 때 정반이 받는 반작용 — 패널 중심을 향한다."""
    return required_push_kn()


def reaction_is_self_balanced() -> bool:
    """두 정반이 동시에 밀면 반작용이 크로스헤드 안에서 상쇄된다.

    동시가 아니면 포탈 기둥이 25 kN 을 통째로 받는다 — 그래서 동시 밀기가
    구조 요구사항이지 편의가 아니다.
    """
    return PLATEN_COUNT == 2


def portal_unbalanced_kn() -> float:
    """동기 실패 시 포탈로 새는 수평력."""
    return 0.0 if reaction_is_self_balanced() else push_reaction_kn()


def cylinder_span_mm() -> int:
    """실린더 두 본 사이 거리 — 정반 세로에서 양끝 인셋을 뺀 것."""
    return PLATEN_Z_MM - 2 * CYL_INSET_MM


def cylinder_z_mm() -> tuple[float, float]:
    """실린더 중심의 z 좌표 (mm)."""
    half = cylinder_span_mm() / 2.0
    return (-half, half)


def max_barrel_od_mm() -> int:
    """정반 두께가 허용하는 배럴 외경 상한."""
    return PLATEN_T_MM - 2 * MIN_PLATEN_WALL_MM - 2 * POCKET_CLEAR_MM


def max_bore_mm() -> int:
    """배럴 상한에서 나오는 보어 상한."""
    return max_barrel_od_mm() - 2 * BARREL_WALL_MM


def bore_mm() -> int:
    """실제로 고르는 표준 보어 — 상한을 넘지 않는 가장 큰 계열값."""
    fits = [b for b in ISO_BORES_MM if b <= max_bore_mm()]
    if not fits:
        raise ValueError("정반 두께가 표준 보어를 하나도 못 담는다")
    return fits[-1]


def rod_mm() -> int:
    return ISO_RODS_MM[bore_mm()]


def barrel_od_mm() -> int:
    return bore_mm() + 2 * BARREL_WALL_MM


def pocket_od_mm() -> int:
    return barrel_od_mm() + 2 * POCKET_CLEAR_MM


def platen_wall_mm() -> float:
    """포켓 위아래에 남는 정반 살 (mm)."""
    return round((PLATEN_T_MM - pocket_od_mm()) / 2.0, 1)


def cylinder_fits_in_platen() -> bool:
    return platen_wall_mm() >= MIN_PLATEN_WALL_MM


def piston_area_mm2() -> float:
    return round(math.pi / 4.0 * bore_mm() ** 2, 1)


def required_push_kn() -> float:
    """단변 하나를 밀어내는 데 필요한 힘 — 원본 인발력 사양을 그대로 쓴다."""
    return kinematics.AFR_PULL_KN


def working_pressure_bar() -> float:
    """정반당 실린더 둘이 required_push_kn 을 내는 작동압."""
    n = required_push_kn() * 1000.0
    return round(n / (CYL_PER_PLATEN * piston_area_mm2()) * 10.0, 1)


def relief_capacity_kn() -> float:
    """릴리프 압력에서 정반당 낼 수 있는 최대 추력."""
    return round(HPU_RELIEF_BAR / 10.0 * piston_area_mm2() * CYL_PER_PLATEN / 1000.0, 1)


def pressure_is_within_relief() -> bool:
    """작동압이 릴리프에서 설계계수만큼 떨어져 있는가."""
    return working_pressure_bar() * PRESSURE_MARGIN <= HPU_RELIEF_BAR


# ── 쇠막대 파생값 ────────────────────────────────────────────────────────
def bar_length_mm() -> int:
    """쇠막대 길이 — 단변 전체를 한 번에 밀어야 하므로 정반 세로와 같다."""
    return PLATEN_Z_MM


def bar_line_load_n_per_mm() -> float:
    """쇠막대가 받는 등분포 반력 — 추력을 막대 길이로 나눈 것."""
    return round(required_push_kn() * 1000.0 / bar_length_mm(), 3)


def bar_h_mm() -> int:
    """쇠막대 높이 — 로드 축(정반 두께 절반)에서 프레임 밑면까지."""
    return FRAME_H_MM + PLATEN_T_MM // 2


def bar_second_moment_mm4() -> float:
    return round(BAR_W_MM * bar_h_mm() ** 3 / 12.0, 1)


def bar_moment_n_mm() -> float:
    """실린더 두 본을 지점으로 본 등분포 보의 최대 모멘트.

    스팬 중앙 처짐모멘트 wL²/8 에서 오버행이 만드는 부모멘트 wa²/2 를 뺀다.
    """
    w = bar_line_load_n_per_mm()
    span = cylinder_span_mm()
    over = CYL_INSET_MM
    return round(w * span ** 2 / 8.0 - w * over ** 2 / 2.0, 1)


def bar_stress_mpa() -> float:
    return round(bar_moment_n_mm() * (bar_h_mm() / 2.0) / bar_second_moment_mm4(), 1)


def bar_sag_mm() -> float:
    """스팬 중앙 처짐 — 가운데가 이만큼 뒤처져 단변을 민다."""
    w = bar_line_load_n_per_mm()
    span = cylinder_span_mm()
    return round(5.0 * w * span ** 4 / (384.0 * STEEL_E_MPA * bar_second_moment_mm4()), 3)


def bar_sag_limit_mm() -> float:
    return round(cylinder_span_mm() / BAR_SAG_LIMIT_RATIO, 3)


def bar_pushes_the_whole_edge() -> bool:
    """쇠막대가 단변 전체를 한 몸으로 밀어내는가 — 응력과 처짐 둘 다."""
    return (bar_stress_mpa() <= STEEL_ALLOW_MPA
            and bar_sag_mm() <= bar_sag_limit_mm())


def bar_mass_kg() -> float:
    v = (BAR_W_MM * bar_h_mm() * bar_length_mm()) / 1e9
    return round(v * STEEL_DENSITY_KG_M3, 1)


# ── 밀어내는 거리와 스토퍼 ───────────────────────────────────────────────
def push_travel_mm() -> int:
    """프레임을 미는 거리 — 라미네이트에서 완전히 빠지고 스토퍼 립에 걸릴 만큼."""
    return FRAME_W_MM + FRAME_RELEASE_CLEAR_MM


def push_time_s() -> float:
    return round(push_travel_mm() / CYL_SPEED_MM_S, 2)


def retract_time_s() -> float:
    """복귀 행정 — 로드측 유효면적이 작아 같은 유량에서 더 빠르다."""
    ratio = bore_mm() ** 2 / (bore_mm() ** 2 - rod_mm() ** 2)
    return round(push_travel_mm() / (CYL_SPEED_MM_S * ratio), 2)


def stroke_spare_mm() -> int:
    """행정에서 실제로 쓰고 남는 여유."""
    return CYL_STROKE_MM - push_travel_mm()


def stopper_face_mm() -> float:
    """스토퍼 캐치면의 x (mm, 플랜트 중심 기준). 밀려온 프레임 앞면이 여기 선다."""
    return kinematics.PANEL_MM[0] / 2.0 + push_travel_mm()


def stopper_catches_the_frame() -> bool:
    """립이 프레임 높이 안에서 걸리는가 — 넘어가면 정지가 아니라 낙하다."""
    return 0 < STOPPER_LIP_MM < FRAME_H_MM and stroke_spare_mm() > 0


# ── 정반의 긴 홈과 톱니 컨베이어 ─────────────────────────────────────────
def support_rows_z_mm() -> tuple[int, ...]:
    """지지열의 z — 바깥 열은 장변 프레임 안쪽에서 여유를 두고 멈춘다."""
    outer = (kinematics.PANEL_MM[1] // 2 - FRAME_W_MM - PAD_EDGE_CLEAR_MM
             - SUPPORT_PAD_Z_MM // 2)
    return (-outer, 0, outer)


def pads_clear_the_frames() -> bool:
    """바깥 패드가 장변 프레임 밑으로 들어가지 않는가."""
    outer = max(support_rows_z_mm()) + SUPPORT_PAD_Z_MM / 2
    return outer + PAD_EDGE_CLEAR_MM <= kinematics.PANEL_MM[1] / 2 - FRAME_W_MM


def slot_z_mm() -> tuple[int, ...]:
    """긴 홈의 중심 z — 지지열마다 하나. 홈이 패드를 앞뒤로 가른다."""
    return support_rows_z_mm()


def chain_runs() -> int:
    return len(slot_z_mm())


def split_pad_z_mm() -> float:
    """홈이 가른 패드 반쪽의 중심 오프셋 (mm)."""
    return round((SLOT_W_MM + (SUPPORT_PAD_Z_MM - SLOT_W_MM) / 2.0) / 2.0, 1)


def split_pad_depth_mm() -> float:
    """반쪽 패드의 z 깊이 (mm)."""
    return round((SUPPORT_PAD_Z_MM - SLOT_W_MM) / 2.0, 1)


def support_zones() -> int:
    """지지 구역 수 — 홈이 패드를 갈라도 한 구역은 한 구역이다."""
    return len(support_rows_z_mm()) * len(SUPPORT_COLS_X_MM)


def slot_clears_the_pads() -> bool:
    """홈이 패드 안에서만 나 있는가 — 패드를 벗어나면 지지면이 끊긴다."""
    return SLOT_W_MM < SUPPORT_PAD_Z_MM and split_pad_depth_mm() > 0


def slot_spans_the_panel() -> bool:
    return SLOT_L_MM > kinematics.PANEL_MM[0]


def sprocket_pitch_d_mm() -> float:
    """스프로킷 피치원 지름 — p / sin(π/z)."""
    return round(CHAIN_PITCH_MM / math.sin(math.pi / SPROCKET_TEETH), 1)


def chain_rise_mm() -> int:
    """체인이 대기위치에서 들어 올리기까지 올라오는 높이."""
    return CHAIN_PARK_MM + CHAIN_LIFT_MM


def laminate_line_load_n_per_mm() -> float:
    """폭 1 mm 띠로 본 무프레임 라미네이트 자중 (N/mm)."""
    return round(LAMINATE_KG_M2 * 9.81 / 1e6, 8)


def laminate_strip_i_mm4() -> float:
    return round(LAMINATE_T_MM ** 3 / 12.0, 4)


def laminate_overhang_mm() -> float:
    """바깥 체인런에서 패널 가장자리까지 — 여기가 외팔보다."""
    return kinematics.PANEL_MM[1] / 2.0 - max(slot_z_mm())


def laminate_span_mm() -> int:
    """이웃한 체인런 사이 거리."""
    zs = sorted(slot_z_mm())
    return min(b - a for a, b in zip(zs, zs[1:]))


def laminate_overhang_sag_mm() -> float:
    w = laminate_line_load_n_per_mm()
    length = laminate_overhang_mm()
    return round(w * length ** 4 / (8.0 * GLASS_E_MPA * laminate_strip_i_mm4()), 3)


def laminate_span_sag_mm() -> float:
    w = laminate_line_load_n_per_mm()
    length = laminate_span_mm()
    return round(5.0 * w * length ** 4
                 / (384.0 * GLASS_E_MPA * laminate_strip_i_mm4()), 3)


def laminate_stress_mpa() -> float:
    """외팔보 고정단 응력 — 체인런 위에서 가장 크다."""
    w = laminate_line_load_n_per_mm()
    length = laminate_overhang_mm()
    return round(w * length ** 2 / 2.0 * (LAMINATE_T_MM / 2.0)
                 / laminate_strip_i_mm4(), 2)


def chain_carries_the_laminate() -> bool:
    """무프레임 유리가 체인 위에서 안전한가."""
    return (laminate_stress_mpa() <= GLASS_ALLOW_MPA
            and slot_clears_the_pads() and slot_spans_the_panel())


def transfer_time_s() -> float:
    """패널이 셀을 빠져나가는 시간."""
    return round(SLOT_L_MM / CHAIN_SPEED_MM_S, 2)


# ── 장변 인발 롤러 ───────────────────────────────────────────────────────
def selected_roller() -> tuple[int, int]:
    """홈에 들어가는 가장 큰 규격 트랙롤러 — 클수록 접촉압이 낮다.

    두 조건이 고른다. ① 폭이 홈 열림에서 여유를 뺀 값 이하여야 홈으로 들어간다.
    ② 외경이 홈 깊이의 ROLLER_PROTRUSION_RATIO 배 이하여야 하중선이 면에서
    멀어지지 않는다.
    """
    limit_w = GROOVE_H_MM - 2 * ROLLER_CLEAR_MM
    limit_d = GROOVE_D_MM * ROLLER_PROTRUSION_RATIO
    fits = [(d, w) for d, w in TRACK_ROLLERS_MM if w <= limit_w and d <= limit_d]
    if not fits:
        raise ValueError("홈 치수가 규격 트랙롤러를 하나도 못 받는다")
    return fits[-1]


def roller_d_mm() -> int:
    return selected_roller()[0]


def roller_h_mm() -> int:
    """롤러 폭 — 홈 벽과 만드는 선접촉의 길이다."""
    return selected_roller()[1]


def roller_protrusion_mm() -> int:
    """롤러가 홈 밖으로 나오는 양 — 바닥에 닿았을 때."""
    return roller_d_mm() - GROOVE_D_MM


def roller_axis_z_mm() -> float:
    """롤러 축의 z (mm, 패널 중심 기준) — 홈 바닥에 닿았을 때."""
    return kinematics.PANEL_MM[1] / 2.0 - GROOVE_D_MM + roller_d_mm() / 2.0


def contact_modulus_mpa() -> float:
    """등가 탄성계수 E* — 경화강 롤러 대 6063 알루미늄 홈벽."""
    inv = (1 - ROLLER_NU ** 2) / ROLLER_E_MPA + (1 - ALU_NU ** 2) / ALU_E_MPA
    return round(1.0 / inv, 1)


def rolling_yield_mpa() -> float:
    """선접촉 구름에서 알루미늄이 항복하기 시작하는 최대접촉압."""
    return round(frames.YIELD_MPA / (2.0 * HERTZ_SHEAR_COEFF), 1)


def roller_allow_mpa() -> float:
    return round(rolling_yield_mpa() / ROLLER_DESIGN_FACTOR, 1)


def roller_capacity_n() -> float:
    """롤러 한 개가 홈 벽에 낼 수 있는 하중 — p_max 허용치에서 역산."""
    p = roller_allow_mpa()
    r = roller_d_mm() / 2.0
    return round(p ** 2 * math.pi * r / contact_modulus_mpa() * roller_h_mm(), 1)


def rollers_per_carriage() -> int:
    """캐리지 하나에 필요한 롤러 수 — 인발력을 압흔 없이 나눠 받는 최소 개수."""
    return math.ceil(frames.PEEL_FORCE_N / roller_capacity_n())


def roller_contact_mpa() -> float:
    """실제 롤러 한 개가 받는 최대접촉압."""
    f = frames.PEEL_FORCE_N / rollers_per_carriage()
    fl = f / roller_h_mm()
    r = roller_d_mm() / 2.0
    return round(math.sqrt(fl * contact_modulus_mpa() / (math.pi * r)), 1)


def roller_leaves_no_brinell() -> bool:
    return roller_contact_mpa() <= roller_allow_mpa()


def roller_fits_the_groove() -> bool:
    """폭이 열림을 지나고, 바닥에 닿고, 하중선이 면에서 멀어지지 않는가."""
    return (roller_h_mm() + 2 * ROLLER_CLEAR_MM <= GROOVE_H_MM
            and roller_protrusion_mm() > 0
            and roller_protrusion_mm() <= GROOVE_D_MM * (ROLLER_PROTRUSION_RATIO - 1))


def pull_travel_mm() -> int:
    """장변을 바깥으로 당기는 거리 — 단변과 같은 이탈 조건."""
    return push_travel_mm()


def roller_reach_mm() -> float:
    """롤러 암이 캐리지에서 홈까지 뻗는 거리 (mm)."""
    return round(LM_RAIL_Z_MM - roller_axis_z_mm(), 1)


def lm_travel_time_s() -> float:
    return round(LM_STROKE_MM / LM_SPEED_MM_S, 2)


def peeled_length_mm() -> float:
    """캐리지 한 대가 실제로 벗기는 길이 — 양끝에서 안쪽으로."""
    return kinematics.PANEL_MM[0] / (CARRIAGE_PER_SIDE * 2.0)


# ── "휘지 않고 직선으로" — 발주처 문장의 검증 ─────────────────────────────
def frame_linear_mass_kg_m() -> float:
    """장변 각관 단위길이 질량 (kg/m)."""
    area = (frames.SECTION_B_MM * frames.SECTION_H_MM
            - (frames.SECTION_B_MM - 2 * frames.SECTION_T_MM)
            * (frames.SECTION_H_MM - 2 * frames.SECTION_T_MM))
    return round(area * 2.70e-3, 4)          # g/mm = kg/m


def released_length_mm() -> float:
    """롤러 뒤로 이미 떨어져 매달린 길이 — 캐리지 하나가 벗긴 만큼이다."""
    return peeled_length_mm()


def self_weight_sag_mm() -> float:
    """떨어진 부분이 자중으로 처지는 양 — 인발력이 안 걸린 자유단이다."""
    w = frame_linear_mass_kg_m() * 9.81 / 1000.0        # N/mm
    length = released_length_mm()
    return round(w * length ** 4
                 / (8.0 * frames.YOUNGS_MODULUS_MPA * frames.second_moment_mm4()), 3)


def roller_free_length_mm() -> float:
    """롤러와 접착 전선 사이 자유 길이 — 홈에 걸려 같이 가므로 롤러 반지름뿐이다."""
    return round(roller_d_mm() / 2.0, 1)


def drops_straight() -> bool:
    """발주처 문장의 검증 — 자중 처짐이 프레임 높이의 1/20 아래면 직선이다."""
    return self_weight_sag_mm() <= frames.SECTION_H_MM / 20.0


def display_bow_mm() -> float:
    """3D 가 그리는 장변 휨 (mm) — 자중 처짐에 프레임 과장배율을 곱한 것."""
    return round(self_weight_sag_mm() * frames.DISPLAY_EXAGGERATION, 1)


def short_edge_lag_mm() -> float:
    """단변이 밀려날 때 가운데가 뒤처지는 양 — 쇠막대 처짐이 그대로 나온다."""
    return bar_sag_mm()


def short_edge_display_bow_mm() -> float:
    return round(short_edge_lag_mm() * frames.DISPLAY_EXAGGERATION, 1)


# ── 도면·콘솔이 읽는 요약 ────────────────────────────────────────────────
def cylinder_spec() -> str:
    return (f"Ø{bore_mm()}/{rod_mm()}×{CYL_STROKE_MM} mm × "
            f"{CYL_PER_PLATEN}본/정반 · {working_pressure_bar():.0f} bar")


def summary() -> dict[str, object]:
    return {
        "platenMm": [PLATEN_X_MM, PLATEN_Z_MM, PLATEN_T_MM],
        "platenCount": PLATEN_COUNT,
        "platenMassKg": platen_mass_kg(),
        "platenSolidMassKg": platen_solid_mass_kg(),
        "platenSteelFraction": platen_steel_fraction(),
        "clampCapacityKn": clamp_capacity_kn(),
        "clampNetKn": clamp_net_kn(),
        "platenDescentS": platen_descent_time_s(),
        "pushReactionKn": push_reaction_kn(),
        "platenLiftMm": platen_lift_mm(),
        "platenAssemblyDropMm": platen_assembly_drop_mm(),
        "chainRiseS": chain_rise_time_s(),
        "cylInsetMm": CYL_INSET_MM,
        "cylSpanMm": cylinder_span_mm(),
        "cylPerPlaten": CYL_PER_PLATEN,
        "maxBoreMm": max_bore_mm(),
        "boreMm": bore_mm(),
        "rodMm": rod_mm(),
        "platenWallMm": platen_wall_mm(),
        "workingBar": working_pressure_bar(),
        "reliefCapacityKn": relief_capacity_kn(),
        "barMm": [BAR_W_MM, bar_h_mm(), bar_length_mm()],
        "barMassKg": bar_mass_kg(),
        "barStressMpa": bar_stress_mpa(),
        "barSagMm": bar_sag_mm(),
        "barSagLimitMm": bar_sag_limit_mm(),
        "pushTravelMm": push_travel_mm(),
        "pushTimeS": push_time_s(),
        "retractTimeS": retract_time_s(),
        "supportRowsZMm": list(support_rows_z_mm()),
        "frameHMm": FRAME_H_MM,
        "barHMm": bar_h_mm(),
        "strokeSpareMm": stroke_spare_mm(),
        "stopperFaceMm": stopper_face_mm(),
        "stopperLipMm": STOPPER_LIP_MM,
        "slotZMm": list(slot_z_mm()),
        "slotWMm": SLOT_W_MM,
        "slotLMm": SLOT_L_MM,
        "chainRuns": chain_runs(),
        "sprocketPitchDMm": sprocket_pitch_d_mm(),
        "chainRiseMm": chain_rise_mm(),
        "laminateSagMm": laminate_overhang_sag_mm(),
        "laminateSpanSagMm": laminate_span_sag_mm(),
        "laminateStressMpa": laminate_stress_mpa(),
        "transferTimeS": transfer_time_s(),
        "grooveMm": [GROOVE_H_MM, GROOVE_D_MM],
        "rollerDMm": roller_d_mm(),
        "rollerProtrusionMm": roller_protrusion_mm(),
        "rollerAxisZMm": roller_axis_z_mm(),
        "rollerHMm": roller_h_mm(),
        "rollersPerCarriage": rollers_per_carriage(),
        "rollerContactMpa": roller_contact_mpa(),
        "rollerAllowMpa": roller_allow_mpa(),
        "pullTravelMm": pull_travel_mm(),
        "rollerReachMm": roller_reach_mm(),
        "lmStrokeMm": LM_STROKE_MM,
        "lmTravelTimeS": lm_travel_time_s(),
        "selfWeightSagMm": self_weight_sag_mm(),
        "rollerFreeLengthMm": roller_free_length_mm(),
        "displayBowMm": display_bow_mm(),
        "shortEdgeBowMm": short_edge_display_bow_mm(),
        "cylinderSpec": cylinder_spec(),
    }
