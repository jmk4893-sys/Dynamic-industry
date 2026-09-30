# -*- coding: utf-8 -*-
"""CD-101 포획빔의 신축 — 몇 단이어야 하고, 그 단수가 견디는가 (OI-07).

미결 항목은 이렇게 적혀 있다: "3D 는 빔이 제 길이 방향으로 벽에서 신축하는
안으로 그렸다 … 다만 2,900 짜리 빔을 250 두께 벽에 넣으려면 겹단 신축이
필요하고, 단수·행정·구동(공압이냐 벨트냐)이 정해져야 제작 도면이 나온다."

**단수는 고르는 값이 아니다.** 수납 깊이가 하한을 정하고, 그 하한이 나오면
나머지가 줄줄이 따라 정해진다.

* **수납 깊이가 단수를 정한다.** 접힌 빔은 올라오는 패널의 발자국을 비켜야
  한다. 그 여유는 패널 자리와 중앙벽에서 나오고, 답은 7 단이다.
* **그 단수가 뿌리 단면을 정한다.** 한 단을 겹칠 때마다 단면 한 변이
  2(t + 틈) 씩 줄어든다. 지금 100 × 60 으로는 2 단이 상한이라, 7 단을 겹치려면
  뿌리를 102 × 102 으로 키워야 한다.
* **강성은 막는 것이 아니다.** 선단 강성이 3분의 1로 줄지만 163 J 을 받을 때
  처짐이 26.7 → 46.1 mm 이고, 받아도 되는 여유는 350 mm 다. 여기서 걸릴 것을
  예상했는데 안 걸린다 — 그 사실도 값으로 남긴다.
* **구동이 걸린다.** 신축이면 바깥 단이 실린더보다 빨라 도착 에너지가 단수의
  제곱으로 는다. 공압으로는 못 멈춘다. OI-05 가 "공압은 감속을 프로파일로 못
  만든다" 를 값으로 남겼고, 그 문장이 여기서 **벨트·서보**를 고른다.

**접합부는 강접으로 본다.** 실제 신축 붐은 슈 사이에 유격이 있어 더 처지므로
위 처짐은 하한이다. 그 유격이 하중 없이 만드는 선단 처짐은 따로 센다 — 7 단이면
7.6 mm 로, 빔이 프레임 밑으로 들어갈 때 두는 틈 20 mm 의 38 % 를 먹는다.

**여기서 처음 적는 값은 겹침 길이·끼움 틈·최소 선단 단면뿐이다.** 도달과
단면은 제작 도면집에서, 패널 자리는 `layout`·`kinematics` 에서, 낙하 에너지와
강성은 `dynamics` 에서 읽는다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.telescope
"""

from __future__ import annotations

import functools
import math

from . import afr, catch, dynamics, kinematics, layout

# ── 신축 기구의 값 (여기서 처음 적는 값) ─────────────────────────────────

#: 단과 단이 겹치는 길이 (mm). 짧으면 슈 반력이 커지고 유격이 는다 — 통상
#: 단 길이의 1/5 이상을 겹치는데, 여기서는 고정값으로 두고 감도를 표로 낸다.
OVERLAP_MM = 200.0

#: 단끼리 끼울 때 한 쪽에 두는 틈 (mm) — 슬라이드 슈가 들어갈 자리다.
NEST_CLEARANCE_MM = 2.0

#: 선단 단의 최소 단면 (깊이, 폭 mm). 이보다 작으면 슈를 못 앉히고 볼트도
#: 못 박는다. 겹칠 수 있는 단수의 상한이 여기서 나온다.
MIN_TIP_MM = (40.0, 40.0)

#: 접힌 빔과 올라오는 패널 사이에 두는 여유 (mm).
STOW_CLEARANCE_MM = 50.0

#: 단 이음 하나의 각 유격 (deg). **가정이다** — 슈 틈과 마모로 생기는 값이라
#: 벤더 자료나 시험에서만 나온다. 신축 붐에서 통상 잡는 크기이고, 단수가 늘면
#: 이 각이 남은 길이에 곱해져 **하중 없이도** 선단이 처진다.
JOINT_SLOP_DEG = 0.05

SHEET = dynamics.SHEET_CATCH


def _beam():
    return dynamics._part(SHEET, "CD-BM-01")


