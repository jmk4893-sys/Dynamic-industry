"""부품 카탈로그와 그것에서 생성되는 부품도·조립도.

이 저장소가 계속 고쳐 온 실패는 하나다 — 같은 값을 두 곳에 적으면 한 곳만
고쳐진다. 부품도는 그 위험이 가장 큰 문서다: 174 장을 손으로 그리면 그
중 한 장은 반드시 옛 치수로 남고, 그 한 장으로 만든 부품은 안 맞는다.

그래서 도면을 그리지 않고 **생성한다**. 이 시험이 지키는 것은 그 사슬이다.

    형상 (parts.py) → 질량 → 지침서 자중 → 앵커·접합
                    ↘ JS 블록 (gen_parts_js.py) → 부품도·조립도

어느 고리든 손으로 끼워 넣으면 여기서 걸린다.
"""

import pathlib
import re
import subprocess
import sys
import unittest

from . import _path  # noqa: F401

import fab_spec as F
import gen_parts_js as GEN
import parts as PT

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


class TestTheCatalogueCoversTheMachine(unittest.TestCase):
    """빠진 부품은 조립 날에 없는 부품이다."""

    def test_every_delivered_module_has_parts_and_a_sequence(self):
        """모듈 하나가 비면 그 모듈은 조립 지침이 없는 채로 나간다."""
        for m in PT.MODULES:
            ps = PT.partsOf(m) if hasattr(PT, "partsOf") else [p for p in PT.P if p.mod == m]
            self.assertTrue(ps, f"{m} 에 부품이 하나도 없다")
            self.assertIn(m, PT.STEPS, f"{m} 에 조립 순서가 없다")
            self.assertTrue(PT.STEPS[m], f"{m} 조립 순서가 비어 있다")

    def test_the_module_list_matches_the_specification(self):
        """사양서가 13개 모듈을 팔기로 했다 — 카탈로그가 그 13개여야 한다."""
        rfq = (ROOT / "docs" / "dg-hk60-rfq.html").read_text(encoding="utf-8")
        for m in PT.MODULES:
            self.assertIn(m, rfq, f"{m} 이 사양서 모듈표에 없다")
        for gone in ("M-010", "M-014", "M-015", "M-016"):
            self.assertNotIn(gone, PT.MODULES,
                             f"{gone} 은 공급범위 밖인데 카탈로그가 부품을 든다")
        self.assertEqual(len(PT.MODULES), 13, "납품 모듈 수가 13 이 아니다")

    def test_part_numbers_are_unique_and_carry_their_module(self):
        """품번이 겹치면 두 부품이 같은 도면을 받는다."""
        ids = [p.pid for p in PT.P]
        self.assertEqual(len(ids), len(set(ids)), "품번이 중복됐다")
        for p in PT.P:
            self.assertTrue(p.pid.startswith("P-" + p.mod[2:] + "-"),
                            f"{p.pid} 의 품번이 모듈 {p.mod} 을 따르지 않는다")

    def test_every_part_says_how_it_attaches_and_when(self):
        """'어떻게 붙는가' 가 없으면 조립도는 부품을 늘어놓은 그림일 뿐이다."""
        for p in PT.P:
            self.assertTrue(p.fix.strip(), f"{p.pid} 에 체결 방법이 없다")
            self.assertTrue(p.note.strip(), f"{p.pid} 에 주의사항이 없다")
            steps = {s[0] for s in PT.STEPS[p.mod]}
            self.assertIn(p.step, steps,
                          f"{p.pid} 의 조립 단계 {p.step} 이 {p.mod} 순서표에 없다")

    def test_every_assembly_step_says_why_and_what_to_check(self):
        """왜 이 순서인지 모르면 현장에서 바꾼다. 무엇을 재는지 없으면 안 잰다."""
        for m, steps in PT.STEPS.items():
            nums = [s[0] for s in steps]
            self.assertEqual(nums, list(range(1, len(steps) + 1)),
                             f"{m} 단계 번호가 1부터 연속이 아니다")
            for n, title, why, check in steps:
                self.assertTrue(title.strip(), f"{m} {n}단계에 제목이 없다")
                self.assertGreater(len(why), 10, f"{m} {n}단계에 '왜' 가 없다")
                self.assertGreater(len(check), 5, f"{m} {n}단계에 '확인' 이 없다")
            used = {p.step for p in PT.P if p.mod == m}
            self.assertTrue(used <= set(nums), f"{m} 에 순서표 밖 단계를 쓰는 부품이 있다")


