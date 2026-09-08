# -*- coding: utf-8 -*-
"""GBR-301 슬롯 적재의 **수치해석** — 무엇이 얼마나 휘고, 언제 멈추고, 어디에 놓이는가.

`gbr_load.py` 는 이 셀에 처음으로 **시간**을 줬다. 행정을 사다리꼴 프로파일에
넣어 한 장 28.28 s 를 냈고, 그것으로 버퍼가 택트를 따라온다는 것을 보였다. 그런데
그 모델은 기계를 **점**으로 본다 — 포크는 늘어나기만 하고 휘지 않으며, 유리는
얹히기만 하고 눕지 않고, 정지는 `STOP_SETTLE_S = 0.3` 이라는 한 상수로 끝난다.

여기서 그 셋을 연속체와 강체로 다시 푼다.

1. **TF-810 콤포크** — 3,200 신장한 2 단 텔레스코픽을 Euler–Bernoulli 유한요소로
   푼다. §7 적대 심사가 「신장 포크 2.9 m 캔틸레버 처짐」을 지적하고 TG-813
   선단받이를 넣게 했는데, **그 처짐을 아무도 계산한 적이 없다.** 계산하면
   4…8 mm 로 소하강 12 mm 예산 안이다 — 받쳐 줄 필요가 없었다. 대신 TG-813 이
   무엇인지가 바뀐다(`tg_gap_window_mm()`).
2. **무프레임 유리** — 폭 1 mm 띠 보로 슬롯 선반 위와 포크 위를 각각 푼다.
   여기서 **하중 경로가 끊겨 있는 것이 드러났다**: 선반 레일이 z ±702.5…757.5 에
   있고 유리 가장자리는 ±700 이라, 유리는 어느 레일에도 닿지 않는다. 강체 적분을
   돌리면 유리가 슬롯을 그냥 통과해 떨어진다.
3. **안착 충격 (하이브리드)** — 유한요소로 푼 유리 띠를 접촉점 1 자유도로
   모드 축약하고, 거기에 강체 유리와 한 방향 접촉 스프링–댐퍼를 물려 12 mm
   소하강을 적분한다. 연속체가 강성을, 강체가 궤적을 맡는 공동시뮬레이션이다.
   축약이 옳은지는 같은 보를 Newmark-β 로 그대로 적분해 주기·진폭으로 맞춰 본다
   (`set_down_verify()`).

**정적피로를 쓴다.** 버퍼는 지나가는 자리가 아니라 **두는** 자리다. 소다석회
유리의 허용응력은 하중 지속시간에 따라 내려가므로(σ ∝ t^(−1/16)) 단기 허용
30 MPa 를 그대로 쓰면 안 된다. `dwell_limit_s()` 가 지금 배치가 견디는 체류시간을
돌려주고, `campaign` 이 내는 실제 최대 체류와 견준다.

단위는 `beam.py` 와 같다 — mm · N · MPa · s · tonne.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass

from . import afr, beam, drives, dynamics, frames, gbr_load, handoff

# ── 재료 ────────────────────────────────────────────────────────────────
#: 알루미늄 밀도 [tonne/mm³] — `afr_peel.ALU_DENSITY_T_MM3` 과 같은 6063 값이다.
ALU_DENSITY_T_MM3 = 2.70e-9
#: 강 밀도 [tonne/mm³] — `afr.STEEL_DENSITY_KG_M3` 에서 온다.
STEEL_DENSITY_T_MM3 = afr.STEEL_DENSITY_KG_M3 * 1e-12

# ── 벤더 확정 항목 — 단면 살두께 ─────────────────────────────────────────
# GA 시트는 부재의 **외형**만 준다 (콤포크 95 × 120, 마스트 160 × 200). 살두께는
# 제작도의 값이라 여기서 계획값을 잡는다 — `gbr_load` 의 이송 프로파일과 같은
# 취급이다. 결론이 이 값에 얼마나 매여 있는지는 `fork_wall_sweep()` 이 보인다:
# 3…10 mm 전 구간에서 처짐이 예산 안이라 **결론이 안 뒤집힌다.**
FORK_WALL_MM = 6.0
#: 2 단 텔레스코픽의 단 사이 미끄럼 여유 [mm] — 안단 단면이 이만큼 더 작아진다.
FORK_SLIDE_CLEAR_MM = 2.0
#: 마스트 살두께 [mm].
MAST_WALL_MM = 8.0

# ── 유리 정적피로 ────────────────────────────────────────────────────────
#: 소다석회 유리의 정적피로 지수 — σ₁/σ₂ = (t₂/t₁)^(1/n). 판유리 설계의 표준값이다.
GLASS_FATIGUE_N = 16.0
#: `afr.GLASS_ALLOW_MPA` 가 가리키는 기준 지속시간 [s] — 판유리 설계의 3 초 하중.
GLASS_REF_S = 3.0

# ── 해석 분할 ────────────────────────────────────────────────────────────
#: 안단 52 요소(le 50) · 밑단 76 요소(le 15.625) — 지지점이 절점에 **정확히** 온다.
FORK_INNER_ELEMENTS, FORK_BASE_ELEMENTS = 52, 76
#: 유리 띠 분할 — le 10 mm. 선반선(±650)과 포크선(±540)이 둘 다 절점에 온다.
GLASS_ELEMENTS = 140
#: 과도해석용 성긴 분할 — le 50 mm. 선반선은 정확히 오고 포크선은 10 mm 스냅한다
#: (스팬 1,080 의 0.9 % — `set_down_verify()` 가 축약 정해와 견줘 확인한다).
GLASS_TRANSIENT_ELEMENTS = 28
MAST_ELEMENTS = 40


# ── 단면 만들기 ──────────────────────────────────────────────────────────
def _rhs(b_mm: float, h_mm: float, t_mm: float) -> tuple[float, float]:
    """직사각 중공 단면의 (I, A) — b 는 폭(중립축과 평행), h 는 휨 방향 깊이."""
    if t_mm <= 0 or 2 * t_mm >= min(b_mm, h_mm):
        raise ValueError("살두께가 단면을 넘는다")
    i = (b_mm * h_mm ** 3 - (b_mm - 2 * t_mm) * (h_mm - 2 * t_mm) ** 3) / 12.0
    a = b_mm * h_mm - (b_mm - 2 * t_mm) * (h_mm - 2 * t_mm)
    return i, a


def fork_section(stage: int = 2, wall_mm: float | None = None) -> beam.Section:
    """콤포크 단면 — 1 은 캐리지에 물린 밑단, 2 는 밀려 나가는 안단.

    안단은 밑단 **안**을 지나가므로 살두께와 미끄럼 여유만큼 작다. 완전 신장에서
    선단을 들고 있는 것은 안단이라, 보수적인 값은 2 다.
    """
    t = FORK_WALL_MM if wall_mm is None else wall_mm
    shrink = 0.0 if stage == 1 else 2.0 * (t + FORK_SLIDE_CLEAR_MM)
    b = gbr_load.FORK_W_MM - shrink          # z 폭
    h = gbr_load.FORK_H_MM - shrink          # y 깊이 (휨 방향)
    i, a = _rhs(b, h, t)
    return beam.Section(frames.YOUNGS_MODULUS_MPA, i, a, h / 2.0,
                        ALU_DENSITY_T_MM3, frames.YIELD_MPA)


def mast_section(wall_mm: float | None = None) -> beam.Section:
    """트윈마스트 단면 — 포크가 뻗는 X 방향 휨(깊이 160)이 약축이다."""
    t = MAST_WALL_MM if wall_mm is None else wall_mm
    i, a = _rhs(gbr_load.MAST_SECTION_MM, gbr_load.MAST_DEPTH_MM, t)
    return beam.Section(afr.STEEL_E_MPA, i, a, gbr_load.MAST_DEPTH_MM / 2.0,
                        STEEL_DENSITY_T_MM3, frames.YIELD_MPA * 1.5)


def glass_section() -> beam.Section:
    """무프레임 라미네이트를 폭 1 mm 띠로 본 단면."""
    t = afr.LAMINATE_T_MM
    return beam.Section(afr.GLASS_E_MPA, t ** 3 / 12.0, t, t / 2.0,
                        afr.LAMINATE_KG_M2 / t * 1e-9, afr.GLASS_ALLOW_MPA)


def glass_strip_load_n_mm() -> float:
    """폭 1 mm 띠의 자중 [N/mm] — `afr.laminate_line_load_n_per_mm()` 과 같은 값."""
    return afr.LAMINATE_KG_M2 * dynamics.G / 1e6


def glass_weight_n() -> float:
    """무프레임 라미네이트 한 장의 무게 [N]."""
    lx, lz = gbr_load.GLASS_L_MM, gbr_load.GLASS_W_MM
    return afr.LAMINATE_KG_M2 * (lx * lz / 1e6) * dynamics.G


# ── ① TF-810 콤포크 — 2 단 텔레스코픽 다물체 ────────────────────────────
#
# 이 부재를 「길이 2,787 mm 의 외팔보」로 보면 처짐이 7 mm 나오는데, 그것은
# **틀린 모델이다.** 2 단 텔레스코픽은 두 단이 1,000 mm 겹친 채로 나가므로 안단은
# 그 겹침 두 점에 받쳐지고, 실제 외팔은 겹침 앞 1,600 mm 뿐이다. 외팔보 처짐은
# 길이의 네제곱이라 (1600/2787)⁴ ≈ 0.11 — 한 자리가 달라진다.
#
# 그래서 두 보를 순서대로 푼다.
#
#   ㉮ 안단 — 겹침 두 점 단순지지 + 앞으로 1,600 외팔. 유리 대부분을 여기서 받는다.
#   ㉯ 밑단 — 승강 캐리지에 물린 자리에서 앞으로 1,187.5 외팔. ㉮의 지지반력 둘을
#      받는다. 캐리지가 처짐과 회전을 둘 다 잡으므로 **뒤쪽은 앞과 끊긴다** —
#      뒤로 나간 1,412 mm 는 제 무게만 지고 선단에 아무 영향이 없다.
#
# 선단 처짐은 셋의 합이다: 밑단의 겹침 끝 처짐 + 그 자리의 회전 × 1,600 + 안단
# 자신의 상대처짐. 회전항이 빠지면 값이 절반으로 줄어 안전측이 아니게 된다.
#
# 분할은 **지지점이 절점에 정확히 놓이도록** 고른다. 겹침 1,000 과 전장 2,600 은
# 25 로 나누어떨어지고(㉮ 104 요소), 밑단 외팔 1,187.5 와 그 위 반력 자리 187.5 는
# 15.625 로 나누어떨어진다(㉯ 76 요소). 절점이 어긋나면 외팔 길이가 수십 mm 씩
# 옮겨 다녀 처짐이 20 % 씩 흔들린다 — 여기서는 그것이 물리가 아니라 격자다.


def _udl_between(bm: beam.Beam, x0: float, w_n_mm: float,
                 lo: float, hi: float) -> list[float]:
    """보의 일부 구간에만 걸리는 등분포하중의 등가 절점하중."""
    f = [0.0] * bm.ndof
    if w_n_mm == 0.0:
        return f
    for e in range(bm.n_el):
        a, b = x0 + e * bm.le, x0 + (e + 1) * bm.le
        overlap = max(0.0, min(b, hi) - max(a, lo))
        if overlap <= 0.0:
            continue
        fe = beam.element_udl(w_n_mm * overlap / bm.le, bm.le)
        base = e * beam.DOF_PER_NODE
        for i in range(4):
            f[base + i] += fe[i]
    return f


def _glass_udl_n_mm() -> float:
    """포크 한 본이 받는 유리 등분포하중 [N/mm]."""
    lo, hi = gbr_load.glass_span_on_fork_mm()
    return glass_weight_n() / 2.0 / (hi - lo)


@dataclass(frozen=True)
class Fork:
    """완전 신장한 콤포크 한 본의 해."""

    droop_mm: float
    stress_mpa: float
    self_kg: float
    free_mm: float
    hz: float

    @property
    def depth_mm(self) -> float:
        return gbr_load.FORK_H_MM


@functools.lru_cache(maxsize=None)
def fork_static(depth_mm: float | None = None, width_mm: float | None = None,
                wall_mm: float | None = None, e_mpa: float | None = None,
                density_t_mm3: float | None = None) -> Fork:
    """완전 신장 · 유리 적재 상태의 2 단 텔레스코픽 해."""
    h = gbr_load.FORK_H_MM if depth_mm is None else depth_mm
    w = gbr_load.FORK_W_MM if width_mm is None else width_mm
    t = FORK_WALL_MM if wall_mm is None else wall_mm
    e = frames.YOUNGS_MODULUS_MPA if e_mpa is None else e_mpa
    rho = ALU_DENSITY_T_MM3 if density_t_mm3 is None else density_t_mm3
    base, inner = (_section(h, w, t, e, rho, False), _section(h, w, t, e, rho, True))

    (b_lo, b_hi), (i_lo, i_hi) = gbr_load.fork_stage_spans_mm()
    o_lo, o_hi = gbr_load.fork_overlap_mm()
    root = gbr_load.mast_x_mm()
    g_lo, g_hi = (v + root for v in gbr_load.glass_span_on_fork_mm())
    gw = _glass_udl_n_mm()

    # ㉮ 안단 — 겹침 두 점 단순지지.
    bi = beam.Beam(inner, i_hi - i_lo, FORK_INNER_ELEMENTS)
    fi = [a + b for a, b in
          zip(_udl_between(bi, i_lo, inner.weight_n_mm, i_lo, i_hi),
              _udl_between(bi, i_lo, gw, max(g_lo, o_lo), g_hi))]
    ka = bi.stiffness()
    na = bi.node_at(o_lo - i_lo) * beam.DOF_PER_NODE
    nb = bi.node_at(o_hi - i_lo) * beam.DOF_PER_NODE
    ui = bi._solve_with_bc([r[:] for r in ka], fi[:], {na: 0.0, nb: 0.0})
    react = [sum(ka[d][j] * ui[j] for j in range(bi.ndof)) - fi[d]
             for d in (na, nb)]

    # ㉯ 밑단 — 캐리지에 물린 자리에서 앞으로만. 뒤쪽은 고정단이 끊는다.
    bb = beam.Beam(base, b_hi - root, FORK_BASE_ELEMENTS)
    fb = [a + b for a, b in
          zip(_udl_between(bb, root, base.weight_n_mm, root, b_hi),
              _udl_between(bb, root, gw, g_lo, min(g_hi, o_lo)))]
    for x, r in zip((o_lo, o_hi), react):
        fb[bb.node_at(x - root) * beam.DOF_PER_NODE] += r
    ub = bb._solve_with_bc(bb.stiffness(), fb[:], {0: 0.0, 1: 0.0})

    hand = bb.node_at(o_hi - root)
    tip = (bb.deflection(ub)[hand]
           + bb.rotation(ub)[hand] * (i_hi - o_hi)
           + bi.deflection(ui)[-1])
    return Fork(
        droop_mm=round(abs(tip), 3),
        stress_mpa=round(max(bi.max_stress_mpa(ui), bb.max_stress_mpa(ub)), 2),
        self_kg=round((base.rho_a * gbr_load.FORK_LEN_MM
                       + inner.rho_a * gbr_load.FORK_LEN_MM) * 1e3, 2),
        free_mm=i_hi - o_hi,
        hz=round(_free_span_hz(bi, na, nb), 3),
    )


def _section(h: float, w: float, t: float, e: float, rho: float,
             inner: bool) -> beam.Section:
    shrink = 2.0 * (t + FORK_SLIDE_CLEAR_MM) if inner else 0.0
    b, d = w - shrink, h - shrink
    i, a = _rhs(b, d, t)
    return beam.Section(e, i, a, d / 2.0, rho, frames.YIELD_MPA)


def _free_span_hz(bm: beam.Beam, *fixed: int) -> float:
    """안단의 1 차 굽힘진동수 [Hz] — 유리 몫을 선단 집중질량으로 얹는다."""
    tip_kg = glass_weight_n() / 2.0 / dynamics.G
    return _with_tip_mass(bm, tip_kg).fundamental_hz(tuple(fixed))


def fork_droop_mm() -> float:
    """설계 선단 처짐 [mm]."""
    return fork_static().droop_mm


def fork_droop_budget_mm() -> float:
    """허용 처짐 [mm] — 진입 높이가 예산이다. 더 처지면 유리가 목표 레일을 긁는다."""
    return gbr_load.SET_DOWN_APPROACH_MM


def fork_droop_ok() -> bool:
    return fork_droop_mm() < fork_droop_budget_mm()


def fork_hz() -> float:
    return fork_static().hz


def fork_wall_sweep(walls: tuple[float, ...] = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
                    ) -> tuple[tuple[float, float, float], ...]:
    """살두께를 훑는다 — (t, 처짐, 응력). 결론이 계획값에 매여 있는지 보는 자리다.

    단조롭지 않다. 살이 두꺼워지면 강성과 자중이 같이 늘고, 겹침 두 점의 반력이
    옮겨 앉으면서 밑단 외팔의 회전 기여가 뒤집히는 구간이 있다 — 그래도 전 구간이
    예산 안이라 **결론은 계획값에 안 매여 있다.**
    """
    out = []
    for t in walls:
        f = fork_static(wall_mm=t)
        out.append((t, f.droop_mm, f.stress_mpa))
    return tuple(out)


def fork_droop_span_mm() -> tuple[float, float]:
    ds = [d for _, d, _ in fork_wall_sweep()]
    return min(ds), max(ds)


# ── 슬롯 피치가 포크 깊이를 정한다 ──────────────────────────────────────
def fork_depth_room_mm() -> float:
    """슬롯 피치가 포크에 내주는 높이 [mm] — 깊이 + 선단처짐이 여기 들어가야 한다.

    목표 슬롯에 들어간 포크는 유리를 놓기 위해 `SET_DOWN_MM` 만큼 더 내려가고,
    그때 몸통 밑면이 **한 칸 아래 유리** 위를 지난다. 유리는 두 슬롯에서 똑같이
    늘어지므로 처짐 항은 서로 지워지고, 남는 것은 피치에서 유리 두께와 여유,
    그리고 접근분을 넘어 더 내려간 몫을 뺀 것이다.
    """
    extra = gbr_load.SET_DOWN_MM - gbr_load.SET_DOWN_APPROACH_MM
    return (gbr_load.slot_pitch_mm() - afr.LAMINATE_T_MM
            - gbr_load.GLASS_CLEARANCE_MM - extra)


def fork_depth_window_mm() -> tuple[float, float]:
    """포크 깊이가 들어갈 수 있는 구간 [mm].

    위는 피치, 아래는 처짐이다 — 얕아지면 휘어서 유리가 목표 레일을 긁는다.
    두 끝 모두 처짐을 통해 깊이에 매여 있으므로 훑어서 찾는다.
    """
    room, lo, hi = fork_depth_room_mm(), None, None
    for half in range(40, 221):                       # 20.0 … 110.0 mm, 0.5 간격
        h = half / 2.0
        try:
            f = fork_static(depth_mm=h)
        except ValueError:
            continue
        if f.droop_mm >= fork_droop_budget_mm():
            continue
        if h + f.droop_mm > room:
            continue
        lo = h if lo is None else lo
        hi = h
    if lo is None:
        raise ValueError("슬롯 피치 안에 들어가는 포크 깊이가 없다")
    return lo, hi


def fork_depth_ok() -> bool:
    lo, hi = fork_depth_window_mm()
    return lo <= gbr_load.FORK_H_MM <= hi


def fork_fits_the_pitch() -> tuple[float, float]:
    """(깊이 + 선단처짐, 슬롯이 내주는 높이) — 앞이 뒤보다 작아야 한다."""
    return round(gbr_load.FORK_H_MM + fork_droop_mm(), 3), round(fork_depth_room_mm(), 3)


def tg_gap_window_mm() -> tuple[float, float]:
    """TG-813 선단받이가 놓일 수 있는 틈 [mm] — 아래는 있고 위는 없다.

    두 요구가 서로를 밀어낸다.

      ① 평상시 안 닿아야 한다              틈 > 선단 처짐
      ② 소하강을 방해하면 안 된다           틈 > 선단 처짐 + 소하강

    ②가 ①을 삼키므로 하한은 처짐 + 소하강이다. **위 한계는 없다** — 위쪽에서
    「유리가 선반을 긁기 전에 받는다」를 걸면 틈 ≤ 진입 높이가 나와 하한과
    모순이다. 즉 이 부재는 슬롯 진입을 받쳐 줄 수 없고, 처짐이 예산의 1/4 이라
    **받쳐 줄 필요도 없다.** 남는 역할은 과대처짐 걸림쇠다.
    """
    return fork_droop_mm() + gbr_load.SET_DOWN_MM, float("inf")


def tg_gap_ok() -> bool:
    lo, _ = tg_gap_window_mm()
    return gbr_load.TG_GAP_MM > lo


# ── ② 무프레임 유리 ─────────────────────────────────────────────────────
def glass_on(lines_mm: tuple[float, ...]) -> dict[str, float]:
    """폭 1,400 유리 띠를 주어진 z 지지선 위에 올려 푼다."""
    if not lines_mm:
        return {"sag_mm": float("inf"), "stress_mpa": float("inf"), "lines": 0}
    width = gbr_load.GLASS_W_MM
    bm = beam.Beam(glass_section(), width, GLASS_ELEMENTS)
    pres = {}
    for z in lines_mm:
        offset = width / 2.0 + z
        if not -1e-9 <= offset <= width + 1e-9:
            raise ValueError(f"지지선 {z} 가 유리 밖이다")
        pres[bm.node_at(offset) * beam.DOF_PER_NODE] = 0.0
    u = bm._solve_with_bc(bm.stiffness(), bm.udl_vector(glass_strip_load_n_mm()),
                          pres)
    return {
        "sag_mm": round(max(abs(v) for v in bm.deflection(u)), 3),
        "stress_mpa": round(bm.max_stress_mpa(u), 3),
        "lines": len(lines_mm),
    }


def glass_on_shelf() -> dict[str, float]:
    """슬롯 선반 위 — 여기가 **오래 두는** 자세다."""
    return glass_on(gbr_load.shelf_bearing_lines_mm())


def glass_on_fork() -> dict[str, float]:
    """콤포크 위 — 이송 중 자세. 몇 초짜리라 단기 허용을 쓴다."""
    return glass_on(gbr_load.fork_lines_mm())


def allow_mpa(seconds: float) -> float:
    """지속시간 `seconds` 에서의 유리 허용응력 [MPa] — σ ∝ t^(−1/n)."""
    if seconds <= 0:
        raise ValueError("지속시간은 양수다")
    return round(afr.GLASS_ALLOW_MPA
                 * (GLASS_REF_S / seconds) ** (1.0 / GLASS_FATIGUE_N), 3)


def dwell_limit_s() -> float:
    """지금 선반 배치가 견디는 체류시간 [s] — 응력이 허용과 만나는 시각."""
    s = glass_on_shelf()["stress_mpa"]
    if s <= 0:
        return float("inf")
    return round(GLASS_REF_S * (afr.GLASS_ALLOW_MPA / s) ** GLASS_FATIGUE_N, 1)


def max_dwell_s() -> float:
    """한 장이 버퍼에 머무는 최대 시간 [s].

    선입선출이므로 **설정점 재고**가 다 빠지는 데 걸리는 시간이 곧 맨 아래 장의
    체류다 — `handoff` 가 유입·배출률에서 낸 재고를 그대로 쓴다.
    """
    stock = handoff.buffer_stock_target_slots()
    draw = handoff.downstream_rate().line_per_h
    return round(stock / draw * 3600.0, 1) if draw > 0 else float("inf")


def glass_keeps_its_strength() -> bool:
    """정적피로까지 보고도 유리가 버티는가."""
    return (dwell_limit_s() > max_dwell_s()
            and glass_on_fork()["stress_mpa"] < afr.GLASS_ALLOW_MPA)


# ── ③ 마스트와 정지 ─────────────────────────────────────────────────────
class _TipMass(beam.Beam):
    """선단에 집중질량을 얹은 보 — `mass()` 만 바꾸면 고유진동·시간적분이 따라온다."""

    def __init__(self, other: beam.Beam, tip_t: float) -> None:
        super().__init__(other.section, other.length, other.n_el, other.foundation)
        self.tip_t = float(tip_t)

    def mass(self) -> list[list[float]]:
        m = super().mass()
        m[self.ndof - 2][self.ndof - 2] += self.tip_t
        return m


def _with_tip_mass(bm: beam.Beam, tip_kg: float) -> beam.Beam:
    return _TipMass(bm, tip_kg * 1e-3)          # kg → tonne


def moving_kg() -> float:
    """포크 신장축이 끌고 가는 질량 [kg] — 콤포크 2 본(2 단씩) + 유리."""
    return round(2.0 * fork_static().self_kg + glass_weight_n() / dynamics.G, 2)


def mast_beam(height_mm: float | None = None) -> beam.Beam:
    """바닥에 물린 마스트 한 본 — 선단(승강 캐리지)에 움직이는 질량의 절반을 얹는다."""
    h = gbr_load.MAST_TOP_MM if height_mm is None else height_mm
    bm = beam.Beam(mast_section(), h, MAST_ELEMENTS)
    return _with_tip_mass(bm, moving_kg() / 2.0)


def mast_hz() -> float:
    """마스트 1 차 진동수 [Hz] — X(포크 방향) 흔들림."""
    return round(mast_beam().fundamental_hz((0, 1)), 3)


def mast_sway_mm(accel_mm_s2: float | None = None) -> float:
    """포크 신장 가감속이 마스트 선단을 미는 양 [mm]."""
    a = gbr_load.SERVO_A_MM_S2 if accel_mm_s2 is None else accel_mm_s2
    force = moving_kg() / 2.0 * (a / 1e3)       # kg · m/s² = N
    bm = mast_beam()
    u = bm._solve_with_bc(bm.stiffness(), _point(bm, force), {0: 0.0, 1: 0.0})
    return round(max(abs(v) for v in bm.deflection(u)), 4)


def _point(bm: beam.Beam, force_n: float) -> list[float]:
    f = [0.0] * bm.ndof
    f[bm.ndof - 2] = force_n
    return f


def settle_s(amplitude_mm: float | None = None,
             tolerance_mm: float | None = None,
             damping_ratio: float = 0.02) -> float:
    """진폭이 허용오차 밑으로 내려가는 데 드는 시간 [s] — A·e^(−ζωt) = tol."""
    a = mast_sway_mm() if amplitude_mm is None else amplitude_mm
    tol = gbr_load.STOP_TOLERANCE_MM if tolerance_mm is None else tolerance_mm
    if a <= tol:
        return 0.0
    w = 2.0 * math.pi * mast_hz()
    return round(math.log(a / tol) / (damping_ratio * w), 4)


def settle_is_not_the_limit() -> bool:
    """구조 정착이 `gbr_load.STOP_SETTLE_S` 를 못 채우는가 — 그러면 그 값은 센서 시간이다."""
    return settle_s() < gbr_load.STOP_SETTLE_S


# ── ④ 가속도 한계 ───────────────────────────────────────────────────────
def accel_limits_mm_s2() -> dict[str, float]:
    """설계 가속도의 상한들 [mm/s²]. 가장 작은 것이 구속이다."""
    droop = fork_droop_mm()
    budget = fork_droop_budget_mm()
    return {
        "유리 미끄럼 (μ·g)": round(drives.FRICTION_MU * dynamics.G * 1e3, 1),
        "포크 동적처짐 (예산 안)":
            round(dynamics.G * 1e3 * (budget / droop - 1.0), 1),
        "분기 정지 ±1.0 mm":
            round(gbr_load.SERVO_A_MM_S2 * gbr_load.STOP_TOLERANCE_MM
                  / max(mast_sway_mm(), 1e-9), 1),
    }


def accel_headroom() -> float:
    """설계 가속도 대비 여유 배수 — 1 보다 커야 한다."""
    return round(min(accel_limits_mm_s2().values()) / gbr_load.SERVO_A_MM_S2, 2)


def accel_binding() -> str:
    """어느 한계가 구속인가."""
    limits = accel_limits_mm_s2()
    return min(limits, key=limits.get)


# ── ⑤ 하이브리드 — 소하강 안착 ──────────────────────────────────────────
#
# 강체 하강(서보 프로파일)과 연속체 굽힘(유리)이 **한 순간에 만난다**. 포크가
# 내려오다 선반이 유리에 닿는 그 순간, 유리는
#
#   · 포크 위 자세(z ±540 지지)로 휘어 있고,
#   · 아직 아래로 v 만큼 내려가고 있으며,
#   · 그 다음부터는 선반 두 선(z ±650)에 매인다.
#
# 그래서 「포크 위 자세를 초기변위로, 하강속도를 초기속도로」 두고 선반 지지에서
# 시간적분한다. 이것이 강체와 연속체를 잇는 자리다 — 앞은 운동학이 정하고
# 뒤는 유한요소가 푼다.
#
# 축약 모델(1 자유도)로도 같은 답이 나와야 한다. 계단하중 + 초기속도의 정해는
#
#     x_peak = x_st + √((x₀ − x_st)² + (v₀/ω)²)
#
# 이고, `set_down_verify()` 가 유한요소 이력의 최댓값과 이것을 견준다.


@dataclass(frozen=True)
class SetDown:
    """안착 한 번 — 닿는 속도와 그때 유리가 받는 것."""

    contact_v_mm_s: float
    peak_sag_mm: float
    static_sag_mm: float
    peak_stress_mpa: float
    amplification: float

    @property
    def safe(self) -> bool:
        return self.peak_stress_mpa < allow_mpa(SET_DOWN_EVENT_S)


#: 안착 충격이 지속되는 시간 [s] — 유리 1 차 주기의 절반쯤이다. 정적피로 허용은
#: 이 시간에서 읽는다(짧을수록 세게 견딘다).
SET_DOWN_EVENT_S = 0.15
#: 유리 판의 구조 감쇠비 — 강 구조의 표준 1 차 감쇠와 같은 계획값이다.
GLASS_DAMPING = 0.02
#: 안착 이력을 몇 주기까지 밟는가 · 한 주기를 몇 걸음으로 나누는가.
SET_DOWN_CYCLES, SET_DOWN_STEPS = 2, 120


def _glass_beam(elements: int | None = None
                ) -> tuple[beam.Beam, dict[int, float], dict[int, float], int]:
    width = gbr_load.GLASS_W_MM
    bm = beam.Beam(glass_section(), width,
                   GLASS_ELEMENTS if elements is None else elements)
    shelf = {bm.node_at(width / 2.0 + z) * beam.DOF_PER_NODE: 0.0
             for z in gbr_load.shelf_bearing_lines_mm()}
    fork = {bm.node_at(width / 2.0 + z) * beam.DOF_PER_NODE: 0.0
            for z in gbr_load.fork_lines_mm()}
    return bm, shelf, fork, bm.node_at(width / 2.0) * beam.DOF_PER_NODE


def glass_sag_at_fork_mm() -> float:
    """선반에 얹힌 유리가 **포크 자리에서** 레일면보다 내려가는 양 [mm].

    포크는 이만큼 더 내려가야 유리에서 떨어진다 — `gbr_load.SET_DOWN_MM` 의 근거다.
    """
    bm, shelf, _, _ = _glass_beam()
    u = bm._solve_with_bc(bm.stiffness(),
                          bm.udl_vector(glass_strip_load_n_mm()), dict(shelf))
    node = bm.node_at(gbr_load.GLASS_W_MM / 2.0 + gbr_load.FORK_OFFSET_MM)
    return round(abs(bm.deflection(u)[node]), 3)


def set_down_required_mm() -> float:
    """포크가 유리에서 떨어지려면 내려야 하는 거리 [mm]."""
    return round(gbr_load.SET_DOWN_APPROACH_MM + glass_sag_at_fork_mm()
                 + gbr_load.STOP_TOLERANCE_MM, 3)


def set_down_releases_the_fork() -> bool:
    return gbr_load.SET_DOWN_MM >= set_down_required_mm()


def _set_down_peak_v_mm_s() -> float:
    """소하강 프로파일의 최고 속도 [mm/s] — 삼각형이면 √(a·s)."""
    s, a, v = gbr_load.SET_DOWN_MM, gbr_load.SERVO_A_MM_S2, gbr_load.SERVO_V_MM_S
    return round(min(v, math.sqrt(a * s)), 3)


def set_down_contact_v_mm_s() -> float:
    """설계 접촉속도 [mm/s] — 정지 허용오차만큼 일찍 닿았을 때 남아 있는 속도.

    명령이 자리에서 서면 접촉속도는 0 이다. 실제로는 축이 `STOP_TOLERANCE_MM`
    만큼 일찍 설 수 있고, 그 지점에서 감속 프로파일이 아직 갖고 있는 속도가
    √(2·a·tol) 다 — 임의로 고른 «최악»이 아니라 서보 사양이 내는 값이다.
    """
    return round(math.sqrt(2.0 * gbr_load.SERVO_A_MM_S2
                           * gbr_load.STOP_TOLERANCE_MM), 3)


def _rigid_datum(bm: beam.Beam, u: list[float], nodes: tuple[int, ...]
                 ) -> list[float]:
    """두 절점을 0 으로 만드는 강체운동(평행이동 + 회전)을 뺀다."""
    (a, b) = sorted(nodes)
    xa, xb = bm.x(a // beam.DOF_PER_NODE), bm.x(b // beam.DOF_PER_NODE)
    wa, wb = u[a], u[b]
    slope = (wb - wa) / (xb - xa)
    out = u[:]
    for n in range(bm.n_node):
        out[n * beam.DOF_PER_NODE] -= wa + slope * (bm.x(n) - xa)
        out[n * beam.DOF_PER_NODE + 1] -= slope
    return out


def set_down(contact_v_mm_s: float | None = None,
             steps: int = SET_DOWN_STEPS) -> SetDown:
    """안착을 **시간적분한다** — 포크 위 자세에서 선반 위 자세로 넘어가는 과도."""
    v = (set_down_contact_v_mm_s() if contact_v_mm_s is None
         else float(contact_v_mm_s))
    bm, shelf, fork, mid = _glass_beam(GLASS_TRANSIENT_ELEMENTS)
    w = bm.udl_vector(glass_strip_load_n_mm())
    on_fork = bm._solve_with_bc(bm.stiffness(), w[:], dict(fork))
    u0 = _rigid_datum(bm, on_fork, tuple(shelf))
    v0 = [v if i % beam.DOF_PER_NODE == 0 else 0.0 for i in range(bm.ndof)]
    on_shelf = bm._solve_with_bc(bm.stiffness(), w[:], dict(shelf))
    static = abs(bm.deflection(on_shelf)[mid // beam.DOF_PER_NODE])

    hz = _with_tip_mass(bm, 0.0).fundamental_hz(tuple(shelf))
    dt = 1.0 / hz / steps
    hist = beam.newmark(bm, int(steps * SET_DOWN_CYCLES), dt,
                        lambda *_: w, prescribed=dict(shelf),
                        damping_ratio=GLASS_DAMPING, u0=u0, v0=v0)
    peak, stress = 0.0, 0.0
    for u in hist:
        peak = max(peak, abs(u[mid]))
        stress = max(stress, bm.max_stress_mpa(u))
    return SetDown(
        contact_v_mm_s=round(v, 3),
        peak_sag_mm=round(peak, 3),
        static_sag_mm=round(static, 3),
        peak_stress_mpa=round(stress, 3),
        amplification=round(peak / static, 3) if static else 0.0,
    )


def set_down_reduced(contact_v_mm_s: float | None = None) -> float:
    """축약 1 자유도의 최대 처짐 [mm] — 계단하중 + 초기속도의 정해."""
    v = (set_down_contact_v_mm_s() if contact_v_mm_s is None
         else float(contact_v_mm_s))
    bm, shelf, fork, mid = _glass_beam()
    w = bm.udl_vector(glass_strip_load_n_mm())
    x_st = abs(bm._solve_with_bc(bm.stiffness(), w[:], dict(shelf))[mid])
    x0 = abs(_rigid_datum(bm, bm._solve_with_bc(bm.stiffness(), w[:], dict(fork)),
                          tuple(shelf))[mid])
    omega = 2.0 * math.pi * _with_tip_mass(bm, 0.0).fundamental_hz(tuple(shelf))
    return round(x_st + math.sqrt((x0 - x_st) ** 2 + (v / omega) ** 2), 3)


def set_down_verify() -> dict[str, float]:
    """유한요소 과도와 축약 1 자유도가 같은 답을 내는가."""
    fe = set_down().peak_sag_mm
    reduced = set_down_reduced()
    return {"fe_peak_mm": fe, "reduced_peak_mm": reduced,
            "error": round(abs(fe - reduced) / reduced, 4)}


def set_down_v_limit_mm_s() -> float:
    """유리가 허용응력에 닿는 접촉속도 [mm/s] — 이 위로는 안착이 유리를 깬다.

    축약 정해를 뒤집어 푼다. 최대 처짐이 허용응력에 해당하는 처짐과 같아지는 v 는

        v = ω·√((x_허용 − x_정적)² − (x₀ − x_정적)²)

    이고, 근호 안이 음수면 **속도와 무관하게** 이미 넘는다는 뜻이라 0 을 준다.
    유한요소 과도가 이 축약과 맞는지는 `set_down_verify()` 가 본다. 소하강
    프로파일이 애초에 낼 수 있는 속도(`_set_down_peak_v_mm_s()`)와 견주는 것은
    `set_down_profile_cannot_break_it()` 이다 — 여기서는 자르지 않는다.
    """
    st = glass_on_shelf()
    if st["stress_mpa"] <= 0:
        return _set_down_peak_v_mm_s()
    x_st, x_allow = st["sag_mm"], st["sag_mm"] * allow_mpa(
        SET_DOWN_EVENT_S) / st["stress_mpa"]
    bm, shelf, fork, mid = _glass_beam()
    w = bm.udl_vector(glass_strip_load_n_mm())
    x0 = abs(_rigid_datum(bm, bm._solve_with_bc(bm.stiffness(), w[:], dict(fork)),
                          tuple(shelf))[mid])
    inside = (x_allow - x_st) ** 2 - (x0 - x_st) ** 2
    if inside <= 0.0:
        return 0.0
    omega = 2.0 * math.pi * _with_tip_mass(bm, 0.0).fundamental_hz(tuple(shelf))
    return round(omega * math.sqrt(inside), 2)


def set_down_profile_cannot_break_it() -> bool:
    """소하강이 최고속으로 닿아도 유리가 안 깨지는가 — 위치오차와 무관한 상한이다."""
    return _set_down_peak_v_mm_s() < set_down_v_limit_mm_s()


def set_down_has_margin() -> bool:
    return set_down_contact_v_mm_s() < set_down_v_limit_mm_s()


# ── ⑥ 승강 포락선 — 접힌 포크가 셔틀 데크를 지나간다 ────────────────────
def reachable_slots() -> tuple[int, ...]:
    """접힌 콤포크가 셔틀 데크를 안 건드리고 닿을 수 있는 슬롯 번호.

    **여기서 셀 배치가 걸린다.** 접힌 포크는 데크 한가운데(x 300…2,900) 위에
    누워 있고, 승강은 슬롯 340…2,236 을 훑는다. 데크 상면은 라인과 같은
    950 mm 라, 포크 밑면이 그 밑으로 내려가는 슬롯에는 **갈 수가 없다** —
    포크가 데크를 뚫는다. 낮은 슬롯이 통째로 못 쓰이는 것이고, 이것은 계산으로
    고칠 수 있는 값이 아니라 배치가 정할 일이다 (랙을 데크 위로 올리거나,
    적재기를 데크 밖으로 내거나). 숫자만 여기 남긴다.
    """
    from . import handoff, layout
    deck_top = float(layout.LINE_TRANSFER_MM)
    pitch = gbr_load.slot_pitch_mm()
    out = []
    for k in range(1, handoff.SLOTS_PER_CARRIAGE + 1):
        rail = gbr_load.SLOT_FIRST_MM + pitch * (k - 1) + gbr_load.SHELF_T_MM / 2
        low = rail + gbr_load.SET_DOWN_APPROACH_MM - gbr_load.SET_DOWN_MM \
            - gbr_load.FORK_H_MM
        if low >= deck_top:
            out.append(k)
    return tuple(out)


def slot_reach_gap() -> int:
    """못 닿는 슬롯 수."""
    from . import handoff
    return handoff.SLOTS_PER_CARRIAGE - len(reachable_slots())


def travel_envelope_is_clear() -> bool:
    return slot_reach_gap() == 0


# ── 요약 ────────────────────────────────────────────────────────────────
def summary() -> dict[str, object]:
    fork, sd = fork_static(), set_down()
    return {
        "fork_droop_mm": fork.droop_mm,
        "fork_stress_mpa": fork.stress_mpa,
        "fork_self_kg": fork.self_kg,
        "fork_free_mm": fork.free_mm,
        "fork_hz": fork.hz,
        "fork_droop_span_mm": fork_droop_span_mm(),
        "fork_depth_window_mm": fork_depth_window_mm(),
        "fork_fits_the_pitch": fork_fits_the_pitch(),
        "glass_on_shelf": glass_on_shelf(),
        "glass_on_fork": glass_on_fork(),
        "glass_sag_at_fork_mm": glass_sag_at_fork_mm(),
        "set_down_required_mm": set_down_required_mm(),
        "dwell_limit_s": dwell_limit_s(),
        "max_dwell_s": max_dwell_s(),
        "mast_hz": mast_hz(),
        "mast_sway_mm": mast_sway_mm(),
        "settle_s": settle_s(),
        "accel_binding": accel_binding(),
        "accel_headroom": accel_headroom(),
        "set_down_v_mm_s": sd.contact_v_mm_s,
        "set_down_v_limit_mm_s": set_down_v_limit_mm_s(),
        "set_down_peak_sag_mm": sd.peak_sag_mm,
        "set_down_amplification": sd.amplification,
        "set_down_stress_mpa": sd.peak_stress_mpa,
        "reachable_slots": len(reachable_slots()),
        "slot_reach_gap": slot_reach_gap(),
    }


def checks() -> dict[str, tuple[float, float, bool]]:
    """(값, 한계, 통과) — 셀이 수치해석을 통과하는가."""
    sd = set_down()
    return {
        "포크 선단 처짐": (fork_droop_mm(), fork_droop_budget_mm(), fork_droop_ok()),
        "포크 깊이 ↔ 슬롯 피치": (*fork_fits_the_pitch(), fork_depth_ok()),
        "포크 응력": (fork_static().stress_mpa, frames.YIELD_MPA / 2.0,
                  fork_static().stress_mpa < frames.YIELD_MPA / 2.0),
        "소하강이 포크를 놓는가": (gbr_load.SET_DOWN_MM, set_down_required_mm(),
                        set_down_releases_the_fork()),
        "TG-813 걸림쇠 틈": (gbr_load.TG_GAP_MM, tg_gap_window_mm()[0], tg_gap_ok()),
        "선반 위 유리 (정적피로)": (max_dwell_s(), dwell_limit_s(),
                             dwell_limit_s() > max_dwell_s()),
        "포크 위 유리": (glass_on_fork()["stress_mpa"], afr.GLASS_ALLOW_MPA,
                    glass_on_fork()["stress_mpa"] < afr.GLASS_ALLOW_MPA),
        "안착 충격": (sd.peak_stress_mpa, allow_mpa(SET_DOWN_EVENT_S), sd.safe),
        "안착 접촉속도": (set_down_contact_v_mm_s(), set_down_v_limit_mm_s(),
                    set_down_has_margin()),
        "소하강 최고속에서도": (_set_down_peak_v_mm_s(), set_down_v_limit_mm_s(),
                       set_down_profile_cannot_break_it()),
        "축약 ↔ 유한요소": (set_down_verify()["error"], 0.05,
                       set_down_verify()["error"] < 0.05),
        "가속도 여유": (accel_headroom(), 1.0, accel_headroom() > 1.0),
        "승강 포락선 (미해결)": (len(reachable_slots()), slot_reach_gap(),
                          travel_envelope_is_clear()),
    }


def main() -> None:
    for key, value in summary().items():
        print(f"  {key:24} {value}")
    print()
    for name, (value, limit, ok) in checks().items():
        print(f"  {'OK ' if ok else 'NG '} {name:22} {value} / {limit}")


if __name__ == "__main__":
    main()
