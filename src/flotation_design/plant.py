"""설비 전체 조립 — 1안(연속 부선조)과 2안(기계식 3단).

두 안 모두 동일한 급광 사양과 동일한 부선 거동 모델을 쓰므로 직접 비교할
수 있다. 차이는 오직 **장치 형식**에서 온다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import design_basis as db
from .attrition import AttritionScrubber, DilutionBox, dilution_box, size_attrition
from .circuit import CircuitResult, FlotationUnit, solve_circuit
from .conditioning import ConditionerDesign, conditioner_train
from .feed import FeedSpec
from .rfc import RfcDesign, RfcOperatingPoint, RfcPerformance, rfc_separation, size_rfc
from .sizing import (
    HollowShaftDesign,
    AerationDesign,
    CellGeometry,
    FrothLoading,
    ImpellerDesign,
    aeration_design,
    froth_loading,
    impeller_design,
    hollow_shaft,
    required_slurry_volume,
    select_motor_kw,
)
from .dewatering import FilterPress, filter_press

WATER_DENSITY = 1000.0

#: 미광 농축조 상승속도 (m/h) — 미립 Si 슬러리 기준 보수값.
THICKENER_RISE_RATE_M_H = 1.2


def _slurry_density(solids_wt: float, solids_sg: float) -> float:
    return WATER_DENSITY / (solids_wt / solids_sg + (1.0 - solids_wt))


@dataclass(frozen=True)
class Thickener:
    """농축조 1기."""

    tag: str
    duty: str
    overflow_m3h: float
    rise_rate_m_h: float

    @property
    def area_m2(self) -> float:
        return self.overflow_m3h / self.rise_rate_m_h

    @property
    def diameter_m(self) -> float:
        return math.ceil(math.sqrt(4.0 * self.area_m2 / math.pi) * 2.0) / 2.0


def _concentrate_filter(tag: str, dry_tph: float, solids_sg: float) -> FilterPress:
    """정광 필터프레스 — 값이 나가는 산물이라 함수율을 낮게 잡는다."""
    return filter_press(
        tag, "정광 탈수 (제련·침출 급광)", dry_tph,
        feed_solids_wt=db.THICKENER_UNDERFLOW_SOLIDS["concentrate"],
        solids_sg=solids_sg,
        cake_moisture=db.CAKE_MOISTURE["concentrate"],
        specific_rate_kg_m2_h=db.FILTER_SPECIFIC_RATE["concentrate"],
        cycle_min=db.FILTER_CYCLE_MIN["concentrate"],
        min_plate_mm=db.FILTER_MIN_PLATE_MM["concentrate"],
    )


def _tailings_filter(tag: str, dry_tph: float, solids_sg: float) -> FilterPress:
    """미광 필터프레스 — 물 회수와 건식 적치가 목적."""
    return filter_press(
        tag, "미광 탈수 (공정수 회수 · 건식 적치)", dry_tph,
        feed_solids_wt=db.THICKENER_UNDERFLOW_SOLIDS["tailings"],
        solids_sg=solids_sg,
        cake_moisture=db.CAKE_MOISTURE["tailings"],
        specific_rate_kg_m2_h=db.FILTER_SPECIFIC_RATE["tailings"],
        cycle_min=db.FILTER_CYCLE_MIN["tailings"],
        min_plate_mm=db.FILTER_MIN_PLATE_MM["tailings"],
    )


@dataclass(frozen=True)
class RfcOption:
    """1안 — 세척수 bias 연속 부선조 1단."""

    design: RfcDesign
    point_avg: RfcOperatingPoint
    point_peak: RfcOperatingPoint
    performance_avg: RfcPerformance
    performance_peak: RfcPerformance
    conditioners: tuple[ConditionerDesign, ...]
    tailings_thickener: Thickener
    concentrate_thickener: Thickener
    concentrate_filter: FilterPress
    tailings_filter: FilterPress

    @property
    def installed_kw(self) -> float:
        # 송풍기 + 급광펌프 + 미광펌프 + 조건조 교반 + 정량펌프
        return (
            self.design.blower_rating_kw
            + 1.5
            + 0.75
            + sum(c.agitator_kw for c in self.conditioners)
            + 0.2
            + self.concentrate_filter.pump_rating_kw
            + self.tailings_filter.pump_rating_kw
        )

    @property
    def filtrate_m3h(self) -> float:
        """필터프레스 여액 — 러퍼(1안은 조건조) 급광으로 되돌린다."""
        return (
            self.concentrate_filter.filtrate_m3h + self.tailings_filter.filtrate_m3h
        )

    @property
    def filtrate_return_to(self) -> str:
        return db.FILTRATE_RETURN_TO["rfc"]

    @property
    def water_recycle_m3h(self) -> float:
        """농축조 월류수와 필터 여액의 총 회수량 (블리드 전)."""
        return (
            self.tailings_thickener.overflow_m3h
            + self.concentrate_thickener.overflow_m3h
            + self.filtrate_m3h
        )

    @property
    def thickener_overflow_m3h(self) -> float:
        return (
            self.tailings_thickener.overflow_m3h
            + self.concentrate_thickener.overflow_m3h
        )

    @property
    def bleed_m3h(self) -> float:
        return self.thickener_overflow_m3h * db.PROCESS_WATER_BLEED_FRACTION

    @property
    def fresh_makeup_m3h(self) -> float:
        cake_water = (
            self.concentrate_filter.cake_water_tph
            + self.tailings_filter.cake_water_tph
        )
        return cake_water + self.bleed_m3h


@dataclass(frozen=True)
class MechanicalCell:
    """기계식 셀 1기의 기계 사양."""

    tag: str
    duty: str
    geometry: CellGeometry
    cells_in_series: int
    impeller: ImpellerDesign
    aeration: AerationDesign
    shaft: HollowShaftDesign
    pulp_density_kg_m3: float

    @property
    def installed_kw(self) -> float:
        return self.impeller.motor_rating_kw * self.cells_in_series

    @property
    def air_supply_pressure_kpa(self) -> float:
        """중공축 손실을 포함한 이 셀의 소요 급기 압력."""
        return self.aeration.total_pressure_kpa + self.shaft.total_pressure_drop_kpa


@dataclass(frozen=True)
class MechanicalOption:
    """2안 — 기계식 러퍼 뱅크 + 클리너."""

    cells: tuple[MechanicalCell, ...]
    units: tuple[FlotationUnit, ...]
    result_avg: CircuitResult
    result_peak: CircuitResult
    conditioners: tuple[ConditionerDesign, ...]
    blower_flow_m3h: float
    blower_pressure_kpa: float
    blower_rating_kw: float
    tailings_thickener: Thickener
    concentrate_thickener: Thickener
    concentrate_filter: FilterPress
    tailings_filter: FilterPress

    def cell(self, tag: str) -> MechanicalCell:
        for c in self.cells:
            if c.tag == tag:
                return c
        raise KeyError(tag)

    def froth_loading(self, tag: str, result: CircuitResult) -> FrothLoading:
        unit = {
            "FC-201": result.rougher,
            "FC-202": result.scavenger,
            "FC-203": result.cleaner,
        }[tag]
        return froth_loading(self.cell(tag).geometry, unit.concentrate.dry_tph)

    @property
    def installed_kw(self) -> float:
        return (
            sum(c.installed_kw for c in self.cells)
            + self.blower_rating_kw
            + sum(c.agitator_kw for c in self.conditioners)
            + 1.5
            + 0.75
            + 0.2
            + self.concentrate_filter.pump_rating_kw
            + self.tailings_filter.pump_rating_kw
        )

    @property
    def filtrate_m3h(self) -> float:
        """필터프레스 여액 — 러퍼 급광으로 되돌린다."""
        return (
            self.concentrate_filter.filtrate_m3h + self.tailings_filter.filtrate_m3h
        )

    @property
    def filtrate_return_to(self) -> str:
        return db.FILTRATE_RETURN_TO["mechanical"]

    @property
    def water_recycle_m3h(self) -> float:
        """정광·미광 농축조 월류수 + 여액 (블리드 전)."""
        return (
            self.tailings_thickener.overflow_m3h
            + self.concentrate_thickener.overflow_m3h
            + self.filtrate_m3h
        )

    @property
    def thickener_overflow_m3h(self) -> float:
        return (
            self.tailings_thickener.overflow_m3h
            + self.concentrate_thickener.overflow_m3h
        )

    @property
    def bleed_m3h(self) -> float:
        return self.thickener_overflow_m3h * db.PROCESS_WATER_BLEED_FRACTION

    @property
    def fresh_makeup_m3h(self) -> float:
        cake_water = (
            self.concentrate_filter.cake_water_tph
            + self.tailings_filter.cake_water_tph
        )
        return cake_water + self.bleed_m3h


@dataclass(frozen=True)
class Pretreatment:
    """전처리 계통 — 두 안이 공용하는 공통 설비.

    로드밀 배출을 고농도 그대로 어트리션 스크러버에 넣어 표면을 벗기고,
    희석박스에서 부선 농도로 묽혀 조건조로 보낸다.

    희석수는 어차피 부선 농도를 맞추려고 들어가던 물이라 **설비 전체 물수지는
    달라지지 않는다** — 투입 지점이 정해질 뿐이다. 다만 그 물을 공정수 회수로
    감당할 수 있는지는 확인해야 한다 (``dilution_covered_by_recycle``).
    """

    scrubber: AttritionScrubber
    dilution: DilutionBox
    bypass: str

    @property
    def installed_kw(self) -> float:
        return self.scrubber.installed_kw + self.dilution.agitator_kw

    @property
    def dilution_water_m3h(self) -> float:
        return self.dilution.dilution_water_m3h

    def water_supply_ok(self, option: RfcOption | MechanicalOption) -> bool:
        """희석수를 그 안의 회수 공정수와 신수 보충으로 받칠 수 있는지.

        희석수는 계 안을 도는 내부 순환수라, 어트리션이 있든 없든 부선 농도를
        맞추려면 어차피 같은 양이 들어간다. 계 밖으로 나가는 물(케이크 잔류수
        + 블리드)이 달라지지 않으므로 **신수 보충량도 달라지지 않는다**.
        여기서 보는 것은 공정수 계통이 이 유량을 감당하는지뿐이다.
        """
        return (
            option.water_recycle_m3h - option.bleed_m3h + option.fresh_makeup_m3h
            >= self.dilution_water_m3h
        )


@dataclass(frozen=True)
class PlantDesign:
    """두 안과 공용 전처리를 함께 담은 설비 설계."""

    feed: FeedSpec
    pretreatment: Pretreatment
    rfc: RfcOption
    mechanical: MechanicalOption

    def total_installed_kw(self, option: RfcOption | MechanicalOption) -> float:
        """전처리를 포함한 계통 전체 설치 전력."""
        return option.installed_kw + self.pretreatment.installed_kw


# --------------------------------------------------------------------------
# 1안
# --------------------------------------------------------------------------
def build_rfc_option(feed: FeedSpec = db.FEED) -> RfcOption:
    sg = feed.solids_specific_gravity
    design = size_rfc(
        db.RFC_TAG,
        db.RFC_DUTY,
        feed.peak_tph,
        sg,
        feed.solids_mass_fraction,
        bias_flux_cm_s=db.RFC_BIAS_FLUX_CM_S,
        inclined_channel_angle_deg=db.RFC_CHANNEL_ANGLE_DEG,
        inclined_channel_spacing_mm=db.RFC_CHANNEL_SPACING_MM,
    )
    point_peak = design.operating_point(feed.peak_tph)
    point_avg = design.operating_point(feed.average_tph)
    perf_peak = rfc_separation(
        feed.component_tph(feed.peak_tph),
        db.FLOAT_MODELS,
        db.RFC_AG_RECOVERY,
        0.0,  # Ag_locked_gangue 성분으로 결합 맥석을 직접 추적
    )
    perf_avg = rfc_separation(
        feed.component_tph(feed.average_tph),
        db.FLOAT_MODELS,
        db.RFC_AG_RECOVERY,
        0.0,
    )
    conditioners = conditioner_train(db.CONDITIONER_STAGES, point_peak.feed_m3h)
    # 필터를 먼저 정한 뒤, 농축조 월류는 '부선 산물 물 - U/F 물'로 계산한다.
    # 슬러리 체적(고체 체적 포함)을 물로 계상하거나 U/F 물을 중복 회수하지 않는다.
    concentrate_filter = _concentrate_filter(
        "FL-101", perf_peak.concentrate_dry_tph, feed.solids_specific_gravity
    )
    tailings_filter = _tailings_filter(
        "FL-102", perf_peak.tailings_dry_tph, feed.solids_specific_gravity
    )
    concentrate_water = point_peak.overflow_water_m3h
    tail_water = (
        point_peak.water_tph
        + point_peak.wash_water_m3h
        - concentrate_water
    )
    concentrate_overflow = max(
        0.0, concentrate_water - concentrate_filter.feed_water_tph
    )
    tail_overflow = max(0.0, tail_water - tailings_filter.feed_water_tph)
    return RfcOption(
        design=design,
        point_avg=point_avg,
        point_peak=point_peak,
        performance_avg=perf_avg,
        performance_peak=perf_peak,
        conditioners=conditioners,
        tailings_thickener=Thickener(
            "TK-101", "미광 농축 · 공정수 회수", tail_overflow, THICKENER_RISE_RATE_M_H
        ),
        concentrate_thickener=Thickener(
            "TK-102", "정광 농축 · 여과 전단", concentrate_overflow,
            THICKENER_RISE_RATE_M_H,
        ),
        concentrate_filter=concentrate_filter,
        tailings_filter=tailings_filter,
    )


# --------------------------------------------------------------------------
# 2안
# --------------------------------------------------------------------------
def build_mechanical_units() -> tuple[FlotationUnit, FlotationUnit, FlotationUnit]:
    """러퍼 → 스캐빈저 → 클리너 3단.

    스캐빈저 정광과 클리너 미광은 모두 러퍼 급광으로 되돌린다.
    """
    rougher = FlotationUnit(
        tag="FC-201",
        duty="러퍼 (Rougher)",
        water_recovery=db.MECHANICAL_WATER_RECOVERY["FC-201"],
        effective_volume_m3=db.ROUGHER_CELL.effective_slurry_volume_m3,
        rate_scale_factor=db.PLANT_SCALE_FACTOR,
    )
    scavenger = FlotationUnit(
        tag="FC-202",
        duty="스캐빈저 (Scavenger)",
        water_recovery=db.MECHANICAL_WATER_RECOVERY["FC-202"],
        effective_volume_m3=db.SCAVENGER_CELL.effective_slurry_volume_m3,
        rate_scale_factor=db.PLANT_SCALE_FACTOR,
        collector_boost=db.MECHANICAL_SCAVENGER_BOOST,
    )
    cleaner = FlotationUnit(
        tag="FC-203",
        duty="클리너 (Cleaner)",
        water_recovery=db.MECHANICAL_WATER_RECOVERY["FC-203"],
        effective_volume_m3=db.CLEANER_CELL.effective_slurry_volume_m3,
        rate_scale_factor=db.PLANT_SCALE_FACTOR,
        wash_water_m3h=db.CLEANER_WASH_WATER_M3H,
        dilution_target_solids=db.CLEANER_FEED_SOLIDS,
    )
    return rougher, scavenger, cleaner


def solve_mechanical(
    feed: FeedSpec, dry_tph: float, filtrate_return_m3h: float = 0.0
) -> CircuitResult:
    rougher, scavenger, cleaner = build_mechanical_units()
    return solve_circuit(
        feed.component_tph(dry_tph),
        db.FLOAT_MODELS,
        db.SPECIFIC_GRAVITY,
        rougher,
        scavenger,
        cleaner,
        rougher_feed_solids=feed.solids_mass_fraction,
        composite_carry_ratio=0.0,  # Ag_locked_gangue 성분으로 결합 상태 추적
        filtrate_return_m3h=filtrate_return_m3h,
    )


def build_mechanical_option(feed: FeedSpec = db.FEED) -> MechanicalOption:
    # 고체 산물량으로 필터 여액을 먼저 구한 뒤, 해당 여액을 러퍼 수력부하에
    # 포함해 최종 회로를 다시 푼다. 목표 7 wt%는 유지되고 신수만 감소한다.
    preliminary_peak = solve_mechanical(feed, feed.peak_tph)
    concentrate_filter = _concentrate_filter(
        "FL-201", preliminary_peak.concentrate.dry_tph, feed.solids_specific_gravity
    )
    tailings_filter = _tailings_filter(
        "FL-202", preliminary_peak.tailings.dry_tph, feed.solids_specific_gravity
    )
    filtrate_peak = concentrate_filter.filtrate_m3h + tailings_filter.filtrate_m3h
    result_peak = solve_mechanical(feed, feed.peak_tph, filtrate_peak)

    preliminary_avg = solve_mechanical(feed, feed.average_tph)
    avg_concentrate_filter = _concentrate_filter(
        "FL-201", preliminary_avg.concentrate.dry_tph, feed.solids_specific_gravity
    )
    avg_tailings_filter = _tailings_filter(
        "FL-202", preliminary_avg.tailings.dry_tph, feed.solids_specific_gravity
    )
    result_avg = solve_mechanical(
        feed,
        feed.average_tph,
        avg_concentrate_filter.filtrate_m3h + avg_tailings_filter.filtrate_m3h,
    )
    unit_results = {
        "FC-201": result_peak.rougher,
        "FC-202": result_peak.scavenger,
        "FC-203": result_peak.cleaner,
    }
    series = {"FC-201": 1, "FC-202": 1, "FC-203": 1}

    cells: list[MechanicalCell] = []
    for tag, duty, geometry in db.MECHANICAL_CELLS:
        ur = unit_results[tag]
        density = _slurry_density(
            ur.feed.solids_mass_fraction, feed.solids_specific_gravity
        )
        impeller = impeller_design(
            geometry,
            density,
            diameter_ratio=db.IMPELLER_DIAMETER_RATIO,
            tip_speed_m_s=db.MECHANICAL_TIP_SPEED_M_S[tag],
            power_number=db.IMPELLER_POWER_NUMBER,
        )
        jg_min, jg_max = db.MECHANICAL_JG_RANGE_CM_S[tag]
        aer = aeration_design(
            geometry,
            density,
            sparger_clearance_m=impeller.bottom_clearance_m,
            jg_cm_s=db.MECHANICAL_JG_CM_S[tag],
            jg_min_cm_s=jg_min,
            jg_max_cm_s=jg_max,
            bubble_d32_mm=db.BUBBLE_D32_MM,
            sparger_loss_kpa=0.0,  # 별도 스파저 없음 — 중공축 분산구 손실은 아래에서 계산
        )
        shaft = hollow_shaft(
            tag,
            shaft_power_kw=impeller.motor_rating_kw,
            speed_rpm=impeller.speed_rpm,
            air_m3h=aer.air_flow_max_m3h,
            length_m=geometry.shell_height_m + db.SHAFT_LENGTH_MARGIN_M,
            target_air_velocity_m_s=db.SHAFT_AIR_VELOCITY_M_S,
            joint_loss_kpa=db.SHAFT_JOINT_LOSS_KPA,
            discharge_ports=db.SHAFT_DISCHARGE_PORTS,
            impeller_mass_kg=db.IMPELLER_ASSEMBLY_MASS_KG[tag],
        )
        cells.append(
            MechanicalCell(tag, duty, geometry, series[tag], impeller, aer, shaft, density)
        )

    blower_flow = sum(c.aeration.air_flow_max_m3h * c.cells_in_series for c in cells)
    # 중공축 급기이므로 축 보어 마찰과 로터리 조인트 손실을 더해 선정한다.
    blower_pressure = (
        math.ceil(max(c.air_supply_pressure_kpa for c in cells) * 1.3 / 5.0) * 5.0
    )
    blower_shaft = (blower_flow / 3600.0) * (blower_pressure * 1000.0) / 0.55

    tail_water = result_peak.tailings.water_tph
    concentrate_water = result_peak.concentrate.water_tph
    tail_overflow = max(0.0, tail_water - tailings_filter.feed_water_tph)
    concentrate_overflow = max(
        0.0, concentrate_water - concentrate_filter.feed_water_tph
    )
    return MechanicalOption(
        cells=tuple(cells),
        units=build_mechanical_units(),
        result_avg=result_avg,
        result_peak=result_peak,
        conditioners=conditioner_train(
            db.CONDITIONER_STAGES, result_peak.rougher.feed_volume_m3h
        ),
        blower_flow_m3h=blower_flow,
        blower_pressure_kpa=blower_pressure,
        blower_rating_kw=select_motor_kw(blower_shaft, service_factor=1.5),
        tailings_thickener=Thickener(
            "TK-201", "미광 농축 · 공정수 회수", tail_overflow, THICKENER_RISE_RATE_M_H
        ),
        concentrate_thickener=Thickener(
            "TK-202", "정광 농축 · 여과 전단", concentrate_overflow,
            THICKENER_RISE_RATE_M_H,
        ),
        concentrate_filter=concentrate_filter,
        tailings_filter=tailings_filter,
    )


# --------------------------------------------------------------------------
# 공용 전처리
# --------------------------------------------------------------------------
def build_pretreatment(feed: FeedSpec = db.FEED) -> Pretreatment:
    """어트리션 스크러버 + 희석박스 — 두 안이 공용한다."""
    sg = feed.solids_specific_gravity
    scrubber = size_attrition(
        db.ATTRITION_TAG,
        db.ATTRITION_DUTY,
        feed.peak_tph,
        sg,
        solids_mass_fraction=db.ATTRITION_SOLIDS_WT,
        cells=db.ATTRITION_CELLS,
        residence_min=db.ATTRITION_RESIDENCE_MIN,
        depth_to_width=db.ATTRITION_DEPTH_TO_WIDTH,
        freeboard_m=db.ATTRITION_FREEBOARD_M,
        impeller_ratio=db.ATTRITION_IMPELLER_RATIO,
        impellers_per_shaft=db.ATTRITION_IMPELLERS_PER_SHAFT,
        power_number=db.ATTRITION_POWER_NUMBER,
        design_tip_speed_m_s=db.ATTRITION_DESIGN_TIP_SPEED_M_S,
        tip_speed_range_m_s=db.ATTRITION_TIP_SPEED_RANGE_M_S,
        specific_energy_range_kwh_t=db.ATTRITION_SPECIFIC_ENERGY_RANGE_KWH_T,
        specific_power_range_kw_m3=db.ATTRITION_SPECIFIC_POWER_RANGE_KW_M3,
        minimum_solids_volume_fraction=db.ATTRITION_MIN_SOLIDS_VOLUME_FRACTION,
        impeller_mass_coeff_kg_m3=db.ATTRITION_IMPELLER_MASS_COEFF_KG_M3,
        shaft_length_margin_m=db.ATTRITION_SHAFT_LENGTH_MARGIN_M,
        liner=db.ATTRITION_LINER,
        feed_pump_kw=db.ATTRITION_FEED_PUMP_KW,
    )
    return Pretreatment(
        scrubber=scrubber,
        dilution=dilution_box(
            db.DILUTION_BOX_TAG,
            db.DILUTION_BOX_DUTY,
            feed.peak_tph,
            sg,
            inlet_solids_wt=db.ATTRITION_SOLIDS_WT,
            outlet_solids_wt=feed.solids_mass_fraction,
            residence_min=db.DILUTION_BOX_RESIDENCE_MIN,
        ),
        bypass=f"{db.ATTRITION_TAG} 전량 바이패스 → {db.DILUTION_BOX_TAG}",
    )


def build_plant(feed: FeedSpec = db.FEED) -> PlantDesign:
    """공용 전처리와 두 안을 모두 계산한다."""
    return PlantDesign(
        feed=feed,
        pretreatment=build_pretreatment(feed),
        rfc=build_rfc_option(feed),
        mechanical=build_mechanical_option(feed),
    )


def mechanical_sizing_check(result: CircuitResult, tag: str, target_min: float) -> float:
    """확정 기계식 셀이 목표 체류시간에 필요한 유효 체적 (m3)."""
    unit = {
        "FC-201": result.rougher,
        "FC-202": result.scavenger,
        "FC-203": result.cleaner,
    }[tag]
    return required_slurry_volume(unit.feed_volume_m3h, target_min)
