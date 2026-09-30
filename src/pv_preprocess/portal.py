# -*- coding: utf-8 -*-
"""BFC-101 포탈의 하중 경로 — 220 mm 편심을 어디로 흘릴 것인가 (OI-04).

미결 항목은 이렇게 적혀 있다: "링 회전 평면이 포탈 기둥 중심에서 220 mm
떨어져 있다. 그만큼 기둥에 비틀림이 걸리는데, 그 하중을 베어링 하우징으로
받을지 가새로 받을지가 도면에 없다. 둘 다 성립하고 무게·정비성이 다르다."

편심은 지어낸 값이 아니다. 기둥은 축방향 ∓1,600 에 서고 링 평면은 ∓1,380 에
있다 — 차가 정확히 220 이다. 그 40 mm 남는 틈(링 관 바깥 1,470 과 기둥 안면
1,510) 때문에 **기둥을 링 평면으로 당기는 안이 성립하지 않는다**는 것도 이미
기록돼 있다. 그래서 편심은 없앨 수 없고, 흘려보낼 길만 고르면 된다.

**푸는 도구는 3차원이어야 한다.** `ring.py` 의 평면 프레임에는 비틀림
자유도가 없어 이 물음에 답할 수 없다. `frame3.py` 가 그 요소를 세우고,
닫힌 해 넷으로 검증한다.

**먼저 걸린 것 — 부품표에 받는 부재가 없다.**

제작 도면집에는 지지 롤러 블록 하우징(BFC-BB-01, 220 × 260 × 300)이 있고
조립 순서는 그것을 "크로스빔 탭에" 붙이라고 적어 두었다. 그런데 크로스빔은
기둥 위(높이 3,480)에 얹히고 롤러는 링 밑(약 2,510)에 있다 — 970 mm 아래다.
하우징 300 으로는 못 닿는다. 즉 **롤러를 기둥까지 잇는 부재가 부품표에도
3D 에도 없다.** `check_load_path` 가 이것을 못 본 이유는 그 부재들이 3D 에
아예 없어서다. OI-04 가 "도면에 없다" 고 적은 자리가 바로 여기다.

그래서 이 해석은 그 부재를 **하나 세우고** 두 경로를 견준다:

* **A — 비틀림으로 받는다.** 받침보를 기둥 중심선(축방향 1,600)에 두고,
  하우징이 220 mm 를 내밀어 링 평면에 닿는다. 편심 모멘트가 받침보를 비틀고
  그 비틀림이 기둥으로 간다. 부재가 적고 통로를 안 먹는다.
* **B — 가새로 받는다.** 같은 받침보에 하우징 끝에서 보 쪽으로 무릎가새를
  하나 건다. 편심 모멘트가 짝힘으로 바뀌어 비틀림이 거의 사라진다. 대신
  가새가 자리를 먹고 부재가 는다.

판정선은 링 때와 같다 — **탄성 처짐이 선삭 런아웃 0.25 를 먹으면 안 된다.**
회전체를 받치는 자리라 그 값이 그대로 살아 있다.

**여기서 처음 적는 값은 SM490A 항복과 받침보·가새의 단면·자리뿐이다.**
편심·기둥 자리·롤러 각은 `kinematics`·`ring` 에서, 반력은 `ring.analyse()`
에서, 하우징 단면은 제작 도면집에서 읽는다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.portal
"""

from __future__ import annotations

import functools
import math

from . import dynamics, fabrication, frame3, kinematics, ring

# ── 재료·부재 (여기서 처음 적는 값) ──────────────────────────────────────

#: SM490A 항복강도 (MPa). KS D 3515 용접구조용 압연강 — 인장 490, 항복 325
#: (t ≤ 16). 포탈 기둥·크로스빔이 이 재질이다.
SM490A_YIELD_MPA = 325.0

#: 정적 안전율. `ring.STATIC_SAFETY` 와 같은 값을 쓴다 — 같은 조립체의 같은
#: 하중이므로 판정 기준이 달라지면 비교가 안 된다.
STATIC_SAFETY = ring.STATIC_SAFETY

