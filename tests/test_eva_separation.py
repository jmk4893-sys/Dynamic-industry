"""떨어진 EVA 분리 (ES-1 · ES-2) 검증.

AS-1 이 떼어 낸 EVA 를 부선 급광에서 걷어내는 계통이다. 은은 건드리지 않고
부선조로 보내야 하므로 포수제 앞에서 기포제만 쓴다. 여기서는 (1) 설계 EVA 를
정하는 잔막 모델, (2) 중력 대신 부선을 고른 근거, (3) 부선 급광 한도에서 역산한
요구 제거율, (4) 2안 동체를 그대로 쓴 셀 사양, (5) S-1 판정선을 확인한다.
"""

import math
import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design.attrition_pilot import tolerable_aluminium_reaction_kg_h
from flotation_design.eva_separation import (
    DewateringBag,
    EvaMethodScreen,
    EvaRequirement,
    batch_t90_limit,
    concentrate_grade_with_eva,
    eva_content_from_film,
    eva_rate_constant_1_min,
    flake_equivalent_diameter_um,
    grade_margin_tph,
    rise_velocity_m_h,
)
from flotation_design.plant import (
    EVA,
    build_eva_separation,
    build_mechanical_option,
    build_plant,
    eva_attachment_efficiency,
    solve_eva_circuit,
)

WAFER_FRACTION = sum(
    c.mass_fraction for c in db.CELL_FRACTION if c.name in ("Si", "Ag_locked_gangue")
)


class TestDesignParticle(unittest.TestCase):
    """잔막 두께 하나로 함량과 박편 크기가 함께 정해진다."""

    def test_cube_flake_matches_sphere_of_same_volume(self):
        a = 10.0
        self.assertAlmostEqual(
            flake_equivalent_diameter_um(a, a), (6.0 / math.pi) ** (1 / 3) * a, places=9
        )

    def test_flake_is_smaller_than_its_width(self):
        d = flake_equivalent_diameter_um(db.EVA_RESIDUAL_FILM_UM, db.EVA_FLAKE_WIDTH_UM)
        self.assertLess(d, db.EVA_FLAKE_WIDTH_UM)
        self.assertGreater(d, db.EVA_RESIDUAL_FILM_UM)

    def test_five_micron_film_is_two_percent(self):
        e = eva_content_from_film(
            5.0, db.CELL_WAFER_THICKNESS_UM, WAFER_FRACTION, db.EVA_SG, 2.33
        )
        self.assertAlmostEqual(e, 0.0200, places=3)

    def test_content_is_linear_in_film(self):
        args = (db.CELL_WAFER_THICKNESS_UM, WAFER_FRACTION, db.EVA_SG, 2.33)
        self.assertAlmostEqual(
            eva_content_from_film(10.0, *args), 2.0 * eva_content_from_film(5.0, *args)
        )
        self.assertEqual(eva_content_from_film(0.0, *args), 0.0)

    def test_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            flake_equivalent_diameter_um(0.0, 30.0)
        with self.assertRaises(ValueError):
            eva_content_from_film(-1.0, 180.0, 0.9, 0.95, 2.33)
        with self.assertRaises(ValueError):
            eva_content_from_film(5.0, 180.0, 0.0, 0.95, 2.33)


class TestMethodScreen(unittest.TestCase):
    """중력으로는 못 가른다 — 기포가 박편을 수천 배 빨리 끌어올린다."""

    def setUp(self):
        self.screen = EvaMethodScreen(
            flow_m3h=7.0, eva_diameter_um=21.0, eva_sg=db.EVA_SG, bubble_d32_mm=0.8
        )

    def test_eva_rises_and_silicon_sinks(self):
        self.assertGreater(rise_velocity_m_h(21.0, db.EVA_SG), 0.0)
        self.assertLess(rise_velocity_m_h(21.0, 2.33), 0.0)

    def test_gravity_skimming_needs_an_impractical_area(self):
        self.assertGreater(self.screen.skim_area_m2, 100.0)

    def test_bubbles_lift_thousands_of_times_faster(self):
        self.assertGreater(self.screen.bubble_to_eva_ratio, 1000.0)


