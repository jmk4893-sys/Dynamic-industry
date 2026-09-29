"""GBR-301 수치해석 — 유한요소·정적피로·하이브리드 안착, 그리고 물리 화면.

`gbr_load.py` 는 이 셀에 시간을 줬다. 여기서는 **연속체**를 준다 — 콤포크가 얼마나
휘고, 유리가 어디에 얹히고, 놓는 순간 무엇을 받는지.

검증은 정해가 있는 것으로만 한다.

* 격자를 4 배 조밀하게 해도 답이 안 바뀔 것 (수렴)
* 축약 1 자유도의 계단하중 정해와 유한요소 과도가 만날 것
* 정적피로 관계가 지수 −1/16 을 그대로 따를 것
* 브라우저 사슬(다른 구현)과 파이썬 Hermite 요소가 같은 처짐을 낼 것
  — 이것은 글자로 못 보므로 `node tools/check_gbr_physics.mjs` 가 잰다

그리고 **드러난 것 셋**을 기록한다. 선반이 유리를 안 물던 것, 12 mm 소하강이
포크를 못 놓던 것, 접힌 콤포크가 셔틀 데크를 지나가는 것. 앞의 둘은 고쳤고
마지막 하나는 배치가 정할 일이라 숫자만 남긴다.
"""

from __future__ import annotations

import importlib.util
import math
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, beam, gbr_dynamics as gd, gbr_load as gl, handoff

ROOT = pathlib.Path(__file__).resolve().parents[1]
PHYSICS = ROOT / "docs/drawings/pv-gbr-physics.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestForkTelescope(unittest.TestCase):
    """TF-810 — 2 단 텔레스코픽을 다물체로 푼다."""

    def test_the_free_span_is_the_overlap_not_the_whole_reach(self):
        """실제 외팔은 겹침 앞쪽뿐이다 — 여기를 전장으로 보면 처짐이 세 배 나온다."""
        fork = gd.fork_static()
        self.assertEqual(fork.free_mm, gl.fork_stage_travel_mm())
        self.assertLess(fork.free_mm, gl.fork_free_length_mm())

    def test_the_mesh_has_converged(self):
        """격자를 4 배 조밀하게 해도 처짐이 1 % 안에서 같아야 한다."""
        coarse = gd.fork_static()
        inner, base = gd.FORK_INNER_ELEMENTS, gd.FORK_BASE_ELEMENTS
        try:
            gd.FORK_INNER_ELEMENTS, gd.FORK_BASE_ELEMENTS = inner * 2, base * 2
            gd.fork_static.cache_clear()
            fine = gd.fork_static()
        finally:
            gd.FORK_INNER_ELEMENTS, gd.FORK_BASE_ELEMENTS = inner, base
            gd.fork_static.cache_clear()
        self.assertAlmostEqual(coarse.droop_mm, fine.droop_mm,
                               delta=0.01 * fine.droop_mm)

    def test_the_droop_fits_inside_the_approach(self):
        """처짐이 진입 높이를 넘으면 넣는 길에 유리가 목표 레일을 긁는다."""
        self.assertTrue(gd.fork_droop_ok())
        self.assertLess(gd.fork_droop_mm(), gd.fork_droop_budget_mm())

    def test_the_conclusion_does_not_hang_on_the_planned_wall(self):
        """살두께는 계획값이다 — 3…10 mm 전 구간에서 예산 안이어야 결론이 선다."""
        for wall, droop, stress in gd.fork_wall_sweep():
            with self.subTest(wall=wall):
                self.assertLess(droop, gd.fork_droop_budget_mm())
                self.assertLess(stress, 0.5 * gd.frames.YIELD_MPA)

    def test_the_slot_pitch_sets_the_fork_depth(self):
        """GA 의 95 는 슬롯 피치에 안 들어간다 — 창이 깊이를 정한다."""
        room = gd.fork_depth_room_mm()
        self.assertLess(room, 95.0, "95 가 들어갔다면 이 해석이 필요 없었다")
        lo, hi = gd.fork_depth_window_mm()
        self.assertLessEqual(lo, gl.FORK_H_MM)
        self.assertLessEqual(gl.FORK_H_MM, hi)
        self.assertTrue(gd.fork_depth_ok())
        depth, allowed = gd.fork_fits_the_pitch()
        self.assertLessEqual(depth, allowed)

    def test_a_deeper_fork_is_rejected(self):
        """창이 실제로 무언가를 거르는가 — GA 의 95 를 넣어 본다."""
        deep = gd.fork_static(depth_mm=LEGACY_DEPTH_MM)
        self.assertGreater(LEGACY_DEPTH_MM + deep.droop_mm,
                           gd.fork_depth_room_mm())


