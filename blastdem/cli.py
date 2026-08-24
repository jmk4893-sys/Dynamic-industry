"""명령행 실행 인터페이스.

    python -m blastdem --list
    python -m blastdem --rock granite --explosive emulsion --burden 3 --spacing 3.5 \
                       --rows 2 --cols 5 --distances 30 50 80 120 --out output
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from . import empirical
from .explosives import EXPLOSIVE_DB, get_explosive
from .pattern import BlastPattern
from .rock import ROCK_DB, get_rock
from .sensors import line_array
from .simulation import BlastSimulation, DomainConfig
from .solver import SolverConfig
from .source import SourceConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="blastdem",
        description="암발파 진동전파 3D DEM 해석",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--list", action="store_true", help="암종/폭약 목록 출력 후 종료")

    g = p.add_argument_group("암반")
    g.add_argument("--rock", default="granite", choices=list(ROCK_DB), help="암종")
    g.add_argument("--vp", type=float, help="현장 Vp [m/s] (지정 시 E 를 역산)")
    g.add_argument("--density", type=float, help="밀도 [kg/m^3] 재지정")
    g.add_argument("--damping", type=float, help="재료 감쇠비 재지정")

    g = p.add_argument_group("폭약")
    g.add_argument("--explosive", default="emulsion", choices=list(EXPLOSIVE_DB), help="폭약 종류")
    g.add_argument("--charge", type=float, help="공당 장약량 [kg] (지정 시 장약장 역산)")

    g = p.add_argument_group("발파패턴")
    g.add_argument("--burden", type=float, default=3.0, help="저항선 B [m]")
    g.add_argument("--spacing", type=float, default=3.5, help="공간격 S [m]")
    g.add_argument("--bench", type=float, default=10.0, help="벤치고 H [m]")
    g.add_argument("--rows", type=int, default=2, help="열 수")
    g.add_argument("--cols", type=int, default=5, help="열당 공 수")
    g.add_argument("--hole-dia", type=float, default=76.0, help="천공경 [mm]")
    g.add_argument("--charge-dia", type=float, help="장약경 [mm] (미지정=완전결합)")
    g.add_argument("--stemming", type=float, help="전색장 [m] (미지정=1.0B)")
    g.add_argument("--subdrill", type=float, help="하부천공장 [m] (미지정=0.3B)")
    g.add_argument("--delay-hole", type=float, default=25.0, help="공간 시차 [ms]")
    g.add_argument("--delay-row", type=float, default=65.0, help="열간 시차 [ms]")

    g = p.add_argument_group("계측")
    g.add_argument("--distances", type=float, nargs="+", default=[30, 50, 80, 120],
                   help="폭원 중심에서의 계측 거리 [m]")
    g.add_argument("--azimuth", type=float, default=0.0, help="측선 방위각 [deg] (0=+x)")

    g = p.add_argument_group("수치해석")
    g.add_argument("--duration", type=float, default=0.0, help="해석시간 [s] (0=자동)")
    g.add_argument("--grid", type=float, help="입자간격 [m] (미지정=자동)")
    g.add_argument("--max-freq", type=float, default=80.0, help="해상 목표 최대주파수 [Hz]")
    g.add_argument("--max-particles", type=int, default=350_000, help="입자수 상한")
    g.add_argument("--cfl", type=float, default=0.25, help="시간간격 안전계수")
    g.add_argument("--efficiency", type=float, default=1.0, help="폭원 전달효율 eta")
    g.add_argument("--damp-band", type=float, nargs=2, default=[10.0, 120.0],
                   metavar=("F1", "F2"),
                   help="Rayleigh 감쇠가 목표 감쇠비를 만족하는 주파수 대역 [Hz]. "
                        "상한을 낮추면 고주파를 더 강하게 감쇠시켜 절리 산란효과를 근사한다")
    g.add_argument("--no-breakage", action="store_true", help="본드 파괴 비활성(순수 탄성)")
    g.add_argument("--snapshots", type=float, nargs="*", help="파면 저장 시각 [ms]")

    g = p.add_argument_group("출력")
    g.add_argument("--out", default="output", help="결과 저장 폴더")
    g.add_argument("--law", default="kr_mean", choices=list(empirical.SD_LAWS),
                   help="비교 경험식")
    g.add_argument("--calibrate", action="store_true",
                   help="해석 PPV 를 --law 경험식에 맞추도록 폭원 효율을 자동 보정")
    g.add_argument("--no-figures", action="store_true", help="그림 생성 생략")
    g.add_argument("--quiet", action="store_true", help="진행률 표시 생략")
    return p


def print_catalog() -> None:
    print("=" * 70, "\n  암종 (--rock)\n" + "=" * 70)
    for k, r in ROCK_DB.items():
        print(f"  {k:<12s} {r.name:<24s} Vp={r.p_velocity:5.0f} m/s  "
              f"E={r.young / 1e9:4.0f} GPa  {r.quality}")
    print("\n" + "=" * 70, "\n  폭약 (--explosive)\n" + "=" * 70)
    for k, e in EXPLOSIVE_DB.items():
        print(f"  {k:<12s} {e.name:<26s} rho={e.density:4.2f}  VOD={e.vod:5.0f} m/s  "
              f"RWS={e.rws:3.0f}")
    print("\n" + "=" * 70, "\n  비교 경험식 (--law)\n" + "=" * 70)
    for k, law in empirical.SD_LAWS.items():
        print(f"  {k:<12s} {law}")
    print("\n" + "=" * 70, "\n  발파진동 허용기준 (PPV)\n" + "=" * 70)
    for name, lim in empirical.REGULATION:
        print(f"  {name:<24s} {lim:6.1f} mm/s")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print_catalog()
        return 0

    # 암반
    rock = get_rock(args.rock)
    if args.density:
        rock.density = args.density
    if args.vp:
        rock.young = rock.density * args.vp ** 2 / 1.2
    if args.damping is not None:
        rock.damping_ratio = args.damping

    # 폭약 · 패턴
    exp = get_explosive(args.explosive)
    hole_dia = args.hole_dia / 1000.0
    charge_dia = (args.charge_dia / 1000.0) if args.charge_dia else hole_dia
    pat = BlastPattern(
        exp, burden=args.burden, spacing=args.spacing, bench_height=args.bench,
        hole_dia=hole_dia, charge_dia=charge_dia, n_rows=args.rows, n_cols=args.cols,
        subdrill=args.subdrill, stemming=args.stemming,
        delay_hole=args.delay_hole / 1000.0, delay_row=args.delay_row / 1000.0,
    )
    if args.charge:   # 장약량 직접 지정 -> 전색장을 줄여 장약장을 맞춘다
        need = exp.charge_length(args.charge, charge_dia)
        depth = pat.bench_height + pat.subdrill
        min_stem = max(0.5, 15.0 * hole_dia)      # 전색장 하한 (천공경의 15배)
        if need > depth - min_stem:
            fits = exp.charge_weight(depth - min_stem, charge_dia)
            print(f"  [경고] 요청 장약량 {args.charge:.1f} kg 은 장약장 {need:.2f} m 가 필요하나,\n"
                  f"         천공장 {depth:.2f} m 에서 전색장 {min_stem:.2f} m 를 확보하면 "
                  f"최대 {fits:.1f} kg 까지만 가능합니다.\n"
                  f"         {fits:.1f} kg 으로 진행합니다. 더 넣으려면 --bench 를 키우거나 "
                  f"--charge-dia 를 늘리십시오.\n")
        stem = max(min_stem, depth - need)
        pat = BlastPattern(
            exp, burden=args.burden, spacing=args.spacing, bench_height=args.bench,
            hole_dia=hole_dia, charge_dia=charge_dia, n_rows=args.rows, n_cols=args.cols,
            subdrill=args.subdrill, stemming=stem,
            delay_hole=args.delay_hole / 1000.0, delay_row=args.delay_row / 1000.0,
        )

    # 계측 측선
    th = np.radians(args.azimuth)
    cx = np.mean([h.x for h in pat.holes])
    cy = np.mean([h.y for h in pat.holes])
    pts, names = line_array((cx, cy), (np.cos(th), np.sin(th)), args.distances)

    sim = BlastSimulation(
        rock=rock, explosive=exp, pattern=pat, sensor_points=pts, sensor_names=names,
        domain=DomainConfig(spacing=args.grid, max_frequency=args.max_freq,
                            max_particles=args.max_particles),
        source_cfg=SourceConfig(efficiency=args.efficiency),
        solver_cfg=SolverConfig(
            duration=args.duration, cfl=args.cfl,
            damping_f1=args.damp_band[0], damping_f2=args.damp_band[1],
            allow_breakage=not args.no_breakage, progress=not args.quiet,
            snapshot_times=[t / 1000.0 for t in (args.snapshots or [])],
        ),
    )
    sim.build()
    print(sim.lattice.summary())
    print(sim.source.summary())
    print(sim.solver.summary())
    print()
    sim.run()
    if args.calibrate:
        f = sim.apply_calibration(args.law)
        print(f"\n  폭원 효율 보정: eta = {f:.2f} ({empirical.SD_LAWS[args.law].name} 기준)")

    report = sim.report(args.law)
    print("\n" + report)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "report.txt"), "w", encoding="utf-8") as f:
        f.write(report + "\n")
    sim.save_csv(os.path.join(args.out, "sensors.csv"))
    if not args.no_figures:
        files = sim.save_figures(args.out, args.law)
        print(f"\n그림 {len(files)}개 저장: {args.out}/")
    print(f"보고서: {args.out}/report.txt,  데이터: {args.out}/sensors.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
