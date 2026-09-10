"""제도 프리미티브 — ISO 128 / ISO 129 관행에 맞춘 SVG 생성기.

용지 좌표는 **mm** 다. viewBox 를 A3(420 × 297)로 잡아 두었으므로 여기서
`3.5` 라고 쓰면 실제 인쇄물에서 3.5 mm 글자가 된다. 모델 좌표(장치의 mm)는
``View`` 가 축척을 걸어 용지 좌표로 옮긴다.

선 굵기는 ISO 128 의 세 계열만 쓴다.

* ``0.25``  치수선 · 중심선 · 해칭 (가는선)
* ``0.35``  숨은선
* ``0.50``  외형선 (굵은선)
* ``0.70``  단면 절단면 · 도면 테두리

축척을 걸어도 선 굵기와 글자 크기는 변하면 안 되므로 `<g transform=scale>` 을
쓰지 않고 파이썬에서 좌표를 계산해 절대값으로 찍는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- 선 굵기 (mm) ---
THIN = 0.25
HIDDEN_W = 0.35
THICK = 0.5
FRAME = 0.7

# --- 글자 높이 (mm) ---
T_DIM = 2.4      # 치수 · 부품표
T_NOTE = 2.7     # 지시선 · 주기
T_LABEL = 3.5    # 부품명
T_VIEW = 4.6     # 뷰 제목
T_TITLE = 6.5    # 표제란 도면명

ARROW = 3.0      # 화살표 길이
GAP = 1.0        # 치수보조선과 물체 사이 틈
OVER = 2.0       # 치수보조선 내밀기


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text_width(s: str, size: float) -> float:
    """글자열의 대략 폭 (mm).

    한글·한자는 전각이라 글자당 폭이 글자높이와 거의 같고, 라틴은 그 절반쯤이다.
    둘을 같게 보면 한글 제목마다 밑줄과 옆 글자가 어긋난다.
    """
    units = 0.0
    for ch in str(s):
        units += 1.0 if ord(ch) > 0x2E80 else 0.54
    return units * size


def fmt(value: float, digits: int = 0) -> str:
    """치수값 표기 — 정수로 떨어지면 소수점을 붙이지 않는다."""
    if digits == 0 or abs(value - round(value)) < 5e-4:
        return f"{value:.0f}"
    return f"{value:.{digits}f}"


class Canvas:
    """한 장의 도면. SVG 조각을 순서대로 쌓는다."""

    WIDTH = 420.0
    HEIGHT = 297.0
    MARGIN_L = 10.0
    MARGIN = 5.0

    def __init__(self, number: str, title: str, subtitle: str, scale: str, aria: str):
        self.number = number
        self.title = title
        self.subtitle = subtitle
        self.scale = scale
        self.aria = aria
        self.body: list[str] = []
        self._defs: list[str] = []
        self._def_ids: set[str] = set()

    # -- 원시 --
    def add(self, markup: str) -> None:
        self.body.append(markup)

    def defn(self, ident: str, markup: str) -> None:
        if ident not in self._def_ids:
            self._def_ids.add(ident)
            self._defs.append(markup)

    # -- 기본 도형 --
    def line(self, x1: float, y1: float, x2: float, y2: float,
             w: float = THICK, cls: str = "ln", dash: str = "") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                 f'class="{cls}" stroke-width="{w}"{d}/>')

    def poly(self, pts: list[tuple[float, float]], w: float = THICK,
             cls: str = "ln", close: bool = False, fill: str = "none", dash: str = "") -> None:
        d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + ("Z" if close else "")
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<path d="{d}" class="{cls}" stroke-width="{w}" fill="{fill}"{da}/>')

    def rect(self, x: float, y: float, w: float, h: float, sw: float = THICK,
             cls: str = "ln", fill: str = "none", rx: float = 0, dash: str = "") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
                 f'rx="{rx}" class="{cls}" stroke-width="{sw}" fill="{fill}"{d}/>')

    def circle(self, cx: float, cy: float, r: float, sw: float = THICK,
               cls: str = "ln", fill: str = "none", dash: str = "") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" '
                 f'class="{cls}" stroke-width="{sw}" fill="{fill}"{d}/>')

    def arc(self, cx: float, cy: float, r: float, a0: float, a1: float,
            sw: float = THICK, cls: str = "ln", fill: str = "none") -> None:
        x0, y0 = cx + r * math.cos(math.radians(a0)), cy - r * math.sin(math.radians(a0))
        x1, y1 = cx + r * math.cos(math.radians(a1)), cy - r * math.sin(math.radians(a1))
        large = 1 if abs(a1 - a0) > 180 else 0
        sweep = 0 if a1 > a0 else 1
        self.add(f'<path d="M{x0:.2f},{y0:.2f} A{r:.2f},{r:.2f} 0 {large} {sweep} {x1:.2f},{y1:.2f}" '
                 f'class="{cls}" stroke-width="{sw}" fill="{fill}"/>')

    def text(self, x: float, y: float, s: str, size: float = T_DIM,
             anchor: str = "middle", cls: str = "tx", weight: str = "",
             rotate: float = 0.0, mono: bool = False) -> None:
        tr = f' transform="rotate({rotate:.1f} {x:.2f} {y:.2f})"' if rotate else ""
        fw = f' font-weight="{weight}"' if weight else ""
        fam = ' class="tx mono"' if mono else f' class="{cls}"'
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" '
                 f'text-anchor="{anchor}"{fw}{fam}{tr}>{esc(s)}</text>')

    # -- 제도 요소 --
    def centreline(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.line(x1, y1, x2, y2, THIN, "cl", dash="6 1.2 1.2 1.2")

    def hidden(self, pts: list[tuple[float, float]], close: bool = False) -> None:
        self.poly(pts, HIDDEN_W, "ln", close=close, dash="2.4 1.2")

    def _arrow(self, x: float, y: float, angle: float) -> None:
        """채운 화살촉. angle 은 촉이 향하는 방향(도)."""
        a = math.radians(angle)
        bx, by = x - ARROW * math.cos(a), y + ARROW * math.sin(a)
        h = ARROW * 0.16
        px, py = -math.sin(a) * h, -math.cos(a) * h
        self.add(f'<path d="M{x:.2f},{y:.2f} L{bx + px:.2f},{by + py:.2f} '
                 f'L{bx - px:.2f},{by - py:.2f}Z" class="fill-ink"/>')

    def dim_h(self, x1: float, x2: float, y: float, label: str,
              ext_from: float | None = None, size: float = T_DIM, above: bool = True) -> None:
        """수평 치수. ``ext_from`` 은 치수보조선이 시작되는 물체 쪽 y."""
        if x2 < x1:
            x1, x2 = x2, x1
        if ext_from is not None:
            s = 1 if y > ext_from else -1
            for x in (x1, x2):
                self.line(x, ext_from + s * GAP, x, y + s * OVER, THIN, "dl")
        self.line(x1, y, x2, y, THIN, "dl")
        if x2 - x1 > 3 * ARROW:
            self._arrow(x1, y, 180)
            self._arrow(x2, y, 0)
        else:  # 좁으면 화살표를 밖으로 뺀다
            self._arrow(x1, y, 0)
            self._arrow(x2, y, 180)
            self.line(x1 - ARROW * 1.6, y, x1, y, THIN, "dl")
            self.line(x2, y, x2 + ARROW * 1.6, y, THIN, "dl")
        dy = -1.0 if above else size + 0.4
        self.text((x1 + x2) / 2, y + dy, label, size, "middle", "tx", mono=True)

    def dim_v(self, y1: float, y2: float, x: float, label: str,
              ext_from: float | None = None, size: float = T_DIM, left: bool = True) -> None:
        """수직 치수. 글자는 치수선을 따라 90° 회전한다 (ISO 129)."""
        if y2 < y1:
            y1, y2 = y2, y1
        if ext_from is not None:
            s = 1 if x > ext_from else -1
            for y in (y1, y2):
                self.line(ext_from + s * GAP, y, x + s * OVER, y, THIN, "dl")
        self.line(x, y1, x, y2, THIN, "dl")
        if y2 - y1 > 3 * ARROW:
            self._arrow(x, y1, 90)
            self._arrow(x, y2, 270)
        else:
            self._arrow(x, y1, 270)
            self._arrow(x, y2, 90)
            self.line(x, y1 - ARROW * 1.6, x, y1, THIN, "dl")
            self.line(x, y2, x, y2 + ARROW * 1.6, THIN, "dl")
        dx = -1.2 if left else size + 0.2
        self.text(x + dx, (y1 + y2) / 2, label, size, "middle", "tx", rotate=-90, mono=True)

    def leader(self, tx: float, ty: float, x: float, y: float, label: str,
               anchor: str = "start", size: float = T_NOTE, dot: bool = True,
               lines: tuple[str, ...] = ()) -> None:
        """지시선 — (tx,ty) 를 가리키고 (x,y) 에서 수평으로 꺾어 글자를 단다."""
        kink = x - 3.2 if anchor == "start" else x + 3.2
        self.poly([(tx, ty), (kink, y), (x, y)], THIN, "dl")
        if dot:
            self.circle(tx, ty, 0.5, 0, "fill-ink", fill="currentColor")
        self.text(x + (0.8 if anchor == "start" else -0.8), y - 0.9, label, size, anchor)
        for i, extra in enumerate(lines):
            self.text(x + (0.8 if anchor == "start" else -0.8), y - 0.9 + (i + 1) * (size + 0.5),
                      extra, size - 0.3, anchor, "tx2")

    def balloon(self, x: float, y: float, no: str, tx: float, ty: float, r: float = 3.4) -> None:
        """부품 풍선 — 부품표의 번호와 도면을 잇는다."""
        ang = math.atan2(y - ty, x - tx)
        self.line(tx, ty, x - r * math.cos(ang), y - r * math.sin(ang), THIN, "dl")
        self.circle(tx, ty, 0.55, 0, "fill-ink", fill="currentColor")
        self.circle(x, y, r, THIN, "ln", fill="var(--paper)")
        self.text(x, y + 1.15, no, T_DIM + 0.2, "middle", "tx", weight="600")

    def ordinate_v(self, x: float, y: float, anchor_x: float, label: str,
                   size: float = T_DIM) -> None:
        """세로 좌표치수 — 기준선에서 재는 표고 하나.

        표고가 촘촘한 용기에서 사슬치수를 쓰면 15 mm 간격의 치수값이 서로
        겹쳐 읽을 수 없다. 좌표치수는 값이 한 줄에 하나씩 놓이므로 겹치지 않는다.
        """
        self.line(anchor_x, y, x, y, THIN, "dl")
        self._arrow(x, y, 180)
        self.text(x + 1.6, y - 0.8, label, size, "start", "tx", mono=True)

    def hatch(self, pts: list[tuple[float, float]], ident: str = "h45", angle: int = 45,
              pitch: float = 2.2) -> None:
        """단면 해칭. 같은 부품은 같은 각도로 칠해야 한 몸으로 읽힌다."""
        self.defn(ident,
                  f'<pattern id="{ident}" width="{pitch}" height="{pitch}" '
                  f'patternUnits="userSpaceOnUse" patternTransform="rotate({angle})">'
                  f'<line x1="0" y1="0" x2="0" y2="{pitch}" class="ln" stroke-width="{THIN * 0.7}"/>'
                  f"</pattern>")
        d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + "Z"
        self.add(f'<path d="{d}" fill="url(#{ident})" stroke="none"/>')

    def fill(self, pts: list[tuple[float, float]], colour: str, alpha: float = 1.0) -> None:
        d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + "Z"
        self.add(f'<path d="{d}" fill="{colour}" fill-opacity="{alpha}" stroke="none"/>')

    def weld(self, x: float, y: float, tx: float, ty: float, symbol: str, note: str = "",
             both: bool = False) -> None:
        """용접기호 (ISO 2553 약식). 기준선 위/아래에 기호와 주기를 단다."""
        self.poly([(tx, ty), (x - 5, y), (x + 17, y)], THIN, "dl")
        self.text(x - 4.2, y - 1.2, symbol, T_NOTE, "start", "tx", weight="600")
        if both:
            self.text(x - 4.2, y + T_NOTE + 0.4, symbol, T_NOTE, "start", "tx", weight="600")
        if note:
            self.text(x + 17.5, y - 1.2, note, T_DIM - 0.1, "start", "tx2")

    def section_arrow(self, x: float, y: float, angle: float, label: str) -> None:
        """단면 화살표 — 절단선 끝에서 보는 방향."""
        a = math.radians(angle)
        self.line(x, y, x + 6 * math.cos(a), y - 6 * math.sin(a), FRAME, "ln")
        self._arrow(x + 6 * math.cos(a), y - 6 * math.sin(a), angle)
        self.text(x - 3.4 * math.cos(a), y + 3.4 * math.sin(a) + 1.2, label,
                  T_VIEW, "middle", "tx", weight="700")

    # -- 표 --
    def table(self, x: float, y: float, widths: list[float], rows: list[list[str]],
              header: bool = True, row_h: float = 4.4, size: float = T_DIM,
              aligns: list[str] | None = None) -> float:
        """단순 표. 반환값은 표 아래쪽 y."""
        total = sum(widths)
        aligns = aligns or ["start"] * len(widths)
        for i, row in enumerate(rows):
            ry = y + i * row_h
            if header and i == 0:
                self.rect(x, ry, total, row_h, 0, "ln", fill="var(--band)")
            self.rect(x, ry, total, row_h, THIN, "ln")
            cx = x
            for w, cell, al in zip(widths, row, aligns):
                if cx > x:
                    self.line(cx, ry, cx, ry + row_h, THIN, "ln")
                tx = cx + 1.2 if al == "start" else (cx + w - 1.2 if al == "end" else cx + w / 2)
                self.text(tx, ry + row_h - 1.5, cell, size, al, "tx",
                          weight="600" if header and i == 0 else "")
                cx += w
        return y + len(rows) * row_h

    # -- 시트 구성 --
    def frame_and_title(self, revision: str, date: str, sheet: str,
                        drawn: str = "설계 계산 자동생성", note: str = "") -> None:
        x0, y0 = self.MARGIN_L, self.MARGIN
        w = self.WIDTH - self.MARGIN_L - self.MARGIN
        h = self.HEIGHT - 2 * self.MARGIN
        self.rect(x0, y0, w, h, FRAME, "ln")
        # 표제란
        tw, th = 178.0, 30.0
        tx, ty = x0 + w - tw, y0 + h - th
        self.rect(tx, ty, tw, th, FRAME, "ln", fill="var(--paper)")
        self.line(tx, ty + 13, tx + tw, ty + 13, THIN, "ln")
        self.line(tx + 118, ty, tx + 118, ty + th, THIN, "ln")
        self.text(tx + 3, ty + 7.0, self.title, T_TITLE, "start", "tx", weight="700")
        self.text(tx + 3, ty + 11.4, self.subtitle, T_DIM, "start", "tx2")
        cells = (
            ("도면번호", self.number), ("축척", self.scale), ("단위", "mm"),
            ("Rev", revision), ("날짜", date), ("시트", sheet),
        )
        for i, (k, v) in enumerate(cells):
            cx = tx + 3 + (i % 3) * 39
            cy = ty + 19 + (i // 3) * 7.6
            self.text(cx, cy - 2.6, k, T_DIM - 0.5, "start", "tx2")
            self.text(cx, cy + 1.4, v, T_NOTE, "start", "tx", weight="600", mono=True)
        self.text(tx + 121, ty + 6.0, "DYNAMIC INDUSTRY", T_NOTE, "start", "tx", weight="700")
        self.text(tx + 121, ty + 10.4, "MP-50 염수 밀도분리 파일럿", T_DIM - 0.4, "start", "tx2")
        self.text(tx + 121, ty + 19.4, drawn, T_DIM - 0.4, "start", "tx2")
        self.text(tx + 121, ty + 24.0, note or "제3각법", T_DIM - 0.4, "start", "tx2")
        # 제3각법 기호
        self.circle(tx + 168, ty + 21.5, 3.2, THIN, "ln")
        self.circle(tx + 168, ty + 21.5, 1.5, THIN, "ln")
        self.poly([(tx + 158, ty + 18.3), (tx + 163, ty + 21.5), (tx + 158, ty + 24.7)],
                  THIN, "ln", close=True)
        return None

    def head(self, chips: list[tuple[str, str]]) -> None:
        """도면 상단 정보 띠 — 재질·표면처리 같은 공통 지시."""
        x = self.MARGIN_L + 2.0
        y = self.MARGIN + 2.0
        for label, value in chips:
            wv = max(text_width(value, T_NOTE), text_width(label, T_DIM - 0.6)) + 4.4
            self.rect(x, y, wv, 9.0, THIN, "ln", fill="var(--band)")
            self.text(x + 2.2, y + 3.6, label, T_DIM - 0.6, "start", "tx2")
            self.text(x + 2.2, y + 7.6, value, T_NOTE, "start", "tx", weight="600")
            x += wv + 1.6

    def view_title(self, x: float, y: float, name: str, scale: str = "") -> None:
        w = text_width(name, T_VIEW)
        self.text(x, y, name, T_VIEW, "start", "tx", weight="700")
        if scale:
            self.text(x + w + 2.6, y, f"척도 {scale}", T_DIM, "start", "tx2")
        self.line(x, y + 1.6, x + w, y + 1.6, THICK, "ln")

    def render(self) -> str:
        defs = "<defs>" + "".join(self._defs) + "</defs>" if self._defs else ""
        return (
            f'<svg viewBox="0 0 {self.WIDTH:.0f} {self.HEIGHT:.0f}" role="img" '
            f'aria-label="{esc(self.aria)}" xmlns="http://www.w3.org/2000/svg">'
            f"{defs}" + "".join(self.body) + "</svg>"
        )


@dataclass
class View:
    """모델 좌표(장치 mm) → 용지 좌표(mm) 사상.

    Attributes:
        ox: 모델 원점의 용지 x.
        oy: 모델 Z=0 의 용지 y.
        scale: 1/n 의 n. 축척 1:5 면 5.
        flip_y: Z 가 위로 가도록 뒤집는다 (제도에서는 늘 참).
    """

    ox: float
    oy: float
    scale: float
    flip_y: bool = True

    def x(self, mx: float) -> float:
        return self.ox + mx / self.scale

    def y(self, mz: float) -> float:
        return self.oy - mz / self.scale if self.flip_y else self.oy + mz / self.scale

    def d(self, mm: float) -> float:
        """모델 길이를 용지 길이로."""
        return mm / self.scale

    def p(self, mx: float, mz: float) -> tuple[float, float]:
        return self.x(mx), self.y(mz)

    def pts(self, coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [self.p(a, b) for a, b in coords]

    @property
    def label(self) -> str:
        return f"1:{self.scale:g}"
