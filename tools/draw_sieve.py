#!/usr/bin/env python3
"""SV-01 원형 시브 도면 생성기 — 2D 총조립도 · 3D · 분해도 · 조립도 · 정비도.

치수를 코드에 두어 설계 변경이 도면에 자동 반영되게 한다.
출력은 자립형 SVG 이며 artifact 에 그대로 삽입한다.

    python3 tools/draw_sieve.py -o drawings/
"""
import argparse
import math
import os

# ── 주요 치수 [mm] ───────────────────────────────────────────────
D = dict(
    body_od=1200,          # 스크린 프레임 외경
    screen_od=1138,        # 유효 체면 (면적 1.02 m2)
    deck_h=120,            # 데크 1 단 높이
    n_deck=4,              # 3 메쉬 + 팬
    cover_h=150,
    base_h=400,
    base_od=900,
    spring_h=120,
    motor_h=330, motor_od=260,
    feed_id=150,
    spout_l=190, spout_h=95,
    clamp_n=8,
)
DECKS = [("280 µm", "280 µm O/S — 조대 폴리머 → P3"),
         ("106 µm", "106~280 µm O/S → CC-01"),
         ("75 µm", "75~106 µm O/S → CC-01"),
         ("PAN", "< 75 µm — 실리콘+은 → P1")]

PART = [
    (1,  "피드 호퍼 · 상부 커버", "STS304 t3",           1),
    (2,  "스크린 프레임 (280 µm)", "STS304 / 메쉬 STS316", 1),
    (3,  "스크린 프레임 (106 µm)", "STS304 / 메쉬 STS316", 1),
    (4,  "스크린 프레임 (75 µm)",  "STS304 / 메쉬 STS316", 1),
    (5,  "볼 데크 (백업)",        "STS304 + 실리콘 볼",   3),
    (6,  "팬 (하부 배출반)",       "STS304 t3",           1),
    (7,  "실리콘 개스킷",          "백색 실리콘 FDA",      4),
    (8,  "토글 클램프 링",         "STS304",              D["clamp_n"]),
    (9,  "초음파 트랜스듀서",       "35 kHz · 200 W",      3),
    (10, "초음파 제너레이터",       "3 ch · 600 W",        1),
    (11, "베이스 링 (앵커)",        "SS400 도장",          1),
    (17, "진동 테이블 (모터 캐리어)", "SS400 / STS304 클래드", 1),
    (12, "코일 스프링",           "SUP9 Ø60×120",        6),
    (13, "수직축 진동모터",         "2.2 kW · 960 rpm",    1),
    (14, "상·하 불평형추",         "주조강",              2),
    (15, "배출 슈트",             "STS304",              4),
    (16, "접지 본딩 스트랩",        "동편조선 · 방폭",       6),
]


# ── SVG 헬퍼 ────────────────────────────────────────────────────
class Svg:
    def __init__(self, w, h, title=""):
        self.w, self.h, self.o = w, h, []
        self.title = title

    def add(self, s):
        self.o.append(s)
        return self

    def rect(self, x, y, w, h, cls="ln", extra=""):
        return self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
                        f'height="{h:.1f}" class="{cls}" {extra}/>')

    def line(self, x1, y1, x2, y2, cls="ln"):
        return self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                        f'y2="{y2:.1f}" class="{cls}"/>')

    def path(self, d, cls="ln"):
        return self.add(f'<path d="{d}" class="{cls}"/>')

    def poly(self, pts, cls="ln"):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        return self.add(f'<polygon points="{p}" class="{cls}"/>')

    def circle(self, cx, cy, r, cls="ln"):
        return self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                        f'class="{cls}"/>')

    def text(self, x, y, s, cls="t", anchor="start", rot=None):
        tr = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else ""
        return self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" '
                        f'text-anchor="{anchor}"{tr}>{s}</text>')

    def dim_h(self, x1, x2, y, label, off=0):
        """수평 치수선."""
        self.line(x1, y - 5, x1, y + 5, "dim")
        self.line(x2, y - 5, x2, y + 5, "dim")
        self.add(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
                 f'class="dim" marker-start="url(#ar)" marker-end="url(#ar)"/>')
        self.text((x1 + x2) / 2, y - 6 + off, label, "td", "middle")
        return self

    def dim_v(self, y1, y2, x, label):
        self.line(x - 5, y1, x + 5, y1, "dim")
        self.line(x - 5, y2, x + 5, y2, "dim")
        self.add(f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" '
                 f'class="dim" marker-start="url(#ar)" marker-end="url(#ar)"/>')
        self.text(x - 7, (y1 + y2) / 2, label, "td", "middle",
                  rot=-90)
        return self

    def balloon(self, x, y, n, tx, ty):
        self.line(x, y, tx, ty, "lead")
        self.circle(tx, ty, 11, "bal")
        self.text(tx, ty + 4, str(n), "tb", "middle")
        return self

    def dump(self):
        return (f'<svg viewBox="0 0 {self.w} {self.h}" role="img" '
                f'aria-label="{self.title}">\n' + DEFS + "\n"
                + "\n".join(self.o) + "\n</svg>")


