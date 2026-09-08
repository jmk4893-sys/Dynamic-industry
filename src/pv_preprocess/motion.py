# -*- coding: utf-8 -*-
"""돌 수 있게 두고 다시 본 세 장면 — `rigid` 엔진의 적용.

`dynamics.py` 는 세 장면을 자유도 하나로 감았다. 그 답들은 틀리지 않았지만
**물체가 안 돈다고 가정한 답**이다. 여기서 회전을 풀어 준다.

  1. **겹장이 포획빔에 떨어질 때** — 지금 모형은 최대 반력을 빔 수로 나눈다.
     그러려면 네 본이 다 닿아야 한다. **닿는가**부터 본다. 안 닿는다 —
     행 ∓580 은 프레임 안쪽이라 그 밑이 허공이고, 행 ∓720 은 패널 바깥끝을
     10 mm 만 문다. 잡는 본은 넷이 아니라 **둘**이고 빔당 힘이 1.44 배다.
  2. **떨어진 패널이 빔 위에 남는가** — 포획빔의 일은 받는 것이 아니라
     **잡는 것**이다. 얹히는 선반이 10 mm 뿐이고 되튐이 79 mm 라, 이 구간을
     정하는 것은 힘이 아니라 자리다.
  3. **마찰 롤러가 미끄러진 뒤** — 미끄러지느냐는 정적으로 나오지만 미끄러진
     **뒤 몇 도를 잃느냐**는 안 나온다. `dynamics` 의 주석이 위상 손실을
     걱정하면서도 값을 못 냈던 자리다. 택트 2 배에서 17.4° 다.

그리고 넷째로 **전도(EOAT)** 를 본다. 이쪽은 결과가 「한계가 아니다」이고,
그 null 도 값으로 남긴다 — 확인 안 한 것과 확인해서 아닌 것은 다르다.

**닫힌 답과 열린 답을 섞지 않는다.** 접촉 지도와 본수 효과는 도면집 값만으로
닫힌다. 도착 자세(기울기·가로 속도)는 **재야 아는 것**이고, 시작품 시험
T-10 이 이미 그 시험이다 — 여기서는 자세를 쓸어 보며 「자세는 안 정한다」는
것까지만 말한다.

**여기서 처음 적는 값은 하나뿐이다** — 프레임 하부 지지폭. 그 하나조차
결론을 좌우하지 않는다는 것을 `bearing_conclusion_is_robust()` 가 폭을
쓸어 보며 확인한다. 나머지는 전부 `kinematics`·`drives`·`dynamics`·
`catch`·`afr` 에서 읽는다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.motion
"""

from __future__ import annotations

import math

from . import afr, catch, drives, dynamics, kinematics, rigid

#: 패널 프레임이 **밑에서** 하중을 받을 수 있는 폭 (mm, 바깥끝에서 안쪽으로).
#:
#: **여기서 처음 적는 값이고, 가정이다.** 도면집에 있는 것은 조 패드가 프레임
#: **상부** 플랜지를 무는 폭(`JAW_PAD_CONTACT_MM` 25)뿐이다. 하부 플랜지 폭은
#: 프레임 단면표가 와야 안다. 상부와 같다고 두었다.
#:
#: 값이 틀려도 결론은 안 바뀐다 — `bearing_conclusion_is_robust()` 가 5…90 mm
#: 를 쓸어 보며 그것을 확인한다. 유리면은 프레임보다 위에 있어(프레임 높이 75)
#: 빔이 닿을 수 없으므로, **닿는 곳은 프레임 밑뿐이다.**
FRAME_BEARING_MM = kinematics.JAW_PAD_CONTACT_MM

#: 정지마찰이 한계에 닿기까지 허용하는 미소 미끄럼 (mm). **수치 장치다** —
#: 정지마찰을 아주 뻣뻣한 접선 스프링으로 흉내 내는 폭이고, 값이 작을수록
#: 이상적인 쿨롱에 가깝다. 답이 이 값에 안 따르는지는
#: `slip_is_not_a_numerical_artifact()` 가 확인한다.
MICROSLIP_MM = 0.05

#: 그 접선 스프링의 감쇠비. **역시 수치 장치이고, 크게 잡는 것이 맞다.**
#:
#: 처음에 0.7 을 주었더니 정격 택트에서 요구 토크가 132.7 N·m 로 나왔다 —
#: `dynamics.flip_slip()` 의 109.5 보다 21 % 크다. 사다리꼴은 t=0 에 최대
#: 가속으로 바로 들어가는 계단 입력이라 스프링이 오버슛한 것이다. 그럴듯한
#: 이야기(「구동계가 무르면 계단 입력이 증폭된다」)라 하마터면 발견으로 적을
#: 뻔했는데, **감쇠비를 0.7 → 5 로 바꾸니 132.7 → 110.5 로 내려갔다.**
#: 진짜 접촉 강성을 모르는 채로는 증폭분이 내 선택일 뿐이라 발견이 아니다.
#: 그래서 스프링이 제 동역학을 못 내도록 크게 잡고, **요구 토크가 정적
#: 모형을 재현하는지**로 그것을 확인한다 (`demand_matches_the_static_model`).
STICK_DAMPING = 5.0


