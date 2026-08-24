"""영상 생성 — 파쇄·비산 애니메이션과 진동파 전파 애니메이션.

mp4 는 imageio-ffmpeg 로 쓴다 (윈도우에 ffmpeg 를 따로 설치할 필요가 없다).
사용할 수 없으면 GIF 로 자동 대체한다.
"""

from __future__ import annotations

import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .plots import KO, L


def _writer(path: str, fps: float):
    """(writer, 실제 저장경로). mp4 가 불가하면 gif 로 대체한다."""
    try:
        import imageio.v2 as imageio
    except ImportError as exc:                       # pragma: no cover
        raise ImportError("영상 생성에는 imageio 가 필요합니다: "
                          "pip install imageio imageio-ffmpeg") from exc
    if path.lower().endswith(".mp4"):
        try:
            return imageio.get_writer(path, fps=int(fps), codec="libx264",
                                      quality=8, macro_block_size=None), path
        except Exception:
            path = os.path.splitext(path)[0] + ".gif"
    return imageio.get_writer(path, fps=int(fps), loop=0), path


def _fig_to_rgb(fig) -> np.ndarray:
    """matplotlib figure -> RGB 배열. 폭·높이를 짝수로 맞춘다.

    h264(yuv420p)는 크로마 서브샘플링 때문에 가로·세로가 모두 짝수여야 한다.
    홀수 치수를 넘기면 인코더가 아예 열리지 않고 'Broken pipe' 로 죽는다.
    """
    fig.canvas.draw()
    rgb = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
    h, w = rgb.shape[:2]
    return rgb[: h - (h % 2), : w - (w % 2)].copy()


# ---------------------------------------------------------------------------
def animate_fragmentation(
    result,
    path: str = "fragmentation.mp4",
    fps: float = 24.0,
    max_particles: int = 6000,
    dpi: int = 96,
    vmax: float | None = None,
    show_progress: bool = True,
) -> str:
    """파쇄·비산 애니메이션 (3D 조감 + 측면도).

    벤치발파에서는 측면도(x-z)가 가장 정보가 많다 — 저항선 이동, 자유면 이완,
    비산 궤적, 파쇄암 적재가 한 화면에 보인다.
    """
    if not result.frames:
        raise ValueError("프레임이 없습니다. FragConfig.snapshot_fps 를 확인하세요.")

    n = result.pos0.shape[0]
    if n > max_particles:
        sel = np.random.default_rng(0).choice(n, max_particles, replace=False)
    else:
        sel = np.arange(n)

    all_pos = np.array([f[1][sel] for f in result.frames])
    all_spd = np.array([f[2][sel] for f in result.frames])
    vmax = float(vmax or np.percentile(all_spd, 99.5)) or 1.0

    x_lo, x_hi = all_pos[..., 0].min() - 1, all_pos[..., 0].max() + 1
    y_lo, y_hi = all_pos[..., 1].min() - 1, all_pos[..., 1].max() + 1
    z_lo = all_pos[..., 2].min() - 1
    z_hi = max(2.0, all_pos[..., 2].max() + 1)

    writer, real = _writer(path, fps)
    # 마커 크기는 '솎아내기 전의 밀도'를 유지하도록 잡는다. 예전 휴리스틱
    # (2200/n)은 입자가 많아질수록 작아져 하한 1 pt^2 에 붙어 버렸고, 3만 입자
    # 해석에서는 화면이 암반이 아니라 먼지처럼 보였다. 기준은 적재 그림
    # (plot_muckpile)이 전 입자를 s=3 으로 그려 잘 읽히는 것이다.
    size = float(np.clip(3.0 * n / max(sel.size, 1), 3.0, 40.0))
    try:
        for n_f, (t, _, _) in enumerate(result.frames):
            pos, spd = all_pos[n_f], all_spd[n_f]
            fig = plt.figure(figsize=(11, 4.6), dpi=dpi)

            ax = fig.add_subplot(121, projection="3d")
            ax.scatter(pos[:, 0], pos[:, 1], pos[:, 2], c=spd, cmap="inferno",
                       vmin=0, vmax=vmax, s=size * 0.6, depthshade=False,
                       linewidths=0)
            ax.set_xlim(x_lo, x_hi); ax.set_ylim(y_lo, y_hi); ax.set_zlim(z_lo, z_hi)
            ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]"); ax.set_zlabel("Z [m]")
            ax.view_init(elev=18, azim=-62)
            try:
                ax.set_box_aspect((x_hi - x_lo, y_hi - y_lo, z_hi - z_lo))
            except Exception:
                pass
            ax.set_title(L("조감", "3D view"), fontsize=9)

            ax2 = fig.add_subplot(122)
            sc = ax2.scatter(pos[:, 0], pos[:, 2], c=spd, cmap="inferno",
                             vmin=0, vmax=vmax, s=size, linewidths=0)
            ax2.axvline(result.face_x, color="tab:cyan", lw=1.0, ls="--")
            ax2.axhline(result.toe_z, color="tab:cyan", lw=1.0, ls="--")
            ax2.axhline(0.0, color="0.6", lw=0.8)
            ax2.set_xlim(x_lo, x_hi); ax2.set_ylim(z_lo, z_hi)
            ax2.set_aspect("equal")
            ax2.set_xlabel("X [m]"); ax2.set_ylabel("Z [m]")
            ax2.set_title(L("측면도 (자유면 방향 →)", "Side view"), fontsize=9)
            fig.colorbar(sc, ax=ax2, label=L("속도 [m/s]", "speed [m/s]"), shrink=0.85)

            fig.suptitle(f"t = {t * 1000:7.1f} ms", fontsize=11)
            fig.tight_layout()
            writer.append_data(_fig_to_rgb(fig))
            plt.close(fig)
            if show_progress and n_f % 10 == 0:
                print(f"\r  영상 {100.0 * n_f / len(result.frames):5.1f}%",
                      end="", flush=True)
    finally:
        writer.close()
    if show_progress:
        print(f"\r  영상 저장 완료: {real}" + " " * 24)
    return real


