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

    # ── 모듈 구성 ────────────────────────────────────────────────
    def test_module_table_matches_the_console_assemblies(self):
        """사양서의 M-0xx 표는 콘솔의 제작도 목록을 옮겨 적은 것이다.

        한쪽만 고치면 입찰자가 실물과 다른 외형치수로 반입계획·크레인을 잡는다.
        치수는 표에 적힌 숫자일 뿐이라 화면상으로는 어긋난 표시가 나지 않는다.
        """
        console_rows = dict(
            (m.group(1), (m.group(2), m.group(3), m.group(4)))
            for m in re.finditer(
                r"\{id:'(M-\d+)',name:'([^']+)',size:'([^']+)',material:'([^']+)'",
                self.console,
            )
        )
        self.assertGreaterEqual(len(console_rows), 13, "콘솔 제작도 목록을 찾지 못했다")
        rfq_rows = re.findall(
            r'<td class="k">(M-\d+)</td><td>([^<]+)</td>'
            r'<td class="num">([^<]+)</td><td>([^<]+)</td>',
            self.html,
        )
        self.assertEqual(
            len(rfq_rows), len(console_rows),
            "사양서 모듈 표의 행 수가 콘솔 제작도 수와 다르다",
        )
        squash = lambda v: re.sub(r"\s+", "", v)
        for ident, name, size, material in rfq_rows:
            self.assertIn(ident, console_rows, f"{ident} 이 콘솔에 없다")
            c_name, c_size, c_material = console_rows[ident]
            self.assertEqual(squash(name), squash(c_name),
                             f"{ident} 의 모듈명이 콘솔과 다르다")
            self.assertEqual(squash(size), squash(c_size),
                             f"{ident} 의 외형치수가 콘솔과 다르다")
            self.assertEqual(squash(material), squash(c_material),
                             f"{ident} 의 재질이 콘솔과 다르다")

    # ── 권취 롤 ──────────────────────────────────────────────────
    def test_roll_change_interval_follows_the_console_model(self):
        """롤당 장수·교체 주기는 검산 가능한 수치다."""
        thick = float(re.search(r"BACKSHEET_T=([\d.e-]+)", self.console).group(1))
        core = float(re.search(r"WR_CORE_R=([\d.]+)", self.console).group(1))
        full = float(re.search(r"WR_FULL_R=([\d.]+)", self.console).group(1))
        length = float(re.search(r"PANEL_L=([\d.]+)", self.console).group(1))
        panels = round((full ** 2 - core ** 2) / (length * thick / math.pi))

        self.assertAlmostEqual(self._num(r"코어 직경</th><td class=\"num\">Ø(\d+) mm"),
                               core * 2000, delta=0.5)
        self.assertAlmostEqual(self._num(r"만권 직경</th><td class=\"num\">Ø(\d+) mm"),
                               full * 2000, delta=0.5)
        self.assertAlmostEqual(self._num(r"백시트 두께</th><td class=\"num\">([\d.]+) mm"),
                               thick * 1000, places=3)
        self.assertAlmostEqual(self._num(r"롤당 처리 장수</th><td class=\"num\">(\d+) 장"),
                               panels, delta=0.5)
        self.assertAlmostEqual(
            self._num(r"롤 교체 주기</th><td class=\"num\">약 ([\d.]+) h"),
            panels / (self.m["line_rate"] * 0.9), delta=0.1,
            msg="롤 교체 주기가 보증 처리량(90% 가동률)과 맞지 않는다",
        )
        self.assertAlmostEqual(
            self._num(r"1장당 직경 증가</th><td class=\"num\">\+([\d.]+) mm"),
            (math.sqrt(core ** 2 + length * thick / math.pi) - core) * 2000, delta=0.1,
        )

    def test_winder_is_specified_downstream_with_a_guide_roll(self):
        """권취부 위치와 박리각 고정은 입찰자가 임의로 정할 사항이 아니다.

        모듈 표의 이름에만 '탠덤 하류' 가 남아 있어도 요구사항이 되지는 않으므로
        6.4항 본문에서 확인한다.
        """
        clause = re.search(
            r'<h3>백시트 권취부</h3>(.*?)</div></div>', self.html, re.S
        )
        self.assertIsNotNone(clause, "백시트 권취부 조항이 없다")
        body = clause.group(1)
        self.assertIn("탠덤 하류", body, "권취부 위치가 규정되지 않았다")
        self.assertIn("가이드롤", body, "박리 가이드롤이 규정되지 않았다")
        self.assertIn("안전펜스 밖", body, "롤 보관대 위치가 규정되지 않았다")
        self.assertRegex(body, r"박리각을 <span class=\"m\">\d+ – \d+°",
                         "박리각 범위가 규정되지 않았다")
        self.assertIn("2축", body, "권취축 이중화가 규정되지 않았다")
        # 콘솔의 실제 배치와 방향이 같은지
        hks = float(re.search(r"HKS_X=([\d.]+)", self.console).group(1))
        drum = float(re.search(r"WR_DRUM_X=([\d.]+)", self.console).group(1))
        self.assertGreater(drum, hks,
                           "사양서는 하류라고 적었는데 콘솔의 권취부는 상류에 있다")

    def test_backsheet_thickness_assumption_is_an_open_item(self):
        """0.30mm 가정이 틀리면 교체 주기가 바뀐다. 가정으로 남겨야 한다."""
        block = re.search(r"<b>OI-11</b>(.*?)</div>\s*</div>", self.html, re.S)
        self.assertIsNotNone(block, "백시트 두께 확인사항이 없다")
        self.assertIn("0.40", block.group(1), "두께 상한에서의 영향이 없다")
        thick = 0.40e-3
        panels = round((0.30 ** 2 - 0.15 ** 2) / (2.4 * thick / math.pi))
        self.assertEqual(panels, 221)
        self.assertIn("221", block.group(1), "두께 0.40mm 일 때의 롤당 장수가 틀렸다")
    # ── 탠덤 동시부하 ────────────────────────────────────────────
    def test_dual_engagement_fraction_is_arithmetic(self):
        """두 칼날이 동시에 물리는 구간은 패널 길이와 칼끝 간격에서 나온다."""
        length = 2400.0
        gap = float(re.search(r"칼끝 간격 <span class=\"m\">(\d+) ± 2 mm", self.html).group(1))
        self.assertAlmostEqual(gap, 300.0, delta=0.5)
        self.assertAlmostEqual(
            self._num(r"행정의 <span class=\"m\">([\d.]+) %</span>\s*가?\s*\n?\s*동시부하"),
            (length - gap) / length * 100, delta=0.1,
            msg="동시부하 구간 비율이 패널 길이·칼끝 간격과 맞지 않는다",
        )

    def test_vacuum_hold_requirement_is_computed_from_the_thrust_range(self):
        """A ≥ 2F/(μ·Δp) — 두 칼날 합으로 잡아야 한다. 한 칼날로 잡으면 절반이 나온다."""
        block = re.search(r"<b>OI-13</b>(.*?)</div>\s*</div>", self.html, re.S)
        self.assertIsNotNone(block, "진공 유지력 확인사항이 없다")
        body = block.group(1)
        self.assertIn("A ≥ 2F / (μ·Δp)", body,
                      "필요 패드 면적 식이 두 칼날 합(2F)이 아니다")
        mu = float(re.search(r"μ = ([\d.]+)", body).group(1))
        dp = float(re.search(r"Δp = (\d+) kPa", body).group(1)) * 1000
        glass = 2.4 * 1.2
        for thrust, area_pat, pct_pat in (
            (1.49e3, r"<span class=\"m\">([\d.]+) m²</span>\(", r"유리면의 ([\d.]+) %\)"),
            (13.37e3, r"상한[^<]*<span class=\"m\">[^<]*</span>[^<]*<span class=\"m\">([\d.]+) m²</span>",
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
        # 본문이 근거로 든 처리량이 실제 라인 성능과 동떨어져 있으면 안 된다
        self.assertAlmostEqual(rate, self.m["line_rate"] * 0.9, delta=1.0,
                               msg="칼날 수명 근거의 처리량이 보증 처리량과 다르다")
        shift = float(re.search(r"8 h 교대당 <span class=\"m\">([\d,]+) m</span>", body)
                      .group(1).replace(",", ""))
        self.assertAlmostEqual(shift, got * 8, delta=1)


class TestRollDischargeRoute(unittest.TestCase):
    """만권 롤 반출 경로 — 사양서의 높이들은 모두 콘솔 상수에서 나온 값이다.

    이 절은 '이렇게 하면 좋겠다' 가 아니라 '이 길밖에 없다' 를 적은 것이다.
    콘솔에서 스키드 높이 하나만 바꿔도 여기 적힌 940/1,240/320/620 이 전부
    틀어지는데, 사양서는 손으로 적은 문서라 화면상으로는 아무 표시가 없다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = RFQ.read_text(encoding="utf-8")
        cls.console = CONSOLE.read_text(encoding="utf-8")

    def _num(self, pattern):
        m = re.search(pattern, self.html)
        self.assertIsNotNone(m, f"사양서에서 수치를 찾지 못했다: {pattern}")
        return float(m.group(1).replace(",", ""))

    def _const(self, name):
        m = re.search(rf"(?:const|,)\s*{name}\s*=\s*(-?[\d.]+(?:e-?\d+)?)[,;]", self.console)
        self.assertIsNotNone(m, f"콘솔 상수 {name} 을 찾지 못했다")
        return float(m.group(1))

    def test_skid_height_matches_the_console(self):
        """스키드 상면과 롤 축높이는 콘솔이 그리는 그 높이여야 한다."""
        rail = self._const("RH_RAIL_Z")
        r = self._const("WR_FULL_R")
        self.assertAlmostEqual(self._num(r"상면 (\d+) mm</span> 스키드 레일"),
                               rail * 1000, delta=1)
        self.assertAlmostEqual(self._num(r"<span class=\"m\">940 \+ 300 = ([\d,]+) mm</span>"),
                               (rail + r) * 1000, delta=1)

    def test_the_roll_clears_the_carrier_rail(self):
        """캐리어 주행레일 상단 770mm — 이 한 줄이 바닥 대차를 배제한 근거다."""
        top = self._num(r"주행레일 상단 <span class=\"m\">(\d+) mm</span>")
        self.assertLess(top, self._const("RH_RAIL_Z") * 1000,
                        "스키드 상면이 주행레일보다 낮다 — 롤이 레일을 뚫는다")
        self.assertAlmostEqual(self._num(r"롤 하단\s*<span class=\"m\">(\d+) mm</span>"),
                               self._const("RH_RAIL_Z") * 1000, delta=1)

    def test_roll_port_opening_matches_the_console(self):
        """포트가 롤보다 작으면 그림에서만 지나간다."""
        w = self._num(r"<span class=\"m\">([\d,]+)\(W\) × 1,350\(H\) mm</span>")
        h = self._num(r"<span class=\"m\">1,900\(W\) × ([\d,]+)\(H\) mm</span>")
        self.assertAlmostEqual(w, self._const("ROLL_PORT_W") * 1000, delta=1)
        self.assertAlmostEqual(
            h, (self._const("ROLL_PORT_Z1") - self._const("ROLL_PORT_Z0")) * 1000, delta=1)
        self.assertGreater(w, self._const("WR_FULL_R") * 2000 + 100,
                           "포트 폭이 롤 직경에 여유를 주지 못한다")

    def test_corner_lift_travel_is_the_height_difference(self):
        """승강 행정은 스키드 높이와 보관 축높이의 차 그 자체다."""
        rail, r = self._const("RH_RAIL_Z"), self._const("WR_FULL_R")
        store = self._const("BS_ROLL_Z")
        self.assertAlmostEqual(self._num(r"차 <span class=\"m\">(\d+) mm</span> 를 받는다"),
                               (rail + r - store) * 1000, delta=1)

    def test_rolling_rail_sets_the_stored_axis_height(self):
        """굴림 레일 상면 + 롤 반경 = 보관 축높이. 셋 중 하나만 틀려도 롤이 뜬다."""
        store, r = self._const("BS_ROLL_Z"), self._const("WR_FULL_R")
        self.assertAlmostEqual(self._num(r"레일 상면 <span class=\"m\">(\d+) mm</span>"),
                               (store - r) * 1000, delta=1)
        self.assertAlmostEqual(self._num(r"= 보관 축높이 <span class=\"m\">(\d+) mm</span>"),
                               store * 1000, delta=1)

    def test_tie_rail_clears_the_passing_roll(self):
        """타이레일이 지나가는 롤보다 낮으면 롤이 레일을 관통한다."""
        rail, r = self._const("RH_RAIL_Z"), self._const("WR_FULL_R")
        tie = self._const("BS_TIE_Z")
        self.assertAlmostEqual(self._num(r"롤 상단\(<span class=\"m\">([\d,]+) mm</span>\)"),
                               (rail + r + r) * 1000, delta=1)
        self.assertAlmostEqual(self._num(r"<span class=\"m\">([\d,]+) mm</span> 에 둔다"),
                               tie * 1000, delta=1)
        self.assertGreater(tie, rail + 2 * r, "타이레일이 지나가는 롤과 겹친다")

    def test_the_blocked_routes_are_recorded_with_their_interference(self):
        """'이 길밖에 없다' 는 주장은 막힌 길을 같이 적어야 성립한다."""
        m = re.search(r"<caption>반출 통로 검토</caption>(.*?)</table>", self.html, re.S)
        self.assertIsNotNone(m, "반출 통로 검토표가 없다")
        table = m.group(1)
        for route in ("상부 인양", "바닥 대차", "+X 굴림"):
            self.assertIn(route, table, f"{route} 검토 결과가 빠졌다")
        self.assertEqual(table.count("불가"), 3, "막힌 통로 판정이 세 개가 아니다")
        self.assertIn("롤 포트로 해소", table, "채택한 통로의 조건이 적혀 있지 않다")

    def test_the_port_shutter_shares_the_hatch_interlock(self):
        """포트만 열리고 해치가 잠겨 있으면 롤이 갈 곳이 없다 — 같은 신호여야 한다."""
        self.assertIn("SHUTTER_CLOSED ∧ 권취축 정지 ∧ CARRIAGE_OUT", self.html)
        self.assertRegex(
            self.console, r"ROLL_PORT_Z1-ROLL_PORT_Z0\)\*\.94\*w\.pose\.inHatch",
            "콘솔의 롤 포트 셔터가 해치와 같은 신호를 쓰지 않는다",
        )


class TestVacuumPadLayout(unittest.TestCase):
    """OI-13 에 적은 패드 배치가 콘솔이 그리는 배치와 같은지.

    이 수치는 '이렇게 하면 된다'는 제안이 아니라 도면이 실제로 그렇게 그려져
    있다는 진술이다. 콘솔에서 패드 하나만 빼도 사양서의 1.29 배가 거짓이 된다.
    """

    MU, DP, F_HI = 0.6, 65_000, 13_370

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
        self.assertAlmostEqual(self._num(r"<span class=\"m\">(\d+)열 × 3행"), cols, delta=0)
        self.assertAlmostEqual(self._num(r"열 × (\d+)행 = 18패드"), rows, delta=0)
        self.assertAlmostEqual(self._num(r"= (\d+)패드 Ø250"), cols * rows, delta=0)
        self.assertAlmostEqual(self._num(r"패드 Ø(\d+)"), r * 2000, delta=0.5)

    def test_pad_area_and_margin_are_the_computed_ones(self):
        cols, rows, r = int(self._c("PAD_COLS")), int(self._c("PAD_ROWS")), self._c("PAD_R")
        area = cols * rows * math.pi * r ** 2
        need = 2 * self.F_HI / (self.MU * self.DP)
        self.assertAlmostEqual(self._num(r"패드 면적 <span class=\"m\">([\d.]+) m²"), area, delta=0.002)
        self.assertAlmostEqual(self._num(r"상한 요구\s*<span class=\"m\">([\d.]+) m²"), need, delta=0.002)
        self.assertAlmostEqual(self._num(r"<span class=\"m\">([\d.]+) 배</span>"), area / need, delta=0.01)

    def test_pitch_and_clearances_come_from_the_panel(self):
        cols, rows, r = int(self._c("PAD_COLS")), int(self._c("PAD_ROWS")), self._c("PAD_R")
        length, width = self._c("PANEL_L"), self._c("PANEL_W")
        px, py = length / cols, width / rows
        self.assertAlmostEqual(self._num(r"피치 <span class=\"m\">(\d+) × 400 mm"), px * 1000, delta=1)
        self.assertAlmostEqual(self._num(r"피치 <span class=\"m\">400 × (\d+) mm"), py * 1000, delta=1)
        self.assertAlmostEqual(self._num(r"패드 간 여유\s*<span class=\"m\">(\d+) mm"),
                               (px - 2 * r) * 1000, delta=1)
        self.assertAlmostEqual(self._num(r"가장자리 여유\s*\n?\s*<span class=\"m\">(\d+) mm"),
                               (width / 2 - (rows - 1) / 2 * py - r) * 1000, delta=1)

    def test_the_assumption_behind_the_layout_is_stated(self):
        """μ 0.6 가정이 빠지면 이 배치가 무조건 성립하는 것처럼 읽힌다."""
        self.assertIn("μ = 0.6 가정에 걸려 있으므로", self.html,
                      "패드 배치가 어떤 가정 위에 서 있는지 적혀 있지 않다")


if __name__ == "__main__":
    unittest.main()
