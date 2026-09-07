# -*- coding: utf-8 -*-
"""JBR-201 박리 순간 클로즈업 — 정션박스가 실제로 떨어져 나오는 15 초.

3D 파생본은 이 셀이 움직이는 것을 보여 주고 상세도는 그 값을 편다. 그런데 정작
**정션박스가 떨어져 나오는 순간**은 3D 에서 보이지 않는다 — 칼날 팁 0.8 mm,
쐐기 12°, 접착 계면, POM 기준 슈, ±8 mm Z 플로팅이 전부 밀리미터 단위라 셀 전체를
담은 시점에서는 몇 픽셀이다.

이 화면은 그 구간만 두 배율로 그린다.

* **헤드 전폭** (±700 mm) — 좌·우 L 칼날 카세트가 ±610 에서 ±10 까지 들어와
  박스 밑에서 만나는 것.
* **계면 확대** (±60 mm) — 칼날 팁이 접착 계면을 파고드는 자리. 팁 두께·쐐기각·
  절입 깊이·기준 슈 접촉이 전부 실척이다.

**형상도 운동도 손으로 쓰지 않는다.** 부품 치수는 통합 설계도 3D 의 생성 호출에서
라벨로 찾아 읽고, 운동식은 같은 파일의 `wt()` 에서 상수를 그대로 뽑는다. 어느
하나라도 원본에서 사라지면 생성이 실패한다 — 화면이 조용히 옛 값으로 남는 대신.

    PYTHONPATH=src python tools/build_jbr_closeup.py

멱등이다. `tests/test_pv_jbr.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-jbr-closeup.html"

#: 이 화면이 다루는 JBR 로컬 시각 (s). 케이블 회수 직전부터 후검증 진입까지.
T_FROM, T_TO = 19.0, 38.0

#: 처음 보여 주는 시각 — 전단 한복판.
T_START = 26.0

#: 셀 그룹 y 오프셋 `be.position.y = pvJbDy = pvRollY - .98` (m).
CELL_Y = -0.075

#: 검출 박스 그룹의 높이 `Ar = new C(.28, 1.12, 0)` 의 y (m, be 기준).
BOX_Y = 1.12


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def mm(v: float) -> str:
    """m → mm 표기."""
    x = round(v * 1000, 2)
    return f"{x:,.2f}".rstrip("0").rstrip(".")


# ── 원본에서 읽기 ────────────────────────────────────────────────────────
def plant_text() -> str:
    return PLANT.read_text(encoding="utf-8")


def revision(text: str) -> str:
    return re.search(r"DRAWING_REVISION = '([^']+)'", text).group(1)


_CALL = re.compile(r"(?:P|Ee|bt)\(")


def _one(text: str, pattern: str, what: str) -> re.Match[str]:
    hits = list(re.finditer(pattern, text))
    if len(hits) != 1:
        raise SystemExit(f"✗ {what}: 앵커가 {len(hits)}곳 — 1곳이어야 한다")
    return hits[0]


def box_part(text: str, label: str) -> dict[str, object]:
    """`P(부모,[sx,sy,sz],[x,y,z],…,"라벨"…)` 를 라벨로 찾아 치수·자리를 읽는다."""
    marks = [m for m in re.finditer(re.escape('"' + label), text)]
    for m in marks:
        starts = [x.start() for x in _CALL.finditer(text, max(0, m.start() - 900), m.start())]
        if not starts:
            continue
        seg = text[starts[-1]:m.start()]
        hit = re.match(r"P\(\s*(\w+)\s*,\s*\[([^\]]*)\]\s*,\s*\[([^\]]*)\]", seg)
        if hit:
            return {"parent": hit.group(1),
                    "size": [_num(v) for v in hit.group(2).split(",")],
                    "at": [_num(v) for v in hit.group(3).split(",")]}
    raise SystemExit(f"✗ 3D 형상에서 '{label}' 의 P(…) 호출을 못 찾았다")


def cyl_part(text: str, label: str) -> dict[str, object]:
    """`Ee(부모, 반지름, 높이, [x,y,z], …, "라벨"…)`."""
    marks = [m for m in re.finditer(re.escape('"' + label), text)]
    for m in marks:
        starts = [x.start() for x in _CALL.finditer(text, max(0, m.start() - 900), m.start())]
        if not starts:
            continue
        seg = text[starts[-1]:m.start()]
        hit = re.match(r"Ee\(\s*(\w+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*\[([^\]]*)\]", seg)
        if hit:
            return {"parent": hit.group(1), "r": _num(hit.group(2)), "h": _num(hit.group(3)),
                    "at": [_num(v) for v in hit.group(4).split(",")]}
    raise SystemExit(f"✗ 3D 형상에서 '{label}' 의 Ee(…) 호출을 못 찾았다")


def _num(v: str) -> float:
    return float(v.strip())


def offset_part(text: str, label: str) -> dict[str, object]:
    """칼날·기준 슈처럼 x 가 `-g*0.13` 형태인 것 — 부호 계수를 따로 돌려준다."""
    marks = [m for m in re.finditer(re.escape('"' + label), text)]
    for m in marks:
        starts = [x.start() for x in _CALL.finditer(text, max(0, m.start() - 900), m.start())]
        if not starts:
            continue
        seg = text[starts[-1]:m.start()]
        hit = re.match(r"P\(\s*(\w+)\s*,\s*\[([^\]]*)\]\s*,\s*\[-g\*([\d.]+),([-\d.]+),([-\d.]+)\]", seg)
        if hit:
            return {"parent": hit.group(1),
                    "size": [_num(v) for v in hit.group(2).split(",")],
                    "dx": _num(hit.group(3)), "y": _num(hit.group(4)), "z": _num(hit.group(5))}
    raise SystemExit(f"✗ 3D 형상에서 '{label}' 의 -g*… 배치를 못 찾았다")


def motion(text: str) -> dict[str, object]:
    """`wt()` 안의 박리 구간 운동 상수 — 식을 그대로 읽는다."""
    blade = _one(text, r"let He=v\?me\(Se\(t,([\d.]+),([\d.]+)\)\):0,H=le\(([\d.]+),([\d.]+),He\)",
                 "칼날 개도")
    hold = _one(text, r"v&&t>=([\d.]+)&&t<([\d.]+)&&\(H=([\d.]+)\)", "칼날 닫힘 유지")
    reopen = _one(text, r"v&&t>=([\d.]+)&&\(H=le\(([\d.]+),([\d.]+),me\(Se\(t,[\d.]+,([\d.]+)\)\)\)\)",
                  "칼날 재개방")
    place = _one(text, r"let it=me\(Se\(t,([\d.]+),([\d.]+)\)\)", "헤드 Y 배치")
    grip = _one(text, r"let tt=de&&v\?me\(Se\(t,([\d.]+),([\d.]+)\)\)\*\(1-me\(Se\(t,([\d.]+),([\d.]+)\)\)\):0",
                "포획 그리퍼")
    drop = _one(text, r"U\.captureGripper\.position\.y=le\(0,(-[\d.]+),tt\)", "그리퍼 하강")
    cup = _one(text, r"U\.vacuumCup\.scale\.y=le\(1,([\d.]+),tt\)", "진공컵 압축")
    fing = _one(text, r"U\.captureFingers\[0\]\.rotation\.z=le\((-[\d.]+),([\d.]+),tt\)", "포획 손가락")
    float_ = _one(text, r"let Ue=de&&v&&t>=([\d.]+)&&t<([\d.]+)\?Math\.sin\(t\*([\d.]+)\+ue\*[\d.]+\)\*([\d.]+):0",
                  "Z 플로팅")
    stem = _one(text, r"U\.displacementStem\.scale\.y=1\+Math\.abs\(Ue\)\*(\d+)", "Z 변위센서 신장")
    lift = _one(text, r"ae=le\(([\d.]+),(-[\d.]+),me\(Se\(t,([\d.]+),([\d.]+)\)\)\),t>=([\d.]+)&&"
                      r"\(ae=le\((-[\d.]+),([\d.]+),me\(Se\(t,[\d.]+,([\d.]+)\)\)\)\)", "승강 플레이트")
    boxlift = _one(text, r"U\.group\.position\.set\(D\+se\.x,le\(Ar\.y,([\d.]+),Te\),se\.z\)", "박스 인양 높이")
    te = _one(text, r"let Te=me\(Se\(t,([\d.]+),([\d.]+)\)\)", "인양 구간")
    interface = _one(text, r"Bl\.visible=v&&t>=([\d.]+)&&t<([\d.]+),Ol\.opacity=le\(([\d.]+),([\d.]+),He\)",
                     "박리 계면 표시")
    return {
        "shear": [float(blade.group(1)), float(blade.group(2))],
        "openWide": float(blade.group(3)), "openShut": float(blade.group(4)),
        "hold": [float(hold.group(1)), float(hold.group(2)), float(hold.group(3))],
        "reopen": [float(reopen.group(1)), float(reopen.group(4))],
        "reopenTo": float(reopen.group(3)),
        "place": [float(place.group(1)), float(place.group(2))],
        "grip": [float(grip.group(1)), float(grip.group(2)), float(grip.group(3)), float(grip.group(4))],
        "gripDrop": float(drop.group(1)),
        "cupSquash": float(cup.group(1)),
        "finger": [float(fing.group(1)), float(fing.group(2))],
        "float": [float(float_.group(1)), float(float_.group(2)),
                  float(float_.group(3)), float(float_.group(4))],
        "stemGain": float(stem.group(1)),
        "descend": [float(lift.group(3)), float(lift.group(4)),
                    float(lift.group(1)), float(lift.group(2))],
        "raise": [float(lift.group(5)), float(lift.group(8)),
                  float(lift.group(6)), float(lift.group(7))],
        "boxTop": float(boxlift.group(1)),
        "boxLift": [float(te.group(1)), float(te.group(2))],
        "interface": [float(interface.group(1)), float(interface.group(2))],
        "interfaceOpacity": [float(interface.group(3)), float(interface.group(4))],
    }


def stages(text: str) -> list[dict[str, object]]:
    i = text.index("var Vt=40,gl=[")
    j = text.index("]", text.index("[", i) + 1)
    depth, k = 0, text.index("[", i)
    while k < len(text):
        if text[k] == "[":
            depth += 1
        elif text[k] == "]":
            depth -= 1
            if depth == 0:
                break
        k += 1
    rows = re.findall(r'\{name:"([^"]+)",start:([\d.]+),end:([\d.]+)\}', text[i:k + 1])
    return [{"name": n, "start": float(a), "end": float(b)} for n, a, b in rows]


def scenarios(text: str) -> list[dict[str, object]]:
    i = text.index("var hp={")
    depth, k = 0, text.index("{", i)
    while k < len(text):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    block = text[i:k + 1]
    out = []
    for key, body in re.findall(r'"([a-z-]+)":\{(.*?)\},?(?=(?:"[a-z-]+":\{)|\}$)', block, re.S):
        boxes = [{k2: float(v) for k2, v in re.findall(r"(\w+):(-?[\d.]+)", b)}
                 for b in re.findall(r"\{(x:[^}]*)\}", body)]
        out.append({"key": key,
                    "label": re.search(r'label:"([^"]*)"', body).group(1),
                    "plan": re.search(r'plan:"([^"]*)"', body).group(1),
                    "boxes": boxes})
    if len(out) != 4:
        raise SystemExit(f"✗ 검출 시나리오가 {len(out)}개 — 4개여야 한다")
    return out


def blade_spec(text: str) -> tuple[str, float, float]:
    """칼날 카세트의 사양 문장과 거기 적힌 팁 두께·쐐기각."""
    m = _one(text, r'"SKD11 교체형 칼날 카세트":null,"([^"]+)"', "칼날 사양")
    spec = m.group(1)
    tip = re.search(r"팁 ([\d.]+) mm", spec)
    wedge = re.search(r"([\d.]+)° 쐐기", spec)
    if not tip or not wedge:
        raise SystemExit(f"✗ 칼날 사양에서 팁·쐐기각을 못 읽었다: {spec}")
    return spec, float(tip.group(1)), float(wedge.group(1))


def model(text: str) -> dict[str, object]:
    """화면이 쓰는 값 전부 — 형상·운동·시각·시나리오."""
    parts = {
        "head": box_part(text, "독립 위치결정 제거 헤드"),
        "carrier": box_part(text, "좌측 L형 칼날 캐리어"),
        "lip": box_part(text, "L형 수직 포획턱"),
        "cassette": offset_part(text, "SKD11 교체형 칼날 카세트"),
        "shoe": offset_part(text, "스프링 POM 기"),
        "gripper": box_part(text, "진공·스프링 포획그리퍼"),
        "cup": cyl_part(text, "진공컵·체크밸브"),
        "compliance": box_part(text, "Z 플로팅 컴플라이언스 모듈"),
        "stem": box_part(text, "Z 변위센서"),
        "nozzle": box_part(text, "국소 파편흡입 노즐"),
        "toolId": box_part(text, "공구 ID·칼날 상태센서"),
        "yaw": box_part(text, "패시브 요 상태 포인터"),
        "plate": box_part(text, "3헤드 공통 승강 플레이트"),
        "panel": box_part(text, "태양광 패널"),
        "box": box_part(text, "비전 검출 정션박스"),
    }
    fingers = _one(text, r"let m=P\(l,\[([^\]]*)\],\[f\*([\d.]+),([\d.]+),0\]", "포획 손가락 형상")
    parts["finger"] = {"size": [_num(v) for v in fingers.group(1).split(",")],
                       "dx": _num(fingers.group(2)), "y": _num(fingers.group(3))}
    connector = _one(text, r"n=Ee\(e,([\d.]+),([\d.]+),\[0,(-[\d.]+),(-[\d.]+)\],M\.jbox", "박스 커넥터")
    parts["connector"] = {"r": _num(connector.group(1)), "h": _num(connector.group(2)),
                          "at": [0.0, -_num(connector.group(3)), -_num(connector.group(4))]}
    spec, tip, wedge = blade_spec(text)
    return {
        "rev": revision(text),
        "cellY": CELL_Y,
        "boxY": BOX_Y,
        "from": T_FROM, "to": T_TO, "start": T_START,
        "infeed": campaign.INFEED_S,
        "parts": parts,
        "motion": motion(text),
        "stages": [s for s in stages(text) if s["end"] > T_FROM and s["start"] < T_TO],
        "scenarios": scenarios(text),
        "bladeSpec": spec, "bladeTipMm": tip, "bladeWedgeDeg": wedge,
    }


# ── 화면 ────────────────────────────────────────────────────────────────
CSS = """
:root{color-scheme:light dark;
 --bg:#eef1f0;--card:#fff;--card2:#f6f8f7;--line:#d2d9d7;--line2:#b3bebb;
 --ink:#141f24;--ink2:#4a5c62;--ink3:#6e8087;--brand:#1b7cb8;--brand2:#4aa8e0;
 --brand-dim:#e3eff8;--accent:#fdca4a;--warn:#9a6b0e;--warn-bg:#fdf4de;
 --ok:#26714a;--red:#a52a30;
 --glass:#bcd3e2;--lam:#8fb3c9;--adhesive:#e08a3c;--jbox:#3f4d55;
 --steel:#9fb0bb;--blade:#3f8f5e;--pom:#4a5a63;--rubber:#7a6a62;--alu:#adbcc4;
 --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#111a1e;--card:#1b262b;--card2:#212d33;--line:#32444a;--line2:#45585f;
 --ink:#e5eeef;--ink2:#a2b7bc;--ink3:#798f96;--brand:#4aa8e0;--brand2:#6cc4f2;
 --brand-dim:#0f3149;--accent:#fdca4a;--warn:#e2a72c;--warn-bg:#3a2f12;
 --ok:#4fb27c;--red:#e2585f;
 --glass:#2d4a5e;--lam:#3f6178;--adhesive:#b46a2a;--jbox:#7c8e99;
 --steel:#5b6d78;--blade:#3f9f68;--pom:#6d7d86;--rubber:#8c7a70;--alu:#6d7f88;}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#111a1e;--card:#1b262b;--card2:#212d33;--line:#32444a;--line2:#45585f;
 --ink:#e5eeef;--ink2:#a2b7bc;--ink3:#798f96;--brand:#4aa8e0;--brand2:#6cc4f2;
 --brand-dim:#0f3149;--accent:#fdca4a;--warn:#e2a72c;--warn-bg:#3a2f12;
 --ok:#4fb27c;--red:#e2585f;
 --glass:#2d4a5e;--lam:#3f6178;--adhesive:#b46a2a;--jbox:#7c8e99;
 --steel:#5b6d78;--blade:#3f9f68;--pom:#6d7d86;--rubber:#8c7a70;--alu:#6d7f88;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:22px 16px 64px}
header.top{border-bottom:2px solid var(--line2);padding-bottom:12px;margin-bottom:18px}
.eyebrow{font-size:12px;letter-spacing:.10em;color:var(--ink3);text-transform:uppercase}
h1{margin:.28em 0 .1em;font-size:24px;line-height:1.25;text-wrap:balance}
h2{margin:26px 0 8px;font-size:17px;border-left:4px solid var(--brand);padding-left:10px}
p{margin:.45em 0;max-width:78ch}
p.lead{color:var(--ink2)}
.note{background:var(--card2);border:1px solid var(--line);border-left:3px solid var(--brand);
 border-radius:8px;padding:9px 13px;margin:10px 0;color:var(--ink2);font-size:14px}
.note.warn{border-left-color:var(--warn);background:var(--warn-bg)}
code{font-family:var(--mono);font-size:.9em;background:var(--brand-dim);padding:1px 5px;border-radius:4px}
.stage{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:10px;margin:12px 0}
canvas{display:block;width:100%;height:auto;border-radius:7px;background:transparent}
.viewhead{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;justify-content:space-between;
 margin:2px 4px 6px;color:var(--ink2);font-size:13px}
.viewhead b{color:var(--ink);font-size:14px}
.ctl{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0}
button,select{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line2);
 border-radius:8px;padding:5px 11px;cursor:pointer;min-height:34px}
