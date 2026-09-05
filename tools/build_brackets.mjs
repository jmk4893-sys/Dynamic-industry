/* 지지 브래킷 재생성 — 뜬 덩어리를 가장 가까운 부재에 매단다.
 *
 * REV.45 까지 이 51본은 씬에 **월드 좌표 리터럴**로 박혀 있었고, 만든 도구는
 * 저장소에 없었다. 그래서 셀을 하나라도 옮기면 브래킷이 옛 자리에 남아 하중
 * 경로가 끊겼다 — A-2b 첫 시도에서 실제로 12본이 그렇게 떴다. 형상을 옮길 수
 * 없는 도면은 고칠 수 없는 도면이다.
 *
 * 방법은 `check_load_path.mjs` 와 같다. 브래킷을 뺀 채 메시를 인접 허용치로
 * 묶어 접지 안 되는 덩어리를 찾고, 각 덩어리에서 이미 접지된 부재까지의 최단
 * 틈을 재어 그 틈을 딱 채우는 브래킷을 낸다. 채운 뒤 다시 세어 남는 덩어리가
 * 없을 때까지 반복한다 — 한 번에 다 닿지는 않기 때문이다.
 *
 * 실행 (저장소 루트에서):
 *     node tools/build_brackets.mjs            # 도면에 다시 써 넣는다
 *     node tools/build_brackets.mjs --dry      # 세어만 본다
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { readFileSync, writeFileSync } from 'node:fs';

const FILE = 'docs/drawings/pv-preprocess-plant.html';
const DRY = process.argv.includes('--dry');

const BEGIN = '/* @brackets-begin */';
const END = '/* @brackets-end */';

/** 받칠 대상이 아닌 것 — mounting.UNSUPPORTED_BY_DESIGN 과 같다. */
const EXEMPT = [
  '이송 중 태양광 패널', 'VS-101 검출 정션박스 형상', 'VS-101A/B-FUSED 고정면 스캔선',
  'CRN-901', 'CMP-701 압축공기 주관',
];

/** 브래킷이 들어가면 안 되는 X 부피 — mounting.BRACKET_KEEP_OUT 과 같아야 한다.
 *
 * "가장 가까운 접지 부재에 매단다" 는 규칙은 움직이는 것 옆에서 틀린다. 그 자리에
 * 부재가 있다는 것과 그 자리가 늘 비어 있다는 것은 다른 말이다. 옛 MB-021·022 가
 * BFC 셔틀 레일을 최근접 부재에 물리려다 팔레트 승강 경로 한가운데 섰고, 간섭
 * 스윕이 잡았다. 그 자리는 팔레트 발자국 밖의 지지 포스트가 받는다. */
const KEEP_OUT = [
  ['LFT-101A 팔레트 승강 경로', -22.45, -18.85, 0.2, 1.95],
  ['LFT-101B 팔레트 승강 경로', -21.85, -18.85, 0.2, 1.95],
];

const ADJ = 0.03;      // 인접 판정 (m)
const FLOOR = 0.05;    // 이 아래면 접지
const MAX_SPAN = 0.75; // 브래킷 하나가 건널 수 있는 최대 틈 (m)

const src = readFileSync(FILE, 'utf8');
const b0 = src.indexOf(BEGIN);
const b1 = src.indexOf(END);
if (b0 < 0 || b1 < 0) { console.error(`✗ ${BEGIN} … ${END} 표식을 찾지 못했다`); process.exit(1); }

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.goto('file://' + resolve(FILE), { waitUntil: 'load' });
await page.waitForTimeout(3400);

