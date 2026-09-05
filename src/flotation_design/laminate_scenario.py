"""EVA 를 안은 라미네이트 급광 시나리오 — 미니앱 수지의 독립 대조.

이 패키지의 기준 급광(:mod:`design_basis`)은 **박리된 c-Si 셀 분획**이다:
폴리머가 없고 Ag 0.59 wt%, P80 66 µm. 그 위에서 RFC 1 단이 99.7 % 를 낸다.

미니앱(``docs/drawings/pv-recycling-miniapp.html``)이 다루는 물질은 다르다 —
유리·프레임만 빠진 라미네이트 파쇄물로 **폴리머가 45–62 wt%** 다. 두 문서가
「300 kg/h」라는 같은 문자열을 쓰지만 같은 물질이 아니다.

여기서는 기준 급광을 건드리지 않고, 라미네이트 조성을 **추가로** 정의해
같은 회로 기계(:func:`circuit.solve_circuit`)에 통과시킨다. 목적은 하나다 —
미니앱이 내는 회수율·품위를 이 패키지의 독자적인 속도론으로 다시 짚어 보는 것.
두 값이 크게 어긋나면 어느 한쪽이 틀렸다는 뜻이다.

회로는 미니앱과 같은 2 단이다.

1. **폴리머 역부선** — 뜨는 것이 버리는 것이다. 소수성 폴리머가 거품으로
   나가고 Ag 를 지닌 침강물이 2 단으로 간다.
2. **Ag 부선** — 침강물만 분쇄해 RFC 로 띄운다. 여기서 뜨는 것이 제품이다.

주의 — 1 단이 뗄 수 있는 폴리머는 **떨어져 나온 백시트뿐**이다. A·Ac 입자
안의 EVA 는 셀에 붙어 있어 뜨지 않는다. 그래서 품위는 1 단이 아니라 2 단의
폴리머 배제율이 가른다(미니앱의 관문 4 와 같은 이야기다).
"""

from __future__ import annotations

from dataclasses import dataclass

from .circuit import FlotationUnit, solve_circuit
from .kinetics import ComponentKinetics

# --------------------------------------------------------------------------
# 라미네이트 급광 — 미니앱 ASSAY 에서 옮겨온 값
# --------------------------------------------------------------------------
#: 입자군별 조성 (wt%, Ag 만 g/t). 미니앱 `ASSAY` 와 같은 표다.
LAMINATE_ASSAY = {
    "A": {"Si": 47.00, "polymer": 45.00, "Cu": 1.55, "Al": 2.50, "ag_gpt": 4500.0},
    "B": {"Si": 0.80, "polymer": 98.00, "Cu": 0.06, "Al": 0.40, "ag_gpt": 100.0},
    "C": {"Si": 32.00, "polymer": 62.00, "Cu": 1.05, "Al": 1.80, "ag_gpt": 3000.0},
}

#: C 입자 질량 중 백시트 몫. 미니앱 `C_BACKSHEET_MASS_FRACTION` 과 같다.
C_BACKSHEET_MASS_FRACTION = 0.1969570654

#: 신규 급광 입자군 비율과 처리량 — 미니앱 건식 회로 기준.
CLASS_FRACTION = {"A": 0.35, "B": 0.20, "C": 0.45}
FRESH_FEED_TPH = 0.300

#: 1 단 2 mm 스캘핑 — B 군 중 밀을 지나고도 2 mm 위에 남는 비율.
BACKSHEET_SCALP_FRACTION = 0.75


def liberated_cell_assay() -> dict[str, float]:
    """해리된 셀(Ac)의 조성.

    어트리션은 계면을 풀 뿐 물질을 바꾸지 않으므로, C 에서 백시트 몫을 뺀
    나머지가 그대로 Ac 다: ``Ac = (C − f·B) / (1 − f)``.

    「C 를 벗기면 A 가 된다」로 두면 A 가 4,500 g/t, B 가 100 g/t 인데 C 가
    3,000 g/t 이므로 Ag 가 창출된다 — 미니앱이 실제로 그 오류를 갖고 있었다.
    """
    f = C_BACKSHEET_MASS_FRACTION
    b, c = LAMINATE_ASSAY["B"], LAMINATE_ASSAY["C"]
    return {k: (c[k] - f * b[k]) / (1 - f) for k in c}


