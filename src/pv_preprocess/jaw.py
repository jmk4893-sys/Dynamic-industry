# -*- coding: utf-8 -*-
"""4점 클램프 조 — 실린더를 어디에 다는가 (OI-03).

미결 항목은 이렇게 적혀 있다: "조 행정 187.5 mm 와 클레비스 자리는 있지만,
실린더를 조의 어느 지점에 다느냐는 모멘트 암과 간섭의 맞바꿈이다. 도면 한
장이 아니라 설계 결정이라 계산이 답을 하나로 좁히지 않는다."

계산이 답을 하나로 좁히지 않는 것은 맞다. 그런데 **좁혀 주는 것은 있다** —
어디까지는 안 되는지가 값으로 나온다. 그러면 검토회의는 되는 구간 안에서
고르면 되고, 그것이 「설계 결정」을 여는 일이다.

세 가지를 낸다.

* **힘은 남는다.** 조가 내야 하는 것은 반전 중에 패널을 놓치지 않을 마찰이고,
  Ø63 두 본이 그보다 훨씬 크다. 그러므로 실린더 자리를 정하는 것은 힘이 아니다.
* **편심은 부싱이 자른다.** 실린더 축이 가이드 포스트 축에서 e 만큼 벗어나면
  그 모멘트를 부싱 두 개가 **짝힘**으로 받는다 — 반력이 e 에 비례해 커지고
  LM40UU 등급이 상한을 준다. 볼 부싱이라 마찰로 물리는 일(자물림)은 안 생기고,
  걸리는 것은 **수명**이다.
* **간섭은 반대쪽에서 자른다.** 조가 열리는 자리(반경 860)에서 링 바깥
  (990)까지는 130 mm 뿐이라 실린더를 반경 바깥으로 곧게 세울 수 없다. 그래서
  편심이 생기는 것이지, 편심을 고른 것이 아니다.

그 두 상한이 **만나지 않는다**는 것이 답이다. 간섭이 강요하는 최소 편심이
지금 부싱 간격이 견디는 상한보다 크다. 부싱을 포스트가 허락하는 데까지 벌리면
겨우 열리는데 폭이 5 mm 다 — 사실상 한 점이고, 여유가 없다는 뜻이다. 그러면
검토회의가 고를 것은 편심이 아니라 **무엇을 바꿀 것인가**가 된다.

**여기서 처음 적는 값은 패드 마찰·파지 안전율·부싱 등급과 간격뿐이다.**
행정·보어·압력은 `kinematics`, 단면과 수량은 제작 도면집, 패널 질량은
`drives`, 반전 가속은 `dynamics` 에서 읽는다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.jaw
"""

from __future__ import annotations

import math
import re

from . import drives, dynamics, kinematics

# ── 파지·안내 (여기서 처음 적는 값) ──────────────────────────────────────

#: 패드(PU 70A)와 알루미늄 프레임 사이의 마찰계수, 건조. `dynamics.CUP_MU` 0.70
#: 은 고무–유리라 이름이 다르지만 크기는 같은 대역이다.
PAD_MU = 0.70

#: 파지 안전율. 놓치면 패널이 떨어지므로 `dynamics.VACUUM_SAFETY` 와 같이 잡는다.
GRIP_SAFETY = 2.0

#: 가이드 포스트 한 본에 앉는 부싱 두 개의 중심 간격 (mm). 처음에 잡은 값이고,
#: **이것이 답을 정하는 손잡이**다 — 넓히면 짝힘 반력이 그만큼 준다.
BUSHING_SPAN_MM = 200.0

#: LM40UU 한 개의 길이 (mm). 포스트 안에서 두 개를 벌릴 수 있는 한계가 여기서
#: 나온다 — 간격 + 이 길이가 포스트를 넘으면 안 된다.
BUSHING_LENGTH_MM = 112.0

#: LM40UU 의 정격 동하중 (N). **카탈로그 등급값이라 벤더 확인이 필요하다.**
#: 작게 잡는 쪽이 보수적이다 — 크게 잡으면 편심을 실제보다 많이 줘도 되는
#: 것처럼 보인다.
BUSHING_DYN_N = 1_960.0

