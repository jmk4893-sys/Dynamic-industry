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
STUDY = ROOT / "docs" / "dg-hk120-twin-cell.html"

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
        self.assertIn("cRhZ=()=>", self.b, "모노레일 높이가 배치에서 파생되지 않는다")
        self.assertIn("cDuctZ()+.55", self.b,
                      "트윈 본선이 배기 헤더 위로 올라가지 않는다")
        # 헤더 자체도 값이 아니라 갓돌에서 나와야 한다 — 단높임 지붕이 올라가면
        # 값으로 박은 헤더는 지붕 아래로 들어가고, 챔버 분기가 공중에 뜬다.
        src = CONSOLE.read_text(encoding="utf-8")
        self.assertIn("const ductZOf=decks=>Math.max(", src,
                      "배기 헤더 높이가 갓돌에서 파생되지 않는다")
        self.assertIn("const cDuctZ=()=>ductZOf(LC().decks);", src,
                      "활성 배치의 헤더가 그 식을 쓰지 않는다")
        self.assertNotIn("const CDUCT_Z=", src, "배기 헤더가 아직 값으로 박혀 있다")
        # 그리고 본선은 EX-101 포크 두상보 위여야 한다 — 만권롤과 카세트가
        # 방책을 넘는 유일한 길이라 막히면 무인 운전이 거기서 끝난다.
        self.assertIn("rhMinZ", self.b, "모노레일이 포크 두상보 하한을 받지 않는다")

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


