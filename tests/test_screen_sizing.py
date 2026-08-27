"""screen_sizing 설계식 검증.

이 모듈은 순수 파이썬이라 numpy 없이도 돌아간다 — 기본 unittest 잡이 보호한다.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import screen_sizing as ss


class CentrifugalFieldTest(unittest.TestCase):
    def test_acceleration_formula(self):
        """a = omega^2 R. 200 rpm, R=75 mm -> 약 3.4 g."""
        a = ss.centrifugal_acceleration(200, 0.075)
        self.assertAlmostEqual(a, (2 * math.pi * 200 / 60) ** 2 * 0.075, places=9)
        self.assertAlmostEqual(a / ss.G, 3.36, places=1)

    def test_field_velocity_reduces_to_gravity(self):
        """accel = g 이면 중력 종말속도와 같아야 한다."""
        for rho in (8960.0, 2500.0, 1200.0):
            for d in (75e-6, 106e-6, 200e-6):
                v_grav, _re = ss.vt(rho, d)      # vt 는 (속도, Re) 를 돌려준다
                self.assertAlmostEqual(ss.vt_in_field(rho, d, ss.G), v_grav, places=6)

    def test_velocity_monotonic_in_acceleration(self):
        prev = 0.0
        for ag in (1.0, 3.4, 7.5, 13.4):
            v = ss.vt_in_field(8960.0, 106e-6, ag * ss.G)
            self.assertGreater(v, prev)
            prev = v

    def test_diameter_inversion_round_trips(self):
        a = ss.centrifugal_acceleration(200, 0.075)
        for d_um in (60, 106, 180):
            v = ss.vt_in_field(8960.0, d_um * 1e-6, a)
            d_back = ss._diameter_at_field_velocity(8960.0, v, a) * 1e6
            self.assertAlmostEqual(d_back / d_um, 1.0, places=3)


class SeparationBoundsTest(unittest.TestCase):
    def test_silicon_binds_the_fine_fraction(self):
        """75~106 µm 에서 제약은 폴리머가 아니라 실리콘이다 (Rev.2 의 오류)."""
        a = ss.centrifugal_acceleration(200, 0.075)
        cu, worst, who = ss.separation_bounds(75, 106, a)
        self.assertIn("실리콘", who)
        self.assertGreater(cu, worst, "구리가 비구리보다 빨라야 분리가 성립한다")

    def test_backsheet_binds_the_coarse_fraction(self):
        """106~200 µm 에서는 실리콘이 120 µm 까지만 있어 백시트가 제약이 된다."""
        a = ss.centrifugal_acceleration(150, 0.075)
        _, _, who = ss.separation_bounds(106, 200, a)
        self.assertIn("백시트", who)

    def test_centrifugal_does_not_widen_the_narrow_band(self):
        """75~106 µm 에서는 원심장이 여유비를 넓히지 않는다 (§6.5).

        Rev.4 주의 — 이 성질은 **좁은 분획에서만** 성립한다. 임계 분획폭
        (밀도비의 세제곱근)을 넘으면 부호가 뒤집힌다. BandWidthTest 참조.
        """
        ratios = []
        for ag in (1.0, 3.4, 13.4):
            cu, worst, _ = ss.separation_bounds(75, 106, ag * ss.G)
            ratios.append(cu / worst)
        self.assertTrue(all(r > 1.0 for r in ratios), "어느 경우든 분리는 성립해야 한다")
        self.assertLessEqual(ratios[-1], ratios[0] + 1e-9,
                             "가속도를 키우면 여유비가 넓어지지 않아야 한다")


class OperatingPointTest(unittest.TestCase):
    def test_configured_points_are_operable(self):
        """CONFIG 의 각 분급기가 밴드 사이에 있고 고형물 부하가 한계 이내인지."""
        area = ss.wheel_area()
        peak = ss.CONFIG["peak_tph"] * 1000.0
        for tag, lo, hi, keys, rpm, v_r in ss.CONFIG["classifiers"]:
            a = ss.centrifugal_acceleration(rpm, ss.CONFIG["wheel_radius_m"])
            cu, worst, _ = ss.separation_bounds(lo, hi, a)
            self.assertLess(worst, v_r, f"{tag}: 비구리가 중량측으로 간다")
            self.assertLess(v_r, cu, f"{tag}: 구리가 경량측으로 샌다")
            q = v_r * area * 3600.0
            solids = sum(ss.CONFIG["split"][k] for k in keys) * peak
            load = solids / q
            self.assertLessEqual(load, 0.5, f"{tag}: 고형물 부하 {load:.3f} kg/m3 초과")

    def test_classifier_sized_for_misplaced_fines_too(self):
        """분급기 부하는 체가 흘려보낸 미분까지 포함해야 한다.

        75 µm 데크가 100 % 가 아니므로 분급기 공급량은 분획 합보다 크다.
        분획 합만 보고 사이징하면 실제 부하를 과소평가한다.
        """
        b = ss.three_product_balance()
        nominal = sum(ss.CONFIG["split"][k] for k in ("106~200", "75~106")) * b["feed"]
        self.assertGreater(b["tc_feed"], nominal, "미분 이월분이 빠져 있다")
        q = ss.CONFIG["classifiers"][0][5] * ss.wheel_area() * 3600.0
        self.assertLessEqual(b["tc_feed"] / q, 0.35,
                             "실부하 기준으로도 0.35 kg/m3 이내여야 한다")


class BandWidthTest(unittest.TestCase):
    """원심장이 여유비에 미치는 영향은 분획 폭에 따라 방향이 뒤집힌다."""

    def _ratio(self, lo, hi, ag):
        cu, worst, _ = ss.separation_bounds(lo, hi, ag * ss.G)
        return cu / worst

    def test_narrow_band_loses_from_centrifugal(self):
        """좁은 분획(75~106, 폭 1.41)에서는 원심장이 여유비를 좁힌다."""
        self.assertLess(self._ratio(75, 106, 16.0), self._ratio(75, 106, 1.0))

    def test_wide_band_gains_from_centrifugal(self):
        """넓은 분획(75~200, 폭 2.67)에서는 반대로 넓어진다 — Rev.4 가 220 rpm 을 쓰는 이유."""
        self.assertGreater(self._ratio(75, 200, 16.0), self._ratio(75, 200, 1.0))

    def _pair_ratio(self, lo_um, hi_um, ag):
        """구리@lo 와 백시트@hi 의 속도비. 재질 실제 입도범위 clip 없이 순수 물리만."""
        d, a = ss.CONFIG["density"], ag * ss.G
        return (ss.vt_in_field(d["구리"], lo_um * 1e-6, a)
                / ss.vt_in_field(d["백시트+EVA"], hi_um * 1e-6, a))

    def test_crossover_matches_the_cube_root_criterion(self):
        """Stokes 와 Newton 이 뒤집히는 임계 분획폭은 밀도비의 세제곱근이다.

        Stokes  여유비 = rho_r / sr^2,  Newton 여유비 = sqrt(rho_r / sr)
        두 식이 같아지는 지점이 sr = rho_r^(1/3) = 1.96 (구리/백시트).
        """
        rho_r = ss.CONFIG["density"]["구리"] / ss.CONFIG["density"]["백시트+EVA"]
        sr = rho_r ** (1.0 / 3.0)
        lo = 75.0

        def delta(width):
            hi = lo * width
            return self._pair_ratio(lo, hi, 16.0) - self._pair_ratio(lo, hi, 1.0)

        self.assertLess(delta(sr * 0.85), 0.0, "임계폭보다 좁으면 원심장이 손해여야 한다")
        self.assertGreater(delta(sr * 1.15), 0.0, "임계폭보다 넓으면 이득이어야 한다")
        self.assertAlmostEqual(delta(sr), 0.0, places=2, msg="임계폭에서는 부호가 바뀌는 중이라 0 에 가까워야 한다")


class ThreeProductBalanceTest(unittest.TestCase):
    """Rev.4 의 목적함수는 품위가 아니라 회수율이다."""

    def test_mass_balance_closes(self):
        b = ss.three_product_balance()
        total = b["P1_실리콘+은"] + b["P2_구리"] + b["P3_백시트"]
        self.assertAlmostEqual(total, b["feed"], places=6)

    def test_scalping_deck_buys_silver_recovery(self):
        """경량측 스캘핑이 은 회수율을 데크 효율 이상으로 끌어올린다."""
        without = ss.three_product_balance(scalp_eff=0.0)["은_회수율"]
        with_ = ss.three_product_balance(scalp_eff=0.90)["은_회수율"]
        self.assertAlmostEqual(without, ss.CONFIG["deck_efficiency"], places=6)
        self.assertGreater(with_, without + 0.05, "스캘핑의 기여가 5 포인트는 넘어야 한다")

    def test_silver_is_the_binding_recovery(self):
        """구리·백시트 회수율은 손댈 데가 없고, 은만 체 효율에 매여 있다."""
        b = ss.three_product_balance(scalp_eff=0.0)
        self.assertGreater(b["구리_회수율"], 0.99)
        self.assertGreater(b["백시트_회수율"], 0.99)
        self.assertLess(b["은_회수율"], b["구리_회수율"])

    def test_dropping_the_106_deck_overloads_the_critical_deck(self):
        """106 µm 데크를 빼면 75 µm 데크가 Ø1200 로는 감당되지 않는다.

        Rev.4 초안에서 '분급기가 하나면 데크도 하나 줄일 수 있다' 고 봤으나,
        106 데크는 밴드를 만드는 것이 아니라 병목 데크의 부하를 덜어 주는 역할이다.
        """
        area_1200 = ss.sieve_area(1.2)
        with_106 = ss.deck_loads()[-1][2]
        cfg = dict(ss.CONFIG)
        cfg["sieve_decks"] = [(200, 0.50), (75, 0.20)]
        without_106 = ss.deck_loads(cfg)[-1][2]
        self.assertLessEqual(with_106, area_1200, "3메쉬 유지 시에는 Ø1200 으로 충분해야 한다")
        self.assertGreater(without_106, area_1200, "106 데크를 빼면 Ø1200 이 모자라야 한다")


if __name__ == "__main__":
    unittest.main()
