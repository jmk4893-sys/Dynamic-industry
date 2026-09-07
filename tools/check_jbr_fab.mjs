/* 제작 도면집이 **실제로 그려지는지** 브라우저로 확인한다.
 *
 * 파이썬 시험은 글자만 본다 — 부품도 SVG 가 빈 채로 나가도 통과한다. 여기서
 * 재는 것은 그려진 결과다: 부품도 수, 구멍 표시, 분해도, 그리고 페이지 오류 0.
 *
 * 실행:  node tools/check_jbr_fab.mjs [문서.html]
 */
import { chromium } from 'playwright';
import { existsSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

function browserPath() {
  if (process.env.PW_CHROMIUM) return process.env.PW_CHROMIUM;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH || '/opt/pw-browsers';
  if (!existsSync(root)) return undefined;
  for (const d of readdirSync(root).filter((x) => x.startsWith('chromium-')).sort().reverse()) {
    const exe = join(root, d, 'chrome-linux', 'chrome');
    if (existsSync(exe)) return exe;
  }
  return undefined;
}

const file = process.argv[2] || 'docs/drawings/pv-jbr-fab.html';
if (!existsSync(file)) { console.error(`✗ 문서가 없다: ${file}`); process.exit(2); }

const browser = await chromium.launch({ executablePath: browserPath() });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(800);

const got = await page.evaluate(() => {
  const sheets = [...document.querySelectorAll('article.sheet')];
  const empty = sheets.filter((s) => {
    const svg = s.querySelector('svg.pd');
    return !svg || svg.querySelectorAll('*').length < 8;
  }).map((s) => s.id);
  const body = document.body.innerText;
  return {
    sheets: sheets.length,
    empty,
    svgs: document.querySelectorAll('svg').length,
    holeCircles: document.querySelectorAll('svg.pd circle').length,
    exploded: document.querySelectorAll('.explode svg').length,
    balloons: document.querySelectorAll('.balloons li').length,
    cards: document.querySelectorAll('section.card').length,
    chars: body.trim().length,
    wide: document.documentElement.scrollWidth > window.innerWidth + 2,
    hasLoad: /하중이 볼트를 정하지 않는다/.test(body),
    hasMass: /본체가 도면의 약 2\.2 t 보다/.test(body),
    hasLift: /실린더 2 개로는 승강부를 들지 못한다/.test(body),
  };
});
await browser.close();

const why = [];
if (got.sheets < 60) why.push(`부품도가 ${got.sheets} 장 (제작품 64 종)`);
if (got.empty.length) why.push(`빈 부품도: ${got.empty.slice(0, 5).join(', ')}${got.empty.length > 5 ? ' 외' : ''}`);
if (got.holeCircles < 100) why.push(`구멍 표시가 ${got.holeCircles} 개`);
if (got.exploded < 9) why.push(`분해도가 ${got.exploded} 개 (조립체 9)`);
if (got.balloons < 40) why.push(`분해도 풍선이 ${got.balloons} 개`);
if (got.chars < 20000) why.push(`본문이 ${got.chars} 자`);
if (got.wide) why.push('가로 스크롤이 생겼다');
if (!got.hasLoad) why.push('하중 검산 문구가 없다');
if (!got.hasMass) why.push('중량 소견이 없다');
if (!got.hasLift) why.push('승강 실린더 소견이 없다');
if (errors.length) why.push('페이지 오류: ' + [...new Set(errors)].join(' | '));

console.log(`${why.length ? '✗' : '✓'} 부품도 ${got.sheets} · 빈 ${got.empty.length} · 구멍 ${got.holeCircles} · `
  + `분해도 ${got.exploded} · 카드 ${got.cards} · ${got.chars} 자`);
if (why.length) console.error('  — ' + why.join('\n  — '));
console.log(why.length ? `✗ ${why.length} 건` : '✓ 제작 도면집이 다 그려진다');
process.exit(why.length ? 1 : 0);
