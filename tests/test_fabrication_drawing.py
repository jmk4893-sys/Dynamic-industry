"""제작도가 제작도인지 — 개념도와 무엇이 달라야 하는가.

사양서 1.2 는 오랫동안 이렇게 적고 있었다: "콘솔의 제작도 탭은 외형 치수를
글자로 표기한 개념 배치이며 판두께·공차·용접기호·끼워맞춤·가공기준면을
포함하지 않는다." 사실이었다 — 그 탭은 모듈 치수와 무관하게 모든 모듈에
같은 고정 사각형 셋(210×210 / 210×120 / 150×120)을 그렸고, 부품란은 전
행의 수량이 "1 SET" 였다. 축척도 투상법도 개정란도 없었다.

F-002 는 그 자리를 메운다. 그런데 도면은 조용히 낡는다 — 3D 는 상수를
따라 움직이는데 도면은 그때 적은 숫자로 남는 것이 이 저장소가 계속 고쳐 온
실패다. 그래서 여기서는 두 가지를 본다.

  ① 제작도가 갖춰야 할 것을 실제로 담고 있는가 (판두께·공차·용접기호·
     데이텀·기하공차·표면조도·축척·투상법·개정란·부품란)
  ② 그 치수가 값이 아니라 모델 상수에서 나오는가

②가 없으면 ①은 한 번만 참이다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"


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


class TestTheDraftingPrimitivesExist(unittest.TestCase):
    """제도 기호가 없으면 도면이 아니라 그림이다."""

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")

    def test_the_sheet_is_a_real_paper_size(self):
        self.assertIn("const A3W=420,A3H=297;", self.src,
                      "시트가 ISO 216 A3 밀리미터 좌표가 아니다")
        self.assertIn('viewBox="0 0 ${A3W} ${A3H}"', self.src,
                      "제작도 시트가 A3 좌표를 쓰지 않는다")

    def test_every_drafting_symbol_is_available(self):
        for fn, why in (
            ("dimH", "수평 치수선"), ("dimV", "수직 치수선"),
            ("weldSym", "용접기호 (ISO 2553)"),
            ("datum", "데이텀 (가공기준면)"),
            ("fcf", "기하공차 틀 (ISO 1101)"),
            ("rough", "표면조도 (ISO 1302)"),
        ):
            self.assertIn(f"function {fn}(", self.src, f"{why} 를 그릴 수단이 없다")
        self.assertIn("const thirdAngle=", self.src,
                      "투상법 기호가 없다 — 각법을 밝히지 않으면 좌우가 뒤집혀 가공된다")

    def test_two_line_weights(self):
        """외형선과 치수선이 같은 굵기면 무엇이 부재인지 도면에서 구분되지 않는다."""
        m = re.search(r"const LW=\{([^}]*)\}", self.src)
        self.assertIsNotNone(m, "선 굵기 계열이 없다")
        w = {k: float(v) for k, v in re.findall(r"(\w+):([\d.]+)", m.group(1))}
        self.assertGreater(w["out"], w["thin"], "외형선이 치수선보다 굵지 않다")

    def test_the_title_block_carries_what_iso_7200_asks(self):
        body = _fn(self.src, "fabTitleBlock")
        for token, why in (
            ("SCALE", "축척"), ("MATERIAL", "재질"), ("MASS", "질량"),
            ("GENERAL TOL.", "일반공차"), ("PROJECTION", "투상법"), ("SHEET", "시트번호"),
        ):
            self.assertIn(token, body, f"표제란에 {why} 칸이 없다")
        self.assertIn("thirdAngle(", body, "표제란이 투상법 기호를 그리지 않는다")
        self.assertIn("function revBlock(", self.src,
                      "개정란이 없다 — 같은 도면번호의 다른 도면이 현장에 돌면 아무도 믿지 않는다")


class TestTheChamberSheetIsFabricationLevel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.body = _fn(cls.src, "chamberFabDrawing")

    def test_it_carries_the_six_things_a_concept_drawing_lacks(self):
        """이름만 있는 것과 그려지는 것은 다르다 — 이어붙는 자리까지 본다.

        `''&&weldSym(...)` 처럼 호출은 남기고 결과만 버려도 이름 검사는
        통과한다. 그래서 문자열 연결(+) 바로 뒤에 오는지를 본다.
        """
        for pattern, why in (
            (r"\+weldSym\(", "용접기호"),
            (r"\+datum\(", "가공기준면"),
            (r"\+fcf\(", "기하공차"),
            (r"\+rough\(", "표면조도"),
            (r"\+ revBlock\(", "개정란"),
            (r"\+ fabTitleBlock\(", "표제란"),
        ):
            self.assertRegex(self.body, pattern, f"{why} 가 시트에 이어붙지 않는다")
        self.assertIn("ISO 2768", self.body, "일반공차 표기가 없다")

    def test_the_bill_of_material_names_materials_not_just_parts(self):
        """'1 SET' 아홉 줄로는 견적을 낼 수 없다 — 행마다 재질·규격이 있어야 한다."""
        self.assertNotIn("1 SET", self.body, "부품란이 아직 수량을 뭉뚱그린다")
        m = re.search(r"const bom=\[(.*?)\n      \];", self.body, re.S)
        self.assertIsNotNone(m, "부품란 배열을 찾지 못했다")
        rows = re.findall(r"\['(\d+)','([^']*)','([^']*)','([^']*)',([^\]]+)\]", m.group(1))
        self.assertGreaterEqual(len(rows), 8, "부품란이 8행 미만이다")
        for no, name, spec, finish, qty in rows:
            self.assertRegex(
                spec, r"(SS400|SUS304|GFRP|AL|kW|mm|t\b|kg/m³|×)",
                f"품번 {no} '{name}' 의 재질·규격 '{spec}' 이 규격이 아니다")
        specs = " ".join(r[2] for r in rows)
        for want in ("SS400", "SUS304", "GFRP"):
            self.assertIn(want, specs, f"부품란에 {want} 규격이 없다")

    def test_every_dimension_comes_from_the_model(self):
        """도면에 숫자를 적으면 단수를 옮길 때 3D 만 따라오고 도면은 남는다."""
        for expr, why in (
            ("mm(HC_DZ)", "단 간격"),
            ("mm(CL_WALL)", "벽 두께"),
            ("mm(HC_Z+.94)", "챔버 높이"),
            ("mm(DECK_L)", "데크 길이"),
            ("bankLampCount(", "뱅크별 램프 수"),
            ("${DECKS}", "단수"),
        ):
            self.assertIn(expr, self.body, f"{why} 가 상수에서 나오지 않는다")
        # 3단 시절 치수가 도형·치수선에 남아 있으면 안 된다.
        # 개정란(desc:)은 이력이므로 옛 값을 적는 것이 맞다 — 빼고 본다.
        drawn = re.sub(r"desc:`[^`]*`|desc:'[^']*'", "", self.body)
        for stale in ("3,620", "2,910", "3단 40등"):
            self.assertNotIn(stale, drawn, f"옛 치수 '{stale}' 가 도면에 남아 있다")

    def test_the_revision_row_records_why_the_deck_count_moved(self):
        self.assertIn("revBlock(", self.body, "개정란이 없다")
        self.assertRegex(self.body, r"유리 열응력 7\.05 . 4\.23 MPa",
                         "개정 사유가 유리 열응력임을 적지 않았다")

    def test_the_sheet_says_it_is_not_for_construction(self):
        """참고도임을 밝히지 않으면 제작사가 이 도면으로 착수한다.

        도면 안(주기)과 도면 밖(설명문) 두 곳에 있어야 한다 — 시트만 인쇄해
        돌리면 화면의 설명문은 따라가지 않는다.
        """
        notes = re.search(r"const notes=\[(.*?)\];", self.body, re.S)
        self.assertIsNotNone(notes, "주기를 찾지 못했다")
        self.assertIn("Not For Construction", notes.group(1),
                      "도면 주기가 참고도임을 밝히지 않는다 — 인쇄하면 이것만 남는다")
        self.assertIn("Not For Construction", self.body.split("const notes=")[0]
                      + self.body.split("];", 1)[-1],
                      "화면 설명문이 참고도임을 밝히지 않는다")


class TestNoSheetPrintsTextOverText(unittest.TestCase):
    """글자가 글자 위에 얹히면 인쇄한 도면에서 둘 다 못 읽는다.

    E-001 은 접지 설명이 '필수 계전·계측' 상자 안에 있었고, C-001 은
    안전회로 설명이 표제란 위로 흘러들어가 있었다. 화면에서는 겹쳐도
    글자가 보이지만 인쇄하면 서로를 지운다.

    좌표를 브라우저에서 재는 것은 시험 밖(스크래치의 경계상자 검사)에서
    하고, 여기서는 다시 그 자리로 돌아가지 않게 좌표를 못 박는다.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")

    def test_the_earth_note_sits_above_the_relay_box(self):
        box = re.search(r'<rect x="585" y="(\d+)"', self.src)
        self.assertIsNotNone(box, "E-001 계전·계측 상자를 찾지 못했다")
        note = re.search(r'<text x="600" y="(\d+)"[^>]*>PE BAR', self.src)
        self.assertIsNotNone(note, "E-001 접지 설명을 찾지 못했다")
        self.assertLess(int(note.group(1)), int(box.group(1)),
                        "접지 설명이 계전·계측 상자 안에 있다")

    def test_the_safety_note_clears_the_title_block(self):
        note = re.search(r'<text x="(\d+)" y="\d+"[^>]*>Safety: OSSD', self.src)
        self.assertIsNotNone(note, "C-001 안전회로 설명을 찾지 못했다")
        # 개념 시트 표제란은 x 870 에서 시작한다 — 그 앞에서 끝나야 한다
        self.assertLess(int(note.group(1)), 300,
                        "안전회로 설명이 표제란 쪽으로 흘러간다")


