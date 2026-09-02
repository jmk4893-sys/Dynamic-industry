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

from pv_preprocess import acoustics, electrical, layout, servos, vision, wiring

DRAWING = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "pv-preprocess-plant.html"


def read_drawing() -> str:
    return DRAWING.read_text(encoding="utf-8")


def station_blocks(html: str) -> dict[str, str]:
    """도면의 `stations` 객체를 키별 원문 블록으로 쪼갠다."""
    block = html[html.index("  var stations = {"):html.index("  var register = [")]
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in block.splitlines():
        key = re.match(r"\s{4}(\w+): \{$", line)
        if key:
            current = key.group(1)
            blocks[current] = []
        if current:
            blocks[current].append(line)
    return {key: "\n".join(lines) for key, lines in blocks.items()}


def part_span(block: str, tag: str, axis: int = 0) -> tuple[float, float]:
    """한 부품의 축 방향 구간 (lo, hi)."""
    found = re.search(
        r"part\('%s', '[^']*', \[([-\d, ]+)\], \[([-\d, ]+)\]" % re.escape(tag), block)
    if found is None:
        raise AssertionError(f"{tag} 를 부품표에서 못 찾았다")
    size = [int(v) for v in found.group(1).split(",")]
    at = [int(v) for v in found.group(2).split(",")]
    return at[axis] - size[axis] / 2, at[axis] + size[axis] / 2


def solid_part_rows(block: str) -> list[tuple[str, list[int], list[int]]]:
    """가드·참조·포락선을 뺀 실물 부품만 (tag, size, at) 으로 돌려준다.

    가드는 셀 경계 자체이고 참조 외형('guard' 종류)은 인접 셀 설비를 점선으로 그린 것이라,
    "가드가 장비에서 얼마나 떨어져 있나"를 잴 때 둘 다 장비로 세면 답이 0 이 된다.
    """
    rows = []
    for line in block.splitlines():
        if "'sweep'" in line or "'guard'" in line:
            continue
        found = re.search(r"part\('([^']*)', '[^']*', \[([-\d, ]+)\], \[([-\d, ]+)\]", line)
        if found:
            rows.append((found.group(1),
                         [int(v) for v in found.group(2).split(",")],
                         [int(v) for v in found.group(3).split(",")]))
    return rows


def catalog_size(html: str, part_number: str) -> list[int]:
    """부품 카탈로그 한 줄의 외형 (L, W, H)."""
    found = re.search(r'\["%s","[^"]*","[^"]*","[^"]*",\[(\d+),(\d+),(\d+)\]' % re.escape(part_number), html)
    if found is None:
        raise AssertionError(f"{part_number} 를 카탈로그에서 못 찾았다")
    return [int(v) for v in found.groups()]


def part_rows(block: str) -> list[tuple[list[int], list[int]]]:
    """한 셀 블록에서 (size, at) 목록을 뽑는다. 회전포락선은 형상이 아니라 제외한다."""
    rows = []
    for line in block.splitlines():
        if "'sweep'" in line:
            continue
        found = re.search(r"part\('[^']*', '[^']*', \[([-\d, ]+)\], \[([-\d, ]+)\]", line)
        if found:
            rows.append(([int(v) for v in found.group(1).split(",")],
                         [int(v) for v in found.group(2).split(",")]))
    return rows


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
        self.assertEqual((current, reduced), (7, 4))
        self.assertIn("영상 헤드 7 → 4", self.html)

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


