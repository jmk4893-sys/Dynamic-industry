"""어트리션 스크러버 (attrition scrubber) — 부선 전 표면 정정(scrubbing) 설비.

로드밀 배출 슬러리를 **고농도 그대로** 받아 입자끼리 문질러 표면을 벗긴 뒤,
희석박스에서 부선 농도로 묽혀 조건조로 보낸다. 분쇄기가 아니다 — 목표는
입자를 깨는 것이 아니라 **표면에 붙은 것을 떼는 것**이다.

무엇을 떼려는가
---------------
1. **박리 잔막.** 셀 분획은 EVA 봉지재·접착층을 벗겨낸 것이라 표면에 유기
   잔막이 남는다. 잔막은 (a) 포수제가 Ag 전극에 닿는 것을 막고,
   (b) 그 자체가 소수성이라 무차별 부상해 정광을 희석한다.
2. **슬라임 코팅.** 습식 분쇄면에 붙은 미립 Si 가 Ag 표면을 덮는다.
   [2] 가 관측한 "습식 분쇄물은 건조 원료의 2배(300 g/t)를 써야 거품이
   선다"(``references.WET_FEED_REAGENT_FACTOR``)의 유력한 원인 후보다.
3. **Ag 전극 박편.** Ag 는 Si 표면에 소결된 층이라 벌크 Si 보다 약하다.
   표면 마모로 일부가 떨어져 나오면 복합입자 동반비 r 이 내려가고,
   그만큼 **정광 품위 상한 1/(1+r) 이 올라간다**.

무엇을 약속하지 않는가
--------------------
**[1][2] 어디에도 어트리션 시험은 없다.** 위 셋은 전부 가설이므로 이 설비는
기본설계 성능에 **크레딧을 전혀 받지 않는다** (``ATTRITION_PERFORMANCE_CREDIT
= 1.0``). 회수율·품위·약제 투입량은 어트리션이 없는 것과 같은 값으로 계산한다.
대신 (a) 전량 바이패스 배관을 두어 없는 것처럼 운전할 수 있게 하고,
(b) 이득을 정량화할 시험 절차와 합격 기준을 설계에 포함한다. 시험에서 이득이
확인되지 않으면 바이패스로 두거나 철거하는 편이 낫다 — 이 설비는 공짜가 아니다.

설계 논리
--------
1. 스크러빙 농도(70 wt%)에서 슬러리 체적유량을 구한다. 고체 체적분율이
   **50 vol% 부근**이어야 입자끼리 닿아 마찰이 생긴다. 묽으면 그냥 교반조다.
2. 체류시간으로 소요 체적을 구하고 상용 규격 계열에서 셀을 고른다. 소규모에서는
   보통 **상용 최소 기종**이 지배한다 (필터프레스와 같은 상황).
3. 팔각조 — 배플 없이 vortex 를 깨는 표준 형상.
4. 대향 피치 축류 임펠러 2단/축. 위는 아래로, 아래는 위로 밀어 **중간
   높이에 전단면**을 만든다. 여기서 입자끼리 갈린다.
5. 회전수는 **설계 주속**에서 정하고, 그 결과 나오는 흡수동력에서 비에너지
   (kWh/t)를 역산해 목표 범위에 드는지 확인한다. 실기 제어변수는 체류시간이
   아니라 **비에너지**이므로, VFD 로 주속을 조정해 처리량 변동을 흡수한다.
6. 축은 비틀림과 예비 로터동역학 중 큰 쪽으로 정한다. 짧고 굵어 보여도
   고농도 슬러리의 정지 토크와 외팔보 길이 때문에 대개 **로터동역학이 지배**한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .feed import PulpProperties
from .sizing import (
    SHAFT_OD_SERIES_MM,
    cantilever_rotor_dynamics,
    select_motor_kw,
    torsional_section_modulus_m3,
)

#: 상용 어트리션 셀 유효체적 계열 (m3). 2/4/10/20/40/60/100/150/200 ft3.
STANDARD_CELL_M3 = (0.057, 0.113, 0.283, 0.566, 1.133, 1.699, 2.832, 4.248, 5.663)

#: 정팔각형 면적 계수 — 마주보는 변 사이 거리(across flats) W 에 대해 A = k*W^2.
OCTAGON_AREA_COEFF = 8.0 * math.tan(math.pi / 8.0) / 4.0


def octagon_area_m2(across_flats_m: float) -> float:
    """마주보는 변 사이 거리로 정팔각형 단면적을 구한다."""
    if across_flats_m <= 0:
        raise ValueError("across_flats_m 은 양수여야 함")
    return OCTAGON_AREA_COEFF * across_flats_m**2


def solids_mass_fraction_for_volume_fraction(
    volume_fraction: float, solids_sg: float
) -> float:
    """주어진 고체 체적분율에 해당하는 질량분율.

    어트리션이 성립하는지는 체적분율(입자끼리 닿는가)로 결정되지만, 현장에서
    재는 것은 질량분율이다. 둘을 잇는 변환으로 **스크러빙 농도의 절대 하한**을
    비중에서 직접 뽑는다.
    """
    if not 0.0 < volume_fraction < 1.0:
        raise ValueError("volume_fraction 은 0~1 사이여야 함")
    if solids_sg <= 0.0:
        raise ValueError("solids_sg 는 양수여야 함")
    return volume_fraction / (volume_fraction + (1.0 - volume_fraction) / solids_sg)


def concentrate_grade_ceiling(carry_ratio: float) -> float:
    """복합입자 동반비 r 에서 정광 품위의 물리적 상한 (질량분율).

    부상 Ag 1 kg 이 같은 입자의 일부로 맥석 r kg 을 달고 오면 품위는
    1/(1+r) 을 넘을 수 없다. 어트리션이 Ag 박편을 떼어내 r 을 낮추면
    이 상한이 올라간다 — 이 설비의 가장 값나가는 상방 시나리오다.
    """
    if carry_ratio < 0:
        raise ValueError("carry_ratio 는 0 이상")
    return 1.0 / (1.0 + carry_ratio)


def short_circuit_fraction(cells: int, theta: float = 0.5) -> float:
    """완전혼합조 n 기 직렬에서 평균 체류시간의 theta 배 미만으로 빠져나가는 질량분율.

    단조 F(theta) = 1 - exp(-n*theta) * sum_{k<n} (n*theta)^k / k!.
    한 조로 다 채우면 급광의 상당 부분이 거의 문질러지지 않고 통과한다.
    어트리션 셀을 **최소 2단 직렬**로 두는 이유가 이것이다.
    """
    if cells < 1:
        raise ValueError("cells 는 1 이상이어야 함")
    if theta < 0:
        raise ValueError("theta 는 0 이상이어야 함")
    x = cells * theta
    series = sum(x**k / math.factorial(k) for k in range(cells))
    return 1.0 - math.exp(-x) * series


# --------------------------------------------------------------------------
# 형상
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AttritionCellGeometry:
    """팔각 어트리션 셀 1기의 형상.

    Attributes:
        across_flats_m: 마주보는 변 사이 거리 (조 내부).
        depth_m: 운전 액면까지의 깊이 = 유효 체적 기준.
        freeboard_m: 액면 위 여유고. 고농도 슬러리는 튀므로 넉넉히 둔다.
    """

    across_flats_m: float
    depth_m: float
    freeboard_m: float

    def __post_init__(self) -> None:
        if self.across_flats_m <= 0 or self.depth_m <= 0:
            raise ValueError("셀 치수는 양수여야 함")
        if self.freeboard_m < 0:
            raise ValueError("freeboard_m 은 0 이상")

    @property
    def plan_area_m2(self) -> float:
        return octagon_area_m2(self.across_flats_m)

    @property
    def working_volume_m3(self) -> float:
        return self.plan_area_m2 * self.depth_m

    @property
    def shell_height_m(self) -> float:
        return self.depth_m + self.freeboard_m

    @property
    def shell_volume_m3(self) -> float:
        return self.plan_area_m2 * self.shell_height_m

    @property
    def circumscribed_diameter_m(self) -> float:
        """꼭짓점 사이 거리 — 설치 공간 산정용."""
        return self.across_flats_m / math.cos(math.pi / 8.0)


# --------------------------------------------------------------------------
# 구동부
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AttritionDrive:
    """축 1개의 임펠러·모터 사양.

    Attributes:
        impellers_per_shaft: 축당 임펠러 수 (대향 피치 2단이 표준).
        design_tip_speed_m_s: 설계 주속.
        absorbed_power_w: 설계 주속에서의 흡수동력 (축 1개).
        motor_rating_kw: 표준 모터 용량.
        tip_speed_min_m_s: VFD 하한 — 고농도 층을 움직이는 데 필요한 최소 주속.
        tip_speed_max_m_s: 실무 상한 — 이 위는 마모가 아니라 분쇄가 된다.
    """

    diameter_m: float
    speed_rpm: float
    tip_speed_m_s: float
    impellers_per_shaft: int
    power_number: float
    pulp_density_kg_m3: float
    absorbed_power_w: float
    motor_rating_kw: float
    service_factor: float
    tip_speed_min_m_s: float
    tip_speed_max_m_s: float
    assembly_mass_kg: float

    @property
    def spacing_m(self) -> float:
        """대향 임펠러 사이 간격 — 전단면이 서는 거리. 통상 1 D."""
        return self.diameter_m

    def power_w_at_tip_speed(self, tip_speed_m_s: float) -> float:
        """다른 주속에서의 흡수동력. P ∝ N^3 이므로 주속의 세제곱."""
        if tip_speed_m_s < 0:
            raise ValueError("주속은 0 이상")
        return self.absorbed_power_w * (tip_speed_m_s / self.tip_speed_m_s) ** 3

    def speed_rpm_at_tip_speed(self, tip_speed_m_s: float) -> float:
        return tip_speed_m_s / (math.pi * self.diameter_m) * 60.0

    @property
    def tip_speed_ceiling_m_s(self) -> float:
        """모터 정격이 허용하는 최대 주속.

        흡수동력이 ``정격 / 서비스계수`` 를 넘으면 안 되므로, 실무 상한과
        모터가 허용하는 상한 중 **작은 쪽**이 VFD 상한이 된다.
        """
        allowed_w = self.motor_rating_kw * 1000.0 / self.service_factor
        by_motor = self.tip_speed_m_s * (allowed_w / self.absorbed_power_w) ** (1.0 / 3.0)
        return min(self.tip_speed_max_m_s, by_motor)

    @property
    def tip_speed_ok(self) -> bool:
        return self.tip_speed_min_m_s <= self.tip_speed_m_s <= self.tip_speed_max_m_s


# --------------------------------------------------------------------------
# 축
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AttritionShaft:
    """어트리션 셀의 중실 교반축 (상부 베어링 외팔보)."""

    outer_diameter_mm: float
    length_m: float
    torque_nm: float
    service_factor: float
    shear_stress_mpa: float
    allowable_shear_mpa: float
    governed_by: str
    critical_speed_rpm: float
    critical_speed_ratio: float
    minimum_critical_speed_ratio: float
    static_deflection_mm: float
    allowable_deflection_mm: float
    overhung_mass_kg: float

    @property
    def is_safe(self) -> bool:
        return (
            self.shear_stress_mpa <= self.allowable_shear_mpa
            and self.critical_speed_ratio >= self.minimum_critical_speed_ratio
            and self.static_deflection_mm <= self.allowable_deflection_mm
        )


def _size_shaft(
    absorbed_power_w: float,
    speed_rpm: float,
    length_m: float,
    overhung_mass_kg: float,
    allowable_shear_mpa: float,
    torque_service_factor: float,
    critical_speed_ratio_min: float,
    allowable_deflection_mm: float,
) -> AttritionShaft:
    """비틀림과 예비 로터동역학 중 큰 쪽으로 중실축 외경을 정한다.

    비틀림 서비스계수 2.0 은 고농도 슬러리가 굳은 상태에서 기동할 때의
    정지 토크를 감안한 값이다. 로터동역학은 임펠러 조립체 전체를 자유단
    집중질량으로 놓은 보수적 외팔보 모델이다 (실제로는 위쪽 임펠러가
    중간 높이에 있어 이보다 유리하다).
    """
    torque = absorbed_power_w / (2.0 * math.pi * speed_rpm / 60.0) * torque_service_factor

    torsion_od = next(
        (
            od
            for od in SHAFT_OD_SERIES_MM
            if torque / torsional_section_modulus_m3(od) / 1e6 <= allowable_shear_mpa
        ),
        None,
    )
    if torsion_od is None:
        raise ValueError("표준 외경 계열로 어트리션 축 토크를 감당할 수 없음")

    dynamic_od = None
    for od in SHAFT_OD_SERIES_MM:
        rd = cantilever_rotor_dynamics(od, 0.0, length_m, speed_rpm, overhung_mass_kg)
        if (
            rd.critical_speed_ratio >= critical_speed_ratio_min
            and rd.static_deflection_mm <= allowable_deflection_mm
        ):
            dynamic_od = od
            break
    if dynamic_od is None:
        raise ValueError("표준 외경 계열로 어트리션 축 임계회전수·처짐 기준 불만족")

    outer_mm = max(torsion_od, dynamic_od)
    dynamics = cantilever_rotor_dynamics(
        outer_mm, 0.0, length_m, speed_rpm, overhung_mass_kg
    )
    return AttritionShaft(
        outer_diameter_mm=outer_mm,
        length_m=length_m,
        torque_nm=torque,
        service_factor=torque_service_factor,
        shear_stress_mpa=torque / torsional_section_modulus_m3(outer_mm) / 1e6,
        allowable_shear_mpa=allowable_shear_mpa,
        governed_by="비틀림" if torsion_od >= dynamic_od else "로터동역학",
        critical_speed_rpm=dynamics.critical_speed_rpm,
        critical_speed_ratio=dynamics.critical_speed_ratio,
        minimum_critical_speed_ratio=critical_speed_ratio_min,
        static_deflection_mm=dynamics.static_deflection_mm,
        allowable_deflection_mm=allowable_deflection_mm,
        overhung_mass_kg=overhung_mass_kg,
    )


# --------------------------------------------------------------------------
# 설비
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AttritionScrubber:
    """어트리션 스크러버 1대 (셀 직렬 n 기).

    Attributes:
        cells: 직렬 셀 수. 단락류(short-circuit) 때문에 최소 2.
        design_residence_min: 설계 총 체류시간 (최대 처리량 기준).
        nominal_cell_m3: 상용 계열에서 고른 셀 유효체적.
        governed_by: 규격을 결정한 기준 — "체류시간" 또는 "상용 최소 기종".
        specific_energy_range_kwh_t: 시험으로 확정할 비에너지 목표 범위.
        feed_pump_kw: 급광 펌프 (중력 급광이면 0).
    """

    tag: str
    duty: str
    design_dry_tph: float
    solids_sg: float
    solids_mass_fraction: float
    cells: int
    geometry: AttritionCellGeometry
    drive: AttritionDrive
    shaft: AttritionShaft
    design_residence_min: float
    nominal_cell_m3: float
    governed_by: str
    specific_energy_range_kwh_t: tuple[float, float]
    specific_power_range_kw_m3: tuple[float, float]
    minimum_solids_volume_fraction: float
    liner: str
    feed_pump_kw: float

    # -- 급광 상태 --------------------------------------------------------
    def pulp_at(self, dry_tph: float) -> PulpProperties:
        """스크러빙 농도에서의 슬러리 물성."""
        return PulpProperties(
            dry_tph=dry_tph,
            solids_sg=self.solids_sg,
            solids_mass_fraction=self.solids_mass_fraction,
        )

    @property
    def pulp(self) -> PulpProperties:
        return self.pulp_at(self.design_dry_tph)

    @property
    def solids_volume_fraction(self) -> float:
        """고체 체적분율 — 어트리션의 성패를 가르는 단 하나의 변수."""
        return self.pulp.solids_volume_fraction

    @property
    def solids_volume_fraction_ok(self) -> bool:
        return self.solids_volume_fraction >= self.minimum_solids_volume_fraction

    @property
    def minimum_solids_mass_fraction(self) -> float:
        """스크러빙이 성립하는 고체 농도의 절대 하한 (질량분율).

        상류 로드밀 배출이 이보다 묽으면 어트리션이 아니라 교반이 된다.
        """
        return solids_mass_fraction_for_volume_fraction(
            self.minimum_solids_volume_fraction, self.solids_sg
        )

    # -- 체적·체류시간 ----------------------------------------------------
    @property
    def total_working_volume_m3(self) -> float:
        return self.geometry.working_volume_m3 * self.cells

    def residence_min(self, dry_tph: float) -> float:
        return self.total_working_volume_m3 / (self.pulp_at(dry_tph).volumetric_flow_m3h / 60.0)

    @property
    def short_circuit_fraction(self) -> float:
        """평균 체류시간의 절반도 못 채우고 나가는 질량분율."""
        return short_circuit_fraction(self.cells, 0.5)

    # -- 동력 -------------------------------------------------------------
    @property
    def absorbed_kw(self) -> float:
        """설계 주속에서 전 셀이 슬러리에 넣는 동력."""
        return self.drive.absorbed_power_w * self.cells / 1000.0

    @property
    def installed_kw(self) -> float:
        return self.drive.motor_rating_kw * self.cells + self.feed_pump_kw

    @property
    def specific_power_kw_m3(self) -> float:
        return self.absorbed_kw / self.total_working_volume_m3

    @property
    def specific_power_ok(self) -> bool:
        low, high = self.specific_power_range_kw_m3
        return low <= self.specific_power_kw_m3 <= high

    def specific_energy_kwh_t(self, dry_tph: float, tip_speed_m_s: float | None = None) -> float:
        """처리량 t 당 투입 에너지 — 어트리션의 실제 제어변수."""
        if dry_tph <= 0:
            raise ValueError("처리량은 양수여야 함")
        power_w = (
            self.drive.absorbed_power_w
            if tip_speed_m_s is None
            else self.drive.power_w_at_tip_speed(tip_speed_m_s)
        )
        return power_w * self.cells / 1000.0 / dry_tph

    def recommended_tip_speed_m_s(self, dry_tph: float) -> float:
        """목표 비에너지 상한을 넘지 않으면서 층을 움직이는 주속.

        처리량이 줄면 같은 주속에서 t 당 에너지가 커지므로 속도를 낮춘다.
        단, 고농도 층을 움직이는 최소 주속 아래로는 내릴 수 없다.
        """
        _, energy_max = self.specific_energy_range_kwh_t
        allowed_w = energy_max * dry_tph * 1000.0 / self.cells
        ratio = min(1.0, (allowed_w / self.drive.absorbed_power_w) ** (1.0 / 3.0))
        target = self.drive.tip_speed_m_s * ratio
        return max(self.drive.tip_speed_min_m_s, min(target, self.drive.tip_speed_ceiling_m_s))

    @property
    def minimum_dry_tph(self) -> float:
        """이보다 적게 넣으면 최저 주속에서도 과다 스크러빙이 되는 처리량.

        주속에는 하한이 있으므로 동력도 더 내려가지 않는다. 처리량만 줄면
        t 당 에너지가 목표 상한을 넘는다. 이 경우 캠페인 운전하거나
        바이패스한다.
        """
        _, energy_max = self.specific_energy_range_kwh_t
        floor_w = self.drive.power_w_at_tip_speed(self.drive.tip_speed_min_m_s)
        return floor_w * self.cells / 1000.0 / energy_max

    @property
    def is_adequate(self) -> bool:
        return (
            self.solids_volume_fraction_ok
            and self.specific_power_ok
            and self.drive.tip_speed_ok
            and self.shaft.is_safe
            and self.residence_min(self.design_dry_tph) >= self.design_residence_min
        )


def size_attrition(
    tag: str,
    duty: str,
    dry_tph: float,
    solids_sg: float,
    solids_mass_fraction: float = 0.70,
    cells: int = 2,
    residence_min: float = 10.0,
    depth_to_width: float = 1.2,
    freeboard_m: float = 0.10,
    impeller_ratio: float = 0.50,
    impellers_per_shaft: int = 2,
    power_number: float = 0.80,
    design_tip_speed_m_s: float = 7.0,
    tip_speed_range_m_s: tuple[float, float] = (6.0, 9.0),
    specific_energy_range_kwh_t: tuple[float, float] = (1.0, 6.0),
    specific_power_range_kw_m3: tuple[float, float] = (8.0, 25.0),
    minimum_solids_volume_fraction: float = 0.40,
    impeller_mass_coeff_kg_m3: float = 500.0,
    shaft_length_margin_m: float = 0.50,
    motor_service_factor: float = 1.4,
    torque_service_factor: float = 2.0,
    allowable_shear_mpa: float = 40.0,
    critical_speed_ratio_min: float = 1.5,
    allowable_deflection_mm: float = 5.0,
    round_to_m: float = 0.005,
    speed_round_to_rpm: float = 10.0,
    liner: str = "천연고무 12 mm",
    feed_pump_kw: float = 0.0,
) -> AttritionScrubber:
    """처리량과 스크러빙 농도로부터 어트리션 스크러버 1대를 산정한다.

    Args:
        dry_tph: 설계(최대) 건조 고체 처리량.
        solids_mass_fraction: 스크러빙 고체 농도. 70~75 wt% 가 표준이며,
            체적분율로 50 vol% 부근이 되어야 입자끼리 닿는다.
        cells: 직렬 셀 수 (최소 2 — 단락류 때문).
        residence_min: 설계 총 체류시간. 실제 체류시간은 상용 규격 때문에
            보통 이보다 길어진다.
        design_tip_speed_m_s: 설계 주속. 회전수와 흡수동력이 여기서 나온다.
        impeller_mass_coeff_kg_m3: 임펠러 1개 질량을 ``coeff * D^3`` 으로 잡는
            예비 계수. 제작도 확정 후 실측 질량으로 재검증해야 한다.
        feed_pump_kw: 중력 급광이면 0. 50 vol% 슬러리는 원심펌프로 보낼 수
            없으므로 펌프를 쓴다면 일축 편심(PC) 펌프다.

    Raises:
        ValueError: 입력이 물리적으로 성립하지 않을 때.
    """
    if dry_tph <= 0:
        raise ValueError("처리량은 양수여야 함")
    if cells < 2:
        raise ValueError("어트리션 셀은 단락류 때문에 최소 2단 직렬이어야 함")
    if not 0.0 < solids_mass_fraction < 1.0:
        raise ValueError("solids_mass_fraction 은 0~1 사이여야 함")
    if residence_min <= 0:
        raise ValueError("체류시간은 양수여야 함")
    tip_min, tip_max = tip_speed_range_m_s
    if not tip_min <= design_tip_speed_m_s <= tip_max:
        raise ValueError("설계 주속이 허용 범위를 벗어남")

    pulp = PulpProperties(
        dry_tph=dry_tph,
        solids_sg=solids_sg,
        solids_mass_fraction=solids_mass_fraction,
    )
    flow_m3h = pulp.volumetric_flow_m3h

    # 1. 셀 규격 — 체류시간 소요량과 상용 최소 기종 중 큰 쪽
    required_per_cell = flow_m3h * residence_min / 60.0 / cells
    nominal = next((v for v in STANDARD_CELL_M3 if v >= required_per_cell), None)
    if nominal is None:
        raise ValueError("상용 어트리션 셀 계열을 초과 — 복수 대수 검토 필요")
    governed_by = (
        "상용 최소 기종"
        if nominal == STANDARD_CELL_M3[0] and required_per_cell < nominal
        else "체류시간"
    )

    # 2. 팔각조 형상 — A*W^2 * (r*W) = V 에서 W 를 풀고 제작 치수로 올림
    width = (nominal / (OCTAGON_AREA_COEFF * depth_to_width)) ** (1.0 / 3.0)
    width = math.ceil(width / round_to_m) * round_to_m
    depth = math.ceil(depth_to_width * width / round_to_m) * round_to_m
    geometry = AttritionCellGeometry(
        across_flats_m=width, depth_m=depth, freeboard_m=freeboard_m
    )

    # 3. 임펠러 — 지름은 조 폭 비율, 회전수는 설계 주속에서
    diameter = round(width * impeller_ratio, 2)
    rev_s = design_tip_speed_m_s / (math.pi * diameter)
    rpm = round(rev_s * 60.0 / speed_round_to_rpm) * speed_round_to_rpm
    rev_s = rpm / 60.0
    tip_speed = math.pi * diameter * rev_s
    absorbed_w = (
        impellers_per_shaft
        * power_number
        * pulp.pulp_density_kg_m3
        * rev_s**3
        * diameter**5
    )
    assembly_mass = impeller_mass_coeff_kg_m3 * impellers_per_shaft * diameter**3
    drive = AttritionDrive(
        diameter_m=diameter,
        speed_rpm=rpm,
        tip_speed_m_s=tip_speed,
        impellers_per_shaft=impellers_per_shaft,
        power_number=power_number,
        pulp_density_kg_m3=pulp.pulp_density_kg_m3,
        absorbed_power_w=absorbed_w,
        motor_rating_kw=select_motor_kw(absorbed_w, motor_service_factor),
        service_factor=motor_service_factor,
        tip_speed_min_m_s=tip_min,
        tip_speed_max_m_s=tip_max,
        assembly_mass_kg=assembly_mass,
    )

    # 4. 축 — 액면 위 구동 데크까지 올라가는 외팔보
    shaft = _size_shaft(
        absorbed_power_w=absorbed_w,
        speed_rpm=rpm,
        length_m=geometry.shell_height_m + shaft_length_margin_m,
        overhung_mass_kg=assembly_mass,
        allowable_shear_mpa=allowable_shear_mpa,
        torque_service_factor=torque_service_factor,
        critical_speed_ratio_min=critical_speed_ratio_min,
        allowable_deflection_mm=allowable_deflection_mm,
    )

    return AttritionScrubber(
        tag=tag,
        duty=duty,
        design_dry_tph=dry_tph,
        solids_sg=solids_sg,
        solids_mass_fraction=solids_mass_fraction,
        cells=cells,
        geometry=geometry,
        drive=drive,
        shaft=shaft,
        design_residence_min=residence_min,
        nominal_cell_m3=nominal,
        governed_by=governed_by,
        specific_energy_range_kwh_t=specific_energy_range_kwh_t,
        specific_power_range_kw_m3=specific_power_range_kw_m3,
        minimum_solids_volume_fraction=minimum_solids_volume_fraction,
        liner=liner,
        feed_pump_kw=feed_pump_kw,
    )


# --------------------------------------------------------------------------
# 희석박스
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DilutionBox:
    """스크러빙 농도 → 부선 농도 희석박스.

    어트리션 배출은 70 wt% 짜리 반죽이라 조건조에 그대로 넣으면 풀어지지
    않는다. 희석박스는 (a) 반죽을 풀고, (b) 어트리션 바이패스 배관의 합류점이
    되며, (c) 밀도계로 희석수를 조절해 조건조 급광 농도를 **7 wt% 로 고정**한다.

    Attributes:
        dilution_water_m3h: 추가로 넣는 물. 부선 농도를 맞추기 위해 어차피
            들어가던 물이므로 **설비 전체 물수지는 달라지지 않는다** —
            투입 지점만 정해질 뿐이다.
    """

    tag: str
    duty: str
    dry_tph: float
    solids_sg: float
    inlet_solids_wt: float
    outlet_solids_wt: float
    residence_min: float
    working_volume_m3: float
    box_volume_m3: float
    agitator_kw: float

    @property
    def inlet_water_tph(self) -> float:
        return self.dry_tph * (1.0 - self.inlet_solids_wt) / self.inlet_solids_wt

    @property
    def outlet_water_tph(self) -> float:
        return self.dry_tph * (1.0 - self.outlet_solids_wt) / self.outlet_solids_wt

    @property
    def dilution_water_m3h(self) -> float:
        return self.outlet_water_tph - self.inlet_water_tph

    @property
    def inlet_m3h(self) -> float:
        return self.dry_tph / self.solids_sg + self.inlet_water_tph

    @property
    def outlet_m3h(self) -> float:
        return self.dry_tph / self.solids_sg + self.outlet_water_tph


def dilution_box(
    tag: str,
    duty: str,
    dry_tph: float,
    solids_sg: float,
    inlet_solids_wt: float,
    outlet_solids_wt: float,
    residence_min: float = 2.0,
    freeboard_ratio: float = 0.15,
    mixing_intensity_kw_m3: float = 1.0,
    round_to_m3: float = 0.05,
) -> DilutionBox:
    """희석박스를 산정한다.

    P80 66 µm Si 입자의 Stokes 침강속도가 mm/s 급이라 2 분이면 수십 cm 를
    가라앉는다. 조건조가 바로 뒤에 있더라도 이 박스는 **교반해야 한다**.

    Raises:
        ValueError: 희석이 아니라 농축이 되는 조건일 때.
    """
    if dry_tph <= 0:
        raise ValueError("처리량은 양수여야 함")
    if not 0.0 < outlet_solids_wt < inlet_solids_wt < 1.0:
        raise ValueError("출구 농도는 입구 농도보다 낮아야 함 (희석)")
    outlet_water = dry_tph * (1.0 - outlet_solids_wt) / outlet_solids_wt
    outlet_flow = dry_tph / solids_sg + outlet_water
    working = outlet_flow * residence_min / 60.0
    total = math.ceil(working * (1.0 + freeboard_ratio) / round_to_m3) * round_to_m3
    return DilutionBox(
        tag=tag,
        duty=duty,
        dry_tph=dry_tph,
        solids_sg=solids_sg,
        inlet_solids_wt=inlet_solids_wt,
        outlet_solids_wt=outlet_solids_wt,
        residence_min=residence_min,
        working_volume_m3=working,
        box_volume_m3=total,
        agitator_kw=select_motor_kw(working * mixing_intensity_kw_m3 * 1000.0, 1.25),
    )
