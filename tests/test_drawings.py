"""설계도(docs/drawings/)가 코드 산출값과 어긋나지 않는지 검증.

도면에는 치수·유량·성능 수치가 문자열로 박혀 있다. `design_basis.py` 를 고치고
도면을 갱신하지 않으면 도면과 계산서가 서로 다른 설비를 가리키게 되므로,
주요 수치가 코드 산출값과 일치하는지 확인한다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design.rfc import rfc_separation, size_rfc

DRAWING = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs"
    / "drawings"
    / "ag-flotation-drawings.html"
)


class TestDrawingDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = DRAWING.read_text(encoding="utf-8")

    def test_exists_and_is_standalone(self):
        self.assertTrue(DRAWING.exists())
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        for tag in ("<html lang=\"ko\">", "<head>", "</head>", "<body>", "</body>", "</html>"):
            self.assertIn(tag, self.html, tag)

    def test_declares_utf8(self):
        # 한글 도면이라 charset 이 빠지면 브라우저에서 깨진다.
        self.assertIn('<meta charset="utf-8">', self.html)

    def test_has_title_and_viewport(self):
        self.assertIn("<title>태양광 셀 Ag 회수 설계도</title>", self.html)
        self.assertIn('name="viewport"', self.html)

    def test_container_tags_balance(self):
        for tag in ("svg", "figure", "section", "table", "defs", "g", "style", "div"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_three_sheets_present(self):
        for no in ("DWG-001", "DWG-002", "DWG-003"):
            self.assertIn(no, self.html, no)
        self.assertEqual(len(re.findall(r"<svg", self.html)), 3)

    def test_every_figure_is_labelled_for_screen_readers(self):
        self.assertEqual(len(re.findall(r'role="img"', self.html)), 3)
        self.assertEqual(len(re.findall(r"aria-label=", self.html)), 3)
        self.assertEqual(len(re.findall(r"<figcaption>", self.html)), 3)

    def test_no_external_assets_beyond_google_fonts(self):
        for url in re.findall(r'https?://[^"\')\s]+', self.html):
            self.assertTrue(
                url.startswith("https://fonts.googleapis.com")
                or url.startswith("https://fonts.gstatic.com"),
                f"CSP 상 차단되는 외부 리소스: {url}",
            )

    def test_theme_tokens_cover_all_three_states(self):
        self.assertIn("@media (prefers-color-scheme: dark)", self.html)
        self.assertIn(':root:not([data-theme="light"])', self.html)
        self.assertIn(':root[data-theme="dark"]', self.html)


class TestDrawingMatchesDesign(unittest.TestCase):
    """도면에 박힌 수치가 코드 산출값과 같은지."""

    @classmethod
    def setUpClass(cls):
        cls.html = DRAWING.read_text(encoding="utf-8")
        sg = db.FEED.solids_specific_gravity
        cls.rfc = size_rfc(
            db.RFC_TAG, db.RFC_DUTY, db.FEED.peak_tph, sg, db.DESIGN_SOLIDS_WT
        )
        cls.perf = rfc_separation(
            db.FEED.component_tph(db.FEED.peak_tph),
            db.FLOAT_MODELS,
            db.RFC_AG_RECOVERY,
            db.COMPOSITE_CARRY_RATIO,
        )

    def assertFigure(self, text: str, label: str):
        # assertIn 은 실패 시 문서 전체를 덤프하므로 메시지를 직접 만든다.
        self.assertTrue(
            text in self.html,
            f"{label} 이(가) 도면과 불일치 — 도면에 '{text}' 가 없음. "
            f"design_basis.py 를 고쳤다면 도면도 갱신할 것.",
        )

    def test_vessel_diameter(self):
        self.assertFigure(f"Ø{self.rfc.diameter_m * 1000:.0f}", "동체 내경")

    def test_riser_height(self):
        self.assertFigure(f"{self.rfc.riser_height_m:.2f} m", "라이저 높이")

    def test_design_fluxes(self):
        self.assertFigure(f"{self.rfc.feed_flux_cm_s:.2f} cm/s", "급광 flux")
        self.assertFigure(f"{self.rfc.wash_water_flux_cm_s:.2f} cm/s", "세척수 flux")
        self.assertFigure(f"{self.rfc.bias_flux_cm_s:.2f} cm/s", "bias flux")

    def test_stream_flows(self):
        self.assertFigure(f"{self.rfc.feed_m3h:.2f} m³/h", "급광 유량")
        self.assertFigure(f"{self.rfc.wash_water_m3h:.2f} m³/h", "세척수 유량")
        self.assertFigure(f"{self.rfc.overflow_water_m3h:.2f} m³/h", "월류수 유량")

    def test_throughput(self):
        self.assertFigure(
            f"{db.FEED.average_tph:.2f} / {db.FEED.peak_tph:.2f} t/h", "처리량"
        )
        self.assertFigure(f"{self.perf.feed_dry_tph * 1000:.0f} kg/h", "급광 고체")

    def test_concentrate_figures(self):
        self.assertFigure(
            f"{self.perf.concentrate_dry_tph * 1000:.2f} kg/h", "정광 고체 유량"
        )
        self.assertFigure(
            f"{self.perf.concentrate_grade('Ag') * 100:.1f} wt% Ag", "정광 Ag 품위"
        )

    def test_tailings_figures(self):
        tail_kgh = self.perf.tailings_dry_tph * 1000
        self.assertFigure(f"{tail_kgh:.0f} kg/h", "미광 고체 유량 (흐름 라벨)")
        self.assertFigure(f'<td class="num">{tail_kgh:.1f}</td>', "미광 고체 유량 (수지표)")
        self.assertFigure(
            f"{self.perf.tailings_grade('Ag') * 1e6:.0f} g/t", "미광 Ag 품위"
        )

    def test_recovery(self):
        self.assertFigure(f"{self.perf.recovery('Ag') * 100:.1f} %", "Ag 회수율")

    def test_feed_grade(self):
        self.assertFigure(f"{db.FEED.grade_ppm('Ag'):,.0f} g/t", "급광 Ag 품위")

    def test_solids_concentration(self):
        self.assertFigure(f"{db.DESIGN_SOLIDS_WT * 100:.0f} wt%", "설계 고체 농도")

    def test_composite_carry_limit_is_stated(self):
        limit = 1.0 / (1.0 + db.COMPOSITE_CARRY_RATIO)
        self.assertFigure(f"{limit * 100:.1f} wt%", "복합입자 품위 상한")

    def test_inclined_channel_spec(self):
        self.assertFigure(
            f"{self.rfc.inclined_channel_angle_deg:.0f}° / "
            f"{self.rfc.inclined_channel_spacing_mm:.0f} mm",
            "경사판 사양",
        )

    def test_patent_disclosure_present(self):
        # 실시권 리스크는 도면에서 빠지면 안 되는 항목이다.
        self.assertIn("2025902821", self.html)


if __name__ == "__main__":
    unittest.main()
