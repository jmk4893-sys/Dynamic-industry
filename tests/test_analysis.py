"""해석기와 해석 결과 — 구조 · 열.

해석기는 스스로 옳다고 말할 수 없다. 이 시험이 지키는 것은 세 겹이다:

  ① **해석기가 물리를 푼다** — 닫힌해 열 건과 오차 안에서 맞는다.
     이 겹이 없으면 아래 두 겹은 정교한 난수다.
  ② **결과가 근거에서 나온다** — 한계는 문헌·규격·설계값에서 오고,
     값은 모델에서 온다. 손으로 적은 숫자가 없다.
  ③ **문서가 모델과 같다** — 보고서는 생성물이므로 모델을 고치고 다시
     찍지 않으면 시험이 먼저 실패한다.

실제로 검증이 두 건의 버그를 잡았다 — 모드해석의 15 배 오차(질량 없는
자유도를 지워 구속해 버린 것)와 정상상태의 64 % 오차(시상수를 전도만
보고 어림해 정상해의 36 % 지점에서 멈춘 것). 그 두 건이 이 시험이
존재하는 이유다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import analysis_structural as ST
import analysis_thermal as TH
import fea
import gen_analysis_doc as GEN
import therm
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ── ① 해석기 ────────────────────────────────────────────────────────
class TestTheSolversAgreeWithClosedForm(unittest.TestCase):
    """검증 없는 해석기는 계산기가 아니라 난수 발생기다."""

    def test_the_frame_solver_matches_five_closed_form_cases(self):
        rows = fea.validate()
        self.assertEqual(len(rows), 5, "검증 사례가 줄었다")
        for name, got, want, err in rows:
            self.assertLess(err, 0.03, f"{name}: {got:.4f} vs 닫힌해 {want:.4f}")

    def test_the_thermal_solver_matches_five_closed_form_cases(self):
        rows = therm.validate()
        self.assertEqual(len(rows), 5, "검증 사례가 줄었다")
        for name, got, want, err in rows:
            self.assertLess(err, 0.02, f"{name}: {got:.4f} vs 닫힌해 {want:.4f}")

    def test_modal_analysis_does_not_constrain_massless_freedoms(self):
        """질량 없는 회전 자유도를 지우면 구조가 뻣뻣해진다 — 15 배 틀렸던 자리.

        캔틸레버 1차 진동수의 닫힌해는 (1.875²/2π)·√(EI/ρAL⁴) 다. Guyan
        축약을 되돌리면 이 값이 한 자릿수 위로 뛴다.
        """
        s = fea.rectsec(100, 100)
        L = 3000.0
        f = fea.Frame()
        ns = [f.node(L * i / 12, 0, 0) for i in range(13)]
        for i in range(12):
            f.beam(ns[i], ns[i + 1], s)
        f.support(ns[0])
        got = f.modes(n=1)[0]
        want = (1.875 ** 2 / (2 * math.pi)) * math.sqrt(
            s.E * s.Iz / (s.rho * s.A * L ** 4))
        self.assertLess(abs(got - want) / want, 0.02,
                        f"1차 진동수 {got:.3f} Hz · 닫힌해 {want:.3f} Hz")

    def test_steady_state_is_reached_not_estimated(self):
        """규정유속 + 대류의 정상해는 Ts = T∞ + q(1/h + t/k). 시상수를
        전도만 보고 어림하면 여기서 64 % 틀린다."""
        st = therm.Stack(therm.Layer("판", 0.02, 15.0, 7800, 500, 8))
        Tf = therm.steady(st, therm.BC(q=5000.0),
                          therm.BC(h=30.0, t_inf=25.0), t0=25.0)
        want = 25.0 + 5000.0 * (1 / 30.0 + 0.02 / 15.0)
        self.assertAlmostEqual(float(Tf[0]), want, delta=want * 0.005)


class TestTheThermalMeshIsBuiltRight(unittest.TestCase):
    """절점을 층 경계에 두는 것이 이 해석의 전제다 — 계면 온도를 보간 없이 읽는다."""

    def test_layer_boundaries_are_nodes(self):
        st = TH.panel_stack()
        x = 0.0
        for ly in st.layers:
            self.assertIn(round(x, 9), [round(v, 9) for v in st.x],
                          f"{ly.name} 앞면이 절점이 아니다")
            x += ly.t
        self.assertAlmostEqual(st.thickness, x, places=9)

    def test_nodal_capacity_sums_to_the_areal_heat_capacity(self):
        """절점 열용량의 합은 적층 전체의 면적열용량이어야 한다 — 반쪽
        셀을 빼먹으면 여기서 어긋난다."""
        st = TH.panel_stack()
        want = sum(ly.rcp * ly.t for ly in st.layers) / 1000
        self.assertAlmostEqual(st.areal_cp, want, places=9)

    def test_the_stack_carries_the_console_areal_heat_capacity(self):
        """두께를 따로 적으면 두 모델이 다른 패널을 데운다."""
        self.assertAlmostEqual(TH.panel_stack().areal_cp, c("AREAL_CP"),
                               places=3)

    def test_the_derived_backsheet_thickness_matches_the_console(self):
        """면적질량 ÷ 밀도가 콘솔의 BACKSHEET_T 와 같아야 밀도 가정이 산다."""
        st = TH.panel_stack()
        back = [ly for ly in st.layers if ly.name == "백시트"][0]
        self.assertAlmostEqual(back.t, c("BACKSHEET_T"), places=6)


# ── ② 결과 ──────────────────────────────────────────────────────────
class TestEveryResultCarriesItsBasis(unittest.TestCase):
    """근거 없는 한계는 통과시키려고 고른 숫자와 구별되지 않는다."""

    def setUp(self):
        self.srs, _ = ST.run()
        self.trs, _ = TH.run()

    def test_ids_are_unique_and_sequential(self):
        for pre, rs in (("S", self.srs), ("T", self.trs)):
            ids = [r.id for r in rs]
            self.assertEqual(ids, [f"{pre}{i}" for i in range(1, len(ids) + 1)],
                             f"{pre} 계열 번호가 어긋났다: {ids}")

    def test_every_result_has_a_limit_a_basis_and_a_note(self):
        for r in list(self.srs) + list(self.trs):
            self.assertGreater(r.limit, 0, f"{r.id} 한계가 없다")
            self.assertGreaterEqual(len(r.basis), 8, f"{r.id} 한계의 근거가 없다")
            self.assertGreaterEqual(len(r.note), 20, f"{r.id} 읽는 법이 없다")
            self.assertTrue(r.unit, f"{r.id} 단위가 없다")

    def test_only_the_two_intended_cases_exceed(self):
        """넘는 것이 늘어나면 설계가 바뀐 것이다 — 조용히 지나가면 안 된다.

        S11 권취축 클램프 중앙집중 · T13 카세트 냉각 두 건만 의도한
        경계 사례다. 둘 다 실패가 아니라 **요구가 되는 초과**다.
        """
        over = sorted(r.id for r in list(self.srs) + list(self.trs) if not r.ok)
        self.assertEqual(over, ["S11", "T13"], f"초과 항목이 바뀌었다: {over}")

    def test_the_analysis_creates_requirements_with_owners(self):
        rq = TH.requirements()
        self.assertGreaterEqual(len(rq), 6)
        for q in rq:
            self.assertRegex(q.id, r"^R\d+$")
            self.assertTrue(q.value.strip(), f"{q.id} 값이 없다")
            self.assertTrue(q.owner.strip(), f"{q.id} 받는 곳이 없다 — "
                            "받을 사람이 없는 요구는 요구가 아니다")
            self.assertGreaterEqual(len(q.why), 40, f"{q.id} 근거가 짧다")


class TestTheStructuralResultsFollowTheDesign(unittest.TestCase):
    """숫자가 아니라 **관계**를 지킨다 — 설계를 바꾸면 함께 움직여야 한다."""

    def test_the_table_carries_only_the_panel_weight_not_the_vacuum(self):
        """진공은 내력 쌍이다. 외력으로 세면 두 자릿수 크게 나온다."""
        _, ex = ST.run()
        w = ex["table"]["w_panel"]
        want = c("MASS_AREAL") * c("PANEL_L") * c("PANEL_W") * 9.80665 / 1000
        self.assertAlmostEqual(w, want, places=4)
        self.assertLess(w, 0.5, "패널 자중이 0.5 kN 을 넘을 수 없다")

    def test_more_columns_reduce_the_table_deflection(self):
        """기둥을 6본으로 올린 근거 — 4본이면 칼날 깊이 예산을 넘었다."""
        rs, _ = ST.run()
        s8 = [r for r in rs if r.id == "S8"][0]
        self.assertLess(s8.value, s8.limit,
                        "상판 자중 처짐이 칼날 깊이 예산을 넘는다")

    def test_the_winding_shaft_answer_depends_on_clamp_position(self):
        """양단 배치는 통과하고 중앙 집중은 넘는다 — 그래서 도면에 못 박는다."""
        _, ex = ST.run()
        self.assertLess(ex["shaft"]["d_wide"], ex["shaft"]["d_bare"],
                        "클램프를 벌리면 처짐이 줄어야 한다")


class TestTheThermalResultsFollowThePhysics(unittest.TestCase):
    def test_the_lumped_model_is_confirmed_not_replaced(self):
        """계면 도달 지연이 설계 체류의 5 % 안이면 덩어리 모델을 써도 된다."""
        rs, ex = TH.run()
        self.assertLess(ex["panel"]["lag"], 0.05 * TH.DWELL)
        self.assertGreater(ex["panel"]["fo"], 5.0, "적층이 열적으로 얇지 않다")

    def test_the_dwell_floor_is_set_by_the_backsheet_not_the_interface(self):
        """유속을 올리면 계면보다 백시트가 먼저 한계에 닿는다."""
        _, ex = TH.run()
        d = ex["dwell_floor"]
        self.assertGreater(d["q_cap"], TH.FLUX,
                           "설계 유속이 이미 상한을 넘었다")
        self.assertLess(d["t_des"], TH.DWELL,
                        "하한이 설계 체류보다 길면 설계가 성립하지 않는다")
        self.assertGreater(d["t_des"], d["t_cap"],
                           "여유를 둔 하한이 융점 하한보다 짧을 수 없다")

    def test_the_console_dwell_floor_is_conservative(self):
        """콘솔의 fdmDwell 을 바꾸지 않은 근거 — 물리 하한보다 길다."""
        _, ex = TH.run()
        console = float(re.search(
            r"fdmDwell:([\d.]+)",
            (ROOT / "docs" / "drawings" / "pv-delamination-3d.html")
            .read_text(encoding="utf-8")).group(1))
        self.assertGreaterEqual(console, ex["dwell_floor"]["t_des"],
                                "콘솔 하한이 물리 하한보다 짧다 — 백시트가 녹는다")

    def test_the_rfq_conservative_model_is_reproduced(self):
        """사양서 5.5항에 인쇄된 4.23 MPa 가 코드에서 그대로 나와야 한다.

        두 모델이 다른 것이지 어느 쪽이 계산을 틀린 것이 아니라는 것을
        보이려면, 사양서의 모델도 코드에 있어야 한다.
        """
        rfq = (ROOT / "docs" / "dg-hk60-rfq.html").read_text(encoding="utf-8")
        printed = float(re.search(
            r'<td class="num">3\.10 kW/m²</td><td class="num">9\.9 K</td>\s*'
            r'<td class="num">([\d.]+) MPa</td>', rfq).group(1))
        q, dt, sig = TH.rfq_bound(5)
        self.assertAlmostEqual(sig, printed, delta=0.05,
                               msg=f"보수 모델 재현 {sig:.2f} · 인쇄 {printed}")
        self.assertAlmostEqual(q, 3.10, delta=0.05)
        self.assertAlmostEqual(dt, 9.9, delta=0.15)

    def test_the_transient_result_sits_below_the_conservative_bound(self):
        """상한을 상한이라고 부르려면 실제로 위에 있어야 한다."""
        rs, ex = TH.run()
        transient = [r for r in rs if r.id == "T6"][0].value
        bound = [r for r in rs if r.id == "T7"][0].value
        self.assertLess(transient, bound)

    def test_a_metal_thermal_break_would_breach_the_touch_limit(self):
        """카탈로그가 GFRP 를 고른 근거 — 금속이면 외피가 60 ℃ 를 넘는다."""
        _, ex = TH.run()
        w = ex["chamber_wall"]
        self.assertLess(w["t_gfrp"], 60.0, "지금 설계로도 외피가 뜨겁다")
        self.assertGreater(w["t_steel"], 60.0,
                           "금속 스페이서가 안전하면 GFRP 를 쓸 이유가 없다")

    def test_the_wall_is_a_small_part_of_the_loss_budget(self):
        """65 % 효율의 나머지가 벽이 아니라는 것이 파일럿 PT-05 의 근거다."""
        _, ex = TH.run()
        w = ex["chamber_wall"]
        self.assertLess(w["q_gfrp"] * w["area"] / 1000, 0.5 * 35.0)

    def test_cooling_matches_the_console_lumped_solution(self):
        """콘솔의 LMTD 식과 과도해가 5 % 안에서 같아야 한다 — 다르면
        덩어리 가정이 깨진 것이고, 그때는 랙 단수가 움직인다."""
        _, ex = TH.run()
        g = ex["glass_cool"]
        self.assertLess(abs(g["t_cool"] - g["lump"]) / g["lump"], 0.05)
        self.assertLess(g["bi"], 0.10, "Bi 가 커지면 LMTD 식을 못 쓴다")


# ── ③ 문서 ──────────────────────────────────────────────────────────
class TestTheReportIsGeneratedFromTheModel(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "docs" / "dg-hk60-analysis.html").read_text(
            encoding="utf-8")

    def test_the_published_report_matches_the_generator(self):
        """손으로 고쳤으면 여기서 걸린다."""
        self.assertEqual(self.html, GEN.build(),
                         "보고서가 모델과 다르다 — gen_analysis_doc.py --write")

    def test_every_result_row_is_printed(self):
        srs, _ = ST.run()
        trs, _ = TH.run()
        for r in list(srs) + list(trs):
            self.assertIn(f'<td class="k">{r.id}</td>', self.html,
                          f"{r.id} 이 보고서에 없다")

    def test_no_markdown_leaks_into_the_printed_page(self):
        """산문 필드의 ** 를 그대로 인쇄한 적이 있다 — 두 번은 안 된다."""
        body = re.sub(r"<style>.*?</style>", "", self.html, flags=re.S)
        self.assertNotIn("**", body)

    def test_the_report_states_what_it_cannot_see(self):
        """한계를 안 적으면 '해석했다' 가 해석하지 않은 것까지 덮는다."""
        for must in ("용접부 국부응력", "판의 국부좌굴", "잔류응력",
                     "대류계수", "박리력 그 자체"):
            self.assertIn(must, self.html, f"경계에 {must} 가 없다")

    def test_the_report_records_the_two_bugs_validation_caught(self):
        """검증이 잡은 것을 지우면 검증표가 장식이 된다."""
        self.assertIn("15 배", self.html)
        self.assertIn("64 %", self.html)
