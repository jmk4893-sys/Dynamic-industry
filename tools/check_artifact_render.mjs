/* 발행본이 **실제로 그리는지** 브라우저로 확인한다.
 *
 * 원본만 렌더해 보고 발행본은 확인하지 않다가 한 번 크게 당했다 — 변환기의
 * `<meta[^>]*>` 가 three.js 셰이더의 `#include <metalnessmap_fragment>` 를
 * `<meta…>` 로 잡아 지웠고, 표준 재질이 컴파일되지 않아 발행본에서 3D 가
 * 통째로 안 나왔다. 원본은 멀쩡했으므로 원본 검사로는 절대 안 잡힌다.
 *
 * 그래서 여기서 재는 것은 변환 결과물이다 — 페이지 오류 0, 셰이더 컴파일
 * 오류 0, 3D 메시 수가 원본과 같을 것.
 *
 * **그 마지막 항목이 오래 약속만이었다.** 코드는 `got.meshes > 100` 만 보고
 * 있었고 원본 메시 수를 읽는 곳이 아예 없었다 — 변환이 메시를 900 개 떨궈도
 * 통과하는 상태였다. 게다가 `!got.has3d ||` 때문에 씬 훅을 못 찾으면 메시
 * 요구를 아예 건너뛰고 「3D 없음」으로 찍고 통과했다. 이 검사가 존재하는
 * 이유가 바로 「발행본에서 3D 가 통째로 안 나온 사고」인데, 그 사고의 모양을
 * 통과로 두고 있었다. 이제 원본을 같이 열어 메시 수를 맞춘다.
 *
 * 실행:  node tools/check_artifact_render.mjs [본문.html …]
 *        (인자를 안 주면 out/ 의 두 벌을 본다)
 */
import { chromium } from 'playwright';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { browserPath } from './pw_browser.mjs';

const files = process.argv.slice(2);
const targets = files.length ? files : [
  'out/pv-preprocess-console-artifact.html',
  'out/pv-preprocess-plant-artifact.html',
];

/** 발행본 → 원본. `tools/build_artifact.py` 의 TARGETS 와 같은 규약이다.
 *  `out/<이름>-artifact.html` 의 원본은 `docs/drawings/<이름>.html` 이고,
 *  콘솔만 `docs/consoles/` 에 있다. */
const sourceOf = (published) => {
  const m = /(?:^|\/)([^/]+)-artifact\.html$/.exec(published);
  if (!m) return null;
  const stem = m[1];
  for (const dir of ['docs/drawings', 'docs/consoles']) {
    const guess = `${dir}/${stem}.html`;
    if (existsSync(guess)) return guess;
  }
  return null;
};

/** 페이지를 열어 메시 수와 본문 길이를 잰다. */
const inspect = async (file) => {
  const page = await browser.newPage({ viewport: { width: 1400, height: 800 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  page.on('requestfailed', (r) => errors.push('요청 실패 ' + r.url().slice(0, 120)));
  await page.goto('file://' + resolve(file), { waitUntil: 'load' });
  await page.waitForTimeout(4500);
  const got = await page.evaluate(() => {
    const host = document.getElementById('jb-removal-operation');
    let meshes = 0;
    if (host && host.__pvScene) host.__pvScene.scene.traverse((o) => { if (o.isMesh) meshes++; });
    return { has3d: !!(host && host.__pvScene), meshes, body: document.body.innerHTML.length };
  });
  await page.close();
  return { ...got, errors };
};

const missing = targets.filter((f) => !existsSync(f));
if (missing.length) {
  console.error(`✗ 본문이 없다: ${missing.join(', ')}\n  python tools/build_artifact.py 를 먼저 돌릴 것`);
  process.exit(2);
}

const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
let bad = 0;
for (const file of targets) {
  const got = await inspect(file);
  const errors = got.errors;

  // 셰이더가 깨지면 브라우저가 콘솔로 알려 준다 — 그 문구를 놓치지 않는다
  const shader = errors.filter((e) => /shader|GLSL|invalid directive|FRAGMENT|VERTEX/i.test(e));

  /* 원본을 같이 열어 메시 수를 맞춘다. 원본에 3D 가 있는데 발행본에 없으면
     그것이 바로 우리가 당한 사고이므로, 「3D 없음」을 통과로 두지 않는다. */
  const src = sourceOf(file);
  const ref = src ? await inspect(src) : null;
  let meshNote = '';
  let meshOk = true;
  if (!ref) {
    meshNote = '  · 원본을 못 찾았다 — 메시 수를 대조하지 못했다';
    meshOk = false;      // 약속한 대조를 못 했으면 통과가 아니다
  } else if (ref.has3d && !got.has3d) {
    meshNote = `  · ✗ 원본에는 3D 가 있는데 발행본에는 없다 (원본 메시 ${ref.meshes})`;
    meshOk = false;
  } else if (ref.has3d && got.meshes !== ref.meshes) {
    meshNote = `  · ✗ 메시 수가 원본과 다르다 — 원본 ${ref.meshes} vs 발행본 ${got.meshes}`;
    meshOk = false;
  } else if (ref.has3d) {
    meshNote = `  · 메시 ${got.meshes} = 원본과 같다`;
  } else {
    meshNote = '  · 원본에 3D 가 없다 (대조 대상 아님)';
  }

  const ok = errors.length === 0 && got.body > 500 && meshOk;
  console.log(`${ok ? '  ✓' : '  ✗'} ${file}  본문 ${got.body} 자`
    + (got.has3d ? ` · 3D 메시 ${got.meshes}` : ' · 3D 없음')
    + (errors.length ? `\n      오류 ${errors.length}: ${errors.slice(0, 2).join(' | ')}` : ''));
  console.log('    ' + meshNote.trim());
  if (shader.length) console.log(`      셰이더 오류: ${shader[0]}`);
  if (!ok) bad++;
}
await browser.close();
console.log(bad
  ? `\n✗ 발행본 ${bad}벌이 제대로 그리지 못한다`
  : `\n✓ 발행본 ${targets.length}벌이 오류 없이 그린다`);
process.exit(bad ? 1 : 0);
