#!/usr/bin/env python3
"""JBR-201 물리 시뮬레이션 화면을 찍는다 — `docs/drawings/pv-jbr-physics.html`.

3D 운전 영상은 **보간**이다. 시각을 주면 자세를 돌려주는 함수라, 6 g 짜리 이송도
부드럽게 재생된다. 화면이 말이 되면 기계도 된다고 믿게 되는 자리다.

이 화면은 다르다. 정션박스는 **적분된다** — 중력·접촉·마찰·반발을 받는 강체이고,
그리퍼가 진공을 끊는 순간부터는 아무도 자세를 정해 주지 않는다. 호퍼에 떨어져
구르다 멈추고, 플랩이 열리면 수거함으로 떨어진다. 그래서 이 화면은 「호퍼가 박스를
받아 내는가」·「수거함 폭 640 이 세 개를 받는가」를 **실제로** 묻는다.

수치는 전부 `jbr_analysis` 에서 온다. 손으로 옮긴 숫자가 없다.

실행:  python3 tools/build_jbr_physics.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pv_preprocess import jbr_analysis as ja      # noqa: E402
from pv_preprocess import jbr_fabrication as jf   # noqa: E402

OUT = ROOT / "docs" / "drawings" / "pv-jbr-physics.html"

#: 물리 적분 시간각. 60 fps 프레임마다 4 번 나눠 밟는다 — 접촉이 튀지 않는 하한이다.
SUBSTEPS = 4
FPS = 60


def scene() -> dict[str, object]:
    """장면 — 좌표는 전부 m, 통합 설계도 셀 좌표계와 같다."""
    mo = ja.SEQUENCE
    boxes = [
        {"z": -0.50, "sx": 0.30, "sz": 0.21, "angle": -0.018},
        {"z": -0.04, "sx": 0.32, "sz": 0.22, "angle": 0.012},
        {"z": 0.42, "sx": 0.29, "sz": 0.21, "angle": -0.009},
    ]
    box_h = mo["sinkY"][0] - 1.12                      # boxTop − 패널 상면
    return {
        "fps": FPS, "substeps": SUBSTEPS,
        "motion": {k: (list(v) if isinstance(v, tuple) else v)
                   for k, v in mo.items() if k != "discharge"},
        "discharge": mo["discharge"],
        "boxes": boxes, "boxH": box_h, "boxX": 0.28,
        "panelY": 1.12,
        "hopper": {"z": mo["sinkZ"], "floorY": mo["sinkY"][1] - box_h / 2.0,
                   "inner": [0.62, 0.60], "wallH": 0.10},
        "bin": {"x": -1.55, "z": mo["sinkZ"], "floorY": 0.105,
                "inner": [0.58, 0.54], "wallH": 0.48},
        "boxKg": ja.box_mass_kg(),
        "restitution": ja.RESTITUTION,
        "friction": 0.45,
        "g": ja.G,
    }


def numbers() -> dict[str, object]:
    """화면 옆에 띄우는 해석 결과 — 같은 함수가 시험과 도면집에도 간다."""
    modal = ja.bridge_modal()
    trav = ja.traverse_check()
    budget = ja.slot_budget()
    fea0 = ja.bridge_fea(0.5, 0.0)
    fea5 = ja.bridge_fea(0.5, 5.0)
    peel = {kn: ja.peel_dynamics(kn) for kn in (2.0, 5.0)}
    fat = {kn: ja.fatigue_life(kn) for kn in (5.0, 15.0)}
    drop = ja.hopper_drop()
    return {
        "rev": "REV.57",
        "modal": modal["modes"], "f1": modal["f1_hz"], "f1kind": modal["f1_kind"],
        "closedHz": modal["closed_form_hz"],
        "defl0": fea0["deflection_mm"], "defl5": fea5["deflection_mm"],
        "datum": ja.DATUM_TOL_MM,
        "traverse": [{"kind": r["kind"], "box": r["box"], "d": r["distance_mm"],
                      "t": r["seconds"], "a": r["a_peak_ms2"], "g": r["g"],
                      "over": r["over"], "ok": r["ok"]} for r in trav["moves"]],
        "limit": trav["limit_ms2"], "worstG": trav["worst_g"],
        "failing": trav["failing"], "total": trav["total"],
        "budget": budget,
        "peel": {str(k): {"t": v["t_stroke_s"], "fits": v["fits"],
                          "steady": v["steady_force_kn"]} for k, v in peel.items()},
        "fatigue": {str(k): {"range": v["range_mpa"], "years": (None if v["infinite_life"]
                                                                else v["years"])}
                    for k, v in fat.items()},
        "drop": {"v": drop["impact_v_ms"], "t": drop["t_first_s"],
                 "e": drop["impact_energy_j"], "settle": drop["t_settle_s"]},
        "slot": ja.SEQUENCE["slot"], "boxes": jf.BOXES_PER_PANEL,
    }


ENGINE = r"""
/* ── 강체 물리 — 임펄스 기반, 고정 시간각, 결정적 ─────────────────────────
 *
 * 외부 엔진을 쓰지 않는다. 저장소 규약이 「해석기는 표준 라이브러리만」이고,
 * 영상이 CDN 유무로 갈리면 다시 찍을 수 없기 때문이다. 대신 닫힌 해(자유낙하 +
 * 반발)와 대조할 수 있게 만들어 두었다 — `PH.check()` 가 그것을 잰다.
 *
 * 접촉은 **꼭짓점 기반**이다. 상자 A 의 여덟 꼭짓점이 상자 B 안에 들어가면, 가장
 * 가까운 면으로 밀어내는 법선과 침투깊이를 낸다. 면-면 안착은 꼭짓점 넷이 동시에
 * 잡혀 안정적으로 선다. 모서리-모서리는 놓치지만 시간각이 작아 관통하지 않는다.
 */
