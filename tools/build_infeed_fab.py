# -*- coding: utf-8 -*-
"""투입 구간 제작 도면집 — 부품도 · 조립도 · 분해도 · 체결표 · 조립 순서.

`src/pv_preprocess/fabrication.py` 가 정본이다. 여기서는 그 데이터로 (1) 부품마다
3면도(정면·평면·측면)에 치수·두께·구멍을 넣은 부품도, (2) 조립체마다 등각 분해도와
부품표·체결표·조립 순서·검사표, (3) 총괄 사양(재질·체결 표준·토크·구멍·용접·도장·
공차)과 플랜트 설치 순서, 볼트·앵커 집계, 모델 대조표를 한 문서로 찍는다.

    PYTHONPATH=src python tools/build_infeed_fab.py

멱등이다. `tests/test_pv_infeed_fab.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import html
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign, fabrication as fab, kinematics, layout  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-infeed-fab.html"
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def n(v: float) -> str:
    if isinstance(v, float) and v != int(v):
        return f"{v:,.1f}"
    return f"{int(round(v)):,}"


# ── 부품도 (3면도) ──────────────────────────────────────────────────────
class View:
    """한 뷰 — mm 좌표를 px 로. 원점은 뷰 좌하단."""

    def __init__(self, ox: float, oy: float, scale: float):
        self.ox, self.oy, self.s = ox, oy, scale
        self.parts: list[str] = []

    def X(self, x: float) -> float:
        return round(self.ox + x * self.s, 1)

    def Y(self, y: float) -> float:
        return round(self.oy - y * self.s, 1)

    def rect(self, x: float, y: float, w: float, h: float, cls: str = "ol") -> None:
        self.parts.append(f'<rect class="{cls}" x="{self.X(x)}" y="{self.Y(y + h)}" width="{round(w * self.s, 1)}" height="{round(h * self.s, 1)}"/>')

    def circle(self, cx: float, cy: float, r: float, cls: str = "ol") -> None:
        self.parts.append(f'<circle class="{cls}" cx="{self.X(cx)}" cy="{self.Y(cy)}" r="{round(r * self.s, 1)}"/>')

    def line(self, x0: float, y0: float, x1: float, y1: float, cls: str = "ol") -> None:
        self.parts.append(f'<line class="{cls}" x1="{self.X(x0)}" y1="{self.Y(y0)}" x2="{self.X(x1)}" y2="{self.Y(y1)}"/>')

    def text(self, x: float, y: float, s: str, cls: str = "t", anchor: str = "middle", dx: float = 0, dy: float = 0, rot: float | None = None) -> None:
        px, py = self.X(x) + dx, self.Y(y) + dy
        tr = f' transform="rotate({rot} {px} {py})"' if rot is not None else ""
        self.parts.append(f'<text class="{cls}" x="{px}" y="{py}" text-anchor="{anchor}"{tr}>{esc(s)}</text>')

    def dim_h(self, x0: float, x1: float, y: float, label: str, off: float = 0) -> None:
        """수평 치수선 — y 는 mm 좌표, off 는 px 오프셋(아래 +)."""
        ya = self.Y(y) + off
        xa, xb = self.X(x0), self.X(x1)
        self.parts.append(f'<line class="dim" x1="{xa}" y1="{ya}" x2="{xb}" y2="{ya}"/>')
        for px in (xa, xb):
            self.parts.append(f'<line class="dim" x1="{px}" y1="{ya - 4}" x2="{px}" y2="{ya + 4}"/>')
            self.parts.append(f'<line class="ext" x1="{px}" y1="{ya}" x2="{px}" y2="{self.Y(y)}"/>')
        self.parts.append(f'<text class="dt" x="{round((xa + xb) / 2, 1)}" y="{ya - 3}" text-anchor="middle">{esc(label)}</text>')

    def dim_v(self, y0: float, y1: float, x: float, label: str, off: float = 0) -> None:
        xa = self.X(x) + off
        ya, yb = self.Y(y0), self.Y(y1)
        self.parts.append(f'<line class="dim" x1="{xa}" y1="{ya}" x2="{xa}" y2="{yb}"/>')
        for py in (ya, yb):
            self.parts.append(f'<line class="dim" x1="{xa - 4}" y1="{py}" x2="{xa + 4}" y2="{py}"/>')
            self.parts.append(f'<line class="ext" x1="{self.X(x)}" y1="{py}" x2="{xa}" y2="{py}"/>')
        self.parts.append(f'<text class="dt" x="{xa + 4}" y="{round((ya + yb) / 2, 1) + 3}" text-anchor="start">{esc(label)}</text>')


def _hole_positions(h: fab.Hole, L: float, W: float) -> list[tuple[float, float]]:
    """뷰 평면(가로 L, 세로 W) 위의 구멍 중심."""
    pts: list[tuple[float, float]] = []
    if h.pattern == "corners":
        e = h.edge
        pts = [(e, e), (L - e, e), (e, W - e), (L - e, W - e)][: h.n]
    elif h.pattern == "row":
        if h.along == "L":
            span = L
            if h.pitch > 0 and h.n > 1:
                xs = [h.edge + i * h.pitch for i in range(h.n)]
                if xs[-1] > L - h.edge:
                    xs = [L / 2 + (i - (h.n - 1) / 2) * h.pitch for i in range(h.n)]
            else:
                xs = [h.edge + i * (span - 2 * h.edge) / max(h.n - 1, 1) for i in range(h.n)] if h.n > 1 else [L / 2]
            pts = [(x, W / 2) for x in xs]
        else:
            ys = [h.edge + i * (W - 2 * h.edge) / max(h.n - 1, 1) for i in range(h.n)] if h.n > 1 else [W / 2]
            pts = [(L / 2, y) for y in ys]
    elif h.pattern == "grid":
        nx = max(2, h.n // 2)
        ny = max(1, h.n // nx)
        for j in range(ny):
            for i in range(nx):
                pts.append((h.edge + i * (L - 2 * h.edge) / (nx - 1), h.edge + j * (W - 2 * h.edge) / max(ny - 1, 1)))
    elif h.pattern == "pcd":
        r = h.pcd / 2
        for i in range(h.n):
            a = 2 * math.pi * i / h.n
            pts.append((L / 2 + r * math.cos(a), W / 2 + r * math.sin(a)))
    return pts


def part_sheet(p: fab.Part, sheet_no: str) -> str:
    """부품 하나의 3면도. 크기에 맞춰 축척을 잡는다."""
    L, W, H = p.L, p.W, p.H
    round_kind = p.kind in ("cyl", "disc", "tube", "ring")
    # 뷰 배치: 정면(L×H) 좌상, 평면(L×W) 좌하, 측면(W×H) 우상
    if p.kind == "ring":
        fw, fh, tw, th, sw, sh = L + W, L + W, L + W, W, W, L + W
    elif p.kind in ("cyl", "disc"):
        fw, fh, tw, th, sw, sh = L, H, L, L, L, H
    elif p.kind == "tube":
        fw, fh, tw, th, sw, sh = L, W, L, W, W, W
    else:
        fw, fh, tw, th, sw, sh = L, H, L, W, W, H
    width_px = 720
    gap = 70
    scale = min((width_px - 3 * gap - 20) / (fw + sw), (330 - 3 * gap) / (fh + th))
    scale = min(scale, 0.9)
    height_px = int((fh + th) * scale + 3 * gap + 40)
    v = View(gap, gap + fh * scale, scale)
    top = View(gap, gap + fh * scale + gap + th * scale, scale)
    side = View(gap + fw * scale + gap, gap + fh * scale, scale)
    parts = []
    t = p.t

    def holes_on(view: View, which: str, vw: float, vh: float) -> None:
        for h in p.holes:
            if h.view != which:
                continue
            for (x, y) in _hole_positions(h, vw, vh):
                view.circle(x, y, h.dia_mm / 2, "hole")
                if h.tapped:
                    view.circle(x, y, h.dia_mm / 2 * 1.15, "tap")
            if h.pattern != "pcd":
                pts = _hole_positions(h, vw, vh)
                if pts:
                    view.text(pts[0][0], pts[0][1], h.callout, "ht", "start", dx=h.dia_mm * scale / 2 + 4, dy=-4)
            else:
                view.text(vw / 2, vh / 2, f"{h.callout} PCD {n(h.pcd)}", "ht", "middle", dy=4)

    # 정면
    if p.kind == "ring":
        v.circle(fw / 2, fh / 2, (L + W) / 2, "ol"); v.circle(fw / 2, fh / 2, (L - W) / 2, "ol")
        v.circle(fw / 2, fh / 2, L / 2, "cl")
        v.text(fw / 2, -40, f"Ø{n(L + W)} 외경 · Ø{n(L - W)} 구멍 · 중심선 Ø{n(L)}", "t")
        # 단면 상세 (우측)
        side.circle(sw / 2, sh / 2, W / 2, "ol"); side.circle(sw / 2, sh / 2, W / 2 - t, "ol")
        side.text(sw / 2, -30, f"관 단면 Ø{n(W)} × t{n(t)}", "t")
        top.rect(0, 0, L + W, W); top.text(tw / 2, -30, f"평면 — 두께 {n(W)}", "t")
    elif p.kind in ("cyl", "disc"):
        v.rect(0, 0, L, H)
        if t > 0 and p.kind == "cyl":
            v.line(t, 0, t, H, "hid"); v.line(L - t, 0, L - t, H, "hid")
        v.dim_h(0, L, 0, f"Ø{n(L)}", 26); v.dim_v(0, H, L, f"{n(H)}", 26)
        top.circle(L / 2, L / 2, L / 2, "ol")
        if p.kind == "disc" and W > 0:
            top.circle(L / 2, L / 2, W / 2, "ol"); top.text(L / 2, L / 2, f"Ø{n(W)}", "ht", dy=-8)
        if t > 0 and p.kind == "cyl":
            top.circle(L / 2, L / 2, L / 2 - t, "ol")
            top.text(L / 2, L + 20, f"t = {n(t)}", "t")
        top.line(L / 2, -10, L / 2, L + 10, "cl"); top.line(-10, L / 2, L + 10, L / 2, "cl")
        holes_on(top, "top", L, L)
        side.rect(0, 0, L, H); side.text(sw / 2, -30, "측면", "t")
    elif p.kind == "tube":
        v.rect(0, 0, L, W); v.line(0, t, L, t, "hid"); v.line(0, W - t, L, W - t, "hid")
        v.dim_h(0, L, 0, f"{n(L)}", 26); v.dim_v(0, W, L, f"Ø{n(W)}", 26)
        side.circle(sw / 2, sh / 2, W / 2, "ol"); side.circle(sw / 2, sh / 2, W / 2 - t, "ol")
        side.text(sw / 2, -30, f"단면 Ø{n(W)} × t{n(t)}", "t")
        top.rect(0, 0, L, W); top.line(0, W / 2, L, W / 2, "cl")
        holes_on(top, "top", L, W)
    else:
        v.rect(0, 0, L, H)
        if p.kind in ("box", "shs") and t > 0:
            v.line(0, t, L, t, "hid"); v.line(0, H - t, L, H - t, "hid")
        v.dim_h(0, L, 0, f"{n(L)}", 26); v.dim_v(0, H, L, f"{n(H)}", 26)
        holes_on(v, "front", L, H)
        top.rect(0, 0, L, W)
        top.dim_v(0, W, L, f"{n(W)}", 26)
        holes_on(top, "top", L, W)
        # 측면 — 단면 형상
        if p.kind in ("box", "shs"):
            side.rect(0, 0, W, H); side.rect(t, t, W - 2 * t, H - 2 * t)
            side.text(sw / 2, -30, f"단면 {n(W)}×{n(H)} × t{n(t)}", "t")
        elif p.kind == "channel":
            side.rect(0, 0, t, H); side.rect(0, 0, W, t); side.rect(0, H - t, W, t)
            side.text(sw / 2, -30, f"ㄷ {n(H)}×{n(W)} × t{n(t)}", "t")
        elif p.kind == "angle":
            side.rect(0, 0, t, H); side.rect(0, 0, W, t)
            side.text(sw / 2, -30, f"ㄱ {n(W)}×{n(H)} × t{n(t)}", "t")
        elif p.kind == "hbeam":
            side.rect(0, 0, W, 1.4 * t); side.rect(0, H - 1.4 * t, W, 1.4 * t); side.rect(W / 2 - t / 2, 0, t, H)
            side.text(sw / 2, -30, f"H {n(H)}×{n(W)} · 웹 t{n(t)}", "t")
        else:
            side.rect(0, 0, W, H)
            side.text(sw / 2, -30, f"두께 {n(H)}" if p.kind == "plate" else f"{n(W)}×{n(H)}", "t")
        holes_on(side, "end", W, H)
        holes_on(side, "side", W, H)
    v.text(0, fh + 12, "정면도", "vl", "start")
    top.text(0, th + 12, "평면도", "vl", "start")
    side.text(0, sh + 12, "측면도 / 단면", "vl", "start", dy=-12)
    svg = (f'<svg class="pd" viewBox="0 0 {width_px} {height_px}" role="img" aria-label="{esc(p.tag)} 부품도">'
           + "".join(v.parts + top.parts + side.parts) + "</svg>")
    mat = fab.MATERIALS[p.material]
    holes_txt = "; ".join(f"{h.callout} — {h.note}" if h.note else h.callout for h in p.holes) or "—"
    block = (
        f'<table class="tb"><tbody>'
        f'<tr><th>도면번호</th><td class="mono">{esc(sheet_no)}</td><th>수량</th><td>{p.qty} / 조립체</td></tr>'
        f'<tr><th>부품번호</th><td class="mono">{esc(p.tag)}</td><th>중량</th><td>{n(p.weight_kg())} kg / 개</td></tr>'
        f'<tr><th>품명</th><td colspan="3">{esc(p.name)}</td></tr>'
        f'<tr><th>외형</th><td colspan="3">{esc(_size_text(p))}</td></tr>'
        f'<tr><th>재질</th><td colspan="3">{esc(p.material)} — {esc(mat[0])} · {esc(mat[1])} · 상당 {esc(mat[2])}</td></tr>'
        f'<tr><th>공정</th><td colspan="3">{esc(p.process)}</td></tr>'
        f'<tr><th>구멍</th><td colspan="3">{esc(holes_txt)}</td></tr>'
        f'<tr><th>표면</th><td colspan="3">{esc(p.finish)}</td></tr>'
        f'<tr><th>공차</th><td colspan="3">{esc(p.tolerance)}</td></tr>'
        + (f'<tr><th>비고</th><td colspan="3">{esc(p.note)}</td></tr>' if p.note else "")
        + "</tbody></table>"
    )
    return f'<article class="sheet" id="{esc(sheet_no)}"><h4><span class="mono">{esc(sheet_no)}</span> {esc(p.tag)} · {esc(p.name)}</h4><div class="pdrow">{svg}{block}</div></article>'


def _size_text(p: fab.Part) -> str:
    L, W, H = p.L, p.W, p.H
    if p.kind == "ring":
        return f"링 중심선 Ø{n(L)} · 관 Ø{n(W)} × t{n(p.t)} (외경 Ø{n(L + W)} · 구멍 Ø{n(L - W)})"
    if p.kind == "cyl":
        return f"Ø{n(L)} × {n(H)}" + (f" · t{n(p.t)}" if p.t else " (솔리드)")
    if p.kind == "disc":
        return f"Ø{n(L)} × t{n(H)}" + (f" · 중앙 Ø{n(W)}" if W else "")
    if p.kind == "tube":
        return f"Ø{n(W)} × t{n(p.t)} × L{n(L)}"
    if p.kind == "plate":
        return f"{n(L)} × {n(W)} × t{n(H)}"
    if p.kind in ("box", "shs", "channel", "angle", "hbeam"):
        return f"L{n(L)} · 단면 {n(W)}×{n(H)} × t{n(p.t)}"
    return f"{n(L)} × {n(W)} × {n(H)}" + (f" · t{n(p.t)}" if p.t else "")


# ── 등각 분해도 ─────────────────────────────────────────────────────────
C30, S30 = math.cos(math.radians(30)), math.sin(math.radians(30))


def iso(x: float, y: float, z: float) -> tuple[float, float]:
    """x 공정방향 · y 상하 · z 깊이 → 화면 (u, v)."""
    return (x - z) * C30, -y + (x + z) * S30


def iso_box(out: list[str], cx: float, cy: float, cz: float, sx: float, sy: float, sz: float, cls: str, label: str | None) -> tuple[float, float]:
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    top = [iso(x0, y1, z0), iso(x1, y1, z0), iso(x1, y1, z1), iso(x0, y1, z1)]
    front = [iso(x0, y0, z1), iso(x1, y0, z1), iso(x1, y1, z1), iso(x0, y1, z1)]
    right = [iso(x1, y0, z0), iso(x1, y0, z1), iso(x1, y1, z1), iso(x1, y1, z0)]
    for face, shade in ((top, "f1"), (front, "f2"), (right, "f3")):
        out.append(f'<polygon class="{cls} {shade}" points="{" ".join(f"{u:.1f},{v:.1f}" for u, v in face)}"/>')
    u, v = iso(x1, y1, z0)
    return u, v


def exploded_view(a: fab.Assembly) -> str:
    inst = a.explode or tuple(
        (p.tag, (p.L if p.kind not in ("cyl", "disc") else p.L, p.H if p.kind not in ("ring",) else p.L + p.W, p.W if p.kind not in ("cyl", "disc", "ring") else (p.L if p.kind != "ring" else p.W)),
         (i * 1.15 * (max(1.0, p.L) * 0.5 + 400), 0.0, 0.0), (0.0, 0.0, 0.0))
        for i, p in enumerate(a.parts[:14])
    )
    pieces = []
    for tag, size, at, ex in inst:
        cx, cy, cz = at[0] + ex[0], at[1] + ex[1], at[2] + ex[2]
        pieces.append((cx + cy + cz, tag, size, (cx, cy, cz)))
    pieces.sort(key=lambda r: r[0])
    out: list[str] = []
    labels: list[tuple[float, float, str]] = []
    us, vs = [], []
    kinds = {p.tag: p.kind for p in a.parts}
    for _, tag, size, (cx, cy, cz) in pieces:
        kind = kinds.get(tag, "box")
        cls = "ring" if kind == "ring" else ("cyl" if kind in ("cyl", "disc") else "box")
        u, v = iso_box(out, cx, cy, cz, size[0], size[1], size[2], cls, tag)
        if kind == "ring":
            uc, vc = iso(cx, cy, cz)
            r = size[1] / 2
            out.append(f'<ellipse class="ringline" cx="{uc:.1f}" cy="{vc:.1f}" rx="{r * C30:.1f}" ry="{r:.1f}" transform="rotate(30 {uc:.1f} {vc:.1f})"/>')
        labels.append((u, v, tag))
        for dx, dy, dz in ((-size[0] / 2, -size[1] / 2, -size[2] / 2), (size[0] / 2, size[1] / 2, size[2] / 2), (size[0] / 2, -size[1] / 2, -size[2] / 2), (-size[0] / 2, size[1] / 2, size[2] / 2)):
            uu, vv = iso(cx + dx, cy + dy, cz + dz)
            us.append(uu); vs.append(vv)
    for i, (u, v, tag) in enumerate(labels):
        out.append(f'<line class="lead" x1="{u:.1f}" y1="{v:.1f}" x2="{u + 60:.1f}" y2="{v - 40:.1f}"/>')
        out.append(f'<circle class="bal" cx="{u + 60:.1f}" cy="{v - 40:.1f}" r="13"/>')
        out.append(f'<text class="bt" x="{u + 60:.1f}" y="{v - 36:.1f}" text-anchor="middle">{i + 1}</text>')
    if not us:
        return ""
    minu, maxu, minv, maxv = min(us) - 90, max(us) + 90, min(vs) - 70, max(vs) + 40
    w, h = maxu - minu, maxv - minv
    legend = "".join(f'<li><b>{i + 1}</b> <span class="mono">{esc(tag)}</span> {esc(next((p.name for p in a.parts if p.tag == tag), ""))}</li>' for i, (_, _, tag) in enumerate(labels))
    return (f'<div class="explode"><svg viewBox="{minu:.0f} {minv:.0f} {w:.0f} {h:.0f}" role="img" aria-label="{esc(a.tag)} 분해도">'
            + "".join(out) + f'</svg><ol class="balloons">{legend}</ol></div>')


# ── 분해도 인스턴스 (자리는 통합 설계도의 부품 좌표) ───────────────────────
def explode_instances() -> dict[str, tuple]:
    k = kinematics
    pick = 0.0
    return {
        "AFU-BW-101": (
            ("BW-COL-01", (150, 4850, 150), (-1255, 2445, 0), (0, 0, -900)),
            ("BW-COL-01", (150, 4850, 150), (1255, 2445, 0), (0, 0, 900)),
            ("BW-BP-01", (300, 20, 300), (-1255, 10, 0), (0, -500, -900)),
            ("BW-BP-01", (300, 20, 300), (1255, 10, 0), (0, -500, 900)),
            ("BW-BM-01", (2360, 100, 150), (0, 4750, 0), (0, 600, 0)),
            ("BW-BM-02", (2360, 100, 150), (0, 3600, 0), (0, 300, 0)),
            ("BW-BM-02", (2360, 100, 150), (0, 2400, 0), (0, 0, 0)),
            ("BW-BM-02", (2360, 100, 150), (0, 1200, 0), (0, -300, 0)),
            ("BW-PNL-01", (2360, 1200, 3.2), (0, 600, 90), (0, 0, 1400)),
            ("BW-PNL-01", (2360, 1200, 3.2), (0, 1800, 90), (0, 0, 1700)),
            ("BW-CAP-01", (2660, 6, 150), (0, 4903, 0), (0, 1100, 0)),
        ),
        "AFU-VG-101": (
            ("VG-COL-01", (150, 4900, 150), (0, 2450, -3210), (0, 0, -900)),
            ("VG-COL-01", (150, 4900, 150), (0, 2450, 3210), (0, 0, 900)),
            ("VG-BP-01", (300, 20, 300), (0, 10, -3210), (0, -500, -900)),
            ("VG-AVM-01", (340, 30, 340), (0, -15, -3210), (0, -800, -900)),
            ("VG-HB-01", (2480, 100, 200), (0, 5000, -3210), (0, 700, -900)),
            ("VG-HB-01", (2480, 100, 200), (0, 5000, 3210), (0, 700, 900)),
            ("VG-MB-01", (100, 200, 6700), (-1140, 5050, 0), (-900, 1200, 0)),
            ("VG-MB-01", (100, 200, 6700), (1140, 5050, 0), (900, 1200, 0)),
            ("VG-CB-01", (2280, 100, 150), (0, 5050, -1600), (0, 1800, 0)),
            ("VG-CB-01", (2280, 100, 150), (0, 5050, 1600), (0, 1800, 0)),
            ("VG-CM-01", (380, 10, 260), (0, 4945, -1600), (0, -700, 0)),
            ("VG-CM-01", (380, 10, 260), (0, 4945, 1600), (0, -700, 0)),
        ),
        "AFU-BFC-101": (
            ("BFC-COL-01", (180, 3350, 240), (-1600, 1675, -1290), (-820, -180, -350)),
            ("BFC-COL-01", (180, 3350, 240), (-1600, 1675, 950), (-820, -180, 350)),
            ("BFC-COL-01", (180, 3350, 240), (1600, 1675, -1290), (820, -180, -350)),
            ("BFC-COL-01", (180, 3350, 240), (1600, 1675, 950), (820, -180, 350)),
            ("BFC-BP-01", (500, 25, 400), (-1600, 12, -1290), (-820, -760, -350)),
            ("BFC-BP-01", (500, 25, 400), (1600, 12, 950), (820, -760, 350)),
            ("BFC-CB-01", (180, 260, 2660), (-1600, 3320, -170), (-820, 1180, 0)),
            ("BFC-CB-01", (180, 260, 2660), (1600, 3320, -170), (820, 1180, 0)),
            ("BFC-BB-01", (220, 300, 260), (-1600, 2900, -520), (-1050, 700, -300)),
            ("BFC-BB-01", (220, 300, 260), (-1600, 2900, 520), (-1050, 700, 300)),
            ("BFC-RNG-01", (180, 1980, 1980), (-1380, k.FLIP_AXIS_MM, 0), (-1080, 700, 0)),
            ("BFC-RNG-01", (180, 1980, 1980), (1380, k.FLIP_AXIS_MM, 0), (1080, 700, 0)),
            ("BFC-DRB-01", (400, 20, 300), (-1380, 2560, 0), (-1080, -400, 0)),
            ("BFC-CAR-01", (2720, 140, 100), (0, 1760, -672), (-1500, -320, -300)),
            ("BFC-CAR-01", (2720, 140, 100), (0, 1760, 672), (-1500, -320, 300)),
            ("BFC-CAR-03", (100, 100, 1445), (-1310, 1760, 0), (-1500, -320, 0)),
            ("BFC-CAR-03", (100, 100, 1445), (1310, 1760, 0), (-1500, -320, 0)),
            ("BFC-SEP-01", (2180, 120, 80), (0, 2060, 0), (-1500, 1160, 0)),
            ("BFC-CLP-01", (2540, 90, 90), (0, 3513, -673), (0, 1160, -900)),
            ("BFC-CLP-01", (2540, 90, 90), (0, 3348, 673), (0, -320, 900)),
            ("BFC-PAD-01", (180, 50, 180), (-1050, 3493, -673), (-1050, 1080, -820)),
            ("BFC-PAD-01", (180, 50, 180), (1050, 3493, -673), (1050, 1080, -820)),
            ("BFC-JGP-01", (40, 400, 40), (-1280, 3640, -860), (-1280, 900, -1000)),
            ("BFC-JGP-01", (40, 400, 40), (1280, 3220, 860), (1280, 900, 1000)),
        ),
        "AFU-CD-101": (
            ("CD-CAS-01", (2900, 60, 60), (0, 1740, 1055), (0, -400, 900)),
            ("CD-CAS-01", (2900, 60, 60), (0, 2300, 1055), (0, 400, 900)),
            ("CD-RL-01", (100, 100, 1600), (-1200, 2020, 300), (-600, 0, 0)),
            ("CD-RL-01", (100, 100, 1600), (1200, 2020, 300), (600, 0, 0)),
            ("CD-BM-01", (2900, 100, 60), (0, 2020, -720), (0, 0, -900)),
            ("CD-BM-01", (2900, 100, 60), (0, 2020, -580), (0, 0, -560)),
            ("CD-BM-01", (2900, 100, 60), (0, 2020, 580), (0, 0, 560)),
            ("CD-BM-01", (2900, 100, 60), (0, 2020, 720), (0, 0, 900)),
        ),
        "AFU-RB-101 · EOAT-101": (
            ("PED-04", (400, 25, 400), (-450, 12, -450), (-500, -400, -500)),
            ("PED-04", (400, 25, 400), (450, 12, 450), (500, -400, 500)),
            ("PED-03", (1100, 30, 1100), (0, 40, 0), (0, -250, 0)),
            ("PED-01", (1100, 560, 1100), (0, 335, 0), (0, 0, 0)),
            ("PED-05", (500, 120, 12), (0, 400, -530), (0, 0, -600)),
            ("PED-02", (1100, 30, 1100), (0, 630, 0), (0, 400, 0)),
            ("EOAT-02", (200, 20, 200), (0, 3300, 0), (0, 1800, 0)),
            ("EOAT-01", (2180, 80, 80), (0, 3150, -380), (0, 1400, -400)),
            ("EOAT-01", (2180, 80, 80), (0, 3150, 380), (0, 1400, 400)),
            ("EOAT-05", (400, 40, 40), (-800, 3100, 0), (-600, 1100, 0)),
            ("EOAT-04", (60, 180, 6), (-1050, 3050, -450), (-1400, 900, -700)),
            ("EOAT-04", (60, 180, 6), (1050, 3050, 450), (1400, 900, 700)),
        ),
        "AFU-PT-101 · AL-101": (
            ("PT-LEG-01", (100, 860, 100), (-1325, 430, -675), (-500, -400, -500)),
            ("PT-LEG-01", (100, 860, 100), (1325, 430, -675), (500, -400, -500)),
            ("PT-LEG-01", (100, 860, 100), (-1325, 430, 675), (-500, -400, 500)),
            ("PT-LEG-01", (100, 860, 100), (1325, 430, 675), (500, -400, 500)),
            ("PT-BP-01", (250, 16, 250), (-1325, 8, -675), (-500, -800, -500)),
            ("PT-FR-01", (2850, 100, 150), (0, 880, -675), (0, 0, -500)),
            ("PT-FR-01", (2850, 100, 150), (0, 880, 675), (0, 0, 500)),
            ("PT-FR-02", (150, 100, 1450), (-1350, 880, 0), (-500, 0, 0)),
            ("PT-FR-02", (150, 100, 1450), (1350, 880, 0), (500, 0, 0)),
            ("PT-TOP-01", (2620, 12, 1520), (0, 939, 0), (0, 500, 0)),
            ("PT-STP-01", (150, 60, 60), (-900, 990, -730), (-300, 900, -600)),
            ("PT-STP-01", (150, 60, 60), (900, 990, -730), (300, 900, -600)),
            ("PT-STP-02", (60, 60, 150), (1330, 990, 0), (700, 900, 0)),
            ("PT-PSH-01", (2720, 40, 60), (0, 980, -820), (0, 800, -900)),
            ("PT-PSH-01", (2720, 40, 60), (0, 980, 820), (0, 800, 900)),
        ),
        "AFU-RJ-101": (
            ("RJ-FR-02", (50, 1200, 50), (-775, 600, -325), (-300, 0, -300)),
            ("RJ-FR-02", (50, 1200, 50), (775, 600, -325), (300, 0, -300)),
            ("RJ-FR-02", (50, 1200, 50), (-775, 600, 325), (-300, 0, 300)),
            ("RJ-FR-02", (50, 1200, 50), (775, 600, 325), (300, 0, 300)),
            ("RJ-FR-01", (1600, 50, 50), (0, 1175, -325), (0, 400, -300)),
            ("RJ-FR-01", (1600, 50, 50), (0, 1175, 325), (0, 400, 300)),
            ("RJ-FR-03", (50, 50, 700), (-775, 1175, 0), (-300, 400, 0)),
            ("RJ-DIV-01", (1550, 1150, 4.5), (0, 600, -285), (0, 0, -100)),
            ("RJ-DIV-01", (1550, 1150, 4.5), (0, 600, 0), (0, 0, 0)),
            ("RJ-DIV-01", (1550, 1150, 4.5), (0, 600, 285), (0, 0, 100)),
            ("RJ-BP-01", (120, 10, 120), (-775, 5, -325), (-300, -400, -300)),
        ),
        "JB-201": (
            ("JB-LEG-01", (80, 830, 80), (-1200, 415, -740), (-300, -300, -400)),
            ("JB-LEG-01", (80, 830, 80), (1200, 415, -740), (300, -300, -400)),
            ("JB-LEG-01", (80, 830, 80), (-1200, 415, 740), (-300, -300, 400)),
            ("JB-LEG-01", (80, 830, 80), (1200, 415, 740), (300, -300, 400)),
            ("JB-BP-01", (150, 12, 150), (-1200, 6, -740), (-300, -700, -400)),
            ("JB-SF-01", (2750, 150, 75), (0, 905, -777), (0, 0, -600)),
            ("JB-SF-01", (2750, 150, 75), (0, 905, 777), (0, 0, 600)),
            ("JB-CRS-01", (40, 80, 1480), (-1000, 800, 0), (0, -300, 0)),
            ("JB-CRS-01", (40, 80, 1480), (1000, 800, 0), (0, -300, 0)),
            ("JB-RL-01", (90, 90, 1480), (-1200, 905, 0), (0, 500, 0)),
            ("JB-RL-01", (90, 90, 1480), (-400, 905, 0), (0, 500, 0)),
            ("JB-RL-01", (90, 90, 1480), (400, 905, 0), (0, 500, 0)),
            ("JB-RL-01", (90, 90, 1480), (1200, 905, 0), (0, 500, 0)),
            ("JB-GRD-01", (2750, 40, 40), (0, 1475, -1040), (0, 300, -900)),
            ("JB-GRD-01", (2750, 40, 40), (0, 1475, 1040), (0, 300, 900)),
        ),
        "AFU-SF-101": (
            ("SF-PST-01", (60, 2300, 60), (-1700, 1150, -1150), (-300, 0, -300)),
            ("SF-PST-01", (60, 2300, 60), (0, 1150, -1150), (0, 0, -300)),
            ("SF-PST-01", (60, 2300, 60), (1700, 1150, -1150), (300, 0, -300)),
            ("SF-PST-01", (60, 2300, 60), (-1700, 1150, 1150), (-300, 0, 300)),
            ("SF-PST-01", (60, 2300, 60), (1700, 1150, 1150), (300, 0, 300)),
            ("SF-PNL-01", (1000, 2000, 40), (-850, 1050, -1150), (0, 0, -900)),
            ("SF-PNL-01", (1000, 2000, 40), (850, 1050, -1150), (0, 0, -900)),
            ("SF-PNL-01", (40, 2000, 1000), (-1700, 1050, -575), (-900, 0, 0)),
            ("SF-BP-01", (120, 8, 120), (-1700, 4, -1150), (-300, -500, -300)),
        ),
    }


# ── 표 ──────────────────────────────────────────────────────────────────
def table(head: list[str], rows: list[list[str]], cls: str = "tb") -> str:
    out = [f'<div class="scroll"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"]
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def bom_table(a: fab.Assembly, sheet_of: dict[str, str]) -> str:
    rows = [[f'<a class="mono" href="#{esc(sheet_of[p.tag])}">{esc(sheet_of[p.tag])}</a>', f'<span class="mono">{esc(p.tag)}</span>', esc(p.name),
             esc(_size_text(p)), esc(p.material), str(p.qty), n(p.weight_kg()), n(p.weight_kg() * p.qty)] for p in a.parts]
    rows.append(["", "", "<b>제작품 합계 (조립체 1벌)</b>", "", "", str(sum(p.qty for p in a.parts)), "", f"<b>{n(a.fabricated_weight_kg())}</b>"])
    return table(["도면", "부품번호", "품명", "외형", "재질", "수량", "단중 kg", "합 kg"], rows)


def commercial_table(a: fab.Assembly) -> str:
    if not a.commercial:
        return "<p class='note'>상용품 없음.</p>"
    return table(["품번", "품명", "규격", "수량", "비고"], [[f'<span class="mono">{esc(c.tag)}</span>', esc(c.name), esc(c.spec), str(c.qty), esc(c.note)] for c in a.commercial])


def joints_table(a: fab.Assembly) -> str:
    rows = []
    for j in a.joints:
        if j.kind == "용접":
            rows.append([esc(j.name), esc(j.parts), "용접", "—", "—", "—", esc(j.note)])
            continue
        rows.append([esc(j.name), esc(j.parts), esc(j.bolt) + (" 케미컬 앵커" if j.kind == "앵커" else f" {j.cls}"), str(j.qty),
                     f"Ø{fab.HOLE_MM[j.size]:g}" if j.kind == "관통" else ("탭" if j.kind == "탭" else f"Ø{fab.HOLE_MM[j.size]:g} · 매입 {fab.ANCHOR_EMBED_MM[j.size]}"),
                     f"{j.torque_nm:g}", esc(j.hardware + (" — " + j.note if j.note else ""))])
    return table(["체결부", "부품", "볼트", "수량", "구멍", "토크 N·m", "하드웨어 · 비고"], rows)


def steps_list(a: fab.Assembly) -> str:
    out = ['<ol class="steps">']
    for s in a.steps:
        out.append(f"<li><b>{esc(s.title)}</b><p>{esc(s.text)}</p>"
                   + (f'<p class="tools">공구 · {esc(s.tools)}</p>' if s.tools else "")
                   + (f'<p class="check">확인 · {esc(s.check)}</p>' if s.check else "") + "</li>")
    out.append("</ol>")
    return "".join(out)


# ── 문서 ────────────────────────────────────────────────────────────────
CSS = """
:root { --ground:#EEF1F3; --sheet:#FFFFFF; --ink:#16202A; --muted:#5B6874; --rule:#C8D0D7; --tint:#E4EAEF; --red:#B5321F; --blue:#2A6CB0; --amber:#C8850A; --green:#2F7D4F; --code:#EDF1F4; --f1:#F3F5F7; --f2:#D9DFE5; --f3:#BFC8D1; color-scheme: light; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --ground:#12181E; --sheet:#1A222A; --ink:#E4E9ED; --muted:#98A5B1; --rule:#34414D; --tint:#232D37; --red:#E0604A; --blue:#6FA8E6; --amber:#E6B04C; --green:#6CBF8A; --code:#232D37; --f1:#3A4652; --f2:#2B3540; --f3:#202830; color-scheme: dark; } }
:root[data-theme="dark"] { --ground:#12181E; --sheet:#1A222A; --ink:#E4E9ED; --muted:#98A5B1; --rule:#34414D; --tint:#232D37; --red:#E0604A; --blue:#6FA8E6; --amber:#E6B04C; --green:#6CBF8A; --code:#232D37; --f1:#3A4652; --f2:#2B3540; --f3:#202830; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink); font: 13.5px/1.55 "Pretendard", -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif; font-variant-numeric: tabular-nums; }
.mono, code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
code { background: var(--code); padding: 0 4px; border-radius: 3px; font-size: .92em; }
a { color: var(--blue); text-decoration: none; } a:hover { text-decoration: underline; }
.page { max-width: 1180px; margin: 0 auto; padding: 24px 20px 64px; display: grid; gap: 26px; }
.title { background: var(--sheet); border: 1px solid var(--rule); display: grid; grid-template-columns: 1fr auto; }
.title > div { padding: 18px 22px; }
.title h1 { margin: 6px 0 4px; font-size: 25px; font-weight: 600; line-height: 1.2; text-wrap: balance; }
.title p { margin: 0; color: var(--muted); max-width: 78ch; }
.eyebrow { font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.block { border-left: 1px solid var(--rule); display: grid; grid-template-columns: auto auto; gap: 0 18px; padding: 14px 22px; font-size: 12.5px; align-content: start; }
.block dt { color: var(--muted); } .block dd { margin: 0; }
section { background: var(--sheet); border: 1px solid var(--rule); padding: 20px 22px 22px; display: grid; gap: 14px; }
section h2 { margin: 0; font-size: 18px; font-weight: 600; }
section h3 { margin: 8px 0 0; font-size: 14.5px; font-weight: 600; }
section h4 { margin: 0; font-size: 13px; font-weight: 600; }
.note { color: var(--muted); font-size: 12.5px; max-width: 100ch; margin: 0; }
.warn { border-left: 3px solid var(--amber); padding: 8px 12px; background: var(--tint); font-size: 12.5px; max-width: 100ch; }
.scroll { overflow-x: auto; }
table.tb { border-collapse: collapse; width: 100%; font-size: 12.3px; }
table.tb th, table.tb td { text-align: left; vertical-align: top; padding: 5px 10px 5px 0; border-bottom: 1px solid var(--rule); }
table.tb thead th { color: var(--muted); font-weight: 600; font-size: 11.5px; letter-spacing: .04em; border-bottom-color: var(--ink); }
table.tb tbody th { color: var(--muted); font-weight: 500; white-space: nowrap; width: 1%; padding-right: 14px; }
.register td:first-child { white-space: nowrap; }
.sheet { border-top: 1px solid var(--rule); padding-top: 12px; display: grid; gap: 8px; }
.pdrow { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, 1fr); gap: 14px; align-items: start; }
svg.pd { width: 100%; height: auto; display: block; background: var(--sheet); border: 1px solid var(--rule); }
svg .ol { fill: none; stroke: var(--ink); stroke-width: 1.1; }
svg .hid { fill: none; stroke: var(--muted); stroke-width: .8; stroke-dasharray: 5 3; }
svg .cl { fill: none; stroke: var(--muted); stroke-width: .6; stroke-dasharray: 12 3 3 3; }
svg .hole { fill: none; stroke: var(--ink); stroke-width: .9; }
svg .tap { fill: none; stroke: var(--ink); stroke-width: .6; stroke-dasharray: 2 2; }
svg .dim { fill: none; stroke: var(--muted); stroke-width: .8; } svg .ext { fill: none; stroke: var(--muted); stroke-width: .5; }
svg text { fill: var(--ink); font-family: inherit; font-size: 10.5px; }
svg .dt, svg .ht { font-family: ui-monospace, Menlo, monospace; font-size: 10px; fill: var(--ink); }
svg .t { font-size: 10.5px; fill: var(--muted); } svg .vl { font-size: 10px; fill: var(--muted); letter-spacing: .04em; }
.explode { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(220px, 1fr); gap: 14px; align-items: start; }
.explode svg { width: 100%; height: auto; display: block; background: var(--sheet); border: 1px solid var(--rule); }
.explode polygon { stroke: var(--ink); stroke-width: .7; stroke-linejoin: round; }
.explode .f1 { fill: var(--f1); } .explode .f2 { fill: var(--f2); } .explode .f3 { fill: var(--f3); }
.explode .ring.f1, .explode .ring.f2, .explode .ring.f3 { fill: none; stroke: var(--muted); stroke-dasharray: 3 2; }
.explode .ringline { fill: none; stroke: var(--ink); stroke-width: 1.6; }
.explode .lead { stroke: var(--red); stroke-width: .8; } .explode .bal { fill: var(--sheet); stroke: var(--red); stroke-width: 1; }
.explode .bt { font-size: 11px; fill: var(--red); font-weight: 600; }
.balloons { margin: 0; padding: 0; list-style: none; font-size: 12px; display: grid; gap: 3px; }
.balloons b { display: inline-block; width: 22px; height: 22px; border-radius: 50%; border: 1px solid var(--red); color: var(--red); text-align: center; line-height: 20px; margin-right: 6px; font-size: 11px; }
ol.steps { margin: 0; padding-left: 22px; display: grid; gap: 8px; max-width: 100ch; }
ol.steps p { margin: 2px 0 0; } ol.steps .tools, ol.steps .check { color: var(--muted); font-size: 12px; }
ol.steps .check { color: var(--green); }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; font-size: 12.5px; margin: 0; }
.kv dt { color: var(--muted); } .kv dd { margin: 0; }
.toc { columns: 3; column-gap: 24px; font-size: 12.5px; margin: 0; padding-left: 18px; }
.ok { color: var(--green); font-weight: 600; } .bad { color: var(--red); font-weight: 600; }
@media (max-width: 800px) { .title { grid-template-columns: 1fr; } .pdrow, .explode { grid-template-columns: 1fr; } .toc { columns: 1; } }
"""


def build() -> str:
    S = fab.summary()
    inst = explode_instances()
    assemblies = [a if a.tag not in inst else fab.Assembly(a.sheet, a.tag, a.name, a.qty, a.scope, a.parts, a.commercial, a.joints, a.steps, a.inspection, inst[a.tag]) for a in fab.ASSEMBLIES]
    sheet_of: dict[str, str] = {}
    for a in assemblies:
        for i, p in enumerate(a.parts, start=1):
            sheet_of[p.tag] = f"{a.sheet}-P{i:02d}"
    Z = {z.key: z for z in layout.build_zones()}
    parts: list[str] = []
    parts.append(f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DG 투입부 제작 도면집</title>
<style>{CSS}</style>
</head>
<body>
<main class="page">
<header class="title">
<div>
<div class="eyebrow">DYNAMIC INDUSTRY · 태양광 패널 전처리 플랜트 · 투입 구간 제작 패키지 · REV.A</div>
<h1>투입 구간 제작 도면집 — 부품도 · 조립도 · 분해도 · 체결 · 조립 순서</h1>
<p>FL-101 반입에서 RB-101 이 손을 떼는 JB-201 인계까지(afu·robot 존, 플랜트 X 0…{n(Z['robot'].x1_mm)})를 실제로 만들기 위한 문서다. 제작품 {S['fabricated_kinds']}종 {S['fabricated_pieces']}개의 치수·두께·재질·구멍, 상용품 {S['commercial_kinds']}종의 규격, 볼트 {n(S['bolts'])}개·앵커 {S['anchors']}개의 호칭·등급·토크, 조립체 {S['assemblies']}벌의 조립 순서와 검사 항목을 담는다. 자리와 높이는 설계 모델(layout·kinematics)과 통합 설계도의 부품 좌표에서 그대로 왔다.</p>
</div>
<dl class="block">
<dt>문서</dt><dd class="mono">PV-FAB-000 · REV.A</dd>
<dt>기준</dt><dd>PV-INFEED-101-DET-2001 · 통합 설계도 REV.53</dd>
<dt>제작품 중량</dt><dd>{n(S['weight_kg'])} kg</dd>
<dt>단위</dt><dd>mm · kg · N·m</dd>
<dt>생성</dt><dd class="mono">tools/build_infeed_fab.py</dd>
</dl>
</header>""")

    # 0. 지위
    parts.append("""<section id="status">
<h2>이 도면집의 지위 — 읽기 전에</h2>
<div class="warn">이 문서는 <b>설계실 출도본(REV.A)</b>이다. 단면·판두께·볼트는 기계 프레임 관례와 하중(반전 카세트 2,500 kg 이상, 패널 45 kg)에서 고른 설계 계획값이고, 자리와 높이는 검증된 설계 모델에서 왔다. 실제 제작 착수 전에 다음이 닫혀야 한다.
<ol>
<li><b>구조 검증</b> — 포탈 기둥·크로스빔·엔드링 지지롤러·페데스털의 응력·처짐 계산 또는 FEA, 앵커 인발 계산 (기술사 검토).</li>
<li><b>OEM 자료</b> — 로봇 베이스 볼트 패턴·TCP·하중도, 시저 리프트 GA·베이스 구멍, 서보·감속기 플랜지, LM·볼스크루 규격 확정.</li>
<li><b>미결 3건</b> — 적층→픽업 4,400 → 3,750 축소 결정(FL-101 제원), LFT 인덱스 50/45 mm 통일, RBPT 2D 시트의 PT 위치 310 mm 정정.</li>
<li><b>설계 미결</b> — 아래 <a href="#open">미결 항목</a> 절. 발주처·벤더 자료나 실물 시험이 있어야 정해지는 것들이고, 도면에 임의값을 넣지 않았다.</li>
</ol>
값을 고칠 때는 <code>src/pv_preprocess/fabrication.py</code> 를 고치고 이 문서를 다시 찍는다 — 손으로 고친 도면은 다음 회차에 갈라진다.</div>
</section>""")

    # 1. 도면 목록
    reg_rows = []
    for a in assemblies:
        reg_rows.append([f'<a href="#{esc(a.sheet)}">{esc(a.sheet)}</a>', esc(a.tag), esc(a.name), f"조립도 · 분해도 · 부품표 · 체결표 · 조립 순서", str(a.qty), str(len(a.parts))])
        for p in a.parts:
            reg_rows.append([f'<a href="#{esc(sheet_of[p.tag])}">{esc(sheet_of[p.tag])}</a>', esc(p.tag), esc(p.name), "부품도 3면 · 구멍 · 재질", f"{p.qty} × {a.qty}", ""])
    parts.append('<section id="register"><h2>도면 목록</h2>' + table(["도면번호", "부품·조립체", "명칭", "내용", "수량", "부품 종수"], reg_rows, "tb register") + "</section>")

    # 2. 총괄 사양
    mat_rows = [[f'<span class="mono">{esc(k)}</span>', esc(v[0]), esc(v[1]), esc(v[2]), f"{v[3] * 1e6:.2f}", esc(v[4])] for k, v in fab.MATERIALS.items()]
    torque_rows = [[esc(k), f"{v[0]:g}", f"{v[1]:g}", f"Ø{fab.HOLE_MM[k]:g}", str(fab.ANCHOR_EMBED_MM.get(k, "—"))] for k, v in fab.TORQUE_NM.items()]
    parts.append('<section id="spec"><h2>총괄 사양 — 재질 · 체결 · 용접 · 도장 · 공차</h2>'
                 '<h3>재질</h3>' + table(["코드", "명칭", "KS", "상당 규격", "밀도 g/cm³", "쓰임"], mat_rows)
                 + '<h3>체결 표준</h3>' + table(["항목", "규정"], [[esc(k), esc(v)] for k, v in fab.FASTENER_STANDARDS])
                 + '<h3>볼트 호칭별 토크 · 관통 구멍 · 앵커 매입</h3>' + table(["호칭", "8.8 토크 N·m", "10.9 토크 N·m", "관통 구멍 (중급)", "케미컬 앵커 매입 mm"], torque_rows)
                 + '<h3>용접</h3><p class="note">기호 KS B 0052 · 용접사 KS B 0885 · 필릿 크기 0.7 t (최소 5) · 기둥-베이스플레이트, 페데스털 동체, 엔드링 맞대기는 완전용입 · 기계가공 정반·상판은 용접 뒤 응력제거 · 외관 VT 전수, 완전용입부 UT 20 %.</p>'
                 '<h3>도장 · 표면</h3><p class="note">구조물 — 블라스트 Sa2.5 · 에폭시 프라이머 60 µm + 우레탄 상도 60 µm, 본체 RAL 7035 · 안전 부위(포획빔·가드·체인 커버) RAL 1023. 기계가공면 방청유. 알루미늄 알로딘 또는 백색 아노다이징 10 µm. 스테인리스 무도장.</p>'
                 '<h3>공차</h3><p class="note">일반 KS B ISO 2768-mK · 프레임 ±2 mm/m · 기계가공 기준면 ±0.1 · 정반 평면도 1.0/2,850 · LM 레일 면 직진도 0.05/1,000 · 엔드링 런아웃 0.25 · 설치 레벨 0.5 mm/m · 수직도 2 mm/기둥.</p>'
                 '<h3>기초</h3><p class="note">콘크리트 C24 이상 · 두께 ≥ 250 · 앵커는 케미컬 주입식, 매입 깊이 위 표 · 그라우트 무수축 (벽체·포탈 30 · 페데스털 40) · 로봇 페데스털과 PT-101 은 <b>기초를 나눈다</b> — 로봇 반력이 정반에 넘어가면 좌표시드가 흔들린다.</p>'
                 '</section>')

    # 3. 플랜트 설치 순서
    order = [
        ("기초 마킹", "존 원점(afu 존 상류면 · 라인 중심)에서 모든 조립체의 중심선을 먹줄로 놓는다. 적층 중심 x 4,400 · 페데스털 6,550 · PT-101 8,840 · 축적런 7,830…10,580 · 벽체 z 0/±3,150 · 리프트 z ±1,600."),
        ("A01 벽체 → A11 안전 가드 포스트", "벽체 3 과 가드 포스트를 먼저 세운다 — 나머지가 그 사이에 들어온다."),
        ("A09 리프트 · A10 유틸리티", "시저 리프트 2 와 진공·유압 스키드. 픽업면 1,880 원점."),
        ("A03 반전 카세트 (Bay A → Bay B)", "포탈 → 크로스빔 → 그라우트 → 롤러·엔드링 → 구동·락핀 → LM·볼스크루 → 캐리지·분리헤드 → 조·패드."),
        ("A04 포획빔", "중앙벽 포켓에 카세트 · 슬라이드 · 승강."),
        ("A02 비전보", "기둥 2 → 헤드빔 → 주보 → 카메라 플레이트 (렌즈 4,820)."),
        ("A05 페데스털 · 로봇 · EOAT", "독립 기초 · OEM 탑재 · EOAT 누설 시험 · 티칭."),
        ("A06 정반 · A08 JB-201 · A07 리젝트 랙", "정반 슬롯과 롤러를 같이 맞춘다 (상면 945 / 950). 랙은 티칭점과 일치."),
        ("A12 지지 브래킷 · 배선 · 배관", "하중 경로 검사 접지 성분 1 · 전기 F1/F2 · 공압·진공·유압."),
        ("시운전", "수동 저속 → 단일 사이클 → 60장 캠페인. 간섭 스윕 실측, 안전기능 SF-01/05/11 검증, 좌표시드 반복도, 이중 브레이크 보유 시험."),
    ]
    parts.append('<section id="order"><h2>플랜트 설치 순서</h2><p class="note">하류(GRM)부터 세워 상류로 온다는 전체 규칙 안에서, 투입 구간은 이 순서다. 크레인은 설치된 설비 위를 넘지 않는다.</p>'
                 '<ol class="steps">' + "".join(f"<li><b>{esc(t)}</b><p>{esc(x)}</p></li>" for t, x in order) + "</ol></section>")

    # 4. 조립체별
    for a in assemblies:
        parts.append(f'<section id="{esc(a.sheet)}"><h2><span class="mono">{esc(a.sheet)}</span> {esc(a.tag)} — {esc(a.name)}</h2>'
                     f'<p class="note">{esc(a.scope)} · 플랜트 {a.qty}벌 · 제작품 {len(a.parts)}종 {n(a.fabricated_weight_kg())} kg/벌 · 체결 {a.bolt_count()}개/벌</p>'
                     '<h3>분해도 (등각 · 자리는 통합 설계도 좌표)</h3>' + exploded_view(a)
                     + '<h3>부품표 (제작품)</h3>' + bom_table(a, sheet_of)
                     + '<h3>상용품</h3>' + commercial_table(a)
                     + '<h3>체결표</h3>' + joints_table(a)
                     + '<h3>조립 순서</h3>' + steps_list(a)
                     + '<h3>검사 항목</h3><ul class="note">' + "".join(f"<li>{esc(i)}</li>" for i in a.inspection) + "</ul>"
                     + '<h3>부품도</h3>' + "".join(part_sheet(p, sheet_of[p.tag]) for p in a.parts)
                     + "</section>")

    # 5. 집계
    fs = fab.fastener_summary()
    fs_rows = [[esc(k), " · ".join(f"{c} {q}개" for c, q in v.items()), str(sum(v.values()))] for k, v in sorted(fs.items())]
    am = fab.anchors_match_mounting()
    checks = fab.geometry_checks()
    sv = fab.servo_axes_covered()
    parts.append('<section id="totals"><h2>집계 · 모델 대조</h2>'
                 '<h3>볼트 · 앵커 (조립체 수량 반영, 예비 10 % 별도)</h3>' + table(["호칭", "등급별", "합계"], fs_rows)
                 + '<h3>앵커 — mounting 모델과 대조</h3>' + table(["셀 · 호칭", "모델", "패키지", "판정"], [[esc(k), str(v[0]), str(v[1]), '<span class="ok">일치</span>' if v[0] == v[1] else '<span class="bad">불일치</span>'] for k, v in am.items()])
                 + '<h3>기구학 치수 대조</h3>' + table(["항목", "판정"], [[esc(k), '<span class="ok">일치</span>' if v else '<span class="bad">불일치</span>'] for k, v in checks.items()])
                 + '<h3>서보 축 — 상용품 반영</h3>' + table(["축", "판정"], [[esc(k), '<span class="ok">반영</span>' if v else '<span class="bad">누락</span>'] for k, v in sv.items()])
                 + f'<p class="note">제작품 총중량 {n(S["weight_kg"])} kg (조립체 수량 반영) · 방출 주기 {campaign.release_takt_s():g} s 기준 투입부 점유 {campaign.INFEED_S:g} s.</p>'
                 "</section>")
    # 6. 미결 항목
    oi_rows = [[f'<span class="mono">{esc(o.tag)}</span>', esc(o.title), esc(o.why_open),
                esc(o.closes_with), esc(o.blocks), esc(o.question or "—")]
               for o in fab.OPEN_ITEMS]
    parts.append('<section id="open"><h2>미결 항목 — 도면으로 못 닫는 것</h2>'
                 '<p class="note">설계 검토에서 나온 지적 중 <b>계산으로 닫을 수 있는 것은 이미 닫혀 모델 안에 있다</b> '
                 '(구동계 검산 <code>drives.py</code>, 볼트·앵커 길이 <code>fasteners.py</code>, 프레임 처짐 '
                 '<code>frames.py</code>). 아래는 발주처·벤더 자료나 실물 시험이 있어야 정해지는 것들이다. '
                 '<b>임의값으로 채우지 않는다</b> — 채우면 검산이 거짓으로 통과하고, 그 사실을 현장에서 안다.</p>'
                 + table(["번호", "항목", "왜 지금 못 정하는가", "무엇이 있어야 닫히는가",
                          "닫히기 전에 하면 안 되는 것", "시작품 질문"], oi_rows, "tb")
                 + '<p class="note">시작품 질문 번호는 <code>src/pv_preprocess/prototype.py</code> 의 '
                 'Q1–Q7 이다 — 그 질문에 걸린 항목은 BFC 시작품이 답한다.</p>'
                 "</section>")
    parts.append("</main>\n</body>\n</html>\n")
    return "\n".join(parts)


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024:.0f} kB")


if __name__ == "__main__":
    main()
