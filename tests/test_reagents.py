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
    def test_schedule_covers_every_reagent(self):
        sched = reagent_schedule(REAGENTS, 0.5)
        self.assertEqual(len(sched), len(REAGENTS))
        self.assertEqual([d.reagent.name for d in sched], [r.name for r in REAGENTS])

    def test_all_pump_flows_are_practically_dosable(self):
        for dose in reagent_schedule(REAGENTS, 0.3):
            self.assertGreater(dose.solution_l_h, 0.1, dose.reagent.name)

    def test_staged_doses_sum_to_intended_totals(self):
        """러퍼·스캐빈저로 분할 투입해도 총 투입량은 설계값과 같아야 한다."""
        by_role: dict[str, float] = {}
        for dose in reagent_schedule(REAGENTS, 0.5):
            by_role[dose.reagent.role] = by_role.get(dose.reagent.role, 0.0) + dose.reagent.dose_g_per_t
        self.assertAlmostEqual(by_role["포수제 (주)"], 120.0, places=9)
        self.assertAlmostEqual(by_role["포수제 (보조)"], 40.0, places=9)
        self.assertAlmostEqual(by_role["기포제"], 30.0, places=9)
        self.assertAlmostEqual(by_role["황화제"], 350.0, places=9)

    def test_collector_is_split_between_rougher_and_scavenger(self):
        pax = [d for d in reagent_schedule(REAGENTS, 0.5) if d.reagent.name.startswith("PAX")]
        self.assertEqual(len(pax), 2)
        points = {d.reagent.addition_point for d in pax}
        self.assertEqual(points, {"CT-2", "FC-102 급광박스"})
        self.assertAlmostEqual(sum(d.active_kg_h for d in pax), 0.060, places=9)


if __name__ == "__main__":
    unittest.main()
