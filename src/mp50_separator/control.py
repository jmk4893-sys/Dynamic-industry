"""MP-50 제어반 (J-06) — 동시 OFF 회로와 운전 시퀀스.

임펠러와 급기의 **동시 차단**이 이 장치의 핵심 동작이다. 둘이 몇 초라도
어긋나면 잔류 와류나 잔류 기포가 층분리를 흐트러뜨려 정치 t=0 이 정의되지
않는다. 그러면 DOE 의 정치시간 축이 통째로 못 쓰게 된다.

그래서 이 반은 두 가지를 구조로 강제한다.

1. **하나의 접점이 둘을 문다.** 운전 릴레이 CR1 의 a 접점 하나가 VFD 의
   RUN 입력을, 다른 하나가 급기 솔레노이드 코일을 잡는다. CR1 이 떨어지면
   두 출력이 같은 순간에 끊긴다. 버튼을 둘로 나누면 사람이 누르는 순서가
   데이터에 섞인다.
2. **분산시간은 사람이 아니라 타이머가 끊는다.** TIM1 이 시간 종료로 CR1
   유지회로를 열어 동시 OFF 를 만든다. 수동 버튼은 그와 직렬로 병치해 조기
   차단만 할 수 있게 둔다 — 조건표대로 돌리면 배치마다 분산시간이 같다.

VFD 정지방식은 **프리런(코스트)** 이다. 램프 정지를 쓰면 감속하는 동안
임펠러가 계속 저어서 t=0 이 흐려진다. 출력을 즉시 끊고 유체가 세우게 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .checks import DESIGN_MAX_RPM, DOE_SETTLING_MAX_S, GEARBOX_MAX_RPM
from .geometry import GEOMETRY

#: 모터 명판 — CHK-06 이 0.37 kW 를 탈락시키고 고른 값.
MOTOR_KW = 0.55
MOTOR_POLES = 4
MAINS_HZ = 60.0
MAINS_V = 380.0
#: 4 극 유도전동기의 정격 회전수 (슬립 약 3 %).
MOTOR_RATED_RPM = 120.0 * MAINS_HZ / MOTOR_POLES * 0.97

#: 제어전원. 젖은 파일럿이라 제어회로는 저전압으로 내린다.
CONTROL_V = 24.0
#: 축 최저 회전수 — DOE 하한.
SHAFT_MIN_RPM = 30.0

#: 감속비 후보. 벤더 GA 로 확정되지만, 표준 감속비 가운데 축 150 rpm 을
#: 낼 수 있는 것은 1/10 뿐이다 — 1/15 는 60 Hz 에서도 117 rpm 에 그친다.
GEAR_RATIOS = (10.0, 15.0, 20.0)
RECOMMENDED_RATIO = 10.0


def shaft_rpm(hz: float, ratio: float = RECOMMENDED_RATIO) -> float:
    """VFD 출력 주파수에서 나오는 교반축 회전수."""
    return MOTOR_RATED_RPM * (hz / MAINS_HZ) / ratio


def vfd_hz(rpm: float, ratio: float = RECOMMENDED_RATIO) -> float:
    """교반축 회전수를 내는 VFD 출력 주파수."""
    return MAINS_HZ * rpm * ratio / MOTOR_RATED_RPM


@dataclass(frozen=True)
class Terminal:
    """제어반 단자 하나."""

    no: str
    kind: str          # 전원 / DI / DO / AI / AO
    name: str
    to: str            # 접속처
    note: str


@dataclass(frozen=True)
class Step:
    """운전 시퀀스의 한 단계."""

    no: str
    name: str
    impeller: str
    air: str
    ends_by: str
    note: str


@dataclass(frozen=True)
class PanelItem:
    """제어반 구성품."""

    tag: str
    name: str
    spec: str
    qty: int
    note: str


#: 단자표. 제어반 제작사가 그대로 배선하는 목록이다.
TERMINALS: tuple[Terminal, ...] = (
    Terminal("L1·L2·L3·PE", "전원", "주회로 입력",
             f"배전반 {MAINS_V:.0f} V 3φ", "MCCB 1 차. 누전차단 30 mA"),
    Terminal("U·V·W·PE", "전원", "VFD 출력 → 모터",
             "C-01 기어드 모터", "차폐 케이블. 실드는 반 쪽 1 점 접지"),
    Terminal("24V·0V", "전원", f"제어전원 DC {CONTROL_V:.0f} V",
             "SMPS 2 차", "젖은 자리라 제어는 저전압으로 내린다"),
    Terminal("X1·X2", "DI", "운전 (자기유지 기동)",
             "PB1 녹색 a 접점", "누르면 CR1 여자 · 자기유지"),
    Terminal("X3·X4", "DI", "동시 OFF (수동)",
             "PB2 적색 b 접점", "CR1 유지회로를 연다 — 조기 차단용"),
    Terminal("X5·X6", "DI", "비상정지",
             "EMS 버섯형 b 접점 2 회로", "제어전원을 끊는다. 복귀는 수동"),
    Terminal("Y1·Y2", "DO", "VFD RUN 지령",
             "VFD DI1 (무전압 a 접점)", "CR1-1. 떨어지면 프리런 정지"),
    Terminal("Y3·Y4", "DO", "급기 솔레노이드",
             "SOL 코일 DC 24 V", "CR1-2. NC 형이라 소자되면 닫힌다"),
    Terminal("Y5·Y6", "DO", "정치 t=0 마크",
             "J-07 로거 DI", "CR1-3. 로거에 차단 시각을 찍는다"),
    Terminal("X7·X8", "DI", "사이클 리셋",
             "PB3 청색 b 접점", "CR2 래치를 푼다. 다음 배치 전에 누른다"),
    Terminal("Y7·Y8", "DO", "정치 종료 부저·램프",
             "BZ1 · PL3", "TIM2 시간종료 — 배출 준비"),
    Terminal("A1·A2", "AO", "VFD 전류 출력 4~20 mA",
             "J-07 로거 AI", "[R] §15 필수 데이터. 분산 상태의 상시 신호"),
    Terminal("A3·A4", "AI", "속도 지령 (선택)",
             "VFD AI1", "반 전면 포텐셔미터. 조건표 회전수를 맞춘다"),
)

#: 운전 시퀀스. 정치시간 격자는 CHK-10 의 권고를 따른다.
SEQUENCE: tuple[Step, ...] = (
    Step("S1", "장입", "정지", "닫힘", "수동",
         "염수와 블랙파우더를 N1 으로 넣는다. 액면 Z720 (61.4 L)"),
    Step("S2", "분산", "운전", "열림", "TIM1 시간종료",
         "조건표의 회전수와 급기량으로 돌린다. 시간은 타이머가 끊는다"),
    Step("S3", "동시 OFF", "프리런 정지", "즉시 닫힘", "즉시 (같은 접점)",
         "CR1 하나가 둘을 동시에 끊는다. 이 순간이 정치 t=0 이다"),
    Step("S4", "정치", "정지", "닫힘", "TIM2 시간종료",
         "자연 부상·침강. 건드리지 않는다"),
    Step("S5", "회수", "정지", "닫힘", "수동",
         "부상물은 N2 · 스키머로, 침강물은 콘 배출로. 시료는 N4A~E"),
)

#: 제어반 구성품. 반 제작사가 이 사양으로 짠다.
PANEL_BOM: tuple[PanelItem, ...] = (
    PanelItem("QF1", "주차단기", f"3P {MAINS_V:.0f} V · 누전차단 30 mA · 10 A", 1,
              "VFD 입력 보호"),
    PanelItem("INV", "VFD", f"정토크 {MOTOR_KW:.2f} kW 이상 (프레임 0.75 kW) · 3φ {MAINS_V:.0f} V", 1,
              "정지방식 프리런 · 전류 아날로그 출력 필수"),
    PanelItem("PS1", "SMPS", f"DC {CONTROL_V:.0f} V 2 A", 1, "제어전원"),
    PanelItem("CR1", "운전 릴레이", f"DC {CONTROL_V:.0f} V · 4a 접점", 1,
              "**동시 OFF 의 본체.** 접점 하나가 VFD, 하나가 SOL 을 문다"),
    PanelItem("TIM1", "분산 타이머", "ON 딜레이 0.1~99.9 분", 1,
              "시간종료로 CR1 유지회로를 연다 — 분산시간을 사람이 정하지 않는다"),
    PanelItem("CR2", "사이클 래치", f"DC {CONTROL_V:.0f} V · 2a 접점", 1,
              "운전 시작에 래치되고 리셋으로 풀린다. 정치 타이머가 배치 전에 "
              "미리 돌지 않게 막는다"),
    PanelItem("TIM2", "정치 타이머", f"ON 딜레이 1~9999 s ({DOE_SETTLING_MAX_S:.0f}~3600 격자)", 1,
              "CR2 래치 상태에서 CR1 이 떨어진 순간부터 센다"),
    PanelItem("PB1", "운전 버튼", "녹색 a 접점 · 램프 내장", 1, "자기유지 기동"),
    PanelItem("PB2", "동시 OFF 버튼", "적색 b 접점 · Ø30", 1,
              "수동 조기 차단. 비상정지와 구분해 따로 둔다"),
    PanelItem("PB3", "리셋 버튼", "청색 b 접점", 1,
              "CR2 래치 해제 · 부저 정지. 다음 배치 전에 누른다"),
    PanelItem("EMS", "비상정지", "버섯형 래치 · b 접점 2 회로", 1,
              "제어전원 차단. 동시 OFF 와 같은 버튼으로 쓰지 않는다"),
    PanelItem("SOL", "급기 솔레노이드", f"2 포트 NC · DC {CONTROL_V:.0f} V · ½\"", 1,
              "소자되면 닫힌다 — 정전에도 공기가 들어가지 않는다"),
    PanelItem("PL1~3", "표시등", f"DC {CONTROL_V:.0f} V · 전원 / 운전 / 정치종료", 3, "-"),
    PanelItem("BZ1", "부저", f"DC {CONTROL_V:.0f} V", 1, "정치 종료 알림"),
    PanelItem("VR1", "속도 설정기", "1 kΩ 포텐셔미터 + 눈금판", 1,
              "조건표 회전수를 맞춘다. 실측은 J-07 전류로 남긴다"),
)

#: VFD 설정값. 회전수 관련은 감속비가 정해져야 확정된다.
VFD_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    ("정지방식", "프리런 (코스트)",
     "램프 정지는 감속 중에도 저어서 정치 t=0 을 흐린다"),
    ("가속시간", "10 s", "정지층을 한 번에 들어올리지 않는다"),
    ("감속시간", "사용 안 함", "프리런이므로 적용되지 않는다"),
    ("V/f 특성", "정토크",
     f"재기동 토크 17.1 N·m 가 모터를 정한다 (CHK-06). 저속에서 토크가 빠지면 안 된다"),
    ("최저 주파수", f"{vfd_hz(SHAFT_MIN_RPM):.1f} Hz",
     f"축 {SHAFT_MIN_RPM:.0f} rpm — 감속비 1/{RECOMMENDED_RATIO:.0f} 기준"),
    ("최고 주파수", f"{vfd_hz(DESIGN_MAX_RPM):.1f} Hz",
     f"축 {DESIGN_MAX_RPM:.0f} rpm — 상한 {GEARBOX_MAX_RPM:.0f} rpm 으로는 Njs 를 못 넘는다 (CHK-05)"),
    ("전자 서멀", f"{MOTOR_KW:.2f} kW 명판 전류", "저속 연속운전 보호"),
    ("아날로그 출력", "출력전류 4~20 mA", "J-07 로깅 ([R] §15)"),
    ("재기동", "정전 복귀 시 자동기동 금지",
     "CR1 이 자기유지라 전원이 끊기면 스스로 떨어진다 — 구조로 막는다"),
)


def timing() -> tuple[tuple[str, tuple[int, ...]], ...]:
    """타임차트용 신호별 on/off — 시퀀스에서 유도한다.

    그림에 손으로 적으면 시퀀스를 고칠 때 그림만 옛 값으로 남는다. 임펠러와
    급기는 ``SEQUENCE`` 의 상태 낱말에서 그대로 읽고, CR1 은 그 둘을 무는
    접점이므로 임펠러와 같은 파형이다. TIM2 는 CR1 이 떨어진 단계부터
    시간종료를 알리는 단계까지 센다.
    """
    imp = tuple(int(s.impeller == "운전") for s in SEQUENCE)
    air = tuple(int(s.air == "열림") for s in SEQUENCE)
    if 1 not in imp:
        raise ValueError("시퀀스에 임펠러 운전 단계가 없다")
    start = imp.index(1)
    stop = start + imp.count(1)                # 임펠러가 멎는 단계
    if imp[start:stop] != (1,) * (stop - start):
        raise ValueError("임펠러 운전 단계가 이어지지 않는다 — 타임차트가 성립하지 않는다")
    last = max(i for i, s in enumerate(SEQUENCE) if "TIM2" in s.ends_by)
    tim2 = tuple(int(stop <= i <= last) for i in range(len(SEQUENCE)))
    return (("임펠러", imp), ("급기 SOL", air), ("CR1", imp), ("TIM2", tim2))


def ratio_table() -> tuple[tuple[str, str, str, str], ...]:
    """감속비 후보별로 축 회전수 범위가 나오는지 따진다.

    축 150 rpm 은 CHK-05 의 권고값이고 여기서 감속비가 갈린다.
    """
    rows = []
    for i in GEAR_RATIOS:
        top = shaft_rpm(MAINS_HZ, i)
        hz_min = vfd_hz(SHAFT_MIN_RPM, i)
        ok = "가능" if top >= DESIGN_MAX_RPM else f"불가 — {DESIGN_MAX_RPM:.0f} rpm 못 냄"
        rows.append((f"1/{i:.0f}", f"{top:.0f} rpm", f"{hz_min:.1f} Hz", ok))
    return tuple(rows)


def summary() -> dict[str, str]:
    """제어반 한 줄 요약 — 도면과 시험이 같은 값을 본다."""
    return {
        "모터": f"{MOTOR_KW:.2f} kW · {MOTOR_POLES} 극 · 3φ {MAINS_V:.0f} V",
        "제어전원": f"DC {CONTROL_V:.0f} V",
        "축 회전수": f"{SHAFT_MIN_RPM:.0f}~{DESIGN_MAX_RPM:.0f} rpm",
        "VFD 주파수": f"{vfd_hz(SHAFT_MIN_RPM):.1f}~{vfd_hz(DESIGN_MAX_RPM):.1f} Hz",
        "감속비": f"1/{RECOMMENDED_RATIO:.0f} (벤더 GA 로 확정)",
        "정지방식": "프리런 (코스트)",
        "동시 OFF": "CR1 단일 접점 — VFD RUN 과 SOL 을 함께 끊는다",
        "급기": f"최대 {GEOMETRY.air_max_lpm:.0f} L/min · SOL 은 NC",
        "정치시간": f"{DOE_SETTLING_MAX_S:.0f}~3600 s (CHK-10)",
    }
