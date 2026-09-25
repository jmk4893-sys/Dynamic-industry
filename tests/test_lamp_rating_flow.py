"""램프 수 · 설치정격 — 콘솔 상수 하나가 문서 끝까지 흐르는가.

포락선 2,500 × 1,400 이 램프를 40 등 · 100 kW 에서 48 등 · 120 kW 로 올린 뒤에도
옛 설비를 말하는 자리가 남아 있었다. 계산은 전부 새 상수로 돌고 있었는데,
그 결과를 **글로 옮긴 자리**가 손으로 적은 숫자를 들고 있었다:

  · 열해석 T12 — 판정 한계가 35 kW 리터럴이었다. 계산은 120 kW 로, 한계는
    100 kW 시절 값으로. 램프 지지 LM5 는 같은 예산을 42 kW 로 쓰고 있었다
  · 해석서 열수지 장 — 제목부터 '30 kW 는 새지 않았다' · '정격 100 × η 0.65'
  · 해석서 IR 뱅크 · 램프 지지 장 — 발열장 2,200 · 챔버 2,300 · 관통 80 개소 ·
    면내 편차 11 K 가 바로 옆 표의 2,400 · 2,500 · 96 · 9 K 와 달랐다
  · 파일럿 PT-04 · PT-05 — 램프 분배 6·7·7·7·7·6, 설치정격 100 kW
  · 발주 시점표 — '램프 40등'
  · 사양서 OI-05 — 손실 예산 35 kW 중 30 kW 의 행방을 '아직 아무도 세지 않았다'
    (해석서가 이미 세었다), 냉각 랙 여유가 3.4항 · 3.6항 · OI-05 에서 서로 달랐다

그래서 두 가지를 묶는다 — 값이 한 곳에서 나오는가, 그리고 문서가 옛 설비를
다시 말하지 않는가.
"""

import re
import unittest

from . import _path  # noqa: F401
from ._path import ROOT

import analysis_irbank as IRB  # noqa: E402
import analysis_thermal as TH  # noqa: E402
import cycle as CY  # noqa: E402
import heatbalance as HB  # noqa: E402
import lampmount as LM  # noqa: E402
import parts as PT  # noqa: E402
import pilot_plan as PP  # noqa: E402
from console_consts import const as c  # noqa: E402

ANALYSIS = ROOT / "docs" / "dg-hk60-analysis.html"
PILOT = ROOT / "docs" / "dg-hk60-pilot.html"
PROCURE = ROOT / "docs" / "dg-hk60-procurement.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


def _text(path):
    return path.read_text(encoding="utf-8")


class TestOneSourceForTheRating(unittest.TestCase):
    """정격 · 유효 · 손실 예산은 콘솔 LAMPS 에서 한 번만 나온다."""

    def test_rated_power_is_lamps_times_lamp_power(self):
        self.assertEqual(TH.LAMPS, int(c("LAMPS")))
        self.assertAlmostEqual(TH.RATED_KW, c("LAMPS") * TH.LAMP_KW, places=9)
        self.assertAlmostEqual(HB.RATED_KW, TH.RATED_KW, places=12)

    def test_the_loss_budget_has_one_owner(self):
        """T12 와 LM5 가 서로 다른 예산을 쓰고 있었다 (35 vs 42)."""
        want = TH.RATED_KW * (1 - TH.ETA)
        self.assertAlmostEqual(TH.LOSS_BUDGET, want, places=9)
        self.assertAlmostEqual(LM.LOSS_BUDGET, TH.LOSS_BUDGET, places=12)
        self.assertAlmostEqual(HB.LOSS_BUDGET, TH.LOSS_BUDGET, places=12)

    def test_t12_judges_against_the_budget_not_a_literal(self):
        rs, _ = TH.chamber_wall()
        t12 = next(r for r in rs if r.id == "T12")
        self.assertAlmostEqual(t12.limit, TH.LOSS_BUDGET, places=12)
        self.assertIn(f"정격 {TH.RATED_KW:.0f} kW", t12.basis)
        self.assertIn(f"손실 예산 {TH.LOSS_BUDGET:.0f} kW", t12.basis)

    def test_the_catalog_bushing_count_is_the_penetration_count(self):
        bush = next(p for p in PT.P if p.pid == "P-002-25")
        self.assertEqual(bush.qty, LM.N_PEN)
        self.assertIn(f"총 {LM.N_PEN} 개소", bush.note)

    def test_the_sag_check_names_the_lamp_it_checks(self):
        rs, _ = LM.run()
        lm1 = next(r for r in rs if r.id == "LM1")
        self.assertIn(f"{LM.HEAT_L:,.0f} 스팬", lm1.what)


