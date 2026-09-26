# -*- coding: utf-8 -*-
"""통합 설계도(3D 영상 콘솔)에서 **AFR-101 프레임 제거장치만 남긴** 파생본을 만든다.

투입 구간 파생본(`tools/build_infeed_scene.py`)이 라인 앞머리를, JBR 파생본
(`tools/build_jbr_scene.py`)이 그 다음 셀을 떼어 냈다면, 이것은 **그 다음 셀 하나**를
떼어 낸다. JBR-201 이 정션박스와 케이블을 뜯어 넘긴 패널을 받아, 정반 안의 실린더가
쇠막대로 단변 알루미늄을 밀어내고, 장축 캐리지 4 대가 홈 롤러로 장변을 바깥으로 당겨
LM 을 타고 뽑아낸 뒤, 톱니 컨베이어가 홈으로 올라와 무프레임 유리를 받아 나가는
것을 처음부터 끝까지 보는 화면이다.

발주처 요청 셋을 이 파생본에서 같이 반영한다 — **그림자·외장 케이싱·천장크레인을 뺀다.**
셋 다 AFR-101 의 부재가 아니라 화면을 덮는 것들이다. 바닥 그림자는 기구 밑을 어둡게
덮고, 외장 케이싱은 껍질로 기구를 가리며, CRN-901 천장크레인은 이 셀 위 10,750 을
가로지르는 **건물 측** 부재다 (설치·정비 인양용이라 운전 중에는 급전조차 차단된다).

* **장면** — afr 셀만 남긴다. JB/AFR-301 직결 인계롤러와 데이터 게이트, 그리고
  REV.50 에서 AFR 반출롤러 위로 올라온 SG-301 연마 헤드는 전부 `ot` 아래에 있어
  셀 귀속이 afr 이므로 자동으로 남는다. afu·robot·jbr·post·buffer·grm 셀과 셀에
  매이지 않는 시설·주행로·주관은 끈다. 형상을 지우지 않고 `visible=false` 로
  끈다 — 원본 3D 는 손대지 않는다.
* **시계** — AFR-101 은 종단 체류 124.03 s 중 `INFEED_S + JBR_S` = 85 s 에 패널을
  받아 `AFR_S` = 39.03 s 를 쓴다. 그래서 시계를 [85, 124.03] 구간으로 **창**을 내고
  그 안에서만 재생·반복·스크럽하게 만든다. 창의 끝은 원본 필름의 끝이라 `ci` 는
  건드리지 않는다 — 이 셀이 패널을 놓는 순간이 곧 영상의 끝이다.
* **시점** — 기본 시점을 AFR 전체로, 시점 버튼은 AFR 것(전체·단축 유압·장축 LM
  인발)과 상부·초기화만 남긴다. 자동추적이 AFR 6 단계에 배정하는 시점 중 마지막
  하나만 후단 셀(`afrpost`)을 보고 있어 이 셀 시점으로 되돌린다.
* **화면** — 흐름표는 JB/AFR-301 → AFR-101 두 칸, 도면 모듈은 AFR 한 장.
  상류 전용 조작(상부 비전 판정·리프트 운전·정션박스 검출·JBR 검증)과 하류 전용
  조작(AFR 레시피·버퍼 초기화)은 숨기고, **이 셀에서 결과가 갈리는 조작**
  (패널 구조 레시피 — `frameless` 는 이 셀의 인발을 통째로 생략시킨다)은 남긴다.
* **배치도** — 원본의 초점(`focusBox`)은 **뷰박스만** 옮기므로 존 밖 장비가 SVG 에
  그대로 남아 축소하면 플랜트 50 m 가 다 나온다. `renderLayout` 안에서만 존을
  afr 하나로 가려 **이 셀 장비만** 그리고, 전체 X·Y 치수도 셀 값으로 바꾸며,
  패널 맨 위에 **장비 전체 스펙(가로·세로·높이)** 을 세운다. 값은 배치 모델의 존
  폭에서 내고 GA 시트의 `envelope` 과 맞는지 확인한다 — 갈라지면 멈춘다.
* **나머지 탭** — 셀 단위 자료(지지·장착의 셀 선택, 도면 목록)는 이 셀로 좁히고,
  합계가 플랜트 값이라 행만 걸러 내면 표와 어긋나는 계통 자료(전기 인입·스마트·
  안전·가동검수와 「설계·PLC·검증」의 서보 38축·소음·열수지)는 숨긴다.

원본 파일을 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 하고 아니면 멈춘다 —
원본이 바뀌어 앵커가 사라지면 파생본이 조용히 옛 모습으로 남는 대신 생성이
실패한다. 값(85 s, 39.03 s, 셀 외형)은 캠페인·배치 모델에서 온다.

    PYTHONPATH=src python tools/build_afr_scene.py

멱등이다. `tests/test_pv_afr.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign, layout  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-afr-scene.html"

#: 3D 원점 — build_literals.SCENE_ORIGIN_X_MM 과 같은 규약 (world x = (plant x − 원점)/1000).
SCENE_ORIGIN_X_MM = 24_750

#: 이 파생본이 다루는 셀.
CELL = "afr"

#: 남기는 시점 버튼. 앞의 셋은 AFR 셀의 시점이고, `top`·`reset` 은 어느 화면에나
#: 있는 일반 시점이다. 자동추적이 AFR 단계마다 고르는 시점이 모두 이 안에 있어야 한다.
KEEP_VIEWS: tuple[str, ...] = ("afr", "afrshort", "afrlong", "top", "reset")

#: 자동추적이 AFR 6 단계에 배정하는 시점 — 원본은 마지막 단계에서 후단 검사
#: (`afrpost`) 를 보는데, 그 셀은 이 파생본에서 꺼져 있어 빈 자리를 비춘다.
#: 마지막 단계의 AFR 쪽 일(정반 상승·톱니 컨베이어 40 mm 상승 반출)을 보도록 되돌린다.
AUTO_VIEWS_OLD = '["afr","afr","afrshort","afrshort","afrlong","afrpost"]'
AUTO_VIEWS_NEW = '["afr","afr","afrshort","afrshort","afrlong","afr"]'
AUTO_VIEWS: tuple[str, ...] = ("afr", "afr", "afrshort", "afrshort", "afrlong", "afr")

#: 도면 모듈에서 지우는 것 — AFR 만 남긴다.
DROP_STATIONS: tuple[str, ...] = ("afu", "bfc", "robot", "jbr", "post", "buffer")

#: 흐름표에서 남기는 칸 (1부터 센다) — JB/AFR-301(8번째) · AFR-101(9번째).
#: 둘 다 이 셀의 하드웨어다. 데이터 인계 게이트는 AFR 존 시작면에 서 있다.
FLOW_FIRST, FLOW_LAST = 8, 9

#: 도면 팝업에서 숨기는 탭 — 합계가 플랜트 값이라 이 셀로 좁힐 수 없는 계통 자료다.
PLANT_TABS: tuple[str, ...] = ("electrical", "smart", "safety", "ops")

#: 「설계·PLC·검증」 안의 플랜트 계통 절 — 서보 38축·플랜트 소음·플랜트 열수지다.
PLANT_SECTIONS: tuple[str, ...] = ("jb-servo-axes", "jb-noise-vibration", "jb-thermal")

#: 숨기는 상·하류 전용 조작. 상부 비전 판정·리프트 운전은 투입셀 것이고, 정션박스
#: 검출 시나리오와 안전·품질 검증 시나리오는 JBR 것이다 (리젝트가 나면 패널이 아예
#: 이 셀에 오지 않아 창 안이 빈다). AFR 레시피 시나리오는 이름과 달리 **버퍼**
#: (GBR-301 R-A/R-B/HOLD 캐리지) 조작이라 하류다. 배치 초점도 여기 든다 —
#: 배치도에 이 셀만 그리므로 다른 초점은 빈 자리를 확대할 뿐이다. 요소는 남는다.
#: 반입 등록 레시피(`pv-panel-structure`)는 남긴다 — `frameless` 가 이 셀의 인발을
#: 통째로 생략시키므로 여기서 결과가 갈리는 조작이다.
HIDDEN_CONTROLS: tuple[str, ...] = ("pv-face-in", "pv-lift-mode", "jb-box-mode",
                                    "jb-validation-mode", "afr-route-mode",
                                    "pv-layout-focus")

#: 꺼진 셀에 속하는 셀 키.
OFF_CELLS: tuple[str, ...] = ("afu", "robot", "jbr", "post", "buffer", "grm")

#: 셀 밖으로 뻗는 이 셀 하드웨어의 상류 여유 (m) — JB/AFR-301 직결 인계롤러 런이
#: 존 시작에서 1,315 상류까지 간다. 그보다 넉넉히 잡아 인계 명판까지 담는다.
UPSTREAM_MARGIN_M = 1.6
#: 하류 여유 (m) — 이 셀 하드웨어는 존 안에서 끝난다. 경계 판정 여유만 준다.
DOWNSTREAM_MARGIN_M = 0.4


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
    """AFR-101 이 패널을 쥐고 있는 시각 창 (s) — 캠페인 모델에서 온다."""
    start = campaign.INFEED_S + campaign.JBR_S
    return start, start + campaign.AFR_S


def zone_world_x() -> tuple[float, float]:
    """afr 존의 world x 범위 (m)."""
    zone = next(z for z in layout.build_zones() if z.key == CELL)
    return ((zone.x0_mm - SCENE_ORIGIN_X_MM) / 1000.0,
            (zone.x1_mm - SCENE_ORIGIN_X_MM) / 1000.0)


def cell_envelope(plant: str) -> tuple[int, int, int]:
    """AFR-101 셀의 가로 × 세로 × 높이 (mm).

    배치 모델의 존 폭에서 내고, 통합 설계도 GA 시트가 적어 둔 `envelope` 과
    맞는지 확인한다. 두 곳이 갈라지면 어느 쪽이 맞는지 화면이 알 수 없으므로
    여기서 멈춘다 — 조용히 한쪽을 고르지 않는다.
    """
    zone = next(z for z in layout.build_zones() if z.key == CELL)
    got = (zone.x1_mm - zone.x0_mm, zone.y1_mm - zone.y0_mm, zone.height_mm)
    m = re.search(rf"{CELL}: \{{.*?envelope: \[(\d+), (\d+), (\d+)\]", plant, re.S)
    if not m:
        raise SystemExit(f"✗ GA 시트에서 {CELL} 의 envelope 을 못 읽었다")
    want = tuple(int(v) for v in m.groups())
    if tuple(int(v) for v in got) != want:
        raise SystemExit(f"✗ 셀 외형이 갈렸다 — 배치 모델 {got} vs GA 시트 {want}")
    return want


def spec_block(plant: str) -> str:
    """배치도 패널 맨 위에 세우는 「장비 전체 스펙」 — 가로·세로·높이."""
    L, W, H = cell_envelope(plant)
    zone = next(z for z in layout.build_zones() if z.key == CELL)
    rows = (
        ("가로 (X · 공정방향)", L, f"존 {zone.x0_mm:,} → {zone.x1_mm:,} mm"),
        ("세로 (Y · 진행방향 좌측)", W, f"존 {zone.y0_mm:,} → {zone.y1_mm:,} mm"),
        ("높이 (Z · FFL 상향)", H,
         "이송면 H=950 · 클램프 H=1,280 · SG-301 H=2,130 · 가드 H=2,380"),
    )
    body = "".join(
        f"<tr><td>{label}</td><td>{value:,} mm</td><td>{note}</td></tr>"
        for label, value, note in rows)
    return (
        '      <div class="pv-afr-spec">\n'
        '        <h4 class="text-small" style="margin:0 0 6px">장비 전체 스펙 '
        f'<span class="viz-badge">{L:,} × {W:,} × {H:,} mm</span></h4>\n'
        '        <div class="table-responsive"><table class="table table-sm">\n'
        "          <thead><tr><th>항목</th><th>값</th><th>기준</th></tr></thead>\n"
        f"          <tbody>{body}</tbody>\n"
        "        </table></div>\n"
        '        <p class="text-small text-muted">셀 외형 포락선이다. 아래 배치도는 '
        "이 파생본에서 <b>AFR-101 셀 장비만</b> 그린다 — 상·하류 존은 통합 설계도에 "
        "그대로 있고 여기서만 뺐다.</p>\n"
        "      </div>\n")


def scene_script(low: float, high: float, t0: float, t1: float) -> str:
    """장면을 좁히는 모듈 — 원본 모듈이 `window.__pvScene` 으로 내놓은 장면을 쓴다."""
    cells = ", ".join(f"'{c}'" for c in OFF_CELLS)
    return f"""<script type="module">
