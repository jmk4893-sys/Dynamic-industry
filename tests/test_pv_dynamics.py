# -*- coding: utf-8 -*-
"""FL-101 → RB-101 시간영역 동역학 — 해석기가 스스로를 증명하게 한다.

해석 결과는 **틀려도 그럴듯해 보인다.** 숫자가 나왔다는 사실이 그 숫자가 맞다는
뜻이 아니다. 그래서 여기서 묻는 것은 「값이 이것이냐」가 아니라 넷이다:

  · **적분기가 수렴하는가** — 간격을 반으로 줄여도 답이 안 변해야 한다.
  · **다른 방법으로 낸 값과 맞는가** — `drives` 는 사다리꼴을 역산해 정격을 냈고
    여기서는 같은 축을 시간으로 감았다. 두 길이 같은 곳에 닿아야 한다.
  · **이미 문서에 적힌 값과 맞는가** — OI-05 의 낙하 에너지 163 J.
  · **물리가 제대로 들어갔는가** — 스테판 힘은 틈의 세제곱에 반비례해야 한다.

값을 리터럴로 박아 두면 이 넷 중 무엇도 확인하지 못한다.
"""

from __future__ import annotations

import importlib.util
import math
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import drives, dynamics, kinematics

ROOT = pathlib.Path(__file__).resolve().parents[1]
DYN = ROOT / "docs/drawings/pv-infeed-dyn.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestIntegrator(unittest.TestCase):
    def test_the_step_halves_without_changing_the_answer(self):
        """적분기를 믿을 유일한 근거 — 간격을 반으로 줄여도 답이 안 변한다.

        접촉이 있는 낙하가 가장 뻣뻣하므로 거기서 본다. 여기서 안 수렴하면
        최대 반력은 물리가 아니라 적분간격이 정한 값이다.
        """
        coarse, fine, ok = dynamics.converged(
            lambda dt: dynamics.catch_impact(dt=dt)["peakN"], 2e-5)
        self.assertTrue(ok, f"낙하 적분이 수렴하지 않는다 — {coarse:.1f} → {fine:.1f} N")

    def test_the_lift_run_is_step_independent(self):
        _c, _f, ok = dynamics.converged(
            lambda dt: dynamics.lift_run(dt=dt).peak()[0], 0.001)
        self.assertTrue(ok, "승강 적분이 간격에 따라 흔들린다")

    def test_the_profile_actually_covers_the_distance(self):
        """사다리꼴 가속도를 두 번 적분하면 행정이 나와야 한다.

        프로파일이 틀리면 그 위에 선 값이 전부 틀리는데, 힘만 봐서는 안 보인다.
        """
        total, distance, dt = 3.0, 1.2, 1e-5
        v = x = 0.0
        steps = int(round(total / dt))
        for i in range(steps):
            v += dynamics.trapezoid(i * dt, total, distance) * dt
            x += v * dt
        self.assertAlmostEqual(x, distance, places=3,
                               msg=f"프로파일이 {distance} 를 못 채운다 — {x:.4f}")
        self.assertAlmostEqual(v, 0.0, places=3, msg="끝에서 안 멈춘다")

    def test_the_peak_speed_matches_the_declared_peak_factor(self):
        """최고속도 = 평균 × 1.5 — `drives.PEAK_FACTOR` 가 적어 둔 그 프로파일이다."""
        total, distance = 3.0, 1.2
        a = dynamics.trapezoid(0.0, total, distance)
        peak = a * (total / 3.0)
        self.assertAlmostEqual(peak, distance / total * drives.PEAK_FACTOR, places=6)


