"""DG-HK60 3D 운전 콘솔(docs/drawings/pv-delamination-3d.html) 검증.

콘솔은 빌드 없이 브라우저로 바로 여는 단일 HTML 파일이다. 스크립트·스타일·도면이
모두 한 파일에 들어 있어 오타 하나로 조작 버튼이 조용히 죽어도 눈에 띄지 않으므로,
문서 구조와 DOM 참조 무결성을 여기서 잡는다.
"""

import math
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


def js_code(html):
    """주석을 걷어낸 스크립트 본문.

    같은 이름이 설명 주석에도 나오면 정규식이 코드가 아니라 주석을 짚는다.
    이 파일에서 이미 두 번 겪은 실수라 헬퍼로 고정한다.
    """
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", html, flags=re.S))


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

    마크는 지급된 아트워크 symbol_100x100mm.ai 의 PDF 경로 연산자를 파싱해 뽑은
    것이고, 원본 정의는 docs/brand/dg-mark.json 하나뿐이다. 콘솔은 그 사본을
    embed 하되 3D 외장·명판 SVG·파비콘·도면 표제란이 모두 같은 MARK 를 쓴다.
    한 곳만 고치면 같은 회사 마크가 아니게 되므로 시험이 그 일치를 강제한다.
    (원본과의 대조는 tests/test_brand_mark.py 가 맡는다.)
    """

    BRAND, ACCENT = "#228CC9", "#FECA4A"

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        m = re.search(r"const MARK=\{\s*vb:\[([\d.,]+)\],\s*paths:\[(.*?)\n      \]\s*\n    \};",
                      cls.html, re.S)
        assert m, "MARK 정의 없음"
        cls.vb = [float(v) for v in m.group(1).split(",")]
        cls.paths = re.findall(r"\{f:'(#[0-9A-Fa-f]{6})',d:'([^']+)'\}", m.group(2))

    def test_mark_matches_the_supplied_artwork(self):
        """아트워크는 파란 도형 4개와 노란 면 1개다."""
        self.assertEqual(len(self.paths), 5, "마크 도형 수가 아트워크와 다르다")
        fills = [f for f, _ in self.paths]
        self.assertEqual(fills.count(self.ACCENT), 1, "노란 면은 하나")
        self.assertEqual(fills.count(self.BRAND), 4, "파란 면은 넷")
        self.assertAlmostEqual(self.vb[0], 100.0, delta=1e-6)
        self.assertAlmostEqual(self.vb[1], 88.9723, delta=1e-4,
                               msg="마크 세로비가 아트워크와 다르다")

    def test_the_mark_keeps_the_artwork_curves(self):
        """모서리 라운드는 베지어다. 직선 다각형으로 되돌리면 다른 도형이 된다."""
        curved = [d for _f, d in self.paths if "C" in d]
        self.assertEqual(len(curved), 3, "아트워크의 곡선 경로 수가 다르다")
        self.assertNotIn("polygon points=", self.html.split("<script>")[0],
                         "손으로 적은 polygon 마크가 마크업에 남아 있다")

    def test_brand_colours_are_sampled_from_the_artwork(self):
        for name, value in (("brand", self.BRAND), ("accent", self.ACCENT)):
            self.assertIn(f"{name}:'{value}'", self.html, f"{name} 색이 아트워크와 다르다")
        for old in ("#268cca", "#fdca4a"):
            self.assertNotIn(old, self.html, f"눈으로 고른 옛 색 {old} 이 남아 있다")

    def test_one_definition_feeds_every_surface(self):
        """3D 외장·명판·파비콘·표제란이 모두 같은 MARK 에서 나와야 한다."""
        for d in (d for _f, d in self.paths):
            self.assertEqual(self.html.count(d), 1,
                             "마크 경로가 두 번 이상 적혀 있다 — 사본이 갈라질 자리다")
        self.assertIn("const MARK_POLYS=markPolys();", self.html)
        for fn, why in (("markPolys(", "베지어 평탄화"), ("markSVG(", "화면용 SVG")):
            self.assertIn(f"function {fn}", self.html, f"{why} 함수 없음")
        body = self._fn3d = re.search(r"function brandMark3D\(.*?\n    \}", self.html, re.S).group(0)
        self.assertIn("MARK_POLYS", body, "3D 외장이 MARK 를 쓰지 않는다")
        self.assertIn("$('npMark').innerHTML=markSVG(", self.html, "명판이 MARK 를 쓰지 않는다")
        self.assertRegex(self.html, r"favicon\.href='data:image/svg\+xml,'\+encodeURIComponent\(markSVG\(",
                         "파비콘이 MARK 를 쓰지 않는다")
        tb = re.search(r"function drawTitleBlock\(.*?\n    \}", self.html, re.S).group(0)
        self.assertIn("MARK_POLYS", tb, "도면 표제란이 MARK 를 쓰지 않는다")
        self.assertIn("${markSVG(", self.html, "제작도 표제란이 MARK 를 쓰지 않는다")

    def test_the_three_dimensional_mark_flips_the_svg_axis(self):
        """SVG 는 y 아래, 장비 면은 v 가 위다. 뒤집지 않으면 마크가 거꾸로 붙는다."""
        body = re.search(r"function brandMark3D\(.*?\n    \}", self.html, re.S).group(0)
        self.assertRegex(body, r"mul\(v,\(H-y\)\*k\)", "3D 마크가 y축을 뒤집지 않는다")

    def test_favicon_is_inline_and_carries_the_mark(self):
        self.assertRegex(self.html, r'<link rel="icon" id="favicon"',
                         "인라인 파비콘 자리 없음")
        self.assertIn("encodeURIComponent(markSVG(", self.html,
                      "파비콘이 MARK 에서 만들어지지 않는다")

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


class TestDeliverableEquipment(unittest.TestCase):
    """도면이 아니라 팔리는 물건으로서 갖춰야 하는 것들.

    아래 항목은 모두 준공검사·인수인계에서 실제로 확인되는 것이고, 빠져 있어도
    화면은 멀쩡해 보이기 때문에 눈으로는 회귀를 잡을 수 없다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)

    def test_every_fence_opening_is_guarded(self):
        """펜스가 끊긴 자리마다 광커튼이 서 있어야 한다.

        반입·반출구는 자재가 지나야 해서 도어를 달 수 없다. 방호 없이 열어두면
        3.8m 개구부가 그대로 남는다.
        """
        fence = re.findall(r"fenceSegment\(([-\d.,\s]+)\)", self.html)
        self.assertTrue(fence, "안전펜스가 없다")
        ends = {}
        for call in fence:
            x0, y0, x1, y1 = (float(v) for v in call.split(",")[:4])
            if x0 == x1:                       # 라인 끝을 막는 세로 구간
                ends.setdefault(x0, []).append((min(y0, y1), max(y0, y1)))
        self.assertTrue(ends, "라인 양 끝 펜스가 없다")
        guarded = [float(m) for m in re.findall(r"lightCurtain\(([-\d.]+),", self.html)]
        for x, spans in ends.items():
            covered = sum(hi - lo for lo, hi in spans)
            outer = max(hi for _, hi in spans) - min(lo for lo, _ in spans)
            if outer - covered < 0.2:          # 틈이 없으면 방호할 것도 없다
                continue
            self.assertTrue(
                any(abs(g - x) < 0.6 for g in guarded),
                f"x={x} 의 개구부가 방호되지 않았다",
            )

    def test_light_curtain_has_muting_and_a_beam_plane(self):
        body = self._fn("lightCurtain")
        self.assertIn("column(", body, "뮤팅 센서 지주가 없다")
        self.assertIn("basePlate(", body, "광커튼 기둥이 바닥판 없이 떠 있다")
        self.assertIn("line([V(x,yA,z),V(x,yB,z)]", body, "방호 광축면을 그리지 않는다")
        self.assertRegex(
            self.html, r"MUTE_VALID\s*=\s*\S", "뮤팅 성립조건이 정의되어 있지 않다"
        )
        self.assertIn("ISO 13855", self.html, "광커튼 이격거리 근거가 없다")

    def test_signal_tower_follows_the_running_state(self):
        """적층등이 상태와 무관하게 켜져 있으면 표시장치가 아니라 장식이다."""
        body = self._fn("signalTower")
        self.assertIn("playing", body, "적층등이 운전상태를 읽지 않는다")
        for colour in ("C.red", "C.yellow", "C.ok"):
            self.assertIn(colour, body, f"{colour} 렌즈가 없다")
        lens = re.search(r"const lens=\[(.*?)\];", body).group(1)
        self.assertLess(
            lens.index("C.ok"), lens.index("C.red"),
            "적층등은 아래에서 위로 녹·황·적 순이어야 한다",
        )
        self.assertIn("START_WARN", self.html, "기동 예고 조건이 없다")

    def test_nameplate_carries_the_legal_ratings(self):
        """명판은 상표 배지가 아니라 IEC 60204-1 16.4 의 표시 의무다."""
        body = self._fn("dataPlate")
        for token in ("3PH4W", "60HZ", "FLA", "SCCR", "IP54", "DWG", "KC CE"):
            self.assertIn(token, body, f"명판에 {token} 표시가 없다")
        self.assertIn("IEC 60204-1", self.html)

    def test_nameplate_values_are_derived_not_typed(self):
        """명판에 손으로 적은 숫자가 있으면 도면과 갈라진다.

        전압·전류·SCCR·도면번호는 모두 부하표와 변압기 제원에서 계산돼야 한다.
        """
        body = self._fn("dataPlate")
        for expr in ("${LINE_V}", "Math.round(FLA)", "${SCCR_KA}", "${DWG_NO}"):
            self.assertIn(expr, body, f"명판이 {expr} 를 계산하지 않고 값을 박아 넣었다")
        self.assertNotRegex(
            body, r"'[^']*\b\d{3}A\b", "명판에 전류값이 문자열로 박혀 있다"
        )

    def test_full_load_current_combines_branches_as_phasors(self):
        """전류를 크기만 더하면 역률이 다른 무효분을 같은 방향으로 취급한다.

        세 가지 계산이 서로 다른 값을 낸다.

          총 kW ÷ 가정 혼합역률   과소평가 — 역률을 하나로 뭉갠다
          분기전류 크기의 산술합   과대평가 — 무효분 각도를 무시한다 (+2.9%)
          유효·무효 각각 합 → 합성  물리적으로 맞는 값

        여기서 부하표를 직접 읽어 세 값을 모두 계산하고, 소스가 셋 중
        마지막 것을 쓰는지 확인한다. 값이 아니라 방법을 잡는 시험이다.
        """
        rows = re.findall(
            r"\{\s*id:'([^']+)'\s*,\s*load:'[^']*'\s*,"
            r"\s*kW:(\d+)\s*,\s*pf:([\d.]+)\s*,\s*mccb:'([^']+)'\s*\}",
            self.html,
        )
        self.assertGreaterEqual(len(rows), 5, "전기부하표를 찾지 못했다")
        volts = int(re.search(r"const LINE_V=(\d+)", self.html).group(1))
        root3 = 3 ** 0.5

        active = sum(int(kw) for _, kw, _, _ in rows)
        reactive = sum(
            int(kw) * math.tan(math.acos(float(pf))) for _, kw, pf, _ in rows
        )
        apparent = math.hypot(active, reactive)
        phasor = apparent * 1000 / (root3 * volts)
        arithmetic = sum(
            int(kw) * 1000 / (root3 * volts * float(pf)) for _, kw, pf, _ in rows
        )

        # 세 방법이 실제로 갈리는 부하표여야 이 시험이 의미를 갖는다
        self.assertGreater(
            arithmetic - phasor, 5,
            "부하표 역률이 고르게 같아 산술합과 위상합이 구분되지 않는다",
        )

        self.assertRegex(
            self.html,
            r"const CONNECTED_KVAR=LOAD_SCHEDULE\.reduce\("
            r"\(a,k\)=>a\+k\.kW\*Math\.tan\(Math\.acos\(k\.pf\)\),0\)",
            "무효전력을 분기별로 합산하지 않는다",
        )
        self.assertRegex(
            self.html,
            r"const CONNECTED_KVA=Math\.hypot\(CONNECTED_KW,CONNECTED_KVAR\)",
            "유효·무효를 합성해 피상전력을 내지 않는다",
        )
        self.assertRegex(
            self.html,
            r"const FLA=CONNECTED_KVA\*1000/\(Math\.sqrt\(3\)\*LINE_V\)",
            "전부하전류가 피상전력에서 나오지 않는다",
        )
        self.assertNotRegex(
            self.html,
            r"const FLA=LOAD_SCHEDULE\.reduce\(\(a,k\)=>a\+branchAmp\(k\),0\)",
            "전부하전류를 분기전류의 산술합으로 되돌렸다",
        )
        # 분기전류 자체는 각 분기 차단기 선정에 그대로 쓰인다
        self.assertRegex(
            self.html,
            r"const branchAmp=k=>k\.kW\*1000/\(Math\.sqrt\(3\)\*LINE_V\*k\.pf\)",
            "분기전류 식이 3상 전류식이 아니다",
        )

    def test_redundant_fans_may_both_be_healthy(self):
        """2×100% 이중화에서 '둘 다 건전' 은 정상이지 기동 금지 조건이 아니다.

        XOR 로 적어두면 정상 상태에서 배기 기동허가가 성립하지 않아, 한 대를
        일부러 못 쓰게 만들어야 기동되는 논리가 된다.
        """
        permit = re.search(r"EXHAUST_RUN = ([^']*)", self.html)
        self.assertIsNotNone(permit, "배기 기동허가 조건을 찾지 못했다")
        self.assertNotIn(
            "XOR", permit.group(1), "배기 기동허가가 팬 이중화 정상상태를 거부한다"
        )
        self.assertIn("∨", permit.group(1), "적어도 한 대 건전 조건이 아니다")
        # 한 대만 돌린다는 의도는 기동조건이 아니라 상용·예비 선택으로 남아야 한다.
        # 그 선택은 불 논리가 아니므로 '=' 을 쓴 논리식으로 적지 않는다
        # (tests/test_logic_expressions.py 의 표기 규약).
        duty = re.search(r"배기팬 상용/예비: ([^']*)", self.html)
        self.assertIsNotNone(duty, "상용·예비 절체 조건이 없다")
        for word in ("대기", "절체", "교대운전"):
            self.assertIn(word, duty.group(1), f"상용·예비 운용에 '{word}' 가 없다")
        self.assertNotIn(
            "FAN_DUTY_SELECT =", self.html,
            "상용·예비 선택은 논리식이 아니다 — '=' 로 적으면 허가처럼 읽힌다"
        )

    def test_short_circuit_rating_has_a_stated_basis(self):
        """SCCR 은 현장에서 재는 값이 아니라 근거를 밝혀 고르는 값이다."""
        self.assertIn("const SCCR_KA=", self.html, "SCCR 이 상수로 정의되어 있지 않다")
        self.assertIn("const ISC_KA=", self.html, "예상 단락전류 계산이 없다")
        sccr = int(re.search(r"const SCCR_KA=(\d+)", self.html).group(1))
        kva = int(re.search(r"const TR_KVA=(\d+)", self.html).group(1))
        volts = int(re.search(r"const LINE_V=(\d+)", self.html).group(1))
        z = [float(v) for v in
             re.search(r"TR_Z=\[([\d.,]+)\]", self.html).group(1).split(",")]
        worst = kva * 1000 / (3 ** 0.5 * volts) / min(z) / 1000
        self.assertGreater(
            sccr, worst,
            f"기기 정격 {sccr}kA 가 예상 단락전류 {worst:.1f}kA 보다 작다",
        )
        self.assertLess(
            sccr, worst * 4,
            f"기기 정격 {sccr}kA 가 예상 단락전류 {worst:.1f}kA 대비 근거 없이 크다",
        )

    def test_no_mass_is_claimed_without_a_basis(self):
        """계량하지 않은 질량을 명판에 각인하면 운송·인양 계획이 그 값을 믿는다."""
        body = self._fn("dataPlate")
        self.assertNotRegex(
            body, r"\d+\s*T\b", "근거 없는 질량이 명판에 남아 있다"
        )
        self.assertIn("계량", self.html, "질량을 계량으로 확정한다는 절차가 없다")

    def test_hazard_labels_sit_at_the_hazards(self):
        body = self._fn("hazardDecal")
        self.assertIn("C.yellow", body, "경고 표지가 노란 삼각형이 아니다")
        kinds = set(re.findall(r"hazardDecal\([^;]*?'(\w+)'\)", self.html))
        self.assertLessEqual(
            {"hot", "crush", "shock"}, kinds,
            f"고온·끼임·감전 표지 가운데 빠진 것이 있다: {kinds}",
        )
        door = self._fn("serviceDoor")
        self.assertIn("hazardDecal(", door, "가열실 정비도어에 표지가 없다")
        self.assertIn("ISO 7010", self.html)

    def test_heavy_modules_have_lifting_points(self):
        """25m 라인은 나뉘어 실려 온다. 걸 자리와 푸는 자리가 현품에 있어야 한다."""
        self.assertIn("liftingLug(", self._fn("gantry"), "모듈 상부에 인양러그가 없다")
        self.assertIn("transportSplit(", self.html, "반입 분할면 표시가 없다")
        self.assertGreaterEqual(
            len(re.findall(r"transportSplit\(", self.html)), 3,
            "분할면 호출이 정의 하나뿐이다",
        )

    def test_transport_split_text_faces_outward(self):
        """면의 법선이 안쪽을 보면 부호가 거울상으로 찍힌다."""
        body = self._fn("transportSplit")
        self.assertIn("V(-s,0,0)", body, "분할면 부호가 뒤집혀 찍힌다")

    def test_delivery_scope_is_written_down(self):
        for token in ("예비품", "보증", "FAT", "SAT", "매뉴얼", "교육"):
            self.assertIn(token, self.html, f"인도 범위에 {token} 항목이 없다")


