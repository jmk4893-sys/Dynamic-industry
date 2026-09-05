#!/usr/bin/env python3
"""콘솔 도면의 상수를 읽고, 도면에 적힌 식을 값으로 펼친다.

도면이 단수·램프 수를 상수 하나에서 파생시키기 시작하면서, 장치 이름도
제작도 치수도 부하표의 kW 도 더는 값이 아니라 식으로 적힌다.

    parts:[..., `캐리지 존재센서×${DECKS}`, ...]
    size:`5600×2600×${Math.round((HC_Z+.94)*1000)}`
    {id:'IR-DB1',load:`IR 램프 ${LAMPS}×2.5kW`,kW:LAMPS*2.5, ...}

그래야 단수를 한 곳에서 바꿀 수 있다. 대신 "이 장치가 도면에 있는가",
"표의 치수가 도면과 같은가" 를 문자열로 물을 수 없게 됐다. 여기서 도면의
상수를 모아 식을 풀어 두고 묻는다.

풀 수 없는 식은 손대지 않는다 — 억지로 펼치면 없는 장치를 있다고 답하게
된다. 그래서 이 모듈은 '모르면 그대로 둔다' 로 실패한다.
"""

from __future__ import annotations

import math
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


class _MATH:
    """도면이 쓰는 Math 중 숫자만 내는 것들."""

    round = staticmethod(lambda x: math.floor(x + 0.5))
    ceil = staticmethod(math.ceil)
    floor = staticmethod(math.floor)
    max = staticmethod(max)
    min = staticmethod(min)
    abs = staticmethod(abs)


def _split_top(body):
    """괄호 밖의 쉼표에서만 자른다 — `const A=1,B=f(2,3);` 를 두 쪽으로."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(body):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(body[start:i])
            start = i + 1
    out.append(body[start:])
    return out


def value(expr, env):
    """상수와 Math 몇 개만으로 된 식이면 그 값, 아니면 None."""
    expr = expr.strip()
    if not expr or not re.fullmatch(r"[\w.\s+\-*/()]+", expr):
        return None
    scope = dict(env)
    scope["Math"] = _MATH
    try:
        v = eval(expr, {"__builtins__": {}}, scope)       # noqa: S307 — 위 검사가 막는다
    except Exception:
        return None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def env(console):
    """콘솔의 숫자 상수를 이름→값으로 모은다.

    `const HC_Z=HC_Z0+HC_DZ*DECKS;` 처럼 다른 상수를 가리키는 것이 있어
    한 번에 다 풀리지 않는다. 더 풀리는 게 없을 때까지 돌린다 — 순환
    참조가 있으면 안 풀린 채로 남고, 그때는 펼치지 않는다.
    """
    pend = {}
    for body in re.findall(r"\bconst ([^;\n]+);", console):
        for part in _split_top(body):
            m = re.fullmatch(r"\s*([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*", part, re.S)
            if m:
                pend.setdefault(m.group(1), m.group(2))
    out = {}
    for _ in range(8):
        moved = False
        for name, rhs in list(pend.items()):
            v = value(rhs, out)
            if v is not None:
                out[name], moved = v, True
                del pend[name]
        if not moved:
            break
    return out


def _fmt(v):
    return str(int(v) if float(v).is_integer() else v)


def expand(console, extra=None):
    """콘솔의 ${...} 중 상수만으로 풀리는 것을 값으로 바꾼다."""
    scope = env(console)
    if extra:
        scope.update(extra)

    def sub(m):
        v = value(m.group(1), scope)
        return m.group(0) if v is None else _fmt(v)

    return re.sub(r"\$\{([^{}]*)\}", sub, console)


def text():
    """대조에 쓰는 콘솔 본문 — 식이 값으로 펼쳐진 것."""
    return expand(CONSOLE.read_text(encoding="utf-8"))


def const(name):
    """콘솔 상수 하나. 없으면 KeyError."""
    return env(CONSOLE.read_text(encoding="utf-8"))[name]
