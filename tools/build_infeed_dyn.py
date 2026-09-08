# -*- coding: utf-8 -*-
"""투입 구간 3D 를 **물리로 구동하는** 파생본을 만든다.

`pv-infeed-scene.html` 은 같은 구간을 **키프레임**으로 움직인다 — 시각 t 를 주면
어디에 있어야 하는지가 적혀 있다. 그것으로 보이지 않는 것이 있다:

* 가속을 올리면 **무엇이 먼저 무너지는가.** 키프레임은 아무리 빨리 감아도
  마찰 롤러가 미끄러지지 않는다 — 그림이 힘을 모르기 때문이다.
* 미끄러지면 **어떻게 되는가.** 토크가 모자란 것이 아니라 위상을 잃는다.
  180° 락 자리에 안 오는 그 모습이 그림에 나와야 결정이 된다.
* 겹장이 떨어지면 **포획빔이 무엇을 받는가.** 낙하는 프로파일이 없다.

그래서 형상은 그대로 두고 **구동만 바꾼다.** 씬이 매 프레임 포즈를 쓰고 나면
그 뒤에 이 모듈이 적분한 상태를 덮어쓴다(`requestAnimationFrame` 은 등록 순서로
돌고 이 모듈이 마지막에 등록된다). 그래서 3D 형상은 정본 하나로 남는다 —
도면이 바뀌면 이 페이지도 같이 바뀐다.

**적분기는 `src/pv_preprocess/dynamics.py` 와 같은 식이다.** 두 벌이 갈라지면
영상이 거짓말을 하므로 `tools/check_dynamics.mjs` 가 브라우저에서 돌려 파이썬
값과 대조한다.

    PYTHONPATH=src python tools/build_infeed_dyn.py
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from pv_preprocess import drives, dynamics, kinematics  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "drawings" / "pv-infeed-scene.html"
OUT = ROOT / "docs" / "drawings" / "pv-infeed-dyn.html"

TITLE = "태양광 전처리 플랜트 · 투입 구간 동역학"


def _replace_once(text: str, old: str, new: str, what: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{what}: 앵커가 {text.count(old)}개 — 1개여야 한다\n  {old[:90]}")
    return text.replace(old, new)


def model() -> dict[str, object]:
    """JS 적분기가 받는 값 — 전부 모델에서 온다. 여기서 새로 적지 않는다."""
    lift_seg = kinematics.PATH[2]
    flip_seg = kinematics.PATH[3]
    sep_seg = kinematics.PATH[0]
    down_seg = kinematics.PATH[4]
    sep_d, sep_n = dynamics.sep_cups()
    eoat_d, eoat_n = dynamics.eoat_cups()
    ring_r = (kinematics.RING_R_MM + kinematics.RING_TUBE_MM) / 1_000.0
    return {
        # 구간 (공정시계 s)
        "sepSeg": list(sep_seg[:2]),
        "liftSeg": list(lift_seg[:2]),
        "flipSeg": list(flip_seg[:2]),
        "downSeg": list(down_seg[:2]),
        # 행정 (m)
        "sepStroke": kinematics.SEPARATION_MM / 1_000.0,
        "liftStroke": (kinematics.FLIP_AXIS_MM
                       - (kinematics.PICK_FACE_MM + kinematics.SEPARATION_MM)) / 1_000.0,
        "downStroke": (kinematics.FLIP_AXIS_MM - kinematics.HANDOVER_MM) / 1_000.0,
        # 관성
        "liftKg": drives.lift_moving_kg(),
        "flipJ": drives.flip_inertia_kgm2(),
        "panelKg": drives.PANEL_KG,
        # 구동 한계
        "ringR": ring_r,
        "preloadN": drives.FLIP_PRELOAD_N,
        "mu": drives.FRICTION_MU,
        "frictionSafety": drives.FRICTION_SAFETY,
        "leadM": drives.LIFT_LEAD_MM / 1_000.0,
        "screwEff": drives.BALLSCREW_EFFICIENCY,
        "servoPeakNm": drives.rated_torque_nm("AXIS-BFC-Z") * drives.SERVO_PEAK_FACTOR,
        # 진공
        "sepHoldN": dynamics.cup_force_n(sep_d, sep_n),
        "eoatHoldN": dynamics.cup_force_n(eoat_d, eoat_n),
        "vacuumSafety": dynamics.VACUUM_SAFETY,
        "stackGapMm": dynamics.stack_gap_mm(),
        "muAir": dynamics.AIR_VISCOSITY_PAS,
        "panelArea": (kinematics.PANEL_MM[0] / 1_000.0) * (kinematics.PANEL_MM[1] / 1_000.0),
        # 낙하 · 접촉
        "dropJ": dynamics.double_sheet_energy_j(),
        "beamKNm": dynamics.catch_beam_stiffness_n_per_mm() * 1_000.0,
        "contactZeta": dynamics.CONTACT_DAMPING,
        "beamCount": dynamics._part(dynamics.SHEET_CATCH, "CD-BM-01").qty,
        "g": dynamics.G,
        # 파이썬이 낸 답 — 검사기가 이것과 대조한다
        "expect": dynamics.summary(),
    }


HUD = """
<style>
#pv-dyn { position: relative; margin: 12px 0 0; padding: 12px 14px;
  border: 1px solid var(--line, #d5dbe1); border-radius: 10px;
  background: var(--panel, #fff); font: 13px/1.5 system-ui, "Noto Sans KR", sans-serif; }
#pv-dyn h3 { margin: 0 0 8px; font-size: 13px; font-weight: 650; letter-spacing: .03em;
  text-transform: uppercase; color: var(--dim, #5d6874); }
#pv-dyn .row { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; }
#pv-dyn .cell { min-width: 132px; }
#pv-dyn .k { font-size: 11.5px; color: var(--dim, #5d6874); }
#pv-dyn .v { font: 650 17px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: -.02em; }
#pv-dyn .v.bad { color: #a4342b; }
#pv-dyn .v.warn { color: #9a6700; }
#pv-dyn .note { margin-top: 8px; font-size: 11.5px; color: var(--dim, #5d6874); }
#pv-dyn input[type=range] { width: 190px; vertical-align: middle; }
#pv-dyn button { font: inherit; padding: 4px 10px; border-radius: 8px;
  border: 1px solid var(--line, #d5dbe1); background: var(--panel-2, #f6f8fa); cursor: pointer; }
</style>
<section id="pv-dyn" aria-label="시간영역 동역학 계기판">
  <h3>동역학 계기판 — 힘에서 나온 움직임</h3>
  <div class="row" id="pv-dyn-cells"></div>
  <div class="row" style="margin-top:10px">
    <label>택트 압축 <input id="pv-dyn-scale" type="range" min="0.6" max="2.5" step="0.01" value="1">
      <span id="pv-dyn-scale-v" style="font-family:ui-monospace">1.00 × 빠르게 (가속 1.00 ×)</span></label>
    <button id="pv-dyn-jump" type="button">반전 구간으로</button>
    <button id="pv-dyn-drop" type="button">겹장 낙하 (OI-05)</button>
    <button id="pv-dyn-reset" type="button">초기화</button>
  </div>
  <p class="note" id="pv-dyn-note"></p>
</section>
"""


def engine_js(m: dict[str, object]) -> str:
    return """
<script type="module">
/* 투입 구간 동역학 — 이 페이지의 움직임은 **적분에서 나온다**.
 *
 * 씬이 매 프레임 키프레임 포즈를 쓰고 나면 그 뒤에 이 모듈이 상태를 덮어쓴다.
 * requestAnimationFrame 은 등록 순서로 돌고 이 모듈이 마지막이라 우리가 이긴다.
 *
 * 식은 src/pv_preprocess/dynamics.py 와 같다 — 반음시 오일러, 사다리꼴 지령,
 * 마찰 롤러 토크 포화, 스테판 접착, 한 방향 접촉. 두 벌이 갈라지면 영상이
 * 거짓말을 하므로 tools/check_dynamics.mjs 가 대조한다.
 */
'use strict';
const M = __MODEL__;

/* ── 적분기 ─────────────────────────────────────────────────────────── */
function trapezoid(t, total, distance) {
  if (total <= 0) return 0;
  const seg = total / 3, a = distance / (seg * (total - seg));
  if (t < seg) return a;
  if (t < 2 * seg) return 0;
  if (t <= total) return -a;
  return 0;
}
class Body {
  constructor(inertia) { this.i = inertia; this.x = 0; this.v = 0; }
  step(f, dt) { this.v += f / this.i * dt; this.x += this.v * dt; }
}

/* ── 축 셋 ──────────────────────────────────────────────────────────── */
const lift = new Body(M.liftKg);
const flip = new Body(M.flipJ);
let sheet = null;                       // 겹장 낙하 자유물체
let scale = 1.0, phaseLost = 0, peak = { liftN: 0, flipNm: 0, dropN: 0 };

/** 승강 — 중력은 상시, 가속은 지령에서. 모터가 내는 힘이 곧 볼스크루 토크다. */
function liftStep(t, total, stroke, dt) {
  const a = trapezoid(t, total / scale, stroke);
  const f = M.liftKg * (a + M.g);
  lift.step(M.liftKg * a, dt);
  if (Math.abs(f) > Math.abs(peak.liftN)) peak.liftN = f;
  return { f, nm: f * M.leadM / (2 * Math.PI * M.screwEff) };
}

/** 반전 — **전달 토크가 포화한다.** 압착력이 정한 한계를 넘으면 롤러가 미끄러지고
 *  링은 지령을 못 따라간다. 그 차이가 위상 손실이고, 180° 락이 안 물리는 이유다. */
function flipStep(t, total, dt) {
  const alpha = trapezoid(t, total / scale, Math.PI);
  const want = M.flipJ * alpha;
  const cap = M.preloadN * M.mu * M.ringR;
  const got = Math.max(-cap, Math.min(cap, want));
  flip.step(got, dt);
  if (Math.abs(want) > Math.abs(peak.flipNm)) peak.flipNm = want;
  if (got !== want) phaseLost += Math.abs(want - got) / M.flipJ * dt * dt;
  return { want, cap, got, slipping: got !== want };
}

/** 적층에서 한 장 떼기 — 자중 + 가속 + 스테판 접착(틈³ 에 반비례). */
function peelDemand() {
  const total = (M.sepSeg[1] - M.sepSeg[0]) / scale;
  const a = trapezoid(0, total, M.sepStroke);
  const speed = a * (total / 3);
  const r = Math.sqrt(M.panelArea / Math.PI);
  const h = Math.max(M.stackGapMm, 1e-6) / 1000;
  const stefan = 3 * Math.PI * M.muAir * Math.pow(r, 4) / (2 * h * h * h) * speed;
  const demand = M.panelKg * M.g + M.panelKg * a + stefan;
  return { demand, stefan, margin: M.sepHoldN / demand };
}

/** 겹장 낙하 — **자유낙하부터** 감는다. 빔에 닿으면 한 방향 접촉(당기지 않는다).
 *
 *  body.x 는 빔 윗면 위의 높이(m)다. 안전분리 상승만큼 위에서 정지 상태로 놓으면
 *  닿는 순간의 에너지가 저절로 OI-05 의 163 J 이 된다 — 속도를 손으로 넣지 않는다. */
function sheetStep(dt) {
  if (!sheet) return 0;
  let f = 0;
  if (sheet.body.x < 0) {
    const c = 2 * M.contactZeta * Math.sqrt(M.beamKNm * M.panelKg);
    f = Math.max(0, M.beamKNm * (-sheet.body.x) - c * sheet.body.v);
  }
  sheet.body.step(f - M.panelKg * M.g, dt);
  if (f > peak.dropN) peak.dropN = f;
  return f;
}

/* ── 씬에 붙기 ──────────────────────────────────────────────────────── */
const host = document.getElementById('jb-removal-operation');
const S = host && host.__pvScene, A = host && host.__pvInfeedTest;
function findMesh(re) {
  let hit = null;
  if (S) S.scene.traverse((o) => {
    if (!hit && o.isMesh && re.test(String((o.userData && o.userData.label) || o.name || ''))) hit = o;
  });
  return hit;
}
const carriage = findMesh(/단장 승강캐리지/), ringMesh = findMesh(/오픈센터 엔드링/);
const liftGroup = carriage && carriage.parent, ringGroup = ringMesh && ringMesh.parent;
let base = null;
if (liftGroup && ringGroup && A) {
  A.setTime(M.liftSeg[0]);
  S.scene.updateMatrixWorld(true);
  base = { y: liftGroup.position.y, rot: ringGroup.rotation.z };
}

/* 낙하용 판 — 새 지오메트리를 만들지 않고 적층 판을 복제한다. */
let dropMesh = null;
function spawnSheet() {
  const src = findMesh(/팔레트 패널 30장/);
  if (!src || !base) return;
  if (!dropMesh) {
    dropMesh = src.clone();
    dropMesh.name = 'DYN 겹장 (딸려 올라온 아랫장)';
    dropMesh.scale.y = 1 / 30;                 // 적층 30장 중 한 장
    S.scene.add(dropMesh);
  }
  dropMesh.visible = true;
  const w = src.getWorldPosition(new S.Vector3());
  dropMesh.position.set(w.x, 0, w.z);
  // 빔 윗면은 대기면(픽업면 + 안전분리 상승)이다. 거기서 sepStroke 만큼 위에
  // **정지 상태로** 놓는다 — 닿는 순간의 에너지가 저절로 163 J 이 된다.
  sheet = { body: new Body(M.panelKg), beamY: base.y };
  sheet.body.x = M.sepStroke;
  sheet.body.v = 0;
  peak.dropN = 0;
}

/* ── 계기판 ─────────────────────────────────────────────────────────── */
const cells = document.getElementById('pv-dyn-cells');
const note = document.getElementById('pv-dyn-note');
function card(k, v, cls) {
  return '<div class="cell"><div class="k">' + k + '</div><div class="v'
    + (cls ? ' ' + cls : '') + '">' + v + '</div></div>';
}
function paint(st) {
  if (!cells) return;
  const peel = peelDemand();
  const commanded = Math.abs(st.want) > 1e-6;
  const slipMargin = commanded ? st.cap / Math.abs(st.want) : null;
  cells.innerHTML = [
    card('승강 힘', Math.abs(st.liftN).toFixed(0) + ' N'),
    card('볼스크루 토크', st.liftNm.toFixed(2) + ' N·m',
         st.liftNm > M.servoPeakNm ? 'bad' : ''),
    card('반전 지령', Math.abs(st.want).toFixed(1) + ' N·m'),
    card('전달 한계', st.cap.toFixed(1) + ' N·m'),
    card('미끄럼 여유', slipMargin === null ? '— 지령 없음' : slipMargin.toFixed(2) + ' ×',
         slipMargin === null ? '' : (slipMargin < 1 ? 'bad'
           : (slipMargin < M.frictionSafety ? 'warn' : ''))),
    card('반전 위상', (flip.x * 180 / Math.PI).toFixed(1) + '°'),
    card('진공 여유', peel.margin.toFixed(2) + ' ×',
         peel.margin < 1 ? 'bad' : (peel.margin < M.vacuumSafety ? 'warn' : '')),
    card('스테판 저항', peel.stefan.toFixed(0) + ' N'),
    card('낙하 반력', peak.dropN ? (peak.dropN / 1000).toFixed(1) + ' kN' : '—'),
    card('공정시계', t.toFixed(1) + ' s'),
    card('단계', stage ? stage.name : '—'),
  ].join('');
  if (note) {
    const bits = [];
    bits.push('적층 틈 ' + M.stackGapMm.toFixed(0) + ' mm — 프레임이 유리면보다 솟은 만큼이다. '
      + '이 틈이 0 이면(무프레임) 스테판 저항이 자릿수로 커져 같은 헤드로는 못 뗀다.');
    if (st.slipping) bits.push('★ 마찰 롤러가 미끄러진다 — 토크가 모자란 게 아니라 위상을 잃는다.');
    if (peak.dropN) bits.push('겹장 ' + M.dropJ.toFixed(0) + ' J 이 빔 '
      + M.beamCount + '본에 ' + (peak.dropN / M.beamCount / 1000).toFixed(2) + ' kN/본 으로 걸렸다.');
    note.textContent = bits.join(' ');
  }
}

/* ── 루프 — 씬 뒤에 등록해 매 프레임 마지막에 쓴다 ──────────────────── */
/* 공정시계를 네 구간에 나눠 태운다. 구간 **밖에서는 축이 지령을 안 받는다** —
 * 반전을 제 구간 전에 돌리면 그림이 공정과 다른 이야기를 한다. */
const SEGS = [
  { name: '안전분리 상승', seg: M.sepSeg, axis: 'lift', stroke: M.sepStroke },
  { name: '대기 — 포획빔 전개', seg: [M.sepSeg[1], M.liftSeg[0]], axis: null },
  { name: '반전축까지 승강', seg: M.liftSeg, axis: 'lift', stroke: M.liftStroke },
  { name: '180° 반전', seg: M.flipSeg, axis: 'flip', stroke: Math.PI },
  { name: '인계 높이로 하강', seg: M.downSeg, axis: 'lift', stroke: -M.downStroke },
];
const T0 = M.sepSeg[0], T1 = M.downSeg[1];
let t = T0, last = 0, stage = SEGS[0];
const DT = 1 / 240;                        // 물리 간격은 화면과 무관하게 고정
function reset() {
  t = T0; lift.x = lift.v = 0; flip.x = flip.v = 0; phaseLost = 0;
  peak = { liftN: 0, flipNm: 0, dropN: peak.dropN };
}
/** 어느 시각으로 건너뛴다 — 거기까지를 **빨리 감아** 상태를 만든다.
 *  포즈를 바로 써 넣으면 속도가 0 인 채로 시작해 물리가 끊긴다. */
function seek(target) {
  reset();
  const step = 1 / 480;
  while (t < target) {
    const s = SEGS.find((q) => t >= q.seg[0] && t < q.seg[1]);
    if (s && s.axis === 'lift') liftStep(t - s.seg[0], s.seg[1] - s.seg[0], s.stroke, step);
    else if (s && s.axis === 'flip') flipStep(t - s.seg[0], s.seg[1] - s.seg[0], step);
    t += step;
  }
}
function frame(now) {
  requestAnimationFrame(frame);
  if (!base) return;
  const wall = last ? Math.min((now - last) / 1000, 0.05) : 0;
  last = now;
  let st = { liftN: M.liftKg * M.g, liftNm: 0, want: 0,
             cap: M.preloadN * M.mu * M.ringR, slipping: false };
  st.liftNm = st.liftN * M.leadM / (2 * Math.PI * M.screwEff);
  for (let acc = 0; acc < wall; acc += DT) {
    stage = SEGS.find((s) => t >= s.seg[0] && t < s.seg[1]) || stage;
    const local = t - stage.seg[0];
    if (stage.axis === 'lift') {
      const l = liftStep(local, stage.seg[1] - stage.seg[0], stage.stroke, DT);
      st.liftN = l.f; st.liftNm = l.nm;
    } else if (stage.axis === 'flip') {
      const f = flipStep(local, stage.seg[1] - stage.seg[0], DT);
      st.want = f.want; st.cap = f.cap; st.slipping = f.slipping;
    }
    sheetStep(DT);
    t += DT;
    if (t > T1) reset();
  }
  liftGroup.position.y = base.y + lift.x;
  ringGroup.rotation.z = base.rot + flip.x;
  if (sheet && dropMesh) dropMesh.position.y = sheet.beamY + Math.max(sheet.body.x, -0.05);
  paint(st);
}
requestAnimationFrame(frame);

/* ── 조작 ───────────────────────────────────────────────────────────── */
const slider = document.getElementById('pv-dyn-scale');
if (slider) slider.addEventListener('input', () => {
  scale = Number(slider.value);
  document.getElementById('pv-dyn-scale-v').textContent =
    scale.toFixed(2) + ' × 빠르게 (가속 ' + (scale * scale).toFixed(2) + ' ×)';
});
const jumpBtn = document.getElementById('pv-dyn-jump');
if (jumpBtn) jumpBtn.addEventListener('click', () => seek(M.flipSeg[0]));
const dropBtn = document.getElementById('pv-dyn-drop');
if (dropBtn) dropBtn.addEventListener('click', spawnSheet);
const resetBtn = document.getElementById('pv-dyn-reset');
if (resetBtn) resetBtn.addEventListener('click', () => {
  peak.dropN = 0; reset();
  sheet = null; if (dropMesh) dropMesh.visible = false;
});

/* ── 검사기가 부르는 자리 ───────────────────────────────────────────── */
window.__pvDynTest = {
  model: M,
  /** 파이썬과 같은 답을 내는지 — 축마다 한 번씩 통째로 감아 최대값을 낸다. */
  run() {
    const dt = 1e-4;
    let lf = 0, lnm = 0;
    const lt = (M.liftSeg[1] - M.liftSeg[0]) / scale;
    for (let x = 0; x <= lt; x += dt) {
      const f = M.liftKg * (trapezoid(x, lt, M.liftStroke) + M.g);
      if (Math.abs(f) > Math.abs(lf)) { lf = f; lnm = f * M.leadM / (2 * Math.PI * M.screwEff); }
    }
    let ft = 0;
    const tt = (M.flipSeg[1] - M.flipSeg[0]) / scale;
    for (let x = 0; x <= tt; x += dt) {
      const nm = M.flipJ * trapezoid(x, tt, Math.PI);
      if (Math.abs(nm) > Math.abs(ft)) ft = nm;
    }
    const b = new Body(M.panelKg);
    b.v = -Math.sqrt(2 * M.dropJ / M.panelKg);
    const c = 2 * M.contactZeta * Math.sqrt(M.beamKNm * M.panelKg);
    let dpk = 0, deepest = 0;
    for (let x = 0, s = 2e-5; x < 1; x += s) {
      const pen = -b.x;
      let f = 0;
      if (pen > 0) f = Math.max(0, M.beamKNm * pen - c * b.v);
      else if (x > 0 && b.v > 0) break;
      if (f > dpk) dpk = f;
      if (pen > deepest) deepest = pen;
      b.step(f - M.panelKg * M.g, s);
    }
    const peel = peelDemand();
    return {
      liftPeakN: lf, liftPeakNm: lnm, flipPeakNm: Math.abs(ft),
      flipCapacityNm: M.preloadN * M.mu * M.ringR,
      impactPeakN: dpk, impactDeflectionMm: deepest * 1000,
      peelDemandN: peel.demand, peelStefanN: peel.stefan,
    };
  },
  /** 택트 압축 배율 — 구간 시간을 1/v 로 줄인다. 가속은 v² 로 오른다. */
  setTakt(v) { scale = v; },
  seek(target) { seek(target); },
  get state() { return { t, liftM: lift.x, flipDeg: flip.x * 180 / Math.PI, phaseLost }; },
  drop() { spawnSheet(); },
  get driven() { return !!base; },
};
</script>
"""


def build() -> pathlib.Path:
    text = BASE.read_text(encoding="utf-8")
    text = _replace_once(text,
                         "<title>태양광 전처리 플랜트 · 투입 구간</title>",
                         f"<title>{TITLE}</title>", "문서 제목")
    js = engine_js(model()).replace(
        "__MODEL__", json.dumps(model(), ensure_ascii=False, allow_nan=False))
    # 화면에 보이는 3D 바로 아래에 둔다. `jb-stage` 는 기본 숨김인 팝업 안이라
    # 거기 넣으면 계기판이 안 보인다 — 계기판은 그림과 같이 봐야 계기판이다.
    anchor = '    <section class="pv-v22-programs" aria-labelledby="pv-v22-program-title">'
    text = _replace_once(text, anchor, HUD + anchor, "영상 아래 프로그램 절 앞")
    text = _replace_once(text, "\n</body>", "\n" + js + "\n</body>", "본문 끝")
    OUT.write_text(text, encoding="utf-8")
    return OUT


def main() -> None:
    path = build()
    kb = path.stat().st_size / 1024
    print(f"{path.relative_to(ROOT)}  {kb / 1024:.2f} MB")
    print("\n파이썬이 낸 답 (JS 적분기가 맞춰야 하는 값)")
    for k, v in dynamics.summary().items():
        print(f"  {k:22} {v}")


if __name__ == "__main__":
    main()
