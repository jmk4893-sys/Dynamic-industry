/* 추출한 벡터가 원본 아트워크와 같은 그림인가 — 픽셀로 잰다.
 *
 * 마크를 "눈으로 보니 같다" 로 넘기면, 어느 판에서 좌표 하나가 틀려도 아무도
 * 모른다. 그래서 두 그림을 같은 크기로 래스터화해 픽셀을 직접 센다.
 *
 *   원본 : symbol_100x100mm.ai 를 PyMuPDF 로 렌더 (tools/render_brand_reference.py)
 *   추출 : src/pv_preprocess/brand.py 의 경로를 Chromium 이 SVG 로 렌더
 *
 * Chromium 을 쓰는 이유는 그것이 **실제로 이 마크를 그릴 엔진**이기 때문이다.
 * 콘솔 SVG 도 3D 캔버스 텍스처도 브라우저가 그린다. 별도 래스터라이저로 재면
 * "라이브러리끼리는 같다"만 확인하고 정작 화면은 확인하지 못한다.
 *
 * 판정은 둘이다.
 *   ① 색 일치 — 각 픽셀의 RGB 거리가 TOL 안인가
 *   ② 도형 일치 — 잉크(비백색) 영역의 IoU. 색이 맞아도 형상이 밀리면 여기서 걸린다
 *
 * 경계 픽셀은 안티에일리어싱 방식이 달라 반드시 어긋난다(원본은 PDF 래스터라이저,
 * 이쪽은 브라우저). 그래서 잉크 영역을 **안쪽으로 침식해** 색을 보고, 경계 자체는
 * IoU 로 본다. 침식 2 px 에서 요구하는 것은 허용오차가 아니라 **완전일치**다 —
 * 색이 맞다면 한 바이트도 달라서는 안 되기 때문이다.
 *
 * 남는 어긋남이 안티에일리어싱인지 좌표 어긋남인지는 해상도를 바꿔 보면 갈린다.
 * 안티에일리어싱이면 경계 픽셀 수가 둘레(∝N)에 비례하고 전체는 면적(∝N²)이라
 * 불일치 비율이 1/N 로 준다. 좌표가 밀렸으면 해상도를 올려도 비율이 안 준다.
 *
 * 실행:  node tools/check_brand_fidelity.mjs [원본.png]
 */
import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { execFileSync } from 'node:child_process';

const REF = process.argv[2] || 'out/brand-reference.png';
const TOL = 12;          // 침식 1 px 에서의 픽셀당 허용 RGB 거리
const MIN_COLOUR = 0.99; // 침식 1 px 색 일치율 하한
const MIN_IOU = 0.99;    // 도형 IoU 하한
const EXACT_ERODE = 2;   // 이만큼 안쪽은 완전일치여야 한다

if (!existsSync(REF)) {
  // 대조용 PNG 는 산출물이라 저장소에 두지 않는다. 원본 아트워크는 저장소에
  // 있으므로 없으면 여기서 찍는다 — 새로 받은 사본에서도 그냥 돌아가야 한다.
  const art = JSON.parse(execFileSync('python3', ['-c',
    "import json,sys; sys.path.insert(0,'src')\n"
    + 'from pv_preprocess import brand; print(json.dumps(brand.SOURCE_PATH))'],
    { encoding: 'utf8' }));
  if (!existsSync(art)) {
    console.error(`✗ 원본 아트워크가 없다: ${art}`);
    process.exit(2);
  }
  mkdirSync(dirname(REF), { recursive: true });
  execFileSync('python3', ['tools/render_brand_reference.py', art, REF], { stdio: 'inherit' });
}

/** brand.py 에서 경로와 색을 그대로 읽어 온다 — 여기서 다시 적지 않는다. */
const brand = JSON.parse(execFileSync('python3', ['-c', `
import json, sys
sys.path.insert(0, 'src')
from pv_preprocess import brand
print(json.dumps({
    'viewW': brand.VIEW_W, 'viewH': brand.VIEW_H,
    'paths': [{'d': s.d, 'fill': s.colour} for s in brand.SHAPES],
}))`], { encoding: 'utf8' }));

const png = readFileSync(resolve(REF));
const browser = await chromium.launch({ args: ['--force-device-scale-factor=1'] });
const page = await browser.newPage();

// 원본 크기를 브라우저에서 읽고, 같은 크기로 SVG 를 그린다.
const size = await page.evaluate(async (b64) => {
  const img = new Image();
  img.src = 'data:image/png;base64,' + b64;
  await img.decode();
  return { w: img.naturalWidth, h: img.naturalHeight };
}, png.toString('base64'));

