"""전처리 플랜트 전동기·서보 축 일람.

"서보가 구현돼 있는지"에 대한 답이 흩어져 있으면 확인할 수 없다 — 3D 라벨,
부품표, 제어반 문구(JBR "EtherCAT 7축 서보")에 이미 박혀 있는 축들을 한 곳에
모으고, 도면(`docs/drawings/pv-preprocess-plant.html` 의 SERVO_AXES 리터럴)과
값이 어긋나면 `tests/test_pv_preprocess.py` 가 잡는다.

두 가지 불변식이 설계 근거다.

* 분전반별 전동기 정격 합계는 그 피더의 설치 kW(`electrical.FEEDERS`)를
  넘을 수 없다 — 축을 추가하면 피더 예산부터 다시 세워야 한다.
* 중력·자세 유지 축(승강·반전·박리)은 브레이크 없이 존재할 수 없다.

정격은 OEM 명판 확정 전의 계획값이다. 토크 근거가 이미 도면에 있는 축은
비고에 그 부품번호를 적는다 (예: BFC 반전 = AFU-BGD-101, 연속 700 N·m).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import electrical

#: 서보 제어·안전 계층 — EL-1008 회로도와 같은 전제
CONTROL_LAYER = "EtherCAT CoE(CSP) · FSoE STO"


@dataclass(frozen=True)
class Axis:
    """전동기 축 한 종류 (qty 대가 같은 사양)."""

    tag: str
    panel: str          # 급전 분전반 (electrical.FEEDERS 의 panel)
    equipment: str
    motion: str
    qty: int
    rated_kw: float     # 1축 정격
    drive: str          # '서보' | '인버터' | '소프트스타터' | '직입'
    feedback: str
    brake: bool
    note: str

    @property
    def group_kw(self) -> float:
        return round(self.qty * self.rated_kw, 2)


#: 서보 축 — EtherCAT 데이지체인에 올라가는 위치제어 축 전부.
SERVO_AXES: tuple[Axis, ...] = (
    Axis("AXIS-BFC-R", "LP-AFU", "BFC-101A/B", "반전 R (180°)", 2, 1.5,
         "서보", "23 bit 절대", True,
         "AFU-BGD-101 — 연속 700 N·m·피크 1.6 kN·m, 감속기·이중 브레이크"),
    Axis("AXIS-BFC-Z", "LP-AFU", "BFC-101A/B", "카세트 승강 Z", 2, 1.1,
         "서보", "23 bit 절대", True,
         "포탈 LM 가이드 · 반전축 H=3,300 도킹, 볼스크루"),
    Axis("AXIS-CD-Z", "LP-AFU", "CD-101", "포획빔 승강", 1, 0.4,
         "서보", "23 bit 절대", True, "중앙벽 수납 ↔ 포획 위치"),
    Axis("AXIS-RB-J13", "LP-RB", "RB-101", "다관절 J1–J3", 3, 1.2,
         "서보", "OEM 절대", True, "OEM 일괄 — 하중도 승인 전 계획값"),
    Axis("AXIS-RB-J46", "LP-RB", "RB-101", "다관절 J4–J6", 3, 0.35,
         "서보", "OEM 절대", True, "OEM 일괄 — 손목 3축"),
    Axis("AXIS-JBR-X", "LP-JBR", "JBR-201", "브리지 X", 1, 0.75,
         "서보", "23 bit 절대", False,
         "JB-MX-005 — 양측 풀리 단일서보·기계 동기축, 정렬 0.08 mm"),
    Axis("AXIS-JBR-HY", "LP-JBR", "JBR-201", "헤드 Y ×3", 3, 0.2,
         "서보", "23 bit 절대", False, "헤드별 0.2 kW 서보벨트 모듈"),
    Axis("AXIS-JBR-PZ", "LP-JBR", "JBR-201", "박리 Z ×3", 3, 0.75,
         "서보", "23 bit 절대", True,
         "1:10 감속 · 회전–직선 추력변환 · 안티백드라이브"),
    Axis("AXIS-AFR-C", "LP-AFR", "AFR-101", "장축 LM 캐리지", 4, 0.75,
         "서보", "23 bit 절대", False, "끝→중앙 1,300 mm 인발 · 힘 모니터"),
    # REV.51: 단변 헤드가 늘어 압력·높이 축이 3 이고, 그 헤드는 폭 방향으로 횡행한다.
    # REV.52: 급전이 LP-GLASS → LP-AFR 이다 — SG·GI 가 AFR 과 한 통합셀이 됐다.
    Axis("AXIS-SG-P", "LP-AFR", "SG-301", "연마 압력·높이 ×3", 3, 0.4,
         "서보", "23 bit 절대", False, "컴플라이언스 제어 — 휠 마모 보상 (장변 2 + 단변 1)"),
    Axis("AXIS-SG-T", "LP-AFR", "SG-301", "단변 헤드 횡행 (폭 1,200 — REV.54 라인 상한)", 1, 0.4,
         "서보", "23 bit 절대", False, "앞·뒤 단변을 정지 상태에서 250 mm/s 로 훑는다 (REV.51)"),
    # 주행이 서면 어느 열에도 못 간다 — 3열 적재 컬럼이 서로를 받아 줘도
    # 주행 하나가 전부를 막는다. 그래서 같은 레일에 구동을 둘 건다(2 마스터).
    # 한쪽이 죽으면 나머지 하나로 감속 주행한다. 바닥면적은 안 는다.
    Axis("AXIS-GBR-X", "LP-GBR", "GBR-301", "수평셔틀 주행 (2구동)", 2, 1.5,
         "서보", "23 bit 절대", False,
         "분기 정지 ±1.0 mm · PU 롤러 · 한 구동 상실 시 감속 주행"),
    Axis("AXIS-GBR-LF", "LP-GBR", "GBR-301", "슬롯 로더 승강", 1, 0.75,
         "서보", "23 bit 절대", True, "캐리지 슬롯 정렬 승강"),
    Axis("AXIS-GBR-FK", "LP-GBR", "GBR-301", "슬롯 로더 포크", 1, 0.4,
         "서보", "23 bit 절대", False, "슬롯 삽입·복귀"),
    # ── REV.54 인계 브리지 — 후단 DG-HK60C 는 자기 서보를 자기 MCC-1 에 갖는다 ──
    # REV.23~53 의 GRM-401 축 7 종(LI·TS·TX·TZ·WR·…)은 그 기계와 함께 나갔다.
    # DG-HK60C 의 구동부 24 기(SV-301 승강 … SV-801 카세트 교환암)는 벤더 PLC·
    # EtherCAT 안이고 플랜트는 OPC UA 로 읽기만 하므로 이 일람에 **넣지 않는다** —
    # 넣으면 STO 노드·드라이브 스트림·피더 예산이 남의 것을 센다 (`hk60c.vendor_drive_count`).
    #
    # 플랜트가 갖는 것은 브리지 하나다. 벤더가 발주자 설비로 넘긴 디스태커 PL-101
    # 의 자리이며, 캐리지는 그대로 두고 **한 장씩** 건넨다 (REV.53 의 결론 그대로).
    # 버퍼 설비라 급전도 LP-GBR 이다.
    Axis("AXIS-GBR-BX", "LP-GBR", "BX-101", "DG-HK60C 인계 브리지", 1, 0.75,
         "서보", "23 bit 절대", True,
         "GBR 캐리지 슬롯 앞에서 LD-101 롤러베드(EL 1,150)까지 유리 한 장을 들어 "
         "왕복한다 — 200 mm 들어 올리는 승강을 겸하므로 브레이크가 붙는다"),
)

#: 서보가 아닌 전동기 — 인버터·소프트스타터·직입.
MOTORS: tuple[Axis, ...] = (
    Axis("MTR-HPU-A", "LP-AFU", "HPU-101", "리프트 유압펌프", 1, 3.7,
         "인버터", "—", False, "비례밸브 승강 — 대기 시 저속 감압"),
    Axis("MTR-VAC", "LP-RB", "EOAT", "진공펌프", 1, 1.5,
         "인버터", "—", False, "픽업 구간만 정격 — 대기 저속"),
    Axis("MTR-CV-J", "LP-JBR", "JBR-201", "셀 컨베이어 기어드", 1, 0.75,
         "직입", "—", False, "JB-CV-004 — 체인 1모터 전체 롤러"),
    Axis("MTR-HPU-6", "LP-AFR", "HPU-601", "단축·벌림 유압펌프", 1, 7.5,
         "소프트스타터", "—", False, "GA 명시 7.5 kW"),
    Axis("MTR-AFR-CV", "LP-AFR", "AFR-101", "반출롤러 기어드 (연마 통과)", 1, 0.75,
         "인버터", "—", False, "SG-301 통과 속도 제어 · 베드-GI 인계 (REV.50)"),
    Axis("MTR-SG-SP", "LP-AFR", "SG-301", "연마 스핀들 ×3", 3, 2.2,
         "인버터", "—", False, "장변 2 동기 + 단변 1 · 국소집진 연동 (REV.51)"),
    Axis("MTR-CV-102", "LP-AFR", "CV-102", "이송 기어드", 1, 0.75,
         "직입", "—", False, "GI-301 통합 검사대 통과 이송"),
    Axis("MTR-DX-MB", "LP-DX", "DX-601", "주 집진 블로워", 1, 7.5,
         "인버터", "—", False, "1,000 m³/h — 풍량 GA 명시"),
    Axis("MTR-DX-LB", "LP-DX", "DX-601", "국소 집진 블로워", 1, 2.2,
         "인버터", "—", False, "JBR 국소 350 m³/h"),
    # REV.54: GRM-401 의 전동기 6 종(방출셔틀·복귀·배기 블로워·냉각 후드·슈레더 투입)은
    # 그 셀과 함께 나갔다. DG-HK60C 의 전동기(투입 롤러·횡인출 벨트·진공펌프 A/B …)는
    # 벤더 MCC-1 안이라 여기 없다.
)


def servo_axis_count() -> int:
    """EtherCAT 서보 축 수 — 도면 배지와 맞아야 한다."""
    return sum(axis.qty for axis in SERVO_AXES)


def servo_axis_count_for(panel: str) -> int:
    return sum(axis.qty for axis in SERVO_AXES if axis.panel == panel)


def motion_kw_by_panel() -> dict[str, float]:
    """분전반별 전동기(서보+비서보) 정격 합계."""
    sums: dict[str, float] = {}
    for axis in SERVO_AXES + MOTORS:
        sums[axis.panel] = round(sums.get(axis.panel, 0.0) + axis.group_kw, 2)
    return sums


def total_servo_kw() -> float:
    return round(sum(axis.group_kw for axis in SERVO_AXES), 2)
