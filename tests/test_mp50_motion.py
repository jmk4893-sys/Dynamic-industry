"""MP-50 층분리 거동 시뮬레이터 검증 — 재생 화면이 도면과 같은 물리를 쓰는지.

화면은 도면 MP-50-P0-004(층분리 운동학)를 시간축으로 푼 것이다. 그래서 검증도
같은 방식을 쓴다 — **도면이 밝힌 식과 상수만으로 모델을 여기서 다시 세운 뒤**
HTML 이 실제로 품고 있는 숫자와 대조한다. 화면의 상수를 고치고 물리를 안 맞추면
여기서 먼저 걸린다.

특히 잠그는 것:
  · 기준 좌표(Z0 · Z300 · Z346 · Z720 · Z946)가 제작도와 같은 값인가
  · 챕터 시각(+25 · +157 s)이 실제로 그 셀의 통과시간인가
  · 기포 등가밀도 7.9 kg/m³ 와 4,593 s 가 Ø200 µm 기포에서 나오는가
  · KPI 80 % 를 위한 부착률 하한(EVA 69 % · 백시트 77 %)이 도면 값과 같은가
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


def aggregate(rho_p, d_p, d_b=D_BUB):
    """입자 + 잔류 기포 1개의 등가밀도·등가경."""
    v_p = math.pi / 6 * d_p ** 3
    v_b = math.pi / 6 * d_b ** 3
    return (rho_p * v_p + RHO_AIR * v_b) / (v_p + v_b), (6 * (v_p + v_b) / math.pi) ** (1 / 3)


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
        self.assertIn("var WIN=600, T0=-60, T_END=660;", self.html)
        self.assertIn('id="scrub" min="-60" max="660"', self.html)


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

    def test_travel_distance(self):
        """상승 입자가 지나야 하는 거리는 액면 − 콘 접선 이다."""
        self.assertAlmostEqual(TRAVEL_MM, 373.59, places=2)
        self.assertIn("373.6", self.html)

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

    def test_chapter_157s_is_the_coarse_silicon_travel_time(self):
        """'+157 s 실리콘이 콘에 닿기 시작' 은 60–75 µm 셀의 통과시간이다."""
        t = travel_s(RHO_EFF["Si"][2][0], bin_d(2), 15)
        self.assertAlmostEqual(t, 157, delta=1)
        self.assertFigure("[157,", "챕터 +157 s")
        self.assertFigure("157 초", "실리콘 통과시간 본문")

    def test_finest_eva_needs_4593s_without_a_bubble(self):
        t = travel_s(RHO_EFF["EVA"][0][0], bin_d(0), 15)
        self.assertAlmostEqual(t, 4593, delta=2)
        self.assertFigure("4,593", "기포 없는 31–45 µm EVA 통과시간")

    def test_one_200um_bubble_collapses_that_to_25s(self):
        """등가밀도 7.9 kg/m³ · 25 초 — 공기가 회수율 변수인 이유."""
        rho_eq, d_eq = aggregate(RHO_EFF["EVA"][0][0], bin_d(0))
        self.assertAlmostEqual(rho_eq, 7.9, delta=0.1)
        v = terminal_v(rho_eq, d_eq, 15)
        self.assertLess(v, 0, "기포가 붙었으면 떠야 한다")
        t = abs(TRAVEL_MM / 1000 / v)
        self.assertAlmostEqual(t, 25, delta=2)
        self.assertFigure("7.9", "기포 등가밀도")
        self.assertFigure("[25,", "챕터 +25 s")
        self.assertGreater(4593 / t, 100, "기포 효과가 100 배 아래면 이야기가 달라진다")

    def test_schiller_naumann_is_actually_implemented(self):
        """Re>1 에서 Stokes 를 그대로 쓰면 속도가 과대해진다."""
        packed = self.html.replace(" ", "")
        self.assertIn("24/re*(1+0.15*Math.pow(re,0.687))", packed)
        rho_eq, d_eq = aggregate(RHO_EFF["EVA"][0][0], bin_d(0))
        re = abs(rho_br(15) * terminal_v(rho_eq, d_eq, 15) * d_eq / mu_br(15))
        self.assertGreater(re, 1, "이 조건은 Stokes 영역이 아니다")

    def test_fine_backsheet_is_neutral_at_15pct(self):
        """31–45 µm 백시트는 15 % 염수에서 사실상 중립 — 화면 중앙에 남는 입자다."""
        t = travel_s(RHO_EFF["BS"][0][0], bin_d(0), 15)
        self.assertGreater(t, 86400, "중립이라면 하루로도 못 지난다")
        self.assertIn("∞ 중립", self.html)
        self.assertIn("영원히 뜨지 않는다", self.html)

    def test_density_cut_moves_with_salinity(self):
        """밀도컷이 걸리는 셀은 31–45 µm 백시트(ρ 1110) 다 — 12 % 에선 가라앉고 18 % 에선 뜬다."""
        self.assertLess(rho_br(12), RHO_EFF["BS"][0][0])
        self.assertGreater(rho_br(18), RHO_EFF["BS"][0][0])
        self.assertGreater(stokes(RHO_EFF["BS"][0][0], bin_d(0), 12), 0)   # 침강
        self.assertLess(stokes(RHO_EFF["BS"][0][0], bin_d(0), 18), 0)      # 부상
        for w in (12, 15, 18):
            self.assertIn(f'data-w="{w}"', self.html)


class TestRecoveryStory(unittest.TestCase):
    """밀도차만으로는 KPI 를 못 채운다는 결론이 화면에 그대로 실려 있는가."""

    @classmethod
    def setUpClass(cls):
        cls.html = MOTION.read_text(encoding="utf-8")

    def test_density_only_misses_the_kpi(self):
        eva, bs = weighted("EVA", 15) * 100, weighted("BS", 15) * 100
        self.assertAlmostEqual(eva, 34.5, delta=0.2)
        self.assertAlmostEqual(bs, 13.8, delta=0.2)
        self.assertLess(eva, 80)
        self.assertIn("34.5 %, 백시트 13.8 %", self.html)

    def test_required_bubble_retention(self):
        """KPI 80 % 를 채우려면 정치 종료까지 남아야 할 부착률."""
        need_e = (0.80 - weighted("EVA", 15)) / (1 - weighted("EVA", 15))
        need_b = (0.80 - weighted("BS", 15)) / (1 - weighted("BS", 15))
        self.assertAlmostEqual(need_e * 100, 69, delta=1)
        self.assertAlmostEqual(need_b * 100, 77, delta=1)
        self.assertIn("EVA ≥ 69 %, 백시트 ≥ 77 %", self.html)

    def test_design_preset_clears_that_bar(self):
        """기본 조건(부착 80 %)은 요구 하한보다 위여야 한다 — 아니면 첫 화면이 미달로 열린다."""
        self.assertIn("state={w:15, att:0.80}", self.html)
        self.assertIn('id="att" min="0" max="100" step="10" value="80"', self.html)
        self.assertGreaterEqual(0.80, (0.80 - weighted("BS", 15)) / (1 - weighted("BS", 15)))

    def test_kpi_gate_is_named_as_the_document_names_it(self):
        for kpi in ("Top polymer recovery", "Top Si loss", "Bottom Si recovery"):
            self.assertIn(kpi, self.html)
        self.assertIn("목표 ≥ 80 %", self.html)

    def test_feed_composition_is_the_documented_one(self):
        """Si 87.5 / EVA 6.25 / BS 6.25 wt% — 문서 §6 관찰조성."""
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
