"""옵션 DG-HK120C 해석 — 표준의 검토를 옵션 설비로 다시 풀고, 옵션에만 있는 것을 더 본다.

옵션은 따로 해석하지 않는다. 표준의 구조 · 열 · IR 뱅크 · 열수지 · 에어록 · 램프 지지 ·
사이클 검토를 **같은 코드로** 옵션의 뿌리 값(7단 · 96등 · 셀 2)에서 다시 푼다
(tools/variant.py). 그래서 이 모듈이 하는 일은 셋뿐이다:

  ① 같은 검토의 표준 값과 옵션 값을 나란히 놓는다 (compare)
  ② 옵션에만 있는 부재를 본다 — 런웨이 최장 경간 · 횡이송 캔틸레버 · 수전 (extra)
  ③ 옵션이 새로 만든 요구를 적는다 (requirements)

옵션을 풀다가 드러난 결정 셋이 여기서 나온다. **SSR 상한** — 단당 램프가 많아 작은
패널에서 백시트가 녹는다(T5). **회전 너트** — 택트가 반이고 행정이 길어 승강축이 공진에
막힌다(CY4 · CY5 · 표준에도 해당). **12 등 배치** — 뱅크당 12 등의 위치를 다시 푼다(IR4).
"""

from __future__ import annotations

import importlib
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import variant  # noqa: E402
from analysis_thermal import Req, Result  # noqa: E402

LID = "twin"
GROUPS = (
    ("구조", "analysis_structural"),
    ("열", "analysis_thermal"),
    ("IR 뱅크", "analysis_irbank"),
    ("램프 지지", "lampmount"),
    ("열수지", "heatbalance"),
    ("에어록", "airlock"),
    ("사이클", "analysis_cycle"),
)
_TW = variant.load(LID, *(m for _, m in GROUPS), "parts", "electrical", "fab_spec", "cycle")
PT_T, EL_T, F_T, CY_T = _TW["parts"], _TW["electrical"], _TW["fab_spec"], _TW["cycle"]


def pinned():
    return variant.pinned(LID)


def _results(mod):
    r = mod.run()
    return list(r[0] if isinstance(r, tuple) else r)


def compare() -> list[tuple[str, Result | None, Result]]:
    """(분야, 표준 결과, 옵션 결과) — 같은 검토를 두 설비로 푼 것. 옵션에만 있는 검토는 표준이 None."""
    out = []
    for name, m in GROUPS:
        base = {r.id: r for r in _results(importlib.import_module(m))}
        with pinned():
            rt = _results(_TW[m])
        out.extend((name, base.get(r.id), r) for r in rt)
    return out


# ── 옵션에만 있는 부재 ────────────────────────────────────────────────
def _cantilever():
    """EX·GL 횡이송 캔틸레버 끝 처짐 — 끝에 선 캐리지 · 포크 유닛 · 패널."""
    b = {p.pid: p for p in PT_T.P}
    sec = b["P-003-21"].shape.d
    h, bb, t = sec["h"], sec["b"], sec["t"]
    i_ = (bb * h ** 3 - (bb - 2 * t) * (h - 2 * t) ** 3) / 12
    tip_kg = (b["P-003-25"].kg + b["P-003-27"].kg + b["P-003-26"].kg + 4 * b["P-003-24"].kg
              + F_T.W_PANEL * 1000 / 9.81)
    p_n = tip_kg * 9.81 * 1.2                        # 급정지 1.2 (포크와 같은 계수)
    w = b["P-003-21"].kg / PT_T.TR_L * 9.81          # N/mm 자중
    L = PT_T.TR_L
    e = 205000.0
    return (p_n * L ** 3 / (3 * e * i_) + w * L ** 4 / (8 * e * i_)), tip_kg, i_


