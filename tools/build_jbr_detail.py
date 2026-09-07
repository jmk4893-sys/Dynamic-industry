# -*- coding: utf-8 -*-
"""JBR-201 상세도 — 투입공정이 넘긴 패널을 받아 정션박스·케이블을 떼는 셀 하나.

3D 파생본(`tools/build_jbr_scene.py`)이 이 장비가 **움직이는 것**을 보여 준다면,
이 상세도는 그 움직임이 무엇에서 나온 값인지를 한 장에 편다 — 자리·시각·축 궤적·
검출 시나리오·차단 시나리오·인계 조건·구동·유틸리티·안전·신뢰도·부품 112 품번.

**손으로 쓰지 않는다.** 값은 두 곳에서만 온다.

1. 파이썬 모델 — `layout`(존·외형·이송면), `campaign`(점유·택트·스토퍼 오프셋),
   `servos`(축), `electrical`·`wiring`(피더·케이블), `air`·`dust`·`acoustics`·
   `thermal`(유틸리티), `safety`(위험원·PL·정지사슬), `reliability`(정지시간·예비품),
   `mounting`·`access`(앵커·접근).
2. 통합 설계도 `docs/drawings/pv-preprocess-plant.html` 의 리터럴 — GA 시트
   (`stations.jbr`), 공정 스테이지(`gl`), 검출 시나리오(`hp`), 차단 시각(`w`),
   부품표(`wo` 의 JB-*), 인터페이스 표, 힘 검산 상수.

두 곳 중 어느 하나가 바뀌면 이 시트도 바뀌어야 하고, `tests/test_pv_jbr.py` 가
커밋된 파일과 생성 결과를 견주므로 잊으면 시험이 실패한다.

    PYTHONPATH=src python tools/build_jbr_detail.py

멱등이다.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import (access, acoustics, air, campaign, dust,  # noqa: E402
                           electrical, handoff, layout, mounting, reliability,
                           safety, servos, thermal, wiring)

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-jbr-detail.html"

#: 이 시트가 다루는 셀.
CELL = "jbr"

#: 3D 월드 원점의 플랜트 X (mm) — build_literals.SCENE_ORIGIN_X_MM 과 같은 규약.
SCENE_ORIGIN_X_MM = 24_750

#: 플랜트 Y 좌표 = 라인 중심 + 3D z. 장비 밴드의 한가운데다.
LINE_CENTER_Y_MM = 3_550

#: 통합 설계도 인터페이스 표에서 그대로 옮기는 행.
INTERFACE_ROWS: tuple[str, ...] = (
    "기계 연결", "핸드셰이크", "패킷 v1.2", "좌표 적용",
    "JBR→AFR 허가", "JBR→AFR 직결", "패널 구조 레시피",
)

#: JBR-201 이 쓰는 서보·모터 태그 (servos.py 의 panel 키로 고른다).
DRIVE_PANEL = "LP-JBR"

#: 차단 시나리오의 화면 라벨 — `#jb-validation-mode` 의 option 순서 그대로 읽는다.
VALIDATION_SELECT_ID = "jb-validation-mode"

#: 검출 시나리오 select.
BOX_SELECT_ID = "jb-box-mode"


# ── 원본에서 읽기 ────────────────────────────────────────────────────────
def plant_text() -> str:
    return PLANT.read_text(encoding="utf-8")


def drawing_revision(text: str) -> str:
    return re.search(r"DRAWING_REVISION = '([^']+)'", text).group(1)


def _bracket(text: str, start: int) -> str:
    """`text[start]` 의 여는 괄호와 짝이 맞는 곳까지 잘라 낸다 (문자열 안은 건너뛴다)."""
    pairs = {"[": "]", "{": "}", "(": ")"}
    open_ch = text[start]
    close_ch = pairs[open_ch]
    depth, i = 0, start
    while i < len(text):
        ch = text[i]
        if ch in ('"', "'", "`"):
            quote = ch
            i += 1
            while text[i] != quote:
                i += 2 if text[i] == "\\" else 1
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise SystemExit("✗ 괄호가 닫히지 않는다")


def ga_sheet(text: str) -> dict[str, object]:
    """GA 시트 리터럴 `stations.jbr` — 사람이 읽는 줄이라 항목별로 꺼낸다."""
    start = text.index("\n    jbr: {")
    block = _bracket(text, text.index("{", start))

    def one(field: str, pattern: str) -> str:
        m = re.search(rf"^\s*{field}: {pattern},?\s*$", block, re.M)
        if not m:
            raise SystemExit(f"✗ GA 시트에 {field} 가 없다")
        return m.group(1)

    envelope = json.loads(one("envelope", r"(\[[^\]]*\])"))
    levels = [(int(a), b) for a, b in
              re.findall(r"\[(\d+), '([^']*)'\]", one("levels", r"(\[.*\])"))]
    parts = [(m[0], m[1], json.loads(m[2]), json.loads(m[3]), json.loads(m[4]))
             for m in re.findall(
                 r"part\('([^']+)', '([^']+)', (\[[^\]]*\]), (\[[^\]]*\]), (\[[^\]]*\])",
                 block)]
    flow = [(m[0], m[1], json.loads(m[2]), json.loads(m[3]))
            for m in re.findall(
                r"step\('([^']+)', '([^']+)', (\[[^\]]*\]), (\[[^\]]*\])\)", block)]
    return {
        "sheet": one("sheet", r"'([^']*)'"),
        "name": one("name", r"'([^']*)'"),
        "envelope": envelope,
        "transfer": int(one("transfer", r"(\d+)")),
        "datum": one("datum", r"'([^']*)'"),
        "anchors": one("anchors", r"'([^']*)'"),
        "tolerance": one("tolerance", r"'([^']*)'"),
        "service": one("service", r"'([^']*)'"),
        "utility": one("utility", r"'([^']*)'"),
        "release": one("release", r"'([^']*)'"),
        "levels": levels,
        "parts": parts,
        "flow": flow,
    }


def stages(text: str) -> list[tuple[str, float, float]]:
    """JBR 공정 스테이지 `gl` — (이름, 로컬 start, 로컬 end)."""
    i = text.index("var Vt=40,gl=[")
    block = _bracket(text, text.index("[", i))
    rows = re.findall(r'\{name:"([^"]+)",start:([\d.]+),end:([\d.]+)\}', block)
    if not rows:
        raise SystemExit("✗ JBR 스테이지 배열을 못 읽었다")
    offset = float(re.search(r"var Vt=(\d+(?:\.\d+)?),gl=", text).group(1))
    if offset != campaign.INFEED_S:
        raise SystemExit(f"✗ 도면의 JBR 오프셋 {offset} 이 campaign.INFEED_S 와 다르다")
    return [(n, float(a), float(b)) for n, a, b in rows]


def stage_axes(text: str) -> list[tuple[str, list[str]]]:
    """스테이지 이름 → 지령 축. 원본의 STAGE_AXES 를 그대로 읽는다."""
    i = text.index("var STAGE_AXES = [")
    block = _bracket(text, text.index("[", i))
    return [(m[0], json.loads(m[1].replace("'", '"')))
            for m in re.findall(r"\[/([^/]+)/, (\[[^\]]*\])\]", block)]


def box_scenarios(text: str) -> list[dict[str, object]]:
    """검출 시나리오 `hp` — 정션박스 개수·좌표·각도."""
    i = text.index("var hp={")
    block = _bracket(text, text.index("{", i))
    out = []
    for key, body in re.findall(r'"([a-z-]+)":\{(.*?)\},?(?=(?:"[a-z-]+":\{)|$)', block, re.S):
        boxes = [{k: float(v) for k, v in re.findall(r"(\w+):(-?[\d.]+)", b)}
                 for b in re.findall(r"\{(x:[^}]*)\}", body)]
        out.append({
            "key": key,
            "label": re.search(r'label:"([^"]*)"', body).group(1),
            "topology": re.search(r'topology:"([^"]*)"', body).group(1),
            "plan": re.search(r'plan:"([^"]*)"', body).group(1),
            "boxes": boxes,
        })
    if len(out) != 4:
        raise SystemExit(f"✗ 검출 시나리오가 {len(out)}개 — 4개여야 한다")
    return out


def block_times(text: str) -> dict[str, float]:
    """차단 시각 `w` — 시나리오별 선행 차단이 걸리는 JBR 로컬 시각 (s)."""
    m = re.search(r'w=Le==="voltage"\|\|Le==="probe"\?([\d.]+):'
                  r'Le==="coverage"\|\|Le==="support"\?([\d.]+):'
                  r'Le==="recipe"\?([\d.]+):Le==="tool"\?([\d.]+):'
                  r'Le==="postfail"\?([\d.]+):1/0', text)
    if not m:
        raise SystemExit("✗ 차단 시각 w 를 못 읽었다")
    v, c, r, t, p = (float(x) for x in m.groups())
    return {"voltage": v, "probe": v, "coverage": c, "support": c,
            "recipe": r, "tool": t, "postfail": p}


def select_options(text: str, select_id: str) -> list[tuple[str, str]]:
    """`<select id=…>` 의 (value, 라벨)."""
    i = text.index(f'id="{select_id}"')
    end = text.index("</select>", i)
    return re.findall(r'<option value="([^"]+)"[^>]*>([^<]*)</option>', text[i:end])


def head_force(text: str) -> tuple[int, int, dict[str, int]]:
    """힘 검산 상수 — 헤드 1기 용량 kN, 설치 헤드 수, 시나리오별 박스 수."""
    cap = int(re.search(r"var HEAD_CAPACITY_KN = (\d+);", text).group(1))
    count = int(re.search(r"var HEAD_COUNT = (\d+);", text).group(1))
    raw = re.search(r"var BOX_COUNT = \{([^}]*)\};", text).group(1)
    boxes = {k: int(v) for k, v in re.findall(r"'([a-z-]+)': (\d+)", raw)}
    return cap, count, boxes


def catalog(text: str) -> list[list[object]]:
    """부품표 `wo` 에서 JB-* 행만. 스키마는 원본의 map 인자 순서 그대로다."""
    i = text.index(',wo=[["AFU-FL-101"')
    rows = json.loads(_bracket(text, text.index("[", i)))
    jb = [r for r in rows if str(r[0]).startswith("JB-") and len(r) >= 10]
    if not jb:
        raise SystemExit("✗ 부품표에서 JB-* 를 못 찾았다")
    return jb


def interface_rows(text: str) -> list[tuple[str, str]]:
    out = []
    for name in INTERFACE_ROWS:
        m = re.search(r"<tr><th>%s</th><td>(.*?)</td></tr>" % re.escape(name), text, re.S)
        if not m:
            raise SystemExit(f"✗ 인터페이스 표에 '{name}' 행이 없다")
        out.append((name, m.group(1).strip()))
    return out


# ── 값 ──────────────────────────────────────────────────────────────────
def n(v: float) -> str:
    if isinstance(v, float) and abs(v - round(v)) > 1e-9:
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{int(round(v)):,}"


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def zone(key: str = CELL) -> layout.Zone:
    return next(z for z in layout.build_zones() if z.key == key)


def world_to_plant_x(world_m: float) -> float:
    return world_m * 1000 + SCENE_ORIGIN_X_MM


def window() -> tuple[float, float]:
    return campaign.INFEED_S, campaign.INFEED_S + campaign.JBR_S


def hardware_span_mm() -> tuple[float, float]:
    """장비가 실제로 차지하는 X (플랜트 mm) — 존에서 가드 여유를 뺀 것."""
    z = zone()
    up, _ = layout.station_edges_mm(CELL)
    x0 = z.x0_mm + up
    return x0, x0 + layout.STATION_HARDWARE_X_MM[CELL]


def origin_offset_mm() -> float:
    """장비 중심이 존 중심에서 얼마나 하류인가.

    가드 여유가 상류 475 · 하류 125 로 **비대칭**이라 둘이 겹치지 않는다. GA 시트의
    부품 좌표는 장비 중심이 원점이고(BASE 를 at[0]=0 에 두면 존 여유가 모델의
    475/125 로 정확히 떨어진다), 3D 장면은 셀 그룹 원점을 존 중심 `gt` 에 둔다.
    그래서 같은 부품이 3D 에서 이만큼 상류로 읽힌다 — 상세도는 GA 규약을 따른다.
    """
    z = zone()
    x0, x1 = hardware_span_mm()
    return (x0 + x1) / 2 - (z.x0_mm + z.x1_mm) / 2


# ── SVG ─────────────────────────────────────────────────────────────────
class Sheet:
    """플랜트 mm 을 화면 px 로 옮기는 작은 제도판."""

    def __init__(self, x0: float, x1: float, y0: float, y1: float, width: int,
                 pad: tuple[int, int, int, int] = (34, 30, 34, 30), flip_y: bool = False):
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.pad, self.width, self.flip_y = pad, width, flip_y
        self.scale = (width - pad[1] - pad[3]) / (x1 - x0)
        self.height = int((y1 - y0) * self.scale) + pad[0] + pad[2]
        self.parts: list[str] = []

    def X(self, x: float) -> float:
        return round(self.pad[3] + (x - self.x0) * self.scale, 1)

    def Y(self, y: float) -> float:
        if self.flip_y:
            return round(self.pad[0] + (self.y1 - y) * self.scale, 1)
        return round(self.pad[0] + (y - self.y0) * self.scale, 1)

    def rect(self, x0, x1, y0, y1, cls, title=None, rx=0) -> None:
        xa, xb = sorted((self.X(x0), self.X(x1)))
        ya, yb = sorted((self.Y(y0), self.Y(y1)))
        t = f"<title>{esc(title)}</title>" if title else ""
        self.parts.append(f'<rect class="{cls}" x="{xa}" y="{ya}" width="{round(xb - xa, 1)}" '
                          f'height="{round(yb - ya, 1)}" rx="{rx}">{t}</rect>')

    def line(self, x0, y0, x1, y1, cls) -> None:
        self.parts.append(f'<line class="{cls}" x1="{self.X(x0)}" y1="{self.Y(y0)}" '
                          f'x2="{self.X(x1)}" y2="{self.Y(y1)}"/>')

    def circle(self, x, y, r_mm, cls, title=None) -> None:
        t = f"<title>{esc(title)}</title>" if title else ""
        self.parts.append(f'<circle class="{cls}" cx="{self.X(x)}" cy="{self.Y(y)}" '
                          f'r="{round(r_mm * self.scale, 1)}">{t}</circle>')

    def text(self, x, y, s, cls="lbl", anchor="start", dx=0.0, dy=0.0, rotate=None) -> None:
        px, py = self.X(x) + dx, self.Y(y) + dy
        tr = f' transform="rotate({rotate} {px} {py})"' if rotate is not None else ""
        self.parts.append(f'<text class="{cls}" x="{px}" y="{py}" '
                          f'text-anchor="{anchor}"{tr}>{esc(s)}</text>')

    def dim_x(self, x0, x1, y, label, above=True) -> None:
        xa, xb, py = self.X(x0), self.X(x1), self.Y(y)
        self.parts.append(f'<line class="dim" x1="{xa}" y1="{py}" x2="{xb}" y2="{py}"/>')
        for px in (xa, xb):
            self.parts.append(f'<line class="dim" x1="{px}" y1="{py - 5}" x2="{px}" y2="{py + 5}"/>')
        self.parts.append(f'<text class="dimt" x="{round((xa + xb) / 2, 1)}" '
                          f'y="{py + (-5 if above else 13)}" text-anchor="middle">{esc(label)}</text>')

    def dim_y(self, y0, y1, x, label, right=True) -> None:
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


#: 평면에 이름을 적는 부품과 그 라벨의 세로 보정 (px). PLATEN·BRIDGE 는 둘 다
#: 라인 중심에 있어 0 으로 두면 글자가 겹쳐 읽힌다.
MARKED: dict[str, int] = {"PLATEN": -9, "BRIDGE": 15, "BIN": 3, "HD-1": 3, "HD-3": 3}


def plan_view(ga: dict[str, object]) -> str:
    """평면 — 존 경계, 가드 여유, 하드웨어 폭, JB-201 축적런 겹침, 부품 자리."""
    jbr, robot, afr = zone("jbr"), zone("robot"), zone("afr")
    acc0, acc1 = layout.accumulator_span_mm()
    up, down = layout.station_edges_mm(CELL)
    hw = layout.STATION_HARDWARE_X_MM[CELL]
    hw0, hw1 = hardware_span_mm()
    y0, y1 = jbr.y0_mm, jbr.y1_mm
    cy = LINE_CENTER_Y_MM

    s = Sheet(acc0 - 700, jbr.x1_mm + 900, y0 - 780, y1 + 420, 1180)
    # 상·하류는 범위 밖이라 존도 장비도 그리지 않는다 — 방향만 적는다. 이웃 사각형이
    # 있으면 어디까지가 이 장비인지 그림에서 갈리지 않는다.
    s.text(jbr.x0_mm - 240, y0 + 210, "← RB-101 · PT (범위 밖)", "lbl small", "end")
    # 오른쪽 위는 존·하드웨어 치수선이 쓰고 있다 — 하류 표기는 아래로 내린다.
    s.text(jbr.x1_mm, y1 + 250, "→ AFR-101 (범위 밖)", "lbl small", "end")
    # 존과 가드
    s.rect(jbr.x0_mm, jbr.x1_mm, y0, y1, "zone", f"jbr 존 {n(jbr.x0_mm)} … {n(jbr.x1_mm)}")
    s.rect(hw0, hw1, cy - 1_100, cy + 1_100, "hw", "하드웨어 폭 (베이스 프레임)")
    # 이송 라인
    s.line(acc0, cy, afr.x0_mm + 1_400, cy, "centre")
    # JB-201 축적·인계 런 (상류 스테이션이지만 셀 귀속은 jbr)
    s.rect(acc0, acc1, cy - 950, cy + 950, "accum",
           f"JB-201 축적·인계 런 {n(layout.ACCUM_RUN_MM)} mm")
    s.text((acc0 + acc1) / 2, cy - 1_060, "JB-201 축적·인계", "lbl small", "middle")
    # GA 부품 자리 — part(at) 은 셀 중심 기준 [X, 상하, 깊이]
    ox = (hw0 + hw1) / 2
    marks = []
    for pid, label, size, at, _ in ga["parts"]:
        if pid == "GUARD":
            continue
        px, pz = ox + at[0], cy + at[2]
        s.rect(px - size[0] / 2, px + size[0] / 2, pz - size[2] / 2, pz + size[2] / 2,
               "part", f"{pid} · {label} · {n(size[0])}×{n(size[2])} mm")
        if pid in MARKED:
            marks.append((px, pz, pid))
    # 라벨은 모든 부품을 그린 **뒤에** 얹는다 — 나중에 그리는 사각형이 앞 라벨을 덮는다.
    # PLATEN 과 BRIDGE 는 둘 다 라인 중심에 서므로 세로로 갈라 놓지 않으면 겹쳐 읽힌다.
    for px, pz, pid in marks:
        s.text(px, pz, pid, "lbl tiny", "middle", dy=MARKED[pid])
    # 치수
    s.dim_x(jbr.x0_mm, jbr.x1_mm, y0 - 250, f"존 {n(jbr.x1_mm - jbr.x0_mm)}")
    s.dim_x(hw0, hw1, y0 - 100, f"하드웨어 {n(hw)}")
    s.dim_x(jbr.x0_mm, hw0, y0 - 460, f"가드 여유 {n(up)}")
    s.dim_x(hw1, jbr.x1_mm, y0 - 460, f"{n(down)}")
    s.dim_x(acc0, acc1, y1 + 250, f"축적런 {n(acc1 - acc0)}", above=False)
    s.dim_y(y0, y1, jbr.x1_mm + 320, f"{n(y1 - y0)}")
    s.text(jbr.x0_mm + 120, y0 + 420, f"jbr · {jbr.note}", "lbl")
    s.text(acc0, cy + 1_180, f"PT-101 정반과 {n(layout.pt_accumulator_overlap_mm())} mm 겹친다",
           "lbl small")
    return s.svg("JBR-201 평면 — 존·가드 여유·하드웨어 폭·부품 자리")


def elevation_view(ga: dict[str, object]) -> str:
    """정면 — 레벨선과 부품 높이. 원점은 하드웨어 중심, 바닥이 0 이다."""
    jbr = zone("jbr")
    hw = layout.STATION_HARDWARE_X_MM[CELL]
    hw0, _ = hardware_span_mm()
    ox = hw0 + hw / 2
    top = jbr.height_mm

    s = Sheet(hw0 - 900, hw0 + hw + 900, -520, top + 420, 1180, flip_y=True)
    s.line(hw0 - 900, 0, hw0 + hw + 900, 0, "ground")
    s.rect(jbr.x0_mm, jbr.x1_mm, 0, top, "zone", f"셀 외형 높이 {n(top)} mm")
    for pid, label, size, at, _ in ga["parts"]:
        if pid == "GUARD":
            continue
        px, py = ox + at[0], at[1]
        s.rect(px - size[0] / 2, px + size[0] / 2, py - size[1] / 2, py + size[1] / 2,
               "part", f"{pid} · {label} · {n(size[0])}×{n(size[1])} mm · 중심 H{n(py)}")
    for level, label in ga["levels"]:
        s.line(hw0 - 780, level, hw0 + hw + 780, level, "level")
        s.text(hw0 + hw + 800, level, label, "lbl small", "end", dy=-5)
    s.line(hw0 - 780, ga["transfer"], hw0 + hw + 780, ga["transfer"], "level on")
    s.text(hw0 - 800, ga["transfer"], f"이송면 {n(ga['transfer'])}", "lbl small", "start", dy=-5)
    s.dim_y(0, top, hw0 - 620, f"{n(top)}", right=False)
    s.dim_x(hw0, hw0 + hw, -300, f"하드웨어 {n(hw)}", above=False)
    return s.svg("JBR-201 정면 — 레벨선과 부품 높이")


def gantt_view(rows: list[tuple[str, float, float]],
               axes: list[tuple[str, list[str]]]) -> str:
    """45 s 공정시계 — 스테이지 막대와 지령 축."""
    t0, t1 = window()
    span = campaign.JBR_S
    width, row_h, left = 1180, 26, 300
    height = 62 + row_h * len(rows)
    out = [f'<svg class="sheet gantt" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="JBR-201 45 초 공정시계">']

    def px(local: float) -> float:
        return round(left + local / span * (width - left - 24), 1)

    for tick in range(0, int(span) + 1, 5):
        x = px(tick)
        out.append(f'<line class="grid" x1="{x}" y1="34" x2="{x}" y2="{height - 22}"/>')
        out.append(f'<text class="dimt" x="{x}" y="26" text-anchor="middle">'
                   f'{tick} s</text>')
        out.append(f'<text class="dimt dim2" x="{x}" y="{height - 8}" text-anchor="middle">'
                   f'{n(t0 + tick)}</text>')
    out.append(f'<text class="lbl small" x="8" y="26">JBR 로컬 (s)</text>')
    out.append(f'<text class="lbl small" x="8" y="{height - 8}">플랜트 공정시계 (s)</text>')
    for i, (name, a, b) in enumerate(rows):
        y = 40 + i * row_h
        out.append(f'<rect class="bar" x="{px(a)}" y="{y}" width="{max(2.0, px(b) - px(a))}" '
                   f'height="{row_h - 8}" rx="3"><title>{esc(name)} · '
                   f'{n(a)}–{n(b)} s (플랜트 {n(t0 + a)}–{n(t0 + b)} s)</title></rect>')
        out.append(f'<text class="lbl tiny" x="{left - 10}" y="{y + row_h - 15}" '
                   f'text-anchor="end">{esc(name)}</text>')
        tags = axis_tags_for(name, axes)
        if tags:
            # 오른쪽 끝에 붙는 막대는 뒤에 글자를 놓을 자리가 없다 — 막대 안쪽에 오른쪽 정렬한다.
            label = " · ".join(tags)
            fits = px(b) + 8 + len(label) * 5.6 < width - 8
            tx = px(b) + 6 if fits else px(b) - 6
            anchor = "start" if fits else "end"
            cls = "lbl tiny axis" + ("" if fits else " inbar")
            out.append(f'<text class="{cls}" x="{tx}" y="{y + row_h - 15}" '
                       f'text-anchor="{anchor}">{esc(label)}</text>')
    out.append("</svg>")
    return "".join(out)


def axis_tags_for(name: str, axes: list[tuple[str, list[str]]]) -> list[str]:
    """스테이지 이름에 걸리는 첫 규칙의 축 — 원본 STAGE_AXES 와 같은 판정이다."""
    for pattern, tags in axes:
        if re.search(pattern, name):
            return tags
    return []


# ── 표 ──────────────────────────────────────────────────────────────────
def table(head: list[str], rows: list[list[object]], cls: str = "",
          num_cols: tuple[int, ...] = ()) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = []
    for row in rows:
        tds = []
        for i, cell in enumerate(row):
            c = ' class="num"' if i in num_cols else ""
            tds.append(f"<td{c}>{cell if isinstance(cell, str) else esc(cell)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="tw"><table class="t {cls}"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def _md(s: str) -> str:
    """모델 주석의 **강조** 만 옮긴다."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


