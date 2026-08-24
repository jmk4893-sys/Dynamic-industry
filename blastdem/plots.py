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
    pos_vals = ppv[ppv > 0]
    lo = max(float(pos_vals.min()) if pos_vals.size else hi / 1e4, hi / 1e4)
    lv = np.logspace(np.log10(lo), np.log10(hi), 24)
    cf = ax.tricontourf(tri, np.maximum(ppv, lv[0]), levels=lv, cmap="turbo",
                        norm=matplotlib.colors.LogNorm())
    cb = fig.colorbar(cf, ax=ax, label="PPV [mm/s]")
    for name, lim in REGULATION[:4]:
        try:
            cs = ax.tricontour(tri, np.maximum(ppv, lv[0]), levels=[lim],
                               colors="white", linewidths=1.1, linestyles="--")
            ax.clabel(cs, fmt=lambda x, n=name: (n if KO else f"{x:g}"), fontsize=7)
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
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 3.0 * nrow), squeeze=False)
    pos = result.surface_pos
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
