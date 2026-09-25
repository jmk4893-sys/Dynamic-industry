# -*- coding: utf-8 -*-
"""부선 급광 — **실리콘과 은만 들어가야 한다.**

전처리 라인 전체가 무엇을 위해 있는지가 여기 한 줄로 적힌다. 발주처 최종
결론이다 —

    **부선 전에 유리·구리·EVA·백시트가 다 제거되는 것이 부선에서 최상의
    결과를 낸다. 이것이 은의 순도와 실리콘의 순도에 가장 큰 변수다.**

그래서 이 모듈은 「무엇이 뜨고 무엇이 가라앉는가」를 세는 표가 아니라
**급광에 무엇이 남아 있으면 안 되는가**를 세는 표다. 부선은 실리콘과 은을
가르는 자리이지 폴리머를 걸러 내는 자리가 아니며, 앞에서 안 걷은 것은
부선이 못 고친다.

## 이 표가 실측에 서 있는 자리

발주처 체 시험이 준 값 둘이 이 모듈의 뼈대다.

  · **급광 입도 32~75 µm.** 이 회로가 실제로 쓰는 창이다.
  · **구리는 75 µm 아래에서 관측되지 않는다.** 99.9 % 가 그 위에 걸린다 —
    연성 금속이라 파쇄에서 깨지지 않고 눌려 펴져 오버사이즈로 남는다.

두 번째가 **구리 관문을 닫는다.** 급광이 −75 µm 이므로 구리는 체에서
걸러져 부선조에 애초에 안 들어온다. 전용 유닛이 필요 없고, 관문을 닫는
것이 기계가 아니라 **분급**이다.

## 세 번 틀렸고 그 자국을 남긴다

  ① 「불소 폴리머는 표면에너지가 낮아 **저절로 떠서** 정광을 버린다」 —
     현장은 반대다. 백시트는 가라앉고 EVA 가 뜬다.
  ② 그 정정을 「**조각이 부상 상한보다 커서** 기포가 못 들어 올린다」로
     설명했다. 그때 조각을 5 mm 로 잡고 있었다. 실제 급광은 32~75 µm 이고
     그것은 부선 효율 영역(10~100 µm) **한가운데**다 — 내 설명이 서 있던
     전제가 67~156 배 틀렸다.
  ③ 유리를 「제품」 칸에 두어 급광 적격처럼 셌다. 회수 가치와 급광 적격은
     다른 축이다.

그래서 **왜 백시트가 가라앉는지 이 모듈은 모른다고 적는다.**
`why_the_backsheet_sinks_is_open()` 이 후보를 늘어놓되 고르지 않는다 —
두 번 틀린 자리에서 세 번째 추측을 설계에 넣지 않는다. 다행히 **설계는
그 답에 안 걸린다**: 이유가 무엇이든 백시트는 실리콘·은과 같은 침강분으로
가므로 앞에서 걷어야 한다는 결론이 같다.

    PYTHONPATH=src python -c "from pv_preprocess import separation; print(separation.summary())"
"""

from __future__ import annotations

from dataclasses import dataclass

#: 물의 밀도 (g/cm³).
WATER_G_CM3 = 1.0

# ── 발주처 체 시험 실측 ─────────────────────────────────────────────────
#: 부선 급광 입도 창 (µm) — 이 회로가 실제로 쓰는 값이다.
FLOTATION_FEED_UM = (32.0, 75.0)
#: 구리가 체 시험에서 관측되지 않는 하한 (µm). 연성 금속이라 파쇄에서
#: 깨지지 않고 눌려 펴져 오버사이즈로 남는다.
COPPER_SIEVE_FLOOR_UM = 75.0
#: 그 아래로 내려가는 구리의 몫 — 실측상 사실상 0.
COPPER_PASSING_FRACTION = 0.001

#: 참고 — 문헌상 부선이 잘 듣는 입도 (µm). 급광 창이 이 안에 통째로 든다.
#: **이 값으로 무엇을 설명하려 하지 말 것** — 위 ②가 그 실수였다.
FLOTATION_EFFICIENT_UM = (10.0, 100.0)


@dataclass(frozen=True)
class Component:
    """급광에 들어올 수 있는 성분 하나.

    `behavior` 는 **관측이 우선**이다. 거동을 밀도나 입도에서 유도하지
    않는다 — 유도하려다 두 번 틀렸다.
    """

    key: str
    name: str
    density_g_cm3: float
    belongs_in_feed: bool         # 부선조에 있어도 되는가
    is_recovered: bool            # 어딘가에서 값이 나가는가
    top_size_um: float | None     # 대표 입도 (None = 급광 창 안)
    behavior: str                 # "float" · "sink" · "oversize"
    evidence: str                 # "관측" · "추정"
    removed_by: str               # 관문을 닫는 수단 ("" = 없다)
    note: str