def scope_table(ga: dict[str, object]) -> str:
    jbr = zone("jbr")
    up, down = layout.station_edges_mm(CELL)
    acc0, acc1 = layout.accumulator_span_mm()
    rows = [
        ["시트번호", f"<code>{esc(ga['sheet'])}</code>"],
        ["명칭", esc(ga["name"])],
        ["존 X (플랜트)", f"{n(jbr.x0_mm)} … {n(jbr.x1_mm)} mm · 길이 {n(jbr.x1_mm - jbr.x0_mm)}"],
        ["존 Y (플랜트)", f"{n(jbr.y0_mm)} … {n(jbr.y1_mm)} mm · 폭 {n(jbr.y1_mm - jbr.y0_mm)}"],
        ["외형", f"{n(ga['envelope'][0])} × {n(ga['envelope'][1])} × {n(ga['envelope'][2])} mm"],
        ["하드웨어 폭", f"{n(layout.STATION_HARDWARE_X_MM[CELL])} mm "
                    f"(가드 여유 상류 {n(up)} · 하류 {n(down)})"],
        ["이송면", f"H {n(ga['transfer'])} mm — {esc(', '.join(layout.SHARED_LINE))} 가 같은 면"],
        ["기준", esc(ga["datum"])],
        ["공차", esc(ga["tolerance"])],
        ["정비 여유", esc(ga["service"])],
        ["유틸리티", esc(ga["utility"])],
        ["JB-201 축적런", f"{n(acc0)} … {n(acc1)} mm ({n(layout.ACCUM_RUN_MM)} mm) — "
                       f"셀 귀속은 jbr 이나 자리는 robot 존을 넘어온다"],
        ["통합 제거셀", f"{esc(' + '.join(layout.INTEGRATED_CELL))} = "
                    f"{n(layout.integrated_cell_length_mm())} mm "
                    f"(따로 세울 때보다 {n(layout.integrated_saving_mm())} mm 짧다)"],
        ["출하 조건", esc(ga["release"])],
    ]
    return table(["항목", "값"], rows, "kv")


