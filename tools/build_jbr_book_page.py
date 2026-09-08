#!/usr/bin/env python3
"""JBR-201 도면집 영상을 한 장짜리 발행 페이지로 싼다.

    python3 tools/build_jbr_book_page.py out/jbr-book.mp4 out/jbr-book-video.html

영상 자체는 `tools/render_jbr_book.mjs` 가 도면 다섯 장을 고정 시간각으로 걸어
찍는다. 이 스크립트는 그 결과를 base64 로 페이지 안에 넣고, 어느 초에 어느
도면을 보고 있는지를 장(章) 표로 적는다. mp4 를 밖에 두면 아티팩트로 발행할 때
따라가지 못하므로 반드시 안에 넣는다.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pv_preprocess import campaign  # noqa: E402

# [시작 초, 제목, 설명] — render_jbr_book.mjs 의 CHAPTERS 와 길이가 같아야 한다.
CHAPTERS = [
    (0, "3D 운전 — 40 → 85 s",
     "도면의 시계 훅을 40 s 에서 85 s 까지 민다. 카메라는 여섯 샷으로 나뉜다 — "
     "셀 전경(00:00) · JB-201 인계부(00:03) · 1헤드 L칼날(00:07) · "
     "진공 포획(00:11) · 상부 시점(00:14) · AFR-101 인계(00:17)."),
    (20, "상세도 — 움직임이 어떤 값에서 나왔는가",
     "입면과 레벨, 헤드 행정, 칼날 진입각, 가위 A→B 순서를 각각 원본 식 옆에 적은 시트다. "
     "값을 바꾸면 3D 도 같이 움직인다."),
    (32, "근접도 — 두 배율",
     "세 장면(박스 박리 · 전선 포획·절단 · 수거함 배출)을 전경 하나와 실척 근접 하나로 "
     "나눠 그린다. 여섯 칸을 같은 길이로 밟는다."),
    (44, "제작 도면집 — 부품도 · 구멍 · 체결표",
     "가공 도면, 구매품, 볼트 토크·구멍 표까지. 발주서에 그대로 옮겨 적을 수 있는 자리다."),
    (54, "물리 시뮬레이션 — 진공이 끊긴 뒤",
     "박스가 손을 떠난 뒤로는 아무도 자세를 정해 주지 않는다. 낙하·충돌·튀어오름을 "
     "적분해 수거함 안에 남는지를 본다."),
]


def build(mp4: Path, out: Path) -> Path:
    b64 = base64.b64encode(mp4.read_bytes()).decode("ascii")
    secs = 66
    scene = Path("docs/drawings/pv-jbr-scene.html").read_text(encoding="utf-8")
    heads = int(re.search(r"var HEAD_COUNT = (\d+);", scene).group(1))
    per_box = float(re.search(r"박스당 ([\d.]+) s", scene).group(1))
    shots = "\n".join(
        f'    <div class="shot"><div class="t">{s // 60:02d}:{s % 60:02d}</div>'
        f'<div><div class="h">{h}</div><div class="d">{d}</div></div></div>'
        for s, h, d in CHAPTERS
    )
    cards = [
        ("헤드", f"{heads}개", "공통 브리지 · 박스마다 순차 제거"),
        ("셀 점유", f"{campaign.JBR_S:.0f} s",
         f"JB-201 인계 {campaign.INFEED_S:.0f} s → AFR-101 인계 "
         f"{campaign.INFEED_S + campaign.JBR_S:.0f} s"),
        ("박스당", f"{per_box:.1f} s", "박리 · 전선 절단 · 호퍼 적재"),
        ("도면", f"{len(CHAPTERS)}장", "3D · 상세 · 근접 · 제작 · 물리"),
    ]
    grid = "\n".join(
        f'    <div class="card"><div class="k">{k}</div><div class="v">{v}</div>'
        f'<div class="n">{n}</div></div>' for k, v, n in cards
    )
    html = TEMPLATE.format(b64=b64, shots=shots, grid=grid, secs=secs,
                           mb=len(b64) / 4 * 3 / 1e6)
    out.write_text(html, encoding="utf-8")
    return out


TEMPLATE = """<title>JBR-201 도면집 영상</title>
<style>
:root {{
  color-scheme: light;
  --ink:#16191c; --dim:#5d6874; --line:#d9dee2; --paper:#f4f5f3; --card:#ffffff;
  --brand:#228CC9; --accent:#FECA4A; --steel:#3d474d;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --ink:#e9edf1; --dim:#9aa6b1; --line:#2a323c; --paper:#0d1116; --card:#161b22; }} }}
:root[data-theme="dark"] {{ --ink:#e9edf1; --dim:#9aa6b1; --line:#2a323c;
  --paper:#0d1116; --card:#161b22; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font:15px/1.65 system-ui,-apple-system,"Segoe UI","Noto Sans KR",sans-serif; }}
.wrap {{ max-width:1120px; margin:0 auto; padding:26px 20px 60px; }}
header {{ display:flex; gap:16px; align-items:flex-start; flex-wrap:wrap;
  padding-bottom:16px; border-bottom:2px solid var(--steel); }}
h1 {{ margin:0; font-size:23px; font-weight:650; letter-spacing:-.01em; }}
.sub {{ margin:5px 0 0; color:var(--dim); font-size:13.5px; }}
.spacer {{ flex:1 1 auto; }}
.stamp {{ font:600 12px/1.5 var(--mono); color:var(--dim); text-align:right; }}
.stamp b {{ display:block; font-size:15px; color:var(--ink); }}
figure {{ margin:20px 0 0; }}
video {{ width:100%; display:block; border:1px solid var(--line);
  border-radius:8px; background:#000; }}
figcaption {{ margin-top:9px; color:var(--dim); font-size:13px; }}
.shots {{ margin:22px 0 0; border-top:1px solid var(--line); }}
.shot {{ display:grid; grid-template-columns:64px 1fr; gap:16px; padding:12px 2px;
  border-bottom:1px solid var(--line); align-items:baseline; }}
.shot .t {{ font:600 13px/1.5 var(--mono); color:var(--brand); }}
.shot .h {{ font-weight:600; }}
.shot .d {{ color:var(--dim); font-size:13.5px; margin-top:2px; }}
.grid {{ display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(178px,1fr));
  margin:22px 0 0; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:8px;
  padding:12px 13px; }}
.card .k {{ color:var(--dim); font-size:12px; }}
.card .v {{ font:650 20px/1.3 var(--mono); margin-top:2px; }}
.card .n {{ color:var(--dim); font-size:12px; margin-top:3px; }}
.note {{ margin:22px 0 0; padding:13px 15px; background:var(--card);
  border:1px solid var(--line); border-left:3px solid var(--accent);
  border-radius:0 8px 8px 0; font-size:13.5px; }}
code {{ font:12.5px/1.5 var(--mono); background:rgba(127,127,127,.13);
  padding:1px 5px; border-radius:4px; }}
</style>
<div class="wrap">
  <header>
    <div>
      <h1>JBR-201 도면집 — 다섯 장을 한 편으로 걷는다</h1>
      <p class="sub">3D 운전 · 상세도 · 근접도 · 제작 도면집 · 물리 시뮬레이션</p>
    </div>
    <span class="spacer"></span>
    <div class="stamp"><b>REV.57</b>1280 × 720 · 15 fps · {secs}초 · {mb:.1f} MB</div>
  </header>

  <figure>
    <video controls playsinline preload="metadata"
      src="data:video/mp4;base64,{b64}"></video>
    <figcaption>화면 녹화가 아니다. 장마다 <b>고정 시간각</b>을 밟는다 — 3D 는 도면의 시계 훅을
      한 프레임씩 밀고, 물리는 적분을 <code>1/15 s</code> 씩 진행하며, 근접도는 rAF 와
      <code>performance.now</code> 를 가상 시계로 갈아 끼운다. 그래서 몇 번을 찍어도 같은
      영상이 나온다.</figcaption>
  </figure>

  <div class="shots">
{shots}
  </div>

  <div class="grid">
{grid}
  </div>

  <p class="note"><b>도면이 바뀌면 영상이 바뀐다.</b> 이 영상은 발행된 도면 다섯 장을 그대로
    열어 찍은 것이다 — 따로 만든 애니메이션이 아니다. 값이 움직이면 같은 명령이 다른 영상을
    낸다. <code>tools/render_jbr_book.mjs</code> · <code>tools/build_jbr_book_page.py</code>.</p>
</div>
"""


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "out/jbr-book.mp4")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "out/jbr-book-video.html")
    print(build(src, dst))
