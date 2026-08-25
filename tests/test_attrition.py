"""어트리션 스크러버 설계 검증.

이 설비의 핵심 주장은 세 가지다.

1. **고체 농도가 전부다** — 체적분율이 50 vol% 부근이어야 입자끼리 닿는다.
2. **성능 크레딧이 없다** — 어트리션을 넣어도 계산서의 회수율·품위·약제
   투입량은 하나도 달라지지 않아야 한다. 문헌 근거가 없기 때문이다.
3. **물수지를 바꾸지 않는다** — 희석수는 부선 농도를 맞추려고 어차피 들어가던
   물이므로, 신수 보충량은 그대로여야 한다.

셋 다 여기서 검증한다.
"""

import math
import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design.attrition import (
    STANDARD_CELL_M3,
    AttritionCellGeometry,
    concentrate_grade_ceiling,
    dilution_box,
    octagon_area_m2,
    short_circuit_fraction,
    size_attrition,
    solids_mass_fraction_for_volume_fraction,
)
from flotation_design.feed import PulpProperties
from flotation_design.plant import build_plant, build_pretreatment
from flotation_design.sizing import torsional_section_modulus_m3

SG = db.FEED.solids_specific_gravity


class TestGeometryHelpers(unittest.TestCase):
    def test_octagon_area_matches_regular_polygon_formula(self):
        # 정팔각형: 변 길이 a, across-flats W = a(1+sqrt2), 면적 = 2(1+sqrt2)a^2
        a = 0.17
        width = a * (1.0 + math.sqrt(2.0))
        self.assertAlmostEqual(
            octagon_area_m2(width), 2.0 * (1.0 + math.sqrt(2.0)) * a**2, places=12
        )

    def test_octagon_area_is_between_inscribed_and_circumscribed_circles(self):
        w = 0.39
        inscribed = math.pi * w**2 / 4.0
        circumscribed = math.pi * (w / math.cos(math.pi / 8.0)) ** 2 / 4.0
        self.assertGreater(octagon_area_m2(w), inscribed)
        self.assertLess(octagon_area_m2(w), circumscribed)

    def test_octagon_area_rejects_nonpositive(self):
        with self.assertRaises(ValueError):
            octagon_area_m2(0.0)

    def test_cell_geometry_volumes(self):
        g = AttritionCellGeometry(across_flats_m=0.39, depth_m=0.47, freeboard_m=0.10)
        self.assertAlmostEqual(g.working_volume_m3, g.plan_area_m2 * 0.47, places=12)
        self.assertAlmostEqual(g.shell_height_m, 0.57, places=12)
        self.assertGreater(g.shell_volume_m3, g.working_volume_m3)
        self.assertGreater(g.circumscribed_diameter_m, g.across_flats_m)

    def test_cell_geometry_rejects_bad_dimensions(self):
        with self.assertRaises(ValueError):
            AttritionCellGeometry(across_flats_m=0.0, depth_m=0.4, freeboard_m=0.1)
        with self.assertRaises(ValueError):
            AttritionCellGeometry(across_flats_m=0.4, depth_m=0.4, freeboard_m=-0.1)


