"""파일럿 시험 계획서를 찍어낸다 — docs/dg-hk60-pilot.html.

시료 수 · 로트 매수 · 규모는 tools/pilot_plan.py 가 요구정밀도에서 푼
값이다. 문서에 손으로 옮겨 적으면 정밀도를 바꾼 날 계획서만 옛 숫자로
남는다. 여기서 생성한다.

    python3 tools/gen_pilot_doc.py            # 표준출력
    python3 tools/gen_pilot_doc.py --write    # docs/ 에 쓴다
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import analysis_thermal as TH  # noqa: E402
import pilot_plan as P  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "dg-hk60-fab-spec.html"
OUT = ROOT / "docs" / "dg-hk60-pilot.html"
ISSUED = "2026-09-07"


def esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md(t) -> str:
    """이스케이프한 뒤 **강조** 만 <strong> 으로 바꾼다."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(t))


def house_style() -> str:
    return re.search(r"<style>.*?</style>", SPEC.read_text(encoding="utf-8"),
                     re.S).group(0)


def mark() -> str:
    return re.search(r"<svg viewBox=\"0 0 100\.0 88\.9723\".*?</svg>",
                     SPEC.read_text(encoding="utf-8"), re.S).group(0)


# ── 1. 왜 파일럿인가 ─────────────────────────────────────────────────
def part1() -> str:
    n15, n10 = P.n_for_mean(0.20, 0.15), P.n_for_mean(0.20, 0.10)
    n0, n1 = P.n_for_proportion(0.95, 0), P.n_for_proportion(0.95, 1)
    return f"""
<div class="clause" id="p1"><div class="n">1</div><div class="c">
  <h3>이 설비는 아직 가정 위에 서 있다</h3>
  <p>사양서(<span class="k">DG-HK60-RFQ-001</span>)가 미결항목
    <strong>15 건</strong>을 스스로 밝혔고, 열해석(<span class="k">DG-HK60C-CAL-001</span>)이
    요구 <strong>6 건</strong>을 더 만들었다. 그 가운데 <strong>계산으로 닫히지
    않는 것</strong>이 파일럿의 몫이다 — 폐패널의 EVA 가 몇 도에서 얼마의 힘으로
    떨어지는지는 아무리 정교한 해석기도 답하지 못한다. 재료가 답한다.</p>

  <div class="warn"><strong>가장 무거운 하나는 박리력이다.</strong>
    사양서 <span class="k">OI-01</span> 이 밴드를 <span class="m">1.49 – 13.37 kN</span>
    으로 적어 두었다 — <strong>9 배</strong>다. 이 하나가 로드셀 용량 · 진공 패드
    면적 · 갠트리 구조하중 · 목표온도 · IR 용량 · 가열 단수를 동시에 매달고 있다.
    값 하나를 재서는 이 여섯을 닫을 수 없어서 <strong>곡선</strong>을 잰다.</p>

  <h4>계획서에서 가장 쉽게 비는 칸 — 시료 수</h4>
  <p>“충분히 반복한다”는 계획이 아니다. 여기서는 요구정밀도에서 거꾸로 푼다.
    평균을 재는 시험은 <span class="k">n = (t·CV/E)²</span> 를 <span class="k">t</span> 가
    <span class="k">n</span> 에 걸려 있는 채로 반복해 풀고, 비율을 재는 시험은
    Clopper–Pearson 하한이 목표를 넘는 최소 <span class="k">n</span> 을 찾는다.
    정규근사를 쓰면 실패 0 회에서 하한이 <span class="m">1.0</span> 이 되어
    “무한히 좋다”는 답이 나온다 — 시료 수를 정하는 데 쓸 수 없는 답이다.</p>

  <div class="tw"><table>
    <caption>시료 수의 근거</caption>
    <thead><tr><th>재는 것</th><th>요구</th><th class="num">n</th><th>비고</th></tr></thead>
    <tbody>
      <tr><td>평균 (박리력)</td><td>CV 20 % · 상대반폭 ±15 %</td>
        <td class="num">{n15}</td><td>온도 1 점당</td></tr>
      <tr><td>평균 (박리력)</td><td>같은 조건 ±10 %</td>
        <td class="num">{n10}</td><td>정밀도를 5 %p 올리는 데 시료가 {n10/n15:.1f} 배</td></tr>
      <tr><td>비율 (유리 수율)</td><td>하한 95 % · 신뢰 95 % · 실패 0</td>
        <td class="num">{n0}</td><td>한 장이라도 깨지면 이 설계가 무너진다</td></tr>
      <tr><td>비율 (유리 수율)</td><td>같은 조건 · 실패 1 허용</td>
        <td class="num">{n1}</td><td><strong>채택</strong> — 실패 0 을 요구하면 시험이 아니라 기도다</td></tr>
    </tbody>
  </table></div>

  <div class="note"><strong>이 문서는 손으로 고치지 않는다.</strong>
    <span class="k">tools/gen_pilot_doc.py</span> 가
    <span class="k">tools/pilot_plan.py</span> 에서 생성한다. 요구정밀도를 바꾸면
    시료 수와 로트 매수와 일정이 함께 움직인다.</div>
</div></div>"""


