"""DG-HK60 상세설계 발주 기술사양서(docs/dg-hk60-rfq.html) 검증.

이 문서는 밖으로 나간다. 입찰자가 여기 적힌 수치로 견적을 내고 설계를 시작하므로,
콘솔이 계산하는 값과 사양서에 적힌 값이 갈라지면 그대로 손해가 된다. 사양서는
사람이 손으로 적은 문서라 갈라져도 화면상으로는 아무 표시가 나지 않는다.

그래서 여기서는 사양서의 수치를 파싱해 콘솔의 검증된 모델(test_pv_console_calculator)
및 콘솔의 전기부하표와 직접 대조한다. 사양서만 고치거나 콘솔만 고치면 실패한다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import console_consts                                        # noqa: E402

from .test_drawings import standalone_document_checks
from .test_pv_console_calculator import DECKS, thermal_model, sixty_panel_run

ROOT = pathlib.Path(__file__).resolve().parents[1]
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
TITLE = "DG-HK60 상세설계 기술사양서 · RFQ"


class TestRfqDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지 — 다른 도면들과 같은 규약을 쓴다."""

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")

    def test_standalone_document(self):
        standalone_document_checks(self, self.html, TITLE)

    def test_clauses_are_citable(self):
        """입찰자는 '4.3항' 으로 인용한다. 번호가 장식이 아니라 주소다."""
        sections = re.findall(r'<section id="(c\d+)">', self.html)
        self.assertEqual(
            sections, [f"c{n}" for n in range(1, 13)],
            "조항 절이 1~12 로 이어지지 않는다",
        )
        # 목차의 모든 링크가 실제 절을 가리키는지
        for target in re.findall(r'href="#(c\d+)"', self.html):
            self.assertIn(
                f'<section id="{target}">', self.html,
                f"목차가 존재하지 않는 조항 {target} 을 가리킨다",
            )

    def test_open_items_are_numbered_and_actionable(self):
        """확인사항은 번호가 있어야 제안서에서 항목별로 답할 수 있다."""
        ids = re.findall(r"<b>(OI-\d+)</b>", self.html)
        self.assertGreaterEqual(len(ids), 10, "확인사항이 10건 미만이다")
        self.assertEqual(len(ids), len(set(ids)), "확인사항 번호가 중복된다")
        nums = [int(i.split("-")[1]) for i in ids]
        self.assertEqual(
            nums, sorted(nums),
            "확인사항이 번호 순으로 놓여 있지 않다: %s\n"
            "입찰자는 목록을 번호로 훑는다 — 순서가 흐트러지면 항목을 빠뜨린다"
            % ids)
        self.assertEqual(
            nums, list(range(1, len(nums) + 1)),
            "확인사항 번호에 빈 자리가 있다: %s" % ids)
        # 각 항목이 현황과 해소 방법을 모두 갖는지
        for block in re.findall(r'<div class="oi">(.*?)</div>\s*</div>', self.html, re.S):
            oid = re.search(r"<b>(OI-\d+)</b>", block).group(1)
            self.assertEqual(
                block.count("<em>현황</em>"), 1, f"{oid} 에 현황이 없다"
            )
            self.assertEqual(
                block.count("<em>해소</em>"), 1, f"{oid} 에 해소 방법이 없다"
            )

    def test_the_module_table_is_the_delivered_scope_not_the_prior_revision(self):
        """표는 값을 매기는 목록이다 — 값이 없는 행은 목록에 없어야 한다.

        한동안 Rev.20 의 17 모듈을 전부 싣고 넷(M-010 VOC · M-014 데이터 ·
        M-015 팔레타이징 · M-016 RTO)에 '공급범위 밖' 을 달아 두었다. 빠진
        것을 입찰자가 알아야 한다는 이유였는데, 값이 '—' 인 행은 어느 쪽으로든
        오해를 만든다. 발주자 결정으로 넷을 뺐다.

        빼면서 잃으면 안 되는 것이 둘이다. 하나는 번호다 — M-001 부터 연번으로
        다시 매기면 넷이 있었다는 사실이 지워진다. 번호의 구멍이 그 자리를
        지킨다. 다른 하나는 경계다 — 표가 말하지 않게 됐으므로 3.4항과 M-017
        이 대신 말해야 한다. 인터록은 넘어가지 않았기 때문이다.
        """
        rows = re.findall(r'<tr><td class="k">(M-\d+)</td>', self.html)
        self.assertEqual(len(rows), len(set(rows)), "모듈 번호가 중복된다")
        nums = sorted(int(r.split("-")[1]) for r in rows)
        gone = [10, 14, 15, 16]
        self.assertEqual(nums, [n for n in range(1, 18) if n not in gone],
                         "표가 납품 13 모듈이 아니다: %s" % rows)
        # 번호를 다시 매기면 안 된다 — 구멍이 정보다
        self.assertNotIn(17, [n for n in nums if n > 13],
                         "번호를 연번으로 다시 매겼다") if len(nums) != 13 else None
        self.assertIn(17, nums, "M-017 경계 인터페이스반이 표에서 사라졌다")
        # 뺀 넷은 표의 행으로 다시 나타나면 안 된다
        for out in ("M-010", "M-014", "M-015", "M-016"):
            self.assertNotIn(f'<tr><td class="k">{out}</td>', self.html,
                             f"{out} 이 다시 표의 행으로 들어왔다")
        # 값이 없는 행이 모듈표에 남아 있으면 안 된다
        table = re.search(r"<caption>납품 모듈.*?</table>", self.html, re.S)
        self.assertIsNotNone(table, "납품 모듈표를 찾지 못했다")
        self.assertNotIn('<td class="num">—</td>', table.group(0),
                         "치수가 '—' 인 행이 모듈표에 남아 있다")
        self.assertNotIn("<tfoot", table.group(0),
                         "모듈표에 공급범위 밖 꼬리가 남아 있다")
        # 표가 말하지 않게 된 경계를 문장과 3.4 항이 대신 말해야 한다
        self.assertIn("이 표에 없는 것은 공급범위에 없다", self.html,
                      "표의 범위를 문장으로 못 박지 않았다")
        boundary = re.search(r"<caption>공급범위 경계 3개소</caption>.*?</table>",
                             self.html, re.S)
        self.assertIsNotNone(boundary, "3.4 경계 표가 사라졌다")
        for term in ("VOC_ABATE_READY", "SHREDDER_READY", "STACK_PRESENT"):
            self.assertIn(term, boundary.group(0),
                          f"{term} — 설비를 넘겨도 인터록은 넘기지 않는다는 것이 "
                          "경계 표에서 사라졌다")
        # 그리고 Rev.20 모듈표를 그대로 쓰지 않는다는 경고는 남아야 한다
        self.assertIn("납품 기계에\n      존재하지 않는다", self.html.replace("</strong>", ""),
                      "Rev.20 모듈표를 그대로 쓰지 않는다는 경고가 없다")

    def test_the_expansion_clause_matches_the_parallel_study(self):
        """1.4 가 요구하는 확장 여지는 검토서가 실제로 계산한 값이어야 한다.

        확장 여지는 치수로만 지켜진다. 사양서가 검토서보다 좁은 값을 적으면
        상세설계가 그 좁은 값으로 굳고, 확장은 재설계가 된다.
        """
        study = (ROOT / "docs" / "dg-hk120-twin-cell.html").read_text(encoding="utf-8")
        clause = re.search(
            r'<div class="n">1\.4</div>(.*?)</div></div>', self.html, re.S)
        self.assertIsNotNone(clause, "1.4 장래 확장 조항이 없다")
        body = clause.group(1)
        self.assertIn("수평", body, "확장이 수평 병렬임을 밝히지 않았다")
        self.assertIn("DG-HK120C", body)
        self.assertIn("dg-hk120-twin-cell.html", body, "검토서 경로를 대지 않았다")
        self.assertIn("범위 밖", body, "확장 설계가 본 용역 밖임을 못 박지 않았다")

        decks = re.search(r"<span class=\"m\">(\d+) → (\d+)</span>단", body)
        self.assertIsNotNone(decks, "확장 시 단수를 밝히지 않았다")
        base = int(re.search(r"const DECKS=(\d+)",
                             CONSOLE.read_text(encoding="utf-8")).group(1))
        self.assertEqual(int(decks.group(1)), base,
                         f"확장의 출발 단수가 납품 표준({base}단)과 다르다")
        self.assertEqual(decks.group(2), "7",
                         "검토서가 고른 단수는 7 단이다")
        self.assertIn("decks:7", CONSOLE.read_text(encoding="utf-8").replace(" ", ""),
                      "콘솔의 확장 배치가 7 단이 아니다")

        aisle = re.search(r'셀 사이 통로 <span class="m">([\d,]+) mm</span>', body)
        self.assertIsNotNone(aisle, "셀 사이 통로 폭을 밝히지 않았다")
        self.assertIn("EX-101", body, "통로 폭을 정하는 장치를 대지 않았다")
        self.assertEqual(aisle.group(1), "2,760",
                         "통로 폭이 EX-101 포탈에서 나온 2,760 mm 가 아니다")
        self.assertIn("aisleFork", study,
                      "검토서가 포크 포탈로 통로를 유도하지 않는다")

    def test_the_handed_over_console_revision_is_the_one_on_disk(self):
        """사양서가 인계한다고 적은 개정과 콘솔이 스스로 붙이는 개정이 같아야 한다.

        둘이 갈리면 입찰자는 자기가 받은 파일이 사양서가 말하는 그 파일인지
        확인할 방법이 없다 — 개정 표기는 인계물의 신원이다.
        """
        console = CONSOLE.read_text(encoding="utf-8")
        stated = re.findall(r"REV\.\d+[A-Z]?", self.html)
        head = re.search(r"<dt>선행자료</dt><dd>(REV\.\d+[A-Z]?)", self.html)
        self.assertIsNotNone(head, "머리말에 인계 개정이 없다")
        self.assertIn("rev:'%s'" % head.group(1),
                      console.replace(" ", ""),
                      "머리말이 적은 %s 를 콘솔이 쓰지 않는다" % head.group(1))
        self.assertIn("개념설계(%s) 결과" % head.group(1), self.html,
                      "꼬리말의 개정이 머리말과 다르다")
        # 폐기된 선행 개정을 인용할 때는 그것이 폐기된 것임을 밝힌다.
        if "REV.20" in stated:
            self.assertIn("폐기된 선행 개정", self.html,
                          "REV.20 을 인용하면서 그것이 폐기된 개정임을 밝히지 않았다")

    def test_states_what_the_handed_over_drawings_are_worth(self):
        """입찰자가 가장 먼저 알아야 할 사실이다. 빠지면 견적이 틀어진다.

        한동안 이 자리는 "선행자료에는 제작도면이 없다" 였다. 콘솔이 제작수준
        표기를 갖춘 시트를 담게 되면서 그 문장이 거짓이 되었는데, 그렇다고
        "제작도가 있다" 도 참이 아니다 — 해석으로 검증되지 않은 가정값이다.
        그래서 성격을 규정하는 쪽으로 바꿨다.
        """
        self.assertIn("참고도(Not For Construction)", self.html,
                      "인계 도면의 성격을 규정하지 않았다")
        self.assertIn("제작 착수\n      도면이 아니다".replace("\n      ", " "),
                      re.sub(r"\s+", " ", self.html),
                      "참고도가 제작 착수 도면이 아님을 밝히지 않았다")
        self.assertIn("부품도", self.html)
        self.assertIn("검증·확정은 본 용역의 범위에 속한다", self.html,
                      "도면 확정이 용역 범위임을 밝히지 않았다")

    def test_cites_the_governing_standards(self):
        for std in ("ISO 12100", "ISO 13849-1", "ISO 13855",
                    "ISO 14119", "ISO 14120", "ISO 7010", "IEC 60204-1"):
            self.assertIn(std, self.html, f"{std} 인용이 없다")


