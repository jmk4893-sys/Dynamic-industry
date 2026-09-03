/* 기구 간섭 검사 — 움직이는 것이 서 있는 것을 뚫는가.
 *
 * REV.26 까지 이 저장소의 간섭 스윕은 세 곳에서 눈을 감고 있었다.
 *
 *   ① 시점을 11개만 봤다. 반전기 투입은 t 10.5–13.3 s 에 일어나는데 그 사이를
 *      t=12 한 점으로만 훑었고, 관통이 가장 깊은 t 11.5 를 건너뛰었다.
 *   ② 라벨 없는 메시를 통째로 건너뛰었다. 거울상·반복물은 라벨을 첫 개체에만
 *      다는 것이 이 파일의 규약이라, 좌우 한 쌍 중 오른쪽은 검사 대상이 아니었다.
 *   ③ 토러스(오픈센터 엔드링)를 바운딩박스로 쟀다. 링은 가운데가 뚫려 있어서
 *      박스가 겹쳐도 통과일 수 있고, 겹치지 않아도 관통일 수 있다.
 *
 * 그래서 실제로 있던 것을 못 봤다 — 패널이 반전 케이지에 대각으로 들어가며
 * 엔드링 단면을 최대 88 mm 파고들고 있었다(REV.26 실측).
 *
 * 이 검사는 셋을 다 고친다. 시간은 0.5 s 간격으로 촘촘히, 대상은 라벨 유무와
 * 무관하게 전부, 링은 축 기준 반경으로 판정한다.
 *
 * 묻는 것은 하나다 — **공정 중인 물건이 설비를 뚫는가.** 설비끼리의 겹침은
 * 대부분 볼트로 붙어 있는 같은 조립체라 겹치는 것이 정상이고, 그것까지 세면
 * 예외 목록이 도면보다 길어져 검사가 뜻을 잃는다. 그래서 대상은 공정물
 * (패널·정션박스·유리·떼어낸 프레임)로 한정하고, 그 공정물을 싣고 가는
 * 캐리어의 형제끼리는 서로 검사하지 않는다.
 *
 * 설계상 접촉(무는 클램프·스토퍼·롤러·지지대)은 예외다. 예외는 이름으로
 * 적어 두고, 그 목록은 src/pv_preprocess/kinematics.py 의 DESIGN_CONTACTS 와
 * 같아야 한다 — 테스트가 둘이 같은지 본다.
 *
 * 실행 (저장소 루트에서):
 *     npm i playwright && npx playwright install chromium
 *     node tools/check_clearance.mjs docs/drawings/pv-preprocess-plant.html
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-preprocess-plant.html';

/** 설계상 접촉 — 무는·받는·미는 부재다. kinematics.DESIGN_CONTACTS 와 같다. */
const DESIGN_CONTACTS = [
  '클램프', '조', '스토퍼', '롤러', '지지', '진공', '포크', '손목', '푸셔', '패드',
  '컨베이어', '셔틀', '캐리지', '레일', '적재대', '리프트', '팔레트', '랙',
  '가위날', '노즐', '센서', '케이블', '슬라이드', '호스', '균열감시',
  '프레임', '정반', '베드', '브래킷', '유압', '인발', '기준 슈', 'RB-101', '포획빔',
  '칼날', '박리 계면',
];

/** 통과 개구 — 공정물이 지나가라고 낸 구멍인데 3D 는 판으로 그린다.
 *  kinematics.PASS_THROUGH 와 같다. */
const PASS_THROUGH = [
  '가드', '게이트', '터널', '커튼', '개구', '슈트', '존', '참조', '투영', '스캔선', '바닥',
];

/** 공정 중인 물건 — src/pv_preprocess/kinematics.py 의 WORKPIECES 와 같다. */
const WORKPIECES = [
  '태양광 패널', '적재 패널', '팔레트 패널', 'JBOX 제거상태',
  '정션박스 형상', '검출 정션박스', '알루미늄 프레임', '박리 유리',
];

