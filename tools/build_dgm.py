# -*- coding: utf-8 -*-
"""후단 유리제거기 DG-HK60C 를 플랜트 도면에 찍는다 — 3D 셀 · 2D 시트 · 인계 패널.

REV.23~53 의 GRM-401 셀은 손으로 그린 3D 였고, 그 좌표는 옛 앱의 하드웨어 목록에서
사람이 옮겨 적은 계획값이었다. REV.54 의 DG-HK60C 는 자기 콘솔·사양서·부품 카탈로그
를 갖는 기계라, 그 값을 `pv_preprocess.hk60c` 가 읽고 여기서 도면에 **찍는다** —
스테이션 좌표·공정선·방책·모듈 외형·경계반 위치가 전부 그 기계의 값이다.

찍는 자리 (전부 표식 사이라 몇 번 돌려도 같다):

* `/* @dgm-3d-begin */ … /* @dgm-3d-end */` — 3D 셀 그룹 `pvGrm` (존 원점 · 브리지 ·
  다섯 스테이션 · 갠트리 · 권취·모노레일 · 카트 · 경계반 · 배기 헤더 · 방책 · 지지)
* `/* @dgm-sheet-begin */ … /* @dgm-sheet-end */` — 2D GA 시트 메타데이터 `grm: {…}`
* `/* @dgm-handoff-begin */ … /* @dgm-handoff-end */` — `pvHandoff` 리터럴과 렌더러
* `<!-- @dgm-ho-begin -->` … `<!-- @dgm-ho-end -->` — 인계 패널 HTML
* 도면 목록의 GA 행 · 인터록 표의 두 행 · 명판·엣지 캐비닛 이름표

실행 (저장소 루트에서):
    PYTHONPATH=src python tools/build_dgm.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign, casing, handoff, hk60c, layout, line, mounting  # noqa: E402

LINE = line.LINE_MAX_MM   # 라인 패널 상한 — 기계 안에서 움직이는 유리는 이 크기다

DRAWING = pathlib.Path(__file__).resolve().parent.parent / "docs/drawings/pv-preprocess-plant.html"
CAPTURE = pathlib.Path(__file__).resolve().parent.parent / "docs/drawings/hk60c-capture.json"
X0, Z0 = 24_750.0, 3_550.0          # 씬 월드 원점 (플랜트 좌표 mm) — build_casing 과 같다


def wx(mm: float) -> float:
    return round((mm - X0) / 1000.0, 4)


def wz(mm: float) -> float:
    return round((mm - Z0) / 1000.0, 4)


def n(v: float) -> str:
    """JS 숫자 리터럴 — 0.5 → .5, 1.0 → 1."""
    t = f"{round(v, 4):.4f}".rstrip("0").rstrip(".") or "0"
    if t.startswith("0."):
        t = t[1:]
    elif t.startswith("-0."):
        t = "-" + t[2:]
    return t


def s(v: str) -> str:
    return "'" + v.replace("'", "’") + "'"


H = hk60c
ST = H.STATION
#: 플랜트 안의 유리 픽업 스테이션 중심 (기계 x mm) — 팔레트 1,300 이 방책선 안에 들게.
GLASS_PICKUP_IN_MM = hk60c.FENCE_X1_MM - 700
ZONE = next(z for z in layout.build_zones() if z.key == "grm")
Y0 = ZONE.y0_mm
LEN = H.LENGTH_MM / 1000.0
EL = H.LINE_EL_MM / 1000.0


def m(mm: float) -> float:
    return mm / 1000.0


# 기계 y (mm) → 그룹 로컬 z (m). 그룹 원점 z = 기계 y 0 이고 플랜트 Y 는 −y 방향으로 큰다.
def lz(y_mm: float) -> float:
    return -m(y_mm)



# ── 벤더 원본 형상 ────────────────────────────────────────────────────────
#: 방책 밖으로 나가는 것은 인도 범위가 아니다. 상류 x<0 는 발주자 픽업 스테이션
#: 자리(플랜트에서는 BX-101 브리지가 대신하고), −y 방책 밖은 롤·카세트 레인인데
#: 플랜트는 그것을 자기 통로 밖 레인에 따로 놓는다 (RFQ OI-17).
def _delivered(part: dict) -> bool:
    """캡처 한 덩어리가 **인도 범위(방책 안)** 인가 — 중심으로 가른다."""
    if part["t"] == "p":
        c = [sum(v[k] for v in part["v"]) / len(part["v"]) for k in range(3)]
    else:
        c = part["c"]
    return (0.0 <= c[0] <= H.FENCE_X1_MM / 1000.0
            and -H.FENCE_YN_MM / 1000.0 <= c[1] <= H.FENCE_YP_MM / 1000.0)


#: 인도 경계에서 자른다. 상류 −900 은 벤더 방책의 팔레트 픽업 자리인데 플랜트는
#: 그 자리에 버퍼 끝단 케이싱과 브리지 개구를 두므로 그 900 을 세우지 않는다.
#: 하류로 넘어가는 배기 헤더는 경계 플랜지 뒤가 발주자 몫이라 존 끝에서 끊는다.
#: 자르는 것은 **길이뿐**이다 — 자리도 치수도 도장도 벤더가 그린 그대로다.
#: 상류 물림 — 버퍼 끝단 케이싱의 끝판이 존 경계를 **넘어와** 선다. 판 중심이
#: `casing.END_OFFSET_MM`(69) 이고 조립 두께가 24 라 하류면이 81 이다. 기계는 그
#: 뒤에 설치 여유를 두고 서므로, 벤더 방책 레일의 상류 끝 106 mm 는 세우지 않는다
#: (그 자리가 브리지 개구이기도 하다). 이것을 안 두면 케이싱 검사가 접촉을 잡는다.
UPSTREAM_SETBACK_MM = casing.END_OFFSET_MM + casing.PANEL_ASSY_MM // 2 + 25


def _clip_x(part: dict) -> dict | None:
    lo, hi = UPSTREAM_SETBACK_MM / 1000.0, H.FENCE_X1_MM / 1000.0
    q = dict(part)
    if part["t"] == "b":
        if any(part.get("r") or (0, 0, 0)):
            return q                       # 회전한 상자는 자르지 않는다 (경계에 없다)
        a, b = part["c"][0] - part["s"][0] / 2, part["c"][0] + part["s"][0] / 2
        na, nb = max(a, lo), min(b, hi)
        if nb - na <= 1e-4:
            return None
        if (na, nb) != (a, b):
            q["c"] = [round((na + nb) / 2, 4), part["c"][1], part["c"][2]]
            q["s"] = [round(nb - na, 4), part["s"][1], part["s"][2]]
    elif part["t"] == "c" and part["x"] == "x":
        a, b = part["c"][0] - part["l"] / 2, part["c"][0] + part["l"] / 2
        na, nb = max(a, lo), min(b, hi)
        if nb - na <= 1e-4:
            return None
        if (na, nb) != (a, b):
            q["c"] = [round((na + nb) / 2, 4), part["c"][1], part["c"][2]]
            q["l"] = round(nb - na, 4)
    elif part["t"] == "p":
        q["v"] = [[min(max(v[0], lo), hi), v[1], v[2]] for v in part["v"]]
    return q


def _finish(hex_color: str, alpha: float, table: dict) -> tuple[float, float]:
    """벤더의 표면 마감(sp 반사강도 · gl 하이라이트 폭)을 거칠기·금속도로 옮긴다.

    콘솔은 자기 소프트웨어 렌더러용으로 sp/gl 을 갖고 three.js 는 roughness/
    metalness 를 갖는다. 같은 도장을 두 렌더러가 같게 보이도록 하는 환산이고,
    **색은 환산하지 않는다** — 색이 도장의 정본이다.
    """
    f = table.get(hex_color) or {"sp": 0.18, "gl": 17}
    rough = min(0.92, max(0.08, 0.95 - float(f["gl"]) / 110.0))
    metal = min(0.80, max(0.02, float(f["sp"]) * 0.9))
    if alpha < 1.0:                       # 유리·투명 가드는 금속이 아니다
        rough, metal = 0.08, 0.05
    return round(rough, 3), round(metal, 3)


#: 플랜트가 **이름으로 부르는** 부재 — 앵커 계획(`mounting.MEMBERS`)·정비 동선·
#: 부품 검색이 이 이름으로 기계를 가리킨다. 형상은 벤더 원본이므로, 그 이름을
#: 가장 가까운 벤더 덩어리에 얹는다. 자리는 전부 모델에서 낸다(리터럴이 아니다).
def _plant_tags() -> list[tuple[float, float, float, str, str]]:
    ld, hc, dl, gc, ul = ST["LD"], ST["HC"], ST["DL"], ST["GC"], ST["UL"]
    tbl_cx = m(dl.x0_mm) + .87 + H.const("CARRIER_L") / 2
    rx0, rz, gy = H.const("CRAIL_X0"), H.const("CRAIL_Z"), H.const("CGY")
    cex = [m(v) for v in H.CE_X_MM]
    cey = (m(H.const("CE_Y0") * 1000), m(H.const("CE_Y1") * 1000))
    fk = H.MODULES["M-003"][1]
    bjx, bjy = m(H.BJ_X_MM), m(H.BJ_Y_MM)
    px = m(GLASS_PICKUP_IN_MM)
    return [
        (m(ld.cx_mm), 0, EL - .07, "LD-101 투입 셔틀 롤러베드",
         f"브리지가 유리 한 장을 내려놓는 자리 — 공정선 EL {H.LINE_EL_MM:,}"),
        (m(ld.cx_mm) - .22, 0, EL - .39, "WI-101 투입 계량 컨베이어",
         "로드셀 4점 합산 ±0.2 % F.S. — 물질수지의 입력값"),
        (m(hc.cx_mm), 0, .3, "DG-HK60C HC-101 가열실 골조 (벤더 앵커군 A1)",
         f"{H.DECKS}단 밀폐 IR — 벤더 D-602 기초에 앵커군 A1"),
        (m(ld.x1_mm) - .42, -m(fk[1]) / 2, m(fk[2]) / 2, "LI-101 승강 포크 문형",
         "층 사이를 오르내리며 캐리어를 데크에 넣는다"),
        (m(dl.x0_mm) + .42, -m(fk[1]) / 2, m(fk[2]) / 2, "EX-101 승강 포크 문형",
         "소킹이 끝난 단에서 캐리어를 뽑아 탠덤으로 보낸다"),
        (tbl_cx, 0, .55, "DG-HK60C VT-101 진공테이블 기둥 6본 (벤더 앵커군 A8)",
         "상판 710 kg — 최중량 단품. 기둥 6본이 바닥으로 내린다"),
        (rx0, -gy, 1.0, "DG-HK60C KG-101 갠트리 주행 문형 4본 (벤더 앵커군 A7)",
         f"주행레일 EL {round(rz * 1000):,} — 55 mm/s 박리 · 700 mm/s 복귀"),
        (m(H.WINDER_X_MM), 0, 3.7, "WR-101 백시트 만권 롤",
         f"Ø600 × 1,460 · {H.ROLL_MASS_KG} kg — RH-201 모노레일로 방책 밖 새들에 내린다"),
        ((cex[0] + cex[1]) / 2, (cey[0] + cey[1]) / 2, m(H.CE_EL_MM),
         "CE-201 셀/EVA 횡인출 컨베이어", "적층체를 자르지 않고 통째로 옆으로 뺀다"),
        (m(H.CART_X_MM), m(H.CART_Y_MM), .275, "CS-201 셀/EVA 평적 카트",
         f"{H.CART_L_MM:,} × {H.CART_W_MM:,} · 통로쪽 레인에서 AGV 가 받는다"),
        (m(gc.cx_mm), 0, .3, "DG-HK60C GC-101 냉각 랙 골조 (벤더 앵커군 A2)",
         f"{H.DECKS}단 강제공랭 140 → 60 ℃ — 배기는 경계 덕트에 합류"),
        (m(ul.cx_mm), 0, EL - .07, "UL-101 반출 셔틀 · WO-303 인라인 계량",
         "60 ℃ 이하로 식은 판유리를 계량하며 내보낸다"),
        (m(ul.x0_mm) + .36, -1.1, 1.45, "QI-301 검사 아치",
         "상부 RGB 카메라 — GLASS_CRACK · QI_FAIL 판정"),
        (bjx, bjy - .38, 1.0, "BJ-101 경계 인터페이스반",
         "VOC_ABATE_READY · GLASS/CELL_TAKEAWAY_READY · 상류 브리지 핸드셰이크 UP_*"),
        (bjx, bjy + .38, 1.0, "BJ-102 경계 인터페이스반 (안전)",
         "IF_ESTOP_LOOP_OK · 광커튼 뮤팅 — 안전회로는 별도 반이다"),
        (bjx, bjy, .07, "DG-HK60C 기초 패드 P1~P3",
         "P1 MCC(EP-1) · P2 진공 스키드(EP-3) · P3 경계 인터페이스"),
        (4.2, -3.2, 1.69, "DG-HK60C 전력·MCC·제어반 M-011",
         f"IR-DB1 {H.LAMPS * H.LAMP_KW:g} kW · HK-DB2 · MCC-1 — 벤더 반이 기초 패드 P1 에 선다"),
        (12.28, -3.2, 1.39, "DG-HK60C VU-101 진공·계장공기 스키드 M-012",
         "진공 펌프·계장공기 — 기초 패드 P2 (EP-3)"),
        (px + .36, -.95, .975, "LC-002 안전 광커튼 (하류 개구)",
         "광축면 Y ±950 × Z 1,950 — 유리 반출 개구를 지킨다"),
    ]


def build_vendor() -> str:
    """벤더 콘솔에서 받아 적은 부품을 **색 버킷별 병합 지오메트리**로 찍는다.

    부품이 1,500 개가 넘어 한 덩어리에 한 메시씩 만들면 드로우콜이 그만큼 는다.
    색이 같은 것끼리 삼각형을 합치면 24 개 남짓이고, 형상은 하나도 잃지 않는다.
    이름이 붙은 덩어리(벤더가 `label3` 로 부른 자리에서 가장 가까운 것)만 따로
    메시로 세워 집기·검색이 되게 한다.
    """
    cap = json.loads(CAPTURE.read_text(encoding="utf-8"))
    base = [r for r in (_clip_x(q) for q in cap["base"] if _delivered(q)) if r is not None]
    pose = [r for r in (_clip_x(q) for q in cap["dynamic"] if _delivered(q)) if r is not None]
    parts = base + pose
    #: 정지 자세(4단계)에서 **움직이는 것들** — 캐리지·나이프·박리 중 유리·셀/EVA 적층체.
    #: 이것만은 합치지 않고 낱개 메시로 세운다. 영상이 이 자세에서 공정을 이어 돌리려면
    #: 조각을 하나씩 잡아 옮겨야 하고, 합쳐 버리면 그 순간 잡을 것이 없어진다.
    moving = {i for i in range(len(base), len(parts)) if parts[i]["t"] in ("b", "c")}
    labels = [l for l in cap["labels"]
              if 0.0 <= l["p"][0] <= H.FENCE_X1_MM / 1000.0
              and -H.FENCE_YN_MM / 1000.0 <= l["p"][1] <= H.FENCE_YP_MM / 1000.0]
    table = cap["finish"]

    # 이름 붙은 자리마다 가장 가까운 상자·원통을 하나 골라 낱개 메시로 뺀다.
    # 플랜트가 부르는 이름이 먼저다 — 앵커 계획·정비 동선·부품 검색이 그 이름을 쓴다.
    named: dict[int, str] = {}
    note: dict[int, str] = {}
    solid = [i for i, q in enumerate(parts) if q["t"] in ("b", "c")]

    def _attach(x: float, y: float, z: float, tag: str, tip: str, reach: float) -> None:
        best, bd = None, reach ** 2
        for i in solid:
            if i in named:
                continue
            c = parts[i]["c"]
            d = (c[0] - x) ** 2 + (c[1] - y) ** 2 + (c[2] - z) ** 2
            if d < bd:
                best, bd = i, d
        if best is not None:
            named[best] = tag
            if tip:
                note[best] = tip

    # 탠덤 칼날 두 대는 자리가 아니라 **형상**으로 찾는다 — 정지 자세가 행정 중간이라
    # 캐리지 위치가 단계마다 다르다. 패널 폭을 건너지르는 같은 단면의 바 두 개이고,
    # 그 사이가 칼끝 리드(300)다. 그 사실을 여기서 확인하고 이름을 붙인다.
    lead_m = H.KNIFE_PITCH_MM / 1000.0
    cand = sorted((i for i, q in enumerate(parts)
                   if q["t"] == "b" and .20 <= q["s"][0] <= .30
                   and m(H.PANEL_MAX_MM[1]) < q["s"][1] <= m(H.PANEL_MAX_MM[1]) + .4
                   and .20 <= q["s"][2] <= .35), key=lambda i: parts[i]["c"][0])
    bars = next(([a, b] for a in cand for b in cand
                 if abs((parts[b]["c"][0] - parts[a]["c"][0]) - lead_m) < .02), [])
    if len(bars) >= 2:
        lead = round((parts[bars[1]]["c"][0] - parts[bars[0]]["c"][0]) * 1000)
        named[bars[0]] = "HKB-101 백시트 개방 핫나이프 (카세트)"
        note[bars[0]] = f"백시트/EVA 계면을 {lead} 선행해 연다 — 180 ℃ (벤더 원본 형상)"
        named[bars[1]] = "HKS-201 셀/EVA 분리 핫나이프 (카세트)"
        note[bars[1]] = f"{lead} 뒤를 따라가며 셀/EVA 를 유리에서 뗀다 — 200 ℃ (벤더 원본 형상)"
    for tx, ty, tz, tag, tip in _plant_tags():
        _attach(tx, ty, tz, tag, tip, 2.5)
    for lab in labels:
        _attach(lab["p"][0], lab["p"][1], lab["p"][2], lab["t"], "", 2.0)

    colors: list[str] = []
    for q in parts:
        key = (q["k"], q["a"])
        if key not in colors:
            colors.append(key)
    ci = {k: i for i, k in enumerate(colors)}

    box, boxr, cyl, poly = [], [], [], []
    for i, q in enumerate(parts):
        if i in named or i in moving:
            continue
        k = ci[(q["k"], q["a"])]
        if q["t"] == "b":
            r = q.get("r") or [0, 0, 0]
            row = [k] + [round(v, 4) for v in q["c"] + q["s"]]
            (boxr if any(r) else box).append(row + ([round(v, 5) for v in r] if any(r) else []))
        elif q["t"] == "c":
            cyl.append([k] + [round(v, 4) for v in q["c"]]
                       + [round(q["r"], 4), round(q["l"], 4), "xyz".index(q["x"]), int(q["g"])])
        else:
            poly.append([k, len(q["v"])] + [round(v, 4) for pt in q["v"] for v in pt])

    def arr(rows: list[list]) -> str:
        return "[" + ",".join(",".join(n(v) if isinstance(v, float) else str(v) for v in row)
                              for row in rows) + "]"

    o: list[str] = []
    w = o.append
    w("// ── 벤더 원본 형상 — tools/capture_hk60c.mjs 가 벤더 콘솔에서 받아 적은 그리기")
    w("//    호출 그대로다(압축 배치 · 4단계 정지 자세). 좌표·치수·도장색을 여기서 고치지")
    w(f"//    않는다. 인도 범위(방책 x 0…{H.FENCE_X1_MM:,} · y {-H.FENCE_YN_MM:,}…{H.FENCE_YP_MM:,}) 안 {len(parts):,}덩어리,")
    w(f"//    그중 이름 붙은 {len(named)}개와 움직이는 {len(moving)}개는 낱개 메시로 세운다.")
    w("var VC=[" + ",".join(s(c) for c, _ in colors) + "];")
    w("var VF=[" + ",".join("[%s,%s,%s]" % (n(_finish(c, a, table)[0]), n(_finish(c, a, table)[1]), n(a))
                            for c, a in colors) + "];")
    w("var VM=VC.map(function(c,i){var t=M.frame.clone();t.color.set(c);"
      "t.roughness=VF[i][0];t.metalness=VF[i][1];"
      "if(VF[i][2]<1){t.transparent=!0;t.opacity=VF[i][2];t.depthWrite=VF[i][2]>.6}return t});")
    w("var VB=" + arr(box) + ",VBR=" + arr(boxr) + ",VY=" + arr(cyl) + ",VP=" + arr(poly) + ";")
    w("(function(){")
    w("var BG=Object.getPrototypeOf(Wn.prototype).constructor,BA=new Wn(1,1,1).attributes.position.constructor;")
    w("var A=VC.map(function(){return{p:[],n:[]}});")
    # 기계 (x,y,z) → 셀 로컬 (x, z, −y). 행렬식 +1 이라 감김·법선이 그대로 산다.
    w("function tri(a,P,Q,R){var ux=Q[0]-P[0],uy=Q[1]-P[1],uz=Q[2]-P[2],vx=R[0]-P[0],vy=R[1]-P[1],vz=R[2]-P[2];")
    w("var nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx,L=Math.hypot(nx,ny,nz)||1;nx/=L;ny/=L;nz/=L;")
    w("[P,Q,R].forEach(function(t){a.p.push(t[0],t[2],-t[1]);a.n.push(nx,nz,-ny)})}")
    w("function quad(a,P,Q,R,S){tri(a,P,Q,R);tri(a,P,R,S)}")
    w("function rot(p,rx,ry,rz){var x=p[0],y=p[1],z=p[2],c,s,t;")
    w("c=Math.cos(rx);s=Math.sin(rx);t=y*c-z*s;z=y*s+z*c;y=t;")
    w("c=Math.cos(ry);s=Math.sin(ry);t=x*c+z*s;z=-x*s+z*c;x=t;")
    w("c=Math.cos(rz);s=Math.sin(rz);t=x*c-y*s;y=x*s+y*c;x=t;return[x,y,z]}")
    w("function boxTri(a,c,sz,r){var hx=sz[0]/2,hy=sz[1]/2,hz=sz[2]/2,")
    w("V=[[-hx,-hy,-hz],[hx,-hy,-hz],[hx,hy,-hz],[-hx,hy,-hz],[-hx,-hy,hz],[hx,-hy,hz],[hx,hy,hz],[-hx,hy,hz]];")
    w("if(r)V=V.map(function(v){return rot(v,r[0],r[1],r[2])});")
    w("V=V.map(function(v){return[c[0]+v[0],c[1]+v[1],c[2]+v[2]]});")
    w("[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]].forEach(function(f){quad(a,V[f[0]],V[f[1]],V[f[2]],V[f[3]])})}")
    w("function cylTri(a,c,r,l,ax,g){var A0=[0,0,0],U=[0,0,0],W=[0,0,0];")
    w("if(ax===0){A0=[1,0,0];U=[0,1,0];W=[0,0,1]}else if(ax===1){A0=[0,1,0];U=[1,0,0];W=[0,0,1]}else{A0=[0,0,1];U=[1,0,0];W=[0,1,0]}")
    w("var r0=[],r1=[],i,j;for(i=0;i<g;i++){var t=i*2*Math.PI/g,cs=Math.cos(t)*r,sn=Math.sin(t)*r,")
    w("q=[U[0]*cs+W[0]*sn,U[1]*cs+W[1]*sn,U[2]*cs+W[2]*sn];")
    w("r0.push([c[0]-A0[0]*l/2+q[0],c[1]-A0[1]*l/2+q[1],c[2]-A0[2]*l/2+q[2]]);")
    w("r1.push([c[0]+A0[0]*l/2+q[0],c[1]+A0[1]*l/2+q[1],c[2]+A0[2]*l/2+q[2]])}")
    w("for(i=0;i<g;i++){j=(i+1)%g;quad(a,r0[i],r0[j],r1[j],r1[i])}")
    w("for(i=1;i<g-1;i++){tri(a,r0[0],r0[i+1],r0[i]);tri(a,r1[0],r1[i],r1[i+1])}}")
    w("for(var i=0;i<VB.length;i+=7)boxTri(A[VB[i]],[VB[i+1],VB[i+2],VB[i+3]],[VB[i+4],VB[i+5],VB[i+6]],null);")
    w("for(var i=0;i<VBR.length;i+=10)boxTri(A[VBR[i]],[VBR[i+1],VBR[i+2],VBR[i+3]],[VBR[i+4],VBR[i+5],VBR[i+6]],[VBR[i+7],VBR[i+8],VBR[i+9]]);")
    w("for(var i=0;i<VY.length;i+=8)cylTri(A[VY[i]],[VY[i+1],VY[i+2],VY[i+3]],VY[i+4],VY[i+5],VY[i+6],VY[i+7]);")
    w("for(var i=0;i<VP.length;){var k=VP[i],m=VP[i+1],v=[],b=i+2;for(var q=0;q<m;q++)v.push([VP[b+q*3],VP[b+q*3+1],VP[b+q*3+2]]);")
    w("for(var q=1;q<m-1;q++)tri(A[k],v[0],v[q],v[q+1]);i=b+m*3}")
    w("A.forEach(function(a,i){if(!a.p.length)return;var gm=new BG();")
    w("gm.setAttribute('position',new BA(new Float32Array(a.p),3));")
    w("gm.setAttribute('normal',new BA(new Float32Array(a.n),3));")
    w("gm.computeBoundingBox();gm.computeBoundingSphere();")
    w("var me=new et(gm,VM[i]);me.castShadow=!0;me.receiveShadow=!0;")
    w("me.userData.label='DG-HK60C 유리제거기 (벤더 도면 원본)';")
    # 도장색을 남긴다 — 절개 뷰가 외장만 골라 숨길 수 있어야 안이 보인다
    w("me.userData.livery=VC[i];")
    w("me.userData.note='벤더 콘솔 pv-delamination-3d.html 의 그리기 호출을 그대로 옮긴 형상·도장이다. 이름 붙은 부품은 따로 집힌다.';")
    w("Ns.push(me);g.add(me)})})();")
    # 이름 붙은 덩어리와 **움직이는 조각** — 낱개 메시
    #: 움직이는 조각에 **역할 이름**을 붙인다 — 도장색과 자리가 역할을 말한다.
    #: 영상이 이 이름으로 조각을 잡아 공정을 이어 돌린다(유리는 냉각·반출로, 셀/EVA 는
    #: 옆으로, 백시트는 권취로). 이름이 없으면 합쳐진 덩어리와 구분할 길이 없다.
    pal = {v: k for k, v in cap["palette"].items()}
    knife_x = [parts[i]["c"][0] for i in bars] if len(bars) >= 2 else []

    def _role(q: dict) -> str | None:
        role = pal.get(q["k"])
        if role == "glass":
            return "DG-HK60C 박리 중 유리"
        if role == "sheet":
            return "DG-HK60C 벗겨지는 백시트"
        if role in ("cell", "cell2"):
            y = q["c"][1]
            if y < -3.0:
                return "DG-HK60C 셀/EVA 카트 적재"
            if y < -1.5:
                return "DG-HK60C 셀/EVA 반출 적층체"
            return "DG-HK60C 유리 위 셀/EVA 층"
        if knife_x and q["t"] == "b" and q["c"][2] > m(H.LINE_EL_MM) \
                and min(abs(q["c"][0] - x) for x in knife_x) < .6:
            return "DG-HK60C 나이프 캐리지"
        return None

    solo = dict(named)
    for i in sorted(moving):
        solo.setdefault(i, _role(parts[i]) or "DG-HK60C 4단계 정지 자세")
    for i, tag in sorted(solo.items(), key=lambda kv: kv[0]):
        q = parts[i]
        k = ci[(q["k"], q["a"])]
        tip = s(note[i]) if i in note else s(
            "탠덤 박리 중 — 영상이 이 조각을 이어 돌린다" if i in moving
            else "벤더 원본 · 도장 " + q["k"])
        if q["t"] == "b":
            r = q.get("r") or [0, 0, 0]
            rot = (f",[{n(r[0])},{n(r[2])},{n(-r[1])}]" if any(r) else "")
            w(f"L([{n(q['s'][0])},{n(q['s'][2])},{n(q['s'][1])}],"
              f"[{n(q['c'][0])},{n(q['c'][2])},{n(-q['c'][1])}],VM[{k}],{s(tag)},{tip}{rot});")
        else:
            ax = {"x": "[0,0,Math.PI/2]", "y": "[Math.PI/2,0,0]", "z": "null"}[q["x"]]
            w(f"Ee(g,{n(q['r'])},{n(q['l'])},"
              f"[{n(q['c'][0])},{n(q['c'][2])},{n(-q['c'][1])}],VM[{k}],{s(tag)},{tip},{ax});")
    return "\n".join(o)


# ── 3D ────────────────────────────────────────────────────────────────────
def build_3d() -> str:
    o: list[str] = []
    w = o.append
    zx0 = wx(ZONE.x0_mm)
    gz = wz(Y0 + H.FENCE_YP_MM)                 # 기계 y 0 의 월드 z
    lift = m(layout.bridge_lift_mm())
    pick = -m(layout.zone_overlap_mm("grm"))    # 브리지가 유리를 집는 자리 (기계 x −475)
    place = m(H.INFEED_CX_MM)                   # 놓는 자리 — LD-101 데크 중심
    rh_z = m(H.monorail_el_mm())
    roll_y = -(layout.roll_saddle_plant_y_mm() - Y0 - H.FENCE_YP_MM)      # 기계 y (mm)
    cass_y = H.CASSETTE_SADDLE_Y_MM
    duct_el = m(H.DUCT_FLANGE_EL_MM)
    mods = H.MODULES

    w("/* @dgm-3d-begin */")
    w("/* REV.54 DG-HK60C 유리제거기 — tools/build_dgm.py 가 hk60c 에서 찍는다. 손으로 쓰지 않는다.")
    w(f"   존 X {ZONE.x0_mm:,}…{ZONE.x1_mm:,} → 월드 x {zx0:g}…{wx(ZONE.x1_mm):g}, 기계 y 0 → 월드 z {gz:g}.")
    w("   기계 좌표(x 공정방향 · y 좌측+ · z 상향)를 그룹 로컬 (x, 높이, −y) 로 놓는다 —")
    w("   −y 면(카트 레인·경계반·모노레일 반출)이 통로(+z) 쪽이다. */")
    # 셀 원점은 존 식에서 낸다 — 리터럴로 되돌리면 존이 움직일 때 격자가 갈라진다 (REV.48 규칙)
    w(f"var pvGrm=new ce;pt.add(pvCell(pvGrm,'grm'));pvGrm.position.set(pvZone.grm[0],0,{n(gz)});")
    w("(function(){")
    w("var g=pvGrm,L=function(a,b,c,d,e,f){return P(g,a,b,c,d,e,f)};")
    w("var MP=function(w,d,y0,y1,x,z,label){L([w,y1-y0,d],[x,(y0+y1)/2,z],M.frame,label);L([w+.14,.03,d+.14],[x,y0+.015,z],M.steel,null)};")
    w("var AB=function(x,z,k,dx){for(var i=0;i<k;i++)L([.05,.05,.05],[x+(i-(k-1)/2)*dx,.045,z],M.dark,null)};")
    # ── 벤더 원본 기계 — 방책·외장·다섯 스테이션·갠트리·권취·경계반·배기까지
    #    벤더 콘솔에서 받아 적은 그대로 찍는다 (손으로 다시 그리지 않는다).
    w(build_vendor())
    # ── 플랜트가 대는 것 — 벤더가 그리지 않거나, 플랜트가 자리를 옮긴 것들 ────
    # BX-101 브리지
    w(f"// BX-101 인계 브리지 — 기계 x {n(pick)} (GBR 캐리지 슬롯 면) → {n(place)} (LD-101 데크 중심) · 행정 {layout.bridge_travel_mm():,} · 승강 {layout.bridge_lift_mm()}")
    w(f"[-.75,.75].forEach(function(z){{L([{n(place-pick)},.05,.05],[{n((pick+place)/2)},{n(EL+.35)},z],M.steel,z<0?'BX-101 브리지 레일':null,z<0?'GBR 캐리지 슬롯 앞에서 LD-101 데크 중심까지 {layout.bridge_travel_mm():,} mm — 벤더가 발주자 설비로 넘긴 디스태커 PL-101 의 자리 (REV.54)':null)}});")
    w(f"L([.9,.06,1.42],[{n(pick+.6)},{n(EL+.29)},0],M.frame,'BX-101 인계 브리지','유리 한 장을 슬롯(950)에서 들어 {layout.bridge_lift_mm()} 올리고 LD-101 롤러베드(1,150)에 내려놓는 캐리어 — AXIS-GBR-BX · LP-GBR');")
    w(f"L([.9,.02,1.2],[{n(pick+.6)},{n(EL+.33)},0],M.panel,'브리지 위 유리','{LINE[0]:,} × {LINE[1]:,} · 유리면 ↓ 백시트 ↑ — 자세가 그대로 이어져 반전기가 없다');")
    w(f"[[{n(pick+.15)},-1.0],[{n(place-.4)},-1.0]].forEach(function(p,i){{MP(.14,.14,0,{n(EL+.32)},p[0],p[1],i===0?'BX-101 브리지 지주 2본 (베이스 4×M16)':null);AB(p[0],p[1],2,.16)}});")
    w(f"[[{n(pick+.15)},1.0],[{n(place-.4)},1.0]].forEach(function(p){{MP(.14,.14,0,{n(EL+.32)},p[0],p[1],null);AB(p[0],p[1],2,.16)}});")
    w(f"L([.15,.3,.12],[{n(pick+.2)},.15,1.35],M.red,'BX-SF-301 브리지 안전 스캐너','브리지 행정 구간 진입 방지 — 안전 PLC (SF-07)');")
    # RH-201 모노레일은 방책을 넘어 통로 **밖** 새들까지 간다 — 그 연장과 기둥,
    # 롤·카세트 새들은 플랜트가 자기 레인에 놓는다 (RFQ OI-17). 방책 안 권취
    # 드럼·문형은 벤더 원본에 있으므로 여기서 다시 그리지 않는다.
    wrx = m(H.WINDER_X_MM)
    hc = ST["HC"]                       # 명판 자리 — 가열실 중심 위
    fyn = m(H.FENCE_YN_MM)              # 통로쪽 방책선 (명판이 그 안쪽 면에 붙는다)
    w(f"L([.12,.12,{n(m(H.RH_Y_MM[0]-cass_y))}],[{n(wrx)},{n(rh_z)},{n((lz(H.RH_Y_MM[0])+lz(cass_y))/2)}],M.steel,'RH-201 모노레일 (EL {H.monorail_el_mm():,})','드럼 위(+550)에서 통로 위를 넘어 카세트 새들(−7,000)까지 — 롤과 소모품이 같은 길로 난다. 통로 위 헤드룸 {H.monorail_el_mm()-490:,}');")
    # 기둥은 방책 안(방책선 −50)과 통로 밖(방책선 − 통로폭 − 100)에 선다 — 플랜트 통로는 비운다
    aisle = layout.AISLE_WIDTH_MM
    for yy in (H.RH_Y_MM[0], -2600, -(H.FENCE_YN_MM - 50), -(H.FENCE_YN_MM + aisle + 100), cass_y):
        lab = s("RH-201 모노레일 기둥") if yy == H.RH_Y_MM[0] else "null"
        w(f"L([.14,{n(rh_z-.06)},.14],[{n(wrx+.3)},{n((rh_z-.06)/2)},{n(lz(yy))}],M.steel,{lab});")
        w(f"L([.4,.12,.14],[{n(wrx+.13)},{n(rh_z)},{n(lz(yy))}],M.steel,null);")  # 기둥 → 레일 캔틸레버 암
    w(f"L([1.4,.4,.9],[{n(wrx)},.72,{n(lz(roll_y))}],M.dark,'BS-301 만권 롤 새들 (통로 밖 · AGV 도킹)','기계 좌표 −5,200 은 플랜트 통로 한가운데(Y 8,600)라 −{-roll_y:,.0f}(Y {layout.roll_saddle_plant_y_mm():,})으로 낸다 — 벤더 확인사항 OI-16');")
    w(f"Ee(g,{n(H.const('WR_FULL_R'))},{n(H.const('ROLL_FACE'))},[{n(wrx)},1.22,{n(lz(roll_y))}],M.rubber,null,null,[Math.PI/2,0,0]);")
    w(f"L([1.2,.3,.8],[{n(wrx+.55)},.9,{n(lz(cass_y))}],M.dark,'KC-301 칼날 카세트 새들 (통로 밖)','200 ℃ 를 지난 카세트는 방책 밖에서만 만진다');")
    # 명판
    # 데칼은 월드 그룹에 존 식으로 놓고 adopt() 가 셀에 입양한다 — 통로 경계(방책 안쪽 면)
    w("})();")
    w(f"(function(){{var g=pt;window.pdGrm=pvNamePlate(g,1.6,[pvZone.grm[0]+{n(m(hc.cx_mm))},2.05,{n(round(fyn-.03+gz,4))}],0,'{H.TAG}','{H.MODEL} 유리제거기');}})();")
    w("(function(){")
    w("})();")
    w("/* @dgm-3d-end */")
    return "\n".join(o)


# ── 2D 시트 ─────────────────────────────────────────────────────────────────
def build_sheet() -> str:
    """`stations.grm` 메타데이터 — 로컬 원점은 존 중심, [X, 높이, 깊이(통로쪽 +)]."""
    cx = H.ENVELOPE_MM[0] // 2            # 9,800
    cy = H.FENCE_WIDTH_MM // 2            # 3,800
    def X(x_mm): return int(round(x_mm - cx))
    def Zc(y_mm): return int(round(-y_mm + H.FENCE_YP_MM - cy))   # 기계 y → 시트 깊이 (통로쪽 +)
    mods = H.MODULES
    ld, hc, dl, gc, ul = (ST[k] for k in ("LD", "HC", "DL", "GC", "UL"))
    tbl_cx = dl.x0_mm + 870 + H.const("CARRIER_L") * 500
    # 벤더 모듈 외형 (L, W, H) → 시트 축 [X, 상하, 깊이] = [L, H, W]
    def dims(key: str) -> list[int]:
        L_, W_, H_ = mods[key][1]
        return [L_, H_, W_]

    parts = [
        # 브리지는 존 경계를 475 물고 버퍼까지 간다(ZONE_OVERLAP_BY_DESIGN). 시트에는 존 안쪽 절반만 —
        # 인계면부터 LD-101 데크 중심까지의 레일을 그린다.
        ("BX-101", "인계 브리지 레일 · 캐리어 (플랜트 · AXIS-GBR-BX)", [H.INFEED_CX_MM, 60, 1420], [X(H.INFEED_CX_MM // 2), 1440, 0], [-1600, 400, 0], "primary"),
        ("LD-101", "투입 셔틀 롤러베드 · WI-101 계량 (M-001)", [ld.length_mm, 140, 1480], [X(ld.cx_mm), 1080, 0], [-1600, 0, 0], "primary"),
        ("HC-101", f"{H.DECKS}단 밀폐 IR 가열실 · {H.LAMPS}등 {H.IR_INSTALLED_KW:g} kW (M-002)", dims("M-002"), [X(hc.cx_mm), mods["M-002"][1][2] // 2, 0], [-900, 0, 0], "primary"),
        ("LI-101", "투입 승강 포크 문형 (M-003)", dims("M-003"), [X(ld.x1_mm - 420), mods["M-003"][1][2] // 2, 0], [-1200, 600, 0], "secondary"),
        ("EX-101", "방출 승강 포크 문형 (M-003)", dims("M-003"), [X(dl.x0_mm + 420), mods["M-003"][1][2] // 2, 0], [-400, 600, 0], "secondary"),
        ("VT-101", "6존 고정 진공테이블 (M-004)", dims("M-004"), [X(tbl_cx), mods["M-004"][1][2] // 2, 0], [0, -500, 0], "primary"),
        ("KG-101", "이동 나이프 갠트리 · 주행레일 EL 1,950 (M-005)", [3500, 2720, 3010], [X((H.const("CRAIL_X0") + H.const("CRAIL_X1")) * 500), 1360, 0], [0, 1200, 0], "primary"),
        ("BC-201", "HKB/HKS 칼날 카세트 (KC-101 자동교환)", [600, 900, 1440], [X(tbl_cx - 900), 1600, 0], [200, 900, 0], "primary"),
        ("WR-101", "백시트 권취 · 만권 롤 Ø600 (M-006)", [1300, 600, 1460], [X(H.WINDER_X_MM), 3700, 0], [0, 1400, -900], "secondary", "cylinder"),
        ("RH-201", "롤·카세트 반출 모노레일 EL 5,100 (방책까지)", [140, 140, H.FENCE_YN_MM + H.RH_Y_MM[0]], [X(H.WINDER_X_MM), H.monorail_el_mm(), Zc((H.RH_Y_MM[0] - H.FENCE_YN_MM) / 2)], [0, 1600, 0], "base"),
        ("KC-101", "칼날 카세트 매거진 (갠트리 위)", [1000, 400, 700], [X(H.const("CKC_X") * 1000), H.const("CKC_Z") * 1000, Zc(H.const("CKC_Y") * 1000)], [200, 1000, 800], "secondary"),
        ("CE-201", "셀/EVA 횡인출 컨베이어 EL 1,050 (M-008)", [H.CE_X_MM[1] - H.CE_X_MM[0], 100, 2000], [X(CART_X := (H.CE_X_MM[0] + H.CE_X_MM[1]) // 2), H.CE_EL_MM, Zc(-1900)], [0, -300, 1200], "secondary"),
        ("CS-201", "셀/EVA 평적 카트 2,600 × 1,300", [H.CART_L_MM, 550, H.CART_W_MM], [X(H.CART_X_MM), 275, Zc(H.CART_Y_MM)], [0, 0, 1800], "base"),
        ("GC-101", f"{H.DECKS}단 유리 냉각 랙 · 140 → 60 ℃ (M-007)", dims("M-007"), [X(gc.cx_mm), mods["M-007"][1][2] // 2, 0], [700, 0, 0], "primary"),
        ("GL-101", "냉각 적입 포크 문형 (M-003)", dims("M-003"), [X(gc.x0_mm - 420), mods["M-003"][1][2] // 2, 0], [400, 600, 0], "secondary"),
        ("GU-101", "냉각 인출 포크 문형 (M-003)", dims("M-003"), [X(gc.x1_mm + 420), mods["M-003"][1][2] // 2, 0], [900, 600, 0], "secondary"),
        ("UL-101", "반출 셔틀 · WO-303 계량 (M-001)", [ul.length_mm, 140, 1480], [X(ul.cx_mm), 1080, 0], [1600, 0, 0], "primary"),
        ("QI-301", "검사 아치 · RJ-301 리젝트 (M-009)", dims("M-009"), [X(ul.x0_mm + 360), mods["M-009"][1][2] // 2, 0], [1200, 900, 0], "secondary"),
        ("M-011", "전력·MCC·제어반 (기초 패드 P1 · EP-1)", dims("M-011"), [X(4200), mods["M-011"][1][2] // 2, Zc(-3200)], [-1200, 0, 1400], "base"),
        ("M-012", "VU-101 진공·계장공기 스키드 (기초 패드 P2 · EP-3)", dims("M-012"), [X(12280), mods["M-012"][1][2] // 2, Zc(-3200)], [0, 0, 1400], "base"),
        ("BJ-101", "경계 인터페이스반 BJ-101/102 (기초 패드 P3)", [1500, 2000, 1000], [X(H.BJ_X_MM), 1000, Zc(H.BJ_Y_MM)], [1200, 0, 1400], "base"),
        ("EXH", f"배기 헤더 Ø460 → 경계 플랜지 Ø600 EL {H.DUCT_FLANGE_EL_MM:,}", [H.DUCT_FLANGE_X_MM - hc.cx_mm, 460, 460], [X((hc.cx_mm + H.DUCT_FLANGE_X_MM) // 2), H.DUCT_FLANGE_EL_MM, Zc(H.DUCT_Y_MM)], [0, 1800, -1200], "base"),
        ("GLASS", "회수 판유리 팔레트 (픽업 스테이션)", [1300, 240, 1340], [X(GLASS_PICKUP_IN_MM), 230, 0], [2000, 600, 0], "primary", "panel"),
        ("SCN-B", "BX-SF-301 브리지 안전 스캐너", [150, 300, 120], [X(120), 150, 1350], [-1800, -400, 800], "safety", "camera"),
        ("FENCE", "M-013 방책 · LC-001/002 광커튼 · 외장", [H.FENCE_X1_MM, 2400, H.FENCE_WIDTH_MM], [X(H.FENCE_X1_MM // 2), 1200, 0], [0, 0, 0], "safety", "guard"),
    ]
    r = H.rate()
    flow = [
        ("1", f"BX-101 브리지 — GBR 슬롯(950)에서 LD-101 데크(1,150)로 {layout.bridge_travel_mm():,} (인계면부터)", [X(0), 1150, 0], [X(ld.cx_mm), 1150, 0]),
        ("2", f"LI-101 포크가 C1…C{H.DECKS} 에 적재 · FULL_LOAD_ACK 후 밀폐 가열 (소킹 {r.dwell_s:g} s)", [X(ld.cx_mm), 1150, 0], [X(hc.cx_mm), 2450, 0]),
        ("3", f"EX-101 방출 (피치 {r.release_pitch_s:g} s) → VT-101 흡착 · 이동 나이프 HKB→HKS 박리 (사이클 {r.tandem_cycle_s:g} s)", [X(hc.cx_mm), 1150, 0], [X(tbl_cx), 1150, 0]),
        ("4", "백시트는 WR-101 권취 → RH-201 로 통로 밖 새들 · 셀/EVA 는 CE-201 → CS-201 카트", [X(tbl_cx), 1500, 0], [X(H.WINDER_X_MM), 3700, 0]),
        ("5", f"GL-101 → GC-101 {H.DECKS}단 냉각 140 → 60 ℃ (143 s)", [X(tbl_cx), 1150, 0], [X(gc.cx_mm), 2450, 0]),
        ("6", "GU-101 → QI-301 검사 → UL-101 반출 → 픽업 스테이션 (GLASS_TAKEAWAY_READY)", [X(gc.cx_mm), 1150, 0], [X(GLASS_PICKUP_IN_MM), 250, 0]),
    ]
    def js(v): return json.dumps(v, ensure_ascii=False)
    lines = ["    /* @dgm-sheet-begin */",
             "    // REV.54: 후단은 DG-HK60C 다. 외형·부품 좌표는 그 기계의 콘솔·사양서·부품 카탈로그",
             "    // (hk60c.py) 에서 tools/build_dgm.py 가 찍는다 — 벤더 GA 가 바뀌면 콘솔을 고치고 다시 찍는다.",
             "    grm: {",
             f"      sheet: {s(layout.STATIONS['grm'].sheet)},",
             f"      name: {s(layout.STATIONS['grm'].name)},",
             f"      envelope: {list(H.ENVELOPE_MM)},",
             f"      transfer: {H.LINE_EL_MM},",
             "      datum: 'A=공정선 EL 1,150 (LD·VT·UL 공통) · B=기계 통심 YC · C=칼끝 300 리드 · D=D-602 X1 끝벽',",
             f"      anchors: {s(mounting.anchor_text('grm'))},",
             "      tolerance: '앵커 위치 ±10 · 레벨 ±5 (D-602) · 롤러 상면 EL 1,150 ±2 · 칼끝 간격 300±2 · 폭 정렬 1,200±3',",
             "      service: '방책 −y 카트 레인 1,850 · 정비 간격 300 · 통로 밖 물류 레인 2,200 (새들·AGV)',",
             f"      utility: 'IR {H.LAMPS}등 {H.IR_INSTALLED_KW:g} kW · 연결부하 {H.CONNECTED_KW:g} kW(수요 {H.EXPECTED_DEMAND_KW:g}) · 진공 −65 kPa 6존 · 계장공기 0.6 MPa · 경계 덕트 Ø600 (팬·후처리 발주자)',",
             f"      release: '브리지 핸드셰이크(UP_PANEL_OFFER/ACK) · IF_ESTOP_LOOP_OK · FULL_LOAD_ACK · P95 사이클 {r.tandem_cycle_s:g} s · 60장 연속 · GC-101 냉각 배기 합류 확인 (OI-16)',",
             f"      levels: [[{H.LINE_EL_MM}, 'LINE EL {H.LINE_EL_MM:,}'], [{H.const('CRAIL_Z')*1000:.0f}, 'RAIL {H.const('CRAIL_Z')*1000:,.0f}'], [{mods['M-002'][1][2]}, 'HC TOP {mods['M-002'][1][2]:,}'], [{H.DUCT_FLANGE_EL_MM}, 'DUCT/RH {H.DUCT_FLANGE_EL_MM:,}']],",
             "      parts: ["]
    for p in parts:
        pid, label, size, at, explode, tone = p[:6]
        kind = f", {s(p[6])}" if len(p) > 6 else ""
        lines.append(f"        part({s(pid)}, {s(label)}, {js([int(round(v)) for v in size])}, {js([int(round(v)) for v in at])}, {js(explode)}, {s(tone)}{kind}),")
    lines[-1] = lines[-1].rstrip(",")
    lines.append("      ],")
    lines.append("      flow: [")
    for mark, label, a, b in flow:
        lines.append(f"        step({s(mark)}, {s(label)}, {js([int(round(v)) for v in a])}, {js([int(round(v)) for v in b])}),")
    lines[-1] = lines[-1].rstrip(",")
    lines.append("      ]")
    lines.append("    }")
    lines.append("    /* @dgm-sheet-end */")
    return "\n".join(lines)


# ── 인계 패널 ───────────────────────────────────────────────────────────────
def build_handoff_js() -> str:
    hs = handoff.summary()
    p = handoff.pacing()
    r = handoff.downstream_rate()
    lit = {
        "model": H.MODEL, "rev": H.REV, "tag": H.TAG,
        "bufferPose": handoff.BUFFER_POSE, "downstreamPose": handoff.DOWNSTREAM_POSE,
        "poseOk": handoff.pose_matches(),
        "upstream": list(handoff.UPSTREAM_MAX_MM), "deck": list(handoff.DOWNSTREAM_MAX_MM),
        "deckMin": list(handoff.DOWNSTREAM_MIN_MM),
        "overL": handoff.oversize_mm()[0], "overW": handoff.oversize_mm()[1],
        "feedUnpaced": p.feed_unpaced_per_h, "feed": p.feed_per_h,
        "gapUnpaced": hs["gap_unpaced_per_h"], "gap": p.gap_per_h,
        "raSlots": handoff.BUFFER_RA_SLOTS,
        "autonomyUnpaced": hs["autonomy_unpaced_h"],
        "holdS": p.hold_s, "taktS": p.takt_s, "taktUnpacedS": campaign.summary(0.0)["takt_s"],
        "allowed": p.allowed_per_h, "margin": p.margin_per_h, "annualLossPct": p.annual_loss_pct,
        "rideThrough": handoff.buffer_ride_through_h(),
        "drainRideThrough": handoff.buffer_drain_ride_through_h(),
        "stockSlots": handoff.buffer_stock_target_slots(), "headroomSlots": handoff.buffer_headroom_slots(),
        "loadPanels": handoff.DOWNSTREAM_LOAD_PANELS,
        "lamps": handoff.LAMP_COUNT, "lampKw": handoff.LAMP_KW, "irKw": handoff.IR_INSTALLED_KW,
        "bridgeMm": layout.bridge_travel_mm(), "bridgeLiftMm": layout.bridge_lift_mm(),
        "lineEl": H.LINE_EL_MM,
        "rate": {"line": r.line_per_h, "nominal": r.tandem_per_h, "thermal": r.thermal_per_h,
                 "tandemCycle": r.tandem_cycle_s, "dwell": r.dwell_s, "pitch": r.release_pitch_s,
                 "bottleneck": r.bottleneck, "availability": H.AVAILABILITY, "knife": H.KNIFE_SPEED_MM_S},
    }
    body = json.dumps(lit, ensure_ascii=False, separators=(",", ":"))
    body = re.sub(r'"(\w+)":', r"\1:", body)
    js = f"""/* @dgm-handoff-begin */
