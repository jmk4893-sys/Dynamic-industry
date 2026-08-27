#!/usr/bin/env python3
"""미립(35~500 µm) 하이브리드 분리 라인 사이징 계산기.

docs/multi-stage-screen-design.md 의 수치를 재현·재산출한다.
실측치가 확보되면 CONFIG 만 고쳐서 다시 돌리면 된다.

    python3 tools/screen_sizing.py

Rev.4 — 목적함수가 품위에서 **회수율**로 바뀌었다. 제품은 3개
        (실리콘+은 / 구리 / 백시트)이고, 은은 실리콘과 결합된 상태 그대로 받는다.
        분급기를 2대 → 1대(75~200 µm 합류)로 합치고, 경량측 스캘핑 시브를 신설해
        은 회수율을 90 → 99 % 로 올렸다. 106 µm 데크는 밴드가 아니라
        75 µm 데크의 부하를 덜기 위해 남긴다.
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
    # Rev.5 — 상단 데크 250 µm (§6.8: 200 은 근접입자 구리를 15 % 유실)
    "sieve_decks": [(250, 0.50), (106, 0.30), (75, 0.20)],
    "sieve_area_factor": 0.90,
    # Rev.6 — 터보(디플렉터 휠) 폐기. 이 컷에서는 반경방향 풍속이 휠
    # 주속을 넘어(v_r/ωR ≈ 1.7, rpm 을 올리면 악화) 컷 조건의 전제인
    # 동반회전 자체가 성립하지 않는다(§6.4). 균일류 향류 컬럼으로 교체.
    "column": dict(tag="CC-01", lo_um=75, hi_um=250, v_super=0.82,
                   id_m=0.45, loading_kgm3=0.30),
    # (구식·이력용) 휠 기하 — §6.5 의 정정 서사 재현에만 쓰인다
    "wheel_radius_m": 0.075,
    "wheel_height_m": 0.095,
    # 구리의 공급물 중 질량비 (가정 — 체분석으로 검증할 것)
    "cu_mass_fraction": 0.09,
    # 체 효율 — sieve_sim.circuit 의 계산값으로 맞춘 등가 효율 (§6.7)
    "deck_efficiency": 0.872,        # 실리콘이 PAN 까지 도달하는 비율
    "scalp_efficiency": 0.275,       # SS-01 이 유실분에서 되찾는 비율
    # 회로 성적 — tools/sieve_sim.py circuit() (Rev.6: 형상 반영 분급,
    # v_cut 0.82 m/s, 전제 정합 실리콘 분포, 시드 3 평균). 간이 수지의
    # 기본값은 이 정밀 계산을 재현하도록 맞춘다.
    "classifier_cu_recovery": 0.969,
    "classifier_cu_grade": 0.949,
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


def sieve_area(diameter_m, cfg=CONFIG):
    """원형 시브의 유효 체면적 [m2]. 프레임·클램프 손실을 계수로 반영."""
    return math.pi * (diameter_m / 2.0) ** 2 * cfg["sieve_area_factor"]


def _mass_fraction_below(aperture_um, cfg=CONFIG):
    """공급물 중 aperture 미만의 질량비.

    분획표(split)의 경계(75/106/200/500)와 다른 개구는 해당 빈 안에서
    로그균등으로 보간한다 — 예: 250 µm 는 200~500 빈의 ln(250/200)/ln(500/200)
    = 24.4 % 를 추가로 통과시킨다.
    """
    sp = cfg["split"]
    edges = [(75, sp["<75"]), (106, sp["75~106"]), (200, sp["106~200"]),
             (500, sp["200~500"])]
    lo, acc = 35.0, 0.0
    for hi, frac in edges:
        if aperture_um >= hi:
            acc += frac
        elif aperture_um > lo:
            acc += frac * math.log(aperture_um / lo) / math.log(hi / lo)
            break
        else:
            break
        lo = hi
    return acc


def deck_loads(cfg=CONFIG, tph=None):
    """SV-01 각 데크의 통과부하 [kg/h] 와 소요면적 [m2].

    데크는 위에서부터 걸러지므로, 어떤 데크의 통과부하는
    '그 위 데크를 빠져나온 양' 이다. 106 µm 데크를 빼면
    75 µm 데크의 부하가 그만큼 늘어난다 — 은 회수의 병목이 여기다.
    """
    feed = (tph if tph is not None else cfg["peak_tph"]) * 1000.0
    out = []
    remaining = feed
    for aperture, capacity in cfg["sieve_decks"]:
        out.append((aperture, remaining, remaining / (capacity * 1000.0)))
        remaining = _mass_fraction_below(aperture, cfg) * feed
    return out


def three_product_balance(cfg=CONFIG, tph=None, deck_eff=None, scalp_eff=None):
    """3제품(실리콘+은 / 구리 / 백시트) 물질수지와 회수율 [kg/h].

    Rev.4 의 목적함수는 품위가 아니라 회수율이므로, 설계 성적을
    분급기 품위가 아니라 제품별 회수율로 직접 계산한다.

    75 µm 데크를 빠져나가지 못한 미분은 분급기로 넘어가 **경량측**으로 간다
    (75 µm 실리콘의 원심 종말속도가 커트의 1/4 수준이라 예외가 없다).
    그래서 은 손실은 구리가 아니라 백시트 제품으로 나가며,
    경량측에 스캘핑 시브를 걸면 되돌릴 수 있다.
    """
    feed = (tph if tph is not None else cfg["peak_tph"]) * 1000.0
    sp = cfg["split"]
    eta = cfg["deck_efficiency"] if deck_eff is None else deck_eff
    eta2 = cfg["scalp_efficiency"] if scalp_eff is None else scalp_eff

    fines = sp["<75"] * feed                    # 실리콘+은 전량
    misplaced = (1.0 - eta) * fines             # 데크를 못 빠져나간 미분
    copper = cfg["cu_mass_fraction"] * feed
    polymer = feed - fines - copper

    tc_feed = (sp["106~200"] + sp["75~106"]) * feed + misplaced
    heavy_cu = copper * cfg["classifier_cu_recovery"]
    heavy = heavy_cu / cfg["classifier_cu_grade"]
    light = tc_feed - heavy
    recovered = eta2 * misplaced                # 스캘핑으로 되찾은 미분

    p1 = eta * fines + recovered
    p2 = heavy
    p3 = sp["200~500"] * feed + light - recovered
    return {
        "feed": feed, "tc_feed": tc_feed, "light": light,
        "P1_실리콘+은": p1, "P2_구리": p2, "P3_백시트": p3,
        "은_회수율": p1 / fines,
        "구리_회수율": heavy_cu / copper,
        "백시트_회수율": (sp["200~500"] * feed + light - misplaced) / polymer,
        "스캘핑_공급": light,
    }


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
    col = cfg["column"]
    d_si = diameter_at_vt(d["실리콘(+Ag)"], col["v_super"]) * 1e6
    print(f"  {col['tag']} {col['lo_um']}~{col['hi_um']} µm "
          f"(v {col['v_super']:.2f} m/s, 중력장): 실리콘 {d_si:5.1f} µm 이하 -> "
          f"경량측(은 손실), 초과 -> 중량측(구리 오염)")

    print()
    print("=" * 76)
    print(f"7. 원형 시브 소요면적 (최대 {peak*1000:.0f} kg/h)")
    print("=" * 76)
    need = 0.0
    caps = dict(cfg["sieve_decks"])
    for ap, load, area in deck_loads(cfg):
        need = max(need, area)
        print(f"  {ap:3d} µm 데크  통과부하={load:5.0f} kg/h  "
              f"능력={caps[ap]:.2f} t/h/m2 -> 소요 {area:.2f} m2")
    print(f"\n  지배 소요면적 = {need:.2f} m2")
    for dia in (1000, 1200, 1500):
        a = math.pi / 4 * (dia / 1000) ** 2 * cfg["sieve_area_factor"]
        print(f"    Ø{dia} mm -> 유효 {a:.2f} m2  (여유 {a/need*100-100:+.0f}%)")

    print()
    print("=" * 76)
    print("8. CC-01 균일류 향류 분급 컬럼 — 밀도 선별")
    print("=" * 76)
    col = cfg["column"]
    bal = three_product_balance(cfg)
    solids = peak * 1000 * (cfg["split"]["106~200"] + cfg["split"]["75~106"]
                            + _mass_fraction_below(col["hi_um"], cfg)
                            - _mass_fraction_below(200, cfg))
    q = solids / col["loading_kgm3"]
    area_col = q / 3600.0 / col["v_super"]
    dia = math.sqrt(4 * area_col / math.pi)
    re_d = RHO_A * col["v_super"] * col["id_m"] / MU
    print(f"  {col['tag']}  {col['lo_um']}~{col['hi_um']} µm  "
          f"v_super {col['v_super']:.2f} m/s (중력장)")
    print(f"        고형물 {solids:5.1f} kg/h, 부하 {col['loading_kgm3']:.2f} kg/m3 "
          f"-> 풍량 {q:4.0f} m3/h -> 소요 단면 {area_col:.3f} m2 (Ø{dia*1000:.0f} mm)")
    print(f"        Re_D = {re_d:,.0f} — 난류 평탄 프로파일. 정류격자(허니컴) 병용")
    print()
    print("  ※ 터보(디플렉터 휠)는 Rev.6 에서 폐기 — 이 컷에서는 v_r 이 휠")
    print("     주속을 넘어(220 rpm: v_r 3.0 vs ωR 1.7 m/s) 동반회전 전제가")
    print("     깨지고, rpm 을 올리면 비율이 더 나빠진다(§6.4).")
    print("  ※ 컬럼의 분리 밴드는 입자 형상에 걸려 있다 — 구형 가정이면 밴드가")
    print("     닫히고(여유비 0.96), 박편 형상을 반영하면 열린다(1.17).")
    print("     §10 형상 실측이 결정 게이트, 대안은 진동 에어테이블.")

    print()
    print("=" * 76)
    print("9. 3제품 물질수지 — 목적함수는 회수율이다 (출처: sieve_sim.circuit)")
    print("=" * 76)
    print(f"  공급 {bal['feed']:.1f} kg/h "
          f"(75 µm 데크 효율 {cfg['deck_efficiency']:.0%}, "
          f"스캘핑 효율 {cfg['scalp_efficiency']:.0%})\n")
    for k in ("P1_실리콘+은", "P2_구리", "P3_백시트"):
        print(f"  {k:14s} {bal[k]:7.1f} kg/h")
    print(f"\n  SS-01 스캘핑 공급 (CC-01 경량측) {bal['스캘핑_공급']:.1f} kg/h"
          f"  -> 소요면적 {bal['스캘핑_공급']/200.0:.2f} m2"
          f" (Ø900 유효 {sieve_area(0.9, cfg):.2f} m2)\n")
    for k in ("구리_회수율", "백시트_회수율", "은_회수율"):
        print(f"  {k:14s} {bal[k]*100:6.2f} %")
    without = three_product_balance(cfg, scalp_eff=0.0)["은_회수율"]
    print(f"\n  ※ 스캘핑 시브가 없으면 은 회수율은 {without*100:.1f} % 로 떨어진다.")
    print("     세 회수율 중 관리 대상은 은 하나이며, 전적으로 두 체의 효율에 달려 있다.")


if __name__ == "__main__":
    report()