# ---------------------------------------------------------------------------
def animate_vibration(
    fdm_result,
    pattern,
    path: str = "vibration.mp4",
    fps: float = 20.0,
    dpi: int = 96,
    show_progress: bool = True,
) -> str:
    """지표 진동파 전파 애니메이션 (FDM 스냅샷)."""
    snaps = fdm_result.snapshots
    if not snaps:
        raise ValueError("스냅샷이 없습니다. FDMConfig.snapshot_times 를 지정하세요.")
    pos = fdm_result.surface_pos
    xs = np.unique(pos[:, 0])
    ys = np.unique(pos[:, 1])
    ts = sorted(snaps)
    vmax = max(float(s.max()) for s in snaps.values()) * 1000.0
    if vmax <= 0:
        raise ValueError("진동이 지표에 도달하지 않았습니다 — 해석시간을 늘리세요.")

    hp = pattern.positions()
    writer, real = _writer(path, fps)
    try:
        for n_f, t in enumerate(ts):
            v = snaps[t].reshape(xs.size, ys.size) * 1000.0
            fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=dpi)
            im = ax.pcolormesh(xs, ys, v.T, cmap="turbo", vmin=0, vmax=vmax,
                               shading="auto")
            ax.plot(hp[:, 0], hp[:, 1], "kv", ms=5, mfc="white")
            ax.set_aspect("equal")
            ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]")
            ax.set_title(L(f"지표 진동  t = {t * 1000:.0f} ms",
                           f"Surface vibration  t = {t * 1000:.0f} ms"), fontsize=10)
            fig.colorbar(im, ax=ax, label="|v| [mm/s]")
            fig.tight_layout()
            writer.append_data(_fig_to_rgb(fig))
            plt.close(fig)
            if show_progress and n_f % 5 == 0:
                print(f"\r  영상 {100.0 * n_f / len(ts):5.1f}%", end="", flush=True)
    finally:
        writer.close()
    if show_progress:
        print(f"\r  영상 저장 완료: {real}" + " " * 24)
    return real
