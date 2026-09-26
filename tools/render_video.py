#!/usr/bin/env python3
"""향류 컬럼 입자 거동 영상 렌더러.

classifier_sim 의 물리(항력·중력·난류·벽충돌)를 그대로 쓰되, 궤적을 프레임으로
기록해 MP4 로 출력한다. 좌우 패널은 같은 풍속에서 공급물만 다르게 두어
'입도 분급을 먼저 하느냐'가 분리를 결정한다는 것을 직접 보인다.

    python3 tools/render_video.py [출력경로]
"""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Polygon, Rectangle
import imageio_ffmpeg
import classifier_sim as cs

for cand in ("WenQuanYi Zen Hei", "Noto Sans CJK KR", "NanumGothic"):
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams.update({"axes.unicode_minus": False, "font.size": 9})

BG, INK, MUTED, LINE = "#0C1214", "#E3EAE9", "#8B9F9E", "#2A3639"
COLOR = {"구리": "#C87E3E", "실리콘+은": "#C85B96", "백시트+EVA": "#2E8FCF", "EVA": "#2E8FCF"}

U_SUPER = 1.70          # m/s — 106~200 µm 분획의 최적 커트 (수치 스윕 결과)
N_PART = 460
DT, T_MAX, STRIDE, FPS = 1.0e-3, 5.0, 20, 30


def sample_feed(n, d_lo_um, d_hi_um, rng):
    """조성·입도분포에서 입자를 표본추출. [d_lo, d_hi] 밖은 버린다(=사전 분급)."""
    names, probs = zip(*cs.COMPOSITION.items())
    probs = np.array(probs, float); probs /= probs.sum()
    mat, dia, rho = [], [], []
    guard = 0
    while len(mat) < n and guard < n * 400:
        guard += 1
        nm = rng.choice(names, p=probs)
        p, m = cs.SIZE_DIST[nm], cs.MATERIALS[nm]
        d = rng.lognormal(np.log(p["median"]), np.log(p["gsd"]))
        if not (m["d_lo"] * 1e6 <= d <= m["d_hi"] * 1e6):
            continue
        if not (d_lo_um <= d <= d_hi_um):
            continue
        mat.append(nm); dia.append(d * 1e-6); rho.append(float(m["rho"]))
    return np.array(mat), np.array(dia), np.array(rho)


def run(column, mat, dia, rho, u_super, seed=3):
    """물리 적분 + 프레임 기록. 배출된 입자는 상·하 수집조에 주차시킨다."""
    rng = np.random.default_rng(seed)
    n = len(dia)
    x = column.W * (0.30 + 0.40 * rng.random(n))
    y = column.height * (0.46 + 0.08 * rng.random(n))
    vx = np.zeros(n); vy = np.zeros(n)
    g_eff = -cs.G * (1.0 - cs.RHO_AIR / rho)
    sigma = column.turbulence_rms(u_super)
    eddy_life = 0.02
    fluct = rng.normal(0, sigma, size=(2, n)); t_eddy = rng.random(n) * eddy_life
    top = np.zeros(n, bool); bot = np.zeros(n, bool)
    park = np.zeros((2, n))
    frames = []

    for step in range(int(T_MAX / DT)):
        live = ~(top | bot)
        if live.any():
            renew = t_eddy <= 0
            if renew.any():
                fluct[:, renew] = rng.normal(0, sigma, size=(2, int(renew.sum())))
                t_eddy[renew] = eddy_life
            t_eddy -= DT
            ux, uy = column.gas_velocity(x, y, u_super)
            ux, uy = ux + fluct[0], uy + fluct[1]
            tau = cs.drag_relaxation_time(rho, dia, np.hypot(vx - ux, vy - uy))
            e = np.exp(-DT / tau)
            vxn = ux + (vx - ux) * e
            vyn = uy + (vy - uy) * e + tau * g_eff * (1.0 - e)
            x = np.where(live, x + 0.5 * (vx + vxn) * DT, x)
            y = np.where(live, y + 0.5 * (vy + vyn) * DT, y)
            vx, vy = np.where(live, vxn, vx), np.where(live, vyn, vy)
            hl, hr = x < 0, x > column.W
            x = np.where(hl, -x, x); x = np.where(hr, 2 * column.W - x, x)
            vx = np.where(hl | hr, -0.3 * vx, vx)

            nt = live & (y >= column.height); nb = live & (y <= 0)
            for m_, ybase in ((nt, column.height), (nb, -0.0)):
                if m_.any():
                    k = int(m_.sum())
                    park[0, m_] = column.W * (0.08 + 0.84 * rng.random(k))
                    off = column.H * 0.42 * rng.random(k)
                    park[1, m_] = ybase + off if ybase > 0 else -off - column.H * 0.06
            top |= nt; bot |= nb
            x = np.where(top | bot, park[0], x)
            y = np.where(top | bot, park[1], y)

        if step % STRIDE == 0:
            frames.append((x.copy(), y.copy(), top.copy(), bot.copy(), step * DT))
    return frames


