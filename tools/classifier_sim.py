#!/usr/bin/env python3
"""향류 공기분급기 라그랑지안 입자 추적 solver (물리 엔진 코어).

폐태양광 미립(35~500 µm) 스트림의 구리/폴리머/실리콘 분리를 수치해석한다.

물리:
  m dv/dt = m g (1 - rho_a/rho_p) - (m/tau) (v - u)
  tau = rho_p d^2 / (18 mu) / (1 + 0.15 Re^0.687)      (Schiller-Naumann 보정 완화시간)
  Re  = rho_a |v - u| d / mu

시간적분은 항력항에 대해 지수적분기(exponential integrator)를 쓴다. 미립에서 tau 가
매우 작아 명시적 오일러는 stiff 해지지만, 지수적분기는 dt >> tau 에서도 무조건 안정하다.

    v(t+dt) = u + (v - u) exp(-dt/tau) + tau g' (1 - exp(-dt/tau))

난류는 이산 무작위 보행(DRW): 에디 수명 동안 고정된 가우시안 변동을 더한다.
"""
from __future__ import annotations
import math
import numpy as np

# ── 물성 ─────────────────────────────────────────────────────────
RHO_AIR = 1.2          # kg/m3
MU = 1.81e-5           # Pa·s
G = 9.81               # m/s2

MATERIALS = {
    "구리":        dict(rho=8960, d_lo=75e-6,  d_hi=200e-6, key="cu"),
    "실리콘+은":   dict(rho=2500, d_lo=20e-6,  d_hi=120e-6, key="si"),
    "백시트+EVA":  dict(rho=1200, d_lo=75e-6,  d_hi=500e-6, key="bs"),
    "EVA":         dict(rho=950,  d_lo=75e-6,  d_hi=500e-6, key="eva"),
}


def drag_relaxation_time(rho_p, d, v_rel):
    """Schiller-Naumann 보정 입자 완화시간 [s]. v_rel 은 상대속도 크기."""
    re = RHO_AIR * np.abs(v_rel) * d / MU
    tau_stokes = rho_p * d * d / (18.0 * MU)
    return tau_stokes / (1.0 + 0.15 * np.power(np.maximum(re, 1e-12), 0.687))


def terminal_velocity(rho_p, d, iters=200):
    """정지 공기 중 종말속도 [m/s] — 해석적 수렴해. solver 검증 기준."""
    v = 1e-3
    for _ in range(iters):
        tau = drag_relaxation_time(rho_p, d, v)
        v = tau * G * (1.0 - RHO_AIR / rho_p)
    return v


class ZigZagColumn:
    """지그재그 향류 컬럼의 기하와 유동장.

    폭 W, 단 높이 H_seg, 단수 n_seg. 각 단에서 기류는 벽면을 따라 사선으로 꺾이며,
    이 편향이 입자를 반복 재분급시켜 분리 정확도를 높인다(지그재그의 원리).
    """

    def __init__(self, width=0.20, seg_height=0.12, n_seg=6, angle_deg=30.0):
        self.W = width
        self.H = seg_height
        self.n = n_seg
        self.angle = math.radians(angle_deg)
        self.height = seg_height * n_seg

    def gas_velocity(self, x, y, u_super):
        """(x, y) 에서의 기류 속도 벡터 [m/s]. u_super 는 겉보기 상승속도."""
        seg = np.floor(y / self.H).astype(int)
        sign = np.where(seg % 2 == 0, 1.0, -1.0)          # 단마다 좌우 교대
        # 벽 근처에서 사선 성분이 강해지고 중앙에서 약해진다
        xi = np.clip(x / self.W, 0.0, 1.0)
        lateral = sign * np.sin(math.pi * xi) * math.tan(self.angle)
        # 벽면 무활조건 근사: 포물선 분포로 중앙이 빠르다
        prof = 1.5 * (1.0 - (2.0 * xi - 1.0) ** 2)
        uy = u_super * np.maximum(prof, 0.15)
        ux = u_super * lateral * 0.5
        return ux, uy

    def turbulence_rms(self, u_super):
        """난류 변동 강도 [m/s]. 지그재그는 편향으로 난류도가 높다(~20 %)."""
        return 0.20 * u_super