#: GA 시트가 적었던 콤포크 깊이 (mm) — 슬롯 피치보다 크다.
LEGACY_DEPTH_MM = 95.0


class TestGlassOnTheShelf(unittest.TestCase):
    """무프레임 유리 — 띠 보로 풀고 정적피로로 읽는다."""

    def test_the_old_rails_never_touched_the_glass(self):
        """z ±702.5…757.5 는 유리(±700) 밖이다 — 하중 경로가 통째로 비어 있었다."""
        legacy_inner = 730.0 - 55.0 / 2
        self.assertGreater(legacy_inner, gl.GLASS_W_MM / 2,
                           "종전 레일이 유리 안이었다면 이 해석이 필요 없었다")
        self.assertLess(gl.shelf_edges_mm()[0], gl.GLASS_W_MM / 2)

    def test_the_shelf_reaches_both_the_glass_and_the_post(self):
        inner, outer = gl.shelf_edges_mm()
        self.assertGreaterEqual(gl.GLASS_W_MM / 2 - inner, gl.SHELF_BEARING_MM)
        self.assertGreaterEqual(outer, gl.POST_Z_MM - gl.POST_MM / 2)
        self.assertLessEqual(outer, gl.SKIN_Z_MM - gl.SKIN_T_MM / 2)

    def test_the_fork_clears_the_shelf(self):
        self.assertTrue(gl.fork_offset_ok())
        self.assertLessEqual(gl.FORK_OFFSET_MM + gl.FORK_W_MM / 2,
                             gl.shelf_edges_mm()[0] - gl.MIN_CLEARANCE_MM)

    def test_a_free_strip_has_no_answer(self):
        """지지선이 없으면 처짐이 무한대다 — 강체 적분이 보여 주는 것과 같은 말이다."""
        self.assertEqual(gd.glass_on(())["sag_mm"], float("inf"))

    def test_the_strip_matches_the_closed_form_when_simply_supported(self):
        """정해가 있는 자세로 검증한다 — 단순지지 등분포 5wL⁴/384EI."""
        width = gl.GLASS_W_MM
        bm = beam.Beam(gd.glass_section(), width, gd.GLASS_ELEMENTS)
        pres = {0: 0.0, (bm.n_node - 1) * beam.DOF_PER_NODE: 0.0}
        w = gd.glass_strip_load_n_mm()
        u = bm._solve_with_bc(bm.stiffness(), bm.udl_vector(w), pres)
        exact = 5.0 * w * width ** 4 / (384.0 * bm.section.ei)
        self.assertAlmostEqual(max(abs(v) for v in bm.deflection(u)), exact,
                               delta=1e-3 * exact)

    def test_static_fatigue_follows_the_exponent(self):
        """σ ∝ t^(−1/16) — 기준 3 s 에서 그대로여야 한다."""
        self.assertAlmostEqual(gd.allow_mpa(gd.GLASS_REF_S), afr.GLASS_ALLOW_MPA, 3)
        ratio = gd.allow_mpa(30.0) / gd.allow_mpa(3.0)
        self.assertAlmostEqual(ratio, 10.0 ** (-1.0 / gd.GLASS_FATIGUE_N), 4)
        self.assertLess(gd.allow_mpa(3600.0), afr.GLASS_ALLOW_MPA)
        self.assertGreater(gd.allow_mpa(0.1), afr.GLASS_ALLOW_MPA)

    def test_the_buffer_dwell_is_far_inside_the_fatigue_limit(self):
        """버퍼는 **두는** 자리다 — 단기 허용 30 을 그대로 쓰면 안 된다."""
        self.assertGreater(gd.dwell_limit_s(), gd.max_dwell_s())
        self.assertTrue(gd.glass_keeps_its_strength())

    def test_the_transport_pose_uses_the_short_term_allowable(self):
        self.assertLess(gd.glass_on_fork()["stress_mpa"], afr.GLASS_ALLOW_MPA)


