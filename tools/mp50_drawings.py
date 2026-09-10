#!/usr/bin/env python3
"""MP-50 아세이별 제작도면 생성 — ``docs/drawings/mp50-fabrication-drawings.html``.

도면을 손으로 그리지 않고 ``mp50_separator`` 의 확정 기하에서 뽑는다. 도면 15 매에
같은 치수가 수십 번 반복되는데, 손으로 적으면 기준치수를 하나 고칠 때마다 그중
몇 개는 옛 값으로 남는다. 제작 현장에서 그 하나가 재작업이 된다.

    python tools/mp50_drawings.py

시트 구성 — 000 기준 · 100 전체조립 · A~K 아세이별 · W 용접검사.
"""

from __future__ import annotations

import datetime as _dt
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from _mp50_draft import (  # noqa: E402
    FRAME, GAP, HIDDEN_W, T_DIM, T_LABEL, T_NOTE, T_TITLE, T_VIEW, THICK, THIN,
    Canvas, View, esc, fmt, text_width,
)

from mp50_separator import ASSEMBLIES, CONFLICTS, GEOMETRY as G, run_checks  # noqa: E402
from mp50_separator.components import BY_CODE, dry_mass_kg, wet_mass_kg  # noqa: E402
from mp50_separator.geometry import COVER_NOZZLES, NOZZLES  # noqa: E402

REV = "R1"
DATE = "2026-09-10"
OUT = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "mp50-fabrication-drawings.html"

CHECKS = run_checks()
SHEETS: list[Canvas] = []


def sheet(number: str, title: str, subtitle: str, scale: str, aria: str) -> Canvas:
    c = Canvas(number, title, subtitle, scale, aria)
    SHEETS.append(c)
    return c


# ==========================================================================
# 공용 형상 — 여러 시트가 같은 윤곽을 그린다
# ==========================================================================
def cone_wall_offset() -> float:
    """콘 벽 두께의 **수평** 성분. 경사면이라 판 두께보다 크다."""
    return G.cone_thickness_mm / math.cos(math.radians(G.cone_half_angle_deg))


def vessel_inner(sign: float = 1.0) -> list[tuple[float, float]]:
    """용기 안쪽 윤곽 (중심선 → 바깥, 아래에서 위로)."""
    return [
        (sign * G.cone_outlet_id_mm / 2, G.cone_outlet_z),
        (sign * G.tank_id_mm / 2, G.shell_bottom_z),
        (sign * G.tank_id_mm / 2, G.shell_top_z),
    ]


def vessel_outer(sign: float = 1.0) -> list[tuple[float, float]]:
    """용기 바깥 윤곽 (위에서 아래로) — 안쪽과 이으면 단면 폴리곤이 된다."""
    dx = cone_wall_offset()
    return [
        (sign * (G.tank_id_mm / 2 + G.shell_thickness_mm), G.shell_top_z),
        (sign * (G.tank_id_mm / 2 + G.shell_thickness_mm), G.shell_bottom_z),
        (sign * (G.cone_outlet_id_mm / 2 + dx), G.cone_outlet_z),
    ]


def vessel_silhouette() -> list[tuple[float, float]]:
    """용기 바깥 윤곽 한 바퀴 — 뒤에 있는 프레임을 가리는 데 쓴다."""
    dx = cone_wall_offset()
    r = G.tank_id_mm / 2 + G.shell_thickness_mm
    ro = G.cone_outlet_id_mm / 2 + dx
    return [(-ro, G.cone_outlet_z), (-r, G.shell_bottom_z), (-r, G.cover_top_z),
            (r, G.cover_top_z), (r, G.shell_bottom_z), (ro, G.cone_outlet_z)]


def mask(c: Canvas, v: View, pts: list[tuple[float, float]]) -> None:
    """용지색으로 채워 뒤의 선을 지운다 — 정면도의 은선 처리."""
    c.fill(v.pts(pts), "var(--paper)")


def section_fill(c: Canvas, v: View, pts: list[tuple[float, float]], thickness_mm: float,
                 ident: str = "hA", angle: int = 45) -> None:
    """단면 채우기 — 판 두께가 종이 위에서 1.2 mm 를 넘어야 해칭이 보인다.

    Ø400 동체의 t3 은 1:5 에서 0.6 mm 라 해칭선이 한 줄도 들어가지 않는다.
    그런 얇은 벽은 실제 제도에서도 해칭하지 않고 까맣게 칠한다.
    """
    if v.d(thickness_mm) >= 1.2:
        c.hatch(pts, ident, angle)
    else:
        c.fill(pts, "var(--ink)", 0.82)
    c.poly(pts, THICK, "ln", close=True)


def draw_vessel_section(c: Canvas, v: View, hatch: bool = True) -> None:
    """용기 단면 — 동체 + 콘 벽을 양쪽에 그린다."""
    for sign in (1.0, -1.0):
        pts = v.pts(vessel_inner(sign) + vessel_outer(sign))
        if hatch:
            section_fill(c, v, pts, G.shell_thickness_mm, "hA", 45 if sign > 0 else -45)
        else:
            c.poly(pts, THICK, "ln", close=True)


def draw_flange_and_cover(c: Canvas, v: View, cover: bool = True) -> None:
    """상단 플랜지 · 커버 단면."""
    fz0, fz1 = G.shell_top_z - G.top_flange_thickness_mm, G.shell_top_z
    for sign in (1.0, -1.0):
        r0 = sign * (G.tank_id_mm / 2 + G.shell_thickness_mm)
        r1 = sign * G.top_flange_od_mm / 2
        section_fill(c, v, v.pts([(r0, fz0), (r1, fz0), (r1, fz1), (r0, fz1)]),
                     G.top_flange_thickness_mm, "hA", 45 if sign > 0 else -45)
    if not cover:
        return
    cz0, cz1 = G.shell_top_z, G.cover_top_z
    r = G.top_flange_od_mm / 2
    section_fill(c, v, v.pts([(-r, cz0), (r, cz0), (r, cz1), (-r, cz1)]),
                 G.cover_thickness_mm, "hB", -45)
    hub = G.cover_hub_od_mm / 2
    hz = cz1 + G.cover_hub_thickness_mm
    for sign in (1.0, -1.0):
        section_fill(c, v, v.pts([(sign * 30, cz1), (sign * hub, cz1), (sign * hub, hz), (sign * 30, hz)]),
                     G.cover_hub_thickness_mm, "hB", -45)


def draw_internals(c: Canvas, v: View, phantom: bool = False) -> None:
    """내부물 — 임펠러 · 배플 · 분산링 · 스키머 · 축."""
    w = HIDDEN_W if phantom else THICK
    dash = "2.4 1.2" if phantom else ""
    # 축
    c.poly(v.pts([(-G.shaft_od_mm / 2, 395), (-G.shaft_od_mm / 2, 1140)]), w, "ln", dash=dash)
    c.poly(v.pts([(G.shaft_od_mm / 2, 395), (G.shaft_od_mm / 2, 1140)]), w, "ln", dash=dash)
    # 임펠러 (45° 경사 블레이드를 옆에서 본 모습)
    proj = G.impeller_blade_width_mm * math.sin(math.radians(G.impeller_pitch_deg)) / 2
    for z in (G.lower_impeller_z, G.upper_impeller_z):
        for sign in (1.0, -1.0):
            r0, r1 = sign * G.impeller_hub_od_mm / 2, sign * G.impeller_od_mm / 2
            c.poly(v.pts([(r0, z + proj), (r1, z - proj)]), w, "ln", dash=dash)
            c.poly(v.pts([(r0, z + proj), (r0, z - proj), (r1, z - proj)]), THIN, "ln", dash=dash)
        hub = v.pts([(-G.impeller_hub_od_mm / 2, z - G.impeller_hub_length_mm / 2),
                     (G.impeller_hub_od_mm / 2, z - G.impeller_hub_length_mm / 2),
                     (G.impeller_hub_od_mm / 2, z + G.impeller_hub_length_mm / 2),
                     (-G.impeller_hub_od_mm / 2, z + G.impeller_hub_length_mm / 2)])
        c.poly(hub, w, "ln", close=True, dash=dash)
    # 배플 (앞뒤 2 매만 단면에 보인다)
    for sign in (1.0, -1.0):
        r1 = sign * (G.tank_id_mm / 2 - G.baffle_wall_gap_mm)
        r0 = sign * G.baffle_inner_radius_mm
        c.poly(v.pts([(r0, G.baffle_bottom_z), (r1, G.baffle_bottom_z),
                      (r1, G.baffle_top_z), (r0, G.baffle_top_z)]), w, "ln", close=True, dash=dash)
    # 분산링 단면 (좌우 두 동강)
    rr = G.sparger_tube_od_mm / 2
    for sign in (1.0, -1.0):
        cx, cz = sign * G.sparger_pcd_mm / 2, G.sparger_z
        c.circle(v.x(cx), v.y(cz), v.d(rr), w, "ln")
    # 스키머 바스켓
    sz = G.skimmer_z
    for sign in (1.0, -1.0):
        r = sign * G.skimmer_od_mm / 2
        c.poly(v.pts([(r, sz - G.skimmer_height_mm), (r, sz)]), w, "ln", dash=dash)
    c.poly(v.pts([(-G.skimmer_od_mm / 2, sz - G.skimmer_height_mm),
                  (G.skimmer_od_mm / 2, sz - G.skimmer_height_mm)]), THIN, "ln", dash="1.4 1.4")


def inner_r_at(z: float) -> float:
    """표고 z 의 용기 **안쪽** 반지름."""
    if z <= G.shell_bottom_z:
        return max(G.cone_outlet_id_mm / 2, G.cone_id_at(max(z, G.cone_outlet_z)) / 2)
    return G.tank_id_mm / 2


def outer_r_at(z: float) -> float:
    """표고 z 의 용기 **바깥** 반지름 — 지시선을 윤곽에 물리는 데 쓴다."""
    if z >= G.shell_top_z - G.top_flange_thickness_mm:
        return G.top_flange_od_mm / 2
    if abs(z - G.support_ring_z) < G.support_ring_thickness_mm:
        return G.support_ring_od_mm / 2
    if z <= G.shell_bottom_z:
        return inner_r_at(z) + cone_wall_offset()
    return G.tank_id_mm / 2 + G.shell_thickness_mm


def draw_liquid(c: Canvas, v: View) -> None:
    """운전 액면과 50 L 하한 — 채움은 용기 안쪽 윤곽을 따른다."""
    z = G.operating_level_z
    body = [(-G.cone_outlet_id_mm / 2, G.cone_outlet_z), (-G.tank_id_mm / 2, G.shell_bottom_z),
            (-G.tank_id_mm / 2, z), (G.tank_id_mm / 2, z),
            (G.tank_id_mm / 2, G.shell_bottom_z), (G.cone_outlet_id_mm / 2, G.cone_outlet_z)]
    c.fill(v.pts(body), "var(--brine)", 0.10)
    for lvl, lab in ((G.operating_level_z, f"WL {G.operating_volume_l:.1f} L"),
                     (G.nominal_level_z, f"WL-MIN {G.nominal_charge_l:.0f} L")):
        r = inner_r_at(lvl)
        c.poly(v.pts([(-r, lvl), (r, lvl)]), THIN, "wl", dash="5 1.6 1.6 1.6")
        c.text(v.x(r) - 1.0, v.y(lvl) - 1.2, lab, T_DIM - 0.3, "end", "wl-tx")


def nozzle_side(c: Canvas, v: View, n, sign: float, w: float = THICK) -> None:
    """노즐을 단면 옆모습으로 — 방위각과 무관하게 좌우로 뻗어 그린다."""
    r_shell = G.tank_id_mm / 2 + G.shell_thickness_mm
    r_end = r_shell + n.projection_mm
    half = n.tube_od_mm / 2 + 2.0
    pts = v.pts([(sign * r_shell, n.z_mm - half), (sign * r_end, n.z_mm - half),
                 (sign * r_end, n.z_mm + half), (sign * r_shell, n.z_mm + half)])
    c.poly(pts, w, "ln", close=True)
    fr = half + 5.0
    c.poly(v.pts([(sign * r_end, n.z_mm - fr), (sign * (r_end + 12), n.z_mm - fr),
                  (sign * (r_end + 12), n.z_mm + fr), (sign * r_end, n.z_mm + fr)]),
           w, "ln", close=True)
    c.centreline(v.x(sign * (r_shell - 14)), v.y(n.z_mm), v.x(sign * (r_end + 18)), v.y(n.z_mm))


# ==========================================================================
# 000 — 기준좌표 · 공차 · 충돌 레지스터
# ==========================================================================
def sheet_000() -> None:
    c = sheet("MP50-000", "기준좌표 · 공차 · 도면목록",
              "Z 원점은 원뿔 가상 정점 · θ 원점은 N1",
              "1:5", "MP-50 기준좌표계와 주요 표고, 도면 목록, 조립 공차, 원본 도면 간 치수 충돌 해결 레지스터")
    c.frame_and_title(REV, DATE, "1/15")
    c.head([("전용적", f"{G.total_volume_l:.2f} L"),
            ("운전 장입", f"{G.operating_volume_l:.1f} L @ Z{G.operating_level_z:.0f}"),
            ("건조질량", f"{dry_mass_kg():.0f} kg"),
            ("운전질량", f"{wet_mass_kg():.0f} kg"),
            ("전체높이", f"{G.overall_height_mm:.0f} (구동부 제외)")])

    v = View(48.0, 256.0, 5.0)
    c.centreline(v.x(0), v.y(-20), v.x(0), v.y(1000))
    draw_vessel_section(c, v, hatch=False)
    draw_flange_and_cover(c, v)
    draw_internals(c, v, phantom=True)
    draw_liquid(c, v)
    # 가상 정점
    c.poly(v.pts([(-G.cone_outlet_id_mm / 2, G.cone_outlet_z), (0, 0),
                  (G.cone_outlet_id_mm / 2, G.cone_outlet_z)]), THIN, "dl", dash="3 1.5")
    c.circle(v.x(0), v.y(0), 1.0, THIN, "ln", fill="var(--paper)")
    c.text(v.x(0), v.y(0) + 5.0, "Z 0 — 가상 정점", T_DIM - 0.3, "middle", "tx2")
    c.view_title(18.0, 30.0, "기준 표고", v.label)

    ladder = [
        (G.cover_top_z, "커버 상면"), (G.shell_top_z, "동체 상단 · 플랜지 면"),
        (760.0, "N1 급광"), (735.0, "N2 부상물"), (G.skimmer_z, "스키머 위어"),
        (G.operating_level_z, f"운전 액면 · {G.operating_volume_l:.1f} L"),
        (G.baffle_top_z, "배플 상단"), (G.nominal_level_z, f"하한 액면 · {G.nominal_charge_l:.0f} L"),
        (G.upper_impeller_z, "상부 임펠러"), (560.0, "N4C 시료"), (520.0, "N3 급기"),
        (G.lower_impeller_z, "하부 임펠러"), (G.support_ring_z, "지지링 · N4A"),
        (G.baffle_bottom_z, "배플 하단"), (G.shell_bottom_z, "동체 하단 (콘 접선)"),
        (G.sparger_z, "급기 분산링"), (G.cone_outlet_z, "콘 배출면"),
    ]
    lx = 106.0
    for i, (z, name) in enumerate(ladder):
        ty = 34.0 + i * 12.9
        ax = v.x(outer_r_at(z))
        c.poly([(ax, v.y(z)), (lx - 3.0, ty), (lx, ty)], THIN, "dl")
        c.circle(ax, v.y(z), 0.5, 0, "fill-ink", fill="currentColor")
        c.text(lx + 1.2, ty - 0.8, f"Z {fmt(z, 1)}", T_NOTE, "start", "tx", weight="600", mono=True)
        c.text(lx + 1.2, ty + 3.1, name, T_DIM - 0.3, "start", "tx2")

    # 도면 목록
    rows = [["도면번호", "내용", "축척"]]
    rows.append(["MP50-000", "기준좌표 · 공차 · 충돌", "1:5"])
    rows.append(["MP50-100", "전체 조립도 (GA)", "1:8"])
    rows += [[a.drawing + suffix, name, sc] for a, suffix, name, sc in (
        (BY_CODE["A"], "1", "탱크 아세이 조립 단면", "1:5"),
        (BY_CODE["A"], "2", "동체 · 콘 전개도", "1:10"),
        (BY_CODE["A"], "3", "노즐 배치 · 노즐표", "1:8"),
    )]
    for code, name, sc in (("B", "상부 커버 아세이", "1:4"), ("C", "구동부 아세이 (HOLD)", "1:5"),
                           ("D", "교반축 · 임펠러 아세이", "1:5"), ("E", "배플 아세이", "1:2"),
                           ("F", "급기 분산링 아세이", "1:2.5"), ("G", "스키머 아세이", "1:4"),
                           ("H", "프레임 아세이", "1:8"), ("I", "노즐 · 배관 · 밸브", "-"),
                           ("J", "계측 · 센서", "-"), ("K", "체결 · 용접 · 검사", "-")):
        rows.append([BY_CODE[code].drawing, name, sc])
    c.view_title(150.0, 30.0, "도면 목록")
    end = c.table(150.0, 34.0, [24.0, 58.0, 16.0], rows, row_h=4.6,
                  aligns=["start", "start", "middle"])

    tol = [["항목", "목표", "검사"]]
    tol += [["축 편심", "≤ 0.5", "다이얼게이지"], ["축 직진도", "≤ 0.5 / 600", "정반 + 다이얼"],
            ["임펠러 TIR", "≤ 1.0", "조립 후 회전"], ["커버 평면도", "≤ 0.5", "정반"],
            ["분산링 편심", "≤ 3", "줄자 + 기준봉"], ["동체 진원도", "≤ 2 (Ø400)", "내경 4 방향"],
            ["노즐 표고", "표기 공차 내", "줄자"], ["프레임 수평", "≤ 0.5 / 550", "수평기"]]
    c.view_title(150.0, end + 9.0, "조립 공차 (mm)")
    end2 = c.table(150.0, end + 13.0, [34.0, 34.0, 30.0], tol, row_h=4.6,
                   aligns=["start", "start", "start"])
    c.text(150.0, end2 + 4.2, "출처 — [R] MP-50 연구문서 Rev.0 §2 공차표", T_DIM - 0.4, "start", "tx2")

    # 충돌 레지스터
    c.view_title(252.0, 30.0, "원본 치수 충돌 해결")
    reg = [["", "항목", "등급", "채택값"]]
    for cf in CONFLICTS:
        reg.append([cf.ref, cf.item, cf.severity, cf.resolution])
    c.table(252.0, 34.0, [8.0, 30.0, 18.0, 100.0], reg, row_h=6.4, size=T_DIM - 0.2,
            aligns=["middle", "start", "middle", "start"])
    y = 34.0 + len(reg) * 6.4 + 5.0
    c.text(252.0, y, "BLOCKING 2 건은 그대로 두면 조립이 되지 않는다.", T_NOTE, "start", "tx", weight="600")
    c.text(252.0, y + 4.2, "PROPOSED 6 건은 공학적 판단이 들어갔으므로 발주 전 승인이 필요하다.",
           T_DIM - 0.2, "start", "tx2")
    c.text(252.0, y + 8.0, "해결 근거 전문은 본 문서의 '충돌 해결 근거' 절에 있다.",
           T_DIM - 0.2, "start", "tx2")

    c.view_title(252.0, y + 16.0, "설계 검증 요약")
    ver = [["", "항목", "결과", "판정"]]
    for chk in CHECKS:
        ver.append([chk.ref.replace("CHK-", ""), chk.item, chk.value, chk.verdict])
    c.table(252.0, y + 20.0, [8.0, 40.0, 82.0, 16.0], ver, row_h=4.8, size=T_DIM - 0.3,
            aligns=["middle", "start", "start", "middle"])


