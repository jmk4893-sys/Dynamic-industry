# -*- coding: utf-8 -*-
"""회전을 풀어 준 세 장면 — 결론이 도면집 값에서 나오는지 지킨다.

이 모듈의 결론은 「포획빔 네 본 중 둘만 받는다」다. 도면을 바꾸자는 말이라
근거가 헐거우면 안 되므로 다섯으로 나눈다:

  · **접촉 지도가 리터럴이 아니라 유도인가** — 행 값을 바꾸면 답이 따라오는가.
  · **모르는 값이 결론을 정하고 있지 않은가** — 프레임 하부 지지폭을 쓸어 본다.
  · **본수 효과와 하이브리드 효과가 섞여 있지 않은가** — 2×2 로 갈라 본다.
  · **정규화가 제 동역학을 내고 있지 않은가** — 요구 토크가 정적 모형과 같은가.
  · **문장과 값이 같은가** — 미결 항목에 실을 문장이 `summary()` 와 맞는가.
"""

from __future__ import annotations

import unittest

from tests import _path  # noqa: F401

from pv_preprocess import catch, dynamics, fabrication, kinematics, motion, rigid


class TestTheContactMap(unittest.TestCase):
    def test_only_the_outer_pair_reaches_the_frame(self):
        """행 ∓580 은 프레임 안쪽이라 못 받는다 — 이 결론이 이 모듈의 전부다."""
        self.assertEqual(motion.bearing_beams(), 2)
        self.assertEqual(sorted(abs(r) for r in motion.bearing_rows_mm()),
                         [720.0, 720.0])

    def test_the_outer_pair_only_catches_the_panel_edge(self):
        """각관은 690…750 을 덮지만 패널은 700 에서 끝난다 — 물림 10 mm."""
        self.assertAlmostEqual(motion.bearing_overlap_mm(720.0), 10.0)
        self.assertAlmostEqual(motion.landing_ledge_mm(), 10.0)

    def test_the_inner_pair_has_air_under_it(self):
        """안쪽 빔 위는 프레임이 아니라 허공이다 — 유리는 그보다 위에 있다."""
        inner = [c for c in motion.contact_map() if abs(c["rowMm"]) == 580.0]
        self.assertEqual(len(inner), 2)
        for c in inner:
            self.assertFalse(c["bears"])
            self.assertTrue(c["underGlass"])
        self.assertGreater(motion.glass_gap_mm(), 0.0)

    def test_the_map_follows_the_drawing_not_a_literal(self):
        """행 값을 바꾸면 지도가 따라오는가 — 손으로 적은 답이 아님을 지킨다."""
        keep = kinematics.CATCH_BEAM_ROWS_MM
        try:
            kinematics.CATCH_BEAM_ROWS_MM = (-690, -640, 640, 690)
            self.assertEqual(motion.bearing_beams(), 2)
            self.assertGreater(motion.landing_ledge_mm(), 10.0,
                               "행을 안쪽으로 옮겼는데 선반이 안 넓어졌다")
        finally:
            kinematics.CATCH_BEAM_ROWS_MM = keep
        self.assertAlmostEqual(motion.landing_ledge_mm(), 10.0)

    def test_the_existing_check_passes_while_the_beams_miss(self):
        """도면집 시험은 「프레임 중심을 낀다」만 본다 — 그것으로는 안 잡힌다.

        `test_pv_drives.test_the_catch_beam_rows_straddle_the_long_frames`
        가 초록인 채로 두 본이 논다. **중심선을 끼는 것과 밑을 받는 것은
        다른 이야기다.** 그 시험을 고치자는 게 아니라, 그것이 이 물음을
        보지 않는다는 사실을 여기서 값으로 남긴다.
        """
        centre = kinematics.CARRIAGE_RAIL_Z_MM
        for sign in (-1, 1):
            pair = sorted((z for z in kinematics.CATCH_BEAM_ROWS_MM
                           if z * sign > 0), key=abs)
            self.assertLess(abs(pair[0]), centre)      # 옛 시험이 보는 것
            self.assertGreater(abs(pair[1]), centre)
        self.assertLess(motion.bearing_beams(),        # 그런데 실제로는
                        len(kinematics.CATCH_BEAM_ROWS_MM))