class TestInfeedHandoff(unittest.TestCase):
    """스택 → 반전카세트 투입 경로가 도면에 실제로 그려져 있는지.

    REV.22-P01 이전에는 3D 모델에만 있던 분리헤드·셔틀·승강캐리지·포획빔이 도면
    부품표에는 없었다. 그래서 "패널이 어떻게 반전기에 들어가는가"를 도면만 보고는
    알 수 없었다. 좌표는 3D 모델 실측값에서 왔으므로 두 문서가 같은 기계를 가리킨다.
    """

    #: 투입 체인 부품과 3D 실측 (size, at). afu 는 월드 X + 15,400, bfc 는 월드 X + 14,800·Z + 1,600.
    AFU_CHAIN = {
        "SEP-A": ([2180, 80, 120], [-1250, 2060, -1900]),
        "SEP-B": ([2180, 80, 120], [-1250, 2060, 1900]),
        "CAR-A": ([2720, 100, 1220], [-1250, 1760, -1900]),
        "CAR-B": ([2720, 100, 1220], [-1250, 1760, 1900]),
        "SHT-A": ([2280, 80, 1410], [-325, 1640, -1750]),
        "SHT-B": ([2280, 80, 1410], [-325, 1640, 1750]),
        "CD-A": ([4460, 60, 1540], [-325, 2020, -1600]),
        "CD-B": ([4460, 60, 1540], [-325, 2020, 1600]),
    }

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)

    def test_afu_carries_the_measured_handoff_chain(self):
        block = self.stations["afu"]
        for tag, (size, at) in self.AFU_CHAIN.items():
            with self.subTest(part=tag):
                found = re.search(
                    r"part\('%s', '[^']*', \[([-\d, ]+)\], \[([-\d, ]+)\]" % re.escape(tag), block)
                self.assertIsNotNone(found, f"{tag} 가 AFU 부품표에 없다 — 투입 경로가 도면에서 끊긴다")
                self.assertEqual([int(v) for v in found.group(1).split(",")], size)
                self.assertEqual([int(v) for v in found.group(2).split(",")], at)

    def test_flip_cassette_is_detailed_not_massing(self):
        """반전카세트가 일반 매싱 상자가 아니라 실물 부품으로 전개돼 있는지."""
        block = self.stations["bfc"]
        tags = set(re.findall(r"part\('([^']+)'", block))
        for tag in ("SEP", "CAR", "SHT", "RNG-L", "RNG-R", "BGD", "CLP-U", "CLP-L", "CDR"):
            self.assertIn(tag, tags, f"{tag} 가 BFC 조립도에 없다")
        for tag in ("VC-1", "VC-2", "VC-3", "VC-4"):
            self.assertIn(tag, tags, "진공 4구역 컵이 없다 — 겹장검출 구역이 도면에 안 보인다")
        for index in range(1, 5):
            self.assertIn(f"CD-{index}", tags, "포획빔 4열이 다 그려져 있지 않다")
            self.assertIn(f"PAD-{index}", tags, "4점 클램프 패드가 다 그려져 있지 않다")
        self.assertGreaterEqual(len(tags), 25, "반전카세트 부품 수가 상세설계 수준이 아니다")

    def test_end_ring_matches_the_3d_torus(self):
        """엔드링 ⌀1,980 · 튜브 180 — 3D 장면의 TorusGeometry(0.9, 0.09) 와 같은 물건인지."""
        block = self.stations["bfc"]
        for tag in ("RNG-L", "RNG-R"):
            found = re.search(
                r"part\('%s', '[^']*', \[([-\d, ]+)\][^\n]*'ring'\)" % tag, block)
            self.assertIsNotNone(found, f"{tag} 가 ring 으로 그려져 있지 않다")
            self.assertEqual([int(v) for v in found.group(1).split(",")], [180, 1980, 1980])

    def test_key_heights_agree_across_the_two_sheets(self):
        """AFU GA 와 BFC 조립도가 같은 레벨을 쓰는지 — 3D 의 Gt=1,880 · At=3,300 · li=2,100."""
        for key in ("afu", "bfc"):
            block = self.stations[key]
            for level in ("PICK 1,880", "HANDOFF 2,100", "SHUTTLE 1,640"):
                with self.subTest(station=key, level=level):
                    self.assertIn(level, block)
            self.assertRegex(block, r"\[3300, '(FLIP )?AXIS 3,300'\]")
        bfc = self.stations["bfc"]
        # 셔틀 1,640 · 캐리지 1,760 · 분리헤드 2,060 · 포획빔 2,020 은 3D 의 Gt 오프셋에서 온다.
        for tag, height in (("SHT", 1640), ("CAR", 1760), ("SEP", 2060), ("CD-1", 2020)):
            found = re.search(r"part\('%s', '[^']*', \[[-\d, ]+\], \[-?\d+, (-?\d+)," % re.escape(tag), bfc)
            self.assertIsNotNone(found, f"{tag} 를 못 찾았다")
            self.assertEqual(int(found.group(1)), height, f"{tag} 높이가 3D 실측과 다르다")

    def test_every_sheet_with_a_sequence_numbers_it_in_order(self):
        for key, block in self.stations.items():
            marks = re.findall(r"step\('(\d+)'", block)
            if not marks:
                continue
            with self.subTest(station=key):
                self.assertEqual(marks, [str(i + 1) for i in range(len(marks))],
                                 "투입 시퀀스 번호가 1부터 이어지지 않는다")

    def test_sequence_endpoints_stay_inside_the_cell(self):
        """시퀀스 화살표가 부품 바운딩박스 밖으로 나가면 뷰 프레임을 넘는다."""
        for key, block in self.stations.items():
            steps = re.findall(r"step\('\d+', '[^']*', \[([-\d, ]+)\], \[([-\d, ]+)\]", block)
            if not steps:
                continue
            rows = part_rows(block)
            box = [
                (min(at[a] - size[a] / 2 for size, at in rows),
                 max(at[a] + size[a] / 2 for size, at in rows))
                for a in range(3)
            ]
            for from_text, to_text in steps:
                for point_text in (from_text, to_text):
                    point = [int(v) for v in point_text.split(",")]
                    for a, name in enumerate("XYZ"):
                        with self.subTest(station=key, axis=name, point=point_text):
                            self.assertGreaterEqual(point[a], box[a][0] - 1)
                            self.assertLessEqual(point[a], box[a][1] + 1)

    def test_both_sheets_explain_the_same_six_steps(self):
        afu = re.findall(r"step\('\d+', '([^']*)'", self.stations["afu"])
        bfc = re.findall(r"step\('\d+', '([^']*)'", self.stations["bfc"])
        self.assertEqual(len(afu), 6)
        self.assertEqual(len(bfc), 6)
        for index, (left, right) in enumerate(zip(afu, bfc), start=1):
            with self.subTest(step=index):
                # 표현은 시트마다 달라도 되지만 같은 동작이어야 한다 — 핵심어로 대조한다.
                key = ("370", "전개", "1,874", "1,420", "180°", "1,200")[index - 1]
                self.assertIn(key, left)
                self.assertIn(key, right)

    def test_capture_beam_is_a_safety_channel(self):
        """포획빔은 낙하 포획이라 안전 색으로 구분돼야 한다."""
        for key in ("afu", "bfc"):
            for line in self.stations[key].splitlines():
                if re.search(r"part\('CD-[A-B1-4]'", line):
                    with self.subTest(station=key, line=line.strip()[:40]):
                        self.assertIn("'safety'", line)


