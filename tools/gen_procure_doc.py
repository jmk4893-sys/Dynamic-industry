"""조달 지침서를 찍어낸다 — docs/dg-hk60-procurement.html.

자재 발주표 · 운반 분할 · 구매품 사양은 읽는 사람이 다르지만(자재 담당 ·
물류 · 구매) 근거가 하나다 — 부품 카탈로그. 셋을 따로 만들면 카탈로그를
고친 날 셋이 따로 낡는다. 한 문서 세 부로 내고, 부마다 따로 뽑아 쓸 수
있게 절을 나눈다.

    python3 tools/gen_procure_doc.py            # 표준출력
    python3 tools/gen_procure_doc.py --write    # docs/ 에 쓴다
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import parts as PT  # noqa: E402
from console_consts import const as c  # noqa: E402
import option as OPT  # noqa: E402
import procure as PR  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "dg-hk60-fab-spec.html"
OUT = ROOT / "docs" / "dg-hk60-procurement.html"


def esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def md(t) -> str:
    """이스케이프한 뒤 **강조** 만 <strong> 으로 바꾼다.

    산문 필드에 마크다운 습관으로 ** 를 쓰는 일이 실제로 있었고, 그대로
    인쇄됐다. 태그를 손으로 적게 하는 대신 여기서 한 번에 바꾼다 —
    이스케이프가 먼저이므로 데이터가 태그를 만들 수는 없다.
    """
    import re as _re
    return _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(t))


def house_style() -> str:
    return re.search(r"<style>.*?</style>", SPEC.read_text(encoding="utf-8"), re.S).group(0)


def mark() -> str:
    return re.search(r"<svg viewBox=\"0 0 100\.0 88\.9723\".*?</svg>",
                     SPEC.read_text(encoding="utf-8"), re.S).group(0)


# 발주 시점 — 무엇을 먼저 사야 하는가. 납기가 긴 것이 공정을 정한다.
LEAD = [
    ("즉시", "형강 · 강판 · 강관",
     "재고품이다. 그러나 **제작 착수 = 절단 착수**이므로 이것이 늦으면 전부 늦는다.",
     "1~2 주"),
    ("즉시", "서보·감속기 · LM 가이드 · 볼스크류",
     "이 설비에서 가장 납기가 길다. 사양 확정 전이라도 **수량과 규격만으로 선발주**한다.",
     "8~12 주"),
    ("즉시", "안전 부품 (라이트커튼 · 인터록 · 비상정지)",
     "인증품이라 대체가 어렵다. 늦으면 시운전을 못 한다 — 안전회로 없이는 돌릴 수 없다.",
     "6~8 주"),
    ("30 %", "MCC · PLC 반",
     "**승인도 제출 후 제작**이다. 승인 왕복에 2~3 주가 더 붙는다.",
     "10~14 주 (승인 포함)"),
    ("30 %", "진공펌프 · 공기 리시버",
     "압력용기 검사가 붙는다. 검사증 없이는 반입하지 않는다.",
     "8~10 주"),
    ("50 %", "IR 램프 · 히터 · 열전대",
     f"규격품이나 수량이 많다(램프 {int(c('LAMPS'))}등). 시운전 소모를 보아 예비를 함께 산다.",
     "4~6 주"),
    ("70 %", "필터 · 패드 · 소모품",
     "마지막에 산다. 먼저 사면 창고에서 늙는다 — 특히 NBR 패드와 필터.",
     "2~4 주"),
]

# 운반·양중 주의 — 짐이 아니라 현장이 정하는 것들
HAUL = [
    ("반입로 폭", "차량 폭 + 1,000 이상. 25 t 트레일러는 회전반경 12 m 를 본다."),
    ("양중", "가장 무거운 단품이 기중기를 정한다. 아래 표의 **최중량 단품** 열을 본다."),
    ("적재 순서", "무거운 것을 바닥에, 긴 것을 아래에. 판재는 세워 싣고 받침목으로 잡는다."),
    ("보양", "STS304 내피와 연삭면(레일·상판)은 **비닐 보양 후 합판 개재**. 긁히면 현장에서 못 고친다."),
    ("결박", "각 짐마다 결박점을 도면에 표시한다. 리프팅 러그가 있는 부재는 러그로만 든다."),
    ("도착 순서", "차수 번호가 곧 도착 순서다. 앞 차수가 세워지기 전에 뒤 차수가 오면 둘 자리가 없다."),
]


def hardened() -> str:
    """소입 후 연삭하는 재질 — 사는 두께를 완성에서 거꾸로 푼 표와 그 근거."""
    route = PR.hardened_route()
    if not route:
        return ""
    # 같은 풀이를 밟는 부품은 한 줄로 — 인서트 둘은 두께 경로가 같다
    groups: dict[tuple, list] = {}
    for r in route:
        groups.setdefault((r["t"], r["extra"], r["stock"]), []).append(r)

    def label(r):
        return r["name"].replace(f'{r["mat"]} ', "").split(" (")[0]

    rows, ground = [], []
    for rs in groups.values():
        r = rs[0]
        dlv = f'{r["delivered"]:.1f}' + (f' (연삭 여유 {r["extra"]:g})' if r["extra"] else "")
        rows.append(
            f'<tr><td class="k">{esc(" · ".join(x["pid"] for x in rs))} {esc(label(r))}</td>'
            f'<td class="num">{r["t"]:.1f}</td><td class="num">{dlv}</td>'
            f'<td class="num">{r["delivered"] + 2 * r["grind"]:.1f}</td>'
            f'<td class="num">{r["need"]:.1f}</td>'
            f'<td class="num"><strong>t{r["stock"]:g}</strong></td></tr>')
        ground.append(f'{label(r)} {r["need_ground"]:.1f}')
    skin, grind = PR.HARDENED[route[0]["mat"]]
    ins = next(r for r in route if r["extra"])
    same = all(r["stock"] == r["stock_ground"] for r in route)
    tail = (f"흑피를 걷은 연삭 평강으로 사도 {' · '.join(ground)} 이라 사는 두께는 같다."
            if same else "흑피를 걷은 연삭 평강으로 사면 사는 두께가 달라진다 — 형태를 정하고 발주한다.")
    return f"""<div class="tw"><table>
      <caption>소입 후 연삭하는 SKD11 — 사는 두께를 완성에서 거꾸로 푼다 (mm)</caption>
      <thead><tr><th>품번</th><th class="num">완성</th><th class="num">납품</th>
        <th class="num">+ 소입 변형 연삭</th><th class="num">+ 흑피 · 탈탄층</th><th class="num">소재</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table></div>
    <div class="warn"><strong>SKD11 은 완성 두께로 사지 않는다.</strong>
      한동안 칼날 인서트를 도면 두께 t{ins["t"]:g} 그대로 사게 잡았다. 인서트는 풀림 상태로 사서
      황삭 → 진공소입 · 심랭 · 뜨임 → 양면 연삭 → MC-401 한 평면 연삭을 거친다 — 소입하면 휘고,
      휜 것을 연삭하면 {ins["t"]:g} 이 남지 않는다. 여유는 면당 흑피 · 탈탄층
      <span class="m">{skin:g}</span> · 소입 변형 연삭 <span class="m">{grind:g}</span> 으로 잡았다.
      <strong>가정이다</strong> — 탈탄 깊이는 소재 성적서로, 소입 변형은 열처리사의 같은 형상 실적으로 확인한다.
      {tail}</div>"""


def part1() -> str:
    bl, pl = PR.bar_lots(), PR.plate_lots()
    bad = PR.unbuyable()

    bars = "".join(
        f'<tr><td class="k">{esc(l.mat)}</td><td>{esc(l.section)}</td>'
        f'<td class="num">{l.stock_len:,.0f}</td><td class="num"><strong>{l.bars}</strong></td>'
        f'<td class="num">{sum(q for _, q, _ in l.pieces)}</td>'
        f'<td class="num">{sum(L * q for L, q, _ in l.pieces) / 1000:,.1f}</td>'
        f'<td class="num">{l.waste_pct:.0%}</td><td class="num">{l.kg_net:,.0f}</td></tr>'
        for l in bl)

    def thick(l):
        if l.t_fin in ((), (l.t,)):
            return f"{l.t:g} t"
        return f'{l.t:g} t · 완성 {" · ".join(f"{x:g}" for x in l.t_fin)}'

    plates = "".join(
        f'<tr><td class="k">{esc(l.mat)}</td><td class="num">{thick(l)}</td>'
        f'<td class="k">{f"{l.sheet[0]:,}×{l.sheet[1]:,}" if l.sheet else "—"}</td>'
        f'<td class="num"><strong>{l.sheets}</strong></td>'
        f'<td class="num">{sum(q for _, _, q, _ in l.pieces)}</td>'
        f'<td class="num">{l.area_net:,.2f}</td><td class="num">{l.kg_net:,.0f}</td></tr>'
        for l in pl)

    # 절단 배치 — 손실이 큰 것부터. 여기가 곧 잔재 관리표다.
    worst = sorted([l for l in bl if l.bars], key=lambda l: -l.waste_pct)[:8]
    cuts = "".join(
        f'<tr><td class="k">{esc(l.mat)} {esc(l.section)}</td>'
        f'<td class="num">{l.stock_len:,.0f}</td><td class="num">{l.bars}</td>'
        f'<td class="num">{l.waste_pct:.0%}</td>'
        f'<td>{esc(" / ".join(f"{c.used:,.0f}" for c in l.cuts[:6]))}'
        f'{" …" if len(l.cuts) > 6 else ""}</td></tr>'
        for l in worst)

    warn = ("" if not bad else
            '<div class="warn"><strong>살 수 없는 치수가 남아 있다.</strong><ul>'
            + "".join(f"<li><span class=\"k\">{esc(a)}</span> {esc(b)} — {md(c)}</li>"
                      for a, b, c in bad)
            + "</ul><strong>제작 착수 전에 푼다.</strong></div>")

    lead = "".join(
        f'<tr><td class="k">{esc(w)}</td><td><strong>{esc(what)}</strong></td>'
        f'<td>{md(why)}</td><td class="k">{esc(lt)}</td></tr>'
        for w, what, why, lt in LEAD)

    return f"""
