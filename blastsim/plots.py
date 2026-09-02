"""결과 시각화. 한글 폰트가 없는 환경에서는 자동으로 영문 라벨로 대체된다."""

from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import ticker
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
    ax[0].plot(d, v, "o-", color="crimson", lw=1.8, ms=6, label=L("FDM 해석", "FDM result"))
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
    ax[1].loglog(sd, v, "o", color="crimson", ms=7, label=L("FDM 해석", "FDM"))
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
    """파쇄 입도 분포 — Kuz-Ram 경험모델을 주곡선으로, DEM 연결성분은 참고로.

    DEM 본드망의 연결성분으로 덩어리를 세는 것은 본드 퍼콜레이션 문제라,
    본드를 90% 넘게 끊기 전에는 전부 한 덩어리로 나온다. 그래서 실무 표준인
    Kuz-Ram 을 주곡선으로 그리고, 신뢰구간 밖이면 DEM 곡선에 경고를 붙인다.
    """
    size = stats["size_sorted"]
    cum = stats["cum"]
    kr = stats.get("kuz_ram")
    if size.size < 2 and not kr:
        return
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.2))

    if kr:
        xs = np.logspace(-2, 1, 200)
        rr = 1.0 - np.exp(-((xs / kr["Xc"]) ** kr["n"]))
        ax[0].semilogx(xs, rr * 100, "-", lw=2.0, color="tab:red",
                       label=f"Kuz-Ram  X50={kr['X50']:.2f} m, n={kr['n']:.2f}")
        for frac, key in ((50, "X50"), (80, "X80")):
            ax[0].axhline(frac, color="0.6", lw=0.7, ls=":")
            ax[0].axvline(kr[key], color="0.6", lw=0.7, ls=":")
            ax[0].text(kr[key], 3, f" {key}={kr[key]:.2f}m", fontsize=7, color="0.3")

    if size.size >= 2:
        ok = stats.get("size_reliable", False)
        ax[0].semilogx(size, cum * 100, "o--", ms=3, lw=1.0,
                       color="tab:blue" if ok else "0.65",
                       label=L("DEM 연결성분" + ("" if ok else " (퍼콜레이션 한계 — 과대)"),
                               "DEM connectivity"))
    ax[0].set_xlabel(L("파쇄체 등가입경 [m]", "Fragment size [m]"))
    ax[0].set_ylabel(L("누적 통과율 [%]", "Cumulative passing [%]"))
    ax[0].set_title(L("파쇄 입도 분포", "Fragment size distribution"))
    ax[0].set_ylim(0, 100)
    ax[0].set_xlim(0.02, 12)
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


