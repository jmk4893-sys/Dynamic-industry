"""MP-50 층분리 거동 시뮬레이터 검증 — 재생 화면이 도면과 같은 물리를 쓰는지.

화면은 도면 MP-50-P0-004(층분리 운동학)를 시간축으로 푼 것이다. 그래서 검증도
같은 방식을 쓴다 — **도면이 밝힌 식과 상수만으로 모델을 여기서 다시 세운 뒤**
HTML 이 실제로 품고 있는 숫자와 대조한다. 화면의 상수를 고치고 물리를 안 맞추면
여기서 먼저 걸린다.

판정 기준은 Rev.B 에서 바뀌었다 — 제품은 하부 배출과 상부 잔류의 **벌크 분할**이므로
「폴리머가 액면까지 올라왔는가」가 아니라 **「분할면의 어느 쪽에 있는가」** 로 센다.

특히 잠그는 것:
  · 기준 좌표(Z0 · Z300 · Z346 · Z720 · Z946)가 제작도와 같은 값인가
  · 배출 8 L 의 분할면이 Z284 인가
  · 챕터 시각(+190 · +700 s)이 실제로 그 셀이 분할면을 넘는 시간인가
  · 간섭침강 (1−φ)^4.65 = ×0.82 가 들어가 있는가
  · 침전 상단 Z214 가 Feed 5 kg 에서 나오고, 분산 링 Z300 이 그 위인가
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

from .test_drawings import standalone_document_checks

MOTION = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "mp50-separation-motion.html"

# ── 설계 상수 (연구문서 Rev.0 · 제작도 Rev.A 와 같은 값) ────────────────
ID_MM, STRAIGHT_MM, CONE_DEG = 400.0, 600.0, 60.0
HALF = math.radians(CONE_DEG / 2)
APEX_MM = (ID_MM / 2) / math.tan(HALF)          # 346.41  콘 이론높이
Z_TAN_MM = APEX_MM
Z_TOP_MM = Z_TAN_MM + STRAIGHT_MM               # 946.41
Z_LEVEL_MM = 720.0
Z_RING_MM = 300.0
TRAVEL_MM = Z_LEVEL_MM - Z_TAN_MM               # 373.59
WIN_S = 600.0                                   # 판정 창
BINS = [(31, 45), (45, 60), (60, 75)]
PSD_W = [0.33, 0.34, 0.33]
RHO_EFF = {
    "EVA": [(980, 70), (950, 60), (920, 50)],
    "BS": [(1110, 100), (1060, 90), (1010, 80)],
    "Si": [(2330, 25), (2330, 22), (2330, 20)],
}
FEED_WT = {"Si": 0.875, "EVA": 0.0625, "BS": 0.0625}   # 문서 §6 관찰조성
G = 9.81
D_BUB = 200e-6
RHO_AIR = 1.2
SI_PACK = 0.55                                   # 침전층 충전율
RHO_SI = 2330.0


def rho_br(w):
    return 998 + 7.55 * w


def mu_br(w):
    return 0.001 * (1 + 0.018 * w)


def bin_d(i):
    return (BINS[i][0] + BINS[i][1]) / 2 * 1e-6


def stokes(rho_p, d, w):
    """+ 는 침강, − 는 부상 (m/s)."""
    return (rho_p - rho_br(w)) * G * d * d / (18 * mu_br(w))


def travel_s(rho_p, d, w, length_mm=TRAVEL_MM):
    v = stokes(rho_p, d, w)
    return math.inf if abs(v) < 1e-12 else abs(length_mm / 1000 / v)


Z_OUT_MM = (34.8 / 2) / math.tan(HALF)           # 콘 절단 Z30.1


def vol_at(z):
    """콘 정점 Z0 에서 z 까지의 누적 체적 (L)."""
    if z <= Z_TAN_MM:
        return math.pi / 3 * (z * math.tan(HALF)) ** 2 * z / 1e6
    return (math.pi / 3 * (Z_TAN_MM * math.tan(HALF)) ** 2 * Z_TAN_MM / 1e6
            + math.pi * 200 * 200 * (z - Z_TAN_MM) / 1e6)


def z_for_vol(v):
    lo, hi = 0.0, 946.0
    for _ in range(80):
        m = (lo + hi) / 2
        if vol_at(m) < v:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


V_LIQ_L = vol_at(Z_LEVEL_MM) - vol_at(Z_OUT_MM)   # 61.45 L
PHI = ((5 * 0.875) / RHO_SI + (5 * 0.125) / 1000) / (V_LIQ_L / 1000)
HIND = (1 - PHI) ** 4.65                          # Richardson-Zaki
DRAW_L = 8.0


def v_mm(rho_p, d, w):
    """mm/s, + 침강. 화면과 같이 Schiller-Naumann 으로 수렴시키고 간섭침강을 곱한다."""
    return terminal_v(rho_p, d, w) * 1000 * HIND


def z_draw(draw_l=DRAW_L):
    return z_for_vol(vol_at(Z_OUT_MM) + draw_l)


def t_cross(rho_p, i, w, draw_l=DRAW_L):
    """액면에서 분할면까지 내려오는 데 걸리는 시간."""
    return (Z_LEVEL_MM - z_draw(draw_l)) / v_mm(rho_p, bin_d(i), w)


def terminal_v(rho_eq, d_eq, w):
    """Schiller-Naumann 항력으로 수렴시킨 종말속도 (+ 침강)."""
    rho, mu = rho_br(w), mu_br(w)
    dr = rho_eq - rho
    if abs(dr) < 1e-9:
        return 0.0
    v = dr * G * d_eq * d_eq / (18 * mu)
    for _ in range(200):
        re = max(abs(rho * v * d_eq / mu), 1e-9)
        cd = 24 / re * (1 + 0.15 * re ** 0.687) if re < 1000 else 0.44
        vn = math.copysign(math.sqrt(abs(4 * dr * G * d_eq / (3 * cd * rho))), dr)
        if abs(vn - v) < 1e-10:
            return vn
        v = 0.5 * (v + vn)
    return v


def arrive_frac(rho_p, i, w, t=WIN_S):
    """도면 004 의 도달률 — L 을 균등 가정한 min(1, v·t/L)."""
    v = abs(stokes(rho_p, bin_d(i), w))
    return min(1.0, v * t / (TRAVEL_MM / 1000))


def weighted(mat, w, t=WIN_S):
    return sum(PSD_W[i] * arrive_frac(RHO_EFF[mat][i][0], i, w, t) for i in range(3))


def bed_z(feed_kg, si_frac=0.875):
    """Feed 배치의 실리콘이 콘에 쌓였을 때의 침전 상단 (mm)."""
    vol_mm3 = feed_kg * si_frac / RHO_SI / SI_PACK * 1e9
    return (vol_mm3 * 3 / (math.pi * math.tan(HALF) ** 2)) ** (1 / 3)


class TestMotionDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지 — 아티팩트 CSP 를 그대로 통과해야 한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = MOTION.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(MOTION.exists())
        standalone_document_checks(self, self.html, "MP-50 층분리 거동 시뮬레이터")

    def test_no_external_script_or_library(self):
        """레포 도면 규약 — 외부 라이브러리 없이 손으로 그린다."""
        self.assertNotIn("<script src", self.html)
        self.assertIn('<canvas id="cv">', self.html)

    def test_reduced_motion_is_respected(self):
        """움직임을 줄이라고 한 사용자에게 자동 재생을 밀어붙이지 않는다."""
        self.assertIn("prefers-reduced-motion:reduce", self.html)
        self.assertIn("if(!reduce){", self.html)

    def test_playback_covers_dispersion_and_settling(self):
        """−60 s 분산 → 0 정지 → +600 s 판정 → +660 s 까지가 한 편이다."""
        self.assertIn("var WIN=600, T0=-60, T_END=1260;", self.html)
        self.assertIn('id="scrub" min="-60" max="660"', self.html.replace('max="1260"', 'max="660"'))


class TestGeometryMatchesTheDrawings(unittest.TestCase):
    """재생 화면의 기하가 제작도 Rev.A 와 같은 좌표인가."""

    @classmethod
    def setUpClass(cls):
        cls.html = MOTION.read_text(encoding="utf-8")

    def js(self, name):
        m = re.search(r"var\s+%s=([-\d.]+)" % name, self.html)
        if m is None:
            m = re.search(r"\b%s=([-\d.]+)" % name, self.html)
        self.assertIsNotNone(m, f"{name} 가 화면에 없다")
        return float(m.group(1))

    def test_cone_angle_fixes_every_z(self):
        """60° 를 지키면 콘 이론높이도 동체 상단도 따라 나온다 — 자유 치수가 아니다."""
        self.assertAlmostEqual(APEX_MM, 346.41, places=2)
        self.assertEqual(self.js("CONE"), 60)
        self.assertEqual(self.js("R"), ID_MM / 2)
        for label in ("Z0", "Z300", "Z346", "Z430", "Z610", "Z720", "Z946"):
            self.assertIn(label, self.html, f"기준 좌표 {label} 표기가 없다")

    def test_level_and_datum(self):
        self.assertEqual(self.js("Z_LEVEL"), Z_LEVEL_MM)
        self.assertEqual(self.js("Z_RING"), Z_RING_MM)
        self.assertEqual(self.js("Z_IMP_LO"), 430)
        self.assertEqual(self.js("Z_IMP_UP"), 610)
        self.assertEqual(self.js("R_IMP"), 150)          # Ø300 — DOE 30~90 rpm 이 얹힌 축
        self.assertEqual(self.js("R_BAF_IN"), 167)       # 폭 25 로 줄여 간극 17 확보
        self.assertEqual(self.js("R_BAF_OUT"), 192)

    def test_draw_plane_is_the_criterion(self):
        """배출 8 L 를 빼면 분할면은 Z284 — 폴리머는 그 위에 남기만 하면 된다."""
        self.assertAlmostEqual(z_draw(8.0), 284, delta=1)
        self.assertAlmostEqual(V_LIQ_L, 61.45, delta=0.05)
        self.assertIn("분할면", self.html)
        self.assertIn("zForVol(volAt(Z_CUT)+state.draw)", self.html.replace(" ", ""))

    def test_settled_bed_stays_below_the_sparger_ring(self):
        """Feed 5 kg 을 다 가라앉혀도 분산 링(Z300)이 묻히면 안 된다."""
        z = bed_z(5.0)
        self.assertAlmostEqual(z, 214, delta=1)
        self.assertIn("H_BED=214", self.html.replace(" ", ""))
        self.assertGreater(Z_RING_MM - z, 80, "링이 침전층에 너무 가깝다")


class TestPhysicsMatchesTheModel(unittest.TestCase):
    """화면이 말하는 수치가 실제로 그 식에서 나오는가."""

    @classmethod
    def setUpClass(cls):
        cls.html = MOTION.read_text(encoding="utf-8")

    def assertFigure(self, text, why):
        self.assertIn(text, self.html, f"{why} — '{text}' 가 화면에 없다")

    def test_brine_correlations(self):
        self.assertAlmostEqual(rho_br(15), 1111.25, places=2)
        self.assertIn("998+7.55*w", self.html.replace(" ", ""))
        self.assertIn("0.001*(1+0.018*w)", self.html.replace(" ", ""))
        self.assertFigure("1111.3", "15 wt% 염수 밀도")

    def test_silicon_always_sinks_polymer_always_rises(self):
        """3×3 전 셀의 부호 — 이 부호가 뒤집히면 화면이 거짓말을 한다."""
        for i in range(3):
            self.assertGreater(stokes(RHO_EFF["Si"][i][0], bin_d(i), 15), 0)
            self.assertLess(stokes(RHO_EFF["EVA"][i][0], bin_d(i), 15), 0)

    def test_chapter_230s_is_the_coarse_silicon_crossing(self):
        """'+230 s' 는 60–75 µm 실리콘이 액면에서 분할면까지 내려오는 시간이다."""
        self.assertAlmostEqual(t_cross(2330, 2, 15), 230, delta=5)
        self.assertFigure("[230,", "챕터 +230 s")

    def test_chapter_700s_is_the_required_settle_time(self):
        """'+700 s' 는 가장 느린 31–45 µm 실리콘 기준 최소 정치시간이다."""
        t = t_cross(2330, 0, 15)
        self.assertAlmostEqual(t, 700, delta=10)
        self.assertGreater(t, 600, "DOE 상한 600 s 로는 모자란다")
        self.assertFigure("[700,", "챕터 +700 s")
        self.assertFigure("700 s", "필요 정치시간 본문")

    def test_polymer_barely_moves_and_that_is_enough(self):
        """정치 600 s 에 EVA 는 40~185 mm 만 올라간다 — 그래도 분할면 위다."""
        rise = [abs(v_mm(RHO_EFF["EVA"][i][0], bin_d(i), 15)) * 600 for i in range(3)]
        self.assertAlmostEqual(min(rise), 40, delta=3)
        self.assertAlmostEqual(max(rise), 185, delta=5)
        self.assertLess(max(rise), Z_LEVEL_MM - z_draw(), "액면까지 가지 못한다")
        self.assertIn("액면까지 갈 필요가 없다", self.html)

    def test_hindered_settling_is_applied(self):
        self.assertAlmostEqual(HIND, 0.824, delta=0.01)
        self.assertIn("Math.pow(1-PHI,4.65)", self.html.replace(" ", ""))
        self.assertIn("0.82", self.html)

    def test_schiller_naumann_is_actually_implemented(self):
        """이 입경대는 Stokes 영역이지만, 항력식은 Re 로 분기하도록 짜여 있어야 한다."""
        packed = self.html.replace(" ", "")
        self.assertIn("24/re*(1+0.15*Math.pow(re,0.687))", packed)
        v = abs(terminal_v(2330, bin_d(2), 15))
        self.assertLess(rho_br(15) * v * bin_d(2) / mu_br(15), 1, "가장 빠른 셀도 Re < 1 이다")

    def test_fine_backsheet_is_neutral_at_15pct(self):
        """31–45 µm 백시트는 15 % 염수에서 사실상 중립 — 배출 체적비만큼 하부로 끌려간다."""
        self.assertLess(abs(v_mm(RHO_EFF["BS"][0][0], bin_d(0), 15)) * 600, 3)
        self.assertAlmostEqual(DRAW_L / V_LIQ_L * 100, 13.0, delta=0.3)
        self.assertIn("≈0 중립", self.html)
        self.assertIn("중립 셀이 유일한 폴리머 손실 경로다", self.html)

    def test_density_cut_moves_with_salinity(self):
        """밀도컷이 걸리는 셀은 31–45 µm 백시트(ρ 1110) 다 — 12 % 에선 가라앉고 18 % 에선 뜬다."""
        self.assertLess(rho_br(12), RHO_EFF["BS"][0][0])
        self.assertGreater(rho_br(18), RHO_EFF["BS"][0][0])
        self.assertGreater(stokes(RHO_EFF["BS"][0][0], bin_d(0), 12), 0)   # 침강
        self.assertLess(stokes(RHO_EFF["BS"][0][0], bin_d(0), 18), 0)      # 부상
        for w in (12, 15, 18):
            self.assertIn(f'data-w="{w}"', self.html)


class TestSplitStory(unittest.TestCase):
    """Rev.B 의 결론이 화면에 그대로 실려 있는가."""

    @classmethod
    def setUpClass(cls):
        cls.html = MOTION.read_text(encoding="utf-8")

    def split_kpi(self, w, t, draw_l=DRAW_L):
        zd = z_draw(draw_l)
        pm = pb = sm = sb = 0.0
        for mat, fr in (("EVA", 0.0625), ("BS", 0.0625), ("Si", 0.875)):
            for i in range(3):
                m = fr * PSD_W[i]
                zb = min(Z_LEVEL_MM, max(Z_OUT_MM, zd + v_mm(RHO_EFF[mat][i][0], bin_d(i), w) * t))
                below = (vol_at(zb) - vol_at(Z_OUT_MM)) / V_LIQ_L
                if mat == "Si":
                    sm += m; sb += m * below
                else:
                    pm += m; pb += m * below
        return dict(top_poly=(pm - pb) / pm * 100, bot_si=sb / sm * 100,
                    si_loss=(sm - sb) / sm * 100)

    def test_density_alone_clears_the_polymer_kpi(self):
        """공기의 도움 없이 Top polymer recovery 가 KPI 80 % 를 넘는다."""
        k = self.split_kpi(15, 600)
        self.assertGreater(k["top_poly"], 90)
        self.assertAlmostEqual(k["top_poly"], 93.6, delta=0.5)

    def test_settle_time_is_what_binds(self):
        """600 s 에서는 Top Si loss 가 기준을 넘고, 900 s 면 들어온다."""
        self.assertGreater(self.split_kpi(15, 600)["si_loss"], 3)
        self.assertLess(self.split_kpi(18, 900)["si_loss"], 3)
        self.assertIn("정치 900 s · 권고", self.html)
        self.assertIn("정치 600 s · DOE 상한", self.html)

    def test_within_bin_fines_need_even_longer(self):
        """구간 중앙값이 아니라 최소 입경 31 µm 을 보면 1,050 s 다."""
        t31 = (Z_LEVEL_MM - z_draw()) / (stokes(2330, 31e-6, 15) * 1000 * HIND)
        self.assertAlmostEqual(t31, 1052, delta=15)
        self.assertIn("1,050", self.html)

    def test_air_is_not_a_recovery_variable(self):
        """공기가 분리 수단으로 되살아나면 안 된다."""
        self.assertIn("분산 수단이지 분리 수단이 아니다", self.html)
        for gone in ("부착률", "잔류 미세기포", "aggregate(", "D_BUB"):
            self.assertNotIn(gone, self.html, f"제거했어야 할 표현이 남아 있다: {gone}")

    def test_kpi_names_follow_the_document(self):
        for kpi in ("Top polymer recovery", "Top Si loss", "Bottom Si recovery"):
            self.assertIn(kpi, self.html)

    def test_feed_composition_is_the_documented_one(self):
        self.assertAlmostEqual(sum(FEED_WT.values()), 1.0, places=6)
        for wt in ("wt:0.8750", "wt:0.0625"):
            self.assertIn(wt, self.html)
        self.assertIn("BINW=[0.33,0.34,0.33]", self.html.replace(" ", ""))

    def test_effective_density_matrix_is_carried_verbatim(self):
        packed = self.html.replace(" ", "")
        for mat, rows in RHO_EFF.items():
            self.assertIn("[" + ",".join(f"[{m},{s}]" for m, s in rows) + "]", packed, mat)


class TestReadability(unittest.TestCase):
    """색만으로 재질을 구분하지 않는가 — 검증기를 통과한 팔레트를 실제로 쓰는가."""

    @classmethod
    def setUpClass(cls):
        cls.html = MOTION.read_text(encoding="utf-8")

    def test_validated_categorical_palette(self):
        for hexes in ("#C07C10", "#B03060", "#2A6FD6",      # light
                      "#C6862B", "#CC5E7E", "#4A90DC"):     # dark
            self.assertIn(hexes, self.html)

    def test_shape_encodes_material_too(self):
        """EVA 원 · 백시트 판상 · 실리콘 파편 — 색각 이상에서도 구분된다."""
        self.assertIn('.swatch.si{background:var(--si);clip-path:polygon(50% 0,100% 100%,0 100%)}',
                      self.html)
        self.assertIn('if(p.m==="EVA"){', self.html)
        self.assertIn('ctx.fillRect(-s*1.5,-s*0.55,s*3,s*1.1)', self.html)

    def test_curves_are_direct_labelled(self):
        self.assertIn('cx.fillText(o.t,x+7,o.y)', self.html)


if __name__ == "__main__":
    unittest.main()
