"""설비 전체 조립 — 1안(연속 부선조)과 2안(기계식 러퍼+클리너).

두 안 모두 동일한 급광 사양과 동일한 부선 거동 모델을 쓰므로 직접 비교할
수 있다. 차이는 오직 **장치 형식**에서 온다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import design_basis as db
from .circuit import CircuitResult, FlotationUnit, solve_circuit
from .conditioning import ConditionerDesign, conditioner_train
from .feed import FeedSpec
from .rfc import RfcDesign, RfcOperatingPoint, RfcPerformance, rfc_separation, size_rfc
from .sizing import (
    AerationDesign,
    CellGeometry,
    FrothLoading,
    ImpellerDesign,
    aeration_design,
    froth_loading,
    impeller_design,
    required_slurry_volume,
    select_motor_kw,
)

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

    @property
    def installed_kw(self) -> float:
        # 송풍기 + 급광펌프 + 미광펌프 + 조건조 교반 + 정량펌프
        return (
            self.design.blower_rating_kw
            + 1.5
            + 0.75
            + sum(c.agitator_kw for c in self.conditioners)
            + 0.2
        )

    @property
    def water_recycle_m3h(self) -> float:
        """농축조에서 회수해 재사용하는 물."""
        return self.tailings_thickener.overflow_m3h + self.concentrate_thickener.overflow_m3h


@dataclass(frozen=True)
class MechanicalCell:
    """기계식 셀 1기의 기계 사양."""

    tag: str
    duty: str
    geometry: CellGeometry
    cells_in_series: int
    impeller: ImpellerDesign
    aeration: AerationDesign
    pulp_density_kg_m3: float

    @property
    def installed_kw(self) -> float:
        return self.impeller.motor_rating_kw * self.cells_in_series


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

    def cell(self, tag: str) -> MechanicalCell:
        for c in self.cells:
            if c.tag == tag:
                return c
        raise KeyError(tag)

    def froth_loading(self, tag: str, result: CircuitResult) -> FrothLoading:
        unit = {"FC-201": result.rougher, "FC-202": result.cleaner}[tag]
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
        )


@dataclass(frozen=True)
class PlantDesign:
    """두 안을 함께 담은 설비 설계."""

    feed: FeedSpec
    rfc: RfcOption
    mechanical: MechanicalOption


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
        db.COMPOSITE_CARRY_RATIO,
    )
    perf_avg = rfc_separation(
        feed.component_tph(feed.average_tph),
        db.FLOAT_MODELS,
        db.RFC_AG_RECOVERY,
        db.COMPOSITE_CARRY_RATIO,
    )
    conditioners = conditioner_train(db.CONDITIONER_STAGES, point_peak.feed_m3h)
    tail_water = point_peak.feed_m3h + point_peak.wash_water_m3h - point_peak.overflow_water_m3h
    return RfcOption(
        design=design,
        point_avg=point_avg,
        point_peak=point_peak,
        performance_avg=perf_avg,
        performance_peak=perf_peak,
        conditioners=conditioners,
        tailings_thickener=Thickener(
            "TK-101", "미광 농축 · 공정수 회수", tail_water, THICKENER_RISE_RATE_M_H
        ),
        concentrate_thickener=Thickener(
            "TK-102", "정광 농축 · 여과 전단", point_peak.overflow_water_m3h,
            THICKENER_RISE_RATE_M_H,
        ),
    )


# --------------------------------------------------------------------------
# 2안
# --------------------------------------------------------------------------
def build_mechanical_units() -> tuple[FlotationUnit, FlotationUnit]:
    rougher = FlotationUnit(
        tag="FC-201",
        duty="러퍼 뱅크 (Rougher bank)",
        water_recovery=db.MECHANICAL_WATER_RECOVERY["FC-201"],
        effective_volume_m3=db.ROUGHER_CELL.effective_slurry_volume_m3
        * db.ROUGHER_CELLS_IN_SERIES,
        cells_in_series=db.ROUGHER_CELLS_IN_SERIES,
        rate_scale_factor=db.PLANT_SCALE_FACTOR,
    )
    cleaner = FlotationUnit(
        tag="FC-202",
        duty="클리너 (Cleaner)",
        water_recovery=db.MECHANICAL_WATER_RECOVERY["FC-202"],
        effective_volume_m3=db.CLEANER_CELL.effective_slurry_volume_m3,
        rate_scale_factor=db.PLANT_SCALE_FACTOR,
        wash_water_m3h=db.CLEANER_WASH_WATER_M3H,
        dilution_target_solids=db.CLEANER_FEED_SOLIDS,
    )
    return rougher, cleaner


def solve_mechanical(feed: FeedSpec, dry_tph: float) -> CircuitResult:
    rougher, cleaner = build_mechanical_units()
    return solve_circuit(
        feed.component_tph(dry_tph),
        db.FLOAT_MODELS,
        db.SPECIFIC_GRAVITY,
        rougher,
        None,
        cleaner,
        rougher_feed_solids=feed.solids_mass_fraction,
        composite_carry_ratio=db.COMPOSITE_CARRY_RATIO,
    )


def build_mechanical_option(feed: FeedSpec = db.FEED) -> MechanicalOption:
    result_peak = solve_mechanical(feed, feed.peak_tph)
    result_avg = solve_mechanical(feed, feed.average_tph)
    unit_results = {"FC-201": result_peak.rougher, "FC-202": result_peak.cleaner}
    series = {"FC-201": db.ROUGHER_CELLS_IN_SERIES, "FC-202": 1}

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
        )
        cells.append(MechanicalCell(tag, duty, geometry, series[tag], impeller, aer, density))

    blower_flow = sum(c.aeration.air_flow_max_m3h * c.cells_in_series for c in cells)
    blower_pressure = max(c.aeration.selection_pressure_kpa for c in cells)
    blower_shaft = (blower_flow / 3600.0) * (blower_pressure * 1000.0) / 0.55

    tail_water = result_peak.tailings.water_tph
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
            "TK-201", "미광 농축 · 공정수 회수", tail_water, THICKENER_RISE_RATE_M_H
        ),
    )


def build_plant(feed: FeedSpec = db.FEED) -> PlantDesign:
    """두 안을 모두 계산한다."""
    return PlantDesign(
        feed=feed,
        rfc=build_rfc_option(feed),
        mechanical=build_mechanical_option(feed),
    )


def mechanical_sizing_check(result: CircuitResult, tag: str, target_min: float) -> float:
    """확정 기계식 셀이 목표 체류시간에 필요한 유효 체적 (m3)."""
    unit = {"FC-201": result.rougher, "FC-202": result.cleaner}[tag]
    return required_slurry_volume(unit.feed_volume_m3h, target_min)