const T0 = 0, T1 = 130, DT = 0.5;
const TOL_M = 0.002;      // 이보다 얕은 겹침은 수치오차로 본다

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(3400);

const result = await page.evaluate(([t0, t1, dt, tol, contacts, work, pass]) => {
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

  // 라벨 없는 거울상은 같은 부모 안 가장 가까운 라벨을 빌려 쓴다.
  const nameOf = (m) => {
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
      if (best) return best + ' (거울상)';
    }
    return '(무명)';
  };
  const names = meshes.map(nameOf);

  const worldBox = (m) => {
    const bb = m.geometry.boundingBox;
    m.updateWorldMatrix(true, false);
    let mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
    for (let i = 0; i < 8; i++) {
      const q = new S.Vector3(i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y, i & 4 ? bb.max.z : bb.min.z)
        .applyMatrix4(m.matrixWorld);
      const v = [q.x, q.y, q.z];
      for (let k = 0; k < 3; k++) { if (v[k] < mn[k]) mn[k] = v[k]; if (v[k] > mx[k]) mx[k] = v[k]; }
    }
    return { mn, mx };
  };

  // ── 대상 고르기 — 공정 중인 물건이고, 실제로 움직이는 것 ────────────────
  const sig = (m) => { m.updateWorldMatrix(true, false); return m.matrixWorld.elements.join(','); };
  anim.setTime(9); const s0 = meshes.map(sig);
  anim.setTime(41); const s1 = meshes.map(sig);
  anim.setTime(92); const s2 = meshes.map(sig);
  const moves = meshes.map((m, i) => s0[i] !== s1[i] || s1[i] !== s2[i] || s0[i] !== s2[i]);
  const isWork = (n) => work.some((w) => n.includes(w));
  const dynamic = meshes.map((m, i) => moves[i] && isWork(names[i]));

  // 캐리어 = 움직이는 메시의 조상 중 스스로 움직이는 가장 위쪽 그룹.
  // 같은 캐리어에 실린 형제는 서로 붙어 있는 것이 정상이다.
  const carrierOf = (m) => {
    let car = m, q = m.parent, hop = 0;
    while (q && q.type !== 'Scene' && hop++ < 6) {
      if (q.position.lengthSq() > 0 || q.rotation.x || q.rotation.y || q.rotation.z) car = q;
      q = q.parent;
    }
    return car;
  };
  const carriers = meshes.map(carrierOf);

  const isContact = (a, b) => contacts.some((w) => a.includes(w) || b.includes(w))
    || pass.some((w) => b.includes(w));

  const hits = {};
  let frames = 0;
  for (let t = t0; t <= t1 + 1e-9; t += dt) {
    anim.setTime(+t.toFixed(2));
    frames++;
    const boxes = meshes.map((m, i) => (m.visible ? worldBox(m) : null));
    for (let i = 0; i < meshes.length; i++) {
      if (!dynamic[i] || !boxes[i]) continue;
      for (let j = 0; j < meshes.length; j++) {
        if (i === j || !boxes[j]) continue;
        if (carriers[i] === carriers[j]) continue;   // 같은 캐리어에 실린 형제
        // 공정물끼리는 보지 않는다. 한 장의 패널이 공정 단계마다 다른 그룹으로
        // 표현되므로(인계 순간 두 표현이 겹친다) 서로 뚫는다는 판정이 뜻이 없다.
        if (dynamic[j]) continue;
        const A = boxes[i], B = boxes[j];
        const ov = [0, 1, 2].map((k) => Math.min(A.mx[k], B.mx[k]) - Math.max(A.mn[k], B.mn[k]));
        if (!ov.every((v) => v > tol)) continue;

        // 토러스는 축 기준 반경으로 다시 판정한다 — 가운데가 뚫려 있다.
        const g = meshes[j].geometry;
        if (g.type === 'TorusGeometry') {
          const M = meshes[j]; M.updateWorldMatrix(true, false);
          const C = new S.Vector3(0, 0, 0).applyMatrix4(M.matrixWorld);
          const AX = new S.Vector3(0, 0, 1).transformDirection(M.matrixWorld).normalize();
          const rIn = g.parameters.radius - g.parameters.tube, rOut = g.parameters.radius + g.parameters.tube;
          const bb = meshes[i].geometry.boundingBox;
          meshes[i].updateWorldMatrix(true, false);
          let pen = 0;
          for (let c = 0; c < 8; c++) {
            const q = new S.Vector3(c & 1 ? bb.max.x : bb.min.x, c & 2 ? bb.max.y : bb.min.y, c & 4 ? bb.max.z : bb.min.z)
              .applyMatrix4(meshes[i].matrixWorld).sub(C);
            const along = q.dot(AX);
            const rad = Math.sqrt(Math.max(0, q.lengthSq() - along * along));
            if (rad > rIn && rad < rOut) pen = Math.max(pen, Math.min(rad - rIn, rOut - rad));
          }
          if (pen <= tol) continue;
          const key = i + '|' + j;
          const h = hits[key] || (hits[key] = { i, j, d: 0, t, n: 0, ring: true, contact: isContact(names[i], names[j]) });
          h.n++; if (pen > h.d) { h.d = pen; h.t = t; }
          continue;
        }

        const depth = Math.min(...ov);
        const key = i + '|' + j;
        const h = hits[key] || (hits[key] = { i, j, d: 0, t, n: 0, ring: false, contact: isContact(names[i], names[j]) });
        h.n++; if (depth > h.d) { h.d = depth; h.t = t; }
      }
    }
  }
  return {
    frames, meshes: meshes.length, dynamic: dynamic.filter(Boolean).length,
    hits: Object.values(hits).map((v) => ({
      k: names[v.i] + ' ∩ ' + names[v.j],
      at: (() => { const c = meshes[v.j].getWorldPosition(new S.Vector3());
        return [c.x, c.y, c.z].map((q) => q.toFixed(1)).join(','); })(),
      mm: Math.round(v.d * 1000), t: +v.t.toFixed(1), n: v.n, ring: v.ring, contact: v.contact,
    })).sort((a, b) => b.mm - a.mm),
  };
}, [T0, T1, DT, TOL_M, DESIGN_CONTACTS, WORKPIECES, PASS_THROUGH]);

