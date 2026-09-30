"""옵션(DG-HK120C)을 표준(DG-HK60C)과 같은 코드로 푸는 장치를 지킨다.

옵션은 뿌리 상수 자리에 콘솔 배치 설정(HK120C)의 값을 핀으로 박고 설계
모듈을 새로 불러 푼다 (tools/console_consts.layout · tools/variant.load).
이 장치가 틀리면 두 가지가 동시에 틀린다 — 옵션 견적이 엉뚱한 기계를
세고, 표준 결과가 옵션 핀에 오염된다. 둘 다 조용히 틀리므로 여기서 묻는다.
"""

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


if __name__ == "__main__":
    unittest.main()
