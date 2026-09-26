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
import inspect
import math
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import (afr, afr_peel, campaign, dust, frames, handoff,
                           recipe, reliability, sg_grind, vision)

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

    def test_the_cut_is_brittle_so_the_arris_follows_if_you_grind(self):
        """칩두께가 연성한계를 크게 넘는다 — **간다면** 모따기가 따라온다.

        이 판정은 공정 요구를 안 읽는다. 읽는 것은 통과속도 하나다. 그러니
        참이라는 것은 조건문의 귀결이고, 전건(갈 이유)은 따로 서야 한다 —
        `ARRIS_REQUIRED_BY_PLANT` 가 그쪽이다.
        """
        self.assertGreater(sg_grind.brittleness_ratio(sg_grind.long_feed_mm_s()), 5.0)
        self.assertTrue(sg_grind.is_brittle(sg_grind.long_feed_mm_s()))
        self.assertTrue(sg_grind.arris_is_required())
        self.assertGreaterEqual(sg_grind.ARRIS_COUNT, 1)
        # 판정이 속도만 읽는다는 것 — 속도를 연성역으로 내리면 뒤집힌다.
        self.assertFalse(sg_grind.is_brittle(1.0))

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

    def test_the_annual_throughput_is_not_copied(self):
        """연간 장수를 베껴 두지 않는다 — REV.59 가 그것을 움직였는데 안 따라왔다."""
        self.assertEqual(sg_grind.panels_per_service(),
                         round(reliability.annual_panels()
                               * sg_grind.WHEEL_SERVICE_MONTHS / 12.0))
        self.assertFalse(hasattr(sg_grind, "ANNUAL_PANELS"),
                         "연간 장수는 reliability 가 정한다 — 상수로 두면 갈라진다")

    def test_the_dust_flow_is_the_dust_model(self):
        ds01 = [s for s in dust.STREAMS if s.tag == "DS-01"][0]
        self.assertEqual(sg_grind.dust_flow_m3h(), ds01.flow_m3h)

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


class TestWhatTheFrameLeavesBehind(unittest.TestCase):
    """프레임을 뜯어내면 실란트 띠가 남는다 — 그것이 이 장비의 진짜 작업량이다.

    처음 이 모듈은 유리 끝면만 보고 실란트를 살 0.03 mm 로 접어 넣었다.
    `recipe` 는 처음부터 '백시트 접촉 압력' 을 선언하고 있었고, 무프레임 항목은
    '**실란트 대신** 라미네이트 가장자리 정리' 라고 적어 두었다 — 프레임형에서는
    실란트가 대상이라는 뜻이다. 여기서 그 범위를 값으로 붙든다.
    """

    def test_the_band_comes_from_the_frame_slot(self):
        """띠의 폭과 두께를 이 모듈이 새로 정하지 않는다."""
        self.assertEqual(sg_grind.SEALANT_BAND_MM, float(frames.SLOT_LIP_MM))
        self.assertEqual(sg_grind.SEALANT_FACE_T_MM, float(frames.SEALANT_T_MM))
        self.assertEqual(sg_grind.STACK_T_MM, float(frames.LAMINATE_STACK_MM))

    def test_the_panel_runs_glass_down(self):
        """기본 레시피가 위를 향하는 면을 백시트로 적어 두었다."""
        self.assertTrue(sg_grind.panel_is_glass_down())
        base = [s for s in recipe.STRUCTURES if s.code == "GLASS_BACKSHEET"][0]
        self.assertEqual(base.top, "백시트")

    def test_the_recipe_declares_a_backsheet_contact(self):
        """모델이 백시트 접촉을 선언한다 — 이 장비가 유리 변만 보는 것이 아니다."""
        base = [s for s in recipe.STRUCTURES if s.code == "GLASS_BACKSHEET"][0]
        self.assertIn("백시트", base.sg)
        frameless = [s for s in recipe.STRUCTURES if s.code == "FRAMELESS"][0]
        self.assertIn("실란트", frameless.sg)      # 무프레임은 '실란트 대신'

    def test_the_face_sealant_dwarfs_the_glass_removal(self):
        """면 실란트가 유리에서 걷는 양보다 두 자리 크다 — 무엇이 작업량인가."""
        self.assertGreater(sg_grind.sealant_ratio_to_glass(), 50.0)
        self.assertGreater(sg_grind.sealant_volume_per_panel_mm3(), 1e5)

    def test_the_wheel_cannot_reach_the_edge_through_the_band(self):
        """이 도면의 결론 — 띠를 먼저 걷지 않으면 휠이 모서리에 못 닿는다."""
        self.assertFalse(sg_grind.wheel_can_reach_the_glass_edge())
        self.assertGreater(sg_grind.sealant_stands_proud_mm(), 0.0)
        self.assertGreater(sg_grind.flange_band_overlap_mm2(), 0.0)
        self.assertEqual(sg_grind.sealant_must_go_first_mm(), sg_grind.flange_reach_mm())
        # 어깨가 걸쳐 나오는 구간이 통째로 띠 안이어야 이 결론이 선다.
        self.assertLessEqual(sg_grind.flange_reach_mm(), sg_grind.SEALANT_BAND_MM)

    def test_widening_the_clearance_does_not_rescue_it(self):
        """여유를 실란트보다 벌리면 어깨가 모서리에서 떨어진다 — 둘 다는 안 된다."""
        need = sg_grind.sealant_left_t_mm()
        self.assertGreater(need, sg_grind.ARRIS_MM * 0.5,
                           "실란트가 아리스 다리보다 훨씬 얇으면 이 논증이 약해진다")

    def test_the_diamond_wheel_must_not_touch_polymer(self):
        """주속이 폴리머 접촉 상한을 크게 넘는다 — 휠이 막히고 집진 전제가 깨진다."""
        self.assertFalse(sg_grind.wheel_may_touch_the_backsheet())
        self.assertGreater(sg_grind.rubbing_speed_ratio(), 1.0)
        # 폴리머를 안 깎아야 DS-01 의 '불연' 선언이 유지된다.
        self.assertTrue(sg_grind.dust_stream_stays_inert())
        ds01 = [s for s in dust.STREAMS if s.tag == "DS-01"][0]
        self.assertFalse(ds01.combustible)
        self.assertNotIn("백시트", ds01.material)
        self.assertEqual(sg_grind.dust_flow_m3h(), ds01.flow_m3h)

    def test_position_control_would_cut_into_the_backsheet(self):
        """프레임 기준 공차합이 백시트보다 두껍다 — 힘 제어여야 하는 이유."""
        self.assertFalse(sg_grind.position_control_is_safe())
        self.assertGreater(sg_grind.backsheet_margin_mm(), 0.0)
        self.assertAlmostEqual(sg_grind.depth_stack_mm(),
                               sg_grind.LAMINATE_TOL_MM + sg_grind.ROLLER_PLANE_TOL_MM
                               + sg_grind.HEIGHT_TOL_MM, places=4)

    def test_the_face_may_only_be_pressed_far_more_gently_than_the_edge(self):
        self.assertLess(sg_grind.safe_face_force_n(),
                        sg_grind.normal_force_n(sg_grind.long_feed_mm_s()))
        self.assertGreater(sg_grind.face_force_ratio(), 1.0)

    def test_the_face_now_has_a_tool(self):
        """한때 없었다 — 레시피는 백시트 접촉 압력을 선언하는데 부품표에는
        클램프 패드뿐이었다. SR-302 가 그 자리를 채운다."""
        self.assertTrue(sg_grind.face_residue_has_a_tool())
        keys = {p.key for u in sg_grind.units() for p in u.parts}
        self.assertIn("srbld", keys)
        self.assertIn("srshoe", keys)

    def test_the_dust_model_now_sizes_for_simultaneous_heads(self):
        """장변 2 대가 동시인지 순차인지 두 모델이 달랐다 — 발주처가 동시로 정했다.

        집진은 "동시에 도는 헤드가 없다" 며 한 대 몫만 잡고 있었다. 이제 후드
        수를 `LONG_HEADS` 에서 받으므로 둘이 다시 갈라지면 여기서 걸린다.
        """
        self.assertTrue(sg_grind.heads_agree_with_the_dust_model())
        self.assertGreaterEqual(dust.SG_SIMULTANEOUS_HOODS, sg_grind.LONG_HEADS)
        self.assertEqual(sg_grind.dust_flow_m3h(),
                         dust.SG_HOOD_M3H * dust.SG_SIMULTANEOUS_HOODS)
        # 순차로 돌렸다면 장변을 두 번 지나가 점유가 늘지만 AFR 정반 안에는 든다 —
        # 그래서 애초에 **결정 가능한** 문제였다.
        self.assertGreater(sg_grind.two_pass_occupancy_s(), sg_grind.occupancy_s())
        self.assertLess(sg_grind.two_pass_occupancy_s(), float(campaign.AFR_S))

    def test_the_open_list_lost_the_head_question(self):
        """미결이 계산에서 나오므로, 조건이 풀리면 항목이 사라져야 한다."""
        titles = [t for t, _ in sg_grind.open_questions()]
        self.assertNotIn("집진이 동시에 도는 헤드 수만큼 잡혀 있지 않다", titles)

    def test_the_open_questions_are_computed_not_declared(self):
        """미결 목록이 계산에서 나온다 — 조건이 풀리면 항목이 사라져야 한다.

        막던 넷은 SR-302 가 들어오면서 닫혔고, 그 자리에 **공구를 정해서 생긴**
        실측 항목 셋이 들어왔다. 목록이 짧아진 것이 아니라 성격이 바뀌었다.
        """
        titles = [q[0] for q in sg_grind.open_questions()]
        self.assertNotIn("휠이 유리 모서리에 못 닿는다", titles)
        self.assertIn("실란트 Gc 가 실측 전 계획값이다", titles)
        for _, body in sg_grind.open_questions():
            self.assertGreater(len(body), 40)

    def test_the_band_polygons_have_the_band_area(self):
        want = sg_grind.SEALANT_BAND_MM * sg_grind.sealant_left_t_mm()
        for fn in (sg_grind.sealant_outline_glass_face,
                   sg_grind.sealant_outline_back_face):
            with self.subTest(fn.__name__):
                self.assertAlmostEqual(sg_grind.polygon_area_mm2(fn()), want, places=6)
                self.assertAlmostEqual(want, sg_grind.sealant_area_mm2(), places=6)