#: 성분 표. 급광에 남아도 되는 것은 **실리콘과 은뿐**이다.
COMPONENTS: tuple[Component, ...] = (
    Component("silicon", "실리콘 셀", 2.33, True, True, None, "sink", "관측", "",
              "**지키려는 것.** 부선이 이것을 가른다"),
    Component("silver", "은 (전극·핑거)", 10.49, True, True, None, "sink", "추정",
              "",
              "**지키려는 것.** 양은 적고 값은 크다 — 순도가 곧 회수액이다. "
              "−32 µm 슬라임으로 얼마나 빠지는지는 따로 봐야 한다"),
    Component("glass", "강화유리", 2.50, False, True, None, "sink", "추정",
              "GRM-401",
              "값나가는 물건이지만 **급광에 있으면 안 된다.** 컬릿으로 따로 "
              "회수하고, 남으면 실리콘·은과 같은 침강분에서 희석한다"),
    Component("copper", "구리 (셀간 리본·버스바)", 8.96, False, True,
              COPPER_SIEVE_FLOOR_UM, "oversize", "관측", "분급 (−75 µm 체)",
              "연성이라 파쇄에서 안 깨지고 눌려 펴진다. 체 시험에서 "
              "75 µm 아래로 안 내려가므로 **급광에 애초에 안 들어온다** — "
              "전용 유닛이 아니라 분급이 이 관문을 닫는다"),
    Component("eva", "EVA 봉지재", 0.95, False, False, None, "float", "관측",
              "DG-HK60",
              "**뜬다** — 물보다 가볍다. 뜬다고 없어지는 것은 아니고 거품에 "
              "실려 나가며 물과 미립자를 같이 끌고 간다"),
    Component("pet", "백시트 PET 심재", 1.38, False, False, None, "sink", "관측",
              "BR-305/306",
              "**가라앉는다** — 실리콘·은과 같은 쪽이다. 이유는 아직 모른다 "
              "(`why_the_backsheet_sinks_is_open()`)"),
    Component("fluoro", "백시트 불소층 (PVF/PVDF)", 1.42, False, False, None,
              "sink", "관측", "BR-305/306",
              "PET 과 같은 행선지다. 표면에너지가 가장 낮은 축인데도 가라앉는 "
              "것이 이 회로의 관측이고, 그것이 설명을 두 번 무너뜨렸다"),
)

#: 발주처 최종 결론 — 이 넷이 다 빠져야 부선이 제 성능을 낸다.
THE_FOUR_GATES = ("glass", "copper", "eva", "backsheet")


def by_key(key: str) -> Component:
    """성분 하나를 이름으로 — 표가 정본이다."""
    return next(c for c in COMPONENTS if c.key == key)


# ── 분급 — 구리 관문을 닫는 것 ──────────────────────────────────────────
def feed_window_um() -> tuple[float, float]:
    """부선 급광 입도 창 (µm)."""
    return FLOTATION_FEED_UM


def is_screened_out(c: Component) -> bool:
    """분급에서 걸러져 부선조에 안 들어오는가."""
    return c.top_size_um is not None and c.top_size_um >= FLOTATION_FEED_UM[1]


def enters_the_cell(c: Component) -> bool:
    """부선조에 실제로 들어오는가."""
    return not is_screened_out(c)


def copper_is_closed_by_classification() -> bool:
    """구리 관문이 기계가 아니라 **분급**으로 닫히는가.

    닫힌다. 체 시험에서 구리가 75 µm 아래로 안 내려가고 급광이 −75 µm 이므로
    오버사이즈로 빠진다. 전용 유닛을 세울 자리가 아니었다.
    """
    return is_screened_out(by_key("copper"))


# ── 급광 안에서의 거동 (관측이다, 유도가 아니다) ────────────────────────
def floats(c: Component) -> bool:
    """뜨는가 — 관측값이다."""
    return c.behavior == "float"


def reports_to_sink(c: Component) -> bool:
    """침강분으로 가는가 — 실리콘·은이 있는 쪽이다."""
    return c.behavior == "sink"


def observed_components() -> tuple[Component, ...]:
    """거동이 실측으로 잡힌 성분 — 나머지는 추정이라고 적어 둔다."""
    return tuple(c for c in COMPONENTS if c.evidence == "관측")


