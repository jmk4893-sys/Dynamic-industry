"""도면과 3D 콘솔이 코드 산출값과 어긋나지 않는지 검증.

두 HTML 은 성격이 다르다. 제작도면은 ``tools/mp50_drawings.py`` 가 기하 모듈에서
**생성**하므로 어긋날 수 없고, 대신 생성물이 단독 문서로 성립하는지와 시트가
빠지지 않았는지를 본다. 3D 콘솔은 손으로 쓴 파일이라 상수가 박혀 있으므로,
그 숫자 하나하나가 모듈과 같은지 확인한다 — 기하를 고치고 콘솔을 잊으면
여기서 깨진다.
"""

import html as _html
import pathlib
import re
import subprocess
import sys
import unittest

from . import _path  # noqa: F401

from mp50_separator import ASSEMBLIES, CONFLICTS, GEOMETRY as G, run_checks
from mp50_separator.components import dry_mass_kg
from mp50_separator.geometry import NOZZLES

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRAWINGS = ROOT / "docs" / "drawings" / "mp50-fabrication-drawings.html"
CONSOLE = ROOT / "docs" / "drawings" / "mp50-3d.html"


def contains(case, haystack, needle, label):
    """assertIn 은 실패 시 500 KB 문서를 통째로 덤프한다 — 메시지를 직접 만든다.

    문서에는 이스케이프된 형태로 들어가므로 (2" → 2&quot;) 양쪽 다 본다.
    """
    case.assertTrue(
        needle in haystack or _html.escape(needle, quote=True) in haystack,
        f"{label} 이(가) 문서에 없음 — 찾은 문자열: {needle!r}. "
        f"기하나 부품을 고쳤다면 python tools/mp50_drawings.py 로 다시 생성할 것.",
    )


def standalone_checks(case, html, title):
    """단독 HTML 문서로서 성립하는지 — 두 파일에 공통."""
    case.assertTrue(html.lstrip().lower().startswith("<!doctype html>"))
    for tag in ('<html lang="ko">', "<head>", "</head>", "<body>", "</body>", "</html>"):
        case.assertIn(tag, html, tag)
    case.assertIn('<meta charset="utf-8">', html)      # 한글 도면 — 빠지면 깨진다
    case.assertIn('name="viewport"', html)
    case.assertIn("<title>" + title + "</title>", html)
    for url in re.findall(r'https?://[^"\')\s]+', html):
        case.assertTrue(
            url.startswith("https://fonts.googleapis.com")
            or url.startswith("https://fonts.gstatic.com")
            or url.startswith("http://www.w3.org/"),   # XML 네임스페이스는 식별자다
            f"CSP 상 차단되는 외부 리소스: {url}",
        )
    case.assertIn("@media (prefers-color-scheme: dark)", html)
    case.assertIn(':root:not([data-theme="light"])', html)
    case.assertIn(':root[data-theme="dark"]', html)


