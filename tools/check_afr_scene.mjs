/* AFR-101 파생본이 **혼자 서서 실제로 움직이는지** 브라우저로 확인한다.
 *
 * 파이썬 시험은 생성된 글자만 본다. 그런데 이 화면이 못 쓰게 되는 방식은 글자에
 * 남지 않는다 — REV.51 이 `STRUCTURE_RECIPES` 를 워크스페이스 IIFE 안에 두는 바람에
 * 3D 모듈의 `pvStructure()` 가 늘 '미등록'을 읽었고, JBR 허가검사의
 * structure_recipe_ok 가 항상 거짓이라 AFR 이 창 39.03 s 내내 1 단계에 멈춰 있었다.
 * 글자로는 아무 흔적이 없다. 그래서 여기서 재는 것은 **움직임**이다.
 *
 *   ① 페이지 오류 0 · 3D 가 실제로 섰을 것
 *   ② 보이는 것이 afr 셀뿐일 것 — 다른 셀의 형상이 한 점도 켜져 있지 않을 것
 *   ③ 발주 요청 셋 — 섀도맵 off · 외장 케이싱(pvCase) off · 천장크레인(pvCrn) off
 *   ④ 창을 훑으면 6 단계를 다 지나고, 단축 밀어내기와 장축 인발이 설계값에 닿을 것
 *
 * 실행:  node tools/check_afr_scene.mjs [문서.html]
 *        (인자를 안 주면 docs/drawings/pv-afr-scene.html 을 본다)
 */
import { chromium } from 'playwright';
import { existsSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

function browserPath() {
  if (process.env.PW_CHROMIUM) return process.env.PW_CHROMIUM;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH || '/opt/pw-browsers';
  if (!existsSync(root)) return undefined;
  for (const d of readdirSync(root).filter((n) => n.startsWith('chromium-')).sort().reverse()) {
    const exe = join(root, d, 'chrome-linux', 'chrome');
    if (existsSync(exe)) return exe;
  }
  return undefined;
}

const file = process.argv[2] || 'docs/drawings/pv-afr-scene.html';
if (!existsSync(file)) {
  console.error(`✗ 문서가 없다: ${file}\n  PYTHONPATH=src python tools/build_afr_scene.py 를 먼저 돌릴 것`);
  process.exit(2);
}

//: 창을 훑는 시각 (s) — 6 단계가 모두 한 번씩 잡히도록 고른다.
const SAMPLES = [86, 93, 97, 104, 110, 116, 122];
//: 설계값 — 단축 밀어내기 120 mm(진행률 1.0) · 장축 LM 주행 1,300 mm · 끝단 벌림 55 mm.
const LONG_TRAVEL_MM = 1300, END_GAP_MM = 55;

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
  const v = new S.Vector3(), cells = {};
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
  });
  return { has3d: true, meshes, visible, cells,
           shadows: S.renderer.shadowMap.enabled,
           crane: crane ? crane.visible : 'no pvCrn',
           casing: casing ? casing.visible : 'no pvCase',
           solo: window.__pvAfrScene ? { low: window.__pvAfrScene.low, high: window.__pvAfrScene.high,
                                         from: window.__pvAfrScene.from, to: window.__pvAfrScene.to } : null };
});

const frames = [];
if (scene.has3d) {
  for (const t of SAMPLES) {
    await page.evaluate((t) => {
      const s = document.getElementById('jb-scrub');
      s.value = String(t); s.dispatchEvent(new Event('input', { bubbles: true }));
    }, t);
    await page.waitForTimeout(600);
    frames.push(await page.evaluate((t) => {
      const a = document.getElementById('jb-removal-operation').__pvInfeedTest.getAfrState();
      return { t: t, phase: a.phaseIndex, active: a.active, short: a.shortProgress,
               long: a.longTravelMm, gap: a.endGapMm, done: a.frameRemoved,
               name: document.getElementById('jb-stage-name').textContent };
    }, t));
  }
}
await browser.close();

const why = [];
if (!scene.has3d) why.push('3D 장면이 서지 않았다 (__pvScene 없음)');
else {
  if (scene.visible < 80) why.push(`보이는 메시가 ${scene.visible} 개뿐이다 — 셀이 통째로 꺼졌다`);
  if (scene.visible >= scene.meshes) why.push('아무것도 꺼지지 않았다 — 플랜트 전체가 그대로다');
  const others = Object.keys(scene.cells).filter((k) => k !== 'afr' && k !== '—');
  if (others.length) why.push(`다른 셀이 켜져 있다: ${others.map((k) => k + ' ' + scene.cells[k]).join(', ')}`);
  if (scene.shadows !== false) why.push('섀도맵이 아직 켜져 있다');
  if (scene.casing !== false) why.push(`외장 케이싱이 꺼지지 않았다 (${scene.casing})`);
  if (scene.crane !== false) why.push(`천장크레인이 꺼지지 않았다 (${scene.crane})`);
  if (!scene.solo) why.push('파생본 모듈이 붙지 않았다 (__pvAfrScene 없음)');
}
// 창 안에서 기구가 실제로 한 사이클을 돈다 — 여기가 REV.51 회귀를 잡는 자리다.
const phases = new Set(frames.map((f) => f.phase));
if (frames.length) {
  if (!frames.every((f) => f.active)) why.push('공정 허가가 나지 않아 AFR 이 서 있다 (active=false) — pvStructure() 를 볼 것');
  if (phases.size < 5) why.push(`창을 훑어도 단계가 ${[...phases].join(',')} 뿐이다 — 6 단계를 다 지나야 한다`);
  const last = frames[frames.length - 1];
  if (!last.done) why.push('창 끝에서도 프레임이 제거되지 않았다');
  if (Math.abs(last.long - LONG_TRAVEL_MM) > 1) why.push(`장축 주행이 ${last.long} mm (${LONG_TRAVEL_MM} 여야 한다)`);
  if (Math.abs(last.gap - END_GAP_MM) > 1) why.push(`끝단 벌림이 ${last.gap} mm (${END_GAP_MM} 여야 한다)`);
  if (Math.abs(last.short - 1) > 0.01) why.push(`단축 밀어내기 진행률이 ${last.short}`);
}
if (errors.length) why.push('페이지 오류: ' + [...new Set(errors)].slice(0, 3).join(' | '));

console.log(`${why.length ? '✗' : '✓'} ${file}`);
if (scene.has3d) {
  console.log(`  메시 ${scene.visible} / ${scene.meshes} 보임 · 셀 ${JSON.stringify(scene.cells)}`
    + `\n  그림자 ${scene.shadows} · 케이싱 ${scene.casing} · 크레인 ${scene.crane}`
    + (scene.solo ? ` · 창 [${scene.solo.from}, ${scene.solo.to}] s · x [${scene.solo.low}, ${scene.solo.high}] m` : ''));
  for (const f of frames) {
    console.log(`  ${String(f.t).padStart(3)} s  단계 ${f.phase}  단축 ${(f.short * 120).toFixed(0)} mm  `
      + `장축 ${String(f.long).padStart(6)} mm  벌림 ${f.gap} mm  ${f.done ? '제거완료' : ''}  ${f.name}`);
  }
}
if (why.length) console.error('  — ' + why.join('\n  — '));
console.log(why.length ? `✗ ${why.length} 건` : '✓ AFR-101 만 서서 6 단계를 다 돈다');
process.exit(why.length ? 1 : 0);
