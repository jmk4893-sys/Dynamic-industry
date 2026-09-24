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

    def test_ten_sheets_present(self):
        for no in ("DWG-001", "DWG-002", "DWG-003", "DWG-004", "DWG-005",
                   "DWG-006", "DWG-007", "DWG-008", "DWG-009", "DWG-010"):
            self.assertIn(no, self.html, no)
        self.assertEqual(len(re.findall(r"<svg", self.html)), 10)
        self.assertIn("10매로 구성한다", self.html)

    def test_every_figure_is_labelled_for_screen_readers(self):
        self.assertEqual(len(re.findall(r'role="img"', self.html)), 10)
        self.assertEqual(len(re.findall(r"aria-label=", self.html)), 10)
        self.assertEqual(len(re.findall(r"<figcaption>", self.html)), 10)


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

    def test_filter_press_line_is_drawn(self):
        from flotation_design.plant import build_rfc_option

        opt = build_rfc_option()
        for f in (opt.concentrate_filter, opt.tailings_filter):
            self.assertFigure(f.tag, f.tag + " 태그")
            self.assertFigure(f"{f.plate_mm:.0f} mm × {f.chambers} 챔버", f.tag + " 여과판")
            self.assertFigure(f"{f.filter_area_m2:.2f} m²", f.tag + " 여과 면적")
        # 미광도 케이크로 나간다 — 슬러리로 끝나면 도면이 설계와 다르다.
        self.assertFigure("미광 케이크", "미광 케이크 산물")

    def test_water_recycle_includes_filtrate(self):
        from flotation_design.plant import build_rfc_option

        opt = build_rfc_option()
        self.assertFigure(f"{opt.water_recycle_m3h:.1f} m³/h", "공정수 회수량")

    def test_hollow_shaft_sheet_matches_shaft_sizing(self):
        from flotation_design.plant import build_mechanical_option

        opt = build_mechanical_option()
        for c in opt.cells:
            s = c.shaft
            self.assertFigure(f"Ø{s.bore_mm:.0f}", c.tag + " 보어")
            self.assertFigure(f"Ø{s.outer_diameter_mm:.0f}", c.tag + " 외경")
            self.assertFigure(
                f"{s.total_pressure_drop_kpa:.1f}", c.tag + " 급기 압력손실"
            )
            self.assertEqual(s.governed_by, "로터동역학", c.tag)
            self.assertFigure(
                f"{s.discharge_ports}×Ø{s.discharge_port_diameter_mm:.0f}",
                c.tag + " 허브 토출구",
            )
            self.assertFigure(f"{s.critical_speed_rpm:.0f}", c.tag + " 1차 위험속도")
            self.assertFigure(f"{s.static_deflection_mm:.2f}", c.tag + " 정적 처짐")
        self.assertFigure(f"{opt.blower_pressure_kpa:.0f} kPa", "송풍기 토출압")
        self.assertFigure(
            f"분산구 {opt.cells[0].shaft.discharge_ports}개", "로터 허브 분산구"
        )

    def test_cell_detail_sheets_match_mechanical_sizing(self):
        # DWG-005~007 — 셀별 상세도면의 치수·성능이 코드 산출값과 같은지.
        from flotation_design.plant import build_mechanical_option

        opt = build_mechanical_option()
        res = opt.result_peak
        units = {"FC-201": res.rougher, "FC-202": res.scavenger,
                 "FC-203": res.cleaner}
        for c in opt.cells:
            g, i, a, s = c.geometry, c.impeller, c.aeration, c.shaft
            u = units[c.tag]
            self.assertFigure(f"{c.tag} 사양", c.tag + " 사양표")
            self.assertFigure(
                f"Ø{g.width_m * 1000:,.0f} × {g.shell_height_m * 1000:,.0f} mm",
                c.tag + " 동체")
            self.assertFigure(
                f"{g.effective_slurry_volume_m3:.3f} m³", c.tag + " 유효 체적")
            self.assertFigure(
                f"{g.lip_height_m * 1000:,.0f} / {g.froth_depth_m * 1000:,.0f} mm",
                c.tag + " 립·거품층")
            self.assertFigure(f"Ø{i.stator_od_m * 1000:,.0f}", c.tag + " 스테이터")
            self.assertFigure(
                f"{i.bottom_clearance_m * 1000:,.0f} mm", c.tag + " 저부 간극")
            self.assertFigure(f"{i.tip_speed_m_s:.2f} m/s", c.tag + " 주속")
            self.assertFigure(
                f"{a.bubble_surface_area_flux_1_s:.1f} s⁻¹", c.tag + " Sb")
            self.assertFigure(
                f"{a.air_flow_min_m3h:.1f}–{a.air_flow_max_m3h:.1f} m³/h",
                c.tag + " 급기 조절 범위")
            self.assertFigure(f"{u.residence_min:.2f} min", c.tag + " 체류시간")
            self.assertFigure(
                f"Ø{s.bore_mm:.0f} / Ø{s.outer_diameter_mm:.0f} mm / "
                f"{s.length_m:.2f} m", c.tag + " 중공축")

    def test_filtrate_returns_to_flotation_feed(self):
        # 여액은 공정수 탱크가 아니라 부선 급광으로 되돌린다.
        self.assertIn("여액 0.47 m³/h → 급광 순환", self.html)

    def test_patent_disclosure_present(self):
        # 실시권 리스크는 도면에서 빠지면 안 되는 항목이다.
        self.assertIn("2025902821", self.html)


