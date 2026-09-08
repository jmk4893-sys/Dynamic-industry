# -*- coding: utf-8 -*-
"""조립 순서도 — 단계마다 무엇이 자리에 놓이는지를 그림으로 낸다.

제작 도면집은 조립 순서를 **글로** 적는다: 「BFC-COL-01 을 세우고 레벨링
잭볼트로 상단 높이를 맞춘다」. 그것으로 순서는 알지만, 그 단계가 끝났을 때
기계가 어떤 모습인지는 안 보인다. 초보자가 조립도를 보고 따라 하려면
**단계마다 한 장**이 있어야 한다.

이 문서는 조립체마다 단계 수만큼 등각도를 낸다. 이미 놓인 부품은 흐리게,
그 단계에서 놓는 부품은 진하게 그리고 번호를 붙인다. 자리는 제작 도면집의
분해도가 쓰는 좌표(`build_infeed_fab.explode_instances`)에서 오는데, 분해
오프셋을 빼고 **조립된 자리** 그대로 쓴다.

    PYTHONPATH=src python tools/build_assembly_steps.py

멱등이다. `tests/test_pv_assembly_steps.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_infeed_fab as fb  # noqa: E402
from build_infeed_detail import esc, n, table  # noqa: E402

from pv_preprocess import fabrication as fab, fasteners as F  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-assembly-steps.html"

#: 등각도 한 장의 폭 (뷰박스 단위는 mm 라 실제 크기는 조립체마다 다르다).
VIEW_W = 560


def instances_of(a: fab.Assembly) -> tuple[tuple[str, tuple[float, float, float], tuple[float, float, float]], ...]:
    """(부품 태그, 크기, 조립된 자리). 분해 오프셋은 쓰지 않는다."""
    raw = fb.explode_instances().get(a.tag)
    if raw is None:
        return ()
    return tuple((tag, size, at) for tag, size, at, _ex in raw)


def _bounds(inst) -> tuple[float, float, float, float]:
    us, vs = [], []
    for _tag, size, at in inst:
        sx, sy, sz = size
        for dx in (-sx / 2, sx / 2):
            for dy in (-sy / 2, sy / 2):
                for dz in (-sz / 2, sz / 2):
                    u, v = fb.iso(at[0] + dx, at[1] + dy, at[2] + dz)
                    us.append(u)
                    vs.append(v)
    if not us:
        return (0.0, 0.0, 1.0, 1.0)
    return min(us), min(vs), max(us), max(vs)


def step_view(a: fab.Assembly, step_no: int, inst, box: tuple[float, float, float, float]) -> tuple[str, list[str]]:
    """한 단계의 등각도와 **그 단계에서 실제로 그려진 부품 목록**.

    풍선의 크기와 글자는 뷰박스 크기에 맞춰 키운다 — SVG 안의 길이는 mm 단위라
    고정값으로 두면 조립체가 큰 곳에서는 보이지 않는다.
    """
    placed: set[str] = set()
    for k in range(1, step_no):
        placed |= set(fab.step_parts(a.sheet, k))
    now = set(fab.step_parts(a.sheet, step_no))
    by_tag = {p.tag: p for p in a.parts}

    u0, v0, u1, v1 = box
    span = max(u1 - u0, v1 - v0)
    unit = span / 100.0                             # 풍선·글자 크기의 기준

    out: list[str] = []
    #: 뒤에서 앞으로 — 등각도는 (x + y + z) 가 큰 것이 앞이다.
    order = sorted(inst, key=lambda r: r[2][0] + r[2][1] + r[2][2])
    balloons: list[tuple[float, float, str]] = []
    drawn: list[str] = []
    for tag, size, at in order:
        if tag not in placed and tag not in now:
            continue
        cls = "now" if tag in now else "past"
        part = by_tag.get(tag)
        u, v = fb.iso_box(out, at[0], at[1], at[2], size[0], size[1], size[2], cls,
                          part.name if part else tag)
        if part is not None and part.kind == "ring":    # 링은 상자 위에 원을 겹쳐 형상을 알린다
            uc, vc = fb.iso(at[0], at[1], at[2])
            r = size[1] / 2
            out.append(f'<ellipse class="ringline {cls}" cx="{uc:.1f}" cy="{vc:.1f}" '
                       f'rx="{r * fb.C30:.1f}" ry="{r:.1f}" transform="rotate(30 {uc:.1f} {vc:.1f})"/>')
        if tag in now:
            drawn.append(tag)
            balloons.append((u, v, tag))

    numbers = {tag: i for i, tag in enumerate(sorted(set(drawn)), start=1)}
    seen: set[str] = set()
    for u, v, tag in balloons:
        if tag in seen:
            continue
        seen.add(tag)
        bu, bv = u + 7 * unit, v - 5 * unit
        out.append(f'<line class="lead" x1="{u:.1f}" y1="{v:.1f}" x2="{bu:.1f}" y2="{bv:.1f}" '
                   f'stroke-width="{0.25 * unit:.2f}"/>')
        out.append(f'<circle class="bal" cx="{bu:.1f}" cy="{bv:.1f}" r="{1.9 * unit:.1f}" '
                   f'stroke-width="{0.3 * unit:.2f}"/>')
        out.append(f'<text class="bt" x="{bu:.1f}" y="{bv + 0.95 * unit:.1f}" text-anchor="middle" '
                   f'style="font-size:{2.7 * unit:.1f}px">{numbers[tag]}</text>')

    pad = span * 0.10 + 12 * unit
    vb = f"{u0 - pad:.0f} {v0 - pad:.0f} {u1 - u0 + 2 * pad:.0f} {v1 - v0 + 2 * pad:.0f}"
    label = f"{a.sheet} 단계 {step_no} 조립도"
    svg = f'<svg viewBox="{vb}" role="img" aria-label="{esc(label)}">' + "".join(out) + "</svg>"
    return svg, sorted(set(drawn))


def step_balloons(a: fab.Assembly, step_no: int, sheet_of: dict[str, str], drawn: list[str]) -> str:
    """이 단계의 부품 목록. 등각도에 형상이 있는 것만 번호를 매긴다."""
    now = sorted(fab.step_parts(a.sheet, step_no))
    if not now:
        return '<p class="note">이 단계는 부품을 놓지 않는다 (기초·양생·조정·시운전).</p>'
    by_tag = {p.tag: p for p in a.parts}
    numbers = {tag: i for i, tag in enumerate(drawn, start=1)}
    items, extra = [], []
    for tag in now:
        p = by_tag[tag]
        link = sheet_of.get(tag, "")
        ref = f'<a class="mono" href="#{esc(link)}">{esc(link)}</a> · ' if link else ""
        body = (f'{ref}<span class="mono">{esc(tag)}</span> {esc(p.name)} '
                f'<span class="q">×{p.qty}</span>')
        if tag in numbers:
            items.append(f"<li><b>{numbers[tag]}</b> {body}</li>")
        else:
            extra.append(f"<li>{body}</li>")
    html = ('<ol class="balloons">' + "".join(items) + "</ol>") if items else ""
    if extra:
        html += ('<p class="note">등각도에 형상이 없는 부품 (작은 부속 — 부품도를 본다)</p>'
                 '<ul class="balloons plain">' + "".join(extra) + "</ul>")
    return html


def step_fasteners(a: fab.Assembly, step_no: int) -> str:
    """이 단계의 조립 순서 글에 나오는 볼트 호칭을 체결표에서 찾아 붙인다."""
    step = a.steps[step_no - 1]
    blob = step.title + " " + step.text + " " + step.check
    rows = []
    for j in a.joints:
        got = F._split(j.bolt)
        if got is None:
            continue
        size, length, cls = got
        if f"{size}×{length:g}" in blob or size in blob or j.name.split(" ")[0] in blob:
            rows.append([esc(j.name), f"<code>{size}×{length:g}</code>", esc(cls), esc(j.kind), str(j.qty),
                         f"{j.torque_nm:g}" if j.torque_nm else "—",
                         esc(F.stack(size, j.kind).items[0][0]) if j.kind != "용접" else "—"])
    if not rows:
        return ""
    return ('<h5>이 단계의 체결</h5>'
            + table(["체결부", "볼트", "등급", "종류", "수량/벌", "토크 N·m", "첫 부속"], rows, "", (4, 5)))


CSS = """
:root {
  --ground: #EEF1F3; --sheet: #FFFFFF; --ink: #16202A; --muted: #5B6874; --rule: #C8D0D7;
  --tint: #E4EAEF; --red: #B5321F; --blue: #2A6CB0; --green: #2F7D4F; --code: #EDF1F4;
  --n1: #C9D4DE; --n2: #A9B8C6; --n3: #8B9CAC; --p1: #F1F3F5; --p2: #E6E9EC; --p3: #DCE0E4;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground: #12181E; --sheet: #1A222A; --ink: #E4E9ED; --muted: #98A5B1; --rule: #34414D;
    --tint: #232D37; --red: #E0604A; --blue: #6FA8E6; --green: #6CBF8A; --code: #232D37;
    --n1: #55697C; --n2: #46586A; --n3: #3A4A59; --p1: #232C35; --p2: #1F2831; --p3: #1C242C;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --ground: #12181E; --sheet: #1A222A; --ink: #E4E9ED; --muted: #98A5B1; --rule: #34414D;
  --tint: #232D37; --red: #E0604A; --blue: #6FA8E6; --green: #6CBF8A; --code: #232D37;
  --n1: #55697C; --n2: #46586A; --n3: #3A4A59; --p1: #232C35; --p2: #1F2831; --p3: #1C242C;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink);
  font: 13.5px/1.55 "Pretendard", -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif;
  font-variant-numeric: tabular-nums; }
