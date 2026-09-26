"""BR-306 백시트 박리 — **약한 면은 덫이었다.**

박리를 못 쓴다고 본 이유 하나는 정말로 틀렸고, 하나는 맞았는데 고쳤다고
착각했다. 이 묶음이 그 둘을 갈라 지킨다.

1. **맞게 고친 것** — 「노후 패널은 접착이 세다」는 반대다. 접착은 세월이
   갈수록 약해지고, 20 년 된 패널을 받는 것이 **유리하다** (`TestAgingHelps`).
2. **틀리게 고친 것** — 「가장 약한 면에서 뜯으면 된다」. 백시트 안쪽
   외피–심재 면이 20 배 약하고 거기에 불소가 얹혀 있어 답처럼 보였는데,
   **PET 심재도 실리콘과 같은 침강분으로 간다.** 외피만 벗기면 심재가 남아
   오염이 그대로다 (`TestTheWeakPlaneIsATrap`).

기구도 반대로 알고 있었다. 백시트가 정광으로 **올라온다**고 적었는데 실제로는
물보다 무겁고 조각이 부상 상한보다 커서 **가라앉는다.** 정본은 `separation`
이고, 이 묶음은 거기서 사양을 받아 온다 — 값을 여기서 다시 정하지 않는다.
"""

from __future__ import annotations

import unittest

from tests import _path  # noqa: F401

from pv_preprocess import br_peel, campaign, handoff, separation, sg_grind


class TestTheWeakPlaneIsATrap(unittest.TestCase):
    """요지 — 가장 약한 면이 문제를 푸는 것처럼 보이지만 안 푼다."""

    def test_the_weakest_plane_does_not_remove_what_must_go(self):
        """제일 약한 면은 아무것도 **완전히** 못 빼낸다 — 심재가 남는다."""
        self.assertTrue(br_peel.the_weak_plane_is_a_trap())
        weak = br_peel.weakest_interface()
        self.assertEqual(weak.key, "fluoro_pet")
        self.assertFalse(br_peel.is_sufficient(weak))
        self.assertEqual(weak.removes, ())

    def test_the_required_plane_is_the_expensive_one(self):
        """뜯어야 하는 면은 20 배 비싼 쪽이다."""
        req = br_peel.required_interface()
        self.assertEqual(req.key, "backsheet_eva")
        self.assertTrue(br_peel.is_sufficient(req))
        self.assertGreater(br_peel.cost_of_going_to_the_right_plane(), 10.0)
        self.assertAlmostEqual(
            br_peel.cost_of_going_to_the_right_plane(),
            round(br_peel.peel_force_n(req)
                  / br_peel.peel_force_n(br_peel.weakest_interface()), 1), places=1)

    def test_the_spec_comes_from_separation_not_from_here(self):
        """무엇이 빠져야 하는지는 `separation` 이 정한다 — 여기서 안 정한다."""
        self.assertEqual(br_peel.must_remove(),
                         separation.gate_component_keys("backsheet"))
        self.assertIn("pet", br_peel.must_remove())
        self.assertIn("fluoro", br_peel.must_remove())
        self.assertEqual(separation.gate_owner("backsheet"), "BR-305 (연마)")

    def test_removing_pet_from_the_spec_would_make_the_weak_plane_enough(self):
        """PET 이 오염원이 아니었다면 약한 면으로 충분했다 — 거기가 갈림이다.

        즉 이 유닛이 비싸진 이유가 공법이 아니라 **PET 의 행선지**다.
        """
        self.assertFalse(br_peel.is_sufficient(br_peel.weakest_interface()))
        fake = br_peel.Interface(
            "probe", "가정", "불소만", 0.6, 0.1, ("fluoro", "pet"), "시험용")
        self.assertTrue(br_peel.is_sufficient(fake))

    def test_the_default_force_is_the_required_plane_not_the_weak_one(self):
        """기본값이 옳은 면이어야 한다 — 약한 면 값을 기본으로 두면 착각한다."""
        self.assertAlmostEqual(br_peel.peel_force_n(),
                               br_peel.peel_force_n(br_peel.required_interface()),
                               places=1)
        self.assertGreater(br_peel.peel_force_n(),
                           br_peel.peel_force_n(br_peel.weakest_interface()))

    def test_peeling_is_interfacial_work_so_thickness_never_enters(self):
        """박리력에 두께가 안 들어간다 — 계면 일이기 때문이다."""
        t0 = sg_grind.BACKSHEET_T_MM
        f0 = br_peel.peel_force_n()
        try:
            sg_grind.BACKSHEET_T_MM = t0 * 3.0
            self.assertEqual(br_peel.peel_force_n(), f0)
        finally:
            sg_grind.BACKSHEET_T_MM = t0


class TestAgingHelps(unittest.TestCase):
    """세월이 박리를 돕는다 — 처음에 반대로 알고 있었다."""

    def test_every_interface_weakens_with_age(self):
        """모든 계면이 노후와 함께 약해진다."""
        self.assertTrue(br_peel.aging_helps())
        for i in br_peel.INTERFACES:
            self.assertLess(i.gc_aged_n_mm, i.gc_fresh_n_mm, i.key)

    def test_the_aged_value_is_the_design_value(self):
        """설계값이 노후값이다 — 우리가 받는 것은 20 년 된 패널이다."""
        self.assertLess(br_peel.peel_force_n(aged=True),
                        br_peel.peel_force_n(aged=False))
        self.assertAlmostEqual(
            br_peel.peel_force_n(),
            round(br_peel.required_interface().gc_aged_n_mm
                  * float(campaign.PANEL_WIDTH_MM), 1), places=1)

    def test_heat_takes_it_down_further(self):
        """가열이 그 위에서 한 번 더 깎는다 — 둘이 남은 위안 전부다."""
        self.assertLess(br_peel.heat_brings_it_to_n(), br_peel.peel_force_n())
        self.assertAlmostEqual(
            br_peel.heat_brings_it_to_n(),
            round(br_peel.peel_force_n() * br_peel.HEAT_DERATE, 1), places=1)
        self.assertLess(br_peel.HEAT_ASSIST_C[0], br_peel.HEAT_ASSIST_C[1])
        self.assertGreater(br_peel.aging_saves_us(), 1.0)
        self.assertGreater(br_peel.heat_saves_us(), 1.0)