<section id="p1"><h2><span class="sn">1</span>자재 발주표</h2>

  <div class="clause"><div class="n">1.1</div><div class="c">
    <h3>이 표가 답하는 것</h3>
    <p>"총 길이 96 m" 는 발주서가 아니다. <strong>"6 m 정척 19본"</strong> 이 발주서다.
      아래 표는 부재를 재질 × 단면으로 묶고 <strong>1차원 절단 배치를 실제로 풀어</strong>
      정척 몇 본을 사야 하는지와 남는 토막이 얼마인지를 낸다. 총 길이를 정척으로 나누면
      4,550 짜리 두 개가 6 m 정척 한 본에 들어간다고 착각한다 — 실제로는 한 본에 하나다.</p>
    <p>절단 손실 <span class="m">{PR.CUT_KERF} mm</span>(톱날 폭 + 단면 정리)와
      정척 양단 트림 <span class="m">{PR.BAR_TRIM} mm</span> 를 각 조각에 얹었다.
      판재는 사방 <span class="m">{PR.PLATE_TRIM} mm</span> 재단 여유를 본다
      (무른 재료는 칼로 재단하므로 여유 없음).</p>
    {warn}
  </div></div>

  <div class="clause"><div class="n">1.2</div><div class="c">
    <h3>형강 · 강관 · 봉</h3>
    <div class="tw"><table>
      <caption>정척 발주 — 총 {sum(l.bars for l in bl)} 본 · 순중량 {sum(l.kg_net for l in bl):,.0f} kg</caption>
      <thead><tr><th>재질</th><th>단면</th><th>정척 mm</th><th>본수</th><th>조각</th>
        <th>순길이 m</th><th>손실</th><th>순중량 kg</th></tr></thead>
      <tbody>{bars}</tbody>
    </table></div>
    <div class="note"><strong>손실률이 높은 것은 잔재가 아니라 설계다.</strong>
      한 단면을 한두 조각만 쓰면 정척 한 본을 사서 대부분 남긴다. 아래 1.4 의
      배치표에서 어느 단면이 그런지 보이고, 상세설계에서 <strong>단면을 통합할 수 있는지</strong>가
      거기서 나온다 — 단면 종류를 줄이면 손실도 줄고 재고도 준다.</div>
  </div></div>

  <div class="clause"><div class="n">1.3</div><div class="c">
    <h3>판재</h3>
    <div class="tw"><table>
      <caption>시트 발주 — 총 {sum(l.sheets for l in pl)} 매 · 순중량 {sum(l.kg_net for l in pl):,.0f} kg</caption>
      <thead><tr><th>재질</th><th>두께</th><th>시트 규격</th><th>매수</th>
        <th>조각</th><th>순면적 ㎡</th><th>순중량 kg</th></tr></thead>
      <tbody>{plates}</tbody>
    </table></div>
    <div class="note"><strong>매수는 직교 재단(길로틴) 기준의 하한이다.</strong>
      실제 네스팅은 제작사가 더 잘 뽑는다 — 이 표는 <strong>몇 매를 사야 하는가</strong>를
      정직하게 내는 데까지다. 제작사가 네스팅 도면을 내면 그 매수를 쓴다.</div>
    {hardened()}
  </div></div>

  <div class="clause"><div class="n">1.4</div><div class="c">
    <h3>절단 배치 — 손실이 큰 단면</h3>
    <div class="tw"><table>
      <caption>정척 한 본에 얼마를 썼는가 (mm) — 손실 상위 8 단면</caption>
      <thead><tr><th>재질 · 단면</th><th>정척</th><th>본수</th><th>손실</th><th>본별 사용 길이</th></tr></thead>
      <tbody>{cuts}</tbody>
    </table></div>
  </div></div>

  <div class="clause"><div class="n">1.5</div><div class="c">
    <h3>발주 시점 — 무엇을 먼저 사는가</h3>
    <p>납기가 긴 것이 공정을 정한다. 자재가 늦으면 절단이 늦고, 서보가 늦으면
      조립이 다 끝나고도 못 돌린다.</p>
    <div class="tw"><table>
      <caption>발주 시점과 납기</caption>
      <thead><tr><th>시점</th><th>무엇을</th><th>왜 그때인가</th><th>납기</th></tr></thead>
      <tbody>{lead}</tbody>
    </table></div>
    <div class="warn"><strong>서보·감속기와 안전 부품은 지금 발주한다.</strong>
      8~12 주는 이 프로젝트의 어떤 설계 작업보다 길다. 사양이 확정되기를 기다리면
      그만큼 준공이 밀린다 — 수량과 규격은 이미 확정되어 있다.</div>
  </div></div>
