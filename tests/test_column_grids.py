"""기둥 격자는 콘솔 한 곳에서 정하고 모두가 읽는다.

VT-101 진공테이블 기둥이 카탈로그·해석에는 6 본, 콘솔 모듈표·3D·기초도에는
4 본이었다. 가열실·냉각 랙도 카탈로그·해석은 6 본인데 3D·기초도는 모서리
4 본이었다. 기초도 D-602 는 토목 업자가 기초를 치는 도면이다 — 앵커가 두 군데
모자란 채로 타설되면 기계를 앉힐 수 없다.

각자 세면 갈라진다. 그래서 격자(열 수 · 안쪽 거리)를 콘솔 뿌리 상수로 두고

    콘솔 TBL_COLS_X · TBL_INSET_X/Y · RACK_COLS_X · RACK_COL_Y
      → 3D · 정면도 C-001 · 기초도 A1/A2/A8
      → 카탈로그 수량 (parts.py) → 모듈표 (PARTS 에서 센다)
      → 해석 S4~S8 (analysis_structural) · 제작 지침서 J1 (fab_spec)

이 한 사슬로 읽게 했다. 여기서 사슬이 끊기면 걸린다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

import analysis_structural as ST
import fab_spec as F
import parts as PT
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


def _flat(s):
    return re.sub(r"\s+", "", s)


def _qty(pid):
    return next(p for p in PT.P if p.pid == pid).qty


class TestTheCatalogCountsTheConsoleGrid(unittest.TestCase):
    def test_the_table_columns(self):
        n = 2 * round(c("TBL_COLS_X"))
        self.assertEqual(n, 6, "VT-101 기둥은 6 본이다 — 4 본이면 S8 이 예산을 넘는다")
        self.assertEqual(PT.TABLE_COLS, n)
        for pid in ("P-004-04", "P-004-05", "P-004-07"):
            self.assertEqual(_qty(pid), n, f"{pid} 가 콘솔 격자({n})와 다르다")
        self.assertEqual(_qty("P-004-06"), 4 * n, "거싯은 기둥당 4 매")

    def test_the_rack_columns(self):
        nx = round(c("RACK_COLS_X"))
        self.assertEqual(PT.RACK_COLS, 2 * nx)
        for pid in ("P-002-01", "P-002-02", "P-007-01", "P-007-02"):
            self.assertEqual(_qty(pid), 2 * nx, f"{pid} 가 랙 격자({2 * nx})와 다르다")
        self.assertEqual(_qty("P-002-03"), 8 * nx, "거싯은 기둥당 4 매")
        self.assertEqual(_qty("P-002-05"), nx, "횡방향 타이빔은 기둥 열마다 하나")

    def test_the_chamber_column_note_is_derived(self):
        """주기에 적힌 기둥 자리가 옛 챔버 길이(3,780)로 남아 있었다."""
        note = next(p for p in PT.P if p.pid == "P-002-01").note
        L = PT.CHAMBER_L
        self.assertIn(f"{L:,.0f}", note)
        self.assertIn(f"±{c('RACK_COL_Y') * 1000:,.0f}", note)
        self.assertNotIn("3,780", note)


class TestTheDrawingsStandOnTheGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        cls.flat = _flat(cls.html)

    def _fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return _flat(m.group(0))

    def test_the_3d_table_columns(self):
        body = self._fn("cPeelCell")
        self.assertIn("for(constxoftblColXs())for(constyoftblColYs())column(", body)
        self.assertNotIn("CARRIER_L-.40", body, "옛 모서리 4 본 좌표가 남아 있다")

    def test_the_3d_rack_columns(self):
        body = self._fn("cRack")
        self.assertIn("for(constxofrackColXs(cx,L,opt.inset||0))for(constyof[-RACK_COL_Y,RACK_COL_Y]){column(", body)
        self.assertIn("plate:PLT(opt.plate)", body, "랙 기둥 판이 카탈로그 품번을 읽지 않는다")
        self.assertNotIn("[x0,x1])for(constyof[-1.15,1.15]", body)

    def test_the_front_view_draws_every_column_line(self):
        self.assertIn("constTCX=tblColXs();", self.flat)
        self.assertNotIn("CTBL_CX-1.25", self.flat, "정면도가 옛 기둥 두 줄을 그린다")

    def test_the_foundation_plan_anchors_every_column(self):
        """D-602 의 앵커 점 수가 카탈로그의 베이스플레이트 수와 같아야 한다."""
        for gid, expr in (
            ("A1", "pts:grid(rackColXs(CST.HC.cx,CST.HC.w),[-RACK_COL_Y,RACK_COL_Y])"),
            # 냉각 랙 끝기둥은 데크 끝에 선다 — 스테이션 끝에 세우면 GL·GU 포크 판과 겹친다
            ("A2", "pts:grid(rackColXs(CST.GC.cx,CST.GC.w,GC_COL_INSET),[-RACK_COL_Y,RACK_COL_Y])"),
            ("A8", "pts:grid(tblColXs(),tblColYs())"),
        ):
            i = self.flat.find("{id:'%s'," % gid)
            self.assertGreater(i, 0, f"기초도 {gid} 를 찾지 못했다")
            row = self.flat[i:self.flat.find("{id:'", i + 1)]
            self.assertIn(expr, row, f"기초도 {gid} 가 기둥 격자를 읽지 않는다")
        # 격자가 내는 점 수 = 카탈로그 베이스플레이트 수
        self.assertEqual(2 * round(c("TBL_COLS_X")), _qty("P-004-05"))
        self.assertEqual(2 * round(c("RACK_COLS_X")), _qty("P-002-02"))
        self.assertEqual(2 * round(c("RACK_COLS_X")), _qty("P-007-02"))
        # 판 크기는 도면이 적지 않는다 — 앵커군 표의 품번으로 카탈로그 판을 읽는다
        self.assertIn("returnObject.assign(g,{part:a.part,plate:PLT(a.part),anchor:a})", self.flat,
                      "기초도의 판이 카탈로그 품번에서 오지 않는다")
        self.assertIsNone(re.search(r"\{id:'A\d+',[^}]*plate:\.\d", self.flat),
                          "기초도가 판 크기를 숫자로 적는다")


class TestTheModulePanelCountsFromTheCatalog(unittest.TestCase):
    """콘솔 모듈표가 수량을 따로 적어 카탈로그와 갈라졌다 (지지기둥×4 ↔ 6 본)."""

    @classmethod
    def setUpClass(cls):
        html = CONSOLE.read_text(encoding="utf-8")
        a0 = html.index("    const assemblies=[")
        cls.block = html[a0:html.index("\n    ];", a0)]
        cls.html = html

    def test_no_hand_counted_structure(self):
        hand = re.findall(r"(?:기둥|거싯|대차|버튼함)×\d", self.block)
        self.assertEqual(hand, [], f"모듈표가 구조 부재 수를 손으로 센다: {hand}")

    def test_every_lookup_names_a_real_part(self):
        ids = re.findall(r"PQ\('(P-\d{3}-\d{2})'\)", self.block)
        self.assertGreaterEqual(len(ids), 20)
        known = {p.pid for p in PT.P}
        self.assertEqual([i for i in ids if i not in known], [], "카탈로그에 없는 품번")

    def test_the_table_row_reads_its_columns(self):
        self.assertIn("지지기둥×${PQ('P-004-04')}", self.block)

    def test_the_drawing_resolves_the_lookups(self):
        """표는 PARTS 보다 먼저 풀리므로 수량 항목은 함수다 — 그릴 때 불러야 한다."""
        flat = _flat(self.html)
        self.assertIn("constitems=a.parts.map(p=>typeofp==='function'?p():p);", flat)
        body = self.html[self.html.index("function assemblyDrawing(a,mode){"):]
        body = body[:body.index("\n    }\n")]
        self.assertNotIn("a.parts.slice(", body, "함수 항목을 풀지 않고 그린다")


class TestTheAnalysisStandsOnTheSameColumns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rs, cls.ex = ST.run()
        cls.by = {r.id: r for r in cls.rs}

    def test_the_table_model_uses_the_console_positions(self):
        n, ix, iy = round(c("TBL_COLS_X")), c("TBL_INSET_X") * 1000, c("TBL_INSET_Y") * 1000
        Lx, Wy = c("CARRIER_L") * 1000, c("CARRIER_W") * 1000
        want = sorted((ix + (Lx - 2 * ix) * i / (n - 1), s * (Wy / 2 - iy))
                      for i in range(n) for s in (-1, 1))
        got = sorted(self.ex["table"]["cols"])
        self.assertEqual(len(got), PT.TABLE_COLS)
        for (gx, gy), (wx, wy) in zip(got, want):
            self.assertAlmostEqual(gx, wx, places=6)
            self.assertAlmostEqual(gy, wy, places=6)
        self.assertIn(f"{PT.TABLE_COLS}본", self.by["S7"].note)

    def test_the_chamber_model_uses_the_console_positions(self):
        nx, yc = round(c("RACK_COLS_X")), c("RACK_COL_Y") * 1000
        got = self.ex["chamber"]["cols"]
        self.assertEqual(len(got), PT.RACK_COLS)
        self.assertEqual(sorted({round(y, 6) for _, y in got}), [-round(yc, 6), round(yc, 6)])
        xs = sorted({round(x, 6) for x, _ in got})
        self.assertEqual(len(xs), nx)
        self.assertAlmostEqual(xs[-1] - xs[0], PT.CHAMBER_L, places=6)
        self.assertIn(f"{PT.RACK_COLS}본", self.by["S4"].note)

    def test_s8_is_judged_under_the_panel(self):
        """추력이 상판을 기울이면 기둥 밖 상판 끝이 가장 크게 움직인다 — 그 자리엔 패널이 없다."""
        t = self.ex["table"]
        self.assertTrue(self.by["S8"].ok)
        self.assertGreaterEqual(t["dz_edge"], t["dz"])
        self.assertIn(f"패널 밖 상판 끝 {t['dz_edge']:.3f}", self.by["S8"].note)


class TestTheBaseJointSharesTheThrustOverEveryColumn(unittest.TestCase):
    def test_j1(self):
        j1 = next(j for j in F.JOINTS if j["id"] == "J1")
        self.assertAlmostEqual(j1["V"], F.F_PEEL_D / PT.TABLE_COLS / 4, places=9,
                               msg="J1 전단이 기둥 수로 나뉘지 않았다")
        span = c("CARRIER_L") - 2 * c("TBL_INSET_X")
        self.assertAlmostEqual(j1["N"], F.F_PEEL_D * c("CZ") / span / 2 / 4, places=9)
        self.assertIn(f"기둥 {PT.TABLE_COLS}본", j1["note"])


if __name__ == "__main__":
    unittest.main()
