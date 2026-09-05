"""DG-HK60C 압축 배치 — 길이가 어디서 나왔는지 검증.

발주자가 쓰는 기계는 5 m 인데 Rev.20 은 끝에서 끝까지 53 m 였다. 그 길이를
무엇이 만들었는지 따져 보면 처리량은 아니다 — 60장/h 는 5단 소킹과 2.4 m
박리행정이 정하고, 둘 다 바닥 길이를 쓰지 않는다. 길이를 만든 것은 (1) 라인
안에 넣은 환경설비·후속공정·팔레타이징과 (2) 패널을 실어 나른 이송축이다.

그래서 이 시험이 지키는 것은 세 가지다.

  1. 압축 배치의 길이가 '적어 둔 값' 이 아니라 패널·데크·캐리어에서
     파생된 계산이어야 한다. 손으로 적으면 패널 사양이 바뀔 때 한쪽만
     고쳐진다.
  2. 이동 나이프로 바꾸어도 처리량이 유지된다는 주장이 실제로 성립해야
     한다. 박리는 상대운동이라 행정도 시간도 그대로지만, 복귀 한 행정이
     새로 생긴다 — 그 복귀속도의 하한이 계산에서 나와야 한다.
  3. 설비를 공급범위에서 떼어도 인터록은 남아야 한다. 멈춘 슈레더에 셀을
     밀어 넣지 않는 조건은 그 슈레더가 남의 것이 되었다고 사라지지 않는다.

콘솔 코드를 보고 베끼지 않는다. 문서가 밝힌 치수와 식으로 여기서 다시 세운
뒤, 콘솔이 그것과 같은 값을 내는지 대조한다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"

# ── 설계 치수 (m) ────────────────────────────────────────────────────────
PANEL_L, DECK_L, CARRIER_L = 2.400, 2.780, 2.900
CL_CLEAR, CL_WALL, CL_DOOR, CL_PARK, CL_END = 0.30, 0.35, 0.30, 0.45, 0.30

STATIONS = [
    ("LD-101", PANEL_L + 2 * CL_CLEAR),
    ("HC-101", DECK_L + 2 * CL_WALL + CL_DOOR),
    ("DL-101", CARRIER_L + 2 * CL_PARK),
    ("GC-101", DECK_L + 2 * CL_CLEAR),
    ("UL-101", PANEL_L + 2 * CL_CLEAR),
]
COMPACT_M = (sum(w for _, w in STATIONS)
             + (len(STATIONS) - 1) * CL_CLEAR + 2 * CL_END)

REV20_M = 49.7 - (-3.4)          # 디스태커 방책 앞 ~ 굴뚝 뒤
SCOPED_M = 29.3 - 0.0            # 환경·후속·팔레타이징을 뗀 나머지

# ── 사이클 (s) ───────────────────────────────────────────────────────────
KNIFE_PITCH, RAPID_DISTANCE = 300.0, 300.0      # mm
PEEL_SPEED, RAPID_SPEED, HANDLING_FIX = 55.0, 200.0, 3.0
RETURN_SPEED = 700.0
NET_TARGET, AVAILABILITY = 60.0, 0.90

LEAD_S = KNIFE_PITCH / PEEL_SPEED
PEEL_S = PANEL_L * 1000 / PEEL_SPEED
HANDLING_S = RAPID_DISTANCE / RAPID_SPEED + HANDLING_FIX
RETURN_DISTANCE = KNIFE_PITCH + PANEL_L * 1000
TARGET_CYCLE = 3600 / (NET_TARGET / AVAILABILITY)


def carrier_cycle():
    """이동 캐리어 — 복귀가 다음 장 뒤로 숨는다."""
    return LEAD_S + PEEL_S + HANDLING_S


def knife_cycle(return_speed=RETURN_SPEED):
    """이동 나이프 — 복귀가 패널 교환창과 겹치므로 둘 중 긴 쪽만 든다."""
    return LEAD_S + PEEL_S + max(HANDLING_S, RETURN_DISTANCE / return_speed)


def return_speed_floor():
    """순생산 60장/h 를 지키는 복귀속도의 하한 (mm/s)."""
    return RETURN_DISTANCE / (TARGET_CYCLE - LEAD_S - PEEL_S)


# ── 유리 냉각 ────────────────────────────────────────────────────────────
MASS_GLASS, CP_GLASS = 8.000, 0.75          # kg/m² · kJ/(kg·K)
GC_IN, GC_OUT, GC_AMB, GC_H = 180.0, 60.0, 25.0, 25.0


def glass_cool_s():
    import math
    m = MASS_GLASS * PANEL_L * PANEL_W_M
    area = 2 * PANEL_L * PANEL_W_M
    lmtd = (GC_IN - GC_OUT) / math.log((GC_IN - GC_AMB) / (GC_OUT - GC_AMB))
    return m * CP_GLASS * 1e3 * (GC_IN - GC_OUT) / (GC_H * area * lmtd)


PANEL_W_M = 1.200


def console():
    return CONSOLE.read_text(encoding="utf-8")


def fn(name):
    """콘솔에서 함수 하나의 본문을 잘라 온다."""
    src = console()
    i = src.index(f"function {name}(")
    depth, j = 0, src.index("{", i)
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    raise AssertionError(f"{name} 본문을 닫지 못했다")


class TestTheLengthIsDerived(unittest.TestCase):
    """길이는 계산이어야 한다 — 적어 두면 다음에 한쪽만 고쳐진다."""

    def setUp(self):
        self.src = console()
        m = re.search(r"const COMPACT_STATIONS=\[(.*?)\n    \];", self.src, re.S)
        self.assertIsNotNone(m, "COMPACT_STATIONS 를 찾지 못했다")
        self.rows = re.findall(r"\['([A-Z]{2}-\d+)','([^']*)',\s*([^,]+),", m.group(1))
        self.assertEqual(len(self.rows), len(STATIONS))

    def test_every_station_length_is_an_expression(self):
        for (code, _name, expr), (want_code, _) in zip(self.rows, STATIONS):
            self.assertEqual(code, want_code)
            self.assertRegex(
                expr, r"PANEL_L|DECK_L|CARRIER_L",
                f"{code} 길이가 패널·데크·캐리어에서 나오지 않는다: {expr}")
            self.assertNotRegex(
                expr.strip(), r"^\d+(\.\d+)?$",
                f"{code} 길이가 손으로 적은 숫자다: {expr}")

    def test_the_total_is_summed_not_typed(self):
        m = re.search(r"const compactLength=\(\)=>(.*?);", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("COMPACT_STATIONS.reduce", m.group(1))

    def test_the_sheet_writes_no_length_by_hand(self):
        """도면 옆에 손으로 적은 치수가 있으면 그쪽이 갈라진다."""
        body = re.sub(r"/\*.*?\*/", "", fn("compactDrawing"), flags=re.S)
        total_mm = round(COMPACT_M * 1000)
        for lit in (str(total_mm), f"{total_mm:,}"):
            self.assertNotIn(lit, body, f"도면에 손으로 적은 전장: {lit}")
        typed = re.findall(r"(?<![$\w.,])(\d[\d,]{3,6})\s*(?:mm|m\b)", body)
        self.assertEqual(typed, [], f"도면에 손으로 적은 치수: {typed}")


class TestTheCompactLine(unittest.TestCase):
    """세 단계의 전장이 실제로 그 값인지."""

    def setUp(self):
        self.src = console()

    def _num(self, name):
        m = re.search(rf"\b{name}=(-?[\d.]+)\s*[,;]", self.src)
        self.assertIsNotNone(m, f"{name} 를 찾지 못했다")
        return float(m.group(1))

    def test_the_clearances_match(self):
        for name, want in [("CL_CLEAR", CL_CLEAR), ("CL_WALL", CL_WALL),
                           ("CL_DOOR", CL_DOOR), ("CL_PARK", CL_PARK),
                           ("CL_END", CL_END)]:
            self.assertAlmostEqual(self._num(name), want, places=6)

    def test_the_total_is_eighteen_point_seven_six_metres(self):
        self.assertAlmostEqual(COMPACT_M, 18.760, places=6)

    def test_the_three_stages_shrink(self):
        self.assertAlmostEqual(self._num("REV20_X1") - self._num("REV20_X0"),
                               REV20_M, places=6)
        self.assertAlmostEqual(self._num("SCOPED_X1") - self._num("SCOPED_X0"),
                               SCOPED_M, places=6)
        self.assertGreater(REV20_M, SCOPED_M)
        self.assertGreater(SCOPED_M, COMPACT_M)

    def test_the_compaction_is_not_all_scope(self):
        """범위만 정리하고 압축이라 부르면 안 된다 — 기계도 줄어야 한다."""
        by_scope = REV20_M - SCOPED_M
        by_machine = SCOPED_M - COMPACT_M
        self.assertGreater(by_machine, 10.0,
                           "기계 설계로 줄인 길이가 10 m 에 못 미친다")
        self.assertGreater(by_scope, 10.0)


class TestThroughputSurvivesTheMovingKnife(unittest.TestCase):
    """박리가 상대운동이라는 주장이 숫자로도 성립하는지."""

    def test_the_peel_stroke_and_time_do_not_change(self):
        self.assertAlmostEqual(PEEL_S, 2400 / 55, places=9)
        self.assertAlmostEqual(RETURN_DISTANCE, 2700.0, places=9)

    def test_at_the_specified_return_speed_the_cycle_is_unchanged(self):
        self.assertAlmostEqual(knife_cycle(), carrier_cycle(), places=9)

    def test_sixty_panels_per_hour_survives(self):
        net = 3600 / knife_cycle() * AVAILABILITY
        self.assertGreaterEqual(net, NET_TARGET)

    def test_the_floor_is_five_hundred_and_fifty(self):
        self.assertAlmostEqual(return_speed_floor(), 550.0, places=6)
        at_floor = 3600 / knife_cycle(return_speed_floor()) * AVAILABILITY
        self.assertAlmostEqual(at_floor, NET_TARGET, places=6)

    def test_below_the_floor_it_fails(self):
        """하한이 진짜 하한인지 — 조금만 느려도 60장/h 가 깨져야 한다."""
        slow = 3600 / knife_cycle(return_speed_floor() - 50) * AVAILABILITY
        self.assertLess(slow, NET_TARGET)

    def test_the_old_rapid_speed_would_not_do(self):
        """캐리어의 200mm/s 를 그대로 쓰면 못 지킨다 — 축이 달라져야 한다."""
        self.assertLess(3600 / knife_cycle(RAPID_SPEED) * AVAILABILITY, NET_TARGET)

    def test_the_console_solves_the_floor_instead_of_writing_it(self):
        src = console()
        m = re.search(r"const returnSpeedFloor=(.*?);", src)
        self.assertIsNotNone(m, "복귀속도 하한이 계산되지 않는다")
        self.assertIn("returnDistance", m.group(1))
        self.assertNotIn("550", m.group(1), "하한이 손으로 적혀 있다")

    def test_the_console_declares_the_same_return_speed(self):
        src = console()
        self.assertIn("knifeReturnSpeed:%d" % RETURN_SPEED, src.replace(" ", ""))


class TestGlassCoolingBuysTimeWithHeight(unittest.TestCase):
    """냉각은 길이가 아니라 단수로 산다 — 그 단수가 시간을 덮는지."""

    def _decks(self):
        m = re.search(r"const GCOOL_DECKS=(\d+);", console())
        self.assertIsNotNone(m)
        return int(m.group(1))

    def test_the_rack_covers_the_cooling_time(self):
        takt = knife_cycle()
        self.assertGreaterEqual(self._decks() * takt, glass_cool_s(),
                                "냉각 랙 단수가 냉각시간을 덮지 못한다")

    def test_the_rack_matches_the_heating_chamber(self):
        """가열실과 같은 단수라야 랙·포크·예비품이 한 벌이면 된다."""
        self.assertEqual(self._decks(), 5)

    def test_a_conveyor_would_have_been_longer(self):
        """같은 시간을 길이로 사면 얼마였는지 — 높이로 산 이유가 이것이다."""
        slots = glass_cool_s() / knife_cycle()
        self.assertGreater(slots * (PANEL_L + CL_CLEAR), 8.0)


class TestDescopingKeepsTheInterlocks(unittest.TestCase):
    """장치는 경계 밖으로 나가도 신호는 남아야 한다."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "plc_model_compact", ROOT / "tools" / "plc_model.py")
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
        cls.leaves = {l.name for l in cls.m.LEAVES}
        cls.derived = {d.name: d for d in cls.m.DERIVED}

    def _reads(self, name):
        seen, stack = set(), list(self.derived[name].terms)
        while stack:
            t = stack.pop()
            if t in seen:
                continue
            seen.add(t)
            if t in self.derived:
                stack.extend(self.derived[t].terms)
        return seen

    def _read_anywhere(self, sig):
        return any(sig in d.terms for d in self.m.DERIVED)

    def test_the_descoped_equipment_still_has_its_permissive(self):
        for sig in ("SHREDDER_READY", "RTO_TEMP_OK", "PL_IN_STACK_PRESENT"):
            self.assertIn(sig, self.leaves, f"{sig} 가 사라졌다")
            self.assertTrue(self._read_anywhere(sig), f"{sig} 를 아무도 읽지 않는다")

    def test_the_boundary_has_its_own_eyes(self):
        """원격 '준비됨' 접점 하나만 믿으면 안 된다 — 우리가 재는 값이 있어야."""
        for sig in ("DUCT_DP_OK", "CELL_BIN_SPACE_OK"):
            self.assertIn(sig, self.leaves)
            self.assertTrue(self._read_anywhere(sig))

    def test_the_safety_circuit_crosses_the_boundary(self):
        self.assertIn("IF_ESTOP_LOOP_OK", self.leaves)
        self.assertIn("IF_ESTOP_LOOP_OK", self._reads("BOUNDARY_READY"))

    def test_abatement_permit_holds_either_way(self):
        """우리 RTO 든 발주자 후처리든 배기 처리의 근거는 하나여야 한다."""
        reads = self._reads("ABATEMENT_PERMIT")
        self.assertIn("RTO_TEMP_OK", reads)
        self.assertIn("VOC_ABATE_READY", reads)

    def test_the_cell_stream_will_not_push_at_a_full_bin(self):
        self.assertIn("CELL_BIN_SPACE_OK", self._reads("CELL_TRANSFER"))

    def test_the_moving_knife_axis_is_a_permit_condition(self):
        reads = self._reads("KNIFE_TRAVERSE_PERMIT")
        self.assertIn("KNIFE_X_HOME", reads)
        self.assertIn("KNIFE_X_POS", reads)


