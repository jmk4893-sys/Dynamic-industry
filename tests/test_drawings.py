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

DRAWINGS_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings"
DRAWING = DRAWINGS_DIR / "ag-flotation-drawings.html"
MODEL_3D = DRAWINGS_DIR / "ag-flotation-3d.html"


def standalone_document_checks(case, html, title):
    """단독 HTML 문서로서 성립하는지 — 두 도면 파일에 공통."""
    case.assertTrue(html.lstrip().lower().startswith("<!doctype html>"))
    for tag in ('<html lang="ko">', "<head>", "</head>", "<body>", "</body>", "</html>"):
        case.assertIn(tag, html, tag)
    case.assertIn('<meta charset="utf-8">', html)   # 한글 도면 — 빠지면 깨진다
    case.assertIn('name="viewport"', html)
    case.assertIn("<title>" + title + "</title>", html)
    for url in re.findall(r'https?://[^"\')\s]+', html):
        case.assertTrue(
            url.startswith("https://fonts.googleapis.com")
            or url.startswith("https://fonts.gstatic.com"),
            f"CSP 상 차단되는 외부 리소스: {url}",
        )
    case.assertIn("@media (prefers-color-scheme: dark)", html)
    case.assertIn(':root:not([data-theme="light"])', html)
    case.assertIn(':root[data-theme="dark"]', html)


class TestDrawingDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = DRAWING.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(DRAWING.exists())
        standalone_document_checks(self, self.html, "태양광 셀 Ag 회수 설계도")

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


class TestModel3dDocument(unittest.TestCase):
    """3D 컷어웨이 모델 — 단독 HTML 로서의 성립과 자립성."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL_3D.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(MODEL_3D.exists())
        standalone_document_checks(self, self.html, "Ag 부선조 3D 컷어웨이")

    def test_no_external_3d_library(self):
        # WebGL 을 직접 쓴다 — 아티팩트 CSP 는 CDN 을 막으므로 라이브러리 반입 금지.
        for banned in ("three.min.js", "three.module", "babylon", "unpkg.com", "cdn."):
            self.assertNotIn(banned, self.html, banned)
        self.assertIn('getContext("webgl"', self.html)

    def test_has_webgl_fallback(self):
        self.assertIn('id="fallback"', self.html)
        self.assertIn("WebGL", self.html)

    def test_builds_both_vessels(self):
        self.assertIn("function buildFC101()", self.html)
        self.assertIn("function buildFC201()", self.html)

    def test_respects_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.html)

    def test_controls_are_labelled(self):
        for probe in ('aria-label="장치 선택"', 'aria-label="컷어웨이 정도"', 'aria-pressed'):
            self.assertIn(probe, self.html, probe)

    def test_container_tags_balance(self):
        for tag in ("div", "section", "table", "style", "script", "header"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")


class TestModel3dMatchesDesign(unittest.TestCase):
    """3D 모델에 표기된 수치가 코드 산출값과 같은지."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL_3D.read_text(encoding="utf-8")
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

    def assertFigure(self, text, label):
        self.assertTrue(
            text in self.html,
            f"{label} 이(가) 3D 모델과 불일치 — '{text}' 가 없음. "
            f"design_basis.py 를 고쳤다면 모델 수치도 갱신할 것.",
        )

    def test_vessel_geometry(self):
        self.assertFigure(f"Ø{self.rfc.diameter_m * 1000:.0f} mm", "FC-101 동체 내경")
        self.assertFigure(f"{self.rfc.riser_height_m:.2f} m", "라이저 높이")

    def test_design_fluxes(self):
        self.assertFigure(f"{self.rfc.feed_flux_cm_s:.2f} cm/s", "급광 flux")
        self.assertFigure(f"{self.rfc.wash_water_flux_cm_s:.2f} cm/s", "세척수 flux")
        self.assertFigure(f"{self.rfc.bias_flux_cm_s:.2f} cm/s", "bias flux")
        self.assertFigure(f"{self.rfc.feed_m3h:.2f} m³/h", "급광 유량")
        self.assertFigure(f"{self.rfc.wash_water_m3h:.2f} m³/h", "세척수 유량")

    def test_performance_figures(self):
        self.assertFigure(f"{self.perf.recovery('Ag') * 100:.1f} %", "Ag 회수율")
        self.assertFigure(
            f"{self.perf.concentrate_dry_tph * 1000:.2f} kg/h @ "
            f"{self.perf.concentrate_grade('Ag') * 100:.1f} wt% Ag",
            "정광",
        )
        self.assertFigure(
            f"{self.perf.tailings_grade('Ag') * 1e6:.0f} g/t", "미광 Ag 품위"
        )

    def test_mechanical_alternative_figures(self):
        rougher = db.ROUGHER_CELL
        self.assertFigure(
            f"{rougher.width_m * 1000:.0f} × {rougher.width_m * 1000:.0f} × "
            f"{rougher.shell_height_m * 1000:.0f} mm",
            "FC-201 내부 치수",
        )
        self.assertFigure(
            f"{rougher.froth_depth_m * 1000:.0f} mm", "FC-201 거품층"
        )

    def test_inclined_channel_spec(self):
        self.assertFigure(
            f"{self.rfc.inclined_channel_angle_deg:.0f}° / "
            f"{self.rfc.inclined_channel_spacing_mm:.0f} mm",
            "경사판 사양",
        )

    def test_states_it_is_not_a_cad_model(self):
        # 개략 형상임을 모델 주기에 반드시 남긴다.
        self.assertIn("제작용 CAD 모델이 아니며", self.html)