#: 폴리머 역부선의 속도론. 폴리머는 소수성이라 속부선 분획이 크고, Si·Ag 는
#: 친수성이라 진부선이 없으며 연행만 남는다. 이 표는 미니앱의 부유도
#: (B 1 · C 0.35 · A 0.03)와 같은 이야기를 속도상수로 옮긴 것이며,
#: 미니앱과 마찬가지로 **벤치 락사이클로 대체해야 할 HOLD** 다.
POLYMER_FLOAT_KINETICS = {
    "polymer_free": ComponentKinetics(
        "polymer_free", fast_fraction=0.88, k_fast=1.90,
        slow_fraction=0.09, k_slow=0.28, entrainment_factor=0.30,
    ),
    # 셀에 붙어 있는 EVA — 입자가 친수성이라 뜨지 않는다. 이것이 품위 문제의 뿌리다.
    "polymer_bound": ComponentKinetics("polymer_bound", entrainment_factor=0.30),
    "Si": ComponentKinetics("Si", entrainment_factor=0.30),
    "Ag": ComponentKinetics("Ag", entrainment_factor=0.30),
    "Cu": ComponentKinetics("Cu", entrainment_factor=0.30),
    "Al": ComponentKinetics("Al", entrainment_factor=0.30),
}

SPECIFIC_GRAVITY = {
    "polymer_free": 1.20, "polymer_bound": 1.20,
    "Si": 2.33, "Ag": 10.49, "Cu": 8.96, "Al": 2.70,
}


@dataclass(frozen=True)
class LaminateResult:
    """2 단 회로를 통과시킨 결과."""

    feed_ag_kg_h: float
    sinks_tph: float
    sinks_ag_kg_h: float
    polymer_removed_fraction: float
    concentrate_kg_h: float
    concentrate_ag_kg_h: float
    plant_recovery: float
    grade_wt_percent: float

    @property
    def meets_recovery(self) -> bool:
        return self.plant_recovery >= 0.99

    @property
    def meets_grade(self) -> bool:
        return self.grade_wt_percent >= 10.0


def laminate_feed_tph(debond: float = 1.0) -> dict[str, float]:
    """어트리션을 지난 습식 급광의 성분별 t/h.

    ``debond`` 는 AS-101/101B 2 단 어트리션의 총 해리도다. 벗겨진 C 는
    해리 셀(Ac)과 백시트(B)로 갈리며, **Ag 는 그 과정에서 보존된다.**
    폴리머는 「떨어져 나온 것(free)」과 「셀에 붙은 것(bound)」으로 나눠
    추적한다 — 부선에서 둘의 거동이 정반대이기 때문이다.
    """
    reject = FRESH_FEED_TPH * CLASS_FRACTION["B"] * BACKSHEET_SCALP_FRACTION
    mass = {t: FRESH_FEED_TPH * f for t, f in CLASS_FRACTION.items()}
    mass["B"] -= reject                      # BIN-102 로 빠진 백시트
    freed = mass["C"] * debond
    mass["Ac"] = freed * (1 - C_BACKSHEET_MASS_FRACTION)
    mass["B"] += freed * C_BACKSHEET_MASS_FRACTION
    mass["C"] -= freed

    assay = dict(LAMINATE_ASSAY)
    assay["Ac"] = liberated_cell_assay()
    out = {k: 0.0 for k in SPECIFIC_GRAVITY}
    for cls, m in mass.items():
        a = assay[cls]
        # 떨어져 나온 백시트(B)의 폴리머만 자유 상이다. A·Ac·C 의 폴리머는
        # 셀에 붙어 있어 부선으로 뗄 수 없다.
        key = "polymer_free" if cls == "B" else "polymer_bound"
        out[key] += m * a["polymer"] / 100
        out["Si"] += m * a["Si"] / 100
        out["Cu"] += m * a["Cu"] / 100
        out["Al"] += m * a["Al"] / 100
        out["Ag"] += m * a["ag_gpt"] / 1e6
    return out


