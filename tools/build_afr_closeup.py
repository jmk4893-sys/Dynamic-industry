# -*- coding: utf-8 -*-
"""AFR-101 두 핵심 유닛의 **부품 확대도** — 통합 설계도에서 파생한다.

플랜트 3D 는 축척이 50 m 다. 거기서 실린더는 원기둥 하나고 LM 캐리지는 상자
하나여야 한다 — 그 축척에서 글랜드와 볼 순환로를 그리면 화면만 무거워진다.
그래서 "실제로 어떻게 생겼고 어떻게 움직이는가" 는 부품표 글자에만 있었다.

이 파생본은 그 두 유닛을 **부품 단위로 확대해서** 보여 준다.

* **형상** — `afr_units.py` 의 부품 목록을 통합 설계도의 3D 연장(`__pvScene.kit`)
  으로 그린다. 같은 재질·같은 조명이라 플랜트와 같은 물건으로 보인다. 35 급
  레일은 단면 다각형을 스윕해서 허리와 볼 홈까지 낸다.
* **구성** — 분해 슬라이더가 부품마다 정해진 방향으로 뽑아 낸다. 리브 격자와
  실린더 포켓은 컷어웨이로 갈라 본다.
* **작동원리** — 유닛마다 5 단계다. 단계를 넘기면 로드가 나오고 쇠막대가 밀고
  스토퍼가 받는다 — 글이 아니라 형상이 움직인다.
* **사양** — 보어·행정·작동압·접촉압은 전부 `afr.py` 가 유도한 값이고, 재질·
  수량·공차는 통합 설계도 부품표 그대로다. 카탈로그 계획값(레일 단면·스터드)은
  그렇게 밝혀 둔다.

원본 파일을 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 하고 아니면 멈춘다.

    PYTHONPATH=src python tools/build_afr_closeup.py

멱등이다. `tests/test_pv_afr.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import afr, afr_units, campaign, frames  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-afr-closeup.html"

#: 플랜트 콘솔에서 이 파생본이 쓰지 않는 것 — 형상만 보는 화면이다.
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
    for u in afr_units.units():
        out.append({
            "key": u.key, "name": u.name, "sheet": u.sheet,
            "envelope": list(u.envelope_mm), "viewR": u.view_r_mm,
            "principle": [list(s) for s in u.principle],
            "parts": [{
                "key": p.key, "name": p.name, "qty": p.qty, "shape": p.shape,
                "size": list(p.size), "pos": list(p.pos), "axis": p.axis,
                "mirror": list(p.mirror), "color": p.color, "material": p.material,
                "role": p.role, "spec": p.spec, "catalog": p.catalog,
                "explode": list(p.explode), "flip": bool(p.flip),
            } for p in u.parts],
        })
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def console_html() -> str:
    """3D 밑에 서는 부품 확대도 콘솔 — 유닛 선택·분해·단면·단계·부품표."""
    return """
  <section class="afr-cu" id="afr-cu" aria-label="AFR-101 부품 확대도">
    <div class="afr-cu-head">
      <div class="viz-controls" role="tablist" aria-label="유닛 선택" id="afr-cu-tabs"></div>
      <span class="viz-badge tabular-nums" id="afr-cu-sheet"></span>
    </div>
    <div class="viz-controls afr-cu-controls">
      <label class="form-label" for="afr-cu-explode">분해 <span class="tabular-nums" id="afr-cu-explode-value">0%</span>
        <input class="form-range" id="afr-cu-explode" type="range" min="0" max="100" step="1" value="0">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="afr-cu-cut" type="checkbox">
        <span class="form-check-label">단면</span></label>
      <label class="form-label" for="afr-cu-cut-at">절단 위치 <span class="tabular-nums" id="afr-cu-cut-value">50%</span>
        <input class="form-range" id="afr-cu-cut-at" type="range" min="0" max="100" step="1" value="50">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="afr-cu-labels" type="checkbox" checked>
        <span class="form-check-label">부품 라벨</span></label>
      <button class="btn" id="afr-cu-prev" type="button">◀ 이전 단계</button>
      <button class="btn btn-primary" id="afr-cu-play" type="button">작동 재생</button>
      <button class="btn" id="afr-cu-next" type="button">다음 단계 ▶</button>
      <button class="btn" id="afr-cu-fit" type="button">시점 맞춤</button>
    </div>
    <div class="afr-cu-step" id="afr-cu-step" aria-live="polite"></div>
    <div class="afr-cu-grid">
      <div class="card afr-cu-parts">
        <h3 class="text-small">부품 구성 <span class="text-muted" id="afr-cu-count"></span></h3>
        <div class="table-responsive"><table class="table table-sm"><thead>
          <tr><th>부품</th><th>수량</th><th>치수 (mm)</th><th>재질</th></tr>
        </thead><tbody id="afr-cu-rows"></tbody></table></div>
        <p class="text-small text-muted">행을 누르면 그 부품만 남기고 시점이 붙습니다. 형상을 눌러도 같습니다.</p>
      </div>
      <div class="card afr-cu-side">
        <h3 class="text-small">작동 원리</h3>
        <ol class="afr-cu-steps" id="afr-cu-principle"></ol>
        <h3 class="text-small afr-cu-h2">사양</h3>
        <div class="table-responsive"><table class="table table-sm"><tbody id="afr-cu-spec"></tbody></table></div>
      </div>
    </div>
  </section>
