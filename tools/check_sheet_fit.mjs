/* 2D 시트가 프레임 안에 들어가는가 — 그리고 렌더할 때마다 같은 크기인가.
 *
 * 이 도면의 시트는 `fitSheet()` 이 내용에 맞춰 viewBox 를 키운다. 넘치면
 * 잘리는 대신 프레임이 넓어지므로 "잘림"은 생기지 않는데, 그 대신 조용한
 * 결함이 하나 생긴다 — **프레임이 렌더할 때마다 달라진다.**
 *
 * 되먹임이다. 긴 글이 시트 폭 1,400 을 넘으면 fitSheet 이 viewBox 를 넓히고,
 * viewBox 가 넓어지면 축척(container ÷ viewBox)이 줄어 같은 글자가 더 작은
 * 실화면 크기로 그려지며, 글리프 어드밴스 반올림이 달라져 사용자단위 길이가
 * 또 바뀐다. REV.27 의 스마트 시트는 이 되먹임으로 프레임이 1,502 ↔ 1,581 을
 * 오갔다 — 두 번 열면 두 번 다른 도면이 나오는 상태였다.
 *
 * 원인은 언제나 같다: 긴 글에 `data-fit` 을 안 준 것. data-fit 이 있으면
 * fitSheet 이 먼저 잘라서 폭 안에 넣으므로 되먹임이 시작되지 않는다.
 *
 * 그래서 이 검사가 묻는 것은 둘이다.
 *   ① 내용의 오른쪽 끝이 시트 폭 SHEET_W 안에 드는가 (세로는 자유 — 시트가
 *      길어지는 것은 설계상 허용이고, 넓어지는 것만 규약 위반이다)
 *   ② 두 번 렌더해도 같은 값이 나오는가
 *
 * 실행:  npm i playwright && npx playwright install chromium
 *        node tools/check_sheet_fit.mjs [파일]
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 시트 규약 폭 (사용자단위). fitSheet 의 하한과 같아야 한다. */
const SHEET_W = 1400;

/** 도면 묶음 탭 — id 는 pv-tab-<key>. */
const TABS = ['fab', 'explode', 'layout', 'register', 'electrical', 'smart', 'mount'];

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3400);

// 도면 묶음은 dialog 안에 있다. 감춰진 채로는 getBBox 가 0 을 돌려주므로
// (그래서 로드 시점의 fitSheet 은 아무것도 재지 못한다) 열어 놓고 잰다.
await page.evaluate(() => {
  const dialog = document.getElementById('pv-v22-dialog');
  if (dialog && !dialog.open) dialog.showModal();
  const panel = document.getElementById('pv-v22-panel-drawing');
  if (panel) panel.hidden = false;
});
await page.waitForTimeout(400);

/** 보이는 패널의 컨트롤을 흔들어 다시 그리게 한다 — 되먹임을 드러내려면 필요하다. */
const rerender = () => page.evaluate(() => {
  for (const panel of document.querySelectorAll('[id^="pv-panel-"]')) {
    if (panel.hidden) continue;
    for (const control of panel.querySelectorAll('select, input[type="checkbox"]')) {
      control.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
});

const measure = () => page.evaluate(() => {
  const out = [];
  for (const svg of document.querySelectorAll('svg.pv-sheet')) {
    if (!svg.getBoundingClientRect().width) continue;
    const box = (svg.getAttribute('viewBox') || '0 0 0 0').split(' ').map(Number);
    let right = 0, bottom = 0, worst = '';
    for (const node of svg.querySelectorAll('text, rect, line, polyline, circle, path')) {
      if (node.id === 'pv-sheet-frame') continue;
      let b;
      try { b = node.getBBox(); } catch { continue; }
      if (!b.width && !b.height) continue;
      if (b.x + b.width > right) {
        right = b.x + b.width;
        worst = (node.textContent || node.tagName).slice(0, 44);
      }
      bottom = Math.max(bottom, b.y + b.height);
    }
    out.push({ id: svg.id, w: box[2], h: box[3],
               right: Math.round(right), bottom: Math.round(bottom), worst });
  }
  return out;
});

const offenders = [];
for (const tab of TABS) {
  const found = await page.evaluate((key) => {
    const button = document.getElementById('pv-tab-' + key);
    if (!button) return false;
    button.click();
    return true;
  }, tab);
  if (!found) { console.log(`  ? ${tab} — 탭이 없다`); continue; }
  await page.waitForTimeout(420);
  await rerender();
  await page.waitForTimeout(420);
  const first = await measure();
  await rerender();
  await page.waitForTimeout(420);
  const second = await measure();

  for (let i = 0; i < first.length; i += 1) {
    const a = first[i], b = second[i] || first[i];
    const over = a.right - SHEET_W;
    const unstable = a.w !== b.w;
    const mark = (over > 0 || unstable) ? '✗' : '·';
    if (over > 0 || unstable) offenders.push({ tab, ...a, second: b.w });
    console.log(`  ${mark} ${tab.padEnd(10)} ${a.id.padEnd(18)} 프레임 ${a.w}×${a.h}`
      + `  내용 ${a.right}×${a.bottom}`
      + (over > 0 ? `  폭 초과 ${over}` : '')
      + (unstable ? `  재렌더 프레임 ${b.w}` : ''));
    if (over > 0) console.log(`      최우측: ${a.worst}`);
  }
}

if (errors.length) {
  console.error('✗ 페이지 오류: ' + errors.join(' | '));
  await browser.close();
  process.exit(2);
}
if (offenders.length) {
  console.error(`\n✗ 시트 ${offenders.length}장이 폭 ${SHEET_W} 을 넘거나 렌더마다 달라진다 — `
    + '넘치는 글에 data-fit 을 주면 fitSheet 이 먼저 잘라서 되먹임이 끊긴다');
  await browser.close();
  process.exit(1);
}
console.log(`\n✓ 시트 ${TABS.length}탭이 폭 ${SHEET_W} 안에 들고 두 번 렌더해도 같은 프레임이다`);
await browser.close();