class TestForkliftWheels(unittest.TestCase):
    """지게차 바퀴가 실제 이동거리로 구르는지.

    REV.22-P01 이전에는 `rotation.z = f*18 - g*18` 이었다. 바퀴 실린더는 이미
    `[Math.PI/2, 0, 0]` 로 눕혀 놓았으므로 그 위에 z 를 돌리면 축이 어긋나 흔들리고,
    18 이라는 계수도 이동거리와 아무 관계가 없었다. 접지점도 30 mm 떠 있었다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_wheel_radius_and_start_are_named_constants(self):
        self.assertIn("var Tp=[],Fwr=.27,Fwx0=-23.2;", self.html)

    def test_wheel_sits_on_the_floor(self):
        """바퀴 중심 높이가 반지름과 같아야 접지한다 — 굴러가는데 떠 있으면 안 된다."""
        self.assertIn("Ee(jt,Fwr,.18,[i,Fwr,e],M.rubber,null,null,[Math.PI/2,0,0])", self.html)

    def test_roll_comes_from_travel_not_a_magic_factor(self):
        self.assertIn("let x=-(_-Fwx0)/Fwr;Tp.forEach(W=>{W.rotation.y=x})", self.html)
        self.assertNotIn("f*18-g*18", self.html)
        self.assertNotIn("W.rotation.z=x", self.html)

    def test_roll_axis_is_the_cylinder_axis(self):
        """실린더는 로컬 Y 가 축이고 pre-rotation 이 X 라, 구름은 rotation.y 여야 한다."""
        self.assertNotRegex(self.html, r"Tp\.forEach\(W=>\{W\.rotation\.[xz]=")


class TestLineLengthReduction(unittest.TestCase):
    """REV.22-P01 장비 단축과, 그 과정에서 나온 버퍼 결함 수정이 유지되는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)

    def test_afr_has_no_dedicated_infeed_conveyor(self):
        """B안 — 셀마다 투입 컨베이어를 따로 두지 않는다.

        AFR 이 자기 투입롤러(3,700)를 갖고 있어서 JBR 출구 롤러와 합쳐 2,500 짜리 패널
        한 장을 넘기는 데 롤러가 5,325 mm 였다. 지금은 JBR 롤러 끝과 AFR 베드를 공용
        인계롤러로 직결하고, AFR 시트에는 가드를 통과하는 참조 구간만 남는다.
        """
        block = self.stations["afr"]
        solid = {tag for tag, _, _ in solid_part_rows(block)}
        self.assertNotIn("CV-101", solid, "AFR 이 아직 자기 투입롤러를 갖고 있다")
        self.assertIn("CV-JA", block, "공용 인계롤러 참조 구간이 도면에 없다")
        for line in block.splitlines():
            if "part('CV-JA'" in line:
                self.assertIn("'guard'", line, "공용 인계롤러는 참조(점선)로 그려야 한다")
        # 카탈로그도 같이 따라와야 한다 — 실물이 아직 3,700 이면 도면만 줄인 셈이다.
        self.assertEqual(catalog_size(self.html, "AFR-CV-101")[0], 1800)
        self.assertIn('["AFR-CV-101","JBR·AFR 공용"', self.html)

    def test_frame_bin_is_transverse(self):
        """A안 — 회수함 장축을 라인 직각으로 돌려 길이를 폭과 바꾼다."""
        size = catalog_size(self.html, "AFR-FH-501")
        self.assertLess(size[0], size[1], "회수함이 아직 라인 방향으로 길다")
        lo, hi = part_span(self.stations["afr"], "FH-501")
        self.assertEqual(hi - lo, size[0], "도면 부품과 카탈로그 외형이 다르다")
        depth_lo, depth_hi = part_span(self.stations["afr"], "FH-501", axis=2)
        self.assertEqual(depth_hi - depth_lo, size[1])
        # 통로측 횡인출 1,200 MIN — 가드까지의 Z 여유가 그만큼 나와야 한다.
        guard_lo, guard_hi = part_span(self.stations["afr"], "GUARD", axis=2)
        self.assertGreaterEqual(depth_lo - guard_lo, 1200)
        self.assertGreaterEqual(guard_hi - depth_hi, 1200)

    def test_afr_guard_clearance_is_equal_on_both_sides(self):
        """가드가 ±5,750 대칭인데 장비가 비대칭이라 하류에만 1,450 이 비어 있었다."""
        block = self.stations["afr"]
        guard = part_span(block, "GUARD")
        rows = solid_part_rows(block)
        hardware_lo = min(at[0] - size[0] / 2 for _, size, at in rows)
        hardware_hi = max(at[0] + size[0] / 2 for _, size, at in rows)
        upstream = hardware_lo - guard[0]
        downstream = guard[1] - hardware_hi
        self.assertEqual(upstream, downstream, "가드 여유가 상·하류에서 다르다")
        self.assertEqual(upstream, 475, "가드 여유가 플랜트 기준(475)과 다르다")

    def test_identical_modules_in_a_row_do_not_collide(self):
        """같은 (높이, 깊이) 자리에 놓인 같은 크기 모듈끼리 X 로 겹치면 물리적으로 불가능하다.

        REV.22 의 GBR 버퍼가 그랬다 — 2,750 모듈을 피치 2,500 으로 놓아 250 mm 겹쳤다.
        """
        for key, block in self.stations.items():
            groups: dict[tuple, list[tuple[float, float]]] = {}
            for size, at in part_rows(block):
                groups.setdefault((tuple(size), at[1], at[2]), []).append(
                    (at[0] - size[0] / 2, at[0] + size[0] / 2))
            for signature, spans in groups.items():
                spans.sort()
                for left, right in zip(spans, spans[1:]):
                    with self.subTest(station=key, size=signature[0]):
                        self.assertLessEqual(
                            left[1], right[0],
                            f"{key} 의 같은 열 모듈이 X 로 {left[1] - right[0]:.0f} mm 겹친다")

    def test_buffer_guard_encloses_the_carriage_bank(self):
        """가드가 캐리지 뒤끝보다 앞에서 끝나면 위험원을 감싸지 못한다."""
        block = self.stations["buffer"]
        guard = part_span(block, "GUARD")
        for tag in ("A-501A", "A-501B", "B-501A", "B-501B", "HOLD"):
            lo, hi = part_span(block, tag)
            with self.subTest(part=tag):
                self.assertLessEqual(guard[0], lo, "가드가 캐리지 앞끝을 못 덮는다")
                self.assertGreaterEqual(guard[1], hi, "가드가 캐리지 뒤끝을 못 덮는다")

    def test_plant_length_label_is_derived_not_typed(self):
        """전체 치수 라벨을 손으로 적어두면 낡는다 — REV.22 에 49,000 이 남아 있었다."""
        self.assertIn("layoutFocusAll.textContent = '전체 ' + n(PLANT_X)", self.html)
        self.assertNotIn("전체 49,000", self.html)