const found = await page.evaluate(([exempt, adj, floor, maxSpan, keepOut]) => {
  const host = document.getElementById('jb-removal-operation');
  if (!host || !host.__pvScene) return { error: '3D 장면 훅(__pvScene)을 찾지 못했다' };
  const items = [];
  host.__pvScene.scene.traverse((o) => {
    if (!o.isMesh || !o.geometry) return;
    const label = (o.userData && o.userData.label) || '';
    if (label.includes('지지 브래킷')) return;          // 자기 자신은 빼고 본다
    o.updateWorldMatrix(true, false);
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    const bb = o.geometry.boundingBox;
    let lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    for (let i = 0; i < 8; i++) {
      const v = new bb.min.constructor(
        i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y, i & 4 ? bb.max.z : bb.min.z,
      ).applyMatrix4(o.matrixWorld);
      lo = [Math.min(lo[0], v.x), Math.min(lo[1], v.y), Math.min(lo[2], v.z)];
      hi = [Math.max(hi[0], v.x), Math.max(hi[1], v.y), Math.max(hi[2], v.z)];
    }
    items.push({ label, lo, hi });
  });

  const isExempt = (i) => exempt.some((k) => items[i].label.includes(k));
  const gapAxis = (A, B, k) => Math.max(A.lo[k] - B.hi[k], B.lo[k] - A.hi[k], 0);
  const gap3 = (A, B) => Math.hypot(gapAxis(A, B, 0), gapAxis(A, B, 1), gapAxis(A, B, 2));

  const out = [];
  const extra = [];   // 이번 회차에 새로 만든 브래킷 (다음 회차의 연결로 쓴다)
  for (let round = 0; round < 6; round++) {
    const all = items.concat(extra);
    const n = all.length;
    const par = Array.from({ length: n }, (_, i) => i);
    const find = (a) => { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; };
    const uni = (a, b) => { a = find(a); b = find(b); if (a !== b) par[a] = b; };
    const touch = (A, B) => {
      for (let k = 0; k < 3; k++) if (A.lo[k] - adj > B.hi[k] || B.lo[k] - adj > A.hi[k]) return false;
      return true;
    };
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) if (touch(all[i], all[j])) uni(i, j);
    const grounded = new Set();
    for (let i = 0; i < n; i++) if (all[i].lo[1] <= floor) grounded.add(find(i));

    const groups = new Map();
    for (let i = 0; i < n; i++) {
      if (i < items.length && isExempt(i)) continue;
      const r = find(i);
      if (grounded.has(r)) continue;
      if (!groups.has(r)) groups.set(r, []);
      groups.get(r).push(i);
    }
    if (!groups.size) return { out, rounds: round };

    let made = 0;
    for (const [, members] of groups) {
      // 예외만으로 이루어진 덩어리는 건너뛴다
      if (members.every((i) => i < items.length && isExempt(i))) continue;
      let best = null;
      for (const i of members) {
        for (let j = 0; j < n; j++) {
          if (find(j) === find(i)) continue;
          if (j < items.length && isExempt(j)) continue;
          if (!grounded.has(find(j))) continue;
          const g = gap3(all[i], all[j]);
          if (g > maxSpan) continue;
          // 브래킷이 앉을 자리(두 상자 사이)가 금지 부피에 걸리면 그 짝은 버린다
          const mid = (k) => (Math.max(Math.min(all[i].hi[k], all[j].hi[k]), Math.min(all[i].lo[k], all[j].lo[k]))
                     + Math.min(Math.max(all[i].lo[k], all[j].lo[k]), Math.max(all[i].hi[k], all[j].hi[k]))) / 2;
          const mx = mid(0), my = mid(1);
          if (keepOut.some(([, x0, x1, y0, y1]) => mx > x0 && mx < x1 && my > y0 && my < y1)) continue;
          if (!best || g < best.g) best = { g, i, j };
        }
      }
      if (!best) continue;
      const A = all[best.i], B = all[best.j];
      // 두 상자를 잇는 최소 직육면체 — 축마다 겹치면 겹친 구간, 떨어지면 그 틈
      const size = [0, 0, 0], at = [0, 0, 0];
      for (let k = 0; k < 3; k++) {
        const lo = Math.max(Math.min(A.hi[k], B.hi[k]), Math.min(A.lo[k], B.lo[k]));
        const hi = Math.min(Math.max(A.lo[k], B.lo[k]), Math.max(A.hi[k], B.hi[k]));
        const a = Math.min(lo, hi), b = Math.max(lo, hi);
        size[k] = Math.max(b - a, 0.06);
        at[k] = (a + b) / 2;
      }
      out.push({ size, at, a: A.label || '(무명)', b: B.label || '(무명)', gap: best.g });
      extra.push({ label: '', lo: [at[0] - size[0] / 2, at[1] - size[1] / 2, at[2] - size[2] / 2],
                   hi: [at[0] + size[0] / 2, at[1] + size[1] / 2, at[2] + size[2] / 2] });
      made++;
    }
    if (!made) return { out, rounds: round, stuck: groups.size };
  }
  return { out, rounds: 6, stuck: -1 };
}, [EXEMPT, ADJ, FLOOR, MAX_SPAN, KEEP_OUT]);
await browser.close();

if (found.error) { console.error('✗ ' + found.error); process.exit(1); }
const { out } = found;
const f = (v) => v.toFixed(3);
const lines = out.map((r, i) => {
  const no = String(i + 1).padStart(3, '0');
  return `L([${r.size.map(f).join(',')}],[${r.at.map(f).join(',')}],M.steel,`
    + `'MB-${no} 지지 브래킷','${r.a} → ${r.b}');`;
});

console.log(`브래킷 ${out.length}본 · 반복 ${found.rounds}회`
  + (found.stuck ? ` · 못 매단 덩어리 ${found.stuck}` : ''));
if (out.length) {
  const g = out.map((r) => r.gap);
  console.log(`틈 ${(Math.min(...g) * 1000).toFixed(0)} … ${(Math.max(...g) * 1000).toFixed(0)} mm`);
}
if (DRY) process.exit(found.stuck ? 1 : 0);

const body = '\n// 손으로 쓰지 않는다 — tools/build_brackets.mjs 가 실측 틈에서 낸다.\n'
  + lines.join('\n') + '\n';
writeFileSync(FILE, src.slice(0, b0 + BEGIN.length) + body + src.slice(b1), 'utf8');
console.log(`${FILE} — 브래킷 블록 ${lines.length}줄 재생성`);
if (found.stuck) process.exit(1);
