"""부선 급광 — **실측 두 값 위에 서 있다.**

발주처 체 시험이 준 것 둘이 이 모듈의 뼈대다 — 급광 입도 **32~75 µm**, 그리고
구리가 **75 µm 아래에서 관측되지 않는다**(99.9 % 가 그 위). 두 번째가 구리
관문을 닫는다: 급광이 −75 µm 이므로 구리는 오버사이즈로 빠져 부선조에 애초에
안 들어온다. 관문을 닫는 것이 기계가 아니라 **분급**이다.

이 묶음이 지키는 것은 값이 아니라 **무엇이 관측이고 무엇이 추측인가**의 경계다.
거동을 밀도나 입도에서 유도하려다 두 번 틀렸기 때문이다 —

1. 「불소는 표면에너지가 낮아 **저절로 뜬다**」 → 현장은 반대.
2. 「**조각이 부상 상한보다 커서** 못 뜬다」 → 그때 조각을 5 mm 로 잡았는데
   실제 급광은 32~75 µm 로 부선 효율 영역 한가운데다. 전제가 67~156 배 틀렸다.

그래서 지금 표는 거동을 **관측으로만** 들고, 왜 백시트가 가라앉는지는
모른다고 적는다 (`TestItSaysWhatItDoesNotKnow`). 설계가 그 답에 안 걸리는
것도 같이 붙든다.
"""

from __future__ import annotations

import unittest

from tests import _path  # noqa: F401

from pv_preprocess import separation


class TestItStandsOnTheSieveData(unittest.TestCase):
    """실측 두 값이 모델의 뼈대다."""

    def test_the_feed_window_is_the_measured_one(self):
        """급광 창이 32~75 µm 다 — 이 회로가 실제로 쓰는 값."""
        lo, hi = separation.feed_window_um()
        self.assertAlmostEqual(lo, 32.0)
        self.assertAlmostEqual(hi, 75.0)
        self.assertLess(lo, hi)

    def test_the_window_sits_inside_the_efficient_band(self):
        """급광 창이 부선 효율 영역 안에 통째로 든다.

        그래서 **입도로는 침강을 설명할 수 없다** — 이것이 옛 설명을 깬 값이다.
        """
        lo, hi = separation.feed_window_um()
        elo, ehi = separation.FLOTATION_EFFICIENT_UM
        self.assertGreaterEqual(lo, elo)
        self.assertLessEqual(hi, ehi)

    def test_copper_does_not_go_below_the_screen(self):
        """구리는 체 시험에서 75 µm 아래로 안 내려간다 — 연성이라 눌려 펴진다."""
        cu = separation.by_key("copper")
        self.assertEqual(cu.behavior, "oversize")
        self.assertEqual(cu.evidence, "관측")
        self.assertGreaterEqual(cu.top_size_um, separation.feed_window_um()[1])
        self.assertLess(separation.COPPER_PASSING_FRACTION, 0.01)


class TestClassificationClosesTheCopperGate(unittest.TestCase):
    """구리 관문은 유닛이 아니라 분급이 닫는다."""

    def test_copper_never_enters_the_cell(self):
        """오버사이즈라 부선조에 안 들어온다."""
        cu = separation.by_key("copper")
        self.assertTrue(separation.is_screened_out(cu))
        self.assertFalse(separation.enters_the_cell(cu))
        self.assertTrue(separation.copper_is_closed_by_classification())

    def test_it_is_therefore_not_in_the_sink_contaminants(self):
        """들어오지도 않으니 침강분을 더럽힐 일이 없다."""
        self.assertNotIn("copper",
                         [c.key for c in separation.contaminates_the_sink_fraction()])
        self.assertIn("copper",
                      [c.key for c in separation.must_be_removed_before_flotation()])

    def test_all_four_gates_now_have_an_owner(self):
        """네 관문이 다 닫힌다 — 구리를 분급이 맡으면서 구멍이 없어졌다."""
        self.assertTrue(separation.all_four_gates_are_covered())
        self.assertEqual(separation.gates_without_an_owner(), ())
        self.assertIn("분급", separation.gate_owner("copper"))
        self.assertEqual(separation.gate_owner("glass"), "GRM-401")
        self.assertEqual(separation.gate_owner("eva"), "DG-HK60")
        self.assertEqual(separation.gate_owner("backsheet"), "BR-305/306")

    def test_an_owner_may_be_a_process_not_a_machine(self):
        """관문을 닫는 것이 꼭 유닛일 필요는 없다 — 그것이 구리의 교훈이다."""
        owners = {separation.gate_owner(g) for g in separation.THE_FOUR_GATES}
        self.assertTrue(all(owners))
        self.assertNotEqual(separation.gate_owner("copper"),
                            separation.gate_owner("backsheet"))