def plot_tet_mesh(mesh, path: str) -> None:
    """사면체 메쉬 진단도 — 단면 / 공벽 확대 / 크기장 / 품질."""
    from matplotlib.collections import PolyCollection

    polys, reg = mesh.cut_polygons(axis=1, value=float(mesh.hole.collar[1]))
    rock = [p for p, r in zip(polys, reg) if r == 0]
    hole = [p for p, r in zip(polys, reg) if r == 1]
    lo, hi = mesh.domain.lo, mesh.domain.hi

    fig, ax = plt.subplots(2, 2, figsize=(11.5, 9.2))

    # (a) 전체 단면 ---------------------------------------------------------
    for a, zoom in ((ax[0, 0], False), (ax[0, 1], True)):
        a.add_collection(PolyCollection(rock, facecolors="#eef2f7",
                                        edgecolors="#5a6b80", linewidths=0.25))
        a.add_collection(PolyCollection(hole, facecolors="#d94a3d",
                                        edgecolors="#7a2018", linewidths=0.25))
        a.set_aspect("equal")
        a.set_xlabel("X [m]")
        a.set_ylabel("Z [m]")
    ax[0, 0].set_xlim(lo[0], hi[0]); ax[0, 0].set_ylim(lo[2], hi[2])
    ax[0, 0].set_title(L(f"Y=0 단면 — 요소 {mesh.n_tets:,}개, 절점 {mesh.n_points:,}개",
                         f"Y=0 section — {mesh.n_tets:,} tets"))

    # (b) 공벽 확대 ---------------------------------------------------------
    cx, cz = mesh.hole.collar[0], mesh.hole.collar[2] - 0.5 * mesh.hole.length
    w = 2.5 * mesh.hole.diameter
    ax[0, 1].set_xlim(cx - w, cx + w); ax[0, 1].set_ylim(cz - w, cz + w)
    ax[0, 1].set_title(L(f"공벽 확대 (Ø{mesh.hole.diameter * 1000:g} mm, ±{w:.2f} m)",
                         f"Borehole wall zoom (±{w:.2f} m)"))

    # (c) 크기장 검증 -------------------------------------------------------
    c = mesh.centroids()
    d = np.maximum(mesh.hole.distance(c), 1e-4)
    size = mesh.edge_lengths().mean(axis=1)
    cfg, h0 = mesh.config, mesh.edge_lengths().min()
    ax[1, 0].plot(d[::7], size[::7], ".", ms=1.2, color="#4a7ab5", alpha=0.35,
                  label=L("요소 평균 모서리", "mean edge"))
    dd = np.logspace(np.log10(d.min()), np.log10(d.max()), 100)
    h_near = cfg.h_near or (np.pi * mesh.hole.diameter / max(4, cfg.n_theta))
    ax[1, 0].plot(dd, np.minimum(cfg.h_far, h_near + cfg.growth * dd), "-",
                  color="crimson", lw=1.8,
                  label=L("설계 크기장 h(d)", "design sizing field"))
    ax[1, 0].set_xscale("log"); ax[1, 0].set_yscale("log")
    # 로그축 지수 라벨의 유니코드 마이너스(U+2212)를 못 그리는 폰트가 있어 평문 포맷 사용
    plain = ticker.FuncFormatter(lambda v, _: f"{v:g}")
    ax[1, 0].xaxis.set_major_formatter(plain)
    ax[1, 0].yaxis.set_major_formatter(plain)
    ax[1, 0].set_xlabel(L("공벽까지 거리 d [m]", "distance to wall d [m]"))
    ax[1, 0].set_ylabel(L("요소 크기 [m]", "element size [m]"))
    ax[1, 0].set_title(L("크기장 추종성", "Sizing-field compliance"))
    ax[1, 0].legend(fontsize=8)

    # (d) 품질 --------------------------------------------------------------
    q = mesh.quality()
    ang = mesh.dihedral_angles()
    ax[1, 1].hist(q, bins=60, range=(0, 1), color="#4a7ab5", alpha=0.85)
    ax[1, 1].axvline(np.median(q), color="crimson", lw=1.6,
                     label=L(f"중앙값 {np.median(q):.3f}", f"median {np.median(q):.3f}"))
    ax[1, 1].axvline(0.1, color="0.35", ls="--", lw=1.1,
                     label=L(f"q>0.1 : {(q > 0.1).mean() * 100:.2f} %",
                             f"q>0.1 : {(q > 0.1).mean() * 100:.2f} %"))
    ax[1, 1].set_xlabel(L("요소 품질 q  (정사면체 = 1)", "quality q (regular = 1)"))
    ax[1, 1].set_ylabel(L("요소 수", "count"))
    ax[1, 1].set_title(L(f"품질 분포 — 이면각 {ang.min():.1f}°~{ang.max():.1f}°",
                         f"Quality — dihedral {ang.min():.1f}-{ang.max():.1f} deg"))
    ax[1, 1].legend(fontsize=8)

    fig.suptitle(L(f"사면체 메쉬 — {mesh.domain.size[0]:g}×{mesh.domain.size[1]:g}"
                   f"×{mesh.domain.size[2]:g} m + 천공홀 "
                   f"Ø{mesh.hole.diameter * 1000:g} mm × {mesh.hole.length:g} m",
                   "Tetrahedral mesh with borehole"), fontsize=11)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def _tri_key(tris: np.ndarray, n: int) -> np.ndarray:
    """정렬된 삼각형 (i,j,k) 를 int64 키로 — 집합 연산용."""
    t = np.sort(tris, axis=1).astype(np.int64)
    return (t[:, 0] * n + t[:, 1]) * n + t[:, 2]