class TestTheRepoHadTheWrongNumber(unittest.TestCase):
    """저장소가 들고 있던 0.5 N/mm 는 문헌값의 몇 분의 일이었다."""

    def test_sg_grind_now_defers_to_this_module(self):
        """같은 수에 이름이 둘이면 갈라진다 — 정본은 `br_peel` 이다."""
        self.assertFalse(hasattr(sg_grind, "BACKSHEET_PEEL_GC_N_MM"))
        self.assertAlmostEqual(
            sg_grind.backsheet_peel_gc_n_mm(),
            next(i for i in br_peel.INTERFACES
                 if i.key == "backsheet_eva").gc_aged_n_mm, places=3)

    def test_the_corrected_value_is_several_times_the_old_planning_one(self):
        """고친 값이 옛 계획값보다 여러 배다 — 박리를 쉽게 보고 있었다."""
        self.assertGreaterEqual(sg_grind.backsheet_peel_gc_n_mm(), 4 * 0.5)

    def test_peeling_still_beats_abrading_after_the_correction(self):
        """상수를 올려도 결론은 그대로다 — 계면 일과 부피 일의 차이다."""
        self.assertGreater(sg_grind.peel_beats_abrade_by(), 100)
        self.assertAlmostEqual(
            sg_grind.backsheet_peel_force_n(),
            round(sg_grind.backsheet_peel_gc_n_mm()
                  * float(campaign.PANEL_WIDTH_MM), 1), places=1)


class TestTheMethodTableIsHonestAboutWhatBlocksEach(unittest.TestCase):
    """공법 후보 — 되는 이유가 아니라 **막히는 곳**을 적는다."""

    def test_every_method_names_its_blocker(self):
        """막히는 곳 없는 공법은 아직 안 본 공법이다."""
        self.assertGreaterEqual(len(br_peel.METHODS), 5)
        for m in br_peel.METHODS:
            self.assertTrue(m.blocker.strip(), m.key)
            self.assertTrue(m.parameters.strip(), m.key)
            self.assertTrue(m.principle.strip(), m.key)

    def test_the_laser_is_clean_but_far_too_slow(self):
        """레이저는 가장 깨끗한데 면적 속도가 벽이다 — 그것을 적어 둔다."""
        laser = next(m for m in br_peel.METHODS if m.key == "ir_laser")
        self.assertTrue(laser.solvent_free)
        self.assertIsNone(laser.seconds_per_panel)
        self.assertIn("면적 속도", laser.blocker)

    def test_the_solvent_route_is_fast_but_carries_a_regulated_substance(self):
        """DMAc 는 상온 5 분으로 빠르지만 규제가 설계를 지배한다."""
        dmac = next(m for m in br_peel.METHODS if m.key == "dmac_soak")
        self.assertFalse(dmac.solvent_free)
        self.assertIn("생식독성", dmac.blocker)
        self.assertLessEqual(dmac.seconds_per_panel, 300.0)

    def test_the_recommendation_is_solvent_free_and_needs_no_pressure_vessel(self):
        """먼저 시험할 것은 용제도 압력용기도 안 드는 쪽이다."""
        rec = br_peel.recommended()
        self.assertEqual(rec.key, "heat_vacuum")
        self.assertTrue(rec.solvent_free)
        self.assertIn(rec, br_peel.solvent_free_methods())
        self.assertGreaterEqual(len(br_peel.solvent_free_methods()), 3)

    def test_inline_fitness_is_measured_against_the_line_takt(self):
        """인라인 여부를 라인 택트로 잰다 — 여기서 정하지 않는다."""
        self.assertAlmostEqual(br_peel.line_takt_s(), campaign.ideal_takt_s(),
                               places=2)
        for m in br_peel.methods_that_fit_inline():
            self.assertLessEqual(m.seconds_per_panel, br_peel.line_takt_s())


