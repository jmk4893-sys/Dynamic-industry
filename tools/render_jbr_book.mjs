/* JBR-201 도면집을 한 편의 영상으로 걷는다 — 다섯 장을 순서대로 보여 준다.
 *
 * 실행 (저장소 루트에서):
 *     node tools/render_jbr_book.mjs out/jbr-frames [fps] [probe]
 *     <ffmpeg> -y -framerate 15 -i out/jbr-frames/f%04d.jpg -c:v libx264 \
 *              -pix_fmt yuv420p -b:v 1400k -preset slow -movflags +faststart out/jbr-book.mp4
 *
 * 화면 녹화가 아니다. 페이지마다 **고정 시간각**을 밟는다 —
 *   · 3D 운전은 도면의 시계 훅(`__pvInfeedTest.setTime`)을 40 → 85 s 로 민다
 *   · 물리는 `PH.advance(1/fps)` 로 적분을 한 걸음씩 진행한다
 *   · 근접도는 rAF 와 `performance.now` 를 가상 시계로 갈아 끼워 프레임마다 판다
 *   · 정지 시트(상세도·제작 도면집)는 스크롤·확대를 시간의 함수로 준다
 * 그래서 몇 번을 찍어도 같은 영상이 나오고, 느린 기계에서도 프레임이 안 빠진다.
 *
 * 프레임 크기는 전부 뷰포트(1280×720)로 통일한다 — 장마다 캔버스 크기가 다르므로
 * 요소를 찍으면 인코더가 받지 못한다.
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const outDir = process.argv[2] || 'out/jbr-frames';
const FPS = Number(process.argv[3] || 15);
const PROBE = process.argv[4] === 'probe';
const W = 1280, H = 720;
mkdirSync(outDir, { recursive: true });

const clamp01 = (u) => Math.max(0, Math.min(1, u));
const smooth = (u) => { u = clamp01(u); return u * u * (3 - 2 * u); };
const span = (v, a, b) => clamp01((v - a) / (b - a));
const lerp = (a, b, u) => a + (b - a) * u;
const lerp3 = (a, b, u) => [lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u)];

/* 장 — [초, 파일, 제목, 부제] */
const CHAPTERS = [
  [20, 'pv-jbr-scene.html', 'JBR-201 · 3D 운전', '패널 진입에서 AFR 인계까지 · 40 → 85 s'],
  [12, 'pv-jbr-detail.html', 'JBR-201 · 상세도', '순차 제거의 움직임이 어떤 값에서 나왔는가'],
  [12, 'pv-jbr-closeup.html', 'JBR-201 · 근접도', '정션박스가 떨어져 나오는 순간 · 두 배율'],
  [10, 'pv-jbr-fab.html', 'JBR-201 · 제작 도면집', '부품도 · 구멍 · 체결표'],
  [12, 'pv-jbr-physics.html', 'JBR-201 · 물리 시뮬레이션', '진공이 끊긴 뒤로는 아무도 자세를 정해 주지 않는다'],
];

/* 3D 운전 샷 — [영상 초, 끝, 카메라 시작·끝, 주시 시작·끝, 자막] (월드 m).
   JBR 셀은 x −14.61…−7.19, y 0…2.8 에 선다. 도면의 기본 시점이 z 음의 쪽이라
   카메라도 전부 그쪽에 둔다 — 양의 쪽은 케이싱 유리판(z ＝ +1.6) 안이다. */
const SHOTS = [
  [0, 3.5, [-14.4, 3.2, -5.4], [-13.9, 3.1, -5.1], [-11.3, 1.35, 0], [-11.2, 1.35, 0],
   'JBR-201 셀 전경 — 7.4 m 한 칸'],
  [3.5, 7, [-15.9, 2.6, -4.6], [-15.4, 2.55, -4.4], [-13.4, 1.25, 0], [-13.1, 1.25, 0],
   'JB-201 인계부 — 패널이 셀로 들어온다'],
  [7, 11, [-12.9, 2.3, -3.6], [-12.4, 2.25, -3.4], [-11.2, 1.25, -0.1], [-11.0, 1.25, -0.1],
   '1헤드 · L칼날 — 박스마다 4.0 s'],
  [11, 14.5, [-11.2, 2.1, -3.1], [-10.8, 2.05, -2.95], [-10.6, 1.2, -0.2], [-10.4, 1.2, -0.2],
   '진공 포획 · Z추종 — 계면 전단'],
  [14.5, 17, [-11.0, 6.4, -3.4], [-10.6, 6.2, -3.2], [-11.0, 1.2, 0], [-10.7, 1.2, 0],
   '상부 시점 — 브리지 X 와 호퍼'],
  [17, 20, [-8.3, 3.0, -5.3], [-7.6, 2.95, -5.0], [-9.7, 1.3, 0], [-9.2, 1.3, 0],
   'AFR-101 인계로 — 85 s'],
];
const shotAt = (v) => {
  const s = SHOTS.find((q) => v >= q[0] && v <= q[1]) || SHOTS[SHOTS.length - 1];
  const u = smooth(span(v, s[0], s[1]));
  return { pos: lerp3(s[2], s[3], u), tgt: lerp3(s[4], s[5], u), sub: s[6] };
};

