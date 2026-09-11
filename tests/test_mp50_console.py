"""MP-50 운전조건 콘솔 검증 — 요인을 움직였을 때 나오는 수가 실제 식에서 나오는가.

이 장비는 부선기가 아니다. 연구문서 §1 이 못박은 대로 **임펠러와 공기는 분산 수단이며
분리 수단이 아니다.** 제품은 하부 배출과 상부 잔류의 **벌크 분할**이므로, 판정 기준은
「폴리머가 액면까지 올라왔는가」가 아니라 **「분할면의 어느 쪽에 있는가」** 다.

콘솔은 도면 Rev.B 의 물성·기하 위에 세 가지를 더 얹었다. 셋 다 여기서 다시 세워
HTML 이 품은 상수·식과 대조한다.

  · 분할면   — 하부 배출량 → 누적 체적 → 분할면 높이 z_d
  · 간섭침강 — Richardson-Zaki (1−φ)^4.65 로 Feed 량이 KPI 에 실제로 걸리게 한다
  · 온도     — 20 °C 상관식에 물의 점도 온도의존성을 곱한다

이 모듈이 특히 잠그는 것은 **지배 변수가 정치시간이라는 결론**이다 — 가장 느린
실리콘이 분할면까지 내려오는 시간이 DOE 의 최대 600 s 를 넘는다.
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
V_LIQ_M3 = 61.46e-3                  # 액면 Z720 의 액량 m³ (교반 계산용)
D_IMP, NP = 0.300, 1.27
G, RHO_SI, PACK = 9.81, 2330.0, 0.55
Z_RING, Z_LEVEL = 300.0, 720.0
Z_TAN = 200.0 / math.tan(HALF)                   # 346.41 mm
Z_OUT = (34.8 / 2) / math.tan(HALF)              # 30.14
BINS = [(31, 45), (45, 60), (60, 75)]
PSD_W = [0.33, 0.34, 0.33]
RHO_EFF = {"EVA": [980, 950, 920], "BS": [1110, 1060, 1010], "Si": [2330, 2330, 2330]}
FEED_WT = {"EVA": 0.0625, "BS": 0.0625, "Si": 0.875}
DRAW_L = 8.0
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
    return shaft_power(rpm, w) / (V_LIQ_M3 * rho_br(w))


def vol_at(z):
    """콘 정점 Z0 에서 z 까지의 누적 체적 (L)."""
    if z <= Z_TAN:
        return math.pi / 3 * (z * math.tan(HALF)) ** 2 * z / 1e6
    return (math.pi / 3 * (Z_TAN * math.tan(HALF)) ** 2 * Z_TAN / 1e6
            + math.pi * 200 * 200 * (z - Z_TAN) / 1e6)


def z_for_vol(v):
    lo, hi = 0.0, 946.0
    for _ in range(80):
        m = (lo + hi) / 2
        if vol_at(m) < v:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


V_LIQ = vol_at(Z_LEVEL) - vol_at(Z_OUT)          # 61.45 L
PHI = ((5 * 0.875) / RHO_SI + (5 * 0.125) / 1000) / (V_LIQ / 1000)
HIND = (1 - PHI) ** 4.65                          # Richardson-Zaki


def v_mm(rho_p, d, w, T=20, hind=True):
    """mm/s, + 침강."""
    return (rho_p - rho_br(w)) * G * d * d / (18 * mu_br(w, T)) * 1000 * (HIND if hind else 1.0)


def z_draw(draw_l=DRAW_L):
    return z_for_vol(vol_at(Z_OUT) + draw_l)


def t_need(w=15, draw_l=DRAW_L, T=20):
    """가장 느린 실리콘이 액면에서 분할면까지 내려오는 시간 (구간 중앙값 기준)."""
    zd = z_draw(draw_l)
    slow = min(v_mm(2330, (lo + hi) / 2 * 1e-6, w, T) for lo, hi in BINS)
    return (Z_LEVEL - zd) / slow


def split_kpi(w=15, t=600.0, draw_l=DRAW_L, T=20):
    zd = z_draw(draw_l)
    pm = pb = sm = sb = 0.0
    for mat, fr in FEED_WT.items():
        for i, (lo, hi) in enumerate(BINS):
            m = fr * PSD_W[i]
            v = v_mm(RHO_EFF[mat][i], (lo + hi) / 2 * 1e-6, w, T)
            zb = min(Z_LEVEL, max(Z_OUT, zd + v * t))
            below = (vol_at(zb) - vol_at(Z_OUT)) / V_LIQ
            if mat == "Si":
                sm += m
                sb += m * below
            else:
                pm += m
                pb += m * below
    bot = sb + pb
    return dict(top_poly=(pm - pb) / pm * 100, bot_si=sb / sm * 100,
                si_loss=(sm - sb) / sm * 100, bot_poly=pb / bot * 100 if bot else 0.0)


def njs(w=15, T=20, kg=5.0, dp=50e-6):
    rho, mu = rho_br(w), mu_br(w, T)
    X = kg / (V_LIQ_M3 * rho) * 100
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
        for fid in ("w", "T", "mix", "set", "rpm", "air", "draw",
                    "kg", "si", "eva", "shape", "mc"):
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


class TestSplitCriterion(unittest.TestCase):
    """판정 기준 — 부선이 아니라 벌크 분할이다."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_draw_volume_sets_the_plane(self):
        """배출 8 L 를 빼면 분할면은 Z284 다 — 콘(14.5 L)보다 얕은 컷이다."""
        self.assertAlmostEqual(V_LIQ, 61.45, delta=0.05)
        self.assertAlmostEqual(z_draw(8.0), 284, delta=1)
        self.assertLess(z_draw(8.0), Z_TAN, "분할면이 콘 접선보다 위면 배출이 과하다")
        self.assertIn("zForVol(V_OUT+s.draw)", self.html.replace(" ", ""))

    def test_polymer_need_not_reach_the_surface(self):
        """정치 600 s 에 EVA 는 40~185 mm 올라갈 뿐인데도 회수율이 90 % 를 넘는다."""
        rise = [abs(v_mm(RHO_EFF["EVA"][i], (lo + hi) / 2 * 1e-6, 15)) * 600
                for i, (lo, hi) in enumerate(BINS)]
        self.assertLess(max(rise), 200, "액면까지 가지 못한다")
        self.assertGreater(split_kpi(15, 600)["top_poly"], 90, "그래도 상부에 남는다")
        self.assertIn("분할면의 어느 쪽에 있는가", self.html)

    def test_air_and_impeller_are_not_in_the_kpi(self):
        """공기·rpm 은 분산 판정에만 쓰인다 — KPI 식에 들어가면 안 된다."""
        body = self.html[self.html.index("function evaluate("):self.html.index("function run(")]
        for token in ("air", "rpm", "mix"):
            # s.airv (파편이 문 공기, 밀도 효과) 는 허용 — 교반·급기 변수만 막는다
            self.assertIsNone(re.search(r"s\.%s\b" % token, body),
                              f"분리 계산에 s.{token} 이 들어갔다")
        self.assertIn("분산 수단이지 분리 수단이 아니다", self.html)

    def test_settle_time_is_the_binding_variable(self):
        """가장 느린 실리콘이 분할면까지 내려오는 시간이 DOE 상한 600 s 를 넘는다."""
        self.assertAlmostEqual(t_need(15), 700, delta=10)
        self.assertGreater(t_need(15), 600, "600 s 로 충분하면 이 도면의 결론이 무너진다")
        self.assertGreater(t_need(18), t_need(12), "염도를 올리면 더 오래 걸린다")
        self.assertGreater(split_kpi(15, 600)["si_loss"], 3, "600 s 에서는 기준을 넘는다")
        self.assertLess(split_kpi(18, 900)["si_loss"], 3, "900 s 면 들어온다")

    def test_hindered_settling_makes_feed_matter(self):
        """Feed 5 kg 의 간섭침강은 18 % 만큼 느리게 만든다."""
        self.assertAlmostEqual(HIND, 0.82, delta=0.02)
        self.assertAlmostEqual(PHI * 100, 4.1, delta=0.2)
        self.assertIn("Math.pow(1-Math.min(0.45,phiSolids(s)),4.65)", self.html.replace(" ", ""))

    def test_neutral_cell_is_the_polymer_loss_path(self):
        """중립 셀은 제자리에 있으므로 배출 체적비만큼 그대로 하부로 간다."""
        v = v_mm(RHO_EFF["BS"][0], 38e-6, 15)
        self.assertLess(abs(v) * 600, 3, "15 % 에서 31–45 µm 백시트는 사실상 중립")
        self.assertAlmostEqual(DRAW_L / V_LIQ * 100, 13.0, delta=0.3)
        self.assertIn("중립 셀 하부 유입", self.html)


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

    def test_draw_volume_is_a_factor(self):
        """배출량은 Top polymer 와 Bottom Si 를 맞바꾸는 손잡이다."""
        self.assertIn('id="draw"', self.html)
        small, big = split_kpi(15, 600, 3.0), split_kpi(15, 600, 16.0)
        self.assertGreater(small["top_poly"], big["top_poly"])
        self.assertLess(small["bot_si"], big["bot_si"])

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