class TestCarriageLoader(unittest.TestCase):
    """캐리지 슬롯 적재기 — 3안 독립 설계·2렌즈 적대 심사의 조합 권고안이 유지되는지.

    골격은 데크-도크 순틈(X 100…325) 트윈마스트 + 2단 텔레스코픽 콤포크이고,
    심사 지적 4건(픽업 후퇴·선단받이·기계 동기·제어반 위치)이 반영돼 있어야 한다.
    """

    ROWS = {"A": -2350, "H": 0, "B": 2350}

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)
        cls.buffer = cls.stations["buffer"]

    def test_every_row_has_the_full_loader_set(self):
        tags = set(re.findall(r"part\('([^']+)'", self.buffer))
        for row in self.ROWS:
            for prefix in ("MSO", "MSI", "TIE", "LFO", "LFI", "FKO", "FKI", "TGO", "TGI"):
                self.assertIn(f"{prefix}-{row}", tags, f"{prefix}-{row} 적재기 부품이 없다")
        for shared in ("CTL-L", "SCN-L", "SCN-R"):
            self.assertIn(shared, tags)

    def test_masts_stand_in_the_deck_dock_gap(self):
        """마스트가 순틈 225(X 100…325) 안에만 서야 셀이 안 커지고 교환로가 산다."""
        for row in self.ROWS:
            for tag in (f"MSO-{row}", f"MSI-{row}"):
                lo, hi = part_span(self.buffer, tag)
                with self.subTest(part=tag):
                    self.assertGreaterEqual(lo, 100)
                    self.assertLessEqual(hi, 325)

    def test_tie_beam_stays_under_the_guard_ceiling(self):
        for row in self.ROWS:
            found = re.search(r"part\('TIE-%s', '[^']*', \[160, 120, 2200\], \[205, (\d+)," % row, self.buffer)
            self.assertIsNotNone(found, f"TIE-{row} 를 못 찾았다")
            self.assertLessEqual(int(found.group(1)) + 60, 2800, "타이빔이 가드 천장을 뚫는다")

    def test_pickup_clears_the_sensor_pack(self):
        """심사 지적 1: 픽업 중심 X −1,500 → 패널(−2,750…−250)이 센서팩(−240…) 앞에서 끝난다."""
        fork_lo, fork_hi = part_span(self.buffer, "FKO-A")
        pickup_center = (fork_lo + fork_hi) / 2
        self.assertEqual(pickup_center, -1500)
        sensor_lo, _ = part_span(self.buffer, "SENSOR")
        self.assertLess(pickup_center + 1250, sensor_lo, "픽업 패널이 센서팩과 겹친다")

    def test_fork_stroke_fits_a_two_stage_telescope(self):
        """도크 중심 1,700 까지 3,200 — 수납 2,600 의 1.6배 안이어야 2단으로 성립한다."""
        fork_lo, fork_hi = part_span(self.buffer, "FKI-B")
        length = fork_hi - fork_lo
        stroke = 1700 - (fork_lo + fork_hi) / 2
        self.assertLessEqual(stroke, 1.6 * length, "2단 텔레스코픽 범위를 넘는 스트로크다")

    def test_fork_lanes_clear_the_slot_rails(self):
        """포크(z 행중심 ±620±60)와 슬롯 레일 내측(±702.5)의 z 분리 — 관문 값 22.5."""
        for row, center in self.ROWS.items():
            for tag, sign in ((f"FKO-{row}", -1), (f"FKI-{row}", 1)):
                z_lo, z_hi = part_span(self.buffer, tag, axis=2)
                edge = max(abs(z_lo - center), abs(z_hi - center))
                with self.subTest(part=tag):
                    self.assertLessEqual(edge, 702.5 - 20, "포크가 슬롯 레일 공간을 침범한다")

    def test_tip_guides_ride_with_the_carriage(self):
        """심사 지적 2: 선단받이 레일은 캐리지 X 구간 안(볼트온)이어야 교환을 막지 않는다."""
        dock_lo, dock_hi = part_span(self.buffer, "A-501A")
        for row in self.ROWS:
            lo, hi = part_span(self.buffer, f"TGO-{row}")
            with self.subTest(row=row):
                self.assertGreaterEqual(lo, dock_lo)
                self.assertLessEqual(hi, dock_hi)

    def test_control_cabinet_is_out_of_the_exchange_corridor(self):
        """심사 지적 4: 제어반은 교환 회랑(X ≥ 325)이 아니라 틈 스트립에 있어야 한다."""
        lo, hi = part_span(self.buffer, "CTL-L")
        self.assertLessEqual(hi, 325, "제어반이 캐리지 교환 회랑 바닥에 서 있다")

    def test_catalog_matches_the_sheet(self):
        self.assertEqual(catalog_size(self.html, "AFR-TF-810"), [2600, 120, 95])
        self.assertEqual(catalog_size(self.html, "AFR-ML-811"), [170, 2770, 2200])
        self.assertEqual(catalog_size(self.html, "AFR-TG-813"), [60, 50, 2100])
        fork_lo, fork_hi = part_span(self.buffer, "FKO-A")
        self.assertEqual(fork_hi - fork_lo, catalog_size(self.html, "AFR-TF-810")[0])

    def test_loader_appears_in_the_3d_scene(self):
        """카탈로그 sceneLabels 와 3D 메시가 같은 라벨을 써야 목록↔화면이 맞는다."""
        for label in ("AFR ML-811 적재기 트윈마스트", "AFR TF-810 텔레스코픽 콤포크"):
            with self.subTest(label=label):
                self.assertGreaterEqual(self.html.count(label), 2, f"{label} 가 3D 장면에 없다")

    def test_loading_animation_is_staged_not_diagonal(self):
        """3D 영상에서 적재가 분기→승강→삽입 순서로 나뉘어야 한다 — 대각선 비행 금지."""
        self.assertIn("le(Ri,r.x,Gz)", self.html)
        self.assertIn("le(1.145,r.y,Gw)", self.html)
        self.assertIn("le(0,r.z,Gq)", self.html)
        self.assertNotIn("Ds.position.set(W,le(1.145,r.y,X),le(0,r.z,X))", self.html)


