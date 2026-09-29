"""전처리 플랜트 안전 골격 — 위험원·PLr·정지시간 예산·안전 I/O.

도면에는 안전 부품이 이미 서 있다. Type 4 라이트커튼 4대(JB-SF-005), 가드락
인터록(004), 뮤팅 센서쌍 4식과 전용 컨트롤러(009·010), 비상정지 2식(006),
그리고 정지시간 시험포트(008)까지. 그런데 그것들이 **무슨 위험원을 무슨
성능수준으로 막는지**는 어디에도 값이 없었다. 등록부의 PV-PLANT-SF-1004 는
근거란에 'PLr·PFHd·정지시간' 이라 적힌 채 '기본설계' 에 멈춰 있었고,
PLC-IO-7101 도 '회로·SISTEMA' 라고만 적혀 있었다. 부품은 골랐는데 그 부품을
고른 근거가 없는 상태다 — §8 의 유압, §26 의 진공, §34 의 공압과 같은 병이되
이번엔 빠진 것이 장비가 아니라 **판단**이다.

이 모듈이 셋을 값으로 만든다.

* **PLr** — ISO 13849-1 부속서 A 위험그래프. S·F·P 세 갈래로 a…e 를 낸다.
  그래프는 표로 박혀 있고, 각 위험원이 왜 그 갈래인지는 근거란에 적는다.
* **정지시간 예산** — ISO 13855. 다만 여기서 안전거리를 구하지는 않는다.
  가드는 이미 서 있고 감지면 위치가 3D 에 박혀 있으므로 **거리가 정지시간의
  예산을 정한다.** 시운전에서 JB-SF-008 로 잰 값이 예산을 넘으면 가드를
  옮기거나 속도를 낮춰야 한다 — 그쪽이 검증 가능한 방향이다.
* **안전 I/O** — 장치 목록에서 이중채널 입력·안전 출력·FSoE 노드를 센다.
  PLC-IO-7101 의 점수가 그 합이다.

**PFHd 는 여기서 내지 않는다.** 그것은 부품 벤더의 B10d·MTTFd 가 있어야
SISTEMA 로 계산되는 값이다. 없는 값을 지어내면 그 순간 이 파일이 거짓이 되고,
거짓인 PFHd 는 없는 PFHd 보다 나쁘다. 이 모듈은 **무엇을 계산해야 하고 그
입력이 무엇인지**까지를 값으로 고정하고 거기서 멈춘다.

크레인 관련 항목 하나는 다른 모듈의 전제를 떠받친다. `electrical.py` 는
CRN-901 을 비동시 부하로 빼는데(수용률 0.20), 그 근거는
"운전 중 설비 위 인양 금지" 라는 **규칙**이었다. 규칙은 지켜지지 않을 수
있고 그러면 계약전력 근거가 무너진다. SF-08 이 그 규칙을 인터록으로 바꾼다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import campaign, electrical, servos, smart

# ── ISO 13849-1 부속서 A 위험그래프 ──────────────────────────────────────
#: S 상해 정도 — 1: 가역(경상) / 2: 비가역(중상·사망)
#: F 노출 빈도·시간 — 1: 드물다·짧다 / 2: 잦다·길다
#: P 위험 회피 가능성 — 1: 조건부 가능 / 2: 거의 불가
#:
#: 세 갈래를 그대로 표로 둔다. 식으로 접으면 읽는 사람이 표준과 대조할 수
#: 없고, 대조할 수 없는 안전 판단은 승인받지 못한다.
RISK_GRAPH: dict[tuple[int, int, int], str] = {
    (1, 1, 1): "a", (1, 1, 2): "b",
    (1, 2, 1): "b", (1, 2, 2): "c",
    (2, 1, 1): "c", (2, 1, 2): "d",
    (2, 2, 1): "d", (2, 2, 2): "e",
}

#: PL 순서 — 비교에 쓴다.
PL_ORDER: tuple[str, ...] = ("a", "b", "c", "d", "e")

#: PL 별 요구 구조. ISO 13849-1 표 로부터의 관례적 대응이며, 실제 채택은
#: SISTEMA 계산이 확인한다.
PL_CATEGORY: dict[str, str] = {
    "a": "Cat.B / 1",
    "b": "Cat.1",
    "c": "Cat.2",
    "d": "Cat.3",
    "e": "Cat.4",
}


def required_pl(severity: int, frequency: int, avoidance: int) -> str:
    """위험그래프에서 PLr 을 낸다."""
    return RISK_GRAPH[(severity, frequency, avoidance)]


def higher_pl(a: str, b: str) -> str:
    """둘 중 높은 PL."""
    return a if PL_ORDER.index(a) >= PL_ORDER.index(b) else b


def muting_cycles_per_day() -> int:
    """뮤팅이 하루에 열리는 횟수 — 패널 1장에 투입·반출 두 번이다.

    SISTEMA 의 n_op 입력이자 HZ-07 이 F2 인 근거다. 안전부품의 B10d 는
    사이클 수로 나누어 T10d 가 되므로, 이 값이 곧 뮤팅 센서의 교체주기다.
    """
    per_hour = 3600.0 / campaign.summary()["takt_s"]
    hours = smart.OPERATING_HOURS_PER_YEAR / smart.OPERATING_DAYS_PER_YEAR
    return round(per_hour * hours * 2)


# ── 위험원 ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Hazard:
    """위험원 하나. PLr 은 S·F·P 에서 나오지 손으로 적지 않는다."""

    tag: str
    cell: str           # layout.STATIONS 의 키
    description: str
    severity: int
    frequency: int
    avoidance: int
    basis: str          # 왜 그 갈래인가

    @property
    def plr(self) -> str:
        return required_pl(self.severity, self.frequency, self.avoidance)


#: 위험원 일람. 노출 빈도 F 는 **사람의 노출**이지 기계의 동작 빈도가 아니다 —
#: 가드 안에서 48.5 초마다 도는 축이라도 사람이 정비 때만 들어간다면 F1 이다.
#: 이 구분을 놓치면 전 셀이 F2 가 되어 PLr 이 실제보다 한 단씩 부푼다.
HAZARDS: tuple[Hazard, ...] = (
    Hazard("HZ-01", "afu", "AFU-101 듀얼 도킹 Bay — 지게차 진입·리프트 승강 협착",
           2, 2, 1,
           "S2 지게차와 리프트 사이 협착은 비가역이다. F2 반입은 상시 작업이라 "
           "사람이 늘 옆에 있다. P1 접근속도가 낮고 BW-101 안전벽체가 Bay 를 "
           "나눠 대피 방향이 남는다"),
    Hazard("HZ-02", "bfc", "BFC-101A/B 반전 카세트 180° 회전 — 회전체·고정물 사이 협착",
           2, 1, 2,
           "S2 2,500 kg 회전체다. F1 가드 안이라 정비 때만 들어간다. "
           "P2 링과 프레임 사이에 들어간 뒤에는 피할 방향이 없다"),
    Hazard("HZ-03", "bfc", "BFC 카세트 승강 Z — 낙하·협착",
           2, 1, 2,
           "S2 4,500 mm 높이의 카세트가 떨어진다. F1 정비 노출. "
           "P2 밑에 있으면 피할 수 없다 — 기계식 정비 안전받침이 그래서 있다"),
    Hazard("HZ-04", "robot", "RB-101 다관절 작업영역 — 충돌·협착",
           2, 1, 2,
           "S2 6축 로봇 충돌. F1 티칭·정비 때만. P2 로봇 도달범위 안에서는 "
           "사람이 로봇보다 느리다"),
    Hazard("HZ-05", "jbr", "JBR-201 3헤드 승강 플레이트·박리 Z 추력 — 협착",
           2, 1, 2,
           "S2 1:10 감속 추력이다. F1 가드 안. P2 헤드 밑에서는 피할 수 없다"),
    Hazard("HZ-06", "jbr", "JBR-201 A/B 순차 공압 가위 — 절단",
           2, 1, 2,
           "S2 손가락 절단은 비가역이다. F1 가드 안. P2 가위 행정은 사람 반응보다 빠르다"),
    Hazard("HZ-07", "jbr", "JBR 투입·반출 개구부 — 뮤팅 중 사람 진입",
           2, 2, 2,
           f"S2 진입하면 HZ-05·06 을 그대로 만난다. **F2 뮤팅은 패널마다 열린다 — "
           f"투입·반출 합쳐 하루 {muting_cycles_per_day():,} 회다.** "
           "P2 열린 개구를 사람이 따라 들어가면 안에서 멈출 방법이 없다"),
    Hazard("HZ-08", "afr", "AFR-101 25 kN 인발·CL-221 클램프 12 kN — 협착·튕김",
           2, 1, 2,
           "S2 25 kN 은 사람을 잡는다. F1 가드 안. P2 인발은 힘 제어라 "
           "물린 뒤에 멈춰도 이미 늦다"),
    # REV.50: 연마 헤드가 AFR 반출롤러 위에 선다 — 위험원도 afr 존이다.
    Hazard("HZ-09", "afr", "SG-301 연마 회전체 — 말림·비산",
           2, 1, 2,
           "S2 회전체 말림. F1 가드 안. P2 말리면 놓을 수 없다"),
    Hazard("HZ-10", "buffer", "GBR-301 셔틀 주행·슬롯 로더 승강 — 협착·낙하",
           2, 1, 2,
           "S2 적재 캐리지 낙하. F1 가드 안. P2 주행로 위에서는 피할 방향이 좁다"),
    Hazard("HZ-11", "grm", "GRM-401 60-IR 뱅크 고온부 — 접촉 화상",
           2, 1, 1,
           "S2 IR 뱅크 표면 화상은 비가역이다. F1 정비 노출. "
           "P1 열은 접촉 전에 느껴지고 인터록에 냉각 지연이 걸린다"),
    Hazard("HZ-12", "post", "유리 파손 비산 — 눈·피부 열상",
           1, 2, 1,
           "S1 보안경·가드로 막히는 경상이다. F2 파손은 60장 중 5장 몫으로 "
           "설계에 이미 들어 있다. P1 비산 방향이 가드로 제한된다"),
    Hazard("HZ-13", "jbr", "정비 중 예기치 않은 기동 — 공압·유압 잔압",
           2, 1, 2,
           "S2 잔압으로 실린더가 한 번 더 나간다. F1 정비 때. "
           "P2 손을 넣은 상태에서 나가면 피할 수 없다 — 안전 잔압배출 밸브가 그래서 있다"),
    Hazard("HZ-14", "afu", "CRN-901 인양물 낙하 — 운전 중 설비 위 통과",
           2, 1, 2,
           "S2 2,500 kg 낙하. F1 설치·정비 인양 때만. P2 밑에 있으면 끝이다. "
           "**이 위험원은 electrical 의 비동시 전제를 떠받친다** — 규칙이 아니라 "
           "인터록이어야 계약전력 근거가 선다"),
)


def hazards_for(cell: str) -> tuple[Hazard, ...]:
    return tuple(h for h in HAZARDS if h.cell == cell)


def plant_plr() -> str:
    """플랜트 전체가 요구하는 최고 PLr."""
    pl = "a"
    for hazard in HAZARDS:
        pl = higher_pl(pl, hazard.plr)
    return pl


def plr_histogram() -> dict[str, int]:
    """PLr 별 위험원 수 — 어디에 무게가 쏠려 있는지."""
    out = {pl: 0 for pl in PL_ORDER}
    for hazard in HAZARDS:
        out[hazard.plr] += 1
    return out


# ── 안전기능 ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SafetyFunction:
    """안전기능 하나 — 검출 · 논리 · 구동의 사슬."""

    tag: str
    name: str
    hazards: tuple[str, ...]
    detection: str
    logic: str
    actuator: str
    note: str

    @property
    def plr(self) -> str:
        """이 기능이 막는 위험원 중 가장 높은 PLr."""
        served = [h for h in HAZARDS if h.tag in self.hazards]
        assert served, self.tag
        pl = "a"
        for hazard in served:
            pl = higher_pl(pl, hazard.plr)
        return pl

    @property
    def category(self) -> str:
        return PL_CATEGORY[self.plr]


SAFETY_FUNCTIONS: tuple[SafetyFunction, ...] = (
    SafetyFunction(
        "SF-01", "비상정지 (전 셀)",
        ("HZ-02", "HZ-03", "HZ-04", "HZ-05", "HZ-06", "HZ-08", "HZ-09", "HZ-10"),
        "JB-SF-006 이중채널 버튼 · 가드 비상정지",
        "안전 PLC — 하드와이어 + FSoE",
        "전 서보 STO · 공압 덤프 · 주접촉기 개방",
        "정지범주 1 — 제어정지 후 동력차단. 정지범주 0 으로 하면 승강축이 "
        "자유낙하한다(HZ-03)"),
    SafetyFunction(
        "SF-02", "가드 인터록 (정비도어)",
        ("HZ-05", "HZ-06", "HZ-13"),
        "JB-SF-004 가드락 안전인터록 (이중채널)",
        "안전 PLC — 잠금해제는 정지확인 후",
        "STO 유지 · 잔압배출 · 재기동 금지",
        "가드락형이라 문이 열리기 전에 정지가 끝난다 — 정지시간 예산을 "
        "가드락이 흡수하므로 이 기능에는 ISO 13855 거리가 걸리지 않는다"),
    SafetyFunction(
        "SF-03", "투입·반출구 침입 감지",
        ("HZ-05", "HZ-06"),
        "JB-SF-005 Type 4 라이트커튼 (해상도 30 mm)",
        "안전 PLC — OSSD 이중채널",
        "JBR 전 축 STO · 공압 덤프",
        "ISO 13855 정지시간 예산이 걸리는 기능. JB-SF-008 시험포트로 "
        "정기 검증한다"),
    SafetyFunction(
        "SF-04", "뮤팅 — 패널만 통과",
        ("HZ-07",),
        "JB-SF-009 뮤팅 센서쌍 4식 (방향·순서·timeout)",
        "JB-SF-010 전용 뮤팅 컨트롤러",
        "뮤팅 실패 시 즉시 SF-03 복귀",
        "이 플랜트의 유일한 PLe 요구다. 부품표가 뮤팅 센서를 4식으로 잡고 전용 "
        "컨트롤러를 따로 둔 이유가 그것이다. 순서 위반·timeout 초과·센서 단일고장 "
        "어느 하나에도 뮤팅을 걸지 않는다 — 뮤팅은 '보호를 끄는' 기능이라 "
        "고장 시 안전측이 곧 '켜진 채로' 다"),
    SafetyFunction(
        "SF-05", "로봇 작업영역 방호",
        ("HZ-04",),
        "AFU-SF-101 안전 스캐너 · BW-101 안전벽체",
        "안전 PLC — 존별 판정",
        "RB-101 STO · 경고존 감속",
        "경고존·정지존 2단. 감속만으로는 PLd 를 못 만든다 — 정지존이 "
        "PLd 사슬이고 감속존은 가용률을 위한 덤이다"),
    SafetyFunction(
        "SF-06", "AFR·유리후단 방호",
        ("HZ-08", "HZ-09", "HZ-12"),
        "AFR-SF-701 가드·라이트커튼",
        "AFR 안전PLC (FSoE 노드)",
        "AFR·SG·GI 축 STO · 유압 덤프",
        "SG-301 회전체는 관성이 커서 STO 만으로는 즉시 서지 않는다 — "
        "SS1(제어감속 후 STO)이 필요하다"),
    SafetyFunction(
        "SF-07", "버퍼·적재부 방호",
        ("HZ-10",),
        "GBR 버퍼 인터록 센서 · GRM 적재부 안전 스캐너",
        "안전 PLC",
        "GBR·GRM 축 STO",
        "캐리지 교환구역은 뮤팅하지 않는다 — 사람이 캐리지를 직접 다루는 "
        "구역이라 뮤팅 조건 자체가 성립하지 않는다"),
    SafetyFunction(
        "SF-08", "운전 중 인양 금지 인터록",
        ("HZ-14",),
        "CRN-901 급전 접촉기 상태 · 라인 운전 상태",
        "안전 PLC — 상호잠금",
        "인양 중 라인 기동 금지 / 라인 운전 중 크레인 급전 차단",
        "**REV.28 부터 글로만 있던 규칙을 회로로 옮긴다.** 이 인터록이 없으면 "
        "electrical.NON_COINCIDENT_PANELS 의 비동시 전제가 관리 규칙에 불과해 "
        f"동시 최악 {electrical.coincident_worst_case_kw()} kW 의 근거가 무너진다"),
    SafetyFunction(
        "SF-09", "고온부 접근 인터록",
        ("HZ-11",),
        "GRM IR 뱅크 표면온도 · 도어 인터록",
        "안전 PLC — 냉각 지연 타이머",
        "IR 전원 차단 · 냉각 완료까지 도어 잠금",
        "온도가 내려가기 전에는 문이 안 열린다. 지연 타이머가 안전기능의 "
        "일부라 표준 타이머로는 안 된다"),
    SafetyFunction(
        "SF-10", "에너지 격리 — 잔압배출·LOTO",
        ("HZ-13",),
        "안전 잔압배출 밸브 · 잔압 확인 압력스위치",
        "안전 PLC — 배출 확인 후 정비허가",
        "공압·유압 이중 잔압배출",
        "§34 의 에어 덤프가 여기 걸린다 — 컴프레서를 세우는 것과 라인의 "
        "잔압을 빼는 것은 다른 일이다"),
    SafetyFunction(
        "SF-11", "도킹 Bay 방호 — Bay 독립 정지",
        ("HZ-01",),
        "AFU-SF-101 안전 스캐너 (Bay 별 존)",
        "안전 PLC — Bay 별 존 판정",
        "진입한 Bay 의 리프트만 정지 · 반대 Bay 는 계속",
        "BW-101 안전벽체가 Bay 를 나누기 때문에 이 기능이 성립한다. "
        "벽이 없으면 한쪽 반입이 반대쪽 운전을 세워 처리량이 절반이 된다 — "
        "안전벽체는 안전 부품이면서 동시에 가용률 부품이다"),
)


def functions_for(hazard_tag: str) -> tuple[SafetyFunction, ...]:
    return tuple(f for f in SAFETY_FUNCTIONS if hazard_tag in f.hazards)


def uncovered_hazards() -> tuple[str, ...]:
    """어느 안전기능도 안 맡은 위험원 — 있으면 설계 구멍이다."""
    covered = {tag for f in SAFETY_FUNCTIONS for tag in f.hazards}
    return tuple(h.tag for h in HAZARDS if h.tag not in covered)


# ── ISO 13855 정지시간 예산 ──────────────────────────────────────────────
#: 접근속도 K (mm/s). 표준은 두 단계다 — 먼저 2,000 으로 계산하고, 그 결과가
#: 500 mm 를 넘으면 1,600 으로 다시 계산하되 500 mm 밑으로는 못 내린다.
APPROACH_FAST_MM_S = 2_000
APPROACH_SLOW_MM_S = 1_600
APPROACH_SWITCH_MM = 500

#: 라이트커튼 해상도 (mm) — JB-SF-005 부품표의 "해상도 30 mm 이하".
CURTAIN_RESOLUTION_MM = 30


def penetration_mm(resolution_mm: int | None = None) -> int:
    """침입거리 C = 8 × (d − 14), 음수면 0. 손가락·손 검출용 식이다."""
    d = CURTAIN_RESOLUTION_MM if resolution_mm is None else resolution_mm
    return max(0, 8 * (d - 14))


def safety_distance_mm(stop_time_s: float, resolution_mm: int | None = None) -> int:
    """정지시간에서 안전거리 S 를 낸다 (ISO 13855 §6.1)."""
    c = penetration_mm(resolution_mm)
    fast = APPROACH_FAST_MM_S * stop_time_s + c
    if fast <= APPROACH_SWITCH_MM:
        return int(-(-fast // 1))
    slow = APPROACH_SLOW_MM_S * stop_time_s + c
    return int(-(-max(slow, APPROACH_SWITCH_MM) // 1))


def max_stop_time_ms(distance_mm: int, resolution_mm: int | None = None) -> int:
    """거리에서 정지시간 예산을 낸다 — safety_distance_mm 의 역이다.

    가드가 이미 서 있으므로 구할 것은 거리가 아니라 **허용 정지시간**이다.
    시운전에서 잰 값이 이 예산을 넘으면 설계가 틀린 것이지 시험이 틀린 게 아니다.
    """
    c = penetration_mm(resolution_mm)
    if distance_mm <= c:
        return 0
    fast = (distance_mm - c) / APPROACH_FAST_MM_S
    if APPROACH_FAST_MM_S * fast + c <= APPROACH_SWITCH_MM:
        return int(fast * 1000)
    return int((distance_mm - c) / APPROACH_SLOW_MM_S * 1000)


@dataclass(frozen=True)
class Opening:
    """라이트커튼이 지키는 개구 하나.

    좌표는 3D 장면에서 실측한 값이다(월드 m → 도면 mm). 손으로 적은 거리가
    아니라 형상에서 나온 거리라, 가드를 옮기면 예산이 따라 움직인다.
    """

    tag: str
    name: str
    plane_x_mm: int         # 감지면 X (플랜트 좌표)
    hazard_x_mm: int        # 가장 가까운 위험원 X
    hazard_part: str
    note: str

    @property
    def distance_mm(self) -> int:
        return abs(self.hazard_x_mm - self.plane_x_mm)

    @property
    def budget_ms(self) -> int:
        return max_stop_time_ms(self.distance_mm)


#: 3D 실측 — `안전 라이트커튼` · `라이트커튼 감지면` 메시의 월드 X 를
#: 플랜트 좌표로 옮긴 값 (world_x = (plant_x − 24,750)/1,000).
OPENINGS: tuple[Opening, ...] = (
    Opening("OP-IN", "JBR 투입구", 17_820, 18_740,
            "3헤드 공통 승강 플레이트 (HZ-05)",
            "차광 투입 터널 1,180 mm 를 지나 첫 위험동작을 만난다"),
    Opening("OP-OUT", "JBR 반출구", 24_580, 23_740,
            "X축 LM가이드·타이밍벨트 종단 (HZ-05)",
            "반출측은 통합셀 접합부 250 mm 를 사이에 두고 **같은 가드 안에서** "
            "AFR 스테이션이 이어받는다 — 셀 경계가 아니라 셀 내부 인계다"),
)

#: 위험원 판정이 갈리는 자리. 투입구 감지면에서 320 mm 앞에 비전 위치보정
#: 서보가 있다. 그것을 '위험구역' 으로 볼 것인가가 예산을 세 배 이상 바꾼다 —
#: 카메라 정렬용 소형 축이라 ISO 12100 의 위험구역이 아니라고 본 것이 이
#: 설계의 판단이고, 위험성평가 승인자가 뒤집을 수 있는 지점이다.
CONTESTED_HAZARD_MM = 320


def contested_budget_ms() -> int:
    """비전 위치보정 서보까지 위험구역으로 보면 남는 예산."""
    return max_stop_time_ms(CONTESTED_HAZARD_MM)


def contested_mechanical_budget_ms() -> int:
    """그 경우 기계 감속에 남는 시간 — 고정비를 뺀 나머지.

    판정이 뒤집혔을 때 무엇을 해야 하는지가 여기서 정해진다. 사슬 전체를
    줄이라는 말은 뜻이 없다 — 검출·논리·STO 반응은 부품이 정하는 고정비라
    설계가 못 건드린다. 줄일 수 있는 것은 기계 감속 하나뿐이고, 그것을
    줄인다는 것은 **축 속도를 낮춘다**는 뜻이라 택트가 따라 늘어난다.
    """
    return contested_budget_ms() - fixed_chain_ms()


def contested_slowdown_ratio() -> float:
    """기계 감속을 몇 배로 줄여야 하는가 — 1 보다 크면 감속이 더 빨라져야 한다."""
    return round(dict(STOP_CHAIN)[MECHANICAL_STOP_STEP]
                 / max(contested_mechanical_budget_ms(), 1), 1)


#: 정지시간 예산의 내역 (ms). 합이 개구 예산 안에 들어야 한다.
#: 벤더 확정 전 계획값이며, JB-SF-008 이 실측으로 대체한다.
STOP_CHAIN: tuple[tuple[str, int], ...] = (
    ("라이트커튼 응답 (Type 4 · OSSD)", 15),
    ("안전 PLC 논리 (FSoE 왕복 2사이클)", 12),
    ("드라이브 STO 반응", 10),
    ("기계 감속·정지 (SS1)", 250),
)


#: 사슬에서 기계가 실제로 서는 데 쓰는 항. 나머지(검출·논리·STO 반응)는
#: 부품이 정하는 고정비라 설계로 줄일 수 있는 폭이 아니다.
MECHANICAL_STOP_STEP = "기계 감속·정지 (SS1)"


def stop_chain_ms() -> int:
    return sum(ms for _, ms in STOP_CHAIN)


def fixed_chain_ms() -> int:
    """기계 감속을 뺀 고정비 — 검출·논리·STO 반응."""
    return stop_chain_ms() - dict(STOP_CHAIN)[MECHANICAL_STOP_STEP]


def openings_have_budget() -> bool:
    """모든 개구가 정지 사슬을 감당하는가."""
    return all(op.budget_ms >= stop_chain_ms() for op in OPENINGS)


def tightest_opening() -> Opening:
    return min(OPENINGS, key=lambda op: op.budget_ms)


# ── 안전 I/O ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SafetyDevice:
    """안전 장치 한 종류 — 점수는 채널 수이지 대수가 아니다."""

    tag: str
    name: str
    qty: int
    inputs_each: int        # 이중채널이면 2
    outputs_each: int
    fsoe_node: bool
    note: str

    @property
    def inputs(self) -> int:
        return self.qty * self.inputs_each

    @property
    def outputs(self) -> int:
        return self.qty * self.outputs_each


SAFETY_DEVICES: tuple[SafetyDevice, ...] = (
    SafetyDevice("JB-SF-004", "가드락 안전인터록", 1, 2, 1, False,
                 "이중채널 입력 + 잠금 솔레노이드 출력"),
    SafetyDevice("JB-SF-005", "Type 4 라이트커튼", 4, 2, 0, False, "OSSD 2채널"),
    SafetyDevice("JB-SF-006", "비상정지·3색 표시등", 2, 2, 3, False,
                 "이중채널 접점 + 표시등 3색 (표시등은 안전출력 아님, 점수만 잡는다)"),
    SafetyDevice("JB-SF-009", "안전 뮤팅 센서쌍", 4, 2, 0, False,
                 "쌍당 센서 2개 · 각 1채널"),
    SafetyDevice("JB-SF-010", "뮤팅 컨트롤러·표시등", 1, 0, 1, True,
                 "뮤팅 램프는 표준이 요구하는 필수 출력이다"),
    SafetyDevice("AFU-SF-101", "안전 스캐너 (도킹 Bay)", 2, 2, 0, True, "존 전환 포함"),
    SafetyDevice("AFR-SF-701", "AFR 가드·라이트커튼", 1, 4, 0, True,
                 "가드 인터록 2 + 커튼 OSSD 2"),
    SafetyDevice("GBR-SF-301", "버퍼 인터록 센서", 1, 2, 0, False, ""),
    SafetyDevice("GRM-SF-401", "적재부 안전 스캐너", 1, 2, 0, True, ""),
    SafetyDevice("JBR-SF-011", "리젝트 게이트·버퍼 인터록", 2, 2, 0, False, ""),
    SafetyDevice("UT-SF-012", "안전 잔압배출 밸브·압력스위치", 2, 1, 1, False,
                 "배출 확인 입력 + 덤프 출력"),
    SafetyDevice("CRN-SF-013", "크레인 급전 접촉기 상태·차단", 1, 2, 1, False,
                 "SF-08 상호잠금 — 이 두 점이 계약전력 근거를 떠받친다"),
    SafetyDevice("GRM-SF-014", "IR 고온부 도어 인터록·온도", 1, 3, 1, False,
                 "도어 2채널 + 온도 1점, 냉각 완료 잠금 출력"),
)


def safety_inputs() -> int:
    return sum(d.inputs for d in SAFETY_DEVICES)


def safety_outputs() -> int:
    return sum(d.outputs for d in SAFETY_DEVICES)


def fsoe_device_nodes() -> int:
    """FSoE 슬레이브가 되는 안전 장치 수."""
    return sum(1 for d in SAFETY_DEVICES if d.fsoe_node)


def sto_nodes(axes: tuple[servos.Axis, ...] | None = None) -> int:
    """STO 를 받는 드라이브 수 — 서보 축 수와 같다.

    상수로 박으면 축이 늘어도 안 는다. 축 목록을 인자로 받는 이유가 그것이고,
    시험이 목록을 늘려 답이 따라 오는지를 본다.
    """
    return sum(axis.qty for axis in (servos.SERVO_AXES if axes is None else axes))


def fsoe_nodes(axes: tuple[servos.Axis, ...] | None = None) -> int:
    """FSoE 링에 올라가는 안전 노드 총수."""
    return fsoe_device_nodes() + sto_nodes(axes)


#: 안전 I/O 모듈 1장의 점수 (관례적 8점 모듈).
IO_MODULE_POINTS = 8

#: 예비율 — 시운전에서 안전 I/O 는 늘 는다. 20 % 는 관례값이다.
IO_SPARE = 0.20


def io_modules(points: int) -> int:
    """점수를 모듈 수로 — 예비율을 얹고 올림."""
    need = points * (1 + IO_SPARE)
    return int(-(-need // IO_MODULE_POINTS))


def io_summary() -> dict[str, int]:
    """PLC-IO-7101 이 실어야 하는 것."""
    return {
        "inputs": safety_inputs(),
        "outputs": safety_outputs(),
        "input_modules": io_modules(safety_inputs()),
        "output_modules": io_modules(safety_outputs()),
        "fsoe_device_nodes": fsoe_device_nodes(),
        "sto_nodes": sto_nodes(),
        "fsoe_nodes": fsoe_nodes(),
    }


#: ISO 13849-1 이 정하는 사명시간 (년). PL 은 이 기간 동안 유지돼야 한다.
MISSION_TIME_YEARS = 20


def cycles_per_year(cycles_per_day: int | None = None) -> int:
    """n_op — 연간 동작 횟수. 기본은 뮤팅 사이클이다."""
    per_day = muting_cycles_per_day() if cycles_per_day is None else cycles_per_day
    return per_day * smart.OPERATING_DAYS_PER_YEAR


def t10d_years(b10d: int, cycles_per_day: int | None = None) -> float:
    """T10d = B10d / (0.1 × n_op) — 10 % 가 위험고장에 이르는 시점.

    벤더가 B10d 를 주면 이 식이 교체주기를 낸다. 사명시간 20년보다 짧으면
    그 부품은 **예방교체 대상**이고, 그 사실이 §44 예비품 목록으로 넘어간다.
    B10d 를 여기서 지어내지 않는 이유는 그것이 부품 선정의 결과이지 설계
    입력이 아니기 때문이다.
    """
    return round(b10d / (0.1 * cycles_per_year(cycles_per_day)), 1)


def needs_scheduled_replacement(b10d: int, cycles_per_day: int | None = None) -> bool:
    """사명시간 안에 T10d 가 오는가 — 오면 정기교체가 PL 유지의 조건이다."""
    return t10d_years(b10d, cycles_per_day) < MISSION_TIME_YEARS


# ── SISTEMA 로 넘길 것 ───────────────────────────────────────────────────
#: 여기서 못 내는 값과 그 이유. 빈칸을 빈칸으로 두는 것이 채우는 것보다 낫다.
SISTEMA_INPUTS: tuple[tuple[str, str], ...] = (
    ("B10d", "각 안전부품(인터록·버튼·밸브)의 벤더값. 사이클 수 n_op 는 "
             "muting_cycles_per_day() 가 낸다 — 그 값이 T10d 교체주기를 정한다"),
    ("MTTFd", "채널별 평균 위험고장시간 — 부품 확정 전에는 못 낸다"),
    ("DC", "진단범위. 이중채널 교차감시·잔압 확인·뮤팅 순서감시가 근거가 된다"),
    ("CCF", "공통원인고장 점수 — 배선 분리·과전압 보호 등 65점 체크리스트"),
    ("PFHd", "위 넷에서 SISTEMA 가 낸다. **이 모듈은 PFHd 를 내지 않는다**"),
)


def summary() -> dict[str, object]:
    """도면 리터럴이 받아 가는 값.

    키는 도면 쪽 표기(camelCase)를 따른다 — 이 사전이 그대로 `var SAFETY`
    가 되므로, 여기서 파이썬 표기를 쓰면 도면 생성기가 이름을 한 번 더
    옮겨 적게 되고 그 옮겨 적기가 곧 두 번째 진실이 된다.
    """
    op = tightest_opening()
    hist = plr_histogram()
    return {
        "hazards": len(HAZARDS),
        "functions": len(SAFETY_FUNCTIONS),
        "plantPlr": plant_plr(),
        "plrA": hist["a"], "plrB": hist["b"], "plrC": hist["c"],
        "plrD": hist["d"], "plrE": hist["e"],
        "resolutionMm": CURTAIN_RESOLUTION_MM,
        "penetrationMm": penetration_mm(),
        "approachFastMmS": APPROACH_FAST_MM_S,
        "approachSlowMmS": APPROACH_SLOW_MM_S,
        "approachSwitchMm": APPROACH_SWITCH_MM,
        "stopChainMs": stop_chain_ms(),
        "tightestOpening": op.tag,
        "tightestBudgetMs": op.budget_ms,
        "contestedMm": CONTESTED_HAZARD_MM,
        "contestedBudgetMs": contested_budget_ms(),
        "fixedChainMs": fixed_chain_ms(),
        "contestedMechanicalMs": contested_mechanical_budget_ms(),
        "contestedSlowdown": contested_slowdown_ratio(),
        "mutingCyclesPerDay": muting_cycles_per_day(),
        "cyclesPerYear": cycles_per_year(),
        "missionYears": MISSION_TIME_YEARS,
        "inputs": safety_inputs(),
        "outputs": safety_outputs(),
        "inputModules": io_modules(safety_inputs()),
        "outputModules": io_modules(safety_outputs()),
        "ioModulePoints": IO_MODULE_POINTS,
        "ioSparePct": int(IO_SPARE * 100),
        "fsoeDeviceNodes": fsoe_device_nodes(),
        "stoNodes": sto_nodes(),
        "fsoeNodes": fsoe_nodes(),
    }