class TestTheGeometryIsRealGeometry(unittest.TestCase):
    """치수 없는 형상은 그림이지 도면이 아니다."""

    def test_every_fabricated_part_has_a_thickness_or_a_section(self):
        """제작사가 판을 자르려면 두께가 있어야 한다."""
        need = {"PL": ("L", "W", "t"), "SLAB": ("L", "W", "t"),
                "BOX": ("h", "b", "t", "L"), "ANG": ("a", "b", "t", "L"),
                "HB": ("h", "b", "tw", "tf", "L"), "CH": ("h", "b", "tw", "tf", "L"),
                "SQB": ("a", "L"), "TU": ("od", "t", "L"), "GU": ("a", "b", "t"),
                "FL": ("od", "id", "t", "pcd", "n", "dh"),
                "MESH": ("L", "W", "wire", "pitch", "frame"), "RB": ("d", "L")}
        for p in PT.P:
            if p.buy:
                continue
            for key in need[p.shape.kind]:
                v = p.shape.d[key]
                self.assertGreater(v, 0, f"{p.pid} 의 {key} 가 0 이하다")

    def test_every_purchased_part_gives_an_envelope_and_a_mass(self):
        """구매품은 형상을 그리지 않는다 — 대신 외형과 질량이 있어야 앉힐 자리를 잡는다."""
        for p in PT.P:
            if not p.buy:
                continue
            for key in ("L", "W", "H", "kg"):
                self.assertGreater(p.shape.d[key], 0, f"{p.pid} 의 {key} 가 없다")

    def test_mass_is_computed_from_geometry_not_typed(self):
        """질량을 손으로 적으면 형상을 고쳤을 때 질량만 옛 값으로 남는다."""
        for p in PT.P:
            if p.buy:
                continue
            want = p.shape.vol() * PT.density(p.mat) / 1e9
            self.assertAlmostEqual(p.kg, want, places=9,
                                   msg=f"{p.pid} 질량이 형상 계산과 다르다")
            self.assertGreater(p.kg, 0, f"{p.pid} 질량이 0 이다 — 밀도가 없는 재질인가")

    def test_the_material_is_one_the_specification_knows(self):
        """지침서에 없는 재질을 쓰면 그 부재는 설계기준이 없다."""
        known = set(F.MATERIALS) | set(PT.RHO_OTHER)
        for p in PT.P:
            self.assertIn(p.mat, known, f"{p.pid} 의 재질 {p.mat} 을 지침서가 모른다")

    def test_plate_holes_stay_inside_the_plate(self):
        """구멍이 판 밖에 있으면 그 판은 만들 수 없다."""
        for p in PT.P:
            if p.shape.kind != "PL":
                continue
            L, W = p.shape.d["L"], p.shape.d["W"]
            for x, y, d in p.shape.d["holes"]:
                self.assertGreaterEqual(x - d / 2, 0, f"{p.pid} 홀이 판 왼쪽으로 나갔다")
                self.assertGreaterEqual(y - d / 2, 0, f"{p.pid} 홀이 판 아래로 나갔다")
                self.assertLessEqual(x + d / 2, L, f"{p.pid} 홀이 판 오른쪽으로 나갔다")
                self.assertLessEqual(y + d / 2, W, f"{p.pid} 홀이 판 위로 나갔다")

    def test_bolt_holes_clear_the_bolt_they_take(self):
        """앵커 M20 에 Ø20 구멍을 뚫으면 현장에서 안 들어간다."""
        for p in PT.P:
            if p.shape.kind != "PL" or "베이스플레이트" not in p.name:
                continue
            for _x, _y, d in p.shape.d["holes"]:
                self.assertGreaterEqual(d, 12, f"{p.pid} 베이스 홀 Ø{d} 는 앵커에 너무 작다")
                self.assertLessEqual(d, 40, f"{p.pid} 베이스 홀 Ø{d} 는 과대하다")

    def test_the_section_profile_closes_for_every_family(self):
        """단면 윤곽이 안 닫히면 등각 그림이 찢어진다."""
        for p in PT.P:
            prof = PT.Shape(p.shape.kind, p.shape.d)
            if p.shape.kind in ("RB", "TU", "FL"):
                continue
            self.assertGreaterEqual(len(prof.bbox()), 3)
            for v in prof.bbox():
                self.assertGreater(v, 0, f"{p.pid} 외형 상자에 0 이 있다")


