"""아티팩트로 변환해도 콘솔이 살아 있는지 본다.

tools/make_artifact.py 는 <style> 과 <body> 만 옮긴다 — <head> 는 통째로
빠진다. 그래서 스크립트가 head 안의 요소를 붙잡으면, 저장소 파일에서는
멀쩡하고 발행본에서만 null 참조로 던진다. 그 지점이 초기 렌더 앞이면
캔버스가 빈 채로 남는데, 화면에는 아무 오류도 나오지 않는다 —
'아티팩트가 왜 비어 있지' 만 남는다.

실제로 그렇게 되어 있었다. 파비콘 link 가 head 에 있는데 스크립트 끝에서
$('favicon').href 로 붙잡고 있었고, 그 바로 다음 줄이
updateUI();applyTheme();resize(); 였다.

그래서 변환한 결과물을 놓고, 스크립트가 id 로 붙잡는 것이 모두 body 안에
있는지 본다. 없는 것을 붙잡는다면 그 자리는 null 검사가 있어야 한다.
"""

import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAKE = ROOT / "tools" / "make_artifact.py"
SOURCES = [
    ROOT / "docs" / "drawings" / "pv-delamination-3d.html",
    ROOT / "docs" / "dg-hk60-rfq.html",
]


def _convert(src):
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "art.html"
        r = subprocess.run([sys.executable, str(MAKE), str(src), str(out)],
                           capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(f"{src.name} 변환 실패: {r.stderr.strip()}")
        return out.read_text(encoding="utf-8")


class TestConversionKeepsThePageAlive(unittest.TestCase):

    def setUp(self):
        # 변환 도구는 사양서 브랜치에만 있다. 없으면 검사할 대상 자체가 없다.
        if not MAKE.exists():
            self.skipTest("이 브랜치에는 아티팩트 변환 도구가 없다")

    def test_every_id_the_script_grabs_survives(self):
        for src in SOURCES:
            if not src.exists():
                continue
            art = _convert(src)
            ids = set(re.findall(r'\bid="([A-Za-z0-9_-]+)"', art))
            # $('x') 로 붙잡는 자리. 앞에 null 검사가 붙은 것은 의도적으로 없어도 된다.
            guarded = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)\s*(?:\?\.|;|\))"
                                     r"|const \w+\s*=\s*\$\('([A-Za-z0-9_-]+)'\)",
                                     art))
            safe = {a or b for a, b in guarded}
            for name in re.findall(r"\$\('([A-Za-z0-9_-]+)'\)\s*\.", art):
                if name in safe:
                    continue
                self.assertIn(
                    name, ids,
                    f"{src.name}: 아티팩트에 없는 #{name} 를 그대로 붙잡는다 — "
                    "변환본에서 null 로 던지고 그 뒤 코드가 실행되지 않는다")

    def test_the_head_only_carries_things_the_page_can_lose(self):
        """head 에 두는 것은 발행본에서 사라져도 되는 것이어야 한다."""
        src = SOURCES[0]
        head = re.search(r"<head>(.*?)</head>", src.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(head)
        for name in re.findall(r'\bid="([A-Za-z0-9_-]+)"', head.group(1)):
            art = _convert(src)
            self.assertNotIn(
                f"$('{name}').", art,
                f"#{name} 는 head 에 있는데 스크립트가 검사 없이 붙잡는다")

    def test_the_artifact_still_carries_the_content(self):
        """변환이 내용을 잃지 않았는지 — 껍데기만 남으면 위 검사는 다 통과한다."""
        for src in SOURCES:
            if not src.exists():
                continue
            art = _convert(src)
            self.assertIn("<title>", art)
            self.assertGreater(len(art), len(src.read_text(encoding="utf-8")) * 0.7,
                               f"{src.name}: 변환본이 원본보다 너무 작다")
            for bad in ("<!doctype", "<html", "<head>", "<body"):
                self.assertNotIn(bad, art.lower(), f"{bad} 가 변환본에 남았다")


if __name__ == "__main__":
    unittest.main()