class TestThePictureSaysWhatItIs(unittest.TestCase):
    """그림이 위상을 거짓말하지 않는가.

    가열실(지붕 5,880)과 냉각 랙(5,680)은 탑이고 탠덤 셀은 낮다. 낮은 각도로
    보면 그 탑 둘이 앞뒤로 서서 '탠덤 2대가 직렬' 처럼 읽히고, 정작 병렬인
    셀 둘은 앞 셀이 뒤 셀을 가려 한 대로 보인다 — 실제로 그렇게 읽혔다.
    형상이 맞아도 그림이 틀리면 그 그림은 못 쓴다."""

    @classmethod
    def setUpClass(cls):
        cls.src = console()
        # 이 절이 보는 것들은 그리기 계층에 있어 압축 배치 블록 밖이다 —
        # 전체를 공백만 지워 본다.
        cls.b = cls.src.replace(" ", "").replace("\n", "")

    def test_the_twin_looks_down_on_the_bay(self):
        """압축과 같은 낮은 시점을 쓰면 앞 셀이 뒤 셀을 가린다."""
        m = re.search(r"consttpresets=\[(.*?)\];", self.b)
        self.assertIsNotNone(m, "트윈 전용 시점이 없다")
        els = [float(v) for v in re.findall(r"el:([\d.]+)", m.group(1))]
        self.assertEqual(len(els), 4)
        self.assertGreaterEqual(min(els), .55,
                                f"트윈 시점 앙각 {min(els)} — 낮으면 두 셀이 겹쳐 한 대로 보인다")
        self.assertIn("viewPresets=()=>twinView()?tpresets:", self.b)

    def test_the_tandem_focus_fits_both_cells(self):
        """탠덤 베이는 x 로 3,800 인데 y 로 14,900 이다 — 세로로 넓다."""
        m = re.search(r"if\(twinView\(\)\)return\[(.*?)\]\[k%4\]", self.b)
        self.assertIsNotNone(m, "트윈 탠덤 확대 시점이 없다")
        radii = [float(v) for v in re.findall(r"radius:([\d.]+)", m.group(1))]
        self.assertEqual(len(radii), 4)
        span = 2 * (layout("HK120C")["celly"] + 3.85)          # 카트 바깥 끝까지
        self.assertGreaterEqual(min(radii), span,
                                f"확대 반경 {min(radii)} m 로는 폭 {span:.1f} m 베이가 안 들어온다")

    def test_the_focus_cameras_come_from_one_place(self):
        """확대·화면맞춤·시점변경이 값을 따로 들면 한 군데만 고쳐진다 —
        그러면 그 버튼만 Rev.20 의 x 17,800 으로 날아간다."""
        for fn in ("tandemFocusCam", "carriageFocusCam"):
            self.assertIn("const" + fn + "=(k=0)=>", self.b)
        # 부르는 자리 셋 — 확대 진입 · 화면 맞춤 · 시점 변경
        self.assertEqual(self.src.count("tandemFocusCam("), 3)
        self.assertEqual(self.src.count("carriageFocusCam("), 3)
        self.assertNotIn("17.8,y:0,z:1.9},az:compactView()", self.src,
                         "옛 삼항 좌표가 남아 있다")

    def test_no_label_gets_to_ignore_the_button(self):
        """라벨은 전부 '부품 라벨' 버튼에 달려 있다 — 예외를 두지 않는다.

        한동안 트윈의 스테이션 이름 넷만 always 로 두어 항상 띄웠다. 켜 둔
        라벨은 화면을 글자밭으로 만들고, 예외가 하나 있으면 다음 배치에서
        그 예외만 안 고쳐진다. 이름은 형상이 말한다 — 바닥 분기 도색과 셀
        갠트리 옆면 도색은 기계에 실제로 칠하는 것이라 버튼과 무관하다.
        """
        flat = self.src.replace(" ", "").replace("\n", "")
        self.assertIn("functionlabel3(text,p,color=C.white){if(!showLabels)return;", flat,
                      "label3 이 버튼을 우회할 수 있는 인자를 다시 갖고 있다")
        self.assertIn("labels.push({text,x:q.x,y:q.y,z:q.z,color})", flat,
                      "라벨이 우회 표식을 다시 들고 다닌다")
        self.assertIn("labels.sort((a,b)=>a.z-b.z);", self.src,
                      "정렬이 우회 표식을 다시 본다")
        for frag in ("C.heat,twinView())", "C.glass,twinView())", "C.teal,!!opt.tag)"):
            self.assertNotIn(frag, self.b, f"{frag} 라벨이 버튼을 우회한다")

    def test_the_twin_still_says_which_cell_is_which_without_labels(self):
        """라벨을 껐으므로 병렬이라는 사실은 도색이 말해야 한다."""
        self.assertIn("decalText(`DL-101 ${opt.tag}`", self.src,
                      "셀 갠트리 옆면 도색이 없다 — 라벨을 끄면 셀 구분이 사라진다")
        self.assertIn("if(twinView()){", self.b, "바닥 분기 도색이 없다")

    def test_the_cell_labels_say_which_of_two(self):
        """'DL-101' 만으로는 두 개가 있다는 사실이 안 읽힌다."""
        for frag in ("라인(병렬2중", "opt.tag==='A'?'−y':'+y'"):
            self.assertIn(frag, self.b, f"셀 이름표에 {frag} 이 없다")

    def test_the_console_carries_a_process_mimic(self):
        """카메라가 어떻게 서든 계통은 글로 남아야 한다."""
        self.assertIn("functiondrawFlowMimic()", self.b)
        self.assertIn("drawTitleBlock();drawFlowMimic();", self.b)
        self.assertIn("탠덤${L.cells}셀수평병렬", self.b)
        self.assertIn("확장옵션·두셀같은바닥", self.b)

    def test_the_floor_paint_shows_the_branch(self):
        """Y 자로 갈라졌다 합쳐지는 도색은 어느 각도에서도 분기로 읽힌다."""
        self.assertIn("if(twinView()){", self.b)
        for frag in ("floorStrip(sp1,0,br0,sg*cy,.17,P,.80)",
                     "floorStrip(br0,sg*cy,br1,sg*cy,.17,P,.88)",
                     "floorStrip(br1,sg*cy,mg,0,.17,P,.80)"):
            self.assertIn(frag, self.b, "바닥 분기 도색이 없다")

    def test_the_floor_mark_is_not_the_old_footprint(self):
        """Rev.20 의 발자국(x 4,500~31,700)을 그대로 쓰면 18.76m 기계가
        27m 짜리 테두리 안에 놓인다."""
        self.assertIn("functiongroundFor()", self.b)
        self.assertIn("mark:[x0,-L.fenceN,x1,L.fenceP]", self.b)
        self.assertIn("constg=groundFor();", self.b)


