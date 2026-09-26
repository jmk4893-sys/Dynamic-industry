# -*- coding: utf-8 -*-
"""BR-305 백시트 면 연마 **작동 확대도** — 통합 설계도에서 파생한다.

BR-305 는 모델은 있는데 **그림이 없었다.** `br_abrade.py` 가 깊이 창·열·동력·
집진을 다 풀어 놓고도 부품 자리가 전부 (0, y, 0) 에 쌓여 있었다 — 수량과
규격만 맞으면 되는 **부품표**였기 때문이다. 그것을 그대로 세우면 두 헤드가
겹치고 아무것도 안 보인다.

이 파생본은 그것을 둘로 나눠 편다.

* **기계 전경** — 판이 이송 롤러에 실려 두 헤드를 차례로 지난다. 무엇이 판을
  누르고(벨트·압반) 무엇이 받치는지(롤러)가 부호로 읽히게 **판 윗면을 y = 0**
  으로 잡았다.
* **벨트–적층 접촉부** — 배율 60 배. 적층 5.5 mm 에서 걷는 것이 0.45 mm 라
  실제 비율로 그리면 깎는 층이 선 하나가 된다. 키운 것은 화면이지 치수가 아니다.

밑에 **깊이 창 띠**를 깐다. 0.32(백시트를 다 걷어야 하는 하한) · 0.37(가장 얕은
자리) · 0.45(목표) · 0.53(가장 깊은 자리) · 0.77(셀에 닿기 전 상한)이 어디에
서는지가 그림으로 드러난다 — 이 유닛이 푸는 문제가 그 띠 하나다.

형상·수치는 전부 `src/pv_preprocess/br_abrade.py` 에서 온다 — 화면에 손으로 쓴
값이 없다. 원본 파일은 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 한다.

    PYTHONPATH=src python tools/build_br_closeup.py

멱등이다. `tests/test_pv_br.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import br_abrade, campaign, sg_grind  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-br-closeup.html"

#: 플랜트 콘솔에서 이 파생본이 쓰지 않는 것 — 형상과 깊이 창만 보는 화면이다.
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
    for u in br_abrade.units():
        out.append({
            "key": u.key, "name": u.name, "sheet": u.sheet,
            "envelope": list(u.envelope_mm), "viewR": u.view_r_mm,
            "mag": br_abrade.CONTACT_MAG if u.key == "contact" else 1.0,
            "view": list(br_abrade.VIEW_DIR[u.key]),
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
    """깊이 창 띠가 읽는 자료 — 이 유닛이 푸는 문제가 이 띠 하나다."""
    a = br_abrade
    lo, hi = a.depth_window_mm()
    return json.dumps({
        "lo": lo, "hi": hi,
        "target": a.TARGET_DEPTH_MM,
        "minCut": a.min_depth_cut_mm(),
        "maxCut": a.max_depth_cut_mm(),
        "backsheet": a.BACKSHEET_T_MM,
        "backEva": a.BACK_EVA_T_MM,
        "follow": a.PLATEN_FOLLOW_MM,
        "bed": a.BED_REFERENCE_TOL_MM,
        "marginRatio": a.depth_margin_ratio(),
        "faceFits": a.face_reference_fits(),
        "bedMisses": a.bed_reference_would_miss(),
        "closesBothWays": a.tolerance_closes_both_ways(),
        "occupancy": a.occupancy_s(),
        # **AFR 정반과 견주지 않는다.** 그것은 SG-301 이야기다 — SG 는 AFR 후단
        # 정반을 같이 쓰므로 그 점유 안에 들어야 한다. BR-305 는 자기 스테이션이라
        # 견줄 대상이 라인의 **택트 하한**이다.
        "taktFloor": float(campaign.takt_floor_s()),
        "notBottleneck": a.is_not_the_new_bottleneck(),
        "bottleneck": campaign.bottleneck(),
        "idealTakt": float(campaign.ideal_takt_s()),
        "marks": [
            [a.BACKSHEET_T_MM, "창 하한 — 백시트를 다 걷어야 한다"],
            [a.min_depth_cut_mm(), "가장 얕은 자리"],
            [a.TARGET_DEPTH_MM, "목표 절입"],
            [a.max_depth_cut_mm(), "가장 깊은 자리"],
            [hi, "창 상한 — 셀에 닿기 전"],
        ],
    }, ensure_ascii=False, separators=(",", ":"))


def spec_payload() -> str:
    """유닛별 사양표 — 값은 전부 모델이 푼 것이다."""
    a = br_abrade
    lo, hi = a.depth_window_mm()
    common = [
        ["이송 / 통과", f"**{a.feed_mm_s():.1f} mm/s** · 통과 "
                    f"{a.pass_length_mm():,.0f} mm · 점유 **{a.occupancy_s()} s** "
                    f"(AFR 정반 {campaign.AFR_S} s · 택트 하한 "
                    f"{campaign.takt_floor_s()} s 아래)"],
        ["깊이 창", f"**{lo}~{hi} mm** (폭 {round(hi - lo, 3)}) — 아래로는 백시트 "
                f"{a.BACKSHEET_T_MM} 를 다 걷고, 위로는 셀에 닿기 전에 멈춘다. "
                f"목표 {a.TARGET_DEPTH_MM} · 실제 {a.min_depth_cut_mm()}~"
                f"{a.max_depth_cut_mm()}"],
        ["기준면", f"압반 추종 **±{a.PLATEN_FOLLOW_MM} mm** 가 창 안에 든다 "
               f"(여유 **{a.depth_margin_ratio()} 배**). 정반 기준이면 공차합 "
               f"{a.BED_REFERENCE_TOL_MM} mm 라 **창을 넘는다** — 그래서 면 기준이다"],
    ]
    return json.dumps({
        "br305": common + [
            ["헤드 / 벨트", f"{a.HEADS} 대 · {'/'.join(a.GRITS)} · 폭 "
                       f"{a.BELT_WIDTH_MM:.0f} · 주속 **{a.BELT_SPEED_M_S:.0f} m/s** "
                       f"(이송의 {a.BELT_SPEED_M_S * 1000 / a.feed_mm_s():,.0f} 배)"],
            ["압반", f"조각 **{a.platen_segments()}** × 피치 "
                 f"{a.PLATEN_SEGMENT_MM:.0f} mm = "
                 f"{a.platen_segments() * a.PLATEN_SEGMENT_MM:,.0f} mm — 판 폭 "
                 f"{campaign.PANEL_WIDTH_MM:,.0f} 을 **폭 방향**으로 덮는다"],
            ["동력", f"제거율 {a.removal_rate_mm3_s():,.0f} mm³/s → 헤드당 "
                 f"{a.power_per_head_kw()} kW · 합 **{a.total_power_kw()} kW** · "
                 f"모터 정격 {a.motor_rating_kw():.0f} kW"],
            ["열", f"접촉 호 {a.contact_arc_mm()} mm 를 "
                f"{a.contact_time_s() * 1000:.2f} ms 에 지난다 → 열침투 "
                f"{a.thermal_skin_mm()} mm 가 절입의 **{a.skin_to_depth_ratio()} 배** "
                f"— 데워진 살이 그대로 칩으로 나간다"],
            ["집진", f"**{a.swarf_kg_per_panel()} kg/장** · 후드 "
                 f"{a.hood_flow_m3h():,} m³/h · 지관 Ø{a.DUCT_D_MM:.0f} × "
                 f"{a.outlets_per_head() * a.HEADS} 개 @ "
                 f"{a.DUCT_VELOCITY_M_S:.0f} m/s"],
            ["앞뒤 걸음", f"**{a.UPSTREAM_TAG} → BR-305 → {a.DOWNSTREAM_TAG}** "
                    f"(`LINE_ORDER` 에서 계산한다). 프레임은 {a.FRAME_REMOVED_AT} "
                    "에서 이미 빠졌다"],
        ],
        "contact": common + [
            ["층", f"백시트 {a.BACKSHEET_T_MM} · 배면 EVA {a.BACK_EVA_T_MM} · "
                f"셀+전면 EVA "
                f"{round(sg_grind.STACK_T_MM - sg_grind.GLASS_T_MM - a.BACK_EVA_T_MM - a.BACKSHEET_T_MM, 3)} "
                f"· 유리 {sg_grind.GLASS_T_MM} = 적층 {sg_grind.STACK_T_MM}"],
            ["넘쳐도 되는 이유", f"백시트를 다 걷고도 배면 EVA 가 "
                        f"{round(hi - a.TARGET_DEPTH_MM, 3)} mm 남는다. EVA 는 "
                        "급광에 이미 있는 것이라 **없던 것을 새로 만들지 않는다**"],
            ["관문", f"백시트가 **{a.the_gate_leak_narrows_by():.0f} 배** 좁아진다 "
                 f"(100 % → {(1 - a.DUST_CAPTURE):.1%}). 다만 그 몫도 "
                 f"**실리콘에 떨어진다** — 누출 "
                 f"{a.escaped_fines_g_per_panel()} g/장"],
            ["가루가 더 나쁘다", f"연마는 없애는 것이 아니라 가루로 바꾼다. 38 µm "
                        f"이하 미립자는 부유선별에서 가장 다루기 나쁘다 — "
                        f"**포집률이 안전 항목이 아니라 품질 사양**인 이유다"],
            ["실란트", f"앞 걸음 {a.UPSTREAM_TAG} 가 띠를 걷어 놔야 한다. 안 걷히면 "
                  f"띠가 백시트보다 {a.sealant_step_over_backsheet_mm()} mm 솟아 "
                  f"추종 {a.PLATEN_FOLLOW_MM} 의 "
                  f"{a.sealant_step_vs_platen_follow()} 배 — 깊이 제어가 깨진다"],
        ],
    }, ensure_ascii=False, separators=(",", ":"))


def open_payload() -> str:
    """모델이 **못 닫는** 것 — 두 곳에서 모아 (제목, 설명) 으로 낸다.

    `br_abrade.open_questions()` 는 문장 목록이라 굵게 쓴 첫 구를 제목으로
    떼어 낸다. 순서가 열어 놓은 것(`what_this_order_leaves_open()`)도 같이
    싣는다 — 둘 다 이 유닛이 못 닫는 것이다.
    """
    rows = []
    for line in tuple(br_abrade.open_questions()) + tuple(
            br_abrade.what_this_order_leaves_open()):
        head = line.split("**")
        title = head[1].rstrip(".").strip() if len(head) > 2 else line[:44]
        rows.append([title, line])
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def console_html() -> str:
    """3D 밑에 서는 확대도 콘솔 — 유닛 선택·분해·단면·단계·깊이 창 띠·부품표."""
    return """
  <section class="br-cu" id="br-cu" aria-label="BR-305 백시트 면 연마 작동 확대도">
    <div class="br-cu-head">
      <div class="viz-controls" role="tablist" aria-label="유닛 선택" id="br-cu-tabs"></div>
      <span class="viz-badge tabular-nums" id="br-cu-sheet"></span>
    </div>
    <div class="viz-controls br-cu-controls">
      <label class="form-label" for="br-cu-explode">분해 <span class="tabular-nums" id="br-cu-explode-value">0%</span>
        <input class="form-range" id="br-cu-explode" type="range" min="0" max="100" step="1" value="0">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="br-cu-cut" type="checkbox">
        <span class="form-check-label">단면</span></label>
      <label class="form-label" for="br-cu-cut-at">절단 위치 <span class="tabular-nums" id="br-cu-cut-value">50%</span>
        <input class="form-range" id="br-cu-cut-at" type="range" min="0" max="100" step="1" value="50">
      </label>
      <label class="form-check form-switch"><input class="form-check-input" id="br-cu-spin" type="checkbox" checked>
        <span class="form-check-label">드럼 회전</span></label>
      <button class="btn" id="br-cu-prev" type="button">◀ 이전 단계</button>
      <button class="btn btn-primary" id="br-cu-play" type="button">작동 재생</button>
      <button class="btn" id="br-cu-next" type="button">다음 단계 ▶</button>
      <button class="btn" id="br-cu-fit" type="button">시점 맞춤</button>
    </div>
    <div class="br-cu-step" id="br-cu-step" aria-live="polite"></div>
    <div class="card br-cu-cycle">
      <div class="br-cu-cycle-head">
        <h3 class="text-small">깊이 창 — 이 기계가 지켜야 하는 것은 <b>이 띠 하나</b></h3>
        <span class="text-small text-muted tabular-nums" id="br-cu-cycle-sum"></span>
      </div>
      <div class="br-cu-band" id="br-cu-band" role="img" aria-label="백시트 연마 깊이 창"></div>
      <p class="text-small text-muted" id="br-cu-cycle-note"></p>
    </div>
    <div class="card br-cu-open">
      <h3 class="text-small">이 해석이 못 닫는 것 <span class="text-muted tabular-nums" id="br-cu-open-count"></span></h3>
      <dl class="br-cu-open-list" id="br-cu-open"></dl>
    </div>
    <div class="card jb-detail" id="jb-detail" aria-live="polite">형상을 누르면 그 부품의 품번과 역할이 여기에 나옵니다.</div>
    <div class="br-cu-grid">
      <div class="card br-cu-parts">
        <h3 class="text-small">부품 구성 <span class="text-muted" id="br-cu-count"></span></h3>
        <div class="table-responsive"><table class="table table-sm"><thead>
          <tr><th>부품</th><th>수량</th><th>규격</th><th>재질</th></tr>
        </thead><tbody id="br-cu-rows"></tbody></table></div>
        <p class="text-small text-muted">행을 누르면 그 부품만 남기고 시점이 붙습니다. 형상을 눌러도 같습니다.</p>
      </div>
      <div class="card br-cu-side">
        <h3 class="text-small">작동 원리</h3>
        <ol class="br-cu-steps" id="br-cu-principle"></ol>
        <h3 class="text-small br-cu-h2">면 연마가 푸는 수</h3>
        <div class="table-responsive"><table class="table table-sm"><tbody id="br-cu-spec"></tbody></table></div>
      </div>
    </div>
  </section>