class UniformCell:
    """균일 유동 분리 셀 — 터보 분급기의 휠 외주 조건.

    ZigZagColumn 은 포물선 분포(중심속도 = 겉보기의 1.5배)를 갖는 중력 컬럼이라
    '겉보기 풍속'과 '입자가 겪는 국소 속도'가 다르다. 터보 분급기의 분급은 휠 외주에서
    일어나고 거기서 반경방향 풍속 v_r 은 균일하므로, 설계값이 곧 국소값이다.
    이 클래스를 써야 설계식(v_r)과 수치해석이 같은 양을 가리킨다.
    """

    def __init__(self, width=0.20, height=0.40, turbulence_intensity=0.20):
        self.W = width
        self.H = height
        self.height = height
        self.n = 1
        self._ti = turbulence_intensity

    def gas_velocity(self, x, y, u_super):
        return np.zeros_like(np.asarray(x, dtype=float)), np.full_like(
            np.asarray(y, dtype=float), u_super)

    def turbulence_rms(self, u_super):
        return self._ti * u_super


def simulate(column, rho_p, d, u_super, n=400, dt=2e-4, t_max=6.0,
             seed=0, turbulence=True, record=None, accel=None, sigma_abs=None):
    """입자군을 컬럼 중단에 투입하고 상단(경량) / 하단(중량) 도달을 판정한다.

    accel 을 주면 중력 대신 그 가속도장(원심 분급기의 omega^2 R)에서 푼다.
    sigma_abs 를 주면 난류 변동을 풍속 비례가 아니라 절대값으로 고정한다 —
    같은 기계 난류에서 분리력만 키웠을 때의 효과를 보려면 이쪽을 쓴다.

    반환: (입자별 상단배출 bool 배열, 입자별 탈출시각)
    record 가 dict 이면 궤적을 기록한다(영상용).
    """
    rng = np.random.default_rng(seed)
    d = np.broadcast_to(np.asarray(d, dtype=float), (n,)).copy()
    rho = np.broadcast_to(np.asarray(rho_p, dtype=float), (n,)).copy()

    x = column.W * (0.35 + 0.30 * rng.random(n))
    y = np.full(n, column.height * 0.5)
    vx = np.zeros(n)
    vy = np.zeros(n)

    body_accel = G if accel is None else accel         # 원심장이면 omega^2 R 을 넣는다
    g_eff = -body_accel * (1.0 - RHO_AIR / rho)        # 부력 보정 체적력(분리 방향 음수)
    if not turbulence:
        sigma = 0.0
    elif sigma_abs is not None:
        sigma = sigma_abs                              # 기계 고유 난류(절대값)
    else:
        sigma = column.turbulence_rms(u_super)
    eddy_life = 0.02
    fluct = rng.normal(0.0, sigma, size=(2, n)) if turbulence else np.zeros((2, n))
    t_eddy = rng.random(n) * eddy_life

    exited_top = np.zeros(n, dtype=bool)
    exited_bot = np.zeros(n, dtype=bool)
    t_exit = np.full(n, np.nan)

    steps = int(t_max / dt)
    t = 0.0
    for step in range(steps):
        live = ~(exited_top | exited_bot)
        if not live.any():
            break

        if turbulence:
            renew = t_eddy <= 0
            if renew.any():
                fluct[:, renew] = rng.normal(0.0, sigma, size=(2, renew.sum()))
                t_eddy[renew] = eddy_life
            t_eddy -= dt

        ux, uy = column.gas_velocity(x, y, u_super)
        ux = ux + fluct[0]
        uy = uy + fluct[1]

        v_rel = np.hypot(vx - ux, vy - uy)
        tau = drag_relaxation_time(rho, d, v_rel)
        e = np.exp(-dt / tau)

        vx_new = ux + (vx - ux) * e
        vy_new = uy + (vy - uy) * e + tau * g_eff * (1.0 - e)

        x = x + 0.5 * (vx + vx_new) * dt
        y = y + 0.5 * (vy + vy_new) * dt
        vx, vy = vx_new, vy_new

        # 벽 충돌: 반발계수 0.3, 접선 성분은 유지
        hit_l = x < 0.0
        hit_r = x > column.W
        x = np.where(hit_l, -x, x)
        x = np.where(hit_r, 2 * column.W - x, x)
        vx = np.where(hit_l | hit_r, -0.3 * vx, vx)

        t += dt
        newly_top = live & (y >= column.height)
        newly_bot = live & (y <= 0.0)
        t_exit[newly_top | newly_bot] = t
        exited_top |= newly_top
        exited_bot |= newly_bot

        if record is not None and step % record["stride"] == 0:
            record["frames"].append((x.copy(), y.copy(),
                                     (exited_top | exited_bot).copy()))

    # 미탈출 입자는 최종 위치로 귀속(체류)
    stuck = ~(exited_top | exited_bot)
    exited_top |= stuck & (y > column.height * 0.5)

    return exited_top, t_exit


