"""칼날 인서트 날끝 (D-502) — 쐐기각은 수직 반력비의 상한이다.

인서트는 판재 외형(PL 8 × 60)으로만 적혀 있어 칼날을 깎을 수 없었다. 9/25 날끝
단면을 정했다. 결정은 하나의 식에 묶여 있다 — 떼어 낸 층이 레이크면을 타고 오르며
칼날을 누르는 힘의 수직/수평 비는 cot(α + atan μ) 를 넘지 못한다. 마찰 하한 0.2 에서
구조해석의 포락 V/H ≤ 1 을 지키는 가장 작은 5° 눈금이 35° 다.

숫자가 바뀌면 결론이 바뀐다 — 그래서 결론을 숫자에 묶는다. 인서트가 홀더 · 이웃
조각과 부딪히지 않는지, 나사가 추력을 마찰로 받는지, 카탈로그 · 콘솔 도면 · 사양서 ·
파일럿 · 해석서가 같은 날끝을 말하는지도 본다.
"""

import math
import re
import unittest

from . import _path  # noqa: F401
from ._path import ROOT

import knife_edge as KE  # noqa: E402
import parts as PT  # noqa: E402
import pilot_plan as PP  # noqa: E402
from console_consts import const as c  # noqa: E402

CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
ANALYSIS = ROOT / "docs" / "dg-hk60-analysis.html"
PILOT = ROOT / "docs" / "dg-hk60-pilot.html"
FAB = ROOT / "docs" / "dg-hk60-fab-spec.html"


def _fn(src, name):
    """함수 본문을 중괄호 균형으로 잘라 낸다."""
    i = src.index(f"function {name}(")
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    raise AssertionError(f"{name} 본문이 닫히지 않는다")


class TestTheWedgeAngleIsTheSmallestThatHoldsTheEnvelope(unittest.TestCase):
    """35° 는 취향이 아니라 풀이다 — 한 눈금 눕히면 포락을 넘고, 세우면 추력만 는다."""

    @classmethod
    def setUpClass(cls):
        cls.lim = KE.limits()

    def test_the_bound_is_the_force_balance_on_the_rake_face(self):
        """레이크면 접촉력 N 과 마찰 μN 을 수직 · 수평으로 나눈 비 그대로다."""
        for a in (25, 35, 45):
            for mu in (0.0, 0.2, 0.5):
                r = math.radians(a)
                want = (math.cos(r) - mu * math.sin(r)) / (math.sin(r) + mu * math.cos(r))
                self.assertAlmostEqual(KE.vh_bound(a, mu), want, places=12)
                if want > 0:
                    self.assertAlmostEqual(KE.vh_bound(a, KE.mu_for(a, want)), want, places=9)

    def test_the_root_constant_is_the_solved_angle(self):
        self.assertEqual(KE.choose_alpha(), c("KNIFE_WEDGE"),
                         "뿌리 상수 KNIFE_WEDGE 가 풀이와 다르다 — 식이 바뀌었거나 손으로 고쳤다")
        self.assertEqual(KE.ALPHA % KE.ALPHA_STEP, 0, "연삭 지그 눈금에 없는 각이다")

    def test_one_step_shallower_breaks_the_envelope(self):
        env = self.lim["vh_env"]
        self.assertLessEqual(KE.vh_bound(KE.ALPHA, KE.MU_MIN), env)
        self.assertGreater(KE.vh_bound(KE.ALPHA - KE.ALPHA_STEP, KE.MU_MIN), env,
                           "한 눈금 눕혀도 포락 안이면 35° 는 필요 이상으로 세운 각이다")

    def test_steeper_only_costs_thrust(self):
        """더 세우면 V/H 는 줄지만 레이크면이 받는 추력 몫이 는다 — 필요한 만큼만 세운다."""
        self.assertGreater(KE.thrust_share(KE.ALPHA + KE.ALPHA_STEP, 0.3), KE.thrust_share(KE.ALPHA, 0.3))

    def test_the_glass_needs_almost_no_friction(self):
        """마찰 가정이 틀려도 유리가 먼저 깨지지 않는다 — 가정이 떨어질 자리가 넓다."""
        mu_gl = KE.mu_for(KE.ALPHA, self.lim["vh_glass"])
        self.assertLess(mu_gl, 0.05)
        self.assertLess(KE.mu_for(KE.ALPHA, self.lim["vh_env"]), KE.MU_MIN)

    def test_the_glass_limit_holds_at_the_land_tolerance(self):
        """S14 는 V/H × 랜드 폭 — 공차 상한 랜드에서도 마찰 하한에서 안이어야 한다."""
        lo, hi = KE.land_final()
        self.assertLessEqual(hi, KE.LAND + KE.LAND_TOL)
        self.assertGreaterEqual(lo, KE.LAND - KE.LAND_TOL)
        self.assertLessEqual(KE.vh_bound(KE.ALPHA, KE.MU_MIN) * self.lim["land_max"], self.lim["arm_max"])

    def test_required_friction_is_written_rounded_up(self):
        """드는 마찰을 내려 적으면 적힌 값에서 한계를 넘는다 (0.0301 → 0.03)."""
        need = KE.mu_for(KE.ALPHA, self.lim["vh_glass"])
        self.assertGreaterEqual(KE.up(need, 3), need)
        self.assertLessEqual(KE.vh_bound(KE.ALPHA, KE.up(need, 3)), self.lim["vh_glass"])
        self.assertLessEqual(KE.vh_bound(KE.ALPHA, KE.up(KE.mu_for(KE.ALPHA, 1.0), 2)), 1.0)


