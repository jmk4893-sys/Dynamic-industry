/* GI 검사 확대도가 **실제로 도는지** 브라우저로 잰다.
 *
 * 글자로만 확인하면 놓치는 것들이 있다 — 부품이 안 그려져도 표는 나오고,
 * 단계를 넘겨도 형상이 안 움직일 수 있다. 그래서 여기서 재는 것은 셋이다:
 * 페이지 오류 0, 세 유닛의 메시가 실제로 섰는가, 그리고 단계를 넘길 때
 * 판이 **자리를 바꾸는가**.
 *
 * 자리표는 모델이 정한 값과 화면 값이 같아야 한다 — 이음매가 비면 여기서
 * 걸린다. 그리고 이 셀의 결론(**화소가 아니라 자리 때문에 여러 대**)이
 * 화면에서도 성립하는지를 수로 확인한다.
 *
 * 실행:  node tools/check_gi_closeup.mjs
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { browserPath } from './pw_browser.mjs';

const FILE = 'docs/drawings/pv-gi-closeup.html';
const UNITS = ['below', 'above', 'window'];
const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
await page.goto('file://' + resolve(FILE), { waitUntil: 'load' });
await page.waitForFunction(() => window.__pvGiCloseup, null, { timeout: 30000 });
await page.waitForTimeout(1500);

const got = await page.evaluate((units) => {
  const A = window.__pvGiCloseup;
  const out = { units: A.units, seam: A.seam, optics: A.optics, mag: A.mag,
                moves: {}, counts: {} };
  for (const u of units) {
    const a = A.positions(u, 0), b = A.positions(u, 4);
    out.counts[u] = Object.keys(a).length;
    let worst = 0, who = '';
    for (const k of Object.keys(a)) {
      if (!b[k]) continue;
      const d = Math.hypot(b[k][0] - a[k][0], b[k][1] - a[k][1], b[k][2] - a[k][2]);
      if (d > worst) { worst = d; who = k; }
    }
    out.moves[u] = { part: who, m: +worst.toFixed(4) };
  }
  out.band = [...document.getElementById('gi-cu-band').children]
    .map((s) => s.querySelector('b').textContent);
  out.rows = document.getElementById('gi-cu-rows').children.length;
  out.spec = document.getElementById('gi-cu-spec').children.length;
  out.stars = (document.getElementById('gi-cu').textContent.match(/\*\*/g) || []).length;
  return out;
}, UNITS);
await browser.close();

const s = got.seam, o = got.optics;
const bad = [];
if (errors.length) bad.push(`페이지 오류 ${errors.length}: ${errors.slice(0, 2).join(' | ')}`);
if (got.units !== 3) bad.push(`유닛 ${got.units} — 3 이어야 한다`);
for (const u of UNITS) {
  if (!got.counts[u]) bad.push(`${u}: 부품이 하나도 안 섰다`);
  /* 움직였는가만 보면 단위를 틀려도 통과한다 — SG 확대도에서 한 번 그렇게
     당했다: 자리 변화를 mm 로 셈해 놓고 m 에 그대로 넣어 유리가 1,400 **m**
     를 갔는데도 '움직인다' 였다. 그래서 위아래를 다 막는다. */
  if (got.moves[u].m < 0.002) bad.push(`${u}: 단계를 넘겨도 안 움직인다 (최대 ${got.moves[u].m} m)`);
  if (got.moves[u].m > 2.0) bad.push(`${u}: ${got.moves[u].part} 가 ${got.moves[u].m} m 움직였다`
    + ' — 장비 포락선을 넘는다 (mm 를 m 에 넣지 않았는지 볼 것)');
}
if (got.band.length !== s.cameras)
  bad.push(`자리 띠가 ${got.band.length} 칸 — 카메라 ${s.cameras} 대여야 한다`);
if (!s.covers) bad.push('자리표가 폭을 못 덮는다 — 이음매가 빈다');
/* 이 셀의 결론이 화면에서도 서는가: 한 대는 자리가 모자라고, 화소는 남는다. */
if (!(s.oneNeeds > s.allotted))
  bad.push(`한 대 안이 ${s.oneNeeds} mm 로 배정 ${s.allotted} mm 를 안 넘는다 — 결론이 바뀐다`);
if (!(s.sensorPx >= s.pixelsNeeded))
  bad.push(`센서 ${s.sensorPx} px 가 필요한 ${s.pixelsNeeded} px 에 모자란다 — '자리 때문' 이 아니게 된다`);
if (!(s.stack <= s.allotted))
  bad.push(`${s.cameras} 대 스택 ${s.stack} mm 가 배정 ${s.allotted} mm 를 넘는다`);
const span = s.seats[s.seats.length - 1].to - s.seats[0].from;
if (Math.abs(span - s.panelW) > 1e-6)
  bad.push(`자리표가 덮는 폭 ${span} ≠ 판 폭 ${s.panelW}`);
if (!(o.dof >= o.bow)) bad.push(`심도 ${o.dof} mm 가 판 휨 ${o.bow} mm 를 못 덮는다`);
if (got.stars) bad.push(`화면에 별표 ${got.stars} 개가 그대로 보인다`);
if (!got.rows || !got.spec) bad.push('부품표·사양표가 비었다');

console.log(`${bad.length ? '✗' : '✓'} ${FILE}`);
console.log(`  유닛 ${got.units} · 부품 메시 below ${got.counts.below}`
  + ` / above ${got.counts.above} / window ${got.counts.window} · 창 배율 ${got.mag}배`);
console.log(`  단계 이동 — below ${got.moves.below.part} ${got.moves.below.m} m ·`
  + ` above ${got.moves.above.part} ${got.moves.above.m} m ·`
  + ` window ${got.moves.window.part} ${got.moves.window.m} m`);
console.log(`  한 대면 ${s.oneNeeds} mm 인데 배정은 ${s.allotted} mm (${s.shortfall} 초과)`
  + ` → ${s.cameras} 대 · 스택 ${s.stack} mm`);
console.log(`  화소는 남는다 — 센서 ${s.sensorPx.toLocaleString()} px ≥ 필요 `
  + `${s.pixelsNeeded.toLocaleString()} px`);
console.log(`  자리 ${s.seats.map((t) => t.width.toFixed(0)).join(' / ')} mm ·`
  + ` 이음매 ${s.overlapEach} mm × ${s.cameras - 1} = ${s.overlapTotal} mm`);
console.log(`  창 ${o.window} mm · 심도 ${o.dof} mm ≥ 휨 ${o.bow} mm ·`
  + ` ${o.lineHz.toLocaleString()} line/s`);
if (bad.length) { bad.forEach((b) => console.log('   ✗ ' + b)); process.exit(1); }
console.log('\n✓ 세 유닛이 서고 단계마다 움직이며, 자리가 폭을 빈틈없이 덮는다');
