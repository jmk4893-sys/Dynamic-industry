# -*- coding: utf-8 -*-
"""투입 구간 상세도 — FL-101 반입부터 RB-101 이 손을 떼는 JB-201 인계까지.

통합 설계도(`docs/drawings/pv-preprocess-plant.html`)는 플랜트 전체를 한 장에
담는다. 투입 구간만 떼어 자세히 보려면 그 안에서 값을 찾아 다녀야 하고,
찾은 값을 손으로 옮겨 적는 순간 두 문서가 갈라진다. 그래서 이 상세도는
**손으로 쓰지 않는다** — 배치·기구학·캠페인·서보·전기·비전·안전·장착 모델과
통합 설계도의 부품표·인터페이스 표에서 값을 읽어 찍어 낸다.

    PYTHONPATH=src python tools/build_infeed_detail.py

멱등이다. `tests/test_pv_infeed_detail.py` 가 커밋된 파일과 생성 결과를 견준다.

범위는 **투입 무리** 하나다: FL-101 지게차 → LFT-101A/B 듀얼 팔레트 리프트 →
SE/VS-101 높이·비전 판정 → BFC-101A/B 단장 분리·수직 승강·180° 반전 →
RB-101 로봇 직접 픽업 → PT-101 3-2-1 정렬정반 → JB-201 축적·인계 런. 로봇이
패널을 놓고 손을 뗀 뒤 JBR-201 이 받는 지점에서 끝나며, JBR-201 부터는
범위 밖이다.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import (campaign, drives, electrical, kinematics, layout,  # noqa: E402
                           maintain, mounting, reliability, safety, servos, vision)

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-infeed-detail.html"

SHEET_NO = "PV-INFEED-101-DET-2001"

# ── 범위 ────────────────────────────────────────────────────────────────
#: 이 상세도가 다루는 셀. 존 표의 처음 두 존이다.
SCOPE_ZONES: tuple[str, ...] = ("afu", "robot")

#: 통합 설계도 부품표에서 가져오는 품번 — 투입 무리에 속한 것 전부.
SCOPE_PART_NUMBERS: tuple[str, ...] = (
    "AFU-FL-101", "AFU-LFT-101", "AFU-HPU-101", "AFU-AVM-101", "AFU-OC-101",
    "AFU-SE-101", "AFU-SF-101", "AFU-BW-101", "AFU-VG-101", "AFU-VS-101",
    "AFU-BFC-101", "AFU-BLR-101", "AFU-BER-101", "AFU-BGD-101", "AFU-CD-101",
    "AFU-RB-101", "AFU-EOAT-101", "AFU-PT-101", "AFU-AL-101", "AFU-RJ-101",
    "AFU-VAC-101",
)

#: 통합 설계도 인터페이스 표에서 그대로 옮기는 행 — 투입 구간의 운전·허가 조건.
SCOPE_INTERFACE_ROWS: tuple[str, ...] = (
    "팔레트 투입", "A/B 운전", "고정 픽업면", "무컨베이어 구역", "최대 패널",
    "벽체·천장 비전", "투입 로봇", "칸별 반전", "정렬 정반", "기계 연결",
    "BFC 반전 허가", "로봇 진입 허가", "리프트 인덱스", "핸드셰이크", "패킷 v1.2",
)

#: 이 구간의 위험원과 안전기능 (safety.py 의 셀 키).
SCOPE_HAZARD_CELLS: tuple[str, ...] = ("afu", "bfc", "robot")

#: 이 구간에 급전하는 분전반.
SCOPE_PANELS: tuple[str, ...] = ("LP-AFU", "LP-RB")

#: 2D 시트 원점의 플랜트 X (mm). AFU 시트는 3D 월드 x −19,100, BFC 시트는 반전축.
AFU_SHEET_ORIGIN_MM = 5_650
#: 플랜트 Y 좌표 = 라인 중심 + 3D z. 라인 중심은 장비 밴드의 한가운데다.
LINE_CENTER_Y_MM = layout.MACHINE_BAND_Y_MM // 2

#: 3D 공정시계에서 읽은 로봇 구간 시각 (s). kinematics.PATH 가 24.0 s 에서 끝나고
#: campaign.INFEED_S(40.0) 에서 JBR 이 받는다 — 그 사이가 로봇의 몫이다.
ROBOT_CLOCK: tuple[tuple[float, float, str], ...] = (
    (24.0, 25.4, "RB-101 EOAT 4구역 진공 흡착 — 로봇 진입 허가 조건 충족 후"),
    (25.4, 30.5, "인계점(적층 직상, 2,100) → PT-101 위(이송면 950) 이송 — 로봇 존으로 X 4,440·Z −1,600"),
    (30.5, 33.5, "안착 · 진공 순차 해제 · 손목 추종 — 스톱·푸셔가 패널을 기준면으로 끈다"),
    (33.5, 37.0, "PT-101 3-2-1 정렬 완료 — 좌표시드 확정 (34–37 s)"),
    (37.0, 40.0, "JB-201 인계 핸드셰이크 — PANEL_OFFER … TRANSFER_COMPLETE, 로봇 후퇴"),
)

#: 판정·파지 준비 구간 (s) — 3D 공정시계 0 … PATH 시작.
PREP_CLOCK: tuple[tuple[float, float, str], ...] = (
    (0.0, 7.5, "LFT 도킹·SE-101 높이 추종 · VS-101 통합 2D＋3D 판정(유리면 방향·외곽·겹장·3분류) · 분리헤드 진공 파지"),
)


# ── 통합 설계도에서 읽기 ───────────────────────────────────────────────
def plant_text() -> str:
    return PLANT.read_text(encoding="utf-8")


def drawing_revision(text: str) -> str:
    return re.search(r"DRAWING_REVISION = '([^']+)'", text).group(1)


def _one_catalog_row(text: str, tag: str) -> list[list[object]]:
    pos = 0
    while True:
        start = text.find(f'["{tag}"', pos)
        if start < 0:
            raise SystemExit(f"✗ 부품표에 {tag} 가 없다")
        depth, j = 0, start
        while True:
            ch = text[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        row = json.loads(text[start:j + 1])
        if len(row) >= 10:
            return [row]
        pos = j


def catalog(text: str) -> list[list[object]]:
    return [row for tag in SCOPE_PART_NUMBERS for row in _one_catalog_row(text, tag)]


def interface_rows(text: str) -> list[tuple[str, str]]:
    """AFU-101–JBR-201 연결 인터페이스 표의 행을 이름으로 꺼낸다 (본문 HTML 그대로)."""
    out = []
    for name in SCOPE_INTERFACE_ROWS:
        m = re.search(r"<tr><th>%s</th><td>(.*?)</td></tr>" % re.escape(name), text, re.S)
        if not m:
            raise SystemExit(f"✗ 인터페이스 표에 '{name}' 행이 없다")
        out.append((name, m.group(1)))
    return out


# ── 값 ──────────────────────────────────────────────────────────────────
def n(v: float) -> str:
    """천 단위 구분 — 도면 표기."""
    if isinstance(v, float) and v != int(v):
        return f"{v:,.1f}"
    return f"{int(round(v)):,}"


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def zones() -> dict[str, layout.Zone]:
    return {z.key: z for z in layout.build_zones()}


def plant_y(z_mm: float) -> float:
    return LINE_CENTER_Y_MM + z_mm


# ── SVG ─────────────────────────────────────────────────────────────────
class Sheet:
    """플랜트 mm 좌표를 화면 px 로 옮기는 작은 제도판."""

    def __init__(self, x0: float, x1: float, y0: float, y1: float, width: int,
                 pad: tuple[int, int, int, int] = (36, 30, 36, 30), flip_y: bool = False):
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.pad = pad          # top, right, bottom, left
        self.width = width
        self.scale = (width - pad[1] - pad[3]) / (x1 - x0)
        self.height = int((y1 - y0) * self.scale) + pad[0] + pad[2]
        self.flip_y = flip_y
        self.parts: list[str] = []

    def X(self, x: float) -> float:
        return round(self.pad[3] + (x - self.x0) * self.scale, 1)

    def Y(self, y: float) -> float:
        if self.flip_y:
            return round(self.pad[0] + (self.y1 - y) * self.scale, 1)
        return round(self.pad[0] + (y - self.y0) * self.scale, 1)

    def rect(self, x0: float, x1: float, y0: float, y1: float, cls: str, title: str | None = None,
             rx: float = 0) -> None:
        xa, xb = sorted((self.X(x0), self.X(x1)))
        ya, yb = sorted((self.Y(y0), self.Y(y1)))
        t = f"<title>{esc(title)}</title>" if title else ""
        self.parts.append(
            f'<rect class="{cls}" x="{xa}" y="{ya}" width="{round(xb - xa, 1)}" '
            f'height="{round(yb - ya, 1)}" rx="{rx}">{t}</rect>')

    def circle(self, x: float, y: float, r_mm: float, cls: str, title: str | None = None) -> None:
        t = f"<title>{esc(title)}</title>" if title else ""
        self.parts.append(f'<circle class="{cls}" cx="{self.X(x)}" cy="{self.Y(y)}" '
                          f'r="{round(r_mm * self.scale, 1)}">{t}</circle>')

    def ellipse(self, x: float, y: float, rx_mm: float, ry_mm: float, cls: str,
                title: str | None = None) -> None:
        """두 축 반경이 다른 형상 — 링을 어느 쪽에서 보든 한 식으로 그린다."""
        t = f"<title>{esc(title)}</title>" if title else ""
        self.parts.append(f'<ellipse class="{cls}" cx="{self.X(x)}" cy="{self.Y(y)}" '
                          f'rx="{round(rx_mm * self.scale, 1)}" '
                          f'ry="{round(ry_mm * self.scale, 1)}">{t}</ellipse>')

    def line(self, x0: float, y0: float, x1: float, y1: float, cls: str) -> None:
        self.parts.append(f'<line class="{cls}" x1="{self.X(x0)}" y1="{self.Y(y0)}" '
                          f'x2="{self.X(x1)}" y2="{self.Y(y1)}"/>')

    def poly(self, pts: list[tuple[float, float]], cls: str, title: str | None = None) -> None:
        t = f"<title>{esc(title)}</title>" if title else ""
        d = " ".join(f"{self.X(x)},{self.Y(y)}" for x, y in pts)
        self.parts.append(f'<polyline class="{cls}" points="{d}">{t}</polyline>')

    def text(self, x: float, y: float, s: str, cls: str = "lbl", anchor: str = "start",
             dx: float = 0, dy: float = 0, rotate: float | None = None) -> None:
        px, py = self.X(x) + dx, self.Y(y) + dy
        tr = f' transform="rotate({rotate} {px} {py})"' if rotate is not None else ""
        self.parts.append(f'<text class="{cls}" x="{px}" y="{py}" text-anchor="{anchor}"{tr}>{esc(s)}</text>')

    def dim_x(self, x0: float, x1: float, y: float, label: str, above: bool = True) -> None:
        """X 치수선 — 도면 관례대로 끝단 틱과 가운데 글자."""
        xa, xb, py = self.X(x0), self.X(x1), self.Y(y)
        self.parts.append(f'<line class="dim" x1="{xa}" y1="{py}" x2="{xb}" y2="{py}"/>')
        for px in (xa, xb):
            self.parts.append(f'<line class="dim" x1="{px}" y1="{py - 5}" x2="{px}" y2="{py + 5}"/>')
        self.parts.append(f'<text class="dimt" x="{round((xa + xb) / 2, 1)}" '
                          f'y="{py + (-4 if above else 12)}" text-anchor="middle">{esc(label)}</text>')

    def dim_y(self, y0: float, y1: float, x: float, label: str, right: bool = True) -> None:
        ya, yb, px = self.Y(y0), self.Y(y1), self.X(x)
        self.parts.append(f'<line class="dim" x1="{px}" y1="{ya}" x2="{px}" y2="{yb}"/>')
        for py in (ya, yb):
            self.parts.append(f'<line class="dim" x1="{px - 5}" y1="{py}" x2="{px + 5}" y2="{py}"/>')
        ty = round((ya + yb) / 2, 1)
        self.parts.append(f'<text class="dimt" x="{px + (7 if right else -7)}" y="{ty + 3}" '
                          f'text-anchor="{"start" if right else "end"}">{esc(label)}</text>')

    def svg(self, label: str) -> str:
        return (f'<svg class="sheet" viewBox="0 0 {self.width} {self.height}" role="img" '
                f'aria-label="{esc(label)}">' + "".join(self.parts) + "</svg>")


def plan_view() -> str:
    """평면 배치 — 존·리프트·벽체·반전 베이·로봇·정반·축적런을 플랜트 좌표로."""
    Z = zones()
    afu, robot, jbr = Z["afu"], Z["robot"], Z["jbr"]
    pick = layout.bfc_pickup_x_mm()
    ped = layout.robot_pedestal_x_mm()
    pt = layout.pt_place_x_mm()
    pt0, pt1 = layout.pt_deck_span_mm()
    ac0, ac1 = layout.accumulator_span_mm()
    band, aisle = layout.MACHINE_BAND_Y_MM, layout.AISLE_WIDTH_MM
    s = Sheet(-3_700, 11_400, -400, band + aisle + 250, 1120, pad=(34, 24, 30, 24))

    # 장비 밴드·통로·존
    s.rect(0, 11_400, 0, band, "band")
    s.rect(0, 11_400, band, band + aisle, "aisle")
    s.text(11_300, band + aisle / 2, f"보행·정비 통로 {n(aisle)}", "lbl-muted", "end", dy=4)
    for z, cls in ((afu, "zone zone-in"), (robot, "zone zone-in")):
        s.rect(z.x0_mm, z.x1_mm, z.y0_mm, z.y1_mm, cls, f"{z.label} 존 {n(z.length_mm)} × {n(z.width_mm)}")
    # 하류(JBR-201 부터)는 범위 밖이라 장비도 존도 그리지 않는다 — 방향만 적는다.
    s.text(11_300, jbr.y0_mm + 260, "→ JBR-201 (범위 밖)", "lbl-muted", "end")
    s.text(afu.x0_mm + 120, band - 220, f"afu 존 · {afu.label}", "lbl-zone")
    s.text(robot.x0_mm + 120, robot.y1_mm + 300, f"robot 존 · {robot.label}", "lbl-zone")

    # 존 넘침(설계) — BFC 하류 기둥 발판이 로봇 존으로 물린다
    over = layout.zone_overlap_mm("afu")
    s.rect(afu.x1_mm, afu.x1_mm + over, robot.y0_mm, robot.y1_mm, "overlap",
           f"afu → robot 넘침 {n(over)} (설계 — 로봇 도달 사슬)")

    # 지게차 진입 차로 (Bay A/B) 와 FL-101 참조 외형
    phx, phz = kinematics.panel_half_xz_mm()
    for sign, bay in ((-1, "A"), (1, "B")):
        zc = sign * layout.BFC_PICKUP_Z_MM
        s.rect(-3_600, pick - phx - 200, plant_y(zc - phz - 100), plant_y(zc + phz + 100), "lane",
               f"지게차 진입 차로 Bay {bay} — 팔레트 폭 {n(phz * 2)} + 여유")
    s.rect(-3_500, -400, plant_y(-layout.BFC_PICKUP_Z_MM - 600), plant_y(-layout.BFC_PICKUP_Z_MM + 600),
           "ref", "FL-101 2.5 t 전동 지게차 3,100 × 1,200 (반입 위치 참조)")
    s.text(-3_450, plant_y(-layout.BFC_PICKUP_Z_MM), "FL-101", "lbl", dy=4)
    s.dim_x(-3_000, 0, plant_y(-layout.BFC_PICKUP_Z_MM - 1_050), "지게차 진입 3,000 MIN")

    # 리프트·적층·벽체·비전보
    for sign, bay in ((-1, "A"), (1, "B")):
        zc = sign * layout.BFC_PICKUP_Z_MM
        dkx, dkz = kinematics.plan_xz(1_450, 900)
        s.rect(pick - dkx, pick + dkx, plant_y(zc - dkz), plant_y(zc + dkz), "base",
               f"LFT-101{bay} 유압 시저 승강대 {n(dkx * 2)} × {n(dkz * 2)}")
        s.rect(pick - phx, pick + phx, plant_y(zc - phz), plant_y(zc + phz), "panel",
               f"30장 적층 {bay} {n(phx * 2)} × {n(phz * 2)} — 장변이 반전축과 나란 · 최상단이 픽업면 1,880")
        s.text(pick, plant_y(zc), f"LFT-101{bay} · 30장 적층", "lbl-panel", "middle", dy=24)
        # 반전 드럼(엔드링) 은 적층 바로 위 — 평면에서는 두 링의 자취
        rhx, rhz = kinematics.ring_half_xz_mm()
        for a in kinematics.ring_plane_offsets_mm():
            rx, rz = kinematics.plan_xz(a, 0)
            s.rect(pick + rx - rhx, pick + rx + rhx, plant_y(zc + rz - rhz), plant_y(zc + rz + rhz), "ring",
                   f"BFC-101{bay} 오픈센터 엔드링 ⌀1,980 (적층 직상, 축 H {n(kinematics.FLIP_AXIS_MM)})")
        # 포탈 기둥 4본 — 통과대역 밖
        chx, chz = kinematics.column_half_xz_mm()
        for cx, cz in kinematics.column_offsets_xz_mm(sign):
            s.rect(pick + cx - chx, pick + cx + chx, plant_y(zc + cz - chz), plant_y(zc + cz + chz),
                   "column", f"BFC-101{bay} 포탈 기둥·LM가이드 180 × 240")
    ow = kinematics.outer_wall_z_mm()
    walls = ((-ow, kinematics.OUTER_WALL_T_MM, "외측벽 A"),
             (0, kinematics.CENTRE_WALL_T_MM, "중앙 백투백벽"),
             (ow, kinematics.OUTER_WALL_T_MM, "외측벽 B"))
    for zc, th, name in walls:
        s.rect(AFU_SHEET_ORIGIN_MM - 1_620 - 1_330, AFU_SHEET_ORIGIN_MM - 1_620 + 1_330,
               plant_y(zc - th / 2), plant_y(zc + th / 2), "wall", f"BW-101 {name} 2,660 × {th}")
    s.text(AFU_SHEET_ORIGIN_MM - 1_620, plant_y(0), "BW-101 중앙벽 · CD-101 포획빔 수납", "lbl", "middle", dy=-9)
    vg = AFU_SHEET_ORIGIN_MM - 2_310
    s.rect(vg - 1_240, vg + 1_240, plant_y(-3_350), plant_y(3_350), "beam",
           "VG-101 독립 방진 비전보 2,480 × 6,700 (상단 5,150)")
    s.text(vg, plant_y(-3_350), "VG-101 비전보 (천장)", "lbl-muted", "middle", dy=-5)
    for sign in (-1, 1):
        zc = sign * layout.BFC_PICKUP_Z_MM
        s.circle(pick, plant_y(zc), 190, "sensor", f"VS-101{'A' if sign < 0 else 'B'} 통합 2D＋3D 헤드 (H 4,820)")
    # 유틸리티
    hpu = AFU_SHEET_ORIGIN_MM - 3_700
    s.rect(hpu - 300, hpu + 300, plant_y(300 - 400), plant_y(300 + 400), "util", "HPU-101 리프트 유압유닛 600 × 800")
    s.text(hpu, plant_y(300), "HPU-101", "lbl-small", "middle", dy=3)
    vac = afu.x0_mm + 900
    s.rect(vac - 470, vac + 470, plant_y(-420), plant_y(420), "util", "VAC-101 이중 진공 스키드 940 × 840")
    s.text(vac, plant_y(0), "VAC-101", "lbl-small", "middle", dy=3)

    # 로봇·리젝트 랙·정반·축적런
    s.circle(ped, plant_y(0), layout.ROBOT_REACH_MM, "reach", f"RB-101 도달 반경 {n(layout.ROBOT_REACH_MM)}")
    s.circle(ped, plant_y(0), 550, "pedestal", "RB-101 650 mm 페데스털 Ø1,100")
    s.text(ped, plant_y(0), "RB-101", "lbl", "middle", dy=4)
    for sign, bay in ((-1, "A"), (1, "B")):
        zc = sign * layout.REJECT_RACK_Z_MM
        xr = ped + layout.REJECT_RACK_DX_MM
        s.rect(xr - 800, xr + 800, plant_y(zc - 350), plant_y(zc + 350), "rack",
               f"AFU-RJ-101 전손 리젝트 랙 {bay} 1,600 × 700 (도달 {n(layout.robot_reject_distance_mm())})")
        s.text(xr, plant_y(zc), f"RJ-101{bay}", "lbl-small", "middle", dy=3)
    tx, ty, _ = layout.PT_TABLE_MM
    s.rect(pt - tx / 2, pt + tx / 2, plant_y(-ty / 2), plant_y(ty / 2), "base",
           f"PT-101 3-2-1 정렬정반 {n(tx)} × {n(ty)} × H900")
    s.rect(pt0, pt1, plant_y(-layout.PT_DECK_MM[1] / 2), plant_y(layout.PT_DECK_MM[1] / 2), "deck",
           f"PT-101 출구 정반 {n(layout.PT_DECK_MM[0])} × {n(layout.PT_DECK_MM[1])} (이송면 950)")
    s.rect(ac0, ac1, plant_y(-1_040), plant_y(1_040), "guard",
           f"JB-201 축적·인계 런 {n(layout.ACCUM_RUN_MM)} · 가드 ±1,040")
    s.text(pt, plant_y(0), "PT-101 · JB-201 투입 스테이션", "lbl", "middle", dy=-12)
    s.text(pt, plant_y(0), f"정반 {n(pt0)}…{n(pt1)} · 축적런 {n(ac0)}…{n(ac1)} · 겹침 {n(layout.pt_accumulator_overlap_mm())}",
           "lbl-small", "middle", dy=18)

    # 로봇 경로 — 인계점 → PT-101 / → 리젝트 랙
    for sign in (-1, 1):
        s.poly([(pick, plant_y(sign * layout.BFC_PICKUP_Z_MM)), (ped, plant_y(0)), (pt, plant_y(0))],
               "path", "RB-101 픽업 → 놓기 경로")
    s.poly([(pick, plant_y(-layout.BFC_PICKUP_Z_MM)), (ped + layout.REJECT_RACK_DX_MM, plant_y(-layout.REJECT_RACK_Z_MM))],
           "path path-reject", "전손 리젝트 경로")

    # 치수
    top = -130
    s.dim_x(afu.x0_mm, afu.x1_mm, top, f"afu {n(afu.length_mm)}")
    s.dim_x(robot.x0_mm, robot.x1_mm, top, f"robot {n(robot.length_mm)}")
    s.dim_x(afu.x0_mm, pick, top - 190, f"적층 {n(layout.BFC_PICKUP_OFFSET_MM)}")
    s.dim_x(pick, ped, top - 190, f"픽업→페데스털 {n(layout.ROBOT_PICK_DX_MM)}")
    s.dim_x(ped, pt, top - 190, f"페데스털→PT {n(layout.ROBOT_PLACE_DX_MM)}")
    s.dim_y(plant_y(0), plant_y(layout.BFC_PICKUP_Z_MM), pick + 1_700, f"Z {n(layout.BFC_PICKUP_Z_MM)}")
    s.dim_y(0, band, 11_250, f"장비 밴드 {n(band)}", right=False)
    s.line(afu.x0_mm, plant_y(0), 11_400, plant_y(0), "centre")
    s.text(10_250, plant_y(0), "라인 중심", "lbl-muted", "start", dy=-4)
    s.text(-3_650, band + aisle + 180, "X = 공정방향 (mm) · Y = 라인 좌측 · 원점 = afu 존 상류면 / 라인 중심 · 축척 NTS", "lbl-muted")
    return s.svg("투입 구간 평면 배치도")


def elevation_view() -> str:
    """입면 (X–Z) — 레벨과 승강 경로."""
    Z = zones()
    afu, robot = Z["afu"], Z["robot"]
    pick = layout.bfc_pickup_x_mm()
    ped = layout.robot_pedestal_x_mm()
    pt = layout.pt_place_x_mm()
    pt0, pt1 = layout.pt_deck_span_mm()
    ac0, ac1 = layout.accumulator_span_mm()
    k = kinematics
    s = Sheet(-3_700, 11_400, -350, 5_700, 1120, pad=(28, 200, 30, 24), flip_y=True)

    s.rect(-3_700, 11_400, -350, 0, "floor", "FFL")
    s.rect(afu.x0_mm, afu.x1_mm, 0, afu.height_mm, "zone zone-in", f"afu 존 높이 {n(afu.height_mm)}")
    s.rect(robot.x0_mm, robot.x1_mm, 0, robot.height_mm, "zone zone-in", f"robot 존 높이 {n(robot.height_mm)}")

    # 지게차 — 링 밑으로 팔레트를 밀어 넣는다
    s.rect(pick - 2_900, pick + 200, 0, k.FORKLIFT_GUARD_TOP_MM, "ref",
           f"FL-101 헤드가드 상단 {n(k.FORKLIFT_GUARD_TOP_MM)} — 링 밑 팔레트 교환 위치")
    s.text(pick - 2_900, 1_450, f"FL-101 헤드가드 {n(k.FORKLIFT_GUARD_TOP_MM)} (팔레트 교환)", "lbl-muted", "end", dy=-6)

    # 리프트·적층 — 입면의 가로는 X 이므로 축직각(단변) 쪽이 보인다
    dkx, _dkz = k.plan_xz(1_450, 900)
    phx, phz = k.panel_half_xz_mm()
    s.rect(pick - dkx, pick + dkx, 0, 130, "base", f"LFT-101 유압 시저 베이스 (X 폭 {n(dkx * 2)})")
    s.poly([(pick - dkx + 150, 130), (pick + dkx - 150, 480), (pick + dkx - 150, 130), (pick - dkx + 150, 480)],
           "scissor", "유압 시저 암 (픽업면 유지 — 한 장마다 상승)")
    s.rect(pick - dkx, pick + dkx, 480, 530, "base", "승강대 데크")
    s.rect(pick - phx, pick + phx, 530, k.PICK_FACE_MM, "panel",
           f"30장 적층 — 이 방향으로는 단변 {n(phx * 2)} 가 보인다 (장변 {n(phz * 2)} 는 지면 안쪽) · 최상단 = 픽업면 1,880")
    s.text(pick, 1_150, "적층 30장", "lbl-panel", "middle", dy=4)

    # 반전 카세트 — 포탈·크로스빔·엔드링·캐리지·분리헤드·포획빔
    chx, _chz = k.column_half_xz_mm()
    col_x = sorted({cx for cx, _ in k.column_offsets_xz_mm(-1)})
    for cx in col_x:
        xc = pick + cx
        s.rect(xc - chx, xc + chx, 0, 3_350, "column",
               f"포탈 기둥·LM가이드 (축직각 {n(cx)}) — 반전축 평면 ∓{n(k.PORTAL_COLUMN_AXIS_MM)} 두 본이 겹쳐 보인다")
    cb0, cb1 = k.crossbeam_cross_extent_mm()
    s.rect(pick + cb0, pick + cb1, 3_190, 3_450, "column",
           f"포탈 크로스빔 스팬 {n(k.CROSSBEAM_SPAN_MM)} — 기둥 밖으로 {n(k.crossbeam_overhang_mm())} 내밈 · 반전축 베어링을 매단다")
    # 엔드링 — 반전축이 지면 안쪽(Z)으로 누우므로 두 링이 한 자리에 겹쳐 정면으로 보인다
    ring_r = k.ring_outer_r_mm()
    rhx, _rhz = k.ring_half_xz_mm()
    bore_x, _ = k.plan_xz(k.RING_TUBE_MM, k.ring_bore_r_mm())
    bore_r = k.ring_bore_r_mm()
    s.ellipse(pick, k.FLIP_AXIS_MM, rhx, ring_r, "ring",
              f"오픈센터 엔드링 ⌀{n(ring_r * 2)} 2매 (평면 ∓{n(k.RING_PITCH_MM / 2)} — 이 방향에서 겹친다)")
    s.ellipse(pick, k.FLIP_AXIS_MM, bore_x, bore_r, "ring",
              f"링 통과 구멍 ⌀{n(k.ring_bore_r_mm() * 2)} — 패널이 이 구멍을 지난다")
    cgx, _cgz = k.plan_xz(k.CARRIAGE_MM / 2, k.CARRIAGE_RAIL_Z_MM + 40)
    s.rect(pick - cgx, pick + cgx, 1_690, 1_830, "carriage",
           f"BLR-101 승강캐리지 (홈 1,760) — 레일쌍 축직각 ∓{n(k.CARRIAGE_RAIL_Z_MM)}, 레일 길이 {n(k.CARRIAGE_MM)} 는 반전축 방향")
    spx, _spz = k.plan_xz(1_090, 540)
    s.rect(pick - spx, pick + spx, 2_020, 2_100, "sep", "SEP 이중진공 분리헤드 (홈 2,060) — 패널 테두리 160 안쪽")
    cdx, _cdz = k.plan_xz(1_450, 900)
    s.rect(pick - cdx, pick + cdx, 1_990, 2_050, "safety",
           "CD-101 포획빔 (전개 2,020) — 4열은 반전축 방향으로 벌어지고, 빔 자체는 축직각으로 뻗는다")
    for h, name in ((k.FLIP_AXIS_MM, "반전축 위의 패널"), (k.HANDOVER_MM, "인계 높이의 패널")):
        s.rect(pick - phx, pick + phx, h - 25, h + 25, "panel-ghost", f"{name} (참조 — 단변 {n(phx * 2)})")
    # 승강 경로
    s.line(pick, k.PICK_FACE_MM, pick, k.FLIP_AXIS_MM, "path")
    s.line(pick, k.FLIP_AXIS_MM, pick, k.HANDOVER_MM, "path")
    s.text(pick, (k.PICK_FACE_MM + k.FLIP_AXIS_MM) / 2, "수직 승강 (X 이동 없음)", "lbl-path", "middle", dx=15, rotate=-90)

    # 비전보
    vg = AFU_SHEET_ORIGIN_MM - 2_310
    s.rect(vg - 1_240, vg + 1_240, 4_950, 5_150, "beam", "VG-101 독립 방진 비전보 (상단 5,150)")
    s.rect(vg - 1_240 - 90, vg - 1_240 + 90, 0, 4_950, "column", "VG-101 독립 기둥 (방진 풋)")
    s.rect(pick - 190, pick + 190, 4_600, 4_840, "sensor", "VS-101A/B 융합헤드 (H 4,820)")
    s.text(pick + 260, 4_720, "VS-101A/B", "lbl-small", dy=4)

    # 로봇·정반·축적런
    s.rect(ped - 550, ped + 550, 0, 650, "pedestal", "RB-101 페데스털 650")
    s.rect(ped - 360, ped + 360, 650, 1_270, "column", "RB-101 J1")
    s.circle(ped, 1_570, 120, "joint", "J2 1,570")
    eox, eoz = k.plan_xz(1_090, 540)
    for xt, zt, ex, cls, name in (
            (pick, k.HANDOVER_MM, eox, "arm arm-pick", f"픽업 자세 (인계점 2,100) — 장변이 Z, X 로는 {n(eox * 2)}"),
            (pt, 1_000, eoz, "arm", f"놓기 자세 (PT-101 위) — J6 가 90° 되돌려 장변이 X, {n(eoz * 2)}")):
        s.poly([(ped, 1_570), ((ped + xt) / 2, 3_050), (xt, zt + 250)], cls, name)
        s.rect(xt - ex, xt + ex, zt + 20, zt + 250, "sep", f"EOAT 4구역 진공 — {name}")
    xr = ped + layout.REJECT_RACK_DX_MM
    s.rect(xr - 800, xr + 800, 0, 1_200, "rack", "AFU-RJ-101 전손 리젝트 랙 (페데스털 양옆 z ±1,550)")
    s.rect(pt - layout.PT_TABLE_MM[0] / 2, pt + layout.PT_TABLE_MM[0] / 2, 0, layout.PT_TABLE_MM[2], "base",
           "PT-101 정렬정반 H900")
    s.rect(pt0, pt1, 900, layout.LINE_TRANSFER_MM, "deck", "출구 정반 이송면 950")
    s.rect(ac0, ac1, layout.roller_axis_mm() - 45, layout.LINE_TRANSFER_MM, "roller",
           f"JB-201 축적·인계 런 — 롤러 축 {n(layout.roller_axis_mm())} + Ø{layout.ROLLER_D_MM}")
    s.rect(ac0, ac1, layout.LINE_TRANSFER_MM, 2_000, "guard", "JB-201 가드")
    s.text(pt, 2_420, "PT-101 · JB-201", "lbl", "middle")
    s.line(pt1, 0, pt1, 5_600, "boundary")
    s.text(pt1 - 80, 5_500, "robot 존 끝 · JBR-201 부터 범위 밖 →", "lbl-muted", "end")

    # 레벨 (우측 여백)
    levels = (
        (layout.LINE_TRANSFER_MM, f"이송면 {n(layout.LINE_TRANSFER_MM)}"),
        (layout.PT_TABLE_MM[2], "PT-101 정반 상면 900"),
        (650, "페데스털 650"),
        (1_570, "RB-101 J2 1,570"),
        (1_760, "승강캐리지 홈 1,760"),
        (k.PICK_FACE_MM, f"픽업면 {n(k.PICK_FACE_MM)} (고정)"),
        (2_020, "포획빔 전개 2,020"),
        (k.HANDOVER_MM, f"로봇 인계 {n(k.HANDOVER_MM)}"),
        (k.FORKLIFT_GUARD_TOP_MM, f"지게차 헤드가드 {n(k.FORKLIFT_GUARD_TOP_MM)}"),
        (k.dwell_mm(), f"대기면 {n(k.dwell_mm())}"),
        (k.ring_bottom_mm(), f"링 하단 {n(k.ring_bottom_mm())}"),
        (k.FLIP_AXIS_MM, f"반전축 {n(k.FLIP_AXIS_MM)}"),
        (k.FLIP_AXIS_MM + ring_r, f"링 상단 {n(k.FLIP_AXIS_MM + ring_r)}"),
        (4_820, "비전 4,820"),
        (5_150, "VG-101 상단 5,150"),
    )
    # 글자가 겹치지 않게 아래에서 위로 최소 간격을 둔다
    placed: list[float] = []
    min_gap = 13.0
    for z_mm, label in sorted(levels):
        py = s.Y(z_mm)
        if placed and placed[-1] - py < min_gap:
            py = placed[-1] - min_gap
        placed.append(py)
        px0, px1 = s.X(11_400), s.width - s.pad[1] + 8
        s.parts.append(f'<line class="level" x1="{s.X(afu.x0_mm)}" y1="{s.Y(z_mm)}" x2="{px0}" y2="{s.Y(z_mm)}"/>')
        s.parts.append(f'<line class="leader" x1="{px0}" y1="{s.Y(z_mm)}" x2="{px1}" y2="{py}"/>')
        s.parts.append(f'<text class="lvl" x="{px1 + 4}" y="{py + 3}">{esc(label)}</text>')

    s.dim_y(k.PICK_FACE_MM, k.dwell_mm(), pick - 1_050, f"안전분리 {k.SEPARATION_MM}", right=False)
    s.dim_y(k.dwell_mm(), k.FLIP_AXIS_MM, pick + 1_850, f"승강 {n(k.FLIP_AXIS_MM - k.dwell_mm())}")
    s.dim_y(k.FLIP_AXIS_MM, k.HANDOVER_MM, pick - 1_700, f"하강 {n(k.FLIP_AXIS_MM - k.HANDOVER_MM)}", right=False)
    s.dim_y(k.FORKLIFT_GUARD_TOP_MM, k.ring_bottom_mm(), pick - 2_400, f"링–헤드가드 {n(k.ring_over_forklift_mm())}", right=False)
    s.dim_y(k.PICK_FACE_MM + k.PANEL_TOP_OFFSET_MM, k.ring_bottom_mm(), pick + 3_150, f"링–적층 {n(k.ring_over_stack_mm())}")
    s.text(-3_650, 5_600, "입면 (X–높이) · 단위 mm · FFL = 0 · 반전축은 지면 안쪽(Z)으로 눕는다 — 패널 장변 2,500 은 이 그림에서 보이지 않는다", "lbl-muted")
    return s.svg("투입 구간 입면도")


def timeline_view() -> str:
    """한 장의 시각표 0 … 48 s — 어느 기계가 언제 패널을 쥐는가."""
    takt = campaign.release_takt_s()
    rows: list[tuple[str, list[tuple[float, float, str, str]]]] = [
        ("LFT-101 · SE/VS-101", [(0.0, 7.5, "도킹·높이 추종·비전 판정", "prep"),
                                 (7.5, 8.8, "겹장 확인", "prep")]),
        ("SEP 분리헤드 · 캐리지", [(7.5, 8.8, "안전분리 상승 370", "lift"),
                                (8.8, 10.5, "대기면 2,250", "hold"),
                                (10.5, 13.3, "수직 승강 1,180", "lift"),
                                (13.3, 20.8, "조 체결 후 후퇴", "hold"),
                                (20.8, 24.0, "하강 1,330 → 2,100", "lift")]),
        ("CD-101 포획빔", [(8.8, 10.5, "Z 전개", "safe"), (10.5, 24.0, "낙하 포획 대기", "safe-hold")]),
        ("엔드링 · 4점 조", [(13.3, 20.8, "체결 · 180° 반전 (GLASS_UP)", "flip"),
                           (20.8, 24.0, "조 열림", "hold")]),
        ("RB-101 · EOAT", [(24.0, 25.4, "진공 흡착", "robot"),
                           (25.4, 30.5, "인계점 → PT-101 이송", "robot"),
                           (30.5, 33.5, "안착·진공 해제", "robot"),
                           (37.0, 40.0, "후퇴", "hold")]),
        ("PT-101 · JB-201", [(33.5, 37.0, "3-2-1 정렬", "align"),
                             (37.0, 40.0, "인계", "align"),
                             (40.0, takt, "JBR 진입 → 스토퍼 8.0 s", "out")]),
        ("전손 (대안 경로)", [(0.0, 7.5, "판정 = 전손", "prep"),
                           (7.5, campaign.INFEED_REJECT_S, "반전 생략 하강 → RJ-101 랙 → 복귀", "reject")]),
    ]
    width, left, right, row_h, top = 1120, 168, 24, 30, 34
    inner = width - left - right
    height = top + row_h * len(rows) + 46
    px = lambda t: round(left + t / takt * inner, 1)  # noqa: E731
    out = [f'<svg class="sheet timeline" viewBox="0 0 {width} {height}" role="img" aria-label="투입 시각표">']
    for t in range(0, int(takt) + 1, 4):
        x = px(t)
        out.append(f'<line class="grid" x1="{x}" y1="{top - 6}" x2="{x}" y2="{height - 40}"/>')
        out.append(f'<text class="tick" x="{x}" y="{top - 10}" text-anchor="middle">{t}</text>')
    for mark, label in ((campaign.INFEED_S, f"INFEED {campaign.INFEED_S:g} s · JBR 이 받는다"),
                        (takt, f"방출 주기 {takt:g} s")):
        x = px(mark)
        out.append(f'<line class="mark" x1="{x}" y1="{top - 6}" x2="{x}" y2="{height - 40}"/>')
        out.append(f'<text class="markt" x="{x - 4}" y="{height - 26}" text-anchor="end">{esc(label)}</text>')
    for i, (actor, bars) in enumerate(rows):
        y = top + i * row_h
        out.append(f'<text class="actor" x="{left - 10}" y="{y + 19}" text-anchor="end">{esc(actor)}</text>')
        out.append(f'<line class="row" x1="{left}" y1="{y + row_h}" x2="{width - right}" y2="{y + row_h}"/>')
        for t0, t1, label, cls in bars:
            x0, x1 = px(t0), px(t1)
            out.append(f'<rect class="bar bar-{cls}" x="{x0}" y="{y + 5}" width="{round(x1 - x0, 1)}" height="{row_h - 10}" rx="2">'
                       f'<title>{esc(f"{t0:g}–{t1:g} s · {label}")}</title></rect>')
            if x1 - x0 > 58:
                out.append(f'<text class="bart" x="{x0 + 5}" y="{y + 19}">{esc(label)}</text>')
    out.append(f'<text class="tick" x="{left}" y="{height - 8}">s · 3D 공정시계 기준 (한 장, 유리면 위 · 정상)</text>')
    out.append("</svg>")
    return "".join(out)


def flow_strip() -> str:
    """플랜트 흐름 전체를 놓고 이 상세도의 범위를 표시한다."""
    steps = [
        ("FL-101", "지게차 반입", True), ("LFT-101A/B", "30장 팔레트 리프트", True),
        ("SE·VS-101", "높이·비전 판정", True), ("BFC-101A/B", "분리·승강·반전", True),
        ("RB-101", "직접 픽업", True), ("PT-101", "3-2-1 정렬", True), ("JB-201", "축적·인계", True),
        ("JBR-201", "정션박스 제거", False), ("AFR-101", "프레임 분리", False),
        ("SG·CV·GI", "연마·검사", False), ("GBR-301", "레시피 버퍼", False), ("GRM-401", "유리 제거", False),
    ]
    out = ['<ol class="flow" aria-label="플랜트 공정 흐름과 상세도 범위">']
    for tag, what, inside in steps:
        out.append(f'<li class="{"in" if inside else "out"}"><b>{esc(tag)}</b><span>{esc(what)}</span></li>')
    out.append("</ol>")
    return "".join(out)


# ── 표 ──────────────────────────────────────────────────────────────────
def table(head: list[str], rows: list[list[object]], cls: str = "", num_cols: tuple[int, ...] = ()) -> str:
    num = ' class="num"'
    out = [f'<div class="scroll"><table class="{cls}"><thead><tr>']
    for i, h in enumerate(head):
        out.append(f'<th{num if i in num_cols else ""}>{h}</th>')
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for i, cell in enumerate(row):
            out.append(f'<td{num if i in num_cols else ""}>{cell}</td>')
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def kinematics_table() -> str:
    k = kinematics
    rows = [
        ["패널 최대 외형", f"{n(k.PANEL_MM[0])} × {n(k.PANEL_MM[1])} × 50", "프레임이 곧 외곽 — 유리 밖에 프레임을 덧붙이지 않는다"],
        ["케이지 안지름 (두 링 안쪽 면)", n(k.cage_clear_span_mm()), f"링 피치 {n(k.RING_PITCH_MM)} − 단면 {k.RING_TUBE_MM}×2"],
        ["패널 끝–링 안쪽 면 여유 (편측)", n(k.cage_axial_clearance_mm()), "양수여야 들어간다 — REV.26 은 −17.5 였다"],
        ["링 통과 구멍 ⌀", n(k.ring_bore_r_mm() * 2), f"토러스 중심선 R{k.RING_R_MM} − 단면 R{k.RING_TUBE_MM}"],
        ["반전축 위 패널 모서리–구멍 여유", n(k.bore_clearance_mm()), "패널 단면 반대각선이 구멍 반경 안"],
        ["캐리지 레일–구멍 여유", n(k.carriage_bore_clearance_mm()),
         f"캐리지 {n(k.CARRIAGE_MM)} 은 케이지보다 길어 링 구멍 **안으로** 오르내린다 (레일 z ∓{k.CARRIAGE_RAIL_Z_MM:g} · y −{k.CARRIAGE_RAIL_DROP_MM})"],
        ["조 행정 (무는 자리 → 여는 자리)", f"{k.jaw_stroke_mm():g}", f"z ∓{k.JAW_CLOSED_Z_MM:g} → ∓{k.JAW_OPEN_Z_MM:g}"],
        ["조를 열었을 때 패드–패널 옆면 여유", n(k.jaw_open_clearance_mm()), "양수여야 반전 뒤 패널이 두 링 사이로 내려간다"],
        ["패드 접촉폭 (프레임 플랜지)", f"{k.JAW_PAD_CONTACT_MM:g}", "**발주처 확정값.** 접촉 면적 "
         f"{n(k.jaw_pad_contact_area_mm2())} mm²/매 — 면압 {k.jaw_pad_pressure_mpa():.2f} MPa "
         f"(Ø{k.JAW_CYLINDER_BORE_MM:g} 실린더 {k.JAW_AIR_MPA:g} MPa · 지레비 1:1 기준, 실린더 자리는 미결)"],
        ["패드 랜드 z 구간 · 편심", f"{n(k.jaw_pad_land_z_mm()[0])}…{n(k.jaw_pad_land_z_mm()[1])} · "
         f"+{k.jaw_pad_land_offset_mm():g}", "랜드는 프레임 위에만 앉는다. 패드 중심 "
         f"{k.JAW_CLOSED_Z_MM:g} 에 가운데를 두면 유리 위로 {k.jaw_pad_land_offset_mm():g} 밀린다 — "
         "**패드를 편심 랜드로 만든다**"],
        ["패드 릴리프 깊이", f"{k.JAW_PAD_RELIEF_MM:g}", f"프레임–유리 단차 {k.PANEL_FRAME_GLASS_STEP_MM:g}"
         f"(가정) + 압축 {k.jaw_pad_compression_mm():.1f} 보다 깊다 — 평면 패드면 폭 92 가 유리에 얹힌다"],
        ["링 하단–적층 최상단 유리면", n(k.ring_over_stack_mm()), "드럼이 적층 위에 서는 조건 (≥ 500)"],
        ["링 하단–지게차 헤드가드", n(k.ring_over_forklift_mm()), "팔레트 교환이 링 밑에서 일어난다 (≥ 250)"],
        ["대기면", n(k.dwell_mm()), f"픽업면 {n(k.PICK_FACE_MM)} + 안전분리 {k.SEPARATION_MM}"],
        ["경로에 X 이동이 있는가", "없음" if k.lift_is_vertical() else "있음", "REV.49 — 링 평면을 가로지르는 구간 자체가 없다"],
    ]
    rows = [[esc(a), esc(b), _md(c)] for a, b, c in rows]
    return table(["항목", "값 (mm)", "근거"], rows, "kv", (1,))


def _md(s: str) -> str:
    """**굵게** 만 받는 최소 마크업."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


