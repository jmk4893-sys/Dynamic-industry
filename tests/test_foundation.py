"""기초도 D-602 · 카탈로그 · 제작 지침서가 한 앵커군 표를 읽는다.

셋이 한동안 서로 다른 기호를 썼다. 기초도는 A1 = 가열실 · A2 = 냉각 랙 · A11 = CE-201
인데, 카탈로그는 가열실 판을 A2 · 냉각 랙 판을 A11 · 방책 기둥을 A11 · CE-201 다리를
결번 A12 로 적었고, 제작 지침서는 가열실을 A2 로 부르며 CE-201 을 판에 구멍이 없는
M16 × 4 로 적었다. 기초도의 판은 손으로 적은 크기라 스테이션 경계 일곱 곳에서 이웃
장비의 판이 서로 겹쳤고(최대 200), RH-201 안쪽 기둥은 KG-101 문형 기둥과 같은 좌표에
서서 '한 기둥이 둘을 받는다' 며 앵커를 하나만 셌다 — 카탈로그는 기둥 둘을 샀다.

    parts.ANCHOR_GROUPS (기호 · 판 품번 · 앵커 · hef)
      → 부품도 체결 칸 (anchor_fix) · 콘솔 ANCHORS (gen_parts_js)
      → 기초도 GROUPS (판은 PLT(품번)) · 제작 지침서 10.1 (fab_spec.ANCHORS)
      → tools/foundation.py 가 같은 좌표로 판 사이 틈을 센다

여기서 사슬이 끊기면 걸린다.
"""

import pathlib
import re
import unittest
from collections import Counter

from . import _path  # noqa: F401

import fab_spec as F
import foundation as FD
import parts as PT
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


def _part(pid):
    return next(p for p in PT.P if p.pid == pid)


def _fn(src, name):
    i = src.index(f"function {name}(")
    j = src.index("\n    function ", i + 10)
    return src[i:j]


class TestOneAnchorTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.body = _fn(cls.src, "foundationDrawing")
        cls.flat = re.sub(r"\s+", "", cls.body)
        cls.ids = [a[0] for a in PT.ANCHOR_GROUPS]

    def test_the_drawing_the_catalog_and_the_spec_use_the_same_ids(self):
        drawing = re.findall(r"\{id:'(A\d+)',eq:", self.body)
        self.assertEqual(drawing, self.ids, "기초도 앵커군이 카탈로그 표와 다르다")
        self.assertEqual([a["id"] for a in F.ANCHORS], self.ids, "제작 지침서 앵커군이 카탈로그 표와 다르다")
        m = re.search(r"const ANCHORS=(\[.*?\]);", self.src)
        self.assertIsNotNone(m, "콘솔에 ANCHORS 가 없다")
        self.assertEqual(re.findall(r'"id":"(A\d+)"', m.group(1)), self.ids,
                         "콘솔 ANCHORS 가 카탈로그 표와 다르다 — gen_parts_js --write")

    def test_the_retired_ids_stay_retired(self):
        """A9 (WR-101 권취 문형) · A12 (BS-301 롤 새들) — 권취부 철거. 당기지 않는다."""
        for gone in PT.ANCHOR_RETIRED:
            self.assertNotIn(gone, self.ids)
            self.assertNotIn(f"({gone})", " ".join(p.fix for p in PT.P),
                             f"부품도 체결 칸이 결번 {gone} 를 부른다")
        nums = [int(a[1:]) for a in self.ids]
        self.assertEqual(nums, sorted(nums), "기호가 번호 순이 아니다")

    def test_every_anchored_plate_is_in_the_table_and_its_label_is_the_table(self):
        """부품도 체결 칸의 기호 · 규격 · 매입깊이 · 개수는 표와 판의 구멍에서 나온다."""
        in_table = {a[2] for a in PT.ANCHOR_GROUPS}
        for p in PT.P:
            for aid in re.findall(r"\((A\d+)(?:~A\d+)?\)", p.fix):
                self.assertIn(p.pid, in_table, f"{p.pid} 가 {aid} 를 부르지만 앵커군 표에 없다")
        for aid, _eq, pid, size, hef, _grade in PT.ANCHOR_GROUPS:
            p = _part(pid)
            self.assertEqual(p.shape.kind, "PL", f"{aid} 의 {pid} 가 판이 아니다")
            holes = p.shape.d["holes"]
            self.assertTrue(holes, f"{pid} 에 앵커 구멍이 없다")
            self.assertIn(f"{size} ({PT.anchor_label(pid)}) ×{len(holes)} · hef {hef}", p.fix,
                          f"{pid} 체결 칸이 앵커군 표와 다르다")
            d = int(size[1:])
            for _x, _y, dh in holes:
                self.assertEqual(dh, d + 2, f"{pid} 구멍 Ø{dh} 가 앵커 {size} + 2 가 아니다")

    def test_the_ce201_anchor_is_what_its_leg_plate_can_take(self):
        """CE-201 다리 판은 200 □ · 구멍 Ø14 둘 — 지침서의 M16 × 4 는 판에 없는 규격이었다."""
        a = next(a for a in F.ANCHORS if a["id"] == "A11")
        self.assertEqual((a["size"], a["n"], a["part"]), ("M12", 2, "P-008-03"))

    def test_the_drawing_reads_the_plate_from_the_catalog(self):
        self.assertTrue("returnObject.assign(g,{part:a.part,plate:PLT(a.part),anchor:a})" in self.flat,
                        "기초도의 판이 앵커군 표의 품번에서 오지 않는다")
        self.assertIsNone(re.search(r"\{id:'A\d+',[^}]*plate:\[?\.\d", self.flat),
                          "기초도가 판 크기를 숫자로 적는다")
        # 3D 도 같은 판 — PLT('…') 가 부르는 품번은 모두 카탈로그에 있다
        called = set(re.findall(r"PLT\('(P-\d{3}-\d{2})'\)", self.src))
        self.assertTrue(called, "3D 가 카탈로그 판을 읽지 않는다")
        for pid in called:
            self.assertTrue(any(p.pid == pid for p in PT.P), f"PLT('{pid}') 가 카탈로그에 없다")
        for pid in {a[2] for a in PT.ANCHOR_GROUPS} - {"P-006-07"}:
            self.assertIn(f"'{pid}'", self.src, f"3D 가 {pid} 판을 그리지 않는다")

    def test_the_table_shows_the_anchor_from_the_table(self):
        """기초도 표의 앵커 칸은 ANCHORS 에서 — 규격 · 개수 · 매입깊이를 손으로 적지 않는다."""
        tbl = self.body[self.body.index("GROUPS.map("):]
        for token in ("g.anchor.size", "g.anchor.n", "g.anchor.hef", "g.part"):
            self.assertTrue(token in tbl, f"기초도 표가 {token} 을 쓰지 않는다")
        self.assertNotRegex(self.body, r"M(10|12|16|20|24)\s*[×x]\s*\d", "기초도가 앵커 규격을 손으로 적는다")


