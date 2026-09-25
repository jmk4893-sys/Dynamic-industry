"""에어록 — 이 장의 결론은 숫자가 아니라 **무엇이 지배하는가**이다.

열수지는 "격리실 부피가 정한다" 고 적었고 그것이 RHB2 를 낳았다. 그 문장이
틀렸다는 것이 이 검토의 전부이므로, 결론이 무너지는 방식도 그 문장으로
되돌아가는 세 가지다.

  ① **지배량이 부피로 되돌아간다** — 손실이 개구 높이의 1.5 제곱과 문
     열림 시간에 비례하지 않으면 이 장은 아무것도 말하지 않는다.
  ② **같은 열을 다시 두 번 센다** — 내문 교환 + 외문 교환은 같은 줄이다.
     되돌아가면 값이 1.35 배로 부풀고, 그 방향은 안전측이라 **아무도
     눈치채지 못한다.** 그래서 시험이 지킨다.
  ③ **카탈로그와 갈라진다** — 셔터 판·행정·수량이 해석과 따로 놀면 도면은
     또 전고 개구로 돌아간다. 실제로 실린더(행정 900)와 판(4,090)이 서로를
     부정한 채로 오래 있었다.
"""

import math
import unittest

from . import _path  # noqa: F401

import airlock as AIR
import parts as PT
from console_consts import const as c


class TestTheSolverMatchesClosedForms(unittest.TestCase):
    def test_every_validation_case_is_within_tolerance(self):
        for name, got, want, err in AIR.validate():
            with self.subTest(name):
                self.assertLess(err, 1e-3, f"{name}: {got} vs {want}")

    def test_the_one_third_coefficient_comes_from_the_integral(self):
        """계수 1/3 은 외운 값이 아니라 중립면 적분의 결과다."""
        h = 1.7
        closed = AIR.exchange_flow(h)
        quad = AIR._flow_quad(h)
        self.assertAlmostEqual(closed / quad, 1.0, places=5)

    def test_the_neutral_plane_sits_at_mid_height(self):
        """가정하지 않고 유량 균형으로 풀어도 개구 중앙이어야 한다."""
        for h in (0.35, 1.2, 4.09):
            with self.subTest(h=h):
                self.assertAlmostEqual(AIR._neutral_plane(h) / h, 0.5, places=6)

    def test_the_ideal_gas_identity_holds(self):
        """ρ = 353/T 이면 Δρ/ρ̄ = ΔT/T̄ 가 **정확히** 성립한다."""
        tbar = (AIR.T_HOT + AIR.T_AMB) / 2 + 273.15
        self.assertAlmostEqual(AIR._buoyancy(),
                               AIR.G * (AIR.T_HOT - AIR.T_AMB) / tbar, places=12)


class TestWhatGovernsTheTerm(unittest.TestCase):
    def test_loss_scales_with_height_to_the_three_halves(self):
        t = AIR.open_time(AIR.OPEN_H)
        for k in (1.5, 2.0, 3.0):
            with self.subTest(k=k):
                r = (AIR.loss_kw(k * AIR.OPEN_H, t_open=t)
                     / AIR.loss_kw(AIR.OPEN_H, t_open=t))
                self.assertAlmostEqual(r, k ** 1.5, places=9)

    def test_loss_is_linear_in_open_time(self):
        t = AIR.open_time(AIR.OPEN_H)
        r = (AIR.loss_kw(AIR.OPEN_H, t_open=3 * t)
             / AIR.loss_kw(AIR.OPEN_H, t_open=t))
        self.assertAlmostEqual(r, 3.0, places=9)

    def test_a_vestibule_only_helps_once_it_actually_binds(self):
        """격리실은 교환량이 그 방을 넘칠 때만 듣는다.

        확정 개구에서는 안 넘치므로 **아끼는 것이 0 이다.** 개구를 전고로
        되돌리면 그때는 듣는다 — 그 대비가 이 장의 논지다.
        """
        v = AIR.vestibule(AIR.OPEN_H)
        self.assertAlmostEqual(AIR.loss_kw(AIR.OPEN_H, vest=v),
                               AIR.loss_kw(AIR.OPEN_H), places=12)
        big = AIR.vestibule(AIR.FULL_H)
        self.assertLess(AIR.loss_kw(AIR.FULL_H, vest=big),
                        AIR.loss_kw(AIR.FULL_H))

    def test_exchange_is_the_smallest_of_the_three_caps(self):
        h, t = AIR.OPEN_H, AIR.open_time()
        q = AIR.exchange_flow(h)
        self.assertAlmostEqual(AIR.exchanged(h, t, None), q * t, places=12)
        self.assertAlmostEqual(AIR.exchanged(h, t, vest=1e-6), 1e-6, places=12)
        self.assertAlmostEqual(AIR.exchanged(h, 1e-6, None), q * 1e-6, places=12)


class TestTheDoubleCountStaysFixed(unittest.TestCase):
    """되돌아가면 값이 부풀고, 그 방향이 안전측이라 아무도 안 본다."""

    def test_only_one_delta_t_leaves_the_system(self):
        v, t = 2.0, 7.0
        h = 9.9                                  # 부피 상한이 걸리도록 큰 개구
        got = AIR.loss_kw(h, t_open=t, vest=v, n_door=1)
        want = (v * AIR.RHO_AIR(AIR.T_AMB) * AIR.CP_AIR
                * (AIR.T_HOT - AIR.T_AMB) / AIR.TAKT / 1000.0)
        self.assertAlmostEqual(got, want, places=12)

    def test_the_two_step_simulation_refuses_the_naive_sum(self):
        """시뮬레이션이 닫힌해와 맞고, 옛 합산은 그보다 크다."""
        v = 2.0
        real, naive = AIR._mix_cycle(v)
        want = v * AIR.RHO_AIR(AIR.T_AMB) * AIR.CP_AIR * (AIR.T_HOT - AIR.T_AMB)
        self.assertAlmostEqual(real / want, 1.0, places=9)
        self.assertGreater(naive, real * 1.2,
                           "옛 합산이 크지 않으면 이 시험이 지키는 것이 없다")


