"""회로 전체(러퍼-스캐빈저-클리너)의 설계 계산 조립.

설계 기준(:mod:`flotation_design.design_basis`)으로부터 셀 3기의 형상·구동부·
급기를 산정하고, 순환류를 포함한 물질수지를 평균/최대 처리량에서 각각
수렴시킨다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import design_basis as db
from .circuit import CircuitResult, FlotationUnit, solve_circuit
from .conditioning import ConditionerDesign, conditioner_train
from .feed import FeedSpec, PulpProperties, pulp_at
from .sizing import (
    AerationDesign,
    CellGeometry,
    FrothLoading,
    ImpellerDesign,
    aeration_design,
    froth_loading,
    impeller_design,
    required_slurry_volume,
)

WATER_DENSITY = 1000.0


@dataclass(frozen=True)
class CellDesign:
    """셀 1기의 기계 사양 일습."""

    tag: str
    duty: str
    geometry: CellGeometry
    impeller: ImpellerDesign
    aeration: AerationDesign
    pulp_density_kg_m3: float

    @property
    def installed_kw(self) -> float:
        return self.impeller.motor_rating_kw


@dataclass(frozen=True)
class CircuitDesign:
    """회로 설계 계산 결과 전체."""

    feed: FeedSpec
    pulp_avg: PulpProperties
    pulp_peak: PulpProperties
    cells: tuple[CellDesign, ...]
    units: tuple[FlotationUnit, ...]
    result_avg: CircuitResult
    result_peak: CircuitResult
    conditioners: tuple[ConditionerDesign, ...]
    blower_flow_m3h: float
    blower_pressure_kpa: float
    blower_rating_kw: float

    def cell(self, tag: str) -> CellDesign:
        for c in self.cells:
            if c.tag == tag:
                return c
        raise KeyError(tag)

    def froth_loading(self, tag: str, result: CircuitResult) -> FrothLoading:
        """해당 셀의 정광 배출 부하."""
        unit = {
            "FC-101": result.rougher,
            "FC-102": result.scavenger,
            "FC-103": result.cleaner,
        }[tag]
        return froth_loading(self.cell(tag).geometry, unit.concentrate.dry_tph)


def _slurry_density(solids_mass_fraction: float, solids_sg: float) -> float:
    w = solids_mass_fraction
    return WATER_DENSITY / (w / solids_sg + (1.0 - w))


def build_units(feed: FeedSpec = db.FEED) -> tuple[FlotationUnit, ...]:
    """설계 기준의 확정 셀 형상으로부터 회로 단위 3기를 만든다."""
    rougher = FlotationUnit(
        tag="FC-101",
        duty="러퍼 (Rougher)",
        water_recovery=db.CELL_WATER_RECOVERY["FC-101"],
        effective_volume_m3=db.ROUGHER_CELL.effective_slurry_volume_m3,
    )
    scavenger = FlotationUnit(
        tag="FC-102",
        duty="스캐빈저 (Scavenger)",
        water_recovery=db.CELL_WATER_RECOVERY["FC-102"],
        effective_volume_m3=db.SCAVENGER_CELL.effective_slurry_volume_m3,
        collector_boost=db.SCAVENGER_COLLECTOR_BOOST,
    )
    cleaner = FlotationUnit(
        tag="FC-103",
        duty="클리너 (Cleaner)",
        water_recovery=db.CELL_WATER_RECOVERY["FC-103"],
        effective_volume_m3=db.CLEANER_CELL.effective_slurry_volume_m3,
        wash_water_m3h=db.CLEANER_WASH_WATER_M3H,
        dilution_target_solids=db.CLEANER_FEED_SOLIDS,
    )
    return (rougher, scavenger, cleaner)


def solve_at(feed: FeedSpec, dry_tph: float) -> CircuitResult:
    """지정 처리량에서 회로를 수렴시킨다."""
    rougher, scavenger, cleaner = build_units(feed)
    return solve_circuit(
        feed.component_tph(dry_tph),
        db.FLOAT_MODELS,
        db.SPECIFIC_GRAVITY,
        rougher,
        scavenger,
        cleaner,
        rougher_feed_solids=db.ROUGHER_FEED_SOLIDS,
    )


def build_circuit(feed: FeedSpec = db.FEED) -> CircuitDesign:
    """회로 설계 전체를 계산한다."""
    result_peak = solve_at(feed, feed.peak_tph)
    result_avg = solve_at(feed, feed.average_tph)

    unit_results = {
        "FC-101": result_peak.rougher,
        "FC-102": result_peak.scavenger,
        "FC-103": result_peak.cleaner,
    }

    cells: list[CellDesign] = []
    for tag, duty, geometry in db.CIRCUIT_CELLS:
        ur = unit_results[tag]
        density = _slurry_density(ur.feed.solids_mass_fraction, feed.solids_specific_gravity)
        impeller = impeller_design(
            geometry,
            density,
            diameter_ratio=db.IMPELLER_DIAMETER_RATIO,
            tip_speed_m_s=db.CELL_TIP_SPEED_M_S[tag],
            power_number=db.IMPELLER_POWER_NUMBER,
        )
        jg_min, jg_max = db.CELL_JG_RANGE_CM_S[tag]
        aer = aeration_design(
            geometry,
            density,
            sparger_clearance_m=impeller.bottom_clearance_m,
            jg_cm_s=db.CELL_JG_CM_S[tag],
            jg_min_cm_s=jg_min,
            jg_max_cm_s=jg_max,
            bubble_d32_mm=db.BUBBLE_D32_MM,
        )
        cells.append(CellDesign(tag, duty, geometry, impeller, aer, density))

    # 송풍기는 3기 공용 — 셀별 최대 급기량의 합으로 선정하고 분기마다
    # 유량계와 제어밸브를 둔다. 개별 송풍기 3대보다 싸고 관리가 쉽다.
    blower_flow = sum(c.aeration.air_flow_max_m3h for c in cells)
    blower_pressure = max(c.aeration.selection_pressure_kpa for c in cells)
    from .sizing import select_motor_kw

    blower_shaft = (blower_flow / 3600.0) * (blower_pressure * 1000.0) / 0.55
    blower_rating = select_motor_kw(blower_shaft, service_factor=1.5)

    conditioners = conditioner_train(
        db.CONDITIONER_STAGES, result_peak.rougher.feed_volume_m3h
    )

    return CircuitDesign(
        feed=feed,
        pulp_avg=pulp_at(feed, feed.average_tph),
        pulp_peak=pulp_at(feed, feed.peak_tph),
        cells=tuple(cells),
        units=build_units(feed),
        result_avg=result_avg,
        result_peak=result_peak,
        conditioners=conditioners,
        blower_flow_m3h=blower_flow,
        blower_pressure_kpa=blower_pressure,
        blower_rating_kw=blower_rating,
    )


def sizing_check(result: CircuitResult, tag: str, target_residence_min: float) -> float:
    """확정 셀이 목표 체류시간에 필요한 체적을 충족하는지 확인용 — 필요 체적 (m3)."""
    unit = {"FC-101": result.rougher, "FC-102": result.scavenger, "FC-103": result.cleaner}[tag]
    return required_slurry_volume(unit.feed_volume_m3h, target_residence_min)
