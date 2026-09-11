"""부품별 상세도면과 3D 단독 보기 검증.

부품도는 ``tools/mp50_parts.py`` 가 생성하므로 숫자가 모듈과 어긋날 수 없다.
대신 **빠진 것이 없는지**를 본다 — 제작품 가운데 도면이 없는 것, 도면은 있는데
목록에 없는 것, 규격·구매품인데 부품도가 붙은 것. 3D 콘솔은 손으로 쓴 파일이라
부품도를 가리키는 연결표가 실제 시트와 맞는지 따로 확인한다.
"""

import html as _html
import pathlib
import re
import subprocess
import sys
import unittest

from . import _path  # noqa: F401

from mp50_separator import ASSEMBLIES, GEOMETRY as G
from mp50_separator.components import FABRICATED

from .test_mp50_drawings import standalone_checks

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:        # 생성기를 직접 읽어 규칙을 맞춘다
    sys.path.insert(0, str(ROOT / "tools"))
import mp50_parts  # noqa: E402
PARTS_DOC = ROOT / "docs" / "drawings" / "mp50-part-drawings.html"
CONSOLE = ROOT / "docs" / "drawings" / "mp50-3d.html"

#: 프레임 안쪽 (용지 mm). 글자가 이 밖으로 나가면 인쇄에서 잘린다.
FRAME_BOX = (11.0, 7.0, 414.0, 291.0)


def has(case, haystack, needle, label):
    """실패 시 700 KB 를 덤프하지 않도록 직접 메시지를 만든다."""
    case.assertTrue(
        needle in haystack or _html.escape(needle, quote=True) in haystack,
        f"{label} 이(가) 부품도에 없음 — 찾은 문자열: {needle!r}. "
        f"부품을 고쳤다면 python tools/mp50_parts.py 로 다시 생성할 것.",
    )


def part_numbers_on_sheets(html):
    """문서에 실린 부품도 시트의 부품번호 — MP50-P-A01 → A-01."""
    out = []
    for raw in sorted(set(re.findall(r'id="MP50-P-([A-Z]\d\d)"', html))):
        out.append(raw[0] + "-" + raw[1:])
    return out


