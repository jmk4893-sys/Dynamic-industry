"""조립 지침서를 찍어낸다 — docs/dg-hk60-assembly.html.

이 문서의 절반은 부품 카탈로그다 (모듈별 순서·부품표·질량). 손으로 옮겨
적으면 카탈로그를 고친 날 문서만 옛 표로 남는다. 그래서 산문은 이 파일에
두고, 표는 parts.py 에서 뽑아 문서를 통째로 생성한다.

    python3 tools/gen_assembly_doc.py            # 표준출력
    python3 tools/gen_assembly_doc.py --write    # docs/ 에 쓴다

시험이 디스크의 문서를 이 출력과 대조하므로, 문서를 손으로 고치면 걸린다.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import parts as PT  # noqa: E402
import fab_spec as F  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "dg-hk60-fab-spec.html"
OUT = ROOT / "docs" / "dg-hk60-assembly.html"


def esc(t: str) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def house_style() -> str:
    """제작 지침서의 스타일을 그대로 쓴다 — 두 문서가 한 벌로 회람된다."""
    s = SPEC.read_text(encoding="utf-8")
    return re.search(r"<style>.*?</style>", s, re.S).group(0)


def masthead_mark() -> str:
    s = SPEC.read_text(encoding="utf-8")
    return re.search(r"<svg viewBox=\"0 0 100\.0 88\.9723\".*?</svg>", s, re.S).group(0)


# ── 모듈을 세우는 순서 ────────────────────────────────────────────────
# 모듈 안의 순서는 카탈로그가 든다. 모듈 **사이**의 순서는 여기서 정한다 —
# 이것을 안 적으면 현장이 반입 순서대로 세우고, 방책이 먼저 서서 나중에
# 들어갈 기계가 못 들어간다. 실제로 가장 흔한 사고다.
ERECTION = [
    ("1", "기초·앵커", ["—"],
     "전 모듈의 앵커를 한 번에 심는다. 나눠 심으면 두 번째 타설에서 위치가 밀린다.",
     "D-602 배치도 · 앵커 41점 · 그라우트 양생 7일"),
    ("2", "무거운 골조", ["M-002", "M-007", "M-004", "M-005"],
     "가장 무겁고 가장 정확해야 하는 것부터. 나중에 세우면 이미 선 것들 사이로 인양해야 한다.",
     "가열실 · 냉각 랙 · 진공테이블 · 갠트리 주행 문형"),
    ("3", "이송 문형", ["M-003"],
     "골조가 선 뒤에 그 사이를 오가는 것을 단다. 반대로 하면 포크가 갈 곳이 없다.",
     "승강 포크 4기 (LI · EX · GL · GU)"),
    ("4", "후단 설비", ["M-006", "M-008", "M-009"],
     "공정 상류가 확정된 뒤에 하류를 맞춘다. 웹 경로와 유리 경로가 상류 위치에서 나온다.",
     "권취·롤 반출 · 횡인출 · 검사"),
    ("5", "유틸리티", ["M-011", "M-012"],
     "기계가 다 앉은 뒤에 전기와 배관을 깐다. 먼저 깔면 기계를 앉힐 때 밟는다.",
     "전력·제어반 · 진공·계장공기 스키드"),
    ("6", "경계", ["M-017"],
     "우리 쪽 끝까지만 세운다. 그 너머는 발주자 설비이므로 경계가 확정된 뒤에 잇는다.",
     "경계 덕트 · 단자반 · 배관반"),
    ("7", "방책", ["M-013"],
     "**맨 마지막이다.** 방책을 먼저 세우면 그 안으로 들어갈 기계의 반입로가 막힌다 — "
     "현장에서 가장 흔한 사고이고, 되돌리려면 방책을 다시 뜯어야 한다.",
     "방책 34기둥 · 메시 32매 · 안전문 2 · 라이트커튼 2조"),
]

TOOLS = [
    ("토크렌치", "0~100 / 100~800 N·m 2본", "교정 성적서 유효기간 1년 · 정밀도 ±4 % — 이것 없이는 체결이 성립하지 않는다"),
    ("임팩트렌치", "예비 조임 전용", "본 조임에 쓰지 않는다. 임팩트는 체결력을 못 만든다"),
    ("레이저 레벨", "정확도 ±1 mm / 10 m", "기둥 상단 레벨과 레일면을 여기서 잡는다"),
    ("데오돌라이트 또는 토탈스테이션", "각도 ±5″", "4기둥 스팬과 직각도 — 줄자로는 3,500 을 ±1 로 못 잡는다"),
    ("다이얼게이지·마그네틱베이스", "0.01 mm", "축 흔들림 · 레일 직진도 · 상판 평면도"),
    ("직각자·수평기", "1 급", "용접 조립 중 상시"),
    ("틈새 게이지", "0.05~1.0 mm", "베이스플레이트 밀착 — 0.1 이 안 들어가야 한다"),
    ("줄자·강철자", "5 m / 1 m", "일반 치수"),
    ("절연저항계", "500 V DC", "IR 램프 회로 · 동력 회로"),
    ("접지저항계", "—", "통전 전 필수 — 10 Ω 이하"),
    ("체인블록·슬링", "2 t 이상", "가열실 기둥 222 kg · 크로스빔 · 만권 롤"),
    ("표면온도계 (비접촉)", "0~300 ℃", "외피 60 ℃ 확인 · 냉각 랙 판정"),
]

READING = [
    ("정면도 · 측면도 · 단면 A-A",
     "같은 물건을 세 방향에서 본 그림이다. 정면도의 가로가 측면도의 가로와 같은 치수라면 "
     "그 둘은 같은 방향을 보고 있는 것이다. 이 도면집은 <b>제3각법</b>을 쓴다 — "
     "표제란 오른쪽 아래의 원뿔 기호가 그것을 말한다."),
    ("등각 그림",
     "정투상이 안 읽히면 <b>이것부터 본다.</b> 부품이 실제로 어떻게 생겼는지를 그린 것이고, "
     "주황색 <b>‘위’</b> 화살표가 어느 면이 위로 가는지를 말한다. "
     "긴 부재는 지그재그 <b>파단선</b>으로 줄여 그렸다 — 실제 길이는 옆에 글로 적혀 있다."),
    ("치수",
     "숫자는 전부 <b>mm</b> 다. 화살표 두 개 사이의 숫자가 그 두 점 사이의 거리다. "
     "<b>Ø</b> 는 지름, <b>t</b> 는 두께, <b>R</b> 은 반지름이다. "
     "도면에 없는 치수는 재지 말고 물어본다 — 그린 대로 재면 축척 오차가 들어간다."),
    ("공차",
     "치수 옆에 아무것도 없으면 <b>ISO 2768-mK</b> 를 따른다 (100 mm 급에서 ±0.3, 1,000 mm 급에서 ±0.8). "
     "±0.5 처럼 따로 적힌 것은 그 자리가 특별히 중요하다는 뜻이다."),
    ("용접기호",
     "화살표가 <b>용접할 자리</b>를 가리킨다. 삼각형은 필릿 용접, 앞의 숫자 <b>z</b> 가 각장(다리 길이)이다. "
     "기준선 끝의 <b>동그라미</b>는 전주(둘레 전체) 용접이다."),
    ("풍선번호",
     "조립도의 원 안 숫자는 <b>부품표의 번호</b>다. 그 번호로 부품표에서 품번(P-002-01 같은 것)을 찾고, "
     "그 품번으로 부품도를 연다. 조립도 → 부품표 → 부품도 순서다."),
    ("데이텀과 기하공차",
     "네모 안의 <b>A · B · C</b> 는 가공 기준면이다. 그 면을 먼저 잡고 나머지를 재라는 뜻이다. "
     "기준면을 임의로 바꾸면 각 부품은 맞는데 조립이 안 맞는 일이 생긴다."),
]

MISTAKES = [
    ("방책을 먼저 세운다", "그 안으로 들어갈 기계의 반입로가 막힌다. 방책은 <b>7단계, 맨 마지막</b>이다."),
    ("임팩트렌치로 본 조임을 한다", "임팩트는 체결력을 만들지 못한다. 예비 조임까지만 쓰고 본 조임은 토크렌치로 한다."),
    ("마찰접합면에 도장을 한다", "J3(갠트리 크로스빔)은 <b>마찰</b>로 힘을 받는다. 도장하면 μ 가 떨어져 미끄러지고, "
     "미끄러지면 칼끝 간격 300±2 가 깨진다. 접합면은 Sa 2½ 로 두고 도장하지 않는다."),
    ("스프링와셔를 쓴다", "체결력 유지에 기여하지 않는다. 이 설비는 <b>체결력 관리 + 마킹</b>으로 풀림을 막고, "
     "진동부에만 쐐기형 풀림방지 와셔를 쓴다."),
    ("베이스플레이트를 그라우트 없이 조인다", "판이 콘크리트에 점으로 닿아 앵커에 휨이 걸린다. 무수축 그라우트 t30 을 반드시 채운다."),
    ("카세트 클램프를 핀보다 먼저 조인다", "핀이 완전히 착좌하기 전에 클램프가 물면 테이퍼 핀이 상한다. "
     "<b>핀 4개 착좌 → 클램프</b> 순서다."),
    ("위아래를 뒤집어 단다", "부품도의 주황색 <b>‘위’</b> 화살표를 본다. 대칭처럼 보여도 볼트 홀 배치가 다른 부품이 있다."),
    ("내피 연마면을 바깥으로 붙인다", "가열실 내피(STS304 #400)는 <b>연마면이 안쪽</b>이다. 반대로 붙이면 복사 효율이 떨어진다."),
    ("단열재를 이음 맞춰 붙인다", "이음을 나란히 맞추면 그 선이 열교가 된다. <b>어긋 물림</b>으로 깐다."),
    ("리미트만 믿고 하드스톱을 생략한다", "리미트가 죽으면 캐리지가 끝까지 간다. 기계식 하드스톱은 선택이 아니다."),
]


def module_section(mod: str) -> str:
    ps = [p for p in PT.P if p.mod == mod]
    steps = PT.STEPS[mod]
    fab = [p for p in ps if not p.buy]
    buy = [p for p in ps if p.buy]
    kg = sum(p.total_kg for p in ps)
    heavy = max(ps, key=lambda p: p.kg)

    rows = "".join(
        f'<tr><td class="num">{n}</td><td><strong>{esc(t)}</strong></td>'
        f'<td>{esc(why)}</td><td class="chk">{esc(chk)}</td></tr>'
        for n, t, why, chk in steps)

    BUY_CLS = ' class="buy"'
    bom = "".join(
        f'<tr{BUY_CLS if p.buy else ""}><td class="k">{esc(p.pid)}</td><td>{esc(p.name)}</td>'
        f'<td>{esc(p.shape.label())}</td><td>{esc(p.mat)}</td>'
        f'<td class="num">{p.qty}</td><td class="num">{p.total_kg:,.1f}</td>'
        f'<td class="num">{p.step}</td><td>{esc(p.fix)}</td></tr>'
        for p in ps)

    return f"""
  <div class="clause"><div class="n">7.{PT.MODULES.index(mod) + 1}</div><div class="c">
    <h3>{esc(mod)} · {esc(PT.MODULE_NAME[mod])}</h3>
    <p>부품 <strong class="m">{len(ps)} 종</strong> · 개수 <strong class="m">{sum(p.qty for p in ps):,} 개</strong> ·
      질량 <strong class="m">{kg:,.0f} kg</strong> — 제작품 {len(fab)} 종 / 구매품 {len(buy)} 종.
      가장 무거운 단품은 <span class="k">{esc(heavy.pid)}</span> {esc(heavy.name)}
      <strong class="m">{heavy.kg:,.0f} kg</strong> 이다{'' if heavy.kg < 25 else ' — 사람 손으로 들지 않는다'}.</p>
    <div class="tw"><table>
      <caption>{esc(mod)} 조립 순서 — {len(steps)} 단계</caption>
      <thead><tr><th>단계</th><th>무엇을</th><th>왜 이 순서인가</th><th>끝내고 확인</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
    <details><summary>{esc(mod)} 부품표 — 전 {len(ps)} 종</summary>
    <div class="tw"><table>
      <caption>{esc(mod)} 부품표</caption>
      <thead><tr><th>품번</th><th>명칭</th><th>형상·규격</th><th>재질</th><th>수량</th><th>kg</th><th>단계</th><th>어떻게 붙는가</th></tr></thead>
      <tbody>{bom}</tbody>
    </table></div></details>
  </div></div>"""


def build() -> str:
    tot_kg = sum(p.total_kg for p in PT.P)
    fab_n = len([p for p in PT.P if not p.buy])
    buy_n = len([p for p in PT.P if p.buy])

    erect = "".join(
        f'<tr><td class="num">{n}</td><td><strong>{esc(t)}</strong></td>'
        f'<td class="k">{esc(" · ".join(ms))}</td><td>{why}</td><td>{esc(what)}</td></tr>'
        for n, t, ms, why, what in ERECTION)

    tools = "".join(
        f"<tr><td><strong>{esc(a)}</strong></td><td class=\"k\">{esc(b)}</td><td>{esc(c)}</td></tr>"
        for a, b, c in TOOLS)

    reading = "".join(
        f"<div class=\"read\"><h4>{esc(a)}</h4><p>{b}</p></div>" for a, b in READING)

    mistakes = "".join(
        f"<tr><td><strong>{esc(a)}</strong></td><td>{b}</td></tr>" for a, b in MISTAKES)

    mods = "".join(module_section(m) for m in PT.MODULES)

    toc = "".join(
        f'<li><a href="#a{i}"><b>{i}</b>{t}</a></li>' for i, t in enumerate(
            ["이 문서를 쓰는 법", "안전 — 조립 중에 다치는 자리",
             "공구와 계측기", "도면 읽는 법", "볼트 조이는 법",
             "모듈을 세우는 순서", "모듈별 조립", "검사와 기록",
             "흔한 실수 열 가지"], start=1))

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#eceff1">
<title>DG-HK60C 조립 지침서</title>
<meta name="description" content="DG-HK60C 폐태양광 패널 분리설비를 도면만 보고 조립하기 위한 지침서 — 안전, 공구, 도면 읽는 법, 볼트 조이는 법, 모듈을 세우는 순서, 모듈별 조립 단계와 검사.">
{house_style()}
<style>
  /* 이 문서만의 것 — 초보자용 읽기 안내와 확인 열 */
  .read{{border-left:3px solid var(--brand2);padding:2px 0 2px 14px;margin:14px 0}}
  .read h4{{margin:0 0 4px;font-size:15px;color:var(--ink)}}
  .read p{{margin:0}}
  td.chk{{color:#2f6b4f}}
  html[data-theme="dark"] td.chk,
  :root:not([data-theme="light"]) td.chk{{color:#7fd0a8}}
  @media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) td.chk{{color:#7fd0a8}}}}
  tr.buy td{{color:var(--ink2)}}
  tr.buy td:first-child::after{{content:' · 구매';color:var(--ink4);font-size:11px}}
  details{{margin:12px 0 0}}
  details summary{{cursor:pointer;font-size:13px;color:var(--brand);padding:6px 0}}
  details[open] summary{{margin-bottom:6px}}
</style>
</head>
<body>
<div class="sheet">

<header class="masthead">
  <div class="issuer">
    {masthead_mark()}
    <div class="issuer-name"><i>FOR NET ZERO PROJECTION</i><b>DYNAMIC INDUSTRY</b></div>
  </div>

  <div class="doc-kind">조립 지침서 · Assembly Instruction</div>
  <h1>DG-HK60C 태양광 패널 분리설비<br>조립 지침서</h1>
  <p class="subtitle">도면을 처음 보는 사람이 <strong>조립도와 부품도만으로</strong> 이 설비를 세울 수 있게 쓴다.
    무엇을 먼저 놓는지, 왜 그 순서인지, 그 단계를 끝내고 무엇을 재는지를 모든 단계에 적었다.
    부품 <strong>{len(PT.P)} 종 · {sum(p.qty for p in PT.P):,} 개 · {tot_kg:,.0f} kg</strong>
    — 제작품 {fab_n} 종 / 구매품 {buy_n} 종.</p>

  <dl class="docref">
    <div><dt>문서번호</dt><dd>DG-HK60C-ASM-001</dd></div>
    <div><dt>개정</dt><dd>Rev.0</dd></div>
    <div><dt>발행일</dt><dd>2026-09-06</dd></div>
    <div><dt>대상 배치</dt><dd>REV.21C (DG-HK60C)</dd></div>
    <div><dt>부품 근거</dt><dd>tools/parts.py</dd></div>
    <div><dt>체결 근거</dt><dd>DG-HK60C-FAB-001</dd></div>
  </dl>
</header>

<nav class="toc" aria-label="목차">
  <h2>목차</h2>
  <ol>{toc}</ol>
</nav>

<!-- ═══ 1 ═══ -->
<section id="a1"><h2><span class="sn">1</span>이 문서를 쓰는 법</h2>

  <div class="clause"><div class="n">1.1</div><div class="c">
    <h3>도면 세 가지를 함께 본다</h3>
    <p>이 설비의 도면은 성격이 셋이고, 조립하는 사람은 <strong>세 가지를 동시에 펴 놓는다</strong>.
      하나만 보면 반드시 막힌다.</p>
    <div class="tw"><table>
      <caption>도면 세 가지 — 각각 무엇에 답하는가</caption>
      <thead><tr><th>도면</th><th>어디에 있나</th><th>무엇에 답하나</th></tr></thead>
      <tbody>
        <tr><td><strong>조립도</strong></td><td class="k">콘솔 · 조립도 탭 (모듈별)</td>
          <td><strong>무엇을 어떤 순서로</strong> 놓는가. 분해 등각도 + 단계표 + 부품표.</td></tr>
        <tr><td><strong>부품도</strong></td><td class="k">콘솔 · 부품도 탭 (품번별)</td>
          <td>그 부품이 <strong>어떻게 생겼고 얼마나 두꺼운가</strong>. 등각 그림 + 정투상 + 재질.</td></tr>
        <tr><td><strong>제작 지침서</strong></td><td class="k">DG-HK60C-FAB-001</td>
          <td><strong>어떤 볼트로 얼마나 조이는가</strong>. 등급 · 체결력 · 조임토크 · 용접 각장.</td></tr>
      </tbody>
    </table></div>
    <div class="note"><strong>찾는 순서는 정해져 있다.</strong>
      조립도의 <strong>원 안 숫자</strong> → 그 아래 <strong>부품표</strong>에서 품번(<span class="k">P-002-01</span> 같은 것) →
      그 품번으로 <strong>부품도</strong>를 연다. 반대로 가면 같은 부품이 여러 모듈에 나오는 자리에서 헤맨다.</div>
  </div></div>

  <div class="clause"><div class="n">1.2</div><div class="c">
    <h3>이 문서의 지위</h3>
    <p>형상과 치수는 <strong>개념설계가 유도한 값</strong>이다. 상세설계에서 확정한다.
      바뀌는 것은 <span class="k">tools/parts.py</span> 의 숫자이고, 부품도·조립도·질량표·이 문서가 함께 따라온다 —
      <strong>어느 한 곳만 고쳐지는 일이 없도록</strong> 전부 한 곳에서 생성한다.</p>
    <div class="warn"><strong>그래서 도면을 손으로 고치지 않는다.</strong> 콘솔의 도면을 직접 편집하면
      다음 생성에서 지워진다. 치수가 틀렸으면 카탈로그를 고치고 다시 찍는다.</div>
  </div></div>
</section>

<!-- ═══ 2 ═══ -->
<section id="a2"><h2><span class="sn">2</span>안전 — 조립 중에 다치는 자리</h2>
  <div class="clause"><div class="n">2.1</div><div class="c">
    <h3>이 설비에서 실제로 위험한 것</h3>
    <div class="warn"><strong>중량물이 첫째다.</strong> 가열실 기둥 한 본이
      <strong class="m">222 kg</strong>, 크로스빔이 <strong class="m">{[p for p in PT.P if p.pid == 'P-005-08'][0].kg:,.0f} kg</strong>,
      만권 롤이 <strong class="m">357 kg</strong> 이다. <strong>25 kg 이 넘는 것은 사람 손으로 들지 않는다</strong> —
      부품도의 질량 칸이 그 판단의 근거다.</div>
    <ul>
      <li><strong>고소</strong> — 랙 상단이 <span class="m">EL 4,550</span>, 모노레일이 <span class="m">EL 5,100</span> 이다.
        2 m 이상은 전부 안전대 착용 구간이고, 사다리가 아니라 <strong>비계 또는 고소작업대</strong>를 쓴다.</li>
      <li><strong>인양 중 하부</strong> — 인양물 아래로 지나가지 않는다. 태그라인으로 유도한다.</li>
      <li><strong>가용접 상태</strong> — 가용접만 된 부재는 서 있어도 서 있는 것이 아니다.
        본용접 전에는 반드시 <strong>가새 또는 체인블록</strong>으로 잡아 둔다.</li>
      <li><strong>통전</strong> — 접지(<span class="k">M-011</span> 3단계)가 끝나기 전에는 어떤 회로도 넣지 않는다.</li>
      <li><strong>시운전 전 방호</strong> — 회전부는 <strong>처음 도는 순간에 이미 덮여 있어야 한다</strong>.
        돌려 보고 덮는 것이 아니다.</li>
    </ul>
    <p>보호구는 상시 <strong>안전모 · 안전화 · 보안경 · 장갑</strong>, 용접 시 차광면과 방염복,
      연삭 시 방진마스크와 귀마개다.</p>
  </div></div>
</section>

<!-- ═══ 3 ═══ -->
<section id="a3"><h2><span class="sn">3</span>공구와 계측기</h2>
  <div class="clause"><div class="n">3.1</div><div class="c">
    <h3>없으면 조립이 성립하지 않는 것</h3>
    <div class="tw"><table>
      <caption>조립에 필요한 공구·계측기</caption>
      <thead><tr><th>공구</th><th>사양</th><th>어디에 쓰나 · 왜 필요한가</th></tr></thead>
      <tbody>{tools}</tbody>
    </table></div>
    <div class="note"><strong>토크렌치 교정 성적서가 없으면 체결을 시작하지 않는다.</strong>
      이 설비의 접합은 볼트가 <strong>정해진 힘으로 눌러 주는 것</strong>으로 성립한다.
      교정되지 않은 렌치로 조인 볼트는 조인 것이 아니라 돌린 것이다.</div>
  </div></div>
</section>

<!-- ═══ 4 ═══ -->
<section id="a4"><h2><span class="sn">4</span>도면 읽는 법</h2>
  <div class="clause"><div class="n">4.1</div><div class="c">
    <h3>처음 보는 사람을 위한 일곱 가지</h3>
    {reading}
    <div class="note"><strong>모르면 재지 말고 묻는다.</strong> 도면에 없는 치수를 화면에서 재면
      축척만큼 틀린다. 부품도는 <strong>표준 축척</strong>(1:1 · 1:2 · 1:5 · 1:10 …)으로만 그려져 있고,
      축척은 각 그림의 제목 옆에 적혀 있다.</div>
  </div></div>
</section>

<!-- ═══ 5 ═══ -->
<section id="a5"><h2><span class="sn">5</span>볼트 조이는 법</h2>
  <div class="clause"><div class="n">5.1</div><div class="c">
    <h3>토크가 아니라 체결력이 사양이다</h3>
    <p>같은 <span class="m">{F.preload('M20', '8.8'):.1f} kN</span> 을 만드는 데도 건조 아연도금은
      <span class="m">{F.torque('M20', '8.8', F.K_DRY):.0f} N·m</span>,
      윤활은 <span class="m">{F.torque('M20', '8.8', F.K_LUB):.0f} N·m</span> 가 필요하다 —
      <strong>40 % 차이</strong>다. 그래서 도면과 지침서는 체결력과 마찰 조건을 함께 적는다.
      제작사가 다른 표면처리를 쓰면 토크를 다시 계산해 제출한다.</p>
    <ol>
      <li><strong>예비 조임 60 %</strong> — 대각선 순서로 한 바퀴. 임팩트렌치는 여기까지만.</li>
      <li><strong>본 조임 100 %</strong> — 같은 대각선 순서로 한 바퀴. 토크렌치로만.</li>
      <li><strong>마킹</strong> — 조임이 끝나면 볼트 머리 · 너트 · 모재에 걸쳐 <strong>한 줄</strong>을 긋는다.
        나중에 풀리면 그 선이 어긋난다. 이것이 이 설비의 풀림 점검 방법이다.</li>
      <li><strong>재사용 금지</strong> — 10.9 등급과 마찰접합 볼트는 1회용이다. 해체하면 신품으로 바꾼다.</li>
    </ol>
    <div class="warn"><strong>스프링와셔를 쓰지 않는다.</strong> 체결력 유지에 기여하지 않고 도장을 긁는다.
      풀림방지는 <strong>체결력 관리 + 마킹</strong>이 하고, 진동·왕복 부위에만 쐐기형 와셔를 쓴다.
      상세는 지침서 <span class="k">DG-HK60C-FAB-001</span> 5.3 과 표준상세 <span class="k">F-901</span>.</div>
  </div></div>
</section>

<!-- ═══ 6 ═══ -->
<section id="a6"><h2><span class="sn">6</span>모듈을 세우는 순서</h2>
  <div class="clause"><div class="n">6.1</div><div class="c">
    <h3>모듈 사이의 순서 — 이것이 제일 먼저 정해진다</h3>
    <p>모듈 <em>안</em>의 순서는 각 모듈의 조립도가 든다. 모듈 <em>사이</em>의 순서는 여기서 정한다.
      이것을 안 적으면 현장이 <strong>반입 순서대로</strong> 세우고, 그러면 나중에 들어갈 기계가 못 들어간다.</p>
    <div class="tw"><table>
      <caption>세우는 순서 — 7 단계</caption>
      <thead><tr><th>순서</th><th>무엇을</th><th>모듈</th><th>왜 이 순서인가</th><th>내용</th></tr></thead>
      <tbody>{erect}</tbody>
    </table></div>
    <div class="warn"><strong>방책은 맨 마지막이다.</strong> 이것 하나만 지켜도 현장에서 가장 비싼 실수를 피한다.
      방책을 먼저 세우면 그 안으로 들어갈 기계의 반입로가 막히고, 되돌리려면 방책을 다시 뜯어야 한다.</div>
  </div></div>
</section>

<!-- ═══ 7 ═══ -->
<section id="a7"><h2><span class="sn">7</span>모듈별 조립</h2>
  <div class="clause"><div class="n">7.0</div><div class="c">
    <h3>읽는 법</h3>
    <p>각 모듈의 표는 <strong>단계 · 무엇을 · 왜 이 순서인가 · 끝내고 확인</strong> 네 칸이다.
      <strong>‘왜’ 를 읽고 나서 손을 댄다</strong> — 순서를 바꾸면 무엇이 안 되는지 알아야
      현장에서 임의로 바꾸지 않는다. 초록색 <strong>확인</strong> 칸은 그 단계를 끝냈다고 말하기 위해
      실제로 재야 하는 값이다. 재지 않았으면 그 단계는 끝난 것이 아니다.</p>
  </div></div>
{mods}
</section>

<!-- ═══ 8 ═══ -->
<section id="a8"><h2><span class="sn">8</span>검사와 기록</h2>
  <div class="clause"><div class="n">8.1</div><div class="c">
    <h3>단계마다 남기는 것</h3>
    <p>각 단계의 <strong>확인</strong> 칸이 곧 검사 항목이다. 측정값을 적고, 측정한 사람과 날짜를 적는다.
      합격 여부만 적힌 기록은 나중에 아무것도 증명하지 못한다 —
      <strong>값을 적어야</strong> 나중에 문제가 생겼을 때 어디서부터 틀어졌는지 찾을 수 있다.</p>
    <ul>
      <li><strong>기초</strong> — 앵커 위치 실측도, 그라우트 배합·양생 기록</li>
      <li><strong>골조</strong> — 기둥 수직도·레벨, 스팬 실측, 베이스 밀착(틈새 게이지)</li>
      <li><strong>정밀부</strong> — 레일 직진도, 상판 평면도, 축 흔들림 (다이얼게이지 기록지)</li>
      <li><strong>체결</strong> — 토크렌치 교정 성적서, 체결 완료 마킹 사진</li>
      <li><strong>용접</strong> — 용접사 자격, 육안검사(ISO 5817 C급), 지정 부위 비파괴</li>
      <li><strong>전기</strong> — 절연저항, 접지저항, 인터록 기능시험</li>
    </ul>
    <div class="note">전체 검사 계획(ITP 14단계)은 제작 지침서 <span class="k">DG-HK60C-FAB-001</span> 13항이 든다.
      이 문서는 그 중 <strong>조립 현장에서 재는 것</strong>만 단계별로 풀어 적은 것이다.</div>
  </div></div>
</section>

<!-- ═══ 9 ═══ -->
<section id="a9"><h2><span class="sn">9</span>흔한 실수 열 가지</h2>
  <div class="clause"><div class="n">9.1</div><div class="c">
    <h3>이 열 가지가 현장에서 실제로 나온다</h3>
    <div class="tw"><table>
      <caption>흔한 실수와 그 결과</caption>
      <thead><tr><th>이렇게 한다</th><th>그러면 이렇게 된다</th></tr></thead>
      <tbody>{mistakes}</tbody>
    </table></div>
  </div></div>
</section>

<footer class="foot">
  <p><strong>DG-HK60C-ASM-001 Rev.0</strong> · 2026-09-06 · DYNAMIC INDUSTRY</p>
  <p>이 문서는 <span class="k">tools/gen_assembly_doc.py</span> 가 부품 카탈로그
    <span class="k">tools/parts.py</span> 에서 생성한다. 문서를 손으로 고치면 다음 생성에서 지워진다 —
    고칠 곳은 카탈로그다.</p>
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