class TestTheEdgeFitsTheBudgets(unittest.TestCase):

    def test_the_holder_front_stands_behind_the_rake(self):
        """홀더 앞면이 레이크면 끝보다 앞이면 떼어 낸 층이 홀더 밑에 갇힌다.
        너무 물리면 인서트가 캔틸레버로 길어진다 — 1 mm 안에서 맞춘다."""
        run = KE.rake_run()
        self.assertGreaterEqual(KE.NOSE, run)
        self.assertLess(KE.NOSE, run + 1.0)

    def test_the_hone_is_a_small_part_of_the_depth_budget(self):
        self.assertLessEqual(KE.hone_ratio(), 0.2 + 1e-9,
                             "호닝 반경 상한이 칼끝 깊이 예산 0.15 의 1/5 을 넘는다")

    def test_grinding_stock_leaves_the_finished_relief(self):
        self.assertGreaterEqual(KE.relief_supply() - KE.GRIND_STOCK, KE.RELIEF - 1e-9)


class TestTheScrewsHoldTheThrustByFriction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.j = KE.joint()

    def test_both_inserts_hold_twice_the_thrust_by_friction(self):
        for name in ("center", "step"):
            self.assertGreaterEqual(self.j[name]["ratio"], KE.SLIP_RULE,
                                    f"{name} 인서트가 추력의 2배를 마찰로 못 받는다")

    def test_m6_because_m10_leaves_no_steel_under_the_head(self):
        """M10 접시머리를 두께 8 판에 묻으면 머리 밑에 1.3 이 남아 소입에서 갈라진다."""
        self.assertGreaterEqual(KE.under_head("M6"), 3.0)
        self.assertLess(KE.under_head("M10"), 2.0)
        self.assertEqual(KE.SCREW, "M6")

    def test_the_hole_row_is_under_the_holder_and_inside_the_insert(self):
        x, r = KE.hole_x(), KE.CSK_D / 2
        self.assertGreaterEqual(x - r, KE.NOSE, "접시가 홀더 앞면 밖(코)에 걸린다 — 받쳐 주는 밑판이 없다")
        self.assertLessEqual(x + r, KE.W, "접시가 인서트 뒤끝을 넘는다")
        self.assertGreater(x - KE.HOLE_D / 2, KE.rake_run(), "나사 구멍이 레이크면 밑을 뚫는다")

    def test_center_holes_stay_on_the_holder_body(self):
        hs = KE.holes_center()
        self.assertEqual(hs[0], KE.HOLE_END)
        self.assertLessEqual(hs[-1], KE.CENTER - KE.END_MIN)
        self.assertEqual(len(hs), 3)

    def test_step_holes_stay_off_the_lap(self):
        """계단 인서트의 안쪽 끝 17 은 제 홀더 밖이다 — 구멍이 거기 들면 받쳐 줄 밑판이 없다."""
        hs = KE.holes_step()
        self.assertGreaterEqual(len(hs), 2, "계단 인서트를 나사 하나로 물리면 돈다")
        body = KE.STEP_W - KE.GAP
        self.assertLessEqual(hs[-1] + KE.CSK_D / 2, body - KE.END_MIN + KE.CSK_D / 2)
        self.assertLessEqual(hs[-1] + KE.CSK_D / 2, KE.STEP_W + KE.LAP - KE.lap_len())


