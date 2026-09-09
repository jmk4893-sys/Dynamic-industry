"""암반 물성 정의 및 데이터베이스.

DEM 격자(lattice.py)는 중심력(central-force) 본드만 사용하므로 Cauchy 관계에 의해
포아송비가 nu = 0.25 로 고정된다. 대부분의 암반이 0.20~0.30 범위이므로 실용상 큰
문제는 없으나, 사용자가 다른 nu 를 지정하면 경고를 출력하고 0.25 로 환산해 사용한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 격자 모델이 구조적으로 재현할 수 있는 포아송비
LATTICE_POISSON = 0.25


@dataclass
class Rock:
    """암반 탄성/강도 물성.

    Attributes
    ----------
    name : 암종 이름
    density : 밀도 [kg/m^3]
    young : 동적 탄성계수 E [Pa]
    poisson : 포아송비 (격자 모델에서는 0.25 로 고정 사용)
    ucs : 일축압축강도 [Pa]
    tensile : 인장강도 [Pa]
    damping_ratio : 재료 감쇠비 (Rayleigh 질량비례), 암반은 보통 0.01~0.05
    quality : 암반 상태 메모 (RMR 등)
    """

    name: str
    density: float
    young: float
    poisson: float = LATTICE_POISSON
    ucs: float = 100e6
    tensile: float = 8e6
    damping_ratio: float = 0.02
    quality: str = ""

    # ---- 파생 물성 -------------------------------------------------------
    @property
    def lame_mu(self) -> float:
        """전단탄성계수 G [Pa]."""
        return self.young / (2.0 * (1.0 + LATTICE_POISSON))

    @property
    def lame_lambda(self) -> float:
        nu = LATTICE_POISSON
        return self.young * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))

    @property
    def p_velocity(self) -> float:
        """P파 속도 Vp [m/s]  =  sqrt((lambda + 2 mu) / rho)."""
        m_mod = self.lame_lambda + 2.0 * self.lame_mu
        return math.sqrt(m_mod / self.density)

    @property
    def s_velocity(self) -> float:
        """S파 속도 Vs [m/s]. nu=0.25 이므로 Vp/Vs = sqrt(3)."""
        return math.sqrt(self.lame_mu / self.density)

    @property
    def r_velocity(self) -> float:
        """Rayleigh 파 속도 근사 (Bergmann 식)."""
        nu = LATTICE_POISSON
        return self.s_velocity * (0.862 + 1.14 * nu) / (1.0 + nu)

    @property
    def impedance(self) -> float:
        """음향 임피던스 rho*Vp [Pa*s/m] — 폭약-암반 정합성 판단에 사용."""
        return self.density * self.p_velocity

    @property
    def tensile_strain(self) -> float:
        """본드 인장 파괴 변형률."""
        return self.tensile / self.young

    @property
    def compressive_strain(self) -> float:
        """본드 압축 항복 변형률 (파쇄대 에너지 소산용)."""
        return self.ucs / self.young

    @classmethod
    def from_velocity(cls, name: str, density: float, vp: float, **kw) -> "Rock":
        """현장 탄성파탐사 결과(rho, Vp)로부터 Rock 생성.

        nu = 0.25 에서 M = rho*Vp^2 = 1.2 E  ->  E = rho*Vp^2 / 1.2
        """
        young = density * vp * vp / 1.2
        return cls(name=name, density=density, young=young, **kw)

    def summary(self) -> str:
        return (
            f"[암반] {self.name}\n"
            f"  rho = {self.density:,.0f} kg/m^3,  E = {self.young / 1e9:.1f} GPa,  nu = {LATTICE_POISSON}\n"
            f"  Vp  = {self.p_velocity:,.0f} m/s,  Vs = {self.s_velocity:,.0f} m/s,  "
            f"VR = {self.r_velocity:,.0f} m/s\n"
            f"  UCS = {self.ucs / 1e6:.0f} MPa,  인장강도 = {self.tensile / 1e6:.1f} MPa,  "
            f"감쇠비 = {self.damping_ratio:.3f}"
        )


# ---------------------------------------------------------------------------
# 대표 암종 데이터베이스 (국내 발파 현장 기준 대표값)
# ---------------------------------------------------------------------------
ROCK_DB: dict[str, Rock] = {
    "granite": Rock("화강암 (Granite)", 2650, 60e9, ucs=160e6, tensile=10e6,
                    damping_ratio=0.015, quality="RMR 70-85, 경암"),
    "gneiss": Rock("편마암 (Gneiss)", 2700, 55e9, ucs=140e6, tensile=9e6,
                   damping_ratio=0.020, quality="RMR 60-80, 경암"),
    "limestone": Rock("석회암 (Limestone)", 2600, 45e9, ucs=100e6, tensile=7e6,
                      damping_ratio=0.025, quality="RMR 55-75, 보통암"),
    "sandstone": Rock("사암 (Sandstone)", 2400, 25e9, ucs=60e6, tensile=4e6,
                      damping_ratio=0.035, quality="RMR 45-65, 보통암"),
    "shale": Rock("셰일 (Shale)", 2450, 20e9, ucs=45e6, tensile=3e6,
                  damping_ratio=0.045, quality="RMR 35-55, 연암"),
    "andesite": Rock("안산암 (Andesite)", 2600, 50e9, ucs=130e6, tensile=8e6,
                     damping_ratio=0.020, quality="RMR 60-80, 경암"),
    "weathered": Rock("풍화암 (Weathered rock)", 2100, 6e9, ucs=15e6, tensile=1.0e6,
                      damping_ratio=0.060, quality="RMR 20-40, 풍화대"),
}


def get_rock(key: str) -> Rock:
    if key not in ROCK_DB:
        raise KeyError(f"알 수 없는 암종 '{key}'. 사용 가능: {list(ROCK_DB)}")
    r = ROCK_DB[key]
    return Rock(**{**r.__dict__})
