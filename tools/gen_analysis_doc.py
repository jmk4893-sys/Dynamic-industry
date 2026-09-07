"""해석 보고서를 찍어낸다 — docs/dg-hk60-analysis.html.

구조는 tools/analysis_structural.py, 열은 tools/analysis_thermal.py 가
푼다. 이 파일은 그 결과를 문서로 옮길 뿐 아무것도 계산하지 않는다 —
숫자가 두 곳에 살면 반드시 갈라지기 때문이다.

    python3 tools/gen_analysis_doc.py            # 표준출력
    python3 tools/gen_analysis_doc.py --write    # docs/ 에 쓴다
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import analysis_irbank as IRB  # noqa: E402
import heatbalance as HBAL  # noqa: E402
import lampmount as LMT  # noqa: E402
import analysis_structural as ST  # noqa: E402
import analysis_thermal as TH  # noqa: E402
import fea  # noqa: E402
import therm  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "dg-hk60-fab-spec.html"
OUT = ROOT / "docs" / "dg-hk60-analysis.html"
DOC = "CAL-001"
ISSUED = "2026-09-07"


def esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md(t) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(t))


def house_style() -> str:
    return re.search(r"<style>.*?</style>", SPEC.read_text(encoding="utf-8"),
                     re.S).group(0)


def mark() -> str:
    return re.search(r"<svg viewBox=\"0 0 100\.0 88\.9723\".*?</svg>",
                     SPEC.read_text(encoding="utf-8"), re.S).group(0)


def _rows(results) -> str:
    out = []
    for r in results:
        cls = "" if r.ok else ' class="over"'
        flag = "OK" if r.ok else "★ 초과"
        out.append(
            f'<tr{cls}><td class="k">{esc(r.id)}</td><td>{md(r.what)}</td>'
            f'<td class="num">{r.value:,.3f}</td><td class="num">{esc(r.unit)}</td>'
            f'<td class="num">{r.limit:,.3f}</td><td class="num">{r.util:.0%}</td>'
            f'<td>{flag}</td></tr>')
    return "".join(out)


def _basis(results) -> str:
    return "".join(
        f'<tr><td class="k">{esc(r.id)}</td><td>{md(r.basis)}</td>'
        f'<td>{md(r.note)}</td></tr>' for r in results)


def _valid(rows, tol) -> str:
    return "".join(
        f'<tr><td>{esc(n)}</td><td class="num">{got:,.4f}</td>'
        f'<td class="num">{want:,.4f}</td><td class="num">{err:.2%}</td>'
        f'<td>{"OK" if err < tol else "★"}</td></tr>' for n, got, want, err in rows)


# ── 1. 무엇을 왜 푸는가 ──────────────────────────────────────────────
def part1() -> str:
    return """
<div class="clause" id="p1"><div class="n">1</div><div class="c">
  <h3>제작 지침서가 답하지 않은 질문</h3>
  <p>제작 지침서(<span class="k">DG-HK60C-FAB-001</span>)는 <strong>강도</strong>를 봤다 —
    볼트가 끊어지는가, 용접이 터지는가, 앵커가 뽑히는가. 이용률이 전부
    <span class="m">0.1</span> 미만이라는 결론이 나왔다. 그것은 좋은 소식이 아니라
    <strong>질문이 틀렸다는 신호</strong>다. 이 설비를 정하는 것이 강도가 아니라는 뜻이니까.</p>
  <div class="warn"><strong>그러면 무엇이 정하는가.</strong>
    칼끝이 <span class="m">0.15 mm</span> 밀리면 EVA 층을 지나쳐 유리를 긁는다.
    상판이 <span class="m">0.38 mm</span> 처지면 진공에 붙은 패널이 따라 처져
    같은 일이 생긴다. 계면이 <span class="m">140 °C</span>에 닿기 전에 백시트가
    <span class="m">165 °C</span>를 넘으면 감아서 팔 물건이 녹는다. 전부
    <strong>강도가 아니라 변형과 온도</strong>다.</div>
  <p>그래서 두 해석기를 만들었다. 구조는 <strong>직접강성법</strong>
    (<span class="k">tools/fea.py</span>), 열은 <strong>1 차원 과도 유한차분</strong>
    (<span class="k">tools/therm.py</span>). 상용 코드를 쓰지 않은 이유는 하나다 —
    이 설비의 형상과 하중이 아직 매일 바뀌기 때문에, 해석이 부품 카탈로그에서
    <strong>자동으로 다시 풀려야</strong> 한다. 형상을 고치면 질량이 바뀌고, 질량이
    바뀌면 이 보고서의 모든 숫자가 따라 움직인다.</p>
  <div class="note"><strong>이 문서는 손으로 고치지 않는다.</strong>
    <span class="k">tools/gen_analysis_doc.py</span> 가 두 해석 모듈에서 생성한다.
    숫자가 틀렸으면 모델을 고치고 다시 찍는다.</div>
</div></div>"""


# ── 2. 검증 ──────────────────────────────────────────────────────────
def part2() -> str:
    return f"""