class TestProcessSequences(unittest.TestCase):
    """정션박스 제거·프레임 분리·반출 과정이 도면에서 읽히는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)

    def test_jbr_explains_the_jbox_removal(self):
        steps = re.findall(r"step\('\d+', '([^']*)'", self.stations["jbr"])
        self.assertEqual(len(steps), 7)
        text = " ".join(steps)
        for key in ("브리지", "박리", "포획", "수거함", "반출"):
            self.assertIn(key, text, f"JBOX 제거 시퀀스에 '{key}' 단계가 없다")
        self.assertIn("part('BIN'", self.stations["jbr"], "정션박스 수거함이 도면에 없다")

    def test_afr_explains_the_frame_separation(self):
        steps = re.findall(r"step\('\d+', '([^']*)'", self.stations["afr"])
        self.assertEqual(len(steps), 6)
        text = " ".join(steps)
        for key in ("클램프", "단축", "장축", "회수함", "반출"):
            self.assertIn(key, text, f"프레임 분리 시퀀스에 '{key}' 단계가 없다")

    def test_afr_discharge_gap_is_bridgeable(self):
        """베드 끝-CV-102 구간은 패널(2,500)보다 짧은 지지 공백만 남아야 한다.

        반출롤러 이전에는 2,950 이 비어 있어 패널이 공중에 뜨는 구간이 있었다.
        검사: 베드·반출롤러가 연속이고, 롤러 끝-셀 하류 가드 끝의 남는 거리가
        패널 길이 미만인지 (post 쪽 CV-102 는 가드 여유 475 에서 바로 시작한다).
        """
        bed_lo, bed_hi = part_span(self.stations["afr"], "BED")
        cv_lo, cv_hi = part_span(self.stations["afr"], "CV-AP")
        self.assertLessEqual(cv_lo, bed_hi, "베드와 반출롤러가 이어지지 않는다")
        guard_lo, guard_hi = part_span(self.stations["afr"], "GUARD")
        # 롤러 끝 → (가드 여유 475) → post 가드 여유 475 → CV-102 시작
        remaining = (guard_hi - cv_hi) + 475
        # 패널이 브리징하려면 공백이 패널 길이보다 짧은 것만으로는 부족하다 —
        # 인계 순간 양단 물림이 최소 300 은 남아야 한다 (2,500 − 300).
        self.assertLessEqual(remaining, 2200, "남는 무지지 구간이 패널 물림 여유를 넘는다")

    def test_discharge_roller_passes_over_the_frame_bin(self):
        """반출롤러(하면)와 회수함(상면)이 겹치면 물리적으로 못 지나간다."""
        found = re.search(r"part\('FH-501', '[^']*', \[\d+, (\d+), \d+\], \[\d+, (\d+),", self.stations["afr"])
        bin_top = int(found.group(2)) + int(found.group(1)) / 2
        found = re.search(r"part\('CV-AP', '[^']*', \[\d+, (\d+), \d+\], \[\d+, (\d+),", self.stations["afr"])
        roller_bottom = int(found.group(2)) - int(found.group(1)) / 2
        self.assertLess(bin_top, roller_bottom, "회수함이 반출롤러를 관통한다")


class TestFlipPortalAndLift(unittest.TestCase):
    """반전카세트 포탈 재배치와 유압 시저 리프트 — 통과 간섭이 되돌아오지 않는지.

    종전 승강기둥·LM가이드는 반전축 선상(z 0)에 서서, 스택에서 반전 중심으로
    셔틀·승강하는 패널(통과대역 z −1,000…+700)을 3D 스윕 실측으로 t 7.5–12.4 s
    동안 관통했다. 포탈 기둥은 그 대역 밖에 서야 한다.
    """

    #: 패널 통과대역 (bfc 로컬 z). 스택 위치 −300±700 과 반전 위치 0±700 의 합집합.
    BAND = (-1000, 700)

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)
        cls.bfc = cls.stations["bfc"]

    def test_portal_columns_stand_outside_the_panel_band(self):
        for tag in ("PLO", "PLI", "PRO", "PRI"):
            z_lo, z_hi = part_span(self.bfc, tag, axis=2)
            with self.subTest(part=tag):
                self.assertTrue(z_hi <= self.BAND[0] or z_lo >= self.BAND[1],
                                f"{tag} 가 패널 통과대역 {self.BAND} 안에 서 있다")

    def test_no_full_height_member_crosses_the_band(self):
        """통과대역 안에 서 있는 전고(全高) 부재가 하나도 없어야 한다 — 일반 불변식."""
        for tag, size, at in solid_part_rows(self.bfc):
            y_lo, y_hi = at[1] - size[1] / 2, at[1] + size[1] / 2
            # 셔틀 높이(1,850…1,910)를 가로지르는 부재만 위험하다
            if not (y_lo < 1850 and y_hi > 1910):
                continue
            z_lo, z_hi = at[2] - size[2] / 2, at[2] + size[2] / 2
            x_lo, x_hi = at[0] - size[0] / 2, at[0] + size[0] / 2
            # 패널 스윕 X: 스택 −1,850±1,250 → 축 0±1,250
            if x_hi < -3100 or x_lo > 1250:
                continue
            with self.subTest(part=tag):
                self.assertTrue(z_hi <= self.BAND[0] or z_lo >= self.BAND[1],
                                f"{tag} 가 셔틀 높이에서 패널 경로를 가로지른다")

    def test_crossbeams_clear_the_clamp_sweep(self):
        """크로스빔은 클램프바 끝(x ±1,430) 밖에서만 하중을 받아야 한다."""
        for tag in ("CB-L", "CB-R"):
            x_lo, x_hi = part_span(self.bfc, tag)
            with self.subTest(part=tag):
                self.assertTrue(x_hi <= -1430 or x_lo >= 1430,
                                f"{tag} 가 회전·클램프 포락선 안에 있다")

    def test_bearing_blocks_sit_on_the_flip_axis(self):
        for tag in ("BB-L", "BB-R"):
            z_lo, z_hi = part_span(self.bfc, tag, axis=2)
            self.assertEqual((z_lo + z_hi) / 2, 0, f"{tag} 가 반전축 위에 있지 않다")

    def test_lift_is_hydraulic_with_a_power_unit(self):
        """리프트가 유압 시저 + HPU-101 로 구현되고 세 문서가 일치하는지."""
        self.assertIn('"30장 팔레트 유압 시저 리프트 A/B"', self.html)
        self.assertIn('["AFU-HPU-101"', self.html)
        self.assertIn("part('LHP', 'HPU-101 리프트 유압유닛'", self.stations["afu"])
        self.assertEqual(
            self.html.count("LFT-101A/B 유압 승강(HPU-101)"), 1,
            "도면 피더 F1 라벨이 유압 승강을 반영해야 한다")
        self.assertIn("유압 승강(HPU-101)", electrical.FEEDERS[0].served)

    def test_lift_hardware_lives_in_the_3d_scene(self):
        for label in ("LFT-101A/B 유압 시저 베이스", "LFT-101A/B 유압 시저 암",
                      "LFT-101A/B 유압 실린더", "LFT HPU-101 유압 파워유닛"):
            with self.subTest(label=label):
                self.assertIn(label, self.html, f"{label} 메시가 3D 장면에 없다")

    def test_deck_scissor_and_cylinder_are_animated_together(self):
        """플랫폼·시저 각·실린더가 같은 데크 높이에서 파생돼야 한다 — 팔레트만 떠오르면 안 된다."""
        self.assertIn("du[K].position.y=Gdy", self.html)
        self.assertIn("ga.rotation.z=ga.userData.gs*Gth", self.html)
        self.assertIn("cp(gc.b,g0,g1)", self.html)

    def test_portal_labels_replace_the_old_posts_in_3d(self):
        self.assertIn("포탈 기둥·LM가이드", self.html)
        self.assertNotIn("벽체형 승강·반전카세트`", self.html.replace("벽체형 수평셔틀", ""))



class TestWiring(unittest.TestCase):
    """배선 길이·분전반 배치(EL-1006~1008)가 wiring.py 와 어긋나지 않는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_cable_length_literal_matches_the_model(self):
        """도면의 CABLE_LENGTH_M 리터럴은 wiring.power_cables() 를 그대로 옮긴 값이어야 한다."""
        found = re.search(r"var CABLE_LENGTH_M = \{([^}]+)\};", self.html)
        self.assertIsNotNone(found, "케이블 길이 리터럴이 도면에 없다")
        drawn = dict(re.findall(r"(F\d): ([\d.]+)", found.group(1)))
        cables = wiring.power_cables()
        self.assertEqual(len(drawn), len(cables))
        for cable in cables:
            with self.subTest(feeder=cable.feeder):
                self.assertAlmostEqual(float(drawn[cable.feeder]), cable.length_m, places=3)

    def test_totals_and_mdb_position_match(self):
        self.assertIn(f"var MDB_X_MM = {wiring.MDB_POSITION_MM[0]},", self.html)
        self.assertIn(f"INCOMING_CABLE_M = {wiring.incoming_cable_m()},", self.html)
        self.assertIn(f"TOTAL_POWER_CABLE_M = {wiring.total_power_cable_m()},", self.html)
        self.assertIn(f"AISLE_CLEAR_MM = {wiring.aisle_clear_width_mm()};", self.html)

    def test_mdb_sits_on_the_demand_center(self):
        """MDB 는 피더 수요 가중 부하중심에서 500 mm 안에 서야 한다 — 케이블 총량의 근거."""
        self.assertLessEqual(abs(wiring.MDB_POSITION_MM[0] - wiring.demand_center_x_mm()), 500)

    def test_aisle_survives_the_wall_mounted_panel(self):
        self.assertGreaterEqual(wiring.aisle_clear_width_mm(), 900)

    def test_every_feeder_panel_has_a_position(self):
        positions = wiring.lp_positions_mm()
        for feeder in electrical.FEEDERS:
            with self.subTest(feeder=feeder.tag):
                self.assertIn(feeder.panel, positions)

    def test_lengths_are_positive_and_plausible(self):
        """맨해튼 경로 하한(수평 |Δx|)보다 짧은 케이블은 물리적으로 불가능하다."""
        for cable in wiring.power_cables():
            lower = abs(wiring.MDB_POSITION_MM[0] - cable.x_mm) / 1000
            with self.subTest(feeder=cable.feeder):
                self.assertGreater(cable.length_m, lower)
                self.assertLess(cable.length_m, lower + 12)

    def test_control_chain_matches_the_drawing(self):
        """EtherCAT 데이지체인 순서가 도면 리터럴과 wiring.control_segments() 에서 같아야 한다."""
        found = re.search(r"var EL_CHAIN = \[([^\]]+)\];", self.html)
        self.assertIsNotNone(found, "EL_CHAIN 리터럴이 도면에 없다")
        drawn = re.findall(r"'([\w-]+)'", found.group(1))
        segments = wiring.control_segments()
        chain = [segments[0].feeder.split("\u2192")[0]] + [row.panel for row in segments]
        self.assertEqual(drawn, chain)

    def test_new_sheets_are_registered_and_selectable(self):
        for sheet in ("PV-PLANT-EL-1006", "PV-PLANT-EL-1007", "PV-PLANT-EL-1008"):
            with self.subTest(sheet=sheet):
                self.assertIn(f"'{sheet}'", self.html, "도면 목록에 등재되지 않았다")
                self.assertIn(f"{sheet} · ", self.html, "표제란이 렌더러에 없다")
        for option in ('value="single"', 'value="mdb"', 'value="system"', 'value="circuit"'):
            with self.subTest(option=option):
                self.assertIn(option, self.html, "전기 도면 셀렉트에 뷰가 빠졌다")

    def test_feeder_table_carries_the_length_column(self):
        self.assertIn("<th>길이 m</th>", self.html)
        self.assertIn("CABLE_LENGTH_M[feeder[0]].toFixed(1)", self.html)
        self.assertIn("TOTAL_POWER_CABLE_M.toFixed(1)", self.html)



