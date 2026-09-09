"""GI-303 롤러 창 위의 패널 — `gi_plate` 의 **검증**.

수치해석은 답을 내는 것이 쉽고 맞는 답인지 아는 것이 어렵다. 여기서는 정해가
있는 것과 정해로 견줄 수 있는 것만 붙든다.

  ① 단면 — 변환단면이 `afr` 의 유리 단독 띠와 한 판인가, 자중이 같은가
  ② 정적 — 한 스팬 단순지지가 5wL⁴/384EI 와 맞는가, 연속보가 그보다 작은가,
     외팔이 고정단 닫힌해보다 **큰가**(뒤가 회전하므로)
  ③ 모드 — 연속보의 1차가 단순지지 한 스팬의 (π/2L²)√(EI/ρA) 인가
  ④ 과도 — 램프가 한 주기를 넘고, 되튐이 앞끝 처짐보다 훨씬 작고, 시작값이
     정적 앞끝 처짐과 이어지는가 (두 풀이가 한 사건인가)
  ⑤ 광학 — 정확한 얇은렌즈 흐림이 심도 끝에서 정확히 c/m 인가, 이송 흐림이 v·t 인가
  ⑥ 예산·문턱 — 항목이 더해져 허용치가 되는가, κ 문턱이 순서대로인가
  ⑦ 브라우저 상수 — SI 로 넘긴 값이 모델값과 같은가
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, beam, gi_optics, gi_plate, sg_grind


class TestTheSectionIsOnePanel(unittest.TestCase):
    """변환단면 — 다른 모듈이 아는 판과 같은 판이어야 한다."""

    def test_layers_add_up_to_the_stack(self):
        total = sum(t for _, t, _, _ in gi_plate.layers())
        self.assertAlmostEqual(total, gi_plate.STACK_T_MM, places=9)
        self.assertGreater(gi_plate.encap_t_mm(), 0.0)

    def test_the_glass_face_is_down(self):
        """`vision` 이 적은 대로 유리면이 아래(y=0)다 — GI-303 이 보는 면."""
        name, _, _, y0 = gi_plate.layers()[0]
        self.assertEqual(name, "유리")
        self.assertEqual(y0, 0.0)

    def test_it_agrees_with_the_glass_only_strip(self):
        """`afr` 는 유리 t³/12 로 처짐을 냈다 — 폴리머를 더해도 10 % 안이어야 한다."""
        self.assertTrue(gi_plate.agrees_with_the_glass_only_strip())
        glass_only = gi_plate.GLASS_E_MPA * afr.laminate_strip_i_mm4()
        self.assertGreater(gi_plate.ei_n_mm2(), glass_only)      # 폴리머는 더할 뿐이다
        self.assertLess(gi_plate.polymer_share_of_stiffness(), 0.01)

    def test_self_weight_is_afr_line_load(self):
        self.assertAlmostEqual(gi_plate.line_load_n_mm(),
                               afr.laminate_line_load_n_per_mm(), places=8)
        self.assertAlmostEqual(gi_plate.section().weight_n_mm,
                               gi_plate.line_load_n_mm(), places=8)

    def test_stiffness_falls_monotonically_as_glass_cracks(self):
        prev = None
        for k in (1.0, 0.5, 0.1, 0.01, 0.001, 0.0):
            ei = gi_plate.ei_n_mm2(k)
            if prev is not None:
                self.assertLess(ei, prev)
            prev = ei
        self.assertGreater(gi_plate.ei_n_mm2(0.0), 0.0)         # 폴리머는 남는다


class TestStaticsAgainstClosedForms(unittest.TestCase):
    """정해가 있는 것으로 유한요소를 붙든다."""

    def test_a_single_pinned_span_is_the_textbook_value(self):
        """단순지지 한 스팬 — 5wL⁴/384EI. 이것이 틀리면 아래는 못 믿는다."""
        b, _ = gi_plate.strip(1.0, 1)
        end = (b.n_node - 1) * beam.DOF_PER_NODE
        u = b.solve_static(prescribed={0: 0.0, end: 0.0}, udl_n_mm=-gi_plate.line_load_n_mm())
        got = -b.deflection(u)[b.n_node // 2]
        self.assertAlmostEqual(got / gi_plate.simply_supported_sag_mm(), 1.0, places=6)

    def test_the_continuous_strip_sags_less_than_one_span(self):
        """이웃 스팬이 붙잡아 준다 — 연속보 처짐이 단순지지의 1/3 아래."""
        self.assertLess(gi_plate.continuity_factor(), 0.35)
        self.assertGreater(gi_plate.continuity_factor(), 0.15)

    def test_the_support_span_is_the_pitch_not_the_window(self):
        """평평한 판은 롤러 꼭대기 한 줄에 닿는다 — 받침 사이는 피치다."""
        self.assertEqual(gi_plate.support_span_mm(), gi_optics.ROLLER_PITCH_MM)
        self.assertEqual(gi_optics.unsupported_span_mm(), gi_optics.ROLLER_PITCH_MM)
        self.assertGreater(gi_plate.support_span_mm(), gi_optics.roller_window_mm())

    def test_the_sag_profile_is_zero_on_every_roller(self):
        _, rollers = gi_plate.strip()
        prof = gi_plate.sag_profile()
        for node in rollers:
            with self.subTest(node=node):
                self.assertAlmostEqual(prof[node][1], 0.0, places=9)

    def test_the_entry_cantilever_exceeds_the_fixed_end_bound(self):
        """뒤가 고정단이 아니라 롤러 위에서 회전하므로 닫힌해보다 크다."""
        reach = gi_plate.entry_reach_mm()
        self.assertGreater(gi_plate.entry_sag_mm(), gi_plate.cantilever_closed_form_mm(reach))
        self.assertLess(gi_plate.entry_sag_mm(), 3 * gi_plate.cantilever_closed_form_mm(reach))

    def test_the_scan_line_sees_less_than_the_tip(self):
        """초점이 보는 것은 끝이 아니라 스캔선이다 — 끝 처짐으로 예산을 쓰면 과하다."""
        self.assertLess(gi_plate.entry_scan_sag_mm(), gi_plate.entry_sag_mm() / 2.0)
        sweep = gi_plate.entry_scan_sweep()
        self.assertEqual(sweep[0][0], gi_plate.SCAN_FROM_ROLLER_MM)
        self.assertEqual(sweep[-1][0], gi_plate.entry_reach_mm())
        ws = [w for _, w in sweep]
        self.assertEqual(ws, sorted(ws))                          # 외팔이 길수록 더 처진다

    def test_the_glass_does_not_break_on_the_rollers(self):
        self.assertTrue(gi_plate.glass_survives_the_rollers())
        self.assertLess(gi_plate.window_stress_mpa(), gi_plate.GLASS_STRENGTH_MPA / 20.0)


class TestModesAgainstTheClosedForm(unittest.TestCase):
    """연속보의 최저 모드는 단순지지 한 스팬의 것이다 (등간격 등스팬)."""

    def test_fundamental_matches_the_pinned_span(self):
        self.assertAlmostEqual(gi_plate.fundamental_hz() / gi_plate.pinned_span_closed_form_hz(),
                               1.0, places=2)

    def test_the_forcing_is_far_below_the_first_mode(self):
        self.assertGreater(gi_plate.frequency_ratio(), 10.0)
        self.assertTrue(gi_plate.rides_the_rollers_quasi_statically())
        self.assertAlmostEqual(gi_plate.runout_amplification(), 1.0, places=2)

    def test_roller_spin_is_rolling_without_slip(self):
        """ω = v/r — rpm 을 따로 안 정한다."""
        want = gi_plate.TRANSPORT_MM_S / (math.pi * gi_plate.ROLLER_D_MM)
        self.assertAlmostEqual(gi_plate.roller_spin_hz(), want, places=9)
        self.assertAlmostEqual(gi_plate.roller_pass_hz(),
                               gi_plate.TRANSPORT_MM_S / gi_plate.PITCH_MM, places=9)


class TestTheLandingIsARampNotAStep(unittest.TestCase):
    """앞끝이 롤러에 얹히는 순간 — 두 풀이가 한 사건이어야 한다."""

    def test_the_tip_meets_the_roller_flank_before_the_apex(self):
        """처진 끝은 꼭대기가 아니라 옆면에 먼저 닿는다 — x = √(2Rδ)."""
        x = gi_plate.landing_approach_mm()
        self.assertGreater(x, 0.0)
        self.assertAlmostEqual(x * x, gi_plate.ROLLER_D_MM * gi_plate.landing_lift_mm(), places=6)
        self.assertLess(x, gi_plate.ROLLER_D_MM / 2.0)

    def test_the_ramp_outlasts_a_period(self):
        """램프가 한 주기를 넘으면 계단 충격이 아니다."""
        self.assertGreater(gi_plate.landing_ramp_in_periods(), 1.0)

    def test_the_transient_starts_where_the_static_entry_ends(self):
        """t=0 의 스캔선 처짐이 정적 외팔의 스캔선 처짐과 같아야 한다 — 이어지는 풀이다."""
        t0, w0 = gi_plate.landing_transient()[0]
        self.assertEqual(t0, 0.0)
        self.assertAlmostEqual(w0, gi_plate.entry_scan_sag_mm(), places=3)

    def test_the_overshoot_is_a_fraction_of_the_entry_sag(self):
        """램프라 되튐이 작다 — 계단으로 잡으면 앞끝 처짐보다 커진다."""
        self.assertLess(gi_plate.landing_overshoot_mm(), gi_plate.entry_scan_sag_mm() / 10.0)

    def test_it_settles_before_the_next_pitch_reaches_the_scan_line(self):
        self.assertTrue(gi_plate.landing_is_quiet_before_the_scan())
        self.assertLess(gi_plate.landing_settles_within_s(), gi_plate.scan_line_dwell_s() / 5.0)

    def test_the_strip_comes_to_rest_at_the_continuous_sag(self):
        _, w_end = gi_plate.landing_transient()[-1]
        rest = gi_plate.window_sag_mm()
        self.assertLess(abs(w_end - rest), gi_plate.ROLLER_RUNOUT_MM / 10.0)


class TestTheOpticsCoupling(unittest.TestCase):
    """처짐이 화소가 되기까지 — 두 식이 한 광학인가."""

    def test_defocus_at_the_dof_edge_is_exactly_the_criterion(self):
        """`gi_optics.depth_of_field_mm` (2Nc(1+m)/m²) 와 정확한 얇은렌즈가 같은 식이다."""
        self.assertTrue(gi_plate.blur_at_dof_edge_is_the_criterion())

    def test_defocus_grows_with_distance_and_is_zero_in_focus(self):
        self.assertEqual(gi_plate.defocus_blur_mm(0.0), 0.0)
        self.assertLess(gi_plate.defocus_blur_mm(1.0), gi_plate.defocus_blur_mm(2.0))
        self.assertAlmostEqual(gi_plate.defocus_blur_mm(1.0), gi_plate.defocus_blur_mm(-1.0), places=3)

    def test_small_dz_limit_is_m_dz_over_n_one_plus_m(self):
        n = gi_plate.cameras()
        m, N = gi_optics.magnification(n), gi_optics.F_NUMBER
        dz = 0.01
        self.assertAlmostEqual(gi_plate.defocus_blur_mm(dz, n) / (m * dz / (N * (1 + m))),
                               1.0, places=3)

    def test_motion_blur_is_speed_times_exposure(self):
        want = gi_plate.TRANSPORT_MM_S * gi_optics.exposure_us() * 1e-6
        self.assertAlmostEqual(gi_plate.motion_blur_mm(), want, places=5)
        self.assertLess(gi_plate.motion_blur_px(), 1.0)
        self.assertGreater(gi_plate.motion_blur_px(), 0.5)         # 화소의 절반을 넘는다

    def test_motion_blur_not_sag_sets_the_image(self):
        self.assertTrue(gi_plate.motion_blur_costs_more_than_sag())

    def test_the_arris_stays_measurable_across_the_budget(self):
        """예산 끝까지 가도 아리스가 확실판정 화소 수 위다 — 이송·교차 양쪽."""
        self.assertTrue(gi_plate.arris_is_measurable(0.0))
        self.assertTrue(gi_plate.arris_is_measurable(gi_optics.PANEL_BOW_MM))
        self.assertGreater(gi_plate.arris_px(0.0, False), gi_plate.arris_px(0.0, True))

    def test_the_effective_pixel_is_never_finer_than_the_pixel(self):
        for dz in (0.0, 1.0, 2.9):
            for along in (True, False):
                with self.subTest(dz=dz, along=along):
                    self.assertGreaterEqual(gi_plate.effective_pixel_mm(dz, along),
                                            gi_optics.RESOLUTION_MM)


class TestTheBudgetAndTheThresholds(unittest.TestCase):
    """3 mm 는 어디로 가는가 · 깨진 유리는 어디서 실패하는가."""

    def test_the_budget_adds_up_to_the_allowance(self):
        b = gi_plate.sag_budget_mm()
        self.assertAlmostEqual(b["envelope"] + b["runout"] + b["warp"], b["allowance"], places=3)
        self.assertEqual(b["allowance"], gi_optics.PANEL_BOW_MM)

    def test_the_envelope_is_the_largest_part_not_the_sum(self):
        b = gi_plate.sag_budget_mm()
        self.assertAlmostEqual(b["envelope"], max(b["gravity"], b["entry"], b["landing"]), places=4)
        self.assertLess(b["envelope"], b["gravity"] + b["entry"] + b["landing"])

    def test_most_of_the_budget_is_left_for_panel_warp(self):
        """자중·앞끝·되튐은 문제가 아니다 — 남는 것이 반입 조건이 된다."""
        self.assertTrue(gi_plate.budget_is_flatness_not_gravity())
        self.assertGreater(gi_plate.warp_allowance_mm(), 2.0)
        self.assertTrue(gi_plate.budget_fits_the_depth_of_field())

    def test_sag_falls_monotonically_with_glass_share(self):
        prev = None
        for k in (0.0, 1e-5, 1e-4, 1e-3, 0.01, 0.1, 1.0):
            sag = gi_plate.window_sag_mm(k)
            if prev is not None:
                self.assertLess(sag, prev)
            prev = sag

    def test_the_thresholds_are_ordered(self):
        """보호창을 안 치는 문턱이 초점을 지키는 문턱보다 낮다 — 창이 더 멀다."""
        self.assertLess(gi_plate.glass_share_for_cover(), gi_plate.glass_share_for_focus())
        self.assertLess(gi_plate.glass_share_for_focus(), 1.0)
        self.assertGreater(gi_plate.cover_gap_mm(), gi_plate.dof_half_mm())

    def test_the_thresholds_hit_their_targets(self):
        self.assertAlmostEqual(gi_plate.window_sag_mm(gi_plate.glass_share_for_focus())
                               / gi_plate.dof_half_mm(), 1.0, places=1)
        self.assertAlmostEqual(gi_plate.window_sag_mm(gi_plate.glass_share_for_cover())
                               / gi_plate.cover_gap_mm(), 1.0, places=1)

    def test_a_fully_crazed_panel_hits_the_cover(self):
        self.assertTrue(gi_plate.a_fully_crazed_panel_hits_the_cover())
        self.assertTrue(gi_plate.a_cracked_panel_still_focuses())

    def test_the_cover_gap_is_the_drawn_one(self):
        """`gi_optics` 형상의 보호창 자리와 같은 값 — 두 곳에 적혀 있지 않다."""
        below = {p.key: p for p in gi_optics.below_unit().parts}
        cover = below["locover"]
        self.assertAlmostEqual(abs(cover.pos[1]),
                               gi_optics.COVER_GLASS_T_MM / 2.0 + gi_plate.cover_gap_mm(),
                               places=6)


class TestTheBrowserGetsTheModel(unittest.TestCase):
    """XPBD 상수 — 모델값과 같아야 하고 단위가 SI 여야 한다."""

    def test_si_constants_match_the_model(self):
        si = gi_plate.physics_si()
        self.assertAlmostEqual(si["ei"], gi_plate.ei_n_mm2() * 1e-3, places=3)     # N·mm²/mm → N·m²/m
        self.assertAlmostEqual(si["rhoA"], gi_plate.AREAL_KG_M2, places=6)
        self.assertAlmostEqual(si["pitchM"] * 1000.0, gi_plate.PITCH_MM, places=6)
        self.assertAlmostEqual(si["sagIntactM"] * 1000.0, gi_plate.window_sag_mm(), places=6)
        self.assertEqual(si["shareFocus"], gi_plate.glass_share_for_focus())
        self.assertEqual(si["shareCover"], gi_plate.glass_share_for_cover())
        self.assertAlmostEqual(si["dofM"] * 1000.0, gi_optics.depth_of_field_mm(gi_plate.cameras()),
                               places=6)
        self.assertAlmostEqual(si["exposureS"] * 1e6, gi_optics.exposure_us(), places=2)

    def test_the_xpbd_strip_would_sag_like_the_fem(self):
        """폭 1 m 띠의 EI 와 ρA 로 단순지지 처짐을 다시 내면 mm 모델과 같다."""
        si = gi_plate.physics_si()
        L = si["pitchM"]
        w = si["rhoA"] * 9.81                                     # N/m per m width
        sag_m = 5.0 * w * L ** 4 / (384.0 * si["ei"])
        self.assertAlmostEqual(sag_m * 1000.0, gi_plate.simply_supported_sag_mm(), places=5)


class TestOpenQuestions(unittest.TestCase):

    def test_the_warp_allowance_is_named(self):
        titles = [t for t, _ in gi_plate.open_questions()]
        self.assertIn("중고 패널의 휨이 반입 조건 안인지 실측 전이다", titles)

    def test_the_crack_threshold_states_its_premise(self):
        body = dict(gi_plate.open_questions())["깨진 유리에 남는 강성이 어디쯤인지 실측 전이다"]
        self.assertIn("평면유지", body)
        self.assertIn("보호창", body)

    def test_motion_blur_is_named_and_tied_to_the_light(self):
        titles = [t for t, _ in gi_plate.open_questions()]
        self.assertIn("화질을 정하는 것은 처짐이 아니라 이송 흐림이다", titles)


if __name__ == "__main__":
    unittest.main()
