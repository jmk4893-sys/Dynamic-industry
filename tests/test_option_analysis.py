"""옵션 DG-HK120C 해석 — 표준의 검토를 같은 코드로 다시 풀고, 옵션이 만든 결정을 지킨다.

옵션을 풀자 결정 셋이 나왔다 — SSR 상한(T5) · 승강축 등급(CY4) · 12 등 배치(IR4). 셋 다
"옵션에서만 필요한 것" 이라 표준의 시험이 지켜 주지 않는다. 여기서 묻는다.

그리고 사이클 검토(CY)가 표준에서 찾은 것 — 스크류를 돌리는 승강축은 택트를 못 맞춘다 —
은 표준의 결정이기도 하다. 그것이 다시 조용히 돌아오지 않게 둘 다 묻는다.
"""

import math
import pathlib
import re
import unittest

from tests import _path  # noqa: F401

import console_consts as C
import variant

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestTheLampTableIsOptimal(unittest.TestCase):
    """램프 위치는 콘솔 LAMP_POS 한 곳에 산다 — 그 값이 정말 최적점인가.

    최적화기(IR.optimize)를 통째로 돌리면 12 등에 50 초가 든다. 대신 표의 값이
    **국소 최적**인지를 본다: 대칭 쌍 하나를 ±5 mm 옮겨서 편차가 줄면 표가 틀렸다."""

    def test_each_bank_layout_is_a_local_optimum(self):
        import irbank as IR
        import analysis_irbank as A
        for n in (8, 12):
            xs = list(A.lamp_pos(n))
            base = IR.field(IR.images(IR.from_positions(xs, length=A.NEW_LEN), IR.RHO_WALL), 41, 21).spread
            for i in range(n // 2):
                for d in (-0.005, 0.005):
                    ys = list(xs)
                    ys[i] -= d
                    ys[n - 1 - i] += d
                    if max(abs(y) for y in ys) > (IR.DECK_L - 0.10) / 2 + 1e-9:
                        continue          # 공동 밖 — 최적화가 막아 둔 쪽
                    sp = IR.field(IR.images(IR.from_positions(sorted(ys), length=A.NEW_LEN),
                                            IR.RHO_WALL), 41, 21).spread
                    self.assertGreaterEqual(sp, base - 1e-4,
                                            f"{n} 등 배치의 {i} 번 쌍을 {d*1000:+.0f} mm 옮기니 편차가 준다")

    def test_the_option_bank_count_has_a_layout(self):
        import analysis_irbank as A
        tw = C.layouts()["twin"]
        n = tw["lamps"] // (tw["decks"] + 1)
        self.assertEqual(len(A.lamp_pos(n)), n, f"옵션 뱅크당 {n} 등의 배치가 콘솔에 없다")
        src = C.CONSOLE.read_text(encoding="utf-8")
        self.assertIn("const lampX=(i,n)=>(LAMP_POS[n]||LAMP_POS[8])[i];", src)


class TestTheSsrCap(unittest.TestCase):
    """단당 램프가 많은 옵션은 작은 패널에서 백시트를 녹인다 — SSR 상한이 그것을 막는가."""

    @classmethod
    def setUpClass(cls):
        import analysis_thermal as TH
        cls.B = TH
        cls.T = variant.load("twin", "analysis_thermal")["analysis_thermal"]

    def _a_min(self, th):
        R = th.CY.RANGE
        return R["panelLength"][0] * R["panelWidth"][0] / 1e6

    def test_the_standard_is_untouched(self):
        self.assertAlmostEqual(self.B.ssr_cap(self._a_min(self.B)), 1.0, places=9)

    def test_the_option_is_capped_at_the_small_panel_only(self):
        with variant.pinned("twin"):
            self.assertLess(self.T.ssr_cap(self._a_min(self.T)), 0.8)
            self.assertEqual(self.T.ssr_cap(self.T.PANEL_A), 1.0, "기본 패널에서 상한이 걸리면 처리량이 깎인다")
            t5 = {r.id: r for r in self.T.dwell_floor()[0]}["T5"]
        b5 = {r.id: r for r in self.B.dwell_floor()[0]}["T5"]
        self.assertTrue(t5.ok, "옵션 모서리의 백시트가 융점을 넘는다")
        self.assertAlmostEqual(t5.value, b5.value, places=3,
                               msg="상한이 걸린 옵션 모서리는 표준 모서리와 같은 유속이어야 한다")


class TestTheLiftAxis(unittest.TestCase):
    """승강축은 너트를 돌린다 — 표준에서 찾은 결정이 옵션에서 한 등급 오른다."""

    @classmethod
    def setUpClass(cls):
        import analysis_cycle as CYB
        cls.B = CYB
        cls.T = variant.load("twin", "analysis_cycle")["analysis_cycle"]
        cls.rb = {r.id: r for r in CYB.run()[0]}
        with variant.pinned("twin"):
            cls.rt = {r.id: r for r in cls.T.run()[0]}

    def test_turning_the_screw_cannot_make_the_takt(self):
        """CY5 는 쓰지 않는 안이다 — 통과하면 결정의 근거가 사라진 것이다."""
        self.assertFalse(self.rb["CY5"].ok)
        self.assertFalse(self.rt["CY5"].ok)

    def test_the_rotating_nut_makes_the_takt_in_both(self):
        for rs in (self.rb, self.rt):
            for k in ("CY1", "CY2", "CY4", "CY6", "CY7"):
                self.assertTrue(rs[k].ok, f"{k} 초과")
        for k in ("CY3", "CY8", "CY9"):
            self.assertTrue(self.rt[k].ok, f"옵션 {k} 초과")

    def test_the_speed_grade_is_the_slowest_that_fits(self):
        for mod, pin in ((self.B, None), (self.T, "twin")):
            ctx = variant.pinned(pin) if pin else _Null()
            with ctx:
                pt = mod.PT
                grades = pt._LIFT_STD
                i = grades.index(pt.FORK_LIFT_V)
                self.assertLessEqual(mod.lift_cycle(pt.FORK_LIFT_V), 0.85 * mod.CY.TAKT + 1e-9)
                if i:
                    self.assertGreater(mod.lift_cycle(grades[i - 1]), 0.85 * mod.CY.TAKT,
                                       "한 등급 느린 것으로도 된다 — 필요 이상으로 빠르다")

    def test_the_catalogue_says_rotating_nut(self):
        import parts as PT
        p = {x.pid: x for x in PT.P}["P-003-07"]
        self.assertIn("회전 너트", p.name)
        self.assertIn(f"리드 {PT.FORK_LEAD:.0f}", p.note)


class _Null:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


class TestTheOptionChapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import analysis_option as AO
        cls.AO = AO
        cls.summary = AO.summary()
        cls.html = (ROOT / "docs" / "dg-hk60-analysis.html").read_text(encoding="utf-8")

    def test_the_option_adds_no_new_exceedance(self):
        """옵션에서 새로 한계를 넘는 것은 없다.

        한동안 'AL2(단 피치 개구 B)만 새로 넘는다' 고 적혀 있었다 — 옵션 에어록 손실을
        옵션 모듈로, 그 허용(η 를 지키는 몫)을 **표준 열수지로** 셈한 잡종 결과였다.
        analysis_thermal · airlock 이 함수 안에서 늦게 부르는 heatbalance 가 핀 아래에서
        표준 모듈을 집었기 때문이다 (tools/variant.py 의 모듈 목록이 그것을 막는다)."""
        self.assertEqual(self.summary["new_over"], [], self.summary)

    def test_the_airlock_allowance_scales_with_the_option_throughput(self):
        """에어록 몫은 처리량이 정한다 — 옵션 허용이 표준 허용과 같으면 열수지가 섞인 것이다."""
        import airlock as AL_B
        al_t = variant.load("twin", "airlock")["airlock"]
        with variant.pinned("twin"):
            t = {r.id: r for r in self.AO._results(al_t)}
        b = {r.id: r for r in self.AO._results(AL_B)}
        self.assertGreater(t["AL3"].limit, 1.8 * b["AL3"].limit,
                           "옵션 에어록 허용이 표준 열수지에서 나왔다 — 모듈이 섞였다")
        self.assertTrue(t["AL2"].ok, "옵션에서 단 피치 개구 B 가 한계를 넘는다")

    def test_the_report_carries_the_option_chapter_and_its_requirements(self):
        self.assertIn('<div class="clause" id="p12"><div class="n">12</div>', self.html)
        for q in self.AO.requirements():
            self.assertIn(f'<td class="k">{q.id}</td>', self.html, q.id)

    def test_every_option_requirement_says_who_takes_it(self):
        for q in self.AO.requirements():
            self.assertRegex(q.id, r"^RO\d+$")
            self.assertTrue(q.owner.strip())
            self.assertGreaterEqual(len(q.why), 40, q.id)


if __name__ == "__main__":
    unittest.main()
