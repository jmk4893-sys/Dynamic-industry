/* 파생본의 배치도가 **이 셀만** 그리는지 브라우저로 확인한다.
 *
 * 존을 거른 것은 `renderLayout` 안에서 이름을 가리는 방식이라, 원본이 그 함수를
 * 손보면 조용히 다시 온 플랜트를 그릴 수 있다. 파이썬 시험은 생성된 글자만 보므로
 * 실제로 무엇이 그려졌는지는 못 본다 — 그리는 쪽이 던지는 예외도 마찬가지다.
 *
 * 그래서 여기서 재는 것은 그려진 SVG 다 — 존 상자가 평면·종단 둘뿐이고, 라벨에
 * JBR-201 말고 다른 셀 이름이 없고, 플랜트 전체 치수가 남아 있지 않을 것.
 *
 * 실행:  node tools/check_jbr_layout.mjs [문서.html]
 *        (인자를 안 주면 docs/drawings/pv-jbr-scene.html 을 본다)
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
  console.error(`✗ 문서가 없다: ${file}\n  PYTHONPATH=src python tools/build_jbr_scene.py 를 먼저 돌릴 것`);
  process.exit(2);
}

//: 배치도에 이름이 나오면 안 되는 이웃 셀들.
const OTHERS = ['AFU-101', 'BFC-101', 'RB-101', 'AFR-101', 'GI-30', 'GBR-301', 'GRM-401'];

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
  const b = [...document.querySelectorAll('button')]
    .find((x) => /장비 스펙·셀 배치/.test(x.textContent));
  if (b) b.click();
});
await page.waitForTimeout(1200);
await page.evaluate(() => document.getElementById('pv-tab-layout').click());
await page.waitForTimeout(1200);

const got = await page.evaluate(() => {
  const svg = document.getElementById('pv-layout-svg');
  const texts = [...svg.querySelectorAll('text')].map((t) => t.textContent.trim());
  const spec = document.querySelector('.pv-jbr-spec');
  const focus = document.querySelector('label[for="pv-layout-focus"]');
  return {
    stations: svg.querySelectorAll('.pv-layout-station').length,
    safety: svg.querySelectorAll('.pv-layout-safety').length,
    zoneNames: [...svg.querySelectorAll('text.pv-layout-text')].map((t) => t.textContent.trim()),
    texts: texts,
    specRows: spec ? spec.querySelectorAll('tbody tr').length : 0,
    specBadge: spec ? (spec.querySelector('.viz-badge') || {}).textContent : '',
    focusShown: focus ? getComputedStyle(focus).display !== 'none' : false,
    title: (svg.querySelector('title') || {}).textContent || '',
  };
});
await browser.close();

const why = [];
// 존 상자는 평면 1 + 종단 1 = 2 개여야 한다. 7 개 존이 남아 있으면 14 개가 된다.
if (got.stations !== 2) why.push(`존 상자가 ${got.stations} 개 (2 여야 한다)`);
if (got.safety !== 1) why.push(`안전구역이 ${got.safety} 개 (1 이어야 한다)`);
if (got.zoneNames.join('|') !== 'JBR-201') why.push(`존 이름이 [${got.zoneNames}]`);
const leaked = OTHERS.filter((n) => got.texts.some((t) => t.includes(n)));
if (leaked.length) why.push(`이웃 셀 이름이 남았다: ${leaked.join(', ')}`);
const totals = got.texts.filter((t) => /전체 X|전체 Y|50,075/.test(t));
if (totals.length) why.push(`플랜트 전체 치수가 남았다: ${totals.join(' / ')}`);
if (!got.texts.some((t) => /셀 X = /.test(t))) why.push('셀 X 치수가 없다');
if (!got.texts.some((t) => /셀 Y = /.test(t))) why.push('셀 Y 치수가 없다');
if (got.specRows !== 3) why.push(`스펙이 ${got.specRows} 줄 (가로·세로·높이 3 줄이어야 한다)`);
if (!/\d.* × .* × .* mm/.test(got.specBadge)) why.push(`스펙 배지가 «${got.specBadge}»`);
if (got.focusShown) why.push('배치 초점 선택이 아직 보인다');
if (!got.title.includes('JBR-201')) why.push(`도면 이름이 «${got.title}»`);
if (errors.length) why.push('페이지 오류: ' + [...new Set(errors)].join(' | '));

console.log(`${why.length ? '✗' : '✓'} 존 상자 ${got.stations} · 이름 [${got.zoneNames}] · `
  + `스펙 ${got.specRows} 줄 ${got.specBadge} · ${got.title}`);
if (why.length) console.error('  — ' + why.join('\n  — '));
console.log(why.length ? `✗ ${why.length} 건` : '✓ 배치도가 이 셀만 그린다');
process.exit(why.length ? 1 : 0);
