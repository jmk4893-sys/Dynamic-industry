"""SG-301 엣지 연마 — 모델이 푼 값과, 그것을 그리는 확대도의 일치.

연마는 세 가지가 **동시에** 맞아야 성립한다 — 동력이 스핀들 정격 안에 들고,
칩두께가 어느 영역에 서는지가 정해지고, 세 면의 점유가 AFR 정반 점유 안에 든다.
그래서 여기서 보는 것도 셋이다.

1. **수** — 닫힌식으로 검산되는 것은 닫힌식으로 견준다(주속·제거율·동력·칩두께).
   그리고 다른 모듈이 이미 정해 둔 값(`campaign` 의 이송·점유, `afr` 의 유리
   두께)을 이 모듈이 **다시 정하지 않는지**를 본다.
2. **형상** — 그리는 다각형의 면적이 계산한 면적과 같은지. 연마 전 단면에서
   연마 후 단면을 뺀 값이 제거 단면적과 같아야 한다. 어긋나면 화면이 모델과
   다른 것을 그리고 있다는 뜻이다.
3. **파생본** — 커밋된 확대도가 생성기 출력과 같고, 화면에 손으로 쓴 수가 없고,
   아티팩트 변환기가 받아들이는 문서인지.

기구가 **실제로 도는지**는 글자로 볼 수 없다. 그것은
`node tools/check_sg_closeup.mjs` 가 브라우저로 잰다.
"""

