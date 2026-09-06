"""DG-HK120C 트윈 배치 — 콘솔의 3D 가 검토서와 같은 배치를 그리는가.

검토서(docs/dg-hk120-twin-cell.html)는 단수·램프수·셀 중심간격·방책 폭을
부등식에서 유도한다. 콘솔의 3D 는 그 배치를 세워 보는 자리다. 둘이 갈라지면
갈라진 줄도 모르고 갈라진다 — 검토서는 표를 다시 그리고 3D 는 그대로 있거나,
3D 만 고쳐 놓고 검토서가 옛 숫자를 계속 말하거나.

이 시험이 지키는 것은 셋이다.

  1. 콘솔의 트윈 설정값이 검토서의 유도값과 같을 것. 값을 두 벌 적으면
     반드시 갈라진다.
  2. 배치가 갈라지는 자리마다 *설정*을 보고 그릴 것. 압축 전용 상수를 그대로
     둔 채 트윈을 얹으면 7단 랙에 3장만 들어간 그림이 나오고, 그 그림은
     간섭검사에도 안 걸린다 — 겹치지 않으니까.
  3. 트윈에서 새로 생긴 자리다툼의 해법이 코드에 남아 있을 것. 방출 문형과
     모노레일, 모노레일과 배기 헤더, 보관열과 방책 — 셋 다 압축에는 없던
     교차이고, 셋 다 위에서 내려다봐야만 보인다.

검토서를 베끼지 않는다. 검토서의 입력에서 여기서 다시 유도한 뒤 콘솔과
대조한다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

import console_consts                                        # noqa: E402

from .test_twin_cell_study import aisle, celly, geo, half_width

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"

DECKS, LAMPS, CELLS = 7, 80, 2


def console():
    return CONSOLE.read_text(encoding="utf-8")


def layout(name):
    """콘솔의 배치 설정 하나 — const HK120C={...}; 안의 값들."""
    m = re.search(rf"const {name}=\{{(.*?)\}};", console(), re.S)
    assert m, f"콘솔에 {name} 설정이 없다"
    blk = m.group(1)
    out = {}
    for k, v in re.findall(r"(\w+)\s*:\s*('[^']*'|[A-Za-z0-9_.]+)", blk):
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = v.strip("'")
    return out


def vec(name):
    """콘솔의 V(x,y,z) 상수 하나."""
    m = re.search(rf"const {name}=V\(([-\d.]+),([-\d.]+),([-\d.]+)\)", console())
    assert m, f"콘솔에 {name} 이 없다"
    return tuple(float(g) for g in m.groups())


def body():
    """압축 계열이 그려지는 부분만 — Rev.20 쪽 코드에 걸리지 않도록."""
    s = console()
    return s[s.index("const HK60C="):s.index("function drawTitleBlock")]


class TestTheConsoleAndTheStudyAgree(unittest.TestCase):
    """수치가 두 벌이면 반드시 갈라진다."""

    @classmethod
    def setUpClass(cls):
        cls.L = layout("HK120C")

    def test_the_model_and_revision_are_named(self):
        self.assertEqual(self.L["model"], "DG-HK120C")
        self.assertEqual(self.L["id"], "twin")

    def test_the_deck_and_lamp_count_are_the_derived_ones(self):
        self.assertEqual(self.L["decks"], DECKS)
        self.assertEqual(self.L["lamps"], LAMPS)
        self.assertEqual(self.L["lamps"] % (self.L["decks"] + 1), 0,
                         "램프가 뱅크로 나누어떨어지지 않는다")

    def test_the_cell_pitch_comes_from_the_study(self):
        self.assertAlmostEqual(self.L["celly"], celly(), delta=.005,
                               msg=f"셀 중심간격 콘솔 {self.L['celly']} ≠ 검토서 {celly():.3f}")
        self.assertAlmostEqual(self.L["aisle"], aisle(), delta=.005,
                               msg=f"중앙 통로 콘솔 {self.L['aisle']} ≠ 검토서 {aisle():.3f}")

    def test_the_fence_comes_from_the_study(self):
        """트윈은 반출이 양쪽으로 나뉜다 — 방책도 양쪽이 같아야 한다."""
        self.assertEqual(self.L["fenceP"], self.L["fenceN"])
        self.assertAlmostEqual(self.L["fenceP"], half_width(), delta=.005,
                               msg=f"방책 콘솔 {self.L['fenceP']} ≠ 검토서 {half_width():.3f}")

    def test_the_aisle_and_the_pitch_are_consistent(self):
        """통로는 셀 중심간격에서 다시 나온다 — 둘 중 하나만 고치면 드러난다."""
        self.assertAlmostEqual(2 * (self.L["celly"] - geo()["gantryY"]),
                               self.L["aisle"], delta=.005)


class TestTheLayoutIsConfigured(unittest.TestCase):
    """배치를 함수로 나누면 한쪽만 고쳐지는 날이 온다."""

    @classmethod
    def setUpClass(cls):
        cls.b = body().replace(" ", "").replace("\n", "")

    def test_the_rack_deck_count_follows_the_layout(self):
        self.assertIn("for(letk=0;k<(opt.decks??DECKS);k++)", self.b,
                      "랙 단수가 배치를 보지 않는다")

    def test_the_chamber_and_cooling_rack_follow_the_layout(self):
        for fn in ("cChamber", "cGlassRack"):
            i = self.b.index("function" + fn + "()")
            head = self.b[i:i + 160]
            self.assertTrue("LC().decks" in head or ("LC()" in head and ".decks" in head),
                            f"{fn} 이 단수를 배치에서 받지 않는다")

    def test_the_moving_panels_follow_the_layout(self):
        """가열실 안의 장 수는 단수와 같아야 한다 — 7단에 3장이면 열수지가 거짓말이 된다."""
        i = self.b.index("functioncompactDynamic")
        seg = self.b[i:i + 1400]
        self.assertIn("DK=LC().decks", seg, "동적 레이어가 단수를 배치에서 받지 않는다")
        self.assertNotIn("Math.min(DECKS,", seg, "동적 레이어에 압축 단수가 박혀 있다")

    def test_two_cells_are_drawn_mirrored_and_unshared(self):
        """셀 B 는 셀 A 의 거울이고, 공용 설비는 한 번만 그린다."""
        self.assertIn("cTandem({mirror:c===1,shared:false,tag:c?'B':'A'})", self.b)
        self.assertIn("withPartOffset(o.tandem,()=>cTwinShared())", self.b)

    def test_the_cells_sit_either_side_of_the_centre(self):
        self.assertIn("cellY=n=>LC().cells===1?0:(n?LC().celly:-LC().celly)", self.b)

    def test_the_two_cells_run_half_a_takt_apart(self):
        """같은 위상으로 돌리면 챔버가 두 장을 동시에 내야 한다."""
        self.assertIn("cellPhase=(p,n)=>n?((p+.5)%1):p", self.b)


class TestTheTwinCrossingsAreResolved(unittest.TestCase):
    """압축에는 없던 교차 셋 — 위에서 내려다봐야만 보이는 것들."""

    @classmethod
    def setUpClass(cls):
        cls.b = body().replace(" ", "").replace("\n", "")

    def test_the_skin_opens_over_the_tandem_bay(self):
        """DL 구간 벽을 그대로 두면 두 셀이 외장 안에 묻히고 카트가 못 나간다."""
        self.assertIn("cSkinRuns=()=>cBayOpen()?[[CSKIN_X0,COP0],[COP1,CSKIN_X1]]:[[CSKIN_X0,CSKIN_X1]]",
                      self.b)
        self.assertIn("cBayOpen=()=>twinView()", self.b)

    def test_the_discharge_portal_clears_the_monorail(self):
        """EX-101 마스트와 RH-201 본선이 같은 x 를 쓰면 마스트가 레일을 뚫는다."""
        self.assertIn("cMastOut=()=>twinView()?CMAST_OUT+.20:CMAST_OUT", self.b)
        self.assertIn("EXX=cMastOut()", self.b)

    def test_the_monorail_clears_the_exhaust_header(self):
        """트윈 본선은 셀 B 롤까지 오므로 배기 헤더(y1,880)를 가로지른다."""
        self.assertIn("cRhZ=()=>twinView()?CDUCT_Z+.55:RH_Z", self.b)

    def test_the_storage_rows_move_out_with_the_fence(self):
        """방책이 물러나면 보관대도 같이 나가야 방책 밖에 남는다."""
        self.assertIn("cOutRow=()=>Math.max(0,LC().fenceN-CFENCE_YN)", self.b)
        self.assertIn("cBsY=()=>BS_SADDLE.y-cOutRow()", self.b)
        self.assertIn("cKcY=()=>CKC_RACK_Y-cOutRow()", self.b)

    def test_the_storage_rows_end_up_outside_the_twin_fence(self):
        """압축의 −5,200 / −7,000 은 방책 −4,200 밖이지만 트윈 방책은 더 나간다."""
        twin = layout("HK120C")["fenceN"]
        compact = console_consts.const("CFENCE_YN")
        out = max(0.0, twin - compact)
        for name, base in (("BS-301", -vec("BS_SADDLE")[1]),
                           ("KC-301", -console_consts.const("CKC_RACK_Y"))):
            self.assertGreater(base + out, twin,
                               f"{name} 보관대가 트윈 방책({twin} m) 안에 남는다")

    def test_the_twin_fence_is_stepped_like_the_study(self):
        """직사각형으로 두르면 점유면적을 과장하고, 넓어지는 것이 DL 하나라는
        이 구성의 요지가 그림에서 지워진다 — 검토서 GA-201 과 같아야 한다."""
        self.assertIn("NP=twin?CFENCE_Y:FP,NN=twin?CFENCE_YN:FN", self.b)
        self.assertIn("DX0=CST.DL.x0-.24,DX1=CST.DL.x1+.24", self.b)
        self.assertIn("fenceSegment(DX0,sgn*nf,DX0,sgn*FP)", self.b, "계단 리턴이 없다")
        self.assertIn("fenceSegment(DX1,sgn*nf,DX1,sgn*FP)", self.b)
        self.assertIn("fenceSegment(CFENCE_X0,sgn*nf,DX0,sgn*nf)", self.b)

    def test_the_discharge_traverse_sits_between_gantry_and_roll(self):
        """레일은 나이프 갠트리(2,740) 위, 만권 롤 하단(3,400) 아래여야 한다."""
        self.assertIn("EXZ=CZ+2.01,EXC=CZ+1.79", self.b)
        cz, full_r, drum_z = 1.15, .30, 3.70
        self.assertGreater(cz + 2.01 - .09, 2.74, "횡이송 레일이 갠트리를 친다")
        self.assertLess(cz + 2.01 + .09, drum_z - full_r, "횡이송 레일이 만권 롤을 친다")


class TestTheLayoutOrderStartsAtTheDeliveredLine(unittest.TestCase):
    def test_the_console_boots_on_the_delivered_layout(self):
        """확장안이 먼저 뜨면 발주자가 그것을 납품 배치로 읽는다."""
        self.assertIn("setLayout('compact');", console())
        self.assertIn("const LAYOUT_ORDER=['compact','twin','rev20'];",
                      console().replace("\n", ""))

    def test_the_title_block_names_the_active_layout(self):
        """표제란이 압축을 말하면서 트윈을 그리면 그 도면은 못 쓴다."""
        b = body().replace(" ", "")
        self.assertNotIn("'DG-HK60C압축배치·개념제작도'", b)
        self.assertIn("TL.model", console())
        self.assertIn("plan:'1가열실·탠덤2셀병렬'", console().replace(" ", ""))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