await browser.close();

if (result.error) { console.error('✗ ' + result.error); process.exit(2); }

const hard = result.hits.filter((h) => h.ring || !h.contact);
const soft = result.hits.filter((h) => !h.ring && h.contact);

console.log(`메시 ${result.meshes} · 공정물 메시 ${result.dynamic} · 프레임 ${result.frames}`);
console.log(`겹침 ${result.hits.length}쌍 — 설계상 접촉 ${soft.length} · 확인 필요 ${hard.length}`);
for (const h of hard.slice(0, 20)) {
  console.log(`  ✗ ${String(h.mm).padStart(4)} mm @t=${String(h.t).padStart(5)}s ${h.ring ? '[링 단면 관통]' : '[관통]'} ${h.k}  @[${h.at}]`);
}
if (errors.length) { console.error('✗ 페이지 오류: ' + errors.join(' | ')); process.exit(2); }
if (hard.length) {
  console.error(`\n✗ 설계상 접촉으로 설명되지 않는 겹침 ${hard.length}쌍 — 기구를 고치거나, `
    + '근거를 적어 kinematics.DESIGN_CONTACTS 와 이 파일의 DESIGN_CONTACTS 에 같이 넣을 것');
  process.exit(1);
}
console.log('\n✓ 공정 중인 물건이 설비를 뚫지 않는다 (남은 겹침은 전부 설계상 접촉)');
