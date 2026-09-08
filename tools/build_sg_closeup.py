# -*- coding: utf-8 -*-
"""SG-301 엣지 연마 **작동 확대도** — 통합 설계도에서 파생한다.

통합 설계도에서 SG-301 은 상자 두 개다 — 몸체 2,200 × 1,500 × 2,220 과 횡행
헤드 300 × 950 × 1,900. 50 m 축척에서는 그것이 맞지만, 그 상자만 보고는
**어떻게 갈리는지** 알 수 없다. 휠이 어디를 무는지, 왜 통과속도가 300 mm/s
인지, 장변과 단변이 왜 동시가 아닌지가 전부 부품표 글자에만 있었다.

이 파생본은 그것을 셋으로 나눠 편다.

* **장변 통과 헤드** — 헤드가 서 있고 유리가 지나간다. 고정 2 대가 동시.
* **단변 횡행 헤드** — 유리가 서 있고 헤드가 폭을 건넌다. 1 대가 두 번.
* **휠–유리 접촉부** — 실제 단면 그대로, 배율만 20 배. 홈이 변을 물고 아리스가
  서는 자리를 본다.

밑에 **순환 띠**를 깐다. 다섯 상(相)의 자리와 길이가 `sg_grind.cycle()` 에서
그대로 오므로, 장변과 단변이 겹치지 않는다는 것이 그림으로 드러난다.

형상·수치는 전부 `src/pv_preprocess/sg_grind.py` 에서 온다 — 화면에 손으로 쓴
값이 없다. 원본 파일은 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 한다.

    PYTHONPATH=src python tools/build_sg_closeup.py

멱등이다. `tests/test_pv_sg.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign, sg_grind  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-sg-closeup.html"

#: 플랜트 콘솔에서 이 파생본이 쓰지 않는 것 — 형상과 순환만 보는 화면이다.
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
    for u in sg_grind.units():
        out.append({
            "key": u.key, "name": u.name, "sheet": u.sheet,
            "envelope": list(u.envelope_mm), "viewR": u.view_r_mm,
            "mag": sg_grind.CONTACT_MAG if u.key == "contact" else 1.0,
            "view": list(sg_grind.VIEW_DIR[u.key]),
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


def cycle_payload() -> str:
    """순환 띠가 읽는 상(相) 자료 — 어느 헤드가 언제 도는가."""
    return json.dumps({
        "phases": [dict(p) for p in sg_grind.cycle()],
        "total": sg_grind.occupancy_s(),
        "simultaneous": sg_grind.simultaneous_occupancy_s(),
        "cost": sg_grind.sequential_cost_s(),
        "slack": sg_grind.slack_s(),
        "afr": float(campaign.AFR_S),
    }, ensure_ascii=False, separators=(",", ":"))


def spec_payload() -> str:
    """유닛별 사양표 — 값은 전부 모델이 푼 것이다."""
    g, lf, sf = sg_grind, sg_grind.long_feed_mm_s(), sg_grind.short_feed_mm_s()
    common = [
        ["휠 / 주속", f"Ø{g.WHEEL_D_MM:.0f} × {g.WHEEL_W_MM:.0f} · "
                   f"{g.SPINDLE_RPM:,.0f} rpm → **{g.wheel_speed_m_s()} m/s**"],
        ["제거 단면 A", f"**{g.removal_area_mm2()} mm²/mm** "
                    f"(끝면 살 {g.STOCK_MM} × 유리 {g.GLASS_T_MM} + 아리스 "
                    f"{g.ARRIS_MM}² ⁄ 2) · 아리스 몫 {g.arris_share() * 100:.0f} %"],
        ["접촉폭 / 등가절입", f"a_p {g.contact_width_mm()} mm · "
                        f"a_e {g.equivalent_depth_mm() * 1_000:.1f} µm · "
                        f"접촉길이 {g.contact_length_mm()} mm"],
    ]
    return json.dumps({
        "long": common + [
            ["이송 / 속도비", f"{lf:.0f} mm/s · v_s/v_w = **{g.speed_ratio(lf):.0f} : 1**"],
            ["제거율 / 동력", f"Q {g.removal_rate_mm3_s(lf)} mm³/s × "
                         f"e_c {g.SPECIFIC_ENERGY_J_MM3:.0f} J/mm³ = "
                         f"**{g.cutting_power_w(lf):.0f} W**"],
            ["스핀들 이용률", f"**{g.utilisation(lf) * 100:.1f} %** "
                        f"({g.spindle_available_w():.0f} W 가용 = {g.SPINDLE_KW} kW × "
                        f"{g.SPINDLE_EFFICIENCY:.2f})"],
            ["한계 통과속도", f"**{g.max_feed_mm_s():.0f} mm/s** — 설계 {lf:.0f} 대비 여유 "
                        f"{g.feed_margin() * 100:.0f} %. e_c 가 "
                        f"{g.specific_energy_that_stalls():.1f} 을 넘으면 못 간다"],
            ["힘 / 면압", f"F_t {g.tangential_force_n(lf)} N · F_n "
                      f"**{g.normal_force_n(lf)} N** · 평균압 "
                      f"{g.contact_pressure_mpa(lf)} MPa"],
            ["헤드", f"고정 {g.LONG_HEADS} 대 · 두 장변 **동시** · 이송이 곧 연마 운동"],
        ],
        "short": common + [
            ["이송 / 속도비", f"{sf:.0f} mm/s · v_s/v_w = **{g.speed_ratio(sf):.0f} : 1**"],
            ["제거율 / 동력", f"Q {g.removal_rate_mm3_s(sf)} mm³/s → "
                         f"**{g.cutting_power_w(sf):.0f} W** · 이용률 "
                         f"{g.utilisation(sf) * 100:.1f} %"],
            ["행정 / 편도", f"폭 {campaign.PANEL_WIDTH_MM:,.0f} mm · "
                       f"{campaign.PANEL_WIDTH_MM / sf:.1f} s + 헤드 행정 "
                       f"{campaign.SG_HEAD_STROKE_S:.1f} s"],
            ["순환 점유", f"앞·뒤 두 번 = **{g.occupancy_s()} s** (동시라면 "
                      f"{g.simultaneous_occupancy_s()} s · 순차 비용 "
                      f"{g.sequential_cost_s()} s)"],
            ["AFR 대비 여유", f"정반 점유 {campaign.AFR_S} s − {g.occupancy_s()} s = "
                         f"**{g.slack_s()} s** → 택트 {campaign.summary()['takt_s']} s 는 "
                         f"AFR 이 정한다"],
            ["헤드", f"횡행 {g.SHORT_HEADS} 대 · 앞단변·뒷단변을 **차례로**"],
        ],
        "contact": common + [
            ["등가 칩두께", f"h_eq = a_e·v_w/v_s = **{g.chip_thickness_mm(lf) * 1_000:.2f} µm**"],
            ["연성 한계", f"d_c = 0.15(E/H)(K_c/H)² = "
                     f"**{g.ductile_limit_mm() * 1_000:.3f} µm** "
                     f"(E {g.GLASS_E_GPA:.0f} · H {g.GLASS_H_GPA:.1f} GPa · "
                     f"K_c {g.GLASS_KC_MPA_M05} MPa·m^0.5)"],
            ["영역", f"h_eq / d_c = **{g.brittleness_ratio(lf):.0f} 배** → **취성**. "
                  "유리는 흐르지 않고 깨져서 떨어진다"],
            ["아리스", f"{g.ARRIS_MM} mm × {g.ARRIS_DEG:.0f}° × {g.ARRIS_COUNT} 곳 — "
                    f"파단면의 균열 끝을 모서리에서 치운다"],
            ["홈 도피 / 높이 공차", f"도피 {g.GROOVE_RELIEF_MM} > 공차 "
                             f"±{g.HEIGHT_TOL_MM} mm · 최악 EVA 스침 "
                             f"{g.eva_skim_mm()} mm"],
            ["휠 마모", f"장당 반경 {g.radial_wear_um_per_panel()} µm · "
                    f"{g.WHEEL_SERVICE_MONTHS} 개월 "
                    f"{g.panels_per_service():,} 장이 요구하는 연삭비 "
                    f"**G ≥ {g.implied_g_ratio():,}** (벤더값 · R-04 에서 실측)"],
        ],
    }, ensure_ascii=False, separators=(",", ":"))


def open_payload() -> str:
    """모델이 **못 닫는** 것 — 선언이 아니라 계산에서 나온 목록이다."""
    return json.dumps([list(q) for q in sg_grind.open_questions()],
                      ensure_ascii=False, separators=(",", ":"))


def console_html() -> str:
    """3D 밑에 서는 확대도 콘솔 — 유닛 선택·분해·단면·단계·순환 띠·부품표."""
    return """
  <section class="sg-cu" id="sg-cu" aria-label="SG-301 연마 작동 확대도">
    <div class="sg-cu-head">
      <div class="viz-controls" role="tablist" aria-label="유닛 선택" id="sg-cu-tabs"></div>
      <span class="viz-badge tabular-nums" id="sg-cu-sheet"></span>
    </div>
    <div class="viz-controls sg-cu-controls">
      <label class="form-label" for="sg-cu-explode">분해 <span class="tabular-nums" id="sg-cu-explode-value">0%</span>
        <input class="form-range" id="sg-cu-explode" type="range" min="0" max="100" step="1" value="0">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="sg-cu-cut" type="checkbox">
        <span class="form-check-label">단면</span></label>
      <label class="form-label" for="sg-cu-cut-at">절단 위치 <span class="tabular-nums" id="sg-cu-cut-value">50%</span>
        <input class="form-range" id="sg-cu-cut-at" type="range" min="0" max="100" step="1" value="50">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="sg-cu-spin" type="checkbox" checked>
        <span class="form-check-label">스핀들 회전</span></label>
      <button class="btn" id="sg-cu-prev" type="button">◀ 이전 단계</button>
      <button class="btn btn-primary" id="sg-cu-play" type="button">작동 재생</button>
      <button class="btn" id="sg-cu-next" type="button">다음 단계 ▶</button>
      <button class="btn" id="sg-cu-fit" type="button">시점 맞춤</button>
    </div>
    <div class="sg-cu-step" id="sg-cu-step" aria-live="polite"></div>
    <div class="card sg-cu-cycle">
      <div class="sg-cu-cycle-head">
        <h3 class="text-small">한 장의 연마 순환 — 장변과 단변은 <b>겹치지 않는다</b></h3>
        <span class="text-small text-muted tabular-nums" id="sg-cu-cycle-sum"></span>
      </div>
      <div class="sg-cu-band" id="sg-cu-band" role="img" aria-label="연마 순환 상 배치"></div>
      <p class="text-small text-muted" id="sg-cu-cycle-note"></p>
    </div>
    <div class="card sg-cu-open">
      <h3 class="text-small">이 해석이 못 닫는 것 <span class="text-muted tabular-nums" id="sg-cu-open-count"></span></h3>
      <dl class="sg-cu-open-list" id="sg-cu-open"></dl>
    </div>
    <div class="card jb-detail" id="jb-detail" aria-live="polite">형상을 누르면 그 부품의 품번과 역할이 여기에 나옵니다.</div>
    <div class="sg-cu-grid">
      <div class="card sg-cu-parts">
        <h3 class="text-small">부품 구성 <span class="text-muted" id="sg-cu-count"></span></h3>
        <div class="table-responsive"><table class="table table-sm"><thead>
          <tr><th>부품</th><th>수량</th><th>규격</th><th>재질</th></tr>
        </thead><tbody id="sg-cu-rows"></tbody></table></div>
        <p class="text-small text-muted">행을 누르면 그 부품만 남기고 시점이 붙습니다. 형상을 눌러도 같습니다.</p>
      </div>
      <div class="card sg-cu-side">
        <h3 class="text-small">작동 원리</h3>
        <ol class="sg-cu-steps" id="sg-cu-principle"></ol>
        <h3 class="text-small sg-cu-h2">연마가 푸는 수</h3>
        <div class="table-responsive"><table class="table table-sm"><tbody id="sg-cu-spec"></tbody></table></div>
      </div>
    </div>
  </section>
