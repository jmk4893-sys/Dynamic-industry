"""조달 계산과 조달 지침서 — 자재 · 운반 · 구매.

부품 카탈로그는 "무엇을 만드는가" 를 든다. 조달은 그것을 **살 수 있는
것과 실을 수 있는 것**으로 바꾼다. 그 변환에서 틀리면 도면은 맞는데
제작이 멈춘다 — 살 수 없는 두께를 그렸거나, 정척보다 긴 부재를 그렸거나,
차에 안 들어가는 것을 만들었을 때다.

이 시험이 지키는 것:

  ① 전 부재가 유통 규격 안에 있다 (없으면 제작 착수 불가)
  ② 절단 배치가 실제로 조각을 다 담는다 (총 길이 나누기가 아니다)
  ③ 차수 순서가 세우는 순서와 같다 (아니면 현장에 둘 자리가 없다)
  ④ 구매품 전 종에 발주 사양이 있다 (없으면 구매가 임의로 고른다)
"""

import pathlib
import unittest

from . import _path  # noqa: F401

import gen_procure_doc as GEN
import parts as PT
import procure as PR

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestEveryPieceCanBeBought(unittest.TestCase):
    """도면에 그릴 수는 있어도 살 수 없는 것이 있으면 제작이 멈춘다."""

    def test_no_piece_falls_outside_the_stock_range(self):
        """이 시험이 실제로 여섯 건을 잡았다 — t90 통판, 유통 시트를 넘는 대판 넷, PC 대판."""
        bad = PR.unbuyable()
        self.assertEqual(bad, [], "살 수 없는 치수: " + "; ".join(
            f"{pid} {what} — {why}" for pid, what, why in bad))

    def test_every_plate_thickness_is_a_stock_thickness(self):
        for lot in PR.plate_lots():
            avail = PR.PLATE_THICK.get(lot.mat)
            self.assertIsNotNone(avail, f"{lot.mat} 의 유통 두께가 등록되지 않았다")
            self.assertIn(lot.t, avail, f"{lot.mat} t{lot.t:g} 는 유통 두께가 아니다")

    def test_every_material_has_a_stock_form(self):
        """재고 형태(시트/플랫바/보드)를 틀리게 적으면 없는 문제를 만들어 낸다."""
        mats = {p.mat for p in PT.P if not p.buy}
        for m in mats:
            if m == "—":
                continue
            self.assertIn(m, PR.PLATE_STOCK, f"{m} 의 재고 규격이 없다")
            self.assertIn(m, PR.PLATE_THICK, f"{m} 의 유통 두께가 없다")

    def test_no_member_is_longer_than_a_mill_length(self):
        for lot in PR.bar_lots():
            self.assertEqual(lot.oversize, (),
                             f"{lot.section} 에 정척보다 긴 조각이 있다: {lot.oversize}")


