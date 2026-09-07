/* 전처리 플랜트 + DG-HK60C 결합 영상 — 도면의 3D 장면에서 프레임을 뽑는다.
 *
 * 실행 (저장소 루트에서):
 *     node tools/render_plant_video.mjs out/video-frames [fps] [probe]
 *     <ffmpeg> -y -framerate 15 -i out/video-frames/f%04d.jpg -c:v libx264 \
 *              -pix_fmt yuv420p -crf 20 out/plant.mp4
 *
 * 절개 뷰다 — 플랜트 껍질(케이싱)을 숨겨 안의 기계를 보인다. 후단 유리제거기는
 * 벤더 원본 형상이고 **정지 자세(4단계 · 탠덤 박리 중)** 로 서 있다. 움직이는 것은
 * 플랜트 몫인 전처리 라인과 BX-101 인계 브리지뿐이다 — 벤더 기계를 우리가
 * 움직여 보이면 그 순간 그림이 벤더 도면이 아니게 된다.
 *
 * 브리지 행정은 리터럴이 아니라 장면에서 잰다 — 브리지 메시와 LD-101 데크
 * 메시의 x 를 읽어 그 사이를 왕복시킨다. 존이 움직이면 영상도 따라간다.
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const outDir = process.argv[2] || 'out/video-frames';
const FPS = Number(process.argv[3] || 15);
const PROBE = process.argv[4] === 'probe';
const W = 1280, H = 720;
mkdirSync(outDir, { recursive: true });

const DUR = 52;        // 영상 길이 (s)
const A_END = 24;      // 전처리 추적 구간 끝 — 캠페인 애니 0…124 s 를 여기에 편다
const HANDOFF = [24, 36];   // 브리지가 유리를 넘기는 구간

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
await page.emulateMedia({ colorScheme: 'light' });
await page.addInitScript(() => {
  const set = () => document.documentElement.setAttribute('data-theme', 'light');
  if (document.documentElement) set();
  document.addEventListener('DOMContentLoaded', set);
});
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
await page.goto('file://' + resolve('docs/drawings/pv-preprocess-plant.html'), { waitUntil: 'load' });
await page.waitForTimeout(3500);

const rig = await page.evaluate(([w, h]) => {
  const host = document.getElementById('jb-removal-operation');
  const S = host.__pvScene, A = host.__pvInfeedTest;
  A.setCampaignIndex(1, true);
  S.scene.fog = null;
  // 절개 뷰 — 껍질을 숨긴다
  S.scene.traverse((o) => {
    if (o.isMesh && typeof o.name === 'string' && o.name.startsWith('case:')) o.visible = false;
  });
  S.renderer.setPixelRatio(1);
  S.renderer.setSize(w, h, false);
  S.camera.aspect = w / h; S.camera.fov = 36; S.camera.near = 0.1; S.camera.far = 400;
  S.camera.updateProjectionMatrix();
  const find = (label) => {
    let f = null;
    S.scene.traverse((o) => { if (!f && o.isMesh && o.userData && o.userData.label === label) f = o; });
    return f;
  };
  const grab = {};
  for (const [k, label] of Object.entries({
    bridge: 'BX-101 인계 브리지', glass: '브리지 위 유리', deck: 'LD-101 투입 셔틀 롤러베드',
  })) {
    const mesh = find(label);
    if (mesh) grab[k] = { mesh, x: mesh.position.x, y: mesh.position.y, z: mesh.position.z };
  }
  window.__vid = { S, A, grab };
  return {
    hasBridge: !!grab.bridge, hasGlass: !!grab.glass,
    stroke: grab.bridge && grab.deck ? +(grab.deck.x - grab.bridge.x).toFixed(3) : 0,
  };
}, [W, H]);
if (!rig.hasBridge) console.error('  BX-101 브리지 메시를 못 찾았다 — 인계 장면이 정지한다');
console.log(`브리지 행정 ${rig.stroke} m (장면에서 실측)`);

const smooth = (u) => { u = Math.max(0, Math.min(1, u)); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const lerp3 = (a, b, u) => [lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u)];

/* 샷 — [시작 s, 끝 s, 카메라 시작, 카메라 끝, 주시 시작, 주시 끝] (월드 m: +X 하류, +Z 통로) */
const SHOTS = [
  [0, 24, [-31, 7, 13], [3, 7, 13], [-24, 1.2, 0], [9, 1.2, 0]],
  [24, 36, [7.0, 5.6, 9.4], [14.0, 5.2, 9.8], [11.3, 1.3, 0.0], [13.6, 1.3, 0.0]],
  [36, 46, [14, 9.5, 14.5], [30, 8.5, 13.5], [17.0, 2.2, 0.6], [30.0, 2.0, 0.6]],
  [46, 52, [34, 9, 17], [10, 16, 30], [22, 1.2, 0], [4, 1.2, 0]],
];
function camAt(v) {
  const s = SHOTS.find((q) => v >= q[0] && v <= q[1]) || SHOTS[SHOTS.length - 1];
  const u = smooth((v - s[0]) / (s[1] - s[0]));
  return { pos: lerp3(s[2], s[3], u), tgt: lerp3(s[4], s[5], u) };
}
/* 브리지 — 슬롯에서 200 들어 LD-101 데크에 내려놓고 빈 채 돌아온다 */
function bridgeAt(v, stroke) {
  if (v < HANDOFF[0]) return { bx: 0, by: 0, gx: 0, gy: 0, gvis: true };
  const [t0, t1] = HANDOFF;
  const u = Math.min(1, (v - t0) / (t1 - t0));
  const out = Math.min(1, u / 0.62);                 // 나가는 행정
  const back = Math.max(0, (u - 0.68) / 0.32);       // 빈 채 복귀
  const lift = out < 0.2 ? smooth(out / 0.2) * 0.2 : out < 0.9 ? 0.2 : (1 - smooth((out - 0.9) / 0.1)) * 0.2;
  const run = smooth(out) * stroke;
  return {
    bx: run * (1 - smooth(back)), by: lift * (1 - smooth(back)),
    gx: run + smooth(back) * 2.2, gy: lift, gvis: back < 0.9,
  };
}

