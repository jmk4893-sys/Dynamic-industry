"""DG-HK60 콘솔의 열수지·사이클 계산 검증.

콘솔은 화면에 두 가지를 함께 보여준다. 하나는 계산 대화상자가 내는 수치이고,
다른 하나는 상세 탭 본문에 사람이 읽는 문장으로 적힌 성능 수치다. 둘은 같은
설계에서 나와야 하는데, 계산은 JS 에 있고 문장은 문자열에 있어 서로를 강제하는
장치가 없었다. 상수 하나만 바꿔도 화면은 멀쩡히 그려지면서 두 값이 조용히
갈라진다.

여기서는 콘솔 코드를 보지 않고 문서가 밝힌 식과 상수만으로 모델을 다시 만든 뒤,

  1. 콘솔이 쓰는 상수가 그 모델의 상수와 같은지
  2. 본문에 적힌 성능 수치가 그 모델의 계산과 맞는지
  3. 모델이 한 곳에만 있고 두 표시가 모두 그것을 부르는지

를 확인한다. 3번이 있어야 1·2번이 계속 의미를 갖는다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

CONSOLE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "pv-delamination-3d.html"
)

# ── 설계 상수 ────────────────────────────────────────────────────────────
# 적층 면적열용량. 유리·EVA·셀·백시트를 합친 단위면적당 열용량이다.
AREAL_CP_KJ_M2K = 8.7358962
# 25 °C 에서 EVA/유리 계면 목표까지. 목표를 200 → 140 °C 로 내렸다.
#
# 가교 EVA 의 결정 융해는 DSC 로 55~95 °C 에서 끝나고, 그 위로는 액체가 되지
# 않고 물러지기만 한다(열경화 망상). 문헌의 100 vs 140 °C 비교도 "과열은
# 박리를 크게 개선하지 않는다"로 끝나고, 상용 핫나이프는 벌크 예열 없이
# 칼날만 180~200 °C 로 쓴다. 200 °C 는 PVDF(165)·PVF(195) 백시트 융점을
# 넘어 권취 중 파단 위험까지 있었다.
T_AMBIENT_C = 25
T_TARGET_C = 140
DELTA_T_K = T_TARGET_C - T_AMBIENT_C
T_HKB_C, T_HKS_C = 180, 200      # 칼날 — NPC 상용 밴드 180~200
# 1D-FDM 으로 구한 계면 도달시간. 열수지상 더 빨리 넣을 수 있어도 열이
# 계면까지 전도되는 데 걸리는 시간은 줄지 않으므로 체류시간의 하한이 된다.
FDM_DWELL_S = 113.15
LAMPS = 60
DECKS = 5
KNIFE_PITCH_MM = 300     # HKB 가 HKS 보다 앞서는 거리
RAPID_DISTANCE_MM = 300  # 장당 급속이송 등가거리

DEFAULTS = dict(
    panelLength=2400.0, panelWidth=1200.0, lampPower=2.5,
    heatEfficiency=65.0, knifeSpeed=55.0, rapidSpeed=200.0, handlingTime=3.0,
)


def thermal_model(**over):
    """문서가 밝힌 식으로 열수지·탠덤·라인 능력을 낸다."""
    v = {**DEFAULTS, **over}
    q = v["panelLength"] * v["panelWidth"] / 1e6 * AREAL_CP_KJ_M2K * DELTA_T_K
    rated = LAMPS * v["lampPower"]
    eta = v["heatEfficiency"] / 100
    dwell = max(DECKS * q / (rated * eta), FDM_DWELL_S)
    pitch = dwell / DECKS
    handling = RAPID_DISTANCE_MM / v["rapidSpeed"] + v["handlingTime"]
    cycle = (KNIFE_PITCH_MM + v["panelLength"]) / v["knifeSpeed"] + handling
    line_cycle = max(pitch, cycle)
    energy = q / (eta * 3600)
    line_rate = 3600 / line_cycle
    return dict(
        q_kj=q, rated_kw=rated, dwell_s=dwell, pitch_s=pitch,
        thermal_rate=3600 / pitch, cycle_s=cycle, tandem_rate=3600 / cycle,
        line_cycle_s=line_cycle, line_rate=line_rate,
        energy_kwh=energy, average_kw=energy * line_rate,
    )


def sixty_panel_run(m):
    """60장 연속시험. n 번째 패널은 5장 전 패널이 빠져야 자리가 난다."""
    starts, ends = [], []
    for n in range(60):
        ready = m["dwell_s"] if n < DECKS else starts[n - DECKS] + m["dwell_s"]
        start = max(ready, ends[n - 1] if n else 0.0)
        starts.append(start)
        ends.append(start + m["cycle_s"])
    return dict(cold_s=ends[-1], steady_s=60 * m["line_cycle_s"])


def as_mmss(seconds):
    t = round(seconds)
    return t // 60, t % 60


class TestModelConstantsAreShared(unittest.TestCase):
    """콘솔이 이 파일과 같은 상수를 쓰는지, 그리고 한 곳에만 두는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _const(self, name):
        m = re.search(rf"const {name}=([\d.]+);", self.html)
        self.assertIsNotNone(m, f"콘솔에 {name} 상수가 없다")
        return float(m.group(1))

    def _model_field(self, name):
        m = re.search(rf"\b{name}:([\d.]+)", self.html)
        self.assertIsNotNone(m, f"MODEL 에 {name} 이 없다")
        return float(m.group(1))

    def test_console_uses_the_same_design_constants(self):
        self.assertAlmostEqual(self._model_field("arealCp"), AREAL_CP_KJ_M2K, places=7)
        self.assertIn("dT:T_TARGET-T_AMB", self.html,
                      "ΔT 가 목표온도에서 파생되지 않고 값으로 적혀 있다")
        self.assertAlmostEqual(self._const("T_TARGET"), T_TARGET_C, places=6)
        self.assertAlmostEqual(self._const("T_AMB"), T_AMBIENT_C, places=6)
        self.assertAlmostEqual(self._const("T_HKB"), T_HKB_C, places=6)
        self.assertAlmostEqual(self._const("T_HKS"), T_HKS_C, places=6)
        self.assertAlmostEqual(self._model_field("fdmDwell"), FDM_DWELL_S, places=6)
        self.assertAlmostEqual(self._model_field("lamps"), LAMPS, places=6)
        self.assertAlmostEqual(self._model_field("decks"), DECKS, places=6)
        self.assertAlmostEqual(self._model_field("knifePitch"), KNIFE_PITCH_MM, places=6)
        self.assertAlmostEqual(
            self._model_field("rapidDistance"), RAPID_DISTANCE_MM, places=6
        )

    def test_each_constant_appears_once(self):
        """상수가 두 번 이상 적혀 있으면 한쪽만 고쳐지는 날이 온다."""
        for literal in ("8.7358962", "113.15"):
            self.assertEqual(
                self.html.count(literal), 1,
                f"{literal} 이 {self.html.count(literal)}곳에 있다 — 모델이 복제되었다",
            )

    def test_both_readouts_call_the_shared_model(self):
        """계산 대화상자와 HUD 전력표시가 각각 식을 구현하면 갈라진다."""
        for fn in ("updateCalculator", "powerMeterActivity"):
            body = re.search(rf"function {fn}\(.*?\n    \}}", self.html, re.S)
            self.assertIsNotNone(body, f"{fn} 를 찾지 못했다")
            self.assertIn(
                "thermalModel(", body.group(0), f"{fn} 가 공용 모델을 쓰지 않는다"
            )
            self.assertIn(
                "readModelInputs()", body.group(0),
                f"{fn} 가 공용 입력 판독을 쓰지 않는다",
            )

    def test_input_ranges_are_shared(self):
        """두 표시가 입력을 다르게 자르면 범위 밖 값에서 서로 다른 답을 낸다.

        합치기 전에는 대화상자만 패널길이를 2400 에 클램프하고 HUD 는 상한이
        없어서, 9999 를 넣으면 두 곳이 다른 처리량을 보고했다.
        """
        self.assertIn("const MODEL_RANGE=", self.html, "입력 허용구간이 공유되지 않는다")
        ranges = re.search(r"const MODEL_RANGE=\{(.*?)\};", self.html, re.S).group(1)
        for field in DEFAULTS:
            self.assertIn(field, ranges, f"{field} 의 허용구간이 없다")
        # 판독 함수가 그 구간으로 자르는지
        reader = re.search(r"function readModelInputs\(\).*?\n    \}", self.html, re.S)
        self.assertIn("clamp(", reader.group(0), "입력을 허용구간으로 자르지 않는다")