#: 볼 부싱 마찰계수. 이 값이 작아서 **자물림은 안 생긴다** — 미끄럼 부싱이면
#: 편심 상한이 힘에서 나왔겠지만, 볼이면 수명에서 나온다.
BUSHING_MU = 0.004

#: 실린더 몸통이 행정 밖으로 더 차지하는 길이 (mm) — 헤드·캡·클레비스.
CYLINDER_BODY_EXTRA_MM = 190.0

SHEET = dynamics.SHEET_BFC
_STROKE = re.compile(r"×\s*([\d,]+)")


def _cyl():
    return dynamics._commercial(SHEET, "BFC-JCY-01")


# ── 실린더가 내는 힘 ────────────────────────────────────────────────────
def cylinder_stroke_mm() -> float:
    """실린더 행정 (mm) — 상용품 **규격**에서 읽는다 ("Ø63 × 190 복동 …").

    이름이 아니라 규격 칸에 있다. 여기 190 을 다시 적으면 부품표를 바꿔도
    안 따라온다.
    """
    m = _STROKE.search(_cyl().spec)
    if not m:
        raise ValueError(f"{_cyl().spec} 에서 행정을 못 읽었다")
    return float(m.group(1).replace(",", ""))


def stroke_covers_the_jaw() -> bool:
    """실린더 행정이 조 행정을 덮는가 — 덮어야 여는 자리까지 간다."""
    return cylinder_stroke_mm() >= kinematics.jaw_stroke_mm()


def cylinders_per_jaw() -> int:
    return _cyl().qty // 2                      # 조 둘에 넷이 붙는다


def cylinder_force_n() -> float:
    """실린더 한 본의 추력 (N) — 보어와 압력은 `kinematics` 가 갖고 있다."""
    area = math.pi * (kinematics.JAW_CYLINDER_BORE_MM / 2.0) ** 2
    return kinematics.JAW_AIR_MPA * area        # MPa·mm² = N


def clamp_force_n() -> float:
    """조 하나가 프레임에 거는 힘 (N)."""
    return cylinder_force_n() * cylinders_per_jaw()


# ── 조가 내야 하는 힘 ───────────────────────────────────────────────────
def required_clamp_n() -> float:
    """반전 중에 패널을 놓치지 않을 최소 파지력 (N).

    최악은 패널이 **세로로 선 순간**이다 — 그때 무게를 받는 것이 마찰뿐이다.
    반전 가속이 더하는 접선력도 같이 센다.
    """
    a_tan = (dynamics.flip_slip()["demandNm"] / drives.flip_inertia_kgm2()
             * kinematics.JAW_CLOSED_Z_MM / 1_000.0)
    pull = drives.PANEL_KG * math.hypot(dynamics.G, a_tan)
    return pull * GRIP_SAFETY / PAD_MU


def clamp_margin() -> float:
    return clamp_force_n() / required_clamp_n()


def force_is_not_what_decides(margin: float = 2.0) -> bool:
    """힘이 자리를 정하는가 — 여유가 이만큼 넘으면 아니다."""
    return clamp_margin() >= margin


# ── 편심이 부싱에 무엇을 하는가 ─────────────────────────────────────────
def bushing_reaction_n(offset_mm: float) -> float:
    """실린더 축이 e 만큼 벗어났을 때 부싱 하나가 받는 옆힘 (N).

    모멘트 F·e 를 간격 s 의 부싱 두 개가 짝힘으로 받는다 — N = F·e/s.
    조 하나에 포스트가 둘이라 그 짝힘을 둘이 나눈다.
    """
    posts = 2
    return clamp_force_n() * offset_mm / BUSHING_SPAN_MM / posts


def max_offset_mm() -> float:
    """부싱 등급이 허락하는 편심의 상한 (mm)."""
    posts = 2
    return BUSHING_DYN_N * BUSHING_SPAN_MM * posts / clamp_force_n()