def _self_test():
    """정지 공기(u=0, 무난류)에서 solver 가 해석적 종말속도로 수렴하는지 확인."""
    print("solver 검증 — 정지 공기 중 종말속도 [m/s]")
    print(f"{'물질':12s}{'입경':>8s}{'해석해':>10s}{'수치해':>10s}{'오차':>9s}")
    ok = True
    for name, m in MATERIALS.items():
        for d in (50e-6, 100e-6, 200e-6):
            v_ref = terminal_velocity(m["rho"], d)
            # 자유낙하 적분: 충분히 긴 시간 뒤 속도
            v, dt = 0.0, 1e-5
            for _ in range(200000):
                tau = drag_relaxation_time(m["rho"], d, v)
                e = math.exp(-dt / tau)
                v = v * e + tau * G * (1.0 - RHO_AIR / m["rho"]) * (1.0 - e)
            err = abs(v - v_ref) / v_ref
            ok &= err < 1e-3
            print(f"{name:12s}{d*1e6:7.0f}µ{v_ref:10.4f}{v:10.4f}{err*100:8.3f}%")
    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    _self_test()

# ══════════════════════════════════════════════════════════════════
#  수치 실험
# ══════════════════════════════════════════════════════════════════

COMPOSITION = {"EVA": 0.33, "백시트+EVA": 0.26, "실리콘+은": 0.32, "구리": 0.09}

SIZE_DIST = {                       # 절단 로그정규 (중앙값 µm, 기하표준편차)
    "구리":       dict(median=120.0, gsd=1.35),
    # Rev.6 — §1 전제("75 µm 이하에 질량 95 % 이상")와 정합하도록 재보정.
    # 종전 (45, 1.55) 는 절단 후 <75 µm 질량이 88 % 라 전제와 모순이었고,
    # 그 모순이 은 회수율을 9 포인트 깎아 내렸다.
    "실리콘+은":  dict(median=38.0,  gsd=1.5),
    "백시트+EVA": dict(median=230.0, gsd=1.60),
    "EVA":        dict(median=230.0, gsd=1.60),
}

GRID_UM = np.array([20, 30, 40, 55, 75, 90, 106, 130, 160, 200, 260, 340, 430, 500.0])


def _lognorm_cdf(x_um, name):
    p = SIZE_DIST[name]
    from math import log, erf, sqrt
    mu, s = log(p["median"]), log(p["gsd"])
    return 0.5 * (1 + math.erf((math.log(x_um) - mu) / (s * math.sqrt(2))))


