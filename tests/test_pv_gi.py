"""GI-302 · GI-303 유리 검사 — 사슬이 서로 맞는지.

라인스캔 검사대는 셋이 한 사슬로 묶여 있다 — 이송 속도가 라인레이트를 정하고,
라인레이트가 노광을 정하고, 노광이 조명을 정한다. 넷째가 형상이다: 폭을 보려면
광학계가 자리를 먹는데, 그 자리를 배치가 이미 배정해 두었다.

여기서 보는 것은 셋이다.

1. **정의식** — 라인레이트·배율·작동거리·심도가 광학의 식 그대로인가.
2. **다른 모듈과의 일치** — 해상도·패널·이송·존치 헤드를 이 모듈이 **다시
   정하지 않는지**, 그리고 자료량이 `ai` 의 '장당 350 MB', 롤러 창이 `vision`
   의 '150 mm' 와 맞는지. 두 곳이 어긋나면 둘 중 하나가 틀린 것이다.
3. **못 닫는 것** — 계산에서 나오는가. 조건이 풀리면 항목이 사라져야 한다.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import ai, campaign, gi_optics, handoff, sg_grind, smart, vision


class TestTheChainFromSpeedToLight(unittest.TestCase):
    """이송 → 라인레이트 → 노광."""

    def test_line_rate_keeps_pixels_square(self):
        """화소가 정사각이려면 라인레이트가 이송÷해상도다."""
        self.assertAlmostEqual(gi_optics.line_rate_hz(),
                               gi_optics.TRANSPORT_MM_S / gi_optics.RESOLUTION_MM,
                               places=1)

    def test_exposure_is_a_duty_of_the_line_period(self):
        self.assertAlmostEqual(gi_optics.line_period_us(),
                               1e6 / gi_optics.line_rate_hz(), places=2)
        self.assertAlmostEqual(gi_optics.exposure_us(),
                               gi_optics.line_period_us() * gi_optics.EXPOSURE_DUTY,
                               places=2)

    def test_the_exposure_is_far_shorter_than_an_area_camera(self):
        """조명이 먼저 막히는 이유 — 배수를 값으로 남긴다."""
        self.assertGreater(gi_optics.exposure_vs_area_camera(), 10)
        self.assertAlmostEqual(
            gi_optics.exposure_vs_area_camera(),
            round((1 / 60) / (gi_optics.exposure_us() / 1e6)))


class TestTheOpticsFitOrDoNot(unittest.TestCase):
    """형상 — 폭을 보려면 자리가 든다. 이 모듈이 찾은 것이 여기 있다."""

    def test_working_distance_is_the_thin_lens_form(self):
        for n in (1, 2, 3, 4):
            with self.subTest(n):
                m = gi_optics.magnification(n)
                self.assertAlmostEqual(gi_optics.working_distance_mm(n),
                                       gi_optics.LENS_F_MM * (1 + 1 / m), places=1)

    def test_magnification_is_image_over_object(self):
        n = 3
        self.assertAlmostEqual(
            gi_optics.magnification(n),
            gi_optics.sensor_width_mm() / (gi_optics.PANEL_W_MM / n), places=5)

    def test_more_cameras_need_less_height(self):
        """대수를 늘리면 대당 시야가 좁아져 광학계가 얕아진다 — 단조여야 한다."""
        heights = [gi_optics.stack_height_mm(n) for n in (1, 2, 3, 4, 5)]
        self.assertEqual(heights, sorted(heights, reverse=True))

    def test_one_camera_does_not_fit_below_the_deck(self):
        """이 모듈의 결론 — GI-303 은 한 대로 안 된다."""
        self.assertFalse(gi_optics.single_camera_is_possible())
        self.assertGreater(gi_optics.single_camera_shortfall_mm(), 0.0)
        self.assertAlmostEqual(
            gi_optics.single_camera_shortfall_mm(),
            gi_optics.one_camera_would_need_mm() - gi_optics.BELOW_DECK_MM, places=1)

    def test_the_chosen_count_is_the_smallest_that_fits(self):
        n = gi_optics.cameras_below()
        self.assertTrue(gi_optics.fits_below_deck(n))
        self.assertFalse(gi_optics.fits_below_deck(n - 1))
        self.assertTrue(gi_optics.sensor_covers_the_width(n))

    def test_a_single_sensor_has_the_pixels_but_not_the_room(self):
        """화소가 모자라서가 아니라 **자리**가 모자라서 여러 대다 — 구분이 근거다."""
        self.assertTrue(gi_optics.sensor_covers_the_width(1))
        self.assertFalse(gi_optics.fits_below_deck(1))

    def test_the_gantry_above_has_room_for_fewer(self):
        """위는 공간이 넉넉해 밑보다 적은 대수로 된다."""
        self.assertLessEqual(gi_optics.cameras_above(), gi_optics.cameras_below())

    def test_depth_of_field_is_the_standard_form(self):
        n = gi_optics.cameras_below()
        m = gi_optics.magnification(n)
        want = 2 * gi_optics.F_NUMBER * gi_optics.CIRCLE_OF_CONFUSION_MM * (1 + m) / m ** 2
        self.assertAlmostEqual(gi_optics.depth_of_field_mm(n), want, places=2)

    def test_the_depth_covers_the_bow(self):
        self.assertTrue(gi_optics.depth_covers_the_bow(gi_optics.cameras_below()))
        self.assertGreater(gi_optics.depth_of_field_mm(gi_optics.cameras_below()),
                           gi_optics.PANEL_BOW_MM)

    def test_seams_need_overlap(self):
        n = gi_optics.cameras_below()
        self.assertGreater(gi_optics.seam_overlap_mm(n), 0.0)
        self.assertEqual(gi_optics.seam_overlap_mm(1), 0.0)


class TestItAgreesWithWhatIsAlreadyWritten(unittest.TestCase):
    """다른 모듈이 정해 둔 값을 다시 정하지 않는지 — 그리고 서로 맞는지."""

    def test_the_resolution_and_panel_come_from_smart(self):
        self.assertEqual(gi_optics.RESOLUTION_MM, float(smart.LINESCAN_RESOLUTION_MM))
        self.assertEqual(gi_optics.PANEL_W_MM, float(smart.PANEL_MAX_MM[1]))
        self.assertEqual(gi_optics.PANEL_L_MM, float(smart.PANEL_MAX_MM[0]))

    def test_the_transport_speed_comes_from_the_campaign(self):
        self.assertEqual(gi_optics.TRANSPORT_MM_S, float(campaign.SG_PASS_MM_S))

    def test_the_data_size_matches_the_ai_note(self):
        """`ai` 가 '장당 350 MB' 라고 적어 두었다 — 광학에서 다시 세어도 같아야 한다."""
        self.assertTrue(gi_optics.agrees_with_the_ai_note())
        self.assertAlmostEqual(gi_optics.mb_per_panel(), 350.0, places=1)
        said = " ".join(str(x) for row in ai.PROJECTS for x in (row.tag, row.data)
                        ) if hasattr(ai, "PROJECTS") else ""
        if said:
            self.assertIn("350 MB", said)

    def test_the_stream_size_matches_smart(self):
        """`smart` 의 스트림 화소 수와 같은 것을 세고 있는가."""
        want = (round(smart.PANEL_MAX_MM[0] / smart.LINESCAN_RESOLUTION_MM)
                * round(smart.PANEL_MAX_MM[1] / smart.LINESCAN_RESOLUTION_MM))
        self.assertEqual(gi_optics.pixels_per_panel(), want)

    def test_the_roller_window_matches_the_vision_note(self):
        """`vision` 이 GI-303 주기에 '150 mm 틈' 이라고 적었다."""
        self.assertTrue(gi_optics.window_matches_vision_note())
        self.assertAlmostEqual(gi_optics.roller_window_mm(), 150.0, places=6)
        gi303 = next(h for h in vision.HEADS if h.tag == "GI-303")
        self.assertIn("150 mm", gi303.note)

    def test_the_scan_line_fits_that_window(self):
        self.assertTrue(gi_optics.scan_line_fits_the_window())

    def test_the_kept_heads_are_the_vision_heads(self):
        self.assertEqual(set(gi_optics.kept_heads()), {"GI-302", "GI-303"})
        self.assertTrue(gi_optics.there_is_no_pre_grind_check())

    def test_the_throughput_comes_from_handoff(self):
        self.assertEqual(gi_optics.glass_per_h(), handoff.sheet_glass_per_h())


class TestWhatItCanActuallySee(unittest.TestCase):
    """해상도가 무엇을 보증하는가 — 보증 못 하는 것도 같이 적는다."""

    def test_a_feature_needs_several_pixels(self):
        self.assertAlmostEqual(
            gi_optics.smallest_reliable_feature_mm(),
            gi_optics.PIXELS_PER_FEATURE * gi_optics.RESOLUTION_MM, places=3)

    def test_the_sealant_band_is_far_above_the_limit(self):
        """SG 가 남기는 띠는 200 화소다 — 이건 못 볼 수가 없다."""
        self.assertTrue(gi_optics.sealant_band_is_visible())
        self.assertEqual(gi_optics.sealant_band_in_pixels(),
                         round(sg_grind.SEALANT_BAND_MM / gi_optics.RESOLUTION_MM))
        self.assertGreater(gi_optics.sealant_band_in_pixels(), 100)

    def test_the_arris_is_measurable_but_only_just(self):
        """아리스는 5 화소다 — 잴 수는 있지만 여유가 크지 않다."""
        self.assertTrue(gi_optics.arris_is_measurable())
        self.assertAlmostEqual(gi_optics.arris_in_pixels(),
                               sg_grind.ARRIS_MM / gi_optics.RESOLUTION_MM, places=2)


class TestTimeAndData(unittest.TestCase):

    def test_scan_time_is_length_over_speed(self):
        self.assertAlmostEqual(gi_optics.scan_time_s(),
                               gi_optics.PANEL_L_MM / gi_optics.TRANSPORT_MM_S, places=3)

    def test_it_fits_the_takt_with_room(self):
        self.assertTrue(gi_optics.fits_the_takt())
        self.assertLess(gi_optics.duty(), 1.0)

    def test_the_pixel_rate_is_width_times_line_rate(self):
        self.assertAlmostEqual(
            gi_optics.pixel_rate_mpx_s(),
            gi_optics.pixels_needed() * gi_optics.line_rate_hz() / 1e6, places=1)


class TestOpenQuestions(unittest.TestCase):
    """못 닫는 것이 계산에서 나오는가."""

    def test_the_camera_count_question_is_open_because_one_does_not_fit(self):
        titles = [t for t, _ in gi_optics.open_questions()]
        self.assertIn("GI-303 은 한 대로 안 된다", titles)

    def test_the_missing_pre_grind_check_is_named(self):
        titles = [t for t, _ in gi_optics.open_questions()]
        self.assertIn("연마 전 검사가 없다", titles)

    def test_the_light_is_named_as_not_yet_a_value(self):
        titles = [t for t, _ in gi_optics.open_questions()]
        self.assertIn("조명 밝기가 아직 값이 아니다", titles)

    def test_closed_conditions_do_not_appear(self):
        """심도가 휨을 덮으므로 그 항목은 없어야 한다."""
        titles = [t for t, _ in gi_optics.open_questions()]
        self.assertNotIn("심도가 판 휨을 못 덮는다", titles)
        self.assertNotIn("아리스 폭은 이 해상도로 못 잰다", titles)

    def test_every_question_says_what_would_close_it(self):
        for title, body in gi_optics.open_questions():
            with self.subTest(title):
                self.assertGreater(len(body), 60)


if __name__ == "__main__":
    unittest.main()
