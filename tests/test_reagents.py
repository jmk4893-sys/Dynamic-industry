import unittest

from . import _path  # noqa: F401

from flotation_design.design_basis import REAGENTS
from flotation_design.reagents import Reagent, ReagentDose, reagent_schedule


class TestReagent(unittest.TestCase):
    def test_rejects_invalid_strength(self):
        with self.assertRaises(ValueError):
            Reagent("X", "role", 100.0, 0.0, 1.0, "CT-1")
        with self.assertRaises(ValueError):
            Reagent("X", "role", 100.0, 1.5, 1.0, "CT-1")

    def test_rejects_invalid_sg(self):
        with self.assertRaises(ValueError):
            Reagent("X", "role", 100.0, 0.1, 0.0, "CT-1")


class TestReagentDose(unittest.TestCase):
    def setUp(self):
        self.reagent = Reagent("PAX", "포수제", 120.0, 0.02, 1.0, "CT-2")

    def test_active_mass_scales_with_throughput(self):
        self.assertAlmostEqual(ReagentDose(self.reagent, 0.5).active_kg_h, 0.060, places=9)
        self.assertAlmostEqual(ReagentDose(self.reagent, 0.3).active_kg_h, 0.036, places=9)

    def test_solution_flow_accounts_for_strength_and_sg(self):
        self.assertAlmostEqual(ReagentDose(self.reagent, 0.5).solution_l_h, 3.0, places=9)

    def test_daily_consumption(self):
        self.assertAlmostEqual(
            ReagentDose(self.reagent, 0.5).active_kg_per_day, 0.060 * 24, places=9
        )

    def test_pump_rating_has_margin_and_floor(self):
        dose = ReagentDose(self.reagent, 0.5)
        self.assertAlmostEqual(dose.pump_rating_l_h(), 6.0, places=9)
        tiny = ReagentDose(Reagent("MIBC", "기포제", 0.3, 1.0, 1.0, "cell"), 0.5)
        self.assertGreaterEqual(tiny.pump_rating_l_h(), 1.0)


class TestSchedule(unittest.TestCase):
    WATER_M3H = 6.64  # 최대 처리량 · 7 wt% 기준

    def test_schedule_covers_every_reagent(self):
        sched = reagent_schedule(REAGENTS, 0.5, self.WATER_M3H)
        self.assertEqual(len(sched), len(REAGENTS))
        self.assertEqual([d.reagent.name for d in sched], [r.name for r in REAGENTS])

    def test_all_pump_flows_are_practically_dosable(self):
        for dose in reagent_schedule(REAGENTS, 0.3, self.WATER_M3H * 0.6):
            self.assertGreater(dose.solution_l_h, 0.1, dose.reagent.name)

    def test_solids_basis_scales_with_throughput(self):
        collector = next(r for r in REAGENTS if r.basis == "solids")
        low = ReagentDose(collector, 0.3, self.WATER_M3H)
        high = ReagentDose(collector, 0.5, self.WATER_M3H)
        self.assertAlmostEqual(high.active_kg_h / low.active_kg_h, 5 / 3, places=9)

    def test_water_basis_scales_with_water_not_solids(self):
        frother = next(r for r in REAGENTS if r.basis == "water")
        same_water = ReagentDose(frother, 0.9, self.WATER_M3H)
        base = ReagentDose(frother, 0.3, self.WATER_M3H)
        self.assertAlmostEqual(same_water.active_kg_h, base.active_kg_h, places=12)
        more_water = ReagentDose(frother, 0.3, self.WATER_M3H * 2)
        self.assertAlmostEqual(more_water.active_kg_h, base.active_kg_h * 2, places=12)

    def test_water_basis_equivalent_dose_falls_at_higher_solids(self):
        """고체 농도를 올리면 물이 줄어 t 당 기포제 소요량이 준다."""
        frother = next(r for r in REAGENTS if r.basis == "water")
        dilute = ReagentDose(frother, 0.5, 6.64)   # 7 wt%
        dense = ReagentDose(frother, 0.5, 1.17)    # 30 wt%
        self.assertLess(dense.equivalent_g_per_t, dilute.equivalent_g_per_t)


if __name__ == "__main__":
    unittest.main()
