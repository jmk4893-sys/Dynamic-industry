"""SV-201 2단 복합기 — 상단 직사각 280 µm → 하단 원형 106/75 µm.

BOM 은 처음부터 복합기를 기술하고 있었다 — overall 2,600×1,800×2,700 · 독립 스키드
2,400×1,600 · 코일스프링 8 · 대향 진동모터 2 는 상단 직사각(직선진동)의 사양이고,
basis 의 Ø1,200 이 하단 원형(수직축 편심)이다. 3D 는 오랫동안 원형 하나에 세 장을
몰아넣어 상단이 통째로 빠져 있었다.

처음 세운 복합기는 PC-201 라이저와 CC-201 급입 사이 슬롯 1,270 mm 에 맞춰 줄여 그렸고
그 불일치를 SV-H3 HOLD 로 들고 있었다. 2026-09-05 CC-201 이하를 동측 1.6 m 이설하기로
결정해(≥1.4 m 요구) 슬롯이 2,990 mm 가 됐고, 복합기는 BOM 크기 그대로 서 있다.

여기서는 미니앱 소스에서

  1. 두 기계의 컷이 갈라져 있는지 (280 / 106·75)
  2. 두 진동 구동이 각각 전력·BOM 에 있는지 — 되돌린 시도는 하단 원형의 수직축
     모터를 어디에도 계상하지 않았다
  3. 마모 모듈이 두 종류로 등록되고 3D 에 표식돼 있는지
  4. 모델이 BOM 외형 그대로인지, 그리고 그 결정(SV-H3 해소)이 기록돼 있는지
  5. 직선진동 스크린이 관행대로 0–5° 이고, 하단 원형이 언더팬 출구(동단) 아래 있는지
  6. CC-201 이하가 실제로 ≥1.4 m 동측에 있는지 — 건식 후단과 습식 열차 모두

를 확인한다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

MINIAPP = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "pv-recycling-miniapp.html"
)
SOURCE = MINIAPP.read_text(encoding="utf-8")
LIVE = "\n".join(line for line in SOURCE.splitlines() if len(line) < 400)

# 이설 전 좌표 (b0b0c14) — 이설량 검사의 기준점
BEFORE_X = {"ccCenter": 4.72, "cyclone2Center": 5.82, "bfCenter": 6.72, "polisherCenter": 6.08}
TK001_BEFORE_X = 9.42
SHIFT_MIN_M = 1.4


def const(name):
    # `const A = 1;` 과 `const A = 1, B = 2;` 둘 다 읽는다 — 스키드 치수가 한 줄에 있다.
    m = re.search(rf"(?:const |, ){name} = (-?[\d.]+)", LIVE)
    if not m:
        raise AssertionError(f"상수를 못 찾음: {name}")
    return float(m.group(1))


def vector_x(name):
    m = re.search(rf"const {name} = new THREE\.Vector3\((-?[\d.]+),", LIVE)
    if not m:
        raise AssertionError(f"Vector3 상수를 못 찾음: {name}")
    return float(m.group(1))


def block(pattern):
    m = re.search(pattern, LIVE, re.S)
    if not m:
        raise AssertionError(f"블록을 못 찾음: {pattern[:40]}")
    return m.group(0)


class TwoStagesTwoCuts(unittest.TestCase):
    """컷이 기계별로 갈라져 있어야 한다."""

    def test_rect_takes_280_and_circular_takes_the_rest(self):
        self.assertEqual(const("PRIMARY_RECT_CUT_UM"), 280)
        cuts = re.search(r"const SECONDARY_SIEVE_CUTS_UM = Object\.freeze\(\[([\d, ]+)\]\)", LIVE)
        self.assertIsNotNone(cuts)
        self.assertEqual([int(v) for v in cuts.group(1).split(",")], [106, 75])

    def test_circular_has_two_decks(self):
        m = re.search(r"const secondaryDeckYs = \[([\d., ]+)\]", LIVE)
        self.assertIsNotNone(m)
        self.assertEqual(len(m.group(1).split(",")), 2)

    def test_retain_map_covers_rect_two_decks_and_pan(self):
        retain = block(r"const SIEVE_RETAIN_DECK = \{.*?\};")
        for key, deck in (("product-280-500", 0), ("product-106-280", 1),
                          ("product-75-106", 2), ("product-under-75", 3)):
            self.assertIn(f'"{key}": {deck}', retain)

    def test_the_cascade_has_a_rect_leg_before_the_circular(self):
        self.assertIn("function rectDeckPoint(", LIVE)
        self.assertIn("function circularDeckPoint(", LIVE)
        self.assertRegex(LIVE, r"sievePassRadius\(track\.sizeMm, PRIMARY_RECT_CUT_UM\)")


class LinearMotionScreenPractice(unittest.TestCase):
    """직선진동 스크린은 던짐각으로 이송하므로 0–5° 에 설치한다."""

    def test_incline_is_shallow(self):
        m = re.search(r"const RECT_INCLINE = THREE\.MathUtils\.degToRad\((\d+)\)", LIVE)
        self.assertIsNotNone(m, "RECT_INCLINE 이 없다")
        self.assertLessEqual(int(m.group(1)), 5)

    def test_two_opposed_exciters_with_their_own_nameplate(self):
        self.assertEqual(const("RECT_EXCITER_RPM"), 960)
        self.assertIn("rectExciters.push({ rotor, dir: side })", LIVE)
        self.assertIn("for (const side of [-1, 1])", LIVE)

    def test_rect_and_circular_vibrate_as_separate_bodies(self):
        # 같은 그룹에 넣으면 두 기계가 한 몸처럼 흔들린다 — 되돌린 시도가 VS-501 에서 그랬다.
        self.assertIn("rectGroup.position.copy(rectMotionOffset)", LIVE)
        self.assertIn("secondaryGroup.position.copy(secondaryMotionOffset)", LIVE)
        self.assertIn("vs501Group.position.copy(vs501MotionOffset)", LIVE)
        self.assertNotIn("addBox(secondaryGroup, { x: 0.78, y: 0.025, z: 0.42 }", LIVE,
                         "VS-501 분배 데크가 아직 원형 진동체 안에 있다")

    def test_underpan_discharges_at_the_toe_end_and_the_circular_sits_under_it(self):
        # 직선진동은 팬 위의 언더도 토출단 쪽으로 실어 나른다 — 원형은 동단 아래여야 한다.
        x0, x1 = const("RECT_X0"), const("RECT_X1")
        circular_x = vector_x("secondaryCenter")
        self.assertGreater(circular_x, (x0 + x1) / 2, "원형이 직사각 중앙보다 서쪽에 있다")
        self.assertLessEqual(circular_x + 0.64, x1 + 0.30, "원형이 직사각 동단을 너무 벗어난다")
        self.assertIn("openHopperGeometry(", LIVE)
        self.assertIn("const SV201_SPIGOT_X = secondaryCenter.x;", LIVE)


class BothDrivesAreAccounted(unittest.TestCase):
    """전력·BOM 에 두 구동이 다 있어야 한다 — 종전에는 수직축 모터가 어디에도 없었다."""

    def test_power_panel_has_both(self):
        sieve = block(r"panel:\"LCP-SV-201\".*?\n      \]")
        self.assertIn('tag:"M-SV-1/2",qty:2,duty:2,kw:1.5', sieve)
        self.assertIn('tag:"M-SV-3",qty:1,duty:1,kw:2.2', sieve)
        declared = float(re.search(r"declaredDemandKw:([\d.]+)", sieve).group(1))
        duty = sum(float(kw) * int(d) for d, kw in re.findall(r"duty:(\d+),kw:([\d.]+)", sieve))
        self.assertAlmostEqual(declared, duty, places=6, msg=f"선언 {declared} ≠ 분기 합 {duty}")

    def test_bom_has_both_motors(self):
        self.assertRegex(LIVE, r'code:"SV-050".*?name:"대향 진동모터 \(상단 직사각\)",qty:2')
        self.assertRegex(LIVE, r'code:"SV-052".*?name:"수직축 편심 진동모터 \(하단 원형\)",qty:1')

    def test_electrical_table_lists_both(self):
        self.assertIn('tag:"M-SV-3",load:"2.2 kW"', LIVE)


class TwoKindsOfWearModule(unittest.TestCase):
    """상단은 핀인 모듈, 하단은 섹터 패널 — 절차가 다르므로 등록도 따로."""

    def test_registry_splits_the_module(self):
        self.assertIn('id: "SV201-RECT-PANEL"', LIVE)
        self.assertIn('id: "SV201-PANEL", machine: "SV-201", tag: "P19", part: "하단 원형 2단 데크 섹터 패널 (106/75 µm)"', LIVE)

    def test_both_are_marked_in_3d(self):
        self.assertIn('markSwap(rectPanels, "SV201-RECT-PANEL")', LIVE)
        self.assertIn('markSwap(sv201Panels, "SV201-PANEL")', LIVE)

    def test_spares_follow(self):
        self.assertRegex(LIVE, r'code:"SV-070".*?106/75 µm 각 3')
        self.assertRegex(LIVE, r'code:"SV-071".*?예비 핀인 모듈 \(상단 직사각\)",qty:6')

    def test_module_count_matches_the_deck(self):
        # 1,800×1,200 데크를 600×600 모듈 3×2 로 덮는다 — BOM 수량·핀 수량이 따라와야 한다.
        self.assertEqual(const("RECT_MODULE"), 0.60)
        self.assertRegex(LIVE, r'code:"SV-021".*?qty:6.*?600×600')
        self.assertRegex(LIVE, r'code:"SV-023".*?qty:12')


class TheModelIsBuiltToBom(unittest.TestCase):
    """이설 뒤에는 줄일 이유가 없다 — 모델 스키드 = BOM 스키드, 데크 1,800×1,200."""

    def test_skid_equals_bom(self):
        x0, x1 = const("SKID_X0"), const("SKID_X1")
        z0, z1 = const("SKID_Z0"), const("SKID_Z1")
        self.assertAlmostEqual(x1 - x0, 2.40, places=6)
        self.assertAlmostEqual(z1 - z0, 1.60, places=6)

    def test_deck_is_1800_by_1200(self):
        self.assertAlmostEqual(const("RECT_X1") - const("RECT_X0"), 1.80, places=6)
        self.assertAlmostEqual(const("RECT_HZ") * 2, 1.20, places=6)
        self.assertRegex(LIVE, r'code:"SV-020".*?1,800×1,200')

    def test_six_legs_twelve_anchors(self):
        # F-SV-01 은 12SET — 다리 6 × 앵커 2. 기초표의 앵커 격자도 12 점이어야 한다.
        self.assertIn("const SKID_LEG_X = [SKID_X0 + 0.06, skidMidX, SKID_X1 - 0.06];", LIVE)
        self.assertIn("gridAnchors([-1228,-1052,-88,88,1052,1228],[-800,800])", SOURCE)
        self.assertRegex(LIVE, r'code:"F-SV-01".*?qty:12')

    def test_inspect_carries_the_envelope_and_the_decision(self):
        env = block(r"const SV201_ENVELOPE = Object\.freeze\(\{.*?\}\);")
        self.assertIn("bomOverallMm: [2600, 1800, 2700]", env)
        self.assertIn("bomSkidMm: [2400, 1600]", env)
        self.assertIn("slotMm: 2990", env)
        self.assertIn("layoutDecision:", env)
        self.assertIn("1.6 m 이설", env)
        self.assertIn("envelope: SV201_ENVELOPE", LIVE)

    def test_hold_row_records_the_relocation_and_is_released(self):
        # holds 배열은 한 줄이 400 자를 넘어 LIVE 에서 걸러지므로 원본을 본다
        m = re.search(r'\{id:"SV-H3",stage:"배치",check:"([^"]+)",record:"([^"]+)",gate:"([A-Z]+)"', SOURCE)
        self.assertIsNotNone(m, "SV-H3 배치 행이 없다")
        check, record, gate = m.groups()
        self.assertIn("1.6 m 이설", check)
        self.assertIn("2,400×1,600", check)
        self.assertIn("2026-09-05", record)
        self.assertNotEqual(gate, "HOLD", "이설로 해소된 HOLD 가 아직 HOLD 다")


class DownstreamMovedEast(unittest.TestCase):
    """CC-201 이하가 실제로 ≥1.4 m 동측으로 갔는지 — 건식 후단과 습식 열차 둘 다."""

    def test_dry_tail_anchors(self):
        for name, before in BEFORE_X.items():
            self.assertGreaterEqual(vector_x(name), before + SHIFT_MIN_M - 1e-9, name)

    def test_wet_train_followed(self):
        m = re.search(r'wetTank\("TK-001", (-?[\d.]+),', LIVE)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(float(m.group(1)), TK001_BEFORE_X + SHIFT_MIN_M - 1e-9)
        # 습식 접경(VR-401 · BH-101)도 같이 갔어야 건식 후단과 겹치지 않는다
        self.assertGreaterEqual(const("bufferX"), 7.82 + SHIFT_MIN_M - 1e-9)

    def test_the_shift_is_uniform_for_the_tail(self):
        # 후단은 한 덩어리로 옮겼다 — 상대 배치가 그대로여야 배관·슈트가 성립한다.
        deltas = {name: round(vector_x(name) - before, 3) for name, before in BEFORE_X.items()}
        self.assertEqual(len(set(deltas.values())), 1, deltas)

    def test_what_stays_put_stays_put(self):
        # 이설 대상이 아닌 것 — PC-201 리시버(x 2.52) · VP-401 헤더 · 제어반 열 · FW-102
        self.assertIn("const pc201ReceiverCenter = new THREE.Vector3(2.52,", LIVE)
        self.assertIn("const vacuumHeader = [[5.30, 1.34, -2.46], [5.86, 1.34, -2.46]];", LIVE)
        self.assertIn('wetControlPanel("PLC-001", 6.72, -2.82,', LIVE)
        self.assertIn('[7.65, 0.50, -1.15], material.equipmentDewater, "FW-102 플레이크 마찰세척"', LIVE)

    def test_the_vent_header_and_rack_reach_the_moved_tail(self):
        m = re.search(r"const ventHeaderX = \[1\.86, (-?[\d.]+)\]", LIVE)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(float(m.group(1)), 6.95 + SHIFT_MIN_M - 1e-9)
        self.assertIn("[0.90, 3.70, 6.40, 8.60].forEach((x) => {", LIVE)


class ThePlatformDoesNotPierceAnything(unittest.TestCase):
    """되돌린 시도의 VS-501 기둥 4개는 원형 체와 언더 호퍼를 관통했다."""

    def test_vs501_rides_the_skid_portal_not_floor_columns(self):
        self.assertIn("VS-501 받침 — 스키드 서단의 포털", LIVE)
        self.assertNotRegex(LIVE, r"y: 1\.62, z: 0\.06 \}, \{ x: 2\.78 \+ dx, y: 0\.93",
                            "옛 바닥 기둥 4개가 남아 있다")

    def test_stack_lift_is_bounded_by_the_vent_header(self):
        lift = const("SV201_STACK_LIFT")
        header = const("VENT_HEADER_Y")
        # 리시버 상단 = 1.75 + lift + 0.14 가 헤더 하단(헤더 반경 0.05) 아래여야 한다
        self.assertLess(1.75 + lift + 0.14, header - 0.05 + 1e-9)


class SeedSequenceUntouched(unittest.TestCase):
    def test_no_random_call_sites_were_added(self):
        self.assertEqual(len(re.findall(r"[^A-Za-z]random\(\)", LIVE)), 37)
        self.assertEqual(LIVE.count("visualRandom()"), 17)


if __name__ == "__main__":
    unittest.main()
