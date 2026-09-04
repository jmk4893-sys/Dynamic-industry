"""정비성 재설계가 한 벌로 맞물려 있는지 검증.

마모부품 등록부(WEAR_PARTS) 가 단일 출처다. 3D 의 교체 모듈 표식, 상태감시 센서 노드,
정비 접근 공간, BOM 의 정비 행, 콘솔 패널이 전부 그 표를 읽어야 한다. 어느 하나만 고치면
여기서 걸린다 — 「등록부에는 있는데 3D 에 없다」가 이 플랜트에서 반복돼 온 결함이다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

MINIAPP = (pathlib.Path(__file__).resolve().parents[1]
           / "docs" / "drawings" / "pv-recycling-miniapp.html")

WEAR_BLOCK_RE = re.compile(r"const WEAR_PARTS = Object\.freeze\(\[(?P<body>.*?)\n  \]\);", re.S)
SENSOR_BLOCK_RE = re.compile(r"const CONDITION_SENSORS = Object\.freeze\(\[(?P<body>.*?)\n  \]\);", re.S)
LOTO_BLOCK_RE = re.compile(r"const LOTO_POINTS = Object\.freeze\(\[(?P<body>.*?)\n  \]\);", re.S)
ENTRY_RE = re.compile(r"\{ id: \"(?P<id>[A-Z0-9-]+)\"")
FIELD_RE = lambda name: re.compile(name + r": \"([^\"]+)\"")  # noqa: E731


def read():
    return MINIAPP.read_text(encoding="utf-8")


def split_entries(body):
    """등록부 본문을 항목 단위로 나눈다 — 각 항목은 `{ id: "..."` 로 시작한다."""
    starts = [m.start() for m in ENTRY_RE.finditer(body)]
    return [body[s:e] for s, e in zip(starts, starts[1:] + [len(body)])]


class WearRegistryTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = read()
        block = WEAR_BLOCK_RE.search(cls.html)
        assert block, "WEAR_PARTS 등록부가 없다"
        cls.entries = split_entries(block.group("body"))
        cls.ids = [ENTRY_RE.search(e).group("id") for e in cls.entries]
        sensors = SENSOR_BLOCK_RE.search(cls.html)
        assert sensors, "CONDITION_SENSORS 등록부가 없다"
        cls.sensor_entries = split_entries(sensors.group("body").replace("{ tag:", "{ id:"))
        cls.sensor_tags = [ENTRY_RE.search(e).group("id") for e in cls.sensor_entries]
        cls.bom_codes = set(re.findall(r'code:\s*"([A-Z]+-[A-Z]*-?\d+[a-z]?)"', cls.html))

    def test_registry_is_substantial_and_unique(self):
        self.assertGreaterEqual(len(self.ids), 30, "마모부품이 30종 미만이다")
        self.assertEqual(len(self.ids), len(set(self.ids)), "id 가 중복된다")
        self.assertGreaterEqual(len(self.sensor_tags), 20, "상태감시 센서가 20점 미만이다")
        self.assertEqual(len(self.sensor_tags), len(set(self.sensor_tags)))

    def test_every_part_states_module_method_mttr_and_life(self):
        """교체 절차·목표 시간·수명 근거가 없는 마모부품은 정비성 설계가 아니다."""
        for entry, pid in zip(self.entries, self.ids):
            for field in ("module", "method", "tools", "spare"):
                self.assertTrue(re.search(field + r': "[^"]{2,}"', entry), f"{pid}: {field} 가 비어 있거나 한 글자다")
            self.assertTrue(re.search(r"mttrMin: \d+", entry), f"{pid}: MTTR 이 없다")
            life = re.search(r'life: \{ basis: "(\w+)", limit: (\d+), unit: "(\w+)" \}', entry)
            self.assertIsNotNone(life, f"{pid}: life 가 없다")
            self.assertIn(life.group(1), ("freshMass", "millMass", "screenMass", "sieveMass", "fineMass", "hours", "wetHours"))
            self.assertGreater(int(life.group(2)), 0)
            self.assertEqual(life.group(3), "kg" if life.group(1).endswith("Mass") else "h",
                             f"{pid}: basis 와 unit 이 어긋난다")

    def test_mttr_targets_are_quick_swap_targets(self):
        """카세트·카트리지·모듈 패널은 한 교대 안에 끝나야 한다 — 4 시간을 넘으면 재설계가 아니다."""
        for entry, pid in zip(self.entries, self.ids):
            mttr = int(re.search(r"mttrMin: (\d+)", entry).group(1))
            self.assertLessEqual(mttr, 240, f"{pid}: MTTR {mttr}분 — 교체식 설계 목표를 넘는다")
        cassette = [e for e in self.entries if re.search(r'module: "(카세트|카트리지|핀인[^"]*|백풀아웃[^"]*|슬라이드[^"]*)"', e)]
        self.assertGreaterEqual(len(cassette), 15, "카세트·카트리지·모듈 단위 교체 부품이 15종 미만이다")
        for entry in cassette:
            mttr = int(re.search(r"mttrMin: (\d+)", entry).group(1))
            self.assertLessEqual(mttr, 120, ENTRY_RE.search(entry).group("id") + ": 카세트류인데 MTTR 이 2시간을 넘는다")

    def test_sensor_references_resolve(self):
        for entry, pid in zip(self.entries, self.ids):
            tags = re.findall(r'"([A-Z]+-[A-Z0-9]+)"', re.search(r"sensors: \[([^\]]*)\]", entry).group(1))
            for tag in tags:
                self.assertIn(tag, self.sensor_tags, f"{pid}: 센서 {tag} 가 CONDITION_SENSORS 에 없다")
        for sensor_entry, tag in zip(self.sensor_entries, self.sensor_tags):
            wear_of = re.search(r'wearOf: "([A-Z0-9-]+)"', sensor_entry)
            self.assertIsNotNone(wear_of, f"{tag}: wearOf 가 없다")
            self.assertIn(wear_of.group(1), self.ids, f"{tag}: wearOf {wear_of.group(1)} 가 등록부에 없다")

    def test_bom_references_resolve(self):
        """등록부가 가리키는 BOM 행이 실제로 있어야 예비품이 발주된다."""
        for entry, pid in zip(self.entries, self.ids):
            codes = re.findall(r'"([A-Z]+-[A-Z]*-?\d+[a-z]?)"', re.search(r"bom: \[([^\]]*)\]", entry).group(1))
            for code in codes:
                self.assertIn(code, self.bom_codes, f"{pid}: BOM {code} 가 없다")
        for code in ("SH-070", "SH-071", "HG-050", "HG-051", "HG-052", "HG-053", "HG-054", "AS-060", "FC-080", "SV-070", "FP-081"):
            self.assertIn(code, self.bom_codes, f"정비·교체 BOM 행 {code} 가 없다")
        # 6개 장비군의 조립 목록 전부에 「정비·교체」가 있어야 BOM 탐색기에서 그 행이 보인다.
        assemblies = re.findall(r"assemblies:\s*\[([^\]]*)\]", self.html)
        self.assertEqual(len(assemblies), 6, "장비군 조립 목록이 6개가 아니다")
        for listing in assemblies:
            self.assertIn('"정비·교체"', listing, "조립 목록에 정비·교체 가 없다: " + listing[:80])

    def test_no_random_call_sites_were_added(self):
        """시드열 무결 — 난수 호출부가 늘면 재현성이 깨진다. 마모·센서 모델은 결정론적이어야 한다."""
        short = [line for line in self.html.splitlines() if len(line) < 400]
        text = "\n".join(short)
        self.assertEqual(len(re.findall(r"[^A-Za-z]random\(\)", text)), 37)
        self.assertEqual(text.count("visualRandom()"), 17)
        model = self.html[self.html.index("function wearOf("):self.html.index("const plcState = {")]
        self.assertNotIn("random", model, "마모·센서 모델이 난수를 쓴다")


class ThreeDimensionalMarkersTest(unittest.TestCase):
    """등록부의 부품이 3D 에서 교체 모듈로 표식돼 있고, 접근 공간이 예약돼 있는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = read()
        block = WEAR_BLOCK_RE.search(cls.html)
        cls.entries = split_entries(block.group("body"))
        cls.ids = [ENTRY_RE.search(e).group("id") for e in cls.entries]
        # 주석 처리된 줄은 살아 있는 표식이 아니다 — 줄 단위로 `//` 를 걸러 낸 뒤 찾는다.
        live = "\n".join(line for line in cls.html.splitlines() if not line.lstrip().startswith("//"))
        cls.marked = set(re.findall(r'markSwap\([^;]*?"([A-Z0-9-]+)"\)', live))
        if 'markSwap(wetEnd, `${tag.replace("-", "")}-WETEND`)' in live:
            cls.marked |= {pid for pid in cls.ids if pid.endswith("-WETEND")}
        cls.envelopes = set(re.findall(r'addEnvelope\("([A-Z0-9-]+)"', live))
        if '["P101-WETEND", p101]' in live:
            cls.envelopes |= {pid for pid in cls.ids if pid.endswith("-WETEND")}

    def test_every_geometry_part_is_marked_in_3d(self):
        for entry, pid in zip(self.entries, self.ids):
            if "geometry: false" in entry:
                continue
            self.assertIn(pid, self.marked, f"{pid}: 등록부에는 있는데 3D 교체 모듈 표식(markSwap)이 없다")

    def test_marked_ids_exist_in_registry(self):
        for pid in self.marked:
            self.assertIn(pid, self.ids, f"3D 표식 {pid} 가 등록부에 없다")

    def test_extraction_envelopes_cover_the_heavy_swaps(self):
        for pid in ("HSG-BLADE", "ICSH-UPPER-CASSETTE", "ICSH-LOWER-CASSETTE", "SCR-DECK",
                    "BF101-CARTRIDGE", "BF201-CARTRIDGE", "FC-ROTOR", "AS101-ROTOR", "P101-WETEND"):
            self.assertIn(pid, self.envelopes, f"{pid}: 인출·인양 공간(addEnvelope)이 예약돼 있지 않다")
        self.assertIn("scene.add(maintenanceEnvelopes)", self.html, "접근 공간이 circuit 이 아니라 scene 직속이어야 한다")

    def test_sensor_nodes_exist_in_3d(self):
        nodes = set(re.findall(r'addSensorNode\([^,]+, "[^"]+", "([A-Z0-9-]+)"', self.html))
        nodes |= set(re.findall(r'sensorTag = "([A-Z0-9-]+)"', self.html))
        nodes |= {"VIT-P101", "VIT-P102", "VIT-PP201", "VIT-P204", "VIT-P301"} if "wetSensorNode(group, `VIT-${tag.replace" in self.html else set()
        nodes |= {"VIT-211", "VIT-212", "VIT-213"} if "wetSensorNode(cell.group, `VIT-21${index + 1}`" in self.html else set()
        for tag in ("VIT-301", "VIT-302", "VIT-303", "VIT-304", "AE-301", "VIT-102", "VIT-103", "TE-102", "WL-101",
                    "PDT-101", "PDT-201", "VIT-P101", "VIT-211"):
            self.assertIn(tag, nodes, f"센서 {tag} 의 3D 노드가 없다")

    def test_quick_release_hardware_replaced_bolted_access(self):
        """도어 스터드 12본 루프가 사라지고 스윙볼트 래치 8점·가스 스트럿이 있어야 한다."""
        self.assertNotIn("for (let i = 0; i < 12; i += 1) {\n      const angle = Math.PI * 2 * i / 12;\n      addCylinder(parts.P02, 0.018", self.html)
        self.assertIn("doorLatches", self.html)
        self.assertIn("rotorCart", self.html)
        self.assertIn("spareRotor", self.html)
        self.assertIn("screenCartridge", self.html)
        self.assertIn("scrDrawer", self.html)
        self.assertIn("백풀아웃 분할링", self.html)
        self.assertIn('jibCrane.name = "JC-201"', self.html)
        # assertRegex 는 실패 시 대상 문자열(1.8 MB)을 통째로 찍으므로 여기서는 쓰지 않는다
        self.assertTrue(re.search(r"\[-4\.40, \"GB-301\", [^\]]*, -1\.10, 0\.62\]", self.html),
                        "GB-301 냉각 연결관이 드로어 인출 경로 위(y 0.62)로 올라가 있지 않다")


class MaintenanceViewAndPanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = read()

    def test_maintenance_mode_is_wired(self):
        self.assertIn('data-hsg-mode="maintenance"', self.html)
        self.assertIn('data-stage-proxy="[data-hsg-mode=&quot;maintenance&quot;]"', self.html)
        self.assertIn('if (mode === "maintenance") {', self.html)
        self.assertIn("applySwapHighlight()", self.html)
        self.assertIn("clearSwapHighlight()", self.html)
        self.assertIn('maintenanceEnvelopes.visible = mode === "maintenance"', self.html)

    def test_highlight_colour_comes_from_the_brand_mark(self):
        """정비 강조색은 브랜드 심볼의 황색을 계산해서 쓴다 — 리터럴로 두 번 정의하지 않는다."""
        self.assertIn("const MAINT_ACCENT_HEX = parseInt(brandFills.find(", self.html)

    def test_panel_exists_and_is_reachable(self):
        for attr in ("data-maint-health", "data-maint-due", "data-maint-mttr", "data-maint-hours",
                     "data-maint-sim-hours", "data-maint-view", "data-maint-rows", "data-maint-sensors",
                     "data-maint-spares", "data-maint-loto"):
            self.assertIn(attr, self.html, attr + " 가 패널에 없다")
        self.assertIn('data-panel-id="predictive"', self.html)
        category = re.search(r'operation: \{[^\n]*panels: \[([^\]]*)\]', self.html).group(1)
        for pid in ("predictive", "ai"):
            self.assertIn(f'"{pid}"', category, f"{pid} 패널이 운전·제어 카테고리에 등록돼 있지 않다 — storage 에 갇힌다")
        process = re.search(r'process: \{[^\n]*panels: \[([^\]]*)\]', self.html).group(1)
        for pid in ("metallurgy", "screen-sizing"):
            self.assertIn(f'"{pid}"', process, f"{pid} 패널이 어느 카테고리에도 없다")

    def test_panel_updates_on_the_readout_cadence_and_inspect_exposes_it(self):
        self.assertIn("updateReadout();\n        updateMaintenance();", self.html)
        self.assertIn("maintenanceUi.rows && !maintenanceUi.rows.closest(\"[hidden]\")", self.html)
        self.assertIn("maintainability: (() => {", self.html)

    def test_loto_points_are_declared(self):
        block = LOTO_BLOCK_RE.search(self.html)
        self.assertIsNotNone(block)
        self.assertGreaterEqual(len(re.findall(r'id: "LOTO-\d+"', block.group("body"))), 3)
        self.assertIn("LOTO 스테이션", self.html)

    def test_world_class_drive_spec(self):
        """주 구동은 IE5 PM · IP66 — IE4 표기가 남아 있으면 사양이 반쪽이다."""
        short = "\n".join(line for line in self.html.splitlines() if len(line) < 700)
        self.assertNotIn("IE4", short, "IE4 표기가 남아 있다")
        for text in ("초경(WC-Co) 팁", "Hardox 500", "ALS-101 자동 윤활", "MCSA-101"):
            self.assertIn(text, self.html, text + " 사양이 없다")


if __name__ == "__main__":
    unittest.main()
