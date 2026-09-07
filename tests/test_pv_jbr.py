"""JBR-201 정션박스 제거장치 파생본 — 생성기 출력과 커밋된 파일, 그리고 모델과의 일치.

파생본은 손으로 쓰지 않는다. `tools/build_jbr_scene.py` 가 통합 설계도에서 JBR 셀만
남겨 찍어 내고, 여기서는 (1) 커밋된 파일이 그 출력과 같은지, (2) 시계 창이 캠페인
모델에서 온 값인지, (3) 원본 3D 형상 코드가 그대로인지(파생본은 보이기만 끈다),
(4) 아티팩트 변환기가 받아들이는 문서인지를 본다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, layout, servos

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENE = ROOT / "docs/drawings/pv-jbr-scene.html"
DETAIL = ROOT / "docs/drawings/pv-jbr-detail.html"
CLOSEUP = ROOT / "docs/drawings/pv-jbr-closeup.html"


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

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("jbr-closeup", conv.TARGETS)
        body = conv.convert(self.html, CLOSEUP)
        self.assertIn("<title>정션박스 박리 순간</title>", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-jbr-closeup.html", readme)
        self.assertIn("tools/build_jbr_closeup.py", readme)


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