# ==========================================================================
# 100 — 전체 조립도
# ==========================================================================
def sheet_100() -> None:
    c = sheet("MP50-100", "전체 조립도 (GA)", "아세이 A~K 배치 · 설치 표고 · 총질량",
              "1:8", "MP-50 전체 조립도 — 정면도와 평면도에 아세이 A부터 K까지의 배치, 프레임 위 설치 표고, 노즐 방위")
    c.frame_and_title(REV, DATE, "2/15")
    c.head([("전체높이", f"{G.overall_height_mm:.0f} + 구동부"),
            ("프레임", f"{G.frame_width_mm:.0f} × {G.frame_width_mm:.0f} × H{G.frame_height_mm:.0f}"),
            ("배출 표고", f"{G.discharge_elevation_mm:.0f}"),
            ("운전질량", f"{wet_mass_kg():.0f} kg"), ("아세이", f"{len(ASSEMBLIES)} 종")])

    off = G.floor_offset_mm
    v = View(92.0, 268.0, 8.0)          # 바닥 기준
    vv = View(92.0, 268.0 - off / 8.0, 8.0)  # 용기 Z 기준
    fw, ft = G.frame_width_mm, G.frame_tube_mm

    # --- 바닥 ---
    ground = v.y(0)
    c.line(v.x(-400), ground, v.x(400), ground, FRAME, "ln")
    for gx in range(-390, 400, 22):
        c.line(v.x(gx), ground, v.x(gx - 14), ground + 3.0, THIN, "ln")

    # --- 프레임 (뒤) ---
    for sx in (-1, 1):
        x0 = sx * (fw / 2 - ft)
        c.poly(v.pts([(x0, 0), (x0 + sx * ft, 0), (x0 + sx * ft, G.frame_height_mm), (x0, G.frame_height_mm)]),
               THICK, "ln", close=True)
        c.poly(v.pts([(sx * (fw / 2 - ft / 2) - 30, -60), (sx * (fw / 2 - ft / 2) + 30, -60),
                      (sx * (fw / 2 - ft / 2) + 30, 0), (sx * (fw / 2 - ft / 2) - 30, 0)]),
               THICK, "ln", close=True)
    for z in (G.frame_height_mm - ft, G.frame_height_mm / 2 - ft / 2, 0.0):
        c.poly(v.pts([(-fw / 2 + ft, z), (fw / 2 - ft, z), (fw / 2 - ft, z + ft), (-fw / 2 + ft, z + ft)]),
               THICK, "ln", close=True)

    # --- 용기 (앞) — 실루엣으로 프레임을 가리고 그린다 ---
    mask(c, vv, vessel_silhouette())
    c.centreline(vv.x(0), vv.y(-30), vv.x(0), vv.y(1460))
    draw_vessel_section(c, vv, hatch=False)
    draw_flange_and_cover(c, vv)
    draw_liquid(c, vv)
    draw_internals(c, vv, phantom=True)
    r = G.support_ring_od_mm / 2
    c.poly(vv.pts([(-r, G.support_ring_z - G.support_ring_thickness_mm),
                   (r, G.support_ring_z - G.support_ring_thickness_mm),
                   (r, G.support_ring_z), (-r, G.support_ring_z)]), THICK, "ln", close=True)
    for tag, sign in (("N1", -1.0), ("N3", -1.0), ("N2", 1.0), ("N5", 1.0)):
        n = next(x for x in NOZZLES if x.tag == tag)
        mask(c, vv, [(sign * 200, n.z_mm - 26), (sign * 300, n.z_mm - 26),
                     (sign * 300, n.z_mm + 26), (sign * 200, n.z_mm + 26)])
        nozzle_side(c, vv, n, sign)
        c.text(vv.x(sign * 292), vv.y(n.z_mm) - 8.0, tag, T_NOTE, "middle", "tx", weight="600")

    # --- 배출 밸브 (맨 앞) ---
    bz = G.cone_outlet_z
    for w0, w1, z0, z1 in ((38, 38, bz - 34, bz), (27, 27, bz - 132, bz - 34), (7, 7, bz - 210, bz - 132)):
        pts = [(-w0, z0), (w1, z0), (w1, z1), (-w0, z1)]
        mask(c, vv, pts)
        c.poly(vv.pts(pts), THICK, "ln", close=True)
    c.leader(vv.x(27), vv.y(bz - 80), vv.x(160), vv.y(bz - 96), '2" 위생 볼밸브',
             lines=('기본형은 2→1½ 리듀싱 클램프',))

    # --- 구동부 HOLD envelope ---
    dz0, dz1 = G.cover_top_z + G.cover_hub_thickness_mm, 1420.0
    c.poly(vv.pts([(-130, dz0), (130, dz0), (130, dz1), (-130, dz1)]), THICK, "ln", close=True, dash="5 2.5")
    mid = (dz0 + dz1) / 2
    c.text(vv.x(0), vv.y(mid) - 2.2, "구동부 C", T_LABEL, "middle", "tx", weight="700")
    c.text(vv.x(0), vv.y(mid) + 2.4, "설치 envelope H469", T_DIM - 0.2, "middle", "tx2")
    c.text(vv.x(0), vv.y(mid) + 6.2, "HOLD — 벤더 GA", T_DIM - 0.2, "middle", "warn")

    # --- 치수 ---
    xl = v.x(-fw / 2)
    c.dim_v(v.y(0), v.y(G.frame_height_mm), xl - 8.0, fmt(G.frame_height_mm), ext_from=xl)
    c.dim_v(vv.y(G.cone_outlet_z), v.y(0), xl - 8.0, fmt(G.discharge_elevation_mm))
    c.dim_v(vv.y(G.cover_top_z), v.y(0), xl - 18.0, fmt(G.overall_height_mm))
    c.dim_v(vv.y(dz1), v.y(0), xl - 28.0, f"{G.elevation_mm(dz1):.0f} 구동 포함")
    c.dim_h(v.x(-fw / 2), v.x(fw / 2), v.y(-90), fmt(fw), ext_from=v.y(-60))
    c.view_title(16.0, 30.0, "정면도", v.label)

    # --- 평면도 ---
    p = View(214.0, 130.0, 8.0)
    c.centreline(p.x(-340), p.y(0), p.x(340), p.y(0))
    c.centreline(p.x(0), p.y(-340), p.x(0), p.y(340))
    c.rect(p.x(-fw / 2), p.y(fw / 2), p.d(fw), p.d(fw), THIN, "cl", dash="6 2.5")
    c.text(p.x(fw / 2), p.y(fw / 2) - 1.4, f"프레임 {fmt(fw)} 사각", T_DIM - 0.4, "end", "tx2")
    for n in NOZZLES:
        if n.tag in ("N4A", "N4B", "N4D", "N4E"):
            continue
        a = math.radians(n.theta_deg)
        rs, re_ = G.tank_id_mm / 2, G.tank_id_mm / 2 + G.shell_thickness_mm + n.projection_mm
        hw = n.tube_od_mm / 2 + 2
        ca, sa = math.cos(a), math.sin(a)
        quad = [(rs * ca - sa * hw, rs * sa + ca * hw), (re_ * ca - sa * hw, re_ * sa + ca * hw),
                (re_ * ca + sa * hw, re_ * sa - ca * hw), (rs * ca + sa * hw, rs * sa - ca * hw)]
        mask(c, p, quad)
        c.poly(p.pts(quad), THICK, "ln", close=True)
        c.poly(p.pts([((re_ + 12) * ca - sa * (hw + 5), (re_ + 12) * sa + ca * (hw + 5)),
                      ((re_ + 12) * ca + sa * (hw + 5), (re_ + 12) * sa - ca * (hw + 5)),
                      (re_ * ca + sa * (hw + 5), re_ * sa - ca * (hw + 5)),
                      (re_ * ca - sa * (hw + 5), re_ * sa + ca * (hw + 5))]), THICK, "ln", close=True)
        c.centreline(p.x((rs - 30) * ca), p.y((rs - 30) * sa), p.x((re_ + 20) * ca), p.y((re_ + 20) * sa))
        lab = "N4 (사다리 5단)" if n.tag == "N4C" else n.tag
        c.text(p.x((re_ + 46) * ca), p.y((re_ + 46) * sa) + 1.2, lab, T_NOTE, "middle", "tx", weight="600")
    c.circle(p.x(0), p.y(0), p.d(G.top_flange_od_mm / 2), THICK, "ln")
    c.circle(p.x(0), p.y(0), p.d(G.tank_id_mm / 2 + G.shell_thickness_mm), THICK, "ln")
    c.circle(p.x(0), p.y(0), p.d(G.tank_id_mm / 2), THICK, "ln")
    c.circle(p.x(0), p.y(0), p.d(G.top_flange_pcd_mm / 2), THIN, "cl", dash="6 1.2 1.2 1.2")
    for i in range(G.top_flange_bolts):
        a = math.radians(360 / G.top_flange_bolts * i + 15)
        c.circle(p.x(G.top_flange_pcd_mm / 2 * math.cos(a)), p.y(G.top_flange_pcd_mm / 2 * math.sin(a)),
                 p.d(7), THIN, "ln")
    for i in range(G.baffle_count):
        a = math.radians(45 + 90 * i)
        r0, r1 = G.baffle_inner_radius_mm, G.tank_id_mm / 2 - G.baffle_wall_gap_mm
        ca, sa = math.cos(a), math.sin(a)
        na, nb = -sa * G.baffle_thickness_mm / 2, ca * G.baffle_thickness_mm / 2
        c.poly(p.pts([(r0 * ca + na, r0 * sa + nb), (r1 * ca + na, r1 * sa + nb),
                      (r1 * ca - na, r1 * sa - nb), (r0 * ca - na, r0 * sa - nb)]), THICK, "ln", close=True)
    c.circle(p.x(0), p.y(0), p.d(G.impeller_od_mm / 2), THIN, "ln", dash="3 1.6")
    c.circle(p.x(0), p.y(0), p.d(G.cover_hub_od_mm / 2), THIN, "ln")
    c.circle(p.x(0), p.y(0), p.d(G.shaft_od_mm / 2), THICK, "ln")
    c.dim_h(p.x(-G.tank_id_mm / 2), p.x(G.tank_id_mm / 2), p.y(-330), f"Ø{fmt(G.tank_id_mm)}")
    c.dim_h(p.x(-G.top_flange_od_mm / 2), p.x(G.top_flange_od_mm / 2), p.y(-360),
            f"Ø{fmt(G.top_flange_od_mm)} 플랜지")
    c.text(p.x(0), p.y(400), "θ 0° = N1 · 위에서 볼 때 반시계 양", T_DIM, "middle", "tx2")
    c.view_title(160.0, 30.0, "평면도", p.label)

    # --- 아세이 구성 ---
    rows = [["", "아세이", "품목", "개수", "질량 kg"]]
    for a in ASSEMBLIES:
        rows.append([a.code, a.name, str(len(a.parts)), str(a.piece_count), f"{a.total_kg:.1f}"])
    rows.append(["", "건조 총계", "", str(sum(a.piece_count for a in ASSEMBLIES)), f"{dry_mass_kg():.1f}"])
    rows.append(["", f"운전 총계 (염수 {G.operating_volume_l:.1f} L)", "", "", f"{wet_mass_kg():.0f}"])
    c.view_title(268.0, 30.0, "아세이 구성")
    end = c.table(268.0, 34.0, [9.0, 62.0, 13.0, 13.0, 20.0], rows, row_h=4.7,
                  aligns=["middle", "start", "middle", "middle", "end"])
    c.view_title(268.0, end + 10.0, "설치 · 반입 주기")
    notes = [
        f"1. 최대 단품은 탱크 아세이 {BY_CODE['A'].total_kg:.0f} kg — 양중 러그 3 개소(A-08) 이용.",
        f"2. 프레임 높이 {G.frame_height_mm:.0f} 은 임의값이 아니라 배출 여유에서 역산했다 (CHK-09).",
        "3. 레벨링 풋으로 커버 상면 수평도 0.5 를 먼저 잡고 구동부를 얹는다.",
        "4. 구동부 C 는 벤더 GA 승인 전 커버 중앙(B-02)을 가공하지 않는다.",
        f"5. 운전 중량 {wet_mass_kg():.0f} kg 은 다리 4 개에 약 {wet_mass_kg() / 4:.0f} kg/각.",
        "6. 배출 호스(I-07)는 프레임 밖으로 빼 통을 옆에 둔다.",
        "7. 시료 사다리 N4A~N4E 는 θ270° 한 줄에 세로로 정렬한다 (평면도에서 겹침).",
    ]
    for i, t in enumerate(notes):
        c.text(268.0, end + 15.4 + i * 4.5, t, T_DIM - 0.2, "start", "tx2")


# ==========================================================================
# A — 탱크 아세이
# ==========================================================================
def elevation_labels() -> list[tuple[float, str]]:
    """좌표치수에 붙일 표고와 그 자리에 있는 것. 노즐 라벨을 따로 두지 않는다."""
    feat: dict[float, list[str]] = {}
    for n in NOZZLES:
        feat.setdefault(n.z_mm, []).append(n.tag)
    for z, name in ((G.cone_outlet_z, "콘 배출"), (G.sparger_z, "분산링"),
                    (G.shell_bottom_z, "콘 접선"), (G.support_ring_z, "지지링"),
                    (G.lower_impeller_z, "하부 임펠러"), (G.upper_impeller_z, "상부 임펠러"),
                    (G.baffle_bottom_z, "배플 하단"), (G.baffle_top_z, "배플 상단"),
                    (G.nominal_level_z, "WL-MIN"), (G.skimmer_z, "스키머"),
                    (G.shell_top_z, "플랜지 면")):
        feat.setdefault(z, []).append(name)
    feat.setdefault(G.operating_level_z, []).append("운전 액면")
    return [(z, " · ".join(v)) for z, v in sorted(feat.items())]


def ordinate_column(c: Canvas, v: View, items: list[tuple[float, str]], x: float,
                    anchor: "callable" = outer_r_at, min_gap: float = 3.9) -> None:
    """표고 좌표치수 한 열.

    표고가 15 mm 차이로 붙어 있으면 1:5 에서 종이 위 3 mm 라 글자가 겹친다.
    참값 위치에는 화살표를 남기고 **글자만** 아래에서 위로 밀어 올려 최소 간격을
    확보한 뒤, 둘이 어긋난 만큼 지시선을 꺾어 잇는다.
    """
    rows = sorted(items, key=lambda r: -r[0])       # 종이 y 오름차순 = 표고 내림차순
    ys = [v.y(z) for z, _ in rows]
    for i in range(1, len(ys)):                     # 위에서 아래로 밀어 내린다
        ys[i] = max(ys[i], ys[i - 1] + min_gap)
    span = ys[-1] - ys[0]
    true_span = v.y(rows[-1][0]) - v.y(rows[0][0])
    shift = (span - true_span) / 2.0                # 열 전체를 가운데로 되돌린다
    for (z, name), ly in zip(rows, ys):
        ty = v.y(z)
        ly -= shift
        ax = v.x(anchor(z)) + 1.0
        if abs(ly - ty) < 0.2:
            c.line(ax, ty, x, ty, THIN, "dl")
        else:
            c.poly([(ax, ty), (x - 12.0, ty), (x - 7.0, ly), (x, ly)], THIN, "dl")
        c._arrow(x, ly, 180)
        c.text(x + 1.6, ly - 0.8, f"Z {fmt(z, 1)}", T_DIM, "start", "tx", mono=True)
        c.text(x + 15.5, ly - 0.8, name, T_DIM - 0.4, "start", "tx2")


