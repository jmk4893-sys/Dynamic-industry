"""옵션 DG-HK120C 도면 세트 — 부품도 · 조립도 · 부하표 E-001T.

옵션 도면은 콘솔에서 따로 그리지 않는다. tools/gen_option_js.py 가 같은 카탈로그를
HK120C 핀으로 다시 푼 것을 블록으로 찍고, 콘솔은 **도면 세트** 선택으로 그 블록을
그린다. 여기서 묻는 것은 셋이다:

  1. 블록이 생성기 출력 그대로인가 — 손으로 고친 옵션 값은 다음 생성에서 지워진다
  2. 도번이 형상을 가리키는가 — 같은 도번에 다른 치수가 돌면 창고에서 섞인다
  3. 콘솔이 옵션을 그리기만 하는가 — 옵션 합계를 콘솔에서 다시 셈하면 식이 두 벌이 된다
"""

import pathlib
import re
import subprocess
import sys
import unittest

from tests import _path  # noqa: F401

import console_consts as C
import gen_option_js as GEN
import option as O

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
PY = [sys.executable]


class TestTheBlockIsGenerated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_the_block_is_exactly_what_the_generator_prints(self):
        self.assertIn(GEN.OPEN, self.html, "콘솔에 옵션 블록 표지가 없다")
        i = self.html.index(GEN.OPEN)
        k = self.html.index(GEN.CLOSE) + len(GEN.CLOSE)
        self.assertEqual(self.html[i:k], GEN.block(),
                         "콘솔의 옵션 블록이 tools/gen_option_js.py 의 출력과 다르다 — "
                         "python3 tools/gen_option_js.py --write 로 다시 찍는다")

    def test_the_generator_is_idempotent(self):
        r = subprocess.run(PY + [str(ROOT / "tools" / "gen_option_js.py"), "--write"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("이미 같다", r.stdout, "생성기를 다시 돌리면 파일이 바뀐다")

    def test_the_block_sits_after_the_standard_catalogue(self):
        """콘솔의 DWG_SETS 가 두 블록을 함께 읽는다 — 옵션 블록이 표준 블록보다 앞서면
        읽는 순서가 바뀌어도 잡히지 않는다. 자리는 표준 블록 바로 뒤로 못 박는다."""
        import gen_parts_js as GP
        k = self.html.index(GP.CLOSE) + len(GP.CLOSE)
        self.assertEqual(self.html[k:k + 1 + len(GEN.OPEN)], "\n" + GEN.OPEN)


class TestDrawingNumbersPointAtShapes(unittest.TestCase):
    """도번은 형상을 가리킨다 — 형상이 같으면 같은 도번, 다르면(또는 옵션에만 있으면) T."""

    @classmethod
    def setUpClass(cls):
        cls.base = {p.pid: p for p in O.PT_B.P}
        cls.opt = {p.pid: p for p in O.PT_T.P}

    def test_one_number_one_shape_across_both_sets(self):
        """두 세트를 합쳐도 한 도번이 두 형상을 가리키지 않는다."""
        seen = {}
        for p in O.PT_B.P:
            seen.setdefault(p.pid, set()).add(O.geometry(p))
        for p in O.PT_T.P:
            seen.setdefault(O.part_no(p), set()).add(O.geometry(p))
        for no, shapes in seen.items():
            self.assertEqual(len(shapes), 1, f"도번 {no} 가 형상 {len(shapes)} 개를 가리킨다")

    def test_a_changed_part_gets_a_new_number(self):
        """P-002-01 가열실 기둥은 옵션에서 1,240 길어진다 — 표준 도번으로 나가면 안 된다."""
        changed = [pid for pid, p in self.opt.items()
                   if pid in self.base and O.geometry(p) != O.geometry(self.base[pid])]
        self.assertTrue(changed, "옵션에서 형상이 바뀐 부품이 하나도 없다 — 비교가 헛돈다")
        for pid in changed:
            self.assertEqual(O.part_no(self.opt[pid]), pid + O.SUFFIX, pid)
        self.assertIn("P-002-01", changed)

    def test_an_unchanged_part_keeps_its_number(self):
        """형상이 같은 부품에 T 를 달면 같은 물건에 도면이 둘이 된다."""
        same = [pid for pid, p in self.opt.items()
                if pid in self.base and O.geometry(p) == O.geometry(self.base[pid])]
        self.assertGreater(len(same), len(self.opt) // 2)
        for pid in same:
            self.assertEqual(O.part_no(self.opt[pid]), pid, pid)

    def test_an_option_only_part_is_marked(self):
        only = [pid for pid in self.opt if pid not in self.base]
        self.assertTrue(only, "옵션에만 있는 부품이 없다 — 횡이송 문형·셀 가드가 빠졌다")
        for pid in only:
            self.assertTrue(O.part_no(self.opt[pid]).endswith(O.SUFFIX), pid)

    def test_a_new_number_never_lands_on_a_standard_number(self):
        for p in O.PT_T.P:
            no = O.part_no(p)
            if no != p.pid:
                self.assertNotIn(no, self.base, f"{no} 가 표준 품번과 겹친다")

    def test_geometry_ignores_float_tails_but_not_real_changes(self):
        """같은 치수가 다른 길로 풀려 1e-9 가 다르면 같은 도면이다 — 0.1 mm 가 다르면 아니다."""
        import copy
        p = next(iter(O.PT_B.P))
        q = copy.deepcopy(p)
        k = next(k for k, v in q.shape.d.items() if isinstance(v, float))
        q.shape.d[k] = q.shape.d[k] + 1e-9
        self.assertEqual(O.geometry(p), O.geometry(q))
        q.shape.d[k] = p.shape.d[k] + 0.1
        self.assertNotEqual(O.geometry(p), O.geometry(q))


class TestPerCellModulesAreDrawnOnce(unittest.TestCase):
    """셀마다 서는 모듈은 표준 조립도를 두 벌 만든다 — 부품이 두 배인 새 도면이 아니다."""

    def test_per_cell_modules_keep_the_standard_assembly_number(self):
        for m in O.PT_T.PER_CELL:
            self.assertEqual(O.module_cells(m), O.PT_T.CELLS, m)
            base = [(p.pid, O.geometry(p), p.qty) for p in O.PT_B.P if p.mod == m]
            unit = [(p.pid, O.geometry(p), O.PT_T.unit_qty(p)) for p in O.PT_T.P if p.mod == m]
            if base == unit and O.PT_B.STEPS[m] == O.PT_T.STEPS[m]:
                self.assertEqual(O.module_no(m), "A-" + m[2:], f"{m} 한 벌이 표준과 같은데 도번이 바뀌었다")

    def test_every_per_cell_part_carries_its_unit_quantity(self):
        """콘솔 조립도는 u(셀당 수량)로 한 벌을 그린다 — u 가 빠지면 한 벌 도면에 두 벌 수량이 찍힌다."""
        import json
        parts = json.loads(re.search(r"const PARTS_OPT=(\[.*?\]);\n", GEN.block()).group(1))
        for q in parts:
            if q["m"] in O.PT_T.PER_CELL:
                self.assertIn("u", q, q["id"])
                self.assertEqual(q["u"] * O.PT_T.CELLS, q["q"], q["id"])

    def test_a_shared_module_that_changed_gets_t(self):
        """가열실은 7 단이 된다 — 조립도가 표준 A-002 로 나가면 5 단 순서로 7 단을 짓는다."""
        self.assertEqual(O.module_no("M-002"), "A-002" + O.SUFFIX)
        self.assertEqual(O.module_no("M-002", opt=False), "A-002")


class TestTheOptionLoadScheduleIsElectricals(unittest.TestCase):
    """E-001T 의 값은 tools/electrical.py 가 낸다 — 콘솔은 그리기만 한다."""

    @classmethod
    def setUpClass(cls):
        import json
        cls.load = json.loads(re.search(r"const LOAD_OPT=(\{.*?\});\n", GEN.block()).group(1))
        cls.tw = C.layouts()["twin"]

    def test_the_ir_split_comes_from_the_option_lamp_count(self):
        """IR 한 분기는 옵션 램프 ÷ 셀 수를 맡는다 — 표준 분기를 복사한 값이 아니다."""
        ir = [r for r in self.load["rows"] if r["base"].startswith("IR-")]
        self.assertEqual(len(ir), self.tw["cells"])
        per = self.tw["lamps"] // self.tw["cells"]
        for r in ir:
            self.assertIn(f"IR 램프 {per}×", r["load"], r)
            self.assertAlmostEqual(r["kW"], per * 2.5, places=6)

    def test_the_lamp_split_is_not_a_copy_of_the_standard(self):
        """램프가 두 배가 아닌 옵션을 가정해도 IR 합이 따라와야 한다 (복사면 120 × 2 로 남는다)."""
        import electrical as EL
        rows = EL.base_branches(lamps=40)
        ir = [b for b in rows if b.id.startswith("IR-")][0]
        self.assertAlmostEqual(ir.kW, 100.0)
        self.assertIn("IR 램프 40×", ir.load)

    def test_every_other_branch_stands_once_per_cell(self):
        by = {}
        for r in self.load["rows"]:
            by.setdefault(r["base"], []).append(r)
        for base, rs in by.items():
            self.assertEqual(len(rs), self.tw["cells"], base)
            self.assertEqual(len({r["mccb"] for r in rs}), 1, f"{base} 분기 차단기가 셀마다 다르다")

    def test_the_summary_is_the_same_rule_as_the_standard(self):
        with O.pinned():
            s = O.EL_T.summary()
        self.assertEqual(self.load["sum"]["af"], s["main_af"])
        self.assertEqual(self.load["sum"]["tr"], s["tr_kva"])
        self.assertEqual(self.load["sum"]["sccr"], s["sccr_ka"])
        self.assertAlmostEqual(self.load["sum"]["fla"], s["fla"], places=5)
        self.assertGreater(s["main_af"], O.EL_B.summary()["main_af"], "옵션 주차단기가 표준보다 크지 않다")


class TestTheConsoleDrawsTheSelectedSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        cls.flat = re.sub(r"\s", "", cls.html)

    def _between(self, a, b):
        return self.html[self.html.index(a):self.html.index(b)]

    def test_the_sets_are_the_two_blocks(self):
        for frag in ("std:{model:HK60C.model,rev:HK60C.rev,parts:PARTS,mods:PART_MODULES,steps:PART_STEPS}",
                     "opt:{model:HK120C.model,rev:HK120C.rev,parts:PARTS_OPT,mods:PART_MODULES_OPT,steps:PART_STEPS_OPT}"):
            self.assertIn(frag, self.flat)

    def test_the_sheets_follow_the_set_not_the_screen(self):
        """트윈 화면에서 표준 부품도를 인쇄할 수 있어야 한다 — 세트 선택만 읽는다."""
        body = self._between("    const DWG_SETS={", "    function boltDetailDrawing(")
        power = self._between("    function elecOf(set){", "    function plcDrawing(){")
        for bad in ("LC()", "twinView()", "compactView()", "layoutId"):
            self.assertNotIn(bad, body, f"부품도·조립도가 활성 배치({bad})를 읽는다")
            self.assertNotIn(bad, power, f"E-001 이 활성 배치({bad})를 읽는다")
        for fn in ("partsBrowser", "assemblyBrowser", "powerDrawing"):
            m = re.search(rf"\n    function {fn}\(\)\{{.*?\n    \}}", self.html, re.S)
            self.assertIn("setPick()", m.group(0), f"{fn} 에 도면 세트 선택이 없다")
        self.assertIn("const dsel=$('dwgSetSel');if(dsel)dsel.addEventListener('change'", self.html)

    def test_the_sheet_prints_the_drawing_number(self):
        sheet = self._between("function partSheet(", "function explodedSheet(")
        self.assertIn("fabTitleBlock({no:partNo(p),", sheet, "부품도 표제란이 도번이 아니라 품번을 적는다")
        self.assertIn("${esc(DS().model)}", sheet, "부품도가 어느 세트인지 적지 않는다")
        asm = self._between("    function assemblyBrowser(", "    function boltDetailDrawing(")
        self.assertIn("fabTitleBlock({no:modNo(asmModule),", asm)

    def test_the_assembly_draws_one_set_of_a_per_cell_module(self):
        ex = self._between("function explodedSheet(", "    function partsBrowser(")
        self.assertIn("uq=q=>unitQ(q,mod)", ex)
        self.assertNotIn("q.q+'개'", ex, "조립도 부품표가 한 벌이 아니라 기계 한 대분을 적는다")
        self.assertIn("const unitQ=(q,m)=>modSets(m)>1?q.u:q.q;", self.html)

    def test_the_option_single_line_is_its_own_sheet(self):
        power = self._between("    function elecOf(set){", "    function plcDrawing(){")
        self.assertIn("titleBlock('E-001T',", power)
        self.assertIn("HK120C.rev,610)", power, "옵션 단선도가 옵션 개정을 달지 않는다")
        self.assertIn("rows:LOAD_OPT.rows", power)
        # 옵션 합계를 콘솔에서 다시 셈하지 않는다
        opt = power[power.index("if(set==='opt')"):power.index("return {no:DWG_NO")]
        self.assertNotIn("reduce(", opt, "옵션 합계를 콘솔이 다시 셈한다 — 식이 두 벌이 된다")
        self.assertIn("${rev===HK120C.rev?HK120C.model:HK60C.model}", self.html,
                      "표제란 모델명이 개정을 따르지 않는다 — 옵션 시트에 DG-HK60C 가 찍힌다")

    def test_the_branch_boxes_do_not_overlap(self):
        """칼 폭 126 · 간격 130 — 한때 간격 110 이라 칸이 16 px 씩 겹치고 첫 칸이 PE 선을 밟았다."""
        power = self._between("    function powerDrawing(){", "    function plcDrawing(){")
        m = re.search(r"branch\((\d+)\+i\*(\d+),g\)", power)
        self.assertIsNotNone(m)
        x0, dx = int(m.group(1)), int(m.group(2))
        w = int(re.search(r'<rect x="\$\{x-(\d+)\}" y="330" width="(\d+)"', power).group(2))
        half = w // 2
        self.assertGreaterEqual(dx, w + 2, "분기 칸이 서로 겹친다")
        pe = int(re.search(r'<path d="M(\d+) 224V454H\d+"', power).group(1))
        self.assertGreater(x0 - half, pe + 5, "첫 분기 칸이 PE 하강선을 밟는다")
        bus = int(re.search(r'<path d="M570 168H(\d+)"', power).group(1))
        groups = len({b.base for b in O.EL_B.branches()})
        self.assertLessEqual(x0 + (groups - 1) * dx + half, bus, "마지막 분기 칸이 모선 밖에 선다")

    def test_the_arithmetic_overestimate_is_computed(self):
        """'508.6A 로 2.9%' 는 옛 부하표의 값이었다 — 부하표를 따라 셈해야 한다."""
        self.assertNotIn("508.6A", self.html)
        self.assertIn("const arith=E.rows.reduce((a,k)=>a+branchAmp(k),0);", self.html)


class TestTheProcurementCitesTheNumbers(unittest.TestCase):
    """조달 지침서 4 부가 옵션 도번을 같은 규칙으로 적는다."""

    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "docs" / "dg-hk60-procurement.html").read_text(encoding="utf-8")

    def test_the_register_counts_are_in_the_document(self):
        reg = O.drawing_register()
        self.assertIn(f"<strong>{len(reg['same'])} 장</strong>을 그대로 쓰고", self.html)
        self.assertIn(f"<strong>{len(reg['new'])} 장</strong>이 새로 선다", self.html)
        for no in reg["new"]:
            self.assertIn(f'<td class="k">{no}</td>', self.html, no)

    def test_every_module_row_names_its_assembly_drawing(self):
        for m in O.PT_T.MODULES:
            n = O.module_cells(m)
            cell = O.module_no(m) + (f" × {n} 벌" if n > 1 else "")
            self.assertIn(f'<td class="k">{m}</td>', self.html)
            self.assertIn(f'<td class="k">{cell}</td>', self.html, m)


if __name__ == "__main__":
    unittest.main()