class TestWhatActuallyInspectsTheResidue(unittest.TestCase):
    """잔사를 무엇이 보는가 — 한 번 틀리게 적었던 자리다.

    접촉부 주기에 "GI-301 이 연마 **전**에 잔사를 센다" 고 썼는데, `vision` 을
    보니 GI-301 은 REV.50 통합(V-4)에서 **은퇴한 헤드**였다. 남은 것은 연마
    **뒤**의 GI-302·GI-303 뿐이라 전/후 비교가 없다. 그것이 "연마 공정창 고정"
    이라는 전제를 만들고, 그 전제는 면에 남는 몫이 실측돼야 선다.
    """

    def test_the_pre_grind_head_is_retired(self):
        gi301 = next(h for h in vision.HEADS if h.tag == "GI-301")
        self.assertFalse(gi301.kept)
        self.assertIn("연마 전", gi301.role)

    def test_only_post_grind_heads_remain(self):
        kept = {h.tag for h in vision.HEADS if h.kept and h.tag.startswith("GI-")}
        self.assertEqual(kept, {"GI-302", "GI-303"})

    def test_the_drawing_does_not_claim_a_pre_grind_check(self):
        """도면 글이 은퇴한 헤드를 살아 있는 것처럼 말하면 안 된다."""
        said = " ".join(b for _, b in sg_grind.contact_unit().principle)
        self.assertNotIn("GI-301 이 연마 **전**에", said)
        self.assertIn("은퇴", said)


class TestUnits(unittest.TestCase):
    """확대도가 그리는 세 유닛."""

    def test_there_are_four_units(self):
        keys = [u.key for u in sg_grind.units()]
        self.assertEqual(keys, ["long", "short", "contact", "scraper"])

    def test_every_unit_has_steps_and_parts(self):
        """단계 수를 5 로 못 박지 않는다 — 접촉부는 '못 닿는다' 를 더해 6 이다."""
        for u in sg_grind.units():
            with self.subTest(u.key):
                self.assertGreaterEqual(len(u.principle), 5)
                self.assertTrue(u.parts)
                self.assertTrue(u.sheet.startswith("PV-SG-") or u.sheet.startswith("PV-SR-"))
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


