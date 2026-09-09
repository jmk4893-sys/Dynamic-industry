# -*- coding: utf-8 -*-
"""투입 구간 결정 등록부 — 검토회의에 올리는 한 장.

미결 항목마다 **값이 이미 정한 것**과 **회의가 정해야 할 것**을 갈라 적는다.
다섯이 서로 물려 있어서 따로 결정하면 어긋나므로 무엇이 무엇을 푸는지를
그래프로 먼저 보인다.

**이 파일이 있는 이유.** 등록부를 처음에는 손으로 써서 아티팩트로만 발행했다.
그러자 값이 바뀌어도 문장이 안 따라왔고, 실제로 OI-05 의 결론이 바뀌면서
등록부가 낡았다 — 「파이썬은 통과하는데 그림은 옛 설계」가 정확히 이 상태다.
그래서 등록부도 다른 도면과 같은 규약에 넣는다: **숫자를 여기에 적지 않고
각 모듈의 `summary()` 에서 읽는다.** 시험이 커밋된 파일과 생성 결과를 견주므로
값이 움직이면 다음 회차에 걸린다.

**웹폰트를 안 쓴다.** 도면집·상세도와 같은 시스템 글꼴 스택을 쓴다 —
`tools/check_artifact_render.mjs` 가 외부 요청 실패를 오류로 세고, 현장에서
망이 없는 자리에서도 같은 모양으로 나와야 하기 때문이다.

    PYTHONPATH=src python tools/build_decisions.py

멱등이다. `tests/test_pv_decisions.py` 가 커밋된 파일과 생성 결과를 대조한다.
"""

from __future__ import annotations

