# -*- coding: utf-8 -*-
"""무프레임 적층에서 한 장을 어떻게 떼어 내는가 — 셋을 같은 틀에서 잰다.

`dynamics.py` 가 답을 하나 냈다: **프레임 있는 적층은 유리면 사이가 8 mm 떠서
쉽고, 무프레임은 곧게 들 수 없다.** 자릿수로 막히므로 컵을 늘려 될 일이 아니다.
그러면 무엇을 해야 하는가 — 그 물음이 이 모듈이다.

`recipe` 는 무프레임을 **등록된 정상 구조**로 두고 있고 (`PROCESS_NO_AFR`),
달라지는 것을 「AFR 인발 생략」 하나로 적어 두었다. **투입부가 먼저 막히는데
그것이 안 적혀 있었다.**

세 가지를 **같은 1-D 레이놀즈 스퀴즈 필름**으로 잰다. 서로 다른 식으로 재면
비교가 성립하지 않는다 — `dynamics.stefan_force_n()` 은 원판 근사라 프레임
적층의 8 mm 를 재기에는 맞지만, 젖힘처럼 **틈이 자리마다 다른** 경우에는 못 쓴다.

    d/dx ( h³/12μ · dp/dx ) = ∂h/∂t          양 끝은 대기압

곧게 들면 h 가 어디서나 같고, 젖히면 h 가 쐐기이며, 밀면 h 가 안 변하고 전단만
남는다. 셋의 답이 **아홉 자릿수** 벌어진다.

**유리가 두 번째 제약이다.** 젖힘 길이를 짧게 잡으면 필름 저항은 줄지만 라미네이트
자체가 깨진다 — `afr` 의 유리 물성(t 3.2 · E 70 GPa · 허용 30 MPa)이 젖힘 길이의
**하한**을 정하고, 컵 파지력이 **상한**을 정한다. 그 사이가 설계 창이다.

여기서 처음 적는 값은 없다. 점성과 접촉 틈은 `dynamics`, 유리는 `afr`,
컵과 행정은 `dynamics`·`kinematics` 에서 온다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.destack
"""

from __future__ import annotations

import math

from . import afr, dynamics, fabrication, kinematics

#: 젖힘 전선의 폭과 길이 (m). 승강 볼스크루 두 본이 라인샤프트로 **장변 방향**에
#: 벌어져 있으므로(`BFC-LS-01` Ø30 L=2,700), 기울이면 단변 쪽 모서리가 뜬다.
#: 즉 쐐기는 장변 2,500 을 따라 열리고 전선 폭은 단변 1,400 이다.
PEEL_LENGTH_M = kinematics.PANEL_MM[0] / 1_000.0
PEEL_WIDTH_M = kinematics.PANEL_MM[1] / 1_000.0

#: 엣지 리프터가 모서리를 들어 올리는 속도 (m/s). 느릴수록 저항이 작다 —
#: 저항이 속도에 **선형**이라 여기서 무리할 이유가 없다.
EDGE_LIFT_MS = 0.05

#: 크랙을 낸 뒤 유지할 모서리 들림 (mm). 이 값이 뒤이어 드는 본 헤드의 저항을
#: 정한다 — 필름 저항이 쐐기 각의 **세제곱에 반비례**하므로 조금만 더 들면
#: 여유가 확 늘어난다.
#:
#: **고른 값이 아니라 유도한 값이다.** 진공 안전율 2.0(`dynamics.VACUUM_SAFETY`,
#: 진공 파단은 곧 유리 파손이라 그렇게 잡혀 있다)을 본 헤드에서도 지키려면
#: 얼마를 들어야 하는지를 `min_edge_lift_mm()` 이 이분법으로 푼다. 14.1 mm 가
#: 나오고, 표준 행정으로 올려 15 로 둔다 — 시험이 이 상수가 유도값을 덮는지 본다.
EDGE_LIFT_MM = 15.0


# ── 1-D 레이놀즈 스퀴즈 필름 ────────────────────────────────────────────
def reynolds_strip_n(length_m: float, width_m: float, gap_at, squeeze_at,
                     steps: int = 3_000) -> float:
    """두 판 사이 공기막이 내는 **저항력** (N). 양 끝은 대기압이다.

    `gap_at(x)` 는 자리 x 의 틈(m), `squeeze_at(x)` 는 그 자리가 벌어지는 속도
    (m/s). 압력을 두 번 적분해 힘으로 만든다 — 벌어지면 음압이므로 저항은 양수다.

    **양 끝을 대기압으로 두는 것이 요점이다.** 한쪽을 막으면(대칭면으로 두면)
    힘이 몇 배로 나온다. 적층에서 떼는 판은 네 변이 다 열려 있다.
    """
    dx = length_m / steps
    xs = [(i + 0.5) * dx for i in range(steps)]
    h = [gap_at(x) for x in xs]
    s = [squeeze_at(x) for x in xs]

    # h³/12μ · p' = ∫₀ˣ s dx + C — 사다리꼴 누적
    flux, acc = [], 0.0
    for v in s:
        acc += v * dx
        flux.append(acc - v * dx / 2)

    mu = dynamics.AIR_VISCOSITY_PAS
    a = sum(12 * mu * flux[i] / h[i] ** 3 * dx for i in range(steps))
    b = sum(12 * mu / h[i] ** 3 * dx for i in range(steps))
    c = -a / b                                    # p(0) = p(L) = 0 이 정한다

    p, acc = [], 0.0
    for i in range(steps):
        acc += 12 * mu * (flux[i] + c) / h[i] ** 3 * dx
        p.append(acc)
    return -sum(p) * dx * width_m


