"""체결 부품 — 형상값이 규격과 맞고, 길이가 실제로 성립하는가.

이 문서가 막는 실패는 하나다: **볼트가 짧아 조여지지 않는 것.** 호칭만 적어
두면 아무도 모르고, 현장에서 앵커에 너트가 안 걸릴 때 안다. 그래서 여기서는
(1) 규격 치수의 내부 정합, (2) 구멍·와셔·나사부가 서로 맞는지, (3) 설계에
쓰인 체결 전부의 길이 검산, (4) 커밋된 문서가 생성기 출력과 같은지를 본다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import fabrication, fasteners as F

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/drawings/pv-fastener-book.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFastenerGeometry(unittest.TestCase):
    """규격 치수 자체가 앞뒤가 맞는가."""

    def test_every_size_has_all_four_parts(self):
        for size in F.SIZES:
            self.assertIn(size, F.HEX_BOLT)
            self.assertIn(size, F.HEX_NUT)
            self.assertIn(size, F.PLAIN_WASHER)
            self.assertIn(size, F.SPRING_WASHER)

    def test_the_size_set_matches_the_fabrication_torque_table(self):
        self.assertEqual(set(F.SIZES), set(fabrication.TORQUE_NM))

    def test_dimensions_grow_with_the_nominal_diameter(self):
        """호칭이 커지면 대변·머리·너트·와셔가 다 커진다 — 오타가 여기서 걸린다."""
        prev = None
        for size in F.SIZES:
            b, nut = F.HEX_BOLT[size], F.HEX_NUT[size]
            pw = F.PLAIN_WASHER[size]
            now = (b.d, b.pitch, b.s, b.k, nut.m, pw.d2, pw.h)
            if prev is not None:
                self.assertGreater(now[0], prev[0], size)
                for i in (1, 2, 3, 4, 5):
                    self.assertGreaterEqual(now[i], prev[i], f"{size} 의 {i}번째 값이 작아졌다")
            prev = now

    def test_washer_bores_clear_the_bolt(self):
        for size in F.SIZES:
            d = F.HEX_BOLT[size].d
            self.assertGreater(F.PLAIN_WASHER[size].d1, d, f"{size} 평와셔가 볼트에 안 들어간다")
            self.assertGreater(F.SPRING_WASHER[size].d1, d, f"{size} 스프링와셔가 볼트에 안 들어간다")

    def test_nut_and_bolt_head_share_the_across_flats(self):
        """이 계열은 볼트 머리와 너트의 대변이 같다 — 공구가 하나로 된다."""
        for size in F.SIZES:
            self.assertEqual(F.HEX_BOLT[size].s, F.HEX_NUT[size].s, size)

    def test_the_thread_length_rule(self):
        for size in F.SIZES:
            b = F.HEX_BOLT[size]
            self.assertEqual(b.b, 2 * b.d + 6, f"{size} 반나사 나사부는 2d + 6")


class TestFastenerFit(unittest.TestCase):
    """설계가 쓰는 체결이 실제로 맞는가."""

    def test_the_design_only_uses_sizes_we_have(self):
        self.assertTrue(all(F.geometry_covers_the_design().values()))

    def test_holes_clear_the_bolts(self):
        bad = [k for k, v in F.holes_clear_the_bolts().items() if not v]
        self.assertEqual(bad, [], f"관통 구멍이 볼트보다 작다: {bad}")

    def test_washers_cover_the_holes(self):
        bad = [k for k, v in F.washers_cover_the_holes().items() if not v]
        self.assertEqual(bad, [], f"평와셔가 구멍을 못 덮는다: {bad}")

    def test_partially_threaded_bolts_reach_the_nut(self):
        bad = [k for k, v in F.threads_reach_the_nuts().items() if not v]
        self.assertEqual(bad, [], f"반나사로는 너트에 안 닿는다 — 온나사 필요: {bad}")

    def test_no_bolt_is_eaten_by_its_own_hardware(self):
        """부속(와셔·너트·나사산)이 볼트 길이를 다 먹으면 그 체결은 성립하지 않는다."""
        short = [f"{u.sheet} {u.joint} {u.size}×{u.length:g}"
                 for u, _, v in F.lengths_are_long_enough() if v.startswith("불가")]
        self.assertEqual(short, [], f"부속이 볼트를 다 먹는다: {short}")

    def test_every_anchor_rod_reaches_its_nut(self):
        """앵커는 매입 + 베이스 + 그라우트를 지나 너트까지 닿아야 한다."""
        short = [f"{tag} {size}×{length:g} (필요 {need:g})"
                 for tag, size, length, need, _, ok in F.anchor_lengths() if not ok]
        self.assertEqual(short, [], f"앵커 로드가 짧다: {short}")

    def test_anchor_rods_are_standard_lengths(self):
        for tag, size, length, need, _, _ in F.anchor_lengths():
            self.assertIn(int(length), F.ANCHOR_ROD_LENGTHS[size],
                          f"{tag} 의 {size}×{length:g} 는 표준 계열에 없다")
            self.assertEqual(int(length), F.anchor_rod_for(size, need),
                             f"{tag} 는 필요 {need:g} 에 맞는 가장 짧은 표준 길이가 아니다")

    def test_the_demand_adds_up(self):
        """너트 수 = 관통 + 앵커 체결 수. 탭 체결은 너트가 없다."""
        want = sum(u.qty for u in F.uses() if u.kind in ("관통", "앵커"))
        self.assertEqual(F.summary()["nuts"], want)
        self.assertEqual(F.summary()["bolts"], sum(u.qty for u in F.uses()))


class TestFastenerDocument(unittest.TestCase):
    """문서 — 커밋본이 생성 결과와 같고, 값을 싣고 있는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_fasteners")
        cls.html = DOC.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-fastener-book.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_fasteners.py 를 돌리고 커밋한다")

    def test_every_used_size_gets_a_shape_drawing(self):
        for size in F.sizes_used():
            self.assertIn(f'aria-label="{size} 체결 부품 형상도"', self.html)

    def test_it_carries_the_standards(self):
        for std in ("KS B 1002", "KS B 1012", "KS B 1326", "KS B 1324"):
            self.assertIn(std, self.html)

    def test_the_sections_are_drawn(self):
        for label in ("관통 체결 상세 단면", "탭 체결 상세 단면", "케미컬 앵커 상세 단면"):
            self.assertIn(f'aria-label="{label}"', self.html)

    def test_the_torques_come_from_the_fabrication_model(self):
        for size in F.sizes_used():
            lo, hi = fabrication.TORQUE_NM[size]
            self.assertIn(f"{lo:g} / {hi:g}", self.html, f"{size} 토크가 제작 모델과 다르다")

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("fasteners", conv.TARGETS)
        body = conv.convert(self.html, DOC)
        self.assertIn("<title>", body)
        self.assertNotIn("<!doctype", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-fastener-book.html", readme)
        self.assertIn("fasteners.py", readme)


if __name__ == "__main__":
    unittest.main()
