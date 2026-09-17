#!/usr/bin/env python3
"""단일 셰브론(역V) 핫나이프 — 150 mm 분절 하나가 받는 힘.

발주자 지시 (9/17): DL-101 의 HKB/HKS 탠덤을 버리고 유리 계면 칼날 **하나**로
간다. 그 칼날은 길이 150 mm 핫나이프 분절을 역V(셰브론)로 늘어놓은 것이다.
묻는 것은 하나다 — **분절 하나가 받는 힘이 얼마인가**.

  총 추력은 형상이 정하지 않는다. 박리 저항은 박리 전선 **폭당** 힘이다
  (OI-01 상한 111 N/cm · 폭 1,400 → 콘솔 F_PEEL 15.60 kN). 칼날을 비스듬히
  놓아도 패널 폭은 그대로이므로 진행방향 합계는 같다. 셰브론이 바꾸는 것은
  ① 그 합계를 몇 개의 분절이 나눠 갖는가 ② 분절마다 힘이 어느 방향인가 ③
  칼날이 패널을 다 지나기까지 얼마나 더 가야 하는가(사이클) 셋이다.

모델 (닫힌해):
  f_w = F_PEEL / PANEL_W                       N/mm 박리 전선 폭당 저항
  θ   = 날개가 횡방향(y)과 이루는 각 (0 이면 직선 칼날)
  분절 i 가 패널 안에 물린 날 길이 ℓ_i (mm). 저항은 날에 수직으로 작용한다
  (쐐기 반력) —
      R_i  = f_w · ℓ_i          면내 합력. **각도와 무관** — 완전히 물린 분절은
                                 f_w × 150 = 1.67 kN, 셰브론을 세우든 눕히든 같다
      F_x  = R_i cos θ          진행 성분. Σ = f_w · PANEL_W = F_PEEL
      F_y  = R_i sin θ          횡 성분. 좌·우 날개가 서로 상쇄 — 홀더가 한 몸이어야 한다
  저항이 전부 진행 방향이라고 보면 분절 힘은 R_i cos θ 로 이보다 작다. 그러니
  R_i 가 포락값이고, 빗각 슬라이싱이 저항을 얼마나 내리는지는 실측(OI-01 곡선을
  셰브론 형상으로 다시 잰다)에서만 나온다 — 여기서는 이득을 안 잡는다.
  설계값은 제작 지침서와 같은 계수를 얹는다: × PSI_DYN 1.30 (물림 충격) × γQ 1.50.

기하:
  날개 반폭 B = KNIFE_W/2 (패널 반폭 + 여유 120). 분절 횡피치 p = 150 cos θ,
  날개당 분절 수 n = ⌈B / p⌉ (마지막 분절은 튀어나온다). 셰브론 깊이는
  칼끝(y = B)에서 B tan θ, 패널 가장자리(y = 700)에서 700 tan θ 이고 후자가
  사이클에 들어간다 — 패널 후단이 y = ±700 의 날을 벗어나야 박리가 끝난다.
  탠덤의 칼끝 간격 300 이 서던 자리에 이 깊이가 선다.

방향 가정: **꼭짓점이 먼저 문다** (Λ 의 꼭짓점이 상류). 박리가 중앙에서
바깥으로 열리고 횡 성분은 좌우 바깥으로 향한다. 뒤집으면(날개 끝이 먼저)
크기는 같고 횡 성분 부호만 바뀐다 — 대신 패널 모서리 두 점이 먼저 맞아
유리 모서리 파손 위험이 있고, 떼어낸 층이 중앙으로 몰린다.
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cycle as CY  # noqa: E402
import fab_spec as F  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 입력 ─────────────────────────────────────────────────────────────────
SEG_L = 150.0                                  # mm 분절 길이 — 발주자 지시
F_PEEL = c("F_PEEL")                           # kN 특성 추력 (OI-01 상한 · 폭 1,400)
PANEL_W = c("PANEL_W") * 1000                  # mm
PANEL_L = c("PANEL_L") * 1000                  # mm
PANEL_HALF = PANEL_W / 2
KNIFE_W = c("KNIFE_W") * 1000                  # mm 칼날 유효폭 1,640
KNIFE_HALF = KNIFE_W / 2
F_W = F_PEEL * 1000 / PANEL_W                  # N/mm 전선 폭당 저항 (11.14)
DESIGN = F.PSI_DYN * F.GAMMA_Q                 # 1.95 — 특성 → 설계
V_KNIFE = CY.DEFAULT["knifeSpeed"]             # mm/s 박리속도 55
KNIFE_PITCH = CY.MODEL["knifePitch"]           # mm 탠덤 칼끝 간격 300 — 사이클 기준
HEAT_W_PER_MM = c("CASS_HEAT_KW") * 1000 / KNIFE_W   # W/mm 카세트 히터 정격을 폭으로 나눈 것
ALPHA_SKD11 = 11.5e-6                          # 1/K 냉간공구강 선팽창 (20~200 ℃ 카탈로그 11~12)
DT_BLADE = c("T_HKS") - c("T_AMB")             # K 200 − 25
T_GLASS = 3.2                                  # mm 유리 두께 (사양서 4.2 적층)


def blades(theta_deg: float, half: float = KNIFE_HALF) -> list[dict]:
    """한 날개의 분절 목록 — 꼭짓점(y=0)부터 바깥으로.

    각 분절: 횡 구간 [y0, y1], 패널 안에 물린 날 길이 ℓ, 면내 합력 R (kN),
    진행 성분 Fx, 횡 성분 Fy (kN). 힘은 특성값이다.
    """
    t = math.radians(theta_deg)
    pitch = SEG_L * math.cos(t)
    n = math.ceil(half / pitch - 1e-9)
    out = []
    for i in range(n):
        y0, y1 = i * pitch, (i + 1) * pitch
        eng_y = max(0.0, min(y1, PANEL_HALF) - y0)      # 패널 안에 든 횡 폭
        ell = eng_y / math.cos(t)                         # 물린 날 길이
        R = F_W * ell / 1000
        out.append(dict(i=i + 1, y0=y0, y1=y1, engaged=ell, R=R,
                        Fx=R * math.cos(t), Fy=R * math.sin(t)))
    return out


def option(theta_deg: float, half: float = KNIFE_HALF) -> dict:
    """각도 하나의 셰브론 — 분절 수 · 힘 · 깊이 · 사이클."""
    t = math.radians(theta_deg)
    bl = blades(theta_deg, half)
    n = len(bl)
    full = F_W * SEG_L / 1000                             # kN 완전히 물린 분절
    wing_fx = sum(b["Fx"] for b in bl)
    wing_fy = sum(b["Fy"] for b in bl)
    depth_panel = PANEL_HALF * math.tan(t)                # mm 패널 가장자리까지 깊이
    depth_tip = n * SEG_L * math.sin(t)                   # mm 마지막 분절 끝까지
    m = CY.model(knife_pitch=depth_panel)
    return dict(
        theta=theta_deg, n=n, blades=2 * n, pitch_y=SEG_L * math.cos(t),
        overhang=n * SEG_L * math.cos(t) - half,          # mm 칼끝이 유효폭 밖으로
        R_full=full, R_full_design=full * DESIGN,
        Fx_full=full * math.cos(t), Fy_full=full * math.sin(t),
        engaged=[b["engaged"] for b in bl],
        wing_fx=wing_fx, wing_fy=wing_fy, total_fx=2 * wing_fx,
        depth_panel=depth_panel, depth_tip=depth_tip,
        ramp_s=depth_panel / V_KNIFE,                     # s 꼭짓점 물림 → 전폭 물림
        cycle=m["knifeLineCycle"], net=m["knifeLineRate"] * CY.AVAILABILITY,
        glass_sigma=wing_fy * 1000 / (T_GLASS * PANEL_L), # MPa 유리 중앙선 인장
    )


def exact_fit(n: int, half: float = KNIFE_HALF) -> float:
    """날개당 n 분절이 정확히 반폭을 덮는 각 (deg) — 튀어나옴 0."""
    cos_t = half / (n * SEG_L)
    if not 0 < cos_t <= 1:
        raise ValueError(f"{n} 분절로는 반폭 {half:.0f} 을 덮지 못한다")
    return math.degrees(math.acos(cos_t))


ANGLES = (15.0, 20.0, round(exact_fit(6), 2), 30.0, 45.0, 60.0)


def straight() -> dict:
    """비교 기준 — 지금의 직선 칼날 (θ = 0)."""
    return option(0.0)


def per_blade_heat_kw() -> float:
    """분절 하나가 지금의 카세트 히터 밀도로 받아야 하는 발열 (kW)."""
    return HEAT_W_PER_MM * SEG_L / 1000


def per_blade_growth_mm() -> float:
    """분절 하나의 열팽창 — 이음이 이만큼 닫히거나 벌어진다."""
    return ALPHA_SKD11 * DT_BLADE * SEG_L


def contract_ok(o: dict) -> bool:
    return o["net"] >= CY.NET_TARGET - 1e-9


def summary() -> dict:
    """문서·시험이 읽는 값."""
    six = option(exact_fit(6))
    return dict(f_w=F_W, R_full=six["R_full"], R_full_design=six["R_full_design"],
                theta_six=six["theta"], six=six, heat_kw=per_blade_heat_kw(),
                growth_mm=per_blade_growth_mm(),
                max_theta_contract=max(o["theta"] for o in map(option, ANGLES) if contract_ok(o)))


def report() -> str:
    L = [f"── 단일 셰브론 핫나이프 · 분절 {SEG_L:.0f} mm · 폭당 저항 {F_W:.2f} N/mm "
         f"(F_PEEL {F_PEEL:.2f} kN / 폭 {PANEL_W:.0f}) ──",
         f"  완전히 물린 분절 1개: R = {F_W:.2f} × {SEG_L:.0f} = {F_W*SEG_L/1000:.2f} kN 특성 "
         f"→ ×{DESIGN:.2f} = {F_W*SEG_L*DESIGN/1000:.2f} kN 설계 — 각도와 무관",
         f"  진행 합계는 형상과 무관하게 {F_PEEL:.2f} kN. 횡 성분은 날개끼리 상쇄 (홀더 한 몸)",
         "",
         "  θ°    날개당  칼날  횡피치  깊이(패널)  분절 진행/횡  날개 횡합  램프   사이클   순생산",
         "        분절    합계   mm      mm          kN/kN         kN       s      s        장/h"]
    for th in (0.0,) + ANGLES:
        o = option(th)
        flag = "" if contract_ok(o) else "  ✗ 계약 미달"
        L.append(f"  {o['theta']:5.2f}  {o['n']:3d}    {o['blades']:3d}   {o['pitch_y']:6.1f}  "
                 f"{o['depth_panel']:7.0f}     {o['Fx_full']:.2f}/{o['Fy_full']:.2f}    "
                 f"{o['wing_fy']:5.2f}   {o['ramp_s']:5.1f}  {o['cycle']:6.2f}   {o['net']:5.1f}{flag}")
    six = option(exact_fit(6))
    L += ["",
          f"  6 분절/날개 정합각 {six['theta']:.2f}° — 칼끝 튀어나옴 {six['overhang']:.0f} mm · "
          f"깊이 {six['depth_panel']:.0f} (탠덤 칼끝 간격 {KNIFE_PITCH:.0f} 자리) · "
          f"순생산 {six['net']:.1f} 장/h (계약 {CY.NET_TARGET})",
          "  분절별 물린 길이 (꼭짓점 → 바깥): " +
          " · ".join(f"{e:.0f}" for e in six["engaged"]) + " mm",
          "  분절별 힘 R (특성): " + " · ".join(f"{F_W*e/1000:.2f}" for e in six["engaged"]) + " kN",
          f"  날개 횡합 {six['wing_fy']:.2f} kN → 유리 중앙선 인장 {six['glass_sigma']:.2f} MPa · "
          f"꼭짓점 이음이 이 힘을 좌우로 잇는다",
          f"  분절당 발열 {per_blade_heat_kw():.2f} kW (지금 카세트 밀도 {HEAT_W_PER_MM:.1f} W/mm) · "
          f"열팽창 {per_blade_growth_mm():.2f} mm/분절 (ΔT {DT_BLADE:.0f} K)"]
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
