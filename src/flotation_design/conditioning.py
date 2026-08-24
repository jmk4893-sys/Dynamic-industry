"""조건조(conditioner) 사이징 — 부선 전 약제 접촉조."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .sizing import select_motor_kw


@dataclass(frozen=True)
class ConditionerDesign:
    """원통형 조건조 1기.

    Attributes:
        tag: 기기 번호.
        duty: 투입 약제 / 목적.
        residence_min: 최대 처리량 기준 체류시간.
        working_volume_m3: 유효(운전 액면) 체적.
        tank_volume_m3: 여유고 포함 전체 체적.
        diameter_m / height_m: 내부 치수.
        agitator_kw: 교반기 모터 용량.
    """

    tag: str
    duty: str
    residence_min: float
    working_volume_m3: float
    tank_volume_m3: float
    diameter_m: float
    height_m: float
    agitator_kw: float
    specific_power_kw_m3: float


def conditioner_train(
    stages: tuple[tuple[str, str, float], ...],
    volumetric_flow_m3h: float,
    freeboard_ratio: float = 0.15,
    height_to_diameter: float = 1.2,
    mixing_intensity_kw_m3: float = 1.0,
    round_to_m3: float = 0.05,
) -> tuple[ConditionerDesign, ...]:
    """(tag, duty, 체류시간[min]) 목록으로 조건조 열(train)을 산정한다.

    슬러리를 부유 상태로 유지하는 데 필요한 교반 강도는 미립 슬러리 기준
    약 0.8~1.2 kW/m3 이며, 여기서는 ``mixing_intensity_kw_m3`` 로 준다.
    """
    out = []
    for tag, duty, minutes in stages:
        working = volumetric_flow_m3h * minutes / 60.0
        total = math.ceil(working * (1.0 + freeboard_ratio) / round_to_m3) * round_to_m3
        diameter = (4.0 * total / (math.pi * height_to_diameter)) ** (1.0 / 3.0)
        out.append(
            ConditionerDesign(
                tag=tag,
                duty=duty,
                residence_min=minutes,
                working_volume_m3=working,
                tank_volume_m3=total,
                diameter_m=diameter,
                height_m=diameter * height_to_diameter,
                agitator_kw=select_motor_kw(working * mixing_intensity_kw_m3 * 1000.0, 1.25),
                specific_power_kw_m3=mixing_intensity_kw_m3,
            )
        )
    return tuple(out)
