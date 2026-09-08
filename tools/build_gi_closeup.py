# -*- coding: utf-8 -*-
"""GI-302 · GI-303 유리 검사 **작동 확대도** — 통합 설계도에서 파생한다.

통합 설계도에서 이 셀은 상자 몇 개다. `vision` 이 GI-303 주기에 "CV-102
롤러(Ø90 · 피치 240) 사이 150 mm 틈에 라인조명과 라인스캔을 넣어 통과 중에
밑을 본다" 고 적었고, 배치는 그 자리에 **550 mm** 를 배정했다. 그 두 줄만으로는
**검사대가 성립하는지**를 볼 수 없다 — 라인스캔은 이송·라인레이트·노광·조명이
한 사슬이고, 넷째로 **형상이 자리를 먹기** 때문이다.

이 파생본은 그것을 셋으로 나눠 편다.

* **GI-303 하부 라인스캔** — 폭을 보려면 자리가 드는데 밑에는 그만한 자리가
  없다. 한 대짜리 광학계가 먹는 높이를 렌즈 공식이 내는데 그것이 배정을
  넘어서, **화소가 아니라 자리 때문에** 여러 대가 된다. 그 수는 여기 안 적는다 —
  `gi_optics` 가 풀고 화면이 받는다.
* **GI-302 상부 라인스캔** — 똑같은 광학인데 위는 넉넉해 한 대로 끝난다.
  같은 렌즈·같은 센서에서 답이 갈리는 이유가 **자리뿐**임을 나란히 놓고 본다.
* **롤러 창 · 스캔선** — 실제 단면 그대로, 배율만 키운다. 창 150 mm 안에서
  스캔선이 얼마나 가는 선인지, 심도가 판 휨을 어떻게 덮는지를 본다.

밑에 **자리 띠**를 깐다. 카메라가 폭 1,400 을 어떻게 나눠 보고 이음매마다
얼마를 겹치는지가 `gi_optics.seam_map()` 에서 그대로 오므로, 이음매가 비지
않는다는 것이 그림으로 드러난다.

형상·수치는 전부 `src/pv_preprocess/gi_optics.py` 에서 온다 — 화면에 손으로 쓴
값이 없다. 원본 파일은 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 한다.

    PYTHONPATH=src python tools/build_gi_closeup.py

멱등이다. `tests/test_pv_gi.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign, gi_optics, vision  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-gi-closeup.html"

#: 플랜트 콘솔에서 이 파생본이 쓰지 않는 것 — 형상과 자리만 보는 화면이다.
HIDE = (
    ".pv-v22-programs", ".pv-v22-console .pv-v22-status-row",
    ".pv-v22-console .viz-controls", ".pv-v22-console .pv-v22-timeline",
    ".pv-v22-move-hint", ".jb-integrated-header", ".pv-flow-map",
    '.viz-controls[aria-label="재생 제어"]', ".jb-scrub-label", "#jb-scrub",
    "#jb-progress", ".jb-live-spec", ".pv-drawing-suite", "details.jb-engineering",
    "#jb-parts-catalog", "#jb-reference-panel", "#pv-cut-controls",
)


def _once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"✗ {what}: 앵커가 {n}곳 — 1곳이어야 한다\n  {old[:90]}")
    return text.replace(old, new)


def unit_payload() -> str:
    """3D 가 읽는 부품 자료 — 모델에서 그대로 나온다."""
    out = []
    for u in gi_optics.units():
        out.append({
            "key": u.key, "name": u.name, "sheet": u.sheet,
            "envelope": list(u.envelope_mm), "viewR": u.view_r_mm,
            "mag": gi_optics.WINDOW_MAG if u.key == "window" else 1.0,
            "view": list(gi_optics.VIEW_DIR[u.key]),
            "principle": [list(s) for s in u.principle],
            "parts": [{
                "key": p.key, "name": p.name, "qty": p.qty, "shape": p.shape,
                "size": list(p.size), "pos": list(p.pos), "axis": p.axis,
                "mirror": list(p.mirror), "color": p.color, "material": p.material,
                "role": p.role, "spec": p.spec, "catalog": p.catalog,
                "explode": list(p.explode),
            } for p in u.parts],
        })
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def seam_payload() -> str:
    """자리 띠가 읽는 자료 — 어느 카메라가 폭의 어디를 보는가."""
    g, n = gi_optics, gi_optics.cameras_below()
    return json.dumps({
        "seats": [dict(x) for x in g.seam_map()],
        "cameras": n,
        "panelW": g.PANEL_W_MM,
        "field": g.field_width_mm(n),
        "overlapEach": g.seam_overlap_each_mm(n),
        "overlapTotal": g.seam_overlap_mm(n),
        "covers": g.seam_map_covers_the_width(),
        "sensorPx": g.SENSOR_PX,
        "pixelsNeeded": g.pixels_needed(),
        "oneNeeds": g.one_camera_would_need_mm(),
        "allotted": g.BELOW_DECK_MM,
        "shortfall": g.single_camera_shortfall_mm(),
        "stack": g.stack_height_mm(n),
    }, ensure_ascii=False, separators=(",", ":"))


def spec_payload() -> str:
    """유닛별 사양표 — 값은 전부 광학이 푼 것이다."""
    g = gi_optics
    n, up = g.cameras_below(), g.cameras_above()
    chain = [
        ["이송 → 라인레이트", f"{g.TRANSPORT_MM_S:.0f} mm/s ÷ {g.RESOLUTION_MM} mm/px = "
                        f"**{g.line_rate_hz():,.0f} line/s** (화소가 정사각이려면)"],
        ["라인주기 · 노광", f"{g.line_period_us():.0f} µs × 듀티 {g.EXPOSURE_DUTY:.0%} = "
                      f"**{g.exposure_us():.0f} µs** — 면적 카메라(1/60 s)의 "
                      f"**1/{g.exposure_vs_area_camera():,}**"],
        ["필요 화소 / 센서", f"폭 {g.PANEL_W_MM:,.0f} ÷ {g.RESOLUTION_MM} = "
                       f"**{g.pixels_needed():,} px** · 센서 {g.SENSOR_PX:,} px × "
                       f"{g.SENSOR_PITCH_UM} µm = 상 {g.sensor_width_mm():.1f} mm"],
    ]
    return json.dumps({
        "below": chain + [
            ["대수 — 자리가 정한다", f"한 대면 스택 **{g.one_camera_would_need_mm():.0f} mm**, "
                            f"배정 {g.BELOW_DECK_MM:.0f} mm → "
                            f"**{g.single_camera_shortfall_mm():.0f} mm 초과.** "
                            f"**{n} 대**면 {g.stack_height_mm(n):.0f} mm 로 든다"],
            ["화소는 남는다", f"센서 한 장 {g.SENSOR_PX:,} px 가 필요한 "
                        f"{g.pixels_needed():,} px 를 이미 넘는다 — "
                        f"**여러 대인 것은 화소 때문이 아니다**"],
            ["배율 / 작동거리", f"m = {g.sensor_width_mm():.1f} ÷ "
                        f"{g.field_width_mm(n):.0f} = **{g.magnification(n):.4f}** · "
                        f"WD = f(1+1/m) = **{g.working_distance_mm(n):.0f} mm** "
                        f"(f{g.LENS_F_MM:.0f})"],
            ["시야 / 이음매", f"대당 {g.field_width_mm(n):.0f} mm · 이음매마다 "
                       f"**{g.seam_overlap_each_mm(n)} mm** 겹침 (합 "
                       f"{g.seam_overlap_mm(n)} mm)"],
            ["심도", f"2Nc(1+m)/m² = **{g.depth_of_field_mm(n)} mm** ≥ 통과 중 휨 "
                  f"{g.PANEL_BOW_MM} mm (F{g.F_NUMBER} · c "
                  f"{g.CIRCLE_OF_CONFUSION_MM * 1000:.1f} µm)"],
            ["창", f"피치 {g.ROLLER_PITCH_MM:.0f} − 외경 {g.ROLLER_D_MM:.0f} = "
                 f"**{g.roller_window_mm():.0f} mm** · `vision` 주기와 같다 · "
                 f"스캔선 폭은 그 {g.RESOLUTION_MM / g.roller_window_mm():.2%}"],
        ],
        "above": chain + [
            ["대수 — 위는 넉넉하다", f"스택 {g.stack_height_mm(up):.0f} mm 가 배정 "
                            f"{g.ABOVE_DECK_MM:,.0f} mm 안이라 **{up} 대**로 끝난다. "
                            f"밑과 **같은 광학인데 답이 다르다**"],
            ["배율 / 작동거리", f"m = **{g.magnification(up):.4f}** · WD = "
                        f"**{g.working_distance_mm(up):.0f} mm**"],
            ["심도", f"**{g.depth_of_field_mm(up)} mm** — 배율이 낮아 밑보다 깊다"],
            ["보는 것", f"연마된 유리면. 아리스 **{g.arris_in_pixels():.0f} 화소**, "
                    f"남은 실란트 띠 **{g.sealant_band_in_pixels():,} 화소** — "
                    f"둘 다 확실판정 기준 {g.PIXELS_PER_FEATURE} 화소 위"],
            ["존치 헤드", f"{' · '.join(g.kept_heads())} — GI-301 은 은퇴했다. "
                     f"그래서 **연마 전 검사가 없다**"],
        ],
        "window": chain[:1] + [
            ["창 대 스캔선", f"창 **{g.roller_window_mm():.0f} mm** 안에서 스캔선 폭은 "
                       f"화소 하나 **{g.RESOLUTION_MM} mm** — "
                       f"{g.RESOLUTION_MM / g.roller_window_mm():.2%} 다. "
                       f"**막는 것은 창의 폭이 아니라 밑의 높이다**"],
            ["받침 없는 거리", f"롤러 두 개 사이 **{g.unsupported_span_mm():.0f} mm** 가 뜬다. "
                        f"그 처짐이 심도 {g.depth_of_field_mm(n)} mm 안이라 초점이 산다"],
            ["최소 결함", f"{g.PIXELS_PER_FEATURE} 화소 × {g.RESOLUTION_MM} = "
                    f"**{g.smallest_reliable_feature_mm()} mm** 부터 확실히 잡는다"],
            ["자료량", f"장당 {g.pixels_per_panel():,} 화소 = **{g.mb_per_panel():.0f} MB** — "
                   f"`ai` 가 적어 둔 값과 **다시 세어도 같다** · "
                   f"{g.pixel_rate_mpx_s():.0f} Mpx/s"],
            ["시간", f"길이 {g.PANEL_L_MM:,.0f} ÷ {g.TRANSPORT_MM_S:.0f} = "
                  f"**{g.scan_time_s()} s** · 가동률 {g.duty():.1%} — 택트 안에 든다"],
            ["배율", f"단면은 실제 값 그대로이고 화면에서만 **{g.WINDOW_MAG:.0f} 배**로 "
                  f"세운다 — 창 {g.roller_window_mm():.0f} 와 화소 "
                  f"{g.RESOLUTION_MM} 는 {g.PANEL_W_MM:,.0f} 옆에서 안 보인다"],
        ],
    }, ensure_ascii=False, separators=(",", ":"))


def open_payload() -> str:
    """모델이 **못 닫는** 것 — 선언이 아니라 계산에서 나온 목록이다."""
    return json.dumps([list(q) for q in gi_optics.open_questions()],
                      ensure_ascii=False, separators=(",", ":"))


def console_html() -> str:
    """3D 밑에 서는 확대도 콘솔 — 유닛 선택·분해·단면·단계·자리 띠·부품표."""
    return """
  <section class="gi-cu" id="gi-cu" aria-label="GI 검사 작동 확대도">
    <div class="gi-cu-head">
      <div class="viz-controls" role="tablist" aria-label="유닛 선택" id="gi-cu-tabs"></div>
      <span class="viz-badge tabular-nums" id="gi-cu-sheet"></span>
    </div>
    <div class="viz-controls gi-cu-controls">
      <label class="form-label" for="gi-cu-explode">분해 <span class="tabular-nums" id="gi-cu-explode-value">0%</span>
        <input class="form-range" id="gi-cu-explode" type="range" min="0" max="100" step="1" value="0">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="gi-cu-cut" type="checkbox">
        <span class="form-check-label">단면</span></label>
      <label class="form-label" for="gi-cu-cut-at">절단 위치 <span class="tabular-nums" id="gi-cu-cut-value">50%</span>
        <input class="form-range" id="gi-cu-cut-at" type="range" min="0" max="100" step="1" value="50">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="gi-cu-spin" type="checkbox" checked>
        <span class="form-check-label">롤러 회전</span></label>
      <button class="btn" id="gi-cu-prev" type="button">◀ 이전 단계</button>
      <button class="btn btn-primary" id="gi-cu-play" type="button">작동 재생</button>
      <button class="btn" id="gi-cu-next" type="button">다음 단계 ▶</button>
      <button class="btn" id="gi-cu-fit" type="button">시점 맞춤</button>
    </div>
    <div class="gi-cu-step" id="gi-cu-step" aria-live="polite"></div>
    <div class="card gi-cu-cycle">
      <div class="gi-cu-cycle-head">
        <h3 class="text-small">폭 1,400 을 나눠 보는 자리 — 이음매는 <b>겹친다</b></h3>
        <span class="text-small text-muted tabular-nums" id="gi-cu-cycle-sum"></span>
      </div>
      <div class="gi-cu-band" id="gi-cu-band" role="img" aria-label="카메라 자리 배치"></div>
      <p class="text-small text-muted" id="gi-cu-cycle-note"></p>
    </div>
    <div class="card gi-cu-open">
      <h3 class="text-small">이 해석이 못 닫는 것 <span class="text-muted tabular-nums" id="gi-cu-open-count"></span></h3>
      <dl class="gi-cu-open-list" id="gi-cu-open"></dl>
    </div>
    <div class="card jb-detail" id="jb-detail" aria-live="polite">형상을 누르면 그 부품의 품번과 역할이 여기에 나옵니다.</div>
    <div class="gi-cu-grid">
      <div class="card gi-cu-parts">
        <h3 class="text-small">부품 구성 <span class="text-muted" id="gi-cu-count"></span></h3>
        <div class="table-responsive"><table class="table table-sm"><thead>
          <tr><th>부품</th><th>수량</th><th>규격</th><th>재질</th></tr>
        </thead><tbody id="gi-cu-rows"></tbody></table></div>
        <p class="text-small text-muted">행을 누르면 그 부품만 남기고 시점이 붙습니다. 형상을 눌러도 같습니다.</p>
      </div>
      <div class="card gi-cu-side">
        <h3 class="text-small">작동 원리</h3>
        <ol class="gi-cu-steps" id="gi-cu-principle"></ol>
        <h3 class="text-small gi-cu-h2">광학이 푸는 수</h3>
        <div class="table-responsive"><table class="table table-sm"><tbody id="gi-cu-spec"></tbody></table></div>
      </div>
    </div>
  </section>