class TestTheCuttingListIsAnActualCuttingList(unittest.TestCase):
    """총 길이를 정척으로 나눈 것은 발주서가 아니다."""

    def test_every_piece_lands_in_some_bar(self):
        """조각 하나가 배치에서 빠지면 그 부재는 자재 없이 도면만 있다."""
        for lot in PR.bar_lots():
            want = sum(q for _L, q, _p in lot.pieces)
            got = sum(len(c.pieces) for c in lot.cuts)
            self.assertEqual(got, want,
                             f"{lot.section}: 조각 {want} 개 중 {got} 개만 배치됐다")

    def test_no_bar_is_overfilled(self):
        """정척보다 많이 담으면 그 배치는 종이 위에서만 성립한다."""
        for lot in PR.bar_lots():
            for c in lot.cuts:
                self.assertLessEqual(c.used, c.stock - PR.BAR_TRIM + 1e-6,
                                     f"{lot.section}: 정척 {c.stock} 에 {c.used} 를 담았다")

    def test_the_kerf_is_counted(self):
        """톱날 폭을 안 세면 마지막 조각이 안 나온다.

        길이를 손실이 실제로 갈라 놓는 자리로 고른다. 6,000 정척에서 트림
        50 을 빼면 5,950 이 남고, 1,980 세 개는 5,940 으로 들어간다 —
        그러나 조각마다 톱날 5 를 더하면 5,955 로 넘친다. 손실을 0 으로
        두면 이 시험이 실패한다.
        """
        cuts = PR.pack_bars([1980, 1980, 1980], (6000,))
        self.assertEqual(len(cuts), 2,
                         "1,980 세 개가 6,000 정척 한 본에 들어간다고 계산했다 — 톱날 폭을 뺐는가")
        self.assertEqual(len(PR.pack_bars([1960, 1960, 1960], (6000,))), 1,
                         "손실을 과하게 얹었다 — 1,960 셋은 한 본에 들어간다")

    def test_a_short_stock_is_preferred_when_it_fits(self):
        """12 m 를 사서 2 m 만 쓰면 나머지는 창고 자리만 차지한다."""
        cuts = PR.pack_bars([1800, 1800], PR.BAR_STOCK)
        self.assertTrue(all(c.stock == 6000 for c in cuts),
                        "짧은 정척으로 되는데 긴 정척을 골랐다")

    def test_plate_sheets_cover_every_piece(self):
        for lot in PR.plate_lots():
            self.assertEqual(lot.unbuyable, (), f"{lot.mat} t{lot.t:g}: {lot.unbuyable}")
            if sum(q for _L, _W, q, _p in lot.pieces):
                self.assertGreaterEqual(lot.sheets, 1,
                                        f"{lot.mat} t{lot.t:g} 매수가 0 이다")

    def test_the_trim_is_skipped_only_for_soft_materials(self):
        """무른 재료는 칼로 재단하고 규격대로 온다 — 강판에 그 규칙을 쓰면 안 된다."""
        for m in PR.NO_TRIM:
            self.assertNotIn(m, ("SS400", "SM490A", "STS304", "SM45C", "SKD11"),
                             f"{m} 은 전단 재료인데 트림 여유를 뺐다")


class TestTheTransportSplitFollowsTheErectionOrder(unittest.TestCase):
    """나중에 세울 것이 먼저 도착하면 현장에 둘 자리가 없다."""

    def test_load_numbers_run_in_erection_order(self):
        loads = PR.truck_loads()
        stages = [x.stage for x in loads]
        self.assertEqual(stages, sorted(stages), "차수 번호가 세우는 단계 순서가 아니다")
        self.assertEqual([x.seq for x in loads], list(range(1, len(loads) + 1)))

    def test_the_fence_arrives_last(self):
        """방책이 먼저 서면 그 안으로 들어갈 기계의 반입로가 막힌다."""
        loads = PR.truck_loads()
        fence = [x for x in loads if x.stage == PR.ERECT_STAGE["M-013"]]
        self.assertTrue(fence, "방책이 운반 차수에 없다")
        self.assertEqual(fence[-1].seq, loads[-1].seq, "방책이 마지막 차수가 아니다")

    def test_every_part_is_loaded_exactly_once(self):
        """한 부품이 빠지면 조립 날에 없는 부품이고, 두 번 실리면 두 번 산 것이다."""
        loaded = [it[0] for x in PR.truck_loads() for it in x.items]
        self.assertEqual(len(loaded), len(set(loaded)), "같은 품번이 두 차에 실렸다")
        self.assertEqual(set(loaded), {p.pid for p in PT.P}, "실리지 않은 부품이 있다")

    def test_no_truck_is_overloaded(self):
        for x in PR.truck_loads():
            self.assertLessEqual(x.kg, x.truck.kg * PR.LOAD_MARGIN + 1e-6,
                                 f"{x.seq}차 적재 {x.kg:,.0f} 이 계획 한도를 넘는다")
            for _pid, _n, _q, _kg, lg in x.items:
                self.assertLessEqual(lg, x.truck.L,
                                     f"{x.seq}차에 적재장보다 긴 부재가 있다")

    def test_the_margin_is_real(self):
        """정격을 꽉 채워 계획하면 결박구 무게와 계근 오차에서 초과가 난다."""
        self.assertLess(PR.LOAD_MARGIN, 1.0)
        self.assertGreaterEqual(PR.LOAD_MARGIN, 0.80)

    def test_every_module_has_an_erection_stage(self):
        for m in PT.MODULES:
            self.assertIn(m, PR.ERECT_STAGE, f"{m} 의 세우는 차수가 없다")

    def test_the_truck_is_the_smallest_that_fits(self):
        """5 t 로 되는 짐에 트레일러를 부르면 그 비용이 그대로 남는다."""
        for x in PR.truck_loads():
            longest = max(r[4] for r in x.items)
            smaller = [t for t in PR.TRUCKS if t.L < x.truck.L and t.L >= longest]
            for t in smaller:
                self.assertGreater(x.kg, t.kg * PR.LOAD_MARGIN,
                                   f"{x.seq}차는 {t.name} 로도 된다")


