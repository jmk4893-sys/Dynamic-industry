"""MP-50 EVA·백시트 분리기 3D 조립 분해도(docs/drawings/mp-50-3d.html) 검증.

이 도면은 제작도 MP-50-P0-001 Rev P0 를 3D 로 옮긴 단일 HTML 파일이다.
빌드 없이 브라우저로 열고 아티팩트로도 배포하므로, 문서 구조·외부자원·DOM 참조
무결성을 여기서 잡는다.

수치는 따로 계산 모듈을 두지 않고 **제작도의 공칭 치수에서 직접 산출**한다.
도면 치수(Ø400 / t3 / 600 / 150 …)를 고치고 본문 수치를 갱신하지 않으면
여기서 실패한다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

from .test_drawings import standalone_document_checks

MODEL = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs" / "drawings" / "mp-50-3d.html"
)
TITLE = "MP-50 EVA·백시트 분리기 조립 분해도"

# ── 제작도 MP-50-P0-001 의 공칭 치수 (mm) ────────────────────────────────
SHELL_OD = 400.0          # B. 탱크 본체 — Ø400
SHELL_T = 3.0             # B. t3
SHELL_H = 600.0           # B. 직동부 600
CONE_H = 150.0            # B·I. 콘 높이 150
CONE_OUT = 38.0           # B. 콘 출구 Ø38
IMPELLER_D = 300.0        # F. 임펠러 Ø300
RING_D = 250.0            # H. 분산기 Ø250
HOLE_D = 2.0              # H. 분사홀 Ø2
HOLE_N = 60               # H. 분사홀 60개
WORKING_L = 50.0          # 명판 — 50 L PILOT

SHELL_ID = SHELL_OD - 2 * SHELL_T

# 하부 배출구 스택 (J) — 플랜지 t8 + 40A 볼밸브 120 + 캠락·플러그 80
DISCHARGE_STACK = 8.0 + 120.0 + 80.0

# 부품표 34 품목 (A. 주요 구성품 번호)
PART_NAMES = [
    "교반 모터", "감속기", "커플링", "상부 커버", "고정볼트 세트", "맨홀",
    "스키머", "탱크 쉘", "사이드 노즐", "사이트글라스", "교반축",
    "임펠러 (상/하)", "배플", "미세기포 분산기", "하부 콘", "하부 배출구",
    "지지 다리", "레벨센서", "압력계", "온도센서", "공기 공급계", "제어반",
    "배관", "밸브류", "클램프", "가스켓", "전선/케이블", "앵커볼트", "명판",
    "방진패드", "배선트레이", "접지단자", "배수호스", "기타 부품",
]

ID_REF = re.compile(r"""document\.getElementById\(\s*["']([A-Za-z][\w-]*)["']\s*\)""")
ID_DEF = re.compile(r"""\bid=["']([A-Za-z][\w-]*)["']""")
# P("01","교반 모터",1,"g2","motor",[…],[…], …) — 분해 벡터와 라벨 앵커
PART_CALL = re.compile(
    r'P\("(\d\d)","([^"]+)",(\d+),"(g\d)","([a-z]+)",(\[[^\]]*\]),(\[[^\]]*\])'
)


def cylinder_l(diameter_mm, height_mm):
    return math.pi / 4 * diameter_mm ** 2 * height_mm / 1e6


def cone_l(top_d, bottom_d, height_mm):
    return (
        math.pi * height_mm / 12
        * (top_d ** 2 + top_d * bottom_d + bottom_d ** 2) / 1e6
    )


class TestModelDocument(unittest.TestCase):
    """단독 HTML 문서로서 성립하는지 — 다른 도면 세 건과 같은 규약."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL.read_text(encoding="utf-8")

    def test_is_standalone_document(self):
        self.assertTrue(MODEL.exists())
        standalone_document_checks(self, self.html, TITLE)

    def test_no_external_3d_library(self):
        # WebGL 을 직접 쓴다 — 아티팩트 CSP 는 CDN 을 막으므로 라이브러리 반입 금지.
        for banned in ("three.min.js", "three.module", "babylon", "unpkg.com", "cdn."):
            self.assertNotIn(banned, self.html, banned)
        self.assertIn('getContext("webgl"', self.html)

    def test_has_webgl_fallback(self):
        self.assertIn('id="fallback"', self.html)
        self.assertIn("WebGL", self.html)

    def test_container_tags_balance(self):
        for tag in ("div", "section", "table", "style", "script", "header", "svg", "ol"):
            opened = len(re.findall(rf"<{tag}[ >]", self.html))
            closed = len(re.findall(rf"</{tag}>", self.html))
            self.assertEqual(opened, closed, f"<{tag}> 태그 불균형")

    def test_every_referenced_id_exists(self):
        # 오타 하나로 조작 버튼이 조용히 죽는 것을 막는다.
        defined = set(ID_DEF.findall(self.html))
        for name in sorted(set(ID_REF.findall(self.html))):
            self.assertIn(name, defined, f"getElementById('{name}') 대상이 없음")

    def test_controls_are_labelled(self):
        for probe in ('aria-label="보기 대상"', 'aria-label="분해 정도"',
                      'aria-label="컷어웨이 정도"', 'aria-pressed'):
            self.assertIn(probe, self.html, probe)

    def test_respects_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.html)


class TestPartList(unittest.TestCase):
    """부품표 34 품목이 모두 3D 부품으로 있는지."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL.read_text(encoding="utf-8")
        cls.calls = PART_CALL.findall(cls.html)

    def test_thirty_four_parts(self):
        self.assertEqual(len(self.calls), 34)
        self.assertEqual([c[0] for c in self.calls],
                         [f"{i:02d}" for i in range(1, 35)])

    def test_part_names_match_the_drawing(self):
        self.assertEqual([c[1] for c in self.calls], PART_NAMES)

    def test_every_part_declares_explode_vector_and_anchor(self):
        for no, name, _q, _g, _m, ex, anchor in self.calls:
            self.assertEqual(len(ex.split(",")), 3, f"{no} {name} 분해 벡터")
            self.assertEqual(len(anchor.split(",")), 3, f"{no} {name} 라벨 앵커")

    def test_quantities_match_the_drawing(self):
        qty = {c[0]: int(c[2]) for c in self.calls}
        # 도면 수량란이 1 이 아닌 품목
        self.assertEqual(qty["12"], 2, "임펠러 (상/하)")
        self.assertEqual(qty["13"], 4, "배플")
        self.assertEqual(qty["17"], 3, "지지 다리")
        self.assertEqual(qty["18"], 2, "레벨센서")
        self.assertEqual(qty["28"], 3, "앵커볼트")
        self.assertEqual(qty["30"], 3, "방진패드")

    def test_every_part_belongs_to_a_view_group(self):
        groups = {c[3] for c in self.calls}
        self.assertEqual(groups, {"g1", "g2", "g3", "g4"})
        for g in sorted(groups):
            self.assertIn(f'grp:"{g}"', self.html, f"{g} 보기 정의 누락")

    def test_agitator_parts_rotate_in_run_mode(self):
        # 교반축·임펠러는 운전 표시에서 돌아야 한다.
        for no in ("11", "12"):
            block = self.html.split(f'P("{no}",')[1].split('P("')[0]
            self.assertIn("rot:true", block, f"{no} 회전 플래그 누락")

    def test_vessel_envelope_is_ghosted_in_run_mode(self):
        # 동체가 불투명하면 운전 표시가 보이지 않는다 — 04·08·15 는 고스트 대상.
        for no in ("04", "08", "15"):
            block = self.html.split(f'P("{no}",')[1].split('P("')[0]
            self.assertIn("env:true", block, f"{no} 고스트 플래그 누락")


class TestFiguresMatchTheDrawing(unittest.TestCase):
    """본문 수치가 제작도 치수에서 산출한 값과 같은지."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL.read_text(encoding="utf-8")
        cls.v_cyl = cylinder_l(SHELL_ID, SHELL_H)
        cls.v_cone = cone_l(SHELL_ID, CONE_OUT, CONE_H)
        cls.v_total = cls.v_cyl + cls.v_cone

    def assertFigure(self, text, label):
        # assertIn 은 실패 시 문서 전체를 덤프하므로 메시지를 직접 만든다.
        self.assertTrue(
            text in self.html,
            f"{label} 이(가) 도면과 불일치 — '{text}' 가 없음. "
            f"제작도 치수를 고쳤다면 본문 수치도 갱신할 것.",
        )

    def test_nominal_dimensions_are_stated(self):
        self.assertFigure(f"Ø{SHELL_OD:.0f} × t{SHELL_T:.0f}", "동체 규격")
        self.assertFigure(f"직동부 {SHELL_H:.0f}", "직동부 높이")
        self.assertFigure(f"Ø{SHELL_OD:.0f} → Ø{CONE_OUT:.0f} · h{CONE_H:.0f}", "하부 콘")
        self.assertFigure(f"Ø{SHELL_ID:.0f}", "동체 내경")
        self.assertFigure(f"Ø{IMPELLER_D:.0f}", "임펠러 직경")
        self.assertFigure(f"Ø{RING_D:.0f}", "분산기 링 직경")
        self.assertFigure("MP-50-P0-001", "도면번호")

    def test_volumes(self):
        self.assertFigure(f"{self.v_cyl:.1f} L", "직동부 체적")
        self.assertFigure(f"{self.v_cone:.1f} L", "콘 체적")
        self.assertFigure(f"{self.v_total:.1f} L", "기하 체적")
        self.assertFigure(f"{WORKING_L:.0f} L", "정격 작업 체적")

    def test_working_level_and_fill_ratio(self):
        level = (WORKING_L - self.v_cone) / (cylinder_l(SHELL_ID, 1000.0) / 1000.0)
        self.assertFigure(f"{level:.0f} mm", "작업 액면")
        self.assertFigure(f"{SHELL_H - level:.0f} mm", "여유고")
        self.assertFigure(f"{WORKING_L / self.v_total * 100:.1f} %", "충수율")

    def test_sparger_figures(self):
        area = HOLE_N * math.pi / 4 * HOLE_D ** 2
        self.assertFigure(f"{area:.1f} mm²", "총 분사홀 면적")
        self.assertFigure(f"{math.pi * RING_D / HOLE_N:.1f} mm", "분사홀 피치")
        self.assertFigure(f"Ø{HOLE_D:.0f} × {HOLE_N}개", "분사홀 사양")
        speeds = " / ".join(
            f"{q / 3600 / (area / 1e6):.1f}" for q in (1.0, 3.0, 5.0)
        )
        self.assertFigure(f"{speeds} m/s", "분사홀 유속")

    def test_impeller_ratio_and_wall_gap(self):
        self.assertFigure(f"{IMPELLER_D / SHELL_ID:.2f}", "임펠러 직경비 D/T")
        self.assertFigure(f"{(SHELL_ID - IMPELLER_D) / 2:.0f} mm", "벽면 간극")
        self.assertFigure(f"T/10 = {SHELL_ID / 10:.1f} mm", "배플 통상 폭")
        # 모델은 통상값을 반올림한 40 mm 로 그린다 (도면 200 은 간섭).
        self.assertFigure("<strong>폭 40 mm</strong>", "모델 배플 폭")
        self.assertIn("box(m,0.040,0.400,0.002", self.html, "배플 형상이 폭 40 이 아님")

    def test_cone_angle_discrepancy_is_quantified(self):
        # 도면은 60° 라고 쓰는데 치수열은 다른 각을 준다 — 그 차이를 수치로 남긴다.
        drop = (SHELL_OD - CONE_OUT) / 2
        half = math.degrees(math.atan(drop / CONE_H))
        self.assertFigure(f"{half:.1f}°", "치수열 반각")
        self.assertFigure(f"내각 {2 * half:.1f}°", "치수열 내각")
        self.assertFigure(f"내각 60° 면 높이 {drop / math.tan(math.radians(30)):.0f}",
                          "내각 60° 환산 높이")
        self.assertFigure(f"반각 60° 면 높이 {drop / math.tan(math.radians(60)):.0f}",
                          "반각 60° 환산 높이")

    def test_discharge_stack_and_leg(self):
        self.assertFigure(f"= <strong>{DISCHARGE_STACK:.0f} mm</strong>", "배출구 스택 높이")
        self.assertFigure("<strong>420 mm</strong>", "모델 다리 길이")
        self.assertFigure("108 mm", "바닥 여유")

    def test_overall_height_is_distinguished_from_tank_height(self):
        self.assertFigure(f"{SHELL_H + CONE_H:.0f} = 직동부 {SHELL_H:.0f} + 콘 {CONE_H:.0f}",
                          "탱크 본체 높이 750 의 내역")
        self.assertFigure("1,885 mm", "조립 전고")

    def test_materials(self):
        for probe in ("SUS304 2B", "SUS316L", "Ra ≤0.8 µm", "Ra ≤0.4 µm",
                      "EPDM / SILICONE"):
            self.assertFigure(probe, "재질 표기")

    def test_fabrication_and_inspection_basis(self):
        for probe in ("0.2 MPa", "M8 20 N·m", "M10 40 N·m",
                      "220 V 1Ø 또는 380 V 3Ø"):
            self.assertFigure(probe, "제작·검사 기준")


class TestReviewFindings(unittest.TestCase):
    """P0 검토 지적이 도면에서 조용히 사라지지 않도록 고정한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = MODEL.read_text(encoding="utf-8")
        cls.review = cls.html.split('class="notes review"')[1]

    def test_seven_findings_are_recorded(self):
        self.assertEqual(len(re.findall(r"<li>", self.review)), 7)

    def test_each_finding_is_present(self):
        for probe in ("배플 폭 200 mm", "하부 콘 각도 60°", "지지 다리 200 mm",
                      "전고 750", "직경비 D/T", "스탠드가 도면에 없다",
                      "재질표가 두 개"):
            self.assertIn(probe, self.review, probe)

    def test_model_states_where_it_departs_from_the_drawing(self):
        # 도면과 다르게 그린 곳은 반드시 밝힌다.
        self.assertIn("제작용 CAD 가 아니며", self.html)
        self.assertIn("아래 지적 항목만 모델에서 달리 그렸다", self.html)


if __name__ == "__main__":
    unittest.main()
