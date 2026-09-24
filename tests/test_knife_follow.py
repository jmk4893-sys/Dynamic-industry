"""칼날 모듈 추종 — 곧은 칼날은 곧은 유리를 전제한다.

9/24 발주자가 계단 칼날의 일곱 조각을 따로 띄워 유리를 따라가게 하는 안을
승인했다. 근거는 두 개의 숫자다.

  · 칼끝 깊이 예산 0.15 에서 칼 쪽(S10)이 0.105 를 쓰는데, 흡착패드 평면도
    0.3 이 만드는 유리 굴곡은 곧은 칼날을 가장 좋게 교정해도 그 나머지를 넘는다.
  · 잠긴 칼날은 수직 반력으로 패드 사이 유리를 들어 올린다. 칼날이 유리를 타면
    그 힘이 박리 전선에서 닫힌다.

숫자가 바뀌면 결론이 바뀔 수 있다 — 그래서 결론을 숫자에 묶는다. 카탈로그 ·
인터록 · 사양서 · 파일럿이 같은 설계를 말하는지도 본다.
"""

import re
import unittest

from . import _path  # noqa: F401
from ._path import ROOT

import analysis_structural as ST  # noqa: E402
import glass_follow as GF  # noqa: E402
import parts as PT  # noqa: E402
import pilot_plan as PP  # noqa: E402
import plc_model as PLC  # noqa: E402
from console_consts import const as c  # noqa: E402

RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


class _Follow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rs, cls.ex = ST.run()
        cls.f = cls.ex["follow"]
        cls.by = {r.id: r for r in cls.rs}


class TestTheStraightKnifeCannotFollowThePads(_Follow):
    """교정으로는 못 구한다 — 그것이 모듈을 푼 이유다."""

    def test_the_straight_knife_breaks_the_budget_even_when_calibrated(self):
        self.assertGreater(self.f["straight"], 0.15,
                           "곧은 한 자루가 예산 안이면 모듈을 풀 이유가 없다")
        self.assertAlmostEqual(self.f["knife_side"], self.ex["knife"]["total"], places=9,
                               msg="잠금의 칼 쪽이 S10 과 다르다")

    def test_the_seven_following_modules_meet_it(self):
        s12 = self.by["S12"]
        self.assertTrue(s12.ok, f"일곱 모듈 추종이 예산을 넘는다: {s12.value:.3f}")
        self.assertAlmostEqual(s12.value, ST.TIP_GRIND + self.f["mc"]["modules"]["p95"], places=9)

    def test_roll_is_what_makes_the_modules_work(self):
        """들림만 주면 모듈 폭 안의 기울기를 못 따라간다."""
        mc = self.f["mc"]
        self.assertGreater(ST.TIP_GRIND + mc["heave"]["p95"], 0.15,
                           "들림만으로 예산 안이면 롤 피벗은 필요 없다 — 설계를 다시 본다")
        self.assertLess(mc["modules"]["p95"], mc["thirds"]["p95"],
                        "일곱 조각이 세 조각보다 못하다")

    def test_the_pad_band_that_would_save_the_straight_knife_is_not_buyable(self):
        """벨로우즈 패드로 못 만드는 평면도라야 모듈화가 정당하다."""
        self.assertLess(self.f["band_needed"], 0.1)
        self.assertAlmostEqual(GF.band_for(0.045), GF.PAD_FLAT * 0.045 / self.f["mc"]["straight"]["p95"])

    def test_the_monte_carlo_is_repeatable_and_linear_in_the_band(self):
        a = GF.monte_carlo(0.3, 400, 11)
        b = GF.monte_carlo(0.3, 400, 11)
        self.assertEqual(a, b, "같은 씨앗에서 다른 숫자가 나온다")
        half = GF.monte_carlo(0.15, 400, 11)
        for k in ("straight", "modules", "heave", "thirds"):
            self.assertAlmostEqual(half[k]["p95"], a[k]["p95"] / 2, places=9,
                                   msg=f"{k} 가 밴드에 선형이 아니다")

    def test_the_pad_rows_are_the_console_pad_rows(self):
        want = [(i - (PT.PAD_ROWS - 1) / 2) * PT.PANEL_W / PT.PAD_ROWS for i in range(PT.PAD_ROWS)]
        self.assertEqual(list(GF.ROW_Y), want)
        self.assertAlmostEqual(GF.SPAN_X, PT.PANEL_L / PT.PAD_COLS)
        self.assertAlmostEqual(GF.PAD_FLAT, PT.PAD_FLAT)

    def test_the_module_spans_are_the_knife_segments(self):
        spans = GF.module_spans()
        self.assertEqual(len(spans), int(c("KNIFE_BLADES")))
        covered = sorted(spans)
        self.assertAlmostEqual(covered[0][0], -GF.HALF)
        self.assertAlmostEqual(covered[-1][1], GF.HALF)
        for (a0, a1), (b0, b1) in zip(covered, covered[1:]):
            self.assertLessEqual(b0, a1, "모듈 사이에 유리를 못 보는 틈이 있다")