const frames = PROBE ? [0, 12, 26, 32, 40, 49]
  : Array.from({ length: Math.round(DUR * FPS) }, (_, i) => i / FPS);
let n = 0; const t0 = Date.now();
for (const v of frames) {
  const animT = v < A_END ? (v / A_END) * 124 : 124;
  const cam = camAt(v), d = bridgeAt(v, rig.stroke);
  const url = await page.evaluate(([animT, cam, d]) => {
    const { S, A, grab } = window.__vid;
    A.setTime(animT);
    if (grab.bridge) {
      grab.bridge.mesh.position.x = grab.bridge.x + d.bx;
      grab.bridge.mesh.position.y = grab.bridge.y + d.by;
    }
    if (grab.glass) {
      grab.glass.mesh.position.x = grab.glass.x + d.gx;
      grab.glass.mesh.position.y = grab.glass.y + d.gy;
      grab.glass.mesh.visible = d.gvis;
    }
    S.camera.position.set(...cam.pos);
    S.camera.up.set(0, 1, 0);
    S.camera.lookAt(new S.Vector3(...cam.tgt));
    S.camera.updateProjectionMatrix();
    S.renderer.render(S.scene, S.camera);
    return S.renderer.domElement.toDataURL('image/jpeg', 0.9);
  }, [animT, cam, d]);
  const name = PROBE ? `probe-${String(v).padStart(2, '0')}.jpg` : `f${String(n).padStart(4, '0')}.jpg`;
  writeFileSync(`${outDir}/${name}`, Buffer.from(url.split(',')[1], 'base64'));
  n++;
  if (n % 50 === 0 || PROBE) {
    console.log(`  ${n}/${frames.length}  v=${v.toFixed(2)}s  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
}
if (errs.length) console.error('  페이지 오류: ' + errs.slice(0, 3).join(' | '));
await browser.close();
console.log(`${outDir} — ${n}장 (${DUR}s · ${FPS}fps · ${W}×${H})`);
