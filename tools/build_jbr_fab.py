# -*- coding: utf-8 -*-
"""JBR-201 제작 도면집 — 부품도 · 조립도 · 체결 · 조립 순서 · 검사.

`src/pv_preprocess/jbr_fabrication.py` 가 정본이다. 여기서는 그 데이터로 부품마다
3면도(치수·두께·구멍)를, 조립체마다 분해도·부품표·체결표·조립 순서·검사표를,
그리고 총괄 사양과 집계·검산을 한 문서로 찍는다.

    PYTHONPATH=src python tools/build_jbr_fab.py

**그리는 코드는 투입 구간 도면집(`build_infeed_fab.py`) 것을 그대로 쓴다.** 두 셀
도면이 같은 모양이어야 현장이 한 가지 읽는 법만 익히면 되고, 3면도·분해도를 두 벌
유지하면 한쪽만 고쳐지기 때문이다. 자료형도 `fabrication.Part/Assembly` 로 같다.

멱등이다. `tests/test_pv_jbr_fab.py` 가 커밋된 파일과 생성 결과를 견주고, 부품표에
이미 있는 값(외형·재질·수량·두께 10 품목)과도 견준다.
"""

from __future__ import annotations

import contextlib
import html
import pathlib
import re
import sys
from collections.abc import Iterator

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_infeed_fab as bif  # noqa: E402  — 그리는 코드를 빌려 온다
import build_jbr_closeup as bjc  # noqa: E402  — 운동식·칼날 사양 파서를 빌려 온다
from pv_preprocess import campaign, fabrication as fab, handoff  # noqa: E402
from pv_preprocess import jbr_fabrication as jf  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-jbr-fab.html"
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"


def plant_values() -> dict[str, object]:
    """검산이 쓰는 값 — 전부 통합 설계도에서 읽는다. 손으로 옮기면 갈린다."""
    text = PLANT.read_text(encoding="utf-8")
    M = bjc.model(text)
    mo = M["motion"]
    lo, hi = mo["shear"]
    stroke = (mo["openWide"] - mo["openShut"]) * 1000.0
    heads = tuple(float(z) for z in re.findall(
        r"part\('HD-\d',[^\]]*\],\s*\[[^,]+,[^,]+,\s*(-?[\d.]+)\]", text))
    pl = re.search(r"part\('PLATEN',[^\[]*\[([\d.]+),\s*[\d.]+,\s*([\d.]+)\]", text)
    return {
        "stroke_mm": stroke, "shear_s": hi - lo, "shear": (lo, hi),
        "tip_mm": M["bladeTipMm"], "wedge_deg": M["bladeWedgeDeg"],
        "cut_mm": M["cutMm"], "cut_tol_mm": M["cutTolMm"],
        "head_z": heads, "platen": (float(pl.group(1)), float(pl.group(2))),
    }

esc, n, table = bif.esc, bif.n, bif.table


@contextlib.contextmanager
def jbr_materials() -> Iterator[None]:
    """빌려 온 그리기 함수들이 `fab.MATERIALS` 를 직접 본다. 이 셀 재질(공구강·7075)은
    거기 없으므로 호출하는 동안만 얹었다가 되돌린다.

    되돌리는 것이 중요하다 — 같은 파이썬 프로세스에서 투입 구간 도면집도 찍히는데,
    거기 재질표에 이 셀 재질이 섞이면 그쪽 멱등 시험이 깨진다. 실제로 시험은 두
    생성기를 한 프로세스에서 부른다.
    """
    saved = dict(fab.MATERIALS)
    fab.MATERIALS.update(jf.JBR_MATERIALS)
    try:
        yield
    finally:
        fab.MATERIALS.clear()
        fab.MATERIALS.update(saved)


def sheet_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for a in jf.ASSEMBLIES:
        for i, p in enumerate(a.parts, start=1):
            out[p.tag] = f"{a.sheet}-P{i:02d}"
    return out


def status_block() -> str:
    """값이 어디서 왔는지 — 이 도면집을 읽기 전에 알아야 하는 것."""
    known = [p for p in jf.parts() if p.t and _bom_states_thickness(p.tag)]
    return (
        '<section class="card"><h2>0. 이 도면집의 지위 — 읽기 전에</h2>'
        '<p>여기 적힌 값은 출처가 셋으로 갈린다. 섞어 읽으면 안 된다.</p>'
        + table(["출처", "무엇이", "지위"], [
            ["<b>부품표에서 온 것</b>",
             f"외형 (L·W·H) · 재질 · 수량 · 공차, 그리고 재질란이 두께를 적어 둔 {len(known)} 품목"
             " (<span class='mono'>RHS 100×100×6</span> · <span class='mono'>STS304 t1.5</span> 꼴)",
             "통합 설계도가 정한 값이다. 여기서 다시 정하지 않고, 시험이 글자 단위로 견준다"],
            ["<b>하중에서 나온 것</b>",
             f"칼날 반력 {jf.BLADE_THRUST_KN:g} kN/헤드 ({jf.HEADS} 헤드 {jf.TOTAL_THRUST_KN:g} kN)를 받는 체결부의 볼트 개수",
             "아래 6 절이 전단 용량과 견줘 이용률을 낸다. 1.0 을 넘으면 시험이 깨진다"],
            ["<b>관례로 고른 것</b>",
             "나머지 두께와 <b>구멍 배치 전부</b>",
             "기계 프레임 관례(가장자리 ≥ 1.5 d · 피치 ≥ 3 d)와 이 셀의 정밀도 요구에서 골랐다. "
             "구조 검증(45 kN 편심·잼 FEA · 앵커 인발)이 오면 <b>정본만 고치고 다시 찍는다</b>"],
        ])
        + '<p class="note"><b>구멍은 부품표에 하나도 없었다.</b> 그것이 이 문서가 있는 이유다 — '
          '외형만으로는 만들 수 없고, 뚫는 자리를 정하지 않으면 조립 순서도 검사 항목도 쓸 수 없다. '
          f'이 도면집이 새로 정한 것은 구멍 {n(jf.hole_tally())} 개와 체결 '
          f'{n(sum(j.qty for j in jf.joints()))} 곳, 그리고 조립 순서·검사 항목이다.</p>'
        '</section>'
    )


#: 부품표 재질란이 두께를 적어 둔 품목 — 정본이 그 값을 그대로 쓰는지 시험이 본다.
BOM_THICKNESS: dict[str, float] = {
    "JB-FR-002": 6, "JB-FR-003": 6, "JB-FR-005": 1.6, "JB-CV-005": 2, "JB-MX-006": 8,
    "JB-HD-012": 1.2, "JB-CB-004": 1.5, "JB-CB-005": 1.5, "JB-WH-001": 1.5, "JB-WH-002": 1.5,
}