class TestRateConstant(unittest.TestCase):
    """k = 1.5·Ea·Ec·Jg/db — 크기 제곱, Jg, Ea 에 비례한다."""

    def k(self, d=20.0, jg=0.9, ea=0.12, db_mm=0.8):
        return eva_rate_constant_1_min(d, jg, ea, db_mm)

    def test_scales_with_the_square_of_size(self):
        self.assertAlmostEqual(self.k(d=20.0) / self.k(d=10.0), 4.0, places=9)

    def test_scales_with_gas_rate_and_attachment(self):
        self.assertAlmostEqual(self.k(jg=0.9) / self.k(jg=0.45), 2.0, places=9)
        self.assertAlmostEqual(self.k(ea=0.24) / self.k(ea=0.12), 2.0, places=9)

    def test_smaller_bubbles_catch_fine_eva_faster(self):
        self.assertGreater(self.k(db_mm=0.4), self.k(db_mm=0.8))

    def test_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            self.k(d=0.0)
        with self.assertRaises(ValueError):
            self.k(ea=1.5)


class TestRequirement(unittest.TestCase):
    """부선 급광 한도에서 역산한 요구 제거율."""

    def test_required_recovery(self):
        r = EvaRequirement(dry_tph=0.5, feed_limit=0.001, freed_eva_tph=0.009)
        self.assertAlmostEqual(r.allowance_tph, 0.0005)
        self.assertAlmostEqual(r.required_recovery, 1.0 - 0.0005 / 0.009)

    def test_nothing_to_remove_below_the_limit(self):
        r = EvaRequirement(dry_tph=0.5, feed_limit=0.001, freed_eva_tph=0.0004)
        self.assertEqual(r.required_recovery, 0.0)

    def test_margin_brings_grade_exactly_to_guarantee(self):
        c, g, guarantee = 0.00636, 0.463, 0.40
        margin = grade_margin_tph(c, g, guarantee)
        self.assertAlmostEqual(concentrate_grade_with_eva(c, g, margin), guarantee, places=12)

    def test_rejects_guarantee_above_design_grade(self):
        with self.assertRaises(ValueError):
            grade_margin_tph(0.006, 0.40, 0.45)


class TestBatchLimit(unittest.TestCase):
    """회로 회수율이 요구치에 닿는 회분 t90 — 해석해로 검산."""

    def test_matches_single_mixer(self):
        tau = 5.0
        required = 0.9
        t90 = batch_t90_limit(lambda k: k * tau / (1.0 + k * tau), required)
        k_needed = required / (1.0 - required) / tau
        self.assertAlmostEqual(t90, math.log(10.0) / k_needed, places=6)

    def test_raises_when_unreachable(self):
        with self.assertRaises(ValueError):
            batch_t90_limit(lambda k: 0.5, 0.9)
        with self.assertRaises(ValueError):
            batch_t90_limit(lambda k: k, 1.0)


class TestDewateringBag(unittest.TestCase):
    def setUp(self):
        self.bag = DewateringBag(
            tag="FB-1", volume_m3=1.0, fill=0.8, units=2,
            cake_solids_volume_fraction=0.35, eva_sg=0.95,
            eva_tph=0.010, minerals_tph=0.0,
        )

    def test_capacity_and_interval(self):
        self.assertAlmostEqual(self.bag.dry_capacity_kg, 1.0 * 0.8 * 0.35 * 950.0)
        self.assertAlmostEqual(self.bag.change_interval_h, self.bag.dry_capacity_kg / 10.0)

    def test_cake_water(self):
        # 케이크 1 m3: EVA 0.35 x 950 kg, 물 0.65 x 1000 kg
        self.assertAlmostEqual(
            self.bag.cake_water_tph / self.bag.eva_tph, 650.0 / (0.35 * 950.0)
        )
        self.assertAlmostEqual(self.bag.cake_moisture, 650.0 / (650.0 + 332.5))

    def test_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            DewateringBag("FB-1", 1.0, 0.8, 2, 1.2, 0.95, 0.01, 0.0)


