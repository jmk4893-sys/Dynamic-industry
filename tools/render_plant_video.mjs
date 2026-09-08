/* 전처리 플랜트 + DG-HK60C 전체 운영 영상 — 도면의 3D 장면에서 프레임을 뽑는다.
 *
 * 실행 (저장소 루트에서):
 *     node tools/render_plant_video.mjs out/video-frames [fps] [probe]
 *     <ffmpeg> -y -framerate 15 -i out/video-frames/f%04d.jpg -c:v libx264 \
 *              -pix_fmt yuv420p -b:v 1150k -preset slow -movflags +faststart out/plant.mp4
 *
 * 투입에서 유리·셀모듈 반출까지 한 번에 본다. 절개 뷰다 — 플랜트 껍질(케이싱)을
 * 숨겨 안의 기계를 보인다.
 *
 * 움직이는 것은 셋이다.
 *   ① 전처리 라인 — 도면이 갖고 있는 60장 캠페인 애니(0…124 s)를 구간별로 편다.
 *   ② BX-101 인계 브리지 — 행정은 장면에서 잰다(브리지 메시와 LD-101 데크 메시의 x).
 *   ③ DG-HK60C 안 — 벤더 원본의 **정지 자세 조각**을 역할 이름으로 잡아 이어 돌린다.
 *      나이프 캐리지가 55 mm/s 로 지나가고, 그 뒤로 유리·셀/EVA·백시트가 3계통으로
 *      갈린다. 기계 형상 자체는 벤더 도면 그대로고 우리가 옮기는 것은 자세뿐이다.
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const outDir = process.argv[2] || 'out/video-frames';
const FPS = Number(process.argv[3] || 15);
const PROBE = process.argv[4] === 'probe';
const W = 1280, H = 720;
mkdirSync(outDir, { recursive: true });

const DUR = 72;
/* 구간 — [영상 시작, 영상 끝, 캠페인 애니 시작, 끝] (애니 0…124 s) */
const PHASES = [
  [0, 8, 0, 9],        // 지게차 도킹 · 30장 팔레트
  [8, 19, 9, 24],      // 듀얼 반전 카세트 — 단장 분리 · 승강 · 180° 반전
  [19, 26, 24, 34],    // RB-101 인계 → PT-101 (손목이 라인 방향으로 되돌린다)
  [26, 34, 34, 62],    // JBR-201 정션박스 제거
  [34, 42, 62, 95],    // AFR-101 프레임 분리 · 연마 · 검사
  [42, 48, 95, 124],   // GBR-301 레시피 버퍼
  [48, 72, 124, 124],  // 후단 — 브리지 인계부터 반출까지
];
const BRIDGE = [48, 58];      // BX-101 이 유리 한 장을 LD-101 데크에 놓는다
const PEEL = [58, 66];        // 55 mm/s 탠덤 박리 행정
const SPLIT = [66, 72];       // 3계통 분기 — 유리 · 셀/EVA · 백시트

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
  S.scene.traverse((o) => {
    if (o.isMesh && typeof o.name === 'string' && o.name.startsWith('case:')) o.visible = false;
  });
  S.renderer.setPixelRatio(1);
  S.renderer.setSize(w, h, false);
  S.camera.aspect = w / h; S.camera.fov = 36; S.camera.near = 0.1; S.camera.far = 400;
  S.camera.updateProjectionMatrix();

  const keep = (o) => ({ o, x: o.position.x, y: o.position.y, z: o.position.z, vis: o.visible });
  const g = { knife: [], glass: [], cells: [], sheet: [], out: [] };
  let bridge = null, glassOnBridge = null, deck = null;
  S.scene.traverse((o) => {
    if (!o.isMesh) return;
    const l = (o.userData && o.userData.label) || '';
    if (l === 'BX-101 인계 브리지') bridge = keep(o);
    else if (l === '브리지 위 유리') glassOnBridge = keep(o);
    else if (l === 'LD-101 투입 셔틀 롤러베드') deck = keep(o);
    else if (l === 'DG-HK60C 나이프 캐리지' || /핫나이프/.test(l)) g.knife.push(keep(o));
    else if (l === 'DG-HK60C 박리 중 유리') g.glass.push(keep(o));
    else if (l === 'DG-HK60C 유리 위 셀/EVA 층') g.cells.push(keep(o));
    else if (l === 'DG-HK60C 벗겨지는 백시트') g.sheet.push(keep(o));
    else if (l === 'DG-HK60C 셀/EVA 반출 적층체') g.out.push(keep(o));
  });
  /* 후단 절개 — 벤더 외장(스킨·리빌)과 방책을 골라 숨긴다. 도장색으로 고르므로
     기계 형상은 하나도 손대지 않는다. 플랜트 케이싱을 숨긴 것과 같은 뜻이다. */
  const CUT = ['#dcdedb', '#1a2124', '#46545a'];
  const skin = [];
  S.scene.traverse((o) => { if (o.isMesh && o.userData && CUT.includes(o.userData.livery)) skin.push(o); });
  window.__vid = { S, A, g, bridge, glassOnBridge, skin };
  return {
    stroke: bridge && deck ? +(deck.x - bridge.x).toFixed(3) : 0,
    counts: Object.fromEntries(Object.entries(g).map(([k, v]) => [k, v.length])),
    hasBridge: !!bridge,
  };
}, [W, H]);
console.log(`브리지 행정 ${rig.stroke} m · 후단 조각 ${JSON.stringify(rig.counts)}`);
if (!rig.hasBridge) console.error('  BX-101 브리지를 못 찾았다 — 인계 장면이 정지한다');

