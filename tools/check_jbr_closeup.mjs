/* 클로즈업 세 장면이 **실제로 그려지는지** 브라우저로 확인한다.
 *
 * 이 화면은 캔버스에 손으로 좌표를 찍는다. 생성기가 통과해도 좌표가 프레임
 * 밖이면 빈 canvas 가 남고, 파이썬 시험은 그것을 못 본다 — 실제로 한 번,
 * `MO.scissor` 가 `M.scissor` 에 있어 세 장면이 전부 백지로 나왔는데도
 * 831 개 시험이 전부 통과했다.
 *
 * 그래서 여기서 재는 것은 픽셀이다 — 페이지 오류 0, 탭마다 두 캔버스가
 * 모두 최소한의 잉크를 갖고, 판독값·제목이 비어 있지 않을 것.
 *
 * 실행:  node tools/check_jbr_closeup.mjs [문서.html]
 *        (인자를 안 주면 docs/drawings/pv-jbr-closeup.html 을 본다)
 */
import { chromium } from 'playwright';
import { existsSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

/* 환경에 미리 깔린 크로미움을 쓴다. playwright 가 기대하는 빌드 번호와 설치본이
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

const file = process.argv[2] || 'docs/drawings/pv-jbr-closeup.html';
if (!existsSync(file)) {
  console.error(`✗ 문서가 없다: ${file}\n  PYTHONPATH=src python tools/build_jbr_closeup.py 를 먼저 돌릴 것`);
  process.exit(2);
}

//: 탭마다 재 볼 시각 (로컬 s). null 이면 그 탭의 기본 시각 그대로.
const SHOTS = [
  ['near', null], ['near', 24.0],
  ['cable', null], ['cable', 17.2], ['cable', 20.5],
  ['bin', null], ['bin', 36.9], ['bin', 37.9],
];
//: 캔버스가 비지 않았다고 볼 최소 잉크 비율 (%).
const MIN_INK = 1.0;

const browser = await chromium.launch({ executablePath: browserPath() });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(500);

let bad = 0;
for (const [tab, at] of SHOTS) {
  await page.click(`.tabs [data-tab="${tab}"]`);
  if (at !== null) {
    await page.evaluate((v) => {
      const s = document.getElementById('scrub');
      s.value = v; s.dispatchEvent(new Event('input'));
    }, at);
  }
  await page.waitForTimeout(250);
  const got = await page.evaluate(() => {
    const ink = (id) => {
      const c = document.getElementById(id);
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      let n = 0;
      for (let i = 3; i < d.length; i += 4) if (d[i] > 8) n += 1;
      return (100 * n) / (d.length / 4);
    };
    return {
      t: document.getElementById('tlocal').textContent,
      wide: document.getElementById('wideName').textContent,
      near: document.getElementById('nearName').textContent,
      note: document.getElementById('tabNote').textContent.length,
      rows: document.querySelectorAll('#readout .r').length,
      ink: [ink('wide'), ink('near')],
    };
  });
  const why = [];
  if (!got.wide || !got.near) why.push('제목이 비었다');
  if (got.note < 40) why.push('설명이 비었다');
  if (got.rows < 8) why.push(`판독값 ${got.rows} 줄`);
  got.ink.forEach((v, i) => {
    if (v < MIN_INK) why.push(`${i === 0 ? '전경' : '근접'} 캔버스가 비었다 (${v.toFixed(2)} %)`);
  });
  const mark = why.length ? '✗' : '✓';
  if (why.length) bad += 1;
  console.log(`${mark} ${tab.padEnd(6)} ${(at === null ? '기본' : at.toFixed(1)).padStart(5)} s  `
    + `잉크 ${got.ink.map((v) => v.toFixed(1) + '%').join(' / ')}  ${got.t}`
    + (why.length ? `  — ${why.join(', ')}` : ''));
}
await browser.close();

if (errors.length) {
  bad += 1;
  console.error('✗ 페이지 오류:\n  ' + [...new Set(errors)].join('\n  '));
}
console.log(bad ? `✗ ${bad} 건` : '✓ 세 장면 여섯 캔버스가 모두 그려진다');
process.exit(bad ? 1 : 0);
