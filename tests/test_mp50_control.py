"""제어반 J-06 — 동시 OFF 회로가 구조로 성립하는지 검증.

이 장치의 핵심 동작은 임펠러와 급기의 **동시 차단**이다. 둘이 몇 초라도
어긋나면 정치 t=0 이 정의되지 않고 DOE 의 정치시간 축이 통째로 못 쓰게 된다.
그래서 여기서 보는 것은 "부품이 목록에 있는가" 가 아니라 **그 동시성이
회로의 구조로 강제되는가** 다.

- 두 출력이 같은 릴레이 접점에 매달려 있는가 (버튼 두 개로 나뉘지 않았는가)
- 급기 밸브가 소자 시 닫히는 NC 인가 (정전에서도 기포가 안 들어가는가)
- VFD 가 프리런으로 서는가 (램프 정지는 감속 중에도 저어서 t=0 을 흐린다)
- 감속비가 설계 회전수를 실제로 낼 수 있는가

회전수·주파수는 계산값이므로 도면이 이 모듈을 읽는지도 함께 본다 — 손으로
박아 두면 감속비를 바꿀 때 그림만 옛 값으로 남는다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

from mp50_separator import control as C
from mp50_separator.checks import DESIGN_MAX_RPM, DOE_SETTLING_MAX_S, GEARBOX_MAX_RPM

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRAWINGS = ROOT / "docs" / "drawings" / "mp50-fabrication-drawings.html"


class TestSpeedChain(unittest.TestCase):
    """모터 → VFD → 감속기 → 교반축."""

    def test_frequency_and_speed_are_inverse(self):
        for rpm in (30.0, 75.0, 150.0):
            self.assertAlmostEqual(C.shaft_rpm(C.vfd_hz(rpm)), rpm, places=9)

    def test_recommended_ratio_reaches_the_design_speed(self):
        top = C.shaft_rpm(C.MAINS_HZ, C.RECOMMENDED_RATIO)
        self.assertGreaterEqual(
            top, DESIGN_MAX_RPM,
            f"감속비 1/{C.RECOMMENDED_RATIO:.0f} 로는 상용주파수에서 {top:.0f} rpm 뿐이다")

    def test_the_vfd_never_has_to_run_above_the_mains_frequency(self):
        """상용주파수 위로 올리면 정토크 영역을 벗어나 재기동 토크가 빠진다."""
        self.assertLessEqual(C.vfd_hz(DESIGN_MAX_RPM), C.MAINS_HZ)

    def test_only_one_standard_ratio_can_do_it(self):
        """감속비 선정이 이 시트의 결론이다 — 후보가 늘면 결론도 바뀐다."""
        ok = [r for r in C.GEAR_RATIOS if C.shaft_rpm(C.MAINS_HZ, r) >= DESIGN_MAX_RPM]
        self.assertEqual(ok, [C.RECOMMENDED_RATIO])

    def test_the_slowest_ratio_lands_on_the_documented_limit(self):
        """1/20 이 [R] 의 상한 90 rpm 과 겹친다 — 그 숫자의 출처로 본 근거."""
        self.assertAlmostEqual(C.shaft_rpm(C.MAINS_HZ, 20.0), GEARBOX_MAX_RPM, delta=5.0)

    def test_ratio_table_verdicts_follow_the_numbers(self):
        for (label, top, hz, verdict), ratio in zip(C.ratio_table(), C.GEAR_RATIOS):
            self.assertEqual(label, f"1/{ratio:.0f}")
            reaches = C.shaft_rpm(C.MAINS_HZ, ratio) >= DESIGN_MAX_RPM
            self.assertEqual(verdict == "가능", reaches, f"{label} 판정이 값과 어긋난다")


class TestSimultaneousCutoff(unittest.TestCase):
    """동시 OFF 는 운용 규칙이 아니라 회로 구조여야 한다."""

    def test_one_relay_carries_every_output_that_must_stop_together(self):
        together = [t for t in C.TERMINALS if t.note.startswith("CR1-")]
        self.assertEqual(len(together), 3, "CR1 접점에 매달린 출력이 셋이 아니다")
        self.assertEqual({t.name for t in together},
                         {"VFD RUN 지령", "급기 솔레노이드", "정치 t=0 마크"})
        for t in together:
            self.assertEqual(t.kind, "DO")

    def test_the_air_valve_closes_when_it_loses_power(self):
        sol = next(i for i in C.PANEL_BOM if i.tag == "SOL")
        self.assertIn("NC", sol.spec, "급기 솔레노이드가 NC 가 아니면 정전에 열린다")

    def test_the_drive_coasts_to_a_stop(self):
        stop = dict((a, b) for a, b, _ in C.VFD_PARAMETERS)["정지방식"]
        self.assertIn("프리런", stop, "램프 정지는 감속 중에도 저어서 t=0 을 흐린다")

    def test_emergency_stop_is_not_the_same_button_as_the_cycle_stop(self):
        """비상정지를 매 배치마다 누르게 만들면 진짜 비상에 쓰이지 않는다."""
        buttons = {i.tag for i in C.PANEL_BOM}
        self.assertLessEqual({"PB2", "EMS"}, buttons)
        self.assertNotEqual(
            next(i for i in C.PANEL_BOM if i.tag == "PB2").name,
            next(i for i in C.PANEL_BOM if i.tag == "EMS").name)

    def test_the_dispersion_time_is_ended_by_a_timer_not_a_person(self):
        step = next(s for s in C.SEQUENCE if s.name == "분산")
        self.assertIn("TIM1", step.ends_by)

    def test_power_cannot_restart_the_agitator_by_itself(self):
        restart = dict((a, b) for a, b, _ in C.VFD_PARAMETERS)["재기동"]
        self.assertIn("금지", restart)


class TestSequence(unittest.TestCase):
    def test_the_agitator_runs_in_exactly_one_step(self):
        running = [s.no for s in C.SEQUENCE if s.impeller == "운전"]
        self.assertEqual(running, ["S2"])

    def test_air_is_open_only_while_the_agitator_runs(self):
        for s in C.SEQUENCE:
            self.assertEqual(s.air == "열림", s.impeller == "운전",
                             f"{s.no} 에서 임펠러와 급기가 따로 논다")

    def test_settling_starts_at_the_cutoff_step(self):
        off = next(i for i, s in enumerate(C.SEQUENCE) if s.name == "동시 OFF")
        self.assertEqual(C.SEQUENCE[off - 1].impeller, "운전")
        self.assertEqual(C.SEQUENCE[off + 1].name, "정치")

    def test_the_timing_chart_is_derived_from_the_sequence(self):
        chart = dict(C.timing())
        self.assertEqual(chart["임펠러"],
                         tuple(int(s.impeller == "운전") for s in C.SEQUENCE))
        self.assertEqual(chart["CR1"], chart["임펠러"], "CR1 이 임펠러와 다른 파형이다")
        self.assertEqual(chart["급기 SOL"], chart["임펠러"])
        self.assertEqual(chart["임펠러"][0], 0, "장입 중에 임펠러가 도는 것으로 그려진다")

    def test_the_settling_timer_spans_the_settling_steps_only(self):
        chart = dict(C.timing())
        for i, s in enumerate(C.SEQUENCE):
            expect = s.name in ("동시 OFF", "정치")
            self.assertEqual(bool(chart["TIM2"][i]), expect, f"{s.no} 의 TIM2 상태")


class TestPanelBillOfMaterials(unittest.TestCase):
    def test_tags_are_unique(self):
        tags = [i.tag for i in C.PANEL_BOM]
        self.assertEqual(len(tags), len(set(tags)))

    def test_every_relay_and_timer_named_by_a_terminal_is_bought(self):
        tags = {i.tag for i in C.PANEL_BOM}
        named = set()
        for t in C.TERMINALS:
            named |= set(re.findall(r"\b(CR\d|TIM\d|PB\d|EMS|SOL|BZ\d|PL\d)", t.name + " " + t.to + " " + t.note))
        missing = {n for n in named if n not in tags and not n.startswith("PL")}
        self.assertEqual(missing, set(), f"단자표가 부르는데 구성품에 없다: {missing}")

    def test_the_settling_timer_covers_the_doe_grid(self):
        tim2 = next(i for i in C.PANEL_BOM if i.tag == "TIM2")
        self.assertIn(f"{DOE_SETTLING_MAX_S:.0f}", tim2.spec)
        self.assertIn("3600", tim2.spec)

    def test_the_drive_frame_is_not_smaller_than_the_motor(self):
        inv = next(i for i in C.PANEL_BOM if i.tag == "INV")
        self.assertIn(f"{C.MOTOR_KW:.2f} kW", inv.spec)

    def test_terminal_numbers_are_unique(self):
        nos = [t.no for t in C.TERMINALS]
        self.assertEqual(len(nos), len(set(nos)))

    def test_the_current_logger_output_is_wired(self):
        """[R] §15 가 요구하는 상시 신호 — 없으면 분산 상태를 남길 방법이 없다."""
        ao = [t for t in C.TERMINALS if t.kind == "AO"]
        self.assertTrue(any("4~20 mA" in t.name for t in ao))


class TestDrawingReadsTheModel(unittest.TestCase):
    """제어반 두 장은 이 모듈의 계산값을 읽어야 한다 — 손으로 박으면 드리프트한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = DRAWINGS.read_text(encoding="utf-8")

    def test_computed_values_appear_on_the_sheets(self):
        for text in (f"{C.vfd_hz(C.SHAFT_MIN_RPM):.1f}~{C.vfd_hz(DESIGN_MAX_RPM):.1f} Hz",
                     f"1/{C.RECOMMENDED_RATIO:.0f}",
                     f"{C.MOTOR_KW:.2f} kW",
                     f"{C.shaft_rpm(C.MAINS_HZ, 20.0):.0f} rpm"):
            self.assertIn(text, self.html, f"제어반 도면에 {text!r} 이 없다 — 다시 생성할 것")

    def test_every_terminal_and_panel_item_is_drawn(self):
        for t in C.TERMINALS:
            self.assertIn(t.no, self.html, f"단자 {t.no}")
        for i in C.PANEL_BOM:
            self.assertIn(i.tag, self.html, f"구성품 {i.tag}")


if __name__ == "__main__":
    unittest.main()
