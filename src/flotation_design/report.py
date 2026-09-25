"""설계 계산서 생성 (Markdown)."""

from __future__ import annotations

from . import design_basis as db
from . import references as ref
from .attrition import short_circuit_fraction
from .attrition_pilot import (
    continuous_energy_factor,
    direct_drive_motor,
    hydrogen_from_aluminium_nm3,
    pilot_scale_up,
    ventilation_for_hydrogen_m3h,
)
from .eva_separation import (
    concentrate_grade_with_eva,
    eva_rate_constant_1_min,
    grade_margin_tph,
)
from .feed import PulpProperties
from .hydrodynamics import analyse_cell
from .kinetics import perfect_mixer_recovery
from .circuit import concentrate_grade_ceiling, solve_circuit
from .transient import simulate_startup
from .plant import (
    PlantDesign,
    build_mechanism_screen,
    build_pilot,
    build_plant,
    mechanical_sizing_check,
)
from .sizing import SHAFT_OD_SERIES_MM, cantilever_rotor_dynamics
from .reagents import reagent_schedule


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _filter_row(f) -> list[str]:
    return [f.tag, f.duty,
            f"여과판 {f.plate_mm:.0f} mm x {f.chambers} 챔버, 면적 {f.filter_area_m2:.2f} m2"]


def _filter_table(presses) -> str:
    """필터프레스 사양표."""
    return _table(
        ["항목"] + [f.tag for f in presses],
        [
            ["역할"] + [f.duty for f in presses],
            ["급광 고체 (kg/h)"] + [f"{f.dry_tph * 1000:.2f}" for f in presses],
            ["급광 농도 (농축조 U/F)"] + [f"{f.feed_solids_wt * 100:.0f} wt%" for f in presses],
            ["여과판"] + [f"{f.plate_mm:.0f} x {f.plate_mm:.0f} mm" for f in presses],
            ["챔버 수"] + [f"{f.chambers}" for f in presses],
            ["**여과 면적 (m2)**"] + [f"**{f.filter_area_m2:.2f}**" for f in presses],
            ["챔버 총용적 (L)"] + [f"{f.chamber_volume_m3 * 1000:.1f}" for f in presses],
            ["사이클 시간 (min)"] + [f"{f.cycle_min:.0f}" for f in presses],
            ["사이클/일"] + [f"{f.cycles_per_day:.1f}" for f in presses],
            ["사이클당 건조 고체 (kg)"] + [f"{f.dry_per_cycle_kg:.1f}" for f in presses],
            ["챔버 충전율"] + [f"{f.chamber_utilisation * 100:.0f} %" for f in presses],
            ["케이크 함수율"] + [f"{f.cake_moisture * 100:.0f} wt%" for f in presses],
            ["**케이크 생산량 (kg/h)**"] + [f"**{f.cake_tph * 1000:.1f}**" for f in presses],
            ["여액 (m3/h)"] + [f"{f.filtrate_m3h:.3f}" for f in presses],
            ["급광 펌프 (kW)"] + [f"{f.pump_rating_kw:.2f}" for f in presses],
            ["규격 결정 기준"] + [f.governed_by for f in presses],
        ],
    )


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}"


def _kgh(x: float, digits: int = 2) -> str:
    return f"{x * 1000:.{digits}f}"


def _delta(model: float, published: float) -> str:
    if published == 0:
        return "—"
    return f"{(model - published) / published * 100:+.1f} %"


