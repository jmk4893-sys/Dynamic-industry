# -*- coding: utf-8 -*-
"""JBR-201 한 셀의 도면 세 벌을 **한 장에 모아** 골라 보게 한다.

같은 셀을 세 벌로 나눠 발행하면 링크도 셋, 판번도 셋이 된다. 어느 것이 최신인지
받는 쪽이 알 방법이 없고, 셋 중 하나만 다시 발행하면 그때부터 갈린다.

그래서 이 화면은 **세 벌을 합치지 않고 그대로 담는다.** 각 도면의 HTML 을 통째로
base64 로 실어 두고, 고른 것만 `<iframe srcdoc>` 으로 띄운다. 문서마다 자기 CSS 와
자기 `id` 를 그대로 쓰므로 서로 섞이지 않고, 내용도 한 번씩만 들어간다 — 합쳐
쓰면서 규칙이 충돌하거나 같은 표가 두 번 나오는 일이 없다.

    PYTHONPATH=src python tools/build_jbr_hub.py

담는 것 (`SHEETS`) — 순서가 곧 보는 순서다.

* **3D 운전 콘솔** — 셀이 움직이는 것
* **상세도** — 그 움직임이 어떤 값에서 나왔는지
* **박리·절단·배출** — 잡고·끊고·떨구는 순간

머리글의 공정시계 띠와 각 탭의 구간은 손으로 쓰지 않는다. 창은
`src/pv_preprocess/campaign.py` 에서, 클로즈업이 다루는 구간은
`tools/build_jbr_closeup.py` 의 상수에서, 도면 이름과 한 줄 설명은 각 도면
파일의 `<title>` 과 `<meta name="description">` 에서 읽는다. 어느 하나라도
사라지면 생성이 실패한다 — 화면이 조용히 옛 값으로 남는 대신.

멱등이다. `tests/test_pv_jbr.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import base64
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-jbr-hub.html"

#: 담을 도면 — (키, 파일, 탭에 적을 역할, 다루는 플랜트 시각 구간).
#: 구간이 None 이면 셀 점유 전체를 다룬다는 뜻이다.
SHEETS: tuple[tuple[str, str, str, str | None], ...] = (
    ("scene", "docs/drawings/pv-jbr-scene.html", "움직이는 것", None),
    ("detail", "docs/drawings/pv-jbr-detail.html", "값이 나온 자리", None),
    ("closeup", "docs/drawings/pv-jbr-closeup.html", "잡고·끊고·떨구는 순간", "closeup"),
)


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def num(v: float) -> str:
    """소수점 뒤 0 은 지운다 — 40.0 s 가 아니라 40 s 다."""
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def head_of(text: str) -> str:
    """`<head>` 안만 본다 — 본문 스크립트에도 `<title>` 이 수십 개 들어 있다."""
    m = re.search(r"<head[^>]*>(.*?)</head>", text, re.S | re.I)
    if not m:
        raise SystemExit("✗ <head> 를 못 찾았다")
    return m.group(1)


def sheet_meta(path: pathlib.Path) -> tuple[str, str]:
    """도면의 이름과 한 줄 설명. 둘 다 그 파일이 스스로 적어 둔 것이다."""
    text = path.read_text(encoding="utf-8")
    head = head_of(text)
    title = re.search(r"<title>(.*?)</title>", head, re.S)
    desc = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', head, re.S)
    if not title:
        raise SystemExit(f"✗ {path}: <head> 안에 <title> 이 없다")
    if not desc:
        raise SystemExit(f"✗ {path}: <meta name=\"description\"> 이 없다 — "
                         "탭 설명을 손으로 쓰지 않으려면 도면이 스스로 적어야 한다")
    return title.group(1).strip(), " ".join(desc.group(1).split())


def payload(path: pathlib.Path) -> str:
    """도면 하나를 base64 로. 원문에 `</script` 가 들어 있어도 안전하고,
    돌려받은 것이 바이트 하나까지 같은지 여기서 확인한다."""
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    if base64.b64decode(b64) != raw:
        raise SystemExit(f"✗ {path}: base64 왕복이 어긋난다")
    return b64


def closeup_window() -> tuple[float, float]:
    """클로즈업이 다루는 플랜트 시각. 그 생성기의 상수에서 읽는다."""
    src = (ROOT / "tools/build_jbr_closeup.py").read_text(encoding="utf-8")
    m = re.search(r"^T_FROM, T_TO = ([\d.]+), ([\d.]+)$", src, re.M)
    if not m:
        raise SystemExit("✗ build_jbr_closeup.py 의 T_FROM·T_TO 를 못 읽었다")
    return (float(m.group(1)) + campaign.INFEED_S, float(m.group(2)) + campaign.INFEED_S)


CSS = """
/* 색·활자는 이 셀의 도면 세 벌이 이미 쓰는 것을 그대로 따른다. 액자만 새로
   만들면 액자와 그림이 서로 다른 물건처럼 보인다. */
