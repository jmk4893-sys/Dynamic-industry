/* 외장 케이싱 간섭 검사 — **껍질이 기계를 치는가.**
 *
 * `check_clearance.mjs` 는 이것을 못 본다. 그 검사가 묻는 것은 "공정 중인
 * 물건이 설비를 뚫는가" 하나이고, 설비끼리의 겹침은 같은 조립체가 볼트로
 * 붙어 있어 정상이라 일부러 건너뛴다. **케이싱은 설비다.** 그래서 케이싱을
 * 넣고 그 검사를 돌려 초록불이 떠도, 껍질이 기계를 뚫는지는 아무도 안 봤다.
 *
 * 이 검사가 묻는 것은 넷이다.
 *
 *   ① 껍질이 기계를 뚫는가        — 존 포락선 안에 있다고 믿지 않고 잰다
 *   ② 껍질이 움직이는 것을 치는가  — 로봇·반전링·셔틀·리프트가 도는 동안
 *   ③ 껍질이 통로로 나오는가      — 보행·피난 폭 1,200 mm
 *   ④ 문이 열릴 자리가 있는가      — 문짝이 통로를 막으면 피난로가 막힌다
 *
 * 껍질은 기계에 **매달려 있으므로** 붙는 것이 정상인 자리가 있다 — 멀리언이
 * 앉는 베이스 빔, 판을 잡는 프레임, 케이싱 자기 부재끼리. 그 셋만 예외다.
 *
 * 실행 (저장소 루트에서):
 *     npm i playwright && npx playwright install chromium
 *     node tools/check_casing_fit.mjs docs/drawings/pv-preprocess-plant.html
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';

/* 판이 앉는 평면 — `tools/build_casing.py` 가 casing.py 에서 찍는다.
 * 검사기가 자기 값을 따로 들면 모델과 갈라진다. */
const PLANES = JSON.parse(readFileSync('out/casing-planes.json', 'utf-8'));

const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 껍질이 붙어도 되는 자리 — 이름으로 아는 것. 다만 이름은 빌려 온 것일 수
 *  있어 이것만으로는 부족하다. 아래 `isMount` 가 **형상으로도** 판정한다. */
const MOUNTS = [
  '베이스', '프레임', '가대', '기둥', '브래킷', '지지', '스탠션', '빔', '레일',
  '가드', '바닥', '존', '참조', '투영', '스캔선',
];
/** 판이 앉는 부재로 볼 최대 두께 (m). 이보다 굵으면 구조가 아니라 장비다. */
const SLENDER_M = 0.20;
/** 판 조립 깊이 (m) — casing.PANEL_ASSY_MM. 이 안쪽 접촉은 판이 얹힌 것이다. */
const SKIN_T_M = 0.024;

const T0 = 0, T1 = 130, DT = 0.5;
const TOL_M = 0.002;          // 이보다 얕으면 수치오차
const AISLE_Z = 3.55;         // 통로 시작 (월드 z) — layout.MACHINE_BAND_Y_MM
const AISLE_W = 1.20;

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3400);