# ── 2. 시험 장치와 시료 ──────────────────────────────────────────────
def part2() -> str:
    rig = "".join(
        f"<tr><td>{esc(r.part)}</td><td class=\"k\">{md(r.what)}</td>"
        f"<td>{md(r.why)}</td></tr>" for r in P.RIG)
    lot = "".join(
        f"<tr><td class=\"k\">로트 {esc(l.lot)}</td><td>{md(l.what)}</td>"
        f"<td class=\"num\">{l.n}</td><td>{md(l.why)}</td></tr>"
        for l in P.lots())
    total = sum(l.n for l in P.lots())
    return f"""
<div class="clause" id="p2"><div class="n">2</div><div class="c">
  <h3>시험 장치 — 1 단 벤치로 충분한 이유</h3>
  <p>5 단을 지을 필요가 없다. 계면 온도를 정하는 것은 <strong>한 장이 받는
    유속</strong>이고, 그것은 1 단으로 낸다. 단간 복사 간섭은 1 차원으로 풀리지도
    않고 벤치로 재지도 못하는 문제라 FAT 로 넘긴다. 탠덤 2 칼날도 마찬가지다 —
    두 칼날의 동시 추력은 <strong>합</strong>이지 상호작용이 아니고, 합은 계산된다.</p>
  <div class="tw"><table>
    <caption>파일럿 벤치 구성</caption>
    <thead><tr><th>계통</th><th>사양</th><th>왜 이것이 필요한가</th></tr></thead>
    <tbody>{rig}</tbody>
  </table></div>

  <h4>시료 — 받는 물건은 깨끗하지 않다</h4>
  <p>경년과 백시트 종류가 박리력을 가른다. 로트 <strong>B</strong>(경년 15 년 ·
    PVF)가 상한을 주므로 <strong>로드셀 용량과 진공 패드 면적은 이쪽이
    정한다</strong>. 로트 <strong>C</strong> 는 일부러 깨진 것을 넣는다 — 진공 존
    하나가 새는 조건을 만들어 6 존 제어가 버티는지 본다.</p>
  <div class="tw"><table>
    <caption>시료 로트 — 매수는 시험표의 신품 소요에서 거꾸로 센다</caption>
    <thead><tr><th>로트</th><th>무엇</th><th class="num">매수</th><th>왜</th></tr></thead>
    <tbody>{lot}
      <tr><th>합계</th><th></th><th class="num">{total}</th>
        <th>폐패널 조달이 이 계획의 첫 관문이다</th></tr>
    </tbody>
  </table></div>
</div></div>"""


