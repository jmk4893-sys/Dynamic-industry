/* 투입 베이 두 칸이 라인 가로(z)에서 서로를 침범하지 않는지 3D 에서 실측한다.
 *
 * **기하 검사 넷이 이것을 못 본다.** `check_cell_grid` 는 존의 X 범위만,
 * `check_clearance` 는 공정 중인 물건이 설비를 뚫는지만, `check_load_path` 는
 * 바닥까지 힘이 가는지만, `check_casing_fit` 은 껍질과 통로만 본다. 베이 A 의
 * 부재가 베이 B 안으로 들어가도 넷 다 초록이다.
 *
 * 반전축을 장변 방향으로 돌리면 카세트의 **넓은 쪽**(기둥 3,380)이 라인 폭에
 * 눕는다. 그래서 베이 피치를 같이 다시 유도해야 하는데(3,380 + 중앙벽 250 =
 * 3,630 → 중심 ∓1,815), 씬 그래프의 베이 내용만 돌리고 피치를 그대로 두면
 * 파이썬도 기하 검사도 통과하는 채로 두 카세트가 **서로를 파고든다.**
 *
 * **처음에는 z 축 투영으로 쟀는데 그것이 틀렸다.** 두 베이의 z 범위가 겹치는
 * 것과 부재가 실제로 부딪히는 것은 다르다 — x 나 y 가 다르면 겹치지 않는다.
 * 그 잣대로 다른 브랜치를 재니 −90 mm 가 나왔지만, 그쪽은 **안쪽 기둥을 두
 * 베이가 공유하는** 설계라 부재가 z 0 을 넘는 것이 정상이었고 `check_clearance`
 * 는 그 도면에서 확인 필요 0 을 냈다. 잣대가 설계 유형을 가리고 있었다.
 *
 * 그래서 **세 축을 다 본다.** 베이 A 의 부재와 베이 B 의 부재가 실제로 겹치는
 * 상자를 갖는지 짝지어 확인하고, z 투영 간격은 **참고로만** 찍는다(공유 기둥
 * 설계에서는 음수가 정상이다).
 *
 * 재는 방법은 하나뿐이다 — **공정시계를 훑는다.** 포획빔은 신축하고 승강
 * 캐리지·조는 움직이므로 정지 프레임 한 장으로는 최대 범위가 안 나온다.
 *
 * 실행 (저장소 루트에서):
 *     node tools/check_bay_clearance.mjs [도면.html]
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 베이에 속한 것으로 세는 조립체 — 이름 앞자리로 가른다. */
const BAY_PARTS = '(BFC-101|BLR-101|SEP-101|CD-101)([AB])';

/** 맞닿아도 되는 깊이 (m). 볼트로 붙은 것과 파고든 것을 가르는 선이다. */
const TOUCH_M = 0.002;

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3400);

const out = await page.evaluate(([partsRe, touch]) => {
  const host = document.getElementById('jb-removal-operation');
  if (!host || !host.__pvScene) return { error: '3D 장면 훅(__pvScene)을 찾지 못했다' };
  const S = host.__pvScene, anim = host.__pvInfeedTest;
  const re = new RegExp(partsRe);

  const picked = [];
  S.scene.traverse((o) => {
    if (!o.isMesh || !o.geometry) return;
    const nm = String(o.name || '') + '|' + String((o.userData && o.userData.label) || '');
    const m = nm.match(re);
    if (!m) return;
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    picked.push({ mesh: o, tag: m[2], name: nm.replace(/^\|/, '').slice(0, 48) });
  });

  // 월드 정렬 상자 — 회전·신축이 걸린 부재는 여덟 꼭짓점을 옮겨 감싼다.
  const box = (m) => {
    const bb = m.geometry.boundingBox;
    m.updateWorldMatrix(true, false);
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < 8; i++) {
      const q = new S.Vector3(i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y,
                              i & 4 ? bb.max.z : bb.min.z).applyMatrix4(m.matrixWorld);
      const v = [q.x, q.y, q.z];
      for (let k = 0; k < 3; k++) {
        if (v[k] < lo[k]) lo[k] = v[k];
        if (v[k] > hi[k]) hi[k] = v[k];
      }
    }
    return { lo, hi };
  };

  const bays = { A: { lo: Infinity, hi: -Infinity }, B: { lo: Infinity, hi: -Infinity } };
  const A = picked.filter((p) => p.tag === 'A'), B = picked.filter((p) => p.tag === 'B');
  let worst = null;

  const sweep = (t) => {
    if (anim && anim.setTime) anim.setTime(t);
    S.scene.updateMatrixWorld(true);
    const boxes = new Map();
    for (const p of picked) {
      const bx = box(p.mesh);
      boxes.set(p, bx);
      const b = bays[p.tag];
      if (bx.lo[2] < b.lo) { b.lo = bx.lo[2]; b.loBy = p.name; b.loT = t; }
      if (bx.hi[2] > b.hi) { b.hi = bx.hi[2]; b.hiBy = p.name; b.hiT = t; }
    }
    // 세 축이 **다** 겹쳐야 부딪힌 것이다. 파고든 깊이는 셋 중 가장 얕은 쪽이다.
    for (const a of A) {
      const ab = boxes.get(a);
      for (const c of B) {
        const cb = boxes.get(c);
        let depth = Infinity;
        for (let k = 0; k < 3; k++) {
          const d = Math.min(ab.hi[k], cb.hi[k]) - Math.max(ab.lo[k], cb.lo[k]);
          if (d < depth) depth = d;
        }
        if (depth > touch && (!worst || depth > worst.depth)) {
          worst = { depth, a: a.name, b: c.name, t };
        }
      }
    }
  };
  const swept = !!(anim && anim.setTime);
  if (swept) { for (let t = 0; t <= 124; t += 0.5) sweep(t); } else sweep(0);
  return { bays, n: picked.length, swept, worst, pairs: A.length * B.length };
}, [BAY_PARTS, TOUCH_M]);

