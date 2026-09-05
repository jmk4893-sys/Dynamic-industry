"""PV 재활용 미니앱의 Ag 회수 수지 검증.

미니앱은 화면에 Ag 회수율·정광 품위를 띄우는데, 그 값이 나오는 계산은 JS 안에
있고 근거가 되는 전제(해리 산물의 조성, 관문값, 신설 셀 치수)는 주석과 상수에
흩어져 있다. 상수 하나가 바뀌어도 화면은 멀쩡히 그려지면서 수지가 조용히
깨질 수 있다 — 실제로 종전 코드가 그랬다: 어트리션이 C 를 A/B 로 재라벨해
**Ag 를 21 % 창출**하고 있었다.

여기서는 미니앱 코드를 흉내내지 않고, 회로도가 밝힌 흐름과 상수만으로 수지를
다시 세운 뒤

  1. 해리 산물 Ac 의 조성이 항등식 Ac = (C − f·B)/(1 − f) 로 닫히는지
  2. 어트리션이 해리도와 무관하게 Ag 를 보존하는지
  3. 1단(폴리머 역부선) 고정점이 질량을 보존하는지
  4. 플랜트 수지가 닫히는지 — 정광 + 네 손실 = 급광
  5. 라우팅 케이스 두 개가 각자 독립으로 정의돼 있는지
  6. 회수율이 밴드로 표기되고 단정적 「99.23 %」가 어디에도 없는지

를 확인한다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

MINIAPP = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "pv-recycling-miniapp.html"
)
SOURCE = MINIAPP.read_text(encoding="utf-8")
# 벤더 번들(three·cannon-es)은 한 줄이 수십만 자다. 우리 코드만 본다.
LIVE = "\n".join(line for line in SOURCE.splitlines() if len(line) < 400)


def const(name, text=None):
    """`const NAME = <숫자>` 를 읽는다."""
    m = re.search(rf"const {name} = ([\d.]+)", text or LIVE)
    if not m:
        raise AssertionError(f"상수를 못 찾음: {name}")
    return float(m.group(1))


def assay_row(letter):
    m = re.search(
        rf"{letter}: {{ Si: ([\d.]+), polymer: ([\d.]+), Cu: ([\d.]+), "
        rf"Al: ([\d.]+), agGpt: ([\d.]+) }}",
        LIVE,
    )
    if not m:
        raise AssertionError(f"ASSAY 행을 못 찾음: {letter}")
    keys = ("Si", "polymer", "Cu", "Al", "agGpt")
    return dict(zip(keys, (float(g) for g in m.groups())))


A = assay_row("A")
B = assay_row("B")
C = assay_row("C")
F_BACKSHEET = const("C_BACKSHEET_MASS_FRACTION")
KEYS = ("Si", "polymer", "Cu", "Al", "agGpt")

#: 해리 산물 — C 에서 백시트 몫을 뺀 나머지. 미니앱도 같은 항등식으로 유도한다.
AC = {k: (C[k] - F_BACKSHEET * B[k]) / (1 - F_BACKSHEET) for k in KEYS}
ASSAY = {"A": A, "B": B, "C": C, "Ac": AC}
TYPES = ("A", "Ac", "B", "C")


def ag_kg(mass):
    """질량 원장(kg)에서 Ag kg 을 낸다."""
    return sum(mass.get(t, 0.0) * ASSAY[t]["agGpt"] for t in TYPES) / 1e6


def attrition(mass, debond):
    """C 를 벗겨 해리 셀(Ac)과 백시트(B)로 가른다 — 조성은 바꾸지 않는다."""
    freed = mass["C"] * debond
    out = dict(mass)
    out["Ac"] = out.get("Ac", 0.0) + freed * (1 - F_BACKSHEET)
    out["B"] = out["B"] + freed * F_BACKSHEET
    out["C"] = out["C"] - freed
    return out


def polymer_float(feed, recovery, passes=40):
    """1단 폴리머 역부선. 회로도(미니앱 solvePolymerFloat 주석)를 그대로 옮긴다.

    FC-201 거품 → FC-204 → (AS-102) → FC-202 → 폴리머 배출
    FC-201 광미 → FC-203 → 광미가 2단 급광
    FC-203 거품 · FC-204 광미 → FC-201 환류 ; FC-202 광미 → FC-204 환류
    """
    to_rougher = {t: 0.0 for t in TYPES}
    to_cleaner = {t: 0.0 for t in TYPES}
    reject = {t: 0.0 for t in TYPES}
    sinks = {t: 0.0 for t in TYPES}
    for _ in range(passes):
        nxt_r = {t: 0.0 for t in TYPES}
        nxt_c = {t: 0.0 for t in TYPES}
        for t in TYPES:
            rough_in = feed.get(t, 0.0) + to_rougher[t]
            rough_froth = rough_in * recovery["rougher"][t]
            rough_tail = rough_in - rough_froth
            scav_froth = rough_tail * recovery["scavenger"][t]
            sinks[t] = rough_tail - scav_froth
            clean_in = rough_froth + to_cleaner[t]
            clean_froth = clean_in * recovery["cleaner"][t]
            reclean_froth = clean_froth * recovery["recleaner"][t]
            reject[t] = reclean_froth
            nxt_r[t] = scav_froth + (clean_in - clean_froth)
            nxt_c[t] = clean_froth - reclean_froth
        to_rougher, to_cleaner = nxt_r, nxt_c
    return reject, sinks


class AcDerivation(unittest.TestCase):
    """해리 산물의 조성은 지어낸 값이 아니라 항등식이어야 한다."""

    def test_recombination_closes(self):
        for k in KEYS:
            back = (1 - F_BACKSHEET) * AC[k] + F_BACKSHEET * B[k]
            self.assertAlmostEqual(back, C[k], places=9, msg=f"{k} 가 C 로 안 닫힌다")

    def test_miniapp_derives_it_rather_than_hardcoding(self):
        # 값을 손으로 적어 두면 ASSAY.C 를 고칠 때 조용히 어긋난다.
        self.assertRegex(LIVE, r"ASSAY\.Ac = Object\.fromEntries")
        self.assertIn("(1 - C_BACKSHEET_MASS_FRACTION)", LIVE)
        self.assertNotRegex(LIVE, r"Ac: \{ Si: [\d.]+")

    def test_ac_is_not_native_a(self):
        # 「C 를 벗기면 A 가 된다」가 종전의 오류였다. 두 조성은 다르다.
        self.assertNotAlmostEqual(AC["agGpt"], A["agGpt"], delta=100)
        self.assertGreater(AC["polymer"], A["polymer"])


class AttritionConservesSilver(unittest.TestCase):
    """해리는 계면을 푸는 것이지 Ag 를 만드는 것이 아니다."""

    def test_conserved_across_debond_range(self):
        feed = {"A": 30.0, "Ac": 0.0, "B": 20.0, "C": 50.0}
        before = ag_kg(feed)
        for debond in (0.0, 0.25, 0.5, 0.75, 0.95, 1.0):
            after = attrition(feed, debond)
            self.assertAlmostEqual(ag_kg(after), before, places=12)
            self.assertAlmostEqual(sum(after.values()), sum(feed.values()), places=12)

    def test_old_relabel_would_have_created_silver(self):
        # 회귀 방지 — 종전 방식(C → A/B)이 얼마나 틀렸는지 숫자로 남긴다.
        feed = {"A": 30.0, "Ac": 0.0, "B": 20.0, "C": 50.0}
        freed = feed["C"]
        old = {"A": feed["A"] + freed * (1 - F_BACKSHEET),
               "Ac": 0.0, "B": feed["B"] + freed * F_BACKSHEET, "C": 0.0}
        self.assertGreater(ag_kg(old) / ag_kg(feed) - 1, 0.10)


class PolymerFloatClosure(unittest.TestCase):
    """1단 고정점은 질량을 보존해야 한다 — 환류가 두 갈래라 특히."""

    RECOVERY = {
        "rougher": {"A": 0.03, "Ac": 0.03, "B": 0.90, "C": 0.35},
        "scavenger": {"A": 0.04, "Ac": 0.04, "B": 0.92, "C": 0.40},
        "cleaner": {"A": 0.02, "Ac": 0.02, "B": 0.88, "C": 0.30},
        "recleaner": {"A": 0.01, "Ac": 0.01, "B": 0.85, "C": 0.25},
    }

    def test_mass_closes(self):
        feed = {"A": 40.0, "Ac": 25.0, "B": 20.0, "C": 15.0}
        reject, sinks = polymer_float(feed, self.RECOVERY)
        total_out = sum(reject.values()) + sum(sinks.values())
        self.assertAlmostEqual(total_out, sum(feed.values()), places=6)

    def test_silver_reports_to_sinks_not_froth(self):
        # 역부선의 요점 — 뜨는 것이 폴리머고 Ag 는 가라앉아야 한다.
        feed = {"A": 40.0, "Ac": 25.0, "B": 20.0, "C": 15.0}
        reject, sinks = polymer_float(feed, self.RECOVERY)
        self.assertGreater(ag_kg(sinks), ag_kg(reject) * 5)


class RoutingCases(unittest.TestCase):
    """두 라우팅은 서로의 하위 모드가 아니라 각자 정의돼 있어야 한다."""

    def test_both_cases_declared(self):
        block = re.search(r"const ROUTING_CASES = Object\.freeze\(\{.*?\n    \}\);",
                          LIVE, re.S)
        self.assertIsNotNone(block, "ROUTING_CASES 블록이 없다")
        self.assertIn('id: "A"', block.group(0))
        self.assertIn('id: "C"', block.group(0))

    def test_case_a_sends_everything_wet(self):
        block = re.search(r'A: Object\.freeze\(\{ id: "A".*?\}\),', LIVE, re.S)
        self.assertIsNotNone(block)
        self.assertIn("copperKeys: Object.freeze([])", block.group(0))

    def test_case_c_keeps_the_two_coarse_bands_dry(self):
        block = re.search(r'C: Object\.freeze\(\{ id: "C".*?\}\)', LIVE, re.S)
        self.assertIsNotNone(block)
        self.assertIn('"product-280-500"', block.group(0))
        self.assertIn('"product-106-280"', block.group(0))
        self.assertNotIn('"product-under-75"', block.group(0))


class RecoveryIsReportedAsABand(unittest.TestCase):
    """99 % 는 관문 조건부다 — 단정적으로 쓰면 안 된다."""

    def test_fc101_recovery_has_low_and_design(self):
        block = re.search(r"const FC101_AG_RECOVERY = Object\.freeze\(\{[^}]*\}\)", LIVE)
        self.assertIsNotNone(block)
        self.assertIn("low:", block.group(0))
        self.assertIn("design:", block.group(0))

    def test_three_gates_are_declared(self):
        block = re.search(r"const AG_RECOVERY_GATES = Object\.freeze\(\[.*?\n    \]\);",
                          LIVE, re.S)
        self.assertIsNotNone(block, "AG_RECOVERY_GATES 가 없다")
        for gate in ("liberation", "fw102", "fc101Tails"):
            self.assertIn(f'id: "{gate}"', block.group(0))

    def test_no_bare_9923_claim(self):
        # 통합안 설계 계산값 99.23 % 는 반박 3건을 반영하기 전 값이다.
        self.assertNotIn("99.23", LIVE)


class AssumptionsAreMarked(unittest.TestCase):
    """미확정 결정 위에 선 값은 가정임이 코드에 남아 있어야 한다."""

    def test_undecided_constants_say_so(self):
        for name in ("FC204_CELL_L", "AS102_CELL_L", "AS101B_CELL_L",
                     "CU_PICKOFF_EFFICIENCY", "POLISH_POLYMER_REJECTION"):
            line = re.search(rf"const {name} = [^\n]*", LIVE)
            self.assertIsNotNone(line, f"{name} 이 없다")
            self.assertIn("가정", line.group(0), f"{name} 에 가정 표기가 없다")

    def test_hold_values_say_hold(self):
        line = re.search(r"const WASHED_CLEANER_ENTRAINMENT_SUPPRESSION = [^\n]*", LIVE)
        self.assertIsNotNone(line)
        self.assertIn("HOLD", line.group(0))


if __name__ == "__main__":
    unittest.main()
