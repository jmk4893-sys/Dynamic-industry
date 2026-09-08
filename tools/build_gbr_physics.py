#!/usr/bin/env python3
"""GBR-301 물리 시뮬레이션 화면을 찍는다 — `docs/drawings/pv-gbr-physics.html`.

3D 운전 영상은 **보간**이다. 시각을 주면 자세를 돌려주는 함수라, 유리가 슬롯에
「놓이는」 장면도 그냥 재생된다. 놓이는 자리에 받칠 것이 있는지는 묻지 않는다.

이 화면은 다르다. 유리는 **적분된다** — 폭 1,400 을 가로지르는 절점 사슬이고,
마디마다 중력과 이웃의 굽힘력과 접촉력을 받는다. 콤포크가 소하강을 시작하면
아무도 유리의 자세를 정해 주지 않는다. 선반이 받으면 얹히고, 안 받으면 떨어진다.

**그래서 하나가 드러났다.** 슬롯 선반 레일은 z ±702.5…757.5 에 있었고 유리
가장자리는 ±700 이다 — 2.5 mm 가 비어서 유리가 어느 레일에도 닿지 않았다.
REV.47 의 「캐리지 밑면이 80 mm 떠 있다」와 같은 종류의 끊긴 하중 경로인데,
그것은 눈으로 보였고 이것은 **떨어뜨려 봐야** 보인다. 화면 왼쪽이 그 배치고
오른쪽이 채택 배치다. 같은 적분기가 둘을 돌린다.

수치는 전부 `gbr_dynamics` · `gbr_load` 에서 온다. 손으로 옮긴 숫자가 없다.

실행:  PYTHONPATH=src python3 tools/build_gbr_physics.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pv_preprocess import afr, gbr_dynamics as gd, gbr_load as gl   # noqa: E402
from pv_preprocess import handoff, layout                           # noqa: E402

OUT = ROOT / "docs" / "drawings" / "pv-gbr-physics.html"

#: 유리 띠를 몇 마디로 나눠 적분하는가 (마디 간격 50 mm — 선반선 ±650 이 절점에
#: 정확히 온다). 파이썬 유한요소(140 요소)보다 성기지만 같은 정적 처짐으로
#: 수렴해야 한다 — `tools/check_gbr_physics.mjs` 가 그것을 잰다.
NODES = 29
#: 화면 프레임과 프레임당 부분걸음.
#:
#: 반음함 오일러는 dt < 2/ω_max 를 넘으면 발산한다. 이산 굽힘 사슬의 최고 진동수는
#: ω_max = 4·√(EI / (ρA·h⁴)) 라 마디가 촘촘할수록 시간각이 작아야 한다 — 그래서
#: 마디 수와 부분걸음을 **같이** 정한다. 지금 조합은 한계의 1/4 이다.
FPS, SUBSTEPS = 60, 240
#: 콤포크 위에서 유리가 먼저 자리를 잡게 두는 시간 (s). 이 예열이 없으면 첫 걸음의
#: 반력이 0 이라 「포크를 이미 놓았다」로 읽힌다.
PREROLL_S = 1.2
#: 소하강이 끝나고 콤포크가 X 로 빠지기까지 기다리는 시간 (s) — GA 흐름 6번이다.
#: **여기서 종전 배치가 드러난다.** 선반이 유리를 안 물었으므로, 포크가 빠지는
#: 순간 유리 밑에 아무것도 없다.
RETRACT_S = 0.6

#: 종전 배치 — 3D 가 REV.59 까지 들고 있던 값이다 (z ±730 · 폭 55).
LEGACY_SHELF_Z_MM, LEGACY_SHELF_W_MM = 730.0, 55.0
#: 종전 콤포크 — z ±620 · 깊이 95.
LEGACY_FORK_Z_MM, LEGACY_FORK_H_MM = 620.0, 95.0


def layout_case(name: str, shelf_z: float, shelf_w: float,
                fork_z: float, fork_h: float) -> dict[str, object]:
    """한 배치의 단면 형상 (mm) — 유리·선반·포크의 z 구간과 높이."""
    return {
        "name": name,
        "shelf": [round(shelf_z - shelf_w / 2, 3), round(shelf_z + shelf_w / 2, 3)],
        "fork": [round(fork_z - gl.FORK_W_MM / 2, 3),
                 round(fork_z + gl.FORK_W_MM / 2, 3)],
        "forkH": fork_h,
        "bearing": round(gl.GLASS_W_MM / 2 - (shelf_z - shelf_w / 2), 3),
    }


def scene() -> dict[str, object]:
    """장면 — 전부 mm, 셀 단면(z–높이) 좌표계다."""
    return {
        "nodes": NODES, "fps": FPS, "substeps": SUBSTEPS,
        "preroll": PREROLL_S, "retract": RETRACT_S,
        "glassW": gl.GLASS_W_MM, "glassT": afr.LAMINATE_T_MM,
        "areaKgM2": afr.LAMINATE_KG_M2, "eMpa": afr.GLASS_E_MPA,
        "allowMpa": afr.GLASS_ALLOW_MPA,
        "slotPitch": gl.slot_pitch_mm(), "shelfT": gl.SHELF_T_MM,
        "approach": gl.SET_DOWN_APPROACH_MM, "setDown": gl.SET_DOWN_MM,
        "v": gl.SERVO_V_MM_S, "a": gl.SERVO_A_MM_S2,
        "damping": gd.GLASS_DAMPING,
        "cases": [
            layout_case("종전 배치", LEGACY_SHELF_Z_MM, LEGACY_SHELF_W_MM,
                        LEGACY_FORK_Z_MM, LEGACY_FORK_H_MM),
            layout_case("채택 배치", gl.SHELF_Z_MM, gl.SHELF_W_MM,
                        gl.FORK_OFFSET_MM, gl.FORK_H_MM),
        ],
    }


def numbers() -> dict[str, object]:
    """옆에 띄우는 해석 결과 — 같은 함수가 시험과 도면집에도 간다."""
    fork, sd = gd.fork_static(), gd.set_down()
    shelf, on_fork = gd.glass_on_shelf(), gd.glass_on_fork()
    depth_lo, depth_hi = gd.fork_depth_window_mm()
    droop_lo, droop_hi = gd.fork_droop_span_mm()
    return {
        "rev": "REV.60",
        "forkFree": fork.free_mm, "forkDroop": fork.droop_mm,
        "forkStress": fork.stress_mpa, "forkKg": fork.self_kg, "forkHz": fork.hz,
        "forkDepth": gl.FORK_H_MM, "depthWindow": [depth_lo, depth_hi],
        "depthRoom": gd.fork_depth_room_mm(),
        "droopSpan": [droop_lo, droop_hi], "droopBudget": gd.fork_droop_budget_mm(),
        "shelfSag": shelf["sag_mm"], "shelfStress": shelf["stress_mpa"],
        "forkSag": on_fork["sag_mm"], "forkGlassStress": on_fork["stress_mpa"],
        "sagAtFork": gd.glass_sag_at_fork_mm(),
        "setDownRequired": gd.set_down_required_mm(), "setDown": gl.SET_DOWN_MM,
        "dwellLimit": gd.dwell_limit_s(), "maxDwell": gd.max_dwell_s(),
        "allowStore": gd.allow_mpa(gd.max_dwell_s()),
        "allowEvent": gd.allow_mpa(gd.SET_DOWN_EVENT_S),
        "impactV": sd.contact_v_mm_s, "impactVLimit": gd.set_down_v_limit_mm_s(),
        "impactSag": sd.peak_sag_mm, "impactStress": sd.peak_stress_mpa,
        "daf": sd.amplification, "verify": gd.set_down_verify(),
        "mastHz": gd.mast_hz(), "mastSway": gd.mast_sway_mm(),
        "settle": gd.settle_s(), "settleBudget": gl.STOP_SETTLE_S,
        "accel": gd.accel_limits_mm_s2(), "accelBinding": gd.accel_binding(),
        "accelHeadroom": gd.accel_headroom(), "accelDesign": gl.SERVO_A_MM_S2,
        "reachable": len(gd.reachable_slots()), "slots": handoff.SLOTS_PER_CARRIAGE,
        "deckTop": float(layout.LINE_TRANSFER_MM),
        "checks": [[k, v[0], v[1], v[2]] for k, v in gd.checks().items()],
    }


ENGINE = r"""
/* ── 유리는 적분된다 — 이산 Euler–Bernoulli 사슬 + 한 방향 접촉 ───────────
 *
 * 외부 엔진을 쓰지 않는다. 저장소 규약이 「해석기는 표준 라이브러리만」이고,
 * 영상이 CDN 유무로 갈리면 다시 찍을 수 없기 때문이다.
 *
 * 유리 단면을 폭 방향으로 N 마디로 자른다. 마디마다 질량 ρA·h 를 두고, 굽힘은
 * 곡률의 2 차 차분에서 낸다 —
 *
 *     κ_i = (u_{i-1} − 2u_i + u_{i+1}) / h²          (곡률)
 *     f_i = −EI/h² · (κ_{i-1} − 2κ_i + κ_{i+1})      (선하중)
 *
 * 범위 밖 κ 를 0 으로 두면 그것이 곧 자유단 조건(모멘트 0 · 전단 0)이라, 유리
 * 가장자리가 저절로 자유롭게 처진다. 접촉은 **한 방향**이다: 받침 위에 있고
 * 받침면보다 내려간 마디만 위로 밀린다 (당기지 않는다).
 *
 * 적분은 반음함 오일러다 — `dynamics.py` 와 같은 방식이고, 접촉 강성이 커서
 * 시간각을 잘게 쓴다. 안정 한계는 dt < 2/ω_max 이고 그것을 `PH.stable()` 이 잰다.
 */
