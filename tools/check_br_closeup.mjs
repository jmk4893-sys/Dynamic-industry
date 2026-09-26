/* SG-301 연마 확대도가 **실제로 도는지** 브라우저로 잰다.
 *
 * 글자로만 확인하면 놓치는 것들이 있다 — 부품이 안 그려져도 표는 나오고,
 * 단계를 넘겨도 형상이 안 움직일 수 있다. 그래서 여기서 재는 것은 셋이다:
 * 페이지 오류 0, 세 유닛의 메시가 실제로 섰는가, 그리고 단계를 넘길 때
 * 헤드·유리가 **자리를 바꾸는가**.
 *
 * 순환은 모델이 정한 값과 화면 값이 같아야 한다 — 장변과 단변이 겹치면
 * 여기서 걸린다.
 *
 * 실행:  node tools/check_sg_closeup.mjs
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { browserPath } from './pw_browser.mjs';

const FILE = 'docs/drawings/pv-br-closeup.html';
const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
await page.goto('file://' + resolve(FILE), { waitUntil: 'load' });
await page.waitForFunction(() => window.__pvBrCloseup, null, { timeout: 30000 });
await page.waitForTimeout(1500);

const got = await page.evaluate(() => {
  const A = window.__pvBrCloseup;
  const out = { units: A.units, cycle: A.cycle, mag: A.mag, feed: A.feed, moves: {}, counts: {} };
  const at = (unit, s) => A.positions(unit, s);
  for (const u of ['br305', 'contact']) {
    const a = at(u, 0), b = at(u, 4);
    out.counts[u] = Object.keys(a).length;
    let worst = 0, who = '';
    for (const k of Object.keys(a)) {
      if (!b[k]) continue;
      const d = Math.hypot(b[k][0] - a[k][0], b[k][1] - a[k][1], b[k][2] - a[k][2]);
      if (d > worst) { worst = d; who = k; }
    }
    out.moves[u] = { part: who, m: +worst.toFixed(3) };
  }
  /* 띠에는 구간 span 과 눈금 i 가 섞여 있다 — b 를 가진 것만 구간이다. */
  const band = [...document.getElementById('br-cu-band').children]
    .filter((s) => s.querySelector('b'))
    .map((s) => s.querySelector('b').textContent);
  out.marks = document.querySelectorAll('#br-cu-band .br-cu-mark').length;
  out.band = band; out.heads = A.heads; out.feed = A.feed;
  out.gantry = A.gantry; out.panel = A.panel;
  out.rows = document.getElementById('br-cu-rows').children.length;
  out.spec = document.getElementById('br-cu-spec').children.length;
  out.stars = (document.getElementById('br-cu').textContent.match(/\*\*/g) || []).length;
  return out;
});
await browser.close();

const c = got.cycle;
const bad = [];
if (errors.length) bad.push(`페이지 오류 ${errors.length}: ${errors.slice(0, 2).join(' | ')}`);
if (got.units !== 2) bad.push(`유닛 ${got.units} — 2 이어야 한다`);
for (const u of ['br305', 'contact']) {
  if (!got.counts[u]) bad.push(`${u}: 부품이 하나도 안 섰다`);
  /* 움직였는가만 보면 단위를 틀려도 통과한다 — sg 쪽에서 한 번 그렇게 당했다:
     자리 변화를 mm 로 셈해 놓고 m 에 그대로 넣어 유리가 1,400 **m** 를 갔는데도
     '움직인다' 였다. 그래서 위아래를 다 막는다. 움직이는 것이 판이 아니라
     **갠트리**이므로 상한은 판 길이가 아니라 **행정**에 여유를 둔 값이다. */
  const cap = u === 'br305' ? got.gantry.strokeMm / 1000 * 1.1 : 3.0;
  if (got.moves[u].m < 0.02) bad.push(`${u}: 단계를 넘겨도 안 움직인다 (최대 ${got.moves[u].m} m)`);
  if (got.moves[u].m > cap) bad.push(`${u}: ${got.moves[u].part} 가 ${got.moves[u].m} m 움직였다`
    + ` — 행정 ${cap.toFixed(2)} m 를 넘는다 (mm 를 m 에 넣지 않았는지 볼 것)`);
}
/* **판이 아니라 갠트리가 움직여야 한다.** 진공 테이블에 물린 판이 움직이면
   흡착이 의미가 없다 — 이 검사가 그 뒤집힘을 막는다. */
if (got.moves.br305.part === 'panel' || got.moves.br305.part === 'table')
  bad.push(`${got.moves.br305.part} 가 가장 많이 움직였다 — 진공 테이블에 물린 판은 서 있어야 한다`);
if (got.moves.br305.m < 1.0) bad.push(`갠트리가 ${got.moves.br305.m} m 만 갔다 — 판을 안 건넌다`);
if (got.gantry.strokeMm < got.panel.l) bad.push(`행정 ${got.gantry.strokeMm} 이 판 길이 ${got.panel.l} 보다 짧다`);
if (got.gantry.machineMm < got.gantry.strokeMm) bad.push('기계 길이가 행정보다 짧다');
/* 깊이 창이 계산에서 오는가 */
if (!(c.lo < c.minCut && c.minCut < c.target && c.target < c.maxCut && c.maxCut < c.hi))
  bad.push(`깊이 창 순서가 깨졌다: ${c.lo} < ${c.minCut} < ${c.target} < ${c.maxCut} < ${c.hi}`);