def reach_table() -> str:
    Z = zones()
    afu, robot, jbr = Z["afu"], Z["robot"], Z["jbr"]
    rows = [
        ["적층 = 반전 드럼 = 인계점 X", n(layout.bfc_pickup_x_mm()), f"afu 존 시작 + {n(layout.BFC_PICKUP_OFFSET_MM)} — 지게차 도킹·주차 여유가 정한다"],
        ["RB-101 페데스털 (J2 축) X", n(layout.robot_pedestal_x_mm()), f"적층 + {n(layout.ROBOT_PICK_DX_MM)}"],
        ["인계점 수평 직선거리", n(layout.robot_pickup_distance_mm()),
         f"√({n(layout.ROBOT_PICK_DX_MM)}² + {n(layout.BFC_PICKUP_Z_MM)}²) — 도달 {n(layout.ROBOT_REACH_MM)} 의 {n(round(layout.ROBOT_REACH_MM - layout.robot_pickup_distance_mm()))} 안쪽"],
        ["PT-101 놓는 자리 X", n(layout.pt_place_x_mm()), f"페데스털 + {n(layout.ROBOT_PLACE_DX_MM)} = jbr 존 중심 − {n(layout.PT_FROM_JBR_CENTER_MM)}"],
        ["전손 리젝트 랙 도달", n(layout.robot_reject_distance_mm()), f"페데스털 + {n(layout.REJECT_RACK_DX_MM)} · z ±{n(layout.REJECT_RACK_Z_MM)}"],
        ["afu 존 길이 (도달 사슬에서)", n(layout.afu_length_from_reach_mm()),
         f"{n(layout.BFC_PICKUP_OFFSET_MM)} + {n(layout.ROBOT_PICK_DX_MM)} + {n(layout.ROBOT_PLACE_DX_MM)} + {n(layout.PT_FROM_JBR_CENTER_MM)} − robot {n(robot.length_mm)} − jbr/2 {n(jbr.length_mm // 2)} = 존 표 {n(afu.length_mm)}"],
        ["afu → robot 존 넘침 (설계)", n(layout.zone_overlap_mm('afu')), "BFC 하류 포탈 기둥 발판·리프트 하류끝 — 베이를 존 안으로 물리면 인계점이 3,803 으로 멀어져 로봇이 못 닿는다"],
        ["이송면 단차 afu → robot", n(dict(((a, b), s) for a, b, s in layout.transfer_steps_mm())[("afu", "robot")]),
         layout.NON_ROLLER_HANDOFF[("afu", "robot")]],
    ]
    rows = [[esc(a), esc(b), _md(c)] for a, b, c in rows]
    return table(["항목", "값 (mm)", "근거"], rows, "kv", (1,))


