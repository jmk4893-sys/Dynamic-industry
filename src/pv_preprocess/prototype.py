# -*- coding: utf-8 -*-
"""BFC-101 반전 카세트 **시작품** — 무엇을 만들어 무엇을 증명하는가.

이 라인 전체가 서 있는 가정은 하나다: *적층에서 45 kg 패널 한 장을 진공으로
떼어, 두 링 사이로 올려, 180° 돌려, 인계 높이에 내려놓을 수 있다.* 이 가정이
참이면 나머지는 돈과 일정 문제이고, 거짓이면 나머지 설계는 값이 없다.

그래서 시작품은 **BFC 한 Bay 만** 만든다. 로봇도, 두 번째 Bay 도, 벽체도,
하류도 짓지 않는다. 그것들은 이 가정이 참으로 밝혀진 뒤에 짓는 것이다.

이 모듈은 그 계획의 정본이다. 값은 셋 중 하나에서만 온다.

1. **설계 모델** — `kinematics`·`layout`·`servos`·`campaign`·`safety`·`mounting`.
   합격 기준은 여기서 온다. 시작품이 증명해야 하는 것은 도면이 적어 놓은 값이지
   시작품을 만들며 새로 정한 값이 아니다.
2. **제작 패키지** — `fabrication.ASSEMBLIES` 의 PV-FAB-A03(반전 카세트)과
   A04(포획빔). 수량 산출은 여기서 그대로 나눠 쓴다. 시작품은 Bay 1식이므로
   플랜트 2벌 중 1벌이다.
3. **여기서 정하는 것** — 단계·관문·시험 방법·시료·계측·일정. 이건 모델에
   없는 것이라 여기 적는다. 근거는 각 항목에 붙였다.

**단가는 여기 없다.** 수량과 사양만 적고 값은 G0 관문의 3사 견적으로 채운다 —
지어낸 단가를 적으면 그 숫자가 계획을 끌고 다닌다.

    PYTHONPATH=src python tools/build_prototype.py
"""

from __future__ import annotations

from dataclasses import dataclass

from . import campaign, crane, fabrication, kinematics, layout, mounting, safety, servos

#: 리그 도번. 플랜트 도면(PV-FAB-*)과 구분한다 — 시작품은 출도본이 아니다.
RIG = "PV-PROTO-BFC-01"

#: 시작품이 베끼는 조립체. A03 이 본체, A04 는 낙하 포획이라 같이 만든다.
#: A04 없이 A03 을 돌리면 시험 중 낙하를 받을 것이 없다.
SOURCE_SHEETS: tuple[str, ...] = ("PV-FAB-A03", "PV-FAB-A04")

#: 시작품 Bay 수. 플랜트는 2 Bay 지만 증명에 필요한 것은 1 Bay 다.
#: 두 Bay 의 상호작용(반대 Bay 안전·교대 급전)은 기계가 아니라 제어 문제이고,
#: 그건 리그 하나로 못 보는 대신 시뮬레이터와 인터록 시험으로 본다.
BAYS = 1


# ── 시작품이 닫는 질문 ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Question:
    """시작품 하나가 답해야 하는 질문. 답이 '아니오' 면 설계가 바뀐다."""

    no: str
    ask: str
    why: str          # 왜 도면으로는 못 닫는가
    fails: str        # '아니오' 일 때 무엇이 바뀌는가