DEFS = '''<defs>
<marker id="ar" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6"
  markerHeight="6" orient="auto"><path d="M0,2 L6,5 L0,8 z" fill="currentColor"/></marker>
<pattern id="hatch" width="7" height="7" patternTransform="rotate(45)"
  patternUnits="userSpaceOnUse">
  <line x1="0" y1="0" x2="0" y2="7" style="stroke:currentColor;stroke-width:1;opacity:.35"/>
</pattern>
</defs>
<style>
.ln{fill:none;stroke:currentColor;stroke-width:1.6}
.ln2{fill:none;stroke:currentColor;stroke-width:1.1}
.thin{fill:none;stroke:currentColor;stroke-width:.8;opacity:.55}
.hid{fill:none;stroke:currentColor;stroke-width:.9;stroke-dasharray:6 4;opacity:.5}
.ctr{fill:none;stroke:currentColor;stroke-width:.8;stroke-dasharray:14 3 3 3;opacity:.55}
.dim{fill:none;stroke:currentColor;stroke-width:.9;opacity:.75}
.lead{fill:none;stroke:currentColor;stroke-width:.8;opacity:.6}
.fillA{fill:var(--c1-wash,rgba(180,101,42,.12));stroke:currentColor;stroke-width:1.4}
.fillB{fill:var(--c2-wash,rgba(176,53,122,.12));stroke:currentColor;stroke-width:1.4}
.fillC{fill:var(--c3-wash,rgba(0,113,176,.12));stroke:currentColor;stroke-width:1.4}
.fillG{fill:currentColor;fill-opacity:.07;stroke:currentColor;stroke-width:1.4}
.hatchf{fill:url(#hatch);stroke:currentColor;stroke-width:1.4}
.bal{fill:var(--surface,#fff);stroke:currentColor;stroke-width:1.2}
.t{font-family:var(--ff-body,system-ui);font-size:12px;fill:currentColor}
.ts{font-family:var(--ff-body,system-ui);font-size:10.5px;fill:currentColor;opacity:.8}
.td{font-family:var(--ff-mono,monospace);font-size:10.5px;fill:currentColor;opacity:.85}
.tb{font-family:var(--ff-mono,monospace);font-size:11px;font-weight:700;fill:currentColor}
.th{font-family:var(--ff-body,system-ui);font-size:13px;font-weight:700;fill:currentColor}
</style>'''


# ── 시트 1 : 2D 총조립도 (정면 단면 + 평면) ──────────────────────
LEVELS = dict(base=(0, 260), spring=(260, 420), table=(420, 520), pan=(520, 640),
              d75=(640, 760), d106=(760, 880), d250=(880, 1000),
              cover=(1000, 1150), feed=(1150, 1210))
SPOUT_Z = {"d250": (940, +1), "d106": (820, -1), "d75": (700, +1),
           "pan": (580, -1)}


