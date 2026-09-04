"""세계 최상급 고도화 네 축을 고정한다.

축마다 '없으면 조용히 지나가는 것' 이 다르다.

  회수율   무게를 재지 않으면 회수율은 주장일 뿐이다. 그런데 화면에는
           아무 표시가 나지 않는다 — 숫자를 적어 넣으면 그만이다.
  공정지능 고정 레시피는 쉬운 패널에서 시간을 버리고 어려운 패널에서 유리를
           깬다. 둘 다 사이클 평균에는 안 나타난다.
  무인화   사람 개입 넷 중 하나만 자동화가 빠져도 무인 시간은 그 주기로 끊긴다.
  환경     배출을 계측하지 못하는 동안의 가열은 기록도 처리도 되지 않는다.

그래서 네 축을 수치와 인터록 항으로 묶어 확인한다. 질량 가정은 독립적으로
세운 열 가정과 대조하고(둘이 같은 적층을 말하는지), 나머지는 실행 모델과
도면에 실제로 그려진 줄을 본다.
"""

import importlib.util
import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"


def _model():
    spec = importlib.util.spec_from_file_location("plc_model", ROOT / "tools" / "plc_model.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.console = CONSOLE.read_text(encoding="utf-8")
        cls.rfq = RFQ.read_text(encoding="utf-8") if RFQ.exists() else None

    def c(self, name):
        m = re.search(rf"\b{name}=([\d.]+)", self.console)
        self.assertIsNotNone(m, f"콘솔에 {name} 상수가 없다")
        return float(m.group(1))


class TestMassBalanceBasis(_Base):
    """회수율은 질량 비율이다. 그 질량이 열 계산과 같은 적층을 말해야 한다."""

    def test_areal_mass_and_heat_capacity_describe_the_same_stack(self):
        cp = (self.c("MASS_GLASS") * self.c("CP_GLASS")
              + self.c("MASS_EVA") * self.c("CP_EVA")
              + self.c("MASS_CELL") * self.c("CP_CELL")
              + self.c("MASS_BACK") * self.c("CP_BACK"))
        heat = float(re.search(r"면적×([\d.]+)×\(200−25\)", self.console).group(1))
        self.assertLess(
            abs(cp - heat) / heat, 0.01,
            f"질량 가정의 면적열용량 {cp:.4f} 가 열수지가 쓰는 {heat} 와 1% 넘게 다르다 — "
            "두 계산이 서로 다른 패널을 말하고 있다")

    def test_recovery_shares_sum_to_one(self):
        m = {k: self.c(f"MASS_{k}") for k in ("GLASS", "EVA", "CELL", "BACK")}
        total = sum(m.values())
        shares = (m["GLASS"] / total, (m["EVA"] + m["CELL"]) / total, m["BACK"] / total)
        self.assertAlmostEqual(sum(shares), 1.0, places=9)
        self.assertGreater(shares[0], 0.75, "유리가 회수 질량의 대부분이어야 한다")

    def test_cell_eva_mass_matches_the_shredder_assumption(self):
        """OI-08 슈레더 부하는 패널당 셀/EVA 4 kg 가정 위에 서 있다."""
        per = (self.c("MASS_EVA") + self.c("MASS_CELL")) * self.c("PANEL_L") * self.c("PANEL_W")
        self.assertTrue(3.2 <= per <= 4.0,
                        f"패널당 셀/EVA {per:.2f} kg 가 사양서의 3.2~4.0 범위 밖이다")

    def test_balance_tolerance_is_declared(self):
        self.assertAlmostEqual(self.c("BALANCE_TOL"), 0.02, places=6)

    def test_specification_repeats_the_computed_figures(self):
        if self.rfq is None:
            self.skipTest("이 브랜치에는 사양서가 없다")
        m = {k: self.c(f"MASS_{k}") for k in ("GLASS", "EVA", "CELL", "BACK")}
        total = sum(m.values())
        panel = total * self.c("PANEL_L") * self.c("PANEL_W")
        self.assertIn(f"{total:.3f}", self.rfq, "사양서 5.5 의 면적질량 합이 콘솔과 다르다")
        self.assertIn(f"{panel:.1f} kg/장", self.rfq, "사양서 5.5 의 패널 질량이 콘솔과 다르다")
        for share, label in ((m["GLASS"] / total, "유리"),
                             ((m["EVA"] + m["CELL"]) / total, "셀/EVA"),
                             (m["BACK"] / total, "백시트")):
            self.assertIn(f"{share * 100:.1f} %", self.rfq,
                          f"사양서 5.5 의 {label} 회수 비율이 콘솔과 다르다")


class TestUnmannedOperation(_Base):
    """사람 개입 넷을 모두 덮어야 무인 시간이 그 주기로 끊기지 않는다."""

    def setUp(self):
        self.m = _model()
        self.derived = {d.name: d for d in self.m.DERIVED}

    def reaches(self, name):
        """이름이 결국 읽는 모든 항. 중간 신호로 한 단계 내려가도 요구는 남는다."""
        seen, stack = set(), list(self.derived[name].terms)
        while stack:
            t = stack.pop()
            if t in seen:
                continue
            seen.add(t)
            if t in self.derived:
                stack.extend(self.derived[t].terms)
        return seen

    def test_permit_covers_every_manual_intervention(self):
        p = self.derived["UNMANNED_PERMIT"].terms
        for term, why in (("AUTO_FEED", "팔레트 투입"),
                          ("AUTO_STACK", "유리 적재"),
                          ("KC_MAGAZINE_READY", "칼날 교환"),
                          ("BIN_LEVEL_OK", "반출함 만재")):
            self.assertIn(term, p, f"무인 허가가 {why} 를 보지 않는다")

    def test_roll_handoff_is_modelled(self):
        self.assertIn("ROLL_HANDOFF", self.derived, "만권 롤 무인 반출이 모델에 없다")
        self.assertIn("AGV_DOCKED", self.derived["ROLL_HANDOFF"].terms)

    def test_knife_autochange_does_not_require_loto(self):
        """무인 운전 중 LOTO 를 요구하면 그 허가는 영원히 성립하지 않는다."""
        t = self.reaches("KNIFE_AUTOCHANGE")
        self.assertNotIn("LOTO_APPLIED", t)
        self.assertNotIn("MAINT_PERMIT", t)
        self.assertNotIn("ZERO_ENERGY_ACK", t)
        for term in ("KNIVES_CLEAR", "CARRIER_PARKED", "KC_ARM_HOME"):
            self.assertIn(term, t, f"칼날 자동교환이 {term} 없이 돈다")

    def test_the_new_machines_are_drawn(self):
        body = re.search(r"\n    function autonomyStations\(.*?\n    \}", self.console, re.S)
        self.assertIsNotNone(body, "autonomyStations 가 없다")
        drawn = "\n".join(ln for ln in re.sub(r"/\*.*?\*/", "", body.group(0), flags=re.S).split("\n")
                          if re.search(r"\b(?:box|cylinder|column|plinth)\(", ln))
        for token in ("PL-101 자동 디스태커 승강마스트", "PL-101 자동 디스태커 흡착 포크",
                      "PL-201 자동 스태커 승강마스트", "PL-201 자동 스태커 흡착 포크",
                      "KC-101 칼날 카세트 매거진×2 랙", "KC-101 칼날 카세트 매거진×2 교환암",
                      "AD-101 AGV 도킹 스테이션 도킹패드", "무인 감시 열화상 카메라×3",
                      "반출함 레벨센서×3", "캐리어 파킹 위치센서"):
            self.assertIn(token, drawn, f"{token} 가 도면에 그려지지 않았다")
        self.assertIn("autonomyStations();", self.console, "무인화 설비가 배치에 놓이지 않았다")


class TestProcessIntelligence(_Base):
    def setUp(self):
        self.m = _model()
        self.derived = {d.name: d for d in self.m.DERIVED}

    def test_adaptive_speed_reads_the_load_cells(self):
        t = self.derived["SPEED_SETPOINT"].terms
        self.assertIn("PEEL_FORCE", t, "적응 속도가 박리력을 읽지 않는다")
        self.assertIn("ADAPT_ENABLE", t)
        self.assertIn("RECIPE_VALIDATED", self.derived["ADAPT_ENABLE"].terms)

    def test_adaptive_band_is_bounded_by_the_process_limits(self):
        band = re.search(r"(\d+)~(\d+)mm/s 구간에서 박리력", self.console)
        self.assertIsNotNone(band, "적응 속도 구간이 적혀 있지 않다")
        lo, hi = int(band.group(1)), int(band.group(2))
        self.assertLess(lo, 55, "적응 하한이 기본값 55mm/s 보다 낮아야 의미가 있다")
        self.assertGreaterEqual(hi, 60, "적응 상한이 FAT 상한 60mm/s 를 담아야 한다")

    def test_knife_wear_closes_the_open_item(self):
        """OI-12 는 수명도 판정 기준도 없다고 적혀 있었다."""
        self.assertIn("KNIFE_WEAR_WARN", self.derived)
        self.assertIn("CUT_LENGTH_TOTAL", self.derived["KNIFE_WEAR_WARN"].terms)
        self.assertTrue("신품 대비 1.20배" in self.console,
                        "칼날 교체 판정 기준(신품 대비 배수)이 적혀 있지 않다")
        self.assertTrue("OI-12" in self.console,
                        "칼날 마모 판정이 어느 확인사항을 닫는지 적혀 있지 않다")

    def test_a_panel_without_a_record_is_not_released(self):
        t = self.derived["PANEL_RELEASE"].terms
        self.assertIn("TRACE_WRITE_OK", t,
                      "기록 성공이 반출 허가의 항이 아니다 — 이력은 사후에 못 만든다")

    def test_oee_has_a_reason_code_source(self):
        self.assertIn("STOP_REASON_CODED", self.derived["OEE_VALID"].terms)


class TestEmissionAndRecovery(_Base):
    def setUp(self):
        self.m = _model()
        self.derived = {d.name: d for d in self.m.DERIVED}

    def test_heating_requires_treatable_and_measurable_emission(self):
        """배출을 처리·계측하지 못하는 동안의 가열은 기록도 처리도 되지 않는다."""
        self.assertIn("EMISSION_OK", self.derived["IR_ENABLE"].terms,
                      "배출 처리·계측 없이 IR 을 켤 수 있다")
        e = self.derived["EMISSION_OK"].terms
        self.assertIn("CEMS_OK", e)
        self.assertIn("RTO_READY", e)

    def test_fire_is_seen_by_flame_not_only_smoke(self):
        t = self.derived["CHAMBER_FIRE_TRIP"].terms
        self.assertIn("FLAME_DETECT", t, "화염 자체를 보는 입력이 없다")
        leaf = {l.name: l for l in self.m.LEAVES}["FLAME_DETECT"]
        self.assertEqual(leaf.io, self.m.FDI, "불꽃감지는 안전 입력이어야 한다")

    def test_purge_needs_its_own_pressure(self):
        self.assertIn("N2_PRESSURE_OK", self.derived["N2_PURGE"].terms,
                      "질소가 없는데 퍼지 지령만 나가면 아무 일도 일어나지 않는다")

    def test_heat_recovery_is_modelled(self):
        self.assertIn("HX_OUTLET_TEMP", self.derived["HEAT_RECOVERY"].terms)

    def test_the_oxidiser_is_drawn(self):
        body = re.search(r"\n    function thermalOxidiser\(.*?\n    \}", self.console, re.S)
        self.assertIsNotNone(body, "thermalOxidiser 가 없다")
        drawn = "\n".join(ln for ln in re.sub(r"/\*.*?\*/", "", body.group(0), flags=re.S).split("\n")
                          if re.search(r"\b(?:box|cylinder|column|plinth|vesselSkirt)\(", ln))
        # 장치 이름만 보면 그 이름을 쓰는 다른 줄이 남아 있어도 통과한다.
        # 부재 단위로 좁혀야 하나를 빼는 것이 잡힌다.
        for token in ("RTO-101 축열식 열산화로 축열탑", "RTO-101 축열식 열산화로 절환밸브",
                      "RTO-101 축열식 열산화로 보조버너", "RTO-101 축열식 열산화로 급기팬",
                      "HX-101 배기–급기 열교환기 본체", "CEMS-101 연속배출감시 굴뚝",
                      "CEMS-101 연속배출감시 분석기 캐비닛", "가열실 불꽃감지기×2",
                      "NP-101 질소 퍼지 유닛 실린더", "NP-101 질소 퍼지 유닛 압력센서"):
            self.assertIn(token, drawn, f"{token} 가 도면에 그려지지 않았다")


class TestWeighingIsDrawn(_Base):
    def test_every_scale_stands_in_the_drawing(self):
        body = re.search(r"\n    function weighingStations\(.*?\n    \}", self.console, re.S)
        self.assertIsNotNone(body, "weighingStations 가 없다")
        drawn = "\n".join(ln for ln in re.sub(r"/\*.*?\*/", "", body.group(0), flags=re.S).split("\n")
                          if re.search(r"\b(?:box|cylinder|column|plinth)\(", ln))
        for token in ("WI-101 투입 계량 컨베이어 로드셀", "WI-101 투입 계량 컨베이어 계량베드",
                      "WO-301 권취롤 계량 새들 로드셀", "WO-302 셀 벨트 계량기 로드셀",
                      "WO-302 셀 벨트 계량기 계량롤러", "WO-303 유리 캐리지 계량대 로드셀",
                      "WO-303 유리 캐리지 계량대 계량판", "RE-101 잔류 EVA 분광계 NIR 헤드",
                      "RE-101 잔류 EVA 분광계 스캔빔"):
            self.assertIn(token, drawn, f"{token} 가 도면에 그려지지 않았다")
        self.assertIn("weighingStations();", self.console, "계량 설비가 배치에 놓이지 않았다")

    def test_balance_closes_over_all_three_streams(self):
        d = {x.name: x for x in _model().DERIVED}
        for term in ("ROLL_MASS", "CELL_MASS_RATE", "GLASS_MASS"):
            self.assertIn(term, d["MASS_BALANCE_OK"].terms,
                          f"물질수지가 {term} 계통을 빼고 닫힌다")
        self.assertIn("PANEL_MASS_IN", d["MASS_BALANCE_OK"].terms,
                      "투입을 재지 않으면 수지가 아니라 반출 합계일 뿐이다")


if __name__ == "__main__":
    unittest.main()