class TestWhatWeDoNotKnowDoesNotDecide(unittest.TestCase):
    def test_the_bottom_flange_width_does_not_change_the_verdict(self):
        self.assertTrue(motion.bearing_conclusion_is_robust())

    def test_it_is_recorded_as_an_assumption(self):
        """하부 지지폭이 가정임을 모듈이 밝히는가 — 조용히 쓰면 안 되는 값이다."""
        import inspect
        src = inspect.getsource(motion)
        self.assertIn("여기서 처음 적는 값이고, 가정이다", src)

    def test_even_a_wide_flange_leaves_the_inner_pair_idle(self):
        for width in (25.0, 50.0, 88.0):
            with self.subTest(width):
                self.assertEqual(motion.bearing_overlap_mm(580.0, width), 0.0)

    def test_a_frame_wide_enough_would_reach_it(self):
        """결론이 「무조건」이 아님을 보인다 — 91 mm 면 닿는다 (그런 모듈은 없다)."""
        self.assertGreater(motion.bearing_overlap_mm(580.0, 91.0), 0.0)


class TestTheTwoEffectsAreSeparated(unittest.TestCase):
    GRID = None

    @classmethod
    def setUpClass(cls):
        cls.GRID = motion.matrix()

    def test_four_massless_is_the_old_answer(self):
        """2×2 의 한 칸이 `dynamics.catch_impact` 여야 표가 이어진다."""
        ref = dynamics.catch_impact()
        got = self.GRID["4본 무질량"]["peakBeamN"]
        self.assertAlmostEqual(got / ref["perBeamN"], 1.0, places=2)

    def test_halving_the_beams_raises_the_force(self):
        raise_ = (self.GRID["2본 무질량"]["peakBeamN"]
                  / self.GRID["4본 무질량"]["peakBeamN"])
        self.assertAlmostEqual(raise_, 1.44, places=1)

    def test_the_beam_inertia_lowers_it(self):
        """하이브리드가 첨두를 깎는다 — 빔이 운동량을 나눠 갖기 때문이다."""
        cut = (self.GRID["4본 모달"]["peakBeamN"]
               / self.GRID["4본 무질량"]["peakBeamN"])
        self.assertLess(cut, 1.0)
        self.assertAlmostEqual(cut, 0.80, places=1)

    def test_the_count_wins(self):
        """두 항이 반대로 가지만 상쇄되지 않는다 — 실제가 가정보다 크다."""
        self.assertGreater(self.GRID["2본 모달"]["peakBeamN"],
                           self.GRID["4본 무질량"]["peakBeamN"])

    def test_the_beam_keeps_moving_after_the_panel_leaves(self):
        """모달 지지에서는 빔 처짐과 패널 하강이 다른 값이다."""
        d = self.GRID["2본 모달"]
        self.assertGreater(d["beamDeflectionMm"], d["deflectionMm"])

    def test_the_hybrid_also_cuts_the_rebound(self):
        self.assertLess(self.GRID["2본 모달"]["reboundMs"],
                        self.GRID["2본 무질량"]["reboundMs"])


class TestTheArrivalAttitude(unittest.TestCase):
    def test_tilt_is_not_what_binds(self):
        self.assertTrue(motion.tilt_is_not_what_binds())

    def test_the_sweep_starts_from_just_touching(self):
        """기울여도 파고든 채로 시작하지 않는가 — 그러면 첨두가 지어진다."""
        flat = motion.drop(tilt_deg=0.0)["peakBeamN"]
        tilted = motion.drop(tilt_deg=2.0)["peakBeamN"]
        self.assertLess(tilted / flat, 1.5, "기울기가 힘을 지어내고 있다")

    def test_low_damping_is_conservative_for_force_but_not_for_holding(self):
        """한 값이 두 물음에서 반대로 작동한다 — 그것을 값으로 남긴다."""
        cuts = motion.damping_cuts_both_ways()
        self.assertGreater(cuts["zeta0.05"], cuts["zeta0.3"])   # 힘은 커지고
        self.assertGreater(cuts["rebound0.05"], cuts["rebound0.3"])  # 되튐도


class TestHoldingIsThePoint(unittest.TestCase):
    def test_the_ledge_is_the_binding_thing(self):
        self.assertTrue(motion.the_ledge_is_the_problem())
        self.assertLess(motion.landing_ledge_mm(),
                        motion.beam_width_mm() / 2.0)

    def test_it_bounces_and_the_bounce_is_bigger_than_the_ledge(self):
        self.assertGreater(motion.bounce_mm(), motion.landing_ledge_mm())

    def test_the_drift_budget_is_small(self):
        """떠 있는 동안 견디는 가로 속도가 100 mm/s 도 안 된다."""
        self.assertLess(motion.drift_allow_ms(), 0.1)