"""


def console_css() -> str:
    return """
  .afr-cu { display: flex; flex-direction: column; gap: 10px; }
  .afr-cu-head { display: flex; flex-wrap: wrap; align-items: center;
    justify-content: space-between; gap: 8px; }
  .afr-cu-controls { align-items: end; }
  .afr-cu-controls .form-label { flex: 0 1 210px; }
  .afr-cu-step { padding: 8px 12px; border-radius: var(--radius-lg);
    background: var(--muted); font-size: var(--font-size-normal); }
  .afr-cu-step b { color: var(--primary); }
  .afr-cu-grid { display: grid; gap: 10px;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); }
  .afr-cu-parts tbody tr { cursor: var(--cursor-interaction, pointer); }
  .afr-cu-parts tbody tr:hover { background: var(--muted); }
  .afr-cu-parts tbody tr.is-on { background: var(--accent); color: var(--accent-foreground); }
  .afr-cu-steps { margin: 0; padding-left: 18px; display: flex;
    flex-direction: column; gap: 6px; font-size: var(--font-size-small); }
  .afr-cu-steps li.is-on { font-weight: var(--font-weight-medium); color: var(--primary); }
  .afr-cu-h2 { margin-top: 12px; }
"""


def scene_script() -> str:
    """부품을 실제로 그리는 모듈 — 통합 설계도의 3D 연장을 쓴다."""
    rail = json.dumps([list(p) for p in afr_units.rail_outline()], separators=(",", ":"))
    prof = frames.profile()
    fr = json.dumps([[round(u - prof["cu_mm"], 3), round(v - prof["cv_mm"], 3)]
                     for u, v in frames.outline()], separators=(",", ":"))
    spec = json.dumps({
        "short": [
            ["보어 / 로드 / 행정", afr.cylinder_spec()],
            ["정반 1매", f"{afr.PLATEN_X_MM} × {afr.PLATEN_Z_MM} × {afr.PLATEN_T_MM} mm · "
                       f"{afr.platen_mass_kg()} kg (통짜 {afr.platen_solid_mass_kg()} kg)"],
            ["포켓 살두께", f"{afr.platen_wall_mm()} mm (최소 {afr.MIN_PLATEN_WALL_MM})"],
            ["추력 / 작동압", f"{afr.required_push_kn()} kN · {afr.working_pressure_bar():.0f} bar "
                          f"(릴리프 {afr.HPU_RELIEF_BAR:.0f})"],
            ["쇠막대", f"{afr.BAR_W_MM} × {afr.bar_h_mm()} × {afr.bar_length_mm():,} mm · "
                    f"{afr.bar_mass_kg()} kg"],
            ["막대 굽힘 / 처짐", f"{afr.bar_stress_mpa()} MPa (허용 {afr.STEEL_ALLOW_MPA:.0f}) · "
                            f"{afr.bar_sag_mm()} mm (한도 {afr.bar_sag_limit_mm()})"],
            ["밀어내기 / 잔여행정", f"{afr.push_travel_mm()} mm · 잔여 {afr.stroke_spare_mm()} mm"],
        ],
        "long": [
            ["레일 / 블록", f"35급 {afr_units.RAIL_W_MM:.0f} × {afr_units.RAIL_H_MM:.0f} · "
                        f"블록 {afr_units.BLOCKS_PER_CARRIAGE} 개 @{afr_units.BLOCK_SPAN_MM:.0f}"],
            ["주행", f"{afr.LM_STROKE_MM:,} mm · {afr.LM_SPEED_MM_S:.0f} mm/s "
                  f"({afr.lm_travel_time_s()} s)"],
            ["롤러", f"Ø{afr.roller_d_mm()} × {afr.roller_h_mm()} × "
                  f"{afr.rollers_per_carriage()} 개 @{afr_units.ROLLER_PITCH_MM:.0f}"],
            ["홈 / 돌출", f"{afr.GROOVE_H_MM} × {afr.GROOVE_D_MM} mm · "
                      f"밖으로 {afr.roller_protrusion_mm()} mm"],
            ["접촉압", f"{afr.roller_contact_mpa()} MPa (허용 {afr.roller_allow_mpa()} · "
                    f"구름항복 {afr.rolling_yield_mpa()})"],
            ["인발력 / 자유길이", f"{frames.PEEL_FORCE_N:.0f} N/캐리지 · 롤러 반경 "
                            f"{afr.roller_free_length_mm()} mm"],
            ["캐리지", f"한 변 {afr.CARRIAGE_PER_SIDE} 대 · 두 변 "
                    f"{afr.CARRIAGE_PER_SIDE * 2} 대 동기"],
        ],
    }, ensure_ascii=False, separators=(",", ":"))
    return f"""<script>
