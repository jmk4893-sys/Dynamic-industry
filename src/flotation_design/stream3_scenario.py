"""③ 스트림 직접 Ag 부선 — 미니앱 수지의 독립 대조.

현행 플랜트는 고속분쇄 폐회로 뒤 공기분급으로 세 산물을 낸다:
① 금속미분 ② 백시트 ③ **실리콘 + 실리콘과 결합한 은**(Ag 3~5 kg/t).

③ 을 그대로 정련소에 보내면 Ag 값은 받지만 Si 값은 못 받는다. 그래서 ③ 을
부유선별해 Ag 를 지닌 것만 띄워 내고 가라앉는 나머지를 실리콘으로 살리는 것이
이 공정의 목적이다.

사용자 확인(2026-09-05) — ③ 에는 **폴리머가 거의 없다.** 미량의 Cu·Ag·Si 와
미분화된 백시트 가루뿐이고 눈으로도 모래·분말에 가깝다. 그래서 회로는
폴리머 역부선 없이 **직접 Ag 부선 한 단**이다.

    ③ → 어트리션(EVA 마찰제거 · Ag 노출) → 분쇄 → 조건조
       → 부선 ─거품→ Ag 정광 (정련소)
              └광미→ Si 산물 (살리려는 것)

이 모듈은 기준 급광(:mod:`design_basis` 의 박리 셀 분획)을 건드리지 않고 ③ 을
**추가로** 정의해, 미니앱이 내는 회수율·품위를 이 패키지의 속도론으로 다시
짚어 보는 데 쓴다. 두 모델이 서로를 베끼지 않았으므로 결과가 붙으면 상호 검증이다.

주의 — Ag 표면이 EVA 에 덮여 있으면 포수제가 붙지 못해 뜨지 않는다. 문헌의
99.7 % 는 EVA 가 없는 박리 셀 분획에서 잰 값, 즉 **완전 노출**일 때의 수치다.
따라서 ``회수율 = 노출도 × R(문헌)`` 이고, 노출도를 정하는 것이 어트리션이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .design_basis import COMPOSITE_CARRY_RATIO

# --------------------------------------------------------------------------
# ③ 스트림 — 실측이 오기 전까지의 설계 조성
# --------------------------------------------------------------------------
#: 처리량. 건식 2 mm 스캘핑(백시트 폐기) 뒤 체 급광이 그대로 ③ 이 된다.
STREAM3_TPH = 0.255

#: Ag 품위. 사용자 실측 범위 3~5 kg/t 의 중앙값을 설계점으로 잡는다.
#: LOI + assay 가 오면 이 값이 확정된다.
STREAM3_AG_GPT = 4000.0

#: 폴리머 잔류. 「거의 없다」를 수치로 옮긴 값이며 **HOLD** 다 —
#: 600 °C 강열감량이 이 값을 준다.
STREAM3_POLYMER_WT = 2.0

#: 잔류 Cu. 공기분급이 금속미분(①)으로 대부분 뺀 뒤 남는 미량.
STREAM3_CU_WT = 0.30

# --------------------------------------------------------------------------
# Ag 표면 노출 — 이 공정의 지배 변수
# --------------------------------------------------------------------------
#: 건식 파쇄만으로 드러나는 몫 (HOLD).
AG_EXPOSURE_FEED = 0.02
#: 어트리션 명판 체류와 그때 노리는 노출도 — **설계 의도이지 실측이 아니다.**
AG_EXPOSURE_NAMEPLATE_MIN = 5.0
AG_EXPOSURE_TARGET = 0.95


def exposure_rate_per_min(t95: float | None = None) -> float:
    """EVA 마찰제거 1 차 속도상수.

    ``t95`` 를 주면 그 값(노출도 0.95 에 걸리는 시간, 분)에서 유도한다.
    주지 않으면 명판 체류에서 설계 의도 노출도가 나오도록 잡는다.
    """
    span = t95 if t95 is not None else AG_EXPOSURE_NAMEPLATE_MIN
    return -math.log((1 - AG_EXPOSURE_TARGET) / (1 - AG_EXPOSURE_FEED)) / span


def ag_exposure(minutes: float, t95: float | None = None) -> float:
    """어트리션 체류에 따른 Ag 표면 노출도."""
    k = exposure_rate_per_min(t95)
    return 1 - (1 - AG_EXPOSURE_FEED) * math.exp(-k * max(0.0, minutes))


# --------------------------------------------------------------------------
# 부선기 선택 — 회수율이 다르다
# --------------------------------------------------------------------------
#: 기존 셀 폐회로. 비부선 2.4 % 때문에 97.6 % 에서 점근한다. 라이선스 없음.
MECHANICAL_RECOVERY = 0.976
#: 리플럭스 부선주. 문헌 99.7 %. 단일 90 min 시험이라 하한을 함께 든다.
REFLUX_RECOVERY = {"low": 0.990, "design": 0.997}


@dataclass(frozen=True)
class Stream3Result:
    """③ 을 직접 Ag 부선에 태운 결과."""

    feed_kg_h: float
    feed_ag_kg_h: float
    exposure: float
    concentrate_kg_h: float
    concentrate_ag_kg_h: float
    grade_wt_percent: float
    ag_recovery: float
    si_product_kg_h: float
    si_product_share: float
    si_product_ag_gpt: float

    @property
    def meets_recovery(self) -> bool:
        return self.ag_recovery >= 0.99

    @property
    def meets_grade(self) -> bool:
        return self.grade_wt_percent >= 10.0


def run(
    attrition_min: float = 9.9,
    flotation_recovery: float = REFLUX_RECOVERY["design"],
    t95: float | None = None,
    ag_gpt: float = STREAM3_AG_GPT,
    tph: float = STREAM3_TPH,
    cu_pickoff: float = 0.90,
) -> Stream3Result:
    """③ 을 직접 Ag 부선에 태운다.

    Args:
        attrition_min: 어트리션 체류. 40 L 셀 1 기가 ③ 255 kg/h 에서 약 9.9 min.
        flotation_recovery: 완전 노출일 때의 부선 회수율(문헌값 또는 기계식 점근).
        t95: EVA 마찰제거 속도. None 이면 설계 의도값.
        cu_pickoff: 분쇄 전 Cu 선별율. 남는 Cu 는 정광으로 간다.
    """
    feed_kg = tph * 1000
    feed_ag = feed_kg * ag_gpt / 1e6
    e = ag_exposure(attrition_min, t95)

    recovered = feed_ag * flotation_recovery * e
    # Ag 와 같은 입자에 붙어 함께 뜨는 Si 계 맥석 — 품위의 상한을 정하는 항이다.
    locked = recovered * COMPOSITE_CARRY_RATIO
    cu_to_conc = feed_kg * STREAM3_CU_WT / 100 * (1 - cu_pickoff)
    # 잔류 백시트 가루는 소수성이라 뜨지만 ③ 에 미량뿐이다.
    dust_to_conc = feed_kg * STREAM3_POLYMER_WT / 100 * 0.60
    concentrate = recovered + locked + cu_to_conc + dust_to_conc
    tails = feed_kg - concentrate
    tails_ag = feed_ag - recovered

    return Stream3Result(
        feed_kg_h=feed_kg,
        feed_ag_kg_h=feed_ag,
        exposure=e,
        concentrate_kg_h=concentrate,
        concentrate_ag_kg_h=recovered,
        grade_wt_percent=recovered / concentrate * 100 if concentrate > 0 else 0.0,
        ag_recovery=recovered / feed_ag if feed_ag > 0 else 0.0,
        si_product_kg_h=tails,
        si_product_share=tails / feed_kg if feed_kg > 0 else 0.0,
        si_product_ag_gpt=tails_ag / tails * 1e6 if tails > 0 else 0.0,
    )


def attrition_tolerance(attrition_min: float, target_recovery: float = 0.99,
                        flotation_recovery: float = REFLUX_RECOVERY["design"]) -> float:
    """목표 회수율을 지키려면 EVA 마찰제거가 얼마나 빨라야 하는가 (t95, 분).

    이것이 어트리션 증설의 값을 재는 잣대다 — 체류가 길수록 허용 t95 가 넓어진다.
    """
    need = target_recovery / flotation_recovery
    if need >= 1:
        return 0.0
    k = -math.log((1 - need) / (1 - AG_EXPOSURE_FEED)) / attrition_min
    return -math.log((1 - AG_EXPOSURE_TARGET) / (1 - AG_EXPOSURE_FEED)) / k
