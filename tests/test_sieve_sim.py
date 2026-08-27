"""sieve_sim 체분리 모델 검증.

numpy 가 필요하므로 simulation-smoke 잡에서 실행된다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
try:
    import numpy as np
    import sieve_sim as sv
    import classifier_sim as cs
    HAVE_SIM = True
except Exception:                                   # pragma: no cover
    HAVE_SIM = False


@unittest.skipUnless(HAVE_SIM, "numpy 필요")
class SamplingTest(unittest.TestCase):
    def test_truncation_respects_material_range(self):
        """실리콘이 120 µm 위로 생기면 데크 부하가 왜곡된다."""
        rng = np.random.default_rng(0)
        for name, m in cs.MATERIALS.items():
            _, I, _ = sv.sample_particles(rng, name, 5000, cs.SIZE_DIST)
            self.assertGreaterEqual(I.min(), m["d_lo"] * 1e6 - 1e-6, name)
            self.assertLessEqual(I.max(), m["d_hi"] * 1e6 + 1e-6, name)

    def test_mass_basis_matches_the_stated_premise(self):
        """전제는 '실리콘·은은 75 µm 이하에 95 % 이상' 이다.

        체분석은 질량 기준이므로 basis='mass' 로 뽑아야 이 전제와 맞는다.
        개수 기준으로 뽑으면 질량이 훨씬 굵어져 전제와 어긋난다.
        """
        rng = np.random.default_rng(1)
        got = {}
        for basis in ("mass", "number"):
            L, I, S = sv.sample_particles(rng, "실리콘+은", 40000, cs.SIZE_DIST, basis)
            w = L * I * S
            got[basis] = float(w[I < 75].sum() / w.sum())
        self.assertGreater(got["mass"], 0.85, "질량 기준은 전제에 가까워야 한다")
        self.assertLess(got["number"], got["mass"] - 0.2,
                        "개수 기준은 눈에 띄게 굵어야 한다 — 두 해석이 다름을 고정")

    def test_axes_are_ordered(self):
        rng = np.random.default_rng(2)
        L, I, S = sv.sample_particles(rng, "백시트+EVA", 3000, cs.SIZE_DIST)
        self.assertTrue(np.all(L >= I - 1e-9))
        self.assertTrue(np.all(I >= S - 1e-9))


@unittest.skipUnless(HAVE_SIM, "numpy 필요")
class PassageTest(unittest.TestCase):
    def test_oversize_never_passes(self):
        """중간축이 개구 이상이면 아무리 얇아도 사각 개구를 통과하지 못한다."""
        p = sv.passage_probability(np.array([80.0, 120.0]), np.array([5.0, 5.0]),
                                   75.0, 50.0)
        self.assertTrue(np.all(p == 0.0))

    def test_flake_passes_slower_than_equant(self):
        """같은 중간축이라도 편평한 입자는 모로 서야 하므로 느리다."""
        I = np.array([40.0])
        flake = sv.passage_probability(I, I * 0.12, 75.0, 50.0)[0]
        equant = sv.passage_probability(I, I * 0.75, 75.0, 50.0)[0]
        self.assertLess(flake, equant / 3.0)

    def test_near_mesh_decays_steeply(self):
        """개구에 가까울수록 Gaudin 항이 급격히 떨어진다 — 실제 컷이 개구보다 작은 이유."""
        S_over_I = 0.6
        ps = [sv.passage_probability(np.array([x]), np.array([x * S_over_I]),
                                     75.0, 50.0)[0] for x in (30.0, 60.0, 70.0)]
        self.assertGreater(ps[0], 5 * ps[1])
        self.assertGreater(ps[1], 3 * ps[2])


@unittest.skipUnless(HAVE_SIM, "numpy 필요")
class BlindingTest(unittest.TestCase):
    def test_ultrasonic_dominates_blinding(self):
        """초음파 없이는 개방면적을 대부분 잃는다 — 모델을 이 산업 사실에 맞춰 보정했다."""
        with_us = sv.blinded_steady_state(0.25, ultrasonic=True)
        without = sv.blinded_steady_state(0.25, ultrasonic=False)
        self.assertLess(with_us, 0.05)
        self.assertGreater(without, 0.5)

    def test_blinding_grows_with_near_mesh_load(self):
        a = sv.blinded_steady_state(0.05, ultrasonic=False)
        b = sv.blinded_steady_state(0.40, ultrasonic=False)
        self.assertGreater(b, a)


@unittest.skipUnless(HAVE_SIM, "numpy 필요")
class CircuitTest(unittest.TestCase):
    DECKS = [250, 106, 75]

    def test_mass_balance_closes_per_material(self):
        c = sv.circuit(decks=self.DECKS, n_per_material=2500)
        for name, r in c["recovery"].items():
            self.assertAlmostEqual(r["P1"] + r["P2"] + r["P3"], 1.0, places=6, msg=name)

    def test_top_deck_250_recovers_copper_that_200_loses(self):
        """근접입자 구리가 200 µm 데크를 넘지 못해 백시트 제품으로 유실된다.

        Rev.4 는 '200 µm 오버에는 구리가 없다' 고 보고 P3 로 직행시켰는데,
        실제 컷이 개구보다 작아 150~200 µm 구리가 여기서 버려진다.
        """
        lost200 = sv.circuit(decks=[200, 106, 75], n_per_material=4000)["recovery"]["구리"]["P3"]
        lost250 = sv.circuit(decks=[250, 106, 75], n_per_material=4000)["recovery"]["구리"]["P3"]
        self.assertGreater(lost200, 0.10, "200 µm 데크의 구리 유실이 무시할 수준이 아니다")
        self.assertLess(lost250, lost200 / 3.0, "250 µm 로 키우면 대부분 회수된다")

    def test_ultrasonic_is_decisive_for_both_products(self):
        on = sv.circuit(decks=self.DECKS, ultrasonic=True, n_per_material=4000)["recovery"]
        off = sv.circuit(decks=self.DECKS, ultrasonic=False, n_per_material=4000)["recovery"]
        self.assertGreater(on["실리콘+은"]["P1"], off["실리콘+은"]["P1"] + 0.10)
        self.assertGreater(on["구리"]["P2"], off["구리"]["P2"] + 0.10)

    def test_scalping_sieve_adds_silver_but_less_than_assumed(self):
        """SS-01 의 기여는 설계서가 가정한 9 포인트보다 작다.

        되찾을 대상이 근접입자 구간에 몰려 있어 두 번째 체도 잘 통과시키지 못한다.
        """
        with_ss = sv.circuit(decks=self.DECKS, ss01=True, n_per_material=4000)
        without = sv.circuit(decks=self.DECKS, ss01=False, n_per_material=4000)
        gain = with_ss["recovery"]["실리콘+은"]["P1"] - without["recovery"]["실리콘+은"]["P1"]
        self.assertGreater(gain, 0.02, "그래도 유의미한 기여는 있어야 한다")
        self.assertLess(gain, 0.09, "설계서의 9 포인트 가정보다는 작아야 한다")

    def test_silver_recovery_is_below_the_assumed_ninety_percent(self):
        """설계서 §6.7 의 '데크 효율 90 %' 가정이 낙관이었음을 고정한다."""
        c = sv.circuit(decks=self.DECKS, n_per_material=6000)
        self.assertLess(c["recovery"]["실리콘+은"]["P1"], 0.90)
        self.assertGreater(c["recovery"]["실리콘+은"]["P1"], 0.70)

    def test_conclusion_is_robust_to_shape_assumption(self):
        """배향 지수를 0.5~1.5 로 바꿔도 결론(80 % 내외)이 뒤집히지 않는다."""
        vals = [sv.circuit(decks=self.DECKS, orient_exp=e, n_per_material=3000)
                ["recovery"]["실리콘+은"]["P1"] for e in (0.5, 1.0, 1.5)]
        self.assertLess(max(vals) - min(vals), 0.08)


if __name__ == "__main__":
    unittest.main()