# ── 도달과 수납 ─────────────────────────────────────────────────────────
def reach_mm() -> float:
    """빔이 벽면에서 내밀어야 하는 길이 (mm) — 빔 길이 그대로다."""
    return float(_beam().size[0])


def shortfall_mm() -> float:
    """다 내밀어도 패널 끝단에 못 미치는 길이 (mm). `kinematics` 가 갖고 있다."""
    return -kinematics.catch_beam_covers_the_panel_mm()


def panel_near_edge_mm() -> float:
    """패널 근단의 라인 가로 자리 (mm) — 접힌 빔은 여기까지만 들어올 수 있다."""
    return layout.BFC_PICKUP_Z_MM - kinematics.PANEL_MM[0] / 2


def stow_depth_mm() -> float:
    """접힌 빔이 쓸 수 있는 깊이 (mm).

    중앙벽 반두께만큼은 벽 포켓에 넣을 수 있고, 그 앞으로는 패널 근단까지가
    비어 있다. 더 밀어 넣으면 **옆 베이의 카세트**가 있고, 덜 빼면 올라오는
    패널을 친다.
    """
    return (kinematics.CENTRE_WALL_T_MM / 2 + panel_near_edge_mm()
            - STOW_CLEARANCE_MM)


def stages_for_depth(depth_mm: float | None = None,
                     overlap_mm: float | None = None) -> int:
    """그 깊이에 접어 넣으려면 몇 단이어야 하는가.

    N 단이면 한 단의 길이는 (도달 + (N−1)·겹침) / N 이다 — 겹치는 만큼 총
    길이가 늘기 때문이다. 그것이 깊이 안에 드는 가장 작은 N 을 찾는다.
    """
    d = stow_depth_mm() if depth_mm is None else depth_mm
    o = OVERLAP_MM if overlap_mm is None else overlap_mm
    for n in range(1, 21):
        if (reach_mm() + (n - 1) * o) / n <= d:
            return n
    return 21


def stage_length_mm(n: int, overlap_mm: float | None = None) -> float:
    o = OVERLAP_MM if overlap_mm is None else overlap_mm
    return (reach_mm() + (n - 1) * o) / n


# ── 단면이 몇 단까지 겹치는가 ────────────────────────────────────────────
def nest_step_mm() -> float:
    """한 단 겹칠 때마다 단면 한 변이 줄어드는 양 (mm) — 양쪽 벽과 틈이다."""
    return 2 * (float(_beam().t) + NEST_CLEARANCE_MM)


def stage_section_mm(k: int) -> tuple[float, float]:
    """뿌리에서 k 번째 단의 (깊이, 폭). k=0 이 뿌리(가장 큰 단)다."""
    _l, w, d = _beam().size
    step = nest_step_mm()
    return (d - k * step, w - k * step)


def max_stages_for_section() -> int:
    """지금 단면으로 겹칠 수 있는 단수의 **상한**."""
    n = 0
    while True:
        d, w = stage_section_mm(n)
        if d < MIN_TIP_MM[0] or w < MIN_TIP_MM[1]:
            return max(n, 1)
        n += 1


def root_section_for_stages(n: int) -> tuple[float, float]:
    """N 단을 겹치려면 뿌리 단면이 얼마여야 하는가 (깊이, 폭 mm)."""
    step = nest_step_mm()
    return (MIN_TIP_MM[0] + (n - 1) * step, MIN_TIP_MM[1] + (n - 1) * step)


def section_allows_the_depth() -> bool:
    """수납 깊이가 요구하는 단수를 지금 단면이 감당하는가 — **안 한다.**"""
    return stages_for_depth() <= max_stages_for_section()


# ── 신축 빔의 강성 ──────────────────────────────────────────────────────
def _i_mm4(depth: float, width: float, t: float) -> float:
    return (width * depth ** 3 - (width - 2 * t) * (depth - 2 * t) ** 3) / 12.0


