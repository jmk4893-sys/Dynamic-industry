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

from . import _path  # noqa: F401

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
        """REV.57: 헤드가 하나라 셀 전체 하중 케이스가 45 kN 에서 15 kN 이 됐다."""
        self.assertEqual(jf.BLADE_THRUST_KN, 15.0)
        self.assertEqual(jf.HEADS, 1)
        self.assertEqual(jf.TOTAL_THRUST_KN, jf.BLADE_THRUST_KN)
        self.assertIn("15 kN", PLANT)
        self.assertNotIn("45 kN 편심", PLANT)

    def test_the_module_table_counts_one_of_each_per_head_module(self):
        """제작·조달 모듈표는 헤드마다 한 벌씩 사는 것을 센다 — 헤드가 하나면 1식이다.

        REV.57 에서 헤드를 줄일 때 3D·부품표·시험계획은 따라왔는데 이 표만
        「3식」으로 남아 있었다. 견적이 여기서 나가면 헤드 값을 세 배로 부른다.
        """
        per_head = ("Y 자동배치축", "L칼날 제거 헤드", "포획·컴플라이언스")
        want = f'{jf.HEADS}식'
        for name in per_head:
            row = next(
                line for line in PLANT.splitlines() if f"<td>{name}</td>" in line
            )
            self.assertIn(
                f'class="text-end">{want}</td>', row, f"{name} 수량이 {want} 이 아니다"
            )