def extra() -> list[tuple[str, Result, Result | None]]:
    """(분야, 옵션 결과, 표준 결과) — 옵션이 새로 세우거나 크게 바꾼 부재 · 수전."""
    import electrical as EL_B
    import parts as PT_B
    out = []

    def runway(pt):
        return Result("S15", "RH-201 런웨이 처짐 (최장 경간)", pt.RH_DEFL, "mm", pt.RH_SPAN / 500,
                      f"L/500 — 경간 {pt.RH_SPAN:,.0f} (호이스트 정격 250 kg + 트롤리 · 중앙 집중 + 자중)",
                      f"H-{pt.RH_SEC[0]}×{pt.RH_SEC[1]} · 기둥 {len(pt.RH_POSTS)} · 본선 {pt._RH_L:,.0f}"
                      + (f" ({pt.RH_N} 토막)" if pt.RH_N > 1 else "")
                      + " — 가장 가벼운 단면부터 대 보아 처음 드는 것을 골랐다")
    with pinned():
        out.append(("구조", runway(PT_T), runway(PT_B)))
        d, tip, i_ = _cantilever()
        out.append(("구조", Result(
            "S16", "횡이송 캔틸레버 끝 처짐", d, "mm", 1.0,
            "조립 지침 M-003 7단계의 허용 1 mm — 셀 위 정지점 핀이 물리는 범위",
            f"캔틸레버 {PT_T.TR_L:,.0f} · □-260×180×9 (I {i_ / 1e6:.1f}×10⁶ mm⁴) · 끝 하중 {tip:.0f} kg × 급정지 1.2 "
            f"+ 자중. 캔틸레버는 제 기둥에서 셀 쪽으로만 나간다"), None))

        def power(el, lab):
            s_ = el.summary()
            return (Result("E1", "주차단기 여유 (FLA × 1.25 ≤ AT)", s_["fla"] * 1.25, "A", s_["main_at"],
                           f"주차단기 {s_['main_at']} AT / {s_['main_af']} AF — 콘솔 E-001 과 같은 선정 규칙",
                           f"{lab} 연결 {s_['kw']:.0f} kW · {s_['kva']:.1f} kVA · 역률 {s_['pf']:.3f} → "
                           f"FLA {s_['fla']:.0f} A · 분기 {s_['branches']}"),
                    Result("E2", "변압기 부하율", s_["kva"], "kVA", 0.80 * s_["tr_kva"],
                           f"{s_['tr_kva']:.0f} kVA 의 80 % — 표준 용량 중 부하율 80 % 안의 최소",
                           f"{lab} 수전 용량을 발주처가 준비한다 — 부하율 {s_['tr_load']:.0%}"),
                    Result("E3", "예상 단락전류 × 1.2 ≤ SCCR", s_["isc_ka"][1] * 1.2, "kA", s_["sccr_ka"],
                           f"기기 단락정격 {s_['sccr_ka']} kA",
                           f"임피던스 5~6 % 무한모선 — 상위 계통을 무시하므로 보수측"))
        pt_, pb_ = power(EL_T, "옵션"), None
    pb_ = power(EL_B, "표준")
    out.extend(("전기", t_, b_) for t_, b_ in zip(pt_, pb_))
    return out