.mono, code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
code { background: var(--code); padding: 0 4px; border-radius: 3px; font-size: .92em; }
a { color: var(--blue); text-decoration: none; } a:hover { text-decoration: underline; }
.page { max-width: 1180px; margin: 0 auto; padding: 24px 20px 64px; display: grid; gap: 26px; }
.title { background: var(--sheet); border: 1px solid var(--rule); display: grid; grid-template-columns: 1fr auto; }
.title > div { padding: 18px 22px; }
.title h1 { margin: 6px 0 4px; font-size: 25px; font-weight: 600; line-height: 1.2; text-wrap: balance; }
.title p { margin: 0; color: var(--muted); max-width: 80ch; }
.eyebrow { font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.block { border-left: 1px solid var(--rule); display: grid; grid-template-columns: auto auto; gap: 0 18px; padding: 14px 22px; font-size: 12.5px; align-content: start; }
.block dt { color: var(--muted); } .block dd { margin: 0; }
section { background: var(--sheet); border: 1px solid var(--rule); padding: 20px 22px 22px; display: grid; gap: 14px; }
section h2 { margin: 0; font-size: 18px; font-weight: 600; }
section h3 { margin: 10px 0 0; font-size: 14.5px; font-weight: 600; }
section h4 { margin: 0; font-size: 13.5px; font-weight: 600; }
section h5 { margin: 6px 0 0; font-size: 12px; font-weight: 600; color: var(--muted); }
.note { color: var(--muted); font-size: 12.5px; max-width: 100ch; margin: 0; }
.callout { border-left: 3px solid var(--blue); background: var(--tint); padding: 12px 16px; margin: 0; }
.callout p { margin: 0 0 8px; } .callout p:last-child { margin: 0; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 12.3px; }
th, td { text-align: left; vertical-align: top; padding: 5px 10px 5px 0; border-bottom: 1px solid var(--rule); }
thead th { color: var(--muted); font-weight: 600; font-size: 11.5px; letter-spacing: .04em; border-bottom-color: var(--ink); }
th.num, td.num { text-align: right; white-space: nowrap; }
.step { border-top: 1px solid var(--rule); padding-top: 14px; display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(270px, 1fr); gap: 16px; align-items: start; }
.step svg { width: 100%; height: auto; display: block; background: var(--sheet); border: 1px solid var(--rule); }
.step polygon { stroke-linejoin: round; }
.step .past { stroke: var(--muted); stroke-width: .5; opacity: .55; }
.step .past.f1 { fill: var(--p1); } .step .past.f2 { fill: var(--p2); } .step .past.f3 { fill: var(--p3); }
.step .now { stroke: var(--ink); stroke-width: 1.1; }
.step .now.f1 { fill: var(--n1); } .step .now.f2 { fill: var(--n2); } .step .now.f3 { fill: var(--n3); }
.step .lead { stroke: var(--red); stroke-width: 1.2; }
.step .bal { fill: var(--sheet); stroke: var(--red); stroke-width: 1.4; }
.step .bt { font-size: 15px; fill: var(--red); font-weight: 700; font-family: inherit; }
.side { display: grid; gap: 8px; }
.what { font-size: 13px; margin: 0; }
.tools, .check { color: var(--muted); font-size: 12px; margin: 0; }
.check { color: var(--green); }
.balloons { margin: 0; padding: 0; list-style: none; display: grid; gap: 3px; font-size: 12.3px; }
.balloons b { display: inline-block; width: 21px; height: 21px; border-radius: 50%; border: 1px solid var(--red);
  color: var(--red); text-align: center; line-height: 19px; margin-right: 6px; font-size: 11px; font-weight: 700; }
.balloons .q { color: var(--muted); }
.balloons.plain { list-style: none; padding-left: 27px; }
.step .ringline { fill: none; stroke: var(--ink); }
.step .ringline.past { stroke: var(--muted); opacity: .5; }
.legend { display: flex; gap: 18px; flex-wrap: wrap; font-size: 12px; color: var(--muted); }
.legend span::before { content: ""; display: inline-block; width: 13px; height: 13px; margin-right: 6px;
  vertical-align: -2px; border: 1px solid var(--rule); }
.legend .l-past::before { background: var(--p2); }
.legend .l-now::before { background: var(--n2); border-color: var(--ink); }
.toc { columns: 2; column-gap: 26px; font-size: 12.5px; margin: 0; padding-left: 18px; }
@media (max-width: 860px) { .title { grid-template-columns: 1fr; } .step { grid-template-columns: 1fr; } .toc { columns: 1; } }
"""


def build() -> str:
    sheet_of: dict[str, str] = {}
    for a in fab.ASSEMBLIES:
        for i, p in enumerate(a.parts, start=1):
            sheet_of[p.tag] = f"{a.sheet}-P{i:02d}"

    total_steps = sum(len(a.steps) for a in fab.ASSEMBLIES)
    out: list[str] = [
        "<!doctype html>",
        "<!-- 이 파일은 손으로 쓰지 않는다. 정본은 src/pv_preprocess/fabrication.py 의 STEP_PARTS 이고 "
        "tools/build_assembly_steps.py 가 찍는다. -->",
        '<html lang="ko"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>투입 구간 조립 순서도 — 단계별 조립도</title>",
        f"<style>{CSS}</style>",
        "</head><body>",
        '<main class="page">',
        '<header class="title"><div>',
        '<div class="eyebrow">DYNAMIC INDUSTRY · 태양광 패널 전처리 플랜트 · 투입 구간 · 조립 순서 · REV.A</div>',
        "<h1>조립 순서도 — 단계마다 무엇이 놓이는가</h1>",
        "<p>제작 도면집은 조립 순서를 글로 적는다. 그것으로 순서는 알지만 그 단계가 끝났을 때 "
        "기계가 어떤 모습인지는 안 보인다. 이 문서는 조립체마다 단계 수만큼 등각도를 낸다 — "
        "이미 놓인 부품은 흐리게, 그 단계에서 놓는 부품은 진하게 그리고 번호를 붙인다. "
        "자리는 제작 도면집의 부품 좌표 그대로다.</p>",
        "</div>",
        '<dl class="block">',
        '<dt>문서</dt><dd class="mono">PV-ASM-000 · REV.A</dd>',
        f"<dt>조립체</dt><dd>{len(fab.ASSEMBLIES)}벌</dd>",
        f"<dt>단계</dt><dd>{total_steps}단계</dd>",
        f"<dt>제작품</dt><dd>{len(sheet_of)}종</dd>",
        '<dt>생성</dt><dd class="mono">tools/build_assembly_steps.py</dd>',
        "</dl></header>",

        '<section id="how"><h2>보는 법</h2>',
        '<div class="callout">',
        "<p><b>흐린 것은 이미 있는 것, 진한 것은 이번에 놓는 것이다.</b> 번호는 그 단계에서 놓는 부품이고, "
        "오른쪽 목록의 번호와 같다. 목록의 도면번호를 누르면 제작 도면집의 부품도로 간다.</p>",
        "<p><b>공구와 확인 항목이 단계마다 붙어 있다.</b> 확인 항목을 통과하지 못하면 다음 단계로 가지 않는다 — "
        "뒤에서 고치려면 앞을 다시 뜯어야 한다.</p>",
        "<p><b>볼트 규격은 체결 부품 도면집이 정본이다.</b> 여기에는 그 단계에서 쓰는 것만 추려 적었다.</p>",
        "</div>",
        '<div class="legend"><span class="l-past">이미 놓인 부품</span>'
        '<span class="l-now">이번 단계에서 놓는 부품</span></div>',
        "<h3>조립체 목록</h3>",
        '<ol class="toc">' + "".join(
            f'<li><a href="#{esc(a.sheet)}">{esc(a.sheet)} {esc(a.tag)}</a> — '
            f'{len(a.steps)}단계 · 제작품 {len(a.parts)}종</li>' for a in fab.ASSEMBLIES) + "</ol>",
        "</section>",
    ]

    for a in fab.ASSEMBLIES:
        inst = instances_of(a)
        out.append(f'<section id="{esc(a.sheet)}"><h2><span class="mono">{esc(a.sheet)}</span> '
                   f"{esc(a.tag)} — {esc(a.name)}</h2>")
        out.append(f'<p class="note">{esc(a.scope)} · 플랜트 {a.qty}벌 · 제작품 {len(a.parts)}종 '
                   f'{n(a.fabricated_weight_kg())} kg/벌 · 체결 {a.bolt_count()}개/벌 · {len(a.steps)}단계</p>')
        if not inst:
            out.append('<p class="note">이 조립체는 통합 설계도에 부품 좌표가 없어 등각도를 그리지 않는다 '
                       "— 단계와 부품은 아래 표로 낸다. (OEM 설비 인터페이스·유틸리티 스키드·지지 브래킷)</p>")
        box = _bounds(inst)
        for step in a.steps:
            out.append('<div class="step">')
            drawn: list[str] = []
            if inst:
                svg, drawn = step_view(a, step.no, inst, box)
                out.append(svg)
            else:
                out.append("<div></div>")
            out.append('<div class="side">')
            out.append(f"<h4>단계 {step.no} — {esc(step.title)}</h4>")
            out.append(f'<p class="what">{esc(step.text)}</p>')
            if step.tools:
                out.append(f'<p class="tools">공구 · {esc(step.tools)}</p>')
            if step.check:
                out.append(f'<p class="check">확인 · {esc(step.check)}</p>')
            out.append(step_balloons(a, step.no, sheet_of, drawn))
            out.append(step_fasteners(a, step.no))
            out.append("</div></div>")
        out.append('<h3>검사 항목 (조립체)</h3><ul class="note">'
                   + "".join(f"<li>{esc(i)}</li>" for i in a.inspection) + "</ul>")
        out.append("</section>")

    out.append("</main></body></html>")
    return "\n".join(out) + "\n"


def main() -> None:
    text = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(text.encode('utf-8')) / 1024:.1f} kB")


if __name__ == "__main__":
    main()
