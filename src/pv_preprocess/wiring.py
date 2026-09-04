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

from . import air, crane, electrical, smart
from .layout import build_zones, plant_envelope_mm

#: 주 분전반 MDB-101 의 벽부 위치 (플랜트 좌표 mm). X 는 피더 수요(kW) 가중
#: 부하중심(demand_center_x_mm())을 500 단위로 반올림한 값이다.
#:
#: REV.23 에서 유리제거셀(IR 뱅크 175 kW)이 하류 끝에 들어오며 부하중심이
#: 20,106 → 42,572 로 22.5 m 내려갔다. 반을 그대로 두면 전체 구리량이 늘고
#: 최대 부하가 가장 먼 자리에 놓인다 — 규칙대로 반을 부하중심으로 옮긴다.
#:
#: REV.28 에서 500 옮겼다. 크레인 피더(F15)는 수요가 1.34 kW 뿐이지만 급전점이
#: 주행 중앙 29,400 이라 부하중심을 42,299 → 42,197 로 끌어올렸고, 그 81 mm 가
#: 하필 500 단위 반올림 경계(42,250)를 넘었다. 규칙이 값을 정하지 값이 규칙을
#: 정하는 게 아니라서, 작은 부하가 경계를 넘기면 반도 따라 움직인다.
#: 42,000 은 이 되먹임(반 위치 → 랙실 위치 → LP-IT → 부하중심)의 고정점이다.
#:
#: REV.34 에서 **다시 42,500 으로 돌아왔다.** 압축공기 기계실(LP-AIR)이 시설
#: 블록 끝 50,450 에 서면서 수요 4.25 kW 를 하류에 얹었고, 그것이 크레인이
#: 상류로 끌어올렸던 102 mm 를 도로 끌어내렸다. 규칙은 한 번도 안 바뀌었고
#: 값만 왕복했다 — 부하가 양쪽에서 붙으면 원래 이렇게 된다.
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
    # 두 IR 반은 랙 앞에 나란히 선다 — 같은 X 에 겹쳐 세울 수는 없다.
    centers["LP-GRM-IRA"] = grm_center - 2_750
    centers["LP-GRM-IRB"] = grm_center - 1_550
    centers["LP-GRM-MEC"] = grm_center + 1_200
    centers["LP-GRM-EXH"] = grm_center + 4_200
    # REV.25 스마트 팩토리. LP-IT 는 자기가 먹이는 랙실 안에 서고, LP-INST 는
    # 존마다 흩어진 엣지 캐비닛의 부하중심에 선다 — MDB 를 부하중심에 두는
    # 규칙과 같은 규칙을 한 단 아래에 적용한 것이다.
    centers["LP-IT"] = server_room_center_x_mm()
    centers["LP-INST"] = edge_cabinet_center_x_mm()
    # REV.28 천장크레인. 페스툰 급전점은 주행거더 **중앙**이다 — 이유는
    # crane_feed_x_mm() 에 적었다.
    centers["LP-CRANE"] = crane_feed_x_mm()
    # REV.34 압축공기. 기계실은 랙실·관제실과 같은 줄에 이어 붙는다 —
    # 셋 다 공정 존이 아니라 구획실이고, 한 줄로 모아야 배선과 벽이 짧다.
    centers["LP-AIR"] = air_room_center_x_mm()
    return centers


def air_room_center_x_mm() -> int:
    """CMP-701 기계실의 부하중심 X (mm).

    시설 블록(랙실·관제실) 끝에 이어 붙인다. 시설이 MDB 를 따라 움직이면
    기계실도 같이 움직인다 — 한 줄이라는 사실이 값보다 먼저다.
    """
    span = facility_span_mm()
    return span[1] + FACILITY_PARTITION_MM + air.room_mm()[0] // 2


