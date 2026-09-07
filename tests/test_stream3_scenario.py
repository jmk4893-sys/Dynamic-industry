"""③ 직접 Ag 부선 시나리오 — 그리고 미니앱 수지와의 교차 대조.

`flotation_design.stream3_scenario` 는 미니앱과 **다른 기계**로 같은 회로를 푼다.
미니앱은 입자군 원장에 완전혼합 1 차 모델을 걸고, 이쪽은 성분 기준으로
Ag ＋ 결합맥석 ＋ 잔류물을 직접 센다. 서로를 베끼지 않았으므로 결과가 붙으면
그것이 상호 검증이다.
"""

import math
import unittest

from . import _path  # noqa: F401

from flotation_design import stream3_scenario as s3
from .test_ag_recovery import const


class ExposureDrivesRecovery(unittest.TestCase):
    """어트리션이 회수율을 정한다 — 이 공정의 전제."""

    def test_exposure_rises_with_residence(self):
        for a, b in ((0, 2), (2, 5), (5, 10), (10, 20)):
            self.assertLess(s3.ag_exposure(a), s3.ag_exposure(b))

    def test_nameplate_hits_the_design_intent(self):
        self.assertAlmostEqual(s3.ag_exposure(s3.AG_EXPOSURE_NAMEPLATE_MIN),
                               s3.AG_EXPOSURE_TARGET, places=12)

    def test_recovery_tracks_exposure(self):
        slow = s3.run(attrition_min=9.9, t95=25.0)
        fast = s3.run(attrition_min=9.9, t95=5.0)
        self.assertLess(slow.ag_recovery, fast.ag_recovery)
        self.assertFalse(slow.meets_recovery)
        self.assertTrue(fast.meets_recovery)

    def test_more_attrition_widens_the_tolerance(self):
        one, two = s3.attrition_tolerance(9.9), s3.attrition_tolerance(19.7)
        self.assertGreater(two, one * 1.8,
                           f"체류 2 배가 허용 t95 를 두 배 가까이 넓혀야 한다: {one:.1f} → {two:.1f}")


class SiliconIsTheProduct(unittest.TestCase):
    """이 공정의 목적 절반은 Si 를 살리는 것이다 — 그 지표가 있어야 한다."""

    def test_almost_all_mass_reports_to_silicon(self):
        r = s3.run()
        self.assertGreater(r.si_product_share, 0.95,
                           "③ 질량의 대부분이 Si 산물로 남아야 목적이 성립한다")

    def test_silicon_keeps_little_silver(self):
        r = s3.run(attrition_min=9.9)
        self.assertLess(r.si_product_ag_gpt, 60,
                        f"Si 산물에 Ag 가 {r.si_product_ag_gpt:.0f} g/t 남으면 회수가 샌 것")

    def test_mass_closes(self):
        r = s3.run()
        self.assertAlmostEqual(r.concentrate_kg_h + r.si_product_kg_h, r.feed_kg_h, places=9)

    def test_silver_closes(self):
        r = s3.run()
        tails_ag = r.si_product_kg_h * r.si_product_ag_gpt / 1e6
        self.assertAlmostEqual(r.concentrate_ag_kg_h + tails_ag, r.feed_ag_kg_h, places=9)


class GradeIsSetByWhatRidesAlong(unittest.TestCase):
    """품위는 Ag 에 붙어 함께 뜨는 것들이 정한다."""

    def test_grade_clears_the_target(self):
        self.assertTrue(s3.run().meets_grade)

    def test_polymer_free_feed_approaches_the_carry_limit(self):
        original = s3.STREAM3_POLYMER_WT
        try:
            s3.STREAM3_POLYMER_WT = 0.0
            r = s3.run(cu_pickoff=1.0)
        finally:
            s3.STREAM3_POLYMER_WT = original
        # 맥석만 남으면 품위 상한은 1/(1+1.1) = 47.6 wt%
        self.assertAlmostEqual(r.grade_wt_percent, 100 / (1 + 1.1), places=1)

    def test_residual_backsheet_dust_is_what_costs_grade(self):
        """LOI 가 잴 값이 곧 품위를 가른다 — 5 wt% 근처가 경계다."""
        original = s3.STREAM3_POLYMER_WT
        try:
            s3.STREAM3_POLYMER_WT = 1.0
            clean = s3.run().grade_wt_percent
            s3.STREAM3_POLYMER_WT = 8.0
            dirty = s3.run().grade_wt_percent
        finally:
            s3.STREAM3_POLYMER_WT = original
        self.assertGreater(clean, 20)
        self.assertLess(dirty, 10, "잔류 가루가 많으면 품위 목표가 깨져야 한다")