<div class="clause" id="p2"><div class="n">2</div><div class="c">
  <h3>해석기 검증 — 검증 없는 해석기는 난수 발생기다</h3>
  <p>직접 짠 해석기를 검증 없이 쓰는 것은 계산기를 쓰는 것이 아니라 숫자를
    지어내는 것이다. 닫힌해가 있는 문제로 먼저 맞춘다. 두 해석기 모두
    <strong>검증이 실제로 버그를 잡았다</strong> — 아래 두 건이 그것이다.</p>

  <div class="tw"><table>
    <caption>구조 해석기 <span class="k">tools/fea.py</span> — 닫힌해 대조</caption>
    <thead><tr><th>검증 문제</th><th class="num">해석</th><th class="num">닫힌해</th>
      <th class="num">오차</th><th>판정</th></tr></thead>
    <tbody>{_valid(fea.validate(), 0.03)}</tbody>
  </table></div>
  <div class="warn"><strong>모드해석이 15 배 틀려 있었다.</strong>
    질량 없는 회전 자유도를 그냥 지웠다. 지우는 것은 <strong>구속하는 것</strong>이라
    구조가 훨씬 뻣뻣해졌고, 캔틸레버 1 차 진동수가 닫힌해의
    <span class="m">15 배</span>로 나왔다. Guyan 정적축약으로 고쳐
    <span class="m">0.46 %</span>가 됐다. 검증이 없었으면 갠트리 고유진동수
    <span class="m">16.8 Hz</span>를 그대로 믿었을 것이다.</div>

  <div class="tw"><table>
    <caption>열 해석기 <span class="k">tools/therm.py</span> — 닫힌해 대조</caption>
    <thead><tr><th>검증 문제</th><th class="num">해석</th><th class="num">닫힌해</th>
      <th class="num">오차</th><th>판정</th></tr></thead>
    <tbody>{_valid(therm.validate(), 0.02)}</tbody>
  </table></div>
  <div class="warn"><strong>정상상태를 정상상태가 아닌 데서 읽고 있었다.</strong>
    “시상수의 몇 배만 돌리자”로 짰는데, 전도만 보고 잡은 시상수가
    <span class="m">13 초</span>였고 실제 시상수는 표면저항 <span class="k">1/h</span>가
    지배해 <span class="m">2,700 초</span>였다. 정상해의 <span class="m">36 %</span>
    지점을 정상상태라고 답했고, 검증 ⑤ 가 <span class="m">64 %</span> 오차로 잡았다.
    지금은 어림하지 않고 <strong>변화가 멎을 때까지</strong> 돌린다.</div>
</div></div>"""


# ── 3. 구조 ──────────────────────────────────────────────────────────
def part3() -> str:
    rs, ex = ST.run()
    bad = [r for r in rs if not r.ok]
    return f"""
<div class="clause" id="p3"><div class="n">3</div><div class="c">
  <h3>구조해석</h3>
  <p>네 가지를 푼다 — <strong>KG-101 갠트리</strong>(칼끝 처짐과 고유진동),
    <strong>HC-101 가열실</strong>(기둥 좌굴 · 지진 층간변위 · 세장비),
    <strong>VT-101 상판</strong>(추력 변위와 자중 처짐),
    <strong>WR-101 권취축</strong>(처짐과 휨응력).</p>
  <div class="tw"><table>
    <caption>구조 검토 — 값 · 한계 · 이용률</caption>
    <thead><tr><th>ID</th><th>항목</th><th class="num">값</th><th class="num">단위</th>
      <th class="num">한계</th><th class="num">이용률</th><th>판정</th></tr></thead>
    <tbody>{_rows(rs)}</tbody>
  </table></div>

  <div class="warn"><strong>세 번 틀린 뒤에야 상판이 풀렸다.</strong>
    처음에는 진공 <span class="m">−65 kPa</span>를 상판 전면에 등분포로 걸어
    <span class="m">294 kN</span>을 얻었다. 다음에는 패드 18 점의 하향 집중하중으로
    바꿔 <span class="m">57 kN</span>을 얻었다. <strong>둘 다 틀렸다</strong> —
    진공은 <strong>내력</strong>이다. 패널을 아래로 당기는 힘과 상판을 위로 당기는
    힘이 같은 크기로 마주 서 있어 계를 벗어나지 않는다. 제어체적을 상판 + 패널로
    잡으면 남는 외력은 <strong>패널 자중 {ex['table']['w_panel']:.2f} kN</strong> 뿐이다.
    한계까지 늘려 통과시키는 대신 물리를 다시 유도해서 얻은 답이다.</div>

  <div class="warn"><strong>{"초과 항목 " + " · ".join(r.id for r in bad) if bad else "전 항목 만족"}
    — 그것이 요구가 된다.</strong>
    <span class="k">S11</span> 은 실패가 아니라 <strong>의도한 경계 사례</strong>다.
    권취 클램프를 축 중앙에 몰면 처짐이 한계를 넘고, 양단에 두면 넘지 않는다.
    코어 <span class="m">Ø300×8t</span> 가 축 <span class="m">Ø60</span> 보다
    <span class="m">123 배</span> 뻣뻣해서 <strong>클램프 위치가 답을 정한다</strong> —
    그러므로 그 위치는 도면에 고정되어야 하고, 그것이 이 해석의 결론이다.</div>

  <div class="tw"><table>
    <caption>근거와 읽는 법</caption>
    <thead><tr><th>ID</th><th>한계의 근거</th><th>무엇을 뜻하는가</th></tr></thead>
    <tbody>{_basis(rs)}</tbody>
  </table></div>