class TestTheGapMustBeMadeNotFound(unittest.TestCase):
    """칼날이 들어갈 틈이 **애초에 없다** — 그래서 공정이 둘이다.

    한때 이 자리를 「JBR 절결을 주워 쓸 수 있다」로 적었다. 있는 구멍을 찾는
    발상이었고, 실제 공정은 **틈을 만드는 공정을 따로 둔다.**
    """

    def test_the_unit_is_two_stages_not_one(self):
        """1 차 커팅과 2 차 커팅(= 박리)이 갈린다 — **정확히 둘이다.**

        한때 셋으로 세었다: 커팅 · 칼날 진입 · 박리. 뒤의 둘은 같은 것이고
        현장이 그것을 「2 차 커팅」이라 부른다.
        """
        self.assertTrue(br_peel.a_gap_must_be_made_not_found())
        self.assertEqual(len(br_peel.stages()), 2)
        first = br_peel.stages()[0]
        self.assertIn("1 차", first[0])
        self.assertIn(f"{br_peel.STARTER_CUT_OFFSET_MM:.0f} mm", first[1])
        self.assertIn(br_peel.STARTER_CUT_ORIENTATION, first[1])
        self.assertIn("가로", br_peel.STARTER_CUT_ORIENTATION)

    def test_thirty_millimetres_is_an_offset_not_a_length(self):
        """30 mm 는 **변에서 들어온 거리**이지 절단 길이가 아니다.

        한 번 절단 길이로 읽어 짧은 슬릿으로 모델링했다 — 46.7 배를 짧게
        잡은 것이었다. 절단선은 폭 전체를 지른다.
        """
        self.assertFalse(hasattr(br_peel, "STARTER_CUT_MM"))
        self.assertAlmostEqual(br_peel.starter_cut_length_mm(),
                               float(campaign.PANEL_WIDTH_MM), places=1)
        self.assertGreater(br_peel.starter_cut_length_mm(),
                           10 * br_peel.STARTER_CUT_OFFSET_MM)
        self.assertTrue(br_peel.one_cut_opens_the_full_width())

    def test_the_freed_tab_is_what_the_blade_grips(self):
        """들리는 띠의 넓이 = 들어온 거리 × 폭 — 칼날이 물 자리다."""
        self.assertAlmostEqual(
            br_peel.released_tab_mm2(),
            round(br_peel.STARTER_CUT_OFFSET_MM
                  * br_peel.starter_cut_length_mm(), 1), places=1)

    def test_the_cut_crosses_cells_so_the_window_never_relaxes(self):
        """절단선이 셀 위를 지난다 — 여백으로 피할 수 없다.

        연마가 면 3.5 m² 에서 겪는 깊이 문제를 커팅은 선 1,400 mm 에서
        겪는다. 면적이 작을 뿐 성격은 같다.
        """
        self.assertTrue(br_peel.STARTER_CUT_CROSSES_CELLS)
        self.assertTrue(br_peel.cut_must_hold_the_window_over_cells())
        self.assertIn("셀 위", br_peel.stages()[0][1])

    def test_the_cut_has_the_same_depth_window_as_abrading(self):
        """커팅 깊이 창이 연마 절입 창과 같다 — 라미네이트가 정하기 때문이다."""
        from pv_preprocess import br_abrade
        self.assertTrue(br_peel.starter_cut_is_the_same_depth_problem())
        self.assertEqual(br_peel.starter_cut_window_mm(),
                         br_abrade.depth_window_mm())
        lo, hi = br_peel.starter_cut_window_mm()
        self.assertAlmostEqual(lo, sg_grind.BACKSHEET_T_MM, places=3)
        self.assertGreater(hi, lo)

    def test_the_window_is_owned_elsewhere_not_redefined_here(self):
        """창을 여기서 다시 정하지 않는다 — 두 곳에 적으면 갈라진다."""
        from pv_preprocess import br_abrade
        lo0, hi0 = br_abrade.depth_window_mm()
        d0 = br_abrade.BACK_EVA_T_MM
        try:
            br_abrade.BACK_EVA_T_MM = d0 + 0.30
            self.assertNotEqual(br_peel.starter_cut_window_mm(), (lo0, hi0))
            self.assertEqual(br_peel.starter_cut_window_mm(),
                             br_abrade.depth_window_mm())
        finally:
            br_abrade.BACK_EVA_T_MM = d0

    def test_the_start_point_and_the_place_are_both_closed_now(self):
        """시작점도 자리도 닫혔다 — 남은 것은 **깊이를 무엇으로 잡나**다.

        물음이 두 번 좁아졌다: 「어디서 시작하나」 → 「어디에 긋나」 →
        「그 창을 1,400 mm 내내 무엇으로 지키나」.
        """
        note = " ".join(br_peel.what_the_first_cut_settles())
        self.assertIn("시작점 물음이 닫혔다", note)
        self.assertIn("자리도 정해졌다", note)
        self.assertIn("절단 깊이를 무엇으로 잡는지가 안 정해졌다",
                      " ".join(br_peel.open_questions()))

    def test_the_second_stage_is_the_peel_under_a_plant_name(self):
        """②는 박리다 — 현장이 그것을 「2 차 커팅」이라 부를 뿐이다.

        도면 글자만 보고 「절단이 한 번 더 있다」로 읽었다가 고쳤다.
        공정은 둘이고 절단은 1 차 한 번뿐이다.
        """
        self.assertEqual(len(br_peel.stages()), 2)
        second = br_peel.stages()[1]
        self.assertIn("2 차 커팅", second[0])
        self.assertIn("박리", second[0])
        self.assertIn("벗긴다", second[1])
        self.assertFalse(hasattr(br_peel, "second_cut_is_unread"))

    def test_the_vocabulary_trap_is_written_down(self):
        """현장 말과 물리 이름이 어긋난 자리를 적어 둔다 — 한 번 틀렸으므로."""
        note = " ".join(br_peel.the_word_cutting_names_the_peel())
        self.assertIn("2 차 커팅", note)
        self.assertIn("공정은 둘이다", note)
        self.assertIn("말이 공정을 가리키지 물리를 가리키지 않는다", note)
        self.assertGreaterEqual(len(br_peel.the_word_cutting_names_the_peel()), 4)

    def test_the_peel_force_is_settled_not_provisional(self):
        """떼어야 할 면이 그대로이므로 **합**은 확정이다."""
        note = " ".join(br_peel.the_word_cutting_names_the_peel())
        self.assertIn("잠정이 아니라", note)
        self.assertNotIn("secondCutIsUnread", br_peel.summary())
        self.assertAlmostEqual(
            br_peel.peel_force_n(),
            br_peel.peel_force_n(br_peel.required_interface()), places=1)

    def test_the_note_no_longer_says_one_front_carries_it(self):
        """「절단이 안 나눈다」를 「아무것도 안 나눈다」로 읽었던 자리다.

        절단은 폭을 안 나누지만 **칼날이 나눈다.** 그 정정이 적혀 있어야 한다.
        """
        note = " ".join(br_peel.the_word_cutting_names_the_peel())
        self.assertNotIn("한 번에 벗기는 값 그대로", note)
        self.assertIn("한 점이 받는 것은 아니다", note)
        self.assertIn(f"{br_peel.BLADE_COUNT} 장", note)

    def test_no_stage_claims_the_gap_already_exists(self):
        """어느 단계도 「틈이 이미 있다」고 말하지 않는다 — 만들어서 연다."""
        text = " ".join(v for _, v in br_peel.stages())
        self.assertIn("진입구가 된다", text)
        self.assertIn("긋는다", text)
        self.assertNotIn("주워", text)


