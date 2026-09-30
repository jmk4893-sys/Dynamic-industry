"""배치 계열 하나(표준 DG-HK60C · 옵션 DG-HK120C)로 설계 모듈을 따로 불러온다.

카탈로그·조달·지침서·해석은 전부 모듈을 부를 때 콘솔 상수를 읽어 값을
정한다. 옵션을 같은 코드로 내려면 그 모듈들을 옵션의 뿌리 값(단수·램프 수·
셀 수)을 핀으로 박은 채 **새로** 실행해야 한다 — 이미 불린 표준 모듈을 그대로
쓰면 7 단 콘솔에 5 단 카탈로그가 붙는다.

    tw = variant.load("twin", "parts", "procure")
    with variant.pinned("twin"):
        lots = tw["procure"].plate_lots()

부른 옵션 모듈은 서로를 옵션으로 가리킨다(procure 안의 PT 가 옵션 카탈로그).
부르는 동안 빼 두었던 표준 모듈은 끝나면 그대로 되돌린다 — 표준 쪽 결과는
이 모듈을 쓰든 안 쓰든 한 글자도 달라지지 않는다.

옵션 모듈의 함수가 부를 때 다시 상수를 읽는 경우가 있으므로, 옵션 모듈을
쓰는 동안에는 pinned() 안에 있어야 한다.

pinned() 는 핀만 쥐는 것이 아니라 **그 배치의 모듈 목록**을 sys.modules 에 올린다.
설계 모듈 몇은 함수 안에서 늦게 부른다(analysis_thermal → heatbalance · irbank,
airlock → heatbalance, analysis_structural → glass_follow). 핀만 쥐면 그 import 가
둘 중 하나로 틀렸다 — 표준 모듈이 이미 있으면 옵션 계산이 표준 열수지를 집고,
없으면 옵션 핀 아래에서 처음 불린 모듈이 sys.modules 에 남아 **그 뒤의 표준 계산이
옵션 값을 읽었다** (에어록 전고 개구 673 kW 가 1,178 kW 로 바뀐 채 시험에 걸렸다).
부르는 순서에 따라 결과가 달라지는 것이다. 그래서 핀 안에서는 옵션 목록만 보이고,
핀 안에서 새로 불린 모듈은 옵션 목록으로 거두고, 나올 때 표준 목록을 되돌린다.
"""

from __future__ import annotations

import contextlib
import importlib
import pathlib
import sys

import console_consts as C

HERE = pathlib.Path(__file__).resolve().parent

# 핀을 쥔 모듈과 이 모듈은 다시 부르지 않는다 — 다시 부르면 핀이 사라진다.
_KEEP = {"console_consts", "variant"}


def _design_modules():
    """tools/ 의 설계 모듈 이름 — 콘솔 상수를 읽을 수 있는 것 전부."""
    return sorted(p.stem for p in HERE.glob("*.py") if p.stem not in _KEEP)


# 배치마다 핀 아래에서 풀린 설계 모듈 — load() 가 채우고 pinned() 가 올린다.
_REG: dict[str, dict] = {}


def load(lid, *names):
    """배치 lid 로 names 모듈을 새로 불러 {이름: 모듈} 로 돌려준다."""
    design = _design_modules()
    saved = {n: sys.modules.pop(n) for n in design if n in sys.modules}
    got = {}
    try:
        with C.layout(lid):
            for n in names:
                got[n] = importlib.import_module(n)
            fresh = {n: sys.modules[n] for n in design if n in sys.modules}
    finally:
        for n in design:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
    _REG.setdefault(lid, {}).update(fresh)
    return got


@contextlib.contextmanager
def pinned(lid):
    """옵션 모듈의 함수를 부르는 동안 그 배치의 핀과 모듈 목록을 쥔다."""
    design = _design_modules()
    reg = _REG.setdefault(lid, {})
    saved = {n: sys.modules.pop(n) for n in design if n in sys.modules}
    sys.modules.update(reg)
    try:
        with C.layout(lid) as fields:
            yield fields
    finally:
        for n in design:
            m = sys.modules.pop(n, None)
            if m is not None:
                reg[n] = m              # 핀 아래에서 풀린 것은 이 배치의 것이다
        sys.modules.update(saved)