#: 받침보 단면 (깊이, 폭, 두께 mm). **부품표에 없는 부재라 여기서 고른다.**
#: 크로스빔(BFC-CB-01)과 같은 박스를 쓴다 — 같은 지그·같은 판재로 만들 수 있고,
#: 새 단면을 하나 더 늘리지 않는다.
SUPPORT_BEAM_MM = (260.0, 180.0, 8.0)

#: 무릎가새 단면 (깊이, 폭, 두께 mm). 압축재라 좌굴을 피할 만큼만 굵게.
BRACE_MM = (100.0, 100.0, 6.0)

#: 가새가 기둥에 붙는 높이 (mm). **가새는 수직면에 놓여야 비틀림을 받는다** —
#: 받침보와 같은 높이의 수평 가새는 보 축에 대한 모멘트를 못 받으므로 아무 일도
#: 안 한다. 그래서 하우징 끝에서 기둥 쪽으로 **내려가며** 붙인다. 이 높이는
#: 지게차 헤드가드 상단(`kinematics.FORKLIFT_GUARD_TOP_MM` 2,165)보다 위여야
#: 팔레트가 링 밑으로 들어온다 — 가새가 먹는 자리가 곧 그 여유다.
BRACE_ANCHOR_Y_MM = 2200.0

#: 가새와 링 사이에 남겨야 할 최소 틈 (mm).
BRACE_CLEARANCE_MM = 50.0

#: 링 지지 롤러의 반지름 (mm) — 접점에서 롤러 축까지. 부품표 BFC-RLR-01 Ø150.
_ROLLER_TAG = "BFC-RLR-01"

SHEET = dynamics.SHEET_BFC


def _part(tag: str) -> fabrication.Part:
    return dynamics._part(SHEET, tag)


# ── 자리 ────────────────────────────────────────────────────────────────
def eccentricity_mm() -> float:
    """링 평면과 기둥 중심선의 축방향 거리 (mm) — **유도값이다.**

    OI-04 의 220 이 어디서 나오는지를 값으로 되짚는다. 문장에만 있으면 피치나
    기둥 자리가 바뀌어도 안 따라온다.
    """
    return kinematics.PORTAL_COLUMN_AXIS_MM - kinematics.RING_PITCH_MM / 2


def roller_positions() -> list[tuple[float, float]]:
    """지지 롤러 접점의 (축직각 X, 높이 Y) — 반각은 `ring` 이 갖고 있다."""
    r = kinematics.RING_R_MM + kinematics.RING_TUBE_MM
    half = math.radians(ring.SUPPORT_HALF_ANGLE_DEG)
    return [(-r * math.sin(half), kinematics.FLIP_AXIS_MM - r * math.cos(half)),
            (+r * math.sin(half), kinematics.FLIP_AXIS_MM - r * math.cos(half))]


def roller_axis_y_mm() -> float:
    """롤러 축 높이 (mm) — 접점에서 롤러 반지름만큼 반경 안쪽(아래)이다."""
    od = float(_part(_ROLLER_TAG).size[0])
    half = math.radians(ring.SUPPORT_HALF_ANGLE_DEG)
    _x, y = roller_positions()[0]
    return y - od / 2 * math.cos(half)


def crossbeam_y_mm() -> float:
    """크로스빔 도심 높이 (mm) — 기둥 위에 얹히므로 기둥 길이 + 빔 깊이의 절반."""
    col = float(_part("BFC-COL-01").size[0])
    depth = float(_part("BFC-CB-01").size[2])
    return col + depth / 2.0


def housing_reaches_the_crossbeam() -> bool:
    """부품표의 하우징 하나로 크로스빔에서 롤러까지 닿는가 — **안 닿는다.**

    이 함수가 False 인 것이 OI-04 의 첫 발견이다. 조립 순서 5 는 하우징을
    "크로스빔 탭에" 붙이라고 하는데, 크로스빔은 롤러보다 이만큼 위에 있다.
    """
    drop = crossbeam_y_mm() - roller_axis_y_mm()
    return drop <= float(_part("BFC-BB-01").size[2])


