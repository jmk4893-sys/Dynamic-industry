"""예제 4 — 통합 해석: FDM 진동 + DEM 파쇄·비산 + 영상.

2자유면(상부면 + 벤치면), 완전 전색 조건에서
  * 원거리 진동(FDM)  -> PPV, 주파수, 규제검토, 지표 진동 등고선/영상
  * 근거리 파쇄·비산(DEM) -> 파쇄입도, 이동·적재, 비산거리, 영상
을 한 번에 만든다.

    python examples/04_hybrid_full.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blastsim.project import BlastProject, ProjectConfig

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "04_hybrid")

cfg = ProjectConfig(
    # 암반
    rock_key="granite",
    poisson=0.25,
    # 폭약 · 천공
    explosive_key="emulsion",
    hole_dia_mm=76.0,
    # 발파 패턴
    burden=3.0, spacing=3.5, bench_height=10.0,
    n_rows=2, n_cols=4,
    delay_hole_ms=25.0, delay_row_ms=65.0,
    # 조건
    full_stemming=True,      # 완전 전색
    two_free_face=True,      # 2자유면
    # 계측
    distances=[30, 50, 80, 120],
    # 해석
    quality="빠름",          # 빠름 / 보통 / 정밀
    run_vibration=True,
    run_fragmentation=True,
    make_video=True,
    calibrate=True,
    outdir=OUT,
)

proj = BlastProject(cfg)
proj.run_all()
print("\n" + proj.report())