class TestTheNeighboursDoNotCollide(unittest.TestCase):
    """일곱 홀더는 따로 뜬다 — 옆 틈과 겹침 끝이 그 움직임을 다 받아야 한다."""

    def test_the_side_gap_takes_opposite_roll(self):
        self.assertGreaterEqual(KE.GAP, KE.gap_need())

    def test_the_lap_end_clears_the_inner_holder(self):
        self.assertGreaterEqual(KE.lap_clear(), 1.0 - 1e-9)
        self.assertLess(KE.LAP_STEP, KE.T - KE.RELIEF - 1.0, "따낸 겹침 끝이 너무 얇다")

    def test_holders_and_gaps_fill_the_width(self):
        steps = 2 * int(c("KNIFE_STEPS"))
        total = KE.CENTER + steps * (KE.STEP_W - KE.GAP) + steps * KE.GAP
        self.assertAlmostEqual(total, c("KNIFE_W") * 1000, places=6)
        self.assertEqual(KE.lap_len(), KE.LAP + KE.GAP)


class TestTheCatalogCarriesTheEdge(unittest.TestCase):
    """부품도가 D-502 와 다른 구멍을 뚫으면 제작사는 부품도를 따른다."""

    @classmethod
    def setUpClass(cls):
        cls.by = {p.pid: p for p in PT.P}

    def test_inserts_carry_the_holes_and_the_edge(self):
        for pid, holes in (("P-005-15", KE.holes_center()), ("P-005-16", KE.holes_step())):
            p = self.by[pid]
            g = p.shape.d
            self.assertEqual((g["W"], g["t"]), (KE.W, KE.T), pid)
            self.assertEqual(tuple(h[0] for h in g["holes"]), holes, pid)
            self.assertTrue(all(h[1] == KE.hole_x() and h[2] == KE.HOLE_D for h in g["holes"]), pid)
            self.assertIn("D-502", g.get("hnote", ""), f"{pid} 구멍 주기가 날끝 도면을 부르지 않는다")
            self.assertIn(f"쐐기 {KE.ALPHA:.0f}°", p.note, pid)
            self.assertIn(f"접시머리 {KE.SCREW}", p.fix, pid)
            self.assertNotIn("M10", p.fix, f"{pid} 이 아직 M10 으로 문다")
            self.assertIn(f"HRC {KE.HRC}", p.finish, pid)
            self.assertIn(f"{KE.TEMPER_C} ℃", p.finish, pid)

    def test_holder_bodies_stand_behind_the_nose_and_off_the_lap(self):
        for pid, length in (("P-005-25", KE.CENTER), ("P-005-26", KE.STEP_W - KE.GAP)):
            g = self.by[pid].shape.d
            self.assertEqual(g["h"], KE.CASS_W - KE.NOSE, f"{pid} 몸통이 코 {KE.NOSE:.0f} 를 먹는다")
            self.assertEqual(g["L"], length, pid)
            self.assertIn("연삭", self.by[pid].finish, f"{pid} 인서트 자리가 도장면이다 — 마찰 접합이 안 선다")