def clock_table(rows: list[tuple[str, float, float]],
                axes: list[tuple[str, list[str]]]) -> str:
    t0, _ = window()
    out = []
    for i, (name, a, b) in enumerate(rows, 1):
        tags = axis_tags_for(name, axes)
        out.append([i, esc(name), n(a), n(b), n(b - a), n(t0 + a), n(t0 + b),
                    ", ".join(tags) or "—"])
    return table(["#", "스테이지", "시작", "끝", "길이", "플랜트 시작", "플랜트 끝", "지령 축"],
                 out, num_cols=(0, 2, 3, 4, 5, 6))


def occupancy_table() -> str:
    rows = [[name, n(sec)] for name, sec in campaign.cell_occupancy_s()]
    return table(["셀", "점유 (s)"], rows, num_cols=(1,))


def box_table(scen: list[dict[str, object]], cap: int, heads: int,
              counts: dict[str, int], labels: dict[str, str]) -> str:
    rows = []
    for s in scen:
        boxes = s["boxes"]
        zs = sorted(b["z"] for b in boxes)
        gap = min((round((b - a) * 1000) for a, b in zip(zs, zs[1:])), default=0)
        angles = " / ".join(f"{b['angle'] * 180 / 3.141592653589793:+.1f}°" for b in boxes)
        used = min(counts[s["key"]], heads)
        rows.append([
            esc(labels.get(s["key"], s["key"])),
            counts[s["key"]],
            used,
            esc(s["topology"]),
            n(round(boxes[0]["x"] * 1000)),
            " / ".join(n(round(b["z"] * 1000)) for b in boxes),
            n(gap) if gap else "—",
            angles,
            f"{cap * used}",
            esc(s["plan"]),
        ])
    return table(["시나리오", "검출", "활성 헤드", "topology", "공통 X (mm)",
                  "박스 Z (mm)", "최소 간격", "각도", "가용 추력 (kN)", "계획"],
                 rows, num_cols=(1, 2, 6, 8))