class TestBacksheetWinder(unittest.TestCase):
    """백시트 권취부 — 롤 성장률과 권취부 위치.

    이 두 가지는 그림만 봐서는 틀린 줄 모른다. 롤이 한 장에 두 배가 되는 그림은
    필름 0.30mm 를 340mm 로 그린 것과 같고, 권취부가 상류에 있으면 웹이 캐리어
    통로를 거꾸로 가로지르는데 정지화면에서는 둘 다 그럴듯해 보인다.
    """

    # 면적보존: 감긴 필름 단면적 n·L·t 가 원환 π(r²−r0²) 와 같다
    T = 0.30e-3          # 백시트 두께
    L = 2.4              # 패널 길이 (사양 2400×1200)
    R0 = 0.15            # 코어 Ø300
    R1 = 0.30            # 만권 Ø600

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        cls.turn = cls.L * cls.T / math.pi

    def _const(self, name):
        """`const NAME=<숫자>` 선언만 읽는다. 주석에 같은 이름이 나와도 안 걸린다."""
        m = re.search(
            rf"(?:const|,)\s*{name}\s*=\s*(-?[\d.]+(?:e-?\d+)?)[,;]", self.html
        )
        self.assertIsNotNone(m, f"상수 {name} 선언을 찾지 못했다")
        return float(m.group(1))

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)

    def _radius(self, n):
        return math.sqrt(self.R0 ** 2 + n * self.turn)

    # ── 롤 성장 ────────────────────────────────────────────────
    def test_roll_radius_is_area_conserving_not_linear(self):
        """r = r0 + k·peel 형태로 돌아가면 실패한다."""
        self.assertIn("rollRadius", self.html, "롤 반경 모델이 없다")
        self.assertRegex(
            self.html, r"rollRadius\s*=\s*n\s*=>.*Math\.sqrt",
            "롤 반경이 제곱근(면적보존)으로 계산되지 않는다",
        )
        self.assertNotIn(".3+.34*clamp(peel)", self.html,
                         "롤 직경이 아직 박리 진행률에 선형으로 붙어 있다")

    def test_film_thickness_and_core_match_the_spec(self):
        self.assertAlmostEqual(self._const("BACKSHEET_T"), self.T, places=6)
        self.assertAlmostEqual(self._const("WR_CORE_R"), self.R0, places=4)
        self.assertAlmostEqual(self._const("WR_FULL_R"), self.R1, places=4)
        self.assertAlmostEqual(self._const("PANEL_L"), self.L, places=4,
                               msg="롤 계산의 패널 길이가 사양 2400mm 이 아니다")

    def test_one_panel_moves_the_diameter_by_about_1_5_mm(self):
        """한 장에 Ø301.5 — 눈으로는 거의 안 변하는 것이 정상이다."""
        self.assertAlmostEqual(self._radius(1) * 2000, 301.5, delta=0.1)
        self.assertAlmostEqual(self._radius(10) * 2000, 314.9, delta=0.1)
        self.assertAlmostEqual(self._radius(60) * 2000, 380.8, delta=0.2)

    def test_full_roll_panel_count_is_stated_and_correct(self):
        n = round((self.R1 ** 2 - self.R0 ** 2) / self.turn)
        self.assertEqual(n, 295)
        self.assertIn("ROLL_FULL_PANELS", self.html)
        # 콘솔이 본문에 적어 둔 값도 같아야 한다
        self.assertIn("295", self.html, "만권 장수가 본문에 없다")
        self.assertIn("4.9", self.html, "만권까지 걸리는 시간이 본문에 없다")

    def test_roll_change_happens_at_full_roll_not_every_panel(self):
        """S7 이 장마다 롤을 빼면 하루 480회 교체하는 설비가 된다."""
        m = re.search(r"function woundCount\(i,p\)\{(.*?)\n    \}", self.html, re.S)
        self.assertIsNotNone(m, "woundCount 를 찾지 못했다")
        self.assertRegex(
            m.group(1), r"i===7\s*\)\s*return\s+ROLL_FULL_PANELS",
            "롤 교체 단계가 만권 상태로 그려지지 않는다",
        )

    def test_winding_roll_takes_a_panel_count(self):
        """호출부가 박리 진행률(0~1)을 넘기면 롤은 다시 한 장에 만권이 된다."""
        for call in re.findall(r"(?<!function )windingRoll\(([^)]*)\)", self.html):
            self.assertTrue(
                call.startswith("winderState("),
                f"windingRoll 에 권취 상태가 아닌 값을 넘긴다: {call}",
            )
        body = self._fn("winderState")
        self.assertRegex(
            body, r"n=woundCount\(i,q\)",
            "권취 상태의 장수가 woundCount 에서 오지 않는다 — 박리 진행률이 섞였다",
        )

    # ── 권취부 위치 ────────────────────────────────────────────
    def test_winder_is_downstream_of_both_knives(self):
        """필름은 칼날에서 분리되는 순간부터 패널 진행방향(+x) 쪽에 있다."""
        hkb = self._const("HKB_X")
        hks = self._const("HKS_X")
        drum = self._const("WR_DRUM_X")
        self.assertGreater(drum, hks, "권취 드럼이 아직 탠덤 상류에 있다")
        self.assertGreater(drum, hkb)
        self.assertGreater(drum - hks, 1.0, "드럼이 HKS 가드에 너무 붙어 있다")

    def test_web_runs_forward_from_the_knife(self):
        """종전 코드는 절단점에서 x=14.7 로 되돌아가 캐리어 통로를 가로질렀다."""
        m = re.search(r"function backsheetWeb\(.*?\n    \}", self.html, re.S)
        self.assertIsNotNone(m, "웹 경로 함수가 없다")
        body = m.group(0)
        self.assertIn("WR_GUIDE_X", body)
        self.assertIn("WR_DRUM_X", body)
        self.assertNotRegex(self.html, r"flexSurface\([^)]*,\s*14\.7\s*,",
                            "웹이 아직 상류 x=14.7 로 되돌아간다")

    def test_peel_guide_roll_sits_at_the_blade(self):
        """가이드롤이 없으면 박리각이 롤 직경을 따라 계속 변한다."""
        guide = self._const("WR_GUIDE_X")
        hkb = self._const("HKB_X")
        self.assertLess(abs(guide - hkb), 0.4, "가이드롤이 박리선에서 멀다")
        self.assertIn("GR-W1", self.html, "가이드롤에 부호가 없다")

    def test_web_clears_the_knife_z_axis_columns(self):
        """웹 가장자리 옆으로 기둥이 지나면 필름이 기둥에 쓸린다."""
        post = self._const("KNIFE_POST_Y")
        half = self._const("PANEL_W") / 2          # 백시트 폭 = 패널 폭
        self.assertGreaterEqual(
            post - half, 0.12,
            "웹 가장자리와 나이프 Z축 기둥 간극이 사양의 120mm 미만이다",
        )
        body = re.search(r"function knifeBar\(.*?\n    \}", self.html, re.S).group(0)
        self.assertIn("KNIFE_POST_Y", body, "기둥 좌표가 상수를 쓰지 않는다")
        self.assertNotIn("[-1.24,1.24]", body, "기둥이 아직 웹 가장자리에 붙어 있다")

    def test_roll_storage_is_outside_the_fence(self):
        """롤 교체는 4.9시간마다다. 방책 안으로 들어가야 한다면 그때마다 라인이 선다."""
        bin_y = self._const("BS_BIN_Y")
        fence = min(
            float(c.split(",")[1])
            for c in re.findall(r"fenceSegment\(([-\d.,\s]+)\)", self.html)
        )
        self.assertLess(bin_y, fence, "BS-301 보관대가 안전펜스 안에 있다")
        self.assertIn("BS-301", self.html)

    def test_control_cabinet_does_not_block_the_roll_exit(self):
        """조작반이 반출 해치 앞을 막으면 롤이 나올 길이 없다."""
        m = re.search(r"plinth\((\d+(?:\.\d+)?),-3\.3,1\.6,1\.2\)", self.html)
        self.assertIsNotNone(m, "PLC/HMI 캐비닛을 찾지 못했다")
        cabinet_x = float(m.group(1))
        drum = self._const("WR_DRUM_X")
        self.assertGreater(
            abs(cabinet_x - drum), 1.4,
            "PLC/HMI 캐비닛이 권취부 롤 반출 통로와 겹친다",
        )

    def test_roll_is_drawn_at_true_size(self):
        """롤을 실치수로 그린다 — 배율 보정이 남아 있으면 실패한다."""
        self.assertNotIn("PANEL_DRAW_SCALE", self.html,
                         "권취 롤에 아직 축척 보정이 붙어 있다")
        self.assertRegex(
            self._fn("winderState"), r"r=rollRadius\(n\)\s*,",
            "권취 반경이 rollRadius 그대로가 아니다 — 배율이 붙어 있다",
        )
        self.assertRegex(
            self._fn("windingRoll"), r"r=w\.r\s*,",
            "롤을 권취 상태의 반경이 아닌 다른 값으로 그린다",
        )
        # 롤 면폭은 사양의 권취 유효폭 1,400~1,500mm 안이어야 한다
        face = self._const("ROLL_FACE")
        self.assertGreaterEqual(face, 1.4)
        self.assertLessEqual(face, 1.5)
        self.assertGreater(face, self._const("PANEL_W"), "롤 면폭이 백시트 폭보다 좁다")

    def test_live_roll_diameter_is_readable_without_turning_on_labels(self):
        """3D 라벨은 기본이 꺼져 있다. 직경이 거기에만 있으면 아무도 못 본다."""
        m = re.search(r"if\(\(index>=3&&index<=7\)\|\|index===15\)\{(.{0,1400}?)\n      \}",
                      self.html, re.S)
        self.assertIsNotNone(m, "항상 보이는 권취 HUD 갱신 블록을 찾지 못했다")
        self.assertIn("winderState(index,local)", m.group(1),
                      "권취 HUD가 3D와 다른 값을 쓴다")
        self.assertIn("flowBacksheetText", m.group(1))
        self.assertRegex(
            self._fn("winderState"), r"Ø\$\{dia\}\s*/\s*Ø\$\{full\}",
            "권취 문구에 현재 직경/만권 직경이 없다",
        )
        self.assertRegex(
            self._fn("winderState"), r"dia=Math\.round\(r\*2000\)",
            "표시 직경이 실제 권취 반경에서 나오지 않는다",
        )


