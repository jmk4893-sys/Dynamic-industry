"""부선셀 사이징: 체적, 형상, 임펠러, 급기, 정광 배출(froth) 부하."""

from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.80665  # m/s2


# --------------------------------------------------------------------------
# 셀 체적
# --------------------------------------------------------------------------
def required_slurry_volume(
    volumetric_flow_m3h: float,
    residence_min: float,
    scale_up_factor: float = 1.0,
) -> float:
    """목표 체류시간을 만족하는 '기포를 포함하지 않은' 슬러리 체적 (m3).

    Args:
        volumetric_flow_m3h: 급광 슬러리 체적유량.
        residence_min: 목표 유효 체류시간 (분).
        scale_up_factor: 실험실 배치시험 → 실기 스케일업 계수 (통상 1.6~2.5).
            배치 부선시간을 그대로 쓸 때 적용하고, 이미 연속식 기준
            체류시간을 넣었다면 1.0 으로 둔다.
    """
    if volumetric_flow_m3h <= 0 or residence_min <= 0:
        raise ValueError("유량과 체류시간은 양수여야 함")
    return volumetric_flow_m3h * residence_min / 60.0 * scale_up_factor


@dataclass(frozen=True)
class CellGeometry:
    """정사각 단면 기계식 부선셀의 형상.

    Attributes:
        width_m: 내부 한 변 길이 (정사각 단면).
        shell_height_m: 셀 동체 전체 높이.
        lip_height_m: 정광 월류 립(lip) 높이 = 운전 액면.
        froth_depth_m: 거품층 두께.
        gas_holdup: 펄프존 기공률(air hold-up), 체적분율.
    """

    width_m: float
    shell_height_m: float
    lip_height_m: float
    froth_depth_m: float
    gas_holdup: float

    @property
    def cross_section_m2(self) -> float:
        return self.width_m**2

    @property
    def shell_volume_m3(self) -> float:
        return self.cross_section_m2 * self.shell_height_m

    @property
    def volume_to_lip_m3(self) -> float:
        return self.cross_section_m2 * self.lip_height_m

    @property
    def pulp_zone_height_m(self) -> float:
        return self.lip_height_m - self.froth_depth_m

    @property
    def pulp_zone_volume_m3(self) -> float:
        """거품층을 제외한 펄프존 체적 (기포 포함)."""
        return self.cross_section_m2 * self.pulp_zone_height_m

    @property
    def effective_slurry_volume_m3(self) -> float:
        """기포 체적을 제외한 실제 슬러리 체적 — 체류시간 계산 기준."""
        return self.pulp_zone_volume_m3 * (1.0 - self.gas_holdup)


def cell_geometry(
    required_slurry_m3: float,
    gas_holdup: float = 0.15,
    froth_depth_m: float = 0.075,
    freeboard_m: float = 0.06,
    height_to_width: float = 1.15,
) -> CellGeometry:
    """필요 슬러리 체적으로부터 정사각 셀 형상을 역산한다.

    거품층 두께와 여유고(freeboard)는 높이에 상수로 더해지므로,
    한 변 길이 ``L`` 에 대해 ``L**2 * (h_pulp + froth + freeboard) = L**3 * r``
    형태의 3차식을 뉴턴법으로 푼다.
    """
    if not 0.0 <= gas_holdup < 1.0:
        raise ValueError("gas_holdup 은 0 이상 1 미만")
    pulp_zone = required_slurry_m3 / (1.0 - gas_holdup)

    # f(L) = r*L**3 - L**2*(froth + freeboard) - pulp_zone = 0
    extra = froth_depth_m + freeboard_m
    l = (pulp_zone / height_to_width) ** (1.0 / 3.0)
    for _ in range(80):
        f = height_to_width * l**3 - extra * l**2 - pulp_zone
        df = 3.0 * height_to_width * l**2 - 2.0 * extra * l
        step = f / df
        l -= step
        if abs(step) < 1e-12:
            break
    shell_height = height_to_width * l
    return CellGeometry(
        width_m=l,
        shell_height_m=shell_height,
        lip_height_m=shell_height - freeboard_m,
        froth_depth_m=froth_depth_m,
        gas_holdup=gas_holdup,
    )