class Strip {
  constructor(cfg) {
    this.n = cfg.nodes;
    this.w = cfg.glassW;
    this.h = this.w / (this.n - 1);
    this.t = cfg.glassT;
    /* 폭 1 mm 띠 기준 — 화면에 쓰는 것은 처짐이라 폭이 상쇄된다. */
    this.EI = cfg.eMpa * Math.pow(this.t, 3) / 12;          // N·mm²/mm
    /* 단위계는 `beam.py` 와 같다 — mm · N · s · tonne. F[N] = m[tonne]·a[mm/s²] 라
       면밀도 11 kg/m² 는 11e-9 tonne/mm² 다. kg 으로 두면 하중이 1,000 배 커지고
       관성이 1,000 배 작아져 사슬이 첫 걸음에 날아간다. */
    this.mLine = cfg.areaKgM2 * 1e-9;                       // tonne/mm² (폭 1 mm)
    this.mNode = this.mLine * this.h;                       // tonne
    this.g = 9806.65;                                       // mm/s²
    this.c = cfg.damping;
    this.u = new Float64Array(this.n);                      // 처짐 (아래 +)
    this.v = new Float64Array(this.n);
    this.k = new Float64Array(this.n);
    this.f = new Float64Array(this.n);
    this.z = Array.from({ length: this.n }, (_, i) => -this.w / 2 + i * this.h);
    /* 접촉 강성 — 굽힘강성의 100 배면 파고드는 깊이가 0.01 mm 밑이라 강체 받침이다.
       더 키우면 접촉 진동수가 시간각의 안정 한계를 넘는다. */
    this.kc = 100 * this.EI / Math.pow(this.h, 3);
    this.cc = 2 * 0.25 * Math.sqrt(this.kc * this.mNode);
    /* 안정 한계를 정하는 것은 접촉과 굽힘 중 빠른 쪽이다. */
    this.omegaMax = Math.max(
      Math.sqrt(this.kc / this.mNode),
      4 * Math.sqrt(this.EI / (this.mLine * Math.pow(this.h, 4))));
  }
  /* dt 가 안정 한계 안인가 — 반음함 오일러는 dt < 2/ω 를 넘으면 발산한다. */
  stable(dt) { return dt < 2 / this.omegaMax; }