</div></div>"""


# ── 4. 열 ────────────────────────────────────────────────────────────
def part4() -> str:
    rs, ex = TH.run()
    st = TH.panel_stack()
    layers = ""
    x = 0.0
    for ly in st.layers:
        layers += (f'<tr><td>{esc(ly.name)}</td><td class="num">{ly.t*1000:.3f}</td>'
                   f'<td class="num">{ly.kk(80):.2f}</td>'
                   f'<td class="num">{ly.rcp/1000:,.1f}</td>'
                   f'<td class="num">{x*1000:.3f}</td></tr>')
        x += ly.t
    from console_consts import const as c
    return f"""
<div class="clause" id="p4"><div class="n">4</div><div class="c">
  <h3>열해석</h3>
  <div class="warn"><strong>콘솔의 열모델에는 두께가 없었다.</strong>
    <span class="k">q = 면적 × 8.7359 × (140−25)</span> 는 “장당 몇 MJ 이 드는가”를
    답한다. 그런데 이 공정이 파는 것은 열량이 아니라 <strong>계면 온도</strong>다 —
    EVA/유리 계면이 <span class="m">140 °C</span>에 닿아야 칼날이 들어간다.
    덩어리 모델에는 그 자리가 아예 없다.</div>

  <h4>패널 적층 — 두께를 값으로 적지 않는다</h4>
  <p>콘솔의 면적질량을 밀도로 나눠 두께를 얻는다. 그래야 이 적층의 면적열용량이
    콘솔의 <span class="k">AREAL_CP</span> 와 <strong>같은 값</strong>이 된다.
    두께를 따로 적으면 두 모델이 서로 다른 패널을 데우게 되고, 그것은 아무도
    눈치채지 못한 채 갈라진다.</p>
  <div class="tw"><table>
    <caption>적층 — 유리를 아래에 두고 쌓는다 (진공 캐리어가 유리면을 잡는다)</caption>
    <thead><tr><th>층</th><th class="num">두께 mm</th><th class="num">k W/(m·K)</th>
      <th class="num">ρc kJ/(m³·K)</th><th class="num">경계 mm</th></tr></thead>
    <tbody>{layers}
      <tr><th>합계</th><th class="num">{st.thickness*1000:.3f}</th><th></th>
        <th class="num">{st.areal_cp:.4f} kJ/(m²·K)</th>
        <th class="num">콘솔 {c('AREAL_CP'):.4f}</th></tr>
    </tbody>
  </table></div>

  <div class="tw"><table>
    <caption>열 검토 — 값 · 한계 · 이용률</caption>
    <thead><tr><th>ID</th><th>항목</th><th class="num">값</th><th class="num">단위</th>
      <th class="num">한계</th><th class="num">이용률</th><th>판정</th></tr></thead>
    <tbody>{_rows(rs)}</tbody>
  </table></div>

  <div class="note"><strong>덩어리 모델이 옳았다.</strong>
    적층이 <span class="m">{st.thickness*1000:.2f} mm</span> 뿐이라 푸리에 수가
    <span class="m">{ex['panel']['fo']:.0f}</span> 이고, 계면 도달이 덩어리 해보다
    <span class="m">{ex['panel']['lag']:.1f} 초</span> 늦을 뿐이다. 과도해석의 첫
    수확은 새 숫자가 아니라 <strong>기존 모델을 믿어도 된다는 확인</strong>이다.
    다만 그 확인은 두께를 넣어 봐야만 나온다.</div>

  <div class="warn"><strong>체류시간 하한을 정하는 것은 계면이 아니라 백시트다.</strong>
    콘솔은 <span class="k">fdmDwell:113.15</span> 를 “1D-FDM 계면 도달시간 하한”
    이라고 적어 두었고, <strong>그 FDM 을 아무도 푼 적이 없었다</strong>. 실제로
    풀어 보면 유속을 올릴 때 먼저 한계에 닿는 것은 계면이 아니라 백시트다 —
    PVDF 융점 <span class="m">165 °C</span>. 융점 그대로면
    <span class="m">{ex['dwell_floor']['t_cap']:.0f} s</span>, 여유
    <span class="m">10 K</span>를 두면
    <span class="m">{ex['dwell_floor']['t_des']:.0f} s</span> 다. 콘솔 값은 그보다
    보수적이라 <strong>바꾸지 않고 근거만 붙였다</strong>.</div>

  <div class="tw"><table>
    <caption>근거와 읽는 법</caption>
    <thead><tr><th>ID</th><th>한계의 근거</th><th>무엇을 뜻하는가</th></tr></thead>
    <tbody>{_basis(rs)}</tbody>
  </table></div>
</div></div>"""


# ── 4b. IR 뱅크 배치 ─────────────────────────────────────────────────
def part4b() -> str:
    rs, ex = IRB.run()
    now, new = ex["now"], ex["new"]
    pos = " · ".join(f"{x*1000:+.0f}" for x in IRB.NEW_X)
    rq = "".join(
        f'<tr><td class="k">{esc(q.id)}</td><td>{esc(q.what)}</td>'
        f'<td class="k">{esc(q.value)}</td><td>{esc(q.owner)}</td>'
        f'<td>{md(q.why)}</td></tr>' for q in IRB.requirements())
    return f"""
