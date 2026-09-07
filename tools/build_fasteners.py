# -*- coding: utf-8 -*-
"""체결 부품 도면집 — 볼트·너트·와셔의 형상도와 체결 상세, 적용표, 소요량.

정본은 `src/pv_preprocess/fasteners.py` 이고 등급·토크·구멍·매입은
`fabrication` 에서 온다. 여기서 하는 일은 그 값을 **그림으로** 내는 것이다.

    PYTHONPATH=src python tools/build_fasteners.py

멱등이다. `tests/test_pv_fasteners.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_infeed_detail import CSS, Sheet, esc, n, table  # noqa: E402

from pv_preprocess import fabrication as fab, fasteners as F  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-fastener-book.html"

#: 형상도에 그리는 대표 볼트 길이 (mm) — 실제 길이는 적용표가 정한다.
DRAW_LENGTH = 70


# ── 형상도 ──────────────────────────────────────────────────────────────
def _hex_across_corners(s: float) -> float:
    """대변 거리 s 인 정육각형의 대각 거리 e = 2s/√3."""
    return s * 2 / math.sqrt(3)


def _hexagon(sheet: Sheet, cx: float, cy: float, s: float, cls: str, title: str) -> None:
    """정면(대변이 위아래로 오는 자세)의 정육각형."""
    r = _hex_across_corners(s) / 2
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
           for a in range(0, 360, 60)]
    sheet.poly(pts + [pts[0]], cls, title)


def fastener_sheet(size: str) -> str:
    """호칭 하나의 형상도 — 볼트 측면, 머리 단면, 너트, 평와셔, 스프링와셔.

    뷰 간격은 각 뷰의 실제 반지름에서 낸다 — 고정 간격으로 두면 M6 에서는
    벌어지고 M24 에서는 겹친다.
    """
    b, nut = F.HEX_BOLT[size], F.HEX_NUT[size]
    pw, sw = F.PLAIN_WASHER[size], F.SPRING_WASHER[size]
    L = DRAW_LENGTH
    head_e, nut_e = _hex_across_corners(b.s), _hex_across_corners(nut.s)
    radii = (head_e / 2, nut_e / 2, pw.d2 / 2, sw.d2 / 2)
    gap = max(24.0, max(radii) * 0.9)

    cx: list[float] = []
    at = L + gap
    for r in radii:
        cx.append(at + r)
        at += 2 * r + gap
    top = max(b.s / 2, *radii)
    x0, x1 = -b.k - 14, cx[-1] + radii[-1] + 12
    y0, y1 = -top - 58, top + 26
    s = Sheet(x0, x1, y0, y1, 1_120, pad=(22, 20, 24, 22), flip_y=True)

    # ① 볼트 측면 — 머리 · 몸통 · 나사부
    s.rect(-b.k, 0, -b.s / 2, b.s / 2, "base", f"육각 머리 — 대변 {b.s:g} · 두께 {b.k:g}")
    s.rect(0, L - b.b, -b.d / 2, b.d / 2, "deck", f"몸통 Ø{b.d:g} (반나사 ISO 4014)")
    s.rect(L - b.b, L, -b.d / 2, b.d / 2, "roller", f"나사부 {b.b:g} · 피치 {b.pitch:g}")
    step = max(b.pitch, (b.b / 18))
    x = L - b.b
    while x < L - step:
        s.line(x, -b.d / 2, x + step * 0.6, b.d / 2, "leader")
        x += step
    s.dim_y(-b.s / 2, b.s / 2, -b.k - 6, f"s {b.s:g}", right=False)
    s.dim_x(-b.k, 0, top + 12, f"k {b.k:g}")
    s.dim_x(0, L, -b.s / 2 - 14, f"L — 적용표가 정한다 (그림 {L})", above=False)
    s.dim_x(L - b.b, L, -b.s / 2 - 30, f"나사부 b {b.b:g}", above=False)
    s.text((L - b.k) / 2, y0 + 8, f"육각볼트 {size} · KS B 1002 (ISO 4014) · 피치 {b.pitch:g}", "lbl", "middle")

    # ② 머리 단면 · ③ 너트 · ④ 평와셔 · ⑤ 스프링와셔
    _hexagon(s, cx[0], 0, b.s, "joint", f"머리 대변 {b.s:g} · 대각 {head_e:.1f}")
    s.circle(cx[0], 0, b.d / 2, "ref", f"나사 Ø{b.d:g}")
    s.text(cx[0], y0 + 26, f"머리 단면 · 대각 {head_e:.1f}", "lbl-small", "middle")
    s.text(cx[0], y0 + 10, f"스패너 회전 Ø{b.spanner_mm:g}", "lbl-muted", "middle")

    _hexagon(s, cx[1], 0, nut.s, "base", f"육각너트 {size} · 대변 {nut.s:g} · 높이 {nut.m:g}")
    s.circle(cx[1], 0, nut.d / 2, "ref", f"나사 Ø{nut.d:g}")
    s.text(cx[1], y0 + 26, f"육각너트 s {nut.s:g}", "lbl-small", "middle")
    s.text(cx[1], y0 + 10, f"높이 m {nut.m:g}", "lbl-muted", "middle")

    for i, (w, name, cls) in enumerate(((pw, "평와셔 KS B 1326", "deck"), (sw, "스프링와셔 KS B 1324", "roller"))):
        c = cx[2 + i]
        s.circle(c, 0, w.d2 / 2, cls, f"{name} {size} — 바깥 Ø{w.d2:g} · 안 Ø{w.d1:g} · 두께 {w.h:g}")
        s.circle(c, 0, w.d1 / 2, "ref", f"안지름 Ø{w.d1:g}")
        s.text(c, y0 + 26, name.split(" ")[0], "lbl-small", "middle")
        s.text(c, y0 + 10, f"Ø{w.d2:g}/{w.d1:g} × {w.h:g}", "lbl-muted", "middle")
    return s.svg(f"{size} 체결 부품 형상도")


#: 단면도에서 부재(판)를 그리는 반높이 (mm) — 도면용 표현값이지 설계 치수가 아니다.
SECTION_PLATE_HALF = 26.0

#: 단면도에 쓰는 대표 그립 (mm). 실제 판 두께는 자리마다 달라 적용표가 정한다.
SECTION_GRIP = 30.0


def _layer_legend(rows: list[tuple[int, str, float]]) -> str:
    return table(["번호", "층", "두께 (mm)"],
                 [[f"<b>{i}</b>", esc(name), f"{th:g}"] for i, name, th in rows], "kv", (2,))


def joint_section(kind: str, size: str = "M16") -> tuple[str, str]:
    """체결 상세 단면 — (도면, 층 범례). 층은 번호로 가리키고 두께는 표로 뺀다.

    얇은 와셔에 치수선을 직접 붙이면 3 mm 짜리 다섯 개가 겹친다.
    """
    b, nut = F.HEX_BOLT[size], F.HEX_NUT[size]
    pw, sw = F.PLAIN_WASHER[size], F.SPRING_WASHER[size]
    hole = fab.HOLE_MM[size]
    half = SECTION_PLATE_HALF

    if kind == "관통":
        layers = [("평와셔 (머리측)", pw.h, pw.d2 / 2, "deck"),
                  ("판 A + 판 B — 그립", SECTION_GRIP, half, "base"),
                  ("평와셔 (너트측)", pw.h, pw.d2 / 2, "deck"),
                  ("스프링와셔", sw.h, sw.d2 / 2, "roller"),
                  ("너트", nut.m, nut.s / 2, "joint")]
    else:
        eng = b.d
        layers = [("평와셔", pw.h, pw.d2 / 2, "deck"),
                  ("스프링와셔", sw.h, sw.d2 / 2, "roller"),
                  ("부재 (관통 구멍)", 12.0, half, "base"),
                  (f"모재 (탭 · 물림 {eng:g})", F.tapped_depth_mm(size, eng) + 8, half, "column")]

    span = sum(th for _, th, _, _ in layers)
    protrusion = F.PROTRUSION_THREADS * b.pitch if kind == "관통" else 0.0
    top = max(half, b.s / 2, *[hh for _, _, hh, _ in layers]) + 22
    s = Sheet(-b.k - 16, span + protrusion + 96, -top, top, 1_120, pad=(22, 22, 26, 22), flip_y=True)

    s.rect(-b.k, 0, -b.s / 2, b.s / 2, "joint", f"볼트 머리 — 대변 {b.s:g} · 두께 {b.k:g}")
    s.text(-b.k / 2, b.s / 2 + 8, "머리", "lbl-small", "middle")

    legend: list[tuple[int, str, float]] = []
    x = 0.0
    for i, (name, th, hh, cls) in enumerate(layers, start=1):
        s.rect(x, x + th, -hh, hh, cls, f"{i}. {name} — {th:g}")
        if "그립" in name or "관통 구멍" in name:
            s.rect(x, x + th, -hole / 2, hole / 2, "ref", f"관통 구멍 Ø{hole:g}")
        s.text(x + th / 2, hh + 8, str(i), "lbl", "middle")
        legend.append((i, name, th))
        x += th

    if kind == "관통":
        s.rect(0, span + protrusion, -b.d / 2, b.d / 2, "roller", f"볼트 {size} — 나사부가 너트를 지난다")
        s.text(span + protrusion + 8, 0, f"나사산 {F.PROTRUSION_THREADS} 산 이상 나온다", "lbl-muted", "start", dy=4)
        s.dim_x(0, span + protrusion, -top + 26,
                f"필요 길이 = 그립 {SECTION_GRIP:g} + 부속 {F.stack(size, '관통').consumed_mm:g}", above=False)
        note = f"관통 체결 단면 (예 {size}) · 판 두께는 자리마다 다르다 — 적용표가 정한다"
    else:
        eng = b.d
        depth = F.tapped_depth_mm(size, eng)
        base = sum(th for _, th, _, _ in layers[:-1])
        s.rect(0, base + eng, -b.d / 2, b.d / 2, "roller", f"볼트 {size}")
        s.rect(base, base + depth, -b.d / 2 - 1.5, b.d / 2 + 1.5, "ref",
               f"탭 깊이 {depth:g} = 물림 {eng:g} + 2 피치")
        s.dim_x(base, base + eng, -top + 26, f"나사 물림 {eng:g} (강 1.0 d)", above=False)
        s.dim_x(base, base + depth, -top + 12, f"탭 깊이 {depth:g}", above=False)
        note = f"탭 체결 단면 (예 {size}) · 알루미늄 모재는 물림 2.0 d · 진동부는 나사고정제"
    s.text(-b.k - 12, top - 12, note, "lbl-muted")
    return s.svg(f"{kind} 체결 상세 단면"), _layer_legend(legend)


def anchor_section(size: str = "M20") -> str:
    """앵커 단면 — 매입·그라우트·베이스플레이트·너트가 길이를 어떻게 먹는가.

    세로로 긴 단면이라 도판 폭을 실제보다 넓게 잡는다. 안 그러면 폭에 맞춘
    축척 때문에 도면이 화면 몇 개 높이로 늘어난다.
    """
    b, nut = F.HEX_BOLT[size], F.HEX_NUT[size]
    pw = F.PLAIN_WASHER[size]
    embed = fab.ANCHOR_EMBED_MM[size]
    plate, grout = 25.0, 30.0
    total = embed + grout + plate + pw.h + nut.m + F.PROTRUSION_THREADS * b.pitch
    rod = F.anchor_rod_for(size, total)
    y0, y1 = -embed - 46, total - embed + 52
    x0, x1 = -330.0, 330.0                        # 세로 단면 — 폭을 넓혀 세로 축척을 잡는다
    s = Sheet(x0, x1, y0, y1, 1_120, pad=(22, 20, 24, 22), flip_y=True)

    s.rect(-150, 150, y0, 0, "floor", "콘크리트 C24 이상")
    s.rect(-(b.d + 4) / 2, (b.d + 4) / 2, -embed, 0, "ref", f"천공 Ø{b.d + 4:g} · 케미컬 주입")
    s.rect(-104, 104, 0, grout, "deck", f"무수축 그라우트 {grout:g}")
    s.rect(-104, 104, grout, grout + plate, "base", f"베이스플레이트 {plate:g}")
    s.rect(-pw.d2 / 2, pw.d2 / 2, grout + plate, grout + plate + pw.h, "deck", f"평와셔 {pw.h:g}")
    s.rect(-nut.s / 2, nut.s / 2, grout + plate + pw.h, grout + plate + pw.h + nut.m, "joint",
           f"너트 {nut.m:g}")
    s.rect(-b.d / 2, b.d / 2, -embed, total - embed, "roller", f"앵커 로드 {size} · 필요 전장 {total:g}")

    for z, label in ((-embed, f"매입 {embed:g} — 케미컬 정착"), (0, "바닥면 (기초 상면)"),
                     (grout, f"그라우트 {grout:g}"), (grout + plate, f"베이스플레이트 {plate:g}"),
                     (total - embed, f"나사산 {F.PROTRUSION_THREADS} 산 여유")):
        s.line(-150, z, 128, z, "level")
        s.text(134, z, label, "lvl", "start", dy=3)
    s.dim_y(-embed, total - embed, -168, f"필요 전장 {total:g}")
    s.text(-320, y1 - 14, f"케미컬 앵커 단면 (예 {size}) · 필요 전장 {total:g} → 표준 로드 {size}×{rod}", "lbl-muted")
    s.text(-320, y0 + 14, "그라우트 양생 전에 토크를 걸면 케미컬이 깨진다", "lbl-muted")
    return s.svg("케미컬 앵커 상세 단면")


# ── 표 ──────────────────────────────────────────────────────────────────
def geometry_table() -> str:
    rows = []
    for size in F.sizes_used():
        b, nut = F.HEX_BOLT[size], F.HEX_NUT[size]
        pw, sw = F.PLAIN_WASHER[size], F.SPRING_WASHER[size]
        lo, hi = fab.TORQUE_NM[size]
        rows.append([f"<code>{size}</code>", f"{b.pitch:g}", f"{b.s:g}", f"{_hex_across_corners(b.s):.1f}",
                     f"{b.k:g}", f"{b.b:g}", f"{nut.s:g}", f"{nut.m:g}",
                     f"Ø{pw.d2:g}/{pw.d1:g}×{pw.h:g}", f"Ø{sw.d2:g}/{sw.d1:g}×{sw.h:g}",
                     f"{fab.HOLE_MM[size]:g}", f"{lo:g} / {hi:g}"])
    return table(["호칭", "피치", "머리 s", "머리 대각 e", "머리 k", "나사부 b",
                  "너트 s", "너트 m", "평와셔", "스프링와셔", "관통 구멍", "토크 8.8 / 10.9"],
                 rows, "", tuple(range(1, 12)))


def stack_table() -> str:
    rows = []
    for size in F.sizes_used():
        for kind in ("관통", "탭", "앵커"):
            st = F.stack(size, kind)
            rows.append([f"<code>{size}</code>", kind,
                         " + ".join(f"{name} {t:g}" for name, t in st.items),
                         f"{st.consumed_mm:g}"])
    return table(["호칭", "체결", "부속 쌓임 (mm)", "볼트 길이에서 먹는 합"], rows, "", (3,))


def grades_table() -> str:
    return table(["등급", "재질", "강도", "짝 너트", "표면처리"],
                 [[f"<code>{esc(a)}</code>", esc(b), esc(c), esc(d), esc(e)] for a, b, c, d, e in F.GRADES])


def engagement_table() -> str:
    rows = []
    for material, mult, why in F.ENGAGEMENT:
        depths = " · ".join(f"{s} {F.tapped_depth_mm(s, F.HEX_BOLT[s].d * mult):g}" for s in F.sizes_used())
        rows.append([esc(material), f"{mult:g} d", depths, esc(why)])
    return table(["모재", "최소 물림", "탭 깊이 (물림 + 2 피치)", "근거"], rows)


def locking_table() -> str:
    return table(["자리", "풀림 방지", "방법"], [[esc(a), esc(b), esc(c)] for a, b, c in F.LOCKING])


def use_table() -> str:
    rows = []
    for u in F.uses():
        grip = u.grip_max_mm
        rows.append([f"<code>{esc(u.sheet)}</code>", esc(u.assembly), esc(u.joint), esc(u.parts),
                     f"<code>{u.size}×{u.length:g}</code>", esc(u.cls), esc(u.kind), str(u.qty),
                     f"{u.torque_nm:g}" if u.torque_nm else "—",
                     f"{u.hole_mm:g}" if u.kind != "탭" else "탭",
                     f"{grip:g}" if grip is not None else "—"])
    return table(["도번", "조립체", "체결부", "부품", "볼트", "등급", "종류", "수량 (플랜트)",
                  "토크 N·m", "구멍 Ø", "물 수 있는 두께"], rows, "", (7, 8, 9, 10))


def demand_table() -> str:
    rows = [[f"<code>{s}</code>", esc(c), str(b), str(nu), str(pw), str(sw), str(sp)]
            for s, c, b, nu, pw, sw, sp in F.demand()]
    total = F.summary()
    rows.append(["<b>합계</b>", "", f"<b>{total['bolts']}</b>", f"<b>{total['nuts']}</b>",
                 f"<b>{total['plain_washers']}</b>", f"<b>{total['spring_washers']}</b>",
                 f"<b>{total['bolts_with_spare']}</b>"])
    return table(["호칭", "등급", "볼트", "너트", "평와셔", "스프링와셔", "볼트 (예비 10 %)"],
                 rows, "", (2, 3, 4, 5, 6))


def anchor_table() -> str:
    rows = []
    for tag, size, length, need, slack, ok in F.anchor_lengths():
        mark = '<b class="ok">여유</b>' if ok else '<b class="bad">부족</b>'
        rows.append([esc(tag), f"<code>{size}×{length:g}</code>", f"{fab.ANCHOR_EMBED_MM[size]:g}",
                     f"{need:g}", f"{slack:+g}", mark])
    return table(["조립체", "앵커 로드", "매입", "필요 전장", "여유", "판정"], rows, "", (2, 3, 4))


def check_table() -> str:
    rows = []
    for name, result in (("설계 호칭이 형상표에 있는가", F.geometry_covers_the_design()),
                         ("관통 구멍 > 볼트 지름", F.holes_clear_the_bolts()),
                         ("평와셔가 관통 구멍을 덮는가", F.washers_cover_the_holes()),
                         ("반나사 볼트로 성립하는가", F.threads_reach_the_nuts())):
        bad = [k for k, v in result.items() if not v]
        rows.append([esc(name), esc(" · ".join(result)),
                     '<b class="ok">전부 통과</b>' if not bad else f'<b class="bad">{esc(", ".join(bad))}</b>'])
    lengths = F.lengths_are_long_enough()
    short = [f"{u.sheet} {u.joint}" for u, _, v in lengths if not v.startswith("여유")]
    rows.append(["볼트 길이가 부속을 넘는가", f"{len(lengths)} 건",
                 '<b class="ok">전부 통과</b>' if not short else f'<b class="bad">{esc(", ".join(short))}</b>'])
    anchors = F.anchor_lengths()
    bad_anchor = [r[0] for r in anchors if not r[5]]
    rows.append(["앵커 로드가 너트까지 닿는가", f"{len(anchors)} 건",
                 '<b class="ok">전부 통과</b>' if not bad_anchor else f'<b class="bad">{esc(", ".join(bad_anchor))}</b>'])
    return table(["검산", "대상", "판정"], rows)


EXTRA_CSS = """
.ok { color: var(--green); }
.bad { color: var(--red); }
.callout { border-left: 3px solid var(--blue); background: var(--tint); padding: 12px 16px; margin: 0; }
.callout p { margin: 0 0 8px; } .callout p:last-child { margin: 0; }
"""


def build() -> str:
    s = F.summary()
    parts: list[str] = [
        "<!doctype html>",
        "<!-- 이 파일은 손으로 쓰지 않는다. 정본은 src/pv_preprocess/fasteners.py 이고 "
        "tools/build_fasteners.py 가 찍는다. -->",
        '<html lang="ko"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>투입 구간 체결 부품 도면집 — 볼트·너트·와셔 형상과 체결 상세</title>",
        f"<style>{CSS}{EXTRA_CSS}</style>",
        "</head><body>",
        '<main class="page">',

        '<header class="title"><div>',
        '<div class="eyebrow">DYNAMIC INDUSTRY · 태양광 패널 전처리 플랜트 · 투입 구간 · 체결 부품 · REV.A</div>',
        "<h1>체결 부품 도면집 — 볼트·너트·와셔의 형상과 치수, 그리고 길이 검산</h1>",
        "<p>제작 도면집은 체결을 호칭으로 적는다. 그것으로 발주는 되지만 제작은 안 된다. "
        "육각 머리의 대변 거리를 모르면 공구 자리를 못 잡고, 너트 높이와 와셔 두께를 모르면 "
        "볼트 길이가 맞는지 알 수 없다. 이 문서가 그 형상과 쌓임을 그림으로 내고, "
        f"설계에 쓰인 체결 {s['joints']}건의 길이를 전부 검산한다.</p>",
        "</div>",
        '<dl class="block">',
        "<dt>문서</dt><dd class=\"mono\">PV-FAS-000 · REV.A</dd>",
        f"<dt>호칭</dt><dd>{s['sizes']}종 ({' · '.join(F.sizes_used())})</dd>",
        f"<dt>체결부</dt><dd>{s['joints']}건</dd>",
        f"<dt>소요</dt><dd>볼트 {n(s['bolts'])} · 너트 {n(s['nuts'])} · 와셔 {n(s['plain_washers'] + s['spring_washers'])}</dd>",
        "<dt>단위</dt><dd class=\"mono\">mm · N·m</dd>",
        '<dt>생성</dt><dd class="mono">tools/build_fasteners.py</dd>',
        "</dl></header>",

        '<section id="basis"><h2>이 문서의 값이 어디서 오는가</h2>',
        '<div class="callout">',
        "<p><b>형상 치수는 KS·ISO 규격의 호칭값이다.</b> 육각볼트 KS B 1002(ISO 4014) · "
        "육각너트 KS B 1012(ISO 4032) · 평와셔 KS B 1326(ISO 7089) · 스프링와셔 KS B 1324. "
        "지어낸 값이 아니라 규격표의 값이고, 조달품은 벤더 시험성적서가 최종 근거다.</p>",
        "<p><b>등급·토크·구멍·매입 깊이는 제작 도면집에서 그대로 읽어 온다.</b> "
        "두 문서에 같은 값을 두 번 적지 않는다 — 적으면 갈라진다.</p>",
        "<p><b>길이는 계산한다.</b> 볼트 길이는 판 두께만으로 정해지지 않는다. "
        "평와셔 2 · 스프링와셔 1 · 너트 1 · 나사산 여유가 먼저 먹고 남는 것이 물 수 있는 두께다. "
        "이 계산이 <b>앵커 로드 10건이 짧다</b>는 것을 찾아냈고, 표준 계열의 다음 길이로 고쳤다.</p>",
        "</div>",
        "<h3>검산</h3>",
        check_table(),
        "</section>",

        '<section id="geometry"><h2>형상과 치수</h2>',
        geometry_table(),
        "<p class=\"note\">머리 대각 e 는 대변 거리에서 파생한다(2s/√3) — 소켓 공구와 카운터보어 지름을 잡는 값이다. "
        "나사부 b 는 반나사 볼트(ISO 4014)의 값이고 L ≤ 125 에서 2d + 6 이다.</p>",
    ]

    for size in F.sizes_used():
        b = F.HEX_BOLT[size]
        parts.append(f'<h3>{size} — 피치 {b.pitch:g} · 머리 대변 {b.s:g} · 스패너 회전 Ø{b.spanner_mm:g}</h3>')
        parts.append(fastener_sheet(size))
    parts.append("</section>")

    parts += [
        '<section id="section"><h2>체결 상세 — 무엇이 어떤 순서로 쌓이는가</h2>',
        "<h3>관통 체결</h3>", *joint_section("관통"),
        "<h3>탭 체결</h3>", *joint_section("탭"),
        "<h3>케미컬 앵커</h3>", anchor_section(),
        "<h3>부속 쌓임 — 볼트 길이에서 먹는 두께</h3>",
        stack_table(),
        "<h3>나사 물림과 탭 깊이</h3>",
        engagement_table(),
        "</section>",

        '<section id="material"><h2>재질 · 표면처리 · 풀림 방지</h2>',
        grades_table(),
        "<h3>풀림 방지</h3>",
        locking_table(),
        "<h3>조임 규칙</h3>",
        "<ul class=\"note\">"
        "<li>토크렌치는 교정 1년 이내. 조인 뒤 볼트·너트·부재에 걸쳐 마킹 페인트.</li>"
        "<li>여러 개를 조이는 자리는 대각 순서로 2회에 나눠 조인다 — 1회차 50 %, 2회차 100 %.</li>"
        "<li>플랜지·베이스플레이트는 중앙에서 바깥으로.</li>"
        "<li>10.9 볼트는 재사용하지 않는다. 한 번 항복 근처까지 조인 볼트는 버린다.</li>"
        "<li>앵커는 그라우트 양생 뒤에 규정 토크 — 양생 전에 걸면 케미컬이 깨진다.</li>"
        "<li>도장면 위로 조이지 않는다. 접촉면은 마스킹하거나 조인 뒤 도장한다.</li>"
        "</ul>",
        "</section>",

        '<section id="anchor"><h2>앵커 로드 길이 검산</h2>',
        "<p>필요 전장 = 매입 + 베이스플레이트 + 그라우트 + 평와셔 + 너트 + 나사산 2피치. "
        "로드는 임의 길이로 안 나오므로 표준 계열에서 이 합을 넘는 가장 짧은 것을 고른다.</p>",
        anchor_table(),
        "</section>",

        '<section id="use"><h2>적용표 — 어느 자리에 무엇이 들어가는가</h2>',
        "<p>제작 도면집의 체결표를 형상까지 풀어 놓은 것이다. "
        "「물 수 있는 두께」는 이 볼트 길이에서 부속을 빼고 남는 값 — 실제 판 두께가 이보다 두꺼우면 볼트를 늘려야 한다.</p>",
        use_table(),
        "</section>",

        '<section id="demand"><h2>소요량</h2>',
        "<p>플랜트 전량 기준이다. 볼트는 예비 10 % 를 더한 값을 같이 낸다 — "
        "탭 체결은 너트가 없고, 앵커는 스프링와셔를 쓰지 않는다.</p>",
        demand_table(),
        "</section>",
        "</main></body></html>",
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024:.1f} kB")


if __name__ == "__main__":
    main()