const V = {
  add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
  sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
  mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
  cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
  len: (a) => Math.hypot(a[0], a[1], a[2]),
  norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
};

/* 쿼터니언 — 회전만 쓴다. */
const Q = {
  mul: (a, b) => [
    a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
    a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
    a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
    a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2]],
  norm: (q) => { const l = Math.hypot(q[0], q[1], q[2], q[3]) || 1; return [q[0] / l, q[1] / l, q[2] / l, q[3] / l]; },
  fromAxis: (ax, ang) => { const s = Math.sin(ang / 2); return [ax[0] * s, ax[1] * s, ax[2] * s, Math.cos(ang / 2)]; },
  /* 회전행렬 (열 우선 3×3) */
  mat: (q) => {
    const [x, y, z, w] = q;
    return [
      [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]];
  },
};
const matVec = (m, v) => [
  m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
  m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
  m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2]];
const matT = (m) => [[m[0][0], m[1][0], m[2][0]], [m[0][1], m[1][1], m[2][1]], [m[0][2], m[1][2], m[2][2]]];

class Body {
  constructor(half, mass, pos, quat) {
    this.h = half;                       // 반치수 [hx,hy,hz]
    this.m = mass;
    this.invM = mass > 0 ? 1 / mass : 0;
    this.p = pos.slice();
    this.q = (quat || [0, 0, 0, 1]).slice();
    this.v = [0, 0, 0];
    this.w = [0, 0, 0];
    this.kinematic = mass <= 0;
    this.sleeping = false;
    /* 직육면체 관성 */
    const [a, b, c] = half.map((x) => 2 * x);
    const k = mass / 12;
    this.Ib = [k * (b * b + c * c), k * (a * a + c * c), k * (a * a + b * b)];
    this.invIb = this.Ib.map((x) => (x > 0 ? 1 / x : 0));
  }
  invIworld() {
    if (this.kinematic) return [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    const R = Q.mat(this.q), Rt = matT(R);
    const D = this.invIb;
    const M = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
      let s = 0;
      for (let k = 0; k < 3; k++) s += R[i][k] * D[k] * Rt[k][j];
      M[i][j] = s;
    }
    return M;
  }
  corners() {
    const R = Q.mat(this.q), out = [];
    for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
      const l = [sx * this.h[0], sy * this.h[1], sz * this.h[2]];
      out.push(V.add(this.p, matVec(R, l)));
    }
    return out;
  }
  toLocal(pt) {
    const Rt = matT(Q.mat(this.q));
    return matVec(Rt, V.sub(pt, this.p));
  }
  toWorldDir(d) { return matVec(Q.mat(this.q), d); }
}

/* 꼭짓점 pt 가 상자 B 안에 있으면 {n, depth} — 가장 얕은 탈출면을 고른다. */
function pointInBox(B, pt) {
  const l = B.toLocal(pt);
  let best = Infinity, axis = -1, sign = 1;
  for (let i = 0; i < 3; i++) {
    const d = B.h[i] - Math.abs(l[i]);
    if (d < 0) return null;
    if (d < best) { best = d; axis = i; sign = l[i] >= 0 ? 1 : -1; }
  }
  const nl = [0, 0, 0]; nl[axis] = sign;
  return { n: B.toWorldDir(nl), depth: best };
}

function contacts(bodies) {
  const out = [];
  for (let i = 0; i < bodies.length; i++) {
    for (let j = 0; j < bodies.length; j++) {
      if (i === j) continue;
      const A = bodies[i], B = bodies[j];
      if (A.kinematic) continue;                       // A 의 꼭짓점만 본다
      if (A.sleeping && B.sleeping) continue;
      const ac = A.corners();
      for (const c of ac) {
        const hit = pointInBox(B, c);
        if (!hit) continue;
        out.push({ a: A, b: B, p: c, n: hit.n, depth: hit.depth });
      }
    }
  }
  return out;
}

