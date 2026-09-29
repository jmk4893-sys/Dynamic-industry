"""부품 카탈로그를 콘솔이 읽을 JS 블록으로 찍어낸다.

카탈로그의 원본은 tools/parts.py 하나다. 콘솔이 같은 표를 손으로 들고 있으면
반드시 갈라지므로 — 이 저장소가 도면과 3D 로 이미 겪은 실패다 — 여기서
기계적으로 찍어내고, 시험이 콘솔 안의 블록을 이 출력과 대조한다.

    python3 tools/gen_parts_js.py            # 표준출력으로 블록을 찍는다
    python3 tools/gen_parts_js.py --write    # 콘솔 파일 안의 블록을 바꿔 넣는다

블록은 콘솔에서 아래 두 표지 사이에 산다:

    /* ⟨PARTS-DATA⟩ … */
    /* ⟨/PARTS-DATA⟩ */
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import parts as PT  # noqa: E402

CONSOLE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "pv-delamination-3d.html"
OPEN = "/* ⟨PARTS-DATA⟩ tools/gen_parts_js.py 가 찍는다 — 손으로 고치지 않는다 */"
CLOSE = "/* ⟨/PARTS-DATA⟩ */"


def _num(v: float) -> float:
    """도면이 쓰는 자리수까지만 — 부동소수 꼬리가 파일 차이를 만들지 않게."""
    return round(v, 3)


def part_obj(p: PT.Part) -> dict:
    d = {k: (tuple(v) if isinstance(v, tuple) else v) for k, v in p.shape.d.items()}
    d.pop("name", None)
    g = {k: (_num(v) if isinstance(v, (int, float)) else v) for k, v in d.items()}
    return {
        "id": p.pid, "m": p.mod, "n": p.name, "k": p.shape.kind, "g": g,
        "mat": p.mat, "fin": p.finish, "q": p.qty, "fix": p.fix,
        "note": p.note, "st": p.step, "kg": _num(p.kg), "lbl": p.shape.label(),
    }


def block() -> str:
    parts = [part_obj(p) for p in PT.P]
    mods = [[m, PT.MODULE_NAME[m]] for m in PT.MODULES]
    steps = {m: [list(s) for s in PT.STEPS[m]] for m in PT.MODULES}
    j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    return "\n".join([
        OPEN,
        f"const PART_MODULES={j(mods)};",
        f"const PARTS={j(parts)};",
        f"const PART_STEPS={j(steps)};",
        CLOSE,
    ])


def write() -> bool:
    src = CONSOLE.read_text(encoding="utf-8")
    new = block()
    if OPEN not in src:
        raise SystemExit(f"콘솔에 {OPEN} 표지가 없다 — 넣을 자리를 못 찾았다")
    i, k = src.index(OPEN), src.index(CLOSE) + len(CLOSE)
    if src[i:k] == new:
        return False
    CONSOLE.write_text(src[:i] + new + src[k:], encoding="utf-8")
    return True


if __name__ == "__main__":
    if "--write" in sys.argv:
        print("콘솔 블록 갱신" if write() else "이미 같다 — 바꾸지 않았다")
    else:
        print(block())
