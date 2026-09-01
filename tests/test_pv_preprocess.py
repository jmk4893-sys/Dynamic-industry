"""전처리 플랜트 배치도가 배치 모델과 어긋나지 않는지 검증.

`docs/drawings/pv-preprocess-plant.html` 는 셀 외형·존 배치를 자바스크립트 리터럴로
들고 있다. `pv_preprocess.layout` 을 고치고 도면을 갱신하지 않으면 (또는 그 반대면)
두 문서가 서로 다른 공장을 가리키게 되므로, 값이 일치하는지 확인한다.

REV.21 에서 실제로 깨져 있던 두 가지 — 존이 자기 장비보다 짧은 것, 통로가 장비에
덮이는 것 — 은 아래 불변식 테스트로 다시 들어올 수 없게 막는다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

from pv_preprocess import electrical, layout, vision

DRAWING = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "pv-preprocess-plant.html"


def read_drawing() -> str:
    return DRAWING.read_text(encoding="utf-8")


class TestLayoutInvariants(unittest.TestCase):
    """배치 모델 자체가 성립하는지 — 도면과 무관하게 항상 참이어야 한다."""

    def setUp(self):
        self.zones = layout.build_zones()

    def test_zone_holds_its_station(self):
        """존은 자기 셀의 X·Y·H 를 담을 수 있어야 한다 (REV.21 은 X 가 10 m 부족했다)."""
        for zone in self.zones:
            station = layout.STATIONS.get(zone.key)
            if station is None:
                continue
            with self.subTest(zone=zone.key):
                self.assertGreaterEqual(zone.length_mm, station.length_mm, "존 X 가 장비보다 짧다")
                self.assertGreaterEqual(zone.width_mm, station.width_mm, "존 Y 가 장비보다 좁다")
                self.assertGreaterEqual(zone.height_mm, station.height_mm, "존 높이가 장비보다 낮다")

    def test_zones_tile_without_gap_or_overlap(self):
        self.assertEqual(self.zones[0].x0_mm, 0)
        for previous, current in zip(self.zones, self.zones[1:]):
            with self.subTest(zone=current.key):
                self.assertEqual(current.x0_mm, previous.x1_mm, "존 사이에 틈이나 겹침이 있다")

    def test_walkway_is_outside_every_zone(self):
        """통로는 장비 밴드 밖 전용 밴드다 (REV.21 은 전장의 49 %에서 겹쳤다)."""
        aisle_y0, aisle_y1 = layout.aisle_band_mm()
        for zone in self.zones:
            with self.subTest(zone=zone.key):
                overlap = min(zone.y1_mm, aisle_y1) - max(zone.y0_mm, aisle_y0)
                self.assertLessEqual(overlap, 0, "장비 존이 보행·정비 통로를 잠식한다")

    def test_every_zone_sits_inside_the_machine_band(self):
        for zone in self.zones:
            with self.subTest(zone=zone.key):
                self.assertGreaterEqual(zone.y0_mm, 0)
                self.assertLessEqual(zone.y1_mm, layout.MACHINE_BAND_Y_MM)

    def test_plant_envelope_is_derived(self):
        length, width, height = layout.plant_envelope_mm()
        self.assertEqual(length, sum(zone.length_mm for zone in self.zones))
        self.assertEqual(width, layout.MACHINE_BAND_Y_MM + layout.AISLE_WIDTH_MM)
        self.assertEqual(height, max(zone.height_mm for zone in self.zones))

    def test_seven_zones_and_one_gate(self):
        self.assertEqual(len(self.zones), 7)
        self.assertEqual([z.key for z in self.zones if z.key not in layout.STATIONS], ["gate"])


class TestDrawingMatchesModel(unittest.TestCase):
    """도면 안의 리터럴이 배치 모델과 같은 값인지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def drawing_envelopes(self) -> dict[str, tuple[int, int, int]]:
        """도면의 `stations` 블록에서 키별 envelope 를 뽑는다."""
        block = self.html[self.html.index("  var stations = {"):self.html.index("  var register = [")]
        found: dict[str, tuple[int, int, int]] = {}
        current = None
        for line in block.splitlines():
            key = re.match(r"\s{4}(\w+): \{$", line)
            if key:
                current = key.group(1)
            envelope = re.search(r"envelope: \[(\d+), (\d+), (\d+)\]", line)
            if envelope and current:
                found[current] = tuple(int(v) for v in envelope.groups())
        return found

    def test_station_envelopes_match(self):
        drawn = self.drawing_envelopes()
        self.assertEqual(set(drawn), set(layout.STATIONS), "도면과 모델의 셀 목록이 다르다")
        for key, station in layout.STATIONS.items():
            with self.subTest(station=key):
                self.assertEqual(drawn[key], station.envelope)

    def test_parts_fit_inside_their_envelope(self):
        """각 셀의 부품 실측 바운딩박스가 자기 GA 외형 안에 들어오는지.

        REV.21 은 bfc(X +260)·buffer(X +1,675) 두 셀에서 부품이 외형을 넘었고, 그 탓에
        평면·정면 뷰의 부품과 라벨이 뷰 프레임 밖으로 나가 옆 뷰를 덮었다.
        part 축은 [X, 상하, 깊이], envelope 축은 [L, W, H] = [X, 깊이, 상하] 로 순서가 다르다.
        """
        block = self.html[self.html.index("  var stations = {"):self.html.index("  var register = [")]
        current = None
        parts: dict[str, list[tuple[list[int], list[int]]]] = {}
        for line in block.splitlines():
            key = re.match(r"\s{4}(\w+): \{$", line)
            if key:
                current = key.group(1)
                parts[current] = []
            found = re.search(
                r"part\('[^']*', '[^']*', \[([-\d, ]+)\], \[([-\d, ]+)\]", line)
            if found and current and "'sweep'" not in line:
                size = [int(v) for v in found.group(1).split(",")]
                at = [int(v) for v in found.group(2).split(",")]
                parts[current].append((size, at))

        self.assertEqual(set(parts), set(layout.STATIONS), "부품표를 못 읽은 셀이 있다")
        for key, station in layout.STATIONS.items():
            rows = parts[key]
            self.assertTrue(rows, f"{key} 부품표가 비었다")
            for part_axis, envelope_axis, name in ((0, 0, "X"), (2, 1, "Y"), (1, 2, "Z")):
                low = min(at[part_axis] - size[part_axis] / 2 for size, at in rows)
                high = max(at[part_axis] + size[part_axis] / 2 for size, at in rows)
                with self.subTest(station=key, axis=name):
                    self.assertLessEqual(
                        high - low,
                        station.envelope[envelope_axis],
                        f"{key} 부품이 {name} 축에서 외형을 넘는다",
                    )

    def test_zone_seed_matches(self):
        """도면의 zoneSeed 순서·Y 시작값이 모델과 같은지."""
        block = self.html[self.html.index("  var zoneSeed = ["):self.html.index("  // [키, 표기, X0")]
        drawn = re.findall(r"\['(\w+)', '([^']*)', (\d+), '([^']*)'", block)
        self.assertEqual(
            [(key, y0) for key, _, y0, _ in [(k, la, int(y), n) for k, la, y, n in drawn]],
            [(seed[0], seed[2]) for seed in layout.ZONE_SEED],
        )

    def test_machine_band_and_aisle_match(self):
        self.assertIn(f"var MACHINE_BAND_Y = {layout.MACHINE_BAND_Y_MM};", self.html)
        self.assertIn(f"var AISLE_WIDTH = {layout.AISLE_WIDTH_MM};", self.html)
        self.assertIn(f"var HANDOFF_CLEARANCE = {layout.HANDOFF_CLEARANCE_MM};", self.html)

    def test_handoff_gate_is_derived_not_hand_set(self):
        """게이트 존은 실측 이격에서 파생해야 한다.

        REV.21 의 1,250 mm 는 그 구간에 자기 하드웨어가 하나도 없는 자리표시였다.
        인계 롤러·데이터 게이트는 AFR 베이스에, VS-301 검증헤드는 JBR 셀 안쪽에 있었다.
        """
        gate = next(zone for zone in layout.build_zones() if zone.key == "gate")
        self.assertEqual(gate.length_mm, layout.HANDOFF_CLEARANCE_MM)
        # 3D 실측 가드-가드 이격 325 mm 보다 작아지면 두 셀 가드가 닿는다.
        self.assertGreaterEqual(layout.HANDOFF_CLEARANCE_MM, 325)
        self.assertNotIn("'gate', 'JB/AFR', 2450, 'MAP', 1250", self.html)

    def test_downstream_span_text_matches(self):
        """AFR-101–GBR-301 구간 치수는 존에서 파생한 값과 같아야 한다."""
        zones = layout.build_zones()
        afr = next(zone for zone in zones if zone.key == "afr")
        span = zones[-1].x1_mm - afr.x0_mm
        self.assertIn(f"{span:,} × {layout.MACHINE_BAND_Y_MM:,} mm", self.html)


class TestDrawingDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지 — docs/drawings/ 의 다른 도면과 같은 기준."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_is_standalone_document(self):
        self.assertTrue(DRAWING.exists())
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        for tag in ('<html lang="ko">', "<head>", "</head>", "<body>", "</body>", "</html>"):
            self.assertIn(tag, self.html, tag)
        self.assertIn('<meta charset="utf-8">', self.html)   # 한글 도면 — 빠지면 깨진다
        self.assertIn('name="viewport"', self.html)
        self.assertIn("<title>태양광 패널 전처리 통합 플랜트 설계도</title>", self.html)

    def test_fetches_nothing_from_the_network(self):
        """오프라인·차단 환경에서도 그대로 열려야 한다.

        REV.21 은 unpkg 에서 lucide 와 floating-ui 를 받아 왔고, 차단되면 프로그램
        버튼의 아이콘이 통째로 사라졌다. 아이콘은 인라인 SVG 로 들어가 있다.
        """
        for pattern in ('src="http', "src='http", 'href="http', "href='http", "@import"):
            self.assertNotIn(pattern, self.html, f"외부 리소스 참조: {pattern}")
        self.assertNotIn("data-lucide", self.html, "CDN 아이콘 런타임이 남아 있다")
        self.assertIn('<meta http-equiv="Content-Security-Policy"', self.html)
        self.assertIn("default-src 'none'", self.html)

    def test_supports_both_themes(self):
        self.assertIn("color-scheme: light dark;", self.html)
        self.assertIn('@media (prefers-color-scheme: dark)', self.html)
        self.assertIn(':root:not([data-theme="light"])', self.html)
        self.assertIn(':root[data-theme="dark"]', self.html)

    def test_container_tags_balance(self):
        for tag in ("svg", "section", "table", "defs", "dialog", "details"):
            with self.subTest(tag=tag):
                opened = len(re.findall(rf"<{tag}[ >]", self.html))
                closed = len(re.findall(rf"</{tag}>", self.html))
                self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_element_ids_are_unique(self):
        markup = re.sub(r"<script[^>]*>.*?</script>", "", self.html, flags=re.S)
        markup = re.sub(r"<style[^>]*>.*?</style>", "", markup, flags=re.S)
        ids = re.findall(r'\sid="([^"]+)"', markup)
        self.assertEqual(len(ids), len(set(ids)), "중복 id")

    def test_labels_and_aria_point_at_real_ids(self):
        markup = re.sub(r"<script[^>]*>.*?</script>", "", self.html, flags=re.S)
        ids = set(re.findall(r'\sid="([^"]+)"', markup))
        for attribute in ("for", "aria-controls", "aria-labelledby", "aria-describedby"):
            targets = {
                target
                for value in re.findall(rf'\s{attribute}="([^"]+)"', markup)
                for target in value.split()
            }
            with self.subTest(attribute=attribute):
                self.assertEqual(targets - ids, set(), f"{attribute} 가 없는 id 를 가리킨다")


