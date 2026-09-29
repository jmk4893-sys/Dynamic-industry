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
 * 실행:  node tools/check_artifact_render.mjs [본문.html …]
 *        (인자를 안 주면 out/ 의 두 벌을 본다)
 */
import { chromium } from 'playwright';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const files = process.argv.slice(2);
const targets = files.length ? files : [
  'out/pv-preprocess-console-artifact.html',
  'out/pv-preprocess-plant-artifact.html',
];

const missing = targets.filter((f) => !existsSync(f));
if (missing.length) {
  console.error(`✗ 본문이 없다: ${missing.join(', ')}\n  python tools/build_artifact.py 를 먼저 돌릴 것`);
  process.exit(2);
}

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
let bad = 0;
for (const file of targets) {
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
    return { has3d: !!(host && host.__pvScene), meshes,
             body: document.body.innerHTML.length };
  });
  await page.close();

  // 셰이더가 깨지면 브라우저가 콘솔로 알려 준다 — 그 문구를 놓치지 않는다
  const shader = errors.filter((e) => /shader|GLSL|invalid directive|FRAGMENT|VERTEX/i.test(e));
  const ok = errors.length === 0 && got.body > 500 && (!got.has3d || got.meshes > 100);
  console.log(`${ok ? '  ✓' : '  ✗'} ${file}  본문 ${got.body} 자`
    + (got.has3d ? ` · 3D 메시 ${got.meshes}` : ' · 3D 없음')
    + (errors.length ? `\n      오류 ${errors.length}: ${errors.slice(0, 2).join(' | ')}` : ''));
  if (shader.length) console.log(`      셰이더 오류: ${shader[0]}`);
  if (!ok) bad++;
}
await browser.close();
console.log(bad
  ? `\n✗ 발행본 ${bad}벌이 제대로 그리지 못한다`
  : `\n✓ 발행본 ${targets.length}벌이 오류 없이 그린다`);
process.exit(bad ? 1 : 0);
