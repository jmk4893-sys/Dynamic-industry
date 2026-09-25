# -*- coding: utf-8 -*-
"""하류 선별에서 무엇이 어디로 가는가 — **이 라인이 왜 폴리머를 미리 걷는지.**

전처리 유닛 두 개(`br_abrade` · `br_peel`)가 다 이 표 하나에 걸려 있다.
그래서 정본을 여기 둔다 — 두 곳에 적으면 갈라진다.

**한 번 통째로 틀리게 세웠다.** 처음에는 「불소 폴리머는 표면에너지가 낮아
시약 없이 저절로 뜨므로 정광에 올라와 품위를 버린다」로 적었다. 실제 현장은
**반대**다 — 백시트는 **가라앉고** EVA 는 **떠오른다.** 기구가 표면화학이
아니라 **밀도와 입도**였다.

  · EVA 는 물보다 가볍다(≈0.95). 기포도 시약도 필요 없이 그냥 뜬다.
  · 백시트는 물보다 무겁다(PET 1.38 · PVF 1.42 · PVDF 1.78). 가라앉는다.
  · 소수성이라 떠야 하지 않나 — **조각이 너무 크다.** 부선이 잘 듣는 입도는
    10~100 µm 이고 가장 좋은 조건에서도 상한이 1 mm 남짓(입자 무게 1~2 mg)
    이다. 그보다 크면 중력이 부력과 부착력을 이겨 기포에서 떨어진다.
    파쇄된 백시트 조각은 그 상한 위에 있다.

그래서 백시트는 실리콘·유리와 **같은 침강분**으로 간다. 실리콘이 값나가는
쪽이므로 이것이 최악의 행선지다 — `contaminates_silicon()`.

그리고 **둘 다 불순물이다.** 회수할 물건이 아니라 나가야 할 물건이므로,
「분말로 곱게 회수한다」 같은 고려가 이 라인에는 없다. 판단은 하나뿐이다 —
**실리콘에 섞이느냐 아니냐.**

    PYTHONPATH=src python -c "from pv_preprocess import separation; print(separation.summary())"
"""

from __future__ import annotations

from dataclasses import dataclass

#: 물의 밀도 (g/cm³) — 뜨고 가라앉는 것을 가르는 선.
WATER_G_CM3 = 1.0

#: 부선이 잘 듣는 입도 (µm). 이 밖으로 나가면 회수율이 떨어진다.
FLOTATION_EFFICIENT_UM = (10.0, 100.0)
#: 가장 좋은 조건에서의 부상 상한 (mm). 입자 무게로 1~2 mg 쯤이고, 그보다
#: 크면 중력이 부력·부착력을 이겨 기포에서 떨어진다. **백시트 조각이 이
#: 위에 있다는 것이 이 모듈의 요점이다.**
FLOTATION_COARSE_LIMIT_MM = 1.0
#: 파쇄된 백시트 조각의 대표 크기 (mm) — **계획값**이다. 파쇄기 설정에
#: 달렸고, 이 값이 상한 아래로 내려가면 이 모듈의 결론이 바뀐다.
SHRED_SIZE_MM = 5.0


@dataclass(frozen=True)
class Component:
    """파쇄 뒤 선별조에 들어가는 성분 하나."""

    key: str
    name: str
    density_g_cm3: float
    is_product: bool          # 회수할 물건인가, 나가야 할 물건인가
    size_mm: float            # 선별조에 들어갈 때의 대표 크기
    naturally_hydrophobic: bool   # 시약 없이도 기포가 붙는가 (폴리머는 그렇다)
    note: str


#: 성분 표. 밀도는 재료 물성이고, 크기는 파쇄 설정에 걸린 계획값이다.
COMPONENTS: tuple[Component, ...] = (
    Component("eva", "EVA 봉지재", 0.95, False, SHRED_SIZE_MM, True,
              "물보다 가벼워 **저절로 뜬다.** 불순물이지만 스스로 갈라지므로 "
              "이 라인이 걱정할 것이 아니다"),
    Component("pet", "백시트 PET 심재", 1.38, False, SHRED_SIZE_MM, True,
              "물보다 무거워 가라앉는다. 소수성이지만 조각이 부상 상한보다 "
              "커서 기포가 못 들어 올린다"),
    Component("fluoro", "백시트 불소층 (PVF/PVDF)", 1.42, False, SHRED_SIZE_MM, True,
              "PET 과 같은 행선지다 — 표면에너지가 가장 낮은 축인데도 크기가 "
              "이긴다. PVDF 계면 1.78 로 더 무겁다"),
    Component("silicon", "실리콘 셀", 2.33, True, 0.5, False,
              "**이 라인이 지키려는 것.** 침강분에 있다"),
    Component("glass", "강화유리", 2.50, True, 1.0, False,
              "역시 침강분이고, 실리콘과는 별도 단계에서 갈린다"),
)


def floats_by_buoyancy(c: Component) -> bool:
    """기포 없이 부력만으로 뜨는가 — 밀도가 물보다 낮은가."""
    return c.density_g_cm3 < WATER_G_CM3


def too_coarse_to_float(c: Component) -> bool:
    """소수성이어도 기포가 못 들어 올리는 크기인가."""
    return c.size_mm > FLOTATION_COARSE_LIMIT_MM


def can_be_lifted_by_bubbles(c: Component) -> bool:
    """기포가 들어 올릴 수 있는가 — 시약 없이 붙고, 들 만큼 작아야 한다.

    둘 다여야 한다. 실리콘·유리는 시약을 줘야 붙으므로 **자연 상태로는**
    안 뜨고, 백시트는 붙긴 하는데 조각이 너무 커서 떨어진다.
    """
    return c.naturally_hydrophobic and not too_coarse_to_float(c)