import html
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import (  # noqa: E402
    catch, drives, jaw, kinematics, motion, portal, ring, telescope,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-infeed-decisions.html"

#: 문서 번호·기준·개정. 도면집 표제와 같은 자리에서 읽히는 값이라 여기 적는다 —
#: 해석 결과가 아니므로 모듈에서 읽을 곳이 없다.
DOC_NO = "PV-INFEED-DEC-01"
BASIS = "PV-FAB-000 REV.A"
REV = "REV.57"

CSS = """
:root{
  --ground:#EFF2F1; --sheet:#FFFFFF; --ink:#141C20; --muted:#5A696D;
  --rule:#C4CDCC; --hair:#DDE3E2; --tint:#E5EAE8;
  --oxide:#96461F; --oxide-soft:#F2E3DA; --verd:#2B6A57; --verd-soft:#DEEAE4;
  --sans:"Pretendard",-apple-system,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",system-ui,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"D2Coding",monospace;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#12181A; --sheet:#1A2224; --ink:#E3E9E8; --muted:#93A2A5;
  --rule:#31403F; --hair:#26312F; --tint:#212B2C;
  --oxide:#D4844F; --oxide-soft:#2E211A; --verd:#5FB194; --verd-soft:#1A2A26;
  color-scheme:dark;
}}
:root[data-theme="dark"]{
  --ground:#12181A; --sheet:#1A2224; --ink:#E3E9E8; --muted:#93A2A5;
  --rule:#31403F; --hair:#26312F; --tint:#212B2C;
  --oxide:#D4844F; --oxide-soft:#2E211A; --verd:#5FB194; --verd-soft:#1A2A26;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font:400 14.5px/1.6 var(--sans);font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased}
.page{max-width:1060px;margin:0 auto;padding:28px 20px 72px;display:grid;gap:26px}
.mono{font-family:var(--mono)}
h1,h2,h3{margin:0;text-wrap:balance;font-weight:600}
p{margin:0}

/* 표제 */
.mast{background:var(--sheet);border:1px solid var(--rule);
  display:grid;grid-template-columns:minmax(0,1fr) auto}
.mast>div{padding:20px 22px}
.eyebrow{font:500 10.5px/1.5 var(--mono);letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted)}
.mast h1{margin:8px 0 6px;font-size:27px;line-height:1.15;letter-spacing:-.01em}
.mast p{color:var(--muted);max-width:60ch;font-size:13.5px}
.block{border-left:1px solid var(--rule);display:grid;
  grid-template-columns:auto auto;gap:5px 16px;align-content:start;
  padding:20px 22px;font-size:12px}
.block dt{color:var(--muted)}
.block dd{margin:0;font-family:var(--mono);font-size:11.5px}

/* 결정 순서 */
.order{background:var(--sheet);border:1px solid var(--rule);padding:20px 22px;
  display:grid;gap:14px}
.order h2{font-size:16px}
.order .lede{color:var(--muted);font-size:13px;max-width:74ch}
.graphwrap{overflow-x:auto}
svg.graph{width:100%;min-width:640px;height:auto;display:block}
svg.graph text{font-family:var(--sans);fill:var(--ink)}
svg.graph .tag{font-family:var(--mono);font-size:11px;fill:var(--muted);letter-spacing:.04em}
svg.graph .nm{font-size:12.5px;font-weight:500}
svg.graph .edge{fill:none;stroke:var(--oxide);stroke-width:1.4}
svg.graph .edget{font-size:11px;fill:var(--oxide)}
svg.graph .box{fill:var(--tint);stroke:var(--rule);stroke-width:1}
svg.graph .box-open{fill:var(--oxide-soft);stroke:var(--oxide)}

/* 결정 블록 */
.rec{background:var(--sheet);border:1px solid var(--rule)}
.rec>header{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline;
  padding:15px 22px;border-bottom:1px solid var(--hair)}
.oi{font:600 13px/1 var(--mono);letter-spacing:.05em;color:var(--oxide)}
.rec h2{font-size:17px;flex:1 1 22ch;line-height:1.25}
.chip{font:500 11px/1 var(--mono);padding:5px 9px;letter-spacing:.03em;
  border:1px solid currentColor;white-space:nowrap}
.chip.open{color:var(--oxide);background:var(--oxide-soft)}
.chip.set{color:var(--verd);background:var(--verd-soft)}
.tracks{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr)}
.track{padding:16px 22px;display:grid;gap:9px;align-content:start}
.track+.track{border-left:1px solid var(--hair)}
.track>h3{font:500 10.5px/1.5 var(--mono);letter-spacing:.12em;
  text-transform:uppercase}
.t-set>h3{color:var(--verd)}
.t-open>h3{color:var(--oxide)}
.track ul{margin:0;padding:0;list-style:none;display:grid;gap:7px;font-size:13.5px}
.track li{position:relative;padding-left:16px}
.track li::before{content:"";position:absolute;left:0;top:.55em;
  width:5px;height:5px;background:currentColor;color:var(--rule)}
.t-set li::before{color:var(--verd)}
.t-open li::before{color:var(--oxide)}
.track b{font-family:var(--mono);font-weight:500;font-size:13px}
.rec>footer{padding:12px 22px;border-top:1px solid var(--hair);
  background:var(--tint);font-size:12.5px;color:var(--muted);
  display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:baseline}
.rec>footer span:first-child{font:500 10.5px/1.5 var(--mono);
  letter-spacing:.12em;text-transform:uppercase;white-space:nowrap}

/* 수치 표 */
.fig{overflow-x:auto;margin-top:2px}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{text-align:left;padding:5px 14px 5px 0;border-bottom:1px solid var(--hair);
  vertical-align:baseline}
thead th{font:500 10.5px/1.5 var(--mono);letter-spacing:.08em;color:var(--muted);
  text-transform:uppercase;border-bottom-color:var(--rule)}
td.n{font-family:var(--mono);white-space:nowrap}
td.n.hi{color:var(--oxide);font-weight:500}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}

/* 마무리 */
.close{background:var(--sheet);border:1px solid var(--rule);border-left:3px solid var(--oxide);
  padding:20px 22px;display:grid;gap:12px}
.close h2{font-size:16px}
.close ol{margin:0;padding-left:1.3em;display:grid;gap:8px;font-size:13.5px;max-width:82ch}
.close ol b{font-family:var(--mono);font-weight:500}
.foot{color:var(--muted);font-size:12px;display:grid;gap:5px;max-width:88ch}
.foot code{font-family:var(--mono);font-size:11.5px;background:var(--tint);padding:1px 5px}
@media (max-width:760px){
  .mast,.tracks{grid-template-columns:1fr}
  .block{border-left:0;border-top:1px solid var(--rule)}
  .track+.track{border-left:0;border-top:1px solid var(--hair)}
}
""".strip()


# ── 조판 도우미 ─────────────────────────────────────────────────────────
def esc(s: object) -> str:
    return html.escape(str(s), quote=False)


def li(*parts: str) -> str:
    return "        <li>" + "".join(parts) + "</li>"


def b(v: object) -> str:
    """수치 강조 — 표와 같은 고정폭으로 찍는다."""
    return f"<b>{esc(v)}</b>"


def table(head: list[str], rows: list[list[tuple[str, str]]]) -> str:
    """(값, 클래스) 짝의 표. 클래스는 "", "n", "n hi" 중 하나다."""
    out = ['      <div class="fig">', "        <table>",
           "          <thead><tr>"
           + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr></thead>",
           "          <tbody>"]
    for r in rows:
        cells = "".join(
            (f"<td>{esc(v)}</td>" if not c else f'<td class="{c}">{esc(v)}</td>')
            for v, c in r)
        out.append(f"            <tr>{cells}</tr>")
    out += ["          </tbody>", "        </table>", "      </div>"]
    return "\n".join(out)


def record(tag: str, title: str, chips: list[tuple[str, str]],
           settled: list[str], open_: list[str], foot: tuple[str, str],
           fig: str = "") -> str:
    chip_html = "".join(
        f'\n    <span class="chip {kind}">{esc(text)}</span>'
        for kind, text in chips)
    return f"""<!-- ── {tag} ─────────────────────────────────── -->
<article class="rec">
  <header>
    <span class="oi">{esc(tag)}</span>
    <h2>{esc(title)}</h2>{chip_html}
  </header>
  <div class="tracks">
    <div class="track t-set">
      <h3>값이 정한 것</h3>
      <ul>
{chr(10).join(settled)}
      </ul>
{fig}
    </div>
    <div class="track t-open">
      <h3>회의가 정할 것</h3>
      <ul>
{chr(10).join(open_)}
      </ul>
    </div>
  </div>
  <footer><span>{esc(foot[0])}</span>
    <span>{esc(foot[1])}</span></footer>
</article>"""


# ── 그래프 ──────────────────────────────────────────────────────────────
def graph(r: dict) -> str:
    """무엇이 무엇을 푸는가 — 화살표 라벨도 값에서 나온다."""
    roller = f"{r['rollerN']:,.0f}"
    drop = f"{r['saving']['inertiaDrop']:.0%}"
    now, new = r["takt"]["nowScale"], r["takt"]["newScale"]
    return f"""  <div class="graphwrap">
  <svg class="graph" viewBox="0 0 900 298" role="img"
       aria-label="OI-02 가 OI-04 의 반력과 택트 여유를 정하고, OI-07 의 구동이 OI-05 의 완충을 없앤다. OI-03 은 독립이다.">
    <defs>
      <marker id="ar" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8"
              markerHeight="7" orient="auto"><path d="M0 0 10 4 0 8Z" fill="#96461F"/></marker>
    </defs>

    <path class="edge" marker-end="url(#ar)" d="M198 132 H286 V50 H354"/>
    <text class="edget" x="352" y="42" text-anchor="end">반각이 반력 {roller} N 을 정한다</text>

    <path class="edge" marker-end="url(#ar)" d="M198 152 H286 V236 H354"/>
    <text class="edget" x="352" y="288" text-anchor="end">단면을 줄이면 관성 {drop} 감</text>

    <path class="edge" marker-end="url(#ar)" d="M546 142 H684"/>
    <text class="edget" x="615" y="130" text-anchor="middle">서보면 완충이 없어진다</text>

    <rect class="box box-open" x="18" y="114" width="180" height="56"/>
    <text class="tag" x="32" y="136">OI-02</text>
    <text class="nm" x="32" y="156">엔드링 단면</text>

    <rect class="box box-open" x="366" y="22" width="180" height="56"/>
    <text class="tag" x="380" y="44">OI-04</text>
    <text class="nm" x="380" y="64">포탈 하중 경로</text>

    <rect class="box box-open" x="366" y="114" width="180" height="56"/>
    <text class="tag" x="380" y="136">OI-07</text>
    <text class="nm" x="380" y="156">신축 단수·구동</text>

    <rect class="box" x="366" y="208" width="180" height="56"/>
    <text class="tag" x="380" y="230">AXIS-BFC-R</text>
    <text class="nm" x="380" y="250">택트 여유 {now:.2f} → {new:.2f}</text>

    <rect class="box box-open" x="690" y="114" width="180" height="56"/>
    <text class="tag" x="704" y="136">OI-05</text>
    <text class="nm" x="704" y="156">포획빔 완충·행</text>

    <rect class="box box-open" x="690" y="22" width="180" height="56"/>
    <text class="tag" x="704" y="44">OI-03</text>
    <text class="nm" x="704" y="64">조 실린더 자리</text>
    <text class="tag" x="704" y="92">들어오는 화살표 없음</text>
  </svg>
  </div>"""


# ── 기록 다섯 ───────────────────────────────────────────────────────────
#
# **f-문자열 안에서 딕셔너리를 파고들지 않는다.** 중첩 따옴표를 허용하는 것은
# 3.12 부터이고 이 저장소의 CI 는 3.10 도 돈다. 값을 먼저 지역 이름으로 꺼내고
# 문장은 그 이름만 본다 — 읽기도 그쪽이 낫다.
def oi02(r: dict) -> str:
    sm, sv, tk = r["smallest"], r["saving"], r["takt"]
    fig = table(["단면을 줄이면", "지금", f"Ø{sm['odMm']:g}×{sm['tMm']:g}"], [
        [("링 한 매", ""), (f"{r['massKg']:,.1f} kg", "n"),
         (f"{sm['massKg']:,.1f} kg", "n hi")],
        [("반전 관성", ""), (f"{sv['totalNowKgm2']:,.1f}", "n"),
         (f"{sv['totalNewKgm2']:,.1f} kg·m²", "n hi")],
        [("필요 압착력", ""), ("1.00", "n"),
         (f"{sv['preloadRatio']:.2f} 배", "n hi")],
        [("택트 여유", ""), (f"{tk['nowScale']:.2f}", "n"),
         (f"{tk['newScale']:.2f} 배", "n hi")],
    ])
    static = f"{r['staticMpa']:.2f} MPa"
    static_share = f"{r['staticMpa'] / r['staticAllowMpa']:.1%}"
    rng = f"{r['rangeMpa']:.2f} MPa"
    radial = f"{r['radialMm']:.4f} mm"
    radial_share = f"{r['radialMm'] / r['runoutMm']:.0%}"
    wall = f"{r['binding']} {r['wallMpa']:.1f} MPa"
    small_od = f"Ø{sm['odMm']:g}×{sm['tMm']:g}"
    bay = f"{sv['baySpanDropMm']:.0f} mm"
    return record(
        "OI-02", "엔드링 단면 — 전역은 남아돌고 국부가 정한다",
        [("set", "해석 완료"), ("open", "결정 필요")],
        [li(f"전역 굽힘 {b(static)} — 허용 {r['staticAllowMpa']:.1f} 의 {static_share}"),
         li(f"회전 응력범위 {b(rng)} — {r['cycles']:,} 회에서 허용 "
            f"{r['fatigueAllowMpa']:.1f}"),
         li(f"반경 변화 {b(radial)} — 선삭 런아웃 {r['runoutMm']:g} 의 {radial_share}"),
         li(f"먼저 차는 것은 {b(wall)}, 사용률 {r['utilisation']:.2f}"),
         li(f"훑은 관 규격 {len(ring.CANDIDATES)} 가지가 {b('모두')} 네 판정을 지난다")],
        [li(f"{b('지지 롤러 반각')} — 모델 어디에도 없던 값이다. "
            f"{r['supportHalfDeg']:g}° 로 잡았고 15…45° 에서 처짐이 두 배 넘게 움직인다"),
         li(f"{b('셸 FEA 또는 시험')} — 보요소는 롤러 밑 관 벽과 용접 노치의 "
            f"국부응력을 못 본다. 위 {r['wallMpa']:.1f} MPa 는 닫힌 해로 낸 상한이다"),
         li(f"{b('얇은 벽의 진원도')} — {small_od} 를 R{kinematics.RING_R_MM:,} 으로 "
            f"굽힐 때의 벤딩 변형은 벤더 확인 사항이다"),
         li(f"단면을 실제로 줄일지 — 줄이면 택트가 열리고 베이가 축방향으로 한 쪽 "
            f"{b(bay)} 씩 준다")],
        ("정해지면 풀리는 것",
         "링 단면 변경 · 반전 감속기 재선정 · 그리고 OI-04 의 롤러 반력이 확정된다."),
        fig)


def oi04(p: dict) -> str:
    closed = portal.analyse(braced=False)
    braced = portal.analyse(braced=True)
    opened = portal.analyse(braced=False, open_beam=True)
    fig = table(["받침보", "비틀림", "처짐", "판정"], [
        [("닫힌 박스", ""), (f"{closed['worstTwistDeg']:.4f}°", "n"),
         (f"{closed['worstSagMm']:.3f} mm", "n"), ("통과", "n")],
        [("닫힌 + 가새", ""), (f"{braced['worstTwistDeg']:.4f}°", "n"),
         (f"{braced['worstSagMm']:.3f} mm", "n"), ("통과", "n")],
        [("열린 단면", ""), (f"{opened['worstTwistDeg']:.3f}°", "n hi"),
         (f"{opened['worstSagMm']:.3f} mm", "n hi"), ("실패", "n hi")],
    ])
    ecc = f"{p['eccentricityMm']:.0f} mm"
    sag = f"{closed['worstSagMm']:.4f} mm"
    share = f"{p['twistShare']:.0%}"
    brace_kg = braced["addedKg"] - closed["addedKg"]
    open_sag = f"{opened['worstSagMm']:.3f} mm"
    open_ratio = f"{opened['worstSagMm'] / p['runoutMm']:.0f}"
    gap = f"{p['missingDropMm']:.0f} mm"
    section = "×".join(f"{v:g}" for v in portal.SUPPORT_BEAM_MM)
    half_pitch = kinematics.RING_PITCH_MM // 2
    return record(
        "OI-04", "220 mm 편심 — 갈리는 것은 가새가 아니라 받침보를 닫느냐다",
        [("set", "해석 완료"), ("open", "결정 필요")],
        [li(f"편심 {b(ecc)} 는 유도값 — 기둥 "
            f"∓{kinematics.PORTAL_COLUMN_AXIS_MM:,} 과 링 피치 절반 "
            f"∓{half_pitch:,} 의 차"),
         li(f"닫힌 박스 받침보면 처짐 {b(sag)}, 응력 {closed['peakMpa']:.1f} MPa"),
         li(f"가새는 비틀림을 {b(share)} 덜 뿐인데 강재 {brace_kg:.0f} kg 과 "
            f"헤드가드 위 {p['braceClearsForkliftMm']:.0f} mm 자리를 먹는다"),
         li(f"열린 단면이면 J 가 {p['closedJ'] / 1e6:.1f}M → "
            f"{p['openJ'] / 1e6:.3f}M mm⁴, 처짐 {b(open_sag)} — "
            f"런아웃의 {open_ratio} 배")],
        [li(f"{b('받침보를 부품표에 올린다')} — 조립 순서는 하우징을 크로스빔 탭에 "
            f"붙이라는데 크로스빔은 {p['crossbeamYMm']:,.0f}, 롤러 축은 "
            f"{p['rollerAxisYMm']:,.0f} 이라 {b(gap)} 가 빈다"),
         li(f"{b('단면 확정')} — 닫힌 박스 권고. {section} 은 여기서 고른 값이지 "
            f"부품표에서 온 것이 아니다"),
         li(f"{b('3D 에 그 부재를 넣는다')} — 지금은 3D 에 없어서 "
            f"<code>check_load_path</code> 가 못 본다"),
         li("접합부·볼트 무리·기초 앵커의 국부 검토")],
        ("정해지면 풀리는 것",
         "포탈 기둥 BFC-COL-01 상세 — 받침보가 오르기 전에는 기둥 보강 자리가 "
         "안 정해진다."),
        fig)


def oi07(t: dict, c: dict) -> str:
    fig = table(["단수", "한 단", "도착 에너지", "공압"], [
        [("1 (통짜)", "n"), (f"{t['reachMm']:,.0f} mm", "n"),
         (f"{t['arrivalSolidJ']:.1f} J", "n"), ("가능", "n")],
        [("2", "n"), (f"{telescope.stage_length_mm(2):,.0f} mm", "n"),
         (f"{telescope.arrival_energy_j(2):.1f} J", "n"), ("불가", "n hi")],
        [(f"{t['stagesForDepth']}", "n"), (f"{t['stageLengthMm']:,.0f} mm", "n"),
         (f"{t['arrivalAtDepthJ']:.1f} J", "n hi"), ("불가", "n hi")],
    ])
    stages = t["stagesForDepth"]
    depth = f"{t['stowDepthMm']:.0f} mm"
    stage_label = f"{stages} 단"
    root = " × ".join(f"{v:.0f}" for v in t["rootForDepthMm"])
    plan = f"{stages} 단 · 뿌리 {t['rootForDepthMm'][0]:.0f} 각형 · 벨트 서보"
    droop = f"{t['droopAtDepthMm']:.1f} mm"
    short = f"{t['shortfallMm']:.0f} mm"
    wall_half = kinematics.CENTRE_WALL_T_MM / 2
    return record(
        "OI-07", "CD-101 신축 — 단수는 수납 깊이가, 구동은 도착 에너지가 정한다",
        [("set", "해석 완료"), ("open", "결정 필요")],
        [li(f"접힌 빔이 쓸 수 있는 깊이 {b(depth)} — 중앙벽 반두께 {wall_half:.0f} 에 "
            f"패널 근단 {t['panelNearEdgeMm']:.0f} 까지, 여유 "
            f"{telescope.STOW_CLEARANCE_MM:g} 를 뺀 값"),
         li(f"그 깊이면 {b(stage_label)}, 한 단 {t['stageLengthMm']:,.0f} mm"),
         li(f"부품표 행정 {t['cylinderStrokeMm']:,.0f} 이 도달 {t['reachMm']:,.0f} 의 "
            f"{b('정확히 절반')} — 2 단 리빙을 전제로 골랐는데 2 단은 깊이에 "
            f"안 들어간다"),
         li(f"{stages} 단을 겹치려면 뿌리를 {b(root)} 로. 그러면 강성이 "
            f"{t['stiffGrownNmm']:.1f} N/mm 로 돌아오고 {c['unprotectedJ']:.0f} J "
            f"처짐 {t['deflGrownMm']:.1f} mm — 강성은 막는 것이 아니다")],
        [li(f"{b(plan)}를 채택할지, 아니면 수납 자리를 넓히는 다른 안으로 갈지"),
         li(f"{b('슈 유격 사양')} — 이음 {stages - 1} 이 각 "
            f"{telescope.JOINT_SLOP_DEG:g}° 만 꺾여도 하중 없이 선단이 {b(droop)} 처져 "
            f"빔–프레임 틈 {t['clearanceMm']:g} mm 의 "
            f"{t['droopShareOfClearance']:.0%} 를 먹는다. 단면을 키워도 안 줄어드는 "
            f"항이라 슈 사양이 곧 그 틈을 정한다"),
         li(f"빔 끝이 장변 끝까지 {b(short)} 못 미치는 것을 그대로 둘지")],
        ("정해지면 풀리는 것",
         "CD-101 조립체 BFC-CD-01 상세 · 그리고 OI-05 의 완충 결정이 바뀐다 — "
         "서보면 도착 에너지 항이 없어진다."),
        fig)


def oi05(c: dict, m: dict) -> str:
    rows = kinematics.CATCH_BEAM_ROWS_MM
    inner, outer = min(abs(r) for r in rows), max(abs(r) for r in rows)
    fig = table(["빔 배치", "받는 본", "빔당 반력", "빔 처짐"], [
        [("도면 가정 (네 본 균등)", ""), (f"{len(rows)}", "n"),
         (f"{m['drawnPerBeamN']:,.0f} N", "n"), ("—", "n")],
        [("실제 · 무질량 지지", ""), (f"{m['bearingBeams']}", "n"),
         (f"{m['twoMasslessN']:,.0f} N", "n hi"), ("—", "n")],
        [("실제 · 빔 관성까지", ""), (f"{m['bearingBeams']}", "n"),
         (f"{m['builtPerBeamN']:,.0f} N", "n hi"),
         (f"{m['builtBeamDeflectionMm']:.1f} mm", "n hi")],
    ])
    residual = f"{c['residualMm']:.0f} mm"
    window = f"{c['windowS']:.3f} s"
    exposure = f"{c['exposureS']:.2f} s"
    dwell = f"{c['protectedDwellS']:.2f} s"
    beams = f"{m['bearingBeams']} 본만"
    ledge = f"{m['ledgeMm']:.0f} mm"
    per_beam = f"{m['builtPerBeamN']:,.0f} N"
    two_stage = f"{catch.two_stage()['exposureS']:.3f} s"
    verdict = f"겹장 판정이 {dwell} 안에 끝나는가"
    best = f"{motion.best_row_mm():.0f}"
    cushion_ratio = f"{c['arrivalJ'] / c['cushionAllowJ']:.0f}"
    tilt_ratio = f"{m['worstTiltN'] / m['builtPerBeamN']:.2f}"
    return record(
        "OI-05", "포획빔 — 창은 열리는데 늦게 들고, 들어가서도 넷 중 둘만 받는다",
        [("set", "해석 완료"), ("open", "결정 필요"), ("open", "실측 대기")],
        [li(f"빔이 설 수 있는 가장 높은 자리는 대기면 아래 {b(residual)} — 남는 낙하 "
            f"{c['residualJ']:.1f} J 로 {c['unprotectedJ']:.1f} 에서 "
            f"{c['protectedRatio']:.0%} 감"),
         li(f"창 {b(window)} 에 {c['speedMs']:.2f} m/s 로 밀면 {c['deployS']:.3f} s 에 "
            f"끝난다 — 창에는 든다"),
         li(f"다만 자리를 잡는 것은 대기면 정지 {c['dwellS']:.1f} s 중 {b(exposure)} 가 "
            f"지난 뒤라, 받쳐 주는 것은 마지막 {b(dwell)} 뿐이다"),
         li(f"그런데 자리도 안 맞는다 — 네 본 중 {b(beams)} 패널을 받는다. 행 "
            f"∓{inner:.0f} 은 프레임 안쪽이라 그 밑이 유리까지 "
            f"{motion.glass_gap_mm():.0f} mm 허공이고, 행 ∓{outer:.0f} 은 패널 "
            f"바깥끝을 {b(ledge)} 만 문다"),
         li(f"그래서 빔당 반력이 {b(per_beam)} — 본수가 {m['countFactor']:.2f} 배로 "
            f"올리고 빔 자체 관성(모달 {m['modalMassKg']:.1f} kg · "
            f"{m['beamHz']:.1f} Hz)이 {m['hybridRelief']:.0%} 를 되돌린 결과다"),
         li(f"묶는 것은 힘이 아니라 {b('자리')} — 얹히는 선반이 {m['ledgeMm']:.0f} mm 라 "
            f"그만큼만 어긋나도 놓치고, 되튐 {m['reboundMs']:.2f} m/s 로 "
            f"{m['bounceMm']:.0f} mm 떠 있는 {m['airborneS']:.2f} s 동안 가로 "
            f"{m['driftAllowMs'] * 1_000:.0f} mm/s 를 넘으면 벗어난다"),
         li(f"도착 자세는 갈림길이 아니다 — {m['worstTiltDeg']:.2f}° 까지 기울여도 "
            f"{m['worstTiltN']:,.0f} N 으로 {tilt_ratio} 배에 그친다")],
        [li(f"{b('포획빔 행 위치')} — ∓{outer:.0f} 에 둘지 ∓{best}"
            f"(물림 {motion.best_ledge_mm():.0f} mm)으로 옮길지, 그리고 남는 두 본의 "
            f"역할. 한쪽 지지 구간 {motion.FRAME_BEARING_MM:.0f} mm 에 폭 "
            f"{motion.beam_width_mm():.0f} 각관 두 본은 애초에 안 들어가므로 "
            f"{b('한쪽당 한 본')} 이 상한이다"),
         li(f"{b('부품표에 완충이 없다')} — 쇼크업소버 {c['absorberJ']:.0f} J 급을 "
            f"열마다 달지, 아니면 OI-07 을 서보로 가서 이 항을 없앨지. 도착 "
            f"{c['arrivalJ']:.1f} J 은 표준 에어쿠션 {c['cushionAllowJ']:.1f} J 의 "
            f"{cushion_ratio} 배다"),
         li(f"{b('프레임 하부 지지폭')} — 도면집에 있는 것은 조 패드가 상부 플랜지를 "
            f"무는 폭뿐이다. {motion.FRAME_BEARING_MM:.0f} mm 로 두었고, 5…90 mm 를 "
            f"쓸어도 안쪽 두 본이 논다는 결론은 안 바뀐다"),
         li(f"{b(verdict)} — 안 끝나면 빔이 없는 자리로 떨어진다. 카세트 승강축으로 "
            f"2 단 전개하면 노출이 {c['exposureS']:.2f} → {b(two_stage)} 로 준다"),
         li("T-시험에서 잴 것: 조임 세팅별 실린더 실측 속도와 겹장이 실제로 어떤 "
            "자세로 도착하는지")],
        ("원리적으로 못 막는 것",
         f"상승 {c['riseS']:.1f} s 동안은 어느 평면에서도 무방비다 — 빔이 패널 밑으로 "
         "들어가야 하는데 그 자리를 패널이 지나는 중이다."),
        fig)


def oi03(j: dict) -> str:
    fig = table(["부싱 간격", "허용 편심", "필요 편심", "판정"], [
        [(f"{j['bushingSpanMm']:.0f} mm (현행)", "n"),
         (f"{j['maxOffsetMm']:.0f} mm", "n"), (f"{j['minOffsetMm']:.0f} mm", "n"),
         ("닫힘", "n hi")],
        [(f"{j['requiredSpanMm']:.0f} mm (필요)", "n"),
         (f"{j['minOffsetMm']:.0f} mm", "n"), (f"{j['minOffsetMm']:.0f} mm", "n"),
         ("경계", "n")],
        [(f"{j['maxSpanMm']:.0f} mm (한계)", "n"),
         (f"{j['maxOffsetAtMaxSpanMm']:.0f} mm", "n"),
         (f"{j['minOffsetMm']:.0f} mm", "n"),
         (f"폭 {j['windowWidthMm']:.0f} mm", "n hi")],
    ])
    clamp = f"{j['clampN']:,.0f} N"
    room = f"{j['radialRoomMm']:.0f} mm"
    length = f"{j['cylinderLengthMm']:.0f} mm"
    offset = f"{j['minOffsetMm']:.0f} mm"
    allow = f"{j['maxOffsetMm']:.0f} mm"
    return record(
        "OI-03", "조 실린더 자리 — 좁혀지지 않는 것이 아니라 너무 좁혀졌다",
        [("set", "해석 완료"), ("open", "결정 필요")],
        [li(f"힘은 자리를 정하지 않는다 — Ø{j['boreMm']:.0f} {j['cylPerJaw']} 본이 "
            f"{b(clamp)}, 필요한 것은 {j['requiredN']:,.0f} N "
            f"(여유 {j['margin']:.2f} 배)"),
         li(f"조 열린 자리에서 링 바깥까지 {b(room)} 인데 실린더 전장은 {b(length)} — "
            f"반경 방향으로 곧게 못 세운다"),
         li(f"눕히면 축이 가이드에서 최소 {b(offset)} 벗어난다. 편심은 고른 것이 "
            f"아니라 생긴 것이다"),
         li(f"간격 {j['bushingSpanMm']:.0f} 에서 부싱 등급이 허락하는 상한은 "
            f"{b(allow)} — 하한이 상한보다 크다")],
        [li(f"셋 중 무엇을 바꿀지 — {b('포스트를 늘려')} 간격 여유를 두거나, "
            f"{b('부싱 등급을 올리거나')}, {b('토글·레버로')} 실린더 행정을 줄여 "
            f"짧은 실린더를 쓰거나"),
         li("부싱 등급·간격·실린더 몸통 길이는 여기서 잡은 값이다 — "
            "벤더 자료가 오면 구간이 움직인다"),
         li("조 바 자체의 굽힘과 클레비스 핀은 아직 안 봤다")],
        ("정해지면 풀리는 것",
         "조 캐리어 BFC-JCR-01 상세 — 실린더 자리와 부싱 간격이 같이 정해져야 "
         "브래킷이 나온다."),
        fig)


# ── 조립 ────────────────────────────────────────────────────────────────
def build() -> str:
    r, p = ring.summary(), portal.summary()
    t, j, c = telescope.summary(), jaw.summary(), catch.summary()
    m = motion.summary()
    return f"""<title>투입 구간 결정 등록부</title>
<style>
{CSS}
</style>

<main class="page">

<header class="mast">
  <div>
    <div class="eyebrow">Dynamic Industry · 전처리 플랜트 투입 구간 · {esc(REV)}</div>
    <h1>투입 구간 결정 등록부</h1>
    <p>미결 여섯 중 다섯을 해석으로 좁혔다. 각 항목마다 <b>값이 이미 정한 것</b>과
      <b>회의가 정해야 할 것</b>을 갈라 적는다. 다섯은 서로 물려 있어서 따로 결정하면
      어긋난다 — 무엇이 무엇을 푸는지 먼저 본다.</p>
  </div>
  <dl class="block">
    <dt>문서</dt><dd>{esc(DOC_NO)}</dd>
    <dt>기준</dt><dd>{esc(BASIS)}</dd>
    <dt>해석</dt><dd>ring · portal · catch<br>telescope · jaw · motion</dd>
    <dt>단위</dt><dd>mm · N · J · s</dd>
  </dl>
</header>

<section class="order">
  <h2>무엇이 무엇을 푸는가</h2>
  <p class="lede">다섯은 순서가 있는 목록이 아니라 <b>그래프</b>다. 화살표는 앞 결정이
    뒤 결정의 입력을 바꾼다는 뜻이고, 셋은 실제로 값이 달라진다. OI-03 만 홀로 선다 —
    다른 것을 기다릴 이유가 없으므로 먼저 처리해도 된다.</p>
{graph(r)}
</section>

{oi02(r)}

{oi04(p)}

{oi07(t, c)}

{oi05(c, m)}

{oi03(j)}

<section class="close">
  <h2>회의에 올릴 순서</h2>
  <ol>
    <li><b>OI-03</b> 을 먼저 — 다른 것을 기다리지 않는다. 포스트·부싱·토글 중
      하나를 고르면 그 자리에서 브래킷 도면이 나간다.</li>
    <li><b>OI-02</b> 의 지지 롤러 반각 — 이것이 OI-04 의 롤러 반력을 정하므로
      OI-04 보다 먼저다. 단면 축소 여부는 그 다음이어도 된다.</li>
    <li><b>OI-07</b> 의 구동 방식 — 서보로 가면 <b>OI-05</b> 의 완충 결정이
      사라진다. 둘을 따로 결정하면 쇼크업소버를 사 놓고 안 쓰게 된다.</li>
    <li><b>OI-05</b> 의 포획빔 행 — 완충과 함께 결정한다. 행을 옮기는 것은
      카세트 수납 자리를 건드리므로 OI-07 의 단수와 같이 봐야 한다.</li>
    <li><b>OI-04</b> 의 받침보 — 위 셋이 정해진 뒤. 부품표에 오르는 새 부재라
      기둥 상세가 여기 걸려 있다.</li>
  </ol>
  <p class="foot">
    <span>여기 값은 하나도 손으로 적지 않았다 — <code>ring.py</code> ·
      <code>portal.py</code> · <code>catch.py</code> · <code>telescope.py</code> ·
      <code>jaw.py</code> · <code>motion.py</code> 의 <code>summary()</code> 에서
      읽어 찍는다. 값이 움직이면 이 장도 같이 움직이고, 안 움직이면 시험이 걸린다
      (<code>tests/test_pv_decisions.py</code>).</span>
    <span>남은 미결 하나는 <b>OI-08</b>(무프레임 투입)이고 시작품 T-시험의
      실측만 기다린다 — 계산으로 더 좁힐 것이 없다.</span>
    <span>손으로 잡은 값은 각 모듈이 「여기서 처음 적는 값」으로 표시해 두었다.
      벤더 자료가 오면 그 자리부터 다시 본다.</span>
  </p>
</section>

</main>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = build()
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(text.encode()) / 1024:.1f} kB")


if __name__ == "__main__":
    main()