# ── 급광 사양 — 이 모듈의 본론 ──────────────────────────────────────────
def feed_should_contain() -> tuple[Component, ...]:
    """부선조에 들어가야 하는 것 — 실리콘과 은뿐이다."""
    return tuple(c for c in COMPONENTS if c.belongs_in_feed)


def must_be_removed_before_flotation() -> tuple[Component, ...]:
    """급광에 있으면 안 되는 것 전부 — **쓸모없어서가 아니라 거기 있으면 안 돼서.**"""
    return tuple(c for c in COMPONENTS if not c.belongs_in_feed)


def valuable_but_not_in_the_feed() -> tuple[Component, ...]:
    """값은 나가는데 급광 밖인 것 — 유리와 구리다."""
    return tuple(c for c in COMPONENTS if c.is_recovered and not c.belongs_in_feed)


def contaminates_the_sink_fraction() -> tuple[Component, ...]:
    """걷어내지 못하면 실리콘·은과 **같은 침강분**에 섞이는 것."""
    return tuple(c for c in must_be_removed_before_flotation()
                 if enters_the_cell(c) and reports_to_sink(c))


def gate_components(gate: str) -> tuple[Component, ...]:
    """한 관문이 걷어야 하는 성분들 — 유닛이 자기 사양을 여기서 받아 간다."""
    if gate == "backsheet":
        return tuple(c for c in COMPONENTS if c.key in ("pet", "fluoro"))
    return (by_key(gate),)


def gate_component_keys(gate: str) -> frozenset[str]:
    """같은 것을 이름만으로."""
    return frozenset(c.key for c in gate_components(gate))


def gate_owner(gate: str) -> str:
    """네 관문마다 무엇이 닫는가 — 유닛일 수도, 분급일 수도 있다."""
    if gate == "backsheet":
        return by_key("pet").removed_by
    return by_key(gate).removed_by


def gates_without_an_owner() -> tuple[str, ...]:
    """닫는 수단이 없는 관문 — 설계 구멍이다."""
    return tuple(g for g in THE_FOUR_GATES if not gate_owner(g))


def all_four_gates_are_covered() -> bool:
    """네 관문이 다 닫혀 있는가."""
    return not gates_without_an_owner()


def silicon() -> Component:
    """지키려는 것 둘 중 하나 — 양이 많은 쪽."""
    return by_key("silicon")


def silver() -> Component:
    """지키려는 것 둘 중 하나 — 양은 적고 값이 큰 쪽."""
    return by_key("silver")


def eva_escape_goes_the_other_way() -> bool:
    """샌 EVA 가 실리콘 쪽으로 가는가 — 안 간다. 뜨는 쪽이다.

    **공짜라는 뜻은 아니다.** EVA 도 관문 넷 중 하나다. 다만 백시트와 달리
    **방향이 반대**라, 연마 절입이 EVA 로 조금 드는 것은 백시트가 남는
    것보다 훨씬 낫다.
    """
    return floats(by_key("eva"))


def purity_depends_on_this() -> tuple[str, ...]:
    """왜 이 표가 라인 전체의 판단 기준인가."""
    missing = gates_without_an_owner()
    lo, hi = FLOTATION_FEED_UM
    return (
        "부선 전에 **유리·구리·EVA·백시트가 다 제거되는 것**이 부선에서 최상의 "
        "결과를 낸다. 이것이 **은의 순도와 실리콘의 순도**에 가장 큰 변수다. "
        "발주처 최종 결론이고, 이 라인의 전처리 유닛이 전부 그것을 위해 있다.",
        "그래서 판단 기준이 유닛별 에너지나 동력이 아니라 **관문이 닫혔는가**다. "
        "부선은 실리콘과 은을 가르는 자리이지 폴리머를 걸러 내는 자리가 아니며, "
        "앞에서 안 걷은 것은 뒤에서 못 고친다.",
        f"급광 창이 {lo:.0f}~{hi:.0f} µm 이고, **구리 관문은 그 창이 닫는다** — "
        f"구리가 체 시험에서 {COPPER_SIEVE_FLOOR_UM:.0f} µm 아래로 안 내려가 "
        "오버사이즈로 빠지기 때문이다. 유리는 GRM-401, EVA 는 DG-HK60, "
        "백시트는 BR-305/306 이 맡는다."
        + ("" if not missing else f" 아직 비어 있는 관문: {', '.join(missing)}."),
        "**유리와 구리를 「불순물」로 뭉뚱그리면 안 된다.** 둘 다 값이 나가므로 "
        "따로 걷어 따로 판다 — 급광 밖이라는 것과 쓸모없다는 것은 다른 말이다.",
    )


