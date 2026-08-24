"""예제 2 — 폭약 종류별 진동 비교.

동일 패턴/암반에서 폭약만 바꿔가며 PPV 를 비교한다.
디커플링(정밀폭약)과 저폭속 폭약의 진동저감 효과를 정량 확인할 수 있다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blastdem import BlastPattern, BlastSimulation, get_explosive, get_rock, line_array
from blastdem.empirical import evaluate
from blastdem.simulation import DomainConfig
from blastdem.solver import SolverConfig

CASES = [
    ("anfo",      0.076),   # 완전결합
    ("emulsion",  0.076),
    ("dynamite",  0.076),
    ("precision", 0.032),   # 디커플링 장약 (조절발파)
    ("low_vod",   0.076),   # 미진동 폭약
]
DISTANCES = [30, 50, 80]
rock = get_rock("granite")
rows = []

for key, cdia in CASES:
    exp = get_explosive(key)
    pat = BlastPattern(exp, burden=3.0, spacing=3.5, bench_height=10.0,
                       hole_dia=0.076, charge_dia=cdia, n_rows=1, n_cols=3)
    pts, names = line_array((0, 0), (1, 0), DISTANCES)
    sim = BlastSimulation(
        rock=rock, explosive=exp, pattern=pat, sensor_points=pts, sensor_names=names,
        domain=DomainConfig(max_frequency=70, max_particles=250_000),
        solver_cfg=SolverConfig(duration=0.10, progress=False),
    ).run()
    W = pat.max_charge_per_delay
    ppv = [r.ppv for r in sim.records]
    rows.append((exp.name, cdia * 1000, W, ppv, sim.records[0].dominant_frequency))
    print(f"완료: {exp.name}")

print("\n" + "=" * 96)
print(f"{'폭약':<24s} {'장약경':>7s} {'W[kg]':>7s} " +
      " ".join(f"{d}m[mm/s]".rjust(11) for d in DISTANCES) + f"{'f[Hz]':>7s}")
print("=" * 96)
base = rows[1][3][0]
for name, cd, W, ppv, f in rows:
    print(f"{name:<24s} {cd:6.0f}mm {W:7.1f} " +
          " ".join(f"{v:11.2f}" for v in ppv) + f"{f:7.0f}")
print("-" * 96)
print("에멀젼 대비 30 m PPV 비:")
for name, cd, W, ppv, f in rows:
    print(f"   {name:<24s} {ppv[0] / base:5.2f} 배   ->  {evaluate(ppv[0])}")
