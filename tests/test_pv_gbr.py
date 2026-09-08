"""GBR-301 레시피 버퍼 파생본 — 생성기 출력과 커밋된 파일, 그리고 모델과의 일치.

파생본은 손으로 쓰지 않는다. `tools/build_gbr_scene.py` 가 통합 설계도에서 buffer
셀만 남겨 찍어 내고, 여기서는 (1) 커밋된 파일이 그 출력과 같은지, (2) 시계 창이
원본 필름의 시각표에서 온 값인지, (3) 원본 3D 형상 코드가 그대로인지(파생본은
보이기만 끈다), (4) 발주 요청 셋 — 그림자·외장 케이싱·천장크레인 — 이 실제로
빠졌는지, (5) 아티팩트 변환기가 받아들이는 문서인지를 본다.

기구가 **실제로 움직이는지**는 글자로 볼 수 없다. 그것은
`node tools/check_gbr_scene.mjs` 가 브라우저로 잰다 — 유리가 GI 에서 데크로 건너와
목표 행으로 횡분기하고 슬롯에 들어가는지, 레시피를 바꾸면 다른 행에 들어가는지.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, layout

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENE = ROOT / "docs/drawings/pv-gbr-scene.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGbrScene(unittest.TestCase):
    """통합 설계도에서 GBR-301 레시피 버퍼만 남긴 파생본."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_gbr_scene")
        cls.html = SCENE.read_text(encoding="utf-8")
        cls.plant = cls.builder.PLANT.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-gbr-scene.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_gbr_scene.py 를 돌리고 커밋한다")

    # ── 시계 ────────────────────────────────────────────────────────────
    def test_the_clock_window_is_read_from_the_film(self):
        """창의 두 끝은 **원본에서 읽는다** — 여기 128.8 이라고 적어 두지 않는다.

        시작은 후단 마지막 칸(`Cr`…`Cr+span`)의 진도 `HANDOVER_V` 이고, 끝은
        필름의 끝(`ci`)이다. 후단 시각표가 바뀌면 창도 같이 움직여야 한다.
        """
        start, span = self.builder.film(self.plant)
        self.assertEqual(start, campaign.INFEED_S + campaign.JBR_S
                         + float(re.search(r"Cr=([0-9.]+),pl=Wr", self.plant).group(1)))
        t0, t1 = self.builder.window(self.plant)
        self.assertEqual(t0, round(start + self.builder.HANDOVER_V * span, 2))
        self.assertEqual(t1, campaign.total_dwell_s())
        self.assertIn(f",Ve={t0:g},ai=0", self.html)
        self.assertIn(f'min="{t0:g}" max="{t1:g}"', self.html)
        self.assertIn(f'id="jb-time">{t0:.2f} / {t1:.2f} s</div>', self.html)

    def test_the_window_is_this_cells_own_work(self):
        """창은 이 셀이 유리를 쥐고 있는 동안이다 — 앞은 후단 검사, 뒤는 없다."""
        t0, t1 = self.builder.window(self.plant)
        _, span = self.builder.film(self.plant)
        self.assertIn(",ci=nt+Lr", self.html)
        self.assertGreater(t1, t0)
        # 후단 마지막 칸의 12 % — 원본 필름이 적재에 준 몫이다. 창의 시작을 두 자리로
        # 반올림해 화면에 적으므로 그 반올림(±0.005 s)만큼은 벌어질 수 있다.
        self.assertAlmostEqual(t1 - t0, (1 - self.builder.HANDOVER_V) * span, delta=0.01)

    def test_every_rewind_lands_inside_the_window(self):
        """조작을 바꿔도 시계가 창 밖(0 s)으로 되감기면 안 된다."""
        t0, _ = self.builder.window(self.plant)
        # 원본의 `Ve=0` 은 선언 1 + 되감기 6 이다. 생성기는 선언을 먼저 바꾸고 남은 6 을 센다.
        self.assertEqual(len(re.findall(r"\bVe=0\b", self.plant)), 7, "원본의 되감기 수가 바뀌었다")
        self.assertNotIn("Ve=0", self.html)
        # 파생본의 `Ve=128.8` 은 선언 1 + 반복 되돌림 1 + 되감기 6 이다.
        self.assertEqual(len(re.findall(rf"\bVe={t0:g}\b", self.html)), 8)
        self.assertIn(f"Ve={t0:g}+(Ve-{t0:g})%(ci-{t0:g})", self.html)
        self.assertIn(f"let pe=Math.round((i-{t0:g})/(ci-{t0:g})*100)", self.html)

    def test_the_short_window_opens_slowly(self):
        """창이 1.23 s 라 원본 기본 배속(0.5×)으로는 한 번에 지나간다."""
        t0, t1 = self.builder.window(self.plant)
        self.assertLess(t1 - t0, 2.0, "창이 길어졌다면 배속을 되돌릴 것")
        self.assertIn("b0=.25,", self.html)
        self.assertIn("b0=.5,", self.plant)
        self.assertIn('<option value="0.25" selected>0.25×</option>', self.html)
        self.assertNotIn('<option value="0.5" selected>', self.html)
        # 눈금도 잘게 썬다 — 0.05 면 창 전체가 24 칸이라 한 칸이 5 % 다.
        self.assertIn('step="0.01"', self.html)

    def test_the_stage_name_is_what_the_window_actually_shows(self):
        """원본 칸 이름은 안 보이는 설비(SG·GI)를 앞세운다 — 이 창의 일로 바꾼다."""
        was = "정반 상승·톱니 컨베이어 40 mm 상승 반출→SG-301→GI-301/302→GBR-301"
        self.assertIn(was, self.plant)
        self.assertNotIn(was, self.html)
        self.assertIn("GBR-301 데크 인계 → Z 분기 → 콤포크 승강·슬롯 적재", self.html)
        # 접두어는 그 칸에서만 뗀다 — 나머지 다섯 칸은 AFR 것이라 그대로 둔다.
        self.assertIn("name:`AFR-101 · ${i.name}`", self.plant)
        self.assertIn('name:i.name.indexOf("GBR-301")===0?i.name:'
                      "`AFR-101 · ${i.name}`", self.html)
        self.assertIn('(u.phase.name.indexOf("GBR-301")===0?u.phase.name:'
                      "`AFR-101 · ${u.phase.name}`)", self.html)

    # ── 시점·도면 ───────────────────────────────────────────────────────
    def test_only_gbr_views_and_the_gbr_sheet_remain(self):
        views = re.findall(r'data-jb-view="([a-z]+)" type="button"', self.html)
        self.assertEqual(sorted(views), sorted(self.builder.KEEP_VIEWS))
        for view in self.builder.AUTO_VIEWS:
            self.assertIn(view, self.builder.KEEP_VIEWS, "자동추적이 고르는 시점이 버튼에 없다")
        sheets = self.html.split('id="pv-drawing-station"')[1][:900]
        for key in self.builder.DROP_STATIONS:
            self.assertNotIn(f'<option value="{key}"', sheets)
        self.assertIn('<option value="buffer" selected>', sheets)
        self.assertIn(',xl="gbr"', self.html)

    def test_the_auto_camera_never_points_at_a_cell_that_is_off(self):
        self.assertIn(f"se={self.builder.AUTO_VIEWS_OLD}", self.plant)
        self.assertIn(f"se={self.builder.AUTO_VIEWS_NEW}", self.html)
        self.assertNotIn("afrpost", self.html.split("se=[")[1][:200])

    def test_the_views_are_derived_from_the_zone_table(self):
        """시점이 겨누는 자리는 배치 모델에서 온다 — 존이 움직이면 시점도 움직인다."""
        want, got = self.builder.view_anchors(), self.builder.view_targets()
        self.assertEqual(sorted(got), sorted(self.builder.KEEP_VIEWS[:3]))
        for key in want:
            with self.subTest(view=key):
                self.assertLessEqual(abs(got[key] - want[key]), self.builder.VIEW_TOLERANCE_M)
        self.builder.check_views()   # 벌어지면 SystemExit
        self.assertIn(self.builder.VIEWS_NEW.rstrip("top:").rstrip(","), self.html)
        self.assertIn(self.builder.VIEWS_OLD, self.plant, "원본은 그대로다")
        self.assertNotIn("afrbuffer", self.html)

    # ── 장면 ────────────────────────────────────────────────────────────
    def test_the_scene_is_narrowed_not_rewritten(self):
        """3D 형상 코드는 원본과 같아야 한다 — 파생본은 보이기만 끈다."""
        i = self.plant.index("var pvZone=")
        j = self.plant.index("Ae.__pvScene=")
        patched = (',xl="line"', "fp.line:fp[i]", '"reset"?"line"', "afrbuffer:{position",
                   'se=["afr","afr"', "b0=.5,", ",Ve=0,ai=0")
        for line in self.plant[i:j].splitlines():
            if any(anchor in line for anchor in patched):
                continue
            self.assertIn(line, self.html, f"원본 장면 코드가 파생본에서 바뀌었다: {line[:80]}")
        self.assertIn("window.__pvGbrScene", self.html)

    def test_the_scene_boundary_is_the_zone_table(self):
        low, high = self.builder.zone_world_x()
        zone = next(z for z in layout.build_zones() if z.key == "buffer")
        self.assertEqual(low, (zone.x0_mm - self.builder.SCENE_ORIGIN_X_MM) / 1000)
        self.assertEqual(high, (zone.x1_mm - self.builder.SCENE_ORIGIN_X_MM) / 1000)
        self.assertIn(f"const LOW = {low:g};", self.html)
        self.assertIn(f"const HIGH = {high:g};", self.html)

    def test_the_workpiece_and_the_fixtures_have_different_thresholds(self):
        """물건은 상류에서 들어오고, 설비는 존 밖이면 남의 것이다.

        한 값으로 묶으면 후단 셀의 EC-POS 엣지 캐비닛이 이 화면에 남는다 —
        실제로 그렇게 남아 있던 것을 문턱을 갈라 뺐다.
        """
        # 유리는 GI 검사대(존 시작에서 상류로 1.675)에서 출발한다.
        self.assertGreater(self.builder.UPSTREAM_MARGIN_M, 1.675)
        self.assertLess(self.builder.FIXTURE_MARGIN_M, 1.675)
        self.assertIn(f"const IN = LOW - {self.builder.UPSTREAM_MARGIN_M:g}", self.html)
        self.assertIn(f"const FIT_IN = LOW - {self.builder.FIXTURE_MARGIN_M:g}", self.html)
        self.assertIn("(v.x < FIT_IN || v.x > FIT_OUT)", self.html)
        self.assertIn("if (v.x < IN || v.x > OUT) tr.visible = false;", self.html)

    def test_the_cells_that_stay_off(self):
        self.assertEqual(sorted(self.builder.OFF_CELLS),
                         sorted(k for k in ("afu", "robot", "jbr", "afr", "post", "grm")))
        self.assertNotIn("buffer", self.builder.OFF_CELLS)
        self.assertIn("if (cell === 'buffer') return;", self.html)

    # ── 발주 요청 셋 ────────────────────────────────────────────────────
    def test_the_3d_casts_no_floor_shadow(self):
        """셀 하나를 보는 화면에서 바닥 그림자는 캐리지 밑을 덮기만 한다."""
        self.assertIn("shadowMap.enabled=!1;", self.html)
        self.assertNotIn("shadowMap.enabled=!0;", self.html)
        self.assertIn("shadowMap.enabled=!0;", self.plant)   # 원본은 그대로다

    def test_the_casing_is_off_by_default_and_by_group(self):
        """껍질은 셔틀과 적재기를 가린다 — 토글 기본값도 끄고 묶음째 끈다."""
        self.assertIn('<input class="form-check-input" id="pv-case" type="checkbox" checked>',
                      self.plant, "원본은 켜 둔 채로 나간다")
        self.assertIn('<input class="form-check-input" id="pv-case" type="checkbox">', self.html)
        self.assertNotIn('id="pv-case" type="checkbox" checked', self.html)
        self.assertIn("['pvCase', 'pvCrn']", self.html)

    def test_the_overhead_crane_is_named_so_it_can_be_switched_off(self):
        """CRN-901 은 셀에 매이지 않는 `pvSpans` 묶음이라 이름이 있어야 통째로 끈다."""
        self.assertIn("var pvCrn=new ce;pt.add(pvSpans(pvCrn));", self.plant)
        self.assertIn("var pvCrn=new ce;pvCrn.name='pvCrn';pt.add(pvSpans(pvCrn));", self.html)
        self.assertIn("for (const s of shells) s.visible = false;", self.html)

    # ── 화면 ────────────────────────────────────────────────────────────
    def test_the_flow_strip_shows_only_this_cell(self):
        first, last = self.builder.FLOW_FIRST, self.builder.FLOW_LAST
        self.assertEqual((first, last), (11, 11))
        self.assertIn(f".pv-flow-track > li:nth-child(-n+{first - 1})", self.html)
        self.assertIn(f".pv-flow-track > li:nth-child(n+{last + 1})", self.html)
        steps = re.findall(r'<li data-flow-step="(\d+)"', self.html)
        self.assertEqual(len(steps), 11, "흐름표 칸은 지우지 않고 CSS 로만 가린다")
        # 가려지지 않는 칸이 GBR-301 이어야 한다.
        self.assertIn('data-flow-step="10" aria-label="GBR-301', self.html)

    def test_upstream_controls_are_hidden_and_the_cell_keeps_its_own(self):
        for key in self.builder.HIDDEN_CONTROLS:
            self.assertIn(f'label[for="{key}"]', self.html)
        # 이 셀의 조작 둘은 남고, 이름도 이 셀 것으로 바뀐다.
        self.assertNotIn('label[for="afr-route-mode"]', self.html)
        self.assertIn('<button class="btn" id="afr-buffer-reset" type="button">', self.html)
        self.assertIn("GBR 레시피 시나리오 (목표 캐리지)", self.html)
        self.assertIn("AFR 가상 레시피 시나리오", self.plant)
        self.assertNotIn("AFR 가상 레시피 시나리오", self.html)
        self.assertNotIn("ENGINEERING BASE REV.22", self.html)
        self.assertIn("GBR-301 단독 파생본", self.html)

    def test_the_cell_envelope_agrees_between_model_and_ga_sheet(self):
        """가로·세로·높이는 배치 모델과 GA 시트 두 곳에 있다 — 갈라지면 멈춘다."""
        L, W, H = self.builder.cell_envelope(self.plant)
        z = next(x for x in layout.build_zones() if x.key == "buffer")
        self.assertEqual((L, W, H), (z.x1_mm - z.x0_mm, z.y1_mm - z.y0_mm, z.height_mm))
        with self.assertRaises(SystemExit):
            self.builder.cell_envelope(
                self.plant.replace("envelope: [9550, 7100, 2800]",
                                   "envelope: [9550, 7100, 2801]"))

    def test_the_layout_draws_this_cell_only(self):
        """원본 초점은 뷰박스만 옮긴다 — 그리는 단계에서 존을 걸러야 한다."""
        self.assertIn("var layoutZones = window.__pvLayoutZones", self.html)
        self.assertIn("return zone[0] === 'buffer'; }", self.html)
        self.assertIn("[['buffer', 'buffer']].forEach(function (pair) {", self.html)
        # 초점 목록에 buffer 가 없었다 — 이 셀만 그리는 화면이라 만들어 준다.
        self.assertIn("afr: ['afr', 'post'], buffer: ['buffer'] };", self.html)
        self.assertIn("focus: 'buffer', clearance: true", self.html)
        # 원본은 그대로다 — 손댄 것은 파생본뿐이다.
        self.assertIn("[['afu', 'robot'], ['jbr', 'afr'], ['post', 'buffer']]", self.plant)
        self.assertNotIn("var layoutZones = window.__pvLayoutZones", self.plant)
        self.assertNotIn("buffer: ['buffer'] };", self.plant)

    def test_the_layout_stops_claiming_plant_totals(self):
        """셀 하나만 그리는데 「전체 X = 50,075」가 서 있으면 그 폭으로 읽힌다."""
        for gone in ("'전체 X = ' + n(PLANT_X)", "'전체 Y = ' + n(PLANT_Y)",
                     "[PLANT_X, PLANT_Y, PLANT_Z].map(n)"):
            with self.subTest(gone=gone):
                self.assertIn(gone, self.plant)
                self.assertNotIn(gone, self.html)
        self.assertIn("'셀 X = ' + n(layoutZones[0][3] - layoutZones[0][2])", self.html)
        self.assertIn("'셀 Y = ' + n(layoutZones[0][5] - layoutZones[0][4])", self.html)

    def test_the_spec_block_carries_the_three_dimensions(self):
        L, W, H = self.builder.cell_envelope(self.plant)
        self.assertIn(f'<span class="viz-badge">{L:,} × {W:,} × {H:,} mm</span>', self.html)
        for label, value in (("가로 (X · 공정방향)", L), ("세로 (Y · 진행방향 좌측)", W),
                             ("높이 (Z · FFL 상향)", H)):
            with self.subTest(label=label):
                self.assertIn(f"<tr><td>{label}</td><td>{value:,} mm</td>", self.html)
        panel = self.html.index('id="pv-panel-layout"')
        self.assertLess(panel, self.html.index('class="pv-gbr-spec"'))
        self.assertLess(self.html.index('class="pv-gbr-spec"'),
                        self.html.index('id="pv-layout-svg"'))

    def test_the_layout_names_this_cell(self):
        for was, now in (("전체 장비배치도", "장비 스펙·셀 배치"),
                         ("상세 장비배치도", "장비 스펙·셀 배치"),
                         ("layout: '전체 장비 상세 배치도'", "layout: 'GBR-301 장비 스펙 · 셀 배치'")):
            with self.subTest(now=now):
                self.assertIn(was, self.plant)
                self.assertNotIn(was, self.html)
                self.assertIn(now, self.html)
        self.assertIn("PV-GBR-301-GA-5201 · GBR-301 셀 배치", self.html)

    def test_the_console_keeps_only_this_cells_tabs(self):
        for key in self.builder.PLANT_TABS:
            with self.subTest(tab=key):
                self.assertIn(f"#pv-tab-{key}", self.html)
                self.assertIn(f'[data-pv-drawing-tab="{key}"]', self.html)
                self.assertIn(f'<button class="nav-link" id="pv-tab-{key}"', self.plant)
        for key in self.builder.PLANT_SECTIONS:
            with self.subTest(section=key):
                self.assertIn(f"#{key}", self.html)
                self.assertIn(f'id="{key}"', self.plant)
        self.assertIn("display: none !important;", self.html)

    def test_the_mount_and_register_tabs_show_this_cell(self):
        self.assertIn("MOUNTINGS.filter(function (m) { return m[0] === 'buffer'; })", self.html)
        self.assertIn("mtStation: 'buffer',", self.html)
        self.assertIn("mtStation: 'grm',", self.plant)
        self.assertIn("register.filter(function (row) "
                      "{ return row.join(' ').indexOf('GBR') >= 0; })", self.html)
        self.assertIn("registerBody.innerHTML = register.map(", self.plant)

    def test_the_parts_search_starts_on_this_cells_group(self):
        """이 셀 부품은 품번이 아니라 **분류**로 묶여 있다 (품번은 AFR- 접두어다)."""
        group = self.builder.PARTS_GROUP
        self.assertIn(f'value="{group}" placeholder=', self.html)
        self.assertIn("var section = row.closest('.jb-part-group');", self.html)
        self.assertIn("|| row.textContent.toLowerCase().indexOf(needle) >= 0;", self.html)
        # 그 분류가 원본 카탈로그에 실제로 있고, 그 안에 GBR-301 이 든다.
        self.assertIn(f'"{group}"', self.plant)
        self.assertIn(f'["AFR-GBR-301","{group}"', self.plant)

    # ── 산출물 ──────────────────────────────────────────────────────────
    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("gbr-scene", conv.TARGETS)
        self.assertEqual(conv.TARGETS["gbr-scene"][0],
                         pathlib.Path("docs/drawings/pv-gbr-scene.html"))
        body = conv.convert(self.html, SCENE)
        self.assertIn("<title>GBR-301 R-A/R-B/HOLD 레시피 버퍼</title>", body)

    def test_the_render_check_exists(self):
        """기구가 실제로 도는지는 브라우저만 안다 — 글자에는 흔적이 없다."""
        check = (ROOT / "tools/check_gbr_scene.mjs").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-gbr-scene.html", check)
        self.assertIn("bufferTransfer", check)
        self.assertIn("pvCrn", check)
        self.assertIn("shadowMap", check)
        self.assertIn("afr-route-mode", check)
        # 만재는 **적재를 안 하는 것**이 정답이라 "안 움직인다" 와 겉모습이 같다.
        # 그 둘을 가르는 것(상류 게이트의 유리·행별 인터록·버퍼 표시)까지 잰다.
        self.assertIn("buffer-full", check)
        self.assertIn("afr-buffer-reset", check)
        self.assertIn("만재인데 적재가 돌았다", check)

    def test_the_readme_lists_it(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-gbr-scene.html", readme)
        self.assertIn("tools/build_gbr_scene.py", readme)


if __name__ == "__main__":
    unittest.main()
