"""JBR-201 정션박스 제거장치 파생본 — 생성기 출력과 커밋된 파일, 그리고 모델과의 일치.

파생본은 손으로 쓰지 않는다. `tools/build_jbr_scene.py` 가 통합 설계도에서 JBR 셀만
남겨 찍어 내고, 여기서는 (1) 커밋된 파일이 그 출력과 같은지, (2) 시계 창이 캠페인
모델에서 온 값인지, (3) 원본 3D 형상 코드가 그대로인지(파생본은 보이기만 끈다),
(4) 아티팩트 변환기가 받아들이는 문서인지를 본다.
"""

from __future__ import annotations

import importlib.util
import math
import pathlib
import re
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, layout, servos

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENE = ROOT / "docs/drawings/pv-jbr-scene.html"
DETAIL = ROOT / "docs/drawings/pv-jbr-detail.html"
CLOSEUP = ROOT / "docs/drawings/pv-jbr-closeup.html"
HUB = ROOT / "docs/drawings/pv-jbr-hub.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestJbrScene(unittest.TestCase):
    """통합 설계도에서 JBR-201 셀만 남긴 파생본."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_jbr_scene")
        cls.html = SCENE.read_text(encoding="utf-8")
        cls.plant = cls.builder.PLANT.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-jbr-scene.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_jbr_scene.py 를 돌리고 커밋한다")

    def test_the_clock_window_is_the_cell_occupancy(self):
        """창은 [투입부 점유, 투입부 점유 + JBR 점유] 다 — 새로 정한 숫자가 없다."""
        t0, t1 = self.builder.window()
        self.assertEqual(t0, campaign.INFEED_S)
        self.assertEqual(t1, campaign.INFEED_S + campaign.JBR_S)
        self.assertIn(f",ci={t1:g}", self.html)
        self.assertIn(f",Ve={t0:g},ai=0", self.html)
        self.assertIn(f'min="{t0:g}" max="{t1:g}"', self.html)
        self.assertNotIn(",ci=nt+Lr", self.html)
        self.assertNotIn('max="124.03"', self.html)

    def test_every_rewind_lands_inside_the_window(self):
        """조작을 바꿔도 시계가 창 밖(0 s)으로 되감기면 안 된다."""
        t0, _ = self.builder.window()
        # 원본의 `Ve=0` 은 선언 1 + 되감기 6 이다. 생성기는 선언을 먼저 바꾸고 남은 6 을 센다.
        self.assertEqual(len(re.findall(r"\bVe=0\b", self.plant)), 7, "원본의 되감기 수가 바뀌었다")
        self.assertNotIn("Ve=0", self.html)
        # 파생본의 `Ve=40` 은 선언 1 + 반복 되돌림 1 + 되감기 6 이다.
        self.assertEqual(len(re.findall(rf"\bVe={t0:g}\b", self.html)), 8)
        self.assertIn(f"Ve={t0:g}+(Ve-{t0:g})%(ci-{t0:g})", self.html)

    def test_only_jbr_views_and_the_jbr_sheet_remain(self):
        views = re.findall(r'data-jb-view="([a-z]+)" type="button"', self.html)
        self.assertEqual(sorted(views), sorted(self.builder.KEEP_VIEWS))
        for view in self.builder.AUTO_VIEWS:
            self.assertIn(view, self.builder.KEEP_VIEWS, "자동추적이 고르는 시점이 버튼에 없다")
        sheets = self.html.split('id="pv-drawing-station"')[1][:900]
        for key in self.builder.DROP_STATIONS:
            self.assertNotIn(f'<option value="{key}"', sheets)
        self.assertIn('<option value="jbr" selected>', sheets)
        self.assertIn(',xl="overall"', self.html)

    def test_the_auto_camera_list_is_the_plant_literal(self):
        """자동추적 시점 목록이 원본과 어긋나면 파생본의 시점 버튼이 모자란다."""
        literal = ",".join(f'"{v}"' for v in self.builder.AUTO_VIEWS)
        self.assertIn(f"ue=[{literal}]", self.plant)

    def test_the_scene_is_narrowed_not_rewritten(self):
        """3D 형상 코드는 원본과 같아야 한다 — 파생본은 보이기만 끈다."""
        i = self.plant.index("var pvZone=")
        j = self.plant.index("Ae.__pvScene=")
        patched = (",ci=nt+Lr", ',xl="line"', "fp.line:fp[i]", '"reset"?"line"',
                   "overall:{position:new C(3.5,6,-10.2)")
        for line in self.plant[i:j].splitlines():
            if any(anchor in line for anchor in patched):
                continue
            self.assertIn(line, self.html, f"원본 장면 코드가 파생본에서 바뀌었다: {line[:80]}")
        self.assertIn("window.__pvJbrScene", self.html)

    def test_the_scene_boundary_is_the_zone_table(self):
        low, high = self.builder.zone_world_x()
        zone = next(z for z in layout.build_zones() if z.key == "jbr")
        self.assertEqual(low, (zone.x0_mm - self.builder.SCENE_ORIGIN_X_MM) / 1000)
        self.assertEqual(high, (zone.x1_mm - self.builder.SCENE_ORIGIN_X_MM) / 1000)
        self.assertIn(f"const LOW = {low:g};", self.html)
        self.assertIn(f"const HIGH = {high:g};", self.html)

    def test_out_of_scope_controls_are_hidden_and_the_cell_keeps_its_own(self):
        for key in self.builder.HIDDEN_CONTROLS:
            self.assertIn(f'label[for="{key}"]', self.html)
        self.assertIn('id="afr-buffer-reset" type="button" hidden', self.html)
        for key in ("jb-box-mode", "jb-validation-mode", "pv-panel-structure"):
            self.assertIn(f'<label class="form-label" for="{key}">', self.html)
            self.assertNotIn(f'label[for="{key}"] {{ display: none', self.html)
        self.assertNotIn("ENGINEERING BASE REV.22", self.html)
        self.assertIn("JBR-201 단독 파생본", self.html)

    def test_the_casing_is_off_by_default(self):
        """이 파생본은 기구를 보는 화면이다 — 껍질은 기본으로 벗겨 둔다."""
        self.assertIn('<input class="form-check-input" id="pv-case" type="checkbox" checked>',
                      self.plant, "원본은 켜 둔 채로 나간다")
        self.assertIn('<input class="form-check-input" id="pv-case" type="checkbox">', self.html)
        self.assertNotIn('id="pv-case" type="checkbox" checked', self.html)

    def test_the_flow_strip_shows_only_the_handoffs_and_the_cell(self):
        first, last = self.builder.FLOW_FIRST, self.builder.FLOW_LAST
        self.assertEqual((first, last), (6, 8))
        self.assertIn(f".pv-flow-track > li:nth-child(-n+{first - 1})", self.html)
        self.assertIn(f".pv-flow-track > li:nth-child(n+{last + 1})", self.html)
        steps = re.findall(r'<li data-flow-step="(\d+)"', self.html)
        self.assertEqual(len(steps), 11, "흐름표 칸은 지우지 않고 CSS 로만 가린다")

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("jbr-scene", conv.TARGETS)
        body = conv.convert(self.html, SCENE)
        self.assertIn("<title>JBR-201 정션박스 제거장치</title>", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-scene.html", readme)
        self.assertIn("tools/build_jbr_scene.py", readme)


class TestJbrDetail(unittest.TestCase):
    """JBR-201 상세도 — 설계 모델·통합 설계도 리터럴에서 찍은 값이 맞는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_jbr_detail")
        cls.html = DETAIL.read_text(encoding="utf-8")
        cls.plant = cls.builder.plant_text()

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-jbr-detail.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_jbr_detail.py 를 돌리고 커밋한다")

    def test_the_stage_list_comes_from_the_plant_and_starts_at_infeed_end(self):
        rows = self.builder.stages(self.plant)
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[0][1], 0.0)
        self.assertEqual(rows[-1][2], campaign.JBR_S,
                         "스테이지 마지막이 campaign.JBR_S 와 다르다")
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(a[2], b[1], f"{a[0]} 와 {b[0]} 사이가 안 이어진다")
        num = self.builder.n
        for name, start, end in rows:
            self.assertIn(f"<td>{name}</td>", self.html)
            self.assertIn(f'<td class="num">{num(campaign.INFEED_S + start)}</td>', self.html)
            self.assertIn(f'<td class="num">{num(campaign.INFEED_S + end)}</td>', self.html)

    def test_the_ga_sheet_matches_the_layout_model(self):
        ga = self.builder.ga_sheet(self.plant)
        station = layout.STATIONS["jbr"]
        self.assertEqual(ga["sheet"], station.sheet)
        self.assertEqual(tuple(ga["envelope"]), station.envelope)
        self.assertEqual(ga["transfer"], station.transfer_height_mm)
        self.assertEqual(ga["transfer"], layout.LINE_TRANSFER_MM)
        self.assertEqual(len(ga["flow"]), 7)
        self.assertEqual(len(ga["parts"]), 13)
        self.assertIn(f"<code>{station.sheet}</code>", self.html)

    def test_the_zone_numbers_are_the_zone_table(self):
        z = next(x for x in layout.build_zones() if x.key == "jbr")
        self.assertIn(f"{z.x0_mm:,} … {z.x1_mm:,} mm", self.html)
        self.assertIn(f"{z.y0_mm:,} … {z.y1_mm:,} mm", self.html)
        self.assertIn(f"{layout.STATION_HARDWARE_X_MM['jbr']:,} mm", self.html)

    def test_the_part_origin_is_the_equipment_centre_not_the_zone_centre(self):
        """GA 부품 좌표의 원점은 장비 중심이다 — BASE 를 거기 두어야 모델의 여유가 나온다."""
        z = next(x for x in layout.build_zones() if x.key == "jbr")
        up, down = layout.station_edges_mm("jbr")
        hw = layout.STATION_HARDWARE_X_MM["jbr"]
        x0, x1 = self.builder.hardware_span_mm()
        self.assertEqual((x0, x1), (z.x0_mm + up, z.x0_mm + up + hw))
        self.assertEqual(x0 - z.x0_mm, up)
        self.assertEqual(z.x1_mm - x1, down)
        # 존 중심에 두면 여유가 대칭이 되어 모델의 비대칭 분할과 어긋난다.
        self.assertNotEqual(up, down, "여유가 대칭이면 이 시트의 원점 주의가 필요 없다")
        offset = self.builder.origin_offset_mm()
        self.assertEqual(offset, (up - down) / 2)
        self.assertIn(f"<b>{self.builder.n(offset)} mm 하류</b>", self.html)

    def test_the_detection_scenarios_match_the_force_check(self):
        scen = self.builder.box_scenarios(self.plant)
        cap, heads, counts = self.builder.head_force(self.plant)
        self.assertEqual(heads, 3)
        for s in scen:
            with self.subTest(scenario=s["key"]):
                self.assertEqual(len(s["boxes"]), counts[s["key"]],
                                 "hp 리터럴의 박스 수와 BOX_COUNT 가 다르다")
                xs = {round(b["x"], 6) for b in s["boxes"]}
                self.assertEqual(len(xs), 1, "같은 X 열이어야 3헤드가 한 스트로크로 민다")
                self.assertIn(f"<td>{s['plan']}</td>", self.html)
        for s in scen:
            available = cap * min(counts[s["key"]], heads)
            self.assertIn(f'<td class="num">{available}</td>', self.html)

    def test_every_validation_scenario_has_a_row(self):
        options = self.builder.select_options(self.plant, self.builder.VALIDATION_SELECT_ID)
        self.assertEqual(len(options), 10)
        w = self.builder.block_times(self.plant)
        for key, _ in options:
            self.assertIn(f"<code>{key}</code>", self.html)
        num = self.builder.n
        for key, local in w.items():
            with self.subTest(scenario=key):
                self.assertIn(f'<td class="num">{num(campaign.INFEED_S + local)}</td>', self.html)

    def test_the_voltage_chain_and_reject_path_come_from_the_bom(self):
        parts = self.builder.catalog(self.plant)
        pv = self.builder.by_prefix(parts, "JB-PV-")
        rj = self.builder.by_prefix(parts, "JB-RJ-")
        self.assertEqual(len(pv), 6)
        self.assertEqual(len(rj), 4)
        for row in pv + rj:
            self.assertIn(f"<code>{row[0]}</code>", self.html)
            self.assertIn(f"<td>{row[2]}</td>", self.html)

    def test_the_design_has_no_discharge_circuit(self):
        """차광하고 재서 허가할 뿐, 패널을 방전시키는 회로는 이 설계에 없다."""
        self.assertTrue(self.builder.discharge_is_absent(self.plant))
        self.assertNotIn("방전", self.plant)
        self.assertIn("방전(단락) 회로가 없다</b>.", self.html,
                      "없다고 적었는데 도면에 방전이 생기면 문장이 어긋난다")

    def test_the_bom_is_every_jb_part(self):
        parts = self.builder.catalog(self.plant)
        self.assertGreaterEqual(len(parts), 100)
        self.assertIn(f"JB-* {len(parts)} 품번", self.html)
        for row in parts:
            self.assertIn(f"<code>{row[0]}</code>", self.html)

    def test_the_drive_axes_are_the_servo_model(self):
        axes = [a for a in servos.SERVO_AXES if a.panel == "LP-JBR"]
        motors = [m for m in servos.MOTORS if m.panel == "LP-JBR"]
        self.assertEqual(sum(a.qty for a in axes), servos.servo_axis_count_for("LP-JBR"))
        for a in axes + motors:
            self.assertIn(f"<td>{a.tag}</td>", self.html)
        total = sum(a.rated_kw * a.qty for a in axes + motors)
        self.assertEqual(total, servos.motion_kw_by_panel()["LP-JBR"])
        self.assertIn(f"<b>{total:,.2f}</b>".rstrip("0").rstrip("."), self.html)

    def test_the_bottleneck_is_named_from_the_model_not_asserted(self):
        """JBR 45 s 는 두 번째다 — 병목을 도면이 아니라 모델에서 읽는다."""
        self.assertIn(campaign.bottleneck(), self.html)
        self.assertNotEqual(campaign.bottleneck(), "JBR-201")

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("jbr-detail", conv.TARGETS)
        body = conv.convert(self.html, DETAIL)
        self.assertIn("<title>JBR-201 정션박스 제거장치 상세도</title>", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-detail.html", readme)
        self.assertIn("tools/build_jbr_detail.py", readme)


class TestJbrCloseup(unittest.TestCase):
    """박리 순간 클로즈업 — 형상과 운동식을 원본에서 읽었는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_jbr_closeup")
        cls.html = CLOSEUP.read_text(encoding="utf-8")
        cls.plant = cls.builder.plant_text()

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-jbr-closeup.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_jbr_closeup.py 를 돌리고 커밋한다")

    def test_the_window_sits_inside_the_cell_occupancy(self):
        self.assertGreaterEqual(self.builder.T_FROM, 0.0)
        self.assertLessEqual(self.builder.T_TO, campaign.JBR_S)
        self.assertLess(self.builder.T_FROM, self.builder.T_START)
        self.assertLess(self.builder.T_START, self.builder.T_TO)

    def test_the_motion_law_is_read_from_the_plant(self):
        mo = self.builder.motion(self.plant)
        # 전단은 칼날이 닫히는 구간이고, 그 구간에 Z 플로팅과 계면 표시가 겹친다.
        self.assertEqual(mo["shear"], mo["float"][:2])
        self.assertEqual(mo["shear"], mo["interface"])
        self.assertGreater(mo["openWide"], mo["openShut"])
        # 하강이 끝나는 시각이 전단 시작이고, 인양 시작이 전단 끝이다.
        self.assertEqual(mo["descend"][1], mo["shear"][0])
        self.assertEqual(mo["raise"][0], mo["shear"][1])
        # 승강 플레이트가 내려간 자리에서 다시 올라간다 — 두 구간이 같은 높이에서 만난다.
        self.assertEqual(mo["descend"][3], mo["raise"][2])
        # 박스는 승강 플레이트와 같은 구간에 딸려 올라간다.
        self.assertEqual(mo["boxLift"], mo["raise"][:2])
        # 진공 포획은 전단보다 **먼저** 물린다 — 칼날이 닫히기 전에 잡는다는 설계다.
        self.assertLess(mo["grip"][1], mo["shear"][1])
        self.assertLessEqual(mo["grip"][1], mo["shear"][0] + 0.2)

    def test_the_blade_tip_and_wedge_come_from_the_spec_sentence(self):
        spec, tip, wedge = self.builder.blade_spec(self.plant)
        self.assertIn("SKD11", spec)
        self.assertGreater(tip, 0)
        self.assertGreater(wedge, 0)
        self.assertIn(f'"bladeTipMm":{tip:g}', self.html)
        self.assertIn(f'"bladeWedgeDeg":{wedge:g}', self.html)

    def test_the_blades_close_past_the_box_edge(self):
        """두 카세트가 박스 발자국을 지나 가운데서 만나야 접착이 다 끊긴다."""
        m = self.builder.model(self.plant)
        p = m["parts"]
        shut, dx = m["motion"]["openShut"], p["cassette"]["dx"]
        half_cassette = p["cassette"]["size"][0] / 2
        inner = -(shut - dx) + half_cassette          # 좌측 카세트의 안쪽 끝
        self.assertGreater(inner, -p["box"]["size"][0] / 2,
                           "닫힌 자세에서 칼날이 박스 발자국에 못 미친다")
        self.assertLess(inner, 0.0, "좌측 칼날이 중심선을 넘어간다")

    def test_the_geometry_is_read_by_label_not_typed_in(self):
        m = self.builder.model(self.plant)
        for key in ("cassette", "shoe", "carrier", "lip", "gripper", "cup",
                    "compliance", "stem", "nozzle", "toolId", "plate", "panel", "box"):
            with self.subTest(part=key):
                self.assertIn(key, m["parts"])
        self.assertEqual(m["parts"]["panel"]["size"][:2],
                         [campaign.PANEL_LENGTH_MM / 1000, 0.045])

    def test_the_shoe_seats_on_the_backsheet_and_the_blade_cuts_the_spec_gap(self):
        """JB-HD-009 가 「백시트 기준면 접촉」·「절입간격 0.6±0.2 mm」 라고 적는다 — 형상이 그래야 한다."""
        m = self.builder.model(self.plant)
        P, mo = m["parts"], m["motion"]
        base = m["cellY"] + mo["descend"][3]                 # 하강이 끝난 자세
        panel_top = m["cellY"] + P["panel"]["at"][1] + P["panel"]["size"][1] / 2
        shoe_bottom = base + P["shoe"]["y"] - P["shoe"]["size"][1] / 2
        blade_bottom = base + P["cassette"]["y"] - P["cassette"]["size"][1] / 2
        self.assertAlmostEqual(shoe_bottom, panel_top, places=6,
                               msg="기준 슈 밑면이 백시트에 닿지 않는다")
        gap = (shoe_bottom - blade_bottom) * 1000
        self.assertAlmostEqual(gap, m["cutMm"], delta=m["cutTolMm"],
                               msg=f"절입간격 {gap:.2f} mm 가 사양 밖이다")
        self.assertGreater(blade_bottom, panel_top - P["box"]["size"][1],
                           "칼날이 패널을 뚫고 들어간다")

    def test_the_cut_spec_is_read_from_the_bom(self):
        spec, cut, tol = self.builder.shoe_spec(self.plant)
        self.assertIn("절입간격", spec)
        self.assertGreater(cut, 0)
        self.assertGreater(tol, 0)
        self.assertIn(f'"cutMm":{cut:g}', self.html)
        self.assertIn(f'"cutTolMm":{tol:g}', self.html)

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("jbr-closeup", conv.TARGETS)
        body = conv.convert(self.html, CLOSEUP)
        self.assertIn("<title>정션박스 박리·절단·배출</title>", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-closeup.html", readme)
        self.assertIn("tools/build_jbr_closeup.py", readme)

    def test_the_render_check_exists_and_names_the_sheet(self):
        """파이썬 시험은 캔버스가 백지인 것을 못 본다 — 그건 브라우저가 잰다."""
        check = (ROOT / "tools/check_jbr_closeup.mjs").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-closeup.html", check)
        for tab in ("near", "cable", "bin"):
            self.assertIn(f"'{tab}'", check)

    # ── 전선 포획·절단 ─────────────────────────────────────────────────
    def test_the_scissor_law_is_sequential_a_then_b(self):
        """두 도체가 동시에 열리면 안 된다 — A 가 완전히 후퇴한 뒤 B 가 닫힌다."""
        S = self.builder.scissor_motion(self.plant)
        self.assertLess(S["cutA"], S["cutB"])
        self.assertLessEqual(S["cutA"] + S["openTo"], S["cutB"] + 1e-9,
                             "A 가 다 열리기 전에 B 가 닫힌다")
        self.assertLess(S["close"], S["openFrom"])
        # 닫히면 두 조가 서로 지나쳐야 자른다.
        self.assertLess(abs(S["shift"][1]), abs(S["shift"][0]))
        self.assertLess(abs(S["rot"][1]), abs(S["rot"][0]))

    def test_each_scissor_has_a_conductor_at_its_own_plane(self):
        """가위는 자를 것이 있는 z 에 서야 한다 — 어느 쪽에 서느냐는 토폴로지가 정한다.

        3분할형은 좌·우로 한 가닥씩 나가므로 검출열을 사이에 두고 갈라서고,
        1개형은 두 가닥이 같은 쪽으로 나가므로 **둘 다 그쪽**에 선다.
        """
        m = self.builder.model(self.plant)
        for scen in m["scenarios"]:
            with self.subTest(scen=scen["key"]):
                z0 = self.builder.unit_z(m, scen, 0)
                z1 = self.builder.unit_z(m, scen, 1)
                self.assertNotAlmostEqual(z0, z1, places=3, msg="두 가위가 같은 자리다")
                lo, hi = self.builder.lane_z_span(m, scen)
                for z in (z0, z1):
                    self.assertGreaterEqual(z, lo)
                    self.assertLessEqual(z, hi)
                if scen["topology"] == "single-lead":
                    for z in (z0, z1):
                        self.assertLess(z, max(b["z"] for b in scen["boxes"]))
                else:
                    self.assertLess(z0, min(b["z"] for b in scen["boxes"]))
                    self.assertGreater(z1, max(b["z"] for b in scen["boxes"]))

    def test_the_cable_topologies_are_both_read(self):
        cb = self.builder.cable_path(self.plant)
        self.assertGreater(cb["radius"], 0)
        self.assertEqual(len(cb["split"]["left"]["points"]), 3)
        self.assertEqual(len(cb["split"]["right"]["points"]), 3)
        self.assertEqual(len(cb["single"]["lanes"]), 2)
        # 3분할형은 좌·우가 서로 거울이다.
        for a, b in zip(cb["split"]["left"]["points"], cb["split"]["right"]["points"]):
            self.assertAlmostEqual(a[0], -b[0], places=6)
            self.assertAlmostEqual(a[2], -b[2], places=6)
        keys = {s["topology"] for s in self.builder.model(self.plant)["scenarios"]}
        self.assertEqual(keys, {"dual-split", "single-lead"})

    def test_the_harness_goes_to_the_cable_bin_not_a_winder(self):
        """이 셀에 권취 드럼은 없다 — 잘린 하네스는 슈트로 흘러 수거함에 담긴다."""
        m = self.builder.model(self.plant)
        h, b = m["motion"]["harness"], m["bin"]
        self.assertLess(m["motion"]["scissor"]["cutB"], h["from"],
                        "다 자르기 전에 하네스를 끌어낸다")
        self.assertAlmostEqual(h["x"], b["cableAt"][0], delta=0.30)
        self.assertLess(h["z"], b["cableAt"][2] + 0.30)
        # JBR-201 부품표 어디에도 권취 드럼은 없다 — 권취롤러는 상류 GRM-401 것이다.
        names = re.findall(r'\["JB-[A-Z]{2}-\d{3}","[^"]*","([^"]*)"', self.plant)
        self.assertGreater(len(names), 50)
        self.assertEqual([n for n in names if "권취" in n], [])
        self.assertIn("케이블 수거함", names)
        self.assertIn("권취하지 않는다", self.html)

    # ── 브리지 · 수거함 배출 ───────────────────────────────────────────
    def test_the_bridge_law_covers_the_whole_window(self):
        """20–33 s 만 읽으면 케이블 절단 자세도 배출 자세도 나오지 않는다."""
        m = self.builder.model(self.plant)
        mo, br = m["motion"], m["motion"]["bridge"]
        self.assertLessEqual(br["inTo"], mo["descend"][0])
        self.assertEqual(br["outFrom"], mo["raise"][1])
        self.assertLessEqual(br["parkTo"], br["restAt"])
        # 창의 어느 시각에서도 값이 나온다.
        for t in (self.builder.T_FROM, 18.0, 24.0, 34.0, self.builder.T_TO - 0.01):
            with self.subTest(t=t):
                self.assertIsInstance(self.builder.plate_y(t, mo), float)
        # 케이블 절단 자세는 칼날 하강 자세보다 얕다 — 같은 축을 두 번 쓴다.
        self.assertGreater(br["dropY"][1], mo["descend"][3])

    def test_the_discharge_drops_into_the_wide_bin(self):
        m = self.builder.model(self.plant)
        D, B = m["motion"]["discharge"], m["bin"]
        self.assertAlmostEqual(D["binX"], B["at"][0], places=6)
        self.assertEqual(D["highY"], m["motion"]["boxTop"])
        self.assertLess(D["restY"], D["highY"])
        # 슈트 통과 확인이 먼저, 수거함 중량 확인이 나중이다.
        self.assertLess(D["chuteLight"][0], D["binWeigh"])
        self.assertLess(D["binWeigh"], D["chuteLight"][1])
        # 광폭 수거함은 검출 3 개가 폭 방향으로 나란히 들어갈 만큼 넓다.
        width = B["base"]["size"][2] * B["widthScale"]
        for scen in m["scenarios"]:
            zs = [b["z"] for b in scen["boxes"]]
            self.assertLess(max(zs) - min(zs) + m["parts"]["box"]["size"][2], width)

    # ── 원본 자체 검산 ─────────────────────────────────────────────────
    def test_the_checks_table_is_computed_not_typed(self):
        m = self.builder.model(self.plant)
        rows = self.builder.checks(m)
        self.assertGreaterEqual(len(rows), 5)
        for c in rows:
            with self.subTest(item=c["item"]):
                for key in ("item", "found", "spec", "ok", "why", "fix"):
                    self.assertIn(key, c)
                self.assertIn(c["item"], self.html)
                self.assertIn(c["found"], self.html)

    def test_the_chute_tilt_matches_its_bom_tolerance(self):
        """맞는 것도 같은 방법으로 재야 표가 검산으로 읽힌다."""
        m = self.builder.model(self.plant)
        tilt = abs(m["bin"]["chute"]["tilt"]) * 180 / math.pi
        self.assertAlmostEqual(tilt, m["chuteDeg"], delta=m["chuteTolDeg"])

    def test_every_check_passes(self):
        """REV.54 에서 넷을 다 고쳤다. 다시 어긋나면 여기서 먼저 걸린다."""
        m = self.builder.model(self.plant)
        bad = [f"{c['item']}: {c['found']} vs {c['spec']}"
               for c in self.builder.checks(m) if not c["ok"]]
        self.assertEqual(bad, [])
        self.assertIn(f"{len(self.builder.checks(m))} 항목 전부 일치", self.html)

    # ── REV.54 에서 고친 넷 — 값이 되돌아가면 여기서 걸린다 ──────────────
    def test_both_cuts_happen_at_the_lowered_pose(self):
        """가위 A 가 하강 전에 닫히던 것을 고쳤다 (플레이트 +150 → 절단 자세 −120)."""
        m = self.builder.model(self.plant)
        mo, S, br = m["motion"], m["motion"]["scissor"], m["motion"]["bridge"]
        for n in (S["cutA"], S["cutB"]):
            for t in (n, n + S["close"]):
                with self.subTest(t=t):
                    self.assertAlmostEqual(self.builder.plate_y(t, mo), br["dropY"][1],
                                           places=6, msg="절단 순간에 가위가 케이블 높이에 없다")
        # 하강 자세를 유지하는 창 안에 두 절단이 다 들어간다.
        self.assertGreaterEqual(S["cutA"], br["dropIn"][1])
        self.assertLessEqual(S["cutB"] + S["close"], br["dropOut"][0])
        # 하강을 앞당기는 쪽은 못 쓴다 — 그 자세의 조 하단이 패널 상면보다 아래다.
        P = m["parts"]
        jaw_bottom = (m["cellY"] + br["dropY"][1] + P["jaw"]["at"][1]
                      - P["jaw"]["size"][1] / 2)
        panel_top = m["cellY"] + P["panel"]["at"][1] + P["panel"]["size"][1] / 2
        self.assertLess(jaw_bottom, panel_top)

    def test_the_harness_is_pulled_only_after_both_cuts(self):
        m = self.builder.model(self.plant)
        S, h, D = m["motion"]["scissor"], m["motion"]["harness"], m["motion"]["discharge"]
        self.assertGreaterEqual(h["from"], S["cutB"] + S["close"])
        self.assertEqual(D["cableLight"][0], h["from"])
        self.assertEqual(D["cableLight"][1], h["to"])

    def test_the_closed_jaws_overlap_by_the_bom_amount(self):
        m = self.builder.model(self.plant)
        S, w = m["motion"]["scissor"], m["parts"]["jaw"]["size"][0] / 2
        over = (w * math.cos(S["rot"][1]) - abs(S["shift"][1])) * 2000
        self.assertAlmostEqual(over, m["jawMm"], delta=m["jawTolMm"])
        self.assertGreater(over, 0, "닫혀도 두 날이 지나치지 않으면 잘리지 않는다")

    def test_the_box_settles_flat_on_the_bin_floor(self):
        m = self.builder.model(self.plant)
        D, B, box = m["motion"]["discharge"], m["bin"], m["parts"]["box"]["size"]
        floor = B["base"]["at"][1] + B["base"]["size"][1] / 2
        self.assertAlmostEqual(D["restY"] - box[1] / 2, floor, places=6)
        # 전복·부채는 낙하 중에만 실린다 — de(1−de)·k 는 양끝에서 0 이다.
        self.assertGreater(D["tumbleGain"], 0)
        for u in (0.0, 1.0):
            self.assertAlmostEqual(u * (1 - u) * D["tumbleGain"], 0.0, places=9)
        self.assertAlmostEqual(0.5 * 0.5 * D["tumbleGain"], 1.0, places=9)

    def test_the_revision_moved_with_the_change(self):
        """형상·운동이 바뀌면 도면 리비전도 같이 움직인다."""
        rev = self.builder.revision(self.plant)
        self.assertRegex(rev, r"^REV\.\d+$")
        self.assertGreaterEqual(int(rev.split(".")[1]), 54)
        self.assertEqual(self.plant.count("REV.54:"), 2)

    def test_the_bom_tolerances_are_quoted_verbatim(self):
        m = self.builder.model(self.plant)
        for tag, name, key in (("JB-CB-003", "교체형 케이블 가위날", "jawSpec"),
                               ("JB-WH-001", "정션박스 일괄 낙하슈트", "chuteSpec"),
                               ("JB-CB-001", "비전 연동 케이블 포획콤", "combSpec")):
            with self.subTest(tag=tag):
                self.assertEqual(m[key], self.builder.bom_tolerance(self.plant, tag, name))
                self.assertIn(m[key], self.html)


class TestJbrHub(unittest.TestCase):
    """도면 모음 — 세 벌을 **합치지 않고** 한 장에 담았는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_jbr_hub")
        cls.html = HUB.read_text(encoding="utf-8")
        # base64 로 실린 도면 본문을 걷어 낸 「액자만」의 마크업.
        cls.frame = re.sub(r'<script type="text/plain" id="doc-[a-z]+">[^<]*</script>',
                           "", cls.html)

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-jbr-hub.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_jbr_hub.py 를 돌리고 커밋한다")

    def test_each_sheet_is_carried_once_and_byte_exact(self):
        """담은 것이 그 도면 파일 그대로여야 한다 — 한 벌씩, 바이트 하나까지."""
        import base64
        for key, rel, _role, _span in self.builder.SHEETS:
            with self.subTest(sheet=key):
                marker = f'<script type="text/plain" id="doc-{key}">'
                self.assertEqual(self.html.count(marker), 1, "같은 도면이 두 번 실렸다")
                b64 = re.search(re.escape(marker) + r"([^<]*)</script>", self.html).group(1)
                self.assertEqual(base64.b64decode(b64), (ROOT / rel).read_bytes())

    def test_the_frame_does_not_paste_sheet_markup(self):
        """도면을 풀어서 붙이면 서식이 섞이고 같은 표가 두 번 나온다."""
        for tag in ("<table", "<canvas", "<svg", "<h2"):
            with self.subTest(tag=tag):
                self.assertNotIn(tag, self.frame)

    def test_the_tab_labels_come_from_the_sheets_themselves(self):
        for key, rel, _role, _span in self.builder.SHEETS:
            title, desc = self.builder.sheet_meta(ROOT / rel)
            with self.subTest(sheet=key):
                self.assertIn(title, self.frame)
                self.assertIn(desc, self.frame)

    def test_the_clock_band_comes_from_the_campaign_model(self):
        infeed, jbr, afr = campaign.INFEED_S, campaign.JBR_S, campaign.AFR_S
        n = self.builder.num
        self.assertIn(f'style="flex:{infeed:g}"', self.frame)
        self.assertIn(f'style="flex:{jbr:g}"', self.frame)
        self.assertIn(f'style="flex:{afr:g}"', self.frame)
        # 머리글이 사용자가 부른 그 창을 그대로 적는다.
        self.assertIn(f"JB-201 인계 <b>{n(infeed)} s</b>", self.frame)
        self.assertIn(f"AFR-101 인계\n    <b>{n(infeed + jbr)} s</b>", self.frame)
        self.assertIn(f"종단 체류 <b>{n(infeed + jbr + afr)} s</b>", self.frame)

    def test_the_closeup_span_is_read_from_its_builder(self):
        closeup = _load("build_jbr_closeup")
        lo, hi = self.builder.closeup_window()
        self.assertEqual(lo, closeup.T_FROM + campaign.INFEED_S)
        self.assertEqual(hi, closeup.T_TO + campaign.INFEED_S)
        self.assertIn(f'"from":{lo},"to":{hi}', self.html)

    def test_a_sheet_without_its_own_description_fails_the_build(self):
        """탭 설명을 손으로 쓰지 않으려면 도면이 스스로 적어야 한다."""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8",
                                         delete=False) as fh:
            fh.write("<html><head><title>이름만 있다</title></head><body></body></html>")
            bare = pathlib.Path(fh.name)
        try:
            with self.assertRaises(SystemExit):
                self.builder.sheet_meta(bare)
        finally:
            bare.unlink()

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("jbr-hub", conv.TARGETS)
        body = conv.convert(self.html, HUB)
        self.assertIn("<title>JBR-201 정션박스·케이블 제거장치</title>", body)
        # 담은 도면은 base64 라 변환기의 골격 벗기기에 닿지 않는다.
        for key, rel, _role, _span in self.builder.SHEETS:
            self.assertIn(f'id="doc-{key}"', body)

    def test_the_readme_and_render_check_list_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-hub.html", readme)
        self.assertIn("tools/build_jbr_hub.py", readme)
        check = (ROOT / "tools/check_jbr_hub.mjs").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-hub.html", check)
        for key, _rel, _role, _span in self.builder.SHEETS:
            self.assertIn(f"{key}:", check)


