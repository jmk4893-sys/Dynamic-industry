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

from pv_preprocess import campaign
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

    def test_the_motion_law_now_stays_inside_what_the_axis_can_give(self):
        """**소견이 닫혔다 — 칸을 4.0 → 7.0 s 로 늘려서다.**

        REV.57 까지 이 시험은 반대를 붙들고 있었다: 이송 6 구간이 전부 축 한계를
        넘고 최악이 10.0 g 였다. 3D 가 보간이라 그 가속도로도 부드럽게 재생됐고,
        그래서 아무도 못 봤다.

        고친 방법은 구동을 키우는 것이 아니라 **시간을 준 것**이다. 축을 4 배로
        올려도(10 m/s²) 점 호퍼 구성은 병목을 못 피했다 — 왕복 거리 자체가
        문제였기 때문이다. 되돌려 칸을 줄이면 여기가 먼저 깨진다.
        """
        t = ja.traverse_check()
        self.assertTrue(t["feasible"], f"{t['failing']}/{t['total']} 구간 초과")
        self.assertEqual(t["failing"], 0)
        self.assertLessEqual(t["worst_over"], 1.0)

    def test_the_slot_holds_the_sequence_with_no_room_to_spare(self):
        """칸 7.0 s 가 필요분 6.96 s 를 겨우 담는다 — 여유가 0.04 s 다.

        이 여백이 얼마나 얇은지가 이 시험의 요점이다. 박스가 조금만 더 멀리
        있어도(시나리오가 바뀌어도) 다시 넘친다.
        """
        b = ja.slot_budget()
        self.assertTrue(b["fits"])
        self.assertLessEqual(b["need_s"], b["slot_now_s"])
        self.assertLess(b["slot_now_s"] - b["need_s"], 0.1)
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

    def test_three_boxes_fanned_at_the_design_pitch_fit_the_bin_read_from_the_plant(self):
        """**소견이 뒤집혔다 — 그리고 이 시험이 그것을 못 잡았었다.**

        REV.57 물리 화면은 수거함 안깊이를 손으로 540 이라 적었고, 부채꼴 570 이 그것을
        30 mm 넘어 바깥 두 박스가 테두리를 물었다. REV.59 에서 원본 `part('BIN')`(640)
        에서 읽게 고치자 3/3 이 들어갔다. 그런데 이 시험은 REV.60 까지 `inner = 0.54`
        리터럴을 스스로 들고 「넘는다」를 계속 단언하고 있었다 — 거울이 아니라
        리터럴을 든 시험은 원본이 바뀌어도 초록이다. 이제 물리 화면이 원본에서 낸
        값을 그대로 쓴다.
        """
        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
        import build_jbr_physics as bjp
        sc = bjp.scene()
        fan = bjp.REST_FAN_M
        depths = [b["sz"] for b in sc["boxes"]]
        zs = [(i - 1) * fan for i in range(len(depths))]
        span = max(z + d / 2 for z, d in zip(zs, depths)) \
            - min(z - d / 2 for z, d in zip(zs, depths))
        inner = sc["bin"]["inner"][1]
        self.assertLess(span, inner)
        self.assertAlmostEqual((inner - span) * 1000.0, 67.0, places=6)
        self.assertGreater(inner, 0.54, "540 은 손으로 옮긴 값이었다 — 부품표는 640 이다")

    def test_the_vacuum_cups_hold_now_that_the_motion_is_feasible(self):
        """진공은 애초에 문제가 아니었다 — 운동식이 6.9 g 를 부르던 것이 문제였다.

        칸이 길어지자 요구 가속도가 축 한계 안으로 들어왔고, 같은 컵이 그대로
        여유를 갖는다. 진공을 키워서 푼 것이 아니다.
        """
        v = ja.vacuum_hold()
        self.assertTrue(v["ok"], f"여유 {v['margin']}")
        self.assertGreater(v["margin"], 1.0)
        self.assertLessEqual(v["accel_ms2"], ja.AXIS_ACCEL_LIMIT_MS2 + 1e-9)


