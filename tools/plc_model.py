#!/usr/bin/env python3
"""DG-HK60 인터록을 실제로 돌려 보는 모델.

이 저장소의 'PLC 프로그램'은 콘솔과 사양서에 흩어져 있는 허가·트립 논리식이다.
글로만 있으면 다음 두 가지가 조용히 지나간다.

  1. 논리식이 부르는데 현장에 그 신호를 만들 장치가 없다.
     — 예: IR_HARD_TRIP 이 SSR_STUCK 을 읽는데 SSR 피드백 장치가 없으면
       그 트립은 영원히 성립하지 않는다. 화면에는 아무 표시도 안 난다.
  2. 장치는 서 있는데 어떤 논리식도 그 신호를 쓰지 않는다.
     — 돈 들여 달아 놓고 제어에 반영이 안 된 상태다.

그래서 신호마다 '이 신호를 만드는 현장 장치'와 'I/O 종류'를 적어 두고,
장치 이름이 3D 모델(콘솔)에 실제로 있는지 대조한다. 계산이 아니라 대조라서
한쪽만 고치면 반드시 걸린다.

    python3 tools/plc_model.py            # 보고서
    python3 tools/plc_model.py --check    # 미해결이 있으면 1 로 종료 (CI 용)
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"

# ── I/O 종류 ────────────────────────────────────────────────────────────
DI, DO, AI, AO, TC = "DI", "DO", "AI", "AO", "TC"
FDI, FDO, COMM = "F-DI", "F-DO", "COMM"

# 선언된 I/O 예산 (콘솔 PLC 도면 · 사양서 7.1)
# 선언된 I/O 예산. 사양서 7.1 이 "예비 20% 이상"을 요구하므로 실사용에서
# 역산해 카드 배수로 올린 값이다 — 이 모델을 돌려 정한 수량이다.
BUDGET = {DI: 160, DO: 80, AI: 40, AO: 16, TC: 48, FDI: 32, FDO: 8}
SPARE_MIN = 0.20                       # 사양서 7.1 이 요구하는 최소 예비율


class Leaf:
    """현장 장치가 만드는 신호."""

    def __init__(self, name, io, count, device, note=""):
        self.name, self.io, self.count, self.device, self.note = name, io, count, device, note


class Derived:
    """다른 신호에서 계산되는 신호."""

    def __init__(self, name, terms, note=""):
        self.name, self.terms, self.note = name, terms, note


class Drive:
    """구동부 — 모터·서보·실린더. 출력 점수와 안전정지 수단을 함께 적는다."""

    def __init__(self, tag, name, io, count, stop, device):
        self.tag, self.name, self.io, self.count = tag, name, io, count
        self.stop, self.device = stop, device


# ── 현장 입력 ───────────────────────────────────────────────────────────
LEAVES = [
    # 전원·제어
    Leaf("MAIN_ACB_ON",        DI, 1, "Q0 ACB 4P 800AF"),
    Leaf("PHASE_OK",           COMM, 0, "전력품질계"),
    Leaf("PE_OK",              DI, 1, "접지바"),
    Leaf("SPD_OK",             DI, 1, "SPD Type1+2"),
    Leaf("UPS_OK",             DI, 1, "UPS-101"),
    Leaf("DC24_A_OK",          DI, 1, "24VDC PSU A/B"),
    Leaf("DC24_B_OK",          DI, 1, "24VDC PSU A/B"),
    Leaf("SAFETY_CPU_OK",      COMM, 0, "PLC-101반"),
    Leaf("NETWORK_RING_OK",    COMM, 0, "PLC-101반"),
    Leaf("PM_METER_OK",        COMM, 0, "전력품질계"),
    # 가열실
    Leaf("C1_PRESENT",         DI, 5, "캐리지 존재센서×5", "C1~C5 각 1점"),
    Leaf("ALL_DECK_LOCKED",    DI, 5, "층별 잠금실린더×5"),
    Leaf("ACTIVE_DECK_PRESENT", DI, 1, "캐리지 존재센서×5"),
    Leaf("ACTIVE_DECK_LOCKED", DI, 1, "층별 잠금실린더×5"),
    Leaf("EVA_INTERFACE_200_ACK", TC, 15, "EVA 계면센서×5", "캐리지별 K열전대 3점"),
    Leaf("ALL_TEMP_OK",        TC, 5, "표면 IR 센서×5"),
    Leaf("INDEPENDENT_OVERTEMP", FDI, 1, "독립 과온센서", "하드와이어 · IR 주접촉기 직접 차단"),
    Leaf("SSR_STUCK",          DI, 6, "IR 뱅크 CT·SSR 피드백×6", "IR 뱅크 B0~B5 각 1점"),
    Leaf("DP_OK",              AI, 1, "차압센서×3"),
    Leaf("INNER_DOOR_OPEN",    FDI, 4, "에어록 도어 위치센서×8"),
    Leaf("OUTER_DOOR_OPEN",    FDI, 4, "에어록 도어 위치센서×8"),
    Leaf("FORK_HOME",          DI, 1, "TS-101 2단 포크"),
    Leaf("FORK_RETRACTED",     DI, 1, "TS-101 2단 포크"),
    Leaf("EXTRACTOR_HOME",     DI, 1, "TS-101 2단 포크"),
    Leaf("DOOR_LOCKED",        FDI, 4, "인터록 도어×4"),
    Leaf("AL102_EMPTY",        DI, 2, "격리실 존재센서×2"),
    Leaf("OUTER_OUT_CLOSED",   FDI, 0, "에어록 도어 위치센서×8"),
    # 진공 캐리어·이송축
    Leaf("VAC_6ZONE_OK",       AI, 6, "진공압센서×6"),
    Leaf("PANEL_VAC_OK",       AI, 1, "진공압센서×6"),
    Leaf("X_LEFT",             COMM, 0, "절대치 엔코더"),
    Leaf("X_RIGHT",            COMM, 0, "절대치 엔코더"),
    Leaf("FOLLOWING_ERROR_OK", COMM, 0, "서보 랙피니언"),
    Leaf("CARRIER_SQUARE",     DI, 4, "패널 착좌·스퀘어 센서×4"),
    Leaf("TRACK_CLEAR",        DI, 2, "주행로 광전센서×2"),
    # 탠덤
    Leaf("HKB_TEMP_OK",        TC, 4, "칼날 열전대×8"),
    Leaf("HKS_TEMP_OK",        TC, 4, "칼날 열전대×8"),
    Leaf("KNIFE_OVERLOAD",     AI, 4, "로드셀×4"),
    Leaf("HKB_LOAD_OK",        AI, 0, "로드셀×4"),
    Leaf("AE_OK",              AI, 2, "AE 센서×4"),
    Leaf("AE_CRACK",           AI, 0, "AE 센서×4"),
    Leaf("CASSETTE_LOCKED",    DI, 2, "카세트 잠금·존재센서×4"),
    Leaf("KNIVES_CLEAR",       DI, 4, "칼날 Z축 상하한센서×4"),
    Leaf("LEAD_300_ACK",       COMM, 0, "백시트 끝단 비전"),
    Leaf("CELL_PATH_CLEAR",    DI, 2, "셀 경로 광전센서×2"),
    # 권취·반출
    Leaf("CLAMP_CLOSED",       DI, 4, "분할클램프×4"),
    Leaf("WEB_TENSION_OK",     AI, 1, "장력 로드셀"),
    Leaf("WEB_BREAK",          DI, 1, "웹 파단 검출센서"),
    Leaf("BACKSHEET_FULL_ACK", DI, 1, "백시트 끝단 비전"),
    Leaf("ROLL_ISOLATED",      DI, 2, "격리셔터 위치센서×2"),
    Leaf("SHUTTER_CLOSED",     DI, 2, "격리셔터 위치센서×2"),
    Leaf("CARRIAGE_OUT",       DI, 2, "롤 반출 위치센서×2"),
    Leaf("BIN_READY",          DI, 2, "BS-301 새들 존재센서×2"),
    Leaf("T2_READY",           TC, 0, "칼날 열전대×8", "HKS 온도에서 파생"),
    # 셀/EVA 반출
    Leaf("CELL_BUFFERED",      DI, 4, "셀 존재센서×4"),
    Leaf("CV_CLEAR",           DI, 2, "벨트 편심센서×2"),
    Leaf("CVC_CLEAR",          DI, 2, "셀 존재센서×4"),
    Leaf("SHREDDER_READY",     COMM, 0, "SH-101 투입롤러"),
    Leaf("SHREDDER_TRIP",      DI, 1, "토크리미터"),
    Leaf("FIRE_BACKFLOW",      DI, 1, "역화격리게이트"),
    Leaf("ISOLATION_GATE_OPEN", DI, 2, "역화격리게이트"),
    # 유리·검사
    Leaf("GLASS_CRACK",        DI, 2, "파손 감지센서"),
    Leaf("LEVEL_ROLLER_READY", DI, 2, "동일높이 인계롤러"),
    Leaf("GC_PRESENT_LOCKED",  DI, 4, "도킹핀×4"),
    Leaf("GC_A_COOLING",       TC, 4, "GC 캐리지 온도센서×4"),
    Leaf("GC_B_EMPTY_LOCKED",  DI, 2, "GC-301B 캐리지"),
    Leaf("SURFACE_TEMP_SAFE",  COMM, 0, "열화상카메라"),
    Leaf("DOCK_LOCKED",        DI, 2, "도킹핀×4"),
    Leaf("ZERO_DROP_PATH_CLEAR", DI, 2, "유리 경로 광전센서×3"),
    Leaf("CROSS_TRANSFER_CLEAR", DI, 2, "GC 교대 광전센서×2"),
    Leaf("QI_FAIL",            COMM, 0, "QI 상부 RGB 카메라"),
    Leaf("RJ_CARRIAGE_PRESENT", DI, 1, "캐리지 존재센서"),
    Leaf("RJ_DOOR_LOCKED",     FDI, 1, "도어인터록"),
    Leaf("GLASS_PATH_CLEAR",   DI, 1, "유리 경로 광전센서×3"),
    # 배기·화재·환경
    Leaf("FAN_A_OK",           DI, 1, "배기팬 A"),
    Leaf("FAN_B_OK",           DI, 1, "배기팬 B"),
    Leaf("CARBON_DP_OK",       AI, 1, "차압센서×3"),
    Leaf("FIRE_DAMPER_OPEN",   FDI, 2, "방화댐퍼 위치센서×2"),
    Leaf("SMOKE",              FDI, 2, "연기센서"),
    Leaf("CO_HIGH",            AI, 1, "CO센서"),
    Leaf("EXHAUST_LOSS",       AI, 1, "풍량센서"),
    Leaf("FIRE_OK",            FDI, 1, "불꽃센서"),
    # 안전
    Leaf("LC_OSSD_CLEAR",      FDI, 4, "안전 광커튼 LC-001/002", "LC-001/002 각 OSSD 2채널"),
    Leaf("MUTE_SENSORS",       DI, 8, "뮤팅 센서 M1~M4×2조", "개구부 2곳 × M1~M4"),
    Leaf("ZERO_ENERGY_ACK",    DI, 4, "LOTO 스테이션"),
    Leaf("LOTO_APPLIED",       DI, 4, "LOTO 스테이션"),
    Leaf("TEMP_SAFE",          TC, 0, "표면 IR 센서×5", "ALL_TEMP_OK 와 같은 점을 읽는다"),
    Leaf("VAC_DUMPED",         AI, 1, "진공압센서×6"),
    Leaf("ST_TOWER_CMD",       FDO, 0, "적층 신호등·부저 ST-101/102",
         "HORN_3S·BEACON_AMBER 는 입력이 아니라 F-DO 출력이다"),
    # ── 계량·물질수지 ───────────────────────────────────────────────────
    # 회수율은 재활용사가 정산받는 지표인데, 무게를 재지 않으면 주장할 근거가
    # 없다. 투입 1점과 반출 3계통을 모두 재야 물질수지가 닫힌다.
    Leaf("LOT_ID_VALID",       COMM, 0, "바코드 리더"),
    Leaf("PANEL_MASS_IN",      AI, 1, "WI-101 투입 계량 컨베이어", "로드셀 4점 합산"),
    Leaf("WI_TARE_OK",         DI, 1, "WI-101 투입 계량 컨베이어"),
    Leaf("ROLL_MASS",          AI, 1, "WO-301 권취롤 계량 새들"),
    Leaf("CELL_MASS_RATE",     AI, 1, "WO-302 셀 벨트 계량기"),
    Leaf("BELT_SPEED_OK",      COMM, 0, "WO-302 셀 벨트 계량기"),
    Leaf("GLASS_MASS",         AI, 2, "WO-303 유리 캐리지 계량대"),
    Leaf("RESIDUAL_EVA",       COMM, 0, "RE-101 잔류 EVA 분광계"),
    Leaf("LOT_COUNT_REACHED",  COMM, 0, "이력 서버 HS-101"),
    # ── 공정 지능 ───────────────────────────────────────────────────────
    # 고정 레시피 한 벌로 모든 패널을 처리하면 쉬운 패널에서 시간을 버리고
    # 어려운 패널에서 유리를 깬다. 이미 달려 있는 로드셀을 닫힌 루프로 묶는다.
    Leaf("PEEL_FORCE",         AI, 0, "로드셀×4", "KNIFE_OVERLOAD 와 같은 점을 읽는다"),
    Leaf("LOAD_CELL_HEALTH_OK", COMM, 0, "로드셀×4"),
    Leaf("RECIPE_VALIDATED",   COMM, 0, "PLC-101반"),
    Leaf("CUT_LENGTH_TOTAL",   COMM, 0, "PLC-101반", "칼날별 누적 절단 연장"),
    Leaf("QI_DONE",            COMM, 0, "QI 상부 RGB 카메라"),
    Leaf("TRACE_DB_OK",        COMM, 0, "이력 서버 HS-101"),
    Leaf("OPC_UA_LINK_OK",     COMM, 0, "이력 서버 HS-101"),
    Leaf("STOP_REASON_CODED",  COMM, 0, "PLC-101반", "ISO 22400 정지 사유 분류"),
    # ── 무인 연속운전 ───────────────────────────────────────────────────
    Leaf("PL_IN_STACK_PRESENT", DI, 2, "PL-101 자동 디스태커"),
    Leaf("PL_OUT_SPACE_OK",    DI, 2, "PL-201 자동 스태커"),
    Leaf("KC_MAGAZINE_READY",  DI, 4, "KC-101 칼날 카세트 매거진×2"),
    Leaf("KC_ARM_HOME",        DI, 2, "KC-101 칼날 카세트 매거진×2"),
    Leaf("CARRIER_PARKED",     DI, 1, "캐리어 파킹 위치센서"),
    Leaf("AGV_DOCKED",         COMM, 0, "AD-101 AGV 도킹 스테이션"),
    Leaf("THERMAL_CAM_OK",     COMM, 0, "무인 감시 열화상 카메라×3"),
    Leaf("REMOTE_ACK",         COMM, 0, "RC-101 원격 감시 콘솔"),
    Leaf("BIN_LEVEL_OK",       AI, 3, "반출함 레벨센서×3"),
    # ── 환경·인증 ───────────────────────────────────────────────────────
    # 200 kW 배기열을 그대로 버리고 있었다. RTO 로 태우고 그 열로 급기를
    # 예열하면 같은 배기 처리가 에너지 회수가 된다.
    Leaf("RTO_TEMP_OK",        TC, 3, "RTO-101 축열식 열산화로"),
    Leaf("RTO_VALVE_OK",       DI, 4, "RTO-101 축열식 열산화로"),
    Leaf("HX_OUTLET_TEMP",     TC, 2, "HX-101 배기–급기 열교환기"),
    Leaf("CEMS_OK",            COMM, 0, "CEMS-101 연속배출감시"),
    Leaf("TOC_HIGH",           AI, 1, "CEMS-101 연속배출감시"),
    Leaf("FLAME_DETECT",       FDI, 2, "가열실 불꽃감지기×2"),
    Leaf("N2_PRESSURE_OK",     DI, 1, "NP-101 질소 퍼지 유닛"),
]

# ── 계산 신호 ───────────────────────────────────────────────────────────
DERIVED = [
    Derived("POWER_ENABLE", ["MAIN_ACB_ON", "PHASE_OK", "PE_OK", "SPD_OK", "FIRE_OK"]),
    Derived("PLC_RUN", ["UPS_OK", "DC24_A_OK", "DC24_B_OK", "SAFETY_CPU_OK", "NETWORK_RING_OK"]),
    Derived("FULL_LOAD_ACK", ["C1_PRESENT"]),
    Derived("ALL_LOCKED", ["ALL_DECK_LOCKED"]),
    Derived("ALL_DOORS_CLOSED", ["INNER_DOOR_OPEN", "OUTER_DOOR_OPEN"]),
    Derived("ALL_INNER_DOORS_CLOSED", ["INNER_DOOR_OPEN"]),
    Derived("ALL_OUTER_DOORS_CLOSED", ["OUTER_DOOR_OPEN"]),
    Derived("SEALED_FULL_LOAD_ACK",
            ["FULL_LOAD_ACK", "ALL_INNER_DOORS_CLOSED", "ALL_OUTER_DOORS_CLOSED", "DP_OK"]),
    Derived("EXHAUST_OK", ["EXHAUST_RUN"]),
    Derived("EXHAUST_RUN", ["FAN_A_OK", "FAN_B_OK", "DP_OK", "CARBON_DP_OK", "FIRE_DAMPER_OPEN"]),
    Derived("IR_ENABLE", ["SEALED_FULL_LOAD_ACK", "EXHAUST_OK", "FIRE_OK",
                          "PM_METER_OK", "EMISSION_OK"]),
    Derived("IR_HARD_TRIP", ["INDEPENDENT_OVERTEMP", "SMOKE", "CO_HIGH", "EXHAUST_LOSS", "SSR_STUCK"]),
    # 에어록은 입측 AL-101 · 출측 AL-102 두 곳이고 각각 내문·외문을 동시에
    # 열 수 없다. 문 위치센서 8점은 2 에어록 × 2 문 × 2 채널이다.
    Derived("AL101_MUTEX", ["INNER_DOOR_OPEN", "OUTER_DOOR_OPEN"]),
    Derived("AL102_MUTEX", ["INNER_DOOR_OPEN", "OUTER_DOOR_OPEN"]),
    Derived("DOOR_MUTEX", ["AL101_MUTEX", "AL102_MUTEX"]),
    Derived("REFILL_ACK", ["ACTIVE_DECK_PRESENT", "ACTIVE_DECK_LOCKED", "FORK_HOME",
                           "ALL_DOORS_CLOSED", "DP_OK"]),
    Derived("LIFT_MOVE", ["ALL_DECK_LOCKED", "FORK_RETRACTED", "EXTRACTOR_HOME", "DOOR_LOCKED"]),
    Derived("EVA_200_ACK", ["EVA_INTERFACE_200_ACK"]),
    Derived("TANDEM_READY", ["HKB_TEMP_OK", "HKS_TEMP_OK", "KNIVES_CLEAR"]),
    Derived("RELEASE_200", ["EVA_INTERFACE_200_ACK", "TANDEM_READY", "AL102_EMPTY", "OUTER_OUT_CLOSED"]),
    Derived("VAC_OK", ["VAC_6ZONE_OK"]),
    Derived("VAC_LOW", ["VAC_6ZONE_OK"]),
    Derived("MOTION_SYNC", ["X_LEFT", "X_RIGHT", "FOLLOWING_ERROR_OK"]),
    Derived("SYNC_ERROR", ["MOTION_SYNC"]),
    Derived("PEEL_PERMIT", ["EVA_200_ACK", "HKB_TEMP_OK", "HKS_TEMP_OK", "VAC_6ZONE_OK"]),
    Derived("HKB_Z_PERMIT", ["EVA_200_ACK", "VAC_6ZONE_OK", "CASSETTE_LOCKED", "HKB_TEMP_OK"]),
    Derived("HKS_Z_PERMIT", ["LEAD_300_ACK", "WEB_TENSION_OK", "HKB_LOAD_OK", "CELL_PATH_CLEAR"]),
    Derived("RAPID_PERMIT", ["KNIVES_CLEAR", "PANEL_VAC_OK", "CARRIER_SQUARE", "TRACK_CLEAR"]),
    Derived("WEB_TENSION_HIGH", ["WEB_TENSION_OK"]),
    Derived("LOAD_HIGH", ["KNIFE_OVERLOAD"]),
    Derived("MOTION_TRIP", ["SYNC_ERROR", "VAC_LOW", "KNIFE_OVERLOAD", "WEB_TENSION_HIGH", "GLASS_CRACK"]),
    Derived("TANDEM_SAFE_STOP", ["LOAD_HIGH", "AE_CRACK", "VAC_LOW", "WEB_BREAK"]),
    Derived("OPEN_300_ACK", ["LEAD_300_ACK"]),
    Derived("WR_PERMIT", ["OPEN_300_ACK", "CLAMP_CLOSED", "VAC_OK", "DOOR_LOCKED"]),
    Derived("HKS_PERMIT", ["BACKSHEET_FULL_ACK", "ROLL_ISOLATED", "VAC_OK", "T2_READY", "AE_OK"]),
    Derived("EJECT_PERMIT", ["SHUTTER_CLOSED", "CARRIAGE_OUT", "BIN_READY"]),
    Derived("BACKSHEET_BIN_ACK", ["EJECT_PERMIT", "BIN_READY"]),
    Derived("ROLL_EJECT_ACK", ["BACKSHEET_BIN_ACK"]),
    Derived("CELL_TRANSFER", ["CVC_CLEAR", "SHREDDER_READY", "ISOLATION_GATE_OPEN"]),
    Derived("SHREDDER_FEED", ["CELL_BUFFERED", "CV_CLEAR", "SHREDDER_READY"]),
    Derived("SHREDDER_FEED_ACK", ["SHREDDER_FEED"]),
    Derived("CELL_OUT_ACK", ["CELL_TRANSFER"]),
    Derived("SHREDDER_ISOLATION", ["FIRE_BACKFLOW", "SHREDDER_TRIP"]),
    Derived("GLASS_TRANSFER", ["LEVEL_ROLLER_READY", "GC_PRESENT_LOCKED", "ZERO_DROP_PATH_CLEAR"]),
    Derived("GLASS_SWAP", ["GC_A_COOLING", "GC_B_EMPTY_LOCKED", "CROSS_TRANSFER_CLEAR"]),
    Derived("GLASS_ACCESS", ["SURFACE_TEMP_SAFE", "COOLING_COMPLETE", "DOCK_LOCKED"]),
    Derived("COOLING_COMPLETE", ["GC_A_COOLING"]),
    Derived("GLASS_CARRIAGE_ACK", ["GLASS_TRANSFER", "GC_PRESENT_LOCKED"]),
    Derived("GLASS_OUT_ACK", ["GLASS_CARRIAGE_ACK"]),
    Derived("REJECT_PERMIT", ["QI_FAIL", "RJ_CARRIAGE_PRESENT", "RJ_DOOR_LOCKED", "GLASS_PATH_CLEAR"]),
    Derived("EMPTY_CARRIER_RELOADED", ["REFILL_ACK"]),
    Derived("NEXT_PANEL", ["BACKSHEET_BIN_ACK", "SHREDDER_FEED_ACK",
                           "GLASS_CARRIAGE_ACK", "EMPTY_CARRIER_RELOADED"]),
    Derived("MUTE_VALID", ["MUTE_SENSORS"]),
    Derived("OPENING_SAFE", ["LC_OSSD_CLEAR", "MUTE_VALID"]),
    # START_WARN 은 읽는 허가가 아니라 내보내는 경보다. 기동 허가가 선 뒤
    # 적층 신호등·부저를 F-DO 로 울리고, 경보가 끝나야 축이 움직인다.
    Derived("START_WARN", ["START_PERMIT", "ST_TOWER_CMD"]),
    Derived("MAINT_PERMIT", ["ZERO_ENERGY_ACK", "LOTO_APPLIED", "TEMP_SAFE", "VAC_DUMPED"]),
    Derived("START_PERMIT", ["FULL_LOAD_ACK", "ALL_LOCKED", "ALL_TEMP_OK",
                             "ALL_DOORS_CLOSED", "EXHAUST_OK"]),
    # ── 계량·물질수지 ───────────────────────────────────────────────────
    Derived("SCALES_HEALTHY", ["PANEL_MASS_IN", "ROLL_MASS",
                               "CELL_MASS_RATE", "GLASS_MASS", "BELT_SPEED_OK"]),
    Derived("LOT_OPEN", ["LOT_ID_VALID", "WI_TARE_OK", "SCALES_HEALTHY"]),
    Derived("STREAMS_DRAINED", ["BACKSHEET_BIN_ACK", "SHREDDER_FEED_ACK",
                                "GLASS_CARRIAGE_ACK"]),
    # 투입 질량과 3계통 반출 질량의 차가 허용 오차 안에 들어야 로트가 닫힌다.
    Derived("MASS_BALANCE_OK", ["PANEL_MASS_IN", "ROLL_MASS",
                                "CELL_MASS_RATE", "GLASS_MASS"]),
    Derived("RESIDUAL_EVA_OK", ["RESIDUAL_EVA"]),
    Derived("LOT_CLOSE", ["LOT_COUNT_REACHED", "STREAMS_DRAINED", "MASS_BALANCE_OK"]),
    Derived("RECOVERY_CERT", ["LOT_CLOSE", "RESIDUAL_EVA_OK", "TRACE_WRITE_OK"]),
    # ── 공정 지능 ───────────────────────────────────────────────────────
    Derived("ADAPT_ENABLE", ["PEEL_PERMIT", "LOAD_CELL_HEALTH_OK",
                             "AE_OK", "RECIPE_VALIDATED"]),
    Derived("SPEED_SETPOINT", ["ADAPT_ENABLE", "PEEL_FORCE", "HKB_LOAD_OK"]),
    Derived("KNIFE_WEAR_WARN", ["PEEL_FORCE", "CUT_LENGTH_TOTAL", "HKS_TEMP_OK"]),
    Derived("KNIFE_CHANGE_DUE", ["KNIFE_WEAR_WARN", "KNIVES_CLEAR"]),
    Derived("TRACE_WRITE_OK", ["TRACE_DB_OK", "LOT_ID_VALID"]),
    # 기록이 남지 않은 패널은 내보내지 않는다 — 이력은 사후에 못 만든다.
    Derived("PANEL_RELEASE", ["QI_DONE", "TRACE_WRITE_OK"]),
    Derived("OEE_VALID", ["STOP_REASON_CODED", "TRACE_DB_OK",
                          "PM_METER_OK", "OPC_UA_LINK_OK"]),
    # ── 무인 연속운전 ───────────────────────────────────────────────────
    Derived("AUTO_FEED", ["PL_IN_STACK_PRESENT", "TRACK_CLEAR", "LOT_OPEN"]),
    Derived("AUTO_STACK", ["PL_OUT_SPACE_OK", "GLASS_CARRIAGE_ACK", "DOCK_LOCKED"]),
    # 칼날 자동교환은 정비허가가 아니라 파킹 상태에서 돈다. LOTO 를 요구하면
    # 무인 운전 중에는 영원히 성립하지 않는다.
    Derived("KNIFE_AUTOCHANGE", ["KNIFE_CHANGE_DUE", "KC_MAGAZINE_READY",
                                 "KC_ARM_HOME", "KNIVES_CLEAR", "CARRIER_PARKED"]),
    Derived("ROLL_HANDOFF", ["BACKSHEET_BIN_ACK", "AGV_DOCKED", "SHUTTER_CLOSED"]),
    Derived("UNMANNED_PERMIT", ["AUTO_FEED", "AUTO_STACK", "KC_MAGAZINE_READY",
                                "BIN_LEVEL_OK", "THERMAL_CAM_OK", "FIRE_OK",
                                "REMOTE_ACK", "OEE_VALID"]),
    # ── 환경·인증 ───────────────────────────────────────────────────────
    Derived("RTO_READY", ["RTO_TEMP_OK", "RTO_VALVE_OK", "EXHAUST_RUN"]),
    Derived("HEAT_RECOVERY", ["RTO_READY", "HX_OUTLET_TEMP", "DP_OK"]),
    Derived("EMISSION_OK", ["CEMS_OK", "TOC_HIGH", "RTO_READY"]),
    Derived("CHAMBER_FIRE_TRIP", ["FLAME_DETECT", "SMOKE", "CO_HIGH"]),
    Derived("N2_PURGE", ["CHAMBER_FIRE_TRIP", "N2_PRESSURE_OK"]),
]

# ── 구동부 ──────────────────────────────────────────────────────────────
DRIVES = [
    Drive("MT-101", "투입 롤러 구동",       DO, 2, "접촉기",  "IE4 기어모터"),
    Drive("SV-201", "캐리어 이송축 좌",     COMM, 0, "STO 2CH", "서보 랙피니언"),
    Drive("SV-202", "캐리어 이송축 우",     COMM, 0, "STO 2CH", "서보 랙피니언"),
    Drive("SV-301", "LI-101 승강 서보",     COMM, 0, "STO 2CH", "서보모터·감속기"),
    Drive("SV-302", "TS-101 포크 서보",     COMM, 0, "STO 2CH", "TS-101 2단 포크"),
    Drive("SV-401", "HKB Z축 서보",         COMM, 0, "STO 2CH", "HKB Z축 서보슬라이드"),
    Drive("SV-402", "HKS Z축 서보",         COMM, 0, "STO 2CH", "HKS Z축 서보슬라이드"),
    Drive("SV-501", "WR-101 권취 토크서보", COMM, 0, "STO 2CH", "토크서보·직경센서"),
    Drive("MT-601", "CVC-301 벨트",         DO, 2, "접촉기",  "VFD 기어모터×2"),
    Drive("MT-602", "CVC-302 벨트",         DO, 2, "접촉기",  "VFD 기어모터×2"),
    Drive("MT-701", "유리 컨베이어",        DO, 2, "접촉기",  "VFD 기어모터"),
    Drive("MT-702", "GC 캐리지 주행",       DO, 2, "접촉기",  "GC-301A 캐리지"),
    Drive("MT-801", "RJ-301 횡셔틀",        DO, 2, "접촉기",  "RJ 횡셔틀"),
    Drive("MT-901", "배기팬 A",             DO, 2, "접촉기",  "배기팬 A"),
    Drive("MT-902", "배기팬 B",             DO, 2, "접촉기",  "배기팬 B"),
    Drive("MT-903", "진공펌프 A",           DO, 2, "접촉기",  "진공펌프 A/B"),
    Drive("MT-904", "진공펌프 B",           DO, 2, "접촉기",  "진공펌프 A/B"),
    Drive("SH-101 투입롤러", "슈레더",               DO, 2, "접촉기",  "SH-101 투입롤러"),
    Drive("CY-201", "층별 잠금실린더",      DO, 5, "덤프밸브", "층별 잠금실린더×5"),
    Drive("CY-202", "에어록 셔터",          DO, 4, "덤프밸브", "투입 에어록"),
    Drive("CY-301", "패널 스토퍼",          DO, 1, "덤프밸브", "패널 스토퍼"),
    Drive("CY-401", "분할클램프",           DO, 4, "덤프밸브", "분할클램프×4"),
    Drive("CY-402", "권취 격리셔터",        DO, 2, "덤프밸브", "격리셔터"),
    Drive("CY-403", "외함 롤 포트 셔터",    DO, 2, "덤프밸브", "외함 롤 포트"),
    Drive("CY-404", "펜스 인터록 해치",     DO, 2, "덤프밸브", "펜스 인터록 해치"),
    Drive("CY-501", "역화격리게이트",      DO, 2, "덤프밸브", "역화격리게이트"),
    Drive("CY-601", "코너 승강대",          DO, 2, "덤프밸브", "코너 승강대"),
    Drive("VV-101", "6존 진공밸브",         DO, 6, "덤프밸브", "체크밸브×6"),
    Drive("SSR-B",  "IR 뱅크 SSR",          AO, 6, "주접촉기", "SSR 분기모듈×60"),
    Drive("ST-101", "적층 신호등·부저",     FDO, 4, "F-DO 직결", "적층 신호등·부저 ST-101/102"),
    # 무인 연속운전
    Drive("SV-701", "PL-101 디스태커 승강",  COMM, 0, "STO 2CH", "PL-101 자동 디스태커"),
    Drive("SV-702", "PL-201 스태커 승강",    COMM, 0, "STO 2CH", "PL-201 자동 스태커"),
    Drive("SV-801", "KC-101 카세트 교환암",  COMM, 0, "STO 2CH", "KC-101 칼날 카세트 매거진×2"),
    Drive("MT-1001", "AGV 도킹 로크",        DO, 2, "접촉기",  "AD-101 AGV 도킹 스테이션"),
    # 환경·인증
    Drive("MT-905", "RTO 급기팬",            DO, 2, "접촉기",  "RTO-101 축열식 열산화로"),
    Drive("CY-701", "RTO 절환밸브",          DO, 4, "덤프밸브", "RTO-101 축열식 열산화로"),
    Drive("BR-101", "RTO 보조버너",          AO, 1, "주차단밸브", "RTO-101 축열식 열산화로"),
    Drive("CY-702", "질소 퍼지 밸브",        FDO, 2, "F-DO 직결", "NP-101 질소 퍼지 유닛"),
    # 계량
    Drive("MT-1101", "WI-101 계량 컨베이어", DO, 2, "접촉기",  "WI-101 투입 계량 컨베이어"),
]

# ── 실행 ────────────────────────────────────────────────────────────────
def build():
    leaves = {l.name: l for l in LEAVES}
    derived = {d.name: d for d in DERIVED}
    return leaves, derived


def report():
    console = CONSOLE.read_text(encoding="utf-8")
    leaves, derived = build()
    problems = []

    # 1. 논리식이 부르는데 정의가 없는 신호
    dangling = []
    for d in DERIVED:
        for t in d.terms:
            if t not in leaves and t not in derived:
                dangling.append((d.name, t))

    # 2. 정의는 있는데 아무도 안 쓰는 신호
    used = {t for d in DERIVED for t in d.terms}
    unused = [n for n in leaves if n not in used]

    # 3. 신호를 만드는 장치가 3D 모델에 있는가
    missing_dev = []
    for l in LEAVES:
        if l.device not in console:
            missing_dev.append(l)

    # 4. 구동부의 장치가 3D 모델에 있는가 / 안전정지 수단이 있는가
    missing_drive = [d for d in DRIVES if d.device not in console]
    no_stop = [d for d in DRIVES if not d.stop]

    # 5. I/O 예산
    io = {k: 0 for k in BUDGET}
    for l in LEAVES:
        if l.io in io:
            io[l.io] += l.count
    for d in DRIVES:
        if d.io in io:
            io[d.io] += d.count

    print("=" * 68)
    print("DG-HK60 인터록 실행 보고서")
    print("=" * 68)
    print(f"  현장 입력 신호 {len(LEAVES)}   계산 신호 {len(DERIVED)}   구동부 {len(DRIVES)}")
    print()

    print("── 1. 부르는데 정의가 없는 신호 ─────────────────────────")
    if dangling:
        for owner, t in dangling:
            print(f"   ✗ {t:26s} ← {owner} 가 읽는데 만드는 곳이 없다")
        problems.append(f"미정의 신호 {len(dangling)}")
    else:
        print("   없음")
    print()

    print("── 2. 정의만 있고 쓰이지 않는 신호 ──────────────────────")
    if unused:
        for n in sorted(unused):
            print(f"   ! {n:26s} ({leaves[n].device})")
        problems.append(f"미사용 신호 {len(unused)}")
    else:
        print("   없음")
    print()

    print("── 3. 신호를 만들 장치가 3D 모델에 없다 ─────────────────")
    if missing_dev:
        for l in missing_dev:
            print(f"   ✗ {l.name:26s} 필요 장치 '{l.device}' ({l.io}×{l.count})")
        problems.append(f"장치 누락 {len(missing_dev)}")
    else:
        print("   없음")
    print()

    print("── 4. 구동부 ────────────────────────────────────────────")
    if missing_drive:
        for d in missing_drive:
            print(f"   ✗ {d.tag:8s} {d.name:20s} 장치 '{d.device}' 가 모델에 없다")
        problems.append(f"구동부 누락 {len(missing_drive)}")
    if no_stop:
        for d in no_stop:
            print(f"   ✗ {d.tag:8s} {d.name:20s} 안전정지 수단 없음")
        problems.append(f"안전정지 누락 {len(no_stop)}")
    if not missing_drive and not no_stop:
        print("   전 구동부 장치·안전정지 확보")
    print()

    print("── 5. I/O 예산 ──────────────────────────────────────────")
    over = []
    for k in (DI, DO, AI, AO, TC, FDI, FDO):
        use, cap = io[k], BUDGET[k]
        pct = 100 * use / cap
        spare = (cap - use) / cap if cap else 0
        flag = "✗ 초과" if use > cap else ("✗ 예비<20%" if spare < SPARE_MIN else "")
        if use > cap or spare < SPARE_MIN:
            over.append(k)
        print(f"   {k:5s} {use:3d} / {cap:3d}   사용 {pct:5.1f} %  예비 {100*spare:5.1f} %  {flag}")
    if over:
        problems.append(f"I/O 부족 {over}")
    print()

    print("=" * 68)
    if problems:
        print("미해결: " + " · ".join(problems))
    else:
        print("미해결 없음")
    print("=" * 68)
    return problems


if __name__ == "__main__":
    probs = report()
    sys.exit(1 if (probs and "--check" in sys.argv) else 0)
