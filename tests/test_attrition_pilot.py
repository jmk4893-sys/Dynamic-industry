"""파일럿 어트리션 셀 PAS-1 검증.

이 시험 셀이 지켜야 할 것은 네 가지다.

1. **방식 선정이 수치로 선다** — 로터-스테이터의 유체 전단은 EVA 강도에
   수백 배 모자라고, 미분의 t 당 표면적은 실리카사의 10배를 넘는다.
2. **결과가 AS-1 로 넘어간다** — 기하 상사, 같은 농도·주속, 비에너지는
   남은 고체 기준으로 쌓이고, 회분 → 연속 환산은 1차 완전혼합조 직렬식과
   맞는다.
3. **시험 범위 전체를 돈다** — 모터·축·토크센서·재킷이 최고 주속, 최저 설정
   온도에서도 성립하고, 시료를 다 떠도 임펠러가 잠겨 있다.
4. **안전** — 수소 배기는 정상상태 희석식과 맞고, 접액부에 유기 재질이 없다.
"""

import math
import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design.attrition_pilot import (
    AL_MOLAR_MASS_KG_MOL,
    MOLAR_VOLUME_NM3_MOL,
    adiabatic_rise_k_per_kwh_t,
    continuous_energy_factor,
    fluid_shear_stress_pa,
    hydrogen_from_aluminium_nm3,
    relative_viscosity,
    size_pilot_cell,
    specific_surface_m2_kg,
    tolerable_aluminium_reaction_kg_h,
    ventilation_for_hydrogen_m3h,
)
from flotation_design.plant import (
    build_mechanism_screen,
    build_pilot,
    build_pilot_scale_up,
    build_plant,
    build_pretreatment,
)

SG = db.FEED.solids_specific_gravity


class TestMechanismScreen(unittest.TestCase):
    def test_relative_viscosity_is_one_for_pure_liquid_and_rises(self):
        self.assertAlmostEqual(relative_viscosity(0.0), 1.0, places=12)
        values = [relative_viscosity(phi) for phi in (0.1, 0.3, 0.5, 0.6)]
        self.assertEqual(values, sorted(values))

    def test_relative_viscosity_rejects_packed_bed(self):
        with self.assertRaises(ValueError):
            relative_viscosity(0.64)

    def test_fluid_shear_is_viscosity_times_rate(self):
        phi = 0.3
        self.assertAlmostEqual(
            fluid_shear_stress_pa(1.0e4, phi), 1.0e-3 * relative_viscosity(phi) * 1.0e4,
            places=9,
        )

    def test_rotor_stator_falls_hundreds_of_times_short_of_eva_strength(self):
        m = build_mechanism_screen()
        # 70 wt% 슬러리, 1e5 /s 에서도 kPa 급
        self.assertLess(m.fluid_shear_pa, 2.0e3)
        self.assertGreater(m.shear_shortfall, 500.0)

    def test_specific_surface_is_six_over_rho_d(self):
        self.assertAlmostEqual(specific_surface_m2_kg(50e-6, 2.5), 6.0 / (2500.0 * 50e-6))

    def test_fine_fraction_has_over_ten_times_the_surface_of_sand(self):
        m = build_mechanism_screen()
        self.assertAlmostEqual(m.representative_size_um, math.sqrt(31.0 * 75.0), places=9)
        self.assertGreater(m.surface_ratio_to_sand, 10.0)
        self.assertLess(m.surface_ratio_to_sand, 15.0)


class TestContinuousConversion(unittest.TestCase):
    def test_single_cstr_matches_closed_form(self):
        # 1기: kE = X/(1-X) = 9, 회분: kE = ln 10
        self.assertAlmostEqual(continuous_energy_factor(0.9, 1), 9.0 / math.log(10.0), places=12)

    def test_factor_reproduces_target_in_tanks_in_series(self):
        # 1차 완전혼합조 n 기 직렬의 잔류분율 (1 + kE/n)^-n 이 목표와 같아야 한다
        for n in (1, 2, 3, 5):
            k_batch = -math.log(1.0 - 0.9)
            k_cont = continuous_energy_factor(0.9, n) * k_batch
            self.assertAlmostEqual((1.0 + k_cont / n) ** (-n), 0.1, places=12)

    def test_factor_falls_toward_plug_flow(self):
        factors = [continuous_energy_factor(0.9, n) for n in (1, 2, 3, 10, 1000)]
        self.assertEqual(factors, sorted(factors, reverse=True))
        self.assertLess(factors[-1], 1.01)
        self.assertGreater(factors[-1], 1.0)

    def test_factor_rejects_bad_input(self):
        for args in ((0.0, 2), (1.0, 2), (0.9, 0)):
            with self.assertRaises(ValueError):
                continuous_energy_factor(*args)