def tip_stiffness_n_per_mm(n: int, root: tuple[float, float] | None = None
                           ) -> float:
    """N 단 신축 외팔보 한 본의 선단 강성 (N/mm).

    단이 계단처럼 바뀌는 외팔보의 선단 처짐은 닫힌 식으로 나온다 —
    δ = (P/E)·Σ∫(L−x)²/I dx. 접합부는 강접으로 보므로 **이 값은 상한**이다.
    """
    total = reach_mm()
    seg = total / n
    e = afr.STEEL_E_MPA
    t = float(_beam().t)
    base = root if root is not None else (float(_beam().size[2]),
                                          float(_beam().size[1]))
    step = nest_step_mm()
    flex = 0.0                                     # δ / P
    for k in range(n):
        x0, x1 = k * seg, (k + 1) * seg
        d, w = base[0] - k * step, base[1] - k * step
        i = _i_mm4(d, w, t)
        flex += (((total - x0) ** 3 - (total - x1) ** 3) / 3.0) / (e * i)
    return 1.0 / flex


def tip_droop_mm(n: int) -> float:
    """하중 없이 유격만으로 생기는 선단 처짐 (mm).

    이음 k 개가 각각 `JOINT_SLOP_DEG` 만큼 꺾이면 그 각이 **남은 길이**에
    곱해진다. 단수가 늘수록 이음도 늘고 팔도 길어져 빠르게 커진다 — 강성과
    달리 이것은 단면을 키워도 안 줄어든다.
    """
    seg = reach_mm() / n
    slop = math.radians(JOINT_SLOP_DEG)
    return sum(slop * (reach_mm() - k * seg) for k in range(1, n))


def droop_eats_the_clearance(n: int) -> bool:
    """유격 처짐이 빔–프레임 틈을 먹는가 — 먹으면 접근하다 프레임을 친다."""
    return tip_droop_mm(n) >= catch.BEAM_CLEARANCE_MM


def solid_tip_stiffness_n_per_mm() -> float:
    """통짜 빔 한 본의 선단 강성 (N/mm) — 견줄 기준."""
    return tip_stiffness_n_per_mm(1)


def catch_deflection_mm(n: int, root: tuple[float, float] | None = None) -> float:
    """N 단 빔 네 본이 163 J 을 받을 때의 처짐 (mm).

    `dynamics.catch_impact()` 를 그대로 쓰되 강성만 바꿔 넣는다 — 충돌 모형을
    두 번 적지 않는다. 등분포 보정(8/3)도 `dynamics` 것과 같게 건다.
    """
    k_tip = tip_stiffness_n_per_mm(n, root)
    k_total = k_tip * (8.0 / 3.0) * _beam().qty
    keep = dynamics.catch_beam_stiffness_n_per_mm
    try:
        dynamics.catch_beam_stiffness_n_per_mm = lambda: k_total
        return dynamics.catch_impact()["deflectionMm"]
    finally:
        dynamics.catch_beam_stiffness_n_per_mm = keep


def deflection_budget_mm() -> float:
    """받아도 되는 처짐 (mm) — 접힌 빔과 패널 사이의 여유가 그 한도다.

    빔이 이보다 더 처지면 겹장을 받으면서 **적층 최상단까지 내려간다** —
    그러면 받은 뜻이 없다. 포획 평면과 픽업면 사이가 그 여유다.
    """
    return catch.design_plane_mm()


# ── 구동 — 신축이면 바깥 단이 더 빨리 움직인다 ──────────────────────────
def stage_speed_ratio(n: int) -> float:
    """실린더 속도 대비 **선단** 속도의 비. 동시전개 리빙이면 단수와 같다."""
    return float(n)


@functools.lru_cache(maxsize=32)
def arrival_energy_j(n: int, speed_ms: float | None = None) -> float:
    """끝단에서 완충이 먹어야 하는 운동에너지 (J).

    단이 각각 다른 속도로 움직인다 — k 번째 단은 실린더의 k 배다. 질량을
    고르게 나눠 보면 에너지가 Σk² 로 는다. OI-05 가 통짜 빔 하나로 셌던 것이
    여기서 커진다.
    """
    v = catch.design_speed_ms() if speed_ms is None else speed_ms
    m_stage = catch.beam_mass_kg() / n
    carriage = catch.CARRIAGE_KG
    return 0.5 * (carriage * v ** 2
                  + sum(m_stage * (k * v) ** 2 for k in range(1, n + 1)))


@functools.lru_cache(maxsize=32)
def pneumatic_still_works(n: int) -> bool:
    """공압으로도 멈출 수 있는가 — 쇼크업소버 등급과 견준다."""
    return arrival_energy_j(n) <= catch.SHOCK_ABSORBER_J


