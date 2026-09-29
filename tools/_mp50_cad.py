"""CAD 출력용 2D 윤곽 — 직선과 원호로 된 닫힌 고리.

레이저·워터젯은 그림이 아니라 **닫힌 윤곽**을 먹는다. 그래서 도면 SVG 와는
따로, 자를 형상만 담은 자료형을 둔다. 고리 하나는 꼭짓점 목록이고 각
꼭짓점은 ``(x, y, bulge)`` 다. ``bulge`` 는 그 꼭짓점에서 **다음** 꼭짓점까지의
호를 나타내는 값으로 ``tan(사잇각/4)`` 이며, 0 이면 직선, 양수면 반시계다.

이 표기를 고른 이유는 DXF 의 POLYLINE 이 쓰는 값과 같기 때문이다. 변환 없이
그대로 쓰면 반올림이 끼어들 자리가 없다.

부호 약속 — 바깥 고리는 반시계, 구멍은 시계. 면적이 양수인지로 확인한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: 꼭짓점 — x, y, 다음 변까지의 bulge.
Vertex = tuple[float, float, float]
Loop = list[Vertex]


def arc_geometry(p1: Vertex, p2: Vertex) -> tuple[float, float, float, float, float]:
    """``p1`` 의 bulge 가 만드는 호의 (중심 x, 중심 y, 반지름, 시작각, 사잇각).

    각은 라디안이고 사잇각은 부호가 있다 (반시계 양수).
    """
    b = p1[2]
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    chord = math.hypot(dx, dy)
    if chord == 0.0 or b == 0.0:
        raise ValueError("직선 구간에는 호가 없다")
    theta = 4.0 * math.atan(b)
    radius = chord / (2.0 * math.sin(theta / 2.0))
    # 현의 중점에서 수직으로 sagitta 만큼 떨어진 곳이 중심이다.
    mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
    h = radius * math.cos(theta / 2.0)
    cx, cy = mx - h * dy / chord, my + h * dx / chord
    start = math.atan2(p1[1] - cy, p1[0] - cx)
    return cx, cy, abs(radius), start, theta


def area(loop: Loop) -> float:
    """고리가 감싸는 넓이 (mm²). 반시계면 양수.

    직선 부분은 신발끈 공식으로, 호는 현 너머의 활꼴을 더하거나 뺀다.
    """
    total = 0.0
    n = len(loop)
    for i, p1 in enumerate(loop):
        p2 = loop[(i + 1) % n]
        total += p1[0] * p2[1] - p2[0] * p1[1]
        if p1[2]:
            _, _, r, _, theta = arc_geometry(p1, p2)
            total += r * r * (theta - math.sin(theta))
    return total / 2.0


def perimeter(loop: Loop) -> float:
    """고리의 둘레 (mm). 절단 길이 견적에 쓴다."""
    total = 0.0
    n = len(loop)
    for i, p1 in enumerate(loop):
        p2 = loop[(i + 1) % n]
        if p1[2]:
            _, _, r, _, theta = arc_geometry(p1, p2)
            total += abs(r * theta)
        else:
            total += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    return total


def bounds(loop: Loop) -> tuple[float, float, float, float]:
    """고리의 외접 사각형. 호가 사분점을 지나면 꼭짓점보다 더 나간다."""
    xs = [p[0] for p in loop]
    ys = [p[1] for p in loop]
    n = len(loop)
    for i, p1 in enumerate(loop):
        p2 = loop[(i + 1) % n]
        if not p1[2]:
            continue
        cx, cy, r, start, theta = arc_geometry(p1, p2)
        for k in range(4):
            a = k * math.pi / 2.0
            # 사분점이 호의 범위 안에 드는가 — 진행 방향으로 각을 편다.
            d = (a - start) % (2.0 * math.pi)
            if theta < 0.0:
                d -= 2.0 * math.pi
            if 0.0 <= d <= theta or theta <= d <= 0.0:
                xs.append(cx + r * math.cos(a))
                ys.append(cy + r * math.sin(a))
    return min(xs), min(ys), max(xs), max(ys)


@dataclass
class Profile:
    """바깥 고리 하나와 구멍 여러 개 — 잘라낼 판 한 장의 형상."""

    outer: Loop
    holes: list[Loop] = field(default_factory=list)
    #: 절곡선 — ((x1, y1), (x2, y2), 각도°, 안쪽/바깥쪽). 자르지 않고 표시만 한다.
    bends: list[tuple[tuple[float, float], tuple[float, float], float, str]] = \
        field(default_factory=list)
    #: 각인·마킹 선 — 자르지 않는다.
    marks: list[Loop] = field(default_factory=list)

    @property
    def area_mm2(self) -> float:
        """구멍을 뺀 실면적."""
        return area(self.outer) + sum(area(h) for h in self.holes)

    @property
    def cut_length_mm(self) -> float:
        return perimeter(self.outer) + sum(perimeter(h) for h in self.holes)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return bounds(self.outer)

    @property
    def size(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bounds
        return x1 - x0, y1 - y0

    def translated(self, dx: float, dy: float) -> "Profile":
        def mv(loop: Loop) -> Loop:
            return [(x + dx, y + dy, b) for x, y, b in loop]
        return Profile(mv(self.outer), [mv(h) for h in self.holes],
                       [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), ang, side)
                        for a, b, ang, side in self.bends],
                       [mv(m) for m in self.marks])

    def check(self) -> None:
        """부호 약속을 지켰는지 — 어기면 CAM 이 구멍을 바깥으로 읽는다."""
        if area(self.outer) <= 0.0:
            raise ValueError("바깥 고리가 반시계가 아니다")
        for i, h in enumerate(self.holes):
            if area(h) >= 0.0:
                raise ValueError(f"구멍 {i} 가 시계 방향이 아니다")


# --------------------------------------------------------------------------
# 고리 만들기
# --------------------------------------------------------------------------
def circle_loop(cx: float, cy: float, r: float, ccw: bool = True) -> Loop:
    """원 — 반원 두 개. bulge 1 이 정확히 180° 다."""
    b = 1.0 if ccw else -1.0
    return [(cx - r, cy, b), (cx + r, cy, b)]


def hole(cx: float, cy: float, dia: float) -> Loop:
    """구멍 — 시계 방향 원."""
    return circle_loop(cx, cy, dia / 2.0, ccw=False)


def slot(cx: float, cy: float, length: float, width: float, ccw: bool = False) -> Loop:
    """장공 — 가로로 누운 오벌. 볼트 구멍 조정에 쓴다."""
    r = width / 2.0
    dx = max(0.0, (length - width) / 2.0)
    b = 1.0 if ccw else -1.0
    if ccw:
        return [(cx - dx, cy - r, 0.0), (cx + dx, cy - r, b),
                (cx + dx, cy + r, 0.0), (cx - dx, cy + r, b)]
    return [(cx - dx, cy + r, 0.0), (cx + dx, cy + r, b),
            (cx + dx, cy - r, 0.0), (cx - dx, cy - r, b)]


def ring(cx: float, cy: float, od: float, id_: float) -> Profile:
    """도넛 — 플랜지·지지링·관 단면."""
    return Profile(circle_loop(cx, cy, od / 2.0), [hole(cx, cy, id_)])


def rect_loop(x: float, y: float, w: float, h: float, r: float = 0.0,
              ccw: bool = True) -> Loop:
    """사각형. ``r`` 을 주면 네 모서리를 둥글린다."""
    if r <= 0.0:
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        loop = [(px, py, 0.0) for px, py in pts]
    else:
        b = math.tan(math.pi / 8.0)          # 90° 호
        loop = [
            (x + r, y, 0.0), (x + w - r, y, b),
            (x + w, y + r, 0.0), (x + w, y + h - r, b),
            (x + w - r, y + h, 0.0), (x + r, y + h, b),
            (x, y + h - r, 0.0), (x, y + r, b),
        ]
    return loop if ccw else reverse(loop)


def polygon_loop(points: list[tuple[float, float]], r: float = 0.0) -> Loop:
    """직선 다각형. ``r`` 을 주면 모든 꼭짓점을 같은 반지름으로 둥글린다.

    염수에 잠기는 부품은 날선 모서리를 두지 않는다 — 부동태 피막이 얇게
    붙어 그 자리가 먼저 뜯긴다. 그래서 R2 가 기본이다.
    """
    if r <= 0.0:
        return [(x, y, 0.0) for x, y in points]
    n = len(points)
    out: Loop = []
    for i in range(n):
        prev = points[(i - 1) % n]
        cur = points[i]
        nxt = points[(i + 1) % n]
        v1 = (prev[0] - cur[0], prev[1] - cur[1])
        v2 = (nxt[0] - cur[0], nxt[1] - cur[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 == 0.0 or l2 == 0.0:
            raise ValueError("점이 겹친다")
        u1 = (v1[0] / l1, v1[1] / l1)
        u2 = (v2[0] / l2, v2[1] / l2)
        cosang = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        angle = math.acos(cosang)            # 두 변 사이 각
        if angle < 1e-9 or abs(angle - math.pi) < 1e-9:
            out.append((cur[0], cur[1], 0.0))
            continue
        setback = r / math.tan(angle / 2.0)
        if setback > min(l1, l2) - 1e-9:
            raise ValueError(f"모서리 R{r} 이 변보다 크다")
        a = (cur[0] + u1[0] * setback, cur[1] + u1[1] * setback)
        c = (cur[0] + u2[0] * setback, cur[1] + u2[1] * setback)
        # 회전 방향 — 외적 부호가 볼록/오목을 가른다.
        cross = u1[0] * u2[1] - u1[1] * u2[0]
        sweep = math.pi - angle
        bulge = math.tan(sweep / 4.0) * (1.0 if cross < 0.0 else -1.0)
        out.append((a[0], a[1], bulge))
        out.append((c[0], c[1], 0.0))
    return out


def reverse(loop: Loop) -> Loop:
    """진행 방향을 뒤집는다 — bulge 부호와 자리도 함께 옮겨야 한다."""
    n = len(loop)
    out: Loop = []
    for i in range(n - 1, -1, -1):
        prev = loop[(i - 1) % n]
        out.append((loop[i][0], loop[i][1], -prev[2]))
    return out


def bolt_circle(cx: float, cy: float, pcd: float, count: int, dia: float,
                offset_deg: float = 0.0) -> list[Loop]:
    """볼트 구멍 원주 배열."""
    out = []
    for i in range(count):
        a = math.radians(offset_deg + 360.0 * i / count)
        out.append(hole(cx + pcd / 2.0 * math.cos(a), cy + pcd / 2.0 * math.sin(a), dia))
    return out


def square_tube(width: float, wall: float, outer_r: float | None = None) -> Profile:
    """각관 단면 — 바깥 모서리는 벽두께만큼, 안쪽은 그 절반으로 둥글다."""
    ro = wall * 1.5 if outer_r is None else outer_r
    ri = max(0.1, ro - wall)
    outer = rect_loop(0.0, 0.0, width, width, ro)
    inner = rect_loop(wall, wall, width - 2 * wall, width - 2 * wall, ri)
    return Profile(outer, [reverse(inner)])
