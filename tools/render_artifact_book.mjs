/* 발행 아티팩트를 한 편으로 걷는다 — 페이지 열 몇과 영상 두 편.
 *
 * 실행 (저장소 루트에서):
 *     node tools/render_artifact_book.mjs out/artifact-frames [fps] [probe]
 *     <ffmpeg> -y -framerate 15 -i out/artifact-frames/f%04d.jpg -c:v libx264 \
 *              -pix_fmt yuv420p -b:v 1100k -preset slow -movflags +faststart \
 *              out/artifact-book.mp4
 *
 * 아티팩트마다 성질이 달라 걷는 방법도 다르다.
 *   · `stills` — 무거운 3D 페이지. 정한 스크롤 위치에서 한 장씩 찍어 물린다.
 *     프레임마다 3D 를 다시 그리면 한 장에 4초가 드는데, 멈춰 선 화면은 그럴 이유가 없다
 *   · `scroll` — 문서·콘솔. 스크롤을 시간의 함수로 줘 매번 같은 영상이 나온다
 *   · `film`  — 이미 영상인 아티팩트(전체 운전 · 도면집). 그 mp4 에서 프레임을 떠 오고
 *     띠만 얹는다. 영상 아티팩트를 브라우저로 다시 찍을 수는 없다 —
 *     이 크로미움에는 H.264 디코더가 없다(`DEMUXER_ERROR_NO_SUPPORTED_STREAMS`)
 *   · `card`  — 표지·맺음. 이 파일이 직접 그린다
 *
 * 띠(자막)에는 아티팩트 제목과 **주소 앞 8자**를 적는다 — 영상만 보고도 어느 발행본인지
 * 찾아갈 수 있어야 한다.
 */