def rounded_cell(
    geometry: CellGeometry,
    width_m: float,
    shell_height_m: float,
) -> CellGeometry:
    """계산값을 제작 편의상 반올림한 치수로 확정한다 (거품층·여유고 유지)."""
    freeboard = geometry.shell_height_m - geometry.lip_height_m
    return CellGeometry(
        width_m=width_m,
        shell_height_m=shell_height_m,
        lip_height_m=shell_height_m - freeboard,
        froth_depth_m=geometry.froth_depth_m,
        gas_holdup=geometry.gas_holdup,
    )


@dataclass(frozen=True)
class ResidenceTime:
    dry_tph: float
    volumetric_flow_m3h: float
    residence_min: float


def residence_time(
    geometry: CellGeometry, volumetric_flow_m3h: float, dry_tph: float = 0.0
) -> ResidenceTime:
    """확정된 셀 형상에서의 실제 유효 체류시간."""
    tau = geometry.effective_slurry_volume_m3 / (volumetric_flow_m3h / 60.0)
    return ResidenceTime(dry_tph, volumetric_flow_m3h, tau)


# --------------------------------------------------------------------------
# 임펠러(로터)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ImpellerDesign:
    diameter_m: float
    stator_od_m: float
    speed_rpm: float
    tip_speed_m_s: float
    ungassed_power_w: float
    gassed_power_w: float
    specific_power_kw_m3: float
    motor_rating_kw: float
    bottom_clearance_m: float


_MOTOR_SERIES_KW = (0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5, 11.0, 15.0)


def select_motor_kw(shaft_power_w: float, service_factor: float = 1.4) -> float:
    """축동력에 여유율을 적용해 표준 모터 용량을 선정한다."""
    required = shaft_power_w / 1000.0 * service_factor
    for rating in _MOTOR_SERIES_KW:
        if rating >= required:
            return rating
    raise ValueError("표준 계열을 초과하는 동력 — 셀 분할 검토 필요")


def impeller_design(
    geometry: CellGeometry,
    pulp_density_kg_m3: float,
    diameter_ratio: float = 0.35,
    tip_speed_m_s: float = 5.5,
    power_number: float = 4.2,
    gassed_power_ratio: float = 0.70,
    stator_ratio: float = 1.35,
    diameter_round_to_m: float = 0.01,
    speed_round_to_rpm: float = 10.0,
) -> ImpellerDesign:
    """로터 지름·회전수·동력 산정.

    동력은 ``P = Np * rho * N**3 * D**5`` (N 은 rev/s) 으로 계산하고,
    급기시 동력저하(relative power demand)를 ``gassed_power_ratio`` 로 반영한다.
    """
    d = round(geometry.width_m * diameter_ratio / diameter_round_to_m) * diameter_round_to_m
    rev_s = tip_speed_m_s / (math.pi * d)
    rpm = round(rev_s * 60.0 / speed_round_to_rpm) * speed_round_to_rpm
    rev_s = rpm / 60.0
    actual_tip = math.pi * d * rev_s

    ungassed = power_number * pulp_density_kg_m3 * rev_s**3 * d**5
    gassed = ungassed * gassed_power_ratio
    return ImpellerDesign(
        diameter_m=d,
        stator_od_m=round(d * stator_ratio, 3),
        speed_rpm=rpm,
        tip_speed_m_s=actual_tip,
        ungassed_power_w=ungassed,
        gassed_power_w=gassed,
        specific_power_kw_m3=ungassed / 1000.0 / geometry.pulp_zone_volume_m3,
        motor_rating_kw=select_motor_kw(ungassed),
        bottom_clearance_m=round(d * 0.6, 3),
    )


# --------------------------------------------------------------------------
# 급기(aeration)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AerationDesign:
    superficial_gas_velocity_cm_s: float
    air_flow_m3h: float
    air_flow_min_m3h: float
    air_flow_max_m3h: float
    bubble_sauter_mean_mm: float
    bubble_surface_area_flux_1_s: float
    static_pressure_kpa: float
    total_pressure_kpa: float
    selection_flow_m3h: float
    selection_pressure_kpa: float
    blower_shaft_power_w: float
    blower_rating_kw: float


