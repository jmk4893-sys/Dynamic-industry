#!/usr/bin/env python3
"""발행 아티팩트 순회 영상을 한 장짜리 발행 페이지로 싼다.

    python3 tools/build_artifact_book_page.py out/artifact-book.mp4 \
            out/artifact-book-video.html

영상은 `tools/render_artifact_book.mjs` 가 아티팩트 페이지와 영상 두 편에서 찍는다.
여기 적은 장(章) 표는 그 도구의 CHAPTERS 와 **길이가 같아야** 하고, 그것을 mp4 헤더의
재생시간과 맞춰 확인한다 — 장 하나를 늘리고 표를 안 고치면 여기서 걸린다.
"""
from __future__ import annotations

import base64
import struct
import sys
from pathlib import Path

# [초, 제목, 설명, 아티팩트 id] — render_artifact_book.mjs 의 CHAPTERS 순서 그대로.
CHAPTERS = [
    (4, "표지", "플랜트 3D 네 벌 · 운전 콘솔 · 60분 연속 운전 · JBR-201 도면집 · "
        "벤더 DG-HK60 문서 · 영상 두 편", None),
    (6, "태양광 전처리 통합 플랜트", "투입 · JBR · AFR · 버퍼 · DG-HK60C 직결. "
        "무거운 3D 는 정한 자리에서 한 장씩 찍어 물린다 — 멈춰 선 화면을 프레임마다 "
        "다시 그릴 이유가 없다", "9e171853-6137-4428-bf65-7009b5eccf7f"),
    (12, "전처리 플랜트 전체 운전", "투입에서 유리·셀모듈 반출까지 · 72초 중 앞 12초. "
        "이미 영상인 아티팩트는 그 mp4 에서 프레임을 떠 온다",
        "30acaf84-816f-45f5-8cc3-79007029e76e"),
    (3, "C안 — 2,400×1,200 (발주처 선택)", "병목 DGM-401 52.56 s · 여유 2.17 s · "
        "브랜치 머리", "45678c2d-8ae8-4e9f-b1b5-4521877e2ceb"),
    (3, "B안 — 2,400×1,200 (벤더 상한)", "후단 순생산 60.5 장/h · 택트 55.08 s",
        "ffb9862d-a721-4a80-8e7e-335becb07443"),
    (3, "A안 — 2,500×1,400 (벤더 포락선)", "58.5 장/h · 택트 57.0 s · 패치로 보존",
        "e98bfb00-550b-45b1-9880-2125a04ca7b4"),
    (7, "MCR-901 운전 콘솔", "설비 상태 · 인터록 · 알람 · 생산 집계",
        "64d5edab-dbe7-4eb5-b8de-389238ad6359"),
    (8, "전처리 60분 연속 운전", "장비별 시간으로 병목을 세우고 흐름이 끊기는지 흘려 본다 "
        "— 병목 DGM-401 · 막힌 초 0", "83585641-115c-4cfd-8d84-6bf9ea3c6ba7"),
    (5, "JBR-201 도면집 허브", "다섯 장을 한 자리에서 고른다",
        "f3b1f4b0-009d-4df4-a68d-2f0c13d17589"),
    (10, "JBR-201 도면집 영상", "다섯 장을 고정 시간각으로 걷는다 · 66초 중 앞 10초",
        "fe206738-5f60-420f-a184-37c59b72534e"),
    (4, "DG-HK60 · IR 탠덤 PV 분리설비 3D 운전 콘솔",
        "벤더 원본 — 형상·치수·도장을 여기서 받아 적었다",
        "063a9784-6c8c-4c25-8d85-1035befed92d"),
    (5, "DG-HK60 상세설계 기술사양서 · RFQ", "인계 경계 · 공급 범위 · 확인사항 OI",
        "377241f9-3731-4e2a-aecc-178adcdb288e"),
    (4, "DG-HK60C 파일럿 시험 계획서", "무엇을 재서 무엇을 판정하는가",
        "c4e09d98-d37c-493f-8b82-0cbd368f0a61"),
    (4, "DG-HK60C 조립 지침서", "앵커 · 정렬 · 배관 · 시운전 순서",
        "613c1af7-8a2b-4868-b75b-360ab1c4591c"),
    (4, "맺음", "값이 움직이면 전부 따라 움직인다", None),
]