class TestServoAxes(unittest.TestCase):
    """서보 축 일람이 servos.py·피더 예산·도면 문구와 어긋나지 않는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def _literal(self, name: str) -> list[tuple]:
        found = re.search(rf"var {name} = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found, f"{name} 리터럴이 도면에 없다")
        rows = re.findall(
            r"\['([\w-]+)', '([\w-]+)', '[^']*', '[^']*', (\d+), ([\d.]+), '[^']*', '[^']*', (true|false)",
            found.group(1))
        return [(tag, panel, int(qty), float(kw), flag == "true")
                for tag, panel, qty, kw, flag in rows]

    def test_literals_match_the_model(self):
        for name, model in (("SERVO_AXES", servos.SERVO_AXES), ("PLANT_MOTORS", servos.MOTORS)):
            drawn = self._literal(name)
            self.assertEqual(len(drawn), len(model), f"{name} 행 수가 다르다")
            for row, axis in zip(drawn, model):
                with self.subTest(axis=axis.tag):
                    self.assertEqual(row[0], axis.tag)
                    self.assertEqual(row[1], axis.panel)
                    self.assertEqual(row[2], axis.qty)
                    self.assertAlmostEqual(row[3], axis.rated_kw, places=3)
                    self.assertEqual(row[4], axis.brake)

    def test_panel_motion_budget_fits_the_feeder(self):
        """분전반별 전동기 정격 합계는 그 피더의 설치 kW 를 넘을 수 없다."""
        installed = {feeder.panel: feeder.installed_kw for feeder in electrical.FEEDERS}
        for panel, kw in servos.motion_kw_by_panel().items():
            with self.subTest(panel=panel):
                self.assertLessEqual(kw, installed[panel],
                                     "전동기 예산이 피더 설치 용량을 넘는다 — 피더부터 다시 세워라")

    def test_axis_counts_match_established_wording(self):
        """총 29축, JBR 7축 — 제어반 문구('EtherCAT 7축 서보')와 배지가 근거."""
        self.assertEqual(servos.servo_axis_count(), 29)
        self.assertEqual(servos.servo_axis_count_for("LP-JBR"), 7)
        self.assertIn("EtherCAT 7축 서보", self.html)
        self.assertIn(f"EtherCAT {servos.servo_axis_count()}축", self.html)

    def test_gravity_axes_carry_brakes(self):
        """승강·반전·박리 축은 브레이크 없이 존재할 수 없다."""
        for axis in servos.SERVO_AXES:
            if any(word in axis.motion for word in ("승강", "반전", "박리")):
                with self.subTest(axis=axis.tag):
                    self.assertTrue(axis.brake, "중력·자세 유지 축에 브레이크가 없다")

    def test_stage_map_only_names_real_axes(self):
        """STAGE_AXES 가 가리키는 축 태그는 전부 일람에 있어야 한다 — 오타는 즉사."""
        found = re.search(r"var STAGE_AXES = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found, "STAGE_AXES 리터럴이 도면에 없다")
        named = set(re.findall(r"'((?:AXIS|MTR)-[\w-]+)'", found.group(1)))
        known = {axis.tag for axis in servos.SERVO_AXES + servos.MOTORS}
        self.assertEqual(named - known, set(), "일람에 없는 축을 강조하려 한다")
        self.assertGreaterEqual(len(named), 10, "매핑이 비어 있으면 라이브 확인이 무의미하다")

    def test_live_monitor_hooks_exist(self):
        for hook in ('id="jb-sv-time"', 'id="jb-sv-active"', 'id="jb-sv-lift"',
                     'id="jb-sv-afr"', 'id="jb-servo-axes-body"', "servoTick: servoTick"):
            with self.subTest(hook=hook):
                self.assertIn(hook, self.html)



class TestAcoustics(unittest.TestCase):
    """소음·진동 예측과 저감 설계가 acoustics.py·부품·도면에 일관되게 반영됐는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)

    def test_noise_literal_matches_the_model(self):
        found = re.search(r"var NOISE_SOURCES = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found, "NOISE_SOURCES 리터럴이 도면에 없다")
        rows = re.findall(r"\['(NS-\w+)', '[^']*', (\d+), ([\d.]+), ([\d.]+),", found.group(1))
        model = acoustics.noise_sources()
        self.assertEqual(len(rows), len(model))
        for row, source in zip(rows, model):
            with self.subTest(source=source.tag):
                self.assertEqual(row[0], source.tag)
                self.assertEqual(int(row[1]), source.x_mm, "음원 위치가 배치 모델과 어긋났다")
                self.assertAlmostEqual(float(row[2]), source.lw_dba, places=1)
                self.assertAlmostEqual(float(row[3]), source.reduction_db, places=1)

    def test_vibration_literal_matches_the_model(self):
        found = re.search(r"var VIBRATION_SOURCES = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found, "VIBRATION_SOURCES 리터럴이 도면에 없다")
        rows = re.findall(r"\['(VS-\w+)', '[^']*', ([\d.]+), ([\d.]+),", found.group(1))
        model = acoustics.vibration_sources()
        self.assertEqual(len(rows), len(model))
        for row, source in zip(rows, model):
            with self.subTest(source=source.tag):
                self.assertEqual(row[0], source.tag)
                self.assertAlmostEqual(float(row[1]), source.freq_hz, places=2)
                self.assertAlmostEqual(float(row[2]), source.fn_hz, places=2)

    def test_summary_constants_match_the_model(self):
        raw_x, raw = acoustics.worst_aisle_dba(mitigated=False)
        mit_x, mit = acoustics.worst_aisle_dba(mitigated=True)
        expected = ("var NOISE_SUMMARY = { "
                    f"nearRaw: {acoustics.worst_near_field_dba(False)}, "
                    f"nearMit: {acoustics.worst_near_field_dba(True)}, "
                    f"aisleRawX: {raw_x}, aisleRaw: {raw}, aisleMitX: {mit_x}, aisleMit: {mit}, "
                    f"nearLimit: {acoustics.NEAR_FIELD_LIMIT_DBA:.0f}, "
                    f"aisleLimit: {acoustics.AISLE_LIMIT_DBA:.0f}, "
                    f"standoffM: {acoustics.AISLE_STANDOFF_M:.0f} }};")
        self.assertIn(expected, self.html, "NOISE_SUMMARY 가 acoustics.py 계산값과 다르다")

    def test_mitigation_is_needed_and_sufficient(self):
        """저감 전은 근접 목표를 넘고(설계의 존재 이유), 저감 후는 두 목표를 다 지킨다."""
        self.assertGreater(acoustics.worst_near_field_dba(False), acoustics.NEAR_FIELD_LIMIT_DBA)
        self.assertLessEqual(acoustics.worst_near_field_dba(True), acoustics.NEAR_FIELD_LIMIT_DBA)
        self.assertLessEqual(acoustics.worst_aisle_dba(True)[1], acoustics.AISLE_LIMIT_DBA)

    def test_isolators_follow_the_third_rule(self):
        """절연 가진원은 fn ≤ f/3 — 전달률 12.5 % 상한."""
        for source in acoustics.vibration_sources():
            with self.subTest(source=source.tag):
                self.assertTrue(acoustics.isolation_ok(source))
                if source.isolated:
                    self.assertLessEqual(
                        acoustics.transmissibility(source.freq_hz, source.fn_hz), 0.125)

    def test_jbr_is_rigid_not_isolated(self):
        """JBR 은 비전 정밀도 때문에 절연하지 않는다 — 실수로 마운트를 달면 잡는다."""
        jbr = next(v for v in acoustics.vibration_sources() if v.tag == "VS-JBR")
        self.assertFalse(jbr.isolated)
        self.assertIn("강성", jbr.note)

    def test_transmissibility_rejects_amplification(self):
        with self.assertRaises(ValueError):
            acoustics.transmissibility(10.0, 8.0)

    def test_mitigation_hardware_exists_everywhere(self):
        """저감 장치는 카탈로그·3D·시트에 실물로 있어야 한다 — 표에만 있으면 장식이다."""
        for tag in ("AFR-ENC-601", "AFR-SIL-601", "AFR-AVM-601", "AFU-AVM-101"):
            with self.subTest(catalog=tag):
                self.assertIn(f'["{tag}"', self.html)
        for label in ("AFR DX-601 흡음 인클로저", "AFR DX-601 배기 소음기",
                      "HPU-601 방진 마운트", "HPU-101 방진 마운트"):
            with self.subTest(scene=label):
                self.assertGreaterEqual(self.html.count(label), 2, f"{label} 3D 메시가 없다")
        # 시트 부품이 라벨 문자열을 공유하므로, 3D 쪽은 실제 메시 호출로 못박는다.
        self.assertIn('M.rubber,"HPU-101 방진 마운트"', self.html)
        self.assertIn('M.rubber,"HPU-601 방진 마운트"', self.html)
        self.assertIn('M.guard,"AFR DX-601 흡음 인클로저"', self.html)
        self.assertIn("part('ENC', 'DX 흡음 인클로저'", self.stations["post"])
        self.assertIn("part('SIL', 'DX 배기 소음기'", self.stations["post"])
        self.assertIn("part('ACL', '연마구간 가드 흡음 라이닝'", self.stations["post"])
        self.assertIn("part('HPM-6', 'HPU-601 방진 마운트'", self.stations["afr"])
        self.assertIn("part('HPM-1', 'HPU-101 방진 마운트'", self.stations["afu"])
        self.assertIn("'PV-PLANT-NV-1009'", self.html, "검토서가 도면 목록에 없다")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