def aeration_design(
    geometry: CellGeometry,
    pulp_density_kg_m3: float,
    sparger_clearance_m: float,
    jg_cm_s: float = 1.0,
    jg_min_cm_s: float = 0.6,
    jg_max_cm_s: float = 1.4,
    bubble_d32_mm: float = 1.2,
    sparger_loss_kpa: float = 15.0,
    blower_efficiency: float = 0.55,
) -> AerationDesign:
    """표면기체속도(Jg) 기준 급기량과 송풍기 사양.

    ``Sb = 6 * Jg / d32`` (기포 표면적 플럭스, 1/s) 는 부선속도상수와
    선형관계를 갖는 핵심 지표로, 미립자 부선에서 40~70 1/s 를 목표로 한다.

    Args:
        sparger_clearance_m: 급기점(로터 하단) 높이 — 셀 바닥 기준.
            송풍기 정압은 이 지점의 펄프 수두로 결정된다.
    """
    area = geometry.cross_section_m2
    q = jg_cm_s / 100.0 * area * 3600.0
    submergence = geometry.pulp_zone_height_m - sparger_clearance_m
    if submergence <= 0.0:
        raise ValueError("급기점이 펄프 액면보다 높음")
    static = pulp_density_kg_m3 * G * submergence / 1000.0
    total = static + sparger_loss_kpa
    # 송풍기는 최대 Jg + 압력 여유 30% 로 선정한다.
    q_max = jg_max_cm_s / 100.0 * area * 3600.0
    p_sel = math.ceil(total * 1.3 / 5.0) * 5.0
    shaft = (q_max / 3600.0) * (p_sel * 1000.0) / blower_efficiency
    return AerationDesign(
        superficial_gas_velocity_cm_s=jg_cm_s,
        air_flow_m3h=q,
        air_flow_min_m3h=jg_min_cm_s / 100.0 * area * 3600.0,
        air_flow_max_m3h=jg_max_cm_s / 100.0 * area * 3600.0,
        bubble_sauter_mean_mm=bubble_d32_mm,
        bubble_surface_area_flux_1_s=6.0 * (jg_cm_s / 100.0) / (bubble_d32_mm / 1000.0),
        static_pressure_kpa=static,
        total_pressure_kpa=total,
        selection_flow_m3h=math.ceil(q_max / 5.0) * 5.0,
        selection_pressure_kpa=p_sel,
        blower_shaft_power_w=shaft,
        blower_rating_kw=select_motor_kw(shaft, service_factor=1.5),
    )


# --------------------------------------------------------------------------
# 거품 배출 부하
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FrothLoading:
    concentrate_tph: float
    froth_area_m2: float
    lip_length_m: float
    carry_rate_tph_m2: float
    lip_loading_tph_m: float
    carry_rate_limit_tph_m2: float
    lip_loading_limit_tph_m: float

    @property
    def carry_rate_ok(self) -> bool:
        return self.carry_rate_tph_m2 <= self.carry_rate_limit_tph_m2

    @property
    def lip_loading_ok(self) -> bool:
        return self.lip_loading_tph_m <= self.lip_loading_limit_tph_m


def froth_loading(
    geometry: CellGeometry,
    concentrate_tph: float,
    lip_sides: int = 2,
    crowder_area_ratio: float = 1.0,
    carry_rate_limit_tph_m2: float = 1.5,
    lip_loading_limit_tph_m: float = 1.5,
) -> FrothLoading:
    """정광 배출 능력 검토 (froth carry rate / lip loading)."""
    area = geometry.cross_section_m2 * crowder_area_ratio
    lip = geometry.width_m * lip_sides
    return FrothLoading(
        concentrate_tph=concentrate_tph,
        froth_area_m2=area,
        lip_length_m=lip,
        carry_rate_tph_m2=concentrate_tph / area,
        lip_loading_tph_m=concentrate_tph / lip,
        carry_rate_limit_tph_m2=carry_rate_limit_tph_m2,
        lip_loading_limit_tph_m=lip_loading_limit_tph_m,
    )