# ── 3. 시험 항목 ─────────────────────────────────────────────────────
def part3() -> str:
    out = []
    for t in P.tests():
        steps = "".join(f"<li>{md(s)}</li>" for s in t.steps)
        out.append(f"""
  <div class="oi">
    <div class="oi-h"><b>{esc(t.id)}</b><span>{esc(t.title)}</span></div>
    <div class="oi-b">
      <div class="tw"><table>
        <tbody>
          <tr><th>닫는 것</th><td class="k">{md(t.closes)}</td></tr>
          <tr><th>바꾸는 것</th><td>{md(t.factors)}</td></tr>
          <tr><th>시행 · 신품</th><td><strong>{t.n}</strong> 회 ·
            <strong>{t.n_new}</strong> 장 &nbsp;— {md(t.reuse)}</td></tr>
          <tr><th>단계</th><td>{t.phase} 단계</td></tr>
        </tbody>
      </table></div>
      <p><em>절차</em></p><ol class="steps">{steps}</ol>
      <p><em>판정</em>{md(t.accept)}</p>
      <p><em>되먹임</em>{md(t.feeds)}</p>
    </div>
  </div>""")
    return f"""
<div class="clause" id="p3"><div class="n">3</div><div class="c">
  <h3>시험 항목</h3>
  <p>항목마다 <strong>무엇을 닫는가</strong>를 먼저 적었다. 닫는 것이 없는 시험은
    하지 않는다 — 파일럿에서 재는 것은 호기심이 아니라 설계상수다.
    <strong>되먹임</strong> 줄이 그 결과가 어느 상수를 다시 쓰는지를 말한다.</p>
  {''.join(out)}
</div></div>"""


# ── 4. 규모·일정과 경계 ──────────────────────────────────────────────
def part4() -> str:
    budget = "".join(
        f"<tr><td>{md(n)}</td><td class=\"num\">{v}</td><td>{md(w)}</td></tr>"
        for n, v, w in P.panel_budget())
    ph = "".join(
        f"<tr><td class=\"num\">{p.no}</td><td>{esc(p.name)}</td>"
        f"<td class=\"num\">{p.weeks} 주</td><td class=\"k\">{md(p.what)}</td>"
        f"<td>{md(p.gate)}</td></tr>" for p in P.phases())
    scope = "".join(f"<tr><td>{md(w)}</td><td>{md(y)}</td></tr>"
                    for w, y in P.OUT_OF_SCOPE)
    n1 = P.panel_budget()[0][1]
    n2 = P.panel_budget()[1][1]
    return f"""
<div class="clause" id="p4"><div class="n">4</div><div class="c">
  <h3>규모와 일정</h3>
  <div class="warn"><strong>파일럿의 크기를 정하는 것은 박리력 곡선이 아니라
    칼날 수명이다.</strong> 곡선은 <span class="m">{n1} 장</span>이면 닫히고,
    수명은 <span class="m">{n2} 장</span>을 넘겨야 한다. 그래서 두 단계로 나눈다 —
    1 단계가 상세설계를 열고, 2 단계는 인도된 설비의 연장 FAT 로 돌려도 된다.</div>
  <div class="tw"><table>
    <caption>패널 소요 — 신품 기준</caption>
    <thead><tr><th>단계</th><th class="num">신품</th><th>비고</th></tr></thead>
    <tbody>{budget}</tbody>
  </table></div>
  <p>시행 수를 그냥 더하면 두 배가 넘게 나온다. 한 장을 통과시키면 박리력 ·
    수율 · 면내 균일도 · 배기 성상 · 열수지가 <strong>한꺼번에</strong> 나오기
    때문이다. 패널은 한 번만 박리된다 — 그것이 이 표의 전제다.</p>
  <div class="tw"><table>
    <caption>단계와 게이트</caption>
    <thead><tr><th class="num">단계</th><th>이름</th><th class="num">기간</th>
      <th>항목</th><th>게이트</th></tr></thead>
    <tbody>{ph}</tbody>
  </table></div>

  <h4>파일럿이 답하지 못하는 것</h4>
  <p>계획서가 못 하는 것을 적지 않으면, 파일럿이 끝난 뒤 “확인했다”가 확인하지
    않은 것까지 덮는다.</p>
  <div class="tw"><table>
    <caption>범위 밖 — FAT · 시운전 · 초기운전으로 넘긴다</caption>
    <thead><tr><th>무엇</th><th>왜 여기서 못 하는가</th></tr></thead>
    <tbody>{scope}</tbody>
  </table></div>
</div></div>"""


