"""단일 셰브론 핫나이프 — 분절 하나가 받는 힘이 근거에서 나오는가.

이 계산이 틀리는 방식은 셋이다:

  ① **총 추력이 형상을 따라 움직인다** — 박리 저항은 폭당 힘이므로 셰브론을
     세워도 진행방향 합계는 F_PEEL 이어야 한다. 합계가 각도에 따라 흔들리면
     분절 힘 배분이 아니라 물리를 잘못 쓴 것이다.
  ② **분절 힘이 각도를 따라 움직인다** — 완전히 물린 분절의 면내 합력은
     f_w × 150 이고 각도와 무관하다. 각도가 바꾸는 것은 성분뿐이다.
  ③ **사이클을 다른 식으로 센다** — 셰브론 깊이는 탠덤 칼끝 간격 자리에
     들어가야 한다. 깊이 300 이면 지금 사이클과 같아야 한다.
"""

import math
import unittest

from . import _path  # noqa: F401

import cycle as CY
import fab_spec as F
import knife_chevron as KC
from console_consts import const as c


class TestTheTotalThrustDoesNotDependOnTheShape(unittest.TestCase):

    def test_feed_components_sum_to_the_console_thrust_at_every_angle(self):
        for th in (0.0, 10.0, 24.35, 45.0, 60.0, 70.0):
            o = KC.option(th)
            self.assertAlmostEqual(o["total_fx"], c("F_PEEL"), places=6, msg=f"θ={th}")

    def test_the_resistance_per_width_is_the_oi01_upper_band(self):
        self.assertAlmostEqual(KC.F_W, 13.37 * 1000 / 1200, places=6)      # 111 N/cm

    def test_the_wings_cancel_laterally_and_each_carries_half(self):
        o = KC.option(30.0)
        self.assertAlmostEqual(o["wing_fx"], c("F_PEEL") / 2, places=9)
        self.assertAlmostEqual(o["wing_fy"], o["wing_fx"] * math.tan(math.radians(30.0)), places=9)


class TestABladeSeesTheSameForceAtAnyAngle(unittest.TestCase):

    def test_a_fully_engaged_blade_carries_f_w_times_its_length(self):
        for th in (0.0, 24.35, 45.0):
            o = KC.option(th)
            self.assertAlmostEqual(o["R_full"], KC.F_W * KC.SEG_L / 1000, places=9)
            self.assertAlmostEqual(o["R_full"], 1.671, places=2)

    def test_the_design_value_carries_the_fabrication_factors(self):
        o = KC.option(24.35)
        self.assertAlmostEqual(o["R_full_design"], o["R_full"] * F.PSI_DYN * F.GAMMA_Q, places=9)
        self.assertAlmostEqual(o["R_full_design"], 3.26, places=2)

    def test_components_close_on_the_resultant(self):
        o = KC.option(45.0)
        self.assertAlmostEqual(math.hypot(o["Fx_full"], o["Fy_full"]), o["R_full"], places=9)

    def test_only_the_blades_inside_the_panel_are_loaded(self):
        bl = KC.blades(KC.exact_fit(6))
        self.assertEqual(len(bl), 6)
        self.assertEqual(sum(1 for b in bl if abs(b["engaged"] - KC.SEG_L) < 1e-6), 5)
        self.assertLess(bl[-1]["engaged"], KC.SEG_L)       # 마지막 분절은 여유 120 을 덮는다
        self.assertAlmostEqual(sum(b["engaged"] for b in bl) * math.cos(math.radians(KC.exact_fit(6))),
                               KC.PANEL_HALF, places=6)


class TestTheGeometryIsQuantisedByTheSegment(unittest.TestCase):

    def test_six_segments_fit_the_half_width_exactly(self):
        th = KC.exact_fit(6)
        self.assertAlmostEqual(6 * KC.SEG_L * math.cos(math.radians(th)), KC.KNIFE_HALF, places=9)
        self.assertAlmostEqual(KC.option(th)["overhang"], 0.0, places=6)

    def test_five_segments_cannot_cover_the_knife_width(self):
        with self.assertRaises(ValueError):
            KC.exact_fit(5)

    def test_a_straight_knife_is_the_zero_angle_case(self):
        o = KC.straight()
        self.assertEqual(o["blades"], 12)
        self.assertAlmostEqual(o["depth_panel"], 0.0)
        self.assertAlmostEqual(o["Fy_full"], 0.0)


class TestTheCycleUsesTheChevronDepthWhereTheTandemPitchStood(unittest.TestCase):

    def test_depth_300_reproduces_the_present_cycle(self):
        m0, m1 = CY.model(), CY.model(knife_pitch=CY.MODEL["knifePitch"])
        self.assertEqual(m0, m1)
        th = math.degrees(math.atan(CY.MODEL["knifePitch"] / KC.PANEL_HALF))
        self.assertAlmostEqual(KC.option(th)["cycle"], m0["knifeLineCycle"], places=6)

    def test_a_steeper_chevron_costs_throughput(self):
        self.assertLess(KC.option(45.0)["net"], KC.option(24.35)["net"])
        self.assertFalse(KC.contract_ok(KC.option(45.0)))

    def test_the_six_segment_chevron_still_meets_the_contract(self):
        self.assertTrue(KC.contract_ok(KC.option(KC.exact_fit(6))))
        self.assertAlmostEqual(KC.summary()["max_theta_contract"], KC.exact_fit(6), places=2)


class TestTheReportSaysWhatTheOwnerAsked(unittest.TestCase):

    def test_it_names_the_per_blade_force_and_its_independence_from_angle(self):
        r = KC.report()
        self.assertIn("1.67 kN 특성", r)
        self.assertIn("3.26 kN 설계", r)
        self.assertIn("각도와 무관", r)
        self.assertIn("✗ 계약 미달", r)


if __name__ == "__main__":
    unittest.main()
