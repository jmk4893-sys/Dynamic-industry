"""태양광 패널 전처리 통합 플랜트 — 배치의 단일 출처.

설계도(`docs/drawings/pv-preprocess-plant.html`)는 셀 외형·존 배치를 문자열로 들고 있다.
같은 값을 여기서도 정의하고 `tests/test_pv_preprocess.py` 가 둘을 대조하므로,
한쪽만 고치면 테스트가 실패한다.
"""

from . import electrical, vision
from .layout import (
    AISLE_WIDTH_MM,
    MACHINE_BAND_Y_MM,
    STATIONS,
    ZONE_SEED,
    Station,
    Zone,
    build_zones,
    plant_envelope_mm,
)

__all__ = [
    "AISLE_WIDTH_MM",
    "electrical",
    "vision",
    "MACHINE_BAND_Y_MM",
    "STATIONS",
    "ZONE_SEED",
    "Station",
    "Zone",
    "build_zones",
    "plant_envelope_mm",
]