class TestEvaSeparationDesign(unittest.TestCase):
    """ES-1 · ES-2 · B-001 · P-001 · FB-1 설계."""

    @classmethod
    def setUpClass(cls):
        cls.es = build_eva_separation()
        cls.mech = build_mechanical_option()

    def test_reuses_the_mechanical_option_shells(self):
        """새로 설계할 회전체가 없다 — ES-1 = FC-202, ES-2 = FC-203."""
        pairs = ((self.es.rougher, self.mech.cell("FC-202")),
                 (self.es.cleaner, self.mech.cell("FC-203")))
        for es_cell, twin in pairs:
            with self.subTest(tag=es_cell.tag):
                self.assertEqual(es_cell.geometry, twin.geometry)
                self.assertEqual(es_cell.impeller.diameter_m, twin.impeller.diameter_m)
                self.assertEqual(es_cell.impeller.speed_rpm, twin.impeller.speed_rpm)
                self.assertEqual(es_cell.impeller.motor_rating_kw, twin.impeller.motor_rating_kw)
                self.assertTrue(es_cell.shaft.is_safe)
        self.assertEqual(self.es.rougher.cells_in_series, db.EVA_ROUGHER_CELLS)

    def test_more_air_needs_a_bigger_bore_not_a_bigger_shaft(self):
        ro, twin = self.es.rougher, self.mech.cell("FC-202")
        self.assertGreater(ro.aeration.air_flow_m3h, twin.aeration.air_flow_m3h)
        self.assertGreater(ro.shaft.bore_mm, twin.shaft.bore_mm)
        self.assertEqual(ro.shaft.outer_diameter_mm, twin.shaft.outer_diameter_mm)

    def test_design_eva_follows_the_film(self):
        p = self.es.particle
        self.assertEqual(p.film_um, db.EVA_RESIDUAL_FILM_UM)
        self.assertAlmostEqual(p.content, 0.02, places=3)
        self.assertAlmostEqual(
            self.es.requirement.freed_eva_tph,
            p.content * db.FEED.peak_tph * db.PILOT_EVA_REMOVAL_TARGET,
        )

    def test_attachment_efficiency_comes_from_the_silver_rougher(self):
        ea = eva_attachment_efficiency()
        self.assertEqual(self.es.attachment_efficiency, ea)
        self.assertTrue(0.1 < ea < 0.3)

    def test_meets_the_flotation_feed_limit(self):
        es = self.es
        self.assertTrue(es.meets_requirement)
        self.assertLessEqual(
            es.residual_eva_tph(es.result_peak), es.requirement.allowance_tph
        )
        self.assertLess(
            es.residual_eva_tph(es.result_avg), es.residual_eva_tph(es.result_peak)
        )

    def test_silver_loss_is_entrainment_only_and_below_limit(self):
        es = self.es
        self.assertTrue(es.ag_loss_ok)
        # 포수제가 없으므로 Ag 는 EVA 속도상수와 무관하다 — 수분 동반만.
        slow = solve_eva_circuit(db.FEED, db.FEED.peak_tph, 0.009, 0.05)
        fast = solve_eva_circuit(db.FEED, db.FEED.peak_tph, 0.009, 5.0)
        self.assertAlmostEqual(slow.recovery("Ag"), fast.recovery("Ag"), places=9)
        self.assertAlmostEqual(slow.recovery("Ag"), slow.recovery("Si"), places=9)

    def test_mass_balance_closes(self):
        for res in (self.es.result_peak, self.es.result_avg):
            self.assertLess(res.mass_balance_error_tph(), 1e-9)

    def test_recovery_rises_with_flake_size(self):
        recoveries = [r for _, r in self.es.size_recovery]
        self.assertEqual(recoveries, sorted(recoveries))
        self.assertLess(recoveries[0], 0.5)   # 5 µm 는 절반도 못 잡는다
        self.assertGreater(recoveries[-1], 0.99)

    def test_thicker_film_needs_more_but_floats_better(self):
        cases = self.es.film_cases
        self.assertEqual([c.film_um for c in cases], list(db.EVA_FILM_CASES_UM))
        for a, b in zip(cases, cases[1:]):
            self.assertGreater(b.required_recovery, a.required_recovery)
            self.assertGreater(b.recovery, a.recovery)
            self.assertGreater(b.diameter_um, a.diameter_um)
        self.assertTrue(all(c.ok for c in cases))

    def test_batch_limits_are_ordered_and_consistent(self):
        lim = self.es.limits
        self.assertLess(lim.peak_min, lim.average_min)
        self.assertLess(lim.peak_min, lim.extra_cell_min)
        # 한계 t90 의 속도상수로 풀면 요구 제거율에 닿는다
        k_batch = math.log(10.0) / lim.peak_min
        res = solve_eva_circuit(
            db.FEED, db.FEED.peak_tph, self.es.requirement.freed_eva_tph,
            k_batch * db.PLANT_SCALE_FACTOR,
        )
        self.assertAlmostEqual(res.recovery(EVA), lim.required_recovery, places=6)
        # 설계 박편은 그 한계 안에 있다 (요구를 만족하므로)
        design_t90 = math.log(10.0) / (self.es.rate_constant_1_min / db.PLANT_SCALE_FACTOR)
        self.assertLess(design_t90, lim.peak_min)

    def test_installed_power(self):
        es = self.es
        self.assertAlmostEqual(
            es.installed_kw,
            es.rougher.impeller.motor_rating_kw * es.rougher.cells_in_series
            + es.cleaner.impeller.motor_rating_kw
            + es.blower_rating_kw
            + es.pump_kw,
        )

    def test_flotation_air_dilutes_hydrogen(self):
        es = self.es
        self.assertAlmostEqual(
            es.tolerable_al_reaction_kg_h,
            tolerable_aluminium_reaction_kg_h(
                es.design_air_m3h, db.H2_LEL_VOL, db.H2_DESIGN_LEL_FRACTION
            ),
        )

    def test_bag_takes_the_upper_bound(self):
        """백은 AS-1 이 EVA 를 전부 뗐을 때로 잡는다 — 설계 부하보다 크다."""
        bag, es = self.es.bag, self.es
        self.assertGreater(bag.eva_tph, es.result_peak.concentrate.component_tph(EVA))
        self.assertGreater(bag.change_interval_h, 8.0)   # 교대당 한 번 이상 바꾸지 않는다

    def test_bypass_and_frother(self):
        self.assertIn(db.EVA_ROUGHER_TAG, self.es.bypass)
        self.assertIn(db.DILUTION_BOX_TAG, self.es.bypass)
        self.assertIn("CT-1", self.es.bypass)
        mibc = next(r for r in db.REAGENTS if r.role == "기포제")
        self.assertIn(db.EVA_ROUGHER_TAG, mibc.addition_point)


class TestPlantIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant = build_plant()

    def test_separation_is_part_of_the_pretreatment(self):
        pre = self.plant.pretreatment
        self.assertEqual(pre.eva.rougher.tag, db.EVA_ROUGHER_TAG)
        self.assertEqual(pre.eva.cleaner.tag, db.EVA_CLEANER_TAG)
        self.assertAlmostEqual(pre.installed_kw, pre.attrition_kw + pre.eva.installed_kw)

    def test_limit_keeps_both_options_above_the_guarantee(self):
        allowance = self.plant.pretreatment.eva.requirement.allowance_tph
        rp, mp = self.plant.rfc.performance_peak, self.plant.mechanical.result_peak
        for c_tph, grade in (
            (rp.concentrate_dry_tph, rp.concentrate_grade("Ag")),
            (mp.concentrate.dry_tph, mp.concentrate.grade_fraction("Ag")),
        ):
            self.assertGreaterEqual(
                concentrate_grade_with_eva(c_tph, grade, allowance),
                db.CONCENTRATE_GRADE_GUARANTEE,
            )

    def test_limit_is_about_half_of_the_rfc_margin(self):
        rp = self.plant.rfc.performance_peak
        margin = grade_margin_tph(
            rp.concentrate_dry_tph, rp.concentrate_grade("Ag"), db.CONCENTRATE_GRADE_GUARANTEE
        )
        share = self.plant.pretreatment.eva.requirement.allowance_tph / margin
        self.assertTrue(0.4 < share < 0.6, share)


if __name__ == "__main__":
    unittest.main()
