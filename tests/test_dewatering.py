"""필터프레스 사이징과 중공축 급기 검증."""

import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design.dewatering import STANDARD_PLATE_MM, FilterPress, filter_press
from flotation_design.plant import build_plant
from flotation_design.sizing import hollow_shaft

SG = 2.374


class TestFilterPress(unittest.TestCase):
    def setUp(self):
        self.conc = filter_press("FL-X", "정광", 0.0065, 0.40, SG,
                                 cake_moisture=0.18, cycle_min=480.0)
        self.tail = filter_press("FL-Y", "미광", 0.494, 0.45, SG,
                                 cake_moisture=0.22, specific_rate_kg_m2_h=25.0,
                                 cycle_min=120.0, min_plate_mm=800.0)

    def test_uses_standard_plate_sizes(self):
        for f in (self.conc, self.tail):
            self.assertIn(f.plate_mm, STANDARD_PLATE_MM)

    def test_chamber_holds_one_cycle_of_cake(self):
        for f in (self.conc, self.tail):
            self.assertGreaterEqual(f.chamber_volume_m3, f.cake_volume_per_cycle_m3)
            self.assertLessEqual(f.chamber_utilisation, 1.0)

    def test_cake_mass_balance(self):
        for f in (self.conc, self.tail):
            self.assertAlmostEqual(f.cake_tph * (1 - f.cake_moisture), f.dry_tph, places=12)
            self.assertAlmostEqual(f.cake_water_tph, f.cake_tph - f.dry_tph, places=12)

    def test_filtrate_is_feed_water_minus_cake_water(self):
        for f in (self.conc, self.tail):
            self.assertAlmostEqual(
                f.filtrate_m3h, f.feed_water_tph - f.cake_water_tph, places=12
            )
            self.assertGreater(f.filtrate_m3h, 0.0)

    def test_drier_cake_leaves_more_filtrate(self):
        wet = filter_press("A", "d", 0.494, 0.45, SG, cake_moisture=0.30,
                           specific_rate_kg_m2_h=25.0, min_plate_mm=800.0)
        dry = filter_press("B", "d", 0.494, 0.45, SG, cake_moisture=0.15,
                           specific_rate_kg_m2_h=25.0, min_plate_mm=800.0)
        self.assertGreater(dry.filtrate_m3h, wet.filtrate_m3h)

    def test_cake_bulk_density_between_water_and_solids(self):
        for f in (self.conc, self.tail):
            self.assertGreater(f.cake_bulk_density_t_m3, 1.0)
            self.assertLess(f.cake_bulk_density_t_m3, SG)

    def test_small_duty_is_governed_by_minimum_machine(self):
        """정광은 양이 적어 상용 최소 기종이 규격을 정한다."""
        self.assertEqual(self.conc.governed_by, "상용 최소 기종")

    def test_large_duty_needs_a_real_press(self):
        self.assertGreater(self.tail.filter_area_m2, 20.0)
        self.assertGreater(self.tail.chambers, 20)

    def test_area_scales_with_throughput(self):
        big = filter_press("C", "d", 1.0, 0.45, SG, specific_rate_kg_m2_h=25.0,
                           min_plate_mm=800.0)
        self.assertGreater(big.filter_area_m2, self.tail.filter_area_m2)

    def test_rejects_bad_inputs(self):
        for kwargs in ({"dry_tph": 0.0}, {"cake_moisture": 1.5}, {"feed_solids_wt": 0.0}):
            args = {"dry_tph": 0.5, "feed_solids_wt": 0.45, "solids_sg": SG}
            args.update(kwargs)
            with self.assertRaises(ValueError):
                filter_press("X", "d", **args)

    def test_rejects_impossible_scale(self):
        with self.assertRaises(ValueError):
            filter_press("X", "d", 500.0, 0.45, SG, min_plate_mm=1500.0)