class TestRfqFiguresMatchTheConsole(unittest.TestCase):
    """사양서의 수치가 콘솔의 계산 및 부하표와 일치하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")
        cls.console = CONSOLE.read_text(encoding="utf-8")
        cls.m = thermal_model()
        cls.run60 = sixty_panel_run(cls.m)

    def _num(self, pattern):
        m = re.search(pattern, self.html)
        self.assertIsNotNone(m, f"사양서에서 수치를 찾지 못했다: {pattern}")
        return float(m.group(1).replace(",", ""))

    # ── 성능 ────────────────────────────────────────────────────────
    def test_nominal_throughput(self):
        self.assertAlmostEqual(
            self._num(r"명목 처리량</th><td class=\"num\">([\d.]+) 장/h"),
            self.m["line_rate"], delta=0.05,
        )

    def test_guaranteed_throughput_is_the_derated_rate(self):
        stated = self._num(r"보증 처리량</th><td class=\"num\">([\d.]+) 장/h")
        self.assertLessEqual(
            stated, self.m["line_rate"] * 0.9 + 0.05,
            "보증 처리량이 90% 가동률 환산값을 넘는다 — 달성 불가능한 보증이다",
        )

    def test_line_cycle(self):
        self.assertAlmostEqual(
            self._num(r"라인 사이클</th><td class=\"num\">([\d.]+) s/장"),
            self.m["cycle_s"], delta=0.05,
        )

    def test_thermal_limit_and_margin(self):
        self.assertAlmostEqual(
            self._num(r"열공정 한계</th><td class=\"num\">([\d.]+) 장/h"),
            self.m["thermal_rate"], delta=0.05,
        )
        margin = (
            (self.m["thermal_rate"] - self.m["line_rate"]) / self.m["thermal_rate"] * 100
        )
        self.assertAlmostEqual(
            self._num(r"열공정 한계</th><td class=\"num\">[\d.]+ 장/h</td><td>여유 ([\d.]+) %"),
            margin, delta=0.05,
        )

    def test_shift_output(self):
        self.assertAlmostEqual(
            self._num(r"8 h 생산량</th><td class=\"num\">약 ([\d,]+) 장"),
            self.m["line_rate"] * 8 * 0.9, delta=0.5,
        )
        self.assertAlmostEqual(
            self._num(r"16 h 생산량</th><td class=\"num\">약 ([\d,]+) 장"),
            self.m["line_rate"] * 16 * 0.9, delta=0.5,
        )

    # ── 열수지 ──────────────────────────────────────────────────────
    def test_heat_per_panel_and_dwell(self):
        self.assertAlmostEqual(
            self._num(r"→ ([\d.]+) MJ/장"), self.m["q_kj"] / 1000, places=2
        )
        self.assertAlmostEqual(
            self._num(r"113\.15 s \)\s*= ([\d.]+) s"), self.m["dwell_s"], delta=0.05
        )
        self.assertAlmostEqual(
            self._num(rf"피치\s*= t_열 / {DECKS} = ([\d.]+) s/장"),
            self.m["pitch_s"], delta=0.05,
        )

    def test_model_constants_match_the_console(self):
        """상수를 사양서에 옮겨 적으면서 틀리면 입찰자가 다른 설비를 설계한다."""
        target = float(re.search(r"const T_TARGET=([\d.]+);", self.console).group(1))
        amb = float(re.search(r"const T_AMB=([\d.]+);", self.console).group(1))
        for literal in ("8.7359", "113.15", f"{round(target - amb)}"):
            self.assertIn(literal, self.html, f"열모델 상수 {literal} 이 사양서에 없다")
        self.assertIn(f"{round(target)}", self.html, "사양서가 계면 목표온도를 말하지 않는다")
        # 콘솔의 실제 상수와 대조 (사양서는 반올림 표기)
        areal = float(re.search(r"arealCp:([\d.]+)", self.console).group(1))
        self.assertAlmostEqual(
            self._num(r"([\d.]+) kJ/\(m²·K\)"), areal, places=4,
            msg="사양서의 면적열용량이 콘솔과 다르다",
        )

    def test_knife_cycle_terms_add_up(self):
        """사양서에 적힌 항별 값이 실제로 합계가 되는지 — 첫 항은 (계단 깊이 + 패널) / 속도."""
        a = self._num(r"= ([\d.]+) \+ 1\.50 \+ 3\.00")
        total = self._num(r"= [\d.]+ \+ 1\.50 \+ 3\.00 = ([\d.]+) s/장")
        self.assertAlmostEqual(a + 1.50 + 3.00, total, delta=0.02)
        self.assertAlmostEqual(total, self.m["cycle_s"], delta=0.05)

    # ── 전기 ────────────────────────────────────────────────────────
    def _load_schedule(self):
        """콘솔 부하표. kW 는 램프 수에서 나온 식일 수 있어 풀어 읽는다."""
        rows = re.findall(
            r"\{\s*id:'([^']+)'\s*,\s*load:[`'][^`']*[`']\s*,"
            r"\s*kW:([\w.*+/ -]+?)\s*,\s*pf:([\d.]+)\s*,"
            r"(?:\s*df:[\d.]+\s*,)?\s*mccb:'([^']+)'\s*\}",
            self.console,
        )
        self.assertGreaterEqual(len(rows), 4, "콘솔 부하표를 찾지 못했다")
        env = console_consts.env(self.console)
        out = []
        for ident, kw, pf, mccb in rows:
            v = console_consts.value(kw, env)
            self.assertIsNotNone(v, f"{ident} 의 kW '{kw}' 를 읽지 못했다")
            out.append((ident, v, pf, mccb))
        return out

    def test_load_schedule_rows_match_the_console(self):
        for ident, kw, pf, mccb in self._load_schedule():
            self.assertIn(ident, self.html, f"{ident} 분기가 사양서에 없다")
            row = re.search(
                rf'{re.escape(ident)}</td>.*?</tr>', self.html, re.S
            )
            self.assertIsNotNone(row, f"{ident} 행을 사양서에서 찾지 못했다")
            self.assertIn(f"{kw:g}", row.group(0), f"{ident} 의 kW 가 콘솔과 다르다")
            self.assertIn(f"{float(pf):.2f}", row.group(0),
                          f"{ident} 의 역률이 콘솔과 다르다")
            self.assertIn(mccb, row.group(0), f"{ident} 의 차단기가 콘솔과 다르다")

    def test_full_load_current_matches_the_phasor_sum(self):
        rows = self._load_schedule()
        volts = int(re.search(r"const LINE_V=(\d+)", self.console).group(1))
        active = sum(kw for _, kw, _, _ in rows)
        reactive = sum(
            kw * math.tan(math.acos(float(pf))) for _, kw, pf, _ in rows
        )
        apparent = math.hypot(active, reactive)
        fla = apparent * 1000 / (3 ** 0.5 * volts)

        self.assertAlmostEqual(self._num(r"FLA ([\d.]+) A"), round(fla), delta=0.5)
        self.assertAlmostEqual(self._num(r"([\d.]+) kVA"), apparent, delta=0.05)
        self.assertAlmostEqual(
            self._num(rf"class=\"num\">([\d.]+)</td><td class=\"num\">{fla:.1f}"),
            active / apparent, delta=0.001,
        )

    def test_breaker_headroom_claim_is_true(self):
        """'nnnAT 기준 n배 여유' 는 검산 가능한 주장이다.

        정격을 시험에 박아 두면 부하표가 바뀌어 차단기를 다시 골랐을 때
        시험이 옛 정격을 계속 찾는다. 정격도 배수도 문서에서 읽는다.
        """
        m = re.search(r"(\d+)AT 기준 ([\d.]+)배 여유", self.html)
        self.assertIsNotNone(m, "주차단기 여유 주장을 찾지 못했다")
        at, claimed = int(m.group(1)), float(m.group(2))
        rows = self._load_schedule()
        volts = int(re.search(r"const LINE_V=(\d+)", self.console).group(1))
        active = sum(kw for _, kw, _, _ in rows)
        reactive = sum(
            kw * math.tan(math.acos(float(pf))) for _, kw, pf, _ in rows
        )
        fla = math.hypot(active, reactive) * 1000 / (3 ** 0.5 * volts)
        self.assertAlmostEqual(claimed, at / fla, delta=0.01)
        self.assertGreaterEqual(at, fla * 1.25, f"주차단기 {at}AT 가 FLA 의 1.25배에 못 미친다")
        self.assertGreater(claimed, 1.0, "차단기 정격이 전부하전류보다 작다")

    # ── 모듈 구성 ────────────────────────────────────────────────
    def test_module_table_matches_the_console_assemblies(self):
        """사양서의 M-0xx 표는 콘솔의 납품 모듈 목록과 같은 근거를 써야 한다.

        치수가 값에서 식으로 바뀌었으므로 문자열 대조는 성립하지 않는다.
        대신 배치 상수에서 길이를 다시 계산해 사양서가 적은 숫자와 맞춘다 —
        한쪽만 고치면 입찰자가 실물과 다른 외형으로 반입계획을 잡는다.
        """
        c = console_consts.const
        panel_l, deck_l, carrier_l = c("PANEL_L"), c("DECK_L"), c("CARRIER_L")
        clear, wall, door, park = (c("CL_CLEAR"), c("CL_WALL"),
                                   c("CL_DOOR"), c("CL_PARK"))
        want = {
            "M-001": panel_l + 2 * clear,
            "M-002": deck_l + 2 * wall + door,
            "M-005": carrier_l + 2 * park,
            "M-007": deck_l + 2 * clear,
            "M-013": c("CFENCE_X1_SPAN") if False else None,   # 방책은 아래에서 따로
        }
        rfq_rows = dict(
            (m.group(1), m.group(2))
            for m in re.finditer(
                r'<td class="k">(M-\d+)</td><td>[^<]+</td>'
                r'<td class="num">(\d+)×', self.html)
        )
        for ident, metres in want.items():
            if metres is None:
                continue
            self.assertIn(ident, rfq_rows, f"{ident} 행이 사양서에 없다")
            self.assertAlmostEqual(
                int(rfq_rows[ident]), round(metres * 1000), delta=1,
                msg=f"{ident} 의 길이가 배치 상수({metres*1000:.0f})와 다르다")
        # 방책은 스테이션이 아니라 방책선에서 나온다
        self.assertIn("M-013", rfq_rows)
        env = console_consts.env(self.console)
        cst = env["CST"]
        compact = (sum(getattr(cst, k).w for k in ("LD", "HC", "DL", "GC", "UL"))
                   + 4 * env["CL_CLEAR"] + 2 * env["CL_END"])
        self.assertEqual(int(rfq_rows["M-013"]), round((compact + .84 - env["CFENCE_X0"]) * 1000),
                         "방책 길이가 −900 → 전장 + 840 과 다르다")
        # 그리고 콘솔의 표는 값이 아니라 식이어야 한다
        flat = self.console.replace(" ", "")
        for expr in ("size:dim(CST.LD.w,", "size:dim(CST.HC.w,",
                     "size:dim(CST.DL.w,", "size:dim(CST.GC.w,",
                     "size:dim(CFENCE_X1-CFENCE_X0,"):
            self.assertIn(expr, flat, f"콘솔 모듈표가 {expr} 를 쓰지 않는다")

    # ── 권취부 철거 ──────────────────────────────────────────────
    def test_the_winder_is_retired_not_left_half_specified(self):
        """권취부가 빠졌는데 롤 설계값 표가 남아 있으면 입찰자가 그것을 견적한다."""
        clause = re.search(r'<h3>셀모듈 인출 — 권취부는 없다</h3>(.*?)</div></div>', self.html, re.S)
        self.assertIsNotNone(clause, "6.4 가 권취부 철거를 말하지 않는다")
        body = clause.group(1)
        self.assertIn("철거", body)
        self.assertIn("설계·견적하지 않는다", body, "빠진 설비를 견적하지 말라는 말이 없다")
        for gone in ("권취 롤 설계값", "만권 롤 반출 경로", "반출 통로 검토", "롤 교체 주기</th>"):
            self.assertNotIn(gone, self.html, f"철거한 권취부의 '{gone}' 가 사양서에 남아 있다")

    def test_the_press_plate_is_specified(self):
        """권취가 하던 일 — 떼어 낸 층을 붙드는 일 — 은 누름판이 맡는다."""
        clause = re.search(r'<h3>셀모듈 인출 — 권취부는 없다</h3>(.*?)</div></div>', self.html, re.S)
        body = clause.group(1)
        self.assertIn("HD-101", body)
        self.assertIn("가열하지 않는다", body, "누름판이 비가열이라는 요구가 없다 — 백시트가 닿는 유일한 면이다")
        self.assertIn("계단 이음", body, "이음 줄의 박리 품질이 요구되지 않았다")
        self.assertIn("PT-10", body, "누름판 예압을 닫을 시험을 대지 않았다")
        c = console_consts.const
        self.assertIn(f"{c('CHD_L')*1000:,.0f} mm", body, "누름판 길이가 콘솔 CHD_L 과 다르다")

    def test_the_roll_item_is_closed_not_deleted(self):
        """OI-11 을 지우면 번호가 당겨지고, 제안서의 답이 엉뚱한 항목을 가리킨다."""
        block = re.search(r"<b>OI-11</b>(.*?)</div>\s*</div>", self.html, re.S)
        self.assertIsNotNone(block, "OI-11 자리가 사라졌다")
        body = block.group(1)
        self.assertIn("닫혔다", body)
        self.assertIn("번호는 당기지 않는다", body)

    # ── 계단 칼날의 물림 ──────────────────────────────────────────
    def test_the_bite_ramp_is_arithmetic(self):
        """물린 폭은 중앙 + 80 mm 마다 한 단 — 콘솔 형상에서 나온다."""
        import knife_stepped as KS
        s = KS.summary()
        widths = " → ".join(f"{w:,.0f}" for w in s["ramp_widths"])
        self.assertIn(widths, self.html, f"사양서의 물림 램프가 형상과 다르다 ({widths})")
        self.assertIn(f"{s['ramp_time']:.2f} s", self.html, "네 계단이 끝나는 시간이 계산과 다르다")
        c = console_consts.const
        self.assertIn(f"깊이 <span class=\"m\">{c('KNIFE_DEPTH')*1000:.0f} mm</span>", self.html)
        self.assertIn(f"전폭 <span class=\"m\">{c('KNIFE_W')*1000:,.0f} mm</span>", self.html)

    def test_the_z_axes_sit_where_the_analysis_put_them(self):
        """베셀점은 해석의 결론이다 — 사양서가 다른 자리를 적으면 해석이 무효가 된다."""
        y = console_consts.const("CZS_Y") * 1000
        self.assertIn(f"y ±{y:.0f} mm", self.html, "Z축 위치가 콘솔 CZS_Y 와 다르다")
        self.assertIn("S10", self.html, "Z축 위치의 근거(CAL-001 S10)를 대지 않았다")

    def test_vacuum_hold_requirement_is_computed_from_the_thrust_range(self):
        """A ≥ 2F/(μ·Δp) — 탠덤 시절의 2 는 두 칼날의 합이었고, 계단 칼날에서는
        같은 식의 2 가 흡착 안전율이다. 식을 바꾸면 패드 배치가 절반으로 줄어든다."""
        block = re.search(r"<b>OI-13</b>(.*?)</div>\s*</div>", self.html, re.S)
        self.assertIsNotNone(block, "진공 유지력 확인사항이 없다")
        body = block.group(1)
        self.assertIn("A ≥ 2F / (μ·Δp)", body,
                      "필요 패드 면적 식이 2F 가 아니다 — 안전율 2 가 빠졌다")
        mu = float(re.search(r"μ = ([\d.]+)", body).group(1))
        dp = float(re.search(r"Δp = (\d+) kPa", body).group(1)) * 1000
        L, W = console_consts.const("PANEL_L"), console_consts.const("PANEL_W")
        glass = L * W
        scale = W / 1.2                                  # 밴드는 폭 1,200 에서 잰 값 — 포락선 폭으로 환산
        for thrust, area_pat, pct_pat in (
            (1.49e3 * scale, r"<span class=\"m\">([\d.]+) m²</span>\(", r"유리면의 ([\d.]+) %\)"),
            (13.37e3 * scale, r"상한[^<]*<span class=\"m\">[^<]*</span>[^<]*<span class=\"m\">([\d.]+) m²</span>",
             r"유리면의 <span class=\"m\">([\d.]+) %</span>"),
        ):
            want = 2 * thrust / (mu * dp)
            got = float(re.search(area_pat, body).group(1))
            self.assertAlmostEqual(got, want, delta=0.005,
                                   msg=f"{thrust/1000:.2f} kN 에서의 필요 패드 면적이 틀렸다")
            pct = float(re.search(pct_pat, body).group(1))
            self.assertAlmostEqual(pct, want / glass * 100, delta=0.15,
                                   msg=f"{thrust/1000:.2f} kN 에서의 유리면 대비 비율이 틀렸다")
        # 추력 범위는 OI-01 과 같은 값이어야 한다
        self.assertIn("1.49", self.html)
        self.assertIn("13.37", self.html)

    def test_blade_life_is_an_open_item_with_the_cut_length(self):
        block = re.search(r"<b>OI-12</b>(.*?)</div>\s*</div>", self.html, re.S)
        self.assertIsNotNone(block, "칼날 수명 확인사항이 없다")
        body = block.group(1)
        rate = float(re.search(r"(\d+) 장/h", body).group(1))
        cut = float(re.search(r"패널당 ([\d,]+) mm", body).group(1).replace(",", "")) / 1000
        got = float(re.search(r"시간당\s*<span class=\"m\">(\d+) m</span>", body).group(1))
        self.assertAlmostEqual(got, rate * cut, delta=0.5,
                               msg="시간당 절단 연장이 본문의 처리량 × 패널 길이와 다르다")
        # 본문이 근거로 든 처리량은 계약 처리량이다 — 모델 순생산(59.6)이 그 위에 있어야 한다
        self.assertAlmostEqual(rate, console_consts.const("NET_TARGET"), delta=0.5,
                               msg="칼날 수명 근거의 처리량이 계약 처리량과 다르다")
        self.assertGreaterEqual(self.m["line_rate"] * 0.9, rate,
                                "모델 순생산이 수명 근거의 처리량보다 낮다")
        shift = float(re.search(r"8 h 교대당 <span class=\"m\">([\d,]+) m</span>", body)
                      .group(1).replace(",", ""))
        self.assertAlmostEqual(shift, got * 8, delta=1)


class TestCassetteDischargeRoute(unittest.TestCase):
    """카세트 인출 포락선 — 사양서의 치수는 모두 콘솔 상수에서 나온 값이다.

    권취부가 빠지기 전에는 이 자리에 만권 롤 반출 경로(스키드 · 롤 포트 · 코너
    승강대)가 있었다. 계단 칼날이 칼날 폭을 1,640 → 1,500 으로 줄이자 외장과
    방책이 140 안으로 들어왔다 — 콘솔은 식이라 따라왔고, 손으로 적은 사양서는
    여기서 대조하지 않으면 옛 값으로 남는다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")
        cls.c = staticmethod(console_consts.const)

    def _block(self):
        m = re.search(r'<div class="logic">카세트 BC-201(.*?)</div>', self.html, re.S)
        self.assertIsNotNone(m, "6.9 인출 포락선 논리 블록이 없다")
        return m.group(1)

    def test_the_cassette_is_the_knife_width(self):
        c = console_consts.const
        blk = self._block()
        self.assertIn(f"{c('KNIFE_W')*1000:,.0f} mm (y축)", blk)
        self.assertIn(f"깊이 {c('CASS_ENV_X')*1000:.0f}", blk)
        self.assertIn(f"{c('CASS_MASS'):.0f} kg", blk)

    def test_the_blocked_floor_route_is_computed(self):
        """스윕 밖으로 빼면 외장을 뚫고, 남는 통로에 사람이 못 선다 — 값은 콘솔에서."""
        c = console_consts.const
        half = c("KNIFE_W") / 2
        centre = c("CGY") + half + .085
        outer = centre + half
        blk = self._block()
        self.assertIn(f"{centre*1000:,.0f}", blk, "스윕 밖 카세트 중심이 계산과 다르다")
        self.assertIn(f"{outer*1000:,.0f}", blk, "카세트 바깥 끝이 계산과 다르다")
        self.assertIn(f"외장 {c('CSKIN_Y')*1000:,.0f} 을 {(outer-c('CSKIN_Y'))*1000:.0f} 뚫는다", blk)
        gap = c("CFENCE_Y") - outer
        self.assertIn(f"방책 {c('CFENCE_Y')*1000:,.0f} = {gap*1000:.0f} mm", blk)
        self.assertLess(gap, .60, "통로가 600 을 넘으면 사람이 선다 — 전제가 바뀌었다")

    def test_the_magazine_and_envelope_match_the_console(self):
        c = console_consts.const
        y = c("CKC_Y") * 1000
        self.assertIn(f"Y −{abs(y):,.0f} · Z {c('CKC_Z')*1000:,.0f}", self.html, "매거진 위치가 콘솔과 다르다")
        half = c("KNIFE_W") / 2 * 1000
        self.assertIn(f"(Y −{abs(y)+half:,.0f} ~ +{half:,.0f})", self.html, "인출 포락선 범위가 콘솔과 다르다")
        self.assertIn(f"KC-301 (Y −{abs(c('CKC_RACK_Y'))*1000:,.0f})", self.html, "KC-301 위치가 콘솔과 다르다")

    def test_the_monorail_carries_only_the_cassette(self):
        self.assertIn("카세트 전용", self.html)
        self.assertNotIn("만권 롤과 같은 모노레일", self.html)


