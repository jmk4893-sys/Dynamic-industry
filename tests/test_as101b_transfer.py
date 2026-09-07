"""AS-101 ↔ AS-101B 이송 — 「펌프안」 확정(2026-09-07)의 형상·전력·정비 등록 검사.

어트리션 2 단(AS-101B)은 SV-201 이설과 무관하게 야드(구 AS-102 자리)에 서 있고, 그
결과 **양쪽 다리가 오르막**이다. 이것이 이 트랜치의 뿌리다 — 처음 HOLD 를 걸 때는
「가는 다리만 펌프, 오는 다리는 중력」으로 셈했는데, 실측 노즐 표고를 보면

    가는 다리 AS-101 토출 EL 0.639 → AS-101B 급액 EL 1.263   (+0.624 m)
    오는 다리 AS-101B 배출 EL 0.627 → BS-101A 수입 EL 1.110   (+0.483 m)

둘 다 올라간다. 그래서 펌프가 **두 조**(P-103A/B · P-104A/B) 필요하다. 이 시험은 그
셈이 형상에서 계속 참인지, 그리고 그 대가(전력 1.5 kW · 마모부 2 종 · LOTO 2 점)가
등록부에 실제로 계상돼 있는지를 잡는다.

원심이 아니라 호스(연동)펌프인 근거도 모델 상수에서 다시 확인한다 —
운전유량 0.244 m³/h 는 DN50 원심의 최소유량 아래이고, 순환물에는 BS-101A 슬롯(1.0 mm)이
잡는 크기의 알루미나 비드가 섞여 있다.
"""

import ast
import pathlib
import re
import unittest

from . import _path  # noqa: F401

MINIAPP = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "pv-recycling-miniapp.html"
)
SOURCE = MINIAPP.read_text(encoding="utf-8")
# 주석 처리한 줄은 살아 있는 코드가 아니다 — 등록 여부를 볼 때는 이쪽을 본다.
LIVE = "\n".join(line for line in SOURCE.splitlines() if not line.lstrip().startswith("//"))

# 실측 노즐 표고 (3D 형상에서 읽은 값) — 배관 끝점이 이 높이에 붙어 있어야 한다.
AS101_OUTLET_EL = 0.639
AS101B_INLET_EL = 1.263
AS101B_OUTLET_EL = 0.627
BS101A_INLET_EL = 1.110
PIPE_HANGER_MIN_Y = 0.80   # 이 위의 수평부는 배관지지 자동배치가 행거로 판정한다


def field(obj, name):
    """`AS101B_TRANSFER` 같은 객체 리터럴에서 숫자 필드를 읽는다."""
    m = re.search(rf"const {obj} = Object\.freeze\(\{{(.*?)\n    \}}\);", LIVE, re.S)
    if not m:
        raise AssertionError(f"객체를 못 찾음: {obj}")
    value = re.search(rf"\b{name}:\s*(-?[\d.]+)", m.group(1))
    if not value:
        raise AssertionError(f"{obj}.{name} 가 없다")
    return float(value.group(1))


def const(name):
    m = re.search(rf"(?:const |, ){name} = (-?[\d.]+)", LIVE)
    if not m:
        raise AssertionError(f"상수를 못 찾음: {name}")
    return float(m.group(1))


def pump_call(tag):
    m = re.search(rf'wetHosePumpPair\("{re.escape(tag)}", (-?[\d.]+), (-?[\d.]+), (\d+),', LIVE)
    if not m:
        raise AssertionError(f"{tag} 호스펌프 조가 없다")
    return {"x": float(m.group(1)), "z": float(m.group(2)), "activation": int(m.group(3))}