  step(dt, supports) {
    const n = this.n, h = this.h, EI = this.EI, u = this.u, v = this.v;
    const k = this.k, f = this.f;
    for (let i = 0; i < n; i += 1) {
      k[i] = (i === 0 || i === n - 1) ? 0
        : (u[i - 1] - 2 * u[i] + u[i + 1]) / (h * h);
    }
    for (let i = 0; i < n; i += 1) {
      const km = i > 0 ? k[i - 1] : 0, kp = i < n - 1 ? k[i + 1] : 0;
      f[i] = -EI / (h * h) * (km - 2 * k[i] + kp) * h;      // 마디 힘 [N]
      f[i] += this.mNode * this.g;                          // 자중
      f[i] -= this.c * 2 * Math.sqrt(EI / (h * h * h) * this.mNode) * v[i];
    }
    /* 접촉 — 받침은 {z0, z1, top} 이고 top 은 그 위 유리 하면의 높이다. */
    for (const s of supports) {
      for (let i = 0; i < n; i += 1) {
        if (this.z[i] < s.z0 || this.z[i] > s.z1) continue;
        const pen = u[i] - s.u;                             // 받침보다 내려간 양
        if (pen <= 0) continue;
        const fc = this.kc * pen + this.cc * Math.max(v[i], 0);
        f[i] -= fc;
        s.load = (s.load || 0) + fc;
      }
    }
    for (let i = 0; i < n; i += 1) {
      v[i] += f[i] / this.mNode * dt;
      u[i] += v[i] * dt;
    }
  }
  /* 최대 굽힘응력 [MPa] — σ = E·(t/2)·κ. */
  stress() {
    let m = 0;
    for (let i = 1; i < this.n - 1; i += 1) {
      const kk = Math.abs((this.u[i - 1] - 2 * this.u[i] + this.u[i + 1])
        / (this.h * this.h));
      m = Math.max(m, kk);
    }
    return m * (this.t / 2) * SCENE.eMpa;
  }
  span() { let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < this.n; i += 1) { lo = Math.min(lo, this.u[i]); hi = Math.max(hi, this.u[i]); }
    return [lo, hi]; }
}

