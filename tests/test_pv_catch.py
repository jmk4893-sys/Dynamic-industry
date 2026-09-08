# -*- coding: utf-8 -*-
"""CD-101 포획빔의 시간 예산 — 결론이 값에서 나왔는지 되짚는다.

이 해석의 결론은 셋이고 셋 다 무거운 말이다:

  · **부품표에 완충이 빠져 있다** — 표준 에어쿠션으로는 도착 에너지를 못 먹는다.
  · **한 평면으로 두면 빔이 늦다** — 대기면 정지 1.7 s 중 받쳐 주는 것은 끝의
    0.27 s 뿐이라, 겹장 판정이 그 안에서 끝나야 한다는 조건이 새로 생긴다.
  · **상승 중에는 어느 평면에서도 무방비다** — 빔이 패널 밑으로 들어가야 하는데
    그 자리를 패널이 지나는 중이기 때문이다.

그래서 묻는 것을 넷으로 나눈다: 적분기가 맞는가 · 값이 부품표에서 오는가 ·
결론이 골라 적은 것이 아니라 유도된 것인가 · 다른 모듈과 같은 값을 쓰는가.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, air, catch, drives, dynamics, fabrication, kinematics


class TestTheIntegrator(unittest.TestCase):
    def test_the_deploy_time_does_not_move_when_the_step_halves(self):
        """Δt 를 반으로 줄여도 답이 안 변해야 한다 — 적분기를 믿을 근거."""
        v = catch.design_speed_ms()
        coarse, fine, ok = dynamics.converged(lambda dt: catch.deploy_time_s(v, dt),
                                              0.001)
        self.assertTrue(ok, f"{coarse:.4f} → {fine:.4f} s 로 움직인다")

    def test_the_run_actually_covers_the_stroke(self):
        """감은 결과가 행정을 다 갔는지 — 안 가고 끝나면 시간이 짧게 나온다."""
        tr = catch.deploy_run(catch.design_speed_ms())
        self.assertGreaterEqual(tr.x[-1] * 1_000.0,
                                catch.cylinder_stroke_mm() - 1.0)

    def test_the_constant_phase_matches_the_hand_calculation(self):
        """가속이 한 줌이므로 시간 ≈ 행정/속도 + 사전시간이어야 한다.

        틀리면 프로파일이 등속이 아니라 다른 무엇이 된 것이다.
        """
        v = 1.0
        hand = catch.cylinder_stroke_mm() / 1_000.0 / v + catch.VALVE_DEAD_MS / 1_000.0
        self.assertLess(abs(catch.deploy_time_s(v) - hand) / hand, 0.05,
                        f"등속 가정이 {hand:.3f} s 를 주는데 "
                        f"{catch.deploy_time_s(v):.3f} s 가 나왔다")

    def test_the_arrival_energy_is_the_kinetic_energy(self):
        """도착 에너지는 ½mv² 그대로다 — 공압은 감속을 프로파일로 못 만든다."""
        v = 0.9
        self.assertAlmostEqual(catch.arrival_energy_j(v),
                               0.5 * catch.moving_mass_kg() * v ** 2, places=6)

    def test_the_speed_for_a_window_inverts_the_time(self):
        """창에서 푼 속도로 다시 감으면 그 창이 나와야 한다."""
        w = 1.5
        v = catch.speed_for_window_ms(w)
        self.assertAlmostEqual(catch.deploy_time_s(v), w, places=2)


class TestTheValuesComeFromTheDrawingBook(unittest.TestCase):
    def test_the_bore_and_stroke_are_read_not_retyped(self):
        """Ø40 × 1,450 은 상용품 이름에서 읽는다 — 부품표를 바꾸면 따라와야 한다."""
        item = dynamics._commercial(catch.SHEET, "CD-RC-01")
        self.assertIn("Ø40", item.name)
        self.assertEqual(catch.cylinder_bore_mm(), 40.0)
        self.assertEqual(catch.cylinder_stroke_mm(), 1_450.0)

    def test_changing_the_cylinder_changes_the_answer(self):
        """부품표를 바꿨는데 답이 그대로면 어딘가 리터럴이 남아 있다.

        **부품표에서 읽는 값은 캐시가 걸려 있다** — 적분 안쪽에서 도면집을
        수만 번 다시 뒤지지 않으려는 것이다. 그래서 흔든 뒤에는 반드시
        `catch.clear_caches()` 를 부른다. 안 부르면 이 시험이 캐시된 옛 답을
        보고 「리터럴이 남았다」로 잘못 걸린다.
        """
        item = dynamics._commercial(catch.SHEET, "CD-RC-01")
        keep = item.name
        try:
            object.__setattr__(item, "name", "로드리스 실린더 Ø63 × 1,450")
            catch.clear_caches()
            self.assertEqual(catch.cylinder_bore_mm(), 63.0)
            self.assertGreater(catch.hold_force_n(), 1_500.0)
        finally:
            object.__setattr__(item, "name", keep)
            catch.clear_caches()
        self.assertEqual(catch.cylinder_bore_mm(), 40.0)

    def test_the_cache_is_what_makes_that_shake_need_clearing(self):
        """캐시가 실제로 걸려 있는지 — 위 시험의 전제를 못 박는다."""
        item = dynamics._commercial(catch.SHEET, "CD-RC-01")
        keep = item.name
        try:
            catch.clear_caches()
            before = catch.hold_force_n()
            object.__setattr__(item, "name", "로드리스 실린더 Ø63 × 1,450")
            self.assertEqual(catch.hold_force_n(), before, "캐시가 안 걸려 있다")
            catch.clear_caches()
            self.assertGreater(catch.hold_force_n(), before)
        finally:
            object.__setattr__(item, "name", keep)
            catch.clear_caches()

    def test_the_beam_mass_comes_from_the_section(self):
        """RHS 100×60×3.2 × 2,900 을 손으로 풀면 같은 값이 나와야 한다."""
        part = dynamics._part(catch.SHEET, "CD-BM-01")
        length, width, depth = part.size
        area = width * depth - (width - 2 * part.t) * (depth - 2 * part.t)
        want = area * length / 1e9 * afr.STEEL_DENSITY_KG_M3
        self.assertAlmostEqual(catch.beam_mass_kg(), want, places=6)
        self.assertTrue(20.0 < catch.beam_mass_kg() < 25.0,
                        f"{catch.beam_mass_kg():.1f} kg — 각관 2.9 m 치고 이상하다")

    def test_the_pressure_comes_from_the_air_system(self):
        """추력은 `air.USE_BAR` 에서 온다 — 여기 압력을 다시 적지 않는다."""
        area = math.pi * (catch.cylinder_bore_mm() / 2.0) ** 2
        self.assertAlmostEqual(catch.thrust_n(), air.USE_BAR / 10.0 * area, places=6)

    def test_the_window_comes_from_the_path_not_a_literal(self):
        """창은 `kinematics.PATH` 의 상승·대기 구간에서 온다."""
        self.assertAlmostEqual(catch.rise_seconds(),
                               kinematics.PATH[0][1] - kinematics.PATH[0][0])
        self.assertAlmostEqual(catch.dwell_seconds(),
                               kinematics.PATH[1][1] - kinematics.PATH[1][0])
        self.assertIn("포획빔", kinematics.PATH[1][2],
                      "대기 구간이 포획빔 전개를 위한 것이라는 기록이 사라졌다")


class TestWhereTheBeamCanStand(unittest.TestCase):
    def test_the_beam_cannot_be_higher_than_the_dwelling_panel(self):
        """대기 중인 패널 밑에 틈만큼은 남아야 한다."""
        self.assertEqual(catch.max_plane_mm(),
                         kinematics.SEPARATION_MM - catch.BEAM_CLEARANCE_MM)

    def test_a_plane_above_the_panel_never_opens(self):
        """평면을 대기면 위로 올리면 패널이 끝내 안 지나가므로 창이 없다."""
        too_high = kinematics.SEPARATION_MM + 1.0
        self.assertEqual(catch.clear_time_s(too_high), math.inf)
        self.assertEqual(catch.window_s(too_high), -math.inf)

    def test_raising_the_plane_costs_time_and_buys_energy(self):
        """맞바꿈이 실제로 단조인가 — 아니면 표를 볼 이유가 없다."""
        rows = catch.plane_options(50.0)
        self.assertGreater(len(rows), 3)
        for a, b in zip(rows, rows[1:]):
            self.assertLess(b["windowS"], a["windowS"], "높이면 창이 늘었다")
            self.assertGreater(b["speedMs"], a["speedMs"], "창이 줄었는데 느려도 된다")
            self.assertLess(b["residualJ"], a["residualJ"], "높였는데 낙하가 늘었다")

    def test_the_design_point_is_the_highest_plane(self):
        """결합력이 어느 평면에서도 안 걸리므로 낙하를 줄이는 쪽이 항상 옳다."""
        self.assertEqual(catch.design_plane_mm(), catch.max_plane_mm())
        self.assertLess(catch.residual_energy_j(catch.design_plane_mm()),
                        catch.unprotected_energy_j() * 0.1)


class TestWhatBindsThisAxis(unittest.TestCase):
    def test_the_magnetic_coupling_caps_the_force_below_the_thrust(self):
        """압력을 6 bar 로 올려도 캐리지가 받는 힘은 0.5 MPa 상당에서 멈춘다."""
        self.assertLess(catch.hold_force_n(), catch.thrust_n())
        self.assertAlmostEqual(catch.hold_force_n(),
                               catch.thrust_n(catch.RODLESS_HOLD_MPA), places=6)

    def test_acceleration_is_not_what_sets_the_window(self):
        """가속에 쓰는 행정이 한 줌이라 창을 정하는 것은 등속 속도다."""
        v = catch.design_speed_ms()
        self.assertLess(catch.accel_distance_mm(v), catch.cylinder_stroke_mm() * 0.05)

    def test_stopping_binds_before_pushing(self):
        """완충이 허락하는 속도가 결합력이 허락하는 속도보다 낮다."""
        self.assertTrue(catch.cushion_is_the_binding_limit())
        self.assertLess(catch.speed_for_energy_ms(catch.SHOCK_ABSORBER_J),
                        catch.coupling_speed_ms())

    def test_the_standard_cushion_cannot_stop_it(self):
        """이것이 부품표를 고치라는 결론의 근거다 — 값이 바뀌면 결론도 바뀌어야 한다."""
        self.assertFalse(catch.standard_cushion_is_enough())
        self.assertGreater(catch.arrival_energy_j(catch.design_speed_ms()),
                           catch.CUSHION_ALLOW_J * 5)

    def test_a_shock_absorber_does_stop_it(self):
        """못 멈추면 빔을 가볍게 하는 수밖에 없다 — 그건 다른 이야기다."""
        self.assertTrue(catch.shock_absorber_is_enough())

    def test_the_bom_has_no_absorber_yet(self):
        """결론이 「부품표에 없다」이므로 **정말 없는지**를 시험이 붙잡는다.

        나중에 누가 업소버를 넣으면 이 시험이 걸리고, 그때 OI-05 를 닫으면 된다.
        """
        items = fabrication.assembly(catch.SHEET)
        names = " ".join(c.name + c.spec for c in items.commercial)
        self.assertNotIn("쇼크업소버", names)
        self.assertNotIn("업소버", names)


class TestWhenTheBeamArrives(unittest.TestCase):
    def test_fitting_the_window_is_not_the_same_as_being_early(self):
        """창 안에 들어도 대기면 정지의 대부분이 지나 버린다 — 이 해석의 요점이다."""
        plane, v = catch.design_plane_mm(), catch.design_speed_ms()
        self.assertLessEqual(catch.deploy_time_s(v), catch.window_s(plane))
        self.assertGreater(catch.exposure_s(plane, v),
                           catch.protected_dwell_s(plane, v),
                           "받쳐 주는 시간이 무방비 시간보다 길면 결론이 뒤집힌다")

    def test_the_protected_part_of_the_dwell_is_short(self):
        """겹장 판정에 주는 조건 — 이 시간 안에 끝나야 한다."""
        plane, v = catch.design_plane_mm(), catch.design_speed_ms()
        protected = catch.protected_dwell_s(plane, v)
        self.assertGreater(protected, 0.0, "아예 못 받치면 빔을 다는 뜻이 없다")
        self.assertLess(protected, catch.dwell_seconds() / 2)

    def test_the_rise_is_unprotected_at_every_plane(self):
        """상승 중에는 어느 평면에서도 빔이 못 들어간다 — 패널이 그 자리를 지난다."""
        for plane in (0.0, 100.0, 250.0, catch.max_plane_mm()):
            self.assertGreater(catch.clear_time_s(plane), 0.0)
            self.assertLessEqual(catch.clear_time_s(plane), catch.rise_seconds())

    def test_two_stages_buy_time_but_not_energy(self):
        """낮게 내고 올리면 노출은 크게 주는데 **그 순간의 낙하는 안 준다.**

        둘을 뭉뚱그리면 2단이 만능처럼 보인다. 다르다는 것을 값이 말해야 한다.
        """
        plane, v = catch.design_plane_mm(), catch.design_speed_ms()
        two = catch.two_stage()
        self.assertTrue(catch.two_stage_is_worth_it())
        self.assertLess(two["exposureS"], catch.exposure_s(plane, v) / 2)
        self.assertGreater(two["worstJ"], catch.residual_energy_j(plane) * 10)

    def test_the_lift_the_two_stage_asks_for_is_modest(self):
        """올리는 속도가 터무니없으면 2단은 답이 아니다 — CD-Z 가 낼 수 있어야 한다."""
        two = catch.two_stage()
        self.assertLess(two["liftPeakMs"], 1.0,
                        f"{two['liftPeakMs']} m/s 는 랙&피니언에 무리다")
        self.assertGreater(two["liftSpanS"], 0.5)

    def test_the_two_stage_uses_hardware_that_already_exists(self):
        """부품표에 카세트 승강축이 있다 — 없는 것을 전제로 한 결론이면 안 된다."""
        item = dynamics._commercial(catch.SHEET, "CD-Z-01")
        self.assertIn("승강", item.name)
        self.assertIn("랙", item.spec)


class TestItAgreesWithTheRestOfTheModel(unittest.TestCase):
    def test_the_unprotected_energy_is_the_one_dynamics_computed(self):
        """163 J 을 여기서 다시 세지 않는다 — 두 곳에 두면 갈라진다."""
        self.assertAlmostEqual(catch.unprotected_energy_j(),
                               dynamics.double_sheet_energy_j(), places=6)

    def test_the_residual_uses_the_same_panel_and_gravity(self):
        """남는 낙하도 같은 질량·중력으로 낸다."""
        plane = 200.0
        want = drives.PANEL_KG * dynamics.G * (kinematics.SEPARATION_MM - plane) / 1e3
        self.assertAlmostEqual(catch.residual_energy_j(plane), want, places=6)

    def test_the_beam_that_catches_is_the_beam_dynamics_sized(self):
        """받는 빔과 나오는 빔이 같은 부재여야 한다."""
        self.assertEqual(catch.SHEET, dynamics.SHEET_CATCH)
        self.assertEqual(dynamics._part(catch.SHEET, "CD-BM-01").qty, 4)

    def test_moving_the_stroke_moves_the_answer(self):
        """행정이 바뀌면 창도 속도도 따라와야 한다 — 얼어붙은 숫자 검사."""
        before = catch.design_speed_ms()
        item = dynamics._commercial(catch.SHEET, "CD-RC-01")
        keep = item.name
        try:
            object.__setattr__(item, "name", "로드리스 실린더 Ø40 × 2,900")
            self.assertGreater(catch.design_speed_ms(), before * 1.5)
        finally:
            object.__setattr__(item, "name", keep)
        self.assertAlmostEqual(catch.design_speed_ms(), before, places=6)

    def test_every_check_passes_today(self):
        for name, ok, why in catch.checks():
            with self.subTest(check=name):
                self.assertTrue(ok, f"{name} — {why}")

    def test_the_annotations_carry_the_numbers(self):
        """문장이 값에서 나와야 한다 — 손으로 쓰면 값이 바뀌어도 안 따라온다."""
        s = catch.summary()
        text = " ".join(catch.annotations())
        for token in (str(s["arrivalJ"]), str(s["exposureS"]),
                      str(s["unprotectedJ"]), "OI-05"):
            self.assertIn(token, text, f"주석에 {token} 이 없다")


class TestItIsRegistered(unittest.TestCase):
    def test_the_open_item_says_what_the_test_must_measure(self):
        """OI-05 가 「실물에서만 나온다」로 끝나면 안 된다 — 무엇을 잴지가 있어야 한다."""
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-05")
        text = item.why_open + item.closes_with + item.blocks
        for token in ("catch.py", "쇼크업소버", "노출"):
            self.assertIn(token, text, f"OI-05 에 {token} 이 없다")

    def test_the_open_item_numbers_are_the_ones_the_module_computes(self):
        """미결 항목에 손으로 적힌 숫자가 해석과 갈라지면 안 된다.

        문장은 사람이 쓰지만 값은 `catch.py` 것이다. 여기서 갈라지면 제작
        도면집이 옛 답을 싣고 다니게 된다 — 그것이 이 회차에 케이싱에서 겪은
        일이고, 같은 방식으로 늙는 자리다.
        """
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-05")
        s = catch.summary()
        two = s["twoStage"]
        for value in (f"{s['residualJ']}", f"{s['arrivalJ']}",
                      f"{s['windowS']:.2f}", f"{s['speedMs']}",
                      f"{s['exposureS']}", f"{s['protectedDwellS']}",
                      f"{two['exposureS']}",
                      f"{s['residualMm']:.0f} mm"):
            self.assertIn(value, item.why_open,
                          f"OI-05 이 {value} 를 안 들고 있다 — 해석과 갈라졌다")

    def test_the_open_item_carries_no_markdown(self):
        """제작 도면집은 별표를 그대로 찍는다 — 다른 항목과 같은 규약이다."""
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-05")
        for field in (item.title, item.why_open, item.closes_with, item.blocks):
            self.assertNotIn("**", field)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
