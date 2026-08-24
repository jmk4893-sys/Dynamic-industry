"""모델이 문헌 실증값을 재현하는지 검증한다.

설계의 신뢰성은 전적으로 이 테스트에 달려 있다. 설계 기준을 손댔을 때
문헌과 어긋나면 여기서 실패해야 한다.
"""

import unittest

from . import _path  # noqa: F401

from flotation_design import design_basis as db
from flotation_design import references as ref
from flotation_design.plant import build_plant, solve_mechanical
from flotation_design.rfc import rfc_separation


class TestBatchKinetics(unittest.TestCase):
    """[1] 회분식 회수율-시간 곡선 재현."""

    def test_silver_kinetic_points(self):
        ag = db.FLOAT_MODELS["Ag"]
        for t_min, published in ref.BATCH_KINETIC_POINTS:
            with self.subTest(t=t_min):
                self.assertAlmostEqual(
                    ag.batch_flotation_recovery(t_min), published, delta=0.02
                )

    def test_silver_ultimate_recovery_matches_tap_water_test(self):
        self.assertAlmostEqual(
            db.FLOAT_MODELS["Ag"].r_max,
            ref.BATCH_TAP_WATER.ag_recovery_percent / 100.0,
            delta=0.005,
        )

    def test_base_metal_recoveries(self):
        t = ref.BATCH_TAP_WATER.flotation_time_min
        for metal, data in ref.BATCH_BASE_METALS.items():
            with self.subTest(metal=metal):
                self.assertAlmostEqual(
                    db.FLOAT_MODELS[metal].batch_flotation_recovery(t),
                    data["recovery_percent"] / 100.0,
                    delta=0.02,
                )

    def test_gangue_has_no_true_flotation(self):
        for name in ("Si", "Al", "Other"):
            self.assertEqual(db.FLOAT_MODELS[name].r_max, 0.0)

    def test_silver_locked_fraction_is_small(self):
        """TIMA 상 Si 내부에 완전 봉입된 Ag 는 거의 없다."""
        self.assertLess(db.FLOAT_MODELS["Ag"].nonfloating_fraction, 0.05)


class TestFeedAssays(unittest.TestCase):
    """급광 조성이 문헌 assay 와 일치하는지."""

    def test_silver_grade(self):
        self.assertAlmostEqual(
            db.FEED.grade_ppm("Ag") / 1e4,
            ref.CONTINUOUS_TRIAL.feed_ag_wt_percent,
            places=3,
        )

    def test_base_metal_grades(self):
        for metal, data in ref.BATCH_BASE_METALS.items():
            with self.subTest(metal=metal):
                self.assertAlmostEqual(
                    db.FEED.grade_ppm(metal) / 1e4, data["feed_wt_percent"], places=4
                )

    def test_particle_size_matches_continuous_trial(self):
        self.assertEqual(db.FEED.p80_micron, ref.CONTINUOUS_TRIAL.p80_micron)


class TestContinuousTrialReproduction(unittest.TestCase):
    """[2] 연속 정상상태 결과 재현."""

    @classmethod
    def setUpClass(cls):
        cls.trial = ref.CONTINUOUS_TRIAL
        cls.perf = rfc_separation(
            db.FEED.component_tph(0.5),
            db.FLOAT_MODELS,
            db.RFC_AG_RECOVERY,
            db.COMPOSITE_CARRY_RATIO,
        )

    def test_silver_recovery(self):
        self.assertAlmostEqual(
            self.perf.recovery("Ag") * 100, self.trial.ag_recovery_percent, delta=0.5
        )

    def test_mass_yield_within_10_percent(self):
        self.assertAlmostEqual(
            self.perf.mass_yield * 100, self.trial.solids_yield_percent, delta=0.15
        )

    def test_concentrate_grade_within_10_percent(self):
        published = self.trial.concentrate_ag_wt_percent
        model = self.perf.concentrate_grade("Ag") * 100
        self.assertLess(abs(model - published) / published, 0.10)

    def test_model_is_conservative_on_grade(self):
        """모델이 문헌보다 품위를 낮게 잡아야 한다 (과대평가 금지)."""
        self.assertLessEqual(
            self.perf.concentrate_grade("Ag") * 100,
            self.trial.concentrate_ag_wt_percent,
        )

    def test_gangue_recovery_matches_measurement(self):
        self.assertAlmostEqual(
            self.perf.recovery("Si"), db.RFC_GANGUE_RECOVERY, delta=0.002
        )

    def test_mass_balance_closes(self):
        self.assertLess(self.perf.mass_balance_error_tph(), 1e-12)