class TestTheWinderSheetShowsBothJourneys(unittest.TestCase):
    """M-006 은 도면이 두 장면을 함께 담아야 한다.

    하나는 필름이 지나가는 길(박리점 → GR-W1 → 아이들러 → DN-101 → 드럼)이고,
    다른 하나는 다 감긴 357 kg 롤이 나가는 길(RH-201 → 방책 밖 BS-301)이다.
    둘째가 없으면 무인 운전이 4.9시간마다 끊긴다 — 보관대가 방책 안이면
    사람이 그 주기로 들어가야 하기 때문이다.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.body = _fn(cls.src, "winderFabDrawing")
        cls.flat = cls.body.replace(" ", "")

    def test_the_sheet_is_reachable(self):
        self.assertIn('data-drawing="winder"', self.src, "탭이 없다")
        self.assertIn("drawingTab==='winder')drawingContent.innerHTML=winderFabDrawing()",
                      self.src, "탭이 시트를 그리지 않는다")

    def test_it_uses_the_fabrication_frame(self):
        for token, why in (("fabSheet(", "A3 도면틀을 쓰지 않는다"),
                           ("fabTitleBlock({", "ISO 7200 표제란이 없다"),
                           ("revBlock([", "개정란이 없다"),
                           ("no:'F-006'", "도면번호가 없다")):
            self.assertTrue(token in self.body, why)

    def test_both_journeys_are_drawn(self):
        """웹 경로만 그리면 롤이 어떻게 나가는지가 도면에 없다."""
        for part in ("CID_X", "CDN_X", "CDRUM", "WR_CORE_R", "WR_FULL_R"):
            self.assertIn(part, self.body, f"웹 경로에 {part} 가 없다")
        for part in ("RH_Y0", "CKC_RACK_Y", "BS_SADDLE", "CFENCE_YN"):
            self.assertIn(part, self.body, f"반출 경로에 {part} 가 없다")
        self.assertIn("롤 반출 단면 B-B", self.body, "반출 단면이 없다")
        # 그리기만 하고 시트에 붙이지 않으면 도면에는 없는 것과 같다
        self.assertIn("+ route + seq + tbl", self.body,
                      "반출 단면이 시트에 조립되지 않는다")

    def test_the_roll_mass_and_interval_are_derived(self):
        """357 kg 도 4.9시간도 백시트 두께와 순생산에서 나온다."""
        self.assertIn("ROLL_MASS", self.body, "롤 질량이 유도되지 않는다")
        self.assertIn("ROLL_FULL_PANELS", self.body, "롤당 장수가 유도되지 않는다")
        self.assertIn("HRS=ROLL_FULL_PANELS/MODEL.netTarget", self.flat,
                      "교체 주기가 롤당 장수 ÷ 순생산에서 나오지 않는다")
        self.assertIn("ROLLKG=ROLL_MASS", self.flat,
                      "롤 질량이 모델값에서 나오지 않는다")
        self.assertIn("BACKSHEET_T", self.body, "백시트 두께가 근거로 적히지 않는다")

    def test_the_sheet_says_the_drum_does_not_wind_during_peel(self):
        """이 계통의 요지 — GR-W1 이 같이 가므로 웹 길이가 상쇄된다."""
        self.assertIn("박리 중 드럼", self.body, "박리 중 권취 0 이 도면에 없다")
        self.assertIn("상쇄", self.body)
        self.assertIn("CDN_Z1-CDN_Z0", self.flat, "댄서 행정이 유도되지 않는다")

    def test_the_ejection_sequence_is_on_the_sheet(self):
        """인터록이 잠그는 순서가 도면에 없으면 안전회로 시험에 근거가 없다."""
        self.assertIn("const SEQ=[", self.body, "반출 순서가 없다")
        self.assertIn("반출 순서", self.body)
        self.assertGreaterEqual(self.body.count("','"), 6, "순서 단계가 모자란다")

    def test_it_records_what_rev20_had_that_this_does_not(self):
        """예비축·절단암·격리셔터·롤 포트·코너 승강대는 압축 배치에 없다."""
        self.assertIn("예비 권취축", self.body, "Rev.20 과의 차이가 도면에 없다")
        self.assertIn("단일 고정 드럼", self.body)
        self.assertIn("단일 고정 드럼", self.src[self.src.index("no:'F-006'") - 4000:],
                      "개정란·표제가 정정을 담지 않는다")

    def test_it_does_not_pretend_to_know_the_shaft(self):
        self.assertIn("정하지 않는 것", self.body)
        self.assertIn("Not For Construction", self.body)

    def test_the_sheet_never_reads_the_layout_the_screen_happens_to_show(self):
        for bad in ("LC()", "cForkHalf()", "twinView()", "compactView()"):
            self.assertNotIn(bad, self.body, f"F-006 이 활성 배치({bad})를 읽는다")


class TestTheForkSheetIsOneDrawingForFour(unittest.TestCase):
    """모듈표는 이 모듈을 'LI-101 승강프레임' 하나 · 1 SET 으로 적고 있었다.

    압축 배치는 같은 문형을 넷 세운다 — LI-101 투입 · EX-101 방출 ·
    GL-101 적입 · GU-101 인출. 넷이 같은 도면이라는 것이 이 시트의 요지이고,
    그것이 지그·검사·예비품을 한 벌로 끝내는 근거다.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.body = _fn(cls.src, "forkFabDrawing")
        cls.flat = cls.body.replace(" ", "")

    def test_the_sheet_is_reachable(self):
        self.assertIn('data-drawing="fork"', self.src, "탭이 없다")
        self.assertIn("drawingTab==='fork')drawingContent.innerHTML=forkFabDrawing()",
                      self.src, "탭이 시트를 그리지 않는다")

    def test_it_uses_the_fabrication_frame(self):
        for token, why in (("fabSheet(", "A3 도면틀을 쓰지 않는다"),
                           ("fabTitleBlock({", "ISO 7200 표제란이 없다"),
                           ("revBlock([", "개정란이 없다"),
                           ("no:'F-003'", "도면번호가 없다")):
            self.assertTrue(token in self.body, why)

    def test_all_four_portals_are_on_the_sheet(self):
        """넷 가운데 하나라도 빠지면 그 문형은 도면 없이 제작된다."""
        for tag in ("LI-101", "EX-101", "GL-101", "GU-101"):
            self.assertIn(tag, self.body, f"{tag} 가 설치 위치표에 없다")
        for coord in ("CMAST_IN", "CMAST_OUT", "CST.DL.x1+.08", "CST.GC.x1+.34"):
            self.assertIn(coord, self.flat.replace("+.08", "+.08"),
                          f"{coord} 좌표가 배치에서 나오지 않는다")
        self.assertIn("UNITS.length", self.body, "기수가 목록에서 나오지 않는다")

    def test_the_height_follows_the_deck_count(self):
        """두상보 상단이 RH-201 모노레일 하한을 만든다 — 값으로 적으면 부딪친다."""
        self.assertIn("TOP=cDeckZ(DECKS-1)+.73+.09", self.flat,
                      "두상보 상단이 최상단 데크에서 나오지 않는다")
        self.assertIn("W=2*(HALF+.075)", self.flat, "문형 폭이 반폭에서 나오지 않는다")
        self.assertIn("HALF=FORK_HALF_STD", self.flat, "반폭이 납품 배치 상수가 아니다")
        self.assertIn("RH_Z", self.body, "모노레일 하한과의 관계가 도면에 없다")

    def test_the_reach_is_drawn_at_the_length_it_is_dimensioned(self):
        """치수는 2,610 인데 그림이 1,120 이면 그 도면은 치수만 맞는 그림이다."""
        self.assertIn("REACH=CST.HC.cx-CMAST_IN", self.flat,
                      "인출 길이가 랙 중심 − 마스트에서 나오지 않는다")
        # 상세도가 REACH 를 실제 좌표로 써서 그려야 한다
        for expr in ("dx(REACH", "REACH*.58", "REACH*.62"):
            self.assertIn(expr, self.flat.replace(" ", ""),
                          f"인출 상세가 {expr} 로 실척을 그리지 않는다")
        self.assertIn("dimH(dx(0),dx(REACH)", self.flat,
                      "인출 치수가 그린 길이에 걸리지 않는다")

    def test_every_deck_level_is_marked(self):
        """포크가 닿아야 하는 자리가 전부 도면에 있어야 한다."""
        # flat 은 공백을 지우므로 'let k' 같은 토큰이 사라진다 — 원문에서 본다
        self.assertIn("for(let k=0;k<DECKS;k++)", self.body,
                      "단 레벨이 단수만큼 그려지지 않는다")
        self.assertIn("cDeckZ(k)", self.body)

    def test_it_does_not_pretend_to_know_the_section(self):
        self.assertIn("정하지 않는 것", self.body)
        self.assertIn("Not For Construction", self.body)

    def test_the_sheet_never_reads_the_layout_the_screen_happens_to_show(self):
        for bad in ("LC()", "cForkHalf()", "twinView()", "compactView()"):
            self.assertNotIn(bad, self.body, f"F-003 이 활성 배치({bad})를 읽는다")


