#!/usr/bin/env python3
"""MP-50 부품별 상세도면 생성 — ``docs/drawings/mp50-part-drawings.html``.

아세이도(MP50-A~K)가 "어디에 어떻게 붙는가"를 보여준다면, 부품도는 **그 부품
하나를 어떻게 깎고 말고 뚫는가**를 보여준다. 가공자는 아세이도를 보지 않고
부품도 한 장만 들고 작업대에 선다. 그래서 각 장은 그 부품만으로 완결돼야 한다 —
소재 규격, 완성 치수, 기하공차, 표면, 가공 순서, 검사.

**부품도는 제작품에만 붙는다.** 볼트·키·O-링은 규격을 적어 주문하고, 모터·밸브·
센서는 벤더가 만든다. 그런 것에 부품도를 그리면 현장에서 "이걸 깎으라는
말인가" 하는 혼선만 생긴다. 구분은 ``components.PROCUREMENT`` 이 정한다.

    python tools/mp50_parts.py
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from _mp50_draft import (  # noqa: E402
    FRAME, T_DIM, T_LABEL, T_NOTE, T_VIEW, THICK, THIN,
    Canvas, View, document, esc, fmt, text_width, wrap,
)

from mp50_separator import GEOMETRY as G  # noqa: E402
from mp50_separator.components import ASSEMBLIES, BY_CODE, FABRICATED, Part  # noqa: E402
from mp50_separator.geometry import COVER_NOZZLES, NOZZLES  # noqa: E402

REV = "R1"
DATE = "2026-09-11"
OUT = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "mp50-part-drawings.html"

#: 기입 없는 치수에 적용되는 일반공차. 부품도마다 되풀이하지 않고 여기서 한 번 건다.
GENERAL_TOLERANCE = "ISO 2768-mK"

SHEETS: list[Canvas] = []
ALLOW_PARTIAL = False   # 작성 중에만 켠다
PART_OF = {p.no: a for a in ASSEMBLIES for p in a.parts}
PART = {p.no: p for a in ASSEMBLIES for p in a.parts}

#: 한 장에 같이 싣는 부품 (소물). 대표 번호 → 함께 싣는 번호들.
SHARED: dict[str, tuple[str, ...]] = {
    "A-07": ("B-03",),
    "E-02": ("F-04",),
    "H-01": ("H-02", "H-03", "H-04"),
    "D-02": ("D-03",),
}
#: 위 표에서 대표가 아닌 쪽 — 자기 장을 갖지 않는다.
FOLDED = {no for group in SHARED.values() for no in group}


def right_column(c: Canvas, part: Part, steps: list[str], inspect: list[tuple[str, str]],
                 extra: list[str] | None = None, also: tuple[str, ...] = ()) -> None:
    """부품도 오른쪽 기둥 — 정보표 · 가공 순서 · 검사 · 주기.

    모든 장이 같은 자리에 같은 것을 담아야 가공자가 장을 넘길 때마다 눈을 다시
    두지 않는다.
    """
    x = 258.0
    asm = PART_OF[part.no]
    rows = [["항목", "내용"]]
    rows += [
        ["부품번호", part.no + (" · " + " · ".join(also) if also else "")],
        ["품명", part.name],
        ["상위 아세이", f"{asm.code} {asm.name}"],
        ["재질", part.material],
        ["소재", part.stock],
        ["수량", f"{part.qty} 개" + (f" (+{sum(PART[o].qty for o in also)})" if also else "")],
        ["단품 질량", f"{part.unit_kg:.3f} kg" if part.unit_kg else "-"],
        ["일반공차", GENERAL_TOLERANCE],
        ["상태", part.status],
    ]
    # 합본한 소물도 자기 소재 규격을 여기서 읽을 수 있어야 한다 — 대표 부품의
    # 소재만 적어 두면 가공자가 두 번째 부품의 소재를 어디서도 찾지 못한다.
    for o in also:
        rows.append([f"{o} 소재", f"{PART[o].name} · {PART[o].stock}"])
    c.view_title(x, 30.0, "부품 정보")
    end = c.table(x, 34.0, [26.0, 126.0], rows, row_h=5.2, size=T_DIM - 0.2,
                  aligns=["start", "start"])

    c.view_title(x, end + 9.0, "가공 순서")
    y = end + 14.0
    for i, step in enumerate(steps, 1):
        c.text(x, y, f"{i}", T_DIM - 0.2, "start", "tx", weight="600", mono=True)
        for j, line in enumerate(wrap(step, 68)):
            c.text(x + 6.0, y, line, T_DIM - 0.2, "start", "tx2")
            y += 3.9
        y += 1.0

    c.view_title(x, y + 5.0, "검사")
    ins = [["항목", "기준"]] + [list(r) for r in inspect]
    y = c.table(x, y + 9.0, [46.0, 106.0], ins, row_h=5.0, size=T_DIM - 0.3,
                aligns=["start", "start"])

    notes = list(extra or [])
    if part.note and part.note != "-":
        notes.insert(0, part.note)
    if notes:
        c.view_title(x, y + 8.0, "주기")
        y += 13.0
        for n in notes:
            for line in wrap("· " + n, 68):
                c.text(x, y, line, T_DIM - 0.3, "start", "tx2")
                y += 3.9
            y += 0.8


_COUNTER = [1]     # 표지가 1 장이므로 부품도는 2 번부터 센다


def part_sheet(no: str, title: str, subtitle: str, scale: str, aria: str) -> tuple[Canvas, Part]:
    part = PART[no]
    c = Canvas(f"MP50-P-{no.replace('-', '')}", title, subtitle, scale, aria)
    SHEETS.append(c)
    also = SHARED.get(no, ())
    _COUNTER[0] += 1
    c.frame_and_title(REV, DATE, f"{_COUNTER[0]}/{TOTAL_SHEETS}")
    chips = [("부품번호", no), ("재질", part.material), ("수량", f"{part.qty}" +
             (f" + {sum(PART[o].qty for o in also)}" if also else "")),
             ("단품 질량", f"{part.unit_kg:.3f} kg" if part.unit_kg else "-"),
             ("일반공차", GENERAL_TOLERANCE), ("상태", part.status)]
    c.head(chips)
    return c, part


TOTAL_SHEETS = 0   # 본문 아래에서 채운다


# ==========================================================================
# 공용 뷰 조각
# ==========================================================================
def plate_edge(c: Canvas, v: View, x0: float, x1: float, z: float, t: float,
               ident: str = "hP") -> None:
    """판재를 옆에서 본 모습. 얇아도 두께가 보이게 채운다."""
    pts = v.pts([(x0, z), (x1, z), (x1, z - t), (x0, z - t)])
    if v.d(t) >= 1.2:
        c.hatch(pts, ident, 45)
    else:
        c.fill(pts, "var(--ink)", 0.82)
    c.poly(pts, THICK, "ln", close=True)


def bolt_circle(c: Canvas, v: View, pcd: float, n: int, dia: float,
                start: float = 0.0) -> None:
    c.circle(v.x(0), v.y(0), v.d(pcd / 2), THIN, "cl", dash="6 1.2 1.2 1.2")
    for i in range(n):
        a = math.radians(360 / n * i + start)
        cx, cy = v.x(pcd / 2 * math.cos(a)), v.y(pcd / 2 * math.sin(a))
        c.circle(cx, cy, v.d(dia / 2), THICK, "ln")
        c.centreline(cx - v.d(dia), cy, cx + v.d(dia), cy)
        c.centreline(cx, cy - v.d(dia), cx, cy + v.d(dia))


def cross_centre(c: Canvas, v: View, r: float) -> None:
    c.centreline(v.x(-r), v.y(0), v.x(r), v.y(0))
    c.centreline(v.x(0), v.y(-r), v.x(0), v.y(r))


# ==========================================================================
# A 탱크
# ==========================================================================
def sheet_a01() -> None:
    c, part = part_sheet(
        "A-01", "동체 (Shell)", "Ø400 ID × H600 × t3 · 롤링 + 세로이음",
        "1:10", "동체 부품도 — 전개 절단 원도, 완성 형상, 노즐 구멍 위치표, 세로이음 개선")

    # --- 전개 (주뷰) ---
    L, H = G.shell_development_length_mm, G.shell_height_mm
    v = View(22.0, 112.0, 10.0)
    c.rect(v.x(0), v.y(H), v.d(L), v.d(H), THICK, "ln")
    c.dim_h(v.x(0), v.x(L), v.y(H) - 9.0, f"{fmt(L, 2)} ±1.0", ext_from=v.y(H))
    c.dim_v(v.y(0), v.y(H), v.x(0) - 4.0, f"{fmt(H)} ±1.0", ext_from=v.x(0))
    r_mid = (G.tank_id_mm + G.shell_thickness_mm) / 2
    for n in NOZZLES:
        arc = math.radians(n.theta_deg) * r_mid
        z = n.z_mm - G.shell_bottom_z
        c.circle(v.x(arc), v.y(z), v.d(n.tube_od_mm / 2 + 2), THICK, "ln")
        c.centreline(v.x(arc) - v.d(n.tube_od_mm + 18), v.y(z),
                     v.x(arc) + v.d(n.tube_od_mm + 18), v.y(z))
        c.centreline(v.x(arc), v.y(z) - v.d(n.tube_od_mm + 18),
                     v.x(arc), v.y(z) + v.d(n.tube_od_mm + 18))
    for i, th in enumerate((90.0, 180.0, 270.0, 315.0)):
        arc = math.radians(th) * r_mid
        c.dim_h(v.x(0), v.x(arc), v.y(H) + 10.0 + i * 7.4, f"{fmt(arc, 1)}  θ{fmt(th)}°",
                ext_from=v.y(0) if i == 0 else None)
    c.view_title(14.0, 30.0, "전개 절단 원도", v.label)
    c.text(14.0, 40.0, "롤링 방향 →  ·  압연 방향(grain)을 원주방향으로", T_DIM - 0.2, "start", "tx2")
    c.text(v.x(0), v.y(H) + 46.0,
           "구멍은 롤링·용접 뒤에 뚫는다. 전개 상태에서 뚫으면 롤링 중 타원이 된다.",
           T_DIM - 0.2, "start", "tx2")

    # --- 완성 형상 ---
    f = View(196.0, 168.0, 6.0)
    ri, ro = G.tank_id_mm / 2, G.tank_id_mm / 2 + G.shell_thickness_mm
    c.centreline(f.x(0), f.y(-14), f.x(0), f.y(H + 14))
    for sign in (1.0, -1.0):
        pts = f.pts([(sign * ri, 0), (sign * ro, 0), (sign * ro, H), (sign * ri, H)])
        c.fill(pts, "var(--ink)", 0.82)
        c.poly(pts, THICK, "ln", close=True)
    c.dim_h(f.x(-ri), f.x(ri), f.y(H) - 9.0, f"Ø{fmt(G.tank_id_mm)} ID", ext_from=f.y(H))
    c.dim_v(f.y(0), f.y(H), f.x(ro) + 9.0, fmt(H), ext_from=f.x(ro), left=False)
    c.leader(f.x(ro), f.y(H * 0.62), f.x(ro) + 22.0, f.y(H * 0.86),
             f"t{fmt(G.shell_thickness_mm)}")
    c.surface(f.x(-ro) - 30.0, f.y(H * 0.40), "Ra 0.8", "내면 전체")
    w = c.fcf(f.x(-ro) - 34.0, f.y(H * 0.20), "round", "2.0")
    c.text(f.x(-ro) - 34.0, f.y(H * 0.20) + w * 0 + 8.4, "내경 4 방향 측정",
           T_DIM - 0.4, "start", "tx2")
    c.view_title(160.0, 30.0, "완성 형상", f.label)

    # --- 세로이음 개선 ---
    d = View(64.0, 246.0, 0.26)
    c.view_title(14.0, 214.0, "세로이음 개선", "4:1")
    for sx, off in ((-1, -0.5), (1, 0.5)):
        pts = d.pts([(sx * 7 + off, -1.5), (sx * 1.2 + off, -1.5),
                     (sx * 0.5 + off, 1.5), (sx * 7 + off, 1.5)])
        c.hatch(pts, "hW", 45 if sx > 0 else -45)
        c.poly(pts, THICK, "ln", close=True)
    c.dim_h(d.x(-0.5), d.x(0.5), d.y(5.4), "1.0", ext_from=d.y(1.5))
    c.dim_v(d.y(-1.5), d.y(1.5), d.x(-8.4), "t3", ext_from=d.x(-7.0))
    c.leader(d.x(1.2), d.y(-1.0), d.x(9.0), d.y(-7.0), "V 개선 70°",
             lines=("루트면 0.5 · 루트 갭 1.0", "이면 아르곤 백퍼지"))
    c.text(14.0, 276.0, "백퍼지 없이 용접하면 이면에 산화막이 남고, 그 자리가 염수에서",
           T_DIM - 0.2, "start", "tx2")
    c.text(14.0, 280.0, "먼저 공식(pitting)이 된다.", T_DIM - 0.2, "start", "tx2")

    # --- 구멍 위치표 ---
    rows = [["노즐", "호길이", "전개 y", "구멍 Ø"]]
    for n in NOZZLES:
        rows.append([n.tag, f"{math.radians(n.theta_deg) * r_mid:.1f}",
                     f"{n.z_mm - G.shell_bottom_z:.0f}", f"{n.tube_od_mm + 4:.1f}"])
    c.view_title(138.0, 214.0, "구멍 위치 (전개 기준)")
    c.table(138.0, 218.0, [22.0, 26.0, 24.0, 24.0], rows, row_h=5.0, size=T_DIM - 0.3,
            aligns=["middle", "end", "end", "end"])
    c.text(138.0, 280.0, "호길이는 중립축 반지름 " + f"{r_mid:.1f}" + " 기준.",
           T_DIM - 0.3, "start", "tx2")

    right_column(
        c, part,
        steps=[
            f"t{fmt(G.shell_thickness_mm)} 판재를 전개 {fmt(L, 2)} × {fmt(H)} 로 절단. 레이저 절단, 절단면 산세.",
            "압연 방향(grain)을 원주방향에 맞춰 롤벤딩. 스프링백을 보고 나눠 말 것.",
            "세로이음 V70° 개선 가공, 루트 갭 1.0 · 루트면 0.5.",
            "이면 아르곤 백퍼지 상태로 TIG 전용입 용접 (W4).",
            "내면 용접부 평활 연삭 후 Ra ≤ 0.8 까지 버프. 걸리는 턱을 남기지 않는다.",
            f"내경을 4 방향에서 재어 Ø{fmt(G.tank_id_mm)} ±2 에 들 때까지 재교정.",
            "노즐 구멍 9 개소 타공 — 왼쪽 구멍 위치표의 호길이·전개 y 로 먹매김.",
            f"액면 눈금 각인 (J-05) — Z{fmt(G.nominal_level_z, 0)}(50 L) · Z{fmt(G.operating_level_z)}({G.operating_volume_l:.1f} L).",
            "전 표면 산세 · 부동태화.",
        ],
        inspect=[
            ("전개 길이", f"{fmt(L, 2)} ±1.0 (절단 직후)"),
            ("높이", f"{fmt(H)} ±1.0"),
            ("진원도", f"Ø{fmt(G.tank_id_mm)} ±2 · 내경 4 방향"),
            ("세로이음", "PT 100 % · 균열·융합불량 없을 것"),
            ("내면 조도", "Ra ≤ 0.8 · 걸리는 턱 없을 것"),
            ("노즐 표고", "MP50-A3 노즐표 공차 내"),
            ("부동태화", "페록실 시험 청색 반응 없을 것"),
        ],
        extra=[f"전개는 **중립축** 둘레 π×(ID+t) = {fmt(L, 2)} 다. 안지름이나 "
               f"바깥지름으로 자르면 롤링 후 Ø{fmt(G.tank_id_mm)} 가 나오지 않는다.",
               "세로이음은 N1(θ0°)과 겹치지 않게 θ30° 로 옮겨 절단한다."],
    )


def sheet_a02() -> None:
    c, part = part_sheet(
        "A-02", "원뿔 (Cone)", f"Ø400 → Ø59.5 · 60° · H{G.cone_truncated_height_mm:.2f}",
        "1:10", "원뿔 부품도 — 전개 부채꼴, 완성 단면, 가상 정점과 모선 길이")

    ro, ri = G.cone_development_outer_r_mm, G.cone_development_inner_r_mm
    ang = G.cone_development_angle_deg
    v = View(92.0, 128.0, 10.0)
    cx, cy = v.p(0, 0)
    c.arc(cx, cy, v.d(ro), 0, ang, THICK, "ln")
    c.arc(cx, cy, v.d(ri), 0, ang, THICK, "ln")
    for a in (0.0, ang):
        ar = math.radians(a)
        c.line(cx + v.d(ri) * math.cos(ar), cy - v.d(ri) * math.sin(ar),
               cx + v.d(ro) * math.cos(ar), cy - v.d(ro) * math.sin(ar), THICK, "ln")
    c.centreline(cx - v.d(ro) - 8, cy, cx + v.d(ro) + 8, cy)
    c.circle(cx, cy, 0.9, THIN, "ln")
    c.dim_h(cx, cx + v.d(ro), cy + 10.0, f"R{fmt(ro, 1)} ±1.0")
    c.dim_h(cx, cx + v.d(ri), cy + 19.0, f"R{fmt(ri, 1)}")
    c.dim_v(cy - v.d(ro), cy, cx - v.d(ro) - 11.0, f"{fmt(ro, 0)}")
    c.text(cx, cy - v.d(ro) - 8.0, f"사잇각 {fmt(ang, 1)}° = 360° × sin{fmt(G.cone_half_angle_deg)}°",
           T_NOTE, "middle", "tx", weight="600")
    c.text(cx, cy - v.d(ro) - 13.0, "60° 원뿔은 전개하면 정확히 반원이라 소재 손실이 적다",
           T_DIM - 0.2, "middle", "tx2")
    c.leader(cx - v.d((ro + ri) / 2), cy, cx - v.d(ro) - 6, cy + 34.0,
             "세로이음 1 개소", anchor="end", lines=("맞대기 전용입 · 백퍼지",))
    c.view_title(14.0, 30.0, "전개 절단 원도", v.label)

    f = View(60.0, 256.0, 4.0)
    bot, top = 0.0, G.cone_truncated_height_mm
    dx = G.shell_thickness_mm / math.cos(math.radians(G.cone_half_angle_deg))
    for sign in (1.0, -1.0):
        pts = f.pts([(sign * G.cone_outlet_id_mm / 2, bot), (sign * G.tank_id_mm / 2, top),
                     (sign * (G.tank_id_mm / 2 + dx), top),
                     (sign * (G.cone_outlet_id_mm / 2 + dx), bot)])
        c.fill(pts, "var(--ink)", 0.82)
        c.poly(pts, THICK, "ln", close=True)
    c.centreline(f.x(0), f.y(bot - 40), f.x(0), f.y(top + 16))
    c.dim_h(f.x(-G.tank_id_mm / 2), f.x(G.tank_id_mm / 2), f.y(top) - 10.0,
            f"Ø{fmt(G.tank_id_mm)} ID", ext_from=f.y(top))
    c.dim_h(f.x(-G.cone_outlet_id_mm / 2), f.x(G.cone_outlet_id_mm / 2), f.y(bot) + 12.0,
            f"Ø{fmt(G.cone_outlet_id_mm, 1)} ID", ext_from=f.y(bot))
    c.dim_v(f.y(bot), f.y(top), f.x(G.tank_id_mm / 2 + 34) + 8.0,
            f"{fmt(top, 2)} ±1.0", left=False)
    ax, ay = f.x(0), f.y(-G.cone_outlet_z)
    c.poly([(f.x(-G.tank_id_mm / 2), f.y(top)), (ax, ay), (f.x(G.tank_id_mm / 2), f.y(top))],
           THIN, "dl", dash="3 1.5")
    c.arc(ax, ay, 13.0, 62, 118, THIN, "dl")
    c.text(ax, ay - 15.4, f"{fmt(G.cone_included_deg)}° ±0.5°", T_NOTE, "middle", "tx",
           weight="600", mono=True)
    c.circle(ax, ay, 0.9, THIN, "ln")
    c.text(ax, ay + 5.0, f"가상 정점 — 정점높이 {fmt(G.cone_apex_height_mm, 2)}",
           T_DIM - 0.3, "middle", "tx2")
    c.leader(f.x(G.tank_id_mm / 4 + 20), f.y(top / 2), f.x(300), f.y(top * 0.88),
             f"모선 {fmt(G.cone_slant_length_mm, 2)}")
    c.surface(f.x(150), f.y(top * 0.62), "Ra 0.8", "내면")
    c.view_title(14.0, 180.0, "완성 단면", f.label)

    right_column(
        c, part,
        steps=[
            f"t{fmt(G.cone_thickness_mm)} 판재에 R{fmt(ro, 1)} / R{fmt(ri, 1)} × {fmt(ang, 0)}° 부채꼴을 "
            "먹매김해 절단. 반원이므로 820 × 420 판재 한 장에서 나온다.",
            "콘 롤로 말아 원뿔로 성형. 큰 쪽부터 잡고 작은 쪽으로 좁혀 간다.",
            "세로이음 V70° 개선, 백퍼지 상태로 TIG 전용입 용접 (W5).",
            "내면 용접부 평활 연삭 후 Ra ≤ 0.8 버프.",
            f"큰 쪽 Ø{fmt(G.tank_id_mm)} · 작은 쪽 Ø{fmt(G.cone_outlet_id_mm, 1)} 를 재고, "
            f"모선을 따라 포함각 {fmt(G.cone_included_deg)}° ±0.5° 확인.",
            f"작은 쪽 끝을 t{fmt(G.cone_thickness_mm)} → t2 로 1:4 테이퍼 가공 "
            "(A-03 스터브와 맞대기용).",
            "산세 · 부동태화.",
        ],
        inspect=[
            ("전개 반지름", f"R{fmt(ro, 1)} ±1.0"),
            ("큰 쪽 내경", f"Ø{fmt(G.tank_id_mm)} ±2"),
            ("작은 쪽 내경", f"Ø{fmt(G.cone_outlet_id_mm, 1)} ±1"),
            ("포함각", f"{fmt(G.cone_included_deg)}° ±0.5°"),
            ("세로이음", "PT 100 %"),
            ("내면 조도", "Ra ≤ 0.8"),
        ],
        extra=[f"원본 [D1] 의 H150 + 60° 는 Ø{fmt(G.tank_id_mm)} 에서 Ø38 로 닫히지 "
               f"않는다 (313.5 필요). 채택한 정점높이 {fmt(G.cone_apex_height_mm, 2)} 는 "
               "동체 상단 Z946 · 커버 상면 Z951 · 전용적 89.9 L 를 동시에 만족하는 "
               "유일한 해석이다 (C1).",
               f"이 원뿔 하나가 전용적의 {G.cone_volume_l / G.total_volume_l * 100:.0f} % 를 "
               f"담는다 ({G.cone_volume_l:.2f} L)."],
    )





def sheet_functions() -> list:
    """``sheet_`` 로 시작하는 함수를 **정의 순서대로** 모은다.

    목록을 따로 관리하면 도면을 새로 쓸 때마다 등록을 잊거나, 목록 줄의 위치
    때문에 코드가 잘려 나가는 일이 생긴다. 정의 순서가 곧 도면 순서다.
    """
    fns = [v for k, v in globals().items()
           if k.startswith("sheet_") and callable(v) and k != "sheet_functions"
           and getattr(v, "__code__", None) and v.__code__.co_argcount == 0]
    return sorted(fns, key=lambda f: f.__code__.co_firstlineno)


def build_all() -> None:
    """전 부품도 생성. 제작품 하나도 빠뜨리지 않았는지 함께 확인한다."""
    global TOTAL_SHEETS
    funcs = sheet_functions()
    TOTAL_SHEETS = len(funcs) + 2        # 표지 + 규격품 명세
    SHEETS.clear()
    _COUNTER[0] = 1
    for fn in funcs:
        fn()
    catalogue_sheet()                     # 맨 뒤
    SHEETS.insert(0, cover_sheet())       # 맨 앞
    drawn = {n for n in (sheet_part_no(c) for c in SHEETS) if n}
    missing = [p.no for p in FABRICATED if p.no not in drawn and p.no not in FOLDED]
    if missing and not ALLOW_PARTIAL:
        raise SystemExit(f"부품도가 없는 제작품: {missing}")
    return missing


# ==========================================================================
# 계열 공용 뷰
# ==========================================================================
def disc_plan(c: Canvas, v: View, od: float, bore: float, *, pcd: float = 0.0,
              n: int = 0, hole: float = 0.0, start: float = 0.0,
              extra_circles: tuple[float, ...] = ()) -> None:
    """원판·링의 평면도."""
    cross_centre(c, v, od / 2 + 26)
    c.circle(v.x(0), v.y(0), v.d(od / 2), THICK, "ln")
    if bore:
        c.circle(v.x(0), v.y(0), v.d(bore / 2), THICK, "ln")
    for r in extra_circles:
        c.circle(v.x(0), v.y(0), v.d(r / 2), THIN, "ln", dash="3 1.6")
    if pcd and n:
        bolt_circle(c, v, pcd, n, hole, start)


def disc_section(c: Canvas, v: View, od: float, bore: float, t: float,
                 ident: str = "hD") -> None:
    """원판·링을 반으로 잘라 본 단면 (두 쪽 모두 그린다)."""
    for sign in (1.0, -1.0):
        pts = v.pts([(sign * bore / 2, 0), (sign * od / 2, 0),
                     (sign * od / 2, t), (sign * bore / 2, t)])
        if v.d(t) >= 1.2:
            c.hatch(pts, ident, 45 if sign > 0 else -45)
        else:
            c.fill(pts, "var(--ink)", 0.82)
        c.poly(pts, THICK, "ln", close=True)
    c.centreline(v.x(0), v.y(-8), v.x(0), v.y(t + 8))


def tube_section(c: Canvas, v: View, od: float, wall: float, length: float,
                 z0: float = 0.0, ident: str = "hT") -> None:
    """관재를 세로로 잘라 본 단면."""
    for sign in (1.0, -1.0):
        pts = v.pts([(sign * (od / 2 - wall), z0), (sign * od / 2, z0),
                     (sign * od / 2, z0 + length), (sign * (od / 2 - wall), z0 + length)])
        if v.d(wall) >= 1.2:
            c.hatch(pts, ident, 45 if sign > 0 else -45)
        else:
            c.fill(pts, "var(--ink)", 0.82)
        c.poly(pts, THICK, "ln", close=True)


def flat_plate(c: Canvas, v: View, pts: list[tuple[float, float]],
               holes: tuple[tuple[float, float, float], ...] = ()) -> None:
    """전개 평판 윤곽과 구멍."""
    c.poly(v.pts(pts), THICK, "ln", close=True)
    for hx, hy, hd in holes:
        c.circle(v.x(hx), v.y(hy), v.d(hd / 2), THICK, "ln")
        c.centreline(v.x(hx) - v.d(hd), v.y(hy), v.x(hx) + v.d(hd), v.y(hy))
        c.centreline(v.x(hx), v.y(hy) - v.d(hd), v.x(hx), v.y(hy) + v.d(hd))


# ==========================================================================
# A-03 배출 스터브 · A-04 동체 노즐
# ==========================================================================
def sheet_a03() -> None:
    c, part = part_sheet(
        "A-03", "배출 스터브", '2 in 위생튜브 Ø63.5 × t2.0 + 2" 페룰',
        "2:1", "배출 스터브 부품도 — 튜브와 페룰의 단면, 콘 접합부 테이퍼, 클램프 접합면")

    v = View(112.0, 190.0, 0.5)
    tube_l, fer_l = 40.0, 6.0
    tube_section(c, v, 63.5, 2.0, tube_l, 0.0)
    for sign in (1.0, -1.0):
        pts = v.pts([(sign * 59.5 / 2, tube_l), (sign * 77.5 / 2, tube_l),
                     (sign * 77.5 / 2, tube_l + fer_l), (sign * 59.5 / 2, tube_l + fer_l)])
        c.hatch(pts, "hT", 45 if sign > 0 else -45)
        c.poly(pts, THICK, "ln", close=True)
        # 콘 쪽 1:4 테이퍼
        c.poly(v.pts([(sign * 63.5 / 2, 0), (sign * 63.5 / 2, 4.0),
                      (sign * (63.5 / 2 + 1.0), 8.0)]), THIN, "ln")
    c.centreline(v.x(0), v.y(-14), v.x(0), v.y(tube_l + fer_l + 14))
    c.dim_h(v.x(-63.5 / 2), v.x(63.5 / 2), v.y(-10), "Ø63.5", ext_from=v.y(0))
    c.dim_h(v.x(-59.5 / 2), v.x(59.5 / 2), v.y(-19), "Ø59.5 ID")
    c.dim_h(v.x(-77.5 / 2), v.x(77.5 / 2), v.y(tube_l + fer_l + 10),
            "Ø77.5 클램프", ext_from=v.y(tube_l + fer_l))
    c.dim_v(v.y(0), v.y(tube_l), v.x(77.5 / 2) + 10.0, f"{fmt(tube_l)} ±0.5", left=False)
    c.dim_v(v.y(tube_l), v.y(tube_l + fer_l), v.x(77.5 / 2) + 22.0, fmt(fer_l), left=False)
    c.leader(v.x(-(63.5 / 2 + 0.5)), v.y(5.0), 60.0, v.y(-18.0),
             "t3 → t2 1:4 테이퍼", anchor="end", lines=("콘(A-02)과 맞대기용",))
    c.surface(14.0, 122.0, "Ra 0.8", "내면")
    c.fcf(14.0, 104.0, "perp", "0.3", "A")
    c.datum(v.x(72), v.y(tube_l + fer_l + 8), "A", v.x(77.5 / 2), v.y(tube_l + fer_l))
    c.view_title(14.0, 30.0, "단면", v.label)
    c.text(14.0, 40.0, "콘 A-02 의 작은 쪽에 맞대기 전용입 용접 (W3)", T_DIM - 0.2, "start", "tx2")

    e = View(60.0, 258.0, 0.5)
    cross_centre(c, e, 52)
    c.circle(e.x(0), e.y(0), e.d(77.5 / 2), THICK, "ln")
    c.circle(e.x(0), e.y(0), e.d(63.5 / 2), THICK, "ln")
    c.circle(e.x(0), e.y(0), e.d(59.5 / 2), THICK, "ln")
    c.view_title(14.0, 210.0, "클램프 면", e.label)
    c.text(14.0, 282.0, "페룰은 위생 규격품을 사 와 튜브에 맞대기 용접한다.",
           T_DIM - 0.2, "start", "tx2")

    right_column(
        c, part,
        steps=[
            "Ø63.5 × t2.0 위생튜브를 L40 으로 직각 절단. 버 제거.",
            '2" 위생 페룰(Ø77.5 클램프면)을 튜브 한쪽에 맞대기 전용입 용접.',
            "반대쪽 끝 바깥면을 t3 → t2 로 1:4 테이퍼 가공 — 콘 A-02 와 두께를 맞춘다.",
            "내면 용접부 평활 연삭 후 Ra ≤ 0.8 버프.",
            "클램프 면의 축 직각도를 다이얼로 확인 (0.3 이내).",
            "산세 · 부동태화.",
        ],
        inspect=[
            ("튜브 길이", "40 ±0.5"),
            ("내경", "Ø59.5 ±0.2"),
            ("클램프 면 직각도", "0.3 / Ø77.5"),
            ("용접", "PT 100 % · 내면 평활"),
            ("내면 조도", "Ra ≤ 0.8"),
        ],
        extra=['원본은 Ø50.8 (1.5 in) 이었다. 작은 쪽으로 붙이면 연구문서가 요구한 '
               '1.5 in / 2 in 배출시험을 한 대에서 둘 다 돌릴 수 없어 2 in 으로 키웠다 (C3). '
               '기본 조건은 2→1½ 리듀싱 클램프로 조인다.'],
    )


def sheet_a04() -> None:
    c, part = part_sheet(
        "A-04", "동체 노즐", "위생 Tri-clamp 9 개소 · 호칭별 치수표",
        "1:1", "동체 노즐 부품도 — 공통 형상과 호칭별 치수표, set-through 관통 용접")

    v = View(110.0, 150.0, 1.0)
    od, wall, proj, fer = 38.1, 1.65, 75.0, 6.0
    shell_t = G.shell_thickness_mm
    # 동체 벽
    pts = v.pts([(-shell_t, -46), (0, -46), (0, 46), (-shell_t, 46)])
    c.hatch(pts, "hS", 45)
    c.poly(pts, THICK, "ln", close=True)
    c.text(v.x(-shell_t) - 4.0, v.y(0), "동체 t3", T_DIM - 0.3, "end", "tx2")
    for sign in (1.0, -1.0):
        p2 = v.pts([(-shell_t, sign * od / 2), (proj, sign * od / 2),
                    (proj, sign * (od / 2 - wall)), (-shell_t, sign * (od / 2 - wall))])
        c.hatch(p2, "hN", -45 if sign > 0 else 45)
        c.poly(p2, THICK, "ln", close=True)
        p3 = v.pts([(proj, sign * (od / 2 - wall)), (proj, sign * 50.5 / 2),
                    (proj + fer, sign * 50.5 / 2), (proj + fer, sign * (od / 2 - wall))])
        c.hatch(p3, "hN", -45 if sign > 0 else 45)
        c.poly(p3, THICK, "ln", close=True)
        c.poly(v.pts([(0, sign * od / 2), (3.4, sign * (od / 2 + 3.4)), (0, sign * (od / 2 + 3.4))]),
               THIN, "ln", close=True, fill="var(--ink)")
        c.poly(v.pts([(-shell_t, sign * (od / 2 - wall)), (-shell_t - 2.2, sign * (od / 2 - wall)),
                      (-shell_t, sign * (od / 2 - wall) - sign * 2.2)]),
               THIN, "ln", close=True, fill="var(--ink)")
    c.centreline(v.x(-shell_t - 12), v.y(0), v.x(proj + fer + 12), v.y(0))
    c.dim_h(v.x(0), v.x(proj), v.y(-52), "돌출 75 ±1", ext_from=v.y(-od / 2))
    c.dim_h(v.x(proj), v.x(proj + fer), v.y(-62), fmt(fer))
    c.dim_v(v.y(-od / 2), v.y(od / 2), v.x(proj + fer) + 12.0, "Ø d1", left=False)
    c.leader(v.x(3.4), v.y(od / 2 + 2), v.x(40), v.y(-66), "바깥 필릿 a2 연속")
    c.leader(v.x(-shell_t - 1.5), v.y(-od / 2 + 1), v.x(-24), v.y(56.0),
             "안쪽 용접 후 평활 연삭", anchor="end")
    c.view_title(14.0, 30.0, "공통 형상 (N2 기준)", v.label)
    c.text(14.0, 40.0, "관을 동체 안쪽면까지 넣고 양면 용접한다 (set-through)",
           T_DIM - 0.2, "start", "tx2")

    rows = [["노즐", "호칭", "튜브 Ø d1 × t", "클램프 Ø", "구멍 Ø", "수량"]]
    seen: dict[float, list[str]] = {}
    for n in NOZZLES:
        seen.setdefault(n.tube_od_mm, []).append(n.tag)
    sizes = {25.4: ('1" TC', 1.65, 50.5), 38.1: ('1½" TC', 1.65, 64.0),
             12.7: ('½" TC', 1.65, 25.0), 104.0: ('Ø100 TC', 2.0, 119.0)}
    for od_mm, tags in sorted(seen.items()):
        nom, t, cl = sizes[od_mm]
        rows.append([", ".join(tags), nom, f"Ø{od_mm:.1f} × t{t}", f"Ø{cl:.1f}",
                     f"Ø{od_mm + 4:.1f}", str(len(tags))])
    c.view_title(14.0, 210.0, "호칭별 치수")
    c.table(14.0, 214.0, [38.0, 26.0, 40.0, 26.0, 26.0, 18.0], rows, row_h=5.4,
            size=T_DIM - 0.2, aligns=["start", "start", "start", "middle", "middle", "middle"])
    c.text(14.0, 214.0 + len(rows) * 5.4 + 5.0,
           "표고·방위는 MP50-A3 노즐표. 구멍은 동체 롤링·용접 뒤에 뚫는다.",
           T_DIM - 0.2, "start", "tx2")

    right_column(
        c, part,
        steps=[
            "호칭별 위생튜브를 돌출 75 + 동체 두께 3 만큼 잘라 버 제거.",
            "동체 구멍에 관을 **안쪽면까지** 넣는다 (set-through). set-on 은 안쪽에 "
            "링 모양 크레비스를 남겨 배치마다 분말이 낀다.",
            "바깥 필릿 a2 연속 + 안쪽 전둘레 용접 (W6).",
            "안쪽 용접부를 동체 내면과 같은 면이 되도록 평활 연삭.",
            "바깥 끝에 호칭별 위생 페룰을 맞대기 용접.",
            "클램프 면의 관축 직각도 확인 후 산세 · 부동태화.",
        ],
        inspect=[
            ("돌출", "75 ±1 (동체 외면 기준)"),
            ("관통 용접", "PT · 내면 평활 · 크레비스 없을 것"),
            ("클램프 면 직각도", "0.3"),
            ("내면 조도", "Ra ≤ 0.8"),
        ],
        extra=["돌출 75 는 클램프 나비너트를 한 바퀴 돌릴 수 있는 최소치에서 정했다."],
    )



# ==========================================================================
# 원판 · 링 계열 — 평면 + 단면이 같은 틀이라 한 함수로 묶는다
# ==========================================================================
def disc_part_sheet(no: str, title: str, subtitle: str, aria: str, *,
                    od: float, bore: float, t: float,
                    plan_scale: float, sec_scale: float,
                    pcd: float = 0.0, n: int = 0, hole: float = 0.0, start: float = 0.0,
                    rings: tuple[tuple[float, int, float, float, str], ...] = (),
                    notes: tuple[tuple[float, float, str, tuple[str, ...]], ...] = (),
                    gdt: tuple[tuple[str, str, str, str], ...] = (),
                    surface_note: tuple[str, str] | None = None,
                    detail=None, steps: list[str] = (), inspect=(), extra=()) -> Canvas:
    """원판·링 부품도 한 장.

    평면(구멍 배치)과 단면(두께)만으로 형상이 다 읽히는 부품들 — 플랜지, 지지링,
    커버판, 허브, 타공판 — 이 한 틀을 쓴다. 지시선은 모두 오른쪽으로 빼서 세로로
    쌓는다. 원 둘레를 따라 아무 데나 붙이면 장마다 다른 자리에 글자가 생긴다.
    """
    c, part = part_sheet(no, title, subtitle, f"1:{plan_scale:g}", aria)
    v = View(82.0, 104.0, plan_scale)
    disc_plan(c, v, od, bore, pcd=pcd, n=n, hole=hole, start=start)
    for rp, rn, rd, rs, lab in rings:
        bolt_circle(c, v, rp, rn, rd, rs)
    c.dim_h(v.x(-od / 2), v.x(od / 2), v.y(-od / 2 - 16), f"Ø{fmt(od)}")
    if bore:
        c.dim_h(v.x(-bore / 2), v.x(bore / 2), v.y(od / 2 + 12), f"Ø{fmt(bore)}")
    if pcd and n:
        c.dim_h(v.x(-pcd / 2), v.x(pcd / 2), v.y(-od / 2 - 27),
                f"PCD Ø{fmt(pcd)} · {n}-Ø{fmt(hole)}")
    # 지시선 — 오른쪽에 세로로 쌓는다
    lx = v.x(od / 2) + 18.0
    ly = v.y(od / 2) + 4.0
    items = [(rp, rs, lab, ()) for rp, rn, rd, rs, lab in rings] + list(notes)
    for rp, ang, lab, lines in items:
        a = math.radians(ang)
        c.leader(v.x(rp / 2 * math.cos(a)), v.y(rp / 2 * math.sin(a)), lx, ly, lab, lines=lines)
        ly += 5.0 + 4.0 * len(lines)
    c.view_title(14.0, 30.0, "평면", v.label)

    sv = View(82.0, 228.0, sec_scale)
    disc_section(c, sv, od, bore, t)
    c.dim_v(sv.y(0), sv.y(t), sv.x(od / 2) + 10.0, f"t{fmt(t)}", left=False)
    c.dim_h(sv.x(-od / 2), sv.x(od / 2), sv.y(0) + 13.0, f"Ø{fmt(od)}", ext_from=sv.y(0))
    c.view_title(14.0, 196.0, "단면", sv.label)
    gy = 250.0
    for kind, tol, dat, note in gdt:
        c.fcf(14.0, gy, kind, tol, dat)
        c.text(40.0, gy + 3.6, note, T_DIM - 0.3, "start", "tx2")
        gy += 8.6
    if surface_note:
        c.surface(14.0, gy + 4.0, surface_note[0], surface_note[1])
    if detail is not None:
        detail(c)
    right_column(c, part, steps=list(steps), inspect=list(inspect),
                 extra=list(extra), also=SHARED.get(no, ()))
    return c


def simple_part_sheet(no: str, title: str, subtitle: str, scale_txt: str, aria: str,
                      views, steps: list[str], inspect, extra=()) -> Canvas:
    """왼쪽 기둥을 직접 그리는 부품도 — 원판 틀에 안 맞는 형상용."""
    c, part = part_sheet(no, title, subtitle, scale_txt, aria)
    views(c)
    right_column(c, part, steps=list(steps), inspect=list(inspect),
                 extra=list(extra), also=SHARED.get(no, ()))
    return c


def sheet_a05() -> None:
    def groove(c: Canvas) -> None:
        d = View(202.0, 232.0, 0.36)
        c.view_title(166.0, 196.0, "가스켓 홈 상세", "2.8:1")
        pts = d.pts([(-9, 0), (-2.5, 0), (-2.5, -3), (2.5, -3), (2.5, 0), (9, 0),
                     (9, 10), (-9, 10)])
        c.hatch(pts, "hG", 45)
        c.poly(pts, THICK, "ln", close=True)
        c.dim_h(d.x(-2.5), d.x(2.5), d.y(-8.0), "5.0 +0.2", ext_from=d.y(-3))
        c.dim_v(d.y(-3), d.y(0), d.x(11.0), "3.0", left=False)
        c.circle(d.x(0), d.y(-0.5), d.d(2.5), THIN, "ln", dash="2 1.4")
        c.leader(d.x(0), d.y(-1.5), d.x(-13.0), d.y(-14.0), "EPDM 코드 Ø5 (B-05)",
                 anchor="end", lines=("커버는 금속면에 직접 앉는다",))

    disc_part_sheet(
        "A-05", "상단 플랜지", f"OD Ø{G.top_flange_od_mm:.0f} × ID Ø{G.shell_od_mm:.0f} × t{G.top_flange_thickness_mm:.0f} · 가스켓 홈",
        "상단 플랜지 부품도 — 볼트 PCD, 가스켓 홈 단면, 밀봉면 평면도 공차",
        od=G.top_flange_od_mm, bore=G.shell_od_mm, t=G.top_flange_thickness_mm,
        plan_scale=4.0, sec_scale=4.0,
        pcd=G.top_flange_pcd_mm, n=G.top_flange_bolts, hole=14.0, start=15.0,
        notes=((430.0, 200.0, "가스켓 홈 Ø430", ("W5 × D3 · 선삭",)),),
        gdt=(("flat", "0.3", "", "가스켓 면 — 커버와 금속 접촉"),
             ("round", "1.0", "", "동체 끼움 보어")),
        surface_note=("Ra 1.6", "가스켓 면"),
        detail=groove,
        steps=[
            "t10 판재를 Ø500 원판으로 절단 (레이저 또는 플라즈마).",
            f"선반에 물려 바깥 Ø{G.top_flange_od_mm:.0f}, 안쪽 Ø{G.shell_od_mm:.0f} 를 깎는다. "
            "안쪽은 동체 바깥면에 끼워지므로 헐거운 쪽으로 (+0.5/0).",
            "가스켓 면을 평면도 0.3 안에 들게 면삭하고 Ra 1.6 으로 마무리.",
            "같은 물림에서 가스켓 홈 Ø430 · 폭 5.0 +0.2 · 깊이 3.0 을 선삭.",
            f"PCD Ø{G.top_flange_pcd_mm:.0f} 에 {G.top_flange_bolts}-Ø14 드릴 (지그 사용, 분할 오차 ±0.3).",
            "동체 바깥면에 끼워 필릿 a3 양면 연속 용접 (W1). 용접 변형 후 가스켓 면 평면도 재확인.",
            "산세 · 부동태화.",
        ],
        inspect=[("바깥·안쪽 지름", "Ø480 ±0.5 / Ø406 +0.5 / 0"),
                 ("가스켓 면 평면도", "0.3 (용접 후)"),
                 ("가스켓 홈", "폭 5.0 +0.2 · 깊이 3.0 ±0.1"),
                 ("볼트 분할", "PCD Ø450 · 각 구멍 ±0.3"),
                 ("가스켓 면 조도", "Ra ≤ 1.6")],
        extra=["가스켓을 플랜지 면 홈에 넣어 커버가 금속면에 직접 앉는다. 그래야 "
               f"[R] 의 동체 상단 Z{G.shell_top_z:.0f} · 커버 상면 Z{G.cover_top_z:.0f} 스택이 "
               "가스켓 두께에 밀리지 않는다 (C8).",
               "용접은 가스켓 면을 다듬은 **뒤**에 한다 — 순서를 바꾸면 용접 변형이 "
               "평면도를 먹는다."],
    )


def sheet_a06() -> None:
    disc_part_sheet(
        "A-06", "지지링", f"OD Ø{G.support_ring_od_mm:.0f} × ID Ø{G.shell_od_mm:.0f} × t{G.support_ring_thickness_mm:.0f} · 프레임 안착면",
        "지지링 부품도 — 프레임 볼트 구멍 배치와 안착면 평면도",
        od=G.support_ring_od_mm, bore=G.shell_od_mm, t=G.support_ring_thickness_mm,
        plan_scale=4.0, sec_scale=4.0,
        rings=((424.0, 4, 14.0, 39.8, "M12 볼트 4 개소 · X=±180 Y=±150"),),
        gdt=(("flat", "0.5", "", "프레임 안착면 (아래쪽)"),),
        steps=[
            "t8 판재를 Ø500 원판으로 절단.",
            f"선반에서 바깥 Ø{G.support_ring_od_mm:.0f}, 안쪽 Ø{G.shell_od_mm:.0f} 가공. "
            "안쪽은 동체 바깥면 끼움 (+0.5/0).",
            "아래 안착면을 평면도 0.5 안에 들게 면삭 — 프레임 크로스레일에 닿는 면이다.",
            "M12 볼트 구멍 4 개소를 X=±180, Y=±150 에 드릴 (Ø14). 프레임 H-03 과 "
            "같은 지그로 뚫어 어긋나지 않게 한다.",
            f"동체 Z{G.support_ring_z:.0f} 에 끼워 필릿 a4 양면 연속 용접 (W7). "
            f"동체/콘 용접선(Z{G.shell_bottom_z:.0f})에서 {G.support_ring_z - G.shell_bottom_z:.0f} mm 띄운다.",
            "산세 · 부동태화.",
        ],
        inspect=[("바깥·안쪽 지름", "Ø480 ±0.5 / Ø406 +0.5 / 0"),
                 ("안착면 평면도", "0.5"),
                 ("볼트 구멍", "X=±180 · Y=±150 각 ±0.5"),
                 ("용접", "육안 · 언더컷 없을 것"),
                 ("설치 표고", f"Z{G.support_ring_z:.0f} ±1")],
        extra=[f"지지링은 동체/콘 맞대기 용접선 바로 위가 아니라 {G.support_ring_z - G.shell_bottom_z:.0f} mm "
               "위에 붙인다. 용접선에 하중을 얹지 않기 위해서다.",
               "볼트 4 개소가 크로스레일(H-03) Y=±150 과 맞아야 하므로, 프레임과 "
               "같은 지그로 뚫는다."],
    )



# ==========================================================================
# A-07 (+B-03) 거싯 · A-08 양중 러그
# ==========================================================================
def sheet_a07() -> None:
    def views(c: Canvas) -> None:
        specs = (("A-07", "보강 거싯", 100.0, 100.0, 5.0, 4, "지지링 하면 ↔ 콘 외면", 40.0),
                 ("B-03", "허브 거싯", 80.0, 60.0, 5.0, 4, "커버 허브 ↔ 커버판", 155.0))
        for no, nm, w, h, t, qty, where, ox in specs:
            v = View(ox, 128.0, 1.0)
            c.poly(v.pts([(0, 0), (w, 0), (0, h)]), THICK, "ln", close=True)
            c.arc(v.x(0) + v.d(9), v.y(0) + v.d(9), v.d(9), 90, 180, THIN, "ln")
            c.dim_h(v.x(0), v.x(w), v.y(0) + 9.0, fmt(w), ext_from=v.y(0))
            c.dim_v(v.y(0), v.y(h), v.x(0) - 9.0, fmt(h), ext_from=v.x(0))
            c.leader(v.x(w * .38), v.y(h * .38), v.x(w * .62), v.y(h * .86),
                     f"{no} · {qty} 개", lines=(where,))
            c.text(v.x(0), v.y(-14), f"빗변 {math.hypot(w, h):.1f} · 모서리 R2",
                   T_DIM - 0.2, "start", "tx2")
            plate_edge(c, View(ox, 214.0, 1.0), 0, w, 0, -t, "hE")
            c.dim_v(View(ox, 214.0, 1.0).y(0), View(ox, 214.0, 1.0).y(t),
                    View(ox, 214.0, 1.0).x(w) + 8.0, f"t{fmt(t)}", left=False)
        c.view_title(14.0, 38.0, "전개 평판", "1:1")
        c.view_title(14.0, 190.0, "두께", "1:1")
        c.text(14.0, 240.0, "두 부품 모두 직각 이등변이 아니다 — 빗변 길이를 확인하고 자른다.",
               T_DIM - 0.2, "start", "tx2")
        c.text(14.0, 246.0, "모서리는 R2 로 둥글린다. 날선 모서리는 부동태 피막이 얇게 "
               "붙어 염수에서 먼저 뜯긴다.", T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "A-07", "거싯 2 종", "A-07 보강 거싯 · B-03 허브 거싯 — 소물 합본", "1:1",
        "거싯 부품도 — 두 종류의 전개 평판과 두께, 모서리 처리",
        views,
        steps=["t5 판재에서 직각 삼각형으로 절단. A-07 은 100 × 100, B-03 은 80 × 60.",
               "모서리 전부 R2 로 둥글리고 버 제거.",
               "A-07: 지지링(A-06) 하면과 콘(A-02) 외면 사이에 90° 등분 4 개소 필릿 용접.",
               "B-03: 커버 허브(B-02) 옆면과 커버판(B-01) 윗면 사이에 90° 등분 4 개소. "
               "허브 볼트 PCD 가 확정되기 전에는 붙이지 않는다 (HOLD).",
               "산세 · 부동태화."],
        inspect=[("외형", "±1.0"), ("두께", "t5 (소재 그대로)"),
                 ("모서리", "R2 · 날선 곳 없을 것"), ("용접", "필릿 a4 연속 · 육안")],
        extra=["B-03 은 구동부 벤더 GA 가 나오기 전에는 붙일 수 없다 — 허브 보어와 "
               "볼트 PCD 가 정해져야 거싯 자리가 정해진다."],
    )


def sheet_a08() -> None:
    def views(c: Canvas) -> None:
        w, h, t, hole = 70.0, 50.0, 6.0, 20.0
        v = View(44.0, 128.0, 1.0)
        c.poly(v.pts([(0, 0), (w, 0), (w, h - 18), (w - 18, h), (0, h)]), THICK, "ln", close=True)
        c.circle(v.x(w - 26), v.y(h - 24), v.d(hole / 2), THICK, "ln")
        cross_centre(c, View(v.x(w - 26) - v.ox * 0 + 0, 0, 1), 0) if False else None
        c.centreline(v.x(w - 26) - v.d(18), v.y(h - 24), v.x(w - 26) + v.d(18), v.y(h - 24))
        c.centreline(v.x(w - 26), v.y(h - 24) - v.d(18), v.x(w - 26), v.y(h - 24) + v.d(18))
        c.dim_h(v.x(0), v.x(w), v.y(0) - 10.0, fmt(w), ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(h), v.x(0) - 9.0, fmt(h), ext_from=v.x(0))
        c.dim_h(v.x(0), v.x(w - 26), v.y(h) + 10.0, "44", ext_from=v.y(h - 24))
        c.dim_v(v.y(0), v.y(h - 24), v.x(w) + 9.0, "26", left=False)
        c.leader(v.x(w - 26 + hole / 2), v.y(h - 24), v.x(w + 26), v.y(h * .2),
                 f"Ø{fmt(hole)}", lines=("샤클 구멍 · 버 제거",))
        c.view_title(14.0, 30.0, "전개 평판", v.label)
        e = View(44.0, 206.0, 1.0)
        plate_edge(c, e, 0, w, 0, -t, "hL")
        c.dim_v(e.y(0), e.y(t), e.x(w) + 8.0, f"t{fmt(t)}", left=False)
        c.view_title(14.0, 182.0, "두께", e.label)
        c.text(14.0, 230.0, f"3 개소 120° 등분 · Z{fmt(900)} · 동체 바깥면에 필릿 a5 연속 용접 (W8).",
               T_DIM - 0.2, "start", "tx2")
        c.text(14.0, 236.0, "공차 총질량 기준으로 계산했다 — 탱크 아세이 "
               f"{BY_CODE['A'].total_kg:.0f} kg 을 3 점으로 든다.", T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                "양중 시 러그 한 개에 걸리는 하중은 3 점 균등이 아니라 2 점 지지로 봐야 "
                "한다. 슬링 각도 60° 에서 러그당 약 " +
                f"{BY_CODE['A'].total_kg / 2 / math.cos(math.radians(30)):.0f} kgf 다.", 74)):
            c.text(14.0, 246.0 + i * 4.2, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "A-08", "양중 러그", "t6 · Ø20 샤클 구멍 · 3 개소 120° 등분", "1:1",
        "양중 러그 부품도 — 외형, 샤클 구멍 위치, 두께, 용접",
        views,
        steps=["t6 판재에서 70 × 50 외형으로 절단. 모서리 한 곳은 18 × 18 모따기.",
               "Ø20 샤클 구멍을 드릴 후 양면 버 제거. 구멍 둘레 C1 모따기.",
               "모서리 R2.",
               "동체 Z900 에 120° 등분 3 개소, 필릿 a5 연속 용접 (W8).",
               "용접 후 PT. 러그는 사람 머리 위로 물건을 드는 부품이므로 육안으로 끝내지 않는다.",
               "산세 · 부동태화."],
        inspect=[("외형", "±1.0"), ("구멍 위치", "±0.5"),
                 ("용접", "PT 100 % · a5 연속"), ("모서리·구멍", "버 없을 것")],
    )


# ==========================================================================
# B 커버
# ==========================================================================
def sheet_b01() -> None:
    disc_part_sheet(
        "B-01", "커버판", f"Ø{G.top_flange_od_mm:.0f} × t{G.cover_thickness_mm:.0f} · 중앙 보어 Ø60",
        "커버판 부품도 — 볼트 PCD, 계측 노즐과 조절봉 구멍, 중앙 보어 HOLD",
        od=G.top_flange_od_mm, bore=60.0, t=G.cover_thickness_mm,
        plan_scale=4.0, sec_scale=4.0,
        pcd=G.top_flange_pcd_mm, n=G.top_flange_bolts, hole=14.0, start=15.0,
        rings=((330.0, 3, 16.7, 60.0, "계측 노즐 3-Ø16.7 (B2·B3·B4)"),
               (330.0, 3, 20.0, 0.0, "조절봉 부싱 3-Ø20 (B-07)")),
        notes=((60.0, 45.0, "중앙 보어 Ø60 — HOLD", ("씰 슬리브 확정 후 가공",)),),
        gdt=(("flat", "0.5", "", "가스켓 접촉면 (아래쪽)"),),
        steps=[
            "t5 판재를 Ø500 원판으로 절단.",
            f"선반에서 바깥 Ø{G.top_flange_od_mm:.0f} 가공, 아래면을 평면도 0.5 안에 들게 면삭.",
            f"PCD Ø{G.top_flange_pcd_mm:.0f} 에 {G.top_flange_bolts}-Ø14 드릴 — 플랜지(A-05)와 "
            "같은 지그를 써 두 부품의 구멍이 맞게 한다.",
            "PCD Ø330 에 계측 노즐 3-Ø16.7 (θ60/180/300) 과 조절봉 부싱 3-Ø20 (θ0/120/240) 드릴.",
            "**중앙 보어 Ø60 과 허브 볼트 구멍은 뚫지 않는다** — 구동부 벤더 GA 승인 "
            "전까지 HOLD (B1 인터페이스).",
            "버 제거 후 산세 · 부동태화.",
        ],
        inspect=[("바깥 지름", "Ø480 ±0.5"), ("평면도", "0.5 (아래면)"),
                 ("볼트 분할", "PCD Ø450 · 각 ±0.3 · A-05 와 맞물릴 것"),
                 ("PCD330 구멍", "각 ±0.5"), ("두께", "t5 (소재 그대로)")],
        extra=["t5 평판이 Ø400 개구를 덮지만 하중은 대기압이 아니라 구동부 자중이다. "
               "중앙 허브(B-02)와 거싯(B-03)이 그 하중을 받으므로 커버판 단독으로는 "
               "강도를 따지지 않는다.",
               "커버 볼트 구멍은 플랜지와 **같은 지그**로 뚫는다. 따로 뚫으면 분할 "
               "오차가 겹쳐 12 개 중 몇 개가 안 들어간다."],
    )


def sheet_b02() -> None:
    disc_part_sheet(
        "B-02", "중앙 보강 허브", f"Ø{G.cover_hub_od_mm:.0f} × t{G.cover_hub_thickness_mm:.0f} · 보어 Ø60 — HOLD",
        "중앙 보강 허브 부품도 — 외형과 두께, 벤더 GA 전 가공 금지 구역",
        od=G.cover_hub_od_mm, bore=60.0, t=G.cover_hub_thickness_mm,
        plan_scale=2.0, sec_scale=2.0,
        notes=((150.0, 45.0, "볼트 PCD — HOLD", ("감속기 마운팅 치수 확정 후",)),
               (60.0, 225.0, "보어 Ø60 — HOLD", ("씰 gland·슬리브 외경 확정 후",))),
        gdt=(("flat", "0.2", "", "감속기 안착면 (위쪽)"),
             ("perp", "0.2", "A", "보어 축 ↔ 안착면")),
        steps=[
            "t10 판재를 Ø240 원판으로 절단.",
            f"선반에서 바깥 Ø{G.cover_hub_od_mm:.0f} 가공, 위 안착면을 평면도 0.2 로 면삭.",
            "**여기서 멈춘다.** 보어와 볼트 구멍은 벤더 GA 승인 후에 가공한다.",
            "— GA 승인 후 — 씰 슬리브 외경에 맞춰 보어 가공 (H7).",
            "— GA 승인 후 — 감속기 마운팅 PCD 에 맞춰 볼트 구멍 가공.",
            "커버판(B-01) 위에 올려 전둘레 필릿 a4 용접, 거싯(B-03) 4 개소 추가.",
            "산세 · 부동태화.",
        ],
        inspect=[("바깥 지름", "Ø220 ±0.5"), ("안착면 평면도", "0.2"),
                 ("보어", "GA 확정 후 H7"), ("보어 직각도", "0.2 / 안착면"),
                 ("볼트 분할", "GA 확정 후 ±0.2")],
        extra=["**벤더 GA 승인 전 중앙을 가공하지 않는다.** 씰 gland 치수와 감속기 "
               "마운팅 PCD 를 모르는 채로 뚫으면 이 부품을 다시 만들어야 한다 "
               "([R] §3 CRITICAL HOLD).",
               "이 부품이 구동부 자중과 축 진동을 커버판으로 퍼뜨린다. 안착면 평면도 "
               "0.2 는 감속기 발이 뜨지 않게 하기 위한 값이다."],
    )


# ==========================================================================
# B-04 커버 노즐 · B-07 부싱
# ==========================================================================
def sheet_b04() -> None:
    def views(c: Canvas) -> None:
        v = View(96.0, 150.0, 0.5)
        od, wall, proj, fer = 12.7, 1.65, 44.0, 6.0
        t = G.cover_thickness_mm
        pts = v.pts([(-42, -t), (42, -t), (42, 0), (-42, 0)])
        c.hatch(pts, "hC", 45)
        c.poly(pts, THICK, "ln", close=True)
        c.text(v.x(-42) + 2.0, v.y(-t / 2) + 7.0, "커버판 t5", T_DIM - 0.3, "start", "tx2")
        for sign in (1.0, -1.0):
            p2 = v.pts([(sign * od / 2, -t), (sign * (od / 2 - wall), -t),
                        (sign * (od / 2 - wall), proj), (sign * od / 2, proj)])
            c.hatch(p2, "hN", -45 if sign > 0 else 45)
            c.poly(p2, THICK, "ln", close=True)
            p3 = v.pts([(sign * (od / 2 - wall), proj), (sign * 25.0 / 2, proj),
                        (sign * 25.0 / 2, proj + fer), (sign * (od / 2 - wall), proj + fer)])
            c.hatch(p3, "hN", -45 if sign > 0 else 45)
            c.poly(p3, THICK, "ln", close=True)
            c.poly(v.pts([(sign * od / 2, 0), (sign * (od / 2 + 2.6), 0),
                          (sign * od / 2, 2.6)]), THIN, "ln", close=True, fill="var(--ink)")
        c.centreline(v.x(0), v.y(-t - 12), v.x(0), v.y(proj + fer + 12))
        c.dim_v(v.y(0), v.y(proj), v.x(25.0 / 2) + 12.0, f"{fmt(proj)} ±1", left=False)
        c.dim_h(v.x(-od / 2), v.x(od / 2), v.y(-t - 12), f"Ø{fmt(od, 1)}", ext_from=v.y(-t))
        c.dim_h(v.x(-25.0 / 2), v.x(25.0 / 2), v.y(proj + fer + 10), "Ø25.0 클램프",
                ext_from=v.y(proj + fer))
        c.leader(v.x(od / 2 + 1.3), v.y(1.3), v.x(56), v.y(-24.0), "바깥 필릿 a2")
        c.view_title(14.0, 30.0, "단면 (공통)", v.label)

        rows = [["번호", "θ", "삽입 깊이", "용도"]]
        for n in COVER_NOZZLES:
            if n.tag == "B1":
                continue
            depth = {"B2": "425 (선단 Z526)", "B3": "225 (선단 Z726)", "B4": "-"}[n.tag]
            rows.append([n.tag, f"{n.theta_deg:.0f}°", depth, n.service])
        c.view_title(14.0, 214.0, "노즐별 배치")
        c.table(14.0, 218.0, [20.0, 20.0, 48.0, 60.0], rows, row_h=5.4, size=T_DIM - 0.2,
                aligns=["middle", "middle", "start", "start"])
        c.text(14.0, 218.0 + len(rows) * 5.4 + 5.0,
               "PCD Ø330 · 커버판(B-01)의 3-Ø16.7 구멍에 끼운다.", T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "B-04", "커버 노즐", '½" TC × 3 · PCD Ø330', "2:1",
        "커버 노즐 부품도 — 공통 단면과 노즐별 배치, 삽입 깊이",
        views,
        steps=["Ø12.7 × t1.65 위생튜브를 돌출 44 + 커버 두께 5 만큼 절단.",
               "커버판 구멍에 커버 아래면과 같은 높이까지 넣고 양면 용접.",
               "아래쪽 용접부 평활 연삭 — 세척수가 고이지 않게 한다.",
               '바깥 끝에 ½" 위생 페룰(Ø25.0 클램프면) 맞대기 용접.',
               "산세 · 부동태화."],
        inspect=[("돌출", "44 ±1"), ("용접", "육안 + PT"), ("클램프 면 직각도", "0.3")],
        extra=["B4 는 배기구다. 급기 10 L/min 이 들어가는데 나갈 데가 없으면 용기가 "
               "가압된다 — 막으면 안 된다.",
               "센서 삽입 깊이는 선단이 액중에 잠기도록 잡았다 — B2 전도도는 액체 "
               "중간(Z526), B3 온도는 액면 바로 아래(Z726)."],
    )


def sheet_b07() -> None:
    def views(c: Canvas) -> None:
        v = View(80.0, 150.0, 0.34)
        od, bore, ln = 20.0, 8.5, 30.0
        for sign in (1.0, -1.0):
            pts = v.pts([(sign * bore / 2, 0), (sign * od / 2, 0),
                         (sign * od / 2, ln), (sign * bore / 2, ln)])
            c.hatch(pts, "hB7", 45 if sign > 0 else -45)
            c.poly(pts, THICK, "ln", close=True)
            c.poly(v.pts([(sign * bore / 2, 10), (sign * (bore / 2 + 2.2), 10),
                          (sign * (bore / 2 + 2.2), 13), (sign * bore / 2, 13)]),
                   THIN, "ln", close=True, fill="var(--paper)")
        c.centreline(v.x(0), v.y(-10), v.x(0), v.y(ln + 10))
        c.dim_h(v.x(-od / 2), v.x(od / 2), v.y(-8), f"Ø{fmt(od)}", ext_from=v.y(0))
        c.dim_h(v.x(-bore / 2), v.x(bore / 2), v.y(ln + 9), f"Ø{fmt(bore, 1)} (M8 통과)",
                ext_from=v.y(ln))
        c.dim_v(v.y(0), v.y(ln), v.x(od / 2) + 10.0, fmt(ln), left=False)
        c.dim_v(v.y(10), v.y(13), v.x(od / 2) + 22.0, "3.0", left=False)
        c.leader(v.x(bore / 2 + 1.1), v.y(11.5), v.x(66), v.y(-6.0), "O-링 홈 W3 × D2.2",
                 lines=("EPDM 코드 Ø3 · 조절봉 누설 차단",))
        c.view_title(14.0, 30.0, "단면", v.label)
        e = View(80.0, 250.0, 0.34)
        cross_centre(c, e, 16)
        c.circle(e.x(0), e.y(0), e.d(od / 2), THICK, "ln")
        c.circle(e.x(0), e.y(0), e.d(bore / 2), THICK, "ln")
        c.view_title(14.0, 206.0, "평면", e.label)
        c.text(14.0, 276.0, "커버판(B-01)의 Ø20 구멍에 끼워 위아래 필릿 용접 · 3 개소 (θ0/120/240).",
               T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "B-07", "스키머 조절봉 부싱", "Ø20 × L30 · M8 통과 · O-링 홈", "3:1",
        "조절봉 부싱 부품도 — 단면과 평면, O-링 홈",
        views,
        steps=["Ø20 환봉을 L30 으로 절단.",
               "Ø8.5 관통 구멍 드릴 — M8 조절봉이 헐겁게 지나가야 한다.",
               "안쪽에 O-링 홈 W3 × D2.2 선삭.",
               "커버판 Ø20 구멍에 끼워 위아래 필릿 용접 (3 개소).",
               "산세 · 부동태화."],
        inspect=[("바깥 지름", "Ø20 ±0.2"), ("보어", "Ø8.5 +0.3 / 0"),
                 ("O-링 홈", "W3 ±0.1 · D2.2 ±0.1"), ("용접", "육안 · 누설 없을 것")],
        extra=["조절봉(G-03)이 이 부싱을 지나 스키머 바스켓 높이를 잡는다. O-링이 "
               "없으면 급기 압력에 염수가 조금씩 올라와 커버 위로 샌다."],
    )


# ==========================================================================
# C 구동부 (제작품 2 종)
# ==========================================================================
def sheet_c05() -> None:
    def views(c: Canvas) -> None:
        v = View(96.0, 180.0, 0.7)
        c.poly(v.pts([(-90, 0), (90, 0), (90, 40), (-90, 40)]), THICK, "ln",
               close=True, dash="5 2.5")
        pts = v.pts([(-110, 0), (110, 0), (110, -6), (-110, -6)])
        c.hatch(pts, "hC5", 45)
        c.poly(pts, THICK, "ln", close=True)
        c.centreline(v.x(0), v.y(-20), v.x(0), v.y(56))
        c.dim_h(v.x(-110), v.x(110), v.y(-16), "Ø220 베이스", ext_from=v.y(-6))
        c.dim_v(v.y(0), v.y(40), v.x(110) + 10.0, "H40 — HOLD", left=False)
        c.dim_v(v.y(-6), v.y(0), v.x(110) + 26.0, "t6", left=False)
        c.text(v.x(0), v.y(24), "치수 HOLD", T_LABEL, "middle", "warn", weight="700")
        c.text(v.x(0), v.y(24) - 5.0, "벤더 GA 승인 후 확정", T_DIM - 0.2, "middle", "tx2")
        c.view_title(14.0, 30.0, "설치 envelope", v.label)
        rows = [["", "벤더가 확정해야 하는 값", "이 값이 없으면"]]
        rows += [["1", "씰 gland 외경 · 볼트 PCD", "베이스 판 구멍을 뚫을 수 없다"],
                 ["2", "감속기 마운팅 PCD · 볼트 규격", "윗면 플랜지를 가공할 수 없다"],
                 ["3", "씰 ↔ 감속기 축방향 거리", "램턴 높이 H40 이 정해지지 않는다"],
                 ["4", "구동부 질량 · 무게중심", "베이스 판 두께를 확정할 수 없다"]]
        c.view_title(14.0, 222.0, "벤더 제출자료")
        c.table(14.0, 226.0, [10.0, 78.0, 108.0], rows, row_h=5.4, size=T_DIM - 0.2,
                aligns=["middle", "start", "start"])

    simple_part_sheet(
        "C-05", "구동 램턴 · 어댑터", "커버 허브 ↔ 씰 ↔ 감속기 — 전 치수 HOLD", "1:0.7",
        "구동 램턴 부품도 — 설치 envelope 와 벤더 확정 대기 치수",
        views,
        steps=["**GA 승인 전 착수 금지.** 아래는 승인 후의 순서다.",
               "t6 판재로 베이스 판(Ø220) 절단, 씰 gland 외경에 맞춰 보어 가공.",
               "Ø180 × t5 관재를 확정 높이로 절단해 베이스에 전둘레 용접.",
               "윗면에 감속기 마운팅 플랜지 가공 — 확정 PCD 로 구멍 드릴.",
               "베이스면 ↔ 윗면 평행도 0.2 로 면삭.",
               "산세 · 부동태화."],
        inspect=[("베이스 보어", "GA 확정 후 H7"), ("마운팅 PCD", "GA 확정 후 ±0.2"),
                 ("상하면 평행도", "0.2"), ("높이", "GA 확정값 ±0.5")],
        extra=["이 부품은 커버 허브(B-02)·씰(C-03)·감속기(C-02) 셋을 잇는다. 셋 중 "
               "하나라도 치수가 안 나오면 만들 수 없다.",
               "설치 envelope Z951~Z1420 (H469) 안에 들어와야 한다 — 넘어가면 전체 "
               "높이와 프레임 전도 검토(CHK-13)를 다시 해야 한다."],
    )


def sheet_c06() -> None:
    def views(c: Canvas) -> None:
        v = View(96.0, 156.0, 0.55)
        od, ln, t = 188.0, 70.0, 1.5
        tube_section(c, v, od, t, ln, 0.0, "hC6")
        c.centreline(v.x(0), v.y(-14), v.x(0), v.y(ln + 14))
        c.dim_h(v.x(-od / 2), v.x(od / 2), v.y(-12), f"Ø{fmt(od)}", ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(ln), v.x(od / 2) + 10.0, fmt(ln), left=False)
        c.leader(v.x(od / 2), v.y(ln * .6), v.x(od / 2 + 34), v.y(ln * .1),
                 f"t{fmt(t)} 절곡", lines=("세로이음 1 개소 · 점용접",))
        c.view_title(14.0, 30.0, "단면", v.label)
        e = View(96.0, 248.0, 0.55)
        cross_centre(c, e, od / 2 + 18)
        c.circle(e.x(0), e.y(0), e.d(od / 2), THICK, "ln")
        c.circle(e.x(0), e.y(0), e.d(od / 2 - t), THIN, "ln")
        for i in range(3):
            a = math.radians(90 + 120 * i)
            c.circle(e.x((od / 2 - 9) * math.cos(a)), e.y((od / 2 - 9) * math.sin(a)),
                     e.d(3), THICK, "ln")
        c.leader(e.x((od / 2 - 9) * math.cos(math.radians(30))),
                 e.y((od / 2 - 9) * math.sin(math.radians(30))),
                 e.x(od / 2 + 30), e.y(od / 2 * .5), "M5 나비볼트 3 개소",
                 lines=("공구 없이 여닫는다",))
        c.view_title(14.0, 192.0, "평면", e.label)
        c.text(14.0, 282.0, "회전하는 커플링에 손이 닿지 않게 가리는 것이 전부다 — "
               "하중을 받지 않으므로 t1.5 로 충분하다.", T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "C-06", "보호 커버", "Ø188 × H70 × t1.5 · 커플링 차폐", "1:0.55",
        "보호 커버 부품도 — 원통 단면과 평면, 나비볼트 고정",
        views,
        steps=["t1.5 판재를 전개 (π × Ø188 = 591) × 70 으로 절단.",
               "원통으로 말아 세로이음 1 개소 점용접.",
               "M5 나비볼트 구멍 3 개소 (120° 등분) 드릴.",
               "모서리 전부 버 제거 — 손이 닿는 부품이라 날이 남으면 안 된다.",
               "산세 · 부동태화."],
        inspect=[("전개 길이", "591 ±2"), ("높이", "70 ±1"),
                 ("구멍 분할", "120° ±2°"), ("모서리", "날선 곳 없을 것")],
        extra=["인터록은 달지 않는다. 30~150 rpm 에서 노출부가 커플링 하나뿐이고 "
               "공구 없이 여는 구조라, 정지 확인 후 접근하는 것으로 관리한다."],
    )


# ==========================================================================
# D 교반축 · 임펠러
# ==========================================================================
def sheet_d01() -> None:
    def views(c: Canvas) -> None:
        L, d = 760.0, G.shaft_od_mm
        v = View(24.0, 96.0, 4.0)          # x = 축방향, y = 반지름
        for sign in (1.0, -1.0):
            c.poly(v.pts([(0, sign * d / 2), (L, sign * d / 2)]), THICK, "ln")
        c.poly(v.pts([(0, -d / 2), (0, d / 2)]), THICK, "ln")
        c.poly(v.pts([(L, -d / 2), (L, d / 2)]), THICK, "ln")
        c.centreline(v.x(-14), v.y(0), v.x(L + 14), v.y(0))
        for a, b, lab in ((10.0, 60.0, "키홈 1"), (190.0, 240.0, "키홈 2"),
                          (700.0, 755.0, "키홈 3")):
            c.rect(v.x(a), v.y(d / 2), v.d(b - a), v.d(3.5), THICK, "ln")
            c.text(v.x((a + b) / 2), v.y(d / 2) - 4.0, lab, T_DIM - 0.4, "middle", "tx2")
        c.dim_h(v.x(0), v.x(L), v.y(-d / 2) - 20.0, f"{fmt(L)} ±1.0", ext_from=v.y(-d / 2))
        for a, lab in ((10.0, "10"), (60.0, "60"), (190.0, "190"), (240.0, "240"), (700.0, "700")):
            c.dim_h(v.x(0), v.x(a), v.y(-d / 2) - 5.0 - (a / 700.0) * 0.0, lab)
        c.dim_v(v.y(-d / 2), v.y(d / 2), v.x(L) + 10.0, f"Ø{fmt(d)} h7", left=False)
        c.datum(v.x(-16), v.y(0), "A", v.x(6), v.y(-d / 2))
        w = c.fcf(14.0, 124.0, "straight", "0.5 / 600", "")
        c.text(14.0 + w + 3.0, 127.6, "축 직진도", T_DIM - 0.3, "start", "tx2")
        w = c.fcf(14.0, 133.0, "runout", "0.05", "A")
        c.text(14.0 + w + 3.0, 136.6, "임펠러 자리 원주 흔들림", T_DIM - 0.3, "start", "tx2")
        c.surface(14.0, 150.0, "Ra 0.8", "전 둘레")
        c.view_title(14.0, 30.0, "축 전체", v.label)
        c.text(14.0, 40.0, "키홈 1·2 = 임펠러 (D-02/03) · 키홈 3 = 커플링 (C-04, GA 확정 후)",
               T_DIM - 0.2, "start", "tx2")

        k = View(58.0, 250.0, 0.5)
        cross_centre(c, k, d / 2 + 10)
        c.circle(k.x(0), k.y(0), k.d(d / 2), THICK, "ln")
        c.rect(k.x(-3), k.y(d / 2), k.d(6), k.d(3.5), THICK, "ln", fill="var(--paper)")
        c.line(k.x(-3), k.y(d / 2), k.x(3), k.y(d / 2), 0.0, "ln")
        c.dim_h(k.x(-3), k.x(3), k.y(-d / 2) - 10.0, "6 P9", ext_from=k.y(0))
        c.dim_v(k.y(d / 2 - 3.5), k.y(d / 2), k.x(d / 2) + 12.0, "3.5", left=False)
        c.text(k.x(0), k.y(-d / 2) - 20.0, f"축 Ø{fmt(d)} h7 · 키 6 × 6 (D-04)",
               T_DIM - 0.2, "middle", "tx2")
        c.view_title(14.0, 208.0, "키홈 단면", "2:1")

        rows = [["항목", "값", "근거"]]
        from mp50_separator.checks import DESIGN_MAX_RPM, critical_speed

        rpm = critical_speed()[0]
        rows += [["1 차 위험속도", f"{rpm:.0f} rpm", "커버 허브를 지지점으로 본 외팔보"],
                 ["운전 최고속도", f"{DESIGN_MAX_RPM:.0f} rpm", "CHK-05 권고"],
                 ["여유", f"{rpm / DESIGN_MAX_RPM:.1f} 배", "1.5 배 이상이면 공진을 피한다"],
                 ["전단응력", "5.6 MPa", "정착층 재기동 토크 17.1 N·m"],
                 ["허용 전단", "약 68 MPa", "SUS316L · 여유 12 배"]]
        c.view_title(138.0, 208.0, "축 지름 근거")
        c.table(138.0, 212.0, [34.0, 26.0, 52.0], rows, row_h=5.2, size=T_DIM - 0.3,
                aligns=["start", "end", "start"])
        c.text(138.0, 212.0 + len(rows) * 5.2 + 5.0,
               "축 지름은 토크가 아니라 위험속도가 정했다.", T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "D-01", "교반축", f"Ø{G.shaft_od_mm:.0f} h7 × L760 · SUS316L", "1:4",
        "교반축 부품도 — 전장과 키홈 위치, 직진도·흔들림 공차, 축 지름 근거",
        views,
        steps=["Ø28 환봉을 L780 으로 절단 (가공 여유 20).",
               "양 센터 가공 후 센터 사이에 물려 Ø25 h7 로 연삭. 한 번 물림에서 "
               "끝까지 간다 — 다시 물리면 동축이 어긋난다.",
               "직진도 0.5 / 600 확인. 넘으면 교정 후 재연삭.",
               "키홈 3 개소 6 P9 × 깊이 3.5 밀링 (엔드밀, 양단 R).",
               "L760 으로 양단 마무리 절단, 끝면 C1 모따기.",
               "임펠러 자리 2 곳의 원주 흔들림을 데이텀 A 기준 0.05 로 확인.",
               "전 둘레 Ra 0.8 까지 연마 후 산세 · 부동태화."],
        inspect=[("지름", "Ø25 h7 (0 / -0.021)"), ("전장", "760 ±1.0"),
                 ("직진도", "0.5 / 600"), ("원주 흔들림", "0.05 (데이텀 A)"),
                 ("키홈", "6 P9 · 깊이 3.5 ±0.1"), ("조도", "Ra ≤ 0.8")],
        extra=["직진도 0.5/600 은 [R] §2 공차표 값이다. 이 값을 못 맞추면 임펠러 "
               "TIR 1.0 도 못 맞춘다.",
               "키홈 3 은 커플링용이라 **벤더 GA 확정 후** 위치를 정한다. GA 전에는 "
               "뚫지 말고 소재만 남겨 둔다."],
    )


def sheet_d02() -> None:
    def views(c: Canvas) -> None:
        D, hub, hl, bw, bt = G.impeller_od_mm, G.impeller_hub_od_mm, G.impeller_hub_length_mm, \
            G.impeller_blade_width_mm, G.impeller_blade_thickness_mm
        v = View(74.0, 104.0, 2.4)
        cross_centre(c, v, D / 2 + 26)
        c.circle(v.x(0), v.y(0), v.d(D / 2), THIN, "cl", dash="5 2")
        c.circle(v.x(0), v.y(0), v.d(hub / 2), THICK, "ln")
        c.circle(v.x(0), v.y(0), v.d(G.shaft_od_mm / 2), THICK, "ln")
        for b in range(G.impeller_blades):
            a = math.radians(90 * b + 45)
            ca, sa = math.cos(a), math.sin(a)
            r0, r1 = hub / 2, D / 2
            hw = bw / 2 * math.cos(math.radians(G.impeller_pitch_deg))
            c.poly(v.pts([(r0 * ca - sa * hw, r0 * sa + ca * hw),
                          (r1 * ca - sa * hw, r1 * sa + ca * hw),
                          (r1 * ca + sa * hw, r1 * sa - ca * hw),
                          (r0 * ca + sa * hw, r0 * sa - ca * hw)]), THICK, "ln", close=True)
        c.dim_h(v.x(-D / 2), v.x(D / 2), v.y(-D / 2 - 16), f"Ø{fmt(D)} ±1")
        c.dim_h(v.x(-hub / 2), v.x(hub / 2), v.y(D / 2 + 12), f"허브 Ø{fmt(hub)}")
        c.text(v.x(0), v.y(-D / 2 - 26), f"{G.impeller_blades} 매 90° 등분 · 취부각 {fmt(G.impeller_pitch_deg)}°",
               T_DIM - 0.2, "middle", "tx2")
        c.view_title(14.0, 30.0, "평면", v.label)

        b = View(162.0, 120.0, 1.6)
        rl = G.impeller_blade_radial_mm
        c.rect(b.x(0), b.y(bw / 2), b.d(rl), b.d(bw), THICK, "ln")
        c.dim_h(b.x(0), b.x(rl), b.y(-bw / 2) - 9.0, fmt(rl), ext_from=b.y(-bw / 2))
        c.dim_v(b.y(-bw / 2), b.y(bw / 2), b.x(rl) + 9.0, fmt(bw), left=False)
        c.text(b.x(rl / 2), b.y(bw / 2) + 8.0, f"t{fmt(bt)} · 모서리 R2",
               T_DIM - 0.2, "middle", "tx2")
        ax, ay = b.x(0), b.y(-bw / 2) - 22.0
        c.arc(ax, ay, 9.0, 0, 45, THIN, "dl")
        c.line(ax, ay, ax + 20, ay, THIN, "dl")
        c.line(ax, ay, ax + 14.2, ay - 14.2, THIN, "dl")
        c.text(ax + 11.0, ay + 4.6, f"{fmt(G.impeller_pitch_deg)}° 취부각", T_NOTE, "start",
               "tx", weight="600")
        c.view_title(138.0, 30.0, "날개 전개", b.label)

        s = View(74.0, 244.0, 1.2)
        for sign in (1.0, -1.0):
            pts = s.pts([(sign * G.shaft_od_mm / 2, -hl / 2), (sign * hub / 2, -hl / 2),
                         (sign * hub / 2, hl / 2), (sign * G.shaft_od_mm / 2, hl / 2)])
            c.hatch(pts, "hH", 45 if sign > 0 else -45)
            c.poly(pts, THICK, "ln", close=True)
            proj = bw * math.sin(math.radians(G.impeller_pitch_deg)) / 2
            c.poly(s.pts([(sign * hub / 2, proj), (sign * D / 2, -proj)]), THICK, "ln")
        c.centreline(s.x(0), s.y(-hl), s.x(0), s.y(hl))
        c.dim_v(s.y(-hl / 2), s.y(hl / 2), s.x(hub / 2) + 10.0, f"{fmt(hl)}", left=False)
        c.leader(s.x(hub / 2 + 8), s.y(0), s.x(D / 2 + 16), s.y(hl * 0.9),
                 "날개 ↔ 허브 필릿 a3 양면")
        c.view_title(14.0, 196.0, "단면", s.label)
        w = c.fcf(138.0, 210.0, "runout", "1.0", "A")
        c.text(138.0 + w + 3.0, 213.6, "조립 후 TIR (축 데이텀 A)", T_DIM - 0.3, "start", "tx2")
        for i, line in enumerate(wrap(
                "D-02(하부 Z430)과 D-03(상부 Z610)은 같은 부품이다. 이 도면으로 2 개를 "
                "만들고, 조립 표고만 달리한다.", 62)):
            c.text(138.0, 228.0 + i * 4.2, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                "날개 팁은 배플 안쪽 모서리(R159)와 9 mm 밖에 안 떨어져 있다. Ø300 "
                "+1 을 넘기면 간섭한다 (C2 · CHK-02).", 62)):
            c.text(138.0, 244.0 + i * 4.2, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "D-02", "임펠러", f"Ø{G.impeller_od_mm:.0f} 4PBT{G.impeller_pitch_deg:.0f}° · D-02/D-03 동일품",
        "1:2.4", "임펠러 부품도 — 평면, 날개 전개, 허브 단면, 조립 후 흔들림 공차",
        views,
        steps=["허브: Ø65 환봉을 L70 으로 절단, 보어 Ø25 H7 가공, 키홈 6 JS9 브로칭.",
               f"날개: t{G.impeller_blade_thickness_mm:.0f} 판재에서 {G.impeller_blade_radial_mm:.0f} × {G.impeller_blade_width_mm:.0f} 4 장 절단, 모서리 R2.",
               f"조립 지그에 허브를 세우고 날개를 90° 등분·취부각 {G.impeller_pitch_deg:.0f}° 로 물린다.",
               "날개 ↔ 허브 필릿 a3 양면 연속 용접. 4 장을 대각 순서로 용접해 비틀림을 막는다.",
               f"용접 후 Ø{G.impeller_od_mm:.0f} +1/0 으로 팁 다듬기 — 넘으면 배플과 간섭한다.",
               "M8 세트스크류 구멍 2 개소 (90° 배치, 키 반대편) 탭 가공.",
               "축에 끼워 TIR 1.0 확인. 넘으면 날개를 잡아 교정.",
               "산세 · 부동태화."],
        inspect=[("바깥 지름", "Ø300 +1 / 0"), ("보어", "Ø25 H7"),
                 ("키홈", "6 JS9"), ("취부각", "45° ±1°"),
                 ("조립 후 TIR", "1.0 (데이텀 A)"), ("용접", "필릿 a3 연속 · 육안")],
        extra=["4 장을 대각으로 용접하지 않으면 허브가 한쪽으로 틀어져 TIR 이 안 나온다.",
               "Ø300 은 D/T 0.75 로 통상(0.33~0.5)보다 크다. 좁은 용기에서 분산을 "
               "얻기 위한 근접 임펠러이며, 그래서 배플 폭이 35 로 제한됐다."],
    )


def sheet_d06() -> None:
    def views(c: Canvas) -> None:
        od, bore, ln = 50.0, G.shaft_od_mm, 25.0
        v = View(84.0, 150.0, 0.5)
        for sign in (1.0, -1.0):
            pts = v.pts([(sign * bore / 2, 0), (sign * od / 2, 0),
                         (sign * od / 2, ln), (sign * bore / 2, ln)])
            c.hatch(pts, "hK", 45 if sign > 0 else -45)
            c.poly(pts, THICK, "ln", close=True)
        c.centreline(v.x(0), v.y(-10), v.x(0), v.y(ln + 10))
        c.dim_h(v.x(-od / 2), v.x(od / 2), v.y(-9), f"Ø{fmt(od)}", ext_from=v.y(0))
        c.dim_h(v.x(-bore / 2), v.x(bore / 2), v.y(ln + 9), f"Ø{fmt(bore)} H7",
                ext_from=v.y(ln))
        c.dim_v(v.y(0), v.y(ln), v.x(od / 2) + 10.0, fmt(ln), left=False)
        c.view_title(14.0, 30.0, "단면", v.label)
        e = View(84.0, 244.0, 0.5)
        cross_centre(c, e, od / 2 + 14)
        c.circle(e.x(0), e.y(0), e.d(od / 2), THICK, "ln")
        c.circle(e.x(0), e.y(0), e.d(bore / 2), THICK, "ln")
        for i in range(2):
            a = math.radians(90 * i)
            c.circle(e.x((od / 2 + bore / 2) / 2 * math.cos(a)),
                     e.y((od / 2 + bore / 2) / 2 * math.sin(a)), e.d(4), THICK, "ln")
        c.leader(e.x((od / 2 + bore / 2) / 2), e.y(0), e.x(od / 2 + 22), e.y(-od / 4),
                 "M6 세트스크류 2 개소", lines=("90° 배치",))
        c.view_title(14.0, 200.0, "평면", e.label)
        c.text(14.0, 272.0, "임펠러 바로 위에 끼워 축방향 위치를 잡는다. 이것이 없으면 "
               "임펠러가 세트스크류만으로 버텨", T_DIM - 0.2, "start", "tx2")
        c.text(14.0, 277.0, f"표고 공차 ±{G.impeller_z_tolerance_mm:.0f} 를 다 써 버린다.",
               T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "D-06", "스러스터 칼라", f"Ø50 × L25 · 보어 Ø{G.shaft_od_mm:.0f} H7 · 2 개", "2:1",
        "스러스터 칼라 부품도 — 단면과 평면, 세트스크류 위치",
        views,
        steps=["Ø55 환봉을 L30 으로 절단.",
               f"보어 Ø{G.shaft_od_mm:.0f} H7 가공 — 축에 미끄러지게 들어가되 흔들리지 않아야 한다.",
               "바깥 Ø50 선삭, 양 끝면 직각 마무리.",
               "M6 세트스크류 탭 2 개소 (90° 배치).",
               "모서리 C1, 산세 · 부동태화."],
        inspect=[("보어", "Ø25 H7"), ("바깥 지름", "Ø50 ±0.3"),
                 ("길이", "25 ±0.2"), ("탭", "M6 · 2 개소 90°")],
    )


# ==========================================================================
# E 배플 · F 분산링
# ==========================================================================
def sheet_e01() -> None:
    def views(c: Canvas) -> None:
        w, ln, t = G.baffle_width_mm, G.baffle_length_mm, G.baffle_thickness_mm
        gap = G.baffle_wall_gap_mm
        v = View(40.0, 250.0, 1.6)
        c.rect(v.x(0), v.y(ln), v.d(w), v.d(ln), THICK, "ln")
        for i in range(3):
            z = 22.0 + i * (ln - 44.0) / 2
            c.rect(v.x(0), v.y(z + 12.5), v.d(gap), v.d(25.0), THIN, "ln", dash="2.4 1.2")
            c.dim_v(v.y(0), v.y(z), v.x(w) + 9.0 + i * 11.0, fmt(z), left=False)
        c.dim_h(v.x(0), v.x(w), v.y(0) - 9.0, f"{fmt(w)} ±0.5", ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(ln), v.x(0) - 9.0, f"{fmt(ln)} ±1", ext_from=v.x(0))
        c.text(v.x(w / 2), v.y(ln) - 7.0, f"t{fmt(t)} · 모서리 R2", T_DIM - 0.2, "middle", "tx2")
        c.view_title(14.0, 30.0, "배플판", v.label)

        d = View(146.0, 116.0, 0.5)
        c.rect(d.x(0), d.y(25.0), d.d(gap), d.d(25.0), THICK, "ln")
        c.dim_h(d.x(0), d.x(gap), d.y(0) - 9.0, f"{fmt(gap)}", ext_from=d.y(0))
        c.dim_v(d.y(0), d.y(25.0), d.x(gap) + 10.0, "25", left=False)
        c.text(d.x(gap / 2), d.y(25.0) - 8.0, f"t{fmt(t)}", T_DIM - 0.2, "middle", "tx2")
        c.leader(d.x(gap), d.y(12.5), d.x(gap) + 34.0, d.y(38.0), "E-02 스탠드오프 탭",
                 lines=("배플당 3 개 · 별도 도면 참조",))
        c.view_title(120.0, 30.0, "스탠드오프", d.label)

        a = View(186.0, 200.0, 1.4)
        c.line(a.x(-46), a.y(0), a.x(46), a.y(0), THICK, "ln")
        c.text(a.x(0), a.y(0) + 6.0, "동체 내면", T_DIM - 0.3, "middle", "tx2")
        c.rect(a.x(-w / 2), a.y(-gap), a.d(w), a.d(t), THICK, "ln")
        for sx in (-1, 1):
            c.rect(a.x(sx * 12 - gap / 2), a.y(0), a.d(gap), a.d(t), THIN, "ln")
        c.dim_v(a.y(-gap), a.y(0), a.x(w / 2) + 12.0, f"{fmt(gap)} 이격", left=False)
        c.view_title(148.0, 160.0, "설치 단면", a.label)
        for i, line in enumerate(wrap(
                "벽에 바로 붙이면 배플 뒤에 분말이 쌓여 배치마다 남는다. 스탠드오프 3 개로 "
                f"{fmt(gap)} mm 띄워 씻기게 한다.", 58)):
            c.text(148.0, 220.0 + i * 4.2, line, T_DIM - 0.2, "start", "tx2")
        w2 = c.fcf(148.0, 238.0, "flat", "1.0", "")
        c.text(148.0 + w2 + 3.0, 241.6, "설치 후 면 평면도", T_DIM - 0.3, "start", "tx2")
        for i, line in enumerate(wrap(
                f"폭 {fmt(w)} 는 임의로 정한 값이 아니다. 원본 80 이면 안쪽 모서리가 R114 로 "
                f"Ø{fmt(G.impeller_od_mm)} 임펠러의 팁 R150 과 36 mm 겹쳐 축이 돌지 않는다 (C2).", 58)):
            c.text(148.0, 254.0 + i * 4.2, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "E-01", "배플판", f"W{G.baffle_width_mm:.0f} × L{G.baffle_length_mm:.0f} × t{G.baffle_thickness_mm:.0f} · 4 매",
        "1:1.6", "배플판 부품도 — 평판 치수, 스탠드오프 위치, 설치 단면과 벽 이격",
        views,
        steps=[f"t{G.baffle_thickness_mm:.0f} 판재를 {fmt(G.baffle_width_mm)} × {fmt(G.baffle_length_mm)} 로 절단 (4 매).",
               "모서리 전부 R2, 버 제거.",
               "스탠드오프 탭(E-02) 3 개를 표시 위치에 필릿 용접.",
               f"동체 내면 Z{fmt(G.baffle_bottom_z)}~Z{fmt(G.baffle_top_z)} 에 90° 등분 4 매 설치. "
               "탭을 벽에 대고 연속 필릿 용접.",
               "용접부 평활 연삭 — 배플 뒤에 걸릴 턱을 남기지 않는다.",
               "산세 · 부동태화."],
        inspect=[("폭", "35 ±0.5 (간섭 여유가 9 mm 뿐이다)"),
                 ("길이", "300 ±1"), ("벽 이격", "6 ±1"),
                 ("등분", "90° ±1°"), ("설치 표고", f"Z{fmt(G.baffle_bottom_z)} ±2")],
        extra=[f"폭 공차를 ±0.5 로 조인 이유는 임펠러 팁 간극이 {G.impeller_tip_clearance_mm:.0f} mm 밖에 "
               "없기 때문이다. 축 편심 0.5 와 임펠러 TIR 1.0 을 함께 쓰면 여유가 "
               f"{G.impeller_tip_clearance_mm - 1.5:.1f} mm 다."],
    )


def sheet_e02() -> None:
    def views(c: Canvas) -> None:
        v = View(48.0, 120.0, 0.4)
        c.rect(v.x(0), v.y(25.0), v.d(6.0), v.d(25.0), THICK, "ln")
        c.dim_h(v.x(0), v.x(6.0), v.y(0) - 10.0, "6", ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(25.0), v.x(6.0) + 12.0, "25", left=False)
        c.text(v.x(3), v.y(25.0) - 12.0, "t3", T_DIM - 0.2, "middle", "tx2")
        c.text(v.x(3), v.y(-14.0), "E-02 · 12 개", T_NOTE, "middle", "tx", weight="600")
        c.view_title(14.0, 30.0, "E-02 스탠드오프 탭", v.label)

        b = View(140.0, 130.0, 0.55)
        c.poly(b.pts([(0, 0), (40, 0), (40, 3), (3, 3), (3, 30), (0, 30)]), THICK, "ln", close=True)
        c.dim_h(b.x(0), b.x(40), b.y(0) - 10.0, "40", ext_from=b.y(0))
        c.dim_v(b.y(0), b.y(30), b.x(0) - 10.0, "30", ext_from=b.x(0))
        c.text(b.x(20), b.y(-20.0), "F-04 · 3 개", T_NOTE, "middle", "tx", weight="600")
        c.leader(b.x(3), b.y(3), b.x(44), b.y(20.0), "90° 절곡 · 내R3",
                 lines=("전개 67 × 30 · t3",))
        c.view_title(112.0, 30.0, "F-04 고정 브래킷", b.label)
        for i, line in enumerate(wrap(
                "E-02 는 배플판(E-01)을 동체 벽에서 6 mm 띄우는 받침이다. 배플 한 매당 "
                "3 개, 4 매에 12 개.", 100)):
            c.text(14.0, 190.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                "F-04 는 급기 분산링(F-01)을 콘 내면에 붙드는 브래킷이다. 120° 등분 3 개소. "
                "긴 쪽을 링에, 짧은 쪽을 콘 벽에 댄다. 링 편심 3 mm 안에 들도록 지그로 "
                "위치를 잡고 붙인다.", 100)):
            c.text(14.0, 206.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                "둘 다 소물이지만 용접 위치가 성능을 정한다 — E-02 가 삐뚤면 배플이 기울고, "
                "F-04 가 삐뚤면 분산링이 편심되어 한쪽 홀로만 공기가 간다.", 100)):
            c.text(14.0, 230.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "E-02", "소물 2 종", "E-02 스탠드오프 탭 · F-04 고정 브래킷 — 합본", "2.5:1",
        "소물 부품도 — 스탠드오프 탭과 분산링 고정 브래킷의 전개 치수",
        views,
        steps=["E-02: t3 판재를 25 × 6 으로 절단 (12 개). 모서리 버 제거.",
               "E-02: 배플판(E-01) 뒷면에 3 개소 필릿 용접.",
               "F-04: t3 판재를 전개 67 × 30 으로 절단 (3 개).",
               "F-04: 내R3 으로 90° 절곡.",
               "F-04: 콘 내면에 120° 등분 3 개소 필릿 용접 — 지그로 분산링 위치를 잡은 뒤 붙인다.",
               "산세 · 부동태화."],
        inspect=[("E-02 외형", "±0.5"), ("F-04 전개", "±1.0"),
                 ("F-04 절곡각", "90° ±1°"), ("F-04 설치", "링 편심 ≤ 3")],
    )


def sheet_f01() -> None:
    def views(c: Canvas) -> None:
        pcd, od, holes = G.sparger_pcd_mm, G.sparger_tube_od_mm, G.sparger_holes
        v = View(74.0, 106.0, 1.5)
        cross_centre(c, v, pcd / 2 + 30)
        c.circle(v.x(0), v.y(0), v.d(pcd / 2 + od / 2), THICK, "ln")
        c.circle(v.x(0), v.y(0), v.d(pcd / 2 - od / 2), THICK, "ln")
        c.circle(v.x(0), v.y(0), v.d(pcd / 2), THIN, "cl", dash="6 1.2 1.2 1.2")
        for i in range(holes):
            a = math.radians(360 / holes * i)
            c.circle(v.x(pcd / 2 * math.cos(a)), v.y(pcd / 2 * math.sin(a)),
                     v.d(2.4), THICK, "ln", fill="var(--ink)")
        c.dim_h(v.x(-pcd / 2), v.x(pcd / 2), v.y(-pcd / 2 - 20), f"PCD Ø{fmt(pcd)}")
        c.arc(v.x(0), v.y(0), v.d(pcd / 2 + 22), 0, 30, THIN, "dl")
        c.text(v.x((pcd / 2 + 30) * math.cos(math.radians(15))),
               v.y((pcd / 2 + 30) * math.sin(math.radians(15))) + 1.0, "30°",
               T_DIM - 0.2, "middle", "tx2")
        c.leader(v.x((pcd / 2 + od / 2) * math.cos(math.radians(105))),
                 v.y((pcd / 2 + od / 2) * math.sin(math.radians(105))),
                 v.x(pcd / 2 + 40), v.y(pcd / 2 * 0.7), "맞대기 이음 1 개소",
                 lines=("강하관 반대편에 둔다",))
        c.view_title(14.0, 30.0, "평면", v.label)

        d = View(174.0, 208.0, 0.16)
        c.circle(d.x(0), d.y(0), d.d(od / 2), THICK, "ln")
        c.circle(d.x(0), d.y(0), d.d(G.sparger_tube_id_mm / 2), THICK, "ln", dash="2.4 1.2")
        c.centreline(d.x(0), d.y(11), d.x(0), d.y(-14))
        c.poly(d.pts([(-G.sparger_hole_dia_mm / 2, -od / 2),
                      (G.sparger_hole_dia_mm / 2, -od / 2)]), THICK, "ln")
        c.poly(d.pts([(0, -8.0), (-1.5, -12.5), (0, -10.6), (1.5, -12.5)]),
               THIN, "ln", close=True, fill="var(--ink)")
        c.dim_h(d.x(-od / 2), d.x(od / 2), d.y(9.0), f"Ø{fmt(od)}", ext_from=d.y(5.0))
        c.leader(d.x(0), d.y(-od / 2), d.x(18), d.y(-7.0),
                 f"Ø{fmt(G.sparger_hole_dia_mm, 1)} 하향",
                 lines=("버 제거 필수 — 버가 남으면", "그 홀만 유량이 준다"))
        c.view_title(138.0, 172.0, "분사홀 단면", "6:1")

        rows = [["항목", "값"]]
        rows += [["급기 (DOE 상한)", f"{G.air_max_lpm:.0f} L/min"],
                 ["오리피스 유속", "7.9 m/s"],
                 ["링 내부 유속", "1.31 m/s"],
                 ["유속 비", "6.0 (3 이상이면 고르게 갈린다)"],
                 ["기포 지름", "약 Ø3.9 mm"]]
        c.view_title(14.0, 216.0, "급기 분배 (CHK-08)")
        c.table(14.0, 220.0, [44.0, 74.0], rows, row_h=5.2, size=T_DIM - 0.3,
                aligns=["start", "start"])
        for i, line in enumerate(wrap(
                "기포 Ø3.9 mm 는 '미세기포'가 아니다. 이 장치에서는 그게 맞다 — 미세기포는 "
                "폴리머에 붙어 부선으로 띄워 밀도차 측정을 오염시킨다 (C5).", 60)):
            c.text(138.0, 216.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "F-01", "급기 분산링", f"PCD Ø{G.sparger_pcd_mm:.0f} · Ø{G.sparger_tube_od_mm:.0f} × t1.5 · Ø1.5 홀 12",
        "1:1.5", "급기 분산링 부품도 — 평면과 분사홀 단면, 급기 분배 검증",
        views,
        steps=[f"Ø{G.sparger_tube_od_mm:.0f} × t1.5 관재를 L840 으로 절단 (π × Ø{G.sparger_pcd_mm:.0f} = 785 + 여유).",
               f"롤벤더로 PCD Ø{G.sparger_pcd_mm:.0f} 원형으로 말고 맞대기 1 개소 전용입 용접.",
               f"Ø{G.sparger_hole_dia_mm:.1f} 홀 {G.sparger_holes} 개를 30° 등분으로 **아래쪽**에 드릴.",
               "홀 안팎 버를 완전히 제거 — 버가 남은 홀은 유량이 줄어 분배가 깨진다.",
               "강하관(F-03) 접속부를 이음 반대편에 용접.",
               "고정 브래킷(F-04) 3 개소 용접.",
               "산세 · 부동태화 후 공기를 넣어 12 개 홀에서 고르게 나오는지 육안 확인."],
        inspect=[("PCD", "Ø250 ±2"), ("링 편심", "≤ 3 (설치 후)"),
                 ("홀 지름", "Ø1.5 ±0.05"), ("홀 분할", "30° ±1°"),
                 ("버", "안팎 모두 없을 것"), ("분사 시험", "12 개 홀 모두 토출")],
        extra=["홀을 아래로 뚫는 이유는 급기를 멈췄을 때 분말이 역류해 막히지 않게 "
               "하기 위해서다. N3 직전의 체크밸브(F-05)와 함께 쓴다.",
               f"원본 [D1] 의 60 × Ø2 였다면 같은 유량에서 오리피스가 0.9 m/s 로 링 "
               "유속과 비슷해져 먼 홀로는 공기가 가지 않는다 (C4)."],
    )


def sheet_f03() -> None:
    def views(c: Canvas) -> None:
        v = View(50.0, 236.0, 0.8)
        pts = [(0, 0), (47, 0), (47, 90), (73, 90)]
        c.poly(v.pts(pts), THICK, "ln")
        for a, b in zip(pts, pts[1:]):
            pass
        c.dim_h(v.x(0), v.x(47), v.y(0) - 10.0, "47", ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(90), v.x(47) + 12.0, "90", left=False)
        c.dim_h(v.x(47), v.x(73), v.y(90) + 10.0, "26", ext_from=v.y(90))
        c.text(v.x(0), v.y(-20.0), "전개 길이 약 300 (굽힘 여유 포함)", T_DIM - 0.2, "start", "tx2")
        c.leader(v.x(47), v.y(0), v.x(96), v.y(-30.0), "굽힘 R24 · 2 개소",
                 lines=("만드렐 벤딩 — 찌그러짐 없을 것",))
        c.view_title(14.0, 30.0, "전개 형상", v.label)
        e = View(186.0, 120.0, 0.16)
        c.circle(e.x(0), e.y(0), e.d(G.sparger_tube_od_mm / 2), THICK, "ln")
        c.circle(e.x(0), e.y(0), e.d(G.sparger_tube_id_mm / 2), THICK, "ln")
        cross_centre(c, e, G.sparger_tube_od_mm / 2 + 4)
        c.dim_h(e.x(-G.sparger_tube_od_mm / 2), e.x(G.sparger_tube_od_mm / 2), e.y(-12),
                f"Ø{fmt(G.sparger_tube_od_mm)} × t1.5")
        c.view_title(150.0, 30.0, "단면", "6:1")
        for i, line in enumerate(wrap(
                "N3(Z520)에서 분산링(Z300)까지 공기를 내린다. 배플 뒤쪽으로 배선해 임펠러 "
                "회전면을 침범하지 않게 한다 — 회전면에 들어가면 관이 잘린다.", 58)):
            c.text(138.0, 150.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                "굽힘은 반드시 만드렐 벤딩으로. 맨드렐 없이 구부리면 단면이 찌그러져 "
                "유로가 좁아지고, 그 자리에 물이 고여 정지 중에 분말이 굳는다.", 58)):
            c.text(138.0, 176.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "F-03", "강하관", f"Ø{G.sparger_tube_od_mm:.0f} × t1.5 · 2 굽힘 · N3 → 분산링", "1:0.8",
        "강하관 부품도 — 전개 형상과 굽힘 치수, 단면",
        views,
        steps=[f"Ø{G.sparger_tube_od_mm:.0f} × t1.5 관재를 L300 으로 절단.",
               "만드렐 벤더로 R24 × 90° 굽힘 2 개소.",
               "한쪽 끝을 분산링(F-01)에, 다른 쪽을 N3 노즐 안쪽에 맞대기 용접.",
               "배관 경로가 배플 뒤쪽을 지나는지 조립 시 확인.",
               "산세 · 부동태화."],
        inspect=[("굽힘 반지름", "R24 ±2"), ("굽힘각", "90° ±2°"),
                 ("단면 찌그러짐", "단축/장축 ≥ 0.9"), ("용접", "PT · 누설 없을 것")],
    )


# ==========================================================================
# G 스키머
# ==========================================================================
def sheet_g01() -> None:
    def views(c: Canvas) -> None:
        od, h, t = G.skimmer_od_mm, G.skimmer_height_mm, 2.0
        dev = math.pi * (od - t)
        v = View(24.0, 92.0, 4.0)
        c.rect(v.x(0), v.y(h), v.d(dev), v.d(h), THICK, "ln")
        c.dim_h(v.x(0), v.x(dev), v.y(h) - 9.0, f"{fmt(dev, 1)} ±1", ext_from=v.y(h))
        c.dim_v(v.y(0), v.y(h), v.x(0) - 8.0, fmt(h), ext_from=v.x(0))
        c.text(v.x(dev / 2), v.y(0) + 8.0, f"t{fmt(t)} · 중립축 π×(Ø{fmt(od)} − t{fmt(t)})",
               T_DIM - 0.2, "middle", "tx2")
        c.view_title(14.0, 30.0, "전개", v.label)

        p = View(74.0, 190.0, 2.2)
        cross_centre(c, p, od / 2 + 22)
        c.circle(p.x(0), p.y(0), p.d(od / 2), THICK, "ln")
        c.circle(p.x(0), p.y(0), p.d(od / 2 - t), THICK, "ln")
        for i in range(3):
            a = math.radians(90 + 120 * i)
            c.circle(p.x((od / 2 - 10) * math.cos(a)), p.y((od / 2 - 10) * math.sin(a)),
                     p.d(4.5), THICK, "ln")
        c.dim_h(p.x(-od / 2), p.x(od / 2), p.y(-od / 2 - 14), f"Ø{fmt(od)} ±2")
        c.leader(p.x((od / 2 - 10) * math.cos(math.radians(90))),
                 p.y((od / 2 - 10) * math.sin(math.radians(90))),
                 p.x(od / 2 + 18), p.y(od / 2 * 0.5), "조절봉 러그 3 개소",
                 lines=("M8 · 120° 등분",))
        c.view_title(14.0, 146.0, "평면", p.label)

        s = View(186.0, 210.0, 2.2)
        for sign in (1.0, -1.0):
            pts = s.pts([(sign * (od / 2 - t), 0), (sign * od / 2, 0),
                         (sign * od / 2, h), (sign * (od / 2 - t), h)])
            c.fill(pts, "var(--ink)", 0.82)
            c.poly(pts, THICK, "ln", close=True)
        c.poly(s.pts([(-od / 2, 0), (od / 2, 0)]), THIN, "ln", dash="2 1.6")
        c.centreline(s.x(0), s.y(-10), s.x(0), s.y(h + 14))
        c.dim_v(s.y(0), s.y(h), s.x(od / 2) + 10.0, fmt(h), left=False)
        c.text(s.x(0), s.y(-8.0), "타공 바닥판(G-02)은 별도 부품", T_DIM - 0.3, "middle", "tx2")
        c.view_title(150.0, 146.0, "단면", s.label)
        w = c.fcf(150.0, 236.0, "flat", "1.0", "")
        c.text(150.0 + w + 3.0, 239.6, "위어 상단 수평도", T_DIM - 0.3, "start", "tx2")
        for i, line in enumerate(wrap(
                "위어 상단이 기울면 한쪽으로만 넘쳐 부상층을 고르게 걷지 못한다. "
                "조절봉 3 개로 수평을 맞춘 뒤 고정한다.", 56)):
            c.text(150.0, 250.0 + i * 4.2, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "G-01", "스키머 링 (위어)", f"Ø{G.skimmer_od_mm:.0f} × H{G.skimmer_height_mm:.0f} × t2", "1:4",
        "스키머 링 부품도 — 전개, 평면, 단면과 위어 수평도",
        views,
        steps=[f"t2 판재를 전개 {math.pi * (G.skimmer_od_mm - 2):.1f} × {G.skimmer_height_mm:.0f} 로 절단.",
               f"롤벤딩으로 Ø{G.skimmer_od_mm:.0f} 원통 성형, 세로이음 1 개소 맞대기 용접.",
               "위어가 될 상단 모서리를 R1 로 다듬는다 — 날이 서면 넘치는 층이 끊긴다.",
               "조절봉 러그 3 개소 (120° 등분) 용접, M8 탭 가공.",
               "타공 바닥판(G-02)을 아래에 끼워 전둘레 필릿 용접.",
               "위어 상단 수평도 1.0 확인.",
               "산세 · 부동태화."],
        inspect=[("바깥 지름", f"Ø{G.skimmer_od_mm:.0f} ±2"),
                 ("높이", f"{G.skimmer_height_mm:.0f} ±1"),
                 ("위어 수평도", "1.0"), ("러그 분할", "120° ±2°"),
                 ("반출", f"동체 개구 Ø{G.tank_id_mm:.0f} 를 통과할 것")],
        extra=[f"바스켓 외경 Ø{G.skimmer_od_mm:.0f} 는 동체 개구 Ø{G.tank_id_mm:.0f} 보다 "
               f"편측 {G.skimmer_clearance_mm:.0f} mm 작다. 걷어낸 폴리머를 담은 채 통째로 "
               "들어올려 그대로 칭량·건조로 보낸다 (CHK-04)."],
    )


def sheet_g02() -> None:
    def views(c: Canvas) -> None:
        od, t, hd, pitch = G.skimmer_od_mm, 1.5, 2.0, 3.5
        open_ratio = 0.907 * (hd / pitch) ** 2
        v = View(74.0, 110.0, 2.2)
        cross_centre(c, v, od / 2 + 20)
        c.circle(v.x(0), v.y(0), v.d(od / 2), THICK, "ln")
        c.circle(v.x(0), v.y(0), v.d(od / 2 - 12), THIN, "cl", dash="5 2")
        # 대표 구간만 실제로 그린다 — 전부 그리면 6 천 개다
        rows = int(52 / (pitch * math.sqrt(3) / 2))
        for r in range(-rows, rows + 1):
            yy = r * pitch * math.sqrt(3) / 2
            offset = (pitch / 2) if r % 2 else 0.0
            for k in range(-9, 10):
                xx = k * pitch + offset
                if math.hypot(xx, yy) < 46:
                    c.circle(v.x(xx), v.y(yy), v.d(hd / 2), THIN, "ln")
        c.circle(v.x(0), v.y(0), v.d(48), THIN, "dl", dash="3 2")
        c.leader(v.x(34), v.y(34), v.x(od / 2 + 16), v.y(-od / 4),
                 "대표 구간만 작도", lines=("실제는 전면 타공",))
        c.dim_h(v.x(-od / 2), v.x(od / 2), v.y(-od / 2 - 14), f"Ø{fmt(od)} ±2")
        c.view_title(14.0, 30.0, "평면", v.label)

        d = View(180.0, 120.0, 0.16)
        for k in (-1, 0, 1):
            c.circle(d.x(k * pitch), d.y(0), d.d(hd / 2), THICK, "ln")
            c.circle(d.x(k * pitch + pitch / 2), d.y(pitch * math.sqrt(3) / 2), d.d(hd / 2),
                     THICK, "ln")
        c.dim_h(d.x(-pitch), d.x(0), d.y(-4.0), f"{pitch}")
        c.dim_v(d.y(0), d.y(pitch * math.sqrt(3) / 2), d.x(pitch + 1.0), "3.03", left=False)
        c.text(d.x(0), d.y(-8.0), "60° 엇갈림", T_DIM - 0.2, "middle", "tx2")
        c.view_title(150.0, 30.0, "타공 배열", "6:1")

        rows2 = [["항목", "값"]]
        rows2 += [["구멍", f"Ø{hd:.1f}"], ["피치", f"{pitch} (60° 엇갈림)"],
                  ["개공률", f"{open_ratio * 100:.1f} %  = 0.907 × (d/p)²"],
                  ["판 두께", f"t{t}"], ["구멍 수", "약 6,000 개"]]
        c.view_title(150.0, 150.0, "타공 사양")
        c.table(150.0, 154.0, [36.0, 62.0], rows2, row_h=5.2, size=T_DIM - 0.3,
                aligns=["start", "start"])
        for i, line in enumerate(wrap(
                "타공판은 완제품을 사 와 Ø300 으로 따내는 편이 싸다. 낱장 드릴링은 "
                "6 천 개를 뚫어야 한다.", 56)):
            c.text(150.0, 190.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                f"구멍 Ø{hd:.0f} 는 분리 대상 입자(31~75 µm)보다 한참 크다. 폴리머를 "
                "거르는 것이 아니라 **염수만 빠지게** 하는 것이 목적이다 — 걷어낸 층에서 "
                "물을 빼고 덩어리를 남긴다.", 56)):
            c.text(150.0, 210.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "G-02", "타공 바닥판", f"Ø{G.skimmer_od_mm:.0f} × t1.5 · Ø2 타공 개공률 30 %", "1:2.2",
        "타공 바닥판 부품도 — 평면, 타공 배열과 개공률 계산",
        views,
        steps=["Ø2 · 피치 3.5 · 60° 엇갈림 타공판(t1.5)을 구매.",
               f"Ø{G.skimmer_od_mm:.0f} 로 원형 절단 (레이저).",
               "절단면 버 제거 — 손이 닿는 부품이다.",
               "스키머 링(G-01) 아래에 끼워 전둘레 필릿 용접.",
               "산세 · 부동태화."],
        inspect=[("지름", f"Ø{G.skimmer_od_mm:.0f} ±2"),
                 ("개공률", "30 % ±3 (구매 사양)"),
                 ("절단면", "버 없을 것"), ("용접", "전둘레 연속 · 누설 무관")],
    )


def sheet_g04() -> None:
    def views(c: Canvas) -> None:
        v = View(66.0, 180.0, 0.7)
        c.poly(v.pts([(-60, 0), (-60, 70), (60, 70), (60, 0)]), THICK, "ln")
        c.arc(v.x(-46), v.y(56), v.d(14), 90, 180, THICK, "ln")
        c.arc(v.x(46), v.y(56), v.d(14), 0, 90, THICK, "ln")
        c.dim_h(v.x(-60), v.x(60), v.y(0) - 12.0, "120", ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(70), v.x(60) + 12.0, "70", left=False)
        c.text(v.x(0), v.y(82.0), f"Ø8 환봉 · 전개 약 340 · 굽힘 R14 × 2",
               T_DIM - 0.2, "middle", "tx2")
        c.leader(v.x(-60), v.y(6), v.x(-10), v.y(-26.0), "양 끝을 링 안쪽에 용접",
                 anchor="end")
        c.view_title(14.0, 30.0, "정면", v.label)
        e = View(180.0, 150.0, 0.16)
        c.circle(e.x(0), e.y(0), e.d(4), THICK, "ln")
        cross_centre(c, e, 8)
        c.dim_h(e.x(-4), e.x(4), e.y(-9), "Ø8")
        c.view_title(150.0, 110.0, "단면", "6:1")
        for i, line in enumerate(wrap(
                "바스켓을 액면에서 들어올릴 때 잡는 손잡이다. 폴리머와 염수를 담은 채로 "
                "드는 무게는 2 kg 이 안 되지만, 손이 미끄러지지 않게 굽힘부를 크게 잡았다.", 56)):
            c.text(150.0, 180.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "G-04", "인양 손잡이", "Ø8 환봉 굽힘 · 스키머 바스켓용", "1:0.7",
        "인양 손잡이 부품도 — 굽힘 형상과 단면",
        views,
        steps=["Ø8 환봉을 L340 으로 절단.",
               "R14 × 90° 굽힘 2 개소.",
               "양 끝을 스키머 링(G-01) 안쪽에 필릿 용접.",
               "용접부·절단면 버 제거 — 맨손으로 잡는 부품이다.",
               "산세 · 부동태화."],
        inspect=[("폭 · 높이", "120 × 70 ±3"), ("굽힘", "R14 ±2"),
                 ("용접", "육안 · 흔들림 없을 것"), ("표면", "날선 곳 없을 것")],
    )


# ==========================================================================
# H 프레임
# ==========================================================================
def sheet_h01() -> None:
    def views(c: Canvas) -> None:
        tube, wall = G.frame_tube_mm, G.frame_tube_thickness_mm
        v = View(28.0, 128.0, 4.0)
        L = G.frame_height_mm
        c.rect(v.x(0), v.y(tube), v.d(L), v.d(tube), THICK, "ln")
        c.dim_h(v.x(0), v.x(L), v.y(0) - 10.0, "길이 L (표 참조)", ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(tube), v.x(L) + 10.0, fmt(tube), left=False)
        c.text(v.x(L / 2), v.y(tube) - 8.0, "양단 직각 절단 · 버 제거",
               T_DIM - 0.2, "middle", "tx2")
        c.view_title(14.0, 30.0, "공통 형상", v.label)

        e = View(78.0, 216.0, 0.5)
        for sign in (1.0, -1.0):
            for sy in (1.0, -1.0):
                pass
        outer = [(-tube / 2, -tube / 2), (tube / 2, -tube / 2), (tube / 2, tube / 2),
                 (-tube / 2, tube / 2)]
        inner = [(x * (1 - 2 * wall / tube), y * (1 - 2 * wall / tube)) for x, y in outer]
        c.poly(e.pts(outer), THICK, "ln", close=True)
        c.poly(e.pts(inner), THICK, "ln", close=True)
        c.hatch(e.pts(outer), "hF", 45)
        c.fill(e.pts(inner), "var(--paper)")
        c.poly(e.pts(inner), THICK, "ln", close=True)
        cross_centre(c, e, tube / 2 + 10)
        c.dim_h(e.x(-tube / 2), e.x(tube / 2), e.y(-tube / 2 - 10), f"□{fmt(tube)}")
        c.dim_v(e.y(tube / 2 - wall), e.y(tube / 2), e.x(tube / 2) + 12.0, f"t{fmt(wall)}",
                left=False)
        c.view_title(14.0, 182.0, "단면", e.label)

        rows = [["번호", "부재", "길이", "수량", "위치 · 가공"]]
        for no in ("H-01", "H-02", "H-03", "H-04"):
            prt = PART[no]
            ln = {"H-01": G.frame_height_mm, "H-02": G.frame_width_mm - tube,
                  "H-03": G.frame_width_mm - 2 * tube, "H-04": G.frame_width_mm - tube}[no]
            where = {"H-01": "기둥 · 양단 직각", "H-02": "상·하부 둘레재 4+4",
                     "H-03": "상부 크로스레일", "H-04": "중간 보강재 · Z 중단"}[no]
            rows.append([no, prt.name, fmt(ln), str(prt.qty), where])
        total = sum(({"H-01": G.frame_height_mm, "H-02": G.frame_width_mm - tube,
                      "H-03": G.frame_width_mm - 2 * tube,
                      "H-04": G.frame_width_mm - tube}[n] * PART[n].qty)
                    for n in ("H-01", "H-02", "H-03", "H-04"))
        rows.append(["", "총 절단 길이", f"{total / 1000:.1f} m", "", "6 m 정척 2 본"])
        c.view_title(138.0, 30.0, "절단 목록")
        # 마지막 칸의 글이 오른쪽 기둥(x=258)을 넘지 않도록 폭을 배분한다.
        c.table(138.0, 34.0, [15.0, 30.0, 16.0, 11.0, 36.0], rows, row_h=5.4,
                size=T_DIM - 0.3, aligns=["middle", "start", "end", "middle", "start"])
        for i, line in enumerate(wrap(
                "네 부재 모두 같은 각관이고 길이만 다르다. 한 도면으로 묶는 편이 "
                "절단 지시가 명확하다.", 56)):
            c.text(138.0, 74.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                "절단면이 직각이 아니면 용접 후 프레임이 비틀려 커버 상면 수평도 0.5 를 "
                "레벨링 풋으로도 못 잡는다. 각도 절단기를 쓰고 단면을 확인한다.", 56)):
            c.text(138.0, 94.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "H-01", "프레임 각관 4 종", f"□{G.frame_tube_mm:.0f} × t{G.frame_tube_thickness_mm:.0f} · H-01~H-04 합본",
        "1:4", "프레임 각관 부품도 — 공통 단면과 절단 목록",
        views,
        steps=[f"□{G.frame_tube_mm:.0f} × {G.frame_tube_mm:.0f} × t{G.frame_tube_thickness_mm:.0f} 각관 6 m 정척 2 본 준비.",
               "절단 목록대로 각도 절단기로 직각 절단. 절단면 직각도 ±0.5°.",
               "절단면 버 제거, 모서리 가볍게 다듬기.",
               "조립 지그에 세워 기둥 4 본 → 하부 둘레재 → 상부 둘레재 → 크로스레일 "
               "→ 중간 보강재 순으로 가용접.",
               "대각 길이를 재어 직각을 확인한 뒤 본용접 (필릿 a3 전둘레).",
               "용접 변형 확인 — 상부 레일 4 점의 높이차 1.0 이내.",
               "산세 · 부동태화."],
        inspect=[("절단 길이", "±1.0"), ("절단면 직각도", "±0.5°"),
                 ("조립 대각차", "≤ 2.0"), ("상부 레일 높이차", "≤ 1.0"),
                 ("용접", "필릿 a3 전둘레 · 육안")],
        extra=[f"프레임 높이 {G.frame_height_mm:.0f} 은 임의값이 아니다. 콘 배출면이 바닥 "
               f"+{G.discharge_elevation_mm:.0f} 에 오고, 2 in 밸브·클램프가 150 을 먹은 뒤 "
               f"아래에 {G.discharge_clearance_mm:.0f} mm 가 남도록 역산했다 (CHK-09)."],
    )


def sheet_h06() -> None:
    def views(c: Canvas) -> None:
        s, t, hole = 100.0, 6.0, 14.0
        v = View(92.0, 128.0, 0.7)
        c.rect(v.x(-s / 2), v.y(s / 2), v.d(s), v.d(s), THICK, "ln")
        c.circle(v.x(0), v.y(0), v.d(hole / 2), THICK, "ln")
        cross_centre(c, v, s / 2 + 12)
        c.dim_h(v.x(-s / 2), v.x(s / 2), v.y(-s / 2 - 12), fmt(s))
        c.dim_v(v.y(-s / 2), v.y(s / 2), v.x(-s / 2) - 3.0, fmt(s), ext_from=v.x(-s / 2))
        c.leader(v.x(hole / 2), v.y(0), v.x(s / 2 + 22), v.y(-s / 4), f"Ø{fmt(hole)}",
                 lines=("M12 앵커 통과",))
        c.view_title(14.0, 30.0, "평면", v.label)
        e = View(92.0, 220.0, 0.7)
        plate_edge(c, e, -s / 2, s / 2, 0, -t, "hH6")
        c.dim_v(e.y(0), e.y(t), e.x(s / 2) + 10.0, f"t{fmt(t)}", left=False)
        c.view_title(14.0, 194.0, "두께", e.label)
        for i, line in enumerate(wrap(
                "기둥(H-01) 아래 끝에 용접해 바닥과 닿는 면을 만든다. 레벨링 풋(H-05)의 "
                "M16 은 이 판이 아니라 기둥 안에 박은 너트에 물린다.", 100)):
            c.text(14.0, 252.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                f"운전 중량 {212:.0f} kg 을 다리 4 개가 나눠 받는다 — 판당 약 54 kg. "
                "앵커는 정하중이 아니라 배출 호스를 당기거나 스키머를 들어올릴 때의 "
                "수평 하중 때문에 권한다 (CHK-13).", 100)):
            c.text(14.0, 268.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "H-06", "베이스 플레이트", "100 × 100 × t6 · Ø14 앵커홀 · 4 개", "1:0.7",
        "베이스 플레이트 부품도 — 평면과 두께, 앵커 구멍",
        views,
        steps=["t6 판재를 100 × 100 으로 절단 (4 개).",
               "중앙에 Ø14 앵커 구멍 드릴, 양면 버 제거.",
               "모서리 R3.",
               "기둥(H-01) 아래 끝에 전둘레 필릿 a4 용접.",
               "4 판의 높이차를 1.0 이내로 확인 (지그 위에서).",
               "산세 · 부동태화."],
        inspect=[("외형", "100 ±1"), ("구멍", "Ø14 ±0.3 · 중앙 ±1"),
                 ("두께", "t6 (소재 그대로)"), ("4 판 높이차", "≤ 1.0")],
    )


def sheet_h07() -> None:
    def views(c: Canvas) -> None:
        w, h, t, hole = 80.0, 60.0, 6.0, 14.0
        v = View(52.0, 128.0, 0.7)
        c.rect(v.x(0), v.y(h), v.d(w), v.d(h), THICK, "ln")
        c.circle(v.x(w / 2), v.y(h - 22), v.d(hole / 2), THICK, "ln")
        c.centreline(v.x(w / 2) - v.d(20), v.y(h - 22), v.x(w / 2) + v.d(20), v.y(h - 22))
        c.centreline(v.x(w / 2), v.y(h - 22) - v.d(20), v.x(w / 2), v.y(h - 22) + v.d(20))
        c.dim_h(v.x(0), v.x(w), v.y(0) - 10.0, fmt(w), ext_from=v.y(0))
        c.dim_v(v.y(0), v.y(h), v.x(0) - 10.0, fmt(h), ext_from=v.x(0))
        c.dim_v(v.y(h - 22), v.y(h), v.x(w) + 10.0, "22", left=False)
        c.leader(v.x(w / 2 + hole / 2), v.y(h - 22), v.x(w + 26), v.y(h * 0.2),
                 f"Ø{fmt(hole)}", lines=("M12 · 지지링(A-06)과 체결",))
        c.view_title(14.0, 30.0, "평면", v.label)
        e = View(52.0, 214.0, 0.7)
        plate_edge(c, e, 0, w, 0, -t, "hH7")
        c.dim_v(e.y(0), e.y(t), e.x(w) + 10.0, f"t{fmt(t)}", left=False)
        c.view_title(14.0, 188.0, "두께", e.label)
        for i, line in enumerate(wrap(
                "상부 크로스레일(H-03) 위에 용접해 지지링(A-06)을 볼트로 받는다. "
                "구멍 위치가 지지링과 어긋나면 용기가 안 앉으므로 같은 지그로 뚫는다.", 100)):
            c.text(14.0, 244.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")
        for i, line in enumerate(wrap(
                "크로스레일이 필요한 이유는 지지링 Ø480 이 프레임 둘레재에 5 mm 밖에 "
                "걸리지 않기 때문이다. 둘레재만으로는 받을 면이 없다.", 100)):
            c.text(14.0, 262.0 + i * 4.4, line, T_DIM - 0.2, "start", "tx2")

    simple_part_sheet(
        "H-07", "지지 브래킷", "80 × 60 × t6 · M12 · 4 개", "1:0.7",
        "지지 브래킷 부품도 — 평면과 두께, 지지링 체결 구멍",
        views,
        steps=["t6 판재를 80 × 60 으로 절단 (4 개).",
               "Ø14 구멍 드릴 — 지지링(A-06)과 **같은 지그**로 뚫는다.",
               "모서리 R3, 버 제거.",
               "상부 크로스레일(H-03) 위 X=±180 · Y=±150 에 필릿 a4 용접.",
               "4 개 브래킷 윗면의 높이차 0.5 이내 확인.",
               "산세 · 부동태화."],
        inspect=[("외형", "±1.0"), ("구멍 위치", "±0.5 · 지지링과 일치"),
                 ("4 개 높이차", "≤ 0.5"), ("용접", "필릿 a4 · 육안")],
    )


# ==========================================================================
# 표지 · 규격품 명세
# ==========================================================================
def sheet_part_no(sheet: Canvas) -> str | None:
    """도면번호에서 부품번호를 되읽는다. 부품도가 아니면 None."""
    raw = sheet.number.replace("MP50-P-", "")
    no = raw[:1] + "-" + raw[1:]
    return no if no in PART else None


def cover_sheet() -> Canvas:
    """부품도 목록과 전 도면에 걸리는 공통 지시. 맨 앞에 놓는다."""
    part_sheets = sum(1 for x in SHEETS if sheet_part_no(x))
    c = Canvas("MP50-P-000", "부품도 목록 · 공통 지시",
               f"제작품 {len(FABRICATED)} 종 · 부품도 {part_sheets} 매 — 이 지시는 전 도면에 걸린다",
               "-", "부품도 목록과 전 도면 공통 지시 — 재질, 일반공차, 표면, 용접, 모서리, 후처리")
    c.frame_and_title(REV, DATE, f"1/{TOTAL_SHEETS}")
    c.head([("제작품", f"{len(FABRICATED)} 종"), ("부품도", f"{part_sheets} 매"),
            ("일반공차", GENERAL_TOLERANCE), ("용접", "TIG · 백퍼지"),
            ("후처리", "산세 · 부동태화")])

    rows = [["도면번호", "부품", "품명", "재질", "수량"]]
    for sheet in SHEETS:
        no = sheet_part_no(sheet)
        if no is None:            # 표지·명세는 목록에 넣지 않는다
            continue
        prt = PART[no]
        also = SHARED.get(no, ())
        qty = prt.qty + sum(PART[o].qty for o in also)
        label = no + (" · " + " · ".join(also) if also else "")
        rows.append([sheet.number, label, sheet.title, prt.material, str(qty)])
    c.view_title(14.0, 30.0, "부품도 목록")
    c.table(14.0, 34.0, [32.0, 34.0, 52.0, 24.0, 16.0], rows, row_h=5.4, size=T_DIM - 0.2,
            aligns=["start", "start", "start", "start", "middle"])

    x = 180.0
    c.view_title(x, 30.0, "공통 지시 — 전 도면 적용")
    notes = [
        ("일반공차", f"기입 없는 치수는 {GENERAL_TOLERANCE} (선형 m 급 · 모서리 K 급)."),
        ("재질", "SUS304 는 동체·커버·프레임, SUS316L 은 축·임펠러·분산링·배플. "
                 "염수에 잠기고 마찰이 있는 것은 316L 로 올렸다."),
        ("소재", "각 도면의 '소재' 란은 **사 오는 형태**다. 완성 치수가 아니라 "
                 "판재·봉재·관재를 어떤 크기로 주문하는지를 적었다."),
        ("용접", "TIG (GTAW) · 316L 용가재. 맞대기는 전면 이면 아르곤 백퍼지. "
                 "백퍼지를 빼면 이면에 산화막이 남고 그 자리가 염수에서 먼저 공식이 된다."),
        ("내면", "액체에 닿는 면은 Ra ≤ 0.8 까지 버프하고 용접부를 평활 연삭한다. "
                 "31~75 µm 분말이 걸릴 턱을 남기지 않는다."),
        ("모서리", "액체에 닿는 모든 모서리 R2 이상. 날선 모서리는 부동태 피막이 "
                   "얇게 붙어 염수에서 먼저 뜯긴다."),
        ("크레비스", "겹침 이음·부분 용접 금지. 틈이 생기면 배치마다 분말이 끼고 "
                     "그 자리에서 틈부식이 시작된다."),
        ("후처리", "전 부품 산세 후 부동태화. 페록실 시험에서 청색 반응이 없을 것."),
        ("표시", "각 부품에 부품번호를 각인 또는 전해 마킹. 스탬핑은 금지 "
                 "— 타흔이 응력집중이 된다."),
    ]
    y = 36.0
    for head, body in notes:
        c.text(x, y, head, T_NOTE, "start", "tx", weight="600")
        y += 4.2
        for line in wrap(body, 76):
            c.text(x + 4.0, y, line, T_DIM - 0.2, "start", "tx2")
            y += 3.9
        y += 2.2

    c.view_title(x, y + 4.0, "조달 구분")
    counts: dict[str, int] = {}
    for a in ASSEMBLIES:
        for prt in a.parts:
            counts[prt.made] = counts.get(prt.made, 0) + 1
    proc = [["구분", "수", "뜻"]]
    proc += [["제작", str(counts.get("제작", 0)), "우리 도면이 있어야 만들 수 있다 — 부품도가 붙는다"],
             ["규격", str(counts.get("규격", 0)), "표준 규격품. 규격을 적어 주문한다 (볼트·키·O-링)"],
             ["구매", str(counts.get("구매", 0)), "벤더 공급품. 사양으로 주문한다 (모터·밸브·센서)"],
             ["가공", str(counts.get("가공", 0)), "별도 부품이 아니라 다른 부품에 넣는 가공 특징"]]
    c.table(x, y + 8.0, [18.0, 12.0, 152.0], proc, row_h=5.4, size=T_DIM - 0.2,
            aligns=["start", "middle", "start"])
    c.text(x, y + 8.0 + len(proc) * 5.4 + 5.0,
           "규격품·구매품 명세는 마지막 장 (MP50-P-999).", T_DIM - 0.2, "start", "tx2")
    return c


def catalogue_sheet() -> Canvas:
    """규격품·구매품 명세 — 도면이 아니라 규격으로 조달하는 것들."""
    c = Canvas("MP50-P-999", "규격품 · 구매품 명세", "도면이 아니라 규격·사양으로 주문한다",
               "-", "규격품과 구매품 명세 — 볼트류 규격과 벤더 공급품 사양")
    SHEETS.append(c)
    c.frame_and_title(REV, DATE, f"{TOTAL_SHEETS}/{TOTAL_SHEETS}")
    std = [p for a in ASSEMBLIES for p in a.parts if p.made == "규격"]
    buy = [p for a in ASSEMBLIES for p in a.parts if p.made == "구매"]
    mach = [p for a in ASSEMBLIES for p in a.parts if p.made == "가공"]
    c.head([("규격품", f"{len(std)} 종"), ("구매품", f"{len(buy)} 종"),
            ("가공 특징", f"{len(mach)} 종"), ("체결 재질", "SUS304 A2-70")])

    rows = [["번호", "품명", "주문 규격", "수량", "상위"]]
    for p in std:
        rows.append([p.no, p.name, p.stock, str(p.qty), PART_OF[p.no].code])
    c.view_title(14.0, 30.0, "규격품 — 규격을 적어 주문한다")
    end = c.table(14.0, 34.0, [16.0, 44.0, 82.0, 16.0, 14.0], rows, row_h=5.4,
                  size=T_DIM - 0.2, aligns=["start", "start", "start", "middle", "middle"])
    c.text(14.0, end + 5.0, "볼트·너트·와셔는 전부 SUS304 A2-70. 조임 토크는 MP50-K.",
           T_DIM - 0.2, "start", "tx2")

    rows2 = [["번호", "품명", "사양", "수량", "상위"]]
    for p in buy:
        rows2.append([p.no, p.name, p.spec, str(p.qty), PART_OF[p.no].code])
    c.view_title(14.0, end + 14.0, "구매품 — 사양으로 주문한다")
    end2 = c.table(14.0, end + 18.0, [16.0, 44.0, 110.0, 16.0, 14.0], rows2, row_h=5.4,
                   size=T_DIM - 0.2, aligns=["start", "start", "start", "middle", "middle"])

    x = 214.0
    rows3 = [["번호", "가공 특징", "어디에"]]
    for p in mach:
        rows3.append([p.no, p.name, p.stock])
    c.view_title(x, 30.0, "가공 특징 — 별도 부품이 아니다")
    e3 = c.table(x, 34.0, [16.0, 40.0, 124.0], rows3, row_h=5.4, size=T_DIM - 0.2,
                 aligns=["start", "start", "start"])

    c.view_title(x, e3 + 10.0, "발주 전 확인")
    y = e3 + 15.0
    for i, line in enumerate([
            "C-01~C-04 는 교반기 벤더 일체 견적이다. 개별로 사면 인터페이스가 맞지 않는다.",
            "C-03 축 씰은 CRITICAL HOLD — 일반 싱글 씰을 확정하지 말고, 고형분 wt% 를 "
            "제시한 뒤 고형분용 더블 카트리지로 RFQ 한다.",
            "I-01 과 I-02 는 둘 다 산다. 1.5 in / 2 in 배출시험을 한 대에서 돌리기 "
            "위해서다 (C3).",
            "J-01 은 pH 가 아니라 전도도(염도)다. NaCl 은 pH 를 움직이지 않으므로 "
            "pH 센서는 이 장치에서 아무것도 알려주지 않는다 (C7).",
            "J-04 사이트글라스는 위생 규격품을 사 온다 — 유리 가공은 하지 않는다.",
            "H-05 레벨링 풋은 방진 패드 일체형으로. 커버 상면 수평도 0.5 를 여기서 잡는다."]):
        for line2 in wrap("· " + line, 74):
            c.text(x, y, line2, T_DIM - 0.2, "start", "tx2")
            y += 3.9
        y += 1.4
    return c


# ==========================================================================
# HTML
# ==========================================================================
def build_html() -> str:
    toc = "".join(
        f'<li><a href="#{s.number}"><code>{s.number}</code>{esc(s.title)}</a></li>'
        for s in SHEETS)
    figures = "".join(
        f'<figure class="sheet" id="{s.number}">{s.render()}'
        f"<figcaption><b>{esc(s.number)} · {esc(s.title)}</b> — {esc(s.subtitle)}</figcaption>"
        f"</figure>" for s in SHEETS)
    made = {}
    for a in ASSEMBLIES:
        for p in a.parts:
            made[p.made] = made.get(p.made, 0) + 1
    header = f"""<header class="doc">
  <h1>MP-50 부품별 상세도면</h1>
  <p>아세이도(MP50-A~K)가 어디에 어떻게 붙는가를 보여준다면, 부품도는
     <b>그 부품 하나를 어떻게 깎고 말고 뚫는가</b>를 보여준다. 가공자는 아세이도를
     보지 않고 부품도 한 장만 들고 작업대에 서므로, 각 장은 그 부품만으로
     완결돼 있다 — 소재 규격, 완성 치수, 기하공차, 표면, 가공 순서, 검사.</p>
  <div class="meta">
    <span>Rev <b>{REV}</b></span><span>작성 <b>{DATE}</b></span>
    <span>부품도 <b>{len(SHEETS)}매</b></span>
    <span>제작품 <b>{made.get('제작', 0)}종</b></span>
    <span>규격품 <b>{made.get('규격', 0)}종</b></span>
    <span>구매품 <b>{made.get('구매', 0)}종</b></span>
    <span>일반공차 <b>{GENERAL_TOLERANCE}</b></span>
  </div>