</section>"""


def part2() -> str:
    loads = PR.truck_loads()
    rows = []
    for x in loads:
        heavy = max(x.items, key=lambda r: r[3])
        long_ = max(r[4] for r in x.items)
        rows.append(
            f'<tr><td class="num"><strong>{x.seq}</strong></td>'
            f'<td>{esc(PR.STAGE_NAME[x.stage])}</td>'
            f'<td class="k">{esc(x.truck.name)}</td>'
            f'<td class="num">{len(x.items)}</td>'
            f'<td class="num">{x.kg:,.0f}</td>'
            f'<td class="num">{x.kg / x.truck.kg:.0%}</td>'
            f'<td class="num">{long_:,.0f}</td>'
            f'<td>{esc(heavy[1])} <span class="k">{heavy[3]:,.0f} kg</span></td>'
            f'<td>{esc(x.special)}</td></tr>')

    trucks = "".join(
        f"<tr><td><strong>{esc(t.name)}</strong></td>"
        f'<td class="num">{t.L:,}</td><td class="num">{t.W:,}</td>'
        f'<td class="num">{t.H:,}</td><td class="num">{t.kg:,}</td>'
        f'<td class="num">{t.kg * PR.LOAD_MARGIN:,.0f}</td></tr>'
        for t in PR.TRUCKS)

    haul = "".join(f"<tr><td><strong>{esc(a)}</strong></td><td>{md(b)}</td></tr>"
                   for a, b in HAUL)

    # 차수별 적재 명세
    detail = "".join(
        f'<details><summary>{x.seq}차 · {esc(PR.STAGE_NAME[x.stage])} · '
        f'{esc(x.truck.name)} · {x.kg:,.0f} kg · {len(x.items)} 품목</summary>'
        f'<div class="tw"><table><caption>{x.seq}차 적재 명세</caption>'
        f"<thead><tr><th>품번</th><th>명칭</th><th>수량</th><th>kg</th><th>최장변 mm</th></tr></thead><tbody>"
        + "".join(f'<tr><td class="k">{esc(pid)}</td><td>{esc(nm)}</td>'
                  f'<td class="num">{q}</td><td class="num">{kg:,.1f}</td>'
                  f'<td class="num">{lg:,.0f}</td></tr>'
                  for pid, nm, q, kg, lg in sorted(x.items, key=lambda r: -r[3]))
        + "</tbody></table></div></details>"
        for x in loads)

    return f"""