def _bom_states_thickness(tag: str) -> bool:
    return tag in BOM_THICKNESS


def load_table() -> str:
    rows = []
    for c in jf.checks():
        mark = '<b class="ok">여유</b>' if c["ok"] else '<b class="bad">초과</b>'
        rows.append([esc(c["name"]), f'{c["n"]}×{esc(c["bolt"])} {esc(c["cls"])}',
                     f'{c["load_kn"]:g} kN', f'{c["capacity_kn"]:g} kN',
                     f'{c["utilisation"]:.2f}', mark, esc(c["why"])])
    return (
        '<h3>6.1 하중을 받는 체결부</h3>'
        + table(["체결부", "볼트", "걸리는 힘", "허용", "이용률", "판정", "왜 그 힘인가"], rows)
        + f'<p class="note"><b>이용률이 낮은 것이 여유가 많다는 뜻은 아니다.</b> '
          f'0.01–0.23 이라는 것은 <b>볼트 개수를 정하는 것이 강도가 아니라는 뜻</b>이다. '
          f'이 셀의 체결부는 헤드 datum ±0.10 · 레일 평행 0.05 를 지켜야 해서 강성과 프레팅으로 '
          f'개수가 정해지고, 강도는 그 뒤에 따라온다. 그래서 이 표는 「볼트를 하중으로 정했다」가 '
          f'아니라 <b>「하중이 볼트를 정하지 않는다」를 확인하는 표</b>다 — 이용률이 1 에 가까워지면 '
          f'그때부터 강도가 지배하므로 시험이 그 경계를 지킨다. 안전율 {jf.SHEAR_SAFETY:g} · '
          f'전단항복 0.6·f<sub>y</sub> 기준.</p>'
        + '<p class="note"><b>박리 반력은 바닥에 닿지 않는다.</b> 칼날이 패널을 아래로 누르면 '
          '패널은 지지정반을, 정반은 베이스를 누르고, 그 힘은 베이스 → X축 빔 → 브리지 → 헤드 → '
          '칼날로 되돌아온다. <b>닫힌 고리</b>라 앵커로 새지 않는다. 그래서 앵커가 보는 것은 '
          f'45 kN 이 아니라 브리지가 설 때의 수평 관성력 '
          f'{jf.CARRIAGE_MASS_KG * jf.X_DECEL_MS2 / 1000:.1f} kN 뿐이다.</p>'
    )


