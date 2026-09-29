"""AI 적용 검토 — 이 플랜트에서 **실제로 되는 것**과 안 되는 것.

검토 규칙은 셋이다.

1. **데이터가 먼저 있어야 한다.** 모델을 고르기 전에 그 신호가 이 플랜트에서
   나오는지부터 본다. 안 나오면 그것은 AI 과제가 아니라 계측 과제다.
2. **라벨이 어디서 오는지 말할 수 있어야 한다.** 사람이 따로 붙여야 하는
   라벨은 비용이고, 공정이 스스로 만드는 라벨(하류 결과·재작업 여부·교체
   이력)은 공짜다. 후자만 지속된다.
3. **AI 가 아니어도 되는 것은 AI 로 하지 않는다.** 기구가 이미 결정론적으로
   푸는 문제(PT-101 3-2-1 정렬 뒤의 패널 좌표)나, 자명한 최적해가 있는
   문제(직렬 라인의 병목 스케줄)에 학습을 얹으면 검증 부담만 늘어난다.

## 감지와 폐루프를 가른다

여기까지의 과제는 전부 **감지**다 — 모델이 판정하고 사람이 움직인다. 세계
최상급 라인을 가르는 선은 그다음이다: 모델이 **설정값을 직접 바꾼다**.

폐루프에는 감지에 없는 규칙이 하나 더 붙는다 — **한계는 모델 밖에서 강제한다.**
학습한 것에 안전을 맡기지 않는다. 모델은 포락선 안에서만 설정값을 내고, 그
포락선은 재래식 인터록이 지킨다. 모델이 이상해져도 설비가 상하지 않는 이유가
이것이고, 이 구분이 없으면 폐루프는 사양이 아니라 희망이다.

그래서 등급은 성능이 아니라 **착수 가능성**으로 매긴다.

* **A** — 지금 있는 데이터로 착수할 수 있다. 새 센서가 필요 없다.
* **B** — `smart.INSTRUMENTS` 로 새로 다는 센서가 붙으면 가능해진다.
* **C** — 기술적으로는 되지만 이득이 작다. **권고하지 않는다.**
* **D** — 지금은 불가. 무엇이 없어서 안 되는지를 적는다.

숫자(표본 공급량·착수 시점)는 전부 `campaign.py`·`smart.py` 에서 파생한다.
가동 계획이 바뀌면 착수 시점이 같이 움직인다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import campaign, handoff, reliability, smart

# ── 표본 공급 ────────────────────────────────────────────────────────────
#: 사전학습 모델을 미세조정(전이학습)할 때 클래스당 필요한 최소 표본.
#: 산업 비전에서 통용되는 하한이며, 확정값이 아니라 착수 판단용 기준선이다.
TRANSFER_MIN_SAMPLES = 1_000

#: 처음부터 학습할 때 클래스당 필요한 표본. 이 플랜트에서 현실적이지 않다 —
#: 그래서 모든 비전 과제를 전이학습 전제로 잡는다.
SCRATCH_MIN_SAMPLES = 10_000


def annual_panels() -> float:
    """연간 촬영 장수 — 전손까지 포함한 전량.

    **가용률을 얹은 값이다.** 라벨은 실제로 처리한 장에서만 나온다 — 라인이
    서 있는 동안에는 카메라가 찍을 것이 없다. REV.45 까지 여기서 공칭 장수
    (가용률 1.0)를 쓰는 바람에 표본 공급을 308,138 로 적었고, 그만큼 착수
    시점(`cold_start_months`)을 짧게 잡고 있었다. `reliability` 가 단일
    출처이므로 목표 가용률이 바뀌면 라벨 공급과 착수 시점이 같이 따라온다.
    """
    return reliability.annual_panels()


def annual_labels() -> dict[str, float]:
    """투입 판정 클래스별 연간 표본 공급.

    구성비는 캠페인 실측(정상 53 · 유리 깨짐 5 · 전손 2)에서 온다. 이 구성이
    현장 반입물과 다르면 착수 시점이 통째로 달라지므로 run-at-rate 확인 항목이다.
    """
    counts = campaign.condition_counts()
    total = sum(counts.values())
    panels = annual_panels()
    return {key: round(panels * value / total) for key, value in counts.items()}


def months_to_threshold(label: str, threshold: int = TRANSFER_MIN_SAMPLES) -> float:
    """그 클래스가 기준 표본에 닿기까지 걸리는 개월 수."""
    per_year = annual_labels()[label]
    if per_year <= 0:
        return float("inf")
    return round(threshold / per_year * 12.0, 1)


def cold_start_months() -> float:
    """가장 희소한 클래스가 기준에 닿는 시점 — 비전 과제 착수 가능 시점."""
    return max(months_to_threshold(label) for label in annual_labels())


def scarcest_label() -> str:
    """공급이 가장 적은 클래스 — 착수 시점을 지배한다."""
    return min(annual_labels(), key=lambda key: annual_labels()[key])


# ── 오분류의 대가 ────────────────────────────────────────────────────────
# "정확도를 몇 % 올린다"는 말은 공정에서 아무 뜻이 없다. 한 장을 잘못 보면
# 라인에서 무엇을 잃는지를 초 단위로 적는다.


def scrap_miss_cost_s() -> float:
    """전손을 정상으로 오판했을 때 잃는 병목 시간 (s).

    전손은 투입부에서 15 s 만 쓰고 빠져야 하는데, 통과시키면 병목 JBR 을
    45 s 점유한다. 병목 시간은 곧 라인 처리량이다.
    """
    return round(campaign.JBR_S, 1)


def cracked_miss_cost_s() -> float:
    """파손 유리를 정상으로 오판했을 때 후단에서 잃는 시간 (s).

    R-A 로 흘러가면 유리제거셀 데크를 한 자리 먹고 시트 유리는 안 나온다 —
    깨진 유리는 시트로 못 벗기기 때문이다. 잃는 것은 데크 방출 피치다.
    """
    return round(handoff.downstream_rate().release_pitch_s, 2)


# ── 과제 ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Case:
    """AI 적용 과제 하나."""

    tag: str
    name: str
    grade: str             # 'A' | 'B' | 'C' | 'D'
    where: str             # 추론이 도는 자리 (엣지 / 랙 / 해당없음)
    data: str              # 입력 신호
    label: str             # 라벨이 어디서 오는가
    method: str
    benefit: str
    caveat: str            # 전제·한계 또는 안 하는 이유
    needs: tuple[str, ...] = ()   # 필요한 신규 계측기 (smart.INSTRUMENTS 태그)


CASES: tuple[Case, ...] = (
    # ── A: 지금 데이터로 착수 가능 (새 계측기 없이) ─────────────────────
    Case("AI-01", "투입 3분류 (정상·유리 깨짐·전손)", "A", "엣지 추론 서버",
         "VS-101A/B 5 MP 2장 (이미 있다)",
         "작업자 정정 — 판정 화면에서 틀린 것을 고치면 그것이 라벨이다. "
         "별도 라벨링 공수가 들지 않고 지금 당장 시작할 수 있다.",
         "사전학습 CNN 전이학습 · 3클래스",
         "전손 오통과 1장 = 병목 45 s, 파손유리 오통과 1장 = 후단 데크 피치 "
         "47.04 s. 지금은 규칙기반이라 애매한 장을 사람이 본다.",
         "**라벨의 질이 두 단계다.** 작업자 정정만으로도 착수는 되지만, "
         "'후단에서 시트가 실제로 벗겨졌는가' 라는 더 정확한 라벨을 그 장에 "
         "되돌려 붙이려면 패널 ID 가 버퍼·GRM 까지 이어져야 한다 — RF-901/902 "
         "결속이 그 조건이다. WI-901 중량은 부가 특징이지 필수는 아니다. "
         "전손 표본이 가장 희소해 착수 시점을 지배하며, 그때까지는 규칙기반과 "
         "**병행 운전**한다."),
    Case("AI-02", "유리 잔사·결함 세그멘테이션", "A", "엣지 추론 서버",
         "GI-302 라인스캔 0.1 mm/px (장당 350 MB)",
         "연마 재작업 여부와 레시피 등급 판정 결과가 그대로 라벨이 된다.",
         "U-Net 계열 세그멘테이션 + 면적·위치 후처리",
         "잔사 판정이 사람 눈에서 화소 면적으로 바뀐다. 레시피 등급 경계가 "
         "재현 가능해진다.",
         "장당 350 MB 라 전량 보존은 못 한다 — 불량 전량 + 정상 2 % 표본만 "
         "남기는 보존 정책이 이 과제의 전제다."),
    Case("AI-03", "전력·유틸리티 이상감지", "B", "히스토리안",
         "PM-901 피더별 12점 · FL-901 공압 · DP-901 차압 · RTD-901",
         "라벨 불요 — 비지도. 정상 운전 구간을 기준분포로 쓴다.",
         "자기부호화기 재구성오차 + 변화점 검출",
         "역률 0.90·고조파 가정이 실측으로 바뀐다. 무부하 시간대 공압 누설은 "
         "스마트 팩토리에서 회수가 가장 빠른 항목이다.",
         "피더 12개는 지금도 모델에 있지만 **계측기가 없어 값이 안 나온다** — "
         "PM-901 이 붙어야 시작한다.",
         ("PM-901", "FL-901", "DP-901", "RTD-901")),
    Case("AI-04", "서보 추종오차 추세 이상", "A", "엣지 캐비닛",
         "36축 × 6신호 × 100 Hz (드라이브가 이미 내보내는 PDO)",
         "라벨 불요 — 비지도. 정비 이력이 쌓이면 지도로 전환한다.",
         "축별 잔차 모델 + 누적합(CUSUM) 변화점",
         "**새 센서가 필요 없다.** 드라이브가 지금도 내보내는 신호를 아무도 "
         "저장하지 않고 있을 뿐이다. 히스토리안만 붙이면 그날부터 쌓인다.",
         "추종오차는 마찰·백래시 증가를 먼저 보여 주지만 베어링 결함 "
         "주파수는 못 본다 — 그것은 AI-05 의 진동 영역이다."),
    # ── B: 센서를 달면 가능 (AI-03 은 계측기가 없어 여기 있다) ──────────
    Case("AI-05", "회전기 베어링 예지보전", "B", "센서 내장 + 엣지",
         "VIB-901…906 3축 진동 (센서 내장 FFT · 특징 16개 1 Hz)",
         "교체·정비 이력. 초기에는 비지도로 시작해 이력이 쌓이면 지도로 옮긴다.",
         "포락선 스펙트럼 특징 + 이상탐지. 이력 축적 후 잔여수명 회귀.",
         "HPU-601(7.5 kW)·SG-301 스핀들·배기 블로워가 서면 라인이 선다. "
         "배기가 서면 실내 열부하가 54.6 → 139.9 kW 로 뛴다.",
         "원파형을 그대로 올리면 센서 1대가 240 kB/s 다 — 회선이 감당 못 한다. "
         "**센서 안에서 FFT 를 돌려 특징만 올리는 것이 전제**(64 B/s).",
         ("VIB-901", "VIB-902", "VIB-903", "VIB-904", "VIB-905", "VIB-906")),
    Case("AI-06", "IR 가열 종점 최적화", "B", "엣지 추론 서버",
         "PY-901 데크별 계면 방사온도 5점 · RF-902 캐리지 이력 · IR 뱅크 전력",
         "박리 결과(AI-07 의 완전도 판정)가 그대로 라벨이 된다 — 닫힌 고리다.",
         "데크별 열이력 → 박리 성공 확률 모델. 장당 잔여 소성시간을 내고 "
         "**IR 뱅크 출력을 직접 조절한다** — 이 플랜트의 유일한 폐루프(CL-01). "
         "포락선(계면 240 °C·출력 175 kW·최소 180 s)은 모델 밖 인터록이 지키고, "
         "센서·모델 이상이면 고정 235.2 s 로 복귀한다.",
         "지금은 체류 235.2 s 를 **전 장에 똑같이** 준다. 유리 두께·오염도가 "
         "다른데도 같은 시간을 주는 것이라, 짧게 끝낼 수 있는 장에서 시간을 "
         "버리고 있다. 병목은 탠덤이지만 IR 여유(76.5 장/h)가 줄면 병목이 "
         "넘어온다 — 여유를 지키는 쪽으로도 값어치가 있다.",
         "계면 온도를 **아무도 재고 있지 않다.** PY-901 없이는 이 과제가 "
         "성립하지 않는다. 방사율 보정과 IR 뱅크 자체 복사의 분리가 난점이다.",
         ("PY-901", "RF-902")),
    Case("AI-07", "박리 완전도 판정", "B", "엣지 추론 서버",
         "VS-401 12 MP 확산조명 (GRM 출구)",
         "후단 시트 유리 회수 성공/실패. 공정이 만든다.",
         "잔막 영역 세그멘테이션 + 합격/재투입 2분류",
         "지금 GRM 출구에는 **아무 검사도 없다**. 벗겨졌는지 아닌지를 사람이 "
         "보고 있고, 그 판정이 AI-06 의 라벨이기도 하다 — 이것이 없으면 "
         "가열 최적화도 못 한다.",
         "잔막이 투명 EVA 라 조명 설계가 판정 성패를 가른다. 편광·저각 조명 "
         "비교가 출도 전 확인 항목이다.",
         ("VS-401",)),
    Case("AI-08", "EVA 오프가스 기반 가열 종점 보조", "B", "엣지 캐비닛",
         "VOC-901 배기 초산·알데하이드 농도",
         "AI-07 완전도 판정과 대조.",
         "농도 곡선 특징 + 종점 분류. AI-06 의 보조 입력.",
         "EVA 는 200 °C 부근에서 초산을 낸다 — 농도 상승이 계면 연화의 "
         "**직접 지표**라 표면 온도보다 앞선다. 배출 관리도 같이 된다.",
         "덕트 희석·응답 지연이 커서 단독 판정에는 못 쓴다. AI-06 의 "
         "보조 신호로만 쓴다.",
         ("VOC-901",)),
    # ── C: 되지만 이득이 작다 ───────────────────────────────────────────
    Case("AI-09", "라인 스케줄 강화학습", "C", "해당없음",
         "캠페인 이산사건 모델 (이미 있다)",
         "시뮬레이터 자체 보상",
         "—",
         "—",
         "**권고하지 않는다.** 이 라인은 직렬이고 병목이 GRM-401 유리제거 "
         "46.49 s/장 로 고정이라 최적해가 자명하다. 실제 택트 48.47 s 와 "
         "그 병목 사이에 남은 것은 2 s 뿐이고, 그마저 앞 장 스토퍼 해제 "
         "규칙이 정한 값이라 스케줄이 아니라 기구가 쥐고 있다. 학습 정책을 "
         "넣으면 검증·설명 부담만 는다."),
    Case("AI-10", "로봇 파지 자세 비전 추정", "C", "해당없음",
         "VS-101/VS-201 영상",
         "—", "—", "—",
         "**권고하지 않는다.** PT-101 이 3-2-1 정렬로 좌표를 기계적으로 "
         "확정한 뒤에는 패널 위치가 이미 정해져 있다 — `vision.py` 가 "
         "영상 헤드를 7 → 4 로 줄인 근거와 같은 이유다. 줄인 카메라를 "
         "AI 로 되살리는 셈이 된다."),
    # ── D: 지금은 불가 ──────────────────────────────────────────────────
    Case("AI-11", "셀 조성·등급 분류 (Ag·Si 회수 최적화)", "D", "해당없음",
         "없음 — 성분을 보는 계측기가 이 플랜트에 없다",
         "없음", "—", "—",
         "**지금은 불가.** XRF 나 분광 계측기가 있어야 성립한다. 비전으로 "
         "셀 표면을 봐도 은 전극 폭까지지 조성은 못 본다. 계측기를 넣는 "
         "것은 이 PR 의 범위 밖이라 넣지 않았다 — 필요하면 별건이다."),
    Case("AI-12", "최종 회수율 예측", "D", "해당없음",
         "이 플랜트 안에서는 없음",
         "후공정(부유선별·정제) 결과가 있어야 하는데 그 라인이 이 플랜트 밖이다",
         "—", "—",
         "**지금은 불가.** 전처리는 유리·프레임·셀을 분리해 내보내는 데서 "
         "끝나고, 최종 회수율은 후공정에서 결정된다. 두 라인의 데이터가 "
         "패널 ID 로 이어지면(JB-VS-005 ↔ 후공정 배치 ID) 그때 성립한다 — "
         "**연결 자체가 선결 과제**이고 모델 문제가 아니다."),
)


@dataclass(frozen=True)
class ControlLoop:
    """폐루프 하나. **한계는 모델 밖에서 강제한다.**

    각 항목이 하나씩 없으면 폐루프가 성립하지 않는다 — 무엇을 재는지,
    무엇을 움직이는지, 모델이 낼 수 있는 값의 범위, 얼마나 빨리 바꿀 수
    있는지, 모델이 죽었을 때 어디로 가는지, 사람이 어떻게 빼는지, 그리고
    그것이 실제로 되는지 어떻게 확인하는지.
    """

    tag: str
    case: str               # 어느 AI 과제의 폐루프인가
    measured: str
    actuated: str
    setpoint: str
    envelope: str           # 재래식 인터록이 지키는 한계 — 모델이 못 넘는다
    rate_limit: str
    fallback: str           # 센서·모델 이상 시 돌아갈 자리
    handover: str           # 사람이 빼는 방법
    acceptance: str         # run-at-rate 에서 확인할 것
    enforced_outside_model: bool


def envelope_bounds() -> dict[str, float]:
    """CL-01 포락선의 경계 — **전부 모델이 내는 값이다.**

    인터록 설정값에 지어낸 수를 적으면 그 인터록은 검증할 수 없다. 그래서
    경계를 여기서 계산하고, 사양 문장에 쓰이는 숫자가 이 값들과 같은지를
    시험이 강제한다.

    - ``maxBankKw``   뱅크 설치용량. 60등 × 관당 정격이고, 그 위는 물리적으로 없다
    - ``minDwellS``   열전달 하한 체류시간. 이보다 짧으면 열이 못 들어간다
    - ``maxDwellS``   현행 고정 소성시간. 모델은 **줄이기만** 한다 — 위쪽으로
                      여는 순간 에너지·온도 양쪽에서 새 근거가 필요해진다
    """
    from . import handoff
    return {
        "maxBankKw": round(handoff.LAMP_COUNT
                           * handoff.lamp_kw(handoff.DOWNSTREAM_MAX_MM[1]), 1),
        "minDwellS": handoff.FDM_DWELL_S,
        "maxDwellS": handoff.downstream_rate().dwell_s,
    }


#: 하드와이어 온도 스위치의 **설정값은 아직 없다.** 계면 온도 상한은 반입 유리의
#: 열응력이 정하는데, 그 시험이 없다 — §36 의 Kst 나 §37 의 예비품 수명과 같은
#: 취급이다. 그럴듯한 섭씨 값을 여기 적어 두면 인터록이 검증된 것처럼 보이므로
#: 적지 않는다. 온도 스위치는 소성시간 포락선과 **별개의 층**이고, CL-01 은 그
#: 설정값 없이도 시간·출력 경계만으로 모델 밖에서 강제된다.
TEMP_TRIP_OPEN = ("계면 온도 스위치 설정값 — 반입 유리 열응력 시험 필요 "
                  "(run-at-rate 이전에 시료 시험)")


#: 이 플랜트의 폐루프. 지금은 하나다 — 늘리는 것보다 하나를 제대로 닫는 것이
#: 먼저다. IR 가열을 고른 이유는 **라벨이 공정 안에서 나오기 때문**이다
#: (AI-07 의 완전도 판정). 사람이 붙여야 하는 라벨로 도는 폐루프는 오래 못 간다.
LOOPS: tuple[ControlLoop, ...] = (
    ControlLoop(
        tag="CL-01",
        case="AI-06",
        measured="PY-901 데크별 계면 방사온도 5점 (1 Hz) · RF-902 캐리지 ID · IR 뱅크 실전력",
        actuated="IR 뱅크 존별 출력 (F9·F10 각 3라인)",
        setpoint="데크별 잔여 소성시간 — 종전의 전 장 고정 235.2 s 를 장마다 다르게 준다",
        envelope="뱅크 출력 상한 175 kW (설치용량) · 소성 하한 113.15 s (열전달 "
                 "하한) · 소성 상한 235.2 s (현행 고정값 — 모델은 줄이기만 한다). "
                 "셋 다 안전 PLC 가 지키고 모델이 못 넘는다. 온도 스위치는 별개 "
                 "층이고 설정값은 아직 없다 (TEMP_TRIP_OPEN)",
        rate_limit="출력 변화율 ±10 %/10 s. 급변은 유리에 열충격을 준다",
        fallback="PY-901 5점 중 2점 이상 이상 · 모델 무응답 2 s · 예측이 포락선 밖 → "
                 "고정 235.2 s 로 즉시 복귀하고 콘솔에 사유를 띄운다. 폴백은 성능 "
                 "저하이지 정지가 아니다",
        handover="운전 콘솔의 자동/수동 전환. 수동이면 고정 시간으로 돌아간다. 전환은 "
                 "언제든 되고 진행 중인 데크는 현재 설정으로 끝낸다",
        acceptance="run-at-rate 에서 ① 종점 판정이 AI-07 완전도와 일치하는 비율 "
                   "② 센서를 일부러 가려 폴백이 실제로 걸리는지 "
                   "③ 포락선 밖 설정값을 주입해 인터록이 막는지",
        enforced_outside_model=True,
    ),
)


def loops() -> tuple[ControlLoop, ...]:
    return LOOPS


def closed_loop_cases() -> tuple[str, ...]:
    """폐루프가 붙은 과제 태그."""
    return tuple(dict.fromkeys(loop.case for loop in LOOPS))


def loops_have_a_way_out(rows: tuple[ControlLoop, ...] | None = None) -> bool:
    """폴백·수동 전환·모델 밖 한계가 없는 폐루프는 사양이 아니라 희망이다.

    인자를 받는 이유는 §37 에서 배운 것 때문이다 — 지금 표가 이미 맞으면
    검사 코드가 죽어도 모른다. 어긋난 것을 넣어 실제로 걸리는지 본다.
    """
    for loop in (LOOPS if rows is None else rows):
        if not loop.fallback or not loop.handover or not loop.envelope:
            return False
        if not loop.enforced_outside_model:
            return False
    return True


def grading_is_consistent(cases: tuple[Case, ...] | None = None) -> bool:
    """등급과 필요 계측기가 서로 어긋나지 않는가.

    **A 는 "지금 있는 것으로 된다"는 뜻이므로 needs 가 비어 있어야 한다.**
    REV.25 초안에서 AI-03 을 A 로 적어 놓고 본문에는 "PM-901 이 붙어야
    시작한다"고 썼다 — 등급이 스스로를 반박하고 있었다. 그런 표는 읽는 사람을
    잘못된 착수 계획으로 이끈다. 코드가 대신 잡게 둔다.

    C·D 는 하지 않기로 한 것이므로 요구 계측기를 적지 않는다.

    `cases` 를 받는 것은 시험을 위해서다. 지금 데이터가 이미 일관되면 이 검사
    자체를 지워도 아무 테스트가 실패하지 않는다 — 그래서 어긋난 표를 일부러
    넣어 보고 잡히는지까지 확인한다.
    """
    for case in (CASES if cases is None else cases):
        if case.grade == "A" and case.needs:
            return False
        if case.grade == "B" and not case.needs:
            return False
        if case.grade in ("C", "D") and case.needs:
            return False
    return True


def by_grade(grade: str) -> tuple[Case, ...]:
    return tuple(case for case in CASES if case.grade == grade)


def grade_counts() -> dict[str, int]:
    return {g: len(by_grade(g)) for g in ("A", "B", "C", "D")}


def startable_now() -> tuple[Case, ...]:
    """A·B 등급 — 이 PR 의 계측 구성으로 착수 가능한 과제."""
    return by_grade("A") + by_grade("B")


def required_instruments() -> tuple[str, ...]:
    """A·B 과제가 요구하는 계측기 태그 — 중복 없이, 등장 순서대로."""
    seen: list[str] = []
    for case in startable_now():
        for tag in case.needs:
            if tag not in seen:
                seen.append(tag)
    return tuple(seen)


def unlocked_by(tag: str) -> tuple[str, ...]:
    """그 계측기가 없으면 못 하는 과제들."""
    return tuple(case.tag for case in CASES if tag in case.needs)


def summary() -> dict[str, object]:
    """도면(AI-1014)이 그대로 쓰는 요약."""
    labels = annual_labels()
    return {
        "cases": len(CASES),
        "grades": grade_counts(),
        "annual_panels": annual_panels(),
        "labels": labels,
        "scarcest": scarcest_label(),
        "cold_start_months": cold_start_months(),
        "transfer_min": TRANSFER_MIN_SAMPLES,
        "scrap_miss_s": scrap_miss_cost_s(),
        "cracked_miss_s": cracked_miss_cost_s(),
        "required_instruments": list(required_instruments()),
        "grading_consistent": grading_is_consistent(),
        "hours_per_year": smart.OPERATING_HOURS_PER_YEAR,
    }
