# -*- coding: utf-8 -*-
"""부선 급광 — **실리콘과 은만 들어가야 한다.**

전처리 라인 전체가 무엇을 위해 있는지가 여기 한 줄로 적힌다. 발주처 최종
결론이다 —

    **부선 전에 유리·구리·EVA·백시트가 다 제거되는 것이 부선에서 최상의
    결과를 낸다. 이것이 은의 순도와 실리콘의 순도에 가장 큰 변수다.**

그래서 이 모듈은 「무엇이 뜨고 무엇이 가라앉는가」를 세는 표가 아니다.
**급광에 무엇이 남아 있으면 안 되는가**를 세는 표다. 부선은 실리콘과 은을
가르는 자리이지 폴리머를 걸러 내는 자리가 아니며, 앞에서 안 걷은 것은
부선이 못 고친다.

**두 번 틀렸고 그 자국을 남긴다.**

  ① 처음에는 「불소 폴리머는 표면에너지가 낮아 저절로 떠서 정광을 버린다」고
     적었다. 현장은 반대다 — 백시트는 가라앉고 EVA 가 뜬다. **입도 영역을
     잘못 봤다**: 부선 효율 영역은 10~100 µm 이고 부상 상한이 1 mm 남짓이라,
     파쇄 조각은 소수성이어도 기포에서 떨어진다. EVA 가 뜨는 것은 밀도
     0.95 로 물보다 가벼워서지 시약 덕이 아니다.
  ② 다음에는 그 정정을 「백시트만 걷으면 된다」로 좁게 읽고 유리를 **제품**
     칸에 두었다. 유리는 값나가는 물건이 맞지만 **급광에 있어서는 안 되는**
     물건이다. 회수 가치와 급광 적격은 다른 축이고, 표가 그 둘을 갈라야 한다.

지금 표는 성분마다 그 둘을 따로 든다 — `is_recovered` (값이 나가는가) 와
`belongs_in_feed` (부선조에 들어가도 되는가). 넷이 제거 대상인 이유가
「쓸모없어서」가 아니라 **「거기 있으면 안 돼서」**임이 그렇게 드러난다.

    PYTHONPATH=src python -c "from pv_preprocess import separation; print(separation.summary())"
"""

from __future__ import annotations

from dataclasses import dataclass

#: 물의 밀도 (g/cm³).
WATER_G_CM3 = 1.0

#: 부선이 잘 듣는 입도 (µm).
FLOTATION_EFFICIENT_UM = (10.0, 100.0)
#: 가장 좋은 조건에서의 부상 상한 (mm). 입자 무게로 1~2 mg 쯤이고, 그보다
#: 크면 중력이 부력·부착력을 이겨 기포에서 떨어진다.
FLOTATION_COARSE_LIMIT_MM = 1.0
#: 파쇄된 폴리머 조각의 대표 크기 (mm) — **계획값**. 파쇄기 설정에 달렸고,
#: 이 값이 상한 아래로 내려가면 `would_fines_float_instead()` 가 실제가 된다.
SHRED_SIZE_MM = 5.0


@dataclass(frozen=True)
class Component:
    """파쇄 뒤 남을 수 있는 성분 하나.

    두 축을 **따로** 든다. 값이 나가는 것(`is_recovered`)과 부선조에 들어가도
    되는 것(`belongs_in_feed`)은 다르다 — 유리와 구리가 그 차이의 자리다.
    """

    key: str
    name: str
    density_g_cm3: float
    belongs_in_feed: bool         # 부선조에 있어도 되는가
    is_recovered: bool            # 어딘가에서 값이 나가는가
    size_mm: float
    naturally_hydrophobic: bool   # 시약 없이도 기포가 붙는가
    removed_by: str               # 어느 유닛이 걷는가 ("" = 이 라인에 없다)
    note: str


