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
        self.assertEqual(separation.gate_owner("backsheet"), "BR-305/306")

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
        """1 차 커팅과 2 차 칼날 진입이 갈린다."""
        self.assertTrue(br_peel.a_gap_must_be_made_not_found())
        self.assertGreaterEqual(len(br_peel.stages()), 3)
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

    def test_no_stage_claims_the_gap_already_exists(self):
        """어느 단계도 「틈이 이미 있다」고 말하지 않는다 — 만들어서 연다."""
        text = " ".join(v for _, v in br_peel.stages())
        self.assertIn("진입구가 된다", text)
        self.assertIn("긋는다", text)
        self.assertNotIn("주워", text)


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
        """이 공법을 무너뜨릴 값을 숨기지 않는다 — 한 장으로 벗겨지는가."""
        note = " ".join(br_peel.open_questions())
        self.assertIn("한 장", note)
        self.assertIn("찢어", note)
        self.assertGreaterEqual(len(br_peel.open_questions()), 4)

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
