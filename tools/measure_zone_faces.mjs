/* 존별 통로쪽 실측면 — `casing.MEASURED_FACE_MM` 을 3D 에서 다시 잰다.
 *
 * 존 표의 통로쪽 깊이는 **공칭값**이다. 껍질을 그 값에 세우면 부재를 파고든다
 * (`casing.MEASURED_FACE_MM` 주석 참조 — 첫 판에서 166 곳이 걸렸다). 그래서
 * 면을 3D 에서 실측하는데, 그 실측이 **손으로 적은 값**이라 장비 밴드가
 * 움직이면 조용히 낡는다. 반전축을 장변 방향으로 돌리며 밴드가 7,100 → 8,550
 * 이 되자 세 존의 침범이 저절로 0 이 된 것처럼 보였다 — 밴드가 넓어져서가
 * 아니라 옛 프레임에서 잰 값이 그대로 남아 있어서였다.
 *
 * 그래서 재는 일을 도구로 옮긴다. 규칙은 주석에 적힌 그대로다:
 *   · 셀 그룹(`userData.cell`)에 속한 메시만
 *   · 껍질(`case:…`)과 형상이 아닌 것(존 포락선·참조·투영선)은 빼고
 *   · 시간을 훑어 **움직이는 것까지 포함한** 최대 월드 z
 *   · 플랜트 Y = 월드 z + 장비 밴드 절반
 *
 * 실행 (저장소 루트에서):
 *     PYTHONPATH=src python tools/build_casing.py     # 밴드 절반을 낸다
 *     node tools/measure_zone_faces.mjs
 */
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const PLANES = JSON.parse(readFileSync('out/casing-planes.json', 'utf-8'));
const BAND_HALF = PLANES._limits.band;          // 월드 z = 플랜트 Y − 이 값
const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 형상이 아닌 것 — 존 포락선·참조 외형·레이저 투영선은 껍질이 피할 대상이 아니다. */
const NOT_SHAPE = ['존 포락선', '참조', '투영', '스캔선', '(참조'];

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3400);

const out = await page.evaluate(([t0, t1, dt, notShape]) => {
  const host = document.getElementById('jb-removal-operation');
  if (!host || !host.__pvScene) return { error: '3D 장면 훅(__pvScene)을 찾지 못했다' };
  if (!host.__pvInfeedTest) return { error: '영상 훅(__pvInfeedTest)을 찾지 못했다' };
  const S = host.__pvScene, anim = host.__pvInfeedTest;

  const items = [];
  const walk = (node, cell) => {
    const here = (node.userData && node.userData.cell) || cell;
    if (node.isMesh && node.geometry && here) {
      if (!node.geometry.boundingBox) node.geometry.computeBoundingBox();
      // 껍질은 **이름**으로 가른다 — 판에 라벨이 붙어 있어도 껍질은 껍질이다.
      const raw = String(node.name || '');
      const nm = String((node.userData && node.userData.label) || raw || '');
      if (!raw.startsWith('case:') && !notShape.some((w) => nm.includes(w))) {
        items.push({ mesh: node, cell: here, name: nm });
      }
    }
    for (const c of node.children) walk(c, here);
  };
  walk(S.scene, null);

  const best = {};
  const maxZ = (m) => {
    const bb = m.geometry.boundingBox;
    m.updateWorldMatrix(true, false);
    let z = -1e9;
    for (let i = 0; i < 8; i++) {
      const q = new S.Vector3(i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y,
                              i & 4 ? bb.max.z : bb.min.z).applyMatrix4(m.matrixWorld);
      if (q.z > z) z = q.z;
    }
    return z;
  };
  for (let t = t0; t <= t1 + 1e-9; t += dt) {
    anim.setTime(t);
    S.scene.updateMatrixWorld(true);
    for (const it of items) {
      const z = maxZ(it.mesh);
      const k = it.cell;
      let tag = it.name;
      if (!tag) {
        const bb = it.mesh.geometry.boundingBox;
        const c = new S.Vector3().copy(bb.max).add(bb.min).multiplyScalar(.5).applyMatrix4(it.mesh.matrixWorld);
        const d = new S.Vector3().copy(bb.max).sub(bb.min);
        const f = (v) => (Math.round(v * 100) / 100).toFixed(2);
        tag = `(무명) @${f(c.x)},${f(c.y)},${f(c.z)} ${f(d.x)}×${f(d.y)}×${f(d.z)} <${it.mesh.parent && it.mesh.parent.name || ''}>`;
      }
      (best[k] = best[k] || []).push({ z, name: tag, t });
      if (best[k].length > 400) { best[k].sort((a, b) => b.z - a.z); best[k].length = 12; }
    }
  }
  return { best, count: items.length };
}, [0, 130, 0.5, NOT_SHAPE]);

await browser.close();
if (out.error) { console.error('✗ ' + out.error); process.exit(1); }
if (errors.length) console.error('페이지 오류: ' + errors[0]);

console.log(`형상 메시 ${out.count} · 밴드 절반 ${(BAND_HALF * 1000).toFixed(0)} mm\n`);
const top = {};
for (const [cell, list] of Object.entries(out.best)) {
  list.sort((a, b) => b.z - a.z);
  const seen = new Set(), keep = [];
  for (const v of list) { if (seen.has(v.name)) continue; seen.add(v.name); keep.push(v); if (keep.length >= 5) break; }
  top[cell] = keep;
}
const rows = Object.entries(top).sort((a, b) => b[1][0].z - a[1][0].z);
for (const [cell, keep] of rows) {
  console.log(`\n[${cell}]`);
  for (const v of keep) {
    console.log(`  Y ${String(Math.round((v.z + BAND_HALF) * 1000)).padStart(6)}  z ${v.z.toFixed(3).padStart(7)}  t ${String(v.t).padStart(5)}  ${v.name}`);
  }
}
console.log('\ncasing.MEASURED_FACE_MM 에 적을 값:');
for (const [cell, keep] of rows) {
  console.log(`    "${cell}": ${Math.round((keep[0].z + BAND_HALF) * 1000)},   # ${keep[0].name}`);
}
