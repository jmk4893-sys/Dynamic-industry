"""세계 최상급 기준으로 이 설비를 채점한다.

"최상급으로 올려 달라" 는 말은 그대로는 검사할 수 없다. 그래서 기준을 **출처
있는 수치**로 바꾸고, 현재 값을 **모델에서 계산**해 격차를 낸다. 값을 여기에
손으로 적지 않는 이유는 하나다 — 적어 두면 설계가 바뀌어도 점수가 안 바뀐다.

## 세 가지 판정만 쓴다

- ``PASS``    기준을 넘었다
- ``GAP``     재 봤고 모자란다. **무엇을 고치면 닫히는지**를 같이 적는다
- ``BLOCKED`` 아직 못 잰다. 벤더 데이터나 시운전 실측이 있어야 나오는 값이라
              지어내지 않는다. 37 절의 예비품 수명, 36 절의 Kst 와 같은 취급이다

``BLOCKED`` 를 ``PASS`` 로 세지 않는 것이 이 파일의 요점이다. 못 잰 것을 통과로
세면 점수가 올라가고, 그 점수를 근거로 설계를 멈추게 된다.

## 품질률이 없다는 것이 가장 큰 발견이다

OEE 는 가용률 × 성능률 × 품질률이다. 앞의 둘은 모델에 있는데 품질률은 없다.
없는 값을 1.0 으로 놓으면 OEE 가 0.854 로 나와 세계 최상급 기준 0.85 를 갓
넘는다 — 그러나 그것은 **공정이 아무것도 망가뜨리지 않는다는 전제**이고, 그
전제는 어디에도 적혀 있지 않았다. 37 절에서 연간 장수가 가용률 1.0 위에 서
있던 것과 같은 종류의 공백이다. 그래서 품질률은 ``None`` 이고 OEE 도 ``None``
이다. run-at-rate 로 재고 나서 채운다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import acceptance, acoustics, ai, campaign, electrical, materials, reliability, safety

#: 채점 축. 발주처가 말한 네 가지 그대로다.
AXES: tuple[str, ...] = ("기술", "내구성", "사용성", "AI")

#: 병목 셀 점유시간 (s). 이상 택트 — 인계 대기가 0 일 때의 값이다.
#: 14 절에서 택트가 병목 + 인계 8 s 로 정해졌으므로 병목 자체가 성능률의 분자다.
BOTTLENECK_OCCUPANCY_S = 45.0

#: 공정 품질률. **모른다.** 폐모듈을 받는 라인이라 "불량" 은 반입물 상태이지
#: 공정 탓이 아니고, 공정이 깨뜨린 유리와 원래 깨져 온 유리를 가르려면
#: 투입 비전과 후단 검사를 대조해야 한다 — run-at-rate 항목이다.
QUALITY_RATE: float | None = None


@dataclass(frozen=True)
class Criterion:
    """기준 하나. `current` 는 값이고, 못 재면 ``None`` 이다."""

    tag: str
    axis: str
    name: str
    target: float | None
    unit: str
    direction: str          # '>=' 또는 '<='
    source: str             # 목표가 어디서 왔는가
    current: Callable[[], float | None]
    closes: str             # 이 격차를 닫는 설계 변경

    def value(self) -> float | None:
        return self.current()

    def verdict(self) -> str:
        v = self.value()
        if v is None or self.target is None:
            return "BLOCKED"
        ok = v >= self.target if self.direction == ">=" else v <= self.target
        return "PASS" if ok else "GAP"

    def shortfall(self) -> float | None:
        """모자란 양. PASS 면 0, 못 재면 ``None``."""
        v = self.value()
        if v is None or self.target is None:
            return None
        gap = self.target - v if self.direction == ">=" else v - self.target
        return max(0.0, round(gap, 4))


# ── 축별 현재값 ──────────────────────────────────────────────────────────

def performance_rate() -> float:
    """성능률 = 이상 택트 / 실제 택트. 인계 대기가 성능률을 깎는다."""
    return BOTTLENECK_OCCUPANCY_S / campaign.summary()["takt_s"]


def oee() -> float | None:
    """OEE. 품질률을 모르므로 지금은 낼 수 없다 — 1.0 으로 덮지 않는다."""
    if QUALITY_RATE is None:
        return None
    return reliability.TARGET_AVAILABILITY * performance_rate() * QUALITY_RATE


def oee_if_quality(quality: float) -> float:
    """품질률을 넣으면 OEE 가 얼마가 되는지. 협의용이지 현재값이 아니다."""
    return reliability.TARGET_AVAILABILITY * performance_rate() * quality


def energy_per_panel_kwh() -> float:
    """장당 전력 원단위. 지표는 세우되 목표는 발주처가 정한다."""
    return electrical.demand_kw() / campaign.summary()["throughput_per_h"]


def worst_mttr_h() -> float:
    """가장 오래 걸리는 복구. 평균이 아니라 최악을 본다 — 라인이 서는 시간이다."""
    return max(b.mttr_h for b in reliability.BLOCKS)


def single_point_blocks() -> tuple[str, ...]:
    """단일 고장으로 라인 전체가 서는 블록. 이중화도 버퍼도 없는 것."""
    return tuple(b.tag for b in reliability.BLOCKS if not b.redundant and not b.buffered)


def single_point_ratio() -> float:
    return len(single_point_blocks()) / len(reliability.BLOCKS)


def spares_unknown() -> int:
    """소요를 모르는 예비품 종수. 0 이어야 정비 계획이 선다."""
    return len(reliability.spares_pending())


def ready_ai_ratio() -> float:
    """지금 착수할 수 있는(A 등급) AI 과제 비율."""
    return sum(1 for c in ai.CASES if c.grade == "A") / len(ai.CASES)


#: 폐루프 — 모델이 **판정만 하는 것이 아니라 설정값을 바꾸는** 과제.
#: 지금 A 등급 셋은 전부 감지·진단이다. 감지는 사람을 부르고, 폐루프는 공정을
#: 바꾼다. 세계 최상급 라인을 가르는 선이 여기다.
CLOSED_LOOP_TAGS: tuple[str, ...] = ()


def closed_loop_count() -> int:
    return len(CLOSED_LOOP_TAGS)


def console_receives_live_data() -> float:
    """운전 콘솔이 실 데이터를 받는가 (1/0).

    지금은 설계 모델 값을 띄우는 레이아웃이다. 화면은 있는데 라인 상태가
    아니므로 운전에 못 쓴다 — SM-1012 백본과 히스토리안이 붙어야 한다.
    """
    return 0.0


def wear_liners_are_replaceable() -> float:
    """분진 고속 접촉면이 교체식 라이너인가 (1/0)."""
    return 1.0 if any("라이너" in r.material or "라이너" in r.reason
                  for r in materials.RULES) else 0.0


CRITERIA: tuple[Criterion, ...] = (
    # ── 기술 ──────────────────────────────────────────────────────────
    Criterion("T-01", "기술", "설비종합효율 OEE", 0.85, "", ">=",
              "JIPM(일본플랜트관리협회) 세계 최상급 OEE 0.85 = 가용률 0.90 × 성능률 0.95 × 품질률 0.999",
              oee,
              "품질률을 run-at-rate 로 재야 OEE 자체가 나온다. 지금은 분모가 없다"),
    Criterion("T-02", "기술", "가용률", 0.90, "", ">=",
              "JIPM 세계 최상급 가용률 0.90",
              lambda: reliability.TARGET_AVAILABILITY,
              "계약 목표 0.92 로 이미 넘는다"),
    Criterion("T-03", "기술", "성능률", 0.95, "", ">=",
              "JIPM 세계 최상급 성능률 0.95",
              performance_rate,
              "택트 48.47 중 인계 대기 3.47 s 를 줄여야 한다 — JB-201 축적구간을 "
              "2 장으로 늘리거나 로봇 방출을 병목 종료와 겹치게 한다"),
    Criterion("T-04", "기술", "장당 전력 원단위", None, "kWh/장", "<=",
              "이 공정의 공개 벤치마크가 없다 — 지표만 세우고 목표는 발주처가 정한다",
              energy_per_panel_kwh,
              "목표를 받으면 기준이 선다. 값 자체는 이미 모델에서 나온다"),
    # ── 내구성 ────────────────────────────────────────────────────────
    Criterion("D-01", "내구성", "최악 복구시간 MTTR", 0.5, "h", "<=",
              "SMRP 정비 우수사례 — 라인 정지 고장 복구 30분 이내",
              worst_mttr_h,
              "무공구 교체 카트리지(칼날·연마휠·핫나이프), 모듈 단위 핫스왑, "
              "고장 지점을 짚어 주는 온보드 진단이 있어야 3.0 h 가 0.5 h 로 내려간다"),
    Criterion("D-02", "내구성", "소요 미상 예비품", 0, "종", "<=",
              "정비 계획이 서려면 모든 소모품의 소요가 정의돼야 한다",
              spares_unknown,
              "칼날·핫나이프·연마휠은 run-at-rate, 뮤팅 센서는 벤더 B10d, "
              "IR 램프는 GRM 벤더값 — 전부 받아야 채워진다"),
    Criterion("D-03", "내구성", "단일고장 정지 블록 비율", 0.0, "", "<=",
              "세계 최상급 연속 라인은 단일 고장으로 전체가 서지 않는다",
              single_point_ratio,
              "5개 블록(AFU·ROBOT·JBR·AFR·GBR)에 이중화나 버퍼가 없다. "
              "버퍼를 넣는 쪽이 이중화보다 싸지만 전장이 늘어난다 — 발주처 결정"),
    Criterion("D-04", "내구성", "사명시간", 20.0, "년", ">=",
              "ISO 13849-1 안전부품 사명시간 상한 20년",
              lambda: float(safety.MISSION_TIME_YEARS),
              "이미 20년으로 잡혀 있다"),
    Criterion("D-05", "내구성", "마모면 교체식 라이너", 1.0, "", ">=",
              "유리 파쇄분 Mohs 6~7 — 고속 접촉면은 교체식이어야 본체가 안 닳는다",
              wear_liners_are_replaceable,
              "AR400 t4 교체식 라이너 규칙이 이미 있다"),
    # ── 사용성 ────────────────────────────────────────────────────────
    Criterion("U-01", "사용성", "통로 소음", 70.0, "dBA", "<=",
              "산업안전보건기준 8시간 노출 90 dBA — 세계 최상급 라인은 통로 70 이하",
              lambda: acoustics.worst_aisle_dba()[1],
              "저감 장치 4종으로 이미 59.9 dBA"),
    Criterion("U-02", "사용성", "운전 콘솔 실데이터 수신", 1.0, "", ">=",
              "운전 화면은 라인 상태를 보여야 한다 — 설계값을 띄우는 것은 운전이 아니다",
              console_receives_live_data,
              "SM-1012 백본에 히스토리안을 붙이고 콘솔이 그것을 읽게 해야 한다. "
              "지금 콘솔은 그 자리를 잡아 둔 레이아웃이다"),
    Criterion("U-03", "사용성", "인수 전 미해결 항목", 0, "항", "<=",
              "인수 시점에 미해결이 남으면 현장에서 다툰다",
              lambda: len(acceptance.open_at_handover()),
              "S-08 분진 시료·S-10 내진 앵커·R-04 마모율 — 셋 다 외부 입력 대기"),
    # ── AI ────────────────────────────────────────────────────────────
    Criterion("A-01", "AI", "착수 가능 과제 비율", 1 / 3, "", ">=",
              "계측 추가 없이 지금 시작할 수 있는 과제가 1/3 은 돼야 착수가 굴러간다",
              ready_ai_ratio,
              "B 등급 5건은 계측기 46점이 들어오면 A 가 된다 — 계측기가 관문이다"),
    Criterion("A-02", "AI", "폐루프 제어 과제", 1, "건", ">=",
              "감지는 사람을 부르고 폐루프는 공정을 바꾼다 — 최상급 라인을 가르는 선",
              closed_loop_count,
              "AI-06 IR 가열 종점을 조언에서 **제어**로 올리는 것이 가장 가깝다. "
              "PY-901 계면 온도계와 AI-07 완전도 판정이 라벨이자 피드백이 된다"),
    Criterion("A-03", "AI", "라벨 착수 시점", 3.0, "개월", "<=",
              "전이학습 기준 클래스당 1,000장 — 가장 희소한 클래스가 착수를 지배한다",
              lambda: 2.4,
              "전손 2.4개월로 이미 안쪽이다"),
)


def by_axis(axis: str) -> tuple[Criterion, ...]:
    return tuple(c for c in CRITERIA if c.axis == axis)


def gaps() -> tuple[Criterion, ...]:
    """재 봤고 모자란 것."""
    return tuple(c for c in CRITERIA if c.verdict() == "GAP")


def blocked() -> tuple[Criterion, ...]:
    """아직 못 재는 것. PASS 로 세지 않는다."""
    return tuple(c for c in CRITERIA if c.verdict() == "BLOCKED")


def passed() -> tuple[Criterion, ...]:
    return tuple(c for c in CRITERIA if c.verdict() == "PASS")


def axis_score(axis: str) -> tuple[int, int, int]:
    """(통과, 격차, 못잼) — 못 잰 것을 분모에서 빼지 않는다."""
    rows = by_axis(axis)
    return (sum(1 for c in rows if c.verdict() == "PASS"),
            sum(1 for c in rows if c.verdict() == "GAP"),
            sum(1 for c in rows if c.verdict() == "BLOCKED"))


def summary() -> dict[str, object]:
    return {
        "criteria": len(CRITERIA),
        "pass": len(passed()),
        "gap": len(gaps()),
        "blocked": len(blocked()),
        "axes": {a: axis_score(a) for a in AXES},
        "performanceRate": round(performance_rate(), 4),
        "oee": oee(),
        "oeeIfPerfectQuality": round(oee_if_quality(1.0), 4),
        "worstMttrH": worst_mttr_h(),
        "singlePoint": single_point_blocks(),
        "energyPerPanelKwh": round(energy_per_panel_kwh(), 3),
    }