def _cutaway(mesh, lo, hi, cut=(0.0, 0.0), wall_keys=None, edge_len=None):
    """[lo,hi] 상자 안에서 지정 사분/반 영역과 천공홀을 들어낸 절개 표면.

    cut 은 (cx, cy) 로 x>cx & y>cy 옥탄트를 제거한다. 한 성분이 None 이면 그 축은
    조건에서 빠지므로 (None, cy) 는 y>cy 절반을 잘라내는 '반절개'가 된다.
    wall_keys / edge_len 은 여러 배율을 그릴 때 재계산을 피하려고 넘기는 캐시다.
    남은 사면체의 경계 삼각형 = (바깥/절단 상자면) + (절개 단면) + (공벽) 이므로
    한 번의 추출로 표면·내부격자·구멍이 동시에 드러난다.
    """
    from blastsim.mesh import REGION_ROCK, _FACES
    c = mesh.centroids()
    drop = np.ones(len(c), dtype=bool)
    if all(v is None for v in cut):
        drop[:] = False                    # 절개 없음 = 암반 영역 전체
    for ax, v in enumerate(cut):
        if v is not None:
            drop &= c[:, ax] > v
    keep = ((mesh.region == REGION_ROCK)
            & np.all(c > np.asarray(lo), axis=1) & np.all(c < np.asarray(hi), axis=1)
            & ~drop)
    tets = mesh.tets[keep]
    if len(tets) == 0:
        return np.zeros((0, 3), int), np.zeros(0), np.zeros(0, bool)
    faces = np.sort(tets[:, _FACES].reshape(-1, 3), axis=1)
    uniq, idx, cnt = np.unique(faces, axis=0, return_index=True, return_counts=True)
    surf, first = uniq[cnt == 1], idx[cnt == 1]
    owner = np.repeat(np.arange(len(tets)), 4)[first]
    el = mesh.edge_lengths() if edge_len is None else edge_len
    size = el[keep][owner].mean(axis=1)

    if wall_keys is None:
        wall_keys = _tri_key(mesh.hole_wall_facets(), mesh.n_points)
    is_wall = np.isin(_tri_key(surf, mesh.n_points), wall_keys)
    return surf, size, is_wall