if __name__ == "__main__":
    unittest.main()


class TestModel3dDocument(unittest.TestCase):
    """3단 회로 3D 모델 — 단독 HTML 로서의 성립과 자립성."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL_3D.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(MODEL_3D.exists())
        standalone_document_checks(self, self.html, "3단 부선기 분해 조립도")

    def test_no_external_3d_library(self):
        # WebGL 을 직접 쓴다 — 아티팩트 CSP 는 CDN 을 막으므로 라이브러리 반입 금지.
        for banned in ("three.min.js", "three.module", "babylon", "unpkg.com", "cdn."):
            self.assertNotIn(banned, self.html, banned)
        self.assertIn('getContext("webgl"', self.html)

    def test_has_webgl_fallback(self):
        self.assertIn('id="fallback"', self.html)
        self.assertIn("WebGL", self.html)

    def test_builds_all_three_cells(self):
        for tag in ("FC-201", "FC-202", "FC-203"):
            self.assertIn(tag, self.html, tag)
        self.assertIn("function buildCell(", self.html)
        self.assertIn("function buildPiping(", self.html)

    def test_has_explode_and_cutaway_controls(self):
        self.assertIn('id="exp"', self.html)
        self.assertIn('id="cut"', self.html)
        self.assertIn('aria-label="분해 정도"', self.html)

    def test_every_part_declares_an_explode_vector_and_anchor(self):
        # part(id, name, mat, ex, anchor, fn) — 분해 방향과 라벨 앵커가 모두 있어야 한다.
        calls = re.findall(r'part\("[^"]+","[^"]+","[a-z]+",(\[[^\]]*\]),(\[[^\]]*\])',
                           self.html)
        self.assertGreaterEqual(len(calls), 26)
        for ex, anchor in calls:
            self.assertEqual(len(ex.split(",")), 3, ex)
            self.assertEqual(len(anchor.split(",")), 3, anchor)

    def test_respects_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.html)

    def test_controls_are_labelled(self):
        for probe in ('aria-label="보기 대상"', 'aria-label="컷어웨이 정도"', 'aria-pressed'):
            self.assertIn(probe, self.html, probe)

    def test_container_tags_balance(self):
        for tag in ("div", "section", "table", "style", "script", "header"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")


class TestAttritionSheetsMatchDesign(unittest.TestCase):
    """DWG-008/009 — 전처리 도면의 수치가 코드 산출값과 같은지."""

    @classmethod
    def setUpClass(cls):
        from flotation_design.plant import build_pretreatment

        cls.html = DRAWING.read_text(encoding="utf-8")
        cls.pre = build_pretreatment()
        cls.sc = cls.pre.scrubber

    def assertFigure(self, text: str, label: str):
        self.assertTrue(
            text in self.html,
            f"{label} 이(가) 도면과 불일치 — 도면에 '{text}' 가 없음. "
            f"design_basis.py 를 고쳤다면 도면도 갱신할 것.",
        )

    def test_cell_dimensions(self):
        g = self.sc.geometry
        self.assertFigure(f"AF {g.across_flats_m * 1000:.0f}", "조 폭 (across flats)")
        self.assertFigure(
            f"{g.across_flats_m * 1000:.0f} × {g.depth_m * 1000:.0f} mm", "조 치수"
        )
        self.assertFigure(
            f"{g.freeboard_m * 1000:.0f} / {g.shell_height_m * 1000:.0f} mm",
            "여유고 / 전고",
        )
        self.assertFigure(f"대각 {g.circumscribed_diameter_m * 1000:.0f}", "대각 치수")

    def test_working_volumes(self):
        g = self.sc.geometry
        self.assertFigure(f"{g.working_volume_m3 * 1000:.1f} L", "셀당 유효 체적")
        self.assertFigure(
            f"{self.sc.total_working_volume_m3 * 1000:.1f} L", "총 유효 체적"
        )

    def test_drive_specs(self):
        d = self.sc.drive
        self.assertFigure(
            f"Ø{d.diameter_m * 1000:.0f} · {d.spacing_m * 1000:.0f} mm",
            "임펠러 지름·간격",
        )
        self.assertFigure(
            f"{d.speed_rpm:.0f} rpm · {d.tip_speed_m_s:.2f} m/s", "회전수·주속"
        )
        self.assertFigure(
            f"{d.tip_speed_min_m_s:.1f} ~ {d.tip_speed_ceiling_m_s:.2f} m/s",
            "VFD 조정 범위",
        )
        self.assertFigure(
            f"{d.absorbed_power_w / 1000.0:.2f} / {d.motor_rating_kw:.1f} kW",
            "흡수동력 / 모터",
        )
        self.assertFigure(f"{self.sc.specific_power_kw_m3:.1f} kW/m³", "체적당 동력")

    def test_shaft_specs(self):
        sh = self.sc.shaft
        self.assertEqual(sh.governed_by, "로터동역학")
        self.assertFigure(
            f"Ø{sh.outer_diameter_mm:.0f} × {sh.length_m:.2f} m", "교반축"
        )
        self.assertFigure(
            f"{sh.critical_speed_rpm:,.0f} rpm / {sh.critical_speed_ratio:.2f}배",
            "임계회전수 / 여유비",
        )

    def test_operating_point(self):
        self.assertEqual(self.sc.governed_by, "상용 최소 기종")
        self.assertFigure(
            f"{self.sc.solids_mass_fraction * 100:.0f} wt% "
            f"({self.sc.solids_volume_fraction * 100:.1f} vol%)",
            "스크러빙 농도",
        )
        self.assertFigure(
            f"{self.sc.residence_min(db.FEED.peak_tph):.1f} min", "체류시간"
        )
        self.assertFigure(
            f"{self.sc.specific_energy_kwh_t(db.FEED.peak_tph):.2f} kWh/t", "비에너지"
        )

    def test_flow_sheet_figures(self):
        dil = self.pre.dilution
        self.assertFigure(f"{dil.dilution_water_m3h:.2f} m³/h", "희석수")
        self.assertFigure(f"{dil.outlet_m3h:.2f} m³/h", "조건조 급광 유량")
        self.assertFigure(
            f"{dil.inlet_solids_wt * 100:.0f} → {dil.outlet_solids_wt * 100:.0f} wt%",
            "희석박스 농도",
        )
        self.assertFigure(f"{self.pre.installed_kw:.2f} kW", "전처리 설치 전력")
        self.assertFigure(f"{db.FEED.peak_tph * 1000:.1f} kg/h", "전처리 고체 유량")

    def test_tags_and_bypass_are_drawn(self):
        for probe in (db.ATTRITION_TAG, db.DILUTION_BOX_TAG, "바이패스",
                      "전단면", "플러싱"):
            self.assertFigure(probe, probe)

    def test_hydrogen_exhaust_is_drawn(self):
        # 후면 전극 Al 이 물과 반응 — 덮개 국소배기와 검지기가 계통도에 있어야 한다
        design_pct = db.H2_LEL_VOL * db.H2_DESIGN_LEL_FRACTION * 100.0
        self.assertFigure(f"H₂ ≤ {design_pct:.0f} vol%", "배기 설계 상한")
        self.assertFigure(f"{db.H2_ALARM_LEL_FRACTION * 100:.0f} % LEL 경보", "수소 경보점")
        for probe in ("AT", "008", "EF-1", "덮개 국소배기"):
            self.assertFigure(probe, probe)

    def test_eva_only_purpose_is_stated_on_the_drawings(self):
        self.assertIn("EVA 박리 설비다", self.html)
        self.assertIn("EVA 를 뗀 효과를 넣지 않았다", self.html)


class TestPilotSheetMatchesDesign(unittest.TestCase):
    """DWG-010 — 파일럿 시험 셀 PAS-1 도면의 수치가 코드 산출값과 같은지."""

    @classmethod
    def setUpClass(cls):
        from flotation_design.plant import (
            build_mechanism_screen,
            build_pilot,
            build_pilot_scale_up,
        )

        html = DRAWING.read_text(encoding="utf-8")
        start = html.index('<span class="sheet-no">DWG-010</span>')
        cls.sheet = html[start : html.index("</section>", start)]
        cls.pc = build_pilot()
        cls.su = build_pilot_scale_up()
        cls.ms = build_mechanism_screen()

    def assertFigure(self, text: str, label: str):
        self.assertTrue(
            text in self.sheet,
            f"{label} 이(가) DWG-010 과 불일치 — 도면에 '{text}' 가 없음. "
            f"design_basis.py 를 고쳤다면 도면도 갱신할 것.",
        )

    def test_cell_dimensions(self):
        pc, g = self.pc, self.pc.geometry
        self.assertFigure(f"AF {g.across_flats_m * 1000:.0f}", "조 폭")
        self.assertFigure(
            f"{g.across_flats_m * 1000:.0f} × {pc.fill_level_m * 1000:.0f} mm", "조 치수"
        )
        self.assertFigure(
            f"{g.freeboard_m * 1000:.0f} / {g.shell_height_m * 1000:.0f} mm", "여유고 / 전고"
        )
        self.assertFigure(f"대각 {g.circumscribed_diameter_m * 1000:.0f}", "대각")
        self.assertFigure(f"전고 {g.shell_height_m * 1000:.0f}", "전고 치수선")
        self.assertFigure(f"액면 {pc.fill_level_m * 1000:.0f}", "액면 치수선")

    def test_batch_and_sampling(self):
        pc = self.pc
        self.assertFigure(
            f"{pc.batch_dry_kg:.0f} kg / {pc.slurry_volume_m3 * 1000:.1f} L", "회분"
        )
        self.assertFigure(
            f"{pc.samples_per_batch}점 × {pc.sample_dry_kg:.2f} kg "
            f"({pc.withdrawal_fraction * 100:.0f} %)",
            "시료 계획",
        )
        self.assertFigure(
            f"{pc.solids_mass_fraction * 100:.0f} wt% ({pc.solids_volume_fraction * 100:.1f} vol%)",
            "스크러빙 농도",
        )

    def test_drive_specs(self):
        pc, d = self.pc, self.pc.drive
        top = pc.max_test_tip_speed_m_s
        self.assertFigure(
            f"Ø{d.diameter_m * 1000:.0f} · {d.spacing_m * 1000:.0f} mm", "임펠러 지름·간격"
        )
        self.assertFigure(
            f"{pc.impeller_clearance_m * 1000:.0f} / {pc.minimum_submergence_m * 1000:.0f} mm",
            "하단 간극 / 잠김",
        )
        self.assertFigure(f"{d.speed_rpm:,.0f} rpm · {d.tip_speed_m_s:.2f} m/s", "기준점")
        self.assertFigure(
            " / ".join(f"{t:.1f}" for t in pc.test_tip_speeds_m_s) + " m/s", "시험 주속"
        )
        self.assertFigure(
            f"{d.tip_speed_ceiling_m_s:.2f} m/s ({pc.speed_rpm(top):,.0f} rpm)", "VFD 상한"
        )
        self.assertFigure(
            f"{pc.power_w(top) / 1000.0:.2f} / {d.motor_rating_kw:.1f} kW", "동력 / 모터"
        )
        self.assertFigure(f"M {d.motor_rating_kw:.1f} kW", "모터 기호")
        self.assertFigure(
            f"{pc.specific_power_kw_m3(db.ATTRITION_DESIGN_TIP_SPEED_M_S):.1f} kW/m³",
            "체적당 동력",
        )

    def test_shaft_and_torque_sensor(self):
        pc, sh = self.pc, self.pc.shaft
        self.assertFigure(f"Ø{sh.outer_diameter_mm:.0f} × {sh.length_m:.2f} m", "교반축")
        self.assertFigure(
            f"{sh.critical_speed_rpm:,.0f} rpm / {sh.critical_speed_ratio:.2f}배", "임계회전수"
        )
        self.assertFigure(
            f"{pc.torque_sensor_nm:.0f} N·m (기동 {sh.torque_nm:.1f})", "토크센서 사양"
        )
        self.assertFigure(f"토크센서 {pc.torque_sensor_nm:.0f} N·m", "토크센서 기호")

    def test_heat_and_hydrogen(self):
        pc = self.pc
        self.assertFigure(
            f"{pc.jacket_area_m2:.3f} m² / {pc.worst_coolant_supply_c:.1f} °C", "재킷 / 냉매"
        )
        self.assertFigure(
            f"{pc.vent_m3h:.0f} m³/h · {pc.tolerable_aluminium_reaction_per_h * 100:.0f} %/h",
            "배기 / Al 반응",
        )
        self.assertFigure(f"배기 {pc.vent_m3h:.0f} m³/h", "배기 기호")
        self.assertFigure(
            " · ".join(f"{t:.0f}" for t in pc.temperatures_c) + " °C", "TCU 설정 온도"
        )
        for probe in ("TIC", "TCU", "AT", "H₂"):
            self.assertFigure(probe, probe)

    def test_sampling_table_matches_schedule(self):
        pc = self.pc
        schedules = [pc.schedule(t) for t in pc.test_tip_speeds_m_s]
        for i, point in enumerate(schedules[0]):
            cells = [f"{point.energy_kwh_t:g} kWh/t"]
            cells += [f"{s[i].elapsed_min:.1f} min" for s in schedules]
            cells += [f"{point.dry_kg_before:.1f} kg", f"{point.fill_level_m * 1000:.0f} mm"]
            row = "<tr>" + "".join(f'<td class="num">{c}</td>' for c in cells) + "</tr>"
            self.assertFigure(row, f"채취 일정 {point.energy_kwh_t:g} kWh/t")

    def test_decision_band_matches_scale_up(self):
        su = self.su
        for limit in (
            su.batch_limit_peak_kwh_t,
            su.batch_limit_peak_upsized_kwh_t,
            su.batch_limit_average_upsized_kwh_t,
        ):
            self.assertFigure(f">{limit:.2f}</text>", f"판정선 {limit:.2f}")
        self.assertFigure(f"환산 {su.energy_factor:.2f}배", "연속 환산 배수")
        self.assertFigure(f"모터 {su.upsized_motor_kw:.1f} kW", "교체 모터")
        self.assertFigure(f"평균 {db.FEED.average_tph:.2f} t/h", "평균 처리량")

    def test_mechanism_rejection_is_quantified(self):
        self.assertFigure(f"1/{self.ms.shear_shortfall:,.0f}", "로터-스테이터 부족 배수")

    def test_no_organic_wetted_parts_on_the_sheet(self):
        self.assertFigure("SUS316L", "접액부 재질")
        self.assertIn("SUS316L", self.pc.wetted_material)
        for word in ("고무", "우레탄"):
            self.assertNotIn(word, self.sheet)

    def test_states_it_is_not_plant_equipment(self):
        self.assertFigure("플랜트 설비 아님", "플랜트 설비 아님")
        self.assertFigure(db.PILOT_TAG, "태그")


class TestModel3dMatchesDesign(unittest.TestCase):
    """3D 모델에 표기된 수치가 코드 산출값과 같은지."""

    @classmethod
    def setUpClass(cls):
        from flotation_design.plant import build_mechanical_option

        cls.html = MODEL_3D.read_text(encoding="utf-8")
        cls.opt = build_mechanical_option()
        cls.res = cls.opt.result_peak
        cls.unit = {
            "FC-201": cls.res.rougher,
            "FC-202": cls.res.scavenger,
            "FC-203": cls.res.cleaner,
        }

    def assertFigure(self, text, label):
        self.assertTrue(
            text in self.html,
            f"{label} 이(가) 3D 모델과 불일치 — '{text}' 가 없음. "
            f"design_basis.py 를 고쳤다면 모델 수치도 갱신할 것.",
        )

    def test_cell_dimensions(self):
        for c in self.opt.cells:
            self.assertFigure(
                f"Ø{c.geometry.width_m * 1000:,.0f} × "
                f"{c.geometry.shell_height_m * 1000:,.0f} mm",
                c.tag + " 동체",
            )

    def test_froth_depths_differ_by_duty(self):
        d = {c.tag: c.geometry.froth_depth_m for c in self.opt.cells}
        self.assertLess(d["FC-202"], d["FC-201"])   # 스캐빈저는 얕게 — 회수 우선
        self.assertGreater(d["FC-203"], d["FC-201"])  # 클리너는 깊게 — 품위 우선
        for tag, v in d.items():
            self.assertFigure(f"{v * 1000:.0f} mm", tag + " 거품층")

    def test_rotor_specs(self):
        for c in self.opt.cells:
            self.assertFigure(
                f"Ø{c.impeller.diameter_m * 1000:.0f} mm · "
                f"{c.impeller.speed_rpm:.0f} rpm",
                c.tag + " 로터",
            )
            kw = c.impeller.motor_rating_kw
            self.assertTrue(
                any(f"{kw:.{d}f} kW" in self.html for d in (0, 1, 2)),
                f"{c.tag} 모터 용량 {kw} kW 가 3D 모델에 없음",
            )

    def test_residence_times(self):
        for tag, u in self.unit.items():
            self.assertFigure(f"{u.residence_min:.1f} min", tag + " 체류시간")

    def test_scavenger_reuses_rougher_vessel(self):
        cells = {c.tag: c for c in self.opt.cells}
        self.assertEqual(cells["FC-202"].geometry.width_m,
                         cells["FC-201"].geometry.width_m)
        self.assertEqual(cells["FC-202"].geometry.shell_height_m,
                         cells["FC-201"].geometry.shell_height_m)
        self.assertIn("러퍼와 공용", self.html)

    def test_circuit_performance(self):
        self.assertFigure(f"{self.res.recovery('Ag') * 100:.1f} %", "회로 Ag 회수율")
        self.assertFigure(
            f"{self.res.concentrate.dry_tph * 1000:.2f} kg/h @ "
            f"{self.res.concentrate.grade_fraction('Ag') * 100:.1f} wt% Ag",
            "최종 정광",
        )
        self.assertFigure(
            f"{self.res.tailings.grade_fraction('Ag') * 1e6:.0f} g/t", "최종 미광 Ag"
        )
        self.assertFigure(f"{self.res.circulating_load * 100:.1f} %", "순환부하")

    def test_stage_recoveries(self):
        for tag, u in self.unit.items():
            self.assertFigure(f"{u.recovery('Ag') * 100:.1f} %", tag + " 단 회수율")

    def test_hollow_shaft_parts_are_modelled(self):
        # 급기를 축으로 넣는 설계이므로 스파저가 아니라 축·조인트가 부품으로 있어야 한다.
        self.assertIn("중공축", self.html)
        self.assertIn("로터리 조인트", self.html)
        for c in self.opt.cells:
            s = c.shaft
            self.assertFigure(f"Ø{s.bore_mm:.0f} / Ø{s.outer_diameter_mm:.0f}",
                              c.tag + " 중공축 보어·외경")

    def test_blower_matches_shaft_losses(self):
        self.assertFigure(
            f"{self.opt.blower_flow_m3h:.0f} m³/h @ "
            f"{self.opt.blower_pressure_kpa:.0f} kPa",
            "송풍기 사양",
        )

    def test_filter_presses_are_modelled(self):
        for f in (self.opt.concentrate_filter, self.opt.tailings_filter):
            self.assertFigure(f.tag, f.tag + " 태그")
            self.assertFigure(
                f"{f.plate_mm:.0f} mm × {f.chambers} 챔버 · {f.filter_area_m2:.2f} m²",
                f.tag + " 여과판 사양",
            )
        self.assertIn("TK-201", self.html)
        self.assertIn("TK-202", self.html)

    def test_installed_power_matches(self):
        self.assertFigure(f"{self.opt.installed_kw:.2f} kW", "설치 전력")

    def test_recycle_streams_are_named(self):
        self.assertIn("스캐빈저 정광", self.html)
        self.assertIn("클리너 미광", self.html)
        # 필터프레스 여액은 러퍼 급광으로 순환한다.
        self.assertIn("여액 → 러퍼 급광 순환", self.html)

    def test_states_it_is_not_a_cad_model(self):
        self.assertIn("제작용 CAD 가 아니며", self.html)


if __name__ == "__main__":
    unittest.main()
