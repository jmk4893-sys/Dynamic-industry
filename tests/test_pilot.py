"""파일럿 시험 계획 — 시료 수 · 재사용 · 닫는 것.

계획서가 실패하는 방식은 정해져 있다:

  ① **시료 수가 근거 없다** — "충분히 반복한다" 는 계획이 아니다.
     요구정밀도에서 거꾸로 풀지 않으면 결과를 못 쓴다.
  ② **매수가 어긋난다** — 로트 표와 시험표를 따로 적으면 갈라진다.
     실제로 그랬다: PT-01 이 50 장을 쓰는데 로트 합이 60 장이고
     PT-03 은 93 장을 요구하는, 아무도 맞춰 본 적 없는 표가 나왔다.
  ③ **닫는 것이 없다** — 무엇을 닫는지 안 적힌 시험은 호기심이다.
  ④ **범위가 무한하다** — 못 하는 것을 안 적으면 "확인했다" 가
     확인하지 않은 것까지 덮는다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import gen_pilot_doc as GEN
import pilot_plan as P

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestSampleSizeIsSolvedNotGuessed(unittest.TestCase):
    """시료 수는 요구정밀도의 함수다 — 상수가 아니다."""

    def test_the_t_approximation_matches_the_table(self):
        """t(0.975, df) 표값. 근사식이 어긋나면 시료 수가 조용히 틀린다."""
        for df, want in ((1, 12.706), (2, 4.303), (5, 2.571), (10, 2.228),
                         (30, 2.042), (120, 1.980)):
            self.assertAlmostEqual(P._t975(df), want, delta=0.03,
                                   msg=f"t(0.975,{df})")

    def test_tighter_precision_needs_more_samples(self):
        a, b = P.n_for_mean(0.20, 0.15), P.n_for_mean(0.20, 0.10)
        self.assertGreater(b, a, "정밀도를 올렸는데 시료가 늘지 않았다")

    def test_more_scatter_needs_more_samples(self):
        self.assertGreater(P.n_for_mean(0.40, 0.15), P.n_for_mean(0.20, 0.15))

    def test_the_sample_size_actually_delivers_the_precision(self):
        """푼 n 이 요구반폭을 만족하고, 하나 적으면 만족하지 않아야 한다."""
        for cv, e in ((0.20, 0.15), (0.20, 0.10), (0.30, 0.20)):
            n = P.n_for_mean(cv, e)
            self.assertLessEqual(P._t975(n - 1) * cv / math.sqrt(n), e)
            self.assertGreater(P._t975(n - 2) * cv / math.sqrt(n - 1), e,
                               f"CV {cv} · E {e} 에서 n 이 하나 크다")

    def test_zero_failure_proportion_uses_the_exact_bound(self):
        """정규근사를 쓰면 실패 0 회에서 하한이 1.0 이 되어 '무한히 좋다' 가 된다.

        Clopper–Pearson 의 닫힌해는 α^(1/n) 이다 — n = 59 에서 처음
        95 % 를 넘는다 (흔히 인용되는 '3의 법칙' 과 같은 자리).
        """
        n = P.n_for_proportion(0.95, 0)
        self.assertEqual(n, 59)
        self.assertGreaterEqual(0.05 ** (1 / n), 0.95)
        self.assertLess(0.05 ** (1 / (n - 1)), 0.95)

    def test_allowing_a_failure_costs_samples(self):
        self.assertGreater(P.n_for_proportion(0.95, 1),
                           P.n_for_proportion(0.95, 0))

    def test_the_binomial_lower_bound_is_monotone(self):
        """같은 실패 수에서 n 이 늘면 하한도 올라야 한다."""
        prev = 0.0
        for n in range(20, 120, 10):
            v = P._cp_lower(1, n)
            self.assertGreater(v, prev, f"n={n} 에서 하한이 내려갔다")
            prev = v


class TestThePanelBudgetReconciles(unittest.TestCase):
    """매수를 두 곳에서 세면 갈라진다 — 한 곳에서만 센다."""

    def setUp(self):
        self.ts = P.tests()
        self.lots = P.lots()

    def test_lot_totals_equal_the_fresh_panel_demand(self):
        self.assertEqual(sum(l.n for l in self.lots),
                         sum(t.n_new for t in self.ts),
                         "로트 합과 신품 소요가 다르다")

    def test_reuse_never_exceeds_the_runs(self):
        for t in self.ts:
            self.assertLessEqual(t.n_new, t.n,
                                 f"{t.id} 신품이 시행보다 많다")
            self.assertGreaterEqual(t.n_new, 0)

    def test_a_test_with_reuse_says_where_it_rides(self):
        for t in self.ts:
            if t.n_new < t.n:
                self.assertGreaterEqual(len(t.reuse), 15,
                                        f"{t.id} 가 무엇에 얹히는지 안 적혔다")

    def test_the_budget_counts_fresh_not_runs(self):
        """시행을 그냥 더하면 두 배가 넘게 나온다 — 그것이 이 표의 요점이다."""
        rows = P.panel_budget()
        self.assertEqual(rows[-1][1], sum(t.n_new for t in self.ts))
        self.assertLess(rows[-1][1], sum(t.n for t in self.ts))

    def test_the_life_test_is_what_sizes_the_pilot(self):
        """파일럿의 크기를 정하는 것은 박리력 곡선이 아니라 칼날 수명이다."""
        by = {t.id: t for t in self.ts}
        phase1 = sum(t.n_new for t in self.ts if t.phase == 1)
        self.assertGreater(by["PT-02"].n_new, phase1,
                           "수명 시험이 1 단계 전체보다 작으면 2 단계를 나눌 이유가 없다")

    def test_the_peel_curve_uses_the_solved_sample_size(self):
        """온도 5 점 × 점당 n. 손으로 적은 수가 아니어야 한다."""
        by = {t.id: t for t in self.ts}
        self.assertEqual(by["PT-01"].n, 5 * P.n_for_mean(0.20, 0.15))

    def test_the_yield_test_uses_the_solved_proportion_size(self):
        by = {t.id: t for t in self.ts}
        self.assertEqual(by["PT-03"].n, P.n_for_proportion(0.95, 1))


class TestEveryTestClosesSomething(unittest.TestCase):
    def setUp(self):
        self.ts = P.tests()

    def test_ids_are_unique_and_sequential(self):
        ids = [t.id for t in self.ts]
        self.assertEqual(ids, [f"PT-{i:02d}" for i in range(1, len(ids) + 1)])

    def test_every_test_names_what_it_closes_and_what_it_feeds(self):
        for t in self.ts:
            self.assertRegex(t.closes, r"(OI-\d+|열해석 [TR]\d+|계약)",
                             f"{t.id} 가 닫는 것이 미결·요구·계약이 아니다")
            self.assertGreaterEqual(len(t.feeds), 20,
                                    f"{t.id} 결과가 어느 상수를 고치는지 없다")
            self.assertGreaterEqual(len(t.accept), 30, f"{t.id} 판정이 짧다")
            self.assertGreaterEqual(len(t.steps), 3, f"{t.id} 절차가 짧다")

    def test_the_thermal_requirements_are_picked_up(self):
        """열해석이 만든 요구 중 파일럿이 받기로 한 것은 실제로 항목이 있어야 한다."""
        import analysis_thermal as TH
        closes = " ".join(t.closes for t in self.ts)
        for q in TH.requirements():
            if "파일럿" in q.owner:
                self.assertIn(q.id, closes,
                              f"{q.id} 을 파일럿이 받기로 했는데 항목이 없다")

    def test_the_open_items_the_plan_claims_are_real(self):
        """사양서에 없는 미결항목을 닫겠다고 쓰면 계획이 허공을 가리킨다."""
        rfq = (ROOT / "docs" / "dg-hk60-rfq.html").read_text(encoding="utf-8")
        real = set(re.findall(r"<b>(OI-\d+)</b>", rfq))
        for t in self.ts:
            for oi in re.findall(r"OI-\d+", t.closes):
                self.assertIn(oi, real, f"{t.id} 이 없는 {oi} 을 닫겠다고 한다")

    def test_the_plan_says_what_it_cannot_answer(self):
        self.assertGreaterEqual(len(P.OUT_OF_SCOPE), 4)
        for what, why in P.OUT_OF_SCOPE:
            self.assertGreaterEqual(len(why), 25, f"{what} — 왜 못 하는지 없다")

    def test_phases_cover_every_test(self):
        got = set()
        for p in P.phases():
            got |= set(p.what.split(" · "))
        self.assertEqual(got, {t.id for t in self.ts}, "단계에서 빠진 시험이 있다")


class TestThePlanDocumentIsGenerated(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "docs" / "dg-hk60-pilot.html").read_text(
            encoding="utf-8")

    def test_the_published_plan_matches_the_generator(self):
        self.assertEqual(self.html, GEN.build(),
                         "계획서가 모델과 다르다 — gen_pilot_doc.py --write")

    def test_every_test_is_printed(self):
        for t in P.tests():
            self.assertIn(f"<b>{t.id}</b>", self.html, f"{t.id} 이 계획서에 없다")

    def test_the_sample_numbers_are_not_hand_typed(self):
        """푼 값이 문서에 있어야 한다 — 정밀도를 바꾸면 문서가 따라온다."""
        for n in (P.n_for_mean(0.20, 0.15), P.n_for_proportion(0.95, 1),
                  sum(l.n for l in P.lots())):
            self.assertIn(f">{n}<", self.html, f"{n} 이 계획서에 없다")

    def test_no_markdown_leaks_into_the_printed_page(self):
        body = re.sub(r"<style>.*?</style>", "", self.html, flags=re.S)
        self.assertNotIn("**", body)


class TestTheSpecimenStateReachesTheDocument(unittest.TestCase):
    """시료의 상태는 계획 모듈에 한 번 적고 문서와 보고서가 그것을 인용한다.

    파일럿은 상류(AFR-101 · JBR-201)가 서기 전에 돌므로, 양산 투입 상태를
    손으로 만들어야 한다. 그 조건이 계획서에 없으면 시료는 프레임을 단 채
    들어오고 1 단계 첫 주가 시료 준비로 사라진다.
    """

    def test_the_document_states_the_input_condition(self):
        html = (ROOT / "docs" / "dg-hk60-pilot.html").read_text(encoding="utf-8")
        self.assertIn(P.SPECIMEN_STATE, html)
        self.assertIn("5 mm 이하로 자르고 눕히지 않는다", html)

    def test_the_report_and_the_budget_carry_it_too(self):
        self.assertIn(P.SPECIMEN_STATE, P.report())
        self.assertIn(P.SPECIMEN_STATE, P.panel_budget()[-1][2])
