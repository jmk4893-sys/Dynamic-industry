"""칼날 카세트를 교체 가능한 물건으로 고정한다.

칼날은 소모품인데, 소모품을 고정 부품처럼 조립하면 교체 때마다 배선을 풀고
간격을 다시 잡는다. 그 손해는 어디에도 표시되지 않는다 — 사이클타임에도,
가동률 계산에도, 도면에도 나오지 않고 정비 기록에만 조용히 쌓인다.

그래서 다음을 검사한다.

  경계     닳는 것(칼날·히터·열전대)과 남는 것(슬라이드·로드셀)이 갈라져
           있는가. 갈라져 있지 않으면 '카세트' 는 이름일 뿐이다.
  구속     클램프 여유가 두 칼날 합성추력을 이기는가. 스프링 잠금인가 —
           공압으로 잠그면 공압이 빠질 때 카세트가 풀린다.
  분리     활선 상태로 커넥터를 뽑을 수 있는가. 히터 차단 확인이 잠금해제보다
           앞에 서 있어야 한다.
  시간     사람 조건(60°C·LOTO)과 기계 조건이 한 허가에 묶여 있는가.
           묶이면 자동교환이 냉각 13분을 통째로 기다린다 — 카세트를 넣은
           이유가 사라지는데, 그래도 라인은 돌기 때문에 아무도 모른다.
  일치     콘솔 계산·도면·사양서가 같은 수치를 말하는가.
"""

import importlib.util
import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

import console_consts                                        # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"

#: 두 칼날 합성추력. 사양서 OI-13 과 같은 값이어야 한다.
TANDEM_THRUST_KN = 13.37