/* 사다리꼴 프로파일 — `gbr_load.move_s()` 와 같은 식이다. */
function profile(stroke, v, a) {
  const tri = stroke <= v * v / a;
  const T = tri ? 2 * Math.sqrt(stroke / a) : v / a + stroke / v;
  return { T, at(t) {
    if (t <= 0) return 0;
    if (t >= T) return stroke;
    if (tri) {
      const half = T / 2;
      return t < half ? 0.5 * a * t * t
        : stroke - 0.5 * a * (T - t) * (T - t);
    }
    const tr = v / a;
    if (t < tr) return 0.5 * a * t * t;
    if (t > T - tr) return stroke - 0.5 * a * (T - t) * (T - t);
    return 0.5 * a * tr * tr + v * (t - tr);
  } };
}
"""


DRIVER = r"""
/* ── 두 배치를 같은 적분기로 돌린다 ──────────────────────────────────────
 * 다른 것은 선반 레일의 z 구간과 콤포크의 z·깊이뿐이다. 초기 자세는 둘 다
 * 「콤포크 위에 얹혀 진입 높이에 떠 있는 유리」고, 거기서 소하강을 시작한다.
 */
const SCENE = __SCENE__, NUM = __NUM__;
const DT = 1 / (SCENE.fps * SCENE.substeps);

function makeRun(cs) {
  const strip = new Strip(SCENE);
  const drop = profile(SCENE.setDown, SCENE.v, SCENE.a);
  /* 처짐 좌표계: 0 = 레일 상면. 유리는 진입 높이만큼 위(음수)에서 시작한다. */
  for (let i = 0; i < strip.n; i += 1) strip.u[i] = -SCENE.approach;
  return {
    cs, strip, drop, t: -SCENE.preroll, done: false, released: false,
    releaseT: null, fell: false, retracted: false, peak: 0, peakStress: 0,
    settled: null,
    supports: {
      shelf: [-1, 1].map((s) => ({ z0: s < 0 ? -cs.shelf[1] : cs.shelf[0],
                                   z1: s < 0 ? -cs.shelf[0] : cs.shelf[1], u: 0 })),
      fork: [-1, 1].map((s) => ({ z0: s < 0 ? -cs.fork[1] : cs.fork[0],
                                  z1: s < 0 ? -cs.fork[0] : cs.fork[1],
                                  u: -SCENE.approach })),
    },
  };
}

