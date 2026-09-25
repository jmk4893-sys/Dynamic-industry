"""하류 선별 — **무엇이 어디로 가는가**, 그리고 왜 한 번 반대로 알았는가.

전처리 유닛 두 개가 이 표 하나에 걸려 있다. 그래서 이 묶음이 지키는 것은
값이 아니라 **기구**다 — 기구를 틀리면 유닛 둘이 같이 틀린다.

처음에는 「불소 폴리머는 표면에너지가 낮아 시약 없이 저절로 뜨므로 정광에
올라와 품위를 버린다」로 적었다. 현장은 반대다 — 백시트는 **가라앉고** EVA 는
**떠오른다.** 표면화학이 아니라 **밀도와 입도**가 정한다. 소수성이 맞아도
조각이 부상 상한보다 크면 기포가 못 들어 올린다.

그 정정이 유닛 쪽에서 무엇을 무너뜨렸는지도 여기서 붙든다 — PET 심재가 불소와
같은 행선지라 **백시트를 통째로** 빼야 하고, 그래서 「가장 약한 면에서 뜯으면
된다」가 성립하지 않는다.
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


class TestItLandsOnTheValuableFraction(unittest.TestCase):
    """가라앉는 곳이 하필 실리콘이 있는 쪽이다."""

    def test_silicon_is_in_the_sink_fraction(self):
        """지키려는 것이 침강분에 있다 — 시약 없이는 기포가 안 붙는다.

        실리콘이 가라앉는 이유는 백시트와 다르다. 백시트는 붙는데 커서
        떨어지고, 실리콘은 **애초에 안 붙는다.**
        """
        si = separation.silicon()
        self.assertTrue(si.is_product)
        self.assertFalse(si.naturally_hydrophobic)
        self.assertFalse(separation.can_be_lifted_by_bubbles(si))
        self.assertTrue(separation.reports_to_sink(si))
        self.assertGreater(si.density_g_cm3, separation.WATER_G_CM3)

    def test_the_polymers_that_sink_are_exactly_the_removal_spec(self):
        """전처리 사양이 「침강분으로 가는 불순물」에서 그대로 나온다."""
        self.assertEqual(
            set(separation.must_be_removed_before_crushing()),
            {c.key for c in separation.contaminates_silicon()})
        for c in separation.contaminates_silicon():
            self.assertFalse(c.is_product, c.key)
            self.assertTrue(separation.reports_to_sink(c), c.key)

    def test_what_separates_itself_is_left_alone(self):
        """스스로 갈라지는 불순물은 전처리가 손대지 않는다."""
        self.assertEqual([c.key for c in separation.separates_itself()], ["eva"])
        self.assertNotIn("eva", separation.must_be_removed_before_crushing())
        self.assertTrue(separation.eva_overshoot_is_harmless())


class TestItBreaksTheWeakPlaneShortcut(unittest.TestCase):
    """이 표가 「가장 약한 면에서 뜯으면 된다」를 무너뜨린다."""

    def test_the_pet_core_goes_where_the_fluoro_goes(self):
        """PET 심재와 불소가 같은 행선지라 외피만 벗기면 소용없다."""
        pet = next(c for c in separation.COMPONENTS if c.key == "pet")
        fluoro = next(c for c in separation.COMPONENTS if c.key == "fluoro")
        self.assertEqual(separation.reports_to_sink(pet),
                         separation.reports_to_sink(fluoro))
        self.assertTrue(separation.the_whole_backsheet_is_the_target())

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
        for key in ("contaminatesSilicon", "wholeBacksheetIsTheTarget",
                    "evaOvershootIsHarmless", "coarseLimitMm"):
            self.assertIn(key, s)
        for v in s.values():
            self.assertIsInstance(v, (int, float, bool, str, list))


if __name__ == "__main__":
    unittest.main()