from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, campaign, sg_grind

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLOSEUP = ROOT / "docs/drawings/pv-sg-closeup.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGrindingNumbers(unittest.TestCase):
    """닫힌식으로 검산되는 것은 닫힌식으로 견준다."""

    def test_wheel_speed_is_pi_d_n(self):
        want = math.pi * sg_grind.WHEEL_D_MM * sg_grind.SPINDLE_RPM / 60_000.0
        self.assertAlmostEqual(sg_grind.wheel_speed_m_s(), want, places=3)
        # 유리 연삭의 통상 주속대 안에 있어야 휠 선정이 말이 된다.
        self.assertTrue(20.0 <= sg_grind.wheel_speed_m_s() <= 35.0)

    def test_removal_rate_is_area_times_feed(self):
        for feed in (sg_grind.long_feed_mm_s(), sg_grind.short_feed_mm_s()):
            self.assertAlmostEqual(sg_grind.removal_rate_mm3_s(feed),
                                   sg_grind.removal_area_mm2() * feed, places=4)

    def test_power_is_specific_energy_times_rate(self):
        feed = sg_grind.long_feed_mm_s()
        self.assertAlmostEqual(
            sg_grind.cutting_power_w(feed),
            sg_grind.SPECIFIC_ENERGY_J_MM3 * sg_grind.removal_rate_mm3_s(feed), places=1)

    def test_the_max_feed_is_the_feed_that_uses_the_whole_spindle(self):
        """한계 이송에서 이용률이 정확히 1 이어야 한다 — 두 식이 같은 것을 푼다."""
        self.assertAlmostEqual(sg_grind.utilisation(sg_grind.max_feed_mm_s()), 1.0, places=3)

    def test_the_design_pass_is_bound_by_the_spindle_not_the_conveyor(self):
        """설계 300 mm/s 가 스핀들 한계 바로 밑이라는 것 — 이 도면의 결론 하나."""
        self.assertLess(sg_grind.utilisation(sg_grind.long_feed_mm_s()), 1.0)
        self.assertTrue(sg_grind.feed_is_spindle_bound())
        self.assertGreater(sg_grind.max_feed_mm_s(), sg_grind.long_feed_mm_s())

    def test_the_short_sweep_has_more_headroom_than_the_long_pass(self):
        """이송이 느리면 이용률도 낮다 — 단조성이 깨지면 어딘가 틀린 것이다."""
        self.assertLess(sg_grind.short_feed_mm_s(), sg_grind.long_feed_mm_s())
        self.assertLess(sg_grind.utilisation(sg_grind.short_feed_mm_s()),
                        sg_grind.utilisation(sg_grind.long_feed_mm_s()))

    def test_the_stalling_specific_energy_is_where_utilisation_hits_one(self):
        e = sg_grind.specific_energy_that_stalls()
        feed = sg_grind.long_feed_mm_s()
        got = e * sg_grind.removal_rate_mm3_s(feed) / sg_grind.spindle_available_w()
        self.assertAlmostEqual(got, 1.0, places=3)
        self.assertGreater(e, sg_grind.SPECIFIC_ENERGY_J_MM3)

    def test_chip_thickness_is_depth_times_speed_ratio(self):
        feed = sg_grind.long_feed_mm_s()
        # 속도비는 소수 첫째 자리로 반올림해 내놓으므로 그만큼 느슨하게 본다.
        want = sg_grind.equivalent_depth_mm() / sg_grind.speed_ratio(feed)
        self.assertAlmostEqual(sg_grind.chip_thickness_mm(feed), want, places=6)

    def test_the_cut_is_brittle_so_the_arris_is_not_optional(self):
        """칩두께가 연성한계를 크게 넘는다 — 그래서 모따기가 필수다."""
        self.assertGreater(sg_grind.brittleness_ratio(sg_grind.long_feed_mm_s()), 5.0)
        self.assertTrue(sg_grind.is_brittle(sg_grind.long_feed_mm_s()))
        self.assertTrue(sg_grind.arris_is_required())
        self.assertGreaterEqual(sg_grind.ARRIS_COUNT, 1)

    def test_the_ductile_limit_is_bifano(self):
        e, h = sg_grind.GLASS_E_GPA * 1e9, sg_grind.GLASS_H_GPA * 1e9
        kc = sg_grind.GLASS_KC_MPA_M05 * 1e6
        want = 0.15 * (e / h) * (kc / h) ** 2 * 1_000.0
        self.assertAlmostEqual(sg_grind.ductile_limit_mm(), want, places=8)

    def test_forces_follow_from_power_and_wheel_speed(self):
        feed = sg_grind.long_feed_mm_s()
        self.assertAlmostEqual(
            sg_grind.tangential_force_n(feed),
            sg_grind.cutting_power_w(feed) / sg_grind.wheel_speed_m_s(), places=2)
        self.assertAlmostEqual(
            sg_grind.normal_force_n(feed),
            sg_grind.tangential_force_n(feed) / sg_grind.FORCE_RATIO, places=1)

    def test_the_arris_eats_most_of_the_removal_area(self):
        """모따기 삼각형이 끝면 살보다 크다 — 동력을 무엇이 먹는지의 답."""
        self.assertGreater(sg_grind.arris_share(), 0.5)
        self.assertAlmostEqual(
            sg_grind.arris_share(),
            sg_grind.ARRIS_COUNT * sg_grind.ARRIS_MM ** 2 / 2
            / sg_grind.removal_area_mm2(), places=4)

    def test_the_relief_covers_the_height_tolerance(self):
        """도피가 세팅 공차보다 커야 어느 쪽으로 틀려도 유리대가 다 갈린다."""
        self.assertTrue(sg_grind.relief_covers_tolerance())
        self.assertGreater(sg_grind.GROOVE_RELIEF_MM, sg_grind.HEIGHT_TOL_MM)
        self.assertAlmostEqual(sg_grind.eva_skim_mm(),
                               sg_grind.GROOVE_RELIEF_MM + sg_grind.HEIGHT_TOL_MM)

    def test_the_wheel_wear_budget_implies_a_grinding_ratio(self):
        """4 개월 주기를 뒤집으면 벤더에게 물어야 할 연삭비가 나온다."""
        g = sg_grind.implied_g_ratio()
        self.assertGreater(g, 100)
        self.assertLess(sg_grind.radial_wear_um_per_panel(), 5.0)
        # 마모가 빠를수록 요구 연삭비가 커진다 — 두 값이 같은 것을 본다.
        worst = max(sg_grind.long_edge_mm(), sg_grind.short_edge_mm())
        total = sg_grind.glass_volume_per_panel_mm3(worst) * sg_grind.panels_per_service()
        self.assertEqual(g, round(total / sg_grind.wheel_wear_volume_mm3()))