def sheet_a1() -> None:
    c = sheet("MP50-A1", "탱크 아세이 조립 단면", "동체 · 원뿔 · 노즐 · 플랜지 · 지지링 · 용접",
              "1:5", "탱크 아세이 조립 단면도 — 동체와 원뿔의 표고, 노즐 위치, 용접 지시, 부품표")
    c.frame_and_title(REV, DATE, "3/15")
    c.head([("재질", "SUS304 2B"), ("판두께", f"t{G.shell_thickness_mm:.0f}"),
            ("내면", "Ra ≤ 0.8 (버프)"), ("용접", "TIG 전용입 · 내면 평활"),
            ("전용적", f"{G.total_volume_l:.2f} L"), ("아세이 질량", f"{BY_CODE['A'].total_kg:.1f} kg")])

    v = View(92.0, 254.0, 5.0)
    c.centreline(v.x(0), v.y(-24), v.x(0), v.y(1000))
    draw_vessel_section(c, v)
    draw_flange_and_cover(c, v, cover=False)
    rs = G.tank_id_mm / 2 + G.shell_thickness_mm
    r = G.support_ring_od_mm / 2
    for sign in (1.0, -1.0):
        section_fill(c, v, v.pts([(sign * rs, G.support_ring_z - G.support_ring_thickness_mm),
                                  (sign * r, G.support_ring_z - G.support_ring_thickness_mm),
                                  (sign * r, G.support_ring_z), (sign * rs, G.support_ring_z)]),
                     G.support_ring_thickness_mm, "hC", 90 if sign > 0 else 0)
    draw_liquid(c, v)
    for n in NOZZLES:
        nozzle_side(c, v, n, 1.0 if n.tag in ("N1", "N5") else -1.0)

    bz = G.cone_outlet_z
    for sign in (1.0, -1.0):
        ro, ri = sign * (G.cone_outlet_id_mm / 2 + 2.0), sign * G.cone_outlet_id_mm / 2
        section_fill(c, v, v.pts([(ri, bz - 40), (ro, bz - 40), (ro, bz), (ri, bz)]),
                     2.0, "hA", 45 if sign > 0 else -45)
        section_fill(c, v, v.pts([(ri, bz - 46), (sign * 38.75, bz - 46),
                                  (sign * 38.75, bz - 40), (ri, bz - 40)]),
                     6.0, "hA", 45 if sign > 0 else -45)

    # 표고 좌표치수 — 노즐 태그를 같은 줄에 붙여 라벨 열을 없앤다
    xd = v.x(G.top_flange_od_mm / 2) + 32.0
    c.line(xd, v.y(-14), xd, v.y(G.shell_top_z + 14), THIN, "dl", dash="6 1.2 1.2 1.2")
    c.text(xd + 1.6, v.y(G.shell_top_z + 19), "표고 · 부착물", T_DIM - 0.2, "start", "tx2")
    ordinate_column(c, v, elevation_labels(), xd)

    xl = v.x(-G.top_flange_od_mm / 2) - 10.0
    c.dim_v(v.y(G.shell_bottom_z), v.y(G.shell_top_z), xl, f"{fmt(G.shell_height_mm)} 동체",
            ext_from=v.x(-rs))
    c.dim_v(v.y(G.cone_outlet_z), v.y(G.shell_bottom_z), xl, f"{fmt(G.cone_truncated_height_mm, 2)} 원뿔대")
    c.dim_v(v.y(0), v.y(G.shell_top_z), xl - 9.0, f"{fmt(G.shell_top_z, 2)} 전고")
    c.dim_h(v.x(-G.tank_id_mm / 2), v.x(G.tank_id_mm / 2), v.y(G.shell_top_z) - 10.0,
            f"Ø{fmt(G.tank_id_mm)} ID", ext_from=v.y(G.shell_top_z))
    c.dim_h(v.x(-G.top_flange_od_mm / 2), v.x(G.top_flange_od_mm / 2), v.y(G.shell_top_z) - 19.0,
            f"Ø{fmt(G.top_flange_od_mm)} 플랜지")
    c.dim_h(v.x(-G.cone_outlet_id_mm / 2), v.x(G.cone_outlet_id_mm / 2), v.y(bz - 62),
            f"Ø{fmt(G.cone_outlet_id_mm, 1)} ID", ext_from=v.y(bz - 46))

    ax, ay = v.p(0, 0)
    c.poly([(v.x(-G.tank_id_mm / 2), v.y(G.shell_bottom_z)), (ax, ay),
            (v.x(G.tank_id_mm / 2), v.y(G.shell_bottom_z))], THIN, "dl", dash="3 1.5")
    c.arc(ax, ay, 13.0, 62, 118, THIN, "dl")
    c.text(ax, ay - 15.4, f"{fmt(G.cone_included_deg)}°", T_NOTE, "middle", "tx", weight="600", mono=True)
    c.circle(ax, ay, 0.9, THIN, "ln")
    c.text(ax, ay + 9.4, f"가상 정점 Z0 — 정점높이 {fmt(G.cone_apex_height_mm, 2)}",
           T_DIM - 0.3, "middle", "tx2")

    # 용접 표시 — 기호는 시트 K 의 용접표에 모으고 여기서는 위치만 찍는다
    for tag, zy in (("W1", G.shell_top_z - 5), ("W2", G.shell_bottom_z), ("W3", bz - 8)):
        fx = v.x(-outer_r_at(zy)) - 12.0
        c.poly([(v.x(-outer_r_at(zy)), v.y(zy)), (fx + 5.0, v.y(zy) - 5.0), (fx, v.y(zy) - 5.0)], THIN, "dl")
        c.poly([(fx, v.y(zy) - 5.0), (fx, v.y(zy) - 9.4), (fx + 6.4, v.y(zy) - 7.2)],
               THIN, "ln", close=True, fill="var(--paper)")
        c.text(fx + 1.4, v.y(zy) - 6.4, tag, T_DIM - 0.4, "start", "tx", weight="600")

    for no, mx, mz in (("A-01", -170, 880), ("A-05", -150, 962), ("A-02", -80, 210),
                       ("A-06", -300, 352), ("A-03", -100, 8)):
        bx, by = v.x(mx + (26 if mx > -200 else -26)), v.y(mz)
        c.balloon(bx, by, no, v.x(mx), v.y(mz))
    c.view_title(16.0, 30.0, "정면 단면", v.label)
    c.text(16.0, 268.0, "노즐은 방위와 무관하게 단면에 투영해 그렸다 — 실제 방위는 MP50-A3.  "
           "용접 W1~W3 의 개선·검사는 MP50-K 용접표.", T_DIM - 0.2, "start", "tx2")

    end = bom_block(c, "A", 208.0, 30.0)
    end = check_note(c, 208.0, end + 6.0, ("CHK-01", "CHK-12"), 96)
    c.text(208.0, end + 4.0, "노즐 관통부 용접 상세와 용접표는 MP50-K.", T_DIM - 0.2, "start", "tx2")


def sheet_a2() -> None:
    c = sheet("MP50-A2", "동체 · 원뿔 전개도", "판금 절단 원도 — 중립축 기준",
              "1:10", "동체와 원뿔의 전개도 — 절단 치수, 노즐 구멍 위치, 롤링 지시, 용접 개선 상세")
    c.frame_and_title(REV, DATE, "4/15")
    c.head([("재질", "SUS304 2B"), ("판두께", f"t{G.shell_thickness_mm:.0f}"),
            ("전개 기준", "중립축 (판 두께 중앙)"), ("절단", "레이저 · 절단면 산세"),
            ("공차", "±1.0 (전개 길이)")])

    L, H = G.shell_development_length_mm, G.shell_height_mm
    v = View(24.0, 128.0, 10.0)
    c.rect(v.x(0), v.y(H), v.d(L), v.d(H), THICK, "ln")
    c.dim_h(v.x(0), v.x(L), v.y(H) - 9.0,
            f"{fmt(L, 2)} = π × (Ø{fmt(G.tank_id_mm)} + t{fmt(G.shell_thickness_mm)})", ext_from=v.y(H))
    c.dim_v(v.y(0), v.y(H), v.x(0) - 8.0, fmt(H), ext_from=v.x(0))
    r_mid = (G.tank_id_mm + G.shell_thickness_mm) / 2
    for n in NOZZLES:
        arc = math.radians(n.theta_deg) * r_mid
        z = n.z_mm - G.shell_bottom_z
        if not (0 <= z <= H):
            continue
        c.circle(v.x(arc), v.y(z), v.d(n.tube_od_mm / 2 + 2), THICK, "ln")
        c.centreline(v.x(arc) - v.d(n.tube_od_mm + 22), v.y(z), v.x(arc) + v.d(n.tube_od_mm + 22), v.y(z))
        c.centreline(v.x(arc), v.y(z) - v.d(n.tube_od_mm + 22), v.x(arc), v.y(z) + v.d(n.tube_od_mm + 22))
    # 방위 → 호길이 (아래쪽으로 뺀다)
    for i, theta in enumerate((90.0, 180.0, 270.0, 315.0)):
        arc = math.radians(theta) * r_mid
        c.dim_h(v.x(0), v.x(arc), v.y(H) + 11.0 + i * 7.4, f"{fmt(arc, 1)}  → θ{fmt(theta)}°",
                ext_from=v.y(0) if i == 0 else None)
    # 표고 → 전개 y
    ordinate_column(c, v, [(n.z_mm, n.tag) for n in NOZZLES
                           if 0 <= n.z_mm - G.shell_bottom_z <= H],
                    v.x(L) + 14.0, anchor=lambda z: L - 2.0, min_gap=4.2)
    c.text(v.x(L) + 14.0, v.y(H) + 6.0, "표고는 Z 기준 · 전개 y = Z − 346.41",
           T_DIM - 0.3, "start", "tx2")
    c.view_title(16.0, 30.0, "동체 전개", v.label)
    c.text(16.0, 40.0, "롤링 방향 →", T_DIM, "start", "tx2")
    c.text(v.x(0), v.y(H) + 44.0,
           "θ0 모서리가 세로이음 맞대기 자리다 — N1(θ0)이 이음과 겹치므로 이음을 θ30° 로 옮겨 절단한다.",
           T_DIM - 0.2, "start", "tx2")

    ro, ri, ang = (G.cone_development_outer_r_mm, G.cone_development_inner_r_mm,
                   G.cone_development_angle_deg)
    cv = View(300.0, 130.0, 10.0)
    cx, cy = cv.p(0, 0)
    c.arc(cx, cy, cv.d(ro), 0, ang, THICK, "ln")
    c.arc(cx, cy, cv.d(ri), 0, ang, THICK, "ln")
    for a in (0.0, ang):
        ar = math.radians(a)
        c.line(cx + cv.d(ri) * math.cos(ar), cy - cv.d(ri) * math.sin(ar),
               cx + cv.d(ro) * math.cos(ar), cy - cv.d(ro) * math.sin(ar), THICK, "ln")
    c.centreline(cx - cv.d(ro) - 7, cy, cx + cv.d(ro) + 7, cy)
    c.circle(cx, cy, 0.9, THIN, "ln")
    c.dim_h(cx, cx + cv.d(ro), cy + 10.0, f"R{fmt(ro, 1)}")
    c.dim_h(cx, cx + cv.d(ri), cy + 19.0, f"R{fmt(ri, 1)}")
    c.dim_v(cy - cv.d(ro), cy, cx - cv.d(ro) - 10.0, f"{fmt(ro, 0)}")
    c.text(cx, cy - cv.d(ro) - 8.0, f"사잇각 {fmt(ang, 1)}° = 360° × sin{fmt(G.cone_half_angle_deg)}°",
           T_NOTE, "middle", "tx", weight="600")
    c.text(cx, cy - cv.d(ro) - 13.0, "60° 원뿔은 전개하면 정확히 반원이 된다",
           T_DIM - 0.2, "middle", "tx2")
    c.leader(cx - cv.d((ro + ri) / 2), cy, cx - cv.d(ro) - 4, cy + 30.0,
             "세로이음 1 개소", anchor="end", lines=("맞대기 전용입 · 내면 평활",))
    c.view_title(248.0, 30.0, "원뿔 전개", cv.label)

    # 맞대기 개선 상세
    dv = View(238.0, 200.0, 0.12)
    c.view_title(208.0, 176.0, "맞대기 개선 상세", "8:1")
    for sx, off in ((-1, -0.4), (1, 0.4)):
        pts = dv.pts([(sx * 9 + off, -1.5), (sx * 1.2 + off, -1.5), (sx * 0.5 + off, 1.5),
                      (sx * 9 + off, 1.5)])
        section_fill(c, dv, pts, 3.0, "hA", 45 if sx > 0 else -45)
    c.dim_h(dv.x(-0.5), dv.x(0.5), dv.y(4.2), "루트 갭 1.0", ext_from=dv.y(1.5))
    c.dim_v(dv.y(-1.5), dv.y(1.5), dv.x(-10.0), "t3", ext_from=dv.x(-9.0))
    c.leader(dv.x(1.0), dv.y(-1.0), dv.x(11.0), dv.y(-6.0), "V 개선 70°",
             lines=("루트면 0.5 · 백퍼지 필수",))
    c.text(208.0, 226.0, "오스테나이트계는 이면에 아르곤 백퍼지를 하지 않으면 산화막이 남고, "
           "그 자리가 염수에서 먼저 공식(pitting)이 된다.", T_DIM - 0.2, "start", "tx2")

    notes = [
        f"1. 동체 전개는 **중립축** 둘레 π×(ID+t) = {fmt(L, 2)} 로 자른다. 안지름이나 바깥지름으로 자르면 롤링 후 Ø400 이 나오지 않는다.",
        f"2. 원뿔 전개 반지름은 모선 길이다 — 바깥 R{fmt(ro, 1)} = (Ø{fmt(G.tank_id_mm)}/2)/sin{fmt(G.cone_half_angle_deg)}°, 안쪽 R{fmt(ri, 1)}.",
        f"3. 원뿔 모선 길이 {fmt(G.cone_slant_length_mm, 2)} · 원뿔대 높이 {fmt(G.cone_truncated_height_mm, 2)} · 가상 정점높이 {fmt(G.cone_apex_height_mm, 2)}.",
        "4. 스프링백을 감안해 롤링 후 진원도를 재고, Ø400 ±2 안에 들 때까지 재교정한다.",
        "5. 압연 방향(grain)을 동체 원주 방향으로 맞춘다 — 세로이음의 굽힘 균열을 줄인다.",
        "6. 노즐 구멍은 롤링·용접이 끝난 뒤 뚫는다. 전개 상태에서 뚫으면 롤링 중 구멍이 타원이 된다.",
        "7. 절단 후 절단면을 산세(pickling)하고, 용접 개선은 위 상세대로 가공한다.",
        f"8. 전개 원판 소요 — 동체 {fmt(L, 0)} × {fmt(H)} 1 매, 원뿔 {fmt(2 * ro, 0)} × {fmt(ro, 0)} 1 매 (반원 부채꼴).",
        "9. 전개 치수 공차 ±1.0. 롤링 후 원주 둘레를 재어 Ø400 ID 를 확인한 뒤 세로이음을 맞춘다.",
    ]
    c.view_title(16.0, 176.0, "판금 지시")
    for i, t in enumerate(notes):
        for j, line in enumerate(_wrap(t, 96)):
            c.text(16.0 + (0 if j == 0 else 4.0), 183.0 + i * 6.6 + j * 3.8, line,
                   T_DIM, "start", "tx" if j == 0 and i < 3 else "tx2")


