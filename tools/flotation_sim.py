"""FC-201 러퍼 축약차수 입자 애니메이션 → mp4.

실행 (저장소 루트에서):
    pip install -e '.[simulation]'
    SIM_KOREAN_FONT=/path/to/NanumGothic.ttf python tools/flotation_sim.py out.mp4

설계 패키지(src/flotation_design)에서 셀 치수·기포 상승속도·기동 ODE 를
직접 읽으므로, design_basis.py 를 바꾸면 영상도 함께 바뀐다. 다만 이 도구는
CFD/DEM 검증 계산이 아니라 설계값으로 보정한 **축약차수 교육용 모델**이다.

2D 단면에서 기포·입자를 개별 추적한다. 속도 스케일은 전부 설계 계산값:
  - 기포군 상승속도 6.5 cm/s (hydrodynamics.swarm_velocity)
  - 입자 침강속도 3.2 mm/s
  - 로터 순환 유속 ~0.5 m/s, 로터 Ø350 @ y 0.21
  - 중공축 외경·보어 — 기포는 로터 허브 분산구에서만 생성
힘/규칙: 유동장 이류 + 종말속도 슬립 + 난류 요동, 기포-입자 충돌 반경 내
확률 부착 (속부선/지연부선/맥석 구분), 거품층 배수(맥석 탈착), 립 월류 회수,
다트밸브 미광 배출, 급광·여액 연속 주입.

충돌·부착·탈착 확률은 시각화를 위한 경험계수이며 설계 보증값에 쓰지 않는다.
정량 검증에는 별도의 다상 CFD/입자추적과 파일럿 시험이 필요하다.
"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.animation
from matplotlib import font_manager, pyplot as plt
from matplotlib.patches import FancyArrow, Polygon, Rectangle

import os
import pathlib
import shutil

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_FONT = os.environ.get("SIM_KOREAN_FONT", "")   # NanumGothic.ttf 경로 (한글 라벨용)
if _FONT and pathlib.Path(_FONT).exists():
    font_manager.fontManager.addfont(_FONT)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=_FONT).get_name()
else:
    print("경고: SIM_KOREAN_FONT 미지정 — 한글 라벨이 깨질 수 있다", file=sys.stderr)
try:
    import imageio_ffmpeg

    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    _FFMPEG = shutil.which("ffmpeg")
    if not _FFMPEG:
        raise RuntimeError(
            "ffmpeg를 찾지 못했습니다. pip install -e '.[simulation]'을 실행하세요."
        )
plt.rcParams["animation.ffmpeg_path"] = _FFMPEG

sys.path.insert(0, str(_ROOT / "src"))
from flotation_design.plant import build_mechanical_option
from flotation_design.transient import simulate_startup
from flotation_design.hydrodynamics import analyse_cell

rng = np.random.default_rng(42)

# ---------- 설계값 ----------
OPT = build_mechanical_option()
CELL = OPT.cells[0]                      # FC-201
RES = OPT.result_peak
G, I, A, S = CELL.geometry, CELL.impeller, CELL.aeration, CELL.shaft
R = G.width_m / 2                        # 0.5 m
LIP = G.lip_height_m                     # 1.24 m
PULP_TOP = LIP - G.froth_depth_m         # 1.165 m
ROTOR_R = I.diameter_m / 2               # 0.175
ROTOR_Y = I.bottom_clearance_m           # 0.21
SHAFT_R = S.outer_diameter_mm / 2000     # 0.04
BORE_R = S.bore_mm / 2000                # 0.01
HYD = analyse_cell(CELL.tag, A.superficial_gas_velocity_cm_s,
                   A.bubble_sauter_mean_mm, G.gas_holdup,
                   G.pulp_zone_height_m, 2.08)
V_BUBBLE = HYD.bubble_swarm_m_s          # 0.065 m/s
V_SETTLE = HYD.particle_settling_mm_s / 1000.0   # 0.0032 m/s
TR = simulate_startup(RES, duration_min=40.0, sample_every_min=0.25)

# ---------- 유동장 (로터 구동 이중 순환 루프) ----------
A_PSI = 0.11                              # 순환 강도 → |u|max ≈ 0.5 m/s
JET = 0.65                                # 로터 방사 제트 (m/s)

def fluid_velocity(x, y):
    """ψ = A sin(πx/R) sin(πy/Hp) 의 회전 성분 + 로터 제트."""
    hp = PULP_TOP
    ux = A_PSI * np.pi / hp * np.sin(np.pi * x / R) * np.cos(np.pi * y / hp)
    uy = -A_PSI * np.pi / R * np.cos(np.pi * x / R) * np.sin(np.pi * y / hp)
    jet = JET * np.exp(-((y - ROTOR_Y - 0.02) / 0.055) ** 2)
    ux = ux + np.sign(x) * jet * np.clip(1 - np.abs(x) / R, 0, 1) * np.clip(np.abs(x) / 0.05, 0, 1)
    inside = (np.abs(x) < R) & (y > 0) & (y < PULP_TOP)
    return np.where(inside, ux, 0.0), np.where(inside, uy, 0.0)

# ---------- 상태 ----------
MAXB, MAXP = 420, 900
b_pos = np.zeros((0, 2)); b_age = np.zeros(0)
FAST, SLOW, GANGUE = 0, 1, 2
p_pos = np.zeros((0, 2)); p_cls = np.zeros(0, int); p_att = np.zeros(0, int)  # -1 자유, else 기포 idx
counts = {"conc_ag": 0, "conc_gangue": 0, "tail_ag": 0, "tail_gangue": 0,
          "feed_ag": 0, "feed_gangue": 0}
hist_t, hist_rec = [], []

def spawn_particles(n, feed=True):
    global p_pos, p_cls, p_att
    cls = rng.choice([FAST, SLOW, GANGUE], size=n, p=[0.12, 0.04, 0.84])
    if feed:  # 급광 박스 (좌상)
        xy = np.column_stack([rng.uniform(-R + 0.01, -R + 0.06, n),
                              rng.uniform(1.02, 1.12, n)])
    else:     # 초기 분산
        xy = np.column_stack([rng.uniform(-R + 0.02, R - 0.02, n),
                              rng.uniform(0.05, PULP_TOP - 0.05, n)])
    p_pos = np.vstack([p_pos, xy]); p_cls = np.append(p_cls, cls)
    p_att = np.append(p_att, np.full(n, -1))
    counts["feed_ag"] += int((cls != GANGUE).sum())
    counts["feed_gangue"] += int((cls == GANGUE).sum())

def spawn_bubbles(n):
    global b_pos, b_age
    side = rng.choice([-1, 1], n)
    x = side * rng.uniform(SHAFT_R + 0.01, ROTOR_R, n)   # 허브 분산구 위치
    y = np.full(n, ROTOR_Y + 0.015) + rng.uniform(0, 0.01, n)
    b_pos = np.vstack([b_pos, np.column_stack([x, y])]); b_age = np.append(b_age, np.zeros(n))

spawn_particles(430, feed=False)

def preload_bubbles():
    global b_pos, b_age
    n1, n2 = 180, 70
    x1 = rng.uniform(-R + 0.03, R - 0.03, n1); y1 = rng.uniform(0.26, PULP_TOP - 0.02, n1)
    x2 = rng.uniform(-R + 0.03, R - 0.03, n2); y2 = rng.uniform(PULP_TOP + 0.005, LIP - 0.02, n2)
    b_pos = np.vstack([b_pos, np.column_stack([np.r_[x1, x2], np.r_[y1, y2]])])
    b_age = np.append(b_age, np.zeros(n1 + n2))

preload_bubbles()

DT = 1 / 60
FPS = int(os.environ.get("SIM_FPS", "30"))
SECONDS = float(os.environ.get("SIM_SECONDS", "26"))
if FPS <= 0 or SECONDS <= 0:
    raise ValueError("SIM_FPS와 SIM_SECONDS는 0보다 커야 한다")
FRAMES = max(1, round(SECONDS * FPS))
SUBSTEPS = max(1, round((1 / FPS) / DT))

def step(t):
    global b_pos, b_age, p_pos, p_cls, p_att
    # ---- 주입: 급광 22 입자/s, 기포 55 개/s (Jg 비례 시각화)
    if len(p_pos) < MAXP and rng.random() < 22 * DT:
        spawn_particles(1)
    nb = rng.poisson(55 * DT)
    if len(b_pos) + nb < MAXB and nb:
        spawn_bubbles(nb)

    # ---- 기포 이동
    if len(b_pos):
        ux, uy = fluid_velocity(b_pos[:, 0], b_pos[:, 1])
        in_froth = b_pos[:, 1] >= PULP_TOP
        vy = np.where(in_froth, 0.014, V_BUBBLE) + uy * np.where(in_froth, 0.0, 0.55)
        vx = np.where(in_froth,
                      np.sign(b_pos[:, 0] + 1e-9) * 0.085,      # 립으로 횡이동
                      ux * 0.55)
        wob = rng.normal(0, 0.02, b_pos.shape)
        b_pos = b_pos + np.column_stack([vx, vy]) * DT + wob * np.sqrt(DT) * (~in_froth[:, None])
        b_pos[:, 0] = np.clip(b_pos[:, 0], -R + 0.012, R - 0.012)
        b_age += DT
        # 월류 (정광) 또는 이탈
        gone = ((b_pos[:, 1] > LIP - 0.03) & (np.abs(b_pos[:, 0]) > R - 0.08)) | (b_pos[:, 1] > LIP + 0.02)
        if gone.any():
            for bi in np.nonzero(gone)[0]:
                riders = np.nonzero(p_att == bi)[0]
                for pi in riders:
                    if p_cls[pi] == GANGUE:
                        counts["conc_gangue"] += 1
                    else:
                        counts["conc_ag"] += 1
                p_att[p_att == bi] = -2          # 회수됨 → 제거 표시
            keep = ~gone
            remap = np.cumsum(keep) - 1
            b_pos = b_pos[keep]; b_age = b_age[keep]
            live = p_att >= 0
            p_att[live] = remap[p_att[live]]
        alive = p_att != -2
        p_pos, p_cls, p_att = p_pos[alive], p_cls[alive], p_att[alive]

    # ---- 입자 이동
    if len(p_pos):
        free = p_att == -1
        ux, uy = fluid_velocity(p_pos[:, 0], p_pos[:, 1])
        vx = ux; vy = uy - V_SETTLE
        noise = rng.normal(0, 0.012, p_pos.shape)
        upd = np.column_stack([vx, vy]) * DT + noise * np.sqrt(DT)
        p_pos[free] = p_pos[free] + upd[free]
        # 부착 입자는 기포에 승차
        att = np.nonzero(p_att >= 0)[0]
        if len(att):
            p_pos[att] = b_pos[p_att[att]] + np.array([0.004, -0.006])
        p_pos[:, 0] = np.clip(p_pos[:, 0], -R + 0.008, R - 0.008)
        p_pos[:, 1] = np.clip(p_pos[:, 1], 0.015, LIP - 0.005)

        # ---- 미광 배출 (저부 → 다트밸브). 저부 전역에서 확률 배출.
        tail = free & (p_pos[:, 1] < 0.22) & (rng.random(len(p_pos)) < 0.002)
        if tail.any():
            for pi in np.nonzero(tail)[0]:
                if p_cls[pi] == GANGUE:
                    counts["tail_gangue"] += 1
                else:
                    counts["tail_ag"] += 1
            keep = ~tail
            p_pos, p_cls, p_att = p_pos[keep], p_cls[keep], p_att[keep]

def attach_pass():
    global p_att
    if not len(b_pos) or not len(p_pos):
        return
    freeidx = np.nonzero(p_att == -1)[0]
    if not len(freeidx):
        return
    # 셀 격자 이웃 검색 — O(N)
    cellsz = 0.024
    bidx = {}
    for j, (bx, by) in enumerate(b_pos):
        bidx.setdefault((int(bx // cellsz), int(by // cellsz)), []).append(j)
    P_ATT = {FAST: 0.45, SLOW: 0.07, GANGUE: 0.008}
    for pi in freeidx:
        px, py = p_pos[pi]
        if py >= PULP_TOP:      # 거품층에서는 신규 부착 없음
            continue
        cx, cy = int(px // cellsz), int(py // cellsz)
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in bidx.get((cx + dx, cy + dy), ()):  # 이웃 기포
                    d = (b_pos[j, 0] - px) ** 2 + (b_pos[j, 1] - py) ** 2
                    if d < 0.012 ** 2:
                        best = j; break
        if best is not None and rng.random() < P_ATT[p_cls[pi]]:
            p_att[pi] = best

def drainage_pass():
    """거품층 배수 — 맥석·지연부선이 탈착해 펄프로 되돌아간다."""
    global p_att, p_pos
    att = np.nonzero(p_att >= 0)[0]
    for pi in att:
        y = p_pos[pi, 1]
        if y >= PULP_TOP:
            p_drop = {FAST: 0.001, SLOW: 0.012, GANGUE: 0.06}[p_cls[pi]]
        else:
            p_drop = {FAST: 0.0004, SLOW: 0.004, GANGUE: 0.02}[p_cls[pi]]
        if rng.random() < p_drop:
            p_att[pi] = -1
            p_pos[pi, 1] = min(p_pos[pi, 1], PULP_TOP - 0.01)

# ---------- 렌더 ----------
fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
fig.patch.set_facecolor("#10161C")
ax = fig.add_axes([0.035, 0.06, 0.46, 0.86]); ax.set_facecolor("#141C24")
ax2 = fig.add_axes([0.565, 0.56, 0.40, 0.34]); ax2.set_facecolor("#141C24")
ax3 = fig.add_axes([0.565, 0.10, 0.40, 0.34]); ax3.set_facecolor("#141C24")
INK, SUB, AG, WATER = "#DFE7EE", "#8AA0B4", "#E0A835", "#3D97A8"

for a_ in (ax2, ax3):
    for sp in a_.spines.values():
        sp.set_color("#31404D")
    a_.tick_params(colors=SUB, labelsize=8)

# 정적 배경 (셀 구조)
def draw_cell():
    ax.set_xlim(-1.15, 1.15); ax.set_ylim(-0.50, 2.10)
    ax.set_aspect("equal"); ax.axis("off")
    # 동체
    ax.plot([-R, -R], [0, G.shell_height_m], color=SUB, lw=2)
    ax.plot([R, R], [0, G.shell_height_m], color=SUB, lw=2)
    cone = Polygon([(-R, 0), (-0.06, -0.29), (0.06, -0.29), (R, 0)],
                   closed=False, fill=False, edgecolor=SUB, lw=2)
    ax.add_patch(cone)
    ax.plot([-0.06, -0.06], [-0.29, -0.40], color=SUB, lw=2)
    ax.plot([0.06, 0.06], [-0.29, -0.40], color=SUB, lw=2)
    # 거품층·립
    ax.add_patch(Rectangle((-R, PULP_TOP), 2 * R, LIP - PULP_TOP,
                           facecolor="#3A3120", edgecolor="none", zorder=1))
    ax.plot([-R, R], [PULP_TOP, PULP_TOP], color="#6B5A2A", lw=0.8, ls="--")
    # 런더
    for sgn in (-1, 1):
        ax.add_patch(Rectangle((sgn * R if sgn > 0 else -R - 0.11, LIP - 0.06),
                               0.11, 0.14, facecolor="none", edgecolor=AG, lw=1.6))
    ax.annotate("", xy=(-R - 0.24, LIP + 0.02), xytext=(-R - 0.11, LIP + 0.02),
                arrowprops=dict(arrowstyle="-|>", color=AG, lw=1.8))
    ax.text(-R - 0.26, LIP + 0.02, "정광", color=AG, fontsize=10, ha="right", va="center")
    # 데크·중공축·로터리 조인트
    deck = G.shell_height_m + 0.18
    ax.plot([-R - 0.06, R + 0.06], [deck, deck], color=SUB, lw=2.4)
    ax.add_patch(Rectangle((-SHAFT_R, ROTOR_Y + 0.03), 2 * SHAFT_R, deck + 0.30 - ROTOR_Y,
                           facecolor="#232E38", edgecolor=SUB, lw=1.2, zorder=3))
    ax.add_patch(Rectangle((-BORE_R, ROTOR_Y + 0.03), 2 * BORE_R, deck + 0.30 - ROTOR_Y,
                           facecolor="#2E5E6B", edgecolor="none", zorder=4))
    ax.add_patch(Rectangle((-0.085, deck + 0.30), 0.17, 0.14,
                           facecolor="#232E38", edgecolor=WATER, lw=1.6, zorder=4))
    ax.annotate("", xy=(-0.085, deck + 0.37), xytext=(-0.32, deck + 0.37),
                arrowprops=dict(arrowstyle="-|>", color=WATER, lw=1.8))
    ax.text(-0.34, deck + 0.37, f"급기 {A.air_flow_m3h:.1f} m³/h", color=WATER,
            fontsize=9, ha="right", va="center")
    ax.text(0.11, deck + 0.30, "로터리 조인트", color=SUB, fontsize=8.5, va="center")
    # 로터·스테이터
    ax.add_patch(Polygon([(-ROTOR_R, ROTOR_Y), (ROTOR_R, ROTOR_Y),
                          (ROTOR_R * 0.8, ROTOR_Y + 0.075), (-ROTOR_R * 0.8, ROTOR_Y + 0.075)],
                         facecolor="#33414E", edgecolor=INK, lw=1.2, zorder=5))
    for sgn in (-1, 1):
        ax.add_patch(Rectangle((sgn * I.stator_od_m / 2 - 0.012, ROTOR_Y - 0.01),
                               0.024, 0.10, facecolor="#232E38", edgecolor=SUB, lw=1))
    # 급광 박스·미광 밸브
    ax.add_patch(Rectangle((-R - 0.16, 0.98), 0.16, 0.20, facecolor="none", edgecolor=SUB, lw=1.6))
    ax.annotate("", xy=(-R - 0.02, 1.07), xytext=(-R - 0.30, 1.07),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.6))
    ax.text(-R - 0.31, 1.11, "급광 + 여액 순환", color=INK, fontsize=9, ha="right")
    ax.add_patch(Rectangle((R + 0.02, 0.02), 0.13, 0.22, facecolor="none", edgecolor=SUB, lw=1.6))
    ax.annotate("", xy=(R + 0.085, -0.22), xytext=(R + 0.085, 0.0),
                arrowprops=dict(arrowstyle="-|>", color=SUB, lw=1.6))
    ax.text(R + 0.13, -0.24, "미광", color=SUB, fontsize=9)
    ax.text(0, 2.02, "FC-201 러퍼 — 중공축 급기 작동 시뮬레이션",
            color=INK, fontsize=12.5, ha="center", weight="bold")
    ax.text(0, -0.44, "속도 스케일: 기포군 6.5 cm/s · 침강 3.2 mm/s · 순환 ≈0.5 m/s (설계 계산값)\n"
            "Ag 입자 비율은 가시화를 위해 과장 (실제 급광 0.59 wt%)",
            color=SUB, fontsize=8, ha="center", va="top")

draw_cell()

# ODE 기동 곡선 (수치해석) — 정적
t_ode = np.array(TR.times_min); r_ode = np.array(TR.recovery_ag) * 100
ax3.plot(t_ode, r_ode, color=AG, lw=2)
ax3.axhline(RES.recovery("Ag") * 100, color=SUB, lw=0.8, ls="--")
ax3.axvline(TR.time_to_95pct_min, color=WATER, lw=0.8, ls=":")
ax3.text(TR.time_to_95pct_min + 0.8, 30, f"t95 = {TR.time_to_95pct_min:.0f} min",
         color=WATER, fontsize=9)
ax3.text(38, RES.recovery("Ag") * 100 - 7, f"정상상태 {RES.recovery('Ag')*100:.1f} %",
         color=SUB, fontsize=8.5, ha="right")
ax3.set_xlim(0, 40); ax3.set_ylim(0, 105)
ax3.set_xlabel("기동 후 시간 (min)", color=SUB, fontsize=9)
ax3.set_title("수치해석 — 회로 기동 과도응답 (CSTR ODE·RK4)", color=INK, fontsize=10)
ax3.set_ylabel("회로 Ag 회수율 (%)", color=SUB, fontsize=9)

# 동적 아티스트
sc_b = ax.scatter([], [], s=13, facecolors="none", edgecolors="#9FD4DE", linewidths=0.7, zorder=6)
sc_g = ax.scatter([], [], s=5, c="#7B8794", zorder=7)
sc_ag = ax.scatter([], [], s=13, c=AG, zorder=8)
sc_att = ax.scatter([], [], s=18, c="#FFCE63", edgecolors="#8A6410", linewidths=0.6, zorder=9)
hud = ax.text(-1.13, 1.62, "", color=INK, fontsize=9.5, va="top")
note = None
ln_rec, = ax2.plot([], [], color=AG, lw=2, label="입자 시뮬레이션")
ax2.set_xlim(0, SECONDS); ax2.set_ylim(0, 105)
ax2.set_xlabel("시뮬레이션 시간 (s)", color=SUB, fontsize=9)
ax2.set_ylabel("Ag 입자 회수율 (%)", color=SUB, fontsize=9)
ax2.set_title("축약차수 입자 모델 — 기포 부착으로 회수된 Ag", color=INK, fontsize=10)

writer_cls = matplotlib.animation.FFMpegWriter
writer = writer_cls(fps=FPS, codec="h264",
                    extra_args=["-pix_fmt", "yuv420p", "-crf", "23", "-preset", "medium"])
out = sys.argv[1] if len(sys.argv) > 1 else "fc201-simulation.mp4"
with writer.saving(fig, out, dpi=100):
    t = 0.0
    for frame in range(FRAMES):
        for _ in range(SUBSTEPS):
            step(t); attach_pass(); drainage_pass(); t += DT
        # 아티스트 갱신
        sc_b.set_offsets(b_pos if len(b_pos) else np.zeros((0, 2)))
        free_g = (p_att == -1) & (p_cls == GANGUE)
        free_a = (p_att == -1) & (p_cls != GANGUE)
        attm = p_att >= 0
        sc_g.set_offsets(p_pos[free_g] if free_g.any() else np.zeros((0, 2)))
        sc_ag.set_offsets(p_pos[free_a] if free_a.any() else np.zeros((0, 2)))
        sc_att.set_offsets(p_pos[attm] if attm.any() else np.zeros((0, 2)))
        ag_in = counts["feed_ag"]
        rec = counts["conc_ag"] / ag_in * 100 if ag_in else 0.0
        hist_t.append(t); hist_rec.append(rec)
        ln_rec.set_data(hist_t, hist_rec)
        hud.set_text(
            f"t = {t:5.1f} s\n"
            f"기포 {len(b_pos):3d}개 · 입자 {len(p_pos):3d}개\n"
            f"정광 회수 Ag {counts['conc_ag']}  맥석 {counts['conc_gangue']}\n"
            f"미광 배출 Ag {counts['tail_ag']}  맥석 {counts['tail_gangue']}"
        )
        writer.grab_frame()
        if frame % 120 == 0:
            print(f"frame {frame}/{FRAMES} t={t:.1f}s bubbles={len(b_pos)} particles={len(p_pos)}", flush=True)

ag_in = counts["feed_ag"]
print("DONE", out)
print("누적 급광 입자 기준 Ag 회수율:",
      f"{counts['conc_ag']/ag_in*100:.1f} %" if ag_in else "N/A",
      "| conc gangue:", counts["conc_gangue"], "| tail:", counts["tail_ag"], counts["tail_gangue"])
