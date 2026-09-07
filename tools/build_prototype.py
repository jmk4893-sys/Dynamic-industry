# -*- coding: utf-8 -*-
"""BFC-101 반전 카세트 시작품 계획서를 찍는다.

정본은 `src/pv_preprocess/prototype.py` 이고, 합격 기준과 수량은 설계 모델과
제작 패키지에서 읽는다. 도판(리그 입면·일정)은 여기서 그린다.

    PYTHONPATH=src python tools/build_prototype.py

멱등이다. `tests/test_pv_prototype.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_infeed_detail import CSS, Sheet, esc, n, table  # noqa: E402

from pv_preprocess import (campaign, crane, fabrication, kinematics,  # noqa: E402
                           layout, mounting, prototype as proto, servos)

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/drawings/pv-bfc-prototype.html"

#: 리그 도판에 쓰는 임시 가드 높이 (mm) — prototype.RIG_SAFETY 의 값과 같아야 한다.
FENCE_H_MM = 2_000


# ── 도판 ────────────────────────────────────────────────────────────────
def rig_view() -> str:
    """리그 입면 X–Z. 적층 중심을 원점으로 잡는다 — 리그는 플랜트 좌표를 안 쓴다."""
    k = kinematics
    pick, dwell = k.PICK_FACE_MM, k.PICK_FACE_MM + k.SEPARATION_MM
    axis, hand = k.FLIP_AXIS_MM, k.HANDOVER_MM
    #: 링은 중심선 반지름 RING_R 에 단면 반지름 RING_TUBE 를 더한 것이 외형이다.
    #: 상세도의 링 하단 2,440 · 상단 4,420 · 외경 Ø1,980 이 이 값에서 나온다.
    ring_out = k.RING_R_MM + k.RING_TUBE_MM
    bore = 2 * (k.RING_R_MM - k.RING_TUBE_MM)
    half_pitch = k.RING_PITCH_MM // 2
    col, top = 1_600, 3_350                      # 포탈 기둥 x 위치와 상단 (A03 부품도)
    x0, x1 = -3_500, 4_800
    s = Sheet(x0, x1, -760, 5_050, 1_120, pad=(26, 216, 30, 26), flip_y=True)

    s.rect(x0, x1, -400, 0, "floor", "리그 바닥 · 앵커 기초")
    s.text(x0 + 60, -230, "리그 기초 — 콘크리트 C24 · 두께 ≥ 250 · 케미컬 앵커 M20", "lbl-muted")
    s.text(x0 + 60, -640, "리그 입면 X–Z · 단위 mm · 바닥 = 0 · 좌표는 적층 중심 기준 · 축척 NTS", "lbl-muted")

    # 포탈 기둥·크로스빔
    for x in (-col, col):
        s.rect(x - 90, x + 90, 0, top, "column", "BFC-COL-01 포탈 기둥 (박스빔 240×180)")
        s.rect(x - 250, x + 250, -20, 0, "base", "BFC-BP-01 베이스플레이트 · 레벨링 풋 · 그라우트 30")
    s.rect(-col - 90, col + 90, top, top + 260, "column", "BFC-CB-01 크로스빔 (박스빔 260×180)")
    s.text(0, top + 380, "크로스빔 — 지지롤러·구동·볼스크루가 여기 매달린다", "lbl-muted", "middle")

    # 엔드링 두 개 (측면에서는 세로 막대) — 외형은 중심선 ± 단면이다
    for x in (-half_pitch, half_pitch):
        s.rect(x - k.RING_TUBE_MM, x + k.RING_TUBE_MM, axis - ring_out, axis + ring_out, "ring",
               f"BFC-RNG-01 오픈센터 엔드링 Ø{n(2 * ring_out)} · 통과 구멍 Ø{n(bore)}")
    s.dim_x(-half_pitch, half_pitch, axis + ring_out + 380, f"링 피치 {n(k.RING_PITCH_MM)}")

    # 승강 캐리지 · 분리헤드 · 포획빔
    s.rect(-k.CARRIAGE_MM // 2, k.CARRIAGE_MM // 2, dwell - 70, dwell + 70, "carriage",
           "BFC-CAR-01 승강 캐리지 레일빔 (LM·볼스크루 구동)")
    s.rect(-1_090, 1_090, dwell + 90, dwell + 170, "sep", "BFC-SEP-01 분리헤드 빔 · 진공컵 4")
    s.rect(-1_450, 1_450, 2_020 - 30, 2_020 + 30, "safety", "A04 포획빔 4열 — 낙하 포획")

    # 적층 시험대 (LFT 대체)
    s.rect(-1_450, 1_450, 0, 520, "base", "적층 시험대 — 전동 스크루 잭 (LFT-101 대체)")
    s.rect(-k.PANEL_MM[0] // 2, k.PANEL_MM[0] // 2, 520, pick, "panel", "폐패널 적층 10장 — 최상단이 픽업면")
    s.text(0, (520 + pick) / 2, "시료 적층 10장", "lbl-panel", "middle", dy=4)

    # 인계 확인대 (로봇 대체)
    s.rect(2_550, 4_350, 0, hand - 60, "rack", "인계 확인대 — RB-101 대체 · 로드셀·다이얼")
    s.rect(2_550, 4_350, hand - 60, hand, "deck", "받이면 (인계 높이)")
    s.text(3_450, hand + 170, "인계 확인대 (로봇 대체)", "lbl", "middle")

    # 임시 가드
    for x in (-3_200, 4_500):
        s.rect(x - 30, x + 30, 0, FENCE_H_MM, "wall", f"임시 메시 가드 {n(FENCE_H_MM)} H")
    s.text(-3_170, 1_200, f"임시 가드 {n(FENCE_H_MM)} H", "lbl-muted")

    # 시험이 재는 세 행정
    # 치수 글자는 서로 겹치지 않게 좌·우로 번갈아 낸다.
    s.dim_y(pick, dwell, -1_900, f"안전분리 {n(k.SEPARATION_MM)}", right=False)
    s.dim_y(dwell, axis, -2_400, f"승강 {n(axis - dwell)}")
    s.dim_y(axis, hand, -2_900, f"하강 {n(axis - hand)}", right=False)

    # 레벨 — 라벨이 겹치면 아래로 민다 (실선은 참값에 그대로 둔다)
    levels = [(axis + ring_out, f"링 상단 {n(axis + ring_out)}"),
              (axis, f"반전축 {n(axis)}"),
              (axis - ring_out, f"링 하단 {n(axis - ring_out)}"),
              (dwell, f"대기면 {n(dwell)}"),
              (hand, f"로봇 인계 {n(hand)}"),
              (2_020, "포획빔 전개 2,020"),
              (pick, f"픽업면 {n(pick)} (고정)")]
    last = None
    for z, label in levels:
        s.line(x0, z, x1, z, "level")
        py = s.Y(z)
        if last is not None and py - last < 17:
            py = last + 17
        last = py
        s.text(x1, z, label, "lvl", "start", dx=12, dy=py - s.Y(z) + 3)
    return s.svg("BFC 시작품 리그 입면")


def schedule_view() -> str:
    """단계 막대. 주 단위 누적이라 어느 관문이 언제 오는지 한눈에 보인다."""
    total = proto.total_weeks()
    s = Sheet(0, total, 0, len(proto.STAGES) + 1.2, 1_120, pad=(28, 150, 26, 74))
    for w in range(0, total + 1, 2):
        s.line(w, 0, w, len(proto.STAGES) + 0.2, "level")
        s.text(w, -0.35, f"{w}", "tick", "middle")
    s.text(total / 2, len(proto.STAGES) + 1.0, f"주 (총 {total}주)", "lbl-muted", "middle")
    at = 0
    for i, st in enumerate(proto.STAGES):
        y = i + 0.2
        s.rect(at, at + st.weeks, y, y + 0.62, "panel", f"{st.gate} {st.name} — {st.weeks}주")
        s.text(-2, y + 0.31, st.gate, "lbl", "end", dy=4)
        s.text(at + st.weeks / 2, y + 0.31, f"{st.name} {st.weeks}주", "lbl-small", "middle", dy=4)
        at += st.weeks
    return s.svg("시작품 일정")


# ── 표 ──────────────────────────────────────────────────────────────────
def questions_table() -> str:
    rows = [[f"<code>{esc(q.no)}</code>", esc(q.ask), esc(q.why), esc(q.fails)] for q in proto.QUESTIONS]
    return table(["번호", "질문", "왜 도면으로 못 닫는가", "'아니오' 면 무엇이 바뀌는가"], rows)


def scope_table() -> str:
    rows = [["만든다", esc(x.what), esc(x.detail)] for x in proto.IN_SCOPE]
    rows += [["안 만든다", esc(x.what), esc(x.detail)] for x in proto.OUT_OF_SCOPE]
    return table(["구분", "항목", "내용·이유"], rows)


def substitutes_table() -> str:
    rows = [[esc(a), esc(b), esc(c)] for a, b, c in proto.SUBSTITUTES]
    return table(["플랜트 사양", "시작품 대체", "그래도 결과가 옮겨가는 이유"], rows)


def stages_table() -> str:
    at, rows = 0, []
    for st in proto.STAGES:
        at += st.weeks
        rows.append([f"<code>{esc(st.gate)}</code>", esc(st.name), str(st.weeks), str(at),
                     esc(st.work), esc(st.exit)])
    return table(["관문", "단계", "기간 (주)", "누적 (주)", "하는 일", "넘어가는 조건"], rows, "", (2, 3))


def tests_table() -> str:
    rows = [[f"<code>{esc(t.tag)}</code>", f"<code>{esc(t.question)}</code>", esc(t.name), esc(t.method),
             esc(t.instrument), esc(t.runs), esc(t.criterion), f"<code>{esc(t.source)}</code>"]
            for t in proto.TESTS]
    return table(["시험", "질문", "이름", "방법", "계측", "횟수", "합격 기준", "기준 출처"], rows)


def specimen_table() -> str:
    rows = [[esc(k), str(v), esc(w)] for k, v, w in proto.specimen_mix()]
    return table(["구분", "매수", "근거"], rows, "", (1,))


def safety_table() -> str:
    return table(["항목", "내용"], [[esc(a), esc(b)] for a, b in proto.RIG_SAFETY])


def cost_table() -> str:
    rows = [[esc(c.group), esc(c.item), esc(c.qty), esc(c.basis), "견적 대상"] for c in proto.cost_lines()]
    return table(["구분", "항목", "수량", "산출 근거", "단가"], rows)


def risk_table() -> str:
    return table(["위험", "크기", "대응"], [[esc(a), esc(b), esc(c)] for a, b, c in proto.RISKS])


def feedback_table() -> str:
    return table(["모델 자리", "지금 값의 성격", "채우는 시험"],
                 [[f"<code>{esc(a)}</code>", esc(b), f"<code>{esc(c)}</code>"] for a, b, c in proto.FEEDBACK])


def coverage_table() -> str:
    cov = proto.questions_are_covered()
    rows = []
    for q in proto.QUESTIONS:
        tests = " · ".join(t.tag for t in proto.TESTS if t.question == q.no)
        ok = '<b class="ok">닫힘</b>' if cov[q.no] else '<b class="bad">시험 없음</b>'
        rows.append([f"<code>{esc(q.no)}</code>", esc(q.ask), esc(tests), ok])
    return table(["질문", "내용", "시험", "판정"], rows)


# ── 문서 ────────────────────────────────────────────────────────────────
EXTRA_CSS = """
.ok { color: var(--green); }
.bad { color: var(--red); }
.gate { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 0; }
.gate dt { font-weight: 600; }
.gate dd { margin: 0; }
.callout { border-left: 3px solid var(--blue); background: var(--tint); padding: 12px 16px; margin: 0; }
.callout p { margin: 0 0 8px; } .callout p:last-child { margin: 0; }
ol.q { margin: 0; padding-left: 20px; } ol.q li { margin-bottom: 6px; max-width: 90ch; }
"""


def build() -> str:
    s = proto.summary()
    k = kinematics
    a3 = fabrication.assembly("PV-FAB-A03")
    a4 = fabrication.assembly("PV-FAB-A04")
    lift = crane.governing_lift()
    anchors = sum(x.count * (x.units if x.per_unit else 1)
                  for m in mounting.MOUNTINGS if m.station == "bfc" for x in m.anchors)
    axes = [x for x in servos.SERVO_AXES if x.tag in ("AXIS-BFC-R", "AXIS-BFC-Z", "AXIS-CD-Z")]
    bfc_s = k.PATH[-1][1] - k.PATH[0][0]
    side = k.cage_axial_clearance_mm()

    parts: list[str] = [
        "<!doctype html>",
        "<!-- 이 파일은 손으로 쓰지 않는다. 정본은 src/pv_preprocess/prototype.py 이고 "
        "tools/build_prototype.py 가 찍는다. -->",
        '<html lang="ko"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>BFC-101 반전 카세트 시작품 계획</title>",
        f"<style>{CSS}{EXTRA_CSS}</style>",
        "</head><body>",
        '<main class="page">',

        # 표제
        '<header class="title"><div>',
        '<div class="eyebrow">DYNAMIC INDUSTRY · 태양광 패널 전처리 플랜트 · 시작품 계획 · REV.A</div>',
        "<h1>BFC-101 반전 카세트 시작품 — 라인을 짓기 전에 한 대만 만든다</h1>",
        "<p>이 라인 전체가 서 있는 가정은 하나다. 적층에서 45 kg 패널 한 장을 진공으로 떼어, "
        f"두 링 사이로 {n(k.FLIP_AXIS_MM - (k.PICK_FACE_MM + k.SEPARATION_MM))} mm 올려, 180° 돌려, "
        f"인계 높이 {n(k.HANDOVER_MM)} mm 에 내려놓을 수 있다는 것. 이 가정이 참이면 나머지는 돈과 일정 "
        "문제이고, 거짓이면 나머지 설계는 값이 없다. 그래서 BFC 한 Bay 만 만들어 그 가정을 시험한다.</p>",
        "</div>",
        '<dl class="block">',
        f'<dt>리그</dt><dd class="mono">{esc(proto.RIG)}</dd>',
        f'<dt>베끼는 도면</dt><dd class="mono">{esc(" · ".join(proto.SOURCE_SHEETS))}</dd>',
        f"<dt>규모</dt><dd>Bay {s['bays']}식 · 제작품 {n(s['fabricated_kg'])} kg</dd>",
        f"<dt>기간</dt><dd>{s['weeks']}주 (G0 – G6)</dd>",
        f"<dt>시험</dt><dd>{s['tests']}건 · 시료 {s['specimens']}장</dd>",
        '<dt>생성</dt><dd class="mono">tools/build_prototype.py</dd>',
        "</dl></header>",

        # 왜
        '<section id="why"><h2>왜 시작품인가</h2>',
        '<div class="callout">',
        "<p>제작 도면집은 설계실 출도본이다. 자리와 높이는 검증된 모델에서 왔지만, 단면과 볼트는 "
        "관례와 하중에서 고른 계획값이고 <b>공정 자체가 실물로 증명된 적이 없다</b>. "
        "폐패널은 새 패널이 아니다 — 표면에 먼지와 수분이 있고, 프레임이 휘어 있고, 유리에 이미 "
        "미세 균열이 있다. 진공으로 한 장만 떨어지는지는 계산으로 나오지 않는다.</p>",
        f"<p>플랜트를 통째로 발주하면 이 질문의 답을 {s['weeks']}주가 아니라 훨씬 뒤에, 훨씬 비싸게 "
        "알게 된다. 시작품은 그 답을 먼저 사는 것이다.</p>",
        "</div>",
        "<h3>이 계획이 닫는 질문</h3>",
        questions_table(),
        "</section>",

        # 범위
        '<section id="scope"><h2>범위 — 무엇을 만들고 무엇을 만들지 않는가</h2>',
        "<p>증명에 필요한 것만 만든다. 안 만드는 것에도 이유를 적었다 — 안 적으면 다음 사람이 다시 논의한다.</p>",
        scope_table(),
        "<h3>대체품</h3>",
        "<p>플랜트 사양 대신 쓰는 것이 있다. 인터페이스가 같으면 시험 결과는 플랜트로 옮겨간다.</p>",
        substitutes_table(),
        "</section>",

        # 리그
        '<section id="rig"><h2>리그 구성</h2>',
        rig_view(),
        "<p class=\"note\">포탈·링·캐리지·조는 제작 도면집 그대로 만든다. 여기를 줄이면 강성과 관성이 "
        "달라져 시험 결과가 플랜트로 옮겨가지 않는다. 대신 리프트는 스크루 잭 시험대로, 로봇은 "
        "고정 인계 확인대로 바꾼다 — 둘 다 이번 질문의 대상이 아니다.</p>",
        table(["항목", "값"], [
            ["제작품", f"{n(s['fabricated_kg'])} kg · {s['part_kinds']}종 (A03 {n(a3.fabricated_weight_kg())} + A04 {n(a4.fabricated_weight_kg())})"],
            ["엔드링", f"Ø{n(2 * (k.RING_R_MM + k.RING_TUBE_MM))} · 통과 구멍 Ø{n(2 * (k.RING_R_MM - k.RING_TUBE_MM))} · 1개 {n(next(p.weight_kg() for p in a3.parts if p.tag == 'BFC-RNG-01'))} kg · 2개"],
            ["상용품", f"{s['commercial_items']}품목"],
            ["체결", f"볼트 {n(s['bolts'])} · 앵커 {anchors} (M20 케미컬)"],
            ["구동", " · ".join(f"{a.tag} {a.rated_kw:g} kW" for a in axes)],
            ["설계 중량 하한", f"{n(lift.mass_kg)} kg (발주처 확인 · T-11 이 실측으로 대체한다)"],
            ["카세트 외형", " × ".join(n(v) for v in layout.STATIONS["bfc"].envelope)],
        ], "kv"),
        "</section>",

        # 단계
        '<section id="stages"><h2>단계와 관문</h2>',
        schedule_view(),
        "<p class=\"note\">관문은 통과 조건이지 일정 표시가 아니다. G0 을 못 넘으면 발주하지 않는다 — "
        "구조 계산 없이 강재를 자르면 시작품이 아니라 그냥 비싼 고철이 된다.</p>",
        stages_table(),
        "</section>",

        # 시험
        '<section id="tests"><h2>시험 계획</h2>',
        "<p>합격 기준은 전부 설계 모델에서 왔다. 시작품이 증명할 것은 도면이 이미 적어 놓은 값이지, "
        "시험하며 새로 정하는 값이 아니다. 기준을 못 맞추면 시작품이 아니라 도면이 틀린 것이다.</p>",
        tests_table(),
        "<h3>질문 대 시험 — 빠진 것이 없는가</h3>",
        coverage_table(),
        "<h3>시료</h3>",
        f"<p>실 폐패널 {s['specimens']}장. 구성비는 60장 캠페인 로스터를 그대로 늘렸다 — "
        "새 패널로 시험하면 이 계획의 목적이 사라진다.</p>",
        specimen_table(),
        "</section>",

        # 안전
        '<section id="safety"><h2>리그 안전</h2>',
        "<p>시작품은 인증 설비가 아니다. 안전 부품 PFHd 가 없어 SISTEMA 계산이 성립하지 않는다. "
        "그래서 사람을 기계에서 떼어 놓는 것으로 대신한다.</p>",
        safety_table(),
        "</section>",

        # 비용
        '<section id="cost"><h2>수량 산출</h2>',
        "<p><b>단가는 비워 둔다.</b> 수량과 사양은 모델과 제작 패키지에서 그대로 나오지만 값은 "
        "G0 관문의 3사 견적으로 채운다. 지어낸 단가를 적으면 그 숫자가 계획을 끌고 다닌다.</p>",
        cost_table(),
        "</section>",

        # 위험
        '<section id="risk"><h2>위험과 대응</h2>',
        risk_table(),
        "</section>",

        # 반영
        '<section id="feedback"><h2>시작품이 설계 모델에 돌려주는 것</h2>',
        "<p>시험은 합격·불합격만 내는 것이 아니라 지금 계획값으로 들어가 있는 자리를 실측값으로 "
        "바꾼다. 그것이 이 시작품의 두 번째 산출물이다.</p>",
        feedback_table(),
        "</section>",

        # 판정
        '<section id="verdict"><h2>판정</h2>',
        '<div class="callout">',
        f"<p><b>가는 조건</b> — 시험 {s['tests']}건 전항 합격. 특히 T-01(단장 분리 100 %), "
        f"T-04(편측 여유 {side:g} mm 유지), T-07(신규 균열 0), "
        f"T-09(BFC 구간 {bfc_s:g} s 이내). 이 넷이 라인 설계의 전제다.</p>",
        "<p><b>조건부</b> — 기준을 못 맞추지만 원인이 밝혀지고 대책이 리그에서 검증되면, "
        "설계 모델을 고치고 해당 시험만 다시 돈다. 택트가 늘면 "
        f"방출 주기 {campaign.release_takt_s():g} s 와 라인 처리량을 다시 계산한다.</p>",
        "<p><b>안 가는 조건</b> — 진공 분리가 폐패널에서 성립하지 않거나(Q1), 반전 중 유리 파손이 "
        "반복되면(Q4) 이 공정 구성 자체를 다시 놓는다. 그때 잃는 것은 시작품 한 대이지 플랜트가 아니다.</p>",
        "</div>",
        "</section>",
        "</main></body></html>",
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024:.1f} kB")


if __name__ == "__main__":
    main()
