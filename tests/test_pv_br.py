"""BR-305 백시트 면 연마 유닛 — 설계가 닫히는지, 그리고 **어디서 닫히다 마는지.**

이 유닛은 저장소에서 처음으로 「세울까 말까」 단계의 물건이다. 그래서 시험이
보는 것도 「값이 맞는가」만이 아니라 **「무엇이 이 결정을 가르는가」** 다.

세 가지가 이 설계를 정했고, 셋 다 처음 예상과 달랐다.

1. **깊이는 면에서 잡아야 한다.** 정반 기준 공차가 창(窓)을 넘는다 — SR-302 가
   띠에서 만난 벽과 같다. 아래 시험이 그 두 기준을 같은 창에 대고 견준다.
2. **헤드는 늘릴수록 나빠진다.** 절입이 얇아지면 가열층이 절입을 넘어 열이
   밑으로 들어간다. 헤드 수의 한계가 **위**에 있다는 것을 붙든다.
3. **채택은 0.02 mm 에서 갈린다.** 손익분기 절입 0.43 에 실제 절입 0.45 다.
   공법이 아니라 여유 깊이가 장부를 뒤집는다 — 그 날카로움을 시험이 지킨다.

그리고 이 유닛이 정말로 하는 일은 불소를 **없애는 것이 아니라 옮기는 것**이다.
가연 풍량 비율이 0.149 에서 0.852 로 넘어가는 것을 마지막 묶음이 붙든다.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import br_abrade, campaign, dust, handoff, sg_grind


class TestItFitsTheLine(unittest.TestCase):
    """라인에 들어갈 수 있는가 — 자리와 시간."""

    def test_it_sits_between_the_two_units_that_force_its_position(self):
        """자리가 정해진다 — 프레임이 빠진 뒤여야 하고 열이 오기 전이어야 한다."""
        self.assertEqual(br_abrade.UPSTREAM_TAG, "AFR-101")
        self.assertEqual(br_abrade.DOWNSTREAM_TAG, "SG-301")

    def test_it_does_not_become_the_new_bottleneck(self):
        """새 병목이 되면 안 된다 — 점유가 라인 택트 안에 든다."""
        self.assertTrue(br_abrade.is_not_the_new_bottleneck())
        self.assertLessEqual(br_abrade.occupancy_s(), campaign.ideal_takt_s())
        self.assertGreater(br_abrade.occupancy_s(), campaign.sg_occupancy_s())

    def test_the_feed_is_set_by_the_takt_not_by_the_vendor(self):
        """이송속도는 택트가 정한다 — 벤더 카탈로그에서 베껴 오지 않는다."""
        self.assertAlmostEqual(
            br_abrade.feed_mm_s(),
            round(br_abrade.pass_length_mm() / br_abrade.belt_time_s(), 1), places=1)
        self.assertAlmostEqual(
            br_abrade.pass_length_mm(),
            float(campaign.PANEL_LENGTH_MM) + br_abrade.PASS_LEAD_MM, places=1)

    def test_it_runs_faster_than_the_demo_line_and_that_is_why_it_is_bigger(self):
        """실증 라인보다 빨리 가야 한다 — 그래서 그 설비를 그대로 못 쓴다.

        개구부 1,300 mm 가 패널 폭 1,400 을 못 받는 것과 같은 이야기를
        시간 쪽에서 본 것이다.
        """
        self.assertGreater(br_abrade.feed_mm_s(), sg_grind.FACE_ABRADE_FEED_MM_S)
        self.assertGreater(br_abrade.BELT_WIDTH_MM, sg_grind.FACE_ABRADE_OPENING_MM)
        self.assertFalse(sg_grind.panel_fits_face_abrader())


class TestDepthMustBeTakenFromTheFace(unittest.TestCase):
    """깊이 — 창이 있고, 그 창을 어디서 잡느냐가 유닛을 가른다."""

    def test_there_is_a_window_and_it_is_the_eva_underneath(self):
        """창의 넓이가 곧 백시트 밑 EVA 다 — 아래는 불소, 위는 셀이다."""
        lo, hi = br_abrade.depth_window_mm()
        self.assertAlmostEqual(lo, br_abrade.BACKSHEET_T_MM, places=3)
        self.assertAlmostEqual(hi, br_abrade.BACKSHEET_T_MM + br_abrade.BACK_EVA_T_MM,
                               places=3)
        self.assertTrue(br_abrade.target_is_inside_the_window())

    def test_we_overshoot_on_purpose(self):
        """일부러 백시트보다 깊이 판다 — 낮은 자리에 남으면 불소가 남는다."""
        self.assertGreater(br_abrade.TARGET_DEPTH_MM, br_abrade.BACKSHEET_T_MM)

    def test_a_bed_reference_misses_and_a_face_reference_fits(self):
        """SR-302 가 띠에서 만난 벽을 면에서 다시 만난다 — 답도 같다.

        정반을 기준으로 잡으면 유리·라미네이션 공차만으로 창을 넘고,
        면에서 잡으면 세 배 가까운 여유가 남는다.
        """
        self.assertTrue(br_abrade.bed_reference_would_miss())
        self.assertTrue(br_abrade.face_reference_fits())
        self.assertGreater(br_abrade.BED_REFERENCE_TOL_MM,
                           br_abrade.depth_window_half_mm())
        self.assertGreater(br_abrade.depth_margin_ratio(), 2.0)
        self.assertTrue(sg_grind.depth_is_referenced_to_the_panel())

    def test_following_the_face_across_the_width_costs_segments(self):
        """띠에서는 슈 하나였지만 면에서는 폭 1,400 을 따라가야 한다."""
        self.assertAlmostEqual(
            br_abrade.platen_segments(),
            math.ceil(float(campaign.PANEL_WIDTH_MM) / br_abrade.PLATEN_SEGMENT_MM))
        self.assertGreater(br_abrade.platen_segments(), 10)


class TestHeatIsWhatDecidesTheMachine(unittest.TestCase):
    """열 — 동력보다 먼저 걸리고, 헤드 수의 한계를 **위**에 만든다."""

    def test_the_criterion_is_whether_the_heated_skin_leaves_as_chip(self):
        """판정이 온도가 아니라 δ/a 다 — 데워진 살이 칩으로 나가는가."""
        self.assertTrue(br_abrade.heat_leaves_with_the_chip())
        self.assertLess(br_abrade.skin_to_depth_ratio(), 1.0)
        self.assertAlmostEqual(
            br_abrade.skin_to_depth_ratio(),
            round(br_abrade.thermal_skin_mm() / br_abrade.depth_per_head_mm(), 3),
            places=3)

    def test_the_skin_follows_the_closed_form(self):
        """가열층은 닫힌식으로 검산된다 — δ = √(α·t), t = 접촉호/이송."""
        a = br_abrade.depth_per_head_mm()
        arc = math.sqrt(br_abrade.CONTACT_DRUM_D_MM * a)
        t = arc / br_abrade.feed_mm_s()
        self.assertAlmostEqual(br_abrade.contact_arc_mm(), arc, places=3)
        self.assertAlmostEqual(br_abrade.contact_time_s(), t, places=5)
        self.assertAlmostEqual(
            br_abrade.thermal_skin_mm(),
            math.sqrt(br_abrade.THERMAL_DIFFUSIVITY_MM2_S * t), places=4)

    def test_more_heads_is_worse_which_is_the_inverted_part(self):
        """헤드를 늘리면 나빠진다 — 이 설계에서 가장 뒤집힌 대목이다.

        절입이 얇아지면 가열층은 그만큼 안 줄어 δ/a 가 커진다. 그래서
        헤드 수의 한계가 아래가 아니라 위에 있다.
        """
        self.assertTrue(br_abrade.heads_are_thermally_sound())
        limit = br_abrade.max_heads_thermally_allowed()
        self.assertGreaterEqual(limit, br_abrade.HEADS)
        thin = br_abrade.TARGET_DEPTH_MM / (limit + 1)
        skin = math.sqrt(br_abrade.THERMAL_DIFFUSIVITY_MM2_S
                         * math.sqrt(br_abrade.CONTACT_DRUM_D_MM * thin)
                         / br_abrade.feed_mm_s())
        self.assertGreaterEqual(skin, thin)

    def test_the_flash_exceeds_melt_and_that_is_why_three_parts_are_mandatory(self):
        """flash 가 융점을 넘는다 — 오픈코트·에어나이프·낮은 주속이 옵션이 아니다."""
        self.assertTrue(br_abrade.flash_reaches_melt())
        self.assertLess(br_abrade.BELT_SPEED_M_S, 20.0)
        keys = {p.key for p in br_abrade.unit().parts}
        self.assertIn("airknife", keys)
        belt = next(p for p in br_abrade.unit().parts if p.key == "belt")
        self.assertIn("오픈코트", belt.material)


class TestPowerIsNotTheProblem(unittest.TestCase):
    """동력 — 걸림돌이 아니라는 것을 값으로 못 박는다."""

    def test_it_is_an_ordinary_industrial_sander(self):
        """총 동력이 시판 광폭 연마기 범위에 든다."""
        self.assertGreater(br_abrade.total_power_kw(), 10.0)
        self.assertLess(br_abrade.total_power_kw(), 150.0)
        self.assertAlmostEqual(
            br_abrade.total_power_kw(),
            br_abrade.power_per_head_kw() * br_abrade.HEADS, places=1)
        self.assertGreater(br_abrade.motor_rating_kw(), br_abrade.power_per_head_kw())

    def test_the_specific_energy_comes_from_sg_grind(self):
        """비에너지를 여기서 다시 정하지 않는다 — `sg_grind` 가 정본이다."""
        self.assertIs(br_abrade.ABRADE_J_MM3, sg_grind.BACKSHEET_ABRADE_J_MM3)
        self.assertIs(br_abrade.BACKSHEET_T_MM, sg_grind.BACKSHEET_T_MM)
        self.assertIs(br_abrade.DENSITY_G_MM3, sg_grind.BACKSHEET_DENSITY_G_MM3)


class TestTheLedgerTurnsOnTwoHundredthsOfAMillimetre(unittest.TestCase):
    """채택 여부가 공법이 아니라 **여유 깊이**에서 갈린다."""

    def test_the_break_even_depth_is_a_closed_form(self):
        """손익분기 절입은 하류 절감분을 면적과 비에너지로 나눈 값이다."""
        area = float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
        self.assertAlmostEqual(
            br_abrade.break_even_depth_mm(),
            round(br_abrade.downstream_heat_saved_j() / (area * br_abrade.ABRADE_J_MM3),
                  3), places=3)

    def test_the_backsheet_alone_would_pay_but_the_overshoot_tips_it(self):
        """백시트만 걷으면 남고, 남기지 않으려고 더 판 만큼 모자란다.

        이것이 이 유닛의 진짜 결론이다 — 「면 연마는 되는가」가 아니라
        「면을 얼마나 고르게 만들 수 있는가」가 답을 정한다.
        """
        self.assertGreater(br_abrade.break_even_depth_mm(), br_abrade.BACKSHEET_T_MM)
        self.assertLess(br_abrade.break_even_depth_mm(), br_abrade.TARGET_DEPTH_MM)
        self.assertLess(br_abrade.depth_headroom_mm(), 0.0)
        self.assertGreater(br_abrade.depth_headroom_mm(), -0.1)
        self.assertFalse(br_abrade.pays_for_itself())

    def test_the_heat_credit_is_owned_by_sg_grind(self):
        """돌려받는 열은 `sg_grind` 가 정본이고 여기서 다시 안 센다."""
        self.assertAlmostEqual(br_abrade.downstream_heat_saved_j(),
                               sg_grind.downstream_heat_saved_j(), places=1)
        self.assertAlmostEqual(
            br_abrade.net_energy_j(),
            br_abrade.energy_per_panel_j() - br_abrade.downstream_heat_saved_j(),
            places=1)


class TestItMovesTheFluorineRatherThanRemovingIt(unittest.TestCase):
    """이 유닛의 결정 항목 — 없애는 것이 아니라 옮기는 것이다."""

    def test_the_dust_is_the_whole_backsheet_plus_the_overshoot(self):
        """분진이 백시트만이 아니다 — 더 판 만큼 EVA 도 함께 나온다."""
        self.assertAlmostEqual(
            br_abrade.swarf_kg_per_panel(),
            round(float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
                  * br_abrade.TARGET_DEPTH_MM * br_abrade.DENSITY_G_MM3 / 1_000.0, 2),
            places=2)
        self.assertGreater(br_abrade.swarf_kg_per_panel(),
                           sg_grind.backsheet_dust_kg_per_panel())
        self.assertAlmostEqual(
            br_abrade.swarf_kg_per_h(),
            round(br_abrade.swarf_kg_per_panel()
                  * handoff.downstream_rate().line_per_h, 1), places=1)

    def test_the_hood_flow_comes_from_duct_conveying_velocity(self):
        """풍량은 선언이 아니라 반송속도에서 나온다 — 느리면 덕트가 연료가 된다."""
        area = math.pi * (br_abrade.DUCT_D_MM / 2_000.0) ** 2
        want = area * br_abrade.DUCT_VELOCITY_M_S * 3_600.0 \
            * br_abrade.outlets_per_head() * br_abrade.HEADS
        self.assertEqual(br_abrade.hood_flow_m3h(), int(round(want)))
        self.assertGreaterEqual(br_abrade.DUCT_VELOCITY_M_S, 18.0)

    def test_it_does_not_fit_the_existing_collector(self):
        """지금 집진기에 못 얹는다 — 별도 계통이다."""
        self.assertFalse(br_abrade.fits_existing_collector())
        self.assertGreater(br_abrade.flow_ratio_to_existing(), 2.0)
        self.assertAlmostEqual(
            br_abrade.flow_ratio_to_existing(),
            round(br_abrade.hood_flow_m3h() / dust.counted_flow_m3h(), 2), places=2)

    def test_the_combustible_fraction_crosses_from_minority_to_majority(self):
        """가연분이 소수에서 다수로 넘어간다 — 집진기의 성격이 바뀐다."""
        self.assertLess(dust.combustible_flow_fraction(), 0.5)
        self.assertGreater(br_abrade.combustible_fraction_after(), 0.5)
        self.assertTrue(br_abrade.breaks_the_inert_premise())

    def test_the_decision_note_says_where_the_fluorine_went(self):
        """옮긴 곳을 글로 적어 둔다 — 값만 두면 다음 사람이 못 읽는다."""
        note = " ".join(br_abrade.what_it_moves())
        self.assertIn("HF", note)
        self.assertIn("집진", note)
        self.assertGreaterEqual(len(br_abrade.what_it_moves()), 4)
        self.assertGreaterEqual(len(br_abrade.open_questions()), 5)


class TestTheUnitDrawsItself(unittest.TestCase):
    """부품 — 위에서 정한 값이 부품표에 그대로 실린다."""

    def test_the_parts_carry_the_numbers_the_model_computed(self):
        """모터 정격·압반 조각 수·지관 수가 계산값과 같다."""
        parts = {p.key: p for p in br_abrade.unit().parts}
        self.assertEqual(parts["platen"].qty,
                         br_abrade.platen_segments() * br_abrade.HEADS)
        self.assertEqual(parts["duct"].qty,
                         br_abrade.outlets_per_head() * br_abrade.HEADS)
        self.assertEqual(parts["motor"].qty, br_abrade.HEADS)
        self.assertIn(f"{br_abrade.motor_rating_kw():.0f} kW", parts["motor"].spec)

    def test_the_principle_walks_the_panel_through(self):
        """작동원리가 물림에서 인계까지 끊기지 않는다."""
        steps = br_abrade.unit().principle
        self.assertGreaterEqual(len(steps), 6)
        self.assertIn("HF", " ".join(t for _, t in steps) + " ".join(
            br_abrade.what_it_moves()))
        self.assertIn(br_abrade.DOWNSTREAM_TAG, " ".join(t for _, t in steps))

    def test_the_summary_is_flat_and_complete(self):
        """요약이 도면 리터럴에 그대로 실릴 수 있는 모양인가."""
        s = br_abrade.summary()
        for key in ("feedMmS", "skinToDepthRatio", "breakEvenDepthMm",
                    "hoodFlowM3h", "combustibleFractionAfter", "partCount"):
            self.assertIn(key, s)
        for value in s.values():
            self.assertIsInstance(value, (int, float, bool, str, list))


if __name__ == "__main__":
    unittest.main()
