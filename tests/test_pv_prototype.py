"""BFC 시작품 계획 — 정본과 문서, 그리고 설계 모델과의 일치.

시작품 계획이 위험한 지점은 하나다: **합격 기준이 도면과 달라지는 것.** 기준이
설계 모델보다 느슨하면 통과해도 플랜트가 못 서고, 빡세면 되는 기계를 버린다.
그래서 여기서 보는 것은 (1) 커밋된 문서가 생성기 출력과 같은지, (2) 기준이
`kinematics`·`campaign`·`fabrication` 의 값과 같은지, (3) 질문마다 그것을 닫는
시험이 있는지다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, crane, fabrication, kinematics, layout, mounting, prototype

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/drawings/pv-bfc-prototype.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPrototypePlan(unittest.TestCase):
    """정본 — 계획이 스스로 앞뒤가 맞는가."""

    def test_every_question_has_a_test(self):
        missing = [q for q, ok in prototype.questions_are_covered().items() if not ok]
        self.assertEqual(missing, [], f"닫는 시험이 없는 질문: {missing}")

    def test_every_test_points_at_a_real_question(self):
        bad = [t for t, ok in prototype.tests_point_at_questions().items() if not ok]
        self.assertEqual(bad, [], f"없는 질문을 가리키는 시험: {bad}")

    def test_the_source_sheets_are_in_the_fabrication_package(self):
        self.assertTrue(all(prototype.source_sheets_exist().values()))
        for sheet in prototype.SOURCE_SHEETS:
            fabrication.assembly(sheet)          # 없으면 KeyError

    def test_the_quantities_are_one_bay_of_the_plant_assemblies(self):
        """제작 중량·부품 종수·볼트는 A03 + A04 의 **1벌** 이다 (플랜트는 2벌)."""
        a3 = fabrication.assembly("PV-FAB-A03")
        a4 = fabrication.assembly("PV-FAB-A04")
        s = prototype.summary()
        self.assertEqual(prototype.BAYS, 1)
        self.assertAlmostEqual(s["fabricated_kg"],
                               round(a3.fabricated_weight_kg() + a4.fabricated_weight_kg(), 1), places=1)
        self.assertEqual(s["part_kinds"], len(a3.parts) + len(a4.parts))
        self.assertEqual(s["bolts"], a3.bolt_count() + a4.bolt_count())
        self.assertEqual(a3.qty, 2, "플랜트가 2 Bay 라는 전제가 깨지면 이 계획의 '1식' 정의도 바뀐다")

    def test_the_specimen_mix_follows_the_campaign_roster(self):
        self.assertTrue(prototype.specimens_add_up())
        normal, cracked, scrap = (n for _, n, _ in prototype.specimen_mix())
        self.assertGreater(normal, cracked + scrap, "정상이 가장 많아야 로스터 구성비와 맞는다")
        self.assertGreater(cracked, 0, "T-08 의 시료가 없다")
        self.assertGreater(scrap, 0)

    def test_the_schedule_adds_up(self):
        self.assertEqual(prototype.total_weeks(), sum(s.weeks for s in prototype.STAGES))
        self.assertEqual([s.gate for s in prototype.STAGES],
                         [f"G{i}" for i in range(len(prototype.STAGES))])
        for s in prototype.STAGES:
            self.assertGreater(s.weeks, 0)
            self.assertTrue(s.exit, f"{s.gate} 에 통과 조건이 없다")

    def test_the_criteria_come_from_the_design_model(self):
        """합격 기준의 숫자가 모델 값과 같은가 — 여기가 갈라지면 시험이 무의미해진다."""
        crit = " ".join(t.criterion + " " + t.method for t in prototype.TESTS)
        self.assertIn(f"{kinematics.cage_axial_clearance_mm():g} mm", crit)
        self.assertIn(f"{kinematics.PATH[3][1] - kinematics.PATH[3][0]:g} s", crit)
        self.assertIn(f"{kinematics.PATH[-1][1] - kinematics.PATH[0][0]:g} s", crit)
        self.assertIn(f"{campaign.INFEED_S:g} s", crit)
        self.assertIn(f"{kinematics.JAW_OPEN_Z_MM - kinematics.JAW_CLOSED_Z_MM:g} ±1 mm", crit)
        for level in (kinematics.PICK_FACE_MM, kinematics.FLIP_AXIS_MM, kinematics.HANDOVER_MM):
            self.assertIn(f"{level:,}", crit)

    def test_the_out_of_scope_list_names_the_robot_and_the_second_bay(self):
        out = " ".join(x.what for x in prototype.OUT_OF_SCOPE)
        self.assertIn("RB-101", out)
        self.assertIn("두 번째 Bay", out)

    def test_no_price_is_invented(self):
        """단가는 견적으로 채운다 — 지어낸 값이 들어오면 계획이 그 숫자를 따라간다."""
        for c in prototype.cost_lines():
            for unit in ("원", "won", "KRW", "$", "USD"):
                self.assertNotIn(unit, c.qty + c.basis, f"{c.item} 에 단가가 적혀 있다")


class TestPrototypeDocument(unittest.TestCase):
    """문서 — 커밋본이 생성 결과와 같고, 모델 값을 싣고 있는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_prototype")
        cls.html = DOC.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-bfc-prototype.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_prototype.py 를 돌리고 커밋한다")

    def test_it_carries_the_questions_and_the_tests(self):
        for q in prototype.QUESTIONS:
            self.assertIn(f"<code>{q.no}</code>", self.html)
        for t in prototype.TESTS:
            self.assertIn(f"<code>{t.tag}</code>", self.html)

    def test_the_rig_drawing_uses_model_levels(self):
        self.assertIn('aria-label="BFC 시작품 리그 입면"', self.html)
        for level in (kinematics.PICK_FACE_MM, kinematics.FLIP_AXIS_MM, kinematics.HANDOVER_MM,
                      kinematics.PICK_FACE_MM + kinematics.SEPARATION_MM):
            self.assertIn(f"{level:,}", self.html)
        self.assertIn(f"링 피치 {kinematics.RING_PITCH_MM:,}", self.html)

    def test_it_names_the_design_mass_as_a_lower_bound(self):
        self.assertIn(f"{crane.governing_lift().mass_kg:,} kg", self.html)
        self.assertIn("T-11", self.html)

    def test_the_anchors_match_the_mounting_model(self):
        want = sum(x.count * (x.units if x.per_unit else 1)
                   for m in mounting.MOUNTINGS if m.station == "bfc" for x in m.anchors)
        self.assertIn(f"앵커 {want} (M20 케미컬)", self.html)

    def test_the_envelope_matches_the_layout_model(self):
        env = " × ".join(f"{v:,}" for v in layout.STATIONS["bfc"].envelope)
        self.assertIn(env, self.html)

    def test_the_cost_table_leaves_the_unit_price_open(self):
        self.assertIn("견적 대상", self.html)
        self.assertIn("단가는 비워 둔다", self.html)

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("prototype", conv.TARGETS)
        body = conv.convert(self.html, DOC)
        self.assertIn("<title>", body)
        self.assertNotIn("<!DOCTYPE", body)
        self.assertNotIn("<!doctype", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-bfc-prototype.html", readme)
        self.assertIn("prototype.py", readme)


if __name__ == "__main__":
    unittest.main()