<div class="clause" id="p5"><div class="n">5</div><div class="c">
  <h3>IR 뱅크 배치 — 1 차원이 못 보던 자리</h3>
  <p>열해석은 요구 <span class="k">R1</span>(면내 온도편차)을 만들어 놓고 스스로
    닫지 못했다. 1 차원은 두께 방향만 보므로 면내 편차를 <strong>원리적으로</strong>
    낼 수 없고, 그 편차는 램프 배치와 반사면이 정한다. 유한 선원 조사도의
    닫힌해에 정반사 이미지를 얹고, 그 유속장을 면내 2 차원 과도 전도로 풀었다.</p>

  <div class="warn"><strong>전도가 구해 주지 않는다.</strong>
    면내 유효 확산계수는 <span class="m">3.7×10⁻⁷ m²/s</span> 이고 소킹
    <span class="m">222 초</span>의 확산길이는 <span class="m">9 mm</span> 다.
    램프 피치는 <span class="m">400 mm</span> 대다 —
    <strong>유속 분포가 그대로 온도 분포가 된다.</strong> 셀(실리콘)의 k·t 가
    유리의 10 배지만 156 mm 웨이퍼가 2 mm 씩 떨어져 있어 셀을 <em>건너서는</em>
    전도하지 않는다. 연속체로 놓으면 있지도 않은 평활화를 계산에 넣게 된다.</p></div>

  <div class="warn"><strong>창을 정하는 것은 유리가 아니라 백시트다.</strong>
    실제 운전 규칙이 “<strong>가장 찬 점</strong>이 140 ℃ 에 닿을 때까지 소킹한다”
    이므로, 면내 편차는 두 곳을 동시에 친다 — 체류시간이 늘어 처리량이 깎이고,
    중앙이 넘쳐 백시트가 녹는다. 그 창은 165 − 140 − 7 =
    <span class="m">18 K</span> 로, 유리 열응력이 주는 21 K 보다 <strong>좁다</strong>.</div>

  <div class="tw"><table>
    <caption>현행 배치와 개선 배치 — 냉점을 140 ℃ 에 올렸을 때</caption>
    <thead><tr><th>ID</th><th>항목</th><th class="num">값</th><th class="num">단위</th>
      <th class="num">한계</th><th class="num">이용률</th><th>판정</th></tr></thead>
    <tbody>{_rows(rs)}</tbody>
  </table></div>

  <h4>무엇이 듣고 무엇이 안 듣는가</h4>
  <ul>
    <li><strong>램프 발열장</strong> — 가장 크게 듣는다. 결손이 램프 축을 따라
      있기 때문이다. 카탈로그의 <span class="m">1,300 mm</span> 는 패널 폭
      1,200 에 끝단 여유 <span class="m">50 mm</span> 뿐이라 폭 가장자리 유속이
      중앙의 <span class="m">69 %</span> 였다.</li>
    <li><strong>길이방향 배치</strong> — 듣는다. 끝을 패널 끝단(±1,200) 바깥
      <span class="m">±1,340</span> 까지 민다.</li>
    <li><strong>내피 반사율</strong> — 크게 듣는다. 연마 STS 가 하는 일이
      장식이 아니었다. 반사가 없으면 편차가
      <span class="m">{IRB.new(0.0)["spread"]:.0f} K</span>, ρ 0.8 이면
      <span class="m">{new["spread"]:.0f} K</span> 다.</li>
    <li><strong>인접 뱅크 반피치 엇갈림</strong> — <strong>안 듣는다. 오히려
      나빠진다.</strong> 처음에 듣는다고 봤고 모델이 아니라고 했다 — 편차의 정체가
      램프 사이 맥놀이가 아니라 가장자리 결손이라, 엇갈리면 끝쪽 램프가
      가장자리에서 멀어진다.</li>
    <li><strong>존 출력 제어</strong> — 거의 안 듣는다. 램프별 SSR 듀티를 잡아도
      결손이 <strong>램프 축 방향</strong>에 있어 자기 축을 따라서는 못 고친다.
      산업용 IR 로의 표준 해법이 여기서는 표준이 아니다.</li>
  </ul>

  <div class="tw"><table>
    <caption>확정 배치</caption>
    <tbody>
      <tr><th>램프</th><td>발열장 <strong>{IRB.NEW_LEN*1000:.0f} mm</strong> ·
        2.5 kW · 뱅크당 {len(IRB.NEW_X)} 등 (총 {IRB.IR.LAMPS} 등 · 100 kW 불변)</td></tr>
      <tr><th>위치</th><td class="k">x = {pos} mm</td></tr>
      <tr><th>단자</th><td>측벽 관통 · 챔버 밖 소켓. 길이를 벌려고가 아니라
        <strong>석영 단자는 고온부 밖에 있어야 수명이 선다</strong> — 램프 교체도
        챔버를 열지 않고 한다. 대가는 총 80 개소의 관통 실링이다</td></tr>
      <tr><th>내피</th><td>연마 STS304 #400 · 반사율
        <strong>ρ ≥ {IRB.RHO_SPEC:.1f}</strong> — 이제 미관이 아니라 검사·정비 항목이다</td></tr>
      <tr><th>엇갈림</th><td>쓰지 않는다 — 인접 뱅크는 같은 x 위치</td></tr>
    </tbody>
  </table></div>

  <div class="tw"><table>
    <caption>근거와 읽는 법</caption>
    <thead><tr><th>ID</th><th>한계의 근거</th><th>무엇을 뜻하는가</th></tr></thead>
    <tbody>{_basis(rs)}</tbody>
  </table></div>

  <div class="tw"><table>
    <caption>이 검토가 만든 요구</caption>
    <thead><tr><th>ID</th><th>무엇</th><th>값</th><th>받는 곳</th><th>왜</th></tr></thead>
    <tbody>{rq}</tbody>
  </table></div>
