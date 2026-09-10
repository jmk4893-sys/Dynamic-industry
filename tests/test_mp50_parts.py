"""MP-50 부품 상세 도면집(docs/drawings/mp-50-parts.html) 검증.

제작도 MP-50-P0-001 의 상세 패널 B~Q 16 매를 2D 정투상도와 3D 로 나란히 그린
단일 HTML 이다. 두 그림이 **같은 치수 상수**에서 나오는 것이 이 도면집의 전제이므로,
상수 선언과 본문 표기가 어긋나지 않는지 여기서 잡는다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

from .test_drawings import standalone_document_checks

PARTS = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "mp-50-parts.html"
)
TITLE = "MP-50 부품 상세 도면집"

# 제작도 상세 패널 — 부호, 품번, 품명, 수량
PANELS = [
    ("B", "08", "탱크 쉘", "1"),
    ("C", "04", "상부 커버", "1"),
    ("D", "06", "맨홀", "1"),
    ("E", "11", "교반축", "1"),
    ("F", "12", "임펠러 (상/하)", "2"),
    ("G", "13", "배플", "4"),
    ("H", "14", "미세기포 분산기", "1"),
    ("I", "15", "하부 콘", "1"),
    ("J", "16", "하부 배출구", "1식"),
    ("K", "17", "지지 다리", "3"),
    ("L", "28", "앵커볼트", "3"),
    ("M", "05", "볼트 · 너트 · 와셔", "1식"),
    ("N", "26", "가스켓 · 씰", "1식"),
    ("O", "23", "배관 및 밸브", "1식"),
    ("P", "22", "제어반", "1"),
    ("Q", "30", "방진패드", "3"),
]

SHEET_HEAD = re.compile(
    r'code:"([A-Q])", no:"(\d\d)", name:"([^"]+)", qty:"([^"]+)", panel:"([^"]+)"'
)
ID_REF = re.compile(r"""\$\(\s*["']([A-Za-z][\w-]*)["']\s*\)""")
ID_DEF = re.compile(r"""\bid=["']([A-Za-z][\w-]*)["']""")


def consts(html):
    """`var NAME=123, OTHER=45;` 형태의 치수 상수를 읽는다."""
    out = {}
    for name, val in re.findall(r"\b([A-Z][A-Z0-9_]{1,9})\s*=\s*(-?\d+(?:\.\d+)?)", html):
        out.setdefault(name, float(val))
    return out


class TestPartsDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지 — 도면 네 건과 같은 규약."""

    @classmethod
    def setUpClass(cls):
        cls.html = PARTS.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(PARTS.exists())
        standalone_document_checks(self, self.html, TITLE)

    def test_no_external_library(self):
        # 2D 는 직접 만든 SVG, 3D 는 직접 쓴 WebGL — 아티팩트 CSP 는 CDN 을 막는다.
        for banned in ("three.min.js", "three.module", "babylon", "d3.js",
                       "unpkg.com", "cdn."):
            self.assertNotIn(banned, self.html, banned)
        self.assertIn('getContext("webgl"', self.html)

    def test_2d_survives_without_webgl(self):
        # WebGL 이 없어도 2D 상세도는 그려져야 한다 — SVG 는 GL 과 무관하다.
        self.assertIn("var ok=!!gl;", self.html)
        self.assertIn("if(ok) requestAnimationFrame(frame);", self.html)
        self.assertIn('id="fallback"', self.html)
        # 시트 전환은 GL 여부와 상관없이 돈다.
        self.assertIn("buildIndex(); go(0);", self.html)

    def test_container_tags_balance(self):
        for tag in ("div", "section", "table", "style", "script", "header", "svg", "ol"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_every_referenced_id_exists(self):
        defined = set(ID_DEF.findall(self.html))
        for name in sorted(set(ID_REF.findall(self.html))):
            self.assertIn(name, defined, f"$('{name}') 대상이 없음")

    def test_controls_are_labelled(self):
        for probe in ('aria-label="상세 시트 선택"', 'aria-label="이전 시트"',
                      'aria-label="다음 시트"', 'aria-pressed'):
            self.assertIn(probe, self.html, probe)

    def test_respects_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.html)


class TestSheets(unittest.TestCase):
    """상세 패널 16 매가 모두, 도면 그대로 있는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = PARTS.read_text(encoding="utf-8")
        cls.heads = SHEET_HEAD.findall(cls.html)

    def test_sixteen_sheets(self):
        self.assertEqual(len(self.heads), 16)

    def test_panel_codes_numbers_names_and_quantities(self):
        got = [(c, no, nm, q) for c, no, nm, q, _p in self.heads]
        self.assertEqual(got, PANELS)

    def test_every_sheet_has_2d_and_3d_and_text(self):
        blocks = self.html.split("sheet({")[1:]
        self.assertEqual(len(blocks), 16)
        for blk, (code, _no, name, _q) in zip(blocks, PANELS):
            for key in ("d2:function()", "d3:function()", "spec:[", "note:",
                        "mat:", "fit:"):
                self.assertIn(key, blk, f"{code} {name} — {key} 없음")
            # 2D 는 반드시 aria-label 을 단 SVG 를 돌려준다.
            self.assertIn("return s.svg(", blk, f"{code} {name} — svg 반환 없음")

    def test_every_sheet_dimensions_its_3d(self):
        # 3D 도 치수를 기입한다 — dim3 / dia3 / lead3 중 하나는 있어야 한다.
        blocks = self.html.split("sheet({")[1:]
        for blk, (code, _no, name, _q) in zip(blocks, PANELS):
            d3 = blk.split("d3:function(){")[1]
            self.assertTrue(
                any(f in d3 for f in ("dim3(", "dia3(", "lead3(")),
                f"{code} {name} — 3D 치수가 없음",
            )

    def test_drawing_line_types_are_defined(self):
        # KS A ISO 128 — 외형선 / 숨은선 / 중심선 / 치수선
        for cls_ in ("svg .ol{", "svg .hd{", "svg .cn{", "svg .dm{"):
            self.assertIn(cls_, self.html, cls_)
        self.assertIn("stroke-dasharray:14 3 2 3", self.html)   # 일점쇄선
        self.assertIn("vector-effect:non-scaling-stroke", self.html)

    def test_viewbox_is_measured_not_guessed(self):
        # 손으로 잡은 뷰박스는 치수 문자 길이를 못 맞춰 잘린다.
        self.assertIn("function fitSvg()", self.html)
        self.assertIn("getBBox()", self.html)
        self.assertIn("document.fonts.ready.then(fitSvg)", self.html)


class TestFiguresComeFromConstants(unittest.TestCase):
    """2D 와 3D 가 같은 치수 상수를 쓰는지 — 상수와 본문 표기의 대조."""

    @classmethod
    def setUpClass(cls):
        cls.html = PARTS.read_text(encoding="utf-8")
        cls.c = consts(cls.html)

    def assertConst(self, name, value):
        self.assertIn(name, self.c, f"치수 상수 {name} 이(가) 없음")
        self.assertEqual(self.c[name], value,
                         f"{name} 이(가) 제작도와 다름 ({self.c[name]} ≠ {value})")

    def test_tank_constants(self):
        self.assertConst("TK_OD", 400); self.assertConst("TK_T", 3)
        self.assertConst("TK_H", 600); self.assertConst("CN_H", 150)
        self.assertConst("CN_OUT", 38); self.assertConst("FL_T", 12)
        self.assertConst("PCD", 360); self.assertConst("PCD_D", 9)

    def test_cover_and_manhole_constants(self):
        self.assertConst("CV_T", 5); self.assertConst("MH_OD", 120)
        self.assertConst("MH_ID", 104); self.assertConst("SK_OD", 55)
        self.assertConst("BOSS_H", 20)

    def test_shaft_and_impeller_constants(self):
        self.assertConst("SH_D", 25); self.assertConst("SH_L", 800)
        self.assertConst("KEY_T", 5); self.assertConst("KEY_I", 6)
        self.assertConst("SH_M", 20)
        self.assertConst("IM_D", 300); self.assertConst("IM_T", 3)
        self.assertConst("IM_UPH", 80); self.assertConst("IM_LOH", 13)

    def test_sparger_constants(self):
        self.assertConst("RG_D", 250); self.assertConst("RG_TUBE", 20)
        self.assertConst("RG_HOLE", 2); self.assertConst("RG_N", 60)
        self.assertConst("RG_CB", 3)

    def test_cone_flange_and_leg_constants(self):
        self.assertConst("CF_OD", 110); self.assertConst("CF_T", 8)
        self.assertConst("CF_PCD", 70); self.assertConst("CF_HD", 11)
        self.assertConst("CF_N", 4)
        self.assertConst("LG_D", 38); self.assertConst("LG_L", 200)
        self.assertConst("LG_BASE", 100); self.assertConst("LG_PCD", 70)

    def test_anchor_and_panel_and_pad_constants(self):
        self.assertConst("AN_M", 10); self.assertConst("AN_L", 110)
        self.assertConst("AN_EMB", 100); self.assertConst("AN_PRJ", 23)
        self.assertConst("CP_W", 300); self.assertConst("CP_H", 400)
        self.assertConst("CP_D", 200)
        self.assertConst("PD_D", 100); self.assertConst("PD_H", 30)

    def test_piping_constants(self):
        self.assertConst("BV_L", 65); self.assertConst("RM_D", 34)
        self.assertConst("RM_L", 200); self.assertConst("FR_D", 68)
        self.assertConst("FR_L", 150); self.assertConst("HB_HEX", 24)
        self.assertConst("TC_D", 120)

    def test_stated_figures_match_the_constants(self):
        c = self.c
        for text, label in [
            (f'"Ø{c["TK_OD"]:.0f} × t{c["TK_T"]:.0f}"', "동체 규격"),
            (f'"Ø{c["IM_D"]:.0f} (상 · 하 공통)"', "임펠러 직경"),
            (f'"Ø{c["SH_D"]:.0f} × {c["SH_L"]:.0f}"', "교반축 규격"),
            (f'"Ø{c["RG_D"]:.0f}"', "분산기 링 직경"),
            (f'"Ø{c["RG_HOLE"]:.0f} × {c["RG_N"]:.0f} 개"', "분사홀"),
            (f'"Ø{c["LG_D"]:.0f} × {c["LG_L"]:.0f}"', "다리 파이프"),
            (f'"Ø{c["PD_D"]:.0f} × {c["PD_H"]:.0f}"', "방진패드"),
            (f'"M{c["AN_M"]:.0f} × {c["AN_L"]:.0f}"', "앵커볼트"),
        ]:
            self.assertIn(text, self.html, f"{label} 표기가 상수와 불일치 — {text}")

    def test_sparger_hole_area_is_stated(self):
        import math
        area = self.c["RG_N"] * math.pi / 4 * self.c["RG_HOLE"] ** 2
        self.assertIn(f"{area:.1f} mm²", self.html, "총 홀 면적")


class TestReviewFlags(unittest.TestCase):
    """조립도와 값이 다른 시트에는 반드시 지적 표시가 붙어야 한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = PARTS.read_text(encoding="utf-8")

    def test_three_sheets_carry_a_flag(self):
        # G 배플(폭 200) · I 하부 콘(60°) · J 배출구 / K 다리(200)
        self.assertEqual(len(re.findall(r"\bwarn:\{", self.html)), 4)

    def test_flags_name_the_finding(self):
        for probe in ("도면 지적 01", "도면 지적 02", "도면 지적 03"):
            self.assertIn(probe, self.html, probe)

    def test_baffle_height_dimension_error_is_recorded(self):
        # 원도의 높이 치수선에 두께값 t2 가 들어가 있다 (지적 08).
        self.assertIn("높이 치수선에 두께값 t2", self.html)

    def test_detail_sheets_state_they_follow_the_drawing(self):
        self.assertIn("상세 시트는 도면 표기값을 그대로 그린다", self.html)


if __name__ == "__main__":
    unittest.main()
