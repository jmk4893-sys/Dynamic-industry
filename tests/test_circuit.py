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
from flotation_design.plant import build_mechanical_units, build_plant, solve_mechanical

K = db.FLOAT_MODELS
SG = db.SPECIFIC_GRAVITY


def feed_stream(tph=0.5, water=None):
    if water is None:
        w = db.FEED.solids_mass_fraction
        water = tph * (1 - w) / w
    return Stream.from_feed(db.FEED.component_tph(tph), K, water)


class TestStream(unittest.TestCase):
    def setUp(self):
        self.s = feed_stream()

    def test_species_split_matches_kinetic_fractions(self):
        fast, slow, non = self.s.species_tph["Ag"]
        kin = K["Ag"]
        total = 0.5 * db.FEED.grade_ppm("Ag") / 1e6
        self.assertAlmostEqual(fast, total * kin.fast_fraction, places=12)
        self.assertAlmostEqual(slow, total * kin.slow_fraction, places=12)
        self.assertAlmostEqual(non, total * kin.nonfloating_fraction, places=12)

    def test_component_and_dry_totals(self):
        expected = 0.5 * db.FEED.grade_ppm("Ag") / 1e6
        self.assertAlmostEqual(self.s.component_tph("Ag"), expected, places=12)
        self.assertAlmostEqual(self.s.dry_tph, 0.5, places=12)

    def test_solids_fraction_and_volume(self):
        w = db.FEED.solids_mass_fraction
        self.assertAlmostEqual(self.s.solids_mass_fraction, w, places=12)
        expected = 0.5 / db.FEED.solids_specific_gravity + 0.5 * (1 - w) / w
        self.assertAlmostEqual(self.s.volumetric_flow_m3h(SG), expected, places=12)

    def test_addition_is_componentwise(self):
        total = self.s + self.s
        self.assertAlmostEqual(total.dry_tph, 1.0, places=12)
        self.assertAlmostEqual(total.water_tph, self.s.water_tph * 2, places=12)

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
        self.assertAlmostEqual(half.water_tph, self.s.water_tph / 2, places=12)

    def test_max_abs_difference_is_zero_for_identical(self):
        self.assertEqual(self.s.max_abs_difference(self.s), 0.0)


class TestDilute(unittest.TestCase):
    def test_adds_water_to_reach_target(self):
        s = feed_stream(0.5, 0.5)  # 50 wt% 고체
        out, added = dilute(s, 0.25)
        self.assertAlmostEqual(out.solids_mass_fraction, 0.25, places=12)
        self.assertAlmostEqual(added, 1.0, places=12)

    def test_never_removes_water(self):
        s = feed_stream(0.5, 20.0)  # 이미 목표보다 묽음
        out, added = dilute(s, 0.25)
        self.assertEqual(added, 0.0)
        self.assertAlmostEqual(out.water_tph, 20.0, places=12)

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
        self.unit = FlotationUnit("FC-201", "러퍼", 0.06, effective_volume_m3=0.85)
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
            "FC-202", "클리너", 0.04, effective_volume_m3=0.073, wash_water_m3h=0.25
        )
        res = float_unit(feed_stream(), unit, K, SG)
        self.assertAlmostEqual(
            res.concentrate.water_tph + res.tailings.water_tph,
            res.feed.water_tph + 0.25,
            places=12,
        )

    def test_nonfloating_species_only_reports_by_entrainment(self):
        self.assertAlmostEqual(
            self.res.recovery("Si"), K["Si"].entrainment_factor * 0.06, places=12
        )

    def test_tanks_in_series_beats_single_tank(self):
        one = float_unit(
            feed_stream(),
            FlotationUnit("X", "d", 0.06, effective_volume_m3=0.85, cells_in_series=1),
            K, SG,
        )
        two = float_unit(
            feed_stream(),
            FlotationUnit("X", "d", 0.06, effective_volume_m3=0.85, cells_in_series=2),
            K, SG,
        )
        self.assertGreater(two.recovery("Ag"), one.recovery("Ag"))

    def test_rejects_zero_cells_in_series(self):
        with self.assertRaises(ValueError):
            FlotationUnit("X", "d", 0.06, effective_volume_m3=0.85, cells_in_series=0)

    def test_rate_scale_factor_slows_recovery(self):
        slow = float_unit(
            feed_stream(),
            FlotationUnit("X", "d", 0.06, effective_volume_m3=0.85, rate_scale_factor=0.5),
            K, SG,
        )
        self.assertLess(slow.recovery("Ag"), self.res.recovery("Ag"))

    def test_dilution_is_reported(self):
        unit = FlotationUnit(
            "X", "d", 0.04, effective_volume_m3=0.073, dilution_target_solids=0.05
        )
        res = float_unit(feed_stream(0.5, 0.5), unit, K, SG)
        self.assertGreater(res.dilution_water_m3h, 0.0)
        self.assertAlmostEqual(res.feed.solids_mass_fraction, 0.05, places=12)


