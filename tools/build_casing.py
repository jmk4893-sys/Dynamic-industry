# -*- coding: utf-8 -*-
"""외장 케이싱 3D 를 `casing.py` 에서 찍어 도면에 넣는다.

케이싱 형상을 손으로 쓰면 모델과 갈라진다 — 어깨선을 한 곳에서 고쳐도 3D 는
옛 높이로 남는다. 그래서 판·문·창·리턴·멀리언·마크를 전부 여기서 찍고,
도면의 `pvCase` 블록을 통째로 갈아 끼운다. 멱등이라 몇 번 돌려도 같다.

실행 (저장소 루트에서):
    PYTHONPATH=src python tools/build_casing.py
"""
import io, pathlib, re, sys
sys.path.insert(0, "src")
from pv_preprocess import casing as C

P = pathlib.Path("docs/drawings/pv-preprocess-plant.html")
X0, Z0 = 24750.0, 3550.0          # 월드 원점 (플랜트 좌표 mm)

def wx(mm): return round((mm - X0) / 1000.0, 4)
def wz(mm): return round((mm - Z0) / 1000.0, 4)
def m(mm):  return round(mm / 1000.0, 4)
def num(v):
    t = f"{v:.4f}".rstrip("0").rstrip(".")
    if t in ("", "-0"): t = "0"
    return t[1:] if t.startswith("0.") else ("-" + t[2:] if t.startswith("-0.") else t)

SUB = {"afu": "LFT-A/B · BFC 투입", "robot": "PT 정렬 · 반전 투입",
       "jbr": "정션박스 제거", "afr": "알루미늄 프레임 분리",
       "post": "CV · SG · GI 유리 검사", "buffer": "레시피 버퍼",
       "grm": "유리 제거"}
TAG = {"afu": "AFU-101", "robot": "RB-101", "jbr": "JBR-201", "afr": "AFR-101",
       "post": "SG-301", "buffer": "GBR-301", "grm": "GRM-401"}

out = []
w = out.append
w("var pvCase=new ce;pt.add(pvCase);pvCase.name='pvCase';")
w("(function(){")
w("var g=pvCase,L=function(a,b,c,d,e,f){return P(g,a,b,c,d,e,f)};")
w("// 메시마다 이름을 단다 — tools/check_casing_fit.mjs 가 껍질을 식별하는 근거다.")
w("var CN=function(m,n){m.name=n;return m;};")
w("// 이 블록은 손으로 쓰지 않는다 — src/pv_preprocess/casing.py 에서 찍는다.")
w(f"// 어깨 {C.SHOULDER_MM} · 리빌 {C.DATUM_MM} · 토우 {C.TOE_H_MM} · 이음매 {C.SEAM_MM}"
  f" · 반경 {C.RADIUS_MM} — 세 선이 전 구간 같은 높이다.")

body_h = m(C.DATUM_MM - C.TOE_H_MM)
body_y = m((C.DATUM_MM + C.TOE_H_MM) / 2)
assy   = m(C.PANEL_ASSY_MM)
cap_h  = m(C.SHOULDER_MM - C.DATUM_MM - C.REVEAL_H_MM)
cap_y  = m((C.SHOULDER_MM + C.DATUM_MM + C.REVEAL_H_MM) / 2)
rev_h  = m(C.REVEAL_H_MM)
rev_y  = m(C.DATUM_MM + C.REVEAL_H_MM / 2)
toe_h  = m(C.TOE_H_MM)
seam   = m(C.SEAM_MM)

