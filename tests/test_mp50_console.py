"""MP-50 운전조건 콘솔 검증 — 요인을 움직였을 때 나오는 수가 실제 식에서 나오는가.

콘솔은 도면 Rev.A 의 물성·기하 위에 세 가지 모델을 더 얹었다. 셋 다 여기서 다시
세워 HTML 이 품은 상수·식과 대조한다.

  · 기포경   — Ø1.0 홀의 Tate 이탈경과 임펠러 난류의 Hinze 파쇄한계 중 작은 쪽
  · 부착     — 1차 부선속도 k = 1.5·U_g·E/d_b, 차단 포집 E = (d_p/d_b)²
  · 온도     — 20 °C 상관식에 물의 점도 온도의존성을 곱한다

이 모듈이 특히 잠그는 것은 **콘솔이 스스로 내놓는 결론**이다. 현 스파저·교반으로는
Ø200 µm 기포가 나오지 않는다는 것, 그리고 그 사실이 회수율 KPI 를 좌우한다는 것.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

from .test_drawings import standalone_document_checks

CONSOLE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "mp50-process-console.html"

# ── 설계 상수 (도면 Rev.A) ─────────────────────────────────────────────
ID, R = 0.400, 0.200
HALF = math.radians(30)
AREA = math.pi / 4 * ID ** 2
V_LIQ = 61.46e-3                     # 액면 Z720 의 액량 m³
D_IMP, NP = 0.300, 1.27
G, SIG, RHO_AIR, RHO_SI, PACK = 9.81, 0.076, 1.2, 2330.0, 0.55
D_HOLE = 1.0e-3
Z_RING = 300.0
BINS = [(31, 45), (45, 60), (60, 75)]
LIMITS = {"poly": 80, "siLoss": 3, "siRec": 90, "botPoly": 12}


def rho_br(w):
    return 998 + 7.55 * w


def mu_w(T):
    """물의 점도 온도의존성 (Vogel 근사) — 20 °C 기준으로 정규화해 쓴다."""
    return math.exp(-3.7188 + 578.919 / (T + 273.15 - 137.546))


def mu_br(w, T=20):
    return 0.001 * (1 + 0.018 * w) * mu_w(T) / mu_w(20)


def shaft_power(rpm, w=15):
    n = rpm / 60
    return 2 * NP * rho_br(w) * n ** 3 * D_IMP ** 5


def epsilon(rpm, w=15):
    return shaft_power(rpm, w) / (V_LIQ * rho_br(w))


def d_tate(w=15):
    """오리피스에서 부력으로 떨어져 나올 때의 기포경."""
    return (6 * D_HOLE * SIG / (G * (rho_br(w) - RHO_AIR))) ** (1 / 3)


def d_hinze(rpm, w=15):
    return 0.725 * (SIG / rho_br(w)) ** 0.6 * epsilon(rpm, w) ** -0.4


def eps_for(d, w=15):
    """그 기포경을 난류로 유지하려면 필요한 소산율."""
    return (0.725 * (SIG / rho_br(w)) ** 0.6 / d) ** 2.5


def k_float(air_lpm, d_b, d_p, phob=1.0):
    """1차 부선속도 (1/s)."""
    ug = air_lpm / 1000 / 60 / AREA
    return 1.5 * ug * (d_p / d_b) ** 2 * phob / d_b


def njs(w=15, T=20, kg=5.0, dp=50e-6):
    rho, mu = rho_br(w), mu_br(w, T)
    X = kg / (V_LIQ * rho) * 100
    S = 6.0 * (0.5 / (D_IMP / ID)) ** 1.3
    return (S * (mu / rho) ** 0.1 * (G * (RHO_SI - rho) / rho) ** 0.45
            * X ** 0.13 * dp ** 0.2 / D_IMP ** 0.85 * 60)


def bed_z(kg, si=0.875):
    return (kg * si / RHO_SI / PACK * 1e9 * 3 / (math.pi * math.tan(HALF) ** 2)) ** (1 / 3)


class TestConsoleDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(CONSOLE.exists())
        standalone_document_checks(self, self.html, "MP-50 운전조건 콘솔")

    def test_no_external_library(self):
        self.assertNotIn("<script src", self.html)

    def test_every_factor_has_a_control(self):
        """요인을 하나 지우면 콘솔이 아니라 그림이 된다."""
        for fid in ("w", "T", "mix", "set", "rpm", "air", "skim",
                    "kg", "si", "eva", "db", "ret", "kf", "sel", "mc"):
            self.assertRegex(self.html, r'id="%s"[^>]*type="range"|type="range"[^>]*id="%s"' % (fid, fid),
                             f"요인 {fid} 슬라이더가 없다")

    def test_time_and_salinity_ranges_cover_the_doe(self):
        """DOE 는 정치 60~600 s · 염도 12/15/18 wt% 를 쓴다 — 그 바깥까지 볼 수 있어야 한다."""
        m = re.search(r'id="set" min="(\d+)" max="(\d+)"', self.html)
        self.assertIsNotNone(m)
        self.assertLessEqual(int(m.group(1)), 60)
        self.assertGreaterEqual(int(m.group(2)), 600)
        m = re.search(r'id="w" min="(\d+)" max="(\d+)"', self.html)
        self.assertLessEqual(int(m.group(1)), 12)
        self.assertGreaterEqual(int(m.group(2)), 18)


class TestBubbleModel(unittest.TestCase):
    """콘솔의 핵심 결론 — 현 장치는 미세기포를 못 만든다."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_tate_detachment_from_the_1mm_hole(self):
        self.assertAlmostEqual(d_tate() * 1000, 3.47, delta=0.02)
        self.assertIn("6*D_HOLE*SIG/(G*(rho-RHO_AIR))", self.html.replace(" ", ""))
        self.assertIn("D_HOLE=1.0e-3", self.html.replace(" ", ""))

    def test_hinze_limit_at_the_doe_ceiling(self):
        """DOE 상한 90 rpm 에서도 파쇄한계가 mm 급이다."""
        self.assertAlmostEqual(epsilon(90), 0.339, delta=0.01)
        self.assertAlmostEqual(shaft_power(90), 23.1, delta=0.2)
        self.assertAlmostEqual(d_hinze(90) * 1000, 3.54, delta=0.05)
        self.assertGreater(min(d_tate(), d_hinze(90)), 1e-3, "교반으로 mm 아래로 못 내려간다")
        self.assertIn("0.725*Math.pow(SIG/rho,0.6)*Math.pow(eps,-0.4)", self.html.replace(" ", ""))

    def test_200um_by_stirring_is_out_of_reach(self):
        """Ø200 µm 를 교반으로 만들려면 지금의 세 자릿수 배가 필요하다."""
        need = eps_for(200e-6)
        self.assertAlmostEqual(need, 447, delta=5)
        self.assertGreater(need / epsilon(90), 1000)
        self.assertIn("미세기포는 벤투리·이젝터나 다공막 스파저 같은 별도 장치로", self.html)

    def test_attachment_rate_collapses_with_bubble_size(self):
        """3.5 mm 기포로는 몇 시간, 200 µm 면 몇 초 — 이 대비가 설계의 전부다."""
        k_big = k_float(5, d_tate(), 50e-6)
        k_fine = k_float(5, 200e-6, 50e-6)
        t70_big = -math.log(0.3) / k_big
        t70_fine = -math.log(0.3) / k_fine
        self.assertGreater(t70_big / 3600, 5, "현 스파저로 70 % 부착에 5시간 이상")
        self.assertLess(t70_fine, 10, "미세기포면 10초 안")
        self.assertGreater(k_fine / k_big, 1000)
        self.assertIn("k=1.5*Ug*E/B.d_b", self.html.replace(" ", ""))

    def test_interception_efficiency_form(self):
        self.assertIn("Math.pow(dp(i)/B.d_b,2)", self.html.replace(" ", ""))
        self.assertIn("E=(d_p/d_b)²", self.html)