function solve(list, dt, restitution, friction, iters) {
  const slop = 0.0008, beta = 0.22;
  for (let it = 0; it < iters; it++) {
    for (const c of list) {
      const { a, b, n } = c;
      const ra = V.sub(c.p, a.p), rb = V.sub(c.p, b.p);
      const va = V.add(a.v, V.cross(a.w, ra));
      const vb = V.add(b.v, V.cross(b.w, rb));
      const rel = V.sub(va, vb);
      const vn = V.dot(rel, n);
      const iA = a.invIworld(), iB = b.invIworld();
      const raxn = V.cross(ra, n), rbxn = V.cross(rb, n);
      const kn = a.invM + b.invM
        + V.dot(raxn, matVec(iA, raxn)) + V.dot(rbxn, matVec(iB, rbxn));
      if (kn <= 0) continue;
      const bias = -beta / dt * Math.max(0, c.depth - slop);
      /* 반발은 첫 반복에만, 그리고 충분히 빠를 때만 — 안착 중에 튀지 않게. */
      const e = (it === 0 && vn < -0.25) ? restitution : 0;
      let jn = -(1 + e) * vn / kn - bias / kn;
      jn = Math.max(0, jn);
      const P = V.mul(n, jn);
      if (!a.kinematic) { a.v = V.add(a.v, V.mul(P, a.invM)); a.w = V.add(a.w, matVec(iA, V.cross(ra, P))); }
      if (!b.kinematic) { b.v = V.sub(b.v, V.mul(P, b.invM)); b.w = V.sub(b.w, matVec(iB, V.cross(rb, P))); }
      /* 쿨롱 마찰 — 접선 두 방향 */
      const va2 = V.add(a.v, V.cross(a.w, ra));
      const vb2 = V.add(b.v, V.cross(b.w, rb));
      let t = V.sub(V.sub(va2, vb2), V.mul(n, V.dot(V.sub(va2, vb2), n)));
      const tl = V.len(t);
      if (tl < 1e-9) continue;
      t = V.mul(t, 1 / tl);
      const raxt = V.cross(ra, t), rbxt = V.cross(rb, t);
      const kt = a.invM + b.invM
        + V.dot(raxt, matVec(iA, raxt)) + V.dot(rbxt, matVec(iB, rbxt));
      if (kt <= 0) continue;
      let jt = -tl / kt;
      const lim = friction * jn;
      jt = Math.max(-lim, Math.min(lim, jt));
      const Pt = V.mul(t, jt);
      if (!a.kinematic) { a.v = V.add(a.v, V.mul(Pt, a.invM)); a.w = V.add(a.w, matVec(iA, V.cross(ra, Pt))); }
      if (!b.kinematic) { b.v = V.sub(b.v, V.mul(Pt, b.invM)); b.w = V.sub(b.w, matVec(iB, V.cross(rb, Pt))); }
    }
  }
}

class World {
  constructor(opts) {
    this.bodies = [];
    this.g = opts.g;
    this.restitution = opts.restitution;
    this.friction = opts.friction;
    this.iters = 12;
    this.impulses = 0;
  }
  add(b) { this.bodies.push(b); return b; }
  step(dt) {
    for (const b of this.bodies) {
      if (b.kinematic || b.sleeping) continue;
      b.v = V.add(b.v, [0, -this.g * dt, 0]);
      b.v = V.mul(b.v, Math.pow(0.999, dt * 60));
      b.w = V.mul(b.w, Math.pow(0.985, dt * 60));
    }
    const list = contacts(this.bodies);
    this.impulses = list.length;
    solve(list, dt, this.restitution, this.friction, this.iters);
    for (const b of this.bodies) {
      if (b.kinematic || b.sleeping) continue;
      b.p = V.add(b.p, V.mul(b.v, dt));
      const wq = [b.w[0], b.w[1], b.w[2], 0];
      b.q = Q.norm(V4add(b.q, qmulScale(wq, b.q, dt * 0.5)));
      /* 잠재우기 — 느려지면 멈춰 세운다. 안 하면 수치잡음으로 영원히 떤다.
         각속도 문턱 0.12 rad/s 는 0.02 회전/s 로, 포개진 상자가 접촉점을 서로
         밀며 남기는 잔떨림보다 크고 실제 굴러감보다는 작다. */
      if (V.len(b.v) < 0.012 && V.len(b.w) < 0.12) {
        b.rest = (b.rest || 0) + dt;
        if (b.rest > 0.35) { b.sleeping = true; b.v = [0, 0, 0]; b.w = [0, 0, 0]; }
      } else b.rest = 0;
    }
  }
  wake() { for (const b of this.bodies) if (!b.kinematic) { b.sleeping = false; b.rest = 0; } }
}
const V4add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3]];
const qmulScale = (wq, q, s) => Q.mul(wq, q).map((x) => x * s);
"""


def build() -> str:
    sc = scene()
    num = numbers()
    return TEMPLATE.replace("__SCENE__", json.dumps(sc, ensure_ascii=False)) \
                   .replace("__NUM__", json.dumps(num, ensure_ascii=False)) \
                   .replace("__ENGINE__", ENGINE) \
                   .replace("__DRIVER__", DRIVER)


DRIVER = r"""
/* ── 장면 구성과 운전 ───────────────────────────────────────────────────
 * 기구(헤드·그리퍼·호퍼·브리지)는 운동식이 정한다 — 그것은 설계값이라 적분하지
 * 않는다. **정션박스만** 적분된다. 진공이 끊기는 순간 kinematic → dynamic 으로
 * 바뀌고, 그때부터 아무도 자세를 정해 주지 않는다.
 */
