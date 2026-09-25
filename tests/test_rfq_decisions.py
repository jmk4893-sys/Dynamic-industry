"""사양서 발행 전 결정 — 열어 둔 자리를 닫고, 닫은 값을 모델에 묶는다.

9/25 까지 사양서에는 '합의된 기준', '협의해 확정', '인터페이스를 확인해 확정' 이
남아 있었다. 입찰자는 그 자리에 값을 매길 수 없다 — 값이 없는 조건은 가장 비싼
해석으로 견적되거나 계약 뒤의 분쟁이 된다. 발주자 쪽 결정을 사양서에 적었고,
여기서는 적은 수치가 파일럿 계획 · 해석 · 콘솔과 같은 식에서 나오는지 본다.
사양서만 고치거나 모델만 고치면 실패한다.

발행 때 적을 칸(발행일 · 접수처 · 담당자)은 test_dg_hk60_rfq 가 센다.
"""

import re
import unittest

from . import _path  # noqa: F401
from ._path import ROOT

import analysis_structural as ST  # noqa: E402
import analysis_thermal as TH  # noqa: E402
import cycle as CY  # noqa: E402
import pilot_plan as PP  # noqa: E402
from console_consts import const as c  # noqa: E402

RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


def plain(html):
    """태그를 벗기고 공백을 하나로 — 줄바꿈과 강조가 문장을 자르지 않게."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def clause(html, num):
    """조항 머리 <div class="n">num</div> 부터 다음 조항 머리까지."""
    i = html.index(f'<div class="n">{num}</div>')
    ends = [e for e in (html.find('<div class="clause">', i + 1), html.find("</section>", i))
            if e != -1]
    return html[i:min(ends)]


class _Rfq(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")
        cls.text = plain(cls.html)

    def cl(self, num):
        return plain(clause(self.html, num))

    def row(self, html, head):
        """head 가 든 표의 행 — 하나여야 한다. 둘이면 어느 쪽이 결정인지 모른다."""
        rows = [plain(r) for r in re.findall(r"<tr>(.*?)</tr>", html, re.S) if head in r]
        self.assertEqual(len(rows), 1, f"'{head}' 행이 {len(rows)} 개다")
        return rows[0]


class TestNothingIsLeftToBeAgreedLater(_Rfq):
    """'합의된 기준' 은 기준이 아니다 — 입찰자는 없는 기준에 값을 매기지 못한다."""

    RETIRED = (
        ("합의된 잔류물", "10.2 SAT 분리 품질 — 합격선이 비어 있었다"),
        ("합의된 시험 패널", "4.2 성능보증 — 무엇으로 보증하는지 비어 있었다"),
        ("협의해 시험 패널 사양을 확정", "4.2 시험 패널 — 계약 뒤로 미뤄져 있었다"),
        ("DOE로 도출해 제안하고", "4.3 합격선 — 입찰자가 제 합격선을 정하게 돼 있었다"),
        ("인터페이스를 확인해 확정", "6.6 CS-201 반출 — 누가 카트를 빼는지 비어 있었다"),
        ("독립 방호구획", "6.6 PL-101/201 — 발주자 설비의 방호를 입찰자에게 지웠다"),
        ("MES 연동 규약은 발주자와 합의", "7 연동 — MES 쪽 일이 누구 몫인지 비어 있었다"),
    )

    def test_the_open_phrases_are_gone(self):
        for phrase, where in self.RETIRED:
            self.assertNotIn(phrase, self.text, f"{where}: '{phrase}' 가 남았다")

    def test_what_stays_open_is_physical_not_a_decision(self):
        """남겨 둔 것은 실측이 닫는 자리다 — 칼날 모듈 예압은 PT-10 이 정한다."""
        self.assertIn("예압은 파일럿 PT-10 에서 확정한다", self.text)


class TestTheTestPanelsAreThePilotLots(_Rfq):
    """보증은 무엇으로 재는지가 정해져야 보증이다 (4.2)."""

    def setUp(self):
        self.c42 = self.cl("4.2")
        self.lots = {lot.lot: lot for lot in PP.lots()}

    def test_the_lots_are_the_pilot_plan_lots(self):
        self.assertIn(f"DG-HK60C-{PP.DOC}", self.c42, "시험 패널이 파일럿 계획서를 가리키지 않는다")
        for name in ("A", "B"):
            self.assertIn(f"로트 {name} {self.lots[name].what}", self.c42,
                          f"4.2 의 로트 {name} 가 파일럿 계획서와 갈라졌다")

    def test_each_lot_carries_the_guarantee(self):
        self.assertIn("두 로트 각각에서 보증한다", self.c42)
        self.assertIn("쉬운 로트의 평균으로 어려운 로트를 덮지 않는다", self.c42)

    def test_the_heavy_lot_is_the_one_the_pilot_says(self):
        """로드셀 용량을 정하는 로트가 사양서와 파일럿에서 같아야 한다."""
        self.assertIn("로드셀 용량을 정하는 쪽이 로트 B", self.c42)
        self.assertIn("로드셀 용량", self.lots["B"].why)
        self.assertNotIn("로드셀 용량", self.lots["A"].why)

    def test_the_guarantee_is_split_where_the_work_is(self):
        """설계는 입찰자, 시공은 제작사 — 둘 사이 원인은 합동 분석이 가른다."""
        for token in ("설계 성능은 입찰자가 보증한다", "도면대로 지었는가는 제작사가 보증한다",
                      "합동 원인분석", "10.2항 SAT 합격선", "12.8항 설계 책임"):
            self.assertIn(token, self.c42)


class TestTheAcceptanceLineIsThePilotArithmetic(_Rfq):
    """SAT 합격선의 시료 수와 한계는 파일럿 PT-03 과 같은 식에서 나온다 (4.3 · 10.2)."""

    def setUp(self):
        self.c43 = self.cl("4.3")
        self.sat = self.row(clause(self.html, "10.2"), "분리 품질")
        self.n = PP.n_for_proportion(PP.YIELD_LOW, failures=PP.YIELD_FAILS)
        self.pt03 = next(t for t in PP.tests() if t.id == "PT-03")

    def test_the_owner_floor_is_stated_in_4_3(self):
        want = (f"로트마다 연속 {self.n} 장에서 유리 파손 {PP.YIELD_FAILS} 장 이하"
                f"(수율 하한 {PP.YIELD_LOW * 100:.0f} % · 신뢰도 95 %, Clopper–Pearson), "
                f"잔류 EVA 중량법 ≤ {PP.RESIDUAL_EVA_MAX:.1f} wt%")
        self.assertIn(want, self.c43)

    def test_the_sat_row_is_the_same_line_per_lot(self):
        self.assertIn("로트 A · B 각각", self.sat)
        self.assertIn(f"연속 {self.n} 장에서 유리 파손 ≤ {PP.YIELD_FAILS} 장 "
                      f"(수율 하한 {PP.YIELD_LOW * 100:.0f} % · 신뢰도 95 %)", self.sat)
        self.assertIn(f"잔류 EVA 중량법 ≤ {PP.RESIDUAL_EVA_MAX:.1f} wt% (4.3)", self.sat)

    def test_the_pilot_proves_the_same_line(self):
        """파일럿이 증명하는 선과 SAT 가 재는 선이 다르면 파일럿은 다른 설비를 승인한다."""
        self.assertEqual(self.pt03.n, self.n)
        self.assertIn(f"{self.n} 장이 필요하다", self.pt03.accept)
        self.assertIn(f"≤ {PP.RESIDUAL_EVA_MAX:.1f} wt%", self.pt03.accept)

    def test_the_zero_failure_alternative_is_the_real_number(self):
        n0 = PP.n_for_proportion(PP.YIELD_LOW, failures=0)
        self.assertLess(n0, self.n)
        self.assertIn(f"파손 0 장을 요구하면 {n0} 장", self.c43)

    def test_the_bidder_may_tighten_but_not_loosen(self):
        self.assertIn("더 엄한 한계를 제안할 수 있고, 더 느슨한 한계는 제안할 수 없다", self.c43)
        self.assertIn("합격선은 DOE 가 정하지 않는다", self.text, "OI-06 이 합격선을 다시 연다")


class TestTheResidualLineHoldsAtTheWorstGap(_Rfq):
    """1.0 wt% 는 칼날이 남기는 가장 나쁜 틈보다 두꺼워야 뜻이 있다 (4.3 주석)."""

    def setUp(self):
        self.c43 = self.cl("4.3")
        self.film = PP.RESIDUAL_EVA_MAX / 100 * c("MASS_GLASS") / TH.RHO["EVA"] * 1000   # mm
        _, ex = ST.follow()
        self.depth = ex["depth"]

    def test_the_film_is_computed_from_the_glass_mass(self):
        self.assertIn(f"잔류 EVA {PP.RESIDUAL_EVA_MAX:.1f} wt% 는 유리 위 EVA 막 "
                      f"{self.film:.3f} mm", self.c43)

    def test_the_worst_gap_is_the_analysis_s12(self):
        self.assertIn(f"칼끝 깊이 {self.depth:.3f} mm (CAL-001 S12, P95)", self.c43)

    def test_the_worst_gap_fits_inside_the_line(self):
        self.assertLessEqual(
            self.depth, self.film,
            f"S12 P95 {self.depth:.3f} mm 가 합격선의 막 {self.film:.3f} mm 를 넘는다 — "
            "4.3 주석의 '그 안에 든다' 가 거짓이 됐다")


class TestWhoRunsFatAndSat(_Rfq):
    """누가 하고 누가 보고 누가 내는지 — 비워 두면 셋 다 입찰자 견적에 들어간다 (10.1)."""

    def setUp(self):
        self.c101 = clause(self.html, "10.1")
        self.p101 = plain(self.c101)

    def test_the_table_has_the_four_rows(self):
        self.assertIn("<caption>수행 · 입회 · 비용</caption>", self.c101)
        for head in ("절차서", "FAT", "SAT", "재시험"):
            self.row(self.c101, f"<th>{head}</th>")

    def test_the_procedure_is_a_deliverable_that_exists(self):
        self.assertIn("입찰자 — 100 % 단계 제출물 (9.4항)", self.row(self.c101, "<th>절차서</th>"))
        self.assertIn("FAT/SAT 절차서", self.row(clause(self.html, "9.4"), "100 %"))

    def test_the_bidder_witnesses_once_each(self):
        self.assertIn("입찰자 입회 1 회", self.row(self.c101, "<th>FAT</th>"))
        sat = self.row(self.c101, "<th>SAT</th>")
        self.assertIn("입찰자 입회 1 회", sat)
        self.assertIn("발주자가 시험 패널(로트 A · B)과 유틸리티를 댄다", sat)

    def test_a_retest_follows_the_cause(self):
        retest = self.row(self.c101, "<th>재시험</th>")
        self.assertIn("4.2항 합동 원인분석", retest)
        self.assertIn("설계 원인이면 입찰자가 도면 정정과 재입회를 부담", retest)

    def test_witnessing_is_priced_in_the_service_period(self):
        weeks = re.search(r"착수지시일\(NTP\)로부터 (\d+)주", self.text).group(1)
        self.assertIn(f"용역기간({weeks}주) 뒤에 오더라도 인건비는 대가에 포함", self.p101)
        self.assertIn("여비·체재비만 실비", self.p101)

    def test_more_support_is_the_optional_item(self):
        self.assertIn("12.5항 7", self.p101)
        items = re.findall(r"<li>(.*?)</li>", clause(self.html, "12.5"), re.S)
        self.assertIn("10.1항 FAT·SAT 입회 각 1 회를 넘는", plain(items[6]),
                      "12.5 의 7 번째 항목이 10.1 입회를 넘는 지원이 아니다")


class TestTheOwnerSideOfTheUnmannedRun(_Rfq):
    """무인 운전의 경계 — 발주자 설비는 발주자가 지키고, 카트는 발주자가 뺀다 (6.6)."""

    def setUp(self):
        self.c66 = self.cl("6.6")
        self.console = CONSOLE.read_text(encoding="utf-8")

    def test_the_agv_dock_left_with_the_roll(self):
        self.assertEqual(self.html.count("AD-101"), 1, "AD-101 이 은퇴 문장 밖에도 남았다")
        self.assertIn("롤을 받던 AGV 도킹 AD-101 도 함께 빠졌다", self.c66)
        self.assertIn("KC-101 · RH-201 · PL-101/201 인터페이스",
                      self.row(clause(self.html, "3.3"), "무인 연속운전"))

    def test_the_pallet_machines_are_guarded_by_their_owner(self):
        self.assertIn("PL-101/201 의 방호는 발주자 몫이다", self.c66)
        self.assertIn("PL-101 디스태커 · PL-201 스태커", self.row(clause(self.html, "3.4"), "<th>팔레타이징</th>"),
                      "3.4 가 PL-101/201 을 발주자 설비로 넘기지 않았다")
        for dev in ("LC-001/002", "BJ-102", "ISO 13857"):
            self.assertIn(dev, self.c66)
        for dev in ("'LC-001'", "'LC-002'", "BJ-102"):
            self.assertIn(dev, self.console, f"사양서가 부르는 {dev} 가 콘솔에 없다")

    def test_the_cart_numbers_are_the_console_numbers(self):
        panels = round(c("CS_STACK") / c("CE_PITCH"))
        hours = panels / CY.NET_TARGET
        self.assertIn(f"카트 하나 {panels} 장 · {hours:.1f} h", self.c66)
        self.assertIn("csCartPanels()/MODEL.netTarget).toFixed(1)", self.console,
                      "콘솔이 카트 시간을 다른 식으로 센다")

    def test_the_swap_fits_the_availability_budget(self):
        budget = (1 - CY.AVAILABILITY) * 3600                      # s/h
        self.assertIn(f"시간당 {budget:.0f} s", self.c66)
        swap = int(re.search(r"교체는 (\d+) 분 안에", self.c66).group(1)) * 60
        hours = round(c("CS_STACK") / c("CE_PITCH")) / CY.NET_TARGET
        self.assertLess(swap / hours, budget,
                        "카트 교체만으로 가동률 예산을 다 쓴다 — 5 분 교체가 성립하지 않는다")

    def test_the_cart_is_taken_by_fork_not_by_a_trolley_we_have_not_seen(self):
        self.assertIn("지게차 포크 포켓(4면 진입)", self.c66)
        self.assertIn("발주자 물류가 방책 밖에서 바꾼다", self.c66)


class TestThePriceIsComparedWithTreatment(_Rfq):
    """두 가격을 받으면 어느 쪽으로 매기는지까지 정해야 한다 (12.7 · OI-15)."""

    def setUp(self):
        self.c127 = self.cl("12.7")

    def test_the_score_uses_the_inclusive_price(self):
        self.assertIn("최저 제안가 기준 상대평가 — 후처리 포함 가격", self.c127)
        self.assertIn("가격 점수는 후처리 포함 가격으로 매긴다 (OI-15)", self.c127)

    def test_the_open_item_points_to_the_rule(self):
        oi = plain(re.search(r"<b>OI-15</b>.*?</div>\s*</div>", self.html, re.S).group(0))
        self.assertIn("평가는 포함 가격으로 한다(12.7항)", oi)

    def test_the_option_has_a_unit_rate_and_a_deadline(self):
        self.assertIn("M-016 설계의 투입 인월 × 본체와 같은 인월 단가", self.c127)
        self.assertIn("60 % 단계 검토가 끝나기 전까지", self.c127)
        self.assertIn("12.8항 계약 변경", self.c127)
        self.assertIn("계약 변경", self.row(clause(self.html, "12.8"), "<th>계약 변경</th>"))
        self.assertIn("60 %", self.row(clause(self.html, "9.4"), "중간 검토"))


class TestTheContractTermsAreComplete(_Rfq):
    """비밀유지는 언제 시작하는지, 책임은 어디까지인지 (12.8)."""

    def setUp(self):
        self.c128 = clause(self.html, "12.8")

    def test_confidentiality_starts_when_the_material_is_handed_over(self):
        nda = self.row(self.c128, "<th>비밀유지</th>")
        self.assertIn("선행자료 수령일(보안서약서 제출일)에 시작", nda)
        self.assertIn("선정 통보 후 14일 안에 선행자료를 반납하거나 폐기", nda)
        self.assertIn("선정 통보일부터 3년간 존속", nda)
        self.assertIn("보안서약서 제출 후", self.text, "선행자료가 서약서 없이 나간다")

    def test_the_liability_has_a_cap_and_its_exceptions(self):
        cap = self.row(self.c128, "<th>책임 한도</th>")
        for token in ("계약금액을 한도로 한다", "간접·결과 손해는 배상하지 않는다",
                      "고의·중과실", "제3자 지식재산권 침해", "비밀유지 위반에는 한도를 두지 않는다",
                      "전문인 배상책임보험"):
            self.assertIn(token, cap)


class TestTheKnifeReturnIsTheSteppedStroke(_Rfq):
    """복귀 행정은 패널 길이 + 계단 깊이다 — 탠덤 간격 300 의 자리가 아니다 (4.1)."""

    def test_the_return_stroke(self):
        stroke = (c("PANEL_L") + c("KNIFE_DEPTH")) * 1000
        self.assertIn(f"나이프 복귀({stroke:,.0f} mm)", self.cl("4.1"))
        self.assertNotIn("2,800 mm", self.cl("4.1"))


if __name__ == "__main__":
    unittest.main()
