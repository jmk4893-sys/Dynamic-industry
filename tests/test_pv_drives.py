"""구동계 — 전동기가 그 속도로 돌 수 있고, 그 토크가 전달되는가.

정격(`servos`)과 행정·시각(`kinematics`)은 각자 옳아도 **둘을 잇는 값**이
틀리면 기계가 안 선다. 이 검산이 처음 잡은 것이 그것이다: 리드 10 볼스크루에
i=10 감속기를 물려 놓고 모터에 25,000 rpm 을 요구하고 있었다. 여기서는
속도·토크·압착력 세 가지를 본다 — 하나라도 문자열로만 있으면 안 된다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, drives, fabrication, kinematics, layout, servos

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/drawings/pv-infeed-detail.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSpeed(unittest.TestCase):
    """행정 ÷ 시각이 전동기 회전수 안에 드는가."""

    def test_every_axis_stays_under_the_maximum_speed(self):
        bad = {k: v for k, v in drives.speed_checks().items() if not v[1]}
        self.assertEqual(bad, {}, f"최대 회전수를 넘는 축: {bad}")

    def test_the_lift_speed_comes_from_the_motion_plan(self):
        """속도를 손으로 적지 않는다 — `kinematics` 의 행정과 시각에서 나온다."""
        b = drives.ballscrews()[0]
        stroke, seconds = drives._lift_segment()
        self.assertAlmostEqual(b.mean_mm_s, stroke / seconds, places=6)
        self.assertGreater(seconds, 0)
        self.assertIn(seconds, [p[1] - p[0] for p in kinematics.PATH])

    def test_the_lift_is_direct_driven(self):
        """감속기를 물리면 회전수가 배로 뛴다 — 직결이 아니면 이 검산이 깨진다."""
        b = drives.ballscrews()[0]
        self.assertEqual(b.ratio, 1.0)
        self.assertEqual(b.lead_mm, drives.LIFT_LEAD_MM)

    def test_a_geared_lift_would_fail_the_speed_check(self):
        """설계 이전 값(리드 10 · i=10)이 실제로 미달로 나오는가 — 검산의 검산."""
        b = drives.ballscrews()[0]
        old = drives.Ballscrew(b.axis, 10.0, 10.0, b.screws, b.stroke_mm, b.seconds, b.moving_kg)
        self.assertGreater(old.motor_rpm, drives.SERVO_MAX_RPM)

    def test_the_flip_ring_turns_half_a_revolution(self):
        f = drives.friction_drives()[0]
        self.assertEqual(f.turns, 0.5)
        self.assertAlmostEqual(f.ring_od_mm,
                               2 * (kinematics.RING_R_MM + kinematics.RING_TUBE_MM))


class TestTorque(unittest.TestCase):
    """실효 ≤ 정격, 피크 ≤ 정격 × 3."""

    def test_every_axis_passes(self):
        bad = {k: v for k, v in drives.torque_checks().items() if not v[3]}
        self.assertEqual(bad, {}, f"토크가 안 나오는 축: {bad}")

    def test_the_rated_torque_comes_from_the_servo_model(self):
        for axis, kw in {a.tag: a.rated_kw for a in servos.SERVO_AXES}.items():
            if axis not in drives.torque_checks():
                continue
            self.assertAlmostEqual(drives.rated_torque_nm(axis),
                                   kw * 1000 / (2 * 3.141592653589793 * drives.SERVO_RATED_RPM / 60),
                                   places=6)

    def test_the_duty_cycle_comes_from_the_campaign_takt(self):
        """실효 토크는 주기가 정한다 — 주기를 베껴 적으면 둘이 어긋난다."""
        self.assertEqual(drives._cycle_s(), campaign.release_takt_s())

    def test_a_gravity_axis_is_not_judged_by_its_running_torque(self):
        """정속 토크는 정격을 넘어도 된다 — 넘지 않으면 이 시험이 무의미하다."""
        b = drives.ballscrews()[0]
        self.assertGreater(b.motor_torque_nm, drives.rated_torque_nm(b.axis))
        self.assertLessEqual(b.rms_torque_nm(drives._cycle_s()), drives.rated_torque_nm(b.axis))

    def test_the_flip_torque_comes_from_inertia_not_from_lifting_weight(self):
        """700 N·m 는 인양 무게에서 나온 값이었다 — 반전축은 포탈을 돌리지 않는다."""
        f = drives.friction_drives()[0]
        self.assertLess(f.torque_nm, 200)
        self.assertLess(drives.flip_rotating_kg(), 1_000)

    def test_the_rotating_mass_only_counts_parts_that_rotate(self):
        a = fabrication.assembly("PV-FAB-A03")
        whole = sum(p.weight_kg() * p.qty for p in a.parts)
        self.assertLess(drives.flip_rotating_kg(), whole)


class TestPreload(unittest.TestCase):
    """마찰 구동은 압착력이 사양이 아니면 토크가 정해지지 않는다."""

    def test_the_preload_is_enough(self):
        bad = {k: v for k, v in drives.preload_is_specified().items() if not v[2]}
        self.assertEqual(bad, {}, f"압착력 부족: {bad}")

    def test_the_transmissible_torque_exceeds_what_the_motion_needs(self):
        for f in drives.friction_drives():
            self.assertGreater(f.torque_limit_nm(), f.torque_nm, f.axis)

    def test_the_preload_is_a_purchased_item(self):
        """사양이 부품표에 없으면 아무도 그 힘을 만들지 않는다."""
        bought = fabrication.assembly("PV-FAB-A03").commercial
        self.assertIn("BFC-DPL-01", {c.tag for c in bought})
        line = next(c for c in bought if c.tag == "BFC-DPL-01")
        self.assertIn(f"{drives.FLIP_PRELOAD_N:g}", line.spec.replace(",", ""))


class TestSeedDatum(unittest.TestCase):
    """좌표시드 — ±1 mm 와 yaw ±0.15° 가 어느 점에 걸리는가."""

    def test_the_far_corner_is_bigger_than_the_corner_tolerance(self):
        """이 둘이 같으면 기준면 정의가 빠진 것이다 — yaw 가 끝에서 자란다."""
        self.assertGreater(layout.seed_far_corner_mm(), layout.PT_SEED_TOLERANCE_MM)

    def test_the_far_corner_follows_the_panel_length(self):
        import math
        want = (layout.PT_SEED_TOLERANCE_MM
                + campaign.PANEL_LENGTH_MM * math.tan(math.radians(layout.PT_SEED_YAW_DEG)))
        self.assertAlmostEqual(layout.seed_far_corner_mm(), round(want, 2), places=2)

    def test_a_whole_panel_within_one_millimetre_needs_no_yaw_left(self):
        """하류가 패널 전체 ±1 mm 를 기대하면 yaw 예산이 남지 않는다 — 그래서 기준 모서리다."""
        self.assertEqual(layout.seed_yaw_for(layout.PT_SEED_TOLERANCE_MM), 0.0)
        self.assertGreater(layout.seed_yaw_for(layout.seed_far_corner_mm()), 0.0)

    def test_the_inverse_round_trips(self):
        yaw = layout.seed_yaw_for(5.0)
        self.assertAlmostEqual(yaw, layout.PT_SEED_YAW_DEG, delta=layout.PT_SEED_YAW_DEG)
        self.assertLess(yaw, layout.PT_SEED_YAW_DEG)


class TestOpenItems(unittest.TestCase):
    """못 닫은 것을 못 닫았다고 적었는가 — 임의값으로 채우면 검산이 거짓으로 통과한다."""

    def test_there_are_open_items(self):
        self.assertTrue(fabrication.OPEN_ITEMS)

    def test_each_one_says_why_it_is_open_and_what_closes_it(self):
        for o in fabrication.OPEN_ITEMS:
            for field in ("title", "why_open", "closes_with", "blocks"):
                self.assertTrue(getattr(o, field).strip(), f"{o.tag} 의 {field} 가 비었다")

    def test_the_tags_are_unique(self):
        tags = [o.tag for o in fabrication.OPEN_ITEMS]
        self.assertEqual(len(tags), len(set(tags)))

    def test_the_prototype_questions_they_name_exist(self):
        bad = [k for k, v in fabrication.open_items_point_at_questions().items() if not v]
        self.assertEqual(bad, [], f"없는 질문을 가리킨다: {bad}")

    def test_they_carry_no_markdown(self):
        """제작 도면집은 마크다운을 그리지 않는다 — 별표가 그대로 찍힌다."""
        for o in fabrication.OPEN_ITEMS:
            for field in ("title", "why_open", "closes_with", "blocks"):
                self.assertNotIn("**", getattr(o, field), f"{o.tag} 의 {field}")

    def test_a_closed_finding_is_not_listed_as_open(self):
        """계산으로 닫은 것(구동계·체결 길이)이 미결로 남아 있으면 안 된다."""
        text = " ".join(o.title + o.why_open for o in fabrication.OPEN_ITEMS)
        for closed in ("감속비", "볼스크루 리드", "앵커 로드 길이"):
            self.assertNotIn(closed, text, f"이미 닫힌 것이 미결에 있다: {closed}")

    def test_the_fabrication_sheet_lists_them(self):
        html = (ROOT / "docs/drawings/pv-infeed-fab.html").read_text(encoding="utf-8")
        self.assertIn("미결 항목 — 도면으로 못 닫는 것", html)
        for o in fabrication.OPEN_ITEMS:
            self.assertIn(o.tag, html, f"{o.tag} 가 도면집에 없다")
            self.assertIn(o.closes_with, html, f"{o.tag} 의 닫는 조건이 도면집에 없다")


class TestDocument(unittest.TestCase):
    """검산 결과가 문서에 실리는가 — 실리지 않으면 아무도 안 본다."""

    @classmethod
    def setUpClass(cls):
        cls.html = DOC.read_text(encoding="utf-8")

    def test_the_detail_sheet_carries_the_transmission_check(self):
        self.assertIn("전동–기구 검산", self.html)
        for axis in drives.speed_checks():
            self.assertIn(axis, self.html)

    def test_it_carries_the_far_corner(self):
        self.assertIn("반대편 모서리 흔들림", self.html)
        self.assertIn(f"±{layout.seed_far_corner_mm():g} mm", self.html)

    def test_the_committed_sheet_is_what_the_builder_makes(self):
        builder = _load("build_infeed_detail")
        self.assertEqual(self.html, builder.build(),
                         "docs/drawings/pv-infeed-detail.html 이 생성기 출력과 다르다")


if __name__ == "__main__":
    unittest.main()