def efficiency(offset_mm: float) -> float:
    """편심 때문에 잃는 추력의 비 (1 이면 손실 없음).

    옆힘이 만드는 마찰이 추력을 갉는다. 볼 부싱이라 이 손실이 작고, 그래서
    **자물림이 상한을 주지 않는다** — 미끄럼 부싱이었다면 여기서 걸렸을 것이다.
    """
    return 1.0 - 2 * BUSHING_MU * offset_mm / BUSHING_SPAN_MM


def jam_offset_mm() -> float:
    """자물림이 시작되는 편심 (mm) — 볼 부싱에서는 터무니없이 크다."""
    return BUSHING_SPAN_MM / (2 * BUSHING_MU)


def jamming_is_not_the_limit() -> bool:
    return jam_offset_mm() > max_offset_mm() * 10


# ── 간섭이 반대쪽에서 자른다 ────────────────────────────────────────────
def radial_room_mm() -> float:
    """조가 열린 자리에서 링 바깥면까지 남는 반경 (mm)."""
    return kinematics.ring_outer_r_mm() - kinematics.JAW_OPEN_Z_MM


def cylinder_length_mm() -> float:
    """실린더 전장 (mm) — 행정에 몸통을 더한 값이다."""
    return cylinder_stroke_mm() + CYLINDER_BODY_EXTRA_MM


def fits_radially() -> bool:
    """실린더를 반경 바깥으로 곧게 세울 수 있는가 — **없다.**

    이것이 편심이 생기는 이유다. 편심을 골라서 생긴 것이 아니라, 반경 방향에
    자리가 없어서 옆으로 비켜 다는 것이다.
    """
    return cylinder_length_mm() <= radial_room_mm()


def min_offset_mm() -> float:
    """반경 자리에 안 들어가는 만큼은 옆으로 비켜야 한다 (mm).

    실린더를 링 평면 안에서 비스듬히 눕히면 반경 성분이 줄고 편심이 는다.
    부족한 길이를 직각삼각형으로 바꾼 것이 이 하한이다.
    """
    over = cylinder_length_mm() - radial_room_mm()
    if over <= 0:
        return 0.0
    return math.sqrt(max(cylinder_length_mm() ** 2 - radial_room_mm() ** 2, 0.0))


def post_length_mm() -> float:
    """가이드 포스트 길이 (mm) — 부품표 BFC-JGP-01 이 정본이다."""
    return float(dynamics._part(SHEET, "BFC-JGP-01").size[2])


def max_span_mm() -> float:
    """포스트 안에서 부싱 두 개를 벌릴 수 있는 최대 간격 (mm)."""
    return post_length_mm() - BUSHING_LENGTH_MM


def required_span_mm() -> float:
    """간섭이 강요하는 편심을 부싱이 견디려면 필요한 간격 (mm)."""
    posts = 2
    return min_offset_mm() * clamp_force_n() / (BUSHING_DYN_N * posts)


def spreading_the_bushings_opens_it() -> bool:
    """부싱을 벌리면 구간이 열리는가 — 포스트가 그 간격을 받쳐 주는가."""
    return required_span_mm() <= max_span_mm()


def max_offset_at_max_span_mm() -> float:
    posts = 2
    return BUSHING_DYN_N * max_span_mm() * posts / clamp_force_n()


def window_mm() -> tuple[float, float]:
    """부싱을 최대로 벌렸을 때 실제로 고를 수 있는 편심 구간 (mm)."""
    return (min_offset_mm(), max_offset_at_max_span_mm())


def window_is_open() -> bool:
    """되는 구간이 비어 있지 않은가 — 간섭 하한이 부싱 상한 밑인가.

    지금 간격 200 으로는 **닫혀 있다.** 포스트가 허락하는 데까지 벌려야 겨우
    열리고, 그 폭이 몇 mm 밖에 안 된다는 것이 이 항목의 답이다.
    """
    lo, hi = window_mm()
    return lo < hi


