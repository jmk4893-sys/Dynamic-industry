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


if __name__ == "__main__":
    unittest.main()