const S = SCENE, N = NUM, MO = S.motion;
const DT = 1 / (S.fps * S.substeps);

let world, boxes, hopper, bin_, state;

function makeStatic(half, pos) { const b = new Body(half, 0, pos); return b; }

function reset() {
  world = new World({ g: S.g, restitution: S.restitution, friction: S.friction });
  const H = S.hopper, B = S.bin;
  /* 호퍼 — 브리지에 매달려 X 로 같이 움직인다. 그래서 매 스텝 위치를 다시 준다. */
  hopper = {
    floor: world.add(makeStatic([H.inner[0] / 2, 0.015, H.inner[1] / 2], [0, H.floorY - 0.015, H.z])),
    walls: [
      world.add(makeStatic([H.inner[0] / 2, H.wallH / 2, 0.018], [0, H.floorY + H.wallH / 2, H.z - H.inner[1] / 2])),
      world.add(makeStatic([H.inner[0] / 2, H.wallH / 2, 0.018], [0, H.floorY + H.wallH / 2, H.z + H.inner[1] / 2])),
      world.add(makeStatic([0.018, H.wallH / 2, H.inner[1] / 2], [-H.inner[0] / 2, H.floorY + H.wallH / 2, H.z])),
      world.add(makeStatic([0.018, H.wallH / 2, H.inner[1] / 2], [H.inner[0] / 2, H.floorY + H.wallH / 2, H.z])),
    ],
  };
  bin_ = {
    floor: world.add(makeStatic([B.inner[0] / 2, 0.025, B.inner[1] / 2], [B.x, B.floorY - 0.025, B.z])),
    walls: [
      world.add(makeStatic([B.inner[0] / 2, B.wallH / 2, 0.025], [B.x, B.floorY + B.wallH / 2, B.z - B.inner[1] / 2])),
      world.add(makeStatic([B.inner[0] / 2, B.wallH / 2, 0.025], [B.x, B.floorY + B.wallH / 2, B.z + B.inner[1] / 2])),
      world.add(makeStatic([0.025, B.wallH / 2, B.inner[1] / 2], [B.x - B.inner[0] / 2, B.floorY + B.wallH / 2, B.z])),
      world.add(makeStatic([0.025, B.wallH / 2, B.inner[1] / 2], [B.x + B.inner[0] / 2, B.floorY + B.wallH / 2, B.z])),
    ],
  };
  boxes = S.boxes.map((b, i) => {
    const body = new Body([b.sx / 2, S.boxH / 2, b.sz / 2], S.boxKg,
      [S.boxX, S.panelY + S.boxH / 2, b.z], Q.fromAxis([0, 1, 0], b.angle));
    body.kinematic = true; body.invM = 0;      // 박리 전에는 패널에 붙어 있다
    body.tag = i; body.held = false; body.landed = null;
    world.add(body);
    return body;
  });
  state = { t: 0, slot: -1, tau: 0, flap: 0, flapWoke: false, bridgeX: S.boxX, released: [], log: [] };
}

function release(body) {
  body.kinematic = false; body.invM = 1 / body.m; body.sleeping = false; body.rest = 0;
}

/* 운동식 — 3D 영상과 같은 시각표. 여기서는 그리퍼 자세만 쓴다. */
const smooth = (w) => { w = Math.max(0, Math.min(1, w)); return w * w * (3 - 2 * w); };
const segw = (t, a, b) => smooth((t - a) / (b - a));

/* 투하 자리 — 설계는 호퍼 안에서 z 로 180 mm 씩 벌려 눕힌다(3D 의 jbRest 와 같다).
   같은 자리에 세 개를 떨구면 쌓이므로, 그 부채꼴이 실제로 필요한지 물리가 답한다. */