class TestTheConsoleDrawsWhatTheModuleSolved(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.body = _fn(cls.src, "insertDrawing")

    def test_the_edge_block_is_the_modules_output(self):
        """콘솔의 EDGE 블록은 knife_edge.py 가 찍는다 — 손으로 고치면 여기서 갈라진다."""
        self.assertIn(KE.js_block(), self.src, "EDGE 블록이 knife_edge.py 와 다르다 — --write 를 돌린다")

    def test_the_sheet_is_reachable_and_framed(self):
        self.assertIn('data-drawing="insert"', self.src)
        self.assertIn("drawingTab==='insert')drawingContent.innerHTML=insertDrawing()", self.src)
        for token in ("fabSheet(", "+ fabTitleBlock({no:'D-502'", "+ revBlock([", "scale:'4:1 / 40:1'"):
            self.assertTrue(token in self.body, f"D-502 에 {token} 이 없다")

    def test_the_sheet_reads_its_numbers_from_the_block(self):
        """35 를 손으로 적으면 뿌리 상수를 바꿔도 도면만 옛 각에 남는다."""
        self.assertIn("E.alpha*Math.PI/180", self.body)
        self.assertNotIn("35°", self.body)
        self.assertNotIn("f2(E.mu_glass)", self.body, "드는 마찰을 내려 적는다")
        self.assertIn("up(E.mu_glass,3)", self.body)

    def test_d501_draws_the_nose(self):
        body = _fn(self.src, "cassetteDrawing")
        self.assertIn("ax(KNIFE_NOSE)", body, "D-501 단면의 홀더가 인서트 코 뒤에 서지 않는다")
        self.assertIn("EDGE.run", body, "D-501 단면에 레이크면이 없다")
        self.assertIn("조각 단면 ${mm(CASS_W)} × ${mm(CASS_H)}", body)

    def test_fabrication_arrowheads_are_iso_size(self):
        """화살표가 치수 글자를 덮던 것 — A3 에서 길이 3 mm 남짓이면 된다 (ISO 129)."""
        for mid in ("fa", "fb"):
            m = re.search(rf'<marker id="{mid}" markerWidth="([\d.]+)" markerHeight="([\d.]+)"', self.src)
            self.assertIsNotNone(m, f"{mid} 표지가 없다")
            self.assertLessEqual(float(m.group(1)), 4.0, f"{mid} 화살표가 길다")
            self.assertLessEqual(float(m.group(2)), 2.0, f"{mid} 화살표가 넓다")


class TestTheConceptTitleBlocksCarryTheirRevision(unittest.TestCase):
    """REV.21C 계단 칼날을 그린 시트가 폐기된 REV.20 · 09-03 을 찍고 있었다."""

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")

    def test_the_date_is_a_parameter_and_the_revision_is_current(self):
        d = re.search(r"const titleBlock=\(([^)]*)\)=>", self.src)
        self.assertIsNotNone(d)
        self.assertEqual(d.group(1), "code,title,subtitle,date,rev=HK60C.rev,h=610")
        self.assertNotIn("SCALE NTS · 2026-09-03", self.src)
        self.assertNotIn("DG-HK60 · ${esc(rev)}", self.src, "모델명이 HK60C 가 아니다")

    def test_every_sheet_is_dated_after_its_revision_began(self):
        """REV.21C 는 09-05 에 섰다 — 그 전 날짜를 단 REV.21C 시트는 있을 수 없다."""
        # 조립도 시트는 도면번호를 변수(a.id)로 넘긴다
        calls = re.findall(r"titleBlock\(('[^']+'|a\.id),.*?,'(\d{4}-\d{2}-\d{2})'(?:,HK60C\.rev,\d+)?\)", self.src)
        names = {n.strip("'") for n, _ in calls}
        for sheet in ("E-001", "C-001 / C-101", "D-501", "D-601"):
            self.assertIn(sheet, names, f"{sheet} 가 날짜를 넘기지 않는다")
        self.assertEqual(len(calls), len(re.findall(r"\btitleBlock\(", self.src)),
                         "날짜 없이 부르는 titleBlock 이 있다")
        for n, date in calls:
            self.assertGreaterEqual(date, "2026-09-05", f"{n} 이 REV.21C 보다 이른 날짜다")

    def test_the_mark_is_not_blown_up_by_the_stage_css(self):
        """자손 선택자로 두면 표제란 안의 마크 svg 도 폭 100% 로 불어나 잘린다."""
        self.assertIn(".drawing-stage>svg{display:block;width:100%", self.src)
        self.assertNotIn(".drawing-stage svg{", self.src)


class TestTheDocumentsSayTheSameEdge(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lim = KE.limits()
        cls.mu_env = KE.up(KE.mu_for(KE.ALPHA, cls.lim["vh_env"]), 2)
        cls.mu_gl = KE.up(KE.mu_for(KE.ALPHA, cls.lim["vh_glass"]), 3)

    def test_the_specification_states_the_edge(self):
        s = RFQ.read_text(encoding="utf-8")
        i = s.index('<div class="n">6.2</div>')
        clause = s[i:s.index('<div class="n">6.3</div>')]
        for token in ("D-502", f"{KE.ALPHA}° ± {KE.WEDGE_TOL}°", f"R {KE.HONE:.2f} ± {KE.HONE_TOL:.2f}",
                      f"{KE.LAND:.1f} ± {KE.LAND_TOL:.1f} mm", f"≥ {KE.RELIEF:.1f} mm", f"{KE.NOSE:.0f} mm",
                      f"{self.mu_env:.2f}", f"{self.mu_gl:.3f}", f"{KE.SCREW} 10.9", "PT-10",
                      f"{math.floor(self.j_ratio() * 10) / 10:.1f} 배"):
            self.assertIn(token, clause, f"6.2 가 {token} 을 말하지 않는다")

    @staticmethod
    def j_ratio():
        j = KE.joint()
        return min(j["center"]["ratio"], j["step"]["ratio"])

    def test_the_pilot_cuts_the_coupon_with_the_same_rake(self):
        pt10 = next(t for t in PP.tests() if t.id == "PT-10")
        text = " ".join(pt10.steps)
        self.assertIn(f"D-502 와 같게 수평에서 {KE.ALPHA}°", text)
        self.assertIn(f"R {KE.HONE:.2f}", text)
        self.assertIn("KNIFE_WEDGE", pt10.feeds, "PT-10 결과가 쐐기각을 다시 쓰지 않는다")
        rig = next(r for r in PP.RIG if r.part.startswith("계단 칼날"))
        self.assertIn("D-502", rig.what)
        doc = PILOT.read_text(encoding="utf-8")
        self.assertIn(f"D-502 와 같게 수평에서 {KE.ALPHA}°", doc, "파일럿 문서를 다시 생성하지 않았다")

    def test_the_analysis_names_the_bound_in_its_limits(self):
        s = ANALYSIS.read_text(encoding="utf-8")
        i = s.index("<td>칼날의 수직 반력</td>")
        row = s[i:s.index("</tr>", i)]
        self.assertIn("D-502", row)
        self.assertIn(f"{self.mu_env:.2f}", row)
        self.assertIn(f"{self.mu_gl:.3f}", row)

    def test_the_fabrication_spec_no_longer_welds_the_joints(self):
        """모듈마다 따로 뜨는 홀더를 이음에서 용접하면 추종이 선다. 부재표 문구만
        고치고 용접표에 '홀더 ↔ 홀더' 행을 남겨 두었던 적이 있다."""
        import fab_spec as F
        s = FAB.read_text(encoding="utf-8")
        self.assertNotIn("계단 이음 용접", s)
        self.assertNotIn("홀더 ↔ 홀더", s, "용접표가 홀더끼리 잇는다")
        self.assertFalse([w for w in F.WELDS if "홀더" in w[0]], "계산기가 홀더 이음 용접을 센다")
        self.assertIn(f"인서트 접시머리 {KE.SCREW}", s)

    def test_the_fabrication_spec_names_the_edge_sheet_and_hardness(self):
        import fab_spec as F
        s = FAB.read_text(encoding="utf-8")
        self.assertIn(f"HRC {KE.HRC}", F.MATERIALS["SKD11"]["use"], "재료표의 인서트 경도가 D-502 와 다르다")
        self.assertEqual(s.count("D-501 · D-502 · D-602"), 2, "머리말 · 꼬리말 도면 목록에 D-502 가 없다")
        self.assertNotIn("일곱 홀더 합", s, "1,590 은 홀더가 아니라 칼날 길이의 합이다")

    def test_f005_hands_the_edge_to_d502(self):
        src = CONSOLE.read_text(encoding="utf-8")
        body = _fn(src, "tandemFabDrawing")
        self.assertNotIn("<b>정하지 않는 것</b>은 인서트", body, "F-005 가 아직 날끝을 미정이라 한다")
        self.assertIn("<b>날끝은 D-502 가", body)
        self.assertIn("'D-501 · 날끝 D-502'", body)


if __name__ == "__main__":
    unittest.main()