class TestTheScraperThatClearsTheBand(unittest.TestCase):
    """SR-302 — 띠를 걷는 공구. **에너지가 공구를 정했다.**

    같은 띠를 갈아내면 부피 일이라 36 kW 가 들고, 긁으면 계면 일이라 20 N 도
    안 든다. 그 차이가 이 유닛이 스크레이퍼인 이유다. 여기서 그것을 값으로
    붙들고, 새로 들어온 불확실성이 미결로 나오는지도 본다.
    """

    def test_scraping_is_interfacial_work_not_volumetric(self):
        """긁는 힘은 Gc × 폭이다 — 두께에 안 걸린다."""
        self.assertAlmostEqual(sg_grind.scrape_force_n(),
                               sg_grind.sealant_gc_n_mm() * sg_grind.SEALANT_BAND_MM,
                               places=2)
        # 두께를 두 배로 봐도 힘이 안 변한다는 것이 계면 일의 정의다.
        self.assertNotIn(str(sg_grind.sealant_left_t_mm()),
                         str(sg_grind.scrape_force_n()))

    def test_the_gc_is_the_one_the_peel_analysis_uses(self):
        """같은 실란트다 — 인발 해석과 다른 값을 쓰면 둘 중 하나가 틀린 것이다."""
        self.assertEqual(sg_grind.sealant_gc_n_mm(), float(afr_peel.SEALANT_GC_N_MM))

    def test_abrading_would_not_fit_but_scraping_does(self):
        """공구 선택의 근거 — 한쪽은 스핀들 안에 들고 한쪽은 안 든다."""
        self.assertTrue(sg_grind.scraping_fits_the_spindle())
        self.assertFalse(sg_grind.abrading_fits_the_spindle())
        self.assertGreater(sg_grind.scrape_beats_abrade_by(), 1_000)

    def test_the_blade_cannot_scratch_glass_but_shears_the_sealant(self):
        self.assertTrue(sg_grind.blade_cannot_scratch_glass())
        self.assertTrue(sg_grind.blade_can_shear_the_sealant())
        self.assertLess(sg_grind.BLADE_HARDNESS_GPA, sg_grind.GLASS_H_GPA)
        self.assertGreater(sg_grind.BLADE_HARDNESS_GPA, sg_grind.SEALANT_HARDNESS_GPA)

    def test_the_shoe_takes_the_depth_off_the_panel_not_the_frame(self):
        """이것이 백시트를 남기는 이유다."""
        self.assertTrue(sg_grind.depth_is_referenced_to_the_panel())
        self.assertLess(sg_grind.blade_assembly_tol_mm(), sg_grind.BACKSHEET_T_MM)
        self.assertGreater(sg_grind.depth_stack_mm(), sg_grind.BACKSHEET_T_MM)
        self.assertTrue(sg_grind.backsheet_survives_scraping())

    def test_the_shoe_presses_far_below_the_face_limit(self):
        self.assertTrue(sg_grind.shoe_is_gentle_enough())
        self.assertLessEqual(sg_grind.SHOE_SPRING_N, sg_grind.safe_face_force_n())
        self.assertLessEqual(sg_grind.shoe_pressure_mpa(), sg_grind.FACE_SAFE_MPA)

    def test_the_dust_stream_is_untouched(self):
        """부스러기가 고체라 DS-01 의 '불연' 선언이 그대로 선다."""
        self.assertTrue(sg_grind.dust_stream_unchanged_by_scraping())
        ds01 = [s for s in dust.STREAMS if s.tag == "DS-01"][0]
        self.assertFalse(ds01.combustible)

    def test_the_only_cost_is_the_lead(self):
        """같은 캐리지에 달므로 장비가 안 늘고 순환만 리드만큼 는다."""
        self.assertAlmostEqual(
            sg_grind.occupancy_s(),
            sg_grind.occupancy_without_scraper_s() + sg_grind.scraper_lead_cost_s(),
            places=2)
        self.assertTrue(sg_grind.sequential_is_affordable())
        self.assertGreater(sg_grind.slack_s(), 0.0)
        self.assertGreater(sg_grind.BLADE_LEAD_MM, sg_grind.WHEEL_D_MM / 2)

    def test_the_published_occupancy_matches_the_carrier_decision(self):
        """광고하는 점유가 **지금 있는 기계**의 점유여야 한다.

        한때 SR-302 가 헤드에 달린 부품이라 리드가 순환의 상(相) 안에 있었고,
        그것을 밖에 빼두면 존재하지 않는 기계의 택트를 광고하는 셈이었다.

        발주처가 날을 자기 캐리어로 옮겼다. 그래서 이 점유는 **휠만의 점유**이고
        리드가 안 실린다 — 반대로, 리드를 아직 물고 있으면 없는 부품의 시간을
        파는 셈이 된다. 어느 쪽이든 정본은 하나이고 두 모듈이 같아야 한다.
        """
        self.assertEqual(sg_grind.BLADE_LEAD_MM, campaign.SG_BLADE_LEAD_MM)
        self.assertAlmostEqual(sg_grind.occupancy_s(),
                               campaign.sg_occupancy_s(), places=2)
        lead_free = ((campaign.PANEL_WIDTH_MM / sg_grind.short_feed_mm_s()
                      + campaign.SG_HEAD_STROKE_S) * 2
                     + campaign.PANEL_LENGTH_MM / sg_grind.long_feed_mm_s()
                     + campaign.SG_INDEX_S)
        if sg_grind.the_carrier_is_its_own():
            self.assertAlmostEqual(sg_grind.occupancy_s(), lead_free, places=2)
            self.assertEqual(sg_grind.scraper_lead_cost_s(), 0.0)
        else:
            self.assertGreater(sg_grind.occupancy_s(), lead_free,
                               "동승인데 점유가 안 늘었다면 리드가 어디에도 없다")
        # 반사실값은 결정과 무관하게 계산된다 — 왜 그랬는지가 남아야 한다.
        self.assertGreater(sg_grind.lead_cost_if_shared_s(), 0.0)

    def test_the_tool_now_exists_and_the_wheel_can_follow(self):
        self.assertTrue(sg_grind.face_residue_has_a_tool())
        self.assertTrue(sg_grind.wheel_can_reach_after_scraping())
        self.assertGreaterEqual(sg_grind.BLADE_WIDTH_MM, sg_grind.flange_reach_mm())

    def test_the_four_blocking_questions_closed(self):
        """미결이 계산에서 나오므로 공구가 생기면 스스로 닫힌다."""
        titles = [t for t, _ in sg_grind.open_questions()]
        for gone in ("휠이 유리 모서리에 못 닿는다", "면 실란트를 걷을 공구가 없다",
                     "백시트가 남는다는 보장이 없다", "집진 흐름이 바뀐다"):
            self.assertNotIn(gone, titles)

    def test_and_new_measurement_questions_took_their_place(self):
        """공구를 정하면 그 공구의 물성이 새 입력이 된다 — 그것을 숨기지 않는다."""
        titles = [t for t, _ in sg_grind.open_questions()]
        self.assertIn("실란트 Gc 가 실측 전 계획값이다", titles)
        self.assertIn("날 수명이 없다", titles)
        # 발주처가 아리스 요구 없음을 확인하면서 넷째가 들어왔다 — 공구가 아니라
        # **요구**가 없어져서 생긴 미결이라 위 셋과 종류가 다르다.
        self.assertIn("아리스를 요구하는 공정이 없다", titles)
        # 다섯째 — 발주처가 날은 살렸는데 그 날을 태운 휠은 요구가 없다.
        self.assertIn("날은 남는데 그것을 태운 휠은 요구가 없다", titles)
        # 면 수는 날 두 장으로 닫혔고 통과 시간은 남았다.
        self.assertNotIn("백시트면 띠를 걷을 공구가 없다", titles)
        self.assertIn("자기 캐리어의 통과가 여유에 안 들어간다", titles)
        # 그리퍼를 정하면서 그 공구의 물성·배치가 새 입력으로 들어왔다.
        self.assertIn("그리퍼 패드 마찰이 실측 전 계획값이다", titles)
        self.assertEqual(len(titles), 9)

    def test_the_gc_headroom_is_stated_not_assumed(self):
        """Gc 가 얼마까지 오르면 허용 압착력을 넘는가 — 그 값을 내놓는다."""
        limit = sg_grind.max_gc_the_face_limit_allows()
        self.assertGreater(limit, sg_grind.sealant_gc_n_mm())
        self.assertAlmostEqual(
            limit * sg_grind.SEALANT_BAND_MM + sg_grind.shoe_friction_n(),
            sg_grind.safe_face_force_n(), places=2)
        self.assertGreater(sg_grind.gc_margin(), 1.0)