#: 포획빔 각관의 폭 (mm) — 도면집 CD-BM-01 단면에서 읽는다.
def beam_width_mm() -> float:
    _length, width, _depth = catch._beam().size
    return float(width)


# ── 1. 접촉 지도 — 네 본 중 몇 본이 닿는가 ──────────────────────────────
def frame_bearing_span_mm(width_mm: float | None = None) -> tuple[float, float]:
    """패널 한쪽 프레임이 하중을 받을 수 있는 구간 (mm, 패널 중심 기준)."""
    w = FRAME_BEARING_MM if width_mm is None else width_mm
    outer = kinematics.PANEL_MM[1] / 2.0
    return (outer - w, outer)


def beam_span_mm(row_mm: float) -> tuple[float, float]:
    half = beam_width_mm() / 2.0
    return (row_mm - half, row_mm + half)


def bearing_overlap_mm(row_mm: float, width_mm: float | None = None) -> float:
    """빔 한 본이 프레임 밑에 실제로 물리는 폭 (mm). 0 이면 안 닿는다."""
    lo, hi = beam_span_mm(abs(row_mm))
    flo, fhi = frame_bearing_span_mm(width_mm)
    return max(0.0, min(hi, fhi) - max(lo, flo))


def contact_map(width_mm: float | None = None) -> list[dict[str, float]]:
    """네 본 각각이 무엇에 닿는지 — 도면의 행 값에서 바로 나온다."""
    out = []
    for row in kinematics.CATCH_BEAM_ROWS_MM:
        lo, hi = beam_span_mm(abs(row))
        overlap = bearing_overlap_mm(row, width_mm)
        out.append({
            "rowMm": float(row),
            "spanLoMm": lo, "spanHiMm": hi,
            "overlapMm": overlap,
            "bears": overlap > 0.0,
            #: 프레임 안쪽이면 그 밑은 허공이다 — 유리는 프레임 높이만큼 위에 있다.
            "underGlass": hi < frame_bearing_span_mm(width_mm)[0],
        })
    return out


def bearing_rows_mm(width_mm: float | None = None) -> tuple[float, ...]:
    return tuple(c["rowMm"] for c in contact_map(width_mm) if c["bears"])


def bearing_beams() -> int:
    return len(bearing_rows_mm())


def bearing_conclusion_is_robust(lo: float = 5.0, hi: float = 90.0,
                                 step: float = 5.0) -> bool:
    """하부 지지폭을 몰라도 「안쪽 두 본은 안 닿는다」가 유지되는가.

    안쪽 행(∓580)의 각관은 |z| 550…610 을 덮는다. 프레임이 바깥끝(700)에서
    안쪽으로 90 mm 넘게 들어와야 610 에 닿는데, 그런 프레임은 유리 면적을
    그만큼 잡아먹는다. **폭을 어떻게 잡아도 안쪽 두 본은 논다.**
    """
    w = lo
    while w <= hi:
        inner = min(abs(r) for r in kinematics.CATCH_BEAM_ROWS_MM)
        if bearing_overlap_mm(inner, w) > 0.0:
            return False
        w += step
    return True


def glass_gap_mm(laminate_mm: float = 10.0) -> float:
    """안쪽 빔의 윗면에서 유리 밑면까지의 거리 (mm) — **왜 못 닿는지.**

    네 본은 한 평면으로 전개된다(`catch.design_plane_mm()` 이 평면 하나다).
    바깥 본이 프레임 밑면에 닿으니 안쪽 본의 윗면도 그 평면에 있다. 프레임은
    높이 75 이고 상면이 유리보다 4 mm 솟아 있으므로(`PANEL_FRAME_GLASS_STEP_MM`),
    라미네이트 두께를 빼고도 그만큼이 남는다.

    라미네이트 두께는 도면집에 없다. 그래서 인자로 두고, 두껍게 잡아도
    양수임을 `bearing_conclusion_is_robust` 옆에서 확인한다 — 71 mm 를
    넘는 라미네이트라야 닿는데 그런 모듈은 없다.
    """
    return (kinematics.PANEL_FRAME_H_MM
            - kinematics.PANEL_FRAME_GLASS_STEP_MM - laminate_mm)


def best_row_mm(width_mm: float | None = None) -> float:
    """물림이 가장 큰 행 위치 (mm) — **고칠 자리를 값으로 낸다.**

    각관을 패널 바깥끝(∓700) 밖으로 내밀지 않으면서 프레임 지지 구간을
    가장 많이 덮는 자리다. 폭 60 각관과 지지 구간 675…700 이면 ∓670 이고
    그때 물림이 지지폭 전체인 25 mm 가 된다 — 지금 ∓720 의 10 mm 에서
    2.5 배다. 행 하나만 옮기면 되는 이야기라 이 값을 남긴다.
    """
    half = beam_width_mm() / 2.0
    flo, fhi = frame_bearing_span_mm(width_mm)
    return min(fhi - half, fhi - half + (fhi - flo))


