/* 전처리 플랜트 전경 렌더 — 도면 미니앱의 3D 장면에서 직접 찍는다.
 *
 * 실행 (저장소 루트에서):
 *     npm i playwright && npx playwright install chromium
 *     node tools/render_plant_views.mjs docs/drawings/pv-preprocess-plant.html docs/renders
 *
 * 프레이밍을 손으로 잡지 않는다. 23개 스테이션 셸(pv-explode-shell)의 실제
 * 바운딩박스를 재서 시선축에 투영하고, 그 반치수로 캔버스 비율과 카메라
 * 거리를 파생시킨다. 그래서 장비가 늘거나 줄면 사진도 따라 바뀐다.
 *
 * 정투영처럼 보이게 화각을 14°까지 좁히고 그만큼 멀리 물러선다(45~48 m).
 * 그 거리에서는 장면 안개가 전체를 회색으로 덮으므로 렌더 동안만 fog 를
 * 끄고 원복한다. 그림자는 끄지 않는다 — 위에서 본 사진에서 높이를 읽는
 * 유일한 단서다.
 *
 * 축 대응: 월드 +X = 하류(공정 진행 방향), 월드 +Z = 배치도 Y 증가 방향
 * = 보행·정비 통로(Y 7,100–8,300)측. 후자는 AFR 존만 Y 로 비대칭
 * (1,200–6,800)인데 3D 에서도 같은 구간이 +Z 로만 (−1.79…+3.78) 비대칭한
 * 것으로 확인했다.
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';

const src = process.argv[2] ?? 'docs/drawings/pv-preprocess-plant.html';
const outDir = process.argv[3] ?? 'docs/renders';
const file = src.startsWith('file://') ? src : 'file://' + (src.startsWith('/') ? src : process.cwd() + '/' + src);
mkdirSync(outDir, { recursive: true });

//: 애니메이션 정지 시각 (s). 라인에 패널이 물려 있는 상태로 찍는다.
const FREEZE_S = 30;

/* padH/padV = 각 축 여백 배수 (1.0 이면 바운딩박스가 화면에 꽉 찬다). */
const VIEWS = [
  { f: 'plant-01-plan',      ko: '평면 · 위에서 내려다본 전경',           dir: [0, 1, 0],          up: [0, 0, -1], long: 3600, padH: 1.04, padV: 1.34, fov: 14 },
  { f: 'plant-02-front',     ko: '정면 · 통로측 (상류 → 하류)',           dir: [0, 0, 1],          up: [0, 1, 0],  long: 3600, padH: 1.04, padV: 1.90, fov: 14 },
  { f: 'plant-03-rear',      ko: '배면 · 벽측 (하류 → 상류)',             dir: [0, 0, -1],         up: [0, 1, 0],  long: 3600, padH: 1.04, padV: 1.90, fov: 14 },
  { f: 'plant-04-left-end',  ko: '좌측면 · 상류 끝 (팔레트 리프트·반전기)', dir: [-1, 0, 0],         up: [0, 1, 0],  long: 1600, padH: 1.12, padV: 1.16, fov: 14 },
  { f: 'plant-05-right-end', ko: '우측면 · 하류 끝 (유리 버퍼 캐리지)',    dir: [1, 0, 0],          up: [0, 1, 0],  long: 1600, padH: 1.12, padV: 1.16, fov: 14 },
  { f: 'plant-06-iso',       ko: '조감도 · 3/4 부감',                     dir: [0.55, 0.62, 0.56], up: [0, 1, 0],  long: 2800, padH: 1.05, padV: 1.05, fov: 26 },
];

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
const errs = [];
page.on('pageerror', e => errs.push(String(e).slice(0, 200)));
await page.emulateMedia({ colorScheme: 'light' });
await page.addInitScript(() => {
  const set = () => document.documentElement.setAttribute('data-theme', 'light');
  if (document.documentElement) set();
  document.addEventListener('DOMContentLoaded', set);
});
await page.goto(file, { waitUntil: 'load' });
await page.waitForTimeout(3000);
await page.evaluate(t => document.getElementById('jb-removal-operation').__pvInfeedTest.setTime(t), FREEZE_S);
await page.waitForTimeout(700);

