# -*- coding: utf-8 -*-
"""CD-101 신축 단수 — 단수가 유도값인지, 결론이 물리에서 오는지.

이 해석의 결론은 「7 단 · 뿌리 102 × 102 · 벨트 서보」다. 셋 다 값에서
나와야 하고, 걸릴 줄 알았던 강성이 **안 걸린다**는 것까지 값이어야 한다.
"""

from __future__ import annotations

import unittest

from tests import _path  # noqa: F401

from pv_preprocess import (afr, catch, dynamics, fabrication, kinematics,
                           layout, telescope)


class TestTheGeometryIsDerived(unittest.TestCase):
    def test_the_reach_and_shortfall_come_from_the_model(self):
        self.assertEqual(telescope.reach_mm(),
                         float(dynamics._part(telescope.SHEET, "CD-BM-01").size[0]))
        self.assertEqual(telescope.shortfall_mm(),
                         -kinematics.catch_beam_covers_the_panel_mm())

    def test_the_stow_depth_comes_from_the_panel_and_the_wall(self):
        self.assertEqual(telescope.panel_near_edge_mm(),
                         layout.BFC_PICKUP_Z_MM - kinematics.PANEL_MM[0] / 2)
        self.assertAlmostEqual(
            telescope.stow_depth_mm(),
            kinematics.CENTRE_WALL_T_MM / 2 + telescope.panel_near_edge_mm()
            - telescope.STOW_CLEARANCE_MM)

    def test_moving_the_pickup_moves_the_stow_depth(self):
        keep = layout.BFC_PICKUP_Z_MM
        try:
            layout.BFC_PICKUP_Z_MM = 2_200
            self.assertGreater(telescope.stow_depth_mm(), 900.0)
        finally:
            layout.BFC_PICKUP_Z_MM = keep

    def test_the_stage_count_is_solved_not_picked(self):
        n = telescope.stages_for_depth()
        self.assertLessEqual(telescope.stage_length_mm(n), telescope.stow_depth_mm())
        self.assertGreater(telescope.stage_length_mm(n - 1),
                           telescope.stow_depth_mm(), "한 단 적어도 들어간다")

    def test_a_deeper_pocket_needs_fewer_stages(self):
        self.assertLess(telescope.stages_for_depth(1_200.0),
                        telescope.stages_for_depth(640.0))

    def test_the_bom_stroke_is_half_the_reach(self):
        """부품표가 이미 2 단 리빙을 전제로 골라 둔 값이라는 근거."""
        self.assertAlmostEqual(catch.cylinder_stroke_mm() * 2,
                               telescope.reach_mm(), places=6)


class TestTheSectionAndTheStiffness(unittest.TestCase):
    def test_the_nest_step_is_two_walls_and_two_gaps(self):
        self.assertAlmostEqual(
            telescope.nest_step_mm(),
            2 * (float(dynamics._part(telescope.SHEET, "CD-BM-01").t)
                 + telescope.NEST_CLEARANCE_MM))

    def test_the_current_section_cannot_take_the_needed_stages(self):
        self.assertFalse(telescope.section_allows_the_depth())
        self.assertLess(telescope.max_stages_for_section(),
                        telescope.stages_for_depth())

    def test_the_root_needed_grows_with_the_stage_count(self):
        a = telescope.root_section_for_stages(3)
        b = telescope.root_section_for_stages(7)
        self.assertGreater(b[0], a[0])
        self.assertAlmostEqual(b[0] - a[0], 4 * telescope.nest_step_mm())

    def test_the_solid_beam_matches_a_plain_cantilever(self):
        """1 단이면 계단이 없으므로 3EI/L³ 와 같아야 한다."""
        part = dynamics._part(telescope.SHEET, "CD-BM-01")
        i = telescope._i_mm4(float(part.size[2]), float(part.size[1]),
                             float(part.t))
        want = 3 * afr.STEEL_E_MPA * i / telescope.reach_mm() ** 3
        self.assertAlmostEqual(telescope.solid_tip_stiffness_n_per_mm(), want,
                               places=6)

    def test_stiffness_falls_with_stages_and_returns_with_a_bigger_root(self):
        s = telescope.summary()
        self.assertLess(s["stiffAtDepthNmm"], s["solidStiffNmm"] * 0.5)
        self.assertGreater(s["stiffGrownNmm"], s["stiffAtDepthNmm"] * 2)

    def test_stiffness_is_not_what_blocks_it(self):
        """걸릴 줄 알았는데 안 걸린다 — 그 사실이 결론의 절반이다."""
        s = telescope.summary()
        self.assertLessEqual(s["deflGrownMm"], s["deflBudgetMm"])
        self.assertLess(s["deflGrownMm"], s["deflBudgetMm"] * 0.2)

    def test_the_impact_model_is_the_one_dynamics_wrote(self):
        """충돌을 여기서 다시 적지 않는다 — 강성만 갈아 끼운다."""
        self.assertAlmostEqual(telescope.catch_deflection_mm(1),
                               dynamics.catch_impact()["deflectionMm"], places=1)

    def test_the_stiffness_swap_is_put_back(self):
        """강성 함수를 잠시 바꿔 쓰므로 **되돌려 놓는지**를 본다."""
        before = dynamics.catch_beam_stiffness_n_per_mm()
        telescope.catch_deflection_mm(5)
        self.assertEqual(dynamics.catch_beam_stiffness_n_per_mm(), before)


