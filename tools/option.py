"""옵션 DG-HK120C — 표준과 같은 코드로 푼 옵션, 그리고 둘의 차이.

옵션은 따로 적지 않는다. 변형 로더(variant.py)가 콘솔 HK120C 의 뿌리 값(단수 7 ·
램프 96 · 셀 2)을 핀으로 박고 카탈로그·조달·부하표를 **새로** 풀어 둔 것을 여기서
표준과 나란히 놓는다. 견적은 차이로 한다:

    옵션 가격 = 표준 가격 + (옵션 − 표준)

그래서 이 모듈이 내는 것은 전부 "옵션에서 무엇이 더 들고 무엇이 빠지는가" 다 —
부품 한 종 한 종의 수량·질량 차이, 정척·시트 차이, 구매품 차이, 운반 차수 차이.
옵션 쪽 함수를 부를 때는 반드시 pinned() 안에서 부른다 (그 모듈이 부를 때 다시
콘솔 상수를 읽는 경우가 있다).
"""

from __future__ import annotations

from typing import NamedTuple

import electrical as EL_B
import parts as PT_B
import procure as PR_B
import variant

LID = "twin"
_TW = variant.load(LID, "parts", "procure", "electrical")
PT_T, PR_T, EL_T = _TW["parts"], _TW["procure"], _TW["electrical"]


def pinned():
    return variant.pinned(LID)


class PartDelta(NamedTuple):
    pid: str
    mod: str
    name: str
    base: object | None     # 표준 부품 (없으면 옵션에만 있다)
    opt: object | None      # 옵션 부품 (없으면 옵션에서 빠진다)

    @property
    def dqty(self) -> int:
        return (self.opt.qty if self.opt else 0) - (self.base.qty if self.base else 0)

    @property
    def dkg(self) -> float:
        return (self.opt.total_kg if self.opt else 0.0) - (self.base.total_kg if self.base else 0.0)

    @property
    def kind(self) -> str:
        """'추가' · '제외' · '수량' · '치수' · '수량·치수'."""
        if self.base is None:
            return "추가"
        if self.opt is None:
            return "제외"
        q = self.base.qty != self.opt.qty
        g = self.base.shape.label() != self.opt.shape.label()
        return "수량·치수" if q and g else ("치수" if g else "수량")


def part_deltas() -> list[PartDelta]:
    """표준과 옵션이 다른 부품 — 수량이나 형상이 다르거나 한쪽에만 있다."""
    b = {p.pid: p for p in PT_B.P}
    t = {p.pid: p for p in PT_T.P}
    out = []
    for pid in sorted(set(b) | set(t)):
        pb, pt = b.get(pid), t.get(pid)
        if pb and pt and pb.qty == pt.qty and pb.shape.label() == pt.shape.label():
            continue
        ref = pt or pb
        out.append(PartDelta(pid, ref.mod, ref.name, pb, pt))
    return out


def modules() -> list[tuple[str, str, float, float, int, int]]:
    """(모듈, 옵션 이름, 표준 kg, 옵션 kg, 표준 품목, 옵션 품목)."""
    out = []
    for m in PT_T.MODULES:
        out.append((m, PT_T.MODULE_NAME[m], PT_B.module_kg(m), PT_T.module_kg(m),
                    sum(1 for p in PT_B.P if p.mod == m), sum(1 for p in PT_T.P if p.mod == m)))
    return out


def totals() -> dict:
    """한눈에 보는 표준 · 옵션 · 차이."""
    with pinned():
        bl_t, pl_t, lo_t = PR_T.bar_lots(), PR_T.plate_lots(), PR_T.truck_loads()
        e_t = EL_T.summary()
        bad_t = PR_T.unbuyable()
    bl_b, pl_b, lo_b = PR_B.bar_lots(), PR_B.plate_lots(), PR_B.truck_loads()
    e_b = EL_B.summary()

    def cat(pt):
        return dict(items=len(pt.P), fab=sum(1 for p in pt.P if not p.buy),
                    buy=sum(1 for p in pt.P if p.buy), pieces=sum(p.qty for p in pt.P),
                    kg=sum(p.total_kg for p in pt.P))

    b, t = cat(PT_B), cat(PT_T)
    b.update(bars=sum(x.bars for x in bl_b), sheets=sum(x.sheets for x in pl_b),
             trucks=len(lo_b), kw=e_b["kw"], af=e_b["main_af"], tr=e_b["tr_kva"])
    t.update(bars=sum(x.bars for x in bl_t), sheets=sum(x.sheets for x in pl_t),
             trucks=len(lo_t), kw=e_t["kw"], af=e_t["main_af"], tr=e_t["tr_kva"])
    return dict(base=b, opt=t, unbuyable=bad_t)


def _key_bar(x):
    return (x.mat, x.kind, x.section, x.stock_len)


def bar_deltas() -> list[tuple[str, str, float, float, int, int, float]]:
    """(재질, 단면, 표준 정척, 옵션 정척, 표준 본수, 옵션 본수, 순중량 차 kg) — 달라진 것만.

    정척은 양쪽을 따로 낸다 — 같은 단면이라도 가장 긴 조각이 바뀌면 정척이 바뀐다
    (옵션은 런웨이가 H-250 으로 옮겨 가서 H-200 에는 짧은 스퍼만 남는다)."""
    with pinned():
        t = {(x.mat, x.section): x for x in PR_T.bar_lots()}
    b = {(x.mat, x.section): x for x in PR_B.bar_lots()}
    out = []
    for k in sorted(set(b) | set(t)):
        xb, xt = b.get(k), t.get(k)
        nb, nt = (xb.bars if xb else 0), (xt.bars if xt else 0)
        kb, kt = (xb.kg_net if xb else 0.0), (xt.kg_net if xt else 0.0)
        if nb == nt and abs(kt - kb) < 0.5:
            continue
        out.append((k[0], k[1], xb.stock_len if xb else 0, xt.stock_len if xt else 0, nb, nt, kt - kb))
    return out


def plate_deltas() -> list[tuple[str, float, tuple | None, int, int, float]]:
    """(재질, 사는 두께, 시트, 표준 매수, 옵션 매수, 순중량 차 kg) — 달라진 것만."""
    with pinned():
        t = {(x.mat, x.t): x for x in PR_T.plate_lots()}
    b = {(x.mat, x.t): x for x in PR_B.plate_lots()}
    out = []
    for k in sorted(set(b) | set(t)):
        xb, xt = b.get(k), t.get(k)
        nb, nt = (xb.sheets if xb else 0), (xt.sheets if xt else 0)
        kb, kt = (xb.kg_net if xb else 0.0), (xt.kg_net if xt else 0.0)
        if nb == nt and abs(kt - kb) < 0.5:
            continue
        out.append((k[0], k[1], (xt or xb).sheet, nb, nt, kt - kb))
    return out


def buy_deltas() -> list[tuple[object, int, int, tuple]]:
    """(옵션 부품, 표준 수량, 옵션 수량, 발주 사양) — 구매품 중 수량이 달라진 것."""
    b = {p.pid: p for p in PT_B.P if p.buy}
    out = []
    with pinned():
        for p in PT_T.P:
            if not p.buy:
                continue
            nb = b[p.pid].qty if p.pid in b else 0
            if nb != p.qty:
                out.append((p, nb, p.qty, PR_T.BUY_SPEC.get(p.pid)))
    return out


def trucks() -> tuple[list, list]:
    """(표준 차수, 옵션 차수)."""
    with pinned():
        t = PR_T.truck_loads()
    return PR_B.truck_loads(), t
