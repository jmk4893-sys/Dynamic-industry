# -*- coding: utf-8 -*-
"""후단 네 도면을 **한 장에 모아** 골라 보게 한다 — AFR-101 · SG-301 · GI.

같은 구간을 네 벌로 나눠 발행하면 링크도 넷, 판번도 넷이 된다. 어느 것이 최신인지
받는 쪽이 알 방법이 없고, 넷 중 하나만 다시 발행하면 그때부터 갈린다. 그래서 이
화면은 **네 벌을 합치지 않고 그대로 담는다.** 각 도면의 HTML 을 통째로 base64 로
실어 두고, 고른 것만 `<iframe srcdoc>` 으로 띄운다 — 서식이 섞이지 않고 같은 표가
두 번 나오지 않는다.

액자(색·활자·탭·해제 방식)는 `build_jbr_hub` 것을 **그대로 가져다 쓴다.** 두 벌을
따로 손보면 같은 라인의 도면집 둘이 서로 다른 물건처럼 보인다.

    PYTHONPATH=src python tools/build_afr_hub.py

담는 것 (`SHEETS`) — 순서가 곧 공정 순서다.

* **AFR-101 제거장치** — 프레임이 빠지는 것
* **AFR 부품 확대도** — 그것을 빼는 기구
* **SG-301 연마 확대도** — 뜯긴 변을 다듬는 것
* **GI 검사 확대도** — 다듬은 것을 보는 것

**띠는 구간이 아니라 점유다.** 모델이 주는 것은 길이(`campaign.AFR_S` ·
`sg_grind.occupancy_s()` · `gi_optics.scan_time_s()`)뿐이고 셀 안에서 그것이 언제
시작하는지는 어디에도 없다. 없는 오프셋을 지어내 「95–120 s」 처럼 적으면 화면이
모델보다 많이 아는 척하게 되므로, 각 도면이 **AFR 39.03 s 중 얼마를 쓰는지**만
그린다. 도면 이름과 한 줄 설명은 각 파일의 `<title>`·`<meta description>` 에서
읽는다 — 어느 하나라도 없으면 생성이 실패한다.

멱등이다. `tests/test_pv_afr_hub.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from pv_preprocess import campaign, gi_optics, sg_grind  # noqa: E402
from build_jbr_hub import CSS, esc, num, payload, sheet_meta  # noqa: E402

OUT = ROOT / "docs/drawings/pv-afr-hub.html"

#: 담을 도면 — (키, 파일, 탭에 적을 역할, 점유 라벨). 점유 초는 `scopes()` 가 낸다.
SHEETS: tuple[tuple[str, str, str, str], ...] = (
    ("scene", "docs/drawings/pv-afr-scene.html", "프레임이 빠지는 것", "AFR-101 셀"),
    ("closeup", "docs/drawings/pv-afr-closeup.html", "그것을 빼는 기구", "AFR-101 셀"),
    ("grind", "docs/drawings/pv-sg-closeup.html", "뜯긴 변을 다듬는 것", "SG-301 반출롤러"),
    ("inspect", "docs/drawings/pv-gi-closeup.html", "다듬은 것을 보는 것", "GI 스캔"),
)


def scopes() -> dict[str, float]:
    """도면마다 AFR 창의 몇 초를 쓰는가 — 전부 모델이 푼 값이다.

    AFR 셀 점유가 분모이고, 그 안에서 SG 는 반출롤러를, GI 는 통과 스캔을 쓴다.
    셋 다 다른 모듈이 정본을 쥐고 있으므로 여기서 새로 정하는 수가 없다.
    """
    return {
        "scene": float(campaign.AFR_S),
        "closeup": float(campaign.AFR_S),
        "grind": sg_grind.occupancy_s(),
        "inspect": gi_optics.scan_time_s(),
    }


def build() -> str:
    infeed, jbr, afr = campaign.INFEED_S, campaign.JBR_S, campaign.AFR_S
    total = campaign.total_dwell_s()
    start = infeed + jbr
    scope = scopes()

    metas, tabs_src, payloads = [], [], []
    for key, rel, role, label in SHEETS:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"✗ {rel} 이 없다 — 그 도면의 생성기를 먼저 돌린다")
        title, desc = sheet_meta(path)
        secs = scope[key]
        if secs > afr:
            raise SystemExit(f"✗ {key}: 점유 {secs} s 가 AFR {afr} s 를 넘는다")
        metas.append({"key": key, "title": title, "desc": desc,
                      "label": label, "secs": secs, "src": rel,
                      "kb": round(path.stat().st_size / 1024)})
        tabs_src.append((key, title, role, label, secs))
        payloads.append((key, payload(path)))

    # 띠 세 칸 — 폭이 곧 초다. 이 도면집이 다루는 것은 세 번째 칸이다.
    segs = "".join(
        f'<div class="seg{" here" if here else ""}" style="flex:{w:g}">{esc(label)}</div>'
        for label, w, here in (
            (f"투입 {num(infeed)} s", infeed, False),
            (f"JBR-201 {num(jbr)} s", jbr, False),
            (f"AFR 이후 {num(afr)} s", afr, True)))

    tabs = "".join(
        f'<button class="tab" type="button" role="tab" id="tab-{key}"'
        f' aria-controls="panel-{key}" aria-selected="{"true" if i == 0 else "false"}"'
        f' data-key="{key}">'
        f'<span class="n">{esc(title)}</span>'
        f'<span class="r">{esc(role)} · {esc(label)} {num(secs)} s</span>'
        f"</button>"
        for i, (key, title, role, label, secs) in enumerate(tabs_src))

    scripts = "\n".join(
        f'<script type="text/plain" id="doc-{key}">{b64}</script>'
        for key, b64 in payloads)

    data = json.dumps(metas, ensure_ascii=False, separators=(",", ":"))
    body = f"""<div class="hub">
