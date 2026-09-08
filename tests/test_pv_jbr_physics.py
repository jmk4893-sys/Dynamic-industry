"""JBR-201 물리 시뮬레이션 화면 — 생성기 고정, 훅, 색인.

REV.57 에 만든 이 화면은 REV.60 까지 README 색인에도, 「커밋본 == 생성기 출력」 시험에도
없었다. 다른 파생본은 전부 그 시험이 지키는데 이것만 빠져 있었다 — 손으로 고쳐도 아무도
모르는 파일이었다. 다중 패널 채움을 붙이면서 같이 묶는다.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from pv_preprocess import jbr_analysis as ja  # noqa: E402

PAGE = ROOT / "docs/drawings/pv-jbr-physics.html"


def _builder():
    spec = importlib.util.spec_from_file_location("build_jbr_physics", ROOT / "tools/build_jbr_physics.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestJbrPhysicsPage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.b = _builder()
        cls.html = PAGE.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.b.build().replace("__REV__", self.b.numbers()["rev"]),
                         "PYTHONPATH=src python tools/build_jbr_physics.py 를 돌리고 커밋한다")

    def test_the_page_exposes_the_multi_panel_hooks(self):
        """`check_jbr_bin.mjs` 와 영상 렌더러가 붙드는 자리 — 없어지면 둘 다 조용히 죽는다."""
        for hook in ("nextPanel", "binState", "reset, advance, check, draw", "window.PH", "PH.check"):
            self.assertIn(hook, self.html, hook)
        self.assertIn("isBox", self.html)

    def test_the_numbers_on_the_page_are_the_analysis(self):
        m = re.search(r"const NUM = (\{.*?\});\n", self.html, re.S)
        self.assertIsNotNone(m)
        num = json.loads(m.group(1))
        self.assertEqual(num["rev"], "REV.60")
        self.assertEqual(num["bin"]["engine_panels"], ja.BIN_ENGINE["panels"])
        self.assertEqual(num["lift"]["fits_cushion"], ja.lift_budget()["fits_cushion"])
        self.assertEqual(num["throttle"]["cap_mms"], ja.peel_throttle()["cap_mms"])
        self.assertEqual(num["slot"], ja.SEQUENCE["slot"])

    def test_the_numbers_on_the_page_are_rounded_for_every_python(self):
        """f1 이 3.11 과 3.12 에서 마지막 자릿수가 달랐다 — libm 을 지난 값은 판마다 다르다.

        생성기가 6 자리로 안정화해 박는다. 그보다 긴 부동소수가 페이지에 있으면 이
        시험이 어느 판에서든 깨진다 — CI 의 한 판에서만 깨지는 것보다 낫다.
        """
        for name in ("NUM", "SCENE"):
            m = re.search(r"const %s = (\{.*?\});\n" % name, self.html, re.S)
            self.assertIsNotNone(m, name)
            longest = max((len(x.split(".")[1]) for x in re.findall(r"\d+\.\d+", m.group(1))), default=0)
            self.assertLessEqual(longest, self.b.STABLE_DECIMALS, f"{name} 에 {longest} 자리 부동소수가 있다")

    def test_the_scene_reads_the_bin_from_the_plant(self):
        sc = self.b.scene()
        self.assertAlmostEqual(sc["bin"]["inner"][1], (640 - 2 * self.b.BIN_WALL_MM) / 1000.0, places=6)
        self.assertEqual(sc["restFanM"], self.b.REST_FAN_M)

    def test_the_readme_lists_the_page_and_its_tools(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-physics.html", readme)
        self.assertIn("tools/build_jbr_physics.py", readme)
        self.assertIn("tools/check_jbr_bin.mjs", readme)
        self.assertIn("tools/render_jbr_video.mjs", readme)
        self.assertTrue((ROOT / "tools/check_jbr_bin.mjs").exists())


if __name__ == "__main__":
    unittest.main()