class TestCompositeCarry(unittest.TestCase):
    """Ag-실리콘 복합입자는 하나의 보존 성분으로 각 단을 통과한다."""

    def setUp(self):
        self.unit = FlotationUnit("FC-201", "러퍼", 0.06, effective_volume_m3=0.85)

    def _grade(self, ratio):
        res = float_unit(feed_stream(), self.unit, K, SG, composite_carry_ratio=ratio)
        return res.concentrate.grade_fraction("Ag"), res

    def test_legacy_carry_is_not_applied_twice(self):
        without, _ = self._grade(0.0)
        with_carry, _ = self._grade(db.COMPOSITE_CARRY_RATIO)
        self.assertAlmostEqual(with_carry, without, places=12)

    def test_locked_gangue_stays_paired_with_silver(self):
        _, res = self._grade(db.COMPOSITE_CARRY_RATIO)
        for stream in (res.feed, res.concentrate, res.tailings):
            self.assertAlmostEqual(
                stream.component_tph("Ag_locked_gangue") / stream.component_tph("Ag"),
                db.COMPOSITE_CARRY_RATIO,
                places=10,
            )

    def test_grade_cannot_exceed_theoretical_limit(self):
        limit = 1.0 / (1.0 + db.COMPOSITE_CARRY_RATIO)
        grade, _ = self._grade(db.COMPOSITE_CARRY_RATIO)
        self.assertLessEqual(grade, limit + 1e-9)

    def test_carry_preserves_mass_balance(self):
        _, res = self._grade(db.COMPOSITE_CARRY_RATIO)
        for name in res.feed.components:
            self.assertAlmostEqual(
                res.concentrate.component_tph(name) + res.tailings.component_tph(name),
                res.feed.component_tph(name),
                places=12,
            )

    def test_legacy_carry_argument_cannot_move_free_gangue(self):
        # 잠금 성분이 있는 새 급광에는 과거 호환용 carry 인자를 재적용하지 않는다.
        res = float_unit(feed_stream(), self.unit, K, SG, composite_carry_ratio=1e6)
        for name in ("Si", "Al"):
            self.assertAlmostEqual(
                res.recovery(name),
                K[name].entrainment_factor * self.unit.water_recovery,
                places=12,
            )


