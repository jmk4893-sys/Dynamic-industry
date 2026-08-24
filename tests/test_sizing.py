import math
import unittest

from . import _path  # noqa: F401

from flotation_design.feed import pulp_at
from flotation_design.design_basis import FEED
from flotation_design.sizing import (
    aeration_design,
    cell_geometry,
    froth_loading,
    impeller_design,
    required_slurry_volume,
    residence_time,
    rounded_cell,
    select_motor_kw,
)


class TestRequiredVolume(unittest.TestCase):
    def test_volume_is_flow_times_time(self):
        self.assertAlmostEqual(required_slurry_volume(1.699, 10.0), 1.699 / 6.0, places=9)

    def test_scale_up_factor_applies(self):
        base = required_slurry_volume(1.699, 10.0)
        self.assertAlmostEqual(required_slurry_volume(1.699, 10.0, 2.0), base * 2.0, places=9)

    def test_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            required_slurry_volume(0.0, 10.0)
        with self.assertRaises(ValueError):
            required_slurry_volume(1.0, -1.0)


class TestCellGeometry(unittest.TestCase):
    def setUp(self):
        self.required = required_slurry_volume(1.699, 10.0)
        self.geom = cell_geometry(
            self.required, gas_holdup=0.15, froth_depth_m=0.075,
            freeboard_m=0.06, height_to_width=1.15,
        )

    def test_solved_geometry_reproduces_required_slurry_volume(self):
        self.assertAlmostEqual(
            self.geom.effective_slurry_volume_m3, self.required, places=9
        )

    def test_height_to_width_ratio_honoured(self):
        self.assertAlmostEqual(
            self.geom.shell_height_m / self.geom.width_m, 1.15, places=9
        )

    def test_freeboard_is_shell_minus_lip(self):
        self.assertAlmostEqual(
            self.geom.shell_height_m - self.geom.lip_height_m, 0.06, places=9
        )

    def test_volumes_are_ordered(self):
        g = self.geom
        self.assertGreater(g.shell_volume_m3, g.volume_to_lip_m3)
        self.assertGreater(g.volume_to_lip_m3, g.pulp_zone_volume_m3)
        self.assertGreater(g.pulp_zone_volume_m3, g.effective_slurry_volume_m3)

    def test_rejects_invalid_gas_holdup(self):
        with self.assertRaises(ValueError):
            cell_geometry(0.3, gas_holdup=1.0)

    def test_rounded_cell_keeps_freeboard_and_froth(self):
        r = rounded_cell(self.geom, 0.70, 0.81)
        self.assertAlmostEqual(r.width_m, 0.70)
        self.assertAlmostEqual(r.shell_height_m - r.lip_height_m, 0.06, places=9)
        self.assertAlmostEqual(r.froth_depth_m, self.geom.froth_depth_m)
        self.assertAlmostEqual(r.cross_section_m2, 0.49, places=9)


class TestResidenceTime(unittest.TestCase):
    def setUp(self):
        self.geom = rounded_cell(
            cell_geometry(required_slurry_volume(1.699, 10.0)), 0.70, 0.81
        )

    def test_peak_residence_near_design_target(self):
        tau = residence_time(self.geom, pulp_at(FEED, 0.5).volumetric_flow_m3h).residence_min
        self.assertAlmostEqual(tau, 9.9, delta=0.2)

    def test_average_residence_is_longer_than_peak(self):
        tau_avg = residence_time(self.geom, pulp_at(FEED, 0.3).volumetric_flow_m3h).residence_min
        tau_peak = residence_time(self.geom, pulp_at(FEED, 0.5).volumetric_flow_m3h).residence_min
        self.assertGreater(tau_avg, tau_peak)
        self.assertAlmostEqual(tau_avg / tau_peak, 5.0 / 3.0, places=6)


class TestMotorSelection(unittest.TestCase):
    def test_picks_next_standard_rating(self):
        self.assertEqual(select_motor_kw(1000.0, 1.4), 1.5)
        self.assertEqual(select_motor_kw(1550.0, 1.4), 2.2)

    def test_raises_beyond_series(self):
        with self.assertRaises(ValueError):
            select_motor_kw(100_000.0)


