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
* **화면** — 흐름표는 JB-201 까지, 도면 모듈 선택은 AFU·BFC·RB/PT 세 장, 배치도
  초점은 상류.

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
    // 라인 전장을 지나는 부재(바닥·바닥 격자)는 남긴다. 크레인 주행로·공압 주관처럼 하류로 25 m 뻗는
    // 건물 측 부재는 투입 구간 밖이라 끈다 — 형상은 그대로다.
    const floor = o.type === 'GridHelper' || (o.geometry && o.geometry.type === 'PlaneGeometry');
    const spans = minX < UPSTREAM && maxX > BOUNDARY;
    if (spans ? !floor : v.x > BOUNDARY) hidden.push(o);
  }}
  // 원본은 일부 부품을 나중에 만들고(레시피·구조 선택), JBR 단계(40 s 뒤)에 자기 부품의 visible 을
  // 매 프레임 다시 켠다 — 그래서 주기적으로 다시 훑고 매 프레임 끈다.
  let frame = 0;
  function scan() {{ S.scene.updateMatrixWorld(true); S.scene.traverse(classify); }}
  function tick() {{
    if (frame++ % 30 === 0) scan();
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
    # 배치도 초점 — 상류
    t = _once(t, "focus: 'all', clearance: true", "focus: 'upstream', clearance: true", "배치도 초점")
    # 흐름표 — JB-201 까지만 보인다
    t = _once(t, '<h3 id="pv-flow-title">전체 공정 흐름</h3>',
              '<h3 id="pv-flow-title">투입 구간 공정 흐름 <span class="text-small text-muted">JBR-201 부터 범위 밖</span></h3>', "흐름표 제목")
    t = _once(t, "</head>",
              f"<style>.pv-flow-track > li:nth-child(n+{KEEP_FLOW_STEPS + 1}) {{ display: none; }}</style>\n</head>", "흐름표 CSS")
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
