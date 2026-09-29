/* 도면을 헤드리스로 열어 JS 오류와 후단 셀 그룹의 존재를 확인한다.
 *     node tools/check_page_load.mjs docs/drawings/pv-preprocess-plant.html */
import { chromium } from 'playwright';
import { resolve } from 'node:path';
const file = process.argv[2];
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
await page.goto('file://' + resolve(file), { waitUntil: 'load' });
await page.waitForTimeout(4000);
const info = await page.evaluate(() => {
  const g = window.pvGrm; const out = { hasGrm: !!g, children: g ? g.children.length : 0 };
  try { out.handoffModel = window.pvHandoff && window.pvHandoff.model; } catch (e) { out.handoffErr = String(e); }
  return out;
});
console.log(JSON.stringify(info));
console.log(errors.length ? errors.slice(0, 20).join('\n') : 'no JS errors');
await browser.close();
