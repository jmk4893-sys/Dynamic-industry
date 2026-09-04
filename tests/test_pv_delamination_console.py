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
        # 한 대만 돌린다는 의도는 기동조건이 아니라 상용·예비 선택으로 남아야 한다
        self.assertIn("FAN_DUTY_SELECT", self.html, "상용·예비 절체 조건이 없다")

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
        m = re.search(rf"\b{name}\s*=\s*(-?[\d.]+(?:e-?\d+)?)", self.html)
        self.assertIsNotNone(m, f"상수 {name} 을 찾지 못했다")
        return float(m.group(1))

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
        for call in re.findall(r"windingRoll\(([^)]*)\)", self.html):
            if call.startswith("panels"):        # 정의부
                continue
            self.assertTrue(
                call.startswith("woundCount("),
                f"windingRoll 에 누적 장수가 아닌 값을 넘긴다: {call}",
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
        """웹 반폭 1.2m 옆으로 기둥이 지나면 필름이 기둥에 쓸린다."""
        post = self._const("KNIFE_POST_Y")
        half = self._const("WEB_HALF")
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

    def test_panel_draw_scale_discrepancy_is_declared(self):
        """도면 패널 4800×2400 과 사양 2400×1200 의 차이를 숨기지 않는다."""
        self.assertIn("PANEL_DRAW_SCALE", self.html,
                      "패널 축척 불일치가 코드에 드러나 있지 않다")
        self.assertIn("2400×1200", self.html, "사양 치수가 주석에 없다")

    def test_live_roll_diameter_is_readable_without_turning_on_labels(self):
        """3D 라벨은 기본이 꺼져 있다. 직경이 거기에만 있으면 아무도 못 본다."""
        m = re.search(r"flowBacksheetText'\)\.textContent=(.{0,900})", self.html, re.S)
        self.assertIsNotNone(m)
        self.assertIn("rollRadius", m.group(1),
                      "권취 직경이 항상 보이는 HUD에 나오지 않는다")


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


if __name__ == "__main__":
    unittest.main()
