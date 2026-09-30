# -*- coding: utf-8 -*-
"""엔드링 FEA — 푼 것을 믿을 근거를 먼저 만든다.

이 해석의 결론은 **지금 단면이 필요보다 훨씬 크다**는 것이고, 그 말은 곧
"깎아도 된다" 는 말이라 근거가 헐거우면 안 된다. 그래서 넷으로 나눈다:

  · **요소가 맞는가** — 닫힌 해 셋과 맞는지, 요소를 늘려도 안 변하는지.
  · **푼 것이 평형인가** — 반력 합이 실린 하중과 같은지.
  · **결론이 유도된 것인가** — 값을 흔들면 결론이 따라 움직이는지.
  · **모르는 것을 모른다고 하는가** — 보요소가 못 보는 자리가 기록에 있는지.

닫힌 해 검증에서 처짐만 2 % 남짓 어긋나는데, 그것은 오차가 아니라 **축변형**
이다. 고전식은 굽힘만 센다. 그 차이를 예측해서 맞추는 것까지가 검증이다.
"""

from __future__ import annotations

import math
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import (afr, campaign, drives, dynamics, fabrication,
                           kinematics, ring, safety, smart)


class TestTheElement(unittest.TestCase):
    def test_a_cantilever_matches_the_closed_form_exactly(self):
        """PL³/3EI 는 오일러–베르누이 요소의 **정확해**다 — 여기서 틀리면 끝이다."""
        E, A, I, L, P, n = 210_000.0, 5_000.0, 2e7, 2_000.0, 1_000.0, 8
        fr = ring.Frame(E, A, I)
        ns = [fr.node(L * k / n, 0.0) for k in range(n + 1)]
        for k in range(n):
            fr.beam(ns[k], ns[k + 1])
        big = ring.PENALTY * E * A / (L / n)
        fr.restrain(ns[0], 1, 0, big)
        fr.restrain(ns[0], 0, 1, big)
        fr.fix_rotation(ns[0], big * L * L)
        fr.load(ns[-1], fy=-P)
        u = fr.solve()
        self.assertAlmostEqual(u[3 * ns[-1] + 1], -P * L ** 3 / (3 * E * I),
                               places=6)

    def test_a_ring_squeezed_across_a_diameter_matches_the_closed_form(self):
        """지름으로 누른 링 — 하중점 WR/π, 90° 에서 WR(1/2 − 1/π).

        곡률이 틀리면 이 둘이 안 맞는다. 하중점 쪽이 **더 큰** 것이 맞다 —
        집중하중 자리에서 전단이 뛰므로 모멘트 기울기가 거기서 가장 크다.
        """
        m_load, m_90, _, _ = _ring_case(192)
        self.assertAlmostEqual(m_load, 1 / math.pi, places=3)
        self.assertAlmostEqual(m_90, 0.5 - 1 / math.pi, places=3)
        self.assertGreater(m_load, m_90)

    def test_the_diametral_deflection_matches_bending_plus_axial(self):
        """고전식 (π/4 − 2/π)WR³/EI 에 **축변형** πRW/4EA 를 더해야 맞는다.

        2.6 % 차이를 "수치오차" 로 넘기면 나중에 진짜 오차를 못 알아본다.
        """
        E, A, I, R, W = 210_000.0, 5_000.0, 2e7, 900.0, 1_000.0
        _, _, dy, dx = _ring_case(192)
        norm = W * R ** 3 / (E * I)
        bend = (math.pi / 4 - 2 / math.pi)
        axial = math.pi * R * W / (4 * E * A) / norm
        self.assertAlmostEqual(abs(dy) / norm, bend + axial, places=4)
        # 수직 지름은 축변형이 반대로 작용해 고전식보다 작다
        self.assertLess(abs(dx) / norm, 2 / math.pi - 0.5)
        self.assertGreater(abs(dx) / norm, (2 / math.pi - 0.5) * 0.97)

    def test_the_mesh_converges(self):
        coarse = ring.analyse(0.0, None, None, None, 36)["peakMpa"]
        fine = ring.analyse(0.0, None, None, None, 72)["peakMpa"]
        self.assertLess(abs(fine - coarse) / fine, 0.01,
                        f"{coarse:.4f} → {fine:.4f} MPa 로 움직인다")

    def test_the_solved_ring_is_in_equilibrium(self):
        """반력 합이 실린 하중과 같아야 한다 — 벌칙 구속을 믿을 근거."""
        for phi in (0.0, 45.0, 90.0):
            with self.subTest(phi=phi):
                self.assertLess(ring.equilibrium_error(phi), 1e-3)


