import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design.circuit import (
    FlotationUnit,
    Stream,
    dilute,
    float_unit,
    solve_circuit,
)
from flotation_design.circuit_design import build_circuit, build_units, solve_at

K = db.FLOAT_MODELS
SG = db.SPECIFIC_GRAVITY


def feed_stream(tph=0.5, water=1.5):
    return Stream.from_feed(db.FEED.component_tph(tph), K, water)


class TestStream(unittest.TestCase):
    def setUp(self):
        self.s = feed_stream()

    def test_species_split_matches_kinetic_fractions(self):
        fast, slow, non = self.s.species_tph["Ag"]
        total = 0.5 * 0.0045
        self.assertAlmostEqual(fast, total * 0.55, places=12)
        self.assertAlmostEqual(slow, total * 0.33, places=12)
        self.assertAlmostEqual(non, total * 0.12, places=12)

    def test_component_and_dry_totals(self):
        self.assertAlmostEqual(self.s.component_tph("Ag"), 0.5 * 0.0045, places=12)
        self.assertAlmostEqual(self.s.dry_tph, 0.5, places=12)

    def test_solids_fraction_and_volume(self):
        self.assertAlmostEqual(self.s.solids_mass_fraction, 0.25, places=12)
        expected = 0.5 / db.FEED.solids_specific_gravity + 1.5
        self.assertAlmostEqual(self.s.volumetric_flow_m3h(SG), expected, places=12)

    def test_addition_is_componentwise(self):
        total = self.s + self.s
        self.assertAlmostEqual(total.dry_tph, 1.0, places=12)
        self.assertAlmostEqual(total.water_tph, 3.0, places=12)

    def test_addition_rejects_mismatched_components(self):
        other = Stream({"Ag": (1.0, 0.0, 0.0)}, 0.0)
        with self.assertRaises(ValueError):
            self.s + other

    def test_empty_stream(self):
        e = Stream.empty(self.s.components)
        self.assertEqual(e.dry_tph, 0.0)
        self.assertEqual(e.grade_fraction("Ag"), 0.0)
        self.assertAlmostEqual((self.s + e).dry_tph, self.s.dry_tph, places=12)

    def test_scaled(self):
        half = self.s.scaled(0.5)
        self.assertAlmostEqual(half.dry_tph, 0.25, places=12)
        self.assertAlmostEqual(half.water_tph, 0.75, places=12)

    def test_max_abs_difference_is_zero_for_identical(self):
        self.assertEqual(self.s.max_abs_difference(self.s), 0.0)


class TestDilute(unittest.TestCase):
    def test_adds_water_to_reach_target(self):
        s = feed_stream(0.5, 0.5)  # 50 wt% 고체
        out, added = dilute(s, 0.25)
        self.assertAlmostEqual(out.solids_mass_fraction, 0.25, places=12)
        self.assertAlmostEqual(added, 1.0, places=12)

    def test_never_removes_water(self):
        s = feed_stream(0.5, 5.0)  # 이미 목표보다 묽음
        out, added = dilute(s, 0.25)
        self.assertEqual(added, 0.0)
        self.assertAlmostEqual(out.water_tph, 5.0, places=12)

    def test_no_target_is_passthrough(self):
        s = feed_stream()
        out, added = dilute(s, None)
        self.assertEqual(added, 0.0)
        self.assertIs(out, s)


class TestFlotationUnit(unittest.TestCase):
    def test_requires_exactly_one_sizing_basis(self):
        with self.assertRaises(ValueError):
            FlotationUnit("X", "duty", 0.1)
        with self.assertRaises(ValueError):
            FlotationUnit("X", "duty", 0.1, effective_volume_m3=0.3, target_residence_min=8.0)

    def test_rejects_bad_water_recovery(self):
        with self.assertRaises(ValueError):
            FlotationUnit("X", "duty", 1.0, target_residence_min=8.0)

    def test_residence_from_fixed_volume(self):
        u = FlotationUnit("X", "duty", 0.1, effective_volume_m3=0.3)
        self.assertAlmostEqual(u.residence_min(1.8), 10.0, places=12)

    def test_target_residence_ignores_flow(self):
        u = FlotationUnit("X", "duty", 0.1, target_residence_min=8.0)
        self.assertEqual(u.residence_min(999.0), 8.0)


