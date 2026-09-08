"""회사 마크 — 정의는 한 곳, 사본은 시험이 강제.

마크는 지급된 아트워크 symbol_100x100mm.ai 에서 뽑았다. 눈으로 옮겨 그리지
않고 PDF 페이지 콘텐츠 스트림의 경로 연산자(m/l/c/h/f)를 파싱해 좌표를 그대로
가져왔고, 색은 ICCBased CMYK 를 ICC 변환해 확정했다.

표준 정의는 docs/brand/dg-mark.json 하나뿐이다. 콘솔과 사양서는 단독 HTML
문서라 도형을 파일 안에 담아야 하는데, 그렇게 생긴 사본은 손으로 관리하면
반드시 갈라진다 — 갈라져도 화면에는 아무 표시가 나지 않고, 캐비닛의 마크와
화면의 마크가 다른 회사 것이 되어 있을 뿐이다. 그래서 여기서 글자 단위로
대조한다. 사양서 쪽 사본은 tools/render_mark.py 가 기계적으로 심는다.
"""

import json
import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARK_JSON = ROOT / "docs" / "brand" / "dg-mark.json"
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"

BLUE, AMBER = "#228CC9", "#FECA4A"


class TestCanonicalDefinition(unittest.TestCase):
    """표준 정의 자체가 아트워크와 맞는지."""

    @classmethod
    def setUpClass(cls):
        cls.mark = json.loads(MARK_JSON.read_text(encoding="utf-8"))

    def test_the_definition_records_where_it_came_from(self):
        """출처가 없으면 다음 사람이 다시 눈으로 그리게 된다."""
        src = self.mark["source"]
        self.assertEqual(src["file"], "symbol_100x100mm.ai")
        self.assertIn("파싱", src["method"])
        self.assertIn("눈으로 옮겨 그리지 않았다", src["method"])
        self.assertIn("CMYK", src["colourSpace"])

    def test_the_shape_is_four_blue_faces_and_one_amber(self):
        paths = self.mark["paths"]
        self.assertEqual(len(paths), 5)
        fills = [p["fill"] for p in paths]
        self.assertEqual(fills.count(BLUE), 4)
        self.assertEqual(fills.count(AMBER), 1)

    def test_colours_come_from_the_cmyk_in_the_artwork(self):
        """색은 고른 것이 아니라 아트워크의 CMYK 를 변환한 값이다."""
        seen = {}
        for p in self.mark["paths"]:
            seen.setdefault(p["fill"], tuple(p["cmyk"]))
            self.assertEqual(seen[p["fill"]], tuple(p["cmyk"]),
                             "같은 색인데 CMYK 가 다르다")
        self.assertEqual(seen[BLUE], (0.776, 0.342, 0.016, 0.0))
        self.assertEqual(seen[AMBER], (0.0, 0.212, 0.815, 0.0))

    def test_the_view_box_is_the_tight_bounding_box(self):
        """베지어 극점까지 포함한 실제 외곽이어야 여백이 생기지 않는다."""
        vb = self.mark["viewBox"]
        self.assertEqual(vb[0], 0)
        self.assertEqual(vb[1], 0)
        self.assertAlmostEqual(vb[2], 100.0, delta=1e-6)
        self.assertAlmostEqual(vb[3], 88.9723, delta=1e-4)
        xs, ys = [], []
        for p in self.mark["paths"]:
            nums = [float(v) for v in re.findall(r"-?\d*\.?\d+", p["d"])]
            xs += nums[0::2]
            ys += nums[1::2]
        # 제어점은 외곽을 넘을 수 있으나, 실제 극점은 0~vb 안이다
        self.assertLessEqual(max(xs), vb[2] + 0.5)
        self.assertLessEqual(max(ys), vb[3] + 0.5)
        self.assertGreaterEqual(min(xs), -0.5)
        self.assertGreaterEqual(min(ys), -0.5)

    def test_the_curves_survived_the_extraction(self):
        """모서리 라운드가 빠지면 다른 도형이다 — 옛 사본이 그랬다."""
        curved = [p for p in self.mark["paths"] if "C" in p["d"]]
        self.assertEqual(len(curved), 3, "곡선을 가진 경로가 셋이어야 한다")

    def test_the_extraction_was_verified_against_a_render_of_the_original(self):
        """일치율이 기록돼 있지 않으면 '추출했다'는 주장에 근거가 없다."""
        v = self.mark["verification"]
        self.assertGreaterEqual(v["exactPixelMatch"], 0.99,
                                "화소 일치율이 기록값보다 낮다")
        self.assertGreaterEqual(v["shapeMatch"], 0.995)
        self.assertEqual(v["mismatchOnEdge"], 1.0,
                         "불일치가 경계 밖에도 있었다면 형상이 다른 것이다")
        self.assertIn("MuPDF", v["method"])
        self.assertIn("Chromium", v["method"])


