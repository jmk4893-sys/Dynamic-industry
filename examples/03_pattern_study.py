"""예제 3 — 저항선·공간격·지발시차 파라미터 스터디.

발파진동을 줄이는 3대 수단(장약량 분할, 디커플링, 지발시차)의 효과를 비교한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blastdem import BlastPattern, BlastSimulation, get_explosive, get_rock, line_array
from blastdem.simulation import DomainConfig
from blastdem.solver import SolverConfig

rock = get_rock("gneiss")
exp = get_explosive("emulsion")
DIST = [40, 70, 110]

CASES = {
    "기준 (B3.0 S3.5, 25/65ms)":   dict(burden=3.0, spacing=3.5, delay_hole=0.025, delay_row=0.065),
    "소단면 (B2.0 S2.4, 25/65ms)": dict(burden=2.0, spacing=2.4, delay_hole=0.025, delay_row=0.065),
    "대단면 (B4.0 S4.8, 25/65ms)": dict(burden=4.0, spacing=4.8, delay_hole=0.025, delay_row=0.065),
    "동시기폭 (B3.0 S3.5, 0ms)":   dict(burden=3.0, spacing=3.5, delay_hole=0.000, delay_row=0.000),
    "전자뇌관 (B3.0 S3.5, 8/17ms)": dict(burden=3.0, spacing=3.5, delay_hole=0.008, delay_row=0.017),
}

print(f"{'조건':<30s} {'W[kg]':>7s} {'총장약':>8s} " +
      " ".join(f"{d}m".rjust(9) for d in DIST))
print("=" * 78)
for label, kw in CASES.items():
    pat = BlastPattern(exp, bench_height=10.0, hole_dia=0.076, n_rows=2, n_cols=4, **kw)
    pts, names = line_array((pat.burden / 2, 0), (1, 0), DIST)
    sim = BlastSimulation(
        rock=rock, explosive=exp, pattern=pat, sensor_points=pts, sensor_names=names,
        domain=DomainConfig(max_frequency=70, max_particles=250_000),
        solver_cfg=SolverConfig(duration=0.0, progress=False),
    ).run()
    print(f"{label:<30s} {pat.max_charge_per_delay:7.1f} {pat.total_charge:8.1f} " +
          " ".join(f"{r.ppv:9.2f}" for r in sim.records))
print("=" * 78)
print("W(지발당 최대장약량)가 진동을 지배한다 — 동시기폭은 W 가 총장약량과 같아져 최악이다.")