def contact_gap_m() -> float:
    """유리끼리 맞닿았을 때 남는 틈 (m) — 표면 거칠기 수준."""
    return dynamics.GLASS_CONTACT_GAP_MM / 1_000.0


# ── 세 가지 방법 ────────────────────────────────────────────────────────
def flat_lift_n(speed_ms: float, gap_mm: float | None = None) -> float:
    """**곧게 들기** — 판 전체를 나란히 띄운다. 틈이 어디서나 같다."""
    gap = contact_gap_m() if gap_mm is None else gap_mm / 1_000.0
    return reynolds_strip_n(PEEL_LENGTH_M, PEEL_WIDTH_M,
                            lambda _x: gap, lambda _x: speed_ms)


def wedge_lift_n(tip_mm: float, tip_speed_ms: float,
                 length_m: float | None = None,
                 width_m: float | None = None) -> float:
    """**젖히기** — 한쪽 끝만 들어 쐐기를 만든다. 틈이 자리마다 다르다."""
    length = PEEL_LENGTH_M if length_m is None else length_m
    width = PEEL_WIDTH_M if width_m is None else width_m
    theta = (tip_mm / 1_000.0) / length
    rate = tip_speed_ms / length
    return reynolds_strip_n(length, width,
                            lambda x: contact_gap_m() + theta * x,
                            lambda x: rate * x)


def shear_n(speed_ms: float) -> float:
    """**밀기** — 면내로 미끄러뜨린다. 틈이 안 변하니 쿠에트 전단만 남는다."""
    area = PEEL_LENGTH_M * PEEL_WIDTH_M
    return dynamics.AIR_VISCOSITY_PAS * area * speed_ms / contact_gap_m()


# ── 유리가 정하는 하한 ──────────────────────────────────────────────────
def glass_stress_mpa(peel_len_mm: float, tip_mm: float) -> float:
    """길이 `peel_len_mm` 를 끝에서 `tip_mm` 들었을 때 라미네이트 굽힘응력 (MPa).

    외팔보로 본다 — 크랙 앞쪽은 아직 붙어 있으므로 그 자리가 고정단이다.
    σ = 1.5 E t δ / a². 물성은 `afr` 에서 온다 (t 3.2 · E 70 GPa).
    """
    return (1.5 * afr.GLASS_E_MPA * afr.LAMINATE_T_MM * tip_mm) / peel_len_mm ** 2


def min_peel_length_mm(tip_mm: float = EDGE_LIFT_MM, safety: float = 2.0) -> float:
    """유리가 견디는 **가장 짧은** 젖힘 길이 (mm).

    짧게 젖힐수록 필름은 싸지지만 유리가 깨진다. σ ≤ 허용/안전율 을 풀면
    a ≥ √(1.5 E t δ · 안전율 / σ_allow) 다.
    """
    return math.sqrt(1.5 * afr.GLASS_E_MPA * afr.LAMINATE_T_MM * tip_mm
                     * safety / afr.GLASS_ALLOW_MPA)


# ── 설계점 ──────────────────────────────────────────────────────────────
def usable_cup_n() -> float:
    """안전율을 뺀 SEP-101 컵 파지력 (N)."""
    d, n = dynamics.sep_cups()
    return dynamics.cup_force_n(d, n) / dynamics.VACUUM_SAFETY


def edge_lifter(peel_len_mm: float | None = None) -> dict[str, float]:
    """모서리를 국부로 젖혀 **크랙을 내는** 동작 — 그 자리의 값들.

    이것이 이 해석의 답이다. 곧게 들면 자릿수로 막히지만, **길이 a 만 국부로**
    젖히면 저항이 한 자릿수 뉴턴으로 떨어진다. 유리가 a 의 하한을 정한다.
    """
    a_mm = min_peel_length_mm() * 1.2 if peel_len_mm is None else peel_len_mm
    a = a_mm / 1_000.0
    film = wedge_lift_n(EDGE_LIFT_MM, EDGE_LIFT_MS, a, PEEL_WIDTH_M)
    return {
        "peelLenMm": a_mm,
        "tipMm": EDGE_LIFT_MM,
        "angleDeg": math.degrees(math.atan((EDGE_LIFT_MM / 1_000.0) / a)),
        "filmN": film,
        "stressMpa": glass_stress_mpa(a_mm, EDGE_LIFT_MM),
        "allowMpa": afr.GLASS_ALLOW_MPA,
        "minLenMm": min_peel_length_mm(),
    }