/* AFR-101 파생본 — tools/build_afr_scene.py 가 붙인다. 원본 3D 형상은 그대로 두고
   보이기만 끈다. 남기는 것은 셀 귀속이 'afr' 인 것 전부다 — JB/AFR-301 직결
   인계롤러·데이터 게이트와 반출롤러 위 SG-301 도 `ot` 아래에 있어 여기에 든다.
   발주 요청으로 외장 케이싱(pvCase)과 CRN-901 천장크레인(pvCrn)은 이름으로 찾아
   끈다 — 둘 다 셀에 매이지 않는 `pvSpans` 묶음이라 위치 판정만으로는 셀 위를
   지나는 조각이 남는다. 그림자는 렌더러 섀도맵에서 이미 껐다. */
(function () {{
  const root = document.getElementById('jb-removal-operation');
  const S = (root && root.__pvScene) || window.__pvScene; if (!S) return;
  const LOW = {low:g};    // world m — afr 존 상류 끝. 직결 인계롤러가 여기서 1.315 m 더 상류로 뻗는다
  const HIGH = {high:g};  // world m — afr 존 하류 끝. 반출롤러가 여기서 CV-102 로 이어진다
  const IN = LOW - {UPSTREAM_MARGIN_M:g}, OUT = HIGH + {DOWNSTREAM_MARGIN_M:g};   // 이 밖에 중심이 있는 것은 끈다
  const OFF = new Set([{cells}]);
  const v = new S.Vector3();
  function cellOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.cell) return p.userData.cell; }} return null; }}
  function transitOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.transit) return p; }} return null; }}
  /* 껍질과 크레인은 묶음째 끈다 — 위치로 거르면 이 셀 위에 걸친 조각이 남는다. */
  const shells = ['pvCase', 'pvCrn'].map(function (n) {{ return S.scene.getObjectByName(n); }})
    .filter(Boolean);
  const transit = new Set(), hidden = [], seen = new WeakSet();
  function classify(o) {{
    if (!o.isMesh && !o.isSprite && !o.isLine) return;
    if (seen.has(o)) return; seen.add(o);
    const tr = transitOf(o); if (tr) {{ transit.add(tr); return; }}
    const cell = cellOf(o);
    if (cell === '{CELL}') return;
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
    for (const s of shells) s.visible = false;
    for (const tr of transit) {{ tr.getWorldPosition(v); if (v.x < IN || v.x > OUT) tr.visible = false; }}
    requestAnimationFrame(tick);
  }}
  tick();
  window.__pvAfrScene = {{ low: LOW, high: HIGH, from: {t0:g}, to: {t1:g},
    get hidden() {{ return hidden.length; }}, get transit() {{ return transit.size; }},
    get shells() {{ return shells.length; }} }};
}})();
</script>
"""


def build() -> str:
    text = PLANT.read_text(encoding="utf-8")
    t0, t1 = window()
    low, high = zone_world_x()
    L, W, H = cell_envelope(text)

    t = text
    # ── 표제·표식 ────────────────────────────────────────────────────────────
    # 이 제목이 그대로 아티팩트 이름이 된다 (tools/build_artifact.py).
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>AFR-101 알루미늄 프레임 제거장치</title>\n"
              '<meta name="description" content="폐 태양광 패널 전처리 라인의 AFR-101 '
              '알루미늄 프레임 분리 셀만 남긴 3D 운전 콘솔 — 12구역 지지·정반 하강·4점 '
              '클램프부터 정반 내장 실린더의 쇠막대 단축 밀어내기, 장축 홈 롤러 인발과 '
              'LM 1,300 mm 주행, 톱니 컨베이어 반출까지 6 단계를 플랜트 '
              f'{t0:g}–{t1:g} s 창에서 반복 재생한다. 그림자·외장 케이싱·천장크레인은 뺐다.">',
              "제목")
    t = _once(t, f'<span class="viz-badge">{campaign.total_dwell_s():g} s TRACE</span>',
              f'<span class="viz-badge">{campaign.AFR_S:g} s TRACE · AFR-101</span>', "배지")
    t = _once(t, '<h2 id="pv-v22-title">태양광 패널 전처리 통합 플랜트</h2>',
              '<h2 id="pv-v22-title">AFR-101 알루미늄 프레임 제거장치 '
              f'(JB/AFR-301 인계 {t0:g} s → 무프레임 반출 {t1:g} s)</h2>', "표제")
    rev = re.search(r"DRAWING_REVISION = '([^']+)'", t).group(1)
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · AFR-101 단독 파생본 · ENGINEERING BASE {rev}", "머리글")
    t = _once(t, '<div class="text-small"><code>Rev.22 · 비전 2헤드·듀얼 반전카세트·JBR·AFR 통합 시뮬레이션</code></div>',
              f'<div class="text-small"><code>{rev} · AFR-101 — 12구역 지지·4점 클램프·'
              '쇠막대 단축 밀어내기·장축 홈 롤러 인발·톱니 컨베이어 반출</code></div>', "상태 칩")

    t = _once(t, '<div class="card jb-detail" id="jb-detail" aria-live="polite">세 벽체 사이의 '
              'BFC-101A/B가 고정 픽업면의 한 장을 상승·반전하고, 650 mm 고상 로봇이 반전 완료품을 '
              '직접 픽업합니다. 적재부·반전기·로봇 사이에는 컨베이어가 없습니다.</div>',
              '<div class="card jb-detail" id="jb-detail" aria-live="polite">JBR-201 이 정션박스와 '
              '케이블을 제거해 넘긴 패널을 12구역 지지정반이 받고, 위에서 내려온 정반 두 장이 '
              '4점 클램프로 물린 뒤 정반 <b>안</b>의 실린더가 쇠막대로 단변 알루미늄을 120 mm '
              '밀어냅니다. 이어 장축 캐리지 4 대의 홈 롤러가 장변 압출재 홈에 들어가 바깥으로 '
              '당기며 LM 을 1,300 mm 타고, 프레임이 다 빠지면 톱니 컨베이어가 정반의 긴 홈으로 '
              '올라와 무프레임 유리를 받아 나갑니다. 형상을 클릭하면 그 부품의 품번과 역할이 '
              '여기에 나옵니다.</div>', "기본 설명문")

    # ── 시계: [t0, t1] 창 ────────────────────────────────────────────────────
    # 창의 **끝**은 원본 필름의 끝(`ci=nt+Lr`)이다 — 이 셀이 패널을 놓는 순간이 곧
    # 영상의 끝이라 자를 것이 없다. 시작만 셀 진입 시각으로 올린다.
    t = _once(t, f'<div class="text-small tabular-nums" id="jb-time">0.00 / {campaign.total_dwell_s():g} s</div>',
              f'<div class="text-small tabular-nums" id="jb-time">{t0:.2f} / {t1:.2f} s</div>', "시계 표시")
    t = _once(t, '<span class="tabular-nums" id="jb-scrub-value">0.0 s</span>',
              f'<span class="tabular-nums" id="jb-scrub-value">{t0:.1f} s</span>', "스크럽 표시")
    t = _once(t, f'id="jb-scrub" type="range" min="0" max="{campaign.total_dwell_s():g}" step="0.05" value="0"',
              f'id="jb-scrub" type="range" min="{t0:g}" max="{t1:g}" step="0.05" value="{t0:g}"', "스크럽")
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
    t = _once(t, ',xl="line"', ',xl="afr"', "기본 시점")
    t = _once(t, 'xl=i==="reset"?"line":i', 'xl=i==="reset"?"afr":i', "초기화 시점")
    t = _once(t, 'let t=i==="reset"?fp.line:fp[i];', 'let t=i==="reset"?fp.afr:fp[i];', "초기화 카메라")
    # 원본의 AFR 전체 시점은 AFR–버퍼까지 함께 보는 거리라 셀 하나만 남으면 화면에서
    # 작다. 셀 5,900 × 5,600 을 채우도록 당기고, 보는 **쪽**도 바꾼다 — 원본은 하류
    # (−z, +x) 에서 보는데 그쪽에는 REV.50 에서 반출롤러 위로 올라온 SG-301 몸체
    # 2,200 이 서 있어 프레임 제거기구를 가린다. 상류 앞쪽(+z, −x)에서 보면 인계롤러 →
    # 12구역 지지베드 → 정반·클램프 포탈 → 장축 캐리지가 한 화면에 차례로 선다.
    t = _once(t, "afr:{position:new C(qt+5.8,5.8,-9.8),target:new C(qt,1.15,0)}",
              "afr:{position:new C(qt-3.85,3.35,5.15),target:new C(qt+.3,1.15,0)}",
              "AFR 전체 시점 거리")
    t = _once(t, AUTO_VIEWS_OLD, AUTO_VIEWS_NEW, "자동추적 마지막 단계 시점")
    # 콘솔 상단 카메라 바는 통합 화면용 목록이라 이 파생본에는 남는 버튼이 둘뿐이다.
    t = _once(t, "['line', 'turner', 'tool', 'afr', 'afrbuffer', '#jb-pan-toggle', 'reset']",
              "['afr', 'afrshort', 'afrlong', 'top', '#jb-pan-toggle', 'reset']",
              "카메라 바 목록")
    button = r'\s*<button class="btn(?: btn-primary)?" data-jb-view="([a-z]+)" type="button">[^<]*</button>'
    t = re.sub(button, lambda m: m.group(0) if m.group(1) in KEEP_VIEWS else "", t)
    left = re.findall(button, t)
    if sorted(left) != sorted(KEEP_VIEWS):
        raise SystemExit(f"✗ 시점 버튼: 남은 것이 {left} — KEEP_VIEWS 와 다르다")
    missing = [v for v in AUTO_VIEWS if v not in KEEP_VIEWS]
    if missing:
        raise SystemExit(f"✗ 자동추적이 고르는 시점 {missing} 이 버튼에 없다")
    t = _once(t, '<button class="btn" data-jb-view="afr" type="button">AFR-101 전체</button>',
              '<button class="btn btn-primary" data-jb-view="afr" type="button">AFR-101 전체</button>',
              "AFR 전체 버튼 강조")

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
    t = _once(t, '<option value="afr">AFR-101 · 프레임 분리 · SG 연마</option>',
              '<option value="afr" selected>AFR-101 · 프레임 분리 · SG 연마</option>',
              "도면 모듈 기본값")
    t = _once(t, "station: 'afu', explode:", "station: 'afr', explode:", "도면 기본 스테이션")
    t = _once(t, "focus: 'all', clearance: true", "focus: 'afr', clearance: true", "배치도 초점")
    t = _once(t, '<option value="all" selected>전체 배치</option>',
              '<option value="all">전체 배치</option>', "배치 초점 기본값 해제")
    t = _once(t, '<option value="afr">AFR·후단·버퍼</option>',
              '<option value="afr" selected>AFR·후단·버퍼</option>', "배치 초점 기본값")

    # ── 배치도를 이 셀 것으로 좁힌다 ────────────────────────────────────────
    # 초점(`focusBox`)은 **뷰박스만** 옮긴다 — 존 밖 장비도 SVG 에 그대로 그려져
    # 있어서 축소하면 플랜트 50 m 가 다 나온다. 이 파생본은 셀 하나를 보는 화면이라
    # 그리는 단계에서 존을 거른다. `renderLayout` 안에서만 `layoutZones` 를 가리므로
    # 바깥의 `zoneByKey`(초점 계산)는 여전히 모든 존을 본다.
    t = _once(t, "function renderLayout() {\n"
                 "    var ox = LAYOUT_ORIGIN_X, oy = LAYOUT_ORIGIN_Y, "
                 "scale = LAYOUT_SCALE, floorY = LAYOUT_FLOOR_Y;",
              "function renderLayout() {\n"
              "    /* AFR-101 파생본: 이 함수 안에서만 존을 셀 하나로 가린다. */\n"
              "    var layoutZones = window.__pvLayoutZones\n"
              "      || (window.__pvLayoutZones = pvAllZones.filter(function (zone) "
              "{ return zone[0] === 'afr'; }));\n"
              "    var ox = LAYOUT_ORIGIN_X, oy = LAYOUT_ORIGIN_Y, "
              "scale = LAYOUT_SCALE, floorY = LAYOUT_FLOOR_Y;",
              "배치도 존 거르기")
    # 가린 이름 너머의 원본 목록을 붙잡아 둔다 — 위 filter 가 읽는 것이 이것이다.
    t = _once(t, "  // [키, 표기, X0, X1, Y0, Y1, 높이, 주기]\n  var layoutZones = ",
              "  // [키, 표기, X0, X1, Y0, Y1, 높이, 주기]\n  var pvAllZones, layoutZones = pvAllZones = ",
              "원본 존 목록 별칭")
    # 안전구역은 존 묶음 셋을 도는데, 거르고 나면 나머지 둘은 빈 묶음이라 높이가
    # 음수인 사각형이 나온다. 이 셀 하나만 돈다.
    t = _once(t, "[['afu', 'robot'], ['jbr', 'afr'], ['post', 'buffer']].forEach(function (pair) {",
              "[['afr', 'afr']].forEach(function (pair) {", "안전구역 묶음")
    # 도면 이름·설명도 셀 것으로.
    t = _once(t, "out.push('<title>태양광 패널 전처리 플랜트 전체 상세 장비배치도</title><desc>듀얼 "
                 "리프트부터 반전 로봇 정션박스 제거 프레임 분리 검사 연마 레시피 버퍼까지 ' +",
              "out.push('<title>AFR-101 알루미늄 프레임 제거셀 장비배치도</title><desc>이 셀 하나의 "
              "평면과 종단 배치 — 상하류 존은 통합 설계도에 있다. 설비 전체는 ' +",
              "배치도 제목")
    t = _once(t, "'PV-PLANT-GA-1001 · 전체 플랜트 상세 배치 · REV.22-P01'",
              "'PV-AFR-101-GA-4101 · AFR-101 셀 배치 · ' + DRAWING_REVISION",
              "배치도 시트번호")
    # 탭·버튼 이름과 모듈 제목.
    t = _once(t, '<button class="nav-link" id="pv-tab-layout" role="tab" '
                 'aria-controls="pv-panel-layout" aria-selected="false" type="button">'
                 "전체 장비배치도</button>",
              '<button class="nav-link" id="pv-tab-layout" role="tab" '
              'aria-controls="pv-panel-layout" aria-selected="false" type="button">'
              "장비 스펙·셀 배치</button>", "배치도 탭 이름")
    t = _once(t, "<span>상세 장비배치도</span>", "<span>장비 스펙·셀 배치</span>",
              "배치도 버튼 이름")
    t = _once(t, '<h3 id="pv-drawing-title">Rev.22 2D·3D 상세 제작도면 및 전체 장비배치</h3>',
              '<h3 id="pv-drawing-title">AFR-101 2D·3D 제작도면 및 장비 스펙</h3>',
              "도면 모듈 제목")
    # 전체 치수는 이제 뜻이 없다 — 셀 하나만 그리는데 옆에 「전체 X = 50,075」가
    # 서 있으면 그 폭이 이 장비의 것으로 읽힌다. 셋 다 셀 값으로 바꾼다.
    t = _once(t, "out.push(text(40, 72, 'X=공정방향 · Y=진행방향 좌측 · Z=FFL 상향 · 영구설비 ' +\n"
                 "      [PLANT_X, PLANT_Y, PLANT_Z].map(n).join(' × ') + ' mm', 'pv-layout-small'));",
              "out.push(text(40, 72, 'X=공정방향 · Y=진행방향 좌측 · Z=FFL 상향 · 셀 외형 ' +\n"
              "      [layoutZones[0][3] - layoutZones[0][2], layoutZones[0][5] - layoutZones[0][4],\n"
              "       layoutZones[0][6]].map(n).join(' × ') + ' mm', 'pv-layout-small'));",
              "배치도 기준 문구")
    t = _once(t, "out.push(dimension(mapX(0), 100, mapX(PLANT_X), 100, "
                 "'전체 X = ' + n(PLANT_X) + ' mm', false, 'layout'));",
              "out.push(dimension(mapX(layoutZones[0][2]), 100, mapX(layoutZones[0][3]), 100,\n"
              "      '셀 X = ' + n(layoutZones[0][3] - layoutZones[0][2]) + ' mm', false, 'layout'));",
              "배치도 X 전체치수")
    t = _once(t, "out.push(dimension(mapX(PLANT_X) + 28, mapY(0), mapX(PLANT_X) + 28, mapY(PLANT_Y), "
                 "'전체 Y = ' + n(PLANT_Y) + ' mm', true, 'layout'));",
              # 오른쪽에 세우면 존 주기 글자를 밟는다 — 비어 있는 왼쪽에 세운다.
              "out.push(dimension(mapX(layoutZones[0][2]) - 34, mapY(layoutZones[0][4]),\n"
              "      mapX(layoutZones[0][2]) - 34, mapY(layoutZones[0][5]),\n"
              "      '셀 Y = ' + n(layoutZones[0][5] - layoutZones[0][4]) + ' mm', true, 'layout'));",
              "배치도 Y 전체치수")
    # 팝업 머리글도 셀 것으로.
    t = _once(t, "    layout: '전체 장비 상세 배치도',",
              "    layout: 'AFR-101 장비 스펙 · 셀 배치',", "배치도 팝업 제목")

    # ── 도면 팝업의 나머지 탭 ───────────────────────────────────────────────
    # ① **셀 단위 자료** — 지지·장착의 셀 선택과 도면 목록은 이 셀로 좁히면 맞는다.
    t = _once(t, "mtStationSel.innerHTML = MOUNTINGS.map(function (m) {",
              "mtStationSel.innerHTML = MOUNTINGS.filter(function (m) "
              "{ return m[0] === 'afr'; }).map(function (m) {", "지지·장착 셀 목록")
    t = _once(t, "mtStation: 'grm',", "mtStation: 'afr',", "지지·장착 기본 셀")
    t = _once(t, "registerBody.innerHTML = register.map(function (row) {",
              "registerBody.innerHTML = register.filter(function (row) "
              "{ return row.join(' ').indexOf('AFR') >= 0; }).map(function (row) {",
              "도면 목록")
    # ② 플랜트 계통 탭과 그 자리로 가는 사이드바 버튼, 그리고 플랜트 집계인 「지지
    #    부재」 표를 숨긴다. 요소는 남는다 — 원본 렌더러가 첫 렌더에서 채우기 때문이다.
    plant_only = ", ".join(["#pv-panel-mount .table-responsive"]
                           + [f"#{k}" for k in PLANT_SECTIONS])
    plant_tabs = ", ".join(f"#pv-tab-{k}" for k in PLANT_TABS)
    plant_btns = ", ".join(f'[data-pv-drawing-tab="{k}"]' for k in PLANT_TABS)
    t = _once(t, "</head>",
              f"<style>{plant_tabs}, {plant_btns}, {plant_only} "
              f"{{ display: none !important; }}</style>\n</head>",
              "플랜트 계통 탭 CSS")

    # 스펙은 배치도 패널 맨 위에 세운다.
    t = _once(t, '    <div id="pv-panel-layout" role="tabpanel" '
                 'aria-labelledby="pv-tab-layout" hidden>\n',
              '    <div id="pv-panel-layout" role="tabpanel" '
              'aria-labelledby="pv-tab-layout" hidden>\n' + spec_block(text),
              "장비 전체 스펙")

    # ── 흐름표 ──────────────────────────────────────────────────────────────
    t = _once(t, '<h3 id="pv-flow-title">전체 공정 흐름</h3>',
              '<h3 id="pv-flow-title">AFR-101 공정 흐름 '
              '<span class="text-small text-muted">투입·JBR 과 후단 연마·검사·버퍼는 범위 밖</span></h3>',
              "흐름표 제목")
    t = _once(t, "</head>",
              f"<style>.pv-flow-track > li:nth-child(-n+{FLOW_FIRST - 1}),"
              f" .pv-flow-track > li:nth-child(n+{FLOW_LAST + 1}) {{ display: none; }}</style>\n</head>",
              "흐름표 CSS")

    # ── 발주 요청 셋: 그림자 · 외장 케이싱 · 천장크레인 ─────────────────────
    # ① 그림자 — 렌더러 섀도맵을 첫 렌더 전에 끈다. 바닥 그림자가 셀 하나를 보는
    #    화면에서는 기구 밑을 어둡게 덮기만 한다. 재질 재컴파일이 필요 없는 자리다.
    t = _once(t, "Dt.shadowMap.enabled=!0;", "Dt.shadowMap.enabled=!1;", "3D 그림자")
    # ② 외장 케이싱 — 껍질이 기구를 가린다. 토글 기본값을 끄고, 장면 모듈이 묶음째
    #    끈다 (토글은 남으니 외형이 필요하면 켤 수 있다).
    t = _once(t, '<input class="form-check-input" id="pv-case" type="checkbox" checked>',
              '<input class="form-check-input" id="pv-case" type="checkbox">', "외장 케이싱 기본값")
    # ③ CRN-901 천장크레인 — 셀에 매이지 않는 `pvSpans` 묶음이라 이름을 붙여야
    #    장면 모듈이 통째로 끌 수 있다. `pvCase` 가 이미 쓰는 방식과 같다.
    t = _once(t, "var pvCrn=new ce;pt.add(pvSpans(pvCrn));",
              "var pvCrn=new ce;pvCrn.name='pvCrn';pt.add(pvSpans(pvCrn));", "천장크레인 이름")

    # 부품 2D·3D 검색 — 목록에는 플랜트 전 품번이 그대로 있다. 이 셀 것만 보려면
    # 매번 "AFR-" 를 쳐야 하므로 검색창을 그 값으로 미리 채우고, 프로그램을 열 때
    # 한 번 거른다. 목록 자체는 줄이지 않는다 — 지우면 다른 셀 부품을 못 보게 된다.
    t = _once(t, 'placeholder="예: AFU-LFT, 승강, EOAT"',
              'value="AFR-" placeholder="예: AFR-PL, 정반, 쇠막대"', "부품 검색 기본값")
    t = _once(t, "    if (name === 'parts' && partsCatalog) partsCatalog.open = true;",
              "    if (name === 'parts' && partsCatalog) { partsCatalog.open = true; applyPartsFilter(); }",
              "부품 검색 최초 적용")
    # 품번 접두어로 거를 때는 **품번만** 본다. 원본은 행 전체 글자를 뒤지는데, 다른
    # 셀 부품의 주기가 이 셀 품번을 인용하고 있어 접두어로 걸러도 남의 부품이
    # 딸려 온다. 품명·재질로 찾는 검색은 그대로 둔다 — 접두어꼴일 때만 좁힌다.
    t = _once(t, "      var hit = !needle || row.textContent.toLowerCase().indexOf(needle) >= 0;",
              "      var byNo = /^[a-z]+-/.test(needle);\n"
              "      var hit = !needle || (byNo\n"
              "        ? (row.dataset.partNo || '').toLowerCase().indexOf(needle) >= 0\n"
              "        : row.textContent.toLowerCase().indexOf(needle) >= 0);",
              "부품 검색 품번 우선")

    # ── 상·하류 전용 조작 ───────────────────────────────────────────────────
    for key in HIDDEN_CONTROLS:
        if f'<label class="form-label" for="{key}">' not in t:
            raise SystemExit(f"✗ 범위 밖 조작 {key} 의 라벨이 없다")
    # `!important` 없이는 못 이긴다 — 배치 초점 라벨은 `.pv-layout-toolbar .form-label`
    # (클래스 둘)이 잡고 있어서 `label[for=…]`(클래스 하나) 보다 우선순위가 높다.
    hidden = ", ".join(f'label[for="{k}"]' for k in HIDDEN_CONTROLS) + ", #afr-buffer-reset"
    t = _once(t, '<button class="btn" id="afr-buffer-reset" type="button">',
              '<button class="btn" id="afr-buffer-reset" type="button" hidden>', "버퍼 초기화 버튼")
    t = _once(t, "</head>", f"<style>{hidden} {{ display: none !important; }}</style>\n</head>",
              "범위 밖 조작 CSS")

    # ── 장면을 좁히는 모듈 — 원본 모듈 뒤에 선다 ────────────────────────────
    t = _once(t, "</body>", scene_script(low, high, t0, t1) + "</body>", "장면 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- AFR-101 파생본: tools/build_afr_scene.py 가 통합 "
              "설계도(pv-preprocess-plant.html)에서 만든다. 손으로 고치지 않는다.\n"
              f"     셀 외형 {L:,} × {W:,} × {H:,} mm · 창 [{t0:g}, {t1:g}] s · "
              "그림자·외장 케이싱·CRN-901 천장크레인 제외. -->\n",
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