def bin_mass(name, lo_um, hi_um):
    """재질 name 의 질량 중 [lo, hi) µm 에 드는 비율(재질 내 정규화)."""
    m = MATERIALS[name]
    lo = max(lo_um, m["d_lo"] * 1e6)
    hi = min(hi_um, m["d_hi"] * 1e6)
    if hi <= lo:
        return 0.0
    total = _lognorm_cdf(m["d_hi"] * 1e6, name) - _lognorm_cdf(m["d_lo"] * 1e6, name)
    return (_lognorm_cdf(hi, name) - _lognorm_cdf(lo, name)) / max(total, 1e-12)


def build_population(grid_um, n_per_bin):
    rho, dia, mat, idx = [], [], [], []
    for name, m in MATERIALS.items():
        for j, d_um in enumerate(grid_um):
            if not (m["d_lo"] * 1e6 <= d_um <= m["d_hi"] * 1e6):
                continue
            rho.append(np.full(n_per_bin, float(m["rho"])))
            dia.append(np.full(n_per_bin, d_um * 1e-6))
            mat.append(np.full(n_per_bin, name))
            idx.append(np.full(n_per_bin, j))
    return (np.concatenate(rho), np.concatenate(dia),
            np.concatenate(mat), np.concatenate(idx))


def partition_table(column, grid_um, velocities, n_per_bin=120, dt=1e-3,
                    t_max=5.0, seed=1, verbose=True):
    """P[(재질, 입경격자)] = 상단(경량측)으로 나갈 확률, 풍속별."""
    rho, dia, mat, idx = build_population(grid_um, n_per_bin)
    if verbose:
        print(f"  입자 {len(rho):,}개 × 풍속 {len(velocities)}점")
    out = {}
    for u in velocities:
        top, _ = simulate(column, rho, dia, u, n=len(rho), dt=dt,
                          t_max=t_max, seed=seed)
        tab = {}
        for name in MATERIALS:
            sel_m = mat == name
            for j in range(len(grid_um)):
                sel = sel_m & (idx == j)
                if sel.any():
                    tab[(name, j)] = float(top[sel].mean())
        out[u] = tab
        if verbose:
            print(f"    u={u:.2f} m/s  상단배출 전체 {top.mean()*100:5.1f} %")
    return out


def evaluate(tab, grid_um, class_lo, class_hi):
    """한 입도 분획에 대해 중량측(하단) 산물의 구리 회수율/품위를 계산한다."""
    heavy = {}   # 재질별 하단으로 간 질량 (공급 전체 대비)
    feed = {}
    for name, comp in COMPOSITION.items():
        h = f = 0.0
        for j, d_um in enumerate(grid_um):
            lo = grid_um[j - 1] if j > 0 else grid_um[0]
            hi = grid_um[j + 1] if j < len(grid_um) - 1 else grid_um[-1]
            lo_e, hi_e = math.sqrt(lo * d_um), math.sqrt(d_um * hi)
            lo_e, hi_e = max(lo_e, class_lo), min(hi_e, class_hi)
            if hi_e <= lo_e:
                continue
            w = comp * bin_mass(name, lo_e, hi_e)
            f += w
            p_top = tab.get((name, j))
            if p_top is None:
                continue
            h += w * (1.0 - p_top)
        heavy[name], feed[name] = h, f
    tot_h = sum(heavy.values())
    cu_rec = heavy["구리"] / feed["구리"] if feed["구리"] > 0 else float("nan")
    cu_grade = heavy["구리"] / tot_h if tot_h > 0 else float("nan")
    poly_rem = 1.0 - ((heavy["EVA"] + heavy["백시트+EVA"]) /
                      max(feed["EVA"] + feed["백시트+EVA"], 1e-12))
    return dict(cu_recovery=cu_rec, cu_grade=cu_grade, poly_removal=poly_rem,
                heavy_mass=tot_h, feed_mass=sum(feed.values()))