def mp4_seconds(path: Path) -> float:
    """mp4 헤더(moov/mvhd)에서 재생시간을 읽는다 — 외부 도구 없이 확인하려고."""
    data = path.read_bytes()
    i = data.find(b"mvhd")
    if i < 0:
        raise ValueError("mvhd 없음 — mp4 가 맞는가")
    ver = data[i + 4]
    # mvhd: type(4) version(1) flags(3) 생성(4|8) 수정(4|8) timescale(4) duration(4|8)
    if ver == 1:
        scale, dur = struct.unpack(">IQ", data[i + 24:i + 36])
    else:
        scale, dur = struct.unpack(">II", data[i + 16:i + 24])
    return dur / scale


def build(mp4: Path, out: Path) -> Path:
    secs = sum(c[0] for c in CHAPTERS)
    played = mp4_seconds(mp4)
    if abs(played - secs) > 0.5:
        raise SystemExit(f"장 표 합계 {secs} s 와 영상 {played:.1f} s 가 다르다 — "
                         "render_artifact_book.mjs 의 CHAPTERS 와 맞춰라")
    b64 = base64.b64encode(mp4.read_bytes()).decode("ascii")
    rows, t = [], 0
    for sec, head, desc, aid in CHAPTERS:
        link = (f' · <a href="https://claude.ai/code/artifact/{aid}">발행본</a>'
                if aid else "")
        rows.append(
            f'    <div class="shot"><div class="t">{t // 60:02d}:{t % 60:02d}</div>'
            f'<div><div class="h">{head}</div>'
            f'<div class="d">{desc}{link}</div></div></div>')
        t += sec
    cards = [
        ("길이", f"{secs}초", f"1280 × 720 · 15 fps · {len(b64) / 4 * 3 / 1e6:.1f} MB"),
        ("장", f"{len(CHAPTERS)}장", "표지·맺음 포함"),
        ("아티팩트", f"{sum(1 for c in CHAPTERS if c[3])}벌",
         "플랜트 · 콘솔 · 도면집 · 벤더 문서 · 영상"),
        ("걷는 방법", "네 가지", "정지컷 · 스크롤 · 필름 · 카드"),
    ]
    grid = "\n".join(
        f'    <div class="card"><div class="k">{k}</div><div class="v">{v}</div>'
        f'<div class="n">{n}</div></div>' for k, v, n in cards)
    out.write_text(TEMPLATE.format(b64=b64, shots="\n".join(rows), grid=grid,
                                   secs=secs, mb=len(b64) / 4 * 3 / 1e6),
                   encoding="utf-8")
    return out


TEMPLATE = """<title>발행 아티팩트 순회 영상</title>
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
a {{ color:var(--brand); }}
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
      <h1>발행 아티팩트를 한 편으로 걷는다</h1>
      <p class="sub">플랜트 3D 네 벌 · 운전 콘솔 · 60분 연속 운전 · JBR-201 도면집 ·
        벤더 DG-HK60 문서 · 영상 두 편</p>
    </div>
    <span class="spacer"></span>
    <div class="stamp"><b>REV.58</b>1280 × 720 · 15 fps · {secs}초 · {mb:.1f} MB</div>
  </header>

  <figure>
    <video controls playsinline preload="metadata"
      src="data:video/mp4;base64,{b64}"></video>
    <figcaption>아티팩트마다 성질이 달라 걷는 방법도 넷이다 — 무거운 3D 페이지는
      정한 자리에서 <b>한 장씩 찍어 물리고</b>, 문서·콘솔은 스크롤을 시간의 함수로 주고,
      이미 영상인 아티팩트는 <b>그 mp4 에서 프레임을 떠 오고</b>, 표지·맺음은 이 도구가
      직접 그린다. 띠에는 제목과 <code>artifact/앞8자</code> 를 적어 영상만 보고도 발행본을
      찾아갈 수 있게 했다.</figcaption>
  </figure>

  <div class="shots">
{shots}
  </div>

  <div class="grid">
{grid}
  </div>

  <p class="note"><b>영상 아티팩트는 브라우저로 다시 못 찍는다.</b> 이 크로미움에는 H.264
    디코더가 없어서(<code>DEMUXER_ERROR_NO_SUPPORTED_STREAMS</code>) 영상이 든 페이지를
    열어도 검은 화면만 나온다. 그래서 그 두 장은 페이지가 아니라 <b>mp4 에서</b> 프레임을
    뜨고 띠만 얹었다. <code>tools/render_artifact_book.mjs</code> ·
    <code>tools/build_artifact_book_page.py</code>.</p>
</div>
"""


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "out/artifact-book.mp4")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "out/artifact-book-video.html")
    print(build(src, dst))
