"""MP-50 파일럿 분리기 도면(제작도 8매 + 3D 조립도) 검증.

두 도면 파일에는 치수·유량·성능 수치가 문자열로 박혀 있다. 이 장비는 전용 계산
모듈이 없으므로, `pv-delamination` 콘솔과 같은 방식으로 **도면이 밝힌 식과 상수만
가지고 모델을 여기서 다시 세운 뒤** 도면의 표기와 대조한다. 도면을 고치면서 계산을
안 맞추면 여기서 먼저 실패한다.

원 스케치의 치수 여러 건이 서로 성립하지 않아 계산으로 다시 잡았고, 그중
**압력시험 0.2 MPa 는 안전 문제**(t5 평판 커버가 항복한다)라 수정 이력이 도면에서
빠지지 않는지도 함께 지킨다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

from .test_drawings import standalone_document_checks

DRAWINGS_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings"
SHEETS = DRAWINGS_DIR / "mp50-pilot-drawings.html"
MODEL_3D = DRAWINGS_DIR / "mp50-pilot-3d.html"

# ── 설계 상수 ────────────────────────────────────────────────────────────
# 동체는 SUS304 Ø400 OD × t3 판을 말아 만든다.
SHELL_OD_MM, SHELL_T_MM = 400.0, 3.0
SHELL_ID_MM = SHELL_OD_MM - 2 * SHELL_T_MM          # 394
STRAIGHT_MM = 600.0
# 콘 출구는 2" 위생관 내경에 맞춘다. 60° 는 포함각이며 침전 배출성을 지배한다.
OUTLET_ID_MM = 47.6
CONE_INCLUDED_DEG = 60.0
WORKING_L = 50.0

# 임펠러는 상업 셀 FC-201(Ø350 / Ø1,000)과 같은 D/T 로 잡았다.
IMP_D_M = 0.140
RPM_DESIGN, RPM_MAX, RPM_MIN = 600.0, 717.0, 179.0
NP_DISC, NP_PBT = 5.0, 1.27      # 6엽 디스크 터빈 / 4엽 45° 경사날개 (무기포)
RHO_SLURRY = 1060.0              # 고체 약 10 wt% 슬러리

# 급기 — 분산기 링 Ø250 에 Ø1.0 홀 60개, 하향 45°
AIR_M3H, HOLES, HOLE_D_M = 2.60, 60, 0.0010
RHO_AIR, CD_ORIFICE, SIGMA = 1.4, 0.62, 0.072
SPARGER_Z_MM, LEVEL_MM = 20.0, 297.0

# 커버는 Ø394 개구를 덮는 t5 평판이다 — 이 용기에서 압력을 지배하는 부재.
COVER_A_M, COVER_T_M, POISSON = 0.197, 0.005, 0.30
E_PA = 1.93e11
ALLOW_MPA, YIELD_MPA = 137.0, 205.0
P_DESIGN_MPA, P_ORIGINAL_MPA = 0.05, 0.20

# 교반축 Ø25 · 임펠러 질량과 오버행으로 1차 위험속도를 검산한다.
SHAFT_D_M = 0.025
IMP_LOWER_KG, IMP_UPPER_KG = 1.4, 1.2
OVERHANG_LOWER_M, OVERHANG_UPPER_M = 0.565, 0.405


def vessel():
    """동체·콘 형상과 체적 — 60° 를 지키면 콘 높이가 결정된다."""
    half = math.radians(CONE_INCLUDED_DEG / 2)
    dr_mm = (SHELL_ID_MM - OUTLET_ID_MM) / 2
    cone_h_mm = dr_mm / math.tan(half)
    slant_mm = dr_mm / math.sin(half)
    area_m2 = math.pi / 4 * (SHELL_ID_MM / 1000) ** 2
    d, dd, h = SHELL_ID_MM / 1000, OUTLET_ID_MM / 1000, cone_h_mm / 1000
    cone_l = math.pi * h / 12 * (d * d + d * dd + dd * dd) * 1000
    cyl_l = area_m2 * (STRAIGHT_MM / 1000) * 1000
    return dict(
        cone_h_mm=cone_h_mm, slant_mm=slant_mm, area_m2=area_m2,
        cone_l=cone_l, cyl_l=cyl_l, total_l=cone_l + cyl_l,
        # 전개 블랭크: 외반경 = R/sin(반각), 전개각 = 360° × sin(반각)
        dev_outer_mm=(SHELL_ID_MM / 2) / math.sin(half),
        dev_inner_mm=(OUTLET_ID_MM / 2) / math.sin(half),
        dev_angle_deg=360.0 * math.sin(half),
        level_mm=(WORKING_L - (cone_l)) / (area_m2),
    )


def agitation(rpm):
    """무기포 축동력·토크·주속. 임펠러 두 장은 한 축이므로 Np 를 더한다."""
    n = rpm / 60.0
    power_w = (NP_DISC + NP_PBT) * RHO_SLURRY * n ** 3 * IMP_D_M ** 5
    return dict(power_w=power_w, torque_nm=power_w / (2 * math.pi * n),
                tip_m_s=math.pi * IMP_D_M * n)


def aeration(m3h):
    """표면 기체속도와 분사홀 유동 — We > 2 라야 제트가 선다."""
    q = m3h / 3600.0
    area = math.pi / 4 * (SHELL_ID_MM / 1000) ** 2
    hole_area = HOLES * math.pi / 4 * HOLE_D_M ** 2
    v = q / hole_area
    return dict(
        jg_cm_s=q / area * 100,
        hole_v=v,
        hole_dp_kpa=RHO_AIR / 2 * (v / CD_ORIFICE) ** 2 / 1000,
        weber=RHO_AIR * v * v * HOLE_D_M / SIGMA,
        head_kpa=RHO_SLURRY * 9.81 * (LEVEL_MM - SPARGER_Z_MM) / 1000 / 1000,
    )


def cover_stress(p_mpa):
    """단순지지 원판 최대 굽힘응력 σ = 3(3+ν)·p·a² / (8·t²)."""
    p = p_mpa * 1e6
    return 3 * (3 + POISSON) * p * COVER_A_M ** 2 / (8 * COVER_T_M ** 2) / 1e6


def critical_speed_rpm():
    """오버행 축의 1차 위험속도 (Dunkerley 합성)."""
    inertia = math.pi * SHAFT_D_M ** 4 / 64
    ei = E_PA * inertia
    out = []
    for mass, length in ((IMP_LOWER_KG, OVERHANG_LOWER_M),
                         (IMP_UPPER_KG, OVERHANG_UPPER_M)):
        defl = mass * 9.81 * length ** 3 / (3 * ei)
        out.append(math.sqrt(9.81 / defl) * 60 / (2 * math.pi))
    return 1 / math.sqrt(sum(1 / n ** 2 for n in out))


class TestSheetDocument(unittest.TestCase):
    """제작도 8매 — 단독 HTML 문서로서 성립하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = SHEETS.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(SHEETS.exists())
        standalone_document_checks(self, self.html, "MP-50 파일럿 분리기 제작도")

    def test_container_tags_balance(self):
        for tag in ("svg", "figure", "section", "table", "defs", "g", "style", "div"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_eight_sheets_present(self):
        for no in ("MP-50-P0-001", "MP-50-P0-002", "MP-50-P0-003", "MP-50-P0-004",
                   "MP-50-P0-005", "MP-50-P0-006", "MP-50-P0-007", "MP-50-P0-008"):
            self.assertIn(no, self.html, no)
        self.assertEqual(len(re.findall(r"<svg", self.html)), 8)

    def test_every_figure_is_labelled_for_screen_readers(self):
        self.assertEqual(len(re.findall(r'role="img"', self.html)), 8)
        self.assertEqual(len(re.findall(r"aria-label=", self.html)), 8)
        self.assertEqual(len(re.findall(r"<figcaption>", self.html)), 8)

    def test_every_svg_is_well_formed(self):
        """도면 한 장이 깨지면 그 장만 사라지므로 눈에 잘 띄지 않는다."""
        import xml.etree.ElementTree as ET
        for i, svg in enumerate(re.findall(r"<svg.*?</svg>", self.html, re.S), 1):
            try:
                ET.fromstring(svg.replace("&quot;", '"'))
            except ET.ParseError as exc:  # pragma: no cover - 실패 시에만
                self.fail(f"MP-50-P0-00{i} SVG 파싱 실패: {exc}")

    def test_bill_of_materials_is_complete(self):
        """부품표는 01~34 가 빠짐없이 있어야 한다 — 발주 누락이 그대로 손실이다."""
        for no in range(1, 35):
            self.assertIn(f'<td class="tag">{no:02d}</td>', self.html, f"BOM {no:02d}")


class TestModel3dDocument(unittest.TestCase):
    """3D 조립·분해도 — 단독 HTML 로서의 성립과 자립성."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL_3D.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(MODEL_3D.exists())
        standalone_document_checks(self, self.html, "MP-50 파일럿 분리기 분해 조립도")

    def test_no_external_3d_library(self):
        # 자매 도면과 같은 규약 — 아티팩트 CSP 는 CDN 을 막으므로 라이브러리 반입 금지.
        for banned in ("three.min.js", "three.module", "babylon", "unpkg.com", "cdn."):
            self.assertNotIn(banned, self.html, banned)
        self.assertIn('getContext("webgl"', self.html)

    def test_has_webgl_fallback(self):
        self.assertIn('id="fallback"', self.html)
        self.assertIn("WebGL", self.html)

    def test_container_tags_balance(self):
        for tag in ("div", "section", "table", "style", "script", "header", "ol", "li"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_every_part_declares_an_explode_vector_and_anchor(self):
        calls = re.findall(
            r'part\("[^"]+","[^"]*","[a-z0-9]+",(\[[^\]]*\]),(\[[^\]]*\])', self.html)
        self.assertGreaterEqual(len(calls), 26)
        for ex, anchor in calls:
            self.assertEqual(len(ex.split(",")), 3, ex)
            self.assertEqual(len(anchor.split(",")), 3, anchor)

    def test_has_explode_and_cutaway_controls(self):
        self.assertIn('id="exp"', self.html)
        self.assertIn('id="cut"', self.html)
        self.assertIn('aria-label="분해 정도"', self.html)

    def test_controls_are_labelled(self):
        for probe in ('aria-label="보기 대상"', 'aria-label="컷어웨이 정도"', "aria-pressed"):
            self.assertIn(probe, self.html, probe)

    def test_respects_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.html)

    def test_key_assemblies_are_modelled(self):
        for probe in ("탱크 셀", "하부 콘", "배플 케이지", "미세기포 분산기",
                      "상부 임펠러", "하부 임펠러", "교반축", "지지 다리"):
            self.assertIn(probe, self.html, probe)

    def test_states_it_is_not_a_cad_model(self):
        self.assertIn("제작용 CAD 가 아니며", self.html)


class TestFiguresMatchTheModel(unittest.TestCase):
    """두 도면에 박힌 수치가 여기서 다시 세운 계산과 같은지."""

    @classmethod
    def setUpClass(cls):
        cls.sheets = SHEETS.read_text(encoding="utf-8")
        cls.model = MODEL_3D.read_text(encoding="utf-8")
        cls.v = vessel()

    def assertFigure(self, text, label, where="both"):
        # assertIn 은 실패 시 문서 전체를 덤프하므로 메시지를 직접 만든다.
        targets = {"sheets": [("제작도", self.sheets)],
                   "model": [("3D", self.model)],
                   "both": [("제작도", self.sheets), ("3D", self.model)]}[where]
        for name, html in targets:
            self.assertTrue(
                text in html,
                f"{label} 이(가) {name}와 불일치 — '{text}' 가 없음. "
                f"치수를 고쳤다면 도면도 갱신할 것.",
            )

    def test_cone_height_follows_from_the_60_degree_rule(self):
        # 60° 를 지키면 높이는 선택지가 아니라 결과값이다 (원 스케치의 150 mm 는 불가).
        self.assertAlmostEqual(self.v["cone_h_mm"], 300.0, delta=0.5)
        self.assertFigure("h 300", "콘 높이")
        self.assertFigure("60° 포함각", "콘 포함각")

    def test_cone_development_is_a_half_annulus(self):
        self.assertAlmostEqual(self.v["dev_angle_deg"], 180.0, places=6)
        self.assertFigure("전개각 180.0°", "콘 전개각", "sheets")
        self.assertFigure(f"R{self.v['dev_outer_mm']:.0f}", "전개 외반경", "sheets")
        self.assertFigure(f"경사길이 {self.v['slant_mm']:.0f}", "콘 경사길이", "sheets")

    def test_volumes_and_working_level(self):
        self.assertAlmostEqual(self.v["total_l"], 87.0, delta=0.1)
        self.assertAlmostEqual(self.v["level_mm"], 297.0, delta=1.0)
        self.assertFigure("50 L / 87 L", "운전 / 전 용량")
        self.assertFigure("+297", "정지 액면")

    def test_impeller_ratio_matches_the_commercial_cell(self):
        ratio = IMP_D_M * 1000 / SHELL_ID_MM
        self.assertAlmostEqual(ratio, 0.355, delta=0.001)
        self.assertFigure(f"{ratio:.3f}", "D/T")

    def test_agitation_duty(self):
        d, mx = agitation(RPM_DESIGN), agitation(RPM_MAX)
        self.assertFigure(f"{d['tip_m_s']:.2f} m/s", "설계 주속")
        self.assertFigure(f"{d['power_w']:.0f} W", "설계 축동력")
        self.assertFigure(f"{mx['power_w']:.0f} W", "최대 축동력")
        self.assertFigure(f"{d['torque_nm']:.2f} → {mx['torque_nm']:.2f} N·m", "축 토크")
        for rpm in (RPM_DESIGN, RPM_MAX, RPM_MIN):
            self.assertFigure(f"{rpm:.0f} rpm", f"{rpm:.0f} rpm 표기")

    def test_motor_covers_the_ungassed_worst_case(self):
        # 기포가 없을 때가 가장 무겁다 — 그 조건에서 0.75 kW 안에 들어야 한다.
        required_w = agitation(RPM_MAX)["power_w"] / 0.94   # 감속기 효율
        self.assertLess(required_w, 750.0)
        self.assertFigure("0.75 kW", "모터 정격")

    def test_shaft_runs_well_below_its_critical_speed(self):
        nc = critical_speed_rpm()
        self.assertLess(RPM_MAX / nc, 0.7)
        self.assertFigure(f"{nc:,.0f} rpm", "1차 위험속도")

    def test_aeration_and_sparger_holes(self):
        a = aeration(AIR_M3H)
        self.assertFigure(f"{a['jg_cm_s']:.2f} cm/s", "표면 기체속도 Jg")
        self.assertFigure(f"{a['hole_v']:.1f} m/s", "홀 유속", "sheets")
        self.assertFigure(f"{a['hole_dp_kpa']:.2f} kPa", "홀 압력손실", "sheets")
        self.assertFigure(f"{a['head_kpa']:.2f} kPa", "링 정수두", "sheets")
        self.assertFigure(f"{HOLES}-Ø{HOLE_D_M*1000:.1f}", "분사홀 사양")

    def test_hole_size_actually_produces_a_jet(self):
        """Ø1.0 은 취향이 아니라 We > 2 를 만족시키려고 고른 값이다."""
        self.assertGreater(aeration(AIR_M3H)["weber"], 2.0)
        # 원 스케치의 Ø2.0 이면 제트가 서지 않는다는 사실이 도면에 남아 있어야 한다.
        coarse_v = (AIR_M3H / 3600) / (HOLES * math.pi / 4 * 0.002 ** 2)
        coarse_we = RHO_AIR * coarse_v ** 2 * 0.002 / SIGMA
        self.assertLess(coarse_we, 2.0)
        self.assertFigure(f"{coarse_v:.1f} m/s · We {coarse_we:.2f}", "Ø2.0 대비", "sheets")

    def test_cover_holds_the_design_pressure(self):
        s = cover_stress(P_DESIGN_MPA)
        self.assertLess(s, ALLOW_MPA)
        self.assertFigure(f"{s:.0f}", "설계압력 커버 응력", "sheets")

    def test_original_test_pressure_would_yield_the_cover(self):
        """원 스케치의 0.2 MPa 시험은 안전 문제다 — 근거가 도면에서 빠지면 안 된다."""
        s = cover_stress(P_ORIGINAL_MPA)
        self.assertGreater(s, YIELD_MPA)
        self.assertFigure(f"{s:.0f}", "0.2 MPa 커버 응력", "sheets")
        self.assertFigure("0.05 MPa", "설계 압력")
        self.assertFigure("0.075 MPa", "시험 압력")

    def test_shell_is_not_the_governing_member(self):
        hoop = P_DESIGN_MPA * 1e6 * (SHELL_ID_MM / 1000) / (2 * SHELL_T_MM / 1000) / 1e6
        self.assertLess(hoop, cover_stress(P_DESIGN_MPA) / 10)
        self.assertFigure(f"{hoop:.1f} MPa", "동체 후프응력", "sheets")

    def test_shell_dimensions(self):
        self.assertFigure(f"Ø{SHELL_OD_MM:.0f} × t{SHELL_T_MM:.0f} × {STRAIGHT_MM:.0f}",
                          "동체 치수")
        self.assertFigure(f"Ø{SHELL_ID_MM:.0f}", "동체 내경")


class TestDeviationRecordSurvives(unittest.TestCase):
    """원 스케치와 달라진 이유가 도면에서 사라지지 않는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = SHEETS.read_text(encoding="utf-8")

    def test_every_deviation_is_recorded_with_a_reason(self):
        for item in ("압력 시험", "하부 콘", "임펠러 지름", "임펠러 구분", "분사홀",
                     "커버 체결", "콘 출구", "하부 플랜지", "배출 밸브", "배플",
                     "키홈", "동체 높이", "교반축 길이", "지지 다리"):
            self.assertIn(f'<td class="tag">{item}</td>', self.html, item)

    def test_deviation_count_is_stated_and_matches_the_table(self):
        rows = re.findall(r'<td class="was">', self.html)
        self.assertEqual(len(rows), 14)
        self.assertIn("<b>14</b>", self.html)

    def test_the_pressure_test_warning_is_prominent(self):
        # 표에만 있고 주기에서 빠지면 제작 현장까지 전달되지 않는다.
        self.assertIn("0.2 MPa 는 시행하지 말 것", self.html)
        self.assertIn('class="bad"', self.html)


if __name__ == "__main__":
    unittest.main()