</div></div>"""


# ── 5b. 램프 지지·관통 상세 ──────────────────────────────────────────
def part4c() -> str:
    rs, ex = LMT.run()
    rq = "".join(
        f'<tr><td class="k">{esc(q.id)}</td><td>{esc(q.what)}</td>'
        f'<td class="k">{esc(q.value)}</td><td>{esc(q.owner)}</td>'
        f'<td>{md(q.why)}</td></tr>' for q in LMT.requirements())
    return f"""
<div class="clause" id="p6"><div class="n">6</div><div class="c">
  <h3>램프 지지·관통 상세 — 걱정한 셋 중 둘이 서로를 지웠다</h3>
  <p>IR 뱅크 검토가 발열장을 2,200 으로 늘리고 단자를 측벽 밖으로 빼면서
    <strong>“처짐 · 실링 · 그림자”</strong>를 상세설계로 넘겼다. 풀어 보니
    <strong>적지 않은 둘이 더 컸다.</strong></p>

  <div class="warn"><strong>처짐은 문제가 아니었다.</strong>
    Ø25×1.2t 석영관 2,200 스팬의 자중 처짐은 <span class="m">{ex['sag']:.1f} mm</span>
    이고, 램프–패널 거리 310 mm 에서 유속 변화는
    <span class="m">{ex['dflux']:.2%}</span> 다 — 면내 편차 11 K 옆에서 보이지
    않는다. <strong>중간 지지가 필요 없고, 필요 없으면 그림자도 없다.</strong>
    남는 것은 관이 아니라 <strong>관 안 필라멘트</strong>의 처짐이고, 그것은
    램프 안쪽 지지대로 제조사가 푼다 — 우리가 지정할 것이지 설계할 것이 아니다.</div>

  <div class="tw"><table>
    <caption>검토 — 값 · 한계 · 이용률</caption>
    <thead><tr><th>ID</th><th>항목</th><th class="num">값</th><th class="num">단위</th>
      <th class="num">한계</th><th class="num">이용률</th><th>판정</th></tr></thead>
    <tbody>{_rows(rs)}</tbody>
  </table></div>

  <h4>넘길 때 적지 않은 둘</h4>
  <div class="warn"><strong>① 차등 열팽창 — 첫 승온에서 램프가 뜯긴다.</strong>
    강재 챔버 <span class="m">2,300 mm</span> 가
    <span class="m">{ex['steel']:.2f} mm</span> 늘 때 석영관은
    <span class="m">{ex['quartz']:.2f} mm</span> 만 는다 (α
    <span class="m">17.3</span> vs <span class="m">0.55</span>×10⁻⁶).
    차이에 길이공차를 더해 <strong>유동단 행정 {ex['float_req']:.0f} mm</strong> 가
    필요하다. 처짐보다 이쪽이 먼저 부러지는 자리다.</div>
  <div class="warn"><strong>② 봉착부 온도 — “밖에 둔다”가 “실온에 노출한다”가
    되면 램프가 검어진다.</strong> 단파장(할로겐) 램프는 몰리브덴 박 봉착부가
    350 ℃ 를 넘으면 산화하고 250 ℃ 밑이면 할로겐이 거기 응축해 사이클이 죽는다.
    석영은 열을 거의 안 날라 열길이가 <span class="m">{ex['mlen']:.1f} mm</span>
    뿐이라, 그 창이 발광부 경계에서
    <span class="m">{ex['x_hot']:.1f}~{ex['x_cold']:.1f} mm</span> —
    폭 <span class="m">{ex['x_cold']-ex['x_hot']:.1f} mm</span> 다.
    <strong>제작 공차({LMT.TOL_PINCH:.0f} mm)보다 좁으므로 우리가 위치를 잡을
    문제가 아니다.</strong></div>

  <h4>관통이 사 오는 대가</h4>
  <p>80 개소를 뚫는다. <strong>열교는 작지만 침기가 크다.</strong> 연기(EVA 초산·
    불화물)를 잡으려면 챔버를 부압으로 둬야 하고, 그러면 그 구멍으로 찬 공기가
    들어와 그것을 140 ℃ 까지 데우는 것이 그대로 손실이 된다. 실링을 안 하면
    <span class="m">{ex['kw_raw']:.1f} kW</span>
    (<span class="m">{ex['m3h_raw']:,.0f} m³/h</span>) 로 벽 손실
    <span class="m">{ex['base_kw']:.2f} kW</span> 의
    <strong>{ex['kw_raw']/ex['base_kw']:.1f} 배</strong>다 — 효율 65 % 의 나머지를
    찾는 일(<span class="k">R5</span>)에 이 항이 들어간다. 파이버 로프 패킹으로
    <span class="m">{ex['kw_seal']:.2f} kW</span> 까지 내린다.</p>
  <p>부시 재질도 사양이지 선택이 아니다. 강재 슬리브로 바꾸면 열교가
    <strong>{ex['add_st']/ex['add_low']:.0f} 배</strong>가 되는데
    <strong>치수가 같아 도면으로는 구분이 안 된다.</strong></p>

  <div class="tw"><table>
    <caption>근거와 읽는 법</caption>
    <thead><tr><th>ID</th><th>한계의 근거</th><th>무엇을 뜻하는가</th></tr></thead>
    <tbody>{_basis(rs)}</tbody>
  </table></div>

  <div class="tw"><table>
    <caption>이 검토가 만든 요구</caption>
    <thead><tr><th>ID</th><th>무엇</th><th>값</th><th>받는 곳</th><th>왜</th></tr></thead>
    <tbody>{rq}</tbody>
  </table></div>