"""


def console_css() -> str:
    return """
  .gi-cu { display: flex; flex-direction: column; gap: 10px; }
  .gi-cu-head { display: flex; flex-wrap: wrap; align-items: center;
    justify-content: space-between; gap: 8px; }
  .gi-cu-controls { align-items: end; }
  .gi-cu-controls .form-label { flex: 0 1 210px; }
  .gi-cu-step { padding: 8px 12px; border-radius: var(--radius-lg);
    background: var(--muted); font-size: var(--font-size-normal); }
  .gi-cu-step b { color: var(--primary); }
  .gi-cu-cycle-head { display: flex; flex-wrap: wrap; align-items: baseline;
    justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .gi-cu-band { display: flex; width: 100%; height: 46px; overflow: hidden;
    border-radius: var(--radius-sm); }
  .gi-cu-band span { display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 1px; min-width: 0; overflow: hidden;
    border-right: 1px solid var(--background); font-size: var(--font-size-small);
    line-height: 1.15; white-space: nowrap; }
  .gi-cu-band span:last-child { border-right: 0; }
  .gi-cu-band b { font-weight: var(--font-weight-medium); }
  .gi-cu-band .gi-p-seat { background: var(--primary); color: var(--primary-foreground); }
  .gi-cu-band .gi-p-seat + .gi-p-seat { background: var(--accent);
    color: var(--accent-foreground); }
  .gi-cu-band .gi-p-seat + .gi-p-seat + .gi-p-seat { background: var(--primary);
    color: var(--primary-foreground); }
  .gi-cu-band .is-now { outline: 2px solid var(--foreground); outline-offset: -2px; }
  .gi-cu-grid { display: grid; gap: 10px;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); }
  .gi-cu-parts tbody tr { cursor: var(--cursor-interaction, pointer); }
  .gi-cu-parts tbody tr:hover { background: var(--muted); }
  .gi-cu-parts tbody tr.is-on { background: var(--accent); color: var(--accent-foreground); }
  .gi-cu-steps { margin: 0; padding-left: 18px; display: flex;
    flex-direction: column; gap: 6px; font-size: var(--font-size-small); }
  .gi-cu-steps li.is-on { font-weight: var(--font-weight-medium); color: var(--primary); }
  .gi-cu-h2 { margin-top: 12px; }
  .gi-cu-open { border-left: 3px solid var(--destructive); }
  .gi-cu-open-list { margin: 8px 0 0; display: flex; flex-direction: column; gap: 8px;
    font-size: var(--font-size-small); }
  .gi-cu-open-list dt { font-weight: var(--font-weight-medium); color: var(--destructive); }
  .gi-cu-open-list dd { margin: 2px 0 0; color: var(--muted-foreground); }
