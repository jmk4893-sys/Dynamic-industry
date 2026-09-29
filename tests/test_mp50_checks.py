"""MP-50 제작성·기능성 검증.

검증은 두 종류다. **조립** 항목은 부품끼리 부딪히지 않는지를 보며 하나라도
FAIL 이면 발주할 수 없다. **기능** 항목은 만들었을 때 목적을 달성하는지를
보며, WARN 은 장치가 아니라 운전조건·시험계획을 고치라는 뜻이다.

여기서는 개별 수치보다 **결론이 뒤집히지 않는지**를 지킨다. 물성 상관식에
±5 % 오차를 넣어도 "90 rpm 으로는 Njs 에 못 미친다", "600 s 로는 미세
폴리머가 안 뜬다" 같은 판정이 그대로여야 그 판정을 근거로 쓸 수 있다.
"""

import unittest

from . import _path  # noqa: F401

from mp50_separator import GEOMETRY as G, run_checks
from mp50_separator.checks import (
    BACKSHEET_DENSITY, DESIGN_MAX_RPM, EVA_DENSITY, GEARBOX_MAX_RPM, SILICON_DENSITY,
    brine_density, brine_viscosity, critical_speed, stokes_velocity, travel_fraction,
)

CHECKS = {c.ref: c for c in run_checks()}


class TestCheckSuite(unittest.TestCase):
    def test_nothing_fails(self):
        bad = [c.ref for c in run_checks() if c.verdict == "FAIL"]
        self.assertEqual(bad, [], "FAIL 이 남아 있으면 발주할 수 없다")

    def test_every_assembly_check_passes(self):
        for c in run_checks():
            if c.kind == "조립":
                self.assertEqual(c.verdict, "PASS", f"{c.ref} {c.item}: {c.value}")

    def test_refs_and_fields(self):
        refs = [c.ref for c in run_checks()]
        self.assertEqual(len(refs), len(set(refs)))
        for c in run_checks():
            self.assertIn(c.kind, {"조립", "기능"}, c.ref)
            self.assertIn(c.verdict, {"PASS", "WARN", "FAIL"}, c.ref)
            self.assertGreater(len(c.detail), 60, c.ref)
            self.assertTrue(c.criterion and c.value, c.ref)


class TestBrineProperties(unittest.TestCase):
    """상관식이 알려진 값과 맞는가 (20 °C, ±0.5 % / ±5 %)."""

    def test_density_against_known_values(self):
        for wt, ref in ((0, 998), (5, 1034), (10, 1071), (18, 1132), (26, 1198)):
            self.assertAlmostEqual(brine_density(wt), ref, delta=ref * 0.005)

    def test_density_falls_with_temperature(self):
        self.assertLess(brine_density(18, 30), brine_density(18, 20))

    def test_viscosity_rises_with_salt(self):
        self.assertGreater(brine_viscosity(18), brine_viscosity(0))
        self.assertAlmostEqual(brine_viscosity(18) * 1000, 1.63, delta=0.10)


class TestSeparationPhysics(unittest.TestCase):
    def test_silicon_sinks_across_the_whole_salinity_range(self):
        for wt in (0, 12, 18, 26):
            self.assertGreater(stokes_velocity(SILICON_DENSITY, 31, wt), 0, f"{wt} wt%")

    def test_eva_floats_from_low_salinity(self):
        for wt in (12, 15, 18):
            self.assertLess(stokes_velocity(EVA_DENSITY[0], 45, wt), 0, f"{wt} wt%")

    def test_fine_backsheet_barely_moves_at_18_wt(self):
        v = abs(stokes_velocity(BACKSHEET_DENSITY[0], 31, 18))
        column = (G.operating_level_z - G.shell_bottom_z) / 1000
        self.assertLess(travel_fraction(v, 600, column), 0.05)

    def test_saturation_makes_fine_backsheet_move(self):
        """포화까지 올리면 상승속도가 뚜렷이 빨라진다 — CHK-10 의 권고 근거.

        밀도차는 25 → 92 kg/m³ 로 3.6 배가 되지만 점도도 1.6 → 2.2 mPa·s 로
        따라 오르므로, 실제 상승속도 이득은 그보다 작은 약 2.7 배다.
        """
        slow = abs(stokes_velocity(BACKSHEET_DENSITY[0], 31, 18))
        fast = abs(stokes_velocity(BACKSHEET_DENSITY[0], 31, 26))
        self.assertGreater(fast / slow, 2.5)
        self.assertLess(fast / slow, 3.2)      # 점도 상승을 무시하면 3.6 배로 과장된다

    def test_settling_scales_with_diameter_squared(self):
        a = stokes_velocity(SILICON_DENSITY, 31, 18)
        b = stokes_velocity(SILICON_DENSITY, 62, 18)
        self.assertAlmostEqual(b / a, 4.0, places=6)

    def test_travel_fraction_is_bounded(self):
        self.assertEqual(travel_fraction(1.0, 10, 0.1), 1.0)
        self.assertAlmostEqual(travel_fraction(0.001, 100, 1.0), 0.1)


class TestFindingsSurviveUncertainty(unittest.TestCase):
    """물성에 오차를 넣어도 결론이 뒤집히지 않는가."""

    def test_njs_exceeds_gearbox_limit_either_way(self):
        chk = CHECKS["CHK-05"]
        self.assertEqual(chk.verdict, "WARN")
        njs = float(chk.value.split()[1])
        self.assertGreater(njs, GEARBOX_MAX_RPM * 1.2)   # 20 % 여유를 둬도 넘는다
        self.assertLess(njs, DESIGN_MAX_RPM)             # 권고 150 rpm 안에는 든다

    def test_fine_polymer_still_short_at_600_s_with_slower_settling(self):
        column = (G.operating_level_z - G.shell_bottom_z) / 1000
        v = abs(stokes_velocity(EVA_DENSITY[0], 31, 18)) * 1.25   # 25 % 빠르게 봐도
        self.assertLess(travel_fraction(v, 600, column), 0.20)

    def test_critical_speed_margin_is_large(self):
        rpm, span, m_eff = critical_speed()
        self.assertGreater(rpm / DESIGN_MAX_RPM, 5.0)
        self.assertGreater(span, 0.4)
        self.assertGreater(m_eff, 1.0)

    def test_critical_speed_drops_if_the_support_point_rises(self):
        """벤더 GA 에서 지지점이 올라가면 재계산해야 한다 (C-03 HOLD)."""
        from mp50_separator.geometry import Geometry

        low = critical_speed()[0]
        deeper = critical_speed(Geometry(lower_impeller_z=300.0))
        self.assertLess(deeper[0], low)


class TestSpargerAndDischarge(unittest.TestCase):
    def test_orifice_distributes_evenly(self):
        self.assertEqual(CHECKS["CHK-08"].verdict, "PASS")

    def test_bubbles_are_not_fine(self):
        """Ø1.5 홀에서 나오는 기포는 미세기포가 아니다 — C5 의 근거."""
        self.assertIn("Ø3.9 mm", CHECKS["CHK-08"].value)

    def test_discharge_clearance_passes(self):
        self.assertEqual(CHECKS["CHK-09"].verdict, "PASS")


class TestStokesValidity(unittest.TestCase):
    def test_reynolds_stays_below_one(self):
        self.assertEqual(CHECKS["CHK-11"].verdict, "PASS")
        re = float(CHECKS["CHK-11"].value.split()[1])
        self.assertLess(re, 1.0)


if __name__ == "__main__":
    unittest.main()