def missing_drop_mm() -> float:
    """크로스빔에서 롤러까지 부품표가 못 채우는 높이 (mm)."""
    return crossbeam_y_mm() - roller_axis_y_mm() - float(_part("BFC-BB-01").size[2])


# ── 모형 ────────────────────────────────────────────────────────────────
def _sections(open_beam: bool = False) -> dict[str, dict[str, float]]:
    col = kinematics.PORTAL_COLUMN_SECTION_MM          # (축방향 180, 축직각 240)
    cb = _part("BFC-CB-01")
    hb = _part("BFC-BB-01")
    return {
        # 기둥: 국부 y 가 전역 X(축직각)라 깊이가 240 이다.
        "column": frame3.box_section(float(col[1]), float(col[0]),
                                     float(_part("BFC-COL-01").t)),
        "crossbeam": frame3.box_section(float(cb.size[2]), float(cb.size[1]),
                                        float(cb.t)),
        "support": (frame3.open_box_section(*SUPPORT_BEAM_MM) if open_beam
                    else frame3.box_section(*SUPPORT_BEAM_MM)),
        # 하우징: PL20 용접물 — 높이 300 · 폭 260 의 박스로 본다.
        "housing": frame3.box_section(float(hb.size[2]), float(hb.size[1]),
                                      float(hb.t)),
        "brace": frame3.box_section(*BRACE_MM),
    }


@functools.lru_cache(maxsize=16)
def analyse(braced: bool = False, open_beam: bool = False) -> dict[str, object]:
    """포탈 한 틀을 푼다. `braced` 가 참이면 무릎가새를 넣는다 (안 B).

    좌표는 포탈 국부다 — X 축직각, Y 높이(바닥 0), Z 축방향(기둥 중심선 1,600,
    링 평면 1,380).
    """
    sec = _sections(open_beam)
    zc = float(kinematics.PORTAL_COLUMN_AXIS_MM)
    zr = zc - eccentricity_mm()
    yb = roller_axis_y_mm()
    ycb = crossbeam_y_mm()
    cols = kinematics.PORTAL_COLUMN_CROSS_MM
    lo, hi = kinematics.crossbeam_cross_extent_mm()

    fr = frame3.Frame3()
    base = [fr.node(x, 0.0, zc) for x in cols]
    at_beam = [fr.node(x, yb, zc) for x in cols]          # 받침보가 붙는 높이
    top = [fr.node(x, ycb, zc) for x in cols]
    for b, m, t in zip(base, at_beam, top):
        if not braced:
            fr.member(b, m, sec["column"])                 # 가새 절점이 없으면 통짜
        fr.member(m, t, sec["column"])
        fr.fix(b)                                          # 기초 고정

    # 크로스빔 — 기둥 위, 양쪽 내밈까지.
    cb_lo = fr.node(lo, ycb, zc)
    cb_hi = fr.node(hi, ycb, zc)
    fr.member(cb_lo, top[0], sec["crossbeam"])
    fr.member(top[0], top[1], sec["crossbeam"])
    fr.member(top[1], cb_hi, sec["crossbeam"])

    # 받침보 — 부품표에 없는 부재. 기둥 사이를 잇는다.
    rollers = roller_positions()
    xs = sorted({cols[0], rollers[0][0], rollers[1][0], cols[1]})
    beam_nodes = {}
    for x in xs:
        beam_nodes[x] = (at_beam[0] if x == cols[0] else
                         at_beam[1] if x == cols[1] else fr.node(x, yb, zc))
    seq = [beam_nodes[x] for x in xs]
    for a, b in zip(seq, seq[1:]):
        fr.member(a, b, sec["support"])

    # 가새를 걸 자리 — 기둥의 아래쪽 절점. 안 B 에서만 쓴다.
    anchors = []
    if braced:
        for k, x in enumerate(cols):
            nd = fr.node(x, BRACE_ANCHOR_Y_MM, zc)
            fr.member(base[k], nd, sec["column"])
            fr.member(nd, at_beam[k], sec["column"])
            anchors.append(nd)

    # 하우징 — 받침보에서 링 평면까지 220 mm 를 내민다.
    tips = []
    for k, (x, _y) in enumerate(rollers):
        tip = fr.node(x, yb, zr)
        fr.member(beam_nodes[x], tip, sec["housing"])
        tips.append(tip)
        if braced:
            fr.member(tip, anchors[k], sec["brace"])

    # 하중 — 링이 롤러를 미는 힘. 반경 방향이라 수직·수평 성분이 같이 있다.
    react = max(ring.analyse()["rollerN"])
    half = math.radians(ring.SUPPORT_HALF_ANGLE_DEG)
    for tip, sign in zip(tips, (-1.0, 1.0)):
        fr.load(tip, fx=sign * react * math.sin(half),
                fy=-react * math.cos(half))

    u = fr.solve()
    worst = 0.0
    who = ""
    for m, (i, j, s, _r) in enumerate(fr.members):
        st = frame3.member_stress_mpa(s, fr.end_forces(m, u))
        if st > worst:
            worst, who = st, _member_name(fr, m, sec)
    sag = [-u[6 * t + 1] for t in tips]
    # **받침보의 비틀림은 전역 X 축 회전이다** — 보가 X 를 따라 뻗으므로
    # θz(자유도 5)를 읽으면 굽힘 회전을 비틀림이라고 말하게 된다.
    twist = [u[6 * beam_nodes[x] + 3] for x, _y in rollers]
    return {
        "braced": braced, "openBeam": open_beam,
        "reactionN": react,
        "sagMm": [round(v, 4) for v in sag],
        "worstSagMm": round(max(sag), 4),
        "tiltMm": round(abs(sag[0] - sag[1]), 4),
        "beamTwistRad": [round(v, 6) for v in twist],
        "worstTwistDeg": round(math.degrees(max(abs(v) for v in twist)), 4),
        "peakMpa": round(worst, 1),
        "peakAt": who,
        "addedKg": round(_added_mass_kg(fr, sec), 1),
        "members": len(fr.members),
    }


