#!/usr/bin/env python3
"""계단형 핫나이프 SHK-101 — 조각 하나가 받는 힘 · 물림 램프 · 사이클 · 계단 높이의 창.

발주자 스케치 (9/24): DL-101 의 HKB/HKS 탠덤을 버리고 칼날 **하나**로 셀모듈과
백시트를 한꺼번에 유리에서 떼어 낸다. 칼끝은 한 줄이 아니라 계단이다 — 중앙
300 이 먼저 물고 양쪽 200 칼날이 한 단에 80 씩 물러나며 세 단을 내려간다
(전폭 1,500 · 깊이 240). 형상은 콘솔 뿌리 상수(KNIFE_*)가 든다. 여기서는 값을
하나도 새로 정하지 않고 그 형상이 무엇을 받는지를 셈한다.

앞선 검토(9/17, 역V 셰브론 150 mm 분절 · 커밋 2c59bbe 의 knife_chevron.py)는
비스듬히 늘어놓은 분절의 힘을 물었다. 계단 칼날은 조각마다 날이 진행방향에
직각이다(θ = 0). 그 검토의 '직선 칼날' 경우가 조각마다 성립하고, 대신 조각이
시간차를 두고 문다. 그래서 묻는 것이 넷으로 바뀐다.

  ① 조각 하나가 받는 힘. 박리 저항은 박리 전선 **폭당** 힘이다 (OI-01 상한
     111 N/cm · 폭 1,400 → 콘솔 F_PEEL 15.60 kN). 조각 i 의 힘은
     f_w × (패널 안에 든 그 조각의 명목 폭) 이고 진행 성분뿐이다 — 날이 직각이라
     횡 성분이 없고, 셰브론처럼 좌우 날개를 이어 줄 이유도 없다. 이음 겹침 15 는
     안쪽 칼날이 이미 떼어 간 줄을 다시 긋는 자리라 힘을 보태지 않는다.
  ② 물림 램프. 중앙 칼끝이 패널 앞끝에 닿은 뒤 계단 높이만큼 갈 때마다 한 단씩
     더 문다. 물린 폭 300 → 700 → 1,100 → 1,400 이고 추력은 폭에 비례한다.
     물림 충격이 전폭 한 번이 아니라 한 단 몫씩 네 번 온다.
  ③ 사이클. 깊이 240 을 더 가야 바깥 칼끝이 패널 뒤끝을 벗어난다 — 탠덤의
     칼끝 간격 300 이 서던 자리에 이 깊이가 선다 (cycle.model(knife_depth=…)).
  ④ 계단 높이의 창. 단이 깊을수록 물림이 부드럽지만 사이클이 길어진다. 계약
     58 장/h 가 허락하는 가장 높은 계단을 거꾸로 푼다.

설계값은 제작 지침서와 같은 계수를 얹는다: × PSI_DYN 1.30 (물림 충격) × γQ 1.50.

    python3 tools/knife_stepped.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cycle as CY  # noqa: E402
import fab_spec as F  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 형상 — 콘솔 뿌리 상수 (mm) ───────────────────────────────────────────
CENTER = c("KNIFE_CENTER") * 1000             # 300 중앙 칼날 — 가장 먼저 문다
STEP_W = c("KNIFE_STEP_W") * 1000             # 200 계단 칼날 폭
STEPS = int(c("KNIFE_STEPS"))                  # 3 한쪽 단수
RISE = c("KNIFE_RISE") * 1000                 # 80 계단 높이 (발주자 확정)
LAP = c("KNIFE_LAP") * 1000                   # 15 이음 겹침
KNIFE_W = c("KNIFE_W") * 1000                 # 1,500 전폭
DEPTH = c("KNIFE_DEPTH") * 1000               # 240 깊이
BLADES = int(c("KNIFE_BLADES"))               # 7 조각
PANEL_W = c("PANEL_W") * 1000                 # 1,400
PANEL_L = c("PANEL_L") * 1000                 # 2,500
PANEL_HALF = PANEL_W / 2

# ── 힘 ───────────────────────────────────────────────────────────────────
F_PEEL = c("F_PEEL")                           # kN 특성 추력 (OI-01 상한 · 폭 1,400)
F_W = F_PEEL * 1000 / PANEL_W                  # N/mm 전선 폭당 저항 (11.14)
DESIGN = F.PSI_DYN * F.GAMMA_Q                 # 1.95 — 특성 → 설계
V_KNIFE = CY.DEFAULT["knifeSpeed"]             # mm/s 박리속도 55

# ── 열 ───────────────────────────────────────────────────────────────────
HEAT_KW = c("CASS_HEAT_KW")                    # kW 카세트 히터 정격 — 일곱 존의 합
BLADE_L_SUM = c("CASS_L") * 1000               # mm 일곱 홀더 길이 합 (겹침 포함) 1,590
ALPHA_SKD11 = 11.5e-6                          # 1/K 냉간공구강 선팽창 (20~200 ℃ 카탈로그 11~12)
DT_BLADE = c("T_KNIFE") - c("T_AMB")           # K 200 − 25


def segments() -> list[dict]:
    """칼날 조각 표 — 중앙부터 바깥으로, 좌우 한 쌍씩.

    y0·y1 은 겹침을 포함한 날 구간(콘솔 KNIFE_SEGS 와 같은 식), y0n·y1n 은 겹침을
    뺀 명목 구간이다. engaged 는 명목 구간 중 패널(±700) 안에 든 폭이고, 힘은 그
    폭에서 나온다. back 은 중앙 칼끝에서 뒤로 물러난 거리(계단 수 × 높이)다.
    """
    out = [dict(k=0, side=0, y0=-CENTER / 2, y1=CENTER / 2,
                y0n=-CENTER / 2, y1n=CENTER / 2, back=0.0)]
    for k in range(1, STEPS + 1):
        a = CENTER / 2 + (k - 1) * STEP_W
        b = a + STEP_W
        out.append(dict(k=k, side=+1, y0=a - LAP, y1=b, y0n=a, y1n=b, back=k * RISE))
        out.append(dict(k=k, side=-1, y0=-b, y1=-a + LAP, y0n=-b, y1n=-a, back=k * RISE))
    for s in out:
        lo, hi = max(-PANEL_HALF, s["y0n"]), min(PANEL_HALF, s["y1n"])
        s["length"] = s["y1"] - s["y0"]                     # 날 길이 (겹침 포함)
        s["engaged"] = max(0.0, hi - lo)                    # 패널 안 명목 폭
        s["R"] = F_W * s["engaged"] / 1000                  # kN 특성
        s["R_design"] = s["R"] * DESIGN
        s["heat_kw"] = HEAT_KW * s["length"] / BLADE_L_SUM  # 날 길이에 비례한 존 정격
        s["growth"] = ALPHA_SKD11 * DT_BLADE * s["length"]  # mm 가열 신장
    return out


def coverage_gaps() -> list[tuple[float, float]]:
    """날이 덮지 못하는 y 구간 — 비어 있어야 한다. 전폭 −750 ~ +750 기준."""
    spans = sorted((s["y0"], s["y1"]) for s in segments())
    gaps, reach = [], -KNIFE_W / 2
    for a, b in spans:
        if a > reach + 1e-9:
            gaps.append((reach, a))
        reach = max(reach, b)
    if reach < KNIFE_W / 2 - 1e-9:
        gaps.append((reach, KNIFE_W / 2))
    return gaps


def ramp() -> list[dict]:
    """물림 램프 — 중앙 칼끝이 패널 앞끝에 닿은 뒤 계단마다 늘어나는 물린 폭과 추력."""
    out = []
    for k in range(STEPS + 1):
        w = sum(s["engaged"] for s in segments() if s["k"] <= k)
        out.append(dict(k=k, travel=k * RISE, t=k * RISE / V_KNIFE,
                        width=w, thrust=F_W * w / 1000, added=F_W * (w - (out[-1]["width"] if out else 0)) / 1000))
    return out


def cycle(rise: float = RISE) -> dict:
    """계단 높이 rise(mm)의 사이클 — 깊이 = 단수 × 높이 를 콘솔 식에 넣는다."""
    m = CY.model(knife_depth=STEPS * rise)
    return dict(depth=STEPS * rise, lead=m["leadTime"], cycle=m["knifeLineCycle"],
                nominal=m["knifeLineRate"], net=m["knifeLineRate"] * CY.AVAILABILITY)


def max_rise(target: float = CY.NET_TARGET) -> float:
    """계약 순생산을 지키는 가장 높은 계단 (mm) — 이분법."""
    lo, hi = 0.0, 1000.0
    if cycle(lo)["net"] < target:
        return 0.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if cycle(mid)["net"] >= target:
            lo = mid
        else:
            hi = mid
    return lo


def summary() -> dict:
    """문서·시험이 읽는 값."""
    seg = segments()
    center = seg[0]
    step = seg[1]
    r = ramp()
    cy = cycle()
    return dict(
        f_w=F_W, center_R=center["R"], center_R_design=center["R_design"],
        step_R=step["R"], step_R_design=step["R_design"],
        outer_R=seg[-1]["R"], total=sum(s["R"] for s in seg),
        entry=r[0]["thrust"], entry_design=r[0]["thrust"] * DESIGN,
        ramp_widths=[x["width"] for x in r], ramp_time=r[-1]["t"],
        depth=cy["depth"], lead=cy["lead"], cycle=cy["cycle"], net=cy["net"],
        max_rise=max_rise(), max_depth=STEPS * max_rise(),
        margin=(KNIFE_W - PANEL_W) / 2, gaps=coverage_gaps(),
        growth_max=max(s["growth"] for s in seg),
        heat_center=center["heat_kw"], heat_step=step["heat_kw"],
    )


def report() -> str:
    seg = segments()
    s = summary()
    L = [f"── 계단형 핫나이프 SHK-101 · 중앙 {CENTER:.0f} + {STEP_W:.0f}×{STEPS}/측 · 계단 {RISE:.0f} · "
         f"전폭 {KNIFE_W:,.0f} · 깊이 {DEPTH:.0f} ──",
         f"  폭당 저항 f_w = {F_PEEL:.2f} kN / {PANEL_W:,.0f} = {F_W:.2f} N/mm (OI-01 상한). "
         f"설계 ×{DESIGN:.2f}",
         "",
         "  조각  단  날 구간 y (mm)        날 길이  패널 안 폭  뒤로   R 특성  R 설계  히터    신장",
         "                                    mm        mm       mm    kN      kN      kW      mm"]
    for x in seg:
        tag = "중앙" if x["k"] == 0 else ("+y" if x["side"] > 0 else "−y")
        L.append(f"  {tag:4s}  {x['k']:d}   {x['y0']:+7.0f} ~ {x['y1']:+7.0f}     {x['length']:6.0f}   "
                 f"{x['engaged']:6.0f}    {x['back']:4.0f}   {x['R']:5.2f}   {x['R_design']:5.2f}   "
                 f"{x['heat_kw']:4.2f}   {x['growth']:4.2f}")
    L += [f"  합계 추력 {s['total']:.2f} kN = F_PEEL {F_PEEL:.2f} — 형상이 합계를 바꾸지 않는다. "
          f"날이 덮지 못하는 틈: {'없음' if not s['gaps'] else s['gaps']}",
          "",
          "  물림 램프 (중앙 칼끝이 패널 앞끝에 닿은 뒤)"]
    for x in ramp():
        L.append(f"    +{x['travel']:3.0f} mm · {x['t']:4.2f} s  물린 폭 {x['width']:5,.0f}  "
                 f"추력 {x['thrust']:5.2f} kN (이번 단 +{x['added']:.2f})")
    L += ["",
          f"  사이클 — 깊이 {s['depth']:.0f} → 선행 {s['lead']:.2f} s · 라인 {s['cycle']:.2f} s · "
          f"순생산 {s['net']:.1f} 장/h (계약 {CY.NET_TARGET})",
          f"  계단 높이의 창 — 계약을 지키는 가장 높은 계단 {s['max_rise']:.0f} mm "
          f"(깊이 {s['max_depth']:.0f}) · 확정 {RISE:.0f} 는 그 안이다",
          f"  양끝 여유 {s['margin']:.0f} mm · 조각 최대 신장 {s['growth_max']:.2f} mm (ΔT {DT_BLADE:.0f} K) "
          f"— 이음 겹침 {LAP:.0f} 의 {s['growth_max']/LAP:.0%}"]
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