def best_ledge_mm(width_mm: float | None = None) -> float:
    return bearing_overlap_mm(best_row_mm(width_mm), width_mm)


def four_beams_cannot_all_bear(width_mm: float | None = None) -> bool:
    """네 본이 다 프레임 밑에 물리는 배치가 애초에 있는가 — **없다.**

    한쪽 프레임의 지지 구간은 25 mm 뿐인데 각관은 60 mm 다. 두 본이 다
    그 구간에 물리려면 중심이 60 mm 안에 들어야 하고, 그러면 서로 겹친다.
    **행을 어떻게 옮겨도 한쪽당 한 본이다.** 그러니 결정은 「행을 고친다」가
    아니라 「받는 본이 둘이라는 것을 받아들이고 그 힘으로 설계한다」이며,
    남는 두 본의 일이 무엇인지를 따로 정해야 한다.
    """
    flo, fhi = frame_bearing_span_mm(width_mm)
    return (fhi - flo) < beam_width_mm()


def landing_ledge_mm() -> float:
    """실제로 잡는 본이 내주는 **선반 폭** (mm) — 이만큼 어긋나면 놓친다."""
    rows = bearing_rows_mm()
    if not rows:
        return 0.0
    return min(bearing_overlap_mm(r) for r in rows)


# ── 2. 낙하 — 평평하게, 그리고 기울어서 ─────────────────────────────────
def beam_i_mm4() -> float:
    _length, width, depth = catch._beam().size
    t = catch._beam().t
    return (width * depth ** 3 - (width - 2 * t) * (depth - 2 * t) ** 3) / 12.0


def beam_hz() -> float:
    """포획빔 한 본의 1차 고유진동수 (Hz) — 외팔보 닫힌 해."""
    length, _w, _d = catch._beam().size
    return rigid.cantilever_hz(afr.STEEL_E_MPA, beam_i_mm4(),
                               catch.beam_mass_kg(), length)


def beam_k_n_per_m() -> float:
    """빔 **한 본**의 등가 강성 (N/m) — `dynamics` 의 합 강성을 본수로 나눈다."""
    return dynamics.catch_beam_stiffness_n_per_mm() * 1_000.0 / catch._beam().qty


def impact_speed_ms() -> float:
    return math.sqrt(2 * dynamics.double_sheet_energy_j() / drives.PANEL_KG)


def panel_inertia_kgm2() -> float:
    """패널을 폭 방향으로 도는 막대로 본 관성 (kg·m²).

    프레임 높이 75 는 넣어 봐야 (75/1400)² 이라 0.3 % 다 — 막대로 둔다.
    """
    return drives.PANEL_KG * (kinematics.PANEL_MM[1] / 1_000.0) ** 2 / 12.0


def drop(rows: tuple[float, ...] | None = None, tilt_deg: float = 0.0,
         hybrid: bool = True, dt: float = 5e-5, span: bool = True,
         mu: float = 0.0, until: float = 0.15) -> dict[str, float]:
    """겹장 낙하를 강체 + 유연 지지로 감는다.

    `rows` 를 안 주면 **실제로 닿는 본만** 쓴다. `hybrid` 가 거짓이면 지지가
    무질량 스프링이 되어 `dynamics.catch_impact` 와 같은 가정이 된다.
    """
    if rows is None:
        rows = bearing_rows_mm()
    w = rigid.World()
    v0 = impact_speed_ms()
    tilt = math.radians(tilt_deg)
    # **기울여 놓으면 시작 자세부터 정해야 한다.** 무게중심을 0 에 두면 낮은
    # 쪽 점이 이미 표면 아래에 있다 — 떨어지기도 전에 파고든 상태로 시작한다.
    # 가장 낮은 점이 표면에 **닿기만 한** 자세에서 시작한다 (평평하면 0 이라
    # 지금까지의 답이 그대로다).
    drop_y = -min(math.sin(tilt) * (r / 1_000.0) for r in rows) if rows else 0.0
    b = w.body(drives.PANEL_KG, panel_inertia_kgm2(), y=drop_y, vy=-v0, th=tilt)
    k = beam_k_n_per_m()
    zeta = dynamics.CONTACT_DAMPING
    sups, cons = [], []
    for row in rows:
        # **접촉점은 행 중심이 아니라 물리는 구간의 중심이다.** 행 ∓720 의
        # 각관은 690…750 을 덮지만 패널은 700 에서 끝나므로 실제로 힘이
        # 오가는 곳은 690…700 이다. 행 중심에 점을 두면 패널 밖에 두는 셈이라
        # 접촉이 아예 안 붙는다 — 처음에 그렇게 짜서 첨두가 0 으로 나왔다.
        centre = math.copysign(
            (sum(_bearing_edges(abs(row))) / 2.0) / 1_000.0, row) \
            if span else row / 1_000.0
        z = centre
        half = bearing_overlap_mm(row) / 2_000.0
        limit = (centre - half, centre + half) if span else None
        if hybrid:
            s = rigid.flexible_support(0.0, k, beam_hz(), zeta, span=limit)
            damp = 2 * zeta * math.sqrt(k * rigid.PENALTY_RATIO
                                        * drives.PANEL_KG / len(rows))
        else:
            s = rigid.Support(y0=0.0, k=k, span=limit)
            damp = 2 * zeta * math.sqrt(k * len(rows) * drives.PANEL_KG) / len(rows)
        w.supports.append(s)
        sups.append(s)
        cons.append(w.contact(b, z, 0.0, s, mu=mu, damping=damp))
    peak_total, lowest, t = 0.0, 0.0, 0.0
    peak_each = [0.0] * len(sups)
    beam_max = 0.0
    rebound, shift = 0.0, 0.0
    seen_contact = False
    while t < until:
        w.step(dt)
        for i, sp in enumerate(sups):
            peak_each[i] = max(peak_each[i], sp.spring_n())
        peak_total = max(peak_total, sum(sp.spring_n() for sp in sups))
        beam_max = max(beam_max, max(sp.q for sp in sups))
        lowest = min(lowest, b.y)
        if any(c.engaged for c in cons):
            seen_contact = True
        elif seen_contact:
            rebound = max(rebound, b.vy)          # 떨어져 나간 뒤의 상승 속도
        shift = max(shift, abs(b.x))
        t += dt
    return {
        "beams": len(sups),
        "peakTotalN": peak_total,
        "peakBeamN": max(peak_each) if peak_each else 0.0,
        "perBeamN": peak_total / len(sups) if sups else 0.0,
        "deflectionMm": (drop_y - lowest) * 1_000.0,
        #: 빔 선단이 실제로 내려간 깊이 (mm). **패널의 하강과 다르다** —
        #: 모달 질량이 있으면 패널이 튕겨 나간 뒤에도 빔은 제 관성으로
        #: 더 내려간다. 빔 응력을 정하는 것은 이쪽이다.
        "beamDeflectionMm": beam_max * 1_000.0,
        "reboundMs": rebound,
        "reboundMm": rebound ** 2 / (2 * rigid.G) * 1_000.0,
        "tiltDeg": math.degrees(b.th),
        "shiftMm": shift * 1_000.0,
    }


