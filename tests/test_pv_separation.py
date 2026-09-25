"""부선 급광 — **실리콘과 은만 들어가야 한다.**

전처리 라인 전체가 무엇을 위해 있는지가 이 표 하나에 걸려 있다. 발주처
최종 결론이 「부선 전에 유리·구리·EVA·백시트가 다 제거되는 것이 최상의
결과를 내고, 그것이 은과 실리콘 순도의 가장 큰 변수」이므로, 판단 기준이
유닛별 에너지가 아니라 **관문이 닫혔는가**다.

이 묶음이 지키는 것은 값이 아니라 **기구와 축**이다. 둘 다 한 번씩 틀렸다.

1. **기구** — 「불소는 표면에너지가 낮아 저절로 뜬다」고 적었는데 현장은
   반대다. 입도 영역을 잘못 봤다: 부상 상한이 1 mm 남짓이라 파쇄 조각은
   소수성이어도 기포에서 떨어진다 (`TestTwoDifferentReasonsForTwoDirections`).
2. **축** — 그 정정을 「백시트만 걷으면 된다」로 좁게 읽고 유리를 **제품**
   칸에 두었다. 회수 가치와 급광 적격은 다른 축이다. 유리·구리는 값이
   나가지만 급광 밖이다 (`TestValueAndFeedAreDifferentAxes`).
"""

from __future__ import annotations

import unittest

from tests import _path  # noqa: F401

from pv_preprocess import separation


class TestTwoDifferentReasonsForTwoDirections(unittest.TestCase):
    """EVA 와 백시트가 갈리는 이유가 서로 다르다."""

    def test_eva_floats_on_density_alone(self):
        """EVA 는 기포도 시약도 없이 뜬다 — 물보다 가볍다."""
        eva = next(c for c in separation.COMPONENTS if c.key == "eva")
        self.assertLess(eva.density_g_cm3, separation.WATER_G_CM3)
        self.assertTrue(separation.floats_by_buoyancy(eva))
        self.assertFalse(separation.reports_to_sink(eva))

    def test_the_backsheet_sinks_although_it_is_hydrophobic(self):
        """백시트는 소수성인데도 가라앉는다 — 밀도와 크기가 이긴다."""
        for key in ("pet", "fluoro"):
            c = next(x for x in separation.COMPONENTS if x.key == key)
            self.assertGreater(c.density_g_cm3, separation.WATER_G_CM3, key)
            self.assertFalse(separation.floats_by_buoyancy(c), key)
            self.assertTrue(separation.too_coarse_to_float(c), key)
            self.assertTrue(separation.reports_to_sink(c), key)

    def test_size_is_what_defeats_the_surface_chemistry(self):
        """표면화학이 맞아도 입도가 틀리면 안 뜬다 — 그 경계를 값으로 든다."""
        self.assertGreater(separation.SHRED_SIZE_MM,
                           separation.FLOTATION_COARSE_LIMIT_MM)
        lo, hi = separation.FLOTATION_EFFICIENT_UM
        self.assertLess(lo, hi)
        self.assertLess(hi / 1_000.0, separation.FLOTATION_COARSE_LIMIT_MM)

    def test_finer_shreds_would_change_the_answer(self):
        """조각이 상한 아래로 내려가면 결론이 바뀐다 — 그래서 크기가 상수다."""
        s0 = separation.SHRED_SIZE_MM
        try:
            separation.SHRED_SIZE_MM = 0.5
            fluoro = next(c for c in separation.COMPONENTS if c.key == "fluoro")
            probe = type(fluoro)(**{**fluoro.__dict__, "size_mm": 0.5})
            self.assertFalse(separation.too_coarse_to_float(probe))
            self.assertTrue(separation.can_be_lifted_by_bubbles(probe))
            self.assertFalse(separation.reports_to_sink(probe))
        finally:
            separation.SHRED_SIZE_MM = s0


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
        keys = [c.key for c in separation.valuable_but_not_in_the_feed()]
        self.assertEqual(sorted(keys), ["copper", "glass"])
        for c in separation.valuable_but_not_in_the_feed():
            self.assertTrue(c.is_recovered, c.key)
            self.assertFalse(c.belongs_in_feed, c.key)

    def test_the_removal_spec_is_everything_that_is_not_the_two_products(self):
        """제거 사양이 「급광 적격이 아닌 것 전부」에서 나온다."""
        removed = {c.key for c in separation.must_be_removed_before_flotation()}
        kept = {c.key for c in separation.feed_should_contain()}
        self.assertEqual(removed | kept, {c.key for c in separation.COMPONENTS})
        self.assertEqual(removed & kept, set())
        self.assertEqual(removed, {"glass", "copper", "eva", "pet", "fluoro"})

    def test_silicon_and_silver_are_both_in_the_sink_fraction(self):
        """지키려는 둘이 다 침강분에 있다 — 거기로 오는 것이 제일 나쁘다."""
        for c in (separation.silicon(), separation.silver()):
            self.assertTrue(separation.reports_to_sink(c), c.key)
            self.assertFalse(c.naturally_hydrophobic, c.key)
        self.assertGreater(separation.silver().density_g_cm3,
                           separation.silicon().density_g_cm3)

    def test_what_lands_on_them_is_named(self):
        """그 침강분에 섞이는 것들을 값으로 든다."""
        sinkers = {c.key for c in separation.contaminates_the_sink_fraction()}
        self.assertIn("pet", sinkers)
        self.assertIn("fluoro", sinkers)
        self.assertIn("glass", sinkers)
        self.assertIn("copper", sinkers)
        self.assertNotIn("eva", sinkers)


