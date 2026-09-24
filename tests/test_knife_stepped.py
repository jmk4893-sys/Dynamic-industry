"""계단형 핫나이프 — 형상이 콘솔에서 오고, 힘·램프·사이클이 그 형상에서 나오는가.

이 계산이 틀리는 방식은 넷이다:

  ① **형상을 두 곳에서 든다** — 계산기가 300 · 200 · 80 을 손으로 적으면 콘솔의
     KNIFE_* 가 바뀔 때 계산만 옛 칼날을 센다. 전부 콘솔 상수에서 읽어야 한다.
  ② **날이 폭을 다 덮지 못한다** — 계단 이음에서 칼끝이 끊기면 그 줄만 안
     떨어져 층이 찢어진다. 이음마다 겹침이 있어야 하고 전폭에 틈이 없어야 한다.
  ③ **총 추력이 형상을 따라 움직인다** — 박리 저항은 폭당 힘이므로 계단으로
     엇갈려도 합계는 F_PEEL 이다. 겹침 15 는 이미 떼어 간 줄이라 힘을 보태면 안 된다.
  ④ **사이클을 다른 식으로 센다** — 계단 깊이는 탠덤 칼끝 간격의 자리에 들어가야
     한다. 깊이 300 이면 옛 탠덤 사이클과 같아야 한다.
"""

import unittest

from . import _path  # noqa: F401

import cycle as CY
import fab_spec as F
import knife_stepped as KS
from console_consts import const as c


class TestTheGeometryComesFromTheConsole(unittest.TestCase):

    def test_the_owner_sketch_is_the_root_constant(self):
        self.assertAlmostEqual(c("KNIFE_CENTER"), .30, places=9)
        self.assertAlmostEqual(c("KNIFE_STEP_W"), .20, places=9)
        self.assertEqual(int(c("KNIFE_STEPS")), 3)
        self.assertAlmostEqual(c("KNIFE_RISE"), .08, places=9)      # 발주자 확정 9/24

    def test_width_and_depth_are_derived_not_typed(self):
        self.assertAlmostEqual(KS.KNIFE_W, KS.CENTER + 2 * KS.STEPS * KS.STEP_W, places=6)
        self.assertAlmostEqual(KS.KNIFE_W, 1500, places=6)
        self.assertAlmostEqual(KS.DEPTH, KS.STEPS * KS.RISE, places=6)
        self.assertAlmostEqual(KS.DEPTH, 240, places=6)
        self.assertEqual(KS.BLADES, 7)

    def test_the_cassette_length_is_the_blade_sum(self):
        """카세트 질량·표면적은 일곱 홀더 길이 합에서 나온다 — 전폭이 아니다."""
        self.assertAlmostEqual(KS.BLADE_L_SUM, sum(s["length"] for s in KS.segments()), places=6)
        self.assertAlmostEqual(KS.BLADE_L_SUM, 1590, places=6)


class TestTheBladesCoverTheWidth(unittest.TestCase):

    def test_there_is_no_gap_across_the_knife(self):
        self.assertEqual(KS.coverage_gaps(), [])

    def test_every_joint_overlaps_by_the_lap(self):
        seg = KS.segments()
        for s in seg[1:]:
            inner = max((t for t in seg if t["k"] == s["k"] - 1 and t["side"] in (0, s["side"])),
                        key=lambda t: t["k"])
            if s["side"] > 0:
                self.assertAlmostEqual(inner["y1"] - s["y0"], KS.LAP, places=6)
            else:
                self.assertAlmostEqual(s["y1"] - inner["y0"], KS.LAP, places=6)

    def test_the_outer_blade_clears_the_panel_edge(self):
        self.assertAlmostEqual(KS.summary()["margin"], 50, places=6)
        self.assertGreater(KS.KNIFE_W / 2, KS.PANEL_HALF)

    def test_heat_growth_does_not_eat_the_lap(self):
        """200 ℃ 에서 조각이 늘어나도 겹침이 한참 남는다 — 이음이 벌어질 일이 없다."""
        self.assertLess(KS.summary()["growth_max"], KS.LAP / 10)


class TestTheThrustIsSharedByWidth(unittest.TestCase):

    def test_blade_forces_sum_to_the_console_thrust(self):
        self.assertAlmostEqual(KS.summary()["total"], c("F_PEEL"), places=9)

    def test_the_lap_carries_no_extra_force(self):
        self.assertAlmostEqual(sum(s["engaged"] for s in KS.segments()), KS.PANEL_W, places=6)

    def test_the_centre_blade_bites_alone_first(self):
        s = KS.summary()
        self.assertAlmostEqual(s["center_R"], KS.F_W * KS.CENTER / 1000, places=9)
        self.assertAlmostEqual(s["center_R"], 3.34, places=2)
        self.assertAlmostEqual(s["center_R_design"], s["center_R"] * F.PSI_DYN * F.GAMMA_Q, places=9)

    def test_the_outermost_blade_only_bites_inside_the_panel(self):
        self.assertAlmostEqual(KS.summary()["outer_R"], KS.F_W * 150 / 1000, places=9)


class TestTheBiteComesInFourSteps(unittest.TestCase):

    def test_the_engaged_width_grows_one_step_per_rise(self):
        self.assertEqual([round(w) for w in KS.summary()["ramp_widths"]], [300, 700, 1100, 1400])

    def test_the_ramp_takes_the_depth_at_peel_speed(self):
        self.assertAlmostEqual(KS.summary()["ramp_time"], KS.DEPTH / CY.DEFAULT["knifeSpeed"], places=9)

    def test_each_step_adds_no_more_than_the_centre(self):
        """물림 충격이 한 단 몫씩 온다 — 어느 한 단도 전폭의 1/3 을 넘지 않는다."""
        for r in KS.ramp():
            self.assertLessEqual(r["added"], c("F_PEEL") / 3 + 1e-9)


class TestTheCycleUsesTheDepth(unittest.TestCase):

    def test_the_depth_sits_where_the_tandem_pitch_was(self):
        self.assertAlmostEqual(KS.cycle()["cycle"], CY.TAKT, places=9)
        self.assertAlmostEqual(KS.cycle()["lead"], 240 / 55, places=9)

    def test_depth_300_is_the_old_tandem(self):
        """칼끝 간격 300 의 탠덤이 쓰던 사이클 55.41 s 로 돌아간다."""
        self.assertAlmostEqual(CY.model(knife_depth=300)["knifeLineCycle"], 55.4091, places=3)

    def test_the_contract_leaves_room_above_the_chosen_rise(self):
        s = KS.summary()
        self.assertGreater(s["max_rise"], KS.RISE)
        self.assertAlmostEqual(s["max_rise"], 108.3, delta=0.2)
        self.assertGreaterEqual(s["net"], CY.NET_TARGET)
        self.assertLess(KS.cycle(s["max_rise"] + 1)["net"], CY.NET_TARGET)


if __name__ == "__main__":
    unittest.main()