def _model():
    spec = importlib.util.spec_from_file_location("plc_model", ROOT / "tools" / "plc_model.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.console = CONSOLE.read_text(encoding="utf-8")
        cls._rfq = RFQ.read_text(encoding="utf-8") if RFQ.exists() else None

    @property
    def rfq(self):
        """사양서는 사양서 브랜치에만 있다. 없으면 그 시험만 건너뛴다."""
        if self._rfq is None:
            self.skipTest("이 브랜치에는 사양서가 없다")
        return self._rfq

    def c(self, name, _depth=0):
        """콘솔 상수 하나. 다른 상수를 가리키면 한 단계 따라간다.

        카세트 온도는 칼날 온도 그 자체다(CASS_T_HOT = T_HKS). 값을 두 번
        적으면 칼날만 내리고 카세트는 그대로인 날이 온다 — 그래서 별칭으로
        두었고, 시험은 별칭을 풀어서 본다.
        """
        m = re.search(rf"\b{name}\s*=\s*([A-Za-z_][A-Za-z0-9_]*|[\d.]+)", self.console)
        self.assertIsNotNone(m, f"콘솔에 {name} 상수가 없다")
        v = m.group(1)
        if v[0].isdigit() or v[0] == ".":
            return float(v)
        self.assertLess(_depth, 3, f"{name} 상수 참조가 너무 깊다")
        return self.c(v, _depth + 1)

    def fn(self, name):
        m = re.search(rf"\n    function {name}\(.*?\n    \}}", self.console, re.S)
        self.assertIsNotNone(m, f"{name} 가 없다")
        return m.group(0)


class TestReplaceableUnit(_Base):
    """교체 단위의 경계가 실제로 그어져 있는가."""

    def test_the_cassette_carries_the_wearing_parts_and_their_heat(self):
        body = self.fn("knifeCassette")
        drawn = "\n".join(ln for ln in re.sub(r"/\*.*?\*/", "", body, flags=re.S).split("\n")
                          if re.search(r"\b(?:box|cylinder|column|plinth)\(", ln))
        for token in ("카세트 프레임", "테이퍼 로케이팅핀", "쐐기 클램프",
                      "잠금·존재센서", "블라인드메이트 커넥터",
                      "냉각 퍼지밸브", "온도센서", "취급 핸들"):
            self.assertIn(token, drawn, f"{token} 가 도면에 그려지지 않았다")

    def test_the_cassette_is_drawn_on_both_knives(self):
        self.assertGreaterEqual(
            self.fn("knifeBar").count("knifeCassette("), 1,
            "카세트가 칼날바에서 그려지지 않는다")
        calls = re.findall(r"knifeBar\([^)]*'(HK[BS])'\)", self.console)
        self.assertEqual(sorted(set(calls)), ["HKB", "HKS"],
                         "카세트를 그리는 knifeBar 가 두 칼날 모두에 쓰이지 않는다")

    def test_the_cassette_spans_the_knife_width(self):
        self.assertEqual(
            re.search(r"CASS_L\s*=\s*(\w+)", self.console).group(1), "KNIFE_W",
            "카세트 길이가 칼날 폭과 따로 논다 — 둘이 갈라지면 도면이 거짓말한다")


class TestRestraint(_Base):
    """구속은 추력을 이겨야 하고, 에너지가 빠질 때 풀리면 안 된다."""

    def test_clamps_beat_the_combined_thrust(self):
        total = self.c("CASS_CLAMP_KN") * 2
        self.assertGreaterEqual(
            total / TANDEM_THRUST_KN, 2.0,
            f"클램프 {total} kN 이 두 칼날 합성추력 {TANDEM_THRUST_KN} kN 의 2배에 못 미친다")

    def test_the_clamp_is_spring_locked_not_air_locked(self):
        drive = next(d for d in _model().DRIVES if d.tag == "CY-405")
        self.assertIn("스프링", drive.stop,
                      "클램프가 공압으로 잠기면 공압이 빠질 때 카세트가 풀린다")

    def test_locating_repeatability_is_far_inside_the_gap_tolerance(self):
        self.assertLessEqual(
            self.c("CASS_REPEAT"), 2.0 / 10,
            "반복정밀도가 칼끝 간격 공차 ±2mm 대비 여유가 없다")


class TestServiceDisconnect(_Base):
    """활선 분리를 구조로 막는다."""

    def test_heater_isolation_is_a_safety_input(self):
        leaf = next(l for l in _model().LEAVES if l.name == "HEATER_ISOLATED")
        self.assertEqual(leaf.io, _model().FDI,
                         "히터 차단 확인이 표준 DI 면 표준 PLC 고장 시 확인이 사라진다")

    def test_release_requires_heater_isolation(self):
        d = {x.name: x for x in _model().DERIVED}
        self.assertIn("HEATER_ISOLATED", d["CASSETTE_RELEASE"].terms,
                      "히터가 살아 있는 채로 잠금이 풀린다")

    def test_a_fitted_cassette_is_verified_before_it_cuts(self):
        d = {x.name: x for x in _model().DERIVED}
        self.assertIn("CASSETTE_READY", d["HKB_Z_PERMIT"].terms)
        for term in ("CASSETTE_LOCKED", "CONNECTOR_MATED", "KNIFE_GAP_OK"):
            self.assertIn(term, d["CASSETTE_READY"].terms,
                          f"교환 뒤 {term} 확인 없이 절입한다")


class TestHumanAndMachineAreSeparatePermits(_Base):
    """둘을 한 허가로 묶으면 자동교환이 냉각을 통째로 기다린다."""

    def setUp(self):
        self.d = {x.name: x for x in _model().DERIVED}

    def test_the_machine_permit_does_not_wait_for_cooling(self):
        t = self.d["CASSETTE_RELEASE"].terms
        self.assertNotIn("CASSETTE_COOL_OK", t)
        self.assertNotIn("MAINT_PERMIT", t)

    def test_the_human_permit_does_wait(self):
        t = self.d["CASSETTE_HANDLING_SAFE"].terms
        for term in ("CASSETTE_COOL_OK", "MAINT_PERMIT"):
            self.assertIn(term, t, f"사람이 {term} 없이 250°C 카세트에 손을 댄다")

    def test_the_touch_limit_is_a_burn_limit(self):
        self.assertLessEqual(self.c("CASS_T_TOUCH"), 65,
                             "접촉 허용온도가 화상 한계를 넘는다")


class TestChangeoverTime(_Base):
    """정지시간은 계산에서 나오고, 세 문서가 같은 값을 말해야 한다."""

    def setUp(self):
        self.mass = self.c("CASS_MASS")
        self.cp = self.c("CASS_CP")

    def _area(self):
        L, W, H = self.c("KNIFE_W"), self.c("CASS_W"), self.c("CASS_H")
        return 2 * (L * W + L * H + W * H)

    def _cool(self):
        hot, touch, amb = self.c("CASS_T_HOT"), self.c("CASS_T_TOUCH"), self.c("CASS_T_AMB")
        lmtd = (hot - touch) / math.log((hot - amb) / (touch - amb))
        return self.mass * self.cp * 1e3 * (hot - touch) / (self.c("CASS_HCONV") * self._area() * lmtd)

    def _heat(self, t0):
        return (self.mass * self.cp * 1e3 * (self.c("CASS_T_HOT") - t0)
                / (self.c("CASS_HEAT_KW") * 1e3 * self.c("CASS_HEAT_ETA")))

    def test_auto_changeover_keeps_cooling_off_the_critical_path(self):
        auto = self.c("CASS_SWAP_AUTO") + self._heat(self.c("CASS_T_PRE"))
        self.assertLess(auto, self._cool(),
                        "자동 교환 정지가 냉각시간보다 길다 — 매거진이 냉각을 받지 못하고 있다")
        self.assertLess(auto / 60, 6, "자동 교환 정지가 6분을 넘는다")

    def _minutes(self, doc):
        """문서에 적힌 '… 분' 을 띄어쓰기·엔티티에 상관없이 모은다."""
        flat = re.sub(r"(?:&nbsp;|\s)+", "", doc.replace("</span>", ""))
        return set(re.findall(r"([\d]+\.[\d])분", flat))

    def test_manual_changeover_pays_the_full_cooling(self):
        auto = self.c("CASS_SWAP_AUTO") + self._heat(self.c("CASS_T_PRE"))
        man = (self._cool() + self.c("CASS_SWAP_MANUAL")
               + self.c("CASS_VERIFY") + self._heat(self.c("CASS_T_AMB")))
        self.assertGreater(man, 3 * auto,
                           "수동과 자동의 차이가 없으면 자동교환 설비가 값을 못 한다")
        self.assertIn(f"{man / 60:.1f}", self._minutes(self.rfq),
                      "사양서의 수동 교환 정지가 계산값과 다르다")

    def test_the_documents_quote_one_number(self):
        """콘솔은 계산하고 사양서는 인용한다. 인용이 계산에서 벗어나면 안 된다."""
        auto = (self.c("CASS_SWAP_AUTO") + self._heat(self.c("CASS_T_PRE"))) / 60
        cool = self._cool() / 60
        table = re.search(r"<caption>교환 정지시간</caption>.*?</table>", self.rfq, re.S)
        self.assertIsNotNone(table, "사양서에 교환 정지시간 표가 없다")
        for value, what in ((auto, "자동교환 정지"), (cool, "강제공랭")):
            for doc, where in ((self.console, "콘솔 사양 대화상자"),
                               (table.group(0), "사양서 6.9 정지시간 표")):
                self.assertIn(f"{value:.1f}", self._minutes(doc),
                              f"{where} 의 {what} 이 계산값 {value:.1f} 분과 다르다")
        # 6.6 무인운전 표도 같은 값을 인용한다 — 인용처가 둘이면 둘 다 봐야 한다
        row = re.search(r"<th>— 그때의 정지</th>.*?</tr>", self.rfq, re.S)
        self.assertIsNotNone(row, "6.6 표에 칼날교환 정지시간 행이 없다")
        self.assertIn(f"{auto:.1f}", self._minutes(row.group(0)),
                      f"사양서 6.6 의 칼날교환 정지가 계산값 {auto:.1f} 분과 다르다")

    def test_the_cassette_is_too_heavy_to_lift_by_hand(self):
        self.assertGreater(self.mass, 25, "이 질량이면 인력 취급 제한이 필요 없다")
        for doc, where in ((self.console, "콘솔"), (self.rfq, "사양서")):
            self.assertIn("인력 취급 한계", doc, f"{where} 에 인력 취급 제한이 없다")


class TestTheDrawingSheet(_Base):
    """도면이 계산에서 나와야 표와 계산이 갈라지지 않는다."""

    def test_the_sheet_exists_and_is_reachable(self):
        self.assertIn('data-drawing="cassette"', self.console, "카세트 도면 탭이 없다")
        self.assertIn("cassetteDrawing()", self.console, "카세트 도면이 그려지지 않는다")
        self.assertIn("D-501", self.console, "도면번호가 없다")

    def test_the_sheet_reads_the_computed_figures(self):
        body = self.fn("cassetteDrawing")
        for token in ("cassCoolSec()", "cassStopAuto()", "cassStopManual()",
                      "CASS_MASS", "CASS_REPEAT", "CASS_CLAMP_KN"):
            self.assertIn(token, body, f"도면이 {token} 를 읽지 않고 값을 적어 넣었다")

    def test_the_sheet_writes_no_time_by_hand(self):
        """읽기만 해서는 부족하다 — 옆에 손으로 적은 값이 있으면 그쪽이 갈라진다."""
        body = re.sub(r"/\*.*?\*/", "", self.fn("cassetteDrawing"), flags=re.S)
        typed = re.findall(r"(?<![$\w.])(\d+\.\d)\s*(?:분|s\b)", body)
        self.assertEqual(typed, [],
                         f"도면에 손으로 적은 시간 {typed} 이 있다 — 계산이 바뀌어도 이 값은 안 바뀐다")

    def test_the_sheet_shows_both_the_boundary_and_the_restraint(self):
        body = self.fn("cassetteDrawing")
        self.assertIn("잔류부", body, "도면에 남는 쪽이 표시되지 않는다")
        self.assertIn("KNIFE_GAP_OK", body, "교환 후 확인 신호가 도면에 없다")
        self.assertIn("HEATER_ISOLATED", body + self.console)


class TestTheSpecification(_Base):
    """사양서가 교체 구조를 요구사항으로 적고 있는가."""

    def test_there_is_a_clause_for_the_cassette(self):
        self.assertRegex(self.rfq, r'<div class="n">6\.9</div>', "카세트 조항이 없다")
        self.assertIn("BC-201 카세트 인터페이스", self.rfq)

    def test_the_clause_names_the_drawing(self):
        self.assertIn("D-501", self.rfq, "사양서가 카세트 도면을 가리키지 않는다")

    def test_fat_proves_the_things_that_can_silently_fail(self):
        for token in ("카세트 교환 10회 반복", "활선 분리 방지",
                      "카세트 자동교환 정지시간", "카세트 강제공랭 실측"):
            self.assertIn(token, self.rfq, f"FAT 에 '{token}' 항목이 없다")

    def test_the_open_item_moved_from_structure_to_lifetime(self):
        oi = re.search(r"<b>OI-12</b>.*?</div>\s*</div>", self.rfq, re.S).group(0)
        self.assertIn("6.9", oi, "OI-12 가 닫힌 교체 구조를 가리키지 않는다")
        self.assertIn("언제 교체하는가", oi,
                      "OI-12 의 남은 미결이 '언제' 로 좁혀져 있지 않다")
        self.assertNotIn("교체 구조가 정해져 있지 않다", oi,
                         "6.9 항이 교체 구조를 정했는데 OI-12 는 아직 미결이라 말한다")


if __name__ == "__main__":
    unittest.main()


class TestTheWithdrawalEnvelopeIsReserved(unittest.TestCase):
    """교체 단위를 정했으면 그 단위가 지나갈 자리도 정해야 한다.

    사양서 6.9 는 카세트 인터페이스(핀·클램프·블라인드메이트·포켓)를 전부
    닫아 놓고도 카세트가 기계 밖으로 나가는 자리는 정하지 않았었다. 압축
    배치를 재어 보면 바닥에는 그 자리가 없다 — 갠트리가 y ±1,420 을 쓸고
    다니고, 스윕 밖으로 빼면 외장을 뚫는다.

    그래서 갠트리 상단과 외장 갓돌 사이의 빈 층을 쓴다. 이 시험은 그 층이
    실제로 비어 있는지, 그리고 포락선이 카세트보다 좁지 않은지를 본다.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.env = console_consts.env(cls.src)

    def c(self, name):
        self.assertIn(name, self.env, f"콘솔에 {name} 상수가 없다")
        return self.env[name]

    def test_the_magazine_clears_the_gantry_sweep(self):
        """갠트리가 지나가는 높이에 매거진을 두면 첫 사이클에 부딪힌다."""
        gantry_top = self.c("CBEAM_Z") + .12 + .07          # X축 랙피니언 상면
        magazine_bottom = self.c("CKC_Z") - .32              # 포켓 받침 아래
        self.assertGreater(
            magazine_bottom, gantry_top + .15,
            f"매거진 하단 {magazine_bottom:.3f} m 가 갠트리 상단 "
            f"{gantry_top:.3f} m 에 너무 가깝다")

    def test_the_magazine_stays_under_the_skin(self):
        """갓돌 위로 나가면 외장이 아니라 그냥 노출 설비가 된다."""
        self.assertLess(self.c("CKC_Z") + .14, self.c("SKIN_TOP"),
                        "매거진이 외장 갓돌보다 높다")

    def test_the_envelope_is_at_least_the_cassette(self):
        """포락선이 카세트보다 좁으면 예약한 뜻이 없다."""
        cass = self.c("KNIFE_W")                             # CASS_L = KNIFE_W
        depth = self.c("CKC_ENV_Z1") - self.c("CKC_ENV_Z0")
        self.assertGreaterEqual(depth, .20, "포락선 높이가 카세트 두께에 못 미친다")
        span = abs(self.c("CKC_Y")) + cass / 2 + self.c("PANEL_W") / 2
        self.assertGreaterEqual(
            span, cass, f"인출 통로 {span:.3f} m 가 카세트 {cass:.3f} m 보다 짧다")

    def test_the_magazine_is_clear_of_the_full_roll(self):
        """만권 롤과 같은 x 선을 쓰므로 y 로 비켜 있어야 한다."""
        roll_edge = 1.46 / 2                                  # ROLL_FACE/2
        cass_edge = self.c("CKC_Y") + self.c("KNIFE_W") / 2
        self.assertLess(cass_edge, -roll_edge,
                        f"카세트 끝 {cass_edge:.3f} m 가 만권 롤 {-roll_edge:.3f} m 와 겹친다")

    def test_the_consumable_path_ends_outside_the_fence(self):
        """소모품은 사람이 만지는 날이 온다 — 그때 방책 안이면 무인이 끊긴다."""
        self.assertLess(self.c("CKC_RACK_Y"), -self.c("CFENCE_YN"),
                        "KC-301 이 방책 안에 있다")
        self.assertLessEqual(self.c("RH_Y1"), self.c("CKC_RACK_Y") + 1e-9,
                             "모노레일이 KC-301 까지 닿지 않는다")

    def test_the_saddle_is_clear_of_the_roll_saddle(self):
        """같은 열에 두면서 겹치면 롤을 내려놓을 자리가 없어진다."""
        roll_far = -5.20 - 1.46 / 2                           # BS_SADDLE.y − ROLL_FACE/2
        cass_near = self.c("CKC_RACK_Y") + self.c("KNIFE_W") / 2
        self.assertLess(cass_near, roll_far,
                        f"KC-301 끝 {cass_near:.3f} m 가 만권 롤 끝 {roll_far:.3f} m 와 겹친다")

    def test_the_drawing_reserves_the_envelope(self):
        """도면에 없으면 현장에서 배관이 그 자리를 먹는다."""
        m = re.search(r"\n    function compactDrawing\(.*?\n    \}", self.src, re.S)
        self.assertIsNotNone(m, "compactDrawing 을 찾지 못했다")
        body = m.group(0)
        self.assertIn("인출 포락선", body, "D-601 이 포락선을 예약하지 않는다")
        self.assertIn("url(#hatch)", body, "예약 공간이 해칭으로 표시되지 않는다")

    def test_the_specification_states_the_envelope(self):
        if not RFQ.exists():
            self.skipTest("이 브랜치에는 사양서가 없다")
        rfq = RFQ.read_text(encoding="utf-8")
        self.assertIn("인출 포락선", rfq, "사양서 6.9 에 포락선 조항이 없다")
        self.assertIn("KC-301", rfq, "사양서가 방책 밖 반출처를 적지 않았다")
        self.assertIn("금지영역", rfq, "포락선을 금지영역으로 표기하라는 요구가 없다")