class TestPartDrawingDocument(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PARTS_DOC.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        standalone_checks(self, self.html, "MP-50 부품별 상세도면")

    def test_sheet_count_and_numbering(self):
        sheets = re.findall(r'<figure class="sheet" id="(MP50-P-[0-9A-Z]+)"', self.html)
        self.assertEqual(len(sheets), 29, "부품도 매수가 바뀌었다")
        self.assertEqual(sheets[0], "MP50-P-000", "표지가 맨 앞이 아니다")
        self.assertEqual(sheets[-1], "MP50-P-999", "규격품 명세가 맨 뒤가 아니다")
        self.assertEqual(len(sheets), len(set(sheets)), "도면번호가 겹친다")
        for i in range(1, len(sheets) + 1):          # 표제란의 시트 번호
            has(self, self.html, f"{i}/{len(sheets)}", f"시트 {i}/{len(sheets)}")

    def test_every_fabricated_part_has_a_drawing(self):
        drawn = set(part_numbers_on_sheets(self.html))
        missing = [p.no for p in FABRICATED if p.no not in drawn and p.no not in mp50_parts.FOLDED]
        self.assertEqual(missing, [], f"부품도가 없는 제작품: {missing}")

    def test_folded_parts_are_named_on_their_host_sheet(self):
        """한 장에 묶은 소물도 번호와 규격이 그 장에 적혀 있어야 한다."""
        for host, group in mp50_parts.SHARED.items():
            for no in group:
                has(self, self.html, no, f"합본 부품 {no}")
                has(self, self.html, mp50_parts.PART[no].name, f"{no} 품명 (대표 {host})")

    def test_bought_parts_are_listed_but_not_drawn(self):
        """규격·구매품에는 부품도를 붙이지 않는다 — 명세 한 장에 모은다."""
        drawn = set(part_numbers_on_sheets(self.html))
        for a in ASSEMBLIES:
            for p in a.parts:
                if p.fabricated:
                    continue
                self.assertNotIn(p.no, drawn, f"{p.no} 은 {p.made} 인데 부품도가 붙었다")
                has(self, self.html, p.no, f"{p.made} {p.no}")
                # 규격품은 주문 규격(stock)으로, 구매품은 사양(spec)으로 산다.
                want = p.spec if p.made == "구매" else p.stock
                has(self, self.html, want, f"{p.no} {'사양' if p.made == '구매' else '주문 규격'}")

    def test_stock_sizes_are_given_for_fabricated_parts(self):
        """소재 규격이 없으면 가공자가 무엇을 잘라야 할지 알 수 없다."""
        for p in FABRICATED:
            self.assertTrue(p.stock, f"{p.no} 에 소재 규격이 없다")
            has(self, self.html, p.stock, f"{p.no} 소재")

    def test_general_tolerance_and_finish_are_stated_once(self):
        has(self, self.html, "ISO 2768-mK", "일반공차")
        has(self, self.html, "산세 · 부동태화", "후처리")

    def test_key_developed_lengths(self):
        """전개 치수는 판금 업체가 그대로 쓰는 숫자다."""
        for text in (f"{G.shell_development_length_mm:.2f}",
                     f"{G.cone_slant_length_mm:.2f}"):
            has(self, self.html, text, f"전개 치수 {text}")

    def test_every_sheet_is_labelled_for_screen_readers(self):
        n = len(re.findall(r'<figure class="sheet"', self.html))
        self.assertEqual(len(re.findall(r'role="img"', self.html)), n)
        self.assertEqual(len(re.findall(r"aria-label=", self.html)), n)
        self.assertEqual(len(re.findall(r"<figcaption>", self.html)), n)

    def test_container_tags_balance(self):
        for tag in ("svg", "figure", "section", "table", "div", "style", "ul", "tbody"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_no_text_escapes_the_frame(self):
        """프레임 밖의 글자는 인쇄에서 잘린다 — 한 장씩 좌표를 본다."""
        x0, y0, x1, y1 = FRAME_BOX
        bad = []
        for x, y in re.findall(r'<text x="(-?[\d.]+)" y="(-?[\d.]+)"', self.html):
            fx, fy = float(x), float(y)
            if not (x0 <= fx <= x1 and y0 <= fy <= y1):
                bad.append((fx, fy))
        self.assertEqual(bad[:8], [], f"프레임을 벗어난 글자 {len(bad)} 개")

    def test_no_text_crosses_into_the_right_column(self):
        """왼쪽 도형부의 글이 오른쪽 기둥(x=258)을 넘으면 정보표 위에 겹쳐 찍힌다.

        좌표만 보는 위 검사로는 잡히지 않는다 — 시작점은 프레임 안인데 글자가
        길어서 넘어가는 경우가 실제로 두 장에서 나왔다. 폭을 추정해서 본다.
        """
        from _mp50_draft import text_width

        col_x = 258.0
        bad = []
        for no, svg in re.findall(
                r'<figure class="sheet" id="([^"]+)">(.*?)</figure>', self.html, re.S):
            if no.endswith("-000") or no.endswith("-999"):
                continue                       # 목록·명세 장에는 오른쪽 기둥이 없다
            for x, y, size, anchor, body in re.findall(
                    r'<text x="(-?[\d.]+)" y="(-?[\d.]+)" font-size="([\d.]+)" '
                    r'text-anchor="(\w+)"[^>]*>(.*?)</text>', svg, re.S):
                x, y, size = float(x), float(y), float(size)
                if not 24.0 <= y <= 258.0:     # 머리띠와 표제란은 전폭을 쓴다
                    continue
                txt = _html.unescape(re.sub(r"<[^>]+>", "", body))
                w = text_width(txt, size)
                left = x if anchor == "start" else (x - w / 2 if anchor == "middle" else x - w)
                if left < col_x and left + w > col_x - 1.0:
                    bad.append((no, txt[:30], round(left, 1), round(left + w, 1)))
        self.assertEqual(bad[:6], [], f"오른쪽 기둥을 침범한 글자 {len(bad)} 개")

    def test_toc_lists_every_sheet(self):
        toc = re.findall(r'<li><a href="#(MP50-P-[0-9A-Z]+)">', self.html)
        sheets = re.findall(r'<figure class="sheet" id="(MP50-P-[0-9A-Z]+)"', self.html)
        self.assertEqual(toc, sheets, "목차와 시트 순서가 어긋난다")


class TestPartDrawingsAreGenerated(unittest.TestCase):
    """부품도는 손으로 고치는 파일이 아니다."""

    def test_regenerating_is_a_no_op(self):
        before = PARTS_DOC.read_text(encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "tools" / "mp50_parts.py")],
                       check=True, capture_output=True)
        self.assertEqual(PARTS_DOC.read_text(encoding="utf-8"), before,
                         "부품도를 손으로 고쳤거나 생성기와 어긋났다 — "
                         "python tools/mp50_parts.py 로 다시 만들 것")