def _bearing_edges(row_mm: float) -> tuple[float, float]:
    lo, hi = beam_span_mm(abs(row_mm))
    flo, fhi = frame_bearing_span_mm()
    return (max(lo, flo), min(hi, fhi))


def as_drawn() -> dict[str, float]:
    """도면이 그린 대로 — 네 본이 다 받는다고 보면."""
    return drop(rows=tuple(float(r) for r in kinematics.CATCH_BEAM_ROWS_MM),
                hybrid=False, span=False)


def as_built() -> dict[str, float]:
    """실제로 닿는 본만 — 유연 지지(하이브리드)로."""
    return drop()


def hybrid_relief() -> dict[str, float]:
    """빔의 제 관성이 첨두를 얼마나 깎는가 — 하이브리드가 바꾸는 것.

    무질량 스프링은 빔이 순간에 제 강성을 다 낸다고 본다. 실제 빔은 모달
    질량이 있어 처음 얼마간을 같이 움직인다 — 그만큼 첨두가 낮다.
    """
    stiff = drop(hybrid=False)
    soft = drop(hybrid=True)
    return {"masslessN": stiff["peakBeamN"], "modalN": soft["peakBeamN"],
            "relief": 1.0 - soft["peakBeamN"] / stiff["peakBeamN"],
            "modalMassKg": rigid.modal_mass_from_hz(beam_k_n_per_m(), beam_hz()),
            "hz": beam_hz()}


def tilt_sweep(limit_deg: float = 2.0, step: float = 0.25
               ) -> list[dict[str, float]]:
    """기울어 도착하면 빔당 힘이 어떻게 가는가."""
    out, a = [], 0.0
    while a <= limit_deg + 1e-9:
        d = drop(tilt_deg=a)
        d["arrivalDeg"] = a
        out.append(d)
        a += step
    return out


def worst_tilt() -> dict[str, float]:
    return max(tilt_sweep(), key=lambda d: d["peakBeamN"])


def tilt_is_not_what_binds(limit: float = 1.25) -> bool:
    """도착 자세가 빔당 힘을 좌우하는가 — **답은 아니다.**

    처음에는 이쪽이 큰 항일 줄 알았다. 기울어 닿으면 한 본이 다 받으니까.
    감아 보니 3° 까지 기울여도 +17 % 다 — 한 본이 먼저 닿는 대신 그 순간
    참여하는 유효질량이 작아져 서로 상쇄한다. **본수가 정하고 자세는 안
    정한다.** 도착 자세를 재야 한다는 이야기를 이 값으로 접는다.
    """
    flat = drop()["peakBeamN"]
    return worst_tilt()["peakBeamN"] / flat <= limit


