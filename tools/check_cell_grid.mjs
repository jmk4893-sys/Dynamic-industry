/* 셀 격자 검사 — 3D 가 그리는 자리가 존 표가 준 자리인가.
 *
 * 이 플랜트에는 격자가 **둘** 있었다. 존 표(`layout.build_zones()`)는 셀 GA
 * 외형을 상류부터 이어 붙여 만들고, 케이싱·존 가드·EC 명판은 그것을 따른다.
 * 그런데 기계군은 씬에 손으로 놓은 좌표 위에 서 있었고, 두 격자가 AFR 아래에서
 * 4,600 mm 갈라졌다. 케이싱 검사도 하중 경로 검사도 이것을 못 본다 — 둘 다
 * "형상끼리" 를 묻지 "형상이 자기 존 안에 있는가" 를 묻지 않기 때문이다.
 *
 * 방법은 단순하다. 셀 그룹마다 `userData.cell` 로 자기 존을 밝히고
 * (씬의 `pvCell()`), 그 그룹 아래 메시의 X 실측 범위가 `pvZone` 의 자기 칸
 * 안에 드는지 본다. 태그가 없는 메시는 **숨기지 않고 따로 센다** — 귀속되지
 * 않은 형상이 있으면 이 검사는 그만큼 눈을 감고 있는 것이다.
 *
 * 실행 (저장소 루트에서):
 *     node tools/check_cell_grid.mjs docs/drawings/pv-preprocess-plant.html
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 존 밖으로 나가도 되는 것 — 건물·설비 공용이라 한 셀에 귀속되지 않는다. */
const SPANS_THE_PLANT = [
  'CRN-901',                 // 천장크레인 — 주행로가 전장을 넘는다
  'CMP-701 압축공기 주관',    // 통로 상부 DN20
  'MDB-101', 'LP-', 'F1',    // 전기 간선
];

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3400);

const result = await page.evaluate(() => {
  const host = document.getElementById('jb-removal-operation');
  if (!host || !host.__pvScene) return { error: '3D 장면 훅(__pvScene)을 찾지 못했다' };
  const zones = host.__pvScene.zone;
  if (!zones) return { error: 'pvZone 격자를 찾지 못했다' };

  const cells = {};       // cell → {x0,x1,n}
  const loose = [];       // 태그 없는 메시
  const spanOf = (o) => {
    o.updateWorldMatrix(true, false);
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    const bb = o.geometry.boundingBox;
    let x0 = 1e9, x1 = -1e9;
    for (let i = 0; i < 8; i++) {
      const v = new bb.min.constructor(
        i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y, i & 4 ? bb.max.z : bb.min.z,
      ).applyMatrix4(o.matrixWorld);
      x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x);
    }
    return [x0, x1];
  };
  const cellOf = (o) => {
    for (let p = o; p; p = p.parent) if (p.userData && p.userData.cell) return p.userData.cell;
    return null;
  };
  host.__pvScene.scene.traverse((o) => {
    if (!o.isMesh || !o.geometry) return;
    const key = cellOf(o);
    const [x0, x1] = spanOf(o);
    const label = (o.userData && o.userData.label) || '';
    if (!key) { loose.push({ label, x0, x1 }); return; }
    if (!cells[key]) cells[key] = { x0: 1e9, x1: -1e9, n: 0 };
    const c = cells[key];
    c.x0 = Math.min(c.x0, x0); c.x1 = Math.max(c.x1, x1); c.n += 1;
  });
  return { zones, cells, loose };
});
await browser.close();

if (result.error) { console.error('✗ ' + result.error); process.exit(1); }
if (errors.length) { console.error('✗ 페이지 오류:\n  ' + errors.join('\n  ')); process.exit(1); }

const { zones, cells, loose } = result;
const mm = (m) => (m * 1000).toFixed(0);
let worst = 0;
const rows = [];
for (const [key, z] of Object.entries(zones)) {
  const c = cells[key];
  if (!c) { rows.push({ key, state: '미귀속', over: null }); continue; }
  const up = z[0] - c.x0;          // 상류로 넘친 양 (양수면 넘침)
  const down = c.x1 - z[1];        // 하류로 넘친 양
  const over = Math.max(0, up, down);
  worst = Math.max(worst, over);
  rows.push({ key, z, c, up, down, over });
}

console.log(`셀 그룹 ${Object.keys(cells).length} · 태그 없는 메시 ${loose.length}`);
console.log(`\n${'존'.padEnd(8)} ${'존 X'.padStart(16)} ${'3D 실측 X'.padStart(16)} ${'상류넘침'.padStart(9)} ${'하류넘침'.padStart(9)}  메시`);
for (const r of rows) {
  if (!r.c) { console.log(`${r.key.padEnd(8)} ${'—'.padStart(16)} ${'그룹 없음'.padStart(16)}`); continue; }
  const flag = r.over > 0.05 ? '✗' : '·';
  console.log(`${flag} ${r.key.padEnd(6)} ${(r.z[0].toFixed(2) + '…' + r.z[1].toFixed(2)).padStart(16)}`
    + ` ${(r.c.x0.toFixed(2) + '…' + r.c.x1.toFixed(2)).padStart(16)}`
    + ` ${mm(Math.max(0, r.up)).padStart(9)} ${mm(Math.max(0, r.down)).padStart(9)}  ${r.c.n}`);
}

const notCovered = loose.filter((m) => !SPANS_THE_PLANT.some((k) => m.label.includes(k)));
if (notCovered.length) {
  const named = [...new Set(notCovered.map((m) => m.label).filter(Boolean))];
  console.log(`\n귀속되지 않은 메시 ${notCovered.length} (이름 있는 것 ${named.length}종)`);
  for (const n of named.slice(0, 12)) console.log('  · ' + n.slice(0, 66));
  if (named.length > 12) console.log(`  … 외 ${named.length - 12}종`);
}

const bad = rows.filter((r) => r.c && r.over > 0.05);
if (bad.length || notCovered.length) {
  console.log(`\n✗ 격자 미정합 — 존을 넘는 셀 ${bad.length} · 최대 ${mm(worst)} mm · 미귀속 메시 ${notCovered.length}`);
  process.exit(1);
}
console.log('\n✓ 모든 셀이 자기 존 안에 있다');