def d50_and_sharpness(tab, grid_um, name):
    """한 재질의 분배곡선에서 d50 과 예리도(d25/d75)를 구한다."""
    d = np.array([g for j, g in enumerate(grid_um) if (name, j) in tab])
    p_bot = np.array([1.0 - tab[(name, j)] for j, g in enumerate(grid_um)
                      if (name, j) in tab])
    if len(d) < 3 or p_bot.max() < 0.75 or p_bot.min() > 0.25:
        return float("nan"), float("nan")
    f = lambda q: float(np.interp(q, p_bot, d))
    d25, d50, d75 = f(0.25), f(0.50), f(0.75)
    return d50, (d25 / d75 if d75 > 0 else float("nan"))


def sweep(column=None, velocities=None, n_per_bin=200, seed=1, verbose=True):
    """풍속 스윕 → 시나리오별 구리 회수율/품위/폴리머 제거율."""
    column = column or ZigZagColumn()
    if velocities is None:
        velocities = np.round(np.arange(0.20, 3.01, 0.10), 2)
    tabs = partition_table(column, GRID_UM, velocities, n_per_bin=n_per_bin,
                           seed=seed, verbose=verbose)
    scenarios = {
        "미분급 75~500 µm": (75.0, 500.0),
        "분획 75~106 µm":   (75.0, 106.0),
        "분획 106~200 µm":  (106.0, 200.0),
    }
    results = {k: [] for k in scenarios}
    for u in velocities:
        for k, (lo, hi) in scenarios.items():
            r = evaluate(tabs[u], GRID_UM, lo, hi)
            r["u"] = float(u)
            results[k].append(r)
    return velocities, results, tabs


def best_point(rows, min_recovery=0.85):
    """회수율 하한을 만족하는 점 중 품위 최대. 없으면 회수율×품위 최대."""
    ok = [r for r in rows if r["cu_recovery"] >= min_recovery]
    pool = ok if ok else rows
    key = (lambda r: r["cu_grade"]) if ok else (lambda r: r["cu_recovery"] * r["cu_grade"])
    return max(pool, key=key)


# ══════════════════════════════════════════════════════════════════
#  응집 모델
# ══════════════════════════════════════════════════════════════════
#
# 지금까지의 해석은 입자를 서로 독립인 구로 두었다. 실제로는 Bo ≈ 1 부근에서
# 부착력이 자중을 이기므로 응집체가 생기고, 응집체는 '구성 입자들의 평균 밀도'로
# 거동한다. 구리가 폴리머 응집체에 갇히면 경량측으로 가고(회수율 손실),
# 폴리머가 구리에 붙으면 중량측으로 간다(품위 손실). 이것이 이상 모델의
# 낙관 편향을 만드는 주된 기전이다.
#
# 모델링 수준: 완전한 응집 DEM 대신, (1) Bo 로 부착 확률을 주고 (2) 프랙탈
# 응집체의 유효 입경·유효 밀도를 계산해 (3) 기존 solver 에 넣는다.
# 응집체 내부 투과유동(permeability)은 무시한다 — 이 때문에 응집체의 항력이
# 실제보다 조금 크게 잡히고, 결과는 여전히 낙관 쪽으로 치우친다.

HAMAKER_J = 6.5e-20
CONTACT_GAP_M = 4.0e-10
ASPERITY_R_M = 0.2e-6
FRACTAL_DIM = 2.4          # 건식 응집체의 통상 범위 2.2~2.5

# 재질별 부착력 배수 — EVA 는 연질·점착성이라 vdW 외에 소성접촉이 더해진다
TACKINESS = {"구리": 1.0, "실리콘+은": 1.0, "백시트+EVA": 2.0, "EVA": 3.0}


def adhesion_force(mat_a, mat_b):
    """두 입자 사이 부착력 [N]. 표면조도 보정이라 입경과 무관하다."""
    base = HAMAKER_J * ASPERITY_R_M / (6.0 * CONTACT_GAP_M ** 2)
    return base * math.sqrt(TACKINESS[mat_a] * TACKINESS[mat_b])


