"""러퍼-스캐빈저-클리너 회로 물질수지 (순환부하 수렴 계산).

회로 구성:

    신급광 + 스캐빈저 정광 + 클리너 미광  ->  러퍼 FC-101
    러퍼 정광  -> (희석) ->  클리너 FC-103  ->  최종 정광
    러퍼 미광  ->  스캐빈저 FC-102  ->  최종 미광
    클리너 미광, 스캐빈저 정광  ->  러퍼 급광으로 순환

각 흐름은 성분별 총량이 아니라 **속부선/지연부선/비부선 분획별 유량**을
추적한다. 이렇게 해야 러퍼에서 속부선 분획이 빠져나간 뒤의 미광이
스캐빈저에서 얼마나 느리게 부상하는지, 반대로 러퍼 정광이 클리너에서
왜 잘 부상하는지가 모델에 자연스럽게 나타난다.

순환류가 있으므로 해는 반복법(successive substitution)으로 수렴시킨다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .kinetics import ComponentKinetics, perfect_mixer_recovery

WATER_SG = 1.0


# --------------------------------------------------------------------------
# 흐름 (stream)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Stream:
    """분획별 고체 유량과 물 유량을 갖는 공정 흐름.

    Attributes:
        species_tph: 성분명 -> (속부선, 지연부선, 비부선) 건조 고체 t/h.
        water_tph: 물 유량 t/h.
    """

    species_tph: dict[str, tuple[float, float, float]]
    water_tph: float = 0.0

    @staticmethod
    def empty(components: tuple[str, ...]) -> "Stream":
        return Stream({c: (0.0, 0.0, 0.0) for c in components}, 0.0)

    @staticmethod
    def from_feed(
        component_tph: dict[str, float], kinetics: dict[str, ComponentKinetics], water_tph: float
    ) -> "Stream":
        """신급광 — 각 성분을 거동 모델의 분획 비율대로 나눈다."""
        return Stream(
            {
                name: tuple(tph * f for f in kinetics[name].species_fractions)
                for name, tph in component_tph.items()
            },
            water_tph,
        )

    @property
    def components(self) -> tuple[str, ...]:
        return tuple(self.species_tph)

    def component_tph(self, name: str) -> float:
        return sum(self.species_tph[name])

    @property
    def component_totals(self) -> dict[str, float]:
        return {name: sum(v) for name, v in self.species_tph.items()}

    @property
    def dry_tph(self) -> float:
        return sum(sum(v) for v in self.species_tph.values())

    @property
    def slurry_tph(self) -> float:
        return self.dry_tph + self.water_tph

    @property
    def solids_mass_fraction(self) -> float:
        total = self.slurry_tph
        return self.dry_tph / total if total else 0.0

    def grade_fraction(self, name: str) -> float:
        return self.component_tph(name) / self.dry_tph if self.dry_tph else 0.0

    def volumetric_flow_m3h(self, specific_gravity: dict[str, float]) -> float:
        solids = sum(
            self.component_tph(name) / specific_gravity[name] for name in self.species_tph
        )
        return solids + self.water_tph / WATER_SG

    def __add__(self, other: "Stream") -> "Stream":
        if set(self.species_tph) != set(other.species_tph):
            raise ValueError("성분 구성이 다른 흐름은 합칠 수 없음")
        return Stream(
            {
                name: tuple(a + b for a, b in zip(self.species_tph[name], other.species_tph[name]))
                for name in self.species_tph
            },
            self.water_tph + other.water_tph,
        )

    def with_water(self, water_tph: float) -> "Stream":
        return replace(self, water_tph=water_tph)

    def scaled(self, factor: float) -> "Stream":
        return Stream(
            {name: tuple(v * factor for v in vals) for name, vals in self.species_tph.items()},
            self.water_tph * factor,
        )

    def max_abs_difference(self, other: "Stream") -> float:
        """수렴 판정용 — 두 흐름의 최대 성분별 유량 차이 (t/h)."""
        diff = abs(self.water_tph - other.water_tph)
        for name, vals in self.species_tph.items():
            for a, b in zip(vals, other.species_tph[name]):
                diff = max(diff, abs(a - b))
        return diff


# --------------------------------------------------------------------------
# 단위 셀
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FlotationUnit:
    """회로를 구성하는 부선 단위 (러퍼 / 스캐빈저 / 클리너).

    체적이 확정된 셀은 ``effective_volume_m3`` 를, 아직 사이징 전이라
    목표 체류시간만 정한 셀은 ``target_residence_min`` 을 준다.

    Attributes:
        tag: 기기 번호.
        duty: 역할.
        water_recovery: 급광 물 중 정광(거품)으로 넘어가는 비율.
            **entrainment 를 유발하는 것은 이 물뿐이다.**
        wash_water_m3h: 거품 세척수 — 정광 쪽 물에 더해지지만 맥석을
            동반하지 않으므로 entrainment 를 늘리지 않는다.
        dilution_target_solids: 급광 고체 농도 목표. 주어지면 부족한
            만큼 희석수를 넣는다 (None 이면 희석 없음).
        collector_boost: 약제 분할 투입 효과 — 지연부선 분획의 속도상수에
            곱하는 계수. 스캐빈저에 포수제를 추가 투입할 때 1 보다 크게 준다.
        cells_in_series: 이 단을 구성하는 동일 체적 셀의 개수. 2 이상이면
            tanks-in-series 로 계산한다. 같은 총 체적이라도 직렬 분할이
            단일 완전혼합조보다 회수율이 높다.
        rate_scale_factor: 회분식 속도상수를 실기로 옮길 때 곱하는 계수.
    """

    tag: str
    duty: str
    water_recovery: float
    effective_volume_m3: float | None = None
    target_residence_min: float | None = None
    wash_water_m3h: float = 0.0
    dilution_target_solids: float | None = None
    collector_boost: float = 1.0
    cells_in_series: int = 1
    rate_scale_factor: float = 1.0

    def __post_init__(self) -> None:
        if (self.effective_volume_m3 is None) == (self.target_residence_min is None):
            raise ValueError(
                f"{self.tag}: effective_volume_m3 와 target_residence_min 중 정확히 하나만 지정"
            )
        if not 0.0 <= self.water_recovery < 1.0:
            raise ValueError(f"{self.tag}: water_recovery 는 0 이상 1 미만")
        if self.cells_in_series < 1:
            raise ValueError(f"{self.tag}: cells_in_series 는 1 이상")
        if self.rate_scale_factor <= 0.0:
            raise ValueError(f"{self.tag}: rate_scale_factor 는 양수")

    def residence_min(self, feed_volume_m3h: float) -> float:
        if self.target_residence_min is not None:
            return self.target_residence_min
        if feed_volume_m3h <= 0:
            raise ValueError(f"{self.tag}: 급광 유량이 0")
        return self.effective_volume_m3 / (feed_volume_m3h / 60.0)


@dataclass(frozen=True)
class UnitResult:
    """단위 셀 1기의 계산 결과."""

    unit: FlotationUnit
    feed: Stream
    concentrate: Stream
    tailings: Stream
    residence_min: float
    feed_volume_m3h: float
    dilution_water_m3h: float

    def recovery(self, component: str) -> float:
        f = self.feed.component_tph(component)
        return self.concentrate.component_tph(component) / f if f else 0.0

    @property
    def mass_pull(self) -> float:
        return self.concentrate.dry_tph / self.feed.dry_tph if self.feed.dry_tph else 0.0


def dilute(stream: Stream, target_solids: float | None) -> tuple[Stream, float]:
    """급광을 목표 고체 농도까지 희석한다. (희석된 흐름, 추가 물 t/h)."""
    if target_solids is None or stream.dry_tph <= 0:
        return stream, 0.0
    required_water = stream.dry_tph * (1.0 - target_solids) / target_solids
    added = max(0.0, required_water - stream.water_tph)
    return stream.with_water(stream.water_tph + added), added


def float_unit(
    feed: Stream,
    unit: FlotationUnit,
    kinetics: dict[str, ComponentKinetics],
    specific_gravity: dict[str, float],
    composite_carry_ratio: float = 0.0,
) -> UnitResult:
    """셀 1기를 통과시켜 정광/미광으로 나눈다.

    분획별로 진부선 회수율을 적용하고, 부상하지 못한 고체에 대해서만
    수분 동반 혼입을 더한다. 거품 세척수는 정광 물에는 더해지지만
    entrainment 계산에는 들어가지 않는다.

    ``cells_in_series`` 가 2 이상이면 총 체류시간을 균등 분할한
    tanks-in-series 로 계산한다.

    Args:
        composite_carry_ratio: 부상한 Ag 1 kg 이 **같은 입자의 일부로**
            달고 올라가는 맥석의 kg. Ag 는 순수 입자가 아니라 Si 웨이퍼에
            소결된 전극이므로, 표면이 소수성이 되어 부상해도 Si 코어를 함께
            끌고 온다. 이것은 수분 동반(entrainment)과 달리 **세척수로
            제거되지 않으며**, 정광 품위의 물리적 상한을 만든다.
            상한 품위 = 1 / (1 + carry_ratio). ``Ag_locked_gangue`` 성분이
            있으면 이미 급광부터 추적하므로 이 호환용 근사는 적용하지 않는다.
    """
    diluted, added_water = dilute(feed, unit.dilution_target_solids)
    volume = diluted.volumetric_flow_m3h(specific_gravity)
    tau = unit.residence_min(volume)

    conc: dict[str, tuple[float, float, float]] = {}
    tail: dict[str, tuple[float, float, float]] = {}
    for name, vals in diluted.species_tph.items():
        kin = kinetics[name]
        rates = (kin.k_fast, kin.k_slow * unit.collector_boost, 0.0)
        c: list[float] = []
        t: list[float] = []
        n = unit.cells_in_series
        for tph, k in zip(vals, rates):
            kt = k * unit.rate_scale_factor * (tau / n)
            floated = tph * (1.0 - (1.0 / (1.0 + kt)) ** n)
            entrained = (tph - floated) * kin.entrainment_factor * unit.water_recovery
            c.append(floated + entrained)
            t.append(tph - floated - entrained)
        conc[name] = (c[0], c[1], c[2])
        tail[name] = (t[0], t[1], t[2])

    # 신규 설계는 Ag 와 결합된 Si 를 ``Ag_locked_gangue`` 성분으로 처음부터
    # 추적한다. 이 성분이 없는 구형/범용 입력에만 1회성 근사모델을 허용한다.
    if composite_carry_ratio > 0.0 and "Ag_locked_gangue" not in diluted.species_tph:
        _add_composite_carry(diluted, kinetics, conc, tail, composite_carry_ratio)

    conc_water = diluted.water_tph * unit.water_recovery + unit.wash_water_m3h
    tail_water = diluted.water_tph * (1.0 - unit.water_recovery)
    return UnitResult(
        unit=unit,
        feed=diluted,
        concentrate=Stream(conc, conc_water),
        tailings=Stream(tail, tail_water),
        residence_min=tau,
        feed_volume_m3h=volume,
        dilution_water_m3h=added_water,
    )


def _add_composite_carry(
    feed: Stream,
    kinetics: dict[str, ComponentKinetics],
    conc: dict[str, tuple[float, float, float]],
    tail: dict[str, tuple[float, float, float]],
    carry_ratio: float,
) -> None:
    """부상한 유용성분에 물리적으로 붙어 함께 올라가는 맥석을 정광으로 옮긴다.

    맥석 성분(진부선 없음) 사이에는 미광에 남아 있는 질량에 비례해 배분하고,
    남은 양을 초과하지 않도록 자른다. ``conc``/``tail`` 을 제자리에서 고친다.
    """
    # carry_ratio 는 Ag-Si 복합입자에서 유도한 값이므로 Cu/Pb 등 다른
    # 부상성분까지 합산하지 않는다.
    valuable = sum(conc.get("Ag", (0.0, 0.0, 0.0)))
    gangue = [n for n in conc if kinetics[n].r_max == 0.0]
    available = {n: sum(tail[n]) for n in gangue}
    total_available = sum(available.values())
    if valuable <= 0.0 or total_available <= 0.0:
        return
    demand = min(carry_ratio * valuable, total_available)
    for name in gangue:
        share = demand * available[name] / total_available
        c, t = list(conc[name]), list(tail[name])
        # 맥석은 전량 비부선 분획이므로 세 번째 슬롯에서 옮긴다.
        moved = min(share, t[2])
        c[2] += moved
        t[2] -= moved
        conc[name] = (c[0], c[1], c[2])
        tail[name] = (t[0], t[1], t[2])


# --------------------------------------------------------------------------
# 회로
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CircuitResult:
    """수렴된 회로 물질수지.

    ``fresh_water_m3h``는 부선 회로 경계에서 필요한 희석·세척수 중 필터 여액을
    제외한 양이다. 설비 전체의 외부 신수는 농축조 월류 재사용·블리드·케이크
    수분까지 닫은 :class:`plant.MechanicalOption.fresh_makeup_m3h`로 평가한다.
    """

    new_feed: Stream
    rougher: UnitResult
    scavenger: UnitResult | None
    cleaner: UnitResult
    concentrate: Stream
    tailings: Stream
    recycle: Stream
    iterations: int
    residual_tph: float
    fresh_water_m3h: float
    filtrate_return_m3h: float = 0.0

    @property
    def circulating_load(self) -> float:
        """순환부하 = 순환 고체량 / 신급광 고체량."""
        return self.recycle.dry_tph / self.new_feed.dry_tph if self.new_feed.dry_tph else 0.0

    def recovery(self, component: str) -> float:
        """최종 정광 기준 회로 전체 회수율."""
        f = self.new_feed.component_tph(component)
        return self.concentrate.component_tph(component) / f if f else 0.0

    @property
    def mass_pull(self) -> float:
        return self.concentrate.dry_tph / self.new_feed.dry_tph if self.new_feed.dry_tph else 0.0

    def enrichment_ratio(self, component: str) -> float:
        feed_grade = self.new_feed.grade_fraction(component)
        if feed_grade <= 0:
            return 0.0
        return self.concentrate.grade_fraction(component) / feed_grade

    def separation_efficiency(self, valuable: str) -> float:
        """Newton 선별효율 = R_valuable - R_gangue."""
        r_v = self.recovery(valuable)
        gangue_feed = self.new_feed.dry_tph - self.new_feed.component_tph(valuable)
        gangue_conc = self.concentrate.dry_tph - self.concentrate.component_tph(valuable)
        return r_v - (gangue_conc / gangue_feed if gangue_feed else 0.0)

    def mass_balance_error_tph(self) -> float:
        """신급광 - (최종 정광 + 최종 미광) 의 최대 성분별 오차."""
        err = 0.0
        for name in self.new_feed.components:
            out = self.concentrate.component_tph(name) + self.tailings.component_tph(name)
            err = max(err, abs(self.new_feed.component_tph(name) - out))
        return err


def solve_circuit(
    feed_component_tph: dict[str, float],
    kinetics: dict[str, ComponentKinetics],
    specific_gravity: dict[str, float],
    rougher: FlotationUnit,
    scavenger: FlotationUnit | None,
    cleaner: FlotationUnit,
    rougher_feed_solids: float = 0.25,
    composite_carry_ratio: float = 0.0,
    filtrate_return_m3h: float = 0.0,
    max_iterations: int = 500,
    tolerance_tph: float = 1e-12,
) -> CircuitResult:
    """순환류를 포함한 회로를 반복법으로 수렴시킨다.

    러퍼 급광 농도는 ``rougher_feed_solids`` 로 제어한다. 순환류가 이미
    그보다 묽으면 신수를 넣지 않는다(물을 뺄 수는 없으므로).

    Args:
        feed_component_tph: 신급광 성분별 건조 고체 유량.
        rougher_feed_solids: 러퍼 급광 목표 고체 질량분율.
        filtrate_return_m3h: 필터프레스에서 러퍼로 직접 되돌리는 여액.
            내부 회수수이므로 신수 소요량에서는 제외하지만 수력부하에는 포함한다.

    Returns:
        수렴된 :class:`CircuitResult`.

    Raises:
        RuntimeError: 지정 반복 횟수 안에 수렴하지 못한 경우.
    """
    components = tuple(feed_component_tph)
    missing = set(components) - set(kinetics)
    if missing:
        raise KeyError(f"부선 거동 모델이 없는 성분: {sorted(missing)}")

    dry = sum(feed_component_tph.values())
    recycle = Stream.empty(components)
    solids_only = Stream.from_feed(feed_component_tph, kinetics, 0.0)

    r_res = s_res = c_res = None
    fresh_water = 0.0
    for iteration in range(1, max_iterations + 1):
        total_dry = dry + recycle.dry_tph
        required_water = total_dry * (1.0 - rougher_feed_solids) / rougher_feed_solids
        fresh_water = max(
            0.0, required_water - recycle.water_tph - filtrate_return_m3h
        )
        rougher_feed = solids_only.with_water(
            fresh_water + filtrate_return_m3h
        ) + recycle

        ccr = composite_carry_ratio
        r_res = float_unit(rougher_feed, rougher, kinetics, specific_gravity, ccr)
        s_res = (
            float_unit(r_res.tailings, scavenger, kinetics, specific_gravity, ccr)
            if scavenger is not None
            else None
        )
        c_res = float_unit(r_res.concentrate, cleaner, kinetics, specific_gravity, ccr)

        new_recycle = c_res.tailings
        if s_res is not None:
            new_recycle = s_res.concentrate + new_recycle
        residual = new_recycle.max_abs_difference(recycle)
        recycle = new_recycle
        if residual <= tolerance_tph:
            break
    else:
        raise RuntimeError(f"회로가 {max_iterations} 회 안에 수렴하지 않음 (잔차 {residual:.3e})")

    return CircuitResult(
        new_feed=solids_only.with_water(fresh_water + filtrate_return_m3h),
        rougher=r_res,
        scavenger=s_res,
        cleaner=c_res,
        concentrate=c_res.concentrate,
        tailings=s_res.tailings if s_res is not None else r_res.tailings,
        recycle=recycle,
        iterations=iteration,
        residual_tph=residual,
        fresh_water_m3h=fresh_water
        + c_res.dilution_water_m3h
        + cleaner.wash_water_m3h
        + (scavenger.wash_water_m3h if scavenger is not None else 0.0)
        + rougher.wash_water_m3h,
        filtrate_return_m3h=filtrate_return_m3h,
    )