def run_points(label):
    """`wetTube(unifiedWet, [[...], ...], d, mat, "label", ...)` 의 점 배열을 읽는다.

    호출 하나가 여러 줄에 걸치므로 라벨을 먼저 찾고 **거기서 앞으로** 자기 호출의
    여는 괄호까지 되짚는다. 앞에서부터 `.*?` 로 훑으면 앞선 wetTube 의 점들을
    같이 물어 온다(실제로 그렇게 물었다).

    점 배열에는 `p103.suction` 같은 식별자도 섞이는데, 여기서 보는 것은 좌표라
    리터럴 삼중항만 뽑는다.
    """
    at = LIVE.find(f'"{label}"')
    if at < 0:
        raise AssertionError(f"배관 라벨을 못 찾음: {label}")
    start = LIVE.rfind("wetTube(unifiedWet, [", 0, at)
    if start < 0:
        raise AssertionError(f"{label}: wetTube 호출을 못 찾음")
    body = LIVE[start:at]
    return [tuple(ast.literal_eval(f"[{p}]")) for p in
            re.findall(r"\[(-?[\d.]+, -?[\d.]+, -?[\d.]+)\]", body)]


def wear_entry(pid):
    block = re.search(r"const WEAR_PARTS = Object\.freeze\(\[(.*?)\n    \]\);", LIVE, re.S).group(1)
    for entry in re.split(r"\n    (?=\{ id: )", block):
        if f'id: "{pid}"' in entry:
            return entry
    raise AssertionError(f"{pid} 마모부 등록이 없다")


class TheYardPlacementCostsTwoPumpedLegs(unittest.TestCase):
    """왜 두 조인가 — 노즐 표고가 양쪽 다 올라가기 때문이다."""

    def test_both_legs_climb_so_neither_can_return_by_gravity(self):
        forward = AS101B_INLET_EL - AS101_OUTLET_EL
        back = BS101A_INLET_EL - AS101B_OUTLET_EL
        self.assertGreater(forward, 0, "가는 다리가 내리막이면 펌프가 필요 없다")
        self.assertGreater(back, 0, "오는 다리가 내리막이면 중력 복귀가 되고 P-104 는 과잉이다")
        self.assertAlmostEqual(field("AS101B_TRANSFER", "forwardLiftM"), forward, places=3)
        self.assertAlmostEqual(field("AS101B_TRANSFER", "returnLiftM"), back, places=3)

    def test_two_pump_pairs_stand_at_each_end_of_the_yard_run(self):
        p103, p104 = pump_call("P-103"), pump_call("P-104")
        # P-103 은 AS-101(주기기 열) 쪽, P-104 는 AS-101B(야드 동단) 쪽에 붙어야
        # 각각이 밀어내는 다리에서 흡입 배관이 짧다.
        self.assertLess(p103["x"], p104["x"], "두 펌프 조가 같은 쪽에 몰려 있다")
        self.assertGreater(p104["x"] - p103["x"], 8.0, "P-104 가 반송 다리 시점(야드 동단)에 없다")
        # 가동 표식 — 이송은 어트리션이 도는 동안만 돈다(공회전 마모는 호스 수명을 깎는다)
        self.assertGreater(p103["activation"], p104["activation"],
                           "1 단 급액과 2 단 반송의 가동 시점이 뒤바뀌었다")

    def test_the_pump_is_sized_above_the_operating_flow(self):
        design = field("AS101B_TRANSFER", "designM3H")
        # 운전유량은 모델이 스스로 계산한다 — 여기서 하드코딩하면 급광이 바뀌어도 통과한다.
        self.assertIn("const AS101_FEED_M3H = slurryFlowM3H(WET_FEED_KGH, AS101_FEED_SOLIDS_WT)", LIVE)
        self.assertGreater(design, 0.244, "설계유량이 운전유량 아래다")
        self.assertLess(design, 0.244 * 2, "설계유량이 운전유량의 2 배를 넘는다 — 최소유량 문제를 되레 키운다")

    def test_the_slurry_basis_matches_the_attrition_feed(self):
        self.assertAlmostEqual(field("AS101B_TRANSFER", "solidsWt"), const("AS101_FEED_SOLIDS_WT"), places=3)
        # SG = 1 / (w/2.4 + (1-w)) at w = 0.65
        sg = 1.0 / (0.65 / 2.4 + 0.35)
        self.assertAlmostEqual(field("AS101B_TRANSFER", "slurrySg"), sg, places=2)

    def test_hose_pump_rationale_is_recorded_not_assumed(self):
        for reason in ("최소유량", "비드"):
            self.assertIn(reason, LIVE, f"호스펌프 선정 근거({reason})가 소스에 없다")
        self.assertIn("호스(연동) 펌프 · DN32", LIVE)


