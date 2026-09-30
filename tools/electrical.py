"""전기 부하표 E-001 — 콘솔 LOAD_SCHEDULE 의 거울과 옵션(2셀) 부하표.

표준은 콘솔 표를 그대로 푼다 (분기 · kW · 역률 · 수용률 · 분기 차단기). 주차단기·
변압기·단락전류를 고르는 규칙도 콘솔과 같다 — tests/test_electrical 이 콘솔 식을
node 로 돌려 표준의 값을 대조한다.

옵션 DG-HK120C 는 **분기를 셀 수만큼 둔다** (총괄 결정). 가열실은 하나지만 램프가
두 배(96 등)이므로 IR 분기도 뱅크 절반씩 둘이고, 칼날 히터·서보·보조 분기도 셀마다
선다. 분기 차단기 정격은 표준 그대로 두고 주회로·변압기만 다시 고른다 — 한 분기
IR-DB1 4P 200A 에 96 등 240 kW(365 A)를 걸 수 없기 때문이다. 서보·VFD 와 보조
분기를 통째로 곱하는 것은 보수적이다: 공용인 LI·GU 포크와 셔틀 몫이 두 번 세지는
대신, 표준에 없던 EX·GL 횡이송 8 축과 둘째 갠트리가 그 몫을 먹는다. 실제 수치는
상세설계의 부하 목록으로 확정한다.
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple

import console_consts as CC


class Branch(NamedTuple):
    id: str
    load: str
    kW: float
    pf: float
    df: float
    mccb: str

    @property
    def amp(self) -> float:
        return self.kW * 1000 / (math.sqrt(3) * LINE_V * self.pf)


def _console() -> str:
    return CC.CONSOLE.read_text(encoding="utf-8")


def _num_list(src: str, name: str) -> list[float]:
    m = re.search(r"const %s=\[([^\]]*)\]" % re.escape(name), src)
    if m is None:
        raise KeyError(name)
    return [float(x) for x in m.group(1).split(",")]


_SRC = _console()
LINE_V = CC.const("LINE_V")
TR_STD = _num_list(_SRC, "TR_STD")
AT_STD = _num_list(_SRC, "AT_STD")
TR_Z = _num_list(_SRC, "TR_Z")
SCCR_STD = _num_list(_SRC, "SCCR_STD")
# 주차단기 프레임은 콘솔 식 안의 목록이다 (const MAIN_AF=[...].find(...))
AF_STD = [float(x) for x in re.search(r"const MAIN_AF=\[([^\]]*)\]", _SRC).group(1).split(",")]
TR_LOAD_MAX = 0.80        # 콘솔 TR_KVA — 부하율 80 % 안의 최소 용량
AT_MARGIN = 1.25          # 콘솔 MAIN_AT — FLA 의 1.25 배 위 표준 정격
SCCR_MARGIN = 1.2         # 콘솔 SCCR_KA — 예상 단락전류 상한의 1.2 배 위


def base_branches() -> list[Branch]:
    """콘솔 LOAD_SCHEDULE 를 **표준 배치의 값**으로 푼다 — 옵션 핀과 무관하다."""
    body = re.search(r"const LOAD_SCHEDULE=\[(.*?)\n\s*\];", _SRC, re.S).group(1)
    with CC.layout("compact"):
        scope = CC.env(_SRC)
    out = []
    for row in re.findall(r"\{(id:.*?)\}\s*,?\s*$", body, re.M):
        load = re.search(r"load:(?:'([^']*)'|`([^`]*)`)", row)
        load = load.group(1) if load.group(1) is not None else load.group(2)
        load = re.sub(r"\$\{([^{}]*)\}", lambda m: CC._fmt(CC.value(m.group(1), scope)), load)
        kw = CC.value(re.search(r"kW:([^,]+),", row).group(1), scope)
        out.append(Branch(re.search(r"id:'([^']+)'", row).group(1), load, float(kw),
                          float(re.search(r"pf:([\d.]+)", row).group(1)),
                          float(re.search(r"df:([\d.]+)", row).group(1)),
                          re.search(r"mccb:'([^']+)'", row).group(1)))
    return out


# 옵션에서 분기를 둘로 나눌 때 붙이는 이름. IR 은 셀이 아니라 뱅크를 가른다 —
# 가열실은 하나이고 뱅크 여덟을 넷씩 나눠 받는다.
def _split_name(b: Branch, k: int, cells: int) -> tuple[str, str]:
    if b.id.startswith("IR-"):
        banks = int(CC.const("DECKS")) + 1
        per = banks // cells
        return f"IR-DB{k + 1}", f"{b.load} · 뱅크 {k * per + 1}~{(k + 1) * per}"
    tag = "AB"[k] if cells <= 2 else str(k + 1)
    return f"{b.id}-{tag}", f"{b.load} · 셀 {tag}"


def branches() -> list[Branch]:
    """활성 배치의 분기표. 표준은 콘솔 표 그대로, 옵션은 분기를 셀 수만큼 둔다."""
    base = base_branches()
    cells = int(CC.const("CELLS"))
    if cells == 1:
        return base
    out = []
    for b in base:
        for k in range(cells):
            i, load = _split_name(b, k, cells)
            out.append(b._replace(id=i, load=load))
    return out


def summary(rows: list[Branch] | None = None) -> dict:
    """연결부하 · 피상전력 · 전부하전류 · 주차단기 · 변압기 · 단락전류 — 콘솔 E-001 과 같은 식."""
    rows = branches() if rows is None else rows
    kw = sum(b.kW for b in rows)
    kvar = sum(b.kW * math.tan(math.acos(b.pf)) for b in rows)
    kva = math.hypot(kw, kvar)
    fla = kva * 1000 / (math.sqrt(3) * LINE_V)
    tr = next((v for v in TR_STD if kva / v <= TR_LOAD_MAX), TR_STD[-1])
    at = next((v for v in AT_STD if v >= fla * AT_MARGIN), AT_STD[-1])
    af = next((v for v in AF_STD if v >= at), AF_STD[-1])
    isc = [tr * 1000 / (math.sqrt(3) * LINE_V) / z / 1000 for z in TR_Z][::-1]
    sccr = next((v for v in SCCR_STD if v >= isc[1] * SCCR_MARGIN), SCCR_STD[-1])
    return dict(kw=kw, kvar=kvar, kva=kva, pf=kw / kva, fla=fla,
                demand=round(sum(b.kW * b.df for b in rows)),
                tr_kva=tr, tr_load=kva / tr, main_at=int(at), main_af=int(af),
                headroom=at / fla, isc_ka=isc, sccr_ka=int(sccr), branches=len(rows))