def ga_drawing():
    s = 0.40
    cx, y0 = 360.0, 730.0
    X = lambda mm: cx + mm * s
    Y = lambda mm: y0 - mm * s
    g = Svg(1440, 900, "SV-01 원형 시브 총조립도 — 정면 단면과 평면")
    R, RB = D["body_od"] / 2, D["base_od"] / 2
    wall = 15

    g.text(40, 36, "SHEET 1 — 총조립도 (GENERAL ARRANGEMENT)", "th")
    g.text(40, 56, "SV-01 다단 원형 시브 Ø1200 · 3 메쉬 + 팬 · 초음파 3단 · 최대 350 kg/h", "ts")
    g.text(cx, 96, "정면 단면 A-A", "th", "middle")

    # 베이스 링(앵커) — 모터가 지나가도록 속이 비어 있다
    b0, b1 = LEVELS["base"]
    for side in (-1, 1):
        g.rect(X(side * RB) - (0 if side < 0 else 46), Y(b1), 46, (b1 - b0) * s, "fillG")
    g.rect(X(-RB), Y(b0 + 26), 2 * RB * s, 26 * s, "fillG")
    g.line(X(-RB), Y(b0 + 130), X(-RB) - 30, Y(b0 + 130), "lead")
    g.text(X(-RB) - 34, Y(b0 + 130) + 4, "베이스 링 Ø900 (앵커)", "ts", "end")

    # 스프링 — 베이스 링과 진동 테이블 사이. 가진원을 절연하는 것이 아니라
    # 진동체 전체(테이블+모터+데크)를 바닥에서 절연한다.
    sp0, sp1 = LEVELS["spring"]
    for sx in (-RB * 0.78, RB * 0.78):
        g.rect(X(sx) - 17, Y(sp0), 34, (sp0 - b0 - 26) * s, "fillG")
    for sx in (-RB * 0.78, RB * 0.78):
        n, top, bot = 7, Y(sp1), Y(sp0)
        d = f"M{X(sx) - 13:.1f},{bot:.1f}"
        for i in range(n * 2):
            d += (f" L{X(sx) + (13 if i % 2 == 0 else -13):.1f},"
                  f"{bot - (bot - top) * (i + 1) / (n * 2):.1f}")
        g.path(d, "ln2")
    g.text(40, Y((sp0 + sp1) / 2) + 4, "코일스프링 6 EA", "ts")

    # 진동 테이블 + 모터 — 모터는 테이블 하면에 볼트 체결되어 스프링 위에서
    # 데크와 함께 진동한다. 베이스 공동으로 내려와 있을 뿐 베이스와 닿지 않는다.
    t0, t1 = LEVELS["table"]
    g.rect(X(-RB * 0.92), Y(t1), 2 * RB * 0.92 * s, (t1 - t0) * s, "fillG")
    mh, mo = D["motor_h"] * s, D["motor_od"] * s
    g.rect(X(0) - mo / 2, Y(t0), mo, mh, "hatchf")
    g.text(X(0), Y(t0 - D["motor_h"] / 2) + 4, "M", "tb", "middle")
    g.line(X(0) + mo / 2, Y(t0 - 140), X(RB) + 26, Y(t0 - 140), "lead")
    g.text(X(RB) + 32, Y(t0 - 140) + 4, "수직축 진동모터 2.2 kW · 960 rpm", "ts")
    g.text(X(RB) + 32, Y(t0 - 140) + 20, "— 진동 테이블 하면 체결 (스프링 위)", "ts")
    for zz, lab in ((t0 - 22, "불평형추 (상)"),
                    (t0 - D["motor_h"] + 2, "불평형추 (하)")):
        g.rect(X(0) - mo * 0.44, Y(zz), mo * 0.88, 20 * s, "fillA")
        g.line(X(0) - mo * 0.44, Y(zz - 8), X(-RB) + 14, Y(zz - 8), "lead")
        g.text(X(-RB) + 10, Y(zz - 8) + 4, lab, "ts", "end")

    # 데크 스택
    order = [("pan", "PAN (배출반)", None),
             ("d75", "75 µm 메쉬", "STS316 평직"),
             ("d106", "106 µm 메쉬", "STS316 평직"),
             ("d250", "280 µm 메쉬", "STS316 평직 · 상단")]
    for key, label, sub in order:
        z0, z1 = LEVELS[key]
        g.rect(X(-R), Y(z1), wall, (z1 - z0) * s, "hatchf")
        g.rect(X(R) - wall, Y(z1), wall, (z1 - z0) * s, "hatchf")
        if key != "pan":
            yy = Y(z0 + 18)
            g.line(X(-R) + wall, yy, X(R) - wall, yy, "ln")
            for k in range(52):
                xx = X(-R) + wall + (2 * R * s - 2 * wall) * k / 51
                g.line(xx, yy - 3, xx, yy + 3, "thin")
            g.text(X(0), yy - 8, label, "td", "middle")
            if sub:
                g.text(X(0), yy + 15, sub, "ts", "middle")
        else:
            g.path(f"M{X(-R) + wall:.1f},{Y(z0 + 30):.1f} "
                   f"Q{X(0):.1f},{Y(z0 - 12):.1f} "
                   f"{X(R) - wall:.1f},{Y(z0 + 30):.1f}", "ln")
            g.text(X(0), Y(z0 + 62), label, "td", "middle")
        g.line(X(-R), Y(z1), X(R), Y(z1), "thin")

    # 커버 · 피드
    c0, c1 = LEVELS["cover"]
    g.path(f"M{X(-R):.1f},{Y(c0):.1f} L{X(-R):.1f},{Y(c0 + 40):.1f} "
           f"L{X(-D['feed_id'] / 2):.1f},{Y(c1):.1f} "
           f"L{X(D['feed_id'] / 2):.1f},{Y(c1):.1f} "
           f"L{X(R):.1f},{Y(c0 + 40):.1f} L{X(R):.1f},{Y(c0):.1f} Z", "fillG")
    f0, f1 = LEVELS["feed"]
    g.rect(X(-D["feed_id"] / 2), Y(f1), D["feed_id"] * s, (f1 - f0) * s, "fillG")
    g.text(X(0), Y(f1) - 10, "피드 인렛 Ø150", "td", "middle")

    # 배출 슈트 — 전부 우측, 데크 높이별로 라벨이 겹치지 않는다
    SHORT = {"d250": "280 O/S → P3", "d106": "106 O/S → CC-01",
             "d75": "75 O/S → CC-01", "pan": "PAN U/S → P1"}
    for key in ("d250", "d106", "d75", "pan"):
        zz = SPOUT_Z[key][0]
        x_in, x_out = X(R), X(R) + D["spout_l"] * s
        h = D["spout_h"] * s
        g.poly([(x_in, Y(zz + 42)), (x_out, Y(zz + 20)),
                (x_out, Y(zz + 20) + h), (x_in, Y(zz + 42) + h)], "fillG")
        g.text(x_out + 8, Y(zz + 20) + h / 2 + 4, SHORT[key], "td")

    # 초음파 트랜스듀서 — 좌측
    for key in ("d250", "d106", "d75"):
        z0, _ = LEVELS[key]
        g.rect(X(-R) - 26, Y(z0 + 82), 26, 22, "fillA")
    g.text(74, Y((LEVELS["d75"][0] + LEVELS["d250"][1]) / 2),
           "초음파 트랜스듀서 35 kHz × 3", "ts", "middle", rot=-90)

    # 중심선 · 치수
    g.line(X(0), Y(1250), X(0), Y(-30), "ctr")
    g.dim_h(X(-R), X(R), 762, "Ø1200")
    g.dim_v(Y(1000), Y(520), X(R) + 250, "480 = 120 × 4단")
    g.dim_v(Y(1210), Y(0), X(R) + 320, "1210")
    g.text(cx, 792, "치수 mm · 축척 NTS · 절단선 A-A 는 평면 B 참조", "td", "middle")

    # ── 평면도 ──
    pcx, pcy, ps = 1080.0, 400.0, 0.28
    g.text(pcx, 96, "평면 B (커버 제거)", "th", "middle")
    g.circle(pcx, pcy, R * ps, "fillG")
    g.circle(pcx, pcy, D["screen_od"] / 2 * ps, "ln2")
    g.circle(pcx, pcy, D["feed_id"] / 2 * ps, "ln")
    g.text(pcx, pcy + 4, "피드", "td", "middle")
    for k in range(D["clamp_n"]):
        a = 2 * math.pi * k / D["clamp_n"] + math.pi / 8
        g.circle(pcx + R * ps * math.cos(a), pcy + R * ps * math.sin(a), 7, "fillA")
    ang = {"d250": 0, "pan": 60, "d106": 120, "d75": 240}
    for key, a_deg in ang.items():
        a = math.radians(a_deg)
        ca, sa = math.cos(a), math.sin(a)
        g.line(pcx + R * ps * ca, pcy - R * ps * sa,
               pcx + (R + D["spout_l"]) * ps * ca, pcy - (R + D["spout_l"]) * ps * sa, "ln")
        ex, ey = pcx + (R + D["spout_l"]) * ps * ca, pcy - (R + D["spout_l"]) * ps * sa
        g.circle(ex, ey, 9, "fillC")
        g.text(ex + 15 * ca, ey - 15 * sa + 4, SHORT[key].split(" →")[0], "td",
               "start" if ca >= 0 else "end")
    g.text(pcx, pcy + R * ps + 46, "배출구 120° 간격 — 슈트 간섭 회피", "ts", "middle")
    g.text(pcx, pcy + R * ps + 64, f"유효 체면 Ø{D['screen_od']} = 1.02 m²", "ts", "middle")
    g.text(pcx + R * ps + 30, pcy - R * ps - 6, f"토글 클램프 {D['clamp_n']} EA", "ts")

    # 배출 범례
    g.text(60, 820, "배출 흐름", "th")
    rows = [("280 O/S", "280~500 µm 조대 폴리머 — 구리 없음 → P3 백시트"),
            ("106 O/S", "106~280 µm → CC-01 향류 컬럼 (합류)"),
            ("75 O/S", "75~106 µm → CC-01 향류 컬럼 (합류)"),
            ("PAN U/S", "< 75 µm 실리콘 + 은 농축물 → P1 침출")]
    for k, (a_, b_) in enumerate(rows):
        g.text(60, 842 + k * 17, a_, "td")
        g.text(150, 842 + k * 17, b_, "ts")

    # 표제란
    g.rect(1000, 800, 400, 84, "ln2")
    g.line(1000, 828, 1400, 828, "ln2")
    g.line(1210, 800, 1210, 884, "ln2")
    g.text(1010, 819, "SV-01 다단 원형 시브", "th")
    g.text(1010, 846, "도번  DI-SV01-GA-01", "td")
    g.text(1010, 867, "축척  NTS · 단위 mm", "td")
    g.text(1220, 846, "Rev.  5", "td")
    g.text(1220, 867, "재질  STS304 / 메쉬 316", "td")
    return g.dump()