# ── 3. 잡은 뒤 — 선반 위에 남는가 ───────────────────────────────────────
def matrix() -> dict[str, dict[str, float]]:
    """네 갈래를 한 표로 — 본수(4/2) × 지지(무질량/모달).

    **한 번에 둘을 바꾸면 무엇이 답을 움직였는지 모른다.** 도면 가정(4본
    무질량)에서 실제(2본 모달)로 가는 사이에 바뀐 것이 둘이라 따로 본다.
    """
    four = tuple(float(r) for r in kinematics.CATCH_BEAM_ROWS_MM)
    two = bearing_rows_mm()
    return {
        "4본 무질량": drop(rows=four, hybrid=False, span=False),
        "4본 모달": drop(rows=four, hybrid=True, span=False),
        "2본 무질량": drop(rows=two, hybrid=False),
        "2본 모달": drop(rows=two, hybrid=True),
    }


def rebound_ms() -> float:
    """되튀어 나가는 속도 (m/s) — **감아서 얻는다.**

    무질량 스프링으로 감으면 1.99 m/s 가 나오고, 그것은 선형 스프링–댐퍼의
    닫힌 해 exp(−ζπ/√(1−ζ²)) · v₀ = 1.96 과 사실상 같다. 모달 질량을 붙이면
    1.25 로 떨어진다 — **빔이 운동량을 나눠 가지고 제 진동으로 들고 있기
    때문이다.** 하이브리드가 첨두만 깎는 것이 아니라 되튐도 같이 깎는다.
    """
    return as_built()["reboundMs"]


def bounce_mm() -> float:
    """되튀어 올라가는 높이 (mm)."""
    return rebound_ms() ** 2 / (2 * rigid.G) * 1_000.0


def airborne_s() -> float:
    """되튄 뒤 다시 내려앉기까지 떠 있는 시간 (s)."""
    return 2 * rebound_ms() / rigid.G


def drift_allow_ms() -> float:
    """떠 있는 동안 견디는 가로 속도 (m/s) — 이보다 빠르면 선반을 벗어난다.

    떠 있는 동안은 마찰이 없다 — 안 닿아 있으니 정말로 없다. 그래서
    보수적 가정이 아니라 그냥 맞는 계산이다.
    """
    t = airborne_s()
    return landing_ledge_mm() / 1_000.0 / t if t else math.inf


def the_ledge_is_the_problem() -> bool:
    """잡는 것을 막는 것이 힘이 아니라 **선반 폭**인가."""
    return landing_ledge_mm() < beam_width_mm() / 2.0


def damping_cuts_both_ways() -> dict[str, float]:
    """감쇠를 작게 잡은 것이 힘에는 보수적이고 **잡는 데는 반대**임을 보인다.

    `dynamics.CONTACT_DAMPING` 주석은 0.10 을 「보수적으로 작게」 잡았다고
    적는다 — 감쇠가 작으면 반력이 커서 빔이 안전해 보이지 않기 때문이다.
    맞는 말인데, 같은 선택이 **되튐을 키운다.** 힘에 보수적인 값이 유지에는
    비보수적이다. 한 값이 두 물음에서 반대 방향으로 작동한다.
    """
    keep = dynamics.CONTACT_DAMPING
    out = {}
    try:
        for z in (0.05, 0.10, 0.30):
            dynamics.CONTACT_DAMPING = z
            d = drop()
            out[f"zeta{z:g}"] = d["peakBeamN"]
            out[f"rebound{z:g}"] = d["reboundMs"]
    finally:
        dynamics.CONTACT_DAMPING = keep
    return out


# ── 4. 반전 — 미끄러진 뒤 몇 도를 잃는가 ────────────────────────────────
def flip_stick_slip(takt_scale: float = 1.0, dt: float = 2e-4,
                    eccentric_mm: float = 0.0) -> dict[str, float]:
    """마찰 롤러 구동을 쿨롱 접촉으로 감는다 — 링이 명령을 따라가는가.

    롤러는 서보라 **명령 각도를 그대로 따른다**고 본다 (위치원). 링은 관성만
    있고, 둘 사이는 압착력 `FLIP_PRELOAD_N` 과 마찰계수가 정하는 접선력이다.
    붙어 있으면 접선 스프링이 늘고, μN 을 넘으면 미끄러지며 다시 감긴다 —
    `rigid.Contact` 가 쓰는 것과 같은 정규화 쿨롱이다.

    `eccentric_mm` 은 패널 무게중심이 반전축에서 벗어난 거리다. `dynamics` 는
    「축이 무게중심을 지나므로 중력은 상쇄된다」고 적었는데, **그것은 값이
    아니라 가정이다.** 얼마까지 견디는지를 여기서 낸다.
    """
    seg = kinematics.PATH[3]
    total = (seg[1] - seg[0]) / takt_scale
    j = drives.flip_inertia_kgm2()
    r = (kinematics.RING_R_MM + kinematics.RING_TUBE_MM) / 1_000.0
    limit = drives.FLIP_PRELOAD_N * drives.FRICTION_MU
    kt = limit / (MICROSLIP_MM / 1_000.0)          # 미끄러지기 직전까지의 접선 강성
    ct = 2 * STICK_DAMPING * math.sqrt(kt * j / r ** 2)
    ecc = eccentric_mm / 1_000.0
    theta = omega = 0.0                            # 링
    cmd = cmd_v = 0.0                              # 롤러가 명령하는 링 각도
    anchor = 0.0                                   # 접선 스프링 기준 (링 원주 위, m)
    slip = peak = 0.0
    t = 0.0
    steps = int(round(total / dt))
    for _i in range(steps):
        alpha = dynamics.trapezoid(t, total, math.pi)
        cmd_v += alpha * dt
        cmd += cmd_v * dt
        stretch = (cmd - theta) * r - anchor
        f = kt * stretch + ct * (cmd_v - omega) * r
        if abs(f) > limit:
            f = math.copysign(limit, f)
            anchor = (cmd - theta) * r - f / kt
            slip += abs(stretch - f / kt)
        peak = max(peak, abs(f * r))
        grav = -drives.PANEL_KG * rigid.G * ecc * math.cos(theta)
        omega += (f * r + grav) / j * dt
        theta += omega * dt
        t += dt
    return {"taktScale": takt_scale,
            "commandDeg": math.degrees(cmd),
            "ringDeg": math.degrees(theta),
            "lostDeg": math.degrees(cmd - theta),
            "slipMm": slip * 1_000.0,
            "peakNm": peak,
            "capacityNm": limit * r,
            "eccentricMm": eccentric_mm}