# ── 판정 ────────────────────────────────────────────────────────────────
def options(step_mm: float = 50.0) -> list[dict[str, float]]:
    """편심별로 부싱 반력·효율·수명 여유를 낸다."""
    rows = []
    e = 0.0
    top = max_offset_mm() * 1.4
    while e <= top:
        n = bushing_reaction_n(e)
        rows.append({
            "offsetMm": round(e, 0),
            "bushingN": round(n, 0),
            "useOfRating": round(n / BUSHING_DYN_N, 2),
            "efficiency": round(efficiency(e), 4),
            "bushingOk": n <= BUSHING_DYN_N,
            "clearOk": e >= min_offset_mm(),
        })
        rows[-1]["ok"] = bool(rows[-1]["bushingOk"] and rows[-1]["clearOk"])
        e += step_mm
    return rows


def summary() -> dict[str, object]:
    return {
        "strokeMm": cylinder_stroke_mm(),
        "jawStrokeMm": kinematics.jaw_stroke_mm(),
        "strokeOk": stroke_covers_the_jaw(),
        "boreMm": kinematics.JAW_CYLINDER_BORE_MM,
        "cylPerJaw": cylinders_per_jaw(),
        "cylinderN": round(cylinder_force_n(), 0),
        "clampN": round(clamp_force_n(), 0),
        "requiredN": round(required_clamp_n(), 0),
        "margin": round(clamp_margin(), 2),
        "forceDecides": not force_is_not_what_decides(),
        "bushingSpanMm": BUSHING_SPAN_MM,
        "bushingRatingN": BUSHING_DYN_N,
        "maxOffsetMm": round(max_offset_mm(), 0),
        "jamOffsetMm": round(jam_offset_mm(), 0),
        "jamNotTheLimit": jamming_is_not_the_limit(),
        "radialRoomMm": round(radial_room_mm(), 0),
        "cylinderLengthMm": round(cylinder_length_mm(), 0),
        "fitsRadially": fits_radially(),
        "minOffsetMm": round(min_offset_mm(), 0),
        "postLengthMm": post_length_mm(),
        "maxSpanMm": round(max_span_mm(), 0),
        "requiredSpanMm": round(required_span_mm(), 0),
        "spreadOpensIt": spreading_the_bushings_opens_it(),
        "maxOffsetAtMaxSpanMm": round(max_offset_at_max_span_mm(), 0),
        "windowOpenAsDrawn": min_offset_mm() < max_offset_mm(),
        "windowOpen": window_is_open(),
        "windowMm": tuple(round(v, 0) for v in window_mm()),
        "windowWidthMm": round(window_mm()[1] - window_mm()[0], 0),
    }


def checks() -> list[tuple[str, bool, str]]:
    s = summary()
    return [
        ("실린더 행정이 조 행정을 덮는다", s["strokeOk"],
         f"실린더 {s['strokeMm']:.0f} ≥ 조 {s['jawStrokeMm']:.1f} mm"),
        ("힘은 자리를 정하지 않는다", s["margin"] >= 2.0,
         f"조 {s['clampN']:.0f} N vs 필요 {s['requiredN']:.0f} N — "
         f"여유 {s['margin']} 배"),
        ("볼 부싱이라 자물림이 상한이 아니다", s["jamNotTheLimit"],
         f"자물림 {s['jamOffsetMm']:,.0f} mm 는 등급 상한 "
         f"{s['maxOffsetMm']:.0f} mm 의 몇 십 배다"),
        ("실린더를 반경 바깥으로 곧게 못 세운다", not s["fitsRadially"],
         f"전장 {s['cylinderLengthMm']:.0f} > 남는 반경 "
         f"{s['radialRoomMm']:.0f} mm — 편심은 고른 것이 아니라 생긴 것이다"),
        ("지금 부싱 간격으로는 구간이 닫혀 있다", not s["windowOpenAsDrawn"],
         f"간섭이 강요하는 최소 편심 {s['minOffsetMm']:.0f} > 간격 "
         f"{s['bushingSpanMm']:.0f} 이 허락하는 {s['maxOffsetMm']:.0f} mm"),
        ("부싱을 벌리면 열린다", s["spreadOpensIt"],
         f"필요 간격 {s['requiredSpanMm']:.0f} ≤ 포스트 {s['postLengthMm']:.0f} 가 "
         f"허락하는 {s['maxSpanMm']:.0f} mm"),
        ("열려도 폭이 몇 mm 뿐이다", 0 < s["windowWidthMm"] < 20,
         f"편심 {s['windowMm'][0]:.0f} … {s['windowMm'][1]:.0f} mm — "
         f"폭 {s['windowWidthMm']:.0f} mm"),
        ("상한에서 부싱이 등급을 다 쓴다",
         abs(bushing_reaction_n(max_offset_mm()) - BUSHING_DYN_N) < 1.0,
         f"편심 {s['maxOffsetMm']:.0f} mm 에서 부싱 반력이 "
         f"{BUSHING_DYN_N:.0f} N 이다"),
    ]


