/* GI 검사 확대도가 **실제로 도는지** 브라우저로 잰다.
 *
 * 글자로만 확인하면 놓치는 것들이 있다 — 부품이 안 그려져도 표는 나오고,
 * 단계를 넘겨도 형상이 안 움직일 수 있다. 그래서 여기서 재는 것은 셋이다:
 * 페이지 오류 0, 세 유닛의 메시가 실제로 섰는가, 그리고 단계를 넘길 때
 * 판이 **자리를 바꾸는가**.
 *
 * 자리표는 모델이 정한 값과 화면 값이 같아야 한다 — 이음매가 비면 여기서
 * 걸린다. 그리고 이 셀의 결론(**화소가 아니라 자리 때문에 여러 대**)이
 * 화면에서도 성립하는지를 수로 확인한다.
 *
 * 넷째 유닛은 물리엔진이다. 화면의 XPBD 띠가 유한요소와 **같은 판**인지를
 * 수로 견준다 — 성한 판이 심도 한가운데 있는가, κ 를 초점 문턱까지 내리면
 * 처짐이 심도 끝(±DOF/2)에 오는가, 보호창 문턱 아래면 보호창을 치는가.
 * 성한 판의 5 µm 는 실시간 솔버가 못 잰다 — 그래서 문턱에서 견준다.
 *
 * 실행:  node tools/check_gi_closeup.mjs
 */
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { browserPath } from './pw_browser.mjs';

