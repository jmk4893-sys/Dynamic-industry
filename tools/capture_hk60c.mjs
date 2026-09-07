/* DG-HK60C 유리제거기 — 벤더 콘솔의 **그리기 호출을 그대로 받아 적는다**.
 *
 * 플랜트 도면의 후단 기계는 REV.54 까지 `build_dgm.py` 가 hk60c 치수에서 **다시
 * 그린** 것이었다. 치수는 맞았지만 형상도 도장도 벤더 콘솔과 달랐다 — 같은
 * 기계가 두 화면에서 다르게 보였다. 여기서는 벤더 콘솔(`pv-delamination-3d.html`)
 * 을 헤드리스로 열고 그 소프트웨어 렌더러의 `box`/`cylinder`/`poly`/`label3`
 * 호출을 가로채, 벤더가 그린 부품을 좌표·치수·도장색 그대로 받아 적는다.
 *
 *   node tools/capture_hk60c.mjs [--stage 4] [--phase 0.55]
 *
 * 받아 적는 것은 **압축 배치**(`compactMachine`/`compactDynamic`) 다 — 그것이 납품
 * 기계이고, `hk60c.LENGTH_MM` 도 콘솔의 `compactLength()` 에서 온다. 확장 배치
 * (`baseMachine`)는 벤더가 하류 설비까지 펼쳐 놓은 참조 도면이라 인도 범위가 아니다.
 *
 * 산출물은 `docs/drawings/hk60c-capture.json` 이고 `tools/build_dgm.py` 가 읽는다.
 * 손으로 고치지 않는다 — 벤더 콘솔이 바뀌면 이것을 다시 돌린다.
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';

const arg = (k, d) => {
  const i = process.argv.indexOf(k);
  return i > 0 && process.argv[i + 1] !== undefined ? process.argv[i + 1] : d;
};
const STAGE = Number(arg('--stage', 4));      // 정지 자세 — 4 = HKB/HKS 탠덤 박리 중
const PHASE = Number(arg('--phase', 0.55));   // 그 단계 안의 진행률
const SRC = resolve('docs/drawings/pv-delamination-3d.html');
const OUT = resolve('docs/drawings/hk60c-capture.json');

/* 후크 — 프리미티브 함수를 **정의된 뒤에 감싼다.** 함수 선언은 같은 스코프의
   바인딩을 공유하므로, 이름을 다시 묶으면 이미 작성된 모든 그리기 코드가 감싼
   쪽을 부른다. box/cylinder 는 자기 면을 poly 로 그리므로 그동안 깊이를 세어
   같은 부품을 두 번 적지 않는다. 좌표는 콘솔 자신의 world() 로 옮긴다. */
const WRAP = `
    (function(){
      if(!globalThis.__CAP)return;
      const ob=box,oc=cylinder,op=poly,ol=label3,r4=v=>+v.toFixed(4);
      box=function(center,size,color,opt={}){
        const w=world(center);
        if(!__CAP.depth)__CAP.list.push({t:'b',c:[r4(w.x),r4(w.y),r4(w.z)],
          s:[r4(size.x),r4(size.y),r4(size.z)],k:color,a:+(opt.alpha??1).toFixed(3),
          r:[opt.rx||0,opt.ry||0,opt.rz||0]});
        __CAP.depth++;try{return ob(center,size,color,opt)}finally{__CAP.depth--}
      };
      cylinder=function(center,radius,length,axis,color,segments=10,opt={}){
        const w=world(center);
        if(!__CAP.depth)__CAP.list.push({t:'c',c:[r4(w.x),r4(w.y),r4(w.z)],r:r4(radius),
          l:r4(length),x:axis,k:color,a:+(opt.alpha??1).toFixed(3),g:segments});
        __CAP.depth++;try{return oc(center,radius,length,axis,color,segments,opt)}finally{__CAP.depth--}
      };
      poly=function(points,color,alpha=1,stroke=null,lineWidth=1,opt){
        if(!__CAP.depth&&points.length>2){const w=points.map(q=>world(q));
          __CAP.list.push({t:'p',v:w.map(q=>[r4(q.x),r4(q.y),r4(q.z)]),k:color,a:+(alpha??1).toFixed(3)});}
        return op(points,color,alpha,stroke,lineWidth,opt);
      };
      label3=function(text,p,color=C.white){
        const w=world(p);__CAP.labels.push({t:text,p:[+w.x.toFixed(3),+w.y.toFixed(3),+w.z.toFixed(3)]});
        return ol(text,p,color);
      };
      globalThis.__HK={compactMachine,compactDynamic,compactLength,C,MATS,PANEL_L,PANEL_W,layout:()=>layoutId};
    })();
`;