class TestEachCellIsItsOwnMachine(unittest.TestCase):
    """셀마다 자기 가드를 갖는가.

    트윈에서 DL 구간 외장을 열어 두 셀을 밖으로 내보낸 순간 셀은 자기 외장을
    잃었다 — 200°C 칼날과 갠트리 스윕이 방책 안에 그대로 드러난다. 방책은
    사람을 라인 밖에 두는 것이고 가드는 라인 안에서 일하는 사람을 움직이는
    축에서 떼어 놓는 것이라 둘은 다른 물건이다.

    그리고 이것이 '두 대' 라는 표시이기도 하다 — 같은 상자가 둘 나란히 서면
    병렬이라는 것이 이름표 없이 형상으로 읽힌다."""

    @classmethod
    def setUpClass(cls):
        cls.src = console()
        cls.b = cls.src.replace(" ", "").replace("\n", "")

    def test_each_twin_cell_gets_a_guard(self):
        self.assertIn("functioncCellGuard(dy,tag)", self.b)
        self.assertIn("if(opt.tag&&!sectionView)cCellGuard(dy,opt.tag)", self.b,
                      "가드가 셀마다 그려지지 않는다")

    def test_the_guard_height_is_bounded_from_three_sides(self):
        """갠트리 레일 상면 위 · 나이프 갠트리 상단 아래 · EX 인계 높이 아래.
        갠트리는 셀 안에서만 돌고 패널은 가드 위로 들어온다."""
        gz = float(re.search(r"CG_Z=([\d.]+)", self.b).group(1))
        rail_top = 1.95 + .22 / 2                       # CRAIL_Z + 레일 두께의 절반
        self.assertGreater(gz, rail_top, "가드가 갠트리 레일보다 낮다")
        self.assertLess(gz, 2.74, "가드가 나이프 갠트리 상단을 덮는다")
        cz = 1.15
        self.assertLess(gz, cz + 1.79 - .11, "가드가 EX-101 인계 높이를 막는다")

    def test_the_guard_plan_steps_around_the_cooling_rack_column(self):
        """+x 안쪽 모서리에는 GC-101 기둥 베이스플레이트가 깔려 있다."""
        self.assertIn("SX=11.44,SY=1.20", self.b)
        self.assertIn("run(true,SY,SX,x1)", self.b, "계단 구간이 없다")
        self.assertIn("run(false,SX,SY,CG_Y)", self.b)

    def test_the_outboard_wall_has_the_discharge_tunnel(self):
        """적층체 2,400 × 1,200 이 통째로 지나가는 개구."""
        self.assertIn("run(true,-CG_Y,x0,x1,[TX0,TX1])", self.b)
        self.assertIn("TX0=CE_X0-.14,TX1=CE_X1+.14", self.b)

    def test_the_inboard_wall_has_one_interlocked_door(self):
        self.assertIn("run(true,CG_Y,x0,SX,[DX-DW/2,DX+DW/2])", self.b)
        self.assertIn("도어인터록스위치", self.b)

    def test_the_transfer_portals_narrow_so_the_guard_fits(self):
        """통로 반폭은 셀중심 − 갠트리기둥 바깥 = 1,295 뿐이다. ±1,120 문형
        (바깥 1,195)으로는 가드 벽이 들어갈 100mm 가 남지 않는다."""
        self.assertIn("constcForkHalf=()=>twinView()?FORK_HALF_TWIN:FORK_HALF_STD", self.b)
        self.assertIn("constFORK_HALF_STD=1.12,FORK_HALF_TWIN=.95", self.b,
                      "문형 반폭이 이름 있는 상수에서 나오지 않는다")
        L = layout("HK120C")
        half, post, wall = .95, .17, .05
        aisle_half = L["celly"] - (1.42 + post / 2)
        self.assertGreater(aisle_half - (half + .15 / 2) - wall / 2, .05,
                           "좁힌 문형으로도 가드 벽이 통로에 못 선다")
        # 두 문형 모두 배치가 정한 폭으로 부른다
        for call in ("cFork(EXX,'EX',-1,", "cFork(CST.DL.x1+.08,'GL',1,"):
            i = self.b.index(call)
            self.assertIn("cForkHalf()", self.b[i:i + 260],
                          f"{call} 이 배치를 보지 않는다")

    def test_the_cutaway_does_not_hide_the_guards(self):
        """컷어웨이는 불투명 외장을 걷어내려고 있다. 가드는 이미 투명하므로
        걷어내면 두 상자만 사라진다."""
        self.assertIn("tandemFocus=true;sectionView=!twinView();", self.b)

    def test_the_vacuum_skid_moves_out_of_the_guard(self):
        self.assertIn("constvx=CST.GC.x0+(twinView()?.75:.5)", self.b)


