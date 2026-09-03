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

from .test_drawings import standalone_document_checks
from .test_pv_console_calculator import thermal_model, sixty_panel_run

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
        # 각 항목이 현황과 해소 방법을 모두 갖는지
        for block in re.findall(r'<div class="oi">(.*?)</div>\s*</div>', self.html, re.S):
            oid = re.search(r"<b>(OI-\d+)</b>", block).group(1)
            self.assertEqual(
                block.count("<em>현황</em>"), 1, f"{oid} 에 현황이 없다"
            )
            self.assertEqual(
                block.count("<em>해소</em>"), 1, f"{oid} 에 해소 방법이 없다"
            )

    def test_states_the_prior_package_has_no_fabrication_drawings(self):
        """입찰자가 가장 먼저 알아야 할 사실이다. 빠지면 견적이 틀어진다."""
        self.assertIn("선행자료에는 제작도면이 없다", self.html)
        self.assertIn("부품도", self.html)

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
            self._num(r"여유 ([\d.]+) %"), margin, delta=0.05
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
            self._num(r"피치\s*= t_열 / 5 = ([\d.]+) s/장"),
            self.m["pitch_s"], delta=0.05,
        )

    def test_model_constants_match_the_console(self):
        """상수를 사양서에 옮겨 적으면서 틀리면 입찰자가 다른 설비를 설계한다."""
        for literal in ("8.7359", "113.15", "175"):
            self.assertIn(literal, self.html, f"열모델 상수 {literal} 이 사양서에 없다")
        # 콘솔의 실제 상수와 대조 (사양서는 반올림 표기)
        areal = float(re.search(r"arealCp:([\d.]+)", self.console).group(1))
        self.assertAlmostEqual(
            self._num(r"([\d.]+) kJ/\(m²·K\)"), areal, places=4,
            msg="사양서의 면적열용량이 콘솔과 다르다",
        )

    def test_tandem_cycle_terms_add_up(self):
        """사양서에 적힌 항별 값이 실제로 합계가 되는지."""
        a = self._num(r"= ([\d.]+) \+ 1\.50 \+ 3\.00")
        total = self._num(r"= [\d.]+ \+ 1\.50 \+ 3\.00 = ([\d.]+) s/장")
        self.assertAlmostEqual(a + 1.50 + 3.00, total, delta=0.02)
        self.assertAlmostEqual(total, self.m["cycle_s"], delta=0.05)

    # ── 전기 ────────────────────────────────────────────────────────
    def _load_schedule(self):
        rows = re.findall(
            r"\{\s*id:'([^']+)'\s*,\s*load:'[^']*'\s*,"
            r"\s*kW:(\d+)\s*,\s*pf:([\d.]+)\s*,\s*mccb:'([^']+)'\s*\}",
            self.console,
        )
        self.assertGreaterEqual(len(rows), 5, "콘솔 부하표를 찾지 못했다")
        return rows

    def test_load_schedule_rows_match_the_console(self):
        for ident, kw, pf, mccb in self._load_schedule():
            self.assertIn(ident, self.html, f"{ident} 분기가 사양서에 없다")
            row = re.search(
                rf'{re.escape(ident)}</td>.*?</tr>', self.html, re.S
            )
            self.assertIsNotNone(row, f"{ident} 행을 사양서에서 찾지 못했다")
            self.assertIn(kw, row.group(0), f"{ident} 의 kW 가 콘솔과 다르다")
            self.assertIn(f"{float(pf):.2f}", row.group(0),
                          f"{ident} 의 역률이 콘솔과 다르다")
            self.assertIn(mccb, row.group(0), f"{ident} 의 차단기가 콘솔과 다르다")

    def test_full_load_current_matches_the_phasor_sum(self):
        rows = self._load_schedule()
        volts = int(re.search(r"const LINE_V=(\d+)", self.console).group(1))
        active = sum(int(kw) for _, kw, _, _ in rows)
        reactive = sum(
            int(kw) * math.tan(math.acos(float(pf))) for _, kw, pf, _ in rows
        )
        apparent = math.hypot(active, reactive)
        fla = apparent * 1000 / (3 ** 0.5 * volts)

        self.assertAlmostEqual(self._num(r"FLA ([\d.]+) A"), round(fla), delta=0.5)
        self.assertAlmostEqual(self._num(r"([\d.]+) kVA"), apparent, delta=0.05)
        self.assertAlmostEqual(
            self._num(r"class=\"num\">([\d.]+)</td><td class=\"num\">494\.2"),
            active / apparent, delta=0.001,
        )

    def test_breaker_headroom_claim_is_true(self):
        """'630AT 기준 1.27배 여유' 는 검산 가능한 주장이다."""
        claimed = self._num(r"630AT 기준 ([\d.]+)배 여유")
        rows = self._load_schedule()
        volts = int(re.search(r"const LINE_V=(\d+)", self.console).group(1))
        active = sum(int(kw) for _, kw, _, _ in rows)
        reactive = sum(
            int(kw) * math.tan(math.acos(float(pf))) for _, kw, pf, _ in rows
        )
        fla = math.hypot(active, reactive) * 1000 / (3 ** 0.5 * volts)
        self.assertAlmostEqual(claimed, 630 / fla, delta=0.01)
        self.assertGreater(claimed, 1.0, "차단기 정격이 전부하전류보다 작다")


if __name__ == "__main__":
    unittest.main()