<header class="top">
  <div class="eyebrow">DYNAMIC INDUSTRY · PV 전처리 라인 · 후단 도면집</div>
  <h1>AFR-101 · SG-301 · GI — 프레임 제거부터 검사까지</h1>
  <p class="sub">AFR-101 인계 <b>{num(start)} s</b> → 버퍼 적재
    <b>{num(total)} s</b> · 후단 점유 <b>{num(afr)} s</b> ·
    종단 체류 <b>{num(total)} s</b> 가운데</p>
  <div class="clock" aria-hidden="true">
    <div class="bar">{segs}</div>
    <div class="span"><i id="spanBar"></i><b id="spanLabel"></b></div>
    <div class="ticks"><span>0 s</span><span>{num(total)} s</span></div>
  </div>
  <div class="tabs" role="tablist" aria-label="후단 도면">{tabs}</div>
</header>
<p class="hint" id="hint"></p>
<main>
  <div class="loading" id="loading" hidden><span>도면을 여는 중…</span></div>
</main>
<footer>
  네 도면은 합치지 않고 그대로 담았다 — 고른 것만 자기 문서로 열리므로 서식이 섞이지
  않고 같은 표가 두 번 나오지 않는다. 띠 밑의 막대는 <b>구간이 아니라 점유</b>다:
  모델이 주는 것은 길이뿐이고 셀 안의 시작 시각은 어디에도 없다. 손으로 쓰지 않는다:
  <code>PYTHONPATH=src python tools/build_afr_hub.py</code> ·
  출처 <code>docs/drawings/pv-{{afr-scene,afr-closeup,sg-closeup,gi-closeup}}.html</code>
