"""STEP AP214 라이터 — 윤곽을 밀어낸 해석 B-rep 솔리드.

기계 가공장은 메시가 아니라 **해석면을 가진 솔리드**를 받는다. 평면·원통·
원뿔로 된 면이라야 CAM 이 지름과 축을 읽고 공구를 건다. 그래서 STL 같은
삼각형 껍질이 아니라 STEP 의 MANIFOLD_SOLID_BREP 을 직접 쓴다.

다루는 형상은 둘이다.

* ``extrude`` — 닫힌 윤곽(직선·원호, 구멍 포함)을 두께만큼 밀어낸 것. 판재,
  링, 관 단면, 각관, 날개, 키까지 여기서 나온다.
* ``cone_shell`` — 잘린 원뿔 껍질. 원뿔 동체 한 종류 때문에 따로 둔다.

**방향 약속.** STEP 은 면의 바깥 법선 기준으로 바깥 고리가 반시계여야 한다.
여기서는 윤곽이 반시계(바깥)·시계(구멍)라는 약속을 그대로 쓰고, 옆면 고리는
'아래 모서리 정방향 → 끝점에서 위로 → 위 모서리 역방향 → 시작점에서 아래로'
순서로 돈다. 이 순서가 바깥 법선을 만든다.

방향을 틀리면 CAD 가 솔리드를 뒤집어 읽어 부피가 음수로 나온다. 그래서
``volume`` 이 발산정리로 제 부피를 직접 재고, 시험이 그 값을 면적 × 두께와
맞춰 본다 — 한 면이라도 뒤집히면 숫자가 어긋난다.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field

from _mp50_cad import Loop, Profile, arc_geometry

#: 스키마 — AP214 는 색·조립까지 담고 거의 모든 CAD 가 읽는다.
SCHEMA = "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }"


@dataclass
class _Ids:
    """엔티티 번호 발급기."""

    n: int = 0
    lines: list[str] = field(default_factory=list)

    def add(self, body: str) -> int:
        self.n += 1
        self.lines.append(f"#{self.n} = {body};")
        return self.n


def esc(text: str) -> str:
    """STEP 문자열 — 아스키가 아닌 글자는 ``\\X2\\`` UTF-16 이스케이프로 넣는다.

    ISO 10303-21 의 파일 본문은 아스키다. 한글 부품명을 그대로 쓰면 파일이
    깨지므로 규격이 정한 확장 표기를 쓴다. OpenCascade 가 이 표기를 푼다.
    """
    out, buf = [], []

    def flush() -> None:
        if buf:
            out.append("\\X2\\" + "".join(f"{ord(c):04X}" for c in buf) + "\\X0\\")
            buf.clear()

    for ch in text:
        if ch == "'":
            flush()
            out.append("''")
        elif ord(ch) < 128:
            flush()
            out.append(ch)
        else:
            buf.append(ch)
    flush()
    return "".join(out)


def _f(v: float) -> str:
    """STEP 실수 표기 — 반드시 소수점이 있어야 한다."""
    if v == 0.0:
        return "0."
    s = f"{v:.9f}".rstrip("0")
    return s if not s.endswith(".") else s + "0"


@dataclass
class Face:
    """부피 적분과 다양체 판정을 위해 남겨 두는 면의 기하."""

    kind: str                      # plane / cylinder / cone
    #: 면 위의 닫힌 고리들을 3D 점열(다각형 근사)로. 부피 적분에만 쓴다.
    loops: list[list[tuple[float, float, float]]]
    normal: tuple[float, float, float] | None = None


def _arc_points(p1, p2, n: int = 24) -> list[tuple[float, float]]:
    """호를 점열로 편다 — 부피 적분용 근사. 파일에는 해석면이 나간다."""
    cx, cy, r, start, theta = arc_geometry(p1, p2)
    return [(cx + r * math.cos(start + theta * i / n),
             cy + r * math.sin(start + theta * i / n)) for i in range(1, n)]


def _flatten(loop: Loop, n: int = 24) -> list[tuple[float, float]]:
    """고리를 점열로 편다."""
    out: list[tuple[float, float]] = []
    m = len(loop)
    for i, p1 in enumerate(loop):
        p2 = loop[(i + 1) % m]
        out.append((p1[0], p1[1]))
        if p1[2]:
            out.extend(_arc_points(p1, p2, n))
    return out


def volume(faces: list[Face]) -> float:
    """발산정리로 잰 부피 (mm³).

    닫힌 껍질이면 ∮ x·n dA / 3 이 부피다. 면이 하나라도 뒤집히면 그 면의
    기여가 부호를 바꾸므로 값이 어긋난다 — 방향 약속을 지켰는지 보는 검사다.
    """
    total = 0.0
    for f in faces:
        for loop in f.loops:
            # 다각형을 첫 점 기준 삼각형으로 나눠 적분한다.
            a = loop[0]
            for i in range(1, len(loop) - 1):
                b, c = loop[i], loop[i + 1]
                u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
                v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
                nx = u[1] * v[2] - u[2] * v[1]
                ny = u[2] * v[0] - u[0] * v[2]
                nz = u[0] * v[1] - u[1] * v[0]
                cxm = (a[0] + b[0] + c[0]) / 3.0
                cym = (a[1] + b[1] + c[1]) / 3.0
                czm = (a[2] + b[2] + c[2]) / 3.0
                total += (cxm * nx + cym * ny + czm * nz) / 6.0
    return total


class Solid:
    """면 목록으로 들고 있다가 STEP 으로 직렬화한다."""

    def __init__(self, name: str):
        self.name = name
        self.volume_analytic = 0.0
        self.faces: list[Face] = []
        #: (표면종류, 파라미터, 고리들) — 직렬화가 쓰는 원자료.
        self.spec: list[tuple] = []

    #: 해석 부피 (mm³). 압출은 면적 × 길이, 원뿔은 두 절두체의 차다.
    #: ``volume()`` 은 호를 직선으로 펴므로 검사용 근사값일 뿐이다.
    volume_analytic: float = 0.0

    @property
    def volume_mm3(self) -> float:
        """면에서 발산정리로 잰 부피 — 방향이 뒤집히면 값이 어긋난다."""
        return volume(self.faces)


def extrude(profile: Profile, thickness: float, name: str = "part",
            z0: float = 0.0) -> Solid:
    """윤곽을 ``+Z`` 로 ``thickness`` 만큼 밀어낸 솔리드."""
    profile.check()
    if thickness <= 0.0:
        raise ValueError("두께는 0 보다 커야 한다")
    s = Solid(name)
    s.volume_analytic = profile.area_mm2 * thickness
    z1 = z0 + thickness

    loops = [(profile.outer, True)] + [(h, False) for h in profile.holes]

    # 위·아래 평면
    top_loops, bot_loops = [], []
    for loop, _outer in loops:
        pts = _flatten(loop)
        top_loops.append([(x, y, z1) for x, y in pts])
        bot_loops.append([(x, y, z0) for x, y in reversed(pts)])
    s.faces.append(Face("plane", top_loops, (0.0, 0.0, 1.0)))
    s.faces.append(Face("plane", bot_loops, (0.0, 0.0, -1.0)))
    s.spec.append(("cap", z1, +1, loops))
    s.spec.append(("cap", z0, -1, loops))

    # 옆면 — 윤곽의 변마다 하나
    for loop, _outer in loops:
        m = len(loop)
        for i, p1 in enumerate(loop):
            p2 = loop[(i + 1) % m]
            if p1[2]:
                pts = [(p1[0], p1[1])] + _arc_points(p1, p2) + [(p2[0], p2[1])]
                cx, cy, r, start, theta = arc_geometry(p1, p2)
                s.spec.append(("cyl", (cx, cy, r, start, theta, z0, z1),
                               (p1[0], p1[1]), (p2[0], p2[1])))
            else:
                pts = [(p1[0], p1[1]), (p2[0], p2[1])]
                s.spec.append(("plane_side", (p1[0], p1[1]), (p2[0], p2[1]), z0, z1))
            # 옆면은 사각형 띠로 쌓는다. 한 점에서 부채꼴로 나누면 원통면을
            # 현으로 가로질러 부피가 어긋난다 — 평면 사각형이라야 정확하다.
            quads = [[(pts[i][0], pts[i][1], z0), (pts[i + 1][0], pts[i + 1][1], z0),
                      (pts[i + 1][0], pts[i + 1][1], z1), (pts[i][0], pts[i][1], z1)]
                     for i in range(len(pts) - 1)]
            s.faces.append(Face("side", quads))
    return s


def cone_shell(r_bottom_out: float, r_top_out: float, height: float,
               thickness: float, name: str = "cone", z0: float = 0.0) -> Solid:
    """잘린 원뿔 껍질 — 바깥·안쪽 원뿔면과 위·아래 고리면.

    원뿔 동체는 판을 부채꼴로 잘라 말아 붙인다. 평판 전개는 DXF 가 갖고,
    여기 STEP 은 **말고 난 완성 형상**이다.
    """
    s = Solid(name)
    s.volume_analytic = cone_volume_mm3(r_bottom_out, r_top_out, height, thickness)
    z1 = z0 + height
    slope = math.hypot(height, r_bottom_out - r_top_out)
    # 벽두께는 면에 수직이므로 반지름 방향 감소량으로 환산한다.
    dr = thickness * slope / height if height else thickness
    n = 48
    for sign, ro_b, ro_t in ((+1, r_bottom_out, r_top_out),
                             (-1, r_bottom_out - dr, r_top_out - dr)):
        quads = []
        for i in range(n):
            a0, a1 = 2.0 * math.pi * i / n, 2.0 * math.pi * (i + 1) / n
            q = [(ro_b * math.cos(a0), ro_b * math.sin(a0), z0),
                 (ro_b * math.cos(a1), ro_b * math.sin(a1), z0),
                 (ro_t * math.cos(a1), ro_t * math.sin(a1), z1),
                 (ro_t * math.cos(a0), ro_t * math.sin(a0), z1)]
            quads.append(q if sign > 0 else list(reversed(q)))
        s.faces.append(Face("cone", quads))
    for z, out_r, in_r, up in ((z1, r_top_out, r_top_out - dr, +1),
                               (z0, r_bottom_out, r_bottom_out - dr, -1)):
        rng = range(n) if up > 0 else range(n - 1, -1, -1)
        quads = []
        for i in rng:
            a0, a1 = 2.0 * math.pi * i / n, 2.0 * math.pi * (i + 1) / n
            q = [(in_r * math.cos(a0), in_r * math.sin(a0), z),
                 (out_r * math.cos(a0), out_r * math.sin(a0), z),
                 (out_r * math.cos(a1), out_r * math.sin(a1), z),
                 (in_r * math.cos(a1), in_r * math.sin(a1), z)]
            quads.append(q if up > 0 else list(reversed(q)))
        s.faces.append(Face("plane", quads, (0.0, 0.0, float(up))))
    s.spec.append(("cone", (r_bottom_out, r_top_out, dr, z0, z1)))
    return s


# --------------------------------------------------------------------------
# 직렬화
# --------------------------------------------------------------------------
def _header(ids: _Ids, name: str) -> tuple[int, int]:
    """단위와 문맥 — 모든 STEP 파일이 앞에 다는 상용구."""
    mm = ids.add("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )")
    rad = ids.add("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    sr = ids.add("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    unc = ids.add(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-06),#{mm},"
                  "'distance_accuracy_value','confusion accuracy')")
    ctx = ids.add(
        f"( GEOMETRIC_REPRESENTATION_CONTEXT(3) "
        f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{unc})) "
        f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{mm},#{rad},#{sr})) REPRESENTATION_CONTEXT('','3D') )")
    app = ids.add("APPLICATION_CONTEXT('automotive design')")
    ids.add(f"APPLICATION_PROTOCOL_DEFINITION('international standard',"
            f"'automotive_design',2000,#{app})")
    pctx = ids.add(f"PRODUCT_CONTEXT('',#{app},'mechanical')")
    pdctx = ids.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app},'design')")
    prod = ids.add(f"PRODUCT('{esc(name)}','{esc(name)}','',(#{pctx}))")
    pdf = ids.add(f"PRODUCT_DEFINITION_FORMATION('','',#{prod})")
    pd = ids.add(f"PRODUCT_DEFINITION('design','',#{pdf},#{pdctx})")
    pds = ids.add(f"PRODUCT_DEFINITION_SHAPE('','',#{pd})")
    return ctx, pds


def _pt(ids: _Ids, x: float, y: float, z: float) -> int:
    return ids.add(f"CARTESIAN_POINT('',({_f(x)},{_f(y)},{_f(z)}))")


def _dir(ids: _Ids, x: float, y: float, z: float) -> int:
    return ids.add(f"DIRECTION('',({_f(x)},{_f(y)},{_f(z)}))")


def _axis(ids: _Ids, origin: int, axis: int, ref: int) -> int:
    return ids.add(f"AXIS2_PLACEMENT_3D('',#{origin},#{axis},#{ref})")


def _write_extrusion(ids: _Ids, sol: Solid) -> int:
    """밀어낸 솔리드를 ADVANCED_FACE 로 푼다. CLOSED_SHELL 번호를 돌려준다."""
    caps = [sp for sp in sol.spec if sp[0] == "cap"]
    sides = [sp for sp in sol.spec if sp[0] in ("cyl", "plane_side")]
    z0 = min(c[1] for c in caps)
    z1 = max(c[1] for c in caps)

    vtx: dict[tuple[float, float, float], int] = {}

    def vertex(x: float, y: float, z: float) -> int:
        key = (round(x, 7), round(y, 7), round(z, 7))
        if key not in vtx:
            vtx[key] = ids.add(f"VERTEX_POINT('',#{_pt(ids, x, y, z)})")
        return vtx[key]

    def straight_edge(p1, p2, z) -> int:
        v1, v2 = vertex(p1[0], p1[1], z), vertex(p2[0], p2[1], z)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        ln = math.hypot(dx, dy)
        d = _dir(ids, dx / ln, dy / ln, 0.0)
        vec = ids.add(f"VECTOR('',#{d},{_f(ln)})")
        line = ids.add(f"LINE('',#{_pt(ids, p1[0], p1[1], z)},#{vec})")
        return ids.add(f"EDGE_CURVE('',#{v1},#{v2},#{line},.T.)")

    vertical: dict[tuple[float, float], int] = {}

    def vertical_edge(p, za, zb) -> int:
        """세로 모서리. 옆면 두 장이 **같은 모서리를 공유**해야 솔리드가 된다.

        면마다 따로 만들면 읽는 쪽이 6 장의 흩어진 면으로 보고 꿰매기에
        기대게 되는데, 그러면 솔리드가 아니라 껍질로 들어온다. 실제로
        OpenCascade 가 그렇게 읽었다.
        """
        key = (round(p[0], 7), round(p[1], 7))
        if key in vertical:
            return vertical[key]
        v1, v2 = vertex(p[0], p[1], za), vertex(p[0], p[1], zb)
        d = _dir(ids, 0.0, 0.0, 1.0 if zb > za else -1.0)
        vec = ids.add(f"VECTOR('',#{d},{_f(abs(zb - za))})")
        line = ids.add(f"LINE('',#{_pt(ids, p[0], p[1], za)},#{vec})")
        e = ids.add(f"EDGE_CURVE('',#{v1},#{v2},#{line},.T.)")
        vertical[key] = e
        return e

    def arc_edge(spec, z) -> int:
        cx, cy, r, start, theta, _a, _b = spec
        p1 = (cx + r * math.cos(start), cy + r * math.sin(start))
        p2 = (cx + r * math.cos(start + theta), cy + r * math.sin(start + theta))
        v1, v2 = vertex(p1[0], p1[1], z), vertex(p2[0], p2[1], z)
        axis = _axis(ids, _pt(ids, cx, cy, z), _dir(ids, 0.0, 0.0, 1.0),
                     _dir(ids, 1.0, 0.0, 0.0))
        circ = ids.add(f"CIRCLE('',#{axis},{_f(r)})")
        # 원의 자연 방향은 반시계다. 시계 호는 .F. 로 뒤집어 태운다.
        return ids.add(f"EDGE_CURVE('',#{v1},#{v2},#{circ},"
                       f"{'.T.' if theta > 0 else '.F.'})")

    # 옆면과, 위·아래 면이 쓸 모서리를 함께 만든다.
    faces: list[int] = []
    bottom_edges: dict[int, list[int]] = {}
    top_edges: dict[int, list[int]] = {}
    loop_index = 0
    loops = caps[0][3]
    cursor = 0
    for li, (loop, _outer) in enumerate(loops):
        bottom_edges[li] = []
        top_edges[li] = []
        m = len(loop)
        for i in range(m):
            sp = sides[cursor]
            cursor += 1
            p1 = (loop[i][0], loop[i][1])
            p2 = (loop[(i + 1) % m][0], loop[(i + 1) % m][1])
            if sp[0] == "cyl":
                eb = arc_edge(sp[1], z0)
                et = arc_edge(sp[1], z1)
                cx, cy, r, start, theta, _, _ = sp[1]
                axis = _axis(ids, _pt(ids, cx, cy, z0), _dir(ids, 0.0, 0.0, 1.0),
                             _dir(ids, 1.0, 0.0, 0.0))
                surf = ids.add(f"CYLINDRICAL_SURFACE('',#{axis},{_f(r)})")
                same = ".T." if theta > 0 else ".F."
            else:
                eb = straight_edge(p1, p2, z0)
                et = straight_edge(p1, p2, z1)
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                ln = math.hypot(dx, dy)
                # 바깥 법선은 진행 방향 오른쪽이다.
                nx, ny = dy / ln, -dx / ln
                axis = _axis(ids, _pt(ids, p1[0], p1[1], z0),
                             _dir(ids, nx, ny, 0.0), _dir(ids, dx / ln, dy / ln, 0.0))
                surf = ids.add(f"PLANE('',#{axis})")
                same = ".T."
            bottom_edges[li].append(eb)
            top_edges[li].append(et)
            ev1 = vertical_edge(p2, z0, z1)
            ev2 = vertical_edge(p1, z0, z1)
            oe = [ids.add(f"ORIENTED_EDGE('',*,*,#{eb},.T.)"),
                  ids.add(f"ORIENTED_EDGE('',*,*,#{ev1},.T.)"),
                  ids.add(f"ORIENTED_EDGE('',*,*,#{et},.F.)"),
                  ids.add(f"ORIENTED_EDGE('',*,*,#{ev2},.F.)")]
            el = ids.add("EDGE_LOOP('',(" + ",".join(f"#{e}" for e in oe) + "))")
            fb = ids.add(f"FACE_OUTER_BOUND('',#{el},.T.)")
            faces.append(ids.add(f"ADVANCED_FACE('',(#{fb}),#{surf},{same})"))
        loop_index += 1

    # 위·아래 평면
    for z, sign in ((z1, +1), (z0, -1)):
        axis = _axis(ids, _pt(ids, 0.0, 0.0, z), _dir(ids, 0.0, 0.0, float(sign)),
                     _dir(ids, 1.0, 0.0, 0.0))
        surf = ids.add(f"PLANE('',#{axis})")
        bounds = []
        for li, (loop, outer) in enumerate(loops):
            edges = top_edges[li] if z == z1 else bottom_edges[li]
            # 위에서 보면 윤곽 방향 그대로, 아래에서 보면 뒤집어야 반시계다.
            if sign > 0:
                oe = [ids.add(f"ORIENTED_EDGE('',*,*,#{e},.T.)") for e in edges]
            else:
                oe = [ids.add(f"ORIENTED_EDGE('',*,*,#{e},.F.)")
                      for e in reversed(edges)]
            el = ids.add("EDGE_LOOP('',(" + ",".join(f"#{e}" for e in oe) + "))")
            kind = "FACE_OUTER_BOUND" if outer else "FACE_BOUND"
            bounds.append(ids.add(f"{kind}('',#{el},.T.)"))
        faces.append(ids.add("ADVANCED_FACE('',(" + ",".join(f"#{b}" for b in bounds)
                             + f"),#{surf},.T.)"))
    return ids.add("CLOSED_SHELL('',(" + ",".join(f"#{f}" for f in faces) + "))")


def _write_cone(ids: _Ids, sol: Solid) -> int:
    """잘린 원뿔 껍질을 CONICAL_SURFACE 네 장과 고리면 두 장으로 푼다.

    한 바퀴 도는 면은 이음선(seam)이 필요하다. 원을 반씩 둘로 끊어 면을
    두 장으로 나누면 이음선이 자연히 생기고, 구멍을 반원 두 개로 그리는
    이 모듈의 다른 곳과도 같은 방식이 된다.
    """
    (rb, rt, dr, z0, z1) = next(sp[1] for sp in sol.spec if sp[0] == "cone")
    h = z1 - z0
    half = math.atan2(rb - rt, h)              # 위로 갈수록 좁아진다

    def pt(r, ang, z):
        return (r * math.cos(ang), r * math.sin(ang), z)

    vcache: dict[tuple, int] = {}

    def vertex(p):
        key = tuple(round(v, 7) for v in p)
        if key not in vcache:
            vcache[key] = ids.add(f"VERTEX_POINT('',#{_pt(ids, *p)})")
        return vcache[key]

    def arc(r, z, a0, a1):
        p0, p1 = pt(r, a0, z), pt(r, a1, z)
        axis = _axis(ids, _pt(ids, 0.0, 0.0, z), _dir(ids, 0.0, 0.0, 1.0),
                     _dir(ids, 1.0, 0.0, 0.0))
        circ = ids.add(f"CIRCLE('',#{axis},{_f(r)})")
        return ids.add(f"EDGE_CURVE('',#{vertex(p0)},#{vertex(p1)},#{circ},.T.)")

    def seam(r0, r1, ang):
        p0, p1 = pt(r0, ang, z0), pt(r1, ang, z1)
        d = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        ln = math.sqrt(sum(v * v for v in d))
        dirn = _dir(ids, d[0] / ln, d[1] / ln, d[2] / ln)
        vec = ids.add(f"VECTOR('',#{dirn},{_f(ln)})")
        line = ids.add(f"LINE('',#{_pt(ids, *p0)},#{vec})")
        return ids.add(f"EDGE_CURVE('',#{vertex(p0)},#{vertex(p1)},#{line},.T.)")

    angles = (0.0, math.pi, 2.0 * math.pi)
    faces: list[int] = []
    rings: dict[tuple[str, float], list[int]] = {}
    for tag, r_b, r_t, outward in (("out", rb, rt, True), ("in", rb - dr, rt - dr, False)):
        bottom = [arc(r_b, z0, angles[i], angles[i + 1]) for i in range(2)]
        top = [arc(r_t, z1, angles[i], angles[i + 1]) for i in range(2)]
        rings[(tag, z0)] = bottom
        rings[(tag, z1)] = top
        seams = [seam(r_b, r_t, angles[i]) for i in range(2)]
        # 원뿔면의 자연 법선은 축에서 바깥을 본다. 안쪽 면은 뒤집는다.
        apex_r = r_b
        place = _axis(ids, _pt(ids, 0.0, 0.0, z0), _dir(ids, 0.0, 0.0, -1.0),
                      _dir(ids, 1.0, 0.0, 0.0))
        surf = ids.add(f"CONICAL_SURFACE('',#{place},{_f(apex_r)},{_f(half)})")
        for i in range(2):
            oe = [ids.add(f"ORIENTED_EDGE('',*,*,#{bottom[i]},.T.)"),
                  ids.add(f"ORIENTED_EDGE('',*,*,#{seams[(i + 1) % 2]},.T.)"),
                  ids.add(f"ORIENTED_EDGE('',*,*,#{top[i]},.F.)"),
                  ids.add(f"ORIENTED_EDGE('',*,*,#{seams[i]},.F.)")]
            if not outward:
                oe = list(reversed(oe))
            el = ids.add("EDGE_LOOP('',(" + ",".join(f"#{e}" for e in oe) + "))")
            fb = ids.add(f"FACE_OUTER_BOUND('',#{el},.T.)")
            faces.append(ids.add(f"ADVANCED_FACE('',(#{fb}),#{surf},"
                                 f"{'.T.' if outward else '.F.'})"))

    for z, up in ((z1, +1), (z0, -1)):
        axis = _axis(ids, _pt(ids, 0.0, 0.0, z), _dir(ids, 0.0, 0.0, float(up)),
                     _dir(ids, 1.0, 0.0, 0.0))
        surf = ids.add(f"PLANE('',#{axis})")
        bounds = []
        for tag, outer in (("out", True), ("in", False)):
            edges = rings[(tag, z)]
            forward = (up > 0) == outer
            if forward:
                oe = [ids.add(f"ORIENTED_EDGE('',*,*,#{e},.T.)") for e in edges]
            else:
                oe = [ids.add(f"ORIENTED_EDGE('',*,*,#{e},.F.)")
                      for e in reversed(edges)]
            el = ids.add("EDGE_LOOP('',(" + ",".join(f"#{e}" for e in oe) + "))")
            kind = "FACE_OUTER_BOUND" if outer else "FACE_BOUND"
            bounds.append(ids.add(f"{kind}('',#{el},.T.)"))
        faces.append(ids.add("ADVANCED_FACE('',(" + ",".join(f"#{b}" for b in bounds)
                             + f"),#{surf},.T.)"))
    return ids.add("CLOSED_SHELL('',(" + ",".join(f"#{f}" for f in faces) + "))")


def cone_volume_mm3(r_bottom_out: float, r_top_out: float, height: float,
                    thickness: float) -> float:
    """잘린 원뿔 껍질의 해석 부피 — 시험이 STEP 과 맞춰 본다."""
    slope = math.hypot(height, r_bottom_out - r_top_out)
    dr = thickness * slope / height

    def frustum(r0: float, r1: float) -> float:
        return math.pi * height / 3.0 * (r0 * r0 + r0 * r1 + r1 * r1)

    return frustum(r_bottom_out, r_top_out) - frustum(r_bottom_out - dr, r_top_out - dr)


def write(path, solids: list[Solid], name: str = "MP-50") -> int:
    """솔리드 하나 이상을 한 STEP 파일로 쓴다. 쓴 바이트 수를 돌려준다."""
    import pathlib

    ids = _Ids()
    ctx, pds = _header(ids, name)
    shells = []
    for s in solids:
        if any(sp[0] == "cone" for sp in s.spec):
            shells.append((s.name, _write_cone(ids, s)))
        else:
            shells.append((s.name, _write_extrusion(ids, s)))
    origin = _axis(ids, _pt(ids, 0.0, 0.0, 0.0), _dir(ids, 0.0, 0.0, 1.0),
                   _dir(ids, 1.0, 0.0, 0.0))
    breps = [ids.add(f"MANIFOLD_SOLID_BREP('{esc(nm)}',#{sh})") for nm, sh in shells]
    items = ",".join(f"#{b}" for b in breps) + f",#{origin}"
    rep = ids.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION('{esc(name)}',({items}),#{ctx})")
    ids.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{rep})")

    stamp = _dt.datetime(2026, 9, 10, tzinfo=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    head = (
        "ISO-10303-21;\nHEADER;\n"
        f"FILE_DESCRIPTION(('{esc(name)}'),'2;1');\n"
        f"FILE_NAME('{esc(name)}','{stamp}',('Dynamic Industry'),('Dynamic Industry'),"
        "'mp50_cad','MP-50','');\n"
        f"FILE_SCHEMA(('{SCHEMA}'));\nENDSEC;\nDATA;\n")
    body = "\n".join(ids.lines)
    text = head + body + "\nENDSEC;\nEND-ISO-10303-21;\n"
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("ascii")
    p.write_bytes(data)
    return len(data)


def parse_entities(text: str) -> dict[int, tuple[str, str]]:
    """STEP 을 {번호: (엔티티명, 인자문자열)} 로 되읽는다 — 시험이 쓴다."""
    out: dict[int, tuple[str, str]] = {}
    body = text.split("DATA;", 1)[1].rsplit("ENDSEC;", 1)[0]
    for chunk in body.split(";"):
        chunk = chunk.strip()
        if not chunk.startswith("#"):
            continue
        ref, _, rest = chunk.partition("=")
        rest = rest.strip()
        name, _, args = rest.partition("(")
        out[int(ref[1:])] = (name.strip(), args.rstrip(")"))
    return out