class TestTheVerticalReactionClosesAtThePeelFront(_Follow):
    """잠금이면 V 가 패드 사이를 건너고, 추종이면 전선에서 닫힌다."""

    def test_following_keeps_the_glass_inside_the_allowable(self):
        for rid in ("S13", "S14"):
            r = self.by[rid]
            self.assertTrue(r.ok, f"{rid} 가 유리 허용을 넘는다: {r.value:.2f} MPa")
            self.assertEqual(r.limit, GF.SIG_GL)

    def test_the_hold_down_preload_is_counted(self):
        """칼날이 떠 있으니 누름판이 붙드는 힘도 유리가 받는다."""
        want = c("KM_NET") + c("CHD_PRELOAD") * c("CHD_POSTS") / (c("KNIFE_W") * 1000)
        self.assertAlmostEqual(self.f["q_follow"], want, places=9)
        self.assertAlmostEqual(self.by["S13"].value, GF.span_stress(want), places=9)

    def test_a_locked_knife_cannot_carry_the_peel_across_the_pads(self):
        """잠금 운전으로 박리하려면 V/H 가 거의 0 이어야 한다 — 그래서 잠금은 진입·복귀용이다."""
        self.assertLess(self.f["lock_vh_max"], 0.05)
        self.assertGreater(self.f["follow_vh_max"], ST.V_RATIO,
                           "추종이 포락 V/H 에서 전선 우력을 못 견딘다")

    def test_the_limits_go_to_the_pilot(self):
        pt10 = next(t for t in PP.tests() if t.id == "PT-10")
        self.assertIn(f"{self.f['vh_arm_max']:.2f} mm", pt10.accept)
        self.assertIn(f"{self.f['lock_vh_max']:.3f}", pt10.accept)
        for sid in ("S12", "S13", "S14"):
            self.assertIn(sid, pt10.closes + pt10.accept)
        self.assertIn(str(int(c("CHD_PRELOAD"))), pt10.factors)
        top = int(re.findall(r"(\d+) N", pt10.factors)[-1])
        self.assertLessEqual(top, self.f["hd_post_max"],
                             "파일럿 누름판 예압 칸이 추종에서 유리 허용을 넘는다")