<section id="p2"><h2><span class="sn">2</span>운반 분할</h2>

  <div class="clause"><div class="n">2.1</div><div class="c">
    <h3>차수가 곧 도착 순서다</h3>
    <p>부재를 차량 적재 단위로 묶되, 순서는 <strong>세우는 순서</strong>를 따른다
      (조립 지침서 6항). 나중에 세울 것이 먼저 도착하면 현장에 둘 자리가 없고,
      그것을 옮기느라 기중기를 두 번 부른다.</p>
    <p>차량은 <strong>남은 짐 가운데 가장 긴 것</strong>이 정하고, 그 차를 채운다.
      긴 빔 하나 때문에 트레일러를 부르게 되면, 같은 차수의 다른 짐도
      그 차에 싣는다 — 이미 부른 차를 비워 보내는 것이 가장 비싸다.</p>
    <div class="tw"><table>
      <caption>차량 제원 — 적재 한도는 정격의 {PR.LOAD_MARGIN:.0%}</caption>
      <thead><tr><th>차량</th><th>적재장 mm</th><th>폭</th><th>높이</th>
        <th>정격 kg</th><th>계획 한도 kg</th></tr></thead>
      <tbody>{trucks}</tbody>
    </table></div>
    <div class="note">정격을 꽉 채워 계획하면 결박구·받침목 무게와 계근 오차에서 초과가 난다.
      그래서 <strong>{PR.LOAD_MARGIN:.0%}</strong> 로 잡는다.
      도로법 한도는 전장 <span class="m">{PR.ROAD_LIMIT['L']:,}</span> ·
      폭 <span class="m">{PR.ROAD_LIMIT['W']:,}</span> ·
      높이 <span class="m">{PR.ROAD_LIMIT['H']:,}</span> mm 이고, 넘으면 운행 허가와 유도차가 붙는다.</div>
  </div></div>

  <div class="clause"><div class="n">2.2</div><div class="c">
    <h3>차수표</h3>
    <div class="tw"><table>
      <caption>운반 차수 — 총 {len(loads)} 차 · {sum(x.kg for x in loads):,.0f} kg</caption>
      <thead><tr><th>차수</th><th>세우는 단계</th><th>차량</th><th>품목</th>
        <th>적재 kg</th><th>적재율</th><th>최장변</th><th>최중량 단품</th><th>비고</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table></div>
    <div class="note"><strong>최중량 단품 열이 기중기를 정한다.</strong>
      짐 전체 무게가 아니라 한 번에 드는 것의 무게가 양중 계획의 근거다.</div>
  </div></div>

  <div class="clause"><div class="n">2.3</div><div class="c">
    <h3>차수별 적재 명세</h3>
    {detail}
  </div></div>

  <div class="clause"><div class="n">2.4</div><div class="c">
    <h3>운반·양중 주의</h3>
    <div class="tw"><table>
      <caption>짐이 아니라 현장이 정하는 것들</caption>
      <thead><tr><th>항목</th><th>기준</th></tr></thead>
      <tbody>{haul}</tbody>
    </table></div>
  </div></div>
</section>"""


def part3() -> str:
    rows = PR.buy_rows()
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r[1], []).append(r)

    secs = []
    for sysname in ("안전", "전기", "계장", "기계", "공압", "구조"):
        items = by.get(sysname)
        if not items:
            continue
        body = "".join(
            f'<tr><td class="k">{esc(p.pid)}</td><td><strong>{esc(p.name)}</strong></td>'
            f"<td>{md(rating)}</td><td>{md(iface)}</td>"
            f'<td class="num">{p.qty}</td><td>{md(insp)}</td>'
            f'<td class="k">{esc(spare)}</td></tr>'
            for p, _s, rating, iface, insp, spare in items)
        secs.append(f"""
    <h3>{esc(sysname)} — {len(items)} 종</h3>
    <div class="tw"><table>
      <caption>{esc(sysname)} 구매품</caption>
      <thead><tr><th>품번</th><th>명칭</th><th>정격·성능</th><th>인터페이스</th>
        <th>수량</th><th>검사·승인</th><th>예비품</th></tr></thead>
      <tbody>{body}</tbody>
    </table></div>""")

    approve = [p for p, _s, _r, _i, insp, _sp in rows if "승인도" in insp]
    cert = [p for p, _s, _r, _i, insp, _sp in rows if "인증서" in insp or "검사증" in insp]

    return f"""
