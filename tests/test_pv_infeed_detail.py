"""투입 구간 상세도 — 생성기 출력과 커밋된 파일, 그리고 모델과의 일치.

상세도는 손으로 쓰지 않는다. `tools/build_infeed_detail.py` 가 모델과 통합
설계도에서 값을 읽어 찍어 내고, 여기서는 (1) 커밋된 파일이 그 출력과 같은지,
(2) 범위 안 품번·레벨·시각이 모델과 어긋나지 않았는지, (3) 아티팩트 변환기가
받아들이는 문서인지를 본다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, kinematics, layout, safety, servos

ROOT = pathlib.Path(__file__).resolve().parents[1]
DETAIL = ROOT / "docs/drawings/pv-infeed-detail.html"
SIM = ROOT / "docs/drawings/pv-infeed-sim.html"
SCENE = ROOT / "docs/drawings/pv-infeed-scene.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestInfeedDetail(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_infeed_detail")
        cls.html = DETAIL.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-infeed-detail.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_infeed_detail.py 를 돌리고 커밋한다")

    def test_the_scope_is_the_first_two_zones(self):
        keys = [z.key for z in layout.build_zones()]
        self.assertEqual(tuple(keys[:2]), self.builder.SCOPE_ZONES)
        afu, robot = layout.STATIONS["afu"], layout.STATIONS["robot"]
        self.assertIn(f"afu {afu.length_mm:,} + robot {robot.length_mm:,} = {afu.length_mm + robot.length_mm:,} mm", self.html)

    def test_every_scope_part_number_is_in_the_plant_catalog_and_the_sheet(self):
        plant = self.builder.plant_text()
        for tag in self.builder.SCOPE_PART_NUMBERS:
            with self.subTest(tag=tag):
                self.assertIn(f'["{tag}"', plant, "통합 설계도 부품표에 없는 품번이다")
                self.assertIn(f"<code>{tag}</code>", self.html)

    def test_levels_come_from_the_model(self):
        for level in (kinematics.PICK_FACE_MM, kinematics.HANDOVER_MM, kinematics.dwell_mm(),
                      kinematics.FLIP_AXIS_MM, round(kinematics.ring_bottom_mm()), layout.LINE_TRANSFER_MM):
            with self.subTest(level=level):
                self.assertIn(f"{level:,}", self.html)
        self.assertIn(f"{kinematics.ring_over_forklift_mm():,.0f}", self.html)

    def test_the_clock_is_continuous_from_pallet_to_jbr(self):
        """준비 → PATH → 로봇 → JBR 진입이 빈틈·겹침 없이 이어져야 한다."""
        b = self.builder
        spans = ([(t0, t1) for t0, t1, _ in b.PREP_CLOCK]
                 + [(t0, t1) for t0, t1, *_ in kinematics.PATH]
                 + [(t0, t1) for t0, t1, _ in b.ROBOT_CLOCK])
        for a, c in zip(spans, spans[1:]):
            self.assertEqual(a[1], c[0], f"{a} 와 {c} 사이가 안 이어진다")
        self.assertEqual(spans[0][0], 0.0)
        self.assertEqual(spans[-1][1], campaign.INFEED_S)

    def test_the_reach_chain_closes_on_the_zone_table(self):
        self.assertEqual(layout.afu_length_from_reach_mm(), layout.STATIONS["afu"].length_mm)
        self.assertTrue(layout.robot_can_reach())
        self.assertIn(f"{layout.ROBOT_REACH_MM:,}", self.html)

    def test_scope_drives_and_hazards_are_listed(self):
        for a in servos.SERVO_AXES + servos.MOTORS:
            if a.panel in self.builder.SCOPE_PANELS:
                self.assertIn(f"<code>{a.tag}</code>", self.html)
        for h in safety.HAZARDS:
            if h.cell in self.builder.SCOPE_HAZARD_CELLS:
                self.assertIn(f"<code>{h.tag}</code>", self.html)
                self.assertIn(f"PL{h.plr}", self.html)

    def test_the_artifact_converter_accepts_it(self):
        """외부에서 받아 오는 자리가 없고 골격 태그가 벗겨지는 문서여야 발행할 수 있다."""
        conv = _load("build_artifact")
        self.assertIn("infeed", conv.TARGETS)
        body = conv.convert(self.html, DETAIL)
        self.assertIn("<title>", body)
        self.assertNotIn("<!DOCTYPE", body)

    def test_the_readme_lists_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-infeed-detail.html", readme)


class TestInfeedSim(unittest.TestCase):
    """투입 구간 운전 콘솔 — 리터럴이 모델에서 왔고 커밋본이 생성기 출력과 같은가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_infeed_sim")
        cls.html = SIM.read_text(encoding="utf-8")
        cls.model = cls.builder.model()

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-infeed-sim.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_infeed_sim.py 를 돌리고 커밋한다")

    def test_the_model_literal_carries_the_design_values(self):
        m = self.model
        self.assertEqual(m["levels"]["axis"], kinematics.FLIP_AXIS_MM)
        self.assertEqual(m["levels"]["dwell"], kinematics.dwell_mm())
        self.assertEqual(m["pick"]["x"], layout.bfc_pickup_x_mm())
        self.assertEqual(m["pt"]["x"], layout.pt_place_x_mm())
        self.assertEqual(m["clock"]["takt"], campaign.release_takt_s())
        self.assertEqual([r[:3] for r in m["clock"]["path"]], [list(p[:3]) for p in kinematics.PATH])
        self.assertEqual(len(m["roster"]), campaign.summary()["panels"])
        # 로봇 도달 사슬은 리터럴에서도 닫혀야 한다
        self.assertEqual(m["robot"]["l1"] + m["robot"]["l2"], m["robot"]["reach"])
        self.assertLess(m["robot"]["pickDist"], m["robot"]["reach"])

    def test_permits_come_from_the_plant_interface_table(self):
        for key, first in (("flip", "single_sheet"), ("robot", "cassette_at_H2100"),
                           ("index", "source_panel_clear"), ("handshake", "PANEL_OFFER")):
            with self.subTest(key=key):
                self.assertEqual(self.model["permits"][key][0], first)
        self.assertEqual(self.model["permits"]["handshake"][-1], "TRANSFER_COMPLETE")

    def test_the_clock_is_continuous(self):
        b = self.builder
        spans = ([(a, c) for a, c, _ in b.PREP_CLOCK] + [(p[0], p[1]) for p in kinematics.PATH]
                 + [(a, c) for a, c, _ in b.ROBOT_CLOCK])
        for x, y in zip(spans, spans[1:]):
            self.assertEqual(x[1], y[0])
        self.assertEqual(spans[-1][1], campaign.INFEED_S)
        rej = [(a, c) for a, c, _ in b.REJECT_CLOCK]
        for x, y in zip(rej, rej[1:]):
            self.assertEqual(x[1], y[0])
        self.assertEqual(rej[-1][1], campaign.INFEED_REJECT_S)

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("infeed-sim", conv.TARGETS)
        body = conv.convert(self.html, SIM)
        self.assertIn("<title>", body)