def render(design: PlantDesign | None = None) -> str:
    """태양광 셀 Ag 회수 부선 설비 설계 계산서."""
    d = design if design is not None else build_plant()
    f, rfc, mech = d.feed, d.rfc, d.mechanical
    pre = d.pretreatment
    sc, dil = pre.scrubber, pre.dilution
    g, dr, sh = sc.geometry, sc.drive, sc.shaft
    pc, ms = build_pilot(f), build_mechanism_screen(f)
    su = pilot_scale_up(sc, f.peak_tph, f.average_tph, db.PILOT_EVA_REMOVAL_TARGET)
    trial = ref.CONTINUOUS_TRIAL
    batch = ref.BATCH_TAP_WATER
    peak_label = f"최대 {f.peak_tph:.2f} t/h"
    avg_label = f"평균 {f.average_tph:.2f} t/h"
    lines: list[str] = []
    add = lines.append

    add("# 태양광 셀 은(Ag) 회수 부선 설비 설계 계산서")
    add("")
    add("> `PYTHONPATH=src python -m flotation_design` 로 자동 생성됨. "
        "설계 기준은 `src/flotation_design/design_basis.py`, "
        "근거 실험값은 `src/flotation_design/references.py` 참조.")
    add("")

    # 0. 설계 근거 ---------------------------------------------------------
    add("## 0. 설계 근거")
    add("")
    add("본 설계는 아래 두 실증 결과를 1차 근거로 삼는다. 모델 파라미터는 이 수치를 "
        "재현하도록 보정했고, `tests/test_references.py` 가 재현성을 검증한다.")
    add("")
    add(_table(
        ["출처", "장치", "조건", "결과"],
        [
            ["[1] Minerals Engineering 242 (2026) 110189",
             f"{batch.cell_volume_l:.0f} L 회분식 기계식 셀",
             f"{batch.solids_wt_percent:.0f} wt%, Jg {batch.jg_cm_s:.2f} cm/s, "
             f"{batch.reagent_g_per_t:.0f} g/t, {batch.flotation_time_min:.0f} min, 수돗물, 자연 pH",
             f"Ag 회수율 {batch.ag_recovery_percent:.1f} %, 정광 {batch.concentrate_ag_wt_percent:.1f} wt% Ag, "
             f"농축비 {batch.ag_upgrade:.1f}, 질량수율 {batch.mass_yield_percent:.2f} %"],
            ["[1] 동상 — 러퍼+클리너 개방회로", "동상", "클리너 1단 추가",
             f"Ag 회수율 {ref.BATCH_ROUGHER_CLEANER['ag_recovery_percent']:.1f} %, "
             f"정광 {ref.BATCH_ROUGHER_CLEANER['concentrate_ag_wt_percent']:.1f} wt% Ag, "
             f"농축비 {ref.BATCH_ROUGHER_CLEANER['ag_upgrade']:.1f}"],
            ["[2] ChemRxiv 2026 (프리프린트)",
             f"연속 1단 부선조 {trial.cross_section_mm[0]:.0f}x{trial.cross_section_mm[1]:.0f} mm",
             f"Jf {trial.feed_flux_cm_s:.1f} / Jg {trial.air_flux_cm_s:.1f} / "
             f"Jw {trial.wash_water_flux_cm_s:.2f} cm/s, 기액 체류 {trial.gas_liquid_residence_min:.0f} min, "
             f"{trial.solids_wt_percent:.0f} wt%",
             f"Ag 회수율 ~{trial.ag_recovery_percent:.0f} %, 정광 {trial.concentrate_ag_wt_percent:.1f} wt% Ag, "
             f"농축비 {trial.ag_upgrade:.0f}, 질량수율 {trial.solids_yield_percent:.2f} %"],
        ],
    ))
    add("")
    add("> [!IMPORTANT]")
    add("> [2] 는 심사 전 프리프린트이며, 저자들이 해당 공정에 대해 호주 가출원"
        "(No. 2025902821, \"Recovery of silver from photovoltaic cells\")을 제출한 상태다. "
        "상업화 전 실시권 검토가 필요하다.")
    add("")

    # 1. 급광 -------------------------------------------------------------
    add("## 1. 급광 사양")
    add("")
    add(_table(
        ["항목", "값", "근거"],
        [
            ["평균 / 최대 처리량", f"{f.average_tph:.2f} / {f.peak_tph:.2f} t/h (건조 고체)", "요구사항"],
            ["원료", "박리된 c-Si 셀 분획 (습식 로드밀 분쇄)", "[1][2]"],
            ["급광 입도 P80", f"{f.p80_micron:.0f} um", "[2]"],
            ["설계 고체 농도", f"{f.solids_mass_fraction * 100:.0f} wt%",
             f"[1] 회분식 검증값. [2] 연속 실증은 {trial.solids_wt_percent:.0f} wt%, "
             f"저자 주장 상한 {trial.max_feasible_solids_wt_percent:.0f} wt% (PV 원료 미검증)"],
            ["고체 평균 비중", f"{f.solids_specific_gravity:.3f}", "성분 조성 가중"],
            ["pH", "조정 없음 (자연 pH)", "[1][2] 모두 무조정 운전"],
            ["모듈 대비 셀 분획 비율", f"{ref.CELL_FRACTION_OF_MODULE * 100:.1f} %", "[2]"],
            ["환산 모듈 처리량",
             f"{f.average_tph / ref.CELL_FRACTION_OF_MODULE:.1f} / "
             f"{f.peak_tph / ref.CELL_FRACTION_OF_MODULE:.1f} t/h",
             "상류 박리 설비가 감당해야 할 규모"],
        ],
    ))
    add("")
    add(_table(
        ["성분", "질량분율 (wt%)", "품위 (g/t)", "비중", "속부선", "지연부선", "비부선",
         "k_fast", "k_slow", "출처"],
        [
            [
                c.name,
                f"{c.mass_fraction * 100:.3f}",
                f"{c.mass_fraction * 1e6:,.0f}",
                f"{c.specific_gravity:.2f}",
                _pct(db.FLOAT_MODELS[c.name].fast_fraction, 0),
                _pct(db.FLOAT_MODELS[c.name].slow_fraction, 0),
                _pct(db.FLOAT_MODELS[c.name].nonfloating_fraction, 0),
                f"{db.FLOAT_MODELS[c.name].k_fast:.2f}",
                f"{db.FLOAT_MODELS[c.name].k_slow:.2f}",
                {"Ag": "[2] assay", "Cu": "[1] Table 2", "Pb": "[1] Table 2"}.get(c.name, "추정"),
            ]
            for c in f.components
        ],
    ))
    add("")
    add(f"속도상수는 **회분식 기준**이며, 실기 연속 셀에는 스케일업 계수 "
        f"{db.PLANT_SCALE_FACTOR:.1f} 를 곱해 쓴다. Ag 의 비부선 분획 "
        f"{db.FLOAT_MODELS['Ag'].nonfloating_fraction * 100:.1f} % 는 [1] 의 TIMA 해리도 분석"
        f"(>90 % 해리 {ref.LIBERATION['fully_liberated_above_90pct'] * 100:.0f} %, "
        f">60 % 해리 {ref.LIBERATION['above_60pct_liberation'] * 100:.0f} %)과 회분식 극한 회수율에 맞춘 값이다.")
    add("")
    add("### 정광 품위의 물리적 상한")
    add("")
    add(f"Ag 는 순수 입자가 아니라 Si 웨이퍼에 소결된 전극이다. 표면이 소수성이 되어 부상해도 "
        f"**Si 코어를 함께 끌고 올라간다.** 부상 Ag 1 kg 당 동반 맥석 "
        f"{db.COMPOSITE_CARRY_RATIO:.1f} kg 으로 두면 정광 품위 상한은 "
        f"1/(1+{db.COMPOSITE_CARRY_RATIO:.1f}) = "
        f"**{concentrate_grade_ceiling(db.COMPOSITE_CARRY_RATIO) * 100:.1f} wt% Ag** 다. "
        f"[2] 의 연속 정광이 {trial.concentrate_ag_wt_percent:.1f} wt%, [1] 의 러퍼+클리너 정광이 "
        f"{ref.BATCH_ROUGHER_CLEANER['concentrate_ag_wt_percent']:.1f} wt% 에서 멈춘 것이 이 상한으로 설명된다. "
        f"이 동반분은 **수분 동반과 달리 세척수로 제거되지 않는다** — 클리너를 아무리 더 붙여도 "
        f"넘을 수 없는 벽이다.")
    add("")

    # 2. 전처리 -----------------------------------------------------------
    add("## 2. 전처리 — 어트리션 스크러버 · 떨어진 EVA 분리 (공통 설비)")
    add("")
    add("로드밀 배출 슬러리를 **묽히기 전에** 고농도 그대로 받아 입자끼리 문질러, 셀 분획 "
        "입자 표면에 붙은 **EVA(봉지재)를 떼어낸다.** 그 뒤 희석박스에서 부선 농도로 묽히고, "
        "떨어진 EVA 를 기포제만 쓰는 부선으로 걷어낸 뒤(§2.8) 조건조로 보낸다. 두 안이 함께 "
        "쓰는 공통 설비이므로 1안·2안 어느 쪽 설치 전력에도 포함하지 않고 따로 계상한다. "
        "분쇄기가 아니라는 점이 중요하다 — 입자를 깨는 것이 아니라 **표면에 붙은 EVA 를 "
        "떼는 것**이 목적이다.")
    add("")
    add("**역할의 경계.** 이 설비가 하는 일은 EVA 박리 하나다. 은(Ag)을 띄우는 것은 뒤의 "
        "부선조(§3·§4)가 한다. 그래서 이 설비의 성능은 부선 성적이 아니라 두 가지로만 판정한다.")
    add("")
    add(f"- **부착 EVA 제거율** — 스크럽 전후, 물에 가라앉은 분획의 EVA(TGA) 비교. "
        f"목표 ≥ {db.PILOT_EVA_REMOVAL_TARGET * 100:.0f} % (잠정)")
    add(f"- **미립 생성** — 스크럽 전후 −10 µm 질량분율 증가 ≤ "
        f"{db.ATTRITION_FINES_ACCEPTANCE_PP:.0f} %p. 넘으면 EVA 를 떼는 것이 아니라 "
        f"Si 를 갈고 있다는 뜻이다.")
    add("")
    add("> [!IMPORTANT]")
    add("> **부선 성능 크레딧 없음.** 이 원료(31~75 µm 미분)에서 EVA 가 기계적으로 "
        "떨어진다는 시험 근거는 아직 없다. 박리 성능은 시험 셀 PAS-1(§2.6)에서 확정한다. "
        "부선 계산은 문헌 원료 기준이며 EVA 를 뗀 효과를 회수율·품위·약제에 반영하지 "
        f"않는다 (`ATTRITION_PERFORMANCE_CREDIT = {db.ATTRITION_PERFORMANCE_CREDIT:.1f}`). "
        f"대신 전량 바이패스({pre.bypass})를 두어 없는 것처럼 운전할 수 있게 했다. "
        "박리가 확인되지 않으면 바이패스로 두거나 열분해로 간다.")
    add("")
    add("### 2.1 운전 기준 — 고체 농도가 전부다")
    add("")
    add(_table(
        ["항목", "값", "근거 · 판정"],
        [
            ["기기 번호 / 역할", f"{sc.tag} / {sc.duty}", "공통 설비"],
            ["**스크러빙 고체 농도**", f"**{sc.solids_mass_fraction * 100:.0f} wt%**",
             "실리카사 스크러빙 표준 70~75 wt%"],
            ["**고체 체적분율**", f"**{sc.solids_volume_fraction * 100:.1f} vol%**",
             f"하한 {sc.minimum_solids_volume_fraction * 100:.0f} vol% — "
             + ("OK" if sc.solids_volume_fraction_ok else "**NG**")
             + ". 이 정도라야 입자끼리 닿는다"],
            ["슬러리 밀도", f"{sc.pulp.pulp_density_kg_m3:.0f} kg/m3", "동력 계산 기준"],
            ["슬러리 유량 (최대)", f"{sc.pulp.volumetric_flow_m3h:.3f} m3/h",
             f"같은 고체를 {f.solids_mass_fraction * 100:.0f} wt% 로 묽히면 "
             f"{d.rfc.point_peak.feed_m3h:.2f} m3/h — **{d.rfc.point_peak.feed_m3h / sc.pulp.volumetric_flow_m3h:.0f}배**"],
            ["상류 로드밀 배출 농도 요구",
             f"≥ {db.ATTRITION_MILL_DISCHARGE_MIN_SOLIDS_WT * 100:.0f} wt%",
             f"봉형밀 배출 통상 65~75 wt% 라 대개 만족한다. 절대 하한은 "
             f"{sc.minimum_solids_mass_fraction * 100:.0f} wt% "
             f"(= {sc.minimum_solids_volume_fraction * 100:.0f} vol%) 이고 그 아래는 "
             f"어트리션이 아니라 교반이다. 미달 시 앞단 사이클론 탈수 — "
             f"**상류 계약 인터페이스 조건**"],
            ["직렬 셀 수", f"{sc.cells} 기",
             f"1기면 급광의 {short_circuit_fraction(1) * 100:.0f} % 가 평균 체류시간의 절반도 "
             f"못 채우고 통과. {sc.cells}기면 {sc.short_circuit_fraction * 100:.0f} %, "
             f"3기라야 {short_circuit_fraction(3) * 100:.0f} % — 이 규모에서 3기는 값을 못 한다"],
            ["설계 체류시간", f"{sc.design_residence_min:.0f} min (총)", "표면 정정 통상 5~15 min"],
            ["**실제 체류시간**",
             f"**{sc.residence_min(f.peak_tph):.1f} min** ({peak_label}) / "
             f"{sc.residence_min(f.average_tph):.1f} min ({avg_label})",
             f"규격 결정 기준: **{sc.governed_by}**"],
        ],
    ))
    add("")
    add(f"체류시간이 설계값보다 긴 것은 문제가 아니다. 상용 최소 기종이 "
        f"{sc.nominal_cell_m3 * 1000:.0f} L 라 필요량("
        f"{sc.pulp.volumetric_flow_m3h * sc.design_residence_min / 60.0 / sc.cells * 1000:.0f} L/셀)"
        f"보다 큰 것을 살 수밖에 없기 때문이고, 어트리션의 실제 제어변수는 체류시간이 "
        f"아니라 **비에너지(kWh/t)** 이기 때문이다 (§2.3). 필터프레스 정광 라인이 "
        f"같은 이유로 상용 최소 기종에 걸린 것과 같은 상황이다.")
    add("")
    smaller_od = max(od for od in SHAFT_OD_SERIES_MM if od < sh.outer_diameter_mm)
    smaller_at_design = cantilever_rotor_dynamics(
        smaller_od, 0.0, sh.length_m, dr.speed_rpm, sh.overhung_mass_kg
    )
    smaller_at_ceiling = cantilever_rotor_dynamics(
        smaller_od, 0.0, sh.length_m, sh.check_speed_rpm, sh.overhung_mass_kg
    )
    add("### 2.2 기계 사양")
    add("")
    add(_table(
        ["항목", "값", "비고"],
        [
            ["조 형식", f"팔각조 {sc.cells} 기 직렬",
             "배플 없이 vortex 를 깨는 표준 형상"],
            ["**셀 내부 치수**",
             f"**AF {g.across_flats_m * 1000:.0f} mm x {g.depth_m * 1000:.0f} mm(D)**",
             f"대각 {g.circumscribed_diameter_m * 1000:.0f} mm, 여유고 "
             f"{g.freeboard_m * 1000:.0f} mm, 전고 {g.shell_height_m * 1000:.0f} mm"],
            ["셀당 유효 체적", f"{g.working_volume_m3 * 1000:.1f} L",
             f"상용 계열 {sc.nominal_cell_m3 * 1000:.0f} L 선정"],
            ["**총 유효 체적**", f"**{sc.total_working_volume_m3 * 1000:.1f} L**", ""],
            ["임펠러", f"대향 피치 축류 {dr.impellers_per_shaft} 단/축",
             "위는 아래로, 아래는 위로 밀어 두 흐름이 중간 높이에서 부딪히는 **충돌면**을 만든다 — "
             "입자끼리 문질린다"],
            ["임펠러 지름 / 간격",
             f"Ø{dr.diameter_m * 1000:.0f} mm / {dr.spacing_m * 1000:.0f} mm",
             f"조 폭 대비 {dr.diameter_m / g.across_flats_m:.2f} "
             f"(부선셀 로터 {db.IMPELLER_DIAMETER_RATIO:.2f} 보다 크다 — 조 전체를 움직여야 한다)"],
            ["설계 회전수 / 주속", f"{dr.speed_rpm:.0f} rpm / {dr.tip_speed_m_s:.2f} m/s",
             f"허용 {dr.tip_speed_min_m_s:.1f}~{dr.tip_speed_max_m_s:.1f} m/s — "
             + ("OK" if dr.tip_speed_ok else "**NG**")],
            ["VFD 조정 범위",
             f"{dr.tip_speed_min_m_s:.1f}~{dr.tip_speed_ceiling_m_s:.2f} m/s "
             f"({dr.speed_rpm_at_tip_speed(dr.tip_speed_min_m_s):.0f}~"
             f"{dr.speed_rpm_at_tip_speed(dr.tip_speed_ceiling_m_s):.0f} rpm)",
             f"상한은 흡수동력이 모터 정격/{dr.service_factor:.1f} 을 넘지 않는 점"],
            ["셀당 흡수동력 / 모터",
             f"{dr.absorbed_power_w / 1000.0:.2f} kW / **{dr.motor_rating_kw:.1f} kW**",
             f"P = {dr.impellers_per_shaft} x Np {dr.power_number:.1f} x rho x N^3 x D^5"],
            ["**체적당 동력**", f"**{sc.specific_power_kw_m3:.1f} kW/m3**",
             f"상용 어트리션 셀 통상 {sc.specific_power_range_kw_m3[0]:.0f}~"
             f"{sc.specific_power_range_kw_m3[1]:.0f} kW/m3 — "
             + ("OK" if sc.specific_power_ok else "**NG**")],
            ["**교반축 외경**", f"**Ø{sh.outer_diameter_mm:.0f} mm** (중실)",
             f"길이 {sh.length_m:.2f} m, 결정 기준 **{sh.governed_by}**"],
            ["축 토크 / 전단응력",
             f"{sh.torque_nm:.1f} N·m / {sh.shear_stress_mpa:.2f} MPa",
             f"VFD 상한 기준, 서비스계수 {sh.service_factor:.1f} (굳은 슬러리 기동 토크), "
             f"허용 {sh.allowable_shear_mpa:.0f} MPa"],
            ["1차 임계회전수 / 운전비",
             f"{sh.critical_speed_rpm:,.0f} rpm / {sh.critical_speed_ratio:.2f}x",
             f"**VFD 상한 {sh.check_speed_rpm:.0f} rpm** 기준, 하한 "
             f"{sh.minimum_critical_speed_ratio:.1f}x — "
             + ("OK" if sh.critical_speed_ratio >= sh.minimum_critical_speed_ratio else "**NG**")],
            ["예비 정적 처짐", f"{sh.static_deflection_mm:.2f} mm",
             f"허용 {sh.allowable_deflection_mm:.0f} mm"],
            ["마모 방호", sc.liner, "Si 는 모스 6.5 대의 각진 입자 — 미끄럼 마모가 심하다"],
            ["급광 방식", "중력 급광" if sc.feed_pump_kw == 0 else f"PC 펌프 {sc.feed_pump_kw:.2f} kW",
             f"{sc.solids_volume_fraction * 100:.0f} vol% 슬러리는 원심펌프로 보낼 수 없다"],
        ],
    ))
    add("")
    add(f"**축은 비틀림이 아니라 {sh.governed_by}이 지배한다.** 전단응력은 허용치의 "
        f"{sh.shear_stress_mpa / sh.allowable_shear_mpa * 100:.0f} % 에 불과하지만, "
        f"{sh.length_m:.2f} m 외팔보 끝에 임펠러 조립체 {sh.overhung_mass_kg:.0f} kg 이 "
        f"매달리므로 1차 굽힘 임계회전수가 운전 회전수에 가까워진다. 검산 회전수는 "
        f"설계점({dr.speed_rpm:.0f} rpm)이 아니라 **VFD 상한({sh.check_speed_rpm:.0f} rpm)** "
        f"이다 — 여유는 운전 범위 전체에서 지켜져야 한다. 한 치수 작은 "
        f"Ø{smaller_od:.0f} mm 는 설계점에서 {smaller_at_design.critical_speed_ratio:.2f}배로 "
        f"통과하지만 VFD 상한에서 {smaller_at_ceiling.critical_speed_ratio:.2f}배로 기준 "
        f"아래다. 임펠러 질량은 D^3 비례 예비값이므로 제작도 확정 후 실측 질량과 실제 "
        f"베어링 스팬으로 재검증해야 한다.")
    add("")
    add("### 2.3 비에너지 — 실제 제어변수")
    add("")
    add(f"어트리션의 스크러빙 강도는 체류시간이 아니라 **투입 에너지 / 처리량**으로 "
        f"결정된다. 상용 최소 기종을 샀으므로 체적은 남고, 처리량이 줄면 같은 회전수에서 "
        f"t 당 에너지가 오히려 커진다. 따라서 VFD 로 주속을 낮춰 목표 범위 "
        f"{sc.specific_energy_range_kwh_t[0]:.0f}~{sc.specific_energy_range_kwh_t[1]:.0f} kWh/t "
        f"안에 유지한다.")
    add("")
    add(_table(
        ["처리량", "설계 주속 유지 시", "권장 주속", "그때 흡수동력", "그때 비에너지"],
        [
            [
                label,
                f"{sc.specific_energy_kwh_t(tph):.2f} kWh/t",
                f"{sc.recommended_tip_speed_m_s(tph):.2f} m/s "
                f"({dr.speed_rpm_at_tip_speed(sc.recommended_tip_speed_m_s(tph)):.0f} rpm)",
                f"{dr.power_w_at_tip_speed(sc.recommended_tip_speed_m_s(tph)) * sc.cells / 1000.0:.2f} kW",
                f"**{sc.specific_energy_kwh_t(tph, sc.recommended_tip_speed_m_s(tph)):.2f} kWh/t**",
            ]
            for label, tph in ((peak_label, f.peak_tph), (avg_label, f.average_tph))
        ],
    ))
    add("")
    add(f"주속에는 하한이 있으므로({dr.tip_speed_min_m_s:.1f} m/s — 이보다 느리면 "
        f"{sc.solids_volume_fraction * 100:.0f} vol% 층이 움직이지 않는다) 동력도 더 내려가지 "
        f"않는다. 따라서 처리량이 **{sc.minimum_dry_tph:.2f} t/h** 아래로 내려가면 최저 "
        f"주속에서도 과다 스크러빙이 된다. 그 아래에서는 캠페인 운전하거나 바이패스한다.")
    add("")
    add("### 2.4 시험 계획과 합격 기준")
    add("")
    add("판정은 전부 EVA 기준이다. 은을 띄우는 부선 시험은 이 설비의 시험에 넣지 않는다.")
    add("")
    add("| 시험 | 방법 | 판정 |")
    add("|---|---|---|")
    add(f"| T-1 비에너지-박리 곡선 | 시험 셀 {db.PILOT_TAG}(§2.6)에서 "
        + " / ".join(f"{e:g}" for e in db.PILOT_ENERGY_POINTS_KWH_T)
        + " kWh/t 시료의 부착 EVA(TGA) | "
        f"1차 적합 → E90. §2.6 판정선과 비교해 AS-1 을 그대로 쓸지 정한다 |")
    add(f"| T-2 운전 변수 | {db.PILOT_TAG} 에서 주속 · 온도 · 농도를 바꿔 같은 채취 | "
        f"곡선이 비에너지 하나로 겹치는가 — 겹치면 비에너지만으로 운전한다 |")
    add("| T-3 실기 확인 | AS-1 시운전에서 급광·배출 시료의 부착 EVA 비교, 바이패스와 "
        "교대 운전 | 실기 비에너지 설정값 확정 · 존치 여부 결정 |")
    add(f"| T-4 미립 생성 | 스크럽 전후 −10 µm 질량분율 | 증가 "
        f"**{db.ATTRITION_FINES_ACCEPTANCE_PP:.0f} %p 이하** — 넘으면 EVA 를 떼는 것이 아니라 "
        f"Si 를 갈고 있다는 뜻 |")
    add("")
    add("**미립 생성이 이 설비의 진짜 위험이다.** 문헌 공정을 따라 탈니(desliming)를 하지 "
        "않으므로, 스크러버에서 깨져 나온 Si 미립은 걸러지지 않고 그대로 부선으로 넘어간다. "
        "그래서 미립은 걸러내는 것이 아니라 **애초에 만들지 않는 것**으로 관리한다 — 주속에 "
        "상한을 두고 비에너지를 VFD 로 잡는다.")
    add("")
    add(f"**떨어진 EVA 의 행방.** AS-1 은 EVA 를 입자에서 떼는 데까지 맡는다. 떨어진 EVA "
        f"(비중 {db.EVA_SG:.2f})는 배출 슬러리에 섞여 나가고, 희석박스 뒤의 "
        f"{db.EVA_ROUGHER_TAG} · {db.EVA_CLEANER_TAG}(§2.8)가 걷어낸다. {db.PILOT_TAG} 은 그 "
        f"설계에 필요한 떨어진 EVA 의 양과 크기를 함께 잰다 (§2.6 P-0 · P-1).")
    add("")
    add(f"**미분 한계.** 급광 P80 은 {f.p80_micron:.0f} µm 로, 어트리션 실적이 쌓인 "
        f"실리카사({db.REFERENCE_SAND_UM:.0f} µm)보다 한 자릿수 작다. 입자 하나가 "
        f"싣고 부딪히는 운동에너지는 d^3 로 줄고, t 당 벗겨야 할 표면은 "
        f"{ms.surface_ratio_to_sand:.0f}배로 는다. 목표 범위 "
        f"{sc.specific_energy_range_kwh_t[0]:.0f}~{sc.specific_energy_range_kwh_t[1]:.0f} kWh/t "
        f"는 모래의 통상값이라 **출발점일 뿐이다.** 이 원료에서 무엇을 얼마나 떼는지는 "
        f"{db.PILOT_TAG}(§2.6)이 정한다.")
    add("")
    add("### 2.5 희석박스와 물수지")
    add("")
    add(_table(
        ["항목", "값", "비고"],
        [
            ["기기 번호 / 역할", f"{dil.tag} / {dil.duty}", ""],
            ["입구 / 출구 농도",
             f"{dil.inlet_solids_wt * 100:.0f} → {dil.outlet_solids_wt * 100:.0f} wt%",
             "출구 농도는 밀도계로 제어 — 조건조 급광을 고정한다"],
            ["**희석수**", f"**{dil.dilution_water_m3h:.2f} m3/h**",
             "공정수 탱크에서 받는다 (아래 수급 확인)"],
            ["출구 유량", f"{dil.outlet_m3h:.2f} m3/h", "조건조 CT-1 급광"],
            ["체류시간 / 유효 체적",
             f"{dil.residence_min:.0f} min / {dil.working_volume_m3:.3f} m3",
             f"박스 {dil.box_volume_m3:.2f} m3"],
            ["교반기", f"{dil.agitator_kw:.2f} kW",
             "P80 66 um 입자의 Stokes 침강이 mm/s 급이라 2 분이면 수십 cm 를 가라앉는다"],
            ["바이패스", pre.bypass, "어트리션 없이 운전·A/B 시험용"],
        ],
    ))
    add("")
    add(f"희석수는 **설비 전체 물수지를 바꾸지 않는다.** 부선 농도 "
        f"{f.solids_mass_fraction * 100:.0f} wt% 를 맞추려고 어차피 들어가던 물이고, "
        f"어트리션은 그 물의 **투입 지점을 뒤로 미룰 뿐**이다. 계 밖으로 나가는 물"
        f"(케이크 잔류수 + 블리드)이 그대로이므로 신수 보충량도 그대로다. 바뀌는 것은 "
        f"공정수 탱크가 감당해야 할 유량뿐이다.")
    add("")
    add(f"희석수 {dil.dilution_water_m3h:.2f} m3/h 는 **계통에서 가장 큰 단일 공정수 "
        f"소비처**다 — 1안 세척수 {rfc.point_peak.wash_water_m3h:.2f} m3/h 의 "
        f"{dil.dilution_water_m3h / rfc.point_peak.wash_water_m3h:.1f}배다. 공정수 배관과 "
        f"밀도제어 밸브를 이 유량으로 잡는다. 회수 공정수(1안 {rfc.water_recycle_m3h:.2f} / "
        f"2안 {mech.water_recycle_m3h:.2f} m3/h)와 신수 보충(1안 {rfc.fresh_makeup_m3h:.2f} / "
        f"2안 {mech.fresh_makeup_m3h:.2f} m3/h)이 이 수요를 받치며, 두 안 모두 수급이 "
        f"성립한다"
        + (" — OK." if pre.water_supply_ok(rfc) and pre.water_supply_ok(mech) else " — **NG**.")
        + " 신수 보충량 자체는 어트리션 도입 전과 같다.")
    add("")
    add(f"**어트리션 계 설치 전력 {pre.attrition_kw:.2f} kW** "
        f"(어트리션 {sc.installed_kw:.2f} + 희석박스 교반 {dil.agitator_kw:.2f}). 떨어진 EVA "
        f"분리(§2.8) {pre.eva.installed_kw:.2f} kW 를 더하면 전처리 계 "
        f"**{pre.installed_kw:.2f} kW**, 1안과 합치면 {d.total_installed_kw(rfc):.2f} kW 로 "
        f"전처리가 계통 전체의 **{pre.installed_kw / d.total_installed_kw(rfc) * 100:.0f} %** 를 "
        f"쓴다. 박리가 시험으로 확인되기 전인 설비로서는 결코 작지 않은 비용이며, 바이패스와 "
        f"시험 계획을 설계에 넣은 이유가 이것이다.")
    add("")

    # 2.6 파일럿 시험 셀 ---------------------------------------------------
    pg, pd, ps, pm = pc.geometry, pc.drive, pc.shaft, pc.motor
    size_lo, size_hi = db.PILOT_FEED_SIZE_UM
    tips = pc.test_tip_speeds_m_s
    top_tip, low_tip = max(tips), min(tips)
    base_tip = db.ATTRITION_DESIGN_TIP_SPEED_M_S
    base_temp = sorted(pc.temperatures_c)[len(pc.temperatures_c) // 2]
    side_temps = " · ".join(f"{t:.0f}" for t in pc.temperatures_c if t != base_temp)
    energies = " / ".join(f"{e:g}" for e in pc.energy_points_kwh_t)
    lel_pct = db.H2_LEL_VOL * 100.0
    design_vol_pct = lel_pct * db.H2_DESIGN_LEL_FRACTION
    tolerable_kg_h = pc.tolerable_aluminium_reaction_per_h * pc.aluminium_in_batch_kg
    low_batch = pc.low_solids_batch
    wall_ratio = pg.wetted_area_per_volume_m / g.wetted_area_per_volume_m
    nozzle_l = pc.pipe_volume_l(50.0, 100.0)
    top_rpm = pc.speed_rpm(top_tip)
    run_min = [pc.run_minutes(t) for t in sorted(tips, reverse=True)]
    add(f"### 2.6 파일럿 시험 셀 {pc.tag} — 블랙파우더 EVA 박리")
    add("")
    add(f"AS-1 이 이 원료에서 EVA 를 뗄 수 있는지는 아직 시험 근거가 없다. {pc.tag} 은 그 "
        f"시험을 하는 장비다 — PV 블랙파우더({size_lo:.0f}~{size_hi:.0f} µm)의 Si 표면에 "
        f"붙은 EVA 를 **기계적으로** 뗄 수 있는지, 뗀다면 **몇 kWh/t 에서, Si 를 얼마나 "
        f"깨뜨리면서** 떼는지 잰다. 같은 셀이 §2.4 의 T-1 · T-2 를 맡는다. 은을 띄우는 부선 "
        f"시험은 하지 않는다. 제작해서 시험하는 장비이므로 설치 전력·물수지에 넣지 않는다.")
    add("")
    add("**방식 선정.** 박리는 표면에 힘을 거는 문제다. 무엇이 그 힘을 거는지로 가른다.")
    add("")
    add(_table(
        ["방식", "박리 기구", "판정"],
        [
            ["로터-스테이터 고전단", "유체 전단 τ = μ_eff x γ̇",
             f"γ̇ {ms.shear_rate_s:,.0f} /s · {ms.volume_fraction * 100:.1f} vol% 에서도 "
             f"τ ≈ {ms.fluid_shear_pa / 1000:.1f} kPa — 벌크 EVA 강도(보수적 하한 "
             f"{ms.eva_strength_mpa:.0f} MPa)의 **1/{ms.shear_shortfall:,.0f}**. Si/EVA 계면 "
             f"박리강도는 따로 잰 값이 없지만 세 자릿수 차이라 유체 전단 단독은 주 박리 기구가 "
             f"되기 어렵다. 서브mm 간극은 고농도 연마성 슬러리에서 못 버틴다 — **기각**"],
            ["비드밀", "비드 충격·압축",
             "취성 Si 가 무른 EVA 보다 먼저 깨지고 비드 마모분이 섞인다. 미분을 "
             "**만드는** 방법 — **기각**"],
            ["**어트리션**", f"입자-입자 마찰 ({pc.solids_volume_fraction * 100:.0f} vol% 층)",
             "각진 Si 모서리가 EVA 막을 긁는다. 접촉점 응력은 유체 전단과 차원이 다르다 — "
             "**채택 (주 가설)**. 단 미분에서의 효율 근거가 없다 → 이 시험"],
            ["열분해 450~550 °C", "EVA 분해·휘발",
             "확실하지만 로와 배가스 처리가 붙는다 — 기계식이 탈락하면 가는 **대안**"],
        ],
    ))
    add("")
    add(f"어트리션을 골라도 근거가 약하다. 체 범위의 기하평균 "
        f"{ms.representative_size_um:.0f} µm 의 t 당 표면적은 {ms.feed_surface_m2_kg:.0f} m2/kg "
        f"로, 어트리션 실적이 쌓인 실리카사({db.REFERENCE_SAND_UM:.0f} µm, "
        f"{ms.sand_surface_m2_kg:.1f} m2/kg)의 **{ms.surface_ratio_to_sand:.0f}배**다. "
        f"**그래서 시험 셀이 먼저다.**")
    add("")
    add(f"**셀 사양.** AS-1 과 기하 상사다 — 흐름 구조가 같으므로 **주속과 비에너지**를 "
        f"1차 스케일업 변수로 쓴다. 재질(금속 / 고무 라이닝)·규모·연속 혼합의 차이는 가정으로 "
        f"남아 P-6 과 AS-1 시운전(T-3)에서 확인한다.")
    add("")
    add(_table(
        ["항목", f"{pc.tag}", "AS-1 (참고)", "근거"],
        [
            ["형식", "회분식 팔각조 1기 · 뚜껑 · 재킷", f"연속 팔각조 {sc.cells}기 직렬",
             "회분 1회로 비에너지 곡선 전체 — 연속식은 체류시간 분포로 곡선이 흐려진다"],
            ["**회분**",
             f"**건조 {pc.batch_dry_kg:.0f} kg** + 물 {pc.water_kg:.2f} kg = "
             f"{pc.slurry_kg:.1f} kg ({pc.slurry_volume_m3 * 1000:.1f} L)",
             "—",
             f"채취 {pc.samples_per_batch}점 x {pc.sample_dry_kg:.2f} kg = "
             f"{pc.withdrawal_fraction * 100:.0f} % ≤ {pc.max_withdrawal * 100:.0f} % 인 최소량"],
            ["고체 농도",
             f"{pc.solids_mass_fraction * 100:.0f} wt% ({pc.solids_volume_fraction * 100:.1f} vol%)",
             f"{sc.solids_mass_fraction * 100:.0f} wt% ({sc.solids_volume_fraction * 100:.1f} vol%)",
             "같은 슬러리"],
            ["**내부 치수**",
             f"**AF {pg.across_flats_m * 1000:.0f} x 액면 {pc.fill_level_m * 1000:.0f} mm**",
             f"AF {g.across_flats_m * 1000:.0f} x {g.depth_m * 1000:.0f} mm",
             f"액면/폭 {pc.depth_to_width:.2f} (AS-1 {g.depth_m / g.across_flats_m:.2f}), "
             f"전고 {pg.shell_height_m * 1000:.0f} mm, 대각 {pg.circumscribed_diameter_m * 1000:.0f} mm"],
            ["임펠러",
             f"대향 피치 {pd.impellers_per_shaft}단 Ø{pd.diameter_m * 1000:.0f} mm, "
             f"간격 {pd.spacing_m * 1000:.0f} · 하단 간극 {pc.impeller_clearance_m * 1000:.0f} mm",
             f"Ø{dr.diameter_m * 1000:.0f} mm",
             f"폭 대비 {pd.diameter_m / pg.across_flats_m:.2f}, Np {pd.power_number:.1f} (설계 가정) — 같음"],
            ["**기준 회전수 / 주속**",
             f"**{pd.speed_rpm:,.0f} rpm / {pd.tip_speed_m_s:.2f} m/s**",
             f"{dr.speed_rpm:.0f} rpm / {dr.tip_speed_m_s:.2f} m/s", "주속을 맞춘다"],
            ["시험 주속",
             " / ".join(f"{t:.1f}" for t in tips) + " m/s "
             f"({pc.speed_rpm(low_tip):,.0f}~{top_rpm:,.0f} rpm)",
             f"VFD {dr.tip_speed_min_m_s:.1f}~{dr.tip_speed_ceiling_m_s:.2f} m/s",
             f"VFD 상한 {pd.tip_speed_ceiling_m_s:.2f} m/s — 모터가 시험 범위를 막지 않는다"],
            ["흡수동력 / 모터",
             f"{pc.power_w(base_tip):,.0f} W ({base_tip:.0f} m/s) · "
             f"{pc.power_w(top_tip):,.0f} W ({top_tip:.0f} m/s) / **{pd.motor_rating_kw:.1f} kW "
             f"{pm.poles}극 직결**",
             f"{dr.absorbed_power_w / 1000:.2f} / {dr.motor_rating_kw:.1f} kW (감속기)",
             "모터는 상한 주속에서 고르고, 직결이라 극수로 토크-속도를 맞춘다 (아래)"],
            ["체적당 동력",
             f"{pc.specific_power_kw_m3(base_tip):.1f} kW/m3 ({base_tip:.0f} m/s)",
             f"{sc.specific_power_kw_m3:.1f} kW/m3",
             "같은 주속에서 v^3/D 로 작은 셀이 크다 — **스케일업 변수가 아니다**"],
            ["**교반축**",
             f"**Ø{ps.outer_diameter_mm:.0f} mm** 중실, 길이 {ps.length_m:.2f} m",
             f"Ø{sh.outer_diameter_mm:.0f} mm, {sh.length_m:.2f} m",
             f"{ps.governed_by} 지배 — 임계 {ps.critical_speed_rpm:,.0f} rpm, "
             f"{ps.check_speed_rpm:,.0f} rpm({top_tip:.0f} m/s)에서 {ps.critical_speed_ratio:.2f}배 "
             f"(예비 질량 — 제작도로 재검산)"],
            ["**토크센서**", f"**{pc.torque_sensor_nm:.0f} N·m** 회전형 + 엔코더", "—",
             f"기동 토크 {ps.torque_nm:.1f} N·m 수용, {low_tip:.0f} m/s 운전 토크 "
             f"{pc.torque_nm(low_tip):.2f} N·m = {pc.lowest_torque_fraction * 100:.0f} % FS"],
            ["접액부", pc.wetted_material, sc.liner,
             f"**고무·우레탄 금지** — 마모분이 TGA 잔류 EVA 에 섞인다. AS-1 과 다른 점이라 "
             f"P-6 에서 따로 본다 (접액 면적/체적 {pg.wetted_area_per_volume_m:.1f} 대 "
             f"{g.wetted_area_per_volume_m:.1f} 1/m)"],
            ["바닥 시료 밸브", pc.sample_valve, "—",
             f"퍼지 한도 점당 건조 {pc.purge_budget_kg * 1000:.0f} g "
             f"(슬러리 {pc.purge_budget_l * 1000:.0f} mL) — 아래"],
            ["재킷 / TCU",
             f"전열면 {pc.jacket_area_m2:.3f} m2, U {pc.jacket_u_w_m2k:.0f} W/m2K",
             "—",
             f"{min(pc.temperatures_c):.0f} °C 를 {top_tip:.0f} m/s 에서 지키려면 냉매 "
             f"{pc.worst_coolant_supply_c:.1f} °C (TCU 하한 {pc.tcu_min_supply_c:.0f} °C) — "
             + ("OK" if pc.temperature_control_ok else "**NG**")],
            ["헤드스페이스 배기", f"{pc.vent_m3h:.0f} m3/h + H2 검지", "덮개 배기 (§2.7)",
             f"LEL {db.H2_ALARM_LEL_FRACTION * 100:.0f} % 경보, "
             f"{db.H2_DESIGN_LEL_FRACTION * 100:.0f} % 교반 정지 — 실측 전 설계 기준"],
            ["판정", "성립" if pc.is_adequate else "**NG**", "",
             "형상·잠김·축·센서·온도·주속·모터"],
        ],
    ))
    add("")
    four = direct_drive_motor(
        pm.rating_kw, 4, pm.supply_hz, pm.speeds_rpm, pm.absorbed_w, pm.start_torque_nm,
        pm.torque_sensor_nm, pm.service_factor, pm.vfd_overload, pm.max_field_weakening,
    )
    alt_hz = 50.0 if pm.supply_hz == 60.0 else 60.0
    alt = direct_drive_motor(
        pm.rating_kw, pm.poles, alt_hz, pm.speeds_rpm, pm.absorbed_w, pm.start_torque_nm,
        pm.torque_sensor_nm, pm.service_factor, pm.vfd_overload, pm.max_field_weakening,
    )
    f_lo, f_hi = pm.frequency_range_hz
    add(f"**모터 — 직결이라 극수가 정한다.** {pd.motor_rating_kw:.1f} kW 는 {top_tip:.0f} m/s "
        f"흡수동력 {pc.power_w(top_tip):,.0f} W 에 {pm.service_factor:.1f} 를 곱해 골랐다. 이 "
        f"선정은 모터가 **기저속도 이상**에서 돌 때만 맞다 — 기저속도 아래에서는 낼 수 있는 "
        f"출력이 회전수에 비례해 준다. {pc.tag} 은 토크센서를 축 사이에 넣느라 감속기 없이 "
        f"직결하므로 기저속도는 극수와 전원({pm.supply_hz:.0f} Hz)이 정한다. VFD 는 중부하 정격"
        f"(정격 토크의 {pm.vfd_overload * 100:.0f} %, 60 s)으로 하고, 토크 제한을 토크센서 정격 "
        f"아래로 걸어 굳은 슬러리 기동({pm.start_torque_nm:.1f} N·m)과 센서 보호를 함께 맡긴다.")
    add("")
    add(_table(
        ["극수", "기저속도", f"{top_rpm:,.0f} rpm 에서 낼 수 있는 출력", "흡수동력 대비",
         "VFD 토크 제한", "판정"],
        [
            [f"{four.poles}극", f"{four.base_speed_rpm:,.0f} rpm",
             f"{four.available_power_w(top_rpm) / 1000:.2f} kW", f"{four.power_margin:.2f}배",
             f"{four.torque_limit_nm:.1f} N·m", "**불가** — 출력 여유·기동 토크 모두 모자람"],
            [f"**{pm.poles}극**", f"{pm.base_speed_rpm:,.0f} rpm",
             f"{pm.available_power_w(top_rpm) / 1000:.2f} kW", f"{pm.power_margin:.2f}배",
             f"{pm.torque_limit_nm:.1f} N·m",
             f"**채택** — {f_lo:.0f}~{f_hi:.0f} Hz, 약계자 {pm.field_weakening_ratio:.2f}배"],
        ],
    ))
    add("")
    add(f"{alt_hz:.0f} Hz 현장이어도 {pm.poles}극이 성립한다 — 과부하 토크가 "
        f"{alt.vfd_overload * alt.rated_torque_nm:.1f} N·m 라 토크 제한을 센서 정격 "
        f"{alt.torque_limit_nm:.0f} N·m 로 낮춘다. 흡수동력은 동력수 {pd.power_number:.1f} "
        f"가정이다 — 실측 토크가 더 크면 이 여유가 먼저 준다 (토크-주속 곡선, 시험 계획).")
    add("")
    add("**비에너지의 정의.** 순 축동력을 **그 순간** 조 안에 남은 건조 고체로 나눠 시간 "
        "적분한다.")
    add("")
    add("```")
    add("E(t) = ∫₀ᵗ [T(τ) − T₀(ω)]·ω(τ) / M_s(τ) dτ")
    add("```")
    add("")
    add("T 는 토크센서 실측, T₀(ω) 는 빈 조(공기 중)에서 같은 회전수로 잰 베어링·씰 마찰 "
        "토크, M_s 는 시료와 퍼지로 뺀 고체를 모두 뺀 조 안 건조 고체다. 물만 넣은 토크는 "
        "빼지 않는다 — 액체 교반 손실도 AS-1 비에너지(슬러리 흡수동력 / 건조 고체)에 들어 "
        "있는 몫이다. 전력계를 쓰지 않는 것은 1 kW 급에서 모터·VFD 손실이 입력의 수십 % 라 "
        "kWh/t 가 부풀고 스케일업이 틀어지기 때문이다.")
    add("")
    add("**E = 0 은 투입 직후다.** 물을 먼저 넣고 저속으로 돌리며 투입구로 고체를 넣는다 "
        "(시간·속도를 SOP 로 고정). 투입이 끝나면 첫 시료를 뜨고 그때까지의 적분값 E₀ 를 "
        "기록한다. 그 뒤의 축 에너지는 가속·감속을 포함해 전부 E 에 든다. 적합에는 E − E₀ 를 "
        "쓰고, 첫 시료와 P-0 원료의 부착 EVA 가 TGA 반복 정밀도 밖으로 다르면(투입 중에 이미 "
        "벗겨졌으면) 원료를 기준으로 전체 E 로 다시 맞춘다.")
    add("")
    add(f"**채취 일정.** 시료를 뜰 때마다 고체가 줄어 같은 동력에서 t 당 에너지가 빨리 "
        f"오른다. 아래 경과 시간은 동력수 가정에서 나온 계획값이고, 실제로는 적분값이 "
        f"채취점에 닿을 때 뜬다. 시료를 다 떠도 상단 임펠러 위에 "
        f"{pc.minimum_submergence_m * 1000:.0f} mm ({pc.minimum_submergence_m / pd.diameter_m:.2f} D)"
        f"가 남는다 — 임펠러 **중심면**(날개 높이 가운데) 기준이다. 날개 윗끝 기준이면 날개 "
        f"투영 높이의 절반만큼 주므로, 기준 {pc.min_submergence_ratio:.1f} D "
        f"({pc.submergence_required_m * 1000:.0f} mm)와의 여유 "
        f"{(pc.minimum_submergence_m - pc.submergence_required_m) * 1000:.0f} mm 가 그 절반보다 "
        f"커야 한다 (제작도 확인).")
    add("")
    first = pc.schedule(tips[0])
    schedules = [pc.schedule(t) for t in tips]
    add(_table(
        ["누적 비에너지"] + [f"{t:.1f} m/s 경과 (min)" for t in tips]
        + ["채취 직전 고체", "액면"],
        [
            [f"{point.energy_kwh_t:g} kWh/t"]
            + [f"{sched[i].elapsed_min:.1f}" for sched in schedules]
            + [f"{point.dry_kg_before:.1f} kg", f"{point.fill_level_m * 1000:.0f} mm"]
            for i, point in enumerate(first)
        ],
    ))
    add("")
    add(f"**바닥 시료.** 조를 돌리는 채로 바닥 밸브로 뜬다. 인출 한도 "
        f"{pc.max_withdrawal * 100:.0f} % 에서 시료 몫({pc.samples_per_batch} x "
        f"{pc.sample_dry_kg:.2f} kg)을 빼면 퍼지로 버릴 수 있는 것은 점당 건조 "
        f"**{pc.purge_budget_kg * 1000:.0f} g — 슬러리 {pc.purge_budget_l * 1000:.0f} mL** 뿐이다. "
        f"일반 볼밸브는 DN50 노즐 100 mm 만으로 {nozzle_l:.2f} L 가 고여 한도의 "
        f"{nozzle_l / pc.purge_budget_l:.0f}배다. 그래서 밸브 시트가 조 바닥 면에 있는 "
        f"**플러시 바텀 밸브**로 한다. 제작 후 물·슬러리로 데드 볼륨을 실측해 퍼지량(그 이상)을 "
        f"SOP 에 적고, 퍼지로 뺀 고체도 M_s 에서 뺀다. 바닥 시료가 조 전체를 대표하는지는 "
        f"P-0B 에서 상·중·하 시료의 고체 농도로 확인한다.")
    add("")
    add("**부착 EVA 제거율.** 질량 기준으로 정의한다.")
    add("")
    add("```")
    add("X(E) = 1 − m(E) / m(E₀),   m = (가라앉은 분획 질량수율) x (그 분획의 EVA 분율, TGA)")
    add("```")
    add("")
    add("떨어진 EVA 는 뜬 분획으로 가므로 가라앉은 분획의 질량도 준다 — 분율만 비교하면 그 "
        "몫을 놓친다. TGA(N2) 질량 감소가 EVA 인지는 P-0 에서 기준 EVA 와 원료로 온도 구간을 "
        "정해 확인하고, 백시트 등 다른 유기물이 있으면 구간을 나눠 해석한다. XPS·FT-IR 은 "
        f"정성 확인용이다 — 박리율을 내지 않는다. E90 은 1 − X = exp(−k(E − E₀)) 를 원점 통과 "
        f"최소제곱(k = ΣE·y / ΣE², y = −ln(1 − X))으로 맞춰 ln 10 / k 로 구하고, "
        f"X ≥ {db.PILOT_FIT_SATURATION * 100:.0f} % 인 점(잔류가 정량 하한 부근)은 뺀다.")
    add("")
    add(f"**온도.** 교반 동력은 전부 열이 된다. 단열이면 1 kWh/t 에 "
        f"{pc.adiabatic_rise_k_per_kwh_t:.2f} K, {max(pc.energy_points_kwh_t):g} kWh/t 에서 "
        f"**{pc.adiabatic_rise_at_max_energy_k:.0f} K** 오른다 — 시험 온도 간격"
        f"({min(pc.temperatures_c):.0f}~{max(pc.temperatures_c):.0f} °C)보다 크다. 재킷 없이 "
        f"돌리면 온도 효과와 비에너지 효과를 가를 수 없다.")
    add("")
    add(f"**수소.** 회분에 Al 이 {pc.aluminium_in_batch_kg:.1f} kg 들어 있다. 배기 "
        f"{pc.vent_m3h:.0f} m3/h 는 헤드스페이스를 {design_vol_pct:.1f} vol% (LEL "
        f"{lel_pct:.0f} % 의 {db.H2_DESIGN_LEL_FRACTION * 100:.0f} %) 아래로 묶으면서 Al 반응 "
        f"{tolerable_kg_h:.2f} kg/h — 회분 Al 의 **{pc.tolerable_aluminium_reaction_per_h * 100:.0f} %/h** "
        f"까지 견딘다. 이것은 **실측 전의 설계 기준**이다. 정치 시험만으로는 어트리션이 "
        f"산화막을 벗기는 효과를 못 담으므로 첫 정규 회분 전에 두 단계로 잰다 — P-0A 는 "
        f"가스를 포집·계량할 수 있는 압력 등급 용기에서 원료 소량을 "
        f"{pc.solids_mass_fraction * 100:.0f} wt% 로 (정치·교반), P-0B 는 {pc.tag} 첫 회분을 "
        f"저속부터 올리며 H2 농도·배기 유량·토크·온도를 본다. 알칼리성 분산제는 Al 반응을 "
        f"빠르게 하므로 쓰지 않는다.")
    add("")
    add("**인터록.**")
    add("")
    add(_table(
        ["조건", "동작"],
        [
            ["배기팬 운전 확인 없음", "교반 기동 금지 · 운전 중이면 정지"],
            ["뚜껑 열림", "교반 기동 금지"],
            [f"H2 LEL {db.H2_ALARM_LEL_FRACTION * 100:.0f} %", "경보"],
            [f"H2 LEL {db.H2_DESIGN_LEL_FRACTION * 100:.0f} %", "교반 정지 — **배기는 계속**"],
            ["과속 · 고토크 · 베어링 고온 · 고진동",
             f"정지 (고토크 = VFD 토크 제한 {pm.torque_limit_nm:.1f} N·m, 센서 정격 "
             f"{pc.torque_sensor_nm:.0f} N·m 이하)"],
            ["TCU 고장 · 슬러리 온도 이탈", "경보 — 그 구간 시료는 무효"],
            ["비상정지", "정지"],
        ],
    ))
    add("")
    add("**시험 계획.**")
    add("")
    add("| 단계 | 조건 | 측정 | 산출물 |")
    add("|---|---|---|---|")
    add("| **P-0** 원료 특성 | 교반 전 (벤치) | TGA(N2) 유기물 — 기준 EVA 로 온도 구간 확인, "
        "**수중 부침 분리**(뜬 EVA = 떨어진 EVA(free) / 가라앉은 분획의 EVA = 부착), "
        "입도(−10 µm), 성분 분석(Al·Si), 입자 밀도, 초기 수분, 공정수 pH·전도도·경도 | "
        "부착 EVA 가 없으면 스크러빙은 필요 없다. 실측 비중이 설계값(2.374)과 다르면 설계 "
        "기준을 고쳐 다시 계산한다 |")
    add(f"| **P-0A** H2 벤치 | 원료 소량, {pc.solids_mass_fraction * 100:.0f} wt%, 정치·교반 | "
        f"가스 포집·계량 압력 등급 용기 — H2 발생 속도, pH, 온도, 시간 | 배기 한계(회분 Al "
        f"{pc.tolerable_aluminium_reaction_per_h * 100:.0f} %/h)와 비교 — 넘으면 배기부터 키운다 |")
    add(f"| **P-0B** 시운전 회분 | {pc.tag} 첫 회분, {low_tip:.0f} m/s 부터 단계 상승 | "
        f"빈 조 마찰 토크 T₀(ω), 인터록 작동, 배기 유량, 밸브 데드 볼륨, 상·중·하 시료 "
        f"농도, {top_tip:.0f} m/s · 최저 액면에서 표면 와류·공기 흡입, H2·토크·온도, 새 "
        f"슬러리 토크-주속 곡선 | 이상 없으면 P-1. 이 회분은 곡선에 쓰지 않는다 |")
    add(f"| **P-1** 비에너지 곡선 | {base_tip:.0f} m/s, {pc.solids_mass_fraction * 100:.0f} wt%, "
        f"{base_temp:.0f} °C | 채취 {energies} kWh/t — 부착 EVA, 뜬 EVA 양·크기, −10 µm | "
        f"1차 적합 1−X = exp(−k(E−E₀)) → **E90 = ln 10 / k** |")
    add(f"| **P-1B** 시간 대조 | 벤치, 교반 없음, {pc.solids_mass_fraction * 100:.0f} wt%, "
        f"{base_temp:.0f} °C, " + " · ".join(f"{m:.0f}" for m in run_min) + " min | "
        f"부착 EVA, −10 µm, pH, H2 | 물에 담근 시간만으로 변하는가 — P-2 의 시간 차를 가른다 |")
    add(f"| **P-2** 주속 | {low_tip:.0f} · {top_tip:.0f} m/s | P-1 과 같은 채취점 | 곡선이 E "
        f"하나로 겹치는가 — 겹치면 E 만으로 스케일업, 아니면 주속 상한 |")
    add(f"| **P-3** 온도 | {side_temps} °C | 〃 | 겨울·여름 공정수 온도 영향 |")
    add(f"| **P-4** 농도 | {low_batch.solids_mass_fraction * 100:.0f} wt% "
        f"({pc.minimum_solids_volume_fraction * 100:.0f} vol% 하한), 액면 같게 — 건조 "
        f"{low_batch.dry_kg:.1f} kg + 물 {low_batch.water_kg:.1f} kg | 〃 (인출 "
        f"{low_batch.withdrawal_fraction * 100:.0f} %, 잠김 "
        f"{low_batch.minimum_submergence_m / pd.diameter_m:.2f} D) | 로드밀 배출 농도 "
        f"요구(≥ {db.ATTRITION_MILL_DISCHARGE_MIN_SOLIDS_WT * 100:.0f} wt%) 확인 |")
    add("| **P-5** 재현성 | P-1 조건 3회 | E90 편차, 질량 수지 폐합 | 판정의 신뢰구간 |")
    add(f"| **P-6** 라이닝 민감도 (조건부) | P-1 조건에 천연고무 라이닝 판 + 우레탄 피복 "
        f"임펠러 — P-1 의 E90 이 판정선 안일 때만 | E90, −10 µm, 토크. 고무 마모분은 EVA 없는 "
        f"같은 입도 시료로 같은 운전을 해 TGA blank 로 뺀다 | 벽 재질이 박리를 바꾸는가 — "
        f"파일럿은 접액 면적/체적이 AS-1 의 {wall_ratio:.2f}배라 차이가 있으면 여기서 더 크게 "
        f"보인다 |")
    add("")
    add(f"매 회분 마지막 시료 뒤에는 주속을 {low_tip:.0f} → {base_tip:.0f} → {top_tip:.0f} m/s "
        f"로 올리며 토크-주속 곡선을 적는다 — 곡선 채취가 끝난 뒤라 E 에 영향이 없다. 실측 "
        f"동력수가 나오고, P-1 과 P-4 를 비교하면 농도에 따른 유동 특성이 보인다.")
    add("")
    add(f"**판정 기준.** 부착 EVA 제거율 **≥ {db.PILOT_EVA_REMOVAL_TARGET * 100:.0f} %** "
        f"(잠정 — 부선 급광이 받아들일 수 있는 잔류 EVA 가 정해지면 그 값으로) 이고, 그 비에너지에서 "
        f"−10 µm 증가가 **{db.ATTRITION_FINES_ACCEPTANCE_PP:.0f} %p 이하** (AS-1 T-4 와 같은 "
        f"기준) 일 것.")
    add("")
    add(f"**AS-1 로 옮기기.** 회분에서는 모든 입자가 같은 에너지를 받지만, 완전혼합조 "
        f"직렬에서는 적게 받는 입자가 생긴다. 1차 거동이면 같은 제거율에 필요한 연속 "
        f"비에너지는 회분의 {su.cells}기 기준 **{su.energy_factor:.2f}배**다 "
        f"(1기 {continuous_energy_factor(su.target_removal, 1):.2f}배, "
        f"3기 {continuous_energy_factor(su.target_removal, 3):.2f}배). 이 환산은 박리가 "
        f"비에너지에 대해 1차이고, 각 셀이 이상적 완전혼합조에 가깝고, {pc.tag} 에서 얻은 "
        f"속도상수 k 가 AS-1 에서도 유지된다는 가정 위에 선다 — P-1·P-2 적합도와 AS-1 "
        f"시운전(T-3)으로 확인한다. AS-1 이 낼 수 있는 비에너지를 이 배수로 나누면 **P-1 의 "
        f"E90 이 얼마 이하여야 하는지**가 나온다.")
    add("")
    add(_table(
        ["P-1 의 E90 (회분)", "AS-1 연속 비에너지 능력", "판정"],
        [
            [f"≤ **{su.batch_limit_peak_kwh_t:.2f} kWh/t**",
             f"{su.as1_peak_kwh_t:.2f} kWh/t ({peak_label}, VFD 상한 "
             f"{su.ceiling_tip_speed_m_s:.2f} m/s)",
             "**AS-1 그대로** — 최대 처리량에서도 목표"],
            [f"≤ {su.batch_limit_peak_upsized_kwh_t:.2f} kWh/t",
             f"{su.as1_peak_upsized_kwh_t:.2f} kWh/t ({peak_label}, "
             f"{su.practical_max_tip_speed_m_s:.1f} m/s)",
             f"모터만 {dr.motor_rating_kw:.1f} → **{su.upsized_motor_kw:.1f} kW** — 축 "
             f"Ø{sh.outer_diameter_mm:.0f} 은 {su.upsized_critical_speed_ratio:.2f}배로 "
             + ("유지" if su.upsized_shaft_ok else "**교체**")],
            [f"≤ {su.batch_limit_average_upsized_kwh_t:.2f} kWh/t",
             f"{su.as1_average_upsized_kwh_t:.2f} kWh/t ({avg_label}, "
             f"{su.practical_max_tip_speed_m_s:.1f} m/s)",
             "모터 교체 + 평균 처리량 상한 — 최대 처리량에는 셀 추가"],
            [f"> {su.batch_limit_average_upsized_kwh_t:.2f} kWh/t",
             "—", "**AS-1 로는 안 된다** — 셀 추가 또는 열분해"],
        ],
    ))
    add("")
    add(f"2·3행은 {su.practical_max_tip_speed_m_s:.0f} m/s 에서 미립 기준을 지킬 때만 "
        f"성립한다 — P-2 가 그것을 본다. {su.practical_max_tip_speed_m_s:.0f} m/s 를 쓸 수 "
        f"없으면 E90 ≤ {su.batch_limit_peak_kwh_t:.2f} 는 그대로, "
        f"**≤ {su.batch_limit_average_kwh_t:.2f} kWh/t 면 현 모터 · 평균 처리량 상한** "
        f"(VFD 상한 · {avg_label} 에서 {su.as1_average_kwh_t:.2f} kWh/t), 그 위는 셀 추가 또는 "
        f"열분해다. 1차 거동에서 벗어나면(잔차가 E 에 따라 한쪽으로 쏠리면) 환산 배수를 "
        f"곡선에서 직접 다시 계산한다.")
    add("")
    add("**확인이 필요한 가정.**")
    add("")
    add(f"- 동력수 {pd.power_number:.1f} 은 모터 예비 선정용 설계 가정이다. 실제 흡수동력과 "
        f"토크는 {pc.tag} 토크 실측으로 바꾼다.")
    add(f"- 임펠러 조립체 질량은 지름 세제곱 비례 예비값({pd.assembly_mass_kg:.1f} kg)이다. "
        f"제작도가 나오면 실측 질량, 허브, 축 단차, 커플링·토크센서, 베어링 강성·스팬, "
        f"외팔 길이, 잠긴 부가질량으로 임계회전수를 다시 검산하고, 모터-커플링-토크센서-축의 "
        f"비틀림 고유진동수가 운전 회전수({pc.speed_rpm(low_tip):,.0f}~{top_rpm:,.0f} rpm)와 "
        f"겹치지 않는지 본다.")
    add(f"- EVA 강도 {db.EVA_STRENGTH_MPA:.0f} MPa 는 벌크 강도의 보수적 하한이다. 계면 "
        f"박리강도가 아니다.")
    add(f"- 부착 EVA 제거 목표 {db.PILOT_EVA_REMOVAL_TARGET * 100:.0f} % 는 잠정값, 박리의 "
        f"1차 거동은 P-1 에서 확인한다.")
    add(f"- 재킷 총괄 열전달계수 {pc.jacket_u_w_m2k:.0f} W/m2K 는 고농도 강교반의 보수값이다.")
    add(f"- 수소 발생률은 문헌값이 없다. P-0A · P-0B 전에는 배기가 견디는 반응 속도(회분 Al 의 "
        f"{pc.tolerable_aluminium_reaction_per_h * 100:.0f} %/h)만 안다.")
    add("- 단위 테스트는 계산 구현의 일관성을 확인할 뿐이다. 동력수, 박리 속도, H2 발생률, "
        "온도·농도·라이닝 영향 같은 물리 가정은 이 시험으로 확인한다.")
    add("")
    # 2.7 수소 -------------------------------------------------------------
    al_frac = f.component_tph(1.0)["Al"]
    al_peak_kg_h = f.component_tph(f.peak_tph)["Al"] * 1000.0
    h2_example = hydrogen_from_aluminium_nm3(al_peak_kg_h * db.PLANT_AL_REACTION_EXAMPLE)
    vent_example = ventilation_for_hydrogen_m3h(
        h2_example, db.H2_LEL_VOL, db.H2_DESIGN_LEL_FRACTION
    )
    add("### 2.7 수소 — Al 이 물과 반응한다")
    add("")
    add(f"급광의 {al_frac * 100:.0f} wt% 가 후면 전극 Al 이다. 중성의 물에서 Al 은 "
        f"산화막으로 보호되지만, **어트리션은 바로 그 막을 긁어내는 장치**다. "
        f"2Al + 6H2O → 2Al(OH)3 + 3H2 로 Al 1 kg 이 H2 "
        f"{hydrogen_from_aluminium_nm3(1.0):.2f} Nm3 를 낸다. 반응 속도는 입도·온도·pH·"
        f"표면 상태에 따라 자릿수가 달라 문헌값으로 정할 수 없다 — "
        f"{pc.tag} P-0A · P-0B 에서 잰다.")
    add("")
    add(_table(
        ["항목", "값", "비고"],
        [
            ["급광 Al (최대 처리량)", f"{al_peak_kg_h:.0f} kg/h", ""],
            [f"예시 — 그 {db.PLANT_AL_REACTION_EXAMPLE * 100:.0f} % 가 반응",
             f"H2 {h2_example:.2f} Nm3/h", "**설계값이 아니다** — 규모 감 잡기용"],
            ["그때 필요한 배기", f"{vent_example:.0f} m3/h",
             f"헤드스페이스 ≤ {design_vol_pct:.1f} vol% (LEL {lel_pct:.0f} % 의 "
             f"{db.H2_DESIGN_LEL_FRACTION * 100:.0f} %)"],
        ],
    ))
    add("")
    add(f"대책: AS-1·DB-1 에 덮개를 씌우고 비스파크 팬으로 국소배기한다. 배기 덕트의 "
        f"수소 검지기가 LEL {db.H2_ALARM_LEL_FRACTION * 100:.0f} % 에서 경보, "
        f"{db.H2_DESIGN_LEL_FRACTION * 100:.0f} % 에서 AS-1 급광을 바이패스하고 플러싱을 "
        f"시작한다 — 배기는 멈추지 않는다. 배기량은 P-0A · P-0B 발생률로 확정한다. 예시 규모면 "
        f"소형 팬 한 대이므로 비용이 아니라 **빠뜨리지 않는 것**이 문제다.")
    add("")

    # 2.8 떨어진 EVA 분리 ---------------------------------------------------
    es = pre.eva
    ep, er = es.particle, es.requirement
    ro, cl = es.rougher, es.cleaner
    es_peak, es_avg = es.result_peak, es.result_avg
    es_rows = []
    for label, res in ((peak_label, es_peak), (avg_label, es_avg)):
        es_rows.append([
            label,
            f"{es.eva_recovery(res) * 100:.1f} %",
            f"{es.residual_eva_tph(res) * 1000:.2f} kg/h "
            f"({es.residual_eva_tph(res) / res.new_feed.dry_tph * 100:.3f} wt%)",
            f"{es.ag_loss(res) * 100:.3f} %",
            f"{res.concentrate.component_tph('EVA') * 1000:.2f} + "
            f"{es.product_minerals_tph(res) * 1000:.2f} kg/h",
            f"{res.rougher.residence_min:.1f} / {res.cleaner.residence_min:.1f} min",
        ])
    add(f"### 2.8 떨어진 EVA 분리 — {ro.tag} · {cl.tag}")
    add("")
    add(f"AS-1 이 입자에서 떼어 낸 EVA 는 배출 슬러리에 섞여 나간다. 비중 {db.EVA_SG:.2f} 의 "
        f"소수성 박편이라 그대로 두면 부선조에서 포수제 없이도 떠 정광으로 간다. 이 계통은 "
        f"희석박스 {dil.tag} 뒤, 조건조 CT-1 앞에서 그것을 걷어낸다. 두 안 공통 설비다.")
    add("")
    add("**역할의 경계.** 이 계통이 하는 일은 떨어진 EVA 를 흐름에서 걷어내는 것 하나다. "
        "EVA 를 입자에서 떼는 것은 AS-1, 은을 띄우는 것은 부선조가 한다. 은은 건드리지 않고 "
        "부선조로 보낸다 — 그래서 **포수제(CT-1) 앞에 두고 기포제만 쓴다.** 포수제가 없으면 "
        "Si·Al·Ag 표면은 물에 젖어 펄프에 남고, 본래 소수성인 EVA 만 기포에 붙는다. "
        "판정은 둘이다.")
    add("")
    add(f"- **부선 급광의 자유 EVA** ≤ 고체의 {db.EVA_FLOTATION_FEED_LIMIT * 100:.1f} wt% "
        f"({peak_label}에서 {er.allowance_tph * 1000:.2f} kg/h)")
    add(f"- **EVA 산물로 새는 Ag** ≤ {db.EVA_AG_LOSS_LIMIT * 100:.1f} % — 부선조(1안) 자신의 "
        f"미광 손실만큼")
    add("")
    add("```")
    add(f"{dil.tag} ({f.solids_mass_fraction * 100:.0f} wt%) → {ro.tag}A → {ro.tag}B ─미광→ "
        f"CT-1 조건조 → 부선")
    add(f"                 └거품→ {cl.tag} ─거품→ EVA 산물 → {es.bag.tag} 탈수 백 → 반출")
    add(f"                          └미광 ─┐")
    add(f"              {es.bag.tag} 여액 ──────┴→ {db.EVA_PUMP_TAG} → {ro.tag} 급광")
    add("```")
    add("")
    sc_ = es.screen
    add("**방식 선정 — 무엇으로 가르는가.**")
    add("")
    add(_table(
        ["방식", "가르는 성질", "수치", "판정"],
        [
            ["중력 부상 (스키밍조)", f"비중차 {1.0 - db.EVA_SG:.2f}",
             f"설계 박편 {ep.equivalent_diameter_um:.0f} µm 가 스스로 뜨는 속도 "
             f"{sc_.eva_rise_m_h:.3f} m/h — {sc_.flow_m3h:.2f} m3/h 를 받으려면 수면적 "
             f"**{sc_.skim_area_m2:.0f} m2**", "기각"],
            ["사이클론", "원심 침강",
             "EVA 는 물보다 가벼워 전량 월류로 가지만 분급점 아래 Si 미립도 함께 간다 — "
             "가르지 못하고 섞어 옮긴다. 탈니를 겸하게 되어 문헌 공정도 바뀐다", "기각"],
            ["체", "크기",
             f"떨어진 EVA 는 원 입자({db.PILOT_FEED_SIZE_UM[0]:.0f}~"
             f"{db.PILOT_FEED_SIZE_UM[1]:.0f} µm)의 면보다 작다", "기각"],
            ["**부선 (기포제만)**", "**표면 — 소수성**",
             f"{db.BUBBLE_D32_MM:.1f} mm 기포 상승 {sc_.bubble_rise_m_s * 100:.1f} cm/s — "
             f"박편이 스스로 뜨는 속도의 **{sc_.bubble_to_eva_ratio:,.0f}배**. 포수제가 없으면 "
             f"광물은 젖어서 남는다", "**채택**"],
        ],
    ))
    add("")
    add("**설계 EVA — 잔막 두께 하나로 정한다.** 셀 양면에 두께 t 의 EVA 잔막이 남았다고 "
        "보면 함량과 떨어진 박편의 크기가 함께 정해진다.")
    add("")
    add(_table(
        ["항목", "값", "근거"],
        [
            ["셀 한 면의 EVA 잔막", f"**{ep.film_um:g} µm**",
             "**잠정** — P-0 의 TGA(함량)와 P-1 의 뜬 EVA 크기로 바꾼다"],
            ["웨이퍼 두께", f"{ep.wafer_um:.0f} µm", "셀 면적당 Si 질량"],
            ["EVA 함량", f"**{ep.content * 100:.2f} wt%** (광물 1 t 당 {ep.content * 1000:.0f} kg)",
             "양면 잔막 질량 / 급광 질량"],
            ["떨어진 박편",
             f"두께 {ep.film_um:g} × 폭 {ep.width_um:.0f} µm → 등체적 "
             f"**{ep.equivalent_diameter_um:.1f} µm**",
             "폭은 원 입자의 면을 넘지 못한다 (시험 분획 하한 — 작을수록 보수적)"],
            [f"ES 로 오는 EVA ({peak_label})", f"{er.freed_eva_tph * 1000:.2f} kg/h",
             f"AS-1 이 목표({db.PILOT_EVA_REMOVAL_TARGET * 100:.0f} %)대로 뗀 몫"],
            ["부착 효율 Ea", f"{es.attachment_efficiency:.3f}",
             "Ag 러퍼 FC-201 의 설계 속도상수를 재현하는 값 (§8.1) — S-1 로 확인"],
            ["설계 박편의 속도상수",
             f"{es.rate_constant_1_min:.3f} 1/min (실기, Jg {db.EVA_JG_CM_S[ro.tag]:.1f} cm/s)",
             "k = 1.5·Ea·Ec·Jg/db, Ec 는 Yoon-Luttrell"],
        ],
    ))
    add("")
    margin_rows = []
    for name, c_tph, grade in (
        ("1안", rfc.performance_peak.concentrate_dry_tph, rfc.performance_peak.concentrate_grade("Ag")),
        ("2안", mech.result_peak.concentrate.dry_tph, mech.result_peak.concentrate.grade_fraction("Ag")),
    ):
        margin = grade_margin_tph(c_tph, grade, db.CONCENTRATE_GRADE_GUARANTEE)
        with_eva = concentrate_grade_with_eva(c_tph, grade, er.allowance_tph)
        margin_rows.append([
            name,
            f"{c_tph * 1000:.2f} kg/h @ {grade * 100:.1f} wt%",
            f"{margin * 1000:.2f} kg/h",
            f"{with_eva * 100:.1f} wt%",
            f"{er.allowance_tph / margin * 100:.0f} % 사용 — "
            + ("OK" if with_eva >= db.CONCENTRATE_GRADE_GUARANTEE else "**NG**"),
        ])
    add(f"**얼마나 걷어야 하나 — 부선 급광 한도에서 역산한다.** 부선 급광으로 넘어간 자유 "
        f"EVA 는 거의 전량 정광으로 간다고 본다. 한도 {db.EVA_FLOTATION_FEED_LIMIT * 100:.1f} wt% "
        f"({er.allowance_tph * 1000:.2f} kg/h)는 1안 정광 품위의 보증 여유(→ "
        f"{db.CONCENTRATE_GRADE_GUARANTEE * 100:.0f} wt%)의 약 절반이다. 나머지는 AS-1 이 남기는 "
        f"부착 EVA 몫으로 둔다. 설계 EVA {er.freed_eva_tph * 1000:.2f} kg/h 에서 요구 제거율은 "
        f"**{er.required_recovery * 100:.1f} %** 다.")
    add("")
    add(_table(
        ["안", "설계 정광", "보증까지의 여유 (EVA 환산)", "한도만큼 EVA 가 섞이면", "판정"],
        margin_rows,
    ))
    add("")
    add(f"**설계 — 2안 동체를 그대로 쓴다.** {ro.tag} 은 FC-202 스캐빈저, {cl.tag} 는 FC-203 "
        f"클리너와 동체·로터·구동부가 같다. 새로 설계할 회전체가 없다. 다른 것은 운전 조건 — "
        f"미립 EVA 를 잡으려고 급기를 Ag 셀보다 높게 두고(동반 혼입은 클리너가 맡는다), 중공축 "
        f"보어만 그 공기에 맞춰 키운다. 클리너 미광은 {db.EVA_PUMP_TAG} 로 {ro.tag} 급광에 "
        f"되돌린다 — 러퍼 거품에 동반된 광물이 부선조로 돌아가는 길이다.")
    add("")
    add(_table(
        ["항목", f"{ro.tag} EVA 러퍼", f"{cl.tag} EVA 클리너"],
        [
            ["동체", f"Ø{ro.geometry.width_m * 1000:,.0f} × {ro.geometry.shell_height_m * 1000:,.0f} mm "
             f"× {ro.cells_in_series}셀 직렬 (FC-202 와 같음)",
             f"Ø{cl.geometry.width_m * 1000:,.0f} × {cl.geometry.shell_height_m * 1000:,.0f} mm "
             f"(FC-203 과 같음)"],
            ["거품층", f"{ro.geometry.froth_depth_m * 1000:.0f} mm — 회수 위주",
             f"{cl.geometry.froth_depth_m * 1000:.0f} mm + 세척수 "
             f"{db.EVA_CLEANER_WASH_WATER_M3H:.2f} m3/h — 배수 위주"],
            ["로터", f"Ø{ro.impeller.diameter_m * 1000:.0f} mm, {ro.impeller.speed_rpm:.0f} rpm, "
             f"{ro.impeller.tip_speed_m_s:.2f} m/s",
             f"Ø{cl.impeller.diameter_m * 1000:.0f} mm, {cl.impeller.speed_rpm:.0f} rpm, "
             f"{cl.impeller.tip_speed_m_s:.2f} m/s"],
            ["모터", f"{ro.impeller.motor_rating_kw:.1f} kW × {ro.cells_in_series}",
             f"{cl.impeller.motor_rating_kw:.2f} kW"],
            ["설계 Jg / Sb", f"{ro.aeration.superficial_gas_velocity_cm_s:.2f} cm/s / "
             f"{ro.aeration.bubble_surface_area_flux_1_s:.1f} 1/s",
             f"{cl.aeration.superficial_gas_velocity_cm_s:.2f} cm/s / "
             f"{cl.aeration.bubble_surface_area_flux_1_s:.1f} 1/s"],
            ["공기 (설계 / 최대)", f"{ro.aeration.air_flow_m3h:.1f} / "
             f"{ro.aeration.air_flow_max_m3h:.1f} m3/h (셀당)",
             f"{cl.aeration.air_flow_m3h:.1f} / {cl.aeration.air_flow_max_m3h:.1f} m3/h"],
            ["중공축 보어 / 외경", f"Ø{ro.shaft.bore_mm:.0f} / Ø{ro.shaft.outer_diameter_mm:.0f} mm",
             f"Ø{cl.shaft.bore_mm:.0f} / Ø{cl.shaft.outer_diameter_mm:.0f} mm"],
            ["임계회전수비 / 처짐", f"{ro.shaft.critical_speed_ratio:.2f} / "
             f"{ro.shaft.static_deflection_mm:.2f} mm — "
             + ("OK" if ro.shaft.is_safe else "**NG**"),
             f"{cl.shaft.critical_speed_ratio:.2f} / {cl.shaft.static_deflection_mm:.2f} mm — "
             + ("OK" if cl.shaft.is_safe else "**NG**")],
            ["급광", f"{es_peak.rougher.feed_volume_m3h:.2f} m3/h ({db.EVA_PUMP_TAG} 순환 포함)",
             f"{es_peak.cleaner.feed_volume_m3h:.3f} m3/h (러퍼 거품)"],
        ],
    ))
    add("")
    add(_table(
        ["부대 설비", "사양", "비고"],
        [
            [f"{db.EVA_BLOWER_TAG} 송풍기", f"{es.blower_flow_m3h:.1f} m3/h @ "
             f"{es.blower_pressure_kpa:.0f} kPa, **{es.blower_rating_kw:.2f} kW**",
             "세 셀 최대 급기 — 펄프 수두 + 축 보어·조인트·토출구 손실에 여유 30 %"],
            [f"{db.EVA_PUMP_TAG} 순환 펌프",
             f"{es.pump_flow_m3h:.2f} m3/h, {es.pump_kw:.2f} kW",
             f"{cl.tag} 미광 + {es.bag.tag} 여액 → {ro.tag} 급광"],
            [f"{es.bag.tag} 탈수 백",
             f"{es.bag.volume_m3:.0f} m3 × {es.bag.units}기 교대",
             f"건조 EVA {es.bag.dry_capacity_kg:.0f} kg/백 — **{es.bag.change_interval_h:.0f} 시간마다 "
             f"교체** (EVA 전량이 떨어졌을 때 {es.bag.eva_tph * 1000:.1f} kg/h 기준), "
             f"케이크 함수 {es.bag.cake_moisture * 100:.0f} %"],
            ["기포제", "MIBC 물 기준 30 ppm", f"{ro.tag} 급광에서 넣는다 — 물을 따라 부선조까지 "
             f"가므로 따로 더 넣지 않는다 (§6)"],
            ["바이패스", es.bypass, "ES 정지 시 부선조는 계속 돈다 — 그동안 EVA 는 정광으로 간다"],
        ],
    ))
    add("")
    add("**성능 (설계 EVA).**")
    add("")
    add(_table(
        ["처리량", "자유 EVA 제거율", "부선 급광으로 넘어가는 EVA", "Ag → EVA 산물",
         "EVA 산물 (EVA + 광물)", "체류 (러퍼 2셀 합 / 클리너)"],
        es_rows,
    ))
    add("")
    add(f"최대 처리량에서 요구 {er.required_recovery * 100:.1f} % 에 대해 "
        f"{es.eva_recovery(es_peak) * 100:.1f} % — "
        + ("OK" if es.meets_requirement else "**NG**")
        + f". Ag 손실 {es.ag_loss(es_peak) * 100:.3f} % 는 전부 수분 동반분이다 — 한도 "
        f"{db.EVA_AG_LOSS_LIMIT * 100:.1f} % 의 "
        f"{es.ag_loss(es_peak) / db.EVA_AG_LOSS_LIMIT * 100:.0f} %"
        + (" — OK." if es.ag_loss_ok else " — **NG**.")
        + " 러퍼 거품에 동반된 광물의 대부분은 클리너 배수로 떨어져 러퍼로 돌아간다. "
        "**계산에 없는 위험**은 EVA 가 덜 떨어진 복합입자다 — 입자에 EVA 가 남아 있으면 "
        "포수제 없이도 뜰 수 있고, 그 입자에 Ag 가 붙어 있으면 EVA 산물로 샌다. 이것은 "
        "S-1 의 거품 Ag 로만 알 수 있다.")
    add("")
    size_rows = []
    for d_um, rec in es.size_recovery:
        k_plant = eva_rate_constant_1_min(
            d_um, db.EVA_JG_CM_S[ro.tag], es.attachment_efficiency, db.BUBBLE_D32_MM
        )
        size_rows.append([f"{d_um:g} µm", f"{k_plant:.3f}", f"{rec * 100:.1f} %"])
    add("**작은 EVA 가 전부를 정한다.** 충돌 효율이 (박편 지름 / 기포 지름)^2 에 비례하므로 "
        "속도상수도 거의 크기의 제곱으로 준다.")
    add("")
    add(_table(["EVA 등체적 지름", "실기 속도상수 (1/min)", f"회수율 ({peak_label})"], size_rows))
    add("")
    (d_fine, r_fine), (d_mid, r_mid) = es.size_recovery[0], es.size_recovery[1]
    add(f"{d_mid:g} µm 박편은 {r_mid * 100:.0f} %, {d_fine:g} µm 는 {r_fine * 100:.0f} % 만 "
        f"걷힌다. 떨어진 EVA 가 설계 박편보다 잘게 찢어져 "
        f"나오면 이 계통의 성능은 크기 분포가 정한다 — 그래서 PAS-1 P-1 이 뜬 EVA 의 크기를 "
        f"재고, S-2 가 크기별 회수율을 잰다. 잘게 찢어진 EVA 가 많으면 기포를 줄이는 쪽"
        f"(충돌 효율이 기포 지름의 제곱에 반비례)을 검토한다.")
    add("")
    film_rows = [
        [
            f"{fc.film_um:g} µm",
            f"{fc.content * 100:.2f} wt%",
            f"{fc.diameter_um:.1f} µm",
            f"{fc.freed_eva_tph * 1000:.2f} kg/h",
            f"{fc.required_recovery * 100:.1f} %",
            f"{fc.recovery * 100:.1f} %",
            f"{fc.residual_tph * 1000:.2f} kg/h — " + ("OK" if fc.ok else "**NG**"),
        ]
        for fc in es.film_cases
    ]
    add("**잔막 두께 민감도.** 두께가 두꺼우면 EVA 는 많아 요구 제거율이 오르지만, 떨어진 "
        "박편도 커서 잘 뜬다.")
    add("")
    add(_table(
        ["잔막", "EVA 함량", "박편 등체적", "ES 로 오는 EVA", "요구 제거율", "달성", "부선 급광으로"],
        film_rows,
    ))
    add("")
    film_ok = all(fc.ok for fc in es.film_cases)
    add(("네 경우 모두 한도 안이다 — 두 효과가 서로 상쇄한다. "
         if film_ok else "일부 두께에서 한도를 넘는다. ")
        + "**위험은 두께가 아니라 박편이 원 입자 면보다 잘게 찢어지는 경우다.**")
    add("")
    lim = es.limits
    add("**판정 — S-1 회분 t90.** S-1(회분 부선, 기포제만)에서 자유 EVA 가 90 % 뜨는 시간을 "
        "구한다 (−ln(1−R) 대 t 를 원점을 지나는 직선으로 맞춘 k 에서 t90 = ln 10 / k). 회분 "
        f"속도상수는 실기에서 {db.PLANT_SCALE_FACTOR} 배로 본다 (Ag 러퍼와 같은 스케일업).")
    add("")
    add(_table(
        ["S-1 회분 t90 (자유 EVA)", f"{ro.tag}·{cl.tag} 판정"],
        [
            [f"≤ **{lim.peak_min:.2f} min**", f"**그대로** — {peak_label}에서도 요구 "
             f"{lim.required_recovery * 100:.1f} %"],
            [f"≤ {lim.average_min:.2f} min",
             f"{avg_label}까지는 그대로 — 최대 처리량은 셀 1기 추가"],
            [f"≤ {lim.extra_cell_min:.2f} min",
             f"같은 동체 셀 1기 추가 ({ro.tag} {ro.cells_in_series + 1}셀) — 배치 공간을 비워 둔다"],
            [f"> {lim.extra_cell_min:.2f} min",
             "기포 부선으로는 비효율 — 기포를 줄이는 방식을 검토하거나 정광 품위 보증을 다시 "
             "정한다"],
        ],
    ))
    add("")
    add(f"한계는 설계 EVA 함량({ep.content * 100:.1f} wt%) 기준이다. P-0 함량이 다르면 요구 "
        f"제거율이 바뀌므로 `design_basis.EVA_RESIDUAL_FILM_UM` 을 고쳐 다시 계산한다.")
    add("")
    add("**시험 계획.**")
    add("")
    add("| 시험 | 방법 | 판정 |")
    add("|---|---|---|")
    add(f"| S-1 회분 EVA 부선 | {db.PILOT_TAG} 을 E90 에서 한 회분 더 돌린 시료, "
        f"{f.solids_mass_fraction * 100:.0f} wt%, MIBC 30 ppm, 포수제 없음. 거품을 0.5 · 1 · 2 · "
        f"4 · 8 min 에 나눠 받는다. 기포제 종류·농도, 공기량, 시간, 고체 농도, pH, 온도를 "
        f"적는다 | 판정 둘 — (1) 자유 EVA 의 t90 → 위 판정표, (2) 거품으로 간 Ag ≤ 급광 Ag 의 "
        f"{db.EVA_AG_LOSS_LIMIT * 100:.1f} % — 거품 품위가 아니라 질량 수지 "
        f"(Σ 거품 질량 x Ag 품위 / 급광 질량 x Ag 품위) |")
    add("| S-2 크기별 회수 | S-1 거품·미광의 EVA 입도 | 위 크기별 표와 비교해 Ea 를 역산한다 — "
        "박편이 설계보다 잘면 여기서 드러난다 |")
    add(f"| S-3 실기 확인 | ES 시운전, 급광·미광·EVA 산물 채취, 바이패스와 교대 | 부선 급광 "
        f"자유 EVA ≤ {db.EVA_FLOTATION_FEED_LIMIT * 100:.1f} wt%, EVA 산물 Ag |")
    add("")
    al_peak = f.component_tph(f.peak_tph)["Al"] * 1000.0
    h2_in_es = hydrogen_from_aluminium_nm3(al_peak * db.PLANT_AL_REACTION_EXAMPLE)
    add(f"**수소.** ES 셀은 거품을 긁어내야 하므로 덮개가 없다. 대신 부선 공기가 거품 위를 "
        f"쓸고 나간다. 설계 급기 {es.design_air_m3h:.1f} m3/h 가 H2 를 "
        f"{db.H2_LEL_VOL * db.H2_DESIGN_LEL_FRACTION * 100:.0f} vol% 아래로 묶는 한계는 Al "
        f"{es.tolerable_al_reaction_kg_h:.2f} kg/h 반응 — 급광 Al 의 "
        f"**{es.tolerable_al_reaction_kg_h / al_peak * 100:.2f} %/h** 다. §2.7 의 예시"
        f"(급광 Al 의 {db.PLANT_AL_REACTION_EXAMPLE * 100:.0f} %)가 전부 ES 안에서 일어나면 거품 "
        f"위 H2 는 {h2_in_es / (es.design_air_m3h + h2_in_es) * 100:.1f} vol% 로 설계 상한을 "
        f"조금 넘지만 폭발하한 {db.H2_LEL_VOL * 100:.0f} vol% 의 "
        f"{h2_in_es / (es.design_air_m3h + h2_in_es) / db.H2_LEL_VOL * 100:.0f} % 다. 셀 상부에 "
        f"H2 검지기를 두고 경보·동작점을 AS-1 덮개 배기와 같게 잡는다. 발생률은 P-0A · P-0B 에서 잰다.")
    add("")
    alt = PulpProperties(f.peak_tph, f.solids_specific_gravity, db.EVA_ALTERNATIVE_SOLIDS_WT)
    base = PulpProperties(f.peak_tph, f.solids_specific_gravity, f.solids_mass_fraction)
    solids_per_water = (
        (alt.dry_tph / alt.water_tph) / (base.dry_tph / base.water_tph)
    )
    add(f"**설치 전력 {es.installed_kw:.2f} kW** ({ro.tag} {ro.installed_kw:.1f} + {cl.tag} "
        f"{cl.installed_kw:.2f} + {db.EVA_BLOWER_TAG} {es.blower_rating_kw:.2f} + "
        f"{db.EVA_PUMP_TAG} {es.pump_kw:.2f}). 전처리 계 {pre.installed_kw:.2f} kW, 1안과 합치면 "
        f"{d.total_installed_kw(rfc):.2f} kW 로 **ES 가 계통의 "
        f"{es.installed_kw / d.total_installed_kw(rfc) * 100:.0f} %** 를 쓴다 — 부선 본체(1안 "
        f"{rfc.installed_kw:.2f} kW)보다 크다. EVA 를 떼면 걷어내는 설비가 따라온다. 전력을 줄이는 "
        f"대안은 ES 를 {db.EVA_ALTERNATIVE_SOLIDS_WT * 100:.0f} wt% 에서 돌리고 CT-1 앞에서 "
        f"부선 농도로 묽히는 것이다 — 슬러리가 {alt.volumetric_flow_m3h:.2f} m3/h 로 "
        f"{base.volumetric_flow_m3h:.2f} m3/h 의 {alt.volumetric_flow_m3h / base.volumetric_flow_m3h * 100:.0f} %"
        f" 가 되어 셀이 작아진다. 대신 같은 거품 물에 실려 가는 광물이 "
        f"{solids_per_water:.1f}배가 되므로, S-1 에서 두 농도의 Ag 손실을 비교한 뒤에만 택한다.")
    add("")
    add(f"물: 세척수 {db.EVA_CLEANER_WASH_WATER_M3H:.2f} m3/h 는 공정수에서 받고, EVA 케이크에 "
        f"남아 나가는 물 {es.bag.cake_water_tph:.3f} m3/h 만큼 신수 보충이 는다. ES 가 부선 "
        f"급광에서 빼는 물은 EVA 산물의 {es_peak.concentrate.water_tph:.3f} m3/h "
        f"({es_peak.concentrate.water_tph / es_peak.new_feed.water_tph * 100:.1f} %)라 부선 "
        f"계산은 급광 {f.solids_mass_fraction * 100:.0f} wt% 그대로 둔다.")
    add("")

    # 3. 1안 --------------------------------------------------------------
    add("## 3. 1안 (주설계) — 세척수 bias 연속 부선조 1단")
    add("")
    rd = rfc.design
    add(_table(
        ["항목", "값", "비고"],
        [
            ["기기 번호 / 역할", f"{rd.tag} / {rd.duty}", ""],
            ["**동체 내경**", f"**{rd.diameter_m * 1000:.0f} mm**",
             f"단면적 {rd.area_m2:.4f} m2"],
            ["라이저 높이", f"{rd.riser_height_m:.2f} m",
             f"기액 체류시간 {rd.gas_liquid_residence_min:.0f} min 유지"],
            ["라이저 체적", f"{rd.riser_volume_m3:.3f} m3", ""],
            ["급광 flux Jf", f"{rd.feed_flux_cm_s:.2f} cm/s", "[2] 실증값 유지"],
            ["기체 flux Jg", f"{rd.air_flux_cm_s:.2f} cm/s", "[2] 실증값 유지"],
            ["세척수 flux Jw", f"{rd.wash_water_flux_cm_s:.2f} cm/s", "[2] 실증값 유지"],
            ["bias flux Jb", f"{rd.bias_flux_cm_s:.2f} cm/s",
             "양수 = 거품층 하향 순유량. 동반 맥석을 씻어내린다"],
            ["경사판", f"{rd.inclined_channel_angle_deg:.0f}° / 간격 "
             f"{rd.inclined_channel_spacing_mm:.0f} mm", "미광부 침강 강화"],
            ["기포 크기", f"{trial.bubble_size_mm[0]:.1f}~{trial.bubble_size_mm[1]:.1f} mm", "[2]"],
            ["송풍기", f"{rd.blower_rating_kw:.2f} kW, "
             f"{rd.air_m3h:.1f} m3/h @ {rd.blower_pressure_kpa:.0f} kPa", ""],
        ],
    ))
    add("")
    add("스케일업은 **flux 상사**로 한다. 실증에서 확인된 급광·기체·세척수 flux 를 그대로 두고 "
        "단면적만 처리량에 비례해 키우면 기액 체류시간과 bias 조건이 보존된다. "
        "체적을 키우는 것이 아니라 단면적을 키우는 것이 핵심이다.")
    add("")
    add(_table(
            ["운전점", "고체 농도", "급광 flux", "기액 체류", "급광", "공기", "세척수", "월류수", "농도 여유"],
        [
            [
                label,
                f"{op.solids_wt * 100:.0f} wt%",
                f"{op.feed_flux_cm_s:.2f} cm/s",
                f"{op.gas_liquid_residence_min:.2f} min",
                f"{op.feed_m3h:.2f} m3/h",
                f"{op.air_m3h:.2f} m3/h",
                f"{op.wash_water_m3h:.2f} m3/h",
                f"{op.overflow_water_m3h:.2f} m3/h",
                f"{(rd.design_solids_wt - op.solids_wt) * 100:.1f} %p"
                if op.within_capacity else "**초과**",
            ]
            for label, op in ((avg_label, rfc.point_avg), (peak_label, rfc.point_peak))
        ],
    ))
    add("")
    add(f"평균 처리량에서는 슬러리·공기·세척수 flux 를 실증값에 유지하고 급광 고체 농도를 "
        f"낮춰 1분 체류시간을 보존한다. 세 flux를 함께 낮추면 체류시간이 늘어나므로 같은 "
        f"성능으로 간주하지 않는다. 고체 농도를 올리면 같은 동체로 더 큰 처리량이 나오지만 — "
        f"{f.solids_mass_fraction * 100:.0f} wt% 에서 {rd.capacity_tph:.2f} t/h, "
        f"15 wt% 에서 {rd.capacity_at_solids(0.15):.2f} t/h, "
        f"{trial.max_feasible_solids_wt_percent:.0f} wt% 에서 "
        f"{rd.capacity_at_solids(trial.max_feasible_solids_wt_percent / 100):.2f} t/h. "
        f"다만 고농도 운전은 PV 원료로 미검증이므로 설계는 검증값에 둔다.")
    add("")
    for label, perf in ((peak_label, rfc.performance_peak), (avg_label, rfc.performance_avg)):
        add(f"### 물질수지 — {label}")
        add("")
        add(_table(
            ["성분", "급광 (kg/h)", "정광 (kg/h)", "미광 (kg/h)", "회수율 (%)",
             "정광 품위 (%)", "미광 품위 (g/t)"],
            [
                [
                    name,
                    _kgh(perf.feed_tph[name]),
                    _kgh(perf.concentrate_tph[name], 3),
                    _kgh(perf.tailings_tph[name]),
                    _pct(perf.recovery(name), 2),
                    f"{perf.concentrate_grade(name) * 100:.2f}",
                    f"{perf.tailings_grade(name) * 1e6:,.0f}",
                ]
                for name in perf.feed_tph
            ]
            + [[
                "**합계**", f"**{_kgh(perf.feed_dry_tph, 1)}**",
                f"**{_kgh(perf.concentrate_dry_tph, 2)}**",
                f"**{_kgh(perf.tailings_dry_tph, 1)}**",
                f"**{_pct(perf.mass_yield, 2)}** (질량수율)", "**100.00**", "—",
            ]],
        ))
        add("")
        add(_table(
            ["지표", "값"],
            [
                ["**Ag 회수율**", f"**{_pct(perf.recovery('Ag'), 1)} %**"],
                ["**Ag 정광 품위**", f"**{perf.concentrate_grade('Ag') * 100:.1f} wt%**"],
                ["Ag 농축비", f"{perf.upgrade('Ag'):.1f} 배"],
                ["Ag 미광 손실", f"{_kgh(perf.tailings_tph['Ag'], 3)} kg/h "
                 f"({perf.tailings_grade('Ag') * 1e6:.0f} g/t)"],
                ["정광량", f"{_kgh(perf.concentrate_dry_tph, 2)} kg/h "
                 f"(급광의 {_pct(perf.mass_yield, 2)} %)"],
                ["후단 침출 물량 감소", f"{1 / perf.mass_yield:.0f} 배"],
                ["물질수지 폐합 오차", f"{perf.mass_balance_error_tph() * 1e6:.1e} g/h"],
            ],
        ))
        add("")

    add("### 부대 설비")
    add("")
    add(_table(
        ["기기", "역할", "사양"],
        [
            [c.tag, c.duty,
             f"유효 {c.working_volume_m3:.3f} m3 / 탱크 {c.tank_volume_m3:.2f} m3, "
             f"Ø{c.diameter_m * 1000:.0f} x {c.height_m * 1000:.0f} mm, 교반 {c.agitator_kw:.2f} kW"]
            for c in rfc.conditioners
        ]
        + [
            [t.tag, t.duty,
             f"월류 {t.overflow_m3h:.2f} m3/h, 상승속도 {t.rise_rate_m_h:.1f} m/h, "
             f"Ø{t.diameter_m:.1f} m"]
            for t in (rfc.tailings_thickener, rfc.concentrate_thickener)
        ]
        + [
            ["P-101", "급광 펌프", "1.5 kW"],
            ["P-102", "미광 펌프", "0.75 kW"],
        ]
        + [_filter_row(f) for f in (rfc.concentrate_filter, rfc.tailings_filter)],
    ))
    add("")
    add(_filter_table([rfc.concentrate_filter, rfc.tailings_filter]))
    add("")
    add(f"**설치 전력 {rfc.installed_kw:.2f} kW**, 공정수 회수 {rfc.water_recycle_m3h:.2f} m3/h. "
        f"농축조 월류 블리드 {rfc.bleed_m3h:.2f} m3/h와 케이크 잔류수를 합한 "
        f"신수 보충량은 **{rfc.fresh_makeup_m3h:.2f} m3/h** 다.")
    add("")
    add(f"이 가운데 필터프레스 여액 {rfc.filtrate_m3h:.3f} m3/h 는 공정수 탱크가 아니라 "
        f"**{rfc.filtrate_return_to}** 으로 되돌린다. 여포를 빠져나온 미립자가 남아 있어 "
        f"공정수로 희석하면 그 안의 Ag 를 그대로 잃기 때문이다.")
    add("")

    # 4. 2안 --------------------------------------------------------------
    add("## 4. 2안 (대안) — 기계식 러퍼 · 스캐빈저 · 클리너 3단")
    add("")
    add("기존 부선 설비를 그대로 쓰거나 범용 장비로 구성해야 할 때의 대안이다. "
        "러퍼 정광은 클리너로, 러퍼 미광은 스캐빈저로 간다. 스캐빈저 정광과 "
        "클리너 미광은 러퍼 급광으로 되돌린다. "
        "급기는 **중공축**으로 넣어 로터가 직접 분산시킨다 (별도 스파저 없음).")
    add("")
    add(_table(
        ["항목"] + [f"{c.tag} ({c.cells_in_series}기)" for c in mech.cells],
        [
            ["역할"] + [c.duty for c in mech.cells],
            ["셀당 내부 치수 (mm)"]
            + [f"Ø{c.geometry.diameter_m * 1000:.0f} x "
               f"{c.geometry.shell_height_m * 1000:.0f}(H)" for c in mech.cells],
            ["거품층 (mm)"] + [f"{c.geometry.froth_depth_m * 1000:.0f}" for c in mech.cells],
            ["셀당 유효 슬러리 체적 (m3)"]
            + [f"{c.geometry.effective_slurry_volume_m3:.3f}" for c in mech.cells],
            ["로터 지름 (mm)"] + [f"{c.impeller.diameter_m * 1000:.0f}" for c in mech.cells],
            ["회전수 (rpm)"] + [f"{c.impeller.speed_rpm:.0f}" for c in mech.cells],
            ["주속 (m/s)"] + [f"{c.impeller.tip_speed_m_s:.2f}" for c in mech.cells],
            ["셀당 모터 (kW)"] + [f"{c.impeller.motor_rating_kw:.2f}" for c in mech.cells],
            ["설계 Jg (cm/s)"]
            + [f"{c.aeration.superficial_gas_velocity_cm_s:.2f}" for c in mech.cells],
            ["셀당 급기량 (m3/h)"] + [f"{c.aeration.air_flow_m3h:.1f}" for c in mech.cells],
            ["체류시간 (min, 최대유량)"]
            + [f"{u.residence_min:.2f}" for u in (
                mech.result_peak.rougher, mech.result_peak.scavenger, mech.result_peak.cleaner)],
            ["**중공축 보어 (mm)**"] + [f"**Ø{c.shaft.bore_mm:.0f}**" for c in mech.cells],
            ["중공축 외경 (mm)"] + [f"Ø{c.shaft.outer_diameter_mm:.0f}" for c in mech.cells],
            ["축 길이 (m)"] + [f"{c.shaft.length_m:.2f}" for c in mech.cells],
            ["축 내부 공기 유속 (m/s)"] + [f"{c.shaft.air_velocity_m_s:.1f}" for c in mech.cells],
            ["전달 토크 (N·m)"] + [f"{c.shaft.torque_nm:.0f}" for c in mech.cells],
            ["비틀림 전단응력 (MPa)"]
            + [f"{c.shaft.shear_stress_mpa:.1f} / {c.shaft.allowable_shear_mpa:.0f}"
               for c in mech.cells],
            ["외경 결정 기준"] + [c.shaft.governed_by for c in mech.cells],
            ["급기 압력손실 (kPa)"]
            + [f"{c.shaft.total_pressure_drop_kpa:.1f}" for c in mech.cells],
            ["분산구"] + [
                f"{c.shaft.discharge_ports} x Ø{c.shaft.discharge_port_diameter_mm:.0f} mm"
                for c in mech.cells
            ],
            ["1차 임계회전수 / 운전비"] + [
                f"{c.shaft.critical_speed_rpm:.0f} rpm / {c.shaft.critical_speed_ratio:.2f}x"
                for c in mech.cells
            ],
            ["예비 정적 처짐 (mm)"]
            + [f"{c.shaft.static_deflection_mm:.2f}" for c in mech.cells],
        ],
    ))
    add("")
    add("**러퍼·스캐빈저 표준화.** 첨부 문헌에는 스캐빈저 단독 시험이나 "
        "8분 체류시간의 근거가 없으므로, FC-202를 임의로 대형화하지 않고 "
        "FC-201과 같은 동체·로터·구동부로 통일했다. FC-202는 거품층을 더 얕게 "
        "운전하므로 같은 동체에서도 유효 체적과 실제 체류시간이 조금 더 크다. "
        "locked-cycle 시험에서 추가 체류시간의 유효성이 확인될 때만 예비 공간에 "
        "2차 스캐빈저를 직렬 증설한다.")
    add("")
    add("**중공축 급기.** 축 상단 로터리 조인트로 공기를 넣어 축 내부 보어를 지나 "
        f"로터 허브의 분산구 {mech.cells[0].shaft.discharge_ports}개로 내보낸다. "
        "로터가 직접 기포를 부수므로 스파저 방식보다 기포가 잘고 균일하다. "
        "축 외경은 단순 L/D가 아니라 로터 집중질량을 포함한 외팔보 예비 모델로 "
        "1차 임계회전수와 정적 처짐을 검산했다. 실제 제작 전에는 확정 베어링 스팬·"
        "불평형 하중으로 로터동역학을 다시 확인해야 한다. 송풍기 압력은 펄프 수두에 "
        "축 보어·로터리 조인트·허브 분산구 손실을 더해 선정했다.")
    add("")
    add(f"송풍기 공용 1대 {mech.blower_rating_kw:.2f} kW "
        f"({mech.blower_flow_m3h:.0f} m3/h @ {mech.blower_pressure_kpa:.0f} kPa), "
        f"미광/정광 농축조 {mech.tailings_thickener.tag}/{mech.concentrate_thickener.tag} "
        f"Ø{mech.tailings_thickener.diameter_m:.1f}/{mech.concentrate_thickener.diameter_m:.1f} m. "
        f"**설치 전력 {mech.installed_kw:.2f} kW.**")
    add("")
    add("### 탈수 라인")
    add("")
    add(_filter_table([mech.concentrate_filter, mech.tailings_filter]))
    add("")
    add(f"여액 {mech.filtrate_m3h:.3f} m3/h 는 공정수 탱크를 거치지 않고 "
        f"**{mech.filtrate_return_to}** 으로 직접 되돌린다 — 여포를 빠져나온 미립자에 "
        f"Ag 가 남아 있어 회로 첫 단에서 한 번 더 부선 기회를 준다. "
        f"두 농축조 월류수와 합친 공정수 회수량은 {mech.water_recycle_m3h:.2f} m3/h, "
        f"블리드 {mech.bleed_m3h:.2f} m3/h와 케이크 잔류수를 보충하는 신수는 "
        f"**{mech.fresh_makeup_m3h:.2f} m3/h** 다.")
    add("")
    for label, res in ((peak_label, mech.result_peak), (avg_label, mech.result_avg)):
        add(f"### 물질수지 — {label}")
        add("")
        add(_table(
            ["단", "체류시간 (min)", "급광 (kg/h)", "정광 (kg/h)", "mass pull", "Ag 회수율"],
            [
                [u.unit.tag, f"{u.residence_min:.2f}", _kgh(u.feed.dry_tph, 1),
                 _kgh(u.concentrate.dry_tph, 2), f"{_pct(u.mass_pull, 2)} %",
                 f"{_pct(u.recovery('Ag'))} %"]
                for u in (res.rougher, res.scavenger, res.cleaner)
            ],
        ))
        add("")
        add(_table(
            ["지표", "값"],
            [
                ["**Ag 회로 회수율**", f"**{_pct(res.recovery('Ag'))} %**"],
                ["**Ag 정광 품위**", f"**{res.concentrate.grade_fraction('Ag') * 100:.1f} wt%**"],
                ["Ag 농축비", f"{res.enrichment_ratio('Ag'):.1f} 배"],
                ["Ag 미광 손실", f"{_kgh(res.tailings.component_tph('Ag'), 3)} kg/h "
                 f"({res.tailings.grade_fraction('Ag') * 1e6:.0f} g/t)"],
                ["정광량", f"{_kgh(res.concentrate.dry_tph, 2)} kg/h ({_pct(res.mass_pull, 2)} %)"],
                ["순환부하", f"{_pct(res.circulating_load, 1)} %"],
                ["회로 희석·세척수 요구량 (여액 제외)",
                 f"{res.fresh_water_m3h:.2f} m3/h"],
                ["필터 여액 러퍼 직송", f"{res.filtrate_return_m3h:.3f} m3/h"],
                ["물질수지 폐합 오차", f"{res.mass_balance_error_tph() * 1e6:.1e} g/h"],
            ],
        ))
        add("")
    add("#### 확정 치수 검증")
    add("")
    add(_table(
        ["셀", "목표 체류시간", "필요 유효 체적", "확정 유효 체적", "실제 체류시간", "판정"],
        [
            [
                tag, f"{target:.1f} min",
                f"{mechanical_sizing_check(mech.result_peak, tag, target):.3f} m3",
                f"{mech.cell(tag).geometry.effective_slurry_volume_m3 * mech.cell(tag).cells_in_series:.3f} m3",
                f"{res.residence_min:.2f} min",
                "OK" if mech.cell(tag).geometry.effective_slurry_volume_m3
                * mech.cell(tag).cells_in_series
                >= mechanical_sizing_check(mech.result_peak, tag, target) * 0.98 else "**NG**",
            ]
            for tag, target, res in (
                ("FC-201", db.MECHANICAL_RESIDENCE_MIN["FC-201"], mech.result_peak.rougher),
                ("FC-202", db.MECHANICAL_RESIDENCE_MIN["FC-202"], mech.result_peak.scavenger),
                ("FC-203", db.MECHANICAL_RESIDENCE_MIN["FC-203"], mech.result_peak.cleaner),
            )
        ],
    ))
    add("")
    rougher, _, cleaner = mech.units
    without_scavenger = solve_circuit(
        f.component_tph(f.peak_tph),
        db.FLOAT_MODELS,
        db.SPECIFIC_GRAVITY,
        rougher,
        None,
        cleaner,
        rougher_feed_solids=f.solids_mass_fraction,
        composite_carry_ratio=0.0,
    )
    add("**스캐빈저 효과.** 같은 러퍼·클리너 회로에서 스캐빈저만 빼면 Ag 회수율은 "
        f"{without_scavenger.recovery('Ag') * 100:.1f} %이고, 3단 폐회로는 "
        f"{mech.result_peak.recovery('Ag') * 100:.1f} %다 "
        f"(+{(mech.result_peak.recovery('Ag') - without_scavenger.recovery('Ag')) * 100:.1f} %p). "
        f"미광 Ag도 {without_scavenger.tailings.grade_fraction('Ag') * 1e6:.0f} → "
        f"{mech.result_peak.tailings.grade_fraction('Ag') * 1e6:.0f} g/t로 낮아진다. "
        "스캐빈저 포수제 추가량은 실증 근거가 없어 기본계산에는 증량을 적용하지 않았다.")
    add("")

    # 5. 비교 -------------------------------------------------------------
    add("## 5. 두 안 비교")
    add("")
    rp, mp = rfc.performance_peak, mech.result_peak
    add(_table(
        ["지표", "1안 연속 부선조", "2안 기계식 3단", "판정"],
        [
            ["Ag 회수율", f"**{_pct(rp.recovery('Ag'))} %**", f"{_pct(mp.recovery('Ag'))} %",
             f"1안 {(rp.recovery('Ag') - mp.recovery('Ag')) * 100:+.1f} %p"],
            ["Ag 정광 품위", f"{rp.concentrate_grade('Ag') * 100:.1f} wt%",
             f"{mp.concentrate.grade_fraction('Ag') * 100:.1f} wt%", "동등 (복합입자 상한)"],
            ["Ag 미광 손실", f"{perf_tail(rp):.0f} g/t",
             f"{mp.tailings.grade_fraction('Ag') * 1e6:.0f} g/t", "1안 압도적"],
            ["부선기 대수", "1기", f"{sum(c.cells_in_series for c in mech.cells)}기", "1안"],
            ["설치 전력 (부선 계통)", f"**{rfc.installed_kw:.2f} kW**", f"{mech.installed_kw:.2f} kW",
             f"1안 {(1 - rfc.installed_kw / mech.installed_kw) * 100:.0f} % 절감"],
            ["설치 전력 (공용 전처리 포함)",
             f"**{d.total_installed_kw(rfc):.2f} kW**",
             f"{d.total_installed_kw(mech):.2f} kW",
             f"전처리 {pre.installed_kw:.2f} kW 는 두 안 공통 (§2)"],
            ["부선기 설치 면적", f"Ø{rd.diameter_m * 1000:.0f} mm x {rd.riser_height_m + 1.2:.1f} m(H)",
             f"{mech.cells[0].geometry.width_m * 2.2:.1f} x "
             f"{mech.cells[0].geometry.width_m * 1.3:.1f} m", "1안"],
            ["체류시간", f"{rd.gas_liquid_residence_min:.0f} min (기액)",
             f"{mp.rougher.residence_min:.1f} + {mp.scavenger.residence_min:.1f} + "
             f"{mp.cleaner.residence_min:.1f} min", "1안"],
            ["순환류", "없음", f"{_pct(mp.circulating_load, 1)} % "
             "(스캐빈저 정광 + 클리너 미광)", "1안"],
            ["기술 성숙도", "TRL 5 (연속 실증 90 min)", "범용 장비, 회분식만 실증", "2안이 조달 유리"],
            ["지식재산", "가출원 대상 — 실시권 검토 필요", "제약 없음", "2안이 유리"],
        ],
    ))
    add("")
    add("**권고 — 1안.** 회수율이 "
        f"{(rp.recovery('Ag') - mp.recovery('Ag')) * 100:.1f} %p 높고 전력은 "
        f"{(1 - rfc.installed_kw / mech.installed_kw) * 100:.0f} % 낮으며 장치가 1기다. "
        "정광 품위는 두 안이 같은데, 이는 품위가 장치가 아니라 복합입자 동반이라는 "
        "**원료 자체의 성질**로 결정되기 때문이다. 다만 1안은 특정 장치 형식에 의존하고 "
        "특허 가출원 대상이므로, 조달·실시권 리스크가 크다면 2안이 현실적 차선이다.")
    add("")

    # 6. 약제 -------------------------------------------------------------
    add("## 6. 약제 계통")
    add("")
    add("**pH 조정제·황화제·억제제를 쓰지 않는다.** 디티오포스핀산계 포수제가 금속 Ag 표면에 "
        "직접 선택 흡착하기 때문이다 ([1] ToF-SIMS: Ag 위 신호가 주변 대비 약 100배). "
        "이전 설계의 소다회·Na2S·규산소다 계통이 통째로 사라지면서 H2S 위험과 "
        "pH·ORP 제어 루프도 함께 없어진다.")
    add("")
    for tph, water, label in (
        (f.average_tph, rfc.point_avg.water_tph, avg_label),
        (f.peak_tph, rfc.point_peak.water_tph, peak_label),
    ):
        add(f"### {label} (1안 기준, 물 {water:.2f} m3/h)")
        add("")
        add(_table(
            ["약제", "역할", "투입량", "환산 (g/t)", "유효성분 (kg/h)", "조제농도",
             "펌프 유량 (L/h)", "펌프 선정 (L/h)", "투입 지점"],
            [
                [
                    dose.reagent.name, dose.reagent.role,
                    f"{dose.reagent.dose:.0f} {dose.reagent.dose_unit}",
                    f"{dose.equivalent_g_per_t:.0f}",
                    f"{dose.active_kg_h:.3f}",
                    f"{dose.reagent.solution_strength * 100:.0f}%"
                    if dose.reagent.solution_strength < 1 else "원액",
                    f"{dose.solution_l_h:.2f}", f"{dose.pump_rating_l_h():.1f}",
                    dose.reagent.addition_point,
                ]
                for dose in reagent_schedule(db.REAGENTS, tph, water)
            ],
        ))
        add("")
    add("**관리 포인트**")
    add("")
    for r in db.REAGENTS:
        if r.note:
            add(f"- **{r.name}** — {r.note}")
    add("")

    # 7. 모델 검증 ---------------------------------------------------------
    add("## 7. 모델 검증 — 문헌 재현")
    add("")
    ag = db.FLOAT_MODELS["Ag"]
    rows = []
    for t_min, published in ref.BATCH_KINETIC_POINTS:
        model = ag.batch_flotation_recovery(t_min)
        rows.append([f"[1] 회분식 Ag 회수율 @ {t_min:.0f} min", f"{published * 100:.1f} %",
                     f"{model * 100:.1f} %", _delta(model, published)])
    rows.append(["[1] 회분식 Ag 극한 회수율",
                 f"{batch.ag_recovery_percent:.1f} %", f"{ag.r_max * 100:.1f} %",
                 _delta(ag.r_max, batch.ag_recovery_percent / 100)])
    for metal, data in ref.BATCH_BASE_METALS.items():
        model = db.FLOAT_MODELS[metal].batch_flotation_recovery(batch.flotation_time_min)
        rows.append([f"[1] 회분식 {metal} 회수율 @ 3 min", f"{data['recovery_percent']:.1f} %",
                     f"{model * 100:.1f} %", _delta(model, data["recovery_percent"] / 100)])
    rows.append(["[2] 연속 Ag 회수율", f"{trial.ag_recovery_percent:.1f} %",
                 f"{rp.recovery('Ag') * 100:.1f} %",
                 _delta(rp.recovery("Ag"), trial.ag_recovery_percent / 100)])
    rows.append(["[2] 연속 질량수율", f"{trial.solids_yield_percent:.2f} %",
                 f"{rp.mass_yield * 100:.2f} %",
                 _delta(rp.mass_yield, trial.solids_yield_percent / 100)])
    rows.append(["[2] 연속 정광 Ag 품위", f"{trial.concentrate_ag_wt_percent:.1f} wt%",
                 f"{rp.concentrate_grade('Ag') * 100:.1f} wt%",
                 _delta(rp.concentrate_grade("Ag"), trial.concentrate_ag_wt_percent / 100)])
    rows.append(["[1] 러퍼+클리너 정광 Ag 품위",
                 f"{ref.BATCH_ROUGHER_CLEANER['concentrate_ag_wt_percent']:.1f} wt%",
                 f"{mp.concentrate.grade_fraction('Ag') * 100:.1f} wt%",
                 _delta(mp.concentrate.grade_fraction("Ag"),
                        ref.BATCH_ROUGHER_CLEANER["concentrate_ag_wt_percent"] / 100)])
    add(_table(["항목", "문헌값", "모델값", "차이"], rows))
    add("")
    add("연속 부선조는 **반응속도 모델을 쓰지 않는다.** 완전혼합조가 아니라 스파저·유동층·"
        "경사판·세척수 bias 로 구성된 흐름 장치라, 기액 체류시간 1분을 CSTR 식에 대입하면 "
        f"Ag 회수율이 {perfect_mixer_recovery(ag.k_fast, 1.0) * ag.fast_fraction * 100 + perfect_mixer_recovery(ag.k_slow, 1.0) * ag.slow_fraction * 100:.0f} % 로 "
        "나와 실측(~100 %)과 전혀 맞지 않는다. flux 상사로 스케일업하면 수력학적 조건이 "
        "보존되므로 실증 측정값을 그대로 이월하는 것이 옳다.")
    add("")

    # 8. 수치해석 ----------------------------------------------------------
    add("## 8. 수치해석 — 수력학 검산과 기동 과도응답")
    add("")
    add("### 8.1 기포-입자 수력학 검산")
    add("")
    add("설계가 쓰는 속도상수는 문헌 회분식 곡선에 맞춘 경험값이다. 제1원리로 "
        "그 값이 물리적으로 성립하는지 검산한다 — 기포 종말속도(Schiller-Naumann "
        "항력 반복해) → 기포 Reynolds 수 → Yoon-Luttrell 충돌 효율 Ec → 포집 "
        "속도상수 k = (3/2)·Ea·Ec·Jg/db. 여기서 부착 효율 Ea 만 미지수이므로, "
        "속부선 분획의 설계 속도상수 "
        f"(회분식 {db.FLOAT_MODELS['Ag'].k_fast:.2f} × 스케일업 계수 {db.PLANT_SCALE_FACTOR} "
        f"= {db.FLOAT_MODELS['Ag'].k_fast * db.PLANT_SCALE_FACTOR:.2f} 1/min) 를 재현하는 "
        "Ea 를 역산한다.")
    add("")
    k_fast_plant = db.FLOAT_MODELS["Ag"].k_fast * db.PLANT_SCALE_FACTOR
    hydro_rows = []
    hydro = []
    for c in mech.cells:
        h = analyse_cell(
            c.tag,
            c.aeration.superficial_gas_velocity_cm_s,
            c.aeration.bubble_sauter_mean_mm,
            c.geometry.gas_holdup,
            c.geometry.pulp_zone_height_m,
            k_fast_plant,
        )
        hydro.append(h)
        hydro_rows.append([
            c.tag,
            f"{h.bubble_rise_m_s * 100:.1f} / {h.bubble_swarm_m_s * 100:.1f}",
            f"{h.bubble_reynolds:.0f}",
            f"{h.collision_efficiency * 100:.2f} %",
            f"{h.ideal_rate_constant_1_min:.1f}",
            f"{h.measured_rate_constant_1_min:.2f}",
            f"**{h.implied_attachment_efficiency:.3f}**",
            f"{h.pulp_transit_s:.0f} s",
        ])
    add(_table(
        ["셀", "기포 상승 단일/군 (cm/s)", "Re", "충돌 효율 Ec",
         "k 이상값 (1/min)", "k 설계값 (1/min)", "역산 Ea", "펄프 통과"],
        hydro_rows,
    ))
    add("")
    add(f"역산된 부착 효율 Ea {min(h.implied_attachment_efficiency for h in hydro):.2f}~"
        f"{max(h.implied_attachment_efficiency for h in hydro):.2f} 는 수십 µm 급 입자의 "
        "문헌 범위(0.1~0.3)에 들어간다 — **설계 속도상수는 물리적으로 정합적이다.** "
        "입자 침강속도는 "
        f"{hydro[0].particle_settling_mm_s:.1f} mm/s (P80 66 µm) 로 순환 유속 "
        "수십 cm/s 대비 무시할 만해, 셀 바닥 모래화(sanding) 위험은 낮다.")
    add("")
    add("### 8.2 기동 과도응답")
    add("")
    tr = simulate_startup(mech.result_peak, duration_min=120.0)
    ss = mech.result_peak
    add("빈 셀에서 급광을 넣기 시작한 순간부터 회로가 정상상태에 도달할 때까지를 "
        "성분별 셀 재고에 대한 CSTR 연립 ODE 로 적분했다 (RK4, Δt 0.02 min). "
        "유효 속도상수는 정상상태 해에서 역산했으므로, 적분이 수렴하면 정상상태 "
        "물질수지와 **정확히 같은 값**에 도달해야 한다 — 이것이 곧 두 계산의 "
        "교차 검증이다.")
    add("")
    add(_table(
        ["지표", "값"],
        [
            ["회수율 95 % 도달 (t95)", f"**{tr.time_to_95pct_min:.1f} min**"],
            ["회수율 99 % 도달 (t99)", f"{tr.time_to_99pct_min:.1f} min"],
            ["120 min 시점 Ag 회수율 (ODE)", f"{tr.final_recovery_ag * 100:.2f} %"],
            ["정상상태 해 (수렴 계산)", f"{ss.recovery('Ag') * 100:.2f} %"],
            ["두 계산의 차이", f"{abs(tr.final_recovery_ag - ss.recovery('Ag')) * 100:.1e} %p"],
            ["120 min 시점 순환부하 (ODE)", f"{tr.circulating_load[-1] * 100:.2f} %"],
        ],
    ))
    add("")
    add(f"기동 후 **약 {tr.time_to_95pct_min:.0f}분(단별 체류시간 합의 약 "
        f"{tr.time_to_95pct_min / (ss.rougher.residence_min + ss.scavenger.residence_min + ss.cleaner.residence_min):.1f}배)** 이면 "
        "성능 보증값 측정을 시작할 수 있다. 순환류(스캐빈저 정광·클리너 미광)가 "
        "안정되는 데 걸리는 시간도 같은 규모다. 시운전 계획의 안정화 대기 시간 "
        "산정 근거가 된다.")
    add("")
    return "\n".join(lines)


def perf_tail(perf) -> float:
    """RFC 미광 Ag 품위 (g/t) — 표 작성 헬퍼."""
    return perf.tailings_grade("Ag") * 1e6
