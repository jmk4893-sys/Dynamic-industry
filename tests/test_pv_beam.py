"""보 유한요소의 **검증** — 닫힌해와 맞는가, 수렴하는가, 에너지가 맞는가.

수치해석은 답을 내는 것이 쉽고 **맞는 답인지 아는 것**이 어렵다. 그래서 여기서는
정해가 있는 문제만 골라 푼다. 이 시험이 통과하는 한, `afr_peel` 이 내는 박리
형상과 화면의 XPBD 상수는 검증된 코드에서 나온 것이다.

  ① 외팔보 선단하중 δ = FL³/3EI · σ = FLc/I   (Hermite 요소는 절점에서 정확하다)
  ② 외팔보 등분포 δ = wL⁴/8EI
  ③ 단순지지 등분포 δ = 5wL⁴/384EI
  ④ 반무한 탄성지지 보의 단부하중 w(0) = 2Pβ/k · β = (k/4EI)^¼
  ⑤ 외팔보 1차 고유진동수 f₁ = (1.875104)²/2π · √(EI/ρAL⁴)
  ⑥ Newmark 자유진동의 주기가 ⑤ 와 맞고, 감쇠 0 에서 진폭이 유지되는가
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr_peel, beam, frames

E, I, A, C, RHO = 69_000.0, 41_882.0, 100.0, 17.5, 2.70e-9
SECTION = beam.Section(E, I, A, C, RHO, 160.0)
EI = E * I


def cantilever(n: int = 20, length: float = 1000.0) -> beam.Beam:
    return beam.Beam(SECTION, length, n)


class TestClosedFormAgreement(unittest.TestCase):
    """정해가 있는 네 문제 — 여기서 어긋나면 아래 것은 전부 못 믿는다."""

    def test_cantilever_tip_load(self):
        b = cantilever()
        u = b.solve_static(loads={b.ndof - 2: -1000.0}, prescribed={0: 0.0, 1: 0.0})
        want = -1000.0 * 1000.0 ** 3 / (3 * EI)
        self.assertAlmostEqual(b.deflection(u)[-1] / want, 1.0, places=8)
        # 고정단 굽힘응력도 정해와 맞는다 (요소 중앙값이라 반 요소만큼 안쪽이다)
        moment = 1000.0 * (1000.0 - b.le / 2)
        self.assertAlmostEqual(b.max_stress_mpa(u) / SECTION.stress_mpa(moment), 1.0, places=6)

    def test_cantilever_udl(self):
        b = cantilever(40)
        u = b.solve_static(prescribed={0: 0.0, 1: 0.0}, udl_n_mm=-1.0)
        want = -1.0 * 1000.0 ** 4 / (8 * EI)
        self.assertAlmostEqual(b.deflection(u)[-1] / want, 1.0, places=8)

    def test_simply_supported_udl(self):
        b = cantilever(40)
        u = b.solve_static(prescribed={0: 0.0, b.ndof - 2: 0.0}, udl_n_mm=-1.0)
        want = -5 * 1.0 * 1000.0 ** 4 / (384 * EI)
        self.assertAlmostEqual(b.deflection(u)[20] / want, 1.0, places=8)

    def test_semi_infinite_beam_on_elastic_foundation(self):
        f = beam.Foundation(2.0, 8.0, 3.0, 0.6)
        bet = f.beta_1_mm(SECTION)
        b = beam.Beam(SECTION, 12.0 / bet, 240, f)
        u = b.solve_static(loads={0: -1000.0})
        want = -2 * 1000.0 * bet / f.k_n_mm2
        self.assertAlmostEqual(b.deflection(u)[0] / want, 1.0, places=4)

    def test_fundamental_frequency(self):
        b = cantilever(24)
        want = (1.875104 ** 2) / (2 * math.pi) * math.sqrt(EI / (SECTION.rho_a * 1000.0 ** 4))
        self.assertAlmostEqual(b.fundamental_hz((0, 1)) / want, 1.0, places=5)


class TestConvergenceAndEnergy(unittest.TestCase):

    def test_the_foundation_solution_converges(self):
        f = beam.Foundation(2.0, 8.0, 3.0, 0.6)
        length = 12.0 / f.beta_1_mm(SECTION)
        got = []
        for n in (30, 60, 120, 240):
            b = beam.Beam(SECTION, length, n, f)
            got.append(b.deflection(b.solve_static(loads={0: -1000.0}))[0])
        # 요소를 배로 늘릴 때마다 남은 오차가 줄어든다
        errs = [abs(g - got[-1]) for g in got[:-1]]
        self.assertTrue(all(errs[i] > errs[i + 1] for i in range(len(errs) - 1)), errs)
        self.assertLess(errs[-1] / abs(got[-1]), 1e-4)

    def test_strain_energy_equals_the_work_done(self):
        """½uᵀKu = ½F·δ — 에너지가 맞으면 강성 조립이 맞다."""
        b = cantilever(30)
        f = -1000.0
        u = b.solve_static(loads={b.ndof - 2: f}, prescribed={0: 0.0, 1: 0.0})
        work = 0.5 * f * b.deflection(u)[-1]
        self.assertAlmostEqual(b.strain_energy(u) / work, 1.0, places=6)


class TestTransient(unittest.TestCase):
    """Newmark 평균가속도법 — 주기가 맞고, 감쇠 0 에서 에너지가 유지되는가."""

    def test_free_vibration_period_matches_the_mode(self):
        b = cantilever(20)
        f1 = b.fundamental_hz((0, 1))
        dt = 1.0 / (f1 * 400)
        u0 = b.solve_static(loads={b.ndof - 2: -1000.0}, prescribed={0: 0.0, 1: 0.0})
        hist = beam.newmark(b, int(3.2 / (f1 * dt)), dt,
                            force=lambda s, t: [0.0] * b.ndof,
                            prescribed={0: 0.0, 1: 0.0}, damping_ratio=0.0, u0=u0)
        tip = [h[b.ndof - 2] for h in hist]
        zc = [i for i in range(1, len(tip)) if tip[i - 1] < 0 <= tip[i]]
        self.assertGreaterEqual(len(zc), 3)
        period = (zc[-1] - zc[0]) / (len(zc) - 1) * dt
        self.assertAlmostEqual(1.0 / period / f1, 1.0, delta=0.01)

    def test_undamped_amplitude_is_preserved(self):
        b = cantilever(16)
        f1 = b.fundamental_hz((0, 1))
        dt = 1.0 / (f1 * 200)
        u0 = b.solve_static(loads={b.ndof - 2: -1000.0}, prescribed={0: 0.0, 1: 0.0})
        hist = beam.newmark(b, int(2.0 / (f1 * dt)), dt,
                            force=lambda s, t: [0.0] * b.ndof,
                            prescribed={0: 0.0, 1: 0.0}, damping_ratio=0.0, u0=u0)
        tip = [h[b.ndof - 2] for h in hist]
        self.assertAlmostEqual(min(tip) / tip[0], 1.0, delta=0.002)


    def test_the_load_is_read_at_the_step_it_arrives_at(self):
        """한 걸음이 푸는 평형은 **도착 시각**의 것이다.

        출발 시각의 하중을 넣으면 하중이 통째로 한 걸음 밀린다. t=0 에 0 이고
        그 뒤 걸리는 하중(충격이 t=0+ 에 시작하는 경우)이면 보가 첫 걸음 동안
        가만히 있어, 되튐·충격 같은 과도응답이 dt 만큼 늦게 나온다.
        """
        b = beam.Beam(SECTION, 1000.0, 4)
        fixed, tip, dt = {0: 0.0, 1: 0.0}, b.ndof - 2, 1.0e-4
        seen = []

        def force(step, t):
            seen.append(step)
            f = [0.0] * b.ndof
            if t > 0.0:
                f[tip] = -100.0
            return f

        hist = beam.newmark(b, 3, dt, force, prescribed=fixed, damping_ratio=0.0)
        self.assertNotEqual(hist[1][tip], 0.0,
                            "하중이 걸린 첫 걸음에 보가 안 움직였다")
        # out[i] 와 force(i, i·dt) 가 같은 시각을 가리킨다.
        self.assertEqual(sorted(set(seen)), list(range(len(hist))))


class TestCohesiveBond(unittest.TestCase):
    """접착은 이중선형 응집영역이다 — 강도로 자르기만 하면 균열이 달아난다."""

    def test_the_softening_branch_is_the_bilinear_law(self):
        f = beam.Foundation(2.0, 8.0, 3.0, 0.6, gc_n_mm2=0.8)
        d0, df = f.break_deflection_mm, f.separation_mm()
        self.assertLess(d0, df)
        self.assertAlmostEqual(0.5 * f.strength_n_mm * df, f.gc_n_mm(), places=9)
        self.assertAlmostEqual(f.damage_stiffness(d0 * 0.5), f.k_n_mm2)
        self.assertEqual(f.damage_stiffness(df * 1.01), 0.0)
        mid = 0.5 * (d0 + df)
        self.assertAlmostEqual(f.damage_stiffness(mid) * mid,
                               f.strength_n_mm * (df - mid) / (df - d0), places=9)

    def test_damage_never_heals(self):
        f = beam.Foundation(2.0, 8.0, 3.0, 0.6, gc_n_mm2=0.8)
        b = beam.Beam(SECTION, 1000.0, 20, f)
        before = list(b.k_eff)
        b.update_damage([10.0 if i % 2 == 0 else 0.0 for i in range(b.ndof)])
        damaged = list(b.k_eff)
        self.assertLess(min(damaged), min(before) + 1e-9)
        b.update_damage([0.0] * b.ndof)          # 되돌려도 강성은 안 돌아온다
        self.assertEqual(b.k_eff, damaged)

    def test_pushing_the_bead_does_not_peel_it(self):
        """눌러서는 안 뜯긴다 — 응집법칙은 **벌림** 쪽만 본다.

        크기(abs)만 보면 보가 시소처럼 기울 때 눌리는 반대쪽 끝을 박리로 읽어,
        접착이 전선에서 멀리 떨어진 곳에서 끊긴다.
        """
        f = beam.Foundation(2.0, 8.0, 3.0, 0.6, gc_n_mm2=0.8)
        df = f.separation_mm()
        self.assertEqual(f.damage_stiffness(-df * 10.0), f.k_n_mm2)
        self.assertEqual(f.damage_stiffness(df * 10.0), 0.0)

        b = beam.Beam(SECTION, 1000.0, 20, f)
        squash = [-10.0 if i % 2 == 0 else 0.0 for i in range(b.ndof)]
        self.assertFalse(b.update_damage(squash), "누르기만 했는데 손상이 생겼다")
        self.assertTrue(all(b.bonded))

    def test_the_opening_sign_follows_the_driver(self):
        """구동단이 음의 방향으로 당겨도 벌림은 벌림이다."""
        f = beam.Foundation(2.0, 8.0, 3.0, 0.6, gc_n_mm2=0.8)
        b = beam.Beam(SECTION, 1000.0, 20, f)
        pull_down = [-10.0 if i % 2 == 0 else 0.0 for i in range(b.ndof)]
        self.assertTrue(b.update_damage(pull_down, opening_sign=-1.0))


class TestAfrPeelModel(unittest.TestCase):
    """AFR 하중 케이스 — 단면·접착·안정성이 서로 맞는가."""

    def test_the_section_comes_from_one_polygon(self):
        s = afr_peel.section()
        p = frames.profile()
        self.assertEqual(s.i_mm4, p["i_lateral_mm4"])
        self.assertEqual(s.area_mm2, p["area_mm2"])
        self.assertAlmostEqual(s.rho_a * 1e6, frames.profile_mass_kg_m(), places=3)

    def test_the_decay_length_sets_the_visible_curve(self):
        d = afr_peel.decay_length_mm()
        self.assertGreater(d, 100.0)                      # 화면에서 보일 만큼 길다
        self.assertLess(d, afr_peel.long_edge_length_mm())  # 변보다는 짧다
        b, s = afr_peel.bond(), afr_peel.section()
        self.assertAlmostEqual(d, 1.0 / (b.k_n_mm2 / (4 * s.ei)) ** 0.25, places=1)

    def test_the_stability_ratio_is_reported_not_assumed(self):
        """설계 인발력이 정상박리력보다 크면 균열이 앞질러 달린다 — 숨기지 않는다."""
        self.assertAlmostEqual(afr_peel.stability(),
                               frames.PEEL_FORCE_N / afr_peel.steady_peel_force_n(), places=3)
        self.assertEqual(afr_peel.peel_is_stable(), afr_peel.stability() <= 1.0)
        self.assertGreater(afr_peel.released_at_end_opening_mm(), 0.0)

    def test_the_short_edge_lag_is_the_bar_sag(self):
        """단변 지연은 쇠막대 처짐이다 — 유한요소와 닫힌식이 같은 자릿수여야 한다."""
        from pv_preprocess import afr
        self.assertAlmostEqual(afr_peel.short_edge_lag_mm(), afr.bar_sag_mm(), delta=0.05)

    def test_the_frame_springs_back(self):
        self.assertFalse(afr_peel.long_edge_yields())
        self.assertLess(afr_peel.long_edge_peak_stress_mpa(), frames.YIELD_MPA)

    def test_the_fem_and_the_browser_peel_the_same_sealant(self):
        """유한요소의 접착과 화면에 넘기는 상수가 **같은 실란트**여야 한다.

        `bond()` 에 Gc 를 안 넘기면 `Foundation` 이 삼각형 넓이에서 되짚어
        δ_f = δ₀ 로 만든다 — 브라우저는 선언값 0.8 N/mm 로 무른 실란트를 벗기고,
        유한요소는 꼬리가 없는 취성 접착을 자르는 서로 다른 물건이 된다.
        """
        b, si = afr_peel.bond(), afr_peel.physics_si()
        self.assertEqual(b.gc_n_mm2, afr_peel.SEALANT_GC_N_MM)
        # physics_si 는 m 로 7 자리에서 반올림한다 — µm 이면 같은 실란트다.
        self.assertAlmostEqual(b.separation_mm(), si["bondSep"] * 1000.0, places=3)
        self.assertAlmostEqual(b.break_deflection_mm, si["bondBreak"] * 1000.0, places=3)
        self.assertGreater(b.separation_mm(), b.break_deflection_mm * 1.5,
                           "연화 구간이 없으면 균열이 한 요소씩 나아가지 않는다")

    def test_the_release_never_skips_ahead_of_the_front(self):
        """해방은 전선에서 이어진다 — 멀리 떨어진 요소가 혼자 끊기면 안 된다.

        시소처럼 기운 보의 **눌리는** 끝을 박리로 읽으면 접착이 전선과 상관없는
        자리에서 끊기고, 전선 좌표가 남지도 않은 접착을 가리킨다.
        """
        b = afr_peel.new_long_beam(afr_peel.LONG_ELEMENTS)
        from pv_preprocess import afr
        pull = float(afr.pull_travel_mm())
        for i in range(1, 13):
            beam.peel(b, 0, pull * i / 12.0, force_cap_n=frames.PEEL_FORCE_N)
            lead = 0
            while lead < b.n_el and not b.bonded[lead]:
                lead += 1
            islands = [e for e in range(lead, b.n_el) if not b.bonded[e]]
            self.assertEqual(islands, [], f"벌림 {pull * i / 12.0:.1f} mm 에서 전선"
                                          f" 0..{lead - 1} 앞쪽 접착이 끊겼다")

    def test_the_browser_gets_si_constants(self):
        si = afr_peel.physics_si()
        s = afr_peel.section()
        self.assertAlmostEqual(si["ei"], s.ei / 1e6, places=3)      # N·mm² → N·m²
        self.assertAlmostEqual(si["ea"], s.ea, places=1)
        self.assertAlmostEqual(si["rhoA"], frames.profile_mass_kg_m(), places=6)
        self.assertGreater(si["bondSep"], si["bondBreak"])

    def test_the_front_curve_only_moves_forward(self):
        curve = afr_peel.front_curve(9)
        xs = [x for _, x in curve]
        self.assertEqual(xs, sorted(xs), "균열 전선이 되돌아갔다")
        self.assertLessEqual(xs[-1], afr_peel.long_edge_length_mm() / 1000.0)


if __name__ == "__main__":
    unittest.main()
