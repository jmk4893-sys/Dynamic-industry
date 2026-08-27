#!/usr/bin/env python3
"""체분리 DEM 결과를 MP4 로 렌더링한다.

    python3 tools/render_sieve_video.py -i sim_out/sieve_dem.npz -o sim_out/sieve.mp4
"""
import argparse
import json
import math
import os
import subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import EllipseCollection
from matplotlib import font_manager

for _f in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",):
    if os.path.exists(_f):
        font_manager.fontManager.addfont(_f)
        plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False

FFMPEG = next((p for p in ("ffmpeg", "/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux")
               if os.path.exists(p) or subprocess.call(
                   ["which", p], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL) == 0), "ffmpeg")

COL = {"구리": "#B4652A", "실리콘+은": "#B0357A", "백시트+EVA": "#0071B0"}
BG, FG, GRID = "#FFFFFF", "#1a1a1a", "#DDDDDD"


def render(npz, out_mp4, fps=30, dpi=110, frame_dir=None):
    z = np.load(npz, allow_pickle=True)
    cfg = json.loads(str(z["cfg"]))
    pos, th, alive, times = z["pos"], z["th"], z["alive"], z["times"]
    owner, off, rad = z["owner"], z["off"], z["rad"]
    name, width, ar = z["name"], z["width"], z["ar"]
    wire_x, wire_r = z["wire_x"], float(z["wire_r"])
    ap, W = cfg["aperture"], cfg["width"]

    mass = math.pi / 6.0 * (width * ar) * width ** 2 * np.array(
        [{"구리": 8960, "실리콘+은": 2500, "백시트+EVA": 1200}[n] for n in name])
    mats = sorted(set(name.tolist()))
    colors = np.array([COL[n] for n in name])[owner]

    frame_dir = frame_dir or os.path.join(os.path.dirname(out_mp4) or ".", "_frames")
    os.makedirs(frame_dir, exist_ok=True)
    for f in os.listdir(frame_dir):
        os.remove(os.path.join(frame_dir, f))

    um = 1e6
    fig = plt.figure(figsize=(12.8, 7.2), dpi=dpi, facecolor=BG)
    axS = fig.add_axes([0.045, 0.09, 0.60, 0.80])
    axR = fig.add_axes([0.695, 0.42, 0.275, 0.47])
    axB = fig.add_axes([0.695, 0.09, 0.275, 0.24])

    for ax in (axS, axR, axB):
        ax.set_facecolor(BG)
        for sp in ax.spines.values():
            sp.set_color(GRID)

    axS.set_xlim(0, W * um)
    axS.set_ylim(-6 * ap * um, 1.7e-3 * um)
    axS.set_aspect("equal")
    axS.set_xlabel("x [µm]", color=FG, fontsize=9)
    axS.set_ylabel("z [µm]   (데크면 = 0)", color=FG, fontsize=9)
    axS.tick_params(colors=FG, labelsize=8)
    axS.axhline(0, color=GRID, lw=0.8)

    ec = EllipseCollection(np.zeros(1), np.zeros(1), np.zeros(1), units="xy",
                           offsets=np.zeros((1, 2)), offset_transform=axS.transData,
                           facecolors="none", edgecolors="none", lw=0.7)
    axS.add_collection(ec)
    wire_col = EllipseCollection(
        np.full(len(wire_x), 2 * wire_r * um), np.full(len(wire_x), 2 * wire_r * um),
        np.zeros(len(wire_x)), units="xy",
        offsets=np.column_stack([wire_x * um, np.zeros(len(wire_x))]),
        offset_transform=axS.transData, facecolors="#555555", edgecolors="#333333",
        lw=0.6, zorder=3)
    axS.add_collection(wire_col)

    n_fr = len(times)
    cum = {m: np.zeros(n_fr) for m in mats}
    for k in range(n_fr):
        gone = ~alive[k]
        for m in mats:
            sel = (name == m)
            cum[m][k] = mass[sel & gone].sum() / mass[sel].sum() * 100

    freq = cfg["freq"]
    for k in range(n_fr):
        o = owner
        cs, sn = np.cos(th[k][o]), np.sin(th[k][o])
        xy = np.column_stack([(pos[k][o, 0] + off * cs) * um,
                              (pos[k][o, 1] + off * sn) * um])
        live = alive[k][o]
        d = 2 * rad * um
        ec.set_offsets(xy)
        ec._widths = d / 2      # EllipseCollection 은 반축을 쓴다
        ec._heights = d / 2
        ec.set_facecolors(np.where(live, colors, "#00000000"))
        ec.set_edgecolors(np.where(live, "#33333366", "#00000000"))

        axS.set_title(f"체분리 DEM — 75 µm 데크 · t = {times[k]*1e3:6.1f} ms  "
                      f"({times[k]*freq:4.1f} 가진주기)", color=FG, fontsize=11, loc="left")

        axR.clear(); axR.set_facecolor(BG)
        for m in mats:
            axR.plot(times[:k+1] * 1e3, cum[m][:k+1], color=COL[m], lw=2.0, label=m)
        axR.set_xlim(0, times[-1] * 1e3); axR.set_ylim(0, 100)
        axR.set_xlabel("시간 [ms]", fontsize=9, color=FG)
        axR.set_ylabel("누적 통과 [질량 %]", fontsize=9, color=FG)
        axR.tick_params(colors=FG, labelsize=8)
        axR.grid(alpha=.25, color=GRID)
        axR.legend(fontsize=8, loc="upper left", framealpha=.9)
        axR.set_title("물질별 통과", color=FG, fontsize=10, loc="left")

        axB.clear(); axB.set_facecolor(BG); axB.axis("off")
        gone = ~alive[k]
        lines = [f"가진강도 Γ = {cfg['gamma']:.0f} g,  {freq:.0f} Hz",
                 f"개구 {ap*um:.0f} µm · 선경 {wire_r*2*um:.0f} µm",
                 f"입자 {len(name)} 개 · 통과 {int(gone.sum())} 개", ""]
        for m in mats:
            sel = name == m
            lines.append(f"{m:9s} {cum[m][k]:5.1f} %")
        fine = width < ap
        lines += ["", f"< 75 µm 입자 통과율 {100*(gone & fine).sum()/max(fine.sum(),1):5.1f} %",
                  f"근접입자(0.8~1.3 a) {100*((width>0.8*ap)&(width<1.3*ap)).sum()/len(width):4.1f} %"]
        axB.text(0, 1, "\n".join(lines), va="top", ha="left", fontsize=9.5,
                 color=FG, family="monospace", transform=axB.transAxes)

        fig.savefig(os.path.join(frame_dir, f"f{k:05d}.png"),
                    facecolor=BG, dpi=dpi)
        if k % 50 == 0:
            print(f"  frame {k}/{n_fr}", flush=True)
    plt.close(fig)

    cmd = [FFMPEG, "-y", "-framerate", str(fps), "-i",
           os.path.join(frame_dir, "f%05d.png"), "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_mp4


if __name__ == "__main__":
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("-i", "--input", default="sim_out/sieve_dem.npz")
    ap_.add_argument("-o", "--output", default="sim_out/sieve.mp4")
    ap_.add_argument("--fps", type=int, default=30)
    a = ap_.parse_args()
    print("완료:", render(a.input, a.output, fps=a.fps))