class TestValuesComeFromOtherModules(unittest.TestCase):
    """이 모듈이 이미 정해진 값을 다시 정하지 않는지."""

    def test_the_feeds_are_the_campaign_feeds(self):
        self.assertEqual(sg_grind.long_feed_mm_s(), float(campaign.SG_PASS_MM_S))
        self.assertEqual(sg_grind.short_feed_mm_s(), float(campaign.SG_SWEEP_MM_S))

    def test_the_glass_thickness_is_the_afr_laminate(self):
        self.assertEqual(sg_grind.GLASS_T_MM, float(afr.LAMINATE_T_MM))

    def test_the_occupancy_agrees_with_the_campaign_model(self):
        """상(相)을 하나씩 세어 더한 값이 캠페인의 점유식과 같아야 한다."""
        self.assertAlmostEqual(sg_grind.occupancy_s(), campaign.sg_occupancy_s(), places=2)

    def test_the_spindle_count_matches_the_heads(self):
        self.assertEqual(sg_grind.SPINDLE_COUNT,
                         sg_grind.LONG_HEADS + sg_grind.SHORT_HEADS)


class TestTheCycleIsSequential(unittest.TestCase):
    """장변과 단변은 왜 동시에 못 하는가 — 모델이 그것을 값으로 말한다."""

    def test_the_phases_do_not_overlap(self):
        t = 0.0
        for phase in sg_grind.cycle():
            self.assertAlmostEqual(float(phase["start"]), t, places=3)
            t = float(phase["end"])
        self.assertAlmostEqual(t, sg_grind.occupancy_s(), places=2)

    def test_no_phase_runs_both_kinds_of_head(self):
        """한 상에서 도는 헤드는 장변 2 대이거나 단변 1 대이거나 없다 — 섞이지 않는다."""
        for phase in sg_grind.cycle():
            self.assertIn(phase["heads"], (0, sg_grind.SHORT_HEADS, sg_grind.LONG_HEADS))
            if phase["heads"] == sg_grind.LONG_HEADS:
                self.assertEqual(phase["motion"], f"이송 {sg_grind.long_feed_mm_s():.0f} mm/s")
            elif phase["heads"] == sg_grind.SHORT_HEADS:
                self.assertEqual(phase["motion"], "정지")

    def test_motion_state_is_what_separates_them(self):
        """장변 상은 유리가 움직이고 단변 상은 선다 — 두 상태가 배타적이다."""
        moving = {p["phase"] for p in sg_grind.cycle() if p["motion"] != "정지"}
        stopped = {p["phase"] for p in sg_grind.cycle() if p["motion"] == "정지"}
        self.assertEqual(moving, {"장변 통과"})
        self.assertTrue({"앞단변", "뒷단변"} <= stopped)

    def test_sequential_costs_exactly_the_shorter_of_the_two(self):
        self.assertAlmostEqual(
            sg_grind.occupancy_s(),
            sg_grind.simultaneous_occupancy_s() + sg_grind.sequential_cost_s(), places=2)
        self.assertGreater(sg_grind.sequential_cost_s(), 0.0)

    def test_sequential_still_fits_inside_the_afr_platen(self):
        """순차로 풀어도 택트가 안 깎이는 근거 — 그것이 여유다."""
        self.assertTrue(sg_grind.sequential_is_affordable())
        self.assertTrue(campaign.sg_fits_the_exit_roller())
        self.assertAlmostEqual(sg_grind.slack_s(),
                               float(campaign.AFR_S) - sg_grind.occupancy_s(), places=2)