class TestTheThreeStreamsAreVisible(unittest.TestCase):
    """세 계통이 그림에서 실제로 보이는가.

    형상이 있어도 나오는 단계가 좁으면 '표현이 안 된다' 로 읽힌다 — 실제로
    그렇게 읽혔다. 필름은 박리 중에만 걸려 있었고(나머지 아홉 단계에서 권취부는
    빈 롤러 셋), 롤은 늘 코어 Ø300 이었으며(295장에 걸쳐 자라는 물건이다),
    셀/EVA 는 트로프 위 세 단계와 카트 위 한 장 사이가 비어 있었다."""

    @classmethod
    def setUpClass(cls):
        cls.src = console()
        cls.b = cls.src.replace(" ", "").replace("\n", "")

    def test_the_web_stays_threaded_between_panels(self):
        """통과 사이에도 필름은 드럼에서 댄서·아이들러까지 걸려 있다."""
        self.assertIn("functioncWebThread(panels)", self.b)
        self.assertIn("cWebThread(wn);", self.b)
        self.assertIn("if(!(cs.onTable&&cs.peeling))cWebTail();", self.b,
                      "박리하지 않을 때 필름 자유단이 없다")
        # 상시 구간은 박리 여부와 무관한 자리에서 불려야 한다
        i = self.b.index("cWebThread(wn);")
        self.assertLess(self.b.index("cRoll(wn,"), i,
                        "웹 걸기가 롤과 같은 블록에 있지 않다")

    def test_the_rollers_show_the_film_wrapping_them(self):
        self.assertIn("functionwebWrap(cx,cz,r,a0,a1,seg=7)", self.b)
        self.assertIn("webWrap(CID_X,CID_Z", self.b)
        self.assertIn("webWrap(CDN_X,", self.b)

    def test_the_roll_is_not_forever_at_core_diameter(self):
        """코어만인 시간은 전체의 1/295 다. 늘 코어면 권취부가 축으로 보인다."""
        m = re.search(r"constCROLL_BASE=Math\.round\(ROLL_FULL_PANELS\*([\d.]+)\)", self.b)
        self.assertIsNotNone(m, "권취 바탕값이 없다")
        frac = float(m.group(1))
        self.assertGreater(frac, .2)
        self.assertLess(frac, .9)
        self.assertIn("constwn=CROLL_BASE+cs.wound;", self.b)
        self.assertIn("constn=CROLL_BASE+cState(index,local).wound", self.b,
                      "HUD 가 3D 와 다른 권취량을 말한다")

    def test_the_cell_stream_does_not_break_between_trough_and_cart(self):
        self.assertIn("if(i>=4&&i<=7)withPartOffset(off,()=>{", self.b)
        self.assertIn("if(i>=6)withPartOffset(off,()=>{", self.b)
        self.assertIn("constn=1+((carriageCycleNo+c)%4);", self.b,
                      "카트에 한 장만 얹으면 평적이 안 보인다")

    def test_the_roll_reclaim_has_visible_gear_and_a_standing_route(self):
        """357 kg 이 셀당 4.9시간마다 나간다 — 그 수단과 길이 보여야 한다."""
        self.assertIn("functioncHoist(hy,rz,bsy)", self.b)
        # 주석이 아니라 그려지는 것을 본다 — 설명만 남고 형상이 빠질 수 있다
        for part, frag in (
                ("훅블록", "box(V(CRAIL_X0,hy,rz-.56),V(.20,.24,.16),C.steel2)"),
                ("슬링", "line([V(CRAIL_X0,hy,rz-.80),V(CRAIL_X0,hy+dyy,bz)]"),
                ("인양빔", "box(V(CRAIL_X0,hy,bz),V(.16,ROLL_FACE+.12,.10),C.steel2)"),
                ("코어 그리퍼", "box(V(CRAIL_X0,hy+dyy,bz-.09),V(.11,.09,.10),C.yellow)")):
            self.assertIn(frag, self.b, f"인양구에 {part} 이 그려지지 않는다")
        self.assertIn("line([V(CRAIL_X0,hy,rz-.50),V(CRAIL_X0,bsy,rz-.50)]", self.b,
                      "반출 경로가 상시 표시되지 않는다")
        self.assertIn("cHoist(0,RH_Z,BS_SADDLE.y);", self.b)      # 압축
        self.assertIn("cHoist(ya,RHZ,BSY);", self.b)              # 트윈

    def test_each_cell_names_its_own_two_outlets(self):
        """셀이 둘이면 반출도 둘이다 — 이름이 없으면 어느 셀 것인지 모른다."""
        self.assertIn("WR-101${opt.tag}·백시트권취부", self.b)
        self.assertIn("CE-201${opt.tag}→CS-201${opt.tag}·셀/EVA반출", self.b)
        self.assertIn("C.sheet,!!opt.tag)", self.b, "권취부 이름표가 항상 뜨지 않는다")
        self.assertIn("C.cell2,true)", self.b, "반출 이름표가 항상 뜨지 않는다")