class TestCrossCheck(unittest.TestCase):
    def test_the_lift_torque_agrees_with_the_sizing(self):
        """시간으로 감은 값이 `drives` 의 정격 산정과 만나야 한다.

        두 모듈이 같은 축을 다른 길로 계산한다 — 한쪽은 프로파일을 역산했고
        한쪽은 감았다. 답이 갈라지면 둘 중 하나가 틀린 것이고, 갈라진 채로
        두면 어느 쪽이 도면에 실렸는지 아무도 모르게 된다.
        """
        _rms, sized_peak, _rated, _ok = drives.torque_checks()["AXIS-BFC-Z"]
        self.assertAlmostEqual(dynamics.lift_torque_nm(), sized_peak, places=2,
                               msg="승강 피크 토크가 정격 산정과 다르다")

    def test_the_drop_energy_is_the_one_written_in_the_open_item(self):
        """OI-05 가 문장으로 적은 163 J 이 모델에서 나와야 한다.

        문장에만 있으면 행정(안전분리 상승 370)이 바뀌어도 안 따라온다.
        """
        self.assertAlmostEqual(dynamics.double_sheet_energy_j(), 163.0, delta=1.0)

    def test_the_flip_torque_is_stricter_than_the_sizing_and_says_why(self):
        """반전 토크가 `drives` 보다 큰 것은 **프로파일이 달라서**다.

        볼스크루는 사다리꼴 1:1:1(4.5θ/t²), 마찰 롤러는 삼각(4θ/t²)으로 잡혀
        있다. 여기서는 둘 다 사다리꼴로 감으므로 반전 쪽이 12.5 % 커진다 —
        그 사실을 알고 있는지를 못 박는다.
        """
        sized = drives.friction_drives()[0].torque_nm
        integrated = dynamics.flip_slip()["demandNm"]
        self.assertGreater(integrated, sized, "사다리꼴이 삼각보다 작을 수 없다")
        self.assertAlmostEqual(integrated / sized, 4.5 / 4.0, places=3,
                               msg="두 프로파일의 비가 4.5/4 가 아니다")

    def test_the_specified_preload_still_covers_the_stricter_profile(self):
        """더 엄한 프로파일에서도 압착력 사양 400 N 이 버티는가.

        버티지 못하면 값을 바꾸는 일이 아니라 축 선정을 다시 여는 일이다.
        """
        self.assertTrue(dynamics.preload_covers_the_trapezoid(),
                        "사다리꼴 요구가 압착력 사양을 넘는다 — 설계 검토회의 감이다")


class TestSeparation(unittest.TestCase):
    def test_the_stack_gap_comes_from_the_frame_step(self):
        """적층 틈은 프레임 단차의 두 배다 — 위아래로 한 번씩."""
        self.assertEqual(dynamics.stack_gap_mm(),
                         2 * kinematics.PANEL_FRAME_GLASS_STEP_MM)

    def test_the_stefan_force_falls_with_the_cube_of_the_gap(self):
        """물리가 제대로 들어갔는가 — 틈을 두 배로 하면 힘이 1/8 이 돼야 한다.

        이 관계가 깨져 있으면 무프레임 결론도, 프레임 적층이 넉넉하다는 결론도
        둘 다 근거가 없다.
        """
        a = dynamics.stefan_force_n(4.0, 0.4)
        b = dynamics.stefan_force_n(8.0, 0.4)
        self.assertAlmostEqual(a / b, 8.0, places=6)

    def test_the_stefan_force_is_linear_in_speed(self):
        a = dynamics.stefan_force_n(8.0, 0.2)
        b = dynamics.stefan_force_n(8.0, 0.4)
        self.assertAlmostEqual(b / a, 2.0, places=6)

    def test_the_framed_stack_separates_with_margin(self):
        self.assertTrue(dynamics.sep_peel_is_enough(),
                        f"프레임 적층에서 여유 {dynamics.sep_peel()['margin']:.2f}")

    def test_a_frameless_panel_cannot_be_lifted_straight_up(self):
        """유리가 맞닿으면 같은 헤드로는 못 뗀다 — 이 해석의 결론이다.

        `recipe` 에 무프레임이 등록돼 있고 AFR 인발만 건너뛰는 것으로 적혀
        있는데, **투입부가 먼저 막힌다.** 자릿수로 막히므로 컵을 늘려 될 일이
        아니다 — 모서리부터 젖히거나 에어나이프로 틈을 먼저 만들어야 한다.
        """
        self.assertTrue(dynamics.frameless_needs_another_way())
        bare = dynamics.sep_peel(dynamics.GLASS_CONTACT_GAP_MM)
        self.assertGreater(bare["demandN"] / bare["holdN"], 1_000,
                           "자릿수로 막히는 것이 아니라면 결론을 다시 써야 한다")


