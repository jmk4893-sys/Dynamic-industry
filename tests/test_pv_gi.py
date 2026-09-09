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

import importlib.util
import json
import math
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import ai, campaign, gi_optics, gi_plate, handoff, sg_grind, smart, vision

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLOSEUP = ROOT / "docs/drawings/pv-gi-closeup.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


class TestTheSeatsAcrossTheWidth(unittest.TestCase):
    """자리표 — 나눈 시야가 폭을 빈틈없이 덮는가."""

    def test_the_seats_cover_the_width_with_no_gap(self):
        self.assertTrue(gi_optics.seam_map_covers_the_width())
        m = gi_optics.seam_map()
        self.assertEqual(len(m), gi_optics.cameras_below())
        self.assertAlmostEqual(m[0]["from"], -gi_optics.PANEL_W_MM / 2.0, places=6)
        self.assertAlmostEqual(m[-1]["to"], gi_optics.PANEL_W_MM / 2.0, places=6)

    def test_neighbours_overlap_by_exactly_the_seam(self):
        """이음매마다 정확히 그만큼 겹친다 — 비면 거기 균열을 못 본다."""
        m = gi_optics.seam_map()
        each = gi_optics.seam_overlap_each_mm(len(m))
        for i in range(len(m) - 1):
            with self.subTest(seam=i):
                self.assertAlmostEqual(m[i]["to"] - m[i + 1]["from"], each, places=3)

    def test_the_seams_add_up_to_the_declared_total(self):
        n = gi_optics.cameras_below()
        self.assertAlmostEqual(gi_optics.seam_overlap_each_mm(n) * (n - 1),
                               gi_optics.seam_overlap_mm(n), places=3)

    def test_one_camera_has_no_seam(self):
        self.assertEqual(gi_optics.seam_overlap_each_mm(1), 0.0)
        self.assertEqual(len(gi_optics.seam_map(1)), 1)

    def test_the_rounded_tile_never_runs_past_the_panel(self):
        """반올림한 몫을 n 번 더하면 폭을 넘는다 — 경계는 반올림 전에 잡는다."""
        for n in (2, 3, 4, 6, 7):
            with self.subTest(cameras=n):
                m = gi_optics.seam_map(n)
                self.assertLessEqual(m[-1]["to"], gi_optics.PANEL_W_MM / 2.0 + 1e-9)
                self.assertGreaterEqual(m[0]["from"],
                                        -gi_optics.PANEL_W_MM / 2.0 - 1e-9)