for key in C.CASED_ZONES:
    x0, x1 = C.zone_span_mm(key)
    face = C.zone_face_mm(key)
    fz, zw = wz(face), m(C.zone_length_mm(key))
    bw = C.bay_width_mm(key)
    w(f"// ── {key} — 칸 {C.bay_count(key)} × {bw:g} mm")
    # 토우 리세스 · 리빌 홈 · 캡 밴드는 칸을 건너 **한 줄**이다. 선이 안 끊긴다.
    zc = num(wx((x0 + x1) / 2))
    # 토우는 그리지 않는다 — 바닥 100 mm 는 빈 그늘이다 (걸레받이가 기계를 파고들었다).
    w(f"CN(L([{num(zw)},{num(rev_h)},{num(m(C.REVEAL_D_MM))}],"
      f"[{zc},{num(rev_y)},{num(round(fz - m(C.REVEAL_D_MM)*1.5, 4))}],M.dark,null),"
      f"'case:{key}:reveal');")
    w(f"CN(L([{num(zw)},{num(cap_h)},{num(assy)}],"
      f"[{zc},{num(cap_y)},{num(round(fz - assy/2, 4))}],M.panel,null),"
      f"'case:{key}:cap');")
    # 판 한 칸씩
    for bay in C.bays(key):
        cx = num(wx(x0 + (bay.index + 0.5) * bw))
        pw = num(m(bw - C.SEAM_MM))
        if bay.kind == "window":
            w(f"CN(L([{pw},{num(body_h)},{num(m(C.GLAZING_T_MM))}],"
              f"[{cx},{num(body_y)},{num(round(fz - m(C.GLAZING_T_MM), 4))}],M.glazing,null),"
              f"'case:{key}:bay{bay.index}:window');")
        else:
            mat = "M.aluminum"
            w(f"CN(L([{pw},{num(body_h)},{num(assy)}],"
              f"[{cx},{num(body_y)},{num(round(fz - assy/2, 4))}],{mat},null),"
              f"'case:{key}:bay{bay.index}:{bay.kind}');")
        if bay.kind == "door":
            # 손잡이는 없다 — 리빌 밑의 손가락 홈이 문을 연다.
            w(f"CN(L([{num(m(bw*0.34))},{num(m(28))},{num(m(18))}],"
              f"[{cx},{num(m(C.DATUM_MM - 60))},{num(round(fz - m(18)*1.6, 4))}],M.dark,null),"
              f"'case:{key}:bay{bay.index}:pull');")
    # 멀리언 — 이음매 뒤에서 판을 잡고 하중을 존 베이스 빔으로 보낸다
    for i in range(C.bay_count(key) + 1):
        mx = num(wx(x0 + i * bw))
        w(f"CN(L([{num(seam*3)},{num(m(C.SHOULDER_MM))},{num(assy)}],"
          f"[{mx},{num(m(C.SHOULDER_MM/2))},{num(round(fz - assy/2, 4))}],M.dark,null),"
          f"'case:{key}:mullion{i}');")
    # 마크는 존마다 한 곳, 같은 높이 — 첫 막힌 칸
    first = next(b for b in C.bays(key) if b.kind == "solid")
    mcx = num(wx(x0 + (first.index + 0.5) * bw))
    w(f"CN(pvNamePlate(g,{num(m(bw*0.62))},[{mcx},{num(m(1750))},{num(round(fz - 0.006, 4))}],0,"
      f"'{TAG[key]}','{SUB[key]}','{key} 외장 케이싱 — 어깨 {C.SHOULDER_MM} · 리빌 {C.DATUM_MM} mm'),"
      f"'case:{key}:mark');")

# 존이 만나며 면이 물러서는 자리 — 리턴으로 닫는다
w("// 리턴 — 면이 물러서는 자리를 닫는다. 안 닫으면 껍질에 구멍이 난다.")
for up, down, at_x, step in C.returns_mm():
    zu, zd = wz(C.zone_face_mm(up)), wz(C.zone_face_mm(down))
    w(f"CN(L([{num(assy)},{num(m(C.SHOULDER_MM - C.TOE_H_MM))},{num(abs(zu - zd))}],"
      f"[{num(wx(at_x))},{num(m((C.SHOULDER_MM + C.TOE_H_MM)/2))},"
      f"{num(round((zu + zd) / 2, 4))}],M.aluminum,null),'case:{up}-{down}:return');")

