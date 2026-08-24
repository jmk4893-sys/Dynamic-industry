"""약제 계통: 투입량(g/t) → 시간당 소요량 및 정량펌프 유량."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reagent:
    """약제 사양.

    Attributes:
        name: 약제명.
        role: 역할 (pH 조정제, 분산/억제제, 황화제, 포수제, 기포제).
        dose_g_per_t: 건조 고체 t 당 유효성분 투입량.
        solution_strength: 조제 용액의 유효성분 질량분율 (원액 사용 시 1.0).
        solution_sg: 조제 용액 비중.
        addition_point: 투입 지점.
        note: 관리 포인트.
    """

    name: str
    role: str
    dose_g_per_t: float
    solution_strength: float
    solution_sg: float
    addition_point: str
    note: str = ""

    def __post_init__(self) -> None:
        if not 0.0 < self.solution_strength <= 1.0:
            raise ValueError(f"{self.name}: solution_strength 는 0 초과 1 이하")
        if self.solution_sg <= 0.0:
            raise ValueError(f"{self.name}: solution_sg 는 양수")


@dataclass(frozen=True)
class ReagentDose:
    """특정 처리량에서의 약제 소요량."""

    reagent: Reagent
    dry_tph: float

    @property
    def active_kg_h(self) -> float:
        """유효성분 소요량 (kg/h)."""
        return self.reagent.dose_g_per_t * self.dry_tph / 1000.0

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


def reagent_schedule(reagents: tuple[Reagent, ...], dry_tph: float) -> tuple[ReagentDose, ...]:
    """처리량에 대한 약제 투입 스케줄."""
    return tuple(ReagentDose(r, dry_tph) for r in reagents)