class TestHydrogen(unittest.TestCase):
    def test_stoichiometry(self):
        # 2Al + 6H2O -> 2Al(OH)3 + 3H2 : Al 1 mol 당 H2 1.5 mol
        expected = 1.0 / AL_MOLAR_MASS_KG_MOL * 1.5 * MOLAR_VOLUME_NM3_MOL
        self.assertAlmostEqual(hydrogen_from_aluminium_nm3(1.0), expected, places=12)
        self.assertAlmostEqual(hydrogen_from_aluminium_nm3(1.0), 1.246, places=3)

    def test_ventilation_holds_headspace_at_design_fraction_of_lel(self):
        h2 = 0.5
        vent = ventilation_for_hydrogen_m3h(h2, db.H2_LEL_VOL, db.H2_DESIGN_LEL_FRACTION)
        self.assertAlmostEqual(h2 / vent, db.H2_LEL_VOL * db.H2_DESIGN_LEL_FRACTION, places=12)

    def test_tolerable_reaction_inverts_ventilation(self):
        al = tolerable_aluminium_reaction_kg_h(30.0, db.H2_LEL_VOL, db.H2_DESIGN_LEL_FRACTION)
        vent = ventilation_for_hydrogen_m3h(
            hydrogen_from_aluminium_nm3(al), db.H2_LEL_VOL, db.H2_DESIGN_LEL_FRACTION
        )
        self.assertAlmostEqual(vent, 30.0, places=9)

    def test_pilot_vent_tolerates_a_tenth_of_batch_aluminium_per_hour(self):
        p = build_pilot()
        self.assertAlmostEqual(p.aluminium_in_batch_kg, p.batch_dry_kg * 0.10, places=12)
        self.assertGreater(p.tolerable_aluminium_reaction_per_h, 0.10)


class TestHeat(unittest.TestCase):
    def test_adiabatic_rise_is_an_energy_balance(self):
        w, cp = 0.70, 0.73
        rise = adiabatic_rise_k_per_kwh_t(w, cp)
        # 고체 1 t + 물 (1-w)/w t 가 3600 kJ 를 받는다
        heat_capacity = 1000.0 * cp + 1000.0 * (1.0 - w) / w * 4.18
        self.assertAlmostEqual(rise * heat_capacity, 3600.0, places=9)
        self.assertAlmostEqual(rise, 1.43, places=2)

    def test_uncontrolled_heating_would_swamp_the_temperature_levels(self):
        p = build_pilot()
        spread = max(p.temperatures_c) - min(p.temperatures_c)
        self.assertGreater(p.adiabatic_rise_at_max_energy_k, spread)

    def test_jacket_holds_lowest_setpoint_at_highest_tip_speed(self):
        p = build_pilot()
        top = p.max_test_tip_speed_m_s
        removed = p.jacket_u_w_m2k * p.jacket_area_m2 * p.coolant_approach_k(top)
        self.assertAlmostEqual(removed, p.power_w(top), places=6)
        self.assertGreaterEqual(p.worst_coolant_supply_c, db.PILOT_TCU_MIN_SUPPLY_C)
        self.assertTrue(p.temperature_control_ok)