def validation_table(options: list[tuple[str, str]], w: dict[str, float]) -> str:
    t0, _ = window()
    #: 화면이 실제로 바꾸는 것 — 3D 번들의 판정 분기와 같은 내용이다.
    effect = {
        "normal": ("—", "정상 반출", "PASS 반출 · 추적성 데이터 저장"),
        "voltage": ("절단 허가", "선행 리젝트", "2극 전압 FAIL — 비전 스캔도 돌지 않는다"),
        "probe": ("절단 허가", "선행 리젝트", "프로브 SELF-TEST FAIL — 비전 스캔도 돌지 않는다"),
        "recipe": ("절단 허가", "선행 리젝트",
                   "좌표열·케이블 topology 불일치. 미등록 구조 레시피는 선택과 무관하게 이 경로다"),
        "coverage": ("헤드 배치", "선행 리젝트", "검출 각도가 패시브 요 ±3° 를 넘는다"),
        "support": ("칼날 접근", "선행 리젝트", "24구역 지지좌표가 제거 좌표를 받치지 못한다"),
        "tool": ("박리 허가", "선행 리젝트", "공구 ID·칼날 상태 FAIL"),
        "postfail": ("정상 반출", "격리 리젝트",
                     "절단·박리·포획·배출을 다 하고 후검증에서 걸린다"),
        "muting": ("전 축", "안전정지 래치", "뮤팅 순서·timeout 불일치 — 외부 수동 리셋 전 복귀 없음"),
        "buffer-full": ("셀 진입", "상류 HOLD", "리젝트 버퍼가 비지 않으면 게이트를 열지 않는다"),
    }
    rows = []
    for key, label in options:
        blocked, route, note = effect[key]
        local = w.get(key)
        rows.append([
            esc(label.split(" · ")[0]),
            f"<code>{esc(key)}</code>",
            n(local) if local is not None else "—",
            n(t0 + local) if local is not None else "—",
            esc(blocked),
            esc(route),
            esc(note),
        ])
    return table(["시나리오", "값", "차단 (로컬 s)", "차단 (플랜트 s)", "차단 대상",
                  "물리 경로", "비고"], rows, num_cols=(2, 3))


def drive_table() -> str:
    axes = [a for a in servos.SERVO_AXES if a.panel == DRIVE_PANEL]
    motors = [m for m in servos.MOTORS if m.panel == DRIVE_PANEL]
    rows = [[a.tag, a.motion, a.qty, n(a.rated_kw), n(a.rated_kw * a.qty), a.drive,
             a.feedback, "有" if a.brake else "—", _md(a.note)]
            for a in axes + motors]
    total = sum(a.rated_kw * a.qty for a in axes + motors)
    rows.append(["<b>합계</b>", f"서보 {servos.servo_axis_count_for(DRIVE_PANEL)} 축 + 비서보 "
                 f"{sum(m.qty for m in motors)}", sum(a.qty for a in axes + motors), "",
                 f"<b>{n(total)}</b>", servos.CONTROL_LAYER, "", "", ""])
    return table(["축", "운동", "수량", "정격 kW", "합 kW", "구동", "피드백", "브레이크", "비고"],
                 rows, num_cols=(2, 3, 4))


def power_table() -> str:
    feeder = next(f for f in electrical.FEEDERS if f.panel == DRIVE_PANEL)
    power = [c for c in wiring.power_cables() if c.panel == DRIVE_PANEL]
    control = [c for c in wiring.control_segments() if DRIVE_PANEL in c.feeder]
    heat = next(h for h in thermal.heat_sources() if h.tag == "TH-CAB-JBR")
    rows = [
        ["피더", f"<code>{esc(feeder.tag)}</code> → <code>{esc(feeder.panel)}</code> · "
                f"{esc(feeder.served)}"],
        ["설치 / 수용", f"{n(feeder.installed_kw)} kW × {feeder.diversity} = "
                    f"{n(feeder.installed_kw * feeder.diversity)} kW"],
        ["차단기 · 케이블", f"{feeder.breaker_at} AT · {esc(feeder.cable)} "
                       f"(출처 {esc(feeder.source)})"],
        ["구동 합계", f"{n(servos.motion_kw_by_panel()[DRIVE_PANEL])} kW — 피더 설치값 안에 든다"],
        ["전력 케이블", " · ".join(f"{n(c.length_m)} m" for c in power) or "—"],
        ["제어 케이블", " · ".join(f"{esc(c.feeder)} {n(c.length_m)} m" for c in control) or "—"],
        ["반 위치", f"플랜트 X {n(wiring.lp_positions_mm()[DRIVE_PANEL])} mm (존 중심)"],
        ["반 발열", f"{esc(heat.tag)} {n(heat.loss_kw)} kW → {esc(heat.cooling)}"],
    ]
    return table(["항목", "값"], rows, "kv")


def utility_table() -> str:
    consumer = next(c for c in air.consumers() if c.cell == CELL)
    stream = next(s for s in dust.STREAMS if "JBR" in s.source)
    noise = next(s for s in acoustics.noise_sources() if s.tag == "NS-JBR")
    vib = next(s for s in acoustics.vibration_sources() if s.tag == "VS-JBR")
    rows = [
        ["압축공기", f"평균 {n(consumer.average_nl_min)} · 피크 {n(consumer.peak_nl_min)} NL/min "
                 f"@ {n(air.USE_BAR)} bar g — 계통 평균의 "
                 f"{consumer.average_nl_min / air.average_nl_min() * 100:.0f} %",
         _md(consumer.basis)],
        ["국소집진", f"<code>{esc(stream.tag)}</code> {n(stream.flow_m3h)} m³/h · "
                 f"가연성 {'예' if stream.combustible else '아니오'}",
         f"{_md(stream.material)} — {_md(stream.basis)}"],
        ["소음", f"Lw {n(noise.lw_dba)} dB(A) · 저감 {n(noise.reduction_db)} dB → 근접 1 m "
               f"{n(acoustics.near_field_dba(noise))} dBA (한도 {n(acoustics.NEAR_FIELD_LIMIT_DBA)})",
         f"{esc(noise.mitigation)} · {esc(noise.character)}"],
        ["진동", f"절연 {'함' if vib.isolated else '<b>안 함</b>'} · {esc(vib.isolator)}",
         _md(vib.note)],
    ]
    return table(["항목", "값", "근거"], rows)