QUESTIONS: tuple[Question, ...] = (
    Question("Q1", "적층 최상단 한 장만 떨어지는가",
             "진공 파지력·박리 거동은 실물 패널의 표면 상태(먼지·수분·프레임 변형)에 달렸고 "
             "계산으로 나오지 않는다. 폐패널은 새 패널이 아니다.",
             "분리 방식 자체를 바꾼다 — 컵 수·배치·박리 각도, 최악의 경우 진공 분리 포기"),
    Question("Q2", "겹장을 붙기 전에 잡아내는가",
             "겹장 판정은 진공 A/B 압력·두께·중량·높이 네 채널의 조합이다. 각 채널의 "
             "판별 문턱값은 실측 분포에서만 나온다.",
             "채널 추가(라인프로파일 두께 계측) 또는 픽업 재시도 로직"),
    Question("Q3", "패널이 두 링 사이를 긁지 않고 지나는가",
             f"편측 여유 {kinematics.cage_axial_clearance_mm():g} mm 는 "
             "도면상 계산값이다. 실물은 링 런아웃·캐리지 처짐·패널 휨이 겹친다.",
             "링 피치를 넓힌다 — 카세트 외형과 포탈이 따라 커지고 셀 길이가 바뀐다"),
    Question("Q4", "180° 돌아가는 동안 유리가 견디는가",
             "패널을 네 점으로 물고 뒤집는 동안 자중이 유리에 굽힘으로 걸린다. 폐패널은 "
             "이미 미세 균열을 갖고 있어 새 패널 물성으로 계산할 수 없다.",
             "지지점 수를 늘리거나(4점 → 6점) 회전 속도를 낮춘다 — 택트가 늘어난다"),
    Question("Q5", "깨진 유리 패널도 같은 동작으로 지나가는가",
             "60장 중 5장이 유리 깨짐이다. 그 5장이 카세트 안에서 부서지면 이물이 "
             "링·롤러·바닥으로 쏟아진다.",
             "깨짐 패널 전용 경로 또는 하부 트레이·집진 추가"),
    Question("Q6", "반전 구간이 배정된 시간 안에 끝나는가",
             f"{kinematics.PATH[0][0]:g}–{kinematics.PATH[-1][1]:g} s, "
             f"즉 {kinematics.PATH[-1][1] - kinematics.PATH[0][0]:g} s 다. 서보 가감속과 "
             "진동 정정 시간은 실물 관성에서만 나온다.",
             "택트가 늘어 라인 처리량이 떨어진다 — 병목이 투입부로 옮겨온다"),
    Question("Q7", "반전 카세트가 실제로 몇 kg 인가",
             f"발주처 확인값 {crane.governing_lift().mass_kg:,} kg 이상은 하한이고 "
             "단면에서 낸 개략값은 그보다 낮았다. 크레인 용량·앵커·바닥하중이 이 값에 달렸다.",
             "크레인 용량과 앵커 사양, 바닥 보강이 바뀐다"),
)


# ── 범위 ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ScopeItem:
    what: str
    detail: str


#: 만든다.
IN_SCOPE: tuple[ScopeItem, ...] = (
    ScopeItem("포탈·크로스빔 (A03)", "기둥 4 · 크로스빔 2 · 베이스플레이트 4. 플랜트 도면 그대로 만든다 — "
              "여기를 줄이면 강성이 달라져 시험 결과가 플랜트로 옮겨가지 않는다."),
    ScopeItem("엔드링·지지롤러·구동 (A03)", "오픈센터 링 2 · 지지롤러 4 · 가이드롤러 4 · 구동 롤러 1 · 락핀 2."),
    ScopeItem("승강 캐리지·LM·볼스크루 (A03)", "레일빔 2 · 엔드빔 2 · LM 가이드 4본 · 볼스크루 2 · 라인샤프트 동기."),
    ScopeItem("분리헤드·진공 (A03)", "헤드 빔 1 · 진공컵 4 · 4구역 개별 진공. 진공 스키드는 임대 또는 소형 대체."),
    ScopeItem("4점 클램프 조 (A03)", "조 2 · 패드 4 · 실린더 4 · 가이드 포스트 4."),
    ScopeItem("포획빔 (A04)", "4열 횡슬라이드 1식. 낙하 시험이 있어야 시험을 할 수 있다."),
    ScopeItem("적층 시험대", "LFT-101 대체. 전동 스크루 잭 승강대로 픽업면을 유지하고 한 장마다 인덱스한다. "
              "유압 시저 2.5 t 를 사지 않는 대신 같은 인터페이스(고정 픽업면·인덱스)를 제공한다."),
    ScopeItem("인계 확인대", "RB-101 대체. 인계 높이에 고정 받이대와 로드셀·다이얼을 두어 "
              "패널이 어느 자세로 어디에 오는지 잰다. 로봇은 이 단계에서 필요 없다."),
    ScopeItem("제어·계측 반", "서보 3축 · 안전 릴레이 · 계측 로거. 플랜트 PLC 구성은 쓰지 않는다."),
)