class TestTheFlipDrive(unittest.TestCase):
    def test_the_demand_reproduces_the_static_model(self):
        """정규화가 제 동역학을 내면 여기가 먼저 벌어진다."""
        self.assertTrue(motion.demand_matches_the_static_model())

    def test_it_does_not_lose_phase_at_the_rated_takt(self):
        self.assertTrue(motion.flip_holds())

    def test_slip_onset_agrees_with_the_static_margin(self):
        """미끄러짐은 토크가 마진배 커질 때 시작한다 — 토크는 배수의 제곱이다."""
        want = dynamics.flip_slip()["margin"] ** 0.5
        self.assertAlmostEqual(motion.slip_onset_scale() / want, 1.0, places=1)

    def test_past_the_limit_it_loses_degrees(self):
        """정적 모형이 못 내던 값 — 미끄러진 **뒤**."""
        lost = motion.flip_stick_slip(2.0)["lostDeg"]
        self.assertGreater(lost, 10.0)

    def test_the_microslip_width_does_not_set_the_answer(self):
        self.assertTrue(motion.slip_is_not_a_numerical_artifact())

    def test_the_axis_may_miss_the_centre_of_gravity_by_a_lot(self):
        """`dynamics` 의 「중력은 상쇄된다」가 얼마나 여유 있는 가정인가."""
        self.assertGreater(motion.eccentricity_allow_mm(), 100.0)


class TestTheNullResult(unittest.TestCase):
    def test_tipping_is_not_the_eoat_limit(self):
        self.assertTrue(motion.tipping_is_not_the_limit())

    def test_it_is_not_close_even_with_a_short_cup_array(self):
        """컵이 훨씬 좁게 모여 있어도 전도가 먼저 오지 않는다."""
        self.assertGreater(motion.eoat_tip_ms2(arm_mm=200.0),
                           dynamics.eoat_limit_ms2()["limitMs2"])


class TestTheWordsMatchTheNumbers(unittest.TestCase):
    def test_the_annotations_carry_the_computed_values(self):
        s = motion.summary()
        text = " ".join(motion.annotations())
        self.assertIn(f"{s['bearingBeams']} 본", text)
        self.assertIn(f"{s['ledgeMm']:.0f} mm", text)
        self.assertIn(f"{s['builtPerBeamN']:.0f} N", text)
        self.assertIn(f"{s['lostDegAt2x']:.1f}°", text)

    def test_the_fab_book_cannot_render_asterisks(self):
        """도면집은 별표를 그대로 찍는다 — 문장에 마크다운을 넣지 않는다."""
        for line in motion.annotations():
            self.assertNotIn("**", line)

    def test_the_open_item_carries_what_the_module_computes(self):
        """미결 항목 OI-05 의 문장과 `summary()` 가 같은 값을 말하는가.

        문장에만 있으면 행 위치가 바뀌어도 안 따라온다 — 이 저장소가 가장
        경계하는 상태다.
        """
        s = motion.summary()
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-05")
        text = item.why_open + " " + item.closes_with
        # 「둘」은 낱말이라 값과 직접 못 견준다 — 낱말과 값을 여기서 묶는다.
        self.assertEqual(s["bearingBeams"], 2)
        self.assertEqual(len(kinematics.CATCH_BEAM_ROWS_MM), 4)
        self.assertIn("네 본 중 둘", text)
        for want in (f"{s['ledgeMm']:.0f} mm",
                     f"{s['builtPerBeamN']:,.0f} N",
                     f"{s['builtBeamDeflectionMm']:.1f} mm",
                     f"{s['loadFactor']:.2f} 배",
                     f"{s['countFactor']:.2f} 배",
                     f"{motion.best_row_mm():.0f}",
                     f"{motion.best_ledge_mm():.0f} mm",
                     f"{motion.glass_gap_mm():.0f} mm"):
            with self.subTest(want):
                self.assertIn(want, text)

    def test_the_open_item_title_says_the_beams_miss(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-05")
        self.assertIn("둘만 받는다", item.title)

    def test_four_beams_could_never_all_bear(self):
        """행을 옮기는 것으로 해결되지 않는다는 것을 못 박는다."""
        self.assertTrue(motion.four_beams_cannot_all_bear())
        self.assertAlmostEqual(motion.best_ledge_mm(), 25.0)
        self.assertGreater(motion.best_ledge_mm(), motion.landing_ledge_mm())

    def test_the_checks_name_what_is_wrong(self):
        failing = [c for c in motion.checks() if not c[1]]
        self.assertEqual(len(failing), 3, "검사 결과가 바뀌었으면 사유를 적는다")
        for _name, _ok, why in failing:
            self.assertTrue(why.strip(), "실패한 검사가 사유를 안 낸다")


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