class TestTheRealKnifeGeometry(unittest.TestCase):
    """SHK-101 실측 형상 — 내가 가정으로 채웠던 자리를 이 값들이 고쳤다."""

    def test_the_knife_is_wider_than_the_panel(self):
        """전폭 = 중앙 + 양쪽 계단 = 1,500. 패널 1,400 에 양쪽 50 이 남는다."""
        self.assertAlmostEqual(br_peel.knife_width_mm(), 1500.0, places=1)
        self.assertAlmostEqual(
            br_peel.knife_width_mm(),
            br_peel.CENTER_BLADE_MM
            + 2 * br_peel.STAGGER_STEPS * br_peel.STEP_BLADE_MM, places=1)
        self.assertAlmostEqual(br_peel.overhang_each_side_mm(), 50.0, places=1)
        self.assertGreater(br_peel.knife_width_mm(), campaign.PANEL_WIDTH_MM)

    def test_the_insert_length_sum_carries_the_lap(self):
        """인서트 길이 합 1,590 = 전폭 + 양쪽 단마다 겹침."""
        self.assertAlmostEqual(br_peel.blade_length_sum_mm(), 1590.0, places=1)
        self.assertAlmostEqual(
            br_peel.blade_length_sum_mm() - br_peel.knife_width_mm(),
            2 * br_peel.STAGGER_STEPS * br_peel.BLADE_LAP_MM, places=1)

    def test_seven_blades_come_from_one_centre_and_three_steps_a_side(self):
        """칼날 수는 선언이 아니라 형상에서 나온다 — 1 + 2×3."""
        self.assertEqual(br_peel.BLADE_COUNT, 1 + 2 * br_peel.STAGGER_STEPS)
        self.assertEqual(len(br_peel.blade_segments()), br_peel.BLADE_COUNT)

    def test_the_strips_are_not_uniform(self):
        """**내가 틀린 자리** — 7×200 균일이 아니라 중앙 300 · 바깥은 잘린다."""
        widths = br_peel.strip_widths_mm()
        self.assertEqual(widths, (300.0, 200.0, 200.0, 200.0, 200.0, 150.0, 150.0))
        self.assertGreater(len(set(widths)), 1)
        self.assertAlmostEqual(br_peel.widest_strip_mm(), 300.0, places=1)

    def test_the_engaged_widths_add_up_to_the_panel(self):
        """조각들이 패널 안에서 무는 폭의 합은 패널 폭이어야 한다."""
        self.assertAlmostEqual(br_peel.engaged_width_mm(),
                               campaign.PANEL_WIDTH_MM, places=1)

    def test_the_worst_segment_sets_the_spec_not_the_average(self):
        """사양은 평균이 아니라 최악 조각이다 — 중앙 300 → 600 N."""
        self.assertAlmostEqual(br_peel.peel_force_per_blade_n(), 600.0, places=1)
        self.assertAlmostEqual(br_peel.per_blade_relief(), 4.67, places=2)
        self.assertLess(br_peel.per_blade_relief(), br_peel.BLADE_COUNT)

    def test_heating_derates_the_segment_the_same_way(self):
        """가열은 조각에도 같은 몫으로 걸린다."""
        self.assertAlmostEqual(
            br_peel.peel_force_per_blade_n(heated=True),
            round(br_peel.peel_force_per_blade_n() * br_peel.HEAT_DERATE, 1),
            places=1)

    def test_splitting_the_width_does_not_change_the_total(self):
        """조각별 힘을 다 더하면 폭 전체 값이다 — 겹침은 안 센다."""
        self.assertTrue(br_peel.total_force_is_conserved())
        self.assertAlmostEqual(
            sum(br_peel.peel_force_on_segment_n(s)
                for s in br_peel.blade_segments()),
            br_peel.peel_force_n(), delta=1.0)

    def test_the_load_is_not_carried_by_one_front(self):
        """합을 한 점이 받는 것으로 적었던 자리를 판정으로 막는다."""
        self.assertTrue(br_peel.the_load_is_carried_by_seven_not_one())
        self.assertGreater(br_peel.BLADE_COUNT, 1)

    def test_the_span_ratio_is_the_knife_over_the_widest_segment(self):
        """**내가 틀린 자리** — n² · n⁴ 의 n 은 칼날 수가 아니라 span 비다."""
        self.assertAlmostEqual(br_peel.span_ratio(), 5.0, places=3)
        self.assertAlmostEqual(br_peel.one_piece_blade_span_mm(),
                               br_peel.knife_width_mm(), places=1)
        self.assertAlmostEqual(br_peel.bending_moment_ratio(), 25.0, places=1)
        self.assertAlmostEqual(br_peel.deflection_ratio(), 625.0, places=1)
        self.assertNotAlmostEqual(br_peel.deflection_ratio(), 2401.0, places=1)

    def test_the_reason_to_split_is_still_stiffness(self):
        """값이 작아졌어도 처짐 쪽이 여전히 가장 크다 — 이유는 안 바뀐다."""
        self.assertTrue(br_peel.stiffness_beats_force_as_the_reason())
        self.assertGreater(br_peel.deflection_ratio(),
                           br_peel.bending_moment_ratio())
        self.assertGreater(br_peel.bending_moment_ratio(),
                           br_peel.per_blade_relief())

    def test_the_strips_run_along_the_length(self):
        """띠는 길이 방향이고 1 차 커팅(가로)과 직각이다."""
        self.assertIn("길이", br_peel.STRIP_ORIENTATION)
        self.assertIn("가로", br_peel.STARTER_CUT_ORIENTATION)
        self.assertAlmostEqual(
            br_peel.peel_travel_mm(), campaign.PANEL_LENGTH_MM, places=1)

    def test_the_second_stage_states_the_per_blade_figure(self):
        """②가 합만 들면 사양을 잘못 고른다 — 최악 조각 값이 적혀 있어야."""
        second = br_peel.stages()[1][1]
        self.assertIn(f"{br_peel.peel_force_per_blade_n():,.0f} N", second)
        self.assertIn(f"{br_peel.BLADE_COUNT} 장", second)
        self.assertNotIn("한 번에", second)

    def test_the_summary_carries_the_real_geometry(self):
        """도면 리터럴이 실측 형상을 본다."""
        s = br_peel.summary()
        for key in ("knifeWidthMm", "bladeLengthSumMm", "staggerRiseMm",
                    "staggerSpreadMm", "bladeLapMm", "widestStripMm",
                    "stripWidthsMm", "spanRatio", "engagedWidthMm"):
            self.assertIn(key, s)
        self.assertEqual(s["staggerSteps"], br_peel.STAGGER_STEPS)