class TestTheTandemSheetSaysWhatMoves(unittest.TestCase):
    """M-005 는 Rev.20 과 가장 크게 달라진 모듈이다.

    종전에는 칼날이 고정이고 패널이 11,200 mm 를 지나갔는데, 압축 배치는
    반대다 — 패널이 서고 칼날이 왕복한다. 모듈표가 오래도록 '고정 HKB/HKS
    탠덤 10,200 × 4,200' 을 부르고 있었으므로, 그 위에 제작도를 그렸다면
    반대로 움직이는 기계가 도면으로 굳었을 것이다. 이 시험이 보는 것은
    그 방향이다.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.body = _fn(cls.src, "tandemFabDrawing")
        cls.flat = cls.body.replace(" ", "")

    def test_the_sheet_is_reachable(self):
        self.assertIn('data-drawing="tandem"', self.src, "탭이 없다")
        self.assertIn("drawingTab==='tandem')drawingContent.innerHTML=tandemFabDrawing()",
                      self.src, "탭이 시트를 그리지 않는다")

    def test_it_uses_the_fabrication_frame(self):
        for token, why in (("fabSheet(", "A3 도면틀을 쓰지 않는다"),
                           ("fabTitleBlock({", "ISO 7200 표제란이 없다"),
                           ("revBlock([", "개정란이 없다"),
                           ("no:'F-005'", "도면번호가 없다")):
            self.assertTrue(token in self.body, why)

    def test_the_travel_is_the_rail_span_not_a_typed_number(self):
        """행정을 손으로 적으면 레일을 옮겼을 때 도면만 옛 행정으로 남는다."""
        self.assertIn("TRAV=mm(CRAIL_X1-CRAIL_X0)", self.flat,
                      "행정이 주행레일 좌표에서 나오지 않는다")
        self.assertIn("L=mm(g.w)", self.flat, "셀 길이가 스테이션 폭에서 나오지 않는다")
        self.assertIn("GAP=mm(TANDEM_GAP)", self.flat, "칼끝 간격이 상수에서 나오지 않는다")
        self.assertIn("constg=CST.DL", self.flat, "셀이 배치의 DL 스테이션이 아니다")

    def test_the_sheet_says_the_panel_stands_and_the_knife_moves(self):
        """도면이 방향을 밝히지 않으면 Rev.20 과 구별되지 않는다."""
        self.assertIn("칼날이 움직이고 패널은 선다", self.body,
                      "무엇이 움직이는지가 도면에 없다")
        self.assertIn("이동 나이프 탠덤 셀", self.body, "표제가 아직 '고정 탠덤' 이다")
        self.assertNotIn("고정 HKB/HKS 탠덤", self.body,
                         "Rev.20 의 이름이 시트에 남아 있다")
        # 개정란이 그 정정을 기록해야 한다
        self.assertIn("이동 나이프로 정정", self.body, "개정 이력에 정정이 없다")

    def test_the_thrust_path_is_written_down(self):
        """13.37 kN 이 어디로 흐르는지가 이 셀의 구조 요건 전부다."""
        self.assertIn("13.37 kN 은 칼날 → 갠트리 → 주행레일 문형 → 기초", self.body,
                      "추력 경로가 도면에 없다")
        self.assertIn("A7", self.body, "기초 도면(D-602)의 앵커군과 이어지지 않는다")
        self.assertIn("A8", self.body, "테이블 기초가 구분되지 않는다")

    def test_the_pad_area_is_checked_against_the_requirement(self):
        """패드가 모자라면 패널이 미끄러진다 — 그 여유를 도면이 적어야 한다."""
        self.assertIn("PAD_AREA.toFixed", self.body, "흡착면적이 계산되지 않는다")
        # 검산은 값 하나가 아니라 식이 적혀 있어야 확인이 된다
        self.assertIn("A ≥ 2F/(μ·Δp)", self.body, "필요면적 식이 도면에 없다")
        # 값만 보면 안 된다 — PAD_AREA/0.686 안에도 같은 숫자가 있어
        # 요구값 문장을 지워도 통과한다. 근거(μ·Δp)까지 함께 본다.
        self.assertIn("0.686 m² (μ 0.6 · Δp 65 kPa)", self.body,
                      "필요면적 상한과 그 근거가 도면에 없다")
        self.assertIn("PAD_AREA/0.686", self.body.replace(" ", ""),
                      "실제 면적이 상한의 몇 배인지 도면이 밝히지 않는다")
        self.assertIn("PAD_COLS", self.body)
        self.assertIn("PAD_ROWS", self.body)

    def test_it_does_not_pretend_to_know_the_section(self):
        self.assertIn("정하지 않는 것", self.body, "정하지 않는 것을 밝히지 않는다")
        self.assertIn("Not For Construction", self.body, "제작 착수 금지 표기가 없다")

    def test_the_sheet_never_reads_the_layout_the_screen_happens_to_show(self):
        for bad in ("LC()", "cForkHalf()", "twinView()", "compactView()"):
            self.assertNotIn(bad, self.body, f"F-005 가 활성 배치({bad})를 읽는다")


class TestTheArrangementSheetIsFabricationLevel(unittest.TestCase):
    """D-601 로는 바닥에 구멍을 못 뚫는다.

    배치 일반도는 "무엇을 떼면 무엇이 남는가" 를 적은 도면이라 앵커도 레벨도
    유틸리티 인입점도 없다. 기계 도면과 건축·설비 도면이 만나는 자리가 비어
    있으면 그 조정은 현장에서 일어나고, 현장에서 일어난 조정은 도면에 남지
    않는다. D-602 가 그 자리다.

    여기서도 보는 것은 두 가지다 — 기초도면이 갖춰야 할 것을 담았는가,
    그리고 그 좌표가 3D 가 기둥을 세운 상수에서 나오는가.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.body = _fn(cls.src, "foundationDrawing")
        cls.flat = re.sub(r"\s+", " ", cls.body)

    def test_the_sheet_is_reachable(self):
        self.assertIn('data-drawing="foundation"', self.src, "탭이 없다")
        self.assertIn("drawingTab==='foundation')drawingContent.innerHTML=foundationDrawing()",
                      self.src, "탭이 시트를 그리지 않는다")

    def test_it_uses_the_fabrication_frame(self):
        """개념 시트(titleBlock)가 아니라 ISO 7200 표제란을 쓴다."""
        for token, why in (("=fabSheet(", "A3 도면틀을 쓰지 않는다"),
                           ("+fabTitleBlock({", "ISO 7200 표제란이 없다"),
                           ("+revBlock([", "개정란이 없다"),
                           ("no:'D-602'", "도면번호가 없다")):
            # assertIn 은 실패하면 본문 전체를 덤프한다 — 시트가 커서 못 읽는다
            self.assertTrue(token in self.body, why)
        self.assertIn("scale:'1:80 / 1:40'", self.body, "축척이 없다")
        self.assertIn("tol:'ISO 2768-mK'", self.body, "일반공차가 없다")

    def test_the_title_block_sits_inside_the_drawing_frame(self):
        """종전 표제란은 아래끝이 289 로 도면틀 안쪽(287) 밖이었다 — 재단선을 밟는다."""
        self.assertIn("const TB_H=38,TB_Y=A3H-10-TB_H;", self.src,
                      "표제란이 도면틀 아래끝에 맞춰져 있지 않다")
        self.assertIn("const X=A3W-140,Y=TB_Y,W=130,H=TB_H;", self.src)
        self.assertIn("Y=TB_Y-6-rows.length*6", self.src,
                      "개정란이 표제란 위에 붙지 않는다")

    def test_every_anchor_coordinate_comes_from_the_layout(self):
        """좌표를 손으로 적으면 배치를 옮길 때 3D 만 따라오고 기초는 옛 자리에 뚫는다."""
        for name in ("CST.HC.x0", "CST.GC.x1", "CMAST_IN", "CMAST_OUT",
                     "CRAIL_X0", "CRAIL_X1", "CGY", "CTBL_CX", "CWFR_X",
                     "CE_X0", "BS_SADDLE", "CKC_SADDLE", "CKC_RACK_Y",
                     "CFENCE_YN", "FORK_HALF_STD"):
            self.assertIn(name, self.body, f"앵커 좌표가 {name} 에서 나오지 않는다")
        # 평면 좌표계 자체도 방책선에서 나온다
        self.assertIn("PX=x=>33+(x-CFENCE_X0)*S", self.flat.replace(" ", ""))
        self.assertIn("PY=y=>32+(CFENCE_Y-y)*S", self.flat.replace(" ", ""))

    def test_the_levels_are_the_derivation_not_a_list_of_numbers(self):
        """레벨은 단수의 함수다 — 단수를 바꾸면 EL 이 통째로 따라와야 한다."""
        for name in ("cDeckZ(k)", "crownTopOf(DECKS)", "ductZOf(DECKS)",
                     "RH_Z", "CRAIL_Z", "CG_Z", "SKIN_TOP+COPE_H", "PLINTH_TOP", "CZ"):
            self.assertIn(name, self.body, f"레벨 {name} 가 유도되지 않는다")
        self.assertIn("length:DECKS", self.flat.replace(" ", ""),
                      "데크 레벨이 단수만큼 생기지 않는다")

    def test_the_sheet_never_reads_the_layout_the_screen_happens_to_show(self):
        """D-602 는 납품 배치(DG-HK60C)의 기초도면이다.

        화면은 압축·트윈·Rev.20 을 오간다. 시트가 LC()·cCrownTop()·cDuctZ()·
        cForkHalf() 같은 '활성 배치' 형태를 쓰면, 트윈을 켜 둔 채 도면을 열었을
        때 7단 기준 EL 이 D-602 라는 이름으로 인쇄된다. 그 도면으로 바닥을
        치면 앵커가 맞지 않는다 — 도면은 화면을 따라가면 안 된다.
        """
        for bad, why in (("LC()", "활성 배치 설정을 읽는다"),
                         ("cCrownTop()", "활성 배치의 갓돌을 읽는다"),
                         ("cDuctZ()", "활성 배치의 덕트 높이를 읽는다"),
                         ("cForkHalf()", "활성 배치의 문형 반폭을 읽는다"),
                         ("twinView()", "트윈 여부를 본다"),
                         ("compactView()", "배치 상태를 본다")):
            self.assertNotIn(bad, self.body, f"D-602 가 {why}")

    def test_the_shared_foundation_is_not_counted_twice(self):
        """RH-201 내측 기둥과 KG-101 레일 문형은 같은 자리다.

        3D 가 두 함수에서 각각 기둥을 세우므로 그대로 세면 앵커가 하나 더
        잡히고, 기초가 있지도 않은 자리에 하나 더 들어간다."""
        self.assertIn("A7 과 기초 공용", self.body,
                      "공용 기초가 도면에 표시되지 않는다")
        self.assertIn("pts:grid([CRAIL_X0],[-(CFENCE_YN+.10)])", self.body,
                      "모노레일 앵커가 아직 내측 기둥을 중복해 센다")

    def test_it_does_not_pretend_to_know_the_bolt_or_the_dead_load(self):
        """모르는 값을 적는 순간 도면이 근거를 잃는다.

        앵커볼트 규격·매입깊이·연단거리와 구조 자중은 부재 단면을 알아야
        나오는데 이 콘솔은 그것을 모른다. 적재하중만 유도해 적고 나머지는
        구조계산으로 넘긴다고 도면에 밝혀야 한다."""
        self.assertIn("앵커볼트 규격·매입깊이·연단거리는 구조계산 후 확정한다",
                      self.body, "앵커볼트를 정하지 않는다는 것이 도면에 없다")
        self.assertIn("구조 자중은 포함하지 않는다", self.body,
                      "자중을 뺐다는 것이 도면에 없다")
        self.assertIn("NOT FOR CONSTRUCTION", self.body,
                      "타설 금지 표기가 없다")

    def test_the_live_loads_are_derived_from_the_material_model(self):
        """적재하중은 유도되는 것만 적는다 — 그것이 '유도치' 라는 말의 뜻이다."""
        for name in ("ROLL_MASS", "MASS_AREAL", "MASS_GLASS", "CASS_MASS"):
            self.assertIn(name, self.body, f"적재하중이 {name} 에서 나오지 않는다")
        self.assertNotRegex(self.body, r"live:\s*\d+\s*[,}]",
                            "적재하중에 손으로 적은 숫자가 있다")

    def test_the_utility_entries_carry_the_electrical_derivation(self):
        """인입점이 부하표와 갈라지면 현장에서 케이블이 안 맞는다."""
        for name in ("LINE_V", "MAIN_AF", "MAIN_AT", "FLA", "TR_KVA"):
            self.assertIn(name, self.body, f"인입점이 {name} 를 쓰지 않는다")
        self.assertIn("ductZOf(DECKS)", self.body,
                      "덕트 플랜지 레벨이 갓돌에서 나오지 않는다")


