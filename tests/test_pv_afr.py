"""AFR-101 알루미늄 프레임 제거장치 파생본 — 생성기 출력과 커밋된 파일, 그리고 모델과의 일치.

파생본은 손으로 쓰지 않는다. `tools/build_afr_scene.py` 가 통합 설계도에서 AFR 셀만
남겨 찍어 내고, 여기서는 (1) 커밋된 파일이 그 출력과 같은지, (2) 시계 창이 캠페인
모델에서 온 값인지, (3) 원본 3D 형상 코드가 그대로인지(파생본은 보이기만 끈다),
(4) 발주 요청 셋 — 그림자·외장 케이싱·천장크레인 — 이 실제로 빠졌는지, (5) 아티팩트
변환기가 받아들이는 문서인지를 본다.

기구가 **실제로 움직이는지**는 글자로 볼 수 없다. 그것은
`node tools/check_afr_scene.mjs` 가 브라우저로 잰다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import afr, afr_units, campaign, frames, layout

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENE = ROOT / "docs/drawings/pv-afr-scene.html"
CLOSEUP = ROOT / "docs/drawings/pv-afr-closeup.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPlantHandPatches(unittest.TestCase):
    """통합 설계도에 손으로 넣은 두 곳이 살아 있는가.

    베이스 브랜치에는 없는 자리라 병합에서 생성물 충돌을 `--theirs` 로 받으면
    **매번 같이 지워진다.** 한 번이라도 잊으면 AFR 이 통째로 안 움직이거나
    부품 확대도가 형상을 못 그리는데, 둘 다 글자에는 흔적이 없다.
    `tools/patch_plant.py` 가 다시 얹고, 여기서 얹혀 있는지 본다.
    """

    def test_both_patches_are_on(self):
        mod = _load("patch_plant")
        text = mod.PLANT.read_text(encoding="utf-8")
        _, done = mod.apply(text)
        missing = [d for d in done if d.endswith("얹음")]
        self.assertFalse(missing,
                         "손패치가 빠졌다 — python tools/patch_plant.py 를 돌릴 것: "
                         + ", ".join(missing))

    def test_the_tool_is_idempotent(self):
        mod = _load("patch_plant")
        text = mod.PLANT.read_text(encoding="utf-8")
        once, _ = mod.apply(text)
        twice, _ = mod.apply(once)
        self.assertEqual(once, twice)

    def test_the_zone_field_survives_the_kit_patch(self):
        """`kit` 을 얹으면서 `zone:pvZone` 을 지우면 파생 도면이 존을 못 읽는다."""
        mod = _load("patch_plant")
        text = mod.PLANT.read_text(encoding="utf-8")
        hook = text[text.index("__pvScene=Object.freeze("):]
        hook = hook[:hook.index(")});") + 4]
        self.assertIn("zone:pvZone", hook)
        self.assertIn("kit:Object.freeze", hook)


class TestAfrScene(unittest.TestCase):
    """통합 설계도에서 AFR-101 셀만 남긴 파생본."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_afr_scene")
        cls.html = SCENE.read_text(encoding="utf-8")
        cls.plant = cls.builder.PLANT.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-afr-scene.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_afr_scene.py 를 돌리고 커밋한다")

    # ── 시계 ────────────────────────────────────────────────────────────
    def test_the_clock_window_is_the_cell_occupancy(self):
        """창은 [투입부+JBR 점유, 거기에 AFR 점유] 다 — 새로 정한 숫자가 없다."""
        t0, t1 = self.builder.window()
        self.assertEqual(t0, campaign.INFEED_S + campaign.JBR_S)
        self.assertEqual(t1, t0 + campaign.AFR_S)
        self.assertIn(f",Ve={t0:g},ai=0", self.html)
        self.assertIn(f'min="{t0:g}" max="{t1:g}"', self.html)
        self.assertIn(f'id="jb-time">{t0:.2f} / {t1:.2f} s</div>', self.html)

    def test_the_window_end_is_the_films_own_end(self):
        """이 셀이 패널을 놓는 순간이 곧 영상의 끝이라 `ci` 는 자를 것이 없다.

        창의 시작은 **모델이 정한다** — 여기 85 라고 적어 두었다가 베이스가
        JBR 칸을 4 → 7 s 로 늘리자 이 시험만 옛 수를 고집했다. 창은 언제나
        `INFEED_S + JBR_S` 이므로 그렇게 견준다.
        """
        start = float(campaign.INFEED_S + campaign.JBR_S)
        self.assertIn(",ci=nt+Lr", self.html)
        self.assertIn(f"var nt={start:g},", self.html)
        self.assertEqual(self.builder.window()[0], start)

    def test_every_rewind_lands_inside_the_window(self):
        """조작을 바꿔도 시계가 창 밖(0 s)으로 되감기면 안 된다."""
        t0, _ = self.builder.window()
        # 원본의 `Ve=0` 은 선언 1 + 되감기 6 이다. 생성기는 선언을 먼저 바꾸고 남은 6 을 센다.
        self.assertEqual(len(re.findall(r"\bVe=0\b", self.plant)), 7, "원본의 되감기 수가 바뀌었다")
        self.assertNotIn("Ve=0", self.html)
        # 파생본의 `Ve=85` 는 선언 1 + 반복 되돌림 1 + 되감기 6 이다.
        self.assertEqual(len(re.findall(rf"\bVe={t0:g}\b", self.html)), 8)
        self.assertIn(f"Ve={t0:g}+(Ve-{t0:g})%(ci-{t0:g})", self.html)
        self.assertIn(f"let pe=Math.round((i-{t0:g})/(ci-{t0:g})*100)", self.html)

    # ── 시점·도면 ───────────────────────────────────────────────────────
    def test_only_afr_views_and_the_afr_sheet_remain(self):
        views = re.findall(r'data-jb-view="([a-z]+)" type="button"', self.html)
        self.assertEqual(sorted(views), sorted(self.builder.KEEP_VIEWS))
        for view in self.builder.AUTO_VIEWS:
            self.assertIn(view, self.builder.KEEP_VIEWS, "자동추적이 고르는 시점이 버튼에 없다")
        sheets = self.html.split('id="pv-drawing-station"')[1][:900]
        for key in self.builder.DROP_STATIONS:
            self.assertNotIn(f'<option value="{key}"', sheets)
        self.assertIn('<option value="afr" selected>', sheets)
        self.assertIn(',xl="afr"', self.html)

    def test_the_auto_camera_list_loses_only_the_downstream_view(self):
        """마지막 단계만 후단 셀을 보고 있었다 — 꺼진 셀이라 이 셀 시점으로 되돌린다."""
        self.assertIn(f"se={self.builder.AUTO_VIEWS_OLD}", self.plant)
        self.assertIn(f"se={self.builder.AUTO_VIEWS_NEW}", self.html)
        self.assertNotIn("afrpost", self.html.split("se=[")[1][:200])

    def test_the_default_camera_looks_from_the_upstream_face(self):
        """하류에는 SG-301 몸체 2,200 이 서 있어 프레임 제거기구를 가린다."""
        self.assertIn("afr:{position:new C(qt-3.85,3.35,5.15),target:new C(qt+.3,1.15,0)}",
                      self.html)
        self.assertIn("afr:{position:new C(qt+5.8,5.8,-9.8),target:new C(qt,1.15,0)}",
                      self.plant, "원본은 그대로다")

    # ── 장면 ────────────────────────────────────────────────────────────
    def test_the_scene_is_narrowed_not_rewritten(self):
        """3D 형상 코드는 원본과 같아야 한다 — 파생본은 보이기만 끈다."""
        i = self.plant.index("var pvZone=")
        j = self.plant.index("Ae.__pvScene=")
        patched = (',xl="line"', "fp.line:fp[i]", '"reset"?"line"',
                   "afr:{position:new C(qt+5.8,5.8,-9.8)", "var pvCrn=new ce;")
        for line in self.plant[i:j].splitlines():
            if any(anchor in line for anchor in patched):
                continue
            self.assertIn(line, self.html, f"원본 장면 코드가 파생본에서 바뀌었다: {line[:80]}")
        self.assertIn("window.__pvAfrScene", self.html)

    def test_the_scene_boundary_is_the_zone_table(self):
        low, high = self.builder.zone_world_x()
        zone = next(z for z in layout.build_zones() if z.key == "afr")
        self.assertEqual(low, (zone.x0_mm - self.builder.SCENE_ORIGIN_X_MM) / 1000)
        self.assertEqual(high, (zone.x1_mm - self.builder.SCENE_ORIGIN_X_MM) / 1000)
        self.assertIn(f"const LOW = {low:g};", self.html)
        self.assertIn(f"const HIGH = {high:g};", self.html)
        # 상류 여유는 JB/AFR-301 직결 인계롤러 런(존 시작 −1,315)을 담아야 한다.
        self.assertGreater(self.builder.UPSTREAM_MARGIN_M, 1.315)
        self.assertIn(f"const IN = LOW - {self.builder.UPSTREAM_MARGIN_M:g}", self.html)

    def test_the_cells_that_stay_off(self):
        self.assertEqual(sorted(self.builder.OFF_CELLS),
                         sorted(k for k in ("afu", "robot", "jbr", "post", "buffer", "grm")))
        self.assertNotIn("afr", self.builder.OFF_CELLS)
        self.assertIn("if (cell === 'afr') return;", self.html)

    # ── 발주 요청 셋 ────────────────────────────────────────────────────
    def test_the_3d_casts_no_floor_shadow(self):
        """셀 하나를 보는 화면에서 바닥 그림자는 기구 밑을 덮기만 한다."""
        self.assertIn("shadowMap.enabled=!1;", self.html)
        self.assertNotIn("shadowMap.enabled=!0;", self.html)
        self.assertIn("shadowMap.enabled=!0;", self.plant)   # 원본은 그대로다

    def test_the_casing_is_off_by_default_and_by_group(self):
        """껍질은 기구를 가린다 — 토글 기본값도 끄고 묶음째 끈다."""
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
    def test_the_flow_strip_shows_only_the_handoff_and_the_cell(self):
        first, last = self.builder.FLOW_FIRST, self.builder.FLOW_LAST
        self.assertEqual((first, last), (8, 9))
        self.assertIn(f".pv-flow-track > li:nth-child(-n+{first - 1})", self.html)
        self.assertIn(f".pv-flow-track > li:nth-child(n+{last + 1})", self.html)
        steps = re.findall(r'<li data-flow-step="(\d+)"', self.html)
        self.assertEqual(len(steps), 11, "흐름표 칸은 지우지 않고 CSS 로만 가린다")

    def test_out_of_scope_controls_are_hidden_and_the_cell_keeps_its_own(self):
        for key in self.builder.HIDDEN_CONTROLS:
            self.assertIn(f'label[for="{key}"]', self.html)
        self.assertIn('id="afr-buffer-reset" type="button" hidden', self.html)
        # 반입 등록 레시피는 남는다 — `frameless` 가 이 셀의 인발을 통째로 생략시킨다.
        self.assertIn('<label class="form-label" for="pv-panel-structure">', self.html)
        self.assertNotIn('label[for="pv-panel-structure"]', self.html)
        self.assertNotIn("ENGINEERING BASE REV.22", self.html)
        self.assertIn("AFR-101 단독 파생본", self.html)

    def test_the_cell_envelope_agrees_between_model_and_ga_sheet(self):
        """가로·세로·높이는 배치 모델과 GA 시트 두 곳에 있다 — 갈라지면 멈춘다."""
        L, W, H = self.builder.cell_envelope(self.plant)
        z = next(x for x in layout.build_zones() if x.key == "afr")
        self.assertEqual((L, W, H), (z.x1_mm - z.x0_mm, z.y1_mm - z.y0_mm, z.height_mm))
        with self.assertRaises(SystemExit):
            self.builder.cell_envelope(
                self.plant.replace("envelope: [5900, 5600, 2800]",
                                   "envelope: [5900, 5600, 2801]"))

    def test_the_layout_draws_this_cell_only(self):
        """원본 초점은 뷰박스만 옮긴다 — 그리는 단계에서 존을 걸러야 한다."""
        self.assertIn("var layoutZones = window.__pvLayoutZones", self.html)
        self.assertIn("return zone[0] === 'afr'; }", self.html)
        self.assertIn("[['afr', 'afr']].forEach(function (pair) {", self.html)
        # 원본은 그대로다 — 손댄 것은 파생본뿐이다.
        self.assertIn("[['afu', 'robot'], ['jbr', 'afr'], ['post', 'buffer']]", self.plant)
        self.assertNotIn("[['afr', 'afr']]", self.plant)
        self.assertNotIn("var layoutZones = window.__pvLayoutZones", self.plant)

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
        self.assertLess(panel, self.html.index('class="pv-afr-spec"'))
        self.assertLess(self.html.index('class="pv-afr-spec"'),
                        self.html.index('id="pv-layout-svg"'))

    def test_the_layout_names_this_cell(self):
        for was, now in (("전체 장비배치도", "장비 스펙·셀 배치"),
                         ("상세 장비배치도", "장비 스펙·셀 배치"),
                         ("layout: '전체 장비 상세 배치도'", "layout: 'AFR-101 장비 스펙 · 셀 배치'")):
            with self.subTest(now=now):
                self.assertIn(was, self.plant)
                self.assertNotIn(was, self.html)
                self.assertIn(now, self.html)
        self.assertIn("PV-AFR-101-GA-4101 · AFR-101 셀 배치", self.html)

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
        self.assertIn("MOUNTINGS.filter(function (m) { return m[0] === 'afr'; })", self.html)
        self.assertIn("mtStation: 'afr',", self.html)
        self.assertIn("mtStation: 'grm',", self.plant)
        self.assertIn("register.filter(function (row) "
                      "{ return row.join(' ').indexOf('AFR') >= 0; })", self.html)
        self.assertIn("registerBody.innerHTML = register.map(", self.plant)

    def test_the_parts_search_starts_on_this_cell(self):
        self.assertIn('value="AFR-" placeholder=', self.html)
        self.assertIn("var byNo = /^[a-z]+-/.test(needle);", self.html)

    # ── 산출물 ──────────────────────────────────────────────────────────
    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("afr-scene", conv.TARGETS)
        self.assertEqual(conv.TARGETS["afr-scene"][0],
                         pathlib.Path("docs/drawings/pv-afr-scene.html"))
        body = conv.convert(self.html, SCENE)
        self.assertIn("<title>AFR-101 알루미늄 프레임 제거장치</title>", body)

    def test_the_render_check_exists(self):
        """기구가 실제로 도는지는 브라우저만 안다 — 글자에는 흔적이 없다."""
        check = (ROOT / "tools/check_afr_scene.mjs").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-afr-scene.html", check)
        self.assertIn("getAfrState", check)
        self.assertIn("pvCrn", check)
        self.assertIn("shadowMap", check)

    def test_the_readme_lists_it(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-afr-scene.html", readme)
        self.assertIn("tools/build_afr_scene.py", readme)


if __name__ == "__main__":
    unittest.main()


class TestAfrCloseup(unittest.TestCase):
    """두 핵심 유닛의 부품 확대도 — 형상·사양이 모델에서 나오는가."""

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_afr_closeup")
        cls.html = CLOSEUP.read_text(encoding="utf-8")
        cls.plant = cls.builder.PLANT.read_text(encoding="utf-8")

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-afr-closeup.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_afr_closeup.py 를 돌리고 커밋한다")

    def test_two_units_with_parts_and_a_principle(self):
        us = afr_units.units()
        self.assertEqual([u.key for u in us], ["short", "long"])
        for u in us:
            with self.subTest(unit=u.key):
                self.assertGreaterEqual(len(u.parts), 10, "부품이 너무 적다")
                self.assertEqual(len(u.principle), 5, "작동원리가 5 단계가 아니다")
                self.assertTrue(all(p.qty >= 1 for p in u.parts))
                self.assertTrue(all(p.role for p in u.parts), "역할이 빈 부품이 있다")

    def test_every_part_points_at_a_catalogue_row(self):
        """부품표에 없는 품번을 지어내지 않는다 — 참고 표시(—)만 예외다."""
        for u in afr_units.units():
            for p in u.parts:
                with self.subTest(part=p.key):
                    if p.catalog == "—":
                        continue
                    self.assertIn(f'["{p.catalog}"', self.plant,
                                  f"{p.catalog} 이 통합 설계도 부품표에 없다")

    def test_the_roller_actually_sits_in_the_groove(self):
        """확대도가 그리는 자리가 모델의 물림과 같은가 — 눈이 아니라 수로 본다."""
        u = afr_units.long_unit()
        roller = next(p for p in u.parts if p.key == "roller")
        work = next(p for p in u.parts if p.key == "work")
        prof = frames.profile()
        groove_mid_y = (work.pos[1] + frames.GROOVE_V0_MM
                        + frames.GROOVE_H_MM / 2 - prof["cv_mm"])
        floor_z = work.pos[2] - prof["cu_mm"] + afr.GROOVE_D_MM
        self.assertAlmostEqual(groove_mid_y, roller.pos[1], places=6,
                               msg="롤러 축이 홈 한가운데가 아니다")
        self.assertAlmostEqual(floor_z, roller.pos[2] + roller.size[0] / 2, places=6,
                               msg="롤러 바깥면이 홈 바닥에 안 닿는다")
        # 홈이 롤러 폭을 받아 주는가 (모델의 선정 조건과 같은 판정)
        self.assertLessEqual(roller.size[1] + 2 * afr.ROLLER_CLEAR_MM, afr.GROOVE_H_MM)

    def test_the_rail_section_is_a_simple_polygon(self):
        pts = afr_units.rail_outline()
        self.assertGreaterEqual(len(pts), 12)
        area2 = sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                    - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
        self.assertGreater(abs(area2) / 2, 0.0)
        self.assertLessEqual(max(abs(u) for u, _ in pts), afr_units.RAIL_W_MM / 2 + 1e-9)
        self.assertLessEqual(max(v for _, v in pts), afr_units.RAIL_H_MM + 1e-9)

    def test_the_specs_come_from_the_model(self):
        for probe in (afr.cylinder_spec(),
                      f"{afr.working_pressure_bar():.0f} bar",
                      f"Ø{afr.roller_d_mm()} × {afr.roller_h_mm()}",
                      f"{afr.roller_contact_mpa()} MPa",
                      f"{afr.bar_sag_mm()} mm"):
            with self.subTest(probe=probe):
                self.assertIn(probe, self.html)

    def test_the_plant_lends_its_3d_kit(self):
        """확대도는 플랜트와 **같은 재질·같은 조명**으로 그린다."""
        self.assertIn("kit:Object.freeze({P:P,Ee:Ee", self.plant)
        self.assertIn("S.kit", self.html)
        self.assertIn("__pvAfrCloseup", self.html)

    def test_the_console_is_the_closeups_own(self):
        for token in ('id="afr-cu-tabs"', 'id="afr-cu-explode"', 'id="afr-cu-cut"',
                      'id="afr-cu-rows"', 'id="afr-cu-principle"', 'id="afr-cu-spec"'):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertIn("shadowMap.enabled=!1;", self.html)
        self.assertNotIn("shadowMap.enabled=!0;", self.html)

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("afr-closeup", conv.TARGETS)
        body = conv.convert(self.html, CLOSEUP)
        self.assertIn("<title>AFR-101 부품 확대도</title>", body)

    def test_the_readme_lists_it(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-afr-closeup.html", readme)
        self.assertIn("tools/build_afr_closeup.py", readme)
