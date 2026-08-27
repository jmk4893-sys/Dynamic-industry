#!/usr/bin/env python3
"""원형 시브(SV-01) 체분리 거동 수치해석 — 0.5 mm 이하 불규칙 형상 입자.

기존 tools/classifier_sim.py 는 **에어분급**(종말속도)을 다룬다.
이 모듈은 그 앞단인 **체분리**(기하 입도)를 다루며, 두 가지가 핵심이다.

1. 입자가 구형이 아니다. 3축(L >= I >= S)으로 모델링한다.
   - 체는 **중간축 I** 를 잰다. 사각 개구를 통과하려면 I 가 개구보다 작아야 한다.
   - 편평한 입자는 데크 위에 **누워서** 흐르므로, 통과하려면 모로 서야 한다.
     이 배향 확률이 편평도(S/I)에 비례해 떨어진다 — 박편이 체질이 느린 이유다.
2. 근접입자(near-mesh)가 개구에 박혀 눈막힘을 만든다. 초음파는 이것을 떨어낸다.
   눈막힘은 개방면적을 줄여 효율을 지수적으로 깎는다.

    python3 tools/sieve_sim.py

주의 — 3축 비(SHAPE)는 **가정값**이며 이 해석에서 가장 불확실한 입력이다.
파일럿에서 형상 계수를 실측해야 한다(§10).
"""
import math
import numpy as np

# ── 물질별 3축 비 (가정 — 실측 필요) ────────────────────────────
# elongation = I/L, flatness = S/I. gsd 는 각 비의 기하표준편차.
SHAPE = {
    "구리":       dict(elong=0.60, flat=0.50, gsd=1.25),  # 리본 파편
    "실리콘+은":  dict(elong=0.75, flat=0.60, gsd=1.20),  # 취성 각형 파편
    "백시트+EVA": dict(elong=0.70, flat=0.35, gsd=1.30),  # 라미네이트 박편
    "EVA":        dict(elong=0.75, flat=0.45, gsd=1.30),  # 연성 덩어리
}

# 체 사양 — (개구 µm, 선경 µm). 선경은 시장 표준 평직 기준.
MESH = {200: 130.0, 106: 71.0, 75: 50.0}

# 통과 확률 모델 파라미터
ORIENT_EXP = 1.0        # 배향 확률 = (S/I)^ORIENT_EXP. 1.0 = 입체각 선형 근사
GAUDIN_EXP = 2.0        # 근접입자 감쇠 지수 ((a-I)/a)^GAUDIN_EXP
NEAR_MESH = (0.80, 1.30)  # 이 배수 구간의 입자가 개구에 박힌다

CONFIG = dict(
    peak_tph=0.35,
    vib_hz=16.0,            # 자이라토리 960 rpm
    residence_s=45.0,       # Ø1200 데크 위 평균 체류시간
    bed_layers=6.0,         # 베드 두께(입자층). 바닥층만 개구에 접한다
    # ── 눈막힘 속도상수 (보정값 — 1 원리 유도가 아니다) ──────────
    # 아래 셋은 이론에서 나온 값이 아니라, 잘 확립된 산업 사실
    #   "100 µm 이하 건식 체는 초음파 없이는 개방면적을 대부분 잃고,
    #    초음파를 걸면 데크 효율 85~95 % 를 유지한다"
    # 를 모델이 재현하도록 맞춘 것이다. 파일럿 실측 대상이다(§10).
    peg_rate=8.0e-3,        # 근접입자 1 회 제시당 박힘 확률
    ultrasonic_clear=0.25,  # 초음파 1 주기당 박힌 입자 이탈 확률
    passive_clear=5.0e-4,   # 볼 데크·타격만 있을 때의 이탈 확률
)


