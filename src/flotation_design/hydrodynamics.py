"""기포·입자 수력학 수치해석.

설계 계산(사이징·물질수지)이 쓰는 속도상수는 문헌 회분식 데이터에 맞춘
경험값이다. 이 모듈은 그 속도상수가 **물리적으로 그럴듯한지** 제1원리로
검산한다 — 기포 상승속도(항력 반복해), 입자 침강속도, 기포-입자 충돌
효율(Yoon-Luttrell), 포집 속도상수. 순서는 다음과 같다.

1. 기포 지름과 물성으로 종말 상승속도를 구한다 (Schiller-Naumann 항력,
   오염 계면 가정 → 강체구).
2. 그 Reynolds 수로 충돌 효율 Ec 를 구한다 (Yoon & Luttrell, 1989).
3. 포집 속도상수 k = (3/2)·Ea·Ec·Jg/db 를 세운다 (Jameson 형).
4. 측정 속도상수(회분식 보정값)와 비교해 **부착 효율 Ea 를 역산**한다.
   Ea 가 문헌 범위(수십 µm 입자에서 0.1~0.3)에 들면 설계 속도상수는
   물리적으로 정합적이다.

전부 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: 물 (20 °C)
WATER_DENSITY_KG_M3 = 998.0
WATER_VISCOSITY_PA_S = 1.0e-3
GRAVITY_M_S2 = 9.81


def drag_coefficient(reynolds: float) -> float:
    """강체구 항력계수 — Schiller-Naumann (Re < 1000), 이후 0.44."""
    if reynolds <= 0.0:
        return math.inf
    if reynolds < 1000.0:
        return 24.0 / reynolds * (1.0 + 0.15 * reynolds**0.687)
    return 0.44


def terminal_velocity(
    diameter_m: float,
    density_kg_m3: float,
    fluid_density_kg_m3: float = WATER_DENSITY_KG_M3,
    viscosity_pa_s: float = WATER_VISCOSITY_PA_S,
) -> float:
    """구의 종말속도 (m/s, 상승이면 양수). 항력-부력 평형을 반복해로 푼다.

    기포는 포수제·기포제로 계면이 오염돼 강체구처럼 거동한다고 본다
    (부선 펄프의 표준 가정 — 청정 계면의 Hadamard-Rybczynski 보다 느리다).
    """
    drho = fluid_density_kg_m3 - density_kg_m3  # 양수면 상승
    if drho == 0.0:
        return 0.0
    # Stokes 초기추정 후 고정점 반복
    v = abs(drho) * GRAVITY_M_S2 * diameter_m**2 / (18.0 * viscosity_pa_s)
    for _ in range(100):
        re = fluid_density_kg_m3 * v * diameter_m / viscosity_pa_s
        cd = drag_coefficient(re)
        v_new = math.sqrt(
            4.0 * abs(drho) * GRAVITY_M_S2 * diameter_m / (3.0 * cd * fluid_density_kg_m3)
        )
        if abs(v_new - v) < 1e-10:
            v = v_new
            break
        v = 0.5 * (v + v_new)  # 감쇠 반복 — 진동 방지
    return math.copysign(v, drho)


def swarm_velocity(single_bubble_m_s: float, gas_holdup: float, n: float = 2.0) -> float:
    """기포군 상승속도 — Richardson-Zaki 형 보정 (1-εg)^n."""
    return single_bubble_m_s * (1.0 - gas_holdup) ** n


def collision_efficiency(
    particle_diameter_m: float, bubble_diameter_m: float, bubble_reynolds: float
) -> float:
    """Yoon-Luttrell (1989) 중간 Re 충돌 효율.

    Ec = (3/2 + 4 Re^0.72 / 15) (dp/db)^2
    """
    ratio = particle_diameter_m / bubble_diameter_m
    return (1.5 + 4.0 * bubble_reynolds**0.72 / 15.0) * ratio**2


def collection_rate_constant_1_min(
    attachment_efficiency: float,
    collision_eff: float,
    superficial_gas_velocity_m_s: float,
    bubble_diameter_m: float,
) -> float:
    """포집 속도상수 k (1/min) — Jameson 형.

    k = (3/2) · Ea · Ec · Jg / db
    """
    k_s = (
        1.5
        * attachment_efficiency
        * collision_eff
        * superficial_gas_velocity_m_s
        / bubble_diameter_m
    )
    return k_s * 60.0


@dataclass(frozen=True)
class HydroAnalysis:
    """한 셀의 수력학 검산 결과."""

    tag: str
    bubble_diameter_mm: float
    particle_diameter_um: float
    bubble_rise_m_s: float          # 단일 기포
    bubble_swarm_m_s: float         # 기포군 (홀드업 보정)
    bubble_reynolds: float
    particle_settling_mm_s: float
    collision_efficiency: float
    ideal_rate_constant_1_min: float   # Ea = 1 가정
    measured_rate_constant_1_min: float
    pulp_transit_s: float           # 기포가 펄프층을 지나는 시간

    @property
    def implied_attachment_efficiency(self) -> float:
        """측정 k 를 재현하는 부착 효율 Ea = k_meas / k_ideal."""
        return self.measured_rate_constant_1_min / self.ideal_rate_constant_1_min

    @property
    def is_physically_consistent(self) -> bool:
        """Ea 가 물리적 범위 (0 < Ea <= 1) 안에 있는지."""
        return 0.0 < self.implied_attachment_efficiency <= 1.0


def analyse_cell(
    tag: str,
    superficial_gas_velocity_cm_s: float,
    bubble_diameter_mm: float,
    gas_holdup: float,
    pulp_depth_m: float,
    measured_rate_constant_1_min: float,
    particle_diameter_um: float = 66.0,
    particle_sg: float = 2.42,
) -> HydroAnalysis:
    """셀 하나의 기포-입자 수력학을 검산한다.

    particle_diameter_um 기본값은 급광 P80 (66 µm),
    particle_sg 기본값은 급광 가중평균 비중이다.
    """
    db = bubble_diameter_mm / 1000.0
    dp = particle_diameter_um / 1e6
    v1 = terminal_velocity(db, 1.2)  # 공기
    vs = swarm_velocity(v1, gas_holdup)
    re = WATER_DENSITY_KG_M3 * v1 * db / WATER_VISCOSITY_PA_S
    ec = collision_efficiency(dp, db, re)
    k_ideal = collection_rate_constant_1_min(
        1.0, ec, superficial_gas_velocity_cm_s / 100.0, db
    )
    vp = terminal_velocity(dp, particle_sg * 1000.0)
    return HydroAnalysis(
        tag=tag,
        bubble_diameter_mm=bubble_diameter_mm,
        particle_diameter_um=particle_diameter_um,
        bubble_rise_m_s=v1,
        bubble_swarm_m_s=vs,
        bubble_reynolds=re,
        particle_settling_mm_s=abs(vp) * 1000.0,
        collision_efficiency=ec,
        ideal_rate_constant_1_min=k_ideal,
        measured_rate_constant_1_min=measured_rate_constant_1_min,
        pulp_transit_s=pulp_depth_m / vs if vs > 0 else math.inf,
    )