function stepRun(r, dt) {
  if (r.done) return;
  r.t += dt;
  /* 예열 구간(t < 0)에서는 포크가 멈춰 있다 — 유리가 먼저 제 자리를 잡는다. */
  const forkU = -SCENE.approach + r.drop.at(r.t);
  for (const s of r.supports.fork) { s.u = forkU; s.load = 0; }
  for (const s of r.supports.shelf) s.load = 0;
  /* 흐름 6번 — 소하강이 끝나면 콤포크가 X 로 빠진다. 그 순간 유리를 잡고 있는
     것은 선반뿐이고, 선반이 유리를 안 물었으면 잡는 것이 없다. */
  if (!r.retracted && r.t > r.drop.T + SCENE.retract) r.retracted = true;
  /* 접촉은 한 방향이라 둘을 항상 켜 둔다 — 「놓았다」는 반력이 스스로 말한다. */
  r.strip.step(dt, r.retracted ? r.supports.shelf
    : r.supports.shelf.concat(r.supports.fork));
  if (r.t < 0) return;
  const forkLoad = r.supports.fork.reduce((a, s) => a + (s.load || 0), 0);
  const shelfLoad = r.supports.shelf.reduce((a, s) => a + (s.load || 0), 0);
  if (!r.released && shelfLoad > 0 && forkLoad <= 1e-9) {
    r.released = true; r.releaseT = r.t;
  }
  const [, hi] = r.strip.span();
  r.peak = Math.max(r.peak, hi);
  if (r.released) r.peakStress = Math.max(r.peakStress, r.strip.stress());
  /* 한 칸 아래 슬롯까지 내려가면 «떨어졌다»로 본다. */
  if (hi > SCENE.slotPitch) { r.fell = true; r.done = true; }
}

/* ── 그리기 ─────────────────────────────────────────────────────────── */
const cv = document.getElementById('c'), cx = cv.getContext('2d');
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function draw(runs) {
  const W = cv.width, H = cv.height, half = W / 2;
  cx.clearRect(0, 0, W, H);
  runs.forEach((r, i) => drawOne(r, i * half, half, H));
}

function drawOne(r, x0, w, h) {
  const padX = 42, padY = 64;
  const sx = (w - 2 * padX) / SCENE.glassW;
  const sy = (h - 2 * padY) / (SCENE.slotPitch * 1.6);
  const X = (z) => x0 + w / 2 + z * sx;
  const Y = (u) => padY + (u + SCENE.approach) * sy;
  cx.save();
  cx.strokeStyle = css('--rule'); cx.lineWidth = 1;
  cx.strokeRect(x0 + 6, 6, w - 12, h - 12);
  cx.fillStyle = css('--muted'); cx.font = '600 15px system-ui';
  cx.fillText(r.cs.name, x0 + 18, 28);
  cx.font = '12px ui-monospace,monospace';
  cx.fillText(`선반 z ±${r.cs.shelf[0]}…${r.cs.shelf[1]} · 물림 ${r.cs.bearing.toFixed(1)} mm`,
    x0 + 18, 46);

  /* 한 칸 아래 유리 — 못 넘는 바닥이다. */
  cx.fillStyle = css('--tint');
  cx.fillRect(X(-SCENE.glassW / 2), Y(SCENE.slotPitch), SCENE.glassW * sx, 4);
  cx.fillStyle = css('--muted'); cx.font = '11px system-ui';
  cx.fillText('한 칸 아래 유리', X(-SCENE.glassW / 2), Y(SCENE.slotPitch) + 16);

  /* 선반 레일 */
  cx.fillStyle = css('--ink');
  for (const s of r.supports.shelf) {
    cx.fillRect(X(s.z0), Y(0), (s.z1 - s.z0) * sx, SCENE.shelfT * sy);
  }
  /* 콤포크 — X 로 빠지면 단면에서 사라진다. */
  if (!r.retracted) {
    cx.fillStyle = css('--blue');
    for (const s of r.supports.fork) {
      cx.fillRect(X(s.z0), Y(s.u), (s.z1 - s.z0) * sx, r.cs.forkH * sy);
    }
  }
  /* 유리 */
  cx.strokeStyle = r.fell ? css('--red') : css('--green');
  cx.lineWidth = 3; cx.beginPath();
  for (let i = 0; i < r.strip.n; i += 1) {
    const px = X(r.strip.z[i]), py = Y(r.strip.u[i]);
    i ? cx.lineTo(px, py) : cx.moveTo(px, py);
  }
  cx.stroke();
  cx.restore();
}