class TestTenPanelTrial(unittest.TestCase):
    """10장 연속 시운전 단계 — 세 계통이 동시에 쌓이는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_stage_exists_and_is_last(self):
        ids = re.findall(r"\{id:'(S\d+)'", self.html)
        self.assertIn("S15", ids, "10장 시운전 단계가 없다")
        self.assertEqual(ids[-1], "S15", "새 단계가 타임라인 끝에 오지 않는다")
        self.assertEqual(len(ids), len(set(ids)), "단계 번호가 중복된다")

    def test_stage_arrays_cover_every_step(self):
        """단계를 추가하면서 카메라·자재흐름 배열을 놓치면 마지막 단계가 조용히 깨진다."""
        steps = len(re.findall(r"\{id:'S\d+'", self.html))
        cams = re.search(r"focusX=\[([-\d.,\s]+)\]", self.html)
        self.assertIsNotNone(cams)
        self.assertEqual(len(cams.group(1).split(",")), steps,
                         "카메라 focusX 배열이 단계 수와 다르다")
        targets = re.search(r"targets=\[(.*?)\],focusX", self.html, re.S)
        self.assertEqual(len(targets.group(1).split(",")), steps,
                         "카메라 targets 배열이 단계 수와 다르다")
        flows = re.search(r"\]\[index\];", self.html)
        block = self.html[:flows.start()]
        rows = re.findall(r"\n        \['[^\]]*\],?", block[-2600:])
        self.assertGreaterEqual(len(rows), steps - 1,
                                "자재흐름 문구가 단계 수를 못 따라간다")

    def test_all_three_material_paths_accumulate(self):
        body = re.search(r"function tenPanelTestActivity\(.*?\n    \}", self.html, re.S)
        self.assertIsNotNone(body, "10장 시운전 동작이 없다")
        body = body.group(0)
        self.assertIn("panelLayers", body, "패널이 탠덤을 통과하지 않는다")
        self.assertIn("cellModuleAt", body, "셀/EVA 가 컨베이어로 투입되지 않는다")
        self.assertIn("woundCount(15", body, "백시트가 롤에 누적되지 않는다")
        self.assertRegex(self.html, r"glassStorageCarriageActivity\(1,\s*Math\.min\(10",
                         "유리가 저장 캐리지에 적재되지 않는다")

    def test_glass_carriage_shows_the_stack(self):
        body = re.search(
            r"function glassStorageCarriageActivity\(.*?\n    \}", self.html, re.S
        ).group(0)
        self.assertIn("stacked", body, "저장 캐리지가 적재 장수를 표현하지 않는다")
        self.assertIn("C.glass", body)

    def test_ten_panels_barely_grow_the_roll(self):
        """시운전 결과 문구가 실제 계산과 맞는지 — 10장에 Ø314.9."""
        r = math.sqrt(0.15 ** 2 + 10 * 2.4 * 0.30e-3 / math.pi)
        self.assertAlmostEqual(r * 2000, 314.9, delta=0.1)
        self.assertIn("Ø314.9", self.html, "10장 시운전 설명의 롤 직경이 없다")


class TestPanelScale(unittest.TestCase):
    """도면이 실제로 1 unit = 1 m 이고, 패널이 사양 치수로 그려지는지.

    종전에는 패널만 4800×2400 으로 — 사양의 2배로 — 그려져 있었다. 축척이
    틀려도 화면은 멀쩡해 보이고, 옆에 놓인 갠트리·펜스가 전부 맞는 치수라
    비교 대상이 없으면 눈으로는 잡히지 않는다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _const(self, name):
        m = re.search(
            rf"(?:const|,)\s*{name}\s*=\s*(-?[\d.]+(?:e-?\d+)?)[,;]", self.html
        )
        self.assertIsNotNone(m, f"상수 {name} 선언을 찾지 못했다")
        return float(m.group(1))

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)

    def test_drawing_scale_is_one_unit_per_metre(self):
        """도면 좌표가 미터라는 것이 이 파일의 다른 모든 치수 주장의 전제다.

        제작도 표에 적힌 치수와 3D 좌표가 다섯 군데에서 맞아야 성립한다.
        """
        # 안전펜스 25,000 mm = M-013
        fence = re.findall(r"fenceSegment\(([-\d.,\s]+)\)", self.html)
        xs = [float(v) for call in fence for v in call.split(",")[:4:2]]
        self.assertAlmostEqual(max(xs) - min(xs), 24.8, delta=0.05)
        self.assertIn("25000×7000", self.html.replace(" ", ""))
        # 탠덤 브리지 10,200 mm = M-005
        self.assertIn("gantry(17.8,10.2,", self.html)
        self.assertIn("10200×4200", self.html)
        # 가열실 M-002 — 표의 길이·폭이 실제로 그려진 외피와 같아야 한다
        tunnel = self._fn("preheatTunnel")
        self.assertRegex(tunnel, r"L\s*=\s*5\.6\b")
        m = re.search(r"id:'M-002'[^}]*?size:'(\d+)×(\d+)×\d+'", self.html)
        self.assertIsNotNone(m, "M-002 제작도 치수를 찾지 못했다")
        self.assertAlmostEqual(float(m.group(1)), 5600, delta=1)
        roof = re.search(r"box\(V\(cx,0,4\.86\),V\(L\+\.42,([\d.]+),", tunnel)
        self.assertIsNotNone(roof, "가열실 지붕 폭을 찾지 못했다")
        self.assertAlmostEqual(
            float(m.group(2)), float(roof.group(1)) * 1000, delta=1,
            msg="M-002 표의 폭이 실제로 그려진 가열실 외피와 다르다",
        )
        # 칼끝 간격 300 mm
        hkb = self._const("HKB_X")
        hks = self._const("HKS_X")
        self.assertAlmostEqual((hks - hkb) * 1000, 300, delta=0.5)

    def test_panel_matches_the_specification(self):
        """패널 2400×1200. 열모델의 기본 패널과도 같은 값이어야 한다."""
        self.assertAlmostEqual(self._const("PANEL_L"), 2.4, places=4)
        self.assertAlmostEqual(self._const("PANEL_W"), 1.2, places=4)
        model = re.search(
            r"panelLength:(\d+),panelWidth:(\d+)", self.html
        )
        self.assertIsNotNone(model, "열모델 기본 패널을 찾지 못했다")
        self.assertAlmostEqual(self._const("PANEL_L") * 1000, float(model.group(1)),
                               delta=0.5, msg="그려지는 패널 길이가 열모델과 다르다")
        self.assertAlmostEqual(self._const("PANEL_W") * 1000, float(model.group(2)),
                               delta=0.5, msg="그려지는 패널 폭이 열모델과 다르다")

    def test_panel_geometry_is_derived_not_typed(self):
        """치수를 함수마다 손으로 적으면 다음 사양 변경 때 또 한쪽만 고쳐진다."""
        for fn in ("panelLayers", "flatLayer", "panelCellPattern"):
            body = self._fn(fn)
            self.assertRegex(body, r"PANEL_(L|W|HL|HW)",
                             f"{fn} 이 패널 치수를 상수로 쓰지 않는다")
            self.assertNotIn("4.8", body, f"{fn} 에 옛 패널 길이가 남아 있다")
            self.assertNotIn("2.4,", body, f"{fn} 에 옛 패널 폭이 남아 있다")

    def test_everything_that_holds_the_panel_is_bigger_than_it(self):
        """패널보다 작은 캐리어·데크·칼날은 물리적으로 성립하지 않는다."""
        length, width = self._const("PANEL_L"), self._const("PANEL_W")
        for name, want in (("CARRIER_L", length), ("DECK_L", length),
                           ("CARRIER_W", width), ("DECK_W", width),
                           ("KNIFE_W", width), ("ROLL_FACE", width)):
            self.assertGreater(
                self._const(name), want,
                f"{name} 이 패널보다 작다 — 패널을 받칠 수 없다",
            )
        # 여유가 지나쳐도 안 된다: 캐리어는 패널 + 500mm 이내
        self.assertLess(self._const("CARRIER_L") - length, 0.6)
        self.assertLess(self._const("CARRIER_W") - width, 0.6)

    def test_tandem_pass_covers_the_whole_panel(self):
        """선단이 HKB 에 닿는 자리에서 후단이 HKS 를 벗어날 때까지.

        통과 구간을 손으로 적어 두면 패널 길이를 바꿀 때 같이 안 바뀌므로,
        HKB/HKS 와 패널 길이에서 유도했는지를 소스에서 확인한다.
        """
        hkb, hks = self._const("HKB_X"), self._const("HKS_X")
        length = self._const("PANEL_L")
        lead = self._const("LEAD_OPEN")
        self.assertRegex(
            self.html, r"TDM_LEAD=HKB_X-PANEL_HL\+LEAD_OPEN",
            "선단 개방 위치가 HKB·패널 길이에서 유도되지 않았다",
        )
        self.assertRegex(
            self.html, r"TDM_OUT=HKS_X\+PANEL_HL",
            "통과 종점이 HKS·패널 길이에서 유도되지 않았다",
        )
        lead_x, out_x = hkb - length / 2 + lead, hks + length / 2
        self.assertAlmostEqual(lead_x, 16.75, delta=0.001)
        self.assertAlmostEqual(out_x, 19.15, delta=0.001)
        # 통과 거리는 패널 길이 + 칼끝 간격
        self.assertAlmostEqual(out_x - (hkb - length / 2), length + (hks - hkb),
                               delta=0.001)
        # 탠덤 단계가 실제로 그 구간을 쓰는지
        self.assertIn("lerp(TDM_LEAD,TDM_OUT,ease(p))", self.html,
                      "S5 통과박리가 유도된 구간을 쓰지 않는다")
        self.assertNotIn("lerp(15.7,20.5", self.html, "옛 통과 구간이 남아 있다")

    def test_cell_module_leaves_where_the_panel_leaves(self):
        """셀 경로 시작점이 패널 배출 위치와 어긋나면 모듈이 허공에서 생긴다."""
        body = self._fn("cellPathPoint")
        self.assertIn("TDM_OUT", body, "셀 경로가 탠덤 배출 위치를 쓰지 않는다")


