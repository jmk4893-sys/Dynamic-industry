"""screen_sizing 설계식 검증.

이 모듈은 순수 파이썬이라 numpy 없이도 돌아간다 — 기본 unittest 잡이 보호한다.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import screen_sizing as ss


class CentrifugalFieldTest(unittest.TestCase):
    def test_acceleration_formula(self):
        """a = omega^2 R. 200 rpm, R=75 mm -> 약 3.4 g."""
        a = ss.centrifugal_acceleration(200, 0.075)
        self.assertAlmostEqual(a, (2 * math.pi * 200 / 60) ** 2 * 0.075, places=9)
        self.assertAlmostEqual(a / ss.G, 3.36, places=1)

    def test_field_velocity_reduces_to_gravity(self):
        """accel = g 이면 중력 종말속도와 같아야 한다."""
        for rho in (8960.0, 2500.0, 1200.0):
            for d in (75e-6, 106e-6, 200e-6):
                v_grav, _re = ss.vt(rho, d)      # vt 는 (속도, Re) 를 돌려준다
                self.assertAlmostEqual(ss.vt_in_field(rho, d, ss.G), v_grav, places=6)

    def test_velocity_monotonic_in_acceleration(self):
        prev = 0.0
        for ag in (1.0, 3.4, 7.5, 13.4):
            v = ss.vt_in_field(8960.0, 106e-6, ag * ss.G)
            self.assertGreater(v, prev)
            prev = v

    def test_diameter_inversion_round_trips(self):
        a = ss.centrifugal_acceleration(200, 0.075)
        for d_um in (60, 106, 180):
            v = ss.vt_in_field(8960.0, d_um * 1e-6, a)
            d_back = ss._diameter_at_field_velocity(8960.0, v, a) * 1e6
            self.assertAlmostEqual(d_back / d_um, 1.0, places=3)


class SeparationBoundsTest(unittest.TestCase):
    def test_silicon_binds_the_fine_fraction(self):
        """75~106 µm 에서 제약은 폴리머가 아니라 실리콘이다 (Rev.2 의 오류)."""
        a = ss.centrifugal_acceleration(200, 0.075)
        cu, worst, who = ss.separation_bounds(75, 106, a)
        self.assertIn("실리콘", who)
        self.assertGreater(cu, worst, "구리가 비구리보다 빨라야 분리가 성립한다")

    def test_backsheet_binds_the_coarse_fraction(self):
        """106~200 µm 에서는 실리콘이 120 µm 까지만 있어 백시트가 제약이 된다."""
        a = ss.centrifugal_acceleration(150, 0.075)
        _, _, who = ss.separation_bounds(106, 200, a)
        self.assertIn("백시트", who)

    def test_centrifugal_does_not_widen_the_window(self):
        """원심장은 분리 여유비를 넓히지 않는다 — 설계서 §6.5 의 주장."""
        ratios = []
        for ag in (1.0, 3.4, 13.4):
            cu, worst, _ = ss.separation_bounds(75, 106, ag * ss.G)
            ratios.append(cu / worst)
        self.assertTrue(all(r > 1.0 for r in ratios), "어느 경우든 분리는 성립해야 한다")
        self.assertLessEqual(ratios[-1], ratios[0] + 1e-9,
                             "가속도를 키우면 여유비가 넓어지지 않아야 한다")


class OperatingPointTest(unittest.TestCase):
    def test_configured_points_are_operable(self):
        """CONFIG 의 각 분급기가 밴드 사이에 있고 고형물 부하가 한계 이내인지."""
        area = ss.wheel_area()
        peak = ss.CONFIG["peak_tph"] * 1000.0
        for tag, lo, hi, key, rpm, v_r in ss.CONFIG["classifiers"]:
            a = ss.centrifugal_acceleration(rpm, ss.CONFIG["wheel_radius_m"])
            cu, worst, _ = ss.separation_bounds(lo, hi, a)
            self.assertLess(worst, v_r, f"{tag}: 비구리가 중량측으로 간다")
            self.assertLess(v_r, cu, f"{tag}: 구리가 경량측으로 샌다")
            q = v_r * area * 3600.0
            load = peak * ss.CONFIG["split"][key] / q
            self.assertLessEqual(load, 0.5, f"{tag}: 고형물 부하 {load:.3f} kg/m3 초과")


if __name__ == "__main__":
    unittest.main()
