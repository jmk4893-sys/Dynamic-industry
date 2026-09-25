"""BR-306 백시트 박리 — **어느 면에서 뜯을지가 설계다.**

`br_abrade` 를 지은 뒤, 부유선별이 목적이면 연마에 되돌아오는 칼이 있다는 것이
드러났다 — 없애는 게 아니라 더 고운 가루로 바꾼다. 그래서 박리를 다시 봤고,
못 쓴다고 본 이유 두 개가 다 틀렸다는 것을 이 묶음이 지킨다.

1. **「노후 패널은 접착이 세다」가 반대였다.** 접착은 세월이 갈수록 약해진다.
   노후 패널은 박리에 불리한 게 아니라 **유리하다** (`TestAgingHelps`).
2. **면을 잘못 고르고 있었다.** 백시트는 그 자체가 3층 적층이고, 야외에서
   실제로 벌어지는 곳은 EVA 계면이 아니라 백시트 **안쪽** 접착층이다.
   거기가 20 분의 1 로 약하다 (`TestTheWeakPlaneIsTheDirtyPlane`).

그리고 그 약한 면이 하필 **오염원이 얹힌 면**이다. 부유선별을 망치는 것은 불소
외피이고, 그것이 바로 그 면 위에 있다. 「세게 뜯어야 한다」와 「오염원을 빼야
한다」가 서로 싸우지 않는다는 뜻이고, 이 묶음의 요지가 그것이다.
"""

from __future__ import annotations

import unittest

from tests import _path  # noqa: F401

from pv_preprocess import br_peel, campaign, sg_grind


class TestTheWeakPlaneIsTheDirtyPlane(unittest.TestCase):
    """요지 — 가장 약한 면과 오염원이 얹힌 면이 같다."""

    def test_they_are_the_same_plane(self):
        """둘이 같은 면이라 목적과 난이도가 안 싸운다."""
        self.assertTrue(br_peel.the_weak_plane_is_the_dirty_plane())
        self.assertEqual(br_peel.weakest_interface().key, "fluoro_pet")
        self.assertTrue(br_peel.weakest_interface().carries_fluoropolymer)

    def test_choosing_that_plane_is_worth_an_order_of_magnitude(self):
        """면을 고르는 것만으로 한 자릿수가 바뀐다."""
        full = next(i for i in br_peel.INTERFACES if i.key == "backsheet_eva")
        self.assertGreater(br_peel.easier_than_full_backsheet_by(), 10.0)
        self.assertLess(br_peel.peel_force_n(), br_peel.peel_force_n(full))
        self.assertAlmostEqual(
            br_peel.easier_than_full_backsheet_by(),
            round(br_peel.peel_force_n(full) / br_peel.peel_force_n(), 1), places=1)

    def test_it_stops_at_the_shallowest_plane_that_does_the_job(self):
        """오염원이 빠지면 거기서 멈춘다 — 깊이 갈수록 딸려 나오는 게 많다."""
        chosen = br_peel.shallowest_interface_that_removes_the_contaminant()
        self.assertEqual(chosen.key, "fluoro_pet")
        self.assertEqual(chosen.above, "불소 외피만")
        deeper = [i for i in br_peel.INTERFACES if i.key != chosen.key]
        for i in deeper:
            self.assertGreater(i.gc_aged_n_mm, chosen.gc_aged_n_mm)

    def test_peeling_is_interfacial_work_so_thickness_never_enters(self):
        """박리력에 두께가 안 들어간다 — 계면 일이기 때문이다."""
        t0 = sg_grind.BACKSHEET_T_MM
        f0 = br_peel.peel_force_n()
        try:
            sg_grind.BACKSHEET_T_MM = t0 * 3.0
            self.assertEqual(br_peel.peel_force_n(), f0)
        finally:
            sg_grind.BACKSHEET_T_MM = t0


class TestAgingHelps(unittest.TestCase):
    """세월이 박리를 돕는다 — 처음에 반대로 알고 있었다."""

    def test_every_interface_weakens_with_age(self):
        """모든 계면이 노후와 함께 약해진다."""
        self.assertTrue(br_peel.aging_helps())
        for i in br_peel.INTERFACES:
            self.assertLess(i.gc_aged_n_mm, i.gc_fresh_n_mm, i.key)

    def test_the_aged_value_is_the_design_value(self):
        """설계값이 노후값이다 — 우리가 받는 것은 20 년 된 패널이다."""
        self.assertLess(br_peel.peel_force_n(aged=True),
                        br_peel.peel_force_n(aged=False))
        self.assertAlmostEqual(
            br_peel.peel_force_n(),
            round(br_peel.weakest_interface().gc_aged_n_mm
                  * float(campaign.PANEL_WIDTH_MM), 1), places=1)

    def test_heat_takes_it_down_further(self):
        """가열이 그 위에서 한 번 더 깎는다."""
        self.assertLess(br_peel.heat_brings_it_to_n(), br_peel.peel_force_n())
        self.assertAlmostEqual(
            br_peel.heat_brings_it_to_n(),
            round(br_peel.peel_force_n() * br_peel.HEAT_DERATE, 1), places=1)
        self.assertLess(br_peel.HEAT_ASSIST_C[0], br_peel.HEAT_ASSIST_C[1])


