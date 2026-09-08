/* GBR-301 파생본이 **혼자 서서 실제로 움직이는지** 브라우저로 확인한다.
 *
 * 파이썬 시험은 생성된 글자만 본다. 그런데 이 화면이 못 쓰게 되는 방식은 글자에
 * 남지 않는다 — 창이 후단 마지막 칸의 진도 0.88 에 걸려 있어서, 그 칸의 시각표가
 * 조금만 바뀌어도 창이 적재 **뒤**로 밀려 정지 화면이 된다. 글자로는 흔적이 없다.
 * 그래서 여기서 재는 것은 **움직임**이다.
 *
 *   ① 페이지 오류 0 · 3D 가 실제로 섰을 것
 *   ② 보이는 것이 buffer 셀뿐일 것 — 다른 셀의 형상이 한 점도 켜져 있지 않을 것
 *   ③ 발주 요청 셋 — 섀도맵 off · 외장 케이싱(pvCase) off · 천장크레인(pvCrn) off
 *   ④ 창을 훑으면 유리가 GI 에서 데크로 건너와 목표 행으로 횡분기하고 슬롯에 들어갈 것
 *      (`bufferTransfer` 0 → 1, z 가 목표 행으로, x 가 캐리지로)
 *   ⑤ 목표 캐리지를 바꾸면 유리가 **다른 행**에 들어갈 것 — 이 셀의 유일한 조작이다
 *   ⑥ 설비끼리 파고들지 않을 것 — 마스트 여섯이 서로도 가드도 안 건드릴 것
 *   ⑦ 목표가 만재면 **적재를 승인하지 않을 것** — 유리는 상류 잠금 게이트에 남고
 *      그 행의 인터록 센서만 붉게 서며, 수량을 초기화하면 다시 들어갈 것
 *
 * 실행:  node tools/check_gbr_scene.mjs [문서.html]
 *        (인자를 안 주면 docs/drawings/pv-gbr-scene.html 을 본다)
 */
import { chromium } from 'playwright';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { browserPath } from './pw_browser.mjs';

const file = process.argv[2] || 'docs/drawings/pv-gbr-scene.html';
if (!existsSync(file)) {
  console.error(`✗ 문서가 없다: ${file}\n  PYTHONPATH=src python tools/build_gbr_scene.py 를 먼저 돌릴 것`);
  process.exit(2);
}

//: 창을 훑는 자리 — 창 길이에 대한 **비율**이다. 초로 박아 두면 후단 시각표가
//: 바뀌어 창이 밀렸을 때 엉뚱한 데를 찍고도 "안 움직인다" 로만 보인다.
//: 창은 페이지가 스스로 말해 주므로(파생본 모듈) 거기서 잡는다.
const FRACTIONS = [0.0, 0.15, 0.35, 0.55, 0.75, 0.9, 1.0];
//: 행 중심 (m) — `gbr_load.ROW_Z_MM` 이 제약에서 낸 값이다. 두 곳이 갈리면
//: `tests/test_pv_gbr.py` 가 먼저 실패한다.
const ROW_Z = { 'R-A': -2.3, 'R-B1': 2.3, 'R-B2': 2.3, HOLD: 0 };
const DECK_X = 3.175, DOCK_X = 6.375, ROW_TOL = 0.25;
//: 인터록 센서(BS-801)가 선 자리 — 셔틀 중심에서 하류로 1,480 (셀 로컬 x).
//: 색은 팔레트에서 오므로 **어느 행이 밝은가**로만 본다 — 팔레트 값을 박지 않는다.
const SENSOR_LOCAL_X = 9.955, SENSOR_ON = 1.0, SENSOR_OFF = 0.5;