def _member_name(fr: frame3.Frame3, m: int, sec: dict[str, dict[str, float]]) -> str:
    names = {id(v): k for k, v in sec.items()}
    korean = {"column": "포탈 기둥", "crossbeam": "크로스빔",
              "support": "받침보", "housing": "롤러 하우징", "brace": "무릎가새"}
    return korean.get(names.get(id(fr.members[m][2]), ""), "?")


def _added_mass_kg(fr: frame3.Frame3, sec: dict[str, dict[str, float]]) -> float:
    """부품표에 없어 새로 드는 강재 (kg) — 받침보와 가새만 센다."""
    from . import afr
    names = {id(v): k for k, v in sec.items()}
    total = 0.0
    for i, j, s, _r in fr.members:
        if names.get(id(s)) not in ("support", "brace"):
            continue
        (x1, y1, z1), (x2, y2, z2) = fr.nodes[i], fr.nodes[j]
        L = math.dist((x1, y1, z1), (x2, y2, z2))
        total += s["A"] * L / 1e9 * afr.STEEL_DENSITY_KG_M3
    return total


# ── 판정 ────────────────────────────────────────────────────────────────
def allow_mpa() -> float:
    return SM490A_YIELD_MPA / STATIC_SAFETY


def options() -> list[dict[str, object]]:
    """두 경로를 같은 판정선으로 견준다."""
    rows = []
    for braced, open_beam, name in (
            (False, False, "A 닫힌 받침보 · 비틀림으로 받는다"),
            (True, False, "B 닫힌 받침보 · 가새를 더한다"),
            (False, True, "A′ 열린 받침보 · 비틀림으로 받는다"),
            (True, True, "B′ 열린 받침보 · 가새로 받는다")):
        a = dict(analyse(braced, open_beam))
        a["name"] = name
        a["sagOk"] = a["worstSagMm"] <= ring.runout_mm()
        a["stressOk"] = a["peakMpa"] <= allow_mpa()
        a["ok"] = bool(a["sagOk"] and a["stressOk"])
        a["utilisation"] = round(max(a["worstSagMm"] / ring.runout_mm(),
                                     a["peakMpa"] / allow_mpa()), 3)
        rows.append(a)
    return rows


