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
 * REV.35 정정 — 탭만 돌면 각 탭의 **기본 시트만** 재고 끝났다. 전기 4장 중
 * 단선결선도 하나, 스마트 3장 중 네트워크 하나만 본 셈이다. 이제 패널 안의
 * 시트 선택 <select> 옵션을 하나씩 골라 가며 잰다. 셀 선택처럼 옵션이 많은
 * 것은 mtcheck 이 따로 보므로, 여기서는 시트 종류를 고르는 select 만 돈다.
 *
 * 실행:  npm i playwright && npx playwright install chromium
 *        node tools/check_sheet_fit.mjs [파일]
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 시트 규약 폭 (사용자단위). fitSheet 의 하한과 같아야 한다. */
const SHEET_W = 1400;

/** 도면 묶음 탭 — id 는 pv-tab-<key>.
 *
 *  **이 목록은 도면과 집합으로 맞춘다.** 손으로 적은 목록을 그냥 훑으면 검사가
 *  두 방향으로 눈을 감는다. 빠진 탭은 `?` 만 찍고 넘어가고, 새로 생긴 탭은
 *  애초에 목록에 없어 한 번도 안 열린다. 탭 하나 이름을 바꿔 재보니
 *  **시트 17 → 11 장으로 줄어든 채 「✓ 시트 11장(탭 9)」로 통과**했다 —
 *  커버리지 35 % 를 잃고도 초록이고, 성공 문장의 「탭 9」는 거짓이었다
 *  (`TABS.length` 를 찍기 때문에 실제로 몇 개를 열었는지와 무관했다). */
const TABS = ['fab', 'explode', 'layout', 'register', 'electrical', 'smart', 'mount', 'safety', 'ops'];

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

/** 시트 종류를 고르는 select — id 가 -view 로 끝난다. 셀·피더 선택은 아니다. */
const sheetViews = (tab) => page.evaluate((key) => {
  const panel = document.getElementById('pv-panel-' + key);
  if (!panel) return [];
  const select = panel.querySelector('select[id$="-view"]');
  if (!select) return [null];
  return Array.from(select.options).map((o) => o.value);
}, tab);

const pickView = (tab, value) => page.evaluate(([key, v]) => {
  if (v === null) return;
  const panel = document.getElementById('pv-panel-' + key);
  const select = panel.querySelector('select[id$="-view"]');
  select.value = v;
  select.dispatchEvent(new Event('change', { bubbles: true }));
}, [tab, value]);

/* 도면이 실제로 가진 탭을 먼저 센다 — 목록과 어긋나면 재기 전에 멈춘다. */
const onPage = await page.evaluate(() => Array.from(
  document.querySelectorAll('[id^="pv-tab-"]'), (b) => b.id.slice('pv-tab-'.length)));
const wanted = new Set(TABS), seen = new Set(onPage);
const gone = TABS.filter((t) => !seen.has(t));
const extra = onPage.filter((t) => !wanted.has(t));
if (gone.length || extra.length) {
  console.error('✗ 탭 목록이 도면과 다르다 — 재기 전에 멈춘다.'
    + (gone.length ? `\n  목록에 있는데 도면에 없다: ${gone.join(', ')}` : '')
    + (extra.length ? `\n  도면에 있는데 목록에 없다(한 번도 안 열린다): ${extra.join(', ')}` : '')
    + '\n  이 도구의 TABS 를 고친다 — 조용히 건너뛰면 커버리지가 줄어든 것을 아무도 모른다.');
  await browser.close();
  process.exit(1);
}

const offenders = [];
let sheets = 0;
let visited = 0;
for (const tab of TABS) {
  const found = await page.evaluate((key) => {
    const button = document.getElementById('pv-tab-' + key);
    if (!button) return false;
    button.click();
    return true;
  }, tab);
  if (!found) {   // 위에서 집합을 맞췄으므로 여기 오면 도면이 재는 중에 바뀐 것이다
    console.error(`✗ ${tab} — 탭을 열지 못했다`);
    await browser.close();
    process.exit(1);
  }
  visited += 1;
  await page.waitForTimeout(420);

  for (const view of await sheetViews(tab)) {
    await pickView(tab, view);
    await page.waitForTimeout(420);
    await rerender();
    await page.waitForTimeout(420);
    const first = await measure();
    await rerender();
    await page.waitForTimeout(420);
    const second = await measure();
    const name = view ? `${tab}/${view}` : tab;

    for (let i = 0; i < first.length; i += 1) {
      sheets += 1;
      const a = first[i], b = second[i] || first[i];
      const over = a.right - SHEET_W;
      const unstable = a.w !== b.w;
      const mark = (over > 0 || unstable) ? '✗' : '·';
      if (over > 0 || unstable) offenders.push({ tab: name, ...a, second: b.w });
      console.log(`  ${mark} ${name.padEnd(20)} ${a.id.padEnd(18)} 프레임 ${a.w}×${a.h}`
        + `  내용 ${a.right}×${a.bottom}`
        + (over > 0 ? `  폭 초과 ${over}` : '')
        + (unstable ? `  재렌더 프레임 ${b.w}` : ''));
      if (over > 0) console.log(`      최우측: ${a.worst}`);
    }
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
if (!sheets) {
  console.error('\n✗ 시트를 한 장도 재지 못했다 — 다이얼로그가 안 열렸거나 svg.pv-sheet 가 없다.'
    + '\n  감춰진 채로는 getBBox 가 0 을 돌려주므로 「넘치지 않음」으로 보인다. 통과시키지 않는다.');
  await browser.close();
  process.exit(1);
}
console.log(`\n✓ 시트 ${sheets}장(탭 ${visited}개를 열어 확인)이 폭 ${SHEET_W} 안에 들고 두 번 렌더해도 같은 프레임이다`);
await browser.close();