class TestTheMirrorIsMarkedAsOne(unittest.TestCase):
    """베낀 값은 갈라질 자리다 — 정본이 오면 시끄럽게 실패해야 한다."""

    def test_the_mirror_knows_it_is_a_mirror(self):
        """정본 모듈이 이 트리에 없는 동안만 베껴 두는 것이 허용된다."""
        self.assertTrue(br_peel.the_mirror_must_become_a_delegation())
        self.assertTrue(br_peel.summary()["mirrorIsStillAMirror"])

    def test_the_provenance_is_written_in_the_source(self):
        """어디서 베꼈는지가 소스에 적혀 있어야 한다."""
        import inspect
        src = inspect.getsource(br_peel)
        self.assertIn("SHK-101", src)
        self.assertIn("console_consts", src)
        self.assertIn("발주자 확정", src)

    def test_the_interface_disagreement_is_recorded_not_resolved(self):
        """형상은 받아 쓰고 **계면은 안 바꿨다** — 그 갈림이 글로 남아야 한다."""
        note = " ".join(br_peel.where_shk101_and_this_unit_disagree())
        self.assertIn("유리 계면", note)
        self.assertIn("백시트–EVA", note)
        self.assertIn("안 들었다", note)
        self.assertGreaterEqual(
            len(br_peel.where_shk101_and_this_unit_disagree()), 5)
        # 판정을 만들지 않는다 — 어느 쪽이 맞는지는 내가 정할 일이 아니다.
        self.assertFalse(hasattr(br_peel, "shk101_is_the_real_unit"))

    def test_the_two_peel_resistances_are_far_apart(self):
        """다섯 배 넘게 벌어져 있다 — 한쪽이 틀렸거나 둘이 다른 공정이다."""
        mine = br_peel.required_interface().gc_aged_n_mm
        self.assertGreater(br_peel.SHK101_PEEL_N_MM / mine, 5.0)