class TestWhatActuallyBlocksIt(unittest.TestCase):
    def test_the_droop_does_not_depend_on_the_section(self):
        """유격 처짐은 단면을 키워도 안 준다 — 그래서 따로 센다."""
        self.assertGreater(telescope.tip_droop_mm(7), telescope.tip_droop_mm(3))
        self.assertEqual(telescope.tip_droop_mm(1), 0.0)

    def test_the_droop_eats_part_of_the_clearance(self):
        s = telescope.summary()
        self.assertGreater(s["droopShareOfClearance"], 0.2)
        self.assertLess(s["droopShareOfClearance"], 1.0)
        self.assertEqual(s["clearanceMm"], catch.BEAM_CLEARANCE_MM)

    def test_the_arrival_energy_grows_with_the_square_of_the_stages(self):
        """바깥 단이 실린더보다 빨라 에너지가 Σk² 로 는다."""
        one, seven = telescope.arrival_energy_j(1), telescope.arrival_energy_j(7)
        self.assertGreater(seven / one, 10.0)

    def test_pneumatic_stops_working_early(self):
        self.assertTrue(telescope.pneumatic_still_works(1))
        self.assertFalse(telescope.pneumatic_still_works(
            telescope.stages_for_depth()))

    def test_the_drive_must_be_a_servo(self):
        self.assertTrue(telescope.drive_must_be_servo())
        self.assertTrue(telescope.belt_removes_the_problem())

    def test_a_workable_stage_count_exists(self):
        n = telescope.smallest_workable_stages()
        self.assertIsNotNone(n)
        self.assertEqual(n, telescope.stages_for_depth())

    def test_every_check_passes_today(self):
        for name, ok, why in telescope.checks():
            with self.subTest(check=name):
                self.assertTrue(ok, f"{name} — {why}")

    def test_the_annotations_say_what_was_assumed(self):
        text = " ".join(telescope.annotations())
        for token in ("강접", "겹침 200", "OI-07"):
            self.assertIn(token, text, f"주석에 {token} 이 없다")


class TestItIsRegistered(unittest.TestCase):
    def test_the_open_item_carries_the_answer(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-07")
        text = item.title + item.why_open + item.closes_with + item.blocks
        for token in ("telescope.py", "서보", "단"):
            self.assertIn(token, text, f"OI-07 에 {token} 이 없다")

    def test_the_open_item_numbers_are_the_ones_the_module_computes(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-07")
        s = telescope.summary()
        for value in (f"{s['stowDepthMm']:.0f}", str(s["stagesForDepth"]),
                      f"{s['arrivalAtDepthJ']}", f"{s['droopAtDepthMm']}"):
            self.assertIn(value, item.why_open, f"OI-07 이 {value} 를 안 들고 있다")

    def test_the_open_item_carries_no_markdown(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-07")
        for field in (item.title, item.why_open, item.closes_with, item.blocks):
            self.assertNotIn("**", field)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