class TestPlantConsoleDefects(unittest.TestCase):
    """파생본을 만들며 드러난 통합 설계도 자체의 결함 두 개 — 회귀 방지."""

    @classmethod
    def setUpClass(cls):
        cls.plant = (ROOT / "docs/drawings/pv-preprocess-plant.html").read_text(encoding="utf-8")

    def test_a_single_zone_focus_does_not_crash(self):
        """LAYOUT_FOCUS.jbr 은 존이 하나다 — pair[1] 을 읽으면 zoneByKey 가 null 을 준다."""
        self.assertIn("var from = zoneByKey(pair[0]), to = zoneByKey(pair[pair.length - 1]);", self.plant)
        focus = re.search(r"var LAYOUT_FOCUS = \{(.*?)\};", self.plant).group(1)
        self.assertIn("jbr: ['jbr']", focus)

    def test_drawing_the_campaign_chart_does_not_stop_the_video(self):
        """표를 그리는 것만으로 3D 공정시계가 멈추고 0 s 로 되감기면 안 된다."""
        self.assertIn("setCampaignIndex(camState.index, false);", self.plant)
        self.assertIn("if (commit !== false) host.__pvInfeedTest.setCampaignIndex(n);", self.plant)


if __name__ == "__main__":
    unittest.main()
