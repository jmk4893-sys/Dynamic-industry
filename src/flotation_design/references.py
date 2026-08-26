"""설계 근거가 되는 공개 실험 데이터.

본 설계는 아래 두 편의 실증 결과를 1차 근거로 삼는다. 코드의 모델
파라미터는 여기 기록된 수치를 재현하도록 보정했고, 테스트가 그 재현성을
검증한다 (``tests/test_references.py``).

[1] H. Saffarian, K.P. Galvin, M. Firouzi,
    "Rethinking silver recovery pathways in end-of-life photovoltaic
    recycling using froth flotation", Minerals Engineering 242 (2026) 110189.
    — 실회수 태양광 셀을 쓴 회분식(batch) 기계식 부선 실험.

[2] H. Saffarian, K.P. Galvin, M. Firouzi,
    "Continuous flotation unlocks full recovery of silver from end-of-life
    solar cells", ChemRxiv preprint (2026-05-24),
    doi:10.26434/chemrxiv.15003814/v1.
    — 동일 계통의 **연속 정상상태** 실증. 세척수(bias)를 쓰는 1단 부선조.

주의 — [2] 는 심사 전 프리프린트이며, 저자들이 해당 공정에 대해
호주 가출원(Australian Provisional Patent Application No. 2025902821,
"Recovery of silver from photovoltaic cells")을 제출한 상태다. 상업화 시
실시권 검토가 필요하다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BatchTest:
    """[1] 회분식 시험 조건과 결과."""

    label: str
    cell_volume_l: float
    solids_wt_percent: float
    tip_speed_m_s: float
    jg_cm_s: float
    reagent_g_per_t: float
    flotation_time_min: float
    feed_ag_wt_percent: float
    concentrate_ag_wt_percent: float
    tailings_ag_wt_percent: float
    mass_yield_percent: float
    ag_recovery_percent: float
    ag_upgrade: float
    water: str


#: [1] Table 1 — 수돗물, 1 L 셀, 150 g/t (3회 평균). 본 설계의 기준 회분식 결과.
BATCH_TAP_WATER = BatchTest(
    label="1 L 회분식 러퍼 / 수돗물 / 150 g/t",
    cell_volume_l=1.0,
    solids_wt_percent=7.0,
    tip_speed_m_s=5.3,
    jg_cm_s=0.20,
    reagent_g_per_t=150.0,
    flotation_time_min=3.0,
    feed_ag_wt_percent=0.75,
    concentrate_ag_wt_percent=24.0,
    tailings_ag_wt_percent=0.019,
    mass_yield_percent=2.92,
    ag_recovery_percent=97.6,
    ag_upgrade=32.2,
    water="tap",
)

#: [1] — 초순수 기준선. 수돗물보다 회수율이 낮다 (역설적이지만 재현됨).
BATCH_ULTRAPURE = BatchTest(
    label="1 L 회분식 러퍼 / 초순수 / 150 g/t",
    cell_volume_l=1.0,
    solids_wt_percent=7.0,
    tip_speed_m_s=5.3,
    jg_cm_s=0.20,
    reagent_g_per_t=150.0,
    flotation_time_min=3.0,
    feed_ag_wt_percent=0.75,
    concentrate_ag_wt_percent=25.4,
    tailings_ag_wt_percent=0.019,
    mass_yield_percent=2.70,
    ag_recovery_percent=91.31,
    ag_upgrade=33.8,
    water="ultrapure",
)

#: [1] — 러퍼 + 클리너 개방회로 (클리너 미광을 최종 미광으로 계상).
#: 폐회로로 돌리면 회수율은 러퍼 값에 근접한다고 저자들이 명시.
BATCH_ROUGHER_CLEANER = {
    "ag_recovery_percent": 86.5,
    "ag_recovery_sd": 2.8,
    "ag_upgrade": 62.6,
    "ag_upgrade_sd": 2.0,
    "concentrate_ag_wt_percent": 46.7,
    "feed_to_leach_percent": 1.4,
    "note": "개방회로. 폐회로 운전 시 러퍼 수준(~97%)에 근접 예상.",
}

#: [1] Table 2 — 수돗물 시험의 Cu·Pb 거동 (3회 평균).
BATCH_BASE_METALS = {
    "Cu": {"feed_wt_percent": 0.013, "recovery_percent": 81.4, "upgrade": 19.7},
    "Pb": {"feed_wt_percent": 0.096, "recovery_percent": 20.9, "upgrade": 9.23},
}

#: [1] 3.2절 — 회분식 Ag 회수율-시간 곡선의 인용 지점.
BATCH_KINETIC_POINTS = ((1.0, 0.80), (3.0, 0.90))

#: [1] 3.1절 — TIMA 해리도 분석.
LIBERATION = {
    "fully_liberated_above_90pct": 0.20,
    "above_60pct_liberation": 0.61,
    "note": "전처리 박리만으로도 전면 전극 Ag 가 일부 노출되며, "
    "Si 기지 내부에 갇힌 난용성 Ag 는 거의 없다고 저자들이 판단.",
}


@dataclass(frozen=True)
class ContinuousTrial:
    """[2] 연속 정상상태 실증 조건과 결과."""

    label: str
    cross_section_mm: tuple[float, float]
    feed_flux_cm_s: float
    air_flux_cm_s: float
    wash_water_flux_cm_s: float
    gas_liquid_residence_min: float
    solids_wt_percent: float
    p80_micron: float
    collector_g_per_t: float
    promoter_g_per_t: float
    frother_ppm: float
    bubble_size_mm: tuple[float, float]
    feed_ag_wt_percent: float
    concentrate_ag_wt_percent: float
    solids_yield_percent: float
    ag_recovery_percent: float
    ag_upgrade: float
    steady_state_min: float
    total_run_min: float
    max_feasible_solids_wt_percent: float

    @property
    def cross_section_m2(self) -> float:
        return self.cross_section_mm[0] * self.cross_section_mm[1] / 1e6


#: [2] — 세척수(bias)를 쓰는 1단 연속 부선조. 논문은 셀 형식을 명시하지 않으나
#: 인용 문헌(Reflux Flotation Cell 계열)과 운전 변수(스파저, 세척수 flux,
#: 기액 체류시간)로 볼 때 RFC 계열 장치로 판단된다.
CONTINUOUS_TRIAL = ContinuousTrial(
    label="1단 연속 부선조 / 세척수 bias / 정상상태 42~90 min",
    cross_section_mm=(100.0, 80.0),
    feed_flux_cm_s=2.0,
    air_flux_cm_s=2.0,
    wash_water_flux_cm_s=0.81,
    gas_liquid_residence_min=1.0,
    solids_wt_percent=2.0,
    p80_micron=66.0,
    collector_g_per_t=300.0,
    promoter_g_per_t=300.0,
    frother_ppm=30.0,
    bubble_size_mm=(0.5, 1.0),
    feed_ag_wt_percent=0.590,
    concentrate_ag_wt_percent=48.8,
    solids_yield_percent=1.25,
    ag_recovery_percent=99.7,
    ag_upgrade=83.0,
    steady_state_min=42.0,
    total_run_min=90.0,
    max_feasible_solids_wt_percent=30.0,
)

#: [2] — 습식 분쇄 원료는 건조 원료 대비 약제를 2배 써야 거품이 선다.
#: 실기는 습식 분쇄물을 그대로 쓰므로 300 g/t 가 설계 기준이다.
WET_FEED_REAGENT_FACTOR = 2.0

#: [2] — 모듈 질량 중 셀 분획 비율 (Deng et al. 2022a 인용).
CELL_FRACTION_OF_MODULE = 0.047

#: 실증 규모 요약 — 처리량 환산 근거로 인용.
TRIAL_SCALE = {
    "cell_material_kg": 22.0,
    "equivalent_panel_kg": 468.0,
    "feed_rate_kg_min": 0.20,
    "trl": 5,
}
