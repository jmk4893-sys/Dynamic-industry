#!/usr/bin/env python3
"""미립(35~500 µm) 하이브리드 분리 라인 사이징 계산기.

docs/multi-stage-screen-design.md 의 수치를 재현·재산출한다.
실측치가 확보되면 CONFIG 만 고쳐서 다시 돌리면 된다.

    python3 tools/screen_sizing.py

Rev.2 — 실 입도 35~500 µm, 유리 제거 후 스트림.
        직사각 경사(스캘핑) + 다단 원형 시브(분급) + 향류 컬럼(에어분급) 하이브리드.
        Rev.1 은 0.6~12 mm 조립 가정이었고, 그 영역의 논리는 여기서 성립하지 않는다.
"""
import math

# ── 설계 전제 ────────────────────────────────────────────────────
CONFIG = {
    "feed_tph": 0.25,
    "peak_tph": 0.35,
    # 물질 밀도 kg/m3
    "density": {
        "구리": 8960,
        "실리콘(+Ag)": 2500,
        "백시트+EVA": 1200,
        "EVA": 950,
    },
    # 입도 분획별 중량비 (가정 — 체분석으로 검증할 것)
    "split": {"200~500": 0.317, "106~200": 0.202, "75~106": 0.127, "<75": 0.354},
    # 원형 시브 데크 (개구 µm, 기준 처리능력 t/h/m2 — 초음파 적용 기준)
    "sieve_decks": [(200, 0.50), (106, 0.30), (75, 0.20)],
    "sieve_area_factor": 0.90,
    # 에어분급 컬럼 (하한 µm, 상한 µm, 분획 키)
    "columns": [(75, 106, "75~106"), (106, 200, "106~200")],
    "column_area_m2": 0.030,
    "hood_face_velocity_min": 2.0,   # 개방형 후드가 실내 기류에 지지 않을 최소 면속도
    # 응집 판정
    "hamaker_J": 6.5e-20,
    "contact_gap_m": 4e-10,
    "asperity_radius_m": 0.2e-6,
}

RHO_A, G, MU = 1.2, 9.81, 1.81e-5


def vt(rho, d_m, iters=400):
    """구형 입자 종말속도 [m/s]와 Re. Cd 를 Re 에 대해 반복 수렴(Stokes~Newton 전이)."""
    v = 1e-3
    for _ in range(iters):
        re = max(RHO_A * v * d_m / MU, 1e-9)
        cd = (24 / re if re < 0.1
              else 24 / re * (1 + 0.15 * re ** 0.687) + 0.42 / (1 + 42500 * re ** -1.16))
        v = math.sqrt(4 * G * d_m * (rho - RHO_A) / (3 * cd * RHO_A))
    return v, RHO_A * v * d_m / MU