def crane_runway_overhang_mm() -> int:
    """주행거더가 플랜트 전장 밖으로 나가는 길이 (편측 mm).

    끝단 설비 위까지 후크가 가려면 엔드트럭이 설비보다 밖에 서야 한다.
    주행 접근여유(BRIDGE_APPROACH_MM)를 실제로 덮는지는 시험이 본다.
    """
    return (crane.RUNWAY_MM - plant_envelope_mm()[0]) // 2


def crane_feed_x_mm() -> int:
    """CRN-901 페스툰 급전점의 플랜트 X (mm) — 주행거더 중앙.

    한쪽 끝에서 먹이면 트레일링 케이블이 주행 전장 60.8 m 를 끝까지
    따라가야 하고, 주행 도체의 전압강하도 그 길이를 그대로 받는다.
    중앙 급전이면 둘 다 절반이 된다. 주행거더는 플랜트 전장에 양끝 같은
    오버행을 두고 걸리므로 그 중앙은 플랜트 중앙과 같다.
    """
    return plant_envelope_mm()[0] // 2


#: 시설(랙실·관제실)을 MDB-101 옆에 붙일 때의 이격 (mm).
#: MDB 반폭 500 + 반과 반 사이 이격 200.
FACILITY_GAP_FROM_MDB_MM = 700

#: 랙실과 관제실 사이 칸막이벽 두께 (mm).
FACILITY_PARTITION_MM = 200


def facility_x0_mm() -> int:
    """시설 구획의 시작 X (mm) — MDB 하류쪽 옆."""
    return MDB_POSITION_MM[0] + FACILITY_GAP_FROM_MDB_MM


def server_room_center_x_mm() -> int:
    return facility_x0_mm() + smart.server_room_mm()[0] // 2