class TestValueAndFeedAreDifferentAxes(unittest.TestCase):
    """값이 나가는 것과 급광에 있어도 되는 것은 다른 축이다."""

    def test_only_silicon_and_silver_belong_in_the_feed(self):
        """급광에 있어야 하는 것은 둘뿐이다."""
        self.assertEqual([c.key for c in separation.feed_should_contain()],
                         ["silicon", "silver"])
        for c in separation.feed_should_contain():
            self.assertTrue(c.is_recovered, c.key)

    def test_glass_and_copper_are_valuable_yet_must_go(self):
        """유리·구리는 값이 나가는데도 급광 밖이다 — 두 축이 갈리는 자리."""
        self.assertEqual(
            sorted(c.key for c in separation.valuable_but_not_in_the_feed()),
            ["copper", "glass"])

    def test_the_removal_spec_partitions_the_table(self):
        """제거 사양이 「급광 적격이 아닌 것 전부」에서 나온다."""
        removed = {c.key for c in separation.must_be_removed_before_flotation()}
        kept = {c.key for c in separation.feed_should_contain()}
        self.assertEqual(removed | kept, {c.key for c in separation.COMPONENTS})
        self.assertEqual(removed & kept, set())

    def test_the_two_products_are_on_opposite_sides(self):
        """지키려는 둘이 서로 반대쪽에 있다 — 부선이 그 둘을 가르는 자리다."""
        self.assertTrue(separation.floats(separation.silver()))
        self.assertTrue(separation.reports_to_sink(separation.silicon()))
        self.assertEqual(separation.float_product().key, "silver")
        self.assertEqual(separation.sink_product().key, "silicon")


class TestEachProductHasItsOwnContaminant(unittest.TestCase):
    """제품마다 오염원이 다르다 — 「불순물」로 뭉뚱그리면 사라지는 구분이다."""

    def test_eva_lands_on_the_silver_not_the_other_way(self):
        """EVA 는 은정광으로 간다 — 한때 「방향이 반대라 덜 아프다」고 적었다."""
        self.assertTrue(separation.eva_lands_on_the_silver())
        self.assertEqual([c.key for c in separation.contaminates("silver")], ["eva"])

    def test_the_backsheet_and_glass_land_on_the_silicon(self):
        """백시트와 유리는 실리콘으로 간다."""
        self.assertEqual(
            {c.key for c in separation.contaminates("silicon")},
            {"glass", "pet", "fluoro"})
        self.assertEqual({c.key for c in separation.contaminates_the_sink_fraction()},
                         {c.key for c in separation.contaminates("silicon")})

    def test_the_two_contaminant_sets_do_not_overlap(self):
        """한 불순물이 두 제품을 동시에 더럽히지는 않는다."""
        ag = {c.key for c in separation.contaminates("silver")}
        si = {c.key for c in separation.contaminates("silicon")}
        self.assertEqual(ag & si, set())
        removed = {c.key for c in separation.must_be_removed_before_flotation()}
        self.assertEqual(ag | si | {"copper"}, removed)

    def test_the_float_side_amplifies_what_lands_on_it(self):
        """뜨는 쪽은 농축되는 작은 흐름이라 같은 g 이 더 아프다."""
        self.assertAlmostEqual(separation.float_side_is_amplified_by(),
                               separation.AG_UPGRADE_CONTINUOUS)
        self.assertGreater(separation.float_side_is_amplified_by(), 10.0)
        self.assertGreater(separation.AG_UPGRADE_CONTINUOUS,
                           separation.AG_UPGRADE_BATCH)
        self.assertGreater(separation.AG_RECOVERY_BATCH, 0.9)

    def test_the_collector_is_named_and_silver_selective(self):
        """포집제가 이름으로 적혀 있고, 그것이 은만 띄우는 근거로 쓰인다."""
        self.assertGreaterEqual(len(separation.AG_COLLECTORS), 2)
        note = " ".join(separation.why_the_backsheet_sinks_is_open())
        for c in separation.AG_COLLECTORS:
            self.assertIn(c, note)
        self.assertIn("선택적", note)
        self.assertIn("단정하지 않는다", note)