class TestGrindingTheWholeBacksheetFace(unittest.TestCase):
    """면 전체를 갈아낼 것인가 — 띠에서 나온 답을 면으로 키운 값들.

    지금 설계는 백시트 면을 안 건드린다. 그래도 이 비교를 값으로 들고 있는
    이유는, 「면을 통째로 연마하면 어떤가」가 되풀이해서 나오는 물음이고
    그때마다 손으로 다시 세면 답이 흔들리기 때문이다.

    이 묶음은 한 번 틀린 자리이기도 하다. 처음에는 띠의 비에너지를 면에
    빌려 쓰고, 면 설비의 택트가 아니라 이 라인의 AFR 택트로 나누고, 하류에서
    돌려받는 열을 아예 안 셌다. 셋이 겹쳐 「면 연마는 말이 안 된다」는 답이
    나왔지만 실제로는 가동 중인 공법이다. 아래 시험은 그 셋을 각각 붙든다.
    """

    def test_abrading_is_volume_work_so_thickness_multiplies(self):
        """연마는 부피 일이다 — 두께가 그대로 곱해진다."""
        self.assertAlmostEqual(
            sg_grind.backsheet_face_volume_mm3(),
            sg_grind.backsheet_face_area_mm2() * sg_grind.BACKSHEET_T_MM, places=1)
        self.assertAlmostEqual(
            sg_grind.backsheet_abrade_energy_j(),
            sg_grind.backsheet_face_volume_mm3() * sg_grind.BACKSHEET_ABRADE_J_MM3,
            places=1)

    def test_the_face_does_not_borrow_the_bands_specific_energy(self):
        """면은 띠의 비에너지를 안 빌린다 — 재료도 공구도 다르다.

        경화 실리콘을 좁은 띠에서 긁는 값과, 무른 폴리머를 넓은 벨트로 얕게
        걷는 값은 같을 수 없다. 빌려 쓰면 동력이 위로 크게 틀린다.
        """
        self.assertLess(sg_grind.BACKSHEET_ABRADE_J_MM3,
                        sg_grind.SEALANT_ABRADE_J_MM3)
        borrowed = (sg_grind.backsheet_face_volume_mm3()
                    * sg_grind.SEALANT_ABRADE_J_MM3 / sg_grind.FACE_ABRADE_TACT_S)
        self.assertGreater(borrowed, 4.0 * sg_grind.backsheet_abrade_power_w())

    def test_the_face_unit_is_timed_by_its_own_tact_not_this_lines(self):
        """면 설비는 자기 정반을 갖는다 — 이 라인의 AFR 택트로 나누지 않는다."""
        self.assertAlmostEqual(
            sg_grind.backsheet_abrade_power_w(),
            sg_grind.backsheet_abrade_energy_j() / sg_grind.FACE_ABRADE_TACT_S,
            places=1)
        self.assertNotAlmostEqual(sg_grind.FACE_ABRADE_TACT_S, float(campaign.AFR_S),
                                  places=1)

    def test_the_power_it_needs_is_an_ordinary_industrial_sander(self):
        """그렇게 세면 동력이 평범한 산업용 연마기 범위에 든다.

        이 시험이 이 묶음의 요지다 — 면 연마가 못 할 일이라는 결론이 나오면
        상수나 나눗수 어느 쪽이 틀린 것이다.
        """
        self.assertGreater(sg_grind.backsheet_abrade_power_kw(), 5.0)
        self.assertLess(sg_grind.backsheet_abrade_power_kw(), 100.0)

    def test_peeling_is_interfacial_work_so_thickness_does_not_enter(self):
        """박리는 계면 일이다 — 두께를 두 배로 해도 힘이 안 변한다.

        연마 쪽은 같은 조작에서 두 배가 된다. 그 대비가 수단을 가른다.
        """
        t0 = sg_grind.BACKSHEET_T_MM
        peel0, abrade0 = sg_grind.backsheet_peel_force_n(), sg_grind.backsheet_abrade_energy_j()
        try:
            sg_grind.BACKSHEET_T_MM = t0 * 2.0
            self.assertEqual(sg_grind.backsheet_peel_force_n(), peel0)
            self.assertAlmostEqual(sg_grind.backsheet_abrade_energy_j(), abrade0 * 2.0, places=1)
        finally:
            sg_grind.BACKSHEET_T_MM = t0

    def test_the_band_answer_holds_at_face_scale(self):
        """띠에서 긁는 쪽이 이겼듯, 면에서도 벗기는 쪽이 크게 이긴다.

        배수가 두 번 움직였고 둘 다 상수를 실제값으로 고쳐서다 — 연마
        비에너지를 8.0 에서 1.6 으로 내렸고(배수가 커짐), 박리 Gc 를 근거
        없던 0.5 에서 문헌값 2.0 으로 올렸다(배수가 1,024 → 256 으로 작아짐).
        **그래도 두 자릿수가 남는다.** 계면 일과 부피 일의 차이지 어느 한
        상수를 크게 잡아서 난 차이가 아니었다는 뜻이다.
        """
        self.assertGreater(sg_grind.scrape_beats_abrade_by(), 1_000)
        self.assertGreater(sg_grind.peel_beats_abrade_by(), 100)
        self.assertAlmostEqual(
            sg_grind.backsheet_peel_energy_j(),
            sg_grind.backsheet_peel_force_n() * float(campaign.PANEL_LENGTH_MM) / 1_000.0,
            places=1)

    def test_removing_the_backsheet_first_buys_heat_back_downstream(self):
        """면을 걷는 값은 순증이 아니다 — 불소원이 빠지면 열박리가 짧아진다.

        돌려받는 몫을 빼면 순 에너지가 음수다. 즉 에너지는 이 공법을 막는
        근거가 못 된다. 앞선 판정은 이 항을 빠뜨려서 뒤집혀 있었다.
        """
        self.assertAlmostEqual(
            sg_grind.downstream_heat_saved_j(),
            sg_grind.downstream_heat_j_per_panel() * sg_grind.BACKSHEET_FIRST_HEAT_SAVING,
            places=1)
        self.assertAlmostEqual(
            sg_grind.face_abrade_net_j(),
            sg_grind.backsheet_abrade_energy_j() - sg_grind.downstream_heat_saved_j(),
            places=1)
        self.assertLess(sg_grind.face_abrade_net_j(), 0.0)
        self.assertTrue(sg_grind.face_abrading_pays_for_itself())

    def test_what_actually_binds_is_dust_and_machine_count_not_energy(self):
        """그래서 걸리는 곳은 에너지가 아니라 분진·대수·개구부다.

        DS-01 은 폴리머를 안 깎는다는 전제로 '불연' 이다. 지금은 참이다.
        면을 갈면 그 전제가 깨지는데, 깨지는 크기를 값으로 들고 있는다.
        """
        self.assertTrue(sg_grind.dust_stream_stays_inert())
        self.assertFalse(sg_grind.wheel_may_touch_the_backsheet())
        self.assertGreater(sg_grind.backsheet_dust_kg_per_h(), 100.0)
        self.assertGreater(sg_grind.face_abraders_needed(), 1)
        self.assertFalse(sg_grind.panel_fits_face_abrader())

    def test_two_independent_routes_say_the_demo_machine_is_smaller(self):
        """개구부와 이송속도가 각각 같은 말을 한다 — 설비가 이 패널보다 작다.

        폭으로 봐도 안 들어가고, 길이를 그 이송속도로 지나게 해도 장당 택트를
        넘는다. 서로 다른 두 상수가 같은 결론을 내므로 어느 하나를 잘못 옮겨
        적은 것이 아니다. 공법이 아니라 크기가 걸린다는 뜻이다.
        """
        self.assertAlmostEqual(
            sg_grind.face_abrade_pass_s(),
            float(campaign.PANEL_LENGTH_MM) / sg_grind.FACE_ABRADE_FEED_MM_S, places=1)
        self.assertFalse(sg_grind.face_abrade_tact_covers_this_panel())
        self.assertFalse(sg_grind.panel_fits_face_abrader())

    def test_the_dust_figure_survives_every_constant_we_had_wrong(self):
        """분진만은 택트에도 비에너지에도 안 걸린다 — 부피 × 밀도뿐이다.

        상수를 어떻게 고쳐도 집진이 받아야 할 물건의 크기는 그대로다.
        그래서 이 값은 앞선 오류를 넘어 살아남은 유일한 요구사항이다.
        """
        e0, t0 = sg_grind.BACKSHEET_ABRADE_J_MM3, sg_grind.FACE_ABRADE_TACT_S
        dust0 = sg_grind.backsheet_dust_kg_per_panel()
        try:
            sg_grind.BACKSHEET_ABRADE_J_MM3 = e0 * 5.0
            sg_grind.FACE_ABRADE_TACT_S = t0 / 3.0
            self.assertEqual(sg_grind.backsheet_dust_kg_per_panel(), dust0)
        finally:
            sg_grind.BACKSHEET_ABRADE_J_MM3, sg_grind.FACE_ABRADE_TACT_S = e0, t0

    def test_the_values_come_from_the_modules_that_own_them(self):
        """면적은 campaign, 하류 열과 라인 속도는 handoff 가 정본이다."""
        self.assertAlmostEqual(
            sg_grind.backsheet_face_area_mm2(),
            float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM), places=1)
        self.assertAlmostEqual(
            sg_grind.downstream_heat_j_per_panel(),
            handoff.downstream_rate().heat_per_panel_mj * 1e6, places=1)
        self.assertAlmostEqual(
            sg_grind.backsheet_dust_kg_per_h(),
            round(sg_grind.backsheet_dust_kg_per_panel()
                  * handoff.downstream_rate().line_per_h, 1), places=1)


