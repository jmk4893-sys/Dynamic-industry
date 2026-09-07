"""제작 지침서가 계산기와 같은 값을 말하는가.

이 저장소가 계속 고쳐 온 실패는 하나다 — 같은 값을 두 곳에 적으면 한 곳만
고쳐진다. 도면과 3D 가 그랬고, 사양서와 콘솔이 그랬다. 제작 지침서는 그
위험이 가장 큰 문서다: 표에 적힌 볼트 규격과 토크가 현장에서 그대로
시공되고, 틀리면 되돌릴 수 없다.

그래서 지침서의 모든 표를 계산기(tools/fab_spec.py)와 대조한다. 표의 숫자를
손으로 고치면 여기서 먼저 실패한다.

두 번째로 보는 것은 계산 자체가 규격과 맞는가다. 계산기의 함수를 다시 부르는
것으로는 검증이 안 되므로(같은 오류를 두 번 낸다), EN 1993-1-8 의 식을
시험 안에서 독립적으로 다시 세워 대조한다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import fab_spec as F

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "dg-hk60-fab-spec.html"


def _cells(html, caption):
    """caption 을 가진 표의 tbody 행을 셀 문자열 리스트로 돌려준다."""
    m = re.search(r"<caption>" + re.escape(caption) + r".*?</table>", html, re.S)
    if m is None:
        raise AssertionError(f"'{caption}' 표를 찾지 못했다")
    body = re.search(r"<tbody>(.*?)</tbody>", m.group(0), re.S).group(1)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        rows.append(cells)
    return rows


class TestTheCalculatorClosesTheDesign(unittest.TestCase):
    """계산이 닫히지 않으면 지침서를 낼 수 없다."""

    def test_every_bolted_joint_keeps_the_fabrication_margin(self):
        """이용률 0.70 은 현장 여유다 — 구멍이 밀리고 토크가 덜 들어간다."""
        for j in F.JOINTS:
            self.assertLessEqual(j["util"], 0.70,
                                 f"{j['id']} 이용률 {j['util']:.2f} 가 여유를 먹었다")

    def test_every_alignment_and_fatigue_check_passes(self):
        for x in F.CRITICAL:
            self.assertLessEqual(x["util"], 1.0,
                                 f"{x['id']} {x['gov']} 이용률 {x['util']:.2f}")

    def test_the_slip_critical_joint_does_not_slip(self):
        """J3 이 미끄러지면 칼끝 간격 300±2 가 깨진다."""
        slip = [j for j in F.JOINTS if j["slip"]]
        self.assertTrue(slip, "마찰접합으로 잡은 접합이 하나도 없다")
        for j in slip:
            self.assertLessEqual(j["slip_util"], 1.0,
                                 f"{j['id']} 미끄러짐 이용률 {j['slip_util']:.2f}")

    def test_the_peel_thrust_is_the_bounding_case(self):
        """하한으로 잡으면 상한에서 무너진다 — 상한 × 동적 × γQ 여야 한다."""
        self.assertAlmostEqual(F.F_PEEL_K, 13.37 * F.PANEL_W / 1.2, places=3,
                               msg="포락 추력이 OI-01 상한(폭 1,200)을 포락선 폭으로 환산한 값이 아니다")
        self.assertAlmostEqual(F.F_PEEL_D, F.F_PEEL_K * 1.30 * 1.50, places=6)

    def test_the_loads_come_from_the_console_not_from_typed_numbers(self):
        """하중을 손으로 적으면 배치를 바꿨을 때 지침서만 옛 하중으로 남는다."""
        import console_consts
        c = console_consts.const
        self.assertAlmostEqual(
            F.W_PANEL, c("MASS_AREAL") * c("PANEL_L") * c("PANEL_W") * F.G / 1000, places=9)
        self.assertAlmostEqual(
            F.W_GLASS, c("MASS_GLASS") * c("PANEL_L") * c("PANEL_W") * F.G / 1000, places=9)
        turn = F.PANEL_L * F.c("BACKSHEET_T") / math.pi
        self.assertEqual(F.ROLL_PANELS, round((0.30 ** 2 - 0.15 ** 2) / turn),
                         "롤당 장수가 면적보존에서 나오지 않는다")
        src = (ROOT / "tools" / "fab_spec.py").read_text(encoding="utf-8")
        self.assertIn("import console_consts", src, "계산기가 콘솔 상수를 읽지 않는다")


class TestTheBoltMathMatchesTheStandard(unittest.TestCase):
    """계산기 함수를 다시 부르면 같은 오류를 두 번 낸다 — 식을 다시 세운다."""

    def test_tension_resistance_follows_en_1993_1_8(self):
        for size, b in F.BOLTS.items():
            for grade, g in F.GRADES.items():
                want = 0.9 * g["fub"] * b["As"] / 1.25 / 1000
                self.assertAlmostEqual(F.bolt_tension(size, grade), want, places=9)

    def test_shear_resistance_uses_the_threaded_shear_plane(self):
        """몸통 전단으로 잡으면 내력이 커지지만 현장에서 확인할 수 없다."""
        self.assertEqual(F.GRADES["8.8"]["av"], 0.6)
        self.assertEqual(F.GRADES["10.9"]["av"], 0.5)
        for size, b in F.BOLTS.items():
            for grade, g in F.GRADES.items():
                want = g["av"] * g["fub"] * b["As"] / 1.25 / 1000
                self.assertAlmostEqual(F.bolt_shear(size, grade), want, places=9)

    def test_preload_is_seventy_percent_of_ultimate(self):
        for size, b in F.BOLTS.items():
            for grade, g in F.GRADES.items():
                self.assertAlmostEqual(F.preload(size, grade),
                                       0.7 * g["fub"] * b["As"] / 1000, places=9)

    def test_torque_follows_from_preload_and_friction(self):
        """토크가 사양이 아니라 체결력이 사양이다 — T = K·d·Fp 로만 나와야 한다."""
        for size in F.BOLTS:
            d = int(size[1:]) / 1000
            for grade in F.GRADES:
                for K in (F.K_DRY, F.K_LUB):
                    self.assertAlmostEqual(
                        F.torque(size, grade, K),
                        K * d * F.preload(size, grade) * 1000, places=6)
        self.assertGreater(F.K_DRY, F.K_LUB, "건조가 윤활보다 토크가 커야 한다")

    def test_the_fatigue_limit_follows_the_knee(self):
        """Δσ_D = Δσ_C·(2/5)^(1/3) — 5×10⁶ 회에서의 무릎."""
        for cat in F.DETAIL_CATEGORY.values():
            self.assertAlmostEqual(F.fatigue_limit(cat),
                                   cat * (2 / 5) ** (1 / 3), places=9)

    def test_weld_leg_never_falls_below_the_plate_rule(self):
        """두꺼운 판에 얇은 각장을 놓으면 용융지가 빨리 식어 균열이 생긴다."""
        for t, z_min in ((6, 4), (12, 5), (19, 6), (25, 8), (40, 10)):
            z, why = F.fillet_leg(0.001, 10_000, "SS400", t_mm=t)
            self.assertEqual(z, z_min, f"t{t} 최소 각장이 {z_min} 이 아니다")
            self.assertIn("판두께", why)
        # 하중이 크면 강도가 이겨야 한다
        z, why = F.fillet_leg(2000.0, 100, "SS400", t_mm=6)
        self.assertGreater(z, 4)
        self.assertEqual(why, "강도")

    def test_anchor_capacity_is_governed_by_the_concrete(self):
        """앵커를 굵혀도 콘크리트가 안 따라오면 소용없다."""
        for a in F.ANCHORS:
            self.assertEqual(a["gov"], "콘크리트 콘",
                             f"{a['id']} 은 {a['gov']} 이 지배한다 — 표의 전제와 다르다")
            self.assertLess(a["cone"], a["steel"],
                            f"{a['id']} 콘 내력이 강재보다 크다")
            self.assertGreaterEqual(a["edge"], 1.5 * a["hef"])
            self.assertGreaterEqual(a["slab"], a["hef"] + 100)


class TestTheSpecificationSaysWhatTheCalculatorComputed(unittest.TestCase):
    """표의 숫자를 손으로 고치면 여기서 먼저 실패한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = SPEC.read_text(encoding="utf-8")

    def test_the_document_exists_and_names_its_calculator(self):
        self.assertIn("tools/fab_spec.py", self.html,
                      "지침서가 계산 근거를 대지 않는다")
        self.assertIn("DG-HK60C-FAB-001", self.html, "문서번호가 없다")

    def test_the_bolt_capacity_table_matches(self):
        rows = _cells(self.html, "볼트 내력·체결력·조임토크")
        seen = {}
        grade = None
        for r in rows:
            if len(r) == 1:                       # 등급 머리행
                grade = re.search(r"등급 (\S+)", r[0]).group(1)
                continue
            seen[(r[0], grade)] = r
        self.assertEqual(len(seen), len(F.BOLTS) * len(F.GRADES),
                         "볼트 내력표의 행 수가 규격×등급과 다르다")
        for (size, grade), r in seen.items():
            self.assertAlmostEqual(float(r[4]), F.bolt_tension(size, grade), delta=0.05,
                                   msg=f"{size} {grade} Ft,Rd")
            self.assertAlmostEqual(float(r[5]), F.bolt_shear(size, grade), delta=0.05,
                                   msg=f"{size} {grade} Fv,Rd")
            self.assertAlmostEqual(float(r[6]), F.preload(size, grade), delta=0.05,
                                   msg=f"{size} {grade} Fp,C")
            dry, lub = (float(v) for v in r[7].split("/"))
            self.assertAlmostEqual(dry, F.torque(size, grade, F.K_DRY), delta=1.0)
            self.assertAlmostEqual(lub, F.torque(size, grade, F.K_LUB), delta=1.0)

    def test_the_joint_table_matches(self):
        rows = [r for r in _cells(self.html, "접합부 12개소") if len(r) >= 10]
        self.assertEqual(len(rows), len(F.JOINTS), "접합부 수가 계산기와 다르다")
        by_id = {j["id"]: j for j in F.JOINTS}
        for r in rows:
            j = by_id[r[0]]
            self.assertEqual(r[2], f"{j['size']} × {j['n']}", f"{j['id']} 볼트 규격·수량")
            self.assertEqual(r[3], j["grade"], f"{j['id']} 등급")
            self.assertAlmostEqual(float(r[5]), j["N"], delta=0.01, msg=f"{j['id']} N,Ed")
            self.assertAlmostEqual(float(r[6]), j["V"], delta=0.01, msg=f"{j['id']} V,Ed")
            self.assertAlmostEqual(float(r[7]), j["util"], delta=0.01, msg=f"{j['id']} 이용률")
            self.assertAlmostEqual(float(r[8]), j["Fp"], delta=0.05, msg=f"{j['id']} Fp,C")
            dry, lub = (float(v) for v in r[9].split("/"))
            self.assertAlmostEqual(dry, j["T_dry"], delta=1.0, msg=f"{j['id']} 건조 토크")
            self.assertAlmostEqual(lub, j["T_lub"], delta=1.0, msg=f"{j['id']} 윤활 토크")

    def test_the_weld_table_matches(self):
        rows = _cells(self.html, "주요 용접 접합")
        self.assertEqual(len(rows), len(F.WELDS), "용접 접합 수가 다르다")
        for r, (name, force, length, mat, t) in zip(rows, F.WELDS):
            self.assertEqual(r[0], name)
            self.assertAlmostEqual(float(r[1]), force, delta=0.05, msg=name)
            z, why = F.fillet_leg(force, length, mat if mat in F.MATERIALS else "SS400", t_mm=t)
            self.assertEqual(r[5], f"z{z:.0f}", f"{name} 각장")
            self.assertEqual(r[6], why, f"{name} 각장 근거")

    def test_the_member_table_matches(self):
        rows = [r for r in _cells(self.html, "모듈별 부재") if len(r) == 4]
        self.assertEqual(len(rows), len(F.MEMBERS), "부재 수가 다르다")
        for r, (mod, part, sec, mat, gov) in zip(rows, F.MEMBERS):
            self.assertEqual(r[0], part)
            self.assertEqual(r[1], sec, f"{part} 단면·두께")
            self.assertEqual(r[2], mat, f"{part} 재질")
            self.assertEqual(r[3], gov, f"{part} 지배 검토")

    def test_the_anchor_table_matches(self):
        rows = _cells(self.html, "접착식 앵커")
        self.assertEqual(len(rows), len(F.ANCHORS))
        for r, a in zip(rows, F.ANCHORS):
            self.assertEqual(r[0], a["id"])
            self.assertEqual(r[2], f"{a['size']} × {a['n']}", f"{a['id']} 앵커 규격")
            self.assertAlmostEqual(float(r[3]), a["hef"], delta=0.5)
            self.assertAlmostEqual(float(r[5]), a["cone"], delta=0.05, msg=f"{a['id']} 콘")
            self.assertEqual(r[7], a["gov"], f"{a['id']} 지배")
            self.assertAlmostEqual(float(r[8]), a["edge"], delta=0.5, msg=f"{a['id']} 연단")
            self.assertAlmostEqual(float(r[10]), a["slab"], delta=0.5, msg=f"{a['id']} 기초두께")

    def test_the_critical_check_table_matches(self):
        rows = [r for r in _cells(self.html, "정렬·피로 지배 부재") if len(r) == 6]
        self.assertEqual(len(rows), len(F.CRITICAL))
        for r, x in zip(rows, F.CRITICAL):
            self.assertEqual(r[0], x["id"])
            self.assertAlmostEqual(float(r[3].split()[0]), x["value"], delta=0.01,
                                   msg=f"{x['id']} 값")
            self.assertAlmostEqual(float(r[4].split()[0]), x["limit"], delta=0.01,
                                   msg=f"{x['id']} 한계")
            self.assertAlmostEqual(float(r[5]), x["util"], delta=0.01, msg=f"{x['id']} 이용률")

    def test_the_material_table_matches(self):
        rows = _cells(self.html, "재료 규격과 사용처")
        self.assertEqual(len(rows), len(F.MATERIALS))
        for r, (name, v) in zip(rows, F.MATERIALS.items()):
            self.assertEqual(r[0], name)
            self.assertEqual(r[1], v["std"], f"{name} 규격")
            self.assertEqual(r[5], v["use"], f"{name} 사용처")