</div></div>"""


# ── 5c. 열수지 ───────────────────────────────────────────────────────
def part4d() -> str:
    rs, ex = HBAL.run()
    b, su = ex["b"], ex["startup"]
    rows = "".join(
        f'<tr><td>{esc(n)}</td><td class="num">{b[k]:.2f}</td>'
        f'<td class="num">{b[k]/b["p_ir"]:.1%}</td></tr>'
        for n, k in (("패널 엔탈피 — 이 설비가 하는 일", "panel"),
                     ("에어록 교환", "airlock"), ("벽 전도", "wall"),
                     ("램프 단자 전도", "terminal"),
                     ("침기 = 배기 엔탈피", "infil"), ("포크 반출", "fork")))
    rq = "".join(
        f'<tr><td class="k">{esc(q.id)}</td><td>{esc(q.what)}</td>'
        f'<td class="k">{esc(q.value)}</td><td>{esc(q.owner)}</td>'
        f'<td>{md(q.why)}</td></tr>' for q in HBAL.requirements())
    return f"""
<div class="clause" id="p7"><div class="n">7</div><div class="c">
  <h3>열수지 — 30 kW 는 새지 않았다</h3>
  <p>열해석이 요구 <span class="k">R5</span> 를 남겼다: 벽 손실은
    <span class="m">5.5 kW</span> 로 손실 예산 35 kW 의 16 % 뿐인데 나머지
    30 kW 의 행방을 아무도 세지 않았다. 세어 보니
    <strong>질문 자체가 틀려 있었다.</strong> 두 군데가 어긋난다.</p>

  <div class="warn"><strong>① 65 kW 는 계약 처리량의 값이 아니다.</strong>
    콘솔은 <span class="k">유효 = 정격 100 × η 0.65 = 65 kW</span> 를 쓰지만
    그것은 <strong>열공정 한계 {HBAL.RATE_THERMAL:.1f} 장/h</strong> 에서
    패널이 받는 값이다. 라인은 탠덤이 정하는
    <strong>{HBAL.RATE_CONTRACT:.0f} 장/h</strong> 로 돌고, 그때 패널이 가져가는
    것은 <span class="m">{b['panel']:.1f} kW</span> 다.
    <span class="k">100 − 65 = 35</span> 은 <strong>서로 다른 두 운전점에서
    하나씩 가져온 뺄셈</strong>이었다.</div>

  <div class="warn"><strong>② 빗나간 복사는 손실이 아니다.</strong>
    η 0.65 는 <strong>결합효율</strong>(지금 이 순간 복사 중 얼마가 패널에
    흡수되는가)이고 그것이 승온 속도를 정한다. 그런데 챔버는 닫힌 공동이고
    내피는 연마 STS(ρ 0.8)다 — 패널을 빗나간 복사는 되튀어 결국 패널·벽·배기
    중 하나로 간다. <strong>정상상태에서 계를 실제로 떠나는 것만이
    손실이다.</strong> 그것을 세면 <span class="m">{b['loss']:.1f} kW</span> 이고
    남는 항이 없다 — 30 kW 는 새는 것이 아니라 <strong>돌고 있었다.</strong></div>

  <div class="tw"><table>
    <caption>제어체적 — 챔버 내부 · 정상상태 · {HBAL.RATE_CONTRACT:.0f} 장/h ·
      IN = IR 전기 {b['p_ir']:.1f} kW (역산)</caption>
    <thead><tr><th>나가는 곳</th><th class="num">kW</th><th class="num">IN 대비</th></tr></thead>
    <tbody>{rows}
      <tr><th>손실 소계</th><th class="num">{b['loss']:.2f}</th>
        <th class="num">{b['loss']/b['p_ir']:.1%}</th></tr>
      <tr><th>정상상태 효율</th><th class="num">{b['eta']:.1%}</th>
        <th class="num">가정 {HBAL.ETA_ASSUMED:.0%}</th></tr>
    </tbody>
  </table></div>

  <p><strong>가정 65 % 는 그대로 둔다.</strong> 결합효율로 체류시간을 잡는 것은
    옳고, 수지가 내는 {b['eta']:.0%} 보다 낮으므로
    <span class="m">{b['assumed_loss']-b['loss']:.1f} kW</span> 의 여유를 들고 있다.
    바꾸는 것은 값이 아니라 <strong>손실 예산의 정의</strong>다 —
    설치정격 100 kW 는 <strong>승온 속도</strong>가 정하지 정상 소비가 정하지
    않으며, 정상 소비는 <span class="m">{b['p_ir']:.1f} kW</span> 다.</p>

  <div class="tw"><table>
    <caption>검토 — 값 · 한계 · 이용률</caption>
    <thead><tr><th>ID</th><th>항목</th><th class="num">값</th><th class="num">단위</th>
      <th class="num">한계</th><th class="num">이용률</th><th>판정</th></tr></thead>
    <tbody>{_rows(rs)}</tbody>
  </table></div>

  <h4>가장 큰 손실 항은 에어록이고, 그 크기는 부피가 정한다</h4>
  <p>내문이 챔버와 격리실을 섞고 외문이 격리실과 실온을 섞는다.
    <strong>격리실이 막다른 방이므로 교환량이 그 부피로 막힌다</strong> — 문
    크기도 여는 시간도 아니다. 지금 격리실이
    <span class="m">{HBAL.airlock_volume():.2f} m³</span> 인 것은 셔터가 랙 전고
    <span class="m">{HBAL.SHUT_H:.2f} m</span> 이기 때문인데,
    <strong>한 번에 한 단만 쓴다.</strong> 한 단 높이로 줄이면
    <span class="m">{ex['small']:.2f} kW</span> 로
    <strong>{b['airlock']-ex['small']:.1f} kW</strong> 를 아낀다
    (<span class="k">RHB2</span>).</p>

  <div class="note"><strong>포크 항에서 200 배 틀렸다.</strong>
    포크 42 kg 이 매 사이클 통째로 열화한다고 놓아 13 kW 가 나왔고, 그 값이
    수지를 η 64.3 % 로 <em>너무 잘</em> 닫았다 — 가정 65 % 와 소수점까지 맞은
    것이 오히려 신호였다. 그 온도변화는 699 kJ 을 5 초에 넣는 것이라
    <span class="m">140 kW</span> 가 필요한데 설치정격이 100 kW 다. 챔버가 줄 수
    없는 열이었다. 실제로는 전열률이 정하고
    <span class="m">{b['fork']:.2f} kW</span> 다.</div>

  <div class="tw"><table>
    <caption>근거와 읽는 법</caption>
    <thead><tr><th>ID</th><th>한계의 근거</th><th>무엇을 뜻하는가</th></tr></thead>
    <tbody>{_basis(rs)}</tbody>
  </table></div>

  <div class="tw"><table>
    <caption>이 검토가 만든 요구</caption>
    <thead><tr><th>ID</th><th>무엇</th><th>값</th><th>받는 곳</th><th>왜</th></tr></thead>
    <tbody>{rq}</tbody>
  </table></div>