<section id="p3"><h2><span class="sn">3</span>구매품 사양</h2>

  <div class="clause"><div class="n">3.1</div><div class="c">
    <h3>구매품은 형상을 그리지 않는다</h3>
    <p>사는 물건의 내부 치수를 도면에 적으면 그것은 거짓말이다. 대신 발주에 필요한
      다섯 가지를 적는다 — <strong>정격·성능 · 인터페이스 · 수량 · 검사·승인 · 예비품</strong>.
      이것이 없으면 구매 담당이 임의로 고르고, 그 선택이 조립 날에 드러난다.</p>
    <p>전 <strong class="m">{len(rows)} 종</strong>이고, 부품도(콘솔 <span class="k">부품도</span> 탭)에는
      외형 상자와 장착면이 그려져 있다 — <strong>앉힐 자리를 잡는 데까지</strong>가 도면의 몫이다.</p>
    <div class="warn"><strong>승인도 제출 대상 {len(approve)} 종</strong>
      (<span class="k">{esc(" · ".join(p.pid for p in approve))}</span>) 은
      <strong>승인 후 제작</strong>이다. 승인 왕복 2~3 주를 일정에 넣는다.
      <strong>인증서·검사증 대상 {len(cert)} 종</strong>은 서류 없이 반입하지 않는다 —
      안전 부품과 압력용기는 서류가 곧 사용 허가다.</div>
  </div></div>

  <div class="clause"><div class="n">3.2</div><div class="c">
    {"".join(secs)}
  </div></div>

  <div class="clause"><div class="n">3.3</div><div class="c">
    <h3>예비품</h3>
    <p>전부 예비를 두면 창고가 공장이 된다. <strong>소모품과 정지시간이 큰 것</strong>만 든다.</p>
    <ul>
      {"".join(f"<li><span class='k'>{esc(pid)}</span> {esc(txt)}</li>" for pid, txt in PR.SPARES.items())}
    </ul>
    <div class="note"><strong>라이트커튼이 예비품 목록에 있는 이유</strong> — 안전 부품이 고장나면
      기계가 서고, 대체품 납기가 6~8 주다. 안전정지가 곧 생산정지다.</div>
  </div></div>