class TestTheSpecificationCarriesTheDecisions(unittest.TestCase):
    """총괄이 내린 판단이 문서에 남아 있어야 다음 사람이 되돌리지 않는다."""

    @classmethod
    def setUpClass(cls):
        cls.html = SPEC.read_text(encoding="utf-8")

    def test_it_resolves_the_contradiction_between_two_drawings(self):
        """F-005 와 D-602 가 추력의 행선지를 다르게 적고 있었다."""
        self.assertIn("작용·반작용", self.html, "추력이 쌍이라는 판정이 없다")
        self.assertIn("한쪽만 설계하면 반대쪽이 뜬다", self.html)
        # 그리고 두 접합이 실제로 같은 설계 추력을 받아야 한다
        j1 = next(j for j in F.JOINTS if j["id"] == "J1")
        j2 = next(j for j in F.JOINTS if j["id"] == "J2")
        self.assertAlmostEqual(j1["V"] * 4, j2["V"] * 4, places=9,
                               msg="테이블과 갠트리가 다른 추력을 받고 있다")

    def test_it_says_the_cassette_clamp_is_not_a_shear_member(self):
        """클램프를 전단재로 세면 설계추력 대비 1.15 밖에 안 된다."""
        self.assertIn("쐐기 클램프는 전단재가 아니다", self.html)
        self.assertIn("테이퍼 로케이팅핀", self.html)
        j5 = next(j for j in F.JOINTS if j["id"] == "J5")
        self.assertTrue(j5["pin"], "J5 가 핀 전단으로 모델되지 않았다")

    def test_it_bans_spring_washers_and_paint_on_faying_surfaces(self):
        """둘 다 설계를 조용히 무효로 만드는 시공이다."""
        self.assertIn("스프링와셔를 쓰지 않는다", self.html)
        self.assertIn("마찰접합면에 도장하면 설계가 무효", self.html)

    def test_the_masses_come_from_the_part_catalogue(self):
        """자중을 형상 없이 적으면 앵커가 그 오차만큼 틀어진다.

        초판은 넷을 개산으로 적었다. 카탈로그를 세워 대조하니 권취 문형이
        +48 % 빗나가 있었다 — 그래서 이제 설계는 카탈로그가 계산한 값을
        쓴다. 이 시험이 지키는 것은 그 연결이다: 계산기가 카탈로그에서
        자중을 가져오고, 문서의 하중표가 그 값을 그대로 적어야 한다.

        누가 다시 상수로 되돌려 적으면 (예: M_WINDER = 620) 여기서 걸린다.
        """
        import parts

        for sym in ("M_CHAMBER", "M_GANTRY", "M_TABLE", "M_WINDER"):
            self.assertAlmostEqual(
                getattr(F, sym), parts.mass(sym), delta=0.5,
                msg=f"{sym} 가 부품 카탈로그의 계산값이 아니다 — 상수로 되돌아갔다")

        load = self.html[self.html.index("설계하중 — 특성값과 설계값"):
                         self.html.index("피로 하중 반복수")]
        for sym, th in (("M_CHAMBER", "HC-101 가열실 자중"), ("M_GANTRY", "KG-101 갠트리 자중"),
                        ("M_TABLE", "VT-101 테이블 자중"), ("M_WINDER", "WR-101 권취부 자중")):
            m = getattr(F, sym)
            self.assertIn(th, load, f"하중표에 {th} 행이 없다")
            self.assertIn(f"{F.kn(m):.1f} kN", load, f"{th} 특성값이 계산과 다르다")
            self.assertIn(f"{m / 1000:.2f} t", load, f"{th} 질량이 계산과 다르다")

        # 카탈로그가 개념설계 유도값이라는 것과, 재검토 조건이 남아 있어야 한다
        load_n = load.replace("±15 %", "± 15 %")
        for m in ("부품 카탈로그", "중량표", "± 15 %", "매입깊이가 규격보다 먼저 움직인다"):
            self.assertIn(m, load_n, f"하중표 옆에 '{m}' 가 없다")
        submit = self.html[self.html.index("착수 전 제출"):][:2000]
        self.assertIn("중량표", submit, "제출 목록에 중량표가 없다")

    def test_the_recomputed_masses_did_not_change_any_size(self):
        """자중이 +48 % 늘었는데 규격이 그대로인 것은 결론이지 우연이 아니다.

        문서가 그렇게 적었으므로 계산이 실제로 그런지 확인한다 — 이 설비의
        접합은 강성·피로·최소규격이 지배하므로 이용률이 여전히 낮아야 한다.
        어느 접합이든 0.70 을 넘으면 그 문장이 거짓이 되고, 규격을 다시
        잡아야 한다.
        """
        self.assertIn("규격이 바뀐 접합·앵커는 없다", self.html,
                      "자중을 다시 계산하고도 그 결과를 문서가 말하지 않는다")
        worst = max(F.JOINTS, key=lambda j: j["util"])
        self.assertLess(worst["util"], 0.70,
                        f"{worst['id']} 이용률 {worst['util']:.2f} — 규격을 다시 잡아야 한다")
        for a in F.ANCHORS:
            self.assertEqual(a["gov"], "콘크리트 콘",
                             f"{a['id']} 지배 파괴가 바뀌었다 — 매입깊이를 다시 본다")

    def test_it_explains_why_utilisation_is_low(self):
        """0.05 를 그대로 두면 '왜 M20 인가' 에 답하지 못한다."""
        self.assertIn("강도가 아니라", self.html)
        self.assertIn("최소 규격", self.html)

    def test_it_names_the_stiffness_number_that_sets_the_crossbeam(self):
        c1 = next(x for x in F.CRITICAL if x["id"] == "C1")
        self.assertIn("300 ± 2 mm", self.html, "칼끝 간격 공차가 문서에 없다")
        self.assertAlmostEqual(c1["limit"], 0.50, places=9,
                               msg="처짐 한계가 공차의 1/4 이 아니다")

    def test_it_gives_the_assembly_order_and_says_why(self):
        self.assertIn("주행레일 문형(4)을 테이블(5)보다 먼저 세운다", self.html)
        self.assertIn("인발시험", self.html, "앵커 시공 시험이 없다")
        self.assertIn("마킹", self.html, "체결 마킹 규칙이 없다")

    def test_it_keeps_the_standards_list_a_closed_set(self):
        for std in ("EN 1993-1-8", "EN 1993-1-9", "EN 1992-4", "ISO 898-1",
                    "ISO 2553", "ISO 5817", "ISO 2768-mK", "ISO 286-2",
                    "ISO 12944-5", "ISO 8501-1"):
            self.assertIn(std, self.html, f"{std} 가 적용 규격에 없다")


