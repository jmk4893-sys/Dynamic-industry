"""예제 1 — 표준 벤치발파 진동 해석 (전체 보고서 + 그림 생성).

화강암 벤치에서 에멀젼폭약 2열 x 5공 발파 시, 30~150 m 지점의 진동을 해석한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blastdem import BlastPattern, BlastSimulation, get_explosive, get_rock, line_array
from blastdem.simulation import DomainConfig
from blastdem.solver import SolverConfig

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "01_bench")

rock = get_rock("granite")
exp = get_explosive("emulsion")

pattern = BlastPattern(
    exp,
    burden=3.0, spacing=3.5, bench_height=10.0,
    hole_dia=0.076, n_rows=2, n_cols=5,
    delay_hole=0.025, delay_row=0.065,
)

pts, names = line_array((3.0, 0.0), (1, 0), [30, 50, 80, 120, 150])

sim = BlastSimulation(
    rock=rock, explosive=exp, pattern=pattern,
    sensor_points=pts, sensor_names=names,
    domain=DomainConfig(max_frequency=70, max_particles=400_000),
    solver_cfg=SolverConfig(duration=0.0, snapshot_times=[0.02, 0.05, 0.10, 0.16]),
)
sim.build()
print(sim.lattice.summary()); print(sim.source.summary()); print(sim.solver.summary(), "\n")
sim.run()
print("\n" + sim.report())

os.makedirs(OUT, exist_ok=True)
sim.save_csv(os.path.join(OUT, "sensors.csv"))
with open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8") as f:
    f.write(sim.report() + "\n")
print("\n저장:", sim.save_figures(OUT))
