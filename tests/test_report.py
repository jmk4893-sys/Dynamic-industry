import os
import pathlib
import subprocess
import sys
import unittest

from . import _path  # noqa: F401

from flotation_design.circuit_design import build_circuit
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
        self.assertGreater(self.case.result_peak.recovery["Ag"], 0.68)
        self.assertGreater(self.case.result_peak.recovery["Cu"], 0.80)


class TestRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = render(build_circuit())

    def test_contains_all_sections(self):
        for heading in (
            "## 1. 급광 사양",
            "## 2. 회로 구성",
            "## 3. 셀별 기계 사양",
            "## 4. 회로 물질수지",
            "## 5. 러퍼 단독(Phase 1) 대비 효과",
            "## 6. 조건조",
            "## 7. 약제 계통",
            "## 8. 유틸리티 집계",
            "## 9. 확정 치수 검증",
        ):
            self.assertIn(heading, self.text)

    def test_lists_every_cell(self):
        for tag in ("FC-101", "FC-102", "FC-103"):
            self.assertIn(tag, self.text)

    def test_reports_both_throughputs(self):
        self.assertIn("평균 0.30 t/h", self.text)
        self.assertIn("최대 0.50 t/h", self.text)

    def test_no_overload_or_undersizing_flagged(self):
        self.assertNotIn("— NG", self.text)
        self.assertNotIn("| NG |", self.text)


class TestCli(unittest.TestCase):
    def test_writes_file(self):
        import pathlib
        import tempfile

        from flotation_design.__main__ import main

        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "sub" / "calc.md"
            self.assertEqual(main(["-o", str(out)]), 0)
            self.assertIn("부유선별 회로 설계 계산서", out.read_text(encoding="utf-8"))

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
        expected = render(build_circuit()) + "\n"
        self.assertEqual(
            doc.read_text(encoding="utf-8"),
            expected,
            "계산서가 코드와 어긋남 — `python -m flotation_design -o docs/design-calculation.md` 재실행 필요",
        )


class TestDocumentedCommandsRun(unittest.TestCase):
    """README·설계문서의 셸 코드블록에 적힌 실행 명령이 실제로 동작하는지 확인.

    패키지가 src 레이아웃이라 PYTHONPATH 없이 ``python -m flotation_design`` 을
    적어두면 신규 체크아웃에서 `No module named flotation_design` 로 실패한다.
    문서와 실제 동작이 어긋나지 않도록 코드블록에서 명령을 뽑아 그대로 실행한다.
    """

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    DOCS = ("README.md", "docs/flotation-separator-design.md")

    def _documented_commands(self) -> list[tuple[str, str]]:
        """문서의 ```bash 코드블록 안에 있는 flotation_design 실행 명령."""
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
                if "-o" in args:  # 커밋된 계산서를 덮어쓰지 않도록 출력을 버린다
                    args[args.index("-o") + 1] = os.devnull
                proc = subprocess.run(
                    [sys.executable, *args[1:]],
                    cwd=self.ROOT,
                    env={**os.environ, "PYTHONPATH": "src"},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, f"{rel}: {command}\n{proc.stderr}")


class TestThroughputOverrideIsHonest(unittest.TestCase):
    """처리량을 바꾸면 셀은 확정 치수 그대로이므로, 계산서가 그 사실을 드러내야 한다."""

    @classmethod
    def setUpClass(cls):
        from dataclasses import replace

        from flotation_design import design_basis as db

        cls.oversized = render(build_circuit(replace(db.FEED, average_tph=0.4, peak_tph=0.6)))
        cls.nominal = render(build_circuit())

    def test_nominal_case_has_no_warning(self):
        self.assertNotIn("[!WARNING]", self.nominal)
        self.assertNotIn("**NG**", self.nominal)

    def test_override_beyond_cell_capacity_warns(self):
        self.assertIn("[!WARNING]", self.oversized)
        self.assertIn("**NG**", self.oversized)
        self.assertIn("기존 셀의 성능 계산", self.oversized)

    def test_override_reports_required_cell_size(self):
        # 확정 치수로는 부족하다면, 필요한 치수를 함께 제시해야 한다.
        self.assertIn("필요 치수 (재계산)", self.oversized)
        self.assertIn("726 x 841 mm", self.oversized)

    def test_override_relabels_operating_points(self):
        self.assertIn("최대 0.60 t/h", self.oversized)
        self.assertIn("평균 0.40 t/h", self.oversized)
        self.assertNotIn("최대 0.50 t/h", self.oversized)
        self.assertNotIn("평균 0.30 t/h", self.oversized)

    def test_override_still_records_the_design_basis(self):
        self.assertIn("설계 기준 처리량 (design_basis)", self.oversized)
        self.assertIn("0.30 / 0.50 t/h", self.oversized)