</section>"""


# ── 4부 · 옵션 DG-HK120C ───────────────────────────────────────────────
def _mod_change(m: str) -> str:
    """모듈 하나가 옵션에서 무엇이 달라지는가 — 두 카탈로그에서 읽는다."""
    B, T = OPT.PT_B, OPT.PT_T
    if m in B.PER_CELL:
        return f"셀마다 한 벌 — 칼날 셀 {T.CELLS}개 (수량 ×{T.CELLS})"
    if m == "M-002":
        return (f"{B.DECKS} → {T.DECKS}단 · 램프 {B.LAMPS} → {T.LAMPS}등 · 외피 벽 "
                f"{B._HC_WALL_H:,.0f} → {T._HC_WALL_H:,.0f} · 기둥 {B.RACK_TOP:,.0f} → {T.RACK_TOP:,.0f}")
    if m == "M-003":
        return (f"EX·GL 문형을 ±{T.M('FORK_HALF_TWIN'):,.0f} 로 죄고 횡이송 캔틸레버 {2 * T._TRAV} · 캐리지 "
                f"{2 * T._TRAV} (행정 {T.TR_TRAVEL:,.0f} · 수직 {T.TR_STROKE:,.0f}) · 문형 높이 "
                f"{B._FK_H:,.0f} → {T._FK_H:,.0f}")
    if m == "M-006":
        return (f"본선 {B._RH_L:,.0f} → {T._RH_L:,.0f} ({T.RH_N} 토막) · 레일면 EL {B.RH_Z:,.0f} → {T.RH_Z:,.0f} · "
                f"H-{B.RH_SEC[0]} → H-{T.RH_SEC[0]} · 기둥 {len(B.RH_POSTS)} → {len(T.RH_POSTS)} · "
                f"KC-101 매거진 {T.CELLS}조 · KC-301 포켓 {B.KC_SLOTS} → {T.KC_SLOTS}")
    if m == "M-007":
        return (f"{B.GCOOL_DECKS} → {T.GCOOL_DECKS}단 · 팬 {B.GC_FANS} → {T.GC_FANS} · "
                f"필터 {B.GC_FILTERS} → {T.GC_FILTERS}")
    if m == "M-011":
        eb, et = OPT.EL_B.summary(), None
        with OPT.pinned():
            et = OPT.EL_T.summary()
        return (f"연결부하 {eb['kw']:,.0f} → {et['kw']:,.0f} kW · 주회로 {eb['main_af']} → {et['main_af']} AF · "
                f"MCC {B.CELLS} → {T.CELLS}면 · 간선 {B._TRAY_L / 1000:.0f} → {T._TRAY_L / 1000:.0f} m")
    if m == "M-012":
        return (f"펌프 {B.VAC_PUMPS} → {T.VAC_PUMPS} (1 예비) · 맥동 탱크 {B.CELLS} → {T.CELLS} · "
                f"배관 {B._VAC_RUN / 1000:.0f} → {T._VAC_RUN / 1000:.0f} m")
    if m == "M-013":
        return (f"방책 둘레 {B.FENCE_LEN / 1000:.1f} → {T.FENCE_LEN / 1000:.1f} m (DL 구간만 넓어지는 계단) · "
                f"게이트 {B.FENCE_GATES} → {T.FENCE_GATES} · 셀 가드 {T.CELLS}벌 · 터널 광커튼 {2 * T.CELLS}")
    return "같다"


def _pcell(p) -> str:
    return "—" if p is None else f"{esc(p.shape.label())} ×{p.qty}"


def part4() -> str:
    B, T = OPT.PT_B, OPT.PT_T
    tot = OPT.totals()
    b, t = tot["base"], tot["opt"]

    def row(label, key, fmt="{:,.0f}", unit=""):
        d = t[key] - b[key]
        sign = "+" if d > 0 else ""
        return (f'<tr><th>{label}</th><td class="num">{fmt.format(b[key])}{unit}</td>'
                f'<td class="num"><strong>{fmt.format(t[key])}{unit}</strong></td>'
                f'<td class="num">{sign}{fmt.format(d)}{unit}</td></tr>')

    summary = "".join([
        row("품목", "items", unit=" 종"), row("부품 개수", "pieces", unit=" 개"),
        row("총질량", "kg", unit=" kg"), row("정척", "bars", unit=" 본"), row("시트", "sheets", unit=" 매"),
        row("운반", "trucks", unit=" 차"), row("구매품", "buy", unit=" 종"),
        row("연결부하", "kw", unit=" kW"), row("주차단기", "af", unit=" AF"), row("변압기", "tr", unit=" kVA")])

    def _asm(m):
        no, n = OPT.module_no(m), OPT.module_cells(m)
        return f'{no}{f" × {n} 벌" if n > 1 else ""}'

    mods = "".join(
        f'<tr><td class="k">{esc(m)}</td><td>{esc(name)}</td>'
        f'<td class="k">{esc(_asm(m))}</td>'
        f'<td class="num">{nb} → {nt}</td><td class="num">{kb:,.0f} → {kt:,.0f}</td>'
        f'<td class="num">{"+" if kt >= kb else ""}{kt - kb:,.0f}</td><td>{esc(_mod_change(m))}</td></tr>'
        for m, name, kb, kt, nb, nt in OPT.modules())
    reg = OPT.drawing_register()

    deltas = OPT.part_deltas()
    by: dict[str, list] = {}
    for d in deltas:
        by.setdefault(d.mod, []).append(d)
    kinds: dict[str, int] = {}
    for d in deltas:
        kinds[d.kind] = kinds.get(d.kind, 0) + 1
    detail = "".join(
        f'<details><summary>{esc(m)} {esc(T.MODULE_NAME[m])} · {len(ds)} 종 · '
        f'{sum(d.dkg for d in ds):+,.0f} kg</summary>'
        f'<div class="tw"><table><caption>{esc(m)} 부품 차이</caption>'
        f"<thead><tr><th>품번</th><th>옵션 도번</th><th>명칭</th><th>구분</th><th>표준</th><th>옵션</th>"
        f'<th class="num">개수 차</th><th class="num">kg 차</th></tr></thead><tbody>'
        + "".join(f'<tr><td class="k">{esc(d.pid)}</td>'
                  f'<td class="k">{esc(OPT.part_no(d.opt)) if d.opt else "—"}</td>'
                  f'<td>{esc(d.name)}</td><td class="k">{esc(d.kind)}</td>'
                  f'<td class="k">{_pcell(d.base)}</td><td class="k">{_pcell(d.opt)}</td>'
                  f'<td class="num">{d.dqty:+d}</td><td class="num">{d.dkg:+,.1f}</td></tr>' for d in ds)
        + "</tbody></table></div></details>"
        for m, ds in by.items())

    def _st(sb, st):
        if not sb or not st or sb == st:
            return f"{(st or sb):,.0f}"
        return f"{sb:,.0f} → {st:,.0f}"

    bars = "".join(
        f'<tr><td class="k">{esc(mat)}</td><td>{esc(sec)}</td><td class="num">{_st(sb, st)}</td>'
        f'<td class="num">{nb}</td><td class="num"><strong>{nt}</strong></td>'
        f'<td class="num">{nt - nb:+d}</td><td class="num">{dkg:+,.0f}</td></tr>'
        for mat, sec, sb, st, nb, nt, dkg in OPT.bar_deltas())
    plates = "".join(
        f'<tr><td class="k">{esc(mat)}</td><td class="num">{tt:g}</td>'
        f'<td class="num">{(f"{sh[0]:,}×{sh[1]:,}" if sh else "—")}</td>'
        f'<td class="num">{nb}</td><td class="num"><strong>{nt}</strong></td>'
        f'<td class="num">{nt - nb:+d}</td><td class="num">{dkg:+,.0f}</td></tr>'
        for mat, tt, sh, nb, nt, dkg in OPT.plate_deltas())

    buys = OPT.buy_deltas()
    new_buy = [x for x in buys if x[1] == 0]
    buy_rows = "".join(
        f'<tr><td class="k">{esc(p.pid)}</td><td><strong>{esc(p.name)}</strong></td>'
        f'<td class="k">{esc(spec[0] if spec else "—")}</td>'
        f'<td class="num">{nb}</td><td class="num"><strong>{nt}</strong></td><td class="num">{nt - nb:+d}</td>'
        f'<td>{md(spec[1]) if spec else esc(p.note)}</td></tr>'
        for p, nb, nt, spec in buys)

    lb, lt = OPT.trucks()
    trows = "".join(
        f'<tr><td class="num"><strong>{x.seq}</strong></td><td>{esc(PR.STAGE_NAME[x.stage])}</td>'
        f'<td class="k">{esc(x.truck.name)}</td><td class="num">{len(x.items)}</td>'
        f'<td class="num">{x.kg:,.0f}</td><td class="num">{max(r[4] for r in x.items):,.0f}</td>'
        f'<td>{esc(max(x.items, key=lambda r: r[3])[1])} '
        f'<span class="k">{max(x.items, key=lambda r: r[3])[3]:,.0f} kg</span></td>'
        f'<td>{esc(x.special)}</td></tr>'
        for x in lt)
    longest = max((r for x in lt for r in x.items), key=lambda r: r[4])

    with OPT.pinned():
        sp_t = dict(OPT.PR_T.SPARES)
    spares = "".join(
        f"<li><span class='k'>{esc(pid)}</span> {esc(PR.SPARES.get(pid, '—'))} → <strong>{esc(txt)}</strong></li>"
        for pid, txt in sp_t.items() if PR.SPARES.get(pid) != txt)

    bad = tot["unbuyable"]
    bad_note = ("옵션도 <strong>살 수 없는 치수 0 건</strong>이다 — 7 단으로 높아진 외피는 시트가 한 장 더 "
                "갈라지고(stock.py), 12 m 를 넘는 런웨이는 두 토막으로 이어 붙인다."
                if not bad else f"<strong>옵션에 살 수 없는 치수 {len(bad)} 건</strong> — "
                + esc(" · ".join(f"{a} {b_}" for a, b_, _ in bad)))

    return f"""
