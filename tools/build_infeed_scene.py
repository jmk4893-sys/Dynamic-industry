# -*- coding: utf-8 -*-
"""통합 설계도(3D 영상 콘솔)에서 **투입 구간만 남긴** 파생본을 만든다.

`docs/drawings/pv-preprocess-plant.html` 은 플랜트 전체를 한 장면에 담는다. 투입
구간만 떼어 보려면 장면·시계·시점·화면 넷을 같이 좁혀야 한다.

* **장면** — afu·robot 셀은 그대로, jbr 셀은 JB-201 인계 롤러(존 경계를 건너는
  하드웨어)까지만, afr·post·buffer·grm 셀과 그 하류의 시설·케이싱·브래킷은 숨긴다.
  형상을 지우지 않고 `visible=false` 로 끈다 — 원본 3D 는 손대지 않는다.
* **시계** — 종단 체류 124.03 s 를 **방출 주기 48 s** 로 자른다. 40 s 에 JBR 이
  받고 8 s 뒤 스토퍼가 물리는 순간이 다음 장의 시작이다. 단계 목록(Fs)은 이미
  40 s 에서 끝나므로 자를 것이 없다.
* **시점** — 기본 시점을 통합라인에서 투입셀 전체로, 시점 버튼은 투입 구간의
  다섯 개만 남긴다. 자동추적은 원래 투입 단계마다 stack·turner·robot·handoff 를
  고르므로 그대로 둔다.
* **화면** — 흐름표는 JB-201 까지, 도면 모듈 선택은 AFU·BFC·RB/PT 세 장. 결과가
  꺼진 셀에서 일어나는 하류 전용 조작(정션박스 검출·JBR 검증·AFR 레시피 시나리오·
  버퍼 초기화)은 숨기고, 40–48 s 단계 이름은 인계 관점으로 적는다.
  외장 케이싱은 기구를 가리므로 그룹을 끄고 토글도 치운다. 3D 그림자(shadow map)는 끈다.
* **배치도** — 원본의 '전체 장비배치도' 탭은 플랜트 전 장비를 그린다. 파생본에서는
  그 자리에 **투입 장비만** 둔다: 상세도(`build_infeed_detail.plan_view`)의 투입 구간
  평면 배치와, 투입 셀·장비의 가로(L·X)·세로(W·Y)·높이(H·Z) 외형 표다. 원본의
  전체 배치 SVG·초점 선택·존 표는 숨기고, 하류 AFR–GBR 평면배치도 접이도 숨긴다.
  외형 값은 통합 설계도 부품표와 `layout.STATIONS` 에서 읽는다.

원본 파일을 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 하고 아니면 멈춘다 —
원본이 바뀌어 앵커가 사라지면 파생본이 조용히 옛 모습으로 남는 대신 생성이
실패한다. 값(48 s)은 캠페인 모델에서 온다.

    PYTHONPATH=src python tools/build_infeed_scene.py

멱등이다. `tests/test_pv_infeed_detail.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_infeed_detail as detail  # noqa: E402
from pv_preprocess import campaign, layout  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-infeed-scene.html"

#: 남기는 시점 버튼 — 투입 구간의 것만.
KEEP_VIEWS: tuple[str, ...] = ("stack", "afu", "robot", "turner", "handoff")
#: 남기는 도면 모듈.
KEEP_STATIONS: tuple[str, ...] = ("afu", "bfc", "robot")
#: 흐름표에서 남기는 단계 수 — FL/LFT · SE/VS · BFC · RB · PT · JB-201.
KEEP_FLOW_STEPS = 6
#: 숨기는 하류 전용 조작 — 정션박스 검출 시나리오 · JBR 안전·품질 검증 시나리오 · AFR 레시피 시나리오.
DOWNSTREAM_CONTROLS: tuple[str, ...] = ("jb-box-mode", "jb-validation-mode", "afr-route-mode")
#: 배치도 탭에 외형을 적는 투입 셀 — layout.STATIONS 키.
SPEC_CELLS: tuple[str, ...] = ("afu", "bfc", "robot")
#: JB-201 축적·인계 런의 가드 반폭 (mm) — 통합 설계도 "JB-201 가드(±1,040)" 실측. 부품표에 행이 없어 여기 적는다.
JB_GUARD_HALF_Y_MM = 1_040


def _scoped_css() -> str:
    """상세도 CSS 중 도판(svg) 규칙과 색 변수만 `.pv-infeed-layout` 아래로 좁혀 가져온다."""
    css = detail.CSS

    def block(pattern: str) -> str:
        m = re.search(pattern, css, re.S)
        if not m:
            raise SystemExit(f"✗ 상세도 CSS 에서 {pattern} 을 못 찾았다")
        return m.group(1)

    out = [
        ".pv-infeed-layout {" + block(r"\n:root \{(.*?)\}") + "}",
        ':root[data-theme="dark"] .pv-infeed-layout {' + block(r'\n:root\[data-theme="dark"\] \{(.*?)\}') + "}",
        '@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .pv-infeed-layout {'
        + block(r'@media \(prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme="light"\]\) \{(.*?)\}') + "} }",
    ]
    for line in css.splitlines():
        if line.startswith("svg"):
            out.append(".pv-infeed-layout " + line)
    out.append(".pv-infeed-layout text { font-family: inherit; }")
    out.append("#pv-panel-layout > :not(.pv-infeed-layout) { display: none; }")
    return "\n".join(out)


def spec_rows(text: str) -> list[tuple[str, str, str, int, int, int, str]]:
    """(품번, 품명, 수량, L, W, H, 구분) — 투입 셀 외형과 투입 무리 부품표."""
    rows: list[tuple[str, str, str, int, int, int, str]] = []
    for key in SPEC_CELLS:
        s = layout.STATIONS[key]
        rows.append((s.sheet, s.name, "1", *s.envelope, "셀 외형 (GA)"))
    for row in detail.catalog(text):
        tag, _group, name, qty, dims, _mat, _proc, _tol, kind, *_ = row
        rows.append((tag, name, qty, int(dims[0]), int(dims[1]), int(dims[2]), kind))
    rows.append(("JB-201", "가드형 축적·인계 컨베이어 (JBR 존 경계를 건넌다)", "1식",
                 layout.ACCUM_RUN_MM, JB_GUARD_HALF_Y_MM * 2, layout.LINE_TRANSFER_MM, "이송면 높이"))
    return rows


def layout_panel(text: str) -> str:
    """배치도 탭 내용 — 투입 구간 평면 배치 + 투입 장비 외형 표."""
    n, esc = detail.n, detail.esc
    afu, robot = detail.zones()["afu"], detail.zones()["robot"]
    x0, x1 = afu.x0_mm, robot.x1_mm
    y0, y1 = min(afu.y0_mm, robot.y0_mm), max(afu.y1_mm, robot.y1_mm)
    h = max(layout.STATIONS[k].height_mm for k in SPEC_CELLS)
    trs = []
    for tag, name, qty, L, W, H, kind in spec_rows(text):
        trs.append(f"<tr><td><code>{esc(tag)}</code></td><td>{esc(name)}</td><td>{esc(qty)}</td>"
                   f"<td>{n(L)}</td><td>{n(W)}</td><td>{n(H)}</td><td>{esc(kind)}</td></tr>")
    return (
        '<div class="pv-infeed-layout">'
        f'<p class="text-small text-muted">투입 구간 전체 — X {n(x0)}…{n(x1)} ({n(x1 - x0)}) × Y {n(y0)}…{n(y1)} ({n(y1 - y0)}) × 최대 높이 {n(h)} mm. '
        '가로 L = X(공정방향) · 세로 W = Y(라인 좌측) · 높이 H = Z(FFL 상향). 하류 셀(JBR·AFR·후단·버퍼·GRM)은 범위 밖이라 싣지 않는다.</p>'
        '<div class="pv-sheet-surface">' + detail.plan_view() + "</div>"
        '<div class="table-responsive"><table class="table table-sm">'
        "<thead><tr><th>품번</th><th>장비</th><th>수량</th><th>가로 L (mm)</th><th>세로 W (mm)</th><th>높이 H (mm)</th><th>구분</th></tr></thead>"
        "<tbody>" + "".join(trs) + "</tbody></table></div>"
        '<p class="text-small text-muted">외형은 통합 설계도 부품표(REV 동일)와 셀 GA 외형 그대로다 · 상세 치수·재질·체결은 상세도와 제작 도면집을 본다.</p>'
        "</div>"
    )


def _once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"✗ {what}: 앵커가 {n}곳 — 1곳이어야 한다\n  {old[:90]}")
    return text.replace(old, new)


def scene_script(takt_s: float, boundary_world_x: float, upstream_world_x: float) -> str:
    """장면을 좁히는 모듈 — 원본 모듈이 `window.__pvScene` 으로 내놓은 장면을 쓴다."""
    return f"""<script type="module">
