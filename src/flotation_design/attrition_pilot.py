"""파일럿 어트리션 셀 PAS-1 — 블랙파우더(31~75 µm) EVA 박리 시험 셀.

무엇을 확인하려는가
------------------
PV 블랙파우더(셀 분쇄 미분)의 Si 표면에 붙은 EVA 를 **기계적으로** 떼어낼 수
있는지, 뗀다면 **몇 kWh/t 에서, Si 를 얼마나 깨뜨리면서** 떼는지. 같은 셀이
AS-1 의 시험 T-1(스크럽 강도 스윕)도 맡는다. 플랜트 설비가 아니라 제작해서
시험하는 장비다.

기각한 방식
----------
1. **로터-스테이터 고전단 믹서.** 유체가 입자 표면에 거는 전단응력은
   로터-스테이터 간극의 통상 상한 전단속도(1e5 /s)를 그대로 써도 70 wt% 슬러리
   에서 약 1 kPa 다. 라미네이트 EVA 의 접착·응집 강도는 MPa 급이라 **천 배
   가까이 모자란다.** 서브mm 간극은 50 vol% 연마성 Si 슬러리에서 버티지도 못한다.
2. **비드밀.** 세라믹 비드 습식 밀링은 미세 Si 를 **만드는** 방법이다. 무른
   EVA 보다 취성인 Si 가 먼저 깨지고, 비드 마모분이 시료를 오염시킨다.
3. **열분해 (450~550 °C).** EVA 는 확실히 없어진다. 기계식이 시험에서 탈락하면
   가는 대안이며, 이 모듈의 범위 밖이다.

남는 기계식 경로는 **어트리션**뿐이다. 50 vol% 층에서 각진 Si 모서리가 무른
EVA 막을 긁는다 — 입자 접촉점의 국부 응력은 유체 전단과 차원이 다르다. 다만
미분에서의 효율을 보여주는 문헌이 없다. 31~75 µm 입자는 t 당 표면적이
실리카사(500 µm)의 약 12배라, 모래에서 쓰던 kWh/t 로 같은 결과를 기대할 수
없다. **그래서 시험 셀이 먼저다.**

설계 논리
--------
1. **AS-1 과 기하 상사.** 팔각조, 깊이/폭 1.2, 대향 피치 2단, D/W 0.5, 간격 1D.
   흐름 구조가 같으므로 **주속과 비에너지(kWh/t)** 만 맞추면 결과가 AS-1 로
   넘어간다. 체적당 동력은 스케일업 변수가 아니다 — 같은 주속에서 D 에 반비례해
   파일럿 쪽이 크다.
2. **회분식 + 시간 채취.** 한 회분으로 비에너지 곡선 전체를 얻는다. 연속식은
   체류시간 분포 때문에 입자마다 받은 에너지가 달라 곡선이 흐려진다.
3. **회분 질량은 시료가 정한다.** 채취점 수 x 시료 질량을 빼도 회분이 10 %
   넘게 줄지 않는 최소량.
4. **에너지는 축 토크로 잰다.** 1 kW 급에서는 모터·VFD 손실이 입력의 수십 %
   라 전력계로 재면 kWh/t 가 그만큼 부풀고 스케일업이 틀어진다. 빈 조(공기
   중)에서 같은 회전수로 잰 베어링·씰 마찰 토크를 빼면 슬러리에 들어간 순
   입력이 남는다. 물만 넣은 토크를 빼면 안 된다 — 액체 교반 손실도 AS-1 의
   비에너지 정의(슬러리 흡수동력 / 건조 고체)에 들어 있는 몫이다.
5. **모터는 상한 주속에서 고른다.** 시험 셀은 주속 범위 전체를 돌려야 한다.
6. **접액부 전부 금속.** 고무·우레탄 마모분은 유기물이라 TGA 로 재는 잔류
   EVA 에 섞인다.
7. **온도를 고정한다.** 단열이면 1 kWh/t 에 약 1.4 K 오른다. 재킷과
   온도조절기(TCU)로 설정값을 지켜 온도와 비에너지가 뒤섞이지 않게 한다.
   가장 낮은 설정 온도를 가장 높은 주속에서 지킬 수 있어야 한다.
8. **수소.** 블랙파우더에는 후면 전극 Al 이 있고, 새로 깨진 Si 면도 물과
   반응한다. 덮개 있는 조의 헤드스페이스를 배기하고 검지한다. 알칼리성
   분산제는 반응을 빠르게 하므로 쓰지 않는다.

연속 설비로의 환산
----------------
회분에서는 모든 입자가 같은 에너지를 받지만, 완전혼합조 직렬에서는 체류시간
분포 때문에 적게 받는 입자가 생긴다. 박리가 비에너지에 대해 1차라고 보면
(P-1 의 곡선으로 검증), 같은 제거율에 필요한 연속 평균 비에너지는 회분의 몇
배가 된다 — ``continuous_energy_factor``. 90 % 제거에서 1기는 3.9배,
2기(AS-1)는 1.9배, 3기는 1.5배다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .attrition import (
    AttritionCellGeometry,
    AttritionDrive,
    AttritionScrubber,
    AttritionShaft,
    attrition_drive,
    octagon_area_m2,
    octagon_width_m,
    solid_shaft,
    solids_mass_fraction_for_volume_fraction,
)
from .sizing import select_motor_kw

WATER_CP_KJ_KGK = 4.18
AL_MOLAR_MASS_KG_MOL = 0.026982
#: 0 °C, 1 atm 기체 몰부피.
MOLAR_VOLUME_NM3_MOL = 0.022414


# --------------------------------------------------------------------------
# 방식 선정 근거
# --------------------------------------------------------------------------
def relative_viscosity(
    volume_fraction: float, max_packing: float = 0.64, intrinsic_viscosity: float = 2.5
) -> float:
    """Krieger–Dougherty 상대점도 ``(1 - phi/phi_m)^(-[eta] phi_m)``."""
    if not 0.0 <= volume_fraction < max_packing:
        raise ValueError("체적분율은 0 이상, 최대 충전분율 미만이어야 함")
    return (1.0 - volume_fraction / max_packing) ** (-intrinsic_viscosity * max_packing)


def fluid_shear_stress_pa(
    shear_rate_s: float, volume_fraction: float, liquid_viscosity_pa_s: float = 1.0e-3
) -> float:
    """슬러리가 입자 표면에 걸 수 있는 유체 전단응력 = 유효점도 x 전단속도.

    로터-스테이터가 EVA 를 벗길 수 있는지 판단하는 상한값이다. 고농도일수록
    유효점도가 커지지만, 그래도 kPa 급을 넘지 못한다.
    """
    if shear_rate_s < 0:
        raise ValueError("전단속도는 0 이상")
    return liquid_viscosity_pa_s * relative_viscosity(volume_fraction) * shear_rate_s


def specific_surface_m2_kg(diameter_m: float, solids_sg: float) -> float:
    """구형 가정 비표면적 ``6 / (rho d)`` — t 당 벗겨야 할 표면의 양."""
    if diameter_m <= 0 or solids_sg <= 0:
        raise ValueError("입경과 비중은 양수여야 함")
    return 6.0 / (solids_sg * 1000.0 * diameter_m)


@dataclass(frozen=True)
class MechanismScreen:
    """방식 선정표 — 왜 로터-스테이터가 아니고 어트리션인가.

    Attributes:
        shear_rate_s: 로터-스테이터 간극 전단속도 (통상 상한).
        volume_fraction: 스크러빙 농도의 고체 체적분율.
        eva_strength_mpa: 라미네이트 EVA 접착·응집 강도 (보수적 하한).
        feed_size_um: 시험 분획 체 범위 (하한, 상한).
        solids_sg: 시험 분획 고체 비중.
        sand_um, sand_sg: 비교 기준 — 실리카사 스크러빙의 대표 입자.
    """

    shear_rate_s: float
    volume_fraction: float
    eva_strength_mpa: float
    feed_size_um: tuple[float, float]
    solids_sg: float
    sand_um: float
    sand_sg: float

    @property
    def fluid_shear_pa(self) -> float:
        return fluid_shear_stress_pa(self.shear_rate_s, self.volume_fraction)

    @property
    def shear_shortfall(self) -> float:
        """EVA 강도 / 유체 전단응력 — 로터-스테이터가 모자라는 배수."""
        return self.eva_strength_mpa * 1e6 / self.fluid_shear_pa

    @property
    def representative_size_um(self) -> float:
        """체 분획의 대표 입경 — 상·하한의 기하평균."""
        low, high = self.feed_size_um
        return math.sqrt(low * high)

    @property
    def feed_surface_m2_kg(self) -> float:
        return specific_surface_m2_kg(self.representative_size_um * 1e-6, self.solids_sg)

    @property
    def sand_surface_m2_kg(self) -> float:
        return specific_surface_m2_kg(self.sand_um * 1e-6, self.sand_sg)

    @property
    def surface_ratio_to_sand(self) -> float:
        """t 당 벗겨야 할 표면이 실리카사의 몇 배인가."""
        return self.feed_surface_m2_kg / self.sand_surface_m2_kg


# --------------------------------------------------------------------------
# 연속 설비로의 환산
# --------------------------------------------------------------------------
def continuous_energy_factor(target_removal: float, cells: int) -> float:
    """회분과 같은 제거율을 완전혼합조 n 기 직렬로 얻는 데 드는 비에너지 배수.

    박리가 비에너지 E 에 대해 1차(``1 - X = exp(-kE)``)라고 보면 회분은
    ``kE = -ln(1-X)``, n 기 직렬은 ``kE = n((1-X)^(-1/n) - 1)`` 이 필요하다.
    n 이 무한대면 1 에 수렴한다 (플러그 흐름 = 회분).
    """
    if not 0.0 < target_removal < 1.0:
        raise ValueError("목표 제거율은 0~1 사이여야 함")
    if cells < 1:
        raise ValueError("cells 는 1 이상이어야 함")
    residual = 1.0 - target_removal
    batch = -math.log(residual)
    continuous = cells * (residual ** (-1.0 / cells) - 1.0)
    return continuous / batch


# --------------------------------------------------------------------------
# 수소
# --------------------------------------------------------------------------
def hydrogen_from_aluminium_nm3(aluminium_kg: float) -> float:
    """``2Al + 6H2O -> 2Al(OH)3 + 3H2`` — Al 1 kg 당 약 1.25 Nm3."""
    if aluminium_kg < 0:
        raise ValueError("Al 질량은 0 이상")
    return aluminium_kg / AL_MOLAR_MASS_KG_MOL * 1.5 * MOLAR_VOLUME_NM3_MOL


def ventilation_for_hydrogen_m3h(
    hydrogen_nm3h: float, lel_vol: float, design_lel_fraction: float
) -> float:
    """수소 발생량을 설계 상한(폭발하한의 일정 비율) 아래로 희석하는 배기량."""
    if hydrogen_nm3h < 0:
        raise ValueError("수소 발생량은 0 이상")
    if not 0.0 < lel_vol < 1.0 or not 0.0 < design_lel_fraction <= 1.0:
        raise ValueError("폭발하한과 설계 비율이 범위를 벗어남")
    return hydrogen_nm3h / (lel_vol * design_lel_fraction)


def tolerable_aluminium_reaction_kg_h(
    vent_m3h: float, lel_vol: float, design_lel_fraction: float
) -> float:
    """배기량이 헤드스페이스를 설계 상한 아래로 묶어 둘 수 있는 Al 반응 속도."""
    if vent_m3h <= 0:
        raise ValueError("배기량은 양수여야 함")
    return vent_m3h * lel_vol * design_lel_fraction / hydrogen_from_aluminium_nm3(1.0)


# --------------------------------------------------------------------------
# 열
# --------------------------------------------------------------------------
def adiabatic_rise_k_per_kwh_t(solids_mass_fraction: float, solids_cp_kj_kgk: float) -> float:
    """비에너지 1 kWh/t 가 전부 열이 될 때의 슬러리 온도 상승 (K).

    교반 동력은 결국 전부 열이 된다. 고체 1 t 에 딸린 슬러리의 열용량으로 나눈다.
    """
    if not 0.0 < solids_mass_fraction < 1.0:
        raise ValueError("solids_mass_fraction 은 0~1 사이여야 함")
    if solids_cp_kj_kgk <= 0:
        raise ValueError("비열은 양수여야 함")
    water_per_solid = (1.0 - solids_mass_fraction) / solids_mass_fraction
    heat_capacity_kj_k_per_t = 1000.0 * (solids_cp_kj_kgk + water_per_solid * WATER_CP_KJ_KGK)
    return 3600.0 / heat_capacity_kj_k_per_t


# --------------------------------------------------------------------------
# 시험 셀
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SamplePoint:
    """회분 1회 중 시료 1점을 뜨는 시점.

    Attributes:
        energy_kwh_t: 이 시점까지 조 안의 고체가 받은 누적 비에너지.
        elapsed_min: 교반 시작부터의 경과 시간.
        dry_kg_before: 시료를 뜨기 직전 조 안의 건조 고체.
        fill_level_m: 시료를 뜨기 직전 액면 높이.
    """

    energy_kwh_t: float
    elapsed_min: float
    dry_kg_before: float
    fill_level_m: float


@dataclass(frozen=True)
class PilotCell:
    """회분식 파일럿 어트리션 셀 1기."""

    tag: str
    duty: str
    solids_sg: float
    solids_mass_fraction: float
    minimum_solids_volume_fraction: float
    batch_dry_kg: float
    sample_dry_kg: float
    max_withdrawal: float
    energy_points_kwh_t: tuple[float, ...]
    test_tip_speeds_m_s: tuple[float, ...]
    temperatures_c: tuple[float, ...]
    geometry: AttritionCellGeometry
    drive: AttritionDrive
    shaft: AttritionShaft
    impeller_clearance_m: float
    min_submergence_ratio: float
    jacket_u_w_m2k: float
    tcu_min_supply_c: float
    solids_cp_kj_kgk: float
    torque_sensor_nm: float
    wetted_material: str
    vent_m3h: float
    aluminium_mass_fraction: float
    h2_lel_vol: float
    h2_design_lel_fraction: float

    # -- 회분 -------------------------------------------------------------
    @property
    def pulp_density_kg_m3(self) -> float:
        w = self.solids_mass_fraction
        return 1000.0 / (w / self.solids_sg + (1.0 - w))

    @property
    def solids_volume_fraction(self) -> float:
        w = self.solids_mass_fraction
        solid = w / self.solids_sg
        return solid / (solid + (1.0 - w))

    @property
    def low_solids_mass_fraction(self) -> float:
        """농도 시험의 낮은 수준 — 입자가 닿는 체적분율 하한에 해당하는 wt%."""
        return solids_mass_fraction_for_volume_fraction(
            self.minimum_solids_volume_fraction, self.solids_sg
        )

    @property
    def slurry_kg(self) -> float:
        return self.batch_dry_kg / self.solids_mass_fraction

    @property
    def water_kg(self) -> float:
        return self.slurry_kg - self.batch_dry_kg

    @property
    def slurry_volume_m3(self) -> float:
        return self.slurry_kg / self.pulp_density_kg_m3

    @property
    def fill_level_m(self) -> float:
        """회분을 다 넣었을 때의 액면 — 형상의 유효 깊이와 같다."""
        return self.geometry.depth_m

    @property
    def depth_to_width(self) -> float:
        return self.fill_level_m / self.geometry.across_flats_m

    @property
    def samples_per_batch(self) -> int:
        return len(self.energy_points_kwh_t)

    @property
    def withdrawal_fraction(self) -> float:
        return self.samples_per_batch * self.sample_dry_kg / self.batch_dry_kg

    @property
    def minimum_fill_level_m(self) -> float:
        """시료를 다 뜬 뒤의 액면. 농도가 같으므로 액면은 건조 고체에 비례한다."""
        return self.fill_level_m * (1.0 - self.withdrawal_fraction)

    @property
    def upper_impeller_elevation_m(self) -> float:
        """바닥에서 상단 임펠러까지 — 하단 간극 + 임펠러 간격(1 D)."""
        return self.impeller_clearance_m + self.drive.spacing_m

    @property
    def minimum_submergence_m(self) -> float:
        return self.minimum_fill_level_m - self.upper_impeller_elevation_m

    @property
    def submergence_ok(self) -> bool:
        return self.minimum_submergence_m >= self.min_submergence_ratio * self.drive.diameter_m

    # -- 동력·토크 --------------------------------------------------------
    @property
    def max_test_tip_speed_m_s(self) -> float:
        return max(self.test_tip_speeds_m_s)

    def power_w(self, tip_speed_m_s: float) -> float:
        return self.drive.power_w_at_tip_speed(tip_speed_m_s)

    def speed_rpm(self, tip_speed_m_s: float) -> float:
        return self.drive.speed_rpm_at_tip_speed(tip_speed_m_s)

    def torque_nm(self, tip_speed_m_s: float) -> float:
        """운전 토크 — 토크센서가 읽는 값. 주속의 제곱에 비례한다."""
        omega = 2.0 * math.pi * self.speed_rpm(tip_speed_m_s) / 60.0
        return self.power_w(tip_speed_m_s) / omega

    def specific_power_kw_m3(self, tip_speed_m_s: float) -> float:
        return self.power_w(tip_speed_m_s) / 1000.0 / self.slurry_volume_m3

    @property
    def torque_sensor_ok(self) -> bool:
        """센서 정격이 기동 토크(최대 주속 운전 토크 x 서비스계수)를 담는지."""
        return self.torque_sensor_nm >= self.shaft.torque_nm

    @property
    def lowest_torque_fraction(self) -> float:
        """가장 낮은 주속의 운전 토크가 센서 정격의 몇 % 인가 — 판독 분해능."""
        return self.torque_nm(min(self.test_tip_speeds_m_s)) / self.torque_sensor_nm

    # -- 시료 일정 --------------------------------------------------------
    def schedule(self, tip_speed_m_s: float) -> tuple[SamplePoint, ...]:
        """주속별 시료 채취 시각.

        비에너지는 조 안에 남은 고체 기준으로 쌓인다. 시료를 뜰 때마다 고체가
        줄어 같은 동력에서 t 당 에너지가 빨리 오르므로, 구간마다 남은 질량으로
        나눈다. 동력은 임펠러가 잠겨 있는 한 액면과 무관하다고 본다.
        """
        power_kw = self.power_w(tip_speed_m_s) / 1000.0
        if power_kw <= 0:
            raise ValueError("주속은 양수여야 함")
        dry_kg = self.batch_dry_kg
        elapsed_h = 0.0
        previous = 0.0
        points = []
        for energy in self.energy_points_kwh_t:
            elapsed_h += (energy - previous) * dry_kg / 1000.0 / power_kw
            points.append(
                SamplePoint(
                    energy_kwh_t=energy,
                    elapsed_min=elapsed_h * 60.0,
                    dry_kg_before=dry_kg,
                    fill_level_m=self.fill_level_m * dry_kg / self.batch_dry_kg,
                )
            )
            dry_kg -= self.sample_dry_kg
            previous = energy
        return tuple(points)

    def run_minutes(self, tip_speed_m_s: float) -> float:
        return self.schedule(tip_speed_m_s)[-1].elapsed_min

    # -- 열 ---------------------------------------------------------------
    @property
    def adiabatic_rise_k_per_kwh_t(self) -> float:
        return adiabatic_rise_k_per_kwh_t(self.solids_mass_fraction, self.solids_cp_kj_kgk)

    @property
    def adiabatic_rise_at_max_energy_k(self) -> float:
        return self.adiabatic_rise_k_per_kwh_t * max(self.energy_points_kwh_t)

    @property
    def jacket_area_m2(self) -> float:
        """재킷 전열면 — 액면 아래 팔각 측벽 + 바닥."""
        perimeter = 8.0 * self.geometry.across_flats_m * math.tan(math.pi / 8.0)
        return perimeter * self.fill_level_m + self.geometry.plan_area_m2

    def coolant_approach_k(self, tip_speed_m_s: float) -> float:
        """설정값을 지키려면 냉매가 슬러리보다 이만큼 차가워야 한다."""
        return self.power_w(tip_speed_m_s) / (self.jacket_u_w_m2k * self.jacket_area_m2)

    def coolant_supply_c(self, setpoint_c: float, tip_speed_m_s: float) -> float:
        return setpoint_c - self.coolant_approach_k(tip_speed_m_s)

    @property
    def worst_coolant_supply_c(self) -> float:
        """가장 낮은 설정 온도를 가장 높은 주속에서 지킬 때의 냉매 공급 온도."""
        return self.coolant_supply_c(min(self.temperatures_c), self.max_test_tip_speed_m_s)

    @property
    def temperature_control_ok(self) -> bool:
        return self.worst_coolant_supply_c >= self.tcu_min_supply_c

    # -- 수소 -------------------------------------------------------------
    @property
    def aluminium_in_batch_kg(self) -> float:
        return self.batch_dry_kg * self.aluminium_mass_fraction

    @property
    def tolerable_aluminium_reaction_per_h(self) -> float:
        """배기가 견디는 Al 반응 속도 — 회분 Al 대비 시간당 분율."""
        kg_h = tolerable_aluminium_reaction_kg_h(
            self.vent_m3h, self.h2_lel_vol, self.h2_design_lel_fraction
        )
        return kg_h / self.aluminium_in_batch_kg

    # -- 종합 -------------------------------------------------------------
    @property
    def is_adequate(self) -> bool:
        return (
            self.solids_volume_fraction >= self.minimum_solids_volume_fraction
            and self.withdrawal_fraction <= self.max_withdrawal + 1e-12
            and self.submergence_ok
            and self.shaft.is_safe
            and self.torque_sensor_ok
            and self.temperature_control_ok
            and self.drive.tip_speed_ceiling_m_s >= self.max_test_tip_speed_m_s - 1e-9
        )


def size_pilot_cell(
    tag: str,
    duty: str,
    solids_sg: float,
    aluminium_mass_fraction: float,
    energy_points_kwh_t: tuple[float, ...],
    test_tip_speeds_m_s: tuple[float, ...],
    reference_tip_speed_m_s: float,
    temperatures_c: tuple[float, ...],
    sample_dry_kg: float = 0.30,
    max_withdrawal: float = 0.10,
    batch_round_kg: float = 5.0,
    solids_mass_fraction: float = 0.70,
    minimum_solids_volume_fraction: float = 0.40,
    depth_to_width: float = 1.2,
    freeboard_m: float = 0.10,
    impeller_ratio: float = 0.50,
    impellers_per_shaft: int = 2,
    power_number: float = 0.80,
    impeller_mass_coeff_kg_m3: float = 500.0,
    impeller_clearance_ratio: float = 0.5,
    min_submergence_ratio: float = 0.5,
    shaft_length_margin_m: float = 0.25,
    motor_service_factor: float = 1.4,
    torque_service_factor: float = 2.0,
    allowable_shear_mpa: float = 40.0,
    critical_speed_ratio_min: float = 1.5,
    allowable_deflection_mm: float = 5.0,
    jacket_u_w_m2k: float = 350.0,
    tcu_min_supply_c: float = -5.0,
    solids_cp_kj_kgk: float = 0.73,
    torque_sensor_series_nm: tuple[float, ...] = (5.0, 10.0, 20.0, 50.0, 100.0),
    vent_m3h: float = 30.0,
    h2_lel_vol: float = 0.04,
    h2_design_lel_fraction: float = 0.25,
    wetted_material: str = "SUS316L 전 접액부 (라이닝·피복 없음)",
    round_to_m: float = 0.005,
    speed_round_to_rpm: float = 10.0,
) -> PilotCell:
    """시료 계획에서 회분 질량을 정하고, AS-1 과 기하 상사인 시험 셀을 산정한다.

    Raises:
        ValueError: 채취 계획이나 주속 범위가 물리적으로 성립하지 않을 때.
    """
    if not energy_points_kwh_t or energy_points_kwh_t[0] < 0:
        raise ValueError("채취 비에너지는 0 이상에서 시작해야 함")
    if any(b <= a for a, b in zip(energy_points_kwh_t, energy_points_kwh_t[1:])):
        raise ValueError("채취 비에너지는 증가 순이어야 함")
    if not test_tip_speeds_m_s or min(test_tip_speeds_m_s) <= 0:
        raise ValueError("시험 주속은 양수여야 함")
    if sample_dry_kg <= 0 or not 0.0 < max_withdrawal < 1.0:
        raise ValueError("시료 질량과 허용 인출 비율이 범위를 벗어남")
    if not 0.0 < aluminium_mass_fraction < 1.0:
        raise ValueError("Al 질량분율은 0~1 사이여야 함")

    # 1. 회분 질량 — 시료를 다 떠도 허용 인출 비율 안에 드는 최소량을 올림
    required = len(energy_points_kwh_t) * sample_dry_kg / max_withdrawal
    batch = math.ceil(round(required / batch_round_kg, 9)) * batch_round_kg

    # 2. 슬러리 체적 → 팔각조 폭(제작 치수로 올림) → 액면 = 체적 / 면적
    w = solids_mass_fraction
    pulp_density = 1000.0 / (w / solids_sg + (1.0 - w))
    volume = batch / w / pulp_density
    width = octagon_width_m(volume, depth_to_width, round_to_m)
    geometry = AttritionCellGeometry(
        across_flats_m=width,
        depth_m=volume / octagon_area_m2(width),
        freeboard_m=freeboard_m,
    )

    # 3. 구동부 — 회전수는 기준 주속에서, 모터는 상한 주속에서
    top = max(test_tip_speeds_m_s)
    drive = attrition_drive(
        width,
        pulp_density,
        reference_tip_speed_m_s,
        (min(test_tip_speeds_m_s), top),
        impeller_ratio=impeller_ratio,
        impellers_per_shaft=impellers_per_shaft,
        power_number=power_number,
        impeller_mass_coeff_kg_m3=impeller_mass_coeff_kg_m3,
        motor_service_factor=motor_service_factor,
        speed_round_to_rpm=speed_round_to_rpm,
        motor_sizing_tip_speed_m_s=top,
    )

    # 4. 축 — 상한 주속에서 검산 (구동부가 뚜껑 위 브리지에 앉는다)
    shaft = solid_shaft(
        absorbed_power_w=drive.power_w_at_tip_speed(top),
        speed_rpm=drive.speed_rpm_at_tip_speed(top),
        length_m=geometry.shell_height_m + shaft_length_margin_m,
        overhung_mass_kg=drive.assembly_mass_kg,
        allowable_shear_mpa=allowable_shear_mpa,
        torque_service_factor=torque_service_factor,
        critical_speed_ratio_min=critical_speed_ratio_min,
        allowable_deflection_mm=allowable_deflection_mm,
    )

    # 5. 토크센서 — 기동 토크를 담는 최소 정격
    sensor = next((r for r in torque_sensor_series_nm if r >= shaft.torque_nm), None)
    if sensor is None:
        raise ValueError("토크센서 정격 계열을 초과")

    return PilotCell(
        tag=tag,
        duty=duty,
        solids_sg=solids_sg,
        solids_mass_fraction=solids_mass_fraction,
        minimum_solids_volume_fraction=minimum_solids_volume_fraction,
        batch_dry_kg=batch,
        sample_dry_kg=sample_dry_kg,
        max_withdrawal=max_withdrawal,
        energy_points_kwh_t=tuple(energy_points_kwh_t),
        test_tip_speeds_m_s=tuple(test_tip_speeds_m_s),
        temperatures_c=tuple(temperatures_c),
        geometry=geometry,
        drive=drive,
        shaft=shaft,
        impeller_clearance_m=impeller_clearance_ratio * drive.diameter_m,
        min_submergence_ratio=min_submergence_ratio,
        jacket_u_w_m2k=jacket_u_w_m2k,
        tcu_min_supply_c=tcu_min_supply_c,
        solids_cp_kj_kgk=solids_cp_kj_kgk,
        torque_sensor_nm=sensor,
        wetted_material=wetted_material,
        vent_m3h=vent_m3h,
        aluminium_mass_fraction=aluminium_mass_fraction,
        h2_lel_vol=h2_lel_vol,
        h2_design_lel_fraction=h2_design_lel_fraction,
    )


# --------------------------------------------------------------------------
# AS-1 로 옮기기
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PilotScaleUp:
    """파일럿 회분 결과를 AS-1 연속 운전으로 옮기는 판정표.

    AS-1 이 낼 수 있는 연속 비에너지를 환산 배수로 나누면, **파일럿에서 목표
    제거율을 얻은 회분 비에너지가 얼마 이하여야 AS-1 이 그대로 감당하는지**가
    나온다. 파일럿 결과를 이 한계와 비교하는 것이 판정의 전부다.

    Attributes:
        energy_factor: 연속 평균 비에너지 / 회분 비에너지 (AS-1 셀 수 기준).
        ceiling_tip_speed_m_s: AS-1 의 현재 VFD 상한 (모터 정격이 막는 곳).
        practical_max_tip_speed_m_s: 주속 실무 상한 — 모터를 키우면 여기까지.
        upsized_motor_kw: 실무 상한까지 돌리는 데 필요한 셀당 모터.
        upsized_critical_speed_ratio: 모터를 키워 실무 상한까지 돌릴 때 현
            축의 임계회전수 여유. 모터만 바꾸면 되는지는 이 값이 정한다.
    """

    target_removal: float
    cells: int
    energy_factor: float
    peak_tph: float
    average_tph: float
    ceiling_tip_speed_m_s: float
    practical_max_tip_speed_m_s: float
    as1_peak_kwh_t: float
    as1_peak_upsized_kwh_t: float
    as1_average_upsized_kwh_t: float
    upsized_motor_kw: float
    upsized_critical_speed_ratio: float
    minimum_critical_speed_ratio: float

    @property
    def upsized_shaft_ok(self) -> bool:
        return self.upsized_critical_speed_ratio >= self.minimum_critical_speed_ratio

    @property
    def batch_limit_peak_kwh_t(self) -> float:
        """이 이하면 AS-1 그대로, 최대 처리량에서도 목표 제거율."""
        return self.as1_peak_kwh_t / self.energy_factor

    @property
    def batch_limit_peak_upsized_kwh_t(self) -> float:
        """이 이하면 모터만 키워 최대 처리량에서 목표 제거율."""
        return self.as1_peak_upsized_kwh_t / self.energy_factor

    @property
    def batch_limit_average_upsized_kwh_t(self) -> float:
        """이 이하면 모터를 키우고 평균 처리량으로 줄여 목표 제거율. 넘으면 AS-1 로는 안 된다."""
        return self.as1_average_upsized_kwh_t / self.energy_factor


def pilot_scale_up(
    scrubber: AttritionScrubber,
    peak_tph: float,
    average_tph: float,
    target_removal: float,
) -> PilotScaleUp:
    """AS-1 의 연속 비에너지 능력을 회분 비에너지 한계로 바꾼다."""
    drive = scrubber.drive
    ceiling = drive.tip_speed_ceiling_m_s
    practical = drive.tip_speed_max_m_s
    return PilotScaleUp(
        target_removal=target_removal,
        cells=scrubber.cells,
        energy_factor=continuous_energy_factor(target_removal, scrubber.cells),
        peak_tph=peak_tph,
        average_tph=average_tph,
        ceiling_tip_speed_m_s=ceiling,
        practical_max_tip_speed_m_s=practical,
        as1_peak_kwh_t=scrubber.specific_energy_kwh_t(peak_tph, ceiling),
        as1_peak_upsized_kwh_t=scrubber.specific_energy_kwh_t(peak_tph, practical),
        as1_average_upsized_kwh_t=scrubber.specific_energy_kwh_t(average_tph, practical),
        upsized_motor_kw=select_motor_kw(
            drive.power_w_at_tip_speed(practical), drive.service_factor
        ),
        upsized_critical_speed_ratio=(
            scrubber.shaft.critical_speed_rpm / drive.speed_rpm_at_tip_speed(practical)
        ),
        minimum_critical_speed_ratio=scrubber.shaft.minimum_critical_speed_ratio,
    )