# ── 모르는 것을 모른다고 적는다 ─────────────────────────────────────────
def why_the_backsheet_sinks_is_open() -> tuple[str, ...]:
    """**왜 가라앉는지 모른다.** 후보만 적고 고르지 않는다.

    이 자리에서 두 번 틀렸다 — 처음엔 「저절로 뜬다」, 다음엔 「조각이 커서
    못 뜬다」. 두 번째는 조각을 5 mm 로 잡고 한 설명인데 실제 급광이
    32~75 µm 라 전제가 무너졌다. 세 번째 추측을 설계에 넣지 않는다.
    """
    lo, hi = FLOTATION_FEED_UM
    return (
        f"급광 {lo:.0f}~{hi:.0f} µm 는 부선이 가장 잘 듣는 영역 한가운데다. "
        "입도로는 설명이 안 된다 — 소수성 입자라면 이 크기에서 잘 떠야 한다.",
        "밀도로도 설명이 안 된다. 부선은 황동석 4.2·방연석 7.5 도 띄운다. "
        "1.4 는 부선에 전혀 무거운 값이 아니다.",
        "**후보 ①** 열이력. 열박리를 지난 폴리머 표면은 처녀 불소수지가 아니라 "
        "탄화·산화된 면이라 표면에너지가 올라갔을 수 있다.",
        "**후보 ②** 시약 계통. 실리콘/유리를 가르려고 넣은 포집제·억제제·pH 가 "
        "폴리머를 같이 눌렀을 수 있다.",
        "**후보 ③** 형상. 갈린 필름은 같은 체 눈을 지나도 납작한 박편이라 "
        "난류 속에서 기포 부착이 안 버틸 수 있다.",
        "**설계는 이 답에 안 걸린다.** 이유가 무엇이든 백시트는 실리콘·은과 "
        "같은 침강분으로 가고, 그러면 앞에서 걷어야 한다는 결론이 같다. "
        "답이 필요해지는 때는 「부선 조건을 바꿔 폴리머를 띄울 수 있는가」를 "
        "물을 때뿐이고, 그것은 이 라인의 물음이 아니다.",
    )


def grinding_finer_is_not_a_way_out() -> tuple[str, ...]:
    """「곱게 갈면 오히려 뜨지 않을까」 — 실측이 이미 아니라고 답했다."""
    lo, hi = FLOTATION_FEED_UM
    return (
        f"한때 이것을 열린 물음으로 적었다. 답은 나와 있다 — 급광이 이미 "
        f"{lo:.0f}~{hi:.0f} µm 인데 **그 상태로 가라앉는다.**",
        "즉 더 갈아서 해결되는 문제가 아니다. 연마 분진이 집진에서 새면 "
        "같은 창으로 들어가 같은 쪽으로 갈 뿐이고, 「미분이라 특별히 더 "
        "해롭다」는 이야기도 아니다 — **급광은 전부가 미분이다.**",
        "그래서 안 잡힌 연마 분진은 그냥 **안 걷힌 백시트**다. 그 이상도 "
        "이하도 아니고, 포집률이 품질 사양인 이유가 그것으로 충분하다.",
    )


def summary() -> dict[str, object]:
    """한 눈에 — 전처리 유닛들이 같은 표를 본다."""
    lo, hi = FLOTATION_FEED_UM
    return {
        "feedWindowUm": [lo, hi],
        "feedShouldContain": [c.key for c in feed_should_contain()],
        "mustBeRemoved": [c.key for c in must_be_removed_before_flotation()],
        "valuableButNotInFeed": [c.key for c in valuable_but_not_in_the_feed()],
        "contaminatesSinkFraction": [c.key for c in contaminates_the_sink_fraction()],
        "screenedOut": [c.key for c in COMPONENTS if is_screened_out(c)],
        "theFourGates": list(THE_FOUR_GATES),
        "gateOwners": {g: gate_owner(g) or "(없음)" for g in THE_FOUR_GATES},
        "gatesWithoutAnOwner": list(gates_without_an_owner()),
        "allFourGatesAreCovered": all_four_gates_are_covered(),
        "copperIsClosedByClassification": copper_is_closed_by_classification(),
        "copperSieveFloorUm": COPPER_SIEVE_FLOOR_UM,
        "observedCount": len(observed_components()),
    }