#: 성분 표. 급광에 남아도 되는 것은 **실리콘과 은뿐**이다.
COMPONENTS: tuple[Component, ...] = (
    Component("silicon", "실리콘 셀", 2.33, True, True, 0.5, False, "",
              "**지키려는 것.** 부선이 이것을 가른다"),
    Component("silver", "은 (전극·핑거)", 10.49, True, True, 0.1, False, "",
              "**지키려는 것.** 양은 적고 값은 크다 — 순도가 곧 회수액이다"),
    Component("glass", "강화유리", 2.50, False, True, 1.0, False, "GRM-401",
              "값나가는 물건이지만 **급광에 있으면 안 된다.** 컬릿으로 따로 "
              "회수하고, 남으면 실리콘과 같은 침강분에서 희석한다"),
    Component("copper", "구리 (셀간 리본·버스바)", 8.96, False, True, 3.0, False, "",
              "역시 값나가지만 급광 밖이다. **이 라인에 전용 유닛이 없다** — "
              "JBR-201 은 정션박스와 케이블을 떼고 리본은 끊어 스텁만 남긴다"),
    Component("eva", "EVA 봉지재", 0.95, False, False, SHRED_SIZE_MM, True,
              "DG-HK60",
              "물보다 가벼워 뜨지만, 뜬다고 없어지는 것은 아니다 — 거품에 "
              "실려 나가며 물과 미립자를 같이 끌고 간다"),
    Component("pet", "백시트 PET 심재", 1.38, False, False, SHRED_SIZE_MM, True,
              "BR-305/306",
              "가라앉아 실리콘·은과 같은 침강분으로 간다. 소수성이지만 조각이 "
              "부상 상한보다 커서 기포가 못 들어 올린다"),
    Component("fluoro", "백시트 불소층 (PVF/PVDF)", 1.42, False, False,
              SHRED_SIZE_MM, True, "BR-305/306",
              "PET 과 같은 행선지다 — 표면에너지가 가장 낮은 축인데도 크기가 "
              "이긴다"),
)

#: 발주처 최종 결론 — 이 넷이 다 빠져야 부선이 제 성능을 낸다.
THE_FOUR_GATES = ("glass", "copper", "eva", "backsheet")


def by_key(key: str) -> Component:
    """성분 하나를 이름으로 — 표가 정본이다."""
    return next(c for c in COMPONENTS if c.key == key)


# ── 뜨고 가라앉는 것 (왜 부선이 못 고치는가) ────────────────────────────
def floats_by_buoyancy(c: Component) -> bool:
    """기포 없이 부력만으로 뜨는가."""
    return c.density_g_cm3 < WATER_G_CM3


def too_coarse_to_float(c: Component) -> bool:
    """소수성이어도 기포가 못 들어 올리는 크기인가."""
    return c.size_mm > FLOTATION_COARSE_LIMIT_MM


def can_be_lifted_by_bubbles(c: Component) -> bool:
    """기포가 들어 올릴 수 있는가 — 붙고, 들 만큼 작아야 한다."""
    return c.naturally_hydrophobic and not too_coarse_to_float(c)


def floats(c: Component) -> bool:
    """뜨는가 — 부력으로 뜨거나 기포가 들어 올리거나."""
    return floats_by_buoyancy(c) or can_be_lifted_by_bubbles(c)


def reports_to_sink(c: Component) -> bool:
    """침강분으로 가는가 — 실리콘·은이 있는 쪽이다."""
    return not floats(c)


# ── 급광 사양 — 이 모듈의 본론 ──────────────────────────────────────────
def feed_should_contain() -> tuple[Component, ...]:
    """부선조에 들어가야 하는 것 — 실리콘과 은뿐이다."""
    return tuple(c for c in COMPONENTS if c.belongs_in_feed)


def must_be_removed_before_flotation() -> tuple[Component, ...]:
    """급광에 있으면 안 되는 것 전부 — **쓸모없어서가 아니라 거기 있으면 안 돼서.**"""
    return tuple(c for c in COMPONENTS if not c.belongs_in_feed)


