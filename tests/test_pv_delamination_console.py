"""DG-HK60 3D 운전 콘솔(docs/drawings/pv-delamination-3d.html) 검증.

콘솔은 빌드 없이 브라우저로 바로 여는 단일 HTML 파일이다. 스크립트·스타일·도면이
모두 한 파일에 들어 있어 오타 하나로 조작 버튼이 조용히 죽어도 눈에 띄지 않으므로,
문서 구조와 DOM 참조 무결성을 여기서 잡는다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

from .test_drawings import standalone_document_checks

CONSOLE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "pv-delamination-3d.html"
)
TITLE = "DG-HK60 · 단일 5단 IR 고정 탠덤 PV 분리설비 · 3D 운전 콘솔 Rev.20"

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
        """다른 도면 두 건과 같은 규약 — 구조·외부자원·테마 대응까지 공통."""
        self.assertTrue(CONSOLE.exists())
        standalone_document_checks(self, self.html, TITLE)

    def test_is_fully_self_contained(self):
        """오프라인·CSP 환경에서도 열려야 하므로 외부 리소스를 두지 않는다.

        인라인 data: URI 는 외부 자원이 아니므로 파비콘에 한해 허용한다.
        XML 네임스페이스 URI 도 식별자일 뿐 내려받지 않는다.
        """
        for url in re.findall(r'https?://[^"\')\s]+', self.html):
            if url.startswith("http://www.w3.org/"):
                continue
            self.fail(f"외부 리소스 참조: {url}")
        self.assertNotIn("src=", self.html, "외부 자원 로드는 두지 않는다")
        for href in re.findall(r'<link[^>]*href="([^"]*)"', self.html):
            self.assertTrue(href.startswith("data:"), f"외부 링크 자원: {href}")

    def test_container_tags_balance(self):
        for tag in ("html", "head", "body", "header", "main", "section", "nav",
                    "dialog", "style", "script", "table", "aside"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_respects_reduced_motion(self):
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.html)

    def test_light_is_the_base_palette(self):
        """규약대로 :root 가 라이트, 다크는 덮어쓰기여야 한다.

        순서가 뒤집히면 시스템 테마가 라이트일 때 다크 토큰이 남는다.
        """
        root = re.search(r"\n\s*:root\{(.*?)\n\s*\}", self.html, re.S)
        self.assertIsNotNone(root, ":root 토큰 블록 없음")
        self.assertIn("--bg:#e3e8e6", root.group(1), ":root 는 라이트 팔레트여야 한다")
        for block in (
            r'@media \(prefers-color-scheme: dark\)\{\s*:root:not\(\[data-theme="light"\]\)\{(.*?)\n\s*\}',
            r':root\[data-theme="dark"\]\{(.*?)\n\s*\}',
        ):
            m = re.search(block, self.html, re.S)
            self.assertIsNotNone(m, block)
            self.assertIn("--bg:#141c20", m.group(1), "다크 블록이 라이트 값을 덮지 않는다")

    def test_dark_and_light_override_the_same_tokens(self):
        """두 다크 블록이 서로 다른 토큰 집합을 정의하면 한쪽에서만 깨진다."""
        media = re.search(
            r'@media \(prefers-color-scheme: dark\)\{\s*:root:not\(\[data-theme="light"\]\)\{(.*?)\n\s*\}',
            self.html, re.S)
        attr = re.search(r':root\[data-theme="dark"\]\{(.*?)\n\s*\}', self.html, re.S)
        names = lambda block: sorted(set(re.findall(r"(--[\w-]+):", block)))
        self.assertEqual(names(media.group(1)), names(attr.group(1)))

    def test_scene_palette_covers_both_themes(self):
        """캔버스는 CSS 변수를 못 읽으므로 JS 쪽 환경 팔레트도 두 벌이어야 한다."""
        env = re.search(r"const ENV=\{(.*?)\n    \};", self.html, re.S)
        self.assertIsNotNone(env, "ENV 팔레트 없음")
        body = env.group(1)
        keys = lambda name: sorted(set(re.findall(
            r"(\w+):", re.search(rf"{name}:\{{(.*?)\n      \}}", body, re.S).group(1))))
        self.assertEqual(keys("light"), keys("dark"), "라이트/다크 환경 키가 다르다")
        self.assertIn("themeButton", self.html, "테마 전환 버튼 없음")

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


class TestComponentMounting(unittest.TestCase):
    """부품이 공중에 떠 있지 않고 하중경로를 갖는지.

    형상은 브라우저에서만 평가되므로 여기서는 지지 부재 자체가 존재하고 실제로
    쓰이는지를 지킨다. 기둥이 바닥까지 내려오지 않으면 기계가 떠 보이고, 그것이
    개념 스케치와 제작 검토도를 가르는 지점이다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_mounting_primitives_exist(self):
        for fn in ("anchorBolts", "basePlate", "column", "gusset",
                   "pillowBlock", "pipeHanger", "plinth", "vesselSkirt"):
            self.assertIn(f"function {fn}(", self.html, f"{fn} 지지 부재 누락")

    def test_column_reaches_the_floor_on_a_base_plate(self):
        """기둥은 바닥에서 시작하고 베이스 플레이트를 깔아야 한다."""
        body = re.search(r"function column\(x,y,zTop,opt=\{\}\)\{(.*?)\n    \}", self.html, re.S)
        self.assertIsNotNone(body, "column() 정의를 찾지 못함")
        src = body.group(1)
        self.assertIn("opt.z0??.11", src, "기둥 하단이 바닥 기준이 아니다")
        self.assertIn("basePlate(", src, "기둥에 베이스 플레이트가 없다")

    def test_base_plate_is_anchored(self):
        body = re.search(r"function basePlate\(.*?\n    \}", self.html, re.S)
        self.assertIn("anchorBolts(", body.group(0), "베이스 플레이트에 앵커볼트가 없다")

    def test_support_members_are_actually_used(self):
        """정의만 해두고 쓰지 않으면 의미가 없다 — 호출 수로 확인한다."""
        for fn, least in (("column(", 20), ("plinth(", 10), ("gusset(", 8), ("pillowBlock(", 4)):
            calls = len(re.findall(re.escape(fn), self.html)) - 1   # 정의 자신은 제외
            self.assertGreaterEqual(calls, least, f"{fn} 호출 {calls}건 — 지지 적용이 빠졌다")

    def test_fastener_detail_is_level_of_detail_gated(self):
        """볼트·패드는 멀리서 서브픽셀이므로 거리 기준으로 걸러야 한다."""
        self.assertIn("const nearView=()=>", self.html)
        self.assertIn("const midView=()=>", self.html)
        for fn in ("anchorBolts", "plinth"):
            body = re.search(rf"function {fn}\(.*?\n    \}}", self.html, re.S).group(0)
            self.assertTrue("nearView()" in body or "midView()" in body,
                            f"{fn} 에 거리 기준 LOD가 없다")