def sheet_a3() -> None:
    c = sheet("MP50-A3", "노즐 배치 · 노즐표", "동체 · 커버 노즐의 방위와 표고",
              "1:5", "노즐 배치도 — 동체와 커버 노즐의 방위각과 표고, 노즐 규격표")
    c.frame_and_title(REV, DATE, "5/15")
    c.head([("접속", "위생 Tri-clamp"), ("돌출", "동체 외면 +75"),
            ("용접", "set-through 전용입"), ("내면", "평활 연삭 · 크레비스 없을 것"),
            ("동체 노즐", f"{len(NOZZLES)} 개"), ("커버 노즐", f"{len(COVER_NOZZLES)} 개")])

    p = View(88.0, 96.0, 5.0)
    c.centreline(p.x(-340), p.y(0), p.x(340), p.y(0))
    c.centreline(p.x(0), p.y(-340), p.x(0), p.y(340))
    c.circle(p.x(0), p.y(0), p.d(G.tank_id_mm / 2), THICK, "ln")
    c.circle(p.x(0), p.y(0), p.d(G.tank_id_mm / 2 + G.shell_thickness_mm), THICK, "ln")
    seen: set[float] = set()
    for n in NOZZLES:
        if n.theta_deg in seen:
            continue
        seen.add(n.theta_deg)
        a = math.radians(n.theta_deg)
        rs, re_ = G.tank_id_mm / 2, G.tank_id_mm / 2 + G.shell_thickness_mm + n.projection_mm
        hw = n.tube_od_mm / 2 + 2
        ca, sa = math.cos(a), math.sin(a)
        quad = [(rs * ca - sa * hw, rs * sa + ca * hw), (re_ * ca - sa * hw, re_ * sa + ca * hw),
                (re_ * ca + sa * hw, re_ * sa - ca * hw), (rs * ca + sa * hw, rs * sa - ca * hw)]
        mask(c, p, quad)
        c.poly(p.pts(quad), THICK, "ln", close=True)
        c.centreline(p.x(-40 * ca), p.y(-40 * sa), p.x((re_ + 24) * ca), p.y((re_ + 24) * sa))
        tags = [x.tag for x in NOZZLES if x.theta_deg == n.theta_deg]
        lab = "N4A~N4E" if len(tags) > 1 else tags[0]
        c.text(p.x((re_ + 42) * ca), p.y((re_ + 42) * sa) + 1.2, lab, T_NOTE, "middle", "tx", weight="600")
        c.text(p.x((re_ + 42) * ca), p.y((re_ + 42) * sa) + 5.2, f"θ{fmt(n.theta_deg)}°",
               T_DIM - 0.3, "middle", "tx2")
        if n.theta_deg not in (0.0,):
            c.arc(p.x(0), p.y(0), p.d(300), 0, n.theta_deg, THIN, "dl")
    c.text(p.x(360), p.y(0) + 1.0, "θ 0°", T_NOTE, "start", "tx", weight="600")
    c.view_title(16.0, 30.0, "노즐 방위 (평면)", p.label)

    cp = View(88.0, 224.0, 5.0)
    c.circle(cp.x(0), cp.y(0), cp.d(G.top_flange_od_mm / 2), THICK, "ln")
    c.circle(cp.x(0), cp.y(0), cp.d(G.cover_hub_od_mm / 2), THICK, "ln")
    c.centreline(cp.x(-280), cp.y(0), cp.x(280), cp.y(0))
    c.centreline(cp.x(0), cp.y(-280), cp.x(0), cp.y(280))
    for n in COVER_NOZZLES:
        if n.tag == "B1":
            continue
        a = math.radians(n.theta_deg)
        rr = 165.0
        c.circle(cp.x(rr * math.cos(a)), cp.y(rr * math.sin(a)), cp.d(n.tube_od_mm / 2 + 2), THICK, "ln")
        c.text(cp.x(228 * math.cos(a)), cp.y(228 * math.sin(a)) + 1.2, n.tag, T_NOTE, "middle", "tx", weight="600")
    c.text(cp.x(0), cp.y(0) + 1.2, "B1", T_NOTE, "middle", "tx", weight="600")
    c.text(cp.x(0), cp.y(0) + 5.4, "HOLD", T_DIM - 0.3, "middle", "warn")
    c.dim_h(cp.x(-165), cp.x(165), cp.y(-250), "PCD Ø330")
    c.view_title(16.0, 152.0, "커버 노즐 배치", cp.label)

    rows = [["번호", "용도", "규격", "θ", "표고 Z", "공차", "시공"]]
    for n in NOZZLES:
        rows.append([n.tag, n.service, n.size, f"{fmt(n.theta_deg)}°", fmt(n.z_mm),
                     f"±{fmt(n.tolerance_mm)}" if n.tolerance_mm else "잠금", n.note])
    rows.append(["N6", "콘 배출", '2" TC', "-", fmt(G.cone_outlet_z, 1), "잠금",
                 "1½ in 기본 / 2 in 시험 — 리듀싱 클램프 교체"])
    for n in COVER_NOZZLES:
        rows.append([n.tag, n.service, n.size, f"{fmt(n.theta_deg)}°", "커버면", "-", n.note])
    c.view_title(196.0, 30.0, "노즐표")
    c.table(196.0, 34.0, [13.0, 34.0, 20.0, 12.0, 16.0, 13.0, 96.0], rows, row_h=5.4,
            size=T_DIM - 0.2, aligns=["middle", "start", "start", "middle", "middle", "middle", "start"])
    conflict_note(c, 196.0, 34.0 + len(rows) * 5.4 + 9.0, ("C7",), 100)


# ==========================================================================
# B — 상부 커버
# ==========================================================================
def sheet_b() -> None:
    c = sheet("MP50-B", "상부 커버 아세이", "커버판 · 보강 허브 · 가스켓 · 계측 노즐",
              "1:4", "상부 커버 아세이 — 평면과 단면, 볼트 PCD, 중앙 허브 HOLD 구역, 가스켓 홈")
    c.frame_and_title(REV, DATE, "6/15")
    c.head([("재질", "SUS304"), ("커버 두께", f"t{G.cover_thickness_mm:.0f}"),
            ("평면도", "≤ 0.5"), ("가스켓", "EPDM O-링 Ø5"),
            ("볼트", f"{G.top_flange_bolt} × {G.top_flange_bolts} · 40 N·m"),
            ("아세이 질량", f"{BY_CODE['B'].total_kg:.1f} kg")])

    R = G.top_flange_od_mm / 2
    v = View(92.0, 106.0, 4.0)
    c.centreline(v.x(-R - 22), v.y(0), v.x(R + 22), v.y(0))
    c.centreline(v.x(0), v.y(-R - 22), v.x(0), v.y(R + 22))
    c.circle(v.x(0), v.y(0), v.d(R), THICK, "ln")
    c.circle(v.x(0), v.y(0), v.d(G.top_flange_pcd_mm / 2), THIN, "cl", dash="6 1.2 1.2 1.2")
    c.circle(v.x(0), v.y(0), v.d(215.0), THIN, "ln", dash="3 1.6")
    c.circle(v.x(0), v.y(0), v.d(G.cover_hub_od_mm / 2), THICK, "ln")
    c.circle(v.x(0), v.y(0), v.d(30.0), THICK, "ln")
    c.hatch([(v.x(30 * math.cos(math.radians(a))), v.y(30 * math.sin(math.radians(a))))
             for a in range(0, 360, 10)], "hHold", 45, 1.6)
    for i in range(G.top_flange_bolts):
        a = math.radians(360 / G.top_flange_bolts * i + 15)
        c.circle(v.x(G.top_flange_pcd_mm / 2 * math.cos(a)), v.y(G.top_flange_pcd_mm / 2 * math.sin(a)),
                 v.d(7), THICK, "ln")
    for n in COVER_NOZZLES:
        if n.tag == "B1":
            continue
        a = math.radians(n.theta_deg)
        cxn, cyn = v.x(165 * math.cos(a)), v.y(165 * math.sin(a))
        c.circle(cxn, cyn, v.d(n.tube_od_mm / 2 + 2), THICK, "ln")
        c.text(cxn, cyn - v.d(30), n.tag, T_NOTE, "middle", "tx", weight="600")
    for i in range(3):
        a = math.radians(30 + 120 * i)
        c.circle(v.x(165 * math.cos(a)), v.y(165 * math.sin(a)), v.d(5), THICK, "ln")
        c.text(v.x(196 * math.cos(a)), v.y(196 * math.sin(a)) + 1.2, "M8", T_DIM - 0.3, "middle", "tx2")
    c.text(v.x(0), v.y(0) + 1.0, "B1  HOLD", T_NOTE, "middle", "warn", weight="700")
    c.text(v.x(0), v.y(0) + 5.2, "벤더 GA 전 가공 금지", T_DIM - 0.4, "middle", "tx2")
    c.dim_h(v.x(-R), v.x(R), v.y(-R - 14), f"Ø{fmt(G.top_flange_od_mm)}")
    c.dim_h(v.x(-G.top_flange_pcd_mm / 2), v.x(G.top_flange_pcd_mm / 2), v.y(-R - 25),
            f"PCD Ø{fmt(G.top_flange_pcd_mm)} · {G.top_flange_bolts}-Ø14")
    c.leader(v.x(215 * math.cos(math.radians(200))), v.y(215 * math.sin(math.radians(200))),
             v.x(R + 26), v.y(-104), "가스켓 홈 Ø430", lines=("W5 × D3 · EPDM 코드 Ø5",))
    c.leader(v.x(G.cover_hub_od_mm / 2 * math.cos(math.radians(140))),
             v.y(G.cover_hub_od_mm / 2 * math.sin(math.radians(140))),
             v.x(R + 26), v.y(126), f"보강 허브 Ø{fmt(G.cover_hub_od_mm)} × t{fmt(G.cover_hub_thickness_mm)}",
             lines=("거싯 4 매 · B-02/B-03",))
    c.leader(v.x(165 * math.cos(math.radians(30))), v.y(165 * math.sin(math.radians(30))),
             v.x(R + 26), v.y(-70), "스키머 조절봉 3 개소", lines=("PCD Ø330 · M8 부싱 + O-링",))
    c.view_title(16.0, 30.0, "평면 (커버 위에서)", v.label)

    sv = View(92.0, 236.0, 4.0)
    for sign in (1.0, -1.0):
        section_fill(c, sv, sv.pts([(sign * 30, 0), (sign * R, 0), (sign * R, G.cover_thickness_mm),
                                    (sign * 30, G.cover_thickness_mm)]), G.cover_thickness_mm, "hB", -45)
        section_fill(c, sv, sv.pts([(sign * 30, G.cover_thickness_mm), (sign * G.cover_hub_od_mm / 2, G.cover_thickness_mm),
                                    (sign * G.cover_hub_od_mm / 2, G.cover_thickness_mm + G.cover_hub_thickness_mm),
                                    (sign * 30, G.cover_thickness_mm + G.cover_hub_thickness_mm)]),
                     G.cover_hub_thickness_mm, "hB", -45)
        section_fill(c, sv, sv.pts([(sign * 203, -G.top_flange_thickness_mm), (sign * R, -G.top_flange_thickness_mm),
                                    (sign * R, 0), (sign * 203, 0)]), G.top_flange_thickness_mm, "hA",
                     45 if sign > 0 else -45)
        c.poly(sv.pts([(sign * 30, G.cover_thickness_mm + G.cover_hub_thickness_mm),
                       (sign * 100, G.cover_thickness_mm), (sign * 30, G.cover_thickness_mm)]),
               THICK, "ln", close=True)
    c.circle(sv.x(-215), sv.y(-1.5), sv.d(2.5), THICK, "ln")
    c.circle(sv.x(215), sv.y(-1.5), sv.d(2.5), THICK, "ln")
    c.centreline(sv.x(0), sv.y(-24), sv.x(0), sv.y(28))
    c.dim_v(sv.y(0), sv.y(G.cover_thickness_mm), sv.x(R) + 9.0, f"t{fmt(G.cover_thickness_mm)}", left=False)
    c.dim_v(sv.y(-G.top_flange_thickness_mm), sv.y(0), sv.x(R) + 9.0,
            f"t{fmt(G.top_flange_thickness_mm)}", left=False)
    c.dim_v(sv.y(G.cover_thickness_mm), sv.y(G.cover_thickness_mm + G.cover_hub_thickness_mm),
            sv.x(R) + 20.0, f"t{fmt(G.cover_hub_thickness_mm)} 허브", left=False)
    c.text(sv.x(0), sv.y(-30), f"커버 상면 Z{fmt(G.cover_top_z, 1)} · 플랜지 면 Z{fmt(G.shell_top_z, 1)}",
           T_DIM - 0.2, "middle", "tx2")
    c.view_title(16.0, 196.0, "단면 (커버 · 플랜지)", sv.label)
    c.text(16.0, 262.0, "가스켓을 플랜지 면에 판 홈에 넣어 커버가 금속면에 직접 앉는다 — "
           "[R] 의 Z946/Z951 스택이 그대로 유지된다.", T_DIM - 0.2, "start", "tx2")

    end = bom_block(c, "B", 208.0, 30.0)
    conflict_note(c, 208.0, end + 6.0, ("C8",), 96)


# ==========================================================================
# C — 구동부 (전량 HOLD)
# ==========================================================================
def sheet_c() -> None:
    c = sheet("MP50-C", "구동부 아세이 — 인터페이스 HOLD", "벤더 GA 승인 전 커버 중앙 가공 금지",
              "1:5", "구동부 아세이 — 설치 envelope 와 인터페이스 치수, 벤더 제출자료 목록")
    c.frame_and_title(REV, DATE, "7/15")
    c.head([("공급", "교반기 벤더 일체"), ("모터", "0.55 kW · VFD"),
            ("출력속도", "30~150 rpm"), ("씰", "고형분용 더블 카트리지"),
            ("상태", "CRITICAL HOLD"), ("아세이 질량", f"{BY_CODE['C'].total_kg:.1f} kg")])

    v = View(96.0, 392.0, 5.0)
    c.centreline(v.x(0), v.y(910), v.x(0), v.y(1450))
    # 커버 (참고)
    section_fill(c, v, v.pts([(-240, G.shell_top_z), (240, G.shell_top_z),
                              (240, G.cover_top_z), (-240, G.cover_top_z)]),
                 G.cover_thickness_mm, "hB", -45)
    section_fill(c, v, v.pts([(-110, G.cover_top_z), (110, G.cover_top_z),
                              (110, G.cover_top_z + G.cover_hub_thickness_mm),
                              (-110, G.cover_top_z + G.cover_hub_thickness_mm)]),
                 G.cover_hub_thickness_mm, "hB", -45)
    z0 = G.cover_top_z + G.cover_hub_thickness_mm
    stack = (("축 씰 (C-03)", 100.0), ("램턴 · 어댑터 (C-05)", 40.0),
             ("커플링 (C-04)", 60.0), ("감속기 + 모터 (C-01/02)", 269.0))
    z = z0
    for name, hgt in stack:
        c.poly(v.pts([(-130, z), (130, z), (130, z + hgt), (-130, z + hgt)]),
               THICK, "ln", close=True, dash="5 2.5")
        c.text(v.x(0), v.y(z + hgt / 2) - 1.0, name, T_DIM - 0.2, "middle", "tx", weight="600")
        c.text(v.x(0), v.y(z + hgt / 2) + 3.0, f"H{fmt(hgt)}", T_DIM - 0.4, "middle", "tx2")
        z += hgt
    c.poly(v.pts([(-G.shaft_od_mm / 2, 940), (-G.shaft_od_mm / 2, z0 + 200),
                  (G.shaft_od_mm / 2, z0 + 200), (G.shaft_od_mm / 2, 940)]), THICK, "ln")
    c.dim_v(v.y(z0), v.y(z), v.x(150) + 10.0, f"{fmt(z - z0)} 설치 envelope", left=False)
    c.dim_v(v.y(G.cover_top_z), v.y(z), v.x(150) + 22.0, f"{fmt(z - G.cover_top_z)} 커버 위 전체", left=False)
    c.dim_h(v.x(-130), v.x(130), v.y(z) + 10.0, "260 최대 폭", ext_from=v.y(z))
    c.leader(v.x(-110), v.y(G.cover_top_z + 5), v.x(-190), v.y(1200),
             "B1 인터페이스 — HOLD", anchor="end",
             lines=("허브 보어 · 볼트 PCD · 씰 gland 는", "벤더 GA 승인 전 가공 금지"))
    c.text(v.x(0), v.y(890), f"바닥 기준 설치 최고점 {fmt(G.elevation_mm(z))} mm  ·  "
           f"커버 상면 {fmt(G.overall_height_mm)} mm", T_DIM - 0.2, "middle", "tx2")
    c.text(v.x(0), v.y(866), "점선은 벤더 GA 로 확정할 최대 허용 외형이다 — 실제 기기는 이 안에 들어와야 한다.",
           T_DIM - 0.2, "middle", "tx2")
    c.view_title(16.0, 30.0, "구동부 설치 envelope", v.label)

    end = bom_block(c, "C", 208.0, 30.0)
    rows = [["", "벤더가 확정해야 하는 값", "이 값이 없으면"]]
    rows += [
        ["1", "출력축 지름 · 키 규격 · 돌출장", "커플링(C-04)과 축 상단(D-01)을 가공할 수 없다"],
        ["2", "감속기 마운팅 PCD · 볼트 규격", "커버 허브(B-02)의 볼트 구멍을 뚫을 수 없다"],
        ["3", "씰 gland 치수 · 슬리브 외경", "허브 보어(B-02)를 가공할 수 없다"],
        ["4", "허용 고형분 wt% · 씰 세정수 요부", "고형분 조건에서 씰 수명을 보증받을 수 없다"],
        ["5", "축 지지점 위치 (베어링 스팬)", "CHK-07 위험속도를 다시 계산해야 한다"],
        ["6", "정격 출력토크 · 서비스 팩터", "CHK-06 재기동 토크 여유를 확인할 수 없다"],
        ["7", "전체 높이 · 질량 · 무게중심", "프레임 전도 검토(CHK-13)를 확정할 수 없다"],
    ]
    c.view_title(208.0, end + 6.0, "벤더 제출자료 (GA 승인 전제)")
    e2 = c.table(208.0, end + 10.0, [8.0, 78.0, 106.0], rows, row_h=5.4, size=T_DIM - 0.2,
                 aligns=["middle", "start", "start"])
    check_note(c, 208.0, e2 + 8.0, ("CHK-05", "CHK-06"), 96)