class TestMechanicalCircuit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = solve_mechanical(db.FEED, 0.5)

    def test_converges(self):
        self.assertLess(self.res.iterations, 200)
        self.assertLess(self.res.residual_tph, 1e-11)

    def test_three_stages_present(self):
        self.assertIsNotNone(self.res.scavenger)
        self.assertEqual(self.res.rougher.unit.tag, "FC-201")
        self.assertEqual(self.res.scavenger.unit.tag, "FC-202")
        self.assertEqual(self.res.cleaner.unit.tag, "FC-203")

    def test_overall_mass_balance_closes(self):
        self.assertLess(self.res.mass_balance_error_tph(), 1e-9)
        self.assertAlmostEqual(
            self.res.concentrate.dry_tph + self.res.tailings.dry_tph, 0.5, places=9
        )

    def test_final_tailings_are_scavenger_tailings(self):
        self.assertAlmostEqual(
            self.res.tailings.dry_tph, self.res.scavenger.tailings.dry_tph, places=12
        )

    def test_scavenger_treats_rougher_tailings(self):
        self.assertAlmostEqual(
            self.res.scavenger.feed.dry_tph, self.res.rougher.tailings.dry_tph, places=12
        )

    def test_recycle_is_scavenger_concentrate_plus_cleaner_tailings(self):
        self.assertAlmostEqual(
            self.res.recycle.dry_tph,
            self.res.scavenger.concentrate.dry_tph + self.res.cleaner.tailings.dry_tph,
            places=12,
        )

    def test_scavenger_standardizes_rougher_vessel(self):
        """미검증 대형화 대신 러퍼와 동체를 공용하고 운전조건만 달리한다."""
        self.assertEqual(db.SCAVENGER_CELL.width_m, db.ROUGHER_CELL.width_m)
        self.assertEqual(
            db.SCAVENGER_CELL.shell_height_m, db.ROUGHER_CELL.shell_height_m
        )
        self.assertLess(
            db.SCAVENGER_CELL.froth_depth_m, db.ROUGHER_CELL.froth_depth_m
        )
        self.assertGreater(self.res.scavenger.residence_min, self.res.rougher.residence_min)

    def test_scavenger_lifts_recovery(self):
        """스캐빈저가 실제로 회수율을 올리는지 — 없는 회로와 비교."""
        r, sc, c = build_mechanical_units()
        without = solve_circuit(
            db.FEED.component_tph(0.5), K, SG, r, None, c,
            rougher_feed_solids=db.FEED.solids_mass_fraction,
            composite_carry_ratio=db.COMPOSITE_CARRY_RATIO,
        )
        self.assertGreater(self.res.recovery("Ag"), without.recovery("Ag") + 0.02)

    def test_grades_sum_to_unity(self):
        for stream in (self.res.concentrate, self.res.tailings):
            total = sum(stream.grade_fraction(n) for n in stream.components)
            self.assertAlmostEqual(total, 1.0, places=12)

    def test_rougher_feed_hits_target_solids(self):
        self.assertAlmostEqual(
            self.res.rougher.feed.solids_mass_fraction,
            db.FEED.solids_mass_fraction,
            places=9,
        )

    def test_cleaner_upgrades_over_rougher(self):
        self.assertGreater(
            self.res.concentrate.grade_fraction("Ag"),
            self.res.rougher.concentrate.grade_fraction("Ag"),
        )

    def test_performance_targets(self):
        self.assertGreater(self.res.recovery("Ag"), 0.93)
        self.assertGreater(self.res.concentrate.grade_fraction("Ag"), 0.40)
        self.assertLess(self.res.mass_pull, 0.03)

    def test_lower_throughput_improves_recovery(self):
        avg = solve_mechanical(db.FEED, 0.3)
        self.assertGreater(avg.recovery("Ag"), self.res.recovery("Ag"))

    def test_filter_press_filtrate_replaces_fresh_rougher_water(self):
        returned = solve_mechanical(db.FEED, 0.5, filtrate_return_m3h=0.47)
        self.assertAlmostEqual(returned.filtrate_return_m3h, 0.47, places=12)
        self.assertAlmostEqual(
            returned.fresh_water_m3h,
            self.res.fresh_water_m3h - 0.47,
            places=9,
        )
        self.assertAlmostEqual(
            returned.rougher.feed.solids_mass_fraction,
            db.FEED.solids_mass_fraction,
            places=9,
        )

    def test_missing_kinetics_raises(self):
        r, sc, c = build_mechanical_units()
        with self.assertRaises(KeyError):
            solve_circuit({"Au": 0.1}, K, SG, r, sc, c)

    def test_non_convergence_raises(self):
        r, sc, c = build_mechanical_units()
        with self.assertRaises(RuntimeError):
            solve_circuit(
                db.FEED.component_tph(0.5), K, SG, r, sc, c,
                max_iterations=2, tolerance_tph=1e-18,
            )


if __name__ == "__main__":
    unittest.main()