await browser.close();

if (out.error) {
  console.error('✗ ' + out.error);
  process.exit(1);
}
if (errors.length) {
  console.error('✗ 페이지 오류 ' + errors.length + '건 — 첫 줄: ' + errors[0]);
  process.exit(1);
}

const mm = (v) => (v * 1000).toFixed(0);
const pad = (v) => mm(v).padStart(7);

console.log(`대상 메시 ${out.n} · ${out.swept ? '공정시계 0…124 s 를 0.5 s 로 훑음' : '정지 프레임 (영상 훅 없음)'}`);

const A = out.bays.A, B = out.bays.B;
if (!out.n || !isFinite(A.lo) || !isFinite(B.lo)) {
  console.error(`\n✗ 베이를 못 찾았다 — ${BAY_PARTS} 에 걸리는 메시가 A/B 양쪽에 있어야 한다.`
    + '\n  조립체 이름이 바뀌었으면 이 도구의 BAY_PARTS 를 같이 고친다 (조용히 통과시키지 않는다).');
  process.exit(1);
}
if (!out.swept) {
  console.error('\n✗ 영상 훅(__pvInfeedTest)이 없어 정지 프레임만 쟀다 — 신축·승강이 빠진 값이다.');
  process.exit(1);
}

for (const [k, b] of [['A', A], ['B', B]]) {
  console.log(`\nBay ${k}  z ${pad(b.lo)} … ${pad(b.hi)}  (폭 ${pad(b.hi - b.lo)})`);
  console.log(`  하한 ${b.loBy}  @${b.loT} s`);
  console.log(`  상한 ${b.hiBy}  @${b.hiT} s`);
}

const [near, far] = A.hi <= B.hi ? [A, B] : [B, A];
const gap = far.lo - near.hi;
console.log(`\nz 투영 간격 ${mm(gap)} mm  (${near.hiBy} ↔ ${far.loBy})`);
if (gap < 0) {
  console.log('  — 참고값이다. 음수라도 세 축이 다 겹쳐야 부딪힌 것이고,'
    + '\n    안쪽 기둥을 두 베이가 공유하는 설계에서는 음수가 정상이다.');
}

console.log(`\n부재 짝 ${out.pairs}쌍을 세 축으로 확인`);
if (out.worst) {
  console.error(`\n✗ 두 베이의 부재가 ${mm(out.worst.depth)} mm 파고든다 @${out.worst.t} s`
    + `\n  ${out.worst.a}\n  ↕\n  ${out.worst.b}`
    + '\n  베이 피치를 다시 유도해야 한다 — `kinematics.bay_pitch_mm()` = 폭에 눕는'
    + ' 카세트 치수 + 중앙벽, 중심은 그 절반이다.');
  process.exit(1);
}
console.log('\n✓ 베이 A 의 부재가 베이 B 의 부재를 파고들지 않는다'
  + ` (맞닿음 허용 ${mm(TOUCH_M)} mm)`);