def requirements() -> list[Req]:
    import analysis_thermal as TH_B
    with pinned():
        th = _TW["analysis_thermal"]
        _, df = th.dwell_floor()
        _, cw = th.chamber_wall()
        ir = _TW["analysis_irbank"]
        ssr_min = th.ssr_cap(th.CY.RANGE["panelLength"][0] * th.CY.RANGE["panelWidth"][0] / 1e6)
        ssr_std = th.ssr_cap(th.PANEL_A)
        cyc, cex = _TW["analysis_cycle"].run()
        s5 = {r.id: r for r in _results(_TW["analysis_structural"])}["S5"]
        al = {r.id: r for r in _results(_TW["airlock"])}
        e = EL_T.summary()
        pos = "·".join(f"{x * 1000:.0f}" for x in ir.NEW_X if x > 0)
    return [
        Req("RO1", "IR 뱅크 SSR 출력 상한 — 패널 면적으로",
            f"흡수유속 ≤ {TH_B.Q_CORNER_STD:,.0f} W/m² · 최소 패널에서 {ssr_min:.0%} · 기본 패널 {ssr_std:.0%}",
            "PLC 레시피 · SSR-B 분기 · 사양서 1.4 옵션 조항",
            f"옵션은 단당 램프가 {PT_T.LAMPS / PT_T.DECKS:.1f} 등(표준 {TH_B.LAMPS / TH_B.DECKS:.1f})이라 입력구간 "
            f"모서리에서 유속이 {df['q_raw']:,.0f} W/m² 로 올라 백시트가 PVDF 융점을 넘는다. 표준이 검증한 "
            f"모서리 유속에 뱅크 출력을 묶으면 T5 가 표준과 같아진다 — 기본 패널에서는 상한이 풀려 "
            f"처리량을 건드리지 않는다"),
        Req("RO2", "승강축 회전 너트 · 등급 한 단계 위",
            f"{PT_T.FORK_LIFT_V:.2f} m/s · 리드 {PT_T.FORK_LEAD:.0f} · 너트 {PT_T.FORK_NUT_RPM:,.0f} rpm",
            "상세설계 · M-003 · 구매 사양 P-003-07",
            f"택트가 {CY_T.TAKT:.1f} s 로 반이고 최장 승강이 {PT_T.LIFT_MAX:,.0f} 이라 LI·GU 사이클이 "
            f"택트의 {cyc[[r.id for r in cyc].index('CY4')].util:.0%} 다. 스크류를 돌리는 종전 방식이면 "
            f"{cex['t_old']:.0f} s 로 택트의 {cex['t_old'] / CY_T.TAKT:.0f} 배다"),
        Req("RO3", "IR 뱅크 12 등 배치",
            f"±{pos} mm · 인접 뱅크 동일 위치", "M-002 · 콘솔 LAMP_POS[12]",
            f"뱅크당 램프가 12 등이라 8 등 배치를 못 쓴다 — IR.optimize(12) 로 다시 풀었다. 면내 편차가 "
            f"표준의 절반이다 (램프가 촘촘하다). 파일럿 PT-04 는 표준 8 등으로 하므로 옵션 FAT 에서 열화상으로 "
            f"확인한다"),
        Req("RO4", "수전 — 주회로 · 변압기",
            f"{e['kw']:.0f} kW · {e['main_at']} AT/{e['main_af']} AF · 변압기 {e['tr_kva']:.0f} kVA · SCCR {e['sccr_ka']} kA",
            "발주처 수전 · E-001 옵션 · MCC 2면",
            f"분기를 셀 수만큼 둔다 — 한 분기 IR-DB1 4P 200A 에 96 등 240 kW 를 걸 수 없다. 서보·VFD 와 "
            f"보조 분기를 통째로 곱한 것은 보수측이다 (공용 포크 몫이 두 번 세지는 대신 횡이송 8 축이 먹는다)"),
        Req("RO5", "가열실 지진 층간변위 — 여유 6 %",
            f"{s5.value:.1f} / {s5.limit:.1f} mm ({s5.util:.0%})", "구조 상세설계 · M-002",
            f"7 단 랙은 높이 {PT_T.RACK_TOP:,.0f} 에 자중 {F_T.M_CHAMBER / 1000:.1f} t 라 H/200 을 거의 다 쓴다. "
            f"외피를 가새로 쓰지 않는 개념 모델의 값이다 — 상세설계에서 외피 판의 전단 강성을 넣거나 "
            f"단부에 가새를 둔다"),
        Req("RO6", "에어록은 표준 확정안 C 를 그대로",
            f"확정안 C {al['AL3'].value:.1f} kW ({al['AL3'].util:.0%}) · 단 피치 개구 B {al['AL2'].value:.1f} kW ({al['AL2'].util:.0%})",
            "상세설계 · M-002 셔터",
            f"옵션은 셔터가 {PT_T.SHUTTERS} 장이고 개폐가 두 배라 에어록 손실도 두 배지만, 처리량이 두 배라 "
            f"η 를 지키는 에어록 몫도 {al['AL3'].limit:.1f} kW 로 함께 커진다 — 단 피치 개구(B)도 한계 안이다. "
            f"그래도 표준의 패널 포락선 개구(C)를 그대로 쓴다: 셔터 판·씰·실린더가 표준 도면 그대로이고, "
            f"B 는 여유가 {1 - al['AL2'].util:.0%} 뿐이라 씰 열화 한 번에 넘는다"),
        Req("RO7", "횡이송 왕복 실측 (검토서 OI-T2)",
            f"캐리지 {cex['t_tr']:.1f} s / 셀 사이클 {cex['cell_cycle']:.1f} s · EX·GL {cex['t_ex']:.1f} s / 택트 {CY_T.TAKT:.1f} s",
            "옵션 FAT · 운전 시퀀스",
            f"가정 속도(횡이송 {PT_T.TR_V:.1f} · 수직 {PT_T.TR_VZ:.1f} · 인출 {PT_T.FORK_V:.2f} m/s)의 계산이다. "
            f"여유가 있으나 인계 동작(포크 끼리의 티인 교차)은 FAT 에서 실측으로 닫는다"),
    ]


def summary() -> dict:
    cmp_, ex_ = compare(), extra()
    over_t = sorted({t.id for _, _, t in cmp_ if not t.ok} | {t.id for _, t, _ in ex_ if not t.ok})
    over_b = sorted({b.id for _, b, _ in cmp_ if b and not b.ok})
    new_over = [i for i in over_t if i not in over_b]
    return dict(checks=len(cmp_) + len(ex_), over_t=over_t, over_b=over_b, new_over=new_over)


if __name__ == "__main__":
    for g, b, t in compare():
        print(f"{g:6s} {t.id:5s} {t.what[:30]:30s} {b.value if b else float('nan'):10.3f} → {t.value:10.3f} "
              f"/ {t.limit:10.3f} {t.util:5.0%} {'OK' if t.ok else '★'}")
    for g, t, b in extra():
        print(f"{g:6s} {t.id:5s} {t.what[:30]:30s} {b.value if b else float('nan'):10.3f} → {t.value:10.3f} "
              f"/ {t.limit:10.3f} {t.util:5.0%} {'OK' if t.ok else '★'}")
    print(summary())
    for q in requirements():
        print(q.id, q.what, "|", q.value)