def safety_table() -> str:
    rows = []
    for h in safety.hazards_for(CELL):
        pl = safety.required_pl(h.severity, h.frequency, h.avoidance)
        fns = safety.functions_for(h.tag)
        rows.append([h.tag, _md(h.description), f"S{h.severity} F{h.frequency} P{h.avoidance}",
                     f"PL {pl}", ", ".join(f.tag for f in fns) or "—", _md(h.basis)])
    return table(["위험원", "내용", "위험도", "요구 PL", "안전기능", "근거"], rows)


def stop_table() -> str:
    s = safety.summary()
    rows = [["정지사슬", f"{n(s['stopChainMs'])} ms (고정 {n(s['fixedChainMs'])} ms 포함)"],
            ["커튼 해상도 · 침투", f"{n(s['resolutionMm'])} mm · {n(s['penetrationMm'])} mm"],
            ["접근속도", f"고속 {n(s['approachFastMmS'])} · 저속 {n(s['approachSlowMmS'])} mm/s "
                     f"(전환 {n(s['approachSwitchMm'])} mm)"]]
    for op in safety.OPENINGS:
        distance = abs(op.hazard_x_mm - op.plane_x_mm)
        budget = safety.max_stop_time_ms(distance)
        rows.append([f"{op.tag} · {op.name}",
                     f"평면 X {n(op.plane_x_mm)} → 위험원 X {n(op.hazard_x_mm)} "
                     f"({n(distance)} mm) · 예산 {n(budget)} ms · "
                     f"{'여유 ' + n(budget - s['stopChainMs']) + ' ms' if budget >= s['stopChainMs'] else '초과'}"])
    rows.append(["뮤팅", f"하루 {n(safety.muting_cycles_per_day())} 회 · 연 "
                       f"{n(safety.cycles_per_year())} 회 (사명시간 {s['missionYears']} 년)"])
    return table(["항목", "값"], rows, "kv")


def by_prefix(parts: list[list[object]], prefix: str) -> list[list[object]]:
    return [r for r in parts if str(r[0]).startswith(prefix)]


def chain_table(parts: list[list[object]], prefix: str, head: str) -> str:
    """부품표에서 접두어로 사슬을 꺼낸다 — 품번 순서가 곧 공정 순서다."""
    rows = [[i, f"<code>{esc(r[0])}</code>", esc(r[2]), esc(r[3]), esc(r[7]), esc(r[9])]
            for i, r in enumerate(by_prefix(parts, prefix), 1)]
    if not rows:
        raise SystemExit(f"✗ 부품표에 {prefix}* 가 없다")
    return table(["#", "품번", head, "수량", "공차·판정", "역할"], rows, num_cols=(0,))


def discharge_is_absent(text: str) -> bool:
    """이 설계에 전기적 방전 회로가 있는가 — 도면 전체에서 그 낱말을 찾는다.

    `잔압`(공압 덤프)과 헷갈리면 안 된다. 여기서 묻는 것은 패널 자체를 단락·방전해
    전압을 없애는 회로이고, 그런 것은 이 도면에 없다 — 차광으로 발전을 억제하고
    2채널로 **재어서** 절단을 허가할 뿐이다.
    """
    return "방전" not in text and "discharge" not in text.lower()


def reliability_table() -> str:
    block = next(b for b in reliability.BLOCKS if b.tag == "RB-JBR")
    budget = reliability.downtime_budget_h()
    downtime = budget * block.share
    rows = [
        ["정지시간 예산 몫", f"{block.share:.2f} × {n(budget)} h = <b>{n(downtime)} h/년</b> "
                       f"(가동률 목표 {reliability.TARGET_AVAILABILITY:.2f} · 운전 "
                       f"{n(reliability.operating_hours())} h/년)"],
        ["MTTR", f"기준 {n(reliability.BASE_MTTR_H[block.tag])} h → "
                f"정비성 개선 후 {n(block.mttr_h)} h"],
        ["허용 고장 횟수", f"{downtime / block.mttr_h:,.1f} 회/년 → 요구 MTBF "
                     f"{reliability.operating_hours() / (downtime / block.mttr_h):,.0f} h"],
        ["이중화", f"{'있음' if block.redundant else '없음'} · 완충 {esc(block.buffer_side)}"],
        ["근거", _md(block.basis)],
    ]
    spares = [s for s in reliability.SPARES() if s.block == "RB-JBR"]
    body = table(["항목", "값"], rows, "kv")
    body += table(["예비품", "품목", "설치 수량", "연간 소요", "조달 (주)", "근거"],
                  [[s.tag, esc(s.name), s.qty_installed,
                    n(s.per_year) if s.per_year is not None else "<b>미확정</b>",
                    s.lead_weeks, _md(s.basis)] for s in spares],
                  num_cols=(2, 4))
    return body


def mounting_table() -> str:
    m = mounting.MOUNTING_OF[CELL]
    rows = [["앵커", " · ".join(f"{a.target} {a.count}×{a.bolt}" for a in m.anchors)],
            ["베이스 플레이트", f"{esc(m.plate)} · grout {m.grout_mm} mm · 레벨 {esc(m.level)}"],
            ["근거", _md(m.note)]]
    for p in access.POINTS:
        if p.station == CELL:
            rows.append([f"접근점 {p.tag}",
                         f"{esc(p.equipment)} · H {n(p.height_mm)} mm · {esc(p.task)} · "
                         f"연 {p.per_year} 회 — {_md(p.basis)}"])
    return table(["항목", "값"], rows, "kv")


def catalog_table(rows: list[list[object]]) -> str:
    groups: dict[str, list[list[object]]] = {}
    for r in rows:
        groups.setdefault(str(r[1]), []).append(r)
    out = []
    for group, items in groups.items():
        body = table(["품번", "품명", "수량", "치수 L×W×H (mm)", "재질", "가공", "공차", "기능"],
                     [[f"<code>{esc(r[0])}</code>", esc(r[2]), esc(r[3]),
                       " × ".join(n(v) for v in r[4]), esc(r[5]), esc(r[6]), esc(r[7]),
                       esc(r[9])] for r in items])
        out.append(f'<details class="grp"><summary>{esc(group)} '
                   f'<span class="cnt">{len(items)} 품번</span></summary>{body}</details>')
    return "".join(out)


def flow_table(ga: dict[str, object]) -> str:
    rows = [[step, esc(label),
             f"[{', '.join(n(v) for v in a)}]", f"[{', '.join(n(v) for v in b)}]"]
            for step, label, a, b in ga["flow"]]
    return table(["#", "동작", "시작 [X, 상하, 깊이] mm", "끝 [X, 상하, 깊이] mm"], rows)


def parts_3d_table(ga: dict[str, object]) -> str:
    rows = []
    for pid, label, size, at, explode in ga["parts"]:
        reach = sum(v * v for v in explode) ** 0.5
        rows.append([f"<code>{esc(pid)}</code>", esc(label),
                     " × ".join(n(v) for v in size),
                     f"[{', '.join(n(v) for v in at)}]",
                     f"[{', '.join(n(v) for v in explode)}]", f"{reach:,.0f}"])
    return table(["부품", "명칭", "치수 (mm)", "자리 (mm)", "분해 벡터 (mm)", "|Δ| (mm)"],
                 rows, num_cols=(5,))


def interface_table(text: str) -> str:
    return table(["항목", "내용"], [[esc(k), v] for k, v in interface_rows(text)], "kv")


def cut_gap_mm(text: str) -> tuple[float, float]:
    """POM 기준 슈가 정하는 절입 깊이 — 부품표 JB-HD-009 의 공차란이 출처다."""
    m = re.search(r'"JB-HD-009","[^"]*","스프링 POM 기준 슈","[^"]*",\[[^\]]*\],'
                  r'"[^"]*","[^"]*","([^"]*)"', text)
    if not m:
        raise SystemExit("✗ JB-HD-009 의 공차란을 못 읽었다")
    v = re.search(r"([\d.]+)\s*±\s*([\d.]+)", m.group(1))
    if not v:
        raise SystemExit(f"✗ 절입간격을 못 읽었다: {m.group(1)}")
    return float(v.group(1)), float(v.group(2))


def stage_span(text: str, needle: str) -> tuple[float, float]:
    """이름에 `needle` 이 든 스테이지의 로컬 구간."""
    hit = [(a, b) for name, a, b in stages(text) if needle in name]
    if len(hit) != 1:
        raise SystemExit(f"✗ 스테이지 «{needle}» 가 {len(hit)} 개 — 1 개여야 한다")
    return hit[0]