<section id="p4"><h2><span class="sn">4</span>옵션 DG-HK120C — 2셀 수평병렬</h2>

  <div class="clause"><div class="n">4.1</div><div class="c">
    <h3>옵션은 차이로 산다</h3>
    <p>옵션 <strong>DG-HK120C</strong> 는 가열실 하나({T.DECKS}단 · {T.LAMPS}등)에 계단 칼날 셀
      {T.CELLS}개를 수평으로 나란히 둔다 (검토서 DG-HK120C · 사양서 1.4항). 옵션의 카탈로그는
      따로 적지 않는다 — 같은 부품 카탈로그를 콘솔 HK120C 의 뿌리 값(단수 · 램프 수 · 셀 수)으로
      다시 풀어 표준과 나란히 놓는다 (<span class="k">tools/variant.py · tools/option.py</span>).
      표준을 고치면 옵션도 같은 식으로 따라 움직인다.</p>
    <div class="logic">옵션 발주 = 표준 발주 + (옵션 − 표준)
옵션 견적 = 표준 견적 + 아래 표의 차이</div>
    <div class="tw"><table>
      <caption>표준과 옵션 — 한눈에</caption>
      <thead><tr><th>항목</th><th class="num">표준 {esc(B.MODEL)}</th><th class="num">옵션 {esc(T.MODEL)}</th>
        <th class="num">차이</th></tr></thead>
      <tbody>{summary}</tbody>
    </table></div>
    <div class="note">{bad_note}</div>
  </div></div>

  <div class="clause"><div class="n">4.2</div><div class="c">
    <h3>모듈별 차이</h3>
    <p>칼날 셀에 딸린 세 모듈(<span class="k">{esc(" · ".join(B.PER_CELL))}</span>)은 셀마다 한 벌씩 서므로
      통째로 곱해진다 — 조립도는 표준 것을 그대로 두 벌 만든다(도번이 같다). 나머지는 공용이고,
      단수 · 셀 간격 · 방책에서 치수가 다시 풀린다. 한 벌이라도 표준과 다른 모듈은 조립도 도번 끝에
      <span class="k">T</span> 가 붙는다.</p>
    <div class="tw"><table>
      <caption>모듈별 품목 · 질량 — 표준 → 옵션</caption>
      <thead><tr><th>모듈</th><th>이름 (옵션)</th><th>조립도</th><th class="num">품목</th><th class="num">질량 kg</th>
        <th class="num">차이 kg</th><th>무엇이 바뀌나</th></tr></thead>
      <tbody>{mods}</tbody>
    </table></div>
  </div></div>

  <div class="clause"><div class="n">4.3</div><div class="c">
    <h3>부품 차이 — {len(deltas)} 종</h3>
    <p>옵션에만 있는 부품 <strong>{kinds.get("추가", 0)} 종</strong>, 수량만 달라진 부품
      <strong>{kinds.get("수량", 0)} 종</strong>, 치수가 달라진 부품
      <strong>{kinds.get("치수", 0) + kinds.get("수량·치수", 0)} 종</strong>이다.</p>
    <p><strong>도번은 형상을 가리킨다.</strong> 옵션 도면 세트는 표준 부품도
      <strong>{len(reg["same"])} 장</strong>을 그대로 쓰고 <strong>{len(reg["new"])} 장</strong>이 새로 선다 —
      치수가 달라졌거나 옵션에만 있는 부품이며 도번 끝에 <span class="k">T</span> 가 붙는다
      (<span class="k">{esc(reg["new"][0])}</span> …). 같은 도번에 다른 치수가 돌면 창고에서 섞인다.
      도면은 콘솔 부품도·조립도 탭에서 <em>도면 세트 → 옵션</em> 으로 연다
      (<span class="k">tools/gen_option_js.py</span> 가 이 카탈로그에서 찍는다).</p>
    {detail}
  </div></div>

  <div class="clause"><div class="n">4.4</div><div class="c">
    <h3>자재 차이 — 정척 · 시트</h3>
    <p>차이는 절단 배치를 옵션으로 다시 푼 결과에서 낸다 — 표준 본수에 부재 길이 합을 더하면
      12 m 짜리를 6 m 정척 두 본에 넣을 수 있다고 착각한다.</p>
    <div class="tw"><table>
      <caption>형강·강관·봉 — 달라진 것만</caption>
      <thead><tr><th>재질</th><th>단면</th><th class="num">정척</th><th class="num">표준</th>
        <th class="num">옵션</th><th class="num">차이</th><th class="num">순중량 차 kg</th></tr></thead>
      <tbody>{bars}</tbody>
    </table></div>
    <div class="tw"><table>
      <caption>판재 — 달라진 것만 (소입 재질은 사는 두께)</caption>
      <thead><tr><th>재질</th><th class="num">두께</th><th class="num">시트</th><th class="num">표준</th>
        <th class="num">옵션</th><th class="num">차이</th><th class="num">순중량 차 kg</th></tr></thead>
      <tbody>{plates}</tbody>
    </table></div>
  </div></div>

  <div class="clause"><div class="n">4.5</div><div class="c">
    <h3>구매품 차이 — {len(buys)} 종</h3>
    <p>옵션에만 있는 구매품 <strong>{len(new_buy)} 종</strong>
      (<span class="k">{esc(" · ".join(p.pid for p, *_ in new_buy))}</span>)의 발주 사양은 이 표가 전부다.
      나머지는 3부의 사양 그대로 수량만 달라진다.</p>
    <div class="tw"><table>
      <caption>구매품 — 수량이 달라진 것</caption>
      <thead><tr><th>품번</th><th>명칭</th><th>계통</th><th class="num">표준</th><th class="num">옵션</th>
        <th class="num">차이</th><th>정격·성능 (옵션)</th></tr></thead>
      <tbody>{buy_rows}</tbody>
    </table></div>
  </div></div>

  <div class="clause"><div class="n">4.6</div><div class="c">
    <h3>운반 — 옵션 차수표</h3>
    <p>표준 {len(lb)} 차가 옵션에서 <strong>{len(lt)} 차</strong>가 된다. 가장 긴 짐은
      {esc(longest[1])} <span class="m">{longest[4]:,.0f}</span> 이다.</p>
    <div class="tw"><table>
      <caption>옵션 운반 차수 — 총 {len(lt)} 차 · {sum(x.kg for x in lt):,.0f} kg</caption>
      <thead><tr><th>차수</th><th>세우는 단계</th><th>차량</th><th>품목</th><th>적재 kg</th>
        <th>최장변</th><th>최중량 단품</th><th>비고</th></tr></thead>
      <tbody>{trows}</tbody>
    </table></div>
  </div></div>

  <div class="clause"><div class="n">4.7</div><div class="c">
    <h3>예비품 — 셀마다 닳는 것은 셀 수만큼</h3>
    <p>칼날 두 자루가 같은 속도로 닳는다. 셀에 딸린 소모품은 셀 수만큼, 램프는 10 % 규칙 그대로다.</p>
    <ul>{spares}</ul>
  </div></div>
