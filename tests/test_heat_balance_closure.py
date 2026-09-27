"""열수지를 누가 닫는가 — 열린 벤치 · 셔터 상자 · FAT.

파일럿 PT-05 는 열수지를 닫는 시험으로 적혀 있었는데 두 군데가 어긋나 있었다:

  · 4단계가 '네 항의 합이 안 맞으면 반사손실이다' 라고 적었다. 열수지 HB2 는
    반대로 결론 냈다 — 닫힌 챔버에서 패널을 빗나간 복사는 연마 내피에 되튀어
    결국 패널·벽·배기로 나가므로 손실 항이 아니다. 해석서 T12 도 같은 몫을
    '배기·데크 열용량·반사손실인데 아직 아무도 세지 않았다' 고 적고 있었다
  · 손실의 절반이 넘는 에어록 교환(HB4)을 PT-05 가 재지 않았다. 에어록 검토
    RAL5 와 열수지 RHB5 는 둘 다 '파일럿 PT-05 가 실측한다' 고 넘겼는데, 정작
    계획서의 '파일럿이 못 답하는 것' 은 벤치가 개방형이라 에어록이 없다고 적었다

고치면서 드러난 것 — **열린 벤치로는 챔버의 수지를 닫을 수 없다.** 그래서
벤치는 결합효율의 하한을, 셔터 한 장을 단 상자는 에어록 항을, FAT 무부하
손실 시험은 챔버의 손실 합을 맡는다. 이 파일은 그 나눔이 다시 흐려지지 않게
묶는다. 사양서 FAT 표의 문 열림 10.7 s (포락선을 넓히기 전의 값) 도 여기서
모델과 잇는다.
"""

import re
import unittest

from . import _path  # noqa: F401
from ._path import ROOT

import airlock as AIR  # noqa: E402
import analysis_thermal as TH  # noqa: E402
import cycle as CY  # noqa: E402
import heatbalance as HB  # noqa: E402
import pilot_plan as PP  # noqa: E402

PILOT = ROOT / "docs" / "dg-hk60-pilot.html"
ANALYSIS = ROOT / "docs" / "dg-hk60-analysis.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"


def _text(path):
    return path.read_text(encoding="utf-8")


def _pt05():
    return next(t for t in PP.tests() if t.id == "PT-05")


class TestTheBenchIsOpen(unittest.TestCase):
    """벤치가 답할 수 있는 것만 벤치에 건다."""

    @classmethod
    def setUpClass(cls):
        cls.t = _pt05()
        cls.steps = " ".join(cls.t.steps)

    def test_the_open_side_residual_is_not_a_chamber_loss(self):
        """벤치의 남는 몫은 열린 옆면의 손실이다 — 챔버로 옮기면 없는 구멍을 찾는다."""
        self.assertNotIn("반사손실", self.steps)
        self.assertIn("HB2", self.steps, "빗나간 복사가 손실이 아니라는 근거를 대지 않는다")
        self.assertIn("하한", self.steps, "벤치 결합효율이 챔버의 하한이라는 것이 빠졌다")

    def test_the_open_side_is_measured_so_the_bench_balance_can_close(self):
        """수지 오차 10 % 를 판정하려면 옆으로 빠지는 복사도 재야 한다."""
        power = next(r for r in PP.RIG if r.part == "전력·열류")
        self.assertIn("옆면 복사계", power.what)
        self.assertIn("옆면 복사계", self.steps)
        self.assertIn("수지 오차 ≤ 10 %", self.t.accept)

    def test_no_generated_document_calls_the_residual_a_reflection_loss(self):
        for path in (PILOT, ANALYSIS):
            text = _text(path)
            self.assertNotIn("반사손실", text, f"{path.name} 에 반사손실이 남아 있다")
            self.assertNotIn("아직 아무도 세지 않았다", text,
                             f"{path.name} 이 열수지가 센 것을 안 셌다고 말한다")

    def test_t12_points_to_the_balance_not_to_a_leak(self):
        rs, _ = TH.chamber_wall()
        t12 = next(r for r in rs if r.id == "T12")
        self.assertIn("HB2", t12.note)
        self.assertNotIn("반사손실", t12.note)


