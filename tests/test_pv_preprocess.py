"""전처리 플랜트 배치도가 배치 모델과 어긋나지 않는지 검증.

`docs/drawings/pv-preprocess-plant.html` 는 셀 외형·존 배치를 자바스크립트 리터럴로
들고 있다. `pv_preprocess.layout` 을 고치고 도면을 갱신하지 않으면 (또는 그 반대면)
두 문서가 서로 다른 공장을 가리키게 되므로, 값이 일치하는지 확인한다.

REV.21 에서 실제로 깨져 있던 두 가지 — 존이 자기 장비보다 짧은 것, 통로가 장비에
덮이는 것 — 은 아래 불변식 테스트로 다시 들어올 수 없게 막는다.
"""

import io
import pathlib
import re
import unittest

from . import _path  # noqa: F401

from pv_preprocess import (acoustics, campaign, electrical, frames, handoff, layout, materials,
                           servos, thermal, vision, wiring)

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

    def test_eight_zones_and_one_gate(self):
        """REV.23 에서 유리제거셀이 존이 되며 7 → 8. gate 만 설비 없는 존이다."""
        self.assertEqual(len(self.zones), 8)
        self.assertEqual([z.key for z in self.zones if z.key not in layout.STATIONS], ["gate"])
        self.assertEqual(self.zones[-1].key, "grm", "유리제거셀이 라인 끝이어야 한다")


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
        # README·코드 주석이 적는 품목 수가 실제와 어긋나면 문서가 거짓말을 한다.
        # REV.23 까지 README 161 · 주석 150 · 실제 149 로 셋이 다 달랐다.
        total = sum(len(rows) for rows in parts.values())
        self.assertEqual(total, 173, "sweep(동작 포락선)은 부품이 아니라 빠진다")
        with io.open("README.md", encoding="utf-8") as handle:
            self.assertIn(f"부품 {total}품목", handle.read())
        self.assertIn(f"현재 {total}품목", self.html)
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
            r"\['(F\d+)', '([\w-]+)', '([^']*)', ([\d.]+), ([\d.]+), (\d+), '([^']*)', '([^']*)'\]", block)
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
        "CAR-A1": ([2720, 100, 140], [-1250, 1760, -2572]),
        "CAR-A2": ([2720, 100, 140], [-1250, 1760, -1228]),
        "CAR-B1": ([2720, 100, 140], [-1250, 1760, 1228]),
        "CAR-B2": ([2720, 100, 140], [-1250, 1760, 2572]),
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
        for tag in ("SEP", "CAR-1", "CAR-2", "SHT", "RNG-L", "RNG-R", "BGD", "CLP-U", "CLP-L", "CDR"):
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
        for tag, height in (("SHT", 1640), ("CAR-1", 1760), ("CAR-2", 1760), ("SEP", 2060), ("CD-1", 2020)):
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
        drawn = dict(re.findall(r"(F\d+): ([\d.]+)", found.group(1)))
        cables = wiring.power_cables()
        self.assertEqual(len(drawn), len(cables))
        for cable in cables:
            with self.subTest(feeder=cable.feeder):
                self.assertAlmostEqual(float(drawn[cable.feeder]), cable.length_m, places=3)

    def test_totals_and_mdb_position_match(self):
        self.assertIn(f"var MDB_X_MM = {wiring.MDB_POSITION_MM[0]},", self.html)
        run = wiring.incoming_cable_m()
        self.assertIn(f"INCOMING_CABLE_M = {0 if run is None else run},", self.html)
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
        """유리제거셀 7축이 더해져 29 → 36축. JBR 7축은 제어반 문구가 근거다."""
        self.assertEqual(servos.servo_axis_count(), 36)
        self.assertEqual(servos.servo_axis_count_for("LP-GRM-MEC"), 7)
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
        rows = re.findall(r"\['(NS-[\w-]+)', '[^']*', (\d+), ([\d.]+), ([\d.]+),", found.group(1))
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



