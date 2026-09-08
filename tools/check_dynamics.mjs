/* 영상의 적분기가 파이썬과 같은 답을 내는가.
 *
 * 두 벌을 따로 두면 반드시 갈라진다 — 그리고 갈라진 쪽이 **영상**이면 아무도
 * 모른다. 그림은 언제나 그럴듯하게 움직이기 때문이다. 그래서 페이지를 실제로
 * 열어 브라우저 안의 적분기를 돌리고, `dynamics.summary()` 가 페이지에 박아 둔
 * 값과 대조한다.
 *
 * 여기서 보는 것 셋:
 *   · **두 적분기가 같은 답을 내는가** (허용오차 안에서)
 *   · **형상이 실제로 물리에 물려 있는가** — 승강 그룹과 링 그룹을 못 찾으면
 *     페이지는 조용히 키프레임으로 돌아간다. 그 상태를 통과로 두지 않는다.
 *   · **가속을 올리면 미끄러지는가** — 그것이 이 영상의 존재 이유다.
 *
 * 실행 (저장소 루트에서):
 *     node tools/check_dynamics.mjs [도면.html]
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-infeed-dyn.html';

/** 항목마다 허용오차 — 적분간격이 달라 자릿수 끝은 안 맞는다. */
const TOL = {
  liftPeakN: 0.001, liftPeakNm: 0.001, flipPeakNm: 0.001, flipCapacityNm: 0.001,
  peelDemandN: 0.001, peelStefanN: 0.001,
  impactPeakN: 0.01, impactDeflectionMm: 0.01,
};

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3600);

const out = await page.evaluate(async () => {
  const T = window.__pvDynTest;
  if (!T) return { error: '동역학 훅(__pvDynTest)이 없다 — 엔진이 안 붙었다' };
  const got = T.run();
  // 미끄럼이 실제로 일어나는가 — 가속을 크게 올려 본다.
  // 택트를 1.5 배로 압축하면 가속이 2.25 배가 된다 — 거기서 미끄러져야 한다.
  T.setTakt(1.5);
  await new Promise((r) => setTimeout(r, 300));
  const capped = T.model.preloadN * T.model.mu * T.model.ringR;
  const wanted = T.run().flipPeakNm;
  T.setTakt(1.0);
  return { got, expect: T.model.expect, driven: T.driven, capped, wanted };
});

await browser.close();

if (out.error) { console.error('✗ ' + out.error); process.exit(1); }
if (errors.length) {
  console.error(`✗ 페이지 오류 ${errors.length}건 — 첫 줄: ${errors[0]}`);
  process.exit(1);
}

let bad = 0;
console.log('두 적분기 대조 (파이썬 ↔ 브라우저)\n');
console.log('  항목                     파이썬        브라우저       차이');
for (const [key, tol] of Object.entries(TOL)) {
  const py = out.expect[key], js = out.got[key];
  if (py === undefined || js === undefined) {
    console.log(`  ✗ ${key.padEnd(22)} ${py === undefined ? '없음' : '—'} / ${js === undefined ? '없음' : '—'}`);
    bad++;
    continue;
  }
  const rel = py === 0 ? Math.abs(js) : Math.abs(js - py) / Math.abs(py);
  const ok = rel <= tol;
  if (!ok) bad++;
  console.log(`  ${ok ? '·' : '✗'} ${key.padEnd(22)} ${py.toFixed(2).padStart(12)}`
    + ` ${js.toFixed(2).padStart(12)}  ${(rel * 100).toFixed(3)} %`
    + (ok ? '' : `   허용 ${(tol * 100).toFixed(1)} %`));
}

if (!out.driven) {
  console.error('\n✗ 형상이 물리에 안 물렸다 — 승강·링 그룹을 못 찾았다.'
    + '\n  이 상태에서 페이지는 조용히 키프레임으로 돌아간다. 통과시키면 안 된다.');
  bad++;
} else {
  console.log('\n· 형상이 물리에 물렸다 — 승강 그룹 position.y · 링 그룹 rotation.z');
}

if (out.wanted <= out.capped) {
  console.error(`\n✗ 택트 1.5× 압축(가속 2.25×)에서도 안 미끄러진다 (지령 ${out.wanted.toFixed(1)} ≤ 한계 ${out.capped.toFixed(1)} N·m).`
    + '\n  포화가 안 걸리면 이 영상은 키프레임과 다를 게 없다.');
  bad++;
} else {
  console.log(`· 택트 1.5× 압축(가속 2.25×)에서 미끄러진다 — 지령 ${out.wanted.toFixed(1)} > 전달 한계 ${out.capped.toFixed(1)} N·m`);
}

if (bad) {
  console.error(`\n✗ ${bad}건 어긋난다 — 영상과 해석이 갈라져 있다`);
  process.exit(1);
}
console.log('\n✓ 영상의 적분기가 해석과 같은 답을 낸다');
