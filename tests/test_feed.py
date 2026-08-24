import unittest

from . import _path  # noqa: F401

from flotation_design.feed import Component, FeedSpec, pulp_at
from flotation_design.design_basis import FEED


class TestComponent(unittest.TestCase):
    def test_rejects_out_of_range_fraction(self):
        with self.assertRaises(ValueError):
            Component("X", 1.5, 2.0)

    def test_rejects_non_positive_sg(self):
        with self.assertRaises(ValueError):
            Component("X", 0.5, 0.0)


class TestFeedSpec(unittest.TestCase):
    def test_rejects_composition_not_summing_to_one(self):
        with self.assertRaises(ValueError):
            FeedSpec(
                components=(Component("A", 0.5, 2.0), Component("B", 0.3, 3.0)),
                average_tph=0.3,
                peak_tph=0.5,
                solids_mass_fraction=0.25,
                p80_micron=75.0,
            )

    def test_rejects_peak_below_average(self):
        with self.assertRaises(ValueError):
            FeedSpec(
                components=(Component("A", 1.0, 2.5),),
                average_tph=0.5,
                peak_tph=0.3,
                solids_mass_fraction=0.25,
                p80_micron=75.0,
            )

    def test_solids_sg_is_volume_weighted_harmonic_mean(self):
        feed = FeedSpec(
            components=(Component("A", 0.5, 2.0), Component("B", 0.5, 4.0)),
            average_tph=0.3,
            peak_tph=0.5,
            solids_mass_fraction=0.25,
            p80_micron=75.0,
        )
        # 1 / (0.5/2 + 0.5/4) = 2.6667  (산술평균 3.0 이 아님)
        self.assertAlmostEqual(feed.solids_specific_gravity, 8.0 / 3.0, places=9)

    def test_design_basis_solids_sg(self):
        self.assertAlmostEqual(FEED.solids_specific_gravity, 2.511, places=3)

    def test_component_tph_splits_feed(self):
        parts = FEED.component_tph(0.5)
        self.assertAlmostEqual(sum(parts.values()), 0.5, places=12)
        self.assertAlmostEqual(parts["Ag"], 0.5 * 0.0045, places=12)

    def test_grade_ppm(self):
        self.assertAlmostEqual(FEED.grade_ppm("Ag"), 4500.0, places=6)
        with self.assertRaises(KeyError):
            FEED.grade_ppm("Au")


class TestPulpProperties(unittest.TestCase):
    def setUp(self):
        self.pulp = pulp_at(FEED, 0.5)

    def test_water_and_slurry_mass(self):
        # 25 wt% 고체 → 고체 1 에 물 3
        self.assertAlmostEqual(self.pulp.water_tph, 1.5, places=9)
        self.assertAlmostEqual(self.pulp.slurry_tph, 2.0, places=9)

    def test_volumetric_flow(self):
        expected = 0.5 / FEED.solids_specific_gravity + 1.5
        self.assertAlmostEqual(self.pulp.volumetric_flow_m3h, expected, places=9)
        self.assertAlmostEqual(self.pulp.volumetric_flow_m3h, 1.699, places=3)

    def test_pulp_sg_between_water_and_solids(self):
        self.assertGreater(self.pulp.pulp_specific_gravity, 1.0)
        self.assertLess(self.pulp.pulp_specific_gravity, FEED.solids_specific_gravity)
        self.assertAlmostEqual(self.pulp.pulp_specific_gravity, 1.177, places=3)

    def test_solids_volume_fraction_consistent_with_flows(self):
        expected = (0.5 / FEED.solids_specific_gravity) / self.pulp.volumetric_flow_m3h
        self.assertAlmostEqual(self.pulp.solids_volume_fraction, expected, places=9)


if __name__ == "__main__":
    unittest.main()