def particle_weight(rho, d):
    return math.pi / 6.0 * d ** 3 * rho * G


def bond(mat, rho, d):
    """표면조도 보정 Bond 수 = 부착력 / 자중."""
    return adhesion_force(mat, mat) / particle_weight(rho, d)


def aggregate_properties(diameters, densities):
    """프랙탈 응집체의 (유효 입경, 유효 밀도).

    고체 부피는 보존되고 포락 부피는 N^(3/Df) 로 커지므로
    rho_eff = rho_mass * N^(1 - 3/Df) 로 묽어진다.
    """
    d = np.asarray(diameters, dtype=float)
    rho = np.asarray(densities, dtype=float)
    n = len(d)
    vol = np.pi / 6.0 * d ** 3
    mass = vol * rho
    rho_mass = mass.sum() / vol.sum()                 # 질량가중 고체밀도
    d_solid = (6.0 * vol.sum() / np.pi) ** (1.0 / 3.0)  # 고체부피 등가경
    if n == 1:
        return float(d_solid), float(rho_mass)
    d_eff = d_solid * n ** (1.0 / FRACTAL_DIM - 1.0 / 3.0)
    rho_eff = rho_mass * n ** (1.0 - 3.0 / FRACTAL_DIM)
    return float(d_eff), float(rho_eff)


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _truncated_lognormal_massbasis(rng, median_mass, gsd, lo_um, hi_um, n):
    """질량기준 로그정규를 [lo, hi] 로 절단해 n 개 표본 [µm].

    SIZE_DIST 의 중앙값은 체분석(질량기준)이다. 여기서 뽑힌 입경은
    '질량 퀀텀'의 입경 — 입자 하나가 같은 질량을 대표하므로, 통계는
    개수 비율이 곧 질량 비율이다(중요도 표본추출).
    """
    mu, sigma = math.log(median_mass), math.log(gsd)
    a = _norm_cdf((math.log(lo_um) - mu) / sigma)
    b = _norm_cdf((math.log(hi_um) - mu) / sigma)
    u = rng.uniform(a, b, n)
    # 역CDF — 이분법 (벡터화)
    lo = np.full(n, -8.0); hi = np.full(n, 8.0)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        c = 0.5 * (1.0 + np.vectorize(math.erf)(mid / math.sqrt(2.0)))
        lo = np.where(c < u, mid, lo)
        hi = np.where(c < u, hi, mid)
    return np.exp(mu + sigma * 0.5 * (lo + hi))


def mass_fraction_in(name, lo_um, hi_um):
    """재질 name 의 전체 질량 중 [lo, hi]∩존재범위 에 드는 비율 (질량기준 CDF)."""
    m, p = MATERIALS[name], SIZE_DIST[name]
    mu, sigma = math.log(p["median"]), math.log(p["gsd"])
    a = max(lo_um, m["d_lo"] * 1e6)
    b = min(hi_um, m["d_hi"] * 1e6)
    if b <= a:
        return 0.0
    # 존재범위 절단 정규화
    fa = _norm_cdf((math.log(m["d_lo"] * 1e6) - mu) / sigma)
    fb = _norm_cdf((math.log(m["d_hi"] * 1e6) - mu) / sigma)
    ga = _norm_cdf((math.log(a) - mu) / sigma)
    gb = _norm_cdf((math.log(b) - mu) / sigma)
    return (gb - ga) / max(fb - fa, 1e-12)


