"""라미네이트 시나리오 — 그리고 미니앱 수지와의 교차 대조.

`flotation_design.laminate_scenario` 는 미니앱과 **다른 기계**로 같은 회로를
푼다. 미니앱은 입자군별 부유도비(B 1 · C 0.35 · A 0.03)에 완전혼합 1 차
모델을 걸고, 이 패키지는 성분별 2 속도 속도론에 연행(entrainment)을 얹는다.
전제도 다르다 — 미니앱은 입자군 질량을, 패키지는 성분 질량을 추적한다.

두 모델이 서로를 베끼지 않았으므로, 결과가 붙으면 그것이 곧 상호 검증이다.
크게 갈라지면 어느 한쪽이 틀렸다는 뜻이므로 여기서 잡는다.
"""

import unittest

from . import _path  # noqa: F401

from flotation_design import laminate_scenario as ls
from .test_ag_recovery import PlantRecoveryLandsInTheStatedBand as MiniApp


class LiberatedCellAssay(unittest.TestCase):
    """해리 산물 조성은 항등식이어야 한다 — 미니앱과 같은 요구."""

    def test_recombines_into_c(self):
        f = ls.C_BACKSHEET_MASS_FRACTION
        ac = ls.liberated_cell_assay()
        b, c = ls.LAMINATE_ASSAY["B"], ls.LAMINATE_ASSAY["C"]
        for k in c:
            self.assertAlmostEqual((1 - f) * ac[k] + f * b[k], c[k], places=9)

    def test_silver_is_conserved_through_attrition(self):
        # 해리도를 훑어도 급광 Ag 는 변하지 않아야 한다.
        base = ls.laminate_feed_tph(0.0)["Ag"]
        for debond in (0.25, 0.5, 0.9, 1.0):
            self.assertAlmostEqual(ls.laminate_feed_tph(debond)["Ag"], base, places=15)


class BoundEvaCannotBeFloatedAway(unittest.TestCase):
    """품위 문제의 뿌리 — EVA 는 「띄워 버릴 상」이 아니다."""

    def test_most_polymer_is_bound_to_the_cell(self):
        feed = ls.laminate_feed_tph(1.0)
        bound = feed["polymer_bound"]
        free = feed["polymer_free"]
        self.assertGreater(bound, free, "셀에 붙은 EVA 가 자유 백시트보다 많아야 한다")

    def test_stage1_removes_far_less_than_the_proposal_assumed(self):
        # 제안서는 1 단이 폴리머를 98.9 % 뗀다고 전제했다. 실제로는 그 근처도 못 간다.
        r = ls.run()
        self.assertLess(r.polymer_removed_fraction, 0.50)
        self.assertGreater(r.polymer_removed_fraction, 0.15)


class TargetsAsBuilt(unittest.TestCase):
    """설계가 실제로 무엇을 달성하는지 — 숨기지 않고 고정한다."""

    def test_grade_target_is_met(self):
        self.assertTrue(ls.run().meets_grade)

    def test_recovery_target_is_not_met_as_built(self):
        # ≥99 % 는 달성되지 않는다. 이 시험이 깨지면 무언가 좋아진 것이니
        # 그때 값을 올리면 된다 — 조용히 미달로 남는 것만 막는다.
        for rec in (0.990, 0.997):
            self.assertFalse(ls.run(rfc_ag_recovery=rec).meets_recovery)

    def test_grade_collapses_without_the_stage2_polymer_rejection(self):
        # 관문 4 가 품위를 가른다는 것을 숫자로 남긴다.
        weak = ls.run(ag_stage_polymer_rejection=0.50)
        self.assertLess(weak.grade_wt_percent, 5.0)


class CrossCheckAgainstTheMiniapp(unittest.TestCase):
    """서로 다른 기계로 푼 두 수지가 같은 답에 오는가."""

    TOLERANCE_PP = 1.0        # 회수율 허용차 (percentage point)
    TOLERANCE_GRADE = 1.5     # 품위 허용차 (wt%)

    def miniapp(self, rfc):
        t = MiniApp("test_grade_clears_the_10wt_target")
        wet, cu, reject = t.dry_split(1.0)
        return t.plant(wet, cu, reject, rfc)

    def test_recovery_agrees(self):
        for rfc in (0.990, 0.997):
            mini = self.miniapp(rfc)["recovery"] * 100
            pkg = ls.run(rfc_ag_recovery=rfc).plant_recovery * 100
            self.assertLess(
                abs(mini - pkg), self.TOLERANCE_PP,
                f"FC-101 {rfc}: 미니앱 {mini:.2f} % vs 패키지 {pkg:.2f} % — 갈라진다",
            )

    def test_grade_agrees(self):
        mini = self.miniapp(0.997)["grade"]
        pkg = ls.run().grade_wt_percent
        self.assertLess(
            abs(mini - pkg), self.TOLERANCE_GRADE,
            f"품위: 미니앱 {mini:.1f} wt% vs 패키지 {pkg:.1f} wt% — 갈라진다",
        )

    def test_both_agree_the_recovery_target_is_missed(self):
        # 결론이 같아야 의미가 있다 — 한쪽만 목표를 넘으면 대조가 실패한 것이다.
        mini = self.miniapp(0.997)["recovery"]
        pkg = ls.run().plant_recovery
        self.assertEqual(mini >= 0.99, pkg >= 0.99)


class DoesNotDisturbTheBaseDesign(unittest.TestCase):
    """추가형이어야 한다 — 기준 급광은 그대로다."""

    def test_base_feed_is_untouched(self):
        from flotation_design import design_basis
        self.assertAlmostEqual(design_basis.FEED.average_tph, 0.30)
        names = {c.name for c in design_basis.CELL_FRACTION}
        self.assertNotIn("polymer_free", names)
        self.assertNotIn("polymer_bound", names)

    def test_scenario_declares_its_own_kinetics(self):
        # 기준 FLOAT_MODELS 를 고쳐 쓰지 않고 자기 표를 든다.
        from flotation_design import design_basis
        self.assertIsNot(ls.POLYMER_FLOAT_KINETICS, design_basis.FLOAT_MODELS)
        self.assertIn("polymer_bound", ls.POLYMER_FLOAT_KINETICS)


if __name__ == "__main__":
    unittest.main()