def belt_removes_the_problem() -> bool:
    """벨트·서보면 감속을 프로파일로 만들 수 있어 도착 에너지 항이 없어진다.

    OI-05 가 "공압은 감속을 프로파일로 못 만든다" 를 값으로 남겼다. 그 문장이
    여기서 구동 방식을 고른다.
    """
    import inspect
    return "감속을 프로파일로 못 만든다" in inspect.getsource(catch)


# ── 판정 ────────────────────────────────────────────────────────────────
@functools.lru_cache(maxsize=8)
def options(max_n: int = 8) -> list[dict[str, object]]:
    """단수별로 무엇이 되고 무엇이 안 되는지."""
    rows = []
    fits_depth = stages_for_depth()
    cap = max_stages_for_section()
    budget = deflection_budget_mm()
    for n in range(1, max_n + 1):
        # 지금 단면으로 못 겹치는 단수는 **뿌리를 키워** 평가한다 — "안 된다" 로
        # 끝내면 키우면 되는지를 못 본다.
        grow = n > cap
        root = root_section_for_stages(n) if grow else None
        rows.append({
            "n": n,
            "stageMm": round(stage_length_mm(n), 0),
            "stowOk": stage_length_mm(n) <= stow_depth_mm(),
            "asIs": not grow,
            "rootMm": tuple(round(v, 0) for v in
                            (root or (float(_beam().size[2]),
                                      float(_beam().size[1])))),
            "stiffNmm": round(tip_stiffness_n_per_mm(n, root), 1),
            "deflMm": round(catch_deflection_mm(n, root), 1),
            "deflOk": catch_deflection_mm(n, root) <= budget,
            "arrivalJ": round(arrival_energy_j(n), 1),
            "airOk": pneumatic_still_works(n),
            "droopMm": round(tip_droop_mm(n), 1),
            "droopOk": not droop_eats_the_clearance(n),
        })
        rows[-1]["ok"] = bool(rows[-1]["stowOk"] and rows[-1]["deflOk"]
                              and rows[-1]["droopOk"])
    return rows


@functools.lru_cache(maxsize=8)
def smallest_workable_stages() -> int | None:
    """수납·처짐·유격을 다 지나는 **가장 적은** 단수 (뿌리를 키우는 것은 허용)."""
    ok = [r["n"] for r in options() if r["ok"]]
    return min(ok) if ok else None


def any_stage_count_works() -> bool:
    return smallest_workable_stages() is not None


def drive_must_be_servo() -> bool:
    """그 단수에서 공압이 못 멈추는가 — 그러면 구동은 벨트·서보다."""
    n = smallest_workable_stages()
    return n is not None and not pneumatic_still_works(n)


@functools.lru_cache(maxsize=1)
def summary() -> dict[str, object]:
    n_depth = stages_for_depth()
    cap = max_stages_for_section()
    return {
        "reachMm": reach_mm(),
        "shortfallMm": shortfall_mm(),
        "panelNearEdgeMm": panel_near_edge_mm(),
        "stowDepthMm": round(stow_depth_mm(), 0),
        "stagesForDepth": n_depth,
        "stageLengthMm": round(stage_length_mm(n_depth), 0),
        "nestStepMm": nest_step_mm(),
        "maxStagesForSection": cap,
        "rootForDepthMm": tuple(round(v, 0)
                                for v in root_section_for_stages(n_depth)),
        "sectionAllows": section_allows_the_depth(),
        "solidStiffNmm": round(solid_tip_stiffness_n_per_mm(), 1),
        "stiffAtDepthNmm": round(tip_stiffness_n_per_mm(n_depth), 2),
        "stiffGrownNmm": round(tip_stiffness_n_per_mm(
            n_depth, root_section_for_stages(n_depth)), 1),
        "solidDeflMm": round(catch_deflection_mm(1), 1),
        "deflAtDepthMm": round(catch_deflection_mm(n_depth), 1),
        "deflGrownMm": round(catch_deflection_mm(
            n_depth, root_section_for_stages(n_depth)), 1),
        "deflBudgetMm": deflection_budget_mm(),
        "arrivalSolidJ": round(arrival_energy_j(1), 1),
        "arrivalAtDepthJ": round(arrival_energy_j(n_depth), 1),
        "absorberJ": catch.SHOCK_ABSORBER_J,
        "workableStages": smallest_workable_stages(),
        "mustBeServo": drive_must_be_servo(),
        "droopAtDepthMm": round(tip_droop_mm(stages_for_depth()), 1),
        "droopShareOfClearance": round(tip_droop_mm(stages_for_depth())
                                       / catch.BEAM_CLEARANCE_MM, 2),
        "clearanceMm": catch.BEAM_CLEARANCE_MM,
        "anyWorks": any_stage_count_works(),
        "cylinderStrokeMm": catch.cylinder_stroke_mm(),
        "strokeIsHalfTheReach": abs(catch.cylinder_stroke_mm() * 2
                                    - reach_mm()) < 1.0,
    }