# ── 아이소메트릭 헬퍼 ───────────────────────────────────────────
RY = 0.17                      # 원 -> 타원 축비. 데크가 Ø1200x120 인 납작한 링이라 얕게 본다


def iso_cyl(g, cx, cy, rx, h, cls="fillG", top=True, ry=None):
    """수직 원통. cy 는 상면 중심. 상면 타원 + 몸통 실루엣."""
    ry = ry if ry is not None else rx * RY
    g.path(f"M{cx - rx:.1f},{cy:.1f} L{cx - rx:.1f},{cy + h:.1f} "
           f"A{rx:.1f},{ry:.1f} 0 0 0 {cx + rx:.1f},{cy + h:.1f} "
           f"L{cx + rx:.1f},{cy:.1f} "
           f"A{rx:.1f},{ry:.1f} 0 0 1 {cx - rx:.1f},{cy:.1f} Z", cls)
    if top:
        g.add(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" '
              f'ry="{ry:.1f}" class="{cls}"/>')
    return g


def iso_mesh(g, cx, cy, rx, ry=None, n=13):
    """상면에 체 메쉬 격자."""
    ry = ry if ry is not None else rx * RY
    g.add(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
          f'class="fillC"/>')
    for k in range(1, n):
        t = -1 + 2 * k / n
        x = cx + rx * t
        dy = ry * math.sqrt(max(0.0, 1 - t * t))
        g.line(x, cy - dy, x, cy + dy, "thin")
        y = cy + ry * t
        dx = rx * math.sqrt(max(0.0, 1 - t * t))
        g.line(cx - dx, y, cx + dx, y, "thin")
    return g


def iso_spout(g, cx, cy, rx, ang_deg, ry=None, ln=64):
    """측면 배출 슈트 — 아이소메트릭 위치에 사다리꼴로."""
    ry = ry if ry is not None else rx * RY
    a = math.radians(ang_deg)
    x0, y0 = cx + rx * math.cos(a), cy + ry * math.sin(a)
    x1, y1 = cx + (rx + ln) * math.cos(a), cy + (ry + ln * RY) * math.sin(a)
    g.poly([(x0, y0 - 11), (x1, y1 - 8), (x1, y1 + 12), (x0, y0 + 15)], "fillG")
    return x1, y1