def findings() -> str:
    """도면집을 찍으면서 스스로 드러난 것. 고치지 않고 올린다."""
    m = jf.mass_check()
    lc = jf.lift_check()
    takt = campaign.summary()["takt_s"]
    mass_mark = '<b class="ok">안</b>' if m["ok"] else '<b class="bad">초과</b>'
    lift_mark = '<b class="ok">가능</b>' if lc["ok"] else '<b class="bad">부족</b>'
    rows = [[esc(c["name"]), esc(c["bolt"]), f'{c["need_mm"]:g} mm', f'{c["slack_mm"]:+g} mm',
             '<b class="ok">넘음</b>' if c["ok"] else '<b class="bad">짧다</b>']
            for c in jf.anchor_check()]
    return (
        '<h3>6.2 앵커 로드 길이</h3>'
        + table(["체결부", "지정", "필요", "여유", "판정"], rows)
        + '<p class="note">필요 길이 = 매입 + 베이스플레이트 + 그라우트 + 평와셔 + 너트 + 나사산 여유. '
          '기초 위로 나오는 부속을 안 세면 너트가 안 걸린다. 규칙과 표준 공급 계열은 '
          '<span class="mono">fasteners</span> 것을 그대로 쓰므로 두 셀이 다른 답을 낼 수 없다 — '
          '<b>길이를 고르지 않고 계산한다.</b> 처음 손으로 적었을 때는 5 건 중 4 건이 짧았다.</p>'
        + '<h3>6.3 중량 — 도면의 「약 2.2 t」와 견준다</h3>'
        + table(["항목", "값", "판정"], [
            ["제작품 총중량 (가드 포함)", f'{n(m["fabricated_kg"])} kg', "—"],
            ["안전가드·리젝트 (A08) — 제 기초에 따로 선다", f'{n(m["guard_kg"])} kg', "본체에서 뺀다"],
            ["<b>본체 제작품 중량</b>", f'<b>{n(m["body_kg"])} kg</b>', "—"],
            ["통합 설계도 「JBR 본체 약 2.2 t」", f'{n(m["plant_kg"])} kg', mass_mark],
            ["차", f'{n(m["over_kg"])} kg ({m["ratio"]}배)', "—"],
        ])
        + f'<p class="note warn"><b>본체가 도면의 약 2.2 t 보다 {m["ratio"]}배 무겁다.</b> '
          '부품표에는 중량 열이 없고 「약 2.2 t」 한 줄이 전부라, 그 값은 부품에서 합산된 것이 '
          '아니라 어림이다. 이 도면집이 처음으로 부품에서 합산했다 — 구매품(서보·감속기·실린더·'
          '집진기)은 아직 안 들어간 값이라 실제로는 더 나간다. '
          '<b>바닥 하중·앵커·반입 계획이 이 값으로 다시 서야 한다.</b> 기구를 가볍게 하는 쪽으로 '
          '고칠지, 도면의 어림값을 고칠지는 구조 검증에서 정한다 — 여기서 한쪽으로 정하지 않았다.</p>'
        + '<h3>6.4 Z 승강 실린더 — 순차로 바꾸자 재고 보어가 살아났다</h3>'
        + table(["항목", "값"], [
            ["함께 오르내리는 것 (승강 플레이트 · Y 캐리지 · 헤드 1 기 · 가이드로드)",
             f'제작품 {n(jf.moving_mass_kg())} kg + 헤드 구매품 추정 {jf.HEAD_COMMERCIAL_KG:g} kg '
             f'= <b>{n(lc["moving_kg"])} kg = {lc["need_kn"]:g} kN</b>'],
            [f'부품표 JB-MZ-002 Ø{jf.LIFT_BORE_MM:g} × {jf.LIFT_COUNT} · {jf.AIR_MPA_MIN:g} MPa',
             f'{lc["force_kn"]:g} kN — 이용률 <b>{lc["utilisation"]:g}</b> {lift_mark}'],
            ["수직 승강 목표 여유", f'≥ {jf.LIFT_SAFETY:g} (실링·가이드 마찰 · 가속 · 행정 중 압력 강하)'],
            ["그 여유를 만족하는 최소 보어 (2 개 기준)",
             f'Ø{lc["bore_needed_mm"]:.0f} → 재고 Ø{jf.LIFT_BORE_MM:g} 로 충분'],
            [f'규정 하한 {jf.AIR_MPA_MIN:g} MPa 에서의 여유', f'<b>{lc["margin"]:g}</b> (목표 {jf.LIFT_SAFETY:g})'],
        ])
        + f'<div class="note ok"><b>REV.56 의 소견이 스스로 풀렸다 — 실린더를 키워서가 아니라 '
          f'매다는 것을 줄여서다.</b> 그때 이 절은 「Ø{jf.LIFT_BORE_MM:g} 두 개로는 못 든다」였고 '
          f'이용률이 1 을 넘었다. 그것은 승강축의 문제가 아니라 <b>헤드 세 기를 한 판에 매단 '
          f'구성의 결과</b>였다. 헤드 두 기와 그 Y 캐리지가 빠지고 승강 플레이트가 '
          f'1,820×2,180 에서 760×640 으로 줄면서 가동 질량이 절반 밑으로 내려갔고, 이용률이 '
          f'{lc["utilisation"]:g} · 여유 {lc["margin"]:g} 가 됐다. <b>보어를 키우는 대신 드는 것을 '
          f'줄인 셈이다.</b> 누가 다시 3 헤드로 되돌리면 이 소견이 그대로 돌아온다.</div>'
        + f'<div class="note"><b>다만 이 중량은 여전히 하한이다.</b> 제작품만 셀 수 있어서, 헤드에 '
          f'실려 같이 오르내리는 구매품(실린더·로드셀·진공컵·센서)은 부품표에 중량 열이 없다. '
          f'여기서는 헤드당 {jf.HEAD_COMMERCIAL_KG:g} kg 로 잡아 얹었다 — 그 값이 두 배가 되어도 '
          f'이용률은 {jf.lift_check(include_commercial=True)["utilisation"]:g} 근처에 머문다.</div>'
        + '<h3>6.4.1 그래도 지지점 수는 열려 있다 — 힘이 아니라 판의 문제다</h3>'
        + table(["구성", f"추력 @{jf.AIR_MPA_MIN:g} MPa", "이용률", "여유", "공기", "로드락 1 개당", "판정"],
                [[f'{o["count"]}×Ø{o["bore_mm"]:.0f}', f'{o["force_kn"]:g} kN',
                  f'{o["utilisation"]:g}', f'{o["margin"]:g}',
                  f'{n(o["air_nl_cycle"] * 3600 / takt)} NL/h', f'{o["rod_lock_kn"]:g} kN',
                  '<b class="ok">OK</b>' if o["ok"] else '<b class="bad">부족</b>']
                 for o in jf.lift_options()])
        + f'<div class="note"><b>힘은 풀렸지만 판을 두 점으로 드는 것은 여전히 기구 문제다.</b> '
          f'다만 판이 760 × 640 mm 로 줄면서 <b>그 문제도 같이 작아졌다</b> — 1,820 × 2,180 을 '
          f'두 점으로 들 때와는 처짐·기울기의 크기가 다르다. 위 표에서 재고 구성 '
          f'2×Ø{jf.LIFT_BORE_MM:g} 의 로드락 부담은 {lc["rod_lock_kn"]:g} kN 이고, 네 점으로 '
          f'가면 절반이 된다. <b>지금은 두 점으로 간다</b> — 판 처짐이 POM 기준 슈의 '
          f'플로팅 ±8 mm 안에 드는지는 구조 검증에서 확인할 일이고, 그때 네 점이 필요하면 '
          f'같은 표에서 고르면 된다.</div>'
        + '<div class="note"><b>내려올 때는 중력이 같은 편이다.</b> 하강에서는 자중 '
          f'{lc["need_kn"]:g} kN 이 더해지므로 배기를 조여 속도를 잡아야 하고, 보어가 클수록 조일 '
          '공기가 많다. 정지 유지는 무전원 로드락(JB-MZ-004)이 하지만 <b>드는 것과 잡는 것은 다른 '
          '일</b>이라, 로드락 용량은 위 표의 「로드락 1 개당」으로 따로 확인해야 한다. '
          '부품표에 카운터밸런스(스프링·평형추·압력 회로)가 없다 — 있었다면 실린더가 동적 몫만 '
          '맡으면 되므로 이 표가 통째로 달라진다. <b>의도에 있었는지가 미결이다.</b></div>'
    )