class TestTheShopDetailSheetAgreesWithTheSpecification(unittest.TestCase):
    """F-901 은 지침서의 표를 현장에서 보는 그림이다.

    사무실에서 읽는 문서와 현장에 붙는 도면에 같은 토크가 적힌다. 둘이
    갈라지면 현장이 먼저 알고, 그때는 이미 조여진 뒤다.
    """

    @classmethod
    def setUpClass(cls):
        cls.console = (ROOT / "docs" / "drawings" / "pv-delamination-3d.html").read_text(
            encoding="utf-8")

    def test_the_sheet_is_reachable(self):
        self.assertIn('data-drawing="bolt"', self.console, "탭이 없다")
        self.assertIn("drawingTab==='bolt')drawingContent.innerHTML=boltDetailDrawing()",
                      self.console, "탭이 시트를 그리지 않는다")
        self.assertIn("no:'F-901'", self.console, "도면번호가 없다")

    def test_the_torque_table_matches_the_calculator(self):
        m = re.search(r"const FAB_TORQUE=\[(.*?)\];", self.console, re.S)
        self.assertIsNotNone(m, "F-901 의 토크표를 찾지 못했다")
        rows = re.findall(r"\['(M\d+)','([\d.]+)',([\d.]+),(\d+),(\d+)\]", m.group(1))
        self.assertTrue(rows, "토크표가 비어 있다")
        for size, grade, fp, dry, lub in rows:
            self.assertAlmostEqual(float(fp), F.preload(size, grade), delta=0.05,
                                   msg=f"{size} {grade} Fp,C")
            self.assertAlmostEqual(float(dry), F.torque(size, grade, F.K_DRY), delta=1.0,
                                   msg=f"{size} {grade} 건조 토크")
            self.assertAlmostEqual(float(lub), F.torque(size, grade, F.K_LUB), delta=1.0,
                                   msg=f"{size} {grade} 윤활 토크")

    def test_the_sheet_carries_the_anchor_and_faying_rules(self):
        body = self.console[self.console.index("function boltDetailDrawing("):]
        body = body[:body.index("function cassetteDrawing(")]
        a7 = next(a for a in F.ANCHORS if a["id"] == "A7")
        self.assertIn(f"{a7['size']} · hef {a7['hef']:.0f}", body,
                      "부품란의 앵커 매입깊이가 계산과 다르다")
        self.assertIn(f"연단 ≥ {a7['edge']:.0f}", body, "연단거리가 계산과 다르다")
        self.assertIn("도장 금지", body, "마찰접합면 도장 금지가 없다")
        self.assertIn("μ = 0.50", body, "마찰계수가 없다")
        self.assertIn("DG-HK60C-FAB-001", body, "지침서를 가리키지 않는다")

    def test_the_sheet_never_reads_the_layout_the_screen_shows(self):
        body = self.console[self.console.index("function boltDetailDrawing("):]
        body = body[:body.index("function cassetteDrawing(")]
        for bad in ("LC()", "twinView()", "compactView()"):
            self.assertFalse(bad in body, f"F-901 이 활성 배치({bad})를 읽는다")


