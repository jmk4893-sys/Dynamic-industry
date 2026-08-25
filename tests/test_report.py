import os
import pathlib
import subprocess
import sys
import unittest

from . import _path  # noqa: F401

from flotation_design.plant import build_plant
from flotation_design.report import render


class TestPlantDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant = build_plant()

    def test_both_options_are_built(self):
        self.assertIsNotNone(self.plant.rfc)
        self.assertIsNotNone(self.plant.mechanical)

    def test_rfc_uses_one_vessel_mechanical_uses_three_cells(self):
        self.assertEqual(
            sum(c.cells_in_series for c in self.plant.mechanical.cells), 3
        )

    def test_rfc_recovers_more_silver(self):
        self.assertGreater(
            self.plant.rfc.performance_peak.recovery("Ag"),
            self.plant.mechanical.result_peak.recovery("Ag"),
        )

    def test_rfc_uses_less_power(self):
        self.assertLess(self.plant.rfc.installed_kw, self.plant.mechanical.installed_kw)

    def test_both_options_hit_the_same_grade_ceiling(self):
        """정광 품위는 장치가 아니라 원료의 복합입자 성질로 결정된다."""
        a = self.plant.rfc.performance_peak.concentrate_grade("Ag")
        b = self.plant.mechanical.result_peak.concentrate.grade_fraction("Ag")
        self.assertLess(abs(a - b) / a, 0.10)

    def test_mechanical_cells_meet_target_residence(self):
        from flotation_design import design_basis as db
        from flotation_design.plant import mechanical_sizing_check

        mech = self.plant.mechanical
        for tag in ("FC-201", "FC-202", "FC-203"):
            target = db.MECHANICAL_RESIDENCE_MIN[tag]
            cell = mech.cell(tag)
            available = cell.geometry.effective_slurry_volume_m3 * cell.cells_in_series
            self.assertGreaterEqual(
                available,
                mechanical_sizing_check(mech.result_peak, tag, target) * 0.98,
                tag,
            )

    def test_froth_loading_within_limits(self):
        for tag in ("FC-201", "FC-202"):
            fl = self.plant.mechanical.froth_loading(tag, self.plant.mechanical.result_peak)
            self.assertTrue(fl.carry_rate_ok, tag)
            self.assertTrue(fl.lip_loading_ok, tag)

    def test_thickeners_sized_on_overflow(self):
        tk = self.plant.rfc.tailings_thickener
        self.assertAlmostEqual(tk.area_m2, tk.overflow_m3h / tk.rise_rate_m_h, places=9)
        self.assertGreater(tk.diameter_m, 0.0)

    def test_unknown_cell_tag_raises(self):
        with self.assertRaises(KeyError):
            self.plant.mechanical.cell("FC-999")


class TestRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = render(build_plant())

    def test_contains_all_sections(self):
        for heading in (
            "## 0. 설계 근거",
            "## 1. 급광 사양",
            "## 2. 1안",
            "## 3. 2안",
            "## 4. 두 안 비교",
            "## 5. 약제 계통",
            "## 6. 모델 검증",
        ):
            self.assertIn(heading, self.text)

    def test_cites_both_papers(self):
        self.assertIn("Minerals Engineering", self.text)
        self.assertIn("ChemRxiv", self.text)

    def test_discloses_the_patent_application(self):
        self.assertIn("2025902821", self.text)

    def test_reports_both_throughputs(self):
        self.assertIn("최대 0.50 t/h", self.text)
        self.assertIn("평균 0.30 t/h", self.text)

    def test_no_overload_or_undersizing_flagged(self):
        self.assertNotIn("— NG", self.text)
        self.assertNotIn("| **NG** |", self.text)
        self.assertNotIn("**초과**", self.text)


class TestGeneratedDocumentIsCurrent(unittest.TestCase):
    """docs/design-calculation.md 가 코드 계산 결과와 일치하는지 확인."""

    def test_committed_calculation_matches_code(self):
        doc = pathlib.Path(__file__).resolve().parents[1] / "docs" / "design-calculation.md"
        self.assertTrue(doc.exists(), "docs/design-calculation.md 없음")
        expected = render(build_plant()) + "\n"
        self.assertEqual(
            doc.read_text(encoding="utf-8"),
            expected,
            "계산서가 코드와 어긋남 — "
            "`PYTHONPATH=src python -m flotation_design -o docs/design-calculation.md` 재실행 필요",
        )


class TestCli(unittest.TestCase):
    def test_writes_file(self):
        import tempfile

        from flotation_design.__main__ import main

        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "sub" / "calc.md"
            self.assertEqual(main(["-o", str(out)]), 0)
            self.assertIn("설계 계산서", out.read_text(encoding="utf-8"))

    def test_throughput_override(self):
        from flotation_design.__main__ import main

        self.assertEqual(main(["--average-tph", "0.2", "--peak-tph", "0.4", "-o", os.devnull]), 0)


class TestDocumentedCommandsRun(unittest.TestCase):
    """README·설계문서의 셸 코드블록에 적힌 실행 명령이 실제로 동작하는지 확인.

    패키지가 src 레이아웃이라 PYTHONPATH 없이 ``python -m flotation_design`` 을
    적어두면 신규 체크아웃에서 `No module named flotation_design` 로 실패한다.
    """

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    DOCS = ("README.md", "docs/flotation-separator-design.md")

    def _documented_commands(self) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for rel in self.DOCS:
            in_shell_block = False
            for line in (self.ROOT / rel).read_text(encoding="utf-8").splitlines():
                if line.startswith("```"):
                    in_shell_block = line.strip() == "```bash"
                    continue
                if not in_shell_block:
                    continue
                command = line.split("#")[0].strip()
                if "python -m flotation_design" in command:
                    found.append((rel, command))
        return found

    def test_documented_commands_are_found(self):
        self.assertGreaterEqual(len(self._documented_commands()), 4)

    def test_every_documented_command_succeeds(self):
        for rel, command in self._documented_commands():
            with self.subTest(doc=rel, command=command):
                prefix = "PYTHONPATH=src "
                self.assertTrue(
                    command.startswith(prefix),
                    f"{rel}: src 레이아웃이므로 {prefix.strip()} 가 필요함 — {command}",
                )
                args = command[len(prefix) :].split()
                self.assertEqual(args[0], "python")
                if "-o" in args:
                    args[args.index("-o") + 1] = os.devnull
                proc = subprocess.run(
                    [sys.executable, *args[1:]],
                    cwd=self.ROOT,
                    env={**os.environ, "PYTHONPATH": "src"},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, f"{rel}: {command}\n{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