class TestDrawingDocument(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = DRAWINGS.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        standalone_checks(self, self.html, "MP-50 아세이별 제작도면")

    def test_fifteen_sheets(self):
        numbers = ["MP50-000", "MP50-100", "MP50-A1", "MP50-A2", "MP50-A3"]
        numbers += [a.drawing for a in ASSEMBLIES if a.code not in ("A",)]
        for no in numbers:
            contains(self, self.html, no, f"도면번호 {no}")
        self.assertEqual(len(re.findall(r"<svg ", self.html)), 15)

    def test_every_sheet_is_labelled_for_screen_readers(self):
        self.assertEqual(len(re.findall(r'role="img"', self.html)), 15)
        self.assertEqual(len(re.findall(r"aria-label=", self.html)), 15)
        self.assertEqual(len(re.findall(r"<figcaption>", self.html)), 15)

    def test_container_tags_balance(self):
        for tag in ("svg", "figure", "section", "table", "defs", "div", "style", "ul", "tbody"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_conflict_register_is_reproduced_in_full(self):
        for c in CONFLICTS:
            contains(self, self.html, c.ref, f"충돌 {c.ref}")
            contains(self, self.html, c.resolution, f"{c.ref} 채택값")
            contains(self, self.html, c.rationale[:40], f"{c.ref} 근거")

    def test_check_results_are_reproduced(self):
        for c in run_checks():
            contains(self, self.html, c.ref, f"검증 {c.ref}")
            contains(self, self.html, c.value, f"{c.ref} 결과")

    def test_every_part_appears_with_its_spec(self):
        for a in ASSEMBLIES:
            for p in a.parts:
                contains(self, self.html, p.no, f"부품 {p.no}")
                contains(self, self.html, p.spec, f"{p.no} 규격")

    def test_key_dimensions(self):
        for text in (f"Ø{G.tank_id_mm:.0f}", f"{G.total_volume_l:.2f} L",
                     f"{G.operating_volume_l:.1f} L", f"{G.shell_development_length_mm:.2f}",
                     f"{G.cone_truncated_height_mm:.2f}", f"{dry_mass_kg():.0f} kg"):
            contains(self, self.html, text, f"치수 {text}")

    def test_all_nozzles_are_scheduled(self):
        for n in NOZZLES:
            contains(self, self.html, n.tag, f"노즐 {n.tag}")
            contains(self, self.html, n.service, f"{n.tag} 용도")


class TestDrawingsAreGenerated(unittest.TestCase):
    """도면은 손으로 고치는 파일이 아니다 — 다시 돌리면 같은 것이 나와야 한다."""

    def test_regenerating_is_a_no_op(self):
        before = DRAWINGS.read_text(encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "tools" / "mp50_drawings.py")],
                       check=True, capture_output=True)
        self.assertEqual(DRAWINGS.read_text(encoding="utf-8"), before,
                         "도면을 손으로 고쳤거나 생성기와 어긋났다 — "
                         "python tools/mp50_drawings.py 로 다시 만들 것")


class TestSpecIsGenerated(unittest.TestCase):
    """제작 기준 Markdown 도 손으로 고치는 파일이 아니다."""

    def test_spec_matches_the_model(self):
        from mp50_separator.__main__ import report

        spec = ROOT / "docs" / "mp50-fabrication-spec.md"
        self.assertTrue(spec.exists(), "docs/mp50-fabrication-spec.md 가 없다")
        self.assertEqual(
            spec.read_text(encoding="utf-8"), report(),
            "제작 기준이 코드와 어긋난다 — "
            "PYTHONPATH=src python -m mp50_separator -o docs/mp50-fabrication-spec.md")