class TestStatedFiguresMatchTheModel(unittest.TestCase):
    """본문에 사람이 읽으라고 적어둔 수치가 실제 계산과 맞는지.

    화면의 문장과 계산기가 갈라지면 어느 쪽이 맞는지 알 수 없게 된다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        cls.m = thermal_model()
        cls.run60 = sixty_panel_run(cls.m)

    def _stated(self, pattern):
        m = re.search(pattern, self.html)
        self.assertIsNotNone(m, f"본문에서 수치를 찾지 못했다: {pattern}")
        return [float(g.replace(",", "")) for g in m.groups()]

    def test_heat_per_panel(self):
        (mj,) = self._stated(r"패널당 필요열량 ([\d.]+)MJ")
        self.assertAlmostEqual(self.m["q_kj"] / 1000, mj, places=2)

    def test_dwell_pitch_and_thermal_limit(self):
        dwell, pitch, rate = self._stated(
            r"5장 열체류 ([\d.]+)초·방출피치 ([\d.]+)초·열공정 한계 ([\d.]+)장/h"
        )
        self.assertAlmostEqual(self.m["dwell_s"], dwell, delta=0.05)
        self.assertAlmostEqual(self.m["pitch_s"], pitch, delta=0.05)
        self.assertAlmostEqual(self.m["thermal_rate"], rate, delta=0.05)

    def test_tandem_cycle_at_both_speeds(self):
        c55, r55, c60, r60 = self._stated(
            r"55mm/s 탠덤 ([\d.]+)초·([\d.]+)장/h, 60mm/s 탠덤 ([\d.]+)초·([\d.]+)장/h"
        )
        self.assertAlmostEqual(self.m["cycle_s"], c55, delta=0.05)
        self.assertAlmostEqual(self.m["tandem_rate"], r55, delta=0.05)
        fast = thermal_model(knifeSpeed=60)
        self.assertAlmostEqual(fast["cycle_s"], c60, delta=0.05)
        self.assertAlmostEqual(fast["tandem_rate"], r60, delta=0.05)

    def test_nominal_and_derated_throughput(self):
        cycle, nominal, derated = self._stated(
            r"55mm/s 탠덤 사이클 ([\d.]+)초·명목 ([\d.]+)장/h·90% 환산 ([\d.]+)장/h"
        )
        self.assertAlmostEqual(self.m["cycle_s"], cycle, delta=0.05)
        self.assertAlmostEqual(self.m["line_rate"], nominal, delta=0.05)
        self.assertAlmostEqual(self.m["line_rate"] * 0.9, derated, delta=0.05)

    def test_shift_output(self):
        h8, h16 = self._stated(r"8시간 90% 약 ([\d,]+)장·16시간 90% 약 ([\d,]+)장")
        self.assertAlmostEqual(self.m["line_rate"] * 8 * 0.9, h8, delta=0.5)
        self.assertAlmostEqual(self.m["line_rate"] * 16 * 0.9, h16, delta=0.5)

    def test_thermal_margin(self):
        margin, derated = self._stated(
            r"열공정 여유 약 ([\d.]+)%, 90% 가동률 순생산 ([\d.]+)장/h"
        )
        expected = (
            (self.m["thermal_rate"] - self.m["line_rate"]) / self.m["thermal_rate"] * 100
        )
        self.assertAlmostEqual(expected, margin, delta=0.05)
        self.assertAlmostEqual(self.m["line_rate"] * 0.9, derated, delta=0.05)

    def test_sixty_panel_run(self):
        """냉간은 첫 5장을 채우는 시간만큼 정상상태보다 길다."""
        sm, ss, cm, cs = self._stated(
            r"60장 정상상태 약 (\d+)분(\d+)초·FULL_LOAD_ACK 이후 냉간 약 (\d+)분(\d+)초"
        )
        self.assertEqual(as_mmss(self.run60["steady_s"]), (int(sm), int(ss)))
        self.assertEqual(as_mmss(self.run60["cold_s"]), (int(cm), int(cs)))
        self.assertGreater(
            self.run60["cold_s"], self.run60["steady_s"],
            "냉간이 정상상태보다 짧을 수 없다",
        )


class TestPowerMeterReadout(unittest.TestCase):
    """PM-101 은 순간전력과 누적 전력량을 함께 표시한다."""

    @classmethod
    def setUpClass(cls):
        cls.body = re.search(
            r"function powerMeterActivity\(.*?\n    \}",
            CONSOLE.read_text(encoding="utf-8"), re.S,
        ).group(0)

    def test_cumulative_energy_survives_the_stage_change(self):
        """가열이 끝났다고 계기가 0 으로 돌아가면 '누적' 이 아니다.

        고치기 전에는 kwh 가 i===2 분기에서만 대입돼, S3 이후 모든 단계에서
        전력은 126.4 kW 를 가리키는데 전력량은 0.00 kWh 로 떨어졌다.
        """
        self.assertRegex(
            self.body, r"else if\(i>2\)\{[^}]*kwh=",
            "가열 단계 이후에 누적 전력량을 잃는다",
        )
        self.assertIn("batchKwh", self.body, "배치 전력량을 이름 붙여 두지 않았다")


class TestModelBehaviour(unittest.TestCase):
    """모델 자체가 물리적으로 말이 되는지. 상수를 잘못 넣으면 여기서 걸린다."""

    def test_fdm_floor_binds_when_lamps_are_ample(self):
        """램프를 아무리 키워도 계면 도달시간 아래로는 못 내려간다."""
        m = thermal_model(lampPower=3.0, panelLength=1600, panelWidth=800)
        self.assertAlmostEqual(m["dwell_s"], FDM_DWELL_S, places=6)

    def test_bottleneck_moves_to_heating_when_peeling_is_fast(self):
        slow = thermal_model(knifeSpeed=35)
        fast = thermal_model(knifeSpeed=60, lampPower=1.0)
        self.assertGreater(slow["cycle_s"], slow["pitch_s"], "35mm/s 는 탠덤 병목이어야 한다")
        self.assertGreater(fast["pitch_s"], fast["cycle_s"], "램프가 모자라면 열 병목이어야 한다")

    def test_line_rate_never_beats_either_limit(self):
        for speed in (35, 45, 55, 60):
            for lamp in (1.0, 2.0, 2.5, 3.0):
                m = thermal_model(knifeSpeed=speed, lampPower=lamp)
                self.assertLessEqual(
                    m["line_rate"], min(m["thermal_rate"], m["tandem_rate"]) + 1e-9,
                    f"{speed}mm/s·{lamp}kW 에서 라인 능력이 병목을 넘었다",
                )

    def test_energy_per_panel_is_independent_of_speed(self):
        """패널 한 장을 데우는 데 드는 에너지는 박리속도와 무관하다."""
        a = thermal_model(knifeSpeed=35)["energy_kwh"]
        b = thermal_model(knifeSpeed=60)["energy_kwh"]
        self.assertAlmostEqual(a, b, places=9)

    def test_average_power_never_exceeds_installed_rating(self):
        for speed in (35, 45, 55, 60):
            m = thermal_model(knifeSpeed=speed)
            self.assertLess(
                m["average_kw"], m["rated_kw"],
                f"{speed}mm/s 에서 평균전력이 설치정격을 넘었다",
            )

    def test_heat_scales_with_area(self):
        small = thermal_model(panelLength=1600, panelWidth=800)
        big = thermal_model(panelLength=2400, panelWidth=1200)
        self.assertAlmostEqual(
            big["q_kj"] / small["q_kj"], (2400 * 1200) / (1600 * 800), places=9
        )


if __name__ == "__main__":
    unittest.main()


class TestProcessTemperature(unittest.TestCase):
    """공정 온도가 왜 그 값인지, 그리고 한 곳에만 있는지.

    계면 목표는 200 → 140 °C, 칼날은 230/250–270 → 180/200 °C 로 내렸다.
    근거는 세 갈래다 — 가교 EVA 는 결정 융해(55~95 °C)가 끝나면 액체가 되지
    않고 물러지기만 하는 열경화 망상이고, 문헌의 100 vs 140 °C 비교도 과열이
    박리를 크게 개선하지 않는다로 끝나며, 상용 핫나이프는 벌크 예열 없이
    칼날만 180~200 °C 로 쓴다.

    이 시험이 지키는 것은 값 자체가 아니라 **값이 흩어지지 않는 것**이다.
    카세트 온도는 칼날 온도 그 자체이므로 별칭이어야 하고, 계면 목표는
    ΔT 의 유일한 출처여야 한다.
    """

    EVA_MELT_TOP = 95        # 가교 EVA 결정 융해 상단 (DSC)
    PVDF_MELT = 165          # 백시트 최저 융점층
    NPC_BAND = (180, 200)    # 상용 핫나이프 칼날 밴드

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def _c(self, name):
        m = re.search(rf"const {name}=([\d.]+);", self.html)
        self.assertIsNotNone(m, f"콘솔에 {name} 상수가 없다")
        return float(m.group(1))

    def test_the_interface_target_sits_in_the_useful_window(self):
        """결정 융해는 끝나야 하고, 백시트는 녹으면 안 된다."""
        t = self._c("T_TARGET")
        self.assertGreater(t, self.EVA_MELT_TOP,
                           "목표가 EVA 결정 융해 상단보다 낮다 — 물러지지 않는다")
        self.assertLess(t, self.PVDF_MELT,
                        "목표가 PVDF 백시트 융점을 넘는다 — 권취 중 찢어진다")

    def test_the_knives_sit_in_the_commercial_band(self):
        lo, hi = self.NPC_BAND
        for name in ("T_HKB", "T_HKS"):
            v = self._c(name)
            self.assertGreaterEqual(v, lo, f"{name} 가 상용 밴드 아래다")
            self.assertLessEqual(v, hi, f"{name} 가 상용 밴드 위다")
        self.assertLessEqual(self._c("T_HKB"), self._c("T_HKS"),
                             "백시트 칼날이 유리계면 칼날보다 뜨겁다 — 백시트에 직접 닿는 쪽이다")

    def test_the_knives_are_hotter_than_the_bulk(self):
        """칼날은 국부 승온을 담당한다 — 벌크보다 낮으면 아무 일도 못 한다."""
        self.assertGreater(self._c("T_HKB"), self._c("T_TARGET"))

    def test_the_cassette_temperature_is_the_knife_temperature(self):
        """값을 두 번 적으면 칼날만 내리고 카세트는 그대로인 날이 온다."""
        self.assertIn("const CASS_T_HOT=T_HKS,", self.html,
                      "카세트 온도가 칼날 온도의 별칭이 아니다")

    def test_delta_t_has_one_source(self):
        self.assertIn("dT:T_TARGET-T_AMB", self.html)
        self.assertNotRegex(self.html, r"dT:\s*\d",
                            "ΔT 가 값으로도 적혀 있다")

    def test_no_stale_two_hundred_degree_interface_remains(self):
        """칼날 200°C 는 남아도 되지만 '계면 200°C' 는 남으면 안 된다."""
        for stale in ("계면 200", "계면을 200", "25→200", "ΔT 175"):
            self.assertNotIn(stale, self.html, f"낡은 온도 표기가 남아 있다: {stale}")