if (c.lo !== c.backsheet) bad.push(`창 하한 ${c.lo} 이 백시트 ${c.backsheet} 과 다르다`);
/* 채택된 기준면은 **윗면 측정**이다. 테이블 기준이 창을 넘는다는 것이
   그 판단의 근거이므로 둘을 같이 본다 — 테이블 기준이 들어 버리면 측정이
   필요 없어지고, 측정이 안 들면 기계가 성립하지 않는다. */
if (c.tableFits) bad.push(`테이블 기준이 창에 든다 (${c.tableMargin} 배) — 그러면 Z 측정을 넣을 이유가 없다`);
if (c.tableMargin >= 1) bad.push(`테이블 기준 여유 ${c.tableMargin} 배가 1 이상이다`);
if (!c.measuredFits) bad.push(`윗면 측정이 창에 안 든다 (${c.sensorTol} mm) — 물러설 자리가 없다`);
if (c.measuredMargin <= c.tableMargin) bad.push('측정이 테이블 기준보다 못하다');
if (c.platenAdopted) bad.push('압반이 아직 채택돼 있다 — 진공 테이블과 겹친다');
if (!c.vacuumFits) bad.push(`흡착 ${c.vacuumCycleS} s 가 예산 ${c.vacuumBudgetS} s 를 넘는다`);
if (!c.visionSees) bad.push('비전이 잣대보다 굵다');
if (c.visionMinMm2 >= c.visionMarkMm2) bad.push('비전 최소 조각이 잣대보다 크다');
if (!c.closesBothWays) bad.push('깊이 공차가 양쪽으로 안 닫힌다');
/* BR-305 는 자기 스테이션이다 — AFR 정반 점유와 견주면 안 된다(그것은 SG-301
   이야기다). 견줄 대상은 라인의 택트 하한이고, 넘으면 이 유닛이 병목이 된다. */
if (c.occupancy > c.taktFloor) bad.push(`점유 ${c.occupancy} s 가 택트 하한 ${c.taktFloor} s 를 넘는다`);
if (!c.notBottleneck) bad.push(`이 유닛이 병목이 된다 (지금 병목 ${c.bottleneck} ${c.idealTakt} s)`);
if (c.marks.length !== 5) bad.push(`창 눈금 ${c.marks.length} 개 — 5 이어야 한다`);
if (got.marks !== 5) bad.push(`화면 눈금 ${got.marks} 개 — 5 이어야 한다`);
if (got.band.length !== 2) bad.push(`깊이 띠 구간 ${got.band.length} 개 — 2 이어야 한다`);
if (got.stars) bad.push(`화면에 별표 ${got.stars} 개가 그대로 보인다`);
if (!got.rows || !got.spec) bad.push('부품표·사양표가 비었다');

console.log(`${bad.length ? '✗' : '✓'} ${FILE}`);
console.log(`  유닛 ${got.units} · 부품 메시 br305 ${got.counts.br305}`
  + ` / contact ${got.counts.contact} · 접촉부 배율 ${got.mag}배 · 헤드 ${got.heads}`);
console.log(`  단계 이동 — br305 ${got.moves.br305.part} ${got.moves.br305.m} m ·`
  + ` contact ${got.moves.contact.part} ${got.moves.contact.m} m`);
console.log(`  갠트리 행정 ${got.gantry.strokeMm} mm · 기계 길이 ${got.gantry.machineMm} mm`
  + ` (판 ${got.panel.l} 의 ${(got.gantry.machineMm / got.panel.l).toFixed(1)} 배)`);
console.log(`  깊이 창 ${c.lo}–${c.hi} mm · 실제 ${c.minCut}–${c.maxCut} · 목표 ${c.target}`
  + ` · 테이블 기준 ${c.tableMargin} 배(못 듦) → 윗면 측정 ±${c.sensorTol} 로 ${c.measuredMargin} 배`);
console.log(`  진공 ${c.vacuumKpa} kPa ${c.vacuumHoldKn} kN · 흡착 ${c.vacuumCycleS} s / 예산 ${c.vacuumBudgetS} s`
  + ` · 비전 ${c.visionMinMm2} mm² / 잣대 ${c.visionMarkMm2} mm²`);
console.log(`  이송 ${got.feed.mmS} mm/s · 벨트 ${got.feed.beltMS} m/s · 통과 ${got.feed.passMm} mm`
  + ` · 점유 ${c.occupancy} s / 택트 하한 ${c.taktFloor} s (병목 ${c.bottleneck} ${c.idealTakt} s)`);
console.log('');
if (bad.length) { bad.forEach((b) => console.log('   ✗ ' + b)); process.exit(1); }
console.log('\n✓ 두 유닛이 서고, 갠트리가 선 판을 건너며, 깊이 창이 계산에서 온다');