def checks() -> list[tuple[str, bool, str]]:
    s = summary()
    return [
        ("도달이 부품표에서 온다", s["reachMm"] == 2_900.0,
         f"빔 길이 {s['reachMm']:.0f} mm, 패널 끝단까지 "
         f"{s['shortfallMm']:.0f} mm 모자란다"),
        ("부품표의 행정이 도달의 절반이다", s["strokeIsHalfTheReach"],
         f"실린더 {s['cylinderStrokeMm']:.0f} × 2 = {s['reachMm']:.0f} — "
         "2 단 리빙을 전제로 고른 값이다"),
        ("수납 깊이가 단수의 하한을 정한다", s["stagesForDepth"] > 2,
         f"깊이 {s['stowDepthMm']:.0f} mm 에 {s['reachMm']:.0f} 을 접으려면 "
         f"{s['stagesForDepth']} 단, 한 단 {s['stageLengthMm']:.0f} mm"),
        ("지금 단면은 그 단수를 못 겹친다", not s["sectionAllows"],
         f"단면 100 × 60 은 {s['maxStagesForSection']} 단이 상한인데 "
         f"{s['stagesForDepth']} 단이 필요하다 — 뿌리를 "
         f"{s['rootForDepthMm'][0]:.0f} × {s['rootForDepthMm'][1]:.0f} 으로 "
         "키워야 한다"),
        ("단수를 늘려도 뿌리를 키우면 강성이 거의 돌아온다",
         s["stiffGrownNmm"] > s["stiffAtDepthNmm"] * 2,
         f"같은 단면이면 {s['solidStiffNmm']} → {s['stiffAtDepthNmm']} N/mm 인데 "
         f"뿌리를 키우면 {s['stiffGrownNmm']} N/mm 로 돌아온다"),
        ("낙하 처짐이 여유 안이다", s["deflGrownMm"] <= s["deflBudgetMm"],
         f"163 J 에 처짐 {s['solidDeflMm']} → {s['deflGrownMm']} mm, "
         f"여유 {s['deflBudgetMm']:.0f} mm — 신축을 막는 것은 강성이 아니다"),
        ("유격이 빔–프레임 틈의 절반 가까이를 먹는다",
         0.2 < s["droopShareOfClearance"] < 1.0,
         f"이음 {s['stagesForDepth'] - 1} 개의 유격만으로 선단이 "
         f"{s['droopAtDepthMm']} mm 처진다 — 틈 {s['clearanceMm']:.0f} mm 의 "
         f"{s['droopShareOfClearance'] * 100:.0f} %"),
        ("뿌리를 키우면 되는 단수가 있다", s["anyWorks"],
         f"{s['workableStages']} 단 · 뿌리 {s['rootForDepthMm'][0]:.0f} × "
         f"{s['rootForDepthMm'][1]:.0f}"),
        ("그 단수에서는 공압이 답이 아니다", s["mustBeServo"],
         f"도착 에너지 {s['arrivalAtDepthJ']} J vs 업소버 "
         f"{s['absorberJ']:.0f} J — 벨트·서보로 간다"),
        ("벨트·서보면 그 항이 없어진다", belt_removes_the_problem(),
         "OI-05 가 「공압은 감속을 프로파일로 못 만든다」를 값으로 남겼다"),
    ]