def review() -> str:
    """설계 검토 — 부품표·서보·운동식을 곱해 보고 안 맞는 것을 낸다.

    이 절은 「무엇을 만든다」가 아니라 **「만들 수 있는가」**를 묻는다. 답이 아니오면
    여기서 고치지 않는다 — 고치는 것은 설계 결정이고, 이 문서가 할 일은 재는 것이다.
    """
    V = plant_values()
    takt = campaign.summary()["takt_s"]
    pa = jf.peel_axis_check(V["stroke_mm"], V["shear_s"])
    bg = jf.blade_geometry_check(V["tip_mm"], V["wedge_deg"], V["cut_mm"], V["cut_tol_mm"])
    pneu = [jf.pneumatic_option(b, V["stroke_mm"], takt) for b in (63.0, 80.0, 100.0)]
    sc = jf.support_check(campaign.PANEL_LENGTH_MM, campaign.PANEL_WIDTH_MM,
                          V["platen"][0], V["platen"][1], V["head_z"])
    bm = jf.bridge_mode((100.0, 150.0), 8.0, 2_500.0, jf.moving_mass_kg(), jf.X_DECEL_MS2)
    ss = jf.scissor_check(63.0, jf.AIR_MPA_MIN, 4.0)
    lives = [jf.ballscrew_life(x, V["stroke_mm"], takt) for x in (15.0, 5.0, 2.0)]
    bad = lambda ok: '<b class="ok">성립</b>' if ok else '<b class="bad">불성립</b>'

    out = ['<h3>6.5 박리축 — 왜 서보·볼스크루를 버렸는가</h3>']
    out.append(
        '<p class="note"><b>이 절과 6.6 절은 이미 내린 결정의 근거다.</b> REV.57 에서 박리축은 '
        '<b>Ø80 공압 실린더</b>가 됐다(JB-HD-002). 아래 계산은 그 전 구성(0.75 kW 서보 + '
        '20×5 볼스크루)이 왜 성립하지 않았는지를 남겨 둔 것이다 — 되돌리려는 사람이 같은 자리를 '
        '다시 밟지 않도록.</p>')
    out.append(table(["항목", "값"], [
        ["칼날 행정 (운동식 <span class='mono'>openWide→openShut</span>)", f'{n(V["stroke_mm"])} mm'],
        ["박리 구간 (스테이지 <span class='mono'>shear</span>)", f'{n(V["shear"][0])} – {n(V["shear"][1])} s = {n(V["shear_s"])} s'],
        ["평균 · 피크 속도", f'{pa["v_mean_mms"]:g} · {pa["v_peak_mms"]:g} mm/s'],
        [f'볼스크루 {jf.PEEL_SCREW_LEAD_MM:g} mm 리드 회전수', f'{n(pa["screw_rpm"])} rpm'],
        [f'감속 1:{jf.PEEL_GEAR_RATIO:g} → <b>모터 회전수</b>',
         f'<b>{n(pa["motor_rpm"])} rpm</b> (0.75 kW 급 통상 상한 {n(pa["motor_max_rpm"])}) — {bad(pa["ok"])}'],
    ]))
    out.append(
        f'<div class="note warn"><b>이 구동계로는 이 운동을 못 낸다.</b> 힘을 하나도 안 넣고 '
        f'행정과 시간만 나눈 결과라 가정이 없다 — 모터가 상한의 <b>{pa["over"]}배</b>로 돌아야 한다. '
        f'뿌리는 <b>한 축에 두 가지 일을 시킨 것</b>이다: {n(V["stroke_mm"])} mm 중 실제로 접착을 '
        f'자르는 구간은 칼날이 박스 밑으로 드는 마지막 10–20 mm 뿐이고 나머지는 공주행인데, '
        f'급속 이송과 고추력 절삭은 최적점이 반대라 한 드라이브로 둘 다 못 한다. '
        f'REV.57 에서 순차로 바뀌며 박리 창이 6.0 → {n(V["shear_s"])} s 로 줄어 <b>모순이 더 '
        f'커졌다</b> — 같은 45.0 s 안에 세 번 밀어야 하기 때문이다. 공압은 이 자리에서 '
        f'문제가 되지 않는다: {n(V["stroke_mm"] / V["shear_s"])} mm/s 는 실린더 통상 범위 안이다.</div>')
    out.append(
        f'<div class="note warn"><b>움직이는 동안에는 {jf.JAM_TRIP_KN:g} kN 임계가 트립되지 않는다.</b> '
        f'{pa["v_mean_mms"]:g} mm/s 에서 이 구동계가 낼 수 있는 최대 힘은 '
        f'<b>{pa["force_at_speed_kn"]:g} kN</b> 이다 (0.75 kW × 효율 {jf.DRIVETRAIN_EFF} ÷ 속도). '
        f'힘이 쌓이는 것은 속도가 0 으로 죽는 잼에서뿐이므로, 그 임계는 공정 감시가 아니라 '
        f'<b>잼 보호</b>다. 그러면 공정창은 정의된 적이 없다.</div>')

    out.append('<h3>6.6 정격 작업 박리력이 없다 — 공압으로 옮기며 급함이 줄었다</h3>')
    out.append(table(["가정한 작업력", "L10 회전", "사이클", "가동 시간", "연수 (8,000 h/년)"],
                     [[f'{c["working_kn"]:g} kN', f'{c["rev_life"]:.3g} rev', f'{n(c["cycles"])}',
                       f'{n(c["hours"])} h', f'<b>{c["years_8000h"]}</b> 년'] for c in lives]))
    out.append(
        f'<div class="note warn"><b>5 주와 46 년 사이다.</b> C ≥ {jf.BALLSCREW_C_KN:g} kN · '
        f'사이클당 {n(V["stroke_mm"] / jf.PEEL_SCREW_LEAD_MM)} rev · 택트 {takt:.2f} s 기준. '
        f'{jf.JAM_TRIP_KN:g} kN 은 <b>임계이지 작업력이 아닌데</b>(원본: 「소프트웨어 제한」·'
        f'「{jf.JAM_TRIP_KN:g} kN/헤드에서 자동 후퇴」) 서보 선정·볼스크루·FEA·앵커가 모두 그 값에 '
        f'매달려 있었다. <b>이 표가 박리축을 공압으로 옮긴 직접적인 이유다</b> — 5 주와 46 년 '
        f'사이에서 조달과 보전 계획을 세울 수는 없다. 실린더로 가면 수명이 주행거리로 정해져 '
        f'이 표 자체가 사라진다(6.7 절). '
        f'<b>그렇다고 작업력이 필요 없어진 것은 아니다</b> — 보어 선정, 칼날·POM 슈 마모, '
        f'잼 임계와 실제 작업점의 거리는 여전히 그 값을 요구한다. 다만 <b>급한 정도가 '
        f'달라졌다</b>: 이산 보어 계열에서는 ±20 % 오차로도 답이 갈리지 않는다(7 절). '
        f'정본의 <span class="mono">WORKING_PEEL_KN</span> 이 비어 있는 것이 그 자리다.</div>')

    out.append('<h3>6.7 칼날 랜드 두께 · <b>채택 구동(공압)</b></h3>')
    out.append(table(["항목", "값"], [
        ["랜드 두께 (부품표 JB-HD-008 「팁 0.8 mm」 — <b>반경이 아니라 두께</b>)",
         f'{bg["tip_mm"]:g} mm · 쐐기 {bg["wedge_deg"]:g}°'],
        ["상용 제거기 통상 하한", f'{bg["min_mm"]:g} mm — {bad(bg["ok"])}'],
        ["날끝 반경(에지 준비)", "사양에 없다 — 부품표 수준에서는 통상이라 소견으로 올리지 않는다"],
    ]))
    out.append(
        '<div class="note"><b>이 값은 정상 범위다.</b> 실리콘만 자르는 날이라면 얇게 갈수록 '
        '좋지만, 이 칼날은 <b>구리 리본도 끊어야</b> 해서 얇으면 말리거나 깨진다. 상용 '
        f'제거기가 {bg["min_mm"]:g} mm 이상을 쓰는 이유가 그것이고 {bg["tip_mm"]:g} mm 는 그 안이다. '
        '<b>한때 이 값을 날끝 반경으로 잘못 읽고 「절입보다 무디다」고 올렸다가 철회했다</b> — '
        '지금 이 검산은 반대쪽을 지킨다. 누가 얇게 바꾸면 여기서 걸린다.</div>')
    out.append(table(["보어", "추력 (0.5–0.6 MPa)", f'주행 수명 (패널당 {pneu[0]["strokes_per_panel"]} 왕복)',
                      "공기"],
                     [[f'Ø{o["bore_mm"]:g}' + (' <b>← 채택</b>' if o["bore_mm"] == 80.0 else ''),
                       f'{o["force_kn"][0]:g} – {o["force_kn"][1]:g} kN',
                       f'{o["years"][0]:g} – {o["years"][1]:g} 년', f'{n(o["air_nl_h"])} NL/h']
                      for o in pneu]))
    out.append(
        f'<div class="note"><b>상용 제거기는 이 축을 공압 실린더로 민다.</b> 그렇게 보면 '
        f'6.5·6.6 절의 모순이 파라미터 문제가 아니라 <b>구동 방식 선택 문제</b>로 바뀐다. '
        f'속도 {n(V["stroke_mm"] / V["shear_s"])} mm/s 는 공압 통상 범위(100–500) 안이고, '
        f'절입은 POM 기준 슈가 기계적으로 잡으므로 <b>축에 위치 제어가 필요 없다</b>. '
        f'무엇보다 <b>볼스크루 수명은 하중의 3 제곱에 걸리지만 실린더 수명은 주행거리에 '
        f'걸린다</b> — 작업력을 ±30 % 안에서 모르는 상태(노화 폐패널이라 분포다)에서 이 차이가 '
        f'결정적이다. 힘을 몰라도 수명이 정해지고, 모자라면 압력을 올리면 되고, 과하면 그냥 '
        f'멈춘다. 공기는 설비 용량 25,200 NL/h 안에 든다. '
        f'서보가 사 주는 것은 <b>힘 감시와 프로파일</b>뿐이라, 로드셀(JB-HD-005)은 남기고 '
        f'구동만 실린더로 옮겼다.</div>')
    out.append(
        f'<div class="note warn"><b>순차는 공짜가 아니다 — 같은 실린더가 패널당 '
        f'{pneu[0]["strokes_per_panel"]} 번 왕복한다.</b> 동시 구성에서는 한 번이었다. '
        f'주행거리가 세 배라 수명이 <b>{pneu[1]["years"][0]:g}–{pneu[1]["years"][1]:g} 년</b>으로 '
        f'짧아졌고, 공기도 {n(pneu[1]["air_nl_h"])} NL/h 로 세 배다. 실린더는 소모품이므로 '
        f'교환 주기가 <b>보전 계획에 들어가야 하는 값</b>이 됐다 — 헤드 Y 축도 같은 이유로 '
        f'주행거리가 늘었다(레일 2,020 → 2,300, JB-MY-001).</div>')
    out.append('<h3>6.8 지지 — 패널이 정반 위에 다 올라가는가</h3>')
    out.append(table(["항목", "값"], [
        ["패널", f'{n(campaign.PANEL_LENGTH_MM)} × {n(campaign.PANEL_WIDTH_MM)} mm'],
        ["지지정반 JB-SP-001", f'{n(V["platen"][0])} × {n(V["platen"][1])} mm'],
        ["받쳐지지 않는 돌출", f'X {sc["over_l_mm"]:g} mm/측 · Z {sc["over_w_mm"]:g} mm/측'],
        ["헤드 z (GA)", " · ".join(f"{z:+g}" for z in V["head_z"])],
        ["정반 반폭", f'{sc["platen_half_w_mm"]:g} mm — 헤드 {len(sc["heads_outside"])} 기가 '
                    f'{sc["worst_out_mm"]:g} mm 바깥 {bad(sc["ok"])}'],
    ]))
    out.append(
        '<div class="note warn"><b>정반이 패널보다 작다 — 다만 헤드는 이제 정반 안에 선다.</b> '
        'REV.56 에서는 헤드 1·3 이 정반 반폭 600 밖 20 mm 에서 눌렀다. 헤드가 한 기가 되면서 '
        '<b>그 절반은 없어졌다</b> — 헤드는 검출 좌표로 가지만 박스는 정반 위에 있다. '
        f'남은 것은 패널이 정반보다 X {sc["over_l_mm"]:g} · Z {sc["over_w_mm"]:g} mm/측 큰 것이다. '
        '프레임이 붙은 채 들어오므로(프레임 제거는 하류 AFR-101 이다) 프레임이 그 몫을 '
        '나르긴 하지만 <b>그 전제가 도면에 없다</b>. 정반을 넓히든지 프레임 지지를 '
        '명시하든지 둘 중 하나다.</div>')

    out.append('<h3>6.9 브리지 동특성 · 가위</h3>')
    out.append(table(["항목", "값"], [
        [f'브리지 RHS 150×100×8 · 스팬 2,500 · 가동부 {n(jf.moving_mass_kg())} kg',
         f'k = {n(bm["k_n_mm"])} N/mm · <b>1 차 {bm["f_hz"]:g} Hz</b>'],
        [f'가감속 {bm["accel_ms2"]:g} m/s² 관성력 {n(bm["inertia_force_n"])} N',
         f'탄성 처짐 <b>{bm["deflection_mm"]:g} mm</b> (헤드 datum 공차 ±0.10)'],
        [f'가위 Ø{ss["bore_mm"]:g} @ {ss["air_mpa"]:g} MPa', f'{n(ss["force_n"])} N · 4 mm² 구리 전단 '
         f'{n(ss["need_n"])} N → 여유 {ss["margin"]:g} (레버비 미기재)'],
    ]))
    out.append(
        f'<div class="note ok"><b>브리지 소견도 매다는 것을 줄여서 풀렸다.</b> REV.56 에서 이 빔은 '
        f'X 감속에서 <b>0.196 mm</b> 처지고 1 차 모드가 18 Hz 였다 — 헤드 datum ±0.10 의 두 배다. '
        f'헤드 두 기를 덜어 내자 같은 RHS 150×100×8 이 <b>{bm["deflection_mm"]:g} mm · '
        f'{bm["f_hz"]:g} Hz</b> 로 규격 안에 들어왔다. 처짐은 어차피 정정 시간의 문제이므로 '
        f'0.10 mm 아래에서는 정정이 사실상 사라진다. <b>빔 단면 방향은 여전히 도면이 정해야 '
        f'한다</b> — 약축으로 돌려 세우면 다시 나빠진다. 가위는 레버비가 도면에 없어 1:1 로 '
        f'본 값이라 여유 {ss["margin"]:g} 는 하한이다 — 케이블 반경이 운동식에 12 mm 로 잡혀 '
        f'있어 4 mm² PV 케이블보다 굵다.</div>')
    return "".join(out)