</div></div>"""


# ── 5. 요구 ──────────────────────────────────────────────────────────
def part5() -> str:
    rq = "".join(
        f'<tr><td class="k">{esc(q.id)}</td><td>{esc(q.what)}</td>'
        f'<td class="k">{esc(q.value)}</td><td>{esc(q.owner)}</td>'
        f'<td>{md(q.why)}</td></tr>' for q in TH.requirements())
    return f"""
<div class="clause" id="p8"><div class="n">8</div><div class="c">
  <h3>이 해석이 만든 요구</h3>
  <p>결과에는 두 갈래가 있다. <strong>검토</strong>는 한계가 있어 통과·초과가 나오고,
    <strong>요구</strong>는 해석이 새로 만들어 낸 조건이라 아직 지킬 사람이 없다.
    요구를 검토표에 끼워 넣으면 이용률 <span class="m">100 %</span>짜리 가짜 행이
    생기므로 따로 낸다. <strong>받는 곳</strong> 칸이 이 조건을 누가 가져가는지를
    말한다.</p>
  <div class="tw"><table>
    <caption>요구 — 설계 · 제어 · 파일럿이 받는다</caption>
    <thead><tr><th>ID</th><th>무엇</th><th>값</th><th>받는 곳</th><th>왜</th></tr></thead>
    <tbody>{rq}</tbody>
  </table></div>
</div></div>"""


# ── 6. 경계 ──────────────────────────────────────────────────────────
def part6() -> str:
    return """
<div class="clause" id="p9"><div class="n">9</div><div class="c">
  <h3>이 해석이 못 보는 것</h3>
  <p>해석의 한계를 적지 않으면 “해석했다”가 해석하지 않은 것까지 덮는다.
    아래는 <strong>이 두 해석기로는 원리적으로 볼 수 없는 것</strong>이며, 상세설계에서
    상용 FEA 와 파일럿이 나눠 받는다.</p>
  <div class="tw"><table>
    <caption>범위 밖</caption>
    <thead><tr><th>무엇</th><th>왜 못 보는가</th><th>어디로</th></tr></thead>
    <tbody>
      <tr><td>용접부 국부응력</td><td>보 요소는 절점에서 힘을 주고받을 뿐
        용접 목두께 안의 응력장을 모른다</td><td>상용 FEA (솔리드)</td></tr>
      <tr><td>볼트 접촉과 프리로드</td><td>접합을 강결로 놓았다. 미끄러짐 · 지압 ·
        풀림은 이 모델 밖이다</td><td>상용 FEA · 체결 시험</td></tr>
      <tr><td>판의 국부좌굴</td><td>보 요소에는 판이 없다. 세장비로 전체좌굴만 본다</td>
        <td>상용 FEA (쉘)</td></tr>
      <tr><td>3 차원 응력집중</td><td>거싯 · 개구부 · 용접 지단의 형상계수는
        형상을 그려야 나온다</td><td>상용 FEA</td></tr>
      <tr><td>잔류응력</td><td>용접 열이력을 풀지 않는다</td><td>열탄소성 해석 · 응력제거</td></tr>
      <tr><td>램프의 방향성 배광</td><td>등방 선원으로 놓았다. 실제 반사판 형상은
        배광을 만든다</td><td>파일럿 PT-04 (열화상)</td></tr>
      <tr><td>연마면의 확산 반사</td><td>벽을 정반사로 놓아 가장자리 보상을
        과대평가한다 — ρ 0 인 경우를 함께 낸 이유다</td><td>파일럿 PT-04</td></tr>
      <tr><td>대류계수 h</td><td>가정이지 계산이 아니다. 유리 25 · 카세트 60 ·
        벽 4~5 W/(m²·K) 전부 문헌값이다</td><td>파일럿 PT-06 · FAT</td></tr>
      <tr><td>EVA 의 가교 반응열과 상변화</td><td>비열을 상수로 놓았다.
        가교가 진행되면 그 열이 수지에 들어온다</td><td>DSC · 파일럿 PT-05</td></tr>
      <tr><td>램프의 단파장 복사 분배</td><td>흡수유속을 규정했다 — 실효 열효율
        65 % 가 그 가정을 통째로 담고 있다</td><td>파일럿 PT-05 (열수지)</td></tr>
      <tr><td>램프의 파장별 흡수율</td><td>백시트는 근적외를 많이 반사한다.
        그 몫이 공동 안에서 돌다가 어느 항으로 나가는지는 수지가 못 가른다</td>
        <td>파일럿 PT-05 (열수지 실측)</td></tr>
      <tr><td>석영관의 고온 크리프</td><td>탄성 처짐만 봤다. 관벽이 변형점
        (1,070 ℃) 아래라 무시했지만 수천 시간의 누적은 안 봤다</td>
        <td>램프 제조사 수평 정격 · 초기 운전</td></tr>
      <tr><td>박리력 그 자체</td><td>재료가 답한다. 어떤 해석기도 폐패널 EVA 의
        박리강도를 지어낼 수 없다</td><td>파일럿 PT-01</td></tr>
    </tbody>
  </table></div>