class TestTheDrawnGeometryIsTheModel(unittest.TestCase):
    """형상이 광학에서 나오는가 — 화면에 손으로 놓은 자리가 없어야 한다."""

    def test_three_units_stand(self):
        keys = [u.key for u in gi_optics.units()]
        self.assertEqual(keys, ["below", "above", "window"])
        for u in gi_optics.units():
            with self.subTest(u.key):
                self.assertGreater(len(u.parts), 3)
                self.assertGreater(len(u.principle), 2)
                self.assertIn(u.key, gi_optics.VIEW_DIR)

    def test_the_camera_count_in_the_drawing_is_the_computed_one(self):
        """밑에 그린 카메라 수가 계산이 낸 대수와 같아야 한다."""
        below = gi_optics.below_unit()
        cams = [p for p in below.parts if p.key.startswith("locam")]
        self.assertEqual(len(cams), gi_optics.cameras_below())
        above = gi_optics.above_unit()
        self.assertEqual(len([p for p in above.parts if p.key.startswith("upcam")]),
                         gi_optics.cameras_above())

    def test_the_optics_stand_at_the_working_distance(self):
        """렌즈가 작동거리에, 카메라가 그 뒤에 선다 — 눈대중이 아니다."""
        n = gi_optics.cameras_below()
        wd = gi_optics.working_distance_mm(n)
        below = {p.key: p for p in gi_optics.below_unit().parts}
        lens = below["lolens0"]
        self.assertAlmostEqual(lens.pos[1], -(wd + gi_optics.LENS_BODY_MM / 2.0),
                               places=3)
        cam = below["locam0"]
        # 카메라 **바깥** 끝이 곧 스택 높이다.
        far = abs(cam.pos[1]) + gi_optics.lens_housing_mm() / 2.0
        self.assertAlmostEqual(far, gi_optics.stack_height_mm(n), places=3)

    def test_the_drawn_stack_fits_the_allotted_room(self):
        """그린 것이 배정 공간 안에 있어야 한다 — 포락선이 그것을 말한다."""
        below = gi_optics.below_unit()
        self.assertAlmostEqual(below.envelope_mm[1], gi_optics.BELOW_DECK_MM,
                               places=3)
        self.assertLessEqual(gi_optics.stack_height_mm(gi_optics.cameras_below()),
                             below.envelope_mm[1])

    def test_the_lenses_sit_on_the_seat_centres(self):
        below = {p.key: p for p in gi_optics.below_unit().parts}
        for seat in gi_optics.seam_map():
            with self.subTest(seat=seat["index"]):
                self.assertAlmostEqual(below[f"lolens{seat['index']}"].pos[0],
                                       seat["centre"], places=3)

    def test_the_rollers_make_the_window_they_claim(self):
        """그린 롤러 사이 간격이 창 값과 같아야 한다."""
        rollers = [p for p in gi_optics.below_unit().parts
                   if p.key.startswith("lorl")]
        self.assertGreaterEqual(len(rollers), 2)
        zs = sorted(p.pos[2] for p in rollers)
        pitch = zs[1] - zs[0]
        self.assertAlmostEqual(pitch, gi_optics.ROLLER_PITCH_MM, places=3)
        self.assertAlmostEqual(pitch - rollers[0].size[0],
                               gi_optics.roller_window_mm(), places=3)

    def test_the_cover_glass_fits_inside_the_window(self):
        below = {p.key: p for p in gi_optics.below_unit().parts}
        self.assertLess(below["locover"].size[2], gi_optics.roller_window_mm())

    def test_the_window_close_up_is_the_real_section_only_magnified(self):
        """확대도는 배율만 다르고 값은 실제 그대로여야 한다."""
        mag = gi_optics.WINDOW_MAG
        w = {p.key: p for p in gi_optics.window_unit().parts}
        self.assertAlmostEqual(w["wnline"].size[2],
                               gi_optics.RESOLUTION_MM * mag, places=6)
        self.assertAlmostEqual(w["wndof"].size[1],
                               gi_optics.depth_of_field_mm(
                                   gi_optics.cameras_below()) * mag, places=6)
        rollers = sorted((p for p in gi_optics.window_unit().parts
                          if p.key.startswith("wnrl")), key=lambda p: p.pos[2])
        self.assertAlmostEqual(rollers[1].pos[2] - rollers[0].pos[2],
                               gi_optics.ROLLER_PITCH_MM * mag, places=6)

    def test_the_scan_line_is_a_sliver_of_the_window(self):
        """막는 것은 창의 폭이 아니라 밑의 높이다 — 그 대비가 형상에 있다."""
        self.assertLess(gi_optics.RESOLUTION_MM,
                        gi_optics.roller_window_mm() / 100.0)
        self.assertTrue(gi_optics.scan_line_fits_the_window())

    def test_every_part_says_what_it_does(self):
        for u in gi_optics.units():
            for p in u.parts:
                with self.subTest(f"{u.key}/{p.key}"):
                    self.assertGreater(len(p.role), 20)
                    self.assertTrue(p.material)