class TestResidenceDistribution(unittest.TestCase):
    """단락류 — 셀을 2단으로 두는 근거."""

    def test_single_tank_matches_analytic_cstr(self):
        self.assertAlmostEqual(
            short_circuit_fraction(1, 0.5), 1.0 - math.exp(-0.5), places=12
        )

    def test_more_cells_reduce_short_circuiting(self):
        values = [short_circuit_fraction(n, 0.5) for n in (1, 2, 3, 4)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_second_cell_earns_more_than_the_third(self):
        """2단으로 얻는 개선이 3단으로 얻는 것보다 크다 — 2단에서 끊는 근거."""
        first = short_circuit_fraction(1) - short_circuit_fraction(2)
        second = short_circuit_fraction(2) - short_circuit_fraction(3)
        self.assertGreater(first, second)

    def test_full_mean_residence_is_never_reached_by_everything(self):
        self.assertLess(short_circuit_fraction(2, 1.0), 1.0)
        self.assertGreater(short_circuit_fraction(2, 1.0), 0.0)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            short_circuit_fraction(0)
        with self.assertRaises(ValueError):
            short_circuit_fraction(2, -0.1)


class TestGradeCeiling(unittest.TestCase):
    def test_design_carry_ratio_reproduces_the_literature_ceiling(self):
        """r = 1.1 → 47.6 wt% — 문헌의 두 최고 품위(48.8 / 46.7)가 멈춘 자리."""
        self.assertAlmostEqual(
            concentrate_grade_ceiling(db.COMPOSITE_CARRY_RATIO), 1.0 / 2.1, places=12
        )

    def test_lower_carry_ratio_raises_the_ceiling(self):
        ceilings = [concentrate_grade_ceiling(r) for r in db.ATTRITION_CARRY_RATIO_CASES]
        self.assertEqual(ceilings, sorted(ceilings))
        self.assertGreater(ceilings[-1], ceilings[0])

    def test_fully_liberated_silver_has_no_ceiling(self):
        self.assertAlmostEqual(concentrate_grade_ceiling(0.0), 1.0, places=12)

    def test_rejects_negative(self):
        with self.assertRaises(ValueError):
            concentrate_grade_ceiling(-0.1)


class TestSolidsFractionConversion(unittest.TestCase):
    def test_round_trip_against_pulp_properties(self):
        w = solids_mass_fraction_for_volume_fraction(0.40, SG)
        pulp = PulpProperties(dry_tph=1.0, solids_sg=SG, solids_mass_fraction=w)
        self.assertAlmostEqual(pulp.solids_volume_fraction, 0.40, places=12)

    def test_denser_solids_need_a_higher_mass_fraction(self):
        """같은 체적분율이라도 무거운 고체는 질량으로 더 많이 넣어야 한다."""
        self.assertGreater(
            solids_mass_fraction_for_volume_fraction(0.40, 10.49),
            solids_mass_fraction_for_volume_fraction(0.40, 2.33),
        )

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            solids_mass_fraction_for_volume_fraction(0.0, SG)
        with self.assertRaises(ValueError):
            solids_mass_fraction_for_volume_fraction(0.4, 0.0)


class TestScrubberSizing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pre = build_pretreatment()
        cls.sc = cls.pre.scrubber

    # -- 고체 농도 --------------------------------------------------------
    def test_scrubbing_density_puts_particles_in_contact(self):
        """어트리션의 전제 — 고체 체적분율 50 vol% 부근."""
        self.assertGreater(self.sc.solids_volume_fraction, 0.45)
        self.assertLess(self.sc.solids_volume_fraction, 0.55)
        self.assertTrue(self.sc.solids_volume_fraction_ok)

    def test_absolute_floor_is_below_the_design_density(self):
        self.assertLess(self.sc.minimum_solids_mass_fraction, self.sc.solids_mass_fraction)
        self.assertGreater(self.sc.minimum_solids_mass_fraction, 0.5)

    def test_mill_discharge_requirement_equals_scrubbing_density(self):
        self.assertAlmostEqual(
            db.ATTRITION_MILL_DISCHARGE_MIN_SOLIDS_WT, self.sc.solids_mass_fraction
        )

    def test_scrubbing_slurry_is_far_smaller_than_flotation_slurry(self):
        """묽히기 전에 문지르는 이유 — 같은 고체가 1/10 이하 체적에 들어간다."""
        flotation = PulpProperties(
            dry_tph=db.FEED.peak_tph,
            solids_sg=SG,
            solids_mass_fraction=db.FEED.solids_mass_fraction,
        )
        self.assertLess(
            self.sc.pulp.volumetric_flow_m3h, flotation.volumetric_flow_m3h / 10.0
        )

    # -- 규격 -------------------------------------------------------------
    def test_two_cells_in_series(self):
        self.assertEqual(self.sc.cells, 2)
        self.assertGreaterEqual(self.sc.cells, 2)

    def test_governed_by_smallest_commercial_size(self):
        self.assertEqual(self.sc.governed_by, "상용 최소 기종")
        self.assertEqual(self.sc.nominal_cell_m3, STANDARD_CELL_M3[0])

    def test_fabricated_cell_is_not_smaller_than_the_selected_size(self):
        self.assertGreaterEqual(
            self.sc.geometry.working_volume_m3, self.sc.nominal_cell_m3
        )

    def test_actual_residence_exceeds_design_residence(self):
        self.assertGreaterEqual(
            self.sc.residence_min(db.FEED.peak_tph), self.sc.design_residence_min
        )

    def test_lower_throughput_gives_longer_residence(self):
        self.assertGreater(
            self.sc.residence_min(db.FEED.average_tph),
            self.sc.residence_min(db.FEED.peak_tph),
        )

    # -- 구동부 -----------------------------------------------------------
    def test_design_tip_speed_is_inside_the_band(self):
        self.assertTrue(self.sc.drive.tip_speed_ok)
        low, high = db.ATTRITION_TIP_SPEED_RANGE_M_S
        self.assertGreaterEqual(self.sc.drive.tip_speed_m_s, low)
        self.assertLessEqual(self.sc.drive.tip_speed_m_s, high)

    def test_power_follows_the_cube_law(self):
        d = self.sc.drive
        self.assertAlmostEqual(
            d.power_w_at_tip_speed(d.tip_speed_m_s), d.absorbed_power_w, places=9
        )
        self.assertAlmostEqual(
            d.power_w_at_tip_speed(2.0 * d.tip_speed_m_s),
            8.0 * d.absorbed_power_w,
            places=6,
        )

    def test_motor_covers_the_absorbed_power_with_service_factor(self):
        d = self.sc.drive
        self.assertGreaterEqual(
            d.motor_rating_kw * 1000.0, d.absorbed_power_w * d.service_factor
        )

    def test_vfd_ceiling_never_overloads_the_motor(self):
        d = self.sc.drive
        self.assertGreaterEqual(d.tip_speed_ceiling_m_s, d.tip_speed_m_s)
        self.assertLessEqual(
            d.power_w_at_tip_speed(d.tip_speed_ceiling_m_s) * d.service_factor,
            d.motor_rating_kw * 1000.0 + 1e-6,
        )

    def test_specific_power_matches_commercial_machines(self):
        low, high = db.ATTRITION_SPECIFIC_POWER_RANGE_KW_M3
        self.assertGreaterEqual(self.sc.specific_power_kw_m3, low)
        self.assertLessEqual(self.sc.specific_power_kw_m3, high)
        self.assertTrue(self.sc.specific_power_ok)

    # -- 비에너지 ---------------------------------------------------------
    def test_specific_energy_at_peak_is_inside_the_target_band(self):
        low, high = self.sc.specific_energy_range_kwh_t
        e = self.sc.specific_energy_kwh_t(db.FEED.peak_tph)
        self.assertGreaterEqual(e, low)
        self.assertLessEqual(e, high)

    def test_design_speed_over_scrubs_at_average_throughput(self):
        """처리량이 줄면 t 당 에너지가 커진다 — VFD 를 두는 이유."""
        _, high = self.sc.specific_energy_range_kwh_t
        self.assertGreater(self.sc.specific_energy_kwh_t(db.FEED.average_tph), high)

    def test_recommended_speed_brings_energy_back_into_the_band(self):
        low, high = self.sc.specific_energy_range_kwh_t
        for tph in (db.FEED.peak_tph, db.FEED.average_tph):
            with self.subTest(tph=tph):
                v = self.sc.recommended_tip_speed_m_s(tph)
                self.assertGreaterEqual(v, self.sc.drive.tip_speed_min_m_s)
                self.assertLessEqual(v, self.sc.drive.tip_speed_ceiling_m_s)
                e = self.sc.specific_energy_kwh_t(tph, v)
                self.assertLessEqual(e, high + 1e-9)
                self.assertGreaterEqual(e, low)

    def test_minimum_throughput_is_where_the_speed_floor_bites(self):
        _, high = self.sc.specific_energy_range_kwh_t
        self.assertAlmostEqual(
            self.sc.specific_energy_kwh_t(
                self.sc.minimum_dry_tph, self.sc.drive.tip_speed_min_m_s
            ),
            high,
            places=9,
        )
        self.assertLess(self.sc.minimum_dry_tph, db.FEED.average_tph)

    def test_specific_energy_rejects_zero_throughput(self):
        with self.assertRaises(ValueError):
            self.sc.specific_energy_kwh_t(0.0)

    # -- 축 ---------------------------------------------------------------
    def test_shaft_is_safe(self):
        self.assertTrue(self.sc.shaft.is_safe)

    def test_shaft_is_governed_by_rotor_dynamics_not_torsion(self):
        """토크는 여유가 크지만 외팔보 끝 로터 질량이 축을 굵게 만든다."""
        sh = self.sc.shaft
        self.assertEqual(sh.governed_by, "로터동역학")
        self.assertLess(sh.shear_stress_mpa, sh.allowable_shear_mpa * 0.25)

    def test_shaft_shear_matches_the_selected_diameter(self):
        sh = self.sc.shaft
        self.assertAlmostEqual(
            sh.shear_stress_mpa,
            sh.torque_nm / torsional_section_modulus_m3(sh.outer_diameter_mm) / 1e6,
            places=9,
        )

    def test_shaft_torque_carries_the_startup_service_factor(self):
        sh, d = self.sc.shaft, self.sc.drive
        self.assertAlmostEqual(
            sh.torque_nm,
            d.absorbed_power_w / (2.0 * math.pi * d.speed_rpm / 60.0) * sh.service_factor,
            places=9,
        )
        self.assertGreaterEqual(sh.service_factor, 2.0)

    def test_critical_speed_keeps_its_margin(self):
        sh = self.sc.shaft
        self.assertGreaterEqual(sh.critical_speed_ratio, sh.minimum_critical_speed_ratio)
        self.assertGreater(sh.critical_speed_rpm, self.sc.drive.speed_rpm)

    # -- 종합 -------------------------------------------------------------
    def test_design_is_adequate(self):
        self.assertTrue(self.sc.is_adequate)

    def test_installed_power_is_motors_plus_pump(self):
        self.assertAlmostEqual(
            self.sc.installed_kw,
            self.sc.drive.motor_rating_kw * self.sc.cells + self.sc.feed_pump_kw,
        )

    def test_gravity_fed_by_default(self):
        """50 vol% 슬러리는 원심펌프로 보낼 수 없다 — 중력 급광이 기본."""
        self.assertEqual(self.sc.feed_pump_kw, 0.0)


class TestScrubberSizingRules(unittest.TestCase):
    """설계 규칙이 다른 조건에서도 성립하는지."""

    def test_large_throughput_is_governed_by_residence_time(self):
        big = size_attrition("AS-X", "대형", 5.0, SG)
        self.assertEqual(big.governed_by, "체류시간")
        self.assertGreaterEqual(big.residence_min(5.0), big.design_residence_min)
        self.assertTrue(big.is_adequate)

    def test_specific_energy_falls_as_throughput_rises(self):
        small = size_attrition("AS-A", "소형", 0.5, SG)
        big = size_attrition("AS-B", "대형", 5.0, SG)
        self.assertLess(
            big.specific_energy_kwh_t(5.0), small.specific_energy_kwh_t(0.5)
        )

    def test_single_cell_is_rejected(self):
        with self.assertRaises(ValueError):
            size_attrition("AS-X", "1단", 0.5, SG, cells=1)

    def test_rejects_nonpositive_throughput(self):
        with self.assertRaises(ValueError):
            size_attrition("AS-X", "x", 0.0, SG)

    def test_rejects_impossible_solids_fraction(self):
        with self.assertRaises(ValueError):
            size_attrition("AS-X", "x", 0.5, SG, solids_mass_fraction=1.0)

    def test_rejects_nonpositive_residence(self):
        with self.assertRaises(ValueError):
            size_attrition("AS-X", "x", 0.5, SG, residence_min=0.0)

    def test_rejects_tip_speed_outside_the_band(self):
        with self.assertRaises(ValueError):
            size_attrition(
                "AS-X", "x", 0.5, SG, design_tip_speed_m_s=12.0,
                tip_speed_range_m_s=(6.0, 9.0),
            )

    def test_rejects_scale_beyond_the_commercial_series(self):
        with self.assertRaises(ValueError):
            size_attrition("AS-X", "x", 500.0, SG)


class TestDilutionBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.box = build_pretreatment().dilution

    def test_dilution_water_is_the_difference_between_the_two_densities(self):
        b = self.box
        self.assertAlmostEqual(
            b.dilution_water_m3h, b.outlet_water_tph - b.inlet_water_tph, places=12
        )
        self.assertGreater(b.dilution_water_m3h, 0.0)

    def test_outlet_matches_the_flotation_feed_density(self):
        self.assertAlmostEqual(self.box.outlet_solids_wt, db.FEED.solids_mass_fraction)
        self.assertAlmostEqual(self.box.inlet_solids_wt, db.ATTRITION_SOLIDS_WT)

    def test_solids_pass_through_unchanged(self):
        self.assertAlmostEqual(self.box.dry_tph, db.FEED.peak_tph)

    def test_box_volume_covers_the_working_volume_with_freeboard(self):
        self.assertGreater(self.box.box_volume_m3, self.box.working_volume_m3)
        self.assertAlmostEqual(
            self.box.working_volume_m3,
            self.box.outlet_m3h * self.box.residence_min / 60.0,
            places=12,
        )

    def test_agitator_is_specified(self):
        """P80 66 um 입자는 2 분이면 수십 cm 를 가라앉는다 — 교반이 필요하다."""
        self.assertGreater(self.box.agitator_kw, 0.0)

    def test_rejects_concentrating_instead_of_diluting(self):
        with self.assertRaises(ValueError):
            dilution_box("DB-X", "x", 0.5, SG, inlet_solids_wt=0.07, outlet_solids_wt=0.70)

    def test_rejects_nonpositive_throughput(self):
        with self.assertRaises(ValueError):
            dilution_box("DB-X", "x", 0.0, SG, inlet_solids_wt=0.70, outlet_solids_wt=0.07)


class TestPlantIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant = build_plant()

    def test_pretreatment_is_part_of_the_plant(self):
        pre = self.plant.pretreatment
        self.assertEqual(pre.scrubber.tag, db.ATTRITION_TAG)
        self.assertEqual(pre.dilution.tag, db.DILUTION_BOX_TAG)
        self.assertIn(db.ATTRITION_TAG, pre.bypass)
        self.assertIn(db.DILUTION_BOX_TAG, pre.bypass)

    def test_pretreatment_power_is_counted_separately_from_both_options(self):
        """공용 설비이므로 어느 안의 설치 전력에도 들어가지 않는다."""
        pre = self.plant.pretreatment
        self.assertAlmostEqual(
            pre.installed_kw, pre.scrubber.installed_kw + pre.dilution.agitator_kw
        )
        for option in (self.plant.rfc, self.plant.mechanical):
            with self.subTest(option=type(option).__name__):
                self.assertAlmostEqual(
                    self.plant.total_installed_kw(option),
                    option.installed_kw + pre.installed_kw,
                )
                self.assertGreater(
                    self.plant.total_installed_kw(option), option.installed_kw
                )

    def test_pretreatment_is_a_large_share_of_plant_power(self):
        """성능 크레딧이 0 인 설비가 전력의 상당 부분을 쓴다 — 바이패스의 근거."""
        pre = self.plant.pretreatment
        share = pre.installed_kw / self.plant.total_installed_kw(self.plant.rfc)
        self.assertGreater(share, 0.30)

    def test_dilution_water_matches_the_flotation_feed_requirement(self):
        """희석수는 부선 농도를 맞추려고 어차피 들어가던 물이다."""
        f = self.plant.feed
        flotation_water = f.peak_tph * (1.0 - f.solids_mass_fraction) / f.solids_mass_fraction
        scrub_water = f.peak_tph * (1.0 - db.ATTRITION_SOLIDS_WT) / db.ATTRITION_SOLIDS_WT
        self.assertAlmostEqual(
            self.plant.pretreatment.dilution_water_m3h,
            flotation_water - scrub_water,
            places=12,
        )

    def test_water_supply_covers_the_dilution_demand_for_both_options(self):
        pre = self.plant.pretreatment
        for option in (self.plant.rfc, self.plant.mechanical):
            with self.subTest(option=type(option).__name__):
                self.assertTrue(pre.water_supply_ok(option))

    def test_attrition_takes_no_performance_credit(self):
        """문헌 근거가 없으므로 성능·약제에 어떤 이득도 반영하지 않는다."""
        self.assertEqual(db.ATTRITION_PERFORMANCE_CREDIT, 1.0)
        self.assertAlmostEqual(
            self.plant.rfc.performance_peak.recovery("Ag"), db.RFC_AG_RECOVERY
        )
        for reagent in db.REAGENTS:
            if reagent.basis == "solids":
                self.assertAlmostEqual(reagent.dose, 300.0)

    def test_throughput_override_still_produces_a_sound_design(self):
        from dataclasses import replace

        plant = build_plant(replace(db.FEED, average_tph=0.6, peak_tph=1.0))
        self.assertTrue(plant.pretreatment.scrubber.is_adequate)
        self.assertGreater(plant.pretreatment.dilution_water_m3h, 0.0)


class TestReportSection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flotation_design.report import render

        cls.text = render(build_plant())

    def test_section_and_subsections_are_present(self):
        for heading in (
            "## 2. 전처리 — 어트리션 스크러버",
            "### 2.1",
            "### 2.2",
            "### 2.3",
            "### 2.4",
            "### 2.5",
        ):
            self.assertIn(heading, self.text, heading)

    def test_later_sections_were_renumbered(self):
        for heading in ("## 3. 1안", "## 4. 2안", "## 5. 두 안 비교", "## 8. 수치해석"):
            self.assertIn(heading, self.text, heading)

    def test_equipment_tags_appear(self):
        self.assertIn(db.ATTRITION_TAG, self.text)
        self.assertIn(db.DILUTION_BOX_TAG, self.text)

    def test_discloses_that_there_is_no_performance_credit(self):
        self.assertIn("성능 크레딧 없음", self.text)
        self.assertIn("ATTRITION_PERFORMANCE_CREDIT", self.text)

    def test_states_the_bypass(self):
        self.assertIn("바이패스", self.text)

    def test_reports_the_acceptance_criterion_for_fines(self):
        self.assertIn(f"{db.ATTRITION_FINES_ACCEPTANCE_PP:.0f} %p", self.text)


if __name__ == "__main__":
    unittest.main()