class TestSimultaneousSeparation(unittest.TestCase):
    """백시트 박리와 셀/EVA 박리는 서로 배타적인 단계가 아니다.

    칼날이 X축에 고정되어 있고 패널이 그 아래를 지나가므로, 패널의 어떤 지점이
    HKB 를 지나면 그 지점의 백시트가 떨어지고, 칼끝 간격만큼 뒤에 같은 지점이
    HKS 를 지나면 셀/EVA 가 떨어진다. 두 박리는 간격 ÷ 이송속도 만큼 어긋난 채
    **동시에** 진행된다.

    종전 코드는 `if(분리진행<=0){백시트}else{셀}` 로 갈라 놓아, 셀 분리가 시작되는
    순간 백시트 가지를 통째로 건너뛰었다. 정작 권취가 일어나는 구간에서 웹도 롤도
    화면에 없었던 원인이 이것이다. 정지화면 한 장만 보면 알 수 없는 종류의 오류라
    여기서 수치로 잡는다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _const(self, name):
        m = re.search(
            rf"(?:const|,)\s*{name}\s*=\s*(-?[\d.]+(?:e-?\d+)?)[,;]", self.html
        )
        self.assertIsNotNone(m, f"상수 {name} 선언을 찾지 못했다")
        return float(m.group(1))

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)

    def _cuts(self, cx):
        """tandemCuts 를 파이썬으로 재현한다 (state.tandem === true)."""
        half = self._const("PANEL_L") / 2
        rear, front = cx - half, cx + half
        clamp = lambda v: max(rear, min(front, v))
        return rear, front, clamp(self._const("HKB_X")), clamp(self._const("HKS_X"))

    # ── 절단선이 칼날에 고정되어 있는가 ─────────────────────────
    def test_both_cuts_are_anchored_at_the_fixed_knives(self):
        """절단선이 진행률(0~1)에서 나오면 칼날이 패널을 따라 움직이는 그림이 된다."""
        body = self._fn("tandemCuts")
        self.assertRegex(body, r"bs:clamp\(HKB_X,rear,front\)",
                         "백시트 절단선이 HKB 위치에 고정되어 있지 않다")
        self.assertRegex(body, r"cell:clamp\(HKS_X,rear,front\)",
                         "셀 절단선이 HKS 위치에 고정되어 있지 않다")
        self.assertNotIn("state.separation", self.html,
                         "박리 진행률 기반의 옛 절단선 계산이 남아 있다")

    def test_the_two_cuts_stay_one_knife_gap_apart(self):
        """두 절단선 간격은 언제나 칼끝 간격이다 — 이게 시간차의 정체다."""
        gap = self._const("HKS_X") - self._const("HKB_X")
        lead, out = 16.75, 19.15                     # TDM_LEAD, TDM_OUT
        seen = 0
        for k in range(401):
            cx = lead + (out - lead) * k / 400
            rear, front, bs, cell = self._cuts(cx)
            if rear < bs < front and rear < cell < front:
                seen += 1
                self.assertAlmostEqual(cell - bs, gap, delta=1e-9,
                                       msg=f"cx={cx:.3f} 에서 절단선 간격이 칼끝 간격과 다르다")
        self.assertGreater(seen, 0, "두 절단선이 동시에 패널 안에 있는 구간이 없다")

    def test_both_separations_run_at_once_for_most_of_the_stroke(self):
        """87.5% 는 RFQ 가 2단 동시 물림으로 적어 둔 값이다. 그림이 이를 지켜야 한다."""
        length = self._const("PANEL_L")
        gap = self._const("HKS_X") - self._const("HKB_X")
        lead, out = 16.75, 19.15
        N = 2000
        both = sum(
            1 for k in range(N)
            if (lambda c: (c[0] < c[2] < c[1] and c[0] < c[3] < c[1]))(
                self._cuts(lead + (out - lead) * (k + 0.5) / N))
        )
        self.assertAlmostEqual(both / N, (length - gap) / length, delta=0.005,
                               msg="두 박리가 동시에 진행되는 구간이 사양과 다르다")

    def test_the_offset_is_the_knife_gap_over_the_feed_rate(self):
        """시간차 = 칼끝 간격 ÷ 55mm/s. 문서가 말하는 5.45초가 여기서 나온다."""
        gap_mm = (self._const("HKS_X") - self._const("HKB_X")) * 1000
        self.assertAlmostEqual(gap_mm, 300, delta=2)
        self.assertAlmostEqual(gap_mm / 55, 5.45, delta=0.05)

    # ── 두 층을 한 프레임에 같이 그리는가 ───────────────────────
    def test_both_layers_are_drawn_in_the_same_frame(self):
        """한쪽이 else 가지에 들어가면 다른 쪽이 화면에서 사라진다."""
        body = js_code(self._fn("panelLayers"))
        # 두 층 모두 조건 없는 문장이어야 한다. 어느 한쪽이라도 if 뒤에 붙으면
        # 그 프레임에서 사라질 수 있고, 그것이 곧 배타적 단계로 되돌아간 것이다.
        for what, call in (("셀", r"flatLayer\(\(q\.rear\+q\.cell\)/2"),
                           ("백시트", r"flatLayer\(\(q\.rear\+q\.bs\)/2")):
            self.assertRegex(body, call, f"남은 {what} 층을 그리지 않는다")
            self.assertRegex(
                body, rf"(?m)^\s*{call}",
                f"{what} 층이 조건부로 그려진다 — 다른 계통과 배타적이 되었다",
            )
        cell = body.index("zCell,C.cell")
        sheet = body.index("zSheet,C.sheet")
        self.assertNotIn("else", body[min(cell, sheet):max(cell, sheet)],
                         "백시트와 셀이 서로 배타적인 가지에 들어가 있다")

    def test_the_web_is_drawn_while_the_cell_is_peeling(self):
        """권취가 실제로 일어나는 구간에서 웹이 없으면 '권취' 가 화면에 없다."""
        body = self._fn("panelLayers")
        m = re.search(r"if\(([^)]*)\)backsheetWeb\(", body)
        self.assertIsNotNone(m, "웹을 그리는 호출을 찾지 못했다")
        cond = m.group(1)
        for forbidden in ("cell", "sep", "separation"):
            self.assertNotIn(forbidden, cond,
                             f"웹 표시 조건이 셀 분리 상태에 묶여 있다: {cond}")
        self.assertIn("bsDone", cond, "웹이 백시트 잔량과 무관하게 그려진다")

    def test_the_exposed_cell_band_is_the_knife_gap(self):
        """백시트만 벗겨진 띠가 곧 칼끝 간격이다 — 시간차의 눈에 보이는 증거."""
        gap = self._const("HKS_X") - self._const("HKB_X")
        rear, front, bs, cell = self._cuts(17.8)     # 두 칼날 사이에 패널 중심
        # 패널은 +x 로 간다. 어떤 지점이 HKB 를 먼저 지나므로 백시트가 먼저 떨어지고,
        # 그 지점이 HKS 에 닿기 전까지는 셀이 남아 있다 — 그 사이가 노출 띠다.
        self.assertLess(bs, cell, "백시트 절단선이 셀 절단선보다 앞서야 한다")
        self.assertAlmostEqual(cell - bs, gap, delta=1e-9)
        self.assertGreater(bs, rear)
        self.assertLess(cell, front)


class TestWinderDischarge(unittest.TestCase):
    """만권 롤은 인터록 해치로만 나가고, 나가서는 빈 새들에 앉아야 한다.

    종전 배출은 드럼에서 보관대까지 직선 보간이라 롤이 펜스를 대각선으로 뚫고
    지나가 새들이 아닌 허공에 놓였다. 배출 경로를 상수로 두고, 그 경로가 실제
    개구를 지나 실제 크래들에 닿는지를 여기서 확인한다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _expr(self, name, seen=None):
        """`const NAME=<식>` 을 숫자로 푼다. 식은 이름·숫자·사칙연산만 허용한다."""
        seen = seen or set()
        self.assertNotIn(name, seen, f"상수 {name} 이 순환 참조한다")
        m = re.search(rf"(?:const|,)\s*{name}\s*=\s*([^,;]+?)[,;]", self.html)
        self.assertIsNotNone(m, f"상수 {name} 선언을 찾지 못했다")
        return self._value(m.group(1), seen | {name})

    def _value(self, expr, seen=frozenset()):
        expr = expr.strip()
        self.assertRegex(expr, r"^[A-Za-z_][\w]*(?:\s*[-+*/]\s*[\w.]+)*$|^-?[\d.]+$",
                         f"해석할 수 없는 식: {expr}")
        out = expr
        for ident in sorted(set(re.findall(r"[A-Za-z_]\w*", expr)), key=len, reverse=True):
            out = out.replace(ident, repr(self._expr(ident, set(seen))))
        return float(eval(out, {"__builtins__": {}}, {}))   # noqa: S307 — 화이트리스트 통과분만

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)

    def _path(self):
        m = re.search(r"const EJECT_PATH=\[(.*?)\n    \];", self.html, re.S)
        self.assertIsNotNone(m, "EJECT_PATH 를 찾지 못했다")
        pts = []
        for row in re.findall(r"\{(.*?)\}", m.group(1)):
            row = re.sub(r"//.*", "", row)
            pts.append({k: self._value(v) for k, v in
                        re.findall(r"(at|x|y|z):\s*([^,}]+)", row)})
        self.assertGreaterEqual(len(pts), 4, "배출 경로 구간이 너무 적다")
        return pts

    def _phases(self):
        m = re.search(r"const EJECT_PHASES=\[(.*?)\n    \];", self.html, re.S)
        self.assertIsNotNone(m, "EJECT_PHASES 를 찾지 못했다")
        return [float(v) for v in re.findall(r"\{at:\s*([\d.]+)", m.group(1))]

    def test_the_roll_leaves_through_the_interlock_hatch(self):
        """롤이 해치 개구 밖으로 지나가면 펜스를 뚫고 나가는 그림이 된다."""
        pts = self._path()
        hx, hw = self._expr("HATCH_X"), self._expr("HATCH_W")
        hz, hh = self._expr("HATCH_Z"), self._expr("HATCH_H")
        r = self._expr("WR_FULL_R")
        hy = self._expr("HATCH_Y")
        crossings = [
            1 for a, b in zip(pts, pts[1:])
            if (a["y"] - hy) * (b["y"] - hy) <= 0 and a["y"] != b["y"]
        ]
        self.assertEqual(len(crossings), 1,
                         "배출 경로가 해치 선을 정확히 한 번 넘지 않는다")
        # 롤은 점이 아니다. 롤 몸통이 펜스 평면에 걸쳐 있는 동안 — y 가 해치 선에서
        # 반지름 이내인 구간 내내 — x·z 가 개구 안에 있어야 실제로 통과한다.
        # 한 점만 보면 개구를 비스듬히 스치고 지나가는 경로도 통과로 읽힌다.
        for a, b in zip(pts, pts[1:]):
            for k in range(201):
                t = k / 200
                y = a["y"] + (b["y"] - a["y"]) * t
                if abs(y - hy) > r:
                    continue
                x = a["x"] + (b["x"] - a["x"]) * t
                z = a["z"] + (b["z"] - a["z"]) * t
                self.assertLessEqual(abs(x - hx), hw / 2 - r,
                                     f"해치를 지날 때 롤이 개구 폭 밖에 있다: x={x:.3f}")
                self.assertLessEqual(abs(z - hz), hh / 2 - r,
                                     f"해치를 지날 때 롤이 개구 높이 밖에 있다: z={z:.3f}")

    def test_the_roll_lands_in_the_empty_saddle(self):
        """앞 새들에는 교대 롤이 이미 놓여 있다. 같은 자리에 또 놓으면 겹친다."""
        end = self._path()[-1]
        rack = self._expr("BS_RACK_X")
        self.assertAlmostEqual(end["x"], self._expr("BS_SADDLE_X"), delta=1e-9)
        self.assertAlmostEqual(end["x"], rack + 0.55, delta=1e-9,
                               msg="배출 종점이 크래들 새들 위치가 아니다")
        self.assertNotAlmostEqual(end["x"], rack - 0.55, delta=0.2,
                                  msg="이미 교대 롤이 놓인 앞 새들에 겹쳐 놓는다")
        self.assertAlmostEqual(end["z"], self._expr("BS_ROLL_Z"), delta=1e-9,
                               msg="배출 종점 높이가 크래들 안착 높이와 다르다")
        self.assertAlmostEqual(end["y"], self._expr("BS_BIN_Y"), delta=1e-9)

    def test_the_path_starts_on_the_drum(self):
        """경로 시작이 드럼이 아니면 롤이 순간이동한다."""
        start = self._path()[0]
        self.assertAlmostEqual(start["x"], self._expr("WR_DRUM_X"), delta=1e-9)
        self.assertAlmostEqual(start["z"], self._expr("WR_WEB_Z"), delta=1e-9)

    def test_path_and_hud_phases_cannot_drift_apart(self):
        """구간 경계가 문구 경계와 다르면 화면의 롤과 HUD 문구가 어긋난다."""
        marks = set(self._phases())
        for p in self._path():
            self.assertIn(round(p["at"], 6), {round(v, 6) for v in marks},
                          f"경로 경계 {p['at']} 에 대응하는 배출 문구가 없다")

    def test_the_path_only_moves_forward(self):
        """되돌아가는 구간이 있으면 배출이 아니라 왕복이다."""
        ats = [p["at"] for p in self._path()]
        self.assertEqual(ats, sorted(ats), "배출 경로 구간이 시간순이 아니다")

    def test_the_hatch_leaf_opens_only_while_the_roll_passes(self):
        """닫힌 문을 통과하는 그림이 되면 인터록 설명이 무의미해진다."""
        m = re.search(r"box\(V\(HATCH_X,HATCH_Y,HATCH_Z\+\(HATCH_H\*[\d.]+\)\*([\w.]+)\)", self.html)
        self.assertIsNotNone(m, "해치 문짝이 배출 상태를 따라 열리지 않는다")
        self.assertEqual(m.group(1), "wq.pose.inHatch",
                         "해치 개폐가 롤 위치와 다른 값에 묶여 있다")

    def test_the_roll_visibly_turns_while_winding(self):
        """직경은 한 장에 0.07mm 자란다. 회전이 없으면 감기는 것이 안 보인다."""
        m = re.search(r"theta:n\*PANEL_L/Math\.max\(WR_CORE_R,r\)", self.html)
        self.assertIsNotNone(m, "권취 회전각이 감은 길이 ÷ 반지름 에서 나오지 않는다")
        self.assertNotIn("panels*.37", js_code(self.html), "임의값 회전이 남아 있다")
        body = re.search(r"\n    function windingRoll\(.*?\n    \}", self.html, re.S).group(0)
        self.assertIn("ROLL_SEAM_MARKS", body, "회전을 보여줄 표식이 없다")
        self.assertIn("Math.cos(a)", body, "분할클램프가 코어를 따라 공전하지 않는다")

    def test_the_web_shows_which_way_it_runs(self):
        """방향 표시가 없으면 웹이 그냥 걸쳐진 판으로 읽힌다."""
        body = re.search(r"\n    function backsheetWeb\(.*?\n    \}", self.html, re.S).group(0)
        self.assertIn("C.yellow", body, "웹 진행방향 화살표가 없다")
        self.assertRegex(body, r"ph=\(\(panels\*PANEL_L\)/TICK\)%1",
                         "웹 눈금이 감은 길이를 따라 흐르지 않는다")
        # 눈금은 웹의 두 구간(칼날→가이드롤, 가이드롤→드럼) 위에 얹혀야 한다.
        # seg 를 비워 두면 문법은 멀쩡한데 화면에서 흐름이 사라진다.
        self.assertRegex(body, r"const seg=\[\[cut,z0,WR_GUIDE_X[^\]]*\],\[WR_GUIDE_X[^\]]*WR_DRUM_X",
                         "웹 눈금이 실제 웹 구간 위에 얹히지 않는다")
        self.assertIn("of seg", body, "웹 눈금 반복이 없다")

    def test_discharge_substeps_are_readable_without_labels(self):
        """S7 은 3.2초짜리 단계다. 문구가 고정이면 롤이 어디까지 갔는지 알 수 없다."""
        self.assertIn("$('stageTitle').textContent=`S7 · ${w.phase.name}`", self.html,
                      "배출 서브페이즈가 단계 제목에 반영되지 않는다")
        self.assertGreaterEqual(len(self._phases()), 5,
                                "배출 서브페이즈가 너무 성기다")
        self.assertIn("BACKSHEET_BIN_ACK", self.html)

    # ── 반출 기구 ──────────────────────────────────────────────
    def test_the_roll_passes_through_the_enclosure_roll_port(self):
        """외함 정비도어는 z0.6~3.95 통짜 판이다. 포트를 안 내면 롤이 벽을 뚫는다."""
        pts, py = self._path(), self._expr("ROLL_PORT_Y")
        w, x0 = self._expr("ROLL_PORT_W"), self._expr("WR_DRUM_X")
        z0, z1, r = self._expr("ROLL_PORT_Z0"), self._expr("ROLL_PORT_Z1"), self._expr("WR_FULL_R")
        cross = [
            (a["x"] + (b["x"] - a["x"]) * (py - a["y"]) / (b["y"] - a["y"]),
             a["z"] + (b["z"] - a["z"]) * (py - a["y"]) / (b["y"] - a["y"]))
            for a, b in zip(pts, pts[1:])
            if a["y"] != b["y"] and (a["y"] - py) * (b["y"] - py) <= 0
        ]
        self.assertEqual(len(cross), 1, "반출 경로가 외함 벽을 정확히 한 번 지나지 않는다")
        x, z = cross[0]
        self.assertLessEqual(abs(x - x0), w / 2 - r, f"롤이 포트 폭 밖으로 지난다: x={x:.3f}")
        self.assertGreaterEqual(z - r, z0, f"롤이 포트 하단보다 낮게 지난다: z={z:.3f}")
        self.assertLessEqual(z + r, z1, f"롤이 포트 상단보다 높게 지난다: z={z:.3f}")
        body = self._fn("serviceDoor")
        self.assertRegex(
            body, r"port=x0<pl&&pr<x1",
            "롤 포트가 정비도어 베이 범위에서 결정되지 않는다",
        )
        self.assertRegex(body, r"pl=WR_DRUM_X-ROLL_PORT_W/2,pr=WR_DRUM_X\+ROLL_PORT_W/2",
                         "롤 포트가 권취 드럼 축에 맞춰 뚫리지 않는다")
        self.assertRegex(body, r"if\(port&&x>pl-[\d.]+&&x<pr\+[\d.]+\)continue",
                         "롤 포트 안에 멀리언이 그대로 남는다")

    def test_the_transfer_height_clears_the_carrier_rail(self):
        """캐리어 레일(y=-1.38)이 z0.77 까지 차 있다. 롤은 그 위로만 나갈 수 있다."""
        rail = self._expr("RH_RAIL_Z")
        self.assertGreaterEqual(rail, 0.78, "스키드 레일 상면이 캐리어 레일보다 낮다")
        self.assertRegex(self.html, r"RH_CARRY_Z=RH_RAIL_Z\+WR_FULL_R",
                         "반출 높이가 레일 상면 + 롤 반경에서 나오지 않는다")

    def test_the_skid_rails_stop_short_of_the_corner_lift(self):
        """레일을 승강대까지 밀면 내려앉는 롤이 레일을 관통한다."""
        body = self._fn("rollSkid")
        self.assertRegex(body, r"yS=BS_BIN_Y\+ROLL_FACE/2\+[\d.]+",
                         "스키드 레일이 코너 승강대 앞에서 끊기지 않는다")
        face, r = self._expr("ROLL_FACE"), self._expr("WR_FULL_R")
        m = re.search(r"yS=BS_BIN_Y\+ROLL_FACE/2\+([\d.]+)", body)
        self.assertGreater(float(m.group(1)), 0.04,
                           "레일 끝이 안착한 롤의 폭 안에 들어온다")

    def test_the_rack_tie_rails_clear_the_passing_roll(self):
        """종전 z1.46 타이레일은 반출 높이 롤(상단 z1.54)과 겹쳐 있었다."""
        tie = self._expr("BS_TIE_Z")
        top = self._expr("RH_CARRY_Z") + self._expr("WR_FULL_R")
        self.assertGreater(tie - 0.07, top, "보관대 타이레일이 지나가는 롤과 겹친다")

    def test_the_last_leg_rolls_the_roll_across_its_own_axis(self):
        """롤 축은 y 다. 마지막 구간이 y 로 움직이면 축방향으로 밀어야 한다."""
        pts = self._path()
        a, b = pts[-2], pts[-1]
        self.assertAlmostEqual(a["y"], b["y"], delta=1e-9, msg="마지막 구간이 축방향 이동이다")
        self.assertAlmostEqual(a["z"], b["z"], delta=1e-9, msg="마지막 구간이 아직 승강 중이다")
        self.assertGreater(abs(b["x"] - a["x"]), 1.0, "마지막 구간에 굴림 거리가 없다")
        body = self._fn("rollSkid")
        self.assertRegex(
            body, r"box\(V\(.*?,y,BS_ROLL_Z-WR_FULL_R-[\d.]+\),V\(BS_SADDLE_X",
            "굴림 레일 상면이 보관 축높이 − 롤 반경에서 나오지 않는다",
        )

    def test_the_corner_lift_follows_the_roll_down(self):
        """승강 테이블이 고정이면 롤이 테이블을 뚫고 내려간다."""
        body = self._fn("windingRoll")
        self.assertRegex(body, r"box\(V\(xx,BS_BIN_Y,\(\.18\+z-r\)/2\)",
                         "코너 승강 테이블이 롤 밑면을 따라가지 않는다")
        self.assertRegex(body, r"w\.eject>=\.74&&w\.eject<\.92",
                         "승강 테이블이 하강 구간에 떠 있지 않다")