class TestTheSpecificationAgreesAboutWhatWasHandedOver(unittest.TestCase):
    """1.2 가 '제작도면이 없다' 고 적어 두면 F-002 가 그 문장을 거짓으로 만든다."""

    @classmethod
    def setUpClass(cls):
        cls.rfq = RFQ.read_text(encoding="utf-8")

    def test_the_handover_clause_matches_what_the_console_actually_carries(self):
        self.assertIn("Not For Construction", self.rfq,
                      "사양서가 인계 도면의 성격(참고도)을 규정하지 않았다")
        self.assertNotIn("선행자료에는 제작도면이 없다", self.rfq,
                         "콘솔이 제작수준 시트를 담게 되었는데 1.2 가 옛 문장으로 남아 있다")
        self.assertIn("검증·확정은 본 용역의 범위에 속한다", self.rfq,
                      "도면 확정이 용역 범위임을 여전히 밝혀야 한다")

    def test_the_clause_names_every_fabrication_level_sheet(self):
        """참고도 목록이 시트보다 짧으면, 빠진 시트는 성격이 규정되지 않은 채 나간다."""
        console = CONSOLE.read_text(encoding="utf-8")
        for no in ("F-002", "D-501", "D-602"):
            self.assertIn(f"no:'{no}'", console.replace(" ", "") ,
                          f"콘솔에 {no} 시트가 없다") if no != "D-501" else None
            self.assertIn(no, self.rfq, f"1.2 가 {no} 를 참고도로 부르지 않는다")

    def test_the_clause_says_what_the_foundation_sheet_does_not_fix(self):
        """앵커 위치만 정한 도면을 받아 바로 타설하면 그 기초는 다시 깬다."""
        self.assertIn("앵커볼트 규격·매입깊이·연단거리·기초 두께·배근은 정하지", self.rfq,
                      "1.2 가 D-602 의 한계를 밝히지 않는다")


if __name__ == "__main__":
    unittest.main()