def floats(c: Component) -> bool:
    """뜨는가 — 부력으로 뜨거나 기포가 들어 올리거나."""
    return floats_by_buoyancy(c) or can_be_lifted_by_bubbles(c)


def reports_to_sink(c: Component) -> bool:
    """침강분으로 가는가."""
    return not floats(c)


def silicon() -> Component:
    """지키려는 것."""
    return next(c for c in COMPONENTS if c.key == "silicon")


def contaminates_silicon() -> tuple[Component, ...]:
    """실리콘과 같은 침강분으로 가는 **불순물** — 이 라인이 미리 걷을 대상."""
    return tuple(c for c in COMPONENTS
                 if not c.is_product and reports_to_sink(c))


def separates_itself() -> tuple[Component, ...]:
    """스스로 갈라지는 불순물 — 전처리가 손댈 필요가 없다."""
    return tuple(c for c in COMPONENTS
                 if not c.is_product and floats_by_buoyancy(c))


def must_be_removed_before_crushing() -> tuple[str, ...]:
    """파쇄 **전에** 걷어야 하는 것의 이름 — 전처리 유닛의 사양이 여기서 나온다.

    파쇄된 뒤에는 못 고친다. 밀도로도(실리콘과 같은 쪽) 부선으로도
    (크기가 상한 위) 안 갈라지기 때문이다.
    """
    return tuple(c.key for c in contaminates_silicon())


def the_whole_backsheet_is_the_target() -> bool:
    """불소층만 걷으면 되는가, 백시트 전체인가.

    **전체다.** PET 심재도 불소층과 같은 행선지라, 외피만 벗기면 심재가
    남아 그대로 실리콘으로 간다. 이것이 「가장 약한 면에서 뜯으면 된다」는
    답을 무너뜨린 사실이다.
    """
    keys = set(must_be_removed_before_crushing())
    return {"pet", "fluoro"} <= keys


def eva_overshoot_is_harmless() -> bool:
    """백시트를 걷다가 EVA 를 조금 더 파도 되는가.

    된다. EVA 는 물보다 가벼워 스스로 뜨므로, 딸려 나오든 남든 실리콘을
    안 더럽힌다. 연마 절입에 여유를 줄 수 있는 근거다.
    """
    return all(floats_by_buoyancy(c) for c in COMPONENTS if c.key == "eva")


def would_fines_float_instead() -> tuple[str, ...]:
    """**열린 물음** — 곱게 갈면 오히려 떠서 빠지지 않는가.

    백시트가 가라앉는 이유가 밀도만이 아니라 **크기**이기도 하므로, 부선이
    잘 듣는 10~100 µm 까지 잘게 만들면 소수성이 살아나 뜰 수도 있다.
    그러면 연마가 문제를 만드는 게 아니라 푸는 셈이 된다.

    다만 이 저장소는 그 위에 설계를 세우지 않는다 — 미립자는 굵은 알갱이에
    달라붙고 거품에 기계적으로 실리기도 해서 방향이 정해져 있지 않다.
    **파쇄 전에 걷어내면 이 물음에 답할 필요가 없다는 것**이 두 전처리
    유닛의 근거다.
    """
    return (
        f"백시트가 침강분으로 가는 이유에 크기가 들어 있다 — 조각 "
        f"{SHRED_SIZE_MM:.0f} mm 가 부상 상한 {FLOTATION_COARSE_LIMIT_MM:.0f} mm "
        f"위다. {FLOTATION_EFFICIENT_UM[0]:.0f}~{FLOTATION_EFFICIENT_UM[1]:.0f} µm "
        "까지 내리면 소수성이 살아나 뜰 수도 있다.",
        "그러면 연마 분진이 실리콘을 더럽히는 게 아니라 부선이 걷어 주는 "
        "것이 된다 — 지금 설계의 전제와 부호가 반대다.",
        "그런데 미립자는 굵은 알갱이에 달라붙고(slime coating) 거품에 "
        "기계적으로도 실려서, 어느 쪽으로 갈지가 회로마다 다르다. 실측 없이 "
        "이 위에 설계를 세우면 안 된다.",
        "**파쇄 전에 걷어내면 이 물음 자체가 없어진다.** 그것이 `br_abrade` 와 "
        "`br_peel` 이 있는 이유이고, 둘 중 무엇을 고르든 바뀌지 않는다.",
    )


def why_it_sinks_although_it_is_hydrophobic() -> tuple[str, ...]:
    """소수성인데 왜 가라앉는가 — 한 번 반대로 적었으므로 이유를 남긴다."""
    bs = next(c for c in COMPONENTS if c.key == "fluoro")
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
        f"{next(c for c in COMPONENTS if c.key == 'eva').density_g_cm3} 로 "
        "물보다 가볍기 때문이다. 같은 조에서 둘이 갈리는 이유가 서로 다르다.",
    )


def summary() -> dict[str, object]:
    """한 눈에 — 두 전처리 유닛이 같은 값을 본다."""
    return {
        "waterG": WATER_G_CM3,
        "coarseLimitMm": FLOTATION_COARSE_LIMIT_MM,
        "shredSizeMm": SHRED_SIZE_MM,
        "floatsByItself": [c.key for c in separates_itself()],
        "contaminatesSilicon": list(must_be_removed_before_crushing()),
        "wholeBacksheetIsTheTarget": the_whole_backsheet_is_the_target(),
        "evaOvershootIsHarmless": eva_overshoot_is_harmless(),
        "siliconDensity": silicon().density_g_cm3,
    }