class TestTheStaircaseEngagesInOrder(unittest.TestCase):
    """물리는 순차, 진행은 동시 — 그리고 **최대 합력은 안 내려간다.**"""

    def test_the_layout_is_a_staircase_not_a_row(self):
        """배치가 중앙 먼저, 좌우 쌍이 한 단씩 물러나는 계단이다."""
        self.assertIn("계단식", br_peel.BLADE_LAYOUT)
        self.assertIn("계단식", br_peel.stages()[1][1])
        self.assertIn("진행은 다 같이", br_peel.stages()[1][1])
        backs = sorted({s.back_mm for s in br_peel.blade_segments()})
        self.assertEqual(backs, [0.0, 80.0, 160.0, 240.0])

    def test_the_spread_is_steps_times_rise_not_n_minus_one(self):
        """**내가 틀린 자리** — 대칭 계단이라 퍼짐이 (n−1)p 의 절반이다."""
        self.assertAlmostEqual(br_peel.stagger_spread_mm(), 240.0, places=1)
        self.assertAlmostEqual(
            br_peel.stagger_spread_mm(),
            br_peel.STAGGER_STEPS * br_peel.STAGGER_RISE_MM, places=1)
        self.assertLess(br_peel.stagger_spread_mm(),
                        (br_peel.BLADE_COUNT - 1) * br_peel.STAGGER_RISE_MM)

    def test_the_real_rise_does_not_lower_the_peak(self):
        """**요지** — 퍼짐 240 이 띠 길이 2,500 안이라 합력이 그대로다."""
        self.assertTrue(br_peel.all_blades_engage_at_once())
        self.assertFalse(br_peel.stagger_lowers_the_peak())
        self.assertAlmostEqual(br_peel.peak_force_n(),
                               br_peel.peel_force_n(), places=1)

    def test_only_past_the_boundary_does_the_peak_fall(self):
        """경계는 띠 길이 ÷ 단수 = 833 mm. 실제 80 은 한참 아래다."""
        edge = br_peel.rise_below_which_all_engage_mm()
        self.assertAlmostEqual(edge, campaign.PANEL_LENGTH_MM / 3, places=1)
        self.assertLess(br_peel.STAGGER_RISE_MM, edge / 10)
        self.assertTrue(br_peel.stagger_lowers_the_peak(edge + 1.0))
        self.assertLess(br_peel.peak_force_n(edge + 1.0), br_peel.peel_force_n())

    def test_lowering_the_peak_costs_stroke(self):
        """합력을 낮추는 값은 행정으로 치른다."""
        edge = br_peel.rise_below_which_all_engage_mm()
        self.assertGreater(br_peel.carriage_travel_mm(edge),
                           br_peel.carriage_travel_mm())
        self.assertGreater(br_peel.carriage_travel_mm(edge),
                           1.9 * br_peel.peel_travel_mm())

    def test_the_carriage_goes_the_spread_further(self):
        """캐리지 행정 = 퍼짐 + 띠 길이 = 2,740."""
        self.assertAlmostEqual(br_peel.carriage_travel_mm(), 2740.0, places=1)
        self.assertAlmostEqual(
            br_peel.carriage_travel_mm(),
            br_peel.stagger_spread_mm() + br_peel.peel_travel_mm(), places=1)
        self.assertGreater(br_peel.carriage_travel_mm(),
                           br_peel.peel_travel_mm())

    def test_the_ramp_is_four_steps_not_seven(self):
        """**내가 틀린 자리** — 좌우 쌍이 같이 물어 걸음이 조각 수보다 적다."""
        ramp = br_peel.engagement_ramp()
        self.assertEqual(len(ramp), br_peel.STAGGER_STEPS + 1)
        self.assertEqual(br_peel.load_rise_is_divided_by(), 4)
        self.assertNotEqual(br_peel.load_rise_is_divided_by(),
                            br_peel.BLADE_COUNT)
        self.assertEqual([w for _, w, _ in ramp], [300.0, 700.0, 1100.0, 1400.0])
        self.assertAlmostEqual(ramp[-1][2], br_peel.peel_force_n(), places=1)

    def test_the_ramp_only_grows(self):
        """물린 폭과 합력이 단마다 늘기만 해야 한다."""
        ramp = br_peel.engagement_ramp()
        for (t0, w0, f0), (t1, w1, f1) in zip(ramp, ramp[1:]):
            self.assertLess(t0, t1)
            self.assertLess(w0, w1)
            self.assertLess(f0, f1)

    def test_what_it_buys_is_the_rise_not_the_peak(self):
        """사 주는 것은 최대값이 아니라 기울기다."""
        note = " ".join(br_peel.what_the_staircase_buys())
        self.assertIn("최대 합력은 안 내려간다", note)
        self.assertIn("걸음에 나뉜다", note)
        self.assertIn("좌우 쌍이 같은 단에서 같이 물기", note)
        self.assertGreaterEqual(len(br_peel.what_the_staircase_buys()), 4)

    def test_the_lap_closes_what_splits_the_film(self):
        """겹침이 「무엇이 가르나」를 닫는다 — 옆날도 찢김도 아니었다."""
        note = " ".join(br_peel.open_questions())
        self.assertIn("닫혔다", note)
        self.assertIn(f"{br_peel.BLADE_LAP_MM:g} mm", note)
        self.assertIn("안쪽 밑으로", note)
        self.assertNotIn("옆날이 째는 것인지", note)

    def test_the_rise_is_no_longer_unknown(self):
        """단높이는 발주자 확정이라 이제 상수다 — None 이 아니다."""
        self.assertFalse(hasattr(br_peel, "STAGGER_PITCH_MM"))
        self.assertAlmostEqual(br_peel.STAGGER_RISE_MM, 80.0, places=1)
        self.assertIn("단높이", " ".join(br_peel.open_questions()))

    def test_the_interface_question_replaced_the_pitch_question(self):
        """닫힌 물음 자리에 **계면** 물음이 들어섰다 — 지금 가장 큰 열림이다."""
        note = " ".join(br_peel.open_questions())
        self.assertIn("어느 계면을 무는 유닛인지", note)
        self.assertIn("배 차이", note)

    def test_the_staircase_satisfies_the_support_condition_by_itself(self):
        """계단식이면 크로스빔 하나에 못 건다 — 조건이 저절로 지켜진다."""
        self.assertTrue(br_peel.the_staircase_splits_the_supports_for_us())
        self.assertTrue(br_peel.summary()["staircaseSplitsTheSupports"])