class TestVacuumPadLayout(unittest.TestCase):
    """OI-13 에 적은 패드 배치가 콘솔이 그리는 배치와 같은지.

    이 수치는 '이렇게 하면 된다'는 제안이 아니라 도면이 실제로 그렇게 그려져
    있다는 진술이다. 콘솔에서 패드 하나만 빼도 사양서의 1.29 배가 거짓이 된다.
    """

    MU, DP = 0.6, 65_000
    F_HI = console_consts.const("F_PEEL") * 1000          # 포락선 폭으로 환산한 OI-01 상한

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")
        cls.console = CONSOLE.read_text(encoding="utf-8")

    def _num(self, pattern):
        m = re.search(pattern, self.html)
        self.assertIsNotNone(m, f"사양서에서 수치를 찾지 못했다: {pattern}")
        return float(m.group(1).replace(",", ""))

    def _c(self, name):
        m = re.search(rf"(?:const|,)\s*{name}\s*=\s*(-?[\d.]+)[,;]", self.console)
        self.assertIsNotNone(m, f"콘솔 상수 {name} 없음")
        return float(m.group(1))

    def test_pad_grid_matches_the_console(self):
        cols, rows = int(self._c("PAD_COLS")), int(self._c("PAD_ROWS"))
        r = self._c("PAD_R")
        self.assertAlmostEqual(self._num(rf"<span class=\"m\">(\d+)열 × {rows}행"), cols, delta=0)
        self.assertAlmostEqual(self._num(rf"열 × (\d+)행 = {cols*rows}패드"), rows, delta=0)
        self.assertAlmostEqual(self._num(r"= (\d+)패드 Ø250"), cols * rows, delta=0)
        self.assertAlmostEqual(self._num(r"패드 Ø(\d+)"), r * 2000, delta=0.5)

    def test_pad_area_and_margin_are_the_computed_ones(self):
        cols, rows, r = int(self._c("PAD_COLS")), int(self._c("PAD_ROWS")), self._c("PAD_R")
        area = cols * rows * math.pi * r ** 2
        need = 2 * self.F_HI / (self.MU * self.DP)
        self.assertAlmostEqual(self._num(r"패드 면적 <span class=\"m\">([\d.]+) m²"), area, delta=0.002)
        self.assertAlmostEqual(self._num(r"상한 요구\s*<span class=\"m\">([\d.]+) m²"), need, delta=0.002)
        # '배' 는 문서 곳곳에 나온다. 패드 여유 배수는 OI-13 안에서만 찾는다.
        oi13 = re.search(r"OI-13</b>.*?</div>\s*</div>", self.html, re.S)
        self.assertIsNotNone(oi13, "OI-13 블록을 찾지 못했다")
        self.assertAlmostEqual(
            float(re.search(r"<span class=\"m\">([\d.]+) 배</span>", oi13.group(0)).group(1)),
            area / need, delta=0.01)

    def test_pitch_and_clearances_come_from_the_panel(self):
        cols, rows, r = int(self._c("PAD_COLS")), int(self._c("PAD_ROWS")), self._c("PAD_R")
        length, width = self._c("PANEL_L"), self._c("PANEL_W")
        px, py = length / cols, width / rows
        self.assertAlmostEqual(self._num(rf"피치 <span class=\"m\">(\d+) × {round(py*1000)} mm"), px * 1000, delta=1)
        self.assertAlmostEqual(self._num(rf"피치 <span class=\"m\">{round(px*1000)} × (\d+) mm"), py * 1000, delta=1)
        gap = re.search(r"패드 간 여유\s*<span class=\"m\">(\d+) / (\d+) mm", self.html)
        self.assertIsNotNone(gap, "패드 간 여유(길이 / 폭)가 없다")
        self.assertAlmostEqual(float(gap.group(1)), (px - 2 * r) * 1000, delta=1)
        self.assertAlmostEqual(float(gap.group(2)), (py - 2 * r) * 1000, delta=1)
        edge = re.search(r"가장자리 여유\s*\n?\s*<span class=\"m\">(\d+) / (\d+) mm", self.html)
        self.assertIsNotNone(edge, "가장자리 여유(길이 / 폭)가 없다")
        self.assertAlmostEqual(float(edge.group(1)), (length / 2 - (cols - 1) / 2 * px - r) * 1000, delta=1)
        self.assertAlmostEqual(float(edge.group(2)), (width / 2 - (rows - 1) / 2 * py - r) * 1000, delta=1)

    def test_the_assumption_behind_the_layout_is_stated(self):
        """μ 0.6 가정이 빠지면 이 배치가 무조건 성립하는 것처럼 읽힌다."""
        self.assertIn("μ = 0.6 가정에 걸려 있으므로", self.html,
                      "패드 배치가 어떤 가정 위에 서 있는지 적혀 있지 않다")