class TestImpact(unittest.TestCase):
    def test_the_beam_stiffness_comes_from_the_fabrication_section(self):
        """강성이 제작 도면집의 단면에서 나오는가 — 여기 다시 적으면 갈라진다."""
        k = dynamics.catch_beam_stiffness_n_per_mm()
        self.assertGreater(k, 0)
        # RHS 100×60×3.2 · 외팔 2,900 · 4본. 단면을 키우면 강성도 커져야 한다.
        self.assertLess(k, 5_000, "강성이 비현실적으로 크다 — 단면 계산을 보라")

    def test_the_impact_force_is_not_the_energy(self):
        """에너지에서 힘으로 가는 것이 이 해석의 요점이다."""
        r = dynamics.catch_impact()
        self.assertGreater(r["peakN"], r["energyJ"] * 10,
                           "반력이 에너지 숫자를 그냥 옮긴 값처럼 보인다")
        self.assertGreater(r["deflectionMm"], 1.0, "빔이 안 휘면 힘이 무한대다")

    def test_the_contact_never_pulls(self):
        """접촉은 한 방향이다 — 빔이 패널을 당기면 그것은 접촉이 아니라 용접이다."""
        r = dynamics.catch_impact()
        self.assertGreaterEqual(r["peakN"], 0)


class TestHeadroom(unittest.TestCase):
    def test_every_check_passes_today(self):
        for name, (need, have, ok) in dynamics.checks().items():
            with self.subTest(name):
                self.assertTrue(ok, f"{name} — 요구 {need:.2f} · 능력 {have:.2f}")

    def test_the_binding_constraint_is_named(self):
        """택트를 줄일 때 **무엇이 먼저 걸리는지**가 답이어야 한다.

        「1.04 배까지 된다」보다 「마찰 롤러가 먼저 걸린다」가 다음 결정을 만든다.
        여유가 1.0 이면 이미 한계이고, 아주 크면 제약이 빠진 것이다.
        """
        head, who = dynamics.takt_headroom()
        self.assertGreaterEqual(head, 1.0, "지금 프로파일이 이미 한계를 넘는다")
        self.assertLess(head, 4.0, "여유가 무한대처럼 나온다 — 제약이 빠졌다")
        self.assertIn("-", who, f"걸리는 것에 설비 태그가 없다 — {who!r}")

    def test_speeding_up_means_shortening_the_time_not_scaling_the_accel(self):
        """구간 시간을 반으로 줄이면 가속은 네 배다 — 도착점은 그대로여야 한다.

        가속에 배율을 곱하면 같은 시간에 더 멀리 가 180° 를 지나친다. 그 정의로는
        「빠르게 돌린다」를 비교할 수 없다.
        """
        base = dynamics.flip_run()
        fast = dynamics.flip_run(takt_scale=2.0)
        self.assertAlmostEqual(base.x[-1], math.pi, places=2, msg="180° 에 안 선다")
        self.assertAlmostEqual(fast.x[-1], math.pi, places=2,
                               msg="빨리 돌렸더니 도착점이 달라졌다")
        self.assertAlmostEqual(abs(fast.peak()[0]) / abs(base.peak()[0]), 4.0, places=2,
                               msg="시간을 반으로 줄였는데 토크가 네 배가 아니다")

    def test_the_eoat_limit_is_the_smaller_of_two_directions(self):
        e = dynamics.eoat_limit_ms2()
        self.assertEqual(e["limitMs2"], min(e["verticalMs2"], e["lateralMs2"]))