def twist_share(open_beam: bool = False) -> float:
    """가새가 받침보 비틀림을 얼마나 덜어 주는가 (0…1)."""
    a, b = analyse(False, open_beam), analyse(True, open_beam)
    if a["worstTwistDeg"] == 0:
        return 0.0
    return round(1 - b["worstTwistDeg"] / a["worstTwistDeg"], 3)


def brace_clearance_mm(samples: int = 200) -> float:
    """가새와 링 사이의 최소 틈 (mm) — 음수면 가새가 링을 뚫는다.

    가새는 하우징 끝에서 기둥으로 **내려가며** 가므로 링 아래를 지난다. 링은
    반지름 `RING_R` 의 원환이라 거리는 닫힌 식으로 나온다 — 링 중심선 원까지의
    거리에서 관 반지름을 뺀 값이다.
    """
    zc = float(kinematics.PORTAL_COLUMN_AXIS_MM)
    zr = zc - eccentricity_mm()
    yb = roller_axis_y_mm()
    worst = math.inf
    for k, (x0, _y) in enumerate(roller_positions()):
        x1 = kinematics.PORTAL_COLUMN_CROSS_MM[k]
        for i in range(samples + 1):
            t = i / samples
            x = x0 + (x1 - x0) * t
            y = yb + (BRACE_ANCHOR_Y_MM - yb) * t
            z = zr + (zc - zr) * t
            # 링 중심선 원(반지름 R, 평면 z = zr)까지의 거리
            rho = math.hypot(x, y - kinematics.FLIP_AXIS_MM)
            d = math.hypot(rho - kinematics.RING_R_MM, z - zr)
            worst = min(worst, d - kinematics.RING_TUBE_MM)
    return worst


def brace_clears_the_ring() -> bool:
    return brace_clearance_mm() >= BRACE_CLEARANCE_MM


def brace_is_needed(open_beam: bool = False) -> bool:
    """가새 없이도 판정선 안에 드는가 — 들면 가새는 무게와 자리를 헛되이 먹는다."""
    rows = {(r["braced"], r["openBeam"]): r for r in options()}
    return not rows[(False, open_beam)]["ok"]


def closing_the_beam_is_what_matters() -> bool:
    """**답이 갈리는 것은 가새가 아니라 받침보를 닫느냐다.**

    닫힌 박스면 비틀림이 무시할 만해 가새가 할 일이 없고, 열면 비틀림이 두
    자릿수 커져 가새가 있어야 판정선을 지킨다.
    """
    return not brace_is_needed(False) and brace_is_needed(True)


def summary() -> dict[str, object]:
    rows = {(r["braced"], r["openBeam"]): r for r in options()}
    a, b = rows[(False, False)], rows[(True, False)]
    ao, bo = rows[(False, True)], rows[(True, True)]
    return {
        "eccentricityMm": eccentricity_mm(),
        "rollerAxisYMm": round(roller_axis_y_mm(), 1),
        "crossbeamYMm": round(crossbeam_y_mm(), 1),
        "housingReaches": housing_reaches_the_crossbeam(),
        "missingDropMm": round(missing_drop_mm(), 0),
        "reactionN": round(a["reactionN"], 0),
        "runoutMm": ring.runout_mm(),
        "allowMpa": allow_mpa(),
        "A": {k: a[k] for k in ("worstSagMm", "tiltMm", "worstTwistDeg",
                                "peakMpa", "peakAt", "addedKg", "utilisation",
                                "ok")},
        "B": {k: b[k] for k in ("worstSagMm", "tiltMm", "worstTwistDeg",
                                "peakMpa", "peakAt", "addedKg", "utilisation",
                                "ok")},
        "Aopen": {k: ao[k] for k in ("worstSagMm", "worstTwistDeg", "peakMpa",
                                     "utilisation", "ok")},
        "Bopen": {k: bo[k] for k in ("worstSagMm", "worstTwistDeg", "peakMpa",
                                     "utilisation", "ok")},
        "closedJ": round(frame3.box_section(*SUPPORT_BEAM_MM)["J"], 0),
        "openJ": round(frame3.open_box_section(*SUPPORT_BEAM_MM)["J"], 0),
        "twistShare": twist_share(),
        "twistShareOpen": twist_share(True),
        "closingMatters": closing_the_beam_is_what_matters(),
        "braceNeeded": brace_is_needed(),
        "braceAnchorYMm": BRACE_ANCHOR_Y_MM,
        "braceClearsRingMm": round(brace_clearance_mm(), 0),
        "braceClearsForkliftMm": round(BRACE_ANCHOR_Y_MM
                                       - kinematics.FORKLIFT_GUARD_TOP_MM, 0),
    }