class TestTheValuesAreRead(unittest.TestCase):
    def test_the_section_comes_from_the_drawing_book(self):
        part = dynamics._part(ring.SHEET, "BFC-RNG-01")
        self.assertEqual(ring.tube_od_mm(), float(part.size[1]))
        self.assertEqual(ring.tube_t_mm(), float(part.t))
        self.assertIn("원관", part.process, "링은 각관이 아니라 원관이다")

    def test_the_runout_comes_from_the_process_text(self):
        """판정선이 제작 공정에서 온다 — 여기 0.25 를 다시 적지 않는다."""
        self.assertEqual(ring.runout_mm(), 0.25)
        self.assertIn("런아웃", dynamics._part(ring.SHEET, "BFC-RNG-01").process)

    def test_the_mass_matches_the_drawing_book(self):
        """단면에서 낸 질량이 부품표 중량과 같아야 한다 — 두 곳이 갈라지면 안 된다."""
        part = dynamics._part(ring.SHEET, "BFC-RNG-01")
        self.assertLess(abs(ring.ring_mass_kg() - part.weight_kg())
                        / part.weight_kg(), 0.02)

    def test_the_ring_inertia_is_the_one_drives_counts(self):
        """`drives.flip_inertia_kgm2()` 의 링 항과 같은 값이어야 한다."""
        by = {p.tag: p.weight_kg()
              for p in fabrication.assembly(ring.SHEET).parts}
        want = 2 * by["BFC-RNG-01"] * (kinematics.RING_R_MM / 1_000.0) ** 2
        self.assertLess(abs(ring.ring_inertia_kgm2() - want) / want, 0.02)

    def test_the_jaw_load_is_the_rotating_mass_minus_the_rings(self):
        """조 하중을 여기서 다시 세지 않는다 — `drives` 가 이미 세어 두었다."""
        rings = 2 * dynamics._part(ring.SHEET, "BFC-RNG-01").weight_kg()
        hung = drives.flip_rotating_kg() - rings
        self.assertAlmostEqual(ring.jaw_load_per_ring_n(),
                               hung / 2 * dynamics.G, places=3)

    def test_the_life_comes_from_the_campaign_and_the_mission_time(self):
        """반복 수를 리터럴로 두면 캠페인이 바뀌어도 안 따라온다."""
        c = campaign.summary()
        want = (c["throughput_per_h"] * c["flipped"] / c["panels"]
                * smart.OPERATING_HOURS_PER_YEAR * safety.MISSION_TIME_YEARS)
        self.assertAlmostEqual(ring.design_cycles(), want, places=3)

    def test_the_modulus_comes_from_afr(self):
        self.assertEqual(ring.Frame(afr.STEEL_E_MPA, 1, 1).e, afr.STEEL_E_MPA)


