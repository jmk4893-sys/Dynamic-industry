"""DXF R12 (AC1009) ASCII 라이터 — 표준 라이브러리만 쓴다.

왜 직접 쓰는가. 이 저장소는 외부 의존성 없이 돌아가고 CI 도 아무것도 설치하지
않는다. 그리고 R12 는 형식이 단순해서 직접 쓰는 편이 오히려 결과를 정확히
통제할 수 있다 — 레이저 CAM 이 읽는 것은 닫힌 폴리라인 하나지 예쁜 그림이
아니다.

R12 를 고른 이유는 **가장 넓게 읽히기** 때문이다. 오래된 CAM 후처리기까지
포함해 사실상 모든 것이 읽는다. 대신 LWPOLYLINE 이 없으므로 POLYLINE +
VERTEX 를 쓰고, 호는 bulge 로 실는다.

치수는 DIMENSION 엔티티 대신 **선과 글자로 직접 그린다**. R12 의 DIMENSION 은
블록 정의에 의존해서 읽는 쪽마다 다르게 풀리는데, 도면의 숫자가 프로그램에
따라 달라지면 안 되기 때문이다. 그려 넣은 치수는 어디서 열어도 같다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: AutoCAD 색 번호. 흰/검(7)은 배경에 따라 뒤집히므로 윤곽에 쓴다.
RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA, WHITE, GREY = 1, 2, 3, 4, 5, 6, 7, 8

#: 레이어 — (이름, 색, 선종류). CAM 은 보통 CUT 만 집어간다.
LAYERS: tuple[tuple[str, int, str], ...] = (
    ("CUT", WHITE, "CONTINUOUS"),        # 바깥 윤곽 — 자른다
    ("HOLE", WHITE, "CONTINUOUS"),       # 구멍 — 자른다
    ("BEND", MAGENTA, "DASHED"),         # 절곡선 — 자르지 않는다
    ("MARK", CYAN, "CONTINUOUS"),        # 각인·표시 — 자르지 않는다
    ("CENTER", YELLOW, "CENTER"),        # 중심선
    ("HIDDEN", GREY, "DASHED"),          # 숨은선
    ("DIM", GREEN, "CONTINUOUS"),        # 치수
    ("TEXT", GREEN, "CONTINUOUS"),       # 글자
    ("FRAME", WHITE, "CONTINUOUS"),      # 도면 틀·표제란
    ("NOTE", GREY, "CONTINUOUS"),        # 주기
)

_LTYPES: tuple[tuple[str, str, float, tuple[float, ...]], ...] = (
    ("CONTINUOUS", "Solid line", 0.0, ()),
    ("DASHED", "Dashed __ __ __ __", 6.0, (4.0, -2.0)),
    ("CENTER", "Center ____ _ ____", 12.0, (8.0, -1.5, 1.0, -1.5)),
)


#: cp949 에 없는 글자를 같은 뜻의 있는 글자로 바꾼다. 도면 파일은 한국 현장의
#: CAD 가 그대로 읽도록 cp949 로 쓰는데, 여기 없는 글자는 조용히 깨지는 대신
#: 바꾸거나 (아래) 예외로 막는다.
#: 긴 것부터 바꾼다 — "µm" 를 낱글자로 바꾸면 "㎛m" 이 된다.
_CP949_SUBST = (
    ("\u00b5m", "\u339b"),                       # µm → ㎛
    ("\u00b5", "u"),                              # 남은 µ
    ("\u2013", "-"), ("\u2014", "-"),             # 엔/엠 대시
    ("\u2205", "\u00d8"), ("\u2300", "\u00d8"),  # ∅ · ⌀ → Ø
)


def cp949_safe(text: str) -> str:
    """cp949 로 쓸 수 있는 글자열로 바꾼다. 못 바꾸면 예외를 던진다."""
    out = text
    for src, dst in _CP949_SUBST:
        out = out.replace(src, dst)
    try:
        out.encode("cp949")
    except UnicodeEncodeError as exc:
        bad = out[exc.start:exc.end]
        raise ValueError(
            f"cp949 로 쓸 수 없는 글자 {bad!r} — _CP949_SUBST 에 대체를 넣을 것: {text!r}"
        ) from exc
    return out


def write(path, drawing: "Drawing") -> int:
    """도면을 cp949 로 저장한다. 쓴 바이트 수를 돌려준다.

    DXF R12 에는 유니코드가 없다. 읽는 쪽은 ``$DWGCODEPAGE`` 를 보고 바이트를
    푸는데, 한국 현장 CAD 의 기본이 ANSI_949 다. UTF-8 로 쓰면 한글이 통째로
    깨져 나온다 — 실제로 확인했다.
    """
    import pathlib as _pathlib

    p = _pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = cp949_safe(drawing.render()).encode("cp949")
    p.write_bytes(data)
    return len(data)


def read(path) -> str:
    """저장한 DXF 를 되읽는다 — 시험이 쓴다."""
    import pathlib as _pathlib

    return _pathlib.Path(path).read_bytes().decode("cp949")


def _g(code: int, value) -> str:
    """그룹 코드 한 쌍. DXF 는 코드 한 줄, 값 한 줄이 전부다."""
    if isinstance(value, float):
        return f"{code:d}\n{value:.6f}\n"
    return f"{code:d}\n{value}\n"


@dataclass
class Drawing:
    """DXF 한 장. 엔티티를 순서대로 쌓았다가 한 번에 직렬화한다."""

    entities: list[str] = field(default_factory=list)
    _min: list[float] = field(default_factory=lambda: [1e18, 1e18])
    _max: list[float] = field(default_factory=lambda: [-1e18, -1e18])

    # -- 범위 --
    def _see(self, x: float, y: float) -> None:
        self._min[0] = min(self._min[0], x)
        self._min[1] = min(self._min[1], y)
        self._max[0] = max(self._max[0], x)
        self._max[1] = max(self._max[1], y)

    # -- 엔티티 --
    def line(self, x1: float, y1: float, x2: float, y2: float, layer: str = "CUT") -> None:
        self._see(x1, y1)
        self._see(x2, y2)
        self.entities.append(
            _g(0, "LINE") + _g(8, layer)
            + _g(10, float(x1)) + _g(20, float(y1)) + _g(30, 0.0)
            + _g(11, float(x2)) + _g(21, float(y2)) + _g(31, 0.0))

    def circle(self, cx: float, cy: float, r: float, layer: str = "HOLE") -> None:
        self._see(cx - r, cy - r)
        self._see(cx + r, cy + r)
        self.entities.append(
            _g(0, "CIRCLE") + _g(8, layer)
            + _g(10, float(cx)) + _g(20, float(cy)) + _g(30, 0.0) + _g(40, float(r)))

    def arc(self, cx: float, cy: float, r: float, start_deg: float, end_deg: float,
            layer: str = "CUT") -> None:
        """DXF 의 호는 언제나 반시계로 시작각 → 끝각이다."""
        self._see(cx - r, cy - r)
        self._see(cx + r, cy + r)
        self.entities.append(
            _g(0, "ARC") + _g(8, layer)
            + _g(10, float(cx)) + _g(20, float(cy)) + _g(30, 0.0) + _g(40, float(r))
            + _g(50, float(start_deg % 360.0)) + _g(51, float(end_deg % 360.0)))

    def polyline(self, vertices, layer: str = "CUT", closed: bool = True) -> None:
        """``(x, y, bulge)`` 목록. 닫힌 윤곽은 CAM 이 이것만 본다.

        호가 있는 윤곽은 꼭짓점만 보면 범위가 좁게 나온다 — 원을 반원 두 개로
        그리면 세로 폭이 0 으로 잡힌다. 사분점을 지나는 호까지 세어 $EXTMIN·
        $EXTMAX 를 채운다. 도면을 열었을 때 화면 맞춤이 어긋나는 것을 막는다.
        """
        from _mp50_cad import arc_geometry

        v = list(vertices)
        n = len(v)
        last = n if closed else n - 1
        for i in range(last):
            p1, p2 = v[i], v[(i + 1) % n]
            if not p1[2]:
                continue
            cx, cy, r, start, theta = arc_geometry(p1, p2)
            for k in range(4):
                ang = k * math.pi / 2.0
                d = (ang - start) % (2.0 * math.pi)
                if theta < 0.0:
                    d -= 2.0 * math.pi
                if 0.0 <= d <= theta or theta <= d <= 0.0:
                    self._see(cx + r * math.cos(ang), cy + r * math.sin(ang))
        body = (_g(0, "POLYLINE") + _g(8, layer) + _g(66, 1)
                + _g(10, 0.0) + _g(20, 0.0) + _g(30, 0.0)
                + _g(70, 1 if closed else 0))
        for x, y, b in vertices:
            self._see(x, y)
            body += (_g(0, "VERTEX") + _g(8, layer)
                     + _g(10, float(x)) + _g(20, float(y)) + _g(30, 0.0))
            if b:
                body += _g(42, float(b))
        body += _g(0, "SEQEND") + _g(8, layer)
        self.entities.append(body)

    def text(self, x: float, y: float, value: str, height: float = 3.5,
             layer: str = "TEXT", align: str = "left", rotation: float = 0.0) -> None:
        """한 줄 글자. ``align`` 은 left / center / right."""
        self._see(x, y)
        halign = {"left": 0, "center": 1, "right": 2}[align]
        body = (_g(0, "TEXT") + _g(8, layer)
                + _g(10, float(x)) + _g(20, float(y)) + _g(30, 0.0)
                + _g(40, float(height)) + _g(1, value) + _g(50, float(rotation))
                + _g(7, "STANDARD"))
        if halign:
            body += _g(72, halign) + _g(11, float(x)) + _g(21, float(y)) + _g(31, 0.0)
        self.entities.append(body)

    def solid(self, pts: list[tuple[float, float]], layer: str = "DIM") -> None:
        """채운 삼각형·사각형 — 치수 화살촉에 쓴다.

        SOLID 의 세 번째·네 번째 점 순서가 뒤집혀 있는 것은 형식이 그렇다.
        """
        p = list(pts)
        if len(p) == 3:
            p.append(p[2])
        for x, y in p:
            self._see(x, y)
        body = _g(0, "SOLID") + _g(8, layer)
        for i, (x, y) in enumerate(p):
            body += _g(10 + i, float(x)) + _g(20 + i, float(y)) + _g(30 + i, 0.0)
        self.entities.append(body)

    # -- 조합 --
    def profile(self, prof, layer_outer: str = "CUT", layer_hole: str = "HOLE") -> None:
        """윤곽 하나 — 바깥 고리와 구멍, 절곡선, 마킹."""
        self.polyline(prof.outer, layer_outer)
        for h in prof.holes:
            self.polyline(h, layer_hole)
        for (x1, y1), (x2, y2), _angle, _side in prof.bends:
            self.line(x1, y1, x2, y2, "BEND")
        for m in prof.marks:
            self.polyline(m, "MARK")

    def centre_mark(self, cx: float, cy: float, r: float) -> None:
        self.line(cx - r, cy, cx + r, cy, "CENTER")
        self.line(cx, cy - r, cx, cy + r, "CENTER")

    def arrow(self, tip_x: float, tip_y: float, angle: float, size: float = 2.5) -> None:
        """치수 화살촉 — ``angle`` 방향으로 뾰족하다 (라디안)."""
        w = size * 0.32
        bx, by = tip_x - size * math.cos(angle), tip_y - size * math.sin(angle)
        nx, ny = -math.sin(angle) * w, math.cos(angle) * w
        self.solid([(tip_x, tip_y), (bx + nx, by + ny), (bx - nx, by - ny)])

    def dim_linear(self, x1: float, y1: float, x2: float, y2: float, offset: float,
                   text: str = "", height: float = 3.5, vertical: bool = False) -> None:
        """두 점 사이 치수. ``vertical`` 이면 세로로 잰다.

        치수선은 잴 두 점에서 ``offset`` 만큼 떨어진 자리에 긋고, 보조선을
        조금 넘겨 뽑는다 (ISO 129).
        """
        over = 1.6
        if vertical:
            dx = offset
            value = text or f"{abs(y2 - y1):.0f}"
            self.line(x1, y1, x1 + dx + math.copysign(over, dx), y1, "DIM")
            self.line(x2, y2, x2 + dx + math.copysign(over, dx), y2, "DIM")
            self.line(x1 + dx, y1, x1 + dx, y2, "DIM")
            lo, hi = (y1, y2) if y1 < y2 else (y2, y1)
            self.arrow(x1 + dx, lo, -math.pi / 2)
            self.arrow(x1 + dx, hi, math.pi / 2)
            self.text(x1 + dx - height * 0.5, (y1 + y2) / 2, value, height, "DIM",
                      "center", 90.0)
        else:
            dy = offset
            value = text or f"{abs(x2 - x1):.0f}"
            self.line(x1, y1, x1, y1 + dy + math.copysign(over, dy), "DIM")
            self.line(x2, y2, x2, y2 + dy + math.copysign(over, dy), "DIM")
            self.line(x1, y1 + dy, x2, y1 + dy, "DIM")
            lo, hi = (x1, x2) if x1 < x2 else (x2, x1)
            self.arrow(lo, y1 + dy, math.pi)
            self.arrow(hi, y1 + dy, 0.0)
            self.text((x1 + x2) / 2, y1 + dy + height * 0.5, value, height, "DIM",
                      "center")

    def dim_diameter(self, cx: float, cy: float, r: float, to_x: float, to_y: float,
                     text: str = "", height: float = 3.5) -> None:
        """지름 치수 — 원 밖으로 지시선을 빼서 적는다."""
        a = math.atan2(to_y - cy, to_x - cx)
        ex, ey = cx + r * math.cos(a), cy + r * math.sin(a)
        self.line(ex, ey, to_x, to_y, "DIM")
        self.arrow(ex, ey, a + math.pi)
        end = to_x + (6.0 if to_x >= cx else -6.0)
        self.line(to_x, to_y, end, to_y, "DIM")
        self.text(end + (1.2 if to_x >= cx else -1.2), to_y + height * 0.3,
                  text or f"Ø{2 * r:.0f}", height, "DIM",
                  "left" if to_x >= cx else "right")

    def leader(self, from_x: float, from_y: float, to_x: float, to_y: float,
               lines: list[str], height: float = 3.0) -> None:
        """지시선 — 꺾어서 글을 여러 줄 단다."""
        self.line(from_x, from_y, to_x, to_y, "DIM")
        end = to_x + (8.0 if to_x >= from_x else -8.0)
        self.line(to_x, to_y, end, to_y, "DIM")
        self.arrow(from_x, from_y, math.atan2(from_y - to_y, from_x - to_x))
        align = "left" if to_x >= from_x else "right"
        pad = 1.4 if to_x >= from_x else -1.4
        for i, s in enumerate(lines):
            self.text(end + pad, to_y + height * 0.3 - i * height * 1.5, s,
                      height, "DIM", align)

    # -- 출력 --
    def render(self) -> str:
        lo = [0.0 if v > 1e17 else v for v in self._min]
        hi = [0.0 if v < -1e17 else v for v in self._max]
        out = [
            _g(0, "SECTION") + _g(2, "HEADER")
            + _g(9, "$ACADVER") + _g(1, "AC1009")
            + _g(9, "$DWGCODEPAGE") + _g(3, "ANSI_949")
            + _g(9, "$INSBASE") + _g(10, 0.0) + _g(20, 0.0) + _g(30, 0.0)
            + _g(9, "$EXTMIN") + _g(10, lo[0]) + _g(20, lo[1]) + _g(30, 0.0)
            + _g(9, "$EXTMAX") + _g(10, hi[0]) + _g(20, hi[1]) + _g(30, 0.0)
            + _g(9, "$LUNITS") + _g(70, 2)          # 십진
            + _g(9, "$INSUNITS") + _g(70, 4)        # mm
            + _g(9, "$LIMMIN") + _g(10, lo[0]) + _g(20, lo[1])
            + _g(9, "$LIMMAX") + _g(10, hi[0]) + _g(20, hi[1])
            + _g(0, "ENDSEC")
        ]
        tables = _g(0, "SECTION") + _g(2, "TABLES")
        tables += _g(0, "TABLE") + _g(2, "LTYPE") + _g(70, len(_LTYPES))
        for name, desc, total, pattern in _LTYPES:
            tables += (_g(0, "LTYPE") + _g(2, name) + _g(70, 64) + _g(3, desc)
                       + _g(72, 65) + _g(73, len(pattern)) + _g(40, total))
            for seg in pattern:
                tables += _g(49, float(seg))
        tables += _g(0, "ENDTAB")
        tables += _g(0, "TABLE") + _g(2, "LAYER") + _g(70, len(LAYERS))
        for name, color, ltype in LAYERS:
            tables += (_g(0, "LAYER") + _g(2, name) + _g(70, 0)
                       + _g(62, color) + _g(6, ltype))
        tables += _g(0, "ENDTAB")
        tables += (_g(0, "TABLE") + _g(2, "STYLE") + _g(70, 1)
                   + _g(0, "STYLE") + _g(2, "STANDARD") + _g(70, 0)
                   + _g(40, 0.0) + _g(41, 1.0) + _g(50, 0.0) + _g(71, 0)
                   + _g(42, 2.5) + _g(3, "txt") + _g(4, "")
                   + _g(0, "ENDTAB"))
        tables += _g(0, "ENDSEC")
        out.append(tables)
        out.append(_g(0, "SECTION") + _g(2, "BLOCKS") + _g(0, "ENDSEC"))
        out.append(_g(0, "SECTION") + _g(2, "ENTITIES")
                   + "".join(self.entities) + _g(0, "ENDSEC"))
        out.append(_g(0, "EOF"))
        return "".join(out)


def parse(text: str) -> list[tuple[int, str]]:
    """DXF 를 (코드, 값) 목록으로 되읽는다 — 시험이 쓴다."""
    lines = text.splitlines()
    out = []
    for i in range(0, len(lines) - 1, 2):
        try:
            out.append((int(lines[i].strip()), lines[i + 1]))
        except ValueError as exc:                # pragma: no cover - 형식이 깨진 경우
            raise ValueError(f"{i} 줄에서 그룹 코드가 아니다: {lines[i]!r}") from exc
    return out


def entities(pairs: list[tuple[int, str]]) -> list[dict]:
    """ENTITIES 구간을 엔티티 목록으로 묶는다. 값은 코드별 목록으로 담는다."""
    out: list[dict] = []
    inside = False
    cur: dict | None = None
    for i, (code, value) in enumerate(pairs):
        if code == 2 and value == "ENTITIES" and i and pairs[i - 1] == (0, "SECTION"):
            inside = True
            continue
        if not inside:
            continue
        if code == 0:
            if value == "ENDSEC":
                break
            cur = {"type": value}
            out.append(cur)
            continue
        if cur is not None:
            cur.setdefault(code, []).append(value)
    return out