# ── 입자 생성 ────────────────────────────────────────────────────
def _norm_cdf(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def _norm_ppf(u):
    """정규분포 역CDF — Acklam 근사 대신 이분법(벡터화, 정밀도 충분)."""
    lo = np.full_like(u, -8.0)
    hi = np.full_like(u, 8.0)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        c = _norm_cdf(mid)
        lo = np.where(c < u, mid, lo)
        hi = np.where(c < u, hi, mid)
    return 0.5 * (lo + hi)


def truncated_lognormal(rng, median, gsd, lo_um, hi_um, n):
    """[lo, hi] 로 절단한 로그정규 표본 [µm]."""
    mu, sigma = math.log(median), math.log(gsd)
    a = _norm_cdf(np.array([(math.log(lo_um) - mu) / sigma]))[0]
    b = _norm_cdf(np.array([(math.log(hi_um) - mu) / sigma]))[0]
    u = rng.uniform(a, b, n)
    return np.exp(mu + sigma * _norm_ppf(u))


def sample_particles(rng, material, n, size_dist, basis="mass"):
    """3축 치수 [µm] 를 뽑는다. 주어진 입도분포는 **체분석**이므로 중간축 I 다.

    basis="mass" (기본) — SIZE_DIST 의 중앙값을 **질량 기준**으로 읽는다.
        체분석 결과는 관례상 질량 기준이므로 이것이 맞다. 질량 ∝ I³ 이므로
        개수 분포의 중앙값은 exp(3 σ²) 만큼 아래에 있다.
    basis="number" — 중앙값을 개수 기준으로 읽는다(과거 거동, 비교용).

    각 재질의 실제 존재 범위(MATERIALS 의 d_lo/d_hi)로 절단한다 —
    절단하지 않으면 실리콘이 200 µm 위까지 생겨 데크 부하가 왜곡된다.
    """
    from classifier_sim import MATERIALS
    d = size_dist[material]
    m = MATERIALS[material]
    median = d["median"]
    if basis == "mass":
        sigma = math.log(d["gsd"])
        median = median * math.exp(-3.0 * sigma * sigma)
    I = truncated_lognormal(rng, median, d["gsd"],
                            m["d_lo"] * 1e6, m["d_hi"] * 1e6, n)
    sh = SHAPE[material]
    ls = math.log(sh["gsd"])
    elong = np.clip(rng.lognormal(math.log(sh["elong"]), ls, n), 0.15, 0.99)
    flat = np.clip(rng.lognormal(math.log(sh["flat"]), ls, n), 0.05, 0.99)
    L = I / elong
    S = I * flat
    return L, I, S


# ── 통과 확률 ────────────────────────────────────────────────────
def open_area_fraction(aperture_um, wire_um):
    """평직 체의 개방면적비."""
    return (aperture_um / (aperture_um + wire_um)) ** 2


def passage_probability(I, S, aperture_um, wire_um, blinded=0.0,
                        orient_exp=ORIENT_EXP, gaudin_exp=GAUDIN_EXP):
    """1 회 제시당 통과 확률.

    세 항의 곱이다.
      개방면적비 x (1 - 눈막힘)  — 개구에 닿을 확률
      ((a - I)/a)^2             — Gaudin. 개구에 가까울수록 급격히 낮아진다
      (S/I)^orient_exp          — 배향. 편평한 입자는 모로 서야 통과한다
    """
    I = np.asarray(I, dtype=float)
    S = np.asarray(S, dtype=float)
    f = open_area_fraction(aperture_um, wire_um) * (1.0 - blinded)
    geom = np.where(I < aperture_um,
                    np.clip((aperture_um - I) / aperture_um, 0.0, 1.0) ** gaudin_exp,
                    0.0)
    orient = np.clip(S / I, 0.0, 1.0) ** orient_exp
    return f * geom * orient


def presentations(cfg=CONFIG):
    """체류 중 한 입자가 개구에 제시되는 유효 횟수."""
    return cfg["vib_hz"] * cfg["residence_s"] / cfg["bed_layers"]


# ── 눈막힘 ───────────────────────────────────────────────────────
def near_mesh_mass_fraction(I, mass, aperture_um, band=NEAR_MESH):
    """근접입자(개구의 0.8~1.3 배)의 질량비 — 눈막힘의 원인 물질."""
    lo, hi = band
    sel = (I >= lo * aperture_um) & (I <= hi * aperture_um)
    tot = mass.sum()
    return float(mass[sel].sum() / tot) if tot > 0 else 0.0


def blinded_steady_state(near_mesh_frac, ultrasonic, cfg=CONFIG):
    """정상상태 눈막힘 면적비.

    박힘 = peg_rate x 근접입자 비율,  이탈 = clear_rate.
    B = peg / (peg + clear) 로 수렴한다.
    """
    peg = cfg["peg_rate"] * near_mesh_frac * cfg["vib_hz"]
    clear = (cfg["ultrasonic_clear"] if ultrasonic else cfg["passive_clear"]) * cfg["vib_hz"]
    return peg / (peg + clear) if (peg + clear) > 0 else 0.0


# ── 데크 1 단 ────────────────────────────────────────────────────
def screen_deck(L, I, S, mass, aperture_um, wire_um, ultrasonic=True,
                cfg=CONFIG, orient_exp=ORIENT_EXP):
    """한 데크를 통과시킨다. (통과 여부 bool 배열, 진단 dict) 반환."""
    nm = near_mesh_mass_fraction(I, mass, aperture_um)
    B = blinded_steady_state(nm, ultrasonic, cfg)
    p = passage_probability(I, S, aperture_um, wire_um, blinded=B,
                            orient_exp=orient_exp)
    n = presentations(cfg)
    passed_prob = 1.0 - (1.0 - p) ** n
    return passed_prob, dict(near_mesh=nm, blinded=B, presentations=n,
                             open_area=open_area_fraction(aperture_um, wire_um))


# ── 3 메쉬 캐스케이드 ────────────────────────────────────────────
DECKS = [200, 106, 75]


def build_feed(rng, n_per_material, composition, size_dist, basis="mass"):
    """물질별 입자를 뽑고 질량을 계산한다. 부피는 삼축 타원체로 근사."""
    from classifier_sim import MATERIALS
    mats, Ls, Is, Ss, ms = [], [], [], [], []
    for name, wfrac in composition.items():
        L, I, S = sample_particles(rng, name, n_per_material, size_dist, basis)
        rho = MATERIALS[name]["rho"]
        vol = math.pi / 6.0 * L * I * S * 1e-18          # m3
        m = vol * rho
        m = m / m.sum() * wfrac                          # 조성비에 맞춰 정규화
        mats.append(np.full(n_per_material, name))
        Ls.append(L); Is.append(I); Ss.append(S); ms.append(m)
    return (np.concatenate(mats), np.concatenate(Ls),
            np.concatenate(Is), np.concatenate(Ss), np.concatenate(ms))


def cascade(rng=None, ultrasonic=True, cfg=CONFIG, orient_exp=ORIENT_EXP,
            n_per_material=6000, composition=None, size_dist=None, seed=0,
            basis="mass", decks=None):
    """3 메쉬 + PAN 을 통과시켜 분획별 물질 질량표를 만든다.

    데크는 위에서부터 걸러진다. 어떤 데크의 O/S 는 그 분획의 제품이 되고,
    U/S 만 다음 데크로 내려간다.
    """
    from classifier_sim import COMPOSITION, SIZE_DIST
    composition = composition or COMPOSITION
    size_dist = size_dist or SIZE_DIST
    rng = rng or np.random.default_rng(seed)
    mats, L, I, S, mass = build_feed(rng, n_per_material, composition,
                                     size_dist, basis)

    remaining = mass.copy()          # 아직 아래로 내려가는 질량
    fractions, diag = {}, {}
    for aperture in (decks or DECKS):
        wire = MESH.get(aperture, 0.65 * aperture)
        p_pass, d = screen_deck(L, I, S, remaining, aperture, wire,
                                ultrasonic=ultrasonic, cfg=cfg,
                                orient_exp=orient_exp)
        through = remaining * p_pass
        over = remaining - through
        fractions[f"+{aperture}"] = over
        diag[aperture] = d
        remaining = through
    fractions["PAN"] = remaining
    return dict(mats=mats, L=L, I=I, S=S, mass=mass,
                fractions=fractions, diag=diag)


def summarise(res, composition=None):
    """분획 x 물질 질량표와 주요 회수율."""
    from classifier_sim import COMPOSITION
    composition = composition or COMPOSITION
    mats = res["mats"]
    table = {}
    for fk, fm in res["fractions"].items():
        table[fk] = {m: float(fm[mats == m].sum()) for m in composition}
    total = {m: float(res["mass"][mats == m].sum()) for m in composition}
    return table, total


# ── 분급 물리 (벡터화) ───────────────────────────────────────────
RHO_AIR, MU_AIR = 1.2, 1.81e-5


def vt_field_vec(rho, d_m, accel, iters=80):
    """가속도장 accel 에서의 종말속도 [m/s] — Schiller-Naumann, numpy 벡터화.

    screen_sizing.vt_in_field 와 같은 식이다. 회로 평가에서 입자마다
    파이썬 루프를 돌리지 않기 위한 벡터판.
    """
    rho = np.asarray(rho, float); d_m = np.asarray(d_m, float)
    v = np.full(np.broadcast(rho, d_m).shape, 1e-3)
    for _ in range(iters):
        re = np.maximum(RHO_AIR * v * d_m / MU_AIR, 1e-12)
        cd = np.where(re < 0.1, 24.0 / re,
                      24.0 / re * (1.0 + 0.15 * re ** 0.687)
                      + 0.42 / (1.0 + 42500.0 * re ** -1.16))
        v = np.sqrt(4.0 * accel * d_m * (rho - RHO_AIR) / (3.0 * cd * RHO_AIR))
    return v


def classify(mats, L, I, S, v_cut, accel=9.81):
    """분급기 통과 판정 — 재질 이름이 아니라 종말속도로 가른다.

    입자 형상은 부피등가 구경 d_eq = (L·I·S)^(1/3) 로만 반영한다(1차 근사).
    반환: heavy(bool 배열) — 종말속도가 커트보다 커서 중량측으로 가는 입자.
    """
    from classifier_sim import MATERIALS
    rho = np.array([MATERIALS[m]["rho"] for m in mats], float)
    d_eq = np.cbrt(L * I * S) * 1e-6
    return vt_field_vec(rho, d_eq, accel) > v_cut


# ── 전체 회로 (SV-01 → TC-01 → SS-01) ───────────────────────────
def circuit(ultrasonic=True, ss01=True, cfg=CONFIG, n_per_material=6000,
            seed=0, orient_exp=ORIENT_EXP, basis="mass", decks=None,
            v_cut=None, accel=9.81):
    """Rev.4 회로 전체의 제품별 회수율을 체 거동 모델로 직접 계산한다.

    설계서 §6.7 은 데크 효율 90 % 를 **가정**했다. 여기서는 그 값을
    형상·근접입자·눈막힘 모델에서 계산해 검증한다.

    분급기는 종말속도 물리(classify)로 가른다 — 과거의 재질 오라클
    (구리면 중량측)은 분급기를 완전하다고 가정하는 것이라 폐기했다.
    v_cut/accel 로 운전점을 지정하며, 기본은 중력장 + 밴드 기하평균.
    """
    from classifier_sim import COMPOSITION, SIZE_DIST
    decks = decks or DECKS
    r = cascade(ultrasonic=ultrasonic, cfg=cfg, n_per_material=n_per_material,
                seed=seed, orient_exp=orient_exp, basis=basis, decks=decks)
    mats, L, I, S = r["mats"], r["L"], r["I"], r["S"]
    fr = r["fractions"]

    p1 = fr["PAN"].copy()                        # SV-01 언더 → P1 직행
    p3 = fr[f"+{decks[0]}"].copy()               # 최상단 오버 → P3 직행
    to_tc = sum(fr[f"+{a}"] for a in decks[1:])  # 중간 분획 → 분급기

    # 분급기 — 재질 오라클이 아니라 종말속도 물리로 가른다.
    # v_cut 미지정 시 분리 밴드(비구리 상한~구리 하한)의 기하평균.
    if v_cut is None:
        import screen_sizing as ssz
        cu_lo, non_hi, _ = ssz.separation_bounds(decks[-1], decks[0], accel)
        v_cut = math.sqrt(cu_lo * non_hi)
    heavy = classify(mats, L, I, S, v_cut, accel)
    p2 = np.where(heavy, to_tc, 0.0)             # 중량측 → P2 구리
    light = np.where(~heavy, to_tc, 0.0)         # 경량측 → SS-01 또는 P3

    ss_diag = None
    if ss01:
        p_pass, ss_diag = screen_deck(L, I, S, light, 75, MESH[75],
                                      ultrasonic=ultrasonic, cfg=cfg,
                                      orient_exp=orient_exp)
        p1 = p1 + light * p_pass
        p3 = p3 + light * (1.0 - p_pass)
    else:
        p3 = p3 + light

    out = {}
    for name in COMPOSITION:
        sel = mats == name
        tot = r["mass"][sel].sum()
        out[name] = dict(P1=float(p1[sel].sum() / tot),
                         P2=float(p2[sel].sum() / tot),
                         P3=float(p3[sel].sum() / tot))
    streams = dict(P1=float(p1.sum()), P2=float(p2.sum()), P3=float(p3.sum()))
    return dict(recovery=out, streams=streams, deck=r["diag"], ss01=ss_diag)


def report(decks=(250, 106, 75), n_per_material=12000):
    from classifier_sim import COMPOSITION
    decks = list(decks)
    print("=" * 76)
    print("1. 체 사양 — 개방면적비와 유효 제시 횟수")
    print("=" * 76)
    for a in decks:
        w = MESH.get(a, 0.65 * a)
        print(f"  {a:3d} µm (선경 {w:5.1f} µm): 개방면적 {open_area_fraction(a, w)*100:5.1f} %")
    print(f"  가진 {CONFIG['vib_hz']:.0f} Hz x 체류 {CONFIG['residence_s']:.0f} s / 베드 "
          f"{CONFIG['bed_layers']:.0f}층 = 유효 제시 {presentations():.0f} 회")

    print()
    print("=" * 76)
    print("2. 분획 x 물질 질량표 [공급 대비 %] — 초음파 ON")
    print("=" * 76)
    r = cascade(decks=decks, n_per_material=n_per_material)
    tbl, tot = summarise(r)
    names = list(COMPOSITION)
    print(f"{'분획':>7} " + "".join(f"{m:>13}" for m in names) + f"{'합계':>10}")
    for fk, row in tbl.items():
        print(f"{fk:>7} " + "".join(f"{row[m]*100:12.2f}%" for m in names)
              + f"{sum(row.values())*100:9.2f}%")

    print()
    print("=" * 76)
    print("3. 데크별 근접입자와 눈막힘")
    print("=" * 76)
    for us in (True, False):
        rr = cascade(decks=decks, ultrasonic=us, n_per_material=n_per_material)
        tag = "초음파 ON " if us else "초음파 OFF"
        cells = "  ".join(f"{a}: 근접 {d['near_mesh']*100:4.1f}% 막힘 {d['blinded']*100:5.1f}%"
                          for a, d in rr["diag"].items())
        print(f"  {tag} | {cells}")

    print()
    print("=" * 76)
    print("4. 회로 전체 회수율 [%]")
    print("=" * 76)
    for us in (True, False):
        for s01 in (True, False):
            c = circuit(decks=decks, ultrasonic=us, ss01=s01,
                        n_per_material=n_per_material)
            print(f"  초음파 {'ON ' if us else 'OFF'} / SS-01 {'있음' if s01 else '없음'}: "
                  + "  ".join(f"{m} P{('1' if m != '구리' else '2')} "
                              f"{c['recovery'][m]['P1' if m != '구리' else 'P2']*100:5.1f}"
                              for m in ("구리", "실리콘+은")))

    print()
    print("=" * 76)
    print("5. 상단 데크 개구 선정 — 근접입자 구리가 상단에서 버려진다")
    print("=" * 76)
    for top in (200, 250, 300, 355):
        c = circuit(decks=[top, 106, 75], n_per_material=n_per_material // 2)
        print(f"  상단 {top:3d} µm: 구리 P2 {c['recovery']['구리']['P2']*100:5.1f} %  "
              f"P3 로 유실 {c['recovery']['구리']['P3']*100:5.1f} %")


if __name__ == "__main__":
    report()