class TestItSaysWhatItDoesNotKnow(unittest.TestCase):
    """모르는 것을 모른다고 적는다 — 두 번 틀린 자리다."""

    def test_behaviour_is_recorded_not_derived(self):
        """거동이 관측 칸에 들어 있고, 추정은 추정이라고 적혀 있다."""
        for c in separation.COMPONENTS:
            self.assertIn(c.behavior, ("float", "sink", "oversize"), c.key)
            self.assertIn(c.evidence, ("관측", "추정"), c.key)
        observed = {c.key for c in separation.observed_components()}
        for key in ("eva", "pet", "fluoro", "copper"):
            self.assertIn(key, observed)

    def test_the_sinking_mechanism_is_left_open_with_candidates(self):
        """왜 가라앉는지 후보만 늘어놓고 고르지 않는다."""
        note = " ".join(separation.why_the_backsheet_sinks_is_open())
        self.assertIn("후보", note)
        self.assertIn("설계는 이 답에 안 걸린다", note)
        self.assertGreaterEqual(
            len(separation.why_the_backsheet_sinks_is_open()), 5)

    def test_the_two_dead_explanations_are_not_reasserted(self):
        """죽은 설명 둘을 되살리지 않는다."""
        note = " ".join(separation.why_the_backsheet_sinks_is_open())
        self.assertIn("입도로는 설명이 안 된다", note)
        self.assertIn("밀도로도 설명이 안 된다", note)

    def test_grinding_finer_is_settled_not_open(self):
        """「곱게 갈면 뜨지 않을까」는 열린 물음이 아니라 답이 나왔다."""
        note = " ".join(separation.grinding_finer_is_not_a_way_out())
        self.assertIn("급광은 전부가 미분", note)
        self.assertIn("안 걷힌 백시트", note)

    def test_the_conclusion_names_which_impurity_hits_which_product(self):
        """판단 기준이 관문이라는 것과, 제품마다 오염원이 다르다는 것을 적는다."""
        note = " ".join(separation.purity_depends_on_this())
        self.assertIn("은의 순도", note)
        self.assertIn("실리콘의 순도", note)
        self.assertIn("32~75 µm", note)
        self.assertIn("은정광", note)
        self.assertIn("EVA", note)

    def test_the_summary_is_flat_and_complete(self):
        """요약이 두 유닛과 도면이 함께 볼 수 있는 모양인가."""
        s = separation.summary()
        for key in ("feedWindowUm", "theFourGates", "gatesWithoutAnOwner",
                    "copperIsClosedByClassification", "screenedOut",
                    "floatProduct", "contaminatesSilver", "contaminatesSilicon"):
            self.assertIn(key, s)
        for v in s.values():
            self.assertIsInstance(v, (int, float, bool, str, list, dict))


if __name__ == "__main__":
    unittest.main()