def flip_holds(takt_scale: float = 1.0, tol_deg: float = 0.1) -> bool:
    return abs(flip_stick_slip(takt_scale)["lostDeg"]) <= tol_deg


def demand_matches_the_static_model(tol: float = 0.02) -> bool:
    """정격 택트에서 요구 토크가 `dynamics.flip_slip()` 과 같은가.

    **이 시험이 정규화가 제 동역학을 안 내고 있음을 지킨다.** 접선 스프링이
    울리기 시작하면 여기가 먼저 벌어진다.
    """
    got = flip_stick_slip(1.0)["peakNm"]
    want = dynamics.flip_slip()["demandNm"]
    return abs(got - want) / want <= tol


def slip_is_not_a_numerical_artifact() -> bool:
    """미소 미끄럼 폭을 바꿔도 위상 손실이 그대로인가."""
    global MICROSLIP_MM
    keep, out = MICROSLIP_MM, []
    try:
        for w in (0.02, 0.05, 0.15):
            MICROSLIP_MM = w
            out.append(flip_stick_slip(1.8)["lostDeg"])
    finally:
        MICROSLIP_MM = keep
    lo, hi = min(out), max(out)
    return (hi - lo) / hi < 0.05 if hi else True


def phase_loss_table() -> list[dict[str, float]]:
    """택트를 올리면 몇 도를 잃는가 — 정적 모형이 못 내던 값."""
    return [flip_stick_slip(x) for x in (1.0, 1.2, 1.4, 1.6, 1.8, 2.0)]


def slip_onset_scale(lo: float = 1.0, hi: float = 2.0,
                     tol: float = 0.01) -> float:
    """위상을 잃기 시작하는 택트 배수 — 이분법."""
    if not flip_holds(lo):
        return lo
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if flip_holds(mid):
            lo = mid
        else:
            hi = mid
    return hi


def eccentricity_allow_mm(hi: float = 400.0, tol: float = 1.0) -> float:
    """무게중심이 축에서 얼마나 벗어나도 위상을 안 잃는가 (mm) — 이분법."""
    lo = 0.0
    if abs(flip_stick_slip(eccentric_mm=hi)["lostDeg"]) <= 0.1:
        return hi
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if abs(flip_stick_slip(eccentric_mm=mid)["lostDeg"]) <= 0.1:
            lo = mid
        else:
            hi = mid
    return lo


# ── 5. EOAT — 넘어가는 것이 한계인가 (null 도 값이다) ───────────────────
def eoat_tip_ms2(arm_mm: float | None = None) -> float:
    """패널이 컵에서 **넘어가기** 시작하는 가로 가속도 (m/s²).

    가로 관성력은 무게중심에 걸리고 컵 면은 그보다 위(또는 아래)에 있으므로
    모멘트가 남는다. 그 모멘트를 컵 배열이 짝힘으로 받는다 — 앞줄 컵의
    파지력이 0 이 되는 순간이 한계다.
    """
    if arm_mm is None:
        arm_mm = kinematics.PANEL_MM[0] / 2.0        # 컵이 장변 끝까지 퍼져 있다고 본다
    d, n = dynamics.eoat_cups()
    hold = dynamics.cup_force_n(d, n) / dynamics.VACUUM_SAFETY
    lever = kinematics.PANEL_FRAME_H_MM / 2.0 / 1_000.0
    return hold * (arm_mm / 1_000.0) / (drives.PANEL_KG * lever)


def tipping_is_not_the_limit() -> bool:
    """전도가 미끄러짐보다 먼저 오지 않는다 — 확인해서 아니라는 뜻이다."""
    return eoat_tip_ms2() > dynamics.eoat_limit_ms2()["limitMs2"]


