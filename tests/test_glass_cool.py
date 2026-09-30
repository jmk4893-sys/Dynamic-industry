"""GC-101 유리 냉각 — 설계 h 를 무엇이 내는가.

콘솔은 냉각 랙 단수를 GCOOL_H = 25 W/(m²·K) 한 숫자에서 냈지만, 그 h 를 내는 장치는
세지 않았다. 랙 −y 벽에 축류 팬 한 줄(Ø520 × 단수 + 1)을 476 피치로 그려 팬끼리 ·
가운데 기둥과 겹쳤고, 카탈로그는 같은 팬을 '지붕 프레임' 에 달았다. 무엇보다 옆에서 부는
바람으로는 그 h 에 필요한 풍량을 급기 필터 면이 받지 못했다.

    tools/glass_cool.py  필요 h → 교차류 후보 A · B (탈락) → 냉각 뱅크(분사 · Martin)
      → 급기량 · 압력 · 전동기 · 소음기 → 카탈로그 M-007 · 조달 사양
      → 콘솔 3D · F-007 · D-602 P4 · 열해석 T8 · T14 · 파일럿 PT-06 · 사양서 3.4

여기서 사슬이 끊기면 걸린다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import analysis_thermal as TH
import glass_cool as GL
import parts as PT
import procure as PR
import variant
from console_consts import const as c

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"


def _part(pid):
    return next(p for p in PT.P if p.pid == pid)


def _fn(src, name):
    i = src.index(f"function {name}(")
    j = src.index("\n    function ", i + 10)
    return src[i:j]


class TestTheRequiredCoefficient(unittest.TestCase):
    def test_the_required_h_is_the_residence_time(self):
        """필요 h 로 식히면 정확히 단수 × 택트가 걸린다 — 식이 콘솔 glassCoolSec 과 같다."""
        h = GL.h_required()
        self.assertAlmostEqual(GL.cool_time(h), GL.DECKS * GL.TAKT, places=6)
        lmtd = (GL.T_IN - GL.T_OUT) / math.log((GL.T_IN - GL.T_AMB) / (GL.T_OUT - GL.T_AMB))
        console_t = GL.M_GLASS * GL.CP_GLASS * (GL.T_IN - GL.T_OUT) / (GL.H_DESIGN * 2 * lmtd)
        self.assertAlmostEqual(GL.cool_time(GL.H_DESIGN), console_t, places=6)

    def test_the_design_h_covers_the_rack(self):
        self.assertGreaterEqual(GL.H_DESIGN, GL.h_required(), "설계 h 로는 랙 단수 안에 안 식는다")
        t9 = next(r for r in TH.run()[0] if r.id == "T9")
        self.assertTrue(t9.ok, "열해석 T9 가 넘는다")


class TestTheSideBlowingFansCannotDoIt(unittest.TestCase):
    """두 팬 배치(A · B)는 셌고 버렸다 — 그 판정이 계산에서 나와야 한다."""

    def test_crossflow_needs_more_air_than_the_filter_face_takes(self):
        n, _a = GL.filter_face()
        cap = n * GL.FILTER_Q
        self.assertGreater(GL.crossflow_q(GL.h_required()), cap,
                           "옆바람으로 필요 h 를 필터 면 정격 안에서 낸다 — 판정을 다시 본다")
        self.assertGreater(GL.crossflow_q(GL.H_DESIGN), 2 * cap)

    def test_a_laminar_boundary_layer_halves_it(self):
        v = GL.v_crossflow(GL.H_DESIGN)
        self.assertLess(GL.h_crossflow(v, laminar=True), GL.H_DESIGN / 2)

    def test_both_fan_layouts_fail(self):
        a, b = GL.candidate_a(), GL.candidate_b()
        self.assertTrue(GL.verdict(a), "A (3 단 × 2 칸) 가 통과한다")
        self.assertTrue(GL.verdict(b), "B (칸마다 Ø450 × 3) 가 통과한다")
        self.assertGreater(a["v_face"], a["v_face_rated"], "A 의 필터 면속도가 정격 안이다")
        self.assertGreater(a["lp"], GL.LP_LIMIT - GL.LP_OTHER, "A 의 소음이 기준 안이다")
        self.assertLess(b["h"], GL.h_required(), "B 가 필요 h 를 낸다")

    def test_the_largest_fan_that_fits_a_bay(self):
        """A 는 칸(기둥 사이)과 벽 높이의 1/3 에 드는 가장 큰 팬이다 — 옛 Ø520 은 476 피치로 겹쳤다."""
        a = GL.candidate_a()
        wall = (GL.RACK_TOP - 0.06) - GL.FACE_Z0
        self.assertLessEqual(a["d"] + GL.AXIAL_HOUSING, min(GL.BAY, wall / 3) + 1e-9)
        bigger = [s for s in GL.AXIAL_SIZES if s > a["d"]]
        if bigger:
            self.assertGreater(bigger[0] + GL.AXIAL_HOUSING, min(GL.BAY, wall / 3))


class TestTheCoolingBanks(unittest.TestCase):
    def test_the_jets_deliver_the_design_h_with_margin(self):
        m = GL.martin()
        self.assertTrue(m["valid"], f"Martin 상관식 범위 밖 — Re {m['re']:.0f} · f {m['f']:.4f} · H/D {m['hd']:.1f}")
        self.assertGreaterEqual(m["h"], GL.H_MARGIN * GL.H_DESIGN,
                                f"분사 h {m['h']:.1f} < 설계 {GL.H_DESIGN} × {GL.H_MARGIN}")
        self.assertLessEqual(m["s_h"], GL.SH_MAX, "노즐 피치가 거리보다 커서 칸 무늬가 유리에 찍힌다")
        t14 = next(r for r in TH.run()[0] if r.id == "T14")
        self.assertTrue(t14.ok)
        self.assertAlmostEqual(t14.limit, m["h"], places=9)

    def test_the_banks_stand_where_the_ir_banks_stand(self):
        self.assertEqual(GL.BANKS, GL.DECKS + 1)
        self.assertAlmostEqual(GL.jet_gap(), c("CDECK_DZ") / 2 - c("GCOOL_BANK_T") / 2, places=12)
        self.assertEqual(_part("P-007-09").qty, 2 * GL.BANKS, "장변 측판이 뱅크마다 두 장이 아니다")
        self.assertEqual(_part("P-007-19").qty, 2 * GL.BANKS, "단변 측판이 뱅크마다 두 장이 아니다")
        self.assertEqual(_part("P-007-10").qty, 2 * GL.BANKS)
        self.assertEqual(_part("P-007-07").qty, 2 * GL.DECKS, "노즐판이 유리 한 면에 한 장이 아니다")
        self.assertEqual(_part("P-007-08").qty, 2, "막음판은 맨 위 · 맨 아래 둘이다")

    def test_the_nozzle_plate_carries_the_nozzles_the_flow_counts(self):
        """급기량은 노즐 수 × 면적 × 속도다 — 노즐판의 구멍이 그 노즐이다."""
        holes = _part("P-007-07").shape.d["holes"]
        nx, ny = GL.jets_per_face()
        self.assertEqual(len(holes), nx * ny)
        for x, y, d in holes:
            self.assertAlmostEqual(d, GL.JET_D * 1000, places=9)
        xs = sorted({round(h[0], 6) for h in holes})
        self.assertTrue(all(abs((b - a) - GL.JET_S * 1000) < 1e-6 for a, b in zip(xs, xs[1:])),
                        "노즐 피치가 GCOOL_JET_S 가 아니다")
        q = 2 * GL.DECKS * len(holes) * math.pi / 4 * GL.JET_D ** 2 * GL.JET_V
        self.assertAlmostEqual(GL.air_flow(), q, places=9)
        self.assertAlmostEqual(PT.GC_AIR_Q, q, places=9)

    def test_the_plenum_feeds_every_nozzle_alike(self):
        self.assertLessEqual(GL.bank_inlet()["ratio"], GL.PLENUM_RATIO,
                             "뱅크 안 흐름이 분사 속도에 비해 빨라 노즐마다 풍량이 갈린다")

    def test_the_unit_is_sized_from_the_flow(self):
        d = GL.design()
        self.assertLessEqual(d["q"] / d["filters"], GL.FILTER_Q + 1e-12, "필터가 정격을 넘는다")
        self.assertEqual(_part("P-007-17").qty, d["filters"])
        self.assertEqual(_part("P-007-18").qty, d["filters"])
        self.assertGreaterEqual(d["motor"]["kw"], d["motor"]["kw_shaft"] * GL.MOTOR_MARGIN - 1e-9)
        self.assertLessEqual(d["noise"]["lp"], GL.LP_LIMIT - GL.LP_OTHER + 1e-9,
                             "방책선 · 통로 소음이 사양서 80 dBA 에서 다른 소음원 몫을 뺀 값을 넘는다")
        u = _part("P-007-13").shape.d
        self.assertAlmostEqual(u["H"], d["ahu"]["H"] * 1000, places=6)
        self.assertAlmostEqual(u["W"], GL.AHU_DEPTH * 1000, places=6)

    def test_the_unit_fits_between_the_column_plates_and_the_skin(self):
        a = GL.ahu()
        plate_edge = GL.RACK_COL_Y + 0.20
        self.assertGreaterEqual(a["y0"] - plate_edge, 0.05 - 1e-9, "급기 유닛이 기둥 판에 붙는다")
        self.assertLess(a["y1"], GL.CSKIN_Y, "급기 유닛이 외장 밖으로 나간다")
        self.assertLessEqual(GL.MANIFOLD_W, GL.BAY, "매니폴드가 한 칸에 들지 않는다")

    def test_the_purchase_spec_says_what_the_model_says(self):
        d = GL.design()
        spec = PR.BUY_SPEC["P-007-13"][1]
        for tok in (f"{d['q']:.2f} m³/s", f"{d['dp']['total']:.0f} Pa", f"{d['motor']['kw']:g} kW",
                    f"IL ≥ {d['noise']['il']} dB", "G4 + F7"):
            self.assertIn(tok, spec, f"급기 유닛 구매 사양에 '{tok}' 가 없다")
        for pid in ("P-007-14", "P-007-15", "P-007-16", "P-007-17", "P-007-18"):
            self.assertIn(pid, PR.BUY_SPEC, f"{pid} 구매 사양이 없다")

    def test_the_fan_row_is_gone(self):
        names = " ".join(p.name + p.fix + p.note for p in PT.P if p.pid.startswith("P-007"))
        for gone in ("Ø520", "지붕 프레임", "냉각 팬", "팬 가드"):
            self.assertNotIn(gone, names, f"철거한 팬 줄의 '{gone}' 가 카탈로그에 남아 있다")
        self.assertFalse(hasattr(PT, "GC_FANS"))


class TestTheOptionRack(unittest.TestCase):
    """옵션(7 단 · 택트 절반)도 같은 뱅크 · 같은 노즐로 선다 — 급기량과 유닛만 커진다."""

    @classmethod
    def setUpClass(cls):
        cls.g = variant.load("twin", "glass_cool")["glass_cool"]
        with variant.pinned("twin"):
            cls.d = cls.g.design()
            cls.cand = [cls.g.verdict(r) for r in cls.g.candidates()]

    def test_the_option_passes_with_the_same_nozzles(self):
        self.assertEqual(self.d["banks"], 8)
        self.assertGreaterEqual(self.g.H_DESIGN, self.d["h_req"], "옵션은 설계 h 로 단수 안에 안 식는다")
        self.assertGreaterEqual(self.d["h_jet"], self.g.H_MARGIN * self.g.H_DESIGN)
        self.assertEqual(self.cand[2], [], "옵션 냉각 뱅크가 떨어진다")
        self.assertTrue(self.cand[0] and self.cand[1], "옵션에서 팬 배치가 통과한다")
        self.assertLessEqual(self.d["noise"]["lp"], self.g.LP_LIMIT - self.g.LP_OTHER + 1e-9)
        self.assertGreater(self.d["q"], GL.air_flow(), "옵션 급기량이 표준보다 크지 않다")


class TestTheConsoleDrawsTheBanks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.rack = re.sub(r"\s+", "", _fn(cls.src, "cGlassRack"))
        cls.f007 = _fn(cls.src, "coolerFabDrawing")

    def test_the_console_flow_is_the_model_flow(self):
        """콘솔 gcoolJets · gcoolAirQ 가 파이썬과 같은 식이다."""
        flat = re.sub(r"\s+", "", self.src)
        self.assertIn("constgcoolJets=()=>Math.floor(PANEL_L/GCOOL_JET_S+1e-9)*Math.floor(PANEL_W/GCOOL_JET_S+1e-9);", flat)
        self.assertIn("constgcoolAirQ=decks=>2*decks*gcoolJets()*Math.PI/4*GCOOL_JET_D**2*GCOOL_JET_V;", flat)

    def test_the_3d_rack_has_a_bank_in_every_ir_slot(self):
        self.assertIn("for(letb=0;b<=DK;b++){constz=CDECK_Z0+CDECK_DZ*b;", self.rack)
        self.assertIn("box(V(g.cx,0,z),V(bankL,bankW,BT),C.steel2);", self.rack)
        self.assertIn("find(p=>p.id==='P-007-13')", self.rack, "급기 유닛 크기를 카탈로그에서 읽지 않는다")
        for gone in ("cylinder(V(x,-1.06,fanZ)", "fanZ", "필터급기면"):
            self.assertNotIn(gone, self.rack, f"철거한 팬 줄 · 필터 면({gone})이 3D 에 남아 있다")

    def test_the_rack_ball_screws_are_gone(self):
        """랙은 고정이다 — 카탈로그에 없는 승강 볼스크류를 그리지 않는다."""
        body = re.sub(r"\s+", "", _fn(self.src, "cRack"))
        self.assertNotIn("cylinder(V(cx+sx*(L/2-.30),y,opt.top/2+.35)", body)

    def test_f007_draws_banks_not_fans(self):
        for tok in ("냉각 뱅크 ×${BANKS}", "gcoolAirQ(DK)", "GCOOL_JET_D", "CAL-001 T14",
                    "rev:'2',date:'2026-09-30'"):
            self.assertTrue(tok in self.f007, f"F-007 에 '{tok}' 가 없다")
        for gone in ("축류 Ø520", "냉각 팬 ×${FANS}", "FANZ"):
            self.assertFalse(gone in self.f007, f"F-007 에 철거한 팬 줄 '{gone}' 가 남아 있다")

    def test_the_foundation_plan_seats_the_unit(self):
        body = _fn(self.src, "foundationDrawing")
        self.assertTrue("{id:'P4',eq:'GC 냉각 급기 유닛'" in body, "D-602 에 급기 유닛 패드가 없다")
        self.assertTrue("PARTS.find(p=>p.id==='P-007-13').g.L/1000" in body)


class TestTheSpecificationSaysWhatWasComputed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rfq = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", RFQ.read_text(encoding="utf-8")))
        cls.d = GL.design()

    def test_clause_3_4_carries_the_model_numbers(self):
        d, m = self.d, self.d["martin"]
        for tok in (f"단수 + 1 = {d['banks']}곳", f"Ø{GL.JET_D * 1000:.0f} @{GL.JET_S * 1000:.0f}",
                    f"{GL.JET_V:g} m/s", f"{m['h']:.1f} W/(m²·K)", f"{d['q']:.2f} m³/s",
                    f"{d['noise']['lp']:.0f} dB(A)", f"{d['heat_kw']:.1f} kW",
                    f"{d['cross_q_design']:.0f} m³/s", f"{d['cross_q_req']:.0f} m³/s",
                    f"{d['filter_face_q']:.0f} m³/s", f"{GL.candidate_a()['lp']:.0f} dB(A)",
                    f"h {GL.candidate_b()['h']:.1f}"):
            self.assertIn(tok, self.rfq, f"사양서 3.4 에 모델 값 '{tok}' 가 없다")
        self.assertIn("옆에서 부는 팬을 쓰지 않는다", self.rfq)


if __name__ == "__main__":
    unittest.main()
