"""알루미늄 프레임의 탄성 휨 — 인발 중 얼마나 휘고, 어디서 항복하는가.

프레임은 강체가 아니라 탄성체다. 인발 롤러가 접착 전선(bond front)에서 멀어질수록
자유 길이가 길어지고, 그 길이의 **세제곱**으로 처짐이 커진다. 어느 지점을 넘으면
굽힘응력이 항복을 넘어 **영구 변형**이 남고, 그러면 프레임은 회수 후 재사용도
정형 배출도 어려워진다. 그래서 "롤러가 접착 전선을 얼마나 바짝 따라가야 하는가"가
설계 수치로 나와야 한다.

모델 (외팔보, 선단 하중)

* δ = F·L³ / (3·E·I)
* σ = F·L·c / I  (선단 하중 외팔보의 고정단 굽힘응력)
* 항복 전 최대 자유 길이 L_max = σ_y·I / (F·c)

단면은 태양광 모듈에 흔한 각형 알루미늄 압출재다. 값은 실측 전 계획값이며,
실제 프레임 단면과 접착 사양이 확정되면 여기만 고치면 도면·영상이 따라온다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import kinematics

#: 알루미늄 탄성계수 (MPa) — 6xxx 계열
YOUNGS_MODULUS_MPA = 69_000.0

#: 항복강도 (MPa) — 6063-T5 기준 보수값
YIELD_MPA = 160.0

#: 프레임 각관 외형 (mm) — 굽힘 방향 높이 h, 폭 b, 살두께 t
SECTION_H_MM = 35.0
SECTION_B_MM = 40.0
SECTION_T_MM = 1.5

#: 인발 롤러 1대가 접착면에서 프레임을 떼는 계획 하중 (N)
PEEL_FORCE_N = 1_200.0

#: 설계 자유 길이 (mm) — 롤러가 접착 전선을 따라가는 거리
DESIGN_FREE_LENGTH_MM = 220.0

#: 영상에서 휨을 보이게 하는 과장 배율. 실제 처짐은 mm 단위라 플랜트 축척에서
#: 보이지 않는다 — 배율을 명시해 두고 화면에도 적는다.
DISPLAY_EXAGGERATION = 40.0


@dataclass(frozen=True)
class BeamCheck:
    free_length_mm: float
    deflection_mm: float
    stress_mpa: float
    yields: bool


def second_moment_mm4() -> float:
    """각관 단면 2차 모멘트 (mm⁴) — 굽힘은 높이 h 방향."""
    inner_h = SECTION_H_MM - 2 * SECTION_T_MM
    inner_b = SECTION_B_MM - 2 * SECTION_T_MM
    return round((SECTION_B_MM * SECTION_H_MM ** 3 - inner_b * inner_h ** 3) / 12.0, 1)


def deflection_mm(free_length_mm: float, force_n: float = PEEL_FORCE_N) -> float:
    """선단 하중 외팔보 처짐."""
    return round(force_n * free_length_mm ** 3
                 / (3.0 * YOUNGS_MODULUS_MPA * second_moment_mm4()), 3)


def stress_mpa(free_length_mm: float, force_n: float = PEEL_FORCE_N) -> float:
    """고정단 굽힘응력."""
    return round(force_n * free_length_mm * (SECTION_H_MM / 2.0) / second_moment_mm4(), 1)


def max_free_length_mm(force_n: float = PEEL_FORCE_N) -> float:
    """항복하지 않는 최대 자유 길이 — 롤러가 접착 전선에서 떨어질 수 있는 한계."""
    return round(YIELD_MPA * second_moment_mm4() / (force_n * (SECTION_H_MM / 2.0)), 1)


def check(free_length_mm: float = DESIGN_FREE_LENGTH_MM,
          force_n: float = PEEL_FORCE_N) -> BeamCheck:
    stress = stress_mpa(free_length_mm, force_n)
    return BeamCheck(free_length_mm, deflection_mm(free_length_mm, force_n),
                     stress, stress > YIELD_MPA)


def design_margin() -> float:
    """설계 자유 길이 대비 항복 한계의 여유 배수."""
    return round(max_free_length_mm() / DESIGN_FREE_LENGTH_MM, 2)


def display_bow_mm() -> float:
    """영상에 그리는 휨 크기 (mm) — 실제 처짐 × 과장배율."""
    return round(check().deflection_mm * DISPLAY_EXAGGERATION, 1)


def springs_back() -> bool:
    """설계 조건에서 탄성 복원하는가 — 영구 변형이 남으면 안 된다."""
    return not check().yields


# ── 실물 압출재 단면 (REV.58) ────────────────────────────────────────────
# 위의 닫힌식은 40 × 35 × 1.5 각관을 가정했는데, 3D 와 배치 모델은 같은 프레임을
# **75 × 75** 로 그리고 있었다 (`afr.FRAME_W_MM` · `kinematics.PANEL_FRAME_H_MM`).
# 두 값이 갈라진 채로는 "영상에서 휘는 모양"이 계산과 다른 물건의 것이 된다.
#
# 그래서 단면을 **하나의 다각형**으로 정의하고 면적·도심·단면 2차 모멘트를 전부
# 거기서 뽑는다. 같은 다각형을 3D 가 그대로 스윕하므로, 화면이 그리는 단면과
# 계산이 쓴 단면이 어긋날 수 없다.
#
# 형상은 태양광 모듈에 흔한 "E" 꼴 C-채널이다 — 바깥 스파인에 유리 슬롯·중간
# 립·바닥 플랜지 셋이 안쪽으로 뻗고, 스파인 바깥면 중간에 인발 롤러가 들어가는
# 홈이 접혀 있다. 살두께·립 치수는 실측 전 계획값이며, 실제 압출재 도면이 오면
# 여기 숫자만 고치면 계산·도면·영상이 같이 따라온다.

#: 프레임 겉치수 (mm) — 폭(패널 안쪽으로) × 높이. 배치 모델의 모듈 단면 높이를 쓴다.
PROFILE_W_MM = 75.0
PROFILE_H_MM = float(kinematics.PANEL_FRAME_H_MM)

#: 압출 살두께 (mm) — 6063-T5, 75 mm 급 프레임의 통상 상단값.
WALL_T_MM = 2.4

#: 유리 슬롯 (mm) — 라미네이트 적층 두께 + 실란트 양면.
LAMINATE_STACK_MM = 5.5
SEALANT_T_MM = 1.5
SLOT_H_MM = LAMINATE_STACK_MM + 2 * SEALANT_T_MM

#: 안쪽으로 뻗는 세 갈래의 도달 거리 (mm) — 상부 플랜지 · 슬롯 하부 립 · 바닥 플랜지.
TOP_FLANGE_MM = 24.0
SLOT_LIP_MM = 20.0
BOTTOM_FLANGE_MM = PROFILE_W_MM

#: 바닥 플랜지 안쪽 끝의 되꺾음 립 높이 (mm) — 플랜지 좌굴을 막는다.
RETURN_LIP_MM = 16.0

#: 인발 홈 — 열림 높이와 깊이 (mm). afr.GROOVE_H_MM · GROOVE_D_MM 과 같아야 하고
#: `afr.groove_matches_the_profile()` 이 그것을 검사한다.
GROOVE_H_MM = 20.0
GROOVE_D_MM = 14.0
#: 홈 열림의 아래 끝 (mm, 프레임 밑면 기준).
GROOVE_V0_MM = 30.0


def outline() -> tuple[tuple[float, float], ...]:
    """단면 외곽선 (u, v) — u 는 바깥면에서 패널 안쪽으로, v 는 밑면에서 위로.

    반시계 방향의 **단순 다각형**이다 (구멍이 없다). 그래서 넓이·2차 모멘트를
    신발끈 공식으로 바로 얻고, 3D 도 이 한 고리를 스윕하면 된다.
    """
    t, w, h = WALL_T_MM, PROFILE_W_MM, PROFILE_H_MM
    gd, g0, g1 = GROOVE_D_MM, GROOVE_V0_MM, GROOVE_V0_MM + GROOVE_H_MM
    slot0 = h - t - SLOT_H_MM - t          # 슬롯 하부 립의 아랫면
    return (
        (0.0, 0.0), (BOTTOM_FLANGE_MM, 0.0),                    # 바닥면
        (BOTTOM_FLANGE_MM, RETURN_LIP_MM),                      # 되꺾음 립 바깥면
        (BOTTOM_FLANGE_MM - t, RETURN_LIP_MM),                  # 립 윗면
        (BOTTOM_FLANGE_MM - t, t), (t, t),                      # 바닥 플랜지 윗면
        (t, g0 - t), (gd + t, g0 - t),                          # 홈 아래 웨브
        (gd + t, g1 + t), (t, g1 + t),                          # 홈 바닥 안쪽면 · 위 웨브
        (t, slot0), (SLOT_LIP_MM, slot0),                       # 슬롯 하부 립 아랫면
        (SLOT_LIP_MM, slot0 + t), (t, slot0 + t),               # 립 끝 · 슬롯 바닥
        (t, h - t), (TOP_FLANGE_MM, h - t),                     # 슬롯 뒷벽 · 천장
        (TOP_FLANGE_MM, h), (0.0, h),                           # 상부 플랜지 끝 · 윗면
        (0.0, g1), (gd, g1), (gd, g0), (0.0, g0),               # 바깥면과 접힌 홈
    )


def _polygon_properties(pts: tuple[tuple[float, float], ...]) -> dict[str, float]:
    """단순 다각형의 넓이·도심·도심축 2차 모멘트 (신발끈)."""
    a2 = cu = cv = iu = iv = 0.0
    n = len(pts)
    for i in range(n):
        u0, v0 = pts[i]
        u1, v1 = pts[(i + 1) % n]
        cross = u0 * v1 - u1 * v0
        a2 += cross
        cu += (u0 + u1) * cross
        cv += (v0 + v1) * cross
        iu += (u0 * u0 + u0 * u1 + u1 * u1) * cross
        iv += (v0 * v0 + v0 * v1 + v1 * v1) * cross
    area = a2 / 2.0
    sign = 1.0 if area >= 0 else -1.0
    area = abs(area)
    cu = sign * cu / (6.0 * area) if area else 0.0
    cv = sign * cv / (6.0 * area) if area else 0.0
    iu = sign * iu / 12.0 - area * cu * cu       # ∫u²dA (도심축)
    iv = sign * iv / 12.0 - area * cv * cv       # ∫v²dA (도심축)
    return {"area_mm2": area, "cu_mm": cu, "cv_mm": cv,
            "i_lateral_mm4": iu, "i_vertical_mm4": iv}


def profile() -> dict[str, float]:
    """단면 제원 — 넓이·도심·두 방향 2차 모멘트.

    `i_lateral_mm4` 는 **인발 방향**(패널 면 안에서 옆으로) 휨의 것이다 — 인발도
    밀어내기도 이 방향으로 일어나므로 영상에서 보이는 휨을 지배한다.
    `i_vertical_mm4` 는 자중 처짐(위아래) 쪽이다.
    """
    p = _polygon_properties(outline())
    p["u_max_mm"] = max(u for u, _ in outline())
    p["v_max_mm"] = max(v for _, v in outline())
    # 최외단 거리 — 인발 휨은 u 방향, 자중 휨은 v 방향이다.
    p["c_lateral_mm"] = max(p["cu_mm"], p["u_max_mm"] - p["cu_mm"])
    p["c_vertical_mm"] = max(p["cv_mm"], p["v_max_mm"] - p["cv_mm"])
    return {k: round(v, 4) for k, v in p.items()}


def profile_area_mm2() -> float:
    return profile()["area_mm2"]


def profile_mass_kg_m() -> float:
    """단위길이 질량 (kg/m) — 6063 알루미늄 2.70 g/cm³."""
    return round(profile_area_mm2() * 2.70e-3, 4)


def profile_i_lateral_mm4() -> float:
    """인발 방향 휨의 단면 2차 모멘트 — 영상의 휨을 지배한다."""
    return profile()["i_lateral_mm4"]


def profile_i_vertical_mm4() -> float:
    return profile()["i_vertical_mm4"]


def profile_ei_lateral() -> float:
    """인발 방향 휨강성 EI [N·mm²]."""
    return YOUNGS_MODULUS_MPA * profile_i_lateral_mm4()


def profile_ea() -> float:
    """축강성 EA [N]."""
    return YOUNGS_MODULUS_MPA * profile_area_mm2()


def wall_developed_mm() -> float:
    """살 전개길이 (mm) — 넓이 ÷ 살두께. 다각형이 제 두께를 갖는지 보는 검산이다."""
    return round(profile_area_mm2() / WALL_T_MM, 1)
