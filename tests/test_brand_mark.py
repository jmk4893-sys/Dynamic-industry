"""회사 심볼 마크가 **한 곳에만** 정의돼 있고, 콘솔 SVG 와 3D 외장이 같은 도형을 쓰는지 검증.

마크는 원본 아트워크(`docs/drawings/brand/symbol_100x100mm.ai`)에서 추출해
`docs/drawings/brand/brand-mark.json` 에 남겼고, 미니앱의 `BRAND_MARK` 가 그 사본이다.
사본이 원본과 어긋나거나, 어느 한쪽이 자기 좌표를 따로 들고 있으면 여기서 실패한다.

추출·화소대조를 다시 돌리려면:

    python3 docs/drawings/brand/extract-brand-mark.py --verify
"""

import json
import pathlib
import re
import unittest

from . import _path  # noqa: F401

DRAWINGS_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings"
MINIAPP = DRAWINGS_DIR / "pv-recycling-miniapp.html"
BRAND_DIR = DRAWINGS_DIR / "brand"
MARK_JSON = BRAND_DIR / "brand-mark.json"
ARTWORK = BRAND_DIR / "symbol_100x100mm.ai"
EXTRACTOR = BRAND_DIR / "extract-brand-mark.py"

# BRAND_MARK 선언 블록만 떼어낸다.
BLOCK_RE = re.compile(
    r"const BRAND_MARK = Object\.freeze\(\{(?P<body>.*?)\n    \}\);", re.S)
PATH_RE = re.compile(r'\{ d: "(?P<d>[^"]+)", fill: "(?P<fill>#[0-9A-F]{6})" \}')
VIEWBOX_RE = re.compile(r"viewBox: Object\.freeze\(\[([^\]]+)\]\)")


def read(path):
    return path.read_text(encoding="utf-8")


