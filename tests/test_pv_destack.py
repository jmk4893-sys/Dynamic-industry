# -*- coding: utf-8 -*-
"""무프레임 적층 분리 — 해석이 스스로를 증명하게 한다.

여기서 나오는 결론은 **설비 하나를 새로 달자**는 것이다. 그런 결론은 근거가
헐거우면 안 되므로 묻는 것을 넷으로 나눈다:

  · **솔버가 맞는가** — 알려진 닫힌 해와 맞는지, 격자를 늘려도 안 변하는지.
  · **세 방법의 차이가 물리에서 오는가** — 틈·각·속도를 흔들면 지수가 맞게 나오는지.
  · **설계점이 유도된 값인가** — 골라 적은 값이면 설계가 바뀌어도 안 움직인다.
  · **하드웨어 주장이 도면집과 맞는가** — 「라인샤프트라 못 기운다」는 부품표가 근거다.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, destack, dynamics, fabrication


class TestSolver(unittest.TestCase):
    def test_the_strip_matches_the_closed_form_for_a_parallel_gap(self):
        """나란한 틈은 손으로 풀린다.

        p'' = 12μv/h³ 를 p(0)=p(L)=0 으로 풀면 p = (6μv/h³)(x²−Lx) 이고,
        폭 W 로 적분하면 **F = μ W L³ v / h³** 다. 솔버가 이것을 못 맞추면
        나머지 답은 볼 것도 없다.
        """
        L, W, h, v = 2.0, 1.0, 1e-4, 0.01
        got = destack.reynolds_strip_n(L, W, lambda _x: h, lambda _x: v)
        want = dynamics.AIR_VISCOSITY_PAS * W * L ** 3 * v / h ** 3
        self.assertAlmostEqual(got / want, 1.0, places=3,
                               msg=f"닫힌 해 {want:,.0f} N 과 {got:,.0f} N 이 다르다")

    def test_the_answer_does_not_move_when_the_grid_doubles(self):
        """격자를 두 배로 해도 답이 안 변해야 한다 — 적분기를 믿을 근거."""
        args = (2.5, 1.4, lambda x: 5e-5 + 0.004 * x, lambda x: 0.16 * x)
        coarse = destack.reynolds_strip_n(*args, steps=1_500)
        fine = destack.reynolds_strip_n(*args, steps=6_000)
        self.assertLess(abs(fine - coarse) / abs(coarse), 0.01,
                        f"격자에 따라 흔들린다 — {coarse:,.1f} → {fine:,.1f} N")

    def test_the_force_scales_with_the_cube_of_the_gap(self):
        """틈을 두 배로 하면 힘이 1/8 — 물리가 제대로 들어갔는지 본다."""
        a = destack.flat_lift_n(0.1, 0.2)
        b = destack.flat_lift_n(0.1, 0.4)
        self.assertAlmostEqual(a / b, 8.0, places=2)

    def test_the_force_is_linear_in_speed(self):
        a = destack.flat_lift_n(0.1)
        b = destack.flat_lift_n(0.2)
        self.assertAlmostEqual(b / a, 2.0, places=6)


class TestThreeWays(unittest.TestCase):
    """곧게 들기 · 젖히기 · 밀기 — 답이 아홉 자릿수 벌어진다."""

    def test_lifting_flat_off_bare_glass_is_hopeless(self):
        """속도로 풀 수 있는 문제가 아니다.

        「그럼 천천히 들면 되지 않나」가 첫 반문이라 그것부터 막는다 — 1 µm/s
        (0.05 mm 를 여는 데만 50 초)에서도 컵 능력을 넘는다.
        """
        self.assertTrue(destack.flat_lift_is_hopeless())
        self.assertGreater(destack.flat_lift_n(1e-6), destack.usable_cup_n())

    def test_peeling_is_orders_of_magnitude_cheaper_than_lifting_flat(self):
        c = destack.compare()
        self.assertGreater(c["flatN"] / c["wedge050N"], 1e6,
                           "젖힘이 곧게 들기보다 자릿수로 싸지 않다 — 결론이 흔들린다")

    def test_shearing_is_free_but_does_not_open_the_gap(self):
        """미는 것과 떼는 것은 다른 일이다.

        면내 전단은 공짜지만(1 N 도 안 된다) 틈이 안 열린다. 이미 있는 헤드
        슬라이드(`BFC-SLD-01` 행정 100)로 무프레임을 풀 수 없는 이유다.
        """
        self.assertLess(destack.shear_n(0.05), 1.0)
        self.assertTrue(destack.head_slide_is_in_plane())

    def test_the_framed_stack_is_the_easy_case(self):
        """프레임이 있으면 같은 계산이 세 자릿수로 싸진다 — 8 mm 가 하는 일이다."""
        c = destack.compare()
        self.assertLess(c["framedN"], c["usableN"])
        self.assertGreater(c["flatN"] / c["framedN"], 1e5)


class TestTwoModelsAgree(unittest.TestCase):
    def test_the_strip_is_the_conservative_one(self):
        """스트립(옆으로 안 샘)이 원판 근사보다 커야 한다.

        비가 1 밑으로 뒤집히면 둘 중 하나가 틀린 것이다. 실제는 둘 사이이고,
        어느 쪽을 쓰느냐는 **틈이 자리마다 다른가**로 갈린다.
        """
        ratio = destack.strip_over_disc()
        self.assertGreater(ratio, 1.0, "스트립이 원판보다 작다 — 모델 하나가 틀렸다")
        self.assertLess(ratio, 10.0, "두 모델이 너무 벌어진다 — 같은 물리가 아니다")

    def test_both_modules_use_the_same_air_and_the_same_gap(self):
        """물성을 두 곳에 적으면 갈라진다."""
        self.assertEqual(destack.contact_gap_m(),
                         dynamics.GLASS_CONTACT_GAP_MM / 1_000.0)


class TestGlassSetsTheFloor(unittest.TestCase):
    def test_a_short_peel_breaks_the_laminate(self):
        """짧게 젖힐수록 필름은 싸지지만 유리가 깨진다 — 그것이 하한이다."""
        short = destack.glass_stress_mpa(100.0, destack.EDGE_LIFT_MM)
        self.assertGreater(short, afr.GLASS_ALLOW_MPA,
                           "100 mm 젖힘이 허용응력 안이라면 유리 물성을 다시 보라")

    def test_the_floor_comes_from_the_glass_properties(self):
        """하한이 `afr` 물성에서 나오는가 — 여기 다시 적으면 갈라진다."""
        want = math.sqrt(1.5 * afr.GLASS_E_MPA * afr.LAMINATE_T_MM
                         * destack.EDGE_LIFT_MM * 2.0 / afr.GLASS_ALLOW_MPA)
        self.assertAlmostEqual(destack.min_peel_length_mm(), want, places=6)

    def test_the_design_peel_length_clears_the_floor(self):
        d = destack.edge_lifter()
        self.assertGreaterEqual(d["peelLenMm"], d["minLenMm"])
        self.assertLessEqual(d["stressMpa"], afr.GLASS_ALLOW_MPA)


class TestDerivedNotChosen(unittest.TestCase):
    def test_the_edge_lift_is_solved_for_not_picked(self):
        """선언한 15 mm 가 유도한 하한을 덮는가.

        고른 값은 설계가 바뀌어도 안 움직인다. 진공 안전율 2.0 을 본 헤드에서도
        지키려면 얼마여야 하는지를 이분법이 풀고, 상수는 그것을 덮기만 한다.
        """
        self.assertTrue(destack.edge_lift_covers_the_margin(),
                        f"선언 {destack.EDGE_LIFT_MM} < 유도 "
                        f"{destack.min_edge_lift_mm():.2f} mm")
        self.assertLess(destack.min_edge_lift_mm(), destack.EDGE_LIFT_MM * 1.5,
                        "상수가 유도값보다 너무 크다 — 근거 없이 키운 값이다")

    def test_a_bigger_lift_buys_margin_fast(self):
        """필름이 각의 세제곱에 반비례하므로 조금만 더 들면 여유가 확 는다."""
        speed = dynamics.sep_peel()["peakMs"]
        self.assertGreater(destack.wedge_lift_n(10.0, speed)
                           / destack.wedge_lift_n(20.0, speed), 5.0)

    def test_the_margin_target_is_the_vacuum_safety_already_declared(self):
        """새 안전율을 만들지 않는다 — 이미 선언된 것을 쓴다."""
        head = destack.main_head_after_crack()
        self.assertGreaterEqual(head["margin"], dynamics.VACUUM_SAFETY)


class TestHardwareClaim(unittest.TestCase):
    def test_the_lineshaft_is_why_the_carriage_cannot_tilt(self):
        """「본 캐리지로는 못 젖힌다」의 근거가 부품표에 있어야 한다.

        `BFC-LS-01` 라인샤프트가 두 볼스크루를 1:1 로 잇고 서보는 하나다.
        라인샤프트를 빼면 이 주장이 무너지므로 시험이 그 존재를 붙잡는다.
        """
        self.assertTrue(destack.screws_are_coupled())
        asm = fabrication.assembly(dynamics.SHEET_BFC)
        shaft = next(c for c in asm.commercial if c.tag == "BFC-LS-01")
        self.assertIn("베벨", shaft.name + shaft.spec)
        servos = [c for c in asm.commercial if c.tag == "BLZ-101"]
        self.assertEqual(len(servos), 1)
        self.assertEqual(servos[0].qty, 1, "승강 서보가 둘이면 갠트리로 젖힐 수 있다")

    def test_the_conclusion_is_that_new_hardware_is_needed(self):
        self.assertTrue(destack.needs_an_edge_lifter())

    def test_every_check_passes_today(self):
        for name, (need, have, ok) in destack.checks().items():
            with self.subTest(name):
                self.assertTrue(ok, f"{name} — 요구 {need:.2f} · 능력 {have:.2f}")


class TestRegistered(unittest.TestCase):
    """결론이 미결 항목과 레시피에 올라가 있는가 — 모듈 안에만 있으면 없는 것이다."""

    def test_the_open_item_names_the_frameless_infeed(self):
        items = {o.tag: o for o in fabrication.OPEN_ITEMS}
        self.assertIn("OI-08", items, "무프레임 투입 전략이 미결 항목에 없다")
        text = items["OI-08"].title + items["OI-08"].why_open
        for token in ("무프레임", "엣지"):
            self.assertIn(token, text, f"OI-08 에 {token} 이 없다")

    def test_the_recipe_says_the_infeed_is_conditional(self):
        """`recipe` 가 「AFR 인발 생략」만 적고 있으면 투입부가 조용히 막힌다."""
        from pv_preprocess import recipe
        frameless = next(s for s in recipe.STRUCTURES if s.ui == "frameless")
        blob = " ".join(str(v) for v in vars(frameless).values())
        self.assertIn("엣지", blob, "무프레임 레시피에 투입 조건이 없다")


if __name__ == "__main__":
    unittest.main()
