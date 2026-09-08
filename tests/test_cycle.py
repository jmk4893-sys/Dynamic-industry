"""사이클 거울(tools/cycle.py) — 콘솔의 thermalModel 과 같은 식인가.

에어록·열수지·IR 뱅크·열해석이 택트·체류·처리량을 값으로 들고 있었고,
패널이 2,400 × 1,200 에서 2,500 × 1,400 으로 커지던 날 그 값들은 전부
틀린 채로 남았을 것이다. cycle.py 가 콘솔의 식을 다시 써서 도구들에
나눠 준다 — 그러면 남는 위험은 하나다: **거울이 원본과 갈라지는 것**.

그래서 콘솔의 thermalModel 함수 자체를 node 로 돌려 파이썬 거울과 대조한다.
콘솔 소스에서 함수 본문을 그대로 잘라 오므로, 콘솔이 식을 바꾸면 여기가
먼저 깨진다. node 가 없는 환경에서는 대조를 건너뛰고 거울 내부의 일관성만
본다.
"""

import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

from . import _path  # noqa: F401

import console_consts  # noqa: E402
import cycle as CY  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
KEYS = ("q", "rated", "eta", "useful", "dwell", "pitch", "thermalRate", "handling",
        "leadTime", "peelTime", "tandemCycle", "tandemRate", "lineCycle", "lineRate",
        "energyPerPanel", "returnDistance", "returnTime", "knifeCycle", "knifeRate",
        "targetCycle", "returnSpeedFloor", "knifeLineCycle", "knifeLineRate", "averagePower")


def js_function():
    src = CONSOLE.read_text(encoding="utf-8")
    m = re.search(r"\n    function thermalModel\(v\)\{.*?\n    \}\n", src, re.S)
    assert m, "콘솔에 thermalModel 이 없다"
    return m.group(0)


class TestTheMirrorIsTheConsole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")

    def _run_js(self, v):
        script = (f"const MODEL={json.dumps(CY.MODEL)};\n{js_function()}\n"
                  f"process.stdout.write(JSON.stringify(thermalModel({json.dumps(v)})));")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(script)
        out = subprocess.run([self.node, f.name], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_the_default_input_matches_the_console_function(self):
        if not self.node:
            self.skipTest("node 가 없다")
        js, py = self._run_js(CY.DEFAULT), CY.model()
        for k in KEYS:
            self.assertAlmostEqual(js[k], py[k], places=9, msg=f"{k}: js {js[k]} · py {py[k]}")
        self.assertEqual(js["bottleneck"], py["bottleneck"])

    def test_the_range_corners_match_too(self):
        """기본 입력만 맞고 다른 입력에서 갈라지는 거울은 거울이 아니다."""
        if not self.node:
            self.skipTest("node 가 없다")
        R = CY.RANGE
        for v in ({**CY.DEFAULT, "panelLength": R["panelLength"][0], "panelWidth": R["panelWidth"][0]},
                  {**CY.DEFAULT, "knifeSpeed": R["knifeSpeed"][1], "knifeReturnSpeed": R["knifeReturnSpeed"][0]},
                  {**CY.DEFAULT, "lampPower": R["lampPower"][1], "heatEfficiency": R["heatEfficiency"][0]}):
            js, py = self._run_js(v), CY.model(v)
            for k in KEYS:
                self.assertAlmostEqual(js[k], py[k], places=9, msg=f"{k} @ {v}")

    def test_the_named_values_are_the_default_run(self):
        m = CY.model()
        self.assertEqual(CY.TAKT, m["knifeLineCycle"])
        self.assertEqual(CY.DWELL, m["dwell"])
        self.assertEqual(CY.RATE_THERMAL, m["thermalRate"])
        self.assertAlmostEqual(CY.RATE_NET, m["knifeLineRate"] * CY.AVAILABILITY, places=12)
        self.assertEqual(CY.NET_TARGET, int(console_consts.const("NET_TARGET")))

    def test_the_contract_sits_just_under_the_model(self):
        """계약 58 장/h 는 기준 패널에서 모델이 내는 순생산 바로 아래여야 한다 —
        위면 지킬 수 없고, 한참 아래면 팔 수 있는 것을 안 판 것이다."""
        self.assertLessEqual(CY.NET_TARGET, CY.RATE_NET)
        self.assertGreater(CY.NET_TARGET, CY.RATE_NET - 1.0)

    def test_the_tools_read_the_mirror_not_typed_numbers(self):
        """도구가 택트를 값으로 들면 다음 패널 변경에서 또 갈라진다."""
        for rel in ("tools/airlock.py", "tools/analysis_irbank.py", "tools/analysis_thermal.py",
                    "tools/heatbalance.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("import cycle as CY", src, f"{rel} 이 사이클 거울을 쓰지 않는다")
            self.assertNotRegex(src, r"^TAKT\s*=\s*[\d.]+", f"{rel} 이 택트를 값으로 든다")