def main_head_after_crack() -> dict[str, float]:
    """크랙을 낸 뒤 본 헤드가 이어 드는 구간 — **여기가 빠듯하다.**

    모서리가 `EDGE_LIFT_MM` 로 들려 있으면 판 전체가 그만큼 기운 쐐기가 된다.
    그 상태에서 본 헤드가 안전분리 상승 속도로 들면 저항이 얼마인가.
    """
    speed = dynamics.sep_peel()["peakMs"]
    film = wedge_lift_n(EDGE_LIFT_MM, speed)
    weight = dynamics.drives.PANEL_KG * dynamics.G
    return {
        "tipMm": EDGE_LIFT_MM,
        "angleDeg": math.degrees(math.atan((EDGE_LIFT_MM / 1_000.0) / PEEL_LENGTH_M)),
        "speedMs": speed,
        "filmN": film,
        "weightN": weight,
        "demandN": film + weight,
        "usableN": usable_cup_n(),
        "margin": usable_cup_n() / (film + weight),
    }


def min_edge_lift_mm(target_margin: float | None = None) -> float:
    """본 헤드가 목표 여유를 갖는 **가장 작은** 모서리 들림 (mm) — 이분법으로 푼다.

    필름 저항이 각의 세제곱에 반비례하므로 이 함수는 아주 잘 수렴한다. 값을
    손으로 고르지 않는 이유는 늘 같다 — 고른 값은 설계가 바뀌어도 안 움직인다.
    """
    target = dynamics.VACUUM_SAFETY if target_margin is None else target_margin
    speed = dynamics.sep_peel()["peakMs"]
    weight = dynamics.drives.PANEL_KG * dynamics.G

    def margin(tip: float) -> float:
        return usable_cup_n() / (wedge_lift_n(tip, speed) + weight)

    lo, hi = 1.0, 100.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if margin(mid) < target:
            lo = mid
        else:
            hi = mid
    return hi


def edge_lift_covers_the_margin() -> bool:
    """선언한 들림이 유도한 하한을 덮는가."""
    return EDGE_LIFT_MM >= min_edge_lift_mm()


def strip_over_disc() -> float:
    """1-D 스트립이 원판 근사보다 몇 배 큰가 — **1 보다 커야 한다.**

    두 모델이 다른 것은 옆으로 새는 공기 때문이다. 원판 근사
    (`dynamics.stefan_force_n`)는 사방으로 새게 두고, 여기 스트립은 **긴 쪽으로만**
    새게 둔다. 실제는 그 사이이고 스트립이 보수적이다.

    어느 쪽을 쓰느냐는 틈이 자리마다 다른가로 갈린다 — 프레임 적층처럼 나란히
    뜨는 2-D 판은 원판 근사, 쐐기처럼 틈이 한 축을 따라 변하면 스트립이다.
    비가 1 밑으로 뒤집히면 둘 중 하나가 틀린 것이다.
    """
    v = dynamics.sep_peel()["peakMs"]
    return flat_lift_n(v, dynamics.stack_gap_mm()) / dynamics.stefan_force_n(
        dynamics.stack_gap_mm(), v)


def flat_lift_is_hopeless(speed_ms: float = 1e-6) -> bool:
    """아무리 천천히 들어도 안 되는가 — 저항은 속도에 **선형**이다.

    「그럼 천천히 들면 되지 않나」가 첫 반문이다. 1 µm/s 라는, 0.05 mm 를 여는 데만
    50 초가 걸리는 속도에서도 컵 능력을 넘는다. 속도로 풀 수 있는 문제가 아니다.
    """
    return flat_lift_n(speed_ms) > usable_cup_n()


# ── 하드웨어가 되는가 ───────────────────────────────────────────────────
def _has(sheet: str, tag: str) -> bool:
    return any(c.tag == tag for c in fabrication.assembly(sheet).commercial)


def screws_are_coupled() -> bool:
    """승강 볼스크루 두 본이 한 서보에 묶여 있는가 — 그러면 캐리지가 못 기운다.

    `BFC-LS-01` 라인샤프트 · 베벨 기어박스가 두 스크루를 1:1 로 잇고 서보는
    `BLZ-101` 하나다. **그래서 본 캐리지로는 젖힐 수 없다.** 젖히려면 라인샤프트를
    떼고 서보를 하나 더 놓아 갠트리 동기로 돌려야 하는데, 그것은 축 하나를 새로
    다는 일이다 — 아래 `edge_lifter()` 가 훨씬 작다.
    """
    return _has(dynamics.SHEET_BFC, "BFC-LS-01")


