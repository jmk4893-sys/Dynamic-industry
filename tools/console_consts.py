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
    # 쉼표는 Math.max(a,b) 의 인수 구분이다 — env() 가 괄호 밖 쉼표에서만
    # 자르므로 여기까지 온 쉼표는 전부 괄호 안이다.
    if not expr or not re.fullmatch(r"[\w.\s+\-*/(),]+", expr):
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
        if "CST" not in out:
            cst = _stations(console, out)
            if cst is not None:
                out["CST"], moved = cst, True
        if not moved:
            break
    return out


class _NS:
    """`CST.DL.x0` 처럼 점으로 파고드는 도면 객체의 대역."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _stations(console, scope):
    """압축 배치의 스테이션 좌표 — 콘솔의 CST 와 같은 식으로 잇는다.

    도면은 `COMPACT_STATIONS` 의 폭을 CL_END 부터 CL_CLEAR 간격으로 이어
    x0·cx·x1 을 만든다. 테이블 중심·레일·컨베이어가 전부 여기서 나오므로
    이 사슬을 못 풀면 그 뒤의 상수도 못 푼다.
    """
    m = re.search(r"const COMPACT_STATIONS=\[(.*?)\n\s*\];", console, re.S)
    if m is None or not {"CL_END", "CL_CLEAR"} <= scope.keys():
        return None
    rows = re.findall(r"\['([A-Z]{2})[^']*',[^,]*,\s*([^,]+),", m.group(1))
    if not rows:
        return None
    cur, out = scope["CL_END"], {}
    for key, expr in rows:
        w = value(expr, scope)
        if w is None:
            return None
        out[key] = _NS(x0=cur, w=w, cx=cur + w / 2, x1=cur + w)
        cur += w + scope["CL_CLEAR"]
    return _NS(**out)


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


def _object_body(console, name):
    """`const NAME={ ... };` 의 중괄호 안을 중괄호 균형으로 잘라 낸다."""
    m = re.search(r"\bconst %s\s*=\s*\{" % re.escape(name), console)
    if m is None:
        raise KeyError(name)
    i = console.index("{", m.start())
    depth = 0
    for k in range(i, len(console)):
        if console[k] == "{":
            depth += 1
        elif console[k] == "}":
            depth -= 1
            if depth == 0:
                return console[i + 1:k]
    raise KeyError(name)


def obj(name, console=None):
    """설정 객체 하나를 이름→값으로 편다.

    배치 상수가 낱개 const 에서 객체로 옮겨 가면서(R20 · CST) 시험이 값을
    물을 데가 없어졌다. 숫자와 숫자 배열만 편다 — 함수나 문자열은 두고
    간다. 모르면 그대로 두는 이 모듈의 규칙은 여기서도 같다.
    """
    console = CONSOLE.read_text(encoding="utf-8") if console is None else console
    scope = env(console)
    # 주석을 먼저 걷어 낸다 — 주석 안의 쉼표("y +2,900")가 필드 경계로 읽힌다
    body = _object_body(console, name)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    out = {}
    for part in _split_top(body):
        part = part.strip()
        m = re.fullmatch(r"([A-Za-z_][\w]*)\s*:\s*(.+)", part, re.S)
        if not m:
            continue
        key, rhs = m.group(1), m.group(2).strip()
        if rhs.startswith("[") and rhs.endswith("]"):
            items = [value(x, scope) for x in _split_top(rhs[1:-1])]
            if items and all(v is not None for v in items):
                out[key] = items
            continue
        v = value(rhs, scope)
        if v is not None:
            out[key] = v
    return out


def inline(text, *names):
    """`R20.railCx` 같은 객체 참조를 값으로 바꾼다.

    배치 좌표가 낱개 const 에서 객체로 옮겨 가면 도면·3D 는 함께 움직이지만
    소스를 글자로 읽던 시험은 눈이 먼다. 값으로 펼쳐 주면 시험은 하던 대로
    좌표를 물을 수 있고, 소스는 한 곳에서만 좌표를 든다.
    """
    console = CONSOLE.read_text(encoding="utf-8")
    for name in names or ("R20",):
        try:
            fields = obj(name, console)
        except KeyError:
            continue
        for key, v in sorted(fields.items(), key=lambda kv: -len(kv[0])):
            if isinstance(v, list):
                # 배열은 첨자까지 함께 편다 — R20.dockX[1] 도 좌표다
                for i, item in enumerate(v):
                    text = text.replace(f"{name}.{key}[{i}]", _fmt(item))
                continue
            text = text.replace(f"{name}.{key}", _fmt(v))
    return text


def const(name):
    """콘솔 상수 하나. `R20.railCx` 처럼 객체 필드도 받는다. 없으면 KeyError."""
    console = CONSOLE.read_text(encoding="utf-8")
    if "." in name:
        owner, key = name.split(".", 1)
        return obj(owner, console)[key]
    return env(console)[name]