def station_table() -> str:
    pt0, pt1 = layout.pt_deck_span_mm()
    ac0, ac1 = layout.accumulator_span_mm()
    lo, hi = layout.infeed_station_span_mm()
    rows = [
        ["PT-101 정렬정반 외형", f"{n(layout.PT_TABLE_MM[0])} × {n(layout.PT_TABLE_MM[1])} × H{layout.PT_TABLE_MM[2]}", "3-2-1 스토퍼·양측 푸셔"],
        ["출구 정반 (3D)", f"{n(layout.PT_DECK_MM[0])} × {n(layout.PT_DECK_MM[1])}", f"패널 {n(campaign.PANEL_LENGTH_MM)} 에 60 씩 물린다"],
        ["정반 X 구간", f"{n(pt0)} … {n(pt1)}", "플랜트 mm"],
        ["JB-201 축적·인계 런", f"{n(ac0)} … {n(ac1)} ({n(layout.ACCUM_RUN_MM)})", f"패널 {n(campaign.PANEL_LENGTH_MM)} + 그립 여유 {layout.GRIP_CLEARANCE_MM}×2 — 존 경계를 건넌다"],
        ["정반–축적런 겹침", n(layout.pt_accumulator_overlap_mm()), "패널 한 장에 가까운 길이가 겹친다 — 둘은 이미 한 스테이션이다"],
        ["투입 스테이션 합집합", f"{n(lo)} … {n(hi)} ({n(hi - lo)})", ""],
        ["겸용으로 더 걷을 수 있는 길이", n(layout.infeed_merge_residue_mm()),
         "합집합 − 한 장 축적 소요 — 그 대가가 좌표시드라 **발주처 결정으로 후보를 닫았다** (§56)"],
        ["좌표시드 공차", f"±{layout.PT_SEED_TOLERANCE_MM:g} mm / yaw ±{layout.PT_SEED_YAW_DEG:g}°",
         "이 라인의 유일한 기계 기준. **기준 모서리**(장변 스토퍼 2 + 단변 스토퍼 1 이 "
         "만나는 점)의 위치 공차와 그 점을 중심으로 한 회전 공차다. "
         "브리지 동기오차 0.08 mm 와 **다른 값**이다"],
        ["반대편 모서리 흔들림", f"±{layout.seed_far_corner_mm():g} mm",
         f"±{layout.PT_SEED_TOLERANCE_MM:g} + {n(campaign.PANEL_LENGTH_MM)}·tan{layout.PT_SEED_YAW_DEG:g}° — "
         f"하류가 패널 전체 ±1 mm 를 기대하면 yaw 를 ±{layout.seed_yaw_for(1.0):g}° 로 조여야 하고, "
         "그것은 3-2-1 스토퍼로 성립하지 않는다. **하류 공차는 기준 모서리 기준으로 읽는다**"],
        ["축적구간 입구 비움", f"{campaign.accumulator_clear_s():g} s",
         f"패널 {n(campaign.PANEL_LENGTH_MM)} ÷ 이송 {campaign.transfer_speed_mm_s():g} mm/s — 지금은 스토퍼 확인 {campaign.JBR_STOPPER_OFFSET_S:g} s 로 다음 장을 놓는다"],
    ]
    rows = [[esc(a), esc(b), _md(c)] for a, b, c in rows]
    return table(["항목", "값", "근거"], rows, "kv", (1,))