class TestEverySurfaceUsesTheOneDefinition(unittest.TestCase):
    """사본이 원본과 글자 단위로 같은지."""

    @classmethod
    def setUpClass(cls):
        cls.mark = json.loads(MARK_JSON.read_text(encoding="utf-8"))
        cls.console = CONSOLE.read_text(encoding="utf-8")
        cls.rfq = RFQ.read_text(encoding="utf-8") if RFQ.exists() else None

    def _paths(self):
        return [(p["fill"], p["d"]) for p in self.mark["paths"]]

    def test_the_console_copy_matches_the_definition(self):
        m = re.search(r"const MARK=\{\s*vb:\[([\d.,]+)\],\s*paths:\[(.*?)\n      \]\s*\n    \};",
                      self.console, re.S)
        self.assertIsNotNone(m, "콘솔에서 MARK 정의를 찾지 못했다")
        vb = [float(v) for v in m.group(1).split(",")]
        self.assertEqual(vb, self.mark["viewBox"][2:],
                         "콘솔 viewBox 가 표준 정의와 다르다")
        got = re.findall(r"\{f:'(#[0-9A-Fa-f]{6})',d:'([^']+)'\}", m.group(2))
        self.assertEqual(got, self._paths(),
                         "콘솔의 마크가 docs/brand/dg-mark.json 과 갈라졌다")

    def test_the_rfq_copy_matches_the_definition(self):
        if self.rfq is None:
            self.skipTest("이 브랜치에는 사양서가 없다")
        m = re.search(r"<!--mark-->(.*?)<!--/mark-->", self.rfq, re.S)
        self.assertIsNotNone(m, "사양서에서 마크 블록을 찾지 못했다 "
                                "(tools/render_mark.py 로 심는다)")
        got = re.findall(r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})"/>', m.group(1))
        self.assertEqual([(f, d) for d, f in got], self._paths(),
                         "사양서의 마크가 docs/brand/dg-mark.json 과 갈라졌다")
        vw, vh = self.mark["viewBox"][2], self.mark["viewBox"][3]
        self.assertIn(f'viewBox="0 0 {vw} {vh}" aria-label="DYNAMIC INDUSTRY"', self.rfq,
                      "사양서 마크의 viewBox 가 표준 정의와 다르다")

    def test_no_document_carries_a_second_hand_drawn_mark(self):
        """옛 마크가 어딘가 남아 있으면 그 화면만 다른 로고를 달게 된다."""
        docs = [("콘솔", self.console)] + ([("사양서", self.rfq)] if self.rfq else [])
        for name, html in docs:
            for stale in ("#268cca", "#fdca4a", "34.2,0 69.9,0"):
                self.assertNotIn(stale, html, f"{name} 에 옛 마크 흔적 {stale}")
            for _f, d in self._paths():
                self.assertEqual(html.count(d), 1,
                                 f"{name} 에 마크 경로가 두 번 이상 적혀 있다")

    def test_the_generator_reports_the_documents_are_in_sync(self):
        """tools/render_mark.py --check 가 CI 에서 갈라짐을 잡는다."""
        import subprocess, sys
        r = subprocess.run([sys.executable, "tools/render_mark.py", "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         f"정적 문서의 마크가 표준 정의와 다르다:\n{r.stderr}")


if __name__ == "__main__":
    unittest.main()