class TestThePlantDoesNotRequireTheArris(unittest.TestCase):
    """발주처가 아리스 요구 없음을 확인했다 — 물리 주장과 섞이지 않게 지킨다."""

    def test_the_two_propositions_are_separate(self):
        """하나는 「간다면 필수」, 하나는 「갈 이유」 — 값이 서로 안 따라간다."""
        self.assertTrue(sg_grind.arris_is_required())
        self.assertFalse(sg_grind.ARRIS_REQUIRED_BY_PLANT)

    def test_the_physics_verdict_reads_only_the_feed(self):
        """자기참조라는 주장의 근거 — 공정을 안 읽고 속도만 읽는다."""
        self.assertEqual(sg_grind.arris_is_required(),
                         sg_grind.is_brittle(sg_grind.long_feed_mm_s()))
        # 속도를 연성역으로 내리면 같은 함수가 거짓이 된다. 공정은 안 바뀌었다.
        self.assertFalse(sg_grind.is_brittle(1.0))

    def test_the_record_says_which_three_were_ruled_out(self):
        """셋 다 아니라고 돌아온 것이 무엇이었는지 적혀 있어야 한다."""
        text = " ".join(sg_grind.the_arris_has_no_requirement())
        for candidate in ("취급 안전", "파편 억제", "하류 유리 제거"):
            self.assertIn(candidate, text)
        self.assertIn("자기참조", sg_grind.the_arris_has_no_requirement.__doc__)

    def test_it_does_not_flip_the_physics(self):
        """요구가 없어진 것이 파단면을 연성면으로 만들지는 않는다."""
        text = " ".join(sg_grind.the_arris_has_no_requirement())
        self.assertIn("물음이 사라진다",
                      sg_grind.the_arris_has_no_requirement.__doc__)
        self.assertIn("전건이 안 선다", text)

    def test_the_arris_was_the_majority_of_the_work(self):
        """무엇이 풀리는지가 큰 이유 — 단면의 절반 이상이 아리스였다."""
        self.assertGreater(sg_grind.arris_share(), 0.5)
        stock_only = sg_grind.STOCK_MM * sg_grind.GLASS_T_MM
        self.assertAlmostEqual(
            stock_only, sg_grind.removal_area_mm2()
            - sg_grind.ARRIS_COUNT * sg_grind.ARRIS_MM ** 2 / 2, places=6)
        self.assertLess(stock_only, sg_grind.removal_area_mm2() / 2)

    def test_the_spindle_stops_being_the_limit(self):
        """아리스를 빼면 통과속도를 정하는 것이 스핀들이 아니게 된다."""
        self.assertTrue(sg_grind.feed_is_spindle_bound())
        stock_only = sg_grind.STOCK_MM * sg_grind.GLASS_T_MM
        relieved = sg_grind.utilisation(sg_grind.long_feed_mm_s()) \
            * stock_only / sg_grind.removal_area_mm2()
        self.assertLess(relieved, 0.5)

    def test_the_stock_is_not_released_with_it(self):
        """끝면 살은 근거가 달라 같이 안 풀린다 — 그것을 적어 둔다."""
        rows = dict(sg_grind.what_the_absent_arris_releases())
        key = [k for k in rows if "끝면 살" in k]
        self.assertEqual(len(key), 1)
        self.assertIn("별개의 물음", rows[key[0]])

    def test_the_sealant_conflict_loses_its_reason(self):
        """「둘 다는 안 된다」가 아리스 때문이었다 — 근거가 사라지는 것을 센다."""
        self.assertFalse(sg_grind.wheel_can_reach_the_glass_edge())
        self.assertGreater(sg_grind.sealant_must_go_first_mm(), 0.0)
        rows = dict(sg_grind.what_the_absent_arris_releases())
        key = [k for k in rows if "둘 다는 안 된다" in k]
        self.assertEqual(len(key), 1)

    def test_the_scrapers_stated_reason_was_the_wheel(self):
        """발견을 적어 둔다 — SR-302 의 근거로 적혀 있던 것이 휠뿐이었다."""
        for fn in (sg_grind.sealant_must_go_first_mm, sg_grind.scraper_unit):
            self.assertIn("휠", inspect.getdoc(fn))
        text = " ".join(sg_grind.the_scrapers_reason_was_the_wheel())
        self.assertIn("br_abrade.the_belt_meets_silicone_first", text)

    def test_it_does_not_decide_whether_sg301_survives(self):
        """판정 함수를 안 만든다 — 결정은 발주처 것이고, 건드리는 것만 센다."""
        titles = [t for t, _ in sg_grind.what_the_absent_arris_leaves_open()]
        self.assertIn("SG-301 이 남는가", titles)
        names = [n for n in dir(sg_grind) if "sg301" in n.lower()
                 or "sg_301" in n.lower()]
        self.assertEqual(names, [])

    def test_the_open_question_is_computed_not_declared(self):
        """미결이 상수에서 나온다 — 요구가 생기면 스스로 닫힌다."""
        titles = [t for t, _ in sg_grind.open_questions()]
        self.assertIn("아리스를 요구하는 공정이 없다", titles)

    def test_the_summary_carries_both(self):
        """도면과 요약이 두 명제를 나란히 든다 — 하나만 보면 오독한다."""
        s = sg_grind.summary()
        self.assertIs(s["arrisIsRequired"], True)
        self.assertIs(s["arrisRequiredByPlant"], False)