#: 만들지 않는다. 이유를 적는다 — 안 적으면 다음 사람이 다시 논의한다.
OUT_OF_SCOPE: tuple[ScopeItem, ...] = (
    ScopeItem("RB-101 로봇·EOAT", "인계 자세와 좌표만 확인하면 되고, 로봇 도달은 별도 벤더 하중도로 닫는 문제다."),
    ScopeItem("두 번째 Bay", "기계적으로 거울상이다. 두 Bay 상호 인터록은 제어 시험으로 본다."),
    ScopeItem("BW-101 벽체·VG-101 비전보", "하중 경로는 구조 계산으로 닫고, 시작품은 자립 프레임으로 대신한다."),
    ScopeItem("VS-101 통합 비전", "유리면 방향 판정은 시작품에서 사람이 대신한다 — 이번에 볼 것은 기구다."),
    ScopeItem("하류 전부 (PT·JB·JBR 이후)", "이 질문과 무관하다."),
    ScopeItem("플랜트 안전 인증 (PLd·Cat.3)", "시작품은 사람이 접근하지 않는 임시 가드로 돌린다. "
              f"본 인증은 {', '.join(h.tag for h in safety.HAZARDS if h.cell == 'bfc')} 의 "
              "PFHd 가 벤더 자료로 계산된 뒤에 받는다."),
)

#: 대체품 — 플랜트 사양 대신 쓰는 것과, 그래도 결과가 옮겨가는 이유.
SUBSTITUTES: tuple[tuple[str, str, str], ...] = (
    ("LFT-101 유압 시저 리프트 2.5 t", "전동 스크루 잭 시험대 (적재 500 kg · 인덱스 ±0.5)",
     f"시험에 쓰는 적층은 {campaign.PALLET_PANELS} 장이 아니라 10 장이면 된다. "
     f"픽업면 {kinematics.PICK_FACE_MM:,} 유지와 한 장 인덱스라는 인터페이스는 같다."),
    ("VAC-101 이중 진공 스키드", "소형 진공 발생기 + 리시버 (임대)",
     "구역별 압력을 따로 읽을 수 있으면 판정 채널은 동일하다."),
    ("플랜트 PLC·FSoE", "범용 모션 컨트롤러 + 안전 릴레이",
     "축 동기와 인터록 논리만 같으면 기구 시험 결과는 같다. 안전 아키텍처는 범위 밖이다."),
    ("BW-101 하중 프레임", "자립 앵커 기초 + 임시 브레이싱",
     "포탈이 벽체에 매달리지 않는 구조라 기둥 4본만으로 하중이 닫힌다."),
)


# ── 단계와 관문 ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Stage:
    """관문 하나. `weeks` 는 이 단계의 기간이고 `exit` 를 못 넘기면 다음이 없다."""

    gate: str
    name: str
    weeks: int
    work: str
    exit: str


STAGES: tuple[Stage, ...] = (
    Stage("G0", "착수 조건", 3,
          "포탈·크로스빔·엔드링 지지롤러 구조 계산(또는 FEA)과 앵커 인발 계산, 상용품 3사 견적, "
          "폐패널 시료 확보 경로 확정.",
          "구조 검토서 서명 · 견적 3사 · 시료 100장 확보 확약"),
    Stage("G1", "발주", 4,
          "강재·기계가공 발주, 상용품 14 품목 발주(서보·감속기·LM·볼스크루 리드타임이 가장 길다), "
          "엔드링 파이프 롤벤딩 발주.",
          "최장 리드타임 품목 납기 확약서"),
    Stage("G2", "제작", 4,
          "절단·용접·응력제거·기계가공. 엔드링은 용접 뒤 선반 가공으로 런아웃을 잡는다.",
          f"제작품 검사 성적서 · 엔드링 런아웃 실측 ≤ 0.25"),
    Stage("G3", "조립", 2,
          f"A03 조립 순서 {len(fabrication.assembly('PV-FAB-A03').steps)} 단계를 그대로 따른다. "
          "각 단계 검사 항목을 기록한다.",
          "조립 검사 전 항목 합격 · 토크 마킹 완료"),
    Stage("G4", "무부하 시운전", 2,
          "패널 없이 저속으로 승강·반전·락·조를 돌린다. 간섭 스윕을 실측하고 센서·인터록을 건다.",
          "간섭 0 · 반복도 시험 합격 · 이중 브레이크 보유 확인"),
    Stage("G5", "부하 시험", 4,
          "실 폐패널로 T-01…T-12 를 돈다. 정상·깨짐·전손을 섞는다.",
          "시험 계획의 합격 기준 전항 충족"),
    Stage("G6", "판정·반영", 1,
          "결과를 설계 모델에 되돌리고, 시작품 보고서로 플랜트 착수 여부를 판정한다.",
          "모델 갱신 커밋 · 판정 회의 결론"),
)