"""


def console_css() -> str:
    return """
  .br-cu { display: flex; flex-direction: column; gap: 10px; }
  .br-cu-head { display: flex; flex-wrap: wrap; align-items: center;
    justify-content: space-between; gap: 8px; }
  .br-cu-controls { align-items: end; }
  .br-cu-controls .form-label { flex: 0 1 210px; }
  .br-cu-step { padding: 8px 12px; border-radius: var(--radius-lg);
    background: var(--muted); font-size: var(--font-size-normal); }
  .br-cu-step b { color: var(--primary); }
  .br-cu-cycle-head { display: flex; flex-wrap: wrap; align-items: baseline;
    justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .br-cu-band { display: flex; width: 100%; height: 46px; overflow: hidden;
    border-radius: var(--radius-sm); }
  .br-cu-band span { display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 1px; min-width: 0; overflow: hidden;
    border-right: 1px solid var(--background); font-size: var(--font-size-small);
    line-height: 1.15; white-space: nowrap; }
  .br-cu-band span:last-child { border-right: 0; }
  .br-cu-band { position: relative; }
  .br-cu-mark { position: absolute; top: 0; bottom: 0; width: 2px;
    background: var(--foreground); opacity: .75; pointer-events: auto; }
  .br-cu-band b { font-weight: var(--font-weight-medium); }
  .br-cu-band .sg-p-long { background: var(--accent); color: var(--accent-foreground); }
  .br-cu-band .sg-p-short { background: var(--primary); color: var(--primary-foreground); }
  .br-cu-band .sg-p-idle { background: var(--muted); color: var(--muted-foreground); }
  .br-cu-band .is-now { outline: 2px solid var(--foreground); outline-offset: -2px; }
  .br-cu-grid { display: grid; gap: 10px;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); }
  .br-cu-parts tbody tr { cursor: var(--cursor-interaction, pointer); }
  .br-cu-parts tbody tr:hover { background: var(--muted); }
  .br-cu-parts tbody tr.is-on { background: var(--accent); color: var(--accent-foreground); }
  .br-cu-steps { margin: 0; padding-left: 18px; display: flex;
    flex-direction: column; gap: 6px; font-size: var(--font-size-small); }
  .br-cu-steps li.is-on { font-weight: var(--font-weight-medium); color: var(--primary); }
  .br-cu-h2 { margin-top: 12px; }
  .br-cu-open { border-left: 3px solid var(--destructive); }
  .br-cu-open-list { margin: 8px 0 0; display: flex; flex-direction: column; gap: 8px;
    font-size: var(--font-size-small); }
  .br-cu-open-list dt { font-weight: var(--font-weight-medium); color: var(--destructive); }
  .br-cu-open-list dd { margin: 2px 0 0; color: var(--muted-foreground); }
