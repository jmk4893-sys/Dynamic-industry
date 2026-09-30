"""조립 순서도 — 부품이 단계에 빠짐없이 한 번씩 배정됐는가, 문서가 그것을 싣는가.

단계별 조립도가 틀리는 방식은 둘이다. **부품이 어느 단계에도 안 들어가면**
조립이 끝나도 그 부품이 남고, **두 단계에 들어가면** 도면이 같은 것을 두 번
놓으라고 시킨다. 그래서 정본의 배정을 먼저 보고, 그다음에 문서를 본다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import fabrication as fab

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/drawings/pv-assembly-steps.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestStepParts(unittest.TestCase):
    """정본 — 배정이 부품표와 맞는가."""

    def test_every_part_is_placed_exactly_once(self):
        problems = {k: v for k, v in fab.steps_cover_every_part().items() if v}
        self.assertEqual(problems, {}, f"단계 배정 문제: {problems}")

    def test_every_assembly_has_a_row_per_step(self):
        for a in fab.ASSEMBLIES:
            self.assertIn(a.sheet, fab.STEP_PARTS, f"{a.sheet} 의 단계 배정이 없다")
            self.assertEqual(len(fab.STEP_PARTS[a.sheet]), len(a.steps), a.sheet)

    def test_step_parts_rejects_a_bad_step_number(self):
        with self.assertRaises(KeyError):
            fab.step_parts("PV-FAB-A01", 0)
        with self.assertRaises(KeyError):
            fab.step_parts("PV-FAB-A01", 99)

    def test_the_first_step_of_an_anchored_assembly_places_nothing(self):
        """기초·천공 단계는 부품을 놓지 않는다 — 앵커가 굳기 전에는 아무것도 안 선다."""
        for sheet in ("PV-FAB-A01", "PV-FAB-A03"):
            self.assertEqual(fab.step_parts(sheet, 1), (), f"{sheet} 1단계는 기초 작업이다")

    def test_the_total_step_count(self):
        self.assertEqual(sum(len(v) for v in fab.STEP_PARTS.values()),
                         sum(len(a.steps) for a in fab.ASSEMBLIES))


class TestAssemblyStepDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_assembly_steps")
        cls.html = DOC.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-assembly-steps.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_assembly_steps.py 를 돌리고 커밋한다")

    def test_every_step_of_every_assembly_appears(self):
        for a in fab.ASSEMBLIES:
            self.assertIn(f'<section id="{a.sheet}">', self.html)
            for step in a.steps:
                self.assertIn(f"단계 {step.no} — {step.title}", self.html,
                              f"{a.sheet} 단계 {step.no} 가 없다")

    def test_assemblies_with_coordinates_get_a_drawing_per_step(self):
        for a in fab.ASSEMBLIES:
            if not self.builder.instances_of(a):
                continue
            for step in a.steps:
                self.assertIn(f'aria-label="{a.sheet} 단계 {step.no} 조립도"', self.html,
                              f"{a.sheet} 단계 {step.no} 의 등각도가 없다")

    def test_a_later_step_draws_at_least_as_much_as_an_earlier_one(self):
        """조립은 쌓이기만 한다 — 뒤 단계가 앞 단계보다 그려진 형상이 적으면 안 된다."""
        a = fab.assembly("PV-FAB-A03")
        inst = self.builder.instances_of(a)
        box = self.builder._bounds(inst)
        counts = []
        for step in a.steps:
            svg, _drawn = self.builder.step_view(a, step.no, inst, box)
            counts.append(svg.count("<polygon"))
        for i in range(1, len(counts)):
            self.assertGreaterEqual(counts[i], counts[i - 1],
                                    f"단계 {i + 1} 이 단계 {i} 보다 적게 그려졌다")

    def test_the_last_step_draws_every_part_that_has_coordinates(self):
        for a in fab.ASSEMBLIES:
            inst = self.builder.instances_of(a)
            if not inst:
                continue
            box = self.builder._bounds(inst)
            svg, _ = self.builder.step_view(a, len(a.steps), inst, box)
            drawn_boxes = svg.count("<polygon") // 3          # 상자 하나에 면 3개
            self.assertEqual(drawn_boxes, len(inst),
                             f"{a.sheet} 마지막 단계에 모든 인스턴스가 없다")

    def test_undrawn_parts_are_called_out(self):
        self.assertIn("등각도에 형상이 없는 부품", self.html)

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("assembly-steps", conv.TARGETS)
        body = conv.convert(self.html, DOC)
        self.assertIn("<title>", body)
        self.assertNotIn("<!doctype", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-assembly-steps.html", readme)


if __name__ == "__main__":
    unittest.main()