class BrandMarkSourceTest(unittest.TestCase):
    """원본 아트워크 → JSON → 미니앱 상수로 이어지는 출처가 끊기지 않았는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read(MINIAPP)
        cls.mark = json.loads(read(MARK_JSON))
        block = BLOCK_RE.search(cls.html)
        assert block, "미니앱에 BRAND_MARK 선언이 없다"
        cls.block = block.group("body")

    def test_artwork_and_extractor_are_committed(self):
        """추출을 다시 돌릴 수 있어야 출처가 검증 가능하다."""
        self.assertTrue(ARTWORK.exists(), "원본 아트워크가 저장소에 없다")
        self.assertGreater(ARTWORK.stat().st_size, 100_000)
        self.assertTrue(EXTRACTOR.exists(), "추출 스크립트가 저장소에 없다")
        self.assertIn("get_drawings()", read(EXTRACTOR),
                      "추출은 PDF 패스를 직접 읽어야 한다 — 눈으로 따라 그린 값이면 안 된다")

    def test_extraction_was_pixel_verified(self):
        """추출 벡터를 다시 래스터화해 원본과 대조한 결과가 기록돼 있는지."""
        match = self.mark["provenance"]["match"]
        # 렌더러가 달라(MuPDF vs Skia) 경계 화소의 안티앨리어싱은 일치하지 않는다.
        # 형상 일치의 판정은 "경계에서 떨어진 곳의 불일치가 0" 이다.
        self.assertEqual(match["mismatchedPixelsAwayFromEdges"], 0)
        self.assertGreaterEqual(match["inkAreaIoU"], 0.999)
        self.assertGreaterEqual(match["blueIoU"], 0.999)
        self.assertGreaterEqual(match["amberIoU"], 0.999)
        self.assertGreaterEqual(match["pixelsWithinTolerance2of255"], 0.99)
        self.assertLessEqual(match["meanAbsErrorPerChannel"], 1.0)

    def test_miniapp_copy_matches_the_extracted_mark(self):
        """미니앱 상수가 JSON 과 글자 단위로 같은지 — 어느 한쪽만 고치면 실패한다."""
        viewbox = VIEWBOX_RE.search(self.block)
        self.assertIsNotNone(viewbox, "BRAND_MARK.viewBox 가 없다")
        self.assertEqual([float(v) for v in viewbox.group(1).split(",")],
                         [float(v) for v in self.mark["viewBox"]])
        found = [(m.group("d"), m.group("fill")) for m in PATH_RE.finditer(self.block)]
        expected = [(p["d"], p["fill"]) for p in self.mark["paths"]]
        self.assertEqual(found, expected, "미니앱 BRAND_MARK 가 brand-mark.json 과 다르다")
        self.assertEqual(len(found), 5, "원본 아트워크는 채움 패스 5개다")

    def test_mark_is_defined_exactly_once(self):
        """같은 좌표가 두 군데 있으면 '한 곳에만 정의' 가 깨진다."""
        self.assertEqual(len(BLOCK_RE.findall(self.html)), 1)
        for path in self.mark["paths"]:
            self.assertEqual(self.html.count(path["d"]), 1,
                             "패스 데이터가 두 번 이상 나타난다: " + path["d"][:40])
        outside = BLOCK_RE.sub("", self.html)
        for name, value in self.mark["colors"].items():
            self.assertNotIn(value, outside,
                             f"브랜드 색 {name}({value}) 이 BRAND_MARK 밖에도 있다")
        # 블록 안에서는 채움 수만큼 나온다 — 파랑 4 · 황색 1
        counts = {}
        for path in self.mark["paths"]:
            counts[path["fill"]] = counts.get(path["fill"], 0) + 1
        for fill, times in counts.items():
            self.assertEqual(self.html.count(fill), times)


class BrandMarkConsumerTest(unittest.TestCase):
    """콘솔 SVG 와 3D 외장이 그 하나만 읽는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read(MINIAPP)

    def function_body(self, name):
        start = self.html.index("function " + name + "(")
        depth, i = 0, self.html.index("{", start)
        for j in range(i, len(self.html)):
            if self.html[j] == "{":
                depth += 1
            elif self.html[j] == "}":
                depth -= 1
                if depth == 0:
                    return self.html[start:j + 1]
        raise AssertionError(name + " 의 본문을 찾지 못했다")

    def test_console_svg_is_built_from_the_shared_mark(self):
        body = self.function_body("brandMarkSvg")
        self.assertIn("BRAND_MARK.viewBox", body)
        self.assertIn("BRAND_MARK.paths", body)
        # 자기 좌표를 들고 있으면 안 된다
        self.assertNotRegex(body, r'd="M[\d.]', "콘솔 SVG 가 패스 좌표를 직접 들고 있다")
        self.assertNotRegex(body, r"#[0-9A-Fa-f]{6}", "콘솔 SVG 가 색을 직접 들고 있다")

    def test_3d_shapes_are_built_from_the_shared_mark(self):
        body = self.function_body("brandMarkShapes")
        self.assertIn("BRAND_MARK.viewBox", body)
        self.assertIn("BRAND_MARK.paths", body)
        self.assertIn("THREE.Shape", body)
        self.assertNotRegex(body, r"\bM[\d.]+,[\d.]+", "3D 형상이 패스 좌표를 직접 들고 있다")
        self.assertNotRegex(body, r"#[0-9A-Fa-f]{6}", "3D 형상이 색을 직접 들고 있다")
        # 원본이 쓰는 명령 넷을 전부 다룬다
        for command in ('"M"', '"L"', '"C"'):
            self.assertIn(command, body)
        self.assertIn("closePath", body)

    def test_3d_decal_extrudes_those_shapes(self):
        body = self.function_body("addBrandMark")
        self.assertIn("brandMarkShapes()", body)
        self.assertIn("ExtrudeGeometry", body)
        self.assertIn("brandMarkMaterial", body)

    def test_3d_material_colour_comes_from_the_mark(self):
        body = self.function_body("brandMarkMaterial")
        self.assertIn("parseInt(fill", body)
        self.assertNotRegex(body, r"0x[0-9A-Fa-f]{6}", "3D 재질이 색을 직접 들고 있다")

    def test_both_consumers_are_actually_used(self):
        """정의만 있고 아무 데도 안 붙으면 의미가 없다 — 콘솔과 장비 양쪽에 붙어야 한다."""
        self.assertGreaterEqual(self.html.count('data-brand-mark="'), 2,
                                "콘솔에 마크 자리가 없다")
        self.assertIn("brandMarkSvg(Number(node.dataset.brandMark)", self.html,
                      "콘솔 마크 자리를 채우는 코드가 없다")
        calls = re.findall(r'addBrandMark\(([^,]+), "([^"]+)"', self.html)
        dry = [c for c in calls if re.fullmatch(r"P\d+", c[1])]
        wet = [c for c in calls if not re.fullmatch(r"P\d+", c[1])]
        self.assertGreaterEqual(len(dry), 3, "건식 장비에 붙은 마크가 3개 미만이다")
        self.assertGreaterEqual(len(wet), 3, "습식·야드 장비에 붙은 마크가 3개 미만이다")
        self.assertEqual(len(calls), len(set(calls)), "같은 자리에 두 번 붙었다")

    def test_wet_marks_carry_the_wet_identity(self):
        """습식 메시는 partId 가 아니라 unifiedName 으로 식별되고 클릭 대상이 아니다.

        없는 부품 ID 를 달아 두면 명판을 클릭했을 때 존재하지 않는 부품을 고르려 든다.
        """
        body = self.function_body("addBrandMark")
        self.assertIn("mesh.userData.unifiedName = tag", body)
        self.assertIn("delete mesh.userData.partId", body)
        self.assertIn("selectables.splice", body, "습식 마크가 클릭 대상에서 빠지지 않는다")

    def test_wet_marks_explode_with_their_host(self):
        """분해 화면에서 명판만 장비에서 떨어져 나가면 안 된다."""
        self.assertIn("child.userData.brandMarkHost", self.html)
        self.assertIn("host.userData.explodeDirection", self.html)
        hosts = re.findall(r"addBrandMark\(unifiedWet, \"[^\"]+\"[^;]*?, (\w+)\);", self.html)
        self.assertGreaterEqual(len(hosts), 2,
                                "unifiedWet 직속 명판은 host 를 넘겨 장비를 따라가야 한다")


if __name__ == "__main__":
    unittest.main()
