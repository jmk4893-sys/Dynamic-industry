"""전처리 플랜트 배치도가 배치 모델과 어긋나지 않는지 검증.

`docs/drawings/pv-preprocess-plant.html` 는 셀 외형·존 배치를 자바스크립트 리터럴로
들고 있다. `pv_preprocess.layout` 을 고치고 도면을 갱신하지 않으면 (또는 그 반대면)
두 문서가 서로 다른 공장을 가리키게 되므로, 값이 일치하는지 확인한다.

REV.21 에서 실제로 깨져 있던 두 가지 — 존이 자기 장비보다 짧은 것, 통로가 장비에
덮이는 것 — 은 아래 불변식 테스트로 다시 들어올 수 없게 막는다.
"""

import dataclasses
import importlib.util
import io
import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

from pv_preprocess import (acceptance, access, acoustics, ai, air, brand, campaign, crane, dust, electrical,
                           frames, handoff, kinematics, layout, materials, mounting, reliability, safety,
                           seismic, smart, servos, thermal, vision, wiring)

DRAWING = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "pv-preprocess-plant.html"


def read_drawing() -> str:
    return DRAWING.read_text(encoding="utf-8")


CONSOLE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "consoles" / "pv-preprocess-console.html"
ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


#: 셀 마크 데칼 — 태그 ↔ 존. 셀마다 하나이고, 3D 실측 가드 면에 붙는다.
DECAL_TAGS = {"AFU-101": "afu", "RB-101": "robot", "JBR-201": "jbr", "AFR-101": "afr",
              "SG-301": "post", "GBR-301": "buffer", "GRM-401": "grm"}


def brand_paths_in(html: str) -> list[str]:
    """HTML 안의 `PV_BRAND` 블록에서 경로 문자열만 뽑는다.

    파일이 마크를 어떻게 쓰든(SVG 든 Path2D 든) 좌표는 이 한 블록에서만 나와야
    한다. 정규식이 `shapes:` 배열의 세 번째 항만 집으므로, 다른 곳에 경로를 또
    적어 두면 여기 안 잡히고 `no_other_path_data` 시험이 잡는다.
    """
    block = re.search(r"shapes:\s*Object\.freeze\((\[\[.*?\]\])\.map", html, re.S)
    if not block:
        return []
    return re.findall(r'"(M[^"]*Z)"', block.group(1))


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
        self.assertEqual(total, 175, "sweep(동작 포락선)은 부품이 아니라 빠진다")
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
        self.assertIn("<title>태양광 전처리 통합 플랜트</title>", self.html)

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
            self.assertRegex(block, r"\[3430, '(FLIP )?AXIS 3,430'\]")
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
                key = ("370", "전개", "1,874", "2,290", "180°", "1,330")[index - 1]
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