class TestTheRepoHadTheWrongNumber(unittest.TestCase):
    """저장소가 들고 있던 0.5 N/mm 는 문헌값의 몇 분의 일이었다."""

    def test_sg_grind_now_defers_to_this_module(self):
        """같은 수에 이름이 둘이면 갈라진다 — 정본은 `br_peel` 이다."""
        self.assertFalse(hasattr(sg_grind, "BACKSHEET_PEEL_GC_N_MM"))
        self.assertAlmostEqual(
            sg_grind.backsheet_peel_gc_n_mm(),
            next(i for i in br_peel.INTERFACES
                 if i.key == "backsheet_eva").gc_aged_n_mm, places=3)

    def test_the_corrected_value_is_several_times_the_old_planning_one(self):
        """고친 값이 옛 계획값보다 여러 배다 — 박리를 쉽게 보고 있었다."""
        self.assertGreaterEqual(sg_grind.backsheet_peel_gc_n_mm(), 4 * 0.5)

    def test_peeling_still_beats_abrading_after_the_correction(self):
        """상수를 올려도 결론은 그대로다 — 계면 일과 부피 일의 차이다."""
        self.assertGreater(sg_grind.peel_beats_abrade_by(), 100)
        self.assertAlmostEqual(
            sg_grind.backsheet_peel_force_n(),
            round(sg_grind.backsheet_peel_gc_n_mm()
                  * float(campaign.PANEL_WIDTH_MM), 1), places=1)


class TestTheMethodTableIsHonestAboutWhatBlocksEach(unittest.TestCase):
    """공법 후보 — 되는 이유가 아니라 **막히는 곳**을 적는다."""

    def test_every_method_names_its_blocker(self):
        """막히는 곳 없는 공법은 아직 안 본 공법이다."""
        self.assertGreaterEqual(len(br_peel.METHODS), 5)
        for m in br_peel.METHODS:
            self.assertTrue(m.blocker.strip(), m.key)
            self.assertTrue(m.parameters.strip(), m.key)
            self.assertTrue(m.principle.strip(), m.key)

    def test_the_laser_is_clean_but_far_too_slow(self):
        """레이저는 가장 깨끗한데 면적 속도가 벽이다 — 그것을 적어 둔다."""
        laser = next(m for m in br_peel.METHODS if m.key == "ir_laser")
        self.assertTrue(laser.solvent_free)
        self.assertIsNone(laser.seconds_per_panel)
        self.assertIn("면적 속도", laser.blocker)

    def test_the_solvent_route_is_fast_but_carries_a_regulated_substance(self):
        """DMAc 는 상온 5 분으로 빠르지만 규제가 설계를 지배한다."""
        dmac = next(m for m in br_peel.METHODS if m.key == "dmac_soak")
        self.assertFalse(dmac.solvent_free)
        self.assertIn("생식독성", dmac.blocker)
        self.assertLessEqual(dmac.seconds_per_panel, 300.0)

    def test_the_recommendation_is_solvent_free_and_needs_no_pressure_vessel(self):
        """먼저 시험할 것은 용제도 압력용기도 안 드는 쪽이다."""
        rec = br_peel.recommended()
        self.assertEqual(rec.key, "heat_vacuum")
        self.assertTrue(rec.solvent_free)
        self.assertIn(rec, br_peel.solvent_free_methods())
        self.assertGreaterEqual(len(br_peel.solvent_free_methods()), 3)

    def test_inline_fitness_is_measured_against_the_line_takt(self):
        """인라인 여부를 라인 택트로 잰다 — 여기서 정하지 않는다."""
        self.assertAlmostEqual(br_peel.line_takt_s(), campaign.ideal_takt_s(),
                               places=2)
        for m in br_peel.methods_that_fit_inline():
            self.assertLessEqual(m.seconds_per_panel, br_peel.line_takt_s())


class TestItSaysWhyThisBeatsAbrading(unittest.TestCase):
    """연마 대신 이쪽을 먼저 보는 이유를 글로 적어 둔다."""

    def test_the_case_rests_on_fines_not_on_force(self):
        """요지는 힘이 아니라 **미분이 안 생긴다**는 것이다."""
        note = " ".join(br_peel.why_not_abrading())
        self.assertIn("미분", note)
        self.assertIn("PET", note)
        self.assertGreaterEqual(len(br_peel.why_not_abrading()), 4)

    def test_the_open_questions_name_what_would_kill_it(self):
        """이 공법을 무너뜨릴 값을 숨기지 않는다 — 한 장으로 벗겨지는가."""
        note = " ".join(br_peel.open_questions())
        self.assertIn("한 장", note)
        self.assertGreaterEqual(len(br_peel.open_questions()), 4)

    def test_the_summary_is_flat_and_complete(self):
        """요약이 도면 리터럴에 실릴 수 있는 모양인가."""
        s = br_peel.summary()
        for key in ("theWeakPlaneIsTheDirtyPlane", "peelForceN",
                    "easierThanFullBacksheetBy", "recommended"):
            self.assertIn(key, s)
        for v in s.values():
            self.assertIsInstance(v, (int, float, bool, str, list))


if __name__ == "__main__":
    unittest.main()