:root{color-scheme:light dark;
 --bg:#eef1f0;--card:#fff;--card2:#f6f8f7;--line:#d2d9d7;--line2:#b3bebb;
 --ink:#141f24;--ink2:#4a5c62;--ink3:#6e8087;--brand:#1b7cb8;--brand2:#4aa8e0;
 --brand-dim:#e3eff8;--up:#c8d3d0;--down:#c8d3d0;--shadow:rgba(20,31,36,.09);
 --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#111a1e;--card:#1b262b;--card2:#212d33;--line:#32444a;--line2:#45585f;
 --ink:#e5eeef;--ink2:#a2b7bc;--ink3:#798f96;--brand:#4aa8e0;--brand2:#6cc4f2;
 --brand-dim:#0f3149;--up:#3b4c52;--down:#3b4c52;--shadow:rgba(0,0,0,.34);}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#111a1e;--card:#1b262b;--card2:#212d33;--line:#32444a;--line2:#45585f;
 --ink:#e5eeef;--ink2:#a2b7bc;--ink3:#798f96;--brand:#4aa8e0;--brand2:#6cc4f2;
 --brand-dim:#0f3149;--up:#3b4c52;--down:#3b4c52;--shadow:rgba(0,0,0,.34);}
*{box-sizing:border-box}
/* 발행본은 호스트 골격이 이 규칙을 주지만 저장소 파일은 스스로 가져야 한다 —
   없으면 iframe 의 display:block 이 이겨서 세 도면이 한꺼번에 늘어선다. */
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--sans)}
.hub{display:flex;flex-direction:column;min-height:100vh}

header.top{background:var(--card);border-bottom:1px solid var(--line);
 padding:14px 18px 0;display:flex;flex-direction:column;gap:9px}
.eyebrow{font-size:11.5px;letter-spacing:.11em;color:var(--ink3);text-transform:uppercase}
h1{margin:0;font-size:20px;line-height:1.2;letter-spacing:-.005em;text-wrap:balance}
.sub{margin:0;color:var(--ink2);font-size:13.5px}
.sub b{color:var(--ink);font-family:var(--mono);font-variant-numeric:tabular-nums;
 font-weight:600}

/* 공정시계 띠 — 장식이 아니라 이 셀이 어디에 있는지다. 폭이 곧 초다. */
.clock{display:grid;grid-template-columns:1fr;gap:4px;max-width:940px}
.bar{display:flex;height:22px;border:1px solid var(--line2);border-radius:5px;
 overflow:hidden;background:var(--card2)}
.seg{display:flex;align-items:center;justify-content:center;font-size:11px;
 color:var(--ink3);white-space:nowrap;overflow:hidden;background:var(--up)}
