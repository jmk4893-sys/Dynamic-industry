"""떨어진 EVA 분리 (ES-1 · ES-2) — 기포제만 쓰는 EVA 부선.

AS-1 이 입자에서 떼어 낸 EVA 는 슬러리에 섞여 나간다. 그대로 두면 부선조에서
정광으로 간다 — 비중 0.95 의 소수성 박편이라 포수제 없이도 뜬다. 이 설비는
희석박스(DB-1) 뒤, 조건조(CT-1) 앞에서 그것을 걷어낸다.

역할의 경계
----------
이 설비가 하는 일은 **떨어진 EVA 를 흐름에서 걷어내는 것** 하나다. EVA 를 입자에서
떼는 것은 AS-1, 은을 띄우는 것은 부선조가 한다. 은은 건드리지 않고 부선조로
보낸다 — 그래서 **포수제 앞**에 두고 기포제만 쓴다. 포수제가 없으면 Si·Al·Ag
표면은 물에 젖어 펄프에 남고, 본래 소수성인 EVA 만 기포에 붙는다.

판정은 둘이다.

- 부선 급광으로 넘어가는 자유 EVA — 고체의 ``EVA_FLOTATION_FEED_LIMIT`` 이하
- EVA 산물로 새는 Ag — ``EVA_AG_LOSS_LIMIT`` 이하 (부선조 자신의 미광 손실만큼)

왜 부선인가
----------
EVA 와 물의 비중차는 0.05 다. 설계 박편(등체적 약 21 µm)이 제 부력으로 뜨는 속도는
시간당 수 cm 라, 부선 급광 전량을 중력으로 가르려면 수면적이 백수십 m2 가 든다.
사이클론은 EVA 를 전량 월류로 보내지만 Si 미립도 함께 보낸다 — 가르는 것이 아니라
섞어서 옮길 뿐이다. 체는 떨어진 EVA 가 원 입자보다 작아 걸리지 않는다. 남는 것은
**표면 성질**로 가르는 부선이다. 0.8 mm 기포는 EVA 박편이 스스로 뜨는 속도의
수천 배로 올라간다.

설계 논리
--------
1. **설계 EVA 는 잔막 두께 하나로 정한다.** 셀 양면에 두께 t 의 EVA 잔막이 남았다고
   보면 함량은 양면 EVA 질량 / 웨이퍼를 포함한 급광 질량이고, 떨어진 박편은
   두께 t · 폭 w(원 입자의 면)다. 두께가 두꺼우면 EVA 는 많지만 박편도 커서 잘 뜬다
   — 두 효과가 서로 상쇄하는지를 두께 민감도로 본다.
2. **속도상수는 기포-입자 충돌로 구한다.** k = 1.5·Ea·Ec·Jg/db (Jameson 형,
   Yoon-Luttrell 충돌 효율 — ``hydrodynamics``). 부착 효율 Ea 는 같은 기포 조건의
   Ag 러퍼(FC-201)에서 역산한 값을 쓴다. 이 설비에서 실측과 맞춘 유일한 부착 효율이다.
3. **작은 EVA 가 전부를 정한다.** Ec 가 (dp/db)^2 에 비례하므로 10 µm 박편은 20 µm
   박편의 약 1/4 속도로 뜬다. 그래서 크기별 회수율 표를 설계 결과로 낸다.
4. **요구 제거율은 부선 급광 한도에서 역산한다.** 한도를 떨어진 EVA 양으로 나누면
   필요한 제거율이 나온다.
5. **판정은 회분 t90 으로 한다.** 시험 S-1(회분 부선, 기포제만)에서 얻은 자유 EVA 의
   t90 을 ES 가 감당하는 한계와 비교한다 — AS-1 의 E90 판정과 같은 구조다.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from .hydrodynamics import (
    WATER_DENSITY_KG_M3,
    WATER_VISCOSITY_PA_S,
    collection_rate_constant_1_min,
    collision_efficiency,
    terminal_velocity,
)

#: 기포 속 공기 밀도 (kg/m3) — 종말속도 계산용.
AIR_DENSITY_KG_M3 = 1.2


# --------------------------------------------------------------------------
# 설계 EVA
# --------------------------------------------------------------------------
def flake_equivalent_diameter_um(thickness_um: float, width_um: float) -> float:
    """두께 t · 폭 w 인 정사각 박편과 체적이 같은 구의 지름 (µm).

    충돌 효율은 입자가 유선을 가로지르는 크기로 정해지므로, 넓적한 박편을
    등체적 구로 보는 것은 **느리게 뜨는 쪽**으로 잡는 셈이다.
    """
    if thickness_um <= 0 or width_um <= 0:
        raise ValueError("박편 두께와 폭은 양수여야 함")
    return (6.0 / math.pi * width_um**2 * thickness_um) ** (1.0 / 3.0)


def eva_content_from_film(
    film_um: float,
    wafer_um: float,
    wafer_mass_fraction: float,
    eva_sg: float,
    wafer_sg: float,
) -> float:
    """셀 양면 잔막 두께에서 EVA 함량을 구한다 (광물 급광 1 t 당 EVA t).

    셀 면적당 웨이퍼 질량은 ``wafer_um · ρSi`` 이고 그것이 급광의
    ``wafer_mass_fraction`` 이므로, 면적당 급광 질량은 그 몫으로 나눈 값이다.
    EVA 는 양면에 ``2 · film_um · ρEVA`` 가 붙어 있다.
    """
    if film_um < 0:
        raise ValueError("잔막 두께는 0 이상")
    if wafer_um <= 0 or wafer_sg <= 0 or eva_sg <= 0:
        raise ValueError("웨이퍼 두께와 비중은 양수여야 함")
    if not 0.0 < wafer_mass_fraction <= 1.0:
        raise ValueError("wafer_mass_fraction 은 0 초과 1 이하")
    return 2.0 * film_um * eva_sg * wafer_mass_fraction / (wafer_um * wafer_sg)


@dataclass(frozen=True)
class EvaDesignParticle:
    """잔막 두께 하나로 정한 설계 EVA.

    Attributes:
        film_um: 셀 한 면의 EVA 잔막 두께.
        width_um: 떨어진 박편의 폭 — 원 입자의 면을 넘지 못한다.
        content: 광물 급광 1 t 당 EVA t.
    """

    film_um: float
    width_um: float
    wafer_um: float
    content: float

    @property
    def equivalent_diameter_um(self) -> float:
        return flake_equivalent_diameter_um(self.film_um, self.width_um)


def eva_design_particle(
    film_um: float,
    width_um: float,
    wafer_um: float,
    wafer_mass_fraction: float,
    eva_sg: float,
    wafer_sg: float,
) -> EvaDesignParticle:
    return EvaDesignParticle(
        film_um=film_um,
        width_um=width_um,
        wafer_um=wafer_um,
        content=eva_content_from_film(film_um, wafer_um, wafer_mass_fraction, eva_sg, wafer_sg),
    )


# --------------------------------------------------------------------------
# 방식 선정
# --------------------------------------------------------------------------
def rise_velocity_m_h(diameter_um: float, specific_gravity: float) -> float:
    """구가 물속에서 제 부력으로 뜨는 속도 (m/h, 가라앉으면 음수)."""
    if diameter_um <= 0:
        raise ValueError("지름은 양수여야 함")
    v = terminal_velocity(diameter_um / 1e6, specific_gravity * 1000.0)
    return v * 3600.0


def eva_rate_constant_1_min(
    diameter_um: float,
    jg_cm_s: float,
    attachment_efficiency: float,
    bubble_d32_mm: float,
) -> float:
    """EVA 박편의 포집 속도상수 (1/min) — k = 1.5·Ea·Ec·Jg/db.

    EVA 는 물과 비중이 거의 같아 유선을 그대로 따라가므로 충돌은 가로채기
    (interception) 뿐이다 — Yoon-Luttrell 식이 그 경우의 식이다.
    """
    if diameter_um <= 0 or jg_cm_s <= 0 or bubble_d32_mm <= 0:
        raise ValueError("지름·Jg·기포 지름은 양수여야 함")
    if not 0.0 < attachment_efficiency <= 1.0:
        raise ValueError("부착 효율은 0 초과 1 이하")
    db_m = bubble_d32_mm / 1000.0
    rise = terminal_velocity(db_m, AIR_DENSITY_KG_M3)
    reynolds = WATER_DENSITY_KG_M3 * rise * db_m / WATER_VISCOSITY_PA_S
    ec = collision_efficiency(diameter_um / 1e6, db_m, reynolds)
    return collection_rate_constant_1_min(attachment_efficiency, ec, jg_cm_s / 100.0, db_m)


@dataclass(frozen=True)
class EvaMethodScreen:
    """떨어진 EVA 를 무엇으로 가르는가 — 중력과 기포의 속도 비교.

    Attributes:
        flow_m3h: 가를 슬러리 유량 (부선 급광).
        eva_diameter_um: 설계 EVA 박편의 등체적 지름.
    """

    flow_m3h: float
    eva_diameter_um: float
    eva_sg: float
    bubble_d32_mm: float

    @property
    def eva_rise_m_h(self) -> float:
        return rise_velocity_m_h(self.eva_diameter_um, self.eva_sg)

    @property
    def skim_area_m2(self) -> float:
        """부선 급광 전량을 부력만으로 가를 때 필요한 수면적."""
        return self.flow_m3h / self.eva_rise_m_h

    @property
    def bubble_rise_m_s(self) -> float:
        return terminal_velocity(self.bubble_d32_mm / 1000.0, AIR_DENSITY_KG_M3)

    @property
    def bubble_to_eva_ratio(self) -> float:
        """기포가 EVA 박편을 얼마나 빨리 끌어올리는가."""
        return self.bubble_rise_m_s * 3600.0 / self.eva_rise_m_h


# --------------------------------------------------------------------------
# 요구 제거율 — 부선 급광 한도
# --------------------------------------------------------------------------
def grade_margin_tph(concentrate_tph: float, grade: float, guarantee: float) -> float:
    """정광 품위를 보증값까지 떨어뜨리는 EVA 양 (t/h) — 품위 여유의 질량 환산."""
    if concentrate_tph <= 0 or not 0.0 < guarantee <= grade:
        raise ValueError("정광 유량은 양수, 보증 품위는 설계 품위 이하여야 함")
    return concentrate_tph * (grade / guarantee - 1.0)


def concentrate_grade_with_eva(concentrate_tph: float, grade: float, eva_tph: float) -> float:
    """부선 급광의 자유 EVA 가 전부 정광으로 갈 때의 정광 품위."""
    if concentrate_tph <= 0 or eva_tph < 0:
        raise ValueError("정광 유량은 양수, EVA 는 0 이상")
    return grade * concentrate_tph / (concentrate_tph + eva_tph)


@dataclass(frozen=True)
class EvaRequirement:
    """ES 가 걷어내야 하는 몫.

    Attributes:
        dry_tph: 광물 급광 (건조).
        feed_limit: 부선 급광으로 넘어가도 되는 자유 EVA (고체 질량분율).
        freed_eva_tph: ES 로 들어오는 자유 EVA.
    """

    dry_tph: float
    feed_limit: float
    freed_eva_tph: float

    @property
    def allowance_tph(self) -> float:
        return self.feed_limit * self.dry_tph

    @property
    def required_recovery(self) -> float:
        if self.freed_eva_tph <= self.allowance_tph:
            return 0.0
        return 1.0 - self.allowance_tph / self.freed_eva_tph


@dataclass(frozen=True)
class EvaFilmCase:
    """잔막 두께 하나에 대한 요구와 성능 — 두께 민감도 표의 한 줄.

    두께가 두꺼우면 EVA 는 많아 요구 제거율이 오르지만, 박편도 커져 잘 뜬다.
    """

    film_um: float
    content: float
    diameter_um: float
    freed_eva_tph: float
    required_recovery: float
    recovery: float

    @property
    def residual_tph(self) -> float:
        return self.freed_eva_tph * (1.0 - self.recovery)

    @property
    def ok(self) -> bool:
        return self.recovery >= self.required_recovery


# --------------------------------------------------------------------------
# 판정 — 회분 t90
# --------------------------------------------------------------------------
def batch_t90_limit(
    recovery_at_batch_k: Callable[[float], float],
    required_recovery: float,
    k_min: float = 1.0e-3,
    k_max: float = 100.0,
    iterations: int = 50,
) -> float:
    """회로 회수율이 요구치에 닿는 회분 속도상수를 찾아 t90 (min) 으로 돌려준다.

    회수율은 속도상수에 대해 단조 증가하므로 로그 구간 이분법으로 푼다.
    t90 은 회분 1차 거동에서 90 % 에 이르는 시간 ``ln 10 / k`` 이다 — S-1 에서
    원점을 지나는 최소제곱으로 k 를 구하는 것과 같은 정의다.

    Raises:
        ValueError: 탐색 구간 끝에서도 요구치에 닿지 않을 때.
    """
    if not 0.0 < required_recovery < 1.0:
        raise ValueError("요구 회수율은 0~1 사이여야 함")
    if recovery_at_batch_k(k_max) < required_recovery:
        raise ValueError("탐색 상한 속도상수로도 요구 회수율에 닿지 않음")
    lo, hi = k_min, k_max
    for _ in range(iterations):
        mid = math.sqrt(lo * hi)
        if recovery_at_batch_k(mid) >= required_recovery:
            hi = mid
        else:
            lo = mid
    return math.log(10.0) / hi


@dataclass(frozen=True)
class EvaBatchLimits:
    """S-1 의 회분 t90 과 비교할 한계 (min). 짧을수록 빨리 뜬다.

    Attributes:
        peak_min: 이 이하면 ES 그대로, 최대 처리량에서도 요구 제거율.
        average_min: 이 이하면 평균 처리량까지는 그대로.
        extra_cell_min: 이 이하면 같은 동체 셀 1기를 더해 최대 처리량을 받는다.
    """

    required_recovery: float
    peak_min: float
    average_min: float
    extra_cell_min: float


# --------------------------------------------------------------------------
# EVA 산물 탈수
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DewateringBag:
    """EVA 산물 탈수 백 — 중력 배수, 2기 교대.

    Attributes:
        cake_solids_volume_fraction: 케이크 안 EVA 의 체적분율. 납작하고 무른
            박편이 느슨하게 쌓여 낮다.
        eva_tph: 백으로 오는 EVA — 떨어진 EVA 가 전부일 때의 상한으로 잡는다.
        minerals_tph: 함께 오는 광물 (동반 혼입).
    """

    tag: str
    volume_m3: float
    fill: float
    units: int
    cake_solids_volume_fraction: float
    eva_sg: float
    eva_tph: float
    minerals_tph: float

    def __post_init__(self) -> None:
        if self.volume_m3 <= 0 or not 0.0 < self.fill <= 1.0 or self.units < 1:
            raise ValueError("백 체적·충전율·대수가 범위를 벗어남")
        if not 0.0 < self.cake_solids_volume_fraction < 1.0:
            raise ValueError("케이크 고체 체적분율은 0~1 사이")

    @property
    def dry_capacity_kg(self) -> float:
        """백 1개가 담는 건조 EVA."""
        return (
            self.volume_m3 * self.fill * self.cake_solids_volume_fraction
            * self.eva_sg * 1000.0
        )

    @property
    def change_interval_h(self) -> float:
        solids_kg_h = (self.eva_tph + self.minerals_tph) * 1000.0
        return self.dry_capacity_kg / solids_kg_h if solids_kg_h > 0 else math.inf

    @property
    def cake_water_tph(self) -> float:
        """케이크에 남아 계 밖으로 나가는 물 — 신수 보충에 더해진다."""
        phi = self.cake_solids_volume_fraction
        return self.eva_tph * (1.0 - phi) / (phi * self.eva_sg)

    @property
    def cake_moisture(self) -> float:
        """습량 기준 함수율."""
        water = self.cake_water_tph
        return water / (water + self.eva_tph) if self.eva_tph > 0 else 0.0
