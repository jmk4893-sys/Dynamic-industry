"""수치 해석이 **푼 것이 맞는가** — 닫힌 해와 대조한다.

해석기를 손으로 짰으므로 결과를 믿을 근거가 필요하다. 그 근거는 「돌아간다」가
아니라 「답을 아는 문제에서 그 답이 나온다」다. 그래서 시험마다 닫힌 해를 옆에 둔다 —
외팔보 처짐 PL³/3EI, 단순보 1 차 모드, 자유낙하 √(2h/g), Euler 좌굴 π²EI/L².

그리고 해석이 실제로 **드러낸 것**을 붙든다. 소견은 조용히 사라지기 쉽다.
"""

from __future__ import annotations

import math
import pathlib
import unittest

from pv_preprocess import jbr_analysis as ja
from pv_preprocess import jbr_fabrication as jf

PLANT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "drawings" / "pv-preprocess-plant.html"


class TestLinearAlgebra(unittest.TestCase):
    def test_gauss_solves_a_known_system(self):
        a = [[2.0, 1.0, -1.0], [-3.0, -1.0, 2.0], [-2.0, 1.0, 2.0]]
        x = ja.solve(a, [8.0, -11.0, -3.0])
        for got, want in zip(x, (2.0, 3.0, -1.0)):
            self.assertAlmostEqual(got, want, places=9)

    def test_a_singular_system_is_refused_not_guessed(self):
        with self.assertRaises(ValueError):
            ja.solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])

    def test_cholesky_reproduces_the_matrix(self):
        a = [[4.0, 12.0, -16.0], [12.0, 37.0, -43.0], [-16.0, -43.0, 98.0]]
        L = ja.cholesky(a)
        for i in range(3):
            for j in range(3):
                got = sum(L[i][k] * L[j][k] for k in range(3))
                self.assertAlmostEqual(got, a[i][j], places=9)

    def test_jacobi_finds_known_eigenvalues(self):
        vals, _ = ja.jacobi_eigen([[2.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(vals[0], 1.0, places=9)
        self.assertAlmostEqual(vals[1], 3.0, places=9)


class TestFrameAgainstClosedForm(unittest.TestCase):
    """유한요소가 닫힌 해와 맞는가 — 맞아야 브리지 결과를 믿을 수 있다."""

    def test_a_cantilever_matches_pl3_over_3ei(self):
        sec = ja.rhs_section(100.0, 100.0, 6.0)
        L, P = 1_000.0, 5_000.0
        f = ja.Frame(nodes=[(0.0, 0.0), (L, 0.0)],
                     members=[ja.Member(0, 1, sec, "외팔보")],
                     fixed={0: (True, True, True)},
                     loads={1: (0.0, -P, 0.0)})
        got = abs(ja.frame_solve(f)["disp"][3 * 1 + 1])
        exact = P * L ** 3 / (3.0 * ja.E_STEEL * sec["inertia_mm4"])
        self.assertAlmostEqual(got / exact, 1.0, places=6)

    def test_a_simply_supported_beam_matches_pl3_over_48ei(self):
        sec = ja.rhs_section(100.0, 150.0, 8.0)
        L, P = 2_400.0, 8_000.0
        f = ja.Frame(nodes=[(0.0, 0.0), (L / 2, 0.0), (L, 0.0)],
                     members=[ja.Member(0, 1, sec), ja.Member(1, 2, sec)],
                     fixed={0: (True, True, False), 2: (True, True, False)},
                     loads={1: (0.0, -P, 0.0)})
        got = abs(ja.frame_solve(f)["disp"][3 * 1 + 1])
        exact = P * L ** 3 / (48.0 * ja.E_STEEL * sec["inertia_mm4"])
        self.assertAlmostEqual(got / exact, 1.0, places=5)

    def test_a_simply_supported_beam_matches_its_first_mode(self):
        """f₁ = (π/2)·√(EI/mL⁴) — 일관 질량행렬이면 1 % 안에 든다."""
        sec = ja.rhs_section(100.0, 150.0, 8.0)
        L = 2_400.0
        n = 8
        nodes = [(L * i / n, 0.0) for i in range(n + 1)]
        members = [ja.Member(i, i + 1, sec) for i in range(n)]
        f = ja.Frame(nodes=nodes, members=members,
                     fixed={0: (True, True, False), n: (True, True, False)})
        got = ja.frame_modes(f, count=1)[0]["f_hz"]
        mass_per_mm = sec["area_mm2"] * ja.RHO_STEEL          # kg/mm
        exact = (math.pi / 2.0) * math.sqrt(
            ja.E_STEEL * sec["inertia_mm4"] * 1000.0 / (mass_per_mm * L ** 4))
        self.assertAlmostEqual(got / exact, 1.0, places=2)


class TestRainflow(unittest.TestCase):
    def test_the_standard_astm_example_counts_correctly(self):
        """ASTM E1049 3 점 계수 — 반전 수가 보존되는 것이 이 알고리즘의 불변량이다.

        모든 점이 극값인 이력에서 계수 합계는 (N−1)/2 여야 한다. 안쪽 쌍을 하나만
        빼면(흔한 실수) 같은 점이 다시 짝지어져 합계가 넘친다.

        계수된 최대 범위가 전역 진폭(9)이 **아니라** 8 인 것은 옳다. 스택이
        [−3, 5, −4] 일 때 9 는 비교 대상 X 였고, 규칙은 Y(=8)를 세고 −3·5 를
        버린다 — 9 는 그렇게 소비되어 사이클로 남지 않는다.
        """
        series = [0.0, 2.0, -2.0, 1.0, -3.0, 5.0, -1.0, 3.0, -4.0, 4.0, -2.0]
        cycles = ja.rainflow(series)
        self.assertGreater(len(cycles), 0)
        total = sum(n for _r, _m, n in cycles)
        self.assertAlmostEqual(total, (len(series) - 1) / 2.0, places=6)
        self.assertAlmostEqual(max(r for r, _m, _n in cycles), 8.0, places=6)
        self.assertAlmostEqual(sorted(r for r, _m, n in cycles if n == 1.0),
                               [2.0, 3.0, 4.0, 8.0])

    def test_a_flat_series_has_no_cycles(self):
        self.assertEqual(ja.rainflow([3.0, 3.0, 3.0]), [])

    def test_the_sn_curve_has_the_two_slopes_ec3_defines(self):
        fat = ja.FAT_CLASS_MPA
        self.assertAlmostEqual(ja.sn_cycles(fat), 2e6, delta=1.0)
        knee = fat * (2e6 / ja.FAT_KNEE_CYCLES) ** (1 / 3)
        self.assertAlmostEqual(ja.sn_cycles(knee), ja.FAT_KNEE_CYCLES, delta=1e3)
        cut = knee * (ja.FAT_KNEE_CYCLES / ja.FAT_CUTOFF_CYCLES) ** (1 / 5)
        self.assertTrue(math.isinf(ja.sn_cycles(cut * 0.99)))


class TestCylinder(unittest.TestCase):
    def test_the_steady_force_matches_pressure_times_area(self):
        r = ja.cylinder_dynamics(80.0, 10.0, 0.5, 0.1, t_max=3.0)
        exact = 0.5e6 * math.pi / 4 * 0.08 ** 2 / 1000.0
        self.assertAlmostEqual(r["steady_force_kn"], exact, places=6)

    def test_a_cylinder_that_cannot_lift_the_load_never_reaches_stroke(self):
        r = ja.cylinder_dynamics(80.0, 360.0, 0.5, 10.0, t_max=3.0)
        self.assertFalse(r["reached"])
        self.assertIsNone(r["t_stroke_s"])

    def test_filling_takes_time_that_p_times_a_does_not_show(self):
        """정상힘은 부하의 몇 배인데도 행정에 시간이 걸린다 — 그것이 이 해석의 요점."""
        r = ja.cylinder_dynamics(80.0, 360.0, 0.5, 1.0, t_max=3.0)
        self.assertTrue(r["reached"])
        self.assertGreater(r["static_margin"], 2.0)
        self.assertGreater(r["t_stroke_s"], 0.05)


class TestDropReference(unittest.TestCase):
    def test_free_fall_matches_sqrt_2h_over_g(self):
        d = ja.drop_reference(1.075, 0.155)
        self.assertAlmostEqual(d["t_first_s"], math.sqrt(2 * 0.92 / ja.G), places=9)
        self.assertAlmostEqual(d["impact_v_ms"], math.sqrt(2 * ja.G * 0.92), places=9)

    def test_bouncing_settles_in_finite_time_below_unit_restitution(self):
        d = ja.drop_reference(1.0, 0.0, e=0.5)
        self.assertLess(d["t_settle_s"], math.inf)
        self.assertGreater(d["t_settle_s"], d["t_first_s"])


class TestBuckling(unittest.TestCase):
    def test_a_slender_rod_uses_euler_and_matches_it(self):
        r = ja.rod_buckling(20.0, 800.0, 1.0)
        self.assertEqual(r["mode"], "Euler")
        i = math.pi * 20.0 ** 4 / 64.0
        exact = math.pi ** 2 * ja.E_STEEL * i / (2.0 * 800.0) ** 2 / 1000.0
        self.assertAlmostEqual(r["p_cr_kn"], round(exact, 1), places=1)

    def test_a_stocky_rod_switches_to_johnson(self):
        self.assertEqual(ja.rod_buckling(60.0, 200.0, 1.0)["mode"], "Johnson")


class TestMotionMirror(unittest.TestCase):
    """거울이 원본과 어긋나면 해석 전체가 다른 기계를 푼 것이 된다."""

    def test_the_motion_mirror_matches_the_plant(self):
        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
        import build_jbr_closeup as bjc
        mo = bjc.model(PLANT.read_text(encoding="utf-8"))["motion"]
        m = ja.SEQUENCE
        self.assertEqual(m["slot"], mo["slot"])
        self.assertEqual(m["slotFrom"], mo["slotFrom"])
        self.assertEqual(m["sinkZ"], mo["sinkZ"])
        self.assertEqual(list(m["shear"]), list(mo["shear"]))
        self.assertEqual(m["openWide"], mo["openWide"])
        self.assertEqual(m["openShut"], mo["openShut"])
        self.assertEqual(list(m["place"]), list(mo["place"]))
        self.assertEqual(list(m["boxLift"]), list(mo["boxLift"]))
        self.assertEqual(list(m["boxSlide"]), list(mo["boxSlide"]))
        self.assertEqual(list(m["sinkY"]), list(mo["sinkY"]))
        self.assertEqual(m["discharge"]["highY"], mo["discharge"]["highY"])
        self.assertEqual(m["discharge"]["restY"], mo["discharge"]["restY"])


class TestWhatTheAnalysisFound(unittest.TestCase):
    """해석이 드러낸 것 — 조용히 지워지지 않게 붙든다."""

    def test_the_first_mode_is_sway_not_bending(self):
        """**닫힌 해는 모드를 잘못 짚었다.**

        `bridge_mode` 는 브리지를 양단 단순지지 보로 놓았다 — 지점이 안 움직인다는
        뜻이다. 실제로는 기둥이 있고, 1 차는 굽힘이 아니라 프레임 흔들림이다.
        굽힘 모드(2 차)는 닫힌 해와 잘 맞는다 — 그래서 이것은 요소가 틀린 것이
        아니라 **모델이 빠뜨린 것**이다.
        """
        m = ja.bridge_modal()
        self.assertEqual(m["f1_kind"], "sway")
        self.assertLess(m["f1_hz"], m["closed_form_hz"])
        bending = next(x for x in m["modes"] if x["kind"] == "bending")
        self.assertAlmostEqual(bending["f_hz"] / m["closed_form_hz"], 1.0, delta=0.15)

    def test_the_closed_form_left_out_the_head_weight(self):
        """박리력이 0 이어도 유한요소 처짐이 닫힌 해보다 크다 — 헤드 자중 때문이다."""
        fea = ja.bridge_fea(0.5, 0.0)["deflection_mm"]
        closed = jf.bridge_mode((100.0, 150.0), 8.0, ja.BRIDGE_SPAN_MM,
                                jf.moving_mass_kg(), jf.X_DECEL_MS2)["deflection_mm"]
        self.assertGreater(fea, closed)

    def test_the_peel_reaction_passes_through_the_bridge(self):
        """닫힌 고리라 앵커로는 안 새지만, 그 고리가 브리지를 지난다."""
        self.assertTrue(jf.FORCE_LOOP_CLOSES_INSIDE)
        self.assertGreater(ja.bridge_fea(0.5, 5.0)["deflection_mm"],
                           2.0 * ja.bridge_fea(0.5, 0.0)["deflection_mm"])

    def test_the_sequential_motion_law_asks_for_accelerations_no_axis_can_give(self):
        """**가장 무거운 소견.** 순차 운동식의 이송 구간이 전부 축 한계를 넘는다.

        3D 는 시각을 주면 자세를 돌려주는 보간이라 10 g 짜리 이송도 부드럽게
        재생된다. 화면이 말이 되는 것과 기계가 되는 것은 다르다.
        """
        t = ja.traverse_check()
        self.assertFalse(t["feasible"])
        self.assertEqual(t["failing"], t["total"])
        self.assertGreater(t["worst_g"], 5.0)

    def test_the_four_second_slot_does_not_hold_the_sequence(self):
        """축 한계를 지키면 칸이 4.0 s 로 안 끝난다 — 얼마나 모자라는지 적어 둔다."""
        b = ja.slot_budget()
        self.assertFalse(b["fits"])
        self.assertGreater(b["need_s"], b["slot_now_s"])
        self.assertEqual(b["slot_now_s"], ja.SEQUENCE["slot"])

    def test_fatigue_is_infinite_below_the_cutoff_and_finite_at_the_trip_force(self):
        """작업력을 모르는 것이 왜 급한지 — 수명이 무한과 유한 사이에서 갈린다."""
        self.assertTrue(ja.fatigue_life(2.0)["infinite_life"])
        self.assertTrue(ja.fatigue_life(5.0)["infinite_life"])
        trip = ja.fatigue_life(jf.JAM_TRIP_KN)
        self.assertFalse(trip["infinite_life"])
        self.assertLess(trip["years"], 60.0)

    def test_the_bore80_cylinder_only_works_below_its_steady_force(self):
        """Ø80·0.5 MPa 는 2.5 kN 이다. 그보다 큰 작업력에서는 행정을 못 낸다."""
        self.assertTrue(ja.peel_dynamics(2.0)["fits"])
        self.assertFalse(ja.peel_dynamics(5.0)["fits"])

    def test_three_boxes_fanned_at_the_design_pitch_overflow_the_narrowed_bin(self):
        """**수거함을 1,320 → 640 으로 줄인 대가가 여기서 나온다.**

        설계는 호퍼 안에서 박스를 z 로 180 mm 씩 벌려 눕힌다. 세 개가 차지하는 폭은
        180×2 + 박스 깊이라 수거함 안폭 540 을 넘는다. 물리 시뮬레이션에서 바깥
        두 개가 테두리를 물었고, 그 원인이 이 산술이다.
        """
        fan, inner = 0.18, 0.54
        depths = (0.21, 0.22, 0.21)
        zs = [(i - 1) * fan for i in range(3)]
        span = max(z + d / 2 for z, d in zip(zs, depths)) \
            - min(z - d / 2 for z, d in zip(zs, depths))
        self.assertGreater(span, inner)
        self.assertAlmostEqual((span - inner) * 1000.0, 30.0, places=6)

    def test_the_vacuum_cups_hold_once_the_motion_is_feasible(self):
        """진공은 문제가 아니다 — 지금 모자란 것은 운동식이 6.9 g 를 부르기 때문이다."""
        self.assertFalse(ja.vacuum_hold()["ok"])
        self.assertTrue(ja.vacuum_hold(accel_ms2=ja.AXIS_ACCEL_LIMIT_MS2)["ok"])


if __name__ == "__main__":
    unittest.main()