class TestHollowShaft(unittest.TestCase):
    def setUp(self):
        self.s = hollow_shaft("FC-X", shaft_power_kw=1.55, speed_rpm=290,
                              air_m3h=12.7, length_m=1.85)

    def test_torque_from_power_and_speed(self):
        import math
        expected = 1550.0 / (2 * math.pi * 290 / 60)
        self.assertAlmostEqual(self.s.torque_nm, expected, places=9)

    def test_bore_meets_air_velocity_target(self):
        self.assertLessEqual(self.s.air_velocity_m_s, 18.0 + 1e-9)
        self.assertGreater(self.s.air_velocity_m_s, 0.0)

    def test_shaft_is_within_allowable_shear(self):
        self.assertTrue(self.s.is_safe)
        self.assertLess(self.s.shear_stress_mpa, self.s.allowable_shear_mpa)

    def test_wall_thickness_positive(self):
        self.assertGreater(self.s.wall_thickness_mm, 0.0)
        self.assertGreater(self.s.outer_diameter_mm, self.s.bore_mm)

    def test_slenderness_governs_a_long_slim_shaft(self):
        """부선기 축은 길고 가늘어 강도가 아니라 처짐이 외경을 정한다."""
        self.assertEqual(self.s.governed_by, "처짐·위험속도")
        self.assertGreaterEqual(self.s.outer_diameter_mm, self.s.length_m / 25 * 1000)

    def test_torsion_governs_a_short_high_torque_shaft(self):
        stub = hollow_shaft("S", shaft_power_kw=40.0, speed_rpm=60,
                            air_m3h=12.0, length_m=0.5)
        self.assertEqual(stub.governed_by, "비틀림")

    def test_pressure_drop_grows_with_length(self):
        longer = hollow_shaft("L", 1.55, 290, 12.7, length_m=2.6)
        self.assertGreater(longer.bore_pressure_drop_kpa, self.s.bore_pressure_drop_kpa)

    def test_rejects_a_shaft_too_long_for_the_standard_series(self):
        """세장비 하한이 표준 외경 계열(최대 Ø140)을 넘으면 거절한다 — 축 길이 3.5 m 한계."""
        with self.assertRaises(ValueError):
            hollow_shaft("X", 1.55, 290, 12.7, length_m=4.0)

    def test_total_drop_includes_joint(self):
        self.assertAlmostEqual(
            self.s.total_pressure_drop_kpa,
            self.s.bore_pressure_drop_kpa + self.s.joint_pressure_drop_kpa,
            places=12,
        )

    def test_rejects_bad_inputs(self):
        for kwargs in ({"shaft_power_kw": 0}, {"speed_rpm": 0},
                       {"air_m3h": 0}, {"length_m": 0}):
            args = {"shaft_power_kw": 1.5, "speed_rpm": 290,
                    "air_m3h": 12.0, "length_m": 1.8}
            args.update(kwargs)
            with self.assertRaises(ValueError):
                hollow_shaft("X", **args)


class TestPlantIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant = build_plant()

    def test_every_mechanical_cell_has_a_safe_hollow_shaft(self):
        for c in self.plant.mechanical.cells:
            self.assertTrue(c.shaft.is_safe, c.tag)
            self.assertGreater(c.shaft.bore_mm, 0)

    def test_blower_pressure_covers_shaft_losses(self):
        mech = self.plant.mechanical
        worst = max(c.air_supply_pressure_kpa for c in mech.cells)
        self.assertGreaterEqual(mech.blower_pressure_kpa, worst)

    def test_shaft_loss_raises_blower_pressure_above_pulp_head_alone(self):
        mech = self.plant.mechanical
        pulp_only = max(c.aeration.total_pressure_kpa for c in mech.cells)
        self.assertGreater(max(c.air_supply_pressure_kpa for c in mech.cells), pulp_only)

    def test_both_options_have_two_filter_presses(self):
        for opt in (self.plant.rfc, self.plant.mechanical):
            self.assertIsInstance(opt.concentrate_filter, FilterPress)
            self.assertIsInstance(opt.tailings_filter, FilterPress)

    def test_filter_feed_matches_circuit_products(self):
        m = self.plant.mechanical
        self.assertAlmostEqual(
            m.concentrate_filter.dry_tph, m.result_peak.concentrate.dry_tph, places=12
        )
        self.assertAlmostEqual(
            m.tailings_filter.dry_tph, m.result_peak.tailings.dry_tph, places=12
        )
        r = self.plant.rfc
        self.assertAlmostEqual(
            r.concentrate_filter.dry_tph, r.performance_peak.concentrate_dry_tph, places=12
        )

    def test_filtrate_counts_toward_water_recycle(self):
        for opt in (self.plant.rfc, self.plant.mechanical):
            self.assertGreater(
                opt.water_recycle_m3h,
                opt.concentrate_filter.filtrate_m3h + opt.tailings_filter.filtrate_m3h,
            )

    def test_filter_pumps_are_in_installed_power(self):
        m = self.plant.mechanical
        rotors = sum(c.installed_kw for c in m.cells)
        self.assertGreater(m.installed_kw, rotors + m.blower_rating_kw)

    def test_design_basis_declares_hollow_shaft_aeration(self):
        self.assertTrue(db.HOLLOW_SHAFT_AIR)


if __name__ == "__main__":
    unittest.main()