# ── 시트 2 : 3D 외관 ────────────────────────────────────────────
def iso_drawing():
    g = Svg(1160, 900, "SV-01 원형 시브 3D 외관 아이소메트릭")
    g.text(40, 36, "SHEET 2 — 3D 외관 (ISOMETRIC)", "th")
    g.text(40, 56, "SV-01 다단 원형 시브 · 조립 상태", "ts")
    cx, rx = 560.0, 210.0
    S = rx / (D["body_od"] / 2)
    ry = rx * RY
    y = 190.0
    LX, RXL = 320.0, cx + rx + 90        # 좌 라벨 우단 · 우 라벨 좌단

    iso_cyl(g, cx, y, D["feed_id"] / 2 * S, 60 * S)
    g.text(cx, y - D["feed_id"] / 2 * S * RY - 16, "피드 인렛 Ø150", "td", "middle")
    y += 60 * S

    ch, r_f = D["cover_h"] * S, D["feed_id"] / 2 * S
    g.path(f"M{cx - r_f:.1f},{y:.1f} L{cx - rx:.1f},{y + ch:.1f} "
           f"A{rx:.1f},{ry:.1f} 0 0 0 {cx + rx:.1f},{y + ch:.1f} "
           f"L{cx + r_f:.1f},{y:.1f} "
           f"A{r_f:.1f},{r_f * RY:.1f} 0 0 1 {cx - r_f:.1f},{y:.1f} Z", "fillG")
    g.line(cx - rx * 0.75, y + ch * 0.45, LX + 8, y + ch * 0.45, "lead")
    g.text(LX, y + ch * 0.45 + 4, "상부 커버 (탈착)", "ts", "end")
    y += ch

    dh = D["deck_h"] * S
    decks = [("280 µm 데크", "280 O/S → P3"), ("106 µm 데크", "106 O/S → CC-01"),
             ("75 µm 데크", "75 O/S → CC-01"), ("PAN (배출반)", "PAN U/S → P1")]
    for k, (lab, spout) in enumerate(decks):
        iso_cyl(g, cx, y, rx, dh, "fillG", top=False)
        if k < 3:
            iso_mesh(g, cx, y + 3, rx * 0.93, rx * 0.93 * RY, n=15)
        ex, ey = iso_spout(g, cx, y + dh * 0.5, rx, -20)
        g.text(RXL, ey + 5, spout, "td")
        g.line(ex + 4, ey + 1, RXL - 8, ey + 1, "lead")
        g.add(f'<ellipse cx="{cx:.1f}" cy="{y + dh:.1f}" rx="{rx:.1f}" '
              f'ry="{ry:.1f}" class="ln2"/>')
        g.line(cx - rx, y + dh * 0.5, LX + 8, y + dh * 0.5, "lead")
        g.text(LX, y + dh * 0.5 + 4, lab, "ts", "end")
        if k < 3:
            g.rect(cx - rx - 22, y + dh * 0.28, 22, 15, "fillA")
        y += dh

    sh = D["spring_h"] * S
    for sx in (-rx * 0.70, rx * 0.70):
        n2, t_, b_ = 6, y, y + sh
        d = f"M{cx + sx - 10:.1f},{t_:.1f}"
        for i in range(n2 * 2):
            d += (f" L{cx + sx + (10 if i % 2 == 0 else -10):.1f},"
                  f"{t_ + (b_ - t_) * (i + 1) / (n2 * 2):.1f}")
        g.path(d, "ln2")
    g.text(RXL, y + sh * 0.6 + 4, "코일스프링 6 EA", "ts")
    g.line(cx + rx * 0.70 + 12, y + sh * 0.6, RXL - 8, y + sh * 0.6, "lead")
    y += sh

    rb = D["base_od"] / 2 * S
    bh = D["base_h"] * S
    iso_cyl(g, cx, y, rb, bh, "fillG")
    g.line(cx - rb, y + bh * 0.5, LX + 8, y + bh * 0.5, "lead")
    g.text(LX, y + bh * 0.5 + 4, "베이스 링 Ø900 (앵커)", "ts", "end")
    g.text(LX, y + bh * 0.5 + 20, "진동모터는 스프링 위 진동 테이블에 체결", "ts", "end")

    # 초음파 제너레이터 — 트랜스듀서 옆에 짧은 리더로
    gx, gy = 66.0, 252.0
    g.rect(gx, gy, 150, 76, "fillA")
    g.text(gx + 75, gy + 24, "초음파 제너레이터", "td", "middle")
    g.text(gx + 75, gy + 42, "3 ch · 600 W", "td", "middle")
    g.text(gx + 75, gy + 60, "→ 트랜스듀서 3 EA", "td", "middle")
    g.line(gx + 150, gy + 66, cx - rx - 24, 334, "lead")

    g.dim_v(190.0, y + bh, cx + rx + 330, "전고 1210")
    g.text(cx, 862, "축척 NTS · 그림에서는 슈트를 한쪽에 모아 그렸으나 실제 배치는 120° 간격이다 (Sheet 1 평면 B)",
           "ts", "middle")
    return g.dump()


# ── 시트 3 : 분해도 ─────────────────────────────────────────────
EXPLODE = [
    (1,  "피드 호퍼 · 상부 커버", 0.60, "cover"),
    (7,  "실리콘 개스킷", 0.10, "gasket"),
    (2,  "스크린 프레임 280 µm", 0.55, "deck"),
    (7,  "실리콘 개스킷", 0.10, "gasket"),
    (3,  "스크린 프레임 106 µm", 0.55, "deck"),
    (7,  "실리콘 개스킷", 0.10, "gasket"),
    (4,  "스크린 프레임 75 µm", 0.55, "deck"),
    (7,  "실리콘 개스킷", 0.10, "gasket"),
    (6,  "팬 (하부 배출반)", 0.55, "pan"),
    (12, "코일스프링 6 EA", 0.45, "spring"),
    (11, "베이스 프레임 · 진동모터", 0.90, "base"),
]