def bench() -> str:
    """벤치 시험 계획 — 공압으로 가면 재는 것이 힘이 아니라 압력이 된다."""
    lo, hi = jf.BENCH_PRESSURE_MPA
    rows = [[f"Ø{b:g}", f'{3.14159 / 4 * b ** 2 * jf.AIR_MPA_MIN / 1000:.2f} kN',
             f'{3.14159 / 4 * b ** 2 * jf.AIR_MPA_MAX / 1000:.2f} kN']
            for b in (63.0, 80.0, 100.0, 125.0)]
    return (
        '<p>서보·볼스크루를 전제하면 시험의 목적은 <b>정격 작업력을 ±30 % 안에서 재는 것</b>'
        '이었다 — L10 이 하중의 3 제곱에 걸리니까. <b>공압으로 가면 목적이 바뀐다.</b> 실린더 '
        '수명은 주행거리에 걸리므로 힘을 정밀하게 알 필요가 없고, 필요한 것은 「어느 보어면 '
        '되는가」 하나다. 보어는 이산값이라 훨씬 거친 측정으로 충분하다.</p>'
        '<p><b>그래서 재는 것이 힘이 아니라 압력이다.</b> 실린더를 실제로 달고 압력을 올리다가 '
        '박스가 떨어지는 압력을 읽으면 그 값이 곧 보어 선정 입력이다 — 로드셀도 토크 계산도 '
        '필요 없다.</p>'
        + '<h3>7.1 어떻게 잡는가</h3>'
        + table(["항목", "내용", "왜 그렇게 잡는가"],
                [[f"<b>{esc(a_)}</b>", b_, c_] for a_, b_, c_ in jf.bench_plan()])
        + '<h3>7.2 무엇을 재는가 — 한 번의 시험이 미결 여럿을 닫는다</h3>'
        + table(["측정", "판정", "이 측정이 닫는 것"],
                [[esc(a_), esc(b_), esc(c_)] for a_, b_, c_ in jf.bench_measurements()])
        + '<h3>7.3 결과를 보어로 옮긴다</h3>'
        + table(["보어", f"{jf.AIR_MPA_MIN:g} MPa", f"{jf.AIR_MPA_MAX:g} MPa"], rows)
        + f'<p class="note">P95 분리력이 나오면 <span class="mono">jbr_fabrication.bore_for()</span> '
          f'가 표준 계열에서 그 힘을 {jf.AIR_MPA_MIN:g} MPa 에 내는 가장 작은 보어를 돌려준다 — '
          f'2.0 kN 이면 Ø80, 3.0 kN 이면 Ø100 이다. 계열이 이산값이라 <b>측정이 ±20 % 만 맞아도 '
          f'답이 갈리지 않는다</b>. 서보였다면 같은 오차가 수명을 두 배로 흔들었다.</p>'
        + '<div class="note"><b>이 시험이 답하지 못하는 것.</b> 30 사이클로는 <b>칼날 장기 수명</b>이 '
          '안 나온다(초기 마모만 본다). 셀 사이클타임·브리지 정정 시간·구조 피로도 여기서 나오지 '
          '않는다 — 그것들은 실기 run-at-rate 몫이다. 여기서 얻는 것은 <b>발주 전에 정해야 하는 '
          '것들</b>뿐이고, 그것이 이 시험을 지금 하는 이유다.</div>'
    )


