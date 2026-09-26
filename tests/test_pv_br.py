"""BR-305 백시트 면 연마 유닛 — 설계가 닫히는지, 그리고 **어디서 닫히다 마는지.**

이 유닛은 저장소에서 처음으로 「세울까 말까」 단계의 물건이다. 그래서 시험이
보는 것도 「값이 맞는가」만이 아니라 **「무엇이 이 결정을 가르는가」** 다.

**목적을 한 번 틀리게 잡았고 그 자리를 시험이 지킨다.** 처음에는 「불소를 열
앞에서 걷어 배가스의 HF 를 막는다」로 세워서, 하류 열박리 절감분을 이 유닛의
값으로 쳤다. 그러면 채택이 에너지 손익분기 0.02 mm 에서 갈리는 것처럼 보인다.
실제 목적은 **부유선별 먹이를 깨끗하게 만드는 것**이다. 불소 폴리머는 표면
에너지가 낮아 시약 없이도 떠서, 파쇄돼 선별조에 들어오면 화학으로 못 막고
정광 품위를 버린다. 목적이 그러면 판정이 둘 다 바뀐다 —

  · 에너지 장부는 **판정 기준이 아니다** (`TestTheLedgerIsNotTheCriterion`).
  · 잔존 백시트는 **0 이어야 한다.** 5 % 남는 것이 5 % 짜리 문제가 아니다
    (`TestTheRealSpecIsThatNoBacksheetSurvives`).

그리고 연마에는 되돌아오는 칼이 있다 — 백시트를 없애는 게 아니라 **더 고운
가루로 바꾼다.** 안 잡힌 가루는 자기가 대신한 필름보다 g 당 더 해롭다
(`TestTheFinesThatEscapeAreTheRisk`).

기계적 결론 셋은 목적이 바뀌어도 그대로다 — 깊이를 면에서 잡아야 하고, 열
판정이 δ/a < 1 이며, 헤드는 늘릴수록 나빠진다.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import br_abrade, campaign, dust, handoff, separation, sg_grind


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


class TestTheRealSpecIsThatNoBacksheetSurvives(unittest.TestCase):
    """진짜 사양 — 가장 얕게 깎이는 자리에서도 백시트가 안 남아야 한다.

    부유선별에서 잔존은 선형 문제가 아니다. 남은 조각이 파쇄되면 저절로 뜨는
    폴리머가 되어 정광에 올라오고, 시약으로는 못 막는다.
    """

    def test_the_minimum_depth_is_set_by_the_following_error(self):
        """최소 절입은 백시트 두께에 압반 추종 오차를 더한 값이다."""
        self.assertAlmostEqual(
            br_abrade.minimum_safe_depth_mm(),
            br_abrade.BACKSHEET_T_MM + br_abrade.PLATEN_FOLLOW_MM, places=3)
        self.assertGreater(br_abrade.TARGET_DEPTH_MM,
                           br_abrade.minimum_safe_depth_mm())
        self.assertGreater(br_abrade.depth_margin_over_minimum_mm(), 0.0)

    def test_the_tolerance_closes_on_both_sides(self):
        """얕은 쪽은 백시트를 다 걷고, 깊은 쪽은 셀에 안 닿는다."""
        self.assertTrue(br_abrade.no_backsheet_survives())
        self.assertTrue(br_abrade.no_cell_is_touched())
        self.assertTrue(br_abrade.tolerance_closes_both_ways())
        self.assertGreaterEqual(br_abrade.min_depth_cut_mm(),
                                br_abrade.BACKSHEET_T_MM)
        self.assertLessEqual(br_abrade.max_depth_cut_mm(),
                             br_abrade.depth_window_mm()[1])

    def test_a_worse_platen_breaks_the_spec_not_the_ledger(self):
        """압반이 나빠지면 깨지는 것은 장부가 아니라 **사양**이다.

        추종 오차가 커지면 최소 절입이 목표를 넘어서 백시트가 남는다.
        그때 고칠 것은 깊이가 아니라 압반이다.
        """
        f0 = br_abrade.PLATEN_FOLLOW_MM
        try:
            br_abrade.PLATEN_FOLLOW_MM = 0.20
            self.assertGreater(br_abrade.minimum_safe_depth_mm(),
                               br_abrade.TARGET_DEPTH_MM)
            self.assertFalse(br_abrade.no_backsheet_survives())
        finally:
            br_abrade.PLATEN_FOLLOW_MM = f0
        self.assertTrue(br_abrade.no_backsheet_survives())


class TestTheLedgerIsNotTheCriterion(unittest.TestCase):
    """에너지 장부 — 계산은 맞지만 이것으로 채택을 정하면 안 된다.

    한 번 이 장부로 결론을 냈다가 목적을 틀리게 잡은 것이 드러났다.
    그래서 계산은 남기되 **판정이 아니라는 것**을 시험이 못 박는다.
    """

    def test_the_break_even_depth_is_still_a_closed_form(self):
        """계산 자체는 맞다 — 하류 절감분을 면적과 비에너지로 나눈 값이다."""
        area = float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM)
        self.assertAlmostEqual(
            br_abrade.break_even_depth_mm(),
            round(br_abrade.downstream_heat_saved_j() / (area * br_abrade.ABRADE_J_MM3),
                  3), places=3)
        self.assertAlmostEqual(
            br_abrade.net_energy_j(),
            br_abrade.energy_per_panel_j() - br_abrade.downstream_heat_saved_j(),
            places=1)

    def test_the_energy_at_stake_is_pocket_change(self):
        """걸린 전기가 잔돈이다 — 이 값으로 결정이 날 수 없다는 뜻이다."""
        self.assertLess(abs(br_abrade.net_energy_j()) / 3.6e6, 0.5)

    def test_the_module_says_out_loud_that_this_is_not_the_criterion(self):
        """판정이 아니라는 것을 글로 적어 둔다 — 값만 두면 또 같은 실수를 한다."""
        note = " ".join(br_abrade.energy_ledger_is_not_the_criterion())
        self.assertIn("정광", note)
        self.assertNotIn("저절로 뜬다", note)
        self.assertGreaterEqual(len(br_abrade.energy_ledger_is_not_the_criterion()), 3)

    def test_the_heat_credit_is_owned_by_sg_grind(self):
        """돌려받는 열은 `sg_grind` 가 정본이고 여기서 다시 안 센다."""
        self.assertAlmostEqual(br_abrade.downstream_heat_saved_j(),
                               sg_grind.downstream_heat_saved_j(), places=1)


class TestTheFinesThatEscapeAreTheRisk(unittest.TestCase):
    """연마는 백시트를 없애는 게 아니라 **더 고운 가루로 바꾼다.**"""

    def test_mass_goes_down_by_two_orders(self):
        """질량으로는 크게 이긴다 — 그러나 그것만 보면 안 된다."""
        self.assertAlmostEqual(
            br_abrade.escaped_fines_g_per_panel(),
            round(br_abrade.swarf_kg_per_panel()
                  * (1.0 - br_abrade.DUST_CAPTURE) * 1_000.0, 1), places=1)
        self.assertLess(br_abrade.escaped_fines_g_per_panel(),
                        br_abrade.uncut_backsheet_g_per_panel())
        self.assertGreater(br_abrade.polymer_reduction_ratio(), 50.0)

    def test_the_capture_rate_is_a_quality_spec_that_inverts(self):
        """포집률은 벤더 카탈로그가 아니라 **선별 회로가 역산해 준다.**"""
        for target in (1.0, 5.0, 20.0):
            need = br_abrade.capture_needed_for(target)
            self.assertAlmostEqual(
                br_abrade.swarf_kg_per_panel() * 1_000.0 * (1.0 - need),
                target, places=1)
        self.assertGreater(br_abrade.capture_needed_for(1.0),
                           br_abrade.capture_needed_for(20.0))

    def test_a_deeper_cut_is_safer_on_residue_but_worse_on_fines(self):
        """더 파면 잔존은 안전해지고 미분은 늘어난다 — 이 둘이 맞선다.

        에너지 장부가 아니라 **이것이** 깊이를 정하는 자리다.
        """
        d0 = br_abrade.TARGET_DEPTH_MM
        fines0 = br_abrade.escaped_fines_g_per_panel()
        floor0 = br_abrade.min_depth_cut_mm()
        try:
            br_abrade.TARGET_DEPTH_MM = d0 + 0.20
            self.assertGreater(br_abrade.escaped_fines_g_per_panel(), fines0)
            self.assertGreater(br_abrade.min_depth_cut_mm(), floor0)
        finally:
            br_abrade.TARGET_DEPTH_MM = d0

    def test_the_note_explains_why_grams_alone_do_not_settle_it(self):
        """질량비만 보면 안 되는 이유를 글로 적어 둔다.

        그리고 **「미분이라 특별히 더 해롭다」는 말을 하지 않는다** — 급광이
        32~75 µm 라 전부가 미분이다. 안 잡힌 분진은 그냥 안 걷힌 백시트다.
        """
        note = " ".join(br_abrade.fines_that_escape_are_the_risk())
        self.assertIn("µm", note)
        self.assertIn("안 걷힌 백시트", note)
        self.assertIn("같은 창", note)

    def test_the_feed_window_comes_from_separation(self):
        """급광 창을 여기서 다시 정하지 않는다 — 실측이 `separation` 에 있다."""
        self.assertEqual(br_abrade.feed_window_um(), separation.feed_window_um())
        self.assertEqual(br_abrade.feed_window_um(), (32.0, 75.0))
        self.assertGreaterEqual(len(br_abrade.fines_that_escape_are_the_risk()), 4)


class TestItMovesThePolymerRatherThanRemovingIt(unittest.TestCase):
    """이 유닛의 결정 항목 — 폴리머를 선별조에서 집진기로 옮기는 것이다."""

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

    def test_the_eva_overshoot_is_fine_but_not_for_the_reason_first_written(self):
        """절입 여유는 괜찮다 — 다만 「방향이 반대라」가 아니다.

        EVA 가 가는 쪽에 **은정광**이 있다. 여유가 괜찮은 진짜 이유는
        더 판 EVA 가 **판 안에 원래 있던 것**이라 급광에 없던 EVA 를
        새로 만들지 않기 때문이다.
        """
        self.assertTrue(br_abrade.overshoot_into_eva_adds_nothing())
        self.assertTrue(br_abrade.eva_lands_on_the_silver())
        self.assertIn("eva", [c.key for c in separation.contaminates("silver")])

    def test_this_units_own_escape_lands_on_the_silicon(self):
        """이 유닛이 못 잡은 분진은 실리콘으로 간다 — 지키는 대상이 그쪽이다."""
        self.assertTrue(br_abrade.this_units_dust_lands_on_the_silicon())
        self.assertNotIn("eva", separation.gate_component_keys("backsheet"))

    def test_the_order_is_grind_then_peel(self):
        """**발주처 결정** — 연마가 백시트를, 칼날이 셀모듈을 맡는다."""
        note = " ".join(br_abrade.the_order_is_grind_then_peel())
        self.assertIn("연마", note)
        self.assertIn("유리를 타므로", note)
        self.assertIn("닿아서", note)
        self.assertIn("셀모듈", br_abrade.NEXT_UNIT)
        self.assertEqual(separation.gate_owner("backsheet"), "BR-305 (연마)")

    def test_the_two_units_are_sequential_not_competing(self):
        """경쟁 구도가 없어졌다 — 다만 **과거로는 남긴다.**

        「겨루는 대안」이라는 말 자체를 지우지는 않는다. 그것이 있었다는 사실이
        결정의 맥락이기 때문이다. 확인할 것은 **현재 시제로 경쟁을 주장하지
        않는가**다.
        """
        import inspect
        from pv_preprocess import br_peel
        src = inspect.getsource(br_abrade)
        self.assertIn("한때", src)                      # 과거로 적혀 있다
        self.assertIn("겨루는 대안**이었다", src)         # 현재형이 아니다
        self.assertIn("경쟁이 아니라 **순차**", src)
        self.assertFalse(br_peel.ADOPTED)
        self.assertGreaterEqual(len(br_peel.this_path_was_not_taken()), 4)

    def test_why_grinding_won_names_four_reasons(self):
        """이유 넷 — 기준면·되돌릴 수 있는 실패·약한 면 덫 없음·온도 충돌 없음."""
        rows = br_abrade.why_this_beats_peeling()
        self.assertEqual(len(rows), 4)
        note = " ".join(rows)
        self.assertIn("기준면이 기구 그 자체", note)
        self.assertIn("한 패스 더 돌리면 된다", note)
        self.assertIn("연마는 면을 고르지 않는다", note)
        self.assertIn("온도 충돌이 없다", note)

    def test_the_datum_margin_is_computed_not_asserted(self):
        """여유 비교가 `br_peel` 값을 받아 온다 — 베끼지 않는다."""
        from pv_preprocess import br_peel
        lo, hi = br_abrade.depth_window_mm()
        band = hi - lo
        self.assertGreater(band / br_abrade.PLATEN_FOLLOW_MM,
                           br_peel.depth_margin_ratio())
        self.assertAlmostEqual(band / br_abrade.PLATEN_FOLLOW_MM, 5.62, places=2)

    def test_the_gate_leak_narrows_but_still_lands_on_silicon(self):
        """누출이 200 배 좁아져도 **실리콘에 떨어진다** — 충분한지는 모른다."""
        self.assertAlmostEqual(br_abrade.the_gate_leak_narrows_by(), 200.0, places=1)
        self.assertTrue(br_abrade.the_leak_still_lands_on_the_silicon())
        note = " ".join(br_abrade.what_this_order_leaves_open())
        self.assertIn("충분한지 모른다", note)
        self.assertIn("실측인지 설계 목표인지 모른다", note)

    def test_the_glass_gate_owner_is_not_guessed(self):
        """칼날과 유리 관문 기존 주인의 관계는 **안 들었으므로 안 바꾼다.**"""
        self.assertEqual(separation.gate_owner("glass"), "GRM-401")
        self.assertIn("추측해서 바꾸지 않는다",
                      " ".join(br_abrade.what_this_order_leaves_open()))

    def test_this_unit_owns_exactly_one_of_the_four_gates(self):
        """이 유닛이 맡은 것은 넷 중 백시트 하나다."""
        self.assertEqual(br_abrade.gate_this_unit_owns(), "backsheet")
        self.assertIn(br_abrade.gate_this_unit_owns(), separation.THE_FOUR_GATES)
        self.assertEqual(separation.gate_owner("backsheet"), "BR-305 (연마)")

    def test_this_unit_defends_the_silicon_and_dg_defends_the_silver(self):
        """이 유닛은 실리콘을 지킨다 — 은은 EVA 관문(DG-HK60) 몫이다."""
        self.assertTrue(separation.reports_to_sink(separation.silicon()))
        self.assertTrue(separation.floats(separation.silver()))
        for key in separation.gate_component_keys("backsheet"):
            self.assertTrue(separation.reports_to_sink(separation.by_key(key)), key)
        self.assertEqual(separation.gate_owner("eva"), "DG-HK60")

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