class TestPhysicsCarriedFromTheDrawings(unittest.TestCase):
    """도면 Rev.A 에서 가져온 값이 그대로인가."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_brine_and_temperature(self):
        self.assertAlmostEqual(rho_br(15), 1111.25, places=2)
        self.assertIn("998+7.55*w", self.html.replace(" ", ""))
        self.assertAlmostEqual(mu_br(15, 10) / mu_br(15, 20), 1.29, delta=0.02)
        self.assertAlmostEqual(mu_br(15, 40) / mu_br(15, 20), 0.65, delta=0.02)
        self.assertIn("578.919", self.html)

    def test_geometry_and_bed(self):
        self.assertAlmostEqual(R / math.tan(HALF) * 1000, 346.41, places=2)
        self.assertAlmostEqual(bed_z(5.0), 214, delta=1)
        self.assertIn("Z_RING=300", self.html.replace(" ", ""))
        self.assertGreater(Z_RING, bed_z(5.0))

    def test_njs_matches_the_doe_ceiling(self):
        """Feed 5 kg 에서 Njs 78 rpm — DOE 의 30/45/60 rpm 은 완전 현탁이 아니다."""
        self.assertAlmostEqual(njs(kg=5.0), 78, delta=1)
        self.assertLess(njs(kg=1.0), njs(kg=8.0))
        self.assertIn("Zwietering", self.html)

    def test_density_cut_neutral_point_is_flagged(self):
        """설계점 15 wt% 는 백시트 31–45 µm 중립점 바로 위다."""
        w_cut = (1110 - 998) / 7.55
        self.assertAlmostEqual(w_cut, 14.83, places=2)
        self.assertLess(abs(15 - w_cut), 0.2)
        self.assertIn("(1110-998)/7.55", self.html.replace(" ", ""))
        self.assertIn("중립점", self.html)

    def test_feed_composition_and_bins(self):
        self.assertIn("BINS=[[31,45],[45,60],[60,75]]", self.html.replace(" ", ""))
        self.assertIn("BINW=[0.33,0.34,0.33]", self.html.replace(" ", ""))
        self.assertIn('value="87.5"', self.html)          # Si 기본 조성


class TestVerdictLogic(unittest.TestCase):
    """판정이 문서의 KPI 한계를 쓰는가."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_acceptance_limits(self):
        packed = self.html.replace(" ", "")
        self.assertIn("LIM={poly:80,siLoss:3,siRec:90,botPoly:12}", packed)
        for name in ("Top polymer recovery", "Top Si loss", "Bottom Si recovery", "Bottom polymer"):
            self.assertIn(name, self.html)

    def test_p10_p90_are_the_gate_not_the_mean(self):
        """평균이 아니라 백분위로 판정해야 '강건'이라 부를 수 있다."""
        packed = self.html.replace(" ", "")
        self.assertIn("ok:pct(P.poly,0.10)>=LIM.poly", packed)
        self.assertIn("ok:pct(P.siLoss,0.90)<=LIM.siLoss", packed)
        self.assertIn("ok:pct(P.siRec,0.10)>=LIM.siRec", packed)
        self.assertIn("ok:pct(P.botPoly,0.90)<=LIM.botPoly", packed)

    def test_monte_carlo_is_deterministic(self):
        """같은 조건이면 같은 답이 나와야 조건 비교가 의미를 갖는다."""
        self.assertIn("seed=20260911", self.html.replace(" ", ""))

    def test_silicon_selectivity_is_a_factor_not_a_constant(self):
        """미세기포를 쓰면 실리콘도 뜬다 — 선택도를 손잡이로 내놓아야 한다."""
        self.assertIn('id="sel"', self.html)
        self.assertIn("ph=mat.poly?mat.phob:1/s.sel", self.html.replace(" ", ""))

    def test_assumptions_are_labelled(self):
        self.assertIn("ASSUMED", self.html)
        self.assertIn("설계 참고값이며 성능 보증값이 아니다", self.html)


class TestReadability(unittest.TestCase):
    """검증기를 통과한 팔레트와 2차 부호를 그대로 쓰는가."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_validated_categorical_palette(self):
        for hx in ("#C6862B", "#CC5E7E", "#4A90DC",      # dark
                   "#C07C10", "#B03060", "#2A6FD6"):     # light
            self.assertIn(hx, self.html)

    def test_shape_encodes_material(self):
        self.assertIn("function marker(", self.html)
        self.assertIn("c.arc(x,y,s,0,6.284)", self.html.replace(" ", ""))
        self.assertIn("c.rect(x-s,y-s,2*s,2*s)", self.html.replace(" ", ""))

    def test_curves_are_direct_labelled(self):
        self.assertIn('c.fillText(o.t+" "+o.v.toFixed(0)+"%"', self.html)


if __name__ == "__main__":
    unittest.main()