const REST_FAN = 0.18;
function sinkZOf(slot) { return MO.sinkZ + (slot - 1) * REST_FAN; }
function headZ(slot, tau) {
  const zs = S.boxes.map((b) => b.z), sink = sinkZOf(slot);
  const z = zs[slot];
  if (tau < MO.place[1]) {
    const from = slot ? sinkZOf(slot - 1) : 0;
    return from + (z - from) * segw(tau, MO.place[0], MO.place[1]);
  }
  if (tau < MO.boxSlide[0]) return z;
  if (tau < MO.boxSlide[1]) return z + (sink - z) * segw(tau, MO.boxSlide[0], MO.boxSlide[1]);
  return sink;
}
function headAccel(slot, tau) {
  const zs = S.boxes.map((b) => b.z), sink = sinkZOf(slot);
  const z = zs[slot];
  if (tau < MO.place[1]) {
    const from = slot ? sinkZOf(slot - 1) : 0;
    return 6 * Math.abs(z - from) / Math.pow(MO.place[1] - MO.place[0], 2);
  }
  if (tau >= MO.boxSlide[0] && tau < MO.boxSlide[1]) {
    return 6 * Math.abs(sink - z) / Math.pow(MO.boxSlide[1] - MO.boxSlide[0], 2);
  }
  return 0;
}

/* 한 프레임 진행 — 기구를 먼저 놓고, 그 다음 물리를 밟는다. */
function advance(dt) {
  const sub = dt / S.substeps;
  for (let k = 0; k < S.substeps; k++) {
    state.t += sub;
    const t = state.t;
    const slotIdx = Math.floor(t / MO.slot);
    const tau = t - MO.slot * slotIdx;
    state.slot = slotIdx; state.tau = tau;

    /* 배출 구간 — 세 칸이 끝나면 브리지가 수거함 위로 가고 플랩이 열린다.
       칸을 도는 동안 브리지는 박스 열(x) 위에 서 있다. */
    const slotsEnd = MO.slot * S.boxes.length;
    const prevX = state.bridgeX;
    if (t >= slotsEnd) {
      const w = smooth((t - slotsEnd) / 2.2);
      state.bridgeX = S.boxX + (S.bin.x - S.boxX) * w;
      if (t >= slotsEnd + 2.6) state.flap = Math.min(1, (t - slotsEnd - 2.6) / 0.35);
    } else state.bridgeX = S.boxX;

    /* 호퍼는 브리지에 매달려 있다. 정적 물체를 **순간이동시키면 안 된다** —
       접촉 해석기가 상대속도로 마찰을 내므로, 속도를 주지 않으면 호퍼가 박스 밑에서
       빠져나가 버린다. 위치와 함께 속도를 같이 준다. */
    const hx = state.bridgeX, vx = (hx - prevX) / sub;
    const parts = [hopper.floor, ...hopper.walls];
    const offs = [0, 0, 0, -S.hopper.inner[0] / 2, S.hopper.inner[0] / 2];
    parts.forEach((b, i) => { b.p[0] = hx + offs[i]; b.v = [vx, 0, 0]; });
    /* 받쳐 주는 것이 움직이면 잠든 박스를 깨운다. 안 깨우면 호퍼만 빠져나가고
       박스는 제자리에 남는다 — 적분을 건너뛰기 때문이지 물리가 아니다. */
    if (Math.abs(vx) > 1e-6) world.wake();
    /* 플랩이 열리면 바닥을 치운다 — 그때부터 박스는 받쳐 주는 것이 없다. */
    const open = state.flap > 0.5;
    hopper.floor.p[1] = open ? -99 : S.hopper.floorY - 0.015;
    /* 열리는 **순간**에만 깨운다. 매 스텝 깨우면 아무것도 잠들지 못해
       「안착」이 영원히 0 이 된다 — 물리가 아니라 신호 처리의 실수다. */
    if (open && !state.flapWoke) { state.flapWoke = true; world.wake(); }

    /* 그리퍼가 잡고 있는 박스는 자세를 받아 쓴다. */
    if (slotIdx < S.boxes.length) {
      const body = boxes[slotIdx];
      if (!body.freed) {
        const z = headZ(slotIdx, tau);
        body.p[2] = z;
        if (tau >= MO.boxLift[0]) {
          const lift = segw(tau, MO.boxLift[0], MO.boxLift[1]);
          body.p[1] = S.panelY + S.boxH / 2 + 0.055 * lift;
        }
        if (tau >= MO.boxSlide[1]) { body.p[1] = MO.sinkY[0]; body.p[0] = state.bridgeX; }
        /* 투하 — 여기서 손을 뗀다. 시각은 운동식의 boxSlide 끝이다. */
        if (tau >= MO.boxSlide[1]) {
          body.freed = true;
          release(body);
          body.v = [0, -0.15, 0];
          body.w = [0.4 * (slotIdx % 2 ? 1 : -1), 0.2, 0.9];
          state.released.push(slotIdx);
          state.log.push([t, `박스 ${slotIdx + 1} 투하 — 진공 해제`]);
        }
      }
    }
    world.step(sub);
  }
}