class TestTheStandardAndTheOptionAreNamedAsSuch(unittest.TestCase):
    """두 구조를 나란히 보존하기로 했다면, 어느 쪽이 납품 표준이고 어느 쪽이
    확장 옵션인지가 그림과 문서에 적혀 있어야 한다. 안 적으면 다음 사람이
    둘 중 아무거나 고르고, 고른 줄도 모른다.

    배치 방향도 마찬가지다 — 병렬은 수직 적층이 아니라 수평이다. 형상만으로
    남겨 두면 다음 개정에서 '바닥을 아끼자' 는 이유로 쌓이게 된다."""

    @classmethod
    def setUpClass(cls):
        cls.src = console()
        cls.b = cls.src.replace(" ", "").replace("\n", "")
        cls.study = STUDY.read_text(encoding="utf-8")

    def test_each_layout_declares_its_role(self):
        for name, role in (("HK60C", "표준"), ("HK120C", "확장 · 수평 병렬")):
            self.assertEqual(layout(name)["role"], role,
                             f"{name} 이 자기 역할을 말하지 않는다")
            self.assertTrue(layout(name)["roleNote"],
                            f"{name} 에 역할 설명이 없다")

    def test_the_console_shows_the_role_where_it_is_read(self):
        """버튼·명판·표제란 — 셋 다 어느 구조인지 말해야 한다."""
        self.assertIn("L.cells>1?'수평 병렬':'단일 탠덤'", self.src, "버튼이 구조를 말하지 않는다")
        self.assertIn("[${L.role}]${L.roleNote}", self.b, "명판이 역할을 말하지 않는다")
        self.assertIn("${TL.plan}·${TL.role}", self.b, "표제란이 역할을 말하지 않는다")

    def test_the_mimic_says_the_parallel_is_horizontal(self):
        self.assertIn("탠덤${L.cells}셀수평병렬", self.b)
        self.assertIn("두셀같은바닥—쌓지않는다", self.b,
                      "수평이라는 것이 미믹에 없다")
        self.assertIn("납품표준·직렬5스테이션", self.b)

    def test_the_two_cells_share_one_floor_datum(self):
        """수평의 정의 — 셀 오프셋이 y 에만 걸린다. z 가 끼면 그것은 적층이다."""
        m = re.search(r"const cellY=n=>(.*?);", self.src)
        self.assertIsNotNone(m)
        self.assertNotIn("z", m.group(1), "셀 오프셋에 z 가 들어 있다 — 수평이 아니다")
        # 한 자리만 보면 안 된다 — 셀을 놓는 자리가 정적·동적 둘이고,
        # 한쪽만 쌓아도 그것은 적층이다.
        places = re.findall(r"y:cellY\(c\),z:([^}]*)\}", self.b)
        self.assertGreaterEqual(len(places), 2, "셀을 놓는 자리를 다 찾지 못했다")
        for z in places:
            self.assertEqual(z, "0", f"셀 오프셋 z 가 {z} 다 — 수평이 아니라 적층이다")

    def test_the_study_records_the_decision(self):
        """검토서가 '이것도 가능하다' 로 끝나면 결정이 남지 않는다."""
        st = self.study.replace(" ", "").replace("\n", "")
        self.assertIn("납품표준안은<strong>DG-HK60C단일탠덤</strong>", st)
        self.assertIn("확장옵션으로설계에나란히보존", st)
        self.assertIn("수직적층이아니라", st)

    def test_the_study_explains_why_horizontal_and_what_it_costs(self):
        st = self.study.replace(" ", "").replace("\n", "")
        self.assertIn("수평병렬을택한이유", st, "배치 방향의 근거가 없다")
        for why in ("추락", "정비발판", "같은바닥기준면"):
            self.assertIn(why, st, f"수평을 택한 이유에 {why} 가 없다")
        self.assertIn("setText('orientArea'", self.study,
                      "면적 대가가 모델에서 나오지 않는다")


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
