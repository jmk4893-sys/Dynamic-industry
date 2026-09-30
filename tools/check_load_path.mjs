/* 하중 경로 검사 — 모든 부품이 바닥까지 이어지는가.
 *
 * 3D 장면은 "무엇이 있는가"는 보여 주지만 "무엇이 받치는가"는 저절로 보여 주지
 * 않는다. REV.25 까지 이 플랜트는 메시 1,765개 중 덩어리 77개(144메시)가 공중에
 * 떠 있었다 — 5단 랙 24메시가 바닥에서 600 mm 뜬 채 서 있는 식이었다. 앵커
 * 계획은 표제란에 글로 다 적혀 있었는데 그 앵커가 받칠 형상이 없었다.
 *
 * 방법은 단순하다. 메시 바운딩박스를 인접 허용치(30 mm)로 묶어 연결 성분을
 * 만들고, 바닥(y ≤ 50 mm)에 닿는 성분만 '접지'로 본다. 나머지는 하중을 어디로도
 * 넘기지 못하는 부재다.
 *
 * 예외는 `mounting.UNSUPPORTED_BY_DESIGN` 과 같아야 한다 — 공정 중 물체와
 * 레이저 투영선은 받칠 대상이 아니다. 그 밖의 것이 뜨면 실패한다.
 *
 * 실행 (저장소 루트에서):
 *     npm i playwright && npx playwright install chromium
 *     node tools/check_load_path.mjs docs/drawings/pv-preprocess-plant.html
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 받칠 대상이 아닌 것 — src/pv_preprocess/mounting.py 의 UNSUPPORTED_BY_DESIGN 과 같다. */
const EXEMPT = [
  '이송 중 태양광 패널',
  'VS-101 검출 정션박스 형상',
  'VS-101A/B-FUSED 고정면 스캔선',
  'CRN-901',              // 천장크레인 — 건물 철골이 받는다 (공급 범위 밖)
  'CMP-701 압축공기 주관',  // 통로 상부 DN20 — 건물 벽·기둥이 받는다 (건축 grid 확정 후)
];

const ADJACENCY_M = 0.03;   // 인접 판정 허용치
const FLOOR_M = 0.05;       // 이 높이 아래면 바닥에 닿은 것으로 본다

/** 씬에 있어야 하는 메시의 최소 개수 — 현행 2,288.
 *
 *  이 검사는 「접지 덩어리에 안 붙은 덩어리」를 세는 방식이라, 메시를 하나도
 *  못 찾으면 떠 있는 덩어리도 0 이고 「✓ 모든 부재가 바닥까지 하중 경로를
 *  갖는다」로 끝난다. 없는 것에 대해 참인 문장이다. 통과시키지 않는다. */
const MIN_MESHES = 1500;

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3400);

const result = await page.evaluate(([tol, floor]) => {
  const host = document.getElementById('jb-removal-operation');
  if (!host || !host.__pvScene) return { error: '3D 장면 훅(__pvScene)을 찾지 못했다' };
  const items = [];
  host.__pvScene.scene.traverse((o) => {
    if (!o.isMesh || !o.geometry) return;
    o.updateWorldMatrix(true, false);
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    const bb = o.geometry.boundingBox;
    let lo = [1e9, 1e9, 1e9];
    let hi = [-1e9, -1e9, -1e9];
    for (let i = 0; i < 8; i++) {
      const v = new bb.min.constructor(
        i & 1 ? bb.max.x : bb.min.x,
        i & 2 ? bb.max.y : bb.min.y,
        i & 4 ? bb.max.z : bb.min.z,
      ).applyMatrix4(o.matrixWorld);
      lo = [Math.min(lo[0], v.x), Math.min(lo[1], v.y), Math.min(lo[2], v.z)];
      hi = [Math.max(hi[0], v.x), Math.max(hi[1], v.y), Math.max(hi[2], v.z)];
    }
    items.push({ label: (o.userData && o.userData.label) || '', lo, hi });
  });

  const n = items.length;
  const parent = Array.from({ length: n }, (_, i) => i);
  const find = (a) => { while (parent[a] !== a) { parent[a] = parent[parent[a]]; a = parent[a]; } return a; };
  const union = (a, b) => { a = find(a); b = find(b); if (a !== b) parent[a] = b; };
  const touches = (A, B) => {
    for (let k = 0; k < 3; k++) if (A.lo[k] - tol > B.hi[k] || B.lo[k] - tol > A.hi[k]) return false;
    return true;
  };
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) if (touches(items[i], items[j])) union(i, j);
  }
  const grounded = new Set();
  for (let i = 0; i < n; i++) if (items[i].lo[1] <= floor) grounded.add(find(i));

  const groups = new Map();
  for (let i = 0; i < n; i++) {
    const r = find(i);
    if (!groups.has(r)) groups.set(r, []);
    groups.get(r).push(i);
  }
  const floating = [];
  for (const [root, idx] of groups) {
    if (grounded.has(root)) continue;
    const lo = [1e9, 1e9, 1e9];
    for (const i of idx) for (let k = 0; k < 3; k++) lo[k] = Math.min(lo[k], items[i].lo[k]);
    floating.push({
      meshes: idx.length,
      bottomY: +lo[1].toFixed(3),
      labels: idx.filter((i) => items[i].label).map((i) => items[i].label),
    });
  }
  floating.sort((a, b) => b.meshes - a.meshes);
  return { total: n, components: groups.size, grounded: grounded.size, floating };
}, [ADJACENCY_M, FLOOR_M]);

