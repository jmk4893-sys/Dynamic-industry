import math
import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design import references as ref
from flotation_design.rfc import (
    RfcDesign,
    rfc_separation,
    size_rfc,
    slurry_volumetric_flow_m3h,
)

SG = db.FEED.solids_specific_gravity


def design(dry_tph=0.5, solids_wt=None):
    return size_rfc(
        "FC-101", "러퍼", dry_tph, SG,
        db.FEED.solids_mass_fraction if solids_wt is None else solids_wt,
        bias_flux_cm_s=db.RFC_BIAS_FLUX_CM_S,
    )


class TestSlurryFlow(unittest.TestCase):
    def test_matches_definition(self):
        q = slurry_volumetric_flow_m3h(0.5, 2.374, 0.07)
        self.assertAlmostEqual(q, 0.5 / 2.374 + 0.5 * 0.93 / 0.07, places=12)

    def test_rejects_bad_solids(self):
        for bad in (0.0, 1.0, -0.1):
            with self.assertRaises(ValueError):
                slurry_volumetric_flow_m3h(0.5, 2.374, bad)


class TestFluxSimilarityScaleUp(unittest.TestCase):
    """실증 flux 를 유지한 채 단면적만 키우는 스케일업."""

    def setUp(self):
        self.d = design()
        self.trial = ref.CONTINUOUS_TRIAL

    def test_fluxes_match_the_trial(self):
        self.assertAlmostEqual(self.d.feed_flux_cm_s, self.trial.feed_flux_cm_s)
        self.assertAlmostEqual(self.d.air_flux_cm_s, self.trial.air_flux_cm_s)
        self.assertAlmostEqual(self.d.wash_water_flux_cm_s, self.trial.wash_water_flux_cm_s)

    def test_gas_liquid_residence_preserved(self):
        combined = self.d.feed_m3h + self.d.air_m3h
        self.assertAlmostEqual(
            self.d.riser_volume_m3 / (combined / 60.0),
            self.trial.gas_liquid_residence_min,
            places=6,
        )

    def test_confirmed_diameter(self):
        self.assertAlmostEqual(self.d.diameter_m, 0.350, places=6)

    def test_capacity_meets_peak_throughput(self):
        self.assertGreaterEqual(self.d.capacity_tph, db.FEED.peak_tph)

    def test_diameter_is_a_standard_size(self):
        self.assertIn(round(self.d.diameter_m * 1000), (150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 1000))

    def test_area_and_flows_are_consistent(self):
        self.assertAlmostEqual(self.d.area_m2, math.pi * 0.35**2 / 4, places=9)
        self.assertAlmostEqual(
            self.d.feed_m3h, self.d.feed_flux_cm_s / 100 * self.d.area_m2 * 3600, places=9
        )

    def test_overflow_water_is_wash_water_less_bias(self):
        self.assertAlmostEqual(
            self.d.overflow_water_m3h,
            (self.d.wash_water_flux_cm_s - self.d.bias_flux_cm_s) / 100
            * self.d.area_m2 * 3600,
            places=9,
        )
        self.assertLess(self.d.overflow_water_m3h, self.d.wash_water_m3h)

    def test_bias_must_be_below_wash_water(self):
        with self.assertRaises(ValueError):
            size_rfc("X", "d", 0.5, SG, 0.07, bias_flux_cm_s=5.0)

    def test_higher_solids_shrinks_the_vessel(self):
        self.assertLess(design(solids_wt=0.30).diameter_m, design(solids_wt=0.02).diameter_m)

    def test_capacity_rises_with_solids_at_fixed_flux(self):
        d = design()
        self.assertLess(d.capacity_at_solids(0.07), d.capacity_at_solids(0.15))
        self.assertLess(d.capacity_at_solids(0.15), d.capacity_at_solids(0.30))

    def test_reproduces_the_authors_scale_up_claim(self):
        """저자들은 30 wt% 운전 시 Ø200 mm 한 대로 호주 전량(~0.43 t/h)이
        처리된다고 했다. 모델이 같은 결론을 내야 한다."""
        d200 = RfcDesign(
            tag="X", duty="d", diameter_m=0.200, design_solids_wt=0.30,
            design_dry_tph=0.0, feed_flux_cm_s=2.0, air_flux_cm_s=2.0,
            wash_water_flux_cm_s=0.81, bias_flux_cm_s=0.25,
            gas_liquid_residence_min=1.0, riser_height_m=2.4,
            inclined_channel_angle_deg=70.0, inclined_channel_spacing_mm=12.0,
            solids_sg=SG,
        )
        self.assertGreater(d200.capacity_at_solids(0.30), 0.43)

    def test_rejects_oversized_duty(self):
        with self.assertRaises(ValueError):
            size_rfc("X", "d", 500.0, SG, 0.02)


