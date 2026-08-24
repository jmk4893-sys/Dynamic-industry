import unittest

from . import _path  # noqa: F401

from flotation_design.design_basis import FEED, FLOAT_MODELS
from flotation_design.kinetics import (
    FloatComponentModel,
    n_cells_in_series_recovery,
    perfect_mixer_recovery,
    simulate,
)


class TestPerfectMixerRecovery(unittest.TestCase):
    def test_zero_time_gives_zero_recovery(self):
        self.assertEqual(perfect_mixer_recovery(0.5, 0.0), 0.0)

    def test_asymptotes_to_r_max(self):
        self.assertAlmostEqual(perfect_mixer_recovery(0.5, 1e7, 0.88), 0.88, places=6)
        self.assertLess(perfect_mixer_recovery(0.5, 1e7, 0.88), 0.88)

    def test_known_value(self):
        # k*tau = 4.5 → 4.5/5.5 = 0.81818
        self.assertAlmostEqual(perfect_mixer_recovery(0.45, 10.0), 9.0 / 11.0, places=12)

    def test_monotonic_in_time(self):
        r = [perfect_mixer_recovery(0.45, t) for t in (1, 5, 10, 20)]
        self.assertEqual(r, sorted(r))

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            perfect_mixer_recovery(-1.0, 10.0)
        with self.assertRaises(ValueError):
            perfect_mixer_recovery(0.5, 10.0, r_max=1.5)


class TestCellsInSeries(unittest.TestCase):
    def test_single_cell_matches_perfect_mixer(self):
        self.assertAlmostEqual(
            n_cells_in_series_recovery(0.45, 9.9, 1, 0.88),
            perfect_mixer_recovery(0.45, 9.9, 0.88),
            places=12,
        )

    def test_splitting_volume_improves_recovery(self):
        one = n_cells_in_series_recovery(0.45, 9.9, 1, 0.88)
        two = n_cells_in_series_recovery(0.45, 9.9, 2, 0.88)
        three = n_cells_in_series_recovery(0.45, 9.9, 3, 0.88)
        self.assertLess(one, two)
        self.assertLess(two, three)
        self.assertLess(three, 0.88)

    def test_rejects_zero_cells(self):
        with self.assertRaises(ValueError):
            n_cells_in_series_recovery(0.45, 9.9, 0)


class TestFloatComponentModel(unittest.TestCase):
    def test_pure_entrainment_component(self):
        m = FloatComponentModel("Si", k_per_min=0.0, r_max=0.0, entrainment_factor=0.55)
        self.assertAlmostEqual(m.recovery(10.0, 0.12), 0.55 * 0.12, places=9)

    def test_recovery_never_exceeds_one(self):
        m = FloatComponentModel("X", k_per_min=10.0, r_max=1.0, entrainment_factor=1.0)
        self.assertLessEqual(m.recovery(60.0, 1.0), 1.0)

    def test_entrainment_only_applies_to_unfloated_fraction(self):
        m = FloatComponentModel("X", k_per_min=1.0, r_max=1.0, entrainment_factor=0.5)
        true_float = perfect_mixer_recovery(1.0, 10.0, 1.0)
        self.assertAlmostEqual(
            m.recovery(10.0, 0.2), true_float + (1 - true_float) * 0.5 * 0.2, places=12
        )


class TestSimulate(unittest.TestCase):
    def setUp(self):
        self.feed = FEED.component_tph(0.5)
        self.res = simulate(self.feed, FLOAT_MODELS, tau_min=9.9, water_recovery=0.12)

    def test_mass_balance_closes_per_component(self):
        for name, tph in self.feed.items():
            self.assertAlmostEqual(
                self.res.concentrate.component_tph[name]
                + self.res.tailings.component_tph[name],
                tph,
                places=12,
            )

    def test_total_mass_balance_closes(self):
        self.assertAlmostEqual(
            self.res.concentrate.dry_tph + self.res.tailings.dry_tph, 0.5, places=12
        )

    def test_grades_sum_to_unity(self):
        total = sum(
            self.res.concentrate.grade_fraction(n) for n in self.res.feed.component_tph
        )
        self.assertAlmostEqual(total, 1.0, places=12)

    def test_recoveries_bounded(self):
        for r in self.res.recovery.values():
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)

    def test_silver_is_upgraded_into_concentrate(self):
        self.assertGreater(self.res.enrichment_ratio("Ag"), 3.0)
        self.assertGreater(
            self.res.concentrate.grade_fraction("Ag"), self.res.feed.grade_fraction("Ag")
        )

    def test_peak_performance_targets(self):
        self.assertGreater(self.res.recovery["Ag"], 0.70)
        self.assertGreater(self.res.recovery["Cu"], 0.80)
        self.assertLess(self.res.mass_pull, 0.25)

    def test_longer_residence_improves_silver_recovery(self):
        slow = simulate(self.feed, FLOAT_MODELS, tau_min=16.5, water_recovery=0.12)
        self.assertGreater(slow.recovery["Ag"], self.res.recovery["Ag"])

    def test_separation_efficiency_positive(self):
        self.assertGreater(self.res.separation_efficiency("Ag"), 0.4)

    def test_missing_model_raises(self):
        with self.assertRaises(KeyError):
            simulate({"Au": 0.1}, FLOAT_MODELS, 10.0)

    def test_empty_stream_grade_is_zero(self):
        self.assertEqual(self.res.concentrate.grade_fraction("__none__"), 0.0)


if __name__ == "__main__":
    unittest.main()