def checks() -> list[tuple[str, bool, str]]:
    s = summary()
    rows = {(r["braced"], r["openBeam"]): r for r in options()}
    a, b = rows[(False, False)], rows[(True, False)]
    ao, bo = rows[(False, True)], rows[(True, True)]
    return [
        ("편심이 유도값이다", eccentricity_mm() == 220.0,
         f"기둥 {kinematics.PORTAL_COLUMN_AXIS_MM} − 링 평면 "
         f"{kinematics.RING_PITCH_MM / 2:.0f} = {eccentricity_mm():.0f} mm"),
        ("부품표만으로는 롤러가 안 받쳐진다", not s["housingReaches"],
         f"크로스빔 {s['crossbeamYMm']} − 롤러축 {s['rollerAxisYMm']} 에 "
         f"하우징 300 을 빼도 {s['missingDropMm']:.0f} mm 가 빈다"),
        ("닫힌 받침보에서는 가새가 할 일이 거의 없다", s["twistShare"] < 0.3,
         f"비틀림 {a['worstTwistDeg']}° → {b['worstTwistDeg']}° "
         f"({s['twistShare'] * 100:.0f} % 감) — 닫힌 박스가 이미 다 받는다"),
        ("열면 비틀림이 두 자릿수 커진다",
         ao["worstTwistDeg"] > a["worstTwistDeg"] * 10,
         f"J {s['closedJ']:,.0f} → {s['openJ']:,.0f} mm⁴ 에서 "
         f"{a['worstTwistDeg']}° → {ao['worstTwistDeg']}°"),
        ("갈리는 것은 가새가 아니라 받침보를 닫느냐다", s["closingMatters"],
         f"닫으면 가새 없이 통과({a['ok']}), 열면 가새 없이는 실패"
         f"({ao['ok']}) · 가새를 넣으면 통과({bo['ok']})"),
        ("두 안 다 처짐이 런아웃 안이다",
         a["sagOk"] and b["sagOk"],
         f"A {a['worstSagMm']} · B {b['worstSagMm']} mm ≤ {s['runoutMm']}"),
        ("두 안 다 응력이 허용 안이다", a["stressOk"] and b["stressOk"],
         f"A {a['peakMpa']} · B {b['peakMpa']} MPa ≤ {s['allowMpa']:.0f}"),
        ("가새가 무게를 더한다", b["addedKg"] > a["addedKg"],
         f"새로 드는 강재 A {a['addedKg']} → B {b['addedKg']} kg"),
        ("가새가 링을 안 뚫는다", brace_clears_the_ring(),
         f"링까지 최소 {brace_clearance_mm():.0f} mm (요구 {BRACE_CLEARANCE_MM:.0f})"),
        ("가새가 지게차 헤드가드 위에 선다",
         BRACE_ANCHOR_Y_MM > kinematics.FORKLIFT_GUARD_TOP_MM,
         f"가새 밑단 {BRACE_ANCHOR_Y_MM:.0f} > 헤드가드 "
         f"{kinematics.FORKLIFT_GUARD_TOP_MM}"),
    ]