class TestTheSheetIsReachable(unittest.TestCase):
    """그려 놓고 못 여는 도면은 없는 것과 같다."""

    def setUp(self):
        self.src = console()

    def test_the_button_and_the_tab_exist(self):
        self.assertIn('id="compactDrawingButton"', self.src)
        self.assertIn('data-drawing="compact"', self.src)

    def test_the_renderer_dispatches_to_it(self):
        self.assertIn("drawingTab==='compact'", self.src)
        self.assertIn("compactDrawing()", self.src)

    def test_the_sheet_carries_its_own_revision(self):
        """압축 배치는 Rev.20 이 아니다 — 표제란이 그렇게 말해야 한다."""
        self.assertIn("'REV.21C'", self.src)


class TestTheDocumentsQuoteOneLength(unittest.TestCase):
    """콘솔과 사양서가 같은 전장을 말하는지."""

    def setUp(self):
        self.rfq = RFQ.read_text(encoding="utf-8") if RFQ.exists() else None

    def _spec(self):
        if self.rfq is None:
            self.skipTest("이 브랜치에는 사양서가 없다")
        return self.rfq

    def test_the_specification_quotes_the_compact_length(self):
        self.assertIn(f"{round(COMPACT_M * 1000):,}", self._spec())

    def test_the_specification_no_longer_claims_thirty_eight_metres(self):
        """3.2 의 38,000 mm 는 슈레더와 배기열차를 빼고 센 값이라 틀렸다."""
        self.assertNotIn("약 38,000 mm", self._spec())

    def test_the_specification_states_the_real_rev20_extent(self):
        self.assertIn(f"{round(REV20_M * 1000):,}", self._spec())


