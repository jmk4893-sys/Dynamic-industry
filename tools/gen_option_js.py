"""옵션 DG-HK120C 도면 세트를 콘솔이 읽을 JS 블록으로 찍어낸다.

옵션 카탈로그는 따로 적지 않는다 — 변형 로더가 tools/parts.py 를 콘솔 HK120C 핀
(단수 7 · 램프 96 · 셀 2)으로 다시 푼 것이다(tools/option.py). 부하표도 같다:
tools/electrical.py 가 콘솔 E-001 식으로 옵션의 분기를 셀 수만큼 두어 푼 값이다.
콘솔은 이 블록을 **그리기만** 한다. 옵션의 합계·도번을 콘솔에서 다시 셈하면 식이
두 벌이 되고, 두 벌은 반드시 갈라진다.

    python3 tools/gen_option_js.py            # 표준출력으로 블록을 찍는다
    python3 tools/gen_option_js.py --write    # 콘솔 파일 안의 블록을 바꿔 넣는다

블록은 콘솔에서 아래 두 표지 사이에 산다 (부품 블록 바로 뒤):

    /* ⟨OPTION-DATA⟩ … */
    /* ⟨/OPTION-DATA⟩ */

담는 것:
  PART_MODULES_OPT  [모듈, 이름, 조립도 도번, 벌 수]  — 셀마다 서는 모듈은 벌 수 2
  PARTS_OPT         부품 — 표준 블록과 같은 필드 + no(도번) · u(셀당 수량, 셀별 부품만)
  PART_STEPS_OPT    모듈별 조립 순서
  LOAD_OPT          {rows: 분기표, sum: 연결부하·전부하전류·주차단기·변압기·단락전류}
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gen_parts_js as GP  # noqa: E402
import option as O  # noqa: E402

CONSOLE = GP.CONSOLE
OPEN = "/* ⟨OPTION-DATA⟩ tools/gen_option_js.py 가 찍는다 — 손으로 고치지 않는다 */"
CLOSE = "/* ⟨/OPTION-DATA⟩ */"


def _f(v: float) -> float:
    """전기 값은 여섯 자리까지 — 화면은 한 자리로 줄여 쓰지만 반올림을 두 번 겹치지 않게."""
    return round(float(v), 6)


def part_obj(p) -> dict:
    o = GP.part_obj(p)
    o["no"] = O.part_no(p)
    if O.PT_T.is_per_cell(p):
        o["u"] = O.PT_T.unit_qty(p)
    return o


def load_obj() -> dict:
    with O.pinned():
        rows = O.EL_T.branches()
        s = O.EL_T.summary(rows)
    return {
        "rows": [{"id": b.id, "base": b.base, "load": b.load, "kW": _f(b.kW), "pf": b.pf,
                  "df": b.df, "mccb": b.mccb} for b in rows],
        "sum": {"kw": _f(s["kw"]), "kvar": _f(s["kvar"]), "kva": _f(s["kva"]), "pf": _f(s["pf"]),
                "fla": _f(s["fla"]), "demand": s["demand"], "tr": int(s["tr_kva"]),
                "at": s["main_at"], "af": s["main_af"], "isc": [_f(x) for x in s["isc_ka"]],
                "sccr": s["sccr_ka"]},
    }


def block() -> str:
    pt = O.PT_T
    parts = [part_obj(p) for p in pt.P]
    mods = [[m, pt.MODULE_NAME[m], O.module_no(m), O.module_cells(m)] for m in pt.MODULES]
    steps = {m: [list(s) for s in pt.STEPS[m]] for m in pt.MODULES}
    j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    return "\n".join([
        OPEN,
        f"const PART_MODULES_OPT={j(mods)};",
        f"const PARTS_OPT={j(parts)};",
        f"const PART_STEPS_OPT={j(steps)};",
        f"const LOAD_OPT={j(load_obj())};",
        CLOSE,
    ])


def write() -> bool:
    src = CONSOLE.read_text(encoding="utf-8")
    new = block()
    if OPEN in src:
        i, k = src.index(OPEN), src.index(CLOSE) + len(CLOSE)
        if src[i:k] == new:
            return False
        out = src[:i] + new + src[k:]
    else:
        # 처음 한 번 — 부품 블록 바로 뒤에 자리를 낸다
        if GP.CLOSE not in src:
            raise SystemExit(f"콘솔에 {GP.CLOSE} 표지가 없다 — 넣을 자리를 못 찾았다")
        k = src.index(GP.CLOSE) + len(GP.CLOSE)
        out = src[:k] + "\n" + new + src[k:]
    CONSOLE.write_text(out, encoding="utf-8")
    return True


if __name__ == "__main__":
    if "--write" in sys.argv:
        print("콘솔 옵션 블록 갱신" if write() else "이미 같다 — 바꾸지 않았다")
    else:
        print(block())
