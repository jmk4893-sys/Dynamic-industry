# -*- coding: utf-8 -*-
"""부선 급광 — **뜨는 쪽이 은정광이고, 가라앉는 쪽이 실리콘이다.**

전처리 라인 전체가 무엇을 위해 있는지가 여기 적힌다. 발주처 최종 결론이
「부선 전에 **유리·구리·EVA·백시트**가 다 제거되는 것이 최상의 결과를 내고
그것이 **은과 실리콘 순도**의 가장 큰 변수」이므로, 판단 기준은 유닛별
에너지가 아니라 **관문이 닫혔는가**다.

## 이 부선이 무엇을 하는 자리인가

**은을 띄우는 자리다.** 뉴캐슬대(CRITIUM) 연구가 정본이고 — 파쇄·분쇄 뒤
황화계 포집제(AEROFLOAT 242 · AEROPHINE 3418A)로 **금속 은만 기포에 태워**
올린다. 배치 97.6 % 회수에 32 배 농축, 연속에서는 거의 100 % 회수에 83 배
농축, 기액 체류 1 분. 실리콘은 표면이 산화막이라 포집제가 안 붙어 가라앉는다.

    뜨는 쪽 (정광)   → **은**      · 급광의 1/83 쯤으로 줄어든다
    가라앉는 쪽      → **실리콘**  · 셀 무게의 90 % 가 여기다

**그래서 불순물마다 떨어지는 제품이 다르다.**

    EVA        → 뜬다  → **은정광을 더럽힌다**
    백시트·유리 → 가라앉는다 → **실리콘을 더럽힌다**
    구리        → 분급에서 빠져 아예 안 들어온다

그리고 뜨는 쪽이 **83 배로 줄어든 작은 흐름**이라, 같은 g 이 들어가도 은정광
품위를 훨씬 크게 깎는다 (`float_side_is_amplified_by()`). EVA 가 그 자리에
있다.

## 네 번 틀렸고 그 자국을 남긴다

  ① 「불소 폴리머는 저절로 **떠서** 정광을 버린다」 — 백시트는 가라앉는다.
  ② 「**조각이 부상 상한보다 커서** 못 뜬다」 — 그때 조각을 5 mm 로 잡았는데
     실제 급광이 32~75 µm 라 전제가 67~156 배 틀렸다.
  ③ 유리를 「제품」 칸에 두어 급광 적격처럼 셌다 — 회수 가치와 급광 적격은
     다른 축이다.
  ④ **은을 침강분에 두었다.** 은은 뜬다. 그래서 「EVA 는 방향이 반대라 덜
     아프다」고 적은 것이 정반대였다 — EVA 가 가는 쪽에 **은이 있다.**

**표 전체가 실측 위에 서 있다** — 일곱 성분의 거동이 다 관측이고 추정이
하나도 없다(`the_table_is_fully_observed()`). 여섯 번 뒤집힌 끝에 닿은
자리이고, 새 성분을 추정으로 넣으면 시험이 먼저 깨진다.

**왜 백시트가 가라앉는지는 여전히 모른다고 적는다**
(`why_the_backsheet_sinks_is_open()`). 다만 후보 하나가 세졌다 — 포집제가
**금속 은에 선택적**이니 폴리머에는 안 붙는다. 그래도 고르지 않는다:
자연 소수성 물질은 포집제 없이도 거품에 실리는 일이 흔하다.

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

# ── 은 부선 — 뉴캐슬대(CRITIUM) 보고값 ──────────────────────────────────
#: 쓰는 포집제. 황화계라 **금속 은에 선택적**이고 실리콘 산화막에는 안 붙는다.
AG_COLLECTORS = ("AEROFLOAT 242", "AEROPHINE 3418A")
#: 배치 시험 — 은 회수율과 농축비.
AG_RECOVERY_BATCH, AG_UPGRADE_BATCH = 0.976, 32.0
#: 연속 파일럿 — 정상상태 기준.
AG_RECOVERY_CONTINUOUS, AG_UPGRADE_CONTINUOUS = 1.00, 83.0
#: 기액 체류시간 (분).
AG_RESIDENCE_MIN = 1.0


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
              "**지키려는 것.** 표면이 산화막이라 포집제가 안 붙어 가라앉는다 — "
              "셀 무게의 90 % 가 이쪽이다"),
    Component("silver", "은 (전극·핑거)", 10.49, True, True, None, "float", "관측",
              "",
              "**지키려는 것 — 그리고 이 부선이 노리는 것.** 황화계 포집제가 "
              "금속 은에 붙어 기포로 올린다. 뉴캐슬대 보고로 배치 97.6 % / "
              "연속 ~100 % 회수, 농축 32~83 배. 정광이 그만큼 작아지므로 "
              "**같이 뜬 불순물이 품위를 크게 깎는다**"),
    Component("glass", "강화유리", 2.50, False, True, None, "sink", "관측",
              "GRM-401",
              "**가라앉는다**(관측). 실리콘과 같은 SiO₂ 계라 포집제가 안 붙는 "
              "것으로 설명이 되지만, 그 설명이 아니라 관측이 근거다. 값나가는 "
              "물건이어도 **급광에 있으면 안 된다** — 컬릿으로 따로 회수하고, "
              "남으면 실리콘 산물을 희석한다"),
    Component("copper", "구리 (셀간 리본·버스바)", 8.96, False, True,
              COPPER_SIEVE_FLOOR_UM, "oversize", "관측", "분급 (−75 µm 체)",
              "연성이라 파쇄에서 안 깨지고 눌려 펴진다. 체 시험에서 "
              "75 µm 아래로 안 내려가므로 **급광에 애초에 안 들어온다** — "
              "전용 유닛이 아니라 분급이 이 관문을 닫는다"),
    Component("eva", "EVA 봉지재", 0.95, False, False, None, "float", "관측",
              "DG-HK60",
              "**뜬다 — 그리고 거기에 은이 있다.** 한때 「방향이 반대라 덜 "
              "아프다」고 적었는데 정반대다. 뜨는 쪽은 83 배로 줄어든 작은 "
              "흐름이라 여기 섞인 것이 은정광 품위를 가장 크게 깎는다"),
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
    """거동이 실측으로 잡힌 성분."""
    return tuple(c for c in COMPONENTS if c.evidence == "관측")


def estimated_components() -> tuple[Component, ...]:
    """거동이 아직 추정인 성분 — **지금은 비어 있다.**

    표 전체가 실측 위에 서 있다는 뜻이고, 이 모듈이 여섯 번 뒤집힌 끝에
    닿은 자리다. 새 성분을 추정으로 넣으면 시험이 먼저 깨진다 — 추측을
    조용히 섞지 말라는 뜻이다.
    """
    return tuple(c for c in COMPONENTS if c.evidence != "관측")


def the_table_is_fully_observed() -> bool:
    """표에 추정이 하나도 안 남았는가."""
    return not estimated_components()


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
    """실리콘과 같은 침강분으로 가는 불순물."""
    return contaminates("silicon")


def float_product() -> Component:
    """뜨는 쪽 제품 — 은정광."""
    return by_key("silver")


def sink_product() -> Component:
    """가라앉는 쪽 제품 — 실리콘."""
    return by_key("silicon")


def float_side_is_amplified_by() -> float:
    """뜨는 쪽이 몇 배로 줄어드는가 — 연속 운전 농축비.

    정광이 급광의 1/83 이므로, **같은 g 이 뜨는 쪽에 들어가면 가라앉는 쪽에
    들어갈 때보다 품위를 그만큼 크게 깎는다.** EVA 가 그 자리에 있다.
    """
    return AG_UPGRADE_CONTINUOUS


def contaminates(product_key: str) -> tuple[Component, ...]:
    """이 제품과 **같은 쪽으로 가는** 불순물 — 전처리가 걷어야 할 대상.

    제품마다 오염원이 다르다는 것이 이 모듈의 요지다. 「불순물」을
    뭉뚱그리면 어느 제품을 지키는 일인지가 사라진다.
    """
    product = by_key(product_key)
    return tuple(c for c in COMPONENTS
                 if not c.belongs_in_feed
                 and enters_the_cell(c)
                 and c.behavior == product.behavior)


def eva_lands_on_the_silver() -> bool:
    """EVA 가 은정광 쪽으로 가는가 — **간다.** 한때 반대로 적었다."""
    return by_key("eva").behavior == float_product().behavior


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
    """왜 이 표가 라인 전체의 판단 기준인가 — 제품마다 오염원이 다르다."""
    lo, hi = FLOTATION_FEED_UM
    ag = ", ".join(c.name for c in contaminates("silver"))
    si = ", ".join(c.name for c in contaminates("silicon"))
    return (
        "부선 전에 **유리·구리·EVA·백시트가 다 제거되는 것**이 부선에서 최상의 "
        "결과를 낸다. 이것이 **은의 순도와 실리콘의 순도**에 가장 큰 변수다. "
        "발주처 최종 결론이고, 이 라인의 전처리 유닛이 전부 그것을 위해 있다.",
        f"**뜨는 쪽이 은정광이다.** 황화계 포집제가 금속 은만 태워 올려 "
        f"{AG_UPGRADE_CONTINUOUS:.0f} 배로 농축한다(연속 기준, 회수 ~100 %). "
        f"그래서 같이 뜬 것이 품위를 크게 깎는다 — 은을 더럽히는 것은 **{ag}** 다.",
        f"**가라앉는 쪽이 실리콘이다.** 표면 산화막이라 포집제가 안 붙는다. "
        f"실리콘을 더럽히는 것은 **{si}** 다.",
        f"급광 창이 {lo:.0f}~{hi:.0f} µm 이고 **구리 관문은 그 창이 닫는다** — "
        f"구리가 체 시험에서 {COPPER_SIEVE_FLOOR_UM:.0f} µm 아래로 안 내려가 "
        "오버사이즈로 빠지기 때문이다. 관문을 닫는 것이 꼭 기계는 아니다.",
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
        "**후보 ①** 열이력·노화막. 열박리를 지난 폴리머 표면은 처녀 불소수지가 "
        "아니라 탄화·산화된 면이라 표면에너지가 올라갔을 수 있다. 같은 연구가 "
        "「노화로 생긴 막이 포집제 흡착을 좌우한다」고 적은 것과 결이 같다.",
        f"**후보 ② (가장 유력)** 포집제 선택성. 쓰는 것이 "
        f"{' · '.join(AG_COLLECTORS)} 로 **금속 은에 선택적인 황화계**라 "
        "폴리머에는 안 붙는다. 다만 자연 소수성 물질은 포집제 없이도 거품에 "
        "실리는 일이 흔해서, 이것만으로 단정하지 않는다.",
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
        "floatProduct": float_product().key,
        "sinkProduct": sink_product().key,
        "contaminatesSilver": [c.key for c in contaminates("silver")],
        "contaminatesSilicon": [c.key for c in contaminates("silicon")],
        "floatSideAmplifiedBy": float_side_is_amplified_by(),
        "evaLandsOnTheSilver": eva_lands_on_the_silver(),
        "screenedOut": [c.key for c in COMPONENTS if is_screened_out(c)],
        "theFourGates": list(THE_FOUR_GATES),
        "gateOwners": {g: gate_owner(g) or "(없음)" for g in THE_FOUR_GATES},
        "gatesWithoutAnOwner": list(gates_without_an_owner()),
        "allFourGatesAreCovered": all_four_gates_are_covered(),
        "copperIsClosedByClassification": copper_is_closed_by_classification(),
        "copperSieveFloorUm": COPPER_SIEVE_FLOOR_UM,
        "observedCount": len(observed_components()),
        "estimatedCount": len(estimated_components()),
        "tableIsFullyObserved": the_table_is_fully_observed(),
    }
