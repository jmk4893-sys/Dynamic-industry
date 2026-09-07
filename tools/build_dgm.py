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

from pv_preprocess import campaign, handoff, hk60c, layout, line, mounting  # noqa: E402

LINE = line.LINE_MAX_MM   # 라인 패널 상한 — 기계 안에서 움직이는 유리는 이 크기다

DRAWING = pathlib.Path(__file__).resolve().parent.parent / "docs/drawings/pv-preprocess-plant.html"
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
    # 방책 M-013 — 상류(x 0)는 플랜트 끝단 케이싱·브리지 개구가 대신한다
    fx1 = m(H.FENCE_X1_MM); fyp = m(H.FENCE_YP_MM); fyn = m(H.FENCE_YN_MM)
    w(f"// 방책 M-013 — x 0…{n(fx1)} · z {n(-fyp)}(벽쪽)…{n(fyn)}(통로쪽) · 높이 2.4. 상류선(−0.9)은 브리지 개구라 안 세운다.")
    w(f"[{n(-fyp)},{n(fyn)}].forEach(function(z){{L([{n(fx1)},.06,.06],[{n(fx1/2)},2.4,z],M.guard,z>0?'DG-HK60C M-013 방책':null,z>0?'방책선 {H.FENCE_X0_MM:,} → {H.FENCE_X1_MM:,} · +{H.FENCE_YP_MM:,} / {H.FENCE_YN_MM * -1:,} — 카트 레인이 −y 쪽이라 통로 쪽이 {H.FENCE_YN_MM - H.FENCE_YP_MM:,} 넓다':null);"
      f"for(var x=.05;x<{n(fx1)};x+=2.4)L([.06,2.4,.06],[Math.min(x,{n(fx1-.05)}),1.2,z],M.guard,null)}});")
    w(f"L([.06,2.4,{n(fyp+fyn)}],[{n(fx1-.03)},1.2,{n((fyn-fyp)/2)}],M.guard,null);")
    w(f"L([.06,2.4,{n(fyp+fyn)}],[.03,1.2,{n((fyn-fyp)/2)}],M.guard,null,null);")
    # 외장 (외피) — 벽 두 장 + 갓돌
    sx0 = m(ST["HC"].x0_mm - 200); sx1 = m(ST["GC"].x1_mm + 200); sky = m(H.SKIN_Y_MM)
    w(f"// 외장 — x {n(sx0)}…{n(sx1)} · z ±{n(sky)} · 3.6 (갓돌 4.8 단높임은 가열실·냉각 랙 위)")
    w(f"[{n(-sky)},{n(sky)}].forEach(function(z){{L([{n(sx1-sx0)},3.6,.07],[{n((sx0+sx1)/2)},1.8,z],M.guard,z>0?'DG-HK60C 외장 (연마 STS304 #400)':null,z>0?'내피 반사율 ρ ≥ 0.4 — IR 뱅크 검토가 미관이 아니라 검사 항목으로 만든 값':null)}});")
    # LD-101 투입 셔틀 + WI-101
    ld = ST["LD"]
    w(f"// LD-101 투입 셔틀 — x {n(m(ld.x0_mm))}…{n(m(ld.x1_mm))} · 공정선 EL {n(EL)}")
    w(f"L([{n(m(ld.length_mm))},.14,1.48],[{n(m(ld.cx_mm))},{n(EL-.07)},0],M.frame,'LD-101 투입 셔틀 롤러베드','브리지가 유리 한 장을 내려놓는 벤더 공정선 EL 1,150 — 폭 정렬 가이드가 1,200±3 으로 문다. 지게차 수동 적재는 비상 우회로만 남는다');")
    w(f"for(var i=0;i<12;i++)Ee(g,pvRollR,1.4,[{n(m(ld.x0_mm)+.2)}+i*.24,{n(EL)}-pvRollR,0],M.rubber,i===0?'LD-101 이송 롤러':null,null,[Math.PI/2,0,0]);")
    w(f"[[{n(m(ld.x0_mm)+.3)},-.6],[{n(m(ld.x0_mm)+.3)},.6],[{n(m(ld.x1_mm)-.3)},-.6],[{n(m(ld.x1_mm)-.3)},.6]].forEach(function(p){{L([.1,{n(EL-.14)},.1],[p[0],{n((EL-.14)/2)},p[1]],M.steel,null)}});")
    # WI-101 은 롤러베드 밑에 제 다리로 선다 — 하중경로 검사가 뜬 계량기를 잡았다 (REV.54)
    w(f"L([1.1,.5,1.3],[{n(m(ld.cx_mm)-.22)},{n(EL-.14-.25)},0],M.steel,'WI-101 투입 계량 컨베이어','로드셀 4점 합산 ±0.2 % F.S. — 물질수지의 투입 1점. 롤러베드 밑 자립 프레임에 로드셀 4점');")
    w(f"[[-.5,-.6],[-.5,.6],[.5,-.6],[.5,.6]].forEach(function(p){{L([.08,{n(EL-.14-.5)},.08],[{n(m(ld.cx_mm)-.22)}+p[0],{n((EL-.14-.5)/2)},p[1]],M.steel,null)}});")
    w(f"[-.8,.8].forEach(function(z){{L([1.9,.09,.16],[{n(m(ld.cx_mm))},{n(EL+.1)},z],M.steel,z<0?'LD-101 폭조절 가이드':null,z<0?'패널 폭 편차 흡수 · 1,200±3 로 문다':null)}});")
    w(f"L([.24,.2,.18],[{n(m(ld.x0_mm)+.9)},2.28,1.1],M.dark,'LD-101 바코드·라벨 리더','LOT_ID_VALID — 브리지 핸드셰이크가 넘긴 패널 ID 와 대조 (RF-902)');")
    w(f"L([.06,2.18,.06],[{n(m(ld.x0_mm)+.9)},1.09,1.1],M.steel,null);")  # 리더 지주
    # BX-101 브리지
    w(f"// BX-101 인계 브리지 — 기계 x {n(pick)} (GBR 캐리지 슬롯 면) → {n(place)} (LD-101 데크 중심) · 행정 {layout.bridge_travel_mm():,} · 승강 {layout.bridge_lift_mm()}")
    w(f"[-.75,.75].forEach(function(z){{L([{n(place-pick)},.05,.05],[{n((pick+place)/2)},{n(EL+.35)},z],M.steel,z<0?'BX-101 브리지 레일':null,z<0?'GBR 캐리지 슬롯 앞에서 LD-101 데크 중심까지 {layout.bridge_travel_mm():,} mm — 벤더가 발주자 설비로 넘긴 디스태커 PL-101 의 자리 (REV.54)':null)}});")
    w(f"L([.9,.06,1.42],[{n(pick+.6)},{n(EL+.29)},0],M.frame,'BX-101 인계 브리지','유리 한 장을 슬롯(950)에서 들어 {layout.bridge_lift_mm()} 올리고 LD-101 롤러베드(1,150)에 내려놓는 캐리어 — AXIS-GBR-BX · LP-GBR');")
    w(f"L([.9,.02,1.2],[{n(pick+.6)},{n(EL+.33)},0],M.panel,'브리지 위 유리','{LINE[0]:,} × {LINE[1]:,} · 유리면 ↓ 백시트 ↑ — 자세가 그대로 이어져 반전기가 없다');")
    w(f"[[{n(pick+.15)},-1.0],[{n(place-.4)},-1.0]].forEach(function(p,i){{MP(.14,.14,0,{n(EL+.32)},p[0],p[1],i===0?'BX-101 브리지 지주 2본 (베이스 4×M16)':null);AB(p[0],p[1],2,.16)}});")
    w(f"[[{n(pick+.15)},1.0],[{n(place-.4)},1.0]].forEach(function(p){{MP(.14,.14,0,{n(EL+.32)},p[0],p[1],null);AB(p[0],p[1],2,.16)}});")
    w(f"L([.15,.3,.12],[{n(pick+.2)},.15,1.35],M.red,'BX-SF-301 브리지 안전 스캐너','브리지 행정 구간 진입 방지 — 안전 PLC (SF-07)');")
    # HC-101 가열실
    hc = ST["HC"]; hcw = m(mods["M-002"][1][1]); hch = m(mods["M-002"][1][2])
    w(f"// HC-101 {H.DECKS}단 밀폐 IR 가열실 — x {n(m(hc.x0_mm))}…{n(m(hc.x1_mm))} · 폭 {n(hcw)} · 높이 {n(hch)} (M-002)")
    w(f"L([{n(m(hc.length_mm))},{n(hch)},{n(hcw)}],[{n(m(hc.cx_mm))},{n(hch/2)},0],M.frame,'DG-HK60C HC-101 가열실 골조 (벤더 앵커군 A1)','{H.DECKS}단 밀폐 가열실 · IR {H.LAMPS}등 × {n(H.LAMP_KW)} kW = {H.IR_INSTALLED_KW:g} kW · 소킹 {H.rate().dwell_s:g} s · 방출 피치 {H.rate().release_pitch_s:g} s · 차압 −30 Pa · 5,763 kg 현장 조립');")
    for k in range(H.DECKS):
        dz = H.const("CDECK_Z0") + H.const("CDECK_DZ") * (k + .5)
        lab = s("C1…C5 데크 (만재 후 회전식 재장전)") if k == 0 else "null"
        tip = s("FULL_LOAD_ACK 뒤 소킹이 끝난 단부터 한 장 방출 → 같은 단 재장전") if k == 0 else "null"
        w(f"L([{n(m(hc.length_mm)-.8)},.04,{n(hcw-.4)}],[{n(m(hc.cx_mm))},{n(dz)},0],M.aluminum,{lab},{tip});")
    w(f"L([{n(m(hc.length_mm)-.6)},.12,.16],[{n(m(hc.cx_mm))},{n(hch+.06)},0],M.orange,'HC-101 IR 뱅크 B0~B{H.DECKS} 램프 단자 (측벽 관통 · 챔버 밖 소켓)','발열장 2,200 · 램프 교체는 챔버를 열지 않는다');")
    w(f"L([.3,{n(EL)},.4],[{n(m(hc.x0_mm)-.15)},{n(EL/2)},0],M.dark,'HC-101 에어록 도어','AL-101 — 밀폐상실 시 셔터 닫힘 유지');")
    # 승강 포크 문형 ×4 (M-003) — LI·EX·GL·GU
    fk = mods["M-003"][1]
    portals = [(m(ld.x1_mm) - .42, "LI-101"), (m(ST["DL"].x0_mm) + .42, "EX-101"),
               (m(ST["GC"].x0_mm) - .42, "GL-101"), (m(ST["GC"].x1_mm) + .42, "GU-101")]
    w(f"// 승강 포크 문형 ×4 (M-003 {fk[0]}×{fk[1]}×{fk[2]}) — LI 투입 · EX 방출 · GL 냉각 적입 · GU 인출")
    for x, tag in portals:
        w(f"[-1,1].forEach(function(s){{L([.22,{n(m(fk[2]))},.22],[{n(x)},{n(m(fk[2])/2)},s*{n(m(fk[1])/2)}],M.steel,s<0?'{tag} 승강 포크 문형':null,s<0?'층선택 승강 · 2단 텔레스코픽 포크 · 두상보 EL {fk[2]:,}':null)}});")
        w(f"L([.22,.2,{n(m(fk[1]))}],[{n(x)},{n(m(fk[2])-.1)},0],M.steel,null);")
        w(f"L([{n(m(fk[0]))},.09,{n(m(fk[1])-.6)}],[{n(x)},{n(EL)},0],M.aluminum,null);")
    # DL-101 탠덤 셀
    dl = ST["DL"]; tbl_cx = m(dl.x0_mm) + .87 + H.const("CARRIER_L") / 2
    w(f"// DL-101 탠덤 분리 셀 — x {n(m(dl.x0_mm))}…{n(m(dl.x1_mm))} · VT-101 고정 진공테이블 중심 {n(tbl_cx)} · 이동 나이프")
    w(f"L([{n(H.const('CARRIER_L'))},.12,{n(H.const('CARRIER_W'))}],[{n(tbl_cx)},{n(EL-.06)},0],M.steel,'VT-101 6존 고정 진공테이블','상판 710 kg — 이 기계의 최중량 단품. 박리 추력 13.37 kN 을 앵커군 A8 넷이 받는다 · −65 kPa 6존');")
    w(f"[[-1.2,-.6],[-1.2,.6],[0,-.6],[0,.6],[1.2,-.6],[1.2,.6]].forEach(function(p,i){{MP(.16,.16,0,{n(EL-.12)},{n(tbl_cx)}+p[0],p[1],i===0?'DG-HK60C VT-101 진공테이블 기둥 6본 (벤더 앵커군 A8)':null);AB({n(tbl_cx)}+p[0],p[1],2,.16)}});")
    w(f"L([{n(m(LINE[0]))},.02,{n(m(LINE[1]))}],[{n(tbl_cx)},{n(EL+.01)},0],M.panel,'박리 중 패널','{LINE[0]:,} × {LINE[1]:,} · 계면 140 ℃ · HKB 180 ℃ / HKS 200 ℃');")
    rx0 = H.const("CRAIL_X0"); rx1 = H.const("CRAIL_X1"); rz = H.const("CRAIL_Z"); gy = H.const("CGY")
    w(f"// KG-101 갠트리 — 주행레일 x {n(rx0)}…{n(rx1)} · 레일 EL {n(rz)} · 문형 4본 (셀/EVA 가 그 아래로 옆으로 나간다)")
    w(f"[[{n(rx0)},{n(-gy)}],[{n(rx0)},{n(gy)}],[{n(rx1)},{n(-gy)}],[{n(rx1)},{n(gy)}]].forEach(function(p,i){{MP(.18,.18,0,{n(rz+.15)},p[0],p[1],i===0?'DG-HK60C KG-101 갠트리 주행 문형 4본 (벤더 앵커군 A7)':null);AB(p[0],p[1],3,.16)}});")
    w(f"[{n(-gy)},{n(gy)}].forEach(function(z){{L([{n(rx1-rx0)},.12,.14],[{n((rx0+rx1)/2)},{n(rz+.15)},z],M.steel,z<0?'KG-101 주행레일':null,z<0?'55 mm/s 박리 → 700 mm/s 복귀 · 랙피니언':null)}});")
    w(f"L([.32,.62,{n(2*gy+.2)}],[{n(tbl_cx-.9)},{n(rz+.52)},0],M.frame,'KG-101 크로스빔·나이프 캐리지','HKB-101/HKS-201 카세트 BC-201 · 칼끝 간격 300±2 · 웹은 이 밑으로 지난다');")
    w(f"L([.26,.9,{n(H.const('KNIFE_W'))}],[{n(tbl_cx-1.05)},{n(EL+.47)},0],M.orange,'HKB-101 백시트 개방 핫나이프 (카세트)','백시트/EVA 계면을 300 먼저 연다 — 180 ℃');")
    w(f"L([.26,.9,{n(H.const('KNIFE_W'))}],[{n(tbl_cx-.75)},{n(EL+.47)},0],M.red,'HKS-201 셀/EVA 분리 핫나이프 (카세트)','300 뒤를 따라가며 셀/EVA 를 유리에서 뗀다 — 200 ℃ · 생산보증 55 mm/s');")
    # 권취 WR-101 + 문형 + RH-201 모노레일 + 새들
    wrx = m(H.WINDER_X_MM)
    w(f"// WR-101 권취 (M-006) — 드럼 x {n(wrx)} EL 3.7 · RH-201 모노레일 EL {n(rh_z)} · 롤은 방책을 넘어 통로 밖 새들로")
    w(f"[-.75,.75].forEach(function(z){{L([.16,{n(rh_z-.3)},.16],[{n(wrx-.4)},{n((rh_z-.3)/2)},z],M.steel,z<0?'WR-101 권취 문형 2본':null,z<0?'문형 919 kg — 드럼·댄서·모노레일 시점을 받는다':null)}});")
    w(f"L([.9,.16,1.66],[{n(wrx-.4)},{n(rh_z-.22)},0],M.steel,null);")
    w(f"Ee(g,{n(H.const('WR_FULL_R'))},{n(H.const('ROLL_FACE'))},[{n(wrx)},3.7,0],M.rubber,'WR-101 백시트 만권 롤','Ø600 × 1,460 · {H.ROLL_MASS_KG} kg · {H.ROLL_PERIOD_H:g} h 마다 — 사람이 들 수 없다',[Math.PI/2,0,0]);")
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
    w(f"L([1.0,.4,.7],[{n(H.const('CKC_X'))},{n(H.const('CKC_Z'))},{n(lz(H.const('CKC_Y')*1000))}],M.orange,'KC-101 칼날 카세트 매거진 (갠트리 위 EL 3,300)','예열 1칸 · 냉각 1칸 · 자동교환 3.9 분 — 268 장마다 한 번보다 잦으면 계약 60 장/h 가 무너진다');")
    w(f"[-.3,.3].forEach(function(dz){{L([.1,{n(H.const('CKC_Z')-.2)},.1],[{n(H.const('CKC_X'))},{n((H.const('CKC_Z')-.2)/2)},{n(lz(H.const('CKC_Y')*1000))}+dz],M.steel,null)}});")
    # CE-201 횡인출 + CS-201 카트
    cex = [m(v) for v in H.CE_X_MM]; cey0 = m(H.const("CE_Y0") * 1000); cey1 = m(H.const("CE_Y1") * 1000); cez = m(H.CE_EL_MM)
    w(f"// CE-201 횡인출 컨베이어 (EL {H.CE_EL_MM:,}) → 외장 반출 터널 LC-003 → CS-201 평적 카트 (통로쪽 레인)")
    w(f"L([{n(cex[1]-cex[0])},.1,{n(-(cey1-cey0))}],[{n((cex[0]+cex[1])/2)},{n(cez)},{n(-(cey0+cey1)/2)}],M.dark,'CE-201 셀/EVA 횡인출 컨베이어','적층체 {LINE[0]:,} × {LINE[1]:,} 을 자르지 않고 통째로 옆으로 밀어 낸다 — 3.96 kg/장 · 238 kg/h');")
    w(f"[[{n(cex[0]+.3)},{n(-cey0-.2)}],[{n(cex[1]-.3)},{n(-cey0-.2)}],[{n(cex[0]+.3)},{n(-cey1+.2)}],[{n(cex[1]-.3)},{n(-cey1+.2)}]].forEach(function(p){{L([.1,{n(cez-.05)},.1],[p[0],{n((cez-.05)/2)},p[1]],M.steel,null)}});")
    w(f"L([{n(m(H.CART_L_MM))},.55,{n(m(H.CART_W_MM))}],[{n(m(H.CART_X_MM))},.275,{n(lz(H.CART_Y_MM))}],M.frame,'CS-201 셀/EVA 평적 카트','2,600 × 1,300 · 333 장 ≈ 5.6 h — 방책 게이트(ISO 14119)로 나간다 · 발주자 파쇄 (OI-08)');")
    w(f"for(var k=0;k<4;k++)L([{n(LINE[0]/1000)},.02,{n(LINE[1]/1000)}],[{n(m(H.CART_X_MM))},.56+k*.03,{n(lz(H.CART_Y_MM))}],M.panel,k===0?'평적 셀/EVA 적층체':null);")
    # GC-101 냉각 랙
    gc = ST["GC"]; gcw = m(mods["M-007"][1][1]); gch = m(mods["M-007"][1][2])
    w(f"// GC-101 {H.DECKS}단 유리 냉각 랙 — x {n(m(gc.x0_mm))}…{n(m(gc.x1_mm))} (M-007) · 140 → 60 ℃ 143 s 강제공랭 · 배기는 경계 덕트에 합류 (OI-16)")
    w(f"L([{n(m(gc.length_mm))},{n(gch)},{n(gcw)}],[{n(m(gc.cx_mm))},{n(gch/2)},0],M.frame,'DG-HK60C GC-101 냉각 랙 골조 (벤더 앵커군 A2)','{H.DECKS}단 강제공랭 h = 25 W/(m²·K) · 냉각 배기 26 kW 를 경계 덕트로 — 실내로 들이면 환기가 오른다');")
    for k in range(H.DECKS):
        dz = H.const("CDECK_Z0") + H.const("CDECK_DZ") * (k + .5)
        lab = s("G1…G5 냉각 데크") if k == 0 else "null"
        w(f"L([{n(m(gc.length_mm)-.8)},.04,{n(gcw-.4)}],[{n(m(gc.cx_mm))},{n(dz)},0],M.aluminum,{lab});")
    w(f"L([.4,.5,1.2],[{n(m(gc.cx_mm))},{n(gch+.25)},0],M.steel,'GC-101 냉각 팬 (배기 → 경계 덕트)','VIB-906');")
    # UL-101 반출 셔틀 + QI-301 + RJ-301 + 픽업 스테이션 + LC-002
    ul = ST["UL"]
    w(f"// UL-101 반출 셔틀 — x {n(m(ul.x0_mm))}…{n(m(ul.x1_mm))} · QI-301 검사 아치 · RJ-301 리젝트 (+y 벽쪽) · 유리 픽업 스테이션 (하류 끝)")
    w(f"L([{n(m(ul.length_mm))},.14,1.48],[{n(m(ul.cx_mm))},{n(EL-.07)},0],M.frame,'UL-101 반출 셔틀 · WO-303 인라인 계량','60 ℃ 이하로 식은 판유리 — GLASS_TAKEAWAY_READY 로 발주자 팔레트에 넘긴다');")
    w(f"[[{n(m(ul.x0_mm)+.3)},-.6],[{n(m(ul.x0_mm)+.3)},.6],[{n(m(ul.x1_mm)-.3)},-.6],[{n(m(ul.x1_mm)-.3)},.6]].forEach(function(p){{L([.1,{n(EL-.14)},.1],[p[0],{n((EL-.14)/2)},p[1]],M.steel,null)}});")
    w(f"[-1,1].forEach(function(s){{L([.16,2.9,.16],[{n(m(ul.x0_mm)+.36)},1.45,s*1.1],M.steel,s<0?'QI-301 검사 아치':null,s<0?'상부 RGB 카메라 — GLASS_CRACK · QI_FAIL · 불합격은 RJ-301 로':null)}});")
    w(f"L([.16,.16,2.36],[{n(m(ul.x0_mm)+.36)},2.85,0],M.steel,null);L([.5,.3,.3],[{n(m(ul.x0_mm)+.36)},2.6,0],M.dark,null);")
    w(f"L([1.3,.14,.9],[{n(m(ul.cx_mm)+.55)},{n(EL-.05)},-1.55],M.dark,'RJ-301 리젝트 횡셔틀','불합격 유리를 라인 밖(벽쪽)으로 뺀다');")
    w(f"L([1.1,1.0,.8],[{n(m(ul.cx_mm)+.55)},.5,-2.3],M.frame,null);")
    # 콘솔의 픽업 스테이션(x 19,100 · 팔레트 1,300)은 방책선 19,600 을 150 넘는다 — 벤더 방책
    # 밖 발주자 자리라 그렇다. 플랜트에서는 존 안에 둔다 (GLASS_PICKUP_IN_MM).
    px = m(GLASS_PICKUP_IN_MM)
    w(f"L([1.3,.14,1.34],[{n(px)},.11,0],M.aluminum,'발주자 인계 · 유리 반출 픽업 스테이션','팔레트 약 20장 · 20분마다 — 하류 끝단에서 지게차·AGV 가 받는다 (GLASS_TAKEAWAY_READY)');")
    w(f"for(var k=0;k<4;k++)L([1.22,.02,1.26],[{n(px)},.2+k*.05,0],M.panel,k===0?'회수 판유리':null,k===0?'{LINE[0]:,} × {LINE[1]:,} · 23.0 kg/장 · 전처리 → 유리제거까지 끝난 결과물':null);")
    w(f"[-.95,.95].forEach(function(z){{L([.08,1.95,.08],[{n(px+.36)},.975,z],M.sensor,z<0?'LC-002 안전 광커튼 (하류 개구)':null,z<0?'광축면 Y ±950 × Z 50–1,910 · 뮤팅 4점':null)}});")
    # 경계 인터페이스반 · 기초 패드 · MCC · 진공 스키드
    bjx = m(H.BJ_X_MM); bjz = lz(H.BJ_Y_MM)
    w(f"// 경계 인터페이스반 BJ-101/102 (x {n(bjx)} · 통로쪽 레인) · 기초 패드 P1~P3 · MCC M-011 · VU-101 스키드 M-012")
    w(f"L([1.5,.14,1.0],[{n(bjx)},.07,{n(bjz)}],M.dark,'DG-HK60C 기초 패드 P1~P3','P3 경계 인터페이스 — P1 MCC(EP-1 x 4,200) · P2 진공 스키드(EP-3 x 12,280) 와 함께 벤더 D-602 가 정한다');")
    w(f"[[-.38,'BJ-101 경계 인터페이스반','VOC_ABATE_READY · GLASS_TAKEAWAY_READY · CELL_TAKEAWAY_READY · 상류 브리지 핸드셰이크 UP_* — 발주자(플랜트) 신호는 전부 여기로'],[.38,'BJ-102 경계 안전회로 인터페이스반','IF_ESTOP_LOOP_OK — 안전회로는 공급범위 경계에서 끊기지 않는다 (SF-09)']].forEach(function(b){{L([.62,1.86,.52],[{n(bjx)}+b[0],1.07,{n(bjz)}],M.frame,b[1],b[2])}});")
    w(f"L([1.6,.14,.86],[4.2,.07,{n(lz(-3200))}],M.dark,null);L([1.6,3.1,.86],[4.2,1.69,{n(lz(-3200))}],M.frame,'DG-HK60C 전력·MCC·제어반 M-011','IR-DB1 100 · HK-DB2 30 · MCC-1 45 · AUX-DB 18 kW — 플랜트 피더 F9(IR)·F10(기구) 두 본이 여기로');")
    w(f"L([1.5,.14,.86],[12.28,.07,{n(lz(-3200))}],M.dark,null);L([1.5,2.5,.86],[12.28,1.39,{n(lz(-3200))}],M.steel,'DG-HK60C VU-101 진공·계장공기 스키드 M-012','드라이 스크류 진공펌프 2대(1 예비) −95 kPa · 리시버 400 L · VIB-905');")
    # 배기 헤더 → 경계 플랜지
    dy = lz(H.DUCT_Y_MM); dfx = m(H.DUCT_FLANGE_X_MM)
    w(f"// 배기 헤더 — 가열실·탠덤 분기 Ø400 → 본관 Ø460 → 경계 플랜지 Ø600 (x {n(dfx)} · EL {n(duct_el)}) → 발주자 후처리")
    w(f"[[{n(m(hc.cx_mm))},{n(hch)}],[{n(tbl_cx)},{n(rz+.8)}]].forEach(function(p,i){{Ee(g,.2,{n(duct_el)}-p[1],[p[0],(p[1]+{n(duct_el)})/2,{n(dy)}],M.steel,i===0?'HC-101 배기 지선 Ø400':null,i===0?'−30 Pa 차압 · VOC 는 경계 CEMS 로':null);L([.3,.16,.5],[p[0],p[1]+.08,{n(dy)}],M.steel,null)}});")
    w(f"Ee(g,.23,{n(dfx-m(hc.cx_mm))},[{n((m(hc.cx_mm)+dfx)/2)},{n(duct_el)},{n(dy)}],M.steel,'배기 본관 Ø460','헤더는 경계 플랜지까지만 — 팬(2×100 %)·스크러버·RTO 는 발주자 설비',[0,0,Math.PI/2]);")
    w(f"Ee(g,.3,.1,[{n(dfx)},{n(duct_el)},{n(dy)}],M.yellow,'경계 덕트 플랜지 Ø600 (EL {H.DUCT_FLANGE_EL_MM:,})','DUCT_DP_OK · 풍량 — 원격 준비 접점만 믿지 않고 여기서 잰다',[0,0,Math.PI/2]);")
    w(f"L([.14,{n(duct_el-.25)},.14],[{n(dfx-.4)},{n((duct_el-.25)/2)},{n(dy)}],M.steel,'배기 헤더 지주',null);")
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
