"""배기 관경은 풍량에서 나온다.

콘솔의 배기 헤더는 지선 Ø400 × 2 · 본관 Ø460 · 경계 플랜지 Ø600 이었고, 카탈로그는
Ø600 × 3 m 여덟 본이었다. 어느 것도 풍량에서 나오지 않았다 — REV.20 의 헤더
치수였다. 사양서 1.4 는 "배기 헤더는 2 셀 유량으로 관경을 정한다" 고 요구한다.

    가열실 지선 = 셔터 두 장을 가두는 봉쇄 유량 (2√2 × 부력 교환유량) + 누설 — 일정
    셀 지선     = 칼날 뒤 슬롯 후드 2.6·L·v·X (셀마다)
    관경        = 운반 속도 8 ~ 12.5 m/s 를 지키는 가장 작은 표준 관경

콘솔의 DUCT_D_* 가 모델의 선택과 같고, 3D · 카탈로그 · 제작 지침서 · 사양서가
그 관경과 풍량을 쓰는지 여기서 본다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import airlock as AIR
import exhaust as EXH
import fab_spec as F
import parts as PT
import plc_model as PLC
import procure as PR
import variant
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
CAL = ROOT / "docs" / "dg-hk60-analysis.html"


def _plain(path):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", path.read_text(encoding="utf-8")))


class TestTheFlowsComeFromTheMachine(unittest.TestCase):
    def test_containment_is_the_integral_not_a_guess(self):
        sh = EXH.shutter()
        self.assertAlmostEqual(sh["q_ex"], AIR.exchange_flow(AIR.OPEN_H), places=12)
        self.assertAlmostEqual(sh["q_buoy"], 2 * math.sqrt(2) * sh["q_ex"], places=12)
        self.assertEqual(sh["q"], max(sh["q_buoy"], sh["q_face"]))
        self.assertAlmostEqual(sh["q_face"], EXH.CAPTURE_V * AIR.OPEN_W * AIR.OPEN_H, places=12)

    def test_two_shutters_because_the_plc_only_blocks_same_side(self):
        """PLC 가 막는 것은 같은 쪽 두 단이다 — 투입·배출이 겹치면 두 장이 열린다."""
        names = {d.name for d in PLC.DERIVED} if hasattr(PLC, "DERIVED") else set()
        src = (ROOT / "tools" / "plc_model.py").read_text(encoding="utf-8")
        for rule in ("IN_SHUTTER_MUTEX", "OUT_SHUTTER_MUTEX"):
            self.assertIn(f'Derived("{rule}"', src)
        self.assertNotIn("CROSS_SHUTTER_MUTEX", src + " ".join(names),
                         "교차 인터록이 생겼으면 봉쇄 유량은 셔터 한 장이다 — N_OPEN 을 내린다")
        self.assertEqual(EXH.N_OPEN, 2)
        self.assertAlmostEqual(EXH.chamber(), 2 * EXH.shutter()["q"] + EXH.leak(), places=12)

    def test_the_hood_reaches_the_leading_tip(self):
        hd = EXH.hood()
        self.assertAlmostEqual(hd["L"], c("KNIFE_W"), places=12)
        self.assertAlmostEqual(hd["X"], c("KNIFE_DEPTH") + EXH.HOOD_SETBACK, places=12)
        self.assertAlmostEqual(hd["q"], 2.6 * hd["L"] * 0.5 * hd["X"], places=12)

    def test_totals(self):
        self.assertAlmostEqual(EXH.total(2) - EXH.total(1), EXH.hood()["q"], places=12)


class TestTheConsoleHoldsWhatTheModelPicks(unittest.TestCase):
    def test_every_segment_is_the_smallest_size_in_the_band(self):
        for s in EXH.segments():
            self.assertEqual(EXH.pick(s["q"], s["lo"]), s["d"],
                             f"{s['name']} Ø{s['d']:.0f} — 모델은 Ø{EXH.pick(s['q'], s['lo'])} 를 고른다")
        for b in EXH.checks():
            self.assertTrue(b.ok, f"{b.id} {b.what} {b.v:.1f} m/s — 대역 밖")

    def test_the_old_boundary_was_too_slow(self):
        """Ø600 은 1 셀에서도 2 셀에서도 흄이 쌓이는 속도였다."""
        old = EXH.legacy()
        self.assertLess(old["bound_1"], EXH.V_MIN)
        self.assertLess(old["bound_2"], EXH.V_MIN)

    def test_the_header_is_sized_for_two_cells(self):
        """사양서 1.4 — 헤더는 2 셀 유량으로, 1 셀에서도 하한 위."""
        self.assertLessEqual(EXH.velocity(EXH.total(2), EXH.D_HDR), EXH.V_MAX)
        self.assertGreaterEqual(EXH.velocity(EXH.total(1), EXH.D_HDR), EXH.V_MIN)


class TestTheDrawingsUseTheSizes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = CONSOLE.read_text(encoding="utf-8")
        i = html.index("    function cBoundary(){")
        cls.body = re.sub(r"\s+", "", html[i:html.index("\n    }\n", i)])
        cls.flat = re.sub(r"\s+", "", html)

    def test_the_3d_header(self):
        for tok in ("DUCT_D_HC/2", "DUCT_D_CELL/2", "DUCT_D_HDR1/2", "DUCT_D_HDR/2",
                    "for(letn=0;n<LY.cells;n++)", "//블리드댐퍼"):
            self.assertIn(tok, self.body, f"cBoundary 가 {tok} 를 쓰지 않는다")
        for old in (",.20,dz-3.2", ",.23,", ",.30,.10"):
            self.assertNotIn(old, self.body, f"옛 관경 반지름 {old} 이 남아 있다")

    def test_the_sheets_and_panel(self):
        self.assertIn("배기덕트플랜지Ø${mm(DUCT_D_HDR)}", self.flat)
        self.assertIn("`경계덕트플랜지Ø${mmv(DUCT_D_HDR)}`", self.flat)
        self.assertIn("Ø${Math.round(DUCT_D_HDR*1000)}·M12×12등분", self.flat)
        for old in ("'배기헤더본관Ø460'", "'경계덕트플랜지Ø600'", "배기덕트플랜지Ø600·EL"):
            self.assertNotIn(old, self.flat)


class TestTheCatalogFollowsThePath(unittest.TestCase):
    def _p(self, pid, cat=PT):
        return next(p for p in cat.P if p.pid == pid)

    def test_sizes(self):
        for pid, d in (("P-017-01", EXH.D_HDR), ("P-017-07", EXH.D_HDR1),
                       ("P-017-08", EXH.D_HC), ("P-017-09", EXH.D_CELL), ("P-002-24", EXH.D_HC)):
            self.assertEqual(self._p(pid).shape.d["od"], d, f"{pid} 관경이 콘솔과 다르다")
        self.assertEqual(self._p("P-017-02").shape.d["id"], EXH.D_HDR)

    def test_lengths_come_from_the_console_route(self):
        self.assertAlmostEqual(PT.L_HDR1, c("CTBL_CX") * 1000 - PT._CST.HC.cx * 1000, places=6)
        self.assertEqual(self._p("P-017-07").qty, math.ceil(PT.L_HDR1 / 3000 - 1e-9))
        self.assertEqual(self._p("P-017-01").qty, math.ceil(PT.L_HDR2 / 3000 - 1e-9))
        self.assertEqual(self._p("P-017-02").qty, 2 * self._p("P-017-01").qty)

    def test_the_bleed_damper_is_bought_to_a_spec(self):
        self.assertEqual(self._p("P-017-12").qty, 1)
        self.assertIn("P-017-12", PR.BUY_SPEC)

    def test_the_option_adds_a_branch_and_a_damper_per_cell(self):
        T = variant.load("twin", "parts")["parts"]
        self.assertEqual(self._p("P-017-09", T).qty, T.CELLS)
        self.assertEqual(self._p("P-017-14", T).qty, T.CELLS)
        self.assertGreater(self._p("P-017-13", T).qty, 0)
        self.assertEqual(self._p("P-017-01", T).shape.d["od"], EXH.D_HDR, "옵션도 같은 헤더를 쓴다")

    def test_the_boundary_joint_names_its_size(self):
        j12 = next(j for j in F.JOINTS if j["id"] == "J12")
        self.assertIn(f"Ø{EXH.D_HDR:.0f}", j12["name"])
        self.assertIn(("M-017", "경계 덕트", f"Ø{EXH.D_HDR:.0f} t3.0", "SS400", "부압 · 지지 간격 3,000"),
                      F.MEMBERS)


class TestTheDocumentsCarryTheFlows(unittest.TestCase):
    def test_rfq(self):
        t = _plain(RFQ)
        self.assertIn(f"{EXH.total(1):.2f} m³/s ({EXH.total(1) * 3600:,.0f} m³/h) · 일정", t)
        self.assertIn(f"표준 {EXH.total(1) * 3600:,.0f} m³/h · 옵션 {EXH.total(2) * 3600:,.0f} m³/h", t)
        self.assertIn(f"경계 덕트 Ø{EXH.D_HDR:.0f} 이 2 셀 "
                      f"{EXH.velocity(EXH.total(2), EXH.D_HDR):.1f} m/s · 1 셀 "
                      f"{EXH.velocity(EXH.total(1), EXH.D_HDR):.1f} m/s", t)
        self.assertIn(f"헤더 ① Ø{EXH.D_HDR1:.0f} · 셀 지선 Ø{EXH.D_CELL:.0f} · 헤더 ② · 경계 Ø{EXH.D_HDR:.0f}", t)

    def test_cal001(self):
        t = _plain(CAL)
        self.assertIn("8.2 배기 — 경계 덕트 Ø600 은 어떤 풍량에서 나왔나", t)
        self.assertIn(f"표준 {EXH.total(1):.2f} · 옵션 {EXH.total(2):.2f} m³/s", t)
        for q in EXH.requirements():
            self.assertIn(q.id, t)


if __name__ == "__main__":
    unittest.main()