class TestWhatTheSecondPassFound(unittest.TestCase):
    """REV.60 — 같은 해석을 현재 판에 다시 걸었더니 나온 것.

    베이스의 OI-05 가 투입 쪽에서 「미는 힘이 아니라 멈추는 힘」을 냈다. 같은 물음을
    이 셀의 실린더 둘에 던졌고, 「비움 주기 미결」은 물리엔진으로 쌓아 숫자로 만들었다.
    """

    def test_the_speed_cap_holds_the_piston(self):
        """미터아웃의 1 차 모형 — 속도를 그 값에서 붙들고, 시간은 행정÷속도 + 시동이다."""
        r = ja.cylinder_dynamics(80.0, 360.0, 0.5, 0.0, v_cap_mms=300.0)
        self.assertAlmostEqual(r["v_peak_mms"], 300.0, places=6)
        self.assertAlmostEqual(r["v_end_mms"], 300.0, places=6)
        self.assertAlmostEqual(r["t_stroke_s"], 360.0 / 300.0, delta=0.05)
        free = ja.cylinder_dynamics(80.0, 360.0, 0.5, 0.0)
        self.assertGreater(free["v_peak_mms"], 3_000.0, "교축 없는 Ø80 은 무부하에서 3 m/s 를 넘는다")

    def test_the_throttle_the_bom_chose_could_not_meet_its_own_window(self):
        """**부품표가 스스로 정한 225 mm/s 는 창이 요구하는 평균값이었다 — 여유 0.**

        REV.59 까지 JB-HD-002 는 「메터아웃 225 mm/s」였고, 해석은 교축을 안 읽고 풀어
        「0.85 s · 여유 0.75 s」라 답했다. 설정을 창이 요구하는 값에 그대로 두면 시동
        지연이 초과분이 되고, 공차 하한 −10 % 에서는 창을 넘는다. 300 ±10 % 는 하한
        270 에서 2 kN 부하로 1.35 s 에 끝나고 끝단 0.54 J 로 쿠션 안이다.
        """
        pt = ja.peel_throttle()
        self.assertAlmostEqual(pt["need_mms"], 225.0, places=6)
        self.assertFalse(pt["fits_at_need"], "창이 요구하는 평균에 설정을 맞추면 하한에서 넘쳐야 한다")
        self.assertGreater(pt["t_at_need_s"], pt["window_s"])
        self.assertEqual(pt["cap_mms"], jf.PEEL_SPEED_MMS)
        self.assertTrue(pt["fits"])
        self.assertGreater(pt["slack_s"], 0.2)
        self.assertTrue(pt["cushion_ok"])
        self.assertLess(pt["ke_end_j"], pt["cushion_j"])
        # 옛 설정 그대로 넣으면 지금도 같은 답이다 — 되돌리면 여기서 걸린다.
        old = ja.peel_dynamics(2.0, speed_cap_mms=225.0)
        self.assertFalse(old["fits"])
        self.assertTrue(old["fits_nominal"] is False or old["t_stroke_s"] > 1.6 - 1e-9)

    def test_the_peel_verdict_is_taken_at_the_slow_end_of_the_tolerance(self):
        d = ja.peel_dynamics(2.0)
        self.assertGreater(d["t_slow_s"], d["t_stroke_s"])
        self.assertAlmostEqual(d["speed_low_mms"], jf.PEEL_SPEED_MMS * (1 - jf.PEEL_SPEED_TOL), places=6)
        self.assertEqual(d["fits"], d["t_slow_s"] <= d["window_s"])

    def test_the_lift_is_limited_by_stopping_not_pushing(self):
        """**힘이 남는다는 답은 맞지만, 남는 힘은 가속이 된다.**

        `lift_check` 이용률 0.59 — 그 여유가 420 행정 끝에 188 kg 을 1 m/s 넘게 밀어
        보낸다. 실린더당 에너지가 표준 쿠션(Ø63 ≈ 2.5 J, 가정)의 수십 배다. 쿠션이
        먹는 속도로 조이면 상승이 창 1.8 s 를 넘고, 업소버면 든다. 손잡이는 힘이 아니라
        행정이나 완충이다 — 상승량이 모델에 없어 여기서 정하지 않는다.
        """
        lb = ja.lift_budget()
        self.assertGreater(lb["free_over_cushion"], 10.0)
        self.assertLess(lb["free_t_s"], lb["window_s"], "힘으로는 창 안이다 — 문제는 힘이 아니다")
        self.assertFalse(lb["fits_cushion"], "쿠션 속도로 조이면 창을 넘어야 한다 — 든다면 소견이 닫힌 것이다")
        self.assertGreater(lb["t_cushion_s"], lb["homing_s"])
        self.assertEqual(lb["binding"], "승강")
        self.assertTrue(lb["fits_shock"])
        self.assertLess(lb["stroke_that_fits_mm"], jf.LIFT_STROKE_MM)
        self.assertTrue(lb["homing_fits"])
        self.assertAlmostEqual(lb["homing_s"], 1.59, places=2)

    def test_the_cushion_assumption_is_shared_with_the_infeed_side(self):
        """같은 가정을 두 벌 두지 않는다 — 저쪽이 카탈로그 값으로 바뀌면 여기도 바뀐다."""
        from pv_preprocess import catch
        self.assertAlmostEqual(ja.cushion_allow_j(40.0), catch.CUSHION_ALLOW_J, places=9)
        self.assertAlmostEqual(ja.cushion_allow_j(80.0), 4.0 * catch.CUSHION_ALLOW_J, places=9)
        self.assertEqual(ja.SHOCK_ABSORBER_J, catch.SHOCK_ABSORBER_J)

    def test_the_bin_fills_in_minutes_not_shifts(self):
        """**「비움 주기 미결」은 미결일 이유가 없었다.**

        명목 90 L 를 완전 충전해도 8.7 장 · 7 분이고, 물리엔진으로 쌓으면 13 장 · 11 분이다.
        스토퍼 해제 조건이 「수거함 정상」이라 찬 수거함은 라인을 세운다 — 시간당
        대여섯 번에서 여덟 번. 어느 자로 재도 손잡이로 인출하는 수거함의 주기가 아니다.
        """
        b = ja.bin_fill()
        self.assertLess(b["dense_minutes"], 10.0)
        self.assertGreater(b["dense_empties_per_h"], 6.0)
        self.assertGreater(b["engine_panels"], 0, "물리엔진 실측이 비어 있다 — node tools/check_jbr_bin.mjs")
        self.assertLess(b["engine_minutes"], 15.0)
        self.assertGreaterEqual(b["engine_panels"], b["dense_panels"], "명목 90 L 는 보수적인 값이어야 한다")
        self.assertLessEqual(b["engine_panels"], b["gross_panels"], "기하 상한을 넘으면 박스가 관통한 것이다")
        self.assertGreater(b["engine_packing"], 0.5)
        self.assertLess(b["engine_packing"], 1.0)

    def test_the_bin_capacity_mirror_matches_the_plant(self):
        import re
        text = PLANT.read_text(encoding="utf-8")
        m = re.search(r'"JB-WH-002".{0,300}?"용량 (\d+) L"', text)
        self.assertIsNotNone(m, "통합 설계도 부품표에서 JB-WH-002 용량을 못 찾았다")
        self.assertEqual(float(m.group(1)), ja.BIN_CAPACITY_L)

    def test_the_bin_inner_mirror_matches_the_physics_scene(self):
        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
        import build_jbr_physics as bjp
        sc = bjp.scene()["bin"]
        self.assertAlmostEqual(ja.BIN_INNER_M[0], sc["inner"][0], places=4)
        self.assertAlmostEqual(ja.BIN_INNER_M[1], sc["inner"][1], places=4)
        self.assertAlmostEqual(ja.BIN_INNER_M[2], sc["wallH"], places=4)

    def test_the_speed_mirror_matches_the_plant(self):
        """부품표 JB-HD-002 의 미터아웃 설정은 통합 설계도 부품표가 원본이다."""
        import re
        text = PLANT.read_text(encoding="utf-8")
        m = re.search(r'"JB-HD-002".{0,300}?"속도 (\d+) mm/s ±(\d+)%"', text)
        self.assertIsNotNone(m, "통합 설계도 부품표에서 JB-HD-002 속도를 못 찾았다")
        self.assertEqual(float(m.group(1)), jf.PEEL_SPEED_MMS)
        self.assertAlmostEqual(float(m.group(2)) / 100.0, jf.PEEL_SPEED_TOL, places=9)
        spec = next(c for c in jf.commercial() if c.tag == "JB-HD-002").spec
        self.assertIn(f"{jf.PEEL_SPEED_MMS:g} mm/s", spec)

    def test_the_homing_window_mirror_matches_the_plant(self):
        import re
        text = PLANT.read_text(encoding="utf-8")
        m = re.search(r'\{name:"헤드 z 원점 복귀·승강 상승[^}]*?start:([\d.]+),end:([\d.]+)\}', text)
        self.assertIsNotNone(m, "스테이지 표에서 원점 복귀·승강 상승 구간을 못 찾았다")
        self.assertAlmostEqual(float(m.group(2)) - float(m.group(1)), ja.HOME_WINDOW_S, places=6)

    def test_fatigue_counts_panels_at_the_campaign_takt(self):
        """48.47 리터럴이 REV.59 의 택트 48.59 위에서 낡아 있었다 — 이제 같이 움직인다."""
        from pv_preprocess import campaign
        takt = campaign.summary()["takt_s"]
        self.assertAlmostEqual(ja.panels_per_year(), 3600.0 / takt * 8_000.0, places=6)
        self.assertEqual(ja.fatigue_life(5.0)["panels_per_year"], ja.panels_per_year())

    def test_vacuum_is_checked_at_the_worst_move(self):
        """가운데 박스 1.5 m/s² 가 아니라 바깥 박스 2.2 m/s² 다 — 최악을 안 보는 검산은 거짓 통과다."""
        v = ja.vacuum_hold()
        worst = ja.traverse_check()["worst"]["a_peak_ms2"]
        self.assertAlmostEqual(v["accel_ms2"], round(worst, 2), places=2)
        self.assertGreater(v["accel_ms2"], 2.0)
        self.assertTrue(v["ok"])


