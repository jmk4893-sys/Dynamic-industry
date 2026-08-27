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


def simulate(column, rho_p, d, u_super, n=400, dt=2e-4, t_max=6.0,
             seed=0, turbulence=True, record=None):
    """입자군을 컬럼 중단에 투입하고 상단(경량) / 하단(중량) 도달을 판정한다.

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

    g_eff = -G * (1.0 - RHO_AIR / rho)                 # 부력 보정 중력(아래 방향 음수)
    sigma = column.turbulence_rms(u_super) if turbulence else 0.0
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
    "실리콘+은":  dict(median=45.0,  gsd=1.55),
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