var pvHandoff={body};
(function(){{
  var rows=Ae.querySelector("#jb-ho-rows");if(!rows)return;
  var H=pvHandoff,d=H.rate,warn='style="color:var(--jb-red,#d33)"';
  var n=function(v){{return String(v).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g,",")}};
  var mk=function(a,b,c,ok,note){{return "<tr><td>"+a+"</td><td>"+b+"</td><td>"+c+"</td><td"+(ok?">✔ ":" "+warn+">✘ ")+note+"</td></tr>"}};
  rows.innerHTML=
    mk("자세",H.bufferPose,H.downstreamPose,H.poseOk,H.poseOk?"일치 — 경계에 반전기 불요":"불일치 — 경계 반전기 필요")
   +mk("모듈 상한",n(H.upstream[0])+" × "+n(H.upstream[1])+" mm (REV.54 통일)",
       n(H.deck[0])+" × "+n(H.deck[1])+" mm (하한 "+n(H.deckMin[0])+" × "+n(H.deckMin[1])+")",H.overL===0&&H.overW===0,
       H.overL===0&&H.overW===0?"라인 상한을 후단 상한으로 통일 — 초과 모듈은 반입 등록에서 범위 외 리젝트":"길이 +"+H.overL+" · 폭 +"+H.overW+" 초과")
   +mk("처리율",H.feedUnpaced+" 장/h (제 속도 R-A) → 페이싱 "+H.feed,d.line+" 장/h 순생산 (명목 "+d.nominal+" × 가동률 "+d.availability+") · 병목 "+d.bottleneck,H.gap<=0,
       "페이싱 전 유입이 "+H.gapUnpaced+" 장/h 빨라 버퍼 "+H.raSlots+"슬롯이 "+H.autonomyUnpaced+" h 만에 찬다 → 방출 보류 "+H.holdS+" s 로 택트 "+H.taktUnpacedS+" → "+H.taktS+" s, 여유 "+(-H.gap)+" 장/h")
   +mk("인계 방식","GBR 캐리지 슬롯 (데크 950)","LD-101 롤러베드 (공정선 EL "+n(H.lineEl)+") · 벤더는 팔레트 픽업+발주자 디스태커를 전제",!0,
       "BX-101 브리지가 디스태커 자리를 대신한다 — 행정 "+n(H.bridgeMm)+" mm · 승강 "+H.bridgeLiftMm+" mm · 한 장씩")
   +mk("적재 단위","1장씩 캐리지 슬롯",H.loadPanels+"장 만재 후 밀폐 가열(FULL_LOAD_ACK) → 방출한 단 즉시 재장전",!0,
       "회전식 재장전은 시각표로 롤링과 같다 — 소킹 "+d.dwell+" s · 피치 "+d.pitch+" s");
  var pb=Ae.querySelector("#jb-ho-plans");
  if(pb)pb.innerHTML=
    "<tr><td>제 속도</td><td>보류 0 s</td><td>"+H.feedUnpaced+" → <b>"+d.line+"</b> 장/h</td><td "+warn+">✘ "+H.gapUnpaced+"</td><td>버퍼 "+H.autonomyUnpaced+" h 만에 만재 → 정지·기동 반복, 무인 허가 깨짐</td></tr>"
   +"<tr><td><b>채택 · 페이싱</b></td><td>방출 보류 "+H.holdS+" s (후단 "+d.line+" − 여유 "+H.margin+" = 허용 R-A "+H.allowed+")</td><td>"+H.feed+" → <b>"+d.line+"</b> 장/h</td><td>✔ "+(-H.gap)+"</td><td>연간 −"+H.annualLossPct+" % · 셀 점유는 그대로, 인터록 하나만 바뀐다</td></tr>";
  Ae.querySelector("#jb-ho-autonomy").textContent=H.rideThrough+"시간";
  Ae.querySelector("#jb-ho-verdict").innerHTML=
    "<b>정리</b> — 후단은 <b>"+H.model+" ("+H.rev+")</b> 이고 플랜트 태그는 "+H.tag+" 다. 자세는 그대로 이어진다. "
    +"라인 상한은 후단 상한 <b>"+n(H.deck[0])+" × "+n(H.deck[1])+"</b> 으로 통일했다 — 플랜트 하드웨어를 줄여 얻는 것이 없고, 후단의 IR 뱅크 해석·파일럿·부품도가 그 상한 위에 서 있기 때문이다. "
    +"처리율은 후단 순생산 "+d.line+" 장/h 가 제 속도 유입 "+H.feedUnpaced+" 보다 느려 <b>전처리를 페이싱</b>한다 — 방출 보류 "+H.holdS+" s, 택트 "+H.taktS+" s, R-A "+H.feed+" 장/h 로 여유 "+(-H.gap)+". "
    +"버퍼는 밀린 것을 쌓는 곳이 아니라 <b>후단이 멈춰도 "+H.rideThrough+"시간은 전처리를 계속 돌리는 완충</b>이고, 후단의 계획 정지(카세트 교환·롤 반출)는 순생산에 평균으로 들어 있어 낱개 정지를 이 여유공간이 받는다. "
    +"IR 은 "+H.lamps+"등 "+H.irKw+" kW 로 "+d.thermal+" 장/h 여유가 있고 병목은 "+d.bottleneck+" 이다 — 칼날 "+d.knife+" mm/s 는 파일럿(OI-01/06)이 확정할 값이라 지금 올려 잡지 않는다."
}}());
/* @dgm-handoff-end */"""
    return js


def build_handoff_html() -> str:
    r = handoff.downstream_rate()
    return f"""<!-- @dgm-ho-begin -->
  <details class="jb-engineering" id="jb-handoff">
    <summary>후단 인계 — {H.MODEL} 유리제거기 <span class="viz-badge">PV-PLANT-HO-1012</span></summary>
    <p class="text-small text-muted">전처리의 마지막 공정은 알루미늄 프레임 제거(AFR) 뒤의 <b>유리 버퍼</b>다. 그 버퍼가
      <a href="pv-delamination-3d.html" target="_blank" rel="noopener"><b>{H.MODEL}</b> — {H.DECKS}단 밀폐 IR 가열실·이동 나이프 탠덤·{H.DECKS}단 냉각 랙 ({H.REV} {H.PLAN})</a> 의 투입 셔틀 LD-101 로 이어진다.
      벤더 문서: <a href="../dg-hk60-rfq.html" target="_blank" rel="noopener">발주 기술사양서 (RFQ)</a> · <a href="../dg-hk60-assembly.html" target="_blank" rel="noopener">조립 지침서</a> — 상류 직결 확인사항은 RFQ OI-16.
      잇는다는 것은 링크를 거는 일이 아니라 <b>경계 조건이 맞는지 따지는 일</b>이다. REV.54 에서 넷을 다시 쟀다 — 자세 하나만 그대로 맞고, 치수·처리율·인계 방식은 결정이 필요했다.
      후단 수치는 옮겨 적지 않는다 — <code>src/pv_preprocess/hk60c.py</code> 가 그 기계의 콘솔·사양서에서 읽고, <code>handoff.py</code> 와 어긋나면 테스트가 실패한다.</p>
    <div class="table-responsive">
      <table class="table table-sm">
        <caption class="text-small text-muted">경계 조건 대조 — 전처리 버퍼 출구 ↔ {H.MODEL} 투입부</caption>
        <thead><tr><th>항목</th><th>전처리 버퍼 출구</th><th>{H.MODEL} 투입부</th><th>판정</th></tr></thead>
        <tbody id="jb-ho-rows"></tbody>
      </table>
    </div>
    <p class="text-small" id="jb-ho-verdict"></p>
    <div class="table-responsive">
      <table class="table table-sm">
        <caption class="text-small text-muted">격차 {abs(handoff.rate_gap_per_h(0.0)):g} 장/h 를 어디서 흡수하는가 — 전처리 페이싱 (REV.54 채택)</caption>
        <thead><tr><th>안</th><th>손잡이</th><th>유입 → 처리</th><th>여유</th><th>대가</th></tr></thead>
        <tbody id="jb-ho-plans"></tbody>
      </table>
    </div>
    <p class="text-small text-muted">파손 유리(R-B)는 이 인계에 넣지 않는다 — 시트로 벗길 수 없어 파편 계통(R-B2 밀폐 파편 분리)으로 빠진다.
      페이싱 뒤에는 후단이 유입보다 빨라 버퍼가 차지 않는다 — 후단이 멈춰도 전처리를 <span id="jb-ho-autonomy"></span> 더 돌리는 완충으로만 남는다.
      후단의 계획 정지(칼날 카세트 교환 3.9 분 · 만권 롤 {H.ROLL_PERIOD_H:g} h 마다)는 순생산 {r.line_per_h:g} 장/h 에 가동률 {H.AVAILABILITY:g} 으로 이미 들어 있다.</p>
  </details>