def exploded_drawing():
    g = Svg(1440, 1080, "SV-01 원형 시브 분해도와 부품표")
    g.text(40, 36, "SHEET 3 — 분해도 (EXPLODED VIEW) 및 부품표", "th")
    g.text(40, 56, "분해·조립은 반드시 전원 차단 · 잠금표지(LOTO) 후 시행한다", "ts")
    cx, rx = 430.0, 190.0
    S = rx / (D["body_od"] / 2)
    ry = rx * RY
    y = 130.0
    g.line(cx, 110, cx, 1010, "ctr")

    for pn, lab, hs, kind in EXPLODE:
        h = D["deck_h"] * S * hs * 1.9
        if kind == "gasket":
            g.add(f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="{rx:.1f}" '
                  f'ry="{ry:.1f}" class="fillB"/>')
            g.add(f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="{rx * 0.88:.1f}" '
                  f'ry="{ry * 0.88:.1f}" class="ln2"/>')
            hh = 10
        elif kind == "cover":
            r_f = D["feed_id"] / 2 * S
            g.path(f"M{cx - r_f:.1f},{y:.1f} L{cx - rx:.1f},{y + h:.1f} "
                   f"A{rx:.1f},{ry:.1f} 0 0 0 {cx + rx:.1f},{y + h:.1f} "
                   f"L{cx + r_f:.1f},{y:.1f} "
                   f"A{r_f:.1f},{r_f * RY:.1f} 0 0 1 {cx - r_f:.1f},{y:.1f} Z", "fillG")
            iso_cyl(g, cx, y - 26, r_f, 26)
            hh = h
        elif kind == "spring":
            for sx in (-rx * 0.66, rx * 0.66):
                n2, t_, b_ = 6, y, y + h
                d = f"M{cx + sx - 10:.1f},{t_:.1f}"
                for i in range(n2 * 2):
                    d += (f" L{cx + sx + (10 if i % 2 == 0 else -10):.1f},"
                          f"{t_ + (b_ - t_) * (i + 1) / (n2 * 2):.1f}")
                g.path(d, "ln2")
            hh = h
        elif kind == "base":
            rb = D["base_od"] / 2 * S
            iso_cyl(g, cx, y, rb, h, "fillG")
            g.rect(cx - 26, y + h * 0.25, 52, h * 0.5, "hatchf")
            g.text(cx, y + h * 0.55, "M", "tb", "middle")
            hh = h
        else:
            iso_cyl(g, cx, y, rx, h, "fillG", top=False)
            if kind == "deck":
                iso_mesh(g, cx, y + 2, rx * 0.9, rx * 0.9 * RY, n=13)
            else:
                g.add(f'<ellipse cx="{cx:.1f}" cy="{y + 2:.1f}" rx="{rx * 0.9:.1f}" '
                      f'ry="{rx * 0.9 * RY:.1f}" class="fillB"/>')
            hh = h
        g.balloon(cx - rx, y + hh * 0.5, pn, cx - rx - 70, y + hh * 0.5)
        g.text(cx - rx - 88, y + hh * 0.5 + 4, lab, "ts", "end")
        y += hh + 40

    # 토글 클램프 · 트랜스듀서 콜아웃
    g.balloon(cx + rx, 300, 8, cx + rx + 70, 300)
    g.text(cx + rx + 86, 304, "토글 클램프 8 EA — 데크 간 체결", "ts")
    g.balloon(cx + rx, 430, 9, cx + rx + 70, 430)
    g.text(cx + rx + 86, 434, "초음파 트랜스듀서 3 EA — 프레임 외주 볼트 고정", "ts")
    g.balloon(cx + rx, 560, 5, cx + rx + 70, 560)
    g.text(cx + rx + 86, 564, "볼 데크 (백업) — 초음파 정지 시 임시 운전용", "ts")

    # 부품표
    tx, ty = 760.0, 640.0
    g.text(tx, ty - 14, "부품표 (BOM)", "th")
    g.rect(tx, ty, 640, 36 + 17 * len(PART), "ln2")
    g.line(tx, ty + 26, tx + 640, ty + 26, "ln2")
    for x in (tx + 44, tx + 360, tx + 570):
        g.line(x, ty, x, ty + 36 + 17 * len(PART), "thin")
    for h_, x_ in (("No", tx + 10), ("품명", tx + 54), ("재질 · 사양", tx + 370),
                   ("수량", tx + 580)):
        g.text(x_, ty + 18, h_, "td")
    for k, (pn, nm, mat, qty) in enumerate(PART):
        yy = ty + 43 + k * 17
        g.text(tx + 10, yy, str(pn), "td")
        g.text(tx + 54, yy, nm, "ts")
        g.text(tx + 370, yy, mat, "ts")
        g.text(tx + 580, yy, str(qty), "td")
    g.text(tx, ty + 36 + 17 * len(PART) + 20,
           "※ 개스킷(7)은 분해 시마다 신품 교체. 재사용하면 데크 간 누설로 분획이 섞인다.", "ts")
    return g.dump()