class TestFloatUnit(unittest.TestCase):
    def setUp(self):
        self.unit = FlotationUnit("FC-101", "러퍼", 0.12, effective_volume_m3=0.2811)
        self.res = float_unit(feed_stream(), self.unit, K, SG)

    def test_mass_balance_closes(self):
        for name in self.res.feed.components:
            self.assertAlmostEqual(
                self.res.concentrate.component_tph(name)
                + self.res.tailings.component_tph(name),
                self.res.feed.component_tph(name),
                places=12,
            )

    def test_water_balance_closes_without_wash_water(self):
        self.assertAlmostEqual(
            self.res.concentrate.water_tph + self.res.tailings.water_tph,
            self.res.feed.water_tph,
            places=12,
        )

    def test_wash_water_reports_to_concentrate(self):
        unit = FlotationUnit(
            "FC-103", "클리너", 0.06, effective_volume_m3=0.0731, wash_water_m3h=0.25
        )
        res = float_unit(feed_stream(), unit, K, SG)
        self.assertAlmostEqual(
            res.concentrate.water_tph + res.tailings.water_tph,
            res.feed.water_tph + 0.25,
            places=12,
        )

    def test_nonfloating_species_only_reports_by_entrainment(self):
        # Si 는 전량 비부선 — 정광으로 가는 것은 수분 동반뿐이다.
        rec = self.res.recovery("Si")
        self.assertAlmostEqual(rec, 0.55 * 0.12, places=12)

    def test_concentrate_is_depleted_in_fast_species(self):
        # 러퍼 미광에는 속부선 분획이 거의 남지 않아야 한다 — 스캐빈저가
        # 어려운 duty 인 이유.
        feed_fast = self.res.feed.species_tph["Ag"][0]
        tail_fast = self.res.tailings.species_tph["Ag"][0]
        self.assertLess(tail_fast / feed_fast, 0.15)

    def test_collector_boost_raises_slow_species_recovery(self):
        boosted = float_unit(
            feed_stream(),
            FlotationUnit("X", "d", 0.12, effective_volume_m3=0.2811, collector_boost=1.4),
            K,
            SG,
        )
        self.assertGreater(boosted.recovery("Ag"), self.res.recovery("Ag"))

    def test_dilution_is_reported(self):
        unit = FlotationUnit(
            "X", "d", 0.06, effective_volume_m3=0.0731, dilution_target_solids=0.18
        )
        res = float_unit(feed_stream(0.5, 0.5), unit, K, SG)
        self.assertGreater(res.dilution_water_m3h, 0.0)
        self.assertAlmostEqual(res.feed.solids_mass_fraction, 0.18, places=12)


class TestSolveCircuit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = solve_at(db.FEED, 0.5)

    def test_converges(self):
        self.assertLess(self.res.iterations, 200)
        self.assertLess(self.res.residual_tph, 1e-11)

    def test_overall_mass_balance_closes(self):
        self.assertLess(self.res.mass_balance_error_tph(), 1e-9)
        self.assertAlmostEqual(
            self.res.concentrate.dry_tph + self.res.tailings.dry_tph, 0.5, places=9
        )

    def test_grades_sum_to_unity(self):
        for stream in (self.res.concentrate, self.res.tailings):
            total = sum(stream.grade_fraction(n) for n in stream.components)
            self.assertAlmostEqual(total, 1.0, places=12)

    def test_rougher_feed_hits_target_solids(self):
        self.assertAlmostEqual(
            self.res.rougher.feed.solids_mass_fraction, db.ROUGHER_FEED_SOLIDS, places=9
        )

    def test_cleaner_feed_is_diluted_to_target(self):
        self.assertAlmostEqual(
            self.res.cleaner.feed.solids_mass_fraction, db.CLEANER_FEED_SOLIDS, places=9
        )

    def test_circulating_load_is_modest(self):
        self.assertGreater(self.res.circulating_load, 0.05)
        self.assertLess(self.res.circulating_load, 0.5)

    def test_recycle_equals_scavenger_conc_plus_cleaner_tails(self):
        expected = (
            self.res.scavenger.concentrate.dry_tph + self.res.cleaner.tailings.dry_tph
        )
        self.assertAlmostEqual(self.res.recycle.dry_tph, expected, places=12)

    def test_circuit_beats_rougher_alone(self):
        from flotation_design.kinetics import simulate

        alone = simulate(db.FEED.component_tph(0.5), K, self.res.rougher.residence_min, 0.12)
        self.assertGreater(self.res.recovery("Ag"), alone.recovery["Ag"])
        self.assertGreater(
            self.res.concentrate.grade_fraction("Ag"),
            alone.concentrate.grade_fraction("Ag"),
        )

    def test_cleaner_rejects_silicon(self):
        self.assertLess(self.res.concentrate.grade_fraction("Si"), 0.05)
        self.assertLess(self.res.recovery("Si"), 0.01)

    def test_silver_recovery_bounded_by_floatable_fraction(self):
        self.assertLess(self.res.recovery("Ag"), K["Ag"].r_max + 0.02)
        self.assertGreater(self.res.recovery("Ag"), 0.70)

    def test_performance_targets_at_peak(self):
        self.assertGreater(self.res.recovery("Ag"), 0.72)
        self.assertGreater(self.res.recovery("Cu"), 0.88)
        self.assertLess(self.res.mass_pull, 0.16)
        self.assertGreater(self.res.enrichment_ratio("Ag"), 5.0)

    def test_lower_throughput_improves_recovery(self):
        avg = solve_at(db.FEED, 0.3)
        self.assertGreater(avg.recovery("Ag"), self.res.recovery("Ag"))

    def test_missing_kinetics_raises(self):
        units = build_units()
        with self.assertRaises(KeyError):
            solve_circuit({"Au": 0.1}, K, SG, *units)

    def test_non_convergence_raises(self):
        units = build_units()
        with self.assertRaises(RuntimeError):
            solve_circuit(
                db.FEED.component_tph(0.5), K, SG, *units, max_iterations=2, tolerance_tph=1e-18
            )


class TestCircuitDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = build_circuit()

    def test_three_cells(self):
        self.assertEqual([c.tag for c in self.d.cells], ["FC-101", "FC-102", "FC-103"])

    def test_scavenger_shares_rougher_shell(self):
        r, s = self.d.cell("FC-101"), self.d.cell("FC-102")
        self.assertEqual(r.geometry.width_m, s.geometry.width_m)
        self.assertEqual(r.geometry.shell_height_m, s.geometry.shell_height_m)
        self.assertEqual(r.impeller.diameter_m, s.impeller.diameter_m)
        self.assertEqual(r.impeller.motor_rating_kw, s.impeller.motor_rating_kw)

    def test_scavenger_has_shallower_froth_and_more_air(self):
        r, s = self.d.cell("FC-101"), self.d.cell("FC-102")
        self.assertLess(s.geometry.froth_depth_m, r.geometry.froth_depth_m)
        self.assertGreater(s.aeration.air_flow_m3h, r.aeration.air_flow_m3h)

    def test_cleaner_has_deeper_froth_and_gentler_rotor(self):
        r, c = self.d.cell("FC-101"), self.d.cell("FC-103")
        self.assertGreater(c.geometry.froth_depth_m, r.geometry.froth_depth_m)
        self.assertLess(c.impeller.tip_speed_m_s, r.impeller.tip_speed_m_s)
        self.assertLess(c.aeration.air_flow_m3h, r.aeration.air_flow_m3h)

    def test_shared_blower_covers_all_cells(self):
        self.assertAlmostEqual(
            self.d.blower_flow_m3h,
            sum(c.aeration.air_flow_max_m3h for c in self.d.cells),
            places=9,
        )
        self.assertEqual(self.d.blower_rating_kw, 1.5)

    def test_motor_selection(self):
        self.assertEqual(self.d.cell("FC-101").impeller.motor_rating_kw, 2.2)
        self.assertEqual(self.d.cell("FC-103").impeller.motor_rating_kw, 0.55)

    def test_froth_loading_within_limits_everywhere(self):
        for tag in ("FC-101", "FC-102", "FC-103"):
            fl = self.d.froth_loading(tag, self.d.result_peak)
            self.assertTrue(fl.carry_rate_ok, tag)
            self.assertTrue(fl.lip_loading_ok, tag)

    def test_confirmed_cells_meet_target_residence(self):
        from flotation_design.circuit_design import sizing_check

        for tag, target in (("FC-101", 8.0), ("FC-102", 10.0), ("FC-103", 8.0)):
            need = sizing_check(self.d.result_peak, tag, target)
            self.assertGreaterEqual(
                self.d.cell(tag).geometry.effective_slurry_volume_m3, need * 0.98, tag
            )

    def test_conditioners_sized_on_recycle_laden_flow(self):
        self.assertGreater(
            self.d.result_peak.rougher.feed_volume_m3h,
            self.d.pulp_peak.volumetric_flow_m3h,
        )
        self.assertGreater(self.d.conditioners[0].working_volume_m3, 0.0)

    def test_unknown_cell_tag_raises(self):
        with self.assertRaises(KeyError):
            self.d.cell("FC-999")


if __name__ == "__main__":
    unittest.main()