/* 닫힌 해 대조 — 엔진이 자유낙하를 맞게 푸는가. */
function check() {
  const w = new World({ g: S.g, restitution: S.restitution, friction: 0 });
  const floor = w.add(makeStatic([2, 0.05, 2], [0, -0.05, 0]));
  const b = w.add(new Body([0.1, 0.1, 0.1], 1, [0, 1.0, 0]));
  let t = 0, first = null;
  const dt = 1 / 2400;
  while (t < 2 && first === null) { w.step(dt); t += dt; if (b.p[1] <= 0.1 + 1e-3) first = t; }
  const exact = Math.sqrt(2 * 0.9 / S.g);
  return { simulated: first, exact, error: Math.abs(first - exact) / exact };
}
"""


TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JBR-201 물리 시뮬레이션 — 정션박스는 적분된다</title>
<meta name="description" content="정션박스를 강체로 적분해 호퍼·수거함 거동을 실제로 묻는다. 수치 해석 결과를 같은 화면에 얹었다.">
<!-- 이 파일은 손으로 쓰지 않는다.
     생성  : tools/build_jbr_physics.py
     수치  : src/pv_preprocess/jbr_analysis.py -->
<style>
:root {
  --ground:#EEF1F3; --sheet:#FFFFFF; --ink:#16202A; --muted:#5B6874; --rule:#C8D0D7;
  --tint:#E4EAEF; --red:#B5321F; --blue:#2A6CB0; --amber:#C8850A; --green:#2F7D4F;
  --code:#EDF1F4; color-scheme: light;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --ground:#12181E; --sheet:#1A222A; --ink:#E4E9ED; --muted:#98A5B1; --rule:#34414D;
  --tint:#232D37; --red:#E0604A; --blue:#6FA8E6; --amber:#E6B04C; --green:#6CBF8A;
  --code:#232D37; color-scheme: dark; } }
:root[data-theme="dark"] {
  --ground:#12181E; --sheet:#1A222A; --ink:#E4E9ED; --muted:#98A5B1; --rule:#34414D;
  --tint:#232D37; --red:#E0604A; --blue:#6FA8E6; --amber:#E6B04C; --green:#6CBF8A;
  --code:#232D37; color-scheme: dark; }
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
.flag { display:inline-block; padding:1px 6px; border-radius:3px; font-size:11px;
  border:1px solid var(--red); color:var(--red); }
</style>
</head>
<body>
<main class="page">
<header>
  <div class="eyebrow">DYNAMIC INDUSTRY · JBR-201 · 물리 시뮬레이션 · ENGINEERING BASE __REV__</div>
  <h1>정션박스는 적분된다 — 운전 영상이 못 묻는 것을 묻는다</h1>
  <p class="lede">3D 운전 영상은 시각을 주면 자세를 돌려주는 <b>보간</b>이다. 그래서 어떤 가속도든 부드럽게 재생된다.
  이 화면에서 기구(헤드·그리퍼·브리지·호퍼)는 여전히 운동식이 정하지만, <b>정션박스는 중력·접촉·마찰·반발을 받는 강체</b>다.
  진공이 끊기는 순간부터 아무도 자세를 정해 주지 않는다 — 호퍼에 떨어져 구르고, 플랩이 열리면 수거함으로 떨어진다.
  옆의 수치는 전부 <code>jbr_analysis</code> 가 푼 것이다.</p>
</header>

<div class="controls">
  <button class="primary" id="play" type="button">일시정지</button>
  <button id="restart" type="button">처음부터</button>
  <label>속도 <select id="speed">
    <option value="0.25">0.25×</option><option value="0.5" selected>0.5×</option>
    <option value="1">1×</option><option value="2">2×</option></select></label>
  <label>시점 <select id="view">
    <option value="iso" selected>아이소메트릭</option>
    <option value="front">정면 (Z–높이)</option>
    <option value="side">측면 (X–높이)</option></select></label>
  <span class="mono" id="clock">0.00 s</span>
  <span id="badge"></span>
</div>

<div class="layout">
  <div class="stage"><canvas id="c" width="1280" height="720"></canvas></div>
  <div class="side">
    <div class="card">
      <h2>이 순간</h2>
      <dl class="kv" id="live"></dl>
    </div>
    <div class="card">
      <h2>구조 — 유한요소</h2>
      <dl class="kv" id="fea"></dl>
    </div>
    <div class="card">
      <h2>이송 가속도 — 운동식이 요구하는 값</h2>
      <table id="trav"><thead><tr><th>구간</th><th class="num">거리</th><th class="num">시간</th><th class="num">필요 a</th><th class="num">한계비</th></tr></thead><tbody></tbody></table>
      <p class="note" id="travnote"></p>
    </div>
    <div class="card">
      <h2>칸 예산</h2>
      <dl class="kv" id="budget"></dl>
    </div>
  </div>
</div>

<p class="note" id="closing"></p>
</main>

<script>
const SCENE = __SCENE__;
const NUM = __NUM__;
__ENGINE__
__DRIVER__

/* ── 아이소메트릭 캔버스 렌더 — 의존성 없음 ─────────────────────────── */
const cv = document.getElementById('c'), cx = cv.getContext('2d');
let view = 'iso';
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function project(p) {
  const [x, y, z] = p;
  if (view === 'front') return [640 + z * 420, 690 - (y - 0.05) * 420];
  if (view === 'side') return [640 + (x + 0.8) * 420, 690 - (y - 0.05) * 420];
  const s = 300;
  return [640 + (x - z) * s * 0.72, 380 - (x + z) * s * 0.32 - (y - 0.6) * s * 0.95];
}
const FACES = [[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]];
function drawBody(b, fill, stroke, alpha) {
  const c = b.corners().map(project);
  const world = b.corners();
  const polys = FACES.map((f) => {
    const zs = f.reduce((s, i) => s + world[i][0] + world[i][2] + world[i][1] * 0.4, 0) / 4;
    return { f, depth: zs };
  }).sort((a, z) => a.depth - z.depth);
  cx.globalAlpha = alpha === undefined ? 1 : alpha;
  for (const { f } of polys) {
    cx.beginPath();
    cx.moveTo(c[f[0]][0], c[f[0]][1]);
    for (let i = 1; i < f.length; i++) cx.lineTo(c[f[i]][0], c[f[i]][1]);
    cx.closePath();
    cx.fillStyle = fill; cx.fill();
    cx.strokeStyle = stroke; cx.lineWidth = 1; cx.stroke();
  }
  cx.globalAlpha = 1;
}

function draw() {
  cx.clearRect(0, 0, cv.width, cv.height);
  const ink = css('--ink'), muted = css('--muted'), rule = css('--rule');
  const blue = css('--blue'), red = css('--red'), amber = css('--amber'), green = css('--green');

  /* 패널 */
  const panel = new Body([1.25, 0.005, 0.70], 0, [0, SCENE.panelY - 0.005, 0]);
  drawBody(panel, css('--tint'), rule, 0.9);

  /* 수거함 · 호퍼 */
  for (const b of [bin_.floor, ...bin_.walls]) drawBody(b, css('--sheet'), muted, 0.55);
  const flapOpen = state.flap > 0.5;
  for (const b of hopper.walls) drawBody(b, css('--sheet'), amber, 0.8);
  if (!flapOpen) drawBody(hopper.floor, css('--sheet'), amber, 0.9);

  /* 헤드 — 잡고 있는 동안만 */
  if (state.slot < SCENE.boxes.length) {
    const z = headZ(state.slot, state.tau);
    const a = headAccel(state.slot, state.tau);
    const over = a > NUM.limit;
    const head = new Body([0.16, 0.10, 0.16], 0, [state.bridgeX + SCENE.boxX, SCENE.panelY + 0.30, z]);
    drawBody(head, over ? red : css('--sheet'), over ? red : ink, over ? 0.35 : 0.9);
  }

  /* 박스 */
  boxes.forEach((b, i) => {
    const held = b.kinematic;
    drawBody(b, held ? blue : (b.sleeping ? green : amber), ink, held ? 0.85 : 1);
  });

  /* 눈금 */
  cx.fillStyle = muted; cx.font = '12px ui-monospace, monospace';
  cx.fillText(`t = ${state.t.toFixed(2)} s   ·   칸 ${Math.min(state.slot + 1, SCENE.boxes.length)}/${SCENE.boxes.length}   ·   접촉 ${world.impulses}`, 16, 24);
  cx.fillText(view === 'iso' ? '아이소메트릭 · 1 눈금 = 100 mm' : (view === 'front' ? '정면 Z–높이' : '측면 X–높이'), 16, 42);
}

/* ── 상태판 ─────────────────────────────────────────────────────────── */
function kv(el, rows) {
  el.replaceChildren();
  for (const [k, v, cls] of rows) {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v; if (cls) dd.className = cls;
    el.appendChild(dt); el.appendChild(dd);
  }
}
function fillStatic() {
  kv(document.getElementById('fea'), [
    ['1 차 모드', `${NUM.f1.toFixed(2)} Hz · ${NUM.f1kind === 'sway' ? '흔들림' : '굽힘'}`, NUM.f1kind === 'sway' ? 'bad' : ''],
    ['닫힌 해 1 차', `${NUM.closedHz} Hz · 굽힘`],
    ['처짐 (박리 0)', `${NUM.defl0.toFixed(3)} mm`],
    ['처짐 (박리 5 kN)', `${NUM.defl5.toFixed(3)} mm`, NUM.defl5 > NUM.datum ? 'bad' : 'good'],
    ['헤드 datum', `±${NUM.datum} mm`],
  ]);
  const tb = document.querySelector('#trav tbody');
  tb.replaceChildren();
  for (const r of NUM.traverse) {
    const tr = document.createElement('tr');
    for (const [txt, cls] of [[`${r.kind} ${r.box}`, ''], [`${r.d.toFixed(0)} mm`, 'num'],
                              [`${r.t.toFixed(2)} s`, 'num'], [`${r.a.toFixed(1)}`, 'num'],
                              [`${r.over.toFixed(1)}×`, 'num']]) {
      const td = document.createElement('td'); td.textContent = txt;
      td.className = cls + (r.ok ? '' : ' bad'); tr.appendChild(td);
    }
    tb.appendChild(tr);
  }
  document.getElementById('travnote').textContent =
    `축 한계 ${NUM.limit} m/s² 기준 ${NUM.failing}/${NUM.total} 구간 초과 · 최악 ${NUM.worstG.toFixed(1)} g.`;
  const b = NUM.budget;
  kv(document.getElementById('budget'), [
    ['배치 이송', `${b.t_place_s} s`], ['파지', `${b.t_grip_s} s`],
    ['박리·유지·재개방·상승', `${b.t_fixed_s} s`], ['슈트 이송', `${b.t_slide_s} s`],
    ['필요', `${b.need_s} s`, 'bad'], ['지금 배분', `${b.slot_now_s} s`],
    ['초과', `+${b.over_s} s`, 'bad'], ['한 판', `${b.panel_s} s`],
  ]);
  document.getElementById('closing').innerHTML =
    `물리엔진은 자유낙하 닫힌 해와 대조해 검증한다(<code>PH.check()</code>). ` +
    `호퍼 낙하 ${NUM.drop.v.toFixed(2)} m/s · 충돌에너지 ${NUM.drop.e.toFixed(2)} J · 안정까지 ${NUM.drop.settle.toFixed(2)} s.`;
}
function fillLive() {
  const a = state.slot < SCENE.boxes.length ? headAccel(state.slot, state.tau) : 0;
  const free = boxes.filter((b) => !b.kinematic).length;
  const asleep = boxes.filter((b) => b.sleeping).length;
  kv(document.getElementById('live'), [
    ['시각', `${state.t.toFixed(2)} s`],
    ['칸 · 상대시각', `${Math.min(state.slot + 1, SCENE.boxes.length)} · ${state.tau.toFixed(2)} s`],
    ['헤드 요구 가속도', `${a.toFixed(1)} m/s² (${(a / 9.80665).toFixed(2)} g)`, a > NUM.limit ? 'bad' : 'good'],
    ['자유 박스', `${free} / ${SCENE.boxes.length}`],
    ['안착', `${asleep}`],
    ['접촉점', `${world.impulses}`],
    ['플랩', state.flap > 0.5 ? '열림' : '닫힘'],
  ]);
  document.getElementById('clock').textContent = `${state.t.toFixed(2)} s`;
  const badge = document.getElementById('badge');
  badge.replaceChildren();
  if (a > NUM.limit) {
    const s = document.createElement('span'); s.className = 'flag';
    s.textContent = `이송 가속도 한계의 ${(a / NUM.limit).toFixed(0)} 배`;
    badge.appendChild(s);
  }
}

/* ── 운전 ───────────────────────────────────────────────────────────── */
let playing = true, speed = 0.5, last = performance.now();
const TOTAL = SCENE.motion.slot * SCENE.boxes.length + 10.0;
reset(); fillStatic();

function frame(now) {
  const dt = Math.min((now - last) / 1000, 0.05); last = now;
  if (playing) {
    let step = dt * speed;
    while (step > 0) { const s = Math.min(step, 1 / SCENE.fps); advance(s); step -= s; }
    if (state.t > TOTAL) reset();
  }
  draw(); fillLive();
  requestAnimationFrame(frame);
}
document.getElementById('play').addEventListener('click', (e) => {
  playing = !playing; e.target.textContent = playing ? '일시정지' : '재생';
});
document.getElementById('restart').addEventListener('click', () => reset());
document.getElementById('speed').addEventListener('change', (e) => { speed = parseFloat(e.target.value); });
document.getElementById('view').addEventListener('change', (e) => { view = e.target.value; });

/* 렌더러(Playwright)가 결정적으로 밟을 수 있게 내놓는다. */
window.PH = {
  reset, advance, check, draw,
  state: () => state,
  bodies: () => boxes.map((b) => ({ p: b.p.slice(), q: b.q.slice(), v: b.v.slice(), w: b.w.slice(), free: !b.kinematic, sleeping: !!b.sleeping })),
  setView: (v) => { view = v; },
  total: TOTAL,
  pause: () => { playing = false; },
};
requestAnimationFrame(frame);
</script>
</body>
</html>
"""


def main() -> int:
    html = build().replace("__REV__", numbers()["rev"])
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} — {'변경 없음' if old == html else '갱신'} ({len(html):,} 자)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