class TheRoutesLandOnRealNozzles(unittest.TestCase):
    """배관이 노즐 표고에 실제로 닿는지, 그리고 지지가 성립하는 높이로 도는지."""

    def test_forward_leg_starts_at_the_as101_outlet_and_ends_at_the_as101b_inlet(self):
        suction = run_points("AS-101 배출 → P-103A/B 흡입")
        self.assertAlmostEqual(suction[0][1], AS101_OUTLET_EL, places=3)
        feed = run_points("P-103A/B → AS-101B 급액")
        self.assertAlmostEqual(feed[-1][1], AS101B_INLET_EL, places=3)

    def test_return_leg_starts_at_the_as101b_outlet(self):
        suction = run_points("AS-101B 배출 → P-104A/B 흡입")
        self.assertAlmostEqual(suction[0][1], AS101B_OUTLET_EL, places=3)

    def test_horizontal_runs_stay_below_the_hanger_threshold(self):
        """y ≥ 0.80 의 수평부는 자동 배관지지가 행거로 판정해 로드를 데크까지 뽑는다.

        야드 회랑에는 매달 구조가 없으므로, 그렇게 두면 허공에 뜬 행거가 그려진다.
        수평부는 0.80 아래로 두고, 높이를 바꾸는 구간만 가파르게 끊는다.
        """
        self.assertAlmostEqual(const("PIPE_HANGER_MIN_Y"), PIPE_HANGER_MIN_Y, places=3)
        for label in ("P-103A/B → AS-101B 급액", "P-104A/B → BS-101A 반송"):
            points = run_points(label)
            for a, b in zip(points, points[1:]):
                run = ((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
                rise = abs(a[1] - b[1])
                if run < 1e-9:
                    continue                       # 순수 수직 — 지지 대상이 아니다
                if rise / run > 0.72:
                    continue                       # 가파른 전이 구간 — 자동배치가 건너뛴다
                self.assertLess(max(a[1], b[1]), PIPE_HANGER_MIN_Y,
                                f"{label}: {a}–{b} 수평부가 행거 판정 높이 위에 있다")

    def test_the_old_two_centimetre_stub_is_gone(self):
        """이설 전에는 두 통 사이가 2 cm 라 배관이랄 것도 없었다 — 그 잔재가 남으면 안 된다."""
        self.assertNotIn('"AS-101 → BS-101A"', LIVE, "옛 스텁 배관이 아직 살아 있다")


class PipeSupportsHangFromRealSteel(unittest.TestCase):
    """이송배관을 놓다 드러난 결함 — 지지 자동배치가 티어를 무한 평면으로 봤다.

    y 만 보고 행거를 걸었기 때문에, 위가 텅 빈 야드 회랑에서도 로드가 벤트 헤더
    높이(2.46 m)까지 올라갔다. 실측하니 행거 36 개 중 33 개가 그런 허공 행거였다.
    티어마다 실제로 덮는 x·z 를 들게 하고, 덮지 않으면 아무것도 놓지 않는다.

    바닥 스탠션으로 대신 받치는 안도 넣어 봤으나, 그러면 11 본 중 6 본이 AB-201A
    모터·P-401A 펌프·AR-301 리시버를 관통한다 — 허공 행거를 관통 기둥으로 바꾸는
    맞바꿈일 뿐이라 되돌렸다.
    """

    def tiers(self):
        block = re.search(r"const wetSupportTiers = \[(.*?)\n    \]\.sort", LIVE, re.S)
        self.assertIsNotNone(block, "wetSupportTiers 를 못 찾음")
        return block.group(1)

    def test_every_tier_declares_where_its_steel_actually_is(self):
        body = self.tiers()
        entries = re.findall(r"\{ y: (\w+), x: (\[[^\]]*\]|\w+), z: (\[[^\]]*\]|\w+) \}", body)
        self.assertGreaterEqual(len(entries), 5, "티어 항목이 줄었다")
        self.assertEqual(len(entries), len(re.findall(r"\{ y:", body)),
                         "x·z 범위 없이 y 만 든 티어가 남아 있다")
        used = {e[0] for e in entries}
        for tier in ("VENT_HEADER_Y", "DRY_RETURN_Y", "DECK_TOP_Y", "VAC_RACK_Y"):
            self.assertIn(tier, used, f"{tier} 티어가 빠졌다")

    def test_the_deck_tier_matches_the_deck_it_names(self):
        body = self.tiers()
        self.assertIn("x: [DECK_X0, DECK_X1], z: [DECK_Z0, DECK_Z1]", body,
                      "데크 티어 범위가 데크 치수 상수와 이어져 있지 않다 — 데크를 늘리면 어긋난다")
        self.assertIn("x: [LAND_X0, LAND_X1]", body, "ST-201 랜딩이 티어로 들어 있지 않다")

    def test_a_point_with_no_steel_above_gets_no_support_at_all(self):
        placement = re.search(r"if \(point\.y >= PIPE_HANGER_MIN_Y\) \{(.*?)\n          \} else \{",
                              LIVE, re.S).group(1)
        self.assertIn("point.x >= t.x[0]", placement, "x 범위를 보지 않는다")
        self.assertIn("point.z >= t.z[0]", placement, "z 범위를 보지 않는다")
        self.assertIn("if (tier === undefined) continue;", placement,
                      "덮는 티어가 없을 때 그냥 넘어가지 않는다")
        self.assertNotIn("wetPipeStanchion", placement,
                         "매달 곳이 없다고 바닥 기둥을 세우면 설비를 관통한다")


class TheDecisionIsRecordedWithItsResidual(unittest.TestCase):

    def test_hold_is_resolved_but_keeps_the_rheology_residual(self):
        hold = re.search(r"const WET_NEW_KIT_HOLD = Object\.freeze\(\[(.*?)\n    \]\);", LIVE, re.S)
        self.assertIsNotNone(hold, "WET_NEW_KIT_HOLD 를 못 찾음")
        body = hold.group(1)
        self.assertIn("해소", body, "HOLD 가 아직 미해소로 남아 있다")
        self.assertIn("residual: AS101B_TRANSFER.vendorHold", body, "해소하면서 잔여 확인사항을 지웠다")
        vendor = re.search(r'vendorHold: "([^"]+)"', LIVE)
        self.assertIsNotNone(vendor, "vendorHold 문구가 없다")
        self.assertIn("항복응력", vendor.group(1), "잔여 항목이 유변물성이 아니다")

    def test_the_console_shows_the_residual_not_just_the_resolution(self):
        self.assertIn("h.residual", LIVE, "패널이 잔여 확인사항을 렌더링하지 않는다")

    def test_the_stream_document_carries_the_decision(self):
        doc = (MINIAPP.parents[1] / "ag-recovery-stream3.md").read_text(encoding="utf-8")
        self.assertIn("펌프안으로 확정", doc, "결정이 문서에 없다")
        for token in ("P-103", "P-104", "0.624", "0.483"):
            self.assertIn(token, doc, f"문서에 {token} 근거가 없다")


class TheCostIsBookedEverywhere(unittest.TestCase):
    """펌프 4 대는 전력·정비·격리·BOM 에 동시에 나타나야 한다."""

    def test_power_branches_exist_and_the_declared_demand_covers_them(self):
        pkg = re.search(r"agRecovery:\{(.*?)\n      \]", LIVE, re.S).group(1)
        for tag in ("P-103A/B", "P-104A/B"):
            self.assertIn(f'tag:"{tag}",qty:2,duty:1,kw:0.75', pkg, f"{tag} 전력 분기가 없다")
        declared = float(re.search(r"declaredDemandKw:([\d.]+)", pkg).group(1))
        duty = sum(int(d) * float(kw) for d, kw in re.findall(r"duty:(\d+),kw:([\d.]+)", pkg))
        self.assertAlmostEqual(declared, duty, places=2,
                               msg="명세 최대수요가 분기 duty 합과 다르다 — 다이버시티 근거 없이 벌어졌다")

    def test_hoses_are_registered_as_wear_modules_with_a_leak_detector(self):
        for pid, sensor in (("P103-HOSE", "LDT-P103"), ("P104-HOSE", "LDT-P104")):
            entry = wear_entry(pid)
            self.assertIn("limit: 2000", entry, f"{pid} 수명이 2,000 h 가 아니다")
            self.assertIn("mttrMin: 40", entry)
            self.assertIn(sensor, entry, f"{pid} 에 {sensor} 가 묶여 있지 않다")
            self.assertIn(f'tag: "{sensor}"', LIVE, f"{sensor} 조건감시 등록이 없다")
        # 파단하면 케이싱 윤활유에 슬러리가 섞인다 — 전도도로 잡는다
        self.assertIn('kind: "leak"', LIVE)
        # assertRegex 는 실패하면 대상 문자열(1.9 MB)을 통째로 찍는다 — 여기서는 쓰지 않는다
        self.assertTrue(re.search(r"leak:\s*\{[^}]*idle:", LIVE), "SENSOR_MODEL 에 leak 곡선이 없다")

    def test_the_leak_probe_exists_in_3d(self):
        self.assertIn('leakProbe.userData.sensorTag = `LDT-${tag.replace("-", "")}`', LIVE,
                      "호스 파단 검출기가 3D 에서 센서 태그를 달고 있지 않다")

    def test_isolation_point_covers_both_pumps(self):
        loto = re.search(r'\{ id: "LOTO-402".*?\}', LIVE, re.S).group(0)
        for tag in ("P-103A/B", "P-104A/B"):
            self.assertIn(tag, loto, f"LOTO-402 가 {tag} 를 덮지 않는다")
        self.assertEqual(int(re.search(r"locks: (\d+)", loto).group(1)), 9,
                         "잠금 수가 덮는 기기 수와 맞지 않는다")

    def test_bom_carries_the_pumps_spares_and_the_pulsation_damper(self):
        codes = {m.group(1): m.group(0) for m in re.finditer(r'\{code:"(AS-0[5-9]\d)".*?\}', LIVE)}
        for code in ("AS-053", "AS-054", "AS-055", "AS-056", "AS-057", "AS-058"):
            self.assertIn(code, codes, f"BOM 행 {code} 가 없다")
        self.assertIn("qty:4", codes["AS-055"], "예비 호스가 펌프 4 대분이 아니다")
        self.assertIn("맥동", codes["AS-056"], "맥동 감쇠기가 없다 — 슈 이탈 맥동이 배관 피로를 만든다")

    def test_nozzle_and_electrical_schedules_point_at_the_pumps(self):
        rows = {m.group(1): m.group(0) for m in re.finditer(r'\{tag:"(AS-N0[45])".*?\}', LIVE)}
        self.assertIn("P-103A/B → AS-101B (2단)", rows.get("AS-N04", ""), "AS-N04 가 P-103 을 가리키지 않는다")
        self.assertIn("P-104A/B → BS-101A", rows.get("AS-N05", ""), "AS-N05 가 P-104 를 가리키지 않는다")
        # 반송 인입은 스크린 중심이 아니라 크라운 상부다 — 배관이 그리 붙어 있다
        self.assertIn("EL +1110", rows["AS-N05"], "AS-N05 표고가 상부 노즐과 다르다")
        for tag in ("P-103A/B", "P-104A/B"):
            self.assertTrue(re.search(r'tag:"' + re.escape(tag) + r'",load:"0\.75 kW×2"', LIVE),
                            f"{tag} 전기 명세 행이 없다")


if __name__ == "__main__":
    unittest.main()