def valuable_but_not_in_the_feed() -> tuple[Component, ...]:
    """값은 나가는데 급광 밖인 것 — 유리와 구리다.

    이 둘이 「불순물」이라는 말로 뭉뚱그려지면 회수 설계가 틀어진다.
    따로 걷어 따로 판다.
    """
    return tuple(c for c in COMPONENTS if c.is_recovered and not c.belongs_in_feed)


def contaminates_the_sink_fraction() -> tuple[Component, ...]:
    """걷어내지 못하면 실리콘·은과 **같은 침강분**에 섞이는 것.

    뜨는 것(EVA)보다 이쪽이 더 나쁘다 — 뜨는 것은 적어도 방향이 반대다.
    """
    return tuple(c for c in must_be_removed_before_flotation()
                 if reports_to_sink(c))


def gate_components(gate: str) -> tuple[Component, ...]:
    """한 관문이 걷어야 하는 성분들 — 유닛이 자기 사양을 여기서 받아 간다."""
    if gate == "backsheet":
        return tuple(c for c in COMPONENTS if c.key in ("pet", "fluoro"))
    return (by_key(gate),)


def gate_component_keys(gate: str) -> frozenset[str]:
    """같은 것을 이름만으로 — 유닛 쪽에서 집합 비교에 쓴다."""
    return frozenset(c.key for c in gate_components(gate))


def silicon() -> Component:
    """지키려는 것 둘 중 하나 — 양이 많은 쪽."""
    return by_key("silicon")


def silver() -> Component:
    """지키려는 것 둘 중 하나 — 양은 적고 값이 큰 쪽."""
    return by_key("silver")


def eva_escape_goes_the_other_way() -> bool:
    """샌 EVA 가 실리콘 쪽으로 가는가 — 안 간다. 뜨는 쪽이다.

    **공짜라는 뜻은 아니다.** EVA 도 관문 넷 중 하나이고, 거품에 실려 나가며
    물과 미립자를 같이 끌고 간다. 다만 백시트와 달리 **방향이 반대**라,
    연마 절입이 EVA 로 조금 드는 것은 백시트가 남는 것보다 훨씬 낫다.
    """
    return floats(by_key("eva")) and not reports_to_sink(by_key("eva"))


def gate_owner(gate: str) -> str:
    """네 관문마다 어느 유닛이 맡는가 — 빈 문자열이면 **이 라인에 없다.**"""
    if gate == "backsheet":
        return by_key("pet").removed_by
    return by_key(gate).removed_by


def gates_without_a_unit() -> tuple[str, ...]:
    """맡는 유닛이 없는 관문 — 설계 구멍이다."""
    return tuple(g for g in THE_FOUR_GATES if not gate_owner(g))


def all_four_gates_are_covered() -> bool:
    """네 관문이 다 닫혀 있는가."""
    return not gates_without_a_unit()


def purity_depends_on_this() -> tuple[str, ...]:
    """왜 이 표가 라인 전체의 판단 기준인가 — 발주처 결론을 그대로 적는다."""
    missing = gates_without_a_unit()
    return (
        "부선 전에 **유리·구리·EVA·백시트가 다 제거되는 것**이 부선에서 최상의 "
        "결과를 낸다. 이것이 **은의 순도와 실리콘의 순도**에 가장 큰 변수다. "
        "발주처 최종 결론이고, 이 라인의 모든 전처리 유닛이 그것을 위해 있다.",
        "그래서 판단 기준이 유닛별 에너지나 동력이 아니라 **관문이 닫혔는가**다. "
        "부선은 실리콘과 은을 가르는 자리이지 폴리머를 걸러 내는 자리가 아니며, "
        "앞에서 안 걷은 것은 뒤에서 못 고친다.",
        f"지금 네 관문 중 "
        + (f"**{len(missing)} 개가 비어 있다**: {', '.join(missing)}."
           if missing else "빈 곳이 없다.")
        + " 유리는 GRM-401, EVA 는 DG-HK60 이 맡고, 백시트는 BR-305/306 이 "
          "그 자리를 채우려고 설계됐다.",
        "**유리와 구리를 「불순물」로 뭉뚱그리면 안 된다.** 둘 다 값이 나가므로 "
        "따로 걷어 따로 판다 — 급광 밖이라는 것과 쓸모없다는 것은 다른 말이다.",
    )