class TestSetDown(unittest.TestCase):
    """소하강 — 강체 하강이 연속체 굽힘으로 넘어가는 자리."""

    def test_twelve_millimetres_does_not_release_the_fork(self):
        """유리가 레일에 닿는 순간 늘어져, 포크 자리는 레일면보다 더 내려간다."""
        self.assertGreater(gd.glass_sag_at_fork_mm(), 0.0)
        self.assertGreater(gd.set_down_required_mm(), gl.SET_DOWN_APPROACH_MM)
        self.assertTrue(gd.set_down_releases_the_fork())
        self.assertGreaterEqual(gl.SET_DOWN_MM, gd.set_down_required_mm())

    def test_the_contact_speed_comes_from_the_servo_tolerance(self):
        expect = math.sqrt(2.0 * gl.SERVO_A_MM_S2 * gl.STOP_TOLERANCE_MM)
        self.assertAlmostEqual(gd.set_down_contact_v_mm_s(), expect, 3)
        self.assertLess(gd.set_down_contact_v_mm_s(), gd._set_down_peak_v_mm_s())

    def test_the_transient_amplifies_but_stays_inside_the_event_allowable(self):
        sd = gd.set_down()
        self.assertGreater(sd.amplification, 1.0)
        self.assertLess(sd.amplification, 2.1)          # 계단하중의 이론 상한
        self.assertTrue(sd.safe)
        self.assertLess(sd.peak_stress_mpa, gd.allow_mpa(gd.SET_DOWN_EVENT_S))

    def test_the_reduced_model_and_the_finite_elements_agree(self):
        """축약 1 자유도의 정해 x_st + √((x₀−x_st)² + (v/ω)²) 와 과도해석이 만난다."""
        v = gd.set_down_verify()
        self.assertLess(v["error"], 0.05)

    def test_a_faster_contact_is_rejected(self):
        """한계 속도가 실제로 무언가를 거르는가."""
        self.assertGreater(gd.set_down_v_limit_mm_s(), gd.set_down_contact_v_mm_s())
        self.assertTrue(gd.set_down_has_margin())
        # 프로파일이 낼 수 있는 최고속으로 닿아도 안 깨진다 — 위치오차와 무관한 상한.
        self.assertTrue(gd.set_down_profile_cannot_break_it())
        fast = gd.set_down(gd.set_down_v_limit_mm_s() * 1.4)
        self.assertFalse(fast.safe, "한계 위에서도 통과하면 한계가 아무것도 안 거른다")


class TestMastAndAccel(unittest.TestCase):
    """ML-811 과 이송 프로파일 — 무엇이 정지 시간을 정하는가."""

    def test_the_mast_is_stiff_enough_that_settling_is_not_the_limit(self):
        """`STOP_SETTLE_S = 0.3` 은 구조가 아니라 **센서** 시간이다."""
        self.assertLess(gd.mast_sway_mm(), gl.STOP_TOLERANCE_MM)
        self.assertEqual(gd.settle_s(), 0.0)
        self.assertTrue(gd.settle_is_not_the_limit())

    def test_the_binding_acceleration_limit_is_friction(self):
        limits = gd.accel_limits_mm_s2()
        self.assertEqual(gd.accel_binding(), min(limits, key=limits.get))
        self.assertGreater(gd.accel_headroom(), 1.0)
        self.assertGreater(min(limits.values()), gl.SERVO_A_MM_S2)