def open_items() -> str:
    rows = [
        ["구조 검증이 없다",
         f"단면과 두께는 관례로 골랐다. {jf.TOTAL_THRUST_KN:g} kN 편심·잼 FEA 와 앵커 인발 "
         f"검토가 오면 정본만 고치고 다시 찍는다. 지금 값으로 만들지 말 것.", "GA 시트 release"],
        ["본체 중량이 도면과 다르다",
         f"부품에서 합산한 본체 {n(jf.mass_check()['body_kg'])} kg 대 도면 어림 2,200 kg. "
         "구매품은 아직 안 들어갔다.", "6.3 절"],
        ["Z 승강 판 처짐 — 두 점 지지로 갈 수 있는가",
         f"힘은 풀렸다(Ø{jf.LIFT_BORE_MM:g}×{jf.LIFT_COUNT} 이용률 "
         f"{jf.lift_check()['utilisation']:g} · 여유 {jf.lift_check()['margin']:g}). 남은 것은 "
         "판을 두 점으로 드는 처짐이 POM 기준 슈 플로팅 ±8 mm 안에 드는가다 — 구조 검증 몫이고, "
         "네 점이 필요하면 6.4.1 표에서 고르면 된다.",
         "6.4.1 절"],
        ["승강 카운터밸런스가 의도에 있었는가",
         "부품표에 스프링·평형추·압력 회로가 없다. 있었다면 실린더가 동적 몫만 맡으면 되므로 "
         "보어 표가 통째로 달라진다.", "6.4.1 절"],
        ["헤드 구매품 중량이 없다",
         f"승강 가동부를 {jf.HEAD_COMMERCIAL_KG:g} kg 추정으로 얹었다. 부품표에 중량 열이 "
         "생기면 <span class='mono'>HEAD_COMMERCIAL_KG</span> 를 0 으로 하고 실제 값을 센다.",
         "6.4 절"],
        ["<b>정격 작업 박리력이 없다</b>",
         f"{jf.JAM_TRIP_KN:g} kN 은 자동 후퇴 임계이지 작업 조건이 아니다. 공압으로 옮기며 "
         "수명이 주행거리로 정해져 <b>급함은 줄었지만 없어지지는 않았다</b> — 보어 확정, 칼날·POM "
         "슈 마모, 잼 임계와 작업점의 거리가 여전히 이 값을 부른다. 7 절 벤치가 그 한 줄을 "
         "가져온다. 정해지면 <span class='mono'>WORKING_PEEL_KN</span> 에 넣는다.",
         "6.6 절"],
        ["<b>박리 실린더 교환 주기</b>",
         f"순차라 같은 실린더가 패널당 {jf.BOXES_PER_PANEL} 번 왕복한다 — 동시 구성의 세 배다. "
         "Ø80 주행 수명이 1.6–3.9 년으로 <b>소모품이 됐다</b>. 교환 주기와 예비품 수량이 "
         "보전 계획에 들어가야 하고, 헤드 Y 축(레일 2,300)도 같은 이유로 주행거리가 늘었다.",
         "6.7 절"],
        ["<b>패널당 4.0 s 순차 창이 가정이다</b>",
         "박스 하나에 Y 이송 0.7 → 포획 0.5 → 박리 1.6 → 유지 0.2 → 재개방 0.4 → 이탈 0.2 → "
         "슈트 이송 0.3 → 투하 0.1 로 잡아 45.0 s 안에 세 번을 넣었다. 이 배분은 "
         "<b>실측이 아니라 배정</b>이다 — 벤치에서 박리 시간이 1.6 s 를 넘으면 셀 사이클타임이 "
         "먼저 깨진다.", "6.5 절 · 3D 운동식"],
        ["<b>정반이 패널보다 작다</b>",
         "정반 1,900×1,200 대 패널 2,500×1,400 — X 300 · Z 100 mm/측이 받쳐지지 않는다. "
         "헤드가 정반 밖에서 누르던 절반은 1 헤드로 없어졌다. 프레임 지지를 전제로 삼는다면 "
         "그 전제를 도면에 적어야 한다.", "6.8 절"],
        ["<b>수거함 용량이 반이 됐다</b>",
         "순차 배출은 박스를 한 줄로 내므로 광폭이 필요 없어져 1,320 → 640 mm 로 줄였다. "
         "용량이 180 → 90 L 라 <b>비움 주기가 두 배로 잦아진다</b> — 무인 운전 시간과 "
         "맞는지는 운영 계획이 정할 값이다.", "JB-WH-002"],
        ["<b>브리지 임시 호퍼 플랩</b>",
         "순차가 새로 요구한 부품(JB-WH-008). 헤드는 한 번에 하나만 들므로 놓을 자리가 있어야 "
         "하고, 없으면 박스마다 브리지를 슈트까지 왕복시켜야 한다. 플랩 구동·열림 확인 2 점과 "
         "박스가 걸렸을 때의 검출·복구가 미정이다.", "JB-WH-008"],
        ["가위 레버비가 없다",
         "Ø63 @0.5 MPa = 1,559 N 을 1:1 로 본 여유 1.95 는 하한이다. 운동식의 케이블 반경 12 mm 가 "
         "맞다면 도체가 훨씬 굵어 여유가 사라진다.", "6.9 절"],
        ["<b>순차가 닫은 것 — 되돌리면 같이 돌아온다</b>",
         "REV.56 의 미결 다섯 중 셋이 「3 헤드 동시」의 부산물이었다: 승강 실린더 부족(이용률 "
         f"1.19 → {jf.lift_check()['utilisation']:g}), 브리지 처짐 0.196 → 0.057 mm, 헤드가 "
         f"정반 밖. {jf.TOTAL_THRUST_KN:g} kN 하중 케이스도 45 kN 에서 내려왔다. "
         "<b>이것들은 고쳐서 닫힌 것이 아니라 구성이 바뀌어 닫힌 것이다</b> — 다시 3 헤드로 "
         "가면 그대로 돌아온다. 시험이 그 자리를 지킨다.", "REV.57"],
        ["칼날 수명",
         "SKD11 카세트의 교체 주기(장수)를 모른다. 시운전 run-at-rate 마모량에서 나온다.",
         "reliability.SPARES()"],
        ["절입 깊이 공정능력",
         f"하류 절결 허용치 {handoff.BACKSHEET_NOTCH_MAX_MM:g} mm 가 절입 공차 깊은 쪽과 같아 여유가 0 이다. "
         "목표 Cpk 와 관리 방식이 run-at-rate 확정 항목이다.",
         handoff.BACKSHEET_NOTCH_SOURCE],
        ["차광 터널 허용 조도",
         "JB-PV-001 내부 허용 조도는 실물 위험성평가에서 확정한다.", "3D 차광 투입 터널 주석"],
        ["PV 허용전압·CAT 등급",
         "JB-PV-002 의 허용전압·CAT 등급이 미정이다. 설계에 방전(단락) 회로가 없어 "
         "남는 전압에서 절단을 허가할지가 같은 자리에서 정해진다.", "JB-PV-002 공차란"],
        ["부품표에 앵커 플레이트가 없다",
         "베이스를 바닥에 앉히는 250×250×16 플레이트 10 장이 부품표 JB-* 어디에도 없다. "
         "치수·수량은 <span class='mono'>mounting.MOUNTINGS['jbr']</span> 이 갖고 있어 거기서 받았지만, "
         "부품표와 마운팅 모델 중 어느 쪽을 조달 기준으로 삼을지는 정해야 한다.",
         "mounting.MOUNTINGS['jbr'].plate"],
        ["2D·3D 원점 175 mm",
         "GA 부품 좌표는 장비 중심, 3D 장면은 존 중심을 쓴다. 어느 쪽을 제작 기준으로 삼을지 "
         "발주처 확정 항목 — 이 도면집의 자리 값도 그 결정을 따른다.", "상세도 미결"],
    ]
    return table(["항목", "내용", "출처"],
                 [[esc(a), b, f'<code>{esc(c)}</code>'] for a, b, c in rows])