/* ── 운전 ───────────────────────────────────────────────────────────── */
let runs, playing = true, speed = 1;
function reset() { runs = SCENE.cases.map(makeRun); }
reset();

function tick() {
  if (playing) {
    for (let k = 0; k < SCENE.substeps * speed; k += 1) {
      for (const r of runs) stepRun(r, DT);
    }
  }
  draw(runs);
  report();
  requestAnimationFrame(tick);
}

const fmt = (v, d = 2) => (v === null || v === undefined || !isFinite(v))
  ? '—' : Number(v).toFixed(d);

function report() {
  const rows = runs.map((r) => {
    const [, hi] = r.strip.span();
    const verdict = r.fell ? '떨어진다'
      : (r.released ? '얹혔다' : (r.retracted ? '포크가 빠졌다' : '내려가는 중'));
    return `<tr><td>${r.cs.name}</td>
      <td class="num">${fmt(hi, 1)}</td>
      <td class="num">${fmt(r.peakStress, 1)}</td>
      <td class="num">${r.releaseT === null ? '—' : fmt(r.releaseT, 2)}</td>
      <td class="${r.fell ? 'bad' : 'good'}">${verdict}</td></tr>`;
  }).join('');
  document.getElementById('live').innerHTML = rows;
  document.getElementById('clock').textContent = fmt(runs[0].t, 2) + ' s';
}

document.getElementById('play').onclick = (e) => {
  playing = !playing; e.target.textContent = playing ? '일시정지' : '이어서';
};
document.getElementById('restart').onclick = () => reset();
document.getElementById('speed').onchange = (e) => { speed = Number(e.target.value); };