class TestImpeller(unittest.TestCase):
    def setUp(self):
        self.geom = rounded_cell(
            cell_geometry(required_slurry_volume(1.699, 10.0)), 0.70, 0.81
        )
        self.pulp = pulp_at(FEED, 0.5)
        self.imp = impeller_design(self.geom, self.pulp.pulp_density_kg_m3)

    def test_diameter_ratio(self):
        self.assertAlmostEqual(self.imp.diameter_m, 0.24, places=9)

    def test_tip_speed_matches_rounded_speed(self):
        expected = math.pi * self.imp.diameter_m * self.imp.speed_rpm / 60.0
        self.assertAlmostEqual(self.imp.tip_speed_m_s, expected, places=9)
        self.assertAlmostEqual(self.imp.tip_speed_m_s, 5.5, delta=0.15)

    def test_power_follows_np_rho_n3_d5(self):
        n = self.imp.speed_rpm / 60.0
        expected = 4.2 * self.pulp.pulp_density_kg_m3 * n**3 * self.imp.diameter_m**5
        self.assertAlmostEqual(self.imp.ungassed_power_w, expected, places=6)

    def test_gassed_power_is_reduced(self):
        self.assertLess(self.imp.gassed_power_w, self.imp.ungassed_power_w)
        self.assertAlmostEqual(
            self.imp.gassed_power_w / self.imp.ungassed_power_w, 0.70, places=9
        )

    def test_motor_covers_ungassed_shaft_power(self):
        self.assertGreaterEqual(
            self.imp.motor_rating_kw, self.imp.ungassed_power_w / 1000.0
        )
        self.assertEqual(self.imp.motor_rating_kw, 2.2)

    def test_specific_power_in_small_cell_range(self):
        self.assertGreater(self.imp.specific_power_kw_m3, 2.0)
        self.assertLess(self.imp.specific_power_kw_m3, 6.0)


class TestAeration(unittest.TestCase):
    def setUp(self):
        self.geom = rounded_cell(
            cell_geometry(required_slurry_volume(1.699, 10.0)), 0.70, 0.81
        )
        pulp = pulp_at(FEED, 0.5)
        self.aer = aeration_design(
            self.geom, pulp.pulp_density_kg_m3, sparger_clearance_m=0.144
        )

    def test_air_flow_from_superficial_velocity(self):
        expected = 0.01 * self.geom.cross_section_m2 * 3600.0
        self.assertAlmostEqual(self.aer.air_flow_m3h, expected, places=9)
        self.assertAlmostEqual(self.aer.air_flow_m3h, 17.64, places=2)

    def test_bubble_surface_area_flux_in_target_band(self):
        self.assertAlmostEqual(self.aer.bubble_surface_area_flux_1_s, 50.0, places=6)
        self.assertGreaterEqual(self.aer.bubble_surface_area_flux_1_s, 40.0)
        self.assertLessEqual(self.aer.bubble_surface_area_flux_1_s, 70.0)

    def test_control_range_brackets_design_point(self):
        self.assertLess(self.aer.air_flow_min_m3h, self.aer.air_flow_m3h)
        self.assertGreater(self.aer.air_flow_max_m3h, self.aer.air_flow_m3h)

    def test_selection_pressure_has_margin(self):
        self.assertGreater(self.aer.selection_pressure_kpa, self.aer.total_pressure_kpa)

    def test_rejects_sparger_above_pulp_level(self):
        with self.assertRaises(ValueError):
            aeration_design(self.geom, 1177.0, sparger_clearance_m=2.0)


class TestFrothLoading(unittest.TestCase):
    def test_within_limits_at_peak(self):
        geom = rounded_cell(cell_geometry(required_slurry_volume(1.699, 10.0)), 0.70, 0.81)
        fl = froth_loading(geom, concentrate_tph=0.085)
        self.assertTrue(fl.carry_rate_ok)
        self.assertTrue(fl.lip_loading_ok)
        self.assertAlmostEqual(fl.lip_length_m, 1.4, places=9)
        self.assertAlmostEqual(fl.carry_rate_tph_m2, 0.085 / 0.49, places=9)

    def test_flags_overload(self):
        geom = rounded_cell(cell_geometry(required_slurry_volume(1.699, 10.0)), 0.70, 0.81)
        fl = froth_loading(geom, concentrate_tph=5.0)
        self.assertFalse(fl.carry_rate_ok)
        self.assertFalse(fl.lip_loading_ok)


if __name__ == "__main__":
    unittest.main()
