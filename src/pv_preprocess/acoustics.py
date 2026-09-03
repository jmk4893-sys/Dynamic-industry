"""전처리 플랜트 소음·진동 예측 모델과 저감 설계 근거.

값은 실측이 아니라 **계획 예측치**다 — 같은 급 설비의 대표 음향파워(Lw)를
출처 삼아, 근접 작업위치(1 m)와 통로(기계 밴드에서 4 m 이격) 두 수음점의
레벨을 계산한다. 시운전 소음도 실측으로 갱신해야 하며, 그때 이 파일만
고치면 도면·표가 같이 따라온다 (`tests/test_pv_preprocess.py` 가 잡는다).

계산 규약 (반자유음장, 점음원):

* Lp = Lw − 20·log10(r) − 8  (Q=2, 바닥 반사)
* 근접 작업위치는 음원별 r=1 m 단독값, 통로는 전 음원 에너지 합.
* 판정: 산안법 8h 노출 90 dBA 가 법정선이지만, 상시 운전 목표는
  근접 ≤ 85 / 통로 ≤ 70 으로 잡는다. 저감 장치 없는 원값이 목표를
  넘는 음원(SG-301 연마)이 저감 설계의 존재 이유다.

진동은 가진원별 주파수와 절연기 고유진동수로 전달률을 본다.

* T = 1 / ((f/fn)² − 1)  — 감쇠 무시 보수식
* 절연하는 음원은 fn ≤ f/3 (전달률 ≤ 12.5 %) 을 강제한다.
* JBR-201 은 **절연하지 않는다** — 비전 반복 ±0.25 mm 는 강성이 우선이라
  독립 그라우트 기초 + 서보 S커브 저크 제한으로 충격 자체를 줄인다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .layout import build_zones

#: 통로 수음점의 기계 밴드 이격 (m) — 기계 밴드 중심 y≈3,500, 통로 y≈7,650
AISLE_STANDOFF_M = 4.0

#: 상시 운전 목표 (dBA)
NEAR_FIELD_LIMIT_DBA = 85.0
AISLE_LIMIT_DBA = 70.0


@dataclass(frozen=True)
class NoiseSource:
    tag: str
    equipment: str
    x_mm: int
    lw_dba: float        # 대책 전 음향파워
    reduction_db: float  # 저감 장치 삽입손실
    mitigation: str
    character: str       # '정상' | '충격성' | '간헐'


@dataclass(frozen=True)
class VibrationSource:
    tag: str
    equipment: str
    freq_hz: float       # 주 가진 주파수
    isolated: bool
    isolator: str
    fn_hz: float         # 절연기 고유진동수 (비절연이면 0)
    note: str


def _zone_center(key: str) -> int:
    zone = next(z for z in build_zones() if z.key == key)
    return (zone.x0_mm + zone.x1_mm) // 2


def noise_sources() -> tuple[NoiseSource, ...]:
    """음원 목록 — 위치는 배치 모델에서 파생한다."""
    afu = _zone_center("afu")
    jbr = _zone_center("jbr")
    afr = _zone_center("afr")
    post = _zone_center("post")
    buffer_ = _zone_center("buffer")
    grm = _zone_center("grm")
    return (
        NoiseSource("NS-SG", "SG-301 양측 연마 스핀들", post, 96.0, 18.0,
                    "가드 흡음 라이닝 + 국소집진 후드 밀착", "정상"),
        NoiseSource("NS-DXM", "DX-601 주 집진 블로워", post, 92.0, 20.0,
                    "AFR-ENC-601 흡음 인클로저 + AFR-SIL-601 배기 소음기", "정상"),
        NoiseSource("NS-DXL", "DX-601 국소 블로워", post, 84.0, 20.0,
                    "주 블로워와 같은 인클로저 동거", "정상"),
        NoiseSource("NS-HPU6", "HPU-601 유압 펌프", afr - 1_700, 88.0, 12.0,
                    "방음 커버 + AFR-AVM-601 방진 마운트", "정상"),
        NoiseSource("NS-HPU1", "HPU-101 유압 펌프", afu - 3_100, 84.0, 12.0,
                    "중앙벽 뒤 배치 + 방음 커버 + AFU-AVM-101 방진 마운트", "정상"),
        NoiseSource("NS-JBR", "JBR-201 박리 충격·공압 배기", jbr, 86.0, 8.0,
                    "가드 흡음 라이닝 + 배기 포트 소음기", "충격성"),
        NoiseSource("NS-CV", "컨베이어·체인 3기", jbr + 3_000, 75.0, 4.0,
                    "저마킹 PU 롤러 + 분할식 체인커버", "정상"),
        NoiseSource("NS-RB", "RB-101·GBR 셔틀 서보", buffer_, 72.0, 0.0,
                    "— (가감속 저크 제한만)", "정상"),
        NoiseSource("NS-FL", "FL-101 전동 지게차", afu - 2_500, 78.0, 0.0,
                    "전동식 채택 (엔진식 88 대비 −10)", "간헐"),
        # ── REV.23 유리제거셀 ────────────────────────────────────────────
        # IR 램프와 탠덤 칼날 자체는 조용하다. 새 음원은 배기 블로워 두 대와
        # 슈레더 정량 투입이다. 블로워는 DX-601 과 같은 대책(인클로저+소음기)을
        # 그대로 적용한다.
        NoiseSource("NS-GRM-IRX", "GRM-EX-401 IR 배기 블로워", grm - 2_150, 89.0, 20.0,
                    "흡음 인클로저 + 배기 소음기 (DX-601 과 동일 사양)", "정상"),
        NoiseSource("NS-GRM-CD", "GRM-CD-401 냉각 후드 블로워", grm + 4_200, 90.0, 20.0,
                    "흡음 인클로저 + 배기 소음기", "정상"),
        NoiseSource("NS-GRM-SH", "CV-301 슈레더 정량 투입", grm + 4_200, 87.0, 14.0,
                    "투입 슈트 고무 라이닝 + 밀폐 커버", "충격성"),
        NoiseSource("NS-GRM-TDM", "TDM-201 탠덤 칼날·권취", grm + 1_200, 76.0, 6.0,
                    "가드 흡음 라이닝", "정상"),
    )


def near_field_dba(source: NoiseSource, mitigated: bool = True) -> float:
    """음원별 근접 작업위치(1 m) 예측 레벨."""
    lw = source.lw_dba - (source.reduction_db if mitigated else 0.0)
    return round(lw - 8.0, 1)


def worst_near_field_dba(mitigated: bool = True) -> float:
    return max(near_field_dba(s, mitigated) for s in noise_sources())


def aisle_spl_dba(x_mm: int, mitigated: bool = True) -> float:
    """통로 위 x 지점의 전 음원 에너지 합 레벨."""
    total = 0.0
    for source in noise_sources():
        lw = source.lw_dba - (source.reduction_db if mitigated else 0.0)
        r = math.hypot((x_mm - source.x_mm) / 1000.0, AISLE_STANDOFF_M)
        total += 10 ** ((lw - 20.0 * math.log10(max(r, 1.0)) - 8.0) / 10.0)
    return round(10.0 * math.log10(total), 1)


def worst_aisle_dba(mitigated: bool = True) -> tuple[int, float]:
    """통로 최악점 (x, dBA) — 250 mm 간격 스캔."""
    zones = build_zones()
    plant_x = max(z.x1_mm for z in zones)
    worst = (0, -1.0)
    for x in range(0, plant_x + 1, 250):
        level = aisle_spl_dba(x, mitigated)
        if level > worst[1]:
            worst = (x, level)
    return worst


def vibration_sources() -> tuple[VibrationSource, ...]:
    return (
        VibrationSource("VS-HPU6", "HPU-601 펌프 1,450 rpm", 24.2, True,
                        "고무 방진 마운트", 8.0, "맥동은 축압기·호스 루프로 절연"),
        VibrationSource("VS-HPU1", "HPU-101 펌프 1,450 rpm", 24.2, True,
                        "고무 방진 마운트", 8.0, "배관은 방진 클램프 고정"),
        VibrationSource("VS-DX", "DX-601 블로워 2,900 rpm", 48.3, True,
                        "스프링 마운트 + 캔버스 이음", 4.0, "덕트는 유연 이음으로 절단"),
        VibrationSource("VS-SG", "SG-301 스핀들 3,000 rpm", 50.0, True,
                        "패드 마운트 (동적 밸런싱 G2.5 병행)", 10.0,
                        "휠 불평형이 1차 가진 — 밸런싱이 먼저다"),
        VibrationSource("VS-JBR", "JBR-201 박리 충격 (과도)", 0.0, False,
                        "— 독립 그라우트 기초", 0.0,
                        "비전 ±0.25 mm 는 강성 우선 — S커브 저크 제한으로 충격 저감"),
        VibrationSource("VS-SHT", "셔틀·캐리지 가감속 ~2 Hz", 2.0, False,
                        "— (구조 강성·저크 제한)", 0.0,
                        "저주파 가진은 절연 불가 — 가감속 프로파일로 관리"),
        VibrationSource("VS-BFC", "BFC 반전 가감속 0.25 Hz", 0.25, False,
                        "— (포탈 강성)", 0.0,
                        "반전 관성은 포탈 4기둥·크로스빔이 받는다"),
    )


def transmissibility(freq_hz: float, fn_hz: float) -> float:
    """감쇠 무시 전달률 — f/fn > √2 에서만 절연이 성립한다."""
    ratio = freq_hz / fn_hz
    if ratio <= math.sqrt(2.0):
        raise ValueError("f/fn ≤ √2 — 절연이 아니라 증폭이다")
    return 1.0 / (ratio ** 2 - 1.0)


def isolation_ok(source: VibrationSource) -> bool:
    """절연 음원의 fn ≤ f/3 규칙 (전달률 ≤ 12.5 %)."""
    if not source.isolated:
        return True
    return source.fn_hz <= source.freq_hz / 3.0
