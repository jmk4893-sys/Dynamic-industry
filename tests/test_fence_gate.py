"""방책 게이트는 개구에서 나온다.

카탈로그는 '안전문 프레임 □-50 L 1,000 × 4 변' — 1 m 각 틀 하나로 CS-201 반출
게이트(기둥 중심 3,000 · 방책 높이 2,400)를 막는다고 적고 있었다. 그 틀은 개구의
1/3 도 못 막는다. 3D 는 문짝 없이 문틀만 그렸다. 옵션의 셀 가드 도어(1,000 ×
2,400)에도 같은 1 m 틀이 들어가 있었다.

지금은 게이트 치수를 콘솔 뿌리 상수(GATE_*)에 두고 3D · 카탈로그 · 조립 순서가
같은 값을 읽는다:

    양개 여닫이 — 문짝 = (기둥 중심 간격 − 기둥 □100 − 틈 3) / 2
    능동짝에 인터록 하나 · 수동짝은 드롭로드 · 능동짝이 수동짝을 덮으며 닫힌다
    게이트 기둥은 □100 (방책 기둥 □60 은 문짝의 모멘트를 받지 못한다) + 상부보
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

import parts as PT
import procure as PR
import variant
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


def _part(pid, cat=PT):
    return next(p for p in cat.P if p.pid == pid)


class TestTheLeavesCloseTheOpening(unittest.TestCase):
    def test_two_leaves_fill_the_post_spacing(self):
        w, post, gap = c("GATE_W"), c("GATE_POST"), c("GATE_GAP")
        self.assertAlmostEqual(2 * c("GATE_LEAF_W") + post + 3 * gap, w, places=9)
        self.assertAlmostEqual(c("GATE_W"), c("CSCART_L") + .30, places=9,
                               msg="게이트 간격은 카트 + 양쪽 150 이다")

    def test_the_cart_passes_between_the_posts(self):
        clear = c("GATE_W") - c("GATE_POST")
        self.assertGreater(clear, c("CSCART_L") + .15, "카트가 게이트 기둥에 걸린다")

    def test_the_leaf_stands_under_the_header_and_closes_the_floor_gap(self):
        top = c("GATE_LEAF_Z0") + c("GATE_LEAF_H")
        header_bottom = 2.50 - c("GATE_POST") / 2           # 콘솔 gate() 상부보 중심 EL 2.50
        self.assertLess(top, header_bottom, "문짝이 상부보에 닿는다")
        self.assertLessEqual(c("GATE_LEAF_Z0"), .18, "문짝 밑 틈이 ISO 13857 180 을 넘는다")

    def test_the_members_are_cut_from_the_leaf(self):
        self.assertEqual(_part("P-013-05").shape.d["L"], PT.GATE_LEAF_H)
        self.assertEqual(_part("P-013-16").shape.d["L"], PT.GATE_LEAF_W - 100)
        self.assertAlmostEqual(PT.GATE_LEAF_W, c("GATE_LEAF_W") * 1000, places=6)
        self.assertNotIn("안전문 프레임", {p.name for p in PT.P},
                         "1 m 각 틀이 카탈로그에 남아 있다")
        for p in PT.P:
            if p.mod == "M-013" and p.shape.kind == "BOX" and p.shape.d["h"] == 50:
                self.assertGreater(p.shape.d["L"], 1000, f"{p.pid} 가 1 m 틀 부재다")


class TestTheGateIsCountedFromTheFence(unittest.TestCase):
    def test_leaf_members_follow_the_gate_count(self):
        self.assertEqual(PT.GATE_LEAVES, 2 * PT.FENCE_GATES)
        self.assertEqual(_part("P-013-05").qty, 2 * PT.GATE_LEAVES)
        self.assertEqual(_part("P-013-16").qty, 3 * PT.GATE_LEAVES)
        self.assertEqual(_part("P-013-17").qty, 2 * PT.GATE_LEAVES)
        self.assertEqual(_part("P-013-21").qty, 3 * PT.GATE_LEAVES)

    def test_one_interlock_per_gate_and_a_bolt_on_the_passive_leaf(self):
        self.assertEqual(_part("P-013-06").qty, PT.FENCE_GATES,
                         "게이트 인터록은 능동짝에 하나다")
        self.assertEqual(_part("P-013-22").qty, PT.FENCE_GATES)
        for pid in ("P-013-21", "P-013-22"):
            self.assertIn(pid, PR.BUY_SPEC, f"{pid} 구매 사양이 없다")

    def test_gate_posts_replace_the_fence_posts_at_the_gate(self):
        """방책 구간은 게이트 기둥에서 끝난다 — 끝 기둥을 두 번 세면 □60 이 문짝을 단다."""
        self.assertEqual(PT.FENCE_POSTS + PT.GATE_POSTS, PT._FENCE_ENDS)
        self.assertEqual(_part("P-013-01").qty, PT.FENCE_POSTS)
        post = _part("P-013-18")
        self.assertEqual(post.qty, PT.GATE_POSTS)
        self.assertGreater(post.shape.d["h"], _part("P-013-01").shape.d["h"])
        self.assertEqual(_part("P-013-19").qty, PT.GATE_POSTS)
        self.assertEqual(_part("P-013-20").qty, PT.FENCE_GATES)
        self.assertEqual(_part("P-013-20").shape.d["L"], PT._GATE_W + 100)

    def test_the_assembly_steps_name_the_leaves(self):
        steps = " ".join(" ".join(map(str, s)) for s in PT.STEPS["M-013"])
        self.assertIn(f"게이트 문짝 {PT.GATE_LEAVES}짝", steps)
        self.assertIn("수동짝", steps)
        self.assertIn(f"게이트 문형 {PT.FENCE_GATES}조", steps)


class TestTheOptionGuardDoorIsARealLeaf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.T = variant.load("twin", "parts")["parts"]

    def test_the_guard_door_leaf_fills_its_opening(self):
        T = self.T
        leaf_h = _part("P-013-23", T).shape.d["L"]
        leaf_w = _part("P-013-24", T).shape.d["L"] + 100
        self.assertAlmostEqual(leaf_w + 90 + 2 * c("GATE_GAP") * 1000, c("CG_DOOR_W") * 1000, places=6)
        self.assertAlmostEqual(leaf_h, (c("CG_Z") - .05 - c("GATE_LEAF_Z0")) * 1000, places=6)
        self.assertEqual(_part("P-013-23", T).qty, 2 * T.CELLS)
        self.assertEqual(_part("P-013-25", T).qty, 2 * T.CELLS)

    def test_every_door_hangs_on_three_hinges(self):
        T = self.T
        self.assertEqual(_part("P-013-21", T).qty, 3 * (T.GATE_LEAVES + T.CELLS))
        self.assertEqual(_part("P-013-06", T).qty, T.FENCE_GATES + T.CELLS)


class TestThe3DDrawsTheLeaves(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = CONSOLE.read_text(encoding="utf-8")
        i = html.index("      const gate=(y,sgn,x0,x1)=>{")
        cls.gate = re.sub(r"\s+", "", html[i:html.index("\n      };", i)])
        j = html.index("    function cCellGuard(")
        cls.guard = re.sub(r"\s+", "", html[j:html.index("\n    }\n", j)])
        cls.html = html

    def test_the_gate_draws_two_closed_leaves_from_the_constants(self):
        for tok in ("constgx0=CSCART.x-GATE_W/2", "GATE_LEAF_W", "GATE_LEAF_H", "GATE_POST",
                    "for(constsof[-1,1])", "//힌지×3", "능동짝인터록", "수동짝드롭로드"):
            self.assertIn(tok, self.gate, f"게이트 3D 에 {tok} 가 없다")
        self.assertNotIn("CSCART_L/2+.15", self.gate, "게이트가 개구 상수를 읽지 않는다")

    def test_the_guard_door_uses_the_same_frame(self):
        self.assertIn("DW=CG_DOOR_W", self.guard)
        self.assertIn("constlw=DW-.09-2*GATE_GAP,lz0=GATE_LEAF_Z0", self.guard)

    def test_the_module_panel_lists_the_gate(self):
        self.assertIn("CS-201 반출 게이트 — 문형 기둥×${PQ('P-013-18')}", self.html)


class TestTheSpecificationDescribesTheGate(unittest.TestCase):
    """사양서 8.1 이 문짝 치수를 적는다 — 모델이 낸 값이어야 한다."""

    def test_rfq_8_1(self):
        html = (ROOT / "docs" / "dg-hk60-rfq.html").read_text(encoding="utf-8")
        body = re.search(r'<div class="n">8\.1</div>(.*?)</div></div>', html, re.S).group(1)
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", body))
        self.assertIn(f"기둥 중심 {PT._GATE_W:,.0f} 양개 여닫이", flat)
        self.assertIn(f"문짝 {PT.GATE_LEAF_W:,.0f} × {PT.GATE_LEAF_H:,.0f} 두 짝", flat)
        self.assertIn(f"문짝 밑 틈은 {c('GATE_LEAF_Z0') * 1000:.0f}", flat)
        self.assertIn("수동짝은 드롭로드", flat)


if __name__ == "__main__":
    unittest.main()