</div></div>"""


def build() -> str:
    srs, _ = ST.run()
    trs, _ = TH.run()
    irs, _ = IRB.run()
    lms, _ = LMT.run()
    hbs, _ = HBAL.run()
    over = [r.id for r in list(srs) + list(trs) if not r.ok]
    toc = "".join(
        f'<li><a href="#p{i}"><b>{i}</b>{t}</a></li>'
        for i, t in enumerate(["무엇을 왜 푸는가", "해석기 검증", "구조해석",
                               "열해석", "이 해석이 만든 요구",
                               "이 해석이 못 보는 것"], start=1))
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#eceff1">
<title>DG-HK60C 구조·열해석 보고서</title>
<meta name="description" content="DG-HK60C 폐태양광 패널 분리설비의 구조·열해석 보고서 — 직접강성법 프레임 해석과 1차원 과도 열전도 해석, 닫힌해 검증, 검토 25건과 해석이 만든 요구 6건.">
{house_style()}
<style>
  tr.over td{{background:var(--flag-sunk)}}
  tr.over td:last-child{{color:var(--flag);font-weight:700}}
  td.k{{white-space:nowrap}}
  .tw td:nth-child(3),.tw td:nth-child(5){{font-variant-numeric:tabular-nums}}
</style>
</head>
<body>
<div class="sheet">

<header class="masthead">
  <div class="issuer">
    {mark()}
    <div class="issuer-name"><i>FOR NET ZERO PROJECTION</i><b>DYNAMIC INDUSTRY</b></div>
  </div>

  <div class="doc-kind">해석 보고서 · Structural &amp; Thermal Analysis</div>
  <h1>DG-HK60C 태양광 패널 분리설비<br>구조 · 열해석 보고서</h1>
  <p class="subtitle">이 설비를 정하는 것은 강도가 아니라 <strong>변형과 온도</strong>다.
    구조 <strong>{len(srs)} 건</strong> · 열 <strong>{len(trs)} 건</strong> ·
    IR 뱅크 <strong>{len(irs)} 건</strong> · 램프 지지 <strong>{len(lms)} 건</strong> ·
    열수지 <strong>{len(hbs)} 건</strong> · 닫힌해 검증 <strong>10 건</strong> ·
    해석이 만든 요구 <strong>{6 + len(IRB.requirements()) + len(LMT.requirements())
    + len(HBAL.requirements())} 건</strong> ·
    검토 초과 <strong>{len(over)} 건</strong> ({' · '.join(over) if over else '없음'}).</p>

  <dl class="docref">
    <div><dt>문서번호</dt><dd>DG-HK60C-{DOC}</dd></div>
    <div><dt>개정</dt><dd>Rev.0</dd></div>
    <div><dt>발행일</dt><dd>{ISSUED}</dd></div>
    <div><dt>대상 배치</dt><dd>REV.21C (DG-HK60C)</dd></div>
    <div><dt>구조 근거</dt><dd>tools/fea.py · analysis_structural.py</dd></div>
    <div><dt>열 근거</dt><dd>tools/therm.py · analysis_thermal.py</dd></div>
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
{part4b()}
{part4c()}
{part4d()}
{part5()}
{part6()}

<footer class="foot">
  <p><strong>DG-HK60C-{DOC} Rev.0</strong> · {ISSUED} · DYNAMIC INDUSTRY</p>
  <p>제작 지침서 <span class="k">DG-HK60C-FAB-001</span> ·
    파일럿 시험 계획서 <span class="k">DG-HK60C-PIL-001</span> 과 한 벌로 읽는다.
    <strong>이것은 개념설계 수준의 확인이다</strong> — 형상과 하중이 확정되면
    상세설계에서 상용 FEA 로 다시 푼다. 그때 이 보고서는 <strong>무엇을 봐야
    하는지의 목록</strong>으로 남는다.</p>
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