const out = await page.evaluate(([t0, t1, dt, tol, mounts, aisleZ, aisleW, planes, slender, skinT]) => {
  const host = document.getElementById('jb-removal-operation');
  if (!host || !host.__pvScene) return { error: '3D 장면 훅(__pvScene)을 찾지 못했다' };
  if (!host.__pvInfeedTest) return { error: '영상 훅(__pvInfeedTest)을 찾지 못했다' };
  const S = host.__pvScene, anim = host.__pvInfeedTest;

  const meshes = [];
  S.scene.traverse((m) => {
    if (!m.isMesh || !m.geometry) return;
    if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
    meshes.push(m);
  });

  // 케이싱 = 이름이 'case:' 로 시작하는 메시. 생성기가 붙인다.
  const isCase = meshes.map((m) => typeof m.name === 'string' && m.name.startsWith('case:'));
  if (!isCase.some(Boolean)) return { error: "케이싱 메시(name='case:…')가 없다" };

  // 빌려 온 이름은 틀릴 수 있다 — 좌표를 같이 적어야 진단이 된다.
  const boxTag = (m) => {
    const b = m.geometry.boundingBox;
    m.updateWorldMatrix(true, false);
    const c = new S.Vector3().copy(b.max).add(b.min).multiplyScalar(0.5).applyMatrix4(m.matrixWorld);
    const d = new S.Vector3().copy(b.max).sub(b.min);
    const f = (v) => (Math.round(v * 1000) / 1000).toFixed(2);
    return ` @${f(c.x)},${f(c.y)},${f(c.z)} ${f(d.x)}×${f(d.y)}×${f(d.z)}`;
  };

  const nameOf = (m) => {
    if (typeof m.name === 'string' && m.name.startsWith('case:')) return m.name;
    const L = m.userData && m.userData.label;
    if (L) return String(L);
    const here = m.getWorldPosition(new S.Vector3());
    for (let up = m.parent, hop = 0; up && hop < 3; up = up.parent, hop++) {
      let best = null, bd = Infinity;
      up.traverse((o) => {
        if (!o.isMesh || o === m) return;
        const l2 = o.userData && o.userData.label; if (!l2) return;
        const d = o.getWorldPosition(new S.Vector3()).distanceTo(here);
        if (d < bd) { bd = d; best = String(l2); }
      });
      if (best) return best + ' (거울상)' + boxTag(m);
    }
    // 라벨을 못 찾으면 **빌려 오지 않는다.** 멀리 있는 형제의 이름을 빌리면
    // 엉뚱한 부재를 지목해 진단이 안 된다 (첫 판에서 buffer 의 겹침이 26 m
    // 떨어진 AFR 가드로 보고됐다). 대신 제 좌표와 크기를 적는다.
    return '(무명)' + boxTag(m);
  };
  const names = meshes.map(nameOf);

  const worldBox = (m) => {
    const bb = m.geometry.boundingBox;
    m.updateWorldMatrix(true, false);
    let mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
    for (let i = 0; i < 8; i++) {
      const q = new S.Vector3(i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y,
                              i & 4 ? bb.max.z : bb.min.z).applyMatrix4(m.matrixWorld);
      const v = [q.x, q.y, q.z];
      for (let k = 0; k < 3; k++) { if (v[k] < mn[k]) mn[k] = v[k]; if (v[k] > mx[k]) mx[k] = v[k]; }
    }
    return { mn, mx };
  };

  // 이름으로 알거나, **판이 앉는 평면에 걸친 가는 부재**면 지지 접촉이다.
  // 첫 판은 이름만 봤는데, 라벨 없는 거울상이 26 m 떨어진 부재의 이름을
  // 빌려 오는 바람에 셀 베이스 빔(14 m × 140 × 160)을 관통으로 셌다.
  const isMount = (n, box, casingName, depth) => {
    if (mounts.some((w) => n.includes(w))) return true;
    const zone = (casingName.split(':')[1] || '').split('-')[0];
    const pl = planes[zone];
    if (!pl) return false;
    const thin = Math.min(box.mx[0] - box.mn[0], box.mx[1] - box.mn[1],
                          box.mx[2] - box.mn[2]) <= slender;
    if (!thin) return false;                       // 굵으면 구조가 아니라 장비다
    // ① 판이 앉는 평면에 걸친 부재  ② 판 두께 안쪽으로만 닿는 부재.
    // 둘 다 "판이 프레임에 얹혔다" 는 뜻이다. 프레임을 가르고 지나가면
    // 겹침이 판 두께를 넘으므로 여기서 안 걸러진다.
    const spans = box.mn[2] <= pl.mount + 1e-6 && box.mx[2] >= pl.mount - 1e-6;
    return spans || depth <= skinT;
  };

  // ── ③ 통로 침범 — 시간과 무관하다 ────────────────────────────────────
  // 껍질은 **설계상** 통로로 조금 나온다 (부재가 밴드 끝까지 나온 존).
  // 그 양이 피난 유효폭 안에 드는지를 본다 — 0 인지가 아니다.
  anim.setTime(0);
  const limit = aisleZ + (planes._limits ? planes._limits.maxEncroach : 0);
  const aisle = [];
  let worstOver = 0;
  for (let i = 0; i < meshes.length; i++) {
    if (!isCase[i]) continue;
    const b = worldBox(meshes[i]);
    const over = (b.mx[2] - aisleZ) * 1000;
    if (over > worstOver) worstOver = over;
    if (b.mx[2] > limit + tol) {
      aisle.push({ name: names[i], over: +over.toFixed(1) });
    }
  }

  // ── ①② 껍질 대 기계 — 시간을 훑는다 ─────────────────────────────────
  const hits = {};
  let frames = 0, sampled = 0;
  for (let t = t0; t <= t1 + 1e-9; t += dt) {
    anim.setTime(+t.toFixed(2));
    frames++;
    const boxes = meshes.map((m) => (m.visible ? worldBox(m) : null));
    for (let i = 0; i < meshes.length; i++) {
      if (!isCase[i] || !boxes[i]) continue;
      sampled++;
      for (let j = 0; j < meshes.length; j++) {
        if (i === j || isCase[j] || !boxes[j]) continue;   // 케이싱끼리는 붙는 게 정상
        const A = boxes[i], B = boxes[j];
        const ov = [0, 1, 2].map((k) => Math.min(A.mx[k], B.mx[k]) - Math.max(A.mn[k], B.mn[k]));
        if (!ov.every((v) => v > tol)) continue;
        const depth = Math.min(...ov);
        const key = names[i] + ' ∩ ' + names[j];
        const rec = hits[key] || (hits[key] = {
          casing: names[i], other: names[j],
          mount: isMount(names[j], B, names[i], depth),
          minD: depth, maxD: depth, t0: t, t1: t, n: 0,
        });
        rec.n++; rec.t1 = t;
        if (depth < rec.minD) rec.minD = depth;
        if (depth > rec.maxD) rec.maxD = depth;
      }
    }
  }

  const rows = Object.values(hits).map((r) => ({
    ...r,
    minMm: +(r.minD * 1000).toFixed(1),
    maxMm: +(r.maxD * 1000).toFixed(1),
    // 깊이가 시간에 따라 변하면 **움직이는 것이 껍질을 치는 것**이다.
    moving: +(r.maxD - r.minD).toFixed(4) > 0.001,
  }));

  return {
    meshes: meshes.length,
    casing: isCase.filter(Boolean).length,
    frames,
    aisle,
    aisleZ, aisleW,
    rows: rows.sort((a, b) => b.maxMm - a.maxMm),
    worstOver: +worstOver.toFixed(1),
  };
}, [T0, T1, DT, TOL_M, MOUNTS, AISLE_Z, AISLE_W, PLANES, SLENDER_M, SKIN_T_M]);

