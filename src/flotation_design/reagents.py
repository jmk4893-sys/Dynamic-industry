"""약제 계통: 투입량(g/t) → 시간당 소요량 및 정량펌프 유량."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reagent:
    """약제 사양.

    투입 기준(``basis``)이 둘이다. 포수제·촉진제는 건조 고체 t 당 g 으로
    투입하지만, 기포제는 **물 기준 농도(ppm)** 로 관리한다. 기포 안정성은
    수상 농도로 결정되므로, 고체 농도가 달라지면 g/t 환산값도 달라진다.

    Attributes:
        name: 약제명.
        role: 역할.
        dose: 투입량. basis 가 "solids" 면 g/t-건조고체, "water" 면 g/m3-물(=ppm).
        solution_strength: 조제 용액의 유효성분 질량분율 (원액 사용 시 1.0).
        solution_sg: 조제 용액 비중.
        addition_point: 투입 지점.
        note: 관리 포인트.
    """

    name: str
    role: str
    dose: float
    solution_strength: float
    solution_sg: float
    addition_point: str
    basis: str = "solids"
    note: str = ""

    def __post_init__(self) -> None:
        if not 0.0 < self.solution_strength <= 1.0:
            raise ValueError(f"{self.name}: solution_strength 는 0 초과 1 이하")
        if self.solution_sg <= 0.0:
            raise ValueError(f"{self.name}: solution_sg 는 양수")
        if self.basis not in ("solids", "water"):
            raise ValueError(f"{self.name}: basis 는 'solids' 또는 'water'")

    @property
    def dose_unit(self) -> str:
        return "g/t" if self.basis == "solids" else "ppm(물)"


@dataclass(frozen=True)
class ReagentDose:
    """특정 처리량에서의 약제 소요량.

    Attributes:
        dry_tph: 건조 고체 처리량.
        water_m3h: 슬러리 중 물 유량 — 물 기준(ppm) 약제 환산에 쓴다.
    """

    reagent: Reagent
    dry_tph: float
    water_m3h: float = 0.0

    @property
    def active_kg_h(self) -> float:
        """유효성분 소요량 (kg/h)."""
        if self.reagent.basis == "water":
            return self.reagent.dose * self.water_m3h / 1000.0
        return self.reagent.dose * self.dry_tph / 1000.0

    @property
    def equivalent_g_per_t(self) -> float:
        """비교용 — 건조 고체 t 당 환산 투입량."""
        if self.dry_tph <= 0:
            return 0.0
        return self.active_kg_h * 1000.0 / self.dry_tph

    @property
    def solution_l_h(self) -> float:
        """조제 용액 기준 정량펌프 유량 (L/h)."""
        return self.active_kg_h / (self.reagent.solution_strength * self.reagent.solution_sg)

    @property
    def active_kg_per_day(self) -> float:
        return self.active_kg_h * 24.0

    def pump_rating_l_h(self, turndown_margin: float = 2.0, minimum_l_h: float = 1.0) -> float:
        """정량펌프 최대 토출량 선정값 (L/h).

        상용 정량펌프의 최소 토출량과 제어 분해능을 고려해 하한을 둔다.
        """
        return max(self.solution_l_h * turndown_margin, minimum_l_h)


def reagent_schedule(
    reagents: tuple[Reagent, ...], dry_tph: float, water_m3h: float = 0.0
) -> tuple[ReagentDose, ...]:
    """처리량에 대한 약제 투입 스케줄."""
    return tuple(ReagentDose(r, dry_tph, water_m3h) for r in reagents)