def campaign_table() -> str:
    s = campaign.summary()
    counts = campaign.bundle_condition_counts()
    occupancy = dict(campaign.cell_occupancy_s())
    rows = [
        ["투입부 점유 (한 장)", f"{campaign.INFEED_S:g} s", "픽업·판정·반전·로봇 투입·정렬·인계까지"],
        ["전손 배출 점유", f"{campaign.INFEED_REJECT_S:g} s", "픽업·판정·반전 생략 하강·로봇 랙 배출·복귀 — 병목을 비켜간다"],
        ["다음 장 방출 주기", f"{campaign.release_takt_s():g} s", f"INFEED {campaign.INFEED_S:g} + JBR 스토퍼 오프셋 {campaign.JBR_STOPPER_OFFSET_S:g}"],
        ["라인 택트 (60장 캠페인)", f"{s['takt_s']:g} s", f"병목 {campaign.bottleneck()} {occupancy[campaign.bottleneck()]:g} s — 투입부 {occupancy['투입부']:g} s 는 병목이 아니다"],
        ["페이스를 당길 수 있는 여지 (분석)", f"{campaign.pace_offset_s():g} s",
         "입구 비움·병목·후단 능력 셋 중 최대 — 묶고 있는 것은 인터록이 아니라 후단이다"],
        ["팔레트", f"{campaign.PALLET_PANELS} 장 × 2 리프트", f"호출 임계 잔량 {campaign.FORKLIFT_CALL_REMAINING} 장 · 교환 {campaign.PALLET_SWAP_S:g} s (대기 리프트가 급전 중이라 택트에 안 더해진다)"],
        ["60장 판정", f"정상 {s['normal']} · 유리 깨짐 {s['cracked']} · 전손 {s['scrap']}",
         f"번들 1: {counts[0]['정상']}/{counts[0]['유리 깨짐']}/{counts[0]['전손']} · 번들 2: {counts[1]['정상']}/{counts[1]['유리 깨짐']}/{counts[1]['전손']}"],
        ["반전 / 바이패스", f"{s['flipped']} / {s['bypassed']}", "유리면 위(U)만 180° 반전 · 유리면 아래(D)는 회전 생략"],
        ["동시 라인 위 매수 (최대)", f"{s['peak_wip']}", "투입부·JBR·AFR 이 실제로 겹친다"],
    ]
    rows = [[esc(a), esc(b), _md(c)] for a, b, c in rows]
    return table(["항목", "값", "근거"], rows, "kv", (1,))


