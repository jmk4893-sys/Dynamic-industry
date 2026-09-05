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
    Axis("AXIS-SG-P", "LP-GLASS", "SG-301", "연마 압력·높이", 2, 0.4,
         "서보", "23 bit 절대", False, "컴플라이언스 제어 — 휠 마모 보상"),
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
    # ── REV.23 유리제거셀(GRM-401) ──────────────────────────────────────
    # 후단 앱의 하드웨어 목록에 이름·기능이 이미 있는 축들이다. 정격은 계획값.
    Axis("AXIS-GRM-LI", "LP-GRM-MEC", "LI-101", "5단 랙 양주 승강", 2, 1.5,
         "서보", "23 bit 절대", True,
         "볼스크루/타이밍벨트 동기축 · 카운터밸런스 · 무여자 브레이크 (앱 명시)"),
    Axis("AXIS-GRM-TS", "LP-GRM-MEC", "TS-101", "2단 텔레스코픽 포크", 1, 0.75,
         "서보", "23 bit 절대", True, "4점 LM 가이드 · 푸시풀 핀 · 낙하방지 폴"),
    Axis("AXIS-GRM-TX", "LP-GRM-MEC", "TDM-201", "탠덤 공통 X축", 1, 1.5,
         "서보", "23 bit 절대", False, "칼끝 300±2 mm 전자기어 추종 (앱 명시)"),
    Axis("AXIS-GRM-TZ", "LP-GRM-MEC", "HKB-101 / HKS-201", "칼날 독립 Z축", 2, 0.4,
         "서보", "23 bit 절대", True, "박리 자세 유지 — 중력축이라 브레이크 필수"),
    Axis("AXIS-GRM-WR", "LP-GRM-MEC", "WR-101", "백시트 전장 권취", 1, 0.75,
         "서보", "23 bit 절대", False, "횡방향 분할클램프 · 장력 제어"),
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
    Axis("MTR-SG-SP", "LP-GLASS", "SG-301", "연마 스핀들", 2, 2.2,
         "인버터", "—", False, "양측 동기 · 국소집진 연동"),
    Axis("MTR-CV-102", "LP-GLASS", "CV-102", "이송 기어드", 1, 0.75,
         "직입", "—", False, "GI-301 통합 검사대 통과 이송"),
    Axis("MTR-DX-MB", "LP-DX", "DX-601", "주 집진 블로워", 1, 7.5,
         "인버터", "—", False, "1,000 m³/h — 풍량 GA 명시"),
    Axis("MTR-DX-LB", "LP-DX", "DX-601", "국소 집진 블로워", 1, 2.2,
         "인버터", "—", False, "JBR 국소 350 m³/h"),
    # ── REV.23 유리제거셀(GRM-401) ──────────────────────────────────────
    Axis("MTR-GRM-EX", "LP-GRM-MEC", "EX-101", "하단 방출셔틀", 1, 0.75,
         "직입", "—", False, "가열 완료 데크에서 탠덤으로 반출"),
    Axis("MTR-GRM-RT", "LP-GRM-MEC", "RT-101", "빈 캐리지 하부 복귀", 1, 0.55,
         "직입", "—", False, "랙 하부 되돌림 — 투입측 재장전 루프"),
    Axis("MTR-GRM-GR", "LP-GRM-MEC", "GR-201 / DS-301", "유리 반출·적재대 하강", 2, 0.4,
         "직입", "—", False, "단거리 저충격 롤러 · 하강식 적재대"),
    Axis("MTR-GRM-IRX", "LP-GRM-EXH", "GRM-EX-401", "IR 배기 블로워", 1, 3.7,
         "인버터", "—", False, "IR 인클로저 손실 반출 — 배기유량 감시 연동"),
    Axis("MTR-GRM-CD", "LP-GRM-EXH", "GRM-CD-401", "냉각 후드 배기 블로워", 1, 4.0,
         "인버터", "—", False, "박리 유리·셀 현열 포집 — 실내 투입 방지"),
    Axis("MTR-GRM-SH", "LP-GRM-EXH", "CV-301", "슈레더 정량 투입", 1, 1.1,
         "인버터", "—", False, "셀/EVA 정량 토출"),
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