def annotations() -> tuple[str, ...]:
    s = summary()
    return (
        f"CD-101 포획빔은 벽면에서 {s['reachMm']:.0f} mm 를 내밀어야 하고 그래도 "
        f"패널 끝단까지 {s['shortfallMm']:.0f} mm 모자란다",
        f"접힌 빔이 쓸 수 있는 깊이는 {s['stowDepthMm']:.0f} mm 다 — 중앙벽 반두께 "
        f"125 에 패널 근단 {s['panelNearEdgeMm']:.0f} 까지, 여유 "
        f"{STOW_CLEARANCE_MM:.0f} 를 뺀 값이다",
        f"그 깊이에 접으려면 {s['stagesForDepth']} 단(한 단 "
        f"{s['stageLengthMm']:.0f} mm)이 필요한데, 단면 100 × 60 으로는 "
        f"{s['maxStagesForSection']} 단이 상한이다 — 한 단 겹칠 때마다 한 변이 "
        f"{s['nestStepMm']:.1f} mm 씩 줄기 때문이다",
        f"뿌리를 {s['rootForDepthMm'][0]:.0f} × {s['rootForDepthMm'][1]:.0f} 으로 "
        f"키우면 단수도 강성도 맞는다 — 같은 단면으로 7 단을 겹치면 선단 강성이 "
        f"{s['solidStiffNmm']} → {s['stiffAtDepthNmm']} N/mm 로 무너지지만 뿌리를 "
        f"키우면 {s['stiffGrownNmm']} N/mm 로 돌아오고, 163 J 처짐이 "
        f"{s['solidDeflMm']} → {s['deflGrownMm']} mm 로 여유 "
        f"{s['deflBudgetMm']:.0f} mm 안이다. 강성은 막는 것이 아니다",
        f"이음 유격은 하중과 무관하게 남는다 — 이음 {s['stagesForDepth'] - 1} 개가 "
        f"각 {JOINT_SLOP_DEG}° 만 꺾여도 선단이 {s['droopAtDepthMm']} mm 처져 "
        f"빔–프레임 틈 {s['clearanceMm']:.0f} mm 의 "
        f"{s['droopShareOfClearance'] * 100:.0f} % 를 먹는다. 단면을 키워도 "
        f"안 줄어드는 항이라 슈 사양이 곧 이 틈을 정한다",
        f"결론 — {s['workableStages']} 단, 뿌리 {s['rootForDepthMm'][0]:.0f} × "
        f"{s['rootForDepthMm'][1]:.0f}, 구동은 벨트·서보. 공압은 도착 에너지 "
        f"{s['arrivalAtDepthJ']} J 를 못 멈춘다(업소버 {s['absorberJ']:.0f} J). "
        f"서보는 감속을 프로파일로 만들 수 있어 그 항이 통째로 없어진다 — "
        f"OI-05 가 남긴 문장이 여기서 구동을 고른다",
        "접합부는 강접으로 봤다 — 실제 신축 붐은 슈 유격이 있어 더 처진다. "
        "위 처짐은 하한이라, 슈 사양이 오면 유격 항과 함께 다시 봐야 한다. "
        "단 사이 겹침 200 도 여기서 고른 값이다 (OI-07)",
    )


if __name__ == "__main__":                                   # pragma: no cover
    import json

    print(json.dumps(summary(), ensure_ascii=False, indent=1))
    print()
    for name, ok, why in checks():
        print(f"{'✓' if ok else '✗'} {name} — {why}")
    print()
    print(f"{'단':>3} {'한 단 mm':>9} {'수납':>5} {'단면':>6} "
          f"{'뿌리 단면':>14} {'강성 N/mm':>10} {'처짐 mm':>9} {'유격 mm':>8} "
          f"{'도착 J':>8} {'공압':>5} {'판정':>5}")
    for r in options():
        print(f"{r['n']:3} {r['stageMm']:9.0f} {'○' if r['stowOk'] else '×':>5} "
              f"{'그대로' if r['asIs'] else '확대':>6} "
              f"{str(r['rootMm']):>14} {r['stiffNmm']:10.1f} {r['deflMm']:9.1f} "
              f"{r['droopMm']:8.1f} {r['arrivalJ']:8.1f} "
              f"{'○' if r['airOk'] else '×':>5} {'○' if r['ok'] else '×':>5}")
    print()
    for line in annotations():
        print("·", line)