# ── 시험 계획 ───────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Test:
    """시험 하나. `criterion` 은 모델에서 온 값이고 `source` 가 그 출처다."""

    tag: str
    question: str      # 어느 질문을 닫는가
    name: str
    method: str
    instrument: str
    runs: str
    criterion: str
    source: str


def _k() -> dict[str, object]:
    """시험 기준에 쓰는 모델 값 — 한 곳에서 읽어 표와 검사가 같은 값을 본다."""
    lift = kinematics.FLIP_AXIS_MM - (kinematics.PICK_FACE_MM + kinematics.SEPARATION_MM)
    return {
        "pick": kinematics.PICK_FACE_MM,
        "dwell": kinematics.PICK_FACE_MM + kinematics.SEPARATION_MM,
        "axis": kinematics.FLIP_AXIS_MM,
        "handover": kinematics.HANDOVER_MM,
        "lift": lift,
        "drop": kinematics.FLIP_AXIS_MM - kinematics.HANDOVER_MM,
        "sep": kinematics.SEPARATION_MM,
        "side": kinematics.cage_axial_clearance_mm(),
        "bore_clear": kinematics.bore_clearance_mm(),
        "rail_clear": kinematics.carriage_bore_clearance_mm(),
        "bore": 2 * (kinematics.RING_R_MM - kinematics.RING_TUBE_MM),
        "jaw": kinematics.JAW_OPEN_Z_MM - kinematics.JAW_CLOSED_Z_MM,
        "flip_s": kinematics.PATH[3][1] - kinematics.PATH[3][0],
        "bfc_s": kinematics.PATH[-1][1] - kinematics.PATH[0][0],
        "index": layout.LFT_INDEX_MM if hasattr(layout, "LFT_INDEX_MM") else 50,
    }


#: 내구 시험 사이클 수. 근거: 방출 주기에서 나오는 하루 생산량의 5 일치다.
#: 무한정 돌릴 수 없고, 초기 마모·체결 풀림·패드 이탈은 이 안에서 나온다.
ENDURANCE_CYCLES = 3_000

#: 시료 폐패널 수. 60장 캠페인 로스터의 구성비를 그대로 쓰되 배수를 늘린다.
SPECIMEN_PANELS = 100