await browser.close();

if (result.error) {
  console.error('✗ ' + result.error);
  process.exit(2);
}

const offenders = result.floating.filter(
  (f) => !f.labels.length || !f.labels.every((l) => EXEMPT.some((e) => l.includes(e))),
);

if (result.total < MIN_MESHES) {
  console.error(`✗ 메시가 ${result.total} 개뿐이다 (하한 ${MIN_MESHES}) — 씬이 안 섰다.`
    + '\n  이 상태의 「떠 있는 덩어리 없음」은 없는 것에 대해 참인 문장이다.');
  process.exit(1);
}

console.log(`메시 ${result.total} · 연결 성분 ${result.components} · 접지 ${result.grounded}`);
/* **이 검사가 무엇을 단정하는지 숫자로 밝힌다.** 묻는 것은 「각 부재에서 바닥까지
   AABB 인접 사슬이 있는가」이고, 실측하면 2,288 중 2,274 가 접지 덩어리 **하나**
   에 들어 있다. 덩어리가 그만큼 크면 개별 부재에 대해 이 검사가 말해 주는 것은
   거의 없다 — 30 mm 안에서 무언가를 스치기만 하면 그 사슬에 들어간다. 진짜
   지지 여부는 `mounting` 의 부재별 검토가 본다. 이 값을 찍어 두어야 초록을
   과대해석하지 않는다. */
const biggest = result.total - result.floating.reduce((a, f) => a + f.meshes, 0);
console.log(`접지 덩어리가 메시 ${biggest} 를 품는다 (전체의 `
  + `${(biggest / result.total * 100).toFixed(1)} %) — AABB 인접 사슬 기준이다`);
console.log(`하중 경로 없음 ${result.floating.length}덩어리 (예외 허용 ${result.floating.length - offenders.length})`);
for (const f of result.floating) {
  const mark = offenders.includes(f) ? '✗' : '·';
  console.log(`  ${mark} ${String(f.meshes).padStart(3)}메시  y0=${f.bottomY.toFixed(3)}  ${f.labels.slice(0, 3).join(' / ') || '(라벨 없음)'}`);
}
if (errors.length) {
  console.error('✗ 페이지 오류: ' + errors.join(' | '));
  process.exit(2);
}
if (offenders.length) {
  console.error(`\n✗ 받칠 것이 없는 부재 ${offenders.length}덩어리 — 지지 부재를 세우거나, `
    + '근거를 적어 mounting.UNSUPPORTED_BY_DESIGN 과 이 파일의 EXEMPT 에 같이 넣을 것');
  process.exit(1);
}
console.log('\n✓ 모든 부재가 바닥까지 하중 경로를 갖는다 '
  + `(예외 ${EXEMPT.length}종 — 공정 중 물체·투영선·건물이 받는 크레인과 공압 주관)`);