</footer>
</div>
{scripts}
<script>
(function () {{
  'use strict';
  var SHEETS = {data};
  var AFR = {afr:g}, START = {start:g}, TOTAL = {total:g};
  var el = function (id) {{ return document.getElementById(id); }};
  var main = document.querySelector('main'), loading = el('loading');
  var tabs = [].slice.call(document.querySelectorAll('.tab'));
  var frames = {{}}, current = null;

  // base64 로 실어 둔 것을 문자열로 되돌린다. 한글이 들어 있으므로 atob 만으로는
  // 안 되고 UTF-8 로 다시 읽어야 한다.
  function decode(b64) {{
    var bin = atob(b64), n = bin.length, u8 = new Uint8Array(n);
    for (var i = 0; i < n; i += 1) u8[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(u8);
  }}

  function open(key) {{
    if (frames[key]) return frames[key];
    var meta = SHEETS.filter(function (s) {{ return s.key === key; }})[0];
    var f = document.createElement('iframe');
    f.id = 'panel-' + key;
    f.setAttribute('role', 'tabpanel');
    f.setAttribute('aria-labelledby', 'tab-' + key);
    f.title = meta.title;
    main.appendChild(f);
    var doc = decode(el('doc-' + key).textContent);
    // srcdoc 이 우선이다. 막히면 같은 출처의 문서에 직접 쓴다.
    if ('srcdoc' in f) {{ f.srcdoc = doc; }} else {{
      var d = f.contentDocument || f.contentWindow.document;
      d.open(); d.write(doc); d.close();
    }}
    frames[key] = f;
    return f;
  }}

  function show(key) {{
    if (current === key) return;
    loading.hidden = !!frames[key];
    var f = open(key);
    if (loading.hidden === false) {{
      f.addEventListener('load', function () {{ loading.hidden = true; }}, {{ once: true }});
      // srcdoc 이 이미 파싱을 끝낸 뒤였다면 load 가 오지 않을 수 있다.
      setTimeout(function () {{ loading.hidden = true; }}, 4000);
    }}
    Object.keys(frames).forEach(function (k) {{ frames[k].hidden = k !== key; }});
    tabs.forEach(function (b) {{
      var on = b.getAttribute('data-key') === key;
      b.setAttribute('aria-selected', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1;
    }});
    var meta = SHEETS.filter(function (s) {{ return s.key === key; }})[0];
    el('hint').textContent = meta.desc;
    // 막대는 **점유**다 — AFR 칸 안에서 이 도면이 쓰는 몫만큼만 채운다.
    // 시작 시각은 모델에 없으므로 칸 왼쪽에 붙인다 (자리를 지어내지 않는다).
    var bar = el('spanBar'), lab = el('spanLabel');
    var a = START / TOTAL * 100, w = meta.secs / TOTAL * 100;
    bar.style.left = a.toFixed(3) + '%';
    bar.style.width = Math.max(0.6, w).toFixed(3) + '%';
    lab.style.left = 'calc(' + (a + w).toFixed(3) + '% + 6px)';
    lab.textContent = meta.label + ' ' + meta.secs + ' s / AFR ' + AFR + ' s';
    current = key;
    try {{ history.replaceState(null, '', '#' + key); }} catch (e) {{ /* 액자 안이면 막힌다 */ }}
  }}

  tabs.forEach(function (b, i) {{
    b.addEventListener('click', function () {{ show(b.getAttribute('data-key')); }});
    b.addEventListener('keydown', function (e) {{
      var d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      var n = tabs[(i + d + tabs.length) % tabs.length];
      n.focus(); show(n.getAttribute('data-key'));
    }});
  }});

  var startKey = (location.hash || '').replace('#', '');
  show(SHEETS.some(function (s) {{ return s.key === startKey; }}) ? startKey : SHEETS[0].key);
}}());
</script>
"""
    return ("<!doctype html>\n"
            "<!-- 후단 도면집: tools/build_afr_hub.py 가 네 도면 파일을 그대로 담아\n"
            "     찍는다. 손으로 고치지 않는다 — 도면을 고치고 이것을 다시 돌린다. -->\n"
            '<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            "<title>AFR-101 · SG-301 · GI 후단 도면집</title>\n"
            '<meta name="description" content="폐 태양광 패널 전처리 라인의 후단 '
            f'{num(afr)} s — 알루미늄 프레임 제거(AFR-101), 그 기구의 부품 확대도, '
            '뜯긴 유리 변을 다듬는 SG-301 연마, 다듬은 것을 보는 GI 라인스캔 검사. '
            '네 도면을 한 장에 담아 골라 본다.">\n'
            f"<style>{CSS}</style>\n</head>\n<body>\n{body}</body>\n</html>\n")


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
