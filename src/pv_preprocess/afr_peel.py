# -*- coding: utf-8 -*-
"""AFR-101 프레임 제거의 **연속체 해석** — 무엇이 얼마나 휘면서 빠지는가.

`frames.check()` 는 자유 길이를 **입력으로 받아** 외팔보 처짐 한 값을 준다.
그런데 인발에서 자유 길이는 입력이 아니라 결과다 — 롤러가 당기면 접착이 어디까지
끊어지는지가 풀려야 나온다. 그리고 3D 가 필요한 것은 한 값이 아니라 **모양**이다.
그래서 여기서는 `beam.py` 의 유한요소로 프레임 전체를 풀고, 접착을 Winkler 탄성
지지로 두어 견인력이 강도를 넘는 자리를 순서대로 떼어 낸다.

두 하중 케이스가 있다.

* **장변 인발** — LA-401 캐리지의 홈 롤러가 프레임을 옆으로 당기며 LM 을 탄다.
  접착 위의 보를 한 점에서 당기는 문제라 특성길이 β⁻¹ = (4EI/k)^¼ 가 휨이
  잦아드는 크기를 정한다. 이 값이 화면에서 보이는 곡선의 크기다.
* **단변 밀어내기** — PB-261 쇠막대가 변 전체를 한 몸으로 민다. 막대가 강체가
  아니라 스팬 중앙이 처지므로, 그 처짐이 그대로 알루미늄의 **강제변위 형상**이
  된다. 여기서 프레임 자신의 휨은 작다 — 발주처가 말한 "직선으로"가 맞다.

**이 해석이 말하는 것 하나** — 설계 인발력 `frames.PEEL_FORCE_N` 은 정상박리에
필요한 힘보다 크다. 정상박리 조건은 P = q_max / 2β 이고 그보다 큰 힘으로 당기면
균열이 캐리지를 앞질러 달린다 (stiff beam / brittle bond 의 전형적인 불안정
박리다 — AE-401 음향방출 감시가 있는 이유이기도 하다). 그 비를 `stability()` 가
돌려주고, 도면·영상은 그 결과를 그대로 그린다. 접착 물성은 실측 전 계획값이며,
실물 실란트 시험이 오면 여기 숫자만 고치면 계산·도면·영상이 같이 따라온다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import afr, beam, frames, kinematics

#: 알루미늄 밀도 [tonne/mm³] — 6063.
ALU_DENSITY_T_MM3 = 2.70e-9

# ── 접착 (실란트) — 실측 전 계획값 ──────────────────────────────────────
#: 프레임–라미네이트 실란트 (부틸/실리콘계) 탄성계수 [MPa].
SEALANT_E_MPA = 2.0
#: 실란트 비드 폭 [mm] — 프레임 채널 안에서 유리 가장자리를 무는 폭.
SEALANT_BEAD_MM = 8.0
#: 실란트 층 두께 [mm].
SEALANT_T_MM = 3.0
#: 실란트 파괴강도 [MPa].
SEALANT_STRENGTH_MPA = 0.6
#: 단위 접착면적당 파괴에너지 [N/mm] — 고무질이라 크다. 응집영역 길이를 정한다.
SEALANT_GC_N_MM = 0.8

#: 해석 요소 수 — 수렴은 `tests/test_pv_beam.py` 가 확인한다.
LONG_ELEMENTS = 100
SHORT_ELEMENTS = 60

#: 영상이 쓰는 자세 수 — 인발 한 사이클을 이만큼으로 나눠 굽는다.
SEQUENCE_SAMPLES = 41


def section() -> beam.Section:
    """프레임 단면 — 인발 방향 휨. 다각형에서 전부 나온다."""
    p = frames.profile()
    return beam.Section(
        e_mpa=frames.YOUNGS_MODULUS_MPA,
        i_mm4=p["i_lateral_mm4"],
        area_mm2=p["area_mm2"],
        c_mm=p["c_lateral_mm"],
        density_t_mm3=ALU_DENSITY_T_MM3,
        yield_mpa=frames.YIELD_MPA,
    )


def gravity_section() -> beam.Section:
    """자중 처짐(위아래)용 — 같은 단면의 다른 축이다."""
    p = frames.profile()
    return beam.Section(frames.YOUNGS_MODULUS_MPA, p["i_vertical_mm4"],
                        p["area_mm2"], p["c_vertical_mm"],
                        ALU_DENSITY_T_MM3, frames.YIELD_MPA)


def bond() -> beam.Foundation:
    return beam.Foundation(SEALANT_E_MPA, SEALANT_BEAD_MM, SEALANT_T_MM,
                           SEALANT_STRENGTH_MPA)


def decay_length_mm() -> float:
    """β⁻¹ — 휨이 잦아드는 특성길이. 화면에서 보이는 곡선의 크기다."""
    return round(bond().decay_length_mm(section()), 1)


def steady_peel_force_n() -> float:
    """정상박리에 필요한 힘 P = q_max / 2β — 이보다 크면 균열이 앞질러 달린다."""
    b = bond()
    return round(b.strength_n_mm / (2.0 * b.beta_1_mm(section())), 1)


def stability() -> float:
    """설계 인발력 ÷ 정상박리력. 1 을 넘으면 불안정 박리다."""
    return round(frames.PEEL_FORCE_N / steady_peel_force_n(), 3)


def peel_is_stable() -> bool:
    return stability() <= 1.0


def cohesive_length_mm() -> float:
    """응집영역(process zone) 길이 ℓ = E·G_c / σ² — 접착이 끊기는 구간의 크기."""
    return round(frames.YOUNGS_MODULUS_MPA * SEALANT_GC_N_MM
                 / SEALANT_STRENGTH_MPA ** 2 * 1e-3, 1)


# ── 장변 인발 ────────────────────────────────────────────────────────────
def long_edge_length_mm() -> float:
    return float(kinematics.PANEL_MM[0])


def new_long_beam(elements: int = LONG_ELEMENTS) -> beam.Beam:
    return beam.Beam(section(), long_edge_length_mm(), elements, bond())


@dataclass(frozen=True)
class Frame:
    """한 자세 — 영상의 한 장이다."""

    t_s: float
    carriage_mm: float
    command_mm: float
    front_mm: float
    reaction_n: float
    max_stress_mpa: float
    w_mm: tuple[float, ...]


def long_edge_sequence(samples: int = SEQUENCE_SAMPLES,
                       elements: int = LONG_ELEMENTS) -> tuple[Frame, ...]:
    """캐리지가 끝에서 중앙으로 가는 동안의 처짐장 — 접착 상태를 이어서 푼다.

    앞의 얼마는 **끝단 벌림**(캐리지가 제자리에서 당기는 구간)이고, 그 뒤가 LM
    주행이다. 접착은 한 번 끊어지면 돌아오지 않으므로 보 하나를 계속 쓴 채로
    자세를 진행시킨다 — 자세마다 새 보를 만들면 균열 이력이 사라진다.
    """
    b = new_long_beam(elements)
    pull = float(afr.pull_travel_mm())
    open_s = afr.LM_STROKE_MM / afr.LM_SPEED_MM_S * 0.12      # 벌림에 쓰는 시간
    travel_s = afr.lm_travel_time_s()
    total = open_s + travel_s
    n_open = max(2, round(samples * open_s / total))
    out: list[Frame] = []
    for i in range(samples):
        t = total * i / (samples - 1)
        if t <= open_s:                                   # 끝단 벌림
            xc, cmd = 0.0, pull * (t / open_s)
        else:                                             # LM 주행
            xc = afr.LM_STROKE_MM * (t - open_s) / travel_s
            cmd = pull
        st = beam.peel(b, b.node_at(xc), cmd, udl_n_mm=0.0,
                       force_cap_n=frames.PEEL_FORCE_N)
        out.append(Frame(round(t, 3), round(xc, 1), round(cmd, 2),
                         round(st.front_mm, 1), round(st.reaction_n, 1),
                         round(st.max_stress_mpa, 2),
                         tuple(round(v, 4) for v in st.w_mm)))
    return tuple(out)


def released_at_end_opening_mm() -> float:
    """끝단을 벌리는 것만으로 떨어지는 길이 — 불안정 박리의 크기다."""
    b = new_long_beam()
    st = beam.peel(b, 0, float(afr.pull_travel_mm()),
                   force_cap_n=frames.PEEL_FORCE_N)
    return round(st.front_mm, 1)


def long_edge_peak_stress_mpa() -> float:
    return max(f.max_stress_mpa for f in long_edge_sequence())


def long_edge_yields() -> bool:
    return long_edge_peak_stress_mpa() > frames.YIELD_MPA


# ── 단변 밀어내기 ────────────────────────────────────────────────────────
def short_edge_length_mm() -> float:
    return float(kinematics.PANEL_MM[1])


def short_edge_profile(elements: int = SHORT_ELEMENTS) -> tuple[float, ...]:
    """쇠막대가 미는 단변의 강제변위 형상 [mm].

    막대는 스팬 양끝(실린더 자리)에서 밀리고 자기 처짐만큼 중앙이 뒤처진다.
    그 처짐 형상을 유한요소로 풀어(등분포 반력을 받는 단순지지 보) 알루미늄에
    그대로 준다 — 도면이 쓰던 포물선 근사 대신 실제 4차 형상이다.
    """
    span = float(afr.cylinder_span_mm())
    bar = beam.Section(afr.STEEL_E_MPA, afr.bar_second_moment_mm4(), afr.BAR_W_MM * afr.bar_h_mm(),
                       afr.bar_h_mm() / 2.0, afr.STEEL_DENSITY_KG_M3 * 1e-12,
                       afr.STEEL_ALLOW_MPA)
    bb = beam.Beam(bar, span, elements)
    q = afr.required_push_kn() * 1000.0 / span            # 프레임이 되미는 등분포
    u = bb.solve_static(prescribed={0: 0.0, bb.ndof - 2: 0.0}, udl_n_mm=-q)
    sag = bb.deflection(u)
    push = float(afr.push_travel_mm())
    # 막대 스팬 밖(단변 끝)은 막대가 없다 — 끝값을 유지한다.
    edge = short_edge_length_mm()
    out = []
    for i in range(elements + 1):
        x = edge * i / elements
        s = (x - (edge - span) / 2.0) / span              # 막대 좌표 0…1
        j = min(elements, max(0, round(s * elements)))
        out.append(round(push + sag[j], 4))
    return tuple(out)


def short_edge_lag_mm() -> float:
    """단변 중앙이 뒤처지는 양 — 막대 처짐 그대로다."""
    p = short_edge_profile()
    return round(max(p) - min(p), 4)


# ── 브라우저 물리엔진이 받는 상수 ────────────────────────────────────────
def xpbd_constants(nodes_long: int = 33, nodes_short: int = 21) -> dict[str, float]:
    """화면에서 도는 XPBD 솔버의 물리 상수 — 전부 위 모델에서 나온다.

    XPBD 의 컴플라이언스는 강성의 역수다 (α = 1/k). 요소 길이 L 의 보에서
    굽힘 구속의 강성은 EI/L, 늘어남 구속은 EA/L 이므로 그 역수를 준다.
    질량은 선질량 × 요소 길이다. 이렇게 두면 화면의 정적 처짐이 유한요소 해와
    같아진다 — `tools/check_afr_physics.mjs` 가 그것을 잰다.
    """
    s = section()
    b = bond()
    ll = long_edge_length_mm() / (nodes_long - 1)
    ls = short_edge_length_mm() / (nodes_short - 1)
    return {
        "nodesLong": nodes_long,
        "nodesShort": nodes_short,
        "segLongMm": round(ll, 3),
        "segShortMm": round(ls, 3),
        "ei": s.ei,
        "ea": s.ea,
        "rhoA": s.rho_a,
        "massLongT": round(s.rho_a * ll, 9),
        "massShortT": round(s.rho_a * ls, 9),
        "bendComplianceLong": round(ll / s.ei, 14),
        "bendComplianceShort": round(ls / s.ei, 14),
        "stretchComplianceLong": round(ll / s.ea, 12),
        "stretchComplianceShort": round(ls / s.ea, 12),
        "bondKNMm2": round(b.k_n_mm2, 4),
        "bondStrengthNMm": round(b.strength_n_mm, 4),
        "bondBreakMm": round(b.break_deflection_mm, 4),
        "bondGcNMm": SEALANT_GC_N_MM,
        "bondSeparationMm": round(2.0 * SEALANT_GC_N_MM * SEALANT_BEAD_MM
                                  / b.strength_n_mm, 4),
        "decayLengthMm": decay_length_mm(),
        "peelForceN": frames.PEEL_FORCE_N,
        "steadyPeelN": steady_peel_force_n(),
        "stability": stability(),
        "yieldMpa": frames.YIELD_MPA,
        "gravityMmS2": 9810.0,
    }


def summary() -> dict[str, object]:
    p = frames.profile()
    return {
        "profile": p,
        "outline": [list(pt) for pt in frames.outline()],
        "massKgM": frames.profile_mass_kg_m(),
        "wallDevelopedMm": frames.wall_developed_mm(),
        "decayLengthMm": decay_length_mm(),
        "cohesiveLengthMm": cohesive_length_mm(),
        "steadyPeelN": steady_peel_force_n(),
        "designPeelN": frames.PEEL_FORCE_N,
        "stability": stability(),
        "stable": peel_is_stable(),
        "releasedAtEndOpeningMm": released_at_end_opening_mm(),
        "shortEdgeLagMm": short_edge_lag_mm(),
        "longEdgePeakStressMpa": long_edge_peak_stress_mpa(),
        "longEdgeYields": long_edge_yields(),
    }


# ── 3D 가 쓰는 단면 (도심 기준·삼각분할까지) ─────────────────────────────
def _ear_clip(pts: list[tuple[float, float]]) -> tuple[int, ...]:
    """단순 다각형의 귀 자르기 삼각분할 — 마구리면을 덮는 인덱스를 낸다."""
    n = len(pts)
    idx = list(range(n))
    area2 = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
                for i in range(n))
    if area2 < 0:                                   # 반시계로 맞춘다
        idx.reverse()

    def cross(o, a, b):
        return ((pts[a][0] - pts[o][0]) * (pts[b][1] - pts[o][1])
                - (pts[a][1] - pts[o][1]) * (pts[b][0] - pts[o][0]))

    def inside(p, a, b, c):
        d1, d2, d3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    out: list[int] = []
    guard = 0
    while len(idx) > 3 and guard < 10_000:
        guard += 1
        for k in range(len(idx)):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if cross(a, b, c) <= 0:                 # 볼록한 꼭짓점만 귀가 된다
                continue
            if any(inside(p, a, b, c) for p in idx if p not in (a, b, c)):
                continue
            out += [a, b, c]
            del idx[k]
            break
        else:                                        # pragma: no cover - 안전망
            raise RuntimeError("삼각분할이 막혔다 — 단면이 단순 다각형이 아니다")
    out += idx[:3]
    return tuple(out)


def section_outline_m() -> tuple[tuple[float, float], ...]:
    """3D 가 스윕하는 단면 (m) — 도심이 원점이고, u 는 바깥면에서 안쪽으로.

    같은 다각형에서 `frames.profile()` 의 면적·2차 모멘트가 나온다. 화면이
    그리는 단면과 계산이 쓴 단면이 같다는 것이 이 함수 하나로 보장된다.
    """
    p = frames.profile()
    return tuple((round((u - p["cu_mm"]) / 1000.0, 6),
                  round((v - p["cv_mm"]) / 1000.0, 6))
                 for u, v in frames.outline())


def section_cap_indices() -> tuple[int, ...]:
    return _ear_clip([(u, v) for u, v in frames.outline()])


def physics_si() -> dict[str, float]:
    """브라우저 물리엔진이 받는 SI 상수 — m·kg·s·N."""
    p = frames.profile()
    b = bond()
    return {
        "ei": round(frames.YOUNGS_MODULUS_MPA * p["i_lateral_mm4"] / 1e6, 4),   # N·m²
        "eiVert": round(frames.YOUNGS_MODULUS_MPA * p["i_vertical_mm4"] / 1e6, 4),
        "ea": round(frames.YOUNGS_MODULUS_MPA * p["area_mm2"], 1),              # N
        "rhoA": frames.profile_mass_kg_m(),                                     # kg/m
        "bondK": round(b.k_n_mm2 * 1e6, 1),        # N/m per m
        "bondQ": round(b.strength_n_mm * 1e3, 1),  # N/m
        "bondBreak": round(b.break_deflection_mm / 1000.0, 7),                  # m
        "bondSep": round(2.0 * SEALANT_GC_N_MM * SEALANT_BEAD_MM
                         / b.strength_n_mm / 1000.0, 7),                        # m
        "peelN": frames.PEEL_FORCE_N,
        "pushN": round(afr.required_push_kn() * 1000.0, 1),
        "decayM": round(decay_length_mm() / 1000.0, 5),
        "yieldMpa": frames.YIELD_MPA,
        "stability": stability(),
        "steadyPeelN": steady_peel_force_n(),
    }


def front_curve(samples: int = 25) -> tuple[tuple[float, float], ...]:
    """(끝단 벌림 진행률, 접착 전선 위치 m) — 유한요소가 낸 균열 이력.

    영상은 이 곡선으로 접착을 푼다. 되감아도 같은 자리에서 같은 값이 나오므로
    스크럽이 어긋나지 않는다 — 화면에서 도는 것은 **모양**(XPBD)이고, 균열이
    어디까지 갔는지는 여기 유한요소 결과가 정한다.
    """
    b = new_long_beam()
    pull = float(afr.pull_travel_mm())
    out: list[tuple[float, float]] = []
    for i in range(samples):
        frac = i / (samples - 1)
        st = beam.peel(b, 0, pull * frac, force_cap_n=frames.PEEL_FORCE_N)
        out.append((round(frac, 4), round(st.front_mm / 1000.0, 4)))
    return tuple(out)
