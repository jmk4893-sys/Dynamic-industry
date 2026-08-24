import unittest

from . import _path  # noqa: F401

from flotation_design.report import build_design, render


class TestDesignCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = build_design()

    def test_confirmed_cell_dimensions(self):
        g = self.case.geometry
        self.assertAlmostEqual(g.width_m, 0.70, places=9)
        self.assertAlmostEqual(g.shell_height_m, 0.81, places=9)
        self.assertAlmostEqual(g.lip_height_m, 0.75, places=9)

    def test_rounded_cell_is_not_undersized(self):
        self.assertGreaterEqual(
            self.case.geometry.effective_slurry_volume_m3,
            self.case.calculated_geometry.effective_slurry_volume_m3 * 0.98,
        )

    def test_residence_times(self):
        self.assertAlmostEqual(self.case.tau_peak_min, 9.9, delta=0.2)
        self.assertAlmostEqual(self.case.tau_avg_min, 16.5, delta=0.3)

    def test_drive_and_blower_selection(self):
        self.assertEqual(self.case.impeller.motor_rating_kw, 2.2)
        self.assertEqual(self.case.aeration.blower_rating_kw, 0.75)

    def test_conditioner_train(self):
        tags = [c.tag for c in self.case.conditioners]
        self.assertEqual(tags, ["CT-1", "CT-2"])
        self.assertGreater(
            self.case.conditioners[0].tank_volume_m3,
            self.case.conditioners[0].working_volume_m3,
        )

    def test_performance_at_both_operating_points(self):
        self.assertGreater(self.case.result_avg.recovery["Ag"], self.case.result_peak.recovery["Ag"])
        self.assertGreater(self.case.result_peak.recovery["Ag"], 0.70)
        self.assertGreater(self.case.result_peak.recovery["Cu"], 0.80)


class TestRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = render(build_design())

    def test_contains_all_sections(self):
        for heading in (
            "## 1. 급광 사양",
            "## 2. 셀 체적 및 형상",
            "## 3. 로터/스테이터 및 구동부",
            "## 4. 급기 (aeration)",
            "## 5. 성능 예측",
            "## 6. 조건조",
            "## 7. 약제 계통",
            "## 8. 유틸리티 집계",
        ):
            self.assertIn(heading, self.text)

    def test_reports_both_throughputs(self):
        self.assertIn("평균 0.30 t/h", self.text)
        self.assertIn("최대 0.50 t/h", self.text)

    def test_no_overload_flagged(self):
        self.assertNotIn("— NG", self.text)


class TestCli(unittest.TestCase):
    def test_writes_file(self):
        import pathlib
        import tempfile

        from flotation_design.__main__ import main

        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "sub" / "calc.md"
            self.assertEqual(main(["-o", str(out)]), 0)
            self.assertIn("단단 부유선별기 설계 계산서", out.read_text(encoding="utf-8"))

    def test_throughput_override(self):
        from flotation_design.__main__ import main

        self.assertEqual(main(["--average-tph", "0.2", "--peak-tph", "0.4", "-o", "/dev/null"]), 0)


if __name__ == "__main__":
    unittest.main()


class TestGeneratedDocumentIsCurrent(unittest.TestCase):
    """docs/design-calculation.md 가 코드 계산 결과와 일치하는지 확인."""

    def test_committed_calculation_matches_code(self):
        import pathlib

        doc = pathlib.Path(__file__).resolve().parents[1] / "docs" / "design-calculation.md"
        self.assertTrue(doc.exists(), "docs/design-calculation.md 없음")
        expected = render(build_design()) + "\n"
        self.assertEqual(
            doc.read_text(encoding="utf-8"),
            expected,
            "계산서가 코드와 어긋남 — `python -m flotation_design -o docs/design-calculation.md` 재실행 필요",
        )
