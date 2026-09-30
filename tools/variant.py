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


def load(lid, *names):
    """배치 lid 로 names 모듈을 새로 불러 {이름: 모듈} 로 돌려준다."""
    design = _design_modules()
    saved = {n: sys.modules.pop(n) for n in design if n in sys.modules}
    got = {}
    try:
        with C.layout(lid):
            for n in names:
                got[n] = importlib.import_module(n)
    finally:
        for n in design:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
    return got


@contextlib.contextmanager
def pinned(lid):
    """옵션 모듈의 함수를 부르는 동안 그 배치의 핀을 유지한다."""
    with C.layout(lid) as fields:
        yield fields