class TestTheCatalogueFeedsTheSpecification(unittest.TestCase):
    """자중을 형상 없이 적으면 앵커가 그 오차만큼 틀어진다."""

    def test_the_specification_takes_its_masses_from_here(self):
        for sym, _what, pids in PT.MASS_GROUPS:
            self.assertAlmostEqual(getattr(F, sym), PT.group_kg(pids), delta=0.5,
                                   msg=f"{sym} 이 카탈로그 계산값이 아니다")

    def test_the_concept_estimates_are_kept_as_a_record(self):
        """개산이 얼마나 빗나갔는지가 '왜 형상이 필요한가' 의 답이다."""
        self.assertEqual(set(PT.MASS_CONCEPT), {s for s, _w, _p in PT.MASS_GROUPS})
        off = [s for s, _w, _a, _g, _d, ok in PT.mass_check() if not ok]
        self.assertTrue(off, "개산이 전부 맞았다면 이 기록을 둘 이유가 없다")
        self.assertIn("M_WINDER", off, "권취 문형 개산이 빗나간 기록이 사라졌다")

    def test_the_mass_groups_do_not_double_count(self):
        """같은 부품을 두 그룹이 세면 자중이 부풀고 앵커가 과대해진다."""
        seen: set[str] = set()
        for _sym, _what, pids in PT.MASS_GROUPS:
            self.assertEqual(len(pids), len(set(pids)), "한 그룹 안에서 중복")
            dup = seen & set(pids)
            self.assertFalse(dup, f"두 그룹이 같은 부품을 센다: {sorted(dup)}")
            seen |= set(pids)

    def test_every_group_member_is_a_real_part(self):
        ids = {p.pid for p in PT.P}
        for sym, _what, pids in PT.MASS_GROUPS:
            for pid in pids:
                self.assertIn(pid, ids, f"{sym} 이 없는 품번 {pid} 을 센다")


