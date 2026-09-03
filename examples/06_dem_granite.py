"""예제 6 — 화강암 DEM 파쇄·암발파 거동 해석 (물리엔진 직접 구동).

예제 5 에서 사면체 메쉬로 형상을 만든 **Ø75 mm x 12 m 천공홀**을 그대로 쓰되,
이번에는 그 안에서 폭약이 터졌을 때 암반이 어떻게 깨지고 어디로 날아가는지를
입자 물리엔진(결합입자 DEM)으로 직접 계산한다.

물리엔진 구성
-------------
    입자   : 지터를 준 단순입방 격자 위의 구형 입자 (질량 = rho * d^3)
    본드   : 1.45 d 이내 이웃과의 중심력 스프링, k = 0.4 E d
             인장변형률이 sigma_t / E 를 넘으면 끊어진다  -> 이것이 '파쇄'
    접촉   : 본드가 끊긴 뒤 Hertz 형 법선 스프링 + Coulomb 마찰
    하중   : 충격파(임피던스 제한) + 폭굉가스 단열팽창 P = P0 (V0/V)^gamma
    적분   : (1) 본드 단계 -> (2) 이동 단계 -> (3) 파쇄체 강체 탄도 단계

암반은 화강암(E = 60 GPa, UCS = 160 MPa, sigma_t = 10 MPa, rho = 2650)이다.

발파 제원 — 12.0 m 천공장을 유지하도록 벤치고와 하부천공장을 맞췄다.
    천공경 Ø75 mm,  천공장 12.0 m  ( 벤치고 11.25 + 하부천공 0.75 )
    저항선 B = 2.5 m,  공간격 S = 3.0 m   ( S/B = 1.2,  H/B = 4.5 )
    전색장 2.5 m (33 D),  2열 x 5공 = 10공,  에멀젼
    비장약량 0.60 kg/m^3  — 화강암 벤치발파 표준 범위(0.5~0.8)

출력
----
    output/06_dem/frag_size.png      파쇄 입도분포 + 입자 속도분포
    output/06_dem/frag_muckpile.png  발파 전후 측면도 (이동거리 색상)
    output/06_dem/frag_behavior.png  공내압 · 파쇄진행 · 에너지 · 저항선 이동
    output/06_dem/frag_video.mp4     파쇄·비산 애니메이션
    output/06_dem/report.txt         해석 보고서

    python examples/06_dem_granite.py [--quality 빠름|보통|정밀] [--no-video]
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blastsim.project import BlastProject, ProjectConfig

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "06_dem")


def build(quality: str = "보통", video: bool = True) -> ProjectConfig:
    """예제 5 의 천공홀(Ø75 mm x 12 m)과 일치하는 화강암 발파 조건."""
    return ProjectConfig(
        # --- 암반: 화강암 ---
        rock_key="granite",
        poisson=0.25,
        # --- 폭약 · 천공 ---
        explosive_key="emulsion",
        hole_dia_mm=75.0,               # 메쉬의 천공홀과 동일
        # --- 패턴: 벤치고 11.25 + 하부천공 0.75 = 천공장 12.0 m ---
        burden=2.5, spacing=3.0, bench_height=11.25, subdrill=0.75,
        n_rows=2, n_cols=5,
        delay_hole_ms=25.0, delay_row_ms=65.0,
        # --- 조건 ---
        full_stemming=True,             # 완전 전색 (가스 구속 -> 이동 지배)
        two_free_face=True,             # 상부면 + 벤치면
        # --- 해석: DEM 만 ---
        quality=quality,
        run_vibration=False,
        run_fragmentation=True,
        make_video=video,
        outdir=OUT,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="화강암 DEM 파쇄·비산 해석")
    ap.add_argument("--quality", default="보통", choices=["빠름", "보통", "정밀"])
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    proj = BlastProject(build(args.quality, not args.no_video))

    print(proj.rock.summary())
    print(proj.pattern.summary())
    print()

    t0 = time.time()
    proj.run_fragmentation()
    print(f"\nDEM 해석 {time.time() - t0:.1f} s")

    proj.save()                       # 보고서 + frag_size / muckpile / behavior
    if not args.no_video:
        proj.make_videos()
        proj.save()                   # 영상 목록을 보고서에 반영

    print("\n" + proj.report())
    print(f"\n결과: {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