class TestEveryPurchasedItemCanBeOrdered(unittest.TestCase):
    """발주 사양이 없으면 구매 담당이 임의로 고르고, 그 선택이 조립 날에 드러난다."""

    def test_every_purchased_part_has_a_procurement_spec(self):
        missing = [p.pid for p in PT.P if p.buy and p.pid not in PR.BUY_SPEC]
        self.assertEqual(missing, [], f"발주 사양이 없는 구매품: {missing}")

    def test_the_spec_names_a_system_the_document_groups_by(self):
        for pid, (sys_, *_rest) in PR.BUY_SPEC.items():
            self.assertIn(sys_, PR.SYS, f"{pid} 의 계통 '{sys_}' 이 목록에 없다")

    def test_no_spec_is_written_for_a_part_that_does_not_exist(self):
        ids = {p.pid for p in PT.P}
        for pid in PR.BUY_SPEC:
            self.assertIn(pid, ids, f"{pid} 은 카탈로그에 없는 품번이다")
            self.assertTrue([p for p in PT.P if p.pid == pid][0].buy,
                            f"{pid} 은 제작품인데 구매 사양이 붙어 있다")

    def test_safety_parts_demand_a_certificate(self):
        """안전 부품은 서류가 곧 사용 허가다 — 인증서 없이 반입하면 시운전을 못 한다."""
        for pid, (sys_, _r, _i, insp) in PR.BUY_SPEC.items():
            if sys_ == "안전":
                self.assertTrue("인증" in insp or "실증" in insp,
                                f"{pid} 안전 부품에 인증·실증 요구가 없다")

    def test_spares_are_only_for_consumables_and_long_stops(self):
        """전부 예비를 두면 창고가 공장이 된다."""
        ids = {p.pid for p in PT.P}
        for pid in PR.SPARES:
            self.assertIn(pid, ids, f"예비품 목록의 {pid} 이 카탈로그에 없다")
        self.assertLess(len(PR.SPARES), 15, "예비품이 너무 많다 — 소모품과 정지시간만 든다")


class TestTheProcurementDocumentSaysWhatWasComputed(unittest.TestCase):
    """문서를 손으로 고치면 카탈로그와 갈라진다."""

    @classmethod
    def setUpClass(cls):
        cls.html = GEN.OUT.read_text(encoding="utf-8")

    def test_the_document_is_exactly_what_the_generator_prints(self):
        self.assertEqual(self.html, GEN.build(),
                         "문서가 tools/gen_procure_doc.py 의 출력과 다르다 — "
                         "python3 tools/gen_procure_doc.py --write 로 다시 찍는다")

    def test_the_totals_are_the_computed_totals(self):
        bl, pl = PR.bar_lots(), PR.plate_lots()
        self.assertIn(f"{sum(l.bars for l in bl)} 본", self.html, "정척 본수가 계산과 다르다")
        self.assertIn(f"{sum(l.sheets for l in pl)} 매", self.html, "시트 매수가 계산과 다르다")
        self.assertIn(f"{len(PR.truck_loads())} 차", self.html, "차수가 계산과 다르다")

    def test_every_load_and_every_purchased_part_appears(self):
        for x in PR.truck_loads():
            self.assertIn(f"{x.seq}차 적재 명세", self.html, f"{x.seq}차 명세가 없다")
        for p in PT.P:
            if p.buy:
                self.assertIn(p.pid, self.html, f"{p.pid} 구매 사양이 문서에 없다")

    def test_no_markdown_leaks_into_the_printed_page(self):
        """산문 필드에 ** 를 쓰는 일이 실제로 있었고 별표가 그대로 인쇄됐다.

        이 시험이 그 부류를 영구히 막는다 — 생성 문서 셋 전부를 본다.
        """
        for name in ("dg-hk60-procurement.html", "dg-hk60-assembly.html",
                     "dg-hk60-fab-spec.html"):
            txt = (ROOT / "docs" / name).read_text(encoding="utf-8")
            self.assertNotIn("**", txt, f"{name} 에 마크다운 별표가 그대로 남았다")

    def test_it_tells_the_reader_which_part_is_theirs(self):
        """셋은 읽는 사람이 다르다 — 그것을 안 적으면 셋 다 아무도 안 읽는다."""
        for m in ("자재 담당", "물류", "구매 담당"):
            self.assertIn(m, self.html, f"'{m}' 가 문서 안내에 없다")

    def test_it_says_what_must_be_ordered_now(self):
        """8~12 주 납기는 어떤 설계 작업보다 길다."""
        self.assertIn("서보", self.html)
        self.assertIn("8~12 주", self.html)
        self.assertIn("승인도", self.html, "승인 후 제작 품목을 밝히지 않는다")

    def test_it_defers_geometry_to_the_catalogue(self):
        self.assertIn("tools/parts.py", self.html)
        self.assertIn("손으로 고치지 않는다", self.html)
        self.assertIn("상세설계에서 확정한다", self.html)


