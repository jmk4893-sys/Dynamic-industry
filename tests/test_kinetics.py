import unittest

from . import _path  # noqa: F401

from flotation_design.design_basis import FEED, FLOAT_MODELS
from flotation_design.kinetics import (
    ComponentKinetics,
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
        # k*tau = 4.5 -> 4.5/5.5
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


class TestComponentKinetics(unittest.TestCase):
    def test_fractions_sum_to_one(self):
        k = FLOAT_MODELS["Ag"]
        self.assertAlmostEqual(sum(k.species_fractions), 1.0, places=12)

    def test_r_max_excludes_nonfloating(self):
        k = FLOAT_MODELS["Ag"]
        self.assertAlmostEqual(k.r_max, 0.88, places=12)
        self.assertAlmostEqual(k.nonfloating_fraction, 0.12, places=12)

    def test_true_flotation_is_sum_over_species(self):
        k = FLOAT_MODELS["Ag"]
        expected = 0.55 * perfect_mixer_recovery(1.20, 10.0) + 0.33 * perfect_mixer_recovery(
            0.12, 10.0
        )
        self.assertAlmostEqual(k.true_flotation_recovery(10.0), expected, places=12)

    def test_never_exceeds_r_max_without_entrainment(self):
        k = FLOAT_MODELS["Ag"]
        self.assertLess(k.true_flotation_recovery(1e6), k.r_max + 1e-9)
        self.assertAlmostEqual(k.true_flotation_recovery(1e7), k.r_max, places=5)

    def test_pure_entrainment_component(self):
        k = FLOAT_MODELS["Si"]
        self.assertEqual(k.r_max, 0.0)
        self.assertAlmostEqual(k.recovery(10.0, 0.12), 0.55 * 0.12, places=12)

    def test_slow_fraction_dominates_long_residence_gain(self):
        # 속부선은 빨리 포화하므로, 체류시간을 늘려 얻는 이득은 거의 전부
        # 지연부선에서 나온다 — 스캐빈저 설계의 근거.
        k = FLOAT_MODELS["Ag"]
        fast_gain = 0.55 * (
            perfect_mixer_recovery(1.20, 20.0) - perfect_mixer_recovery(1.20, 10.0)
        )
        slow_gain = 0.33 * (
            perfect_mixer_recovery(0.12, 20.0) - perfect_mixer_recovery(0.12, 10.0)
        )
        self.assertGreater(slow_gain, fast_gain * 2.5)

    def test_recovery_never_exceeds_one(self):
        k = ComponentKinetics("X", 0.9, 10.0, 0.1, 5.0, entrainment_factor=1.0)
        self.assertLessEqual(k.recovery(60.0, 1.0), 1.0)

    def test_rejects_fractions_over_one(self):
        with self.assertRaises(ValueError):
            ComponentKinetics("X", 0.7, 1.0, 0.5, 0.1)

    def test_rejects_negative_rate_constant(self):
        with self.assertRaises(ValueError):
            ComponentKinetics("X", 0.5, -1.0)

    def test_rejects_bad_entrainment_factor(self):
        with self.assertRaises(ValueError):
            ComponentKinetics("X", 0.5, 1.0, entrainment_factor=1.5)


class TestSimulate(unittest.TestCase):
    def setUp(self):
        self.feed = FEED.component_tph(0.5)
        self.res = simulate(self.feed, FLOAT_MODELS, tau_min=9.92, water_recovery=0.12)

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

    def test_rougher_only_baseline(self):
        self.assertAlmostEqual(self.res.recovery["Ag"], 0.707, delta=0.01)
        self.assertAlmostEqual(self.res.recovery["Cu"], 0.848, delta=0.01)

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
