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


if __name__ == "__main__":
    unittest.main()
