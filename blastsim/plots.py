"""결과 시각화. 한글 폰트가 없는 환경에서는 자동으로 영문 라벨로 대체된다."""

from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.tri import Triangulation

from .empirical import REGULATION, ScaledDistanceLaw
from .sensors import SensorRecord

_KO_CANDIDATES = [
    "Malgun Gothic", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic",
    "Noto Sans CJK KR", "Noto Sans KR", "Source Han Sans KR", "WenQuanYi Zen Hei",
]


def _setup_font() -> bool:
    """사용 가능한 한글 폰트를 찾아 설정. 성공하면 True."""
    have = {f.name for f in fm.fontManager.ttflist}
    for name in _KO_CANDIDATES:
        if name in have:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return True
    return False


KO = _setup_font()


def L(ko: str, en: str) -> str:
    """한글 폰트 유무에 따른 라벨 선택."""
    return ko if KO else en


plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 140, "axes.grid": True,
                     "grid.alpha": 0.3, "font.size": 9})


# ---------------------------------------------------------------------------
def plot_ppv_distance(records: list[SensorRecord], charge: float,
                      laws: dict[str, ScaledDistanceLaw], path: str) -> None:
    """PPV-거리 감쇠곡선 + 경험식 + 규제기준."""
    d = np.array([r.distance for r in records])
    v = np.array([r.ppv for r in records])
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))

    dd = np.linspace(max(d.min() * 0.6, 1.0), d.max() * 1.4, 200)
    for name, law in laws.items():
        ax[0].plot(dd, law.ppv(dd, charge), "--", lw=1.2, label=str(law))
    ax[0].plot(d, v, "o-", color="crimson", lw=1.8, ms=6, label=L("DEM 해석", "DEM result"))
    for name, lim in REGULATION:
        ax[0].axhline(lim, color="gray", lw=0.7, ls=":")
        ax[0].text(dd[-1], lim, f" {name}" if KO else f" {lim:g}", va="bottom",
                   ha="right", fontsize=7, color="gray")
    ax[0].set_xscale("log"); ax[0].set_yscale("log")
    ax[0].set_xlabel(L("이격거리 D [m]", "Distance D [m]"))
    ax[0].set_ylabel("PPV [mm/s]")
    ax[0].set_title(L("거리에 따른 진동 감쇠", "PPV attenuation"))
    ax[0].legend(fontsize=7, loc="upper right")

    sd = d / charge ** 0.5
    ax[1].loglog(sd, v, "o", color="crimson", ms=7, label=L("DEM 해석", "DEM"))
    if len(sd) > 2:
        s, i = np.polyfit(np.log10(sd), np.log10(v), 1)
        xs = np.linspace(sd.min(), sd.max(), 50)
        ax[1].plot(xs, 10 ** i * xs ** s, "-", color="navy", lw=1.6,
                   label=f"K={10 ** i / 10:.0f}, n={-s:.2f}")
    for name, law in laws.items():
        ax[1].plot(np.sort(sd), law.ppv(np.sort(sd) * charge ** 0.5, charge), "--", lw=1.0,
                   label=name)
    ax[1].set_xlabel(L("자승근 환산거리 D/√W [m/kg^0.5]", "Scaled distance D/√W"))
    ax[1].set_ylabel("PPV [mm/s]")
    ax[1].set_title(L("환산거리 회귀", "Scaled-distance regression"))
    ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def plot_waveforms(records: list[SensorRecord], path: str, max_n: int = 5) -> None:
    """속도 시간이력 (3성분)."""
    recs = records[:max_n]
    fig, axes = plt.subplots(len(recs), 1, figsize=(9, 1.7 * len(recs)), sharex=True)
    axes = np.atleast_1d(axes)
    comp = [L("방사 Vx", "Vx"), L("접선 Vy", "Vy"), L("연직 Vz", "Vz")]
    for ax, r in zip(axes, recs):
        for c, (lab, col) in enumerate(zip(comp, ["#c0392b", "#27ae60", "#2980b9"])):
            ax.plot(r.time * 1000, r.velocity[:, c] * 1000, lw=0.8, color=col, label=lab)
        ax.set_ylabel("mm/s")
        ax.text(0.99, 0.92, f"{r.name}  D={r.distance:.0f}m  PPV={r.ppv:.2f} mm/s  "
                            f"f={r.dominant_frequency:.0f}Hz",
                transform=ax.transAxes, ha="right", va="top", fontsize=8,
                bbox=dict(fc="white", ec="none", alpha=0.7))
    axes[0].legend(ncol=3, fontsize=7, loc="upper left")
    axes[-1].set_xlabel(L("시간 [ms]", "Time [ms]"))
    fig.suptitle(L("계측점 속도 시간이력", "Velocity time histories"), fontsize=10)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def plot_spectra(records: list[SensorRecord], path: str, max_n: int = 5) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4))
    drawn = 0
    for r in records[:max_n]:
        f, a = r.spectrum()
        m = (f > 0) & (f < 300)
        peak = float(a[m].max()) if m.any() else 0.0
        if peak <= 0:                      # 신호가 없거나 기록이 너무 짧은 경우
            continue
        ax.plot(f[m], a[m] / peak, lw=1.1, label=f"{r.name} ({r.distance:.0f}m)")
        drawn += 1
    if drawn == 0:
        plt.close(fig)
        return
    ax.set_xlabel(L("주파수 [Hz]", "Frequency [Hz]"))
    ax.set_ylabel(L("정규화 진폭", "Normalized amplitude"))
    ax.set_title(L("진동 주파수 스펙트럼", "Vibration spectra"))
    ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def _surface_tri(pos: np.ndarray) -> Triangulation:
    return Triangulation(pos[:, 0], pos[:, 1])


