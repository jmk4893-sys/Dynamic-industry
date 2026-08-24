"""부선 반응속도 모델 및 단위 셀 물질수지.

완전혼합(perfectly mixed) 셀 1기의 회수율은

    R = (k * tau) / (1 + k * tau)

이지만, 실제 급광은 단일 속도상수로 부상하지 않는다. 같은 성분이라도
Ag 노출면이 큰 입자는 빠르게, 노출면이 작은 복합입자는 느리게 부상하고,
Ag 가 내부에 완전히 갇힌 입자는 아예 부상하지 않는다. 따라서 성분마다
**속부선(fast) / 지연부선(slow) / 비부선(non-floating)** 3분획으로 나눈
Kelsall 형 2속도 모델을 사용한다.

    R = phi_fast * k_f*tau/(1 + k_f*tau) + phi_slow * k_s*tau/(1 + k_s*tau)

**스캐빈저를 설계하려면 이 구분이 필수다.** 단일 속도상수 모델은 러퍼
미광에 남은 물질이 러퍼 급광과 같은 속도로 부상한다고 가정하므로
스캐빈저 회수율을 크게 과대평가한다. 실제로 러퍼 미광은 속부선 분획이
이미 빠져나간 뒤라 지연부선·비부선 위주이며, 스캐빈저는 그만큼 긴
체류시간을 필요로 한다.

맥석의 수분 동반 혼입(entrainment)은 부선속도가 아니라 수분회수율에
비례하므로 별도 계수(``entrainment_factor``)로 다룬다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 성분을 나누는 부선 분획의 이름 (순서 고정).
SPECIES = ("fast", "slow", "nonfloating")


def perfect_mixer_recovery(k_per_min: float, tau_min: float, r_max: float = 1.0) -> float:
    """완전혼합 셀 1기의 회수율 (0~1)."""
    if k_per_min < 0 or tau_min < 0:
        raise ValueError("k, tau 는 음수일 수 없음")
    if not 0.0 <= r_max <= 1.0:
        raise ValueError("r_max 는 0~1")
    kt = k_per_min * tau_min
    return r_max * kt / (1.0 + kt)


def n_cells_in_series_recovery(
    k_per_min: float, tau_total_min: float, n_cells: int, r_max: float = 1.0
) -> float:
    """동일 체적 셀 n 기 직렬의 회수율 — 셀 분할 이득 확인용."""
    if n_cells < 1:
        raise ValueError("n_cells >= 1")
    kt = k_per_min * (tau_total_min / n_cells)
    return r_max * (1.0 - (1.0 / (1.0 + kt)) ** n_cells)


@dataclass(frozen=True)
class ComponentKinetics:
    """성분 하나의 2속도 부선 거동.

    Attributes:
        name: 성분명 (:class:`~flotation_design.feed.Component` 와 일치).
        fast_fraction: 속부선 분획 비율.
        k_fast: 속부선 분획의 1차 속도상수 (1/min).
        slow_fraction: 지연부선 분획 비율.
        k_slow: 지연부선 분획의 1차 속도상수 (1/min).
        entrainment_factor: 수분회수율 대비 맥석 혼입 계수
            (degree of entrainment). 미립일수록 1.0 에 가까워진다.
    """

    name: str
    fast_fraction: float = 0.0
    k_fast: float = 0.0
    slow_fraction: float = 0.0
    k_slow: float = 0.0
    entrainment_factor: float = 0.0

    def __post_init__(self) -> None:
        if self.fast_fraction < 0 or self.slow_fraction < 0:
            raise ValueError(f"{self.name}: 분획 비율은 음수일 수 없음")
        if self.fast_fraction + self.slow_fraction > 1.0 + 1e-12:
            raise ValueError(f"{self.name}: 속부선 + 지연부선 분획이 1 을 초과")
        if self.k_fast < 0 or self.k_slow < 0:
            raise ValueError(f"{self.name}: 속도상수는 음수일 수 없음")
        if not 0.0 <= self.entrainment_factor <= 1.0:
            raise ValueError(f"{self.name}: entrainment_factor 는 0~1")

    @property
    def nonfloating_fraction(self) -> float:
        return 1.0 - self.fast_fraction - self.slow_fraction

    @property
    def r_max(self) -> float:
        """진부선으로 도달 가능한 회수율 상한."""
        return self.fast_fraction + self.slow_fraction

    @property
    def species_fractions(self) -> tuple[float, float, float]:
        """(속부선, 지연부선, 비부선) 분획 비율."""
        return (self.fast_fraction, self.slow_fraction, self.nonfloating_fraction)

    @property
    def species_rate_constants(self) -> tuple[float, float, float]:
        """(속부선, 지연부선, 비부선) 속도상수 — 비부선은 0."""
        return (self.k_fast, self.k_slow, 0.0)

    def true_flotation_recovery(self, tau_min: float) -> float:
        """진부선(entrainment 제외) 회수율."""
        return sum(
            frac * perfect_mixer_recovery(k, tau_min)
            for frac, k in zip(self.species_fractions, self.species_rate_constants)
        )

    def recovery(self, tau_min: float, water_recovery: float) -> float:
        """진부선 + 수분 동반 혼입을 합한 총 회수율."""
        true_float = self.true_flotation_recovery(tau_min)
        entrained = (1.0 - true_float) * self.entrainment_factor * water_recovery
        return min(1.0, true_float + entrained)


@dataclass(frozen=True)
class StreamAssay:
    """한 산물(정광/미광)의 유량과 품위."""

    name: str
    dry_tph: float
    component_tph: dict[str, float]

    def grade_fraction(self, component: str) -> float:
        if self.dry_tph <= 0:
            return 0.0
        return self.component_tph.get(component, 0.0) / self.dry_tph

    def grade_ppm(self, component: str) -> float:
        return self.grade_fraction(component) * 1_000_000.0


@dataclass(frozen=True)
class SeparationResult:
    """셀 1기 1회 통과 결과."""

    residence_min: float
    feed: StreamAssay
    concentrate: StreamAssay
    tailings: StreamAssay
    recovery: dict[str, float]
    water_recovery: float

    @property
    def mass_pull(self) -> float:
        """정광 질량 회수율 (mass pull)."""
        return self.concentrate.dry_tph / self.feed.dry_tph if self.feed.dry_tph else 0.0

    def enrichment_ratio(self, component: str) -> float:
        feed_grade = self.feed.grade_fraction(component)
        if feed_grade <= 0:
            return 0.0
        return self.concentrate.grade_fraction(component) / feed_grade

    def separation_efficiency(self, valuable: str) -> float:
        """Newton 선별효율 = R_valuable - R_gangue (0~1)."""
        r_v = self.recovery[valuable]
        feed_v = self.feed.component_tph[valuable]
        gangue_feed = self.feed.dry_tph - feed_v
        gangue_conc = self.concentrate.dry_tph - self.concentrate.component_tph[valuable]
        r_g = gangue_conc / gangue_feed if gangue_feed else 0.0
        return r_v - r_g


def simulate(
    feed_component_tph: dict[str, float],
    models: dict[str, ComponentKinetics],
    tau_min: float,
    water_recovery: float = 0.12,
) -> SeparationResult:
    """성분별 유량과 거동 모델로 셀 1기의 정광/미광 물질수지를 계산한다.

    급광의 분획 구성이 :attr:`ComponentKinetics.species_fractions` 그대로라고
    가정하므로 **신급광을 받는 러퍼에만** 유효하다. 러퍼 미광을 받는
    스캐빈저처럼 분획 구성이 이미 변형된 흐름에는
    :mod:`flotation_design.circuit` 의 흐름 추적 모델을 써야 한다.
    """
    missing = set(feed_component_tph) - set(models)
    if missing:
        raise KeyError(f"부선 거동 모델이 없는 성분: {sorted(missing)}")

    conc: dict[str, float] = {}
    tail: dict[str, float] = {}
    rec: dict[str, float] = {}
    for name, tph in feed_component_tph.items():
        r = models[name].recovery(tau_min, water_recovery)
        rec[name] = r
        conc[name] = tph * r
        tail[name] = tph * (1.0 - r)

    feed_total = sum(feed_component_tph.values())
    return SeparationResult(
        residence_min=tau_min,
        feed=StreamAssay("Feed", feed_total, dict(feed_component_tph)),
        concentrate=StreamAssay("Concentrate", sum(conc.values()), conc),
        tailings=StreamAssay("Tailings", sum(tail.values()), tail),
        recovery=rec,
        water_recovery=water_recovery,
    )