class TestInfeedScene(unittest.TestCase):
    """통합 설계도에서 투입 구간만 남긴 파생본 — 원본 형상은 그대로, 시계·시점·화면만 좁혔는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_infeed_scene")
        cls.html = SCENE.read_text(encoding="utf-8")
        cls.plant = cls.builder.PLANT.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-infeed-scene.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_infeed_scene.py 를 돌리고 커밋한다")

    def test_the_clock_is_the_release_takt(self):
        takt = campaign.release_takt_s()
        self.assertIn(f",ci={takt:g}", self.html)
        self.assertNotIn(",ci=nt+Lr", self.html)
        self.assertIn(f'max="{takt:g}"', self.html)
        self.assertNotIn('max="124.03"', self.html)

    def test_only_infeed_views_and_stations_remain(self):
        import re
        views = re.findall(r'data-jb-view="([a-z]+)" type="button"', self.html)
        self.assertEqual(sorted(views), sorted(self.builder.KEEP_VIEWS))
        self.assertIn('class="btn btn-primary" data-jb-view="afu"', self.html)
        for key in ("jbr", "afr", "post", "buffer"):
            self.assertNotIn(f'<option value="{key}">', self.html.split('id="pv-drawing-station"')[1][:600])
        self.assertIn(',xl="afu"', self.html)

    def test_the_scene_is_narrowed_not_rewritten(self):
        """3D 형상 코드는 원본과 같아야 한다 — 파생본은 보이기만 끈다."""
        i = self.plant.index("var pvZone=")
        j = self.plant.index("Ae.__pvScene=")
        patched = (",ci=nt+Lr", ',xl="line"', 'fp.line:fp[i]', '"reset"?"line"')
        for line in self.plant[i:j].splitlines():
            if any(anchor in line for anchor in patched):
                continue
            self.assertIn(line, self.html, f"원본 장면 코드가 파생본에서 바뀌었다: {line[:80]}")
        self.assertIn("window.__pvInfeedScene", self.html)
        robot_end = next(z.x1_mm for z in layout.build_zones() if z.key == "robot")
        self.assertIn(f"const BOUNDARY = {(robot_end - 24_750) / 1000 + 0.5:g};", self.html)

    def test_downstream_controls_are_hidden_and_the_handoff_is_named(self):
        for key in self.builder.DOWNSTREAM_CONTROLS:
            self.assertIn(f'label[for="{key}"]', self.html)
        self.assertIn('id="afr-buffer-reset" type="button" hidden', self.html)
        self.assertIn('<label class="form-label" for="pv-panel-structure">', self.html, "구조 레시피는 투입 쪽 조작이라 남아야 한다")
        self.assertNotIn("JBR 자가점검", self.html)
        self.assertIn("JB-201 → JBR-201 인계", self.html)
        self.assertNotIn("ENGINEERING BASE REV.22", self.html)
        self.assertNotIn("Rev.22 · 비전 2헤드", self.html)

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("infeed-scene", conv.TARGETS)
        body = conv.convert(self.html, SCENE)
        self.assertIn("<title>태양광 전처리 플랜트 · 투입 구간</title>", body)