class TestMaterialDensity(unittest.TestCase):
    """유효밀도와 실밀도는 같은 값이 아니다 — 콘솔이 둘을 구분해 내놓는가."""

    # 문헌값 (kg/m³) — EVA 봉지재는 ASTM D1505, 나머지는 수지 문헌값
    LIT = {"EVA": 948, "PET": 1380, "PVF": 1440, "PVDF": 1760, "Si": 2329}

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_saturated_brine_cannot_float_a_real_backsheet(self):
        """포화 NaCl 상한 1,197 < 백시트 실밀도 1,380~1,760 — 이 장비의 하드 리밋이다."""
        sat = rho_br(26.4)
        self.assertAlmostEqual(sat, 1197.3, delta=0.5)
        for k in ("PET", "PVF", "PVDF"):
            self.assertGreater(self.LIT[k], sat, f"{k} 가 포화 염수보다 가볍다면 결론이 바뀐다")
        self.assertLess(self.LIT["EVA"], 998, "EVA 는 청수에서도 뜬다")
        self.assertIn("어떤 농도에서도 뜨지 않는다", self.html)

    def test_console_offers_three_density_sources(self):
        for key in ("doc", "lit", "cmp"):
            self.assertIn('data-k="%s"' % key, self.html)
        packed = self.html.replace(" ", "")
        self.assertIn("EVA:[[948,15],[948,15],[948,15]]", packed)
        self.assertIn("BS:[[1450,150],[1450,150],[1450,150]]", packed)

    def test_entrapped_air_is_modelled_as_density_not_flotation(self):
        """미습윤 파편이 문 공기는 밀도 효과로만 다룬다 — 부착 속도식이 아니다."""
        self.assertIn("function withAir(", self.html)
        self.assertIn("rho_p*(1-a)+1.2*a", self.html.replace(" ", ""))
        self.assertLess(1200 * (1 - 0.083) + 1.2 * 0.083, rho_br(15))
        self.assertGreater(1200 * (1 - 0.05) + 1.2 * 0.05, rho_br(15))
        self.assertIn("8.3", self.html)

    def test_composite_fragment_sits_at_the_saturation_boundary(self):
        """EVA 50 vol% + 백시트 50 vol% ≈ 1,200 — 포화 NaCl 경계다."""
        comp = 0.5 * self.LIT["EVA"] + 0.5 * 1450
        self.assertAlmostEqual(comp, 1199, delta=5)
        self.assertAlmostEqual((comp - 998) / 7.55, 26.6, delta=0.3)

    def test_literature_densities_cost_polymer_recovery(self):
        """실밀도를 쓰면 상부 폴리머가 무너진다 — 그것이 이 전환의 요점이다."""
        doc = split_kpi(15, 600)["top_poly"]
        zd, pm, pb = z_draw(), 0.0, 0.0
        for rho_p in (948, 1450):
            for i, (lo, hi) in enumerate(BINS):
                m = 0.0625 * PSD_W[i]
                v = v_mm(rho_p, (lo + hi) / 2 * 1e-6, 15)
                zb = min(Z_LEVEL, max(Z_OUT, zd + v * 600))
                pm += m
                pb += m * (vol_at(zb) - vol_at(Z_OUT)) / V_LIQ
        lit = (pm - pb) / pm * 100
        self.assertLess(lit, doc - 15, "실밀도에서 회수율이 크게 떨어져야 한다")
        self.assertIn("2단 밀도컷", self.html)


if __name__ == "__main__":
    unittest.main()
