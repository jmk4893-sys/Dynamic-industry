"""전처리 플랜트 열수지와 냉각 계통 설계.

냉각이 없던 두 곳 — HPU-101/601 유압유와 셀 분전반 내 드라이브 — 에
냉각기를 사이징해 붙이고, 공정 전체의 발열이 어디로 빠지는지(열수지)를
한 표로 만든다. 규칙 출처는 업계 관례다.

* 유압 발열 = 설치 입력의 30 % (시스템 효율 70 % 전제) — 실측 전 표준 관례.
* 드라이브 반내 발열 = 전동기 정격의 5 % (서보·VFD 효율 95 %).
* 냉각기 용량 = 발열 × 1.25 (필터 오염·주위온도 여유 25 %).
* 반내 온도 목표 40 °C 이하 — 발열 0.4 kW 이상이면 필터팬 대신 열교환기.
* 실내 잔여 발열은 전체 환기로 처리: V[m³/h] = Q[kW]·3600 / (1.2·1.005·ΔT).

`docs/drawings/pv-preprocess-plant.html` 의 THERMAL_* 리터럴과 냉각기
부품(AFU-OC-101, AFR-OC-601)이 이 계산과 어긋나면 테스트가 잡는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import electrical, handoff, servos

#: 유압 입력 대비 발열 비율 — 시스템 효율 70 % 관례
HPU_LOSS_RATIO = 0.30

#: 드라이브(서보·VFD) 반내 발열 비율 — 효율 95 %
DRIVE_LOSS_RATIO = 0.05

#: 냉각기 용량 여유율
COOLER_MARGIN = 1.25

#: 반내 발열이 이 값을 넘으면 필터팬으로는 부족 — 열교환기·판넬쿨러
CABINET_FAN_LIMIT_KW = 0.4

#: 전체 환기 설계 온도 상승 (실내 − 외기)
ROOM_DELTA_T_C = 5.0


@dataclass(frozen=True)
class HeatSource:
    tag: str
    equipment: str
    loss_kw: float      # 연속 환산 발열
    sink: str           # '유압유' | '반내' | '배기' | '실내'
    cooling: str        # 냉각 수단
    cooler_tag: str     # 냉각기 부품번호 ('—' 는 전용 냉각기 없음)
    cooler_kw: float    # 냉각기 정격 방열 (0 은 전용 냉각기 없음)


def hpu_loss_kw(input_kw: float) -> float:
    return round(input_kw * HPU_LOSS_RATIO, 2)


def cooler_required_kw(loss_kw: float) -> float:
    return round(loss_kw * COOLER_MARGIN, 2)


def cabinet_loss_kw(panel: str) -> float:
    """분전반 내 드라이브 발열 — 그 반이 급전하는 전동기 정격의 5 %."""
    motion = servos.motion_kw_by_panel().get(panel, 0.0)
    return round(motion * DRIVE_LOSS_RATIO, 2)


def ir_demand_kw() -> float:
    """유리제거셀 IR 뱅크의 수요 전력 (kW) — 발열 배분의 분모."""
    return round(sum(f.demand_kw for f in electrical.FEEDERS
                     if f.panel.startswith("LP-GRM-IR")), 2)


def ir_useful_kw() -> float:
    """패널로 들어가는 몫 — 박리 후 유리·셀의 현열로 나온다."""
    return round(ir_demand_kw() * handoff.HEAT_EFFICIENCY_PCT / 100.0, 2)


def ir_enclosure_loss_kw() -> float:
    """인클로저로 빠지는 몫 — IR 배기가 받는다."""
    return round(ir_demand_kw() - ir_useful_kw(), 2)


def heat_sources() -> tuple[HeatSource, ...]:
    """주요 발열원과 냉각 수단. 표에 없는 잔여 발열은 실내로 가 환기가 받는다.

    JBR 의 7축 드라이브는 셀 옆 자체 제어반(EtherCAT 7축 서보 반)에 살므로
    TH-CAB-JBR 로 따로 세고, TH-CAB-LP 합계에서는 LP-JBR 을 뺀다 — 중복 금지.
    """
    lp_sum = round(sum(kw for panel, kw in cabinet_loads().items()
                       if panel != "LP-JBR"), 2)
    jbr_cab = round(cabinet_loss_kw("LP-JBR") + 0.35, 2)  # 드라이브 + PLC·비전 0.35
    return (
        HeatSource("TH-HPU1", "HPU-101 유압 (3.7 kW 입력)", hpu_loss_kw(3.7),
                   "유압유", "공랭 오일쿨러 + 60 L 증량 탱크", "AFU-OC-101", 1.5),
        HeatSource("TH-HPU6", "HPU-601 유압 (7.5 kW 입력)", hpu_loss_kw(7.5),
                   "유압유", "공랭 오일쿨러 (릴리프 체류 대응)", "AFR-OC-601", 3.0),
        HeatSource("TH-CAB-JBR", "JBR 7축 드라이브·PLC 반", jbr_cab,
                   "반내", "필터팬·열교환기 (기존 JB-EL-006, 0.8 kW)", "JB-EL-006", 0.8),
        HeatSource("TH-CAB-LP", "셀 분전반 7면 드라이브 합 (JBR 반 별도)", lp_sum,
                   "반내", "발열 ≥0.4 kW 반은 열교환기, 그 외 필터팬", "—", 0.0),
        HeatSource("TH-SG", "SG-301 연마 절삭열·스핀들", 3.2,
                   "배기", "국소집진 기류로 반출 (1,000 m³/h)", "—", 0.0),
        HeatSource("TH-DX", "DX-601 블로워 축동력", 9.7,
                   "배기", "배기 기류로 옥외 반출", "—", 0.0),
        # REV.23 유리제거셀 — 이 플랜트 최대 발열원이다. 둘 다 반드시 배기로
        # 빼야 한다. 실내로 들어오면 환기량이 33,000 → 110,000 m³/h 가 된다.
        HeatSource("TH-GRM-IR", "GRM-401 IR 인클로저 손실 (수요의 35 %)",
                   ir_enclosure_loss_kw(), "배기",
                   "IR 배기 덕트 · 블로워 3.7 kW (배기유량 감시 인터록)",
                   "GRM-EX-401", 0.0),
        HeatSource("TH-GRM-GL", "GRM-401 박리 유리·셀 현열 (수요의 65 %)",
                   ir_useful_kw(), "배기",
                   "냉각 후드 · 블로워 4.0 kW — 포집 못 하면 그대로 실내 부하",
                   "GRM-CD-401", 0.0),
    )


def exhausted_kw() -> float:
    """배기로 빠지는 발열 — 실내 부하에서 뺀다."""
    return round(sum(s.loss_kw for s in heat_sources() if s.sink == "배기"), 2)


#: 공정실 **밖**에서 소비되는 피더 — 구획된 랙실·관제실이라 그 발열은
#: 자기 항온항습기로 나가고 공정실 환기에 들어오지 않는다.
#:
#: REV.25 에서 스마트 팩토리 부하가 붙으며 필요해졌다. 그냥 두면 랙 발열
#: 8.8 kW 를 공정실이 받는 것으로 계산돼 환기량이 과대해진다 — "보수적"이
#: 아니라 **다른 방의 열을 이 방에 더하는 것**이라 틀린 값이다.
#: 엣지 캐비닛(LP-INST)은 실제로 공정실 안에 서므로 여기 없다.
#:
#: REV.34 에서 LP-AIR 가 들어왔다. 컴프레서를 공정실 밖에 두는 이유는 셋인데
#: (흡입공기 청정도·발열·소음) 그중 **흡입공기**만으로 이미 결론이 난다 —
#: 유리분이 도는 방에서 공기를 빨면 흡입필터와 오일이 먼저 죽고 압축공기
#: 품질도 그만큼 나빠진다. air.py 의 기계실 절 참조.
OFF_ROOM_PANELS: tuple[str, ...] = ("LP-IT", "LP-AIR")

#: 공정과 **동시에 걸리지 않는** 피더. 공정실 안에 있지만 환기 피크에는
#: 들어오지 않는다. 명단은 electrical.py 가 갖는다 — 같은 사실을 두 군데
#: 적어 두면 한쪽만 고치는 날이 온다.
#:
#: REV.28 의 천장크레인이 그렇다. 운전 중 설비 위에서 인양하는 것은 안전상
#: 금지라, 크레인이 도는 때는 공정이 서 있는 때다. 환기는 **동시에 걸리는
#: 최대**로 잡는 것이므로 여기에 더하면 §25 에서 랙 발열을 공정실에 더했던
#: 것과 같은 종류의 틀린 값이 된다 — 그때는 다른 **방**의 열이었고 이번에는
#: 다른 **시간**의 열이다.
NON_COINCIDENT_PANELS = electrical.NON_COINCIDENT_PANELS


def off_room_kw() -> float:
    """공정실 밖에서 소비되는 수요 (kW)."""
    return round(sum(feeder.demand_kw for feeder in electrical.FEEDERS
                     if feeder.panel in OFF_ROOM_PANELS), 2)


def non_coincident_kw() -> float:
    """공정 피크와 동시에 걸리지 않는 수요 (kW)."""
    return round(sum(feeder.demand_kw for feeder in electrical.FEEDERS
                     if feeder.panel in NON_COINCIDENT_PANELS), 2)


def room_load_kw() -> float:
    """공정실에 남는 열 — 수요에서 배기 반출분·구획실 소비·비동시 부하를 뺀 상한."""
    return round(electrical.demand_kw() - exhausted_kw() - off_room_kw()
                 - non_coincident_kw(), 2)


def required_airflow_m3h(delta_t_c: float = ROOM_DELTA_T_C) -> int:
    """실내 온도 상승 ΔT 이하를 지키는 전체 환기량 (m³/h), 500 단위 올림."""
    airflow = room_load_kw() * 3600.0 / (1.2 * 1.005 * delta_t_c)
    return int(-(-airflow // 500) * 500)


def cabinet_loads() -> dict[str, float]:
    """분전반별 반내 발열 (kW)."""
    return {feeder.panel: cabinet_loss_kw(feeder.panel) for feeder in electrical.FEEDERS}


def cabinet_needs_exchanger(panel: str) -> bool:
    return cabinet_loss_kw(panel) >= CABINET_FAN_LIMIT_KW


def coolers_are_sized() -> bool:
    """전용 냉각기는 발열 × 1.25 이상이어야 한다."""
    return all(s.cooler_kw >= cooler_required_kw(s.loss_kw)
               for s in heat_sources() if s.cooler_kw > 0)
