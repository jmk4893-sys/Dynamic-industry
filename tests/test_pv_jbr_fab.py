"""JBR-201 제작 패키지 — 정본과 부품표의 일치, 그리고 도면집의 멱등.

제작 도면집은 손으로 쓰지 않는다. `tools/build_jbr_fab.py` 가
`src/pv_preprocess/jbr_fabrication.py` 에서 찍어 내고, 여기서는

1. 커밋된 파일이 그 출력과 같은지,
2. 정본이 **부품표에 이미 있는 값**(외형·재질·수량·두께 10 품목)과 어긋나지 않는지,
3. 체결이 공유 표준(토크·구멍·앵커 매입)을 벗어나지 않는지,
4. 하중 검산이 성립하는지 — 이용률이 1 을 넘으면 볼트가 모자란다,
5. 스스로 드러낸 소견(중량·승강 실린더)을 도면집이 **여전히 말하고 있는지**

를 본다. (5) 가 있는 이유는, 소견을 조용히 지워 문서를 깔끔하게 만드는 것이
가장 쉬운 퇴행이기 때문이다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from pv_preprocess import fabrication as fab  # noqa: E402
from pv_preprocess import campaign, fasteners, handoff, jbr_fabrication as jf, mounting  # noqa: E402

PLANT = (ROOT / "docs/drawings/pv-preprocess-plant.html").read_text(encoding="utf-8")
SHEET = ROOT / "docs/drawings/pv-jbr-fab.html"


def _builder():
    spec = importlib.util.spec_from_file_location("build_jbr_fab", ROOT / "tools/build_jbr_fab.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bom() -> dict[str, tuple[str, str, str, str]]:
    """부품표 JB-* 행 → (품명, 수량, 외형, 재질)."""
    i = PLANT.find("wo=[[")
    seg = PLANT[i:i + 400_000]
    out = {}
    for m in re.finditer(r'\["(JB-[A-Z0-9-]+)","[^"]*","([^"]*)","([^"]*)",\[([^\]]*)\],"([^"]*)"', seg):
        out[m.group(1)] = (m.group(2), m.group(3), m.group(4), m.group(5))
    return out


def _base(tag: str) -> str:
    """JB-FR-001A → JB-FR-001. 부품표 1 식을 부재로 편 것이라 접미가 붙는다."""
    return re.sub(r"^(JB-[A-Z]+-\d+)[A-Z]$", r"\1", tag)


class TestJbrFabModel(unittest.TestCase):
    def test_every_part_traces_to_the_bom_or_the_mounting_model(self):
        bom = _bom()
        for p in jf.parts():
            if _base(p.tag) in bom:
                continue
            # 부품표에 없는 것은 하나뿐이고, 그것은 mounting 이 갖고 있다.
            self.assertEqual(p.tag, "JB-FR-006", f"출처 없는 부품: {p.tag}")

    def test_the_anchor_plate_comes_from_the_mounting_model(self):
        """부품표에는 앵커 플레이트가 없다 — mounting 이 갖고 있어 거기서 받는다."""
        m = next(x for x in mounting.MOUNTINGS if x.station == "jbr")
        plate = next(p for p in jf.parts() if p.tag == "JB-FR-006")
        self.assertEqual(m.plate, f"{plate.L:g}×{plate.W:g}×{plate.H:g}")
        base = next(a for a in m.anchors if a.target == "베이스")
        self.assertEqual(plate.qty, base.count)
        self.assertEqual(base.bolt, "M16")

    def test_the_thicknesses_the_bom_states_are_not_re_decided(self):
        """부품표 재질란이 두께를 적어 둔 품목은 정본이 그 값을 그대로 써야 한다."""
        b = _builder()
        self.assertEqual(len(b.BOM_THICKNESS), 10)
        bom = _bom()
        for tag, t in b.BOM_THICKNESS.items():
            part = next(p for p in jf.parts() if p.tag == tag)
            self.assertEqual(part.t, t, f"{tag} 두께가 부품표와 다르다")
            # 부품표 재질란이 정말 그 두께를 적고 있는지도 본다.
            self.assertIn(str(t).rstrip("0").rstrip("."), bom[_base(tag)][3].replace(" ", ""))

    def test_quantities_match_the_bom(self):
        """수량이 갈리면 조달이 갈린다. 부재로 편 것(접미 A–D)은 빼고 본다."""
        bom = _bom()
        for p in jf.parts():
            if p.tag != _base(p.tag) or p.tag not in bom:
                continue
            want = re.match(r"(\d+)", bom[p.tag][1])
            if want and "식" not in bom[p.tag][1]:
                self.assertEqual(p.qty, int(want.group(1)), f"{p.tag} 수량")

    def test_every_material_is_defined(self):
        for p in jf.parts():
            self.assertIn(p.material, jf.MATERIALS, f"{p.tag} 재질 미정의")
            self.assertGreater(jf.weight_kg(p), 0, f"{p.tag} 중량 0")

    def test_fasteners_stay_inside_the_shared_standard(self):
        """볼트를 두 셀이 다르게 조이면 현장이 표를 두 개 들고 다닌다."""
        for j in jf.joints():
            self.assertIn(j.size, fab.TORQUE_NM, f"{j.name} 토크 미정의")
            self.assertIn(j.size, fab.HOLE_MM, f"{j.name} 구멍 미정의")
            if j.kind == "앵커":
                self.assertIn(j.size, fab.ANCHOR_EMBED_MM, f"{j.name} 앵커 매입 미정의")
        for p in jf.parts():
            for h in p.holes:
                self.assertIn(h.bolt, fab.HOLE_MM, f"{p.tag} 구멍 {h.bolt}")

    def test_edge_and_pitch_follow_the_stated_rule(self):
        """가장자리 ≥ 1.5 d · 피치 ≥ 3 d — 체결 표준이 스스로 적은 규칙이다."""
        for p in jf.parts():
            for h in p.holes:
                d = h.dia_mm
                if h.pattern in ("row", "corners") and h.edge:
                    self.assertGreaterEqual(h.edge, 1.5 * d, f"{p.tag} 가장자리 {h.edge} < 1.5×{d}")
                if h.pattern == "row" and h.pitch:
                    self.assertGreaterEqual(h.pitch, 3 * d, f"{p.tag} 피치 {h.pitch} < 3×{d}")

    def test_the_anchor_rods_are_long_enough(self):
        """기준 브랜치가 세운 규칙 — 매입 + 판 + 그라우트 + 부속을 넘어야 한다.

        손으로 적었을 때 5 건 중 4 건이 짧았다. 지금은 계산해서 고르므로 어긋날 수
        없지만, `fasteners` 의 부속 쌓임이 바뀌면 여기서 먼저 깨져야 한다.
        """
        got = jf.anchor_check()
        self.assertEqual(len(got), 5)
        for c in got:
            self.assertTrue(c["ok"], f"{c['name']} {c['bolt']} < 필요 {c['need_mm']}")
            self.assertIn(int(c["length"]), fasteners.ANCHOR_ROD_LENGTHS[c["size"]],
                          f"{c['name']} 길이가 표준 공급 계열에 없다")

    def test_the_loaded_joints_have_capacity(self):
        for c in jf.checks():
            self.assertTrue(c["ok"], f"{c['name']} 이용률 {c['utilisation']}")
            self.assertLessEqual(c["utilisation"], 1.0)

    def test_strength_is_not_what_sets_the_bolt_counts(self):
        """이용률이 1 에 가까워지면 그때부터 강도가 지배한다 — 그 경계를 지킨다."""
        self.assertTrue(jf.LOAD_IS_NOT_BINDING)
        self.assertLess(max(c["utilisation"] for c in jf.checks()), 0.5)

    def test_the_blade_load_comes_from_the_plant(self):
        self.assertEqual(jf.BLADE_THRUST_KN, 15.0)
        self.assertEqual(jf.HEADS, 3)
        self.assertIn("15 kN", PLANT)


class TestJbrFabFindings(unittest.TestCase):
    """도면집이 스스로 드러낸 것 — 조용히 지워지지 않게 붙든다."""

    def test_the_body_is_heavier_than_the_drawing_says(self):
        m = jf.mass_check()
        self.assertFalse(m["ok"])
        self.assertGreater(m["ratio"], 1.5)
        self.assertEqual(m["plant_kg"], 2_200.0)
        self.assertIn("약 2.2 t", PLANT)

    def test_the_lift_cylinders_are_short(self):
        lc = jf.lift_check()
        self.assertFalse(lc["ok"])
        self.assertGreater(lc["utilisation"], 1.0)
        self.assertGreater(lc["bore_needed_mm"], jf.LIFT_BORE_MM)

    def test_the_sheet_still_says_both(self):
        html = SHEET.read_text(encoding="utf-8")
        self.assertIn("본체가 도면의 약 2.2 t 보다", html)
        self.assertIn("실린더 2 개로는 승강부를 들지 못한다", html)
        self.assertIn("하중이 볼트를 정하지 않는다", html)
        self.assertIn("박리 반력은 바닥에 닿지 않는다", html)

    def test_the_notch_capability_item_is_carried_over(self):
        """하류가 받아들인 절결의 여유 0 은 제작 단계 관리 항목이다."""
        html = SHEET.read_text(encoding="utf-8")
        self.assertIn("절입 깊이 공정능력", html)
        self.assertIn(handoff.BACKSHEET_NOTCH_SOURCE, html)


class TestJbrReview(unittest.TestCase):
    """설계 검토가 짚은 것들 — 값이 고쳐지면 여기가 먼저 알려 준다.

    시험이 「불성립」을 단언하는 것이 이상해 보이지만, 이것들은 **아직 안 고친 것**
    이고 고치는 것은 설계 결정이다. 누군가 고치면 이 시험이 깨지면서 「고쳐졌다」를
    알려 준다 — 그때 문구와 미결 항목을 같이 내리면 된다.
    """

    def setUp(self):
        self.b = _builder()
        self.V = self.b.plant_values()
        self.html = SHEET.read_text(encoding="utf-8")

    def test_the_stroke_and_window_come_from_the_plant(self):
        """검산이 손으로 옮긴 숫자 위에 서면 안 된다."""
        self.assertEqual(self.V["stroke_mm"], 360.0)
        self.assertEqual(self.V["shear_s"], 6.0)
        self.assertEqual(self.V["tip_mm"], 0.8)
        self.assertEqual(self.V["head_z"], (-620.0, 0.0, 620.0))
        self.assertEqual(self.V["platen"], (1900.0, 1200.0))

    def test_the_peel_axis_overruns_the_servo(self):
        """힘을 안 넣고 행정÷시간만 나눈 결과 — 가정이 없는 모순이다."""
        c = jf.peel_axis_check(self.V["stroke_mm"], self.V["shear_s"])
        self.assertFalse(c["ok"])
        self.assertGreater(c["motor_rpm"], jf.SERVO_MAX_RPM)
        self.assertGreater(c["lead_needed_mm"], jf.PEEL_SCREW_LEAD_MM)

    def test_the_jam_trip_cannot_be_reached_while_moving(self):
        c = jf.peel_axis_check(self.V["stroke_mm"], self.V["shear_s"])
        self.assertFalse(c["trip_reachable"])
        self.assertLess(c["force_at_speed_kn"], jf.JAM_TRIP_KN)

    def test_the_working_peel_force_is_still_undefined(self):
        """정해지면 여기가 깨진다 — 그때 수명 표와 미결을 같이 닫는다."""
        self.assertIsNone(jf.WORKING_PEEL_KN)
        self.assertEqual(jf.JAM_TRIP_KN, jf.BLADE_THRUST_KN)

    def test_the_ballscrew_life_spans_five_weeks_to_decades(self):
        takt = campaign.summary()["takt_s"]
        hot = jf.ballscrew_life(15.0, self.V["stroke_mm"], takt)
        cool = jf.ballscrew_life(2.0, self.V["stroke_mm"], takt)
        self.assertLess(hot["years_8000h"], 0.2)
        self.assertGreater(cool["years_8000h"], 10)

    def test_the_blade_land_is_inside_commercial_practice(self):
        """「팁 0.8 mm」는 날끝 반경이 아니라 **랜드 두께**다.

        한때 반경으로 잘못 읽고 「절입보다 무디다」고 올렸다가 철회했다. 이 날은
        실리콘만이 아니라 구리 리본도 끊으므로 얇게 갈 수 없고, 상용 제거기도
        0.5 mm 이상을 쓴다. 이제 이 시험은 반대쪽을 지킨다.
        """
        c = jf.blade_geometry_check(self.V["tip_mm"], self.V["wedge_deg"],
                                    self.V["cut_mm"], self.V["cut_tol_mm"])
        self.assertTrue(c["ok"])
        self.assertGreaterEqual(self.V["tip_mm"], jf.BLADE_LAND_MIN_MM)
        self.assertFalse(hasattr(jf, "blade_edge_check"))

    def test_the_pneumatic_option_covers_the_duty(self):
        """상용 방식 — 실린더 수명은 주행거리라 작업력을 몰라도 정해진다."""
        takt = campaign.summary()["takt_s"]
        o = jf.pneumatic_option(80.0, self.V["stroke_mm"], takt)
        self.assertGreaterEqual(o["force_kn"][0], 2.0)
        self.assertGreater(o["years"][0], 3.0)
        self.assertLess(o["air_nl_h"], 25_200)

    def test_the_platen_is_smaller_than_the_panel(self):
        c = jf.support_check(campaign.PANEL_LENGTH_MM, campaign.PANEL_WIDTH_MM,
                             self.V["platen"][0], self.V["platen"][1], self.V["head_z"])
        self.assertFalse(c["ok"])
        self.assertEqual(len(c["heads_outside"]), 2)
        self.assertGreater(c["over_l_mm"], 0)

    def test_the_bridge_deflects_past_the_head_tolerance(self):
        c = jf.bridge_mode((100.0, 150.0), 8.0, 2_500.0, jf.moving_mass_kg(), jf.X_DECEL_MS2)
        self.assertGreater(c["deflection_mm"], 0.10)
        self.assertLess(c["f_hz"], 30)

    def test_the_sheet_carries_every_one_of_them(self):
        for phrase in ("이 구동계로는 이 운동을 못 낸다",
                       "임계가 트립되지 않는다",
                       "5 주와 46 년 사이다",
                       "이 값은 정상 범위다",
                       "상용 제거기는 이 축을 공압 실린더로 민다",
                       "정반이 패널보다 작고",
                       "처짐은 위반이 아니라 정정 시간이다"):
            self.assertIn(phrase, self.html, f"소견이 사라졌다: {phrase}")

    def test_the_detail_sheet_states_why_the_blade_cannot_be_thin(self):
        """철회한 소견의 흔적이 남지 않았는지, 그리고 이유가 적혔는지."""
        detail = (ROOT / "docs/drawings/pv-jbr-detail.html").read_text(encoding="utf-8")
        self.assertNotIn("날이 깨끗이 자른다는 전제", detail)
        self.assertIn("구리 리본도 끊어야 해서 얇게 갈 수 없다", detail)
        self.assertIn("후검증 실측으로 확인할 것", detail)


class TestJbrFabSheet(unittest.TestCase):
    def setUp(self):
        self.b = _builder()
        self.html = SHEET.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.b.build(),
                         "docs/drawings/pv-jbr-fab.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_jbr_fab.py 를 돌리고 커밋한다")

    def test_every_part_gets_a_sheet(self):
        for p in jf.parts():
            self.assertIn(f">{p.tag}", self.html, f"{p.tag} 부품도가 없다")

    def test_it_says_where_each_value_came_from(self):
        self.assertIn("부품표에서 온 것", self.html)
        self.assertIn("하중에서 나온 것", self.html)
        self.assertIn("관례로 고른 것", self.html)
        self.assertIn("구멍은 부품표에 하나도 없었다", self.html)

    def test_the_borrowed_drawing_code_does_not_leak_into_the_infeed_sheet(self):
        """이 셀 재질을 얹었다가 되돌리지 않으면 투입 구간 재질표가 오염된다."""
        spec = importlib.util.spec_from_file_location(
            "build_infeed_fab_probe", ROOT / "tools/build_infeed_fab.py")
        bif = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bif)
        self.b.build()                                   # 먼저 이 셀을 찍고
        infeed = bif.build()                             # 바로 투입 구간을 찍는다
        self.assertNotIn("SKD11", infeed)
        self.assertNotIn("A7075-T6", infeed)
        self.assertEqual(infeed, (ROOT / "docs/drawings/pv-infeed-fab.html").read_text(encoding="utf-8"))

    def test_it_carries_a_description_for_the_hub(self):
        head = self.html[:self.html.index("</head>")]
        self.assertIn('name="description"', head)


if __name__ == "__main__":
    unittest.main()
