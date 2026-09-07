# -*- coding: utf-8 -*-
"""통합 설계도(3D 영상 콘솔)에서 **JBR-201 정션박스 제거장치만 남긴** 파생본을 만든다.

투입 구간 파생본(`tools/build_infeed_scene.py`)이 FL-101 에서 JB-201 인계까지를
떼어 냈다면, 이것은 그 **바로 다음 셀 하나**를 떼어 낸다. 투입공정이 넘긴 패널을
받아 전선을 자르고 정션박스를 박리·포획·배출하고 후검증까지 하는 장비가 실제로
움직이는 것을 처음부터 끝까지 보는 화면이다.

투입 파생본과 다른 점은 **시계가 0 에서 시작하지 않는다**는 것이다. JBR-201 은
종단 체류 124.03 s 중 `INFEED_S` = 40 s 에 패널을 받아 `JBR_S` = 45 s 를 쓴다.
그래서 이 파생본은 시계를 [40, 85] 구간으로 **창(window)** 을 내고 그 안에서만
재생·반복·스크럽하게 만든다. 시각 자체는 원본 그대로라 통합 설계도와 같은
숫자를 읽는다 — 40 s 가 진입, 85 s 가 AFR-101 인계다.

* **장면** — jbr 셀만 남긴다. JB-201 축적·인계 하드웨어는 `Cn` 아래 있어 셀
  귀속이 jbr 이므로 자동으로 남고, afu·robot·afr·post·buffer·grm 셀과 셀에
  매이지 않는 시설·주행로·주관은 끈다. 형상을 지우지 않고 `visible=false` 로
  끈다 — 원본 3D 는 손대지 않는다.
* **시계** — `ci` 를 85 s 로 자르고 시작·반복·진행률·단계이동을 40 s 창에 묶는다.
* **시점** — 기본 시점을 JBR 전체로, 시점 버튼은 JBR 것(전체·3헤드·포획·검증·
  정렬·구동·공압·안전·리젝트)과 인계부·상부·초기화만 남긴다. 자동추적이 JBR
  단계마다 고르는 시점(`handoff·safetyflow·clamp·overall·service·tool·capture`)이
  전부 그 안에 있다.
* **화면** — 흐름표는 JB-201 → JBR-201 → JB/AFR-301 세 칸, 도면 모듈은 JBR 한 장,
  배치도 초점은 정렬·JBR. 상류 전용 조작(상부 비전 판정·리프트 운전)과 하류 전용
  조작(AFR 레시피·버퍼 초기화)은 숨기고, **JBR 자신의 조작**(정션박스 검출
  시나리오·안전품질 검증 시나리오·패널 구조 레시피)은 남긴다.

원본 파일을 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 하고 아니면 멈춘다 —
원본이 바뀌어 앵커가 사라지면 파생본이 조용히 옛 모습으로 남는 대신 생성이
실패한다. 값(40 s, 45 s)은 캠페인·배치 모델에서 온다.

    PYTHONPATH=src python tools/build_jbr_scene.py

멱등이다. `tests/test_pv_jbr.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign, layout  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-jbr-scene.html"

#: 3D 원점 — build_literals.SCENE_ORIGIN_X_MM 과 같은 규약 (world x = (plant x − 원점)/1000).
SCENE_ORIGIN_X_MM = 24_750

#: 남기는 시점 버튼. 앞의 아홉은 JBR 셀의 근접 시점이고, `handoff` 는 패널이 들어오는
#: 인계부, `top`·`reset` 은 어느 화면에나 있는 일반 시점이다. 자동추적이 JBR 단계마다
#: 고르는 시점이 모두 이 안에 있어야 한다.
KEEP_VIEWS: tuple[str, ...] = ("handoff", "overall", "tool", "capture", "service",
                               "clamp", "drive", "pneumatic", "safety", "safetyflow",
                               "top", "reset")

#: 자동추적이 JBR 11 단계에 배정하는 시점 — 원본 리터럴과 같아야 한다.
AUTO_VIEWS: tuple[str, ...] = ("handoff", "safetyflow", "clamp", "overall", "service",
                               "tool", "tool", "capture", "capture", "service", "safetyflow")

#: 도면 모듈에서 지우는 것 — JBR 만 남긴다.
DROP_STATIONS: tuple[str, ...] = ("afu", "bfc", "robot", "afr", "post", "buffer")

#: 흐름표에서 남기는 칸 — JB-201(6번째) · JBR-201(7번째) · JB/AFR-301(8번째).
FLOW_FIRST, FLOW_LAST = 6, 8

#: 숨기는 상·하류 전용 조작. JBR 자신의 조작(jb-box-mode·jb-validation-mode)과
#: 반입 등록 레시피(pv-panel-structure)는 이 셀에서 실제로 결과가 달라지므로 남긴다.
HIDDEN_CONTROLS: tuple[str, ...] = ("pv-face-in", "pv-lift-mode", "afr-route-mode")

#: 꺼진 셀에 속하는 셀 키.
DOWN_CELLS: tuple[str, ...] = ("afu", "robot", "afr", "post", "buffer", "grm")


def _once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"✗ {what}: 앵커가 {n}곳 — 1곳이어야 한다\n  {old[:90]}")
    return text.replace(old, new)


def _split_select(text: str, select_id: str) -> tuple[str, str, str]:
    """`id` 로 지목한 `<select>` 하나를 앞·본문·뒤로 가른다."""
    opens = [m for m in re.finditer(rf'<select[^>]*id="{select_id}"[^>]*>', text)]
    if len(opens) != 1:
        raise SystemExit(f"✗ select#{select_id}: {len(opens)}곳 — 1곳이어야 한다")
    start = opens[0].end()
    end = text.index("</select>", start)
    return text[:start], text[start:end], text[end:]


def window() -> tuple[float, float]:
    """JBR-201 이 패널을 쥐고 있는 시각 창 (s) — 캠페인 모델에서 온다."""
    start = campaign.INFEED_S
    return start, start + campaign.JBR_S


def zone_world_x() -> tuple[float, float]:
    """jbr 존의 world x 범위 (m)."""
    zone = next(z for z in layout.build_zones() if z.key == "jbr")
    return ((zone.x0_mm - SCENE_ORIGIN_X_MM) / 1000.0,
            (zone.x1_mm - SCENE_ORIGIN_X_MM) / 1000.0)


def scene_script(low: float, high: float, t0: float, t1: float) -> str:
    """장면을 좁히는 모듈 — 원본 모듈이 `window.__pvScene` 으로 내놓은 장면을 쓴다."""
    cells = ", ".join(f"'{c}'" for c in DOWN_CELLS)
    return f"""<script type="module">
