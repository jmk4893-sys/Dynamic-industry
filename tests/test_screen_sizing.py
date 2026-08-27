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
    def test_column_operating_point_is_inside_the_shape_band(self):
        """CC-01 의 v_super 가 형상 반영 밴드(0.81~0.95 m/s) 안에 있는지.

        형상 반영: 체는 중간축 I 를 재므로 부피등가 구경 d_eq = I·(I/L·S/I)^(1/3).
        구리 하한은 최소 구리(75 µm), 비구리 상한은 최대 백시트(250 µm)로 잡는다.
        """
        col = ss.CONFIG["column"]
        d = ss.CONFIG["density"]
        # sieve_sim.SHAPE 과 같은 값 (구리 elong .60 flat .50 / 백시트 .70 .35)
        cu_deq = col["lo_um"] * (1 / 0.60 * 0.50) ** (1 / 3.0)
        bs_deq = col["hi_um"] * (1 / 0.70 * 0.35) ** (1 / 3.0)
        cu_lo = ss.vt(d["구리"], cu_deq * 1e-6)[0]
        non_hi = ss.vt(d["백시트+EVA"], bs_deq * 1e-6)[0]
        self.assertGreater(cu_lo, non_hi, "형상 반영 밴드가 열려 있어야 한다")
        self.assertLess(col["v_super"], cu_lo, "구리가 경량측으로 새면 안 된다")

    def test_sphere_band_is_closed_at_gravity(self):
        """구형 가정으로는 1g 밴드가 닫힌다 — 컬럼 채택이 형상에 걸려 있음을 고정.

        §10 형상 실측이 결정 게이트인 이유다. 이 테스트가 깨진다면(구형으로도
        밴드가 열린다면) 문서의 리스크 서술을 지워야 한다.
        """
        col = ss.CONFIG["column"]
        cu_lo, non_hi, _ = ss.separation_bounds(col["lo_um"], col["hi_um"], ss.G)
        self.assertLess(cu_lo, non_hi)

    def test_turbo_regime_is_self_inconsistent(self):
        """터보 폐기 근거 고정 — 이 컷에서 v_r 이 휠 주속을 넘고, rpm 증가로 악화.

        컷 조건(원심 종말속도 = v_r)은 입자가 휠과 동반회전할 때만 성립한다.
        v_r > ωR 이면 공기가 날개 사이를 곧장 가로질러 전제가 깨진다.
        """
        import math
        R = ss.CONFIG["wheel_radius_m"]
        ratios = []
        for rpm in (220, 900):
            w = 2 * math.pi * rpm / 60.0
            cu, non, _ = ss.separation_bounds(75, 250, w * w * R)
            ratios.append((w * R) / math.sqrt(cu * non))
        self.assertLess(ratios[0], 1.0, "220 rpm 에서 이미 ωR < v_r 이어야 한다")
        self.assertLess(ratios[1], ratios[0] + 0.05,
                        "rpm 을 올려도 비율이 개선되지 않아야 한다")

    def test_column_loading_within_limit(self):
        col = ss.CONFIG["column"]
        self.assertLessEqual(col["loading_kgm3"], 0.5)

    def test_classifier_sized_for_misplaced_fines_too(self):
        """분급기 부하는 체가 흘려보낸 미분까지 포함해야 한다."""
        b = ss.three_product_balance()
        nominal = sum(ss.CONFIG["split"][k] for k in ("106~200", "75~106")) * b["feed"]
        self.assertGreater(b["tc_feed"], nominal, "미분 이월분이 빠져 있다")


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

    def test_recoveries_meet_targets_conservatively(self):
        """간이수지(보수 모델 보정)가 목표선 위에 있는지 — Cu ≥90, BS ≥95, Si ≥85.

        구리 93.4 % 는 베드 부하 보정(보수) 모델값이다. 무보정 모델은 98.6 %
        — 실제는 이 사이이며 §10 파일럿(4-5 비교체질)이 확정한다.
        """
        b = ss.three_product_balance(scalp_eff=0.0)
        self.assertGreater(b["구리_회수율"], 0.90)
        self.assertGreater(b["백시트_회수율"], 0.95)
        self.assertGreater(b["은_회수율"], 0.85)

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