class TestJbrFabFindings(unittest.TestCase):
    """도면집이 스스로 드러낸 것 — 조용히 지워지지 않게 붙든다."""

    def test_the_body_is_heavier_than_the_drawing_says(self):
        m = jf.mass_check()
        self.assertFalse(m["ok"])
        self.assertGreater(m["ratio"], 1.5)
        self.assertEqual(m["plant_kg"], 2_200.0)
        self.assertIn("약 2.2 t", PLANT)

    def test_the_sequential_change_freed_the_lift_cylinders(self):
        """**소견이 스스로 풀렸다** — 3 헤드를 1 헤드로 줄이자 승강 질량이 절반 밑으로 내려갔다.

        REV.56 까지 이 시험은 「Ø63 두 개로는 못 든다」를 붙들고 있었다. 그것은
        45 kN 3 헤드 구성의 결과였지 승강축 자체의 문제가 아니었다. 헤드 두 기와
        그 Y 캐리지·승강 플레이트 여유분이 빠지면서 도면의 재고 보어가 그대로 산다.
        누가 다시 3 헤드로 되돌리면 여기가 먼저 깨진다.
        """
        lc = jf.lift_check()
        self.assertTrue(lc["ok"], f"이용률 {lc['utilisation']}")
        self.assertLess(lc["utilisation"], 1 / jf.LIFT_SAFETY)
        self.assertGreaterEqual(lc["margin"], jf.LIFT_SAFETY)
        self.assertLessEqual(lc["bore_needed_mm"], jf.LIFT_BORE_MM)

    def test_the_lift_still_passes_at_the_low_end_of_the_air_band(self):
        """공압은 압력이 흔들린다 — 규정 하한 0.45 MPa 에서도 서야 한다."""
        self.assertTrue(jf.lift_check(air_mpa=jf.AIR_MPA_MIN)["ok"])

    def test_the_moving_mass_is_a_lower_bound(self):
        """제작품만 셀 수 있다 — 헤드 구매품 7 종은 부품표에 중량 열이 없다."""
        bare = jf.lift_check(include_commercial=False)
        full = jf.lift_check()
        self.assertTrue(bare["lower_bound"])
        self.assertEqual(round(full["moving_kg"] - bare["moving_kg"], 1),
                         jf.HEAD_COMMERCIAL_KG)

    def test_four_points_beat_two_on_air_and_rod_lock(self):
        """큰 판을 두 점으로 드는 것은 힘과 별개의 문제다 — 4×Ø80 이 2×Ø125 를 이긴다."""
        by = {(o["count"], o["bore_mm"]): o for o in jf.lift_options()}
        four80, two125 = by[(4, 80.0)], by[(2, 125.0)]
        self.assertTrue(four80["ok"] and two125["ok"])
        self.assertLess(four80["air_nl_cycle"], two125["air_nl_cycle"])
        self.assertLess(four80["rod_lock_kn"], two125["rod_lock_kn"])

    def test_the_vertical_lift_still_asks_for_margin_not_just_unity(self):
        """합격선은 이용률 1.0 이 아니다 — 여유 1.5 를 유지한다."""
        self.assertGreaterEqual(jf.LIFT_SAFETY, 1.5)
        for o in jf.lift_options():
            with self.subTest(cyl=(o["count"], o["bore_mm"])):
                self.assertEqual(o["ok"], o["margin"] >= jf.LIFT_SAFETY)

    def test_the_sheet_still_says_both(self):
        html = SHEET.read_text(encoding="utf-8")
        self.assertIn("본체가 도면의 약 2.2 t 보다", html)
        self.assertIn("다만 이 중량은 여전히 하한이다", html)
        self.assertIn("하중이 볼트를 정하지 않는다", html)
        self.assertIn("박리 반력은 바닥에 닿지 않는다", html)
        # REV.57: 풀린 소견은 **지웠다가 아니라 뒤집어서** 남긴다 — 왜 풀렸는지가 값이다.
        self.assertIn("실린더를 키워서가 아니라 매다는 것을 줄여서다", html)
        self.assertIn("다시 3 헤드로 되돌리면 이 소견이 그대로 돌아온다", html)
        self.assertNotIn("실린더 2 개로는 승강부를 들지 못한다", html)

    def test_the_sheet_prices_what_the_sequential_change_cost(self):
        """푼 것만 적고 치른 값을 안 적으면 그것은 기록이 아니다."""
        html = SHEET.read_text(encoding="utf-8")
        for phrase in ("순차는 공짜가 아니다",
                       "박리 실린더 교환 주기",
                       "수거함 용량이 반이 됐다",
                       "브리지 임시 호퍼 플랩",
                       "순차가 닫은 것 — 되돌리면 같이 돌아온다"):
            self.assertIn(phrase, html, f"치른 값이 안 적혔다: {phrase}")

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
        """검산이 손으로 옮긴 숫자 위에 서면 안 된다.

        REV.57 에서 박리 창이 6.0 → 1.6 s 로 줄었다. 3 기가 한 번에 6 초를 쓰던
        것을 한 기가 박스마다 쓰기 때문이다 — 같은 45.0 s 안에 세 번 들어가야 한다.
        """
        self.assertEqual(self.V["stroke_mm"], 360.0)
        self.assertAlmostEqual(self.V["shear_s"], 1.6, places=6)
        self.assertEqual(self.V["tip_mm"], 0.8)
        self.assertEqual(self.V["head_z"], (0.0,))
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
        """채택 구동 — 실린더 수명은 주행거리라 작업력을 몰라도 정해진다.

        REV.57 부터 같은 실린더가 패널당 세 번 왕복한다(순차). 수명이 그만큼 짧아지는
        것이 순차의 대가이고, 그 셈이 빠지면 보전 계획이 세 배 낙관이 된다.
        """
        takt = campaign.summary()["takt_s"]
        o = jf.pneumatic_option(80.0, self.V["stroke_mm"], takt)
        self.assertEqual(o["strokes_per_panel"], jf.BOXES_PER_PANEL)
        self.assertGreaterEqual(o["force_kn"][0], 2.0)
        self.assertGreater(o["years"][0], 1.0)
        self.assertLess(o["air_nl_h"], 25_200)
        once = jf.pneumatic_option(80.0, self.V["stroke_mm"], takt, strokes_per_panel=1)
        # 라인 택트가 55.08 s 라 반올림 자리에서 0.1 km 가 갈린다 — 비율만 본다.
        self.assertAlmostEqual(once["km_per_year"] * jf.BOXES_PER_PANEL, o["km_per_year"], delta=0.2)

    def test_the_platen_is_smaller_than_the_panel(self):
        """헤드는 정반 안(z=0)에 주차하고, 패널은 **길이로만** 정반을 넘는다.

        정션박스 워크스페이스에서는 폭도 넘었다(패널 1,400 · 정반 1,300). 이 플랜트는
        라인 상한이 2,400×1,200 이라 폭이 정반 안에 들어온다 — 넘는 것은 길이뿐이고,
        그래서 지지 소견도 길이 쪽만 남는다. 라인 상한이 다시 벤더 포락선으로 올라가면
        (A안) 폭이 다시 넘으므로 이 시험이 먼저 깨진다.
        """
        c = jf.support_check(campaign.PANEL_LENGTH_MM, campaign.PANEL_WIDTH_MM,
                             self.V["platen"][0], self.V["platen"][1], self.V["head_z"])
        self.assertFalse(c["ok"])
        self.assertEqual(c["heads_outside"], ())      # 1 헤드는 정반 안에 선다
        self.assertGreater(c["over_l_mm"], 0)
        self.assertEqual(c["over_w_mm"], 0, "폭이 정반을 넘는다 — 라인 상한을 다시 보라")

    def test_the_sequential_change_brought_the_bridge_inside_tolerance(self):
        """**이 소견도 스스로 풀렸다** — 움직이는 질량이 줄자 처짐과 고유진동수가 같이 나았다.

        REV.56 까지 브리지는 X 감속에서 0.11 mm 처지고 1 차 모드가 30 Hz 아래였다.
        그것도 헤드 세 기를 매단 결과였다. 두 기를 덜어 내자 같은 빔이 규격 안으로
        들어온다 — 빔을 키우는 대신 매다는 것을 줄인 셈이다.
        """
        c = jf.bridge_mode((100.0, 150.0), 8.0, 2_500.0, jf.moving_mass_kg(), jf.X_DECEL_MS2)
        self.assertLessEqual(c["deflection_mm"], 0.10, "헤드 datum ±0.10 을 넘는다")
        self.assertGreaterEqual(c["f_hz"], 30)

    def test_the_sheet_carries_every_one_of_them(self):
        for phrase in ("이 구동계로는 이 운동을 못 낸다",
                       "임계가 트립되지 않는다",
                       "5 주와 46 년 사이다",
                       "이 값은 정상 범위다",
                       "상용 제거기는 이 축을 공압 실린더로 민다",
                       "정반이 패널보다 작다 — 다만 헤드는 이제 정반 안에 선다",
                       "브리지 소견도 매다는 것을 줄여서 풀렸다"):
            self.assertIn(phrase, self.html, f"소견이 사라졌다: {phrase}")

    def test_the_detail_sheet_states_why_the_blade_cannot_be_thin(self):
        """철회한 소견의 흔적이 남지 않았는지, 그리고 이유가 적혔는지."""
        detail = (ROOT / "docs/drawings/pv-jbr-detail.html").read_text(encoding="utf-8")
        self.assertNotIn("날이 깨끗이 자른다는 전제", detail)
        self.assertIn("구리 리본도 끊어야 해서 얇게 갈 수 없다", detail)
        self.assertIn("후검증 실측으로 확인할 것", detail)