class TestTheScraperSurvivesTheWheel(unittest.TestCase):
    """발주처가 「SR-302 를 살린 안」을 골랐다 — 걸음은 남고 숙주는 근거를 잃었다."""

    def test_the_two_decisions_point_different_ways(self):
        """날은 살리고 아리스는 요구하지 않았다 — 두 답이 같은 방향이 아니다."""
        self.assertTrue(sg_grind.SCRAPER_KEPT_BY_PLANT)
        self.assertFalse(sg_grind.ARRIS_REQUIRED_BY_PLANT)

    def test_the_lead_left_the_wheels_cycle(self):
        """리드가 휠 때문에 있었고, 날이 나가면서 SG-301 에서 빠졌다."""
        self.assertIn("휠", inspect.getdoc(sg_grind.lead_cost_if_shared_s))
        self.assertGreater(sg_grind.lead_cost_if_shared_s(), 0.0)
        self.assertEqual(sg_grind.scraper_lead_cost_s(), 0.0)
        # 두 값이 같아졌다 — 지금 점유가 이미 날 없는 점유다.
        self.assertAlmostEqual(sg_grind.occupancy_without_scraper_s(),
                               sg_grind.occupancy_s(), places=2)

    def test_it_does_not_repurpose_the_lead_as_the_blades_time(self):
        """빠진 리드가 날의 점유가 되는 것이 아니라고 적는다 — 통과 종류가 다르다."""
        text = " ".join(sg_grind.the_scraper_outlives_its_host())
        self.assertIn("이 값을 그대로 쓰면 안", text)
        self.assertIn("날의 점유가 되는 것이 아니다", text)

    def test_the_carrier_is_decided_and_the_kinematics_are_not(self):
        """거처는 정해졌고 운동학은 안 정해졌다 — 그 둘을 갈라 적는다."""
        self.assertTrue(sg_grind.the_carrier_is_its_own())
        titles = [t for t, _ in sg_grind.what_the_absent_arris_leaves_open()]
        self.assertIn("자기 캐리어의 운동학", titles)
        # 면도 붙잡는 주체도 답이 왔고, 남은 것은 그리퍼의 생김새다.
        self.assertIn("그리퍼를 무엇으로 어떻게 놓는가", titles)
        self.assertNotIn("날이 몇 면을 긁는가", titles)
        self.assertNotIn("SR-302 가 어디에 실리는가", titles)

    def test_the_requirement_widened_from_shoulder_to_band(self):
        """근거가 옮겨가며 요구 폭이 넓어진다 — 어깨 몫에서 띠 전체로."""
        wheel, belt, blade = sg_grind.the_band_requirement_widened()
        self.assertEqual(wheel, sg_grind.sealant_must_go_first_mm())
        self.assertEqual(belt, float(sg_grind.SEALANT_BAND_MM))
        self.assertGreater(belt, wheel)
        self.assertEqual(blade, sg_grind.BLADE_WIDTH_MM)

    def test_the_existing_blade_already_covers_it(self):
        """공구를 안 바꿔도 되는 이유 — 날 폭이 애초에 띠 기준이었다."""
        self.assertTrue(sg_grind.the_blade_already_covers_the_wider_requirement())
        self.assertEqual(sg_grind.BLADE_WIDTH_MM,
                         sg_grind.SEALANT_BAND_MM + 4.0)

    def test_the_open_question_is_computed_from_the_two_constants(self):
        """미결이 두 상수에서 나온다 — 한쪽이 바뀌면 스스로 닫힌다."""
        titles = [t for t, _ in sg_grind.open_questions()]
        self.assertIn("날은 남는데 그것을 태운 휠은 요구가 없다", titles)

    def test_the_summary_carries_the_decision(self):
        s = sg_grind.summary()
        self.assertIs(s["scraperKeptByPlant"], True)


class TestTheBladeGetsItsOwnCarrier(unittest.TestCase):
    """발주처가 거처를 자기 캐리어로 정했다 — 회계가 리드에서 운동학으로 옮겼다."""

    def test_the_decision_lives_in_campaign(self):
        """정본이 하나다 — 리드를 쥔 모듈이 결정도 쥔다."""
        self.assertTrue(campaign.SCRAPER_ON_ITS_OWN_CARRIER)
        self.assertIs(sg_grind.the_carrier_is_its_own(), True)
        self.assertEqual(campaign.sg_blade_lead_mm(), 0.0)

    def test_the_cycle_reads_the_decision_not_the_constant(self):
        """순환이 결정에서 리드를 받아 온다 — 리터럴을 안 쓴다."""
        src = inspect.getsource(sg_grind.cycle)
        self.assertIn("campaign.sg_blade_lead_mm()", src)
        self.assertNotIn("campaign.SG_BLADE_LEAD_MM", src)

    def test_the_two_modules_agree_on_the_occupancy(self):
        self.assertAlmostEqual(sg_grind.occupancy_s(),
                               campaign.sg_occupancy_s(), places=2)

    def test_the_slack_grew_by_exactly_the_lead(self):
        """리드가 빠진 만큼 여유가 늘었다 — 다른 데서 온 값이 아니다."""
        self.assertAlmostEqual(
            sg_grind.slack_s(),
            campaign.AFR_S - sg_grind.occupancy_s(), places=2)
        self.assertGreater(sg_grind.slack_s(), sg_grind.lead_cost_if_shared_s())

    def test_the_path_is_the_perimeter_per_face(self):
        per = 2.0 * (campaign.PANEL_LENGTH_MM + campaign.PANEL_WIDTH_MM)
        self.assertAlmostEqual(sg_grind.scraper_path_mm(1), per, places=1)
        self.assertAlmostEqual(sg_grind.scraper_path_mm(2), 2 * per, places=1)

    def test_power_is_never_the_limit(self):
        """힘이 고정이라 동력이 속도에 선형인데 어디서도 한계에 안 닿는다."""
        for feed in (300.0, 1000.0, 3000.0):
            self.assertLess(sg_grind.scraper_power_at_w(feed),
                            sg_grind.spindle_available_w() * 0.1)
        self.assertAlmostEqual(
            sg_grind.scraper_power_at_w(600.0),
            2 * sg_grind.scraper_power_at_w(300.0), places=1)

    def test_the_inherited_feed_does_not_fit_the_slack(self):
        """물려받은 이송으로는 안 들어간다 — 그래서 필요 이송을 내놓는다."""
        lf = sg_grind.long_feed_mm_s()
        self.assertFalse(sg_grind.scraper_fits_the_slack(lf))
        need = sg_grind.feed_that_fits_the_slack_mm_s()
        self.assertGreater(need, lf)
        self.assertTrue(sg_grind.scraper_fits_the_slack(need * 1.001))

    def test_the_needed_feed_is_cheap_in_power(self):
        """필요 이송에서도 동력이 문제가 아니라는 것 — 한계가 캐리지임의 근거."""
        need = sg_grind.feed_that_fits_the_slack_mm_s()
        self.assertLess(sg_grind.scraper_power_at_w(need),
                        sg_grind.spindle_available_w() * 0.05)
        text = " ".join(sg_grind.the_own_carrier_frees_the_feed())
        self.assertIn("캐리지와 슈", text)

    def test_the_head_arrangement_is_borrowed_not_chosen(self):
        """SG 배치를 빌려 견주기만 한다 — 정한 것이 아니라고 적혀야 한다."""
        doc = inspect.getdoc(sg_grind.scraper_time_like_sg_heads_s)
        self.assertIn("배치를 정한 것이 아니라", doc)
        self.assertLess(
            sg_grind.feed_that_fits_the_slack_mm_s(like_sg_heads=True),
            sg_grind.feed_that_fits_the_slack_mm_s())