class TestTheConsoleReadsTheGeneratedCatalogue(unittest.TestCase):
    """콘솔이 표를 손으로 들면 반드시 갈라진다."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_the_data_block_is_exactly_what_the_generator_prints(self):
        """블록을 손으로 고치면 여기서 걸린다 — 고칠 곳은 parts.py 다."""
        self.assertIn(GEN.OPEN, self.html, "콘솔에 카탈로그 블록 표지가 없다")
        i = self.html.index(GEN.OPEN)
        k = self.html.index(GEN.CLOSE) + len(GEN.CLOSE)
        self.assertEqual(self.html[i:k], GEN.block(),
                         "콘솔의 부품 블록이 tools/gen_parts_js.py 의 출력과 다르다 — "
                         "python3 tools/gen_parts_js.py --write 로 다시 찍는다")

    def test_the_generator_is_idempotent(self):
        """다시 찍었을 때 파일이 바뀌면 저장소가 늘 더러운 상태가 된다."""
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_parts_js.py"), "--write"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("이미 같다", r.stdout, "생성기를 다시 돌리면 파일이 바뀐다")

    def test_the_console_draws_every_shape_family(self):
        """형상족 하나가 투상 없이 남으면 그 부품은 그림 없는 도면이 된다."""
        kinds = {p.shape.kind for p in PT.P}
        body = self.html[self.html.index("function sectProfile("):
                         self.html.index("function partSheet(")]
        sheet = self.html[self.html.index("function partSheet("):
                          self.html.index("function explodedSheet(")]
        for k in kinds:
            self.assertTrue(f"'{k}'" in body or f"'{k}'" in sheet,
                            f"형상족 {k} 을 그리는 코드가 없다")

    def test_the_part_sheet_never_reads_the_layout_the_screen_shows(self):
        """부품도는 배치와 무관하다 — 트윈을 켜 둔 채 열어도 같아야 한다."""
        sheet = self.html[self.html.index("function partSheet("):
                          self.html.index("    /* ── 부품도·조립도 브라우저")]
        for bad in ("LC()", "twinView()", "compactView()", "cCrownTop()", "cDuctZ()"):
            self.assertNotIn(bad, sheet, f"부품도가 활성 배치({bad})를 읽는다")

    def test_the_browser_offers_both_sheets(self):
        for tab in ('data-drawing="parts"', 'data-drawing="assembly"'):
            self.assertIn(tab, self.html, f"{tab} 탭이 없다")
        for fn in ("partsBrowser()", "assemblyBrowser()"):
            self.assertIn(fn, self.html, f"{fn} 가 디스패치에 없다")

    def test_the_full_bom_is_not_truncated_below_the_sheet(self):
        """A3 한 장에 174 행이 안 들어간다 — 잘린 행이 어디에도 없으면 그 부품은 없는 것이 된다."""
        br = self.html[self.html.index("function assemblyBrowser("):
                       self.html.index("    function boltDetailDrawing(")]
        self.assertIn("part-bom", br, "도면 밑 전체 부품표가 없다")
        self.assertIn("ps.map(", br, "전체 부품표가 전 부품을 돌지 않는다")
        self.assertIn("전 ${ps.length} 종", br, "전체 부품표가 몇 종인지 밝히지 않는다")
        # 표를 만들기만 하고 안 돌려주면 화면에 없다 — 만든 것과 낸 것은 다르다
        ret = br[br.index("return `<div class=\"part-pick\">"):]
        self.assertIn("+tbl", ret,
                      "전체 부품표를 만들어 놓고 화면에 내지 않는다")

    def test_the_sheet_points_at_the_fabrication_specification(self):
        """부품도가 체결 규격을 스스로 적으면 지침서와 갈라진다."""
        sheet = self.html[self.html.index("function partSheet("):
                          self.html.index("function explodedSheet(")]
        self.assertIn("DG-HK60C-FAB-001", sheet,
                      "부품도가 체결 사양의 출처를 대지 않는다")
        self.assertIn("tools/parts.py", sheet,
                      "부품도가 자기 출처를 밝히지 않는다 — 도면만 고치는 사람이 생긴다")


class TestTheDrawingsSayWhatTheyAre(unittest.TestCase):
    """개념설계 유도값을 확정값처럼 내보내면 그 도면으로 물건을 만든다."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_the_sheet_declares_its_standing(self):
        sheet = self.html[self.html.index("function partSheet("):
                          self.html.index("function explodedSheet(")]
        self.assertIn("상세설계에서 확정한다", sheet,
                      "부품도가 개념설계 유도값임을 밝히지 않는다")

    def test_purchased_parts_are_marked_as_purchased(self):
        """구매품 도면을 제작품처럼 내면 제작사가 살 것을 만들려 든다.

        '구매품' 이라는 낱말이 시트 어딘가에 있는 것으로는 부족하다 — 표제란
        재질 칸에도 그 낱말이 있어서, 머리띠의 구분이 사라져도 통과한다.
        구분은 **두 갈래 문구가 다 있는가**로 확인한다.
        """
        sheet = self.html[self.html.index("function partSheet("):
                          self.html.index("function explodedSheet(")]
        for m in ("구매품 — 규격으로 산다", "제작품 — 이 도면으로 만든다"):
            self.assertIn(m, sheet, f"부품도 머리띠에 '{m}' 구분이 없다")
        buys = [p for p in PT.P if p.buy]
        self.assertGreater(len(buys), 30, "구매품이 이렇게 적을 리 없다")
        # 구매품은 제작 치수를 그리지 않는다 — 외형과 규격만 준다
        for q in buys:
            self.assertEqual(set(q.shape.d) , {"L", "W", "H", "kg"},
                             f"{q.pid} 구매품에 제작 치수가 붙어 있다")

    def test_the_catalogue_report_runs_and_closes(self):
        out = PT.report()
        self.assertIn("부품 카탈로그", out)
        self.assertIn("자중", out)
        self.assertIn(f"{len(PT.P)}", out)