class TestJbrBenchPlan(unittest.TestCase):
    """벤치 시험 계획 — 공압으로 바뀌면서 재는 대상이 힘에서 압력으로 옮겨졌다."""

    def test_the_bore_series_is_discrete_and_the_lookup_lands_on_it(self):
        """계열이 이산값이라 측정이 거칠어도 답이 안 갈린다 — 그것이 공압의 이점이다."""
        for kn, want in ((1.5, 63.0), (2.0, 80.0), (2.5, 80.0), (3.0, 100.0)):
            self.assertEqual(jf.bore_for(kn), want, f"{kn} kN")
        for b in jf.BORE_SERIES:
            self.assertIn(b, jf.BORE_SERIES)
        with self.assertRaises(ValueError):
            jf.bore_for(999.0)

    def test_a_twenty_percent_error_does_not_change_the_bore(self):
        """서보였다면 같은 오차가 수명을 두 배로 흔든다 — 그 대비가 계획의 근거다."""
        self.assertEqual(jf.bore_for(2.1), jf.bore_for(2.1 * 1.19))

    def test_the_plan_covers_ageing_and_temperature(self):
        text = " ".join(x for row in jf.bench_plan() for x in row)
        self.assertIn("노화", text)
        self.assertEqual(len(jf.BENCH_TEMPS_C), 2)
        self.assertGreaterEqual(jf.BENCH_SAMPLES, 30)

    def test_every_downstream_condition_is_measured(self):
        """하류 조건 셋이 기하로만 서 있었다 — 이 시험이 실측으로 바꾼다."""
        judged = " ".join(b for _, b, _ in jf.bench_measurements())
        self.assertIn(f"{handoff.RIBBON_STUB_MAX_MM:g}", judged)
        self.assertIn(f"{handoff.SILICONE_RESIDUE_MAX_MM:g}", judged)
        self.assertIn(f"{handoff.BACKSHEET_NOTCH_MAX_MM:g}", judged)

    def test_the_ribbon_gap_is_on_the_measurement_list(self):
        """리본이 도면에 없다 — 같은 시험에서 실측하면 그 자리가 채워진다."""
        items = " ".join(a for a, _, _ in jf.bench_measurements())
        self.assertIn("리본", items)

    def test_the_sheet_says_what_the_test_cannot_answer(self):
        html = SHEET.read_text(encoding="utf-8")
        self.assertIn("이 시험이 답하지 못하는 것", html)
        self.assertIn("재는 것이 힘이 아니라 압력이다", html)


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

    def test_the_borrowed_drawing_code_does_not_leak_into_the_shared_table(self):
        """이 셀 재질을 얹었다가 되돌리지 않으면 **공용 재질표**가 오염된다.

        빌려 온 그리기 함수들이 `fabrication.MATERIALS` 를 직접 본다. 같은 프로세스에서
        다른 셀 도면집도 찍히므로, 얹은 것을 되돌리지 않으면 그쪽 표에 공구강·7075 가
        섞인다. 정션박스 워크스페이스에서는 투입 구간 시트로 그것을 잡았는데, 이
        저장소는 그 시트를 갖고 있지 않으므로 **표 자체**를 찍기 전후로 견준다.
        """
        from pv_preprocess import fabrication as fab
        from pv_preprocess import jbr_fabrication as jf_

        before = dict(fab.MATERIALS)
        self.b.build()
        self.assertEqual(fab.MATERIALS, before, "공용 재질표가 이 셀 재질로 오염됐다")
        for tool_steel in ("SKD11", "A7075-T6"):
            with self.subTest(material=tool_steel):
                self.assertIn(tool_steel, jf_.JBR_MATERIALS)
                self.assertNotIn(tool_steel, fab.MATERIALS)

    def test_it_carries_a_description_for_the_hub(self):
        head = self.html[:self.html.index("</head>")]
        self.assertIn('name="description"', head)


if __name__ == "__main__":
    unittest.main()