for (const v of VIEWS) {
  const shot = await page.evaluate((v) => {
    const S = document.getElementById('jb-removal-operation').__pvScene;
    const { scene, camera, renderer } = S;

    // 플랜트 실물 외곽 — 바닥·그리드·하늘은 셸 밖이라 자동으로 빠진다.
    const mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
    scene.children.filter(c => c.name === 'pv-explode-shell').forEach(g => g.traverse(m => {
      if (!m.isMesh || !m.geometry || m.visible === false) return;
      const bb = m.geometry.boundingBox || (m.geometry.computeBoundingBox(), m.geometry.boundingBox);
      if (!bb) return;
      m.updateWorldMatrix(true, false);
      for (let i = 0; i < 8; i++) {
        const q = new S.Vector3(i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y, i & 4 ? bb.max.z : bb.min.z)
          .applyMatrix4(m.matrixWorld);
        const a = [q.x, q.y, q.z];
        for (let k = 0; k < 3; k++) { if (a[k] < mn[k]) mn[k] = a[k]; if (a[k] > mx[k]) mx[k] = a[k]; }
      }
    }));
    const c = new S.Vector3((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2);

    // 시선축 기준 반치수 — 화면 가로/세로/깊이
    const dir = new S.Vector3(...v.dir).normalize();
    const upIn = new S.Vector3(...v.up);
    const right = new S.Vector3().crossVectors(upIn, dir).normalize();
    const upv = new S.Vector3().crossVectors(dir, right).normalize();
    let hw = 0, hh = 0, hd = 0;
    for (let i = 0; i < 8; i++) {
      const q = new S.Vector3(i & 1 ? mx[0] : mn[0], i & 2 ? mx[1] : mn[1], i & 4 ? mx[2] : mn[2]).sub(c);
      hw = Math.max(hw, Math.abs(q.dot(right)));
      hh = Math.max(hh, Math.abs(q.dot(upv)));
      hd = Math.max(hd, Math.abs(q.dot(dir)));
    }
    const HW = hw * v.padH, HH = hh * v.padV, aspect = HW / HH;
    const W = aspect >= 1 ? v.long : Math.max(480, Math.round(v.long * aspect));
    const H = aspect >= 1 ? Math.max(480, Math.round(v.long / aspect)) : v.long;

    const sv = { pos: camera.position.clone(), quat: camera.quaternion.clone(), up: camera.up.clone(),
                 fov: camera.fov, near: camera.near, far: camera.far, aspect: camera.aspect,
                 fog: scene.fog, w: renderer.domElement.width, h: renderer.domElement.height,
                 pr: renderer.getPixelRatio() };
    scene.fog = null;                       // 45 m 밖에서는 안개가 전체를 덮는다
    renderer.setPixelRatio(1);
    renderer.setSize(W, H, false);

    camera.up.copy(upIn);
    camera.fov = v.fov;
    camera.aspect = W / H;
    const t = Math.tan(v.fov * Math.PI / 360);
    const D = Math.max(HH / t, HW / (t * camera.aspect)) + hd;
    camera.position.copy(c).addScaledVector(dir, D);
    camera.near = Math.max(0.1, D - hd - 20);
    camera.far = D + hd + 200;
    camera.updateProjectionMatrix();
    camera.lookAt(c);

    renderer.render(scene, camera);
    renderer.render(scene, camera);
    const url = renderer.domElement.toDataURL('image/png');   // 같은 tick 안이라 버퍼가 살아 있다

    scene.fog = sv.fog;
    camera.position.copy(sv.pos); camera.quaternion.copy(sv.quat); camera.up.copy(sv.up);
    camera.fov = sv.fov; camera.near = sv.near; camera.far = sv.far; camera.aspect = sv.aspect;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(sv.pr);
    renderer.setSize(sv.w / sv.pr, sv.h / sv.pr, false);

    return { url, W, H, D: +D.toFixed(1), hw: +hw.toFixed(2), hh: +hh.toFixed(2) };
  }, v);

  const buf = Buffer.from(shot.url.split(',')[1], 'base64');
  writeFileSync(`${outDir}/${v.f}.png`, buf);
  console.log(`${v.f.padEnd(18)} ${shot.W}×${shot.H}  D=${shot.D} m  내용 ${(shot.hw * 2).toFixed(2)}×${(shot.hh * 2).toFixed(2)} m  ${(buf.length / 1024).toFixed(0)} KB  ${v.ko}`);
}
console.log('page errors:', errs.length ? errs : 'none');
await browser.close();