class TestVacuumHoldingForce(unittest.TestCase):
    """흡착패드 면적은 장식이 아니라 유지력 그 자체다.

    패널은 흡착만으로 잡혀 있고 두 칼날의 추력은 전부 패드 마찰로 받는다.
    필요 면적은 A ≥ 2F/(μ·Δp) (사양서 OI-13) 이고, 여기서 부족하면 통과박리
    중에 패널이 미끄러진다 — 그림에서는 아무 표시도 나지 않는 종류의 오류다.

    종전 그림은 3×3 = 9패드 Ø280 이라 추력 상한에서 필요 면적의 0.81배였고,
    제작도 목록은 같은 캐리어의 패드를 18개로 적고 있었다. 표와 그림이 서로
    달랐고 둘 중 하나는 반드시 틀린 상태였다.
    """

    MU, DP = 0.6, 65_000        # 패드 마찰계수 / 진공 차압
    F_HI = 13_370               # OI-01 추력 상한 (N)

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _const(self, name):
        m = re.search(rf"(?:const|,)\s*{name}\s*=\s*(-?[\d.]+)[,;]", self.html)
        self.assertIsNotNone(m, f"상수 {name} 을 찾지 못했다")
        return float(m.group(1))

    def _pads(self):
        return int(self._const("PAD_COLS")), int(self._const("PAD_ROWS")), self._const("PAD_R")

    def test_pad_area_covers_the_upper_thrust_bound(self):
        cols, rows, r = self._pads()
        area = cols * rows * math.pi * r ** 2
        need = 2 * self.F_HI / (self.MU * self.DP)
        self.assertGreater(area, need,
                           f"패드 면적 {area:.3f}m² 가 필요 면적 {need:.3f}m² 에 못 미친다 "
                           "— 추력 상한에서 패널이 미끄러진다")
        self.assertGreater(area / need, 1.2, "여유가 20% 미만이다")

    def test_pad_count_matches_the_fabrication_list(self):
        """표와 그림이 다르면 둘 중 하나는 틀린 것이다."""
        cols, rows, _r = self._pads()
        m = re.search(r"흡착패드×(\d+)", self.html)
        self.assertIsNotNone(m, "제작도 목록에 흡착패드 수량이 없다")
        self.assertEqual(cols * rows, int(m.group(1)),
                         "그림의 패드 수가 제작도 목록과 다르다")

    def test_zones_match_the_zone_instrumentation(self):
        """존마다 압력센서·필터·체크밸브가 하나씩 — 열 하나가 한 존이다."""
        cols, _rows, _r = self._pads()
        self.assertEqual(cols, 6, "6존 진공이라고 적어 두고 존 수가 다르다")
        for part in ("진공압센서×6", "진공필터×6", "체크밸브×6"):
            self.assertIn(part, self.html, f"제작도 목록에 {part} 가 없다")
        body = self._fn("carrier")
        self.assertIn("padXs()", body, "존별 매니폴드가 패드 열에서 유도되지 않는다")

    def test_pads_fit_inside_the_glass_face(self):
        """패드가 유리 밖으로 나가면 흡착이 안 된다."""
        cols, rows, r = self._pads()
        length = self._const("PANEL_L")
        width = self._const("PANEL_W")
        px, py = length / cols, width / rows
        self.assertGreater(px - 2 * r, 0.05, "열 간격이 패드 지름보다 좁다")
        self.assertGreater(py - 2 * r, 0.05, "행 간격이 패드 지름보다 좁다")
        self.assertLess((cols - 1) / 2 * px + r, length / 2, "패드가 패널 길이 밖으로 나간다")
        self.assertLess((rows - 1) / 2 * py + r, width / 2, "패드가 패널 폭 밖으로 나간다")

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)


