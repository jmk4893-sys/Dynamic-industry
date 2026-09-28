"""열수지 — 제어체적이 닫히는가, 그리고 왜 닫혀야 하는가.

이 검토의 결론은 숫자가 아니라 **프레임**이다: 30 kW 는 새지 않았고,
질문이 두 군데에서 틀려 있었다. 그 결론이 무너지는 방식은 셋이다.

  ① **제어체적이 안 닫힌다** — IN 은 OUT 의 합이어야 한다. 항 하나를
     빼거나 두 번 세면 그 순간 이 검토는 아무것도 아니다.
  ② **항의 크기가 물리를 넘는다** — 포크 항에서 실제로 그랬다. 챔버가
     줄 수 없는 140 kW 를 요구하는 값이 13 kW 로 앉아 수지를 "너무 잘"
     닫았다. **너무 잘 닫히는 것이 신호**라는 것을 시험으로 남긴다.
  ③ **두 효율이 섞인다** — 결합효율(승온 속도)과 정상상태 효율(에너지
     보존)은 다른 양이다. 섞으면 있지도 않은 구멍을 찾게 된다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import heatbalance as HB
import lampmount as LM
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestTheControlVolumeCloses(unittest.TestCase):
    def setUp(self):
        self.b = HB.balance()

    def test_in_equals_out(self):
        """제어체적의 전부다. 이것이 안 맞으면 나머지는 읽을 필요가 없다."""
        out = (self.b["panel"] + self.b["wall"] + self.b["airlock"]
               + self.b["infil"] + self.b["terminal"] + self.b["fork"])
        self.assertAlmostEqual(self.b["p_ir"], out, places=9)
        self.assertAlmostEqual(self.b["loss"], out - self.b["panel"], places=9)

    def test_efficiency_is_the_panel_share(self):
        self.assertAlmostEqual(self.b["eta"],
                               self.b["panel"] / self.b["p_ir"], places=12)

    def test_no_term_exceeds_what_the_chamber_can_deliver(self):
        """포크 항에서 이 자리를 실제로 틀렸다 — 200 배.

        어떤 손실 항도 설치정격을 넘을 수 없고, 사이클 안에 넣어야 하는
        열이 정격을 넘으면 그 모델은 틀린 것이다.
        """
        for k in ("wall", "airlock", "infil", "terminal", "fork"):
            self.assertLess(self.b[k], HB.RATED_KW,
                            f"{k} 항이 설치정격을 넘는다 — 모델이 틀렸다")
        # 포크: 노출 시간 안에 넣어야 하는 순간 전력
        peak = HB.fork() * HB.TAKT / HB.FORK_EXPOSE
        self.assertLess(peak, HB.RATED_KW,
                        f"포크가 노출 {HB.FORK_EXPOSE:.0f} 초에 {peak:.0f} kW 를 "
                        "요구한다 — 챔버가 줄 수 없는 열이다")

    def test_closing_too_well_is_a_smell_not_a_result(self):
        """수지가 가정 효율과 소수점까지 맞으면 의심해야 한다.

        처음에 η 64.3 % 가 나와 가정 65 % 와 거의 같았고, 그것이 맞아서가
        아니라 **틀린 항이 빈 자리를 정확히 메워서**였다. 지금은 12 kW 의
        여유가 벌어져 있고, 그 여유가 사라지면 항 하나를 다시 봐야 한다.
        """
        gap = self.b["assumed_loss"] - self.b["loss"]
        self.assertGreater(gap, 5.0,
                           "수지가 가정과 5 kW 안으로 붙었다 — 항 하나가 "
                           "빈 자리를 메우고 있지 않은지 다시 본다")

    def test_the_counted_losses_are_smaller_than_the_assumption(self):
        """가정이 수지보다 손실을 크게 잡아야 체류시간 계산이 보수측이다."""
        self.assertLess(self.b["loss"], self.b["assumed_loss"])
        self.assertGreater(self.b["eta"], HB.ETA_ASSUMED)


class TestTheTermsAreRight(unittest.TestCase):
    def test_panel_enthalpy_matches_the_console_formula(self):
        """열모델의 q 를 그대로 쓴다 — 콘솔의 질량 기반 AREAL_CP(8.663)는 열모델의
        arealCp(8.7359)와 1 % 안에서만 같은 다른 값이라, 여기서 쓰면 HB1 의
        '유효 78 kW' 가 0.8 % 어긋난다."""
        import cycle as CY
        q = CY.model()["q"]
        self.assertAlmostEqual(HB.Q_PANEL_KJ, q, places=9)
        self.assertAlmostEqual(HB.panel(3600.0), q, places=9)
        mass_based = (c("AREAL_CP") * c("PANEL_L") * c("PANEL_W") * (c("T_TARGET") - c("T_AMB")))
        self.assertLess(abs(mass_based / q - 1), 0.01, "질량 가정과 열 가정이 1 % 밖으로 갈라졌다")

    def test_the_thermal_limit_rate_reproduces_the_console_useful_power(self):
        """65 kW 가 어느 운전점의 값인지가 이 검토의 출발점이다."""
        self.assertAlmostEqual(HB.panel(HB.RATE_THERMAL),
                               HB.RATED_KW * HB.ETA_ASSUMED, delta=0.6)
        self.assertLess(HB.panel(HB.RATE_CONTRACT),
                        HB.panel(HB.RATE_THERMAL),
                        "계약 처리량이 열공정 한계보다 낮아야 이 논지가 선다")

    def test_the_airlock_term_comes_from_the_airlock_solver(self):
        """열수지가 이 항을 스스로 세면 반드시 에어록 검토와 갈라진다."""
        import airlock as AIR
        self.assertAlmostEqual(HB.airlock()[1], AIR.kw(), places=12)
        self.assertAlmostEqual(HB.balance()["airlock"], AIR.kw(), places=12)

    def test_the_airlock_is_bounded_by_the_opening_not_by_a_volume(self):
        """납품 배치에는 격리실이 없다 — 막는 것은 부피가 아니라 개구다.

        옛 모델은 격리실 부피에 비례했다. 그 방이 없으므로 지금은 개구
        높이의 1.5 제곱에 비례해야 한다.
        """
        import airlock as AIR
        t = AIR.open_time(AIR.OPEN_H)        # 같은 시간에서 높이만 바꾼다
        r = (AIR.loss_kw(2 * AIR.OPEN_H, t_open=t)
             / AIR.loss_kw(AIR.OPEN_H, t_open=t))
        self.assertAlmostEqual(r, 2.0 ** 1.5, places=9)
        # 시간에는 선형이다 — 문 열림 시간이 두 배면 손실도 두 배
        self.assertAlmostEqual(
            AIR.loss_kw(AIR.OPEN_H, t_open=2 * t)
            / AIR.loss_kw(AIR.OPEN_H, t_open=t), 2.0, places=9)
        # 격리실을 더해도 안 줄어든다 — 교환이 그 방을 채우지 못한다
        self.assertAlmostEqual(
            AIR.loss_kw(AIR.OPEN_H, vest=AIR.vestibule(AIR.OPEN_H)),
            AIR.loss_kw(AIR.OPEN_H), places=12)

    def test_the_airlock_is_still_the_biggest_loss_term(self):
        _, ex = HB.run()
        self.assertGreater(ex["b"]["airlock"], ex["b"]["wall"],
                           "에어록이 벽보다 작으면 이 장을 쓸 이유가 없다")
        self.assertGreater(ex["full"], 100.0,
                           "전고 개구가 정격을 안 넘으면 AL1 의 논지가 죽는다")

    def test_infiltration_and_exhaust_are_the_same_term(self):
        """부압이 빼내는 만큼 새 구멍으로 들어온다 — 따로 세면 두 번 센다."""
        area, m3h, kw = HB.infiltration()
        want = HB.LM.CD * area * 1e-6 * math.sqrt(2 * LM.DP / LM.RHO_AIR) * 3600
        self.assertAlmostEqual(m3h, want, places=6)

    def test_terminal_conduction_uses_the_fin_root_flux(self):
        m, _, _ = LM.pinch()
        A, _ = LM._section()
        want = (LM.K_Q * 1e-3 * A) * m * (LM.T_TUBE - LM.T_BUSH) * LM.N_PEN / 1000
        self.assertAlmostEqual(HB.terminal(), want, places=9)

    def test_the_fork_term_is_set_by_exposure_time_not_mass(self):
        """질량은 이 항에 안 들어온다. 들어오는 것은 노출 시간과 대기 온도다."""
        import airlock as AIR
        self.assertAlmostEqual(HB.FORK_EXPOSE, 2 * AIR.REACH / AIR.V_FORK,
                               places=12)
        cold = HB.fork(t_rest=c("T_AMB"))
        warm = HB.fork(t_rest=60.0)
        self.assertGreater(cold, warm)
        self.assertAlmostEqual(cold / warm,
                               (c("T_TARGET") - c("T_AMB"))
                               / (c("T_TARGET") - 60.0), places=9)

    def test_the_fork_and_the_airlock_share_one_time(self):
        """포크가 들어가 있는 동안 문이 열려 있다 — 하나를 줄이면 둘이 준다."""
        import airlock as AIR
        self.assertLess(HB.FORK_EXPOSE, AIR.open_time())
        self.assertGreater(HB.FORK_EXPOSE, 0.5 * AIR.open_time(),
                           "포크 왕복이 문 열림 시간의 대부분이어야 RHB3 가 선다")

    def test_startup_energy_is_dominated_by_the_inner_steel(self):
        su = HB.startup()
        self.assertGreater(su["inner"], su["insul"] + su["gas"])
        self.assertGreater(su["minutes"], 5.0)
        self.assertLess(su["minutes"], 120.0)


class TestTheFramingIsRecorded(unittest.TestCase):
    """이 검토가 남기는 것은 숫자가 아니라 구분이다 — 지우면 다시 헤맨다."""

    def setUp(self):
        self.rs, self.ex = HB.run()

    def test_only_the_airlock_lever_exceeds(self):
        over = sorted(r.id for r in self.rs if not r.ok)
        self.assertEqual(over, ["HB5"], f"판정이 바뀌었다: {over}")

    def test_every_result_and_requirement_carries_its_basis(self):
        for r in self.rs:
            self.assertGreater(r.limit, 0, f"{r.id} 한계가 없다")
            self.assertGreaterEqual(len(r.basis), 8, f"{r.id} 근거가 없다")
            self.assertGreaterEqual(len(r.note), 20, f"{r.id} 읽는 법이 없다")
        rq = HB.requirements()
        self.assertGreaterEqual(len(rq), 5)
        for q in rq:
            self.assertRegex(q.id, r"^RHB\d+$")
            self.assertTrue(q.owner.strip(), f"{q.id} 받는 곳이 없다")
            self.assertGreaterEqual(len(q.why), 40, f"{q.id} 근거가 짧다")

    def test_the_framing_lives_in_the_model_not_only_in_prose(self):
        """산문은 지워질 수 있다. 프레임은 **결과 항의 주기**에 있어야 한다.

        고의 파손시험에서 보고서의 산문 한 문단을 지웠는데 시험이 통과했다 —
        같은 말이 HB2 주기에도 있었기 때문이다. 통과한 것이 다행이었지
        시험이 지킨 것이 아니었으므로, 지키는 자리를 모델로 옮긴다.
        """
        by = {r.id: r for r in self.rs}
        self.assertIn("두 운전점", by["HB1"].note,
                      "'100−65=35' 가 두 운전점의 뺄셈이라는 것이 HB1 주기에 없다")
        self.assertIn("돌고", by["HB2"].note,
                      "빗나간 복사가 돈다는 것이 HB2 주기에 없다")
        self.assertIn("너무 잘", by["HB8"].note,
                      "수지가 너무 잘 닫혔던 것이 신호였다는 기록이 HB8 주기에 없다")

    def test_the_report_carries_every_row(self):
        html = (ROOT / "docs" / "dg-hk60-analysis.html").read_text(encoding="utf-8")
        for r in self.rs:
            self.assertIn(f'<td class="k">{r.id}</td>', html,
                          f"{r.id} 이 보고서에 없다")
        body = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
        self.assertNotIn("**", body)

    def test_the_thermal_requirement_points_at_the_discharge(self):
        import analysis_thermal as TH
        r5 = [q for q in TH.requirements() if q.id == "R5"][0]
        self.assertIn("heatbalance", r5.value)