# ── 정리 ────────────────────────────────────────────────────────────────
def summary() -> dict[str, object]:
    grid = matrix()
    drawn = grid["4본 무질량"]
    built = grid["2본 모달"]
    worst = worst_tilt()
    return {
        "beamWidthMm": beam_width_mm(),
        "frameBearingMm": FRAME_BEARING_MM,
        "rowsMm": list(kinematics.CATCH_BEAM_ROWS_MM),
        "bearingRowsMm": list(bearing_rows_mm()),
        "bearingBeams": bearing_beams(),
        "ledgeMm": landing_ledge_mm(),
        "drawnPerBeamN": drawn["perBeamN"],
        "twoMasslessN": grid["2본 무질량"]["peakBeamN"],
        "fourModalN": grid["4본 모달"]["peakBeamN"],
        "builtPerBeamN": built["peakBeamN"],
        "builtDeflectionMm": built["deflectionMm"],
        "builtBeamDeflectionMm": built["beamDeflectionMm"],
        "loadFactor": built["peakBeamN"] / drawn["perBeamN"],
        "countFactor": grid["2본 무질량"]["peakBeamN"] / drawn["perBeamN"],
        "beamHz": beam_hz(),
        "modalMassKg": rigid.modal_mass_from_hz(beam_k_n_per_m(), beam_hz()),
        "hybridRelief": 1.0 - grid["4본 모달"]["peakBeamN"] / drawn["perBeamN"],
        "worstTiltDeg": worst["arrivalDeg"],
        "worstTiltN": worst["peakBeamN"],
        "reboundMs": rebound_ms(),
        "bounceMm": bounce_mm(),
        "airborneS": airborne_s(),
        "driftAllowMs": drift_allow_ms(),
        "slipOnsetScale": slip_onset_scale(),
        "lostDegAt2x": flip_stick_slip(2.0)["lostDeg"],
        "eccentricAllowMm": eccentricity_allow_mm(),
        "eoatTipMs2": eoat_tip_ms2(),
        "eoatSlipMs2": dynamics.eoat_limit_ms2()["limitMs2"],
    }


def checks() -> list[tuple[str, bool, str]]:
    s = summary()
    n = len(kinematics.CATCH_BEAM_ROWS_MM)
    return [
        ("포획빔 네 본이 모두 프레임 밑에 물린다",
         s["bearingBeams"] == n,
         f"{s['bearingBeams']}/{n} 본만 물린다 — 안쪽 두 본 밑은 "
         f"유리까지 {glass_gap_mm():.0f} mm 허공이다"),
        ("잡는 선반이 각관 폭의 절반은 된다",
         not the_ledge_is_the_problem(),
         f"선반 {s['ledgeMm']:.0f} mm (각관 {s['beamWidthMm']:.0f}) — "
         f"이만큼 어긋나면 놓친다"),
        ("빔당 힘이 도면이 가정한 값을 안 넘는다",
         s["loadFactor"] <= 1.0,
         f"{s['builtPerBeamN']:.0f} N vs 가정 {s['drawnPerBeamN']:.0f} N "
         f"({s['loadFactor']:.2f} 배). 본수만 {s['countFactor']:.2f} 배, "
         f"빔 관성이 {s['hybridRelief']:.0%} 되돌린다"),
        ("하부 지지폭을 몰라도 결론이 유지된다",
         bearing_conclusion_is_robust(), "안쪽 두 본이 폭에 따라 닿기도 한다"),
        ("도착 자세는 빔당 힘을 좌우하지 않는다",
         tilt_is_not_what_binds(),
         f"기울기 {s['worstTiltDeg']:.2f}° 에서 {s['worstTiltN']:.0f} N"),
        ("반전이 정격 택트에서 위상을 안 잃는다",
         flip_holds(), f"{flip_stick_slip()['lostDeg']:.3f}° 손실"),
        ("반전 요구 토크가 정적 모형과 같다",
         demand_matches_the_static_model(),
         "정규화가 제 동역학을 내고 있다 — STICK_DAMPING 을 본다"),
        ("EOAT 는 넘어가기 전에 미끄러진다",
         tipping_is_not_the_limit(),
         f"전도 {s['eoatTipMs2']:.0f} vs 미끄럼 {s['eoatSlipMs2']:.1f} m/s²"),
    ]