class TestConsoleSoloMode(unittest.TestCase):
    """3D 콘솔의 부품 단독 보기 — 손으로 쓴 파일이라 연결이 끊기기 쉽다."""

    @classmethod
    def setUpClass(cls):
        cls.js = CONSOLE.read_text(encoding="utf-8")
        cls.parts_html = PARTS_DOC.read_text(encoding="utf-8")

    def console_map(self, name):
        """콘솔에 박힌 ``const <name> = {...}`` 를 읽어 dict 로 돌려준다."""
        m = re.search(rf"const {name} = \{{(.*?)\n\}};", self.js, re.S)
        self.assertIsNotNone(m, f"콘솔에 {name} 표가 없다")
        return dict(re.findall(r'"([^"]+)":"([^"]+)"', m.group(1)))

    def test_solo_controls_exist(self):
        for token in ('id="btnSolo"', 'id="btnPrev"', 'id="btnNext"', 'id="soloInfo"',
                      "function fitCam", "function setSolo", "function stepPart",
                      "function envelope", "function bbox"):
            self.assertIn(token, self.js, f"단독 보기 요소 {token} 이 없다")

    def test_every_drawing_link_points_at_a_real_sheet(self):
        """연결표가 가리키는 시트가 부품도 문서에 실제로 있어야 한다."""
        dwg = self.console_map("DWG")
        self.assertTrue(dwg, "DWG 표가 비었다")
        for no, sheet in dwg.items():
            self.assertIn(f'id="MP50-P-{sheet}"', self.parts_html,
                          f"{no} → MP50-P-{sheet} 시트가 부품도에 없다")

    def test_drawing_map_covers_the_consoles_fabricated_parts(self):
        """콘솔에 있는 제작품은 모두 부품도로 갈 길이 있어야 한다."""
        dwg = self.console_map("DWG")
        bought = set(re.search(r"const BOUGHT = \[(.*?)\];", self.js, re.S).group(1)
                     .replace('"', "").replace("\n", "").split(","))
        bought = {b.strip() for b in bought if b.strip()}
        numbers = set(re.findall(r'no:"([A-Z]-\d\d)"', self.js)) - {"LIQ"}
        for no in sorted(numbers):
            self.assertTrue(no in dwg or no in bought,
                            f"{no} 이 DWG 에도 BOUGHT 에도 없다 — 단독 보기에서 갈 곳이 없다")

    def test_bought_list_matches_the_model(self):
        """구매·규격품 목록이 components 의 구분과 같아야 한다."""
        bought = set(re.search(r"const BOUGHT = \[(.*?)\];", self.js, re.S).group(1)
                     .replace('"', "").replace("\n", "").split(","))
        bought = {b.strip() for b in bought if b.strip()}
        by_no = {p.no: p for a in ASSEMBLIES for p in a.parts}
        for no in sorted(bought):
            self.assertIn(no, by_no, f"콘솔의 {no} 이 부품표에 없다")
            self.assertFalse(by_no[no].fabricated,
                             f"{no} 은 {by_no[no].made} 인데 구매품으로 묶였다")

    def test_assembly_sheet_links_resolve(self):
        """아세이도 연결 — A 만 3 장으로 나뉘어 A1 을 가리킨다."""
        fab = (ROOT / "docs" / "drawings" / "mp50-fabrication-drawings.html").read_text(
            encoding="utf-8")
        for a in ASSEMBLIES:
            target = "MP50-A1" if a.code == "A" else f"MP50-{a.code}"
            self.assertIn(f'id="{target}"', fab, f"아세이 {a.code} → {target} 이 없다")

    def test_deep_link_documents_the_solo_parameter(self):
        self.assertIn("solo=", self.js, "해시 딥링크에 solo 가 없다")
        self.assertIn("q.solo", self.js, "solo 해시를 읽지 않는다")

    def test_solo_turns_off_things_that_assume_the_whole_vessel(self):
        """입자 시뮬레이션은 장치 전체를 전제로 한다 — 단독 보기에서 꺼져야 한다."""
        self.assertIn("if(state.run && !solo){", self.js, "단독 보기에서 입자가 그려진다")
        self.assertIn("if(state.run) setRun(false);", self.js,
                      "단독 보기로 들어갈 때 운전 재생이 꺼지지 않는다")


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