def plot_surface_ppv(result, pattern, records: list[SensorRecord], path: str) -> None:
    """지표면 PPV 분포도 + 천공 배치 + 계측점."""
    pos, ppv = result.surface_pos, result.surface_ppv * 1000.0
    fig, ax = plt.subplots(figsize=(8, 6.2))
    tri = _surface_tri(pos)
    hi = float(ppv.max())
    if not np.isfinite(hi) or hi <= 0:      # 진동이 지표에 도달하지 않은 경우
        plt.close(fig)
        return
    lo = hi / 300.0                      # 표시 동적범위 약 2.5 decade
    lv = np.logspace(np.log10(lo), np.log10(hi), 24)
    cf = ax.tricontourf(tri, np.clip(ppv, lv[0], lv[-1]), levels=lv, cmap="turbo",
                        norm=matplotlib.colors.LogNorm(vmin=lo, vmax=hi))
    cb = fig.colorbar(cf, ax=ax, label="PPV [mm/s]", shrink=0.85)
    ticks = [t for t in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
             if lo <= t <= hi]
    if len(ticks) >= 2:
        cb.set_ticks(ticks)
        cb.set_ticklabels([f"{t:g}" for t in ticks])
    # 규제기준 등고선 — 해석 범위 안에 드는 기준만
    for name, lim in REGULATION:
        if not (lv[0] < lim < hi):
            continue
        try:
            cs = ax.tricontour(tri, np.clip(ppv, lv[0], lv[-1]), levels=[lim],
                               colors="white", linewidths=1.4, linestyles="--")
            ax.clabel(cs, fmt=lambda x, n=name: (f"{n} {x:g}" if KO else f"{x:g}"),
                      fontsize=7, colors="white")
        except Exception:
            pass
    hp = pattern.positions()
    ax.plot(hp[:, 0], hp[:, 1], "kv", ms=6, mfc="white", label=L("발파공", "Blastholes"))
    sp = np.array([r.position for r in records])
    ax.plot(sp[:, 0], sp[:, 1], "w*", ms=11, mec="k", label=L("계측점", "Sensors"))
    ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]"); ax.set_aspect("equal")
    ax.set_title(L("지표면 최대입자속도(PPV) 분포", "Surface PPV distribution"))
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def plot_snapshots(result, pattern, path: str) -> None:
    """파면 전파 스냅샷."""
    snaps = result.snapshots
    if not snaps:
        return
    ts = sorted(snaps)
    ncol = min(4, len(ts)); nrow = int(np.ceil(len(ts) / ncol))
    pos = result.surface_pos
    ar = (pos[:, 1].max() - pos[:, 1].min()) / max(pos[:, 0].max() - pos[:, 0].min(), 1e-9)
    w = 3.4
    fig, axes = plt.subplots(nrow, ncol, figsize=(w * ncol, w * ar * nrow + 0.6),
                             squeeze=False)
    tri = _surface_tri(pos)
    vmax = max(float(s.max()) for s in snaps.values()) * 1000.0
    if not np.isfinite(vmax) or vmax <= 0:
        plt.close(fig)
        return
    hp = pattern.positions()
    for k, t in enumerate(ts):
        ax = axes[k // ncol][k % ncol]
        val = snaps[t] * 1000.0
        ax.tricontourf(tri, val, levels=np.linspace(0, vmax, 20), cmap="turbo")
        ax.plot(hp[:, 0], hp[:, 1], "kv", ms=3)
        ax.set_title(f"t = {t * 1000:.0f} ms", fontsize=9)
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for k in range(len(ts), nrow * ncol):
        axes[k // ncol][k % ncol].axis("off")
    fig.suptitle(L("지표 진동파 전파 (|v|)", "Surface wave propagation |v|"), fontsize=10)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def plot_layout(lattice, pattern, records: list[SensorRecord], path: str) -> None:
    """3D 모델 배치도."""
    fig = plt.figure(figsize=(9, 6.5))
    ax = fig.add_subplot(111, projection="3d")
    x0, x1, y0, y1, dz = lattice.x0, lattice.x1, lattice.y0, lattice.y1, lattice.depth
    for zs in (0.0, -dz):
        ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], [zs] * 5, color="gray", lw=0.8)
    for xx, yy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ax.plot([xx, xx], [yy, yy], [0, -dz], color="gray", lw=0.8)

    for h in pattern.holes:
        ax.plot([h.x, h.x], [h.y, h.y], [h.z_collar, h.charge_top], color="0.55", lw=1.4)
        ax.plot([h.x, h.x], [h.y, h.y], [h.charge_top, h.z_bottom], color="crimson", lw=3.0)
    ax.plot([], [], color="crimson", lw=3, label=L("장약부", "Charge"))
    ax.plot([], [], color="0.55", lw=1.5, label=L("전색부", "Stemming"))

    sp = np.array([r.position for r in records])
    ax.scatter(sp[:, 0], sp[:, 1], sp[:, 2] + 0.5, c="royalblue", marker="*", s=90,
               label=L("계측점", "Sensors"), depthshade=False)
    ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]"); ax.set_zlabel("Z [m]")
    ax.set_title(L("해석 모델 배치 (발파공 · 계측점)", "Model layout"))
    ax.legend(fontsize=8, loc="upper left")
    ax.view_init(elev=24, azim=-58)
    try:
        ax.set_box_aspect((x1 - x0, y1 - y0, dz * 2.2))
    except Exception:
        pass
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def plot_source(explosive, source, path: str) -> None:
    """공내압 시간이력과 스펙트럼."""
    t = np.linspace(0, 20e-3, 3000)
    p = explosive.pressure_history(t) * source.hole_pressure[0] / 1e6
    fig, ax = plt.subplots(1, 2, figsize=(9.5, 3.4))
    ax[0].plot(t * 1000, p, color="darkorange", lw=1.6)
    ax[0].set_xlabel(L("시간 [ms]", "Time [ms]"))
    ax[0].set_ylabel(L("등가공동 압력 [MPa]", "Cavity pressure [MPa]"))
    ax[0].set_title(f"{explosive.name}" if KO else "Source pressure")
    amp = np.abs(np.fft.rfft(p)); fr = np.fft.rfftfreq(t.size, t[1] - t[0])
    m = fr < 800
    ax[1].plot(fr[m], amp[m] / amp[m].max(), color="darkorange", lw=1.4)
    ax[1].set_xlabel(L("주파수 [Hz]", "Frequency [Hz]"))
    ax[1].set_ylabel(L("정규화 진폭", "Normalized"))
    ax[1].set_title(L("폭원 주파수 특성", "Source spectrum"))
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