class TestBrandMark(unittest.TestCase):
    """회사 마크 — 도형이 적힌 곳이 하나인가.

    마크가 3D 외장에도 붙고 콘솔 화면에도 붙는다. 두 벌로 두면 한쪽만 고쳐지는
    날이 오고, 그날 두 마크는 같은 회사 것이 아니게 된다. 그래서 이 시험이
    묻는 것은 "예쁜가" 가 아니라 **같은 문자열인가** 다.

    도형이 원본 아트워크와 같은지는 여기서 못 잰다 — 픽셀 대조는 브라우저가
    필요하므로 `tools/check_brand_fidelity.mjs` 가 따로 잰다. 이 시험은 그
    아래 단계, 즉 **한 번 뽑은 도형이 두 소비자에게 그대로 갔는가**를 본다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()
        cls.console = read_console()

    def test_the_extraction_is_not_hand_written(self):
        """좌표는 추출기 출력이지 사람이 적은 값이 아니다."""
        self.assertEqual(brand.SOURCE_FILE, "symbol_100x100mm.ai")
        self.assertEqual(len(brand.SHAPES), 5)
        self.assertEqual(len(brand.shapes_of("blue")), 4)
        self.assertEqual(len(brand.shapes_of("amber")), 1)
        # 100 mm 짜리 심볼 — 파일 이름과 ArtBox 가 맞는다
        self.assertAlmostEqual(brand.WIDTH_MM, 100.0, places=2)
        ax0, ay0, ax1, ay1 = brand.ARTBOX_PT
        self.assertAlmostEqual((ax1 - ax0) / 72 * 25.4, brand.WIDTH_MM, places=3)
        self.assertAlmostEqual((ay1 - ay0) / (ax1 - ax0) * brand.VIEW_W,
                               brand.VIEW_H, places=3)
        # 추출기와 **원본 아트워크** 가 둘 다 저장소에 있어야 재현할 수 있다.
        # 추출기만 있고 원본이 없으면 `brand.py` 의 좌표는 확인할 길이 없는 값이
        # 되고, 그 순간 "눈으로 따라 그린 것" 과 구별되지 않는다.
        self.assertTrue((ROOT / "tools" / "extract_brand.py").exists())
        art = ROOT / brand.SOURCE_PATH
        self.assertTrue(art.exists(), f"원본 아트워크가 없다: {brand.SOURCE_PATH}")
        self.assertEqual(art.name, brand.SOURCE_FILE)
        # AI 는 PDF 1.4 컨테이너다 — 추출기가 읽는 것이 그 사실이다
        self.assertTrue(art.read_bytes().startswith(b"%PDF-"))

    def test_every_path_is_a_closed_fill(self):
        """열린 경로는 채움이 뷰어마다 달라진다."""
        for shape in brand.SHAPES:
            with self.subTest(shape=shape.tag):
                self.assertTrue(shape.d.startswith("M"))
                self.assertTrue(shape.d.endswith("Z"))
                self.assertIn(shape.role, ("blue", "amber"))
                self.assertEqual(shape.colour, brand.ROLE_COLOUR[shape.role])
                self.assertEqual(len(shape.cmyk), 4)

    def test_the_drawing_and_the_console_use_the_same_shapes(self):
        """이 시험이 이 판의 요점이다 — 두 파일이 **글자까지** 같아야 한다."""
        want = list(brand.path_data())
        self.assertEqual(brand_paths_in(self.html), want, "3D 도면의 마크가 어긋났다")
        self.assertEqual(brand_paths_in(self.console), want, "콘솔의 마크가 어긋났다")
        # 두 소비자끼리도 같다 — 위 둘이 같은 값을 가리키므로 자동이지만,
        # 어느 쪽이 틀렸는지 읽히게 따로 적는다
        self.assertEqual(brand_paths_in(self.html), brand_paths_in(self.console))

    def test_the_colours_are_the_same_everywhere(self):
        """색이 갈리면 도형이 같아도 다른 마크다."""
        for html, where in ((self.html, "도면"), (self.console, "콘솔")):
            with self.subTest(where=where):
                self.assertIn(f'blue: "{brand.BLUE}"', html)
                self.assertIn(f'amber: "{brand.AMBER}"', html)
                self.assertEqual(html.count(brand.BLUE) >= 1, True)
        # CMYK 원값도 같이 남아 있어야 도장·실크 발주가 된다
        self.assertEqual(len(brand.BLUE_CMYK), 4)
        self.assertEqual(len(brand.AMBER_CMYK), 4)

    def test_no_other_path_data_hides_in_either_file(self):
        """PV_BRAND 밖에 경로가 또 적혀 있으면 단일 출처가 아니다.

        마크 경로는 `M…Z` 꼴이고 좌표가 소수점을 갖는다. 그 꼴의 문자열이
        PV_BRAND 블록 밖에 있으면 누군가 마크를 베껴 둔 것이다.
        """
        for html, where in ((self.html, "도면"), (self.console, "콘솔")):
            with self.subTest(where=where):
                block = re.search(r"shapes:\s*Object\.freeze\(\[\[.*?\]\]\.map", html, re.S)
                outside = html[:block.start()] + html[block.end():]
                for shape in brand.SHAPES:
                    self.assertNotIn(shape.d, outside,
                                     f"{where}: {shape.tag} 경로가 PV_BRAND 밖에도 있다")

    def test_the_drawing_draws_the_mark_from_that_one_block(self):
        """3D 는 캔버스 Path2D 로, 콘솔은 SVG 로 — 둘 다 같은 블록을 읽는다."""
        self.assertIn("new Path2D(s[2])", self.html)
        self.assertIn("window.pvMarkPaint", self.html)
        self.assertIn("pvMarkPaint(x, 26, 44, 92)", self.html,
                      "명판 텍스처가 전역 마크 함수를 써야 한다")
        self.assertIn("PV_BRAND", self.console)
        self.assertIn("markSvg", self.console)

    def test_the_console_values_come_from_the_model(self):
        """콘솔 숫자를 손으로 적으면 도면과 갈린다."""
        import json as _json
        block = re.search(r"var CONSOLE = (\{.*?\n  \});", self.console, re.S)
        self.assertIsNotNone(block, "CONSOLE 블록이 없다")
        got = _json.loads(re.sub(r"\n  ", "\n", block.group(1)))
        self.assertEqual(got["taktS"], campaign.summary()["takt_s"])
        self.assertEqual(got["demandKw"], electrical.demand_kw())
        self.assertEqual(got["stopChainMs"], safety.stop_chain_ms())
        self.assertEqual(got["annualPanels"], reliability.annual_panels())
        self.assertEqual(got["unanchored"], len(seismic.unanchored()))
        self.assertEqual(got["dustFlowM3h"], dust.counted_flow_m3h())
        self.assertEqual(got["airFadNlMin"], air.compressor_fad_nl_min())
        self.assertEqual(got["acceptanceItems"], len(acceptance.items()))

    def test_the_plates_ride_on_enclosures_that_already_stood(self):
        """마크는 **붙인 것**이지 세운 것이 아니다.

        명판을 달려고 기둥을 세우면 통로를 먹는다 — §36 에서 고정 플랫폼을 못
        세운 것과 같은 벽이다. 그래서 판은 이미 서 있던 엣지 캐비닛 도어와
        관제실 벽면에 **면일치로 박힌다.** 캐비닛 도어에는 원래 라벨 없는
        주황 띠(420 × 100 × 20)가 20 mm 나와 있었고, 그것을 두께 12 인 명판으로
        바꿔 넣었으므로 보행 유효폭은 오히려 넓어진다.
        """
        # 존마다 하나 — 부제는 배치 모델의 존 라벨이라 존이 바뀌면 여기서 걸린다
        want = {"EC-AFU": "afu", "EC-ROB": "robot", "EC-JBR": "jbr", "EC-AFR": "afr",
                "EC-POS": "post", "EC-BUF": "buffer", "EC-GRM": "grm"}
        labels = {z.key: z.label for z in layout.build_zones()}
        calls = re.findall(r"pvNamePlate\(g,([\d.]+),\[([-\d.]+),([\d.]+),([-\d.]+)\],"
                           r"0,'([\w-]+)','([^']*)'\)", self.html)
        # 캐비닛 7면 + 관제실 1면 + 셀 마크 데칼 7장
        self.assertEqual(len(calls), len(want) + 1 + len(DECAL_TAGS))
        seen = {}
        for w, x, y, z, tag, sub in calls:
            seen[tag] = (float(w), float(z), sub)
        for tag, key in want.items():
            with self.subTest(tag=tag):
                self.assertIn(tag, seen, f"{tag} 명판이 없다")
                w, z, sub = seen[tag]
                self.assertEqual(sub, labels[key], "부제는 존 라벨에서 온다")
                # 캐비닛은 z 4.45…4.75 — 판이 문짝 면보다 통로쪽으로 나오면 안 된다
                self.assertGreaterEqual(round(z - 0.012 / 2, 6), 4.45,
                                        f"{tag} 명판이 통로로 나왔다")
                self.assertLessEqual(w, 0.6, "판이 문짝(600)보다 넓다")
        # 라벨 없던 주황 띠는 남아 있으면 안 된다 — 명판이 그 자리를 대신했다
        self.assertNotIn("L([.42,.1,.02],", self.html, "빈 주황 띠가 남아 있다")
        # 세운 것이 없어야 한다 — 표지주·신호등을 다시 들이지 않았는지 본다
        for erected in ("pvSign", "pvBeacon", "콘솔 전면 스커트"):
            self.assertNotIn(erected, self.html,
                             f"{erected} — 마크를 붙이려고 설비를 세우지 않는다")

    def test_the_artifact_is_built_from_the_repo_not_maintained(self):
        """아티팩트를 손으로 고치면 저장소와 갈린다 — 변환기가 저장소에 있어야 한다.

        발행본을 사람이 만지기 시작하면 그때부터 두 벌이고, 두 벌은 반드시
        갈라진다. 그래서 발행은 **저장소 → 기계 변환 → 발행** 한 방향이고,
        그 변환기가 저장소 안에 있어야 아무나 같은 결과를 다시 얻는다.

        여기서 이름만 확인하면 안 된다 — `FETCHING` 을 `FETCHING_OFF` 로 바꿔
        검사를 꺼도 부분문자열은 그대로 남는다. 그래서 변환기를 **실제로 돌려**
        막아야 할 것을 막는지 본다.
        """
        builder = ROOT / "tools" / "build_artifact.py"
        self.assertTrue(builder.exists(), "아티팩트 변환기가 저장소에 없다")

        spec = importlib.util.spec_from_file_location("_build_artifact", builder)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # 원본을 표에서 가리켜야 하고, 그 파일이 실재해야 한다
        self.assertIn("console", mod.TARGETS)
        src, _ = mod.TARGETS["console"]
        self.assertEqual(src, pathlib.Path("docs/consoles/pv-preprocess-console.html"))
        self.assertTrue(CONSOLE.exists())

        good = mod.convert(read_console(), src)
        # 골격 태그가 실제로 벗겨졌는가. 이름 **뒤에 경계**를 요구해야 한다 —
        # 부분문자열로 보면 정상적으로 살아남은 `<header>` 를 골격으로 오인한다.
        for tag in ("doctype", "html", "head", "body", "meta"):
            with self.subTest(tag=tag):
                self.assertIsNone(re.search(r"</?" + tag + r"(?=[\s/>])", good, re.I),
                                  f"{tag} 골격 태그가 남았다")
        # 이름은 저장소 파일의 <title> 이 그대로 간다 — 변환기가 짓지 않는다
        self.assertIn("<title>MCR-901 운전 콘솔</title>", good)
        self.assertNotIn("MCR-901", builder.read_text(encoding="utf-8"),
                         "변환기가 이름을 지으면 관리 대상이 하나 늘어난다")

        # 막아야 할 것을 실제로 막는가 — 넣어 보고 거부되는지 본다
        blocked = {
            "script src": '<script src="https://cdn.example.com/x.js"></script>',
            "link href": '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?f=X">',
            "css url()": "<style>body{background:url(https://img.example.com/a.png)}</style>",
            "css @import": '<style>@import "https://cdn.example.com/a.css";</style>',
            "fetch()": '<script>fetch("https://api.example.com/v1")</script>',
            "프로토콜 상대": '<script src="//cdn.example.com/x.js"></script>',
        }
        base = read_console()
        for name, inject in blocked.items():
            with self.subTest(inject=name):
                with self.assertRaises(SystemExit):
                    mod.convert(base.replace("<style>", inject + "\n<style>", 1), src)
        # 문장 속 주소는 요청이 아니다 — 오탐하면 도면처럼 큰 파일이 아예 안 나온다
        mod.convert(base.replace("<style>", "<!-- 근거: https://example.com/spec -->\n<style>", 1), src)
        # 골격 확인은 스트리퍼가 실패했을 때의 안전망이다 — 실패시켜서 걸리는지 본다
        keep = mod.STRIP_HEAD_TAGS
        try:
            mod.STRIP_HEAD_TAGS = tuple(p for p in keep if "body" not in p.pattern)
            with self.assertRaises(SystemExit):
                mod.convert(base, src)
        finally:
            mod.STRIP_HEAD_TAGS = keep
        # 이름이 없으면 아티팩트 이름이 파일명으로 떨어진다
        with self.assertRaises(SystemExit):
            mod.convert(base.replace("<title>MCR-901 운전 콘솔</title>", ""), src)

        # 콘솔 원본이 자기가 원본임을 밝혀야 나중에 발행본을 고치지 않는다
        self.assertIn("tools/build_artifact.py", base)

    def test_stripping_the_skeleton_does_not_eat_the_body(self):
        """골격만 벗겨야 한다 — 이름으로 시작하는 다른 것까지 먹으면 안 된다.

        실제로 당한 자리다. `<meta[^>]*>` 가 three.js 셰이더의
        `#include <metalnessmap_fragment>` 를 `<meta…>` 로 잡아 두 줄을 지웠고,
        표준 재질이 컴파일되지 않아 **발행본에서 3D 가 통째로 안 나왔다.**
        같은 이유로 `</?head[^>]*>` 가 `<header>` 와 `</header>` 를 지웠다.

        원본은 멀쩡했으므로 원본을 아무리 렌더해도 안 잡힌다. 그래서 여기서는
        변환기에 그 꼴을 직접 먹여 살아남는지 본다.
        """
        builder = ROOT / "tools" / "build_artifact.py"
        spec = importlib.util.spec_from_file_location("_build_artifact2", builder)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        src = pathlib.Path("docs/consoles/pv-preprocess-console.html")

        page = (
            "<!doctype html>\n<html lang=\"ko\">\n<head>\n"
            '<meta charset="utf-8">\n'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'">\n'
            "<title>T</title>\n</head>\n<body>\n"
            "<header class=\"top\">머리</header>\n"
            # 이름으로 시작할 뿐 골격이 아닌 것들 — 경계를 안 보면 이것들도 지워진다
            "<bodytext>본문</bodytext>\n<htmlwidget>위젯</htmlwidget>\n"
            "<script>var s=`#include <metalnessmap_pars_fragment>\n"
            "#include <metalnessmap_fragment>\n"
            "#include <normal_fragment_maps>`;<\\/script>\n"
            "</body>\n</html>\n"
        )
        out = mod.convert(page, src)

        # 벗겨야 할 것은 벗겨졌는가 — 여기서도 경계를 요구한다. 부분문자열로 보면
        # 바로 아래에서 살아남기를 요구하는 <htmlwidget> 을 골격으로 오인한다.
        self.assertNotIn("<!doctype", out.lower())
        for gone in ("html", "head", "body", "meta"):
            with self.subTest(gone=gone):
                self.assertIsNone(re.search(r"</?" + gone + r"(?=[\s/>])", out, re.I),
                                  f"{gone} 골격 태그가 남았다")
        # 남아야 할 것은 남았는가 — 여기가 실제로 깨졌던 자리다
        for kept in ("<header class=", "</header>", "<bodytext>", "</bodytext>",
                     "<htmlwidget>", "</htmlwidget>",
                     "#include <metalnessmap_pars_fragment>",
                     "#include <metalnessmap_fragment>",
                     "#include <normal_fragment_maps>"):
            with self.subTest(kept=kept):
                self.assertIn(kept, out, f"골격이 아닌 것을 지웠다: {kept}")

        # 변환기 스스로도 개수로 확인해야 한다 — 스트리퍼가 다시 넓어지면 멈춘다
        keep = mod.STRIP_HEAD_TAGS
        try:
            mod.STRIP_HEAD_TAGS = keep + (re.compile(r"<meta[^>]*>\s*", re.I),)
            with self.assertRaises(SystemExit):
                mod.convert(page, src)
        finally:
            mod.STRIP_HEAD_TAGS = keep

        # 발행본을 브라우저로 확인하는 도구가 저장소에 있어야 한다.
        # 원본만 봐서는 이 결함이 잡히지 않는다는 것이 이번 교훈이다.
        checker = ROOT / "tools" / "check_artifact_render.mjs"
        self.assertTrue(checker.exists())
        text = checker.read_text(encoding="utf-8")
        self.assertIn("pageerror", text)
        self.assertIn("shader", text.lower())

    def test_the_mark_is_actually_visible_on_the_plant(self):
        """붙였는데 안 보이면 안 붙인 것과 같다.

        처음엔 명판(420 mm)을 통로 바깥벽 캐비닛에만 달았고, 그 결과 플랜트
        전경에서 마크가 **하나도 읽히지 않았다.** 이 플랜트는 열린 프레임 +
        투명 가드라 로고가 붙을 기계 외장이 아예 없기 때문이다.

        그래서 셀마다 통로쪽 가드 면에 데칼을 붙였다. 여기서 지키는 것은 셋이다 —
        셀마다 하나일 것, 멀리서 읽힐 만큼 클 것, 통로를 먹지 않을 것.
        """
        calls = re.findall(r"pvNamePlate\(g,([\d.]+),\[([-\d.]+),([\d.]+),([-\d.]+)\],"
                           r"0,'([\w-]+)','([^']*)'\)", self.html)
        decals = {tag: (float(w), float(x), float(z))
                  for w, x, y, z, tag, _ in calls if tag in DECAL_TAGS}
        self.assertEqual(set(decals), set(DECAL_TAGS), "셀마다 데칼이 하나씩 있어야 한다")

        zones = {z.key: z for z in layout.build_zones() if z.key != "gate"}
        self.assertEqual(len(DECAL_TAGS), len(zones), "데칼 수는 셀 수와 같다")
        for tag, key in DECAL_TAGS.items():
            with self.subTest(tag=tag):
                w, x, z = decals[tag]
                # 캐비닛 명판(420)보다 세 배 이상 커야 전경에서 읽힌다
                self.assertGreaterEqual(w, 1.2, f"{tag} 데칼이 작아 안 읽힌다")
                # 장비 밴드 안이어야 보행 유효폭을 안 먹는다 (통로는 z 3.55…4.75)
                self.assertLessEqual(z + 0.012 / 2, 3.55,
                                     f"{tag} 데칼이 통로로 넘어왔다")
                # 자기 셀 안에 있어야 한다
                zone = zones[key]
                lo = (zone.x0_mm - 24750) / 1000
                hi = (zone.x1_mm - 24750) / 1000
                self.assertGreaterEqual(x, lo - 0.5, f"{tag} 데칼이 셀 밖이다")
                self.assertLessEqual(x, hi + 0.5, f"{tag} 데칼이 셀 밖이다")

    def test_the_plate_texture_paints_the_mark_not_a_copy(self):
        """명판 텍스처가 마크를 **직접 그리지 않고** 전역을 부른다.

        캔버스에 도형을 다시 적어 두면 그 순간 두 번째 출처가 생긴다. 명판
        코드에는 경로 문자열이 없어야 하고, `pvMarkPaint` 를 불러야 한다.
        """
        i = self.html.index("function pvPlateTexture(")
        j = self.html.index("function pvNamePlate(")
        body = self.html[i:j]
        self.assertIn("window.pvMarkPaint(", body, "명판이 전역 마크 함수를 써야 한다")
        self.assertNotIn("Path2D", body, "명판 안에서 도형을 다시 그리면 출처가 둘이다")
        for shape in brand.SHAPES:
            self.assertNotIn(shape.d, body)
        # 판 비율은 캔버스 비율에서 나와야 글자가 늘어나지 않는다
        self.assertIn("var h = w * 168 / 512;", self.html)


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
        self.assertAlmostEqual(electrical.contract_kw(), 293.1, places=1)
        self.assertGreater(electrical.contract_kw(), electrical.LOW_VOLTAGE_LIMIT_KW)
        self.assertTrue(electrical.needs_high_voltage())
        self.assertEqual(electrical.HV_SUPPLY_VOLTAGE_V, 22_900)
        # 전처리만일 때는 저압이 맞았다 — 그 사실이 기록으로 남아야 한다
        preprocess_only = sum(f.demand_kw for f in electrical.FEEDERS
                              if not f.panel.startswith("LP-GRM")
                              and f.panel not in ("LP-IT", "LP-INST", "LP-CRANE", "LP-AIR"))
        self.assertLess(preprocess_only * electrical.CONTRACT_MARGIN,
                        electrical.LOW_VOLTAGE_LIMIT_KW,
                        "REV.22 까지의 저압 인입은 틀린 게 아니라 전제가 바뀐 것이다")

    def test_plant_taps_the_existing_site_service(self):
        """부지에 1,200 kW 가 이미 있으면 자체 수전설비를 세울 이유가 없다."""
        self.assertEqual(electrical.SITE_SERVICE_KW, 1200.0)
        self.assertTrue(electrical.taps_existing_service())
        self.assertIn("기존 부지 인입", electrical.supply_method())
        self.assertAlmostEqual(electrical.site_utilisation_pct(), 24.4, places=1)
        self.assertAlmostEqual(electrical.site_headroom_kw(), 906.9, places=1)
        # 수용률이 전부 1.0 이 되는 최악에도 들어가야 '여유가 있다'고 말할 수 있다
        self.assertAlmostEqual(electrical.worst_case_kw(), 299.0, places=1)
        self.assertTrue(electrical.fits_site_service())
        self.assertLess(electrical.worst_case_kw() / electrical.SITE_SERVICE_KW, 0.25)
        # 재는 자가 설치(266.0)인지 계약(268.2)인지 — 둘 사이 값에서 갈린다.
        # 부지 계통에 실제로 흐르는 최악은 여유율을 곱한 행정값이 아니다.
        #
        # REV.28 에서 이 부등호가 뒤집혔다. 계약 287.3 < 상한 287.5 인데, 그
        # 0.2 는 크레인이 공정과 같이 도는 경우에만 생긴다 — 운전 중 설비 위
        # 인양은 안전상 금지라 일어나지 않는 경우다. 계약이 덮어야 하는 것은
        # 상한이 아니라 **동시에 걸릴 수 있는** 최악이므로, 재는 자를 바꾼다.
        self.assertGreater(electrical.contract_kw(),
                           electrical.coincident_worst_case_kw())
        self.assertLess(electrical.contract_kw(), electrical.worst_case_kw(),
                        "상한이 계약을 넘는다 — 넘는 몫이 비동시 부하뿐인지가 관건이다")
        self.assertAlmostEqual(
            electrical.worst_case_kw() - electrical.coincident_worst_case_kw(),
            sum(f.installed_kw for f in electrical.FEEDERS
                if f.panel in electrical.NON_COINCIDENT_PANELS), places=1)
        self.assertTrue(electrical.fits_site_service(300.0))
        self.assertFalse(electrical.fits_site_service(298.0))
        # 인입이 있어도 최악이 안 들어가면 자체 수전을 세워야 한다
        self.assertFalse(electrical.taps_existing_service(250.0))
        self.assertFalse(electrical.taps_existing_service(0.0))
        # 세울 큐비클이 없다 — 부지 설비를 쓴다
        self.assertEqual(electrical.substation_cubicles(), ())
        self.assertEqual(electrical.substation_room_mm(), (0, 0, 0))
        self.assertEqual(electrical.incomer_summary()["transformer_kva"], 0)

    def test_low_voltage_tap_is_bounded_by_voltage_drop_not_ampacity(self):
        """저압으로 끌면 거리를 묶는 것은 허용전류가 아니라 전압강하다."""
        self.assertTrue(electrical.TAP_AT_LOW_VOLTAGE)
        self.assertAlmostEqual(electrical.lv_tap_max_length_m(), 172.8, places=1)
        # 굵게 할수록 멀리 가지만 비례하지는 않는다 (리액턴스는 거의 안 줄어든다)
        self.assertLess(electrical.lv_tap_max_length_m(150),
                        electrical.lv_tap_max_length_m(240))
        self.assertLess(electrical.lv_tap_max_length_m(240),
                        electrical.lv_tap_max_length_m(300))
        self.assertAlmostEqual(electrical.lv_tap_max_length_m(300), 172.8, places=1)
        # REV.34 에서 주회로가 300 mm² 로 올라가 기본값과 300 이 같아졌다 —
        # 240 이 여전히 더 짧은지가 "굵을수록 멀리 간다" 를 지키는 확인이다.
        self.assertLess(electrical.lv_tap_max_length_m(240),
                        electrical.lv_tap_max_length_m())
        # 허용전류만 보면 300 은 514 A 라 여유가 있는데, 거리가 먼저 끊긴다
        self.assertGreater(electrical.LV_CABLE_AMPACITY_A[300],
                           electrical.main_breaker_at())

    def test_the_tap_distance_is_not_invented(self):
        """부지 배전반까지의 실거리는 발주처 실측이다 — 숫자를 지어내면 안 된다."""
        self.assertIsNone(wiring.SITE_BOARD_TO_MDB_MM)
        self.assertIsNone(wiring.incoming_cable_m())
        self.assertFalse(wiring.incoming_length_is_known())
        self.assertIn("INCOMING_CABLE_M = 0,", self.html)
        self.assertIn("incomingKnown: false", self.html)
        self.assertIn("미확정", self.html, "길이를 모르면 도면도 모른다고 적어야 한다")
        # **거리와 판정은 다른 것이다.** 발주처가 준 것은 "151 m 이내" 라는
        # 판정이지 몇 m 인지가 아니다. 판정은 방식(저압 분기·변압기 불요)을
        # 정하고, 거리는 케이블 물량을 정한다 — 한계값을 실거리 자리에 적으면
        # 물량이 상한으로 부푼 채 확정 얼굴을 하고 발주로 간다.
        self.assertTrue(wiring.SITE_BOARD_WITHIN_LV_LIMIT)
        self.assertTrue(wiring.lv_tap_is_confirmed(), "방식은 확정됐다")
        self.assertIsNone(wiring.SITE_BOARD_TO_MDB_MM, "거리는 여전히 모른다")
        self.assertFalse(wiring.incoming_length_is_known())
        self.assertFalse(wiring.lv_tap_is_confirmed(within=False),
                         "한계 밖이면 저압 분기가 아니다 — 분기가 죽지 않았는지 본다")
        # 한계값이 실거리로 새어 들어가면 안 된다
        self.assertNotEqual(wiring.SITE_BOARD_TO_MDB_MM,
                            int(electrical.lv_tap_max_length_m() * 1000))
        self.assertIn("withinLvLimit: true", self.html)
        self.assertIn("lvTapConfirmed: true", self.html)
        self.assertIn("이내 확인 · 실거리 미확정", self.html)
        self.assertIn("저압 분기가 확정됐다", self.html)
        self.assertNotIn("INCOMING_CABLE_M.toFixed(1) + ' m (인입점 x=0 기준)'", self.html)

    def test_transformer_is_sized_from_demand_not_guessed(self):
        """변압기는 목표 부하율과 계약 피상전력 중 큰 쪽이 지배한다."""
        self.assertAlmostEqual(electrical.apparent_demand_kva(), 241.2, places=1)
        self.assertEqual(electrical.transformer_kva(), 500)
        self.assertIn(electrical.transformer_kva(), electrical.TRANSFORMER_RATINGS_KVA)
        self.assertGreaterEqual(electrical.transformer_kva(), electrical.contract_kva())
        self.assertAlmostEqual(electrical.transformer_load_pct(), 48.2, places=1)
        self.assertLessEqual(electrical.transformer_load_pct(),
                             electrical.TRANSFORMER_LOAD_FACTOR * 100,
                             "부하율이 목표를 넘으면 한 단계 큰 용량을 골랐어야 한다")
        # 여기서는 계약 피상전력이 지배한다 — 부하율 기준은 301.4 > 276.0 에 가려진다.
        # 어느 쪽이 정했는지가 바뀌면 설계 근거가 바뀐 것이므로 못 박아 둔다.
        self.assertEqual(electrical.transformer_sizing_basis(), "계약 피상전력")
        self.assertAlmostEqual(electrical.transformer_required_kva(), 325.65, places=1)
        # 계약이 지배하지 않는 지점에서 부하율 기준이 실제로 작동하는지 — 0.80 이
        # 아니면 170 kVA 는 300 이 아니라 200 으로 떨어진다.
        self.assertEqual(electrical.transformer_sizing_basis(apparent_kva=170, contract=0),
                         "목표 부하율")
        self.assertEqual(electrical.transformer_kva(apparent_kva=170, contract=0), 300)
        self.assertEqual(electrical.transformer_kva(apparent_kva=160, contract=0), 200)

    def test_the_main_cable_carries_the_breaker_not_the_demand(self):
        """차단기가 떨어지기 전에 케이블이 타면 보호가 성립하지 않는다."""
        size = electrical.lv_main_cable_mm2()
        self.assertEqual(size, 300)
        self.assertGreaterEqual(electrical.LV_CABLE_AMPACITY_A[size],
                                electrical.main_breaker_at())
        # 종전 인입 규격 35 mm² 는 이 전류를 못 받는다 — 그것이 확정의 이유 중 하나다
        self.assertLess(electrical.LV_CABLE_AMPACITY_A[35], electrical.main_breaker_at())
        self.assertLess(electrical.lv_cable_mm2(100), size, "전류가 작으면 더 얇아야 한다")

    def test_high_voltage_would_move_the_copper_off_the_long_run(self):
        """저압 분기 한계를 넘으면 고압 분기로 간다 — 그때의 근거를 남긴다."""
        self.assertAlmostEqual(electrical.hv_incoming_current_a(), 8.21, places=2)
        self.assertLess(electrical.hv_incoming_current_a(),
                        electrical.demand_current_a() / 40,
                        "같은 전력을 고압으로 나르면 전류가 40배 이상 작아진다")
        self.assertEqual(electrical.transformer_kva(), 500,
                         "고압 분기로 가면 국소 변압기가 이 용량이다 — REV.25 에서 "
                         "스마트 팩토리 부하가 붙으며 300 → 500 으로 한 단 올라갔다")

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
        self.assertAlmostEqual(need, 33.8, places=1)

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
                      # 상한과 동시 최악은 다른 값이다. 도면이 둘을 같게 적으면
                      # 계약이 무엇을 덮는지가 흐려진다 — 그래서 따로 못 박는다.
                      f"coincidentWorstCaseKw: {c['coincident_worst_case_kw']}",
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
        self.assertIn("function fitSheet(svg)", self.html)
        self.assertIn("fitSheet(electricalSvg);", self.html, "렌더 후에 호출되지 않으면 없는 것과 같다")
        self.assertIn("fitSheet(smartSvg);", self.html, "스마트 시트도 같은 맞춤을 받아야 한다")
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


class TestSmartFactory(unittest.TestCase):
    """REV.25 스마트 팩토리 — 계측·네트워크·데이터가 설비에서 파생되는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_data_volume_is_derived_from_the_equipment_not_guessed(self):
        """축을 늘리면 회선이 따라와야 한다 — 데이터량은 설비의 함수다."""
        counts = smart.drive_counts()
        self.assertEqual(counts["서보"], servos.servo_axis_count())
        self.assertEqual(sum(counts.values()),
                         sum(a.qty for a in servos.SERVO_AXES + servos.MOTORS))
        # 서보 36축 × 6신호 × 100 Hz × 4 B 가 드라이브 대역의 지배항이다
        self.assertAlmostEqual(smart.drive_stream_bytes_per_s(), 88_056.0, places=1)
        self.assertAlmostEqual(smart.timeseries_bytes_per_s() / 1000, 91.7, places=1)
        # 공정 태그도 축·존에서 나온다
        self.assertEqual(smart.plc_tag_count(),
                         sum(a.qty for a in servos.SERVO_AXES + servos.MOTORS)
                         * smart.PLC_TAGS_PER_AXIS
                         + len(smart.edge_zones()) * smart.PLC_TAGS_PER_ZONE)

    def test_vision_dominates_and_each_head_sees_a_different_flow(self):
        """세 물량을 구분하지 않으면 대역이 틀린다."""
        streams = {st.head: st for st in smart.image_streams()}
        # 투입은 전손까지 찍는다 — 찍어야 판정을 한다
        self.assertAlmostEqual(streams["VS-101A"].per_hour, smart.panels_per_h(), places=1)
        self.assertGreater(smart.panels_per_h(), campaign.summary()["throughput_per_h"])
        # JBR 은 라인에 들어온 것만
        self.assertAlmostEqual(streams["VS-201A"].per_hour, 72.2, places=1)
        # 유리 검사는 R-A 정상만 — handoff 의 정본을 쓴다
        self.assertAlmostEqual(streams["GI-302"].per_hour, handoff.sheet_glass_per_h(), places=1)
        self.assertAlmostEqual(streams["VS-401"].per_hour, handoff.sheet_glass_per_h(), places=1)
        # 라인스캔 한 대가 드라이브 전체를 압도한다 — 이것이 설계의 지배항이다
        self.assertGreater(streams["GI-302"].bytes_per_s, smart.timeseries_bytes_per_s() * 60)
        self.assertAlmostEqual(smart.vision_raw_bytes_per_s() / 1e6, 6.90, places=2)

    def test_retention_policy_is_what_makes_storage_affordable(self):
        """장당 350 MB 를 전량 보존하면 성립하지 않는다."""
        self.assertAlmostEqual(smart.flagged_ratio(), 0.1167, places=4)
        self.assertAlmostEqual(smart.vision_retention(), 0.1367, places=4)
        self.assertAlmostEqual(smart.annual_storage_tb(), 14.19, places=2)
        self.assertAlmostEqual(smart.storage_capacity_tb(), 63.9, places=1)
        # 저장은 가동시간에 정비례한다 — 2교대 확정으로 2.06배가 됐다
        self.assertAlmostEqual(
            smart.annual_storage_tb() / 6.88,
            smart.OPERATING_HOURS_PER_YEAR / 2_000.0, places=2)
        # 전량 보존하면 같은 3년이 200 TB 를 넘는다
        seconds = smart.OPERATING_HOURS_PER_YEAR * 3600.0
        whole = smart.vision_raw_bytes_per_s() * seconds * smart.RETENTION_YEARS / 1e12
        self.assertGreater(whole, 140.0)
        # 같은 이중화를 적용해 사과 대 사과로 비교한다 — 보존 정책이 7배를 줄인다
        self.assertGreater(whole * smart.STORAGE_REDUNDANCY / smart.storage_capacity_tb(), 7.0)

    def test_operating_hours_come_from_the_confirmed_shift_plan(self):
        """가동시간은 교대 계획에서 나온다 — 라벨 공급과 저장이 여기 달려 있다."""
        self.assertEqual(smart.SHIFT_HOURS_PER_DAY, 16.0)
        self.assertEqual(smart.OPERATING_DAYS_PER_YEAR, 275)
        self.assertEqual(smart.PLANNED_STOP_HOURS_PER_DAY, 1.0)
        self.assertAlmostEqual(smart.OPERATING_HOURS_PER_YEAR, 4_125.0, places=1)
        self.assertAlmostEqual(
            smart.OPERATING_HOURS_PER_YEAR,
            (smart.SHIFT_HOURS_PER_DAY - smart.PLANNED_STOP_HOURS_PER_DAY)
            * smart.OPERATING_DAYS_PER_YEAR, places=1)
        # 계획정지를 빼는 항이 죽으면 6.7 % 과대해진다 — 지금 값으로는 그
        # 항을 지워도 아무 시험이 실패하지 않으므로 인자를 넣어 확인한다
        self.assertEqual(smart.operating_hours_per_year(stop_h=0.0), 4_400.0)
        self.assertGreater(smart.operating_hours_per_year(stop_h=0.0),
                           smart.OPERATING_HOURS_PER_YEAR)
        self.assertEqual(smart.operating_hours_per_year(shift_h=8.0, days=250,
                                                        stop_h=0.0), 2_000.0)

    def test_backbone_grade_is_chosen_above_the_requirement(self):
        self.assertAlmostEqual(smart.required_mbps(), 111.9, places=1)
        self.assertEqual(smart.backbone_grade_mbps(), 1_000)
        self.assertIn(smart.backbone_grade_mbps(), smart.ETHERNET_GRADES_MBPS)
        self.assertGreater(smart.backbone_grade_mbps(), smart.required_mbps())
        # 여유율을 뺀 순수 요구도 100 Mbps 등급을 넘는다 — 등급 선택의 근거
        self.assertGreater(smart.peak_bytes_per_s() * 8 / 1e6, 55.0)

    def test_redundant_pairs_do_not_share_a_rack(self):
        """공간이 남아도 이중화 쌍은 랙을 나눈다."""
        self.assertEqual(smart.rack_units_used(), 28)
        self.assertLessEqual(smart.rack_units_used(),
                             smart.RACK_HEIGHT_U * smart.RACK_FILL_LIMIT,
                             "28U 는 42U 한 면에 들어간다 — 공간 때문이 아니다")
        self.assertEqual(smart.rack_count(), 2)
        # 어느 품목이 쌍인지까지 못 박는다. "이중화 품목이 하나라도 있다"로
        # 재면 코어 스위치의 표시를 지워도 통과한다 — 실제로 그렇게 새어 나갔다.
        self.assertEqual({item.name for item in smart.redundant_pairs()},
                         {"코어 스위치 (백본 링 종단)", "OT/IT 경계 방화벽",
                          "MES·SCADA 서버", "UPS"})
        for item in smart.redundant_pairs():
            with self.subTest(item=item.name):
                self.assertGreaterEqual(item.qty, 2, "쌍이 아니면 이중화가 아니다")
        # 쌍이 하나도 없으면 랙은 한 면으로 줄어야 한다 — 2 가 상수가 아님을 확인
        self.assertEqual(smart.rack_units_used() // (smart.RACK_HEIGHT_U + 1) + 1, 1)

    def test_the_two_rooms_are_separate_and_outside_the_machine_band(self):
        """랙 팬 소음과 상주 근무는 같은 방에 못 있는다."""
        self.assertEqual(smart.server_room_mm(), (1800, 3200, 2700))
        self.assertEqual(smart.control_room_mm(), (4000, 3400, 2700))
        # 공정 존이 아니다 — 전기실과 같은 취급
        self.assertNotIn("smart", [z.key for z in layout.build_zones()])
        self.assertNotIn("server", [z.key for z in layout.build_zones()])
        # 두 방을 나란히 놓아도 MDB 하류에 들어간다
        span = wiring.facility_span_mm()
        self.assertEqual(span[1] - span[0],
                         smart.server_room_mm()[0] + wiring.FACILITY_PARTITION_MM
                         + smart.control_room_mm()[0])
        self.assertGreater(span[0], wiring.MDB_POSITION_MM[0])
        self.assertLessEqual(span[1], layout.plant_envelope_mm()[0])
        # 엣지 반 위치는 상수가 아니라 캐비닛 부하중심이다 — 여기서 독립으로 다시 센다
        centres = {z.key: (z.x0_mm + z.x1_mm) // 2 for z in layout.build_zones()}
        keys = smart.edge_zones()
        expected = round(sum(centres[k] for k in keys) / len(keys) / 500) * 500
        self.assertEqual(wiring.edge_cabinet_center_x_mm(), expected)
        self.assertEqual(wiring.lp_positions_mm()["LP-INST"], expected)
        # 배치가 바뀌면 반도 따라와야 한다 — 상수로 박아 두면 여기서 걸린다
        shifted = {key: value + 10_000 for key, value in centres.items()}
        self.assertEqual(wiring.edge_cabinet_center_x_mm(shifted), expected + 10_000)

    def test_smart_load_is_a_feeder_not_a_footnote(self):
        """계측·서버도 전력을 먹는다 — 피더로 잡아야 계약전력에 들어간다."""
        panels = {f.panel: f for f in electrical.FEEDERS}
        self.assertIn("LP-IT", panels)
        self.assertIn("LP-INST", panels)
        self.assertAlmostEqual(panels["LP-IT"].installed_kw, smart.it_installed_kw(), places=1)
        self.assertAlmostEqual(panels["LP-INST"].installed_kw,
                               smart.instrument_installed_kw(), places=1)
        self.assertAlmostEqual(smart.smart_installed_kw(), 14.8, places=1)
        # 케이블·차단기가 다른 피더와 같은 규칙을 받는다
        for tag in ("F13", "F14"):
            feeder = next(f for f in electrical.FEEDERS if f.tag == tag)
            with self.subTest(feeder=tag):
                self.assertIn(feeder.breaker_at, electrical.BREAKER_TRIPS_A + (20, 32, 40, 16))
                self.assertIn(tag, {c.feeder for c in wiring.power_cables()})

    def test_the_smart_layer_shortens_the_allowable_tap_distance(self):
        """전류가 늘면 전압강하 한계가 줄어든다 — 공짜가 아니다."""
        self.assertAlmostEqual(electrical.lv_tap_max_length_m(), 172.8, places=1)
        # 스마트 부하가 없었다면 얼마였는지를 같은 식으로 되짚는다
        without = electrical.demand_kw() - sum(
            f.demand_kw for f in electrical.FEEDERS if f.panel in ("LP-IT", "LP-INST"))
        ratio = without / electrical.demand_kw()
        self.assertAlmostEqual(electrical.lv_tap_max_length_m() / ratio, 183.6, delta=0.6)

    def test_the_smart_layer_stays_off_the_motion_bus(self):
        """수집 트래픽을 EtherCAT 에 얹으면 계측이 축을 흔든다.

        AI-04 가 재려는 것이 바로 추종오차인데, 그 신호를 수집하는 트래픽이
        같은 실시간 버스에 있으면 사이클 지터가 그대로 추종오차로 나타난다 —
        재려는 대상을 재는 행위가 망가뜨리는 구성이다.
        """
        chain = {c.panel for c in wiring.control_segments()}
        chain |= {c.feeder.split("→")[0] for c in wiring.control_segments()}
        self.assertNotIn("LP-IT", chain)
        self.assertNotIn("LP-INST", chain)
        # 그래도 급전은 받는다 — 전력 계통에는 있고 모션 버스에만 없다
        power = {c.panel for c in wiring.power_cables()}
        self.assertIn("LP-IT", power)
        self.assertIn("LP-INST", power)
        # 두 망이 만나는 곳은 OT/IT 경계 하나뿐이다
        firewall = [r for r in smart.RACK_ITEMS if "방화벽" in r.name]
        self.assertEqual(len(firewall), 1)
        self.assertTrue(firewall[0].redundant)

    def test_every_instrument_earns_its_place(self):
        """그 신호로 무엇을 결정하는지가 없으면 데이터만 늘린다."""
        case_tags = {case.tag for case in ai.CASES}
        for item in smart.INSTRUMENTS:
            with self.subTest(instrument=item.tag):
                self.assertIn(item.unlocks, case_tags, "여는 과제가 실재해야 한다")
                self.assertTrue(item.purpose.strip())
                self.assertGreater(item.qty, 0)
        self.assertEqual(sum(i.qty for i in smart.INSTRUMENTS), 46)

    def test_drawing_carries_the_smart_layer(self):
        sm = smart.summary()
        for token in (f"racks: {sm['racks']}",
                      f"rackU: {sm['rack_u']}",
                      f"edgeCabinets: {sm['edge_cabinets']}",
                      f"instruments: {sm['instruments']}",
                      f"plcTags: {sm['plc_tags']}",
                      f"timeseriesKbS: {sm['timeseries_kb_s']}",
                      f"visionRawMbS: {sm['vision_raw_mb_s']}",
                      f"visionKeptMbS: {sm['vision_kept_mb_s']}",
                      f"retentionPct: {sm['vision_retention_pct']}",
                      f"requiredMbps: {sm['required_mbps']}",
                      f"backboneMbps: {sm['backbone_mbps']}",
                      f"annualTb: {sm['annual_tb']}",
                      f"storageTb: {sm['storage_tb']}",
                      f"smartKw: {sm['smart_kw']}",
                      f"serverRoomX: {wiring.server_room_center_x_mm()}",
                      f"edgeCenterX: {wiring.edge_cabinet_center_x_mm()}",
                      # 가동시간은 라벨 공급과 저장이 전부 매달린 값이다.
                      # 도면만 계획정지를 안 뺀 값을 적으면 AI 시트가 조용히
                      # 6.7 % 과대한 표본을 약속한다.
                      f"hoursPerYear: {int(sm['hours_per_year'])}"):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        # 시트 3장이 도면 목록에 있어야 한다
        for sheet in ("PV-PLANT-SM-1012", "PV-PLANT-SM-1013", "PV-PLANT-AI-1014"):
            with self.subTest(sheet=sheet):
                self.assertIn(sheet, self.html)
        self.assertIn("'smart'", self.html, "탭이 selectTab 유효 목록에 있어야 한다")


class TestAiFeasibility(unittest.TestCase):
    """AI 적용 검토 — 등급이 스스로를 반박하지 않는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_grading_cannot_contradict_itself(self):
        """A 는 '지금 되는 것'이므로 신규 계측기를 요구할 수 없다."""
        self.assertTrue(ai.grading_is_consistent())
        # 지금 표가 일관되므로, 검사 코드가 죽어도 위 한 줄로는 안 잡힌다.
        # 어긋난 표를 일부러 넣어 실제로 걸러지는지까지 본다.
        good = ai.CASES[0]
        self.assertEqual(good.grade, "A")
        broken_a = dataclasses.replace(good, needs=("PM-901",))
        self.assertFalse(ai.grading_is_consistent((broken_a,)),
                         "A 인데 계측기를 요구하면 걸러야 한다")
        broken_b = dataclasses.replace(good, grade="B", needs=())
        self.assertFalse(ai.grading_is_consistent((broken_b,)),
                         "B 인데 무엇이 필요한지 없으면 걸러야 한다")
        broken_c = dataclasses.replace(good, grade="C", needs=("PM-901",))
        self.assertFalse(ai.grading_is_consistent((broken_c,)),
                         "안 하기로 한 것에 계측기를 적으면 걸러야 한다")
        for case in ai.CASES:
            with self.subTest(case=case.tag):
                self.assertIn(case.grade, ("A", "B", "C", "D"))
                if case.grade == "A":
                    self.assertEqual(case.needs, (), "A 인데 계측기가 필요하면 A 가 아니다")
                if case.grade == "B":
                    self.assertTrue(case.needs, "B 는 무엇이 붙어야 되는지 적어야 한다")
                if case.grade in ("C", "D"):
                    self.assertEqual(case.needs, ())
                    self.assertTrue(case.caveat.strip(), "안 하는 이유를 적어야 한다")

    def test_label_supply_sets_the_start_date(self):
        """가장 희소한 클래스가 착수 시점을 지배한다."""
        labels = ai.annual_labels()
        self.assertEqual(ai.annual_panels(), 308_138)
        self.assertEqual(labels["정상"], 272_189)
        self.assertEqual(labels["유리 깨짐"], 25_678)
        self.assertEqual(labels["전손"], 10_271)
        self.assertEqual(ai.scarcest_label(), "전손")
        self.assertAlmostEqual(ai.cold_start_months(), 1.2, places=1)
        # 처음부터 학습을 물리치는 근거가 **바뀌었다.** 1교대 가정에서는
        # 전손 기준 24개월이라 "비현실적" 이었는데, 2교대 확정으로 11.7개월이
        # 됐다 — 절대 개월수로는 더 이상 그 말을 못 한다.
        #
        # 그래도 전제는 그대로다. 근거가 절대값이 아니라 **배수**이기 때문이다:
        # 처음부터 학습은 표본이 10배 필요하므로 언제나 착수가 10배 늦다.
        # 가동시간이 어떻게 바뀌어도 이 비는 변하지 않는다.
        scratch = ai.months_to_threshold("전손", ai.SCRATCH_MIN_SAMPLES)
        self.assertAlmostEqual(scratch, 11.7, places=1)
        # 개월수는 0.1 로 반올림돼 나오므로(11.7 / 1.2 = 9.75) 비는 반올림
        # 전의 값으로 잰다 — 재는 자가 반올림에 흔들리면 안 된다.
        self.assertAlmostEqual(
            ai.SCRATCH_MIN_SAMPLES / labels["전손"]
            / (ai.TRANSFER_MIN_SAMPLES / labels["전손"]),
            ai.SCRATCH_MIN_SAMPLES / ai.TRANSFER_MIN_SAMPLES, places=6)
        self.assertGreater(scratch, 10.0, "그래도 한 해 가까이 늦다")
        # 가동시간이 두 배면 착수도 절반이 된다 (파생값이라는 확인)
        self.assertAlmostEqual(
            ai.TRANSFER_MIN_SAMPLES / labels["전손"] * 12.0, ai.cold_start_months(), places=1)

    def test_misclassification_is_priced_in_seconds_not_percent(self):
        """정확도 % 는 공정에서 뜻이 없다."""
        self.assertAlmostEqual(ai.scrap_miss_cost_s(), 45.0, places=1)
        self.assertAlmostEqual(ai.cracked_miss_cost_s(), 47.04, places=2)
        self.assertEqual(ai.scrap_miss_cost_s(), campaign.JBR_S)
        self.assertGreater(ai.scrap_miss_cost_s(), campaign.INFEED_REJECT_S,
                           "전손은 투입부 15 s 로 끝나야 하는데 통과하면 병목을 먹는다")

    def test_we_say_no_where_ai_is_not_the_answer(self):
        """기구가 이미 푸는 문제에 학습을 얹지 않는다."""
        declined = {case.tag for case in ai.by_grade("C")}
        self.assertEqual(declined, {"AI-09", "AI-10"})
        pose = next(c for c in ai.CASES if c.tag == "AI-10")
        self.assertIn("3-2-1", pose.caveat, "vision.py 의 최소화 근거와 같은 이유여야 한다")
        sched = next(c for c in ai.CASES if c.tag == "AI-09")
        self.assertIn(campaign.bottleneck(), sched.caveat)
        # 불가한 것도 무엇이 없어서인지 적는다
        for case in ai.by_grade("D"):
            with self.subTest(case=case.tag):
                self.assertIn("없", case.data + case.label)

    def test_required_instruments_are_all_actually_ordered(self):
        """B 과제가 요구하는 계측기가 계측 목록에 없으면 착수 못 한다."""
        ordered = {item.tag for item in smart.INSTRUMENTS}
        for tag in ai.required_instruments():
            with self.subTest(instrument=tag):
                self.assertIn(tag, ordered)
        self.assertEqual(len(ai.startable_now()), 8)
        self.assertEqual(ai.grade_counts(), {"A": 3, "B": 5, "C": 2, "D": 2})

    def test_drawing_carries_the_ai_review(self):
        a = ai.summary()
        for token in (f"cases: {a['cases']}",
                      f"gradeA: {a['grades']['A']}",
                      f"gradeB: {a['grades']['B']}",
                      f"annualPanels: {a['annual_panels']}",
                      f"labelScrap: {a['labels']['전손']}",
                      f"coldStartMonths: {a['cold_start_months']}",
                      f"scrapMissS: {a['scrap_miss_s']}",
                      f"crackedMissS: {a['cracked_miss_s']}"):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        # 시트가 마크다운 별표를 그대로 그리면 안 된다
        self.assertIn("function plain(value)", self.html)
        self.assertIn("replace(/\\*\\*/g, '')", self.html)


class TestMounting(unittest.TestCase):
    """REV.26 지지·장착 — 부품이 무엇에 얹혀 있는지가 형상과 값으로 있는가."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_every_cell_has_a_mounting_spec(self):
        self.assertTrue(mounting.stations_are_covered())
        # 셀이 하나 늘면 장착 사양도 따라와야 한다 — 검사가 살아 있는지 확인한다
        self.assertFalse(mounting.stations_are_covered(set(layout.STATIONS) | {"newcell"}))
        self.assertFalse(mounting.stations_are_covered(set()))
        for key, m in mounting.MOUNTING_OF.items():
            with self.subTest(station=key):
                self.assertTrue(m.anchors, "앵커 없는 셀은 서 있을 수 없다")
                self.assertGreaterEqual(m.total_anchors, 4, "베이스플레이트 하나에 최소 4본")
                self.assertGreater(m.grout_mm, 0)
                self.assertTrue(m.plate.strip())
                self.assertTrue(m.note.strip(), "왜 이렇게 잡았는지가 있어야 한다")

    def test_anchor_text_is_generated_not_typed(self):
        """표제란 문장을 손으로 적으면 모델과 어긋난다 — 데이터에서 만든다."""
        block = self.html[self.html.index("  var stations = {"):
                          self.html.index("  var register = [")]
        for key in mounting.MOUNTING_OF:
            with self.subTest(station=key):
                self.assertIn("anchors: '" + mounting.anchor_text(key) + "'", block)
        # 합계는 기초도면으로 넘기는 값이라 못 박는다
        self.assertEqual(mounting.total_anchors(), 190)
        self.assertEqual(mounting.anchors_by_bolt(), {"M16": 94, "M20": 88, "M24": 8})
        # '/기' 는 개소마다라는 뜻이다 — 곱해지지 않으면 수량이 반이 된다
        grm = mounting.MOUNTING_OF["grm"]
        mast = next(a for a in grm.anchors if a.target == "마스트")
        self.assertTrue(mast.per_unit)
        self.assertEqual(mast.total, mast.count * mast.units)
        self.assertEqual(grm.total_anchors, 36)

    def test_the_anchor_plan_has_something_to_hold_down(self):
        """'랙 8×M20' 이라고 적었으면 받칠 랙 다리가 3D 에 있어야 한다.

        REV.25 까지 grm 의 앵커 계획은 랙·마스트·탠덤 빔·후드를 정확히 적고
        있었는데 3D 에는 랙 다리도 갠트리 기둥도 없었다 — 5단 랙 24메시가
        바닥에서 600 mm 뜬 채 서 있었다. 사양은 글로 있고 형상이 없었다.
        """
        for member in mounting.MEMBERS:
            with self.subTest(member=member.label):
                # 파일 어딘가에 있는지가 아니라 **두 번** 있는지를 본다 —
                # MOUNT_MEMBERS 리터럴에 한 번, 3D 부재 라벨로 한 번.
                # 하나만 있으면 표에는 있는데 형상이 없다는 뜻이고, 그것이
                # REV.25 까지의 상태였다.
                self.assertGreaterEqual(
                    self.html.count("'" + member.label + "'"), 2,
                    "표에만 있고 3D 에 형상이 없다")
                self.assertIn(member.support, mounting.SUPPORT_CLASSES)
                self.assertTrue(member.carries.strip())
        # 앵커 계획이 대상을 이름으로 부른 셀은 그 대상을 받치는 부재가 있어야 한다
        for key in ("grm", "afr", "afu"):
            with self.subTest(station=key):
                self.assertTrue(mounting.members_of(key), f"{key} 에 지지 부재가 없다")
        self.assertEqual(mounting.members_by_class()["floor"], 16)

    def test_brackets_came_from_measured_gaps(self):
        """브래킷은 임의로 세운 것이 아니라 잰 것이다 — 전부 도면에 있어야 한다."""
        self.assertEqual(mounting.BRACKET_SERIES, 53)
        self.assertEqual(mounting.BRACKET_COUNT, 51)
        for tag in mounting.bracket_tags():
            with self.subTest(bracket=tag):
                self.assertIn(tag + " 지지 브래킷", self.html)
        # 폐번은 도면에 없어야 하고, 왜 물렸는지가 남아야 한다
        for tag, why in mounting.BRACKET_WITHDRAWN:
            with self.subTest(withdrawn=tag):
                # 부품으로는 없어야 한다. 폐번 사유를 적은 주석에는 이름이 남는다 —
                # 그게 이 번호를 다시 쓰지 않는 근거다.
                self.assertNotIn(tag + " 지지 브래킷", self.html)
                self.assertGreater(len(why), 20, "폐번 사유가 한 줄은 있어야 한다")
        # 번호는 재사용하지 않는다 — 채번 범위 밖은 비어 있어야 한다
        self.assertNotIn(f"{mounting.BRACKET_PREFIX}{mounting.BRACKET_SERIES + 1:03d}", self.html)

    def test_exemptions_are_named_and_justified(self):
        """받칠 대상이 아닌 것은 근거와 함께 적는다 — 늘리기 쉬우면 안 된다."""
        self.assertEqual(len(mounting.UNSUPPORTED_BY_DESIGN), 5)
        for label, why in mounting.UNSUPPORTED_BY_DESIGN:
            with self.subTest(label=label):
                # 라벨 **로 시작하는 문자열 리터럴**이 도면에 있어야 한다.
                # 완전일치로 재지 않는 것은 CRN-901 처럼 한 덩어리가 메시 8개에
                # 걸리는 예외가 있어서다 — 검사 도구도 includes 로 잡는다.
                self.assertRegex(self.html, "'" + re.escape(label) + "[^']*'")
                self.assertTrue(why.strip())
        # 검사 도구의 예외 목록과 같아야 한다 — 둘이 갈라지면 검사가 헐거워진다
        tool = pathlib.Path("tools/check_load_path.mjs").read_text(encoding="utf-8")
        for label, _ in mounting.UNSUPPORTED_BY_DESIGN:
            with self.subTest(label=label):
                self.assertIn("'" + label + "'", tool)
        self.assertIn("ADJACENCY_M = 0.03", tool)
        self.assertIn("FLOOR_M = 0.05", tool)

    def test_drawing_carries_the_mounting_sheet(self):
        sm = mounting.summary()
        for token in (f"anchors: {sm['anchors']}",
                      f"m16: {sm['by_bolt']['M16']}",
                      f"m20: {sm['by_bolt']['M20']}",
                      f"m24: {sm['by_bolt']['M24']}",
                      f"members: {sm['members']}",
                      f"brackets: {sm['brackets']}",
                      f"exempt: {sm['exempt']}"):
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertIn("PV-PLANT-MT-1015", self.html, "도면 목록에 장착 상세가 없다")
        self.assertIn("'mount'", self.html, "탭이 selectTab 유효 목록에 있어야 한다")
        self.assertIn("fitSheet(mountSvg);", self.html, "장착 시트도 같은 맞춤을 받아야 한다")
        # 볼트 배치는 개수에서 파생한다 — 상수로 박으면 개수가 바뀔 때 안 따라온다
        self.assertIn("function plateBolts(count)", self.html)


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
        self.assertAlmostEqual(electrical.installed_kw(), 299.0, places=1)
        self.assertAlmostEqual(electrical.demand_kw(), 217.10, places=1)
        self.assertEqual(electrical.main_breaker_at(), 500)
        self.assertEqual(electrical.main_breaker_frame_a(), 630)
        self.assertAlmostEqual(electrical.contract_kva(), 325.65, places=0)
        # **예고한 대로 됐다.** REV.25 에서 "다음에 F14 만한 부하를 하나 더
        # 붙이면 차단기가 한 단 올라간다" 고 적었고, REV.28 크레인이 여유를
        # 2.6 kW 까지 줄였고, REV.34 압축공기 4.25 kW 가 그것을 넘겼다.
        #
        # 400 → 500 AT 로 올라가며 주회로도 240 → 300 mm² 가 됐다. 그 대신
        # 여유가 52.2 kW 로 열렸다 — 다음 부하는 이 안에서 받는다.
        self.assertAlmostEqual(electrical.breaker_headroom_kw(), 52.2, places=1)
        air_feeder = next(f for f in electrical.FEEDERS if f.tag == "F16")
        self.assertGreater(electrical.breaker_headroom_kw(), air_feeder.demand_kw,
                           "한 단 올린 뒤에는 같은 크기 부하를 또 받을 수 있어야 한다")
        # 400 AT 로는 안 됐다는 것이 이 회차의 근거다 — 되짚어 확인한다
        self.assertGreater(electrical.demand_current_a(), 400 * 0.9,
                           "수요 전류가 400 AT 의 90 % 를 넘으면 한 단 올린다")
        ir = [f for f in electrical.FEEDERS if f.panel.startswith("LP-GRM-IR")]
        self.assertEqual(len(ir), 2, "175 kW 를 한 피더에 몰면 차단기가 주차단기와 맞먹는다")
        for feeder in ir:
            with self.subTest(feeder=feeder.tag):
                self.assertLess(feeder.breaker_at, electrical.main_breaker_at())

    def test_the_load_centre_moved_and_the_board_followed(self):
        """최대 부하가 하류 끝에 생겼는데 반을 그대로 두면 규칙과 어긋난다."""
        centre = wiring.demand_center_x_mm()
        # 값이 아니라 **규칙**을 못 박는다. 500 단위 반올림이면 중심과 반 위치는
        # 최대 250 까지 벌어지는 것이 정상이라, delta 200 으로 재면 규칙을 지킨
        # 배치에서도 실패한다 — REV.25 에서 실제로 그렇게 실패했다.
        self.assertEqual(wiring.MDB_POSITION_MM[0], round(centre / 500) * 500)
        self.assertLessEqual(abs(wiring.MDB_POSITION_MM[0] - centre), 250)
        # 하류 IR 뱅크가 중심을 끌고 내려간 상태는 그대로여야 한다
        self.assertGreater(centre, 40_000, "IR 뱅크가 부하중심을 하류로 끌었다")
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
        self.assertEqual(thermal.required_airflow_m3h(), 35000)
        # 랙실은 구획실이라 그 발열은 공정실 환기에 들어오지 않는다
        self.assertAlmostEqual(thermal.off_room_kw(), 13.01, places=2)
        self.assertEqual(thermal.OFF_ROOM_PANELS, ("LP-IT", "LP-AIR"))
        # 배기가 실패하면 어떻게 되는지를 값으로 남긴다 — 후드가 전제라는 근거
        def airflow(room_kw):
            return room_kw * 3600.0 / (1.2 * 1.005 * thermal.ROOM_DELTA_T_C)

        room = thermal.room_load_kw()
        self.assertAlmostEqual(airflow(room), 34_988, delta=200)
        self.assertAlmostEqual(airflow(room + thermal.ir_useful_kw()), 85_917, delta=300,
                               msg="냉각 후드가 현열을 못 잡으면 환기가 2.5 배가 된다")
        self.assertAlmostEqual(
            airflow(room + thermal.ir_useful_kw() + thermal.ir_enclosure_loss_kw()),
            113_331, delta=400, msg="둘 다 실내로 오면 환기가 3.2 배가 된다")

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


class TestKinematics(unittest.TestCase):
    """반전기 투입 기구학 — 패널이 지나가는 자리.

    발주처 지적 "패널이 반전기에 투입될 때 간섭이 생겨" 를 재현하고, 같은
    결함이 다시 들어오면 실패하는 불변식으로 못 박는다.
    """

    @classmethod
    def setUpClass(cls):
        with io.open(DRAWING, encoding="utf-8") as handle:
            cls.html = handle.read()

    def test_the_panel_fits_between_the_end_rings(self):
        """REV.26 은 패널이 케이지보다 **길어서** 애초에 들어가지 않았다.

        3D 의 알루미늄 프레임이 2,500 × 1,400 유리 바깥에 붙어 조립체가
        2,615 × 1,515 였다 — 케이지 안지름 2,580 보다 35 mm 길다.
        """
        self.assertGreater(kinematics.cage_axial_clearance_mm(), 0,
                           "패널이 두 엔드링 사이에 들어가지 않는다")
        self.assertGreaterEqual(kinematics.cage_axial_clearance_mm(), 20)
        # 규격을 벗어난 패널을 넣으면 반드시 걸려야 한다.
        span = kinematics.cage_clear_span_mm()
        self.assertLess((span - 2615) / 2, 0, "2,615 짜리 패널은 들어가면 안 된다")

    def test_the_panel_passes_under_the_ring_and_over_the_carriage(self):
        """수평 이송은 캐리지 상단과 링 하단 사이 창을 지나간다.

        REV.26 은 그 창이 130 mm 였고 이송면이 링에 **22 mm** 까지 붙어
        있었다 — 설계값이 아니라 우연이다. 반전축을 130 올려 창을 260 으로
        벌리고 위아래를 100 mm 넘게 뒀다.
        """
        self.assertGreaterEqual(kinematics.under_ring_clearance_mm(), 100)
        self.assertGreaterEqual(kinematics.over_carriage_clearance_mm(), 100)
        # 옛 반전축(3,300)으로 되돌리면 링 여유가 100 밑으로 떨어진다.
        old = kinematics.FLIP_AXIS_MM - 130
        old_gap = (old - kinematics.ring_outer_r_mm()) - (
            kinematics.TRANSFER_MM + kinematics.PANEL_TOP_OFFSET_MM)
        self.assertLess(old_gap, 0, "옛 축 높이에서는 이송면이 링에 걸린다")

    def test_the_panel_fits_the_ring_bore(self):
        """반전축에 앉았을 때 패널 단면이 통과 구멍 안이어야 한다."""
        self.assertGreater(kinematics.bore_clearance_mm(), 0)
        self.assertEqual(round(kinematics.ring_bore_r_mm() * 2), 1620)

    def test_the_path_never_climbs_while_crossing_a_ring(self):
        """REV.26 의 결함 그 자체 — 링 평면을 가로지르면서 올라갔다.

        지금 경로가 이미 맞아서 검사 코드가 죽어도 모르는 일을 막으려고
        어긋난 경로를 주입해 실제로 걸리는지까지 본다.
        """
        self.assertTrue(kinematics.crossing_is_level())
        bad = tuple((t0, t1, name, True) if name == kinematics.CROSSING_PHASE else (t0, t1, name, climbs)
                    for t0, t1, name, climbs in kinematics.PATH)
        self.assertFalse(kinematics.crossing_is_level(bad),
                         "가로지르며 올라가는 경로를 걸러내지 못한다")

    def test_the_clamp_jaw_reaches_the_panel_and_opens_clear_of_it(self):
        """조가 물어야 할 패널에서 660 mm 떨어져 있었고, 하강 경로를 막았다."""
        # 무는 자리는 패널 장변 프레임의 중심이다.
        self.assertAlmostEqual(kinematics.JAW_CLOSED_Z_MM, kinematics.PANEL_MM[1] / 2 - 27.5, places=1)
        # 여는 자리는 패널 반폭 밖이라 두 링 사이 하강 경로를 비운다.
        self.assertGreater(kinematics.jaw_open_clearance_mm(), 0,
                           "조를 열어도 패널이 내려갈 길이 없다")
        self.assertGreater(kinematics.jaw_stroke_mm(), 100)

    def test_the_afr_clamp_portal_stands_where_nothing_else_does(self):
        """상부에서 내려오는 것에는 그것을 매달 것이 있어야 한다.

        CL-221 4기(합 12 kN)가 y 1,030…1,950 에 서 있는데 1,950 위가 비어
        있었다. 기둥 자리는 통과 폭·셔틀·LM 레일 밖, 가드 안쪽에서만 난다.
        """
        self.assertEqual(kinematics.afr_clamp_reaction_kn(), 12.0)
        self.assertTrue(kinematics.afr_portal_is_clear())
        self.assertEqual(kinematics.AFR_CROSSHEAD_SOFFIT_MM, kinematics.AFR_CLAMP_TOP_MM,
                         "크로스헤드 하면이 클램프 상단과 같아야 매달린다")
        for _name, limit in kinematics.AFR_PORTAL_OBSTACLES_MM:
            with self.subTest(limit=limit):
                self.assertFalse(kinematics.afr_portal_is_clear(limit - 1),
                                 "장애물 안쪽에 세운 기둥을 걸러내지 못한다")
        self.assertFalse(kinematics.afr_portal_is_clear(kinematics.AFR_GUARD_Z_MM + 1),
                         "가드 밖에 세운 기둥을 걸러내지 못한다")
        self.assertEqual(kinematics.afr_portal_anchor_total(), 16)

    def test_the_portal_and_the_jaw_exist_in_the_drawing(self):
        """모델에만 있고 3D 에 형상이 없으면 §25 와 같은 병이다.

        표에 한 번·3D 에 한 번, 두 번 나와야 한다.
        """
        for label in ("AFR CL-221 클램프 포탈 기둥 4본",
                      "AFR CL-221 포탈 크로스헤드 2본",
                      "AFR 클램프 포탈 종방향 타이빔 2본",
                      "VAC-101 진공 스키드 베이스"):
            with self.subTest(label=label):
                self.assertGreaterEqual(self.html.count("'" + label + "'"), 2,
                                        "표에만 있고 3D 에 형상이 없다")
        self.assertIn("4점 단장 클램프 ${sg<0?", self.html)
        self.assertIn("클램프 z축 가이드 포스트 4본", self.html)

    def test_the_drawing_carries_the_same_numbers(self):
        for key, value in kinematics.summary().items():
            if isinstance(value, list):
                continue
            with self.subTest(key=key):
                self.assertIn(f"{key}: {value:g}" if isinstance(value, float)
                              else f"{key}: {value}", self.html)

    def test_the_3d_uses_the_model_numbers(self):
        """3D 상수가 모델에서 떨어져 나가면 **영상만** 옛 설계로 돌아간다.

        파이썬은 통과하는데 기구는 틀린 상태가 된다 — 변이 시험에서 실제로
        두 건이 그렇게 살아남았다(이송면 2.29 → 2.25, 조 여닫이 삭제).
        기하 검사(`tools/check_clearance.mjs`)는 잡지만 CI 의 파이썬은 못 봤다.
        그래서 리터럴을 모델에서 직접 못 박는다.
        """
        def js(mm: float) -> str:
            """미니파이 소스가 쓰는 표기 — 0.86 은 .86 으로 적힌다."""
            text = f"{mm / 1000:g}"
            return text[1:] if text.startswith("0.") else text

        self.assertIn(f"var At={js(kinematics.FLIP_AXIS_MM)},"
                      f"pvTv={js(kinematics.TRANSFER_MM)},", self.html,
                      "반전축·이송면 3D 상수가 모델과 다르다")
        # 조는 반전 구간에만 물고, 진입·하강 구간에는 열려 있어야 한다.
        self.assertIn(f"jg.position.set(0,0,sg*{js(kinematics.JAW_OPEN_Z_MM)})", self.html)
        self.assertIn(f"le({js(kinematics.JAW_OPEN_Z_MM)},"
                      f"{js(kinematics.JAW_CLOSED_Z_MM)},cj)", self.html,
                      "조가 여닫이 없이 한 자리에 고정돼 있다")

    def test_the_checker_and_the_model_share_one_list(self):
        """검사 도구의 예외 목록이 모델과 어긋나면 검사가 뜻을 잃는다.

        **양방향으로** 본다. 한쪽만 훑으면 모델에서 낱말을 빼도 통과한다 —
        루프가 도는 횟수만 줄 뿐이라 아무도 모른다. §24·§25 에서 세 번 겪은
        그 병이라 여기서는 집합으로 맞춘다.
        """
        tool = (pathlib.Path(__file__).resolve().parents[1]
                / "tools" / "check_clearance.mjs").read_text(encoding="utf-8")

        def words(const: str) -> set[str]:
            body = tool[tool.index(f"const {const} = ["):]
            return set(re.findall(r"'([^']+)'", body[:body.index("];")]))

        for const, model in (("WORKPIECES", kinematics.WORKPIECES),
                             ("DESIGN_CONTACTS", kinematics.DESIGN_CONTACTS),
                             ("PASS_THROUGH", kinematics.PASS_THROUGH)):
            with self.subTest(const=const):
                self.assertEqual(words(const), set(model),
                                 f"{const} 가 모델과 검사 도구에서 다르다")


class TestCrane(unittest.TestCase):
    """CRN-901 5 t 천장크레인 — 천장고 12,000 이 확정된 뒤의 인양 계통.

    발주처가 천장고와 용량을 정해 줬으므로 여기서 지킬 것은 하나다:
    **후크 높이를 천장고와 혼동하지 않는 것.** 12 m 천장을 보고 12 m 를 들
    수 있다고 적는 것이 이 종류 설계에서 가장 흔한 오독이다.
    """

    #: 3D 월드 원점의 플랜트 X (mm). 도면 전체가 쓰는 좌표 규약이라
    #: 여기서만 쓰는 값이 아니다 — world_x = (plant_x − 이 값) / 1000.
    WORLD_ORIGIN_X_MM = 24_750

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    # ── 높이 계통 ────────────────────────────────────────────────────────
    def test_hook_height_is_not_the_ceiling_height(self):
        """후크가 올라가는 높이는 천장고에서 크레인 두께를 뺀 값이다."""
        self.assertEqual(crane.CEILING_MM, 12_000)
        self.assertEqual(crane.rail_top_mm(), 10_750)
        self.assertEqual(crane.hook_height_mm(), 9_700)
        # 값이 아니라 **식**을 못 박는다. 상수를 바꾸면 따라와야 한다.
        self.assertEqual(
            crane.hook_height_mm(),
            crane.CEILING_MM - crane.ROOF_CLEARANCE_MM
            - crane.CRANE_ABOVE_RAIL_MM - crane.HOOK_APPROACH_MM)
        self.assertLess(crane.hook_height_mm(), crane.CEILING_MM - 2_000,
                        "천장고를 그대로 후크 높이로 적으면 2.3 m 를 지어내는 것이다")

    def test_lifting_needs_more_headroom_than_the_object_is_tall(self):
        """슬링과 후크 블록은 물건 **위**에 있다 — 빠뜨리면 2.5 m 를 잃는다."""
        tall = crane.tallest_lift()
        self.assertEqual(tall.name, "VG-101 독립 방진 비전보 조립체")
        self.assertEqual(crane.required_hook_mm(tall),
                         tall.height_mm + crane.sling_height_mm()
                         + crane.HOOK_BLOCK_MM + crane.GROUND_LIFT_MM)
        self.assertEqual(crane.required_hook_mm(tall), 8_370)
        self.assertEqual(crane.hook_margin_mm(), 1_330)
        # 슬링 높이는 상수가 아니라 폭과 각에서 나온다. REV.28 은 "60° · 폭
        # 2.9 m 기준" 이라 적고 값은 2,000 을 썼는데, 그 값이 되려면 각이
        # 54° 여야 한다 — 눕은 쪽이라 다리 장력을 과소평가하는 방향이었다.
        self.assertEqual(crane.sling_height_mm(), 2_520)
        self.assertEqual(crane.sling_height_mm(angle_deg=54), 2_000)
        self.assertGreater(crane.sling_height_mm(spread_mm=4_000),
                           crane.sling_height_mm())
        # 목록의 **전부**가 들려야 한다 — 가장 높은 하나만 보면 정렬이 바뀔 때
        # 조용히 못 드는 것이 생긴다.
        for lift in crane.LIFTS:
            with self.subTest(lift=lift.name):
                self.assertLessEqual(crane.required_hook_mm(lift),
                                     crane.hook_height_mm())

    def test_capacity_is_set_by_the_heaviest_single_piece(self):
        gov = crane.governing_lift()
        self.assertEqual(gov.name, "BFC 반전 카세트 (Bay 1식)")
        self.assertEqual(gov.mass_kg, 2_500)
        self.assertEqual(crane.capacity_kg(), 5_000)
        # **정격이 받는 것은 물건이 아니라 후크에 걸린 전부다.** 부속 자중을
        # 빼고 재면 여유를 실제보다 크게 적게 된다.
        self.assertEqual(crane.hook_load_kg(gov), 2_650)
        self.assertEqual(crane.capacity_margin(), 1.89)
        self.assertGreaterEqual(crane.capacity_margin(), 1.5,
                                "확인값이 '2,500 이상' 이라 위가 열려 있다 — 여유가 필요하다")
        # 확인값의 위가 열려 있으므로 **어디까지 되는지**가 답의 일부다
        self.assertEqual(crane.max_lift_kg(), 4_850)
        self.assertTrue(crane.fits_capacity())
        self.assertTrue(crane.fits_capacity(4_850))
        self.assertFalse(crane.fits_capacity(4_860),
                         "부속 자중을 안 빼면 5,000 까지 된다고 적게 된다")
        for lift in crane.LIFTS:
            with self.subTest(lift=lift.name):
                self.assertTrue(crane.fits_capacity(lift.mass_kg))
                self.assertTrue(lift.basis.strip(), "중량의 근거가 없으면 숫자가 아니다")

    def test_it_cannot_carry_over_installed_equipment(self):
        """넘길 수 없다는 사실이 시공 순서를 정한다 — 크레인 사양이 아니다."""
        tallest_fixed = layout.plant_envelope_mm()[2]
        self.assertEqual(tallest_fixed, 5_150)
        self.assertEqual(crane.carry_over_hook_mm(tallest_fixed), 12_970)
        self.assertGreater(crane.carry_over_hook_mm(tallest_fixed),
                           crane.hook_height_mm(),
                           "넘길 수 있으면 시공 순서를 논할 이유가 없다")
        self.assertGreater(crane.carry_over_hook_mm(tallest_fixed), crane.CEILING_MM,
                           "천장을 키워도 안 되는 값이라야 순서로 푸는 것이 답이 된다")
        # 거더 하면은 설비 최고점 위로 넉넉히 뜬다 — 넘기는 것과는 다른 이야기다
        self.assertEqual(crane.clears_plant(tallest_fixed), 5_600)

    def test_the_install_order_runs_against_the_process_flow(self):
        """반입 동선이 곧 안 세운 장비 밴드라, 먼 쪽부터 소비해야 한다.

        REV.28 의 주석은 "반입은 통로를 따라" 라고 적었는데 틀렸다 — 통로
        유효폭 900 으로는 폭 2,900 짜리 반전 카세트가 못 지난다. 통로는
        사람이 다니는 길이고, 반입 동선은 폭 7,100 의 장비 밴드다.
        """
        flow = [zone.key for zone in layout.build_zones()]
        # 출입구가 투입방향(상류)이라는 것은 발주처 확인값이다 — 건축이 이미
        # 그렇게 설계돼 있다. 확인 전에는 지게차 진입측에서 미루어 잡았다.
        self.assertEqual(crane.ENTRY_ZONE, "afu")
        self.assertEqual(flow[0], crane.ENTRY_ZONE, "출입구는 공정 상류에 있다")
        self.assertEqual(crane.install_order(), tuple(reversed(flow)))
        self.assertEqual(crane.install_order()[0], "grm", "가장 먼 쪽을 먼저")
        self.assertEqual(crane.install_order()[-1], crane.ENTRY_ZONE, "문 쪽이 마지막")
        # 문이 반대쪽에 있으면 순서도 뒤집혀야 한다 — 규칙이지 값이 아니다
        self.assertEqual(crane.install_order(entry_zone="grm"), tuple(flow))

    def test_the_aisle_is_not_the_haul_route(self):
        """통로를 반입 동선으로 적으면 폭이 세 배 모자란 계획이 된다."""
        self.assertEqual(crane.widest_module_mm(), 2_900)
        self.assertEqual(crane.widest_module_mm(),
                         layout.STATIONS[crane.governing_lift().station].envelope[1])
        self.assertEqual(crane.haul_width_mm(), layout.MACHINE_BAND_Y_MM)
        self.assertGreater(crane.haul_width_mm(), crane.widest_module_mm())
        self.assertFalse(crane.aisle_can_haul(wiring.aisle_clear_width_mm()),
                         "유효 900 통로로 2,900 모듈이 지나갈 수 없다")
        self.assertTrue(crane.aisle_can_haul(3_000), "경계가 실제로 작동하는지")
        # 개구 하한은 **치수가 아니라 하한**이다. 높이를 정하는 VG-101 은
        # 보 + 기둥 2본이라 통짜로 올 물건이 아니고, 무엇이 통짜로 오는지는
        # 분할 반입 계획(벤더 몫)에 달렸다 — 그 조건을 도면이 같이 적는다.
        self.assertEqual(crane.entry_opening_min_mm(), (2_900, 5_150))
        self.assertEqual(crane.entry_opening_min_mm()[0], crane.widest_module_mm())
        self.assertEqual(crane.entry_opening_min_mm()[1],
                         max(lift.height_mm for lift in crane.LIFTS))
        # 개구 실치수는 발주처 확인값이다. 폭은 넉넉하고 높이가 반입 방식을
        # 가른다 — 그 판정을 값으로 못 박는다.
        self.assertEqual(crane.ENTRY_OPENING_MM, (6_000, 5_000))
        self.assertEqual(crane.entry_width_margin_mm(), 3_100)
        self.assertTrue(crane.entry_opening_covers_plan(),
                        "폭은 눕혀도 안 줄어드는 치수가 있어 개구가 직접 받아야 한다")
        # 최중량은 세운 채 들어오지만 운반대에 500 밖에 안 남는다 —
        # 저상 대차 전용이고 일반 트레일러 베드(1,000+)로는 못 들어온다
        self.assertEqual(crane.upright_bed_headroom_mm(), 500)
        self.assertIn(crane.governing_lift(), crane.upright_lifts(400))
        self.assertNotIn(crane.governing_lift(), crane.upright_lifts(600))
        # 가장 높은 VG-101 은 개구보다 높다 — 조립체 높이지 반입 단위가 아니다
        tall = crane.tallest_lift()
        self.assertLess(crane.upright_bed_headroom_mm(tall), 0)
        self.assertEqual(len(crane.upright_lifts(0)), len(crane.LIFTS) - 1)
        self.assertIn("세운 채 반입", self.html)
        self.assertIn("안에서 조립", self.html)
        # 종전의 틀린 문장이 되살아나면 실패한다
        source = (pathlib.Path(__file__).resolve().parents[1]
                  / "src" / "pv_preprocess" / "crane.py").read_text(encoding="utf-8")
        self.assertNotIn("반입은 통로(Y 7,100–8,300)를 따라\n제자리 옆까지", source)

    # ── 평면 계통 ────────────────────────────────────────────────────────
    def test_the_span_is_set_by_the_machine_band(self):
        """스팬은 고른 값이 아니라 밴드를 덮어야 나오는 값이다."""
        self.assertEqual(crane.MACHINE_BAND_MM, layout.MACHINE_BAND_Y_MM)
        self.assertEqual(crane.hook_reach_z_mm(), 3_800)
        self.assertTrue(crane.covers_machine_band())
        # 인자를 열어 둔 뜻 — 지금 값이 마침 맞아서 검사가 죽어도 모르는 일을 막는다
        self.assertFalse(crane.covers_machine_band(7_000))
        self.assertFalse(crane.covers_machine_band(8_200))
        self.assertTrue(crane.covers_machine_band(8_400))

    def test_the_crane_fits_under_the_confirmed_ceiling(self):
        self.assertTrue(crane.fits_under_ceiling())
        self.assertFalse(crane.fits_under_ceiling(11_000))
        self.assertTrue(crane.fits_under_ceiling(12_000))

    def test_the_runway_covers_the_plant_from_both_ends(self):
        """주행거더는 양끝 같은 오버행으로 걸리고, 접근여유를 빼도 전장을 덮는다."""
        length = layout.plant_envelope_mm()[0]
        self.assertEqual(wiring.crane_runway_overhang_mm(), 1_000)
        self.assertEqual(crane.RUNWAY_MM, length + 2 * wiring.crane_runway_overhang_mm())
        # 엔드트럭 접근여유를 뺀 뒤에도 후크가 양끝 밖까지 나가야 한다
        self.assertGreater(wiring.crane_runway_overhang_mm(), crane.BRIDGE_APPROACH_MM)
        self.assertEqual(wiring.crane_runway_overhang_mm() - crane.BRIDGE_APPROACH_MM, 300)

    def test_the_festoon_is_fed_at_the_middle_of_the_runway(self):
        """끝에서 먹이면 트레일링 케이블과 전압강하가 두 배가 된다."""
        length = layout.plant_envelope_mm()[0]
        self.assertEqual(wiring.crane_feed_x_mm(), length // 2)
        self.assertEqual(wiring.lp_positions_mm()["LP-CRANE"], wiring.crane_feed_x_mm())

    # ── 전기 ─────────────────────────────────────────────────────────────
    def test_the_crane_has_its_own_feeder(self):
        feeder = next(f for f in electrical.FEEDERS if f.panel == "LP-CRANE")
        self.assertEqual(feeder.tag, "F15")
        self.assertAlmostEqual(feeder.installed_kw, crane.installed_kw(), places=2)
        self.assertAlmostEqual(feeder.diversity, crane.DIVERSITY, places=3)
        self.assertAlmostEqual(feeder.demand_kw, crane.demand_kw(), places=2)
        self.assertEqual(crane.installed_kw(), 6.7)
        # 급전 케이블이 스케줄에 실제로 있어야 한다
        cable = next(c for c in wiring.power_cables() if c.panel == "LP-CRANE")
        self.assertEqual(cable.feeder, "F15")
        self.assertGreater(cable.length_m, 0)

    def test_the_crane_is_not_on_the_motion_bus(self):
        """펜던트·무선 조작이라 EtherCAT 모션 체인에 들어갈 일이 없다."""
        chain = {c.panel for c in wiring.control_segments()}
        chain |= {c.feeder.split("→")[0] for c in wiring.control_segments()}
        self.assertNotIn("LP-CRANE", chain)
        self.assertIn("LP-CRANE", {c.panel for c in wiring.power_cables()})

    def test_a_non_coincident_load_is_named_once(self):
        """비동시라는 사실을 두 군데 적으면 한쪽만 고치는 날이 온다."""
        self.assertEqual(electrical.NON_COINCIDENT_PANELS, ("LP-CRANE",))
        self.assertIs(thermal.NON_COINCIDENT_PANELS, electrical.NON_COINCIDENT_PANELS)
        # 환기는 동시에 걸리는 최대로 잡는다 — 크레인을 더하면 한 단 커진다
        self.assertEqual(thermal.required_airflow_m3h(), 35_000)
        inflated = (thermal.room_load_kw() + thermal.non_coincident_kw()) * 3600.0 \
            / (1.2 * 1.005 * thermal.ROOM_DELTA_T_C)
        self.assertGreater(int(-(-inflated // 500) * 500), thermal.required_airflow_m3h(),
                           "크레인을 실내 부하에 더하면 환기가 커진다 — 그래서 뺐다")

    # ── 도면 ─────────────────────────────────────────────────────────────
    def test_the_drawing_carries_the_crane_numbers(self):
        summary = crane.summary()
        for key, value in summary.items():
            token = f"{key}: " + (f"'{value}'" if isinstance(value, str) else f"{value}")
            with self.subTest(token=token):
                self.assertIn(token.replace("'", '"'), self.html)
        self.assertIn("⑤ 건물 측 인터페이스", self.html,
                      "받치는 쪽이 다르면 넘겨야 할 값이 생긴다 — 도면에 있어야 한다")
        self.assertIn("PV-PLANT-MT-1015", self.html)

    def test_the_3d_uses_the_model_numbers(self):
        """3D 를 사람이 손으로 고치면 모델과 갈라진다 — 리터럴을 못 박는다."""
        rx = (layout.plant_envelope_mm()[0] / 2 - self.WORLD_ORIGIN_X_MM) / 1000
        self.assertIn(f"RX={rx:g},BX=RX;", self.html,
                      "주행거더 중앙이 플랜트 중앙이 아니면 오버행이 양끝 다르다")
        self.assertIn(f"L([{crane.RUNWAY_MM / 1000:.2f},.40,.20],[RX,10.50,z]", self.html)
        # 레일 상면 = TOR, 후크 블록 상면 = 후크 최고 높이
        self.assertIn(f"[RX,{crane.rail_top_mm() / 1000 - 0.025:g},z]", self.html)
        self.assertIn(f"[BX,{crane.hook_height_mm() / 1000 - 0.225:g},0]", self.html)

    def test_every_sheet_stays_inside_its_frame(self):
        """긴 글에 data-fit 이 없으면 프레임이 렌더마다 달라진다.

        fitSheet 이 내용에 맞춰 viewBox 를 키우는데, 넓어진 viewBox 는 축척을
        줄이고 줄어든 축척은 글리프 반올림을 바꿔 사용자단위 길이를 또 바꾼다.
        REV.27 의 스마트 시트가 이 되먹임으로 1,502 ↔ 1,581 을 오갔다 — 두 번
        열면 두 번 다른 도면이 나오는 상태였다.

        폭을 재는 것은 헤드리스(tools/check_sheet_fit.mjs)의 일이고, 여기서는
        긴 글이 data-fit 없이 나가는 자리를 원문에서 막는다.
        """
        tool = (pathlib.Path(__file__).resolve().parents[1]
                / "tools" / "check_sheet_fit.mjs").read_text(encoding="utf-8")
        self.assertIn("const SHEET_W = 1400;", tool)
        self.assertIn("var w = Math.max(1400, Math.ceil(right + 26))", self.html,
                      "검사 도구의 규약 폭이 fitSheet 의 하한과 같아야 한다")
        # 되먹임을 일으켰던 네 자리는 전부 data-fit 을 달고 나가야 한다
        for token in ('data-fit="1320" x="40"',            # 스마트 네트워크 캡션 2줄
                      'data-fit="1300" x="60"',            # 장착 시트 하단 3줄
                      "data-fit=\"610\" x=\"' + (busX + 368)"):   # 계통도 피더 설명 2줄
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        # 집계 블록의 캡션 y 는 **행 수에서** 나와야 한다. 리터럴 5 로 박아
        # 두면 행을 늘리는 순간 캡션이 그 위에 찍힌다 — REV.30 에서 ⑤ 에
        # 두 행을 더하다 실제로 겹쳤다.
        self.assertIn("var cy = by + 30 + sumRows4.length * 24 + 28;", self.html)
        self.assertIn("Math.max(cy + 30 + sumRows5.length * 24, sy + 190) + 30;", self.html)
        self.assertNotIn("by + 30 + 5 * 24", self.html)
        self.assertNotIn("cy + 30 + 5 * 24", self.html)
        # 종전의 data-fit 없는 형태가 되살아나면 다시 흔들린다
        self.assertNotIn("out.push(text(40, 762, '랙 2면은 공간이", self.html)
        self.assertNotIn("out.push(text(60, cap, 'REV.25 까지 앵커 계획은", self.html)
        self.assertNotIn("out.push(text(busX + 368, fy - 3, feeder[2],", self.html)

    def test_the_building_carries_it_and_the_checkers_know(self):
        """공급 범위 밖이라는 사실은 근거와 함께 두 곳에 같이 있어야 한다."""
        exemptions = dict(mounting.UNSUPPORTED_BY_DESIGN)
        self.assertIn("CRN-901", exemptions)
        self.assertIn("건물 철골", exemptions["CRN-901"])
        tool = (pathlib.Path(__file__).resolve().parents[1]
                / "tools" / "check_load_path.mjs").read_text(encoding="utf-8")
        self.assertIn("'CRN-901'", tool)
        # 건물에 넘기는 값이 근거 안에 숫자로 들어 있어야 한다
        self.assertIn(f"{crane.rail_top_mm():,}", exemptions["CRN-901"])
        self.assertIn(f"{crane.SPAN_MM:,}", exemptions["CRN-901"])


class TestCompressedAir(unittest.TestCase):
    """CMP-701 압축공기 — 쓰는데 만드는 것이 없었다.

    §8 의 유압(데크는 올라가는데 HPU 가 없었다)·§26 의 진공(흡착은 그리고
    진공원이 없었다)과 같은 병의 세 번째다. 여기서 못 박는 것은 값이 아니라
    **소비처에서 용량이 나온다**는 관계다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_the_plant_was_already_consuming_air(self):
        """만들기 전에 쓰고 있었다는 사실이 이 모듈의 존재 이유다."""
        jbr = next(c for c in air.consumers() if c.tag == "JBR-201")
        self.assertTrue(jbr.confirmed, "셀 사양에 적힌 값이다 — 여기서 지어낸 게 아니다")
        self.assertEqual((jbr.average_nl_min, jbr.peak_nl_min), (260.0, 420.0))
        self.assertIn("0.5–0.6 MPa", self.html, "셀 사양이 도면에 그대로 있어야 한다")
        # FL-901 은 주관이 있다고 전제하고 재고 있었다
        header = [i for i in smart.INSTRUMENTS if i.tag == "FL-901"]
        self.assertEqual(len(header), 1)
        self.assertIn("압축공기", header[0].name)

    def test_capacity_comes_from_the_consumers(self):
        """용량을 고르지 않고 소비처에서 파생시킨다."""
        self.assertAlmostEqual(air.average_nl_min(), 393.1, places=1)
        self.assertAlmostEqual(air.required_fad_nl_min(), 542.5, places=1)
        # 여유는 곱셈으로 들어간다 — 숨기지 않고 이름으로 드러낸다
        self.assertAlmostEqual(
            air.required_fad_nl_min(),
            air.average_nl_min() * (1 + air.UNLISTED_MARGIN) * (1 + air.LEAKAGE_MARGIN),
            places=1)
        self.assertEqual(air.compressor_kw(), 5.5)
        self.assertEqual(air.compressor_fad_nl_min(), 800)
        self.assertGreaterEqual(air.compressor_fad_nl_min(), air.required_fad_nl_min())
        self.assertTrue(air.covers_peak(), "운전 1대가 동시 피크를 받아야 한다")
        # 소비가 늘면 기종이 따라 올라가는지 — 값이 아니라 규칙인지 본다
        self.assertEqual([kw for kw, fad in air.COMPRESSOR_RANGE if fad >= 1_500][0], 11.0)

    def test_the_dust_collector_pulse_is_derived_not_guessed(self):
        """탈진 공기는 집진 풍량에서 여과면적을 거쳐 나온다."""
        self.assertEqual(air.DUST_FLOW_M3H, 1_350)
        f7 = next(f for f in electrical.FEEDERS if f.tag == "F7")
        self.assertIn("1,000 m³/h", f7.served)
        self.assertIn("350 m³/h", f7.served)
        self.assertAlmostEqual(air.filter_area_m2(), 18.8, places=1)
        self.assertEqual(air.pulse_valves(), 7)
        self.assertAlmostEqual(air.pulse_average_nl_min(), 35.0, places=1)

    def test_the_receiver_exists_for_the_pulse_but_is_sized_by_cycling(self):
        """리시버가 있는 이유와 크기를 정하는 것이 다르다 — 그 구분이 근거다."""
        self.assertAlmostEqual(air.receiver_for_pulse_l(), 101.3, places=1)
        self.assertAlmostEqual(air.receiver_for_cycling_l(), 271.2, places=1)
        self.assertEqual(air.receiver_l(), 300)
        self.assertEqual(air.receiver_governed_by(), "기동 횟수")
        self.assertGreaterEqual(air.receiver_l(),
                                max(air.receiver_for_pulse_l(),
                                    air.receiver_for_cycling_l()))

    def test_the_header_is_sized_at_working_pressure(self):
        """FAD 를 그대로 쓰면 관을 과대하게 잡는다 — 압축된 부피로 재야 한다."""
        self.assertEqual(air.header_bore_mm(), 20)
        self.assertLessEqual(air.header_velocity_ms(), air.HEADER_VELOCITY_MS)
        # 대기압 유량으로 재면 관경이 커진다 — 그 차이가 이 시험의 요점이다
        naive = air.required_fad_nl_min() / 1000 / 60 / air.HEADER_VELOCITY_MS
        naive_bore = math.sqrt(naive * 4 / math.pi) * 1000
        self.assertGreater(naive_bore, air.header_bore_mm())

    def test_the_compressor_room_is_outside_the_process_room(self):
        """유리분이 도는 방에서 공기를 빨면 흡입필터와 오일이 먼저 죽는다."""
        self.assertIn("LP-AIR", thermal.OFF_ROOM_PANELS)
        self.assertEqual(thermal.required_airflow_m3h(), 35_000)
        # 공정실에 뒀다면 환기가 커진다 — 그 사실이 배치의 근거다
        inflated = ((thermal.room_load_kw() + air.demand_kw()) * 3600.0
                    / (1.2 * 1.005 * thermal.ROOM_DELTA_T_C))
        self.assertGreater(int(-(-inflated // 500) * 500), thermal.required_airflow_m3h())
        # 기계실은 시설 블록에 이어 붙는다
        self.assertEqual(wiring.lp_positions_mm()["LP-AIR"],
                         wiring.air_room_center_x_mm())
        self.assertGreater(wiring.air_room_center_x_mm(), wiring.facility_span_mm()[1])

    def test_one_running_one_standby_follows_the_vacuum_precedent(self):
        """공기가 끊기면 클램프가 풀린다 — VAC-101 과 같은 근거다."""
        self.assertEqual((air.COMPRESSOR_UNITS, air.COMPRESSOR_DUTY), (2, 1))
        self.assertAlmostEqual(air.installed_kw(), 11.5, places=1)
        # 수용률은 상수가 아니라 운전대수비 × 부하율에서 나온다
        self.assertAlmostEqual(air.diversity(), 0.37, places=2)
        feeder = next(f for f in electrical.FEEDERS if f.panel == "LP-AIR")
        self.assertEqual(feeder.tag, "F16")
        self.assertAlmostEqual(feeder.installed_kw, air.installed_kw(), places=2)
        self.assertAlmostEqual(feeder.diversity, air.diversity(), places=2)

    def test_the_air_load_pushed_the_breaker_up_a_step(self):
        """§25 에서 예고한 지점이다 — 그 예고가 맞았는지 값으로 확인한다."""
        self.assertEqual(electrical.main_breaker_at(), 500)
        self.assertEqual(electrical.lv_main_cable_mm2(), 300)
        # 공기가 없었다면 수요가 얼마였는지 되짚는다 — 400 AT 안이었다
        limit_kw = 400 * 0.9 * 1.732 * 380 * 0.9 / 1000
        without = electrical.demand_kw() - air.demand_kw()
        self.assertLess(without, limit_kw)
        self.assertGreater(electrical.demand_kw(), limit_kw)
        # 클램프가 유압으로 판명되면 컴프레서는 한 단 내려간다. 그래도 차단기는
        # 안 돌아온다 — 400 AT 를 넘긴 것은 공압 전체가 아니라 그 마지막 0.4 kW 다
        self.assertLess(air.compressor_kw(False), air.compressor_kw())
        self.assertGreater(without + air.demand_kw(False), limit_kw)
        # 굵어진 주회로가 저압 분기 한계를 늘렸다 — 확인값 151 m 는 그대로 유효
        self.assertAlmostEqual(electrical.lv_tap_max_length_m(), 172.8, places=1)
        self.assertTrue(wiring.SITE_BOARD_WITHIN_LV_LIMIT)

    def test_the_header_is_carried_by_the_building(self):
        """통로에 기둥을 세우면 유효폭 900 을 먹는다 — 건물이 받는 부재다."""
        exemptions = dict(mounting.UNSUPPORTED_BY_DESIGN)
        self.assertIn("CMP-701 압축공기 주관", exemptions)
        self.assertIn("건물 벽·기둥", exemptions["CMP-701 압축공기 주관"])
        self.assertEqual(air.hangers(), 18)
        self.assertAlmostEqual(air.hanger_load_kg(), 3.9, places=1)
        # 건물에 넘기는 값이 근거 안에 숫자로 있어야 한다
        self.assertIn(f"{air.HANGER_PITCH_MM:,}", exemptions["CMP-701 압축공기 주관"])

    def test_the_drawing_carries_the_air_numbers(self):
        for key, value in air.summary().items():
            token = f"{key}: " + (f"'{value}'" if isinstance(value, str) else f"{value}")
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertIn("var pvAir=new ce;", self.html, "3D 형상이 있어야 한다")
        self.assertIn("'PV-PLANT-UT-1003', '전기·공압·진공·집진', '2D Utility', '앱 반영'",
                      self.html, "도면목록에서 '기본설계' 를 벗어나야 한다")


class TestSafety(unittest.TestCase):
    """안전 골격 — 부품은 서 있는데 그 부품을 고른 근거가 없었다.

    §8·§26·§34 는 빠진 것이 **장비**였다. 여기서 빠져 있던 것은 **판단**이다 —
    Type 4 라이트커튼도 뮤팅 컨트롤러도 부품표에 있었지만, 무슨 위험원을 무슨
    성능수준으로 막는지가 어디에도 값으로 없었다. 그래서 이 시험이 못 박는
    것은 장치 목록이 아니라 **PLr 이 손으로 적히지 않는다**는 관계다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_the_risk_graph_matches_the_standard(self):
        """ISO 13849-1 부속서 A 를 그대로 옮겼는가 — 여덟 갈래 전부.

        표를 그 표 자신으로 검사하면(`required_pl` 이 `RISK_GRAPH` 를 그대로
        읽으므로) 어느 칸을 고쳐도 시험이 통과한다. 그래서 여기 적는 것은
        **표준의 독립 전사(轉寫)** 다 — 파생 로직을 베끼는 것과는 다르다.
        표준이 밖에 있으니 사본이 둘이어야 어긋남을 볼 수 있다.
        """
        standard = {
            (1, 1, 1): "a", (1, 1, 2): "b",
            (1, 2, 1): "b", (1, 2, 2): "c",
            (2, 1, 1): "c", (2, 1, 2): "d",
            (2, 2, 1): "d", (2, 2, 2): "e",
        }
        self.assertEqual(safety.RISK_GRAPH, standard)
        # 표가 그렇게 생긴 이유 — S 는 두 칸, F·P 는 각 한 칸씩 올린다
        for (s, f, p), pl in standard.items():
            with self.subTest(sfp=(s, f, p)):
                self.assertEqual(safety.PL_ORDER.index(pl),
                                 2 * (s - 1) + (f - 1) + (p - 1))
                self.assertEqual(safety.required_pl(s, f, p), pl)

    def test_every_hazard_has_a_safety_function(self):
        """맡는 것이 없는 위험원은 설계 구멍이다."""
        self.assertEqual(safety.uncovered_hazards(), ())
        for hazard in safety.HAZARDS:
            with self.subTest(hazard=hazard.tag):
                self.assertTrue(safety.functions_for(hazard.tag))
                # PLr 은 필드가 아니라 S·F·P 에서 나온다
                self.assertEqual(
                    hazard.plr,
                    safety.RISK_GRAPH[(hazard.severity, hazard.frequency, hazard.avoidance)])

    def test_a_function_is_never_weaker_than_what_it_covers(self):
        """기능의 PL 은 맡은 위험원 중 최고치여야 한다 — 평균이 아니다."""
        for func in safety.SAFETY_FUNCTIONS:
            served = [h for h in safety.HAZARDS if h.tag in func.hazards]
            with self.subTest(func=func.tag):
                self.assertTrue(served)
                worst = max(served, key=lambda h: safety.PL_ORDER.index(h.plr))
                self.assertEqual(func.plr, worst.plr)
                self.assertEqual(func.category, safety.PL_CATEGORY[func.plr])

    def test_muting_is_the_only_ple_demand(self):
        """뮤팅은 '보호를 끄는' 기능이라 고장 시 안전측이 '켜진 채로' 다."""
        self.assertEqual(safety.plant_plr(), "e")
        ple = [h.tag for h in safety.HAZARDS if h.plr == "e"]
        self.assertEqual(ple, ["HZ-07"])
        muting = next(f for f in safety.SAFETY_FUNCTIONS if f.tag == "SF-04")
        self.assertEqual(muting.hazards, ("HZ-07",))
        self.assertEqual(muting.plr, "e")
        self.assertEqual(muting.category, "Cat.4")
        # F2 인 근거는 사이클 수다 — 상수가 아니라 캠페인·가동시간에서 나온다
        hazard = next(h for h in safety.HAZARDS if h.tag == "HZ-07")
        self.assertEqual(hazard.frequency, 2)
        self.assertIn(f"{safety.muting_cycles_per_day():,}", hazard.basis)

    def test_muting_cycles_come_from_the_campaign(self):
        """패널 1장에 투입·반출 두 번. 가동시간이 바뀌면 같이 움직여야 한다."""
        per_hour = 3600.0 / campaign.summary()["takt_s"]
        hours = smart.OPERATING_HOURS_PER_YEAR / smart.OPERATING_DAYS_PER_YEAR
        self.assertEqual(safety.muting_cycles_per_day(), round(per_hour * hours * 2))
        self.assertEqual(safety.cycles_per_year(),
                         safety.muting_cycles_per_day() * smart.OPERATING_DAYS_PER_YEAR)

    def test_the_penetration_distance_follows_iso_13855(self):
        """C = 8 × (d − 14). 해상도 30 이면 128 이고, 14 이하면 0 이다."""
        self.assertEqual(safety.penetration_mm(), 128)
        self.assertEqual(safety.penetration_mm(30), 8 * (30 - 14))
        self.assertEqual(safety.penetration_mm(14), 0)
        self.assertEqual(safety.penetration_mm(10), 0)

    def test_the_inverse_never_buys_budget_that_is_not_there(self):
        """되짚기는 정확히 되돌아오지 않아도 되지만, 헐거워지면 안 된다.

        표준의 500 mm 하한 때문에 정지시간 448…500 mm 구간이 전부 500 으로
        눌린다. 그 500 을 다시 시간으로 되짚으면 원래보다 **짧은** 예산이
        나온다(200 → 500 mm → 186 ms). 짧은 쪽이 안전한 쪽이므로 그대로 둔다 —
        되짚기가 원래보다 긴 예산을 주는 일만 없으면 된다.
        """
        for ms in (50, 100, 200, 300, 400):
            with self.subTest(ms=ms):
                distance = safety.safety_distance_mm(ms / 1000)
                back = safety.max_stop_time_ms(distance)
                self.assertLessEqual(back, ms)
                self.assertLessEqual(safety.safety_distance_mm(back / 1000), distance)
        # K 는 500 mm 를 경계로 바뀐다 — 가까운 쪽이 2,000, 먼 쪽이 1,600
        self.assertEqual(safety.safety_distance_mm(0.1), 328)       # 2000×0.1 + 128
        self.assertEqual(safety.safety_distance_mm(0.4), 1600 * 0.4 + 128)
        # 눌리는 구간은 전부 하한으로 간다
        self.assertEqual(safety.safety_distance_mm(0.2), safety.APPROACH_SWITCH_MM)
        # 거리가 침입거리보다 짧으면 예산이 없다
        self.assertEqual(safety.max_stop_time_ms(100), 0)

    def test_the_openings_can_hold_the_stop_chain(self):
        """가드는 이미 서 있다 — 그러므로 거리가 정지시간의 예산을 정한다."""
        self.assertTrue(safety.openings_have_budget())
        self.assertEqual(safety.stop_chain_ms(), sum(ms for _, ms in safety.STOP_CHAIN))
        self.assertEqual(safety.tightest_opening().tag, "OP-OUT")
        for op in safety.OPENINGS:
            with self.subTest(opening=op.tag):
                self.assertEqual(op.distance_mm, abs(op.hazard_x_mm - op.plane_x_mm))
                self.assertEqual(op.budget_ms, safety.max_stop_time_ms(op.distance_mm))
                self.assertGreater(op.budget_ms, safety.stop_chain_ms())

    def test_the_contested_hazard_would_break_the_budget(self):
        """320 mm 짜리 판정 하나가 예산을 다섯 배 바꾼다 — 무엇을 해야 하는지까지."""
        self.assertEqual(safety.contested_budget_ms(), 96)
        self.assertLess(safety.contested_budget_ms(), safety.stop_chain_ms())
        # 사슬 전체를 줄이라는 말은 뜻이 없다 — 고정비는 설계가 못 건드린다
        self.assertEqual(safety.fixed_chain_ms(),
                         safety.stop_chain_ms()
                         - dict(safety.STOP_CHAIN)[safety.MECHANICAL_STOP_STEP])
        self.assertEqual(safety.contested_mechanical_budget_ms(),
                         safety.contested_budget_ms() - safety.fixed_chain_ms())
        # 남는 것은 기계 감속뿐이고, 그것을 4.2배 빠르게 하라는 요구가 된다
        self.assertGreater(safety.contested_mechanical_budget_ms(), 0)
        self.assertAlmostEqual(safety.contested_slowdown_ratio(), 4.2, places=1)
        self.assertGreater(safety.contested_slowdown_ratio(), 1.0,
                           "1 이하면 판정이 뒤집혀도 아무 일이 안 일어난다는 뜻이다")

    def test_safety_io_counts_channels_not_devices(self):
        """이중채널 인터록 1대는 1점이 아니라 2점이다."""
        self.assertEqual(safety.safety_inputs(),
                         sum(d.qty * d.inputs_each for d in safety.SAFETY_DEVICES))
        self.assertEqual(safety.safety_outputs(),
                         sum(d.qty * d.outputs_each for d in safety.SAFETY_DEVICES))
        self.assertGreater(safety.safety_inputs(), len(safety.SAFETY_DEVICES))
        # 모듈 수는 예비율을 얹고 올림한다
        self.assertEqual(safety.io_modules(8), 2)      # 8 × 1.2 = 9.6 → 2장
        self.assertEqual(safety.io_modules(6), 1)      # 6 × 1.2 = 7.2 → 1장

    def test_sto_nodes_track_the_servo_count(self):
        """STO 는 드라이브마다 하나다 — 축을 늘리면 FSoE 노드가 따라 늘어야 한다.

        지금 값이 36 이라는 것만 확인하면 36 을 상수로 박아도 시험이 통과한다.
        축을 하나 얹어 답이 따라 오는지를 봐야 파생인지 아닌지가 갈린다.
        """
        self.assertEqual(safety.sto_nodes(), sum(a.qty for a in servos.SERVO_AXES))
        self.assertEqual(safety.sto_nodes(), 36)
        grown = servos.SERVO_AXES + (
            dataclasses.replace(servos.SERVO_AXES[0], tag="AXIS-TEST", qty=3),)
        self.assertEqual(safety.sto_nodes(grown), safety.sto_nodes() + 3)
        self.assertEqual(safety.fsoe_nodes(grown), safety.fsoe_nodes() + 3)
        self.assertEqual(safety.fsoe_nodes(),
                         safety.fsoe_device_nodes() + safety.sto_nodes())

    def test_the_crane_interlock_holds_up_the_contract_power(self):
        """비동시 전제는 규칙이 아니라 회로여야 한다."""
        self.assertIn("LP-CRANE", electrical.NON_COINCIDENT_PANELS)
        self.assertLess(electrical.coincident_worst_case_kw(), electrical.worst_case_kw())
        interlock = next(f for f in safety.SAFETY_FUNCTIONS if f.tag == "SF-08")
        self.assertEqual(interlock.hazards, ("HZ-14",))
        self.assertIn("NON_COINCIDENT_PANELS", interlock.note)
        # 계약전력이 그 전제 위에 서 있다는 사실을 근거가 숫자로 들고 있어야 한다
        self.assertIn(f"{electrical.coincident_worst_case_kw()}", interlock.note)

    def test_the_module_refuses_to_invent_pfhd(self):
        """없는 PFHd 는 거짓 PFHd 보다 낫다."""
        self.assertFalse(hasattr(safety, "pfhd"))
        self.assertIn("PFHd", dict(safety.SISTEMA_INPUTS))
        self.assertIn("이 모듈은 PFHd 를 내지 않는다", dict(safety.SISTEMA_INPUTS)["PFHd"])
        # 대신 그 계산의 입력을 값으로 낸다
        self.assertGreater(safety.t10d_years(2_000_000), safety.MISSION_TIME_YEARS)
        self.assertTrue(safety.needs_scheduled_replacement(1_000_000))
        self.assertFalse(safety.needs_scheduled_replacement(2_000_000))

    def test_the_drawing_carries_the_safety_numbers(self):
        # SAFETY 블록은 summary() 를 JSON 으로 찍은 것이다 — 키까지 따옴표가 붙는다
        for key, value in safety.summary().items():
            token = f'"{key}": ' + (f'"{value}"' if isinstance(value, str) else f"{value}")
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        for hazard in safety.HAZARDS:
            with self.subTest(hazard=hazard.tag):
                self.assertIn(f'"{hazard.tag}"', self.html)
        for func in safety.SAFETY_FUNCTIONS:
            with self.subTest(func=func.tag):
                self.assertIn(f'"{func.tag}"', self.html)
        self.assertIn("'PV-PLANT-SF-1004', '위험원·PLr·안전기능·정지포락선', '2D Safety', '앱 반영'",
                      self.html, "도면목록에서 '기본설계' 를 벗어나야 한다")
        self.assertIn("PLC-IO-7101', '안전 I/O 점수·FSoE 노드·handshake', '전장', '앱 반영'",
                      self.html)
        self.assertIn('id="pv-tab-safety"', self.html)
        self.assertIn("'safety'", self.html, "탭 목록에 안전이 있어야 한다")

    def test_the_sheet_checker_knows_every_tab(self):
        """탭을 늘리고 검사에 안 넣으면 그 시트는 아무도 안 본다.

        REV.34 까지 시트 검사는 각 탭의 **기본 시트만** 봤다 — 전기 4장 중
        단선결선도 하나뿐이었다. 그래서 분전반 배선도가 시트 폭을 218 넘긴 채
        여러 판 지나갔다. 탭 목록이 어긋나면 여기서 잡는다.
        """
        checker = (pathlib.Path(__file__).resolve().parents[1]
                   / "tools" / "check_sheet_fit.mjs").read_text(encoding="utf-8")
        listed = set(re.findall(r"'([a-z]+)'", re.search(
            r"const TABS = \[(.*?)\];", checker).group(1)))
        in_drawing = set(re.findall(r'id="pv-tab-([a-z]+)"', self.html))
        self.assertEqual(listed, in_drawing)
        self.assertIn("safety", listed)
        # 검사는 시트 선택 옵션도 하나씩 돌아야 한다
        self.assertIn('select[id$="-view"]', checker)

    def test_the_mdb_sheet_splits_branches_into_tiers(self):
        """분기 16회로를 한 열에 그리면 반 밖으로 나간다 — 단 수는 피더에서 나온다."""
        self.assertIn("var PER_TIER = 8", self.html)
        self.assertIn("Math.ceil(feeders.length / PER_TIER)", self.html)
        self.assertNotIn("var ductY = e.y + 430;", self.html)
        self.assertGreater(len(electrical.FEEDERS), 8,
                           "8 이하로 줄면 이 단 분할이 필요 없어진다")


class TestDustExplosion(unittest.TestCase):
    """DX-601 — 집진기는 있었고, 그 안이 터질 수 있는지가 없었다.

    이 시험이 지키는 것은 값이 아니라 **태도**다. 폭발 특성은 시험으로만
    나오므로 여기서 Kst 를 지어내지 않는다. 대신 지어내지 않았다는 사실과,
    지금 확실히 말할 수 있는 것(알루미늄 미분 없음·점화원 셋·옥내 벤트 불가)이
    값으로 서 있는지를 본다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_the_collector_and_the_air_model_see_the_same_flow(self):
        """여과 면적·밸브·압축공기가 전부 이 풍량에서 나온다."""
        self.assertTrue(dust.flow_is_consistent())
        self.assertEqual(dust.counted_flow_m3h(), air.DUST_FLOW_M3H)
        self.assertEqual(dust.filter_area_m2(), air.filter_area_m2())
        self.assertEqual(dust.pulse_valves(), air.pulse_valves())

    def test_the_most_combustible_stream_is_outside_the_count(self):
        """CV-301 은 이름만 있고 풍량이 없다 — 그것이 이 모듈이 찾은 것이다."""
        missing = dust.unquantified_streams()
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].tag, "DS-03")
        self.assertTrue(missing[0].combustible)
        self.assertIsNone(missing[0].flow_m3h)
        # 집계에 없다는 사실이 근거에 적혀 있어야 한다
        self.assertIn(f"{air.DUST_FLOW_M3H:,}", missing[0].basis)

    def test_glass_dust_does_not_make_the_mixture_safe(self):
        """불활성분이 있다는 것과 혼합물이 불활성화된다는 것은 다른 말이다."""
        glass = next(s for s in dust.STREAMS if s.tag == "DS-01")
        self.assertFalse(glass.combustible)
        self.assertIn("불활성화", glass.basis)
        # 가연 흐름이 있는 한 비율은 0 이 아니다
        self.assertGreater(dust.combustible_flow_fraction(), 0)
        self.assertLess(dust.combustible_flow_fraction(), 1)

    def test_the_frame_is_pulled_so_there_is_no_aluminium_fines(self):
        """이 설비가 St-3 를 피하는 이유는 공정이지 집진기가 아니다."""
        self.assertTrue(dust.FRAME_IS_PULLED_NOT_CUT)
        st3 = next(c for c in dust.ST_CLASSES if c[0] == "St-3")
        self.assertIn("인발", st3[3])
        self.assertEqual(dust.st_class(350), "St-3")
        self.assertEqual(dust.st_class(200), "St-1")
        self.assertEqual(dust.st_class(201), "St-2")
        self.assertEqual(dust.st_class(0), "St-0")

    def test_the_module_refuses_to_invent_kst(self):
        """Kst 를 상수로 갖고 있으면 그 순간 이 파일이 거짓이 된다."""
        self.assertFalse(hasattr(dust, "KST"))
        self.assertFalse(hasattr(dust, "PMAX"))
        names = [t[0] for t in dust.REQUIRED_TESTS]
        self.assertTrue(any("14034-1/2" in n for n in names))
        self.assertTrue(any("14034-3" in n for n in names))
        # 혼합 시료로 시험해야 한다는 것이 목록에 있어야 한다
        self.assertTrue(any("혼합" in n for n in names))

    def test_indoor_siting_forces_a_choice(self):
        """옥내로 벤트를 열 수 없다 — 셋 중 하나이고 셋 다 배치가 바뀐다."""
        self.assertEqual(len(dust.INDOOR_VENT_OPTIONS), 3)
        self.assertTrue(dust.ISOLATION_REQUIRED)
        self.assertEqual(len(dust.IGNITION_SOURCES), 3)
        # 세 점화원이 모두 실재하는 설비를 가리켜야 한다
        for tag, _ in dust.IGNITION_SOURCES:
            with self.subTest(tag=tag):
                self.assertTrue(tag.startswith(("SG-301", "GRM-401", "정전기")))

    def test_the_missing_flow_has_a_consequence_chain(self):
        """풍량 하나가 컴프레서까지 간다 — 그 사슬이 글로 있어야 한다."""
        chain = dust.missing_flow_consequences()
        self.assertGreaterEqual(len(chain), 4)
        self.assertTrue(any("F16" in c for c in chain))
        self.assertTrue(any(f"{air.AIR_TO_CLOTH_M3_H_M2:g}" in c for c in chain))


class TestHeightAccess(unittest.TestCase):
    """고소 정비 — 정비 대상은 높이 있는데 올라가는 방법이 없었다."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_height_alone_picks_the_means(self):
        """수단은 손으로 고르는 것이 아니라 높이가 정한다."""
        self.assertIn("불요", access.means_for(500))
        self.assertIn("발판", access.means_for(1_500))
        self.assertIn("이동식", access.means_for(3_000))
        self.assertIn("고소작업대", access.means_for(11_000))
        for point in access.POINTS:
            with self.subTest(point=point.tag):
                self.assertEqual(point.means, access.means_for(point.height_mm))
                self.assertEqual(point.needs_fall_protection,
                                 point.height_mm >= access.FALL_PROTECTION_MM)

    def test_every_point_needs_fall_protection(self):
        """2 m 를 넘는 것이 여덟 중 여덟이다 — 하나도 예외가 아니다."""
        self.assertEqual(len(access.needing_fall_protection()), len(access.POINTS))
        self.assertEqual(access.FALL_PROTECTION_MM, 2_000)

    def test_heights_come_from_the_model(self):
        """상수로 적으면 크레인·비전보가 바뀌어도 안 따라온다.

        값이 같은지만 보면 파생인지 리터럴인지 못 가른다 — 지금 5,150 이라
        `5_150` 을 박아 놔도 통과한다. 그래서 값과 **적힌 꼴** 둘 다 본다.
        """
        highest = access.highest()
        self.assertEqual(highest.height_mm, crane.rail_top_mm())
        vg = next(p for p in access.POINTS if p.tag == "AC-01")
        self.assertEqual(vg.height_mm, crane.tallest_lift().height_mm)
        header = next(p for p in access.POINTS if p.tag == "AC-05")
        self.assertIn(f"{air.hangers()}", header.basis)
        # 크레인에서 오는 두 높이는 식으로 적혀 있어야 한다
        source = (pathlib.Path(__file__).resolve().parents[1]
                  / "src" / "pv_preprocess" / "access.py").read_text(encoding="utf-8")
        self.assertIn("crane.tallest_lift().height_mm", source)
        self.assertIn("crane.rail_top_mm()", source)
        for literal in (f"{vg.height_mm:_}", f"{highest.height_mm:_}"):
            with self.subTest(literal=literal):
                self.assertNotIn(f'"afu", {literal},', source)
                self.assertNotIn(f'"post", {literal},', source)

    def test_a_fixed_platform_does_not_fit_the_aisle(self):
        """§34 의 공압 주관이 기둥을 못 세운 것과 같은 벽이다."""
        self.assertEqual(access.AISLE_CLEAR_MM, wiring.aisle_clear_width_mm())
        self.assertFalse(access.fixed_platform_fits_aisle())
        self.assertFalse(access.fixed_platform_fits_aisle(restricted=True))
        self.assertLess(access.aisle_left_after_platform_mm(), wiring.WALKWAY_MIN_MM)
        self.assertTrue(access.MOBILE_IS_THE_ANSWER)

    def test_mobile_does_not_erase_the_anchor_points(self):
        """이동식이어도 안전대는 어딘가에 걸어야 한다."""
        self.assertEqual(access.ANCHOR_POINT_KN, 15.0)
        groups = dict(access.anchor_points())
        self.assertEqual(len(groups), 3)
        joined = " ".join(groups.values())
        self.assertIn("우리 일이다", joined)
        self.assertIn("건물이 받는다", joined)

    def test_the_building_gets_the_crane_rail(self):
        """크레인 주행거더·공압 주관과 같은 자리다."""
        building = access.handed_to_building()
        self.assertEqual([p.tag for p in building], ["AC-08"])
        self.assertIn(f"{crane.rail_top_mm():,}", building[0].basis)


class TestSeismic(unittest.TestCase):
    """내진 — 앵커 190개는 자중에서 나온 값이고 지진은 안 봤다."""

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_masses_and_heights_come_from_the_lift_list(self):
        """크레인이 드는 것과 지진이 흔드는 것은 같은 물건이다."""
        names = [c.name for c in seismic.components()]
        self.assertEqual(names, [lift.name for lift in crane.LIFTS])
        for comp, lift in zip(seismic.components(), crane.LIFTS):
            with self.subTest(name=comp.name):
                self.assertEqual((comp.mass_kg, comp.height_mm),
                                 (lift.mass_kg, lift.height_mm))

    def test_the_base_width_is_not_the_cell_envelope(self):
        """셀 폭으로 재면 복원 모멘트가 부풀어 '문제 없다' 는 거짓이 나온다."""
        for comp in seismic.components():
            envelope = layout.STATIONS[comp.station].envelope
            with self.subTest(name=comp.name):
                self.assertLess(comp.base_mm, min(envelope[0], envelope[1]))
                self.assertTrue(comp.basis, "베이스폭은 출처가 있어야 한다")

    def test_the_force_follows_the_code_shape(self):
        """Fp = 0.4·a_p·S_DS·W/(Rp/Ip), 상·하한이 걸린다."""
        # 하한이 지배하는 구간 — 강체는 0.4/2.5 = 0.16 < 0.3 이라 늘 하한이다
        self.assertAlmostEqual(seismic.seismic_ratio(seismic.AP_RIGID, 1.0),
                               seismic.FP_MIN_FACTOR, places=4)
        # 유연체는 0.4×2.5/2.5 = 0.4 이므로 하한을 넘는다
        self.assertAlmostEqual(seismic.seismic_ratio(seismic.AP_FLEXIBLE, 1.0),
                               0.4, places=4)
        # 상한 — 아무리 키워도 1.6·S_DS 를 못 넘는다
        self.assertLessEqual(seismic.seismic_ratio(100.0, 1.0),
                             seismic.FP_MAX_FACTOR)
        # 세장비가 임계를 넘으면 유연체로 본다
        for comp in seismic.components():
            with self.subTest(name=comp.name):
                self.assertEqual(comp.is_flexible,
                                 comp.slenderness > seismic.SLENDER_RATIO)

    def test_three_components_have_no_anchor_group(self):
        """셀 총수로는 '이 물건이 안 넘어진다' 를 못 보인다."""
        missing = {c.name for c in seismic.unanchored()}
        self.assertEqual(len(missing), 3)
        self.assertIn("MDB-101 주 분전반", missing)
        self.assertIn("VG-101 독립 방진 비전보 조립체", missing)
        self.assertEqual(len(seismic.anchored()) + len(seismic.unanchored()),
                         len(seismic.components()))
        # 답이 없는 것은 0 이 아니라 NaN 이어야 한다 — 0 은 '괜찮다' 로 읽힌다
        for comp in seismic.unanchored():
            with self.subTest(name=comp.name):
                self.assertTrue(math.isnan(seismic.anchor_tension_kn(comp)))
                self.assertTrue(math.isnan(seismic.anchor_utilisation(comp)))

    def test_the_wall_panel_is_the_worst_shape(self):
        """벽부 D300 에 높이 2,100 — 지레비가 깊이뿐이다."""
        slim = seismic.most_slender()
        self.assertEqual(slim.name, "MDB-101 주 분전반")
        self.assertTrue(slim.wall_mounted)
        self.assertAlmostEqual(slim.slenderness, 7.0, places=2)
        # 가정한 S_DS 보다 낮은 데서 들린다 — 그것이 이 시험의 요점이다
        self.assertLess(seismic.uplift_sds(slim), seismic.ASSUMED_SDS)
        self.assertIn(slim.name, seismic.ANCHOR_GROUP)
        self.assertIsNone(seismic.ANCHOR_GROUP[slim.name])

    def test_anchor_groups_come_from_the_mounting_plan(self):
        """앵커 수를 여기서 다시 세면 mounting 과 어긋난다."""
        for comp in seismic.anchored():
            station, target = seismic.ANCHOR_GROUP[comp.name]
            mount = mounting.MOUNTING_OF[station]
            anchor = next(a for a in mount.anchors if a.target == target)
            expected = anchor.count * (anchor.units if anchor.per_unit else 1)
            with self.subTest(name=comp.name):
                self.assertEqual(seismic.total_anchors(comp), expected)
                self.assertEqual(seismic.anchor_size(comp), anchor.bolt)
                self.assertEqual(comp.station, station)

    def test_the_anchored_ones_are_not_the_problem(self):
        """지진이 지배하지 않는다 — 그리고 그 사실을 상한과 구분해서 적는다."""
        self.assertTrue(seismic.holds())
        self.assertTrue(seismic.governing_sds_is_capped())
        self.assertEqual(seismic.governing_sds(), seismic.SDS_SEARCH_LIMIT)
        for comp in seismic.anchored():
            with self.subTest(name=comp.name):
                self.assertGreater(seismic.uplift_sds(comp), seismic.ASSUMED_SDS)

    def test_the_remedy_puts_bigger_anchors_last(self):
        """전도는 지레비가 정한다 — 앵커를 키우는 것이 첫 수가 아니다."""
        order = [r[0] for r in seismic.REMEDY_ORDER]
        self.assertEqual(order[0], "베이스를 넓힌다")
        self.assertLess(order.index("무게중심을 낮춘다"), order.index("앵커를 키운다"))
        self.assertIn("앵커를 키운다", order)

    def test_the_drawing_carries_the_environment_numbers(self):
        for name, values in (("DUST", dust.summary()),
                             ("ACCESS", access.summary()),
                             ("SEISMIC", seismic.summary())):
            for key, value in values.items():
                if isinstance(value, bool):
                    token = f'"{key}": ' + ("true" if value else "false")
                elif isinstance(value, str):
                    token = f'"{key}": "{value}"'
                else:
                    token = f'"{key}": {value}'
                with self.subTest(block=name, token=token):
                    self.assertIn(token, self.html)
        for tag in ("PV-PLANT-DX-1016", "PV-PLANT-AC-1017", "PV-PLANT-SE-1018"):
            with self.subTest(tag=tag):
                self.assertIn(f"['{tag}'", self.html)
                self.assertIn("'앱 반영'", self.html)


class TestReliability(unittest.TestCase):
    """가동률 — §25·§26 의 연간 숫자가 무엇 위에 서 있었는가.

    MTBF 를 지어내지 않는다는 점에서 §43 의 Kst 와 같은 태도다. 대신 물음을
    뒤집어 **가용률을 정하고 요구 MTBF 를 낸다** — 실적을 못 재는 자리에서
    설계가 할 수 있는 일은 그것을 요구로 바꾸는 것이다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_the_annual_figures_assumed_perfect_uptime(self):
        """§25 의 308,138 장은 가용률 1.0 위에 서 있었다."""
        self.assertEqual(reliability.nominal_annual_panels(), ai.annual_panels())
        self.assertEqual(reliability.nominal_annual_panels(),
                         round(smart.panels_per_h() * smart.OPERATING_HOURS_PER_YEAR))
        # 가용률을 얹으면 줄어들고, 그 차이가 라벨·저장·매출로 간다
        self.assertLess(reliability.annual_panels(), reliability.nominal_annual_panels())
        self.assertEqual(reliability.annual_shortfall(),
                         reliability.nominal_annual_panels() - reliability.annual_panels())
        self.assertGreater(reliability.annual_shortfall(), 0)

    def test_the_downtime_budget_comes_from_the_target(self):
        """목표 가용률 한 줄이 아래 전부를 정한다.

        지금 값이 330 인지만 보면 `return 330.0` 으로 바꿔도 통과한다. 목표를
        갈아 끼워 예산이 따라 움직이는지를 봐야 관계가 확인된다.
        """
        self.assertAlmostEqual(
            reliability.downtime_budget_h(),
            round(smart.OPERATING_HOURS_PER_YEAR * (1 - reliability.TARGET_AVAILABILITY), 1),
            places=1)
        # 목표를 낮추면 예산이 늘고, 계통 예산과 요구 MTBF 가 따라 움직인다
        loose = reliability.downtime_budget_h(0.85)
        self.assertGreater(loose, reliability.downtime_budget_h())
        self.assertAlmostEqual(loose,
                               round(smart.OPERATING_HOURS_PER_YEAR * 0.15, 1), places=1)
        for block in reliability.BLOCKS:
            with self.subTest(block=block.tag):
                self.assertGreater(block.downtime_h(0.85), block.downtime_h())
                self.assertLess(block.required_mtbf_h(0.85), block.required_mtbf_h())
        self.assertTrue(reliability.blocks_share_sums_to_one())
        self.assertAlmostEqual(sum(b.downtime_h() for b in reliability.BLOCKS),
                               reliability.downtime_budget_h(), places=1)

    def test_required_mtbf_is_the_inversion(self):
        """MTBF 를 모르니 구할 수 없다 → 그렇다면 요구로 적는다."""
        for block in reliability.BLOCKS:
            with self.subTest(block=block.tag):
                self.assertAlmostEqual(block.failures_per_year(),
                                       round(block.downtime_h() / block.mttr_h, 2), places=2)
                self.assertEqual(
                    block.required_mtbf_h(),
                    int(smart.OPERATING_HOURS_PER_YEAR / block.failures_per_year()))
                # 요구 MTBF 는 운전시간보다 짧을 수 없을 만큼 느슨하면 안 된다
                self.assertGreater(block.required_mtbf_h(), 0)
        # 정지시간을 가장 많이 쓰는 곳과 요구가 가장 빡빡한 곳은 다르다
        self.assertNotEqual(reliability.governing_block().tag,
                            reliability.tightest_mtbf_block().tag)
        self.assertEqual(reliability.governing_block().tag, "RB-JBR")

    def test_the_buffer_makes_a_hole_in_the_series_chain(self):
        """버퍼가 없었다면 같은 고장률에서 가용률이 더 낮다."""
        self.assertEqual(reliability.buffer_ride_through_h(),
                         handoff.buffer_ride_through_h())
        self.assertGreater(reliability.buffered_downtime_h(), 0)
        self.assertLess(reliability.availability_without_buffer(),
                        reliability.TARGET_AVAILABILITY)
        # 흡수는 완충시간을 넘지 못한다 — MTTR 이 길면 부분만 벌어 준다
        for block in reliability.buffered_blocks():
            with self.subTest(block=block.tag):
                self.assertLessEqual(min(block.mttr_h, reliability.buffer_ride_through_h()),
                                     reliability.buffer_ride_through_h())

    def test_unknown_lives_are_not_covered_with_zero(self):
        """수명을 모르는 것을 0 으로 덮으면 그 0 이 곧 근거가 된다."""
        pending = reliability.spares_pending()
        self.assertGreater(len(pending), 0)
        for spare in pending:
            with self.subTest(spare=spare.tag):
                self.assertIsNone(spare.per_year)
                self.assertIsNone(spare.stock())
        # 소요를 아는 것은 재고가 나온다
        for spare in reliability.spares_with_rate():
            with self.subTest(spare=spare.tag):
                self.assertGreaterEqual(spare.stock(), 1)
        self.assertEqual(len(reliability.initial_stock()),
                         len(reliability.spares_with_rate()))

    def test_spare_rates_come_from_usage(self):
        """소요는 손으로 적는 것이 아니라 사용량에서 나온다."""
        bags = next(s for s in reliability.SPARES() if s.tag == "SP-04")
        self.assertEqual(bags.qty_installed, reliability.filter_bags())
        self.assertEqual(reliability.filter_bags(), 19)
        self.assertEqual(reliability.filter_bags(),
                         max(1, round(air.filter_area_m2() / reliability.BAG_AREA_M2)))
        self.assertAlmostEqual(bags.per_year, 9.5, places=1)
        self.assertAlmostEqual(bags.per_year,
                               round(reliability.filter_bags() / reliability.BAG_LIFE_YEARS, 1),
                               places=1)
        # 수명은 관례값(3~5년)보다 짧아야 한다 — 유리분이 연마성이라는 것이 근거다
        self.assertLess(reliability.BAG_LIFE_YEARS, 3.0)
        self.assertIn("연마성", bags.basis)
        valves = next(s for s in reliability.SPARES() if s.tag == "SP-05")
        self.assertEqual(valves.qty_installed, air.pulse_valves())

    def test_the_drawing_carries_the_reliability_numbers(self):
        for key, value in reliability.summary().items():
            token = f'"{key}": ' + (f'"{value}"' if isinstance(value, str) else f"{value}")
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertIn("['PV-PLANT-RA-1019'", self.html)
        self.assertIn('id="pv-tab-ops"', self.html)


class TestAcceptance(unittest.TestCase):
    """FAT·SAT — 검수 기준이 모델에서 나온다.

    검수서를 따로 쓰면 도면과 어긋난다. 여기서 못 박는 것은 값이 아니라
    **기대값이 리터럴이 아니라 호출**이라는 사실이다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = read_drawing()

    def test_every_item_names_the_model_value_it_checks(self):
        """근거 없는 검수 항목은 현장에서 협상 대상이 된다.

        `return True` 로 바꿔도 통과하면 검사가 아니다 — 근거가 빠진 항목을
        넣어 보고 False 가 나오는지까지 본다.
        """
        self.assertTrue(acceptance.every_item_has_a_source())
        broken = acceptance.items()[0]
        self.assertFalse(acceptance.every_item_has_a_source(
            (dataclasses.replace(broken, source=""),)))
        self.assertFalse(acceptance.every_item_has_a_source(
            (dataclasses.replace(broken, source="근거없음"),)))
        for item in acceptance.items():
            with self.subTest(item=item.tag):
                self.assertIn(item.stage, acceptance.STAGES)
                self.assertTrue(item.method)
                self.assertTrue(item.tolerance)
                # 기대값은 호출이라 지금 계산된다
                self.assertIsNotNone(item.value())

    def test_the_expected_values_track_the_model(self):
        """모델이 바뀌면 검수 기준이 따라 바뀐다 — 어긋날 수가 없다."""
        pairs = {
            "F-01": safety.stop_chain_ms(),
            "F-04": safety.sto_nodes(),
            "F-05": air.compressor_fad_nl_min(),
            "F-07": electrical.demand_kw(),
            "F-08": mounting.total_anchors(),
            "F-09": crane.hook_height_mm(),
            "S-01": campaign.summary()["takt_s"],
            "S-04": handoff.buffer_ride_through_h(),
            "S-05": thermal.required_airflow_m3h(),
            "S-07": dust.counted_flow_m3h(),
            "S-10": len(seismic.unanchored()),
            "R-02": reliability.TARGET_AVAILABILITY,
            "R-03": reliability.annual_panels(),
        }
        found = {i.tag: i for i in acceptance.items()}
        for tag, expected in pairs.items():
            with self.subTest(tag=tag):
                self.assertEqual(found[tag].value(), expected)
        # 값이 같은지만 보면 `lambda: 287` 로 박아도 통과한다 — 적힌 꼴을 본다
        source = (pathlib.Path(__file__).resolve().parents[1]
                  / "src" / "pv_preprocess" / "acceptance.py").read_text(encoding="utf-8")
        literal = re.findall(r"lambda: (?:\d|['\"])", source)
        self.assertEqual(literal, [],
                         "기대값은 리터럴이 아니라 모델 호출이어야 한다")
        self.assertEqual(len(re.findall(r"lambda: ", source)), len(acceptance.items()))

    def test_the_stages_split_by_what_a_factory_can_show(self):
        """공장에서 되는 것과 라인이 서야 되는 것은 다르다."""
        self.assertEqual(len(acceptance.by_stage(acceptance.FAT)), 10)
        self.assertEqual(len(acceptance.by_stage(acceptance.SAT)), 10)
        self.assertEqual(len(acceptance.by_stage(acceptance.RAR)), 5)
        self.assertEqual(sum(len(acceptance.by_stage(s)) for s in acceptance.STAGES),
                         len(acceptance.items()))
        with self.assertRaises(ValueError):
            acceptance.by_stage("없는단계")

    def test_three_items_are_still_open_at_handover(self):
        """인수 후 확정이 아니라 인수 조건에 명시로 다뤄야 한다."""
        open_tags = {i.tag for i in acceptance.open_at_handover()}
        self.assertEqual(open_tags, {"S-08", "S-10", "R-04"})
        # S-10 은 지금 0 이 아니다 — 그것이 열려 있다는 뜻이다
        s10 = next(i for i in acceptance.items() if i.tag == "S-10")
        self.assertGreater(s10.value(), 0)
        self.assertEqual(s10.value(), len(seismic.unanchored()))

    def test_blocking_items_cover_the_contract_numbers(self):
        """인수를 막는 항목이 계약 숫자를 덮어야 한다."""
        blocking = {i.tag for i in acceptance.blocking()}
        for tag in ("F-01", "F-07", "S-01", "S-02", "R-02"):
            with self.subTest(tag=tag):
                self.assertIn(tag, blocking)
        # 누설률과 연간 환산은 차단이 아니다 — 고쳐서 넘길 수 있는 것들이다
        self.assertNotIn("F-06", blocking)
        self.assertNotIn("R-03", blocking)

    def test_the_drawing_carries_the_acceptance_numbers(self):
        for key, value in acceptance.summary().items():
            token = f'"{key}": ' + (f'"{value}"' if isinstance(value, str) else f"{value}")
            with self.subTest(token=token):
                self.assertIn(token, self.html)
        self.assertIn("['PV-PLANT-QA-1020'", self.html)
        for item in acceptance.items():
            with self.subTest(item=item.tag):
                self.assertIn(f'"{item.tag}"', self.html)