const html = readFileSync(SRC, 'utf8');
const open = html.indexOf('<script>\n  (()=>{');
const close = html.indexOf('</script>', open);
if (open < 0 || close < 0) { console.error('✗ 콘솔 스크립트 블록을 찾지 못했다'); process.exit(2); }
let js = html.slice(open + '<script>'.length, close);
const tail = js.lastIndexOf('})();');
if (tail < 0) { console.error('✗ 콘솔 IIFE 의 끝을 찾지 못했다'); process.exit(2); }
js = js.slice(0, tail) + WRAP + js.slice(tail);

const dir = mkdtempSync(join(tmpdir(), 'hk60c-'));
const probe = join(dir, 'probe.html');
writeFileSync(probe, html.slice(0, open) + '<script>' + js + html.slice(close));

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
await page.addInitScript(() => { window.__CAP = { list: [], labels: [], depth: 0 }; });
await page.goto('file://' + probe, { waitUntil: 'load' });
await page.waitForTimeout(2000);

const cap = await page.evaluate(([stage, phase]) => {
  const H = window.__HK;
  if (!H) return { error: '__HK 훅이 없다 — 콘솔 스크립트가 끝까지 돌지 않았다' };
  const run = (fn) => {
    __CAP.list = []; __CAP.labels = []; __CAP.depth = 0;
    fn();
    return { parts: __CAP.list.slice(), labels: __CAP.labels.slice() };
  };
  if (H.layout() === 'rev20') return { error: "콘솔이 확장 배치('rev20')로 열렸다 — 납품 기계는 압축 배치다" };
  const base = run(() => H.compactMachine());
  const dyn = run(() => H.compactDynamic(stage, phase));
  return {
    base, dyn,
    palette: Object.fromEntries(Object.entries(H.C)),
    finish: Object.fromEntries(Object.entries(H.MATS)),
    panel: [H.PANEL_L, H.PANEL_W], length_m: H.compactLength(), layout: H.layout(),
  };
}, [STAGE, PHASE]);
await browser.close();

if (cap.error) { console.error('✗ ' + cap.error); process.exit(2); }
if (errs.length) console.error('  페이지 오류: ' + errs.slice(0, 3).join(' | '));

const parts = [...cap.base.parts, ...cap.dyn.parts];
const labels = [...cap.base.labels, ...cap.dyn.labels];
const box = { lo: [1e9, 1e9, 1e9], hi: [-1e9, -1e9, -1e9] };
const pts = (p) => (p.t === 'p' ? p.v
  : p.t === 'b' ? [[p.c[0] - p.s[0] / 2, p.c[1] - p.s[1] / 2, p.c[2] - p.s[2] / 2],
                   [p.c[0] + p.s[0] / 2, p.c[1] + p.s[1] / 2, p.c[2] + p.s[2] / 2]]
  : [[p.c[0] - (p.x === 'x' ? p.l / 2 : p.r), p.c[1] - (p.x === 'y' ? p.l / 2 : p.r), p.c[2] - (p.x === 'z' ? p.l / 2 : p.r)],
     [p.c[0] + (p.x === 'x' ? p.l / 2 : p.r), p.c[1] + (p.x === 'y' ? p.l / 2 : p.r), p.c[2] + (p.x === 'z' ? p.l / 2 : p.r)]]);
for (const p of parts) for (const v of pts(p)) for (let k = 0; k < 3; k++) {
  box.lo[k] = Math.min(box.lo[k], v[k]); box.hi[k] = Math.max(box.hi[k], v[k]);
}

const out = {
  source: 'docs/drawings/pv-delamination-3d.html',
  note: '벤더 콘솔의 그리기 호출을 그대로 받아 적은 것. tools/capture_hk60c.mjs 가 만든다.',
  stage: STAGE, phase: PHASE,
  axes: '기계 좌표 · x 공정방향 · y 좌(+)/우(−) · z 상향 · 1 = 1 m',
  panel_m: cap.panel, layout: cap.layout, length_m: +cap.length_m.toFixed(3),
  bbox: { lo: box.lo.map((v) => +v.toFixed(3)), hi: box.hi.map((v) => +v.toFixed(3)) },
  palette: cap.palette, finish: cap.finish,
  counts: { base: cap.base.parts.length, dynamic: cap.dyn.parts.length, labels: labels.length },
  base: cap.base.parts, dynamic: cap.dyn.parts, labels,
};
writeFileSync(OUT, JSON.stringify(out));
const by = {};
for (const p of parts) by[p.t] = (by[p.t] || 0) + 1;
console.log(`${OUT.split('/').slice(-1)[0]} — 고정 ${cap.base.parts.length} · 동적(${STAGE}단계 ${PHASE}) ${cap.dyn.parts.length}`
  + ` · 라벨 ${labels.length} · 상자 ${by.b || 0} 원통 ${by.c || 0} 판 ${by.p || 0}`);
console.log(`  포락 x ${box.lo[0].toFixed(2)}…${box.hi[0].toFixed(2)} · y ${box.lo[1].toFixed(2)}…${box.hi[1].toFixed(2)} · z ${box.lo[2].toFixed(2)}…${box.hi[2].toFixed(2)} (m)`);