class TestWhatTheAnswerIs(unittest.TestCase):
    def test_global_bending_is_nowhere_near_the_limit(self):
        """이것이 OI-02 의 답이다 — 전역 굽힘이 이 링을 정하지 않는다."""
        s = ring.summary()
        self.assertLess(s["staticMpa"], s["staticAllowMpa"] * 0.05)
        self.assertLess(s["rangeMpa"], s["fatigueAllowMpa"] * 0.05)
        self.assertTrue(ring.bending_is_not_what_sizes_the_ring())

    def test_the_deflection_does_not_eat_the_runout(self):
        s = ring.summary()
        self.assertLessEqual(s["radialMm"], s["runoutMm"])
        self.assertLess(s["radialMm"], s["runoutMm"] * 0.25)

    def test_both_rollers_stay_loaded_through_the_turn(self):
        """하나가 뜨면 가이드 롤러가 받아야 하고, 그러면 다른 해석이 된다."""
        self.assertTrue(ring.rollers_stay_in_compression())
        self.assertGreater(ring.rotation_sweep()["minRollerN"], 0.0)

    def test_the_stress_reverses_as_it_turns(self):
        """응력범위가 정적 최대보다 커야 한다 — 안 그러면 뒤집힘을 안 센 것이다."""
        sw = ring.rotation_sweep()
        self.assertGreater(sw["worstRangeMpa"], sw["peakStaticMpa"])

    def test_the_turning_inertia_does_not_change_the_load_case(self):
        """도는 동안의 접선 관성력이 자중에 비해 작다 — 자중 해석으로 충분하다."""
        self.assertLess(ring.dynamic_amplification(), 0.05)

    def test_the_section_is_class_one(self):
        self.assertLessEqual(ring.dt_class(), 2)
        self.assertEqual(ring.dt_class(180.0, 1.5), 4, "얇은 벽은 4 등급이어야 한다")

    def test_a_much_smaller_section_still_passes(self):
        small = ring.smallest_section()
        self.assertIsNotNone(small)
        self.assertLess(small["massKg"], ring.ring_mass_kg() * 0.5)
        self.assertTrue(small["ok"])

    def test_the_local_wall_is_what_binds_first_today(self):
        """전역이 아니라 **롤러 밑 관 벽**이 먼저 찬다 — 그 사실이 결론의 핵심이다."""
        self.assertEqual(ring.verdict(ring.tube_od_mm(), ring.tube_t_mm())["binding"],
                         "롤러 밑 관 벽")

    def test_thinning_the_wall_raises_the_local_stress_fastest(self):
        """벽을 얇게 하면 국부응력이 t² 로 오른다 — 전역은 거의 안 움직인다."""
        thick = ring.verdict(180.0, 10.0)
        thin = ring.verdict(180.0, 6.0)
        self.assertGreater(thin["wallMpa"] / thick["wallMpa"], 2.0)
        self.assertLess(thin["staticMpa"] / thick["staticMpa"], 1.3)


class TestTheThingsThatMoveTheAnswer(unittest.TestCase):
    def test_the_support_angle_actually_matters(self):
        """모델에 없던 값이라 **얼마나 예민한지**를 못 박아 둔다."""
        rows = ring.support_sweep()
        radial = [r["radialMm"] for r in rows]
        self.assertGreater(max(radial) / min(radial), 2.0,
                           "반각이 처짐을 두 배도 안 바꾸면 감도 표를 볼 이유가 없다")
        self.assertTrue(any(r["halfDeg"] == ring.SUPPORT_HALF_ANGLE_DEG
                            for r in rows), "쓰는 값이 표에 없다")

    def test_a_narrower_support_raises_the_moment(self):
        """좁게 받치면 링이 더 휜다 — 물리가 맞는 방향인지."""
        rows = {r["halfDeg"]: r for r in ring.support_sweep()}
        self.assertGreater(rows[15.0]["radialMm"], rows[30.0]["radialMm"])
        self.assertLess(rows[15.0]["rollerN"], rows[30.0]["rollerN"])

    def test_changing_the_drawing_book_changes_the_answer(self):
        """부품표를 바꿨는데 답이 그대로면 어딘가 리터럴이 남아 있다."""
        part = dynamics._part(ring.SHEET, "BFC-RNG-01")
        keep = part.size
        before = ring.summary()["staticMpa"]
        try:
            object.__setattr__(part, "size", (1_800, 120, 10))
            ring.clear_caches()
            self.assertEqual(ring.tube_od_mm(), 120.0)
            self.assertGreater(ring.rotation_sweep()["peakStaticMpa"], before)
        finally:
            object.__setattr__(part, "size", keep)
            ring.clear_caches()
        self.assertAlmostEqual(ring.summary()["staticMpa"], before, places=6)

    def test_the_smaller_section_buys_takt(self):
        """관성이 줄면 마찰 롤러 여유가 늘어야 한다 — 이 항목의 값어치다."""
        t = ring.takt_after_reduction()
        self.assertGreater(t["newScale"], t["nowScale"] * 1.3)
        self.assertEqual(t["nowScale"], dynamics.takt_headroom()[0])
        self.assertEqual(t["nowBinding"], dynamics.takt_headroom()[1])

    def test_the_drive_radius_works_against_the_saving(self):
        """지름을 줄이면 마찰 롤러의 팔이 짧아진다 — 이득만 세면 안 된다."""
        v = ring.inertia_saving()
        self.assertLess(v["driveRadiusNewM"], v["driveRadiusNowM"])
        self.assertLess(v["preloadRatio"], 1.0)
        self.assertGreater(v["preloadRatio"], v["totalNewKgm2"] / v["totalNowKgm2"],
                           "반지름 손해가 반영이 안 됐다")