class TestBrandIdentity(unittest.TestCase):
    """회사 마크가 한 벌의 도형에서 나오고, 실제로 부착돼 있는지.

    마크는 지급된 로고 아트워크에서 추출한 폴리곤이며, 장비 외장(3D)과 콘솔
    크롬(SVG)에 같은 좌표로 그려진다. 두 곳이 따로 놀면 같은 회사 마크가 아니게
    되므로, SVG 좌표를 JS 도형에서 유도해 일치를 강제한다.
    """

    BRAND, ACCENT = "#268cca", "#fdca4a"

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        m = re.search(r"const MARK_SHAPES=\[(.*?)\n    \];", cls.html, re.S)
        assert m, "MARK_SHAPES 없음"
        cls.shapes = []
        for role, pts in re.findall(r"\{c:'(\w)',p:\[(.*?)\]\}", m.group(1)):
            cls.shapes.append((role, [[float(v) for v in p.split(",")]
                                      for p in re.findall(r"\[([-\d.,]+)\]", pts)]))

    @staticmethod
    def _fmt(v):
        v = round(v, 1)
        return str(int(v)) if float(v).is_integer() else str(v)

    def test_mark_matches_the_supplied_artwork(self):
        """로고는 파란 도형 4개와 노란 면 1개로 이뤄진다."""
        self.assertEqual(len(self.shapes), 5, "마크 도형 수가 아트워크와 다르다")
        roles = [r for r, _ in self.shapes]
        self.assertEqual(roles.count("a"), 1, "노란 면은 하나")
        self.assertEqual(roles.count("b"), 4, "파란 면은 넷")
        for _role, poly in self.shapes:
            self.assertGreaterEqual(len(poly), 6, "각 면은 다각형이어야 한다")

    def test_brand_colours_are_sampled_from_the_artwork(self):
        for name, value in (("brand", self.BRAND), ("accent", self.ACCENT)):
            self.assertIn(f"{name}:'{value}'", self.html, f"{name} 색이 아트워크와 다르다")

    def test_svg_mark_matches_the_three_dimensional_mark(self):
        """SVG 폴리곤은 JS 도형에서 y축만 뒤집어 유도된 좌표여야 한다."""
        for _role, poly in self.shapes:
            pts = " ".join(f"{self._fmt(x)},{self._fmt(100 - y)}" for x, y in poly)
            self.assertIn(f"points='{pts}'", self.html,
                          f"SVG 마크가 3D 마크와 어긋난다: {pts}")

    def test_favicon_is_inline_and_carries_the_mark(self):
        link = re.search(r'<link rel="icon" href="(data:image/svg\+xml,[^"]+)"', self.html)
        self.assertIsNotNone(link, "인라인 파비콘 없음")
        self.assertEqual(link.group(1).count("polygon"), len(self.shapes),
                         "파비콘 마크의 도형 수가 다르다")

    def test_tagline_is_present(self):
        self.assertIn("FOR NET ZERO PROJECTION", self.html, "태그라인 누락")

    def test_brand_is_applied_to_the_machine(self):
        for fn in ("brandMark3D", "brandLockup", "decalText", "liveryStripe", "dataPlate"):
            self.assertIn(f"function {fn}(", self.html, f"{fn} 없음")
        badges = len(re.findall(r"cabinetBadge\(", self.html)) - 1
        self.assertGreaterEqual(badges, 5, f"외장 마크 부착 {badges}곳 — 너무 적다")
        self.assertGreaterEqual(len(re.findall(r"liveryStripe\(", self.html)) - 1, 6)
        self.assertIn("dataPlate(V(", self.html, "명판이 장비에 부착되지 않았다")

    def test_every_applied_letter_has_a_glyph(self):
        """서체에 없는 글자는 조용히 빈칸으로 그려진다 — 실제로 겪은 버그다."""
        block = re.search(r"const GLYPHS=\{(.*?)\n    \};", self.html, re.S)
        self.assertIsNotNone(block, "GLYPHS 없음")
        glyphs = set(re.findall(r"'(.)':\[", block.group(1)))
        used = set()
        for pattern in (r"decalText\('([^']*)'",
                        r"brandLockup\([^)]*?,\s*'([^']*)'\)",
                        r"cabinetBadge\([^)]*?,\s*'([^']*)'\)",
                        r"word='([^']*)'"):
            for text in re.findall(pattern, self.html):
                used |= set(text.upper())
        self.assertTrue(used, "각인 문자열을 찾지 못했다")
        missing = sorted(used - glyphs)
        self.assertEqual(missing, [], f"서체에 없는 글자가 각인에 쓰였다: {missing}")

    def test_applied_graphics_use_a_sort_bias(self):
        """페인터 알고리즘에서 데칼은 바탕판보다 앞서야 한다."""
        self.assertIn("function withBias(", self.html)
        self.assertIn("depth:depth-drawBias", self.html, "poly 가 정렬 바이어스를 반영하지 않는다")
        for fn in ("dataPlate", "cabinetBadge"):
            body = re.search(rf"function {fn}\(.*?\n    \}}", self.html, re.S).group(0)
            self.assertIn("withBias(", body, f"{fn} 가 바이어스를 쓰지 않는다")


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