def sample_primaries(rng, n, lo_um, hi_um):
    """분획 [lo, hi] 안의 1차 입자를 표본추출한다 — 등질량 퀀텀 방식.

    (Rev.6 정정) 종전에는 질량기준 중앙값으로 **개수기준** 표본을 뽑고
    뒤에서 d³ρ 로 다시 질량 가중했다 — 이중 가중으로 굵은 쪽이 부풀었다.
    지금은 질량기준 분포에서 직접 뽑고 입자마다 같은 질량을 대표시킨다.
    재질별 개수는 조성(질량비) × 분획 내 질량비율에 비례한다.
    """
    names = list(COMPOSITION)
    w = np.array([COMPOSITION[k] * mass_fraction_in(k, lo_um, hi_um)
                  for k in names], float)
    if w.sum() <= 0:
        return np.array([]), np.array([]), np.array([])
    w /= w.sum()
    counts = np.floor(w * n).astype(int)
    for _ in range(n - counts.sum()):          # 잔여를 큰 순으로 배분
        counts[np.argmax(w * n - counts)] += 1
    mats, dias, rhos = [], [], []
    for nm, cnt in zip(names, counts):
        if cnt == 0:
            continue
        m, p = MATERIALS[nm], SIZE_DIST[nm]
        a = max(lo_um, m["d_lo"] * 1e6)
        b = min(hi_um, m["d_hi"] * 1e6)
        d = _truncated_lognormal_massbasis(rng, p["median"], p["gsd"], a, b, cnt)
        mats.append(np.full(cnt, nm))
        dias.append(d * 1e-6)
        rhos.append(np.full(cnt, float(m["rho"])))
    order = rng.permutation(n)
    return (np.concatenate(mats)[order], np.concatenate(dias)[order],
            np.concatenate(rhos)[order])


def agglomerate(rng, mats, dias, rhos, dispersion_efficiency=0.0, max_size=8):
    """1차 입자를 응집체로 묶는다.

    부착 확률 = Bo/(1+Bo) × (1 - 분산기 효율).
    dispersion_efficiency = 1.0 이면 완전 분산(= 기존 이상 모델).

    반환: (응집체별 유효입경, 유효밀도, 1차입자 -> 응집체 index)
    """
    n = len(dias)
    order = rng.permutation(n)
    cluster_of = np.full(n, -1, dtype=int)
    clusters = []
    for i in order:
        bo = bond(mats[i], rhos[i], dias[i])
        p_stick = (bo / (1.0 + bo)) * (1.0 - dispersion_efficiency)
        open_c = [k for k, c in enumerate(clusters) if len(c) < max_size]
        if open_c and rng.random() < p_stick:
            k = open_c[rng.integers(len(open_c))]
            clusters[k].append(int(i))
            cluster_of[i] = k
        else:
            clusters.append([int(i)])
            cluster_of[i] = len(clusters) - 1
    agg_d = np.empty(len(clusters))
    agg_rho = np.empty(len(clusters))
    for k, c in enumerate(clusters):
        agg_d[k], agg_rho[k] = aggregate_properties(dias[c], rhos[c])
    return agg_d, agg_rho, cluster_of


def evaluate_with_agglomeration(cell, lo_um, hi_um, v_cut, accel, sigma_abs=0.20,
                                dispersion_efficiency=0.0, n_primary=3000,
                                seed=0, dt=1e-3, t_max=4.0):
    """응집을 반영한 구리 회수율/품위.

    응집체 단위로 분리되지만 성적은 1차 입자 질량 기준으로 집계한다 —
    폴리머 응집체에 갇힌 구리는 회수 실패로 계산된다.
    """
    rng = np.random.default_rng(seed)
    mats, dias, rhos = sample_primaries(rng, n_primary, lo_um, hi_um)
    agg_d, agg_rho, cluster_of = agglomerate(
        rng, mats, dias, rhos, dispersion_efficiency)
    top, _ = simulate(cell, agg_rho, agg_d, v_cut, n=len(agg_d), dt=dt,
                      t_max=t_max, seed=seed + 1, accel=accel, sigma_abs=sigma_abs)
    heavy = ~top[cluster_of]                       # 1차 입자별 중량측 여부
    # 등질량 퀀텀 — 개수 비율이 곧 질량 비율 (sample_primaries 참조)
    mass = np.ones(len(dias))
    is_cu = mats == "구리"
    cu_mass = mass[is_cu].sum()
    heavy_mass = mass[heavy].sum()
    cu_heavy = mass[is_cu & heavy].sum()
    sizes = np.bincount(cluster_of, minlength=len(agg_d))
    return dict(
        cu_recovery=cu_heavy / cu_mass if cu_mass > 0 else float("nan"),
        cu_grade=cu_heavy / heavy_mass if heavy_mass > 0 else float("nan"),
        mean_cluster=float(sizes.mean()),
        singlet_fraction=float((sizes == 1).sum() / len(sizes)),
        n_primary=len(mats), n_agg=len(agg_d),
    )