# ── 열린 물음 ───────────────────────────────────────────────────────────
def would_fines_float_instead() -> tuple[str, ...]:
    """곱게 갈면 오히려 떠서 빠지지 않는가 — 적되 그 위에 설계를 안 세운다."""
    return (
        f"백시트가 침강분으로 가는 이유에 크기가 들어 있다 — 조각 "
        f"{SHRED_SIZE_MM:.0f} mm 가 부상 상한 {FLOTATION_COARSE_LIMIT_MM:.0f} mm "
        f"위다. {FLOTATION_EFFICIENT_UM[0]:.0f}~{FLOTATION_EFFICIENT_UM[1]:.0f} µm "
        "까지 내리면 소수성이 살아나 뜰 수도 있다.",
        "그러면 연마 분진이 실리콘을 더럽히는 게 아니라 부선이 걷어 주는 것이 "
        "된다 — 지금 설계의 전제와 부호가 반대다.",
        "그런데 미립자는 굵은 알갱이에 달라붙고(slime coating) 거품에 기계적으로도 "
        "실려서, 어느 쪽으로 갈지가 회로마다 다르다. 실측 없이 이 위에 설계를 "
        "세우면 안 된다.",
        "**파쇄 전에 걷어내면 이 물음 자체가 없어진다.** 그것이 관문을 앞단에 "
        "두는 이유이고, 네 관문 전부에 같은 논리가 걸린다.",
    )


def why_it_sinks_although_it_is_hydrophobic() -> tuple[str, ...]:
    """소수성인데 왜 가라앉는가 — 한 번 반대로 적었으므로 이유를 남긴다."""
    bs, eva = by_key("fluoro"), by_key("eva")
    return (
        f"밀도가 {bs.density_g_cm3} 로 물보다 무겁다. 뜨려면 기포가 들어 "
        "올려야 하는데, 부력만으로는 안 된다.",
        f"그런데 조각이 {SHRED_SIZE_MM:.0f} mm 라 부상 상한 "
        f"{FLOTATION_COARSE_LIMIT_MM:.0f} mm 위다. 이 크기에서는 중력이 "
        "부력과 부착력을 이겨 기포에서 떨어진다.",
        "즉 **표면화학이 맞아도 입도가 틀리면 안 뜬다.** 표면에너지가 낮다는 "
        "것만 보고 「저절로 뜬다」고 한 것이 오류였다 — 그것은 10~100 µm "
        "영역의 이야기다.",
        f"EVA 가 뜨는 것은 시약이나 기포 덕이 아니라 밀도가 "
        f"{eva.density_g_cm3} 로 물보다 가볍기 때문이다. 같은 조에서 둘이 "
        "갈리는 이유가 서로 다르다.",
    )


def summary() -> dict[str, object]:
    """한 눈에 — 전처리 유닛들이 같은 표를 본다."""
    return {
        "feedShouldContain": [c.key for c in feed_should_contain()],
        "mustBeRemoved": [c.key for c in must_be_removed_before_flotation()],
        "valuableButNotInFeed": [c.key for c in valuable_but_not_in_the_feed()],
        "contaminatesSinkFraction": [c.key for c in contaminates_the_sink_fraction()],
        "theFourGates": list(THE_FOUR_GATES),
        "gateOwners": {g: gate_owner(g) or "(없음)" for g in THE_FOUR_GATES},
        "gatesWithoutAUnit": list(gates_without_a_unit()),
        "allFourGatesAreCovered": all_four_gates_are_covered(),
        "coarseLimitMm": FLOTATION_COARSE_LIMIT_MM,
        "shredSizeMm": SHRED_SIZE_MM,
    }