def output_table(text: str) -> str:
    """출력 조건과, **기구의 무엇이 그것을 보증하는가**.

    사양은 `handoff` 모델에서, 보증 수단은 이 도면의 값(절입 공차·스테이지 시각)에서
    온다. 둘을 맞대 보는 것이 이 표의 일이다 — 조건만 적어 두면 지켜지는지 알 수 없다.
    """
    cut, tol = cut_gap_mm(text)
    cable = stage_span(text, "순차 절단")
    shear = stage_span(text, "동시 박리")
    lift = stage_span(text, "동시 인양")
    back = handoff.LAMINATE_BACKSHEET_MM

    # 전단면이 백시트 기준면보다 아래다 — 그 평면을 지나는 것은 그 높이에서 잘린다.
    stub = -(cut - tol)                                   # 최악(얕은 절입)의 돌출
    deep = cut + tol                                      # 최악(깊은 절입)의 절결 깊이
    margin = handoff.BACKSHEET_NOTCH_MAX_MM - deep         # 허용치까지 남은 여유
    gap_word = "같다" if margin == 0 else f"{abs(margin):g} mm 차이다"
    guards = {
        "리본 단부 돌출": (
            f"L칼날이 POM 기준 슈로 백시트 기준면을 잡고 그보다 <b>{cut:g}±{tol:g} mm 아래</b>에서 "
            f"박스 발자국 전체를 쓴다. 그 평면을 지나는 것은 같은 높이에서 잘리므로 "
            f"얕은 쪽 공차({cut - tol:g} mm)에서도 절단면이 기준면 아래라 "
            f"<b>돌출이 남지 않는다</b>.",
            stub <= handoff.RIBBON_STUB_MAX_MM,
            "리본이 도면에 없다 — 계산은 서지만 검증할 대상이 없다"),
        "리본 단부 자세": (
            f"전단 <b>{n(shear[0])}–{n(shear[1])} s</b> 가 인양 "
            f"<b>{n(lift[0])}–{n(lift[1])} s</b> 보다 <b>먼저</b> 끝난다. 붙어 있는 채로 "
            "들어 올리는 순간이 없으므로 단부가 눕을 자리가 없다.",
            shear[1] <= lift[0], ""),
        "케이블 잔여": (
            f"콤이 도체를 홈에 물고 가위 A→B 가 <b>{n(cable[0])}–{n(cable[1])} s</b> 에 "
            "순차 절단한 뒤 하네스를 전량 케이블 배출슈트로 흘린다. 절단은 검출열 밖에서 "
            "이루어지고 남는 꼬리는 박스에 붙어 함께 나간다.",
            True, ""),
        "접착 실리콘 잔여": (
            f"접착층은 백시트 면 <b>위</b>에 있고 전단면은 그보다 {cut:g} mm 아래다. "
            "그래서 접착은 전량 박스와 함께 떨어진다 — 잔여 0 mm.",
            0.0 <= handoff.SILICONE_RESIDUE_MAX_MM, ""),
        "정션박스 자리 백시트 절결": (
            f"절결을 내는 것은 절입 그 자체다 — 깊이가 곧 <b>{cut:g}±{tol:g} mm</b>이고 "
            f"범위는 L칼날이 쓸고 가는 박스 발자국 안이다. 공차 상단 "
            f"<b>{deep:g} mm</b> 가 허용치 {handoff.BACKSHEET_NOTCH_MAX_MM:g} mm 와 "
            f"{gap_word}.",
            deep <= handoff.BACKSHEET_NOTCH_MAX_MM,
            "여유 0 — 깊은 쪽 공차를 넘기면 곧바로 불합격이다" if margin == 0 else ""),
    }
    rows = []
    for item, spec, why in handoff.jbox_trace_spec():
        how, ok, caveat = guards[item]
        mark = ('<b class="ok">보증</b>' if ok else '<b class="bad">미보증</b>')
        if caveat:
            mark += f'<span class="cav">{esc(caveat)}</span>'
        rows.append([esc(item), esc(spec), how, mark, esc(why)])
    body = table(["항목", "사양", "무엇이 보증하는가", "판정", "왜 상류 조건인가"], rows)

    pierce = cut - tol > back
    # 3.10·3.11 은 f-string 안에 줄바꿈 든 식을 못 읽는다 (PEP 701 은 3.12 부터).
    tight = ("공차 안에 들면 합격이지만 넘기면 곧바로 불합격이라, 이 치수는 공정능력으로 "
             "지켜야 하지 도면 공차로 지켜지지 않는다") if margin <= 0 else "여유가 있다"
    note = (
        f'<div class="note"><b>절결은 하류가 받아들였다 — 닫힌 항목.</b> '
        f'절입 {cut:g}±{tol:g} mm 가 백시트 {back:g} mm 보다 깊어'
        f'{" (얕은 쪽 공차에서도)" if pierce else ""} 칼날이 박스 발자국마다 백시트를 '
        f'관통한다는 것을 이 시트가 스스로 올렸고, 하류가 <b>절입을 줄이는 대신 절결을 '
        f'받는 쪽</b>으로 답했다 — 권취는 폭 1,400 중 국부 구멍이고, 절입을 백시트 두께 '
        f'안으로 올리는 쪽은 2,500 패널에서 그 공차를 지키기 어렵다. 그래서 '
        f'<b>기구는 그대로 둔다.</b> 대신 절결이 한도 붙은 허용 조건으로 위 표에 들어왔다 '
        f'(<code>{esc(handoff.BACKSHEET_NOTCH_SOURCE)}</code>).</div>'
        f'<div class="note warn"><b>남은 것 둘.</b> '
        f'① <b>리본이 도면에 없다.</b> JB 품번 어디에도 리본·플러시 절단 항목이 없고 3D 에도 '
        f'리본이 없다. 위 계산은 전단면이 백시트 기준면보다 아래라는 데서 나오지만, 잴 대상이 '
        f'도면에 없으므로 <b>검증되지 않았다</b> — 리본 관통 위치를 도면에 넣고 후검증'
        f'(JBR-VS-201A)에 돌출 높이 측정을 더해야 한다. '
        f'② <b>절결 여유가 {margin:g} mm 다.</b> 허용치 '
        f'{handoff.BACKSHEET_NOTCH_MAX_MM:g} mm 는 절입 공차의 깊은 쪽 {deep:g} mm 를 '
        f'{"딱 그만큼만 담는다" if margin == 0 else "담는다"} — '
        f'{tight}. 절입 깊이를 run-at-rate 의 관리 항목(Cpk)으로 올릴 것.</div>')
    return body + note


def open_items(text: str) -> str:
    """미결 항목 — 모델이 스스로 '미확정' 이라고 적은 것만 모은다."""
    items = [
        ("칼날 수명", "SP-01 SKD11 칼날 카세트의 연간 소요가 <b>없다</b>. 패널당 절단 길이는 "
                  "알지만 수명(장수)을 모른다 — 시운전 run-at-rate 에서 마모량을 재야 나온다.",
         "reliability.SPARES()"),
        ("뮤팅 센서 B10d", f"연 {n(safety.cycles_per_year())} 회 작동한다. B10d 가 있어야 T10d 가 "
                       f"나오고, 200만 밑이면 사명시간 {safety.MISSION_TIME_YEARS} 년 안에 "
                       "정기교체 대상이 된다 — 벤더 확정 항목.", "reliability.SPARES() SP-07"),
        ("서보 상세", "servos.py 의 축에는 스트로크·속도·가감속·관성비 필드가 없다. 정격은 "
                  "OEM 명판 확정 전의 계획값이며, 감속비는 AXIS-JBR-PZ 의 1:10 하나뿐이다.",
         "servos.py 모듈 주석"),
        ("헤드 추력", "헤드 1기 15 kN 은 <b>계산상</b> 상한이다. 45 kN 편심·잼 FEA 와 1헤드 "
                  "공정창이 출하 조건에 남아 있다.", "GA 시트 release"),
        ("부품 중량", "부품표에 중량 열이 없다. 셀 총중량 약 2.2 t 한 줄이 전부다.",
         "통합 설계도 상업화 사양표"),
        ("차광 조도", "차광 투입 터널의 허용 내부조도는 실물 위험성평가에서 확정한다.",
         "3D 차광 투입 터널 주석"),
        ("리본이 도면에 없다",
         f"하류가 리본 단부 돌출 ≤{handoff.RIBBON_STUB_MAX_MM:g} mm 와 눕힘 금지를 "
         "요구하는데 <b>리본이 이 도면 어디에도 없다</b> — JB 품번에도, 3D 에도. 전단면이 "
         "백시트 기준면보다 아래라 계산은 서지만 잴 대상이 없다. 리본 관통 위치·높이를 "
         "도면에 넣고 후검증에 돌출 측정을 더해야 조건이 검증된다.",
         f"{handoff.JBOX_TRACE_SOURCE} vs 부품표 JB-*"),
        ("절입 깊이 공정능력",
         f"절결 허용치 {handoff.BACKSHEET_NOTCH_MAX_MM:g} mm 가 절입 공차의 깊은 쪽 "
         f"{n(sum(cut_gap_mm(text)))} mm 와 <b>같다</b> — 여유 0. 도면 공차 안에 들면 "
         "합격이지만 넘기면 곧바로 하류 불합격이므로, 이 치수는 공차가 아니라 "
         "<b>공정능력</b>으로 지켜야 한다. 목표 Cpk 와 관리 방식이 run-at-rate 확정 항목이다. "
         "(절결 자체는 하류가 받아들여 닫혔다.)",
         f"JB-HD-009 공차란 vs {handoff.BACKSHEET_NOTCH_SOURCE}"),
        ("2D·3D 원점", f"GA 시트는 장비 중심을, 3D 장면은 존 중심을 부품 좌표 원점으로 쓴다. "
                    f"가드 여유가 상류 {n(layout.station_edges_mm(CELL)[0])} · 하류 "
                    f"{n(layout.station_edges_mm(CELL)[1])} 로 비대칭이라 둘이 "
                    f"<b>{n(origin_offset_mm())} mm</b> 어긋난다. 어느 쪽을 제작 기준으로 "
                    "삼을지는 발주처 확정 항목이다.", "layout.station_edges_mm('jbr')"),
        ("허용전압·방전", "JB-PV-002 의 허용전압과 CAT 등급이 위험성평가 확정 항목이다. "
                     "설계에 방전(단락) 회로가 없으므로, 재고도 남는 전압에서 절단을 "
                     "허가할지 아니면 방전 단계를 넣을지가 같은 자리에서 정해진다.",
         "JB-PV-002 공차란"),
    ]
    return table(["항목", "내용", "출처"],
                 [[esc(a), b, f"<code>{esc(c)}</code>"] for a, b, c in items])


