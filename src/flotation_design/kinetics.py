"""1차 반응속도 기반 단단 부선 성능 예측 및 물질수지.

완전혼합(perfectly mixed) 셀 1기에 대한 고전적 회수율 식

    R = R_max * (k * tau) / (1 + k * tau)

을 사용한다. 단단(1-stage) 구성에서는 체류시간을 늘려도 회수율이
``R_max`` 에 점근할 뿐이라는 점이 이 식에서 바로 드러나며, 이것이
스캐빈저 1기 추가 여부를 판단하는 근거가 된다.

맥동 없이 물에 딸려 올라가는 맥석(entrainment)은 부선속도가 아니라
수분회수율에 비례하므로 별도 모델(``entrainment_factor``)로 다룬다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
    """동일 체적 셀 n 기 직렬의 회수율 — 단단 대비 이득 확인용."""
    if n_cells < 1:
        raise ValueError("n_cells >= 1")
    kt = k_per_min * (tau_total_min / n_cells)
    return r_max * (1.0 - (1.0 / (1.0 + kt)) ** n_cells)


@dataclass(frozen=True)
class FloatComponentModel:
    """성분별 부선 거동 모델.

    Attributes:
        name: 성분명 (:class:`~flotation_design.feed.Component` 와 일치).
        k_per_min: 1차 부선속도상수. 0 이면 진부선(true flotation) 없음.
        r_max: 최대 회수 가능 분율 — Ag 의 경우 Si 와의 결합/미해리로
            인한 상한을 의미한다.
        entrainment_factor: 수분회수율 대비 맥석 혼입 계수 (degree of
            entrainment). 미립일수록 1.0 에 가까워진다.
    """

    name: str
    k_per_min: float
    r_max: float
    entrainment_factor: float = 0.0

    def recovery(self, tau_min: float, water_recovery: float) -> float:
        true_float = perfect_mixer_recovery(self.k_per_min, tau_min, self.r_max)
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
    """단단 부선 1회 통과 결과."""

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
    models: dict[str, FloatComponentModel],
    tau_min: float,
    water_recovery: float = 0.12,
) -> SeparationResult:
    """성분별 유량과 거동 모델로 정광/미광 물질수지를 계산한다."""
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