# ── 시트 4 : 조립도 ─────────────────────────────────────────────
ASSY = [
    ("1", "베이스 링 앵커링", [
        "베이스 링을 레벨 ±0.5 mm/m 이내로 앵커링",
        "모터가 지나갈 중앙 공동의 간섭 여부 확인",
        "스프링 시트 청소·이물 제거"]),
    ("2", "진동 테이블 + 모터", [
        "진동모터를 테이블 하면에 체결 (모터는 반드시 스프링 위 진동체에)",
        "절연저항 ≥ 5 MΩ 확인 후 결선, 배선은 플렉시블 루프",
        "상·하 불평형추 위상각 45° (초기값) — 시운전에서 재조정",
        "스프링 6 EA(자유장 편차 ≤ 1 mm 짝) 위에 테이블 안착, 수평 ±1 mm"]),
    ("3", "데크 적층", [
        "아래에서부터 팬 → 75 → 106 → 280 µm 순으로 쌓는다",
        "데크마다 신품 실리콘 개스킷을 끼운다 (재사용 금지)",
        "배출구 방향이 120° 간격이 되도록 회전 정렬"]),
    ("4", "클램프 체결", [
        "토글 클램프 8 EA 를 대각선 순서로 2 회에 나누어 조인다",
        "체결 후 데크 간 단차 ≤ 0.5 mm",
        "메쉬 장력 — 손가락 압입 시 처짐 ≤ 2 mm"]),
    ("5", "초음파 · 커버", [
        "트랜스듀서 3 EA 를 프레임 외주에 볼트 고정 (18 N·m)",
        "제너레이터 배선 후 채널별 공진주파수 자동정합 실행",
        "상부 커버 장착, 피드 인렛에 플렉시블 연결"]),
    ("6", "시운전", [
        "무부하 5 분 — 이상음·편진동 확인",
        "진폭 실측: 수직 3~5 mm (스티커 게이지)",
        "가진강도 Γ = A(2πf)²/g 가 4~6 g 인지 확인",
        "부하 운전 후 분획별 오버사이즈 혼입률 2 % 이하 확인"]),
]


def assembly_drawing():
    g = Svg(1440, 860, "SV-01 조립 순서도")
    g.text(40, 36, "SHEET 4 — 조립도 (ASSEMBLY SEQUENCE)", "th")
    g.text(40, 56, "아래에서 위로 쌓는다. 각 단계의 확인 항목을 통과해야 다음으로 넘어간다.", "ts")

    # 상단 : 적층 순서 모식
    cx0, rx, S = 150.0, 92.0, 92.0 / (D["body_od"] / 2)
    ry = rx * RY
    seq = [("11", "베이스"), ("12", "스프링"), ("6", "팬"), ("4", "75 µm"),
           ("3", "106 µm"), ("2", "280 µm"), ("1", "커버")]
    for k, (pn, lab) in enumerate(seq):
        cx = cx0 + k * 190
        yb = 392.0
        for j in range(k + 1):
            hh = 26
            yy = yb - j * 26
            cls = "fillA" if j == k else "fillG"
            iso_cyl(g, cx, yy, rx if j > 0 else rx * 0.78, hh, cls, top=(j == k))
        g.text(cx, 116, lab, "td", "middle")
        g.circle(cx, 142, 13, "bal")
        g.text(cx, 147, str(k + 1), "tb", "middle")
        if k < len(seq) - 1:
            g.path(f"M{cx + rx + 12:.1f},344 L{cx + 190 - rx - 12:.1f},344", "dim")
            g.add(f'<path d="M{cx + 190 - rx - 18:.1f},339 L{cx + 190 - rx - 10:.1f},344 '
                  f'L{cx + 190 - rx - 18:.1f},349 z" fill="currentColor" opacity=".7"/>')

    # 하단 : 절차표
    y0 = 470.0
    g.text(40, y0 - 12, "조립 절차 및 확인 항목", "th")
    col_w = 460
    for c in range(3):
        for r in range(2):
            idx = c + 3 * r
            if idx >= len(ASSY):
                continue
            no, title, items = ASSY[idx]
            bx, by = 40 + c * col_w, y0 + r * 172
            g.rect(bx, by, col_w - 24, 152, "ln2")
            g.line(bx, by + 32, bx + col_w - 24, by + 32, "ln2")
            g.circle(bx + 22, by + 16, 12, "fillA")
            g.text(bx + 22, by + 21, no, "tb", "middle")
            g.text(bx + 44, by + 21, title, "th")
            for i, it in enumerate(items):
                g.text(bx + 16, by + 56 + i * 22, "·", "td")
                g.text(bx + 30, by + 56 + i * 22, it, "ts")
    g.text(40, 838, "※ 클램프는 반드시 대각선 순서로 2 회 분할 체결한다. 한 번에 조이면 개스킷이 편측 압축되어 데크 간 누설이 생긴다.", "ts")
    return g.dump()


# ── 시트 5 : 정비도 ─────────────────────────────────────────────
MAINT = [
    ("A", "메쉬 눈막힘 점검", "매 교대 (8 h)", "육안 + 광투과. 개방면적 90 % 미만이면 초음파 출력·주파수 정합 점검"),
    ("B", "초음파 트랜스듀서", "주 1 회", "채널별 소비전력 편차 ±10 % 이내. 벗어나면 정합 재실행 또는 소자 교체"),
    ("C", "실리콘 개스킷", "분해 시마다", "신품 교체. 재사용 시 데크 간 누설로 분획이 섞인다"),
    ("D", "메쉬 장력·손상", "월 1 회", "처짐 ≤ 2 mm. 핀홀 1 개도 은 손실로 직결되므로 발견 즉시 프레임 교체"),
    ("E", "토글 클램프", "월 1 회", "이완 여부 확인, 데크 간 단차 ≤ 0.5 mm"),
    ("F", "코일스프링", "6 개월", "자유장 편차 ≤ 1 mm, 균열·영구변형 시 6 EA 일괄 교체"),
    ("G", "진동모터 베어링", "3,000 h", "그리스 보충. 진동 실효치 급증 시 즉시 정지"),
    ("H", "불평형추 위상각", "진폭 이상 시", "수직 진폭 3~5 mm 로 재조정. Γ 4~6 g 유지"),
    ("I", "접지 본딩", "월 1 회", "저항 ≤ 1 Ω. 분진 폭발 방지 — 방폭 요구사항"),
]