class TestPilotCell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = build_pilot()
        cls.as1 = build_pretreatment().scrubber

    def test_batch_is_set_by_the_sampling_plan(self):
        p = self.p
        needed = p.samples_per_batch * p.sample_dry_kg / p.max_withdrawal
        self.assertGreaterEqual(p.batch_dry_kg, needed)
        self.assertLess(p.batch_dry_kg - needed, db.PILOT_BATCH_ROUND_KG)
        self.assertLessEqual(p.withdrawal_fraction, p.max_withdrawal)
        self.assertEqual(p.batch_dry_kg, 20.0)

    def test_batch_fills_the_cell_to_the_working_level(self):
        p = self.p
        self.assertAlmostEqual(
            p.geometry.plan_area_m2 * p.fill_level_m, p.slurry_volume_m3, places=12
        )
        self.assertAlmostEqual(p.slurry_kg - p.water_kg, p.batch_dry_kg, places=12)

    def test_geometric_similarity_with_as1(self):
        p, as1 = self.p, self.as1
        self.assertAlmostEqual(p.drive.diameter_m / p.geometry.across_flats_m,
                               db.ATTRITION_IMPELLER_RATIO, delta=0.02)
        self.assertAlmostEqual(p.depth_to_width, db.ATTRITION_DEPTH_TO_WIDTH, delta=0.06)
        self.assertLessEqual(p.depth_to_width, db.ATTRITION_DEPTH_TO_WIDTH)
        self.assertEqual(p.drive.impellers_per_shaft, as1.drive.impellers_per_shaft)
        self.assertEqual(p.drive.power_number, as1.drive.power_number)

    def test_same_pulp_and_tip_speed_as_as1(self):
        p, as1 = self.p, self.as1
        self.assertAlmostEqual(p.solids_volume_fraction, as1.solids_volume_fraction, places=12)
        self.assertGreaterEqual(p.solids_volume_fraction, p.minimum_solids_volume_fraction)
        self.assertAlmostEqual(p.drive.tip_speed_m_s, as1.drive.tip_speed_m_s, delta=0.1)

    def test_low_solids_level_is_the_contact_threshold(self):
        p = self.p
        self.assertAlmostEqual(p.low_solids_mass_fraction, self.as1.minimum_solids_mass_fraction,
                               places=12)
        self.assertLess(p.low_solids_mass_fraction, p.solids_mass_fraction)

    def test_specific_power_is_not_a_scale_up_variable(self):
        # 같은 주속에서 작은 셀의 체적당 동력이 더 크다 — P/V 는 v^3/D 로 움직인다
        p, as1 = self.p, self.as1
        tip = db.ATTRITION_DESIGN_TIP_SPEED_M_S
        self.assertGreater(p.specific_power_kw_m3(tip), as1.specific_power_kw_m3)

    def test_motor_does_not_cap_the_test_range(self):
        p = self.p
        self.assertGreaterEqual(p.drive.tip_speed_ceiling_m_s, p.max_test_tip_speed_m_s - 1e-9)
        # AS-1 은 모터가 VFD 상한을 막는다 — 시험 셀은 그러면 안 된다
        self.assertLess(self.as1.drive.tip_speed_ceiling_m_s, p.max_test_tip_speed_m_s)

    def test_shaft_is_checked_at_the_top_test_speed(self):
        p = self.p
        top_rpm = p.speed_rpm(p.max_test_tip_speed_m_s)
        self.assertAlmostEqual(p.shaft.check_speed_rpm, top_rpm, places=9)
        self.assertTrue(p.shaft.is_safe)

    def test_torque_sensor_carries_startup_and_resolves_lowest_speed(self):
        p = self.p
        self.assertGreaterEqual(p.torque_sensor_nm, p.shaft.torque_nm)
        smaller = [r for r in db.PILOT_TORQUE_SENSOR_SERIES_NM if r < p.torque_sensor_nm]
        self.assertTrue(all(r < p.shaft.torque_nm for r in smaller))
        self.assertGreater(p.lowest_torque_fraction, 0.10)

    def test_torque_is_power_over_angular_speed(self):
        p = self.p
        tip = 8.0
        omega = 2.0 * math.pi * p.speed_rpm(tip) / 60.0
        self.assertAlmostEqual(p.torque_nm(tip) * omega, p.power_w(tip), places=9)

    def test_impellers_stay_submerged_after_the_last_sample(self):
        p = self.p
        self.assertTrue(p.submergence_ok)
        last = p.schedule(db.ATTRITION_DESIGN_TIP_SPEED_M_S)[-1]
        self.assertGreater(last.fill_level_m - p.upper_impeller_elevation_m,
                           p.min_submergence_ratio * p.drive.diameter_m)

    def test_schedule_delivers_the_energy_points_on_remaining_solids(self):
        p = self.p
        for tip in p.test_tip_speeds_m_s:
            power_kw = p.power_w(tip) / 1000.0
            points = p.schedule(tip)
            self.assertEqual(len(points), p.samples_per_batch)
            self.assertEqual(points[0].elapsed_min, 0.0)
            energy = 0.0
            for before, after in zip(points, points[1:]):
                hours = (after.elapsed_min - before.elapsed_min) / 60.0
                energy += power_kw * hours / (after.dry_kg_before / 1000.0)
                self.assertAlmostEqual(energy, after.energy_kwh_t, places=9)
                self.assertAlmostEqual(before.dry_kg_before - after.dry_kg_before,
                                       p.sample_dry_kg, places=12)

    def test_design_speed_curve_fits_in_an_hour(self):
        self.assertLess(self.p.run_minutes(db.ATTRITION_DESIGN_TIP_SPEED_M_S), 60.0)

    def test_no_organic_wetted_parts(self):
        # AS-1 은 고무 라이닝·우레탄 피복 — 시험 셀은 의도적으로 금속만 쓴다
        self.assertIn("고무", db.ATTRITION_LINER)
        for word in ("고무", "우레탄", "라이닝 있음"):
            self.assertNotIn(word, self.p.wetted_material)

    def test_pilot_is_adequate(self):
        self.assertTrue(self.p.is_adequate)

    def test_pilot_is_not_plant_equipment(self):
        plant = build_plant()
        self.assertFalse(hasattr(plant, "pilot"))
        self.assertNotIn(db.PILOT_TAG, repr(plant.pretreatment))

    def test_rejects_bad_sampling_plan(self):
        kwargs = dict(
            tag="X", duty="x", solids_sg=SG, aluminium_mass_fraction=0.1,
            test_tip_speeds_m_s=(6.0, 7.0, 9.0), reference_tip_speed_m_s=7.0,
            temperatures_c=(20.0,),
        )
        with self.assertRaises(ValueError):
            size_pilot_cell(energy_points_kwh_t=(0.0, 2.0, 1.0), **kwargs)
        with self.assertRaises(ValueError):
            size_pilot_cell(energy_points_kwh_t=(), **kwargs)


class TestScaleUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.su = build_pilot_scale_up()
        cls.as1 = build_pretreatment().scrubber

    def test_factor_uses_as1_cell_count(self):
        su = self.su
        self.assertEqual(su.cells, self.as1.cells)
        self.assertAlmostEqual(su.energy_factor,
                               continuous_energy_factor(su.target_removal, su.cells), places=12)
        self.assertAlmostEqual(su.energy_factor, 1.878, places=3)

    def test_as1_capability_is_taken_at_its_vfd_ceiling(self):
        su, as1 = self.su, self.as1
        ceiling = as1.drive.tip_speed_ceiling_m_s
        self.assertAlmostEqual(su.as1_peak_kwh_t,
                               as1.specific_energy_kwh_t(db.FEED.peak_tph, ceiling), places=12)
        self.assertGreater(su.as1_peak_kwh_t, as1.specific_energy_kwh_t(db.FEED.peak_tph))

    def test_limits_are_capability_over_factor_and_ordered(self):
        su = self.su
        self.assertAlmostEqual(su.batch_limit_peak_kwh_t * su.energy_factor, su.as1_peak_kwh_t)
        self.assertLess(su.batch_limit_peak_kwh_t, su.batch_limit_peak_upsized_kwh_t)
        self.assertLess(su.batch_limit_peak_upsized_kwh_t, su.batch_limit_average_upsized_kwh_t)
        # 같은 주속이면 비에너지는 처리량에 반비례
        self.assertAlmostEqual(
            su.as1_average_upsized_kwh_t * su.average_tph,
            su.as1_peak_upsized_kwh_t * su.peak_tph, places=9,
        )

    def test_upsizing_the_motor_keeps_the_current_shaft(self):
        su = self.su
        self.assertGreater(su.upsized_motor_kw, self.as1.drive.motor_rating_kw)
        self.assertTrue(su.upsized_shaft_ok)


if __name__ == "__main__":
    unittest.main()