class TestCompositeCarryLimit(unittest.TestCase):
    """복합입자 동반이 정광 품위의 상한을 만든다."""

    def test_theoretical_limit(self):
        limit = 1.0 / (1.0 + db.COMPOSITE_CARRY_RATIO)
        # 문헌의 두 최고 품위가 모두 이 상한 근처에서 멈췄다.
        self.assertAlmostEqual(
            limit * 100, ref.CONTINUOUS_TRIAL.concentrate_ag_wt_percent, delta=3.0
        )
        self.assertAlmostEqual(
            limit * 100,
            ref.BATCH_ROUGHER_CLEANER["concentrate_ag_wt_percent"],
            delta=3.0,
        )

    def test_no_stage_can_exceed_the_limit(self):
        limit = 1.0 / (1.0 + db.COMPOSITE_CARRY_RATIO)
        plant = build_plant()
        self.assertLessEqual(
            plant.rfc.performance_peak.concentrate_grade("Ag"), limit + 1e-9
        )
        self.assertLessEqual(
            plant.mechanical.result_peak.concentrate.grade_fraction("Ag"), limit + 1e-9
        )


class TestMechanicalCircuitVsPublishedCleaner(unittest.TestCase):
    """[1] 러퍼+클리너 결과와 비교."""

    @classmethod
    def setUpClass(cls):
        cls.result = solve_mechanical(db.FEED, 0.5)

    def test_concentrate_grade_close_to_published(self):
        published = ref.BATCH_ROUGHER_CLEANER["concentrate_ag_wt_percent"]
        model = self.result.concentrate.grade_fraction("Ag") * 100
        self.assertLess(abs(model - published) / published, 0.10)

    def test_closed_circuit_beats_published_open_circuit_recovery(self):
        """저자들이 예측한 대로, 폐회로가 개방회로보다 회수율이 높아야 한다."""
        self.assertGreater(
            self.result.recovery("Ag") * 100,
            ref.BATCH_ROUGHER_CLEANER["ag_recovery_percent"],
        )

    def test_recovery_below_batch_rougher(self):
        """실기 CSTR 은 회분식보다 불리하다 — 모델이 이를 반영해야 한다."""
        self.assertLess(
            self.result.recovery("Ag") * 100, ref.BATCH_TAP_WATER.ag_recovery_percent
        )


class TestReagentBasis(unittest.TestCase):
    def test_collector_dose_matches_wet_feed_requirement(self):
        """습식 분쇄 원료는 건조 원료 최적치의 2배가 필요하다 ([2])."""
        expected = ref.BATCH_TAP_WATER.reagent_g_per_t * ref.WET_FEED_REAGENT_FACTOR
        collector = next(r for r in db.REAGENTS if "3418A" in r.name)
        self.assertAlmostEqual(collector.dose, expected, places=6)
        self.assertAlmostEqual(collector.dose, ref.CONTINUOUS_TRIAL.collector_g_per_t)

    def test_frother_is_dosed_on_water_basis(self):
        frother = next(r for r in db.REAGENTS if r.role == "기포제")
        self.assertEqual(frother.basis, "water")
        self.assertAlmostEqual(frother.dose, ref.CONTINUOUS_TRIAL.frother_ppm)

    def test_no_ph_modifier_or_sulfidiser(self):
        """문헌은 자연 pH·무황화 운전이다 — 이전 설계의 계통이 남아 있으면 안 된다."""
        self.assertIsNone(db.PH_CONTROL)
        names = " ".join(r.name for r in db.REAGENTS).lower()
        for banned in ("na2s", "소다회", "na2co3", "규산소다", "silicate", "xanthate", "pax"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
