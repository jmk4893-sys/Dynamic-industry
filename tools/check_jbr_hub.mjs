/* 도면 모음이 **정말로 한 벌씩만 보이는지** 브라우저로 확인한다.
 *
 * 세 문서를 한 장에 담는 화면이라 파이썬 시험이 못 보는 실패 방식이 있다.
 * 실제로 한 번 당했다 — `[hidden]{display:none!important}` 를 저장소 파일에
 * 안 넣었더니 `iframe{display:block}` 이 이겨서 세 도면이 나란히 늘어섰는데,
 * 생성기도 시험도 전부 통과했다. 발행본은 호스트 골격이 그 규칙을 주므로
 * 저장소 파일에서만 나는 어긋남이었다.
 *
 * 그래서 여기서 재는 것은 화면이다 — 탭마다 액자가 하나만 보이고, 그 액자 안이
 * 제 문서(제목·본문)로 열리고, 3D 가 있어야 할 곳에 캔버스가 있을 것.
 *
 * 실행:  node tools/check_jbr_hub.mjs [문서.html]
 *        (인자를 안 주면 docs/drawings/pv-jbr-hub.html 을 본다)
 */
import { chromium } from 'playwright';
import { existsSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

/* 환경에 미리 깔린 크로미움을 쓴다 — playwright 가 기대하는 빌드 번호와 설치본이
 * 어긋나 있는 컨테이너가 있어서, 있으면 그것을 직접 가리킨다. */
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

const file = process.argv[2] || 'docs/drawings/pv-jbr-hub.html';
if (!existsSync(file)) {
  console.error(`✗ 문서가 없다: ${file}\n  PYTHONPATH=src python tools/build_jbr_hub.py 를 먼저 돌릴 것`);
  process.exit(2);
}

//: 탭 키 → [기대하는 문서 제목의 일부, 캔버스가 있어야 하는가]
const WANT = {
  scene: ['JBR-201 정션박스 제거장치', true],
  detail: ['상세도', false],
  closeup: ['박리·절단·배출', true],
};

const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(1200);

let bad = 0;
for (const key of Object.keys(WANT)) {
  await page.click(`.tab[data-key="${key}"]`);
  await page.waitForTimeout(key === 'scene' ? 5000 : 2000);
  const got = await page.evaluate(() => {
    const frames = [...document.querySelectorAll('iframe')];
    const open = frames.filter((f) => !f.hidden);
    const d = open[0] && open[0].contentDocument;
    return {
      shown: open.length,
      built: frames.length,
      id: open[0] ? open[0].id : '',
      title: d ? d.title : '(문서에 닿지 못했다)',
      chars: d ? d.body.innerText.trim().length : 0,
      canvas: d ? d.querySelectorAll('canvas').length : 0,
      hint: document.getElementById('hint').textContent.trim().length,
      span: document.getElementById('spanLabel').textContent.trim(),
      selected: [...document.querySelectorAll('.tab[aria-selected="true"]')].length,
    };
  });
  const [wantTitle, wantCanvas] = WANT[key];
  const why = [];
  if (got.shown !== 1) why.push(`액자가 ${got.shown} 개 보인다`);
  if (got.id !== 'panel-' + key) why.push(`보이는 것이 ${got.id || '없다'}`);
  if (!got.title.includes(wantTitle)) why.push(`문서 제목이 «${got.title}»`);
  if (got.chars < 400) why.push(`본문이 ${got.chars} 자`);
  if (wantCanvas && got.canvas < 1) why.push('캔버스가 없다');
  if (got.hint < 20) why.push('설명이 비었다');
  if (!/^[\d.]+–[\d.]+ s$/.test(got.span)) why.push(`구간 표시가 «${got.span}»`);
  if (got.selected !== 1) why.push(`탭이 ${got.selected} 개 눌려 있다`);
  if (why.length) bad += 1;
  console.log(`${why.length ? '✗' : '✓'} ${key.padEnd(8)} 액자 ${got.shown}/${got.built} · `
    + `«${got.title}» ${got.chars} 자 · 캔버스 ${got.canvas} · ${got.span}`
    + (why.length ? `  — ${why.join(', ')}` : ''));
}
await browser.close();

if (errors.length) {
  bad += 1;
  console.error('✗ 페이지 오류:\n  ' + [...new Set(errors)].join('\n  '));
}
console.log(bad ? `✗ ${bad} 건` : '✓ 세 도면이 한 벌씩만 열린다');
process.exit(bad ? 1 : 0);
