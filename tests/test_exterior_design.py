"""외장 디자인 시스템을 고정한다.

외형은 취향의 문제로 보이지만, 무너지는 방식은 정해져 있다 — 기준선이
하나씩 어긋나고, 색이 한 종류씩 늘고, 캐비닛마다 상표를 두르기 시작한다.
그 셋을 막는다.

  기준선  걸레받이·유리띠·리빌·갓돌이 정해진 순서로 서 있어야 하나의 몸체로
          읽힌다. 하나만 뒤집혀도 외형은 리그로 되돌아간다.
  색      바깥으로 보이는 면은 외장 3색(몸체·리빌·상표)으로만 칠한다.
          안전색이 기계에서 유일하게 채도 높은 것이어야 그 색이 뜻을 갖는다.
  치수    외면은 반입 분할면 베이스플레이트 밖에, 갓돌은 갠트리 보 아래에
          있어야 한다. 이건 취향이 아니라 간섭이다.

컷어웨이·분해·확대에서 외장이 걷히는 것도 함께 고정한다 — 그때 보려는
것은 안쪽이고, 외장이 남아 있으면 그 화면은 쓸모가 없다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def num(self, name):
        m = re.search(rf"\b{name}=(-?[\d.]+)", self.html)
        self.assertIsNotNone(m, f"외장 기준선 {name} 이 없다")
        return float(m.group(1))

    def hexof(self, key):
        m = re.search(rf"\b{key}:'(#[0-9a-fA-F]{{6}})'", self.html)
        self.assertIsNotNone(m, f"팔레트에 {key} 가 없다")
        return m.group(1).lower()

    def fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.html, re.S)
        self.assertIsNotNone(m, f"{name} 함수를 찾지 못했다")
        return m.group(0)


class TestDatumsAreOrdered(_Base):
    def test_horizontal_events_stack_in_order(self):
        seq = ["PLINTH_TOP", "SILL_TOP", "BAND_Z0", "BAND_Z1",
               "SEAM_Z0", "SEAM_Z1", "SKIN_TOP"]
        vals = [self.num(n) for n in seq]
        for a, b, na, nb in zip(vals, vals[1:], seq, seq[1:]):
            self.assertLess(a, b, f"{na}({a}) 가 {nb}({b}) 보다 높다 — 기준선이 뒤집혔다")

    def test_the_body_is_taller_than_a_person(self):
        """눈높이보다 낮으면 외장이 아니라 난간이다."""
        self.assertGreater(self.num("SKIN_TOP"), 2.0)

    def test_the_glazed_band_is_at_eye_level(self):
        lo, hi = self.num("BAND_Z0"), self.num("BAND_Z1")
        self.assertLess(lo, 1.7, "유리띠 아래가 눈높이보다 높다")
        self.assertGreater(hi, 1.7, "유리띠 위가 눈높이보다 낮다")

    def test_plinth_is_recessed_so_the_body_floats(self):
        self.assertGreater(self.num("PLINTH_BACK"), 0.02,
                           "걸레받이를 들여박지 않으면 기계가 바닥에 붙는다")

    def test_joint_rhythm_reads_as_a_seam_not_a_stripe(self):
        mod, rev = self.num("PANEL_MOD"), self.num("REVEAL")
        self.assertGreater(mod, 0.6, "이음 간격이 너무 좁아 무늬가 된다")
        self.assertLess(rev, mod / 20, "리빌이 넓어 이음이 아니라 띠가 된다")


class TestItClearsWhatItMustClear(_Base):
    def test_the_skin_plane_clears_the_transport_split_base_plates(self):
        """TP-2·TP-3 분할면 베이스플레이트가 y=2.18 까지 나온다."""
        self.assertGreater(self.num("SKIN_Y"), 2.18,
                           "외면이 반입 분할면 베이스플레이트를 파고든다")

    def test_the_coping_sits_below_the_gantry_beam(self):
        """갠트리 세로보 밑면이 z=3.64 다. 갓돌이 그 위로 올라가면 뚫린다."""
        self.assertLessEqual(self.num("SKIN_TOP") + self.num("COPE_H"), 3.68)

    def test_the_skin_stops_short_of_the_glass_outfeed(self):
        """유리 반출 빔이 x21.7 에서 +y 로 건너간다."""
        runs = re.search(r"'1'\s*:\[(.*?)\]\];", self.html, re.S)
        self.assertIsNotNone(runs, "+y 외장 구간 정의를 찾지 못했다")
        ends = [float(m) for m in re.findall(r",\s*([\d.]+),'", runs.group(1))]
        self.assertLessEqual(max(ends), 21.6, "+y 외장이 유리 반출 경로를 막는다")


class TestPaletteRestraint(_Base):
    def test_enclosures_are_one_family(self):
        """독립 캐비닛과 클래딩이 다른 회색이면 몸체가 하나로 안 읽힌다."""
        self.assertEqual(self.hexof("skin"), self.hexof("cab"),
                         "외함 색과 클래딩 색이 다르다")

    def test_the_reveal_is_darker_than_the_structure(self):
        """틈은 골조보다 어두워야 깊이로 읽힌다.

        화면·렌즈·벨트(black·belt)는 이보다 더 어두워도 된다 — 그건 재료지
        그림자가 아니다. 비교 대상은 구조 회색뿐이다."""
        rev = self.hexof("reveal")
        lum = lambda h: int(h[1:3], 16) * .30 + int(h[3:5], 16) * .59 + int(h[5:7], 16) * .11
        for key in ("dark", "steel2", "steel", "cab", "skin"):
            self.assertGreater(
                lum(self.hexof(key)), lum(rev),
                f"{key} 가 리빌보다 어둡다 — 틈이 구조보다 깊어야 한다")

    def test_the_skin_is_matte(self):
        """비싼 기계는 반짝이지 않는다. 무광 아노다이즈드가 기준이다."""
        m = re.search(r"\[C\.skin\]\s*:\{sp:([\d.]+)", self.html)
        self.assertIsNotNone(m, "외장 재질이 정의되지 않았다")
        self.assertLessEqual(float(m.group(1)), 0.12, "외장 반사가 너무 세다")

    def test_no_safety_colour_is_painted_on_the_skin(self):
        """안전색이 외장에 쓰이면 안전색이 뜻을 잃는다."""
        body = self.fn("skinWall")
        for bad in ("C.yellow", "C.red", "C.accent", "C.heat", "C.knife"):
            self.assertNotIn(bad, body, f"외장 패널에 {bad} 를 칠했다")

    def test_one_accent_line_not_one_per_cabinet(self):
        """상표선은 몸체를 한 줄로 지나야 한다 — 캐비닛마다 두르면 무늬가 된다."""
        self.assertIn("C.brand", self.fn("skinWall"), "외장에 상표선이 없다")
        self.assertNotIn("C.accent", self.fn("gantry"),
                         "갠트리 보에 두 번째 강조색이 남아 있다")


class TestTheSkinGetsOutOfTheWay(_Base):
    def test_cutaway_explode_and_focus_all_drop_the_skin(self):
        body = self.fn("machineSkin")
        guard = re.search(r"if\((.*?)\)return;", body)
        self.assertIsNotNone(guard, "외장을 걷는 조건이 없다")
        for flag in ("sectionView", "explodeView", "tandemFocus", "carriageFocus"):
            self.assertIn(flag, guard.group(1),
                          f"{flag} 에서 외장이 안 걷힌다 — 그 화면은 안쪽을 보려는 것이다")

    def test_glazed_runs_have_no_opaque_backing(self):
        """유리 뒤에 벽을 세우면 창이 아니라 검은 판이 된다."""
        body = self.fn("skinWall")
        m = re.search(r"if\(kind===('panel')\)box\(V\(cx,yb", body)
        self.assertIsNotNone(
            m, "배면 벽이 패널 구간에만 서는지 확인할 수 없다 — 유리 구간에도 서면 창이 막힌다")
        self.assertIn("멀리언", body, "유리 구간의 이음을 잡는 멀리언이 없다")

    def test_the_roll_port_is_framed_not_missing(self):
        body = self.fn("skinWall")
        self.assertIn("'port'", body, "롤 개구부가 구간 종류로 정의되지 않았다")
        # 주석이 아니라 실제로 그리는 줄을 본다 — 설명만 남기고 부재를 빼도
        # 통과하면 시험이 아니라 문서다.
        block = re.search(r"if\(kind==='port'\)\{(.*?)\n      \}", body, re.S)
        self.assertIsNotNone(block, "개구부 테두리를 그리는 자리가 없다")
        jamb = block.group(1)
        self.assertIn("x0+", jamb, "개구부 시작쪽 문설주가 없다")
        self.assertIn("x1-", jamb, "개구부 끝쪽 문설주가 없다")
        self.assertIn("C.reveal", jamb, "개구부 상인방 리빌이 없다 — 위가 열린 채로 끝난다")
        self.assertIn("'port'", re.search(r"SKIN_RUNS=\{.*?\};", self.html, re.S).group(0),
                      "롤 개구부 구간이 배치에 없다")

    def test_the_skin_is_placed(self):
        self.assertIn("machineSkin();", self.html, "외장이 배치에 놓이지 않았다")


class TestSpecificationCarriesTheSystem(_Base):
    """외장 기준선은 사양서에도 있어야 한다.

    콘솔만 고쳐 두면 제작사는 그것을 본 적이 없다. 6.8항의 수치가 콘솔
    상수에서 재계산한 값과 같은지 대조한다 — 한쪽만 고치면 실패한다."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rfq = (ROOT / "docs" / "dg-hk60-rfq.html")

    def test_the_spec_repeats_the_console_datums(self):
        if not self.rfq.exists():
            self.skipTest("이 브랜치에는 사양서가 없다")
        body = self.rfq.read_text(encoding="utf-8")
        for name, fmt in (("PLINTH_TOP", "{:.0f} mm"), ("BAND_Z0", "{:,.0f}"),
                          ("BAND_Z1", "{:,.0f}"), ("SEAM_Z0", "{:,.0f}"),
                          ("SEAM_Z1", "{:,.0f}"), ("SKIN_TOP", "{:,.0f}")):
            mm = self.num(name) * 1000
            self.assertIn(fmt.format(mm), body,
                          f"사양서 6.8 의 {name} 이 콘솔 상수({mm:.0f} mm)와 다르다")
        self.assertIn(f"{self.num('PANEL_MOD') * 1000:,.0f} mm", body,
                      "사양서 6.8 의 이음 박자가 콘솔과 다르다")
        self.assertIn(f"{self.num('REVEAL') * 1000:.0f} mm", body,
                      "사양서 6.8 의 리빌 폭이 콘솔과 다르다")
        self.assertIn(f"{self.num('PLINTH_BACK') * 1000:.0f} mm", body,
                      "사양서 6.8 의 걸레받이 들여박기가 콘솔과 다르다")


if __name__ == "__main__":
    unittest.main()
