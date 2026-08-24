"""blastdem — 암발파 진동전파 3D DEM 해석 프로그램.

간단 사용 예
-----------
    from blastdem import *

    sim = BlastSimulation(
        rock=get_rock("granite"),
        explosive=get_explosive("emulsion"),
        pattern=BlastPattern(get_explosive("emulsion"), burden=3.0, spacing=3.5),
        sensor_points=..., sensor_names=...,
    ).run()
    print(sim.report())
    sim.save_figures("output")
"""

from .rock import Rock, ROCK_DB, get_rock
from .explosives import Explosive, EXPLOSIVE_DB, get_explosive
from .pattern import BlastHole, BlastPattern
from .lattice import Lattice
from .source import BlastSource, SourceConfig
from .solver import DEMSolver, SolverConfig, Result
from .sensors import SensorRecord, line_array, radial_array, build_records, table
from .empirical import ScaledDistanceLaw, SD_LAWS, REGULATION, fit_law, regulation_table
from .simulation import BlastSimulation, DomainConfig

__version__ = "0.1.0"
__all__ = [
    "Rock", "ROCK_DB", "get_rock",
    "Explosive", "EXPLOSIVE_DB", "get_explosive",
    "BlastHole", "BlastPattern", "Lattice",
    "BlastSource", "SourceConfig", "DEMSolver", "SolverConfig", "Result",
    "SensorRecord", "line_array", "radial_array", "build_records", "table",
    "ScaledDistanceLaw", "SD_LAWS", "REGULATION", "fit_law", "regulation_table",
    "BlastSimulation", "DomainConfig",
]