"""


def scene_script() -> str:
    """부품을 실제로 그리는 모듈 — 통합 설계도의 3D 연장을 쓴다."""
    g = br_abrade
    # BR-305 는 스윕 단면을 안 쓴다 — 층이 전부 판형이라 상자로 읽힌다.
    poly = "{}"
    return f"""<script>
/* BR-305 백시트 면 연마 작동 확대도 — tools/build_br_closeup.py 가 붙인다.
   형상은 `br_abrade.py` 의 부품 목록에서 나오고, 그리는 연장은
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
      PITCH = {json.dumps(br_abrade.ROW_PITCH_MM, separators=(",", ":"))};
  var MM = 0.001;                                   // 모델은 mm, 씬은 m
  var FEED = {g.feed_mm_s()}, BELT_MS = {g.BELT_SPEED_M_S},
      PANEL_W = {campaign.PANEL_WIDTH_MM}, PANEL_L = {campaign.PANEL_LENGTH_MM},
      MAG = {g.CONTACT_MAG}, DEPTH = {g.TARGET_DEPTH_MM},
      DRUM_RPS = {g.BELT_SPEED_M_S * 1000.0 / (math.pi * g.CONTACT_DRUM_D_MM):.3f},
      HEADS = {g.HEADS}, PASS = {g.pass_length_mm()};
  var chrome = K.M.steel.clone(); chrome.metalness = .62; chrome.roughness = .26;
  /* 포락선은 **틀만** 보이면 된다 — sg 보다 훨씬 비춘다. 여기서는 기계가
     상자 안에 들어 있어서 .38 이면 안이 안 보인다. */
  var ghost = K.M.aluminum.clone(); ghost.transparent = !0; ghost.opacity = .08;
  ghost.depthWrite = !1;
  /* 집진 후드는 벨트 나가는 쪽을 통째로 감싼다 — 막힌 대로 그리면 이 도면이
     보여 줄 것이 가려진다. 형상은 그대로 두고 살만 비춘다. */
  var shroud = K.M.dark.clone(); shroud.transparent = !0; shroud.opacity = .18;
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
  var SPINNERS = {{ drum: 1, feed: 1, motor: 1 }};
  function pose(u, t) {{
    var grp = built[u.key]; if (!grp) return;
    var ex = exVal();
    grp.children.forEach(function (m) {{
      var k = m.userData.part, h = m.userData.home, d = new S.Vector3(), side = m.userData.side;
      /* 자리 변화는 전부 **mm 로 셈해서 마지막에 m 로 바꾼다** — 씬은 m 다. */
      if (u.key === 'br305') {{
        /* ① 판이 들어온다 → ②③ 1 단 → ④ 2 단 → ⑤⑥ 나간다.
           판은 **한 방향으로만** 간다 — 왕복시키면 두 헤드를 두 번 지난다. */
        var run = Math.max(0, Math.min(1, t / 4));
        if (k === 'panel') d.x = (1 - run * 2) * PANEL_L / 2;
        /* 헤드는 물릴 때 내려앉는다 — 절입이 만들어지는 자리가 여기다 */
        var head = (k === 'belt' || k === 'drum' || k === 'platen'
                    || k === 'airknife' || k === 'hood');
        if (head) d.y = (1 - Math.max(0, Math.min(1, t))) * 180;
      }} else {{
        /* 접촉부 — 벨트가 내려와 백시트를 먹고, 칩이 떠서 나간다.
           이 유닛은 배율이 걸려 있으므로 이동도 같은 배율로 잰다. */
        var down = Math.max(0, Math.min(1, t / 1.6));
        var eat = Math.max(0, Math.min(1, (t - 1.6) / 1.8));
        var fly = Math.max(0, Math.min(1, (t - 3) / 2));
        if (k === 'cbelt' || k === 'cplaten') d.y = (1 - down) * 3.2 * MAG;
        /* 걷히는 층이 실제로 얇아지는 대신 **위로 사라진다** — 두께를 줄이면
           씬 좌표가 아니라 형상을 바꿔야 한다. */
        if (k === 'cbacksheet') m.visible = eat < .96;
        if (k === 'cchip') {{
          m.visible = eat > .25;
          d.x = -fly * 420 * MAG / MAG; d.y = fly * 1.8 * MAG;
        }}
      }}
      d.multiplyScalar(MM);
      m.position.copy(h).add(d).add(m.userData.blow.clone().multiplyScalar(ex));
      if (SPINNERS[k]) m.rotation.y = spin;
    }});
  }}

  /* 모델 글은 **강조** 를 마크다운으로 쓴다 — 화면에서는 태그로 바꾼다. */
  function md(s) {{ return String(s).replace(/\\*\\*(.+?)\\*\\*/g, '<b>$1</b>'); }}
  function exVal() {{ return Number(el('br-cu-explode').value) / 100; }}
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
    /* 방향은 모델(`br_abrade.VIEW_DIR`)이 정한다 — 접촉부는 단면이라 스윕 축을
       따라 봐야 옆모습이 나온다. */
    var v = u.view || [.6, .8, 1], n = Math.hypot(v[0], v[1], v[2]);
    S.camera.position.set(v[0] / n * d, v[1] / n * d, v[2] / n * d);
    S.controls.target.set(0, tall * .12, 0); S.controls.update();
  }}

  /* 깊이 창 띠 — 이 유닛이 푸는 문제가 이 띠 하나다 */
  function band() {{
    var hi = CYCLE.hi, seg = [
      ['sg-p-idle', 0, CYCLE.backsheet, '백시트 — 여기까지는 반드시 걷는다'],
      ['sg-p-long', CYCLE.backsheet, CYCLE.hi, '배면 EVA — 넘쳐도 되는 여유층'],
    ];
    el('br-cu-band').innerHTML = seg.map(function (t, i) {{
      var w = t[2] - t[1];
      return '<span class="' + t[0] + '" data-i="' + i + '" style="flex:' + w + ' 1 0">'
        + '<b>' + t[1].toFixed(2) + '–' + t[2].toFixed(2) + ' mm</b>'
        + '<span>' + t[3] + '</span></span>';
    }}).join('')
      + CYCLE.marks.map(function (m) {{
        return '<i class="br-cu-mark" style="left:' + (m[0] / hi * 100).toFixed(2)
          + '%" title="' + m[1] + ' — ' + m[0].toFixed(2) + ' mm"></i>';
      }}).join('');
    el('br-cu-cycle-sum').textContent = '창 ' + CYCLE.lo.toFixed(2) + '–'
      + CYCLE.hi.toFixed(2) + ' mm · 실제 ' + CYCLE.minCut.toFixed(2) + '–'
      + CYCLE.maxCut.toFixed(2) + ' mm · 점유 ' + CYCLE.occupancy.toFixed(2) + ' s';
    el('br-cu-cycle-note').innerHTML = md(
      '아래로는 백시트 **' + CYCLE.backsheet.toFixed(2) + ' mm** 를 다 걷어야 하고, '
      + '위로는 셀에 닿기 전에 멈춰야 한다 — 그 사이 **'
      + (CYCLE.hi - CYCLE.lo).toFixed(2) + ' mm** 가 이 기계가 지켜야 하는 전부다. '
      + '압반이 **판 면**에 얹혀 ±' + CYCLE.follow.toFixed(2) + ' mm 를 따라가므로 '
      + '여유가 **' + CYCLE.marginRatio.toFixed(2) + ' 배**다. 정반을 기준으로 잡으면 '
      + '공차합 ' + CYCLE.bed.toFixed(2) + ' mm 라 **창을 넘는다** — 그것이 이 유닛이 '
      + '압반을 분할하는 이유다. 눈금은 왼쪽부터 창 하한 · 가장 얕은 자리 · 목표 · '
      + '가장 깊은 자리 · 창 상한이다.');
  }}

  function bandMark() {{
    var kids = el('br-cu-band').children, i;
    for (i = 0; i < kids.length; i += 1)
      if (kids[i].classList) kids[i].classList.toggle('is-now',
        active && active.key === 'contact' && kids[i].dataset.i === '0');
  }}

  function show(key) {{
    active = UNITS.filter(function (u) {{ return u.key === key; }})[0];
    UNITS.forEach(function (u) {{ built[u.key].visible = u.key === key; }});
    el('br-cu-sheet').textContent = active.sheet;
    el('br-cu-count').textContent = '· ' + active.parts.length + ' 종 '
      + active.parts.reduce(function (a, p) {{ return a + p.qty; }}, 0) + ' 개';
    el('br-cu-rows').innerHTML = active.parts.map(function (p) {{
      return '<tr data-part="' + p.key + '"><td>' + p.name + '</td><td class="tabular-nums">'
        + p.qty + '</td><td>' + md(p.spec || '—') + '</td><td>' + p.material + '</td></tr>';
    }}).join('');
    el('br-cu-principle').innerHTML = active.principle.map(function (s) {{
      return '<li><b>' + s[0] + '</b> ' + md(s[1]) + '</li>';
    }}).join('');
    el('br-cu-spec').innerHTML = (SPEC[key] || []).map(function (r) {{
      return '<tr><th scope="row">' + r[0] + '</th><td>' + md(r[1]) + '</td></tr>';
    }}).join('');
    [].forEach.call(el('br-cu-tabs').children, function (b) {{
      b.classList.toggle('btn-primary', b.dataset.unit === key);
      b.setAttribute('aria-selected', String(b.dataset.unit === key));
    }});
    step = 0; focus = null; fit(active); render();
  }}

  function render() {{
    if (!active) return;
    pose(active, step);
    var p = active.principle[Math.min(active.principle.length - 1, Math.floor(step))];
    el('br-cu-step').innerHTML = '<b>' + p[0] + '</b> ' + md(p[1]);
    [].forEach.call(el('br-cu-principle').children, function (li, i) {{
      li.classList.toggle('is-on', i === Math.floor(step));
    }});
    [].forEach.call(el('br-cu-rows').children, function (tr) {{
      tr.classList.toggle('is-on', tr.dataset.part === focus);
    }});
    if (focus) built[active.key].children.forEach(function (m) {{
      m.visible = m.userData.part === focus;
    }});
    el('br-cu-explode-value').textContent = Math.round(exVal() * 100) + '%';
    el('br-cu-cut-value').textContent = el('br-cu-cut-at').value + '%';
    bandMark();
  }}

  /* 단면 — 씬 전체에 잘라 내는 평면 하나를 건다 */
  var plane = new S.Plane(new S.Vector3(-1, 0, 0), 0);
  function cutUpdate() {{
    var on = el('br-cu-cut').checked;
    S.renderer.clippingPlanes = on ? [plane] : [];
    S.renderer.localClippingEnabled = on;
    if (active) plane.constant = (Number(el('br-cu-cut-at').value) / 100 - .5)
      * active.envelope[0] * MM;
  }}

  UNITS.forEach(function (u) {{ built[u.key] = build(u); }});
  el('br-cu-tabs').innerHTML = UNITS.map(function (u) {{
    return '<button class="btn" type="button" role="tab" data-unit="' + u.key + '">'
      + u.name.split(' (')[0] + '</button>';
  }}).join('');
  el('br-cu-tabs').addEventListener('click', function (e) {{
    var b = e.target.closest('[data-unit]'); if (b) show(b.dataset.unit);
  }});
  el('br-cu-rows').addEventListener('click', function (e) {{
    var tr = e.target.closest('[data-part]'); if (!tr) return;
    focus = focus === tr.dataset.part ? null : tr.dataset.part;
    if (!focus) built[active.key].children.forEach(function (m) {{ m.visible = true; }});
    render();
  }});
  el('br-cu-explode').addEventListener('input', render);
  el('br-cu-cut').addEventListener('change', cutUpdate);
  el('br-cu-cut-at').addEventListener('input', cutUpdate);
  el('br-cu-prev').addEventListener('click', function () {{
    playing = false; step = Math.max(0, Math.floor(step) - 1); render(); }});
  el('br-cu-next').addEventListener('click', function () {{
    playing = false;
    step = Math.min(active.principle.length - 1, Math.floor(step) + 1); render(); }});
  el('br-cu-play').addEventListener('click', function () {{
    playing = !playing; if (playing && step >= active.principle.length - 1) step = 0;
    el('br-cu-play').textContent = playing ? '일시정지' : '작동 재생'; }});
  el('br-cu-fit').addEventListener('click', function () {{ if (active) fit(active); }});

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
    /* 드럼 회전수는 주속에서 나온다 — 벨트 주속 / 원주. */
    if (el('br-cu-spin').checked) spin += dt * DRUM_RPS * 2 * Math.PI;
    if (playing) {{
      step += dt * .55;
      if (step >= active.principle.length - 1) {{
        step = active.principle.length - 1; playing = false;
        el('br-cu-play').textContent = '작동 재생';
      }}
    }}
    if (playing || el('br-cu-spin').checked) render();
    requestAnimationFrame(tick);
  }}
  /* 원본 공정시계와 자동추적은 이 화면에서 방해만 된다. */
  var auto = document.getElementById('pv-auto-camera');
  if (auto && auto.checked) {{ auto.checked = !1; auto.dispatchEvent(new Event('change')); }}
  var play = document.getElementById('jb-play');
  if (play && /일시정지/.test(play.textContent)) play.click();
  el('br-cu-open-count').textContent = '· ' + OPEN.length + ' 건';
  el('br-cu-open').innerHTML = OPEN.map(function (q) {{
    return '<dt>' + md(q[0]) + '</dt><dd>' + md(q[1]) + '</dd>';
  }}).join('');
  band(); show(UNITS[0].key); cutUpdate(); requestAnimationFrame(tick);
  window.__pvBrCloseup = {{ units: UNITS.length, cycle: CYCLE,
    feed: {{ mmS: FEED, beltMS: BELT_MS, passMm: PASS }},
    panel: {{ w: PANEL_W, l: PANEL_L }}, mag: MAG, depth: DEPTH, heads: HEADS,
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
    g = br_abrade
    lo, hi = g.depth_window_mm()
    t = PLANT.read_text(encoding="utf-8")
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>BR-305 백시트 면 연마 작동 확대도</title>\n"
              '<meta name="description" content="붙어 있는 백시트를 파쇄 전에 면에서 '
              '걷어내는 BR-305 를 부품 단위로 확대한 3D 도면 — 판이 이송 롤러에 실려 두 '
              f'헤드를 지나는 기계 전경과, 배율 {g.CONTACT_MAG:.0f} 배로 키운 벨트–적층 '
              f'접촉부. 깊이 창 {lo}~{hi} mm 가 이 기계가 지켜야 하는 전부이고, 압반이 '
              '판 면을 타는 이유가 그 창에 있다.">', "제목")
    t = _once(t, '<h2 id="pv-v22-title">태양광 패널 전처리 통합 플랜트</h2>',
              '<h2 id="pv-v22-title">BR-305 백시트 면 연마 작동 확대도 — 2 헤드 통과 · '
              '벨트–적층 접촉부</h2>', "표제")
    t = _once(t, f'<span class="viz-badge">{campaign.total_dwell_s():g} s TRACE</span>',
              f'<span class="viz-badge">BACKSHEET ABRASION · {g.occupancy_s()} s</span>',
              "배지")
    rev = t.split("DRAWING_REVISION = '")[1].split("'")[0]
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · BR-305 백시트 면 연마 작동 확대도 · "
              f"ENGINEERING BASE {rev}", "머리글")

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
    t = _once(t, "</body>", scene_script() + "</body>", "면 연마 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- BR-305 백시트 면 연마 작동 확대도: "
              "tools/build_br_closeup.py 가 통합 설계도에서 만든다. 손으로 고치지 않는다.\n"
              "     형상·수치는 src/pv_preprocess/br_abrade.py 에서 온다 — 화면에 손으로 쓴 "
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