# ── 문서 ────────────────────────────────────────────────────────────────
CSS = """
:root{color-scheme:light dark;
 --bg:#f2f4f3;--card:#fff;--card2:#f7f9f8;--line:#d3dad8;--line2:#b6c0bd;
 --ink:#16242a;--ink2:#4b5d63;--ink3:#6f8087;--brand:#1b7cb8;--brand-dim:#e2eef8;
 --accent:#fdca4a;--warn:#9a6b0e;--warn-bg:#fdf4de;--ok:#26714a;--red:#a52a30;
 --zone:#dfe9f4;--hw:#cfe0ef;--part:#9fbdd4;--accum:#f2e6c8;
 --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#131b1f;--card:#1c262b;--card2:#222d33;--line:#33454b;--line2:#465960;
 --ink:#e6eeef;--ink2:#a4b8bd;--ink3:#7a9098;--brand:#4aa8e0;--brand-dim:#10324a;
 --accent:#fdca4a;--warn:#e2a72c;--warn-bg:#3a2f12;--ok:#4fb27c;--red:#e2585f;
 --zone:#1d3448;--hw:#24445c;--part:#3d6584;--accum:#463b1c;}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#131b1f;--card:#1c262b;--card2:#222d33;--line:#33454b;--line2:#465960;
 --ink:#e6eeef;--ink2:#a4b8bd;--ink3:#7a9098;--brand:#4aa8e0;--brand-dim:#10324a;
 --accent:#fdca4a;--warn:#e2a72c;--warn-bg:#3a2f12;--ok:#4fb27c;--red:#e2585f;
 --zone:#1d3448;--hw:#24445c;--part:#3d6584;--accum:#463b1c;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif;}
.wrap{max-width:1260px;margin:0 auto;padding:24px 18px 72px}
header.top{border-bottom:2px solid var(--line2);padding-bottom:14px;margin-bottom:22px}
.eyebrow{font-size:12px;letter-spacing:.10em;color:var(--ink3);text-transform:uppercase}
h1{margin:.28em 0 .12em;font-size:26px;line-height:1.25;text-wrap:balance}
h2{margin:34px 0 10px;font-size:19px;border-left:4px solid var(--brand);padding-left:10px}
h3{margin:20px 0 8px;font-size:15px;color:var(--ink2)}
p{margin:.5em 0;max-width:78ch}
p.lead{color:var(--ink2)}
.note{background:var(--card2);border:1px solid var(--line);border-left:3px solid var(--brand);
 border-radius:8px;padding:10px 14px;margin:12px 0;color:var(--ink2);font-size:14px}
.note.warn{border-left-color:var(--warn);background:var(--warn-bg)}
code{font-family:var(--mono);font-size:.9em;background:var(--brand-dim);
 padding:1px 5px;border-radius:4px}
.tw{overflow-x:auto;margin:10px 0;border:1px solid var(--line);border-radius:9px;background:var(--card)}
table.t{border-collapse:collapse;width:100%;font-size:13.5px}
table.t th,table.t td{border-bottom:1px solid var(--line);padding:7px 10px;
 text-align:left;vertical-align:top}
table.t thead th{background:var(--card2);color:var(--ink2);font-weight:600;white-space:nowrap;
 position:sticky;top:0}
table.t tbody tr:last-child td{border-bottom:0}
table.t td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.kv th{width:180px;white-space:nowrap;color:var(--ink2)}
svg.sheet{display:block;width:100%;height:auto;background:var(--card);
 border:1px solid var(--line);border-radius:9px;margin:12px 0}
svg .zone{fill:var(--zone);stroke:var(--line2);stroke-width:1}
svg .hw{fill:var(--hw);stroke:var(--line2);stroke-width:1}
svg .accum{fill:var(--accum);stroke:var(--line2);stroke-width:1;fill-opacity:.75}
svg .part{fill:var(--part);stroke:var(--ink2);stroke-width:.7;fill-opacity:.86}
svg .centre{stroke:var(--brand);stroke-width:.9;stroke-dasharray:9 3 2 3}
svg .ground{stroke:var(--ink2);stroke-width:1.4}
svg .level{stroke:var(--brand);stroke-width:.8;stroke-dasharray:5 4;opacity:.75}
svg .level.on{stroke-width:1.5;stroke-dasharray:none}
svg .grid{stroke:var(--line);stroke-width:.7}
svg .dim{stroke:var(--ink3);stroke-width:.8}
svg text{fill:var(--ink);font:12px -apple-system,system-ui,sans-serif}
svg text.dimt{fill:var(--ink3);font-size:11px;font-variant-numeric:tabular-nums}
svg text.dimt.dim2{fill:var(--ink3);opacity:.72}
svg text.small{font-size:11.5px;fill:var(--ink2)}
b.ok{color:var(--ok)}
b.bad{color:var(--red)}
.cav{display:block;font-size:11.5px;color:var(--ink3);font-weight:400;margin-top:2px}
svg text.tiny{font-size:10.5px;fill:var(--ink2)}
svg text.axis{fill:var(--brand);font-family:var(--mono);font-size:9.5px}
svg text.axis.inbar{fill:var(--card);}
svg .bar{fill:var(--brand);fill-opacity:.82}
details.grp{border:1px solid var(--line);border-radius:9px;background:var(--card);margin:8px 0}
details.grp>summary{cursor:pointer;padding:9px 13px;font-weight:600;color:var(--ink2)}
details.grp[open]>summary{border-bottom:1px solid var(--line)}
details.grp .tw{margin:0;border:0;border-radius:0}
.cnt{font-weight:400;color:var(--ink3);font-size:12.5px;margin-left:6px}
footer{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);
 color:var(--ink3);font-size:12.5px}
@media (max-width:640px){.wrap{padding:16px 12px 56px}h1{font-size:21px}}
"""


