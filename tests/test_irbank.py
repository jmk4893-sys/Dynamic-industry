"""IR 뱅크 배치 — 복사 유속과 면내 온도편차.

이 검토가 답한 질문은 "램프를 어디에 얼마나 길게 두는가" 다. 그 답이
틀리는 방식은 셋이다:

  ① **모델이 물리가 아니다** — 유한 선원의 조사도는 닫힌해가 있다.
     수치적분과 맞지 않으면 아래 결론이 전부 장식이다.
  ② **결론이 근거에서 안 나온다** — 현행 배치가 실제로 넘고 개선 배치가
     실제로 통과해야 한다. 숫자를 바꿔 통과시킨 것이 아니어야 한다.
  ③ **결정이 도면에 안 내려간다** — 확정한 램프 길이와 위치가 카탈로그와
     콘솔에 그대로 있어야 한다. 검토서에만 있으면 아무 일도 안 한 것이다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import analysis_irbank as AIR
import irbank as IR
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestTheRadiantModelIsPhysics(unittest.TestCase):
    def test_the_closed_form_matches_numerical_integration(self):
        """닫힌해를 쓴 이유는 속도지 근사가 아니다 — 적분과 같아야 한다."""
        lp = IR.Lamp(0.0, 0.31, 2.5, 1.30)
        for px, py in ((0.0, 0.0), (0.4, 0.2), (1.1, 0.55), (0.05, 0.64)):
            n, acc = 4000, 0.0
            dl = lp.length / n
            wprime = lp.kw * 1000 / lp.length
            for k in range(n):
                ly = -lp.length / 2 + (k + 0.5) * dl
                R2 = (px - lp.x) ** 2 + (py - ly) ** 2 + lp.z ** 2
                acc += wprime * dl * lp.z / (4 * math.pi * R2 ** 1.5)
            got = lp.irradiance(px, py)
            self.assertAlmostEqual(got, acc, delta=acc * 1e-4,
                                   msg=f"({px},{py}) 닫힌해 {got:.3f} vs 적분 {acc:.3f}")

    def test_both_source_limits_come_out_right(self):
        """짧은 램프는 점광원(1/h²), 긴 램프는 선광원(1/h) 이다.

        처음에 긴 램프에 1/h² 을 기대했다가 2.03 이 나왔다 — 모델이 틀린
        것이 아니라 시험이 틀렸다. 유한 선원은 두 극한 **사이**에 있고,
        그 전이를 제대로 담는지가 이 해석기의 핵심이다. 실제 램프
        (2.2 m · 높이 0.31) 는 선광원 쪽에 가깝다.
        """
        def ratio(L):
            a = IR.Lamp(0.0, 0.31, 2.5, L).irradiance(0, 0)
            b = IR.Lamp(0.0, 0.62, 2.5, L).irradiance(0, 0)
            return a / b
        self.assertAlmostEqual(ratio(0.005), 4.0, delta=0.05)   # 점광원 극한
        self.assertAlmostEqual(ratio(40.0), 2.0, delta=0.05)    # 선광원 극한
        mid = ratio(AIR.NEW_LEN)
        self.assertTrue(2.0 < mid < 4.0, f"실제 램프가 두 극한 밖이다: {mid}")

    def test_a_longer_lamp_lifts_the_width_edge(self):
        """폭 결손이 램프 길이의 함수라는 것이 이 검토의 출발점이다."""
        prev = 0.0
        for L in (1.30, 1.70, 2.20):
            lam = IR.even(7, 2.48, length=L)
            f = IR.field(IR.images(lam, 0.0), 21, 11)
            nx, ny = len(f.xs), len(f.ys)
            ratio = f.E[nx // 2][0] / f.E[nx // 2][ny // 2]
            self.assertGreater(ratio, prev, f"L={L} 에서 가장자리가 안 올랐다")
            prev = ratio

    def test_wall_reflection_only_helps(self):
        for n in (6, 7):
            a = IR.field(IR.images(IR.even(n, 2.48), 0.0), 21, 11).spread
            b = IR.field(IR.images(IR.even(n, 2.48), 0.8), 21, 11).spread
            self.assertLess(b, a, "벽 반사가 균일도를 나쁘게 만들 수 없다")

    def test_in_plane_conduction_is_glass_only(self):
        """면내 전도에 셀을 넣지 않은 것은 **의도한 선택**이다.

        실리콘의 k·t 는 유리의 10 배지만, 156 mm 웨이퍼가 2 mm 씩 떨어져
        있고 탭 리본만 잇는다 — 셀 **안에서는** 평활하지만 셀을 건너서는
        전도하지 않는다. 연속체로 놓으면 있지도 않은 평활화를 계산에
        넣게 되고, 그러면 배치가 실제보다 좋아 보인다.

        고의 파손시험이 이 자리를 못 잡아서 넣었다 — 결론은 안 뒤집혔지만
        모델링 선택이 무방비였다.
        """
        glass = 1.00 * (c("MASS_GLASS") / 2500.0)
        self.assertAlmostEqual(IR.KT_PLATE, glass, places=9,
                               msg="면내 전도가 유리 단독이 아니다")

    def test_conduction_cannot_smooth_the_lamp_pitch(self):
        """면내 확산길이가 램프 피치보다 훨씬 작다 — 검토 전체의 전제다.

        전제가 모델링 선택에 기대지 않는다는 것까지 본다: 셀을 연속체로
        놓아 전도를 11 배로 **후하게** 줘도 여전히 평활화가 안 된다.
        """
        pitch = 2.48 / 6
        for name, kt in (("유리 단독", IR.KT_PLATE),
                         ("셀 포함 (낙관)", IR.KT_PLATE + 148.0 * 0.223e-3)):
            diff_len = math.sqrt(kt / IR.CP_AREAL * 222.6)
            self.assertLess(diff_len * 10, pitch,
                            f"{name}: 확산길이 {diff_len*1000:.0f} mm 가 피치 "
                            f"{pitch*1000:.0f} mm 에 비해 작지 않다 — 그러면 "
                            "유속 분포가 곧 온도 분포라는 논리가 무너진다")

    def test_scaling_preserves_the_energy_budget(self):
        f = IR.field(IR.images(IR.even(7, 2.48), 0.5), 31, 15).scaled(13000.0)
        area = IR.PANEL_L * IR.PANEL_W
        self.assertAlmostEqual(f.mean * area, 13000.0, delta=1.0)

    def test_the_cold_spot_soak_actually_reaches_the_target(self):
        f = IR.field(IR.images(IR.from_positions(list(AIR.NEW_X),
                                                 length=AIR.NEW_LEN) * 2, 0.8),
                     41, 21).scaled(AIR.Q_PANEL)
        d, T = IR.soak_to_cold(f, 140.0)
        s = IR.stats(T)
        self.assertAlmostEqual(s["tmin"], 140.0, delta=0.5)
        self.assertGreater(d, 100.0)


class TestTheConclusionFollowsFromTheModel(unittest.TestCase):
    def setUp(self):
        self.rs, self.ex = AIR.run()

    def test_the_present_layout_fails_and_the_new_one_passes(self):
        bad = sorted(r.id for r in self.rs if not r.ok)
        self.assertEqual(bad, ["IR1", "IR2", "IR3"],
                         f"판정이 바뀌었다: {bad}")

    def test_the_backsheet_window_is_tighter_than_the_glass_window(self):
        """유리 21 K 가 아니라 백시트 18 K 가 창을 정한다 — 이 순서가 뒤집히면
        검토의 결론이 달라진다."""
        window = AIR.T_BACK_MAX - AIR.T_TARGET - 7.0
        self.assertLess(window, AIR.DT_GLASS)

    def test_the_new_layout_survives_a_soiled_inner_skin(self):
        """반사율이 절반으로 떨어져도 백시트가 견뎌야 사양이 된다."""
        self.assertLess(self.ex["new_soiled"]["back"], AIR.T_BACK_MAX)
        self.assertLess(AIR.RHO_SPEC, AIR.RHO_POLISHED / 1.5)

    def test_the_new_layout_keeps_the_contract_throughput(self):
        self.assertLess(self.ex["new"]["pitch"], AIR.TAKT,
                        "피치가 택트를 넘으면 처리량을 소킹이 정하게 된다")
        self.assertGreaterEqual(self.ex["new"]["rate"], 60.0)

    def test_the_present_layout_breaks_the_contract_throughput(self):
        self.assertLess(self.ex["now"]["rate"], 60.0)

    def test_stagger_is_worse_not_better(self):
        """엇갈리면 좋아진다는 것이 처음 가설이었고 모델이 아니라고 했다.
        그 결론을 지운 채로 배치만 남으면 다음 사람이 다시 엇갈린다."""
        xs = list(AIR.NEW_X)
        same = IR.from_positions(xs, length=AIR.NEW_LEN) * 2
        off = (xs[1] - xs[0]) / 2
        stag = (IR.from_positions(xs, length=AIR.NEW_LEN)
                + [l._replace(x=l.x + off)
                   for l in IR.from_positions(xs, length=AIR.NEW_LEN)])
        a = IR.field(IR.images(same, 0.8), 41, 21).spread
        b = IR.field(IR.images(stag, 0.8), 41, 21).spread
        self.assertLess(a, b, "엇갈림이 좋아졌다면 확정 배치를 다시 봐야 한다")

    def test_end_lamps_sit_outside_the_panel_edge(self):
        """끝 램프가 패널 안쪽이면 그 바깥을 아무도 데우지 않는다."""
        self.assertGreater(max(AIR.NEW_X), c("PANEL_L") / 2)

    def test_the_lamp_fits_the_cavity(self):
        self.assertLess(AIR.NEW_LEN, IR.CAVITY_W)
        self.assertGreater((IR.CAVITY_W - AIR.NEW_LEN) / 2, 0.030,
                           "측벽 여유가 30 mm 미만이면 관통 부시가 안 들어간다")

    def test_every_result_and_requirement_carries_its_basis(self):
        for r in self.rs:
            self.assertGreater(r.limit, 0, f"{r.id} 한계가 없다")
            self.assertGreaterEqual(len(r.basis), 8, f"{r.id} 근거가 없다")
            self.assertGreaterEqual(len(r.note), 20, f"{r.id} 읽는 법이 없다")
        rq = AIR.requirements()
        self.assertGreaterEqual(len(rq), 5)
        for q in rq:
            self.assertRegex(q.id, r"^RIR\d+$")
            self.assertTrue(q.owner.strip(), f"{q.id} 받는 곳이 없다")
            self.assertGreaterEqual(len(q.why), 40, f"{q.id} 근거가 짧다")


class TestTheDecisionReachedTheDrawings(unittest.TestCase):
    """검토서에만 있는 결정은 아무 일도 하지 않는다."""

    def setUp(self):
        self.console = (ROOT / "docs" / "drawings" /
                        "pv-delamination-3d.html").read_text(encoding="utf-8")

    def test_the_catalogue_carries_the_new_lamp_length(self):
        import parts as PT
        lamp = [p for p in PT.P if p.pid == "P-002-18"][0]
        overall = lamp.shape.d["L"] if "L" in lamp.shape.d else None
        self.assertIsNotNone(overall, "구매품 램프의 전장을 못 읽었다")
        self.assertGreaterEqual(overall, AIR.NEW_LEN * 1000,
                                "카탈로그 램프가 확정 발열장보다 짧다")

    def test_the_console_uses_the_optimised_positions(self):
        m = re.search(r"const LAMP_POS=\{[^}]*7:\[([^\]]+)\]", self.console)
        self.assertIsNotNone(m, "콘솔에 램프 위치표가 없다")
        got = [float(v) for v in m.group(1).split(",")]
        self.assertEqual([round(v, 3) for v in got],
                         [round(v, 3) for v in AIR.NEW_X],
                         "콘솔의 램프 위치가 검토 결과와 다르다")

    def test_the_console_uses_the_new_heated_length(self):
        m = re.search(r"const LAMP_HEAT=([\d.]+);", self.console)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(float(m.group(1)), AIR.NEW_LEN, places=3)

    def test_the_console_no_longer_spaces_lamps_evenly(self):
        """균등 배치 식이 남아 있으면 어느 도면 하나가 옛 배치를 그린다.
        REV.20 은 폐기 배치이므로 제외한다."""
        self.assertNotIn("(g.w-.84)/(per-1)", self.console)
        self.assertNotIn("(chamberL-2*wall-600)/(n-1)", self.console)

    def test_the_bank_count_is_decks_plus_one(self):
        """캐리어 수량이 뱅크 수를 따라야 한다 — 종전 10 은 한 뱅크를 빠뜨렸다."""
        import parts as PT
        car = [p for p in PT.P if p.pid == "P-002-17"][0]
        self.assertEqual(car.qty, (int(c("DECKS")) + 1) * 2)