class TestProcurementTerms(unittest.TestCase):
    """12항 발주 조건의 수치가 서로 맞는지 확인한다.

    일정·기성·배점은 표 안에서 스스로 더해지는 값이다. 한 행만 고치고 합계를
    안 고치면 입찰자가 먼저 발견한다 — 그때는 사양서 전체의 신뢰가 깎인다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")
        start = cls.html.index('<section id="c12">')
        cls.c12 = cls.html[start:cls.html.index("</section>", start)]

    def _table(self, caption):
        m = re.search(
            rf"<caption>{re.escape(caption)}[^<]*</caption>(.*?)</table>",
            self.c12, re.S)
        self.assertIsNotNone(m, f"'{caption}' 표를 찾지 못했다")
        return m.group(1)

    @staticmethod
    def _cells(row):
        return [re.sub(r"<[^>]+>", "", c).strip()
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]

    def test_schedule_weeks_add_up(self):
        """소요의 누적합이 누적 열과 같고, 마지막 누적이 선언한 용역기간이다."""
        rows = re.findall(r"<tr>(.*?)</tr>", self._table("단계별 일정"), re.S)
        rows = [r for r in rows if "<td" in r]
        self.assertEqual(len(rows), 6, "일정 표가 6행이 아니다")
        total = 0
        for row in rows:
            c = self._cells(row)
            spent = int(re.search(r"(\d+)주", c[2]).group(1))
            cum = int(re.search(r"(\d+)주", c[3]).group(1))
            total += spent
            self.assertEqual(
                cum, total, f"'{c[0]}' 단계의 누적 {cum}주가 소요 합 {total}주와 다르다")
        declared = int(re.search(
            r"착수지시일\(NTP\)로부터 (\d+)주", self.c12).group(1))
        self.assertEqual(
            total, declared,
            f"단계 소요 합 {total}주가 선언한 용역기간 {declared}주와 다르다")

    def test_payment_shares_add_to_one_hundred(self):
        rows = re.findall(r"<tr>(.*?)</tr>", self._table("기성 구분"), re.S)
        rows = [r for r in rows if "<th>" in r and "<td" in r]
        self.assertEqual(len(rows), 5, "기성이 5회가 아니다")
        total = 0
        for row in rows:
            c = self._cells(row)
            share = int(re.search(r"(\d+) %", c[2]).group(1))
            running = int(re.search(r"(\d+) %", c[3]).group(1))
            total += share
            self.assertEqual(
                running, total, f"'{c[0]}' 의 누계 {running} % 가 합 {total} % 와 다르다")
        self.assertEqual(total, 100, f"기성 비율 합이 {total} % 다")

    def test_evaluation_points_add_to_one_hundred(self):
        rows = re.findall(r"<tr>(.*?)</tr>", self._table("평가 배점"), re.S)
        points = [int(m.group(1)) for r in rows if "<td" in r
                  for m in [re.search(r'class="num">(\d+)<', r)] if m]
        # 마지막은 tfoot 의 합계
        self.assertEqual(points[-1], 100, "배점 합계가 100 이 아니다")
        self.assertEqual(
            sum(points[:-1]), points[-1],
            f"항목 배점 합 {sum(points[:-1])} 이 합계 {points[-1]} 과 다르다")
        tech = re.search(r"기술 <span class=\"m\">(\d+)</span>", self.c12)
        price = re.search(r"가격 <span class=\"m\">(\d+)</span>", self.c12)
        self.assertIsNotNone(tech, "기술 배점 선언이 없다")
        self.assertEqual(
            int(tech.group(1)) + int(price.group(1)), 100,
            "기술·가격 배점 선언이 100 이 아니다")
        self.assertEqual(
            sum(points[:-2]), int(tech.group(1)),
            "기술 항목 배점 합이 선언한 기술 배점과 다르다")

    def test_open_item_count_matches_the_register(self):
        """12항의 'N건' 은 11항에서 아직 열린 항목을 센 수다.

        항목이 늘어도, 하나가 닫혀도 여기가 따라 틀린다. 닫힌 항목은 번호를
        당기지 않고 제목에 '해소' 를 달아 남기므로(OI-11) 등록 수에서 그만큼 뺀다.
        태그를 걷어 내고 세는 것은 '<strong>15건</strong>' 처럼 강조가 끼어도
        검사에서 빠지지 않게 하려는 것이다 — 세 곳 중 한 곳만 보던 때가 있었다.
        """
        titles = re.findall(
            r'<div class="oi-h"><b>OI-\d+</b><span>(.*?)</span>', self.html)
        self.assertEqual(len(titles), len(re.findall(r"<b>(OI-\d+)</b>", self.html)))
        closed = sum("해소" in t for t in titles)
        self.assertGreaterEqual(closed, 1, "OI-11 이 닫힌 항목으로 표시되지 않았다")
        open_items = len(titles) - closed
        text = re.sub(r"<[^>]+>", "", self.c12)
        stated = re.findall(r"(\d+)\s*건", text)
        self.assertGreaterEqual(
            len(stated), 3, "12항이 확인사항 건수를 적는 세 곳(12.5 · 배점표 · 주석) 중 일부가 없다")
        for n in stated:
            self.assertEqual(
                int(n), open_items,
                f"12항이 확인사항을 {n}건이라 하는데 11항에 열린 항목은 {open_items}건이다 "
                f"(등록 {len(titles)} · 해소 {closed})")

    def test_required_experience_covers_what_this_machine_needs(self):
        """실적 요구는 이 설비가 실제로 요구하는 기술에서 나와야 한다."""
        table = self._table("필수 실적")
        for token, why in (
            ("≥ 200 °C", "칼날·카세트가 도달하는 200 °C 공정온도"),
            ("2축 이상 위치 동기", "좌우 동기 이송축"),
            ("ISO 13849-1", "안전기능 PLr 검증"),
            ("과도 열전도 해석", "체류시간 하한을 정하는 해석"),
        ):
            self.assertIn(token, table, f"필수 실적에 {why} 가 없다")

    def _offsets(self):
        """접수 일정 세 행의 '발행일 + N 영업일' 을 읽는다."""
        rows = re.findall(r'class="num">D \+ (\d+) 영업일', self.c12)
        self.assertEqual(len(rows), 3, "접수 일정이 발행일 기준 영업일 3행이 아니다")
        return [int(n) for n in rows]

    def test_intake_is_counted_from_issue_in_business_days(self):
        """날짜를 박아 둔 사양서는 발행이 늦어지면 마감이 먼저 지나 버린다.

        9/7 초안은 질의 마감을 9/18 로 적었고, 발행 전에 그날이 지났다. 기한은
        발행일(D)에서 영업일로 세고, 달력 날짜는 발행할 때 적는다.
        """
        offsets = self._offsets()
        self.assertEqual(offsets, sorted(offsets), "질의·답변·접수 마감 순서가 뒤집혔다")
        self.assertEqual(len(set(offsets)), 3, "두 기한이 같은 날이다")
        self.assertGreater(offsets[0], 0, "질의 마감이 발행일과 같거나 앞선다")
        self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}", self.c12[self.c12.index("12.6"):
                                                                  self.c12.index("12.7")]),
                          "12.6 에 달력 날짜가 박혀 있다")

    def test_the_issue_date_is_left_for_issue_in_all_three_places(self):
        """발행일은 머리말·접수 일정 표제·꼬리말 세 곳에 나온다 — 세 곳 모두 발행 때 적는다.

        한 곳만 날짜로 남으면 입찰자는 어느 날짜로 기간을 세야 하는지 알 수 없고,
        마감을 다투는 순간 그 불일치가 그대로 분쟁이 된다.
        """
        self.assertIn("<dt>발행일</dt><dd>발행 시 기재</dd>", self.html, "머리말 발행일")
        self.assertIn("<caption>접수 일정 — 본 사양서 발행일(D) 기준 영업일</caption>", self.html,
                      "접수 일정 표제")
        self.assertIn("DYNAMIC INDUSTRY · 발행일은 발행 시 기재한다</p>", self.html, "꼬리말")
        self.assertIn("발행일 · 접수처 · 담당자는 <code>발행 시 기재</code>한다", self.c12)
        self.assertEqual(self.html.count("발행 시 기재"), 3,
                         "발행 때 적을 칸이 셋(머리말 · 12.6 · 꼬리말)이 아니다")

    def test_business_days_are_defined(self):
        """영업일의 정의가 없으면 '+9 영업일' 은 사람마다 다른 날이 된다."""
        self.assertIn("영업일은 토·일과 관공서 공휴일을 뺀 날", self.c12)
        self.assertIn("발행할 때 세 기한을 달력 날짜로 바꿔", self.c12)

    def test_the_proposal_window_is_what_the_text_says(self):
        """답변 회신부터 접수 마감까지의 영업일을 표에서 세어 본문과 댄다."""
        offsets = self._offsets()
        working = offsets[2] - offsets[1]
        self.assertGreaterEqual(
            working, 10,
            "제안서 작성 기간이 %d 영업일뿐이다 — 상세설계 제안에는 짧다" % working)
        stated = re.search(r"제안서 작성 기간은[^<]*<span class=\"m\">(\d+) 영업일</span>",
                           self.c12)
        self.assertIsNotNone(stated, "본문이 제안서 작성 기간을 영업일로 밝히지 않았다")
        self.assertEqual(
            int(stated.group(1)), working,
            "본문은 %s 영업일이라 적었는데 표로 세면 %d 영업일이다"
            % (stated.group(1), working))

    def test_payment_is_tied_to_approval_not_submission(self):
        """제출만으로 기성이 나가면 승인 단계가 압력을 잃는다."""
        table = self._table("기성 구분")
        self.assertIn("승인", table)
        self.assertIn("검토 완료", table)
        self.assertIn("발주자 승인 또는 검토 완료", self.c12,
                      "지급 요건이 승인임을 본문이 밝히지 않았다")


if __name__ == "__main__":
    unittest.main()


class TestTheAnalysisRequirementsReachedTheSpecification(unittest.TestCase):
    """해석이 만든 요구는 사양서에 적혀야 비로소 구속력이 생긴다.

    **요구를 만들어 놓고 문서에 안 넣으면 아무 일도 일어나지 않는다.**
    입찰자는 CAL-001 을 받지 않는다 — 사양서만 받는다. 그래서 여기서는
    보고서가 만든 요구 셋이 사양서 문장으로 살아 있는지를 본다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")

    # ── RIR3 · 내피 반사율
    def test_the_inner_skin_reflectance_is_a_specified_value(self):
        self.assertIn("ρ ≥ 0.4", self.html,
                      "내피 반사율이 사양서에 없으면 2B 소지가 납품된다")
        self.assertRegex(self.html, r"연마\s*STS304\s*#400",
                         "연마 등급이 없으면 반사율을 만들 방법이 안 적힌다")

    def test_the_reflectance_is_inspected_not_just_specified(self):
        """적기만 하고 검사하지 않으면 도면으로 구분이 안 된다."""
        self.assertRegex(self.html, r"가열실 내피 반사율",
                         "FAT 항목에 반사율 측정이 없다")
        self.assertIn("최저점", self.html, "점별 최저값 판정이 없다")

    def test_the_reflectance_is_maintained_not_just_accepted(self):
        """반사율은 열화한다 — 인수 시점만 보면 2 년 뒤 처리량이 준다."""
        seg = self.html[self.html.index("정비 매뉴얼"):][:700]
        self.assertIn("ρ ≥ 0.4", seg)
        self.assertIn("재연마", seg, "미달 시 무엇을 하는지가 없다")

    # ── RLM4 · 램프 봉착부
    def test_the_lamp_seal_temperature_is_a_purchase_condition(self):
        self.assertIn("250", self.html)
        self.assertIn("350", self.html)
        self.assertRegex(self.html, r"봉착부.{0,40}보증",
                         "봉착부 온도를 '보증' 으로 사지 않으면 우리가 못 정하는 값이 열린다")

    def test_the_lamp_seal_is_an_open_item_with_a_way_to_close_it(self):
        i = self.html.index("<b>OI-16</b>")
        seg = self.html[i:i + 2200]
        self.assertIn("해소", seg, "닫는 방법이 없는 미결항목은 미결이 아니라 방치다")
        self.assertRegex(seg, r"시험성적서|성적서")

    # ── RHB2 / RAL1 · 단별 셔터
    def test_the_airlock_is_specified_as_per_deck_shutters(self):
        self.assertIn("단별 셔터", self.html)
        self.assertIn("DECK_SHUTTER_MUTEX", self.html)
        self.assertNotIn("이중셔터 에어록", self.html,
                         "격리실이 없는데 이중셔터라고 적으면 제작사가 격리실을 만든다")

    def test_the_full_height_opening_is_recorded_as_rejected(self):
        """'검토하지 않았다' 와 '검토하고 안 샀다' 는 다르다."""
        import airlock as AIR
        full = AIR.solve()[0]["kw"]
        self.assertRegex(self.html, r"전고 개구.{0,80}kW",
                         "전고 개구를 왜 안 쓰는지가 사양서에 없다")
        self.assertIn(f"{full:,.0f} kW", self.html.replace("<span class=\"m\">", "")
                      .replace("</span>", ""))

    def test_the_shutter_count_follows_the_deck_count(self):
        """단수를 바꾸면 셔터 수도 바뀐다 — 상수로 박히면 갈라진다."""
        import parts
        plain = re.sub(r"<[^>]+>", "", self.html)
        self.assertIn(f"모두 {parts.SHUTTERS} 매", plain)
        self.assertIn(f"양단 각 {int(console_consts.const('DECKS'))} 단", plain)


class TestTheSafetyIoBudgetFollowsTheAirlock(unittest.TestCase):
    """단별 셔터가 안전 I/O 를 밀어 올렸다 — 그 대가가 문서에 적혀야 한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")

    def test_the_declared_safety_io_matches_the_interlock_model(self):
        import plc_model as M
        used = {k: 0 for k in M.BUDGET}
        for l in M.LEAVES:
            if l.io in used:
                used[l.io] += l.count
        for d in M.DRIVES:
            if d.io in used:
                used[d.io] += d.count
        plain = re.sub(r"<[^>]+>", "", self.html)
        self.assertIn(f"F-DI {M.BUDGET[M.FDI]} · F-DO {M.BUDGET[M.FDO]}", plain,
                      "7.1 의 안전 I/O 선언이 실행 모델의 예산과 다르다")
        self.assertIn(f"실사용 F-DI {used[M.FDI]}", plain,
                      "실사용 F-DI 가 모델과 다르다")