def run(
    debond: float = 1.0,
    rfc_ag_recovery: float = 0.997,
    ag_stage_polymer_rejection: float = 0.94,
    composite_carry_ratio: float = 1.1,
) -> LaminateResult:
    """2 단 회로를 풀어 플랜트 회수율과 품위를 낸다.

    Args:
        debond: AS-101/101B 총 해리도.
        rfc_ag_recovery: FC-101 리플럭스 부선의 Ag 회수율. 문헌값 0.997 은
            단일 90 min 시험이고 광미가 검출한계 이하라, 미니앱과 마찬가지로
            0.990–0.997 밴드로 다루는 것이 정직하다.
        ag_stage_polymer_rejection: 2 단(분쇄＋RFC＋폴리싱)이 밀어내는 폴리머
            비율. **품위를 가르는 값이고 근거가 없다** — 미니앱의 관문 4.
    """
    feed = laminate_feed_tph(debond)
    feed_ag = feed["Ag"]
    # 건식 폐기(BIN-102)로 빠진 백시트의 Ag 도 플랜트 급광에는 들어간다.
    reject_tph = FRESH_FEED_TPH * CLASS_FRACTION["B"] * BACKSHEET_SCALP_FRACTION
    reject_ag = reject_tph * LAMINATE_ASSAY["B"]["ag_gpt"] / 1e6
    plant_feed_ag = feed_ag + reject_ag

    rougher = FlotationUnit(tag="FC-201", duty="폴리머 러퍼", target_residence_min=10.0,
                            water_recovery=0.28, dilution_target_solids=0.25)
    scavenger = FlotationUnit(tag="FC-203", duty="폴리머 스캐빈저", target_residence_min=14.0,
                              water_recovery=0.32)
    cleaner = FlotationUnit(tag="FC-204", duty="폴리머 세척 클리너", target_residence_min=5.0,
                            water_recovery=0.18, wash_water_m3h=0.4)
    result = solve_circuit(
        feed_component_tph=feed,
        kinetics=POLYMER_FLOAT_KINETICS,
        specific_gravity=SPECIFIC_GRAVITY,
        rougher=rougher, scavenger=scavenger, cleaner=cleaner,
        rougher_feed_solids=0.25,
    )
    # 역부선이므로 **미광(tailings)이 산물**이다.
    sinks = result.tailings
    sinks_totals = sinks.component_totals
    sinks_ag = sinks_totals.get("Ag", 0.0)
    polymer_in = feed["polymer_free"] + feed["polymer_bound"]
    polymer_out = sinks_totals.get("polymer_free", 0.0) + sinks_totals.get("polymer_bound", 0.0)
    removed = 1 - polymer_out / polymer_in if polymer_in > 0 else 0.0

    # 2 단 — 침강물만 분쇄해 RFC 로 띄운다.
    recovered = sinks_ag * rfc_ag_recovery
    concentrate = (
        recovered
        + recovered * composite_carry_ratio
        + polymer_out * (1 - ag_stage_polymer_rejection)
        + sinks_totals.get("Cu", 0.0) * 0.10          # 분쇄 전 Cu 선별 90 % 가정
    )
    return LaminateResult(
        feed_ag_kg_h=plant_feed_ag * 1000,
        sinks_tph=sinks.dry_tph,
        sinks_ag_kg_h=sinks_ag * 1000,
        polymer_removed_fraction=removed,
        concentrate_kg_h=concentrate * 1000,
        concentrate_ag_kg_h=recovered * 1000,
        plant_recovery=recovered / plant_feed_ag if plant_feed_ag > 0 else 0.0,
        grade_wt_percent=recovered / concentrate * 100 if concentrate > 0 else 0.0,
    )