def head_slide_is_in_plane() -> bool:
    """분리헤드의 공압 슬라이드(`BFC-SLD-01` 행정 100)는 **면내** 운동이다.

    밀기는 공짜지만(전단 0.01 N 대) 밀어서는 틈이 안 열린다 — 미는 것과 떼는 것은
    다른 일이다. 이미 있는 슬라이드로 무프레임을 풀 수는 없다.
    """
    return _has(dynamics.SHEET_BFC, "BFC-SLD-01")


def needs_an_edge_lifter() -> bool:
    """지금 하드웨어로는 크랙을 못 낸다 — 엣지 리프터가 새로 필요하다."""
    return screws_are_coupled() and flat_lift_is_hopeless()


# ── 요약 ────────────────────────────────────────────────────────────────
def compare() -> dict[str, float]:
    """세 방법을 같은 속도에서 견준다 — 이 표가 결론이다."""
    v = dynamics.sep_peel()["peakMs"]
    return {
        "flatN": flat_lift_n(v),
        "wedge010N": wedge_lift_n(PEEL_LENGTH_M * math.radians(0.10) * 1_000, v),
        "wedge020N": wedge_lift_n(PEEL_LENGTH_M * math.radians(0.20) * 1_000, v),
        "wedge050N": wedge_lift_n(PEEL_LENGTH_M * math.radians(0.50) * 1_000, v),
        "shearN": shear_n(0.05),
        "framedN": flat_lift_n(v, dynamics.stack_gap_mm()),
        "usableN": usable_cup_n(),
        "speedMs": v,
    }


def summary() -> dict[str, object]:
    lift, head, cmp = edge_lifter(), main_head_after_crack(), compare()
    return {
        "flatN": round(cmp["flatN"], 0),
        "framedN": round(cmp["framedN"], 1),
        "shearN": round(cmp["shearN"], 3),
        "usableN": round(cmp["usableN"], 0),
        "minPeelMm": round(lift["minLenMm"], 0),
        "peelLenMm": round(lift["peelLenMm"], 0),
        "peelTipMm": lift["tipMm"],
        "peelFilmN": round(lift["filmN"], 1),
        "peelStressMpa": round(lift["stressMpa"], 1),
        "headFilmN": round(head["filmN"], 0),
        "headDemandN": round(head["demandN"], 0),
        "headMargin": round(head["margin"], 2),
        "minEdgeLiftMm": round(min_edge_lift_mm(), 1),
        "stripOverDisc": round(strip_over_disc(), 2),
        "screwsCoupled": screws_are_coupled(),
        "needsEdgeLifter": needs_an_edge_lifter(),
    }


def checks() -> dict[str, tuple[float, float, bool]]:
    lift, head = edge_lifter(), main_head_after_crack()
    return {
        "엣지 리프터 필름": (lift["filmN"], usable_cup_n(), lift["filmN"] <= usable_cup_n()),
        "엣지 리프터 유리": (lift["stressMpa"], afr.GLASS_ALLOW_MPA,
                       lift["stressMpa"] <= afr.GLASS_ALLOW_MPA),
        "본 헤드 이어 들기": (head["demandN"], head["usableN"],
                        head["margin"] >= dynamics.VACUUM_SAFETY),
        "모서리 들림 사양": (min_edge_lift_mm(), EDGE_LIFT_MM, edge_lift_covers_the_margin()),
    }


def main() -> None:
    c = compare()
    print(f"무프레임 적층 — 같은 속도 {c['speedMs']:.3f} m/s 에서\n")
    print(f"  {'곧게 들기 (유리 접촉)':30} {c['flatN']:18,.0f} N")
    print(f"  {'젖히기 0.10°':30} {c['wedge010N']:18,.0f} N")
    print(f"  {'젖히기 0.20°':30} {c['wedge020N']:18,.0f} N")
    print(f"  {'젖히기 0.50°':30} {c['wedge050N']:18,.0f} N")
    print(f"  {'밀기 (면내 50 mm/s)':30} {c['shearN']:18,.2f} N")
    print(f"  {'(참고) 프레임 적층 곧게':30} {c['framedN']:18,.1f} N")
    print(f"  {'컵이 쓸 수 있는 힘':30} {c['usableN']:18,.0f} N")
    print("\n엣지 리프터 설계점")
    for k, v in edge_lifter().items():
        print(f"  {k:14} {v:10.2f}")
    print("\n검산")
    for name, (need, have, ok) in checks().items():
        print(f"  {'✓' if ok else '✗'} {name:18} 요구 {need:10.2f}  능력 {have:10.2f}")


if __name__ == "__main__":
    main()