def forklift_table() -> str:
    rows = [[f"{e.at_s:g}", esc(e.lift), esc(e.kind), esc(e.note)] for e in campaign.forklift_events()]
    return table(["시각 (s)", "리프트", "동작", "비고"], rows, "", (0,))


def classification_table() -> str:
    rows = [
        ["정상 · 유리면 위 (U)", "BFC 180° 반전 후 투입", "PT-101 → JB-201 → 라인", "R-A 정상 유리 버퍼"],
        ["정상 · 유리면 아래 (D)", "반전 생략 · 인계높이로 하강", "PT-101 → JB-201 → 라인", "R-A"],
        ["유리 깨짐 (u/d)", "정상과 같이 투입", "정션박스·프레임 제거를 그대로 거친다", "R-B 파손 유리 버퍼"],
        ["전손 (X)", "반전 없이 인계높이로 하강", f"RB-101 이 PT-101 대신 AFU-RJ-101 랙 (도달 {n(layout.robot_reject_distance_mm())})", "라인에 들어가지 않는다"],
        ["양면발전형 · 미등록 (구조 레시피)", "반입 등록에서 걸린다", "양면형은 범위 외 리젝트 (전손과 같은 경로) · 미등록은 HOLD", "—"],
    ]
    return table(["VS-101 판정 / 등록", "BFC 동작", "RB-101 경로", "적재"], [[esc(c) for c in r] for r in rows])