TESTS: tuple[Test, ...] = (
    Test("T-01", "Q1", "단장 분리 — 최상단 한 장만 뜨는가",
         "적층 10장에서 최상단을 4구역 진공으로 파지해 안전분리 높이까지 올린다. 올라온 매수를 센다.",
         "구역별 진공압 · 헤드 로드셀 · 레이저 거리 2점",
         "정상 60 회 · 깨짐 20 회 · 습윤·분진 조건 20 회",
         f"1장만 분리 100 % · 파지 실패 시 즉시 정지 · 안전분리 {_k()['sep']} mm 상승 중 이탈 0",
         "kinematics.SEPARATION_MM"),
    Test("T-02", "Q2", "겹장 판정 문턱값",
         "일부러 2장을 붙여 올려 네 채널(진공 A/B 압력·중량·두께·높이)의 분포를 기록하고 판별 문턱을 정한다.",
         "진공압 · 로드셀 · 레이저 2점",
         "겹장 30 회 · 단장 60 회",
         "겹장 미검출 0 회 · 단장 오검출 ≤ 2 %",
         "인터페이스 표 '리프트 인덱스' 조건 no_double_sheet"),
    Test("T-03", "Q1", "픽업면 유지 — 인덱스 정밀도",
         f"한 장을 뗄 때마다 시험대를 인덱스시켜 픽업면 {_k()['pick']:,} mm 가 유지되는지 잰다. "
         "실제 폐패널 두께 분포를 같이 기록한다.",
         "레이저 거리 2점 · 두께 게이지",
         "10장 적층 × 6 회",
         "픽업면 편차 ≤ ±1.0 mm · 실측 패널 피치 기록",
         "AFU-SE-101 높이 반복 ≤ 1.0 mm"),
    Test("T-04", "Q3", "링 통과 여유 실측",
         "패널을 올린 채 승강 전 구간에서 패널 끝과 링 안쪽 면, 캐리지 레일과 링 구멍 사이를 잰다.",
         "틈새 게이지 · 다이얼 게이지 · 고속 카메라",
         "저속 10 회 · 정격 속도 10 회",
         f"편측 여유 ≥ {_k()['side']:g} mm 유지 · 접촉 0 회 · "
         f"모서리–구멍 {_k()['bore_clear']:.0f} · 레일–구멍 {_k()['rail_clear']:.0f} 유지",
         "kinematics.cage_clear_span_mm"),
    Test("T-05", "Q6", "수직 승강 반복도·시간",
         f"{_k()['pick']:,} → {_k()['dwell']:,} → {_k()['axis']:,} → {_k()['handover']:,} mm 를 반복한다.",
         "리니어 스케일 · 서보 인코더 로그",
         "100 회",
         f"승강 반복 ±0.5 mm · 승강 {_k()['lift']:,} mm 와 하강 {_k()['drop']:,} mm 가 배정 시간 안",
         "PV-FAB-A03 검사 항목 · kinematics.PATH"),
    Test("T-06", "Q4", "4점 조 체결·행정",
         "조를 열고 닫으며 행정과 패드 면 정렬을 재고, 패널을 문 상태에서 유격을 확인한다.",
         "다이얼 게이지 · 실린더 압력",
         "200 회",
         f"행정 {_k()['jaw']:g} ±1 mm · 패드 면 동일 평면 ≤ 0.5 mm · 문 상태 패널 유격 0",
         "kinematics.JAW_OPEN_Z_MM − JAW_CLOSED_Z_MM"),
    Test("T-07", "Q4", "180° 반전 — 유리 건전성",
         "정상 패널을 물고 180° 돌린 뒤 유리를 검사한다. 회전 속도를 3 단으로 바꿔 반복한다.",
         "EL 검사(전후) · 육안 · 가속도계",
         "정상 40 회 · 각 속도 단 12 회 이상",
         f"신규 균열 0 · 반전 시간 ≤ {_k()['flip_s']:g} s · 양단 위상차 ≤ 0.3°",
         "kinematics.PATH 반전 구간"),
    Test("T-08", "Q5", "깨진 유리 패널 취급",
         "유리 깨짐 패널을 정상과 같은 순서로 통과시키고, 링·롤러·바닥의 이물을 회수해 잰다.",
         "저울 · 하부 트레이 · 육안",
         "20 회",
         "라인 정지 유발 0 · 회수 불가 이물 0 · 파편이 링 구동부에 들어가지 않을 것",
         "campaign 로스터 유리 깨짐 5/60"),
    Test("T-09", "Q6", "반전 구간 사이클 타임",
         "T-01 부터 인계 안착까지를 한 사이클로 잡고 정격 속도로 연속 운전한다.",
         "서보 로그 · 사이클 타이머",
         "50 사이클",
         f"BFC 구간 ≤ {_k()['bfc_s']:g} s · 한 장 투입부 점유 ≤ {campaign.INFEED_S:g} s",
         "kinematics.PATH · campaign.INFEED_S"),
    Test("T-10", "Q3", "포획빔 낙하 포획",
         "패널을 승강 중 일부러 놓아 포획빔이 받는지 본다. 전개 시간도 같이 잰다.",
         "고속 카메라 · 전개 완료 센서",
         "10 회",
         "45 kg 패널 300 mm 낙하 포획 · 전개 ≤ 1.7 s · 포획빔 영구변형 0",
         "PV-FAB-A04 검사 항목"),
    Test("T-11", "Q7", "실중량·무전원 보유",
         "카세트 조립체를 크레인 로드셀로 달아 실중량을 재고, 전원을 끊어 이중 브레이크 각각의 보유를 본다.",
         "크레인 로드셀 · 각도계",
         "중량 1 회 · 브레이크 각 10 회",
         f"실중량 기록(설계 하한 {crane.governing_lift().mass_kg:,} kg 과 대조) · "
         "브레이크 1개만으로 자세 유지 · 각도 변화 ≤ 0.5°",
         "crane.governing_lift · AXIS-BFC-R 이중 브레이크"),
    Test("T-12", "Q4", "내구 — 마모·풀림",
         f"정상 패널로 {ENDURANCE_CYCLES:,} 사이클을 돌리고 500 사이클마다 토크·런아웃·패드를 점검한다.",
         "토크렌치 · 다이얼 게이지 · 패드 두께 게이지",
         f"{ENDURANCE_CYCLES:,} 사이클",
         "체결 풀림 0 · 링 런아웃 증가 ≤ 0.1 · 패드 마모 ≤ 1 mm · 진공컵 누설 증가 없음",
         "PV-FAB-A03 검사 항목"),
)


