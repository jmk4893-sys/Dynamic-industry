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

const FILE = 'docs/drawings/pv-sg-closeup.html';
const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
await page.goto('file://' + resolve(FILE), { waitUntil: 'load' });
await page.waitForFunction(() => window.__pvSgCloseup, null, { timeout: 30000 });
await page.waitForTimeout(1500);

const got = await page.evaluate(() => {
  const A = window.__pvSgCloseup;
  const out = { units: A.units, cycle: A.cycle, mag: A.mag, feed: A.feed, moves: {}, counts: {} };
  const at = (unit, s) => A.positions(unit, s);
  for (const u of ['long', 'short', 'contact', 'scraper']) {
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
  const band = [...document.getElementById('sg-cu-band').children]
    .map((s) => s.querySelector('b').textContent);
  out.band = band;
  out.rows = document.getElementById('sg-cu-rows').children.length;
  out.spec = document.getElementById('sg-cu-spec').children.length;
  out.stars = (document.getElementById('sg-cu').textContent.match(/\*\*/g) || []).length;
  return out;
});
await browser.close();

const c = got.cycle;
const bad = [];
if (errors.length) bad.push(`페이지 오류 ${errors.length}: ${errors.slice(0, 2).join(' | ')}`);
if (got.units !== 4) bad.push(`유닛 ${got.units} — 4 이어야 한다`);
for (const u of ['long', 'short', 'contact', 'scraper']) {
  if (!got.counts[u]) bad.push(`${u}: 부품이 하나도 안 섰다`);
  /* 움직였는가만 보면 단위를 틀려도 통과한다 — 한 번 그렇게 당했다: 자리 변화를
     mm 로 셈해 놓고 m 에 그대로 넣어 유리가 1,400 **m** 를 갔는데도 '움직인다'
     였다. 그래서 위아래를 다 막는다. 이 장비의 어떤 부품도 2 m 를 안 넘는다. */
  if (got.moves[u].m < 0.02) bad.push(`${u}: 단계를 넘겨도 안 움직인다 (최대 ${got.moves[u].m} m)`);
  if (got.moves[u].m > 2.0) bad.push(`${u}: ${got.moves[u].part} 가 ${got.moves[u].m} m 움직였다`
    + ' — 장비 포락선을 넘는다 (mm 를 m 에 넣지 않았는지 볼 것)');
}
if (got.band.join('·') !== '앞단변·정착·장변 통과·정착·뒷단변')
  bad.push(`순환 상 배치가 다르다: ${got.band.join('·')}`);
if (Math.abs(c.total - (c.simultaneous + c.cost)) > 0.011)
  bad.push(`순차 비용이 안 맞는다: ${c.total} ≠ ${c.simultaneous} + ${c.cost}`);
if (c.total > c.afr) bad.push(`점유 ${c.total} s 가 AFR 정반 ${c.afr} s 를 넘는다`);
if (got.stars) bad.push(`화면에 별표 ${got.stars} 개가 그대로 보인다`);
if (!got.rows || !got.spec) bad.push('부품표·사양표가 비었다');

console.log(`${bad.length ? '✗' : '✓'} ${FILE}`);
console.log(`  유닛 ${got.units} · 부품 메시 long ${got.counts.long} / short ${got.counts.short}`
  + ` / contact ${got.counts.contact} / scraper ${got.counts.scraper} · 접촉부 배율 ${got.mag}배`);
console.log(`  단계 이동 — long ${got.moves.long.part} ${got.moves.long.m} m ·`
  + ` short ${got.moves.short.part} ${got.moves.short.m} m ·`
  + ` contact ${got.moves.contact.part} ${got.moves.contact.m} m ·`
  + ` scraper ${got.moves.scraper.part} ${got.moves.scraper.m} m`);
console.log(`  점유 ${c.total} s (동시라면 ${c.simultaneous} s · 순차 비용 ${c.cost} s)`
  + ` · AFR 정반 ${c.afr} s · 여유 ${c.slack} s`);
console.log(`  이송 장변 ${got.feed.long} mm/s · 단변 ${got.feed.short} mm/s`);
if (bad.length) { bad.forEach((b) => console.log('   ✗ ' + b)); process.exit(1); }
console.log('\n✓ 네 유닛이 서고 단계마다 움직이며, 장변과 단변이 겹치지 않는다');