"""


def console_css() -> str:
    return """
  .sg-cu { display: flex; flex-direction: column; gap: 10px; }
  .sg-cu-head { display: flex; flex-wrap: wrap; align-items: center;
    justify-content: space-between; gap: 8px; }
  .sg-cu-controls { align-items: end; }
  .sg-cu-controls .form-label { flex: 0 1 210px; }
  .sg-cu-step { padding: 8px 12px; border-radius: var(--radius-lg);
    background: var(--muted); font-size: var(--font-size-normal); }
  .sg-cu-step b { color: var(--primary); }
  .sg-cu-cycle-head { display: flex; flex-wrap: wrap; align-items: baseline;
    justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .sg-cu-band { display: flex; width: 100%; height: 46px; overflow: hidden;
    border-radius: var(--radius-sm); }
  .sg-cu-band span { display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 1px; min-width: 0; overflow: hidden;
    border-right: 1px solid var(--background); font-size: var(--font-size-small);
    line-height: 1.15; white-space: nowrap; }
  .sg-cu-band span:last-child { border-right: 0; }
  .sg-cu-band b { font-weight: var(--font-weight-medium); }
  .sg-cu-band .sg-p-long { background: var(--accent); color: var(--accent-foreground); }
  .sg-cu-band .sg-p-short { background: var(--primary); color: var(--primary-foreground); }
  .sg-cu-band .sg-p-idle { background: var(--muted); color: var(--muted-foreground); }
  .sg-cu-band .is-now { outline: 2px solid var(--foreground); outline-offset: -2px; }
  .sg-cu-grid { display: grid; gap: 10px;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); }
  .sg-cu-parts tbody tr { cursor: var(--cursor-interaction, pointer); }
  .sg-cu-parts tbody tr:hover { background: var(--muted); }
  .sg-cu-parts tbody tr.is-on { background: var(--accent); color: var(--accent-foreground); }
  .sg-cu-steps { margin: 0; padding-left: 18px; display: flex;
    flex-direction: column; gap: 6px; font-size: var(--font-size-small); }
  .sg-cu-steps li.is-on { font-weight: var(--font-weight-medium); color: var(--primary); }
  .sg-cu-h2 { margin-top: 12px; }
  .sg-cu-open { border-left: 3px solid var(--destructive); }
  .sg-cu-open-list { margin: 8px 0 0; display: flex; flex-direction: column; gap: 8px;
    font-size: var(--font-size-small); }
  .sg-cu-open-list dt { font-weight: var(--font-weight-medium); color: var(--destructive); }
  .sg-cu-open-list dd { margin: 2px 0 0; color: var(--muted-foreground); }