class TestOpenFinding(unittest.TestCase):
    """접힌 콤포크가 셔틀 데크를 지나간다 — 고치지 않고 **적어 둔다.**"""

    def test_low_slots_are_out_of_reach(self):
        reach = gd.reachable_slots()
        self.assertLess(len(reach), handoff.SLOTS_PER_CARRIAGE)
        self.assertEqual(gd.slot_reach_gap(),
                         handoff.SLOTS_PER_CARRIAGE - len(reach))
        self.assertFalse(gd.travel_envelope_is_clear())
        self.assertEqual(reach[-1], handoff.SLOTS_PER_CARRIAGE,
                         "닿는 것은 위쪽 슬롯이다 — 데크가 아래를 막는다")

    def test_every_other_check_passes(self):
        for name, (value, limit, ok) in gd.checks().items():
            if name.startswith("승강 포락선"):
                continue
            with self.subTest(check=name):
                self.assertTrue(ok, f"{name}: {value} / {limit}")


class TestPhysicsPage(unittest.TestCase):
    """물리 화면 — 커밋본이 생성기 출력과 같은가, 수치가 모델에서 왔는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_gbr_physics")
        cls.html = PHYSICS.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-gbr-physics.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python3 tools/build_gbr_physics.py 를 돌리고 커밋한다")

    def test_both_layouts_are_on_the_page(self):
        cases = self.builder.scene()["cases"]
        self.assertEqual([c["name"] for c in cases], ["종전 배치", "채택 배치"])
        legacy, adopted = cases
        self.assertGreater(legacy["shelf"][0], gl.GLASS_W_MM / 2,
                           "종전 선반이 유리 안이면 화면이 아무것도 안 묻는다")
        self.assertLess(adopted["shelf"][0], gl.GLASS_W_MM / 2)

    def test_the_integrator_is_inside_its_stability_limit(self):
        """dt < 2/ω_max — 넘으면 사슬이 발산해 화면이 아무것도 못 묻는다."""
        sc = self.builder.scene()
        h = sc["glassW"] / (sc["nodes"] - 1)
        ei = sc["eMpa"] * sc["glassT"] ** 3 / 12.0
        m_line = sc["areaKgM2"] * 1e-9
        bend = 4.0 * math.sqrt(ei / (m_line * h ** 4))
        contact = math.sqrt(100.0 * ei / h ** 3 / (m_line * h))
        dt = 1.0 / (sc["fps"] * sc["substeps"])
        self.assertLess(dt, 2.0 / max(bend, contact))

    def test_the_shelf_line_lands_on_a_node(self):
        """지지선이 절점 사이에 걸리면 사슬이 받침을 통째로 놓친다."""
        sc = self.builder.scene()
        h = sc["glassW"] / (sc["nodes"] - 1)
        offset = sc["glassW"] / 2 - gl.shelf_edges_mm()[0]
        self.assertAlmostEqual(offset / h, round(offset / h), places=9)

    def test_the_numbers_come_from_the_model(self):
        num = self.builder.numbers()
        self.assertEqual(num["forkDroop"], gd.fork_droop_mm())
        self.assertEqual(num["shelfSag"], gd.glass_on_shelf()["sag_mm"])
        self.assertEqual(num["setDownRequired"], gd.set_down_required_mm())
        self.assertEqual(num["reachable"], len(gd.reachable_slots()))

    def test_the_page_has_no_hand_written_geometry(self):
        """화면에 박힌 숫자는 전부 `__SCENE__`·`__NUM__` 으로 들어간다."""
        self.assertNotIn("__SCENE__", self.html)
        self.assertNotIn("__NUM__", self.html)
        self.assertIn("gbr_dynamics", self.html)


if __name__ == "__main__":
    unittest.main()
