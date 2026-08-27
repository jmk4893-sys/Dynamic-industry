#!/usr/bin/env python3
"""classifier_sim 결과를 그림으로 만든다."""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import classifier_sim as cs

for cand in ("WenQuanYi Zen Hei", "Noto Sans CJK KR", "NanumGothic"):
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams.update({
    "axes.unicode_minus": False, "figure.dpi": 130,
    "axes.edgecolor": "#C5D0CE", "axes.linewidth": 0.9,
    "grid.color": "#DBE3E1", "grid.linewidth": 0.8,
    "xtick.color": "#63736F", "ytick.color": "#63736F",
    "axes.labelcolor": "#3C4B4A", "text.color": "#16211F", "font.size": 9,
})
CU, SI, POLY = "#B4652A", "#B0357A", "#0071B0"
SCEN = {"미분급 75~500 µm": SI, "분획 75~106 µm": POLY, "분획 106~200 µm": CU}


def fig_grade_recovery(vel, res, path):
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    for name, rows in res.items():
        rec = np.array([r["cu_recovery"] for r in rows]) * 100
        gra = np.array([r["cu_grade"] for r in rows]) * 100
        c = SCEN[name]
        ax.plot(rec, gra, "-", color=c, lw=2.0, label=name, zorder=3)
        b = cs.best_point(rows)
        ax.plot(b["cu_recovery"] * 100, b["cu_grade"] * 100, "o", color=c,
                ms=8, mec="white", mew=1.6, zorder=5)
        dy = {"미분급 75~500 µm": -30, "분획 75~106 µm": -20, "분획 106~200 µm": -48}[name]
        ax.annotate(f"{b['u']:.2f} m/s · 회수 {b['cu_recovery']*100:.0f}% · 품위 {b['cu_grade']*100:.0f}%",
                    (b["cu_recovery"] * 100, b["cu_grade"] * 100),
                    textcoords="offset points", xytext=(-10, dy), fontsize=8,
                    color=c, ha="right", fontweight="bold")
    ax.axvline(85, color="#63736F", ls="--", lw=0.9, zorder=1)
    ax.text(84, 108, "회수율 하한 85 %", fontsize=8, color="#63736F", ha="right", va="center")
    ax.set_xlabel("구리 회수율 [%]"); ax.set_ylabel("중량측 산물의 구리 품위 [%]")
    ax.set_title("입도 분급이 에어분급 성능을 결정한다", fontsize=11.5, pad=10, loc="left")
    ax.grid(True, zorder=0); ax.set_xlim(0, 102); ax.set_ylim(0, 114)
    ax.legend(frameon=False, loc="lower left", fontsize=8.5)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)
    return path


def fig_partition(tabs, path):
    us = sorted(tabs)
    fig, axes = plt.subplots(1, len(us), figsize=(9.6, 4.0), sharey=True)
    style = {"구리": (CU, "-", 2.2), "실리콘+은": (SI, "-", 1.6),
             "백시트+EVA": (POLY, "-", 1.8), "EVA": (POLY, "--", 1.4)}
    for ax, u in zip(np.atleast_1d(axes), us):
        lo, hi = (75, 106) if u < 1.5 else (106, 200)
        ax.axvspan(lo, hi, color="#E4EAE9", zorder=0)
        for name, (c, ls, lw) in style.items():
            d = [g for j, g in enumerate(cs.GRID_UM) if (name, j) in tabs[u]]
            p = [(1 - tabs[u][(name, j)]) * 100 for j, g in enumerate(cs.GRID_UM)
                 if (name, j) in tabs[u]]
            if d: ax.plot(d, p, ls, color=c, lw=lw, label=name, zorder=3)
        ax.set_xscale("log"); ax.set_xlim(18, 560); ax.set_ylim(-3, 103)
        ax.set_xticks([20, 50, 75, 106, 200, 500])
        ax.set_xticklabels(["20", "50", "75", "106", "200", "500"])
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.tick_params(axis="x", which="minor", length=2)
        ax.axhline(50, color="#63736F", ls=":", lw=0.9, zorder=1)
        ax.set_title(f"u = {u:.2f} m/s   (분획 {lo}~{hi} µm)", fontsize=10, loc="left")
        ax.set_xlabel("입경 [µm]"); ax.grid(True, zorder=0)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    np.atleast_1d(axes)[0].set_ylabel("중량측(하단) 귀속 확률 [%]")
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=8, loc="center left")
    fig.suptitle("분배(Tromp) 곡선 — 음영이 해당 컬럼이 담당하는 입도 분획",
                 fontsize=11.5, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.94]); fig.savefig(path, bbox_inches="tight"); plt.close(fig)
    return path


def fig_agglomeration(path):
    """분산기 효율에 따른 구리 품위·회수율."""
    import json
    data = json.load(open("sim_out/agglomeration.json"))
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    colors = {"TC-01": CU, "TC-02": POLY}
    for tag, (etas, grade, rec) in data.items():
        e = np.array(etas) * 100
        ax.plot(e, np.array(grade) * 100, "-", color=colors[tag], lw=2.2,
                label=f"{tag} 구리 품위", zorder=3)
        ax.plot(e, np.array(rec) * 100, "--", color=colors[tag], lw=1.3,
                label=f"{tag} 구리 회수율", zorder=3)
        need = float(np.interp(0.98, grade, etas)) * 100
        ax.plot(need, 98, "o", color=colors[tag], ms=8, mec="white", mew=1.6, zorder=5)
        dx = (-6, -20) if tag == "TC-02" else (6, -20)
        ax.annotate(f"{tag} {need:.0f} %", (need, 98), textcoords="offset points",
                    xytext=dx, fontsize=8.5, color=colors[tag], fontweight="bold",
                    ha="right" if tag == "TC-02" else "left")
    ax.axhline(98, color="#63736F", ls=":", lw=1.0, zorder=1)
    ax.text(2, 98.4, "품위 목표 98 %", fontsize=8.5, color="#63736F")
    ax.set_xlabel("분산기 효율 [%]"); ax.set_ylabel("구리 품위 · 회수율 [%]")
    ax.set_title("응집이 무너뜨리는 것은 회수율이 아니라 품위다",
                 fontsize=11.5, pad=10, loc="left")
    ax.set_xlim(-2, 102); ax.set_ylim(80, 101.5); ax.grid(True, zorder=0)
    ax.legend(frameon=False, loc="lower right", fontsize=8.5, ncol=2)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    vel, res, _ = pickle.load(open("sim_out/sweep.pkl", "rb"))
    tabs = pickle.load(open("sim_out/partition.pkl", "rb"))
    print(fig_grade_recovery(vel, res, "sim_out/fig1_grade_recovery.png"))
    print(fig_partition(tabs, "sim_out/fig2_partition.png"))
    print(fig_agglomeration("sim_out/fig3_agglomeration.png"))
