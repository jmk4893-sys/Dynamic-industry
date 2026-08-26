"""탈수 계통 — 필터프레스 사이징.

농축조 언더플로를 받아 케이크로 뽑고 여액을 공정수로 돌려보낸다.
정광은 값이 나가는 산물이라 반드시 여과해 함수율을 낮춰야 하고,
미광은 물을 회수하고 건식 적치하기 위해 여과한다.

여과 면적은 두 조건 중 **큰 쪽**으로 정한다.

1. 처리 속도 — ``A = 건조 고체량 / 비여과속도``
2. 챔버 용적 — 한 사이클치 케이크가 챔버에 들어가야 한다

소규모 정광 라인에서는 2번이 아니라 **상용 최소 기종**이 지배하는 일이
흔하다. 그런 경우 연속 운전이 아니라 농축조에 모았다가 교대당 한 번씩
회분 운전하는 편이 합리적이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: 상용 여과판 한 변 길이 (mm).
STANDARD_PLATE_MM = (250, 320, 470, 630, 800, 1000, 1200, 1500)

#: 여과판 유효 면적 계수 — 가스켓·포트를 뺀 실효 비율.
PLATE_EFFECTIVE_FRACTION = 0.85


@dataclass(frozen=True)
class FilterPress:
    """필터프레스 1대.

    Attributes:
        dry_tph: 처리할 건조 고체량.
        cake_moisture: 케이크 함수율 (습량 기준 질량분율).
        plate_mm: 여과판 한 변 길이.
        chamber_depth_mm: 챔버 두께.
        chambers: 챔버 수.
        cycle_min: 1 사이클 소요 시간 (충전 + 압착 + 배출).
        governed_by: 크기를 결정한 기준.
    """

    tag: str
    duty: str
    dry_tph: float
    feed_solids_wt: float
    cake_moisture: float
    solids_sg: float
    plate_mm: float
    chamber_depth_mm: float
    chambers: int
    cycle_min: float
    specific_rate_kg_m2_h: float
    governed_by: str

    @property
    def area_per_chamber_m2(self) -> float:
        """챔버 1개의 유효 여과 면적 — 양면이므로 2배."""
        s = self.plate_mm / 1000.0
        return 2.0 * s * s * PLATE_EFFECTIVE_FRACTION

    @property
    def volume_per_chamber_m3(self) -> float:
        s = self.plate_mm / 1000.0
        return s * s * (self.chamber_depth_mm / 1000.0) * PLATE_EFFECTIVE_FRACTION

    @property
    def filter_area_m2(self) -> float:
        return self.chambers * self.area_per_chamber_m2

    @property
    def chamber_volume_m3(self) -> float:
        return self.chambers * self.volume_per_chamber_m3

    @property
    def cake_bulk_density_t_m3(self) -> float:
        """케이크 겉보기 밀도 — 고체와 잔류수의 체적 합."""
        w = self.cake_moisture
        return 1.0 / ((1.0 - w) / self.solids_sg + w)

    @property
    def cake_tph(self) -> float:
        """습 케이크 생산량."""
        return self.dry_tph / (1.0 - self.cake_moisture)

    @property
    def cycles_per_day(self) -> float:
        return 24.0 * 60.0 / self.cycle_min

    @property
    def dry_per_cycle_kg(self) -> float:
        return self.dry_tph * 1000.0 * (self.cycle_min / 60.0)

    @property
    def cake_volume_per_cycle_m3(self) -> float:
        return self.cake_tph * (self.cycle_min / 60.0) / self.cake_bulk_density_t_m3

    @property
    def chamber_utilisation(self) -> float:
        """챔버 충전율 — 1.0 에 가까울수록 기종이 알맞다."""
        return self.cake_volume_per_cycle_m3 / self.chamber_volume_m3

    @property
    def feed_water_tph(self) -> float:
        return self.dry_tph * (1.0 - self.feed_solids_wt) / self.feed_solids_wt

    @property
    def cake_water_tph(self) -> float:
        return self.cake_tph - self.dry_tph

    @property
    def filtrate_m3h(self) -> float:
        """공정수로 되돌리는 여액."""
        return max(0.0, self.feed_water_tph - self.cake_water_tph)

    @property
    def pump_rating_kw(self) -> float:
        """급광 펌프 — 격막 펌프 기준 개략값."""
        return 0.75 if self.filter_area_m2 < 5 else 2.2


def filter_press(
    tag: str,
    duty: str,
    dry_tph: float,
    feed_solids_wt: float,
    solids_sg: float,
    cake_moisture: float = 0.20,
    specific_rate_kg_m2_h: float = 18.0,
    cycle_min: float = 120.0,
    chamber_depth_mm: float = 30.0,
    min_chambers: int = 6,
    min_plate_mm: float = 470.0,
) -> FilterPress:
    """처리량과 사이클로부터 여과판 규격과 챔버 수를 정한다.

    Args:
        feed_solids_wt: 농축조 언더플로 고체 농도.
        cake_moisture: 목표 케이크 함수율 (습량 기준).
        specific_rate_kg_m2_h: 비여과속도. 미립 규산질 슬러리 기준 12~25.
        cycle_min: 1 사이클 시간.
        min_plate_mm: 상용 최소 기종의 여과판 크기.

    Raises:
        ValueError: 표준 계열로 감당할 수 없는 규모일 때.
    """
    if dry_tph <= 0:
        raise ValueError("건조 고체량은 양수여야 함")
    if not 0.0 < cake_moisture < 1.0:
        raise ValueError("cake_moisture 는 0~1 사이")
    if not 0.0 < feed_solids_wt < 1.0:
        raise ValueError("feed_solids_wt 는 0~1 사이")

    need_area = dry_tph * 1000.0 / specific_rate_kg_m2_h
    bulk = 1.0 / ((1.0 - cake_moisture) / solids_sg + cake_moisture)
    cake_per_cycle = dry_tph / (1.0 - cake_moisture) * (cycle_min / 60.0) / bulk

    for plate in STANDARD_PLATE_MM:
        if plate < min_plate_mm:
            continue
        s = plate / 1000.0
        a_ch = 2.0 * s * s * PLATE_EFFECTIVE_FRACTION
        v_ch = s * s * (chamber_depth_mm / 1000.0) * PLATE_EFFECTIVE_FRACTION
        by_rate = math.ceil(need_area / a_ch)
        by_volume = math.ceil(cake_per_cycle / v_ch)
        chambers = max(by_rate, by_volume, min_chambers)
        if chambers <= 80:                       # 상용 1대 한계
            if chambers == min_chambers and by_rate <= min_chambers and by_volume <= min_chambers:
                governed = "상용 최소 기종"
            elif by_volume >= by_rate:
                governed = "챔버 용적"
            else:
                governed = "여과 속도"
            return FilterPress(
                tag=tag, duty=duty, dry_tph=dry_tph, feed_solids_wt=feed_solids_wt,
                cake_moisture=cake_moisture, solids_sg=solids_sg, plate_mm=plate,
                chamber_depth_mm=chamber_depth_mm, chambers=chambers,
                cycle_min=cycle_min, specific_rate_kg_m2_h=specific_rate_kg_m2_h,
                governed_by=governed,
            )
    raise ValueError("표준 여과판 계열로 1대 처리 불가 — 복수 대수 검토 필요")
