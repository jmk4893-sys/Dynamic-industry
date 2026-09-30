# -*- coding: utf-8 -*-
"""결정 등록부 — 회의 자료가 모델을 따라오는가.

이 장은 손으로 써서 아티팩트로만 발행했던 것이다. 그래서 값이 바뀌어도
문장이 안 따라왔고, OI-05 의 결론이 바뀌자 **아무도 모르는 채로 낡았다.**
생성기를 붙인 이유가 그것이므로, 시험도 그 한 가지를 지킨다:

  · **커밋된 파일이 생성기 출력과 같은가** — 손으로 고치면 걸린다.
  · **숫자가 모듈에서 오는가** — 모듈 값을 흔들면 장도 따라 움직여야 한다.
    안 움직이면 어딘가 리터럴이 남은 것이다.
  · **다섯 항목과 결합 관계가 다 실렸는가.**
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import catch, jaw, kinematics, motion, portal, ring, telescope

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs/drawings/pv-infeed-decisions.html"


def _builder():
    """`tools/` 는 패키지가 아니라 경로로 읽는다 — 다른 도면 시험과 같은 방식."""
    spec = importlib.util.spec_from_file_location(
        "build_decisions", ROOT / "tools" / "build_decisions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTheCommittedPage(unittest.TestCase):
    HTML = PAGE.read_text(encoding="utf-8")

    def test_it_is_what_the_builder_makes(self):
        self.assertEqual(
            self.HTML, _builder().build(),
            "docs/drawings/pv-infeed-decisions.html 이 생성기 출력과 다르다 — "
            "PYTHONPATH=src python tools/build_decisions.py 를 돌리고 커밋한다")

    def test_building_twice_changes_nothing(self):
        mod = _builder()
        self.assertEqual(mod.build(), mod.build(), "생성이 멱등이 아니다")

    def test_it_carries_all_five_records(self):
        for tag in ("OI-02", "OI-03", "OI-04", "OI-05", "OI-07"):
            with self.subTest(tag):
                self.assertIn(f'<span class="oi">{tag}</span>', self.HTML)

    def test_it_names_the_one_that_only_measurement_closes(self):
        self.assertIn("OI-08", self.HTML)

    def test_both_themes_are_defined(self):
        """토글과 시스템 설정 양쪽에서 색이 잡히는가."""
        self.assertIn('@media (prefers-color-scheme:dark)', self.HTML)
        self.assertIn(':root[data-theme="dark"]', self.HTML)
        self.assertIn("--ground:#EFF2F1", self.HTML)     # 밝은 쪽이 :root 에 있다


class TestTheNumbersComeFromTheModules(unittest.TestCase):
    """모듈 값을 흔들면 장이 따라 움직이는가 — 리터럴이 남았으면 여기서 걸린다."""

    def _rebuilt(self) -> str:
        return _builder().build()

    def test_the_catch_beam_rows_move_the_page(self):
        keep = kinematics.CATCH_BEAM_ROWS_MM
        try:
            before = self._rebuilt()
            kinematics.CATCH_BEAM_ROWS_MM = (-690, -640, 640, 690)
            motion.clear_caches()
            after = self._rebuilt()
        finally:
            kinematics.CATCH_BEAM_ROWS_MM = keep
            motion.clear_caches()
        self.assertNotEqual(before, after, "행을 옮겼는데 등록부가 그대로다")
        self.assertEqual(before, self._rebuilt(), "되돌렸는데 안 돌아왔다")

    def test_clearing_the_caches_is_what_makes_the_shake_honest(self):
        """캐시를 안 비우면 「값을 흔들어도 안 움직인다」로 잘못 통과한다."""
        keep = kinematics.CATCH_BEAM_ROWS_MM
        try:
            motion.clear_caches()
            first = motion.summary()["ledgeMm"]     # 캐시를 데운다
            kinematics.CATCH_BEAM_ROWS_MM = (-690, -640, 640, 690)
            stale = motion.summary()["ledgeMm"]     # 안 비우면 옛 답이 나온다
            motion.clear_caches()
            fresh = motion.summary()["ledgeMm"]
        finally:
            kinematics.CATCH_BEAM_ROWS_MM = keep
            motion.clear_caches()
        self.assertEqual(stale, first, "캐시가 안 걸려 있다 — 이 시험의 전제가 깨졌다")
        self.assertNotEqual(fresh, stale, "비웠는데도 옛 답이다")

    def test_the_frame_bearing_assumption_changes_the_words_not_the_verdict(self):
        """가정 폭을 바꾸면 문장은 따라 바뀌지만 **결론은 안 바뀐다.**

        이것이 그 가정을 안고 갈 수 있는 이유다 — 폭을 넓혀도 잡는 본은 여전히
        둘이고 선반도 10 mm 다. 패널 바깥끝(∓700)이 자르기 때문이지 플랜지
        폭이 자르는 것이 아니다.
        """
        keep = motion.FRAME_BEARING_MM
        try:
            before = self._rebuilt()
            motion.clear_caches()
            baseline = motion.summary()
            motion.FRAME_BEARING_MM = 40.0
            motion.clear_caches()
            widened = motion.summary()
            after = self._rebuilt()
        finally:
            motion.FRAME_BEARING_MM = keep
            motion.clear_caches()
        self.assertNotEqual(before, after, "가정을 바꿨는데 문장이 그대로다")
        self.assertEqual(widened["bearingBeams"], baseline["bearingBeams"])
        self.assertEqual(widened["ledgeMm"], baseline["ledgeMm"])
        self.assertGreater(motion.best_ledge_mm(40.0), motion.best_ledge_mm())

    def test_the_headline_figures_are_the_summary_figures(self):
        html = PAGE.read_text(encoding="utf-8")
        m, c = motion.summary(), catch.summary()
        r, j = ring.summary(), jaw.summary()
        t, p = telescope.summary(), portal.summary()
        for want in (f"{m['builtPerBeamN']:,.0f} N",
                     f"{m['ledgeMm']:.0f} mm",
                     f"{m['bearingBeams']} 본만",
                     f"{c['windowS']:.3f} s",
                     f"{r['rollerN']:,.0f} N",
                     f"{j['clampN']:,.0f} N",
                     f"{t['stowDepthMm']:.0f} mm",
                     f"{p['eccentricityMm']:.0f} mm"):
            with self.subTest(want):
                self.assertIn(want, html)

    def test_the_graph_edges_carry_derived_values(self):
        html = PAGE.read_text(encoding="utf-8")
        r = ring.summary()
        self.assertIn(f"반각이 반력 {r['rollerN']:,.0f} N 을 정한다", html)
        self.assertIn(f"택트 여유 {r['takt']['nowScale']:.2f} → "
                      f"{r['takt']['newScale']:.2f}", html)


class TestItSaysWhatItCannotSee(unittest.TestCase):
    HTML = PAGE.read_text(encoding="utf-8")

    def test_the_invented_members_are_flagged(self):
        """제가 세운 부재와 잡은 값을 회의 자료가 감추지 않는가."""
        for phrase in ("여기서 고른 값이지",           # 받침보 단면
                       "모델 어디에도 없던 값이다",     # 롤러 반각
                       "여기서 잡은 값이다"):           # 부싱 등급·간격
            with self.subTest(phrase):
                self.assertIn(phrase, self.HTML)

    def test_the_frame_bearing_width_is_named_as_an_assumption(self):
        self.assertIn("프레임 하부 지지폭", self.HTML)
        self.assertIn("쓸어도 안쪽 두 본이 논다는 결론은 안 바뀐다", self.HTML)

    def test_it_says_where_the_numbers_come_from(self):
        self.assertIn("여기 값은 하나도 손으로 적지 않았다", self.HTML)
        self.assertIn("tests/test_pv_decisions.py", self.HTML)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