"""


def scene_script() -> str:
    """부품을 실제로 그리는 모듈 — 통합 설계도의 3D 연장을 쓴다."""
    g = sg_grind
    poly = json.dumps({
        "polyBefore": [list(p) for p in g.edge_outline_before()],
        "polyAfter": [list(p) for p in g.edge_outline_after()],
        "polyRemoved": [list(p) for p in g.removed_outline()],
        "polyWheel": [list(p) for p in g.wheel_groove_outline()],
        "polySealG": [list(p) for p in g.sealant_outline_glass_face()],
        "polySealB": [list(p) for p in g.sealant_outline_back_face()],
    }, separators=(",", ":"))
    return f"""<script>
/* SG-301 연마 작동 확대도 — tools/build_sg_closeup.py 가 붙인다.
   형상은 `sg_grind.py` 의 부품 목록과 단면 다각형에서 나오고, 그리는 연장은
   통합 설계도가 `__pvScene.kit` 으로 내준 것이라 재질·조명이 플랜트와 같다. */
(function () {{
  /* 원본 3D 는 `<script type="module">` 이라 이 고전 스크립트보다 **뒤에** 돈다. */
  var tries = 0;
  (function wait() {{
    var r = document.getElementById('jb-removal-operation');
    if (r && r.__pvScene && r.__pvScene.kit) return start(r.__pvScene);
    if (tries++ < 600) requestAnimationFrame(wait);
  }})();
  function start(S) {{
  var K = S.kit, UNITS = {unit_payload()}, CYCLE = {cycle_payload()},
      SPEC = {spec_payload()}, POLY = {poly}, OPEN = {open_payload()},
      PITCH = {json.dumps(sg_grind.ROW_PITCH_MM, separators=(",", ":"))};
  var MM = 0.001;                                   // 모델은 mm, 씬은 m
  var LONG_FEED = {g.long_feed_mm_s()}, SHORT_FEED = {g.short_feed_mm_s()},
      PANEL_W = {campaign.PANEL_WIDTH_MM}, PANEL_L = {campaign.PANEL_LENGTH_MM},
      RPM = {g.SPINDLE_RPM}, MAG = {g.CONTACT_MAG}, GRIT = {g.GRIT_UM};
  var chrome = K.M.steel.clone(); chrome.metalness = .62; chrome.roughness = .26;
  var ghost = K.M.aluminum.clone(); ghost.transparent = !0; ghost.opacity = .38;
  ghost.depthWrite = !1;
  /* 집진 후드는 휠을 통째로 감싼다 — 막힌 대로 그리면 이 도면이 보여 줄 것이
     가려진다. 형상은 그대로 두고 살만 비춘다. */
  var shroud = K.M.dark.clone(); shroud.transparent = !0; shroud.opacity = .22;
  shroud.depthWrite = !1;
  var MAT = {{ steel: K.M.steel, dark: K.M.dark, orange: K.M.orange,
    rubber: K.M.rubber, frame: K.M.frame, aluminum: K.M.aluminum,
    chrome: chrome, ghost: ghost, shroud: shroud }};
  var group = new S.Group(); S.scene.add(group);
  var built = {{}}, active = null, step = 0, playing = false, focus = null, spin = 0;

  /* 단면 다각형을 x 축으로 스윕한다 — 접촉부는 배율만 곱한다 */
  function sweep(sec, len, mat, mag) {{
    var n = sec.length, pos = [], ix = [], j, k, c, s;
    for (s = 0; s < 2; s += 1) for (j = 0; j < n; j += 1)
      pos.push((s ? .5 : -.5) * len * MM, sec[j][1] * mag * MM, sec[j][0] * mag * MM);
    for (j = 0; j < n; j += 1) {{ k = (j + 1) % n; ix.push(j, k, n + k, j, n + k, n + j); }}
    for (c = 2; c < n; c += 1) {{ ix.push(0, c, c - 1); ix.push(n, n + c - 1, n + c); }}
    var geo = new K.Geo();
    geo.setAttribute('position', new K.Attr(new Float32Array(pos), 3));
    geo.setIndex(ix); geo.computeVertexNormals();
    var m = new K.Mesh(geo, mat); m.castShadow = !0; m.receiveShadow = !0; return m;
  }}

  function placements(p) {{                          /* 수량을 실제 자리로 편다 */
    var out = [], m = p.mirror.join(','), i;
    if (p.shape === 'cylrow' || p.shape === 'gritrow') {{   /* 줄지어 놓는 것 */
      var pitch = PITCH[p.key] || 100;               /* 간격도 모델이 정한다 */
      for (i = 0; i < p.qty; i += 1)
        out.push([p.pos[0] + (i - (p.qty - 1) / 2) * pitch, p.pos[1], p.pos[2]]);
      return out;
    }}
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
        if (POLY[p.shape]) mesh = sweep(POLY[p.shape], p.size[0], mat, u.mag);
        else if (p.shape === 'cyl' || p.shape === 'cylrow') {{
          var r = p.size[0] * MM / 2, h = (p.shape === 'cylrow' ? p.size[1] : p.size[1]) * MM;
          mesh = new K.Mesh(new K.Cyl(r, r, h, 30), mat);
          if (p.axis === 'x') mesh.rotation.z = Math.PI / 2;
          else if (p.axis === 'z') mesh.rotation.x = Math.PI / 2;
        }} else if (p.shape === 'gritrow') {{
          mesh = new K.Mesh(new K.Box(p.size[0] * MM, p.size[1] * MM, p.size[2] * MM), mat);
          mesh.rotation.set(.6, .5, .3);
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

  /* 작동원리 — 단계마다 부품이 실제로 움직인다 */
  var SPINNERS = {{ lwhl: 1, swhl: 1, larb: 1, sarb: 1 }};
  function pose(u, t) {{
    var grp = built[u.key]; if (!grp) return;
    var ex = exVal();
    grp.children.forEach(function (m) {{
      var k = m.userData.part, h = m.userData.home, d = new S.Vector3(), side = m.userData.side;
      /* 자리 변화는 전부 **mm 로 셈해서 마지막에 m 로 바꾼다** — 씬은 m 다. */
      if (u.key === 'long') {{
        /* ② 인피드 — 헤드가 변 쪽으로 붙는다 · ③ 유리가 지나간다 */
        var infeed = Math.max(0, Math.min(1, t - 1)) * 60;
        if (k !== 'glass' && k !== 'roll') d.z = -side * infeed;
        if (k === 'glass') {{
          /* 화면에 세운 조각이 1,400 이므로 그 절반씩 왕복한다 — 실제로는
             {campaign.PANEL_LENGTH_MM:,.0f} mm 가 {g.long_feed_mm_s():.0f} mm/s 로 지나간다. */
          var run = Math.max(0, Math.min(1, (t - 2) / 2));
          d.x = (run * 2 - 1) * 700;
        }}
      }} else if (u.key === 'short') {{
        /* ① 유리 정지 · ② 하강·인피드 · ③ 폭을 건넌다 */
        var down = Math.max(0, Math.min(1, t - 1));
        var cross = Math.max(0, Math.min(1, (t - 2) / 2));
        var head = (k === 'car' || k === 'zsl' || k === 'hood'
                    || k === 'smot' || k === 'shsg' || k === 'sarb' || k === 'swhl');
        if (head) {{ d.x = down * 90; d.z = (cross * 2 - 1) * PANEL_W / 2; }}
        if (k === 'glass') d.x = t < 1 ? (1 - t) * 520 : 0;
      }} else {{
        /* 접촉부 — 홈이 다가와 물고, 살이 떨어지고, 아리스가 선다.
           이 유닛은 배율이 걸려 있으므로 이동도 같은 배율로 잰다. */
        var close = Math.max(0, Math.min(1, t));
        var eat = Math.max(0, Math.min(1, t - 2));
        if (k === 'rim' || k === 'grit') d.z = (1 - close) * 13 * MAG;
        if (k === 'cutaway') {{ d.y = eat * 9.5 * MAG; d.z = -eat * 3 * MAG; }}
        /* 연마 전·후 단면을 겹쳐 그리면 같은 자리에서 서로를 가린다 —
           한 번에 하나만 세운다. */
        m.visible = (k === 'done') ? t >= 2.2
          : (k === 'edge') ? t < 2.2 : (k === 'cutaway') ? eat < .98 : true;
      }}
      d.multiplyScalar(MM);
      m.position.copy(h).add(d).add(m.userData.blow.clone().multiplyScalar(ex));
      if (SPINNERS[k]) m.rotation.y = spin;
    }});
  }}

  /* 모델 글은 **강조** 를 마크다운으로 쓴다 — 화면에서는 태그로 바꾼다. */
  function md(s) {{ return String(s).replace(/\\*\\*(.+?)\\*\\*/g, '<b>$1</b>'); }}
  function exVal() {{ return Number(el('sg-cu-explode').value) / 100; }}
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
    /* 방향은 모델(`sg_grind.VIEW_DIR`)이 정한다 — 접촉부는 단면이라 스윕 축을
       따라 봐야 옆모습이 나온다. */
    var v = u.view || [.6, .8, 1], n = Math.hypot(v[0], v[1], v[2]);
    S.camera.position.set(v[0] / n * d, v[1] / n * d, v[2] / n * d);
    S.controls.target.set(0, tall * .12, 0); S.controls.update();
  }}

  /* 순환 띠 — 다섯 상의 자리와 길이가 모델에서 그대로 온다 */
  function band() {{
    el('sg-cu-band').innerHTML = CYCLE.phases.map(function (p, i) {{
      var cls = p.heads === 0 ? 'sg-p-idle'
        : (p.phase === '장변 통과' ? 'sg-p-long' : 'sg-p-short');
      return '<span class="' + cls + '" data-i="' + i + '" style="flex:' + p.dur + ' 1 0">'
        + '<b>' + p.phase + '</b><span>' + p.dur.toFixed(1) + ' s'
        + (p.heads ? ' · 헤드 ' + p.heads : '') + '</span></span>';
    }}).join('');
    el('sg-cu-cycle-sum').textContent = '합 ' + CYCLE.total.toFixed(2) + ' s'
      + ' · AFR 정반 ' + CYCLE.afr.toFixed(2) + ' s · 여유 ' + CYCLE.slack.toFixed(2) + ' s';
    el('sg-cu-cycle-note').innerHTML = md(
      '장변은 유리가 **움직여야** 갈리고 단변은 유리가 **서 있어야** 훑을 수 있다 — '
      + '운동 상태가 배타적이라 두 연마는 **동시에 못 한다.** 그래서 점유가 더해져 '
      + '**' + CYCLE.total.toFixed(2) + ' s** 다. 동시라면 ' + CYCLE.simultaneous.toFixed(2)
      + ' s 였을 것이고, 순차로 푸는 값이 **' + CYCLE.cost.toFixed(2) + ' s** 다. '
      + 'AFR 정반 점유 안에 **' + CYCLE.slack.toFixed(2) + ' s** 가 남으므로 택트는 안 깎인다.');
  }}

  function bandMark() {{
    var want = active && active.key === 'long' ? '장변 통과'
      : active && active.key === 'short' ? (step < 3 ? '앞단변' : '뒷단변') : null;
    [].forEach.call(el('sg-cu-band').children, function (s, i) {{
      s.classList.toggle('is-now', !!want && CYCLE.phases[i].phase === want
        && (want !== '앞단변' || i === 0) && (want !== '뒷단변' || i === 4));
    }});
  }}

  function show(key) {{
    active = UNITS.filter(function (u) {{ return u.key === key; }})[0];
    UNITS.forEach(function (u) {{ built[u.key].visible = u.key === key; }});
    el('sg-cu-sheet').textContent = active.sheet;
    el('sg-cu-count').textContent = '· ' + active.parts.length + ' 종 '
      + active.parts.reduce(function (a, p) {{ return a + p.qty; }}, 0) + ' 개';
    el('sg-cu-rows').innerHTML = active.parts.map(function (p) {{
      return '<tr data-part="' + p.key + '"><td>' + p.name + '</td><td class="tabular-nums">'
        + p.qty + '</td><td>' + md(p.spec || '—') + '</td><td>' + p.material + '</td></tr>';
    }}).join('');
    el('sg-cu-principle').innerHTML = active.principle.map(function (s) {{
      return '<li><b>' + s[0] + '</b> ' + md(s[1]) + '</li>';
    }}).join('');
    el('sg-cu-spec').innerHTML = (SPEC[key] || []).map(function (r) {{
      return '<tr><th scope="row">' + r[0] + '</th><td>' + md(r[1]) + '</td></tr>';
    }}).join('');
    [].forEach.call(el('sg-cu-tabs').children, function (b) {{
      b.classList.toggle('btn-primary', b.dataset.unit === key);
      b.setAttribute('aria-selected', String(b.dataset.unit === key));
    }});
    step = 0; focus = null; fit(active); render();
  }}

  function render() {{
    if (!active) return;
    pose(active, step);
    var p = active.principle[Math.min(active.principle.length - 1, Math.floor(step))];
    el('sg-cu-step').innerHTML = '<b>' + p[0] + '</b> ' + md(p[1]);
    [].forEach.call(el('sg-cu-principle').children, function (li, i) {{
      li.classList.toggle('is-on', i === Math.floor(step));
    }});
    [].forEach.call(el('sg-cu-rows').children, function (tr) {{
      tr.classList.toggle('is-on', tr.dataset.part === focus);
    }});
    if (focus) built[active.key].children.forEach(function (m) {{
      m.visible = m.userData.part === focus;
    }});
    el('sg-cu-explode-value').textContent = Math.round(exVal() * 100) + '%';
    el('sg-cu-cut-value').textContent = el('sg-cu-cut-at').value + '%';
    bandMark();
  }}

  /* 단면 — 씬 전체에 잘라 내는 평면 하나를 건다 */
  var plane = new S.Plane(new S.Vector3(-1, 0, 0), 0);
  function cutUpdate() {{
    var on = el('sg-cu-cut').checked;
    S.renderer.clippingPlanes = on ? [plane] : [];
    S.renderer.localClippingEnabled = on;
    if (active) plane.constant = (Number(el('sg-cu-cut-at').value) / 100 - .5)
      * active.envelope[0] * MM;
  }}

  UNITS.forEach(function (u) {{ built[u.key] = build(u); }});
  el('sg-cu-tabs').innerHTML = UNITS.map(function (u) {{
    return '<button class="btn" type="button" role="tab" data-unit="' + u.key + '">'
      + u.name.split(' (')[0] + '</button>';
  }}).join('');
  el('sg-cu-tabs').addEventListener('click', function (e) {{
    var b = e.target.closest('[data-unit]'); if (b) show(b.dataset.unit);
  }});
  el('sg-cu-rows').addEventListener('click', function (e) {{
    var tr = e.target.closest('[data-part]'); if (!tr) return;
    focus = focus === tr.dataset.part ? null : tr.dataset.part;
    if (!focus) built[active.key].children.forEach(function (m) {{ m.visible = true; }});
    render();
  }});
  el('sg-cu-explode').addEventListener('input', render);
  el('sg-cu-cut').addEventListener('change', cutUpdate);
  el('sg-cu-cut-at').addEventListener('input', cutUpdate);
  el('sg-cu-prev').addEventListener('click', function () {{
    playing = false; step = Math.max(0, Math.floor(step) - 1); render(); }});
  el('sg-cu-next').addEventListener('click', function () {{
    playing = false;
    step = Math.min(active.principle.length - 1, Math.floor(step) + 1); render(); }});
  el('sg-cu-play').addEventListener('click', function () {{
    playing = !playing; if (playing && step >= active.principle.length - 1) step = 0;
    el('sg-cu-play').textContent = playing ? '일시정지' : '작동 재생'; }});
  el('sg-cu-fit').addEventListener('click', function () {{ if (active) fit(active); }});

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
    if (el('sg-cu-spin').checked) spin += dt * (RPM / 60) * 2 * Math.PI / 60;
    if (playing) {{
      step += dt * .55;
      if (step >= active.principle.length - 1) {{
        step = active.principle.length - 1; playing = false;
        el('sg-cu-play').textContent = '작동 재생';
      }}
    }}
    if (playing || el('sg-cu-spin').checked) render();
    requestAnimationFrame(tick);
  }}
  /* 원본 공정시계와 자동추적은 이 화면에서 방해만 된다. */
  var auto = document.getElementById('pv-auto-camera');
  if (auto && auto.checked) {{ auto.checked = !1; auto.dispatchEvent(new Event('change')); }}
  var play = document.getElementById('jb-play');
  if (play && /일시정지/.test(play.textContent)) play.click();
  el('sg-cu-open-count').textContent = '· ' + OPEN.length + ' 건';
  el('sg-cu-open').innerHTML = OPEN.map(function (q) {{
    return '<dt>' + md(q[0]) + '</dt><dd>' + md(q[1]) + '</dd>';
  }}).join('');
  band(); show(UNITS[0].key); cutUpdate(); requestAnimationFrame(tick);
  window.__pvSgCloseup = {{ units: UNITS.length, cycle: CYCLE,
    feed: {{ long: LONG_FEED, short: SHORT_FEED }},
    panel: {{ w: PANEL_W, l: PANEL_L }}, mag: MAG, grit: GRIT,
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
    g = sg_grind
    t = PLANT.read_text(encoding="utf-8")
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>SG-301 연마 작동 확대도</title>\n"
              '<meta name="description" content="AFR-101 이 프레임을 뜯어낸 유리 변을 '
              'SG-301 이 다이아몬드 형상휠로 다듬는 과정을 부품 단위로 확대한 3D 도면 — '
              '고정 2대가 통과 유리를 가는 장변 헤드, 폭 1,400 을 건너는 단변 횡행 헤드, '
              '그리고 20배로 키운 휠–유리 접촉부. 순환 띠가 장변과 단변이 왜 동시가 아닌지를 '
              '보여 준다.">', "제목")
    t = _once(t, '<h2 id="pv-v22-title">태양광 패널 전처리 통합 플랜트</h2>',
              '<h2 id="pv-v22-title">SG-301 연마 작동 확대도 — 장변 통과 · 단변 횡행 · '
              '휠–유리 접촉부</h2>', "표제")
    t = _once(t, '<span class="viz-badge">124.03 s TRACE</span>',
              f'<span class="viz-badge">EDGE GRINDING · {g.occupancy_s()} s</span>', "배지")
    rev = t.split("DRAWING_REVISION = '")[1].split("'")[0]
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · SG-301 연마 작동 확대도 · ENGINEERING BASE {rev}",
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
    t = _once(t, "</body>", scene_script() + "</body>", "연마 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- SG-301 연마 작동 확대도: tools/build_sg_closeup.py 가 "
              "통합 설계도에서 만든다. 손으로 고치지 않는다.\n"
              "     형상·수치는 src/pv_preprocess/sg_grind.py 에서 온다 — 화면에 손으로 쓴 "
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
