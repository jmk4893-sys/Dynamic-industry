"""옵션(DG-HK120C)을 표준(DG-HK60C)과 같은 코드로 푸는 장치를 지킨다.

옵션은 뿌리 상수 자리에 콘솔 배치 설정(HK120C)의 값을 핀으로 박고 설계
모듈을 새로 불러 푼다 (tools/console_consts.layout · tools/variant.load).
이 장치가 틀리면 두 가지가 동시에 틀린다 — 옵션 견적이 엉뚱한 기계를
세고, 표준 결과가 옵션 핀에 오염된다. 둘 다 조용히 틀리므로 여기서 묻는다.
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import _path  # noqa: F401

import console_consts as C
import variant


class TestLayoutPins(unittest.TestCase):
    def test_compact_pin_is_the_unpinned_console(self):
        """'compact' 핀은 핀이 없는 상태와 같아야 한다 — 표준이 곧 콘솔이다."""
        console = C.CONSOLE.read_text(encoding="utf-8")
        bare = C.env(console)
        with C.layout("compact"):
            pinned = C.env(console)
        self.assertEqual(set(bare), set(pinned))
        for k, v in bare.items():
            if k == "CST":
                continue
            self.assertEqual(v, pinned[k], k)

    def test_base_cells_is_the_console_compact_layout(self):
        """CELLS 는 콘솔에 낱개 const 가 없다 — 표준 배치 설정의 cells 와 같아야 한다."""
        self.assertEqual(C.layouts()["compact"]["cells"], C.BASE_CELLS)
        self.assertEqual(C.const("CELLS"), C.BASE_CELLS)

    def test_twin_pins_come_from_the_console_layout(self):
        """옵션의 단수·램프 수·셀 수는 콘솔 HK120C 가 쥔 값이다 — 여기서 다시 적지 않는다."""
        tw = C.layouts()["twin"]
        with C.layout("twin"):
            for field, root in C.LAYOUT_ROOTS.items():
                self.assertEqual(C.const(root), tw[field], root)
            self.assertEqual(C.active(), "twin")
        self.assertEqual(C.active(), "compact", "핀이 컨텍스트 밖으로 샜다")

    def test_derived_constants_follow_the_pin(self):
        """DECKS 에서 파생된 상수는 핀 값으로 다시 풀려야 한다 — 유리 냉각 랙 단수가 그 예다."""
        with C.layout("twin"):
            self.assertEqual(C.const("GCOOL_DECKS"), C.const("DECKS"))
        self.assertEqual(C.const("GCOOL_DECKS"), C.const("DECKS"))


class TestVariantLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import parts
        cls.base = parts
        cls.twin = variant.load("twin", "parts")["parts"]

    def test_base_module_is_untouched(self):
        """옵션을 불러도 표준 모듈은 그 객체 그대로 남는다."""
        import parts
        self.assertIs(parts, self.base)
        self.assertEqual(parts.DECKS, C.layouts()["compact"]["decks"])
        self.assertIsNot(self.twin, self.base)

    def test_twin_catalog_is_solved_with_twin_roots(self):
        tw = C.layouts()["twin"]
        self.assertEqual(self.twin.DECKS, tw["decks"])
        self.assertEqual(self.twin.LAMPS, tw["lamps"])

    def test_twin_chamber_grows_by_derivation_not_by_copy(self):
        """7 단 가열실은 적은 것이 아니라 풀린 것이다 — 기둥이 두 단 높이만큼 길어진다."""
        b = {p.pid: p for p in self.base.P}
        t = {p.pid: p for p in self.twin.P}
        col_b, col_t = b["P-002-01"].shape.d["L"], t["P-002-01"].shape.d["L"]
        two_decks = 2 * self.base.CDECK_DZ
        self.assertAlmostEqual(col_t - col_b, two_decks, delta=1.0)
        self.assertEqual(t["P-002-18"].qty, C.layouts()["twin"]["lamps"])


def _node():
    return shutil.which("node")


def _run_js(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
    out = subprocess.run([_node(), f.name], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


def _const_line(src, name):
    m = re.search(r"\n\s*const %s=[^;]*;" % re.escape(name), src)
    assert m, name
    return m.group(0).strip()


class TestTheNestedPinDoesNotLeak(unittest.TestCase):
    def test_the_standard_values_are_the_standard_inside_the_option(self):
        """옵션 안에서 표준을 물어도 표준이 나와야 한다 — 부하표가 분기를 가를 때 쓴다.
        핀을 박은 채 배치 객체를 풀면 HK120C 의 lamps:2*LAMPS 가 두 번 곱해진다."""
        with C.layout("twin"):
            lays = C.layouts()
            with C.layout("compact"):
                self.assertEqual(C.const("LAMPS"), lays["compact"]["lamps"])
        self.assertEqual(lays, C.layouts())
        self.assertEqual(lays["twin"]["lamps"], 2 * lays["compact"]["lamps"])


class TestTheOptionCatalogue(unittest.TestCase):
    """옵션 카탈로그가 옵션의 기계를 세는가 — 셀별 · 공용 · 옵션 전용."""

    @classmethod
    def setUpClass(cls):
        import option
        cls.O = option
        cls.B, cls.T = option.PT_B, option.PT_T

    def test_cell_parts_are_counted_once_per_cell(self):
        b = {p.pid: p for p in self.B.P}
        for p in self.T.P:
            if not self.T.is_per_cell(p) or p.pid not in b:
                continue
            q = b[p.pid]
            if q.shape.label() == p.shape.label():
                self.assertEqual(p.qty, self.T.CELLS * q.qty, p.pid)

    def test_the_per_cell_modules_are_whole_cells(self):
        for m in self.T.PER_CELL:
            kb, kt = self.B.module_kg(m), self.T.module_kg(m)
            self.assertAlmostEqual(kt, self.T.CELLS * kb, delta=1e-6 * kt, msg=m)

    def test_anchor_masses_are_one_cell_not_two(self):
        """앵커는 셀 하나의 테이블·갠트리를 받친다 — 두 셀을 더해 넘기면 앵커가 과대설계된다."""
        for sym in ("M_TABLE", "M_GANTRY"):
            self.assertAlmostEqual(self.T.mass(sym), self.B.mass(sym), places=6, msg=sym)
        self.assertGreater(self.T.mass("M_CHAMBER"), self.B.mass("M_CHAMBER"), "7 단 가열실이 가볍다")

    def test_the_option_can_be_bought_and_every_purchase_is_specified(self):
        tot = self.O.totals()
        self.assertEqual(tot["unbuyable"], [], "옵션에 살 수 없는 치수가 있다")
        with self.O.pinned():
            miss = [p.pid for p in self.T.P if p.buy and p.pid not in self.O.PR_T.BUY_SPEC]
        self.assertEqual(miss, [], f"발주 사양이 없는 옵션 구매품: {miss}")

    def test_option_only_specs_are_option_only_parts(self):
        """옵션 전용 사양이 표준 카탈로그의 품번을 덮어쓰면 표준 발주가 조용히 바뀐다."""
        base = {p.pid for p in self.B.P}
        opt = {p.pid for p in self.T.P if p.buy}
        for pid in self.O.PR_T.OPTION_BUY_SPEC:
            self.assertNotIn(pid, base, pid)
            self.assertIn(pid, opt, pid)

    def test_the_chamber_wall_is_split_by_the_stock_sheet(self):
        """7 단 외피는 5,100 이라 8×20 시트 폭 2,398 에 두 장으로 안 든다 — 세 장이다."""
        for pt in (self.B, self.T):
            end = {p.pid: p for p in pt.P}["P-002-10"]
            self.assertLessEqual(end.shape.d["W"], 2438 - 2 * 20 + 1e-6)
            self.assertAlmostEqual(end.shape.d["W"] * end.qty, pt._HC_WALL_H, places=6)
        self.assertGreater({p.pid: p for p in self.T.P}["P-002-10"].qty,
                           {p.pid: p for p in self.B.P}["P-002-10"].qty)

    def test_the_insulation_covers_the_faces_the_thermal_check_uses(self):
        for pt in (self.B, self.T):
            board = {p.pid: p for p in pt.P}["P-002-14"]
            area = board.qty * board.shape.d["L"] * board.shape.d["W"] / 1e6
            self.assertGreaterEqual(area, pt.HC_AREA, "단열 보드가 외피 면을 다 못 덮는다")
            self.assertLess(area, 1.25 * pt.HC_AREA, "단열 보드가 면보다 한참 많다")

    def test_the_runway_section_is_chosen_by_the_longest_span(self):
        for pt in (self.B, self.T):
            self.assertLessEqual(pt.RH_DEFL, pt.RH_SPAN / 500, "런웨이 처짐이 L/500 을 넘는다")
            lighter = [s for s in pt._RH_HB if s[0] < pt.RH_SEC[0]]
            for s in lighter:
                self.assertGreater(pt.rh_defl(s, pt.RH_SPAN), pt.RH_SPAN / 500,
                                   f"더 가벼운 H-{s[0]} 로도 된다")
        self.assertGreater(self.T.RH_N, 1, "15 m 본선을 정척 한 본으로 샀다")

    def test_the_steel_density_is_the_specification_value(self):
        import fab_spec
        self.assertEqual(self.B._RHO_STEEL, fab_spec.MATERIALS["SS400"]["rho"])

    def test_stock_tables_have_one_home(self):
        import procure
        import stock
        self.assertIs(procure.PLATE_STOCK, stock.PLATE_STOCK)
        self.assertIs(procure.PLATE_THICK, stock.PLATE_THICK)


class TestTheMonorailHeightIsTheConsoles(unittest.TestCase):
    """RH-201 레일면 EL 은 콘솔 cRhZ 의 거울이다 — 두 배치 모두 node 로 대조한다."""

    def test_both_layouts_match_the_console_function(self):
        if not _node():
            self.skipTest("node 가 없다")
        import option
        src = C.CONSOLE.read_text(encoding="utf-8")
        fn = re.search(r"\n    function crownTopOf\(decks\)\{.*?\n    \}\n", src, re.S).group(0)
        lines = "\n".join(_const_line(src, n) for n in (
            "RH_CLR", "rhMinZ", "RH_Z", "ductZOf"))
        head = ("const CDECK_Z0=%r,CDECK_DZ=%r;const cDeckZ=k=>CDECK_Z0+CDECK_DZ*(k+.5);"
                "const SKIN_TOP=%r,COPE_H=%r;const CROWN_CLR=%r;const DECKS=%d;"
                % (C.const("CDECK_Z0"), C.const("CDECK_DZ"), C.const("SKIN_TOP"),
                   C.const("COPE_H"), C.const("CROWN_CLR"), int(C.const("DECKS"))))
        tw = C.layouts()["twin"]["decks"]
        js = _run_js(head + fn + lines + (
            "\nconst c=Math.max(RH_Z,Math.ceil(rhMinZ(DECKS)*20)/20);"
            f"\nconst t=Math.max(ductZOf({tw})+.55,Math.ceil(rhMinZ({tw})*20)/20);"
            "\nprocess.stdout.write(JSON.stringify({c,t}));"))
        self.assertAlmostEqual(option.PT_B.RH_Z, js["c"] * 1000, places=3)
        self.assertAlmostEqual(option.PT_T.RH_Z, js["t"] * 1000, places=3)
        src_c = re.sub(r"\s", "", src)
        self.assertIn("constcRhZ=()=>{constL=LC();returnMath.max(twinView()?cDuctZ()+.55:RH_Z,"
                      "Math.ceil(rhMinZ(L.decks)*20)/20)};", src_c,
                      "콘솔 cRhZ 가 바뀌었다 — parts.py 의 거울을 다시 본다")


class TestTheLoadScheduleIsTheConsoles(unittest.TestCase):
    """부하표 거울 — 표준은 콘솔 E-001 식 그대로, 옵션은 분기를 셀 수만큼."""

    def test_the_standard_matches_the_console(self):
        if not _node():
            self.skipTest("node 가 없다")
        import electrical as EL
        src = C.CONSOLE.read_text(encoding="utf-8")
        i = src.index("    const LINE_V=")
        j = src.index("    const DWG_NO=")
        js = _run_js(f"const LAMPS={int(C.const('LAMPS'))};\n" + src[i:j]
                     + "\nprocess.stdout.write(JSON.stringify({CONNECTED_KW,CONNECTED_KVA,FLA,DEMAND_KW,"
                       "TR_KVA,MAIN_AT,MAIN_AF,SCCR_KA}));")
        py = EL.summary()
        self.assertAlmostEqual(py["kw"], js["CONNECTED_KW"], places=9)
        self.assertAlmostEqual(py["kva"], js["CONNECTED_KVA"], places=9)
        self.assertAlmostEqual(py["fla"], js["FLA"], places=9)
        for k, j_ in (("demand", "DEMAND_KW"), ("tr_kva", "TR_KVA"), ("main_at", "MAIN_AT"),
                      ("main_af", "MAIN_AF"), ("sccr_ka", "SCCR_KA")):
            self.assertEqual(py[k], js[j_], k)

    def test_the_option_doubles_the_branches_not_the_breakers(self):
        import option
        b = option.EL_B.branches()
        with option.pinned():
            t = option.EL_T.branches()
            st = option.EL_T.summary()
        cells = C.layouts()["twin"]["cells"]
        self.assertEqual(len(t), cells * len(b))
        self.assertEqual({x.mccb for x in t}, {x.mccb for x in b}, "분기 차단기 정격이 바뀌었다")
        ir = [x for x in t if x.id.startswith("IR-")]
        self.assertEqual(sum(x.kW for x in ir), C.layouts()["twin"]["lamps"] * 2.5,
                         "IR 분기 합이 옵션 램프 수와 다르다")
        self.assertGreater(st["main_af"], option.EL_B.summary()["main_af"])


if __name__ == "__main__":
    unittest.main()
