"""급광(feed) 조성과 슬러리 물성 계산."""

from __future__ import annotations

from dataclasses import dataclass, field

WATER_DENSITY = 1000.0  # kg/m3, 20 degC


@dataclass(frozen=True)
class Component:
    """급광을 구성하는 성분 하나.

    Attributes:
        name: 성분명.
        mass_fraction: 건조 고체 기준 질량분율 (0~1).
        specific_gravity: 진비중 (물 = 1).
    """

    name: str
    mass_fraction: float
    specific_gravity: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.mass_fraction <= 1.0:
            raise ValueError(f"{self.name}: mass_fraction 은 0~1 이어야 함")
        if self.specific_gravity <= 0.0:
            raise ValueError(f"{self.name}: specific_gravity 는 양수여야 함")


@dataclass(frozen=True)
class FeedSpec:
    """부선기 급광 사양.

    Attributes:
        components: 건조 고체의 성분 구성.
        average_tph: 시간당 평균 처리량 (건조 고체 t/h).
        peak_tph: 시간당 최대 처리량 (건조 고체 t/h).
        solids_mass_fraction: 슬러리 중 고체 질량분율 (0~1).
        p80_micron: 급광 입도 P80.
    """

    components: tuple[Component, ...]
    average_tph: float
    peak_tph: float
    solids_mass_fraction: float
    p80_micron: float
    deslime_cut_micron: float = 10.0

    def __post_init__(self) -> None:
        total = sum(c.mass_fraction for c in self.components)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"성분 질량분율 합이 1.0 이 아님: {total:.6f}")
        if not 0.0 < self.solids_mass_fraction < 1.0:
            raise ValueError("solids_mass_fraction 은 0~1 사이여야 함")
        if self.peak_tph < self.average_tph:
            raise ValueError("peak_tph 는 average_tph 이상이어야 함")

    @property
    def solids_specific_gravity(self) -> float:
        """성분 비중의 체적가중(조화) 평균."""
        inverse = sum(c.mass_fraction / c.specific_gravity for c in self.components)
        return 1.0 / inverse

    def component_tph(self, tph: float) -> dict[str, float]:
        """주어진 처리량에서 성분별 건조 고체 유량 (t/h)."""
        return {c.name: tph * c.mass_fraction for c in self.components}

    def grade_ppm(self, name: str) -> float:
        """성분 품위를 g/t 로 반환."""
        for c in self.components:
            if c.name == name:
                return c.mass_fraction * 1_000_000.0
        raise KeyError(name)


@dataclass(frozen=True)
class PulpProperties:
    """특정 처리량에서의 슬러리 물성.

    Attributes:
        dry_tph: 건조 고체 처리량 (t/h).
        solids_sg: 고체 평균 비중.
        solids_mass_fraction: 고체 질량분율.
    """

    dry_tph: float
    solids_sg: float
    solids_mass_fraction: float

    @property
    def water_tph(self) -> float:
        """희석수를 포함한 슬러리 중 물 유량 (t/h)."""
        return self.dry_tph * (1.0 - self.solids_mass_fraction) / self.solids_mass_fraction

    @property
    def slurry_tph(self) -> float:
        return self.dry_tph + self.water_tph

    @property
    def pulp_specific_gravity(self) -> float:
        """슬러리 비중 (기포 제외)."""
        w = self.solids_mass_fraction
        return 1.0 / (w / self.solids_sg + (1.0 - w) / 1.0)

    @property
    def pulp_density_kg_m3(self) -> float:
        return self.pulp_specific_gravity * WATER_DENSITY

    @property
    def solids_volume_fraction(self) -> float:
        return self.solids_mass_fraction * self.pulp_specific_gravity / self.solids_sg

    @property
    def volumetric_flow_m3h(self) -> float:
        """슬러리 체적유량 (m3/h) — 셀 사이징의 기준값."""
        return self.dry_tph / self.solids_sg + self.water_tph / 1.0


def pulp_at(feed: FeedSpec, dry_tph: float) -> PulpProperties:
    """급광 사양과 처리량으로부터 슬러리 물성을 만든다."""
    return PulpProperties(
        dry_tph=dry_tph,
        solids_sg=feed.solids_specific_gravity,
        solids_mass_fraction=feed.solids_mass_fraction,
    )