# ==========================================================================
# D — 교반축 · 임펠러
# ==========================================================================
def sheet_d() -> None:
    c = sheet("MP50-D", "교반축 · 임펠러 아세이", "분산 수단 — 분리 수단이 아니다",
              "1:5", "교반축과 임펠러 아세이 — 축 전장과 키홈, 임펠러 평면과 블레이드 상세, 위험속도 검증")
    c.frame_and_title(REV, DATE, "8/15")
    c.head([("재질", "SUS316L"), ("축", f"Ø{G.shaft_od_mm:.0f} h7 × L760"),
            ("임펠러", f"Ø{G.impeller_od_mm:.0f} {G.impeller_blades}PBT{G.impeller_pitch_deg:.0f}°"),
            ("직진도", "0.5 / 600"), ("TIR", "≤ 1.0"),
            ("아세이 질량", f"{BY_CODE['D'].total_kg:.1f} kg")])

    v = View(54.0, 248.0, 5.0)
    top = 1155.0
    c.poly(v.pts([(-G.shaft_od_mm / 2, 395), (-G.shaft_od_mm / 2, top),
                  (G.shaft_od_mm / 2, top), (G.shaft_od_mm / 2, 395)]), THICK, "ln", close=True)
    c.centreline(v.x(0), v.y(380), v.x(0), v.y(top + 16))
    for z in (G.lower_impeller_z, G.upper_impeller_z):
        c.poly(v.pts([(-G.shaft_od_mm / 2, z - 25), (-G.shaft_od_mm / 2 + 3, z - 25),
                      (-G.shaft_od_mm / 2 + 3, z + 25), (-G.shaft_od_mm / 2, z + 25)]),
               THIN, "ln", close=True)
        proj = G.impeller_blade_width_mm * math.sin(math.radians(G.impeller_pitch_deg)) / 2
        for sign in (1.0, -1.0):
            c.poly(v.pts([(sign * G.impeller_hub_od_mm / 2, z + proj),
                          (sign * G.impeller_od_mm / 2, z - proj)]), THICK, "ln")
        c.poly(v.pts([(-G.impeller_hub_od_mm / 2, z - G.impeller_hub_length_mm / 2),
                      (G.impeller_hub_od_mm / 2, z - G.impeller_hub_length_mm / 2),
                      (G.impeller_hub_od_mm / 2, z + G.impeller_hub_length_mm / 2),
                      (-G.impeller_hub_od_mm / 2, z + G.impeller_hub_length_mm / 2)]),
               THICK, "ln", close=True)
    c.dim_v(v.y(395), v.y(top), v.x(-G.impeller_od_mm / 2) - 6.0, "760 전장",
            ext_from=v.x(-G.shaft_od_mm / 2))
    ordinate_column(c, v, [(395.0, "축 하단"), (G.lower_impeller_z, "하부 임펠러 D-02"),
                           (G.upper_impeller_z, "상부 임펠러 D-03"), (951.4, "커버 상면 통과"),
                           (top, "커플링 자리")],
                    v.x(G.impeller_od_mm / 2) + 12.0, anchor=lambda z: G.impeller_od_mm / 2)
    c.text(v.x(0), v.y(top + 22), f"임펠러 간격 {fmt(G.impeller_spacing_mm)} = {G.impeller_spacing_mm / G.impeller_od_mm:.2f} D",
           T_DIM - 0.2, "middle", "tx2")
    c.view_title(16.0, 30.0, "교반축 정면", v.label)

    pv = View(166.0, 92.0, 4.0)
    c.circle(pv.x(0), pv.y(0), pv.d(G.impeller_od_mm / 2), THIN, "cl", dash="4 2")
    c.circle(pv.x(0), pv.y(0), pv.d(G.impeller_hub_od_mm / 2), THICK, "ln")
    c.circle(pv.x(0), pv.y(0), pv.d(G.shaft_od_mm / 2), THICK, "ln")
    c.centreline(pv.x(-190), pv.y(0), pv.x(190), pv.y(0))
    c.centreline(pv.x(0), pv.y(-190), pv.x(0), pv.y(190))
    for i in range(G.impeller_blades):
        a = math.radians(90 * i + 45)
        ca, sa = math.cos(a), math.sin(a)
        r0, r1 = G.impeller_hub_od_mm / 2, G.impeller_od_mm / 2
        hw = G.impeller_blade_width_mm / 2 * math.cos(math.radians(G.impeller_pitch_deg))
        c.poly(pv.pts([(r0 * ca - sa * hw, r0 * sa + ca * hw), (r1 * ca - sa * hw, r1 * sa + ca * hw),
                       (r1 * ca + sa * hw, r1 * sa - ca * hw), (r0 * ca + sa * hw, r0 * sa - ca * hw)]),
               THICK, "ln", close=True)
    c.dim_h(pv.x(-G.impeller_od_mm / 2), pv.x(G.impeller_od_mm / 2), pv.y(-190),
            f"Ø{fmt(G.impeller_od_mm)}")
    c.dim_h(pv.x(-G.impeller_hub_od_mm / 2), pv.x(G.impeller_hub_od_mm / 2), pv.y(-210),
            f"허브 Ø{fmt(G.impeller_hub_od_mm)}")
    c.text(pv.x(0), pv.y(210), f"{G.impeller_blades}매 90° 등분", T_DIM - 0.2, "middle", "tx2")
    c.view_title(128.0, 30.0, "임펠러 평면", pv.label)

    bv = View(136.0, 190.0, 2.5)
    rl = G.impeller_blade_radial_mm
    bw = G.impeller_blade_width_mm
    c.rect(bv.x(0), bv.y(bw / 2), bv.d(rl), bv.d(bw), THICK, "ln")
    c.dim_h(bv.x(0), bv.x(rl), bv.y(-bw / 2) - 8.0, f"{fmt(rl)}", ext_from=bv.y(-bw / 2))
    c.dim_v(bv.y(-bw / 2), bv.y(bw / 2), bv.x(rl) + 8.0, f"{fmt(bw)}", left=False)
    c.text(bv.x(rl / 2), bv.y(bw / 2 + 12), f"블레이드 전개 · t{fmt(G.impeller_blade_thickness_mm)} · 모서리 R2",
           T_DIM - 0.2, "middle", "tx2")
    ax, ay = bv.x(0), bv.y(-bw / 2) + 16.0
    c.arc(ax, ay, 9.0, 0, 45, THIN, "dl")
    c.line(ax, ay, ax + 20, ay, THIN, "dl")
    c.line(ax, ay, ax + 14.2, ay - 14.2, THIN, "dl")
    c.text(ax + 11.0, ay + 4.4, f"{fmt(G.impeller_pitch_deg)}° 취부각",
           T_NOTE, "start", "tx", weight="600")
    c.view_title(128.0, 168.0, "블레이드 상세", bv.label)

    kv = View(168.0, 252.0, 1.0)
    c.circle(kv.x(0), kv.y(0), kv.d(G.impeller_hub_od_mm / 2), THICK, "ln")
    c.circle(kv.x(0), kv.y(0), kv.d(G.shaft_od_mm / 2), THICK, "ln")
    c.rect(kv.x(-3), kv.y(G.shaft_od_mm / 2 + 2.8), kv.d(6), kv.d(2.8), THICK, "ln")
    c.centreline(kv.x(-44), kv.y(0), kv.x(44), kv.y(0))
    c.centreline(kv.x(0), kv.y(-44), kv.x(0), kv.y(44))
    c.leader(kv.x(0), kv.y(G.shaft_od_mm / 2 + 1.4), kv.x(42), kv.y(-14), "키홈 6 × 6",
             lines=("축 6P9 · 허브 6JS9",))
    c.leader(kv.x(G.impeller_hub_od_mm / 2 * math.cos(math.radians(210))),
             kv.y(G.impeller_hub_od_mm / 2 * math.sin(math.radians(210))),
             kv.x(-42), kv.y(20), "M8 세트스크류 2 개", anchor="end", lines=("90° 배치 · 키 반대편 가압",))
    c.text(kv.x(0), kv.y(-36), f"보어 Ø{fmt(G.shaft_od_mm)} H7 · 허브 Ø{fmt(G.impeller_hub_od_mm)}",
           T_DIM - 0.2, "middle", "tx2")
    c.view_title(128.0, 222.0, "허브 · 키홈 상세", "1:1")

    end = bom_block(c, "D", 208.0, 30.0)
    check_note(c, 208.0, end + 6.0, ("CHK-07",), 96)


# ==========================================================================
# E — 배플 (C2 BLOCKING 해결)
# ==========================================================================
def sheet_e() -> None:
    c = sheet("MP50-E", "배플 아세이", "선회류 차단 — 원본 폭 80 은 임펠러와 간섭한다",
              "1:4", "배플 아세이 — 배치 평면과 1대1 간극 상세에 원본 80 mm 폭의 임펠러 간섭과 채택한 35 mm 의 간극을 함께 표시")
    c.frame_and_title(REV, DATE, "9/15")
    c.head([("재질", "SUS316L"), ("규격", f"W{G.baffle_width_mm:.0f} × L{G.baffle_length_mm:.0f} × t{G.baffle_thickness_mm:.0f}"),
            ("수량", f"{G.baffle_count} 매 90° 등분"), ("벽 이격", f"{G.baffle_wall_gap_mm:.0f}"),
            ("팁 간극", f"{G.impeller_tip_clearance_mm:.0f}"), ("배플비", f"{G.baffle_area_ratio:.3f} (n·w/T)")])

    def baffles(view: View, width: float, cls: str, w: float, dash: str = "") -> None:
        for i in range(G.baffle_count):
            a = math.radians(45 + 90 * i)
            ca, sa = math.cos(a), math.sin(a)
            r1 = G.tank_id_mm / 2 - G.baffle_wall_gap_mm
            r0 = r1 - width
            hw = G.baffle_thickness_mm / 2
            c.poly(view.pts([(r0 * ca - sa * hw, r0 * sa + ca * hw), (r1 * ca - sa * hw, r1 * sa + ca * hw),
                             (r1 * ca + sa * hw, r1 * sa - ca * hw), (r0 * ca + sa * hw, r0 * sa - ca * hw)]),
                   w, cls, close=True, dash=dash)

    v = View(66.0, 96.0, 4.0)
    c.circle(v.x(0), v.y(0), v.d(G.tank_id_mm / 2), THICK, "ln")
    c.circle(v.x(0), v.y(0), v.d(G.tank_id_mm / 2 + G.shell_thickness_mm), THICK, "ln")
    c.centreline(v.x(-250), v.y(0), v.x(250), v.y(0))
    c.centreline(v.x(0), v.y(-250), v.x(0), v.y(250))
    c.circle(v.x(0), v.y(0), v.d(G.impeller_od_mm / 2), THIN, "cl", dash="5 2")
    baffles(v, 80.0, "warn-ln", THIN, "3 1.6")
    baffles(v, G.baffle_width_mm, "ln", THICK)
    c.dim_h(v.x(-G.tank_id_mm / 2), v.x(G.tank_id_mm / 2), v.y(-232), f"Ø{fmt(G.tank_id_mm)} ID")
    c.dim_h(v.x(-G.impeller_od_mm / 2), v.x(G.impeller_od_mm / 2), v.y(-250),
            f"Ø{fmt(G.impeller_od_mm)} 임펠러 회전면")
    c.text(v.x(0), v.y(240), "θ45° 부터 90° 등분", T_DIM - 0.2, "middle", "tx2")
    c.text(v.x(0), v.y(-268), f"설치 표고 Z{fmt(G.baffle_bottom_z)}~Z{fmt(G.baffle_top_z)}",
           T_DIM - 0.2, "middle", "tx2")
    # 상세 지시 원
    da = math.radians(45)
    c.circle(v.x(176 * math.cos(da)), v.y(176 * math.sin(da)), 9.0, THIN, "dl")
    c.text(v.x(176 * math.cos(da)) + 10.0, v.y(176 * math.sin(da)) - 8.0, "X", T_VIEW, "start", "tx", weight="700")
    c.view_title(16.0, 30.0, "배치 평면", v.label)

    # --- 상세 X : 반지름 방향을 그대로 종이에 편다 (1:1) ---
    d = View(62.0, 236.0, 1.0)   # x = 반지름 - 150, y = 접선방향 옵셋
    ox = 150.0
    c.line(d.x(200 - ox), d.y(-26), d.x(200 - ox), d.y(26), THICK, "ln")
    c.line(d.x(203 - ox), d.y(-26), d.x(203 - ox), d.y(26), THICK, "ln")
    section_fill(c, d, d.pts([(200 - ox, -26), (203 - ox, -26), (203 - ox, 26), (200 - ox, 26)]),
                 G.shell_thickness_mm, "hA", 45)
    # 채택 배플
    section_fill(c, d, d.pts([(G.baffle_inner_radius_mm - ox, -G.baffle_thickness_mm / 2),
                              (194 - ox, -G.baffle_thickness_mm / 2), (194 - ox, G.baffle_thickness_mm / 2),
                              (G.baffle_inner_radius_mm - ox, G.baffle_thickness_mm / 2)]),
                 G.baffle_thickness_mm, "hD", -45)
    # 원본 80 — 간섭 구간을 붉게
    c.poly(d.pts([(114 - ox, -G.baffle_thickness_mm / 2), (194 - ox, -G.baffle_thickness_mm / 2),
                  (194 - ox, G.baffle_thickness_mm / 2), (114 - ox, G.baffle_thickness_mm / 2)]),
           THIN, "warn-ln", close=True, dash="3 1.6")
    c.fill(d.pts([(114 - ox, -G.baffle_thickness_mm / 2), (150 - ox, -G.baffle_thickness_mm / 2),
                  (150 - ox, G.baffle_thickness_mm / 2), (114 - ox, G.baffle_thickness_mm / 2)]),
           "var(--warn)", 0.42)
    # 임펠러 팁 궤적
    c.line(d.x(0), d.y(-30), d.x(0), d.y(30), THIN, "cl", dash="5 2")
    c.text(d.x(0), d.y(34), "임펠러 팁 R150", T_DIM - 0.3, "middle", "tx2")
    for zz, lab, y0 in ((6.0, f"{fmt(G.baffle_wall_gap_mm)}", 12.0),):
        c.dim_h(d.x(194 - ox), d.x(200 - ox), d.y(y0), lab, ext_from=d.y(G.baffle_thickness_mm / 2))
    c.dim_h(d.x(G.baffle_inner_radius_mm - ox), d.x(194 - ox), d.y(20.0), f"{fmt(G.baffle_width_mm)}",
            ext_from=d.y(G.baffle_thickness_mm / 2))
    c.dim_h(d.x(0), d.x(G.baffle_inner_radius_mm - ox), d.y(-14.0),
            f"{fmt(G.impeller_tip_clearance_mm)}", ext_from=d.y(-G.baffle_thickness_mm / 2))
    c.dim_h(d.x(114 - ox), d.x(0), d.y(-24.0), "36 간섭", ext_from=d.y(-G.baffle_thickness_mm / 2))
    c.leader(d.x(-26), d.y(2), d.x(30.0), d.y(-30.0), "원본 W80 이 차지하는 자리",
             lines=("임펠러 회전면 안으로 36 mm 들어온다 — 축이 돌지 않는다",))
    c.leader(d.x(202 - ox), d.y(16), d.x(66.0), d.y(30.0), "동체 t3")
    c.view_title(16.0, 196.0, "상세 X — 임펠러 ↔ 배플 간극", "1:1")

    bv = View(146.0, 250.0, 2.5)
    c.rect(bv.x(0), bv.y(G.baffle_length_mm), bv.d(G.baffle_width_mm), bv.d(G.baffle_length_mm), THICK, "ln")
    for i in range(3):
        zz = 22.0 + i * (G.baffle_length_mm - 44.0) / 2
        c.rect(bv.x(0), bv.y(zz + 12.5), bv.d(G.baffle_wall_gap_mm), bv.d(25.0), THIN, "ln", dash="2.4 1.2")
    c.dim_h(bv.x(0), bv.x(G.baffle_width_mm), bv.y(0) + 8.0, f"{fmt(G.baffle_width_mm)}", ext_from=bv.y(0))
    c.dim_v(bv.y(0), bv.y(G.baffle_length_mm), bv.x(G.baffle_width_mm) + 9.0,
            f"{fmt(G.baffle_length_mm)}", left=False)
    c.leader(bv.x(G.baffle_wall_gap_mm / 2), bv.y(34.5), bv.x(G.baffle_width_mm) + 30.0, bv.y(70.0),
             "스탠드오프 3 개", lines=(f"25 × {fmt(G.baffle_wall_gap_mm)} × t{fmt(G.baffle_thickness_mm)}",
                                   "벽 뒤에 분말이 쌓이지 않게 띄운다"))
    c.text(bv.x(G.baffle_width_mm / 2), bv.y(G.baffle_length_mm) - 7.0,
           f"t{fmt(G.baffle_thickness_mm)} · R2", T_DIM - 0.2, "middle", "tx2")
    c.view_title(140.0, 118.0, "배플판 상세", bv.label)
    c.text(16.0, 282.0, f"배플비 {G.baffle_area_ratio:.3f} (관행 0.4 대비 다소 낮으나 D/T {G.impeller_diameter_ratio:.2f} 의 "
           f"근접 임펠러가 선회류를 함께 억제한다).", T_DIM - 0.2, "start", "tx2")

    end = bom_block(c, "E", 208.0, 30.0)
    end = conflict_note(c, 208.0, end + 6.0, ("C2",), 96)
    check_note(c, 208.0, end + 4.0, ("CHK-02",), 96)