import { chromium } from 'playwright';
import { writeFileSync, copyFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const outDir = process.argv[2] || 'out/artifact-frames';
const FPS = Number(process.argv[3] || 15);
const PROBE = process.argv[4] === 'probe';
const W = 1280, H = 720;
const FFMPEG = process.env.FFMPEG
  || '/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2';
mkdirSync(outDir, { recursive: true });

const clamp01 = (u) => Math.max(0, Math.min(1, u));
const smooth = (u) => { u = clamp01(u); return u * u * (3 - 2 * u); };
const span = (v, a, b) => clamp01((v - a) / (b - a));

/* 장 — {초, 방식, 파일, 제목, 부제, 아티팩트 주소} */
const CHAPTERS = [
  { secs: 4, mode: 'card', title: '발행 아티팩트',
    sub: '태양광 패널 전처리 플랜트 · REV.58',
    lines: ['플랜트 3D 네 벌 · 운전 콘솔 · 60분 연속 운전',
            'JBR-201 도면집 · 벤더 DG-HK60 문서 · 영상 두 편'] },

  { secs: 6, mode: 'stills', file: 'out/pv-preprocess-plant-artifact.html',
    at: [0, 0.42, 0.78], title: '태양광 전처리 통합 플랜트',
    sub: '투입 · JBR · AFR · 버퍼 · DG-HK60C 직결', id: '9e171853' },

  { secs: 12, mode: 'film', file: 'out/plant.mp4', from: 0,
    title: '전처리 플랜트 전체 운전', sub: '투입에서 유리·셀모듈 반출까지 · 72초',
    id: '30acaf84' },

  { secs: 3, mode: 'stills', file: 'out/pv-preprocess-plant-c.html', at: [0, 0.42],
    title: 'C안 — 2,400×1,200 (발주처 선택)',
    sub: '병목 DGM-401 52.56 s · 여유 2.17 s · 브랜치 머리', id: '45678c2d' },
  { secs: 3, mode: 'stills', file: 'out/pv-preprocess-plant-b.html', at: [0, 0.42],
    title: 'B안 — 2,400×1,200 (벤더 상한)',
    sub: '후단 순생산 60.5 장/h · 택트 55.08 s', id: 'ffb9862d' },
  { secs: 3, mode: 'stills', file: 'out/pv-preprocess-plant-a.html', at: [0, 0.42],
    title: 'A안 — 2,500×1,400 (벤더 포락선)',
    sub: '58.5 장/h · 택트 57.0 s · 패치로 보존', id: 'e98bfb00' },

  { secs: 7, mode: 'scroll', file: 'out/pv-preprocess-console-artifact.html',
    title: 'MCR-901 운전 콘솔', sub: '설비 상태 · 인터록 · 알람 · 생산 집계',
    id: '64d5edab' },
  { secs: 8, mode: 'scroll', file: 'out/pv-preprocess-hour-artifact.html',
    title: '전처리 60분 연속 운전',
    sub: '장비별 시간 · 병목 DGM-401 · 막힌 초 0', id: '83585641' },

  { secs: 5, mode: 'scroll', file: 'out/pv-jbr-hub-artifact.html',
    title: 'JBR-201 도면집 허브', sub: '다섯 장을 한 자리에서 고른다', id: 'f3b1f4b0' },
  { secs: 10, mode: 'film', file: 'out/jbr-book.mp4', from: 0,
    title: 'JBR-201 도면집 영상', sub: '다섯 장을 고정 시간각으로 걷는다 · 66초',
    id: 'fe206738' },

  { secs: 4, mode: 'stills', file: 'docs/drawings/pv-delamination-3d.html', at: [0, 0.5],
    title: 'DG-HK60 · IR 탠덤 PV 분리설비 3D 운전 콘솔',
    sub: '벤더 원본 — 형상·치수·도장을 여기서 받아 적었다', id: '063a9784' },
  { secs: 5, mode: 'scroll', file: 'docs/dg-hk60-rfq.html',
    title: 'DG-HK60 상세설계 기술사양서 · RFQ',
    sub: '인계 경계 · 공급 범위 · 확인사항 OI', id: '377241f9' },
  { secs: 4, mode: 'scroll', file: 'docs/dg-hk60-pilot.html',
    title: 'DG-HK60C 파일럿 시험 계획서', sub: '무엇을 재서 무엇을 판정하는가',
    id: 'c4e09d98' },
  { secs: 4, mode: 'scroll', file: 'docs/dg-hk60-assembly.html',
    title: 'DG-HK60C 조립 지침서', sub: '앵커 · 정렬 · 배관 · 시운전 순서',
    id: '613c1af7' },

  { secs: 4, mode: 'card', title: '값이 움직이면 전부 따라 움직인다',
    sub: 'src/pv_preprocess 가 정본이고 도면·콘솔·문서·영상은 거기서 찍힌다',
    lines: ['시험 1,647건 · 헤드리스 검사 다섯 · JBR 검사 넷',
            'github.com/jmk4893-sys/Dynamic-industry'] },
];

/* 장 제목 띠 — 어느 발행본을 보고 있는지 화면 안에 적는다. */
function banner({ title, sub, id }) {
  const el = document.createElement('div');
  el.id = '__cap';
  el.innerHTML = '<b></b><span></span><i></i>';
  el.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;'
    + 'padding:11px 18px;background:#0e141a;border-top:1px solid #2b3947;color:#eef2f5;'
    + 'font:600 15px/1.35 system-ui,"Noto Sans KR",sans-serif;display:flex;gap:14px;'
    + 'align-items:baseline';
  el.querySelector('b').textContent = title;
  const s = el.querySelector('span');
  s.textContent = sub;
  s.style.cssText = 'font-weight:400;font-size:12.5px;opacity:.78;flex:1 1 auto';
  const a = el.querySelector('i');
  a.textContent = id ? `artifact/${id}` : '';
  a.style.cssText = 'font:500 11.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;'
    + 'font-style:normal;opacity:.55;letter-spacing:.02em';
  document.body.appendChild(el);
}

const CARD = ({ title, sub, lines }) => `<style>
html,body{margin:0;height:100%}
body{background:#0d1116;color:#eef2f5;display:grid;place-items:center;
  font:15px/1.7 system-ui,-apple-system,"Segoe UI","Noto Sans KR",sans-serif}
.c{text-align:center;max-width:860px;padding:0 40px}
h1{margin:0;font-size:42px;font-weight:650;letter-spacing:-.02em}
.s{margin:14px 0 0;font-size:17px;color:#9aa6b1}
.l{margin:30px 0 0;padding-top:22px;border-top:1px solid #2b3947;
  font:13.5px/1.9 ui-monospace,SFMono-Regular,Menlo,monospace;color:#8d99a5}
</style><div class="c"><h1>${title}</h1><p class="s">${sub}</p>
<div class="l">${(lines || []).join('<br>')}</div></div>`;

let n = 0;
const frameName = (i) => `f${String(i).padStart(4, '0')}.jpg`;
const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});