class TestTheDocumentsSpeakOfThisPlant(unittest.TestCase):
    """생성 문서가 지금 설비의 숫자를 말하는가."""

    @classmethod
    def setUpClass(cls):
        cls.analysis = _text(ANALYSIS)
        cls.pilot = _text(PILOT)
        cls.procure = _text(PROCURE)
        cls.rfq = _text(RFQ)
        cls.console = _text(CONSOLE)

    def test_the_analysis_states_the_current_budget(self):
        b = HB.balance()
        rest = TH.LOSS_BUDGET - b["wall"]
        self.assertIn(f"정격 {TH.RATED_KW:.0f} kW − 유효 {TH.USEFUL_KW:.0f} kW = "
                      f"손실 예산 {TH.LOSS_BUDGET:.0f} kW", self.analysis)
        self.assertIn(f"열수지 — {rest:.0f} kW 는 새지 않았다", self.analysis)
        self.assertIn(f"총 {TH.LAMPS} 등 · {TH.RATED_KW:.0f} kW 불변", self.analysis)
        self.assertIn(f"총 {2 * TH.LAMPS} 개소의 관통 실링", self.analysis)

    def test_the_pilot_and_procurement_carry_the_lamp_count(self):
        self.assertIn(f"IR 설치정격 {TH.RATED_KW:.0f} kW", self.pilot)
        n = TH.LAMPS // (TH.DECKS + 1)
        self.assertIn(f"뱅크당 {n} 등 × {TH.DECKS + 1} 뱅크", self.pilot)
        self.assertIn(f"램프 {TH.LAMPS}등", self.procure)
        pt04 = next(t for t in PP.tests() if t.id == "PT-04")
        self.assertTrue(any(f"{CY.DWELL:.0f} s" in s for s in pt04.steps),
                        "PT-04 의 마지막 소킹 시점이 설계 체류와 다르다")

    def test_no_generated_document_speaks_of_the_old_plant(self):
        """40 등 · 100 kW · 2,400 × 1,200 시절의 숫자가 현재형으로 다시 들어오면 실패.

        이력을 적는 자리(콘솔 개정 이력 · 사양서 3.6항 전후 비교)는 생성 문서가
        아니라 여기서 보지 않는다.
        """
        stale = {
            "해석서": (self.analysis, (
                "정격 100", "설치정격 100", "설치정격이 100", "100 kW 불변",
                "손실 예산 35", "총 80 개소", "80 개소를 뚫는다", "2,200 스팬",
                "강재 챔버 <span class=\"m\">2,300", "±1,340", "80.9 장/h",
                "13.7 kW", "면내 편차 11 K", "30 kW 는 새", "222 초",
                "설계 체류 222.6")),
            "파일럿": (self.pilot, ("설치정격 100", "6·7·7·7·7·6", "222 s")),
            "조달": (self.procure, ("램프 40등",)),
            "콘솔 카탈로그": (self.console, ("총 80 개소", "23.1 → 44.6")),
        }
        for doc, (text, phrases) in stale.items():
            for s in phrases:
                self.assertNotIn(s, text, f"{doc} 에 옛 설비의 '{s}' 가 남아 있다")


class TestTheRfqAgreesWithItself(unittest.TestCase):
    """사양서는 손으로 쓴다 — 그래서 계산과 한 번 더 대조한다."""

    @classmethod
    def setUpClass(cls):
        cls.rfq = _text(RFQ)
        m = re.search(r"<b>OI-05</b>(.*?)<div class=\"oi\">", cls.rfq, re.S)
        cls.oi05 = m.group(1)

    def test_oi05_reports_the_counted_balance(self):
        b = HB.balance()
        self.assertIn(f"{TH.LOSS_BUDGET:.0f} kW", self.oi05)
        self.assertIn(f"{b['loss']:.1f} kW", self.oi05)
        self.assertIn(f"{b['eta'] * 100:.0f} %", self.oi05)
        self.assertNotIn("아직 아무도 세지 않았다", self.oi05,
                         "해석서가 이미 센 것을 사양서가 안 셌다고 말한다")

    def test_the_rack_margin_is_one_number(self):
        """3.4항 · 3.6항 · OI-05 가 13/88 · 17/94 · 88 로 서로 달랐다."""
        _, gc = TH.glass_cool()
        m3 = 3 * CY.TAKT / gc["lump"] - 1
        m5 = int(c("DECKS")) * CY.TAKT / gc["lump"] - 1
        self.assertIn(f'{m3 * 100:.0f} → {m5 * 100:.0f} %', self.rfq)
        self.assertIn(f"5단 · 여유 {m5 * 100:.0f} %", self.rfq)
        self.assertIn(f'<span class="m">{m5 * 100:.0f} %</span>라', self.oi05)


if __name__ == "__main__":
    unittest.main()