class TestWhatTheThirdPassFound(unittest.TestCase):
    """REV.61 — 밖에서 온 3 헤드 제안을 재면서 나온 것.

    같은 물음이 세 번째 왔다(REV.59 유압 + 3 헤드, REV.61 공통 갠트리 + 간격 서보
    + 보강 크로스빔). 두 번은 손으로 스윕해 답했다. 손으로 재면 재는 사람마다
    답이 달라지므로, 이번에는 **모델이 답하게** 만들고 그 자리를 시험이 지킨다.
    """

    def test_the_prize_for_more_heads_is_less_than_a_tenth_of_a_second(self):
        """**헤드를 늘려 버는 것은 정반 점유 0.08 s 다.**

        JBR 을 0 초로 만들어도 라인은 방출 인터록(투입 40 + 스토퍼 8)과 유리제거셀
        아래로 못 내려간다. 처리량으로는 72.0 → 72.1 장/h 다. 앞단이 빨라져 이
        상금이 1 초를 넘으면 이 시험이 깨지고, 그때는 헤드 증설을 다시 재야 한다.
        """
        p = ja.head_prize()
        self.assertLess(p["headroom_s"], 1.0)
        self.assertFalse(p["worth_more_heads"])
        self.assertLess(p["throughput_gain_per_h"], 1.0)
        self.assertEqual(p["binding"], "방출 인터록 (투입 + 스토퍼)")
        self.assertAlmostEqual(p["takt_floor_s"],
                               campaign.INFEED_S + campaign.JBR_STOPPER_OFFSET_S
                               + campaign.RELEASE_HOLD_S, places=2)

    def test_the_densest_scenario_caps_the_head_count_at_two(self):
        """**헤드 수를 정하는 것은 가장 조밀한 시나리오다.**

        도면이 스스로 「3개 · 조밀 위치」(간격 360)를 들고 있다. 헤드 z 발자국이
        420 이라 그 사이에 셋째가 못 들어간다 — 바깥 둘을 세우면 남는 틈이 300 이다.
        간격 서보를 달아도 안 바뀐다: 서보는 헤드를 옮기지 좁게 만들지 않는다.

        REV.61 까지 이 해석은 `BOX_Z_M`(비대칭, 간격 460) 하나만 보고 있었고,
        그 시나리오만 보면 세 기가 선다.
        """
        fit = ja.head_fit()
        self.assertEqual(fit["usable_heads"], 2)
        self.assertFalse(fit["three_heads_land_everywhere"])
        worst = fit["worst"]
        self.assertEqual(worst["key"], "triple-compact")
        self.assertEqual(worst["boxes"], 3)
        self.assertEqual(worst["heads"], 2)
        self.assertLess(worst["clearance_mm"], 0.0)
        self.assertEqual(worst["sequential_passes"], 2)
        # 기본 시나리오만 보면 셋이 선다 — 그것이 이 소견이 안 보이던 이유다.
        wide = next(r for r in fit["rows"] if r["key"] == "triple-wide")
        self.assertEqual(wide["heads"], 3)
        self.assertGreater(wide["clearance_mm"], 0.0)

    def test_a_spacing_servo_does_not_make_the_head_narrower(self):
        """간격 서보를 어디에 두든 판정은 헤드 폭이 정한다."""
        zs = ja.SCENARIOS["triple-compact"][1]
        self.assertEqual(ja.simultaneous_heads(zs)["heads"], 2)
        # 헤드가 좁아져야만 셋이 선다 — 그것은 서보가 사 주는 것이 아니다.
        self.assertEqual(ja.simultaneous_heads(zs, head_z_mm=340.0)["heads"], 3)

    def test_stiffening_the_bridge_lowers_the_first_mode(self):
        """**「보강 크로스빔」은 정확히 안 도와주는 부재다.**

        1 차가 굽힘이면 단면을 키우는 것이 정답이지만 이 프레임의 1 차는 흔들림이고,
        브리지를 키우면 기둥 위 질량이 늘어 오히려 내려간다. 고칠 곳은 기둥이다.
        """
        sw = ja.stiffening_sweep()
        self.assertEqual(sw["base_kind"], "sway")
        self.assertFalse(sw["stiffening_the_bridge_helps"])
        self.assertTrue(sw["stiffening_the_column_helps"])
        self.assertLess(sw["bridge"][-1]["f_hz"], sw["base_f_hz"])
        self.assertGreater(sw["column"][-1]["f_hz"], 2.0 * sw["base_f_hz"])
        for row in sw["bridge"] + sw["column"]:
            self.assertEqual(row["kind"], "sway", "1 차가 굽힘이 되면 이 표의 뜻이 바뀐다")

    def test_the_lift_now_carries_three_answers_and_picks_none(self):
        """서보가 셋째 답이다 — 창을 가장 넉넉히 지키지만 축이 하나 는다.

        고르는 것은 사람이다. 모델은 셋을 나란히 재 두기만 한다.
        """
        lb = ja.lift_budget()
        self.assertEqual(len(lb["options"]), 3)
        self.assertIn("서보", [name for name, _note in lb["options"]])
        self.assertTrue(lb["fits_servo"])
        self.assertLess(lb["servo_t_s"], lb["t_cushion_s"])
        self.assertFalse(lb["fits_cushion"], "공압 그대로면 여전히 창을 넘는다")
        self.assertIsNone(jf.WORKING_PEEL_KN, "서보 이야기가 작업력을 정해 주지는 않는다")

    def test_the_scenario_mirror_matches_the_plant(self):
        """시나리오 거울은 통합 설계도가 원본이다."""
        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
        import build_jbr_closeup as bjc
        got = {s["key"]: (s["label"], tuple(round(b["z"], 3) for b in s["boxes"]))
               for s in bjc.scenarios(PLANT.read_text(encoding="utf-8"))}
        self.assertEqual(set(got), set(ja.SCENARIOS))
        for key, (label, zs) in ja.SCENARIOS.items():
            self.assertEqual(got[key][0], label, key)
            self.assertEqual(got[key][1], tuple(round(z, 3) for z in zs), key)
        # 기본 시나리오는 거울 안에 있어야 한다 — 두 곳이 갈라지면 안 된다.
        self.assertEqual(tuple(round(z, 3) for z in ja.BOX_Z_M),
                         ja.SCENARIOS["triple-wide"][1])

    def test_the_head_footprint_mirror_matches_the_plant(self):
        """헤드 z 발자국은 부품표가 원본이고, 칼날 개도와 무관하다."""
        import re
        text = PLANT.read_text(encoding="utf-8")
        m = re.search(r"part\('HD-1',[^\[]*\[([\d.]+),\s*([\d.]+),\s*([\d.]+)\]", text)
        self.assertIsNotNone(m, "통합 설계도에서 part('HD-1', …) 을 못 찾았다")
        self.assertEqual(float(m.group(3)), ja.HEAD_Z_MM)
        # 칼날은 x 로 벌어진다 — z 발자국이 개도를 따라가면 이 전제가 깨진다.
        self.assertIn("left.position.x", text)
        self.assertGreater(ja.SEQUENCE["openWide"] * 1000.0, ja.HEAD_Z_MM,
                           "칼날이 z 로 벌어진다면 발자국을 다시 정의해야 한다")


if __name__ == "__main__":
    unittest.main()