class TestTheFourGates(unittest.TestCase):
    """관문 넷 — 닫힌 것과 빈 것을 세운다."""

    def test_there_are_exactly_four(self):
        """발주처가 정한 넷이다."""
        self.assertEqual(separation.THE_FOUR_GATES,
                         ("glass", "copper", "eva", "backsheet"))

    def test_every_gate_maps_to_components_in_the_table(self):
        """관문마다 표의 성분으로 내려간다 — 이름만 있는 관문은 없다."""
        covered = set()
        for g in separation.THE_FOUR_GATES:
            keys = separation.gate_component_keys(g)
            self.assertTrue(keys, g)
            covered |= keys
        self.assertEqual(
            covered, {c.key for c in separation.must_be_removed_before_flotation()})

    def test_the_backsheet_gate_is_two_components_not_one(self):
        """백시트 관문은 불소층과 PET 둘이다 — 외피만 걷으면 안 닫힌다."""
        self.assertEqual(separation.gate_component_keys("backsheet"),
                         frozenset({"pet", "fluoro"}))

    def test_copper_has_no_unit_and_that_is_reported(self):
        """구리 관문이 비어 있다 — 설계 구멍이고 숨기지 않는다."""
        self.assertIn("copper", separation.gates_without_a_unit())
        self.assertEqual(separation.gate_owner("copper"), "")
        self.assertFalse(separation.all_four_gates_are_covered())

    def test_the_other_three_name_their_unit(self):
        """나머지 셋은 맡는 유닛이 있다."""
        self.assertEqual(separation.gate_owner("glass"), "GRM-401")
        self.assertEqual(separation.gate_owner("eva"), "DG-HK60")
        self.assertEqual(separation.gate_owner("backsheet"), "BR-305/306")

    def test_the_conclusion_is_written_down_as_the_criterion(self):
        """판단 기준이 에너지가 아니라 관문이라는 것을 글로 적어 둔다."""
        note = " ".join(separation.purity_depends_on_this())
        self.assertIn("은의 순도", note)
        self.assertIn("실리콘의 순도", note)
        self.assertIn("copper", note)
        self.assertGreaterEqual(len(separation.purity_depends_on_this()), 4)


class TestItBreaksTheWeakPlaneShortcut(unittest.TestCase):
    """이 표가 「가장 약한 면에서 뜯으면 된다」를 무너뜨린다."""

    def test_the_pet_core_goes_where_the_fluoro_goes(self):
        """PET 심재와 불소가 같은 행선지라 외피만 벗기면 소용없다."""
        pet, fluoro = separation.by_key("pet"), separation.by_key("fluoro")
        self.assertEqual(separation.reports_to_sink(pet),
                         separation.reports_to_sink(fluoro))
        self.assertEqual(separation.gate_component_keys("backsheet"),
                         frozenset({"pet", "fluoro"}))

    def test_the_open_question_about_fines_is_written_down_not_built_on(self):
        """곱게 갈면 뜰 수도 있다는 물음을 적되, 그 위에 설계를 안 세운다."""
        note = " ".join(separation.would_fines_float_instead())
        self.assertIn("파쇄 전에 걷어내면", note)
        self.assertGreaterEqual(len(separation.would_fines_float_instead()), 4)

    def test_the_reversal_is_recorded_so_it_is_not_repeated(self):
        """반대로 알았던 이유를 남긴다 — 값만 두면 다음 사람이 또 틀린다."""
        note = " ".join(separation.why_it_sinks_although_it_is_hydrophobic())
        self.assertIn("입도", note)
        self.assertIn("µm", note)
        self.assertGreaterEqual(
            len(separation.why_it_sinks_although_it_is_hydrophobic()), 4)

    def test_the_summary_is_flat_and_complete(self):
        """요약이 두 유닛과 도면이 함께 볼 수 있는 모양인가."""
        s = separation.summary()
        for key in ("feedShouldContain", "theFourGates", "gatesWithoutAUnit",
                    "allFourGatesAreCovered", "coarseLimitMm"):
            self.assertIn(key, s)
        for v in s.values():
            self.assertIsInstance(v, (int, float, bool, str, list, dict))


if __name__ == "__main__":
    unittest.main()
