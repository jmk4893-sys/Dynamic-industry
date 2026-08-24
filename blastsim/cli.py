"""명령행 실행 인터페이스.

    python -m blastsim --list                       # 암종/폭약/경험식 목록
    python -m blastsim --gui                        # 윈도우 GUI 실행
    python -m blastsim --rock granite --explosive emulsion \\
        --burden 3 --spacing 3.5 --bench 10 --rows 2 --cols 5 \\
        --distances 30 50 80 120 --quality 보통 --out output
"""

from __future__ import annotations

import argparse
import sys

from . import empirical
from .explosives import EXPLOSIVE_DB
from .project import QUALITY_PRESETS, BlastProject, ProjectConfig
from .rock import ROCK_DB


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="blastsim",
        description="발파 진동(FDM) · 파쇄/비산(DEM) 통합 해석",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--list", action="store_true", help="암종/폭약/경험식 목록 출력")
    p.add_argument("--gui", action="store_true", help="윈도우 GUI 실행")

    g = p.add_argument_group("암반")
    g.add_argument("--rock", default="granite", choices=list(ROCK_DB))
    g.add_argument("--vp", type=float, help="현장 Vp [m/s] (지정 시 E 역산)")
    g.add_argument("--poisson", type=float, default=0.25, help="포아송비 (FDM 은 자유)")
    g.add_argument("--damping", type=float, help="재료 감쇠비")

    g = p.add_argument_group("폭약 · 천공")
    g.add_argument("--explosive", default="emulsion", choices=list(EXPLOSIVE_DB))
    g.add_argument("--hole-dia", type=float, default=76.0, help="천공경 [mm]")
    g.add_argument("--charge-dia", type=float, help="장약경 [mm] (미지정=완전결합)")
    g.add_argument("--charge", type=float, help="공당 장약량 [kg]")

    g = p.add_argument_group("발파 패턴")
    g.add_argument("--burden", type=float, default=3.0, help="저항선 B [m]")
    g.add_argument("--spacing", type=float, default=3.5, help="공간격 S [m]")
    g.add_argument("--bench", type=float, default=10.0, help="벤치고 H [m]")
    g.add_argument("--rows", type=int, default=2)
    g.add_argument("--cols", type=int, default=5)
    g.add_argument("--stemming", type=float, help="전색장 [m] (미지정=1.0B)")
    g.add_argument("--subdrill", type=float, help="하부천공장 [m] (미지정=0.3B)")
    g.add_argument("--delay-hole", type=float, default=25.0, help="공간 시차 [ms]")
    g.add_argument("--delay-row", type=float, default=65.0, help="열간 시차 [ms]")

    g = p.add_argument_group("조건")
    g.add_argument("--partial-stemming", action="store_true",
                   help="부분 전색 (기본은 완전 전색)")
    g.add_argument("--one-free-face", action="store_true",
                   help="1자유면 (기본은 2자유면: 상부면 + 벤치면)")
    g.add_argument("--face-angle", type=float, default=0.0, help="사면 경사각 [deg]")

    g = p.add_argument_group("계측 · 해석")
    g.add_argument("--distances", type=float, nargs="+",
                   default=[30, 50, 80, 120], help="계측거리 [m]")
    g.add_argument("--azimuth", type=float, default=0.0, help="측선 방위각 [deg]")
    g.add_argument("--quality", default="보통", choices=list(QUALITY_PRESETS))
    g.add_argument("--no-vibration", action="store_true", help="FDM 진동해석 생략")
    g.add_argument("--no-fragmentation", action="store_true", help="DEM 파쇄해석 생략")
    g.add_argument("--no-video", action="store_true", help="영상 생성 생략")
    g.add_argument("--no-calibrate", action="store_true", help="폭원 보정 생략")
    g.add_argument("--law", default="kr_mean", choices=list(empirical.SD_LAWS))
    g.add_argument("--efficiency", type=float, default=1.0, help="폭원 전달효율 eta")
    g.add_argument("--gas-efficiency", type=float, default=0.25,
                   help="가스가 암반 이동에 쓰는 에너지 비율")
    g.add_argument("--out", default="output", help="결과 폴더")
    return p


def print_catalog() -> None:
    print("=" * 72, "\n  암종 (--rock)\n" + "=" * 72)
    for k, r in ROCK_DB.items():
        print(f"  {k:<12s} {r.name:<24s} Vp={r.p_velocity:5.0f} m/s  "
              f"E={r.young / 1e9:4.0f} GPa  {r.quality}")
    print("\n" + "=" * 72, "\n  폭약 (--explosive)\n" + "=" * 72)
    for k, e in EXPLOSIVE_DB.items():
        print(f"  {k:<12s} {e.name:<26s} rho={e.density:4.2f}  VOD={e.vod:5.0f} m/s  "
              f"RWS={e.rws:3.0f}")
    print("\n" + "=" * 72, "\n  해석 품질 (--quality)\n" + "=" * 72)
    for k, q in QUALITY_PRESETS.items():
        print(f"  {k:<6s} FDM {q['fdm_max_freq']:5.0f} Hz / 셀 {q['fdm_max_cells']:>9,}"
              f"  |  DEM 입자 {q['particle'] * 100:.0f} cm, DEM {q['throw'] * 1e3:.0f} ms"
              f" + 탄도 {(q['frag_total'] - q['throw']) * 1e3:.0f} ms")
    print("\n" + "=" * 72, "\n  비교 경험식 (--law)\n" + "=" * 72)
    for k, law in empirical.SD_LAWS.items():
        print(f"  {k:<12s} {law}")
    print("\n" + "=" * 72, "\n  발파진동 허용기준 (PPV)\n" + "=" * 72)
    for name, lim in empirical.REGULATION:
        print(f"  {name:<24s} {lim:6.1f} mm/s")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print_catalog()
        return 0
    if args.gui:
        from .gui import main as gui_main
        return gui_main()

    cfg = ProjectConfig(
        rock_key=args.rock, vp=args.vp, poisson=args.poisson,
        damping_ratio=args.damping,
        explosive_key=args.explosive, hole_dia_mm=args.hole_dia,
        charge_dia_mm=args.charge_dia, charge_kg=args.charge,
        burden=args.burden, spacing=args.spacing, bench_height=args.bench,
        n_rows=args.rows, n_cols=args.cols, stemming=args.stemming,
        subdrill=args.subdrill, delay_hole_ms=args.delay_hole,
        delay_row_ms=args.delay_row,
        full_stemming=not args.partial_stemming,
        two_free_face=not args.one_free_face, face_angle_deg=args.face_angle,
        distances=list(args.distances), azimuth_deg=args.azimuth,
        quality=args.quality,
        run_vibration=not args.no_vibration,
        run_fragmentation=not args.no_fragmentation,
        make_video=not args.no_video,
        calibrate=not args.no_calibrate,
        law=args.law, efficiency=args.efficiency,
        gas_efficiency=args.gas_efficiency, outdir=args.out,
    )
    proj = BlastProject(cfg)
    proj.run_all()
    print("\n" + proj.report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