class TestThePlatesDoNotOverlap(unittest.TestCase):
    """판은 카탈로그 품번 그대로이고, 좌표는 3D 가 기둥을 세운 상수다."""

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.flat = re.sub(r"\s+", "", _fn(cls.src, "foundationDrawing"))
        cls.groups = FD.groups()

    def test_the_mirror_reads_the_same_expressions_as_the_drawing(self):
        """foundation.py 는 D-602 GROUPS 의 좌표식을 한 줄씩 옮긴 것이다 — 식이 갈라지면 여기서 걸린다."""
        for gid, expr in (
            ("A1", "pts:grid(rackColXs(CST.HC.cx,CST.HC.w),[-RACK_COL_Y,RACK_COL_Y])"),
            ("A2", "pts:grid(rackColXs(CST.GC.cx,CST.GC.w,GC_COL_INSET),[-RACK_COL_Y,RACK_COL_Y])"),
            ("A3", "pts:grid([CMAST_IN],[-HALF,HALF])"),
            ("A4", "pts:grid([CMAST_OUT],[-HALF,HALF])"),
            ("A5", "pts:grid([CMAST_GL],[-HALF,HALF])"),
            ("A6", "pts:grid([CMAST_GU],[-HALF,HALF])"),
            ("A7", "pts:grid([CRAIL_X0,CRAIL_X1],[-CGY,CGY])"),
            ("A8", "pts:grid(tblColXs(),tblColYs())"),
            ("A10", "pts:grid([CRAIL_X0],[-(CFENCE_YN+.10),RH_POST_IN])"),
            ("A11", "pts:grid([CE_LEG_X0,CE_LEG_X1],[CE_LEG_Y0,CE_LEG_Y1])"),
            ("A13", "pts:[[CKC_SADDLE.x,CKC_RACK_Y]]"),
            ("A14", "pts:grid([QI_X],[-1.02,1.02])"),
            ("A15", "pts:fencePts"),
            ("A16", "pts:grid([GX0,GX1],[-CFENCE_YN])"),
        ):
            i = self.flat.index("{id:'%s'," % gid)
            row = self.flat[i:self.flat.find("{id:'", i + 1)]
            self.assertTrue(expr in row, f"D-602 {gid} 좌표식이 foundation.py 와 갈라졌다 — {expr}")
        # assertIn 은 실패하면 시트 전체를 덤프한다 — assertTrue 로 본다
        self.assertTrue("HALF=FORK_HALF_STD;" in self.flat, "포크 반폭이 납품 배치 상수가 아니다")
        self.assertTrue("constGX0=CSCART.x-GATE_W/2,GX1=CSCART.x+GATE_W/2;" in self.flat,
                        "게이트 기둥 자리가 CS-201 중심에서 나오지 않는다")
        self.assertIn("const CSCART=V((CE_X0+CE_X1)/2,", self.src, "게이트 중심이 CE-201 중심이 아니다")
        self.assertTrue("/FENCE_PITCH-1e-9)" in self.flat, "방책 기둥 피치가 공용 상수가 아니다")
        self.assertIn("constCKC_SADDLE=V(CKC_X,", self.src.replace(" ", ""), "새들 x 가 CKC_X 가 아니다")

    def test_no_two_plates_come_closer_than_the_grout_gap(self):
        """스테이션 경계 일곱 곳에서 판이 겹쳤다 — GL 포크 ↔ GC 첫 기둥 200 · EX/GL 포크 ↔ KG 문형 120 …"""
        bad = FD.clashes()
        self.assertEqual(bad, [], "판이 겹치거나 30 mm 안으로 붙는다: "
                         + ", ".join(f"{a}↔{b} {g * 1000:.0f} mm" for a, b, g in bad[:8]))
        self.assertGreaterEqual(FD.min_gap(), FD.GAP_MIN - 1e-9)

    def test_the_mirror_catches_an_overlap(self):
        """시험이 겹침을 실제로 본다 — 냉각 랙 끝기둥을 스테이션 끝으로 되돌리면 GL·GU 포크 판과 겹친다."""
        orig = FD._rack_cols
        try:
            FD._rack_cols = lambda cx, w, inset=0.0: orig(cx, w, 0.0)
            pairs = {(a, b) for a, b, _g in FD.clashes()}
        finally:
            FD._rack_cols = orig
        self.assertTrue({("A2", "A5"), ("A2", "A6")} & pairs or {("A5", "A2"), ("A6", "A2")} & pairs,
                        f"인셋을 빼도 겹침을 못 본다: {sorted(pairs)[:6]}")

    def test_each_plate_count_is_the_catalog_quantity(self):
        """기초도가 세는 판 수 = 카탈로그가 사는 판 수 (포크 판 하나를 A3~A6 넷이 나눈다)."""
        n = Counter()
        for _aid, pid, _lw, pts in self.groups:
            n[pid] += len(pts)
        for pid, k in n.items():
            self.assertEqual(k, _part(pid).qty, f"{pid} 기초도 {k} ↔ 카탈로그 {_part(pid).qty}")

    def test_the_monorail_inner_post_is_not_the_gantry_portal_post(self):
        """정밀 문형에 호이스트를 싣지 않는다 — 안쪽 기둥은 문형 기둥 바깥에 따로 선다."""
        rh_in, cgy = c("RH_POST_IN"), c("CGY")
        self.assertLess(rh_in, -cgy, "안쪽 기둥이 문형 기둥 안쪽(통로)에 선다")
        (L7, W7), (L10, W10) = FD.plate("P-005-02"), FD.plate("P-006-03")
        self.assertGreaterEqual(abs(rh_in + cgy) - (W7 + W10) / 2, FD.GAP_MIN - 1e-9,
                                "안쪽 기둥 판이 문형 판에 붙는다")
        self.assertAlmostEqual(PT.RH_POSTS[0], rh_in * 1000, places=6, msg="카탈로그 기둥 자리가 콘솔과 다르다")
        self.assertEqual(len(PT.RH_POSTS), _part("P-006-03").qty)
        self.assertIn("pts:grid([CRAIL_X0],[-(CFENCE_YN+.10),RH_POST_IN])",
                      re.sub(r"\s+", "", self.src), "3D/기초도가 안쪽 기둥을 문형 좌표에 세운다")

    def test_the_fence_is_one_pitch_everywhere(self):
        """방책 기둥은 카탈로그 · 3D · 기초도가 같은 피치 · 같은 구간 · 같은 끝 공유 규칙으로 센다."""
        self.assertEqual(PT._FENCE_PITCH, c("FENCE_PITCH") * 1000)
        a15 = next(pts for aid, _p, _lw, pts in self.groups if aid == "A15")
        self.assertEqual(len(a15), PT.FENCE_POSTS, "기초도 방책 기둥 수가 카탈로그와 다르다")
        self.assertIn("Math.ceil(L/FENCE_PITCH-1e-9)", re.sub(r"\s+", "", self.src),
                      "3D 방책이 공용 피치로 칸을 나누지 않는다")

    def test_no_pad_sits_on_an_anchor_plate(self):
        """반 · 스키드 · 냉각 급기 유닛(P4)의 패드는 앵커 판과 떨어진다 — 급기 유닛은 냉각 랙 판 50 밖."""
        self.assertEqual(FD.pad_clashes(), [], "패드가 앵커 판에 얹힌다")
        for pid, expr in (("P1", "x:CST.HC.x0+.6,y:-2.88,w:1.60,d:.86"),
                          ("P2", "x:CST.GC.x0+.5,y:-2.90,w:1.50,d:.86"),
                          ("P3", "x:CBJ_X,y:-2.62,w:1.50,d:1.00"),
                          ("P4", "x:CST.GC.cx+(CST.GC.w/2-GC_COL_INSET)/2,y:RACK_COL_Y+.25+PARTS.find")):
            i = self.flat.index("{id:'%s'," % pid)
            self.assertTrue(expr in self.flat[i:i + 260], f"D-602 {pid} 자리가 foundation.pads() 와 갈라졌다")

    def test_the_totals_on_the_title_block_are_counted(self):
        self.assertTrue("constNPL=GROUPS.reduce((a,g)=>a+g.pts.length,0),"
                        "NAN=GROUPS.reduce((a,g)=>a+g.pts.length*g.anchor.n,0);" in self.flat,
                        "표제란의 판 · 앵커 수를 세지 않는다")
        self.assertTrue("판${NPL}·앵커${NAN}" in self.flat, "표제란이 판 · 앵커 수를 적지 않는다")


if __name__ == "__main__":
    unittest.main()