class TestTheCompactHall(unittest.TestCase):
    """3D 홀이 실제로 18.76 m 배치를 그리는지.

    도면(D-601)만 고치고 홀은 53 m 인 채로 두면, 같은 콘솔 안에서 두 개정이
    서로 다른 기계를 말하게 된다. 그래서 홀 쪽도 같은 상수에서 나와야 한다.
    """

    def setUp(self):
        self.src = console()

    def _num(self, name):
        m = re.search(rf"\b{name}=(-?[\d.]+)\s*[,;]", self.src)
        self.assertIsNotNone(m, f"{name} 를 찾지 못했다")
        return float(m.group(1))

    def test_the_compact_hall_is_what_opens(self):
        """압축 배치가 발주 범위다 — 콘솔이 그것을 먼저 보여야 한다."""
        self.assertIn("let compactView=true;", self.src)
        self.assertIn("setLayout(true);", self.src)

    def test_both_layouts_stay_reachable(self):
        """Rev.20 을 지우지 않는다 — 무엇을 떼어 무엇이 줄었는지 나란히 봐야 한다."""
        self.assertIn('id="layoutButton"', self.src)
        self.assertIn("function setLayout(compact)", self.src)
        self.assertIn("steps=compact?C21_STEPS:REV20_STEPS", self.src)
        self.assertIn("buildTimeline()", fn("setLayout"),
                      "배치를 바꿔도 타임라인이 그대로면 단계가 어긋난다")

    def test_the_five_stations_are_drawn(self):
        """주석 처리된 호출은 부르는 것이 아니다 — 주석을 걷고 본다."""
        scene = re.sub(r"//[^\n]*|/\*.*?\*/", "", fn_body("compactMachine"), flags=re.S)
        for name in ("cInfeed", "cChamber", "cTandem", "cGlassRack", "cOutfeed"):
            self.assertIn(f"function {name}(", self.src, f"{name} 이 없다")
            self.assertIn(name, scene, f"{name} 이 장면에 불리지 않는다")

    def test_the_station_origins_come_from_the_same_table(self):
        """홀 좌표가 도면의 스테이션 표에서 파생돼야 둘이 갈라지지 않는다."""
        m = re.search(r"const CST=\(\(\)=>\{(.*?)\}\)\(\);", self.src, re.S)
        self.assertIsNotNone(m, "CST 스테이션 원점 표를 찾지 못했다")
        self.assertIn("COMPACT_STATIONS", m.group(1))
        self.assertIn("CL_CLEAR", m.group(1))
        self.assertIn("CL_END", m.group(1))

    def test_the_hall_fits_the_quoted_length(self):
        """마지막 스테이션 끝 + 끝벽이 곧 전장이어야 한다."""
        cur = CL_END
        for _, w in STATIONS:
            cur += w + CL_CLEAR
        self.assertAlmostEqual(cur - CL_CLEAR + CL_END, COMPACT_M, places=6)

    def test_the_panel_stands_still_and_the_knife_moves(self):
        """이 배치의 전부다 — 패널이 서고 칼날이 간다."""
        body = fn_body("cState")
        self.assertRegex(body, r"i>=3&&i<=5\)\{px=CPNL_CX;",
                         "박리 중 패널 x 가 고정이 아니다")
        knife = fn_body("cKnifeX")
        self.assertIn("CHKB0", knife)
        self.assertIn("CHKB1", knife)
        self.assertIn("CHKB_PARK", knife)

    def test_the_knife_stroke_is_the_panel_length(self):
        """행정이 패널 길이가 아니면 상대운동이 같다는 주장이 깨진다."""
        self.assertIn("const CHKB0=CPNL_CX-PANEL_HL,CHKB1=CPNL_CX+PANEL_HL;", self.src)
        self.assertIn("const CHKB_PARK=CHKB0-LEAD_OPEN;", self.src)

    def test_the_heavy_roll_stays_off_the_moving_axis(self):
        """357 kg 만권 롤을 갠트리에 얹으면 700mm/s 복귀가 성립하지 않는다."""
        gantry = fn_body("cGantry")
        self.assertIn("CWEB_Z", gantry, "가이드롤 GR-W1 이 갠트리에 없다")
        self.assertNotIn("CDRUM", gantry, "만권 롤이 이동축에 실려 있다")
        self.assertIn("CDRUM", fn_body("cTandem"), "만권 롤이 고정부에 없다")

    def test_the_web_self_compensation_is_recorded(self):
        """박리 중 권취가 0 인 이유가 코드 옆에 남아 있어야 한다 — 다음 사람이 큰 댄서를 다시 넣는다."""
        head = self.src[self.src.index("Rev.21C 압축 배치 3D"):][:1600]
        self.assertIn("상쇄", head)
        self.assertIn("2,700mm", head)

    def test_the_descoped_equipment_is_not_in_the_hall(self):
        body = fn_body("compactMachine")
        tree = "".join(fn_body(f) for f in
                       ("cInfeed", "cChamber", "cTandem", "cGlassRack",
                        "cOutfeed", "cBoundary", "cUtilities", "cEnclosure"))
        for gone in ("thermalOxidiser", "scrubberUnit", "autonomyStations",
                     "cellHandlingStation", "cellConveyorDevices"):
            self.assertNotIn(gone, body + tree, f"{gone} 이 압축 배치에 남아 있다")

    def test_the_boundary_hardware_is_in_the_hall(self):
        """이름만 라벨에 적혀 있으면 안 된다 — 실제로 그려진 것에 붙어 있어야 한다."""
        drawn = [ln for ln in (fn_body("cBoundary") + fn_body("cTandem")).split("\n")
                 if re.search(r"\b(box|cylinder|poly|plinth|column)\(", ln) and "//" in ln]
        joined = "\n".join(drawn)
        for dev in ("경계 인터페이스반 BJ-101", "경계 안전회로 인터페이스반 BJ-102",
                    "경계 덕트 차압센서", "셀/EVA 배출슈트 레벨센서×2"):
            self.assertIn(dev, joined, f"경계 납품품 {dev} 이 홀에 서 있지 않다")

    def test_the_cooling_rack_reuses_the_heating_rack(self):
        """같은 랙이라는 판단이 도면에도 코드에도 같아야 예비품이 한 벌이다."""
        self.assertIn("cRack(g.cx,g.w", fn_body("cChamber"))
        self.assertIn("cRack(g.cx,g.w", fn_body("cGlassRack"))

    def test_the_title_block_says_which_revision(self):
        self.assertIn("compactView?'REV.21C':'REV.20'", self.src)
        self.assertIn("치수 미확정", self.src)


def fn_body(name):
    """콘솔에서 함수 하나의 본문을 잘라 온다 (모듈 수준 헬퍼의 얇은 껍데기)."""
    return fn(name)