</section>"""


def build() -> str:
    bl, pl = PR.bar_lots(), PR.plate_lots()
    loads = PR.truck_loads()
    buy = PR.buy_rows()
    steel = sum(l.kg_net for l in bl) + sum(l.kg_net for l in pl)

    toc = "".join(
        f'<li><a href="#p{i}"><b>{i}</b>{t}</a></li>'
        for i, t in enumerate(["자재 발주표", "운반 분할", "구매품 사양", "옵션 DG-HK120C"], start=1))

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#eceff1">
<title>DG-HK60C 조달 지침서</title>
<meta name="description" content="DG-HK60C 폐태양광 패널 분리설비의 조달 지침서 — 정척 절단 배치를 푼 자재 발주표, 세우는 순서를 따르는 운반 차수표, 발주 가능한 수준의 구매품 사양.">
{house_style()}
<style>
  details{{margin:10px 0 0}}
  details summary{{cursor:pointer;font-size:13px;color:var(--brand);padding:6px 0}}
  details[open] summary{{margin-bottom:6px}}
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

  <div class="doc-kind">조달 지침서 · Procurement &amp; Logistics</div>
  <h1>DG-HK60C 태양광 패널 분리설비<br>조달 지침서</h1>
  <p class="subtitle">부품 카탈로그를 <strong>살 수 있는 것과 실을 수 있는 것</strong>으로 바꾼다.
    정척 <strong>{sum(l.bars for l in bl)} 본</strong> · 시트 <strong>{sum(l.sheets for l in pl)} 매</strong> ·
    강재 <strong>{steel:,.0f} kg</strong> · 운반 <strong>{len(loads)} 차</strong> ·
    구매품 <strong>{len(buy)} 종</strong>. 4부는 옵션 DG-HK120C(2셀 수평병렬)의 차이다.</p>

  <dl class="docref">
    <div><dt>문서번호</dt><dd>DG-HK60C-PRC-001</dd></div>
    <div><dt>개정</dt><dd>Rev.0</dd></div>
    <div><dt>발행일</dt><dd>2026-09-06</dd></div>
    <div><dt>대상 배치</dt><dd>REV.21C (DG-HK60C)</dd></div>
    <div><dt>부품 근거</dt><dd>tools/parts.py</dd></div>
    <div><dt>계산 근거</dt><dd>tools/procure.py</dd></div>
  </dl>
</header>

<nav class="toc" aria-label="목차">
  <h2>목차</h2>
  <ol>{toc}</ol>
</nav>

<div class="clause"><div class="n">0</div><div class="c">
  <h3>이 문서를 나눠 쓰는 법</h3>
  <p>세 부는 읽는 사람이 다르다 — <strong>1부는 자재 담당, 2부는 물류·현장, 3부는 구매 담당</strong>.
    부별로 따로 뽑아 써도 되지만 근거는 하나다. 부품 카탈로그
    (<span class="k">tools/parts.py</span>)가 바뀌면 세 부가 함께 움직인다 —
    따로 만들면 카탈로그를 고친 날 셋이 따로 낡는다.</p>
  <div class="note"><strong>이 문서는 손으로 고치지 않는다.</strong>
    <span class="k">tools/gen_procure_doc.py</span> 가 카탈로그에서 생성한다.
    수량이 틀렸으면 카탈로그를 고치고 다시 찍는다.</div>
</div></div>
{part1()}
{part2()}
{part3()}
{part4()}

<footer class="foot">
  <p><strong>DG-HK60C-PRC-001 Rev.0</strong> · 2026-09-06 · DYNAMIC INDUSTRY</p>
  <p>제작 지침서 <span class="k">DG-HK60C-FAB-001</span> ·
    조립 지침서 <span class="k">DG-HK60C-ASM-001</span> 과 한 벌로 낸다.
    수량과 형상은 개념설계가 유도한 값이며 상세설계에서 확정한다 —
    <strong>확정 전 발주는 납기가 긴 품목(서보·안전 부품)에 한한다.</strong></p>
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