class TestTheDrawnSectionIsTheCalculatedSection(unittest.TestCase):
    """그리는 다각형과 계산한 면적이 어긋나면 화면이 모델과 다른 것을 그린다."""

    def test_the_removed_polygon_has_the_removal_area(self):
        self.assertAlmostEqual(sg_grind.polygon_area_mm2(sg_grind.removed_outline()),
                               sg_grind.removal_area_mm2(), places=6)

    def test_before_minus_after_is_the_removal_area(self):
        before = sg_grind.polygon_area_mm2(sg_grind.edge_outline_before())
        after = sg_grind.polygon_area_mm2(sg_grind.edge_outline_after())
        self.assertAlmostEqual(before - after, sg_grind.removal_area_mm2(), places=6)

    def test_the_wheel_rim_polygon_has_the_solid_area(self):
        self.assertAlmostEqual(sg_grind.polygon_area_mm2(sg_grind.wheel_groove_outline()),
                               sg_grind.groove_solid_mm2(), places=6)

    def test_the_flange_clears_the_laminate(self):
        """어깨가 하나뿐이라 유리 밑 라미네이트를 안 문다 — 형상에서 읽는다."""
        self.assertTrue(sg_grind.flange_clears_laminate())

    def test_the_ground_edge_carries_the_arris(self):
        """연마 후 단면에 45° 모따기가 실제로 있는지 — 점을 세어 본다."""
        after = sg_grind.edge_outline_after()
        legs = [(round(abs(b[0] - a[0]), 4), round(abs(b[1] - a[1]), 4))
                for a, b in zip(after, after[1:] + after[:1])]
        self.assertIn((sg_grind.ARRIS_MM, sg_grind.ARRIS_MM), legs)

    def test_every_outline_is_a_simple_closed_polygon(self):
        for name in ("edge_outline_before", "edge_outline_after", "removed_outline",
                     "wheel_groove_outline"):
            pts = getattr(sg_grind, name)()
            with self.subTest(name):
                self.assertGreaterEqual(len(pts), 4)
                self.assertEqual(len(set(pts)), len(pts))   # 겹치는 점이 없어야 한다
                self.assertGreater(sg_grind.polygon_area_mm2(pts), 0.0)


class TestUnits(unittest.TestCase):
    """확대도가 그리는 세 유닛."""

    def test_there_are_three_units(self):
        keys = [u.key for u in sg_grind.units()]
        self.assertEqual(keys, ["long", "short", "contact"])

    def test_every_unit_has_five_steps_and_parts(self):
        for u in sg_grind.units():
            with self.subTest(u.key):
                self.assertEqual(len(u.principle), 5)
                self.assertTrue(u.parts)
                self.assertTrue(u.sheet.startswith("PV-SG-"))
                self.assertIn(u.key, sg_grind.VIEW_DIR)

    def test_every_part_carries_a_role_and_a_material(self):
        for u in sg_grind.units():
            for p in u.parts:
                with self.subTest(f"{u.key}/{p.key}"):
                    self.assertTrue(p.role.strip())
                    self.assertTrue(p.material.strip())
                    self.assertGreaterEqual(p.qty, 1)

    def test_the_head_standoff_is_the_wheel_radius(self):
        """대기 자리가 눈대중이 아니라 휠 반경에서 나온다."""
        self.assertEqual(sg_grind.contact_standoff_mm(), sg_grind.WHEEL_D_MM / 2)
        self.assertEqual(sg_grind.head_park_mm(),
                         sg_grind.contact_standoff_mm() + sg_grind.INFEED_STROKE_MM)

    def test_the_rollers_stop_short_of_the_edge(self):
        """롤러가 변까지 뻗으면 휠과 부딪친다 — 내밀린 길이가 있어야 한다."""
        roll = [p for p in sg_grind.long_unit().parts if p.key == "roll"][0]
        self.assertAlmostEqual(roll.size[1],
                               campaign.PANEL_WIDTH_MM - 2 * sg_grind.EDGE_OVERHANG_MM)
        self.assertLess(roll.size[1], campaign.PANEL_WIDTH_MM)
        self.assertGreater(sg_grind.EDGE_OVERHANG_MM, sg_grind.WHEEL_D_MM / 2 * 0.5)

    def test_the_long_unit_has_two_heads_and_the_short_one(self):
        wheels = {u.key: [p for p in u.parts if p.key.endswith("whl")]
                  for u in sg_grind.units()}
        self.assertEqual(wheels["long"][0].qty, sg_grind.LONG_HEADS)
        self.assertEqual(wheels["short"][0].qty, sg_grind.SHORT_HEADS)