class MechanicalCircuitCannotReach99(unittest.TestCase):
    """기존 셀 폐회로는 비부선 2.4 % 에 막힌다 — 결정 4 의 근거."""

    def test_mechanical_falls_short(self):
        r = s3.run(attrition_min=19.7, flotation_recovery=s3.MECHANICAL_RECOVERY)
        self.assertFalse(r.meets_recovery)
        self.assertGreater(r.ag_recovery, 0.95)

    def test_reflux_reaches_it(self):
        r = s3.run(attrition_min=19.7, flotation_recovery=s3.REFLUX_RECOVERY["design"])
        self.assertTrue(r.meets_recovery)


class CrossCheckAgainstTheMiniapp(unittest.TestCase):
    """미니앱과 이 모듈이 같은 상수 위에 서 있는가."""

    def test_exposure_constants_match(self):
        self.assertAlmostEqual(s3.AG_EXPOSURE_FEED, const("AG_EXPOSURE_FEED"), places=9)
        self.assertAlmostEqual(s3.AG_EXPOSURE_TARGET, const("AG_EXPOSURE_TARGET"), places=9)
        self.assertAlmostEqual(s3.AG_EXPOSURE_NAMEPLATE_MIN,
                               const("AG_EXPOSURE_NAMEPLATE_MIN"), places=9)

    def test_carry_ratio_matches(self):
        self.assertAlmostEqual(s3.COMPOSITE_CARRY_RATIO, const("AG_COMPOSITE_CARRY"), places=9)

    def test_reflux_band_matches(self):
        from .test_ag_recovery import LIVE
        import re
        m = re.search(r"const FC101_AG_RECOVERY = Object\.freeze\(\{ low: ([\d.]+), design: ([\d.]+)", LIVE)
        self.assertIsNotNone(m, "FC101_AG_RECOVERY 밴드를 못 찾음")
        self.assertAlmostEqual(s3.REFLUX_RECOVERY["low"], float(m.group(1)), places=9)
        self.assertAlmostEqual(s3.REFLUX_RECOVERY["design"], float(m.group(2)), places=9)

    def test_exposure_curve_agrees(self):
        e0 = const("AG_EXPOSURE_FEED")
        k = -math.log((1 - const("AG_EXPOSURE_TARGET")) / (1 - e0)) / const("AG_EXPOSURE_NAMEPLATE_MIN")
        for minutes in (2.0, 4.9, 9.9, 19.7):
            mini = 1 - (1 - e0) * math.exp(-k * minutes)
            self.assertAlmostEqual(s3.ag_exposure(minutes), mini, places=12)


class NoPolymerStageRemains(unittest.TestCase):
    """③ 이 폴리머-희박이므로 역부선 단은 없어야 한다."""

    def test_miniapp_dropped_the_polymer_float(self):
        from .test_ag_recovery import LIVE
        self.assertNotIn("solvePolymerFloat", LIVE)
        self.assertNotIn("AG_STAGE_POLYMER_REJECTION", LIVE)

    def test_miniapp_declares_the_direct_circuit(self):
        from .test_ag_recovery import LIVE
        self.assertIn("AG_CIRCUIT_OPTIONS", LIVE)
        self.assertIn("mechanical", LIVE)
        self.assertIn("reflux", LIVE)


if __name__ == "__main__":
    unittest.main()
