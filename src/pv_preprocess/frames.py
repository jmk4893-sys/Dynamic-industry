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