.seg.here{background:var(--brand);color:#fff;font-weight:600}
.ticks{display:flex;justify-content:space-between;font-family:var(--mono);
 font-size:10.5px;color:var(--ink3);font-variant-numeric:tabular-nums}
.span{position:relative;height:13px;margin-top:1px}
.span i{position:absolute;top:0;height:7px;border:1px solid var(--brand2);
 border-bottom:0;border-radius:3px 3px 0 0}
.span b{position:absolute;top:0;font-family:var(--mono);font-size:10.5px;
 color:var(--brand);font-weight:600;font-variant-numeric:tabular-nums;
 transform:translateY(-1px)}

/* 탭 — 이름과 역할, 그리고 그 도면이 다루는 구간까지 한 칸에 담는다. */
.tabs{display:flex;flex-wrap:wrap;gap:0;margin:0;padding:0;list-style:none}
.tab{appearance:none;font:inherit;text-align:left;cursor:pointer;
 background:transparent;border:0;border-bottom:2px solid transparent;
 padding:8px 16px 9px;color:var(--ink2);display:flex;flex-direction:column;gap:1px;
 border-radius:6px 6px 0 0}
.tab:hover{background:var(--card2);color:var(--ink)}
.tab .n{font-size:14px;font-weight:600;color:var(--ink2)}
.tab .r{font-size:11.5px;color:var(--ink3)}
.tab[aria-selected="true"]{border-bottom-color:var(--brand);background:var(--brand-dim)}
.tab[aria-selected="true"] .n{color:var(--brand)}
.tab[aria-selected="true"] .r{color:var(--ink2)}
.tab:focus-visible{outline:2px solid var(--brand);outline-offset:-2px}

.hint{margin:0;padding:9px 18px;background:var(--card2);
 border-bottom:1px solid var(--line);color:var(--ink2);font-size:13px}
main{flex:1;min-height:0;display:flex;position:relative;background:var(--bg)}
iframe{flex:1;min-height:78vh;width:100%;border:0;display:block;background:var(--bg)}
.loading{position:absolute;inset:0;display:flex;align-items:center;
 justify-content:center;gap:9px;color:var(--ink3);font-size:13.5px;
 font-family:var(--mono);pointer-events:none;background:var(--bg)}
footer{border-top:1px solid var(--line);background:var(--card);
 padding:10px 18px 14px;color:var(--ink3);font-size:12px}
footer code{font-family:var(--mono);font-size:.92em;background:var(--brand-dim);
 padding:1px 5px;border-radius:4px;color:var(--ink2)}
footer a{color:var(--brand)}
@media (max-width:720px){
 header.top{padding:12px 12px 0}
 h1{font-size:18px}
 .tab{padding:7px 11px 8px}
 .hint,footer{padding-left:12px;padding-right:12px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""


def build() -> str:
    infeed, jbr = campaign.INFEED_S, campaign.JBR_S
    afr = campaign.AFR_S
    total = infeed + jbr + afr
    c_from, c_to = closeup_window()

    metas, sheets, payloads = [], [], []
    for key, rel, role, span in SHEETS:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"✗ {rel} 이 없다 — 그 도면의 생성기를 먼저 돌린다")
        title, desc = sheet_meta(path)
        lo, hi = (c_from, c_to) if span == "closeup" else (infeed, infeed + jbr)
        metas.append({"key": key, "title": title, "desc": desc,
                      "from": lo, "to": hi, "src": rel,
                      "kb": round(path.stat().st_size / 1024)})
        sheets.append((key, title, role, lo, hi))
        payloads.append((key, payload(path)))

    # 띠 세 칸 — 폭이 곧 초다.
    segs = "".join(
        f'<div class="seg{" here" if here else ""}" style="flex:{w:g}">{esc(label)}</div>'
        for label, w, here in (
            (f"투입 {num(infeed)} s", infeed, False),
            (f"JBR-201 {num(jbr)} s", jbr, True),
            (f"AFR {num(afr)} s", afr, False)))

    tabs = "".join(
        f'<button class="tab" type="button" role="tab" id="tab-{key}"'
        f' aria-controls="panel-{key}" aria-selected="{"true" if i == 0 else "false"}"'
        f' data-key="{key}">'
        f'<span class="n">{esc(title)}</span>'
        f'<span class="r">{esc(role)} · 플랜트 {num(lo)}–{num(hi)} s</span>'
        f"</button>"
        for i, (key, title, role, lo, hi) in enumerate(sheets))

    scripts = "\n".join(
        f'<script type="text/plain" id="doc-{key}">{b64}</script>'
        for key, b64 in payloads)

    data = json.dumps(metas, ensure_ascii=False, separators=(",", ":"))
    body = f"""<div class="hub">
<header class="top">
  <div class="eyebrow">DYNAMIC INDUSTRY · PV 전처리 라인 · 셀 2 / 4</div>
  <h1>JBR-201 정션박스·케이블 제거장치</h1>
  <p class="sub">JB-201 인계 <b>{num(infeed)} s</b> → AFR-101 인계
    <b>{num(infeed + jbr)} s</b> · 셀 점유 <b>{num(jbr)} s</b> ·
    종단 체류 <b>{num(total)} s</b> 가운데</p>
  <div class="clock" aria-hidden="true">
    <div class="bar">{segs}</div>
    <div class="span"><i id="spanBar"></i><b id="spanLabel"></b></div>
    <div class="ticks"><span>0 s</span><span>{num(total)} s</span></div>
  </div>
  <div class="tabs" role="tablist" aria-label="JBR-201 도면">{tabs}</div>
</header>
<p class="hint" id="hint"></p>
<main>
  <div class="loading" id="loading" hidden><span>도면을 여는 중…</span></div>
</main>
<footer>
  세 도면은 합치지 않고 그대로 담았다 — 고른 것만 자기 문서로 열리므로 서식이 섞이지
  않고 같은 표가 두 번 나오지 않는다. 손으로 쓰지 않는다:
  <code>PYTHONPATH=src python tools/build_jbr_hub.py</code> ·
  출처 <code>docs/drawings/pv-jbr-{{scene,detail,closeup}}.html</code>
</footer>
</div>
{scripts}
<script>
(function () {{
  'use strict';
  var SHEETS = {data};
  var TOTAL = {total:g};
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
    // 띠 밑의 구간 표시 — 이 도면이 45 초 가운데 어디를 다루는지.
    var bar = el('spanBar'), lab = el('spanLabel');
    var a = meta.from / TOTAL * 100, b2 = meta.to / TOTAL * 100;
    bar.style.left = a.toFixed(3) + '%';
    bar.style.width = Math.max(0.6, b2 - a).toFixed(3) + '%';
    lab.style.left = 'calc(' + b2.toFixed(3) + '% + 6px)';
    lab.textContent = meta.from + '–' + meta.to + ' s';
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

  var start = (location.hash || '').replace('#', '');
  show(SHEETS.some(function (s) {{ return s.key === start; }}) ? start : SHEETS[0].key);
}}());
</script>
"""
    return ("<!doctype html>\n"
            "<!-- JBR-201 도면 모음: tools/build_jbr_hub.py 가 세 도면 파일을 그대로\n"
            "     담아 찍는다. 손으로 고치지 않는다 — 도면을 고치고 이것을 다시 돌린다. -->\n"
            '<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            "<title>JBR-201 정션박스·케이블 제거장치</title>\n"
            '<meta name="description" content="폐 태양광 패널 전처리 라인의 JBR-201 '
            '정션박스·케이블 제거 셀 — JB-201 인계 40 s 부터 AFR-101 인계 85 s 까지를 '
            '3D 운전 콘솔·상세도·박리 순간 클로즈업 세 도면으로 담아 골라 본다.">\n'
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