class TestElectricalIncomer(unittest.TestCase):
    """전기 인입도(PV-PLANT-EL-1005)가 부하 계산과 어긋나지 않는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_feeder_table_matches_the_model(self):
        """도면 안의 피더 리터럴이 electrical.py 와 같은 값인지."""
        block = self.html[self.html.index("  var feeders = ["):self.html.index("  function electricalTotals()")]
        rows = re.findall(
            r"\['(F\d)', '([\w-]+)', '([^']*)', ([\d.]+), ([\d.]+), (\d+), '([^']*)', '([^']*)'\]", block)
        self.assertEqual(len(rows), len(electrical.FEEDERS), "도면과 모델의 피더 수가 다르다")
        for drawn, feeder in zip(rows, electrical.FEEDERS):
            with self.subTest(feeder=feeder.tag):
                self.assertEqual(drawn[0], feeder.tag)
                self.assertEqual(drawn[1], feeder.panel)
                self.assertEqual(drawn[2], feeder.served)
                self.assertAlmostEqual(float(drawn[3]), feeder.installed_kw, places=3)
                self.assertAlmostEqual(float(drawn[4]), feeder.diversity, places=3)
                self.assertEqual(int(drawn[5]), feeder.breaker_at)
                self.assertEqual(drawn[6], feeder.cable)
                self.assertEqual(drawn[7], feeder.source)

    def test_supply_constants_match(self):
        self.assertIn(f"var SUPPLY_VOLTAGE_V = {electrical.SUPPLY_VOLTAGE_V};", self.html)
        self.assertIn(f"var POWER_FACTOR = {electrical.POWER_FACTOR:.2f};", self.html)
        self.assertIn(f"var MAIN_BREAKER_FRAME_A = {electrical.MAIN_BREAKER_FRAME_A};", self.html)
        self.assertIn(f"var CONTRACT_MARGIN = {electrical.CONTRACT_MARGIN};", self.html)

    def test_main_breaker_carries_the_demand(self):
        """주 차단기는 수요 전류에 10 % 여유를 얹고도 남아야 한다."""
        self.assertGreaterEqual(electrical.main_breaker_at(), electrical.demand_current_a() * 1.1)
        self.assertLessEqual(electrical.main_breaker_at(), electrical.MAIN_BREAKER_FRAME_A)

    def test_every_feeder_breaker_carries_its_own_load(self):
        """피더 차단기도 자기 설치 부하 전류를 견뎌야 한다."""
        for feeder in electrical.FEEDERS:
            current = feeder.installed_kw * 1000 / (
                3 ** 0.5 * electrical.SUPPLY_VOLTAGE_V * electrical.POWER_FACTOR)
            with self.subTest(feeder=feeder.tag):
                self.assertGreaterEqual(feeder.breaker_at, current, "피더 차단기가 설치 부하보다 작다")

    def test_demand_never_exceeds_installed(self):
        self.assertLess(electrical.demand_kw(), electrical.installed_kw())
        for feeder in electrical.FEEDERS:
            with self.subTest(feeder=feeder.tag):
                self.assertLessEqual(feeder.diversity, 1.0)
                self.assertGreater(feeder.diversity, 0.0)

    def test_drawing_is_registered(self):
        self.assertIn("'PV-PLANT-EL-1005'", self.html)
        self.assertIn('id="pv-tab-electrical"', self.html)
        self.assertIn('id="pv-electrical-svg"', self.html)


class TestVisionReduction(unittest.TestCase):
    """비전 최소화가 도면·부품표·3D 에 일관되게 반영됐는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_retired_parts_are_gone_from_the_catalog(self):
        for part_no in vision.RETIRED_PART_NUMBERS:
            with self.subTest(part=part_no):
                self.assertNotIn(f'["{part_no}"', self.html, "부품표에 제거 대상이 남아 있다")

    def test_retired_heads_are_hidden_in_3d(self):
        """부품표에서 뺀 헤드가 3D 에만 남으면 BOM 과 화면이 어긋난다."""
        block = self.html[self.html.index("function retireReducedVisionHeads()"):]
        block = block[:block.index("}());")]
        for label in vision.RETIRED_MESH_LABELS:
            with self.subTest(label=label):
                self.assertIn(f"'{label}'", block)

    def test_transport_and_data_gate_survive(self):
        """JB/AFR 게이트의 이송·데이터 기능은 남겨야 한다 — 영상 헤드만 뺀 것이다."""
        for kept in ("JB/AFR-301 직결 동기 인계 롤러", "JB/AFR-301 데이터 인계 게이트"):
            with self.subTest(mesh=kept):
                self.assertIn(kept, self.html)
                self.assertNotIn(f"'{kept}'", self.html[self.html.index("var retired = ["):
                                                        self.html.index("var hidden = 0;")])

    def test_safety_channels_are_untouched(self):
        """안전 채널은 감축 대상이 아니다 — SISTEMA 재계산 없이 손댈 수 없다."""
        for part_no in vision.PROTECTED_SAFETY_PARTS:
            with self.subTest(part=part_no):
                self.assertIn(f'["{part_no}"', self.html, "보호 대상 안전 부품이 사라졌다")

    def test_head_count_reduction(self):
        current, reduced = vision.head_reduction()
        self.assertEqual((current, reduced), (7, 5))
        self.assertEqual(len(vision.retired_heads()), len(vision.RETIRED_PART_NUMBERS))
        self.assertIn("영상 헤드 7 → 5", self.html)

    def test_review_sheet_is_registered(self):
        self.assertIn("'PV-VIS-901'", self.html)
        self.assertIn('id="jb-vision-reduction"', self.html)