def diameter_at_vt(rho, v_target, lo=1e-6, hi=5e-3):
    """주어진 종말속도를 갖는 입경 [m]. 이분법."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if vt(rho, mid)[0] < v_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def equal_settling_ratio(rho_heavy, rho_light, d_heavy_m):
    """등침강 입경비. 분획 폭이 이 값보다 좁아야 밀도로 갈린다."""
    v, _ = vt(rho_heavy, d_heavy_m)
    return diameter_at_vt(rho_light, v) / d_heavy_m


def bond_number(d_m, rho, cfg=CONFIG):
    """표면조도 보정 Bond 수 = 부착력/자중. 1 을 넘으면 응집이 이긴다."""
    f = cfg["hamaker_J"] * cfg["asperity_radius_m"] / (6 * cfg["contact_gap_m"] ** 2)
    return f / (math.pi / 6 * d_m ** 3 * rho * G)


def cut_velocity(lo_um, hi_um, cfg=CONFIG):
    """한 입도 분획에서 구리 하한과 폴리머 상한 사이의 커트 속도와 간극."""
    d = cfg["density"]
    v_cu_lo, _ = vt(d["구리"], lo_um * 1e-6)
    v_poly_hi, _ = vt(d["백시트+EVA"], hi_um * 1e-6)
    return (v_cu_lo + v_poly_hi) / 2, v_cu_lo - v_poly_hi


def report(cfg=CONFIG):
    d = cfg["density"]
    peak = cfg["peak_tph"]

    print("=" * 76)
    print("1. 종말속도 [m/s] — 35~500 µm")
    print("=" * 76)
    sizes = [35, 50, 75, 106, 150, 200, 300, 500]
    print(f"{'물질':14s}" + "".join(f"{s:>9d}" for s in sizes) + "   µm")
    for name, rho in d.items():
        print(f"{name:14s}" + "".join(f"{vt(rho, s*1e-6)[0]:9.3f}" for s in sizes))

    print()
    print("=" * 76)
    print("2. 등침강 입경비 — 입도 분획은 이보다 좁아야 한다")
    print("=" * 76)
    for d_cu in (75, 100, 150, 200):
        r_bs = equal_settling_ratio(d["구리"], d["백시트+EVA"], d_cu * 1e-6)
        r_ev = equal_settling_ratio(d["구리"], d["EVA"], d_cu * 1e-6)
        print(f"  구리 {d_cu:3d} µm 대비  백시트+EVA {r_bs:.2f}배 · EVA {r_ev:.2f}배")

    print()
    print("=" * 76)
    print("3. 분획별 커트 속도와 분리 간극")
    print("=" * 76)
    for lo, hi in ((75, 200), (75, 106), (106, 200)):
        v, gap = cut_velocity(lo, hi, cfg)
        ratio = hi / lo
        mark = "견고" if gap > 0.5 else ("성립하나 타이트" if gap > 0 else "중첩 — 불가")
        print(f"  {lo:3d}~{hi:3d} µm (입경비 {ratio:.2f}) : 커트 {v:.2f} m/s, "
              f"간극 {gap:+.3f} m/s  -> {mark}")

    print()
    print("=" * 76)
    print("4. 개방형 후드가 왜 불가능한가")
    print("=" * 76)
    for v_hood in (2.0, 2.5, 2.8, 3.2):
        d_cu = diameter_at_vt(d["구리"], v_hood) * 1e6
        print(f"  후드 {v_hood:.1f} m/s -> 구리 {d_cu:5.1f} µm 이하가 전부 딸려 올라감")
    v_need, _ = cut_velocity(75, 200, cfg)
    print(f"\n  필요 커트 {v_need:.2f} m/s < 후드 최소 면속도 "
          f"{cfg['hood_face_velocity_min']:.1f} m/s -> 개방형 후드로는 원리적으로 불가")

    print()
    print("=" * 76)
    print("5. 응집 판정 — 표면조도 보정 Bond 수 (실리콘 기준)")
    print("=" * 76)
    for d_um in (20, 35, 50, 75, 106, 150, 200):
        bo = bond_number(d_um * 1e-6, d["실리콘(+Ag)"], cfg)
        j = ("응집 지배 — 건식 분급 불가" if bo > 3 else
             "응집 우세 — 강제 분산 필수" if bo > 1 else
             "경계 — 분산기 병용 시 가능" if bo > 0.3 else "자중 지배 — 분급 가능")
        print(f"  d={d_um:4d} µm : Bo = {bo:7.2f}   {j}")

    print()
    print("=" * 76)
    print("6. 은 손실 / 구리 오염 경로")
    print("=" * 76)
    for lo, hi, _ in cfg["columns"]:
        v, _ = cut_velocity(lo, hi, cfg)
        d_si = diameter_at_vt(d["실리콘(+Ag)"], v) * 1e6
        print(f"  {lo:3d}~{hi:3d} µm 컬럼 (커트 {v:.2f} m/s): "
              f"실리콘 {d_si:5.1f} µm 이하 -> 경량측(은 손실), 초과 -> 중량측(구리 오염)")

    print()
    print("=" * 76)
    print(f"7. 원형 시브 소요면적 (최대 {peak*1000:.0f} kg/h)")
    print("=" * 76)
    order = ["200~500", "106~200", "75~106"]
    carried, need = 1.0, 0.0
    for (ap, cap), key in zip(cfg["sieve_decks"], order):
        load = peak * carried
        area = load / cap
        need = max(need, area)
        print(f"  {ap:3d} µm 데크  통과부하={load*1000:5.0f} kg/h  "
              f"능력={cap:.2f} t/h/m2 -> 소요 {area:.2f} m2")
        carried -= cfg["split"][key]
    print(f"\n  지배 소요면적 = {need:.2f} m2")
    for dia in (1000, 1200, 1500):
        a = math.pi / 4 * (dia / 1000) ** 2 * cfg["sieve_area_factor"]
        print(f"    Ø{dia} mm -> 유효 {a:.2f} m2  (여유 {a/need*100-100:+.0f}%)")

    print()
    print("=" * 76)
    print(f"8. 에어분급 컬럼 (단면 {cfg['column_area_m2']:.3f} m2)")
    print("=" * 76)
    total_q = 0.0
    for lo, hi, key in cfg["columns"]:
        v, _ = cut_velocity(lo, hi, cfg)
        q = v * cfg["column_area_m2"] * 3600
        total_q += q
        solids = peak * 1000 * cfg["split"][key]
        print(f"  {lo:3d}~{hi:3d} µm : 커트 {v:.2f} m/s -> {q:5.0f} m3/h, "
              f"고형물 {solids:5.1f} kg/h, 부하 {solids/q:.2f} kg/m3")
    print(f"\n  컬럼 합계 {total_q:.0f} m3/h  (+ 시브 커버 환기·집진 별도)")


if __name__ == "__main__":
    report()