def maintenance_drawing():
    g = Svg(1440, 800, "SV-01 정비도 — 정비 포인트와 주기")
    g.text(40, 36, "SHEET 5 — 정비도 (MAINTENANCE)", "th")
    g.text(40, 56, "은 회수율은 두 체(75 µm 데크 · SS-01)의 상태에 직결된다 — A·C·D 를 최우선으로 관리한다.", "ts")

    s = 0.34
    cx, y0 = 360.0, 660.0
    X = lambda mm: cx + mm * s
    Y = lambda mm: y0 - mm * s
    R, RB, wall = D["body_od"] / 2, D["base_od"] / 2, 12

    b0, b1 = LEVELS["base"]
    for side in (-1, 1):
        g.rect(X(side * RB) - (0 if side < 0 else 40), Y(b1), 40, (b1 - b0) * s, "fillG")
    t0, t1 = LEVELS["table"]
    g.rect(X(-RB * 0.92), Y(t1), 2 * RB * 0.92 * s, (t1 - t0) * s, "fillG")
    mo, mh = D["motor_od"] * s, D["motor_h"] * s
    g.rect(X(0) - mo / 2, Y(t0), mo, mh, "hatchf")
    sp0, sp1 = LEVELS["spring"]
    for sx in (-RB * 0.78, RB * 0.78):
        n2, t_, b_ = 6, Y(sp1), Y(sp0)
        d = f"M{X(sx) - 10:.1f},{b_:.1f}"
        for i in range(n2 * 2):
            d += (f" L{X(sx) + (10 if i % 2 == 0 else -10):.1f},"
                  f"{b_ - (b_ - t_) * (i + 1) / (n2 * 2):.1f}")
        g.path(d, "ln2")
    for key in ("pan", "d75", "d106", "d250"):
        z0, z1 = LEVELS[key]
        g.rect(X(-R), Y(z1), wall, (z1 - z0) * s, "hatchf")
        g.rect(X(R) - wall, Y(z1), wall, (z1 - z0) * s, "hatchf")
        if key != "pan":
            g.line(X(-R) + wall, Y(z0 + 18), X(R) - wall, Y(z0 + 18), "ln")
        g.line(X(-R), Y(z1), X(R), Y(z1), "thin")
    c0, c1 = LEVELS["cover"]
    g.path(f"M{X(-R):.1f},{Y(c0):.1f} L{X(-D['feed_id'] / 2):.1f},{Y(c1):.1f} "
           f"L{X(D['feed_id'] / 2):.1f},{Y(c1):.1f} L{X(R):.1f},{Y(c0):.1f} Z", "fillG")

    pts = {
        "A": (X(0), Y(LEVELS["d75"][0] + 18), X(0) + 30, Y(1265)),
        "B": (X(-R) - 8, Y(LEVELS["d106"][0] + 60), X(-R) - 80, Y(940)),
        "C": (X(-R) + 4, Y(LEVELS["d106"][1]), X(-R) - 80, Y(830)),
        "D": (X(R) - wall - 40, Y(LEVELS["d250"][0] + 18), X(R) + 70, Y(1010)),
        "E": (X(R), Y(LEVELS["d106"][1]), X(R) + 70, Y(880)),
        "F": (X(RB * 0.78), Y((sp0 + sp1) / 2), X(R) + 70, Y(560)),
        "G": (X(0) + mo / 2, Y(t0 - 160), X(R) + 70, Y(300)),
        "H": (X(0) - mo * 0.4, Y(t0 - 300), X(-R) - 80, Y(160)),
        "I": (X(-RB), Y(b0 + 60), X(-R) - 80, Y(30)),
    }
    for tag, (px, py, bx, by) in pts.items():
        g.balloon(px, py, tag, bx, by)

    tx, ty = 690.0, 130.0
    g.text(tx, ty - 16, "정비 항목 · 주기", "th")
    rows = 26 + 34 * len(MAINT)
    g.rect(tx, ty, 736, rows, "ln2")
    g.line(tx, ty + 26, tx + 736, ty + 26, "ln2")
    for x in (tx + 38, tx + 210, tx + 314):
        g.line(x, ty, x, ty + rows, "thin")
    for h_, x_ in (("표기", tx + 8), ("항목", tx + 50), ("주기", tx + 220),
                   ("판정 기준 · 조치", tx + 324)):
        g.text(x_, ty + 18, h_, "td")
    for k, (tag, item, per, crit) in enumerate(MAINT):
        yy = ty + 48 + k * 34
        g.circle(tx + 20, yy - 5, 11, "bal")
        g.text(tx + 20, yy - 1, tag, "tb", "middle")
        g.text(tx + 50, yy, item, "ts")
        g.text(tx + 220, yy, per, "td")
        g.text(tx + 324, yy, crit, "ts")
    g.text(tx, ty + rows + 26,
           "※ A·C·D 는 은 회수율에 직결된다. 이 셋을 놓치면 다른 정비를 아무리 잘해도 P1 회수율이 무너진다.", "ts")
    g.text(tx, ty + rows + 46,
           "※ 모든 정비는 전원 차단 · LOTO · 잔류 분진 퍼지 후 시행한다. 분진 폭발 위험 구역이다.", "ts")
    return g.dump()