</header>
<ul class="toc">{toc}</ul>"""
    prose = f"""
<section class="prose">
  <h2>부품도가 붙는 것과 붙지 않는 것</h2>
  <p>부품 {sum(made.values())}종 가운데 부품도가 붙는 것은 <b>제작품 {made.get('제작', 0)}종</b>뿐이다.
     볼트·키·O-링은 규격을 적어 주문하고, 모터·밸브·센서는 벤더가 만든다.
     그런 것에 부품도를 그리면 현장에서 "이걸 깎으라는 말인가" 하는 혼선만 생긴다.
     구분은 <code>components.PROCUREMENT</code> 이 정하고, 규격품·구매품은
     마지막 장(MP50-P-999)에 명세로 실었다.</p>

  <h2>소물은 합본한다</h2>
  <p>25 × 6 짜리 탭 하나에 A3 한 장을 쓰면 도면 뭉치만 두꺼워지고 가공자가 장을
     더 넘긴다. 같은 판재에서 같은 공정으로 나오는 소물은 한 장에 묶었다 —
     거싯 2종(A-07 · B-03), 소물 2종(E-02 · F-04), 프레임 각관 4종(H-01~H-04),
     그리고 같은 부품인 임펠러 2개(D-02 · D-03).</p>

  <h2>치수는 코드에서 나온다</h2>
  <p>도면에 박힌 숫자는 <code>mp50_separator</code> 의 확정 기하에서 계산된다.
     전개 길이 {G.shell_development_length_mm:.2f}, 원뿔 모선 {G.cone_slant_length_mm:.2f},
     임펠러 팁 간극 {G.impeller_tip_clearance_mm:.0f} — 손으로 적은 값이 없으므로
     기준치수를 고치면 전 부품도가 함께 움직인다. 관련 도면:
     <a href="mp50-fabrication-drawings.html">아세이별 제작도면 15매</a> ·
     <a href="mp50-3d.html">3D 분해 · 컷어웨이 콘솔</a>.</p>
</section>"""
    return document("MP-50 부품별 상세도면",
                    f"MP-50 염수 밀도분리 파일럿 장치의 부품별 상세도면 {len(SHEETS)}매 — "
                    "제작품마다 소재 규격, 완성 치수, 기하공차, 가공 순서, 검사 항목.",
                    header, figures + prose)


def main() -> None:
    build_all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_html(), encoding="utf-8")
    print(f"{OUT} — {len(SHEETS)} 매, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