/* ── 시험 훅 — 적분기가 파이썬 유한요소와 같은 답을 내는가 ─────────────── */
window.PH = {
  scene: SCENE, numbers: NUM,
  stable: () => runs.every((r) => r.strip.stable(DT)),
  /* 채택 배치를 정지 상태까지 돌려 정착 처짐과 응력을 돌려준다. */
  settle(index = 1, seconds = 10) {
    const r = makeRun(SCENE.cases[index]);
    const n = Math.round((seconds + SCENE.preroll) / DT);
    for (let i = 0; i < n; i += 1) stepRun(r, DT);
    const [, hi] = r.strip.span();
    return { sag: hi, stress: r.strip.stress(), fell: r.fell,
             released: r.released, releaseT: r.releaseT,
             retracted: r.retracted };
  },
  run(index = 1, seconds = 10) { return this.settle(index, seconds); },
};
requestAnimationFrame(tick);
"""


TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GBR-301 물리 시뮬레이션 — 유리는 적분된다</title>
<meta name="description" content="무프레임 유리를 굽힘 사슬로 적분해 슬롯 선반이 실제로 받아 내는지 묻는다. 종전 배치에서는 떨어진다.">
<!-- 이 파일은 손으로 쓰지 않는다.
     생성  : tools/build_gbr_physics.py
     수치  : src/pv_preprocess/gbr_dynamics.py · gbr_load.py -->
<style>
:root {
  --ground:#EEF1F3; --sheet:#FFFFFF; --ink:#16202A; --muted:#5B6874; --rule:#C8D0D7;
  --tint:#E4EAEF; --red:#B5321F; --blue:#2A6CB0; --amber:#C8850A; --green:#2F7D4F;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --ground:#12181E; --sheet:#1A222A; --ink:#E4E9ED; --muted:#98A5B1; --rule:#34414D;
  --tint:#232D37; --red:#E0604A; --blue:#6FA8E6; --amber:#E6B04C; --green:#6CBF8A;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --ground:#12181E; --sheet:#1A222A; --ink:#E4E9ED; --muted:#98A5B1; --rule:#34414D;
  --tint:#232D37; --red:#E0604A; --blue:#6FA8E6; --amber:#E6B04C; --green:#6CBF8A;
  color-scheme: dark; }
* { box-sizing:border-box; }
body { margin:0; background:var(--ground); color:var(--ink);
  font:13.5px/1.5 "Pretendard",-apple-system,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",system-ui,sans-serif;
  font-variant-numeric:tabular-nums; }
code,.mono { font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace; }
.page { max-width:1400px; margin:0 auto; padding:18px 18px 40px; display:grid; gap:14px; }
header .eyebrow { font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
h1 { margin:4px 0 6px; font-size:22px; font-weight:600; }
.lede { margin:0; color:var(--muted); max-width:96ch; }
.layout { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:14px; align-items:start; }
.stage { background:var(--sheet); border:1px solid var(--rule); padding:8px; }
canvas { width:100%; height:auto; display:block; background:transparent; }
.side { display:grid; gap:12px; }
.card { background:var(--sheet); border:1px solid var(--rule); padding:10px 12px; display:grid; gap:6px; }
.card h2 { margin:0; font-size:12px; color:var(--muted); font-weight:600; letter-spacing:.04em; }
.kv { display:grid; grid-template-columns:auto 1fr; gap:2px 12px; font-size:12.5px; margin:0; }
.kv dt { color:var(--muted); } .kv dd { margin:0; text-align:right; }
.bad { color:var(--red); font-weight:600; } .good { color:var(--green); font-weight:600; }
.controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center;
  background:var(--sheet); border:1px solid var(--rule); padding:8px 12px; }
button,select { font:inherit; color:inherit; background:var(--sheet);
  border:1px solid var(--rule); border-radius:4px; padding:5px 10px; min-height:30px; cursor:pointer; }
button.primary { background:var(--ink); color:var(--sheet); border-color:var(--ink); }
table { border-collapse:collapse; width:100%; font-size:12px; }
th,td { text-align:left; padding:3px 8px 3px 0; border-bottom:1px solid var(--rule); }
th { color:var(--muted); font-weight:600; font-size:11px; }
td.num { text-align:right; }
.note { color:var(--muted); font-size:12px; margin:0; max-width:96ch; }
.wrap { overflow-x:auto; }
</style>
</head>
<body>
<main class="page">
<header>
  <div class="eyebrow">DYNAMIC INDUSTRY · GBR-301 · 물리 시뮬레이션 · ENGINEERING BASE __REV__</div>
  <h1>유리는 적분된다 — 놓이는 자리에 받칠 것이 있는가</h1>
  <p class="lede">3D 운전 영상은 시각을 주면 자세를 돌려주는 <b>보간</b>이다. 그래서 유리가 슬롯에 「놓이는」 장면도 그냥 재생되고,
  놓이는 자리에 받칠 것이 있는지는 묻지 않는다. 이 화면에서 무프레임 유리는 <b>폭 1,400 을 가로지르는 굽힘 사슬</b>이고,
  마디마다 중력·이웃의 굽힘력·한 방향 접촉력을 받는다. 콤포크가 소하강을 시작하면 아무도 자세를 정해 주지 않는다.
  왼쪽이 종전 배치, 오른쪽이 채택 배치다 — <b>같은 적분기</b>가 둘을 돌린다.
  옆의 수치는 전부 <code>gbr_dynamics</code> 가 푼 것이다.</p>
</header>

<div class="controls">
  <button class="primary" id="play" type="button">일시정지</button>
  <button id="restart" type="button">처음부터</button>
  <label>속도 <select id="speed">
    <option value="0.25">0.25×</option><option value="0.5">0.5×</option>
    <option value="1" selected>1×</option><option value="2">2×</option></select></label>
  <span class="mono" id="clock">0.00 s</span>
</div>

<div class="layout">
  <div class="stage"><canvas id="c" width="1360" height="520"></canvas></div>
  <div class="side">
    <div class="card">
      <h2>이 순간</h2>
      <div class="wrap"><table>
        <thead><tr><th>배치</th><th class="num">처짐 mm</th><th class="num">응력 MPa</th>
        <th class="num">놓은 시각 s</th><th>결과</th></tr></thead>
        <tbody id="live"></tbody></table></div>
    </div>
    <div class="card">
      <h2>콤포크 — 2 단 텔레스코픽 유한요소</h2>
      <dl class="kv" id="fork"></dl>
    </div>
    <div class="card">
      <h2>유리 — 띠 유한요소와 정적피로</h2>
      <dl class="kv" id="glass"></dl>
    </div>
    <div class="card">
      <h2>안착 충격 — 하이브리드</h2>
      <dl class="kv" id="impact"></dl>
    </div>
    <div class="card">
      <h2>마스트·가속도</h2>
      <dl class="kv" id="mast"></dl>
    </div>
  </div>
</div>

<div class="card">
  <h2>수치해석 판정</h2>
  <div class="wrap"><table>
    <thead><tr><th>항목</th><th class="num">값</th><th class="num">한계</th><th>판정</th></tr></thead>
    <tbody id="checks"></tbody></table></div>
  <p class="note">「승강 포락선」은 <b>미해결</b>로 남긴다 — 접힌 콤포크가 셔틀 데크(상면 __DECK__ mm) 위에 누워 있어
  낮은 슬롯으로 내려갈 수가 없다. 계산으로 고칠 값이 아니라 배치가 정할 일이라 숫자만 적어 둔다.</p>
</div>

<script>
__ENGINE__
__DRIVER__

/* 옆 카드 채우기 — 값은 전부 파이썬에서 온 것이다. */
const N = NUM;
const put = (id, rows) => {
  document.getElementById(id).innerHTML = rows
    .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
};
put('fork', [
  ['자유 외팔 (겹침 앞)', `${N.forkFree.toLocaleString()} mm`],
  ['선단 처짐', `${N.forkDroop} mm / 예산 ${N.droopBudget}`],
  ['살두께 3…10 훑기', `${N.droopSpan[0]}…${N.droopSpan[1]} mm`],
  ['굽힘응력', `${N.forkStress} MPa`],
  ['1 차 진동수', `${N.forkHz} Hz`],
  ['자중 (본당)', `${N.forkKg} kg`],
  ['깊이 창 (슬롯 피치)', `${N.depthWindow[0]}…${N.depthWindow[1]} mm`],
  ['채택 깊이', `${N.forkDepth} mm`],
]);
put('glass', [
  ['선반 위 처짐', `${N.shelfSag} mm`],
  ['선반 위 응력', `${N.shelfStress} MPa`],
  ['포크 위 처짐 / 응력', `${N.forkSag} mm / ${N.forkGlassStress} MPa`],
  ['포크 자리 늘어짐', `${N.sagAtFork} mm`],
  ['필요 소하강', `${N.setDownRequired} mm → 채택 ${N.setDown}`],
  ['최대 체류', `${(N.maxDwell / 60).toFixed(0)} 분`],
  ['정적피로 한계', `${(N.dwellLimit / 86400).toFixed(1)} 일`],
  ['허용 (체류 / 충격)', `${N.allowStore} / ${N.allowEvent} MPa`],
]);
put('impact', [
  ['접촉속도 (설계 / 한계)', `${N.impactV} / ${N.impactVLimit} mm/s`],
  ['최대 처짐', `${N.impactSag} mm`],
  ['동적 증폭', `×${N.daf}`],
  ['최대 응력', `${N.impactStress} MPa`],
  ['축약 ↔ 유한요소', `오차 ${(N.verify.error * 100).toFixed(1)} %`],
]);
put('mast', [
  ['마스트 1 차 진동수', `${N.mastHz} Hz`],
  ['신장 가감속 흔들림', `${N.mastSway} mm`],
  ['구조 정착', `${N.settle} s / 계상 ${N.settleBudget} s`],
  ['가속도 구속', N.accelBinding],
  ['가속도 여유', `×${N.accelHeadroom}`],
  ['닿는 슬롯', `${N.reachable} / ${N.slots}`],
]);
document.getElementById('checks').innerHTML = N.checks.map(([name, v, lim, ok]) =>
  `<tr><td>${name}</td><td class="num">${v}</td><td class="num">${lim}</td>
   <td class="${ok ? 'good' : 'bad'}">${ok ? 'OK' : '미해결'}</td></tr>`).join('');
</script>
</main>
</body>
</html>
"""


def build() -> str:
    num = numbers()
    return (TEMPLATE
            .replace("__ENGINE__", ENGINE)
            .replace("__DRIVER__", DRIVER)
            .replace("__SCENE__", json.dumps(scene(), ensure_ascii=False))
            .replace("__NUM__", json.dumps(num, ensure_ascii=False))
            .replace("__REV__", str(num["rev"]))
            .replace("__DECK__", f"{num['deckTop']:,.0f}"))


def main() -> int:
    OUT.write_text(build(), encoding="utf-8")
    print(f"물리 화면 생성 — {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