/* AFR-101 부품 확대도 — tools/build_afr_closeup.py 가 붙인다.
   형상은 `afr_units.py` 의 부품 목록에서 나오고, 그리는 연장은 통합 설계도가
   `__pvScene.kit` 으로 내준 것이라 재질·조명이 플랜트와 같다. */
(function () {{
  /* 원본 3D 는 `<script type="module">` 이라 이 고전 스크립트보다 **뒤에** 돈다.
     그래서 장면이 설 때까지 기다린다 — 바로 읽으면 늘 없다. */
  var tries = 0;
  (function wait() {{
    var r = document.getElementById('jb-removal-operation');
    if (r && r.__pvScene && r.__pvScene.kit) return start(r.__pvScene);
    if (tries++ < 600) requestAnimationFrame(wait);
  }})();
  function start(S) {{
  var K = S.kit, UNITS = {unit_payload()}, RAIL = {rail}, FRAME = {fr}, SPEC = {spec};
  var MM = 0.001;                                   // 모델은 mm, 씬은 m
  var chrome = K.M.steel.clone(); chrome.metalness = .62; chrome.roughness = .26;
  var cut = K.M.green.clone(); cut.transparent = !0; cut.opacity = .15;
  cut.depthWrite = !1;
  var ghost = K.M.aluminum.clone(); ghost.transparent = !0; ghost.opacity = .5;
  var MAT = {{ steel: K.M.steel, dark: K.M.dark, orange: K.M.orange,
    rubber: K.M.rubber, frame: K.M.frame, aluminum: K.M.aluminum,
    chrome: chrome, cut: cut, ghost: ghost }};
  var group = new S.Group(); S.scene.add(group);
  var built = {{}}, active = null, step = 0, playing = false, focus = null;

  function sweep(sec, len, mat, axis, flip) {{      /* 단면 다각형을 스윕한다 */
    var n = sec.length, pos = [], ix = [];
    for (var s = 0; s < 2; s += 1) for (var j = 0; j < n; j += 1) {{
      var a = (s ? .5 : -.5) * len * MM, v = sec[j][1] * MM,
          u = sec[j][0] * MM * (flip ? -1 : 1);
      if (axis === 'z') pos.push(u, v, a); else pos.push(a, v, u);
    }}
    for (var j2 = 0; j2 < n; j2 += 1) {{
      var k = (j2 + 1) % n;
      ix.push(j2, k, n + k, j2, n + k, n + j2);
    }}
    for (var c = 2; c < n; c += 1) {{ ix.push(0, c, c - 1); ix.push(n, n + c - 1, n + c); }}
    var g = new K.Geo();
    g.setAttribute('position', new K.Attr(new Float32Array(pos), 3));
    g.setIndex(ix); g.computeVertexNormals();
    var m = new K.Mesh(g, mat); m.castShadow = !0; m.receiveShadow = !0; return m;
  }}

  function placements(p) {{                          /* 수량을 실제 자리로 편다 */
    var out = [], m = p.mirror.join(','), i;
    if (m === 'y') out = [[0, 1, 0], [0, -1, 0]];
    else if (m === 'z') out = [[0, 0, 1], [0, 0, -1]];
    else if (m === 'x') out = [[1, 0, 0], [-1, 0, 0]];
    else if (m === 'z,x') out = [[1, 0, 1], [1, 0, -1], [-1, 0, 1], [-1, 0, -1]];
    else out = [[1, 1, 1]];
    var pts = [];
    if (m === 'x2') {{                               /* 블록 양끝 엔드캡 */
      for (i = 0; i < 4; i += 1) pts.push([p.pos[0] * (i < 2 ? 1 : -1)
        * (i % 2 ? -1 : 1), p.pos[1], p.pos[2]]);
      return pts;
    }}
    if (m === 'row') {{                              /* 롤러 열 */
      for (i = 0; i < p.qty; i += 1)
        pts.push([p.pos[0] + (i - (p.qty - 1) / 2) * {afr_units.ROLLER_PITCH_MM},
                  p.pos[1], p.pos[2]]);
      return pts;
    }}
    if (p.key === 'ribz') {{
      for (i = 0; i < p.qty; i += 1)
        pts.push([0, 0, (i - (p.qty - 1) / 2) * {afr.PLATEN_RIB_PITCH_MM}]);
      return pts;
    }}
    if (p.key === 'ribx') {{
      for (i = 0; i < p.qty; i += 1)
        pts.push([(i - (p.qty - 1) / 2) * {afr.PLATEN_RIB_PITCH_MM}, 0, 0]);
      return pts;
    }}
    for (i = 0; i < out.length; i += 1)
      pts.push([p.pos[0] * out[i][0] || p.pos[0] * (out[i][0] || 1),
                p.pos[1] * (out[i][1] || 1), p.pos[2] * (out[i][2] || 1)]);
    return pts.map(function (q, j) {{
      var s = out[j] || [1, 1, 1];
      return [p.pos[0] * (s[0] || 1), p.pos[1] * (s[1] || 1), p.pos[2] * (s[2] || 1)];
    }});
  }}

  function build(u) {{
    var g = new S.Group(); g.visible = false; group.add(g);
    u.parts.forEach(function (p) {{
      placements(p).forEach(function (at, idx) {{
        var mesh;
        if (p.shape === 'rail') mesh = sweep(RAIL, p.size[2], chrome, 'x');
        else if (p.shape === 'frame') mesh = sweep(FRAME, p.size[2], ghost, p.axis, p.flip);
        else if (p.shape === 'cyl') {{
          var geo = new K.Cyl(p.size[0] * MM / 2, p.size[0] * MM / 2, p.size[1] * MM, 28);
          mesh = new K.Mesh(geo, MAT[p.color] || K.M.steel);
          if (p.axis === 'x') mesh.rotation.z = Math.PI / 2;
          else if (p.axis === 'z') mesh.rotation.x = Math.PI / 2;
        }} else {{
          mesh = new K.Mesh(new K.Box(p.size[0] * MM, p.size[1] * MM, p.size[2] * MM),
                            MAT[p.color] || K.M.steel);
        }}
        mesh.castShadow = !0; mesh.receiveShadow = !0;
        mesh.position.set(at[0] * MM, at[1] * MM, at[2] * MM);
        mesh.userData.home = mesh.position.clone();
        mesh.userData.blow = new S.Vector3(p.explode[0] * MM, p.explode[1] * MM,
                                           p.explode[2] * MM);
        mesh.userData.part = p.key;
        mesh.userData.label = p.name + (p.catalog ? ' (' + p.catalog + ')' : '');
        mesh.userData.note = p.role + (p.spec ? ' · ' + p.spec : '') + ' · ' + p.material;
        if (idx === 0) K.pick.push(mesh);
        g.add(mesh);
      }});
    }});
    return g;
  }}

  /* 작동원리 — 단계마다 부품이 실제로 움직인다 */
  function pose(u, t) {{
    var g = built[u.key]; if (!g) return;
    var push = {afr.push_travel_mm()} * MM, pull = {afr.pull_travel_mm()} * MM,
        reach = {afr.roller_reach_mm()} * MM, travel = {afr.LM_STROKE_MM} * MM;
    g.children.forEach(function (m) {{
      var k = m.userData.part, h = m.userData.home, d = new S.Vector3();
      if (u.key === 'short') {{
        var ex = (k === 'rod' || k === 'clevis' || k === 'nut' || k === 'bar')
          ? push * Math.max(0, Math.min(1, (t - 1) / 2)) : 0;
        if (k === 'stopface' || k === 'stoppad') ex = 0;
        d.set(h.x >= 0 ? ex : -ex, 0, 0);
        if (k === 'skin' || k === 'ribz' || k === 'ribx' || k === 'pocket'
            || k === 'barrel' || k === 'cap' || k === 'gland' || k === 'port')
          d.set(0, t < 1 ? {afr.platen_lift_mm()} * MM * (1 - t) : 0, 0);
      }} else {{
        var enter = Math.max(0, Math.min(1, t)), open = Math.max(0, Math.min(1, t - 2)),
            run = Math.max(0, Math.min(1, t - 3));
        if (k === 'slide' || k === 'head' || k === 'roller' || k === 'stud' || k === 'flange')
          d.set(0, 0, reach * (enter - 1) + pull * open);
        if (k !== 'rail') d.x = travel * run;
      }}
      m.position.copy(h).add(d).add(m.userData.blow.clone().multiplyScalar(exVal()));
    }});
  }}

  /* 모델 글은 **강조** 를 마크다운으로 쓴다 — 화면에서는 태그로 바꾼다. */
  function md(s) {{ return String(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>'); }}
  function exVal() {{ return Number(el('afr-cu-explode').value) / 100; }}
  function el(id) {{ return document.getElementById(id); }}

  function fit(u) {{
    /* 레일은 2.9 m 지만 볼 것은 유닛이다 — 포락선이 아니라 시점 반경으로 잡는다. */
    var r = (u.viewR || Math.max.apply(null, u.envelope)) * MM;
    S.camera.position.set(r * 1.15, r * .78, r * 1.32);
    S.controls.target.set(0, r * .12, 0); S.controls.update();
  }}

  function show(key) {{
    active = UNITS.filter(function (u) {{ return u.key === key; }})[0];
    UNITS.forEach(function (u) {{ built[u.key].visible = u.key === key; }});
    el('afr-cu-sheet').textContent = active.sheet;
    el('afr-cu-count').textContent = '· ' + active.parts.length + ' 종 '
      + active.parts.reduce(function (a, p) {{ return a + p.qty; }}, 0) + ' 개';
    el('afr-cu-rows').innerHTML = active.parts.map(function (p) {{
      return '<tr data-part="' + p.key + '"><td>' + p.name + '</td><td class="tabular-nums">'
        + p.qty + '</td><td class="tabular-nums">' + md(p.spec || '—') + '</td><td>'
        + p.material + '</td></tr>';
    }}).join('');
    el('afr-cu-principle').innerHTML = active.principle.map(function (s) {{
      return '<li><b>' + s[0] + '</b> ' + md(s[1]) + '</li>';
    }}).join('');
    el('afr-cu-spec').innerHTML = (SPEC[key] || []).map(function (r) {{
      return '<tr><th scope="row">' + r[0] + '</th><td>' + r[1] + '</td></tr>';
    }}).join('');
    [].forEach.call(el('afr-cu-tabs').children, function (b) {{
      b.classList.toggle('btn-primary', b.dataset.unit === key);
      b.setAttribute('aria-selected', String(b.dataset.unit === key));
    }});
    step = 0; focus = null; fit(active); render();
  }}

  function render() {{
    if (!active) return;
    pose(active, step);
    var p = active.principle[Math.min(active.principle.length - 1, Math.floor(step))];
    el('afr-cu-step').innerHTML = '<b>' + p[0] + '</b> ' + md(p[1]);
    [].forEach.call(el('afr-cu-principle').children, function (li, i) {{
      li.classList.toggle('is-on', i === Math.floor(step));
    }});
    [].forEach.call(el('afr-cu-rows').children, function (tr) {{
      tr.classList.toggle('is-on', tr.dataset.part === focus);
    }});
    built[active.key].children.forEach(function (m) {{
      m.visible = !focus || m.userData.part === focus;
    }});
    el('afr-cu-explode-value').textContent = Math.round(exVal() * 100) + '%';
    el('afr-cu-cut-value').textContent = el('afr-cu-cut-at').value + '%';
  }}

  /* 단면 — 씬 전체에 잘라 내는 평면 하나를 건다 */
  var plane = new S.Plane(new S.Vector3(-1, 0, 0), 0);
  function cutUpdate() {{
    var on = el('afr-cu-cut').checked;
    S.renderer.clippingPlanes = on ? [plane] : [];
    S.renderer.localClippingEnabled = on;
    if (active) plane.constant = (Number(el('afr-cu-cut-at').value) / 100 - .5)
      * active.envelope[0] * MM;
  }}

  UNITS.forEach(function (u) {{ built[u.key] = build(u); }});
  el('afr-cu-tabs').innerHTML = UNITS.map(function (u) {{
    return '<button class="btn" type="button" role="tab" data-unit="' + u.key + '">'
      + u.name.split(' (')[0] + '</button>';
  }}).join('');
  el('afr-cu-tabs').addEventListener('click', function (e) {{
    var b = e.target.closest('[data-unit]'); if (b) show(b.dataset.unit);
  }});
  el('afr-cu-rows').addEventListener('click', function (e) {{
    var tr = e.target.closest('[data-part]'); if (!tr) return;
    focus = focus === tr.dataset.part ? null : tr.dataset.part; render();
  }});
  el('afr-cu-explode').addEventListener('input', render);
  el('afr-cu-cut').addEventListener('change', cutUpdate);
  el('afr-cu-cut-at').addEventListener('input', cutUpdate);
  el('afr-cu-labels').addEventListener('change', function () {{
    var t = document.getElementById('pv-labels');
    if (t) {{ t.checked = el('afr-cu-labels').checked; t.dispatchEvent(new Event('change')); }}
  }});
  el('afr-cu-prev').addEventListener('click', function () {{
    playing = false; step = Math.max(0, Math.floor(step) - 1); render(); }});
  el('afr-cu-next').addEventListener('click', function () {{
    playing = false;
    step = Math.min(active.principle.length - 1, Math.floor(step) + 1); render(); }});
  el('afr-cu-play').addEventListener('click', function () {{
    playing = !playing; if (playing && step >= active.principle.length - 1) step = 0;
    el('afr-cu-play').textContent = playing ? '일시정지' : '작동 재생'; }});
  el('afr-cu-fit').addEventListener('click', function () {{ if (active) fit(active); }});

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
    if (playing) {{
      step += dt * .55;
      if (step >= active.principle.length - 1) {{
        step = active.principle.length - 1; playing = false;
        el('afr-cu-play').textContent = '작동 재생';
      }}
      render();
    }}
    requestAnimationFrame(tick);
  }}
  /* 원본 공정시계와 자동추적은 이 화면에서 방해만 된다 — 시계는 세우고 카메라는
     내가 잡는다. 켜 둔 채로는 단계가 바뀔 때마다 시점이 플랜트로 끌려간다. */
  var auto = document.getElementById('pv-auto-camera');
  if (auto && auto.checked) {{ auto.checked = !1; auto.dispatchEvent(new Event('change')); }}
  var play = document.getElementById('jb-play');
  if (play && /일시정지/.test(play.textContent)) play.click();
  show(UNITS[0].key); cutUpdate(); requestAnimationFrame(tick);
  window.__pvAfrCloseup = {{ units: UNITS.length,
    get meshes() {{ return group.children.reduce(function (a, g) {{
      return a + g.children.length; }}, 0); }},
    get active() {{ return active && active.key; }} }};
  }}
}})();
</script>
"""


def build() -> str:
    t = PLANT.read_text(encoding="utf-8")
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>AFR-101 부품 확대도</title>\n"
              '<meta name="description" content="AFR-101 프레임 제거장치의 두 핵심 유닛을 '
              '부품 단위로 확대한 3D 도면 — 정반 내장 유압 실린더·쇠막대·스토퍼로 단변을 '
              '밀어내는 단축 인출 유닛과, 35급 LM 레일 위 캐리지가 홈 롤러로 장변을 당기는 '
              '장축 인발 유닛. 분해·단면·작동 5단계와 부품표·사양을 같이 본다.">', "제목")
    t = _once(t, '<h2 id="pv-v22-title">태양광 패널 전처리 통합 플랜트</h2>',
              '<h2 id="pv-v22-title">AFR-101 부품 확대도 — 단축 인출 유닛 · 장축 인발 LM 유닛</h2>',
              "표제")
    t = _once(t, f'<span class="viz-badge">{campaign.total_dwell_s():g} s TRACE</span>',
              '<span class="viz-badge">ASSEMBLY DETAIL</span>', "배지")
    rev = t.split("DRAWING_REVISION = '")[1].split("'")[0]
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · AFR-101 부품 확대도 · ENGINEERING BASE {rev}", "머리글")

    # 콘솔을 부품 확대도 것으로 바꾼다 — 3D 무대만 남기고 나머지는 CSS 로 가린다.
    t = _once(t, "</head>", f"<style>{', '.join(HIDE)} {{ display: none !important; }}"
              f"{console_css()}</style>\n</head>", "콘솔 정리 CSS")
    t = _once(t, '    <section class="pv-v22-programs" aria-labelledby="pv-v22-program-title">',
              console_html() + '    <section class="pv-v22-programs" aria-labelledby="pv-v22-program-title">',
              "부품 확대도 콘솔")
    # 클릭한 형상의 품번·역할은 원본 픽커가 여기에 쓴다 — 콘솔 안으로 옮긴다.
    t = _once(t, '<div class="afr-cu-step" id="afr-cu-step" aria-live="polite"></div>',
              '<div class="afr-cu-step" id="afr-cu-step" aria-live="polite"></div>\n'
              '    <div class="card jb-detail" id="jb-detail" aria-live="polite">'
              '형상을 누르면 그 부품의 품번과 역할이 여기에 나옵니다.</div>', "픽커 자리")
    t = _once(t, '<div class="card jb-detail" id="jb-detail" aria-live="polite">세 벽체 사이의 '
              'BFC-101A/B가 고정 픽업면의 한 장을 상승·반전하고, 650 mm 고상 로봇이 반전 완료품을 '
              '직접 픽업합니다. 적재부·반전기·로봇 사이에는 컨베이어가 없습니다.</div>', "", "원본 픽커 제거")
    # 그림자·케이싱·크레인은 부품을 보는 화면에서도 걷어 낸다.
    t = _once(t, "Dt.shadowMap.enabled=!0;", "Dt.shadowMap.enabled=!1;", "3D 그림자")
    t = _once(t, '<input class="form-check-input" id="pv-case" type="checkbox" checked>',
              '<input class="form-check-input" id="pv-case" type="checkbox">', "외장 케이싱")
    t = _once(t, "</body>", scene_script() + "</body>", "부품 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- AFR-101 부품 확대도: tools/build_afr_closeup.py 가 통합 "
              "설계도에서 만든다. 손으로 고치지 않는다.\n"
              "     형상은 src/pv_preprocess/afr_units.py 의 부품 목록에서 나온다. -->\n",
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
