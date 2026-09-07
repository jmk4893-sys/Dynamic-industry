"""투입 구간 상세도 — 생성기 출력과 커밋된 파일, 그리고 모델과의 일치.

상세도는 손으로 쓰지 않는다. `tools/build_infeed_detail.py` 가 모델과 통합
설계도에서 값을 읽어 찍어 내고, 여기서는 (1) 커밋된 파일이 그 출력과 같은지,
(2) 범위 안 품번·레벨·시각이 모델과 어긋나지 않았는지, (3) 아티팩트 변환기가
받아들이는 문서인지를 본다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, kinematics, layout, safety, servos

ROOT = pathlib.Path(__file__).resolve().parents[1]
DETAIL = ROOT / "docs/drawings/pv-infeed-detail.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestInfeedDetail(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_infeed_detail")
        cls.html = DETAIL.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-infeed-detail.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_infeed_detail.py 를 돌리고 커밋한다")

    def test_the_scope_is_the_first_two_zones(self):
        keys = [z.key for z in layout.build_zones()]
        self.assertEqual(tuple(keys[:2]), self.builder.SCOPE_ZONES)
        afu, robot = layout.STATIONS["afu"], layout.STATIONS["robot"]
        self.assertIn(f"afu {afu.length_mm:,} + robot {robot.length_mm:,} = {afu.length_mm + robot.length_mm:,} mm", self.html)

    def test_every_scope_part_number_is_in_the_plant_catalog_and_the_sheet(self):
        plant = self.builder.plant_text()
        for tag in self.builder.SCOPE_PART_NUMBERS:
            with self.subTest(tag=tag):
                self.assertIn(f'["{tag}"', plant, "통합 설계도 부품표에 없는 품번이다")
                self.assertIn(f"<code>{tag}</code>", self.html)

    def test_levels_come_from_the_model(self):
        for level in (kinematics.PICK_FACE_MM, kinematics.HANDOVER_MM, kinematics.dwell_mm(),
                      kinematics.FLIP_AXIS_MM, round(kinematics.ring_bottom_mm()), layout.LINE_TRANSFER_MM):
            with self.subTest(level=level):
                self.assertIn(f"{level:,}", self.html)
        self.assertIn(f"{kinematics.ring_over_forklift_mm():,.0f}", self.html)

    def test_the_clock_is_continuous_from_pallet_to_jbr(self):
        """준비 → PATH → 로봇 → JBR 진입이 빈틈·겹침 없이 이어져야 한다."""
        b = self.builder
        spans = ([(t0, t1) for t0, t1, _ in b.PREP_CLOCK]
                 + [(t0, t1) for t0, t1, *_ in kinematics.PATH]
                 + [(t0, t1) for t0, t1, _ in b.ROBOT_CLOCK])
        for a, c in zip(spans, spans[1:]):
            self.assertEqual(a[1], c[0], f"{a} 와 {c} 사이가 안 이어진다")
        self.assertEqual(spans[0][0], 0.0)
        self.assertEqual(spans[-1][1], campaign.INFEED_S)

    def test_the_reach_chain_closes_on_the_zone_table(self):
        self.assertEqual(layout.afu_length_from_reach_mm(), layout.STATIONS["afu"].length_mm)
        self.assertTrue(layout.robot_can_reach())
        self.assertIn(f"{layout.ROBOT_REACH_MM:,}", self.html)

    def test_scope_drives_and_hazards_are_listed(self):
        for a in servos.SERVO_AXES + servos.MOTORS:
            if a.panel in self.builder.SCOPE_PANELS:
                self.assertIn(f"<code>{a.tag}</code>", self.html)
        for h in safety.HAZARDS:
            if h.cell in self.builder.SCOPE_HAZARD_CELLS:
                self.assertIn(f"<code>{h.tag}</code>", self.html)
                self.assertIn(f"PL{h.plr}", self.html)

    def test_the_artifact_converter_accepts_it(self):
        """외부에서 받아 오는 자리가 없고 골격 태그가 벗겨지는 문서여야 발행할 수 있다."""
        conv = _load("build_artifact")
        self.assertIn("infeed", conv.TARGETS)
        body = conv.convert(self.html, DETAIL)
        self.assertIn("<title>", body)
        self.assertNotIn("<!DOCTYPE", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-infeed-detail.html", readme)