def plot_tet_mesh_3d(mesh, path: str, elev: float = 20.0, azim: float = 42.0) -> None:
    """사면체 메쉬 3D 사분절개 렌더 — 세 배율 + 공벽 재하면.

    배율마다 절개면을 다시 뽑는다. 전역 절개면을 잘라 쓰면 확대 화면에
    잘린 단면만 남고 내부가 보이지 않기 때문이다.
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    lo, hi = mesh.domain.lo, mesh.domain.hi
    cx, cy, cz = mesh.hole.collar
    d = mesh.hole.diameter
    views = [
        (L("전체 사분절개", "Quarter cut-away"),
         lo, hi, (cx, cy), 0.05),
        (L("공구 주변 ±1.0 m × 깊이 3 m", "Collar region ±1.0 m x 3 m"),
         (cx - 1.0, cy - 1.0, cz - 3.0), (cx + 1.0, cy + 1.0, cz), (cx, cy), 0.2),
        # 근접은 반절개 — 원통을 정확히 반으로 갈라 공벽이 그대로 드러난다
        (L(f"공벽 반절개 (Ø{d * 1000:g} mm)", "Wall half-section"),
         (cx - 0.09, cy - 0.09, cz - 6.12), (cx + 0.09, cy + 0.09, cz - 5.82),
         (None, cy), 0.5),
    ]

    fig = plt.figure(figsize=(13.5, 10.5))
    plain = ticker.FuncFormatter(lambda v, _: f"{v:g}")
    wall_keys = _tri_key(mesh.hole_wall_facets(), mesh.n_points)
    edge_len = mesh.edge_lengths()
    all_sz = _cutaway(mesh, lo, hi, wall_keys=wall_keys, edge_len=edge_len)[1]
    norm = matplotlib.colors.LogNorm(vmin=max(all_sz.min(), 1e-4), vmax=all_sz.max())
    cmap = plt.get_cmap("YlGnBu_r")
    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)

    for k, (title, blo, bhi, cut, lw) in enumerate(views):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        ax.set_proj_type("ortho")
        surf, size, is_wall = _cutaway(mesh, blo, bhi, cut=cut,
                                       wall_keys=wall_keys, edge_len=edge_len)
        if len(surf):
            # 암반면과 공벽을 한 컬렉션에 담는다. mplot3d 는 컬렉션 '사이'의 깊이를
            # 정렬하지 않으므로 따로 그리면 뒤 컬렉션이 통째로 가려지거나 덮인다.
            fc = cmap(norm(size))
            ec = np.tile(matplotlib.colors.to_rgba("#33404f"), (len(surf), 1))
            fc[is_wall] = matplotlib.colors.to_rgba("#d94a3d")
            ec[is_wall] = matplotlib.colors.to_rgba("#6d1c15")
            pc = Poly3DCollection(mesh.points[surf], facecolors=fc, edgecolors=ec,
                                  linewidths=lw)
            pc.set_zsort("average")
            ax.add_collection3d(pc)
        ax.set_xlim(blo[0], bhi[0]); ax.set_ylim(blo[1], bhi[1])
        ax.set_zlim(blo[2], bhi[2])
        ax.set_box_aspect([bhi[i] - blo[i] for i in range(3)])
        ax.view_init(elev=elev, azim=azim)
        for a, lab in ((ax.xaxis, "X [m]"), (ax.yaxis, "Y [m]"), (ax.zaxis, "Z [m]")):
            a.set_major_formatter(plain)
            a.set_label_text(lab)
        ax.locator_params(nbins=4)
        ax.tick_params(labelsize=7, pad=-2)
        ax.set_title(f"{title}   ({len(surf):,} tri)", fontsize=10)

    # (d) 공벽 재하면만 — 폭굉 가스압이 걸리는 표면
    ax = fig.add_subplot(2, 2, 4, projection="3d")
    ax.set_proj_type("ortho")
    wall = mesh.hole_wall_facets()
    wc = mesh.points[wall].mean(axis=1)
    seg = wc[:, 2] > cz - 1.0
    depth = wc[seg, 2]
    pc = Poly3DCollection(
        mesh.points[wall[seg]],
        facecolors=plt.get_cmap("autumn")(
            (depth - depth.min()) / max(float(np.ptp(depth)), 1e-9)),
        edgecolors="#6d1c15", linewidths=0.3)
    pc.set_zsort("average")
    ax.add_collection3d(pc)
    r = mesh.hole.radius * 1.4
    ax.set_xlim(cx - r, cx + r); ax.set_ylim(cy - r, cy + r); ax.set_zlim(cz - 1.0, cz)
    ax.set_box_aspect((2 * r, 2 * r, 0.45))
    ax.view_init(elev=12, azim=azim)
    for a, lab in ((ax.xaxis, "X [m]"), (ax.yaxis, "Y [m]"), (ax.zaxis, "Z [m]")):
        a.set_major_formatter(plain)
        a.set_label_text(lab)
    ax.locator_params(nbins=3)
    ax.tick_params(labelsize=7, pad=-2)
    ax.set_title(L(f"공벽 재하면 상부 1 m ({int(seg.sum()):,} tri)",
                   f"Wall load surface, top 1 m ({int(seg.sum()):,} tri)"), fontsize=10)

    fig.subplots_adjust(left=0.02, right=0.88, top=0.93, bottom=0.03,
                        wspace=0.06, hspace=0.22)
    cb = fig.colorbar(sm, ax=fig.axes[:3], shrink=0.45, pad=0.02, location="right")
    cb.set_label(L("요소 크기 [m]", "element size [m]"), fontsize=9)
    cb.ax.yaxis.set_major_formatter(plain)
    fig.suptitle(L(f"사면체 메쉬 3D 절개 — {mesh.domain.size[0]:g}×"
                   f"{mesh.domain.size[1]:g}×{mesh.domain.size[2]:g} m + 천공홀 "
                   f"Ø{d * 1000:g} mm × {mesh.hole.length:g} m (요소 {mesh.n_tets:,})",
                   "Tetrahedral mesh — 3D cut-away"), fontsize=11)
    fig.savefig(path); plt.close(fig)