def annotations() -> tuple[str, ...]:
    s = summary()
    rows = {(r["braced"], r["openBeam"]): r for r in options()}
    a, b = rows[(False, False)], rows[(True, False)]
    ao = rows[(False, True)]
    lines = [
        f"링 평면과 기둥 중심선의 편심 {s['eccentricityMm']:.0f} mm 는 유도값이다 — "
        f"기둥 축방향 ∓{kinematics.PORTAL_COLUMN_AXIS_MM} 과 링 피치 절반 "
        f"∓{kinematics.RING_PITCH_MM / 2:.0f} 의 차다",
        f"부품표에 롤러를 기둥까지 잇는 부재가 없다 — 크로스빔은 "
        f"{s['crossbeamYMm']:.0f}, 롤러 축은 {s['rollerAxisYMm']:.0f} 이고 "
        f"하우징 300 을 다 써도 {s['missingDropMm']:.0f} mm 가 빈다. 3D 에도 "
        f"그 자리가 비어 있어 `check_load_path` 가 못 봤다",
        f"받침보를 하나 세워 두 경로를 견준다 — 롤러 반력 {s['reactionN']:.0f} N/개, "
        f"판정선은 링 선삭 런아웃 {s['runoutMm']} mm 다",
        f"A 비틀림으로 받는다 — 처짐 {a['worstSagMm']} mm · 받침보 비틀림 "
        f"{a['worstTwistDeg']}° · 최대 {a['peakMpa']} MPa ({a['peakAt']}) · "
        f"새 강재 {a['addedKg']} kg",
        f"B 가새로 받는다 (기둥 {s['braceAnchorYMm']:.0f} 에 물린다) — "
        f"처짐 {b['worstSagMm']} mm · "
        f"비틀림 {b['worstTwistDeg']}° ({s['twistShare'] * 100:.0f} % 감) · 최대 "
        f"{b['peakMpa']} MPa ({b['peakAt']}) · 새 강재 {b['addedKg']} kg",
    ]
    lines.append(
        f"받침보를 열린 단면으로 만들면 J 가 {s['closedJ']:,.0f} → {s['openJ']:,.0f} mm⁴ "
        f"로 떨어져 비틀림이 {a['worstTwistDeg']}° → {ao['worstTwistDeg']}° 가 되고 "
        f"처짐이 {a['worstSagMm']} → {ao['worstSagMm']} mm 로 뛴다 — "
        f"{'그때는 가새가 있어야 한다' if not ao['ok'] else '그래도 판정선 안이다'}")
    if not s["braceNeeded"]:
        lines.append(
            "비틀림만으로도 판정선 안에 든다 — 가새는 무게와 자리를 더할 뿐 "
            "필요해서 넣는 것이 아니다. 넣을 이유가 있다면 그것은 강도가 아니라 "
            "다른 것이어야 한다 (진동·정비·조립 순서)")
    else:
        lines.append("비틀림만으로는 판정선을 못 지킨다 — 가새가 필요하다")
    lines.append(
        f"가새는 수직면에 놓여야 비틀림을 받는다 — 하우징 끝에서 기둥으로 "
        f"내려가며 걸면 링까지 {s['braceClearsRingMm']:.0f} mm 남고 지게차 "
        f"헤드가드보다 {s['braceClearsForkliftMm']:.0f} mm 위에 선다. 그 자리가 "
        f"곧 가새가 먹는 정비 공간이다")
    lines.append(
        "프레임 요소는 부재를 선으로 본다 — 하우징과 받침보의 접합부 국부응력, "
        "볼트 무리, 기초 앵커는 여기서 안 나온다. 받침보 단면도 여기서 고른 "
        "것이지 부품표에서 온 것이 아니다 (OI-04)")
    return tuple(lines)


if __name__ == "__main__":                                   # pragma: no cover
    import json

    print(json.dumps(summary(), ensure_ascii=False, indent=1))
    print()
    for name, ok, why in checks():
        print(f"{'✓' if ok else '✗'} {name} — {why}")
    print()
    for line in annotations():
        print("·", line)