# ==========================================================================
# F — 급기 분산링
# ==========================================================================
def sheet_f() -> None:
    c = sheet("MP50-F", "급기 분산링 아세이", "콘 정착층을 들어올리는 분산 보조 — 부선용 아님",
              "1:2.5", "급기 분산링 아세이 — 링 평면, 분사홀 상세, 강하관 배치, 급기 분배 검증")
    c.frame_and_title(REV, DATE, "10/15")
    c.head([("재질", "SUS316L"), ("링", f"PCD Ø{G.sparger_pcd_mm:.0f} · Ø{G.sparger_tube_od_mm:.0f} × t{G.sparger_tube_thickness_mm:.1f}"),
            ("분사홀", f"Ø{G.sparger_hole_dia_mm:.1f} × {G.sparger_holes} 하향"),
            ("설치", f"Z{G.sparger_z:.0f}±{G.sparger_z_tolerance_mm:.0f}"),
            ("급기", f"0~{G.air_max_lpm:.0f} L/min"), ("편심", "≤ 3")])

    v = View(82.0, 96.0, 4.0)
    c.circle(v.x(0), v.y(0), v.d(G.sparger_pcd_mm / 2 + G.sparger_tube_od_mm / 2), THICK, "ln")
    c.circle(v.x(0), v.y(0), v.d(G.sparger_pcd_mm / 2 - G.sparger_tube_od_mm / 2), THICK, "ln")
    c.circle(v.x(0), v.y(0), v.d(G.sparger_pcd_mm / 2), THIN, "cl", dash="6 1.2 1.2 1.2")
    c.circle(v.x(0), v.y(0), v.d(G.cone_id_at(G.sparger_z) / 2), THIN, "cl", dash="4 2")
    c.centreline(v.x(-230), v.y(0), v.x(230), v.y(0))
    c.centreline(v.x(0), v.y(-230), v.x(0), v.y(230))
    for i in range(G.sparger_holes):
        a = math.radians(360 / G.sparger_holes * i)
        c.circle(v.x(G.sparger_pcd_mm / 2 * math.cos(a)), v.y(G.sparger_pcd_mm / 2 * math.sin(a)),
                 v.d(4.5), THICK, "ln", fill="var(--ink)")
    c.dim_h(v.x(-G.sparger_pcd_mm / 2), v.x(G.sparger_pcd_mm / 2), v.y(-190),
            f"PCD Ø{fmt(G.sparger_pcd_mm)}")
    c.dim_h(v.x(-G.cone_id_at(G.sparger_z) / 2), v.x(G.cone_id_at(G.sparger_z) / 2), v.y(-208),
            f"콘 ID Ø{fmt(G.cone_id_at(G.sparger_z), 1)} @ Z{fmt(G.sparger_z)}")
    c.arc(v.x(0), v.y(0), v.d(150), 0, 30, THIN, "dl")
    c.text(v.x(160 * math.cos(math.radians(15))), v.y(160 * math.sin(math.radians(15))) + 1.0,
           "30°", T_DIM - 0.2, "middle", "tx2")
    c.leader(v.x(G.sparger_pcd_mm / 2 * math.cos(math.radians(120))),
             v.y(G.sparger_pcd_mm / 2 * math.sin(math.radians(120))), v.x(254), v.y(-160),
             f"분사홀 Ø{fmt(G.sparger_hole_dia_mm, 1)} × {G.sparger_holes}",
             lines=("하향 · 버 제거 필수",))
    c.leader(v.x((G.sparger_pcd_mm / 2 + G.sparger_tube_od_mm / 2) * math.cos(math.radians(60))),
             v.y((G.sparger_pcd_mm / 2 + G.sparger_tube_od_mm / 2) * math.sin(math.radians(60))),
             v.x(260), v.y(200), "롤벤딩 후 맞대기 1 개소",
             lines=("이음은 강하관 반대편에 둔다",))
    c.text(v.x(0), v.y(-232), f"벽 간극 {fmt(G.sparger_wall_clearance_mm, 1)} (편심 3 소진 후 {fmt(G.sparger_wall_clearance_mm - 3, 1)})",
           T_DIM - 0.2, "middle", "tx2")
    c.view_title(16.0, 30.0, "분산링 평면", v.label)

    hv = View(74.0, 212.0, 0.40)
    c.circle(hv.x(0), hv.y(0), hv.d(G.sparger_tube_od_mm / 2), THICK, "ln")
    c.circle(hv.x(0), hv.y(0), hv.d(G.sparger_tube_id_mm / 2), THICK, "ln", dash="2.4 1.2")
    c.poly(hv.pts([(-G.sparger_hole_dia_mm / 2, -G.sparger_tube_od_mm / 2),
                   (G.sparger_hole_dia_mm / 2, -G.sparger_tube_od_mm / 2)]), THICK, "ln")
    c.centreline(hv.x(0), hv.y(11), hv.x(0), hv.y(-16))
    c.poly(hv.pts([(0, -8.0), (-1.6, -13.0), (0, -11.0), (1.6, -13.0)]), THIN, "ln", close=True, fill="var(--ink)")
    c.dim_h(hv.x(-G.sparger_tube_od_mm / 2), hv.x(G.sparger_tube_od_mm / 2), hv.y(10.0),
            f"Ø{fmt(G.sparger_tube_od_mm)}", ext_from=hv.y(6.0))
    c.leader(hv.x(0), hv.y(-G.sparger_tube_od_mm / 2), hv.x(20), hv.y(-9.0),
             f"Ø{fmt(G.sparger_hole_dia_mm, 1)} 하향", lines=("정지 중 분말 역류를 막으려면", "N3 직전에 체크밸브(F-05)"))
    c.view_title(16.0, 176.0, "분사홀 상세", "2.5:1")
    c.text(16.0, 258.0, "공기는 분산 중에만 켜고 정치 시작과 동시에 끈다. 기포 지름은 계산상 Ø3.9 mm 로 "
           "'미세기포'가 아니며, 이 장치에서는 그것이 맞다 — 미세기포는 폴리머를 부선으로 띄워 "
           "밀도차 측정을 오염시킨다.", T_DIM - 0.2, "start", "tx2")

    end = bom_block(c, "F", 208.0, 30.0)
    end = conflict_note(c, 208.0, end + 6.0, ("C4", "C5"), 96)
    check_note(c, 208.0, end + 4.0, ("CHK-03",), 96)


# ==========================================================================
# G — 스키머
# ==========================================================================
def sheet_g() -> None:
    c = sheet("MP50-G", "스키머 아세이", "부상 폴리머를 걸러낸 채로 통째로 들어올린다",
              "1:4", "스키머 아세이 — 바스켓 평면과 단면, 조절봉, 반출 간극 검증")
    c.frame_and_title(REV, DATE, "11/15")
    c.head([("재질", "SUS316L"), ("바스켓", f"Ø{G.skimmer_od_mm:.0f} × H{G.skimmer_height_mm:.0f} × t2"),
            ("타공", "Ø2 · 개공률 30 %"), ("설치", f"Z{G.skimmer_z:.0f}±{G.skimmer_z_tolerance_mm:.0f}"),
            ("반출 간극", f"편측 {G.skimmer_clearance_mm:.0f}"), ("위어 수평도", "≤ 1.0")])

    v = View(90.0, 106.0, 4.0)
    c.circle(v.x(0), v.y(0), v.d(G.tank_id_mm / 2), THIN, "cl", dash="5 2")
    c.circle(v.x(0), v.y(0), v.d(G.skimmer_od_mm / 2), THICK, "ln")
    c.circle(v.x(0), v.y(0), v.d(G.skimmer_od_mm / 2 - 2), THICK, "ln")
    c.centreline(v.x(-240), v.y(0), v.x(240), v.y(0))
    c.centreline(v.x(0), v.y(-240), v.x(0), v.y(240))
    for rr in range(30, 140, 22):
        for i in range(max(6, int(rr / 6))):
            a = math.radians(360 / max(6, int(rr / 6)) * i)
            c.circle(v.x(rr * math.cos(a)), v.y(rr * math.sin(a)), v.d(2.0), THIN, "ln")
    for i in range(3):
        a = math.radians(90 + 120 * i)
        c.circle(v.x(140 * math.cos(a)), v.y(140 * math.sin(a)), v.d(5), THICK, "ln")
    c.dim_h(v.x(-G.skimmer_od_mm / 2), v.x(G.skimmer_od_mm / 2), v.y(-200), f"Ø{fmt(G.skimmer_od_mm)}")
    c.dim_h(v.x(-G.tank_id_mm / 2), v.x(G.tank_id_mm / 2), v.y(-218), f"동체 ID Ø{fmt(G.tank_id_mm)}")
    c.leader(v.x(70), v.y(70), v.x(230), v.y(-110), "타공 Ø2 · 개공률 30 %",
             lines=("염수는 빠지고 폴리머는 남는다",))
    c.leader(v.x(140 * math.cos(math.radians(210))), v.y(140 * math.sin(math.radians(210))),
             v.x(-206), v.y(150), "조절봉 M8 3 개", anchor="end", lines=("커버 관통 · 상하 ±20",))
    c.view_title(16.0, 30.0, "바스켓 평면", v.label)

    sv = View(90.0, 232.0, 4.0)
    for sign in (1.0, -1.0):
        c.poly(sv.pts([(sign * G.skimmer_od_mm / 2, 0), (sign * G.skimmer_od_mm / 2, G.skimmer_height_mm)]),
               THICK, "ln")
        c.poly(sv.pts([(sign * (G.skimmer_od_mm / 2 - 2), 0),
                       (sign * (G.skimmer_od_mm / 2 - 2), G.skimmer_height_mm)]), THICK, "ln")
        c.poly(sv.pts([(sign * 140, G.skimmer_height_mm), (sign * 140, G.skimmer_height_mm + 220)]),
               THICK, "ln", dash="4 2")
    c.poly(sv.pts([(-G.skimmer_od_mm / 2, 0), (G.skimmer_od_mm / 2, 0)]), THICK, "ln")
    c.centreline(sv.x(0), sv.y(-20), sv.x(0), sv.y(260))
    lvl = G.operating_level_z - G.skimmer_z + G.skimmer_height_mm - 12
    c.poly(sv.pts([(-G.tank_id_mm / 2, lvl), (G.tank_id_mm / 2, lvl)]), THIN, "wl", dash="5 1.6 1.6 1.6")
    c.text(sv.x(G.tank_id_mm / 2), sv.y(lvl) - 1.4, "운전 액면", T_DIM - 0.3, "end", "wl-tx")
    c.dim_v(sv.y(0), sv.y(G.skimmer_height_mm), sv.x(G.skimmer_od_mm / 2) + 10.0,
            f"H{fmt(G.skimmer_height_mm)}", left=False)
    c.leader(sv.x(-G.skimmer_od_mm / 2), sv.y(G.skimmer_height_mm), sv.x(-140), sv.y(96.0),
             "위어 — 부상층이 넘어온다", anchor="end", lines=("수평도 1.0 이내",))
    c.leader(sv.x(0), sv.y(0), sv.x(220), sv.y(-8.0), "타공 바닥판 t1.5")
    c.view_title(16.0, 200.0, "바스켓 단면", sv.label)
    c.text(16.0, 276.0, "바스켓을 통째로 들어올려 그대로 칭량·건조로 보낸다 — "
           "Top 회수 질량을 옮겨 담지 않고 잰다.", T_DIM - 0.2, "start", "tx2")

    end = bom_block(c, "G", 208.0, 30.0)
    check_note(c, 208.0, end + 6.0, ("CHK-04",), 96)


# ==========================================================================
# H — 프레임
# ==========================================================================
def sheet_h() -> None:
    c = sheet("MP50-H", "프레임 아세이", "높이는 배출 여유에서 역산했다",
              "1:8", "프레임 아세이 — 정면·측면·평면, 절단 목록, 배출 여유와 전도 검토")
    c.frame_and_title(REV, DATE, "12/15")
    fw, ft, fh = G.frame_width_mm, G.frame_tube_mm, G.frame_height_mm
    c.head([("재질", "SUS304"), ("각파이프", f"□{ft:.0f} × {ft:.0f} × t{G.frame_tube_thickness_mm:.0f}"),
            ("크기", f"{fw:.0f} × {fw:.0f} × H{fh:.0f}"), ("레벨링", "M16 × 4 · ±25"),
            ("수평도", "≤ 0.5 / 550"), ("아세이 질량", f"{BY_CODE['H'].total_kg:.1f} kg")])

    def frame_elevation(v: View, cross: bool) -> None:
        ground = v.y(0)
        c.line(v.x(-fw / 2 - 60), ground, v.x(fw / 2 + 60), ground, FRAME, "ln")
        for gx in range(int(-fw / 2 - 50), int(fw / 2 + 60), 26):
            c.line(v.x(gx), ground, v.x(gx - 16), ground + 3.0, THIN, "ln")
        for sx in (-1, 1):
            x0 = sx * (fw / 2 - ft)
            c.poly(v.pts([(x0, 0), (x0 + sx * ft, 0), (x0 + sx * ft, fh), (x0, fh)]), THICK, "ln", close=True)
            c.poly(v.pts([(sx * (fw / 2 - ft / 2) - 30, -60), (sx * (fw / 2 - ft / 2) + 30, -60),
                          (sx * (fw / 2 - ft / 2) + 30, 0), (sx * (fw / 2 - ft / 2) - 30, 0)]),
                   THICK, "ln", close=True)
        for z in (fh - ft, fh / 2 - ft / 2, 0.0):
            c.poly(v.pts([(-fw / 2 + ft, z), (fw / 2 - ft, z), (fw / 2 - ft, z + ft), (-fw / 2 + ft, z + ft)]),
                   THICK, "ln", close=True)
        if cross:
            for sx in (-1, 1):
                c.poly(v.pts([(sx * 150 - ft / 2, fh - ft), (sx * 150 + ft / 2, fh - ft),
                              (sx * 150 + ft / 2, fh), (sx * 150 - ft / 2, fh)]), THICK, "ln", close=True)

    v = View(64.0, 176.0, 8.0)
    frame_elevation(v, cross=False)
    c.dim_v(v.y(0), v.y(fh), v.x(-fw / 2) - 10.0, f"{fmt(fh)}", ext_from=v.x(-fw / 2))
    c.dim_v(v.y(-60), v.y(0), v.x(-fw / 2) - 10.0, "60 풋")
    c.dim_h(v.x(-fw / 2), v.x(fw / 2), v.y(-96), fmt(fw), ext_from=v.y(-60))
    c.dim_v(v.y(fh / 2 - ft / 2), v.y(fh - ft), v.x(fw / 2) + 10.0, "335", left=False)
    c.view_title(16.0, 30.0, "정면", v.label)

    sv = View(160.0, 176.0, 8.0)
    frame_elevation(sv, cross=True)
    c.view_title(120.0, 30.0, "측면 (크로스레일 방향)", sv.label)
    c.leader(sv.x(150), sv.y(fh - ft / 2), sv.x(fw / 2 + 36), sv.y(fh + 90), "상부 크로스레일 2 개",
             lines=("Y = ±150 — 지지링 Ø480 이", "둘레재에 5 mm 밖에 안 걸린다"))

    pv = View(64.0, 248.0, 8.0)
    c.rect(pv.x(-fw / 2), pv.y(fw / 2), pv.d(fw), pv.d(fw), THICK, "ln")
    c.rect(pv.x(-fw / 2 + ft), pv.y(fw / 2 - ft), pv.d(fw - 2 * ft), pv.d(fw - 2 * ft), THICK, "ln")
    for sy in (-1, 1):
        c.rect(pv.x(-fw / 2 + ft), pv.y(sy * 150 + ft / 2), pv.d(fw - 2 * ft), pv.d(ft), THICK, "ln")
    c.circle(pv.x(0), pv.y(0), pv.d(G.support_ring_od_mm / 2), THIN, "cl", dash="5 2")
    c.circle(pv.x(0), pv.y(0), pv.d(G.shell_od_mm / 2), THIN, "cl", dash="5 2")
    for sx in (-1, 1):
        for sy in (-1, 1):
            c.circle(pv.x(sx * 180), pv.y(sy * 150), pv.d(7), THICK, "ln")
    c.centreline(pv.x(-fw / 2 - 30), pv.y(0), pv.x(fw / 2 + 30), pv.y(0))
    c.centreline(pv.x(0), pv.y(-fw / 2 - 30), pv.x(0), pv.y(fw / 2 + 30))
    c.dim_h(pv.x(-180), pv.x(180), pv.y(-fw / 2 - 16), "360 볼트 간격")
    c.dim_v(pv.y(-150), pv.y(150), pv.x(fw / 2) + 12.0, "300", left=False)
    c.text(pv.x(fw / 2) + 14.0, pv.y(60), f"지지링 Ø{fmt(G.support_ring_od_mm)} 이", T_DIM - 0.2, "start", "tx2")
    c.text(pv.x(fw / 2) + 14.0, pv.y(20), "크로스레일에 앉는다", T_DIM - 0.2, "start", "tx2")
    c.text(pv.x(fw / 2) + 14.0, pv.y(-20), "M12 × 4", T_DIM - 0.2, "start", "tx2")
    c.view_title(16.0, 206.0, "평면", pv.label)

    end = bom_block(c, "H", 208.0, 30.0)
    cut = [["번호", "부재", "길이", "수량", "가공"]]
    cut += [["H-01", f"□{ft:.0f} 기둥", fmt(fh), "4", "양단 직각 절단"],
            ["H-02", f"□{ft:.0f} 둘레재", fmt(fw - ft), "8", "상·하 각 4"],
            ["H-03", f"□{ft:.0f} 크로스레일", fmt(fw - 2 * ft), "2", "Y=±150"],
            ["H-04", f"□{ft:.0f} 중간 보강재", fmt(fw - ft), "4", "Z 중단"]]
    c.view_title(208.0, end + 6.0, "절단 목록")
    e2 = c.table(208.0, end + 10.0, [16.0, 52.0, 22.0, 16.0, 60.0], cut, row_h=5.0,
                 size=T_DIM - 0.2, aligns=["middle", "start", "end", "middle", "start"])
    c.text(208.0, e2 + 5.0, f"총 절단 길이 약 {(4 * fh + 8 * (fw - ft) + 2 * (fw - 2 * ft) + 4 * (fw - ft)) / 1000:.1f} m",
           T_DIM - 0.2, "start", "tx2")
    check_note(c, 208.0, e2 + 11.0, ("CHK-09", "CHK-13"), 96)