#: 시료 구성 — 60장 캠페인 로스터의 판정 구성비를 배수로 늘린다.
def specimen_mix() -> tuple[tuple[str, int, str], ...]:
    """(구분, 매수, 근거). 합은 SPECIMEN_PANELS 다."""
    roster = campaign.build_roster() if hasattr(campaign, "build_roster") else None
    if roster is not None:
        total = len(roster)
        cracked = sum(1 for r in roster if getattr(r, "condition", "") == "유리 깨짐")
        scrap = sum(1 for r in roster if getattr(r, "condition", "") == "전손")
    else:                                            # 로스터 API 가 없으면 문서화된 구성비
        total, cracked, scrap = 60, 5, 2
    k = SPECIMEN_PANELS / total
    n_cracked, n_scrap = round(cracked * k), round(scrap * k)
    return (
        ("정상 (유리면 위 · 아래 섞어서)", SPECIMEN_PANELS - n_cracked - n_scrap,
         f"로스터 {total - cracked - scrap}/{total} 비율"),
        ("유리 깨짐", n_cracked, f"로스터 {cracked}/{total} 비율 — T-08 의 시료다"),
        ("전손", n_scrap, f"로스터 {scrap}/{total} 비율 — 반전을 생략하는 경로 확인용"),
    )


# ── 리그 안전 ───────────────────────────────────────────────────────────
#: 시작품은 인증 설비가 아니다. 그래서 사람을 기계에서 떼어 놓는 것으로 대신한다.
RIG_SAFETY: tuple[tuple[str, str], ...] = (
    ("접근 금지 원칙", "운전 중 리그 반경 2 m 안에 사람이 들어가지 않는다. 시료 투입·회수는 정지 상태에서만 한다."),
    ("임시 가드", "3면 메시 펜스 2,000 H · 출입문 1 곳에 안전 스위치. 정면은 시험 관측을 위해 폴리카보네이트."),
    ("비상정지", "이중채널 버튼 2 곳 + 유선 리모트 1. 정지범주 1 — 제어정지 뒤 동력차단. "
     "정지범주 0 으로 하면 승강축이 자유낙하한다."),
    ("낙하 대비", "정비 안전받침(기계식)을 승강 구간에 항상 건다. 포획빔은 시험 항목이면서 동시에 이 리그의 안전 장치다."),
    ("무전원 자세", "반전축 이중 브레이크와 락핀이 정전 시 자세를 유지하는지 G4 에서 먼저 확인한 뒤 패널을 올린다."),
    ("유리 파편", "하부 전면 트레이와 집진. 시험자는 보안경·장갑·안전화. 깨진 패널 취급은 2인 1조."),
    ("이 리그로 하지 않는 것", "PLd·Cat.3 검증. 안전 부품 PFHd 가 없어 SISTEMA 계산이 성립하지 않는다 — "
     "본 설비 인증은 벤더 자료가 온 뒤 별도로 받는다."),
)