class TestTheCatalogueStaysConsistentWithTheSpecification(unittest.TestCase):
    """자재 발주표가 찾아낸 모순은 다시 생기면 안 된다."""

    def test_the_cassette_mass_matches_the_load_the_specification_uses(self):
        """카세트를 통판으로 적었더니 128 kg 이 되어 35 kg/벌 과 3.7 배 어긋났다.

        지침서는 이 질량으로 J5(테이퍼 핀)와 갠트리 이동부 자중을 잡는다.
        카탈로그가 다시 무거워지면 그 계산이 조용히 틀어진다.
        """
        import console_consts
        import fab_spec as F

        body = [p for p in PT.P if p.pid == "P-005-17"][0]
        insert = [p for p in PT.P if p.pid == "P-005-15"][0]
        pin = [p for p in PT.P if p.pid == "P-005-18"][0]
        one_set = body.kg + insert.kg + 4 * pin.kg
        want = console_consts.const("CASS_MASS")
        self.assertLess(abs(one_set - want) / want, 0.30,
                        f"카세트 1벌 {one_set:.1f} kg 이 사양 {want} kg 과 30 % 넘게 다르다")
        self.assertAlmostEqual(F.W_CASS, want * F.G / 1000, places=6)


if __name__ == "__main__":
    unittest.main()


class TestTheLampIsBoughtWithItsGuarantee(unittest.TestCase):
    """램프 지지 검토가 만든 요구 RLM4 — 우리가 못 정하는 값은 **사는 조건**이 된다.

    봉착부 온도 창은 폭 6.5 mm 로 제작 공차보다 좁다. 그것을 설치 위치로
    맞추려 들면 매번 실패하므로, 제작사가 보증하는 형식으로 사는 수밖에 없다.
    **구매 사양에 안 적으면 그냥 램프가 온다.**
    """

    def test_the_seal_temperature_window_is_in_the_purchase_spec(self):
        sys_, rating, iface, insp = PR.BUY_SPEC["P-002-18"]
        self.assertIn("250", rating)
        self.assertIn("350", rating)
        self.assertIn("보증", rating, "'보증' 이 없으면 참고값이 된다")

    def test_the_guarantee_is_witnessed_not_just_claimed(self):
        _s, _r, _i, insp = PR.BUY_SPEC["P-002-18"]
        self.assertIn("성적서", insp, "곡선 성적서가 없으면 보증을 확인할 방법이 없다")
        self.assertIn("SAT", insp, "인수 때 실측하지 않으면 서류로 끝난다")

    def test_the_heated_length_matches_the_ir_bank_review(self):
        _s, rating, iface, _i = PR.BUY_SPEC["P-002-18"]
        import analysis_irbank as AIR
        self.assertIn(f"{AIR.NEW_LEN*1000:,.0f}", rating, "발열장이 구매 사양에 없으면 관습 길이가 온다")
        self.assertIn("유동", iface, "양단 고정이면 첫 승온에서 뜯긴다")

    def test_the_shutter_cylinder_follows_the_airlock_decision(self):
        import airlock as AIR
        _s, rating, _i, insp = PR.BUY_SPEC["P-002-22"]
        self.assertIn(f"행정 {AIR.stroke()*1000:.0f}", rating)
        self.assertIn("단별", rating)
        self.assertIn("동시개방 금지", insp)

    def test_every_purchased_item_still_has_a_spec(self):
        rows = PR.buy_rows()
        self.assertGreater(len(rows), 40, "구매품이 없다면 이 시험이 지키는 것이 없다")
        missing = [r[0].pid for r in rows if r[0].pid not in PR.BUY_SPEC]
        self.assertEqual(missing, [], f"구매 사양이 없는 품목: {missing}")