const result = await page.evaluate(async ([b64, brand, size, tol, exactErode]) => {
  const draw = async (src, w, h) => {
    const img = new Image();
    img.src = src;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const g = c.getContext('2d', { willReadFrequently: true });
    g.fillStyle = '#ffffff';
    g.fillRect(0, 0, w, h);
    g.drawImage(img, 0, 0, w, h);
    return g.getImageData(0, 0, w, h).data;
  };

  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + size.w
    + '" height="' + size.h + '" viewBox="0 0 ' + brand.viewW + ' ' + brand.viewH + '">'
    + brand.paths.map((p) => '<path fill="' + p.fill + '" d="' + p.d + '"/>').join('')
    + '</svg>';

  const a = await draw('data:image/png;base64,' + b64, size.w, size.h);
  const b = await draw('data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg))),
                       size.w, size.h);

  const n = size.w * size.h;
  const inkA = new Uint8Array(n), inkB = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const o = i * 4;
    inkA[i] = (a[o] < 245 || a[o + 1] < 245 || a[o + 2] < 245) ? 1 : 0;
    inkB[i] = (b[o] < 245 || b[o + 1] < 245 || b[o + 2] < 245) ? 1 : 0;
  }
  // 잉크 영역 침식 — 경계 안티에일리어싱을 색 판정에서 뺀다
  const erode = (src, times) => {
    let cur = src;
    for (let s = 0; s < times; s++) {
      const nx = new Uint8Array(n);
      for (let y = 1; y < size.h - 1; y++) {
        for (let x = 1; x < size.w - 1; x++) {
          const i = y * size.w + x;
          nx[i] = (cur[i] && cur[i - 1] && cur[i + 1]
            && cur[i - size.w] && cur[i + size.w]) ? 1 : 0;
        }
      }
      cur = nx;
    }
    return cur;
  };
  const inner = erode(inkA, 1);
  const core = erode(inkA, exactErode);

  let coreChecked = 0, coreSame = 0, coreWorst = 0;
  for (let i = 0; i < n; i++) {
    if (!core[i]) continue;
    const o = i * 4;
    const d = Math.hypot(a[o] - b[o], a[o + 1] - b[o + 1], a[o + 2] - b[o + 2]);
    coreChecked++;
    if (d === 0) coreSame++;
    else coreWorst = Math.max(coreWorst, d);
  }

  let inter = 0, union = 0, checked = 0, same = 0, worst = 0;
  const off = new Map();
  for (let i = 0; i < n; i++) {
    if (inkA[i] || inkB[i]) union++;
    if (inkA[i] && inkB[i]) inter++;
    if (!inner[i]) continue;
    const o = i * 4;
    const d = Math.hypot(a[o] - b[o], a[o + 1] - b[o + 1], a[o + 2] - b[o + 2]);
    checked++;
    if (d <= tol) same++;
    else {
      worst = Math.max(worst, d);
      const key = [a[o], a[o + 1], a[o + 2], b[o], b[o + 1], b[o + 2]].join(',');
      off.set(key, (off.get(key) || 0) + 1);
    }
  }
  return {
    w: size.w, h: size.h, pixels: n,
    inkA: inkA.reduce((s, v) => s + v, 0), inkB: inkB.reduce((s, v) => s + v, 0),
    inter, union, checked, same, worst: +worst.toFixed(1),
    coreChecked, coreSame, coreWorst: +coreWorst.toFixed(1),
    off: [...off.entries()].sort((p, q) => q[1] - p[1]).slice(0, 4),
  };
}, [png.toString('base64'), brand, size, TOL, EXACT_ERODE]);

await browser.close();

const colour = result.same / result.checked;
const iou = result.inter / result.union;
console.log(`원본 ${result.w} × ${result.h} px · 잉크 원본 ${result.inkA.toLocaleString()} `
  + `· 추출 ${result.inkB.toLocaleString()}`);
console.log(`도형 IoU        ${(iou * 100).toFixed(3)} %   (교집합 ${result.inter.toLocaleString()} / 합집합 ${result.union.toLocaleString()})`);
console.log(`색 일치         ${(colour * 100).toFixed(3)} %   (경계 1 px 침식 후 ${result.checked.toLocaleString()} px 중 ${result.same.toLocaleString()})`);
if (result.checked > result.same) {
  console.log(`  최대 RGB 거리 ${result.worst}`);
  for (const [k, c] of result.off) {
    const v = k.split(',').map(Number);
    console.log(`  원본 #${v.slice(0, 3).map((x) => x.toString(16).padStart(2, '0')).join('')}`
      + ` ↔ 추출 #${v.slice(3).map((x) => x.toString(16).padStart(2, '0')).join('')}  ${c} px`);
  }
}

const core = result.coreSame / result.coreChecked;
console.log(`내부 완전일치    ${(core * 100).toFixed(4)} %   `
  + `(${EXACT_ERODE} px 침식 후 ${result.coreChecked.toLocaleString()} px 중 `
  + `${result.coreSame.toLocaleString()} · 최대거리 ${result.coreWorst})`);

if (core < 1) {
  console.error(`\n✗ 안쪽 ${EXACT_ERODE} px 에서 색이 어긋난다 — 경계 문제가 아니라 `
    + '채움 색이 다르다는 뜻이다');
  process.exit(1);
}
if (iou < MIN_IOU || colour < MIN_COLOUR) {
  console.error(`\n✗ 일치율 미달 — 도형 ${(iou * 100).toFixed(3)} % (하한 ${MIN_IOU * 100}) `
    + `· 색 ${(colour * 100).toFixed(3)} % (하한 ${MIN_COLOUR * 100})`);
  process.exit(1);
}
console.log(`\n✓ 추출 벡터가 원본과 일치한다 — 도형 ${(iou * 100).toFixed(3)} % · `
  + `색 ${(colour * 100).toFixed(3)} % · 내부 완전일치 ${(core * 100).toFixed(4)} % `
  + '(남는 차이는 두 래스터라이저의 경계 처리)');
