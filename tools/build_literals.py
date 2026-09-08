"""배치 모델이 바뀌면 따라 움직이는 도면 리터럴을 한 번에 다시 찍는다.

존 표(`layout.build_zones`)는 이 플랜트의 뿌리다 — 존 하나가 길어지거나 없어지면
소음원 위치·케이블 길이·MDB 부하중심·크레인 주행로·스마트 시설 X·케이싱이 전부
따라 움직인다. 그동안 그 재생성을 그때그때 임시 스크립트로 했고, 스크립트가 남지
않아 다음 사람이 같은 것을 다시 짰다. REV.45 에서 게이트 존이 없어지며 도면
리터럴 50여 곳이 한꺼번에 어긋난 것이 계기다.

    PYTHONPATH=src python tools/build_literals.py

멱등이다. 값이 이미 맞으면 아무것도 안 바꾼다.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import (access, acoustics, ai, crane, kinematics,  # noqa: E402
                           layout, mounting, reliability, safety, smart, thermal,
                           wiring)

DRAWING = pathlib.Path(__file__).resolve().parent.parent / "docs/drawings/pv-preprocess-plant.html"

# AFR 시트에 손으로 그린 12구역 지지베드 — 공용 인계롤러가 여기서 끝난다.
# 시트의 BED 부품과 같은 값이어야 한다 (part('BED', …, [3250, …], [-400, …])).
BED_X_MM, BED_L_MM = -400, 3250

#: 3D 씬 원점의 플랜트 X (mm). world_x = (plant_x - 이 값) / 1000.
SCENE_ORIGIN_X_MM = 24_750


def q(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return "'" + v + "'"
    if isinstance(v, float):
        return f"{v:g}" if v != int(v) else f"{v:.1f}"
    return str(v)


class Patch:
    def __init__(self, text: str) -> None:
        self.text = text
        self.changed = 0

    def one(self, pattern: str, build) -> None:
        """정확히 한 곳을 찾아 갈아 끼운다. 0 곳이나 2 곳이면 멈춘다."""
        hits = re.findall(pattern, self.text, re.S)
        assert len(hits) == 1, f"앵커 {len(hits)}곳: {pattern[:60]}"
        new = self.text[:]
        self.text = re.sub(pattern, lambda m: build(m), self.text, count=1, flags=re.S)
        if new != self.text:
            self.changed += 1

    def rows(self, name: str, rows, indent: str = "        ") -> None:
        body = "\n" + ",\n".join(
            indent + "[" + ", ".join(q(c) for c in r) + "]" for r in rows)
        self.one(rf"(var {name} = \[)(?:.*?)(\n  \];)",
                 lambda m: m.group(1) + body + m.group(2))

    def scalar(self, key: str, value: object, sep: str = ": ") -> None:
        pat = re.escape(key) + re.escape(sep) + r"-?[\d.]+"
        hits = re.findall(pat, self.text)
        assert len(hits) == 1, f"스칼라 {key} {len(hits)}곳"
        new = re.sub(pat, key + sep + q(value), self.text, count=1)
        if new != self.text:
            self.changed += 1
        self.text = new


def zone_seed_rows() -> list[list[object]]:
    out: list[list[object]] = []
    for key, label, y0, note, fallback in layout.ZONE_SEED:
        row: list[object] = [key, label, y0, note]
        if fallback is not None:
            row += list(fallback)
        out.append(row)
    return out


def main() -> int:
    p = Patch(DRAWING.read_text(encoding="utf-8"))

    # ── 존 시드 ──────────────────────────────────────────────────────────
    body = "\n" + ",\n".join(
        "    [" + ", ".join(q(c) for c in row) + "]" for row in zone_seed_rows())
    p.one(r"(  var zoneSeed = \[)(?:.*?)(\n  \];)",
          lambda m: m.group(1) + body + m.group(2))

    # ── 3D 셀 격자 ───────────────────────────────────────────────────────
    # 이 플랜트에는 격자가 둘 있었다. 존 표(여기)와, 씬에 손으로 놓은 셀 좌표.
    # 두 격자는 AFR 아래에서 4,600 mm 갈라져 있었고 아무 검사도 그것을 안 봤다
    # (케이싱·하중경로 검사는 "형상끼리" 를 묻지 "형상이 자기 존 안인가" 를
    # 묻지 않는다). 존 범위를 씬에 값으로 들여보내 3D 가 그것을 기준으로
    # 검사받게 한다 — `tools/check_cell_grid.mjs`.
    def _m(mm: int) -> str:
        """플랜트 mm → 씬 world m 문자열 (씬 원점은 x 24,750 mm)."""
        t = f"{(mm - SCENE_ORIGIN_X_MM) / 1000:g}"
        return t[1:] if t.startswith("0.") else (
            "-" + t[2:] if t.startswith("-0.") else t)

    grid = ",".join(f"{z.key}:[{_m(z.x0_mm)},{_m(z.x1_mm)}]"
                    for z in layout.build_zones())
    p.one(r"var pvZone=\{[^}]*\}", lambda m: "var pvZone={" + grid + "}")

    # ── 셀 외형·이름 ─────────────────────────────────────────────────────
    for key, st in layout.STATIONS.items():
        if key == "bfc":
            continue                       # 부품 조립도라 존이 없다
        p.one(rf"(\n    {key}: \{{.*?envelope: )\[[\d, ]+\]",
              lambda m, st=st: m.group(1)
              + "[" + ", ".join(str(v) for v in st.envelope) + "]")

    # 이송면 — 셀 표제란의 H 는 모델의 이송 높이다. REV.44 까지 robot·jbr 이
    # 900 으로 남아 있었고 3D 는 또 1,025 였다 — 한 플랜트에 세 값이 있었다.
    for key, st in layout.STATIONS.items():
        if key == "bfc":
            continue
        p.one(rf"(\n    {key}: \{{.*?\n      transfer: )\d+",
              lambda m, st=st: m.group(1) + str(st.transfer_height_mm))

    # 종단면 주기 — 라인의 최저·최고 이송면에서 파생한다
    levels = sorted({st.transfer_height_mm for k, st in layout.STATIONS.items()
                     if k not in ("afu", "bfc")})
    p.one(r"'기준 이송면 H=[\d,~]+ · BFC 로봇 인계 H=[\d,]+'",
          lambda m: f"'기준 이송면 H={levels[0]:,}~{levels[-1]:,} · "
          f"BFC 로봇 인계 H={layout.STATIONS['bfc'].transfer_height_mm:,}'")

    # 초점 뷰 — 없어진 존을 가리키면 화면이 빈다
    p.one(r"var LAYOUT_FOCUS = \{[^}]*\}",
          lambda m: "var LAYOUT_FOCUS = { all: null, upstream: ['afu', 'robot'], "
                    "jbr: ['jbr'], afr: ['afr', 'post'] }")

    # ── 지지·장착 요약 ───────────────────────────────────────────────
    # 부재 수·브래킷 수·앵커 수는 mounting 이 센다. 손으로 적으면 부재 하나를
    # 빼도 배지가 옛 수를 보여 준다 (REV.49 에서 셔틀 포스트를 빼며 그랬다).
    sm = mounting.summary()
    p.one(r"MOUNT_SUMMARY = \{[^}]*\}",
          lambda m: ("MOUNT_SUMMARY = { stations: %d, anchors: %d, m16: %d, m20: %d, m24: %d, "
                     "members: %d, brackets: %d, keepOut: %d, floor: %d, frame: %d, gantry: %d, "
                     "exempt: %d }")
          % (sm["stations"], sm["anchors"], sm["by_bolt"]["M16"], sm["by_bolt"]["M20"],
             sm["by_bolt"]["M24"], sm["members"], sm["brackets"], sm["keepOut"],
             sm["by_class"]["floor"], sm["by_class"]["frame"], sm["by_class"]["gantry"],
             sm["exempt"]))

    # ── 반전기 기구학 요약 ───────────────────────────────────────────
    # 3D 표제란이 그대로 보여 주는 값이다. REV.48 까지 손으로 적은 리터럴이었고,
    # 시험이 모델 요약의 키·값이 도면에 있는지만 봤다 — 모델에서 키가 없어지면
    # (REV.49 의 이송면·링 밑 여유) 도면에 옛 값이 남아도 아무도 몰랐을 자리다.
    def _kv(k: str, v: object) -> str:
        return f"{k}: {json.dumps(v)}" if isinstance(v, list) else f"{k}: {v}"
    p.one(r"var KINEMATICS = \{[^}]*\}",
          lambda m: "var KINEMATICS = {" + ", ".join(
              _kv(k, v) for k, v in kinematics.summary().items()) + "}")

    # ── 소음 ─────────────────────────────────────────────────────────────
    p.rows("NOISE_SOURCES",
           [(s.tag, s.equipment, s.x_mm, s.lw_dba, s.reduction_db,
             s.mitigation, s.character) for s in acoustics.noise_sources()])
    raw_x, raw = acoustics.worst_aisle_dba(mitigated=False)
    mit_x, mit = acoustics.worst_aisle_dba(mitigated=True)
    p.one(r"var NOISE_SUMMARY = \{[^}]*\}",
          lambda m: ("var NOISE_SUMMARY = { nearRaw: %s, nearMit: %s, aisleRawX: %d, "
                     "aisleRaw: %s, aisleMitX: %d, aisleMit: %s, nearLimit: %.0f, "
                     "aisleLimit: %.0f, standoffM: %.0f }")
          % (acoustics.worst_near_field_dba(False), acoustics.worst_near_field_dba(True),
             raw_x, raw, mit_x, mit, acoustics.NEAR_FIELD_LIMIT_DBA,
             acoustics.AISLE_LIMIT_DBA, acoustics.AISLE_STANDOFF_M))

    # ── 배선 ─────────────────────────────────────────────────────────────
    p.one(r"var MDB_X_MM = \d+, INCOMING_CABLE_M = [\d.]+, TOTAL_POWER_CABLE_M = [\d.]+",
          lambda m: "var MDB_X_MM = %d, INCOMING_CABLE_M = %s, TOTAL_POWER_CABLE_M = %s"
          % (wiring.MDB_POSITION_MM[0],
             0 if wiring.incoming_cable_m() is None else q(wiring.incoming_cable_m()),
             q(round(wiring.total_power_cable_m(), 1))))


    # 케이블 길이 — 반이 움직이면 12본이 전부 다시 계산된다
    p.one(r"var CABLE_LENGTH_M = \{[^}]*\}",
          lambda m: "var CABLE_LENGTH_M = { "
          + ", ".join(f"{c.feeder}: {c.length_m:g}" for c in wiring.power_cables())
          + " }")

    # ── 통합 제거셀의 가드 ───────────────────────────────────────────────
    # 두 스테이션은 한 인클로저 안에 있다. 접합부에는 벽이 없으므로 각 시트의
    # 가드는 자기 존 구간만 그린다 — 폭·중심을 장비 실측에서 파생한다.
    # REV.52: 스테이션이 셋이다 — post 하드웨어는 CV-102 통과 롤러 런이고 시트
    # 로컬 원점(GI 검사대 중심)에서 상류 1,225 · 하류 1,645 다.
    hardware = {"jbr": (-3400, 3400),
                "afr": (-2325, 3325),   # REV.50: SG-301 몸체 끝 (롤러 런 중심 2,225 + 1,100)
                "post": (-layout.POST_GI_FROM_HARDWARE_MM,
                         layout.STATION_HARDWARE_X_MM["post"]
                         - layout.POST_GI_FROM_HARDWARE_MM)}
    sides = {0: "상류", len(layout.INTEGRATED_CELL) - 1: "하류"}
    guard_lo: dict[str, int] = {}
    for key, (h0, h1) in hardware.items():
        up, down = layout.station_edges_mm(key)
        lo, hi = h0 - up, h1 + down
        assert hi - lo == layout.STATIONS[key].envelope[0], (key, hi - lo)
        guard_lo[key] = lo
        side = sides.get(layout.INTEGRATED_CELL.index(key), "가운데")
        # 접합부 250 을 반씩 나눠 가지면 구간이 홀수인 스테이션이 생긴다 —
        # post 가 그렇다(3,025). 중심을 반올림하면 부재 끝이 0.5 mm 어긋나므로
        # 공용 인계롤러(CV-JA)와 같은 이유로 실제 기하를 그대로 적는다.
        p.one(rf"(\n    {key}: \{{.*?part\('GUARD', )'[^']*', \[\d+, (\d+), (\d+)\], "
              rf"\[-?[\d.]+, (\d+), 0\]",
              lambda m, lo=lo, hi=hi, side=side:
              m.group(1) + f"'JB/AFR 통합 가드 ({side} 스테이션 구간)', "
              f"[{hi - lo}, {m.group(2)}, {m.group(3)}], [{(lo + hi) / 2:g}, {m.group(4)}, 0]")

    # 접합부를 넘어 이어지는 공용 인계롤러는 자기 시트 안에서만 그린다.
    # 통합 전에는 AFR 가드(-3,200)까지 그려도 됐지만, 가드가 물러나며 시트
    # 밖으로 나갔다 — 서브어셈블리 시트는 자기 구간까지만 그린다.
    #
    # 접합부 250 을 절반씩 나눠 가지므로 이 구간은 **홀수**(425)다. 그래서
    # 중심이 -2,237.5 로 떨어진다. 반올림하면 부품 끝이 시트 포락선을 0.5 mm
    # 넘거나 베드를 0.5 mm 파고든다 — 실제 기하가 반올림보다 우선이다.
    lo = guard_lo["afr"]              # AFR 시트의 상류 경계 = 통합 가드 끝
    hi = BED_X_MM - BED_L_MM // 2     # 12구역 지지베드 상류 끝
    p.one(r"part\('CV-JA', '[^']*', \[[\d.]+, (\d+), (\d+)\], \[-?[\d.]+, (\d+), 0\]",
          lambda m: f"part('CV-JA', '공용 인계롤러 (JBR 스테이션에서 이어짐)', "
          f"[{q(hi - lo)}, {m.group(1)}, {m.group(2)}], "
          f"[{q((lo + hi) / 2)}, {m.group(3)}, 0]")

    # 진입 화살표도 같은 경계에서 출발한다. 통합 전에는 -2,610 에서 시작했는데
    # 그건 옛 AFR 가드(-3,200) 안쪽이었다 — 가드가 -2,450 으로 물러난 지금은
    # 시트 밖에서 출발하는 화살표다. 경계에서 베드 중심까지로 다시 찍는다.
    p.one(r"step\('1', '공용 인계롤러 진입[^']*', \[-?\d+, (\d+), 0\], \[-?\d+, (\d+), 0\]\)",
          lambda m: f"step('1', '공용 인계롤러 진입·베드 안착 {BED_X_MM - lo:,}', "
          f"[{lo}, {m.group(1)}, 0], [{BED_X_MM}, {m.group(2)}, 0])")

    # AFR 존 시작부터 플랜트 끝까지의 상세 포락선 표기 — 존에서 파생한다
    zones = {z.key: z for z in layout.build_zones()}
    tail = layout.plant_envelope_mm()[0] - zones["afr"].x0_mm
    p.one(r"상세 배치 포락선은 [\d,]+ × [\d,]+ mm",
          lambda m: f"상세 배치 포락선은 {tail:,} × {layout.MACHINE_BAND_Y_MM:,} mm")

    # ── AFR CL-221 클램프 포탈 ───────────────────────────────────────────
    # 크로스헤드 하면은 이송면 위에 쌓인 것들의 합이다 (kinematics). 이송면이
    # 움직이면 기둥 전장·크로스헤드·타이빔이 전부 따라와야 하고, 안 따라오면
    # 클램프가 크로스헤드에서 떨어져 공중에 매달린다.
    soffit = kinematics.AFR_CROSSHEAD_SOFFIT_MM / 1000
    depth = kinematics.AFR_CROSSHEAD_DEPTH_MM / 1000
    col = kinematics.AFR_PORTAL_HEIGHT_MM / 1000
    p.one(r"L\(\[\.14, [\d.]+, \.14\], \[x, [\d.]+, z\]",
          lambda m: f"L([.14, {col:g}, .14], [x, {col / 2:g}, z]")
    p.one(r"L\(\[\.16, [\d.]+, 3\.04\], \[x, [\d.]+, 0\]",
          lambda m: f"L([.16, {depth:g}, 3.04], [x, {soffit + depth / 2:g}, 0]")
    p.one(r"L\(\[1\.98, [\d.]+, \.14\], \[pvZone\.afr\[0\]\+2\.05, [\d.]+, z\]",
          lambda m: f"L([1.98, {depth:g}, .14], [pvZone.afr[0]+2.05, {soffit + depth / 2:g}, z]")
    p.one(r"// 크로스헤드 하면 [\d.]+ 가 클램프 실린더 상단을 직접 받는다\.",
          lambda m: f"// 크로스헤드 하면 {soffit:g} 가 클램프 실린더 상단을 직접 받는다.")
    p.one(r"y 1\.03…[\d.]+ 에 서 있는데 \*\*[\d.]+ 위에 아무것도 없었다\*\*",
          lambda m: f"y 1.03…{soffit:g} 에 서 있는데 **{soffit:g} 위에 아무것도 없었다**")
    p.one(r"'하면 [\d.]+ 가 상부 클램프 실린더 상단을 직접 받는다",
          lambda m: f"'하면 {soffit:g} 가 상부 클램프 실린더 상단을 직접 받는다")
    p.one(r"\['AFR CL-221 포탈 크로스헤드 2본', 'afr', 'floor', '[^']*'\]",
          lambda m: "['AFR CL-221 포탈 크로스헤드 2본', 'afr', 'floor', '"
          + [mm for mm in mounting.MEMBERS
             if mm.label == "AFR CL-221 포탈 크로스헤드 2본"][0].carries + "']")

    # ── 신뢰도·AI ────────────────────────────────────────────────────────
    # 블록을 하나 가르거나 가용률 식을 고치면 도면의 두 표가 같이 움직여야 한다.
    p.one(r"var RELIABILITY = \{.*?\};",
          lambda m: "var RELIABILITY = "
          + json.dumps(reliability.summary(), ensure_ascii=False) + ";")
    p.one(r"var RELIABILITY_BLOCKS = \[.*?\];",
          lambda m: "var RELIABILITY_BLOCKS = " + json.dumps(
              [[b.tag, b.name, b.share, b.mttr_h, b.redundant, b.buffered,
                b.downtime_h(), b.failures_per_year(), b.required_mtbf_h(), b.basis]
               for b in reliability.BLOCKS], ensure_ascii=False) + ";")

    a = ai.summary()
    labels = a["labels"]
    grades = a["grades"]
    p.one(r"var AI_SUMMARY = \{[^}]*\};",
          lambda m: ("var AI_SUMMARY = { cases: %d, gradeA: %d, gradeB: %d, gradeC: %d, "
                     "gradeD: %d, annualPanels: %d, labelNormal: %d, labelCracked: %d, "
                     "labelScrap: %d, scarcest: '%s', coldStartMonths: %s, transferMin: %d, "
                     "scrapMissS: %s, crackedMissS: %s };")
          % (a["cases"], grades["A"], grades["B"], grades["C"], grades["D"],
             a["annual_panels"], labels["정상"], labels["유리 깨짐"], labels["전손"],
             a["scarcest"], q(a["cold_start_months"]), a["transfer_min"],
             q(a["scrap_miss_s"]), q(a["cracked_miss_s"])))

    # ── 안전 ─────────────────────────────────────────────────────────────
    p.one(r"var SAFETY = \{.*?\};",
          lambda m: "var SAFETY = "
          + json.dumps(safety.summary(), ensure_ascii=False) + ";")
    p.one(r"var SAFETY_OPENINGS = \[.*?\];",
          lambda m: "var SAFETY_OPENINGS = " + json.dumps(
              [[o.tag, o.name, o.plane_x_mm, o.hazard_x_mm, o.hazard_part,
                o.distance_mm, o.budget_ms, o.note] for o in safety.OPENINGS],
              ensure_ascii=False) + ";")

    # ── 고소 접근 ────────────────────────────────────────────────────────
    # 이송면이 내려가면 포탈이 낮아지고, 낮아지면 추락 방호 대상 수가 바뀐다.
    p.one(r"var ACCESS = \{.*?\};",
          lambda m: "var ACCESS = "
          + json.dumps(access.summary(), ensure_ascii=False) + ";")
    p.one(r"var ACCESS_POINTS = \[.*?\];",
          lambda m: "var ACCESS_POINTS = " + json.dumps(
              [[pt.tag, pt.equipment, pt.station, pt.height_mm, pt.task,
                pt.per_year, pt.ours, pt.means, pt.needs_fall_protection, pt.basis]
               for pt in access.POINTS], ensure_ascii=False) + ";")

    # ── 크레인 ───────────────────────────────────────────────────────────
    p.scalar("runwayMm", crane.summary()["runwayMm"])
    # 3D — 주행거더 중앙은 플랜트 중앙이다 (월드 원점 x = 24,750)
    rx = (layout.plant_envelope_mm()[0] / 2 - 24_750) / 1000
    p.one(r"RX=[-\d.]+,BX=RX;", lambda m: f"RX={rx:g},BX=RX;")
    p.one(r"L\(\[[\d.]+,\.40,\.20\],\[RX,10\.50,z\]",
          lambda m: f"L([{crane.RUNWAY_MM / 1000:.2f},.40,.20],[RX,10.50,z]")
    p.one(r"'길이 [\d,]+ 이 플랜트 전장 [\d,]+ 을 덮는다\.",
          lambda m: f"'길이 {crane.RUNWAY_MM:,} 이 플랜트 전장 "
          f"{layout.plant_envelope_mm()[0]:,} 을 덮는다.")
    p.one(r'installOrder: \[[^\]]*\]',
          lambda m: "installOrder: ["
          + ", ".join('"' + k + '"' for k in crane.install_order()) + "]")

    # ── 스마트 시설 — 위치는 배선 모델이 존에서 파생한다 ───────────────
    # 데이터량·태그 수는 서보 축 수의 함수다 (REV.49 에서 셔틀 X 축 2 가 빠지며
    # 37 → 35 축, 태그 600 → 584, 시계열 94.1 → 89.2 kB/s). 손으로 적은 리터럴은
    # 축을 빼도 옛 값을 보여 준다 — 그래서 요약에서 그대로 찍는다.
    sm = smart.summary()
    for key, value in (("serverRoomX", wiring.server_room_center_x_mm()),
                       ("controlRoomX", wiring.control_room_center_x_mm()),
                       ("edgeCenterX", wiring.edge_cabinet_center_x_mm()),
                       ("facilityX0", wiring.facility_x0_mm()),
                       ("facilityX1", wiring.facility_span_mm()[1])):
        p.scalar(key, value)
    # 나머지 키는 SMART 리터럴 **안에서만** 바꾼다 — itKw 같은 이름은 다른 표에도 있다.
    smart_keys = (("racks", sm["racks"]), ("rackU", sm["rack_u"]),
                  ("rackHeatKw", sm["rack_heat_kw"]),
                  ("edgeCabinets", sm["edge_cabinets"]), ("wifiAps", sm["wifi_aps"]),
                  ("instruments", sm["instruments"]), ("plcTags", sm["plc_tags"]),
                  ("servos", sm["drive_counts"]["서보"]),
                  ("inverters", sm["drive_counts"]["인버터"]),
                  ("dol", sm["drive_counts"]["직입"] + sm["drive_counts"]["소프트스타터"]),
                  ("timeseriesKbS", sm["timeseries_kb_s"]),
                  ("visionRawMbS", sm["vision_raw_mb_s"]),
                  ("visionKeptMbS", sm["vision_kept_mb_s"]),
                  ("retentionPct", sm["vision_retention_pct"]),
                  ("requiredMbps", sm["required_mbps"]),
                  ("backboneMbps", sm["backbone_mbps"]),
                  ("annualTb", sm["annual_tb"]), ("storageTb", sm["storage_tb"]),
                  ("itKw", sm["it_kw"]), ("instKw", sm["inst_kw"]),
                  ("smartKw", sm["smart_kw"]),
                  ("hoursPerYear", int(sm["hours_per_year"])))

    def _smart(m: re.Match) -> str:
        body = m.group(0)
        for key, value in smart_keys:
            body, n = re.subn(rf"\b{key}: -?[\d.]+", f"{key}: {q(value)}", body)
            assert n == 1, f"SMART 키 {key} {n}곳"
        return body
    p.one(r"var SMART = \{[^}]*\}", _smart)

    # ── 공압·집진 — 두 블록이 모델 요약을 그대로 받는다 ─────────────────
    # 이 둘은 손으로 넣은 리터럴이었다. REV.59 에서 SG 후드가 한 대 몫에서 두 대
    # 몫으로 늘자 여과면적·펄스밸브·압축공기가 다 움직였는데 도면은 옛 수를 계속
    # 말했다 — 시험이 잡았지만, 잡히는 것과 따라오는 것은 다른 일이다.
    def _block(name: str, values: dict):
        """도면 블록이 들고 있는 키를 모델 요약으로 갈아 끼운다.

        키가 `key:` 인 블록과 `"key":` 인 블록이 섞여 있다 — 둘 다 받는다.
        처음에 홑따옴표 꼴만 보게 만들었더니 DUST 블록에서 **한 키도 못 찾고
        조용히 지나갔다.** 그래서 한 키도 못 찾으면 멈춘다.

        블록에 있는 키만 다룬다 — 요약이 더 많은 것을 들고 있어도 도면이 다 보여
        줄 이유는 없다. 반대로 **블록에 있는데 요약에 없는 키**는 정본이 사라진
        것이므로 멈춘다.
        """
        val = r"(?:-?[\d.]+|'[^']*'|\"[^\"]*\"|true|false)"

        def build(m: re.Match) -> str:
            body = m.group(0)
            keys = re.findall(rf'"?(\w+)"?: {val}', body)
            assert keys, f"{name} 블록에서 키를 하나도 못 찾았다"
            missing = [k for k in keys if k not in values]
            assert not missing, f"{name} 블록의 {missing} 가 모델 요약에 없다"
            for key in keys:
                value = values[key]
                if isinstance(value, (list, tuple, dict)):
                    continue                      # 구조는 이 자리에서 안 다룬다
                for quoted in (f'"{key}"', key):  # 블록의 표기를 그대로 지킨다
                    pat = rf"{re.escape(quoted)}: {val}"
                    body, n = re.subn(pat, f"{quoted}: {q(value)}", body, count=1)
                    if n:
                        break
                else:
                    raise AssertionError(f"{name} 키 {key} 를 못 갈아 끼웠다")
            # 모델이 키를 새로 내놓으면 블록에 **넣는다** — 갈아 끼우기만 하면
            # 새 값이 도면에 영영 안 나타난다 (시험이 잡지만 손으로 넣어야 했다).
            quoted = '"' in body.split("{", 1)[1].split(":", 1)[0]
            for key, value in values.items():
                if key in keys or isinstance(value, (list, tuple, dict)):
                    continue
                label = f'"{key}"' if quoted else key
                body = body.rstrip().rstrip("}").rstrip()
                sep = "" if body.endswith("{") else ","
                body = f"{body}{sep} {label}: {q(value)} }}"
            return body
        p.one(rf"var {name} = \{{[^}}]*\}}", build)

    from pv_preprocess import acceptance, air as _air, dust as _dust, electrical
    _block("AIR", _air.summary())
    _block("DUST", _dust.summary())
    _block("THERMAL_SUMMARY", {
        "room": thermal.room_load_kw(), "airflow": thermal.required_airflow_m3h(),
        "exhausted": thermal.exhausted_kw(),
        # 도면이 정수로 적어 온 자리다 — 5.0 으로 찍으면 시험이 잡는다.
        "deltaT": int(thermal.ROOM_DELTA_T_C),
        "hpuLossRatio": thermal.HPU_LOSS_RATIO,
        "driveLossRatio": thermal.DRIVE_LOSS_RATIO,
        "coolerMargin": thermal.COOLER_MARGIN})
    _block("ACCEPTANCE", acceptance.summary())
    # INCOMER 블록은 모델의 snake_case 를 camelCase 로 옮겨 적은 것이라 이름이
    # 1:1 이 아니다 (hv_voltage_v → hvV). 그 대응을 여기에 명시로 둔다 —
    # 시험(test_drawing_carries_the_confirmed_incomer)이 쓰는 것과 같은 표다.
    # 급전 표도 손으로 유지되고 있었다 — F7 의 풍량 문구와 F16 의 다이버시티가
    # 모델에서 움직였는데 도면은 옛 값을 계속 말했다.
    p.rows("feeders",
           [[f.tag, f.panel, f.served, f.installed_kw, f.diversity, f.breaker_at,
             f.cable, f.source] for f in electrical.FEEDERS], indent="    ")

    _inc = electrical.incomer_summary()
    _block("INCOMER", {
        "tapsSite": _inc["taps_site"], "tapLowVoltage": _inc["tap_low_voltage"],
        "siteServiceKw": _inc["site_service_kw"],
        "siteUtilPct": _inc["site_utilisation_pct"],
        "siteHeadroomKw": _inc["site_headroom_kw"],
        "worstCaseKw": _inc["worst_case_kw"],
        "coincidentWorstCaseKw": _inc["coincident_worst_case_kw"],
        "lvTapMaxM": _inc["lv_tap_max_m"], "highVoltage": _inc["high_voltage"],
        "hvV": _inc["hv_voltage_v"], "contractKw": _inc["contract_kw"],
        "contractKva": _inc["contract_kva"], "apparentKva": _inc["apparent_kva"],
        "transformerKva": _inc["transformer_kva"],
        "transformerKvaIfHv": _inc["unit_transformer_kva"],
        "transformerLoadPct": _inc["transformer_load_pct"],
        "capacitorKvar": _inc["capacitor_kvar"], "hvCurrentA": _inc["hv_current_a"],
        "hvCable": _inc["incoming_cable"], "vcbA": _inc["vcb_a"],
        "lvMainMm2": _inc["lv_main_cable_mm2"],
        "breakerHeadroomKw": _inc["breaker_headroom_kw"],
        # 아래 넷은 요약에 없고 상수·판정이다. 값이 안 움직이는 것들이지만
        # 블록의 모든 키를 덮어야 "조용히 안 갈아 끼움" 이 안 생긴다.
        "lowVoltageLimitKw": electrical.LOW_VOLTAGE_LIMIT_KW,
        "dropPct": electrical.FEEDER_VOLTAGE_DROP_PCT,
        "incomingKnown": not _inc["taps_site"],
        "withinLvLimit": _inc["contract_kw"] <= _inc["site_service_kw"],
        "lvTapConfirmed": _inc["tap_low_voltage"],
        "method": _inc["method"], "substationMm": _inc["substation_room_mm"]})

    # ── 패널 구조 레시피 (REV.51) — recipe.py 가 정본이다 ──────────────────
    from pv_preprocess import recipe, campaign
    p.rows("STRUCTURE_RECIPES", recipe.literal_rows(), indent="    ")
    # SG-301 반출롤러 점유 — 설계·PLC·검증 표의 문구가 campaign 값을 따른다
    p.one(r"SG-301 반출롤러 점유 [\d.]+ s",
          lambda m: f"SG-301 반출롤러 점유 {campaign.sg_occupancy_s():g} s")

    # ── 레시피 버퍼 용량 — handoff.py 가 정본이다 ─────────────────────────
    # 3D 는 캐리지를 **물리 행**으로 세어 R-A 50 / R-B 50 이었고, 완충시간을 내는
    # `handoff.py` 는 **레시피 배분**으로 세어 75 / 25 였다. 같은 하드웨어를 두
    # 문서가 다르게 읽고 있었던 것이고, 화면은 50 을 띄우는데 사양서의 완충시간은
    # 75 에서 나왔다. GA 시트가 B 열 스테이지 자리를 「R-A 스테이지 캐리지
    # (B열 · 레시피 재배분)」 = A-501C 로 못박고 있으므로 배분 쪽이 설계 의도다.
    # 두 곳이 갈리지 않게 여기서 찍는다.
    from pv_preprocess import handoff
    _mod = {"A": handoff.BUFFER_CARRIAGES[0], "B": handoff.BUFFER_CARRIAGES[1], "H": 1}
    _cap = {"A": handoff.BUFFER_RA_SLOTS, "B": handoff.BUFFER_RB_SLOTS,
            "H": handoff.BUFFER_HOLD_SLOTS}
    p.one(r"BUF_SLOT=\d+,BUF_CAP=\{[^}]*\},BUF_MOD=\{[^}]*\}",
          lambda m: f"BUF_SLOT={handoff.SLOTS_PER_CARRIAGE},"
                    + "BUF_CAP={" + ",".join(f"{k}:{v}" for k, v in _cap.items()) + "},"
                    + "BUF_MOD={" + ",".join(f"{k}:{v}" for k, v in _mod.items()) + "}")

    # AFR 셀이 패널을 받는 시각 — 3D 애니메이션의 `nt` 다. 리터럴로 박혀 있었고,
    # REV.58 이 JBR 칸을 4 → 7 s 로 늘려 인계가 85 → 94 s 로 밀렸는데도 85 로
    # 남아 있었다 — 그 9 s 동안 AFR 이 아직 오지 않은 패널을 잡고 움직였다.
    # 이제 모델이 정한다: 투입 구간 + JBR 점유가 곧 이 셀의 시작이다.
    p.one(r"\bvar nt=[\d.]+,",
          lambda m: f"var nt={campaign.INFEED_S + campaign.JBR_S:g},")

    # 종단 체류 — 화면 두 곳이 아직 124 를 말하고 있었다. `ci`(=nt+Lr)는 3D 가
    # 계산해 쓰는데, 통합 헤더 배지와 서보 패널의 분모는 **글자로 박혀** 있어
    # REV.58·59 가 JBR 칸을 옮길 때 따라오지 못했다. 여기서 찍어 다시 갈라지지 않게 한다.
    p.one(r"ONE PLANT · [\d.]+ s TRACE",
          lambda m: f"ONE PLANT · {campaign.total_dwell_s():g} s TRACE")
    p.one(r"stage\.time\.toFixed\(1\) \+ ' / [\d.]+ s'",
          lambda m: f"stage.time.toFixed(1) + ' / {campaign.total_dwell_s():.1f} s'")

    # ── 열수지 — 반내 발열은 서보 일람에서 나온다 ────────────────────────
    # 이름표도 모델에서 찍는다 — "셀 분전반 7면" 처럼 반 수가 박힌 문구가 있어,
    # 반이 합쳐지면 값만 고쳐서는 도면이 옛 이야기를 계속 한다 (REV.52).
    for src in thermal.heat_sources():
        p.one(rf"(\['{re.escape(src.tag)}', ')[^']*(', )[\d.]+(, '[^']*', '[^']*', '[^']*', )[\d.]+\]",
              lambda m, src=src: f"{m.group(1)}{src.equipment}{m.group(2)}{src.loss_kw}"
                                 f"{m.group(3)}{src.cooler_kw}]")
    loads = thermal.cabinet_loads()
    p.rows("THERMAL_CABINETS",
           [(panel, kw, "열교환기" if thermal.cabinet_needs_exchanger(panel)
             else ("필터팬" if kw > 0 else "— (전동기 없음)"))
            for panel, kw in loads.items()])

    DRAWING.write_text(p.text, encoding="utf-8")
    print(f"도면 리터럴 재생성 — {p.changed}곳 갱신 "
          f"(존 {len(layout.ZONE_SEED)}개 · 전장 {layout.plant_envelope_mm()[0]:,} mm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