def catalog_table(text: str) -> str:
    rows = []
    for row in catalog(text):
        tag, group, name, qty, dims, material, process, tol, _kind, desc, meshes = row[:11]
        rows.append([f"<code>{esc(tag)}</code>", esc(name), esc(qty),
                     esc(" × ".join(n(d) for d in dims)), esc(material), esc(process), esc(tol), esc(desc)])
    return table(["품번", "품명", "수량", "외형 (mm)", "재질·사양", "공정", "공차·성능", "기능"], rows, "catalog", (2, 3))


def drives_table() -> str:
    rows = []
    for a in servos.SERVO_AXES + servos.MOTORS:
        if a.panel in SCOPE_PANELS:
            rows.append([f"<code>{esc(a.tag)}</code>", esc(a.panel), esc(a.equipment), esc(a.motion), str(a.qty),
                         f"{a.rated_kw:g}", f"{a.group_kw:g}", esc(a.drive), esc(a.feedback),
                         "있음" if a.brake else "—", esc(a.note)])
    return table(["축", "분전반", "장비", "동작", "수", "정격 kW", "합 kW", "구동", "피드백", "브레이크", "비고"],
                 rows, "", (4, 5, 6))


def transmission_table() -> str:
    """전동기와 기구 사이 — 그 속도로 돌 수 있는가, 그 토크가 전달되는가.

    정격만 적어 두면 검산이 안 된다. 행정 ÷ 시각으로 속도를 내고 리드·감속비로
    회전수를 환산해 정격 안에 드는지 본다 (`drives.py`).
    """
    spd, trq = drives.speed_checks(), drives.torque_checks()
    pre = drives.preload_is_specified()
    rows = []
    for b in drives.ballscrews():
        rms, peak, rated, ok = trq[b.axis]
        rows.append([f"<code>{esc(b.axis)}</code>", "볼스크루 직결",
                     f"리드 {b.lead_mm:g} × {b.screws}본 · i={b.ratio:g}",
                     f"{b.mean_mm_s:.0f} mm/s (최고 {b.peak_mm_s:.0f})",
                     f"{spd[b.axis][0]:,} / {drives.SERVO_MAX_RPM:,}",
                     f"{rms:g} / {rated:g}", f"{peak:g} / {rated * drives.SERVO_PEAK_FACTOR:g}",
                     "—", "만족" if ok and spd[b.axis][1] else "**미달**"])
    for f in drives.friction_drives():
        need, _peak, rated, ok = trq[f.axis]
        have, want, pok = pre[f.axis]
        rows.append([f"<code>{esc(f.axis)}</code>", "마찰 롤러",
                     f"링 Ø{n(f.ring_od_mm)} ← 롤러 Ø{n(f.roller_od_mm)} · i={f.ratio:g}",
                     f"{f.ring_rpm:.1f} rpm (링)",
                     f"{spd[f.axis][0]:,} / {drives.SERVO_MAX_RPM:,}",
                     f"{need:g} / {rated:g}",
                     f"링 {f.torque_nm:.0f} / 전달 상한 {f.torque_limit_nm():.0f}",
                     f"{have:g} / {want:g}",
                     "만족" if ok and pok and spd[f.axis][1] else "**미달**"])
    return table(["축", "전동", "감속·리드", "기구 속도", "모터 rpm / 최대",
                  "실효 N·m / 정격", "피크 N·m / 한계", "압착 N / 필요", "판정"],
                 rows, "", (3, 4, 5, 6, 7))


def feeders_table() -> str:
    kw = servos.motion_kw_by_panel()
    rows = []
    for f in electrical.FEEDERS:
        if f.panel in SCOPE_PANELS:
            rows.append([f"<code>{esc(f.tag)}</code>", esc(f.panel), esc(f.served), f"{f.installed_kw:g}",
                         f"{f.diversity:g}", f"{f.installed_kw * f.diversity:.2f}", str(f.breaker_at), esc(f.cable),
                         f"{kw.get(f.panel, 0):g}", esc(f.source)])
    return table(["피더", "분전반", "급전 대상", "설치 kW", "수용률", "수요 kW", "차단기 AT", "케이블", "전동기 합 kW", "출처"],
                 rows, "", (3, 4, 5, 6, 8))


def vision_table() -> str:
    rows = []
    for h in vision.HEADS:
        if h.cell == "AFU-101":
            rows.append([f"<code>{esc(h.tag)}</code>", esc(h.role), "존치" if h.kept else "감축", esc(h.note)])
    rows.append(["<code>SE-101A/B-L/R</code>", "리프트별 높이·기울기 독립 채널 4EA", "존치 (안전 채널)",
                 "V-5 미적용 — PLr·PFHd 재계산과 위험성평가 재승인 없이 줄이지 않는다"])
    rows.append(["<code>AFU-SF-101</code>", "듀얼 도킹 게이트 · Bay 별 안전 스캐너 2식", "존치 (안전 채널)",
                 "SF-05 로봇 작업영역 · SF-11 도킹 Bay 독립 정지"])
    return table(["헤드·센서", "역할", "최소화안", "비고"], rows)


def safety_table() -> str:
    rows = []
    for h in safety.HAZARDS:
        if h.cell in SCOPE_HAZARD_CELLS:
            funcs = ", ".join(f.tag for f in safety.functions_for(h.tag))
            rows.append([f"<code>{esc(h.tag)}</code>", esc(h.description), f"S{h.severity} F{h.frequency} P{h.avoidance}",
                         f"PL{h.plr}", esc(safety.PL_CATEGORY[h.plr]), esc(funcs), _md(h.basis)])
    return table(["위험원", "내용", "S·F·P", "PLr", "구조", "안전기능", "근거"], rows)


def safety_functions_table() -> str:
    rows = []
    scope_tags = {h.tag for h in safety.HAZARDS if h.cell in SCOPE_HAZARD_CELLS}
    for f in safety.SAFETY_FUNCTIONS:
        if set(f.hazards) & scope_tags:
            rows.append([f"<code>{esc(f.tag)}</code>", esc(f.name), esc(", ".join(f.hazards)), f"PL{f.plr}",
                         esc(f.category), esc(f.detection), esc(f.logic), esc(f.actuator), _md(f.note)])
    return table(["기능", "이름", "위험원", "PL", "구조", "검출", "논리", "구동", "비고"], rows)


def mounting_table() -> str:
    rows = []
    for m in mounting.MOUNTINGS:
        if m.station in ("afu", "bfc", "robot"):
            anchors = " · ".join(
                f"{a.target} {a.count}×{a.bolt}" + (f" ×{a.units}기" if a.per_unit else "") for a in m.anchors)
            rows.append([esc(m.station), esc(anchors), str(m.total_anchors), esc(m.plate), str(m.grout_mm),
                         esc(m.level), esc(m.note)])
    return table(["셀", "앵커", "합계", "베이스플레이트", "그라우트 mm", "레벨링", "비고"], rows, "", (2, 4))


def keepout_table() -> str:
    rows = [[esc(name), f"{x0:g} … {x1:g}", f"{z0:g} … {z1:g}", esc(why)]
            for name, (x0, x1, z0, z1), why in mounting.BRACKET_KEEP_OUT]
    return table(["금지 부피", "월드 X (m)", "Z (m)", "근거"], rows)


def uptime_table() -> str:
    rows = []
    for b in reliability.BLOCKS:
        if b.tag in ("RB-AFU", "RB-BFC", "RB-ROBOT"):
            p = maintain.PROFILE_BY_TAG[b.tag]
            rows.append([f"<code>{esc(b.tag)}</code>", esc(b.name), f"{b.share:.0%}",
                         "2식 — 절반 속도로 계속" if b.redundant else "—",
                         f"{p.base_h:g} → {p.mttr_h():g}", esc(p.module), _md(b.basis)])
    return table(["블록", "설비", "정지 예산 몫", "이중화", "MTTR h (계획 → 설계)", "교환 모듈", "근거"], rows, "", (2,))