class TestNoFrozenNumbers(unittest.TestCase):
    """값이 모델에서 나오는가 — 리터럴로 박혀 있으면 여기서 걸린다."""

    def test_a_heavier_panel_moves_everything(self):
        before = dynamics.summary()
        original = drives.PANEL_KG
        try:
            drives.PANEL_KG = original * 2
            after = dynamics.summary()
        finally:
            drives.PANEL_KG = original
        for key in ("peelDemandN", "impactJ", "impactPeakN", "eoatLimitMs2"):
            self.assertNotEqual(before[key], after[key], f"{key} 가 패널 무게를 안 본다")

    def test_a_wider_gap_moves_the_separation_margin(self):
        near = dynamics.sep_peel(2.0)["margin"]
        far = dynamics.sep_peel(16.0)["margin"]
        self.assertGreater(far, near, "틈이 벌어졌는데 여유가 안 늘어난다")

    def test_the_summary_reports_what_the_checks_use(self):
        s, c = dynamics.summary(), dynamics.checks()
        self.assertAlmostEqual(s["flipCapacityNm"],
                               round(c["BFC-101 롤러 미끄럼"][1], 1), places=1)


class TestDynamicsPage(unittest.TestCase):
    """영상 페이지 — 커밋본이 생성기 출력과 같은가, 그리고 **정말 물리로 도는가**.

    파이썬 시험이 볼 수 있는 것은 여기까지다. 브라우저 안에서 두 적분기가
    같은 답을 내는지는 `node tools/check_dynamics.mjs` 가 본다.
    """

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_infeed_dyn")
        cls.html = DYN.read_text(encoding="utf-8")

    def test_the_committed_page_is_what_the_builder_makes(self):
        self.assertEqual(self.html, _rebuilt(self.builder),
                         "docs/drawings/pv-infeed-dyn.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_infeed_dyn.py 를 돌리고 커밋한다")

    def test_the_page_carries_the_answer_python_computed(self):
        """파이썬이 낸 값이 페이지에 실려야 검사기가 대조할 수 있다."""
        for key in ("liftPeakNm", "flipPeakNm", "impactPeakN", "peelStefanN"):
            self.assertIn(f'"{key}"', self.html, f"{key} 가 페이지에 없다")

    def test_the_page_integrates_instead_of_replaying(self):
        """키프레임으로 되돌아가면 여기서 걸린다.

        적분기(반음시 오일러)·토크 포화·한 방향 접촉 셋이 다 있어야 이 페이지가
        「힘에서 나온 움직임」이다. 하나라도 빠지면 그냥 재생이다.
        """
        for token, why in (
            ("this.v += f / this.i * dt", "반음시 오일러 적분기"),
            ("Math.max(-cap, Math.min(cap, want))", "마찰 롤러 토크 포화"),
            ("Math.max(0, M.beamKNm", "한 방향 접촉 (빔이 당기지 않는다)"),
            ("Math.pow(r, 4)", "스테판 접착"),
        ):
            self.assertIn(token, self.html, f"{why} 가 페이지에 없다")

    def test_the_model_values_come_from_the_model(self):
        """페이지가 받는 값이 전부 모델에서 나오는가 — 손으로 적은 것이 없어야 한다."""
        m = self.builder.model()
        self.assertEqual(m["flipJ"], drives.flip_inertia_kgm2())
        self.assertEqual(m["liftKg"], drives.lift_moving_kg())
        self.assertEqual(m["dropJ"], dynamics.double_sheet_energy_j())
        self.assertEqual(m["stackGapMm"], dynamics.stack_gap_mm())
        self.assertEqual(m["expect"], dynamics.summary())


def _rebuilt(builder) -> str:
    """생성기를 돌려 본 결과 — 파일을 덮어쓰지 않고 문자열만 받는다."""
    import io
    import contextlib
    original = builder.OUT.read_bytes()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            builder.build()
        return builder.OUT.read_text(encoding="utf-8")
    finally:
        builder.OUT.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
