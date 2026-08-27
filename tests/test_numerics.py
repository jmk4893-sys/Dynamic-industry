"""수치해석 모듈 검증 — 수력학 검산과 기동 과도응답.

hydrodynamics 는 해석해가 있는 극한(Stokes)과 물리적 부등식으로,
transient 는 정상상태 물질수지와의 폐합으로 검증한다.
"""

import math
import unittest

from . import _path  # noqa: F401

from flotation_design.hydrodynamics import (
    HydroAnalysis,
    analyse_cell,
    collision_efficiency,
    drag_coefficient,
    swarm_velocity,
    terminal_velocity,
)
from flotation_design.plant import build_mechanical_option
from flotation_design.transient import _effective_rate_1_min, simulate_startup


class TestTerminalVelocity(unittest.TestCase):
    def test_stokes_limit_matches_analytic_solution(self):
        # 10 µm 모래알 — Re << 1 이므로 Stokes 해와 일치해야 한다.
        d, rho = 10e-6, 2650.0
        analytic = (rho - 998.0) * 9.81 * d**2 / (18.0 * 1.0e-3)
        v = terminal_velocity(d, rho)
        self.assertAlmostEqual(abs(v), analytic, delta=analytic * 0.02)
        self.assertLess(v, 0)  # 침강은 음수

    def test_08mm_bubble_rises_at_about_9_cm_s(self):
        # 오염 계면 0.8 mm 기포의 강체구 해 — 문헌 8~12 cm/s 범위.
        v = terminal_velocity(0.8e-3, 1.2)
        self.assertGreater(v, 0.07)
        self.assertLess(v, 0.13)

    def test_bigger_bubble_rises_faster(self):
        self.assertGreater(terminal_velocity(1.5e-3, 1.2), terminal_velocity(0.5e-3, 1.2))

    def test_neutral_density_does_not_move(self):
        self.assertEqual(terminal_velocity(1e-3, 998.0), 0.0)

    def test_drag_blends_to_newton_regime(self):
        self.assertAlmostEqual(drag_coefficient(1e6), 0.44)
        # Stokes 극한: Cd -> 24/Re
        self.assertAlmostEqual(drag_coefficient(0.01), 24.0 / 0.01, delta=24.0 / 0.01 * 0.05)

    def test_swarm_is_slower_than_single_bubble(self):
        v1 = terminal_velocity(0.8e-3, 1.2)
        self.assertLess(swarm_velocity(v1, 0.15), v1)
        self.assertAlmostEqual(swarm_velocity(v1, 0.0), v1)


class TestCollisionEfficiency(unittest.TestCase):
    def test_scales_with_particle_size_squared(self):
        e1 = collision_efficiency(30e-6, 0.8e-3, 80.0)
        e2 = collision_efficiency(60e-6, 0.8e-3, 80.0)
        self.assertAlmostEqual(e2 / e1, 4.0, places=6)

    def test_small_particle_on_big_bubble_is_rarely_hit(self):
        self.assertLess(collision_efficiency(10e-6, 2.0e-3, 100.0), 0.005)


