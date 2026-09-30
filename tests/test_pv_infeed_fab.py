"""투입 구간 제작 도면집 — 정본(fabrication.py)의 정합성과 생성 출력.

제작 패키지는 손으로 쓰지 않는다. 여기서는 (1) 커밋된 도면집이 생성기 출력과
같은지, (2) 체결 호칭이 토크·구멍 표에 다 있는지, (3) 앵커 수가 mounting 모델과,
치수가 kinematics·layout 과, 서보 축이 servos 와 어긋나지 않는지, (4) 모든 제작품이
도면번호를 갖고 중량이 양수인지, (5) 아티팩트 변환기가 받아들이는지를 본다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import fabrication as fab

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAB = ROOT / "docs/drawings/pv-infeed-fab.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFabricationData(unittest.TestCase):

    def test_every_joint_has_a_torque_and_a_hole(self):
        self.assertEqual(fab.joint_checks(), [])

    def test_anchors_match_the_mounting_model(self):
        for key, (model, pkg) in fab.anchors_match_mounting().items():
            with self.subTest(key=key):
                self.assertEqual(model, pkg)

    def test_geometry_matches_kinematics_and_layout(self):
        for key, ok in fab.geometry_checks().items():
            with self.subTest(key=key):
                self.assertTrue(ok)

    def test_every_infeed_servo_axis_is_bought(self):
        for tag, ok in fab.servo_axes_covered().items():
            with self.subTest(axis=tag):
                self.assertTrue(ok)

    def test_parts_are_unique_and_weigh_something(self):
        tags = [p.tag for a in fab.ASSEMBLIES for p in a.parts]
        self.assertEqual(len(tags), len(set(tags)), "부품번호가 겹친다")
        for a in fab.ASSEMBLIES:
            for p in a.parts:
                with self.subTest(part=p.tag):
                    self.assertGreater(p.weight_kg(), 0)
                    self.assertIn(p.material, fab.MATERIALS)
                    self.assertGreater(p.qty, 0)

    def test_torque_table_is_monotonic(self):
        sizes = list(fab.TORQUE_NM)
        for a, b in zip(sizes, sizes[1:]):
            self.assertLess(fab.TORQUE_NM[a][0], fab.TORQUE_NM[b][0])
            self.assertLess(fab.TORQUE_NM[a][0], fab.TORQUE_NM[a][1])
            self.assertLess(fab.HOLE_MM[a], fab.HOLE_MM[b])

    def test_the_ring_weighs_what_the_crane_model_assumed(self):
        """crane.py 는 엔드링 2 × ⌀180 t10 파이프를 237 kg 으로 잡았다."""
        ring = next(p for a in fab.ASSEMBLIES for p in a.parts if p.tag == "BFC-RNG-01")
        self.assertAlmostEqual(ring.weight_kg(), 237, delta=5)


class TestFabricationDrawings(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_infeed_fab")
        cls.html = FAB.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-infeed-fab.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_infeed_fab.py 를 돌리고 커밋한다")

    def test_every_part_has_a_sheet_and_every_assembly_an_exploded_view(self):
        for a in fab.ASSEMBLIES:
            self.assertIn(f'id="{a.sheet}"', self.html)
            for i, p in enumerate(a.parts, start=1):
                self.assertIn(f'id="{a.sheet}-P{i:02d}"', self.html)
                self.assertIn(p.tag, self.html)
        self.assertEqual(self.html.count('<article class="sheet"'), sum(len(a.parts) for a in fab.ASSEMBLIES))
        self.assertEqual(self.html.count('aria-label="') >= len(fab.ASSEMBLIES), True)

    def test_positional_exploded_views_cover_the_load_bearing_assemblies(self):
        inst = self.builder.explode_instances()
        for tag in ("AFU-BW-101", "AFU-BFC-101", "AFU-RB-101 · EOAT-101", "AFU-PT-101 · AL-101", "JB-201"):
            self.assertIn(tag, inst)
            parts = {p.tag for a in fab.ASSEMBLIES if a.tag == tag for p in a.parts}
            for row in inst[tag]:
                self.assertIn(row[0], parts, f"{tag} 분해도에 부품표에 없는 {row[0]}")

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("infeed-fab", conv.TARGETS)
        body = conv.convert(self.html, FAB)
        self.assertIn("<title>DG 투입부 제작 도면집</title>", body)

    def test_the_readme_lists_the_package(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-infeed-fab.html", readme)
        self.assertIn("fabrication.py", readme)
