"""MP-50 염수 밀도분리 파일럿 도면(제작도 11매 + 3D 조립도) 검증 — Rev.A.

이 장비는 부선기가 아니라 **염수 자연 밀도분리조**다. 임펠러와 공기는 분산 수단이고,
분산이 끝나면 동시에 정지해 중력·부력만으로 FLOAT / SINK 가 진행된다.

전용 계산 모듈이 없는 장비이므로 `pv-delamination` 콘솔과 같은 방식으로 **도면이 밝힌
식과 상수만 가지고 모델을 여기서 다시 세운 뒤** 도면의 표기와 대조한다. 연구문서
Rev.0 의 기준값(콘 이론높이 346 · 동체 상단 Z946 · 전 용적 89.9 L · 액면 Z720)을
재현하는지도 함께 지켜, 도면이 문서에서 조용히 떨어져 나가지 않게 한다.
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

# ── 설계 상수 (연구문서 Rev.0 §2 · §7) ──────────────────────────────────
ID_MM, T_SHELL_MM, STRAIGHT_MM = 400.0, 3.0, 600.0   # Tank ID Ø400 · Shell H600
CONE_DEG = 60.0                                       # 벽면각 — 침전 배출성 지배
Z_LEVEL_MM = 720.0                                    # 설계 액면
Z_RING_MM, Z_IMP_LO_MM, Z_IMP_UP_MM = 300.0, 430.0, 610.0
Z_BAF_LO_MM, Z_BAF_UP_MM = 390.0, 690.0
D_IMP_MM, D_RING_MM = 300.0, 250.0
BAFFLE_W_MM, BAFFLE_GAP_MM = 25.0, 8.0                # 원문 80 → 간섭으로 재산정
OUTLET_BORE = {"1.5": 34.8, "2": 47.5}                # 위생관 내경
BINS = [(31, 45), (45, 60), (60, 75)]
RHO_EFF = {"EVA": [(980, 70), (950, 60), (920, 50)],
           "Backsheet": [(1110, 100), (1060, 90), (1010, 80)],
           "Silicon": [(2330, 25), (2330, 22), (2330, 20)]}
SALTS = (12, 15, 18)
PSD_W = [0.33, 0.34, 0.33]
G = 9.81
NP_PBT = 1.27
RPMS = (30, 45, 60, 75, 90)
DOE_LEVELS = (3, 5, 5, 3, 5)      # NaCl × rpm × Air × Mixing × Settling
SETTLE_WINDOW_S = 600.0
D_BUBBLE_M = 200e-6
RHO_AIR = 1.2

HALF = math.radians(CONE_DEG / 2)


def vessel():
    """콘 60° 를 지키면 이론높이는 선택이 아니라 결과값이다."""
    apex_h = (ID_MM / 2) / math.tan(HALF)
    area = math.pi / 4 * (ID_MM / 1000) ** 2
    v_cone = math.pi / 3 * (ID_MM / 2000) ** 2 * (apex_h / 1000) * 1000
    v_cyl = area * (STRAIGHT_MM / 1000) * 1000
    return dict(
        apex_h=apex_h, area=area, v_cone=v_cone, v_cyl=v_cyl,
        z_tan=apex_h, z_shell_top=apex_h + STRAIGHT_MM,
        z_cover_top=apex_h + STRAIGHT_MM + 5.0,
        total_l=v_cone + v_cyl,
        # 전개 블랭크 — 60° 에서만 정확히 반원 고리가 된다
        dev_outer=(ID_MM / 2) / math.sin(HALF),
        dev_angle=360.0 * math.sin(HALF),
    )


V = vessel()


def vol_at(z):
    if z <= V["apex_h"]:
        return math.pi / 3 * ((z * math.tan(HALF)) / 1000) ** 2 * (z / 1000) * 1000
    return V["v_cone"] + V["area"] * ((z - V["apex_h"]) / 1000) * 1000


def z_for(v):
    lo, hi = 0.0, V["z_shell_top"]
    for _ in range(90):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if vol_at(mid) < v else (lo, mid)
    return (lo + hi) / 2


def cut_z(bore):
    """이론 정점을 배출 내경에서 자른 높이."""
    return (bore / 2) / math.tan(HALF)


def rho_brine(w): return 998 + 7.55 * w
def mu_brine(w): return 0.001 * (1 + 0.018 * w)


def erf(x):
    s = -1 if x < 0 else 1
    a = abs(x)
    t = 1 / (1 + 0.3275911 * a)
    return s * (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                      - 0.284496736) * t + 0.254829592) * t * math.exp(-a * a))


def float_prob(mat, i, w):
    m, s = RHO_EFF[mat][i]
    return 0.5 * (1 + erf((rho_brine(w) - m) / s / math.sqrt(2)))


def bin_d(i): return (BINS[i][0] + BINS[i][1]) / 2 * 1e-6


TRAVEL_M = (Z_LEVEL_MM - V["z_tan"]) / 1000     # 액면 → 콘 접선


def stokes(rho_p, d_m, w):
    return (rho_p - rho_brine(w)) * G * d_m * d_m / (18 * mu_brine(w))


def travel_s(mat, i, w):
    v = stokes(RHO_EFF[mat][i][0], bin_d(i), w)
    return math.inf if abs(v) < 1e-12 else abs(TRAVEL_M / v)


def arrived(mat, w, t=SETTLE_WINDOW_S):
    """균일 현탁 가정에서 t 초 안에 상·하부에 닿는 질량 비율."""
    return sum(PSD_W[i] * min(1.0, abs(stokes(RHO_EFF[mat][i][0], bin_d(i), w)) * t / TRAVEL_M)
               for i in range(3))


def terminal_v(rho_eq, d_eq, w):
    """Schiller-Naumann 항력으로 수렴시킨 종말속도 (Re > 1 영역)."""
    rho, mu = rho_brine(w), mu_brine(w)
    dr = rho_eq - rho
    v = dr * G * d_eq * d_eq / (18 * mu)
    for _ in range(200):
        re = max(abs(rho * v * d_eq / mu), 1e-9)
        cd = 24 / re * (1 + 0.15 * re ** 0.687) if re < 1000 else 0.44
        vn = math.copysign(math.sqrt(abs(4 * dr * G * d_eq / (3 * cd * rho))), dr)
        if abs(vn - v) < 1e-9:
            return vn
        v = 0.5 * (v + vn)
    return v


def bubble_travel_s(mat, i, w):
    """분산 중에 붙어 정지 후에도 남는 미세기포가 실어 올리는 속도."""
    rho_p, d_p = RHO_EFF[mat][i][0], bin_d(i)
    v_p = math.pi / 6 * d_p ** 3
    v_b = math.pi / 6 * D_BUBBLE_M ** 3
    rho_eq = (rho_p * v_p + RHO_AIR * v_b) / (v_p + v_b)
    d_eq = (6 * (v_p + v_b) / math.pi) ** (1 / 3)
    return abs(TRAVEL_M / terminal_v(rho_eq, d_eq, w))


def shaft_power(rpm, w=15):
    n = rpm / 60
    return 2 * NP_PBT * rho_brine(w) * n ** 3 * (D_IMP_MM / 1000) ** 5


def njs(w, dp, kg, v_l):
    """Zwietering — S 를 D/T 로 보정한다 (기준 D/T 0.5, S 6.0)."""
    rho, mu = rho_brine(w), mu_brine(w)
    x = kg / (v_l / 1000 * rho) * 100
    s = 6.0 * ((0.5 / (D_IMP_MM / ID_MM)) ** 1.3)
    return s * (mu / rho) ** 0.1 * (G * (2330 - rho) / rho) ** 0.45 * \
        x ** 0.13 * dp ** 0.2 / (D_IMP_MM / 1000) ** 0.85 * 60


V_LEVEL_L = vol_at(Z_LEVEL_MM)
BAFFLE_INNER_R = 200 - BAFFLE_GAP_MM - BAFFLE_W_MM


class TestSheetDocument(unittest.TestCase):
    """제작도 11매 — 단독 HTML 문서로서 성립하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = SHEETS.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(SHEETS.exists())
        standalone_document_checks(self, self.html, "MP-50 염수 밀도분리 파일럿 제작도")

    def test_container_tags_balance(self):
        for tag in ("svg", "figure", "section", "table", "defs", "style", "div"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_eleven_sheets_present(self):
        for n in range(1, 12):
            self.assertIn(f"MP-50-P0-{n:03d}", self.html, f"sheet {n}")
        self.assertEqual(len(re.findall(r"<svg", self.html)), 11)

    def test_every_figure_is_labelled_for_screen_readers(self):
        self.assertEqual(len(re.findall(r'role="img"', self.html)), 11)
        self.assertEqual(len(re.findall(r"aria-label=", self.html)), 11)
        self.assertEqual(len(re.findall(r"<figcaption>", self.html)), 11)

    def test_every_svg_is_well_formed(self):
        """도면 한 장이 깨지면 그 장만 사라지므로 눈에 잘 띄지 않는다."""
        import xml.etree.ElementTree as ET
        for i, svg in enumerate(re.findall(r"<svg.*?</svg>", self.html, re.S), 1):
            try:
                ET.fromstring(svg.replace("&quot;", '"'))
            except ET.ParseError as exc:  # pragma: no cover - 실패 시에만
                self.fail(f"MP-50-P0-{i:03d} SVG 파싱 실패: {exc}")

    def test_bill_of_materials_is_complete(self):
        for no in range(1, 35):
            self.assertIn(f'<td class="tag">{no:02d}</td>', self.html, f"BOM {no:02d}")


class TestModel3dDocument(unittest.TestCase):
    """3D 조립·분해도 — 단독 HTML 로서의 성립과 자립성."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL_3D.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(MODEL_3D.exists())
        standalone_document_checks(self, self.html, "MP-50 염수 밀도분리 파일럿 분해 조립도")

    def test_no_external_3d_library(self):
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

    def test_separation_result_view_exists(self):
        """이 장비의 산출물은 FLOAT / SINK 두 층이다 — 보기로 확인할 수 있어야 한다."""
        self.assertIn('id="vSep"', self.html)
        self.assertIn("FLOAT 층", self.html)
        self.assertIn("SINK 층", self.html)
        # 동체가 불투명하면 층이 보이지 않는다.
        self.assertIn("SEE_THROUGH", self.html)

    def test_every_view_button_is_wired(self):
        ids = set(re.findall(r'id="(v[A-Z][a-z]+)"', self.html))
        for i in ids:
            self.assertIn(f'document.getElementById("{i}").addEventListener', self.html, i)

    def test_states_it_is_not_a_cad_model(self):
        self.assertIn("제작용 CAD 가 아니며", self.html)


class TestFiguresMatchTheModel(unittest.TestCase):
    """두 도면에 박힌 수치가 여기서 다시 세운 계산과 같은지."""

    @classmethod
    def setUpClass(cls):
        cls.sheets = SHEETS.read_text(encoding="utf-8")
        cls.model = MODEL_3D.read_text(encoding="utf-8")

    def assertFigure(self, text, label, where="both"):
        targets = {"sheets": [("제작도", self.sheets)],
                   "model": [("3D", self.model)],
                   "both": [("제작도", self.sheets), ("3D", self.model)]}[where]
        for name, html in targets:
            self.assertTrue(
                text in html,
                f"{label} 이(가) {name}와 불일치 — '{text}' 가 없음. "
                f"치수를 고쳤다면 도면도 갱신할 것.",
            )

    # ── 연구문서 Rev.0 의 기준값을 재현하는지 ──
    def test_reproduces_research_document_geometry(self):
        self.assertAlmostEqual(V["apex_h"], 346.0, delta=0.5)      # 문서 Cone H346
        self.assertAlmostEqual(V["z_shell_top"], 946.0, delta=0.5)  # 문서 Shell top Z946
        self.assertAlmostEqual(V["z_cover_top"], 951.0, delta=0.5)  # 문서 Cover top Z951
        self.assertAlmostEqual(V["total_l"], 89.9, delta=0.1)       # 문서 총용적 89.9 L
        self.assertFigure(f"{V['total_l']:.2f} L", "전 용적")
        self.assertFigure("Z720", "설계 액면")

    def test_cone_angle_fixes_the_height(self):
        # 60° 를 지키면 높이는 결과값이다 — 원 스케치의 H150 은 여기서 걸러진다.
        self.assertAlmostEqual(V["apex_h"], (ID_MM / 2) / math.tan(HALF), places=9)
        self.assertFigure("60°", "콘 벽면각")
        self.assertFigure(f"{V['apex_h']:.2f}", "콘 이론높이", "sheets")

    def test_cone_development_is_a_half_annulus(self):
        self.assertAlmostEqual(V["dev_angle"], 180.0, places=6)
        self.assertFigure("전개각 180.0°", "콘 전개각", "sheets")
        self.assertFigure(f"R{V['dev_outer']:.0f}", "전개 외반경", "sheets")

    def test_outlet_truncation(self):
        for tag, bore in OUTLET_BORE.items():
            self.assertFigure(f"Z{cut_z(bore):.0f}", f"{tag}″ 절단면", "sheets")

    def test_working_volume_and_nominal_level(self):
        self.assertAlmostEqual(V_LEVEL_L, 61.46, delta=0.05)
        self.assertFigure(f"{V_LEVEL_L:.2f} L", "설계 액면 체적", "sheets")
        self.assertFigure(f"Z{z_for(50.0):.0f}", "호칭 50 L 액면", "sheets")

    # ── 간섭 ──
    def test_document_baffle_and_impeller_cannot_coexist(self):
        """원문 조합(배플 80)은 임펠러와 38 mm 겹친다 — 근거가 도면에 남아야 한다."""
        orig_inner = 200 - BAFFLE_GAP_MM - 80.0
        self.assertLess(orig_inner - D_IMP_MM / 2, 0, "원문 조합이 간섭하지 않는다면 도면 근거가 틀렸다")
        # 도면은 조판용 마이너스(U+2212)를 쓴다
        self.assertFigure(f"\u2212{abs(orig_inner - D_IMP_MM/2):.0f} mm", "원문 간섭량", "sheets")

    def test_adopted_baffle_clears_the_impeller(self):
        clear = BAFFLE_INNER_R - D_IMP_MM / 2
        self.assertGreaterEqual(clear, 15.0, "TIR 1.0 + 편심 0.5 를 흡수할 여유가 없다")
        self.assertFigure(f"간극 {clear:.0f} mm", "채택 간극", "sheets")
        self.assertFigure(f"{clear:.0f} mm", "채택 간극", "model")

    # ── 교반 ──
    def test_impeller_ratio_and_speeds(self):
        self.assertAlmostEqual(D_IMP_MM / ID_MM, 0.750, places=3)
        self.assertFigure(f"{D_IMP_MM / ID_MM:.3f}", "D/T")
        for rpm in RPMS:
            self.assertFigure(f"{rpm}", f"{rpm} rpm 수준", "sheets")

    def test_shaft_power_is_tiny_so_the_motor_is_set_by_startup(self):
        p90 = shaft_power(90)
        self.assertLess(p90, 30.0)          # 90 rpm 에서 23 W
        self.assertFigure(f"{p90:.1f}", "90 rpm 축동력", "sheets")

    def test_just_suspended_speed_sits_inside_the_doe_range(self):
        n = njs(15, 75e-6, 3.0, V_LEVEL_L)
        self.assertTrue(60 <= n <= 90, f"Njs {n:.0f} rpm 이 DOE 범위 밖")
        self.assertFigure(f"{n:.0f} rpm", "Njs")

    # ── 밀도컷 ──
    def test_silicon_always_sinks_and_eva_always_floats(self):
        for w in SALTS:
            for i in range(3):
                self.assertLess(float_prob("Silicon", i, w), 0.001)
                self.assertGreater(float_prob("EVA", i, w), 0.90)

    def test_backsheet_fine_bin_is_the_density_cut(self):
        """31-45 µm 백시트(1110)가 15 % 염수(1111)와 사실상 같다 — 스윕의 중심."""
        self.assertAlmostEqual(rho_brine(15), RHO_EFF["Backsheet"][0][0], delta=2.0)
        self.assertLess(float_prob("Backsheet", 0, 12), 0.5)
        self.assertGreater(float_prob("Backsheet", 0, 18), 0.5)
        for w in SALTS:
            self.assertFigure(f"{rho_brine(w):.0f}", f"{w}% 염수 밀도", "sheets")

    def test_float_probability_table_matches(self):
        for mat in RHO_EFF:
            for i in range(3):
                for w in SALTS:
                    self.assertFigure(f"{float_prob(mat, i, w)*100:.1f} %",
                                      f"{mat} {BINS[i]} {w}% FLOAT 확률", "sheets")

    # ── 운동학 : 이 도면집이 문서에 더한 부분 ──
    def test_stokes_stays_valid_for_bare_particles(self):
        v = stokes(2330, 75e-6, 15)
        re = rho_brine(15) * v * 75e-6 / mu_brine(15)
        self.assertLess(re, 1.0, "Stokes 영역을 벗어나면 표의 속도가 틀린다")

    def test_silicon_clears_the_window_but_polymer_does_not(self):
        for i in range(3):
            self.assertLess(travel_s("Silicon", i, 15), SETTLE_WINDOW_S)
        for mat in ("EVA", "Backsheet"):
            for i in range(3):
                self.assertGreater(travel_s(mat, i, 15), SETTLE_WINDOW_S)

    def test_density_alone_misses_the_polymer_recovery_kpi(self):
        """KPI P10 ≥ 80 % 인데 밀도차만으로는 EVA 34.5 % · BS 13.8 % 다."""
        for mat, expect in (("EVA", 34.5), ("Backsheet", 13.8)):
            got = arrived(mat, 15) * 100
            self.assertAlmostEqual(got, expect, delta=0.3)
            self.assertLess(got, 80.0)
            self.assertFigure(f"{got:.1f} %", f"{mat} 600 s 도달률", "sheets")

    def test_a_single_residual_bubble_closes_the_gap(self):
        bare = travel_s("EVA", 0, 15)
        with_bubble = bubble_travel_s("EVA", 0, 15)
        self.assertGreater(bare / with_bubble, 100, "기포 효과가 100배 미만이면 결론이 바뀐다")
        self.assertFigure(f"{with_bubble:.0f} s", "기포 부착 통과시간", "sheets")
        self.assertFigure(f"{bare:,.0f} s", "기포 없는 통과시간", "sheets")

    def test_travel_time_table_matches(self):
        for mat in RHO_EFF:
            for i in range(3):
                for w in SALTS:
                    t = travel_s(mat, i, w)
                    want = "중립" if t > 1e5 else f"{t:,.0f}"
                    self.assertFigure(want, f"{mat} {BINS[i]} {w}% 통과시간", "sheets")

    # ── 침전 · 링 ──
    def test_sparger_ring_stays_above_the_settled_bed(self):
        """5 kg 배치에서도 링(Z300)이 침전물에 묻히면 안 된다."""
        si_kg = 5.0 * 0.875
        bed_l = si_kg / 2330 / 0.55 * 1000
        z_bed = (bed_l / (math.pi / 3 * math.tan(HALF) ** 2 / 1e9 * 1000)) ** (1 / 3)
        self.assertLess(z_bed, Z_RING_MM)
        self.assertFigure(f"Z{z_bed:.0f}", "5 kg 침전 상단")

    # ── DOE ──
    def test_doe_space_is_1125_conditions(self):
        n = 1
        for k in DOE_LEVELS:
            n *= k
        self.assertEqual(n, 1125)
        self.assertFigure("1,125", "DOE 조건 수", "sheets")


class TestDeviationRecordSurvives(unittest.TestCase):
    """연구문서와 달라진 이유가 도면에서 사라지지 않는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = SHEETS.read_text(encoding="utf-8")

    def test_every_deviation_from_the_research_document_is_recorded(self):
        for item in ("배플 폭", "습부 재질", "공기의 역할", "배플 지지", "콘 절단면",
                     "구동", "커버 체결", "동시 OFF", "T3 측정 항목"):
            self.assertIn(f'<td class="tag">{item}</td>', self.html, item)

    def test_rev_p0_to_rev_a_change_is_recorded(self):
        for item in ("공정 원리", "기준선", "동체", "하부 콘", "전 용적", "임펠러", "액면"):
            self.assertIn(f'<td class="tag">{item}</td>', self.html, item)

    def test_the_hold_items_stay_visible(self):
        for probe in ("CRITICAL HOLD", "Vendor GA", "double cartridge"):
            self.assertIn(probe, self.html, probe)

    def test_the_two_findings_are_stated_in_the_notes(self):
        # 표에만 있고 주기에서 빠지면 제작 현장까지 전달되지 않는다.
        self.assertIn("같은 탱크에 들어가지", self.html)
        self.assertIn("잔류 미세기포", self.html)
        self.assertIn('class="bad"', self.html)


if __name__ == "__main__":
    unittest.main()