def interface_table(text: str) -> str:
    rows = [[f"<th scope=\"row\">{esc(name)}</th>", body] for name, body in interface_rows(text)]
    out = ['<div class="scroll"><table class="iface"><tbody>']
    for th, body in rows:
        out.append(f"<tr>{th}<td>{body}</td></tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def sequence_table() -> str:
    rows = []
    for t0, t1, name in PREP_CLOCK:
        rows.append([f"{t0:g} – {t1:g}", "판정·파지 준비", esc(name)])
    for t0, t1, name, climbs, _travels in kinematics.PATH:
        rows.append([f"{t0:g} – {t1:g}", "BFC-101 승강·반전", esc(name) + (" · 높이 변화" if climbs else " · 높이 유지")])
    for t0, t1, name in ROBOT_CLOCK:
        rows.append([f"{t0:g} – {t1:g}", "RB-101 · PT-101 · JB-201", esc(name)])
    rows.append([f"{campaign.INFEED_S:g} – {campaign.release_takt_s():g}", "JBR-201 (범위 밖)",
                 esc(f"JBR 진입 → {campaign.JBR_STOPPER_OFFSET_S:g} s 뒤 스토퍼·측면 정렬 — 그 순간 로봇이 다음 장을 내려놓는다")])
    return table(["시각 (s)", "구간", "동작"], rows, "", (0,))


def open_items() -> str:
    items = [
        ("FL-101 · 팔레트 실기종", "AFU 시트 출도 조건이다. 지게차 도킹·주차 여유가 적층 위치(afu 존 시작 + 4,400)를 정하므로 실기종이 오면 이 값이 움직인다."),
        ("적층 → 픽업 4,400 축소 검토", "직전 작업 세션에서 3,750 (−650) 이 가능하다는 근거를 잡아 두었으나 FL-101 벤더 제원 확인 뒤 반영 여부를 정하기로 하고 **코드·도면에는 아직 넣지 않았다.** 넣으면 afu 존·전장·하류 셀 좌표가 전부 따라온다 (layout.BFC_PICKUP_OFFSET_MM)."),
        ("RB-101 OEM 하중도", "자세별 하중승인 · TCP · dress pack · 정지·금지 포락선 — RBPT 시트 출도 조건. 서보 정격은 OEM 일괄 계획값이다."),
        ("BFC 반전 카세트 계산", "축·베어링·브레이크 계산 · 회전포락선 · 겹장검출 판정식(진공 A/B·두께·중량·높이) · 포획빔 전개동기·낙하시험 · 포탈기둥–통과대역 이격 실측. 반전 카세트 중량은 발주처 확인 2,500 kg 이상을 하한으로 쓴다."),
        ("리프트 인덱스 피치", "LFT-101 사양은 한 장 픽업마다 50 mm 상승인데 AFU 시트의 30장 적층은 1,350 (45 mm/장) 으로 그려져 있다. 실기종 패널 두께로 한 값으로 맞춘다."),
        ("RBPT 2D 시트의 PT 위치", f"시트는 페데스털–PT 중심을 2,600 으로 그리고 모델(3D 실측 검증)은 {n(layout.ROBOT_PLACE_DX_MM)} 이다 — 310 mm 차이. 정본은 모델이며 시트를 맞춰야 한다."),
        ("앵커 배정", "afu 12×M20 은 '예비' 이고 VG-101 비전보·VAC-101 스키드에는 앵커군이 배정돼 있지 않다(내진 SE-1018 미배정 3대 중 2대). 바닥하중 승인이 AFU 시트 출도 조건이다."),
        ("BW-101 동시 비상토크", "양측 Bay 가 동시에 비상정지할 때의 반전 토크를 벽체가 받는 구조검증이 남아 있다."),
        ("PFHd", "위험원 4건의 PLr 은 위험그래프에서 나왔고 PFHd 는 부품 B10d·MTTFd 가 와야 SISTEMA 로 낸다 — 여기서 지어내지 않는다."),
    ]
    out = ['<dl class="open">']
    for title, body in items:
        out.append(f"<dt>{esc(title)}</dt><dd>{_md(body)}</dd>")
    out.append("</dl>")
    return "".join(out)


# ── 문서 ────────────────────────────────────────────────────────────────
CSS = """
:root {
  --ground: #EEF1F3; --sheet: #FFFFFF; --ink: #16202A; --muted: #5B6874; --rule: #C8D0D7;
  --tint: #E4EAEF; --tint-out: #F3F4F5; --red: #B5321F; --blue: #2A6CB0; --amber: #C8850A;
  --green: #2F7D4F; --blue-fill: rgba(42,108,176,.14); --red-fill: rgba(181,50,31,.10);
  --amber-fill: rgba(200,133,10,.18); --grey-fill: rgba(22,32,42,.08); --code: #EDF1F4;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground: #12181E; --sheet: #1A222A; --ink: #E4E9ED; --muted: #98A5B1; --rule: #34414D;
    --tint: #232D37; --tint-out: #1E252C; --red: #E0604A; --blue: #6FA8E6; --amber: #E6B04C;
    --green: #6CBF8A; --blue-fill: rgba(111,168,230,.16); --red-fill: rgba(224,96,74,.14);
    --amber-fill: rgba(230,176,76,.2); --grey-fill: rgba(228,233,237,.08); --code: #232D37;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --ground: #12181E; --sheet: #1A222A; --ink: #E4E9ED; --muted: #98A5B1; --rule: #34414D;
  --tint: #232D37; --tint-out: #1E252C; --red: #E0604A; --blue: #6FA8E6; --amber: #E6B04C;
  --green: #6CBF8A; --blue-fill: rgba(111,168,230,.16); --red-fill: rgba(224,96,74,.14);
  --amber-fill: rgba(230,176,76,.2); --grey-fill: rgba(228,233,237,.08); --code: #232D37;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink);
  font: 14px/1.55 "Pretendard", -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif;
  font-variant-numeric: tabular-nums; }
code, .mono, .num, .tick, .dimt, .lvl { font-family: ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; }
code { background: var(--code); padding: 1px 5px; border-radius: 3px; font-size: .92em; }
.page { max-width: 1160px; margin: 0 auto; padding: 24px 20px 64px; display: grid; gap: 28px; }
.title { background: var(--sheet); border: 1px solid var(--rule); display: grid; grid-template-columns: 1fr auto; }
.title > div { padding: 18px 22px; }
.title h1 { margin: 6px 0 4px; font-size: 26px; line-height: 1.2; font-weight: 600; text-wrap: balance; }
.title p { margin: 0; color: var(--muted); max-width: 70ch; }
.eyebrow { font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.block { border-left: 1px solid var(--rule); display: grid; grid-template-columns: auto auto; gap: 0 18px; padding: 14px 22px; align-content: start; font-size: 12.5px; }
.block dt { color: var(--muted); }
.block dd { margin: 0; }
.flow { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 4px; }
.flow li { padding: 8px 8px 10px; border-top: 3px solid var(--rule); background: var(--tint-out); color: var(--muted); min-width: 0; }
.flow li.in { border-top-color: var(--blue); background: var(--sheet); color: var(--ink); }
.flow li b { display: block; font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.flow li span { display: block; font-size: 11.5px; }
section { background: var(--sheet); border: 1px solid var(--rule); padding: 20px 22px 22px; display: grid; gap: 14px; }
section h2 { margin: 0; font-size: 17px; font-weight: 600; }
section h3 { margin: 6px 0 0; font-size: 14px; font-weight: 600; color: var(--muted); }
section > p { margin: 0; max-width: 80ch; }
.note { color: var(--muted); font-size: 12.5px; max-width: 90ch; margin: 0; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
th, td { text-align: left; vertical-align: top; padding: 6px 10px 6px 0; border-bottom: 1px solid var(--rule); }
thead th { font-weight: 600; color: var(--muted); font-size: 11.5px; letter-spacing: .04em; border-bottom-color: var(--ink); }
th.num, td.num { text-align: right; white-space: nowrap; }
table.kv td:first-child { white-space: nowrap; font-weight: 500; }
table.kv td:nth-child(2) { white-space: nowrap; }
table.catalog td:nth-child(4), table.catalog td:nth-child(3) { white-space: nowrap; }
table.iface th { white-space: nowrap; font-weight: 500; color: var(--ink); padding-right: 16px; width: 1%; }
table.iface td code { white-space: normal; }
.open { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 8px 18px; }
.open dt { font-weight: 500; }
.open dd { margin: 0; max-width: 90ch; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; color: var(--muted); }
.legend span::before { content: ""; display: inline-block; width: 12px; height: 12px; margin-right: 6px; vertical-align: -1px; border: 1px solid var(--rule); }
.legend .l-panel::before { background: var(--blue-fill); border-color: var(--blue); }
.legend .l-safe::before { background: var(--amber-fill); border-color: var(--amber); }
.legend .l-path::before { border: 0; border-top: 2px dashed var(--red); height: 0; }
.legend .l-zone::before { background: var(--tint); }
.legend .l-out::before { background: var(--tint-out); }
svg.sheet { width: 100%; height: auto; display: block; }
svg text { fill: var(--ink); font-size: 11px; }
svg .lbl-muted, svg .tick, svg .dimt, svg .lvl { fill: var(--muted); font-size: 10.5px; }
svg .lbl-small { font-size: 10px; }
svg .lbl-zone { fill: var(--muted); font-size: 11px; letter-spacing: .04em; }
svg .lbl-panel { fill: var(--blue); font-weight: 600; }
svg .lbl-path { fill: var(--red); font-size: 10px; }
svg .band { fill: var(--sheet); stroke: none; }
svg .aisle { fill: var(--grey-fill); stroke: none; }
svg .zone { fill: var(--tint); stroke: var(--rule); stroke-width: 1; }
svg .zone-out { fill: var(--tint-out); stroke-dasharray: 4 3; }
svg .overlap { fill: var(--red-fill); stroke: var(--red); stroke-dasharray: 3 2; stroke-width: .8; }
svg .lane { fill: none; stroke: var(--muted); stroke-dasharray: 6 4; stroke-width: .8; }
svg .ref { fill: none; stroke: var(--muted); stroke-dasharray: 3 3; stroke-width: 1; }
svg .base { fill: var(--grey-fill); stroke: var(--ink); stroke-width: .9; }
svg .deck { fill: var(--sheet); stroke: var(--ink); stroke-width: .9; }
svg .panel { fill: var(--blue-fill); stroke: var(--blue); stroke-width: 1; }
svg .panel-ghost { fill: none; stroke: var(--blue); stroke-dasharray: 3 2; stroke-width: .8; }
svg .ring { fill: var(--sheet); stroke: var(--ink); stroke-width: 1.4; }
svg .column { fill: var(--ink); stroke: none; opacity: .85; }
svg .wall { fill: var(--muted); stroke: none; opacity: .7; }
svg .beam { fill: none; stroke: var(--muted); stroke-width: 1.2; stroke-dasharray: 8 3; }
svg .sensor { fill: var(--green); stroke: none; }
svg .util { fill: var(--sheet); stroke: var(--muted); stroke-width: .9; }
svg .reach { fill: none; stroke: var(--red); stroke-width: .8; stroke-dasharray: 2 3; }
svg .pedestal { fill: var(--grey-fill); stroke: var(--ink); stroke-width: 1.2; }
svg .joint { fill: var(--sheet); stroke: var(--ink); stroke-width: 1.2; }
svg .rack { fill: var(--sheet); stroke: var(--ink); stroke-dasharray: 5 2; stroke-width: .9; }
svg .guard { fill: none; stroke: var(--amber); stroke-width: 1; stroke-dasharray: 4 2; }
svg .safety { fill: var(--amber-fill); stroke: var(--amber); stroke-width: 1; }
svg .carriage, svg .sep { fill: var(--sheet); stroke: var(--ink); stroke-width: .9; }
svg .scissor { fill: none; stroke: var(--ink); stroke-width: 1; }
svg .roller { fill: var(--grey-fill); stroke: var(--ink); stroke-width: .8; }
svg .floor { fill: var(--grey-fill); stroke: var(--ink); stroke-width: 1; }
svg .arm { fill: none; stroke: var(--ink); stroke-width: 2.2; stroke-linejoin: round; stroke-linecap: round; }
svg .arm-pick { stroke-dasharray: 5 3; opacity: .6; }
svg .path { fill: none; stroke: var(--red); stroke-width: 1.4; stroke-dasharray: 6 3; }
svg .path-reject { stroke-dasharray: 2 3; }
svg .dim { stroke: var(--muted); stroke-width: .8; }
svg .level { stroke: var(--rule); stroke-width: .7; stroke-dasharray: 2 4; }
svg .leader { stroke: var(--muted); stroke-width: .6; }
svg .centre { stroke: var(--muted); stroke-width: .7; stroke-dasharray: 14 4 3 4; }
svg .boundary { stroke: var(--red); stroke-width: .8; stroke-dasharray: 8 4; }
svg.timeline .grid { stroke: var(--rule); stroke-width: .7; }
svg.timeline .row { stroke: var(--rule); stroke-width: .7; }
svg.timeline .mark { stroke: var(--red); stroke-width: 1; }
svg.timeline .markt { fill: var(--red); font-size: 10.5px; }
svg.timeline .actor { font-size: 11.5px; }
svg.timeline .bart { font-size: 10.5px; fill: var(--ink); }
svg.timeline .bar { stroke-width: .8; }
svg.timeline .bar-prep { fill: var(--grey-fill); stroke: var(--muted); }
svg.timeline .bar-lift, svg.timeline .bar-flip { fill: var(--blue-fill); stroke: var(--blue); }
svg.timeline .bar-hold { fill: var(--sheet); stroke: var(--muted); stroke-dasharray: 3 2; }
svg.timeline .bar-safe { fill: var(--amber-fill); stroke: var(--amber); }
svg.timeline .bar-safe-hold { fill: none; stroke: var(--amber); stroke-dasharray: 3 2; }
svg.timeline .bar-robot { fill: var(--red-fill); stroke: var(--red); }
svg.timeline .bar-align { fill: var(--sheet); stroke: var(--ink); }
svg.timeline .bar-out { fill: var(--tint-out); stroke: var(--rule); }
svg.timeline .bar-reject { fill: none; stroke: var(--red); stroke-dasharray: 2 3; }
@media (max-width: 720px) {
  .title { grid-template-columns: 1fr; }
  .block { border-left: 0; border-top: 1px solid var(--rule); }
  .flow { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .open { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""


def build() -> str:
    text = plant_text()
    rev = drawing_revision(text)
    Z = zones()
    afu, robot = Z["afu"], Z["robot"]
    span = afu.length_mm + robot.length_mm
    k = kinematics
    parts = [
        "<!DOCTYPE html>",
        '<html lang="ko">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>DG 투입부 상세 — FL-101 → RB-101 인계</title>",
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        '<main class="page">',
        # 표제란
        '<header class="title">',
        "<div>",
        f'<div class="eyebrow">DYNAMIC INDUSTRY · 태양광 패널 전처리 플랜트 · 투입 구간 상세 · ENGINEERING BASE {esc(rev)}</div>',
        "<h1>투입 구간 상세 — FL-101 반입에서 RB-101 이 손을 떼는 JB-201 인계까지</h1>",
        f"<p>통합 설계도에서 투입 무리만 떼어 낸 상세도다. 지게차가 팔레트를 놓는 자리부터 로봇이 PT-101 에 패널을 놓고 3-2-1 정렬이 좌표시드를 만들어 JB-201 이 JBR-201 로 넘기는 지점까지 — "
        f"플랜트 X {n(afu.x0_mm)} … {n(robot.x1_mm)} ({n(span)} mm), afu·robot 두 존이다. 값은 전부 배치·기구학·캠페인·서보·전기·비전·안전·장착 모델과 통합 설계도의 부품표에서 읽어 찍었다.</p>",
        "</div>",
        '<dl class="block">',
        f"<dt>시트</dt><dd class=\"mono\">{SHEET_NO}</dd>",
        f"<dt>기준 도면</dt><dd class=\"mono\">PV-AFU-101-GA-2101 · PV-BFC-101-ASM-2201 · PV-RBPT-101-GA-2301</dd>",
        f"<dt>범위</dt><dd>afu {n(afu.length_mm)} + robot {n(robot.length_mm)} = {n(span)} mm</dd>",
        f"<dt>이송면</dt><dd>픽업 {n(k.PICK_FACE_MM)} → 인계 {n(k.HANDOVER_MM)} → 라인 {n(layout.LINE_TRANSFER_MM)}</dd>",
        f"<dt>한 장 점유</dt><dd>{campaign.INFEED_S:g} s · 방출 주기 {campaign.release_takt_s():g} s</dd>",
        "<dt>생성</dt><dd class=\"mono\">tools/build_infeed_detail.py</dd>",
        "</dl>",
        "</header>",
        # 범위
        '<section id="scope">',
        "<h2>범위 — 플랜트 흐름 안에서 이 상세도가 다루는 자리</h2>",
        flow_strip(),
        "<p class=\"note\">로봇이 PT-101 에 패널을 놓고 스톱·푸셔가 좌표시드를 만든 뒤 JB-201 축적런이 JBR-201 로 넘기는 순간이 경계다. 그 뒤(JBR-201 정션박스 제거부터)는 통합 설계도를 본다. 투입부는 라인 병목이 아니다 — 병목은 "
        f"{esc(campaign.bottleneck())} 이고 투입부는 {campaign.INFEED_S:g} s 로 그보다 짧다.</p>",
        "</section>",
        # 평면
        '<section id="plan">',
        "<h2>평면 배치</h2>",
        '<div class="legend"><span class="l-zone">존 (범위 안)</span><span class="l-panel">패널·적층</span><span class="l-safe">포획빔·가드</span><span class="l-path">로봇 경로 / 도달 반경</span></div>',
        plan_view(),
        "<p class=\"note\">Bay A/B 는 라인 중심에 대칭이다. 반전 드럼(두 엔드링)은 적층 바로 위에 서므로 수평 셔틀이 없고, 지게차는 팔레트를 링 밑으로 밀어 넣는다. BFC 하류 포탈 기둥 발판은 로봇 존으로 "
        f"{n(layout.zone_overlap_mm('afu'))} mm 물려 있다 — 로봇이 베이 안으로 팔을 넣어 픽업하려면 그래야 한다(설계 넘침).</p>",
        "</section>",
        # 입면
        '<section id="elevation">',
        "<h2>입면과 레벨</h2>",
        elevation_view(),
        "<h3>기구학 여유 — 반전 카세트 안에서 패널이 지나가는 자리</h3>",
        kinematics_table(),
        "</section>",
        # 시퀀스
        '<section id="timeline">',
        "<h2>한 장의 시각표</h2>",
        timeline_view(),
        sequence_table(),
        "<p class=\"note\">7.5 – 24.0 s 는 kinematics.PATH 의 다섯 구간이고 3D 공정시계의 분기 시각과 같다. 24 – 40 s 는 로봇의 몫이며, 40 s 에 JBR 이 받고 8 s 뒤 스토퍼가 물리는 순간 로봇이 다음 장을 내려놓는다 — "
        f"그래서 방출 주기는 {campaign.release_takt_s():g} s 다. 전손은 반전을 생략하고 {campaign.INFEED_REJECT_S:g} s 만 쓴다.</p>",
        "</section>",
        # 로봇 도달·스테이션
        '<section id="reach">',
        "<h2>로봇 도달 사슬과 투입 스테이션</h2>",
        "<p>투입 무리의 X 자리는 한 방향 사슬이다. 적층은 지게차 여유가, 페데스털은 인계점 도달이, PT-101 은 JBR 축적런이 정하고 — 그 넷이 동시에 서려면 afu 존 길이가 딱 하나로 정해진다.</p>",
        reach_table(),
        "<h3>PT-101 + JB-201 — 정반과 축적런은 한 스테이션이다</h3>",
        station_table(),
        "</section>",
        # 판정·캠페인
        '<section id="campaign">',
        "<h2>판정·분류와 연속 운전</h2>",
        classification_table(),
        "<h3>60장 캠페인에서 투입부가 하는 일</h3>",
        campaign_table(),
        "<h3>지게차 동작</h3>",
        forklift_table(),
        "</section>",
        # 인터페이스
        '<section id="interface">',
        "<h2>운전 조건·허가·인계 (통합 설계도 인터페이스 표에서)</h2>",
        interface_table(text),
        "</section>",
        # 부품
        '<section id="parts">',
        "<h2>부품표 — 투입 무리</h2>",
        catalog_table(text),
        "</section>",
        # 구동·전기
        '<section id="drives">',
        "<h2>구동·전기</h2>",
        drives_table(),
        "<h3>전동–기구 검산</h3>",
        transmission_table(),
        f"<p class=\"note\">반전축이 돌리는 것은 링·조·패드·패널 <strong>{drives.flip_rotating_kg():.0f} kg</strong> "
        f"(관성 {drives.flip_inertia_kgm2():.0f} kg·m²)이지 포탈을 포함한 인양 무게가 아니다. "
        "승강축은 감속기 없이 직결한다 — 리드 10 에 i=10 을 물리면 모터가 25,000 rpm 이어야 했다.</p>",
        "<h3>급전</h3>",
        feeders_table(),
        "<p class=\"note\">서보는 EtherCAT CoE(CSP) · FSoE STO 계층에 올라간다. 중력·자세 유지 축(승강·반전·포획빔 승강·로봇 관절)은 전부 브레이크가 있다.</p>",
        "</section>",
        # 비전·센서
        '<section id="vision">',
        "<h2>비전·센서</h2>",
        vision_table(),
        "</section>",
        # 안전
        '<section id="safety">',
        "<h2>안전 — 위험원과 안전기능</h2>",
        safety_table(),
        "<h3>안전기능</h3>",
        safety_functions_table(),
        "</section>",
        # 장착·가동
        '<section id="mounting">',
        "<h2>지지·장착과 가동</h2>",
        mounting_table(),
        "<h3>브래킷 금지 부피 — 팔레트가 쓸고 지나가는 자리</h3>",
        keepout_table(),
        "<h3>가동·정비</h3>",
        uptime_table(),
        "</section>",
        # 미결
        '<section id="open">',
        "<h2>미결 · 발주처 확인 항목</h2>",
        open_items(),
        "</section>",
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024:.0f} kB")


if __name__ == "__main__":
    main()
