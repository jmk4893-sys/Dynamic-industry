"""DG-HK60 3D 운전 콘솔(docs/drawings/pv-delamination-3d.html) 검증.

콘솔은 빌드 없이 브라우저로 바로 여는 단일 HTML 파일이다. 스크립트·스타일·도면이
모두 한 파일에 들어 있어 오타 하나로 조작 버튼이 조용히 죽어도 눈에 띄지 않으므로,
문서 구조와 DOM 참조 무결성을 여기서 잡는다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

CONSOLE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "pv-delamination-3d.html"
)

# `$('foo')` 와 `document.getElementById('foo')` 로 참조하는 정적 id
ID_REF = re.compile(r"""(?:\$|document\.getElementById)\(\s*['"]([A-Za-z][\w-]*)['"]\s*\)""")
# 정적 마크업과 템플릿 문자열 양쪽에서 정의되는 id
ID_DEF = re.compile(r"""\bid=["']([A-Za-z][\w-]*)["']""")


class TestConsoleDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(CONSOLE.exists())
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        for tag in ('<html lang="ko">', "<head>", "</head>", "<body>", "</body>", "</html>"):
            self.assertIn(tag, self.html, tag)
        self.assertIn('<meta charset="utf-8">', self.html)  # 한글 콘솔 — 빠지면 깨진다
        self.assertIn('name="viewport"', self.html)
        self.assertIn("<title>", self.html)

    def test_is_fully_self_contained(self):
        """오프라인·CSP 환경에서도 열려야 하므로 외부 리소스를 두지 않는다."""
        for url in re.findall(r'https?://[^"\')\s]+', self.html):
            self.fail(f"외부 리소스 참조: {url}")
        for attr in ("src=", "<link "):
            self.assertNotIn(attr, self.html, f"외부 자원 로드({attr})는 두지 않는다")

    def test_container_tags_balance(self):
        for tag in ("html", "head", "body", "header", "main", "section", "nav",
                    "dialog", "style", "script", "table", "aside"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_respects_reduced_motion(self):
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.html)

    def test_canvas_and_controls_are_labelled(self):
        canvas = re.search(r"<canvas[^>]*>", self.html)
        self.assertIsNotNone(canvas)
        self.assertIn('role="img"', canvas.group(0))
        self.assertIn("aria-label=", canvas.group(0))
        # 토글 버튼은 눌림 상태를 보조기술에 알려야 한다
        for btn in ("sectionButton", "explodeButton", "labelButton", "cameraButton",
                    "panButton", "carriageFocusButton", "tandemFocusButton"):
            markup = re.search(rf'<button[^>]*id="{btn}"[^>]*>', self.html)
            self.assertIsNotNone(markup, btn)
            self.assertIn("aria-pressed", markup.group(0), btn)


class TestConsoleDomReferences(unittest.TestCase):
    """스크립트가 참조하는 요소가 실제로 존재하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        cls.defined = set(ID_DEF.findall(cls.html))
        cls.referenced = set(ID_REF.findall(cls.html))

    def test_every_referenced_id_exists(self):
        missing = sorted(self.referenced - self.defined)
        self.assertEqual(missing, [], f"스크립트가 없는 id를 참조한다: {missing}")

    def test_focus_hud_step_rows_exist(self):
        """HUD 단계 행은 템플릿 문자열로 참조하므로 개수까지 확인한다."""
        for n in range(1, 5):
            self.assertIn(f'id="tandemStep{n}"', self.html)
        for n in range(1, 7):
            self.assertIn(f'id="carriageStep{n}"', self.html)

    def test_ids_are_unique(self):
        found = ID_DEF.findall(self.html)
        dupes = sorted({i for i in found if found.count(i) > 1})
        self.assertEqual(dupes, [], f"id 중복: {dupes}")


class TestConsoleContent(unittest.TestCase):
    """콘솔이 설명하는 설비 구성이 빠지지 않았는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_all_fifteen_process_steps(self):
        for n in range(15):
            self.assertIn(f"id:'S{n}'", self.html, f"S{n} 공정 단계 누락")

    def test_all_thirteen_assemblies(self):
        for n in range(1, 14):
            self.assertIn(f"M-{n:03d}", self.html, f"M-{n:03d} 어셈블리 누락")

    def test_states_it_is_not_a_frozen_design(self):
        """개념 검토용임을 문서 안에서 밝혀야 한다."""
        self.assertIn("치수 미확정", self.html)
        self.assertIn("개념", self.html)


if __name__ == "__main__":
    unittest.main()