# ── 수량 산출 (단가는 견적) ─────────────────────────────────────────────
@dataclass(frozen=True)
class CostLine:
    """비용 한 줄. 수량은 모델에서 나오고 단가는 G0 견적으로 채운다."""

    group: str
    item: str
    qty: str
    basis: str


def cost_lines() -> tuple[CostLine, ...]:
    a3, a4 = fabrication.assembly("PV-FAB-A03"), fabrication.assembly("PV-FAB-A04")
    # fabricated_weight_kg() 는 이미 **1벌(= Bay 1식)** 기준이다. 플랜트 수량(qty)으로 나누지 않는다.
    steel = (a3.fabricated_weight_kg() + a4.fabricated_weight_kg()) * BAYS
    bolts = a3.bolt_count() + a4.bolt_count()
    anchors = sum(x.count * (x.units if x.per_unit else 1)
                  for m in mounting.MOUNTINGS if m.station == "bfc" for x in m.anchors)
    axes = [x for x in servos.SERVO_AXES if x.tag in ("AXIS-BFC-R", "AXIS-BFC-Z", "AXIS-CD-Z")]
    kw = sum(x.rated_kw for x in axes)
    return (
        CostLine("제작", "구조·기계 제작품 (A03 + A04, Bay 1식)", f"{steel:,.0f} kg / {len(a3.parts) + len(a4.parts)} 종",
                 "재질별 강재 + 절단·용접·응력제거·기계가공. 엔드링은 롤벤딩 + 선반 가공."),
        CostLine("제작", "엔드링 (오픈센터 Ø1,980)", "2 EA",
                 f"1 개 {next(p for p in a3.parts if p.tag == 'BFC-RNG-01').weight_kg():,.0f} kg. "
                 "런아웃 0.25 를 잡는 가공이 값의 대부분이다."),
        CostLine("상용품", "구동·전동 (서보·감속기·브레이크)", f"{len(axes)} 축 / {kw:g} kW",
                 " · ".join(f"{x.tag} {x.rated_kw:g} kW" for x in axes)),
        CostLine("상용품", "직선 운동 (LM·볼스크루·라인샤프트)", "LM 4본 · 블록 8 · 볼스크루 2",
                 "A03 상용품표 그대로. 리드타임이 가장 길어 G1 에서 먼저 건다."),
        CostLine("상용품", "그 밖의 A03·A04 상용품", f"{len(a3.commercial) + len(a4.commercial)} 품목",
                 "베어링·락핀·실린더·진공컵·센서·슬라이드."),
        CostLine("체결", "볼트·앵커", f"볼트 {bolts:,} · 앵커 {anchors}",
                 "플랜트 도면집의 호칭·등급·토크 그대로. 예비 10 % 별도."),
        CostLine("리그", "적층 시험대 (LFT 대체)", "1 식",
                 "전동 스크루 잭 승강대 · 적재 500 kg · 인덱스 ±0.5."),
        CostLine("리그", "인계 확인대 · 임시 가드 · 트레이", "1 식",
                 "고정 받이대 · 메시 펜스 3면 · 하부 파편 트레이 · 집진."),
        CostLine("제어", "제어·계측 반", "1 면",
                 "모션 컨트롤러 · 서보 드라이브 3 · 안전 릴레이 · 데이터 로거."),
        CostLine("계측", "계측 장비", "1 식",
                 "로드셀 · 레이저 거리계 2 · 리니어 스케일 · 고속 카메라 · EL 검사(외주 가능)."),
        CostLine("시료", "폐패널 시료", f"{SPECIMEN_PANELS} 장",
                 "구성비는 캠페인 로스터. 운반·보관·폐기 포함."),
        CostLine("용역", "구조 계산·앵커 인발 (G0)", "1 건",
                 "기술사 검토. 이것이 없으면 G1 로 못 넘어간다."),
        CostLine("용역", "설치·시운전·시험 인건", f"{sum(s.weeks for s in STAGES[3:])} 주",
                 "G3–G6. 2인 기준."),
    )