# ---------------------------------------------------------------------------
def plot_fragmentation(result, stats: dict, path: str) -> None:
    """파쇄 입도 분포 (누적통과율 + Rosin-Rammler 회귀)."""
    size = stats["size_sorted"]
    cum = stats["cum"]
    if size.size < 2:
        return
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.2))

    ax[0].semilogx(size, cum * 100, "o-", ms=3, lw=1.4, color="tab:blue",
                   label=L("DEM 해석", "DEM"))
    xs = np.logspace(np.log10(max(size.min(), 1e-3)), np.log10(size.max()), 120)
    rr = 1.0 - np.exp(-((xs / max(stats["Xc"], 1e-6)) ** stats["n_rr"]))
    ax[0].semilogx(xs, rr * 100, "--", lw=1.3, color="tab:red",
                   label=f"Rosin-Rammler  Xc={stats['Xc']:.2f} m, n={stats['n_rr']:.2f}")
    for frac, key, col in ((50, "X50", "0.4"), (80, "X80", "0.6")):
        ax[0].axhline(frac, color=col, lw=0.7, ls=":")
        ax[0].axvline(stats[key], color=col, lw=0.7, ls=":")
        ax[0].text(stats[key], 3, f" {key}={stats[key]:.2f}m", fontsize=7, color="0.3")
    ax[0].set_xlabel(L("파쇄체 등가입경 [m]", "Fragment size [m]"))
    ax[0].set_ylabel(L("누적 통과율 [%]", "Cumulative passing [%]"))
    ax[0].set_title(L("파쇄 입도 분포", "Fragment size distribution"))
    ax[0].set_ylim(0, 100)
    ax[0].legend(fontsize=7, loc="upper left")

    v = result.peak_speed
    v = v[v > 0.1]
    if v.size:
        ax[1].hist(v, bins=50, color="tab:orange", edgecolor="none")
        ax[1].axvline(20.0, color="crimson", lw=1.2, ls="--")
        ax[1].text(20.0, ax[1].get_ylim()[1] * 0.9,
                   L(" 비산 기준 20 m/s", " flyrock 20 m/s"), fontsize=7, color="crimson")
    ax[1].set_yscale("log")
    ax[1].set_xlabel(L("입자 최대속도 [m/s]", "Peak particle speed [m/s]"))
    ax[1].set_ylabel(L("입자 수", "count"))
    ax[1].set_title(L(f"속도 분포 (최대 {stats['v_max']:.0f} m/s, "
                      f"비산거리 {stats['flyrock_range']:.0f} m)",
                      "Speed distribution"))
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def plot_muckpile(result, path: str) -> None:
    """발파 전후 측면도 — 저항선 이동과 파쇄암 적재 형상."""
    p0, p1 = result.pos0, result.pos
    disp = np.linalg.norm(p1 - p0, axis=1)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True, sharey=True)

    ax[0].scatter(p0[:, 0], p0[:, 2], s=3, c="0.55", linewidths=0)
    ax[0].set_title(L("발파 전", "Before"))
    sc = ax[1].scatter(p1[:, 0], p1[:, 2], s=3, c=disp, cmap="viridis", linewidths=0)
    ax[1].set_title(L("발파 후 (색 = 이동거리)", "After (color = displacement)"))
    fig.colorbar(sc, ax=ax[1], label=L("이동거리 [m]", "displacement [m]"), shrink=0.85)

    for a in ax:
        a.axvline(result.face_x, color="tab:cyan", lw=1.1, ls="--")
        a.axhline(result.toe_z, color="tab:cyan", lw=1.1, ls="--")
        a.axhline(0.0, color="0.6", lw=0.8)
        a.set_aspect("equal")
        a.set_xlabel("X [m]")
    ax[0].set_ylabel("Z [m]")
    fig.suptitle(L("파쇄암 이동 및 적재 (측면도, 자유면 방향 →)",
                   "Muckpile (side view)"), fontsize=10)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