# ==========================================================================
# I — 노즐 · 배관 · 밸브
# ==========================================================================
def sheet_i() -> None:
    c = sheet("MP50-I", "노즐 · 배관 · 밸브 계통도", "장입 · 배출 · 급기 · 시료채취",
              "NTS", "배관 계통도 — 장입, 부상물 배출, 급기, 시료채취, 하부 배출 계통과 밸브 목록")
    c.frame_and_title(REV, DATE, "13/15")
    c.head([("배관", "위생 Tri-clamp"), ("재질", "SUS316L / EPDM 가스켓"),
            ("배출", '1½ in 기본 / 2 in 시험'), ("급기", f"0~{G.air_max_lpm:.0f} L/min"),
            ("시료", "5 단 사다리"), ("아세이 질량", f"{BY_CODE['I'].total_kg:.1f} kg")])

    v = View(96.0, 250.0, 5.0)
    c.centreline(v.x(0), v.y(-30), v.x(0), v.y(1000))
    for sign in (1.0, -1.0):
        c.poly(v.pts(vessel_inner(sign)), THICK, "ln")
    c.poly(v.pts([(-G.tank_id_mm / 2, G.shell_top_z), (G.tank_id_mm / 2, G.shell_top_z)]), THICK, "ln")
    draw_liquid(c, v)

    def valve(x: float, y: float, size: float = 3.2, label: str = "") -> None:
        c.poly([(x - size, y - size), (x - size, y + size), (x + size, y - size), (x + size, y + size)],
               THICK, "ln", close=True, fill="var(--paper)")
        if label:
            c.text(x, y - size - 1.6, label, T_DIM - 0.3, "middle", "tx", weight="600")

    def run(pts: list[tuple[float, float]]) -> None:
        c.poly([(v.x(a), v.y(b)) for a, b in pts], THICK, "ln")

    rs = G.tank_id_mm / 2
    run([(-rs, 760), (-350, 760), (-350, 900)])
    valve(v.x(-350), v.y(848), 3.2, "V1")
    c.text(v.x(-350), v.y(920), "급광 투입", T_DIM - 0.2, "middle", "tx2")
    c.text(v.x(-350), v.y(900) - 8.4, '1" TC · N1', T_DIM - 0.4, "middle", "tx2")

    run([(rs, 735), (330, 735), (330, 620)])
    valve(v.x(330), v.y(676), 3.2, "V2")
    c.text(v.x(330), v.y(596), "부상물 배출", T_DIM - 0.2, "middle", "tx2")

    run([(-rs, 520), (-330, 520), (-330, 300)])
    valve(v.x(-330), v.y(420), 3.2, "V4")
    c.circle(v.x(-330), v.y(360), v.d(22), THICK, "ln")
    c.text(v.x(-330), v.y(360) + 1.0, "FI", T_DIM - 0.2, "middle", "tx", weight="600")
    c.poly(v.pts([(-352, 320), (-308, 320), (-330, 296)]), THICK, "ln", close=True)
    c.text(v.x(-330), v.y(276), "급기 (체크밸브 포함)", T_DIM - 0.2, "middle", "tx2")

    for n in NOZZLES:
        if not n.tag.startswith("N4"):
            continue
        run([(rs, n.z_mm), (300, n.z_mm)])
        valve(v.x(300), v.y(n.z_mm), 2.6)
        c.text(v.x(318), v.y(n.z_mm) + 1.0, n.tag, T_DIM - 0.4, "start", "tx2")
    c.text(v.x(330), v.y(760), "시료 사다리 5 단", T_DIM - 0.2, "middle", "tx", weight="600")
    c.text(v.x(330), v.y(736) + 3.0, "V3A~V3E", T_DIM - 0.4, "middle", "tx2")

    bz = G.cone_outlet_z
    run([(0, bz), (0, bz - 200)])
    valve(v.x(0), v.y(bz - 120), 3.8, "V5")
    c.text(v.x(0), v.y(bz - 216), "하부 배출", T_DIM - 0.2, "middle", "tx2")
    c.text(v.x(0), v.y(bz - 232), "2 in 스터브 · 리듀싱 클램프로 1½ in 전환", T_DIM - 0.4, "middle", "tx2")
    c.view_title(16.0, 30.0, "배관 계통도", "NTS")

    rows = [["번호", "밸브", "규격", "형식", "노즐", "용도"]]
    rows += [["V1", "급광 밸브", '1" TC', "볼밸브", "N1", "배치 장입 — 분말 + 염수"],
             ["V2", "부상물 밸브", '1½" TC', "볼밸브", "N2", "폴리머층 경사분리"],
             ["V3A~E", "시료 밸브", '½" TC', "볼밸브 5 개", "N4A~E", "시간별 층 조성 채취"],
             ["V4", "급기 밸브", '½"', "볼 + 니들", "N3", "DOE 0/3/5/8/10 L/min"],
             ["V5", "배출 밸브", '2" TC', "3-pc 볼밸브", "N6", "Si-rich 회수 · 2 in 시험"],
             ["V5R", "배출 밸브 (기본)", '1½" TC', "3-pc + 리듀서", "N6", "기본 조건 · V5 와 교체"],
             ["CV1", "체크밸브", '½"', "위생형", "N3 직전", "정지 중 분말 역류 차단"],
             ["FI", "공기 유량계", "0~20 L/min", "로타미터", "-", "급기량 재현"]]
    c.view_title(208.0, 30.0, "밸브 목록")
    end = c.table(208.0, 34.0, [17.0, 42.0, 22.0, 32.0, 22.0, 57.0], rows, row_h=5.2,
                  size=T_DIM - 0.2, aligns=["middle", "start", "start", "start", "middle", "start"])
    end = bom_block(c, "I", 208.0, end + 8.0, "부품표")
    conflict_note(c, 208.0, end + 4.0, ("C3",), 96)


# ==========================================================================
# J — 계측 · 센서
# ==========================================================================
def sheet_j() -> None:
    c = sheet("MP50-J", "계측 · 센서 아세이", "재는 것은 염수 밀도와 온도지 pH 가 아니다",
              "1:6", "계측 아세이 — 센서 위치, 계기 목록, 제어반 구성, 시료 사다리 피복 검증")
    c.frame_and_title(REV, DATE, "14/15")
    c.head([("제어", "VFD + 타이머"), ("핵심 동작", "임펠러 · 급기 동시 OFF"),
            ("염도", "전도도 0~200 mS/cm"), ("온도", "Pt100 3-wire"),
            ("급기", "로타미터 0~20 L/min"), ("층 높이", "시료 사다리 5 단")])

    v = View(62.0, 250.0, 6.0)
    c.centreline(v.x(0), v.y(-20), v.x(0), v.y(1010))
    for sign in (1.0, -1.0):
        c.poly(v.pts(vessel_inner(sign)), THICK, "ln")
    c.poly(v.pts([(-G.tank_id_mm / 2, G.shell_top_z), (G.tank_id_mm / 2, G.shell_top_z)]), THICK, "ln")
    draw_liquid(c, v)
    for tag, z, side, note in (("J01", 526.0, -1, "전도도 · 삽입 425"), ("J02", 726.0, 1, "온도 · 삽입 225")):
        c.poly(v.pts([(side * 90, G.cover_top_z), (side * 90, z)]), THICK, "ln")
        c.circle(v.x(side * 90), v.y(z), v.d(16), THICK, "ln", fill="var(--ink)")
        bx, by = v.x(side * 250), v.y(1120)
        c.circle(bx, by, 4.6, THICK, "ln", fill="var(--paper)")
        c.text(bx, by + 1.4, tag, T_DIM - 0.2, "middle", "tx", weight="600")
        c.poly([(v.x(side * 90), v.y(G.cover_top_z)), (bx, by + 4.6)], THIN, "dl")
        c.text(bx if side > 0 else bx + 16.0, by - 7.0, note, T_DIM - 0.4, "middle", "tx2")
    for n in NOZZLES:
        if not n.tag.startswith("N4"):
            continue
        c.poly(v.pts([(G.tank_id_mm / 2, n.z_mm), (270, n.z_mm)]), THICK, "ln")
        c.circle(v.x(290), v.y(n.z_mm), 3.2, THICK, "ln", fill="var(--paper)")
        c.text(v.x(320), v.y(n.z_mm) + 1.0, f"{n.tag}  Z{fmt(n.z_mm)}", T_DIM - 0.3, "start", "tx2")
    c.text(v.x(330), v.y(790), "시료 사다리", T_DIM - 0.2, "middle", "tx", weight="600")
    n5 = next(n for n in NOZZLES if n.tag == "N5")
    c.circle(v.x(-G.tank_id_mm / 2), v.y(n5.z_mm), v.d(52), THICK, "ln")
    c.leader(v.x(-G.tank_id_mm / 2 - 46), v.y(n5.z_mm), v.x(-160), v.y(240), "J-04 사이트글라스",
             anchor="end", lines=("Ø100 · 부상층 확인",))
    c.dim_v(v.y(400.0), v.y(720.0), v.x(-236), "320 사다리 피복")
    c.view_title(16.0, 30.0, "센서 배치", v.label)

    rows = [["번호", "계기", "규격", "위치", "무엇을 위해"]]
    where = {"J-01": "커버 B2", "J-02": "커버 B3", "J-03": "급기 라인", "J-04": "동체 N5",
             "J-05": "동체 외면", "J-06": "프레임 측면", "J-07": "제어반"}
    why = {"J-01": "실제 염수 밀도 (염도)", "J-02": "밀도 온도보정", "J-03": "DOE 급기 조건 재현",
           "J-04": "부상층 형성 육안 확인", "J-05": "장입량 확인",
           "J-06": "임펠러·급기 동시 차단", "J-07": "[R] §15 필수 데이터"}
    for prt in BY_CODE["J"].parts:
        rows.append([prt.no, prt.name, prt.spec, where.get(prt.no, "-"), why.get(prt.no, "-")])
    c.view_title(200.0, 30.0, "계기 목록")
    end = c.table(200.0, 34.0, [14.0, 36.0, 62.0, 22.0, 56.0], rows, row_h=5.4,
                  size=T_DIM - 0.3, aligns=["middle", "start", "start", "middle", "start"])

    # --- 제어반 ---
    pv = View(300.0, 200.0, 3.0)
    c.view_title(200.0, end + 12.0, "제어반 J-06 구성", "NTS")
    c.rect(pv.x(0), pv.y(180), pv.d(300), pv.d(180), THICK, "ln")
    for i, lab in enumerate(("전원", "운전", "정지")):
        c.circle(pv.x(40 + i * 70), pv.y(146), pv.d(13), THICK, "ln")
        c.text(pv.x(40 + i * 70), pv.y(120), lab, T_DIM - 0.4, "middle", "tx2")
    for i, (ly, lab, wide) in enumerate(((78, "임펠러 rpm (VFD)", 250), (44, "급기 SOL", 250),
                                         (10, "임펠러 · 급기 동시 OFF", 250))):
        c.rect(pv.x(25), pv.y(ly + 26), pv.d(wide), pv.d(26), THICK, "ln",
               fill="var(--band)" if i == 2 else "none")
        c.text(pv.x(33), pv.y(ly + 8), lab, T_DIM - 0.3, "start", "tx", weight="700" if i == 2 else "")
    c.leader(pv.x(60), pv.y(16), pv.x(150), pv.y(-46), "단일 접점으로 묶는다",
             lines=("둘이 동시에 꺼지지 않으면", "정치 t=0 이 정의되지 않는다"))
    conflict_note(c, 128.0, 96.0, ("C7",), 44)
    check_note(c, 16.0, 264.0, ("CHK-14",), 100)


# ==========================================================================
# K — 체결 · 용접 · 검사
# ==========================================================================
def sheet_k() -> None:
    c = sheet("MP50-K", "체결 · 용접 · 검사 기준", "용접 지도 · 조임 토크 · FAT",
              "1:10", "체결과 용접 기준 — 용접 지도와 용접표, 노즐 관통부 상세, 조임 토크, FAT 시험 단계")
    c.frame_and_title(REV, DATE, "15/15")
    c.head([("용접", "TIG (GTAW) · 316L 용가재"), ("이면", "아르곤 백퍼지 필수"),
            ("내면", "평활 연삭 · 크레비스 없을 것"), ("검사", "PT + 누설 0.2 MPa 30 분"),
            ("후처리", "산세 · 부동태화"), ("체결", "SUS304 A2-70")])

    # --- 좌상 : 노즐 관통부 상세 ---
    dv = View(64.0, 100.0, 0.42)
    c.view_title(16.0, 30.0, "노즐 관통부 상세 (W6)", "2.4:1")
    section_fill(c, dv, dv.pts([(-16, 0), (16, 0), (16, -3), (-16, -3)]), 7.2, "hA", 45)
    for sx in (-1, 1):
        section_fill(c, dv, dv.pts([(sx * 6.35, -3), (sx * 8.35, -3), (sx * 8.35, 20), (sx * 6.35, 20)]),
                     4.8, "hD", -45)
        c.poly(dv.pts([(sx * 8.35, 0), (sx * 11.4, -3), (sx * 8.35, -3)]), THIN, "ln",
               close=True, fill="var(--ink)")
        c.poly(dv.pts([(sx * 6.35, -3), (sx * 4.2, -3), (sx * 6.35, -1.2)]), THIN, "ln",
               close=True, fill="var(--ink)")
    c.dim_h(dv.x(-6.35), dv.x(6.35), dv.y(27), "노즐 ID", ext_from=dv.y(20))
    c.leader(dv.x(11.4), dv.y(-1.5), dv.x(20), dv.y(12), "바깥 필릿 a2 연속")
    c.leader(dv.x(-4.2), dv.y(-2.4), dv.x(-2), dv.y(-24), "안쪽 평활 연삭", anchor="end",
             lines=("set-on 은 링 모양 크레비스를 남긴다",))
    c.text(16.0, 124.0, "관통부는 관을 판 안쪽면까지 넣고 양면 용접한다.", T_DIM - 0.2, "start", "tx2")

    # --- 좌하 : 용접 지도 ---
    v = View(64.0, 254.0, 10.0)
    c.view_title(16.0, 140.0, "용접 지도", v.label)
    c.centreline(v.x(0), v.y(-16), v.x(0), v.y(1000))
    draw_vessel_section(c, v, hatch=False)
    draw_flange_and_cover(c, v, cover=False)
    welds = (("W1", G.shell_top_z), ("W8", 900.0), ("W4", 620.0), ("W6", 760.0),
             ("W7", G.support_ring_z), ("W2", G.shell_bottom_z), ("W5", 200.0),
             ("W3", G.cone_outlet_z))
    for i, (tag, z) in enumerate(welds):
        side = -1 if i % 2 == 0 else 1
        fx = v.x(side * (outer_r_at(z) + 40))
        c.poly([(v.x(side * outer_r_at(z)), v.y(z)), (fx, v.y(z))], THIN, "dl")
        c.circle(fx + side * 3.6, v.y(z), 3.4, THIN, "ln", fill="var(--paper)")
        c.text(fx + side * 3.6, v.y(z) + 1.2, tag, T_DIM - 0.2, "middle", "tx", weight="600")

    # --- 중앙 : 용접표 ---
    rows = [["", "이음", "형식", "개선 · 지시", "검사"]]
    rows += [["W1", "플랜지 ↔ 동체", "필릿 a3 양면", "연속 · 각장 3", "육안 + PT"],
             ["W2", "동체 ↔ 원뿔", "맞대기 전용입", "V70° · 루트갭 1.0 · 백퍼지", "PT 100 %"],
             ["W3", "원뿔 ↔ 스터브", "맞대기 전용입", "t3→t2 1:4 테이퍼 · 백퍼지", "PT 100 %"],
             ["W4", "동체 세로이음", "맞대기 전용입", "V70° · 내면 평활 연삭", "PT 100 %"],
             ["W5", "원뿔 세로이음", "맞대기 전용입", "V70° · 내면 평활 연삭", "PT 100 %"],
             ["W6", "노즐 관통부 (9)", "set-through 양면", "안쪽 평활 · 바깥 필릿 a2", "육안 + PT"],
             ["W7", "지지링 ↔ 동체", "필릿 a4 양면", "연속 · 용접선에서 54 이격", "육안"],
             ["W8", "양중 러그 (3)", "필릿 a5", "연속 · 총질량 기준", "PT"]]
    c.view_title(126.0, 30.0, "용접표")
    end = c.table(126.0, 34.0, [9.0, 38.0, 30.0, 52.0, 22.0], rows, row_h=5.4,
                  size=T_DIM - 0.3, aligns=["middle", "start", "start", "start", "start"])
    for i, line in enumerate(_wrap("오스테나이트계는 이면 백퍼지 없이 용접하면 산화막이 남고, "
                                   "그 자리가 염수에서 먼저 공식(pitting)이 된다. 용접 후 전 표면을 "
                                   "산세하고 부동태화한다.", 60)):
        c.text(126.0, end + 5.0 + i * 4.0, line, T_DIM - 0.2, "start", "tx2")

    insp = [["", "검사 항목", "기준"]]
    insp += [["1", "치수", "MP50-000 공차표"],
             ["2", "진원도", "Ø400 ±2 (내경 4 방향)"],
             ["3", "PT (침투탐상)", "맞대기 100 % · 균열 · 융합불량 없을 것"],
             ["4", "누설", "0.2 MPa 30 분 무강하"],
             ["5", "내면 조도", "Ra ≤ 0.8 · 걸리는 턱 없을 것"],
             ["6", "부동태화", "페록실 시험 청색 반응 없을 것"]]
    c.view_title(126.0, end + 26.0, "검사 항목")
    e2 = c.table(126.0, end + 30.0, [9.0, 46.0, 96.0], insp, row_h=5.4, size=T_DIM - 0.3,
                 aligns=["middle", "start", "start"])
    bom_block(c, "K", 126.0, e2 + 10.0, "체결품 부품표",
              cols=[12.0, 32.0, 46.0, 18.0, 11.0, 14.0, 18.0], notes=False)

    # --- 우측 : 조임 토크 + FAT ---
    tq = [["체결부", "볼트", "수량", "토크", "순서"]]
    tq += [["커버 ↔ 플랜지", G.top_flange_bolt, str(G.top_flange_bolts), "40 N·m", "대각 2 회전"],
           ["지지링 ↔ 프레임", "M12", "4", "40 N·m", "대각"],
           ["임펠러 세트스크류", "M8", "4", "20 N·m", "키 반대편"],
           ["프레임 앵커", "M12 케미컬", "4", "제조사 기준", "레벨링 후"],
           ["스키머 조절봉", "M8", "3", "손 + 이중너트", "위어 수평 후"]]
    c.view_title(292.0, 30.0, "조임 토크")
    e3 = c.table(292.0, 34.0, [34.0, 22.0, 12.0, 26.0, 24.0], tq, row_h=5.4, size=T_DIM - 0.3,
                 aligns=["start", "start", "middle", "start", "start"])

    fat = [["단계", "시험", "합격 기준"]]
    fat += [["T0", "치수 · 용접 · 누설", "치수 공차 내 · PT 지시 없음 · 0.2 MPa 30 분"],
            ["T1", "물 30 L 무부하", "진동 이상 없음 · 전류 안정"],
            ["T2", "물 40 L", "액면 요동 프리보드 내"],
            ["T3", "NaCl + 급기", "12/15/18 wt% 실측 · 분사 균일"],
            ["T4", "블랙파우더 1 kg", "질량수지 오차 ≤ 3 % · 동시 OFF"],
            ["T5", "2 kg", "동일"],
            ["T6", "3 kg", "동일 · 배출시간 기록"],
            ["T7", "핵심조건 3 회 반복", "KPI 재현성 확인"]]
    c.view_title(292.0, e3 + 9.0, "FAT 시험 단계")
    e4 = c.table(292.0, e3 + 13.0, [14.0, 40.0, 64.0], fat, row_h=5.4, size=T_DIM - 0.3,
                 aligns=["middle", "start", "start"])
    c.text(292.0, e4 + 5.0, "출처 — [R] 연구문서 Rev.0 §4 FAT 표.", T_DIM - 0.2, "start", "tx2")
    for i, line in enumerate(_wrap("T3 부터는 실제 염수를 쓴다. NaCl 은 SUS304 에 공식을 일으키므로 "
                                   "매 시험 뒤 청수로 씻어 내고 물기를 말린다. DOE 를 포화 염도까지 "
                                   "넓힐 경우 동체 재질을 SUS316L 로 올려야 한다 (CHK-10).", 48)):
        c.text(292.0, e4 + 12.0 + i * 4.0, line, T_DIM - 0.2, "start", "tx2")