/* 투입 구간 파생본 — tools/build_infeed_scene.py 가 붙인다. 원본 3D 형상은 그대로 두고
   보이기만 끈다. 경계는 robot 존 끝(JB-201 인계 롤러 하류 끝)이다. */
(function () {{
  const root = document.getElementById('jb-removal-operation');
  const S = (root && root.__pvScene) || window.__pvScene; if (!S) return;
  const BOUNDARY = {boundary_world_x:g};   // world m — 이 하류에 중심이 있는 것은 끈다
  const UPSTREAM = {upstream_world_x:g};   // world m — 여기서 시작해 라인을 지나는 부재(바닥·크레인 주행로·주관)는 남긴다
  const DOWN = new Set(['afr', 'post', 'buffer', 'grm']);
  const v = new S.Vector3();
  function cellOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.cell) return p.userData.cell; }} return null; }}
  function transitOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.transit) return p; }} return null; }}
  const transit = new Set(), hidden = [], seen = new WeakSet();
  function classify(o) {{
    if (!o.isMesh && !o.isSprite && !o.isLine) return;
    if (seen.has(o)) return; seen.add(o);
    const tr = transitOf(o); if (tr) {{ transit.add(tr); return; }}
    const cell = cellOf(o);
    if (cell === 'afu' || cell === 'robot') return;
    if (DOWN.has(cell)) {{ hidden.push(o); return; }}
    o.getWorldPosition(v);
    let minX = v.x, maxX = v.x;
    if (o.geometry) {{
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      const bb = o.geometry.boundingBox, sx = Math.abs(o.matrixWorld.elements[0]) || 1;
      minX = v.x + bb.min.x * sx; maxX = v.x + bb.max.x * sx;
    }}
    // 라인 전장을 지나는 부재 중 바닥면만 남긴다. 60 m 바닥 격자와 크레인 주행로·공압 주관처럼
    // 하류로 25 m 뻗는 건물 측 부재는 투입 구간 밖이라 끈다 — 형상은 그대로다.
    const floor = o.geometry && o.geometry.type === 'PlaneGeometry';
    const spans = minX < UPSTREAM && maxX > BOUNDARY;
    if (spans ? !floor : v.x > BOUNDARY) hidden.push(o);
  }}
  // 원본은 일부 부품을 나중에 만들고(레시피·구조 선택), JBR 단계(40 s 뒤)에 자기 부품의 visible 을
  // 매 프레임 다시 켠다 — 그래서 주기적으로 다시 훑고 매 프레임 끈다.
  let frame = 0;
  function scan() {{ S.scene.updateMatrixWorld(true); S.scene.traverse(classify); }}
  const casing = S.scene.getObjectByName('pvCase');   // 외장 케이싱 — 투입 구간 파생본에서는 뺀다 (기구를 가린다)
  function tick() {{
    if (frame++ % 30 === 0) scan();
    if (casing) casing.visible = false;
    for (const o of hidden) o.visible = false;
    for (const tr of transit) {{ tr.getWorldPosition(v); tr.visible = v.x < BOUNDARY + 1.4; }}
    requestAnimationFrame(tick);
  }}
  tick();
  window.__pvInfeedScene = {{ boundary: BOUNDARY, get hidden() {{ return hidden.length; }}, get transit() {{ return transit.size; }}, taktS: {takt_s:g} }};
}})();
</script>
"""


def build() -> str:
    text = PLANT.read_text(encoding="utf-8")
    takt = campaign.release_takt_s()
    # world x = (plant x − 3D 원점) / 1000 — build_literals.SCENE_ORIGIN_X_MM 과 같은 규약.
    origin = 24_750
    robot_end = next(z.x1_mm for z in layout.build_zones() if z.key == "robot")
    boundary = (robot_end - origin) / 1000.0 + 0.5      # JB-201 축적런 하류 끝(10,580)까지 남긴다
    upstream = (0 - origin) / 1000.0 + 1.0

    t = text
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>태양광 전처리 플랜트 · 투입 구간</title>", "제목")
    t = _once(t, '<span class="viz-badge">124.03 s TRACE</span>',
              f'<span class="viz-badge">{takt:g} s TRACE · 투입 구간</span>', "배지")
    t = _once(t, "<h2 id=\"pv-v22-title\">태양광 패널 전처리 통합 플랜트</h2>",
              "<h2 id=\"pv-v22-title\">태양광 패널 전처리 플랜트 — 투입 구간 (FL-101 → RB-101 → JB-201)</h2>", "표제")
    t = _once(t, '<div class="text-small tabular-nums" id="jb-time">0.00 / 124.03 s</div>',
              f'<div class="text-small tabular-nums" id="jb-time">0.00 / {takt:.2f} s</div>', "시계 표시")
    t = _once(t, 'id="jb-scrub" type="range" min="0" max="124.03" step="0.05" value="0"',
              f'id="jb-scrub" type="range" min="0" max="{takt:g}" step="0.05" value="0"', "스크럽")
    t = _once(t, ",ci=nt+Lr", f",ci={takt:g}", "종단 시각 → 방출 주기")
    # 기본 시점 — 통합라인 대신 투입셀 전체
    t = _once(t, ',xl="line"', ',xl="afu"', "기본 시점")
    t = _once(t, 'xl=i==="reset"?"line":i', 'xl=i==="reset"?"afu":i', "초기화 시점")
    t = _once(t, 'let t=i==="reset"?fp.line:fp[i];', 'let t=i==="reset"?fp.afu:fp[i];', "초기화 카메라")
    # 시점 버튼 — 투입 구간 것만 남기고 첫 버튼을 기본으로
    def keep_button(m: re.Match) -> str:
        return m.group(0) if m.group(1) in KEEP_VIEWS else ""
    button = r'\s*<button class="btn(?: btn-primary)?" data-jb-view="([a-z]+)" type="button">[^<]*</button>'
    t = re.sub(button, keep_button, t)
    left = re.findall(button, t)
    if sorted(left) != sorted(KEEP_VIEWS):
        raise SystemExit(f"✗ 시점 버튼: 남은 것이 {left} — KEEP_VIEWS 와 다르다")
    t = _once(t, '<button class="btn btn-primary" data-jb-view="line"', '<button class="btn" data-jb-view="line"', "통합라인 버튼 강조 해제") if 'data-jb-view="line"' in t else t
    t = _once(t, '<button class="btn" data-jb-view="afu" type="button">투입셀 전체</button>',
              '<button class="btn btn-primary" data-jb-view="afu" type="button">투입셀 전체</button>', "투입셀 버튼 강조")
    # 도면 모듈 선택 — AFU·BFC·RB/PT 만
    for key, label in (("jbr", "JBR-201 · 정션박스 제거"), ("afr", "AFR-101 · 프레임 분리 · SG 연마"),
                       ("post", "CV·GI · 유리 후단"), ("buffer", "GBR-301 · R-A/R-B/HOLD 버퍼")):
        t = _once(t, f'          <option value="{key}">{label}</option>\n', "", f"도면 모듈 {key}")
    # 배치도 탭 — 전체 장비배치도 대신 투입 장비만: 평면 배치 + 외형 표. 원본 SVG·초점·존 표는 CSS 로 숨긴다.
    t = _once(t, '<div id="pv-panel-layout" role="tabpanel" aria-labelledby="pv-tab-layout" hidden>\n',
              '<div id="pv-panel-layout" role="tabpanel" aria-labelledby="pv-tab-layout" hidden>\n' + layout_panel(text) + "\n",
              "배치도 패널")
    t = _once(t, "</head>", f"<style>{_scoped_css()}</style>\n</head>", "배치도 CSS")
    t = _once(t, '<span>상세 장비배치도</span></button>', '<span>투입 장비 배치·외형</span></button>', "배치도 프로그램 버튼")
    t = _once(t, 'aria-controls="pv-panel-layout" aria-selected="false" type="button">전체 장비배치도</button>',
              'aria-controls="pv-panel-layout" aria-selected="false" type="button">투입 장비 배치·외형</button>', "배치도 탭")
    t = _once(t, "layout: '전체 장비 상세 배치도',", "layout: '투입 장비 배치 · 외형 (L × W × H)',", "배치도 제목")
    t = _once(t, '<h3 id="pv-drawing-title">Rev.22 2D·3D 상세 제작도면 및 전체 장비배치</h3>',
              '<h3 id="pv-drawing-title">투입 구간 2D·3D 상세 제작도면 및 투입 장비 배치·외형</h3>', "도면 표제")
    t = _once(t, '<details class="jb-engineering">\n    <summary>AFR-101–GBR-301 비전통합 상세 2D 평면배치도',
              '<details class="jb-engineering" hidden>\n    <summary>AFR-101–GBR-301 비전통합 상세 2D 평면배치도', "하류 평면배치도 접이")
    # 흐름표 — JB-201 까지만 보인다
    t = _once(t, '<h3 id="pv-flow-title">전체 공정 흐름</h3>',
              '<h3 id="pv-flow-title">투입 구간 공정 흐름 <span class="text-small text-muted">JBR-201 부터 범위 밖</span></h3>', "흐름표 제목")
    t = _once(t, "</head>",
              f"<style>.pv-flow-track > li:nth-child(n+{KEEP_FLOW_STEPS + 1}) {{ display: none; }}</style>\n</head>", "흐름표 CSS")
    # 하류 전용 조작 — 결과가 꺼진 셀에서 일어나 화면에 나타나지 않으므로 숨긴다.
    # 패널 구조 레시피(pv-panel-structure)는 반입 등록에서 걸리는 투입 쪽 조작이라 남긴다.
    hidden_controls = ", ".join(f'label[for="{k}"]' for k in DOWNSTREAM_CONTROLS) + ", #afr-buffer-reset"
    for key in DOWNSTREAM_CONTROLS:
        if f'<label class="form-label" for="{key}">' not in t:
            raise SystemExit(f"✗ 하류 조작 {key} 의 라벨이 없다")
    t = _once(t, '<input class="form-check-input" id="pv-case" type="checkbox" checked>',
              '<input class="form-check-input" id="pv-case" type="checkbox">', "케이싱 토글 기본 off")
    hidden_controls += ", label.form-switch:has(#pv-case)"
    # 3D 그림자 — 렌더러 섀도맵을 첫 렌더 전에 끈다 (재질 재컴파일이 필요 없다)
    t = _once(t, "Dt.shadowMap.enabled=!0;", "Dt.shadowMap.enabled=!1;", "3D 그림자")
    t = _once(t, '<button class="btn" id="afr-buffer-reset" type="button">',
              '<button class="btn" id="afr-buffer-reset" type="button" hidden>', "버퍼 초기화 버튼")
    t = _once(t, "</head>", f"<style>{hidden_controls} {{ display: none; }}</style>\n</head>", "하류 조작 CSS")
    # 40 – 48 s 단계 이름 — JBR 자가점검 문구 대신 인계 관점으로
    t = _once(t, '{name:"PANEL_OFFER·DATA_ACK / JBR 자가점검",start:0,end:2},{name:"차광·패널 ID·2극 전압 확인",start:2,end:8}',
              '{name:"JB-201 → JBR-201 인계 — PANEL_OFFER·DATA_ACK · JBR 투입구 진입 (범위 밖)",start:0,end:2},'
              f'{{name:"JBR-201 투입 롤러 이송 — {campaign.JBR_STOPPER_OFFSET_S:g} s 뒤 스토퍼 → 다음 장 방출",start:2,end:{campaign.JBR_STOPPER_OFFSET_S:g}}}',
              "인계 구간 단계 이름")
    # 표식 — 원본의 REV.22 문구 대신 도면 개정과 범위를 적는다
    rev = re.search(r"DRAWING_REVISION = '([^']+)'", t).group(1)
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · 투입 구간 파생본 · ENGINEERING BASE {rev}", "머리글")
    t = _once(t, '<div class="text-small"><code>Rev.22 · 비전 2헤드·듀얼 반전카세트·JBR·AFR 통합 시뮬레이션</code></div>',
              f'<div class="text-small"><code>{rev} · 투입 구간 — 듀얼 리프트·반전카세트·RB-101·PT-101·JB-201 인계</code></div>', "상태 칩")
    # 장면을 좁히는 모듈 — 원본 모듈 뒤에 선다
    t = _once(t, "</body>", scene_script(takt, boundary, upstream) + "</body>", "장면 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- 투입 구간 파생본: tools/build_infeed_scene.py 가 통합 설계도(pv-preprocess-plant.html)에서 만든다. 손으로 고치지 않는다. -->\n",
              "파생본 표식")
    return t


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