def add_oversize_leak(rng, mats, dias, rhos, mass_fraction,
                      lo_um=150.0, hi_um=250.0, material="백시트+EVA"):
    """체 이월을 모사한다 — 분획 상한을 넘는 폴리머가 분급기 공급물에 섞여 들어온다.

    체눈 파손·눈막힘·응집체가 포락 입경으로 체질되는 경우 모두 이 형태로 나타난다.
    mass_fraction 은 최종 공급물 질량 대비 이월분의 비율이다.
    """
    if mass_fraction <= 0.0:
        return mats, dias, rhos
    rho_leak = float(MATERIALS[material]["rho"])
    # 등질량 퀀텀 — 이월 질량비는 곧 이월 퀀텀 개수비
    n_leak = max(1, round(mass_fraction / (1.0 - mass_fraction) * len(dias)))
    p = SIZE_DIST[material]
    d_leak = _truncated_lognormal_massbasis(rng, p["median"], p["gsd"],
                                            lo_um, hi_um, n_leak) * 1e-6
    return (np.concatenate([mats, np.full(len(d_leak), material)]),
            np.concatenate([dias, d_leak]),
            np.concatenate([rhos, np.full(len(d_leak), rho_leak)]))


def evaluate_feed(cell, lo_um, hi_um, v_cut, accel, sigma_abs=0.20,
                  dispersion_efficiency=1.0, sieve_leak=0.0,
                  leak_range_um=(150.0, 250.0), n_primary=2500, seed=0,
                  dt=1e-3, t_max=4.0):
    """분급기 성능을 두 가지 불완전성과 함께 평가한다.

    dispersion_efficiency — 응집(§6.6). 1.0 이면 완전 분산.
    sieve_leak            — 체 이월(§6.3.1). 0.0 이면 완전한 체.

    성적은 1차 입자 질량 기준으로 집계한다.
    """
    rng = np.random.default_rng(seed)
    mats, dias, rhos = sample_primaries(rng, n_primary, lo_um, hi_um)
    n_native = len(dias)
    mats, dias, rhos = add_oversize_leak(rng, mats, dias, rhos, sieve_leak,
                                         *leak_range_um)
    n_leak = len(dias) - n_native
    agg_d, agg_rho, cluster_of = agglomerate(
        rng, mats, dias, rhos, dispersion_efficiency)
    top, _ = simulate(cell, agg_rho, agg_d, v_cut, n=len(agg_d), dt=dt,
                      t_max=t_max, seed=seed + 1, accel=accel, sigma_abs=sigma_abs)
    heavy = ~top[cluster_of]
    mass = np.ones(len(dias))                 # 등질량 퀀텀
    is_cu = mats == "구리"
    cu_mass, heavy_mass = mass[is_cu].sum(), mass[heavy].sum()
    cu_heavy = mass[is_cu & heavy].sum()
    return dict(
        cu_recovery=cu_heavy / cu_mass if cu_mass > 0 else float("nan"),
        cu_grade=cu_heavy / heavy_mass if heavy_mass > 0 else float("nan"),
        # 주입된 이월분만 계상 — 분획 안의 원생 백시트와 구분한다
        leak_mass_fraction=float(n_leak / len(dias)) if sieve_leak else 0.0,
    )
