"""압축공기 계통 CMP-701 (UT-1003) — 공압을 쓰는데 만드는 것이 없었다.

REV.33 까지 이 플랜트는 압축공기를 **쓰고 있었다.** JBR-201 셀 사양에
`에어 0.5–0.6 MPa · 평균 260 / 피크 420 NL/min` 이 적혀 있고, 승강 가이드
실린더·공압 가위·에어나이프·안전정지 시 에어 덤프가 전부 그 공기로 움직인다.
계측기 FL-901 은 아예 **"압축공기 주관 유량·압력"** 을 재고 있다 — 주관이
있다고 전제하고 재는 것이다.

그런데 그 공기를 만드는 것이 어디에도 없었다. 컴프레서·드라이어·리시버·주관
검색 0건. 전기 피더 0건. 3D 형상 0건.

§8 에서 데크 상승 로직만 있고 유압 하드웨어(HPU)가 없던 것, §26 에서 진공
흡착은 그려 놓고 진공원(VAC-101)이 없던 것과 **같은 병의 세 번째**다. 동작은
그리고 그 동작을 만드는 유틸리티는 안 세운다.

이 파일은 그것을 세운다. 용량을 고르지 않고 **소비처에서 파생**시킨다.

지어낸 값은 전부 이름을 붙여 드러냈다 — `UNLISTED_MARGIN` 과
`LEAKAGE_MARGIN` 이 그것이다. 숨겨서 섞어 넣으면 나중에 실측이 왔을 때 무엇을
고쳐야 하는지 알 수 없다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import campaign

# ── 압력 계통 ────────────────────────────────────────────────────────────
#: 사용단 압력 (bar g). JBR 셀 사양 0.5–0.6 MPa 의 상단.
USE_BAR = 6.0

#: 컴프레서 토출 압력 (bar g). 사용단 + 배관 강하 + 드라이어 강하 + 제어 밴드.
SUPPLY_BAR = 7.0

#: 주관 허용 압력강하 (bar). 이 안에서 관경을 고른다.
HEADER_DROP_BAR = 0.2

#: 주관 유속 상한 (m/s). 넘으면 압력강하가 급히 커지고 소음이 난다.
HEADER_VELOCITY_MS = 6.0


# ── 집진 탈진 (DX-601) ───────────────────────────────────────────────────
#: 집진 풍량 (m³/h) — 주 집진 1,000 + JBR 국소 350. `electrical.FEEDERS` 의
#: F7 사양과 같아야 한다 (시험이 대조한다).
DUST_FLOW_M3H = 1_350

#: 여과속도 A/C 비 (m³/(h·m²)). 미분진 펄스제트 카트리지 관례 1.2 m/min.
AIR_TO_CLOTH_M3_H_M2 = 72.0

#: 펄스 밸브 1개가 맡는 여과면적 (m²). 관례값.
AREA_PER_VALVE_M2 = 3.0

#: 펄스 1회 공기량 (Nm³/밸브). 0.5 MPa · 100 ms 관례값.
PULSE_NM3 = 0.05

#: 탈진 주기 (분). DP-901 차압 트리거이며 이 값은 **계획 상한**이다 —
#: 실제로는 차압이 임계를 넘을 때만 돌므로 평균은 이보다 작다.
PULSE_INTERVAL_MIN = 10.0


def filter_area_m2() -> float:
    """여과면적 (m²) — 풍량과 A/C 비에서 나온다."""
    return round(DUST_FLOW_M3H / AIR_TO_CLOTH_M3_H_M2, 1)


def pulse_valves() -> int:
    """펄스 밸브 수 — 여과면적을 밸브당 담당면적으로 나눈다."""
    return math.ceil(filter_area_m2() / AREA_PER_VALVE_M2)


def pulse_average_nl_min() -> float:
    """탈진 **평균** 공기량 (NL/min)."""
    return round(pulse_valves() * PULSE_NM3 / PULSE_INTERVAL_MIN * 1000, 1)


# ── AFR 상부 클램프 (CL-221) ─────────────────────────────────────────────
#: **가정 — CL-221 4기는 공압이다.**
#:
#: 같은 셀에 HPU-601 유압이 있어서 유압일 수도 있다. 공압으로 잡은 근거는
#: 셋이다: ① 3 kN 은 5 bar 에서 보어 87 mm 면 나오는 힘이라 공압으로 충분하고
#: ② 유압 25 kN 을 쓰는 인발축(SA-301)과 달리 클램프는 빠른 여닫이가 중요하며
#: ③ 안전정지 시 "에어 덤프" 규약이 클램프를 포함한다고 읽힌다.
#:
#: 틀렸다면 컴프레서가 그만큼 작아진다 — **크게 잡는 쪽이 안전한 방향**이라
#: 이렇게 두고 확인 항목에 올린다.
CLAMP_IS_PNEUMATIC = True

CLAMP_UNITS = 4
CLAMP_BORE_MM = 100          # 3 kN / 5 bar → 필요 보어 87 → 표준 100
CLAMP_STROKE_MM = 200        # 계획값 — 패널면에서 떼는 행정
CLAMP_ROD_AREA_RATIO = 0.8   # 로드측 유효면적비


def clamp_nm3_per_panel(pneumatic: bool | None = None) -> float:
    """클램프 4기가 패널 1장에 쓰는 공기 (Nm³) — 왕복 1회."""
    if not (CLAMP_IS_PNEUMATIC if pneumatic is None else pneumatic):
        return 0.0
    bore, stroke = CLAMP_BORE_MM / 1000, CLAMP_STROKE_MM / 1000
    extend = math.pi / 4 * bore ** 2 * stroke * (USE_BAR + 1.0)
    return round((extend + extend * CLAMP_ROD_AREA_RATIO) * CLAMP_UNITS, 4)


def panels_per_h() -> float:
    """시간당 처리 장수 — 캠페인 택트에서 나온다."""
    return round(3600.0 / campaign.summary()["takt_s"], 1)


def clamp_average_nl_min(pneumatic: bool | None = None) -> float:
    """클램프 평균 공기량 (NL/min)."""
    return round(clamp_nm3_per_panel(pneumatic) * panels_per_h() / 60 * 1000, 1)


# ── 소비처 ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Consumer:
    """압축공기 소비처 하나."""

    tag: str
    cell: str
    average_nl_min: float
    peak_nl_min: float
    basis: str
    confirmed: bool     # 문서화된 값인가, 여기서 파생한 계획값인가


def consumers(pneumatic: bool | None = None) -> tuple[Consumer, ...]:
    """소비처 목록. 파생값이 있어 상수가 아니라 함수다.

    `pneumatic` 은 AFR 클램프 가정을 갈아 끼우는 자리다 — 기본은
    `CLAMP_IS_PNEUMATIC`. 가정이 뒤집혔을 때 무엇이 따라 움직이는지를
    값으로 물을 수 있어야 미확정 항목이 문장에 머물지 않는다.
    """
    return (
        Consumer("JBR-201", "jbr", 260.0, 420.0,
                 "셀 유틸리티 사양 — 0.5–0.6 MPa · 0.26–0.20 Nm³/장 (60–80 장/h). "
                 "승강 Ø63 가이드 실린더 2 · A/B 순차 공압 가위 · 에어나이프 포함",
                 True),
        Consumer("DX-601", "post", pulse_average_nl_min(), 0.0,
                 f"펄스제트 탈진 — 집진 {DUST_FLOW_M3H:,} m³/h ÷ A/C {AIR_TO_CLOTH_M3_H_M2:g} "
                 f"= 여과 {filter_area_m2():g} m² → 밸브 {pulse_valves()}개 × "
                 f"{PULSE_NM3} Nm³ / {PULSE_INTERVAL_MIN:g}분. "
                 "순간 소비는 리시버가 받으므로 피크를 컴프레서에 싣지 않는다",
                 False),
        Consumer("AFR CL-221", "afr",
                 clamp_average_nl_min(pneumatic), clamp_average_nl_min(pneumatic),
                 f"상부 클램프 {CLAMP_UNITS}기 Ø{CLAMP_BORE_MM} × {CLAMP_STROKE_MM} 왕복 · "
                 f"{clamp_nm3_per_panel(pneumatic)} Nm³/장 × {panels_per_h()} 장/h. "
                 "**공압이라는 가정** — CLAMP_IS_PNEUMATIC 참조",
                 False),
    )


#: **미계상 여유.** 셀마다 스토퍼·푸셔·정렬 실린더가 더 있는데 공압 액추에이터
#: 인벤토리가 아직 없다(서보는 servos.py 로 36축을 세었지만 공압은 안 셌다).
#: 그 목록이 생기면 이 여유는 실제 소비처로 바뀌어 없어진다.
UNLISTED_MARGIN = 0.15

#: **누설 여유.** 신설 배관 관례. 오래된 공장은 20–30 % 가 흔하고, 그것이
#: FL-901 을 단 이유다 — AI-03 이 무부하 시간대 누설량을 산출한다.
LEAKAGE_MARGIN = 0.20


def average_nl_min(pneumatic: bool | None = None) -> float:
    """소비처 평균 합계 (NL/min) — 여유 전."""
    return round(sum(c.average_nl_min for c in consumers(pneumatic)), 1)


def peak_nl_min(pneumatic: bool | None = None) -> float:
    """동시 피크 (NL/min) — 여유 전. 탈진 순간은 리시버가 받는다."""
    return round(sum(max(c.peak_nl_min, c.average_nl_min)
                     for c in consumers(pneumatic)), 1)


def required_fad_nl_min(pneumatic: bool | None = None) -> float:
    """컴프레서가 내야 하는 자유공기량 FAD (NL/min)."""
    return round(average_nl_min(pneumatic)
                 * (1 + UNLISTED_MARGIN) * (1 + LEAKAGE_MARGIN), 1)


# ── 컴프레서 ─────────────────────────────────────────────────────────────
#: 표준 스크류 컴프레서 (kW, 7 bar 에서의 FAD NL/min). 카탈로그 관례값.
COMPRESSOR_RANGE: tuple[tuple[float, int], ...] = (
    (3.7, 500), (5.5, 800), (7.5, 1_050), (11.0, 1_600), (15.0, 2_300),
)

#: **1 운전 · 1 예비.** VAC-101 과 같은 근거다 — 공기가 끊기면 클램프가
#: 풀리고 패널이 떨어진다. §26 에서 "진공 파단은 곧 유리 파손" 이라 리시버를
#: 2기로 둔 것과 같은 판단이라, 여기서만 다르게 할 이유가 없다.
COMPRESSOR_UNITS = 2
COMPRESSOR_DUTY = 1


def compressor_kw(pneumatic: bool | None = None) -> float:
    """1대 정격 (kW) — 필요 FAD 를 넘는 첫 표준 기종."""
    need = required_fad_nl_min(pneumatic)
    for kw, fad in COMPRESSOR_RANGE:
        if fad >= need:
            return kw
    raise ValueError("필요 FAD 가 표준 기종을 넘는다 — 계통 재검토")


def compressor_fad_nl_min(pneumatic: bool | None = None) -> int:
    """선정 기종의 FAD (NL/min)."""
    kw = compressor_kw(pneumatic)
    return next(fad for rated, fad in COMPRESSOR_RANGE if rated == kw)


def compressor_margin() -> float:
    """선정 FAD ÷ 필요 FAD."""
    return round(compressor_fad_nl_min() / required_fad_nl_min(), 2)


def covers_peak() -> bool:
    """운전 1대가 동시 피크를 받는가 — 리시버 없이도 버티는가."""
    return compressor_fad_nl_min() >= peak_nl_min()


# ── 리시버 ───────────────────────────────────────────────────────────────
#: 탈진 1발이 허용하는 압력강하 (bar). 이보다 떨어지면 사용단이 0.5 MPa 밑으로
#: 내려가 클램프 힘이 모자란다.
PULSE_DROP_BAR = 0.5

#: 컴프레서 로드/언로드 최대 기동 횟수 (회/h). 이보다 잦으면 모터가 상한다.
MAX_STARTS_PER_H = 30

#: 표준 리시버 용량 (L).
RECEIVER_RANGE: tuple[int, ...] = (200, 300, 500, 1_000, 2_000)


def receiver_for_pulse_l() -> float:
    """탈진 1발을 받는 데 필요한 리시버 용량 (L).

    **리시버가 있는 이유가 이것이다.** 펄스는 0.1 초에 끝나는데 컴프레서는
    그 속도로 못 따라간다 — 순간 수요는 저장으로 받고 컴프레서는 평균만 낸다.
    """
    return round(PULSE_NM3 * 1.013 / PULSE_DROP_BAR * 1_000, 1)


def receiver_for_cycling_l() -> float:
    """기동 횟수를 상한 안에 두는 데 필요한 용량 (L).

    V = Q × t / (4 × Δp) — 로드/언로드 제어의 표준식.
    """
    q = required_fad_nl_min()
    minutes = 60.0 / MAX_STARTS_PER_H
    return round(q * minutes / (4 * (SUPPLY_BAR - USE_BAR)), 1)


def receiver_l() -> int:
    """리시버 용량 (L) — 둘 중 큰 쪽을 넘는 첫 표준 용기."""
    need = max(receiver_for_pulse_l(), receiver_for_cycling_l())
    for size in RECEIVER_RANGE:
        if size >= need:
            return size
    raise ValueError("필요 리시버가 표준 용기를 넘는다")


def receiver_governed_by() -> str:
    """리시버 용량을 정한 쪽 — 어느 요구가 지배하는지가 설계 근거다."""
    return "탈진 펄스" if receiver_for_pulse_l() >= receiver_for_cycling_l() \
        else "기동 횟수"


# ── 드라이어·주관 ────────────────────────────────────────────────────────
#: 냉동식 드라이어 압력노점 (°C). 실내 배관이라 동결 우려가 없어 냉동식으로
#: 충분하다 — 흡착식은 노점 −40 이 필요할 때 쓴다.
DRYER_DEW_POINT_C = 3.0

#: 드라이어 소비전력 (kW). 처리량에 대한 관례값.
DRYER_KW = 0.5


def header_bore_mm() -> int:
    """주관 관경 (mm) — 유속 상한에서 나온다.

    압축공기는 압력이 높을수록 부피가 줄므로, 유속은 **사용 압력에서의
    실제 유량**으로 재야 한다. FAD 를 그대로 쓰면 관을 과대하게 잡는다.
    """
    actual_m3_s = required_fad_nl_min() / 1000 / 60 / (SUPPLY_BAR + 1.0)
    area = actual_m3_s / HEADER_VELOCITY_MS
    bore = math.sqrt(area * 4 / math.pi) * 1000
    for size in (15, 20, 25, 32, 40, 50, 65, 80):
        if size >= bore:
            return size
    raise ValueError("주관이 표준 관경을 넘는다")


def header_velocity_ms() -> float:
    """선정 관경에서의 실제 유속 (m/s)."""
    actual_m3_s = required_fad_nl_min() / 1000 / 60 / (SUPPLY_BAR + 1.0)
    area = math.pi / 4 * (header_bore_mm() / 1000) ** 2
    return round(actual_m3_s / area, 2)


# ── 주관 행거 (건물 인터페이스) ──────────────────────────────────────────
#: 주관 행거 간격 (mm). DN20 강관의 관례 지지 간격.
HANGER_PITCH_MM = 3_000

#: DN20 강관 단위중량 (kg/m) — 공관 기준. 공기는 무게가 없다시피 하다.
HEADER_KG_PER_M = 1.3

#: 주관 길이 (mm) — 기계실에서 상류 끝까지. 3D 실측과 같아야 한다.
HEADER_RUN_MM = 50_950


def hangers() -> int:
    """행거 수 — 길이를 간격으로 나눈다."""
    return math.ceil(HEADER_RUN_MM / HANGER_PITCH_MM) + 1


def hanger_load_kg() -> float:
    """행거 1개가 받는 하중 (kg)."""
    return round(HEADER_KG_PER_M * HANGER_PITCH_MM / 1000, 1)


# ── 기계실 ───────────────────────────────────────────────────────────────
#: **컴프레서는 공정실 밖에 세운다.** 이유가 셋인데 하나만으로도 결론이 난다.
#:
#:   ① 흡입공기. 유리분·폴리머 분진이 도는 방에서 공기를 빨아들이면 흡입필터와
#:      오일이 먼저 죽는다. 압축공기 품질도 그만큼 나빠진다.
#:   ② 발열. 축동력의 거의 전부가 열이 된다 — 공정실에 두면 환기가 늘어난다.
#:   ③ 소음. 인클로저형이라도 75 dBA 급이다.
#:
#: 랙실(SVR-902)·관제실(MCR-901)과 같은 취급이라 `thermal.OFF_ROOM_PANELS`
#: 에 들어간다.
COMPRESSOR_FOOTPRINT_MM = (800, 700)     # 인클로저형 1대
DRYER_FOOTPRINT_MM = (500, 600)
RECEIVER_DIAMETER_MM = 600
MAINTENANCE_CLEARANCE_MM = 1_000         # 전면 정비 공간
ROOM_HEIGHT_MM = 2_700


def room_mm() -> tuple[int, int, int]:
    """기계실 외형 (mm) — 기기 배치에서 파생한다.

    폭 = 컴프레서 2대 + 드라이어 + 리시버 + 기기 사이 이격,
    깊이 = 기기 깊이 + 전면 정비 공간.
    """
    gap = 100
    width = (COMPRESSOR_FOOTPRINT_MM[0] * COMPRESSOR_UNITS
             + DRYER_FOOTPRINT_MM[0] + RECEIVER_DIAMETER_MM
             + gap * (COMPRESSOR_UNITS + 2))
    depth = max(COMPRESSOR_FOOTPRINT_MM[1], DRYER_FOOTPRINT_MM[1],
                RECEIVER_DIAMETER_MM) + MAINTENANCE_CLEARANCE_MM
    return (int(-(-width // 100) * 100), int(-(-depth // 100) * 100), ROOM_HEIGHT_MM)


# ── 전기·열·소음 ─────────────────────────────────────────────────────────
def installed_kw(pneumatic: bool | None = None) -> float:
    """설치 전력 (kW) — 컴프레서 전대 + 드라이어."""
    return round(compressor_kw(pneumatic) * COMPRESSOR_UNITS + DRYER_KW, 1)


#: 수용률. 1대만 돌고, 그 1대도 로드/언로드로 쉰다.
#: 부하율 = 필요 FAD ÷ 선정 FAD 에서 나온다 — 상수로 박지 않는다.
def diversity(pneumatic: bool | None = None) -> float:
    """수용률 — 운전 대수 비율 × 부하율."""
    duty_ratio = COMPRESSOR_DUTY / COMPRESSOR_UNITS
    load_ratio = required_fad_nl_min(pneumatic) / compressor_fad_nl_min(pneumatic)
    dryer = DRYER_KW / installed_kw(pneumatic)
    return round(duty_ratio * load_ratio * (1 - dryer) + dryer, 2)


def demand_kw(pneumatic: bool | None = None) -> float:
    return round(installed_kw(pneumatic) * diversity(pneumatic), 2)


#: 소음 — 인클로저형 스크류 1 m 음압 (dBA). 기계실 벽이 다시 줄인다.
NOISE_DBA = 75.0


def summary() -> dict[str, object]:
    """도면·검토서에 그대로 넣는 값."""
    room = room_mm()
    return {
        "useBar": USE_BAR,
        "supplyBar": SUPPLY_BAR,
        "averageNlMin": average_nl_min(),
        "peakNlMin": peak_nl_min(),
        "unlistedMargin": UNLISTED_MARGIN,
        "leakageMargin": LEAKAGE_MARGIN,
        "requiredFadNlMin": required_fad_nl_min(),
        "compressorKw": compressor_kw(),
        "compressorUnits": COMPRESSOR_UNITS,
        "compressorFadNlMin": compressor_fad_nl_min(),
        "compressorMargin": compressor_margin(),
        "receiverL": receiver_l(),
        "receiverGovernedBy": receiver_governed_by(),
        "dryerDewPointC": DRYER_DEW_POINT_C,
        "headerBoreMm": header_bore_mm(),
        "headerVelocityMs": header_velocity_ms(),
        "filterAreaM2": filter_area_m2(),
        "pulseValves": pulse_valves(),
        "roomMm": list(room),
        "installedKw": installed_kw(),
        "demandKw": demand_kw(),
        "headerRunMm": HEADER_RUN_MM,
        "hangers": hangers(),
        "hangerPitchMm": HANGER_PITCH_MM,
        "hangerLoadKg": hanger_load_kg(),
        "noiseDba": NOISE_DBA,
    }