class TestCloseupDrawing(unittest.TestCase):
    """커밋된 확대도가 생성기 출력과 같고, 화면에 손으로 쓴 수가 없는지."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_sg_closeup")
        cls.html = CLOSEUP.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "PYTHONPATH=src python tools/build_sg_closeup.py 를 다시 돌릴 것")

    def test_it_is_derived_from_the_plant(self):
        self.assertIn("tools/build_sg_closeup.py", self.html)
        self.assertIn("<title>SG-301 연마 작동 확대도</title>", self.html)
        self.assertNotIn("<title>태양광 전처리 통합 플랜트</title>", self.html)

    def test_the_payload_is_the_model(self):
        units = json.loads(self.builder.unit_payload())
        self.assertEqual([u["key"] for u in units], ["long", "short", "contact"])
        for got, want in zip(units, sg_grind.units()):
            self.assertEqual(got["sheet"], want.sheet)
            self.assertEqual(len(got["parts"]), len(want.parts))
            self.assertEqual(got["view"], list(sg_grind.VIEW_DIR[want.key]))
        self.assertEqual(units[2]["mag"], sg_grind.CONTACT_MAG)

    def test_the_cycle_payload_is_the_model_cycle(self):
        cyc = json.loads(self.builder.cycle_payload())
        self.assertEqual([p["phase"] for p in cyc["phases"]],
                         [p["phase"] for p in sg_grind.cycle()])
        self.assertEqual(cyc["total"], sg_grind.occupancy_s())
        self.assertEqual(cyc["simultaneous"], sg_grind.simultaneous_occupancy_s())
        self.assertEqual(cyc["slack"], sg_grind.slack_s())
        self.assertEqual(cyc["afr"], float(campaign.AFR_S))

    def test_the_drawn_polygons_are_the_model_polygons(self):
        for name, fn in (("polyBefore", sg_grind.edge_outline_before),
                         ("polyAfter", sg_grind.edge_outline_after),
                         ("polyRemoved", sg_grind.removed_outline),
                         ("polyWheel", sg_grind.wheel_groove_outline)):
            with self.subTest(name):
                marker = json.dumps([list(p) for p in fn()], separators=(",", ":"))
                self.assertIn(marker, self.html)

    def test_the_headline_numbers_reach_the_page(self):
        for text in (f"{sg_grind.wheel_speed_m_s()} m/s",
                     f"{sg_grind.removal_area_mm2()} mm",
                     f"{sg_grind.max_feed_mm_s():.0f} mm/s",
                     f"{sg_grind.occupancy_s()} s",
                     f"{sg_grind.implied_g_ratio():,}"):
            with self.subTest(text):
                self.assertIn(text, self.html)

    def test_the_row_pitch_comes_from_the_model(self):
        """줄 간격이 화면에 손으로 박혀 있으면 모델이 바뀌어도 안 따라온다."""
        self.assertIn(json.dumps(sg_grind.ROW_PITCH_MM, separators=(",", ":")), self.html)

    def test_the_console_is_wired(self):
        for ident in ("sg-cu-tabs", "sg-cu-band", "sg-cu-rows", "sg-cu-spec",
                      "sg-cu-principle", "sg-cu-step", "__pvSgCloseup"):
            with self.subTest(ident):
                self.assertIn(ident, self.html)

    def test_shadows_and_casing_are_off(self):
        """부품을 보는 화면이므로 바닥 그림자와 외장은 걷는다."""
        self.assertIn("Dt.shadowMap.enabled=!1;", self.html)
        self.assertNotIn("Dt.shadowMap.enabled=!0;", self.html)
        self.assertNotIn('id="pv-case" type="checkbox" checked', self.html)

    def test_the_builder_is_idempotent_and_anchored(self):
        """앵커가 한 곳이 아니면 멈춰야 한다 — 원본이 바뀌면 조용히 낡지 않는다."""
        with self.assertRaises(SystemExit):
            self.builder._once("a b a", "a", "x", "두 곳")
        with self.assertRaises(SystemExit):
            self.builder._once("b", "a", "x", "없음")

    def test_the_artifact_converter_takes_it(self):
        art = _load("build_artifact")
        self.assertIn("sg-closeup", art.TARGETS)
        src, out = art.TARGETS["sg-closeup"]
        self.assertEqual(src, pathlib.Path("docs/drawings/pv-sg-closeup.html"))
        body = art.to_artifact(self.html) if hasattr(art, "to_artifact") else None
        if body is not None:
            self.assertNotIn("<html", body.lower())
            self.assertIn("<title>", body)
        self.assertTrue(str(out).endswith("pv-sg-closeup-artifact.html"))


if __name__ == "__main__":
    unittest.main()