const FILE = 'docs/drawings/pv-gi-closeup.html';
const UNITS = ['below', 'above', 'window', 'plate'];
const browser = await chromium.launch({
  executablePath: browserPath(),
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
await page.goto('file://' + resolve(FILE), { waitUntil: 'load' });
await page.waitForFunction(() => window.__pvGiCloseup, null, { timeout: 30000 });
await page.waitForTimeout(1500);

const got = await page.evaluate((units) => {
  const A = window.__pvGiCloseup;
  const out = { units: A.units, seam: A.seam, optics: A.optics, mag: A.mag,
                moves: {}, counts: {} };
  for (const u of units) {
    const a = A.positions(u, 0), b = A.positions(u, 4);
    out.counts[u] = Object.keys(a).length;
    let worst = 0, who = '';
    for (const k of Object.keys(a)) {
      if (!b[k]) continue;
      const d = Math.hypot(b[k][0] - a[k][0], b[k][1] - a[k][1], b[k][2] - a[k][2]);
      if (d > worst) { worst = d; who = k; }
    }
    out.moves[u] = { part: who, m: +worst.toFixed(4) };
  }
  /* 물리 — 이송을 멈추고 창 위에 판을 앉힌 뒤 가라앉힌다 */
  const P = A.plate, phy = A.phy;
  A.go('plate', 0);
  P.runout(false); P.convey(false);
  P.place(phy.rollerZM[phy.rollerZM.length - 1] + phy.pitchM / 2);
  const settle = (k) => { P.setShare(k); return P.settle(240); };
  out.plate = {
    intact: settle(1.0), intactFinite: P.finite, intactInDof: P.inDof,
    atFocus: settle(phy.shareFocus), atFocusInDof: P.inDof, atFocusTouch: P.touching,
    belowCover: settle(phy.shareCover / 3), belowCoverTouch: P.touching,
    dofHalf: phy.dofM / 2, coverGap: phy.coverGapM, sagFem: phy.sagIntactM,
    sagFocusFem: phy.sagFocusM, entryFem: phy.entryScanSagM,
    blurIntact: null,
  };
  /* 보호창에서 판을 떼어 다시 앉힌 뒤 읽는다 — 8 mm 에서 6 µm 로 돌아오는 데는 프레임이 든다 */
  P.place(phy.rollerZM[phy.rollerZM.length - 1]); P.setShare(1.0); P.settle(180); out.plate.blurIntact = P.blurPx;
  /* 이송을 다시 켜고 앞끝이 창을 건너게 한다 — 발산하지 않고 끝이 다음 롤러에 얹히는가 */
  P.convey(true); P.place(phy.rollerZM[0]);
  let worst = 0, ok = true;
  for (let f = 0; f < 200; f += 1) { P.settle(1); if (!P.finite) ok = false; if (P.sagM !== null) worst = Math.max(worst, Math.abs(P.sagM)); }
  out.plate.entryWorst = worst; out.plate.entryFinite = ok;
  A.go('below', 0);
  out.band = [...document.getElementById('gi-cu-band').children]
    .map((s) => s.querySelector('b').textContent);
  out.rows = document.getElementById('gi-cu-rows').children.length;
  out.spec = document.getElementById('gi-cu-spec').children.length;
  out.stars = (document.getElementById('gi-cu').textContent.match(/\*\*/g) || []).length;
  return out;
}, UNITS);
await browser.close();

const s = got.seam, o = got.optics;
const bad = [];
if (errors.length) bad.push(`페이지 오류 ${errors.length}: ${errors.slice(0, 2).join(' | ')}`);
if (got.units !== 4) bad.push(`유닛 ${got.units} — 4 이어야 한다`);
for (const u of UNITS) {
  if (!got.counts[u]) bad.push(`${u}: 부품이 하나도 안 섰다`);
  if (u === 'plate') continue;                 /* 띠는 키프레임이 아니라 물리가 움직인다 — 아래서 본다 */
  /* 움직였는가만 보면 단위를 틀려도 통과한다 — SG 확대도에서 한 번 그렇게
     당했다: 자리 변화를 mm 로 셈해 놓고 m 에 그대로 넣어 유리가 1,400 **m**
     를 갔는데도 '움직인다' 였다. 그래서 위아래를 다 막는다. */
  if (got.moves[u].m < 0.002) bad.push(`${u}: 단계를 넘겨도 안 움직인다 (최대 ${got.moves[u].m} m)`);
  if (got.moves[u].m > 2.0) bad.push(`${u}: ${got.moves[u].part} 가 ${got.moves[u].m} m 움직였다`
    + ' — 장비 포락선을 넘는다 (mm 를 m 에 넣지 않았는지 볼 것)');
}
if (got.band.length !== s.cameras)
  bad.push(`자리 띠가 ${got.band.length} 칸 — 카메라 ${s.cameras} 대여야 한다`);
if (!s.covers) bad.push('자리표가 폭을 못 덮는다 — 이음매가 빈다');
/* 이 셀의 결론이 화면에서도 서는가: 한 대는 자리가 모자라고, 화소는 남는다. */
if (!(s.oneNeeds > s.allotted))
  bad.push(`한 대 안이 ${s.oneNeeds} mm 로 배정 ${s.allotted} mm 를 안 넘는다 — 결론이 바뀐다`);
if (!(s.sensorPx >= s.pixelsNeeded))
  bad.push(`센서 ${s.sensorPx} px 가 필요한 ${s.pixelsNeeded} px 에 모자란다 — '자리 때문' 이 아니게 된다`);
if (!(s.stack <= s.allotted))
  bad.push(`${s.cameras} 대 스택 ${s.stack} mm 가 배정 ${s.allotted} mm 를 넘는다`);
const span = s.seats[s.seats.length - 1].to - s.seats[0].from;
if (Math.abs(span - s.panelW) > 1e-6)
  bad.push(`자리표가 덮는 폭 ${span} ≠ 판 폭 ${s.panelW}`);
if (!(o.dof >= o.bow)) bad.push(`심도 ${o.dof} mm 가 판 휨 ${o.bow} mm 를 못 덮는다`);
/* 물리엔진이 유한요소와 같은 판인가 */
const pl = got.plate;
if (!pl.intactFinite || !pl.entryFinite) bad.push('XPBD 띠가 발산했다');
if (pl.intact === null) bad.push('가라앉힌 뒤 스캔선 위에 판이 없다');
else {
  if (!pl.intactInDof) bad.push(`성한 판이 심도 밖이다 (${(pl.intact * 1000).toFixed(3)} mm)`);
  /* 성한 판 — 5 µm 자릿수. 128 서브스텝에서 XPBD 가 6.6 을 낸다 (서브스텝 8 이면 236) */
  const ri = pl.intact / pl.sagFem;
  if (!(ri > 0.33 && ri < 3))
    bad.push(`성한 판 XPBD ${(pl.intact * 1e6).toFixed(1)} µm 가 유한요소 ${(pl.sagFem * 1e6).toFixed(1)} 의 자릿수가 아니다 — 서브스텝이 모자라면 판이 무르게 나온다`);
  /* 문턱 — 여기가 정량 비교다. XPBD 는 2차 차분 곡률이라 유한요소보다 9 % 무르다 */
  const r = pl.atFocus / pl.sagFocusFem;
  if (!(r > 0.8 && r < 1.25))
    bad.push(`κ=초점 문턱에서 XPBD ${(pl.atFocus * 1000).toFixed(2)} mm 가 유한요소 ${(pl.sagFocusFem * 1000).toFixed(2)} 와 25 % 넘게 다르다`);
  if (pl.atFocusTouch) bad.push('초점 문턱에서 벌써 보호창을 친다');
  if (!pl.belowCoverTouch) bad.push(`κ=보호창 문턱/3 인데 보호창을 안 친다 (${(pl.belowCover * 1000).toFixed(2)} mm)`);
  if (!(pl.blurIntact > 1.0 && pl.blurIntact < 1.5)) bad.push(`성한 판 유효 화소 ${pl.blurIntact} px 가 이송 흐림 자릿수가 아니다`);
  /* 앞끝 외팔 + 얹힘 — 유한요소의 스캔선 최대와 같은 자릿수여야 한다 (같은 물리가 따로 나온다) */
  const re = pl.entryWorst / pl.entryFem;
  if (!(re > 0.5 && re < 2.5)) bad.push(`앞끝이 건너는 동안 XPBD 최대 ${(pl.entryWorst * 1000).toFixed(3)} mm 가 유한요소 ${(pl.entryFem * 1000).toFixed(3)} 의 자릿수가 아니다`);
  if (!(pl.entryWorst < pl.dofHalf)) bad.push(`앞끝이 건너는 동안 심도를 벗어난다 (${(pl.entryWorst * 1000).toFixed(3)} mm)`);
}
if (got.stars) bad.push(`화면에 별표 ${got.stars} 개가 그대로 보인다`);
if (!got.rows || !got.spec) bad.push('부품표·사양표가 비었다');

console.log(`${bad.length ? '✗' : '✓'} ${FILE}`);
console.log(`  유닛 ${got.units} · 부품 메시 below ${got.counts.below}`
  + ` / above ${got.counts.above} / window ${got.counts.window} / plate ${got.counts.plate} · 창 배율 ${got.mag}배`);
if (got.plate.intact !== null) console.log(`  XPBD ↔ 유한요소 — 성한 판 ${(got.plate.intact * 1e6).toFixed(1)} µm (FEM ${(got.plate.sagFem * 1e6).toFixed(1)}) ·`
  + ` κ=초점 문턱 ${(got.plate.atFocus * 1000).toFixed(2)} mm (FEM ${(got.plate.sagFocusFem * 1000).toFixed(2)}) ·`
  + ` κ=보호창/3 ${got.plate.belowCoverTouch ? '친다' : '안 친다'} · 유효 화소 ${got.plate.blurIntact.toFixed(2)} px ·`
  + ` 앞끝 최악 ${(got.plate.entryWorst * 1000).toFixed(3)} mm (FEM ${(got.plate.entryFem * 1000).toFixed(3)})`);
console.log(`  단계 이동 — below ${got.moves.below.part} ${got.moves.below.m} m ·`
  + ` above ${got.moves.above.part} ${got.moves.above.m} m ·`
  + ` window ${got.moves.window.part} ${got.moves.window.m} m`);
console.log(`  한 대면 ${s.oneNeeds} mm 인데 배정은 ${s.allotted} mm (${s.shortfall} 초과)`
  + ` → ${s.cameras} 대 · 스택 ${s.stack} mm`);
console.log(`  화소는 남는다 — 센서 ${s.sensorPx.toLocaleString()} px ≥ 필요 `
  + `${s.pixelsNeeded.toLocaleString()} px`);
console.log(`  자리 ${s.seats.map((t) => t.width.toFixed(0)).join(' / ')} mm ·`
  + ` 이음매 ${s.overlapEach} mm × ${s.cameras - 1} = ${s.overlapTotal} mm`);
console.log(`  창 ${o.window} mm · 심도 ${o.dof} mm ≥ 휨 ${o.bow} mm ·`
  + ` ${o.lineHz.toLocaleString()} line/s`);
if (bad.length) { bad.forEach((b) => console.log('   ✗ ' + b)); process.exit(1); }
console.log('\n✓ 네 유닛이 서고, 자리가 폭을 빈틈없이 덮고, 화면의 XPBD 가 유한요소와 같은 판이다');