class TestNamedDevicesAreDrawn(unittest.TestCase):
    """제작도 목록이 부르는 장치는 그림에도 서 있어야 한다.

    목록에만 있고 그림에 없으면, 입찰자는 표를 보고 견적을 내는데 도면에는
    그 자리가 비어 있다. 이 셋은 실제로 그랬던 구간이다 — 투입부는 롤러 베드와
    비전 기둥만, 셀 컨베이어는 벨트만, 검사부는 스캔선만 있었다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)

    def _drawn(self, name):
        """설명 주석과 라벨을 걷어낸 본문 — 장치를 실제로 그리는 줄만 남는다.

        이름이 설명문에만 있어도 통과하면 '그림에 있다'를 못 지킨다. 실제로
        주석만 지워도 시험이 통과한 적이 있어, 그리는 줄에 붙어 있어야만
        인정하도록 좁혔다.
        """
        body = re.sub(r"/\*.*?\*/", "", self._fn(name), flags=re.S)
        body = re.sub(r"label3\([^\n]*", "", body)
        draws = [ln for ln in body.split("\n")
                 if re.search(r"\b(?:box|cylinder|column|plinth|poly|line)\(", ln)]
        return "\n".join(draws)

    def test_infeed_carries_its_listed_devices(self):
        body = self._drawn("infeedStation")
        for token, why in (("폭조절 가이드", "폭조절 가이드"), ("스토퍼", "패널 스토퍼"),
                           ("비전카메라", "2D 비전카메라"), ("높이센서", "레이저 높이센서"),
                           ("바코드 리더", "바코드 리더"), ("광전센서", "광전센서"),
                           ("케이블베어", "케이블베어"), ("기어모터", "IE4 기어모터")):
            self.assertIn(token, body, f"투입부에 {why} 가 없다")
        self.assertIn("infeedStation();", self.html, "투입부가 배치에 놓이지 않았다")

    def test_cell_conveyor_carries_its_listed_devices(self):
        body = self._drawn("cellConveyorDevices")
        for token in ("셀 존재센서", "벨트 편심센서", "금속검출기", "국소배기 노즐",
                      "역화 격리게이트", "토크리미터", "점검커버"):
            self.assertIn(token, body, f"셀 컨베이어에 {token} 가 없다")
        self.assertIn("cellConveyorDevices();", self.html)

    def test_inspection_and_reject_carry_their_listed_devices(self):
        body = self._drawn("inspectionRejectStation")
        for token in ("상부 RGB 카메라", "하부 RGB 카메라", "열화상 카메라", "라인레이저",
                      "투과조명", "검사 엔코더", "RJ 횡셔틀", "받침트레이",
                      "밀폐 리젝트 캐리지", "도어 인터록", "캐리지 존재센서", "재처리 라벨러"):
            self.assertIn(token, body, f"검사·리젝트에 {token} 가 없다")
        self.assertIn("inspectionRejectStation();", self.html)

    def test_the_upgraded_sections_are_no_longer_the_thin_ones(self):
        """장치를 세웠다면 그 구간의 부재 수가 실제로 늘어야 한다."""
        for fn, least in (("infeedStation", 18), ("cellConveyorDevices", 14),
                          ("inspectionRejectStation", 24)):
            body = self._fn(fn)
            drawn = len(re.findall(r"\b(?:box|cylinder|column|plinth|poly)\(", body))
            self.assertGreaterEqual(drawn, least,
                                    f"{fn} 이 그리는 부재가 {drawn}개뿐이다")


if __name__ == "__main__":
    unittest.main()