class TestTheModulesAreBuilt(unittest.TestCase):
    """카세트는 한 벌로 교환된다 — 공압과 신호는 캐리어 빔에 남는다."""

    def setUp(self):
        self.p = {p.pid: p for p in PT.P}
        self.n = int(c("KNIFE_BLADES"))

    def test_every_module_has_its_suspension(self):
        by_name = {p.name: p for p in PT.P if p.mod == "M-005"}
        want = {"카세트 홀더 (중앙)": 1, "카세트 홀더 (계단)": self.n - 1,
                "모듈 판스프링 (들림·롤)": 2 * self.n, "모듈 상한 스톱": self.n,
                "무게 보상 스프링": self.n, "모듈 잠금쐐기": self.n, "모듈 변위계": self.n}
        for name, qty in want.items():
            self.assertIn(name, by_name, f"{name} 이 카탈로그에 없다")
            self.assertEqual(by_name[name].qty, qty, f"{name} 수량")

    def test_the_holders_add_up_to_the_cassette_length(self):
        hold = [p for p in PT.P if p.name.startswith("카세트 홀더")]
        total = sum(p.shape.d["L"] * p.qty for p in hold)
        self.assertAlmostEqual(total, PT.CASS_L, places=6,
                               msg="홀더 길이의 합이 카세트 길이(겹침 포함)와 다르다")

    def test_air_and_signals_stay_on_the_machine(self):
        """교환품에 공압과 신호를 실으면 교환 때마다 배관을 푼다."""
        for name in ("모듈 잠금쐐기", "모듈 변위계"):
            part = next(p for p in PT.P if p.name == name)
            self.assertIn("캐리어 빔", part.fix, f"{name} 이 캐리어 빔에 서지 않는다")

    def test_the_pad_flatness_is_one_number(self):
        """조립 검사와 구매 검사와 해석이 같은 밴드를 말해야 한다."""
        import procure as PR
        want = f"동일 평면 ≤ {c('PAD_FLAT') * 1000:.1f}"
        step = next(s for s in PT.STEPS["M-004"] if "흡착패드" in s[1])
        self.assertIn(want, step[3], "조립 검사의 패드 평면도가 해석과 다르다")
        self.assertIn(want, PR.BUY_SPEC["P-004-08"][3], "구매 검사의 패드 평면도가 해석과 다르다")
        self.assertAlmostEqual(GF.PAD_FLAT, c("PAD_FLAT") * 1000)


class TestTheInterlocksHoldTheModes(unittest.TestCase):
    """들어갈 때와 나올 때는 곧은 칼날이어야 한다."""

    def setUp(self):
        self.d = {x.name: x for x in PLC.DERIVED}
        self.leaves = {x.name: x for x in PLC.LEAVES}

    def test_the_knife_is_locked_to_enter_to_return_and_to_change(self):
        for name in ("KNIFE_Z_PERMIT", "RAPID_PERMIT", "CASSETTE_RELEASE"):
            self.assertIn("KM_ALL_LOCKED", self.d[name].terms, f"{name} 이 모듈 잠금을 보지 않는다")

    def test_losing_the_glass_stops_the_knife(self):
        self.assertIn("KM_TRAVEL_END", self.d["KNIFE_SAFE_STOP"].terms)

    def test_every_module_is_seen_and_driven(self):
        n = int(c("KNIFE_BLADES"))
        self.assertEqual(self.leaves["KM_LOCKED"].count, n)
        self.assertEqual(self.leaves["KM_TRACK"].count, n)
        drive = next(x for x in PLC.DRIVES if x.tag == "CY-407")
        self.assertEqual(drive.count, n, "모듈마다 따로 풀리지 않는다")
        self.assertEqual(drive.stop, "스프링 잠금", "공압이 빠지면 잠겨야 칼날이 유리에서 뜬다")


class TestTheSpecificationSaysIt(_Follow):
    """입찰자는 해석 보고서가 아니라 사양서를 받는다."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rfq = RFQ.read_text(encoding="utf-8")
        i = cls.rfq.index("<h3>계단 칼날 셀 (DL-101 · SHK-101)</h3>")
        cls.c62 = cls.rfq[i:cls.rfq.index("</ul>", i)]

    def test_the_clause_carries_the_model_numbers(self):
        want = [f"±{c('KM_TRAVEL') * 1000:.1f} mm", f"±{c('KM_ROLL'):.1f}°",
                f"{c('KNIFE_LAND') * 1000:.1f} mm", f"{c('KM_NET'):.2f} N/mm",
                f"{c('PAD_FLAT') * 1000:.1f} mm", f"{c('KM_ENTRY') * 1000:.0f} mm",
                f"{self.f['lock_vh_max']:.3f}", f"≤ {self.f['vh_arm_max']:.2f} mm"]
        for token in want:
            self.assertIn(token, self.c62, f"6.2 항에 {token} 이 없다 — 모델과 갈라졌다")

    def test_the_clause_names_the_checks(self):
        for sid in ("S12", "S13", "S14", "PT-10", "KM_TRAVEL_END"):
            self.assertIn(sid, self.c62)

    def test_the_io_budget_grew_by_one_analogue_card(self):
        self.assertEqual(PLC.BUDGET[PLC.AI], 48)
        self.assertIn("AI 카드 한 장(8 점)을 더했다", self.rfq)


if __name__ == "__main__":
    unittest.main()