/* 장 제목 띠 — 어느 도면을 보고 있는지 화면 안에 적는다. */
function banner({ title, sub }) {
  const el = document.createElement('div');
  el.id = '__cap';
  el.innerHTML = '<b></b><span></span>';
  el.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;'
    + 'padding:10px 18px;background:#0e141a;border-top:1px solid #2b3947;color:#eef2f5;'
    + 'font:600 15px/1.35 system-ui,"Noto Sans KR",sans-serif;display:flex;gap:14px;'
    + 'align-items:baseline';
  el.querySelector('b').textContent = title;
  const s = el.querySelector('span');
  s.textContent = sub;
  s.style.cssText = 'font-weight:400;font-size:12.5px;opacity:.78';
  document.body.appendChild(el);
}

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
let n = 0;
const shot = async (page) => {
  const buf = await page.screenshot({ type: 'jpeg', quality: 88 });
  writeFileSync(resolve(outDir, `f${String(n).padStart(4, '0')}.jpg`), buf);
  n += 1;
};

for (const [secs, file, title, sub] of CHAPTERS) {
  const frames = PROBE ? Array.from({ length: 6 }, (_, i) => (i + 0.5) * secs / 6)
    : Array.from({ length: Math.round(secs * FPS) }, (_, i) => i / FPS);
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  // 가상 시계는 **훅이 없는 장에만** 건다. 3D 운전(`setTime`)과 물리(`PH.advance`)는
  // 자기 시계를 갖고 있고, rAF 를 뺏으면 부팅부터 못 한다.
  const virtualClock = file === 'pv-jbr-closeup.html';
  if (virtualClock) await page.addInitScript((fps) => {
    let now = 0; const queue = [];
    const raf = (cb) => { queue.push(cb); return queue.length; };
    Object.defineProperty(window, 'requestAnimationFrame', { value: raf, writable: true });
    Object.defineProperty(window, 'cancelAnimationFrame', { value: () => {}, writable: true });
    performance.now = () => now;
    Date.now = () => now;
    window.__tick = () => {
      now += 1000 / fps;
      const due = queue.splice(0, queue.length);
      for (const cb of due) { try { cb(now); } catch (e) { /* 한 장이 죽어도 나머지는 돈다 */ } }
    };
  }, FPS);
  await page.goto('file://' + resolve('docs/drawings', file));
  await page.waitForTimeout(1200);
  await page.evaluate(banner, { title, sub });

  if (file === 'pv-jbr-scene.html') {
    await page.evaluate(([w, h]) => {
      // 훅은 window 가 아니라 **호스트 요소**에 붙는다 (플랜트 원본과 같은 자리).
      const host = document.getElementById('jb-removal-operation');
      const S = host.__pvScene;
      window.__book = { S, T: host.__pvInfeedTest };
      const g = document.getElementById('jb-guard'); if (g && g.checked) g.click();
      // 무대만 남기고 페이지 크롬을 걷어 낸다 — 3D 가 프레임 전체를 쓰게.
      const stage = document.getElementById('jb-stage');
      document.body.appendChild(stage);
      for (const el of Array.from(document.body.children)) {
        if (el !== stage && el.id !== '__cap') el.style.display = 'none';
      }
      document.documentElement.style.background = document.body.style.background = '#0a0f14';
      stage.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;'
        + 'margin:0;padding:0;border:0;border-radius:0;z-index:9000;background:#0a0f14';
      const cv = document.getElementById('jb-canvas');
      cv.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%';
      const help = document.querySelector('.jb-help'); if (help) help.remove();
      // 상태 카드는 남긴다 — 지금 몇 초에 무엇을 하는지가 영상의 절반이다.
      // 페이지가 실행 중에 이 카드를 무대 밖 슬롯으로 옮기므로 직접 무대 안으로 되돌린다.
      const st = document.querySelector('.jb-status');
      if (st) {
        stage.appendChild(st);
        st.style.cssText = 'position:absolute;left:16px;top:16px;z-index:20;max-width:56%;'
          + 'background:rgba(10,16,21,.86);border:1px solid #2b3947;border-radius:8px;'
          + 'padding:10px 14px;color:#eef2f5;box-shadow:none;display:grid;gap:3px';
        for (const kid of st.querySelectorAll('*')) kid.style.color = '#eef2f5';
      }
      S.renderer.setSize(w, h, false);
      if (S.camera.isPerspectiveCamera) { S.camera.aspect = w / h; }
      S.camera.updateProjectionMatrix();
      // 페이지에도 자기 카메라를 물리는 루프가 있다. 렌더 직전에 우리 값을 덮어
      // 어느 쪽이 먼저 돌든 화면에는 우리가 정한 샷만 남게 한다.
      const draw = S.renderer.render.bind(S.renderer);
      S.renderer.render = (scene, cam) => {
        const c = window.__book.cam;
        if (c && cam) {
          cam.position.set(c.pos[0], c.pos[1], c.pos[2]);
          cam.up.set(0, 1, 0);
          cam.lookAt(new S.Vector3(c.tgt[0], c.tgt[1], c.tgt[2]));
          cam.updateProjectionMatrix();
        }
        draw(scene, cam);
      };
    }, [W, H]);
    let sub = null;
    for (const v of frames) {
      const at = lerp(40, 85, span(v, 0, 20));
      const cam = shotAt(v);
      if (cam.sub !== sub) {
        sub = cam.sub;
        await page.evaluate((t) => { document.querySelector('#__cap span').textContent = t; }, sub);
      }
      await page.evaluate(([at, cam]) => {
        const { S, T } = window.__book;
        window.__book.cam = cam;
        if (T) T.setTime(at);
        S.renderer.render(S.scene, S.camera);
      }, [at, cam]);
      await shot(page);
    }
  } else if (file === 'pv-jbr-physics.html') {
    await page.evaluate(() => { const b = document.getElementById('play'); if (b) b.click(); });
    for (const v of frames) {
      await page.evaluate((fps) => { if (window.PH && window.PH.advance) window.PH.advance(1 / fps); else window.__tick(); }, FPS);
      await shot(page);
    }
  } else if (file === 'pv-jbr-closeup.html') {
    // 세 장면(박리 · 절단 · 배출) × 두 배율(전경 · 실척) = 여섯 칸을 같은 길이로 나눈다.
    for (const v of frames) {
      const cell = Math.min(5, Math.floor(span(v, 0, secs) * 6));
      await page.evaluate(([cell]) => {
        const tabs = [...document.querySelectorAll('[data-tab]')];
        const want = tabs[Math.floor(cell / 2)];
        if (want && !want.classList.contains('on')) want.click();
        const cv = document.getElementById(cell % 2 ? 'near' : 'wide');
        const box = cv.closest('.stage') || cv;
        const y = box.getBoundingClientRect().top + window.scrollY;
        window.scrollTo(0, Math.max(0, Math.round(y - 8)));
      }, [cell]);
      await page.evaluate(() => window.__tick());
      await shot(page);
    }
  } else {
    // 정지 시트 — 위에서 아래로 천천히 훑는다. 스크롤은 시간의 함수라 매번 같다.
    const height = await page.evaluate(() => document.body.scrollHeight);
    for (const v of frames) {
      const u = smooth(span(v, 0.6, secs - 0.6));
      await page.evaluate(([y]) => window.scrollTo(0, y), [Math.round(u * Math.max(0, height - H))]);
      await shot(page);
    }
  }
  await page.close();
  process.stderr.write(`  ${file} — ${frames.length}프레임\n`);
}
await browser.close();
console.log(`${n}프레임 · ${outDir} · ${(n / FPS).toFixed(1)} s @ ${FPS} fps`);