def annotations() -> tuple[str, ...]:
    s = summary()
    return (
        f"조 개폐 Ø{s['boreMm']:.0f} × {s['strokeMm']:.0f} 두 본이 조 하나에 "
        f"{s['clampN']:.0f} N 을 건다 — 반전 중 패널을 잡는 데 필요한 "
        f"{s['requiredN']:.0f} N 의 {s['margin']} 배다. 실린더 자리를 정하는 것은 "
        f"힘이 아니다",
        f"조가 열린 자리에서 링 바깥까지 {s['radialRoomMm']:.0f} mm 뿐인데 실린더 "
        f"전장은 {s['cylinderLengthMm']:.0f} mm 다 — 반경 방향으로 곧게 못 세우므로 "
        f"눕혀 달아야 하고, 그때 축이 가이드에서 최소 {s['minOffsetMm']:.0f} mm "
        f"벗어난다. 편심은 고른 것이 아니라 생긴 것이다",
        f"편심 e 는 부싱 두 개가 짝힘으로 받는다 — 간격 {s['bushingSpanMm']:.0f} mm "
        f"에서 반력이 e 에 비례하고 LM40UU 등급 {s['bushingRatingN']:.0f} N 이 "
        f"상한 {s['maxOffsetMm']:.0f} mm 를 준다. 간섭이 강요하는 "
        f"{s['minOffsetMm']:.0f} 보다 작으니 **지금 간격으로는 자리가 없다**",
        f"손잡이는 부싱 간격이다 — {s['requiredSpanMm']:.0f} mm 로 벌리면 견디고, "
        f"포스트 {s['postLengthMm']:.0f} 는 {s['maxSpanMm']:.0f} 까지 허락한다. "
        f"다 벌려도 고를 수 있는 폭이 {s['windowWidthMm']:.0f} mm 뿐이라 사실상 "
        f"한 점이다 — 계산이 답을 좁히지 않는다던 자리에서 오히려 너무 좁혀졌다",
        f"볼 부싱이라 자물림은 {s['jamOffsetMm']:,.0f} mm 에서야 시작한다 — "
        f"미끄럼 부싱이었다면 힘에서 걸렸겠지만 여기서는 **수명**이 자른다",
        f"그래서 검토회의가 고를 것은 편심이 아니라 **무엇을 바꿀 것인가**다 — "
        f"포스트를 늘리거나(간격 여유), 부싱 등급을 올리거나, 실린더를 짧게 "
        f"(토글·레버로 행정을 줄여) 하거나. 셋 다 지금 도면을 건드린다",
        "부싱 등급과 간격, 실린더 몸통 길이는 여기서 잡은 값이다 — 벤더 자료가 "
        "오면 구간이 움직인다. 조 바 자체의 굽힘과 클레비스 핀은 안 봤다 (OI-03)",
    )


if __name__ == "__main__":                                   # pragma: no cover
    import json

    print(json.dumps(summary(), ensure_ascii=False, indent=1))
    print()
    for name, ok, why in checks():
        print(f"{'✓' if ok else '✗'} {name} — {why}")
    print()
    print(f"{'편심 mm':>8} {'부싱 N':>8} {'등급 사용':>9} {'효율':>8} "
          f"{'간섭':>5} {'부싱':>5}")
    for r in options():
        print(f"{r['offsetMm']:8.0f} {r['bushingN']:8.0f} {r['useOfRating']:9.2f} "
              f"{r['efficiency']:8.4f} {'○' if r['clearOk'] else '×':>5} "
              f"{'○' if r['bushingOk'] else '×':>5}")
    print()
    for line in annotations():
        print("·", line)