"""


def scene_script() -> str:
    """부품을 실제로 그리는 모듈 — 통합 설계도의 3D 연장을 쓴다."""
    g = gi_optics
    return f"""<script>
/* GI 검사 작동 확대도 — tools/build_gi_closeup.py 가 붙인다.
   형상은 `gi_optics.py` 의 부품 목록에서 나오고 — 자리는 작동거리·스택 높이·
   자리표가 정한다 — 그리는 연장은 통합 설계도가 `__pvScene.kit` 으로 내준 것이라
   재질·조명이 플랜트와 같다. */
(function () {{
  /* 원본 3D 는 `<script type="module">` 이라 이 고전 스크립트보다 **뒤에** 돈다. */
  var tries = 0;
  (function wait() {{
    var r = document.getElementById('jb-removal-operation');
    if (r && r.__pvScene && r.__pvScene.kit) return start(r.__pvScene);
    if (tries++ < 600) requestAnimationFrame(wait);
  }})();
  function start(S) {{
  var K = S.kit, UNITS = {unit_payload()}, SEAM = {seam_payload()},
      SPEC = {spec_payload()}, OPEN = {open_payload()};
  var MM = 0.001;                                   // 모델은 mm, 씬은 m
  var TRANSPORT = {g.TRANSPORT_MM_S}, LINE_HZ = {g.line_rate_hz()},
      PANEL_W = {g.PANEL_W_MM}, PANEL_L = {g.PANEL_L_MM},
      MAG = {g.WINDOW_MAG}, WINDOW = {g.roller_window_mm()},
      BOW = {g.PANEL_BOW_MM}, DOF = {g.depth_of_field_mm(g.cameras_below())};
  /* 롤러 각속도 — 미끄럼 없이 굴러야 하므로 ω = v / r 다. rpm 을 따로 안 정한다. */
  var ROLLER_RAD_S = TRANSPORT / ({g.ROLLER_D_MM} / 2);
  var chrome = K.M.steel.clone(); chrome.metalness = .62; chrome.roughness = .26;
  /* 판은 비쳐야 한다 — 밑을 보는 도면인데 판이 막히면 광학이 안 보인다. */
  var glass = K.M.aluminum.clone(); glass.transparent = !0; glass.opacity = .26;
  glass.depthWrite = !1; glass.color.set(0x9fd8e8);
  /* 조명과 스캔선은 **빛**이라 살이 아니다 — 스스로 밝게 둔다. */
  var amber = K.M.orange.clone(); amber.emissive && amber.emissive.set(0x552200);
  /* 심도 포락선은 자리를 차지하는 물건이 아니라 **영역**이다. */
  var cyan = K.M.aluminum.clone(); cyan.transparent = !0; cyan.opacity = .18;
  cyan.depthWrite = !1; cyan.color.set(0x36c6d8);
  var MAT = {{ steel: K.M.steel, dark: K.M.dark, orange: K.M.orange,
    rubber: K.M.rubber, frame: K.M.frame, aluminum: K.M.aluminum,
    chrome: chrome, glass: glass, amber: amber, cyan: cyan }};
  var group = new S.Group(); S.scene.add(group);
  var built = {{}}, active = null, step = 0, playing = false, focus = null, spin = 0;

  function placements(p) {{                          /* 수량을 실제 자리로 편다 */
    var m = p.mirror.join(',');
    if (m === 'z') return [[p.pos[0], p.pos[1], p.pos[2]],
                           [p.pos[0], p.pos[1], -p.pos[2]]];
    if (m === 'x') return [[p.pos[0], p.pos[1], p.pos[2]],
                           [-p.pos[0], p.pos[1], p.pos[2]]];
    return [[p.pos[0], p.pos[1], p.pos[2]]];
  }}

  function build(u) {{
    var grp = new S.Group(); grp.visible = false; group.add(grp);
    u.parts.forEach(function (p) {{
      placements(p).forEach(function (at, idx) {{
        var mesh, mat = MAT[p.color] || K.M.steel;
        if (p.shape === 'cyl') {{
          var r = p.size[0] * MM / 2, h = p.size[1] * MM;
          mesh = new K.Mesh(new K.Cyl(r, r, h, 30), mat);
          if (p.axis === 'x') mesh.rotation.z = Math.PI / 2;
          else if (p.axis === 'z') mesh.rotation.x = Math.PI / 2;
        }} else {{
          mesh = new K.Mesh(new K.Box(p.size[0] * MM, p.size[1] * MM, p.size[2] * MM), mat);
        }}
        mesh.castShadow = !0; mesh.receiveShadow = !0;
        mesh.position.set(at[0] * MM, at[1] * MM, at[2] * MM);
        mesh.userData.home = mesh.position.clone();
        mesh.userData.blow = new S.Vector3(p.explode[0] * MM, p.explode[1] * MM,
                                           p.explode[2] * MM);
        mesh.userData.part = p.key;
        mesh.userData.side = at[2] < 0 ? -1 : 1;
        mesh.userData.label = p.name + (p.catalog !== '—' ? ' (' + p.catalog + ')' : '');
        mesh.userData.note = p.role + (p.spec ? ' · ' + p.spec : '') + ' · ' + p.material;
        if (idx === 0) K.pick.push(mesh);
        grp.add(mesh);
      }});
    }});
    return grp;
  }}

  /* 작동원리 — 단계마다 부품이 실제로 움직인다.
     도는 것은 이송롤러뿐이고 그 속도는 **이송이 정한다** (ω = v / r) —
     연마휠처럼 따로 rpm 을 갖는 물건이 이 셀에는 없다. */

  function pose(u, t) {{
    var grp = built[u.key]; if (!grp) return;
    var ex = exVal();
    grp.children.forEach(function (m) {{
      var k = m.userData.part, h = m.userData.home, d = new S.Vector3();
      m.visible = true;
      /* 자리 변화는 전부 **mm 로 셈해서 마지막에 m 로 바꾼다** — 씬은 m 다. */
      if (u.key === 'below' || u.key === 'above') {{
        /* 판이 {g.TRANSPORT_MM_S:.0f} mm/s 로 창 위를 지나간다. 광학은 서 있다 —
           라인스캔은 **이송이 곧 두 번째 축**이라 카메라가 움직일 이유가 없다. */
        var run = Math.max(0, Math.min(1, (t - 1) / 2));
        if (/glass$/.test(k)) d.z = (run * 2 - 1) * 420;
        /* 조명은 스캔이 시작돼야 켜진다 — 노광이 라인주기의 일부다. */
        if (/light$/.test(k)) m.visible = t >= 1;
        /* 브래킷·갠트리는 분해로만 움직인다 */
      }} else {{
        /* 창 확대도 — 판이 받침 없는 구간에서 심도 안으로 처진다.
           이 유닛은 배율이 걸려 있으므로 처짐도 같은 배율로 잰다. */
        var sag = Math.max(0, Math.min(1, t - 1));
        if (k === 'wnglass') d.y = -sag * BOW * MAG;
        /* 심도 포락선은 ③에서만 세운다 — 늘 켜 두면 유리를 가린다 */
        if (k === 'wndof') m.visible = t >= 2;
      }}
      d.multiplyScalar(MM);
      m.position.copy(h).add(d).add(m.userData.blow.clone().multiplyScalar(ex));
      /* 롤러는 z 로 눕혀 놓았으므로(축이 x) 스핀은 x 성분에 얹는다 */
      if (/rl\d+$/.test(k)) m.rotation.x = spin;
    }});
  }}

  /* 모델 글은 **강조** 를 마크다운으로 쓴다 — 화면에서는 태그로 바꾼다. */
  function md(s) {{ return String(s).replace(/\\*\\*(.+?)\\*\\*/g, '<b>$1</b>'); }}
  function exVal() {{ return Number(el('gi-cu-explode').value) / 100; }}
  function el(id) {{ return document.getElementById(id); }}

  function fit(u) {{
    /* 거리를 눈대중으로 잡으면 무대 비율이 바뀔 때마다 잘린다 — 시야각에서
       **푼다.** 세로 시야각은 고정이고 가로는 그것에 종횡비를 곱한 것이므로,
       두 축을 각각 풀어 먼 쪽을 쓴다. 이 무대는 가로로 길어 보통 세로가 이긴다. */
    var e = u.envelope, t = Math.tan((S.camera.fov || 50) * Math.PI / 360),
        a = S.camera.aspect || 1.8;
    var wide = Math.max(e[0], e[2]) / 2 * MM;       // 수평으로 담아야 하는 반폭
    var tall = e[1] / 2 * MM;                       // 세로로 담아야 하는 반높이
    /* 여백 — 시점이 비스듬하면 포락선의 대각이 화면에 들어오므로 그만큼 더 뺀다. */
    var d = Math.max(tall / t, wide / (t * a)) * 1.45 + wide * .45;
    /* 방향은 모델(`gi_optics.VIEW_DIR`)이 정한다 — 접촉부는 단면이라 스윕 축을
       따라 봐야 옆모습이 나온다. */
    var v = u.view || [.6, .8, 1], n = Math.hypot(v[0], v[1], v[2]);
    S.camera.position.set(v[0] / n * d, v[1] / n * d, v[2] / n * d);
    S.controls.target.set(0, tall * .12, 0); S.controls.update();
  }}

  /* 자리 띠 — 카메라가 폭의 어디를 보는가. 자리와 겹침이 모델에서 그대로 온다 */
  function band() {{
    var half = SEAM.panelW / 2;
    el('gi-cu-band').innerHTML = SEAM.seats.map(function (t, i) {{
      return '<span class="gi-p-seat" data-i="' + i + '" style="flex:' + t.width + ' 1 0">'
        + '<b>카메라 ' + (i + 1) + '</b><span>' + t.width.toFixed(0) + ' mm · '
        + t.from.toFixed(0) + ' → ' + t.to.toFixed(0) + '</span></span>';
    }}).join('');
    el('gi-cu-cycle-sum').textContent = '폭 ' + SEAM.panelW.toFixed(0) + ' mm · '
      + SEAM.cameras + ' 대 · 이음매 ' + (SEAM.cameras - 1) + ' 곳 × '
      + SEAM.overlapEach.toFixed(1) + ' mm';
    el('gi-cu-cycle-note').innerHTML = md(
      '폭 **' + SEAM.panelW.toFixed(0) + ' mm** 를 한 대로 보려면 광학계가 **'
      + SEAM.oneNeeds.toFixed(0) + ' mm** 를 먹는데 롤러 밑에 배정된 것은 '
      + SEAM.allotted.toFixed(0) + ' mm 다 — **' + SEAM.shortfall.toFixed(0)
      + ' mm 초과.** 센서 한 장이면 화소는 ' + SEAM.sensorPx.toLocaleString()
      + ' 로 필요한 ' + SEAM.pixelsNeeded.toLocaleString()
      + ' 에 대해 남으므로, **여러 대인 것은 화소가 아니라 자리 때문이다.** '
      + SEAM.cameras + ' 대로 나누면 스택이 **' + SEAM.stack.toFixed(0)
      + ' mm** 로 줄어 들어가고, 이음매마다 **' + SEAM.overlapEach.toFixed(1)
      + ' mm** 씩 겹쳐 폭을 빈틈없이 덮는다.');
  }}

  function bandMark() {{
    /* 밑을 보는 유닛일 때만 자리를 짚는다 — 위는 한 대라 나눌 자리가 없다 */
    var on = active && active.key === 'below';
    [].forEach.call(el('gi-cu-band').children, function (s) {{
      s.classList.toggle('is-now', on);
    }});
  }}

  function show(key) {{
    active = UNITS.filter(function (u) {{ return u.key === key; }})[0];
    UNITS.forEach(function (u) {{ built[u.key].visible = u.key === key; }});
    el('gi-cu-sheet').textContent = active.sheet;
    el('gi-cu-count').textContent = '· ' + active.parts.length + ' 종 '
      + active.parts.reduce(function (a, p) {{ return a + p.qty; }}, 0) + ' 개';
    el('gi-cu-rows').innerHTML = active.parts.map(function (p) {{
      return '<tr data-part="' + p.key + '"><td>' + p.name + '</td><td class="tabular-nums">'
        + p.qty + '</td><td>' + md(p.spec || '—') + '</td><td>' + p.material + '</td></tr>';
    }}).join('');
    el('gi-cu-principle').innerHTML = active.principle.map(function (s) {{
      return '<li><b>' + s[0] + '</b> ' + md(s[1]) + '</li>';
    }}).join('');
    el('gi-cu-spec').innerHTML = (SPEC[key] || []).map(function (r) {{
      return '<tr><th scope="row">' + r[0] + '</th><td>' + md(r[1]) + '</td></tr>';
    }}).join('');
    [].forEach.call(el('gi-cu-tabs').children, function (b) {{
      b.classList.toggle('btn-primary', b.dataset.unit === key);
      b.setAttribute('aria-selected', String(b.dataset.unit === key));
    }});
    step = 0; focus = null; fit(active); render();
  }}

  function render() {{
    if (!active) return;
    pose(active, step);
    var p = active.principle[Math.min(active.principle.length - 1, Math.floor(step))];
    el('gi-cu-step').innerHTML = '<b>' + p[0] + '</b> ' + md(p[1]);
    [].forEach.call(el('gi-cu-principle').children, function (li, i) {{
      li.classList.toggle('is-on', i === Math.floor(step));
    }});
    [].forEach.call(el('gi-cu-rows').children, function (tr) {{
      tr.classList.toggle('is-on', tr.dataset.part === focus);
    }});
    if (focus) built[active.key].children.forEach(function (m) {{
      m.visible = m.userData.part === focus;
    }});
    el('gi-cu-explode-value').textContent = Math.round(exVal() * 100) + '%';
    el('gi-cu-cut-value').textContent = el('gi-cu-cut-at').value + '%';
    bandMark();
  }}

  /* 단면 — 씬 전체에 잘라 내는 평면 하나를 건다 */
  var plane = new S.Plane(new S.Vector3(-1, 0, 0), 0);
  function cutUpdate() {{
    var on = el('gi-cu-cut').checked;
    S.renderer.clippingPlanes = on ? [plane] : [];
    S.renderer.localClippingEnabled = on;
    if (active) plane.constant = (Number(el('gi-cu-cut-at').value) / 100 - .5)
      * active.envelope[0] * MM;
  }}

  UNITS.forEach(function (u) {{ built[u.key] = build(u); }});
  el('gi-cu-tabs').innerHTML = UNITS.map(function (u) {{
    return '<button class="btn" type="button" role="tab" data-unit="' + u.key + '">'
      + u.name.split(' (')[0] + '</button>';
  }}).join('');
  el('gi-cu-tabs').addEventListener('click', function (e) {{
    var b = e.target.closest('[data-unit]'); if (b) show(b.dataset.unit);
  }});
  el('gi-cu-rows').addEventListener('click', function (e) {{
    var tr = e.target.closest('[data-part]'); if (!tr) return;
    focus = focus === tr.dataset.part ? null : tr.dataset.part;
    if (!focus) built[active.key].children.forEach(function (m) {{ m.visible = true; }});
    render();
  }});
  el('gi-cu-explode').addEventListener('input', render);
  el('gi-cu-cut').addEventListener('change', cutUpdate);
  el('gi-cu-cut-at').addEventListener('input', cutUpdate);
  el('gi-cu-prev').addEventListener('click', function () {{
    playing = false; step = Math.max(0, Math.floor(step) - 1); render(); }});
  el('gi-cu-next').addEventListener('click', function () {{
    playing = false;
    step = Math.min(active.principle.length - 1, Math.floor(step) + 1); render(); }});
  el('gi-cu-play').addEventListener('click', function () {{
    playing = !playing; if (playing && step >= active.principle.length - 1) step = 0;
    el('gi-cu-play').textContent = playing ? '일시정지' : '작동 재생'; }});
  el('gi-cu-fit').addEventListener('click', function () {{ if (active) fit(active); }});

  /* 플랜트 형상은 매 프레임 끈다 — 원본 애니메이션이 계속 켜기 때문이다. */
  var last = performance.now();
  function tick(now) {{
    var dt = Math.min(.1, (now - last) / 1000); last = now;
    S.scene.traverse(function (o) {{
      if ((o.isMesh || o.isSprite || o.isLine) && !o.userData.part
          && !group.getObjectById(o.id)) o.visible = false;
    }});
    group.visible = true;
    if (active) built[active.key].visible = true;
    /* 3,000 rpm 을 그대로 돌리면 보이지도 않고 어지럽다 — 60 분의 1 로 돌린다 */
    if (el('gi-cu-spin').checked) spin += dt * ROLLER_RAD_S / 60;
    if (playing) {{
      step += dt * .55;
      if (step >= active.principle.length - 1) {{
        step = active.principle.length - 1; playing = false;
        el('gi-cu-play').textContent = '작동 재생';
      }}
    }}
    if (playing || el('gi-cu-spin').checked) render();
    requestAnimationFrame(tick);
  }}
  /* 원본 공정시계와 자동추적은 이 화면에서 방해만 된다. */
  var auto = document.getElementById('pv-auto-camera');
  if (auto && auto.checked) {{ auto.checked = !1; auto.dispatchEvent(new Event('change')); }}
  var play = document.getElementById('jb-play');
  if (play && /일시정지/.test(play.textContent)) play.click();
  el('gi-cu-open-count').textContent = '· ' + OPEN.length + ' 건';
  el('gi-cu-open').innerHTML = OPEN.map(function (q) {{
    return '<dt>' + md(q[0]) + '</dt><dd>' + md(q[1]) + '</dd>';
  }}).join('');
  band(); show(UNITS[0].key); cutUpdate(); requestAnimationFrame(tick);
  window.__pvGiCloseup = {{ units: UNITS.length, seam: SEAM,
    optics: {{ transport: TRANSPORT, lineHz: LINE_HZ, window: WINDOW,
               bow: BOW, dof: DOF }},
    panel: {{ w: PANEL_W, l: PANEL_L }}, mag: MAG,
    get meshes() {{ return group.children.reduce(function (a, g) {{
      return a + g.children.length; }}, 0); }},
    get active() {{ return active && active.key; }},
    get step() {{ return step; }},
    go: function (k, s) {{ show(k); step = s; render(); return true; }},
    /* 검사가 부품 자리를 직접 읽는 길 — 씬을 훑으면 플랜트 형상과 섞인다.
       (플랜트 메시도 userData.part 를 달고 있어 이름만으로는 안 갈린다.) */
    positions: function (k, s) {{
      this.go(k, s);
      var out = {{}};
      built[k].children.forEach(function (m) {{
        if (!out[m.userData.part]) out[m.userData.part] =
          [+m.position.x.toFixed(4), +m.position.y.toFixed(4), +m.position.z.toFixed(4)];
      }});
      return out;
    }} }};
  }}
}})();
</script>
"""


def build() -> str:
    g = gi_optics
    t = PLANT.read_text(encoding="utf-8")
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>GI-302 · GI-303 검사 작동 확대도</title>\n"
              '<meta name="description" content="'
              'GI-302 · GI-303 라인스캔 검사대를 부품 단위로 확대한 3D 도면 — '
              '롤러 밑 자리가 모자라 3 대가 되는 하부 라인스캔, 같은 광학인데 한 대로 '
              '끝나는 상부, 그리고 6배로 키운 롤러 창–스캔선. 자리 띠가 폭 1,400 을 '
              '어떻게 나눠 보고 이음매가 왜 겹쳐야 하는지를 '
              '보여 준다.">', "제목")
    t = _once(t, '<h2 id="pv-v22-title">태양광 패널 전처리 통합 플랜트</h2>',
              '<h2 id="pv-v22-title">GI 검사 작동 확대도 — 하부 라인스캔 · 상부 · '
              '롤러 창</h2>', "표제")
    t = _once(t, f'<span class="viz-badge">{campaign.total_dwell_s():g} s TRACE</span>',
              f'<span class="viz-badge">LINE SCAN · {g.line_rate_hz():,.0f} line/s</span>',
              "배지")
    rev = t.split("DRAWING_REVISION = '")[1].split("'")[0]
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · GI 검사 작동 확대도 · ENGINEERING BASE {rev}",
              "머리글")

    t = _once(t, "</head>", f"<style>{', '.join(HIDE)} {{ display: none !important; }}"
              f"{console_css()}</style>\n</head>", "콘솔 정리 CSS")
    t = _once(t, '    <section class="pv-v22-programs" aria-labelledby="pv-v22-program-title">',
              console_html()
              + '    <section class="pv-v22-programs" aria-labelledby="pv-v22-program-title">',
              "확대도 콘솔")
    t = _once(t, '<div class="card jb-detail" id="jb-detail" aria-live="polite">세 벽체 사이의 '
              'BFC-101A/B가 고정 픽업면의 한 장을 상승·반전하고, 650 mm 고상 로봇이 반전 완료품을 '
              '직접 픽업합니다. 적재부·반전기·로봇 사이에는 컨베이어가 없습니다.</div>', "",
              "원본 픽커 제거")
    t = _once(t, "Dt.shadowMap.enabled=!0;", "Dt.shadowMap.enabled=!1;", "3D 그림자")
    t = _once(t, '<input class="form-check-input" id="pv-case" type="checkbox" checked>',
              '<input class="form-check-input" id="pv-case" type="checkbox">', "외장 케이싱")
    t = _once(t, "</body>", scene_script() + "</body>", "검사 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- GI 검사 작동 확대도: tools/build_gi_closeup.py 가 "
              "통합 설계도에서 만든다. 손으로 고치지 않는다.\n"
              "     형상·수치는 src/pv_preprocess/gi_optics.py 에서 온다 — 화면에 손으로 쓴 "
              "값이 없다. -->\n", "파생본 표식")
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