button:hover,select:hover{background:var(--card2)}
button.on{background:var(--brand);border-color:var(--brand);color:#fff}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
label.f{display:flex;gap:6px;align-items:center;color:var(--ink2);font-size:13.5px}
input[type=range]{accent-color:var(--brand);width:100%}
.scrub{display:grid;grid-template-columns:1fr auto;gap:6px 12px;align-items:center;margin-top:6px}
.scrub .t{font-family:var(--mono);font-size:13px;color:var(--ink2);white-space:nowrap;
 font-variant-numeric:tabular-nums}
.readout{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin:12px 0}
.r{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:8px 11px}
.r span{display:block;font-size:11.5px;color:var(--ink3);letter-spacing:.02em}
.r b{display:block;font-size:16px;font-variant-numeric:tabular-nums;margin-top:1px}
.r.hot b{color:var(--brand)}
.r.alarm b{color:var(--red)}
.tw{overflow-x:auto;margin:9px 0;border:1px solid var(--line);border-radius:9px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
thead th{background:var(--card2);color:var(--ink2);font-weight:600;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.chip{font-size:12px;padding:3px 9px;border-radius:999px;background:var(--card2);
 border:1px solid var(--line);color:var(--ink2)}
.chip.on{background:var(--brand);border-color:var(--brand);color:#fff}
footer{margin-top:36px;padding-top:12px;border-top:1px solid var(--line);
 color:var(--ink3);font-size:12.5px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media (max-width:640px){.wrap{padding:14px 10px 48px}h1{font-size:20px}}
"""


def build() -> str:
    text = plant_text()
    M = model(text)
    data = json.dumps(M, ensure_ascii=False, separators=(",", ":"))
    t0, t1 = M["from"] + M["infeed"], M["to"] + M["infeed"]
    shear = M["motion"]["shear"]

    body = f"""<div class="wrap">
<header class="top">
  <div class="eyebrow">DYNAMIC INDUSTRY · JBR-201 · ENGINEERING BASE {esc(M['rev'])}</div>
  <h1>정션박스가 떨어져 나오는 순간</h1>
  <p class="lead">JBR-201 의 45 초 가운데 <b>로컬 {M['from']:g}–{M['to']:g} s</b>
  (플랜트 {t0:g}–{t1:g} s)만 떼어 두 배율로 그린다. 좌·우 L 칼날이
  ±{mm(M['motion']['openWide'])} 에서 ±{mm(M['motion']['openShut'])} 까지 들어와 박스 밑에서 만나는 것이
  위 그림, 칼날 팁이 접착 계면을 파고드는 자리가 아래 그림이다. 전단은
  <b>로컬 {shear[0]:g}–{shear[1]:g} s</b>({shear[1] - shear[0]:g} 초) 동안 일어난다.</p>
</header>

<div class="ctl" role="group" aria-label="재생 제어">
  <button id="play" type="button" class="on">일시정지</button>
  <button id="prev" type="button">이전 단계</button>
  <button id="next" type="button">다음 단계</button>
  <label class="f" for="speed">속도
    <select id="speed">
      <option value="0.05">0.05× · 초저속</option>
      <option value="0.15" selected>0.15×</option>
      <option value="0.4">0.4×</option>
      <option value="1">1× · 실시간</option>
    </select>
  </label>
  <label class="f" for="scen">검출 시나리오
    <select id="scen"></select>
  </label>
  <label class="f" for="yaw">요 각도
    <select id="yaw">
      <option value="recipe" selected>레시피 각도 (검출값)</option>
      <option value="fail">5.2° · ±3° 초과 (coverage 리젝트)</option>
    </select>
  </label>
  <label class="f"><input type="checkbox" id="dims" checked> 치수·라벨</label>
</div>
<div class="scrub">
  <input id="scrub" type="range" min="{M['from']:g}" max="{M['to']:g}" step="0.01"
         value="{M['start']:g}" aria-label="공정 위치">
  <div class="t"><span id="tlocal"></span> · <span id="tplant"></span></div>
</div>
<div class="chips" id="chips" aria-live="polite"></div>

<div class="stage">
  <div class="viewhead"><b>헤드 전폭 — 칼날 진입과 박스 분리</b>
    <span id="scale1"></span></div>
  <canvas id="wide" role="img"
    aria-label="좌우 L 칼날 카세트가 정션박스 밑으로 들어와 접착 계면을 전단하고 박스를 들어 올리는 단면"></canvas>
</div>

<div class="stage">
  <div class="viewhead"><b>계면 확대 — 칼날 팁·쐐기·기준 슈</b>
    <span id="scale2"></span></div>
  <canvas id="near" role="img"
    aria-label="칼날 팁이 백시트면 접착 계면을 파고드는 자리의 확대 단면"></canvas>
</div>

<div class="readout" id="readout"></div>

<h2>이 순간에 무엇이 움직이는가</h2>
<div class="tw"><table><thead><tr><th>동작</th><th>로컬 s</th><th>플랜트 s</th>
<th>값</th><th>식 (원본 <code>wt()</code>)</th></tr></thead><tbody id="motion"></tbody></table></div>

<h2>수직 스택업</h2>
<p class="lead">전단 자세(승강 플레이트 최저)에서 각 면의 높이. 셀 원점
<code>be.y = {mm(M['cellY'])} mm</code> 를 더한 월드 값이다.</p>
<div class="tw"><table><thead><tr><th>면</th><th>월드 H (mm)</th>
<th>패널 상면 기준 (mm)</th><th>비고</th></tr></thead><tbody id="stack"></tbody></table></div>

<h2>칼날</h2>
<p class="lead" id="bladespec"></p>

<footer>
  JBR-201 박리 순간 클로즈업 · {esc(M['rev'])} ·
  생성 <code>PYTHONPATH=src python tools/build_jbr_closeup.py</code><br>
  형상·운동 출처 — <code>docs/drawings/pv-preprocess-plant.html</code> 의 3D 생성 호출과
  <code>wt()</code>, 시각 출처 — <code>src/pv_preprocess/campaign.py</code>
</footer>
</div>
<script>
(function () {{
  'use strict';
  var M = {data};
  var P = M.parts, MO = M.motion;
  var css = getComputedStyle(document.documentElement);
  var cache = {{}};
  function C(name) {{
    if (cache[name] === undefined) cache[name] = css.getPropertyValue('--' + name).trim() || '#888';
    return cache[name];
  }}
  function recolor() {{ cache = {{}}; css = getComputedStyle(document.documentElement); }}
  if (window.matchMedia) {{
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    (mq.addEventListener ? mq.addEventListener.bind(mq, 'change') : mq.addListener.bind(mq))(function () {{
      recolor(); draw();
    }});
  }}
  if (window.MutationObserver) {{
    new MutationObserver(function () {{ recolor(); draw(); }})
      .observe(document.documentElement, {{ attributes: true, attributeFilter: ['data-theme', 'class', 'style'] }});
  }}

  // ── 운동식 — 원본 wt() 와 같은 보간 ─────────────────────────────────
  var BLADE_TIP = M.bladeTipMm / 1000, BLADE_WEDGE = M.bladeWedgeDeg;

  function sat(v) {{ return v < 0 ? 0 : v > 1 ? 1 : v; }}
  function span(t, a, b) {{ return sat((t - a) / (b - a)); }}
  function ease(x) {{ return x * x * (3 - 2 * x); }}          // smoothstep
  function step(t, a, b) {{ return ease(span(t, a, b)); }}
  function lerp(a, b, u) {{ return a + (b - a) * u; }}

  function bladeOpen(t) {{
    var h = lerp(MO.openWide, MO.openShut, step(t, MO.shear[0], MO.shear[1]));
    if (t >= MO.hold[0] && t < MO.hold[1]) h = MO.hold[2];
    if (t >= MO.reopen[0]) h = lerp(MO.reopenTo, MO.openWide, step(t, MO.reopen[0], MO.reopen[1]));
    return h;
  }}
  function plateY(t) {{
    var d = MO.descend, r = MO.raise;                 // [t0,t1,from,to]
    if (t < d[0]) return d[2];
    if (t < r[0]) return lerp(d[2], d[3], step(t, d[0], d[1]));
    if (t < r[1]) return lerp(r[2], r[3], step(t, r[0], r[1]));
    return r[3];
  }}
  function gripT(t) {{
    return step(t, MO.grip[0], MO.grip[1]) * (1 - step(t, MO.grip[2], MO.grip[3]));
  }}
  function floatY(t, head) {{
    if (t < MO.float[0] || t >= MO.float[1]) return 0;
    return Math.sin(t * MO.float[2] + head * 1.7) * MO.float[3];
  }}
  function boxY(t) {{
    if (t < MO.boxLift[0]) return M.boxY;
    return lerp(M.boxY, MO.boxTop, step(t, MO.boxLift[0], MO.boxLift[1]));
  }}
  function shearing(t) {{ return t >= MO.shear[0] && t < MO.shear[1]; }}

  // ── 상태 ────────────────────────────────────────────────────────────
  var t = M.start, playing = true, speed = 0.15, showDims = true;
  var scen = M.scenarios[0], yawMode = 'recipe';
  var el = function (id) {{ return document.getElementById(id); }};
  var wide = el('wide'), near = el('near');

  function activeBox() {{ return scen.boxes[Math.min(1, scen.boxes.length - 1)]; }}
  function yawRad() {{ return yawMode === 'fail' ? 5.2 * Math.PI / 180 : activeBox().angle; }}

  // ── 제도판 ──────────────────────────────────────────────────────────
  function board(cv, halfWidth, cx, cyWorld, halfHeight) {{
    var dpr = Math.min(2.5, window.devicePixelRatio || 1);
    var w = cv.clientWidth || 900;
    var h = Math.round(w * (halfHeight / halfWidth));
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    cv.style.height = h + 'px';
    var g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    var s = w / (halfWidth * 2);
    return {{
      g: g, w: w, h: h, s: s,
      X: function (x) {{ return (x - cx) * s + w / 2; }},
      Y: function (y) {{ return h / 2 - (y - cyWorld) * s; }},
      rect: function (x0, y0, x1, y1, fill, stroke) {{
        var a = this.X(Math.min(x0, x1)), b = this.Y(Math.max(y0, y1));
        var ww = Math.abs(x1 - x0) * s, hh = Math.abs(y1 - y0) * s;
        if (fill) {{ g.fillStyle = fill; g.fillRect(a, b, ww, hh); }}
        if (stroke) {{ g.strokeStyle = stroke; g.lineWidth = 0.9; g.strokeRect(a, b, ww, hh); }}
      }},
      line: function (x0, y0, x1, y1, colour, dash, wid) {{
        g.save(); g.strokeStyle = colour; g.lineWidth = wid || 0.9;
        g.setLineDash(dash || []); g.beginPath();
        g.moveTo(this.X(x0), this.Y(y0)); g.lineTo(this.X(x1), this.Y(y1));
        g.stroke(); g.restore();
      }},
      poly: function (pts, fill, stroke) {{
        g.beginPath();
        for (var i = 0; i < pts.length; i += 1) {{
          var px = this.X(pts[i][0]), py = this.Y(pts[i][1]);
          if (i === 0) g.moveTo(px, py); else g.lineTo(px, py);
        }}
        g.closePath();
        if (fill) {{ g.fillStyle = fill; g.fill(); }}
        if (stroke) {{ g.strokeStyle = stroke; g.lineWidth = 0.9; g.stroke(); }}
      }},
      text: function (x, y, s2, colour, align, size, dx, dy) {{
        g.fillStyle = colour; g.textAlign = align || 'center';
        g.font = (size || 11) + 'px -apple-system, system-ui, sans-serif';
        g.fillText(s2, this.X(x) + (dx || 0), this.Y(y) + (dy || 0));
      }},
      dimX: function (x0, x1, y, label, colour) {{
        var a = this.X(x0), b = this.X(x1), py = this.Y(y);
        g.save(); g.strokeStyle = colour; g.fillStyle = colour; g.lineWidth = 0.8;
        g.beginPath(); g.moveTo(a, py); g.lineTo(b, py); g.stroke();
        g.beginPath(); g.moveTo(a, py - 4); g.lineTo(a, py + 4);
        g.moveTo(b, py - 4); g.lineTo(b, py + 4); g.stroke();
        g.textAlign = 'center'; g.font = '10.5px ui-monospace, monospace';
        g.fillText(label, (a + b) / 2, py - 5); g.restore();
      }},
      dimY: function (y0, y1, x, label, colour) {{
        var a = this.Y(y0), b = this.Y(y1), px = this.X(x);
        g.save(); g.strokeStyle = colour; g.fillStyle = colour; g.lineWidth = 0.8;
        g.beginPath(); g.moveTo(px, a); g.lineTo(px, b); g.stroke();
        g.beginPath(); g.moveTo(px - 4, a); g.lineTo(px + 4, a);
        g.moveTo(px - 4, b); g.lineTo(px + 4, b); g.stroke();
        g.textAlign = 'left'; g.font = '10.5px ui-monospace, monospace';
        g.fillText(label, px + 6, (a + b) / 2 + 3); g.restore();
      }}
    }};
  }}

  // ── 한 장면의 좌표 계산 ─────────────────────────────────────────────
  function pose(t) {{
    var ae = plateY(t), H = bladeOpen(t), tt = gripT(t), fl = floatY(t, 1);
    var base = M.cellY + ae;                       // 승강 플레이트가 실은 프레임의 y 기준
    var b = P.box, bx = activeBox();
    return {{
      ae: ae, H: H, tt: tt, fl: fl, base: base,
      panelTop: M.cellY + P.panel.at[1] + P.panel.size[1] / 2,
      panelBot: M.cellY + P.panel.at[1] - P.panel.size[1] / 2,
      boxCy: M.cellY + boxY(t),
      boxH: b.size[1], boxW: b.size[0],
      bondT: Math.max(0, (M.cellY + M.boxY - b.size[1] / 2) * -1
               + (M.cellY + P.panel.at[1] + P.panel.size[1] / 2)),
      cassetteY: base + P.cassette.y + fl,
      cassetteT: P.cassette.size[1],
      cassetteW: P.cassette.size[0],
      shoeY: base + P.shoe.y + fl,
      shoeT: P.shoe.size[1],
      shoeW: P.shoe.size[0],
      carrierY: base + P.carrier.at[1] + fl,
      lipY: base + P.lip.at[1] + fl,
      gripY: base + P.gripper.at[1] + lerp(0, MO.gripDrop, tt),
      cupY: base + P.cup.at[1] + lerp(0, MO.gripDrop, tt),
      cupSquash: lerp(1, MO.cupSquash, tt),
      fingerY: base + P.finger.y + lerp(0, MO.gripDrop, tt),
      plateBot: base + P.plate.at[1] - P.plate.size[1] / 2,
      yaw: shearing(t) ? yawRad() : 0,
      angleOver: yawMode === 'fail'
    }};
  }}

  function cassetteSpan(p, sign) {{
    // 캐리어는 ±H, 카세트는 캐리어에서 -g*dx (g = 좌 −1 / 우 +1)
    var centre = sign * p.H - sign * P.cassette.dx;
    return [centre - p.cassetteW / 2, centre + p.cassetteW / 2];
  }}
  function shoeSpan(p, sign) {{
    var centre = sign * p.H - sign * P.shoe.dx;
    return [centre - p.shoeW / 2, centre + p.shoeW / 2];
  }}

  // ── 그리기 ──────────────────────────────────────────────────────────
  function drawScene(bd, p, wideView, tipX) {{
    var g = bd.g, ink = C('ink'), ink2 = C('ink2'), ink3 = C('ink3'), line = C('line2');
    // 지지정반 · 패널
    bd.rect(-1.2, p.panelBot - 0.06, 1.2, p.panelBot, C('steel'), line);
    bd.rect(-1.2, p.panelBot, 1.2, p.panelTop, C('glass'), line);
    bd.line(-1.2, p.panelTop - 0.004, 1.2, p.panelTop - 0.004, C('lam'), [], 1.6);
    // 스프링 손가락 — 박스 발자국 안(±120)이라 박스보다 먼저 그린다.
    [-1, 1].forEach(function (s) {{
      var fa = lerp(MO.finger[0], MO.finger[1], p.tt) * s;
      var fx = s * P.finger.dx, fy = p.fingerY;
      g.save();
      g.translate(bd.X(fx), bd.Y(fy)); g.rotate(-fa);
      g.fillStyle = C('accent'); g.strokeStyle = line; g.lineWidth = 0.8;
      var fw = P.finger.size[0] * bd.s, fh = P.finger.size[1] * bd.s;
      g.fillRect(-fw / 2, -fh / 2, fw, fh); g.strokeRect(-fw / 2, -fh / 2, fw, fh);
      g.restore();
    }});

    // 정션박스 (요 회전은 단면에서 상면 기울기로 보인다)
    var by = p.boxCy, half2 = p.boxH / 2, tilt = Math.tan(p.yaw) * (p.boxW / 2);
    bd.poly([[-p.boxW / 2, by - half2], [p.boxW / 2, by - half2],
             [p.boxW / 2, by + half2 + tilt], [-p.boxW / 2, by + half2 - tilt]],
            C('jbox'), C('ink'));
    // 진공컵 · 그리퍼
    var cupH = P.cup.h * p.cupSquash, cupR = P.cup.r;
    bd.rect(-cupR, p.cupY - cupH / 2, cupR, p.cupY + cupH / 2, C('rubber'), line);
    bd.rect(-P.gripper.size[0] / 2, p.gripY - P.gripper.size[1] / 2,
            P.gripper.size[0] / 2, p.gripY + P.gripper.size[1] / 2, C('alu'), line);

    // 좌·우 칼날 조립 (캐리어 · 포획턱 · 카세트 · POM 슈)
    [-1, 1].forEach(function (s) {{
      var cs = cassetteSpan(p, s), ss = shoeSpan(p, s);
      var carrierX = s * p.H;
      bd.rect(carrierX - P.carrier.size[0] / 2, p.carrierY - P.carrier.size[1] / 2,
              carrierX + P.carrier.size[0] / 2, p.carrierY + P.carrier.size[1] / 2,
              C('steel'), line);
      bd.rect(carrierX - P.lip.size[0] / 2, p.lipY - P.lip.size[1] / 2,
              carrierX + P.lip.size[0] / 2, p.lipY + P.lip.size[1] / 2, C('accent'), line);
      bd.rect(ss[0], p.shoeY - p.shoeT / 2, ss[1], p.shoeY + p.shoeT / 2, C('pom'), C('ink'));
      // 카세트 — 몸체와 갈린 쐐기를 나눠 그린다 (팁·쐐기각은 사양 문장에서 온다)
      var tip = BLADE_TIP, wedge = BLADE_WEDGE * Math.PI / 180;
      var inner = s < 0 ? cs[1] : cs[0], outer = s < 0 ? cs[0] : cs[1];
      var away = outer > inner ? 1 : -1;                       // 팁에서 몸체 쪽
      var back = inner + away * (p.cassetteT - tip) / Math.tan(wedge);
      bd.rect(back, p.cassetteY - p.cassetteT / 2, outer, p.cassetteY + p.cassetteT / 2,
              C('blade'), line);
      bd.poly([[back, p.cassetteY - p.cassetteT / 2], [inner, p.cassetteY - tip / 2],
               [inner, p.cassetteY + tip / 2], [back, p.cassetteY + p.cassetteT / 2]],
              C('blade'), line);
    }});

    // 접착 계면 — 두 칼날 팁 **사이**가 아직 붙어 있는 구간이다. 팁이 지나간 자리는
    // 떨어진 것이라 옅게 남는다. 박스·슈가 이 자리를 덮으므로 맨 위에 얹는다.
    var bond = p.panelTop - p.bondT, half = p.boxW / 2;
    var lt = cassetteSpan(p, -1)[1], rt = cassetteSpan(p, 1)[0];
    g.save(); g.globalAlpha = 0.28;
    bd.rect(-half, bond, half, p.panelTop, C('adhesive'), null);
    g.restore();
    var a0 = Math.max(-half, Math.min(half, lt)), a1 = Math.min(half, Math.max(-half, rt));
    if (a1 > a0) bd.rect(a0, bond, a1, p.panelTop, C('adhesive'), C('ink'));

    if (wideView) {{
      bd.rect(-P.plate.size[0] / 2, p.plateBot, P.plate.size[0] / 2, p.plateBot + P.plate.size[1],
              C('alu'), line);
      if (showDims) {{
        bd.dimX(-p.H, p.H, p.carrierY + P.carrier.size[1] / 2 + 0.020,
                (p.H * 2000).toFixed(0) + ' 캐리어 간격', ink3);
        var l = cassetteSpan(p, -1), r = cassetteSpan(p, 1);
        bd.dimX(l[1], r[0], p.panelBot - 0.034,
                ((r[0] - l[1]) * 1000).toFixed(0) + ' 칼날 간극', ink3);
        bd.dimX(-p.boxW / 2, p.boxW / 2, p.boxCy + p.boxH / 2 + 0.055,
                (p.boxW * 1000).toFixed(0) + ' 박스', ink3);
        bd.text(0, p.boxCy, 'JBOX', '#fff', 'center', 12, 0, 4);
        bd.text(-0.72, p.panelTop - 0.026, '패널 (유리면 아래 · 백시트 위)', ink2, 'left', 11);
        bd.text(-0.72, p.plateBot + P.plate.size[1] / 2, '3헤드 공통 승강 플레이트', ink, 'left', 11, 0, 4);
      }}
    }} else if (showDims) {{
      var x0 = (tipX === undefined ? -p.boxW / 2 : tipX);
      bd.line(x0 - 0.055, p.panelTop, x0 + 0.055, p.panelTop, ink3, [4, 3], 0.9);
      bd.dimY(p.panelTop, p.cassetteY - p.cassetteT / 2, x0 - 0.030,
              ((p.cassetteY - p.cassetteT / 2 - p.panelTop) * 1000).toFixed(1) + ' 칼날 하면', ink);
      bd.dimY(p.panelTop, p.boxCy - p.boxH / 2, x0 + 0.026,
              ((p.boxCy - p.boxH / 2 - p.panelTop) * 1000).toFixed(1) + ' 박스 하면', ink);
      bd.text(x0 - 0.046, p.panelTop, '패널 상면 (기준)', ink, 'left', 10.5, 0, 13);
      bd.text(x0 - 0.046, p.cassetteY + p.cassetteT / 2, 'SKD11 카세트 '
              + (p.cassetteT * 1000).toFixed(0) + ' t · 팁 ' + M.bladeTipMm
              + ' · 쐐기 ' + M.bladeWedgeDeg + '°', C('blade'), 'left', 10.5, 0, -4);
      bd.text(x0 + 0.046, p.panelTop - 0.0038, '아직 붙어 있는 접착', ink, 'right', 10.5);
      if (x0 > -p.boxW / 2) bd.text(x0 + 0.046, p.boxCy, 'JBOX', ink, 'right', 11);
      if (p.shoeY + p.shoeT / 2 < p.panelTop) {{
        bd.text(x0 - 0.046, p.shoeY, 'POM 기준 슈가 패널 상면 아래 '
                + ((p.panelTop - p.shoeY - p.shoeT / 2) * 1000).toFixed(1) + ' mm',
                C('red'), 'left', 10.5, 0, 3);
      }}
    }}
  }}

  function draw() {{
    var p = pose(t);
    // 위 그림 — 승강 플레이트 밑면부터 지지정반까지가 프레임을 채우게 잡는다.
    var hi = p.plateBot + 0.035, lo = p.panelBot - 0.085;
    var b1 = board(wide, 0.74, 0, (hi + lo) / 2, Math.max(0.165, (hi - lo) / 2));
    drawScene(b1, p, true);
    el('scale1').textContent = '가로 ±740 mm · 1 px ≈ ' + (1000 / b1.s).toFixed(2) + ' mm';
    // 아래 그림 — 좌측 칼날의 팁을 따라간다. 팁이 박스 밑으로 들어가면 계면에 머문다.
    var cs = cassetteSpan(p, -1);
    var tipX = cs[1];                       // 좌측 카세트의 안쪽 끝 = 팁
    var b2 = board(near, 0.054, tipX, p.panelTop - 0.0155, 0.036);
    drawScene(b2, p, false, tipX);
    el('scale2').textContent = '가로 ±54 mm · 1 px ≈ ' + (1000 / b2.s).toFixed(3)
      + ' mm · 좌측 칼날 팁 추종 (x = ' + (tipX * 1000).toFixed(0) + ' mm)';
    paint(p);
  }}

  // ── 판독값 ──────────────────────────────────────────────────────────
  function stageAt(t) {{
    for (var i = 0; i < M.stages.length; i += 1) {{
      if (t >= M.stages[i].start && t < M.stages[i].end) return M.stages[i];
    }}
    return M.stages[M.stages.length - 1];
  }}
  function bonded(p) {{
    var h = p.boxW / 2, a = Math.max(-h, Math.min(h, cassetteSpan(p, -1)[1]));
    var b = Math.min(h, Math.max(-h, cassetteSpan(p, 1)[0]));
    return Math.max(0, (b - a) * 1000);
  }}

  function row(label, value, cls) {{
    return '<div class="r ' + (cls || '') + '"><span>' + label + '</span><b>' + value + '</b></div>';
  }}
  function paint(p) {{
    el('tlocal').textContent = '로컬 ' + t.toFixed(2) + ' s';
    el('tplant').textContent = '플랜트 ' + (t + M.infeed).toFixed(2) + ' s';
    el('scrub').value = t.toFixed(2);
    var st = stageAt(t), sh = shearing(t);
    el('chips').innerHTML =
      '<span class="chip on">' + st.name + '</span>' +
      '<span class="chip' + (sh ? ' on' : '') + '">전단 ' + MO.shear[0] + '–' + MO.shear[1] + ' s</span>' +
      '<span class="chip' + (p.tt > 0.02 ? ' on' : '') + '">진공 포획</span>' +
      '<span class="chip' + (t >= MO.boxLift[0] && t < MO.boxLift[1] ? ' on' : '') + '">인양</span>';
    var l = cassetteSpan(p, -1), r = cassetteSpan(p, 1);
    var cut = (p.cassetteY - p.cassetteT / 2 - p.panelTop) * 1000;
    el('readout').innerHTML =
      row('캐리어 개도', '±' + (p.H * 1000).toFixed(0) + ' mm', sh ? 'hot' : '') +
      row('칼날 간극', ((r[0] - l[1]) * 1000).toFixed(0) + ' mm', sh ? 'hot' : '') +
      row('칼날 절입 (패널 상면 기준)', cut.toFixed(1) + ' mm') +
      row('Z 플로팅', (p.fl * 1000).toFixed(2) + ' mm', Math.abs(p.fl) > 0.0001 ? 'hot' : '') +
      row('Z 변위센서 신장', '×' + (1 + Math.abs(p.fl) * MO.stemGain).toFixed(3)) +
      row('패시브 요', (p.yaw * 180 / Math.PI).toFixed(2) + '°',
          p.angleOver && sh ? 'alarm' : '') +
      row('진공컵 압축', ((1 - p.cupSquash) * 100).toFixed(0) + ' %', p.tt > 0.02 ? 'hot' : '') +
      row('남은 접착 폭', bonded(p).toFixed(0) + ' / ' + (p.boxW * 1000).toFixed(0) + ' mm',
          bonded(p) <= 0 ? 'alarm' : sh ? 'hot' : '') +
      row('박스 중심 (패널 상면 기준)', ((p.boxCy - p.panelTop) * 1000).toFixed(0) + ' mm',
          t >= MO.boxLift[0] ? 'hot' : '');
  }}

  // ── 표 ──────────────────────────────────────────────────────────────
  function fill() {{
    var rows = [
      ['헤드 Y 자동배치', MO.place, '검출 Y 좌표로 이동', 'it = smoothstep(t, ' + MO.place[0] + ', ' + MO.place[1] + ')'],
      ['칼날 하강', [MO.descend[0], MO.descend[1]],
       (MO.descend[2] * 1000).toFixed(0) + ' → ' + (MO.descend[3] * 1000).toFixed(0) + ' mm',
       'ae = lerp(' + MO.descend[2] + ', ' + MO.descend[3] + ', smoothstep(t, ' + MO.descend[0] + ', ' + MO.descend[1] + '))'],
      ['진공 포획', [MO.grip[0], MO.grip[1]],
       '그리퍼 ' + (MO.gripDrop * 1000).toFixed(0) + ' mm 하강 · 컵 ' + ((1 - MO.cupSquash) * 100).toFixed(0) + ' % 압축',
       'tt = smoothstep(t, ' + MO.grip[0] + ', ' + MO.grip[1] + ')'],
      ['전단 (박리)', MO.shear,
       '캐리어 ±' + (MO.openWide * 1000).toFixed(0) + ' → ±' + (MO.openShut * 1000).toFixed(0) + ' mm',
       'H = lerp(' + MO.openWide + ', ' + MO.openShut + ', smoothstep(t, ' + MO.shear[0] + ', ' + MO.shear[1] + '))'],
      ['Z 플로팅 (채터)', [MO.float[0], MO.float[1]],
       '±' + (MO.float[3] * 1000).toFixed(1) + ' mm · ' + (MO.float[2] / (2 * Math.PI)).toFixed(2) + ' Hz',
       'Ue = sin(t·' + MO.float[2] + ' + i·1.7) × ' + MO.float[3]],
      ['접착 계면 표시', MO.interface,
       '불투명도 ' + MO.interfaceOpacity[0] + ' → ' + MO.interfaceOpacity[1],
       'Ol.opacity = lerp(' + MO.interfaceOpacity[0] + ', ' + MO.interfaceOpacity[1] + ', He)'],
      ['동시 인양', MO.boxLift,
       (MO.raise[2] * 1000).toFixed(0) + ' → ' + (MO.raise[3] * 1000).toFixed(0) + ' mm · 박스 ' +
       (M.boxY * 1000).toFixed(0) + ' → ' + (MO.boxTop * 1000).toFixed(0) + ' mm',
       'ae = lerp(' + MO.raise[2] + ', ' + MO.raise[3] + ', smoothstep(t, ' + MO.raise[0] + ', ' + MO.raise[1] + '))'],
      ['칼날 재개방', MO.reopen,
       '±' + (MO.reopenTo * 1000).toFixed(0) + ' → ±' + (MO.openWide * 1000).toFixed(0) + ' mm',
       'H = lerp(' + MO.reopenTo + ', ' + MO.openWide + ', smoothstep(t, ' + MO.reopen[0] + ', ' + MO.reopen[1] + '))']
    ];
    el('motion').innerHTML = rows.map(function (r) {{
      return '<tr><td>' + r[0] + '</td><td class="num">' + r[1][0] + ' – ' + r[1][1] + '</td>' +
        '<td class="num">' + (r[1][0] + M.infeed) + ' – ' + (r[1][1] + M.infeed) + '</td>' +
        '<td>' + r[2] + '</td><td><code>' + r[3] + '</code></td></tr>';
    }}).join('');

    var p = pose(MO.shear[0] + 0.5);
    var faces = [
      ['승강 플레이트 하면', p.plateBot, '3헤드가 매달린 기준면'],
      ['칼날 캐리어 중심', p.carrierY, 'L 칼날 카세트를 무는 자리'],
      ['칼날 카세트 상면', p.cassetteY + p.cassetteT / 2, ''],
      ['칼날 카세트 하면', p.cassetteY - p.cassetteT / 2, '이 면이 접착 계면을 지난다'],
      ['정션박스 상면', p.boxCy + p.boxH / 2, '진공컵이 무는 면'],
      ['패널 상면 (백시트)', p.panelTop, '기준면'],
      ['정션박스 하면', p.boxCy - p.boxH / 2, '패널 상면보다 아래 — 그 차이가 접착 두께다'],
      ['POM 기준 슈 하면', p.shoeY - p.shoeT / 2, '칼날 높이를 기계적으로 정하는 면'],
      ['패널 하면 (유리)', p.panelBot, '']
    ];
    el('stack').innerHTML = faces.map(function (f) {{
      var rel = (f[1] - p.panelTop) * 1000;
      return '<tr><td>' + f[0] + '</td><td class="num">' + (f[1] * 1000).toFixed(1) + '</td>' +
        '<td class="num">' + (rel >= 0 ? '+' : '') + rel.toFixed(1) + '</td><td>' + f[2] + '</td></tr>';
    }}).join('');
    el('bladespec').textContent = M.bladeSpec;

    var sel = el('scen');
    sel.innerHTML = M.scenarios.map(function (s, i) {{
      return '<option value="' + i + '">' + s.label + '</option>';
    }}).join('');
  }}

  // ── 조작 ────────────────────────────────────────────────────────────
  function setPlaying(v) {{
    playing = v;
    el('play').textContent = v ? '일시정지' : '재생';
    el('play').classList.toggle('on', v);
  }}
  el('play').addEventListener('click', function () {{ setPlaying(!playing); }});
  el('speed').addEventListener('change', function () {{ speed = Number(this.value); }});
  el('dims').addEventListener('change', function () {{ showDims = this.checked; draw(); }});
  el('scen').addEventListener('change', function () {{ scen = M.scenarios[Number(this.value)]; draw(); }});
  el('yaw').addEventListener('change', function () {{ yawMode = this.value; draw(); }});
  el('scrub').addEventListener('input', function () {{
    t = Number(this.value); setPlaying(false); draw();
  }});
  el('prev').addEventListener('click', function () {{
    var st = stageAt(t); setPlaying(false);
    t = (t - st.start > 0.15) ? st.start : Math.max(M.from, st.start - 0.001);
    t = Math.max(M.from, stageAt(t).start); draw();
  }});
  el('next').addEventListener('click', function () {{
    var st = stageAt(t); setPlaying(false);
    t = Math.min(M.to, st.end + 0.001); draw();
  }});
  window.addEventListener('resize', draw);

  var last = 0;
  function frame(now) {{
    if (playing) {{
      if (last) {{
        t += (now - last) / 1000 * speed;
        if (t >= M.to) t = M.from;
      }}
      last = now; draw();
    }} else {{ last = now; }}
    requestAnimationFrame(frame);
  }}
  fill(); draw();
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) setPlaying(false);
  requestAnimationFrame(frame);
}}());
</script>
"""
    return ("<!doctype html>\n"
            "<!-- JBR-201 박리 순간 클로즈업: tools/build_jbr_closeup.py 가 통합 설계도의\n"
            "     3D 생성 호출과 wt() 에서 찍는다. 손으로 고치지 않는다. -->\n"
            '<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            "<title>정션박스 박리 순간</title>\n"
            '<meta name="description" content="JBR-201 이 정션박스를 떼어 내는 15 초를 헤드 전폭과 '
            '접착 계면 두 배율로 그린 실척 단면 — 칼날 개도·절입·Z 플로팅·진공 포획·인양을 '
            '원본 운동식 그대로 재생한다.">\n'
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
