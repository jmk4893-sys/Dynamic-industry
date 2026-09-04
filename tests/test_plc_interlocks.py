"""PLC 인터록을 실제로 돌려 결과를 고정한다.

논리식은 글로만 있으면 두 가지가 조용히 지나간다.

  · 논리식이 부르는데 그 신호를 만들 장치가 현장에 없다.
    없는 신호는 영원히 성립하지 않으므로 그 허가는 걸리지 않거나 그 트립은
    절대 동작하지 않는다. 화면에도 도면에도 아무 표시가 나지 않는다.
  · 장치는 서 있는데 어떤 논리식도 그 신호를 쓰지 않는다.

tools/plc_model.py 가 신호마다 '이 신호를 만드는 현장 장치'와 I/O 종류를
적어 두고, 그 장치가 제작도 목록·3D 도면에 실제로 있는지 대조한다. 여기서는
그 모델을 돌려 미해결이 0 인지, 그리고 I/O 예산이 사양서가 요구하는 예비율을
지키는지 확인한다. 한쪽만 고치면 반드시 실패한다.
"""

import importlib.util
import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"


def _model():
    spec = importlib.util.spec_from_file_location("plc_model", ROOT / "tools" / "plc_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestInterlockModelRuns(unittest.TestCase):
    """모델을 돌린 결과가 깨끗한지."""

    @classmethod
    def setUpClass(cls):
        cls.m = _model()
        cls.console = CONSOLE.read_text(encoding="utf-8")

    def test_every_term_has_a_definition(self):
        """부르는데 만드는 곳이 없는 신호가 있으면 그 논리식은 죽은 식이다."""
        leaves = {l.name for l in self.m.LEAVES}
        derived = {d.name for d in self.m.DERIVED}
        dangling = [(d.name, t) for d in self.m.DERIVED for t in d.terms
                    if t not in leaves and t not in derived]
        self.assertEqual(dangling, [], f"정의 없는 신호: {dangling}")

    def test_every_signal_is_actually_read(self):
        """돈 들여 단 장치가 제어에 반영이 안 된 상태를 잡는다."""
        used = {t for d in self.m.DERIVED for t in d.terms}
        unused = sorted(l.name for l in self.m.LEAVES if l.name not in used)
        self.assertEqual(unused, [], f"어떤 논리식도 읽지 않는 신호: {unused}")

    def test_every_field_signal_has_a_device_in_the_model(self):
        """신호를 만들 장치가 제작도 목록·도면에 없으면 견적도 시공도 못 한다."""
        missing = [f"{l.name}←{l.device}" for l in self.m.LEAVES
                   if l.device not in self.console]
        self.assertEqual(missing, [], f"장치가 없는 신호: {missing}")

    def test_every_device_is_a_bill_of_material_line(self):
        """도면 어딘가에 글자로 있는 것과 구매 품목인 것은 다르다."""
        bom = set()
        for m in re.finditer(r"parts:\[(.*?)\]\}", self.console):
            bom |= set(re.findall(r"'([^']+)'", m.group(1)))
        # 백시트 끝단 비전은 여기 있었다. 폐기된 REV.05 문장에만 이름이 남아
        # 장치 대조를 통과하고 있었고, 그래서 구매 품목 요구도 면제돼 있었다.
        # 이제 GR-W1 상부에 실제로 세웠으므로 예외가 아니다.
        soft = {"전력품질계", "PLC-101반", "접지바", "SPD Type1+2",
                "UPS-101", "24VDC PSU A/B", "Q0 ACB 4P 800AF", "서보 랙피니언",
                "절대치 엔코더", "HKB Z축 서보슬라이드", "HKS Z축 서보슬라이드",
                "SH-101 투입롤러", "투입 에어록", "격리셔터", "외함 롤 포트",
                "펜스 인터록 해치", "코너 승강대", "역화격리게이트", "층별 잠금실린더×5",
                "분할클램프×4", "체크밸브×6", "SSR 분기모듈×60", "토크서보·직경센서",
                "TS-101 2단 포크", "서보모터·감속기", "IE4 기어모터", "VFD 기어모터",
                "VFD 기어모터×2", "GC-301A 캐리지", "RJ 횡셔틀", "배기팬 A", "배기팬 B",
                "진공펌프 A/B"}
        need = {l.device for l in self.m.LEAVES} | {d.device for d in self.m.DRIVES}
        missing = sorted(d for d in need - bom - soft)
        self.assertEqual(missing, [], f"제작도 목록에 없는 장치: {missing}")

    def test_every_drive_has_a_safe_stop(self):
        """구동부에 안전정지 수단이 없으면 트립이 걸려도 축은 돈다."""
        no_stop = [d.tag for d in self.m.DRIVES if not d.stop]
        self.assertEqual(no_stop, [], f"안전정지 수단 없는 구동부: {no_stop}")
        servos = [d for d in self.m.DRIVES if d.tag.startswith("SV-")]
        self.assertGreaterEqual(len(servos), 7, "서보축 수가 줄었다")
        for d in servos:
            self.assertIn("STO", d.stop, f"{d.tag} 서보에 STO 가 없다")

    def test_the_report_has_no_unresolved_items(self):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            problems = self.m.report()
        self.assertEqual(problems, [], f"미해결: {problems}\n{buf.getvalue()}")


class TestIoBudget(unittest.TestCase):
    """선언한 I/O 가 실제 점수를 담는지."""

    @classmethod
    def setUpClass(cls):
        cls.m = _model()
        cls.console = CONSOLE.read_text(encoding="utf-8")
        cls.rfq = RFQ.read_text(encoding="utf-8") if RFQ.exists() else None
        cls.use = {k: 0 for k in cls.m.BUDGET}
        for l in cls.m.LEAVES:
            if l.io in cls.use:
                cls.use[l.io] += l.count
        for d in cls.m.DRIVES:
            if d.io in cls.use:
                cls.use[d.io] += d.count

    def test_budget_covers_the_points(self):
        for k, cap in self.m.BUDGET.items():
            self.assertLessEqual(self.use[k], cap, f"{k} 점수 {self.use[k]} 가 {cap} 를 넘는다")

    def test_spare_meets_the_specification(self):
        """사양서 7.1 이 예비 20% 이상을 요구한다 — 선언값이 그것을 지켜야 한다."""
        for k, cap in self.m.BUDGET.items():
            spare = (cap - self.use[k]) / cap
            self.assertGreaterEqual(spare, self.m.SPARE_MIN,
                                    f"{k} 예비 {100*spare:.1f}% 가 20% 미만이다")

    def test_console_drawing_declares_the_same_budget(self):
        b = self.m.BUDGET
        self.assertIn(f"DI {b['DI']} · DO {b['DO']}", self.console)
        self.assertIn(f"AI {b['AI']} · AO {b['AO']}", self.console)
        self.assertIn(f"TC {b['TC']}", self.console)
        self.assertIn(f"F-DI {b['F-DI']} · F-DO {b['F-DO']}", self.console)
        self.assertIn(f">DI{b['DI']} / DO{b['DO']}<", self.console)
        self.assertIn(f">AI{b['AI']} / AO{b['AO']} / TC{b['TC']}<", self.console)
        self.assertIn(f">F-DI{b['F-DI']} / F-DO{b['F-DO']}<", self.console)

    def test_specification_declares_the_same_budget_and_the_actual_use(self):
        if self.rfq is None:
            self.skipTest("이 브랜치에는 사양서가 없다")
        b = self.m.BUDGET
        self.assertIn(f"DI {b['DI']} · DO {b['DO']} · AI {b['AI']} · AO {b['AO']} · TC {b['TC']}",
                      self.rfq, "사양서 표준 I/O 가 콘솔·모델과 다르다")
        self.assertIn(f"F-DI {b['F-DI']} · F-DO {b['F-DO']}", self.rfq)
        u = self.use
        self.assertIn(f"DI {u['DI']} · DO {u['DO']} · AI {u['AI']} · AO {u['AO']} · TC {u['TC']}",
                      self.rfq, "사양서에 적은 실사용 점수가 모델과 다르다")
        self.assertIn(f"F-DI {u['F-DI']} · F-DO {u['F-DO']}", self.rfq)


class TestSignalsFoundByRunningIt(unittest.TestCase):
    """모델을 돌려서 찾아낸 것들 — 다시 빠지면 여기서 걸린다."""

    @classmethod
    def setUpClass(cls):
        cls.console = CONSOLE.read_text(encoding="utf-8")

    def _bom(self):
        bom = set()
        for m in re.finditer(r"parts:\[(.*?)\]\}", self.console):
            bom |= set(re.findall(r"'([^']+)'", m.group(1)))
        return bom

    def test_web_tension_load_cell_is_back(self):
        """MOTION_TRIP 의 WEB_TENSION_HIGH 를 만드는 장치. 개정 중에 목록에서 빠졌었다."""
        self.assertIn("장력 로드셀", self._bom(),
                      "권취부 장력 로드셀이 제작도 목록에서 빠졌다 — WEB_TENSION_HIGH 가 죽는다")

    def test_hard_trip_inputs_exist(self):
        """IR_HARD_TRIP 은 소프트웨어와 무관한 하드와이어 경로다."""
        bom = self._bom()
        for part in ("독립 과온센서", "연기센서", "CO센서", "IR 뱅크 CT·SSR 피드백×6", "풍량센서"):
            self.assertIn(part, bom, f"IR_HARD_TRIP 입력 {part} 가 없다")

    def test_permit_position_sensors_exist(self):
        """허가 조건이 읽는 위치센서. 액추에이터만 있고 위치확인이 없으면 허가가 성립하지 않는다."""
        bom = self._bom()
        for part in ("에어록 도어 위치센서×8", "격리셔터 위치센서×2", "롤 반출 위치센서×2",
                     "BS-301 새들 존재센서×2", "칼날 Z축 상하한센서×4", "방화댐퍼 위치센서×2"):
            self.assertIn(part, bom, f"위치확인 장치 {part} 가 없다")

    def test_path_clear_photocells_exist(self):
        bom = self._bom()
        for part in ("주행로 광전센서×2", "셀 경로 광전센서×2",
                     "유리 경로 광전센서×3", "GC 교대 광전센서×2"):
            self.assertIn(part, bom, f"경로확인 광전센서 {part} 가 없다")

    def test_safety_devices_are_purchasable_lines(self):
        """광커튼·뮤팅·신호등은 그려져 있었지만 구매 품목이 아니었다."""
        bom = self._bom()
        for part in ("안전 광커튼 LC-001/002", "뮤팅 센서 M1~M4×2조",
                     "적층 신호등·부저 ST-101/102"):
            self.assertIn(part, bom, f"안전장치 {part} 가 제작도 목록에 없다")

    def test_the_new_sensors_are_drawn(self):
        body = re.search(r"\n    function interlockSensors\(.*?\n    \}", self.console, re.S)
        self.assertIsNotNone(body, "interlockSensors 가 없다")
        drawn = "\n".join(ln for ln in body.group(0).split("\n")
                          if re.search(r"\b(?:box|cylinder|column)\(", ln))
        for token in ("칼날 Z축 상하한센서", "셀 경로 광전센서", "주행로 광전센서",
                      "격리셔터 위치센서", "롤 반출 위치센서", "BS-301 새들 존재센서",
                      "웹 파단 검출센서", "백시트 끝단 비전", "유리 경로 광전센서",
                      "GC 교대 광전센서", "에어록 도어 위치센서", "격리실 존재센서",
                      "방화댐퍼 위치센서"):
            self.assertIn(token, drawn, f"{token} 가 도면에 그려지지 않았다")
        self.assertIn("interlockSensors();", self.console, "센서가 배치에 놓이지 않았다")


if __name__ == "__main__":
    unittest.main()