class TestConsoleDocument(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        standalone_checks(self, self.html, "MP-50 3D 분해 · 컷어웨이 콘솔")

    def test_canvas_is_described(self):
        contains(self, self.html, '<canvas id="stage"', "3D 뷰포트")
        contains(self, self.html, 'role="img"', "뷰포트 role")
        m = re.search(r'aria-label="([^"]{80,})"', self.html)
        self.assertIsNotNone(m, "3D 뷰포트에 서술형 aria-label 이 필요하다")

    def test_has_a_fallback_without_webgl(self):
        contains(self, self.html, "fallback", "WebGL 대체 안내")
        contains(self, self.html, "WebGL", "WebGL 언급")

    def test_respects_reduced_motion(self):
        contains(self, self.html, "prefers-reduced-motion", "움직임 줄이기 대응")

    def test_controls_are_present(self):
        for ident in ("btnExplode", "btnCut", "btnRun", "rngExplode", "rngCut", "rngSalt",
                      "partList", "asmRow", "seqbar"):
            contains(self, self.html, f'id="{ident}"', f"조작 {ident}")


class TestConsoleConstantsMatchTheModel(unittest.TestCase):
    """콘솔에 박힌 상수가 기하 모듈과 같은가."""

    @classmethod
    def setUpClass(cls):
        cls.html = CONSOLE.read_text(encoding="utf-8")
        block = re.search(r"const G = \{(.*?)\n\};", cls.html, re.S)
        assert block, "콘솔의 const G 블록을 찾지 못했다"
        cls.g = {k: float(v) for k, v in re.findall(r"(\w+):\s*(-?[\d.]+)", block.group(1))}

    def assertConst(self, key, value, places=2):
        self.assertIn(key, self.g, key)
        self.assertAlmostEqual(self.g[key], value, places=places,
                               msg=f"콘솔의 {key} 가 기하 모듈과 다르다")

    def test_vessel(self):
        self.assertConst("tankId", G.tank_id_mm)
        self.assertConst("shellT", G.shell_thickness_mm)
        self.assertConst("shellH", G.shell_height_mm)
        self.assertConst("coneDeg", G.cone_included_deg)
        self.assertConst("coneOutId", G.cone_outlet_id_mm)
        self.assertConst("apexH", G.cone_apex_height_mm)
        self.assertConst("coneH", G.cone_truncated_height_mm)
        self.assertConst("coneOutZ", G.cone_outlet_z)
        self.assertConst("shellBotZ", G.shell_bottom_z)
        self.assertConst("shellTopZ", G.shell_top_z)
        self.assertConst("coverTopZ", G.cover_top_z)

    def test_internals(self):
        self.assertConst("impOd", G.impeller_od_mm)
        self.assertConst("impLoZ", G.lower_impeller_z)
        self.assertConst("impHiZ", G.upper_impeller_z)
        self.assertConst("bafW", G.baffle_width_mm)
        self.assertConst("bafN", G.baffle_count)
        self.assertConst("bafZ0", G.baffle_bottom_z)
        self.assertConst("bafZ1", G.baffle_top_z)
        self.assertConst("bafGap", G.baffle_wall_gap_mm)
        self.assertConst("spPcd", G.sparger_pcd_mm)
        self.assertConst("spZ", G.sparger_z)
        self.assertConst("spHoles", G.sparger_holes)
        self.assertConst("skimOd", G.skimmer_od_mm)
        self.assertConst("skimZ", G.skimmer_z)
        self.assertConst("shaftOd", G.shaft_od_mm)

    def test_frame_and_levels(self):
        self.assertConst("frameW", G.frame_width_mm)
        self.assertConst("frameH", G.frame_height_mm)
        self.assertConst("ringOd", G.support_ring_od_mm)
        self.assertConst("ringZ", G.support_ring_z)
        self.assertConst("levelZ", G.operating_level_z)
        self.assertConst("floorOffset", G.floor_offset_mm)
        self.assertConst("volL", G.operating_volume_l, places=1)
        self.assertConst("totalL", G.total_volume_l, places=1)
        self.assertConst("minLevelZ", G.nominal_level_z, places=1)

    def test_nozzle_table_matches(self):
        rows = re.findall(r'\{ tag:"(\w+)",\s*th:(-?[\d.]+),\s*z:(-?[\d.]+),\s*od:([\d.]+)',
                          self.html)
        self.assertEqual(len(rows), len(NOZZLES))
        by_tag = {n.tag: n for n in NOZZLES}
        for tag, th, z, od in rows:
            n = by_tag[tag]
            self.assertAlmostEqual(float(th), n.theta_deg, places=3, msg=tag)
            self.assertAlmostEqual(float(z), n.z_mm, places=3, msg=tag)
            self.assertAlmostEqual(float(od), n.tube_od_mm, places=3, msg=tag)

    def test_particle_physics_constants_match(self):
        from mp50_separator.checks import BACKSHEET_DENSITY, EVA_DENSITY, SILICON_DENSITY

        contains(self, self.html, f"const SI_RHO = {SILICON_DENSITY:.0f};", "실리콘 밀도")
        contains(self, self.html,
                 "const EVA_RHO = [" + ", ".join(f"{v:.0f}" for v in EVA_DENSITY) + "];",
                 "EVA 유효밀도")
        contains(self, self.html,
                 "const BS_RHO  = [" + ", ".join(f"{v:.0f}" for v in BACKSHEET_DENSITY) + "];",
                 "백시트 유효밀도")

    def test_brine_correlation_matches(self):
        """콘솔의 Stokes·염수 식이 checks.py 와 같은 계수를 쓴다."""
        contains(self, self.html, "998 + 7.15*w + 0.026*w*w", "염수 밀도식")
        contains(self, self.html, "1.002e-3 * (1 + 0.0123*w + 0.00126*w*w)", "염수 점도식")
        contains(self, self.html, "18 * brineViscosity(saltWt)", "Stokes 식")


if __name__ == "__main__":
    unittest.main()
