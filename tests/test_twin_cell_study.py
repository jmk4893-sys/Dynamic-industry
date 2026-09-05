"""DG-HK120C 검토서 — 두 셀 구성의 수치가 콘솔 모델과 같은 근거를 쓰는가.

검토서는 발주 문서가 아니지만 그렇다고 아무 숫자나 써도 되는 것은 아니다.
사이클·면적열용량·FDM 하한·유리 물성은 DG-HK60 콘솔이 검증한 가정이고,
이 문서는 그 가정을 규모만 키워 쓴다. 두 곳이 갈라지면 검토서 쪽이 틀린다.

여기서 보는 것은 값의 일치가 아니라 *유도가 성립하는가* 다 — 세 제약이
실제로 채택안을 가두는지, 채택 규칙이 문서에 적힌 대로인지.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import console_consts                                        # noqa: E402

from .test_drawings import standalone_document_checks
from .test_pv_console_calculator import (AREAL_CP_KJ_M2K, DEFAULTS, FDM_DWELL_S,
                                         thermal_model)

ROOT = pathlib.Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs" / "dg-hk120-twin-cell.html"
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
TITLE = "DG-HK120C 검토서 · 1챔버 2탠덤셀"

CELLS = 2
GLASS_ALLOW_MPA = 7.0
REF_MARGIN = 16.9          # DG-HK60C 열공정 여유


def study():
    return STUDY.read_text(encoding="utf-8")


def const(name, src=None):
    """검토서 모델 블록의 값 하나."""
    m = re.search(rf"\b{name}\s*:\s*([\d.]+)", src or study())
    assert m, f"검토서에 {name} 이 없다"
    return float(m.group(1))


class TestTheStudyIsAStandaloneDocument(unittest.TestCase):
    def test_is_standalone_document(self):
        standalone_document_checks(self, study(), TITLE)

    def test_it_says_it_is_not_an_order_document(self):
        """검토서를 발주 문서로 오해하면 이 치수로 제작이 들어간다."""
        s = study()
        self.assertIn("CONCEPT", s)
        self.assertIn("발주 문서가 아니다", s)


class TestTheCellCeilingIsReal(unittest.TestCase):
    """셀 하나에 천장이 있다는 것이 이 검토의 출발점이다."""

    def test_the_ceiling_is_the_peel_stroke_alone(self):
        peel = DEFAULTS["panelLength"] / DEFAULTS["knifeSpeed"]
        ceiling = 3600 / peel
        self.assertAlmostEqual(ceiling, 82.5, delta=.1)
        self.assertLess(3600 / thermal_model()["cycle_s"], ceiling,
                        "실제 사이클이 박리만 한 것보다 빠를 수는 없다")

    def test_the_study_derives_it_and_does_not_type_it(self):
        s = study()
        self.assertIn("3600/peelOnly", s.replace(" ", ""),
                      "셀 상한이 계산이 아니라 값으로 적혀 있다")


class TestTheChamberSizingIsBounded(unittest.TestCase):
    """단수와 램프 수는 세 부등식의 교집합이다 — 취향이 아니다."""

    @classmethod
    def setUpClass(cls):
        cls.s = study()
        cls.takt = const("cellCycle", cls.s) / CELLS
        cls.q = const("q", cls.s)

    def _sigma(self, lamps, decks):
        useful = lamps * const("lampKW", self.s) * const("eta", self.s)
        share = 8.0 * 0.75 / AREAL_CP_KJ_M2K
        area = DEFAULTS["panelLength"] * DEFAULTS["panelWidth"] / 1e6
        flux = useful / decks * share / area
        dt = flux * 1000 * 3.2e-3 / 1.0
        return 73e9 * 9e-6 * dt / (2 * (1 - 0.23)) / 1e6

    def test_the_reference_cycle_matches_the_console(self):
        """셀 하나의 사이클은 콘솔이 정한다 — 검토서가 새로 정하지 않는다.

        콘솔의 이동 나이프 사이클은 선행 + 박리 + max(교환창, 복귀) 다.
        검토서는 그 값을 그대로 받아 쓴다.
        """
        m = thermal_model()
        lead = 300 / DEFAULTS["knifeSpeed"]
        peel = DEFAULTS["panelLength"] / DEFAULTS["knifeSpeed"]
        handling = 300 / DEFAULTS["rapidSpeed"] + DEFAULTS["handlingTime"]
        ret = (300 + DEFAULTS["panelLength"]) / 700
        knife_cycle = lead + peel + max(handling, ret)
        self.assertAlmostEqual(const("cellCycle", self.s), knife_cycle, delta=.01)
        self.assertGreater(knife_cycle, m["cycle_s"] - 1,
                           "이동 나이프가 이동 캐리어보다 빠를 수는 없다")

    def test_the_heat_balance_sets_a_floor_on_power(self):
        useful_needed = self.q * 1000 / self.takt
        installed = useful_needed / const("eta", self.s)
        self.assertGreater(installed, 160, "필요 설치전력이 비현실적으로 낮다")
        self.assertLess(installed, 175, "필요 설치전력이 비현실적으로 높다")

    def test_the_fdm_limit_sets_a_floor_on_decks(self):
        self.assertGreaterEqual(math.ceil(FDM_DWELL_S / self.takt), 5,
                                "FDM 하한이 단수를 전혀 묶지 않는다")

    def test_the_chosen_candidate_passes_all_three(self):
        """7단 · 80등 — 통과하고, 여유가 DG-HK60C 와 같아야 한다."""
        lamps, decks = 80, 7
        pitch = self.q * 1000 / (lamps * const("lampKW", self.s) * const("eta", self.s))
        margin = (3600 / pitch - 3600 / self.takt) / (3600 / pitch) * 100
        self.assertLessEqual(pitch, self.takt, "피치가 택트를 넘는다")
        self.assertGreaterEqual(decks * pitch, FDM_DWELL_S, "체류가 FDM 하한에 못 미친다")
        self.assertLessEqual(self._sigma(lamps, decks), GLASS_ALLOW_MPA, "유리 열응력 초과")
        self.assertAlmostEqual(margin, REF_MARGIN, delta=.2,
                               msg="채택안의 열공정 여유가 DG-HK60C 와 다르다")

    def test_one_more_lamp_bank_would_break_the_glass(self):
        """왜 더 못 키우는지 — 유리가 먼저 걸린다는 것이 이 설계의 하한이다."""
        self.assertGreater(self._sigma(84, 6), GLASS_ALLOW_MPA,
                           "6단 84등에서도 유리가 견디면 단수 선택 근거가 다른 데 있다")

    def test_the_selection_rule_is_written_down(self):
        """규칙 없이 고른 값은 다음 사람이 다시 고른다."""
        for token in ("per===10", "Math.abs(a.margin-REF_MARGIN)"):
            self.assertIn(token, self.s.replace(" ", ""),
                          f"채택 규칙이 코드에 없다: {token}")

    def test_the_reference_margin_comes_from_the_delivered_line(self):
        """기준 여유를 새로 고르면 '같은 열설계를 키운다' 는 전제가 깨진다."""
        self.assertIn("constREF_MARGIN=M.hk60.margin;", self.s.replace(" ", ""),
                      "채택 기준 여유가 DG-HK60C 에서 파생되지 않는다")
        # CSS 의 margin:0 이 아니라 hk60 블록의 값을 본다
        m = re.search(r"hk60:\{[^}]*margin:([\d.]+)", self.s)
        self.assertIsNotNone(m, "검토서에 DG-HK60C 여유가 없다")
        self.assertAlmostEqual(float(m.group(1)), REF_MARGIN, delta=.05,
                               msg="검토서가 적은 DG-HK60C 여유가 실제와 다르다")


class TestRedundancyIsTheOtherHalf(unittest.TestCase):
    """처리량 2배보다 '한 셀이 서도 계약값' 이 팔기 쉬울 수 있다."""

    def test_one_cell_still_meets_the_contract(self):
        cell = const("cellCycle")
        degraded = 3600 / cell * const("availability")
        self.assertGreaterEqual(degraded, 60.0,
                                f"1셀 정지 시 {degraded:.1f} 장/h — 계약값에 못 미친다")

    def test_the_study_names_the_single_point(self):
        """이중화라고 적어 놓고 단일점을 숨기면 그것은 광고다."""
        s = study()
        self.assertIn("가열실은 이중화되지 않는다", s)


class TestTheLayoutKeepsWhatWasEarned(unittest.TestCase):
    """압축 배치가 번 성질을 이 구성이 도로 까먹지 않는지."""

    def test_the_length_does_not_change(self):
        s = study()
        self.assertIn("len:M.hk60.length", s.replace(" ", ""),
                      "전장이 DG-HK60C 에서 파생되지 않는다")

    def test_the_aisle_takes_the_cassette(self):
        """A안이 찾아낸 인출 포락선을 두 셀 구성이 다시 잃으면 안 된다."""
        aisle = const("aisle")
        cass = console_consts.const("KNIFE_W")
        self.assertGreaterEqual(aisle + 1e-9, cass,
                                f"중앙 통로 {aisle:.2f} m 가 카세트 {cass:.2f} m 를 못 받는다")

    def test_the_fence_is_stepped_not_rectangular(self):
        """직사각형으로 그리면 점유면적을 과장한다."""
        s = study()
        self.assertIn("방책은 계단형이다", s)


class TestTheBrandMarkIsTheOneDefinition(unittest.TestCase):
    def test_the_study_copy_matches_the_console(self):
        """마크 사본이 셋이 됐다 — 눈으로 옮겨 그리면 다른 도형이 된다."""
        import json
        mark = json.loads((ROOT / "docs" / "brand" / "dg-mark.json").read_text(encoding="utf-8"))
        s = study()
        for pth in mark["paths"]:
            self.assertIn(pth["d"], s, "마크 경로가 정의와 다르다")
            self.assertIn(pth["fill"], s)
