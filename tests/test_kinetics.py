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
        self.assertAlmostEqual(k.r_max, k.fast_fraction + k.slow_fraction, places=12)
        self.assertAlmostEqual(k.nonfloating_fraction, 1.0 - k.r_max, places=12)
        self.assertAlmostEqual(k.r_max, 0.976, places=12)

    def test_true_flotation_is_sum_over_species(self):
        k = FLOAT_MODELS["Ag"]
        expected = k.fast_fraction * perfect_mixer_recovery(
            k.k_fast, 10.0
        ) + k.slow_fraction * perfect_mixer_recovery(k.k_slow, 10.0)
        self.assertAlmostEqual(k.true_flotation_recovery(10.0), expected, places=12)

    def test_scale_factor_slows_the_plant(self):
        k = FLOAT_MODELS["Ag"]
        self.assertLess(k.true_flotation_recovery(6.0, 0.8), k.true_flotation_recovery(6.0, 1.0))

    def test_never_exceeds_r_max_without_entrainment(self):
        k = FLOAT_MODELS["Ag"]
        self.assertLess(k.true_flotation_recovery(1e6), k.r_max + 1e-9)
        self.assertAlmostEqual(k.true_flotation_recovery(1e7), k.r_max, places=5)

    def test_pure_entrainment_component(self):
        k = FLOAT_MODELS["Si"]
        self.assertEqual(k.r_max, 0.0)
        self.assertAlmostEqual(k.recovery(10.0, 0.12), k.entrainment_factor * 0.12, places=12)

    def test_late_recovery_gain_comes_disproportionately_from_slow_fraction(self):
        """속부선은 빨리 포화하므로, 체류시간을 늘려 얻는 이득은 질량 비중에
        비해 지연부선 쪽이 훨씬 크다. 체류시간을 늘릴지 판단하는 근거다."""
        k = FLOAT_MODELS["Ag"]
        fast_gain = k.fast_fraction * (
            perfect_mixer_recovery(k.k_fast, 20.0) - perfect_mixer_recovery(k.k_fast, 10.0)
        )
        slow_gain = k.slow_fraction * (
            perfect_mixer_recovery(k.k_slow, 20.0) - perfect_mixer_recovery(k.k_slow, 10.0)
        )
        mass_share = k.slow_fraction / k.r_max
        gain_share = slow_gain / (slow_gain + fast_gain)
        self.assertLess(mass_share, 0.20)
        self.assertGreater(gain_share, 0.45)

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
        # 신급광을 받는 단일 CSTR 러퍼 — 회분식보다 낮아야 한다.
        self.assertGreater(self.res.recovery["Ag"], 0.85)
        self.assertLess(self.res.recovery["Ag"], 0.976)

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