class TestCloseupDrawing(unittest.TestCase):
    """커밋된 확대도가 생성기 출력과 같고, 화면에 손으로 쓴 수가 없는지."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_gi_closeup")
        cls.html = CLOSEUP.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "PYTHONPATH=src python tools/build_gi_closeup.py 를 다시 돌릴 것")

    def test_it_is_derived_from_the_plant(self):
        self.assertIn("tools/build_gi_closeup.py", self.html)
        self.assertIn("<title>GI-302 · GI-303 검사 작동 확대도</title>", self.html)
        self.assertNotIn("<title>태양광 전처리 통합 플랜트</title>", self.html)

    def test_the_payload_is_the_model(self):
        units = json.loads(self.builder.unit_payload())
        self.assertEqual([u["key"] for u in units], ["below", "above", "window", "plate"])
        for got, want in zip(units, gi_optics.units() + (gi_plate.physics_unit(),)):
            with self.subTest(want.key):
                self.assertEqual(got["sheet"], want.sheet)
                self.assertEqual(len(got["parts"]), len(want.parts))
        self.assertEqual(units[2]["mag"], gi_optics.WINDOW_MAG)
        self.assertEqual(units[3]["mag"], gi_plate.PHYSICS_MAG)
        self.assertEqual(units[3]["view"], list(gi_plate.VIEW_DIR))
        self.assertEqual(units[0]["mag"], 1.0)

    def test_the_physics_payload_is_the_model(self):
        """XPBD 상수가 `gi_plate.physics_si()` 그대로인가 — 화면에 손으로 쓴 물리가 없다."""
        phy = json.loads(self.builder.physics_payload())
        self.assertEqual(phy, json.loads(json.dumps(gi_plate.physics_si())))
        self.assertIn("eiTable", phy)
        self.assertEqual(phy["nodes"], gi_plate.STRIP_NODES)
        self.assertNotIn("9.81", self.builder.spec_payload())        # 중력은 씬이 안다

    def test_the_open_questions_include_the_plate(self):
        payload = json.loads(self.builder.open_payload())
        titles = [q[0] for q in payload]
        for t, _ in gi_plate.open_questions():
            with self.subTest(t):
                self.assertIn(t, titles)

    def test_the_seam_payload_is_the_model_seat_map(self):
        seam = json.loads(self.builder.seam_payload())
        self.assertEqual(seam["seats"], [dict(x) for x in gi_optics.seam_map()])
        self.assertEqual(seam["cameras"], gi_optics.cameras_below())
        self.assertTrue(seam["covers"])
        self.assertEqual(seam["oneNeeds"], gi_optics.one_camera_would_need_mm())
        self.assertEqual(seam["allotted"], gi_optics.BELOW_DECK_MM)

    def test_the_page_carries_the_finding_not_just_the_numbers(self):
        """이 셀의 결론은 '한 대로는 자리가 모자란다' 다 — 그것이 화면에 있어야 한다."""
        self.assertIn(f"{gi_optics.one_camera_would_need_mm():.0f} mm", self.html)
        self.assertIn(f"{gi_optics.single_camera_shortfall_mm():.0f} mm 초과", self.html)
        self.assertIn("화소 때문이 아니다", self.html)

    def test_the_headline_numbers_reach_the_page(self):
        n = gi_optics.cameras_below()
        for text in (f"{gi_optics.line_rate_hz():,.0f} line/s",
                     f"{gi_optics.exposure_us():.0f} µs",
                     f"{gi_optics.working_distance_mm(n):.0f} mm",
                     f"{gi_optics.depth_of_field_mm(n)} mm",
                     f"{gi_optics.roller_window_mm():.0f} mm",
                     f"{gi_optics.mb_per_panel():.0f} MB"):
            with self.subTest(text):
                self.assertIn(text, self.html)

    def test_no_number_is_typed_by_hand(self):
        """생성기가 모델을 부르지 않고 수를 적어 두면 모델이 바뀌어도 안 따라온다."""
        source = (ROOT / "tools/build_gi_closeup.py").read_text(encoding="utf-8")
        for typed in ("1,065", "1064.7", "498.2", "3,000 line", "466.67"):
            with self.subTest(typed):
                self.assertNotIn(typed, source)

    def test_the_console_is_wired(self):
        for ident in ("gi-cu-tabs", "gi-cu-band", "gi-cu-rows", "gi-cu-spec",
                      "gi-cu-principle", "gi-cu-open", "__pvGiCloseup"):
            with self.subTest(ident):
                self.assertIn(ident, self.html)

    def test_the_open_questions_reach_the_page(self):
        payload = json.loads(self.builder.open_payload())
        self.assertEqual([q[0] for q in payload],
                         [t for t, _ in gi_optics.open_questions() + gi_plate.open_questions()])
        self.assertGreater(len(payload), 3)


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