class TestTheAssemblyManualIsUsableByABeginner(unittest.TestCase):
    """도면을 처음 보는 사람이 조립할 수 있어야 한다는 것이 이 문서의 요구다.

    그 요구는 검사 가능하다. 세 가지가 있어야 한다 — 도면 읽는 법, 모듈을
    세우는 순서(모듈 사이의 순서), 그리고 단계마다 '왜' 와 '무엇을 재는가'.
    하나라도 빠지면 "그림은 봤는데 어디서부터 손대야 하나" 가 된다.
    """

    @classmethod
    def setUpClass(cls):
        import gen_assembly_doc
        cls.G = gen_assembly_doc
        cls.html = gen_assembly_doc.OUT.read_text(encoding="utf-8")

    def test_the_document_is_exactly_what_the_generator_prints(self):
        """문서를 손으로 고치면 카탈로그와 갈라진다 — 고칠 곳은 parts.py 다."""
        self.assertEqual(self.html, self.G.build(),
                         "문서가 tools/gen_assembly_doc.py 의 출력과 다르다 — "
                         "python3 tools/gen_assembly_doc.py --write 로 다시 찍는다")

    def test_it_teaches_how_to_read_a_drawing(self):
        """정투상을 못 읽는 사람이 이 설비를 조립한다는 것이 전제다."""
        for m in ("제3각법", "등각 그림", "파단선", "용접기호", "풍선번호",
                  "ISO 2768-mK", "데이텀"):
            self.assertIn(m, self.html, f"도면 읽는 법에 '{m}' 가 없다")
        self.assertIn("조립도 → 부품표 → 부품도", self.html,
                      "도면을 찾아가는 순서를 알려주지 않는다")

    def test_it_fixes_the_order_between_modules_not_only_within(self):
        """모듈 사이의 순서가 없으면 현장이 반입 순서대로 세운다."""
        self.assertIn("모듈을 세우는 순서", self.html)
        for m in PT.MODULES:
            self.assertIn(m, self.html, f"{m} 이 세우는 순서 어디에도 없다")
        # 방책이 마지막이라는 것이 이 문서에서 가장 비싼 한 줄이다
        last = [row for row in self.G.ERECTION if "M-013" in row[2]]
        self.assertTrue(last, "방책이 세우는 순서에 없다")
        self.assertEqual(last[0][0], str(len(self.G.ERECTION)),
                         "방책이 마지막 순서가 아니다 — 반입로가 막힌다")
        self.assertIn("반입로가 막힌다", self.html)

    def test_every_module_section_carries_its_steps_and_its_parts(self):
        for m in PT.MODULES:
            self.assertIn(f"{m} 조립 순서", self.html, f"{m} 순서표가 없다")
            self.assertIn(f"{m} 부품표", self.html, f"{m} 부품표가 없다")
        # 부품표는 전 부품을 든다 — 잘린 부품은 없는 부품이 된다
        for p in PT.P:
            self.assertIn(p.pid, self.html, f"{p.pid} 가 조립 지침서에 없다")

    def test_the_numbers_are_the_catalogue_numbers(self):
        """질량을 손으로 옮겨 적으면 카탈로그를 고친 날 문서만 옛 값이 된다."""
        for m in PT.MODULES:
            ps = [p for p in PT.P if p.mod == m]
            self.assertIn(f"{sum(x.total_kg for x in ps):,.0f} kg", self.html,
                          f"{m} 질량이 카탈로그 계산과 다르다")
        self.assertIn(f"{len(PT.P)} 종", self.html, "총 품목 수가 카탈로그와 다르다")

    def test_it_names_the_tools_without_which_assembly_cannot_start(self):
        """교정된 토크렌치 없이 조인 볼트는 조인 것이 아니라 돌린 것이다."""
        self.assertIn("토크렌치", self.html)
        self.assertIn("교정 성적서", self.html)
        self.assertIn("임팩트", self.html, "임팩트렌치를 본 조임에 쓰지 말라는 말이 없다")
        self.assertIn("접지저항", self.html, "통전 전 접지 확인이 공구 목록에 없다")

    def test_it_warns_about_the_mistakes_that_actually_happen(self):
        self.assertGreaterEqual(len(self.G.MISTAKES), 10, "흔한 실수가 열 가지가 안 된다")
        for m in ("마찰접합", "스프링와셔", "그라우트", "하드스톱"):
            self.assertIn(m, self.html, f"흔한 실수에 '{m}' 가 없다")

    def test_it_defers_fastening_to_the_fabrication_specification(self):
        """체결 규격을 두 문서가 각자 적으면 반드시 갈라진다."""
        self.assertIn("DG-HK60C-FAB-001", self.html,
                      "조립 지침서가 체결 사양의 출처를 대지 않는다")
        self.assertIn("F-901", self.html, "표준상세를 가리키지 않는다")
        # 토크 값을 적었다면 계산기가 낸 값이어야 한다
        self.assertIn(f"{F.torque('M20', '8.8', F.K_DRY):.0f} N·m", self.html)
        self.assertIn(f"{F.torque('M20', '8.8', F.K_LUB):.0f} N·m", self.html)

    def test_it_says_the_geometry_is_not_final(self):
        """개념설계 유도값을 확정값처럼 내보내면 그 도면으로 물건을 만든다."""
        self.assertIn("상세설계에서 확정한다", self.html)
        self.assertIn("도면을 손으로 고치지 않는다", self.html)


if __name__ == "__main__":
    unittest.main()
