"""전처리 플랜트 배선 — 분전반 위치, 트레이 경로, 실제 케이블 길이.

길이의 뼈대는 전부 배치 모델에서 파생한다. 존 좌표가 바뀌면 여기와 도면의
케이블 스케줄이 같이 틀어지고, `tests/test_pv_preprocess.py` 가 그것을 잡는다.

경로 규약 (트레이 1계통, 통로 상부):

* 주 분전반 MDB-101 은 통로 외곽벽(y=8,300)에 벽부한다. 반깊이 300 이라
  통로 유효폭이 1,200 − 300 = 900 으로 보행 최소폭을 그대로 지킨다.
* 주 케이블 트레이는 통로 상부 H=2,600, y=7,700 을 X 방향으로 관통한다.
* 셀 분전반 LP-xx 는 각 존 통로측 전면(y=7,000)에 서고, 트레이에서 수직
  드롭으로 내려온다.
* 길이 = 수평 맨해튼 거리(|Δx| + |Δy|) + 수직 상승·하강 + 성단 여유,
  전체에 시공 여유 10 % 를 얹는다. 신뢰할 수 없는 자리는 만들지 않는다 —
  모든 항이 아래 상수로 명시된다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import electrical
from .layout import build_zones

#: 주 분전반 MDB-101 의 벽부 위치 (플랜트 좌표 mm). X 는 피더 수요(kW) 가중
#: 부하중심(demand_center_x_mm())을 500 단위로 반올림한 값이다.
#:
#: REV.23 에서 유리제거셀(IR 뱅크 175 kW)이 하류 끝에 들어오며 부하중심이
#: 20,106 → 42,572 로 22.5 m 내려갔다. 반을 그대로 두면 전체 구리량이 늘고
#: 최대 부하가 가장 먼 자리에 놓인다 — 규칙대로 반을 부하중심으로 옮긴다.
MDB_POSITION_MM = (42_500, 8_150)

#: 주 트레이 높이와 Y 위치 (mm)
TRAY_HEIGHT_MM = 2_600
TRAY_Y_MM = 7_700

#: 셀 분전반 LP 의 통로측 전면 Y (mm), 상단 높이 (mm)
LP_Y_MM = 7_000
LP_TOP_MM = 1_900

#: MDB 인출 높이 (mm) — 상부 인출
MDB_TOP_MM = 1_900

#: 성단(단말) 여유 — 양단 각 1.5 m
TERMINATION_MM = 3_000

#: 시공 여유율
SLACK = 1.10


@dataclass(frozen=True)
class Cable:
    """케이블 스케줄 한 행."""

    feeder: str            # F1…F8 또는 제어 계통 태그
    panel: str
    x_mm: int              # 부하측 분전반의 플랜트 X
    length_m: float
    kind: str              # '전력' | '제어'


def _zone_center(key: str) -> int:
    zone = next(z for z in build_zones() if z.key == key)
    return (zone.x0_mm + zone.x1_mm) // 2


def lp_positions_mm() -> dict[str, int]:
    """셀 분전반의 플랜트 X. 존 중심에 세우되, 존이 없는 반은 실제 기기 위치를 쓴다."""
    centers = {
        "LP-AFU": _zone_center("afu"),
        "LP-RB": _zone_center("robot"),
        "LP-JBR": _zone_center("jbr"),
        "LP-AFR": _zone_center("afr"),
        "LP-GLASS": _zone_center("post"),
        "LP-GBR": _zone_center("buffer"),
    }
    # DX-601 은 post 존 안 국소집진(존 로컬 x +125 부근), 제어반 LP-CTRL 은
    # JBR 의 PLC·서보 제어반(3D 실측 x 17,065…17,785) 옆이다.
    post = next(z for z in build_zones() if z.key == "post")
    centers["LP-DX"] = post.x0_mm + 4_575
    centers["LP-CTRL"] = 17_400
    # GRM-401 의 반 4면은 자기 존 안에서 부하 옆에 선다. IR 두 뱅크는 5단 랙
    # (존 로컬 X −3,800…−500) 앞, 기구반은 탠덤 앞, 배기반은 슈레더 쪽이다.
    grm = next(z for z in build_zones() if z.key == "grm")
    grm_center = (grm.x0_mm + grm.x1_mm) // 2
    centers["LP-GRM-IRA"] = grm_center - 2_150
    centers["LP-GRM-IRB"] = grm_center - 2_150
    centers["LP-GRM-MEC"] = grm_center + 1_200
    centers["LP-GRM-EXH"] = grm_center + 4_200
    return centers


def cable_length_mm(load_x_mm: int) -> int:
    """MDB → 부하측 분전반 전력 케이블 길이 (mm).

    수평: |Δx| + (MDB y 8,150 → 트레이 y 7,700) + (트레이 → LP y 7,000)
    수직: MDB 상단 1,900 → 트레이 2,600 상승 + 트레이 → LP 상단 1,900 하강
    """
    horizontal = abs(MDB_POSITION_MM[0] - load_x_mm) \
        + (MDB_POSITION_MM[1] - TRAY_Y_MM) + (TRAY_Y_MM - LP_Y_MM)
    vertical = (TRAY_HEIGHT_MM - MDB_TOP_MM) + (TRAY_HEIGHT_MM - LP_TOP_MM)
    return round((horizontal + vertical) * SLACK) + TERMINATION_MM


def power_cables() -> list[Cable]:
    """F1…F8 전력 케이블 스케줄 — 피더 순서 그대로."""
    positions = lp_positions_mm()
    rows = []
    for feeder in electrical.FEEDERS:
        x = positions[feeder.panel]
        rows.append(Cable(feeder.tag, feeder.panel, x,
                          round(cable_length_mm(x) / 100) / 10, "전력"))
    return rows


def control_segments() -> list[Cable]:
    """제어 네트워크 구간 — EtherCAT 데이지체인과 안전 I/O 링.

    LP-CTRL(17,400)에서 상류로 한 팔, 하류로 한 팔을 뻗는 데이지체인이다.
    구간 길이는 인접 분전반 사이 트레이 경로로 잡는다 (수평 |Δx| + 드롭 2×700).
    """
    positions = lp_positions_mm()
    chain = ["LP-AFU", "LP-RB", "LP-JBR", "LP-CTRL", "LP-AFR", "LP-GLASS", "LP-DX", "LP-GBR",
             # REV.23: 유리제거셀 4면을 X 순서대로 체인 끝에 잇는다.
             "LP-GRM-IRA", "LP-GRM-IRB", "LP-GRM-MEC", "LP-GRM-EXH"]
    rows = []
    for a, b in zip(chain, chain[1:]):
        run = abs(positions[a] - positions[b]) + 2 * (TRAY_HEIGHT_MM - LP_TOP_MM)
        rows.append(Cable(f"{a}→{b}", b, positions[b],
                          round((run * SLACK + TERMINATION_MM) / 100) / 10, "제어"))
    return rows


def demand_center_x_mm() -> int:
    """피더 수요(kW) 가중 부하중심 X — MDB 위치의 근거."""
    positions = lp_positions_mm()
    weight = sum(f.demand_kw for f in electrical.FEEDERS)
    center = sum(f.demand_kw * positions[f.panel] for f in electrical.FEEDERS) / weight
    return round(center)


def incoming_cable_m() -> float:
    """공장 인입점(플랜트 x=0, 통로 외곽 코너 가정) → MDB 인입 케이블 길이 (m)."""
    run = MDB_POSITION_MM[0] + (TRAY_HEIGHT_MM - MDB_TOP_MM) * 2
    return round((run * SLACK + TERMINATION_MM) / 100) / 10


def total_power_cable_m() -> float:
    return round(sum(c.length_m for c in power_cables()), 1)


def aisle_clear_width_mm() -> int:
    """분전반 벽부 후 통로 유효폭 — 보행 최소 900 을 지켜야 한다."""
    return 1_200 - 300