class TestTheDilemmaIsADatumProblem(unittest.TestCase):
    """백시트를 먼저 뜯으려면 EVA 안에 칼끝을 세워야 한다 — 기준면이 없다."""

    def test_the_band_is_the_rear_eva_and_comes_from_br_abrade(self):
        """띠는 후면 EVA 한 겹이고 값은 `br_abrade` 가 든다 — 두 곳에 안 적는다."""
        from pv_preprocess import br_abrade
        lo, hi = br_abrade.depth_window_mm()
        self.assertAlmostEqual(br_peel.eva_band_mm(), hi - lo, places=3)
        self.assertAlmostEqual(br_peel.eva_band_mm(),
                               br_abrade.BACK_EVA_T_MM, places=2)

    def test_the_tolerances_come_from_sg_grind(self):
        """제어폭도 베끼지 않는다 — 슈 기준·프레임 기준 둘 다 `sg_grind` 정본."""
        self.assertAlmostEqual(br_peel.depth_control_mm(True),
                               sg_grind.blade_assembly_tol_mm(), places=4)
        self.assertAlmostEqual(br_peel.depth_control_mm(False),
                               sg_grind.depth_stack_mm(), places=4)

    def test_only_the_face_reference_fits_in_the_band(self):
        """**요지** — 면 기준은 들어가고 프레임 기준은 창을 통째로 넘는다."""
        self.assertTrue(br_peel.the_face_reference_is_the_only_one_that_fits())
        self.assertGreater(br_peel.depth_margin_ratio(True), 1.0)
        self.assertLess(br_peel.depth_margin_ratio(False), 1.0)
        self.assertAlmostEqual(br_peel.depth_margin_ratio(True), 2.25, places=2)

    def test_the_margin_is_thin_even_when_it_fits(self):
        """들어가도 얇다 — 한쪽에 0.125 mm 다. 넉넉하다고 읽으면 안 된다."""
        self.assertAlmostEqual(br_peel.net_margin_each_side_mm(), 0.125, places=3)
        self.assertLess(br_peel.net_margin_each_side_mm(),
                        br_peel.eva_band_mm() / 3)

    def test_the_root_is_the_datum_not_the_precision(self):
        """유리는 기준면이 되고 EVA 는 안 된다 — 그것이 글로 남아야 한다."""
        note = " ".join(br_peel.there_is_no_datum_inside_the_eva())
        self.assertIn("접촉", note)
        self.assertIn("재서", note)
        self.assertIn("유리가 물리적으로 막아", note)
        self.assertGreaterEqual(
            len(br_peel.there_is_no_datum_inside_the_eva()), 4)

    def test_the_failure_is_asymmetric(self):
        """얕으면 하드 실패, 깊으면 공구 비용 — 그 비대칭이 적혀 있어야 한다."""
        note = " ".join(br_peel.the_window_has_a_soft_upper_edge())
        self.assertIn("하드 실패", note)
        self.assertIn("제품 손실이 아니다", note)
        self.assertIn("유리까지 가지 마라", note)

    def test_the_soft_edge_is_not_turned_into_a_number(self):
        """셀 두께와 전면 EVA 가 모델에 없으므로 **얼마나 넓어지는지 안 적는다.**"""
        note = " ".join(br_peel.the_window_has_a_soft_upper_edge())
        self.assertIn("못 적는다", " ".join(br_peel.open_questions()))
        self.assertIn("지어내지 않는다", note)
        for name in ("CELL_T_MM", "FRONT_EVA_T_MM", "soft_edge_extra_mm"):
            self.assertFalse(hasattr(br_peel, name), msg=name)

    def test_cutting_and_peeling_pull_temperature_apart(self):
        """자르기는 차가워야, 떼기는 뜨거워야 — 한 유닛에 온도가 둘 필요하다."""
        note = " ".join(br_peel.cutting_and_peeling_want_opposite_temperatures())
        self.assertIn("차가워야", note)
        self.assertIn("뜨거워야", note)
        self.assertIn("온도가 두 개 필요하다", note)
        self.assertIn("계면만 풀기", note)

    def test_the_order_swap_is_recorded_as_a_way_out(self):
        """순서를 바꾸면 깊이를 재서 멈출 일이 없어진다 — 근거로 남긴다."""
        note = " ".join(br_peel.removing_the_glass_first_removes_the_cut())
        self.assertIn("순서를 안 정했다", note)
        self.assertIn("EVA 를 가를 필요가 없어진다", note)
        self.assertIn("깊이를 재서 멈출 필요가 없어진다", note)
        self.assertGreaterEqual(
            len(br_peel.removing_the_glass_first_removes_the_cut()), 5)

    def test_the_cut_does_not_simply_vanish(self):
        """**내가 과하게 적었던 자리** — 구부리면 약한 면이 먼저 갈라진다.

        한때 「1 차 커팅이 없어진다」고 적었다. 같은 파일이 이미
        `the_weak_plane_is_a_trap()` 을 들고 있는데 그 둘을 연결하지 않았다.
        """
        note = " ".join(br_peel.removing_the_glass_first_removes_the_cut())
        self.assertNotIn("1 차 커팅이 없어진다", note)
        self.assertNotIn("1 차 커팅도 없어진다", note)
        self.assertIn("통째로 없어지는 것은 아니다", note)
        self.assertIn("면을 골라 줘야", note)
        self.assertIn(br_peel.weakest_interface().key, note)
        self.assertIn("분산 → 국소", note)
        # 열린 물음 쪽 사본도 같이 고쳐져 있어야 한다.
        self.assertNotIn("1 차 커팅도 없어진다",
                         " ".join(br_peel.open_questions()))

    def test_the_order_decides_four_things_not_five(self):
        """순서가 정하는 것은 넷이고 PR 본문은 무관하다 — 「다 지배한다」가 과했다."""
        rows = br_peel.what_the_order_decides()
        self.assertEqual(len(rows), 4)
        for subject, first, second in rows:
            self.assertTrue(subject and first and second)
            self.assertNotEqual(first, second)
        joined = " ".join(s for r in rows for s in r)
        self.assertNotIn("PR 본문", joined)

    def test_two_of_the_four_change_shape_rather_than_vanish(self):
        """②는 국소화되고 ③은 다른 유닛으로 옮겨간다 — 사라진다고 적지 않는다."""
        rows = dict((r[0], r[2]) for r in br_peel.what_the_order_decides())
        depth = next(v for k, v in rows.items() if "절단 깊이" in k)
        ratio = next(v for k, v in rows.items() if "기동" in k)
        self.assertIn("국소형", depth)
        self.assertIn("면 선택", depth)
        self.assertIn("값은 안 없어지고", ratio)
        self.assertIn("어느 계면에서 재느냐", ratio)

    def test_the_temperature_curve_survives_either_order(self):
        """온도 곡선만 순서를 안 기다려도 된다 — EVA 물성이기 때문이다."""
        self.assertTrue(br_peel.the_curve_is_worth_measuring_either_way())
        rows = dict((r[0], (r[1], r[2])) for r in br_peel.what_the_order_decides())
        curve = next(v for k, v in rows.items() if "온도별" in k)
        self.assertIn("둘", curve[0])
        self.assertIn("하나", curve[1])
        self.assertIn("버려지지 않는다", " ".join(br_peel.why_the_order_dominates()))

    def test_why_it_dominates_is_not_logical_entailment(self):
        """지배하는 이유가 함의가 아니라 **주체의 존재**라는 것이 적혀 있어야."""
        note = " ".join(br_peel.why_the_order_dominates())
        self.assertIn("논리적 함의가 아니다", note)
        self.assertIn("기계가 존재하느냐", note)
        self.assertIn("넷 중 셋", note)
        self.assertIn("네 관문은 순서와 무관", note)

    def test_the_order_is_not_decided_here(self):
        """**판정을 만들지 않는다** — 유닛이 있느냐는 발주처 몫이다."""
        self.assertTrue(br_peel.the_order_is_not_mine_to_decide())
        self.assertTrue(br_peel.summary()["orderIsNotOursToDecide"])
        for name in ("glass_first_is_better", "recommended_order",
                     "the_backsheet_unit_is_unnecessary"):
            self.assertFalse(hasattr(br_peel, name), msg=name)
        # 계면과 힘은 그대로여야 한다 — 형상만 받아 왔다.
        self.assertAlmostEqual(br_peel.required_interface().gc_aged_n_mm,
                               2.0, places=2)
        self.assertAlmostEqual(br_peel.peel_force_n(), 2800.0, places=1)

    def test_the_swap_names_what_it_still_needs_measured(self):
        """순서를 바꾸기 전에 모르는 둘 — 반송과 EVA 가 어느 쪽에 붙느냐."""
        note = " ".join(br_peel.what_the_order_swap_needs_measured())
        self.assertIn("깨져도 되는지", note)
        self.assertIn(separation.float_product().name, note)
        self.assertEqual(len(br_peel.what_the_order_swap_needs_measured()), 2)

    def test_the_open_questions_lead_with_the_dilemma(self):
        """열린 물음이 「갈려 있다」에서 멈추지 않고 **왜** 갈리는지 든다."""
        note = " ".join(br_peel.open_questions())
        self.assertIn("기준면이 없다", note)
        self.assertIn("종류의 차이", note)
        self.assertIn("내가 안 고른다", note)