class TestTheCatalogueAgrees(unittest.TestCase):
    def test_the_shutter_catalogue_matches_the_analysis(self):
        self.assertAlmostEqual(PT.SHUT_STROKE / 1000.0, AIR.stroke(), places=9)
        self.assertAlmostEqual(PT.SHUT_PLATE_H / 1000.0,
                               AIR.shutters()["plate_h"], places=9)
        self.assertEqual(PT.SHUTTERS, AIR.shutters()["n"])
        self.assertAlmostEqual(PT.SHUT_OPEN_H / 1000.0, AIR.OPEN_H, places=9)

    def test_every_shutter_part_carries_the_deck_count(self):
        """단별 셔터는 단수를 따라와야 한다 — 상수로 박으면 단수가 바뀔 때 갈라진다."""
        want = int(c("DECKS")) * 2
        for pid, mult in (("P-002-20", 1), ("P-002-22", 1), ("P-002-21", 4)):
            with self.subTest(pid):
                q = [p for p in PT.P if p.pid == pid][0]
                self.assertEqual(q.qty, want * mult)

    def test_the_cylinder_stroke_clears_the_opening(self):
        """행정이 개구보다 짧으면 문이 안 열린다 — 종전 카탈로그가 그랬다."""
        self.assertGreaterEqual(PT.SHUT_STROKE, PT.SHUT_OPEN_H)
        self.assertGreaterEqual(PT.SHUT_PLATE_H, PT.SHUT_OPEN_H)

    def test_splitting_the_shutter_did_not_add_steel(self):
        sh = AIR.shutters()
        self.assertLess(sh["mass"], sh["mass_old"])
        self.assertGreater(sh["perim"], sh["perim_old"],
                           "씰 둘레는 늘어야 한다 — 그 대가를 안 적으면 거짓말이다")


class TestTheOpeningIsNotSmallerThanWhatPasses(unittest.TestCase):
    def test_the_opening_clears_the_pass_envelope(self):
        self.assertGreater(AIR.OPEN_H, AIR.PASS_H)
        self.assertLess(AIR.OPEN_H, c("CDECK_DZ"),
                        "개구가 단 피치를 넘으면 이웃 단이 함께 열린다")

    def test_the_pass_envelope_is_built_from_parts_not_typed(self):
        self.assertAlmostEqual(
            AIR.PASS_H,
            AIR.FORK_T + AIR.PANEL_T + AIR.SET_DROP + 2 * AIR.OPEN_CLR,
            places=12)

    def test_a_vestibule_must_hold_the_whole_panel(self):
        """격리실 깊이를 문 포켓(0.30 m)으로 잡은 것이 옛 오류였다."""
        self.assertGreater(AIR.VEST_D, c("PANEL_L"))
        self.assertGreater(AIR.VEST_D, c("CL_DOOR") * 5)


class TestTheConclusionSurvives(unittest.TestCase):
    def setUp(self):
        self.rs, self.ex = AIR.run()
        self.by = {r.id: r for r in self.rs}

    def test_only_the_current_drawing_exceeds(self):
        over = [r.id for r in self.rs if not r.ok]
        self.assertEqual(over, ["AL1"],
                         "초과가 AL1 뿐이 아니면 확정안이 성립하지 않는다")

    def test_the_full_height_opening_exceeds_the_installed_rating(self):
        """이것이 이 장의 논지다 — 넘지 않으면 쓸 이유가 없다."""
        self.assertGreater(self.by["AL1"].value, AIR.RATED_KW)

    def test_the_chosen_option_leaves_room(self):
        self.assertLess(self.by["AL3"].util, 0.6)

    def test_the_deck_pitch_opening_is_not_good_enough(self):
        """단 피치로만 줄여도 모자란다 — 그래서 포락선까지 간다."""
        o = self.ex["opts"]
        self.assertGreater(o["B"]["kw"], o["C"]["kw"] * 2)
        self.assertGreater(o["B"]["kw"] / self.ex["allow"], 0.8)

    def test_the_governing_sentence_lives_in_the_model(self):
        """산문만 지키면 산문을 지워도 통과한다 — 모델 주기에서 지킨다."""
        text = " ".join([AIR.__doc__ or "", AIR.exchanged.__doc__ or "",
                         AIR.loss_kw.__doc__ or ""])
        for phrase in ("1.5 제곱", "격리실", "두 번"):
            with self.subTest(phrase):
                self.assertIn(phrase, text)

    def test_every_requirement_names_who_receives_it(self):
        for q in AIR.requirements():
            with self.subTest(q.id):
                self.assertTrue(q.owner.strip())
                self.assertTrue(q.why.strip())
                self.assertTrue(q.id.startswith("RAL"))


class TestTheReportIsPrintable(unittest.TestCase):
    def test_the_report_runs_and_names_the_answer(self):
        r = AIR.report()
        self.assertIn("AL1", r)
        self.assertIn("RAL1", r)
        self.assertIn("★ 1 항목 초과", r)

    def test_the_report_shows_every_option_and_marks_the_choice(self):
        """네 안을 나란히 안 보이면 '검토하고 안 샀다' 를 증명할 수 없다."""
        r = AIR.report()
        for key in ("A", "B", "C", "D"):
            with self.subTest(key):
                self.assertIn(AIR.options()[
                    "ABCD".index(key)]["name"][:12], r)
        self.assertIn("← 확정", r)
