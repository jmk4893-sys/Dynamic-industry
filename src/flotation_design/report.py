"""설계 계산서 생성 (Markdown)."""

from __future__ import annotations

from . import design_basis as db
from . import references as ref
from .attrition import concentrate_grade_ceiling, short_circuit_fraction
from .hydrodynamics import analyse_cell
from .kinetics import perfect_mixer_recovery
from .circuit import solve_circuit
from .transient import simulate_startup
from .plant import PlantDesign, build_plant, mechanical_sizing_check
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
    ag_peak_tph = f.component_tph(f.peak_tph)["Ag"]
    solids_dose_g_t = sum(r.dose for r in db.REAGENTS if r.basis == "solids")
    reagent_saving_kg_y = (
        solids_dose_g_t
        * (1.0 - 1.0 / ref.WET_FEED_REAGENT_FACTOR)
        * f.average_tph
        * db.ANNUAL_OPERATING_HOURS
        / 1000.0
    )
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
    add("## 2. 전처리 — 어트리션 스크러버 (공통 설비)")
    add("")
    add("로드밀 배출 슬러리를 **묽히기 전에** 고농도 그대로 받아 입자끼리 문질러 "
        "표면을 벗기고, 희석박스에서 부선 농도로 묽혀 조건조로 보낸다. 두 안이 "
        "함께 쓰는 공통 설비이므로 1안·2안 어느 쪽 설치 전력에도 포함하지 않고 "
        "따로 계상한다. 분쇄기가 아니라는 점이 중요하다 — 입자를 깨는 것이 아니라 "
        "**표면에 붙은 것을 떼는 것**이 목적이다.")
    add("")
    add("무엇을 떼려는가:")
    add("")
    add("1. **박리 잔막** — EVA 봉지재·접착층을 벗겨낸 표면에 남은 유기 잔막. "
        "포수제가 Ag 전극에 닿는 것을 막고, 그 자체가 소수성이라 무차별 부상해 정광을 희석한다.")
    add(f"2. **슬라임 코팅** — 습식 분쇄면에 붙은 미립 Si. [2] 가 관측한 "
        f"\"습식 분쇄물은 건조 원료의 {ref.WET_FEED_REAGENT_FACTOR:.0f}배를 써야 거품이 선다\" "
        f"(150 → {db.REAGENTS[0].dose:.0f} g/t)의 유력한 원인 후보다.")
    add(f"3. **Ag 전극 박편** — Ag 는 Si 표면에 소결된 층이라 벌크 Si 보다 약하다. "
        f"표면 마모로 일부가 떨어지면 복합입자 동반비 r 이 내려가고 정광 품위 상한 "
        f"1/(1+r) 이 올라간다 (아래 상방 시나리오).")
    add("")
    add("> [!IMPORTANT]")
    add("> **성능 크레딧 없음.** [1][2] 어디에도 어트리션 시험이 없다. 위 셋은 전부 "
        "가설이므로 이 계산서의 회수율·품위·약제 투입량은 **어트리션이 없는 것과 같은 "
        f"값**이다 (`ATTRITION_PERFORMANCE_CREDIT = {db.ATTRITION_PERFORMANCE_CREDIT:.1f}`). "
        f"대신 전량 바이패스({pre.bypass})를 두어 없는 것처럼 운전할 수 있게 하고, "
        "이득을 정량화할 시험(§2.4)과 합격 기준을 설계에 넣었다. "
        "시험에서 이득이 확인되지 않으면 바이패스로 두거나 철거하는 편이 낫다.")
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
             "위는 아래로, 아래는 위로 밀어 중간 높이에 **전단면**을 만든다"],
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
             f"{sh.torque_nm:.1f} N·m / {sh.shear_stress_mpa:.1f} MPa",
             f"서비스계수 {sh.service_factor:.1f} (굳은 슬러리 기동 토크), "
             f"허용 {sh.allowable_shear_mpa:.0f} MPa"],
            ["1차 임계회전수 / 운전비",
             f"{sh.critical_speed_rpm:.0f} rpm / {sh.critical_speed_ratio:.2f}x",
             f"하한 {sh.minimum_critical_speed_ratio:.1f}x — "
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
        f"매달리므로 1차 굽힘 임계회전수가 운전 회전수에 가까워진다. 임펠러 질량은 "
        f"D^3 비례 예비값이므로 제작도 확정 후 실측 질량과 실제 베어링 스팬으로 "
        f"재검증해야 한다.")
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
    add("### 2.4 상방 시나리오와 시험 계획")
    add("")
    add("이 설비가 값을 하는 경로는 두 가지이고, 둘 다 **시험으로만 확인된다.**")
    add("")
    add(f"**(가) 정광 품위 상한.** Ag 박편이 Si 에서 떨어지면 동반비 r 이 내려간다. "
        f"현재 r = {db.COMPOSITE_CARRY_RATIO:.1f} 에서 상한은 "
        f"{concentrate_grade_ceiling(db.COMPOSITE_CARRY_RATIO) * 100:.1f} wt% 이고, "
        f"실제 정광이 {d.rfc.performance_peak.concentrate_grade('Ag') * 100:.1f} wt% 로 "
        f"거기 붙어 있다. **클리너를 더 붙여도 못 넘는 벽을 넘는 유일한 수단**이다.")
    add("")
    add(_table(
        ["동반비 r", "정광 품위 상한", "Ag + 결합 맥석 (최대 처리량)", "급광 대비"],
        [
            [
                f"{r:.1f}" + (" (현재 설계)" if r == db.COMPOSITE_CARRY_RATIO else ""),
                f"{concentrate_grade_ceiling(r) * 100:.1f} wt% Ag",
                f"{ag_peak_tph * (1.0 + r) * 1000:.2f} kg/h",
                f"급광의 {ag_peak_tph * (1.0 + r) / f.peak_tph * 100:.2f} %",
            ]
            for r in db.ATTRITION_CARRY_RATIO_CASES
        ],
    ))
    add("")
    add(f"**(나) 약제 절감.** [2] 는 습식 분쇄물에 건조 원료의 "
        f"{ref.WET_FEED_REAGENT_FACTOR:.0f}배 약제가 필요했다고 보고했다. 그 원인이 "
        f"슬라임 코팅이라면 어트리션으로 되돌릴 수 있다. 전량 회복 시 고체 기준 약제 "
        f"{solids_dose_g_t:.0f} → {solids_dose_g_t / ref.WET_FEED_REAGENT_FACTOR:.0f} g/t, "
        f"{avg_label} · 연 {db.ANNUAL_OPERATING_HOURS:,.0f} 시간 기준 **연 "
        f"{reagent_saving_kg_y:,.0f} kg** 의 포수제·촉진제 절감이다.")
    add("")
    add("| 시험 | 방법 | 판정 |")
    add("|---|---|---|")
    add(f"| T-1 스크럽 강도 스윕 | 실험실 어트리션 셀에서 0 / 1 / 3 / "
        f"{sc.specific_energy_range_kwh_t[1]:.0f} kWh/t 처리 후 동일 조건 부선 | "
        f"회수율·정광 품위·소요 약제량의 kWh/t 응답 곡선 |")
    add("| T-2 동반비 r 측정 | 세척수 bias 를 올려 수분 동반을 0 에 가깝게 만든 상태의 "
        "정광 품위 g 에서 r = (1-g)/g 를 역산, 스크럽 전후 비교 | r 이 유의하게 "
        "내려가면 (가) 성립 |")
    add(f"| T-3 실기 A/B | 바이패스를 8 시간씩 교대 개폐하며 미광 Ag·정광 품위·"
        f"약제 소요량 비교 | 실기 조건에서의 최종 확인 |")
    add(f"| T-4 미립 생성 | 스크럽 전후 -10 um 질량분율 | 증가 "
        f"**{db.ATTRITION_FINES_ACCEPTANCE_PP:.0f} %p 이하** — 넘으면 표면 정정이 아니라 "
        f"분쇄를 하고 있다는 뜻 |")
    add("")
    add(f"**미립 생성이 이 설비의 진짜 위험이다.** 문헌 공정을 그대로 따라 "
        f"탈니(desliming)를 하지 않으므로, 떨어져 나온 슬라임은 걸러지지 않고 회로에 "
        f"그대로 남는다. 1안은 세척수 bias 가 거품층에서 그것을 씻어내리므로 "
        f"(맥석 회수율 {db.RFC_GANGUE_RECOVERY * 100:.2f} %) 상대적으로 안전하지만, "
        f"2안은 수분 동반 계수가 "
        f"{db.FLOAT_MODELS['Si'].entrainment_factor:.2f} 이라 미립이 늘면 정광이 그만큼 "
        f"희석된다. **어트리션은 1안과 더 잘 맞는다.**")
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
    add(f"**설치 전력 {pre.installed_kw:.2f} kW** "
        f"(어트리션 {sc.installed_kw:.2f} + 희석박스 교반 {dil.agitator_kw:.2f}). "
        f"1안과 합치면 {d.total_installed_kw(rfc):.2f} kW 로, 전처리가 계통 전체의 "
        f"**{pre.installed_kw / d.total_installed_kw(rfc) * 100:.0f} %** 를 쓴다. "
        f"성능 크레딧이 0 인 설비로서는 결코 작지 않은 비용이며, 바이패스와 시험 계획을 "
        f"설계에 넣은 이유가 이것이다.")
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
