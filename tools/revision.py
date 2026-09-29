# -*- coding: utf-8 -*-
"""지금 개정 번호 — README 의 개정 절에서 읽는다.

발행 페이지의 스탬프에 개정을 **손으로 적어 두면** 개정마다 어긋난다. 실제로
어긋났다: 계단 칼날 개정(REV.59)으로 도면을 다시 찍고 영상도 다시 찍었는데,
도면집 영상 페이지는 REV.57, 순회 영상 페이지는 REV.58 을 그대로 달고 있었다.
영상 옆에 적힌 값이 영상과 다른 데서 올 수 없다는 규칙은 개정 번호에도 걸린다.
"""
from __future__ import annotations

import pathlib
import re

#: 개정 절의 머리 — `#### §67 … (REV.59)`
_HEAD = re.compile(r"^#### §\d+ .*\(REV\.(\d+)\)", re.M)


def current(readme: pathlib.Path | None = None) -> str:
    """`REV.N` — README 가 가진 개정 가운데 가장 큰 것.

    절은 새것이 위에 오지만 **순서로 집으면 안 된다** — 앞쪽에 옛 절(§48)이 하나
    끼어 있어 첫 일치가 REV.47 이 된다. 가장 큰 값이 지금 개정이다.
    """
    path = readme or pathlib.Path("README.md")
    revs = [int(r) for r in _HEAD.findall(path.read_text(encoding="utf-8"))]
    if not revs:
        raise SystemExit(f"{path} 에서 개정 절(#### §N … (REV.M))을 못 읽었다")
    return f"REV.{max(revs)}"
