# -*- coding: utf-8 -*-
"""포탈 하중 경로 — 3차원 요소를 먼저 믿을 수 있게 만들고 나서 답한다.

OI-04 의 결론은 「가새를 넣을지 말지」가 아니라 **「받침보를 닫을지 열지」**로
바뀐다. 그런 뒤집기는 근거가 헐거우면 안 되므로 넷으로 나눈다:

  · **요소가 맞는가** — 굽힘 두 축·비틀림·양단고정을 닫힌 해와 맞춘다.
  · **자리가 유도값인가** — 220 을 손으로 적었는지, 모델에서 나오는지.
  · **결론이 물리에서 오는가** — J 를 두 자릿수 낮추면 답이 따라 뒤집히는지.
  · **모르는 것을 모른다고 하는가** — 부품표에 없는 부재를 세웠다고 적었는지.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, dynamics, fabrication, frame3, kinematics, portal, ring


class TestTheElement(unittest.TestCase):
    SEC = frame3.box_section(260.0, 180.0, 8.0)
    L, P, T = 2_000.0, 1_000.0, 1e6

    def _cantilever(self, comp: int) -> float:
        fr = frame3.Frame3()
        a, b = fr.node(0, 0, 0), fr.node(self.L, 0, 0)
        fr.member(a, b, self.SEC)
        fr.fix(a)
        fr.load(b, **{("fy" if comp == 1 else "fz"): -self.P})
        return abs(fr.solve()[6 * b + comp])

    def test_bending_matches_the_closed_form_on_both_axes(self):
        """PL³/3EI 를 두 축에서 각각 맞춘다 — 한 축만 보면 Iy·Iz 가 바뀐 것을 놓친다."""
        e = afr.STEEL_E_MPA
        self.assertAlmostEqual(self._cantilever(1),
                               self.P * self.L ** 3 / (3 * e * self.SEC["Iz"]),
                               places=3)
        self.assertAlmostEqual(self._cantilever(2),
                               self.P * self.L ** 3 / (3 * e * self.SEC["Iy"]),
                               places=3)

    def test_the_two_axes_are_not_the_same(self):
        """단면이 260×180 이라 두 축이 달라야 한다 — 같으면 이름이 뒤바뀐 것이다."""
        self.assertGreater(self.SEC["Iz"], self.SEC["Iy"] * 1.5)

    def test_torsion_matches_TL_over_GJ(self):
        fr = frame3.Frame3()
        a, b = fr.node(0, 0, 0), fr.node(self.L, 0, 0)
        fr.member(a, b, self.SEC)
        fr.fix(a)
        fr.load(b, mx=self.T)
        got = fr.solve()[6 * b + 3]
        want = self.T * self.L / (frame3.shear_modulus_mpa() * self.SEC["J"])
        self.assertAlmostEqual(got / want, 1.0, places=3)

    def test_a_fixed_fixed_beam_matches_PL3_over_192EI(self):
        """양단고정 중앙하중 — 조립과 구속이 같이 맞아야 나오는 값이다."""
        fr = frame3.Frame3()
        a = fr.node(0, 0, 0)
        m = fr.node(self.L / 2, 0, 0)
        b = fr.node(self.L, 0, 0)
        fr.member(a, m, self.SEC)
        fr.member(m, b, self.SEC)
        fr.fix(a)
        fr.fix(b)
        fr.load(m, fy=-self.P)
        got = abs(fr.solve()[6 * m + 1])
        want = self.P * self.L ** 3 / (192 * afr.STEEL_E_MPA * self.SEC["Iz"])
        self.assertAlmostEqual(got / want, 1.0, places=2)

    def test_a_vertical_member_does_not_break_the_local_axes(self):
        """수직 부재는 기준벡터가 부재와 나란해져 외적이 0 이 되는 함정이 있다."""
        fr = frame3.Frame3()
        a, b = fr.node(0, 0, 0), fr.node(0, self.L, 0)
        fr.member(a, b, self.SEC)
        fr.fix(a)
        fr.load(b, fx=self.P)
        u = fr.solve()                      # 특이행렬이면 여기서 터진다
        self.assertGreater(abs(u[6 * b]), 0.0)

    def test_closing_the_section_is_what_makes_torsion_stiff(self):
        """열린 단면의 J 는 두 자릿수 작다 — 굽힘은 거의 그대로여야 한다."""
        op = frame3.open_box_section(260.0, 180.0, 8.0)
        self.assertLess(op["J"], self.SEC["J"] / 100)
        self.assertAlmostEqual(op["Iz"], self.SEC["Iz"], places=6)

    def test_the_shear_modulus_comes_from_the_modulus(self):
        self.assertAlmostEqual(frame3.shear_modulus_mpa(),
                               afr.STEEL_E_MPA / (2 * (1 + frame3.STEEL_NU)))


class TestThePlacesAreDerived(unittest.TestCase):
    def test_the_eccentricity_is_not_a_literal(self):
        """OI-04 의 220 이 어디서 나오는지 — 기둥 자리와 링 피치의 차다."""
        self.assertEqual(portal.eccentricity_mm(), 220.0)
        self.assertEqual(portal.eccentricity_mm(),
                         kinematics.PORTAL_COLUMN_AXIS_MM
                         - kinematics.RING_PITCH_MM / 2)

    def test_moving_the_ring_pitch_moves_the_eccentricity(self):
        keep = kinematics.RING_PITCH_MM
        try:
            kinematics.RING_PITCH_MM = 2_600
            self.assertEqual(portal.eccentricity_mm(), 300.0)
        finally:
            kinematics.RING_PITCH_MM = keep
        self.assertEqual(portal.eccentricity_mm(), 220.0)

    def test_the_roller_places_come_from_the_ring_module(self):
        """지지 반각을 두 곳에 적으면 갈라진다 — `ring` 이 정본이다."""
        half = math.radians(ring.SUPPORT_HALF_ANGLE_DEG)
        r = kinematics.RING_R_MM + kinematics.RING_TUBE_MM
        x, y = portal.roller_positions()[1]
        self.assertAlmostEqual(x, r * math.sin(half))
        self.assertAlmostEqual(y, kinematics.FLIP_AXIS_MM - r * math.cos(half))

    def test_the_reaction_comes_from_the_ring_solution(self):
        self.assertAlmostEqual(portal.analyse()["reactionN"],
                               max(ring.analyse()["rollerN"]), places=6)

    def test_the_criterion_is_the_ring_runout(self):
        """판정선을 여기서 다시 적지 않는다 — 링 선삭 공차가 그대로 산다."""
        self.assertEqual(portal.summary()["runoutMm"], ring.runout_mm())


class TestTheMissingMember(unittest.TestCase):
    def test_the_housing_cannot_reach_the_crossbeam(self):
        """OI-04 의 첫 발견 — 부품표만으로는 롤러가 안 받쳐진다."""
        self.assertFalse(portal.housing_reaches_the_crossbeam())
        self.assertGreater(portal.missing_drop_mm(), 500.0)

    def test_the_gap_is_between_the_crossbeam_and_the_roller(self):
        self.assertGreater(portal.crossbeam_y_mm(), portal.roller_axis_y_mm())
        self.assertAlmostEqual(
            portal.missing_drop_mm(),
            portal.crossbeam_y_mm() - portal.roller_axis_y_mm()
            - float(dynamics._part(portal.SHEET, "BFC-BB-01").size[2]), places=6)

    def test_the_assembly_step_still_says_the_crossbeam(self):
        """조립 순서가 「크로스빔 탭에」라고 적고 있는 것이 근거다.

        나중에 누가 그 문장을 고치면 이 시험이 걸리고, 그때 위 발견도 다시 봐야 한다.
        """
        steps = fabrication.assembly(portal.SHEET).steps
        text = " ".join(s.text for s in steps if "롤러" in s.title)
        self.assertIn("크로스빔", text)

    def test_the_support_beam_is_declared_as_new(self):
        import inspect
        src = inspect.getsource(portal)
        i = src.find("SUPPORT_BEAM_MM = ")
        self.assertIn("부품표에 없는 부재", src[max(0, i - 300):i])


class TestWhatActuallyDecidesIt(unittest.TestCase):
    def test_the_closed_beam_carries_the_eccentricity_easily(self):
        s = portal.summary()
        self.assertTrue(s["A"]["ok"])
        self.assertLess(s["A"]["worstSagMm"], s["runoutMm"] * 0.25)
        self.assertLess(s["A"]["peakMpa"], s["allowMpa"] * 0.05)

    def test_the_brace_buys_almost_nothing_on_a_closed_beam(self):
        """가새는 무게와 자리를 더할 뿐이다 — 그것이 이 항목의 답이다."""
        s = portal.summary()
        self.assertLess(s["twistShare"], 0.3)
        self.assertGreater(s["B"]["addedKg"], s["A"]["addedKg"])
        self.assertFalse(s["braceNeeded"])

    def test_opening_the_beam_flips_the_answer(self):
        """J 를 두 자릿수 낮추면 결론이 따라 뒤집혀야 한다 — 안 뒤집히면 모형이 둔한 것이다."""
        s = portal.summary()
        self.assertGreater(s["Aopen"]["worstTwistDeg"],
                           s["A"]["worstTwistDeg"] * 100)
        self.assertFalse(s["Aopen"]["ok"])
        self.assertTrue(s["Bopen"]["ok"])
        self.assertTrue(s["closingMatters"])

    def test_the_twist_is_most_of_the_sag(self):
        """편심 처짐의 대부분이 비틀림에서 온다 — 굽힘이면 가새가 무의미했을 것이다."""
        a = portal.analyse()
        twist_part = math.radians(a["worstTwistDeg"]) * portal.eccentricity_mm()
        self.assertGreater(twist_part / a["worstSagMm"], 0.5)

    def test_the_brace_only_works_in_the_vertical_plane(self):
        """수평 가새는 보 축 모멘트를 못 받는다 — 그 사실이 상수 옆에 적혀 있어야 한다."""
        import inspect
        src = inspect.getsource(portal)
        i = src.find("BRACE_ANCHOR_Y_MM = ")
        note = src[max(0, i - 500):i]
        self.assertIn("수직면", note)
        self.assertIn("수평 가새", note)

    def test_the_brace_has_to_thread_past_the_ring(self):
        """가새가 링을 뚫으면 안이 아니다 — 기하로 확인한다."""
        self.assertTrue(portal.brace_clears_the_ring())
        self.assertGreater(portal.brace_clearance_mm(), portal.BRACE_CLEARANCE_MM)
        self.assertLess(portal.brace_clearance_mm(), 200.0,
                        "여유가 크면 이 검사가 아무것도 안 잡는다")

    def test_the_brace_stands_above_the_forklift(self):
        """가새 밑단이 헤드가드보다 낮으면 팔레트가 못 들어온다."""
        self.assertGreater(portal.BRACE_ANCHOR_Y_MM,
                           kinematics.FORKLIFT_GUARD_TOP_MM)

    def test_every_check_passes_today(self):
        for name, ok, why in portal.checks():
            with self.subTest(check=name):
                self.assertTrue(ok, f"{name} — {why}")


class TestItSaysWhatItCannotSee(unittest.TestCase):
    def test_the_annotations_admit_the_blind_spots(self):
        text = " ".join(portal.annotations())
        for token in ("접합부", "볼트", "앵커", "OI-04"):
            self.assertIn(token, text, f"주석에 {token} 이 없다")

    def test_the_annotations_say_the_beam_was_chosen_here(self):
        text = " ".join(portal.annotations())
        self.assertIn("부품표에서 온 것이 아니다", text)

    def test_the_annotations_carry_the_numbers(self):
        s = portal.summary()
        text = " ".join(portal.annotations())
        for value in (f"{s['A']['worstSagMm']}", f"{s['Aopen']['worstTwistDeg']}",
                      f"{s['missingDropMm']:.0f}"):
            self.assertIn(value, text, f"주석에 {value} 가 없다")


class TestItIsRegistered(unittest.TestCase):
    def test_the_open_item_carries_the_answer(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-04")
        text = item.title + item.why_open + item.closes_with + item.blocks
        for token in ("portal.py", "받침보", "닫힌"):
            self.assertIn(token, text, f"OI-04 에 {token} 이 없다")

    def test_the_open_item_numbers_are_the_ones_the_module_computes(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-04")
        s = portal.summary()
        for value in (f"{s['A']['worstSagMm']}", f"{s['Aopen']['worstSagMm']}",
                      f"{s['missingDropMm']:.0f}", f"{s['A']['peakMpa']}"):
            self.assertIn(value, item.why_open,
                          f"OI-04 이 {value} 를 안 들고 있다 — 해석과 갈라졌다")

    def test_the_open_item_carries_no_markdown(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-04")
        for field in (item.title, item.why_open, item.closes_with, item.blocks):
            self.assertNotIn("**", field)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