def annotations() -> tuple[str, ...]:
    """도면집 미결 항목에 그대로 실을 문장 — **별표(**) 를 쓰지 않는다.**"""
    s = summary()
    return (
        f"포획빔 네 본 중 실제로 패널을 받는 것은 {s['bearingBeams']} 본이다. "
        f"행 ∓580 은 프레임 안쪽이라 그 밑이 유리까지 {glass_gap_mm():.0f} mm "
        f"허공이고, 행 ∓720 은 패널 바깥끝(∓700)을 "
        f"{s['ledgeMm']:.0f} mm 만 문다.",
        f"그래서 빔당 반력이 도면 가정 {s['drawnPerBeamN']:.0f} N 이 아니라 "
        f"{s['builtPerBeamN']:.0f} N ({s['loadFactor']:.2f} 배) 이고 빔 처짐은 "
        f"{s['builtBeamDeflectionMm']:.1f} mm 다. 본수가 {s['countFactor']:.2f} 배로 "
        f"올리고 빔 자체 관성(모달 {s['modalMassKg']:.1f} kg, "
        f"{s['beamHz']:.0f} Hz)이 {s['hybridRelief']:.0%} 를 되돌린다.",
        f"이 구간을 정하는 것은 힘이 아니라 자리다. 얹히는 선반이 "
        f"{s['ledgeMm']:.0f} mm 라 그만큼만 어긋나도 놓치고, 되튐 "
        f"{s['reboundMs']:.2f} m/s 로 {s['bounceMm']:.0f} mm 떠 있는 "
        f"{s['airborneS']:.2f} s 동안 가로 "
        f"{s['driftAllowMs'] * 1_000:.0f} mm/s 를 넘으면 벗어난다.",
        f"도착 자세는 갈림길이 아니다 — {s['worstTiltDeg']:.2f}° 까지 기울여도 "
        f"{s['worstTiltN']:.0f} N 으로 {s['worstTiltN'] / s['builtPerBeamN']:.2f} "
        f"배에 그친다. 재야 할 것은 자세가 아니라 행 위치다.",
        f"반전은 정격에서 위상을 안 잃는다. 택트 {s['slipOnsetScale']:.2f} 배부터 "
        f"미끄러지고 2 배에서 {s['lostDegAt2x']:.1f}° 를 잃는다. 무게중심이 "
        f"반전축에서 {s['eccentricAllowMm']:.0f} mm 벗어나도 견딘다.",
        f"EOAT 는 넘어가기 전에 미끄러진다 — 전도 {s['eoatTipMs2']:.0f} vs "
        f"미끄럼 {s['eoatSlipMs2']:.1f} m/s². 확인해서 아닌 것이라 "
        f"미끄러짐 한계 하나만 보면 된다.",
    )


def main() -> None:                                          # pragma: no cover
    s = summary()
    print("── 접촉 지도 ──")
    for c in contact_map():
        mark = "받는다" if c["bears"] else ("유리 밑 허공" if c["underGlass"]
                                            else "패널 밖")
        print(f"  행 {c['rowMm']:>7.0f}  각관 {c['spanLoMm']:.0f}…"
              f"{c['spanHiMm']:.0f}  물림 {c['overlapMm']:>5.1f} mm  {mark}")
    print(f"\n  프레임 지지 구간 {frame_bearing_span_mm()[0]:.0f}…"
          f"{frame_bearing_span_mm()[1]:.0f} mm (가정 폭 {FRAME_BEARING_MM:.0f})")
    print(f"  실제로 받는 본 {s['bearingBeams']} / "
          f"{len(kinematics.CATCH_BEAM_ROWS_MM)},  선반 {s['ledgeMm']:.0f} mm")

    print("\n── 낙하 — 본수 × 지지 ──")
    for name, d in matrix().items():
        print(f"  {name:<10} 빔당 {d['peakBeamN']:>7.0f} N   "
              f"빔 처짐 {d['beamDeflectionMm']:>5.1f} mm   "
              f"되튐 {d['reboundMs']:.2f} m/s")
    print(f"  본수만 바꾸면 {s['countFactor']:.2f} 배, 모달만 붙이면 "
          f"{1 - s['hybridRelief']:.2f} 배, 둘 다면 {s['loadFactor']:.2f} 배")
    print(f"  빔 1차 {s['beamHz']:.1f} Hz, 모달질량 {s['modalMassKg']:.2f} kg")
    print(f"  최악 도착 기울기 {s['worstTiltDeg']:.2f}° → {s['worstTiltN']:.0f} N")

    print("\n── 잡은 뒤 ──")
    print(f"  되튐 {s['reboundMs']:.2f} m/s → {s['bounceMm']:.0f} mm 뜨고 "
          f"{s['airborneS']:.2f} s 떠 있다")
    print(f"  그동안 가로 {s['driftAllowMs'] * 1_000:.0f} mm/s 를 넘으면 "
          f"선반 {s['ledgeMm']:.0f} mm 를 벗어난다")
    cuts = damping_cuts_both_ways()
    for z in (0.05, 0.10, 0.30):
        print(f"    ζ {z:<5} 첨두 {cuts[f'zeta{z:g}']:>7.0f} N   "
              f"되튐 {cuts[f'rebound{z:g}']:.2f} m/s")

    print("\n── 반전 ──")
    for row in phase_loss_table():
        print(f"  택트 ×{row['taktScale']:.1f}  요구 {row['peakNm']:>6.1f} / "
              f"전달 {row['capacityNm']:.1f} N·m   손실 {row['lostDeg']:>7.3f}°")
    print(f"  손실 시작 배수 {s['slipOnsetScale']:.2f}, "
          f"편심 허용 {s['eccentricAllowMm']:.0f} mm")

    print("\n── EOAT ──")
    print(f"  전도 {s['eoatTipMs2']:.0f} vs 미끄럼 {s['eoatSlipMs2']:.1f} m/s² "
          f"— 넘어가는 것은 한계가 아니다")

    print("\n── 검사 ──")
    for name, ok, why in checks():
        print(f"  {'OK ' if ok else '주의'}  {name}" + ("" if ok else f" — {why}"))


if __name__ == "__main__":                                   # pragma: no cover
    main()