const shot = async (page) => {
  const buf = await page.screenshot({ type: 'jpeg', quality: 88 });
  writeFileSync(resolve(outDir, frameName(n)), buf);
  n += 1;
};
/* 한 장을 여러 프레임으로 물린다 — 멈춰 선 화면을 다시 그릴 이유가 없다. */
const hold = (frames) => {
  const src = resolve(outDir, frameName(n - 1));
  for (let i = 1; i < frames; i += 1) copyFileSync(src, resolve(outDir, frameName(n++)));
};

for (const ch of CHAPTERS) {
  const secs = PROBE ? Math.min(ch.secs, 1) : ch.secs;
  const total = Math.max(1, Math.round(secs * FPS));

  if (ch.mode === 'film') {
    // 영상 아티팩트는 그 mp4 에서 뜬다. 띠는 투명 PNG 로 얹는다.
    const bar = resolve(outDir, '_bar.png');
    const bp = await browser.newPage({ viewport: { width: W, height: H } });
    await bp.setContent('<style>html,body{margin:0;background:transparent}</style>');
    await bp.evaluate(banner, { title: ch.title, sub: ch.sub, id: ch.id });
    const box = await bp.locator('#__cap').boundingBox();
    writeFileSync(bar, await bp.locator('#__cap').screenshot({ type: 'png' }));
    await bp.close();
    execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-ss', String(ch.from || 0),
      '-t', String(secs), '-i', resolve(ch.file), '-i', bar,
      '-filter_complex', `[0:v]fps=${FPS},scale=${W}:${H}[v];[v][1:v]overlay=0:${H - Math.round(box.height)}`,
      '-q:v', '3', '-start_number', String(n), resolve(outDir, 'f%04d.jpg')]);
    n += total;
    process.stderr.write(`  ${ch.file} — ${total}프레임 (film)\n`);
    continue;
  }

  const page = await browser.newPage({ viewport: { width: W, height: H } });
  if (ch.mode === 'card') {
    await page.setContent(CARD(ch));
    await page.waitForTimeout(300);
    await shot(page); hold(total);
  } else {
    await page.goto('file://' + resolve(ch.file));
    await page.waitForTimeout(ch.mode === 'stills' ? 3200 : 1400);
    await page.evaluate(banner, { title: ch.title, sub: ch.sub, id: ch.id });
    const height = await page.evaluate(() => document.body.scrollHeight);
    const deep = Math.max(0, height - H);
    if (ch.mode === 'stills') {
      const cuts = ch.at.length;
      for (let i = 0; i < cuts; i += 1) {
        await page.evaluate((y) => window.scrollTo(0, y), Math.round(ch.at[i] * deep));
        await page.waitForTimeout(900);
        await shot(page);
        const want = Math.round(total * (i + 1) / cuts) - Math.round(total * i / cuts);
        hold(want);
      }
    } else {
      for (let i = 0; i < total; i += 1) {
        const u = smooth(span(i / FPS, 0.5, secs - 0.5));
        await page.evaluate((y) => window.scrollTo(0, y), Math.round(u * deep));
        await shot(page);
      }
    }
  }
  await page.close();
  process.stderr.write(`  ${ch.file || 'card'} — ${total}프레임 (${ch.mode})\n`);
}
await browser.close();
console.log(`${n}프레임 · ${outDir} · ${(n / FPS).toFixed(1)} s @ ${FPS} fps`);