def build() -> str:
    ts = P.tests()
    total = sum(l.n for l in P.lots())
    weeks = sum(p.weeks for p in P.phases())
    toc = "".join(
        f'<li><a href="#p{i}"><b>{i}</b>{t}</a></li>'
        for i, t in enumerate(["왜 파일럿인가", "시험 장치와 시료",
                               "시험 항목", "규모와 일정"], start=1))
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#eceff1">
<title>DG-HK60C 파일럿 시험 계획서</title>
<meta name="description" content="DG-HK60C 폐태양광 패널 분리설비의 파일럿 시험 계획서 — 온도-박리력 곡선, 칼날 수명, 유리 수율, 면내 온도 균일도, 열수지를 요구정밀도에서 푼 시료 수로 확정한다.">
{house_style()}
<style>
  ol.steps{{margin:6px 0 10px 18px;padding:0;font-size:13px;line-height:1.75}}
  ol.steps li{{margin:3px 0}}
  .oi-b table{{margin:4px 0 10px}}
  .oi-b th{{white-space:nowrap;width:88px}}
  td.k{{white-space:nowrap}}
</style>
</head>
<body>
<div class="sheet">

<header class="masthead">
  <div class="issuer">
    {mark()}
    <div class="issuer-name"><i>FOR NET ZERO PROJECTION</i><b>DYNAMIC INDUSTRY</b></div>
  </div>

  <div class="doc-kind">파일럿 시험 계획서 · Pilot Test Plan</div>
  <h1>DG-HK60C 태양광 패널 분리설비<br>파일럿 시험 계획서</h1>
  <p class="subtitle">가정을 숫자로 바꾸는 자리. 시험 <strong>{len(ts)} 항목</strong> ·
    시료 <strong>{total} 장</strong> · <strong>{weeks} 주</strong> ·
    사양서 미결 <strong>9 건</strong>과 열해석 요구 <strong>3 건</strong>을 닫는다.</p>

  <dl class="docref">
    <div><dt>문서번호</dt><dd>DG-HK60C-{P.DOC}</dd></div>
    <div><dt>개정</dt><dd>Rev.0</dd></div>
    <div><dt>발행일</dt><dd>{ISSUED}</dd></div>
    <div><dt>대상 배치</dt><dd>REV.21C (DG-HK60C)</dd></div>
    <div><dt>계획 근거</dt><dd>tools/pilot_plan.py</dd></div>
    <div><dt>해석 근거</dt><dd>DG-HK60C-CAL-001</dd></div>
  </dl>
</header>

<nav class="toc" aria-label="목차">
  <h2>목차</h2>
  <ol>{toc}</ol>
</nav>
{part1()}
{part2()}
{part3()}
{part4()}

<footer class="foot">
  <p><strong>DG-HK60C-{P.DOC} Rev.0</strong> · {ISSUED} · DYNAMIC INDUSTRY</p>
  <p>발주 기술사양서 <span class="k">DG-HK60-RFQ-001</span> ·
    해석 보고서 <span class="k">DG-HK60C-CAL-001</span> 과 한 벌로 읽는다.
    <strong>1 단계 완료가 상세설계 착수의 전제다</strong> — 박리력 설계값이 서지
    않으면 갠트리 구조하중도 진공 패드 면적도 확정할 수 없다.</p>
</footer>

</div>
</body>
</html>
"""


if __name__ == "__main__":
    html = build()
    if "--write" in sys.argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur == html:
            print("이미 같다 — 바꾸지 않았다")
        else:
            OUT.write_text(html, encoding="utf-8")
            print(f"{OUT.name} 갱신  {len(html):,} bytes")
    else:
        print(html)
