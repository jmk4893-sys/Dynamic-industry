/* 부품 2D·3D 목록이 **이 셀 품번만** 보여 주는지 브라우저로 확인한다.
 *
 * 검색창을 "JB-" 로 미리 채워 두었는데, 거르는 일은 열 때 한 번 도는 자바스크립트가
 * 한다 — 목록을 채우는 것이 module 스크립트라 파이썬 시험은 「value="JB-" 가 있다」
 * 까지만 볼 수 있고 실제로 몇 줄이 남았는지는 못 본다.
 *
 * 그래서 여기서 재는 것은 열린 목록이다 — 보이는 줄이 전부 JB- 이고, 원본이 딸려
 * 보내던 AFU-PT-101(주기에 JB-201 을 인용한다)이 섞이지 않을 것.
 *
 * 실행:  node tools/check_jbr_parts.mjs [문서.html]
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

const file = process.argv[2] || 'docs/drawings/pv-jbr-scene.html';
if (!existsSync(file)) {
  console.error(`✗ 문서가 없다: ${file}`);
  process.exit(2);
}

const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(4500);
await page.evaluate(() => {
  const b = [...document.querySelectorAll('[data-pv-program="parts"]')][0];
  if (b) b.click();
});
await page.waitForTimeout(1500);

const got = await page.evaluate(() => {
  const box = document.getElementById('pv-parts-filter');
  const cat = document.getElementById('jb-parts-catalog');
  const rows = [...cat.querySelectorAll('.jb-part-item')];
  const open = rows.filter((r) => !r.hidden);
  return {
    value: box ? box.value : '(검색창이 없다)',
    placeholder: box ? box.placeholder : '',
    total: rows.length,
    shown: open.length,
    nos: open.map((r) => r.dataset.partNo),
    groupsShown: [...cat.querySelectorAll('.jb-part-group')].filter((g) => !g.hidden).length,
    count: (document.getElementById('pv-parts-count') || {}).textContent || '',
  };
});

//: 검색창을 비우면 전 품번이 돌아와야 한다 — 목록을 지운 것이 아니라 거른 것이다.
await page.fill('#pv-parts-filter', '');
await page.waitForTimeout(400);
const cleared = await page.evaluate(() =>
  [...document.querySelectorAll('#jb-parts-catalog .jb-part-item')].filter((r) => !r.hidden).length);

//: 품명 검색은 그대로 돌아야 한다 (접두어꼴이 아닌 낱말).
await page.fill('#pv-parts-filter', '가위');
await page.waitForTimeout(400);
const byName = await page.evaluate(() =>
  [...document.querySelectorAll('#jb-parts-catalog .jb-part-item')].filter((r) => !r.hidden).length);
await browser.close();

const why = [];
if (got.value !== 'JB-') why.push(`검색창 기본값이 «${got.value}»`);
const leaked = got.nos.filter((n) => !String(n).startsWith('JB-'));
if (leaked.length) why.push(`이 셀 것이 아닌 품번이 보인다: ${leaked.join(', ')}`);
if (got.shown < 100) why.push(`보이는 품목이 ${got.shown} 개 (JB- 는 112 개다)`);
if (got.shown >= got.total) why.push(`거르지 않았다 — ${got.shown}/${got.total}`);
if (!/\d+ \/ \d+품목/.test(got.count)) why.push(`품목수 표시가 «${got.count}»`);
if (cleared !== got.total) why.push(`검색창을 비웠는데 ${cleared}/${got.total} 만 돌아왔다`);
if (byName < 1) why.push('품명 검색(「가위」)이 0 건 — 접두어 아닌 검색이 깨졌다');
if (/AFU-LFT/.test(got.placeholder)) why.push('예시가 아직 투입 구간 품번이다');
if (errors.length) why.push('페이지 오류: ' + [...new Set(errors)].join(' | '));

console.log(`${why.length ? '✗' : '✓'} 기본값 «${got.value}» · ${got.shown}/${got.total}품목 · `
  + `분류 ${got.groupsShown} · 비우면 ${cleared} · 「가위」 ${byName}`);
if (why.length) console.error('  — ' + why.join('\n  — '));
console.log(why.length ? `✗ ${why.length} 건` : '✓ 부품 목록이 이 셀 품번으로 열린다');
process.exit(why.length ? 1 : 0);