class TestTheShutterBoxMeasuresTheAirlock(unittest.TestCase):
    """가장 큰 손실 항은 문이 있어야 잰다 — 셔터 한 장이면 된다."""

    @classmethod
    def setUpClass(cls):
        cls.t = _pt05()
        cls.steps = " ".join(cls.t.steps)
        cls.box = next(r for r in PP.RIG if r.part == "셔터 상자")

    def test_the_box_carries_the_production_opening(self):
        self.assertIn(f"개구 {AIR.OPEN_W*1e3:,.0f} × {AIR.OPEN_H*1e3:.0f}", self.box.what)
        self.assertIn("P-002-20", self.box.what)

    def test_the_cold_pool_stays_below_the_sill(self):
        """한 번 열 때 들어온 찬 공기가 문턱까지 차오르면 개구가 막혀 교환을 작게 잰다."""
        pool = AIR.chosen()["V"] / (PP.BOX_W * PP.BOX_D)
        self.assertGreaterEqual(PP.BOX_SILL, 2 * pool)
        self.assertGreater(PP.BOX_H, PP.BOX_SILL + AIR.OPEN_H, "개구 위에 뜨거운 공기가 고일 자리가 없다")
        self.assertGreaterEqual(PP.BOX_KW, AIR.kw(), "히터가 생산 개폐 손실을 못 댄다")

    def test_pt05_runs_the_box_at_production_timing(self):
        self.assertIn("셔터 상자", self.steps)
        self.assertIn(f"택트 {CY.TAKT:.1f} s", self.steps)
        self.assertIn(f"{AIR.open_time():.1f} s 씩 여닫는", self.steps)
        self.assertIn(f"가정 {AIR.CD:.2f}", self.steps, "유출계수를 역산하지 않는다")

    def test_the_acceptance_is_the_airlock_budget(self):
        _, ex = AIR.run()
        self.assertIn(f"에어록 몫 {ex['allow']:.1f} kW", self.t.accept)
        self.assertIn(f"계산 {AIR.kw():.2f} kW", self.t.accept)
        self.assertIn(f"회당 {AIR.kw() * CY.TAKT / AIR.N_DOOR:.0f} kJ", self.t.accept)

    def test_every_heat_requirement_given_to_the_pilot_has_a_test(self):
        """열수지·에어록 요구 중 파일럿이 받기로 한 것은 실제로 항목이 있어야 한다."""
        closes = " ".join(t.closes for t in PP.tests())
        for q in HB.requirements() + AIR.requirements():
            if "파일럿" in q.owner:
                self.assertIn(q.id, closes, f"{q.id} 을 파일럿이 받기로 했는데 항목이 없다")

    def test_the_plan_does_not_call_what_it_tests_out_of_scope(self):
        """못 답하는 것 표가 PT-05 가 재는 에어록을 계속 범위 밖이라 하면 계획이 둘로 갈린다."""
        for what, why in PP.OUT_OF_SCOPE:
            self.assertNotIn("에어록", what, f"'{what}' — PT-05 가 재는 것을 범위 밖이라 한다")
        chamber = next(y for w, y in PP.OUT_OF_SCOPE if "챔버" in w)
        self.assertIn("FAT", chamber, "챔버 전체를 누가 닫는지 적지 않았다")


class TestTheChamberClosesAtFat(unittest.TestCase):
    """챔버의 손실 합은 챔버가 있어야 잰다 — FAT 무부하 손실 시험."""

    @classmethod
    def setUpClass(cls):
        cls.rfq = _text(RFQ)
        cls.b = HB.balance()
        cls.hold = cls.b["wall"] + cls.b["infil"] + cls.b["terminal"]
        cls.inc = cls.b["airlock"] + cls.b["fork"]

    def test_the_fat_table_has_the_no_load_loss(self):
        self.assertIn("가열실 무부하 손실", self.rfq)
        self.assertIn(f"≤ {self.b['assumed_loss']:.1f} kW", self.rfq)
        self.assertIn(f"계산 {self.hold:.1f} + {self.inc:.1f} = {self.b['loss']:.1f} kW", self.rfq)

    def test_the_fat_door_open_time_is_the_models(self):
        """포락선을 넓혀 데크가 길어지자 문 열림이 10.7 → 10.9 s 가 됐는데 표는 그대로였다."""
        row = re.search(r"포크 왕복 시간</strong>.*?</tr>", self.rfq, re.S).group(0)
        self.assertIn(f"문 열림 ≤ {AIR.open_time():.1f} s", row)
        self.assertIn(f"포크 왕복 {2 * AIR.REACH / AIR.V_FORK:.1f} s", row)

    def test_rhb5_and_ral5_hand_the_chamber_to_fat(self):
        reqs = {q.id: q for q in HB.requirements() + AIR.requirements()}
        for rid in ("RHB5", "RAL5"):
            self.assertIn("PT-05", reqs[rid].owner)
            self.assertIn("FAT", reqs[rid].owner)
        self.assertIn(f"문 닫힘 유지 {self.hold:.1f} kW", reqs["RHB5"].value)
        self.assertIn(f"생산 개폐 증분 {self.inc:.1f} kW", reqs["RHB5"].value)

    def test_oi05_says_who_closes_what(self):
        oi05 = re.search(r"<b>OI-05</b>(.*?)<div class=\"oi\">", self.rfq, re.S).group(1)
        self.assertNotIn("전력량계·배기", oi05, "OI-05 가 아직 파일럿이 챔버 수지를 닫는다고 한다")
        self.assertIn("셔터 한 장", oi05)
        self.assertIn("FAT 무부하 손실", oi05)


if __name__ == "__main__":
    unittest.main()