def build() -> str:
    text = plant_text()
    rev = drawing_revision(text)
    ga = ga_sheet(text)
    rows = stages(text)
    axes = stage_axes(text)
    scen = box_scenarios(text)
    cap, heads, counts = head_force(text)
    parts = catalog(text)
    t0, t1 = window()
    discharge_absent = discharge_is_absent(text)
    box_labels = dict(select_options(text, BOX_SELECT_ID))
    validations = select_options(text, VALIDATION_SELECT_ID)
    w = block_times(text)

    body = f"""<div class="wrap">
<header class="top">
  <div class="eyebrow">DYNAMIC INDUSTRY · {esc(ga['sheet'])} · ENGINEERING BASE {esc(rev)}</div>
  <h1>JBR-201 정션박스·케이블 제거장치 상세도</h1>
  <p class="lead">투입공정(FL-101 → LFT-101A/B → BFC-101A/B → RB-101 → PT-101)이
  JB-201 로 넘긴 패널을 받아, 차광 아래에서 2극 전압을 확인하고 케이블을 순차 절단한 뒤
  검출된 개수만큼의 헤드가 정션박스를 동시에 박리·포획해 배출하고 후검증까지 마치는
  셀 하나. 플랜트 공정시계로 <b>{n(t0)} s 진입 → {n(t1)} s AFR-101 인계</b>,
  점유 <b>{n(campaign.JBR_S)} s</b>.</p>
</header>

<div class="note">이 시트의 숫자는 손으로 쓴 것이 하나도 없다.
<code>src/pv_preprocess/*.py</code> 의 설계 모델과 통합 설계도
<code>docs/drawings/pv-preprocess-plant.html</code> 의 리터럴에서 읽어
<code>tools/build_jbr_detail.py</code> 가 찍는다. 움직이는 것은
<a href="pv-jbr-scene.html">JBR-201 3D 파생본</a>에서 본다.</div>

<h2>1. 자리와 범위</h2>
{scope_table(ga)}
{plan_view(ga)}
<div class="note warn">이 시트의 부품 좌표 원점은 <b>장비 중심</b>이다 — GA 시트의 BASE 를
at[0]=0 에 두면 존 여유가 모델의 {n(layout.station_edges_mm(CELL)[0])} / {n(layout.station_edges_mm(CELL)[1])} mm 로
정확히 떨어진다. 가드 여유가 비대칭이라 장비 중심은 존 중심보다
<b>{n(origin_offset_mm())} mm 하류</b>이고, 3D 장면은 셀 그룹 원점을 존 중심에 두므로
같은 부품이 거기서는 그만큼 상류로 읽힌다. 두 값을 견줄 때 이 차이를 먼저 빼야 한다.</div>
<p class="lead">평면. 파란 띠가 jbr 존, 그 안의 진한 띠가 하드웨어 폭이다. 왼쪽 노란 띠는
JB-201 축적·인계 런으로, 셀 귀속은 jbr 이지만 자리는 상류 robot 존으로
{n(layout.pt_accumulator_overlap_mm())} mm 넘어와 PT-101 정반과 겹친다 — 두 물건이 이미 한
스테이션이라는 뜻이고, 겸용으로 더 줄일 수 있는 것은
{n(layout.infeed_merge_residue_mm())} mm 뿐이다.</p>

<h2>2. 입면과 레벨</h2>
{elevation_view(ga)}
{table(["레벨", "높이 (mm)"], [[esc(lbl), n(v)] for v, lbl in ga["levels"]]
       + [["이송면 (설계 확정)", n(ga["transfer"])], ["셀 외형 높이", n(ga["envelope"][2])]],
       num_cols=(1,))}
<div class="note">이송면 {n(layout.LINE_TRANSFER_MM)} mm 는 {esc(' · '.join(layout.SHARED_LINE))} 가
공유한다. GA 시트의 레벨선이 TRANSFER 900 으로 남아 있는 것은 통일 이전 표기이며,
설계 확정값은 <code>layout.LINE_TRANSFER_MM</code> = {n(layout.LINE_TRANSFER_MM)} mm 다.</div>

<h2>3. 45 초 공정시계</h2>
{gantt_view(rows, axes)}
{clock_table(rows, axes)}
<h3>라인 안에서의 위치</h3>
{occupancy_table()}
<div class="note">택트를 정하는 것은 <b>{esc(campaign.bottleneck())}</b>
({n(campaign.ideal_takt_s())} s)이고 JBR-201 은 두 번째다. 다음 장 투입은 JBR 이 끝나기를
기다리지 않는다 — 앞 장이 들어가 스토퍼가 물리는
{n(campaign.JBR_STOPPER_OFFSET_S)} s 뒤가 방출 주기
{n(campaign.release_takt_s())} s 의 근거이며, 축적구간
{n(campaign.ACCUMULATOR_MM)} mm 를 {n(campaign.JBR_STOPPER_OFFSET_S)} s 에 지나므로
이송속도는 {n(campaign.transfer_speed_mm_s())} mm/s 다.</div>

<h2>4. GA 시트의 7 동작</h2>
{flow_table(ga)}
<h3>3D 분해도 부품과 분해 벡터</h3>
{parts_3d_table(ga)}

<h2>5. 검출 시나리오와 헤드 배정</h2>
<p class="lead">헤드 {heads} 기는 같은 X 열에 있는 박스를 <b>동시에</b> 맡는다 — 헤드 index 가
박스 index 를 그대로 받는다. 검출 개수는 활성 헤드 수와 화면 문구와 힘 검산만 바꾸고,
스테이지 시각은 바꾸지 않는다.</p>
{box_table(scen, cap, heads, counts, box_labels)}
<div class="note">가용 추력 = 헤드 1기 {cap} kN × min(검출, 설치 {heads}). 헤드 수 제한이 없으면
박스가 헤드보다 많은 시나리오에서 용량을 과대평가한다. 인터록은 동일 X열 편차 ≤15 mm,
헤드간 간격 ≥260 mm, 각도 |θ|≤3° 를 요구하며, 위 네 시나리오의 최소 간격은 모두 그 위다.</div>

<h2>6. 차단·리젝트 시나리오</h2>
{validation_table(validations, w)}
<div class="note warn">선행 리젝트는 <b>칼날이 들어가기 전에</b> 막는다. 후검증 실패만 절단·박리·
포획·배출을 다 하고 나서 격리되며, 안전 뮤팅 불일치는 그 자리에서 래치해 외부 수동 리셋
전에는 자동복귀하지 않는다. 리젝트 버퍼는 최대 한 장을 물리적으로 격리하고 권한자의
트랩키 해제 후에만 인출한다 — 비지 않으면 게이트를 열지 않고 상류를 HOLD 한다.</div>

<h2>7. 인계 조건</h2>
{interface_table(text)}

<h3>JBR-201 출력 조건 — 하류 DG-HK60 투입 조건</h3>
<p class="lead">발주자가 DG-HK60 의 투입 상태를 「프레임·정션박스·케이블 제거 후
라미네이트」로 확정했다. 그 사양서가 적은 <b>정션박스 흔적 허용치</b>가 곧 이 셀의
출력 조건이고, 같은 값이 JB/AFR-301 통합 검증의 합격 조건에 들어간다.
값의 출처는 <code>{esc(handoff.JBOX_TRACE_SOURCE)}</code> 이고 수치는
<code>handoff.py</code> 에서 온다.</p>
{output_table(text)}

<h2>8. 구동과 전기</h2>
{drive_table()}
{power_table()}

<h2>9. 유틸리티</h2>
{utility_table()}

<h2>10. 안전</h2>
{safety_table()}
{stop_table()}
<h3>잔류·발전 전압 처리 사슬</h3>
<p class="lead">폐 패널은 빛을 받으면 발전한다. 이 셀은 그것을 <b>없애지 않고</b> 억제한 뒤
재서 허가한다 — 차광으로 발전을 낮추고, 외부 스트링 분리와 2극 고임피던스 전압과 프로브
자기진단·절연감시를 AND 로 묶어 통과할 때만 절단회로를 연다.</p>
{chain_table(parts, "JB-PV-", "장치")}
<div class="note warn">도면 전체에 <b>방전(단락) 회로가 없다</b>{'' if discharge_absent else ' — 아래 표와 어긋난다'}.
설계는 발전을 억제하고 재는 데까지이며, 재고도 남는 전압을 어떻게 다룰지는
JB-PV-002 의 허용전압·CAT 등급과 함께 실물 위험성평가에서 정한다.</div>
<h3>리젝트 경로</h3>
{chain_table(parts, "JB-RJ-", "장치")}

<h2>11. 신뢰도와 정비</h2>
{reliability_table()}
<h3>장착·접근</h3>
{mounting_table()}

<h2>12. 부품표 — JB-* {len(parts)} 품번</h2>
<p class="lead">통합 설계도 부품표에서 JB- 접두어 행을 그대로 옮긴다. 부품마다 2D 기준도와
3D 형상이 통합 설계도의 <b>부품 2D·3D</b> 프로그램에 있다.</p>
{catalog_table(parts)}

<h2>13. 미결 항목</h2>
{open_items(text)}

<footer>
  {esc(ga['sheet'])} · {esc(rev)} · 생성 <code>PYTHONPATH=src python tools/build_jbr_detail.py</code><br>
  값 출처 — 설계 모델 <code>src/pv_preprocess/</code> · 통합 설계도
  <code>docs/drawings/pv-preprocess-plant.html</code>
</footer>
</div>
"""
    return ("<!doctype html>\n"
            "<!-- JBR-201 상세도: tools/build_jbr_detail.py 가 설계 모델과 통합 설계도에서\n"
            "     찍는다. 손으로 고치지 않는다. -->\n"
            '<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            "<title>JBR-201 정션박스 제거장치 상세도</title>\n"
            '<meta name="description" content="폐 태양광 패널 전처리 라인의 JBR-201 '
            "정션박스·케이블 제거 셀 상세도 — 자리·45 초 공정시계·검출과 차단 시나리오·인계 "
            '조건·구동·유틸리티·안전·신뢰도·부품 112 품번.">\n'
            f"<style>{CSS}</style>\n</head>\n<body>\n{body}</body>\n</html>\n")


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