const clamp01 = (u) => Math.max(0, Math.min(1, u));
const smooth = (u) => { u = clamp01(u); return u * u * (3 - 2 * u); };
const span = (v, a, b) => clamp01((v - a) / (b - a));
const lerp = (a, b, u) => a + (b - a) * u;
const lerp3 = (a, b, u) => [lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u)];

/* 샷 — [시작 s, 끝 s, 카메라 시작, 끝, 주시 시작, 끝] (월드 m: +X 하류, +Z 통로) */
const SHOTS = [
  [0, 8, [-14.5, 6.0, 9.5], [-16.0, 4.6, 7.6], [-21.0, 1.2, -1.4], [-20.6, 1.6, -1.5]],
  [8, 19, [-16.0, 4.6, 7.6], [-16.8, 4.2, 5.4], [-20.6, 2.0, -1.5], [-20.4, 2.6, -1.2]],
  [19, 26, [-16.6, 4.4, 6.4], [-13.0, 4.2, 6.6], [-19.4, 1.8, -0.6], [-15.6, 1.3, 0.0]],
  [26, 34, [-12.4, 4.6, 7.0], [-7.6, 4.4, 7.0], [-15.2, 1.3, 0.0], [-9.6, 1.3, 0.0]],
  [34, 42, [-7.0, 5.0, 7.6], [0.6, 4.8, 7.4], [-9.0, 1.3, 0.0], [-1.4, 1.3, 0.0]],
  [42, 48, [1.6, 5.2, 8.2], [7.6, 5.0, 8.0], [-0.6, 1.3, 0.0], [6.4, 1.3, 0.0]],
  [48, 58, [7.0, 5.6, 9.4], [14.0, 5.2, 9.8], [11.3, 1.3, 0.0], [13.6, 1.3, 0.0]],
  [58, 66, [16.8, 6.4, 9.8], [24.2, 5.8, 9.2], [20.6, 1.3, 0.0], [23.2, 1.3, 0.0]],
  [66, 72, [24.5, 5.6, 8.6], [33.0, 9.5, 17.0], [25.5, 1.4, 1.4], [23.0, 1.4, 0.4]],
];
function camAt(v) {
  const s = SHOTS.find((q) => v >= q[0] && v <= q[1]) || SHOTS[SHOTS.length - 1];
  return { pos: lerp3(s[2], s[3], smooth(span(v, s[0], s[1]))), tgt: lerp3(s[4], s[5], smooth(span(v, s[0], s[1]))) };
}
function animAt(v) {
  const p = PHASES.find((q) => v >= q[0] && v <= q[1]) || PHASES[PHASES.length - 1];
  return lerp(p[2], p[3], span(v, p[0], p[1]));
}
function bridgeAt(v, stroke) {
  if (v < BRIDGE[0]) return { bx: 0, by: 0, gx: 0, gy: 0, gvis: true };
  const u = span(v, BRIDGE[0], BRIDGE[1]);
  const out = Math.min(1, u / 0.62), back = Math.max(0, (u - 0.68) / 0.32);
  const lift = out < 0.2 ? smooth(out / 0.2) * 0.2 : out < 0.9 ? 0.2 : (1 - smooth((out - 0.9) / 0.1)) * 0.2;
  const run = smooth(out) * stroke;
  return { bx: run * (1 - smooth(back)), by: lift * (1 - smooth(back)),
    gx: run + smooth(back) * 1.6, gy: lift, gvis: back < 0.9 };
}
/* 후단 — 나이프가 지나가고 그 뒤로 셋이 갈린다 */
function machineAt(v) {
  const peel = span(v, PEEL[0], PEEL[1]);              // 55 mm/s 통과박리
  const back = span(v, PEEL[1], PEEL[1] + 1.2);        // 700 mm/s 복귀
  const kx = lerp(-1.15, 1.15, peel) * (1 - back) + (-1.15) * back;
  const sp = span(v, SPLIT[0], SPLIT[1]);
  return {
    cut: v >= 55.0,                         // 후단 절개 — 외장을 걷고 안을 보인다
    kx,                                     // 나이프 캐리지 X
    peel,                                   // 벗겨진 만큼 백시트·셀층이 따라간다
    glassOut: smooth(span(v, SPLIT[0], SPLIT[0] + 3.6)) * 6.4,   // 유리 → 냉각·반출
    cellOut: smooth(sp) * 2.6,              // 셀/EVA → 통로쪽 카트
    fade: 1 - smooth(span(v, SPLIT[0] + 1.2, SPLIT[0] + 3.0)),   // 유리 위 셀층은 걷힌다
  };
}

