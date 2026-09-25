"""램프 지지·관통 상세 — 처짐 · 열팽창 · 열교 · 침기 · 봉착부.

IR 뱅크 검토가 "처짐 · 실링 · 그림자" 를 상세설계로 넘겼는데, 풀어 보니
**적지 않은 둘이 더 컸다** — 차등 열팽창과 봉착부 온도. 그 결론이 틀리는
방식은 셋이다:

  ① **재료 상수를 잘못 넣는다** — 석영의 α 가 강재의 1/30 이라는 것이
     LM3 전체의 근거다. 이 값이 흔들리면 유동 행정이 흔들린다.
  ② **정식의 방향이 뒤집힌다** — 봉착부 창은 **넓어야** 좋고 처짐은
     **작아야** 좋다. 한 번 뒤집혔다가 시험이 아니라 눈으로 잡았다.
  ③ **결정이 도면에 안 내려간다** — 유동 행정과 부시 재질이 카탈로그와
     구매 사양에 없으면 치수가 같은 강재 슬리브가 온다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import irbank as IR
import lampmount as LM
import parts as PT
import procure as PR
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestTheBeamAndFinAreRight(unittest.TestCase):
    def test_sag_matches_the_closed_form(self):
        """δ = 5wL⁴/384EI. 단면 성질까지 손으로 다시 센다."""
        d, _, A, I = LM.sag()
        ID = LM.OD - 2 * LM.WALL
        self.assertAlmostEqual(A, math.pi / 4 * (LM.OD ** 2 - ID ** 2), places=6)
        self.assertAlmostEqual(I, math.pi / 64 * (LM.OD ** 4 - ID ** 4), places=3)
        w = LM.M_LAMP * 9.80665 / LM.HEAT_L
        self.assertAlmostEqual(d, 5 * w * LM.HEAT_L ** 4 / (384 * LM.E_Q * I),
                               places=9)

    def test_sag_scales_with_the_fourth_power_of_span(self):
        """스팬을 두 배로 하면 처짐이 16 배 — 발열장을 더 늘릴 때 쓸 눈금이다."""
        _, I = LM._section()
        w = LM.M_LAMP * 9.80665 / LM.HEAT_L
        def d(L):
            return 5 * w * L ** 4 / (384 * LM.E_Q * I)
        self.assertAlmostEqual(d(2 * LM.HEAT_L) / d(LM.HEAT_L), 16.0, places=6)

    def test_quartz_barely_expands_next_to_steel(self):
        """LM3 전체가 이 비에 걸려 있다."""
        self.assertLess(LM.ALPHA_Q * 25, LM.ALPHA_STS,
                        "석영이 강재의 1/25 보다 많이 늘면 유동 행정 결론이 바뀐다")
        steel, quartz, diff = LM.expansion()
        self.assertAlmostEqual(diff, steel - quartz, places=9)
        self.assertGreater(diff, 3.0, "차이가 3 mm 미만이면 유동단이 필요 없다")

    def test_the_fin_length_is_short_because_quartz_conducts_badly(self):
        """봉착부 창이 좁은 이유가 이것이다 — 열길이가 20 mm 도 안 된다."""
        m, x_hot, x_cold = LM.pinch()
        A, _ = LM._section()
        want = math.sqrt(LM.H_PINCH * 1e-6 * math.pi * LM.OD /
                         (LM.K_Q * 1e-3 * A))
        self.assertAlmostEqual(m, want, places=9)
        self.assertLess(1 / m, 20.0)
        self.assertLess(x_hot, x_cold, "350 ℃ 자리가 250 ℃ 자리보다 멀 수 없다")

    def test_leakage_follows_the_orifice_law(self):
        """침기는 √Δp 로 는다 — 부압을 네 배로 하면 두 배다."""
        _, q1, kw1 = LM.leakage(1.0)
        try:
            LM.DP *= 4
            _, q4, kw4 = LM.leakage(1.0)
        finally:
            LM.DP /= 4
        self.assertAlmostEqual(q4 / q1, 2.0, places=6)
        self.assertAlmostEqual(kw4 / kw1, 2.0, places=6)

    def test_sealing_and_bushing_material_both_matter(self):
        _, _, kw_seal = LM.leakage(LM.SEAL_FACTOR)
        _, _, kw_raw = LM.leakage(1.0)
        self.assertLess(kw_seal, kw_raw / 5, "실링이 한 자릿수를 못 줄이면 의미가 없다")
        _, _, add_low = LM.bridge(LM.K_BUSH_LOW)
        _, _, add_st = LM.bridge(LM.K_BUSH_STEEL)
        self.assertGreater(add_st / add_low, 10.0,
                           "재질 차이가 작으면 사양으로 적을 이유가 없다")


class TestTheConclusionsHoldTheirDirection(unittest.TestCase):
    def setUp(self):
        self.rs, self.ex = LM.run()

    def test_only_the_two_intended_cases_exceed(self):
        """LM6(봉착부 창)·LM7(그림자)만 넘는다 — 둘 다 '하지 않는 이유' 다."""
        over = sorted(r.id for r in self.rs if not r.ok)
        self.assertEqual(over, ["LM6", "LM7"], f"판정이 바뀌었다: {over}")

    def test_the_pinch_window_is_stated_as_needed_over_available(self):
        """창은 **넓어야** 좋다. 값/한계를 뒤집어 적으면 좁은 창이 OK 로 나온다."""
        r = [x for x in self.rs if x.id == "LM6"][0]
        self.assertAlmostEqual(r.value, LM.TOL_PINCH, places=6)
        self.assertAlmostEqual(r.limit, self.ex["x_cold"] - self.ex["x_hot"],
                               places=6)
        self.assertFalse(r.ok, "물리가 주는 창이 제작 공차보다 넓어졌다면 "
                               "RLM4(제조사에 넘김)의 근거가 사라진다")

    def test_the_shadow_is_the_blocked_lamp_not_an_area_ratio(self):
        """면적비로 세면 1.9 K 가 나와 '괜찮다' 가 된다 — 그림자는 그런 게 아니다."""
        frac, dT = LM.shadow()
        self.assertGreater(frac, 0.15, "가장 가까운 램프의 직달 몫이 이보다 작을 수 없다")
        self.assertGreater(dT, IR.PANEL_W * 0 + 21.0,
                           "지지대가 유리 허용 편차를 못 넘으면 금지할 이유가 없다")

    def test_no_intermediate_support_is_needed(self):
        """LM1 이 지지를 없애야 LM7 이 '쓰지 않는 이유' 로 남는다."""
        r = [x for x in self.rs if x.id == "LM1"][0]
        self.assertTrue(r.ok)
        self.assertLess(self.ex["dflux"], 0.02)

    def test_penetration_losses_stay_inside_the_budget(self):
        self.assertLess(self.ex["add_low"] + self.ex["kw_seal"],
                        self.ex["base_kw"],
                        "관통부가 벽 자체보다 더 새면 관통을 다시 생각해야 한다")

    def test_every_result_and_requirement_carries_its_basis(self):
        for r in self.rs:
            self.assertGreater(r.limit, 0, f"{r.id} 한계가 없다")
            self.assertGreaterEqual(len(r.basis), 8, f"{r.id} 근거가 없다")
            self.assertGreaterEqual(len(r.note), 20, f"{r.id} 읽는 법이 없다")
        rq = LM.requirements()
        self.assertGreaterEqual(len(rq), 5)
        for q in rq:
            self.assertRegex(q.id, r"^RLM\d+$")
            self.assertTrue(q.owner.strip(), f"{q.id} 받는 곳이 없다")
            self.assertGreaterEqual(len(q.why), 40, f"{q.id} 근거가 짧다")


class TestTheDecisionReachedTheCatalogue(unittest.TestCase):
    def test_the_lamp_note_carries_the_floating_end(self):
        lamp = [p for p in PT.P if p.pid == "P-002-18"][0]
        self.assertIn("유동", lamp.fix,
                      "양단 고정으로 지으면 첫 승온에서 램프가 뜯긴다")

    def test_the_bushing_spec_names_a_conductivity_limit(self):
        spec = PR.BUY_SPEC["P-002-25"]
        blob = " ".join(spec)
        self.assertIn("0.9", blob, "부시 열전도율 상한이 구매 사양에 없다")
        self.assertRegex(blob, r"누설", "잔여 누설 한도가 구매 사양에 없다")

    def test_the_bushing_count_matches_two_ends_per_lamp(self):
        bush = [p for p in PT.P if p.pid == "P-002-25"][0]
        self.assertEqual(bush.qty, int(c("LAMPS")) * 2)

    def test_the_report_carries_the_section(self):
        html = (ROOT / "docs" / "dg-hk60-analysis.html").read_text(encoding="utf-8")
        for r in self.rs if hasattr(self, "rs") else LM.run()[0]:
            self.assertIn(f'<td class="k">{r.id}</td>', html,
                          f"{r.id} 이 보고서에 없다")
        self.assertIn("램프 지지·관통 상세", html)
        body = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
        self.assertNotIn("**", body)