def explode_of(a: fab.Assembly) -> tuple:
    """분해도 배치 — 부품을 위로 쌓아 올린다.

    빌려 온 자동 배치는 부품을 대각선으로 흩는데, 이 셀 부재는 6.8 m 짜리 긴 각관이라
    그렇게 하면 화면 가득 실오라기 몇 개가 된다. 조립 순서대로 **위로** 쌓으면 분해도가
    읽히는 대로 조립 순서가 된다 — 밑에서부터 올린다.

    자리는 그림을 위한 것이지 설계값이 아니다. 실제 자리는 GA 시트가 갖는다.
    """
    gap = 420.0
    out, y = [], 0.0
    for p in a.parts[:12]:
        sx = max(p.L, 60.0)
        sy = max(p.H if p.kind != "tube" else p.W, 40.0)
        sz = max(p.W if p.kind not in ("cyl", "disc") else p.L, 40.0)
        y += sy / 2
        out.append((p.tag, (sx, sy, sz), (0.0, y, 0.0), (0.0, 0.0, 0.0)))
        y += sy / 2 + gap
    return tuple(out)


def build() -> str:
    sheet_of = sheet_map()
    with jbr_materials():
        m = jf.mass_check()
        tally = jf.bolt_tally()
        parts_html: list[str] = []
        asm_html: list[str] = []
        for a0 in jf.ASSEMBLIES:
            a = fab.Assembly(a0.sheet, a0.tag, a0.name, a0.qty, a0.scope, a0.parts,
                             a0.commercial, a0.joints, a0.steps, a0.inspection, explode_of(a0))
            asm_html.append(
                f'<section class="card" id="{esc(a.sheet)}"><h2>{esc(a.sheet)} · {esc(a.tag)} — {esc(a.name)}</h2>'
                f'<p class="note">{esc(a.scope)} · 플랜트 {a.qty}벌 · 제작품 {len(a.parts)}종 '
                f'{n(jf.assembly_weight_kg(a))} kg/벌 · 체결 {a.bolt_count()}개/벌</p>'
                + bif.exploded_view(a)
                + '<h3>부품표</h3>' + bif.bom_table(a, sheet_of)
                + ('<h3>구매품</h3>' + bif.commercial_table(a) if a.commercial else '')
                + '<h3>체결</h3>' + bif.joints_table(a)
                + '<h3>조립 순서</h3>' + bif.steps_list(a)
                + '<h3>검사</h3><ul class="chk">'
                + "".join(f'<li>{esc(x)}</li>' for x in a.inspection) + '</ul></section>')
            for i, p in enumerate(a.parts, start=1):
                parts_html.append(bif.part_sheet(p, f"{a.sheet}-P{i:02d}"))

        mat_rows = [[f'<span class="mono">{esc(k)}</span>', esc(v[0]), esc(v[1]), esc(v[2]),
                     f"{v[3] * 1e6:.2f}", esc(v[4])]
                    for k, v in jf.MATERIALS.items()
                    if k in {p.material for p in jf.parts()}]
    torque_rows = [[esc(k), f"{v[0]:g}", f"{v[1]:g}", f"Ø{fab.HOLE_MM[k]:g}",
                    str(fab.ANCHOR_EMBED_MM.get(k, "—")), str(tally.get(k, 0))]
                   for k, v in fab.TORQUE_NM.items()]

    doc = [f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JBR-201 정션박스 제거장치 제작 도면집</title>
<meta name="description" content="JBR-201 정션박스·케이블 제거셀을 만드는 법 — 부품도 {len(jf.parts())}종 · 조립도 {len(jf.ASSEMBLIES)} · 구멍 {n(jf.hole_tally())} · 체결 {n(sum(j.qty for j in jf.joints()))}">
<style>{bif.CSS}</style>
</head>
<body>
<main class="page">
<header class="title">
<div>
<div class="eyebrow">DYNAMIC INDUSTRY · 태양광 패널 전처리 플랜트 · JBR-201 제작 패키지 · REV.A</div>
<h1>JBR-201 정션박스·케이블 제거장치 제작 도면집</h1>
<p>JB-201 인계({campaign.INFEED_S:g} s)부터 AFR-101 인계({campaign.INFEED_S + campaign.JBR_S:g} s)까지를 맡는 셀 하나를
<b>실제로 만들기 위한</b> 문서다. 제작품 {len(jf.parts())}종의 치수·두께·재질·구멍, 구매품 {len(jf.commercial())}종의 규격,
볼트 {n(sum(j.qty for j in jf.joints()))}개의 호칭·등급·토크, 조립체 {len(jf.ASSEMBLIES)}벌의 조립 순서와 검사 항목을 담는다.
외형·재질·수량·공차는 통합 설계도 부품표에서 그대로 왔고, <b>구멍과 체결은 여기서 처음 정했다</b>.</p>
</div>
<dl class="block">
<dt>문서</dt><dd class="mono">PV-JBR-FAB-000 · REV.A</dd>
<dt>기준</dt><dd>PV-JBR-201-GA-3101 · 통합 설계도 REV.56</dd>
<dt>본체 제작품 중량</dt><dd>{n(m['body_kg'])} kg</dd>
<dt>단위</dt><dd>mm · kg · N·m</dd>
</dl>
</header>
{status_block()}
<section class="card"><h2>1. 도면 목록</h2>
{table(["도면번호", "조립체", "내용", "제작품", "체결", "중량/벌"],
       [[f'<a href="#{esc(a.sheet)}" class="mono">{esc(a.sheet)}</a>', esc(a.tag), esc(a.name),
         f"{len(a.parts)}종", f"{a.bolt_count()}개", f"{n(jf.assembly_weight_kg(a))} kg"]
        for a in jf.ASSEMBLIES])}
</section>
<section class="card"><h2>2. 조립체</h2></section>
{"".join(asm_html)}
<section class="card"><h2>3. 부품도</h2>
<p class="note">3면도 · 치수 · 두께 · 구멍. 축척은 부품 크기에 맞춘다.</p></section>
{"".join(parts_html)}
<section class="card"><h2>4. 총괄 사양</h2>
<h3>재질</h3>{table(["코드", "이름", "KS", "상당 규격", "밀도 g/cm³", "쓰임"], mat_rows)}
<h3>체결 표준</h3>{table(["항목", "규정"], [[esc(k), esc(v)] for k, v in fab.FASTENER_STANDARDS])}
<h3>토크 · 구멍 · 이 셀 사용량</h3>{table(["호칭", "8.8 N·m", "10.9 N·m", "관통 구멍", "앵커 매입", "이 셀 개수"], torque_rows)}
</section>
<section class="card"><h2>5. 집계</h2>
{table(["항목", "값"], [
    ["제작품", f"{len(jf.parts())}종 · {n(sum(p.qty for p in jf.parts()))}개"],
    ["구매품", f"{len(jf.commercial())}종"],
    ["구멍", f"{n(jf.hole_tally())}개"],
    ["볼트·앵커", " · ".join(f"{k} {v}" for k, v in tally.items()) + f" (합 {n(sum(tally.values()))})"],
    ["본체 제작품 중량", f"{n(m['body_kg'])} kg"],
    ["안전가드·리젝트 (별도 기초)", f"{n(m['guard_kg'])} kg"],
])}
</section>
<section class="card"><h2>6. 검산 — 이 도면집이 스스로 재는 것</h2>
{load_table()}
{findings()}
{review()}
</section>
<section class="card"><h2>7. 벤치 시험 계획 — 발주 전에 정해야 하는 것</h2>
{bench()}
</section>
<section class="card"><h2>8. 미결</h2>
<p class="note">이 도면집이 답하지 못한 것들. 답이 오면 정본(<span class="mono">src/pv_preprocess/jbr_fabrication.py</span>)만 고치고 다시 찍는다.</p>
{open_items()}
</section>
<footer class="foot">생성 <span class="mono">tools/build_jbr_fab.py</span> · 정본 <span class="mono">src/pv_preprocess/jbr_fabrication.py</span> · 손으로 고치지 말 것</footer>
</main>
</body>
</html>
"""]
    return "".join(doc)


def main() -> None:
    out = build()
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if old == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024:.0f} kB")


if __name__ == "__main__":
    main()
