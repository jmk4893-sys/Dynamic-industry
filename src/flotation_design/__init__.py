"""태양광 셀 은(Ag) 회수 부유선별 설비 설계 계산 패키지.

박리된 c-Si 태양광 셀 분획에서 금속 Ag 를 부유선별로 농축하는 설비를
설계한다. 설계 전제는 실증 논문 두 편(:mod:`flotation_design.references`)
에서 가져왔고, 모델은 그 실험값을 재현하도록 보정되어 있다.

두 안이 공용하는 전처리(:mod:`flotation_design.attrition`)를 앞에 두고,
부선 본체는 두 가지 안을 함께 계산한다.

* **전처리** — 어트리션 스크러버(EVA 박리) + 희석박스 (:mod:`flotation_design.attrition`),
  떨어진 EVA 분리 — 기포제만 쓰는 EVA 부선 (:mod:`flotation_design.eva_separation`)
* **1안** — 세척수 bias 를 쓰는 연속 부선조 1단 (:mod:`flotation_design.rfc`)
* **2안** — 기계식 러퍼 뱅크 + 클리너 (:mod:`flotation_design.circuit`)

``PYTHONPATH=src python -m flotation_design`` 으로 (또는 설치 후
``flotation-design`` 으로) 전체 설계 계산서를 출력할 수 있다.
"""

from . import references
from .attrition import (
    AttritionCellGeometry,
    AttritionDrive,
    AttritionScrubber,
    AttritionShaft,
    DilutionBox,
    dilution_box,
    octagon_area_m2,
    short_circuit_fraction,
    size_attrition,
    solids_mass_fraction_for_volume_fraction,
)
from .circuit import (
    CircuitResult,
    FlotationUnit,
    Stream,
    UnitResult,
    concentrate_grade_ceiling,
    float_unit,
    solve_circuit,
)
from .conditioning import ConditionerDesign, conditioner_train
from .eva_separation import (
    DewateringBag,
    EvaBatchLimits,
    EvaDesignParticle,
    EvaFilmCase,
    EvaMethodScreen,
    EvaRequirement,
    eva_content_from_film,
    eva_rate_constant_1_min,
    flake_equivalent_diameter_um,
)
from .feed import Component, FeedSpec, PulpProperties, pulp_at
from .kinetics import (
    ComponentKinetics,
    SeparationResult,
    StreamAssay,
    batch_recovery,
    n_cells_in_series_recovery,
    perfect_mixer_recovery,
    simulate,
)
from .plant import (
    EvaSeparation,
    MechanicalCell,
    MechanicalOption,
    PlantDesign,
    Pretreatment,
    RfcOption,
    Thickener,
    build_eva_separation,
    build_plant,
    build_pretreatment,
    solve_eva_circuit,
    solve_mechanical,
)
from .reagents import Reagent, ReagentDose, reagent_schedule
from .rfc import (
    RfcDesign,
    RfcOperatingPoint,
    RfcPerformance,
    rfc_separation,
    size_rfc,
    slurry_volumetric_flow_m3h,
)
from .sizing import (
    AerationDesign,
    CellGeometry,
    FrothLoading,
    ImpellerDesign,
    ResidenceTime,
    RotorDynamics,
    aeration_design,
    cantilever_rotor_dynamics,
    cell_geometry,
    froth_loading,
    impeller_design,
    required_slurry_volume,
    residence_time,
    torsional_section_modulus_m3,
)

__all__ = [
    "references",
    "Component",
    "FeedSpec",
    "PulpProperties",
    "pulp_at",
    "ComponentKinetics",
    "SeparationResult",
    "StreamAssay",
    "batch_recovery",
    "n_cells_in_series_recovery",
    "perfect_mixer_recovery",
    "simulate",
    "CircuitResult",
    "FlotationUnit",
    "Stream",
    "UnitResult",
    "float_unit",
    "solve_circuit",
    "RfcDesign",
    "RfcOperatingPoint",
    "RfcPerformance",
    "rfc_separation",
    "size_rfc",
    "slurry_volumetric_flow_m3h",
    "MechanicalCell",
    "MechanicalOption",
    "PlantDesign",
    "Pretreatment",
    "RfcOption",
    "Thickener",
    "build_plant",
    "build_pretreatment",
    "solve_mechanical",
    "AerationDesign",
    "CellGeometry",
    "FrothLoading",
    "ImpellerDesign",
    "ResidenceTime",
    "RotorDynamics",
    "aeration_design",
    "cantilever_rotor_dynamics",
    "cell_geometry",
    "froth_loading",
    "impeller_design",
    "required_slurry_volume",
    "residence_time",
    "torsional_section_modulus_m3",
    "Reagent",
    "ReagentDose",
    "reagent_schedule",
    "ConditionerDesign",
    "conditioner_train",
    "AttritionCellGeometry",
    "AttritionDrive",
    "AttritionScrubber",
    "AttritionShaft",
    "DilutionBox",
    "concentrate_grade_ceiling",
    "dilution_box",
    "octagon_area_m2",
    "short_circuit_fraction",
    "size_attrition",
    "solids_mass_fraction_for_volume_fraction",
    "DewateringBag",
    "EvaBatchLimits",
    "EvaDesignParticle",
    "EvaFilmCase",
    "EvaMethodScreen",
    "EvaRequirement",
    "EvaSeparation",
    "build_eva_separation",
    "eva_content_from_film",
    "eva_rate_constant_1_min",
    "flake_equivalent_diameter_um",
    "solve_eva_circuit",
]

__version__ = "0.2.0"
