# -*- coding: utf-8 -*-
"""강체 엔진 — 믿을 근거를 먼저 만들고 나서 쓴다.

새 엔진은 기존 답을 뒤집을 수 있으므로 순서가 중요하다. 넷으로 나눈다:

  · **적분기와 회전이 맞는가** — 자유낙하·편심 충격량·순간중심.
  · **마찰이 두 갈래 다 맞는가** — 붙어 있을 때 안 움직이고, 미끄러지면
    a = g(sinα − μcosα) 로 움직이는가.
  · **접촉이 분포로 잡히는가** — 전도 한계 a/g = b/h 를 앞뒤로 낀다.
  · **기존 답을 지운 게 아니라 넓혔는가** — 대칭 낙하가
    `dynamics.catch_impact` 를 그대로 재현하는가. 이것이 제일 중요하다.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, catch, drives, dynamics, rigid


class TestTheIntegrator(unittest.TestCase):
    def test_free_fall_matches_half_g_t_squared(self):
        got, want = rigid.free_fall()
        self.assertAlmostEqual(got / want, 1.0, places=4)

    def test_gravity_is_the_same_number_as_dynamics(self):
        """중력을 두 곳에 적었다 — 두 모듈이 다른 답을 내면 안 된다.

        `dynamics` 를 들여오면 순환이 되어 값을 공유하지 못한다. 그래서
        **시험이 정본 노릇을 한다.** 한쪽만 고치면 여기서 걸린다.
        """
        self.assertEqual(rigid.G, dynamics.G)

    def test_semi_implicit_euler_does_not_grow_energy(self):
        """감쇠 없는 접촉 위에서 오래 튀겨도 에너지가 안 자라는가.

        **한 순간끼리 견주면 안 된다.** 반음시 오일러는 에너지를 O(dt) 폭
        안에서 흔든다 — 자라지 않을 뿐 일정하지도 않다. 그래서 앞뒤 구간의
        **최대값**을 견준다. 명시 오일러라면 이 값이 계속 자란다.
        """
        w = rigid.World()
        b = w.body(1.0, 1.0, y=0.01)
        sup = w.support(y0=0.0, k=1e5)
        w.contact(b, 0.0, 0.0, sup)
        early = late = 0.0
        for i in range(200_000):
            w.step(2e-5)
            e = b.kinetic_j() + 1.0 * rigid.G * b.y
            if i < 20_000:
                early = max(early, e)
            elif i >= 180_000:
                late = max(late, e)
        self.assertLessEqual(late, early * 1.01, "적분기가 에너지를 만든다")


class TestRotation(unittest.TestCase):
    def test_offcentre_impulse_gives_v_and_omega(self):
        d = rigid.offcentre_impulse()
        self.assertAlmostEqual(d["v"], d["vClosed"], places=9)
        self.assertAlmostEqual(d["w"], d["wClosed"], places=9)

    def test_the_instant_centre_stands_still(self):
        """편심 충격량 뒤 I/(md) 자리의 속도가 0 인가 — 회전 결합의 검산."""
        self.assertAlmostEqual(rigid.offcentre_impulse()["pivotSpeed"], 0.0,
                               places=9)

    def test_a_point_on_a_turned_body_lands_where_geometry_says(self):
        b = rigid.Body(1.0, 1.0, x=2.0, y=3.0, th=math.pi / 2)
        x, y = b.world(1.0, 0.0)
        self.assertAlmostEqual(x, 2.0, places=9)
        self.assertAlmostEqual(y, 4.0, places=9)


class TestFriction(unittest.TestCase):
    def test_it_slides_at_the_closed_form_acceleration(self):
        d = rigid.block_on_incline(30.0, 0.20)
        self.assertTrue(d["slips"])
        self.assertAlmostEqual(d["accel"] / d["accelClosed"], 1.0, places=2)

    def test_it_does_not_slide_when_the_angle_is_below_the_cone(self):
        d = rigid.block_on_incline(10.0, 0.40)
        self.assertFalse(d["slips"])
        self.assertLess(abs(d["slid"]), 1e-5, "붙어 있어야 하는데 흘렀다")

    def test_the_boundary_is_where_tan_alpha_equals_mu(self):
        """마찰뿔 앞뒤로 낀다.

        **붙어 있어도 0 은 아니다** — 접선 스프링이 요구 힘만큼 늘어난다
        (여기서는 1.4 µm). 절대 epsilon 으로 재면 그 탄성변형을 미끄러짐으로
        읽게 되므로, 미끄러진 쪽과의 **비**로 본다.
        """
        mu = 0.30
        edge = math.degrees(math.atan(mu))
        stuck = abs(rigid.block_on_incline(edge - 2.0, mu)["slid"])
        slid = rigid.block_on_incline(edge + 4.0, mu)["slid"]
        self.assertGreater(slid, 1e-3, "마찰뿔 밖인데 안 미끄러진다")
        self.assertLess(stuck, slid / 100.0, "마찰뿔 안인데 흘렀다")


class TestContactDistribution(unittest.TestCase):
    def test_the_tipping_threshold_is_the_aspect_ratio(self):
        """a/g = b/h 를 앞뒤로 낀다 — 반폭과 반높이가 같으니 1.0 이다."""
        self.assertFalse(rigid.block_tips(0.98)["tipped"])
        self.assertTrue(rigid.block_tips(1.02)["tipped"])

    def test_not_tipping_still_leans(self):
        """안 넘어가도 앞쪽이 더 받는다 — 접촉이 분포로 잡혔다는 뜻."""
        d = rigid.block_tips(0.9)
        self.assertGreater(d["frontN"], d["rearN"])


class TestItReproducesTheOneDegreeOfFreedomModel(unittest.TestCase):
    """**이 반이 제일 중요하다.** 새 엔진이 기존 답과 다르면 둘 중 하나가 틀렸다."""

    def test_a_symmetric_drop_reproduces_catch_impact(self):
        ref = dynamics.catch_impact()
        got = rigid.symmetric_drop(
            drives.PANEL_KG, ref["impactMs"],
            dynamics.catch_beam_stiffness_n_per_mm() * 1_000.0,
            dynamics.CONTACT_DAMPING)
        self.assertAlmostEqual(got["peakN"] / ref["peakN"], 1.0, places=3)
        self.assertAlmostEqual(got["deflectionMm"] / ref["deflectionMm"], 1.0,
                               places=3)

    def test_a_symmetric_drop_does_not_rotate(self):
        ref = dynamics.catch_impact()
        got = rigid.symmetric_drop(
            drives.PANEL_KG, ref["impactMs"],
            dynamics.catch_beam_stiffness_n_per_mm() * 1_000.0,
            dynamics.CONTACT_DAMPING)
        self.assertLess(abs(got["tilt"]), 1e-9, "대칭인데 돌았다")


class TestTheModalReduction(unittest.TestCase):
    """하이브리드의 관성이 어디서 왔는가 — 두 식이 서로를 검산한다."""

    def _beam(self):
        part = catch._beam()
        length, width, depth = part.size
        t = part.t
        i = (width * depth ** 3 - (width - 2 * t) * (depth - 2 * t) ** 3) / 12.0
        return length, i, catch.beam_mass_kg()

    def test_the_textbook_factor_and_the_frequency_agree(self):
        """0.2427 배와 닫힌 해 진동수가 같은 이야기인가 — 오타를 잡는 시험."""
        length, i, mass = self._beam()
        hz = rigid.cantilever_hz(afr.STEEL_E_MPA, i, mass, length)
        k_tip = 3 * afr.STEEL_E_MPA * i / length ** 3 * 1_000.0     # N/m
        self.assertAlmostEqual(rigid.modal_mass_from_hz(k_tip, hz)
                               / rigid.modal_mass_kg(mass), 1.0, places=6)

    def test_the_factor_is_three_over_lambda_to_the_fourth(self):
        self.assertAlmostEqual(rigid.modal_mass_kg(1.0),
                               3.0 / 1.875104 ** 4, places=9)

    def test_a_massless_support_is_the_old_assumption(self):
        """질량 0 이면 표면이 안 움직이고 지지 스프링이 곧 접촉 스프링이다."""
        s = rigid.Support(y0=0.0, k=1_000.0)
        self.assertFalse(s.moves)
        self.assertEqual(s.surface, 0.0)
        self.assertEqual(s.stiffness(), 1_000.0)

    def test_a_modal_support_uses_the_penalty_to_couple(self):
        s = rigid.flexible_support(0.0, 1_000.0, 10.0)
        self.assertTrue(s.moves)
        self.assertEqual(s.stiffness(), 1_000.0 * rigid.PENALTY_RATIO)


class TestTheNumericalDevicesAreDevices(unittest.TestCase):
    def test_the_penalty_ratio_does_not_set_the_answer(self):
        """벌칙 강성비를 30…300 으로 바꿔도 지지 스프링 힘이 그대로인가."""
        ref = dynamics.catch_impact()
        k = dynamics.catch_beam_stiffness_n_per_mm() * 1_000.0

        def run() -> float:
            return rigid.symmetric_drop(drives.PANEL_KG, ref["impactMs"], k,
                                        dynamics.CONTACT_DAMPING)["peakN"]

        self.assertLess(rigid.insensitive_to_penalty(run)["spread"], 0.01)

    def test_every_validation_lands_on_its_closed_form(self):
        for name, (got, want) in rigid.validations().items():
            with self.subTest(name):
                if want == 0.0:
                    self.assertLess(abs(got), 1e-6, name)
                else:
                    self.assertAlmostEqual(got / want, 1.0, places=2, msg=name)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
