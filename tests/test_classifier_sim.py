"""classifier_sim 물리 코어 검증.

numpy 는 pyproject 의 [simulation] 선택 의존성이므로, 설치되지 않은 환경
(기본 unittest CI 잡)에서는 건너뛴다.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

try:
    import numpy  # noqa: F401
    import classifier_sim as cs
    HAVE_SIM = True
except ImportError:  # pragma: no cover - 선택 의존성 미설치 환경
    HAVE_SIM = False


@unittest.skipUnless(HAVE_SIM, "numpy 미설치 — [simulation] extra 필요")
class TerminalVelocityTest(unittest.TestCase):
    """정지 공기 중 종말속도가 힘 평형 해와 일치하는지."""

    def test_matches_force_balance(self):
        for m in cs.MATERIALS.values():
            for d in (50e-6, 100e-6, 200e-6):
                v = cs.terminal_velocity(m["rho"], d)
                # 항력 = 부력 보정 중력 이어야 한다
                tau = cs.drag_relaxation_time(m["rho"], d, v)
                residual = v - tau * cs.G * (1.0 - cs.RHO_AIR / m["rho"])
                self.assertLess(abs(residual), 1e-9 + 1e-6 * v)

    def test_stokes_limit(self):
        """미립 극한에서 Stokes 해 v = rho d^2 g / (18 mu) 로 수렴한다.

        완전히 일치하지는 않는다 — 남는 편차가 곧 Schiller-Naumann 보정항
        (1 + 0.15 Re^0.687) 이므로, 그 크기까지 함께 검증한다.
        """
        for d, rho in ((2e-6, 2500.0), (5e-6, 2500.0)):
            v_stokes = rho * d * d * cs.G / (18 * cs.MU) * (1 - cs.RHO_AIR / rho)
            v = cs.terminal_velocity(rho, d)
            re = cs.RHO_AIR * v * d / cs.MU
            expected_ratio = 1.0 / (1.0 + 0.15 * re ** 0.687)
            self.assertAlmostEqual(v / v_stokes, expected_ratio, places=6)
            self.assertLess(abs(v / v_stokes - 1.0), 2e-3,
                            "Re << 1 에서는 Stokes 해에 0.2 % 이내로 붙어야 한다")

    def test_monotonic_in_size_and_density(self):
        prev = 0.0
        for d in (30e-6, 60e-6, 120e-6, 240e-6):
            v = cs.terminal_velocity(8960, d)
            self.assertGreater(v, prev)
            prev = v
        self.assertGreater(cs.terminal_velocity(8960, 1e-4),
                           cs.terminal_velocity(1200, 1e-4))


@unittest.skipUnless(HAVE_SIM, "numpy 미설치 — [simulation] extra 필요")
class IntegratorTest(unittest.TestCase):
    """지수적분기가 큰 dt 에서도 종말속도로 안정 수렴하는지."""

    def _free_fall(self, rho, d, dt, steps):
        v = 0.0
        for _ in range(steps):
            tau = cs.drag_relaxation_time(rho, d, v)
            e = math.exp(-dt / tau)
            v = v * e + tau * cs.G * (1.0 - cs.RHO_AIR / rho) * (1.0 - e)
        return v

    def test_stable_for_dt_far_above_tau(self):
        rho, d = 2500.0, 20e-6                      # tau ~ 3 ms
        v_ref = cs.terminal_velocity(rho, d)
        for dt in (1e-4, 1e-3, 1e-2, 1e-1):
            v = self._free_fall(rho, d, dt, int(5.0 / dt))
            self.assertLess(abs(v - v_ref) / v_ref, 2e-2,
                            f"dt={dt} 에서 발산 또는 부정확 (v={v}, ref={v_ref})")


@unittest.skipUnless(HAVE_SIM, "numpy 미설치 — [simulation] extra 필요")
class ColumnTest(unittest.TestCase):
    def test_gas_velocity_is_upward_and_bounded(self):
        col = cs.ZigZagColumn()
        xs = numpy.linspace(0, col.W, 25)
        ys = numpy.linspace(0, col.height, 25)
        ux, uy = col.gas_velocity(xs, ys, 1.7)
        self.assertTrue((uy > 0).all(), "상승 성분이 어디서나 양수여야 한다")
        self.assertTrue((uy <= 1.7 * 1.5 + 1e-9).all(), "중앙 최대 1.5배를 넘지 않는다")

    def test_heavy_reports_down_light_reports_up(self):
        """분획 106~200 µm, u=1.70 m/s 에서 구리는 하단, 폴리머는 상단."""
        col = cs.ZigZagColumn()
        cu, _ = cs.simulate(col, 8960.0, 150e-6, 1.70, n=200, dt=1e-3, t_max=4.0, seed=5)
        poly, _ = cs.simulate(col, 1200.0, 150e-6, 1.70, n=200, dt=1e-3, t_max=4.0, seed=5)
        self.assertLess(cu.mean(), 0.10, "구리가 경량측으로 새면 안 된다")
        self.assertGreater(poly.mean(), 0.90, "폴리머는 경량측으로 가야 한다")


@unittest.skipUnless(HAVE_SIM, "numpy 미설치 — [simulation] extra 필요")
class AgglomerateGeometryTest(unittest.TestCase):
    """프랙탈 응집체의 유효 입경·유효 밀도."""

    def test_single_particle_is_itself(self):
        d, rho = cs.aggregate_properties([100e-6], [8960.0])
        self.assertAlmostEqual(d, 100e-6, places=9)
        self.assertAlmostEqual(rho, 8960.0, places=6)

    def test_solid_volume_is_conserved(self):
        ds = [80e-6, 100e-6, 120e-6]
        rhos = [8960.0, 1200.0, 1200.0]
        d_eff, rho_eff = cs.aggregate_properties(ds, rhos)
        v_solid = sum(math.pi / 6 * x ** 3 for x in ds)
        m_total = sum(math.pi / 6 * x ** 3 * r for x, r in zip(ds, rhos))
        v_env = math.pi / 6 * d_eff ** 3
        self.assertGreater(v_env, v_solid, "포락 부피가 고체 부피보다 커야 한다")
        self.assertAlmostEqual(rho_eff * v_env / m_total, 1.0, places=6,
                               msg="유효밀도 x 포락부피 = 총 질량이어야 한다")

    def test_aggregate_is_diluted_and_larger(self):
        """입자가 늘수록 커지고 묽어진다 — 프랙탈 차원 2.4 의 귀결."""
        prev_d, prev_rho = cs.aggregate_properties([100e-6], [1200.0])
        for n in (2, 4, 8):
            d, rho = cs.aggregate_properties([100e-6] * n, [1200.0] * n)
            self.assertGreater(d, prev_d)
            self.assertLess(rho, prev_rho)
            prev_d, prev_rho = d, rho


@unittest.skipUnless(HAVE_SIM, "numpy 미설치 — [simulation] extra 필요")
class BondNumberTest(unittest.TestCase):
    def test_copper_sticks_less_than_polymer(self):
        """같은 입경이면 무거운 구리가 Bo 가 낮다 — 덜 붙는다."""
        bo_cu = cs.bond("구리", 8960.0, 100e-6)
        bo_poly = cs.bond("백시트+EVA", 1200.0, 100e-6)
        self.assertLess(bo_cu, bo_poly)
        self.assertLess(bo_cu, 1.0, "100 µm 구리는 자중이 이겨야 한다")
        self.assertGreater(bo_poly, 1.0, "100 µm 폴리머는 부착이 이겨야 한다")

    def test_bond_falls_with_size(self):
        prev = float("inf")
        for d in (20e-6, 50e-6, 100e-6, 200e-6):
            bo = cs.bond("백시트+EVA", 1200.0, d)
            self.assertLess(bo, prev)
            prev = bo


@unittest.skipUnless(HAVE_SIM, "numpy 미설치 — [simulation] extra 필요")
class AgglomerationEffectTest(unittest.TestCase):
    def _cell_and_field(self):
        import screen_sizing as ss
        return cs.UniformCell(), ss.centrifugal_acceleration(200, 0.075)

    def test_full_dispersion_gives_all_singlets(self):
        rng = numpy.random.default_rng(0)
        mats, dias, rhos = cs.sample_primaries(rng, 300, 75.0, 106.0)
        _, _, cluster_of = cs.agglomerate(rng, mats, dias, rhos,
                                          dispersion_efficiency=1.0)
        self.assertEqual(len(set(cluster_of.tolist())), len(mats),
                         "완전 분산이면 모든 입자가 단독이어야 한다")

    def test_no_dispersion_forms_clusters(self):
        rng = numpy.random.default_rng(0)
        mats, dias, rhos = cs.sample_primaries(rng, 300, 75.0, 106.0)
        _, _, cluster_of = cs.agglomerate(rng, mats, dias, rhos,
                                          dispersion_efficiency=0.0)
        self.assertLess(len(set(cluster_of.tolist())), len(mats))

    def test_ideal_case_reproduces_no_agglomeration_result(self):
        """분산효율 1.0 이면 이상 모델(회수·품위 100 %)로 되돌아와야 한다."""
        cell, accel = self._cell_and_field()
        r = cs.evaluate_with_agglomeration(cell, 75.0, 106.0, 2.07, accel,
                                           dispersion_efficiency=1.0,
                                           n_primary=800, seed=3)
        self.assertGreater(r["cu_recovery"], 0.99)
        self.assertGreater(r["cu_grade"], 0.99)

    def test_agglomeration_hurts_grade_more_than_recovery(self):
        """응집의 주된 피해는 회수율이 아니라 품위다 — 설계서의 주장."""
        cell, accel = self._cell_and_field()
        good = cs.evaluate_with_agglomeration(cell, 75.0, 106.0, 2.07, accel,
                                              dispersion_efficiency=1.0,
                                              n_primary=1500, seed=3)
        bad = cs.evaluate_with_agglomeration(cell, 75.0, 106.0, 2.07, accel,
                                             dispersion_efficiency=0.0,
                                             n_primary=1500, seed=3)
        grade_drop = good["cu_grade"] - bad["cu_grade"]
        rec_drop = good["cu_recovery"] - bad["cu_recovery"]
        self.assertGreater(grade_drop, 0.05, "품위가 뚜렷이 나빠져야 한다")
        self.assertGreater(grade_drop, rec_drop * 3,
                           "품위 손실이 회수율 손실보다 훨씬 커야 한다")


@unittest.skipUnless(HAVE_SIM, "numpy 미설치 — [simulation] extra 필요")
class SieveLeakTest(unittest.TestCase):
    """체 이월 — 분획 상한을 넘는 폴리머가 분급기 공급물에 섞여 들어오는 경우."""

    def _field(self):
        import screen_sizing as ss
        return cs.UniformCell(), ss.centrifugal_acceleration(200, 0.075)

    def test_leak_hits_the_requested_mass_fraction(self):
        rng = numpy.random.default_rng(0)
        mats, dias, rhos = cs.sample_primaries(rng, 800, 75.0, 106.0)
        base = (numpy.pi / 6 * dias ** 3 * rhos).sum()
        for target in (0.05, 0.20):
            m2, d2, r2 = cs.add_oversize_leak(rng, mats, dias, rhos, target)
            total = (numpy.pi / 6 * d2 ** 3 * r2).sum()
            got = (total - base) / total
            self.assertAlmostEqual(got, target, delta=0.03,
                                   msg=f"이월 질량비가 목표({target})에서 벗어났다: {got:.3f}")

    def test_zero_leak_is_a_no_op(self):
        rng = numpy.random.default_rng(0)
        mats, dias, rhos = cs.sample_primaries(rng, 200, 75.0, 106.0)
        m2, d2, r2 = cs.add_oversize_leak(rng, mats, dias, rhos, 0.0)
        self.assertEqual(len(m2), len(mats))

    def test_leak_destroys_grade_but_not_recovery(self):
        """이월은 굵은 폴리머를 중량측으로 보내므로 품위만 무너뜨린다."""
        cell, accel = self._field()
        clean = cs.evaluate_feed(cell, 75.0, 106.0, 2.07, accel,
                                 sieve_leak=0.0, n_primary=1200, seed=7)
        leaky = cs.evaluate_feed(cell, 75.0, 106.0, 2.07, accel,
                                 sieve_leak=0.10, n_primary=1200, seed=7)
        self.assertGreater(clean["cu_grade"] - leaky["cu_grade"], 0.05,
                           "이월 10 % 면 품위가 뚜렷이 나빠져야 한다")
        self.assertAlmostEqual(clean["cu_recovery"], leaky["cu_recovery"], delta=0.02,
                               msg="회수율은 거의 영향받지 않아야 한다")

    def test_grade_falls_monotonically_with_leak(self):
        cell, accel = self._field()
        prev = 1.01
        for leak in (0.0, 0.05, 0.10, 0.20):
            g = cs.evaluate_feed(cell, 75.0, 106.0, 2.07, accel, sieve_leak=leak,
                                 n_primary=1200, seed=7)["cu_grade"]
            self.assertLess(g, prev + 1e-9)
            prev = g

    def test_sieve_precision_matters_more_than_classifier_precision(self):
        """체 이월 10 % 의 피해가 v_r 을 15 % 틀어놓는 것보다 크다 — 설계서 §6.3.1."""
        cell, accel = self._field()
        base = cs.evaluate_feed(cell, 75.0, 106.0, 2.07, accel, n_primary=1200, seed=7)
        leak = cs.evaluate_feed(cell, 75.0, 106.0, 2.07, accel, sieve_leak=0.10,
                                n_primary=1200, seed=7)
        detuned = cs.evaluate_feed(cell, 75.0, 106.0, 2.07 * 1.15, accel,
                                   n_primary=1200, seed=7)
        leak_loss = base["cu_grade"] - leak["cu_grade"]
        tune_loss = base["cu_grade"] - detuned["cu_grade"]
        self.assertGreater(leak_loss, tune_loss,
                           "체가 새는 쪽이 분급기가 틀어지는 쪽보다 치명적이어야 한다")


if __name__ == "__main__":
    unittest.main()