# 플랜트 양 끝단
from pv_preprocess import layout as _L
# 하류 끝은 3D 격자가 존 표보다 뒤에 있다 — 그림에서만 그만큼 물러선다
# (casing.scene_end_shim_mm 참고. 격자가 등록되면 0 이라 식이 그대로 맞는다).
for key, at_x, label in (
        ("afu", C.zone_span_mm("afu")[0] - C.END_OFFSET_MM, "상류"),
        ("grm", C.zone_span_mm("grm")[1] + C.scene_end_shim_mm() + C.END_OFFSET_MM,
         "하류")):
    zone = next(z for z in _L.build_zones() if z.key == key)
    zu, zd = wz(zone.y1_mm), wz(zone.y0_mm)
    w(f"CN(L([{num(assy)},{num(m(C.SHOULDER_MM - C.TOE_H_MM))},{num(abs(zu - zd))}],"
      f"[{num(wx(at_x))},{num(m((C.SHOULDER_MM + C.TOE_H_MM)/2))},"
      f"{num(round((zu + zd) / 2, 4))}],M.aluminum,"
      f"'{label} 끝단 케이싱','플랜트 {label} 끝을 닫는 판 — 벽쪽은 발열 때문에 일부러 비워 둔다'),"
      f"'case:{key}:end');")
    # 끝단 판도 제 판틀이 있어야 바닥까지 하중 경로가 선다 — 가드 바깥면으로
    # 69 mm 물러나며 셀 끝 골조에서 떨어졌고, 하중경로 검사가 그것을 잡았다.
    inb = -1 if label == "상류" else 1
    p0, p1 = C.endpost_span_mm(key)
    w(f"CN(L([{num(assy)},{num(m(p1 - p0))},{num(m(120))}],"
      f"[{num(round(wx(at_x) - inb * assy, 4))},{num(m((p0 + p1) / 2))},"
      f"{num(round((zu + zd) / 2, 4))}],M.dark,null),'case:{key}:endpost');")

w("}());")
block = "\n".join(out)

import json as _json
import re as _re

s = io.open(P, encoding="utf-8").read()
# 도면이 읽는 CASING 리터럴도 모델에서 나온다 — 손으로 맞추면 반드시 갈라진다
_lit = "  var CASING = " + _json.dumps(C.summary(), ensure_ascii=False) + ";"
_pat = _re.compile(r"  var CASING = \{.*?\};")
assert len(_pat.findall(s)) == 1, "CASING 리터럴 앵커"
s = _pat.sub(lambda _m: _lit, s, count=1)
# 재질에 glazing 추가 (멱등)
if "glazing:new xo(" not in s:
    anchor = "guard:new xo({color:SC.brand,transparent:!0,opacity:.055,roughness:.06,metalness:.02,depthWrite:!1,side:bn})}"
    assert s.count(anchor) == 1, s.count(anchor)
    s = s.replace(anchor, anchor[:-1] + ",glazing:new xo({color:SC.rim,transparent:!0,"
                  "opacity:.20,roughness:.03,metalness:.02,depthWrite:!1,side:bn})}")

start = "var pvCase=new ce;pt.add(pvCase);"
if start in s:
    i = s.index(start)
    j = s.index("\n}());", i) + len("\n}());")
    s = s[:i] + block + s[j:]
else:
    anchor2 = "var pvDecal=new ce;pt.add(pvDecal);"
    assert s.count(anchor2) == 1
    s = s.replace(anchor2, block + "\n" + anchor2)

io.open(P, "w", encoding="utf-8").write(s)
# 검사기가 쓸 마운트 평면 — 판이 어느 부재 위에 앉는지. 단일 출처를 공유한다.
import json as _json
planes = {k: {"mount": round((C.MEASURED_FACE_MM[k] - Z0) / 1000.0, 4),
              "face": round((C.zone_face_mm(k) - Z0) / 1000.0, 4),
              "x0": round((C.zone_span_mm(k)[0] - X0) / 1000.0, 4),
              "x1": round((C.zone_span_mm(k)[1] - X0) / 1000.0, 4)}
          for k in C.CASED_ZONES}
planes["_limits"] = {"band": round((3550 + 3550 - Z0) / 1000.0, 4),
                     "maxEncroach": C.MAX_ENCROACH_MM / 1000.0}
pathlib.Path("out").mkdir(exist_ok=True)
io.open("out/casing-planes.json", "w", encoding="utf-8").write(
    _json.dumps(planes, ensure_ascii=False, indent=1))

print(f"케이싱 3D — 존 {len(C.CASED_ZONES)} · 칸 {len(C.all_bays())} · 멀리언 {C.mullion_count()} · {len(block.splitlines())}줄")
