"""태양광 패널 재활용용 부유선별 회로 설계 계산 패키지.

Ag(은)·Cu(구리) 회수를 목적으로 하는 러퍼-스캐빈저-클리너 3단 회로의
셀 사이징, 임펠러/급기 계산, 2속도 반응속도 기반 성능 예측, 순환부하를
포함한 물질수지, 약제 투입량 산정을 수행한다.

기본 설계 케이스는 :mod:`flotation_design.design_basis` 에 정의되어 있으며,
``PYTHONPATH=src python -m flotation_design`` 으로 (또는 설치 후
``flotation-design`` 으로) 전체 설계 계산서를 출력할 수 있다.
"""

from .feed import Component, FeedSpec, PulpProperties
from .sizing import (
    AerationDesign,
    CellGeometry,
    FrothLoading,
    ImpellerDesign,
    ResidenceTime,
    aeration_design,
    cell_geometry,
    froth_loading,
    impeller_design,
    required_slurry_volume,
    residence_time,
)
from .kinetics import (
    ComponentKinetics,
    SeparationResult,
    StreamAssay,
    n_cells_in_series_recovery,
    perfect_mixer_recovery,
    simulate,
)
from .circuit import (
    CircuitResult,
    FlotationUnit,
    Stream,
    UnitResult,
    float_unit,
    solve_circuit,
)
from .reagents import Reagent, ReagentDose, reagent_schedule
from .conditioning import ConditionerDesign, conditioner_train
from .circuit_design import CellDesign, CircuitDesign, build_circuit, solve_at

__all__ = [
    "Component",
    "FeedSpec",
    "PulpProperties",
    "AerationDesign",
    "CellGeometry",
    "FrothLoading",
    "ImpellerDesign",
    "ResidenceTime",
    "aeration_design",
    "cell_geometry",
    "froth_loading",
    "impeller_design",
    "required_slurry_volume",
    "residence_time",
    "ComponentKinetics",
    "SeparationResult",
    "StreamAssay",
    "n_cells_in_series_recovery",
    "perfect_mixer_recovery",
    "simulate",
    "CircuitResult",
    "FlotationUnit",
    "Stream",
    "UnitResult",
    "float_unit",
    "solve_circuit",
    "Reagent",
    "ReagentDose",
    "reagent_schedule",
    "ConditionerDesign",
    "conditioner_train",
    "CellDesign",
    "CircuitDesign",
    "build_circuit",
    "solve_at",
]

__version__ = "0.1.0"
