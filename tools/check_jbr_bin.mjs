/* 수거함이 몇 장째에 차는가 — 물리엔진으로 잰다.
 *
 * 산술은 상한만 준다: 90 L ÷ 3.47 L = 26 개, 완전 충전이라는 낙관이다. 실제로는
 * 박스가 굴러 눕는 자세가 쌓임을 정하고, 그것은 적분해야 나온다. 그래서 물리 화면을
 * 실제로 열어 한 장이 끝나도 수거함을 비우지 않고 다음 장을 넣는다 — 더미가 테두리에
 * 닿거나 박스가 밖으로 나가는 장수가 답이다.
 *
 * 엔진은 결정적이라(고정 시간각 · 난수 없음) 값이 재현된다. 그 값을
 * `jbr_analysis.BIN_ENGINE` 이 거울로 들고 있고, 여기서 다시 재서 대조한다 — 거울이
 * 낡으면 실패하고 새 값을 알려 준다. **거울을 손으로 고치지 말 것.**
 *
 * 여기서 보는 것 셋:
 *   · **엔진이 맞게 푸는가** — 자유낙하 닫힌 해와 2 % 안
 *   · **첫 장은 3/3 이 들어가는가** — 영상 검사와 같은 조건 (REV.59 의 640 회귀)
 *   · **몇 장째에 차는가** — 거울과 같은가, 산술 상한 아래인가
 *
 * 실행 (저장소 루트에서):
 *     node tools/check_jbr_bin.mjs [docs/drawings/pv-jbr-physics.html]
 */
import { chromium } from 'playwright';
import { browserPath } from './pw_browser.mjs';
import { resolve } from 'node:path';

const file = process.argv[2] || 'docs/drawings/pv-jbr-physics.html';
const MAX_PANELS = 40;

const browser = await chromium.launch({ executablePath: browserPath() });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForFunction(() => window.PH !== undefined && window.PH.nextPanel !== undefined);

const chk = await page.evaluate(() => window.PH.check());
console.log(`자유낙하 대조: 모의 ${chk.simulated.toFixed(4)} s · 해석 ${chk.exact.toFixed(4)} s · 오차 ${(chk.error * 100).toFixed(2)} %`);
if (!(chk.error < 0.02)) {
  console.error('✗ 물리엔진이 닫힌 해와 2 % 안에서 안 맞는다');
  await browser.close(); process.exit(1);
}

const out = await page.evaluate((MAX) => {
  const PH = window.PH;
  PH.pause(); PH.reset();
  const fps = SCENE.fps;
  const rows = [];
  for (let panel = 1; panel <= MAX; panel++) {
    while (PH.state().t <= PH.total) PH.advance(1 / fps);
    const bs = PH.binState();
    rows.push({ panel, boxes: bs.boxes, inside: bs.inside, escaped: bs.escaped,
                fill: bs.fillM, wall: bs.wallM, full: bs.full });
    if (bs.full) break;
    PH.nextPanel();
  }
  return { rows, mirror: NUM.bin, inner: SCENE.bin.inner, wall: SCENE.bin.wallH, boxL: NUM.bin.box_l };
}, MAX_PANELS);
const SCENE_WALL = out.wall;

await browser.close();
if (errors.length) { console.error(`✗ 페이지 오류 ${errors.length}건 — 첫 줄: ${errors[0]}`); process.exit(1); }

console.log('\n  장   박스   안   밖   채움 mm   (테두리 ' + (out.rows[0].wall * 1000).toFixed(0) + ')');
for (const r of out.rows) {
  console.log(`  ${String(r.panel).padStart(2)}   ${String(r.boxes).padStart(3)}  ${String(r.inside).padStart(3)}  ${String(r.escaped).padStart(3)}   ${(r.fill * 1000).toFixed(0).padStart(6)}${r.full ? '   ← 만재' : ''}`);
}

let bad = 0;
const first = out.rows[0];
if (first.inside !== first.boxes || first.escaped !== 0) {
  console.error(`✗ 첫 장에서 ${first.inside}/${first.boxes} — 수거함 치수가 다시 어긋났다`); bad++;
}
const last = out.rows[out.rows.length - 1];
if (!last.full) { console.error(`✗ ${MAX_PANELS} 장을 넣어도 안 찼다 — binState 판정을 다시 본다`); bad++; }

/* 찬 시점: 마지막 장은 넘친 장이다. 「받아 낸 장수」는 그 앞까지다. */
const held = last.full ? last.panel - 1 : last.panel;
const heldRow = out.rows[Math.max(0, held - 1)];
const packing = heldRow.inside * out.boxL / 1000 / (out.inner[0] * out.inner[1] * Math.max(heldRow.fill, 1e-6));
console.log(`\n  받아 낸 것 ${held} 장 · ${heldRow.inside} 개 · 채움 ${(heldRow.fill * 1000).toFixed(0)} mm · 충전율 ${(packing * 100).toFixed(0)} %`);
console.log(`  부품표 명목 90 L 로는 ${out.mirror.dense_panels} 장 · 기하 상한(테두리까지 완전 충전) ${out.mirror.gross_panels} 장 · 거울 ${out.mirror.engine_panels} 장`);

/* 관통이 있으면 기하 상한을 넘는다 — 그것이 엔진이 틀렸다는 신호다. */
if (held > out.mirror.gross_panels + 0.5) {
  console.error(`✗ 실측 ${held} 장이 기하 상한 ${out.mirror.gross_panels} 을 넘는다 — 박스가 겹쳐 들어갔다(관통)`); bad++;
}
const mi = out.mirror.inner_m;
if (Math.abs(mi[0] - out.inner[0]) > 1e-4 || Math.abs(mi[1] - out.inner[1]) > 1e-4 || Math.abs(mi[2] - SCENE_WALL) > 1e-4) {
  console.error(`✗ 안치수 거울이 다르다 — jbr_analysis.BIN_INNER_M 을 (${out.inner[0]}, ${out.inner[1]}, ${SCENE_WALL}) 으로`); bad++;
}
const want = { panels: held, boxes: heldRow.inside, fill_m: Number(heldRow.fill.toFixed(3)) };
const m = out.mirror;
if (m.engine_panels !== want.panels || m.engine_boxes !== want.boxes
    || Math.abs(m.engine_fill_m - want.fill_m) > 0.0015) {
  console.error(`✗ 거울이 다르다 — jbr_analysis.BIN_ENGINE 을 ${JSON.stringify(want)} 으로 (지금 `
    + `{panels: ${m.engine_panels}, boxes: ${m.engine_boxes}, fill_m: ${m.engine_fill_m}})`);
  bad++;
}

if (bad) process.exit(1);
console.log(`\n✓ 수거함은 ${held} 장(${heldRow.inside} 개)째에 찬다 — ${m.engine_minutes} 분마다 · 시간당 ${m.engine_empties_per_h} 회`);
