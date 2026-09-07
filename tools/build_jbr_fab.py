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
import sys
from collections.abc import Iterator

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_infeed_fab as bif  # noqa: E402  — 그리는 코드를 빌려 온다
from pv_preprocess import campaign, fabrication as fab, handoff  # noqa: E402
from pv_preprocess import jbr_fabrication as jf  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-jbr-fab.html"

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
    mass_mark = '<b class="ok">안</b>' if m["ok"] else '<b class="bad">초과</b>'
    lift_mark = '<b class="ok">가능</b>' if lc["ok"] else '<b class="bad">부족</b>'
    return (
        '<h3>6.2 중량 — 도면의 「약 2.2 t」와 견준다</h3>'
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
        + '<h3>6.3 Z 승강 실린더 — 부품표 값끼리 견준다</h3>'
        + table(["항목", "값"], [
            ["함께 오르내리는 것 (승강 플레이트 · Y 캐리지 3 · 헤드 3 기 · 가이드로드)",
             f'{n(lc["moving_kg"])} kg = {lc["need_kn"]:g} kN'],
            [f'부품표 JB-MZ-002 Ø{jf.LIFT_BORE_MM:g} × {jf.LIFT_COUNT} · 공급 {jf.AIR_MPA_MIN:g} MPa',
             f'{lc["force_kn"]:g} kN'],
            ["이용률", f'{lc["utilisation"]:g} — {lift_mark}'],
            ["필요 보어 (여유 0)", f'Ø{lc["bore_needed_mm"]:.0f} 이상'],
        ])
        + f'<p class="note warn"><b>Ø{jf.LIFT_BORE_MM:g} 실린더 2 개로는 승강부를 들지 못한다.</b> '
          f'{lc["need_kn"]:g} kN 이 필요한데 {jf.AIR_MPA_MIN:g} MPa 에서 {lc["force_kn"]:g} kN 밖에 '
          f'안 나온다 (이용률 {lc["utilisation"]:g}). 여유 없이도 Ø{lc["bore_needed_mm"]:.0f} 가 필요하니 '
          '표준 보어로는 Ø100 이 든다. 셋 중 하나다 — 실린더를 키우거나, 승강부를 가볍게 하거나, '
          '부품표에 없는 카운터밸런스(스프링·평형추)가 설계 의도에 있었거나. '
          '<b>어느 쪽인지는 이 도면집이 정할 일이 아니라 기구 설계가 답할 일이라 올려만 둔다.</b> '
          '무전원 로드락(JB-MZ-004)은 유지용이라 드는 힘에 보태지 않는다.</p>'
    )


def open_items() -> str:
    rows = [
        ["구조 검증이 없다",
         f"단면과 두께는 관례로 골랐다. 45 kN 편심·잼 FEA 와 앵커 인발 검토가 오면 정본만 고치고 "
         f"다시 찍는다. 지금 값으로 만들지 말 것.", "GA 시트 release"],
        ["본체 중량이 도면과 다르다",
         f"부품에서 합산한 본체 {n(jf.mass_check()['body_kg'])} kg 대 도면 어림 2,200 kg. "
         "구매품은 아직 안 들어갔다.", "6.2 절"],
        ["Z 승강 실린더가 모자란다",
         f"Ø{jf.LIFT_BORE_MM:g}×{jf.LIFT_COUNT} 로 이용률 {jf.lift_check()['utilisation']:g}. "
         "실린더·중량·카운터밸런스 중 무엇을 고칠지 미정.", "6.3 절"],
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
</section>
<section class="card"><h2>7. 미결</h2>
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