class TestUpstreamAlreadyStoodForThis(unittest.TestCase):
    """상류가 이미 박리를 알고 있었다 — 새로 유도하지 않고 받아 온다."""

    def test_the_tear_risk_is_an_existing_upstream_spec(self):
        """찢김 위험이 이 유닛보다 먼저 사양으로 서 있었다."""
        self.assertTrue(br_peel.tear_risk_is_already_specified())
        self.assertGreater(handoff.RIBBON_STUB_MAX_MM, 0.0)
        self.assertFalse(handoff.RIBBON_MAY_BE_LAID_OVER)

    def test_the_conditions_come_from_handoff_not_from_here(self):
        """값을 여기서 다시 정하지 않는다 — 두 곳에 적으면 갈라진다."""
        text = " ".join(v for _, v in br_peel.upstream_conditions())
        self.assertIn(f"{handoff.RIBBON_STUB_MAX_MM:g}", text)
        self.assertIn(f"{handoff.SILICONE_RESIDUE_MAX_MM:g}", text)
        self.assertGreaterEqual(len(br_peel.upstream_conditions()), 3)

    def test_the_jbr_notch_is_no_longer_claimed_as_the_start_point(self):
        """JBR 절결은 여전히 있지만 **시작점이 아니다.**

        있는 구멍을 주워 쓰는 발상이었고, 실제 공정은 틈을 따로 만든다.
        절결 자체는 `handoff` 가 든 상류 사실로 남는다 — 정션박스 발자국
        안에만 있고 깊이 상한이 걸려 있다.
        """
        self.assertFalse(hasattr(br_peel, "jbr_notch_as_a_start_point"))
        self.assertGreater(handoff.BACKSHEET_NOTCH_MAX_MM, 0.0)
        self.assertTrue(handoff.BACKSHEET_NOTCH_FOOTPRINT_ONLY)
        self.assertTrue(br_peel.a_gap_must_be_made_not_found())


class TestItSaysWhyThisBeatsAbrading(unittest.TestCase):
    """연마 대신 이쪽을 먼저 보는 이유를 글로 적어 둔다."""

    def test_the_case_rests_on_removal_not_on_force(self):
        """요지는 힘이 아니라 **필름째 라인 밖으로 나간다**는 것이다.

        「미분이 안 생긴다」로 적었던 것을 고쳤다 — 급광이 32~75 µm 라
        미분 자체가 문제가 아니었다. 문제는 **안 잡힌 몫이 남는다**는 것이다.
        """
        note = " ".join(br_peel.why_not_abrading())
        self.assertIn("필름째", note)
        self.assertIn("침강분", note)
        self.assertGreaterEqual(len(br_peel.why_not_abrading()), 4)

    def test_the_open_questions_name_what_would_kill_it(self):
        """이 공법을 무너뜨릴 값을 숨기지 않는다 — 띠가 끝까지 가는가."""
        note = " ".join(br_peel.open_questions())
        self.assertIn("온전히 가는지", note)
        self.assertIn("찢어", note)
        self.assertGreaterEqual(len(br_peel.open_questions()), 4)

    def test_the_old_one_sheet_question_is_marked_closed(self):
        """「한 장으로 벗겨지나」는 현장이 답했다 — 열어 둔 척하지 않는다."""
        note = " ".join(br_peel.open_questions())
        self.assertIn("그 물음은 닫혔다", note)
        self.assertIn(f"{br_peel.BLADE_COUNT} 장", note)

    def test_what_splits_the_film_is_written_as_unknown(self):
        """무엇이 필름을 가르는지는 **안 들었다** — 세 번째 추측을 하지 않는다.

        현장이 든 것은 「칼날 갯수만큼」뿐이다. 옆날이 째는지 사이에서
        찢어지는지는 사양이 갈리는 물음이라 모른다고 적는다.
        """
        note = " ".join(br_peel.open_questions())
        self.assertIn("무엇이 필름을", note)
        self.assertIn("모른다", note)
        self.assertIn("추측", note)

    def test_the_summary_is_flat_and_complete(self):
        """요약이 도면 리터럴에 실릴 수 있는 모양인가."""
        s = br_peel.summary()
        for key in ("theWeakPlaneIsATrap", "peelForceN",
                    "costOfGoingToTheRightPlane", "requiredInterface"):
            self.assertIn(key, s)
        for v in s.values():
            self.assertIsInstance(v, (int, float, bool, str, list))


if __name__ == "__main__":
    unittest.main()
