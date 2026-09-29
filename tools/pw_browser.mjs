/* Playwright 실행 파일을 찾는 한 곳.
 *
 * `chromium.launch()` 를 인자 없이 부르면 Playwright 는 자기 버전에 맞는
 * 폴더만 본다. 컨테이너에 브라우저가 **미리** 깔려 있고 그 버전이 패키지와
 * 어긋나면 (`chromium_headless_shell-1243` 을 찾는데 `-1194` 만 있는 식)
 * 검사 전체가 실행조차 못 한다 — 도면이 멀쩡해도 초록불을 볼 수 없다.
 *
 * 그래서 실제로 깔려 있는 chromium 을 직접 짚는다. 못 찾으면 undefined 를
 * 돌려주고, 그때는 Playwright 의 기본 해석에 맡긴다 (로컬 개발 환경).
 */
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

export function browserPath() {
  if (process.env.PW_CHROMIUM) return process.env.PW_CHROMIUM;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH || '/opt/pw-browsers';
  if (!existsSync(root)) return undefined;
  for (const d of readdirSync(root).filter((n) => n.startsWith('chromium-')).sort().reverse()) {
    const exe = join(root, d, 'chrome-linux', 'chrome');
    if (existsSync(exe)) return exe;
  }
  const plain = join(root, 'chromium', 'chrome-linux', 'chrome');
  return existsSync(plain) ? plain : undefined;
}