if __name__ == "__main__":
    unittest.main()


class TestTheReflectanceRequirementIsBuildable(unittest.TestCase):
    """IR 뱅크 검토가 만든 요구 RIR3 이 제작 지침서에서 **만들 수 있는 것**이 됐는가.

    요구는 세 번 적혀야 지켜진다 — 무엇을(표면처리 사양) · 언제 재는가(ITP) ·
    미달이면 무엇을 하는가. 하나라도 빠지면 도면과 같은 치수의 다른 물건이 온다.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = SPEC.read_text(encoding="utf-8")

    def test_the_surface_table_carries_the_polish_and_the_reflectance(self):
        i = self.html.index("<th>가열실 내피</th>")
        row = self.html[i:i + 320]
        self.assertIn("#400", row, "연마 등급이 없으면 만들 방법이 안 적힌다")
        self.assertIn("ρ ≥ 0.4", row, "반사율이 없으면 2B 소지가 온다")

    def test_the_shutter_inner_face_gets_the_same_finish(self):
        """셔터도 공동의 벽면이다 — 셔터만 무광이면 그 자리가 냉점이 된다."""
        self.assertIn("에어록 단별 셔터 내면", self.html)

    def test_the_reflectance_is_measured_before_the_lamps_go_in(self):
        """램프가 붙으면 벽에 반사율계를 댈 자리가 없다."""
        i = self.html.index("가열실 내피 반사율 확인")
        row = self.html[i:i + 400]
        self.assertIn("램프 장착 전", row)
        self.assertIn("9", row, "몇 점을 재는지가 없다")
        self.assertIn("최저점", row, "평균만 보면 한 벽이 죽어도 통과한다")

    def test_the_itp_steps_are_numbered_without_a_gap(self):
        rows = re.findall(r'<tr><td class="num">(\d+)</td><td>', self.html)
        self.assertEqual(rows, [str(i) for i in range(1, len(rows) + 1)],
                         "ITP 단계 번호가 끊기거나 겹친다")

    def test_the_shutter_interlock_is_proven_at_assembly(self):
        self.assertIn("동시개방 금지", self.html,
                      "두 단이 동시에 열리면 손실이 두 배다 — 조립 때 확인한다")