<!-- @dgm-ho-end -->"""


# ── 조립 ────────────────────────────────────────────────────────────────────
def replace_between(text: str, begin: str, end: str, block: str, *, first_begin: str | None = None,
                    first_end: str | None = None, keep_end: bool = False) -> str:
    """표식 사이를 갈아 끼운다. 표식이 없으면 처음 한 번은 옛 앵커로 자리를 잡는다."""
    if begin in text and end in text:
        i, j = text.index(begin), text.index(end) + len(end)
        return text[:i] + block + text[j:]
    assert first_begin and first_end, f"표식도 옛 앵커도 없다: {begin}"
    assert text.count(first_begin) == 1, f"옛 앵커 {text.count(first_begin)}곳: {first_begin[:60]}"
    assert text.count(first_end) == 1, f"옛 앵커 {text.count(first_end)}곳: {first_end[:60]}"
    i = text.index(first_begin)
    j = text.index(first_end) + (len(first_end) if keep_end else 0)
    assert i < j
    return text[:i] + block + text[j:]


def main() -> int:
    text = DRAWING.read_text(encoding="utf-8")

    # 3D 셀 — 옛 pvGrm 블록(REV.23~53)은 `var pvGrm=new ce;` 로 시작해 지지·장착 IIFE 의
    # `})();` 로 끝난다. 그 뒤가 `Ae.__pvFlyTest` 다.
    text = replace_between(text, "/* @dgm-3d-begin */", "/* @dgm-3d-end */", build_3d(),
                           first_begin="var pvGrm=new ce;", first_end="})();\n\nAe.__pvFlyTest",
                           keep_end=False)
    # 옛 블록의 마지막 `})();` 는 first_end 앵커의 일부라 남는다 — 새 블록이 자기 것을 갖고 있으므로 지운다.
    text = text.replace("/* @dgm-3d-end */})();\n\nAe.__pvFlyTest", "/* @dgm-3d-end */\n\nAe.__pvFlyTest")
    text = text.replace("/* @dgm-3d-end */\n})();\n\nAe.__pvFlyTest", "/* @dgm-3d-end */\n\nAe.__pvFlyTest")
    # 옛 머리말 주석
    old_head = re.search(r"/\* REV\.23 GRM-401 유리제거셀 — 링크만 걸려 있던 후단 라인을 3D 장면에 세운다\..*?\*/\n", text, re.S)
    if old_head:
        text = text.replace(old_head.group(0), "/* REV.54 후단 유리제거기 DG-HK60C — 3D 셀은 아래 @dgm-3d 블록에서 tools/build_dgm.py 가 찍는다. */\n")

    # 2D 시트 메타데이터
    text = replace_between(text, "    /* @dgm-sheet-begin */", "    /* @dgm-sheet-end */", build_sheet(),
                           first_begin="    // REV.23: 유리제거(박리) 라인을 플랜트 안으로 들여왔다. 종전에는 버퍼에서",
                           first_end="        step('6', '셀/EVA 는 CB-201·슈레더로, 유리는 DS-301 적층', [1200, 1100, 2050], [5175, 800, 0])\n      ]\n    }",
                           keep_end=True)

    # 인계 패널 JS
    text = replace_between(text, "/* @dgm-handoff-begin */", "/* @dgm-handoff-end */", build_handoff_js(),
                           first_begin="var pvHandoff={plans:",
                           first_end="s 로 늘고 여유가 4.6 → \"+(-H.gap)+\" 장/h 로 줄어든 것이다.\"\n}());",
                           keep_end=True)
    # 인계 패널 HTML
    text = replace_between(text, "<!-- @dgm-ho-begin -->", "<!-- @dgm-ho-end -->", build_handoff_html(),
                           first_begin='  <details class="jb-engineering" id="jb-handoff">',
                           first_end="더 돌리는 완충으로만 남는다.</p>\n  </details>", keep_end=True)

    # 도면 목록 GA 행
    text = re.sub(r"\['PV-(?:GRM|DGM)-401-GA-6101', '[^']*', '2D/3D GA', '[^']*', '[^']*'\]",
                  f"['{layout.STATIONS['grm'].sheet}', '{H.MODEL} 유리제거기 (벤더 · {H.DECKS}단 IR·탠덤·냉각 랙)', "
                  "'2D/3D GA', '앱 반영', '벤더 D-602 기초·앵커 하중 · 냉각 배기 합류 · 브리지 핸드셰이크 (OI-16)']", text)
    # 인터록 표 두 행
    text = re.sub(r"<tr><td>AFR 박리 허가</td><td>[\d,]+×[\d,]+ 치수 레시피,",
                  f"<tr><td>AFR 박리 허가</td><td>{LINE[0]:,}×{LINE[1]:,} 치수 레시피,", text)
    text = re.sub(r"<tr><td>BX-101 인계</td><td>[^<]*</td><td>[^<]*</td></tr>",
                  "<tr><td>BX-101 인계</td><td>GBR 캐리지 슬롯 점유·RFID 일치, DG-HK60C UP_PANEL_ACK(LD-101 빈 상태·TRACK_CLEAR·LOT_OPEN), "
                  "IF_ESTOP_LOOP_OK, 브리지 원점 ACK</td><td>브리지 정지·유리 현재 위치 유지, 경계 안전회로 개방 시 자동복귀 금지·작업자 확인 요청</td></tr>", text)
    # 명판·엣지 캐비닛 — 옛 REV.50 명판(존 시작 +9,625 월드 리터럴)은 새 블록이 자기 명판을 갖고 오므로 지운다
    text = re.sub(r"window\.pdGrm=pvNamePlate\(g,1\.6,\[pvZone\.grm\[0\]\+9\.625,2\.05,3\.544\],0,'GRM-401','유리 제거'\);\n", "", text)
    text = re.sub(r"'EC-GRM','[^']*'", f"'EC-GRM','{ZONE.label}'", text)
    text = text.replace("'GRM-401 명판 → (무명)'", f"'{H.TAG} 명판 → (무명)'")
    # 라인 상한 문구 — 2,500 × 1,400 은 REV.54 이전 값이다
    text = text.replace("2,500 × 1,400", f"{LINE[0]:,} × {LINE[1]:,}")
    text = text.replace("2,500×1,400", f"{LINE[0]:,}×{LINE[1]:,}")

    DRAWING.write_text(text, encoding="utf-8")
    print(f"DG-HK60C 도면 블록 재생성 — 3D {len(build_3d()):,} 자 · 시트 {len(build_sheet()):,} 자 · 인계 {len(build_handoff_js()):,} 자")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