class TestTurndown(unittest.TestCase):
    def setUp(self):
        self.d = design()

    def test_peak_is_within_capacity(self):
        op = self.d.operating_point(db.FEED.peak_tph)
        self.assertTrue(op.within_capacity)
        self.assertLessEqual(op.turndown_ratio, 1.0)

    def test_turndown_scales_all_fluxes_together(self):
        op = self.d.operating_point(db.FEED.average_tph)
        self.assertAlmostEqual(op.feed_flux_cm_s, self.d.feed_flux_cm_s, places=12)
        self.assertAlmostEqual(op.air_flux_cm_s, self.d.air_flux_cm_s, places=12)
        self.assertAlmostEqual(op.wash_water_flux_cm_s, self.d.wash_water_flux_cm_s,
                               places=12)
        self.assertAlmostEqual(op.gas_liquid_residence_min, 1.0, places=12)

    def test_turndown_reduces_solids_to_preserve_flux(self):
        op = self.d.operating_point(db.FEED.average_tph)
        self.assertLess(op.solids_wt, db.FEED.solids_mass_fraction)
        self.assertAlmostEqual(self.d.capacity_at_solids(op.solids_wt),
                               db.FEED.average_tph, places=9)

    def test_overload_is_flagged(self):
        op = self.d.operating_point(5.0)
        self.assertFalse(op.within_capacity)

    def test_solids_required_for_throughput(self):
        w = self.d.solids_required_for(0.3)
        self.assertAlmostEqual(self.d.capacity_at_solids(w), 0.3, places=9)


class TestSeparation(unittest.TestCase):
    def setUp(self):
        self.perf = rfc_separation(
            db.FEED.component_tph(0.5), db.FLOAT_MODELS,
            db.RFC_AG_RECOVERY, db.COMPOSITE_CARRY_RATIO,
        )

    def test_mass_balance_closes(self):
        self.assertLess(self.perf.mass_balance_error_tph(), 1e-12)

    def test_grades_sum_to_unity(self):
        for grade in (self.perf.concentrate_grade, self.perf.tailings_grade):
            self.assertAlmostEqual(sum(grade(n) for n in self.perf.feed_tph), 1.0, places=12)

    def test_silver_recovery_matches_measured_value(self):
        self.assertAlmostEqual(self.perf.recovery("Ag"), db.RFC_AG_RECOVERY, places=9)

    def test_recoveries_bounded(self):
        for name in self.perf.feed_tph:
            self.assertGreaterEqual(self.perf.recovery(name), 0.0)
            self.assertLessEqual(self.perf.recovery(name), 1.0)

    def test_gangue_reports_only_by_composite_carry(self):
        """세척수 bias 가 있으면 수분 동반이 사실상 0 이므로,
        자유 맥석은 정광으로 가지 않고 잠금 맥석만 Ag와 함께 간다."""
        no_carry = rfc_separation(
            db.FEED.component_tph(0.5), db.FLOAT_MODELS, db.RFC_AG_RECOVERY, 0.0
        )
        self.assertAlmostEqual(no_carry.recovery("Si"), 0.0, places=12)
        self.assertAlmostEqual(
            self.perf.recovery("Ag_locked_gangue"),
            self.perf.recovery("Ag"),
            places=12,
        )
        self.assertAlmostEqual(
            self.perf.concentrate_tph["Ag_locked_gangue"]
            / self.perf.concentrate_tph["Ag"],
            db.COMPOSITE_CARRY_RATIO,
            places=12,
        )

    def test_zero_silver_floatability_raises(self):
        from flotation_design.kinetics import ComponentKinetics

        broken = dict(db.FLOAT_MODELS)
        broken["Ag"] = ComponentKinetics("Ag")
        with self.assertRaises(ValueError):
            rfc_separation(db.FEED.component_tph(0.5), broken, 0.9, 1.1)


class TestBlower(unittest.TestCase):
    def test_pressure_covers_riser_head(self):
        d = design()
        static = 1000 * 9.80665 * d.riser_height_m / 1000
        self.assertGreater(d.blower_pressure_kpa, static)

    def test_rating_is_a_standard_motor(self):
        self.assertIn(design().blower_rating_kw, (0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0))


if __name__ == "__main__":
    unittest.main()