def control_room_center_x_mm() -> int:
    return (facility_x0_mm() + smart.server_room_mm()[0]
            + FACILITY_PARTITION_MM + smart.control_room_mm()[0] // 2)


def facility_span_mm() -> tuple[int, int]:
    """시설 구획이 차지하는 X 구간 (시작, 끝 mm)."""
    width = (smart.server_room_mm()[0] + FACILITY_PARTITION_MM
             + smart.control_room_mm()[0])
    return (facility_x0_mm(), facility_x0_mm() + width)


def edge_cabinet_center_x_mm(centers: dict[str, int] | None = None) -> int:
    """엣지 캐비닛의 부하중심 X (mm) — 캐비닛은 존마다 한 면씩 같은 용량이다.

    `centers` 를 받는 것은 시험을 위해서다. 지금 배치에서 이 값은 마침
    25,000 이라, 함수를 `return 25_000` 으로 바꿔도 현재 데이터로는 아무
    테스트가 실패하지 않는다 — 다른 배치를 넣어 실제로 따라오는지 본다.
    """
    zones = centers if centers is not None else {
        zone.key: (zone.x0_mm + zone.x1_mm) // 2 for zone in build_zones()}
    keys = [key for key in smart.edge_zones() if key in zones]
    return round(sum(zones[key] for key in keys) / len(keys) / 500) * 500


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
    # REV.25 정정 — LP-INST·LP-IT 는 **여기 없다.**
    #
    # 처음엔 스마트 팩토리 반 2면을 이 체인 끝에 붙였다. 틀렸다. 이 체인은
    # EtherCAT 모션·안전 버스이고, 거기에 붙는다는 것은 히스토리안 수집
    # 트래픽을 실시간 버스에 얹는다는 뜻이다. 사이클 지터가 그대로 축 추종
    # 오차가 된다 — AI-04 가 재려는 바로 그 신호를 계측 자신이 흔든다.
    #
    # 엣지 캐비닛과 랙실은 별도 이더넷 백본 링(SM-1012)에 물린다. 두 망이
    # 만나는 곳은 OT/IT 경계 방화벽 한 곳뿐이다.
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


#: 전기실(국소 변압기반) 저압반 중심 → MDB-101 중심 거리 (mm).
#: 전기실을 세울 때는 MDB 옆 통로 외곽벽에 붙인다.
SUBSTATION_TO_MDB_MM = 2_000

#: **부지 저압 배전반 → MDB-101 실거리 (mm).**
#: REV.24 에서 부지 1,200 kW 인입에 물리기로 하면서 생긴 유일한 미지수다.
#: 부지 배전반이 어디 있는지는 발주처 실측 사항이라 **여기서 지어내지 않는다**.
#:
#: REV.29 에서 발주처가 **그 배전반이 이미 서 있다**고 확인해 줬다. 있다는
#: 것은 확인됐지만 **어디에** 있는지는 여전히 실측 사항이라, 이 값은 그대로
#: None 이다 — 존재를 안다고 거리를 아는 것이 아니다.
#: None 이면 도면도 길이를 적지 않고 한계 거리(240 mm² 기준 162 m)만 적는다.
#: 실측이 오면 이 한 줄만 채우면 케이블 스케줄과 도면이 같이 따라온다.
SITE_BOARD_TO_MDB_MM: int | None = None

#: **부지 배전반까지의 거리가 저압 분기 한계 안인가.** 발주처 확인 — 그렇다.
#:
#: 거리와 판정은 다른 것이다. 발주처가 준 것은 "151 m 이내" 라는 **판정**이지
#: 몇 m 인지가 아니다. 판정만으로 정해지는 것과 거리가 있어야 정해지는 것을
#: 갈라 둔다 —
#:
#:   * 판정이 정하는 것 : 저압 분기로 간다 · 변압기 불요 · 전기실 불요.
#:     이것들이 이제 **확정**이다. REV.32 까지는 계획이었다.
#:   * 거리가 정하는 것 : 분기 주회로 실길이. 여전히 모른다.
#:
#: 한계값(151 m)을 실거리 자리에 적으면 케이블 물량이 상한으로 부풀고, 그
#: 부풀린 값이 "확정" 얼굴을 하고 발주로 간다. 그래서 안 적는다.
SITE_BOARD_WITHIN_LV_LIMIT = True


def incoming_cable_m() -> float | None:
    """분기 주회로 길이 (m). 모르면 None — 지어내지 않는다.

    * 저압 분기: 부지 배전반 → MDB. 실거리를 받아야 산정된다.
    * 고압 분기·자체 수전: 전기실 변압기 2차 → MDB (파생값).
    """
    if electrical.taps_existing_service() and electrical.TAP_AT_LOW_VOLTAGE:
        if SITE_BOARD_TO_MDB_MM is None:
            return None
        run = SITE_BOARD_TO_MDB_MM + (TRAY_HEIGHT_MM - MDB_TOP_MM) * 2
    else:
        run = SUBSTATION_TO_MDB_MM + (TRAY_HEIGHT_MM - MDB_TOP_MM) * 2
    return round((run * SLACK + TERMINATION_MM) / 100) / 10


def incoming_length_is_known() -> bool:
    """분기 주회로 길이가 확정됐는가 — 아니면 도면에 한계 거리만 적는다."""
    return incoming_cable_m() is not None


def lv_tap_is_confirmed(within: bool | None = None) -> bool:
    """저압 분기가 **확정**인가.

    거리를 몰라도 "한계 안" 이라는 판정만 있으면 방식은 정해진다 —
    변압기도 전기실도 세우지 않는다는 뜻이다. 인자를 열어 둔 것은,
    지금 True 라서 이 분기가 죽어도 아무도 모르는 일을 막기 위해서다.
    """
    ok = SITE_BOARD_WITHIN_LV_LIMIT if within is None else within
    return bool(ok) and electrical.taps_existing_service() \
        and electrical.TAP_AT_LOW_VOLTAGE


def total_power_cable_m() -> float:
    return round(sum(c.length_m for c in power_cables()), 1)


def aisle_clear_width_mm() -> int:
    """분전반 벽부 후 통로 유효폭 — 보행 최소 900 을 지켜야 한다."""
    return 1_200 - 300