const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
page.on('requestfailed', (r) => errors.push('요청 실패 ' + r.url().slice(0, 120)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(5000);

const scene = await page.evaluate(() => {
  const host = document.getElementById('jb-removal-operation');
  const S = host && host.__pvScene;
  if (!S) return { has3d: false };
  const crane = S.scene.getObjectByName('pvCrn'), casing = S.scene.getObjectByName('pvCase');
  const v = new S.Vector3(), cells = {}, stray = [];
  let meshes = 0, visible = 0;
  const shown = (o) => { for (let p = o; p; p = p.parent) if (!p.visible) return false; return true; };
  const cellOf = (o) => { for (let p = o; p; p = p.parent) if (p.userData && p.userData.cell) return p.userData.cell; return null; };
  S.scene.updateMatrixWorld(true);
  S.scene.traverse((o) => {
    if (!o.isMesh) return;
    meshes += 1;
    if (!shown(o)) return;
    visible += 1;
    o.getWorldPosition(v);
    const k = cellOf(o) || '—';
    cells[k] = (cells[k] || 0) + 1;
    if (!cellOf(o)) stray.push((o.userData && o.userData.label) || (o.geometry && o.geometry.type));
  });
  // ML-811 트윈마스트 여섯의 z 구간 — 설비끼리의 겹침은 기하 검사 다섯 중
  // 어느 것도 안 본다 (그것들은 «공정물 ↔ 설비» 와 «껍질 ↔ 기계» 를 묻는다).
  // 행을 옮기면서 마스트만 제자리에 남아 100 mm 파고든 적이 있어 여기서 잰다.
  const masts = [];
  S.scene.traverse((o) => {
    if (!o.isMesh || !o.geometry || o.geometry.type !== 'BoxGeometry') return;
    const q = o.geometry.parameters;
    if (Math.abs(q.width - 0.16) > 1e-6 || Math.abs(q.height - 2.65) > 1e-6) return;
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    const bb = o.geometry.boundingBox, m = o.matrixWorld;
    const a = new S.Vector3(bb.min.x, bb.min.y, bb.min.z).applyMatrix4(m);
    const c = new S.Vector3(bb.max.x, bb.max.y, bb.max.z).applyMatrix4(m);
    masts.push([Math.min(a.z, c.z), Math.max(a.z, c.z)]);
  });
  masts.sort((a, b) => a[0] - b[0]);
  return { has3d: true, meshes, visible, cells, stray: [...new Set(stray)], masts,
           shadows: S.renderer.shadowMap.enabled,
           crane: crane ? crane.visible : 'no pvCrn',
           casing: casing ? casing.visible : 'no pvCase',
           solo: window.__pvGbrScene ? { low: window.__pvGbrScene.low, high: window.__pvGbrScene.high,
                                         from: window.__pvGbrScene.from, to: window.__pvGbrScene.to } : null };
});

// 창은 페이지가 스스로 말한다 — 모델이 시계를 옮기면 검사도 따라간다.
if (!scene.solo) { console.error('✗ 파생본 모듈이 없어 창을 읽을 수 없다'); process.exit(1); }
const window0 = Number(scene.solo.from), window1 = Number(scene.solo.to);

const sample = async (t) => {
  await page.evaluate((t) => {
    const s = document.getElementById('jb-scrub');
    s.value = String(t); s.dispatchEvent(new Event('input', { bubbles: true }));
  }, t);
  await page.waitForTimeout(600);
  // page.evaluate 는 인자를 **하나만** 넘긴다 — 묶어서 준다.
  return page.evaluate(({ SENSOR_X, ROW }) => {
    const host = document.getElementById('jb-removal-operation');
    const S = host.__pvScene, a = host.__pvInfeedTest.getAfrState();
    const v = new S.Vector3();
    let g = null;
    S.scene.traverse((o) => {
      if (g || !o.isMesh || !o.userData || o.userData.label !== 'AFR 무프레임 유리 적층체') return;
      let vis = true; for (let p = o; p; p = p.parent) if (!p.visible) vis = false;
      o.getWorldPosition(v);
      g = { x: +v.x.toFixed(2), y: +v.y.toFixed(2), z: +v.z.toFixed(2), vis: vis };
    });
    // 행별 인터록 센서 — 만재면 목표 행만 밝게 선다.
    const sensors = {};
    S.scene.traverse((o) => {
      if (!o.isMesh || !o.material || !o.material.emissive || !o.geometry) return;
      if (o.geometry.type !== 'SphereGeometry') return;
      if (Math.abs(o.position.x - SENSOR_X) > 0.6) return;
      o.getWorldPosition(v);
      const row = Math.abs(v.z - ROW.A) < 0.3 ? 'R-A' : Math.abs(v.z - ROW.B) < 0.3 ? 'R-B'
                : Math.abs(v.z) < 0.3 ? 'HOLD' : null;
      if (row) sensors[row] = { hex: '#' + o.material.emissive.getHexString(),
                                lit: +o.material.emissiveIntensity.toFixed(2) };
    });
    const status = document.getElementById('afr-buffer-status');
    return { transfer: a.bufferTransfer, recipe: a.recipe, slot: a.targetSlot,
             module: a.targetModule, full: a.bufferFull, counts: a.bufferCounts,
             glass: g, sensors: sensors,
             status: status ? status.textContent.trim().replace(/\s+/g, ' ') : null };
  }, { SENSOR_X: SENSOR_LOCAL_X, ROW: { A: ROW_Z['R-A'], B: ROW_Z['R-B1'] } });
};

const setRoute = async (mode) => {
  // 조작은 「통합 시뮬레이션」 팝업 안에 있다 — 열지 않고 값만 바꿔 이벤트를 흘린다.
  await page.evaluate((m) => {
    const s = document.getElementById('afr-route-mode');
    s.value = m; s.dispatchEvent(new Event('change', { bubbles: true }));
  }, mode);
  await page.waitForTimeout(400);
};

const frames = [];
if (scene.has3d) {
  for (const t of FRACTIONS.map((x) => +(window0 + x * (window1 - window0)).toFixed(3))) {
    frames.push({ t: t, ...(await sample(t)) });
  }
}

// 목표 캐리지를 바꾸면 유리가 다른 행에 들어가는가 — 이 셀의 유일한 조작이다.
const routes = [];
if (scene.has3d) {
  for (const [mode, code] of [['r-a', 'R-A'], ['r-b1', 'R-B1'], ['hold', 'HOLD']]) {
    await setRoute(mode);
    const end = await sample(window1);
    routes.push({ mode: mode, want: code, ...end });
  }
}

// 만재 — 적재를 승인하지 않고 유리를 상류 잠금 게이트에 남긴다. 이 셀에서 화면이
// **아무 일도 안 일어나는 것처럼 보이는** 유일한 경우라, 그 대신 무엇이 서는지를 잰다.
let full = null, recovered = null;
if (scene.has3d) {
  await setRoute('buffer-full');
  full = await sample(window1);
  await page.evaluate(() => document.getElementById('afr-buffer-reset').click());
  await page.waitForTimeout(400);
  recovered = await sample(window1);
}
await browser.close();

const why = [];
if (!scene.has3d) why.push('3D 장면이 서지 않았다 (__pvScene 없음)');
else {
  if (scene.visible < 80) why.push(`보이는 메시가 ${scene.visible} 개뿐이다 — 셀이 통째로 꺼졌다`);
  if (scene.visible >= scene.meshes) why.push('아무것도 꺼지지 않았다 — 플랜트 전체가 그대로다');
  const others = Object.keys(scene.cells).filter((k) => k !== 'buffer' && k !== '—');
  if (others.length) why.push(`다른 셀이 켜져 있다: ${others.map((k) => k + ' ' + scene.cells[k]).join(', ')}`);
  // 셀에 안 매인 것으로 남아도 되는 것은 바닥면과 이 셀의 엣지 캐비닛뿐이다.
  const allowed = /^(PlaneGeometry|EC-BUF)/;
  const leaked = scene.stray.filter((s) => !allowed.test(String(s)));
  if (leaked.length) why.push(`셀 밖 설비가 남았다: ${leaked.slice(0, 4).join(', ')}`);
  if (scene.shadows !== false) why.push('섀도맵이 아직 켜져 있다');
  if (scene.casing !== false) why.push(`외장 케이싱이 꺼지지 않았다 (${scene.casing})`);
  if (scene.crane !== false) why.push(`천장크레인이 꺼지지 않았다 (${scene.crane})`);
  // 마스트 여섯 — 서로 겹치지 않고, 가드 기둥 안쪽 면(±3.45)을 넘지 않을 것.
  if (scene.masts.length !== 6) why.push(`ML-811 마스트가 ${scene.masts.length}본이다 (6본이어야 한다)`);
  for (let i = 1; i < scene.masts.length; i += 1) {
    const gap = scene.masts[i][0] - scene.masts[i - 1][1];
    if (gap < 0) why.push(`마스트가 서로 ${Math.round(-gap * 1000)} mm 파고든다`
      + ` (${scene.masts[i - 1].join('…')} ↔ ${scene.masts[i].join('…')})`);
  }
  const outer = scene.masts.length
    ? Math.max(-scene.masts[0][0], scene.masts[scene.masts.length - 1][1]) : 0;
  if (outer > 3.45 + 1e-6)
    why.push(`외측 마스트가 가드 기둥 안쪽 면을 ${Math.round((outer - 3.45) * 1000)} mm 넘는다`);
}
// 창 안에서 유리가 GI → 데크 → 목표 행 → 슬롯으로 실제로 간다.
if (frames.length) {
  const first = frames[0], last = frames[frames.length - 1];
  if (!frames.every((f) => f.glass && f.glass.vis)) why.push('창 안에서 유리가 보이지 않는 프레임이 있다');
  if (first.transfer > 0.02) why.push(`창이 이미 적재 중에 시작한다 (transfer=${first.transfer})`);
  if (last.transfer < 0.999) why.push(`창 끝에서도 적재가 끝나지 않았다 (transfer=${last.transfer})`);
  if (Math.abs(first.glass.x - DECK_X) < 0.5) why.push('창 시작에서 유리가 이미 데크 위다 — 인계가 창 밖이다');
  const onDeck = frames.some((f) => Math.abs(f.glass.x - DECK_X) < 0.2 && Math.abs(f.glass.z) < 0.2);
  if (!onDeck) why.push('유리가 데크 중심(픽업 정지)에 서는 프레임이 없다');
  const wantZ = ROW_Z[last.recipe];
  if (wantZ === undefined) why.push(`목표 레시피를 모르겠다 (${last.recipe})`);
  else if (Math.abs(last.glass.z - wantZ) > ROW_TOL)
    why.push(`유리가 ${last.recipe} 행(z=${wantZ})이 아니라 z=${last.glass.z} 에 있다`);
  if (Math.abs(last.glass.x - DOCK_X) > 0.4)
    why.push(`유리가 도크 캐리지(x=${DOCK_X})가 아니라 x=${last.glass.x} 에 있다`);
}
// 레시피를 바꾸면 행이 바뀐다.
for (const r of routes) {
  if (r.recipe !== r.want) why.push(`레시피 ${r.mode} 를 골랐는데 목표가 ${r.recipe} 다`);
  const wantZ = ROW_Z[r.want];
  if (r.glass && Math.abs(r.glass.z - wantZ) > ROW_TOL)
    why.push(`${r.want} 를 골랐는데 유리가 z=${r.glass.z} 에 들어갔다 (${wantZ} 이어야 한다)`);
}
// 만재는 **적재를 안 하는 것**이 정답이다 — 안 움직이는 것과 구분해서 잰다.
if (full) {
  if (!full.full) why.push('만재를 골랐는데 bufferFull 이 서지 않는다');
  if (full.transfer > 0) why.push(`만재인데 적재가 돌았다 (transfer=${full.transfer})`);
  if (full.glass && full.glass.vis)
    why.push(`만재인데 유리가 셀 안에 보인다 (x=${full.glass.x}) — 상류 게이트에 남아야 한다`);
  if (!/FULL/.test(full.status || '')) why.push(`버퍼 표시가 만재를 안 알린다: ${full.status}`);
  const target = full.recipe === 'HOLD' ? 'HOLD' : full.recipe.slice(0, 3);
  const lit = full.sensors[target];
  if (!lit) why.push(`${target} 행의 인터록 센서를 못 찾았다`);
  else {
    if (lit.lit < SENSOR_ON) why.push(`만재인데 ${target} 인터록이 안 켜졌다 (${lit.lit})`);
    for (const [row, s] of Object.entries(full.sensors)) {
      if (row !== target && s.lit >= SENSOR_OFF)
        why.push(`만재가 아닌 ${row} 행 인터록까지 켜졌다 (${s.lit})`);
    }
  }
}
if (recovered) {
  if (recovered.full) why.push('수량을 초기화했는데 만재가 안 풀렸다');
  if (recovered.transfer < 0.999) why.push(`초기화 뒤에도 적재가 안 돈다 (transfer=${recovered.transfer})`);
  if (!recovered.glass || !recovered.glass.vis) why.push('초기화 뒤에도 유리가 안 보인다');
}
if (errors.length) why.push('페이지 오류: ' + [...new Set(errors)].slice(0, 3).join(' | '));

console.log(`${why.length ? '✗' : '✓'} ${file}`);
if (scene.has3d) {
  console.log(`  메시 ${scene.visible} / ${scene.meshes} 보임 · 셀 ${JSON.stringify(scene.cells)}`
    + `\n  그림자 ${scene.shadows} · 케이싱 ${scene.casing} · 크레인 ${scene.crane}`
    + (scene.solo ? ` · 창 [${scene.solo.from}, ${scene.solo.to}] s · x [${scene.solo.low}, ${scene.solo.high}] m` : ''));
  console.log('  마스트 z ' + scene.masts.map((a) => a.map((n) => n.toFixed(2)).join('…')).join(' · '));
  for (const f of frames) {
    console.log(`  ${String(f.t).padStart(7)} s  적재 ${(f.transfer * 100).toFixed(0).padStart(3)} %  `
      + `유리 (${String(f.glass.x).padStart(5)}, ${String(f.glass.y).padStart(4)}, ${String(f.glass.z).padStart(5)})  `
      + `목표 ${f.recipe} M${f.module}-S${f.slot}${f.full ? ' FULL' : ''}`);
  }
  for (const r of routes) {
    console.log(`  경로 ${r.mode.padEnd(5)} → ${String(r.recipe).padEnd(5)} · 유리 z ${r.glass.z}`);
  }
  if (full) {
    const lamps = Object.entries(full.sensors)
      .map(([row, s]) => `${row} ${s.hex}@${s.lit}`).join(' · ');
    console.log(`  만재     → 적재 ${full.transfer * 100} % · 유리 ${full.glass.vis ? '보임' : '상류 게이트'}`
      + ` (x ${full.glass.x}) · ${full.status}\n           램프 ${lamps}`);
  }
  if (recovered) {
    console.log(`  초기화   → 적재 ${(recovered.transfer * 100).toFixed(0)} % · 유리 `
      + `(${recovered.glass.x}, ${recovered.glass.z}) · ${recovered.status}`);
  }
}
if (why.length) console.error('  — ' + why.join('\n  — '));
console.log(why.length ? `✗ ${why.length} 건`
  : '✓ GBR-301 만 서서 인계·분기·적재를 다 돌고, 만재면 승인하지 않는다');
process.exit(why.length ? 1 : 0);