# ── 위험 ────────────────────────────────────────────────────────────────
RISKS: tuple[tuple[str, str, str], ...] = (
    ("진공 파지가 폐패널 표면에서 안 붙는다", "높음",
     "컵 사양(벨로우즈 단수·재질)을 2 종 준비해 G5 초반에 바꿔 본다. 표면 청소 스텝 추가도 대안이다."),
    ("반전 중 유리가 깨진다", "중간",
     "지지점을 6점으로 늘릴 수 있게 조 캐리어에 예비 자리를 미리 뚫어 둔다. 회전 속도 3 단 시험이 그 판단 근거다."),
    ("서보·LM 리드타임이 일정을 끈다", "높음",
     "G1 에서 최장 품목만 먼저 발주한다. 제작(G2)과 병행이라 4 주 안에 안 오면 G3 가 밀린다."),
    ("실중량이 설계 하한을 넘는다", "중간",
     "T-11 을 G3 끝에 배치해 크레인·앵커 재검토 시간을 남긴다."),
    ("시료 폐패널을 못 구한다", "중간",
     "G0 의 착수 조건에 넣었다. 확약 없이 G1 으로 넘어가면 G5 에서 리그가 논다."),
    ("깨짐 패널 파편이 구동부에 들어간다", "낮음",
     "하부 트레이를 처음부터 단다. T-08 결과에 따라 플랜트 설계에 커버를 추가한다."),
)


# ── 시작품이 모델에 돌려주는 것 ─────────────────────────────────────────
#: (모델 자리, 지금 값의 성격, 어느 시험이 채우는가)
FEEDBACK: tuple[tuple[str, str, str], ...] = (
    ("crane.governing_lift().mass_kg", "발주처 확인 하한", "T-11"),
    ("kinematics.PATH 반전·승강 구간 시각", "설계 계획값", "T-05 · T-07 · T-09"),
    ("layout / campaign 의 리프트 인덱스 (미결 3건 중 1건)", "50 과 45 가 문서마다 다르다", "T-03 이 실측 피치로 닫는다"),
    ("진공컵 수·배치 (BFC-VC-01 · SEP 헤드)", "4 구역 계획", "T-01 · T-02"),
    ("겹장 판정 문턱값", "채널만 정해져 있고 값이 없다", "T-02"),
    ("조 지지점 수·회전 속도", "4점 · 단일 속도", "T-07"),
    ("링 통과 여유 공차", "계산 여유", "T-04"),
)


# ── 검사 ────────────────────────────────────────────────────────────────
def total_weeks() -> int:
    """G0 부터 G6 까지."""
    return sum(s.weeks for s in STAGES)


def questions_are_covered() -> dict[str, bool]:
    """질문마다 그것을 닫는 시험이 하나 이상 있는가."""
    asked = {t.question for t in TESTS}
    return {q.no: q.no in asked for q in QUESTIONS}


def tests_point_at_questions() -> dict[str, bool]:
    """시험이 가리키는 질문이 실제로 있는가 (오타 방지)."""
    known = {q.no for q in QUESTIONS}
    return {t.tag: t.question in known for t in TESTS}


def source_sheets_exist() -> dict[str, bool]:
    """베끼는 조립체가 제작 패키지에 있는가."""
    have = {a.sheet for a in fabrication.ASSEMBLIES}
    return {s: s in have for s in SOURCE_SHEETS}


def specimens_add_up() -> bool:
    return sum(n for _, n, _ in specimen_mix()) == SPECIMEN_PANELS


def summary() -> dict[str, object]:
    a3, a4 = fabrication.assembly("PV-FAB-A03"), fabrication.assembly("PV-FAB-A04")
    return {
        "rig": RIG,
        "bays": BAYS,
        "questions": len(QUESTIONS),
        "tests": len(TESTS),
        "stages": len(STAGES),
        "weeks": total_weeks(),
        "fabricated_kg": round((a3.fabricated_weight_kg() + a4.fabricated_weight_kg()) * BAYS, 1),
        "part_kinds": len(a3.parts) + len(a4.parts),
        "commercial_items": len(a3.commercial) + len(a4.commercial),
        "bolts": a3.bolt_count() + a4.bolt_count(),
        "specimens": SPECIMEN_PANELS,
        "endurance_cycles": ENDURANCE_CYCLES,
    }