await browser.close();

if (out.error) { console.error('✗ ' + out.error); process.exit(1); }
if (errors.length) { console.error('✗ 페이지 오류\n  ' + errors.join('\n  ')); process.exit(1); }

const mount = out.rows.filter((r) => r.mount && !r.moving);
const moving = out.rows.filter((r) => r.moving);
const hard = out.rows.filter((r) => !r.mount && !r.moving);

console.log(`메시 ${out.meshes} · 케이싱 ${out.casing} · ${out.frames}프레임`);
console.log(`겹침 ${out.rows.length}쌍 — 지지 접촉 ${mount.length} · `
  + `움직이는 것과 ${moving.length} · 고정 관통 ${hard.length}`);

for (const r of moving) {
  console.log(`  ✗ 움직임  ${r.casing}  ∩  ${r.other}`
    + `  최대 ${r.maxMm} mm  t ${r.t0.toFixed(1)}…${r.t1.toFixed(1)} s`);
}
for (const r of hard.slice(0, 25)) {
  console.log(`  ✗ 고정    ${r.casing}  ∩  ${r.other}  ${r.maxMm} mm`);
}
if (hard.length > 25) console.log(`  … 외 ${hard.length - 25}쌍`);

const maxEnc = (PLANES._limits ? PLANES._limits.maxEncroach : 0) * 1000;
console.log(`통로 — 껍질이 최대 ${out.worstOver} mm 나옴 (허용 ${maxEnc} mm · `
  + `유효폭 ${(out.aisleW * 1000 - Math.max(0, out.worstOver)).toFixed(0)} mm)`);
if (out.aisle.length) {
  for (const a of out.aisle.slice(0, 10)) console.log(`  ✗ ${a.name}  ${a.over} mm 나옴 — 허용 초과`);
}

const bad = moving.length + hard.length + out.aisle.length;
if (bad) {
  console.error(`\n✗ 케이싱이 ${bad}곳에서 간섭한다`);
  process.exit(1);
}
console.log('\n✓ 껍질이 기계를 치지 않는다 (남은 겹침은 전부 매달린 지지 접촉)');