class TestCutawayAndExplode(unittest.TestCase):
    """컷어웨이·분해 조작이 메인 3D 영상과 도면 3D 분해도 양쪽에 같은 축으로 붙어 있는지."""

    #: 두 화면이 공유해야 하는 절단축. 한쪽에만 축을 추가하면 조작이 어긋난다.
    CUT_AXES = ("x+", "x-", "z+", "z-", "y+")

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_bundle_exports_scene_handles(self):
        """3D 번들이 씬 핸들을 내보내야 컷어웨이를 읽을 수 있는 코드로 구현할 수 있다."""
        self.assertIn("Ae.__pvScene=Object.freeze({", self.html)
        for handle in ("scene:", "camera:", "controls:", "renderer:", "pickables:",
                       "Plane:", "Group:", "Vector3:"):
            with self.subTest(handle=handle):
                self.assertIn(handle, self.html)

    def test_scene_controls_offer_every_axis(self):
        for axis in self.CUT_AXES:
            with self.subTest(axis=axis):
                self.assertIn(f'<option value="{axis}"', self.html)
        self.assertIn('id="pv-cut-enable"', self.html)
        self.assertIn('id="pv-cut-position"', self.html)
        self.assertIn('id="pv-scene-explode"', self.html)
        self.assertIn('id="pv-cut-reset"', self.html)

    def test_drawing_tab_offers_the_same_axes(self):
        block = self.html[self.html.index("  var CUT_AXES = {"):self.html.index("  var state = { tab: 'fab'")]
        found = tuple(re.findall(r"'([xyz][+-])': \{ axis:", block))
        self.assertEqual(found, self.CUT_AXES, "도면 3D 분해도의 절단축이 메인 영상과 다르다")
        self.assertIn('id="pv-explode-cut-axis"', self.html)
        self.assertIn('id="pv-explode-cut-at"', self.html)

    def test_cut_axis_maps_to_a_real_box_axis(self):
        """축 인덱스는 part.size/at 의 [X, 상하, 깊이] 순서를 따라야 한다."""
        block = self.html[self.html.index("  var CUT_AXES = {"):self.html.index("  var state = { tab: 'fab'")]
        expected = {"x+": 0, "x-": 0, "z+": 2, "z-": 2, "y+": 1}
        for key, axis in re.findall(r"'([xyz][+-])': \{ axis: (\d)", block):
            with self.subTest(axis=key):
                self.assertEqual(int(axis), expected[key])

    def test_section_faces_use_a_distinct_fill(self):
        """절단으로 새로 생긴 면은 단면색으로 채워 잘린 자리를 드러내야 한다."""
        self.assertIn("section: css('--destructive'", self.html)
        self.assertIn("face.section ? fills.section", self.html)


class TestRemovalHeadCapacity(unittest.TestCase):
    """구동 용량 검산의 상수가 도면 목록의 헤드 사양과 맞는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_head_capacity_matches_the_drawing_register(self):
        self.assertIn("var HEAD_CAPACITY_KN = 15;", self.html)
        self.assertIn("'PV-JBR-HD-3201', '15 kN L칼날 제거헤드'", self.html)

    def test_head_count_matches_the_three_head_bridge(self):
        self.assertIn("var HEAD_COUNT = 3;", self.html)
        for head in ("HD-1", "HD-2", "HD-3"):
            self.assertIn(f"part('{head}'", self.html, f"{head} 가 JBR-201 부품표에 없다")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