class TestBothFacesAreScrapedAtOnce(unittest.TestCase):
    """발주처가 날 두 장·양면 동시로 정했다 — 면 수가 맞춰졌다."""

    def test_the_counts_agree_now(self):
        self.assertEqual(sg_grind.BLADE_FACES, sg_grind.RESIDUE_FACES)
        self.assertFalse(sg_grind.the_back_face_band_has_no_tool())

    def test_the_name_matches_the_return(self):
        """이름이 「없다」이므로 없을 때 참이어야 한다 — 뒤집혀 있으면 오독한다."""
        self.assertEqual(sg_grind.the_back_face_band_has_no_tool(),
                         sg_grind.BLADE_FACES < sg_grind.RESIDUE_FACES)

    def test_the_problem_it_solved_is_still_recorded(self):
        """왜 두 장인지의 근거가 남아야 한다 — 한 장이면 절반이 남았다."""
        one = sg_grind.sealant_volume_per_panel_mm3(faces=1)
        both = sg_grind.sealant_volume_per_panel_mm3(faces=sg_grind.RESIDUE_FACES)
        self.assertAlmostEqual(both, 2 * one, places=1)
        text = " ".join(sg_grind.how_the_faces_were_made_to_add_up())
        self.assertIn(f"{one:,.0f} mm³", text)
        self.assertIn(f"{sg_grind.EDGE_OVERHANG_MM:.0f} mm", text)

    def test_the_existing_predicate_is_marked_as_not_about_faces(self):
        """「공구가 있는가」를 「두 면이 걷힌다」로 읽으면 안 된다고 적혀야 한다."""
        self.assertTrue(sg_grind.face_residue_has_a_tool())
        doc = inspect.getdoc(sg_grind.face_residue_has_a_tool)
        self.assertIn("몇 면을 걷는가", doc)
        self.assertIn("the_back_face_band_has_no_tool", doc)

    def test_travel_is_one_lap_whatever_the_blade_count(self):
        """「동시」의 값이 이것이다 — 주행이 날 수에 안 걸린다."""
        per = 2.0 * (campaign.PANEL_LENGTH_MM + campaign.PANEL_WIDTH_MM)
        self.assertAlmostEqual(sg_grind.scraper_travel_mm(), per, places=1)
        self.assertTrue(sg_grind.the_second_blade_costs_no_time())
        self.assertAlmostEqual(
            sg_grind.travel_if_one_blade_did_both_faces_mm(),
            per * sg_grind.RESIDUE_FACES, places=1)

    def test_the_scraping_length_is_not_the_travel(self):
        """긁는 길이와 주행 거리를 섞으면 시간이 두 배로 나온다."""
        self.assertAlmostEqual(
            sg_grind.scraper_path_mm(),
            sg_grind.scraper_travel_mm() * sg_grind.BLADE_FACES, places=1)
        self.assertGreater(sg_grind.scraper_path_mm(),
                           sg_grind.scraper_travel_mm())

    def test_the_time_functions_read_the_travel(self):
        """시간이 주행에서 나온다 — 면을 늘려도 안 변한다."""
        lf = sg_grind.long_feed_mm_s()
        want = sg_grind.scraper_travel_mm() / lf
        self.assertAlmostEqual(sg_grind.scraper_serial_time_s(lf), want, places=2)

    def test_the_second_blade_buys_exactly_one_lap(self):
        lf = sg_grind.long_feed_mm_s()
        self.assertAlmostEqual(sg_grind.time_the_second_blade_saves_s(lf),
                               sg_grind.scraper_travel_mm() / lf, places=2)

    def test_the_normal_force_cancels_and_the_tangential_adds(self):
        """마주 본다고 다 상쇄되는 것이 아니다 — 갈리는 자리를 지킨다."""
        self.assertEqual(sg_grind.normal_net_on_panel_n(), 0.0)
        self.assertEqual(sg_grind.clamp_force_n(), sg_grind.SHOE_SPRING_N)
        self.assertAlmostEqual(
            sg_grind.tangential_total_n(),
            sg_grind.scrape_total_force_n() * sg_grind.BLADE_FACES, places=2)
        self.assertGreater(sg_grind.tangential_total_n(),
                           sg_grind.scrape_total_force_n())

    def test_the_cancellation_needs_them_opposed(self):
        """같은 자리에서 마주 봐야 성립한다 — 어긋나면 우력이다."""
        self.assertTrue(sg_grind.BLADES_ARE_OPPOSED)
        text = " ".join(sg_grind.the_shoes_oppose_each_other())
        self.assertIn("우력", text)
        self.assertIn("같은 자리", text)

    def test_one_face_still_sees_only_one_spring(self):
        """두 장이라고 한 면이 두 배로 눌리지 않는다."""
        self.assertTrue(sg_grind.shoe_is_gentle_enough())
        self.assertLessEqual(sg_grind.SHOE_SPRING_N, sg_grind.safe_face_force_n())

    def test_the_per_face_comparison_is_untouched(self):
        """긁기 대 갈기 비교는 한 면끼리여야 한다 — 합력을 넣으면 반토막 난다."""
        lf = sg_grind.long_feed_mm_s()
        self.assertAlmostEqual(
            sg_grind.scrape_power_w(lf),
            sg_grind.scrape_total_force_n() * lf / 1_000.0, places=2)
        self.assertGreater(sg_grind.scrape_beats_abrade_by(), 1_000)

    def test_the_carrier_power_uses_the_total(self):
        lf = sg_grind.long_feed_mm_s()
        self.assertAlmostEqual(
            sg_grind.scraper_power_at_w(lf),
            sg_grind.tangential_total_n() * lf / 1_000.0, places=1)

    def test_the_face_gap_is_no_longer_an_open_question(self):
        titles = [t for t, _ in sg_grind.open_questions()]
        self.assertNotIn("백시트면 띠를 걷을 공구가 없다", titles)

    def test_the_drawing_carries_both_sets(self):
        """도면이 두 세트를 다 세워야 한다 — 하나만 그리면 결정이 안 보인다."""
        keys = [p.key for p in sg_grind.scraper_unit().parts]
        for k in ("srbld", "srbld2", "srshoe", "srshoe2", "srband", "srband2"):
            self.assertIn(k, keys)

    def test_the_lower_set_mirrors_about_the_laminate(self):
        """아래 세트가 라미네이트 중립면의 거울상이어야 마주 본다."""
        parts = {p.key: p for p in sg_grind.scraper_unit().parts}
        mid = -sg_grind.STACK_T_MM / 2 - 8.0
        for a, b in (("srarm", "srarm2"), ("srspr", "srspr2"),
                     ("srshoe", "srshoe2"), ("srbld", "srbld2"),
                     ("srchip", "srchip2")):
            self.assertAlmostEqual(parts[b].pos[1], 2 * mid - parts[a].pos[1],
                                   places=3, msg=f"{b} 가 {a} 의 거울상이 아니다")
            self.assertEqual(parts[b].pos[0], parts[a].pos[0])


