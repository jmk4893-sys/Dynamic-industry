"""설비 전체 조립 — 1안(연속 부선조)과 2안(기계식 3단).

두 안 모두 동일한 급광 사양과 동일한 부선 거동 모델을 쓰므로 직접 비교할
수 있다. 차이는 오직 **장치 형식**에서 온다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import design_basis as db
from .attrition import AttritionScrubber, DilutionBox, dilution_box, size_attrition
from .attrition_pilot import (
    MechanismScreen,
    PilotCell,
    PilotScaleUp,
    pilot_scale_up,
    size_pilot_cell,
    tolerable_aluminium_reaction_kg_h,
)
from .circuit import CircuitResult, FlotationUnit, solve_circuit
from .conditioning import ConditionerDesign, conditioner_train
from .eva_separation import (
    DewateringBag,
    EvaBatchLimits,
    EvaDesignParticle,
    EvaFilmCase,
    EvaGradeBudget,
    EvaMethodScreen,
    EvaRequirement,
    batch_t90_limit,
    eva_cake_water_tph,
    eva_design_particle,
    eva_rate_constant_1_min,
)
from .feed import FeedSpec
from .hydrodynamics import analyse_cell
from .kinetics import ComponentKinetics
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
        """필터프레스 여액 합계 — 정광 여액은 CT-1, 미광 여액은 공정수 탱크로."""
        return (
            self.concentrate_filter.filtrate_m3h + self.tailings_filter.filtrate_m3h
        )

    @property
    def filtrate_return_to(self) -> str:
        """정광 여액이 가는 곳 — 부선 회로의 첫 단."""
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
    def cake_water_m3h(self) -> float:
        """정광 · 미광 케이크에 남아 계 밖으로 나가는 물."""
        return (
            self.concentrate_filter.cake_water_tph
            + self.tailings_filter.cake_water_tph
        )


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
        """필터프레스 여액 합계 — 정광 여액은 러퍼 급광, 미광 여액은 공정수 탱크로."""
        return (
            self.concentrate_filter.filtrate_m3h + self.tailings_filter.filtrate_m3h
        )

    @property
    def filtrate_return_to(self) -> str:
        """정광 여액이 가는 곳 — 부선 회로의 첫 단."""
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
    def cake_water_m3h(self) -> float:
        """정광 · 미광 케이크에 남아 계 밖으로 나가는 물."""
        return (
            self.concentrate_filter.cake_water_tph
            + self.tailings_filter.cake_water_tph
        )


#: 떨어진 EVA 를 회로 계산에서 부르는 성분명.
EVA = "EVA"


@dataclass(frozen=True)
class EvaSeparation:
    """떨어진 EVA 분리 — 기포제만 쓰는 EVA 러퍼 + 클리너 (공통 설비).

    AS-1 이 떼어 낸 EVA 를 부선 급광에서 걷어낸다. 셀은 2안 동체를 그대로
    쓴다 (ES-1 = FC-202, ES-2 = FC-203). 클리너 미광은 ES-1 급광으로 되돌린다
    — 러퍼 거품에 동반된 광물이 부선조로 돌아가는 길이다. 상세 근거는
    ``eva_separation.py`` 모듈 도크스트링 참조.

    Attributes:
        rate_constant_1_min: 설계 박편의 실기 속도상수 (ES-1 급기 기준).
        size_recovery: (EVA 등체적 지름 µm, 회로 회수율) — 최대 처리량.
        budget: 1안 정광 품위 여유 — AS-1 박리 목표와 이 계통의 한도가 나눠 쓴다.
        collector_sensitivity: (정상 부선 대비 은이 뜨는 속도 비, EVA 산물로 새는
            Ag) — 포수제가 ES 로 들어올 때 (최대 처리량).
        tolerable_collector_activity: EVA 산물 Ag 가 한도에 닿는 속도 비.
    """

    particle: EvaDesignParticle
    screen: EvaMethodScreen
    budget: EvaGradeBudget
    requirement: EvaRequirement
    attachment_efficiency: float
    rate_constant_1_min: float
    rougher: MechanicalCell
    cleaner: MechanicalCell
    blower_flow_m3h: float
    blower_pressure_kpa: float
    blower_rating_kw: float
    pump_kw: float
    pump_flow_m3h: float
    bag: DewateringBag
    result_peak: CircuitResult
    result_avg: CircuitResult
    size_recovery: tuple[tuple[float, float], ...]
    film_cases: tuple[EvaFilmCase, ...]
    limits: EvaBatchLimits
    collector_sensitivity: tuple[tuple[float, float], ...]
    tolerable_collector_activity: float
    bypass: str

    @property
    def removal_target(self) -> float:
        """AS-1 박리 목표 — 이 몫이 떨어져 ES 로 온다."""
        return self.budget.removal_target

    def freed_eva_tph(self, dry_tph: float) -> float:
        """AS-1 이 목표대로 뗀 EVA — ES 급광."""
        return self.particle.content * dry_tph * self.removal_target

    @property
    def bypass_grade(self) -> float:
        """ES 를 바이패스할 때 1안 정광 품위 — 떨어진 EVA 와 남은 부착 EVA 가 모두 뜨면."""
        freed = self.freed_eva_tph(self.budget.dry_tph)
        return self.budget.grade_with(freed, self.budget.eva_tph - freed)

    @property
    def installed_kw(self) -> float:
        return (
            self.rougher.installed_kw
            + self.cleaner.installed_kw
            + self.blower_rating_kw
            + self.pump_kw
        )

    @property
    def design_air_m3h(self) -> float:
        """설계 Jg 에서 세 셀로 들어가는 공기 — 거품 위 수소를 쓸어내는 양이기도 하다."""
        return (
            self.rougher.aeration.air_flow_m3h * self.rougher.cells_in_series
            + self.cleaner.aeration.air_flow_m3h
        )

    @property
    def tolerable_al_reaction_kg_h(self) -> float:
        """ES 셀은 덮개가 없다 — 부선 공기가 거품 위 수소를 설계 상한 아래로
        희석할 수 있는 Al 반응 속도."""
        return tolerable_aluminium_reaction_kg_h(
            self.design_air_m3h, db.H2_LEL_VOL, db.H2_DESIGN_LEL_FRACTION
        )

    @staticmethod
    def eva_recovery(result: CircuitResult) -> float:
        return result.recovery(EVA)

    @staticmethod
    def residual_eva_tph(result: CircuitResult) -> float:
        """부선 급광(CT-1)으로 넘어가는 자유 EVA."""
        return result.tailings.component_tph(EVA)

    @staticmethod
    def product_minerals_tph(result: CircuitResult) -> float:
        """EVA 산물에 섞여 나가는 광물 (동반 혼입)."""
        return result.concentrate.dry_tph - result.concentrate.component_tph(EVA)

    @staticmethod
    def ag_loss(result: CircuitResult) -> float:
        """EVA 산물로 새는 Ag / 급광 Ag."""
        return result.recovery("Ag")

    @property
    def meets_requirement(self) -> bool:
        return self.eva_recovery(self.result_peak) >= self.requirement.required_recovery

    @property
    def ag_loss_ok(self) -> bool:
        return self.ag_loss(self.result_peak) <= db.EVA_AG_LOSS_LIMIT


@dataclass(frozen=True)
class Pretreatment:
    """전처리 계통 — 두 안이 공용하는 공통 설비.

    로드밀 배출을 고농도 그대로 어트리션 스크러버에 넣어 EVA 를 떼고,
    희석박스에서 ES 급광 농도로 묽힌 뒤, 떨어진 EVA 를 ES 에서 걷어내고
    조건조로 보낸다.

    희석수는 **청수(포수제 없는 물)** 로 넣는다. 회수 공정수에는 포수제가 남아 있어
    ES 로 들어오면 은이 EVA 산물로 뜬다. 그 대가로 ES 앞에 넣은 청수는 부선 뒤
    공정수로 나와 블리드가 된다 — 물수지는 ``PlantDesign.water_balance`` 에서 닫는다.
    """

    scrubber: AttritionScrubber
    dilution: DilutionBox
    bypass: str
    eva: EvaSeparation

    @property
    def attrition_kw(self) -> float:
        """EVA 를 떼는 몫 — 어트리션 + 희석박스 교반."""
        return self.scrubber.installed_kw + self.dilution.agitator_kw

    @property
    def installed_kw(self) -> float:
        return self.attrition_kw + self.eva.installed_kw

    @property
    def dilution_water_m3h(self) -> float:
        """DB-1 희석수 설계 유량 — 출구 7 wt%, 순환류 공제 없음 (밸브·배관 기준)."""
        return self.dilution.dilution_water_m3h


#: 물수지 경우 — W1 기준(ES 앞 청수), W3 ES 20 wt%(청수 절감), W4 GAC(공정수 재사용).
WATER_CASES = ("W1", "W3", "W4")
WATER_CASE_LABELS = {
    "W1": "W1 기준 — ES 앞 청수",
    "W3": f"W3 ES {db.EVA_ALTERNATIVE_SOLIDS_WT * 100:.0f} wt%",
    "W4": "W4 GAC — 공정수에서 포수제를 빼 ES 앞에",
}


@dataclass(frozen=True)
class WaterBalance:
    """계통 물수지 한 경우 (m3/h) — 청수와 회수 공정수를 가른다.

    ES 앞(DB-1 희석 · ES-2 세척수)에는 청수, CT-1 부터는 공정수를 쓴다. ES 앞에 넣은
    청수는 부선 뒤 공정수로 나오지만 ES 앞으로 되돌릴 수 없으므로, 케이크에 남는
    몫을 뺀 전량이 블리드가 된다 (``gac`` 로 포수제를 뺀 공정수를 ES 앞에 쓸 때만
    예외). 물수지는 ``feed_water + fresh = cake_water + bleed`` 로 닫힌다.

    Attributes:
        option: "1안" 또는 "2안".
        case: ``WATER_CASES`` 중 하나.
        feed_water: 로드밀 배출(70 wt%)과 함께 들어오는 물 — 상류가 청수로 댄다.
        es_feed_solids: DB-1 설정 — ES-1 급광(순환류 포함) 고체 농도.
        es_clean: ES 계통이 쓰는 청수 (DB-1 희석 + ES-2 세척수, FB-1 여액 반송 공제).
        es_wash: 그중 ES-2 세척수.
        es_tails_water: ES 미광에 실려 CT-1 로 가는 물.
        eva_cake_water: EVA 케이크(FB-1)에 남아 나가는 물.
        concentrate_filtrate: 정광 여액 — 첫 단 급광으로 직송.
        ct1_makeup: CT-1 보충수 (공정수) — 부선 급광을 설계 유량·농도로 맞춘다.
        process_users: 보충수 밖의 공정수 사용처 (1안 세척수, 2안 클리너 세척·희석수).
        process_supply: 공정수 탱크로 오는 물 (농축조 월류 + 미광 여액).
        overflow: 농축조 월류 — 최소 블리드의 기준.
        filter_cake_water: 정광 · 미광 케이크에 남아 나가는 물.
        gac: 공정수 중 GAC 로 포수제를 빼 ES 앞에 쓰는 몫 (W4).
        es_ag_loss: 이 경우 EVA 산물로 새는 Ag / 급광 Ag.
    """

    option: str
    case: str
    dry_tph: float
    feed_water: float
    es_feed_solids: float
    es_clean: float
    es_wash: float
    es_tails_water: float
    eva_cake_water: float
    concentrate_filtrate: float
    ct1_makeup: float
    process_users: float
    process_supply: float
    overflow: float
    filter_cake_water: float
    es_ag_loss: float
    gac: float = 0.0

    @property
    def label(self) -> str:
        return WATER_CASE_LABELS[self.case]

    @property
    def db1_dilution(self) -> float:
        """운전 중 DB-1 희석수 — ES-2 미광과 FB-1 여액이 일부를 대신한다."""
        return self.es_clean - self.es_wash

    @property
    def minimum_bleed(self) -> float:
        return self.overflow * db.PROCESS_WATER_BLEED_FRACTION

    @property
    def process_surplus(self) -> float:
        """공정수 탱크에 남는 물 — 사용처와 GAC 로 보낸 뒤."""
        return self.process_supply - self.ct1_makeup - self.process_users - self.gac

    @property
    def bleed(self) -> float:
        return max(self.minimum_bleed, self.process_surplus)

    @property
    def fresh_to_process(self) -> float:
        """최소 블리드를 지키려고 공정수 탱크에 넣는 신수."""
        return self.bleed - self.process_surplus

    @property
    def fresh_clean(self) -> float:
        """ES 앞에 넣는 신수 (청수)."""
        return self.es_clean - self.gac

    @property
    def fresh(self) -> float:
        return self.fresh_clean + self.fresh_to_process

    @property
    def cake_water(self) -> float:
        return self.filter_cake_water + self.eva_cake_water

    @property
    def closure_error(self) -> float:
        """들어온 물(로드밀 + 신수) − 나간 물(케이크 + 블리드)."""
        return self.feed_water + self.fresh - self.cake_water - self.bleed

    @property
    def gac_bed_m3(self) -> float:
        """활성탄 층 체적 — 공탑 접촉시간 기준."""
        return self.gac * db.GAC_EBCT_MIN / 60.0


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

    def concentrate(self, option: str, dry_tph: float | None = None) -> tuple[float, float]:
        """(정광 t/h, Ag 품위) — EVA 없음."""
        peak = dry_tph is None or math.isclose(dry_tph, self.feed.peak_tph)
        if option == "1안":
            perf = self.rfc.performance_peak if peak else self.rfc.performance_avg
            return perf.concentrate_dry_tph, perf.concentrate_grade("Ag")
        res = self.mechanical.result_peak if peak else self.mechanical.result_avg
        return res.concentrate.dry_tph, res.concentrate.grade_fraction("Ag")

    def option_ag_recovery(self, option: str, dry_tph: float | None = None) -> float:
        peak = dry_tph is None or math.isclose(dry_tph, self.feed.peak_tph)
        if option == "1안":
            perf = self.rfc.performance_peak if peak else self.rfc.performance_avg
            return perf.recovery("Ag")
        res = self.mechanical.result_peak if peak else self.mechanical.result_avg
        return res.recovery("Ag")

    def overall_ag_recovery(self, option: str, dry_tph: float | None = None) -> float:
        """전처리를 포함한 계통 Ag 회수율 — ES 에서 EVA 산물로 새는 몫을 뺀다."""
        es = self.pretreatment.eva
        peak = dry_tph is None or math.isclose(dry_tph, self.feed.peak_tph)
        loss = es.ag_loss(es.result_peak if peak else es.result_avg)
        return (1.0 - loss) * self.option_ag_recovery(option, dry_tph)

    def eva_budget(self, option: str) -> EvaGradeBudget:
        """최대 처리량 정광 품위 여유 — 1안이 AS-1 박리 목표를 정한다."""
        if option == "1안":
            return self.pretreatment.eva.budget
        c_tph, grade = self.concentrate(option)
        return _grade_budget(self.feed, c_tph, grade, self.pretreatment.eva.particle.content)

    def water_balance(
        self, option: str, dry_tph: float | None = None, case: str = "W1"
    ) -> WaterBalance:
        """최대(기본) · 평균 처리량의 계통 물수지."""
        return _water_balance(self, option, dry_tph, case)


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
    # 고체 산물량으로 필터 여액을 먼저 구한 뒤, 정광 여액을 러퍼 수력부하에
    # 포함해 최종 회로를 다시 푼다 (미광 여액은 공정수 탱크로). 목표 7 wt%는
    # 유지되고 ES 미광 · CT-1 보충수로 받을 몫만 준다.
    preliminary_peak = solve_mechanical(feed, feed.peak_tph)
    concentrate_filter = _concentrate_filter(
        "FL-201", preliminary_peak.concentrate.dry_tph, feed.solids_specific_gravity
    )
    tailings_filter = _tailings_filter(
        "FL-202", preliminary_peak.tailings.dry_tph, feed.solids_specific_gravity
    )
    result_peak = solve_mechanical(feed, feed.peak_tph, concentrate_filter.filtrate_m3h)

    preliminary_avg = solve_mechanical(feed, feed.average_tph)
    avg_concentrate_filter = _concentrate_filter(
        "FL-201", preliminary_avg.concentrate.dry_tph, feed.solids_specific_gravity
    )
    result_avg = solve_mechanical(
        feed, feed.average_tph, avg_concentrate_filter.filtrate_m3h
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
        eva=build_eva_separation(feed),
    )


# --------------------------------------------------------------------------
# 떨어진 EVA 분리 — ES-1 러퍼 + ES-2 클리너 (공통 설비)
# --------------------------------------------------------------------------
def _eva_flotation_cell(
    tag: str,
    duty: str,
    geometry: CellGeometry,
    cells_in_series: int,
    density: float,
) -> MechanicalCell:
    """2안과 같은 방식(로터 + 중공축 급기)으로 ES 셀의 기계 사양을 낸다."""
    impeller = impeller_design(
        geometry,
        density,
        diameter_ratio=db.IMPELLER_DIAMETER_RATIO,
        tip_speed_m_s=db.EVA_TIP_SPEED_M_S[tag],
        power_number=db.IMPELLER_POWER_NUMBER,
    )
    jg_min, jg_max = db.EVA_JG_RANGE_CM_S[tag]
    aeration = aeration_design(
        geometry,
        density,
        sparger_clearance_m=impeller.bottom_clearance_m,
        jg_cm_s=db.EVA_JG_CM_S[tag],
        jg_min_cm_s=jg_min,
        jg_max_cm_s=jg_max,
        bubble_d32_mm=db.BUBBLE_D32_MM,
        sparger_loss_kpa=0.0,
    )
    shaft = hollow_shaft(
        tag,
        shaft_power_kw=impeller.motor_rating_kw,
        speed_rpm=impeller.speed_rpm,
        air_m3h=aeration.air_flow_max_m3h,
        length_m=geometry.shell_height_m + db.SHAFT_LENGTH_MARGIN_M,
        target_air_velocity_m_s=db.SHAFT_AIR_VELOCITY_M_S,
        joint_loss_kpa=db.SHAFT_JOINT_LOSS_KPA,
        discharge_ports=db.SHAFT_DISCHARGE_PORTS,
        impeller_mass_kg=db.EVA_IMPELLER_MASS_KG[tag],
    )
    return MechanicalCell(
        tag, duty, geometry, cells_in_series, impeller, aeration, shaft, density
    )


def solve_eva_circuit(
    feed: FeedSpec,
    dry_tph: float,
    eva_tph: float,
    rate_constant_1_min: float,
    rougher_cells: int = db.EVA_ROUGHER_CELLS,
    feed_solids: float | None = None,
    collector_activity: float = 0.0,
    rougher_water_recovery: float | None = None,
) -> CircuitResult:
    """ES-1(러퍼 n 셀) + ES-2(클리너, 미광은 러퍼 급광으로) 물질수지.

    포수제가 없으므로 광물은 진부선 없이 수분 동반으로만 거품에 간다. EVA 는
    한 가지 속도상수로 뜬다. 클리너 급기가 러퍼와 다른 만큼 속도상수를 Jg 비로
    줄인다 (k 는 Jg 에 비례).

    Args:
        feed_solids: ES-1 급광(순환류 포함) 고체 농도 — DB-1 설정. 기본은 부선 설계 농도.
        collector_activity: 포수제가 ES 로 들어올 때 — 광물이 정상 부선(실기 환산)
            속도의 이 비율로 뜬다. 0 이면 수분 동반뿐이다.
        rougher_water_recovery: ES-1 수분회수율 재정의. 농도를 올려도 거품 물(m3/h)은
            급기·거품층이 정하므로, 급광 물이 준 만큼 비율이 커진다 (W3).
    """
    if collector_activity < 0.0:
        raise ValueError("collector_activity 는 0 이상")
    if collector_activity == 0.0:
        kinetics = {
            c.name: ComponentKinetics(
                c.name, entrainment_factor=db.FLOAT_MODELS[c.name].entrainment_factor
            )
            for c in feed.components
        }
    else:
        scale = collector_activity * db.PLANT_SCALE_FACTOR
        kinetics = {}
        for c in feed.components:
            m = db.FLOAT_MODELS[c.name]
            kinetics[c.name] = ComponentKinetics(
                c.name,
                fast_fraction=m.fast_fraction,
                k_fast=m.k_fast * scale,
                slow_fraction=m.slow_fraction,
                k_slow=m.k_slow * scale,
                entrainment_factor=m.entrainment_factor,
            )
    kinetics[EVA] = ComponentKinetics(
        EVA,
        fast_fraction=1.0,
        k_fast=rate_constant_1_min,
        entrainment_factor=db.EVA_ENTRAINMENT_FACTOR,
    )
    specific_gravity = {c.name: c.specific_gravity for c in feed.components}
    specific_gravity[EVA] = db.EVA_SG
    component_tph = feed.component_tph(dry_tph)
    component_tph[EVA] = eva_tph
    rougher = FlotationUnit(
        db.EVA_ROUGHER_TAG,
        db.EVA_ROUGHER_DUTY,
        db.EVA_WATER_RECOVERY[db.EVA_ROUGHER_TAG]
        if rougher_water_recovery is None
        else rougher_water_recovery,
        effective_volume_m3=db.EVA_ROUGHER_CELL.effective_slurry_volume_m3 * rougher_cells,
        cells_in_series=rougher_cells,
    )
    cleaner = FlotationUnit(
        db.EVA_CLEANER_TAG,
        db.EVA_CLEANER_DUTY,
        db.EVA_WATER_RECOVERY[db.EVA_CLEANER_TAG],
        effective_volume_m3=db.EVA_CLEANER_CELL.effective_slurry_volume_m3,
        wash_water_m3h=db.EVA_CLEANER_WASH_WATER_M3H,
        rate_scale_factor=db.EVA_JG_CM_S[db.EVA_CLEANER_TAG]
        / db.EVA_JG_CM_S[db.EVA_ROUGHER_TAG],
    )
    return solve_circuit(
        component_tph,
        kinetics,
        specific_gravity,
        rougher,
        None,
        cleaner,
        rougher_feed_solids=feed.solids_mass_fraction if feed_solids is None else feed_solids,
    )


def solve_eva_for_tails_water(
    feed: FeedSpec,
    dry_tph: float,
    eva_tph: float,
    rate_constant_1_min: float,
    tails_water_tph: float,
    min_solids: float | None = None,
) -> CircuitResult:
    """ES 미광 물이 주어진 값이 되는 DB-1 설정(ES 급광 농도)을 찾는다.

    하류가 받을 수 있는 물보다 ES 가 더 내보내면 뺄 방법이 없다 — 그때는 DB-1 이
    덜 묽힌다. ES 미광 물은 급광 농도가 오를수록 줄어드는 단조 함수라 이분법으로 푼다.
    """
    lo = feed.solids_mass_fraction if min_solids is None else min_solids
    hi = 0.5

    def tails(w: float) -> CircuitResult:
        return solve_eva_circuit(feed, dry_tph, eva_tph, rate_constant_1_min, feed_solids=w)

    if tails(lo).tailings.water_tph <= tails_water_tph:
        return tails(lo)
    if tails(hi).tailings.water_tph > tails_water_tph:
        raise ValueError("ES 급광 농도를 올려도 하류가 받을 물보다 많다")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if tails(mid).tailings.water_tph > tails_water_tph:
            lo = mid
        else:
            hi = mid
    return tails(hi)


def eva_attachment_efficiency() -> float:
    """Ag 러퍼(FC-201)의 설계 속도상수를 재현하는 부착 효율 — ES 에 그대로 쓴다."""
    return analyse_cell(
        "FC-201",
        db.MECHANICAL_JG_CM_S["FC-201"],
        db.BUBBLE_D32_MM,
        db.GAS_HOLDUP,
        db.ROUGHER_CELL.pulp_zone_height_m,
        db.FLOAT_MODELS["Ag"].k_fast * db.PLANT_SCALE_FACTOR,
    ).implied_attachment_efficiency


def design_eva_particle(
    feed: FeedSpec = db.FEED, film_um: float = db.EVA_RESIDUAL_FILM_UM
) -> EvaDesignParticle:
    """잔막 두께 하나로 정한 설계 EVA — 함량과 박편 크기."""
    wafer_fraction = sum(
        c.mass_fraction for c in feed.components if c.name in ("Si", "Ag_locked_gangue")
    )
    wafer_sg = next(c.specific_gravity for c in feed.components if c.name == "Si")
    return eva_design_particle(
        film_um,
        db.EVA_FLAKE_WIDTH_UM,
        db.CELL_WAFER_THICKNESS_UM,
        wafer_fraction,
        db.EVA_SG,
        wafer_sg,
    )


def _grade_budget(
    feed: FeedSpec, concentrate_tph: float, grade: float, eva_content: float
) -> EvaGradeBudget:
    return EvaGradeBudget(
        dry_tph=feed.peak_tph,
        concentrate_tph=concentrate_tph,
        grade=grade,
        guarantee=db.CONCENTRATE_GRADE_GUARANTEE,
        free_limit=db.EVA_FLOTATION_FEED_LIMIT,
        eva_content=eva_content,
    )


def attrition_budget(feed: FeedSpec = db.FEED) -> EvaGradeBudget:
    """1안(주설계) 최대 처리량 정광 품위 여유 — AS-1 박리 목표의 출처.

    자유 EVA 한도를 뺀 나머지가 스크럽 뒤 부착 EVA 잔류 한도이고, 설계 EVA
    함량으로 나눈 몫이 박리 목표다 (``db.ATTRITION_TARGET_OPTION``).
    """
    perf = rfc_separation(
        feed.component_tph(feed.peak_tph), db.FLOAT_MODELS, db.RFC_AG_RECOVERY, 0.0
    )
    return _grade_budget(
        feed,
        perf.concentrate_dry_tph,
        perf.concentrate_grade("Ag"),
        design_eva_particle(feed).content,
    )


def build_eva_separation(feed: FeedSpec = db.FEED) -> EvaSeparation:
    """ES-1 · ES-2 · B-001 · P-001 · FB-1 — 떨어진 EVA 를 걷어내는 계통."""
    rougher_tag, cleaner_tag = db.EVA_ROUGHER_TAG, db.EVA_CLEANER_TAG

    def particle_for(film_um: float) -> EvaDesignParticle:
        return design_eva_particle(feed, film_um)

    ea = eva_attachment_efficiency()
    jg = db.EVA_JG_CM_S[rougher_tag]
    budget = attrition_budget(feed)
    target = budget.removal_target

    def rate(diameter_um: float) -> float:
        return eva_rate_constant_1_min(diameter_um, jg, ea, db.BUBBLE_D32_MM)

    def freed(particle: EvaDesignParticle, dry_tph: float) -> float:
        # AS-1 이 목표(정광 품위 여유에서 나온 값)대로 뗀 몫이 ES 로 온다.
        return particle.content * dry_tph * target

    particle = particle_for(db.EVA_RESIDUAL_FILM_UM)
    k_design = rate(particle.equivalent_diameter_um)
    eva_peak = freed(particle, feed.peak_tph)
    result_peak = solve_eva_circuit(feed, feed.peak_tph, eva_peak, k_design)
    result_avg = solve_eva_circuit(
        feed, feed.average_tph, freed(particle, feed.average_tph), k_design
    )
    requirement = EvaRequirement(feed.peak_tph, db.EVA_FLOTATION_FEED_LIMIT, eva_peak)

    solids_sg = feed.solids_specific_gravity
    rougher = _eva_flotation_cell(
        rougher_tag,
        db.EVA_ROUGHER_DUTY,
        db.EVA_ROUGHER_CELL,
        db.EVA_ROUGHER_CELLS,
        _slurry_density(result_peak.rougher.feed.solids_mass_fraction, solids_sg),
    )
    cleaner = _eva_flotation_cell(
        cleaner_tag,
        db.EVA_CLEANER_DUTY,
        db.EVA_CLEANER_CELL,
        1,
        _slurry_density(result_peak.cleaner.feed.solids_mass_fraction, solids_sg),
    )
    cells = (rougher, cleaner)
    blower_flow = sum(c.aeration.air_flow_max_m3h * c.cells_in_series for c in cells)
    blower_pressure = (
        math.ceil(max(c.air_supply_pressure_kpa for c in cells) * 1.3 / 5.0) * 5.0
    )
    blower_shaft = (blower_flow / 3600.0) * (blower_pressure * 1000.0) / 0.55

    size_recovery = tuple(
        (d, EvaSeparation.eva_recovery(
            solve_eva_circuit(feed, feed.peak_tph, eva_peak, rate(d))
        ))
        for d in db.EVA_SIZE_TABLE_UM
    )
    film_cases = []
    for film in db.EVA_FILM_CASES_UM:
        p = particle_for(film)
        f_eva = freed(p, feed.peak_tph)
        r = solve_eva_circuit(feed, feed.peak_tph, f_eva, rate(p.equivalent_diameter_um))
        film_cases.append(EvaFilmCase(
            film_um=film,
            content=p.content,
            diameter_um=p.equivalent_diameter_um,
            freed_eva_tph=f_eva,
            required_recovery=EvaRequirement(
                feed.peak_tph, db.EVA_FLOTATION_FEED_LIMIT, f_eva
            ).required_recovery,
            recovery=EvaSeparation.eva_recovery(r),
        ))

    required = requirement.required_recovery

    def limit(dry_tph: float, cells_: int) -> float:
        if required <= 0.0:
            return math.inf  # 떨어진 EVA 가 한도보다 적다 — 걷어낼 필요가 없다
        return batch_t90_limit(
            lambda k_batch: EvaSeparation.eva_recovery(solve_eva_circuit(
                feed, dry_tph, freed(particle, dry_tph),
                k_batch * db.PLANT_SCALE_FACTOR, cells_,
            )),
            required,
        )

    limits = EvaBatchLimits(
        required_recovery=required,
        peak_min=limit(feed.peak_tph, db.EVA_ROUGHER_CELLS),
        average_min=limit(feed.average_tph, db.EVA_ROUGHER_CELLS),
        extra_cell_min=limit(feed.peak_tph, db.EVA_ROUGHER_CELLS + 1),
    )

    def ag_loss_at(activity: float) -> float:
        return EvaSeparation.ag_loss(solve_eva_circuit(
            feed, feed.peak_tph, eva_peak, k_design, collector_activity=activity
        ))

    collector_sensitivity = tuple(
        (a, EvaSeparation.ag_loss(result_peak) if a == 0.0 else ag_loss_at(a))
        for a in db.EVA_COLLECTOR_ACTIVITY_CASES
    )
    lo, hi = 0.0, max(db.EVA_COLLECTOR_ACTIVITY_CASES)
    if ag_loss_at(hi) <= db.EVA_AG_LOSS_LIMIT:
        tolerable = hi
    else:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if ag_loss_at(mid) > db.EVA_AG_LOSS_LIMIT:
                hi = mid
            else:
                lo = mid
        tolerable = lo

    bag = DewateringBag(
        tag=db.EVA_BAG_TAG,
        volume_m3=db.EVA_BAG_VOLUME_M3,
        fill=db.EVA_BAG_FILL,
        units=db.EVA_BAG_UNITS,
        cake_solids_volume_fraction=db.EVA_CAKE_SOLIDS_VOLUME_FRACTION,
        eva_sg=db.EVA_SG,
        # 백은 떨어진 EVA 가 전부일 때(AS-1 이 전량을 뗐을 때)로 잡는다.
        eva_tph=particle.content * feed.peak_tph * EvaSeparation.eva_recovery(result_peak),
        minerals_tph=EvaSeparation.product_minerals_tph(result_peak),
    )
    return EvaSeparation(
        particle=particle,
        budget=budget,
        screen=EvaMethodScreen(
            flow_m3h=result_peak.rougher.feed_volume_m3h,
            eva_diameter_um=particle.equivalent_diameter_um,
            eva_sg=db.EVA_SG,
            bubble_d32_mm=db.BUBBLE_D32_MM,
        ),
        requirement=requirement,
        attachment_efficiency=ea,
        rate_constant_1_min=k_design,
        rougher=rougher,
        cleaner=cleaner,
        blower_flow_m3h=blower_flow,
        blower_pressure_kpa=blower_pressure,
        blower_rating_kw=select_motor_kw(blower_shaft, service_factor=1.5),
        pump_kw=db.EVA_PUMP_KW,
        # ES-2 미광 + FB-1 여액(EVA 산물의 물 중 케이크에 남지 않는 몫).
        pump_flow_m3h=(
            result_peak.recycle.water_tph
            + result_peak.recycle.dry_tph / solids_sg
            + result_peak.concentrate.water_tph - bag.cake_water_tph
        ),
        bag=bag,
        result_peak=result_peak,
        result_avg=result_avg,
        size_recovery=size_recovery,
        film_cases=tuple(film_cases),
        limits=limits,
        collector_sensitivity=collector_sensitivity,
        tolerable_collector_activity=tolerable,
        bypass=f"{rougher_tag} 바이패스 ({db.DILUTION_BOX_TAG} → CT-1) — 수동, 정광 격리",
    )


# --------------------------------------------------------------------------
# 계통 물수지 — 청수(ES 앞)와 회수 공정수(CT-1 부터)
# --------------------------------------------------------------------------
def _water_balance(
    design: PlantDesign, option: str, dry_tph: float | None, case: str
) -> WaterBalance:
    """한 안 · 한 처리량 · 한 경우의 물수지.

    1. 하류(부선 급광)가 받아야 할 물을 정한다 — 1안은 flux 고정 급광, 2안은
       러퍼 7 wt%(순환류 포함). 정광 여액은 여기에 직송한다.
    2. ES 는 설계 농도(W3 는 대안 농도)에서 돈다. ES 미광 물이 하류 몫보다 많으면
       뺄 방법이 없으므로 DB-1 이 덜 묽힌다 (ES 급광 농도를 올린다).
    3. 모자라는 몫은 CT-1 보충수(공정수)로 채운다.
    4. 공정수 탱크 = 농축조 월류 + 미광 여액. 사용처를 뺀 나머지가 블리드다.
    """
    if option not in ("1안", "2안"):
        raise ValueError("option 은 '1안' 또는 '2안'")
    if case not in WATER_CASES:
        raise ValueError(f"case 는 {WATER_CASES} 중 하나")
    f = design.feed
    sg = f.solids_specific_gravity
    peak = dry_tph is None or math.isclose(dry_tph, f.peak_tph)
    if not peak and not math.isclose(dry_tph, f.average_tph):
        raise ValueError("물수지는 최대 · 평균 처리량에서만 푼다")
    tph = f.peak_tph if peak else f.average_tph
    es = design.pretreatment.eva

    if option == "1안":
        rfc = design.rfc
        point = rfc.point_peak if peak else rfc.point_avg
        perf = rfc.performance_peak if peak else rfc.performance_avg
        c_dry, t_dry = perf.concentrate_dry_tph, perf.tailings_dry_tph
        need = point.water_tph
        users = point.wash_water_m3h
        conc_water = point.overflow_water_m3h
        tail_water = point.water_tph + point.wash_water_m3h - conc_water
    else:
        res = design.mechanical.result_peak if peak else design.mechanical.result_avg
        c_dry, t_dry = res.concentrate.dry_tph, res.tailings.dry_tph
        need = res.new_feed.water_tph
        users = res.fresh_water_m3h - (res.new_feed.water_tph - res.filtrate_return_m3h)
        conc_water = res.concentrate.water_tph
        tail_water = res.tailings.water_tph
    cf = _concentrate_filter("FL", c_dry, sg)
    tf = _tailings_filter("FL", t_dry, sg)
    from_es = need - cf.filtrate_m3h

    eva_in = es.freed_eva_tph(tph)
    k = es.rate_constant_1_min
    if case == "W3":
        w7 = f.solids_mass_fraction
        w = db.EVA_ALTERNATIVE_SOLIDS_WT
        water_ratio = ((1.0 - w7) / w7) / ((1.0 - w) / w)
        es_res = solve_eva_circuit(
            f, tph, eva_in, k, feed_solids=w,
            rougher_water_recovery=min(
                1.0, db.EVA_WATER_RECOVERY[db.EVA_ROUGHER_TAG] * water_ratio
            ),
        )
    else:
        es_res = es.result_peak if peak else es.result_avg
    if es_res.tailings.water_tph > from_es + 1e-9:
        # 하류가 더 받지 못한다 — DB-1 이 덜 묽힌다.
        es_res = solve_eva_for_tails_water(f, tph, eva_in, k, from_es)
    makeup = max(0.0, from_es - es_res.tailings.water_tph)
    eva_cake = eva_cake_water_tph(
        es_res.concentrate.component_tph(EVA), db.EVA_CAKE_SOLIDS_VOLUME_FRACTION, db.EVA_SG
    )
    feed_water = tph * (1.0 - db.ATTRITION_SOLIDS_WT) / db.ATTRITION_SOLIDS_WT
    es_clean = es_res.tailings.water_tph + eva_cake - feed_water
    overflow = (tail_water - tf.feed_water_tph) + (conc_water - cf.feed_water_tph)
    return WaterBalance(
        option=option,
        case=case,
        dry_tph=tph,
        feed_water=feed_water,
        es_feed_solids=es_res.rougher.feed.solids_mass_fraction,
        es_clean=es_clean,
        es_wash=db.EVA_CLEANER_WASH_WATER_M3H,
        es_tails_water=es_res.tailings.water_tph,
        eva_cake_water=eva_cake,
        concentrate_filtrate=cf.filtrate_m3h,
        ct1_makeup=makeup,
        process_users=users,
        process_supply=overflow + tf.filtrate_m3h,
        overflow=overflow,
        filter_cake_water=cf.cake_water_tph + tf.cake_water_tph,
        es_ag_loss=EvaSeparation.ag_loss(es_res),
        gac=es_clean if case == "W4" else 0.0,
    )


# --------------------------------------------------------------------------
# 파일럿 시험 셀 — 플랜트 설비가 아니다 (설치 전력·물수지 제외)
# --------------------------------------------------------------------------
def build_pilot(feed: FeedSpec = db.FEED) -> PilotCell:
    """PAS-1 — AS-1 과 기하 상사인 회분식 EVA 박리 시험 셀."""
    return size_pilot_cell(
        db.PILOT_TAG,
        db.PILOT_DUTY,
        feed.solids_specific_gravity,
        aluminium_mass_fraction=feed.component_tph(1.0)["Al"],
        energy_points_kwh_t=db.PILOT_ENERGY_POINTS_KWH_T,
        test_tip_speeds_m_s=db.PILOT_TIP_SPEEDS_M_S,
        reference_tip_speed_m_s=db.ATTRITION_DESIGN_TIP_SPEED_M_S,
        temperatures_c=db.PILOT_TEMPERATURES_C,
        sample_dry_kg=db.PILOT_SAMPLE_DRY_KG,
        max_withdrawal=db.PILOT_MAX_WITHDRAWAL,
        batch_round_kg=db.PILOT_BATCH_ROUND_KG,
        solids_mass_fraction=db.ATTRITION_SOLIDS_WT,
        minimum_solids_volume_fraction=db.ATTRITION_MIN_SOLIDS_VOLUME_FRACTION,
        depth_to_width=db.ATTRITION_DEPTH_TO_WIDTH,
        freeboard_m=db.ATTRITION_FREEBOARD_M,
        impeller_ratio=db.ATTRITION_IMPELLER_RATIO,
        impellers_per_shaft=db.ATTRITION_IMPELLERS_PER_SHAFT,
        power_number=db.ATTRITION_POWER_NUMBER,
        impeller_mass_coeff_kg_m3=db.ATTRITION_IMPELLER_MASS_COEFF_KG_M3,
        impeller_clearance_ratio=db.PILOT_IMPELLER_CLEARANCE_RATIO,
        min_submergence_ratio=db.PILOT_MIN_SUBMERGENCE_RATIO,
        shaft_length_margin_m=db.PILOT_SHAFT_LENGTH_MARGIN_M,
        jacket_u_w_m2k=db.PILOT_JACKET_U_W_M2K,
        tcu_min_supply_c=db.PILOT_TCU_MIN_SUPPLY_C,
        solids_cp_kj_kgk=db.SOLIDS_CP_KJ_KGK,
        torque_sensor_series_nm=db.PILOT_TORQUE_SENSOR_SERIES_NM,
        supply_hz=db.SITE_SUPPLY_HZ,
        motor_pole_series=db.PILOT_MOTOR_POLE_SERIES,
        vfd_overload=db.PILOT_VFD_OVERLOAD,
        max_field_weakening=db.PILOT_MAX_FIELD_WEAKENING,
        vent_m3h=db.PILOT_VENT_M3H,
        h2_lel_vol=db.H2_LEL_VOL,
        h2_design_lel_fraction=db.H2_DESIGN_LEL_FRACTION,
        wetted_material=db.PILOT_WETTED_MATERIAL,
        sample_valve=db.PILOT_SAMPLE_VALVE,
    )


def build_mechanism_screen(feed: FeedSpec = db.FEED) -> MechanismScreen:
    """PAS-1 방식 선정 근거 — 유체 전단 상한과 t 당 표면적."""
    pilot = build_pilot(feed)
    return MechanismScreen(
        shear_rate_s=db.ROTOR_STATOR_SHEAR_RATE_S,
        volume_fraction=pilot.solids_volume_fraction,
        eva_strength_mpa=db.EVA_STRENGTH_MPA,
        feed_size_um=db.PILOT_FEED_SIZE_UM,
        solids_sg=pilot.solids_sg,
        sand_um=db.REFERENCE_SAND_UM,
        sand_sg=db.REFERENCE_SAND_SG,
    )


def build_pilot_scale_up(feed: FeedSpec = db.FEED) -> PilotScaleUp:
    """파일럿 회분 결과를 AS-1 로 옮기는 판정 한계 — 목표는 정광 품위 여유에서."""
    return pilot_scale_up(
        build_pretreatment(feed).scrubber,
        feed.peak_tph,
        feed.average_tph,
        attrition_budget(feed).removal_target,
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