def draw_panel(ax, column, title, subtitle):
    ax.set_facecolor(BG)
    ax.set_xlim(-0.02, column.W + 0.02)
    ax.set_ylim(-column.H * 0.90, column.height + column.H * 0.92)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    # 지그재그 벽
    for i in range(column.n):
        y0, y1 = i * column.H, (i + 1) * column.H
        left = 0.0 if i % 2 == 0 else column.W * 0.30
        right = column.W * 0.70 if i % 2 == 0 else column.W
        ax.add_patch(Polygon([[left, y0], [right, y0], [right, y1], [left, y1]],
                             closed=True, fc="none", ec=LINE, lw=1.0, zorder=1))
    ax.add_patch(Rectangle((0, 0), column.W, column.height, fc="none",
                           ec=MUTED, lw=1.4, zorder=2))
    ax.add_patch(Rectangle((0, column.height), column.W, column.H * 0.5,
                           fc="#161E21", ec=LINE, lw=1.0, zorder=1))
    ax.add_patch(Rectangle((0, -column.H * 0.5), column.W, column.H * 0.5,
                           fc="#161E21", ec=LINE, lw=1.0, zorder=1))
    ax.text(column.W / 2, column.height + column.H * 0.66, "경량측 배출 (상단)",
            color=MUTED, fontsize=8.5, ha="center", zorder=6)
    ax.text(column.W / 2, -column.H * 0.76, "중량측 배출 (하단)",
            color=MUTED, fontsize=8.5, ha="center", zorder=6)
    ax.set_title(title, color=INK, fontsize=11.5, pad=20, loc="left")
    ax.text(0, 1.005, subtitle, transform=ax.transAxes, color=MUTED,
            fontsize=8.5, va="bottom")


def main(out="sim_out/classifier.mp4"):
    col = cs.ZigZagColumn()
    rng = np.random.default_rng(2)
    cases = [
        ("미분급 공급  75~500 µm", "입도 분급 없이 그대로 투입", (75.0, 500.0)),
        ("분급 후 공급  106~200 µm", "원형 시브로 먼저 분급한 분획", (106.0, 200.0)),
    ]
    runs = []
    for title, sub, (lo, hi) in cases:
        mat, dia, rho = sample_feed(N_PART, lo, hi, rng)
        print(f"  {title}: 입자 {len(mat)}개 "
              f"(구리 {(mat=='구리').sum()}, 폴리머 "
              f"{((mat=='EVA')|(mat=='백시트+EVA')).sum()}, 실리콘 {(mat=='실리콘+은').sum()})")
        runs.append((title, sub, mat, dia, rho, run(col, mat, dia, rho, U_SUPER)))

    n_frames = min(len(r[5]) for r in runs)
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 6.4), facecolor=BG)
    fig.subplots_adjust(left=0.04, right=0.96, top=0.76, bottom=0.11, wspace=0.14)
    fig.suptitle("향류 에어분급 — 입도 분급을 먼저 하느냐가 분리를 결정한다",
                 color=INK, fontsize=14, x=0.04, ha="left", y=0.965)
    fig.text(0.04, 0.905, f"두 패널 모두 같은 풍속 u = {U_SUPER:.2f} m/s. "
             "차이는 공급물의 입도 폭뿐이다.", color=MUTED, fontsize=9.5, ha="left")
    hud = []
    scats = []
    for ax, (title, sub, mat, dia, rho, fr) in zip(axes, runs):
        draw_panel(ax, col, title, sub)
        cols = np.array([COLOR[m] for m in mat])
        sizes = np.clip((dia * 1e6) ** 1.5 / 22.0, 5, 90)
        sc = ax.scatter(fr[0][0], fr[0][1], s=sizes, c=cols, alpha=0.9,
                        linewidths=0, zorder=5)
        scats.append((sc, cols, sizes, mat))
        hud.append(ax.text(0.02, -0.055, "", transform=ax.transAxes, color=INK,
                           fontsize=9.5, va="top"))
    for x0, c, lab in ((0.040, "#C87E3E", "구리"),
                       (0.115, "#2E8FCF", "백시트 · EVA"),
                       (0.235, "#C85B96", "실리콘 + 은")):
        fig.text(x0, 0.858, "\u25cf", color=c, fontsize=11, ha="left", va="center")
        fig.text(x0 + 0.016, 0.858, lab, color=MUTED, fontsize=9.5,
                 ha="left", va="center")
    clock = fig.text(0.96, 0.905, "", color=MUTED, fontsize=9.5, ha="right",
                     family="monospace")

    w, h = fig.canvas.get_width_height()
    writer = imageio_ffmpeg.write_frames(out, (w, h), fps=FPS, quality=8,
                                         macro_block_size=1)
    writer.send(None)
    for k in range(n_frames):
        for (sc, cols, sizes, mat), (title, sub, m2, d2, r2, fr) , h_ in zip(
                scats, runs, hud):
            x, y, top, bot, t = fr[k]
            sc.set_offsets(np.c_[x, y])
            done = top | bot
            a = np.where(done, 0.55, 0.95)
            rgba = np.array([matplotlib.colors.to_rgba(c) for c in cols])
            rgba[:, 3] = a
            sc.set_facecolors(rgba)
            cu = mat == "구리"
            cu_bot = (cu & bot).sum(); cu_all = max(cu.sum(), 1)
            heavy = bot.sum()
            grade = (cu & bot).sum() / heavy * 100 if heavy else 0.0
            h_.set_text(f"구리 회수 {cu_bot/cu_all*100:5.1f} %   "
                        f"중량측 구리 품위 {grade:5.1f} %")
        clock.set_text(f"t = {fr[k][4]:4.2f} s")
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
        writer.send(np.ascontiguousarray(buf))
    writer.close()
    plt.close(fig)
    print(f"  -> {out}")
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sim_out/classifier.mp4")