class TestItSaysWhatItCannotSee(unittest.TestCase):
    def test_the_beam_model_admits_its_blind_spot(self):
        """셸 응력·용접 노치를 못 본다는 사실이 주석에 있어야 한다."""
        text = " ".join(ring.annotations())
        for token in ("셸", "국부", "상한", "OI-02"):
            self.assertIn(token, text, f"주석에 {token} 이 없다")

    def test_the_wall_stress_is_labelled_an_upper_bound(self):
        import inspect
        src = inspect.getsource(ring.wall_stress_mpa)
        self.assertIn("보수적", src)
        self.assertIn("0.318", inspect.getsource(ring.wall_stress_mpa)
                      + inspect.getdoc(ring.wall_stress_mpa))

    def test_the_support_angle_is_marked_as_new(self):
        import inspect
        src = inspect.getsource(ring)
        i = src.find("SUPPORT_HALF_ANGLE_DEG = ")
        self.assertIn("모델 어디에도 없던 값", src[max(0, i - 400):i])

    def test_every_check_passes_today(self):
        for name, ok, why in ring.checks():
            with self.subTest(check=name):
                self.assertTrue(ok, f"{name} — {why}")


class TestItIsRegistered(unittest.TestCase):
    def test_the_open_item_carries_the_answer(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-02")
        text = item.title + item.why_open + item.closes_with + item.blocks
        for token in ("ring.py", "셸", "택트"):
            self.assertIn(token, text, f"OI-02 에 {token} 이 없다")

    def test_the_open_item_calls_the_ring_a_round_tube(self):
        """부품표는 Ø180 원관이라고 적혀 있는데 미결 항목만 각관이라고 했다.

        고친 것을 **고쳤다고 적어 두는 것**까지가 정정이다 — 값만 바꾸면
        다음 사람이 같은 오해를 다시 한다.
        """
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-02")
        self.assertIn("원관", item.why_open)
        self.assertIn("각관이라고 적고 있었다", item.why_open,
                      "정정했다는 기록이 없다")
        self.assertIn("원관", dynamics._part(ring.SHEET, "BFC-RNG-01").process)

    def test_the_open_item_numbers_are_the_ones_the_module_computes(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-02")
        s = ring.summary()
        for value in (f"{s['staticMpa']}", f"{s['rangeMpa']}",
                      f"{s['radialMm']}", f"{s['wallMpa']}",
                      f"{s['takt']['newScale']}"):
            self.assertIn(value, item.why_open,
                          f"OI-02 이 {value} 를 안 들고 있다 — 해석과 갈라졌다")

    def test_the_open_item_carries_no_markdown(self):
        item = next(o for o in fabrication.OPEN_ITEMS if o.tag == "OI-02")
        for field in (item.title, item.why_open, item.closes_with, item.blocks):
            self.assertNotIn("**", field)


def _ring_case(n: int) -> tuple[float, float, float, float]:
    """지름으로 누른 링 — (하중점 M/WR, 90° M/WR, δ∥, δ⊥)."""
    E, A, I, R, W = 210_000.0, 5_000.0, 2e7, 900.0, 1_000.0
    fr = ring.Frame(E, A, I)
    ns = [fr.node(R * math.cos(2 * math.pi * k / n),
                  R * math.sin(2 * math.pi * k / n)) for k in range(n)]
    for k in range(n):
        fr.beam(ns[k], ns[(k + 1) % n])
    big = ring.PENALTY * E * A / (2 * math.pi * R / n)
    top, bot = n // 4, 3 * n // 4
    fr.load(ns[top], fy=-W)
    fr.load(ns[bot], fy=+W)
    fr.restrain(ns[bot], 0, 1, big)
    fr.restrain(ns[bot], 1, 0, big)
    fr.restrain(ns[top], 1, 0, big)
    u = fr.solve()
    mm = fr.end_moments(u)
    return (abs(mm[top][0]) / (W * R), abs(mm[0][0]) / (W * R),
            u[3 * ns[top] + 1] - u[3 * ns[bot] + 1],
            u[3 * ns[0]] - u[3 * ns[n // 2]])


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
