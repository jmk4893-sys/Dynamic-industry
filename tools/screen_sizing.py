#!/usr/bin/env python3
"""미립(35~500 µm) 하이브리드 분리 라인 사이징 계산기.

docs/multi-stage-screen-design.md 의 수치를 재현·재산출한다.
실측치가 확보되면 CONFIG 만 고쳐서 다시 돌리면 된다.

    python3 tools/screen_sizing.py

Rev.3 — 실 입도 35~500 µm, 유리 제거 후 스트림.
        직사각 경사(스캘핑) + 다단 원형 시브(입도 분급) + 터보 분급기(밀도 선별).
        Rev.2 의 중력식 지그재그 컬럼은 실용 범위(0.3~10 mm) 밖이라 폐기하고,
        디플렉터 휠(터보) 분급기로 교체했다.
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
    # 터보(디플렉터 휠) 분급기 — (태그, 하한 µm, 상한 µm, 분획키, 회전수, 반경방향 풍속)
    # v_r 은 밴드(비구리 상한 ~ 구리 하한)의 기하평균 — 양쪽 여유를 같게 둔다.
    "classifiers": [
        ("TC-01", 75, 106, "75~106", 200, 2.07),
        ("TC-02", 106, 200, "106~200", 150, 1.88),
    ],
    "wheel_radius_m": 0.075,         # Ø150 디플렉터 휠 (두 대 공통)
    "wheel_height_m": 0.065,         # 고형물 부하를 0.35 kg/m3 이하로 낮추기 위해 h50 -> h65
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


def centrifugal_acceleration(rpm, radius_m):
    """디플렉터 휠 외주의 원심가속도 [m/s2] = omega^2 R."""
    return (2.0 * math.pi * rpm / 60.0) ** 2 * radius_m


def vt_in_field(rho, d_m, accel, iters=300):
    """가속도장 accel 에서의 종말속도 [m/s].

    터보 분급기의 컷 조건은 '원심장 종말속도 = 반경방향 공기속도' 이므로,
    중력 g 를 omega^2 R 로 바꾼 같은 문제가 된다.
    """
    v = 1e-4
    for _ in range(iters):
        re = max(RHO_A * v * d_m / MU, 1e-12)
        cd = (24 / re if re < 0.1
              else 24 / re * (1 + 0.15 * re ** 0.687) + 0.42 / (1 + 42500 * re ** -1.16))
        v = math.sqrt(4 * accel * d_m * (rho - RHO_A) / (3 * cd * RHO_A))
    return v


def _diameter_at_field_velocity(rho, v_target, accel, lo=1e-6, hi=3e-3):
    """가속도장 accel 에서 종말속도가 v_target 이 되는 입경 [m]."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if vt_in_field(rho, mid, accel) < v_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# 재질별 실제 입도 범위 [µm] — 밴드 상한을 정할 때 이 범위를 넘겨 쓰면 안 된다.
SIZE_RANGE_UM = {"구리": (75, 200), "실리콘(+Ag)": (20, 120),
                 "백시트+EVA": (75, 500), "EVA": (75, 500)}


def separation_bounds(lo_um, hi_um, accel, cfg=CONFIG):
    """분획 안에서 (구리 최저속도, 비구리 최고속도, 제약 재질).

    비구리 상한은 폴리머만이 아니라 실리콘까지 포함해서 잡아야 한다 —
    75~106 µm 에서는 실리콘이 제약이고, 폴리머만 보면 여유비를 과대평가한다.
    """
    d = cfg["density"]
    cu = vt_in_field(d["구리"], max(lo_um, SIZE_RANGE_UM["구리"][0]) * 1e-6, accel)
    worst, who = 0.0, ""
    for name, (dlo, dhi) in SIZE_RANGE_UM.items():
        if name == "구리":
            continue
        dd = min(hi_um, dhi)
        if dd < max(lo_um, dlo):
            continue
        v = vt_in_field(d[name], dd * 1e-6, accel)
        if v > worst:
            worst, who = v, f"{name}@{dd:.0f}µm"
    return cu, worst, who


def wheel_area(cfg=CONFIG):
    return 2.0 * math.pi * cfg["wheel_radius_m"] * cfg["wheel_height_m"]


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
    for tag, lo, hi, _key, rpm, v_r in cfg["classifiers"]:
        a = centrifugal_acceleration(rpm, cfg["wheel_radius_m"])
        d_si = _diameter_at_field_velocity(d["실리콘(+Ag)"], v_r, a) * 1e6
        print(f"  {tag} {lo:3d}~{hi:3d} µm (v_r {v_r:.2f} m/s, a/g={a/G:.1f}): "
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
    print("8. 터보(디플렉터 휠) 분급기 — 밀도 선별")
    print("=" * 76)
    A = wheel_area(cfg)
    print(f"  휠 Ø{cfg['wheel_radius_m']*2000:.0f} mm × h{cfg['wheel_height_m']*1000:.0f} mm"
          f"  ->  원통면적 {A:.4f} m2\n")
    total_q = 0.0
    for tag, lo, hi, key, rpm, v_r in cfg["classifiers"]:
        a = centrifugal_acceleration(rpm, cfg["wheel_radius_m"])
        cu, worst, who = separation_bounds(lo, hi, a, cfg)
        q = v_r * A * 3600
        total_q += q
        solids = peak * 1000 * cfg["split"][key]
        print(f"  {tag}  {lo:3d}~{hi:3d} µm  {rpm} rpm (a/g={a/G:.1f})")
        print(f"        구리 하한 {cu:5.2f} | 비구리 상한 {worst:5.2f} ({who}) "
              f"| 여유비 {cu/worst:.2f}")
        print(f"        v_r {v_r:.2f} m/s -> {q:4.0f} m3/h, 고형물 {solids:5.1f} kg/h, "
              f"부하 {solids/q:.3f} kg/m3")
    print(f"\n  분급기 풍량 합계 {total_q:.0f} m3/h  (+ 시브 커버 환기·집진 별도)")
    print("\n  ※ 원심장은 분리 여유비를 넓히지 않는다(오히려 미세하게 좁다).")
    print("     터보로 가는 이유는 중력식 지그재그가 이 입도에서 작동 범위 밖이고,")
    print("     회전수와 풍량 두 노브로 컷을 독립 조절할 수 있기 때문이다.")


if __name__ == "__main__":
    report()
