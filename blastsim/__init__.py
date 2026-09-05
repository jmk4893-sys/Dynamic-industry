"""blastsim — 발파 진동·파쇄·비산 통합 해석 프로그램.

    FDM (fdm.py)   : 원거리 진동 전파 — 엇갈림 격자 속도-응력, 공간 4차
    DEM (frag.py)  : 근거리 파쇄·비산 — 본드형 입자, 접촉·중력·가스팽창
    DEM (lattice.py): 격자형 진동 해석 (FDM 교차검증용, 초기 구현)
    MESH (mesh.py) : 천공홀을 형상 그대로 담는 비정렬 사면체 메쉬

간단 사용 예
-----------
    from blastsim import *

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
from .fdm import BenchGeometry, CavitySource, FDMConfig, FDMModel, FDMSolver
from .frag import BlastLoad, FragConfig, FragModel, FragSolver, fragment_analysis
from .project import BlastProject, ProjectConfig, QUALITY_PRESETS, fragmentation_stats
from .mesh import (MESH_PRESETS, REGION_HOLE, REGION_ROCK, Borehole, BoxDomain,
                   MeshConfig, TetMesh, build_tet_mesh)

__version__ = "0.1.0"
__all__ = [
    "Rock", "ROCK_DB", "get_rock",
    "Explosive", "EXPLOSIVE_DB", "get_explosive",
    "BlastHole", "BlastPattern", "Lattice",
    "BlastSource", "SourceConfig", "DEMSolver", "SolverConfig", "Result",
    "SensorRecord", "line_array", "radial_array", "build_records", "table",
    "ScaledDistanceLaw", "SD_LAWS", "REGULATION", "fit_law", "regulation_table",
    "BlastSimulation", "DomainConfig",
    "BenchGeometry", "CavitySource", "FDMConfig", "FDMModel", "FDMSolver",
    "BlastLoad", "FragConfig", "FragModel", "FragSolver", "fragment_analysis",
    "BlastProject", "ProjectConfig", "QUALITY_PRESETS", "fragmentation_stats",
    "BoxDomain", "Borehole", "MeshConfig", "TetMesh", "build_tet_mesh",
    "MESH_PRESETS", "REGION_ROCK", "REGION_HOLE",
]
