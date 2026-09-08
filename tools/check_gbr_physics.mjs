/* GBR-301 물리 화면이 **실제로 적분하는지** 브라우저로 확인한다.
 *
 * 파이썬 시험은 생성된 글자만 본다. 그런데 이 화면이 못 쓰게 되는 방식은 글자에
 * 남지 않는다 — 시간각이 안정 한계를 넘으면 사슬이 발산하고, 접촉이 한 방향이
 * 아니면 유리가 받침에 «붙어» 아무것도 못 묻는 화면이 된다. 둘 다 글자로는
 * 멀쩡하다. 그래서 여기서 재는 것은 **거동**이다.
 *
 *   ① 페이지 오류 0 · 적분기가 안정 한계 안일 것
 *   ② 종전 배치에서 유리가 **떨어질 것** — 선반이 유리 밖이라 받는 것이 없다
 *   ③ 채택 배치에서 유리가 **얹힐 것** — 그리고 콤포크를 놓을 것
 *   ④ 얹힌 처짐이 파이썬 유한요소(`gbr_dynamics.glass_on_shelf()`)와 맞을 것
 *      — 브라우저 사슬과 파이썬 Hermite 요소는 **서로 다른 구현**이다
 *   ⑤ 얹힌 응력이 저장 허용응력(정적피로) 밑일 것
 *   ⑥ 포크를 놓는 시각이 소하강 프로파일 안일 것
 *
 * 실행:  node tools/check_gbr_physics.mjs [문서.html]
 */
import { chromium } from 'playwright';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { browserPath } from './pw_browser.mjs';

const file = process.argv[2] || 'docs/drawings/pv-gbr-physics.html';
if (!existsSync(file)) {
  console.error(`✗ 문서가 없다: ${file}\n  PYTHONPATH=src python3 tools/build_gbr_physics.py 를 먼저 돌릴 것`);
  process.exit(2);
}

//: 서로 다른 두 이산화(브라우저 사슬 29 마디 · 파이썬 Hermite 140 요소)가 이만큼
//: 안에서 만나야 한다. 넘으면 둘 중 하나가 틀린 것이다. 사슬이 성기고 감쇠가
//: 2 % 라 잔진동이 조금 남는다 — 그 몫까지 보고 8 % 로 둔다.
const SAG_TOL = 0.08;
//: 정지까지 밟는 시간 (s).
const SETTLE_S = 10;

const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--allow-file-access-from-files'],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForFunction(() => window.PH && window.PH.numbers, null, { timeout: 20000 });

const fail = [];
const ok = (name, cond, detail) => {
  console.log(`${cond ? '  ok' : '  NG'}  ${name}${detail ? ' — ' + detail : ''}`);
  if (!cond) fail.push(name);
};

console.log(`GBR-301 물리 화면 검사 — ${file}`);

// ① 오류와 안정성
ok('페이지 오류 0', errors.length === 0, errors.slice(0, 2).join(' | '));
const stable = await page.evaluate(() => window.PH.stable());
ok('적분기가 안정 한계 안', stable === true);

// ②③④⑤⑥
const runs = await page.evaluate((s) => [0, 1].map((i) => window.PH.run(i, s)), SETTLE_S);
const num = await page.evaluate(() => window.PH.numbers);
const scene = await page.evaluate(() => window.PH.scene);

ok('종전 배치 — 포크가 빠지면 유리가 떨어진다', runs[0].fell === true,
   `처짐 ${runs[0].sag.toFixed(1)} mm · 슬롯 피치 ${scene.slotPitch}`);
ok('종전 배치 — 선반이 유리를 못 문다', runs[0].released === false);
ok('채택 배치 — 유리가 얹힌다', runs[1].fell === false && runs[1].released === true,
   `처짐 ${runs[1].sag.toFixed(2)} mm`);

const rel = Math.abs(runs[1].sag - num.shelfSag) / num.shelfSag;
ok('브라우저 사슬 ↔ 파이썬 유한요소', rel < SAG_TOL,
   `${runs[1].sag.toFixed(2)} vs ${num.shelfSag} mm (${(rel * 100).toFixed(1)} %)`);

ok('얹힌 응력이 저장 허용 밑', runs[1].stress < num.allowStore,
   `${runs[1].stress.toFixed(2)} < ${num.allowStore} MPa`);

ok('포크를 놓는 시각이 프로파일 안', runs[1].releaseT !== null && runs[1].releaseT < 1.0,
   `${runs[1].releaseT === null ? '—' : runs[1].releaseT.toFixed(3)} s`);

await browser.close();
if (fail.length) {
  console.error(`\n✗ ${fail.length}건 실패: ${fail.join(' · ')}`);
  process.exit(1);
}
console.log('\n✓ 물리 화면이 제 몫을 한다');
