# -*- coding: utf-8 -*-
"""조 개폐 실린더 자리 — 「계산이 답을 하나로 좁히지 않는다」를 되짚는다.

미결 항목의 그 문장이 맞는지 본다. 결론은 반대다 — 너무 좁혀져서 되는 구간이
5 mm 밖에 안 남는다. 그런 뒤집기는 근거가 있어야 하므로 셋으로 나눈다:

  · **값이 부품표·모델에서 오는가** — 행정·보어·포스트 길이.
  · **두 상한이 물리에서 오는가** — 간섭 하한과 부싱 상한.
  · **손잡이를 돌리면 답이 따라 움직이는가** — 부싱 간격·등급.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import drives, dynamics, fabrication, jaw, kinematics


class TestTheValuesAreRead(unittest.TestCase):
    def test_the_stroke_comes_from_the_spec_not_the_name(self):
        item = dynamics._commercial(jaw.SHEET, "BFC-JCY-01")
        self.assertIn("190", item.spec)
        self.assertNotIn("190", item.name)
        self.assertEqual(jaw.cylinder_stroke_mm(), 190.0)

    def test_the_stroke_covers_the_jaw_travel(self):
        self.assertTrue(jaw.stroke_covers_the_jaw())
        self.assertEqual(kinematics.jaw_stroke_mm(),
                         kinematics.JAW_OPEN_Z_MM - kinematics.JAW_CLOSED_Z_MM)

    def test_the_force_comes_from_the_bore_and_the_pressure(self):
        area = math.pi * (kinematics.JAW_CYLINDER_BORE_MM / 2.0) ** 2
        self.assertAlmostEqual(jaw.cylinder_force_n(),
                               kinematics.JAW_AIR_MPA * area, places=6)

    def test_the_count_comes_from_the_bom(self):
        self.assertEqual(jaw.cylinders_per_jaw(),
                         dynamics._commercial(jaw.SHEET, "BFC-JCY-01").qty // 2)

    def test_the_post_length_comes_from_the_bom(self):
        self.assertEqual(jaw.post_length_mm(),
                         float(dynamics._part(jaw.SHEET, "BFC-JGP-01").size[2]))

    def test_changing_the_bore_changes_the_answer(self):
        keep = kinematics.JAW_CYLINDER_BORE_MM
        before = jaw.max_offset_mm()
        try:
            kinematics.JAW_CYLINDER_BORE_MM = 40.0
            self.assertGreater(jaw.max_offset_mm(), before,
                               "보어를 줄이면 편심 여유가 늘어야 한다")
        finally:
            kinematics.JAW_CYLINDER_BORE_MM = keep


class TestForceIsNotWhatDecides(unittest.TestCase):
    def test_the_required_grip_is_the_panel_held_by_friction(self):
        """세로로 선 순간 무게를 마찰이 받는다 — 그 식 그대로여야 한다."""
        a_tan = (dynamics.flip_slip()["demandNm"] / drives.flip_inertia_kgm2()
                 * kinematics.JAW_CLOSED_Z_MM / 1_000.0)
        want = (drives.PANEL_KG * math.hypot(dynamics.G, a_tan)
                * jaw.GRIP_SAFETY / jaw.PAD_MU)
        self.assertAlmostEqual(jaw.required_clamp_n(), want, places=6)

    def test_there_is_ample_margin(self):
        self.assertGreater(jaw.clamp_margin(), 2.0)
        self.assertTrue(jaw.force_is_not_what_decides())

    def test_a_weaker_pad_would_change_that(self):
        """마찰이 반이면 요구가 두 배 — 결론이 값에 매여 있는지."""
        keep = jaw.PAD_MU
        try:
            jaw.PAD_MU = keep / 2
            self.assertAlmostEqual(jaw.clamp_margin(),
                                   jaw.clamp_force_n()
                                   / jaw.required_clamp_n(), places=6)
            self.assertLess(jaw.clamp_margin(), 2.0)
        finally:
            jaw.PAD_MU = keep


class TestTheTwoLimits(unittest.TestCase):
    def test_the_cylinder_does_not_fit_radially(self):
        """편심이 생기는 이유 — 반경 방향에 자리가 없다."""
        self.assertFalse(jaw.fits_radially())
        self.assertEqual(jaw.radial_room_mm(),
                         kinematics.ring_outer_r_mm() - kinematics.JAW_OPEN_Z_MM)
        self.assertGreater(jaw.cylinder_length_mm(), jaw.radial_room_mm() * 2)

    def test_the_minimum_offset_is_the_pythagorean_leftover(self):
        want = math.sqrt(jaw.cylinder_length_mm() ** 2
                         - jaw.radial_room_mm() ** 2)
        self.assertAlmostEqual(jaw.min_offset_mm(), want, places=6)

    def test_the_bushing_reaction_is_a_couple(self):
        """N = F·e / s / 포스트 수 — 간격을 두 배로 하면 반력이 반이어야 한다."""
        e = 100.0
        self.assertAlmostEqual(
            jaw.bushing_reaction_n(e),
            jaw.clamp_force_n() * e / jaw.BUSHING_SPAN_MM / 2, places=6)
        keep = jaw.BUSHING_SPAN_MM
        try:
            jaw.BUSHING_SPAN_MM = keep * 2
            self.assertAlmostEqual(jaw.bushing_reaction_n(e) * 2,
                                   jaw.clamp_force_n() * e / keep / 2, places=6)
        finally:
            jaw.BUSHING_SPAN_MM = keep

    def test_ball_bushings_do_not_jam(self):
        """미끄럼 부싱이면 힘에서 걸렸겠지만 볼이면 수명이 자른다."""
        self.assertTrue(jaw.jamming_is_not_the_limit())
        self.assertGreater(jaw.jam_offset_mm(), jaw.max_offset_mm() * 10)
        self.assertGreater(jaw.efficiency(jaw.max_offset_mm()), 0.98)

    def test_the_window_is_closed_as_drawn(self):
        """이 항목의 답 — 지금 간격으로는 자리가 없다."""
        self.assertGreater(jaw.min_offset_mm(), jaw.max_offset_mm())
        self.assertFalse(jaw.summary()["windowOpenAsDrawn"])


class TestTheHandle(unittest.TestCase):
    def test_spreading_the_bushings_opens_it(self):
        self.assertTrue(jaw.spreading_the_bushings_opens_it())
        self.assertLessEqual(jaw.required_span_mm(), jaw.max_span_mm())

    def test_the_post_limits_how_far_they_spread(self):
        self.assertAlmostEqual(jaw.max_span_mm(),
                               jaw.post_length_mm() - jaw.BUSHING_LENGTH_MM)

    def test_the_window_that_opens_is_only_millimetres_wide(self):
        s = jaw.summary()
        self.assertTrue(s["windowOpen"])
        self.assertLess(s["windowWidthMm"], 20.0)
        self.assertGreater(s["windowWidthMm"], 0.0)

    def test_a_better_bushing_would_widen_it(self):
        keep = jaw.BUSHING_DYN_N
        before = jaw.summary()["windowWidthMm"]
        try:
            jaw.BUSHING_DYN_N = keep * 1.5
            self.assertGreater(jaw.window_mm()[1] - jaw.window_mm()[0], before)
        finally:
            jaw.BUSHING_DYN_N = keep

    def test_every_check_passes_today(self):
        for name, ok, why in jaw.checks():
            with self.subTest(check=name):
                self.assertTrue(ok, f"{name} — {why}")

    def test_the_annotations_name_what_to_change(self):
        text = " ".join(jaw.annotations())
        for token in ("포스트", "부싱 등급", "토글", "OI-03"):
            self.assertIn(token, text, f"주석에 {token} 이 없다")


class TestItIsRegistered(unittest.TestCase):
    def test_the_open_item_carries_the_answer(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-03")
        text = item.title + item.why_open + item.closes_with + item.blocks
        for token in ("jaw.py", "부싱", "편심"):
            self.assertIn(token, text, f"OI-03 에 {token} 이 없다")

    def test_the_open_item_numbers_are_the_ones_the_module_computes(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-03")
        s = jaw.summary()
        for value in (f"{s['minOffsetMm']:.0f}", f"{s['maxOffsetMm']:.0f}",
                      f"{s['requiredSpanMm']:.0f}", f"{s['margin']}"):
            self.assertIn(value, item.why_open, f"OI-03 이 {value} 를 안 들고 있다")

    def test_the_open_item_carries_no_markdown(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-03")
        for field in (item.title, item.why_open, item.closes_with, item.blocks):
            self.assertNotIn("**", field)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