class TestThermal(unittest.TestCase):
    """열수지·냉각 계통이 thermal.py·부품·도면에 일관되게 반영됐는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)

    def test_sources_literal_matches_the_model(self):
        found = re.search(r"var THERMAL_SOURCES = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found, "THERMAL_SOURCES 리터럴이 도면에 없다")
        rows = re.findall(r"\['(TH-[\w-]+)', '[^']*', ([\d.]+), '([^']*)', '[^']*', '([^']*)', ([\d.]+)\]",
                          found.group(1))
        model = thermal.heat_sources()
        self.assertEqual(len(rows), len(model))
        for row, source in zip(rows, model):
            with self.subTest(source=source.tag):
                self.assertEqual(row[0], source.tag)
                self.assertAlmostEqual(float(row[1]), source.loss_kw, places=2)
                self.assertEqual(row[2], source.sink)
                self.assertEqual(row[3], source.cooler_tag)
                self.assertAlmostEqual(float(row[4]), source.cooler_kw, places=2)

    def test_cabinet_literal_matches_the_model(self):
        found = re.search(r"var THERMAL_CABINETS = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found)
        rows = re.findall(r"\['(LP-[\w-]+)', ([\d.]+), '([^']*)'\]", found.group(1))
        loads = thermal.cabinet_loads()
        self.assertEqual(len(rows), len(loads))
        for panel, kw, method in rows:
            with self.subTest(panel=panel):
                self.assertAlmostEqual(float(kw), loads[panel], places=2,
                                       msg="반내 발열이 서보 일람 파생값과 다르다")
                self.assertEqual(method.startswith("열교환기"),
                                 thermal.cabinet_needs_exchanger(panel),
                                 "0.4 kW 규칙과 냉각 방식이 어긋난다")

    def test_summary_matches_the_model(self):
        expected = ("var THERMAL_SUMMARY = { "
                    f"room: {thermal.room_load_kw()}, airflow: {thermal.required_airflow_m3h()}, "
                    f"exhausted: {thermal.exhausted_kw()}, deltaT: {thermal.ROOM_DELTA_T_C:.0f}, "
                    f"hpuLossRatio: {thermal.HPU_LOSS_RATIO}, driveLossRatio: {thermal.DRIVE_LOSS_RATIO}, "
                    f"coolerMargin: {thermal.COOLER_MARGIN} }};")
        self.assertIn(expected, self.html, "THERMAL_SUMMARY 가 thermal.py 계산값과 다르다")

    def test_every_oil_sink_has_a_sized_cooler(self):
        """유압유 발열엔 전용 냉각기가 있어야 하고, 용량은 발열 × 1.25 이상."""
        self.assertTrue(thermal.coolers_are_sized())
        for source in thermal.heat_sources():
            if source.sink == "유압유":
                with self.subTest(source=source.tag):
                    self.assertGreater(source.cooler_kw, 0, "유압유 발열에 냉각기가 없다")
                    self.assertGreaterEqual(source.cooler_kw,
                                            thermal.cooler_required_kw(source.loss_kw))

    def test_hpu_rule_is_thirty_percent(self):
        self.assertAlmostEqual(thermal.hpu_loss_kw(7.5), 2.25)
        self.assertAlmostEqual(thermal.hpu_loss_kw(3.7), 1.11)

    def test_cooling_hardware_exists_everywhere(self):
        for tag in ("AFU-OC-101", "AFR-OC-601"):
            with self.subTest(catalog=tag):
                self.assertIn(f'["{tag}"', self.html)
        self.assertIn('M.steel,"HPU-101 오일쿨러"', self.html, "오일쿨러 3D 메시가 없다")
        self.assertIn('M.steel,"HPU-601 오일쿨러"', self.html, "오일쿨러 3D 메시가 없다")
        self.assertIn("part('OC', 'HPU-101 오일쿨러'", self.stations["afu"])
        self.assertIn("part('OC-6', 'HPU-601 오일쿨러'", self.stations["afr"])
        self.assertIn("'PV-PLANT-TH-1010'", self.html)

    def test_room_load_is_covered_by_ventilation(self):
        """환기량 공식 역산 — 22,500 m³/h 로 ΔT 5 °C 가 실제로 지켜지는지."""
        airflow = thermal.required_airflow_m3h()
        delta_t = thermal.room_load_kw() * 3600.0 / (1.2 * 1.005 * airflow)
        self.assertLessEqual(delta_t, thermal.ROOM_DELTA_T_C)


class TestMaterials(unittest.TestCase):
    """내구 재질 규칙과 적용이 materials.py·카탈로그·도면에 일치하는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_rules_literal_matches_the_model(self):
        found = re.search(r"var MATERIAL_RULES = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found, "MATERIAL_RULES 리터럴이 도면에 없다")
        rows = re.findall(r"\['([^']*)', '([^']*)', '([^']*)', '([^']*)'\]", found.group(1))
        self.assertEqual(len(rows), len(materials.RULES))
        for row, rule in zip(rows, materials.RULES):
            with self.subTest(env=rule.env):
                self.assertEqual(row[0], rule.env)
                self.assertEqual(row[2], rule.material)

    def test_applications_literal_matches_the_model(self):
        found = re.search(r"var MATERIAL_APPLICATIONS = \[(.*?)\n  \];", self.html, re.S)
        self.assertIsNotNone(found)
        rows = re.findall(r"\['([^']*)', '([^']*)', '([^']*)', '([^']*)'\]", found.group(1))
        self.assertEqual(len(rows), len(materials.APPLICATIONS))
        for row, app in zip(rows, materials.APPLICATIONS):
            with self.subTest(part=app.part_no):
                self.assertEqual(row[0], app.part_no)
                self.assertEqual(row[2], app.before)
                self.assertEqual(row[3], app.after)

    def test_applied_materials_reached_the_catalog(self):
        """적용 표가 장식이 되면 안 된다 — 카탈로그 재질 문자열이 실제로 바뀌어야 한다."""
        for part_no, after in materials.applied_materials().items():
            with self.subTest(part=part_no):
                self.assertIn(f'"{after}"', self.html,
                              f"{part_no} 카탈로그 재질이 적용 표와 다르다")
        self.assertNotIn('"슬롯후드/프리세퍼레이터/필터"', self.html,
                         "AFR-DX-601 의 옛 재질이 카탈로그에 남아 있다")

    def test_abrasion_rule_is_grounded(self):
        """유리분 마모 규칙의 근거(Mohs 6–7, STS304 경도 한계)가 지워지면 잡는다."""
        rule = next(r for r in materials.RULES if "고속 접촉면" in r.env)
        self.assertIn("AR400", rule.material)
        self.assertIn("Mohs 6–7", rule.reason)
        self.assertIn("STS304(15–25 HRC)", rule.reason)
        self.assertIn("'PV-PLANT-MT-1011'", self.html)



class TestSceneLighting(unittest.TestCase):
    """3D 장면 색이 테마에 끌려다니지 않는지.

    라이트 테마에서 키라이트 색이 `--foreground`(거의 검정)라 조명이 죽고, 금속·고무가
    `--foreground`/`--border` 파생이라 테마마다 색이 뒤집혔다 — 같은 설비가 폰에서는
    크롬, PC 에서는 검정으로 보였다. 장비 색·조명은 고정, 배경·안개·바닥만 테마를 따른다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_lights_do_not_borrow_theme_text_colors(self):
        """조명 색을 테마 토큰에서 뽑으면 라이트 테마에서 키라이트가 검정이 된다."""
        self.assertNotIn("new Er(F.foreground", self.html, "키라이트가 다시 테마 글자색을 쓴다")
        self.assertNotIn("new vo(F.background,F.muted", self.html, "환경광이 다시 테마색을 쓴다")
        self.assertIn("new Er(SC.key,3.4)", self.html)
        self.assertIn("new vo(SC.sky,SC.ground,1.95)", self.html)
        self.assertIn("new Er(SC.rim,1.05)", self.html, "림라이트가 없으면 금속 윤곽이 죽는다")
        self.assertEqual(self.html.count("new Er(SC.key,"), 2,
                         "메인·부품 미리보기 두 장면 모두 고정 키라이트를 써야 한다")

    def test_scene_palette_is_fixed(self):
        """장면 팔레트는 CSS 토큰이 아니라 고정 리터럴이어야 한다."""
        found = re.search(r"var SC=\{([^}]+)\};", self.html)
        self.assertIsNotNone(found, "장면 팔레트 SC 가 없다")
        body = found.group(1)
        for key in ("key", "fill", "rim", "sky", "ground", "metal",
                    "aluminum", "dark", "rubber", "panel", "jbox", "lampOff"):
            with self.subTest(key=key):
                self.assertRegex(body, rf"{key}:Sc\(\d+,\d+,\d+\)",
                                 f"SC.{key} 가 고정 RGB 가 아니다")

    def test_inverting_materials_now_use_the_fixed_palette(self):
        """테마에 따라 뒤집히던 재질이 전부 고정색으로 바뀌었는지."""
        for pair in ("steel:new Tt({color:SC.metal", "aluminum:new Tt({color:SC.aluminum",
                     "dark:new Tt({color:SC.dark", "rubber:new Tt({color:SC.rubber",
                     "panel:new Tt({color:SC.panel", "jbox:new Tt({color:SC.jbox"):
                with self.subTest(material=pair.split(":")[0]):
                    self.assertIn(pair, self.html)
        for banned in ("rubber:new Tt({color:F.foreground", "jbox:new Tt({color:F.foreground",
                       "steel:new Tt({color:F.metal", "panel:new Tt({color:F.card"):
            with self.subTest(banned=banned.split(":")[0]):
                self.assertNotIn(banned, self.html, "재질이 다시 테마색으로 돌아갔다")
        self.assertNotIn("F.muted)", self.html.split("var M={")[1].split("},wo=[")[0],
                         "소등 램프색이 테마 글자색이면 다크에서 흰색으로 빛난다")

    def test_accent_colors_are_theme_independent(self):
        """강조색도 라이트·다크에서 같은 값이어야 설비 색이 기기마다 안 바뀐다."""
        for token in ("F.teal=Sc(", "F.orange=Sc(", "F.green=Sc(", "F.red=Sc(", "F.yellow=Sc("):
            with self.subTest(token=token):
                self.assertIn(token, self.html)

    def test_background_still_follows_the_theme(self):
        """배경·안개·바닥까지 고정하면 다크 모드에서 흰 배경이 남는다 — 여기는 테마를 따른다."""
        self.assertIn("Dt.setClearColor(F.background,1)", self.html)
        self.assertIn("pt.fog=new qa(F.background,32,72)", self.html)
        self.assertIn('color:F.background,roughness:1', self.html)

    def test_theme_change_resyncs_the_scene_background(self):
        """테마를 바꾸면 3D 배경도 따라와야 한다 — 로드 시점 값에 고정돼 있었다."""
        self.assertIn('function Bth()', self.html)
        self.assertIn('let i=qn("--background");Dt.setClearColor(i,1)', self.html)
        self.assertIn('new MutationObserver(Bth).observe(document.documentElement', self.html)
        self.assertIn('matchMedia("(prefers-color-scheme: dark)").addEventListener("change",Bth)', self.html)



class TestViewNavigation(unittest.TestCase):
    """3D 화면을 마우스·터치로 자유롭게 옮길 수 있는지.

    팬 클램프가 cursor(-7,1.1,0) 중심 반경 28 이라 플랜트 우측 끝(월드 x≈+25.7,
    GBR 버퍼)에 아예 닿지 못했다 — 최대 도달이 +21 이었다. 전장 44.75 m 를
    양 끝까지 훑을 수 있어야 한다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_pan_clamp_covers_the_whole_plant(self):
        """팬 반경은 클램프 중심에서 플랜트 양 끝까지 닿아야 한다."""
        found = re.search(r'ht\.cursor\?\.set\(([-\d.]+),([-\d.]+),([-\d.]+)\);'
                          r'"maxTargetRadius"in ht&&\(ht\.maxTargetRadius=(\d+)\)', self.html)
        self.assertIsNotNone(found, "팬 클램프 설정을 찾지 못했다")
        cursor_x, radius = float(found.group(1)), float(found.group(4))
        # 월드 좌표 = 플랜트 좌표/1000 − 19.075
        half = layout.plant_envelope_mm()[0] / 1000.0
        left, right = -19.075, half - 19.075
        self.assertLessEqual(abs(left - cursor_x), radius, "좌측 끝에 팬이 닿지 않는다")
        self.assertLessEqual(abs(right - cursor_x), radius, "우측 끝(GBR)에 팬이 닿지 않는다")
        self.assertGreaterEqual(radius, half, "팬 반경이 전장보다 짧다")

    def test_zoom_out_can_frame_the_whole_line(self):
        """전장을 한 화면에 담으려면 최대 거리가 전장보다 넉넉해야 한다."""
        found = re.search(r"ht\.maxDistance=(\d+);", self.html)
        self.assertIsNotNone(found)
        self.assertGreaterEqual(float(found.group(1)), layout.plant_envelope_mm()[0] / 1000.0 * 2,
                                "최대 줌아웃이 전장의 2배에 못 미친다")

    def test_pan_mode_switches_drag_and_one_finger(self):
        """이동 모드는 드래그와 한 손가락을 이동으로 바꿔야 한다."""
        self.assertIn('id="jb-pan-toggle"', self.html)
        self.assertIn("ht.mouseButtons.LEFT=pvPanOn?Yn.PAN:Yn.ROTATE", self.html)
        self.assertIn("ht.touches.ONE=pvPanOn?ri.PAN:ri.ROTATE", self.html)
        self.assertIn("'afrbuffer', '#jb-pan-toggle', 'reset'", self.html,
                      "이동 모드 버튼이 화면 콘솔 행(cameraShortcuts)에 배치되지 않았다")

    def test_keyboard_walk_replaces_discrete_key_pan(self):
        """OrbitControls 의 키 팬은 한 번 누를 때마다 한 칸씩 튄다 — 누르고 있는 동안
        매 프레임 움직이는 보행으로 갈아탔으므로 원래 핸들러는 떼어내야 한다."""
        self.assertIn("Dt.domElement.tabIndex=0", self.html)
        self.assertNotIn("ht.listenToKeyEvents", self.html,
                         "OrbitControls 키 팬을 붙여 두면 방향키가 보행과 이중으로 먹는다")
        self.assertNotIn("ht.keyPanSpeed", self.html, "쓰지 않는 키 팬 속도 설정이 남아 있다")
        for code, action in (("KeyW", "f"), ("KeyS", "b"), ("KeyA", "l"), ("KeyD", "r"),
                             ("KeyQ", "d"), ("KeyE", "u"),
                             ("ArrowUp", "f"), ("ArrowDown", "b"),
                             ("ArrowLeft", "l"), ("ArrowRight", "r")):
            with self.subTest(code=code):
                self.assertIn(f'{code}:"{action}"', self.html)

    def test_view_angle_reaches_overhead_and_underside(self):
        """0.49π 로 묶여 있어 바로 위에서 내려다보지도, 설비 밑을 올려다보지도 못했다."""
        low = re.search(r"ht\.minPolarAngle=([\d.]+);", self.html)
        high = re.search(r"ht\.maxPolarAngle=Math\.PI\*([\d.]+);", self.html)
        self.assertIsNotNone(low, "최소 극각 설정을 찾지 못했다")
        self.assertIsNotNone(high, "최대 극각 설정을 찾지 못했다")
        self.assertLessEqual(float(low.group(1)), 0.05, "바로 위에서 내려다볼 수 없다")
        self.assertGreaterEqual(float(high.group(1)), 0.9, "설비 밑을 올려다볼 수 없다")

    def test_walk_moves_camera_and_pivot_together(self):
        """회전축만 옮기면 시점이 끌려간다 — 카메라와 축이 같은 변위를 받아야 걷는 느낌이 난다."""
        self.assertIn("hi.position.add(pvFlyD),ht.target.add(pvFlyD)", self.html)

    def test_walk_speed_scales_with_view_distance(self):
        """멀리서는 성큼, 붙어서는 조심스럽게 — 한 속도로 고정하면 둘 중 하나가 못 쓰게 된다."""
        self.assertIn("return Math.min(16,Math.max(.55,e*.42))*i", self.html)
        self.assertIn('pvFlyK.has("fast")?3:1', self.html, "Shift 질주가 없다")
        self.assertIn('pvFlyK.has("slow")?.28:1', self.html, "Alt 미세 이동이 없다")

    def test_walk_and_orbit_share_a_floor(self):
        """바닥 밑으로 꺼지면 지면을 뚫고 나가 아무것도 안 보인다."""
        self.assertIn("let n=hi.position.y+pvFlyD.y;n<-1.6&&(pvFlyD.y+=-1.6-n)", self.html,
                      "보행에 바닥 하한이 없다")
        self.assertIn('ht.addEventListener("change",()=>{hi.position.y<-1.6&&(hi.position.y=-1.6)})',
                      self.html, "회전으로 밑을 파고들 때 하한이 없다")

    def test_walk_keys_stay_out_of_text_entry(self):
        """부품 검색창에 'wasd' 를 치는 동안 화면이 걸어다니면 안 된다."""
        self.assertIn("function pvFlyTyping(i)", self.html)
        self.assertIn('t==="INPUT"||t==="TEXTAREA"||t==="SELECT"||!!(e&&e.isContentEditable)',
                      self.html)
        self.assertIn("if(!pvFlyHot||i.metaKey||i.ctrlKey||pvFlyTyping(i))return", self.html)

    def test_walk_keys_activate_only_over_the_view(self):
        """화면 밖에서는 키가 죽어야 페이지 스크롤·버튼 조작과 싸우지 않는다."""
        self.assertIn('Dt.domElement.addEventListener("pointerenter",()=>pvFlySet(!0))', self.html)
        self.assertIn('Dt.domElement.addEventListener("pointerleave",()=>pvFlySet(!1))', self.html)
        self.assertIn('addEventListener("blur",()=>pvFlyK.clear())', self.html)

    def test_drag_does_not_select_a_part(self):
        """화면을 끌고 손을 떼면 클릭이 따라 나와 엉뚱한 부품이 선택됐다."""
        self.assertIn("function pvPickOk(i)", self.html)
        self.assertIn('Dt.domElement.addEventListener("click",i=>{pvPickOk(i)&&L0(i,!1)})', self.html)
        self.assertNotIn('addEventListener("click",i=>L0(i,!1))', self.html)

    def test_modifier_panning_is_left_to_orbitcontrols(self):
        """OrbitControls 가 Shift·Ctrl 을 반대 동작으로 이미 처리한다 — 직접 바꾸면 뒤집힌다."""
        self.assertNotIn("i.shiftKey?Yn.PAN:Yn.ROTATE", self.html,
                         "Shift 처리를 직접 하면 OrbitControls 규칙과 싸워 회전이 된다")

    def test_controls_are_documented_on_screen(self):
        self.assertIn("pv-v22-move-hint", self.html)
        self.assertIn("Shift+드래그", self.html)
        self.assertIn("두 손가락", self.html)
        self.assertIn("<b>W A S D</b>", self.html, "보행 키가 화면에 안내되지 않는다")
        self.assertIn("<b>Q E</b>", self.html, "승강 키가 화면에 안내되지 않는다")



class TestCampaign(unittest.TestCase):
    """60장 연속 캠페인 — 3분류 판정, 파이프라인 연속 운전, 버퍼 분류."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_bundles_match_the_request(self):
        """1번 번들 유리 깨짐 3장, 2번 2장. 전손은 리젝트 경로를 보이려 각 1장."""
        counts = campaign.bundle_condition_counts()
        self.assertEqual(counts[0]["유리 깨짐"], 3)
        self.assertEqual(counts[1]["유리 깨짐"], 2)
        for bundle, (name, lift, pattern) in zip(counts, campaign.BUNDLE_PATTERNS):
            with self.subTest(bundle=name):
                self.assertEqual(sum(bundle.values()), campaign.PALLET_PANELS)
                self.assertEqual(len(pattern), campaign.PALLET_PANELS)
                self.assertEqual(set(pattern) - set("UDudX"), set())
                self.assertIn("U", pattern)
                self.assertIn("D", pattern)
                self.assertTrue(lift.startswith("LFT-101"))

    def test_three_classes_route_to_three_places(self):
        """전손만 리젝트, 유리 깨짐은 태워서 R-B, 정상은 R-A."""
        for panel in campaign.panels():
            with self.subTest(index=panel.index):
                if panel.condition == "전손":
                    self.assertEqual(panel.action, "투입 리젝트")
                    self.assertEqual(panel.buffer, "—")
                    self.assertEqual(panel.jbr_end, panel.jbr_start, "전손이 병목을 점유했다")
                else:
                    self.assertIn(panel.action, ("반전 투입", "바이패스 투입"))
                    self.assertEqual(panel.buffer,
                                     "R-B" if panel.condition == "유리 깨짐" else "R-A")
                    self.assertGreater(panel.jbr_end, panel.jbr_start)
        self.assertEqual(campaign.buffer_counts(),
                         {"R-A": campaign.condition_counts()["정상"],
                          "R-B": campaign.condition_counts()["유리 깨짐"]})

    def test_cracked_glass_is_processed_exactly_like_a_normal_panel(self):
        """유리 깨짐은 공정을 그대로 탄다 — 버퍼만 갈라진다."""
        spans = {}
        for panel in campaign.panels():
            if panel.condition == "전손":
                continue
            spans.setdefault(panel.condition, set()).add(
                (round(panel.infeed_end - panel.infeed_start, 2),
                 round(panel.jbr_end - panel.jbr_start, 2),
                 round(panel.afr_end - panel.afr_start, 2)))
        self.assertEqual(spans["유리 깨짐"], spans["정상"],
                         "유리 깨짐이 정상품과 다른 시간을 쓴다")

    def test_robot_feeds_the_next_panel_without_waiting_for_jbr(self):
        """로봇팔은 JBR 인계 즉시 다음 장을 투입한다 — 종단 대기가 아니다."""
        rows = [p for p in campaign.panels() if p.condition != "전손"]
        overlaps = 0
        for previous, panel in zip(rows, rows[1:]):
            with self.subTest(index=panel.index):
                self.assertLessEqual(panel.infeed_start, previous.jbr_end,
                                     "앞 장의 JBR 이 끝난 뒤에야 투입하면 연속이 아니다")
            if panel.infeed_start < previous.afr_end:
                overlaps += 1
        self.assertEqual(overlaps, len(rows) - 1, "라인이 겹쳐 돌지 않는다")
        self.assertGreaterEqual(campaign.peak_wip(), 3, "동시 재공이 3장 미만이면 파이프라인이 아니다")

    def test_takt_is_the_bottleneck_not_the_lead_time(self):
        """택트는 병목 JBR 45 s 이고, 1장차 종단 체류는 도면의 124.03 s 와 맞아야 한다."""
        self.assertEqual(campaign.bottleneck(), "JBR-201")
        summary = campaign.summary()
        # 셀 병목은 JBR 이지만, 실제 택트는 "앞 장 스토퍼에 다음 장 투입" 규칙이 정한다.
        self.assertAlmostEqual(summary["takt_s"], campaign.release_takt_s(), delta=1.0)
        self.assertGreater(campaign.release_takt_s(), campaign.JBR_S)
        first = campaign.panels()[0]
        self.assertAlmostEqual(first.afr_end, 124.03, places=2)
        self.assertAlmostEqual(campaign.INFEED_S + campaign.JBR_S + campaign.AFR_S, 124.03, places=2)

    def test_scrap_does_not_cost_a_full_takt(self):
        """전손은 투입부만 쓰고 병목을 비켜간다 — 그래서 택트를 잃지 않는다."""
        for panel in campaign.panels():
            if panel.condition != "전손":
                continue
            with self.subTest(index=panel.index):
                self.assertAlmostEqual(panel.infeed_end - panel.infeed_start,
                                       campaign.INFEED_REJECT_S, places=2)
        self.assertLess(campaign.INFEED_REJECT_S, campaign.JBR_S)

    def test_drawing_literals_match_the_model(self):
        found = re.search(r"var pvCamB=\[(.*?)\],\s*pvCamTakt", self.html, re.S)
        self.assertIsNotNone(found, "캠페인 리터럴이 도면에 없다")
        drawn = re.findall(r'\["([^"]+)","([^"]+)","([UDudX]+)"\]', found.group(1))
        self.assertEqual(len(drawn), len(campaign.BUNDLE_PATTERNS))
        for row, spec in zip(drawn, campaign.BUNDLE_PATTERNS):
            with self.subTest(bundle=spec[0]):
                self.assertEqual(row[0], spec[0])
                self.assertEqual(row[1], spec[1])
                self.assertEqual(row[2], spec[2], "번들 패턴이 campaign.py 와 다르다")
        for token, value in (("pvCamTakt", campaign.release_takt_s()), ("pvCamRejectS", campaign.INFEED_REJECT_S),
                             ("pvCamInfeed", campaign.INFEED_S), ("pvCamPallet", campaign.PALLET_PANELS),
                             ("pvCamCall", campaign.FORKLIFT_CALL_REMAINING)):
            with self.subTest(token=token):
                self.assertIn(f"{token}={value:g}", self.html)
        self.assertIn(f"pvCamAfr={campaign.AFR_S:g}", self.html)

    def test_drawing_schedule_matches_the_model(self):
        """도면의 스케줄 리터럴은 파이프라인 계산 결과 그대로여야 한다."""
        found = re.search(r"var pvCamT=\[(.*?)\];", self.html, re.S)
        self.assertIsNotNone(found, "스케줄 리터럴이 도면에 없다")
        drawn = re.findall(r"\[([-\d.,]+)\]", found.group(1))
        rows = campaign.panels()
        self.assertEqual(len(drawn), len(rows))
        for row, panel in zip(drawn, rows):
            values = [float(v) for v in row.split(",")]
            with self.subTest(index=panel.index):
                self.assertEqual(values, [panel.infeed_start, panel.infeed_end, panel.jbr_start,
                                          panel.jbr_end, panel.afr_start, panel.afr_end])

    def test_first_pallet_is_drained_before_the_second(self):
        """지게차가 두 곳에 넣고, 한 곳이 다 비면 그때 대기 리프트가 받는다."""
        lifts = [p.lift for p in campaign.panels()]
        first, second = campaign.BUNDLE_PATTERNS[0][1], campaign.BUNDLE_PATTERNS[1][1]
        self.assertEqual(lifts[:campaign.PALLET_PANELS], [first] * campaign.PALLET_PANELS)
        self.assertEqual(lifts[campaign.PALLET_PANELS:], [second] * campaign.PALLET_PANELS)
        self.assertEqual(campaign.remaining_after(campaign.PALLET_PANELS),
                         {first: 0, second: campaign.PALLET_PANELS})
        self.assertIn("Rt[0].count>0?0:Rt[1].count>0?1:0", self.html)
        self.assertIn("forkliftCallRemaining:Hl,", self.html)

    def test_forklift_loads_both_then_refills_the_empty_one(self):
        events = campaign.forklift_events()
        initial = [e for e in events if e.kind == "초기 적재"]
        self.assertEqual(len(initial), 2, "처음에 두 곳을 채워야 한다")
        self.assertTrue(all(e.at_s == 0.0 for e in initial))
        for bundle_no, (_, lift, _) in enumerate(campaign.BUNDLE_PATTERNS, start=1):
            mine = [p for p in campaign.panels() if p.bundle == bundle_no]
            swap = next(e for e in events if e.kind == "팔레트 교환" and e.lift == lift)
            call = next(e for e in events if e.kind == "호출" and e.lift == lift)
            with self.subTest(lift=lift):
                self.assertEqual(swap.at_s, mine[-1].infeed_end, "비는 즉시 교환해야 한다")
                self.assertEqual(call.at_s, mine[-1 - campaign.FORKLIFT_CALL_REMAINING].infeed_end)

    def test_campaign_ui_and_scrap_rack_exist(self):
        for hook in ('id="jb-campaign"', 'id="jb-cam-strip"', 'id="jb-cam-pipeline"',
                     'id="jb-cam-timeline"', 'id="jb-cam-buffer"', 'id="jb-cam-takt"',
                     'id="jb-cam-play"', "setCampaignIndex(i,e2)"):
            with self.subTest(hook=hook):
                self.assertIn(hook, self.html)
        self.assertIn("' data-cond=\"' + p.condition + '\"'", self.html,
                      "스트립 칸이 판정을 싣지 않으면 3분류가 색으로 구분되지 않는다")
        for condition in ("정상", "유리 깨짐", "전손"):
            with self.subTest(condition=condition):
                self.assertIn(f'button[data-cond="{condition}"]', self.html)
        # 전손이 나갈 곳이 실제로 있어야 한다
        self.assertIn('["AFU-RJ-101"', self.html)
        self.assertIn("part('RJ-A', '전손 리젝트 랙 A'", self.html)
        self.assertIn('M.frame,e===0?"AFU-RJ-101 전손 리젝트 랙"', self.html)
        self.assertNotIn("파손 리젝트 랙", self.html, "유리 깨짐도 리젝트하는 것처럼 읽힌다")



class TestFrameElasticity(unittest.TestCase):
    """알루미늄 프레임은 탄성체다 — 인발 자유 길이가 길면 항복한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_design_free_length_stays_elastic(self):
        check = frames.check()
        self.assertFalse(check.yields, "설계 자유 길이에서 프레임이 항복한다")
        self.assertTrue(frames.springs_back())
        self.assertLess(check.stress_mpa, frames.YIELD_MPA)

    def test_yield_limit_bounds_the_roller(self):
        """롤러는 접착 전선에서 이 거리 안쪽에 있어야 한다."""
        limit = frames.max_free_length_mm()
        self.assertGreater(limit, frames.DESIGN_FREE_LENGTH_MM, "설계값이 이미 한계를 넘었다")
        self.assertAlmostEqual(frames.stress_mpa(limit), frames.YIELD_MPA, delta=0.5)
        self.assertGreaterEqual(frames.design_margin(), 1.2, "항복까지 여유가 부족하다")

    def test_deflection_grows_with_the_cube(self):
        """자유 길이 2배면 처짐 8배 — 이 비선형이 설계의 핵심이다."""
        base = frames.deflection_mm(200.0)
        self.assertAlmostEqual(frames.deflection_mm(400.0) / base, 8.0, places=2)
        self.assertGreater(frames.stress_mpa(frames.max_free_length_mm() + 50), frames.YIELD_MPA)

    def test_drawing_literal_matches_the_model(self):
        check = frames.check()
        for token, value in (("inertia", frames.second_moment_mm4()), ("force", frames.PEEL_FORCE_N),
                             ("free", frames.DESIGN_FREE_LENGTH_MM), ("deflection", check.deflection_mm),
                             ("stress", check.stress_mpa), ("yieldMpa", frames.YIELD_MPA),
                             ("maxFree", frames.max_free_length_mm()), ("margin", frames.design_margin()),
                             ("exaggeration", frames.DISPLAY_EXAGGERATION),
                             ("displayBow", frames.display_bow_mm())):
            with self.subTest(token=token):
                self.assertIn(f"{token}: {value:g}", self.html)

    def test_frames_bend_in_the_3d_scene(self):
        """세그먼트로 나뉘고 휨이 애니메이션에 실제로 들어가야 한다."""
        self.assertIn("e.userData.bowT=1-Math.pow(z/.6167,2)", self.html, "단축 프레임이 분할되지 않았다")
        self.assertIn("pvBow*V.userData.bowT*4*_*(1-_)", self.html, "단축 휨이 애니메이션에 없다")
        self.assertIn("bw=pvBow*4*ae*(1-ae)", self.html, "장축 휨이 애니메이션에 없다")
        self.assertIn("var pvBow=%s;" % (("%g" % (frames.display_bow_mm() / 1000)).lstrip("0")), self.html)
        self.assertIn("40배 과장", self.html, "과장 배율을 화면에 밝히지 않았다")


class TestContinuousPlayback(unittest.TestCase):
    """60장이 실제로 연속 투입되는지 — 한 장 돌고 멈추면 안 된다."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_release_is_triggered_by_the_jbr_stopper(self):
        """다음 장은 앞 장의 스토퍼·자세교정이 작동할 때 들어간다."""
        self.assertEqual(campaign.release_takt_s(),
                         campaign.INFEED_S + campaign.JBR_STOPPER_OFFSET_S)
        rows = [p for p in campaign.panels() if p.condition != "전손"]
        for previous, panel in zip(rows, rows[1:]):
            stopper = previous.jbr_start + campaign.JBR_STOPPER_OFFSET_S
            with self.subTest(index=panel.index):
                self.assertGreaterEqual(panel.infeed_start + 1e-9, min(stopper, previous.infeed_end),
                                        "앞 장 스토퍼보다 먼저 투입됐다")

    def test_playback_wrap_matches_the_model_takt(self):
        """영상 반복 주기와 계산 택트가 같아야 화면과 숫자가 어긋나지 않는다."""
        self.assertIn(f"pvCamWrap={campaign.release_takt_s():g},", self.html)
        self.assertIn(f"pvCamTakt={campaign.release_takt_s():g},", self.html)
        self.assertAlmostEqual(campaign.summary()["takt_s"], campaign.release_takt_s(), delta=1.0)

    def test_playback_api_exists_and_advances(self):
        for hook in ("startCampaign(i)", "stopCampaign()", "campaignPlayback()",
                     "function pvCamTick()", "function pvCamHalt()"):
            with self.subTest(hook=hook):
                self.assertIn(hook, self.html)
        # 전손은 배출 시간에, 정상품은 스토퍼 시점에 넘어간다
        self.assertIn('e.condition==="전손"?pvCamRejectS:pvCamWrap', self.html)
        # 마지막 장에서 멈춘다
        self.assertIn("pvCamIdx>=i.length?pvCamHalt()", self.html)

    def test_speed_options_allow_watching_sixty_panels(self):
        """60장 × 48 s 라 배속이 없으면 48분을 봐야 한다."""
        for option in ('<option value="4">4×</option>',
                       '<option value="8">8× · 60장 연속용</option>'):
            with self.subTest(option=option):
                self.assertIn(option, self.html)


class TestCarriageClearance(unittest.TestCase):
    """유리면이 위인 패널은 정션박스가 아래로 향한다 — 승강캐리지가 눌러선 안 된다."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.stations = station_blocks(cls.html)

    def test_carriage_rails_sit_under_the_long_frame(self):
        """레일은 유리 밑이 아니라 장변 프레임(패널 반폭 700 − 프레임 27.5) 아래여야 한다."""
        self.assertIn("P(d,[2.72,.1,.14],[0,0,-.672]", self.html)
        self.assertIn("P(d,[2.72,.1,.14],[0,0,.672]", self.html)
        self.assertNotIn("P(d,[2.72,.1,.14],[0,0,-.54]", self.html,
                         "레일이 다시 유리 밑으로 들어가 정션박스를 누른다")

    def test_sheet_shows_twin_rails_not_a_slab(self):
        """시트가 통판이면 정션박스가 지나갈 개구부가 도면에서 보이지 않는다."""
        for tag in ("CAR-A1", "CAR-A2", "CAR-B1", "CAR-B2"):
            with self.subTest(tag=tag):
                self.assertIn(f"part('{tag}'", self.stations["afu"])
        self.assertIn("part('JBOX-C', '정션박스 통과 개구부", self.stations["bfc"])
        self.assertNotIn("part('CAR-A', 'BLR-101A 단장 승강캐리지', [2720, 100, 1220]", self.html)

    def test_opening_clears_the_junction_box(self):
        """레일 사이 개구부가 정션박스 폭(210)보다 넉넉해야 한다."""
        rails = 2 * 672          # 레일 중심 간격
        opening = rails - 140    # 레일 폭 140 을 뺀 순개구
        self.assertGreaterEqual(opening, 210 * 2, "정션박스 통과 여유가 부족하다")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestHandoff(unittest.TestCase):
    """전처리 버퍼 → DG-HK 2400 박리 라인 인계.

    잇는다는 것은 링크를 거는 일이 아니라 경계 조건이 맞는지 따지는 일이다.
    자세는 맞고 치수와 처리율은 안 맞는다 — 그 사실이 도면에 그대로 적혀야 한다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.downstream = (pathlib.Path(__file__).resolve().parents[1]
                          / "docs" / "drawings" / "pv-delam-tandem.html")

    def test_downstream_drawing_is_present_and_self_contained(self):
        """후단 도면이 없으면 인계 링크가 죽는다. 외부 CDN 은 이 저장소 규약상 0건이다."""
        self.assertTrue(self.downstream.is_file(), "후단 박리 도면이 없다")
        text = self.downstream.read_text(encoding="utf-8")
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)

    def test_plant_links_the_buffer_to_the_downstream_line(self):
        self.assertIn('id="jb-handoff"', self.html)
        self.assertIn('href="pv-delam-tandem.html"', self.html,
                      "버퍼에서 후단 라인으로 가는 링크가 없다")

    def test_pose_carries_through_without_a_flipper(self):
        """양쪽 다 유리면 ↓·백시트 ↑ 라 경계에 반전기가 붙지 않는다."""
        self.assertTrue(handoff.pose_matches())
        self.assertEqual(handoff.BUFFER_POSE, handoff.DOWNSTREAM_POSE)
        self.assertIn(f'bufferPose:"{handoff.BUFFER_POSE}"', self.html)

    def test_widened_deck_takes_the_top_end_module(self):
        """데크를 넓혀 전처리 상한 모듈이 그대로 들어간다 — 마지막 불일치가 해소됐다."""
        self.assertEqual(handoff.AS_UPLOADED_MAX_MM, (2400, 1200),
                         "넓히기 전 값이 기록에서 사라지면 안 된다")
        self.assertEqual(handoff.DOWNSTREAM_MAX_MM, handoff.UPSTREAM_MAX_MM,
                         "데크가 전처리 상한과 같아야 상한 모듈이 들어간다")
        self.assertTrue(handoff.fits_downstream(*handoff.UPSTREAM_MAX_MM))
        self.assertEqual(handoff.oversize_mm(), (0.0, 0.0))
        self.assertTrue(handoff.fits_downstream(2400, 1200), "종전 상한도 계속 받는다")
        self.assertFalse(handoff.fits_downstream(1500, 1000), "하한 미만은 여전히 걸러야 한다")
        self.assertFalse(handoff.fits_downstream(2600, 1400), "새 상한을 넘으면 걸러야 한다")

    def test_widening_the_deck_pulls_the_lamp_rating_with_it(self):
        """램프 관이 데크 폭을 가로지르므로 폭을 넓히면 관 정격도 같이 올라간다."""
        # 라인 수는 5단 랙의 수평면 개수라 폭과 무관하다 — 개수는 60 그대로다
        self.assertEqual(handoff.IR_LINES, 6, "상부 1 + 단간 4 + 하부 1")
        self.assertEqual(handoff.LAMP_COUNT, 60, "폭을 넓혀도 램프 '개수'는 안 늘어난다")
        self.assertAlmostEqual(handoff.lamp_kw(1200), handoff.AS_UPLOADED_LAMP_KW, places=4)
        self.assertAlmostEqual(handoff.lamp_kw(1400), 2.9167, places=4)
        self.assertAlmostEqual(handoff.IR_INSTALLED_KW, 175.0, places=1)
        self.assertAlmostEqual(handoff.AS_UPLOADED_IR_KW, 150.0, places=1)
        self.assertAlmostEqual(handoff.LAMP_PITCH_MM, 250.0, places=1,
                               msg="라인당 10등을 2,500 에 펴면 피치가 240 → 250 이 된다")
        # 관 정격을 안 올리면 어떻게 되는지를 값으로 남긴다
        starved = handoff.downstream_rate(lamp_kw_override=handoff.AS_UPLOADED_LAMP_KW)
        self.assertEqual(starved.bottleneck, "IR 열공정")
        self.assertLess(starved.line_per_h, handoff.sheet_glass_per_h(),
                        "관 정격을 안 올리면 유입을 못 받는다")

    def test_downstream_rate_mirrors_the_uploaded_model(self):
        """DG-HK 2400 Rev.10 앱의 계산을 그대로 옮긴 값 — 재유도하지 않았다."""
        u = handoff.as_uploaded_rate()
        self.assertAlmostEqual(u.heat_per_panel_mj, 4.40, places=2)
        self.assertAlmostEqual(u.dwell_s, 225.79, places=2)
        self.assertAlmostEqual(u.release_pitch_s, 45.16, places=2)
        self.assertAlmostEqual(u.tandem_cycle_s, 77.5, places=1)
        self.assertAlmostEqual(u.line_per_h, 46.5, places=1)

    def test_adopted_configuration_is_plan_b(self):
        """버퍼에 실제로 연결된 것은 B안 구성이다 — 열은 그대로, 탠덤만 빨라진다."""
        self.assertEqual(handoff.ADOPTED_PLAN, "B")
        d, u = handoff.downstream_rate(), handoff.as_uploaded_rate()
        self.assertAlmostEqual(d.tandem_cycle_s, 52.7, places=1)
        self.assertAlmostEqual(d.line_per_h, 68.4, places=1)
        self.assertEqual(d.bottleneck, "2단 탠덤 박리")
        # 데크가 넓어진 만큼 장당 열량이 늘었지만 램프도 같이 늘려 체류는 거의 그대로다
        self.assertGreater(d.heat_per_panel_mj, u.heat_per_panel_mj)
        self.assertAlmostEqual(d.dwell_s, u.dwell_s, delta=12.0,
                               msg="램프를 폭에 맞춰 늘렸으므로 체류가 크게 늘면 안 된다")
        self.assertGreater(d.thermal_per_h, d.tandem_per_h,
                           "IR 이 병목이라면 증설 대상이 바뀐다")

    def test_feed_no_longer_outruns_the_adopted_line(self):
        """개선 전에는 유입이 빨라 버퍼가 2.56 h 만에 찼다 — 채택 후에는 차지 않는다."""
        feed = handoff.sheet_glass_per_h()
        self.assertAlmostEqual(feed, 66.0, places=1)
        self.assertGreater(feed, handoff.as_uploaded_rate().line_per_h,
                           "개선 전에는 밀렸다는 사실이 기록으로 남아야 한다")
        self.assertLess(handoff.rate_gap_per_h(), 0, "채택 후에는 여유가 있어야 한다")
        self.assertEqual(handoff.buffer_autonomy_h(), float("inf"))
        # 버퍼의 역할이 '밀린 것 쌓기' 에서 '후단 정지 버티기' 로 바뀐다
        self.assertAlmostEqual(handoff.buffer_ride_through_h(), 0.76, places=2)

    def test_knife_speed_alone_cannot_close_the_gap(self):
        """인계 10 s 를 그대로 두면 필요 칼날이 상한을 넘는다 — 인계 단축이 전제다."""
        need = handoff.knife_speed_for_balance(handoff.AS_UPLOADED_HANDLING_S)
        self.assertAlmostEqual(need, 62.9, places=1)
        self.assertGreater(need, handoff.KNIFE_SPEED_MAX_MM_S,
                           "인계를 그대로 두면 칼날 상한으로도 못 따라간다")
        self.assertFalse(handoff.balances_at_max_knife_speed(handoff.AS_UPLOADED_HANDLING_S))
        at_max = handoff.downstream_rate(knife_speed_mm_s=handoff.KNIFE_SPEED_MAX_MM_S,
                                         handling_s=handoff.AS_UPLOADED_HANDLING_S)
        self.assertLess(at_max.line_per_h, handoff.sheet_glass_per_h())

    def test_adopted_handling_brings_the_required_knife_under_the_limit(self):
        """인계를 6 s 로 줄이면 필요 칼날이 상한 아래로 내려온다 — 그래서 성립한다."""
        need = handoff.knife_speed_for_balance()
        self.assertAlmostEqual(need, 57.7, places=1)
        self.assertLess(need, handoff.KNIFE_SPEED_MAX_MM_S)
        self.assertLessEqual(need, handoff.KNIFE_SPEED_MM_S,
                             "채택한 칼날 속도가 필요치를 이미 넘어서야 한다")
        self.assertTrue(handoff.balances_at_max_knife_speed())

    def test_drawing_literal_matches_the_model(self):
        """도면 리터럴과 모듈이 어긋나면 화면이 거짓말을 한다."""
        d = handoff.downstream_rate()
        at_max = handoff.downstream_rate(
            knife_speed_mm_s=handoff.KNIFE_SPEED_MAX_MM_S).line_per_h
        for token in (f"overL:{handoff.oversize_mm()[0]:g}",
                      f"overW:{handoff.oversize_mm()[1]:g}",
                      f"feed:{handoff.sheet_glass_per_h():g}",
                      f"gap:{handoff.rate_gap_per_h():g}",
                      f"raSlots:{handoff.BUFFER_RA_SLOTS}",
                      "autonomy:Infinity" if handoff.buffer_autonomy_h() == float("inf")
                      else f"autonomy:{handoff.buffer_autonomy_h():g}",
                      f"rideThrough:{handoff.buffer_ride_through_h():g}",
                      f'adopted:"{handoff.ADOPTED_PLAN}"',
                      f"knife:{handoff.KNIFE_SPEED_MM_S:g}",
                      f"handling:{handoff.HANDLING_S:g}",
                      f"loadPanels:{handoff.DOWNSTREAM_LOAD_PANELS}",
                      f"atMax:{at_max:g}",
                      f"knifeNeed:{handoff.knife_speed_for_balance():g}",
                      f"line:{d.line_per_h:g}",
                      f"thermal:{d.thermal_per_h:g}",
                      f"tandemCycle:{d.tandem_cycle_s:g}",
                      f'bottleneck:"{d.bottleneck}"'):
            with self.subTest(token=token):
                self.assertIn(token, self.html)

    def test_panel_never_prints_infinity_to_the_reader(self):
        """자립시간이 무한이 된 뒤로 화면에 'Infinity시간' 이 뜨면 안 된다."""
        self.assertNotIn('#jb-ho-autonomy").textContent=H.autonomy', self.html)
        self.assertIn('#jb-ho-autonomy").textContent=H.rideThrough+"시간"', self.html)
        self.assertIn("후단이 멈춰도 전처리를 <span id=\"jb-ho-autonomy\"></span> 더 돌리는", self.html)

    def test_broken_glass_is_kept_out_of_the_handoff(self):
        """파손 유리는 시트로 못 벗긴다 — 후단에 넣으면 안 된다."""
        self.assertIn("파손 유리(R-B)는 이 인계에 넣지 않는다", self.html)
        self.assertEqual(handoff.sheet_glass_per_h(),
                         round(campaign.summary()["normal"]
                               / campaign.summary()["run_s"] * 3600, 1),
                         "인계 유입은 정상 유리(R-A)만 세어야 한다")


class TestIncomingService(unittest.TestCase):
    """REV.23 인입 확정 — 계약전력에서 수전 방식이 따라 나오는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_contract_power_crosses_the_low_voltage_limit(self):
        """자체 수전을 세운다면 고압이어야 한다 — 부지 인입이 없어졌을 때의 근거."""
        self.assertAlmostEqual(electrical.contract_kw(), 268.2, places=1)
        self.assertGreater(electrical.contract_kw(), electrical.LOW_VOLTAGE_LIMIT_KW)
        self.assertTrue(electrical.needs_high_voltage())
        self.assertEqual(electrical.HV_SUPPLY_VOLTAGE_V, 22_900)
        # 전처리만일 때는 저압이 맞았다 — 그 사실이 기록으로 남아야 한다
        preprocess_only = sum(f.demand_kw for f in electrical.FEEDERS
                              if not f.panel.startswith("LP-GRM"))
        self.assertLess(preprocess_only * electrical.CONTRACT_MARGIN,
                        electrical.LOW_VOLTAGE_LIMIT_KW,
                        "REV.22 까지의 저압 인입은 틀린 게 아니라 전제가 바뀐 것이다")

    def test_plant_taps_the_existing_site_service(self):
        """부지에 1,200 kW 가 이미 있으면 자체 수전설비를 세울 이유가 없다."""
        self.assertEqual(electrical.SITE_SERVICE_KW, 1200.0)
        self.assertTrue(electrical.taps_existing_service())
        self.assertIn("기존 부지 인입", electrical.supply_method())
        self.assertAlmostEqual(electrical.site_utilisation_pct(), 22.4, places=1)
        self.assertAlmostEqual(electrical.site_headroom_kw(), 931.8, places=1)
        # 수용률이 전부 1.0 이 되는 최악에도 들어가야 '여유가 있다'고 말할 수 있다
        self.assertAlmostEqual(electrical.worst_case_kw(), 266.0, places=1)
        self.assertTrue(electrical.fits_site_service())
        self.assertLess(electrical.worst_case_kw() / electrical.SITE_SERVICE_KW, 0.25)
        # 재는 자가 설치(266.0)인지 계약(268.2)인지 — 둘 사이 값에서 갈린다.
        # 부지 계통에 실제로 흐르는 최악은 여유율을 곱한 행정값이 아니다.
        self.assertGreater(electrical.contract_kw(), electrical.worst_case_kw())
        self.assertTrue(electrical.fits_site_service(267.0))
        self.assertFalse(electrical.fits_site_service(265.0))
        # 인입이 있어도 최악이 안 들어가면 자체 수전을 세워야 한다
        self.assertFalse(electrical.taps_existing_service(200.0))
        self.assertFalse(electrical.taps_existing_service(0.0))
        # 세울 큐비클이 없다 — 부지 설비를 쓴다
        self.assertEqual(electrical.substation_cubicles(), ())
        self.assertEqual(electrical.substation_room_mm(), (0, 0, 0))
        self.assertEqual(electrical.incomer_summary()["transformer_kva"], 0)

    def test_low_voltage_tap_is_bounded_by_voltage_drop_not_ampacity(self):
        """저압으로 끌면 거리를 묶는 것은 허용전류가 아니라 전압강하다."""
        self.assertTrue(electrical.TAP_AT_LOW_VOLTAGE)
        self.assertAlmostEqual(electrical.lv_tap_max_length_m(), 162.3, places=1)
        # 굵게 할수록 멀리 가지만 비례하지는 않는다 (리액턴스는 거의 안 줄어든다)
        self.assertLess(electrical.lv_tap_max_length_m(150),
                        electrical.lv_tap_max_length_m(240))
        self.assertLess(electrical.lv_tap_max_length_m(240),
                        electrical.lv_tap_max_length_m(300))
        self.assertAlmostEqual(electrical.lv_tap_max_length_m(300), 188.8, places=1)
        # 허용전류만 보면 240 은 450 A 라 여유가 큰데, 거리는 162 m 에서 끊긴다
        self.assertGreater(electrical.LV_CABLE_AMPACITY_A[240],
                           electrical.main_breaker_at())

    def test_the_tap_distance_is_not_invented(self):
        """부지 배전반까지의 실거리는 발주처 실측이다 — 숫자를 지어내면 안 된다."""
        self.assertIsNone(wiring.SITE_BOARD_TO_MDB_MM)
        self.assertIsNone(wiring.incoming_cable_m())
        self.assertFalse(wiring.incoming_length_is_known())
        self.assertIn("INCOMING_CABLE_M = 0,", self.html)
        self.assertIn("incomingKnown: false", self.html)
        self.assertIn("미확정", self.html, "길이를 모르면 도면도 모른다고 적어야 한다")
        self.assertNotIn("INCOMING_CABLE_M.toFixed(1) + ' m (인입점 x=0 기준)'", self.html)

    def test_transformer_is_sized_from_demand_not_guessed(self):
        """변압기는 목표 부하율과 계약 피상전력 중 큰 쪽이 지배한다."""
        self.assertAlmostEqual(electrical.apparent_demand_kva(), 220.8, places=1)
        self.assertEqual(electrical.transformer_kva(), 300)
        self.assertIn(electrical.transformer_kva(), electrical.TRANSFORMER_RATINGS_KVA)
        self.assertGreaterEqual(electrical.transformer_kva(), electrical.contract_kva())
        self.assertAlmostEqual(electrical.transformer_load_pct(), 73.6, places=1)
        self.assertLessEqual(electrical.transformer_load_pct(),
                             electrical.TRANSFORMER_LOAD_FACTOR * 100,
                             "부하율이 목표를 넘으면 한 단계 큰 용량을 골랐어야 한다")
        # 여기서는 계약 피상전력이 지배한다 — 부하율 기준은 298.1 > 276.0 에 가려진다.
        # 어느 쪽이 정했는지가 바뀌면 설계 근거가 바뀐 것이므로 못 박아 둔다.
        self.assertEqual(electrical.transformer_sizing_basis(), "계약 피상전력")
        self.assertAlmostEqual(electrical.transformer_required_kva(), 298.05, places=1)
        # 계약이 지배하지 않는 지점에서 부하율 기준이 실제로 작동하는지 — 0.80 이
        # 아니면 170 kVA 는 300 이 아니라 200 으로 떨어진다.
        self.assertEqual(electrical.transformer_sizing_basis(apparent_kva=170, contract=0),
                         "목표 부하율")
        self.assertEqual(electrical.transformer_kva(apparent_kva=170, contract=0), 300)
        self.assertEqual(electrical.transformer_kva(apparent_kva=160, contract=0), 200)

    def test_the_main_cable_carries_the_breaker_not_the_demand(self):
        """차단기가 떨어지기 전에 케이블이 타면 보호가 성립하지 않는다."""
        size = electrical.lv_main_cable_mm2()
        self.assertEqual(size, 240)
        self.assertGreaterEqual(electrical.LV_CABLE_AMPACITY_A[size],
                                electrical.main_breaker_at())
        # 종전 인입 규격 35 mm² 는 이 전류를 못 받는다 — 그것이 확정의 이유 중 하나다
        self.assertLess(electrical.LV_CABLE_AMPACITY_A[35], electrical.main_breaker_at())
        self.assertLess(electrical.lv_cable_mm2(100), size, "전류가 작으면 더 얇아야 한다")

    def test_high_voltage_would_move_the_copper_off_the_long_run(self):
        """저압 분기 한계를 넘으면 고압 분기로 간다 — 그때의 근거를 남긴다."""
        self.assertAlmostEqual(electrical.hv_incoming_current_a(), 7.51, places=2)
        self.assertLess(electrical.hv_incoming_current_a(),
                        electrical.demand_current_a() / 40,
                        "같은 전력을 고압으로 나르면 전류가 40배 이상 작아진다")
        self.assertEqual(electrical.transformer_kva(), 300,
                         "고압 분기로 가면 국소 변압기가 이 용량이다")

    def test_power_factor_correction_is_sized(self):
        """0.90 은 한전 기준선이라 감액이 없다 — 0.95 로 올리는 뱅크를 잡아 둔다."""
        kvar = electrical.capacitor_kvar()
        self.assertEqual(kvar, 35)
        self.assertIn(kvar, electrical.CAPACITOR_STEPS_KVAR)
        import math
        need = electrical.demand_kw() * (
            math.tan(math.acos(electrical.BASE_POWER_FACTOR))
            - math.tan(math.acos(electrical.TARGET_POWER_FACTOR)))
        self.assertGreaterEqual(kvar, need)
        self.assertAlmostEqual(need, 30.9, places=1)

    def test_no_electrical_room_is_needed_now(self):
        """부지 저압 배전반에서 따면 세울 반도 방도 없다."""
        self.assertEqual(electrical.substation_room_mm(), (0, 0, 0))
        self.assertNotIn("substation", [z.key for z in layout.build_zones()])
        # 세우게 되는 두 경우의 크기는 그대로 남겨 둔다 — 되돌아갈 근거다
        self.assertEqual(sum(w for w, _ in electrical.SUBSTATION_CUBICLES), 4600)
        self.assertEqual(sum(w for w, _ in electrical.UNIT_SUBSTATION_CUBICLES), 2600,
                         "고압 분기면 계량·주차단이 부지 쪽이라 2면뿐이다")
        self.assertEqual(electrical.SUBSTATION_CUBICLE_DEPTH_MM
                         + electrical.SUBSTATION_FRONT_CLEARANCE_MM
                         + electrical.SUBSTATION_REAR_CLEARANCE_MM, 3600)

    def test_drawing_carries_the_confirmed_incomer(self):
        """도면 인입도가 확정값과 어긋나면 화면이 거짓말을 한다."""
        c = electrical.incomer_summary()
        for token in (f"tapsSite: {'true' if c['taps_site'] else 'false'}",
                      f"tapLowVoltage: {'true' if c['tap_low_voltage'] else 'false'}",
                      f"siteServiceKw: {c['site_service_kw']}",
                      f"siteUtilPct: {c['site_utilisation_pct']}",
                      f"siteHeadroomKw: {c['site_headroom_kw']}",
                      f"worstCaseKw: {c['worst_case_kw']}",
                      f"lvTapMaxM: {c['lv_tap_max_m']}",
                      f"highVoltage: {'true' if c['high_voltage'] else 'false'}",
                      f"hvV: {c['hv_voltage_v']}",
                      f"contractKw: {c['contract_kw']}",
                      f"transformerKva: {c['transformer_kva']}",
                      f"transformerKvaIfHv: {c['unit_transformer_kva']}",
                      f"transformerLoadPct: {c['transformer_load_pct']}",
                      f"capacitorKvar: {c['capacitor_kvar']}",
                      f"hvCurrentA: {c['hv_current_a']}",
                      f"vcbA: {c['vcb_a']}",
                      f"lvMainMm2: {c['lv_main_cable_mm2']}",
                      f"hvCable: '{c['incoming_cable']}'",
                      f"lowVoltageLimitKw: {electrical.LOW_VOLTAGE_LIMIT_KW}"):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        # 종전 저압 인입 문구가 남아 있으면 두 말을 하는 도면이 된다
        self.assertNotIn("인입 4C×35 mm² Cu", self.html)

    def test_single_line_geometry_is_derived_not_pinned(self):
        """계통 6단·피더 12행이 프레임을 넘지 않으려면 간격이 파생값이어야 한다."""
        self.assertNotIn("chainPitch = 40, busTop = 268, feederTop = 312, feederPitch = 52",
                         self.html, "상수로 박으면 행이 늘 때 조용히 넘친다")
        self.assertIn("var busTop = chainTop + (SL_CHAIN_ROWS - 1) * chainPitch + 44;", self.html)
        self.assertIn("Math.min(52, Math.floor((frameBottom - 76 - feederTop)", self.html)

    def test_the_sheet_fits_its_content_instead_of_clipping_it(self):
        """행이 늘면 시트가 커져야 한다 — 상수 프레임은 조용히 잘라낸다.

        REV.24 에서 실제로 났다. 인입 집계가 9 → 14 행이 되며 고정 높이 320 을
        넘어 캡션 위에 겹쳐 찍혔고, F11 의 부하 설명이 프레임 오른쪽으로 692 px
        삐져나갔다. 글자폭을 코드에서 어림해도, 프레임을 상수로 박아도 같은 일이
        반복되므로 **그린 뒤 실측해서 맞추는** 패스를 둔다.
        """
        self.assertIn("function fitElectricalSheet()", self.html)
        self.assertIn("fitElectricalSheet();", self.html, "렌더 후에 호출되지 않으면 없는 것과 같다")
        self.assertIn("id=\"pv-sheet-frame\"", self.html, "프레임을 못 찾으면 키울 수도 없다")
        # 잘라내기 전에 실제 길이를 잰다 — 어림한 글자폭이면 폰트가 바뀔 때 틀린다
        self.assertIn("t.getComputedTextLength() <= max", self.html)
        # 집계 상자 높이가 행 수에서 나오는가
        self.assertIn("h: 62 + sumRows.length * 26 - 6", self.html)
        self.assertNotIn("var box = { x: 40, y: 386, w: 300, h: 320 };", self.html)

    def test_panel_rows_are_packed_not_alternated(self):
        """반이 몰리면 홀짝 2단으로는 못 피한다 — 겹치지 않는 단을 찾아야 한다."""
        self.assertNotIn("rowOf[pair[1]] = rank % 2;", self.html)
        self.assertIn("while (lastX[r] !== undefined && px - lastX[r] < LP_BOX_W + 6) r++;", self.html)
        # GRM 4면은 5 m 안에 몰려 있다 — 2단으로 갈라도 같은 단에 둘이 남는다
        positions = wiring.lp_positions_mm()
        grm = sorted(positions[p] for p in positions if p.startswith("LP-GRM"))
        self.assertEqual(len(grm), 4)
        self.assertLess(grm[-1] - grm[0], 7_000, "네 반이 이렇게 가까우니 단을 파생시켜야 한다")

    def test_every_feeder_panel_has_a_position_in_the_drawing(self):
        """도면의 위치 표에 빠진 반이 있으면 계통 연결도에 NaN 이 그려진다."""
        block = self.html[self.html.index("  function lpPositions() {"):
                          self.html.index("  var EL_CHAIN = [")]
        for feeder in electrical.FEEDERS:
            with self.subTest(panel=feeder.panel):
                self.assertIn(f"'{feeder.panel}'", block)
        # 같은 X 에 두 반을 세우면 라벨이 포개지고 구간 길이가 0 이 된다
        positions = wiring.lp_positions_mm()
        self.assertNotEqual(positions["LP-GRM-IRA"], positions["LP-GRM-IRB"])


class TestGlassRemovalIntegration(unittest.TestCase):
    """REV.23 — 유리제거(박리) 라인이 링크가 아니라 플랜트의 한 존인지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_glass_removal_is_a_plant_zone_not_a_link(self):
        """버퍼가 마지막이면 전처리 플랜트가 유리를 못 벗긴 채 끝난다."""
        zones = layout.build_zones()
        self.assertEqual(zones[-1].key, "grm")
        grm = layout.STATIONS["grm"]
        self.assertEqual(grm.envelope, (14050, 6100, 3600))
        self.assertEqual(grm.sheet, "PV-GRM-401-GA-6101")
        self.assertIn(grm.sheet, self.html, "도면 목록에 GA 시트가 없다")
        # 존은 장비 밴드 안에 들어와야 하고 통로를 잠식하면 안 된다
        self.assertLessEqual(zones[-1].y1_mm, layout.MACHINE_BAND_Y_MM)
        self.assertEqual(layout.plant_envelope_mm()[0], 58800,
                         "44,750(전처리) + 14,050(유리제거) = 58,800")

    def test_the_3d_scene_actually_carries_the_cell(self):
        """도면에만 있고 영상에 없으면 '연결'이 아니다."""
        self.assertIn("var pvGrm=new ce;pt.add(pvGrm);", self.html)
        for tag in ("M0-101", "M1-101", "IR-701", "LI-101", "TS-101", "EX-101",
                    "TDM-201", "HKB-101", "HKS-201", "WR-101", "CB-201", "DS-301"):
            with self.subTest(part=tag):
                self.assertIn(tag, self.html)
        # 바닥이 셀을 못 받치면 장비가 허공에 선다 (월드 x 34.1 까지)
        self.assertIn("new xr(64,18)", self.html, "바닥을 하류로 늘리지 않았다")

    def test_knife_heads_fit_the_300mm_lead(self):
        """칼끝 리드가 300 이면 두 헤드 몸체는 그보다 좁아야 나란히 선다."""
        self.assertIn("'HKB-101 백시트 개방 핫나이프', [260,", self.html)
        self.assertIn("'HKS-201 셀/EVA 분리 핫나이프 (300 리드)', [260,", self.html)

    def test_campaign_now_ends_at_glass_not_at_the_buffer(self):
        """캠페인이 버퍼에서 끝나면 유리가 벗겨졌는지 알 수 없다."""
        rows = handoff.glass_removal_timeline()
        summary = handoff.glass_removal_summary()
        self.assertEqual(len(rows), 53, "R-A 정상 유리만 후단으로 간다")
        self.assertEqual({r.panel_index for r in rows},
                         {p.index for p in campaign.panels() if p.buffer == "R-A"})
        self.assertAlmostEqual(summary["buffer_run_s"], 2890.03, places=1)
        self.assertAlmostEqual(summary["glass_finish_s"], 3344.33, places=1)
        self.assertAlmostEqual(summary["glass_finish_min"], 55.7, places=1)
        self.assertGreater(summary["glass_finish_s"], summary["buffer_run_s"],
                           "유리제거는 버퍼 이후에도 이어진다")
        self.assertAlmostEqual(summary["tail_s"], 454.3, places=1)

    def test_the_cell_never_starves_once_it_starts(self):
        """첫 배치 가열 대기(FULL_LOAD_ACK) 동안 쌓인 재고로 끝까지 물린다."""
        summary = handoff.glass_removal_summary()
        self.assertAlmostEqual(summary["grm_utilisation"], 1.0, places=3)
        rows = handoff.glass_removal_timeline()
        # 데크는 롤링이다 — n 번째는 n−5 번째가 박리로 빠져야 들어간다
        for n in range(handoff.DOWNSTREAM_LOAD_PANELS, len(rows)):
            with self.subTest(sheet=rows[n].order):
                self.assertGreaterEqual(
                    rows[n].load_s, rows[n - handoff.DOWNSTREAM_LOAD_PANELS].peel_start_s,
                    "데크가 비기 전에 다음 장을 실었다")
        # 데크가 빌 때까지 기다리는 것이지 후단이 놀아서 밀리는 것이 아니다
        self.assertAlmostEqual(summary["max_buffer_wait_s"], 187.2, places=1)
        self.assertEqual(summary["peak_buffer_sheets"], 4.0)
        self.assertLess(summary["peak_buffer_sheets"], handoff.BUFFER_RA_SLOTS,
                        "동시 체류가 R-A 50 슬롯을 넘으면 버퍼 설계부터 다시 세워야 한다")

    def test_the_ir_bank_forces_a_bigger_service(self):
        """IR 175 kW 는 이 플랜트 최대 부하다 — 100 AT 로는 못 받는다."""
        self.assertAlmostEqual(electrical.installed_kw(), 266.0, places=1)
        self.assertAlmostEqual(electrical.demand_kw(), 198.70, places=1)
        self.assertEqual(electrical.main_breaker_at(), 400)
        self.assertEqual(electrical.main_breaker_frame_a(), 400)
        self.assertAlmostEqual(electrical.contract_kva(), 298.05, places=0)
        ir = [f for f in electrical.FEEDERS if f.panel.startswith("LP-GRM-IR")]
        self.assertEqual(len(ir), 2, "175 kW 를 한 피더에 몰면 차단기가 주차단기와 맞먹는다")
        for feeder in ir:
            with self.subTest(feeder=feeder.tag):
                self.assertLess(feeder.breaker_at, electrical.main_breaker_at())

    def test_the_load_centre_moved_and_the_board_followed(self):
        """최대 부하가 하류 끝에 생겼는데 반을 그대로 두면 규칙과 어긋난다."""
        centre = wiring.demand_center_x_mm()
        self.assertAlmostEqual(centre, 42572, delta=200)
        self.assertEqual(wiring.MDB_POSITION_MM[0], round(centre / 500) * 500)
        self.assertGreaterEqual(wiring.aisle_clear_width_mm(), 900,
                                "반을 옮겨도 보행 최소폭은 지켜야 한다")

    def test_ir_heat_must_leave_the_room(self):
        """IR 발열을 실내로 들이면 환기가 세 배가 된다 — 배기로 빼야 한다."""
        self.assertAlmostEqual(thermal.ir_demand_kw(), 131.25, places=2)
        self.assertAlmostEqual(thermal.ir_useful_kw() + thermal.ir_enclosure_loss_kw(),
                               thermal.ir_demand_kw(), places=2)
        grm = [h for h in thermal.heat_sources() if h.tag.startswith("TH-GRM")]
        self.assertEqual(len(grm), 2)
        for source in grm:
            with self.subTest(source=source.tag):
                self.assertEqual(source.sink, "배기", "실내로 가면 환기가 감당 못 한다")
        self.assertEqual(thermal.required_airflow_m3h(), 33000)
        # 배기가 실패하면 어떻게 되는지를 값으로 남긴다 — 후드가 전제라는 근거
        def airflow(room_kw):
            return room_kw * 3600.0 / (1.2 * 1.005 * thermal.ROOM_DELTA_T_C)

        room = thermal.room_load_kw()
        self.assertAlmostEqual(airflow(room), 32_570, delta=200)
        self.assertAlmostEqual(airflow(room + thermal.ir_useful_kw()), 83_499, delta=300,
                               msg="냉각 후드가 현열을 못 잡으면 환기가 2.5 배가 된다")
        self.assertAlmostEqual(
            airflow(room + thermal.ir_useful_kw() + thermal.ir_enclosure_loss_kw()),
            110_913, delta=400, msg="둘 다 실내로 오면 환기가 3.4 배가 된다")

    def test_noise_stays_inside_the_limits_with_the_new_cell(self):
        """배기 블로워 두 대와 슈레더가 들어와도 목표를 지켜야 한다."""
        self.assertLessEqual(acoustics.worst_near_field_dba(), acoustics.NEAR_FIELD_LIMIT_DBA)
        self.assertLessEqual(acoustics.worst_aisle_dba()[1], acoustics.AISLE_LIMIT_DBA)
        tags = {n.tag for n in acoustics.noise_sources()}
        self.assertIn("NS-GRM-SH", tags, "슈레더를 안 세면 소음 검토가 거짓말이 된다")


class TestBalancePlans(unittest.TestCase):
    """격차 19.5 장/h 를 어디서 흡수하는가 — 두 안 다 성립하지만 잃는 것이 다르다."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_release_hold_is_the_only_throttle(self):
        """감속은 셀 점유시간을 건드리지 않는다 — 로봇이 손을 늦게 뗄 뿐이다."""
        self.assertEqual(campaign.RELEASE_HOLD_S, 0.0, "기본은 제 속도로 돈다")
        base, held = campaign.summary(), campaign.summary(20.0)
        self.assertGreater(held["takt_s"], base["takt_s"])
        self.assertLess(held["throughput_per_h"], base["throughput_per_h"])
        self.assertEqual(held["panels"], base["panels"], "보류가 장수를 바꾸면 안 된다")
        self.assertEqual(held["normal"], base["normal"], "보류가 판정을 바꾸면 안 된다")
        self.assertAlmostEqual(campaign.release_takt_s(20.0),
                               campaign.release_takt_s() + 20.0, places=6)

    def test_plan_b_lifts_the_downstream_within_its_limits(self):
        """B안은 칼날 상한과 인계 단축만으로 유입을 받아낸다 — 증설이 아니다."""
        b = handoff.plan_b()
        self.assertEqual(b.key, "B")
        self.assertLessEqual(handoff.PLAN_B_KNIFE_MM_S, handoff.KNIFE_SPEED_MAX_MM_S,
                             "칼날이 상한을 넘으면 그 안이 아니다")
        self.assertLess(handoff.PLAN_B_HANDLING_S, handoff.AS_UPLOADED_HANDLING_S)
        self.assertGreater(handoff.PLAN_B_KNIFE_MM_S, handoff.AS_UPLOADED_KNIFE_MM_S)
        self.assertGreaterEqual(b.margin_per_h, 0, "B안인데 여전히 밀린다")
        self.assertAlmostEqual(b.capacity_per_h, 68.4, places=1)
        self.assertIn("데크", b.lever, "데크 확장이 이 안의 일부라는 것이 표에 보여야 한다")
        self.assertIn(f"IR 관 {handoff.AS_UPLOADED_LAMP_KW:g} → {handoff.LAMP_KW:.2f} kW", b.lever)

    def test_plan_c_throttles_the_upstream_to_match(self):
        """C안은 후단 능력까지 정확히 내려온다 — 더 내리면 낭비다."""
        c = handoff.plan_c()
        self.assertEqual(c.key, "C")
        self.assertGreaterEqual(c.margin_per_h, 0, "C안인데 여전히 밀린다")
        self.assertLess(c.margin_per_h, 1.0, "필요 이상으로 내렸다")
        hold = handoff.plan_c_hold_s()
        self.assertGreater(hold, 0)
        loose = campaign.summary(hold - 1.0)
        self.assertGreater(loose["normal"] / loose["run_s"] * 3600.0,
                           handoff.as_uploaded_rate().line_per_h,
                           "보류를 1초 줄이면 다시 밀려야 최소값이다")

    def test_plan_c_costs_bottleneck_utilisation(self):
        """감속의 대가는 병목이 노는 것이다 — 그 사실이 표에 적혀야 한다."""
        self.assertGreater(handoff.JBR_UTILISATION_BASE, 0.9)
        held = campaign.summary(handoff.plan_c_hold_s())
        self.assertLess(campaign.JBR_S / held["takt_s"], handoff.JBR_UTILISATION_BASE)
        self.assertIn("놀게 된다", handoff.plan_c().cost)

    def test_both_plans_are_shown_in_the_drawing(self):
        self.assertIn('id="jb-ho-plans"', self.html)
        for plan in handoff.plans():
            with self.subTest(plan=plan.key):
                self.assertIn(f'"key":"{plan.key}"', self.html)
                self.assertIn(f'"cap":{plan.capacity_per_h:g}', self.html)
                self.assertIn(f'"margin":{plan.margin_per_h:g}', self.html)

    def test_variant_builder_anchors_still_exist(self):
        """두 벌을 찍어내는 앵커가 사라지면 빌드가 조용히 어긋난다."""
        self.assertIn(f"pvCamTakt={campaign.release_takt_s():g}", self.html)
        self.assertIn(f"pvCamWrap={campaign.release_takt_s():g}", self.html)
        delam = (pathlib.Path(__file__).resolve().parents[1]
                 / "docs" / "drawings" / "pv-delam-tandem.html").read_text(encoding="utf-8")
        self.assertIn(f'id="knifeSpeed" type="number" min="20" max="60" step="1" '
                      f'value="{handoff.KNIFE_SPEED_MM_S:g}"', delam)
        self.assertIn(f'id="handlingTime" type="number" min="5" max="25" step="1" '
                      f'value="{handoff.HANDLING_S:g}"', delam)

    def test_blank_field_falls_back_to_the_connected_configuration(self):
        """칸을 비우면 계산기가 업로드 당시 값으로 조용히 되돌아가면 안 된다."""
        delam = (pathlib.Path(__file__).resolve().parents[1]
                 / "docs" / "drawings" / "pv-delam-tandem.html").read_text(encoding="utf-8")
        self.assertIn(f"calcNumber('knifeSpeed',{handoff.KNIFE_SPEED_MM_S:g})", delam)
        self.assertIn(f"calcNumber('handlingTime',{handoff.HANDLING_S:g})", delam)
        self.assertNotIn(f"calcNumber('knifeSpeed',{handoff.AS_UPLOADED_KNIFE_MM_S:g})", delam)
        self.assertNotIn(f"calcNumber('handlingTime',{handoff.AS_UPLOADED_HANDLING_S:g})", delam)