class TestHydroConsistency(unittest.TestCase):
    """설계 속도상수가 물리적으로 재현 가능한지 — 계산서 §7.1 의 검산."""

    @classmethod
    def setUpClass(cls):
        from flotation_design import design_basis as db

        cls.opt = build_mechanical_option()
        cls.k_fast_plant = db.FLOAT_MODELS["Ag"].k_fast * db.PLANT_SCALE_FACTOR
        cls.hydro = [
            analyse_cell(
                c.tag,
                c.aeration.superficial_gas_velocity_cm_s,
                c.aeration.bubble_sauter_mean_mm,
                c.geometry.gas_holdup,
                c.geometry.pulp_zone_height_m,
                cls.k_fast_plant,
            )
            for c in cls.opt.cells
        ]

    def test_implied_attachment_efficiency_is_physical(self):
        # Ea 가 (0, 1] 밖이면 설계 k 는 물리적으로 불가능한 값이다.
        for h in self.hydro:
            self.assertTrue(h.is_physically_consistent, h.tag)

    def test_implied_attachment_efficiency_in_literature_range(self):
        # 수십 µm 입자의 문헌 Ea 는 대략 0.1~0.3.
        for h in self.hydro:
            self.assertGreater(h.implied_attachment_efficiency, 0.05, h.tag)
            self.assertLess(h.implied_attachment_efficiency, 0.5, h.tag)

    def test_particles_settle_much_slower_than_circulation(self):
        # 침강 수 mm/s vs 순환 수십 cm/s — 모래화 없음의 근거.
        for h in self.hydro:
            self.assertLess(h.particle_settling_mm_s, 10.0, h.tag)

    def test_bubble_crosses_pulp_within_residence_time(self):
        # 기포 통과시간이 체류시간보다 훨씬 짧아야 급기가 낭비되지 않는다.
        res = self.opt.result_peak
        units = {"FC-201": res.rougher, "FC-202": res.scavenger, "FC-203": res.cleaner}
        for h in self.hydro:
            self.assertLess(h.pulp_transit_s, units[h.tag].residence_min * 60.0 * 0.1, h.tag)


class TestTransientStartup(unittest.TestCase):
    """기동 ODE 적분이 정상상태 물질수지와 폐합하는지 — 계산서 §7.2."""

    @classmethod
    def setUpClass(cls):
        cls.res = build_mechanical_option().result_peak
        cls.tr = simulate_startup(cls.res, duration_min=120.0)

    def test_effective_rate_reproduces_unit_recovery(self):
        # k = R/(τ(1-R)) 역산의 자기 일관성.
        u = self.res.rougher
        k = _effective_rate_1_min(u, "Ag")
        r = k * u.residence_min / (1.0 + k * u.residence_min)
        self.assertAlmostEqual(r, u.recovery("Ag"), places=10)

    def test_ode_converges_to_steady_state_recovery(self):
        self.assertAlmostEqual(
            self.tr.final_recovery_ag, self.res.recovery("Ag"), places=6
        )

    def test_ode_converges_to_steady_circulating_load(self):
        # 가장 느린 모드(비부선 성분, τ_eff ≈ 11 min)가 120 min 에 e^-11 수준
        # 잔차를 남기므로 1e-4 까지만 요구한다.
        self.assertAlmostEqual(
            self.tr.circulating_load[-1], self.res.circulating_load, places=4
        )

    def test_ode_converges_to_steady_concentrate_flow(self):
        self.assertAlmostEqual(
            self.tr.concentrate_ag_kg_h[-1],
            self.res.concentrate.component_tph("Ag") * 1000.0,
            places=5,
        )

    def test_startup_takes_a_finite_and_plausible_time(self):
        # t95 는 체류시간 합(28 min)의 0.1~2배 사이여야 그럴듯하다.
        total_tau = (
            self.res.rougher.residence_min
            + self.res.scavenger.residence_min
            + self.res.cleaner.residence_min
        )
        self.assertTrue(math.isfinite(self.tr.time_to_95pct_min))
        self.assertGreater(self.tr.time_to_95pct_min, total_tau * 0.1)
        self.assertLess(self.tr.time_to_95pct_min, total_tau * 2.0)
        self.assertGreater(self.tr.time_to_99pct_min, self.tr.time_to_95pct_min)

    def test_recovery_rises_monotonically_during_startup(self):
        rec = self.tr.recovery_ag
        for a, b in zip(rec, rec[1:]):
            self.assertLessEqual(a, b + 1e-12)

    def test_starts_empty(self):
        self.assertEqual(self.tr.recovery_ag[0], 0.0)
        self.assertEqual(self.tr.circulating_load[0], 0.0)


class TestReportSection(unittest.TestCase):
    def test_calculation_report_contains_numerics_section(self):
        import pathlib

        doc = (
            pathlib.Path(__file__).resolve().parents[1]
            / "docs"
            / "design-calculation.md"
        ).read_text(encoding="utf-8")
        self.assertIn("## 7. 수치해석", doc)
        self.assertIn("Yoon-Luttrell", doc)
        self.assertIn("t95", doc)


if __name__ == "__main__":
    unittest.main()