const frames = PROBE ? [3, 12, 22, 30, 38, 45, 53, 62, 69]
  : Array.from({ length: Math.round(DUR * FPS) }, (_, i) => i / FPS);
let n = 0; const t0 = Date.now();
for (const v of frames) {
  const cam = camAt(v), d = bridgeAt(v, rig.stroke), mk = machineAt(v), at = animAt(v);
  const url = await page.evaluate(([at, cam, d, mk]) => {
    const { S, A, g, bridge, glassOnBridge, skin } = window.__vid;
    A.setTime(at);
    for (const o of skin) o.visible = !mk.cut;
    if (bridge) { bridge.o.position.x = bridge.x + d.bx; bridge.o.position.y = bridge.y + d.by; }
    if (glassOnBridge) {
      glassOnBridge.o.position.x = glassOnBridge.x + d.gx;
      glassOnBridge.o.position.y = glassOnBridge.y + d.gy;
      glassOnBridge.o.visible = d.gvis;
    }
    for (const p of g.knife) p.o.position.x = p.x + mk.kx;
    for (const p of g.sheet) p.o.position.x = p.x + mk.kx * 0.9;
    for (const p of g.cells) { p.o.position.x = p.x + mk.kx * 0.5; p.o.visible = mk.fade > 0.05; }
    for (const p of g.glass) p.o.position.x = p.x + mk.glassOut;
    for (const p of g.out) p.o.position.z = p.z + mk.cellOut;
    S.camera.position.set(...cam.pos);
    S.camera.up.set(0, 1, 0);
    S.camera.lookAt(new S.Vector3(...cam.tgt));
    S.camera.updateProjectionMatrix();
    S.renderer.render(S.scene, S.camera);
    return S.renderer.domElement.toDataURL('image/jpeg', 0.9);
  }, [at, cam, d, mk]);
  const name = PROBE ? `probe-${String(v).padStart(2, '0')}.jpg` : `f${String(n).padStart(4, '0')}.jpg`;
  writeFileSync(`${outDir}/${name}`, Buffer.from(url.split(',')[1], 'base64'));
  n++;
  if (n % 60 === 0 || PROBE) console.log(`  ${n}/${frames.length}  v=${v.toFixed(2)}s  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
if (errs.length) console.error('  페이지 오류: ' + errs.slice(0, 3).join(' | '));
await browser.close();
console.log(`${outDir} — ${n}장 (${DUR}s · ${FPS}fps · ${W}×${H})`);
