"""도면 시트의 글자 배치를 기계로 보는 보조 도구.

A3 시트는 코드가 좌표를 찍는다. 치수 하나를 고치면 글 길이가 따라 변하므로,
어느 장에서 무엇이 프레임 밖으로 나갔고 무엇이 무엇 위에 앉았는지는 46 장을
일일이 띄워 보기 전에는 알 수 없다. 제작도면과 부품도 두 시험이 같은 눈으로
보도록 여기에 모은다.

글자 폭은 ``_mp50_draft.text_width`` 로 재고 이 값은 실측 대비 ±8 % 쯤 틀리므로,
닿기만 한 것을 겹쳤다고 하지 않도록 여유를 준다. 세로로 세운 치수 글씨는
좌표계가 달라 제외한다 — ``transform`` 이 붙은 글자가 그것이다.
"""

from __future__ import annotations

import html as _html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

from _mp50_draft import Canvas, text_width  # noqa: E402


def _canvas_frames() -> tuple[tuple[float, ...], tuple[float, ...]]:
    """프레임과 표제란의 칸을 ``Canvas`` 에서 직접 받아온다.

    여기에 숫자를 베껴 두면 여백을 고쳤을 때 시험만 옛 자리를 본다.
    """
    c = Canvas("", "", "", "", "")
    c.frame_and_title("", "", "")
    tx, ty, tw, th = c.title_block
    return ((Canvas.MARGIN_L, Canvas.MARGIN,
             Canvas.WIDTH - Canvas.MARGIN, Canvas.HEIGHT - Canvas.MARGIN),
            (tx, ty, tx + tw, ty + th))


FRAME, TITLE_BLOCK = _canvas_frames()

_TEXT = re.compile(r'<text x="(-?[\d.]+)" y="(-?[\d.]+)" font-size="([\d.]+)" '
                   r'text-anchor="(\w+)"([^>]*)>(.*?)</text>', re.S)
_TITLE_GROUP = re.compile(r'<g class="tb">.*?</g>', re.S)
_SHEET = re.compile(r'<figure class="sheet" id="([^"]+)">(.*?)</figure>', re.S)


def sheets(html: str) -> list[tuple[str, str]]:
    """생성된 문서에서 (도면번호, SVG) 를 뽑는다."""
    return _SHEET.findall(html)


def text_boxes(svg: str) -> list[tuple[float, float, float, float, str]]:
    """글자마다 (x0, y0, x1, y1, 내용). 표제란 안의 글과 세운 글씨는 뺀다."""
    out = []
    for x, y, size, anchor, attrs, body in _TEXT.findall(_TITLE_GROUP.sub("", svg)):
        if "transform" in attrs:
            continue
        x, y, size = float(x), float(y), float(size)
        txt = _html.unescape(re.sub(r"<[^>]+>", "", body))
        if not txt.strip():
            continue
        w = text_width(txt, size, bold=('weight="6' in attrs or 'weight="7' in attrs))
        x0 = x if anchor == "start" else (x - w / 2 if anchor == "middle" else x - w)
        out.append((x0, y - size * 0.74, x0 + w, y + size * 0.20, txt))
    return out


def off_frame(html: str) -> list[str]:
    """프레임 밖으로 나갔거나 표제란을 덮은 글자."""
    fx0, fy0, fx1, fy1 = FRAME
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    bad = []
    for number, svg in sheets(html):
        for x0, y0, x1, y1, txt in text_boxes(svg):
            if x0 < fx0 or x1 > fx1 or y0 < fy0 or y1 > fy1:
                bad.append(f"{number} 프레임 밖: {txt[:36]!r}")
            elif x1 > tx0 and x0 < tx1 and y1 > ty0 and y0 < ty1:
                bad.append(f"{number} 표제란 위: {txt[:36]!r}")
    return bad


def overlaps(html: str, slack: float = 0.6) -> list[str]:
    """서로 올라탄 글자 쌍. ``slack`` 은 폭 추정 오차만큼의 여유 (mm)."""
    bad = []
    for number, svg in sheets(html):
        b = text_boxes(svg)
        for i in range(len(b)):
            for j in range(i + 1, len(b)):
                a, d = b[i], b[j]
                if (min(a[2], d[2]) - max(a[0], d[0]) > slack
                        and min(a[3], d[3]) - max(a[1], d[1]) > slack):
                    bad.append(f"{number}: {a[4][:28]!r} ↔ {d[4][:28]!r}")
    return bad