# ==========================================================================
# 아세이 시트 공용 요소
# ==========================================================================
BOM_COLS = [13.0, 40.0, 66.0, 21.0, 11.0, 16.0, 25.0]
BOM_ALIGN = ["middle", "start", "start", "start", "middle", "end", "start"]


def _mass(kg: float) -> str:
    """부품표 질량 표기 — 작은 부품이 0.00 으로 보이지 않게 자릿수를 늘린다."""
    if not kg:
        return "-"
    return f"{kg:.3f}" if kg < 0.01 else f"{kg:.2f}"


def bom_block(c: Canvas, code: str, x: float, y: float, title: str = "부품표",
              cols: list[float] | None = None, notes: bool = True) -> float:
    """아세이 부품표 — 도면 우측에 공통 형식으로 놓는다."""
    a = BY_CODE[code]
    widths = cols or BOM_COLS
    rows = [["번호", "품명", "규격", "재질", "수량", "질량 kg", "상태 · 지시"]]
    for prt in a.parts:
        rows.append([prt.no, prt.name, prt.spec, prt.material, str(prt.qty),
                     _mass(prt.unit_kg), prt.status])
    rows.append(["", f"아세이 {a.code} 계", "", "", str(a.piece_count), f"{a.total_kg:.1f}", ""])
    c.view_title(x, y, title)
    end = c.table(x, y + 4.0, widths, rows, row_h=5.0, size=T_DIM - 0.2, aligns=BOM_ALIGN)
    if not notes:
        return end
    c.view_title(x, end + 9.0, "가공 · 조립 지시")
    yy = end + 13.6
    for prt in a.parts:
        if not prt.note or prt.note == "-":
            continue
        c.text(x, yy, prt.no, T_DIM - 0.2, "start", "tx", weight="600", mono=True)
        for line in _wrap(prt.note, 88):
            c.text(x + 14.0, yy, line, T_DIM - 0.2, "start", "tx2")
            yy += 3.9
        yy += 0.7
    return yy


def _wrap(text: str, width: int) -> list[str]:
    """한글 폭을 2 로 세어 줄바꿈."""
    out, line, w = [], "", 0
    for word in str(text).split(" "):
        ww = sum(2 if ord(ch) > 0x2E80 else 1 for ch in word) + 1
        if w + ww > width and line:
            out.append(line)
            line, w = word, ww
        else:
            line = f"{line} {word}".strip()
            w += ww
    if line:
        out.append(line)
    return out


def check_note(c: Canvas, x: float, y: float, refs: tuple[str, ...], width: int = 92) -> float:
    """해당 시트와 관련된 검증 항목을 근거와 함께 싣는다."""
    c.view_title(x, y, "설계 검증")
    yy = y + 5.4
    for ref in refs:
        chk = next(k for k in CHECKS if k.ref == ref)
        c.text(x, yy, f"{chk.ref} {chk.item}", T_NOTE, "start", "tx", weight="600")
        c.text(x + 92.0, yy, chk.verdict, T_NOTE, "end",
               "warn" if chk.verdict != "PASS" else "tx", weight="600")
        yy += 4.0
        c.text(x, yy, chk.value, T_DIM - 0.2, "start", "tx", mono=True)
        yy += 4.0
        for line in _wrap(chk.detail, width):
            c.text(x, yy, line, T_DIM - 0.3, "start", "tx2")
            yy += 3.7
        yy += 2.6
    return yy


def conflict_note(c: Canvas, x: float, y: float, refs: tuple[str, ...], width: int = 92) -> float:
    """이 아세이에서 원본과 달라진 부분과 그 이유."""
    c.view_title(x, y, "원본과 달라진 점")
    yy = y + 5.4
    for ref in refs:
        cf = next(k for k in CONFLICTS if k.ref == ref)
        c.text(x, yy, f"{cf.ref} {cf.item}", T_NOTE, "start", "tx", weight="600")
        c.text(x + 92.0, yy, cf.severity, T_NOTE, "end",
               "warn" if cf.blocking else "tx2", weight="600")
        yy += 4.0
        for src, val in cf.sources:
            c.text(x, yy, f"{src} {val}", T_DIM - 0.3, "start", "tx2")
            yy += 3.7
        c.text(x, yy, f"→ {cf.resolution}", T_DIM - 0.1, "start", "tx", weight="600")
        yy += 4.2
        for line in _wrap(cf.rationale, width):
            c.text(x, yy, line, T_DIM - 0.3, "start", "tx2")
            yy += 3.7
        yy += 2.6
    return yy


# ==========================================================================
# HTML 출력
# ==========================================================================
STYLE = """
:root{
  color-scheme:light dark;
  --bg:#E8ECEF;--surface:#FFFFFF;--surface-2:#F4F7F9;
  --paper:#FFFFFF;--band:#EDF1F4;
  --ink:#141B21;--ink-2:#4E5C67;--ink-3:#7C8A95;
  --line:#9AA6B1;--rule:#D2D9DF;
  --dl:#5C6A75;--cl:#8C6BA8;
  --brine:#1F6E8C;--wl:#12607C;
  --warn:#9C3A22;--ok:#1F6B45;--hold:#8A5A0B;
  --sans:"IBM Plex Sans KR",system-ui,-apple-system,"Malgun Gothic",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0D1216;--surface:#141B21;--surface-2:#1A232A;
    --paper:#171F26;--band:#202A32;
    --ink:#E4EAEF;--ink-2:#A2B0BB;--ink-3:#78868F;
    --line:#6B7A85;--rule:#2A353D;
    --dl:#93A3AE;--cl:#B394D0;
    --brine:#57B6D8;--wl:#6FC6E4;
    --warn:#E8836A;--ok:#5FBF8E;--hold:#DDA83B;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#0D1216;--surface:#141B21;--surface-2:#1A232A;
  --paper:#171F26;--band:#202A32;
  --ink:#E4EAEF;--ink-2:#A2B0BB;--ink-3:#78868F;
  --line:#6B7A85;--rule:#2A353D;
  --dl:#93A3AE;--cl:#B394D0;
  --brine:#57B6D8;--wl:#6FC6E4;
  --warn:#E8836A;--ok:#5FBF8E;--hold:#DDA83B;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-weight:400;line-height:1.65;-webkit-text-size-adjust:100%}
.wrap{max-width:1360px;margin:0 auto;padding:32px 16px 72px}
header.doc{padding:28px 0 20px;border-bottom:2px solid var(--ink);margin-bottom:8px}
header.doc h1{font-size:clamp(21px,3.4vw,30px);line-height:1.25;margin:0 0 6px;letter-spacing:-.01em}
header.doc p{margin:0;color:var(--ink-2);font-size:14px;max-width:76ch}
.meta{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:14px;font-size:12.5px;
  color:var(--ink-2);font-family:var(--mono)}
.meta b{color:var(--ink);font-weight:600}
.toc{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:6px;
  margin:22px 0 8px;padding:0;list-style:none}
.toc a{display:block;padding:8px 10px;background:var(--surface);border:1px solid var(--rule);
  border-radius:5px;text-decoration:none;color:var(--ink);font-size:12.5px}
.toc a:hover{border-color:var(--line);background:var(--surface-2)}
.toc code{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);display:block}
figure.sheet{margin:34px 0 0;background:var(--surface);border:1px solid var(--rule);
  border-radius:6px;overflow:hidden}
figure.sheet svg{display:block;width:100%;height:auto;background:var(--paper)}
figcaption{padding:13px 16px;border-top:1px solid var(--rule);background:var(--surface-2);
  font-size:13px;color:var(--ink-2)}
figcaption b{color:var(--ink);font-weight:600}
section.prose{margin:44px 0 0}
section.prose h2{font-size:19px;margin:0 0 10px;padding-bottom:7px;border-bottom:1px solid var(--rule)}
section.prose h3{font-size:14.5px;margin:22px 0 5px}
section.prose p{margin:0 0 10px;font-size:13.5px;color:var(--ink-2);max-width:88ch}
section.prose ul{margin:0 0 12px;padding-left:20px;font-size:13.5px;color:var(--ink-2);max-width:88ch}
table.reg{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 18px}
table.reg th,table.reg td{border:1px solid var(--rule);padding:7px 9px;text-align:left;vertical-align:top}
table.reg th{background:var(--band);font-weight:600;color:var(--ink)}
table.reg td{color:var(--ink-2)}
table.reg td.k{font-family:var(--mono);white-space:nowrap;color:var(--ink);font-weight:600}
.tag{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11px;
  font-family:var(--mono);font-weight:600;border:1px solid currentColor}
.tag.b{color:var(--warn)}.tag.m{color:var(--hold)}.tag.n{color:var(--ink-3)}
.tag.pass{color:var(--ok)}.tag.warn{color:var(--hold)}.tag.fail{color:var(--warn)}
/* --- SVG 도면 --- */
svg .ln{stroke:var(--ink);fill:none;stroke-linecap:round;stroke-linejoin:round}
svg .dl{stroke:var(--dl);fill:none;stroke-linecap:round}
svg .cl{stroke:var(--cl);fill:none;stroke-linecap:round}
svg .wl{stroke:var(--wl);fill:none}
svg .fill-ink{fill:var(--ink);stroke:none;color:var(--ink)}
svg text{font-family:var(--sans);fill:var(--ink)}
svg .tx{fill:var(--ink)}
svg .tx2{fill:var(--ink-2)}
svg .wl-tx{fill:var(--wl);font-weight:600}
svg .warn{fill:var(--warn);font-weight:600}
svg .warn-ln{stroke:var(--warn);fill:none}
svg .mono{font-family:var(--mono)}
@media (max-width:720px){
  .wrap{padding:20px 10px 48px}
  figure.sheet{border-radius:4px}
}
@media print{
  body{background:#fff}
  .wrap{max-width:none;padding:0}
  header.doc,.toc,section.prose{display:none}
  figure.sheet{border:none;margin:0;page-break-after:always}
  figcaption{display:none}
}
"""


def _severity_tag(sev: str) -> str:
    cls = {"BLOCKING": "b", "MAJOR": "m"}.get(sev, "n")
    return f'<span class="tag {cls}">{sev}</span>'


def _verdict_tag(v: str) -> str:
    return f'<span class="tag {v.lower()}">{v}</span>'


CAPTIONS: dict[str, str] = {}


def build_html() -> str:
    checks_rows = "".join(
        f"<tr><td class=\"k\">{c.ref}</td><td>{esc(c.kind)}</td><td>{esc(c.item)}</td>"
        f"<td>{esc(c.criterion)}</td><td class=\"k\">{esc(c.value)}</td>"
        f"<td>{_verdict_tag(c.verdict)}</td><td>{esc(c.detail)}</td></tr>"
        for c in CHECKS
    )
    conflict_rows = "".join(
        f"<tr><td class=\"k\">{cf.ref}</td><td>{esc(cf.item)}</td><td>{_severity_tag(cf.severity)}</td>"
        f"<td>" + "<br>".join(f"<b>{esc(s)}</b> {esc(val)}" for s, val in cf.sources) + "</td>"
        f"<td class=\"k\">{esc(cf.resolution)}</td><td>{esc(cf.rationale)}</td>"
        f"<td>{'승인 필요' if cf.approval == 'PROPOSED' else '확정'}</td></tr>"
        for cf in CONFLICTS
    )
    toc = "".join(
        f'<li><a href="#{s.number}"><code>{s.number}</code>{esc(s.title)}</a></li>'
        for s in SHEETS
    )
    figures = "".join(
        f'<figure class="sheet" id="{s.number}">{s.render()}'
        f"<figcaption><b>{esc(s.number)} · {esc(s.title)}</b> — "
        f"{esc(CAPTIONS.get(s.number, s.subtitle))}</figcaption></figure>"
        for s in SHEETS
    )
    blocking = sum(1 for cf in CONFLICTS if cf.blocking)
    proposed = sum(1 for cf in CONFLICTS if cf.approval == "PROPOSED")
    warns = sum(1 for c in CHECKS if c.verdict == "WARN")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="MP-50 폐태양광 블랙파우더 염수 밀도분리 파일럿 장치의 아세이별 제작도면 {len(SHEETS)}매 — 기준좌표, 전체 조립도, 탱크·커버·구동·교반축·배플·분산링·스키머·프레임·배관·계측·체결 아세이, 전개도와 용접·검사 기준.">
<title>MP-50 아세이별 제작도면</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&amp;family=IBM+Plex+Sans+KR:wght@300;400;500;600;700&amp;display=swap">
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
<header class="doc">
  <h1>MP-50 아세이별 제작도면</h1>
  <p>폐태양광 블랙파우더(31~75 µm)에서 EVA·백시트를 염수 밀도차로 걷어내는
     소형 파일럿 장치. 도면 {len(SHEETS)}매는 <code>mp50_separator</code> 의 확정 기하에서
     생성되므로, 기준치수를 고치면 전 도면이 함께 움직인다.</p>
  <div class="meta">
    <span>Rev <b>{REV}</b></span><span>작성 <b>{DATE}</b></span>
    <span>전용적 <b>{G.total_volume_l:.2f} L</b></span>
    <span>운전 장입 <b>{G.operating_volume_l:.1f} L</b></span>
    <span>건조질량 <b>{dry_mass_kg():.0f} kg</b></span>
    <span>아세이 <b>{len(ASSEMBLIES)}종</b></span>
    <span>부품 <b>{sum(a.piece_count for a in ASSEMBLIES)}개</b></span>
  </div>
</header>
<ul class="toc">{toc}</ul>
{figures}
<section class="prose">
  <h2>원본 치수 충돌과 해결 근거</h2>
  <p>MP-50 의 치수는 세 문서에 흩어져 있고 셋이 서로 다르다 — <b>[R]</b> 연구문서 Rev.0(2026-09-10),
     <b>[D1]</b> 도면 MP-50-P0-001(2026-09-09), <b>[D2]</b> 도면 MP50-DR-000(2025-07-05).
     어느 하나를 골라 그대로 옮기면 제작이 되지 않는다. 아래 {len(CONFLICTS)}건 중
     <b>{blocking}건은 그대로 두면 조립 자체가 불가능</b>하고,
     {proposed}건은 공학적 판단이 들어갔으므로 발주 전 승인이 필요하다.</p>
  <table class="reg">
    <thead><tr><th>번호</th><th>항목</th><th>등급</th><th>원본</th><th>채택값</th><th>근거</th><th>상태</th></tr></thead>
    <tbody>{conflict_rows}</tbody>
  </table>

  <h2>설계 검증</h2>
  <p>도면이 "제작 가능" 하다는 말에는 두 가지가 있다. <b>조립</b> 항목은 부품끼리 부딪히지 않고
     원뿔이 닫히고 빼낼 것이 개구를 통과하는지를 보며, 전부 통과해야 발주할 수 있다.
     <b>기능</b> 항목은 만들었을 때 목적을 달성하는지를 본다. 기능 항목의 WARN {warns}건은
     장치를 고치라는 뜻이 아니라 <b>운전조건과 시험계획을 고치라</b>는 뜻이다.</p>
  <table class="reg">
    <thead><tr><th>번호</th><th>구분</th><th>항목</th><th>기준</th><th>결과</th><th>판정</th><th>내용</th></tr></thead>
    <tbody>{checks_rows}</tbody>
  </table>
</section>
</div>
</body>
</html>
"""


def main() -> None:
    sheet_000()
    sheet_100()
    for fn in _SHEET_FUNCTIONS:
        fn()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_html(), encoding="utf-8")
    print(f"{OUT} — {len(SHEETS)} 매, {OUT.stat().st_size // 1024} KB")


_SHEET_FUNCTIONS: list = [sheet_a1, sheet_a2, sheet_a3, sheet_b, sheet_c, sheet_d, sheet_e, sheet_f, sheet_g, sheet_h, sheet_i, sheet_j, sheet_k]

if __name__ == "__main__":
    main()