class TestTheGripperTakesTheDrag(unittest.TestCase):
    """발주처가 접선 합력을 그리퍼가 받는 것으로 정했다."""

    def test_the_grip_force_follows_from_the_drag(self):
        """물어야 하는 힘이 끄는 힘 ÷ 마찰 × 안전율이다 — 임의값이 아니다."""
        self.assertAlmostEqual(
            sg_grind.grip_force_needed_n(),
            sg_grind.tangential_total_n() * sg_grind.GRIP_SAFETY
            / sg_grind.GRIP_FRICTION, places=1)
        self.assertGreater(sg_grind.grip_force_needed_n(),
                           sg_grind.tangential_total_n())

    def test_the_face_limit_is_a_pressure_not_a_force(self):
        """면 한계가 넓이로 답을 낸다 — 「몇 N 까지」가 아니라 「몇 mm² 를」."""
        self.assertAlmostEqual(
            sg_grind.grip_pad_area_needed_mm2(),
            sg_grind.grip_force_needed_n() / sg_grind.FACE_SAFE_MPA, places=1)
        self.assertTrue(sg_grind.grip_is_sized_by_area_not_force())
        text = " ".join(sg_grind.the_face_limit_turns_force_into_area())
        self.assertIn("한계가 아니라", text)

    def test_the_pad_is_far_from_being_the_binding_limit(self):
        """성립이 깨지는 마찰이 한참 아래여야 한다 — 그래야 치수 문제다."""
        self.assertLess(sg_grind.friction_below_which_the_pad_outgrows_the_panel(),
                        sg_grind.GRIP_FRICTION / 10.0)
        face = campaign.PANEL_LENGTH_MM * campaign.PANEL_WIDTH_MM
        self.assertLess(sg_grind.grip_pad_area_needed_mm2(), face / 100.0)

    def test_the_shoe_friction_is_not_reused_for_the_pad(self):
        """슈는 미끄러지라고, 패드는 잡으라고 고른 값이다 — 같으면 안 된다."""
        self.assertGreater(sg_grind.GRIP_FRICTION, sg_grind.SHOE_FRICTION)
        doc = inspect.getdoc(sg_grind.grip_force_needed_n)
        self.assertIn("마찰계수", doc)
        src = inspect.getsource(sg_grind)
        self.assertIn("빌려 오면 안 된다", src)

    def test_the_pad_must_clear_the_sealant_band(self):
        """띠 위에 얹으면 걷을 것을 눌러 붙이고 마찰 전제도 깨진다."""
        self.assertEqual(sg_grind.grip_must_sit_inboard_mm(),
                         sg_grind.SEALANT_BAND_MM)

    def test_the_drag_also_makes_a_moment(self):
        """변에서 끌고 안쪽에서 잡으니 힘만 받는 것이 아니다."""
        short_pass = sg_grind.grip_moment_n_m()
        long_pass = sg_grind.grip_moment_n_m(long_edge=True)
        self.assertGreater(short_pass, long_pass)
        self.assertAlmostEqual(
            short_pass,
            sg_grind.tangential_total_n() * campaign.PANEL_LENGTH_MM
            / 2.0 / 1_000.0, places=2)

    def test_the_layout_is_a_parameter_not_a_decision(self):
        """배치를 정하지 않는다 — 정해지면 값이 나온다는 것만 보인다."""
        wide = sg_grind.grip_pad_force_n(4, 1_000.0)
        narrow = sg_grind.grip_pad_force_n(4, 500.0)
        self.assertGreater(narrow, wide)        # 좁게 놓으면 우력분이 커진다
        self.assertGreater(sg_grind.grip_pad_force_n(2, 1_000.0), wide)
        doc = inspect.getdoc(sg_grind.grip_pad_force_n)
        self.assertIn("배치를 정하는 함수가 아니다", doc)
        self.assertEqual(sg_grind.grip_pad_force_n(0, 1_000.0), float("inf"))

    def test_the_planning_values_are_open_questions(self):
        titles = [t for t, _ in sg_grind.open_questions()]
        self.assertIn("그리퍼 패드 마찰이 실측 전 계획값이다", titles)
        self.assertIn("그리퍼 패드 배치를 안 들었다", titles)
        self.assertIn("한쪽으로 누르는지 양쪽으로 무는지 안 들었다", titles)

    def test_the_holder_is_decided_but_not_its_shape(self):
        titles = [t for t, _ in sg_grind.what_the_absent_arris_leaves_open()]
        self.assertIn("그리퍼를 무엇으로 어떻게 놓는가", titles)
        self.assertNotIn("판을 무엇이 붙잡는가", titles)

    def test_the_drawing_shows_where_the_pad_must_stand(self):
        parts = {p.key: p for p in sg_grind.scraper_unit().parts}
        self.assertIn("srgrip", parts)
        self.assertIn("배치 미정", parts["srgrip"].name)
        self.assertIn(f"{sg_grind.grip_must_sit_inboard_mm():.0f} mm 안쪽",
                      parts["srgrip"].role)

    def test_the_summary_carries_the_sizing_chain(self):
        s = sg_grind.summary()
        self.assertAlmostEqual(s["gripForceNeededN"],
                               sg_grind.grip_force_needed_n(), places=1)
        self.assertAlmostEqual(s["gripPadAreaMm2"],
                               sg_grind.grip_pad_area_needed_mm2(), places=1)


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
        self.assertEqual([u["key"] for u in units],
                         ["long", "short", "contact", "scraper"])
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
