/* JBR-201 물리 시뮬레이션을 영상으로 찍는다.
 *
 * 화면 녹화가 아니다. 페이지를 열어 `PH.advance(1/fps)` 로 **고정 시간각**을 밟고,
 * 프레임마다 캔버스를 PNG 로 받아 ffmpeg 에 넣는다. 그래서
 *
 *   · 몇 번을 찍어도 같은 영상이 나온다 (실시간 재생 속도에 안 매인다)
 *   · 물리 적분이 렌더 프레임률과 분리된다 (한 프레임에 4 서브스텝)
 *   · 느린 기계에서도 프레임이 안 빠진다
 *
 * ffmpeg 은 Playwright 가 들고 오는 것을 쓴다 — 컨테이너에 따로 깔린 것이 없다.
 * 그 빌드는 축소판이다 — 데먁서는 `image2pipe`, 디코더는 **MJPEG 뿐**(PNG 없음),
 * 인코더는 VP8 뿐이다. 그래서 프레임을 JPEG 으로 받아 **표준입력으로 흘려 넣어**
 * WebM 으로 찍는다. 파일로 떨구지 않으므로 디스크도 안 쓴다.
 *
 * 실행:  node tools/render_jbr_video.mjs [출력.webm]
 */
import { chromium } from 'playwright';
import { browserPath } from './pw_browser.mjs';
import { existsSync, mkdirSync, readdirSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PAGE = join(ROOT, 'docs', 'drawings', 'pv-jbr-physics.html');
const OUT = resolve(process.argv[2] || join(ROOT, 'out', 'jbr-physics.webm'));
const FPS = 60;

function ffmpeg() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH || '/opt/pw-browsers';
  if (existsSync(root)) {
    for (const d of readdirSync(root).filter((n) => n.startsWith('ffmpeg')).sort().reverse()) {
      for (const name of ['ffmpeg-linux', 'ffmpeg']) {
        const p = join(root, d, name);
        if (existsSync(p)) return p;
      }
    }
  }
  return 'ffmpeg';
}

/* 각 구간을 어느 시점에서 보여 줄지 — 물리가 잘 보이는 쪽으로 고른다. */
function viewAt(t, slotEnd) {
  if (t < 1.0) return 'iso';
  if (t >= slotEnd + 2.4) return 'front';     // 플랩이 열려 수거함으로 떨어지는 구간
  return 'iso';
}

const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--force-device-scale-factor=1'],
});
const page = await browser.newPage({ viewport: { width: 1760, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 300)); });
await page.goto('file://' + PAGE, { waitUntil: 'load' });
await page.waitForFunction(() => window.PH !== undefined);

/* 캔버스를 고유 해상도(1280×720)로 펴 준다. 기본 레이아웃은 폭 1400 에 사이드바를
   빼고 나면 972 px 라, 그대로 찍으면 영상이 그만큼 작아지고 글자가 뭉갠다. */
await page.addStyleTag({ content:
  '.page{max-width:none!important} .layout{grid-template-columns:1280px 360px!important}' +
  '#c{width:1280px!important;height:720px!important}' });

/* 자유낙하 닫힌 해 대조 — 엔진이 맞게 푸는지 먼저 확인한다. */
const chk = await page.evaluate(() => window.PH.check());
console.log(`  자유낙하 대조: 모의 ${chk.simulated.toFixed(4)} s · 해석 ${chk.exact.toFixed(4)} s · 오차 ${(chk.error * 100).toFixed(2)} %`);
if (!(chk.error < 0.02)) {
  console.error('✗ 물리엔진이 닫힌 해와 2 % 안에서 안 맞는다 — 영상을 찍지 않는다');
  await browser.close();
  process.exit(1);
}

const total = await page.evaluate(() => window.PH.total);
const slotEnd = await page.evaluate(() => SCENE.motion.slot * SCENE.boxes.length);
const count = Math.ceil(total * FPS);
console.log(`  ${total.toFixed(1)} s · ${count} 프레임 · ${FPS} fps`);

mkdirSync(dirname(OUT), { recursive: true });
const ff = spawn(ffmpeg(), [
  '-y', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', String(FPS), '-i', 'pipe:0',
  '-c:v', 'libvpx', '-b:v', '5M', '-deadline', 'good', '-cpu-used', '2',
  '-pix_fmt', 'yuv420p', OUT], { stdio: ['pipe', 'ignore', 'pipe'] });
let ffErr = '', ffCode = null;
ff.stderr.on('data', (d) => { ffErr += d; });
ff.stdin.on('error', () => {});          /* ffmpeg 이 먼저 죽으면 EPIPE 가 난다 */
const done = new Promise((res) => {
  ff.on('close', (code) => { ffCode = code; res(); });
  ff.on('error', (e) => { ffCode = -1; ffErr += String(e); res(); });
});
const bail = () => {
  console.error('✗ ffmpeg 실패 (code ' + ffCode + '):\n' + ffErr.split('\n').slice(-12).join('\n'));
  process.exit(1);
};
const write = (buf) => new Promise((res) => {
  if (ffCode !== null) return res();
  ff.stdin.write(buf) ? res() : ff.stdin.once('drain', res);
});

await page.evaluate(() => { window.PH.pause(); window.PH.reset(); });
const canvas = page.locator('#c');
let lastView = null;
for (let i = 0; i < count; i++) {
  const t = i / FPS;
  const v = viewAt(t, slotEnd);
  if (v !== lastView) { await page.evaluate((vv) => window.PH.setView(vv), v); lastView = v; }
  await page.evaluate((fps) => { window.PH.advance(1 / fps); window.PH.draw(); }, FPS);
  await write(await canvas.screenshot({ type: 'jpeg', quality: 92 }));
  if (ffCode !== null) { await browser.close(); bail(); }
  if (i % 120 === 0) process.stdout.write(`\r  프레임 ${i}/${count}`);
}
process.stdout.write(`\r  프레임 ${count}/${count}\n`);

/* 마지막 상태 — 박스가 실제로 수거함 안에 들어갔는가. */
const finalState = await page.evaluate(() => ({
  bodies: window.PH.bodies(), st: window.PH.state(), bin: SCENE.bin,
}));
await browser.close();
ff.stdin.end();
await done;
if (ffCode !== 0) bail();

if (errors.length) {
  console.error('✗ 페이지 오류:', errors.slice(0, 3));
  process.exit(1);
}

const B = finalState.bin;
const inside = finalState.bodies.filter((b) => {
  const [x, y, z] = b.p;
  return Math.abs(x - B.x) <= B.inner[0] / 2 + 0.05
      && Math.abs(z - B.z) <= B.inner[1] / 2 + 0.05
      && y < B.floorY + 0.35;
});
console.log(`  수거함 안 ${inside.length}/${finalState.bodies.length} · 안착 ${finalState.bodies.filter((b) => b.sleeping).length}`);
console.log(`✓ ${OUT}`);
if (inside.length < finalState.bodies.length) {
  console.error('✗ 박스가 수거함 밖으로 나갔다 — 호퍼·수거함 치수를 다시 본다');
  process.exit(2);
}