/* JBR-201 파생본 — tools/build_jbr_scene.py 가 붙인다. 원본 3D 형상은 그대로 두고
   보이기만 끈다. 남기는 것은 셀 귀속이 'jbr' 인 것 전부다 — JB-201 축적·인계
   하드웨어도 `Cn` 아래에 있어 여기에 든다. */
(function () {{
  const root = document.getElementById('jb-removal-operation');
  const S = (root && root.__pvScene) || window.__pvScene; if (!S) return;
  const LOW = {low:g};    // world m — jbr 존 상류 끝. 인계 롤러가 여기서 2.9 m 더 상류로 뻗는다
  const HIGH = {high:g};  // world m — jbr 존 하류 끝. 공용 인계롤러가 AFR 가드까지 걸친다
  const IN = LOW - 3.2, OUT = HIGH + 1.4;   // 이 밖에 중심이 있는 것은 끈다
  const OFF = new Set([{cells}]);
  const v = new S.Vector3();
  function cellOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.cell) return p.userData.cell; }} return null; }}
  function transitOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.transit) return p; }} return null; }}
  const transit = new Set(), hidden = [], seen = new WeakSet();
  function classify(o) {{
    if (!o.isMesh && !o.isSprite && !o.isLine) return;
    if (seen.has(o)) return; seen.add(o);
    const tr = transitOf(o); if (tr) {{ transit.add(tr); return; }}
    const cell = cellOf(o);
    if (cell === 'jbr') return;
    if (OFF.has(cell)) {{ hidden.push(o); return; }}
    o.getWorldPosition(v);
    let minX = v.x, maxX = v.x;
    if (o.geometry) {{
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      const bb = o.geometry.boundingBox, sx = Math.abs(o.matrixWorld.elements[0]) || 1;
      minX = v.x + bb.min.x * sx; maxX = v.x + bb.max.x * sx;
    }}
    // 라인 전장을 지나는 부재 중 바닥면만 남긴다 — 60 m 바닥 격자는 이 셀 밑에도 있지만
    // 크레인 주행로·공압 주관처럼 양쪽으로 20 m 씩 뻗는 건물 측 부재는 이 셀 밖이다.
    const floor = o.geometry && o.geometry.type === 'PlaneGeometry';
    const spans = minX < IN && maxX > OUT;
    if (spans ? !floor : (v.x < IN || v.x > OUT)) hidden.push(o);
  }}
  // 원본은 일부 부품을 나중에 만들고(레시피·구조 선택) 자기 단계에서 visible 을 매 프레임
  // 다시 켠다 — 그래서 주기적으로 다시 훑고 매 프레임 끈다.
  let frame = 0;
  function scan() {{ S.scene.updateMatrixWorld(true); S.scene.traverse(classify); }}
  function tick() {{
    if (frame++ % 30 === 0) scan();
    for (const o of hidden) o.visible = false;
    for (const tr of transit) {{ tr.getWorldPosition(v); if (v.x < IN || v.x > OUT) tr.visible = false; }}
    requestAnimationFrame(tick);
  }}
  tick();
  window.__pvJbrScene = {{ low: LOW, high: HIGH, from: {t0:g}, to: {t1:g},
    get hidden() {{ return hidden.length; }}, get transit() {{ return transit.size; }} }};
}})();
</script>
"""


def build() -> str:
    text = PLANT.read_text(encoding="utf-8")
    t0, t1 = window()
    low, high = zone_world_x()

    t = text
    # ── 표제·표식 ────────────────────────────────────────────────────────────
    # 이 제목이 그대로 아티팩트 이름이 된다 (tools/build_artifact.py).
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>JBR-201 정션박스 제거장치</title>", "제목")
    t = _once(t, '<span class="viz-badge">124.03 s TRACE</span>',
              f'<span class="viz-badge">{campaign.JBR_S:g} s TRACE · JBR-201</span>', "배지")
    t = _once(t, '<h2 id="pv-v22-title">태양광 패널 전처리 통합 플랜트</h2>',
              '<h2 id="pv-v22-title">JBR-201 정션박스·케이블 제거장치 '
              f'(JB-201 인계 {t0:g} s → AFR-101 인계 {t1:g} s)</h2>', "표제")
    rev = re.search(r"DRAWING_REVISION = '([^']+)'", t).group(1)
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · JBR-201 단독 파생본 · ENGINEERING BASE {rev}", "머리글")
    t = _once(t, '<div class="text-small"><code>Rev.22 · 비전 2헤드·듀얼 반전카세트·JBR·AFR 통합 시뮬레이션</code></div>',
              f'<div class="text-small"><code>{rev} · JBR-201 — 차광·전압확인·순차절단·'
              '3헤드 L칼날 동시박리·진공포획·일괄배출·후검증</code></div>', "상태 칩")

    t = _once(t, '<div class="card jb-detail" id="jb-detail" aria-live="polite">세 벽체 사이의 '
              'BFC-101A/B가 고정 픽업면의 한 장을 상승·반전하고, 650 mm 고상 로봇이 반전 완료품을 '
              '직접 픽업합니다. 적재부·반전기·로봇 사이에는 컨베이어가 없습니다.</div>',
              '<div class="card jb-detail" id="jb-detail" aria-live="polite">JB-201 이 넘긴 패널을 '
              '차광 투입터널에서 받아 2극 전압을 확인하고, 케이블을 A→B 순차 절단한 뒤 검출된 개수만큼의 '
              '헤드가 같은 X 열의 정션박스를 L 칼날로 동시 박리·진공 포획해 한 번에 배출합니다. '
              '형상을 클릭하면 그 부품의 품번과 역할이 여기에 나옵니다.</div>', "기본 설명문")

    # ── 시계: [t0, t1] 창 ────────────────────────────────────────────────────
    t = _once(t, '<div class="text-small tabular-nums" id="jb-time">0.00 / 124.03 s</div>',
              f'<div class="text-small tabular-nums" id="jb-time">{t0:.2f} / {t1:.2f} s</div>', "시계 표시")
    t = _once(t, '<span class="tabular-nums" id="jb-scrub-value">0.0 s</span>',
              f'<span class="tabular-nums" id="jb-scrub-value">{t0:.1f} s</span>', "스크럽 표시")
    t = _once(t, 'id="jb-scrub" type="range" min="0" max="124.03" step="0.05" value="0"',
              f'id="jb-scrub" type="range" min="{t0:g}" max="{t1:g}" step="0.05" value="{t0:g}"', "스크럽")
    t = _once(t, ",ci=nt+Lr", f",ci={t1:g}", "종단 시각 → JBR 인계 시각")
    t = _once(t, ",Ve=0,ai=0", f",Ve={t0:g},ai=0", "시작 시각")
    t = _once(t, "Ve%=ci", f"Ve={t0:g}+(Ve-{t0:g})%(ci-{t0:g})", "반복 구간")
    t = _once(t, "Ve=s?ci:0", f"Ve=s?ci:{t0:g}", "만재 복귀 시각")
    t = _once(t, "let pe=Math.round(i/ci*100)",
              f"let pe=Math.round((i-{t0:g})/(ci-{t0:g})*100)", "진행률")
    t = _once(t, "Ve=i>0?Fs[i-1].start+.02:0",
              f"Ve=Math.max({t0:g},i>0?Fs[i-1].start+.02:{t0:g})", "이전 단계 클램프")
    t = _once(t, "Ve=i<Fs.length-1?Fs[i+1].start+.02:ci",
              "Ve=Math.min(ci,i<Fs.length-1?Fs[i+1].start+.02:ci)", "다음 단계 클램프")
    # 조작을 바꾸면 원본은 시계를 0 으로 되감는다 (검출 시나리오·검증 시나리오·구조
    # 레시피·리프트·AFR 레시피·캠페인 장 선택). 여기서 0 은 창 밖이라 화면이 빈 셀을
    # 비추게 되므로 창의 시작으로 되감는다.
    rewinds = len(re.findall(r"\bVe=0\b", t))
    if rewinds != 6:
        raise SystemExit(f"✗ 시계 되감기: {rewinds}곳 — 6곳이어야 한다")
    t = re.sub(r"\bVe=0\b", f"Ve={t0:g}", t)

    # ── 시점 ────────────────────────────────────────────────────────────────
    t = _once(t, ',xl="line"', ',xl="overall"', "기본 시점")
    t = _once(t, 'xl=i==="reset"?"line":i', 'xl=i==="reset"?"overall":i', "초기화 시점")
    t = _once(t, 'let t=i==="reset"?fp.line:fp[i];', 'let t=i==="reset"?fp.overall:fp[i];', "초기화 카메라")
    # 기본 시점은 통합라인 기준이라 이 셀 하나만 남으면 화면에서 작다 — 셀을 채우도록 당긴다.
    t = _once(t, "overall:{position:new C(3.5,6,-10.2),target:new C(gt+.25,1.15,.55)}",
              "overall:{position:new C(gt+6.4,4.5,-7.1),target:new C(gt+.15,1.35,.05)}",
              "JBR 전체 시점 거리")
    # 콘솔 상단 카메라 바는 통합 화면용 목록이라 이 파생본에는 남는 버튼이 두 개뿐이다.
    t = _once(t, "['line', 'turner', 'tool', 'afr', 'afrbuffer', '#jb-pan-toggle', 'reset']",
              "['overall', 'tool', 'capture', 'service', 'safetyflow', '#jb-pan-toggle', 'reset']",
              "카메라 바 목록")
    button = r'\s*<button class="btn(?: btn-primary)?" data-jb-view="([a-z]+)" type="button">[^<]*</button>'
    t = re.sub(button, lambda m: m.group(0) if m.group(1) in KEEP_VIEWS else "", t)
    left = re.findall(button, t)
    if sorted(left) != sorted(KEEP_VIEWS):
        raise SystemExit(f"✗ 시점 버튼: 남은 것이 {left} — KEEP_VIEWS 와 다르다")
    missing = [v for v in AUTO_VIEWS if v not in KEEP_VIEWS]
    if missing:
        raise SystemExit(f"✗ 자동추적이 고르는 시점 {missing} 이 버튼에 없다")
    t = _once(t, '<button class="btn" data-jb-view="overall" type="button">전체</button>',
              '<button class="btn btn-primary" data-jb-view="overall" type="button">JBR-201 전체</button>',
              "JBR 전체 버튼 강조")

    # ── 도면·배치도 ─────────────────────────────────────────────────────────
    # `afr`·`post` 같은 값은 배치도 초점 select 에도 있다 — 도면 모듈 select 안에서만 지운다.
    head, select, tail = _split_select(t, "pv-drawing-station")
    for key in DROP_STATIONS:
        pattern = re.compile(rf'[ ]*<option value="{key}"[^>]*>[^<]*</option>\n')
        found = pattern.findall(select)
        if len(found) != 1:
            raise SystemExit(f"✗ 도면 모듈 {key}: 앵커가 {len(found)}곳 — 1곳이어야 한다")
        select = pattern.sub("", select)
    t = head + select + tail
    t = _once(t, '<option value="jbr">JBR-201 · 정션박스 제거</option>',
              '<option value="jbr" selected>JBR-201 · 정션박스 제거</option>', "도면 모듈 기본값")
    t = _once(t, "station: 'afu', explode:", "station: 'jbr', explode:", "도면 기본 스테이션")
    t = _once(t, "focus: 'all', clearance: true", "focus: 'jbr', clearance: true", "배치도 초점")
    t = _once(t, '<option value="all" selected>전체 배치</option>',
              '<option value="all">전체 배치</option>', "배치 초점 기본값 해제")
    t = _once(t, '<option value="jbr">정렬·JBR</option>',
              '<option value="jbr" selected>정렬·JBR</option>', "배치 초점 기본값")

    # ── 흐름표 ──────────────────────────────────────────────────────────────
    t = _once(t, '<h3 id="pv-flow-title">전체 공정 흐름</h3>',
              '<h3 id="pv-flow-title">JBR-201 공정 흐름 '
              '<span class="text-small text-muted">투입부와 AFR-101 은 범위 밖</span></h3>', "흐름표 제목")
    t = _once(t, "</head>",
              f"<style>.pv-flow-track > li:nth-child(-n+{FLOW_FIRST - 1}),"
              f" .pv-flow-track > li:nth-child(n+{FLOW_LAST + 1}) {{ display: none; }}</style>\n</head>",
              "흐름표 CSS")

    # ── 상·하류 전용 조작 ───────────────────────────────────────────────────
    for key in HIDDEN_CONTROLS:
        if f'<label class="form-label" for="{key}">' not in t:
            raise SystemExit(f"✗ 범위 밖 조작 {key} 의 라벨이 없다")
    hidden = ", ".join(f'label[for="{k}"]' for k in HIDDEN_CONTROLS) + ", #afr-buffer-reset"
    t = _once(t, '<button class="btn" id="afr-buffer-reset" type="button">',
              '<button class="btn" id="afr-buffer-reset" type="button" hidden>', "버퍼 초기화 버튼")
    t = _once(t, "</head>", f"<style>{hidden} {{ display: none; }}</style>\n</head>", "범위 밖 조작 CSS")

    # ── 장면을 좁히는 모듈 — 원본 모듈 뒤에 선다 ────────────────────────────
    t = _once(t, "</body>", scene_script(low, high, t0, t1) + "</body>", "장면 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- JBR-201 파생본: tools/build_jbr_scene.py 가 통합 "
              "설계도(pv-preprocess-plant.html)에서 만든다. 손으로 고치지 않는다. -->\n",
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
