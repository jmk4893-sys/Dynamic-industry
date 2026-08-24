"""설계 계산 결과를 Markdown 리포트로 출력."""

from __future__ import annotations

from dataclasses import dataclass

from . import design_basis as db
from .conditioning import ConditionerDesign, conditioner_train
from .feed import FeedSpec, PulpProperties, pulp_at
from .kinetics import SeparationResult, n_cells_in_series_recovery, simulate
from .reagents import reagent_schedule
from .sizing import (
    AerationDesign,
    CellGeometry,
    ImpellerDesign,
    aeration_design,
    cell_geometry,
    froth_loading,
    impeller_design,
    required_slurry_volume,
    residence_time,
    rounded_cell,
)


@dataclass(frozen=True)
class DesignCase:
    """설계 기준 전체를 한 번에 계산한 결과 묶음."""

    feed: FeedSpec
    pulp_avg: PulpProperties
    pulp_peak: PulpProperties
    calculated_geometry: CellGeometry
    geometry: CellGeometry
    impeller: ImpellerDesign
    aeration: AerationDesign
    tau_avg_min: float
    tau_peak_min: float
    result_avg: SeparationResult
    result_peak: SeparationResult
    conditioners: tuple[ConditionerDesign, ...]


def build_design(feed: FeedSpec = db.FEED) -> DesignCase:
    """설계 기준으로부터 전체 계산을 수행한다."""
    pulp_avg = pulp_at(feed, feed.average_tph)
    pulp_peak = pulp_at(feed, feed.peak_tph)

    needed = required_slurry_volume(
        pulp_peak.volumetric_flow_m3h, db.TARGET_RESIDENCE_AT_PEAK_MIN
    )
    calc = cell_geometry(
        needed,
        gas_holdup=db.GAS_HOLDUP,
        froth_depth_m=db.FROTH_DEPTH_M,
        freeboard_m=db.FREEBOARD_M,
        height_to_width=db.HEIGHT_TO_WIDTH,
    )
    geom = rounded_cell(calc, db.CELL_WIDTH_M, db.CELL_SHELL_HEIGHT_M)

    impeller = impeller_design(
        geom,
        pulp_peak.pulp_density_kg_m3,
        diameter_ratio=db.IMPELLER_DIAMETER_RATIO,
        tip_speed_m_s=db.IMPELLER_TIP_SPEED_M_S,
        power_number=db.IMPELLER_POWER_NUMBER,
    )
    aer = aeration_design(
        geom,
        pulp_peak.pulp_density_kg_m3,
        sparger_clearance_m=impeller.bottom_clearance_m,
        jg_cm_s=db.JG_DESIGN_CM_S,
        bubble_d32_mm=db.BUBBLE_D32_MM,
    )

    tau_avg = residence_time(geom, pulp_avg.volumetric_flow_m3h, feed.average_tph).residence_min
    tau_peak = residence_time(geom, pulp_peak.volumetric_flow_m3h, feed.peak_tph).residence_min

    result_avg = simulate(
        feed.component_tph(feed.average_tph), db.FLOAT_MODELS, tau_avg, db.WATER_RECOVERY
    )
    result_peak = simulate(
        feed.component_tph(feed.peak_tph), db.FLOAT_MODELS, tau_peak, db.WATER_RECOVERY
    )

    conditioners = conditioner_train(db.CONDITIONER_STAGES, pulp_peak.volumetric_flow_m3h)

    return DesignCase(
        feed=feed,
        pulp_avg=pulp_avg,
        pulp_peak=pulp_peak,
        calculated_geometry=calc,
        geometry=geom,
        impeller=impeller,
        aeration=aer,
        tau_avg_min=tau_avg,
        tau_peak_min=tau_peak,
        result_avg=result_avg,
        result_peak=result_peak,
        conditioners=conditioners,
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def render(case: DesignCase) -> str:
    """설계 계산 리포트 (Markdown)."""
    f, g, imp, aer = case.feed, case.geometry, case.impeller, case.aeration
    lines: list[str] = []
    add = lines.append

    add("# 단단 부유선별기 설계 계산서")
    add("")
    add("> `python -m flotation_design` 로 자동 생성됨. "
        "설계 기준은 `src/flotation_design/design_basis.py` 참조.")
    add("")

    # 1. 급광
    add("## 1. 급광 사양")
    add("")
    add(_table(
        ["항목", "값"],
        [
            ["평균 처리량 (건조 고체)", f"{f.average_tph:.2f} t/h"],
            ["최대 처리량 (건조 고체)", f"{f.peak_tph:.2f} t/h"],
            ["급광 입도 P80", f"{f.p80_micron:.0f} um"],
            ["탈니(deslime) 컷", f"{f.deslime_cut_micron:.0f} um"],
            ["고체 평균 비중", f"{f.solids_specific_gravity:.3f}"],
            ["슬러리 고체 농도", f"{f.solids_mass_fraction * 100:.0f} wt%"],
            ["슬러리 비중", f"{case.pulp_peak.pulp_specific_gravity:.3f}"],
            ["고체 체적분율", f"{case.pulp_peak.solids_volume_fraction * 100:.1f} vol%"],
        ],
    ))
    add("")
    add(_table(
        ["성분", "질량분율 (wt%)", "품위 (g/t)", "비중", "평균 0.3 t/h (kg/h)", "최대 0.5 t/h (kg/h)"],
        [
            [
                c.name,
                f"{c.mass_fraction * 100:.3f}",
                f"{c.mass_fraction * 1e6:,.0f}",
                f"{c.specific_gravity:.2f}",
                f"{f.average_tph * c.mass_fraction * 1000:.2f}",
                f"{f.peak_tph * c.mass_fraction * 1000:.2f}",
            ]
            for c in f.components
        ],
    ))
    add("")
    add(_table(
        ["유량", "평균 (0.3 t/h)", "최대 (0.5 t/h)"],
        [
            ["건조 고체", f"{case.pulp_avg.dry_tph:.3f} t/h", f"{case.pulp_peak.dry_tph:.3f} t/h"],
            ["물", f"{case.pulp_avg.water_tph:.3f} t/h", f"{case.pulp_peak.water_tph:.3f} t/h"],
            ["슬러리 (질량)", f"{case.pulp_avg.slurry_tph:.3f} t/h",
             f"{case.pulp_peak.slurry_tph:.3f} t/h"],
            ["슬러리 (체적)", f"{case.pulp_avg.volumetric_flow_m3h:.3f} m3/h",
             f"{case.pulp_peak.volumetric_flow_m3h:.3f} m3/h"],
            ["슬러리 (체적)", f"{case.pulp_avg.volumetric_flow_m3h / 0.06:.1f} L/min",
             f"{case.pulp_peak.volumetric_flow_m3h / 0.06:.1f} L/min"],
        ],
    ))
    add("")

    # 2. 셀 체적 및 형상
    add("## 2. 셀 체적 및 형상")
    add("")
    required = required_slurry_volume(
        case.pulp_peak.volumetric_flow_m3h, db.TARGET_RESIDENCE_AT_PEAK_MIN
    )
    add(_table(
        ["항목", "값", "근거"],
        [
            ["설계 체류시간 (최대 유량 기준)", f"{db.TARGET_RESIDENCE_AT_PEAK_MIN:.1f} min",
             "단단(스캐빈저 없음) 구성 — 통상 러퍼 4~6분 대비 상향"],
            ["필요 슬러리 체적", f"{required:.3f} m3", "Q x tau"],
            ["기공률 (air hold-up)", f"{g.gas_holdup * 100:.0f} %", "기계식 강제급기 셀 표준"],
            ["필요 펄프존 체적", f"{required / (1 - g.gas_holdup):.3f} m3", "슬러리 체적 / (1 - 기공률)"],
            ["계산 치수 (한 변 x 높이)",
             f"{case.calculated_geometry.width_m * 1000:.0f} x "
             f"{case.calculated_geometry.shell_height_m * 1000:.0f} mm", "H/W = 1.15"],
            ["**확정 치수 (내부)**",
             f"**{g.width_m * 1000:.0f} x {g.width_m * 1000:.0f} x "
             f"{g.shell_height_m * 1000:.0f} mm(H)**", "제작 반올림"],
            ["단면적", f"{g.cross_section_m2:.3f} m2", ""],
            ["동체 전체 체적", f"{g.shell_volume_m3:.3f} m3", ""],
            ["월류 립 높이 (운전 액면)", f"{g.lip_height_m * 1000:.0f} mm",
             f"여유고 {(g.shell_height_m - g.lip_height_m) * 1000:.0f} mm"],
            ["거품층 두께", f"{g.froth_depth_m * 1000:.0f} mm", "50~100 mm 가변 (다트밸브 액면제어)"],
            ["펄프존 체적", f"{g.pulp_zone_volume_m3:.3f} m3", ""],
            ["**유효 슬러리 체적**", f"**{g.effective_slurry_volume_m3:.3f} m3**", "체류시간 기준값"],
        ],
    ))
    add("")
    add(_table(
        ["운전점", "슬러리 유량", "유효 체류시간"],
        [
            ["평균 0.30 t/h", f"{case.pulp_avg.volumetric_flow_m3h:.3f} m3/h",
             f"{case.tau_avg_min:.1f} min"],
            ["최대 0.50 t/h", f"{case.pulp_peak.volumetric_flow_m3h:.3f} m3/h",
             f"{case.tau_peak_min:.1f} min"],
        ],
    ))
    add("")

    # 3. 임펠러
    add("## 3. 로터/스테이터 및 구동부")
    add("")
    add(_table(
        ["항목", "값", "비고"],
        [
            ["로터 지름 D", f"{imp.diameter_m * 1000:.0f} mm",
             f"D/W = {imp.diameter_m / g.width_m:.2f}"],
            ["스테이터 외경", f"{imp.stator_od_m * 1000:.0f} mm", "1.35 D"],
            ["로터 바닥 이격", f"{imp.bottom_clearance_m * 1000:.0f} mm", "0.6 D"],
            ["회전수", f"{imp.speed_rpm:.0f} rpm", "VFD 264~528 rpm 가변"],
            ["주속 (tip speed)", f"{imp.tip_speed_m_s:.2f} m/s", "미립 부선 5~7 m/s"],
            ["축동력 (무급기)", f"{imp.ungassed_power_w / 1000:.2f} kW",
             f"Np = {db.IMPELLER_POWER_NUMBER}"],
            ["축동력 (급기시)", f"{imp.gassed_power_w / 1000:.2f} kW", "RPD 0.70"],
            ["단위체적 동력", f"{imp.specific_power_kw_m3:.2f} kW/m3", "소형 셀 3~5 kW/m3"],
            ["**모터**", f"**{imp.motor_rating_kw:.1f} kW** (4P, IE3) + VFD", "여유율 1.4"],
        ],
    ))
    add("")

    # 4. 급기
    add("## 4. 급기 (aeration)")
    add("")
    add(_table(
        ["항목", "값", "비고"],
        [
            ["표면기체속도 Jg (설계)", f"{aer.superficial_gas_velocity_cm_s:.2f} cm/s",
             "미립 금속 부선 0.6~1.4 cm/s"],
            ["급기량 (설계)", f"{aer.air_flow_m3h:.1f} m3/h "
             f"({aer.air_flow_m3h / 0.06:.0f} L/min)", ""],
            ["급기량 (제어 범위)",
             f"{aer.air_flow_min_m3h:.1f} ~ {aer.air_flow_max_m3h:.1f} m3/h",
             "Jg 0.6~1.4 cm/s"],
            ["기포 Sauter 평균경 d32", f"{aer.bubble_sauter_mean_mm:.1f} mm", "MIBC 기준"],
            ["기포 표면적 플럭스 Sb", f"{aer.bubble_surface_area_flux_1_s:.0f} 1/s",
             "목표 40~70 1/s"],
            ["급기점 정압", f"{aer.static_pressure_kpa:.1f} kPa", "펄프 수두 (로터 하단 기준)"],
            ["필요 토출압", f"{aer.total_pressure_kpa:.1f} kPa", "배관·스파저 손실 15 kPa 포함"],
            ["송풍기 선정 duty",
             f"{aer.selection_flow_m3h:.0f} m3/h x {aer.selection_pressure_kpa:.0f} kPa",
             "최대 Jg + 압력 여유 30%"],
            ["송풍기 축동력", f"{aer.blower_shaft_power_w / 1000:.2f} kW", "효율 55%"],
            ["**송풍기**",
             f"**{aer.blower_rating_kw:.2f} kW** 측류형(side-channel) 블로어",
             "열식 질량유량계 + 제어밸브로 Jg 폐루프 제어"],
        ],
    ))
    add("")

    # 5. 성능 예측
    add("## 5. 성능 예측 (1차 반응속도 모델)")
    add("")
    for label, res in (("평균 0.30 t/h", case.result_avg), ("최대 0.50 t/h", case.result_peak)):
        fl = froth_loading(g, res.concentrate.dry_tph)
        add(f"### {label} (체류시간 {res.residence_min:.1f} min)")
        add("")
        add(_table(
            ["성분", "급광 (kg/h)", "정광 (kg/h)", "미광 (kg/h)", "회수율 (%)",
             "정광 품위 (%)"],
            [
                [
                    name,
                    f"{res.feed.component_tph[name] * 1000:.2f}",
                    f"{res.concentrate.component_tph[name] * 1000:.2f}",
                    f"{res.tailings.component_tph[name] * 1000:.2f}",
                    f"{res.recovery[name] * 100:.1f}",
                    f"{res.concentrate.grade_fraction(name) * 100:.2f}",
                ]
                for name in res.feed.component_tph
            ]
            + [
                [
                    "**합계**",
                    f"**{res.feed.dry_tph * 1000:.1f}**",
                    f"**{res.concentrate.dry_tph * 1000:.1f}**",
                    f"**{res.tailings.dry_tph * 1000:.1f}**",
                    f"**{res.mass_pull * 100:.1f}** (mass pull)",
                    "**100.00**",
                ]
            ],
        ))
        add("")
        add(_table(
            ["지표", "값"],
            [
                ["Ag 회수율", f"{res.recovery['Ag'] * 100:.1f} %"],
                ["Ag 정광 품위", f"{res.concentrate.grade_ppm('Ag'):,.0f} g/t "
                 f"({res.concentrate.grade_fraction('Ag') * 100:.2f} %)"],
                ["Ag 농축비", f"{res.enrichment_ratio('Ag'):.2f} 배"],
                ["Ag 선별효율 (Newton)", f"{res.separation_efficiency('Ag') * 100:.1f} %"],
                ["Cu 회수율", f"{res.recovery['Cu'] * 100:.1f} %"],
                ["Cu 정광 품위", f"{res.concentrate.grade_fraction('Cu') * 100:.1f} %"],
                ["정광 질량 회수율", f"{res.mass_pull * 100:.1f} %"],
                ["Froth carry rate", f"{fl.carry_rate_tph_m2:.3f} t/h/m2 "
                 f"(한계 {fl.carry_rate_limit_tph_m2:.1f}) — "
                 f"{'OK' if fl.carry_rate_ok else 'NG'}"],
                ["Lip loading", f"{fl.lip_loading_tph_m:.3f} t/h/m "
                 f"(한계 {fl.lip_loading_limit_tph_m:.1f}) — "
                 f"{'OK' if fl.lip_loading_ok else 'NG'}"],
            ],
        ))
        add("")

    # 단단 vs 2단
    add("### 단단 구성의 한계 (참고)")
    add("")
    m = db.FLOAT_MODELS["Ag"]
    rows = []
    for n in (1, 2, 3):
        r = n_cells_in_series_recovery(m.k_per_min, case.tau_peak_min, n, m.r_max)
        rows.append([f"{n} 기 직렬 (동일 총 체적)", f"{r * 100:.1f} %"])
    add(_table(["구성 (최대 유량 기준, 총 체류시간 동일)", "Ag 회수율 (진부선분)"], rows))
    add("")
    gain = (
        n_cells_in_series_recovery(m.k_per_min, case.tau_peak_min, 2, m.r_max)
        - n_cells_in_series_recovery(m.k_per_min, case.tau_peak_min, 1, m.r_max)
    )
    add(f"위 표는 수분 동반(entrainment) 기여분을 제외한 진부선 회수율이다. "
        f"동일 총 체적을 셀 2기로 나누면 Ag 회수율이 {gain * 100:.1f}%p "
        f"개선된다. 본 설계는 요구사항에 따라 1단으로 확정하되, 셀 동체를 "
        f"중앙 격벽으로 2실 분할할 수 있도록 플랜지 좌면을 남겨 향후 개조를 가능하게 한다.")
    add("")

    # 6. 조건조
    add("## 6. 조건조 (conditioner)")
    add("")
    add(_table(
        ["기기", "역할", "체류시간 (min)", "유효 체적 (m3)", "탱크 체적 (m3)",
         "내경 x 높이 (mm)", "교반기 (kW)"],
        [
            [
                c.tag, c.duty, f"{c.residence_min:.0f}", f"{c.working_volume_m3:.3f}",
                f"{c.tank_volume_m3:.2f}",
                f"{c.diameter_m * 1000:.0f} x {c.height_m * 1000:.0f}",
                f"{c.agitator_kw:.2f}",
            ]
            for c in case.conditioners
        ],
    ))
    add("")

    # 7. 약제
    add("## 7. 약제 계통")
    add("")
    for tph, label in ((f.average_tph, "평균 0.30 t/h"), (f.peak_tph, "최대 0.50 t/h")):
        add(f"### {label}")
        add("")
        add(_table(
            ["약제", "역할", "투입량 (g/t)", "유효성분 (kg/h)", "조제농도",
             "펌프 유량 (L/h)", "펌프 선정 (L/h)", "투입 지점"],
            [
                [
                    d.reagent.name, d.reagent.role, f"{d.reagent.dose_g_per_t:.0f}",
                    f"{d.active_kg_h:.3f}",
                    f"{d.reagent.solution_strength * 100:.0f}%" if d.reagent.solution_strength < 1
                    else "원액",
                    f"{d.solution_l_h:.2f}", f"{d.pump_rating_l_h():.1f}",
                    d.reagent.addition_point,
                ]
                for d in reagent_schedule(db.REAGENTS, tph)
            ],
        ))
        add("")
    add("**관리 포인트**")
    add("")
    for r in db.REAGENTS:
        if r.note:
            add(f"- **{r.name}** — {r.note}")
    add("")

    # 8. 유틸리티
    add("## 8. 유틸리티 집계")
    add("")
    total_kw = (
        imp.motor_rating_kw
        + aer.blower_rating_kw
        + sum(c.agitator_kw for c in case.conditioners)
        + 1.5  # 급광/미광 펌프
        + 0.3  # 정량펌프 6대
    )
    running_kw = (
        imp.gassed_power_w / 1000
        + aer.blower_shaft_power_w / 1000
        + sum(c.working_volume_m3 * c.specific_power_kw_m3 for c in case.conditioners)
        + 1.1
        + 0.2
    )
    add(_table(
        ["항목", "값"],
        [
            ["설치 전력 (합계)", f"{total_kw:.2f} kW"],
            ["상시 소비 전력 (최대 운전시 추정)", f"{running_kw:.2f} kW"],
            ["공정수 (신수 + 회수수)",
             f"{case.pulp_peak.water_tph:.2f} m3/h (거품세척수 0.2 m3/h 별도)"],
            ["급기", f"{aer.selection_flow_m3h:.0f} m3/h @ {aer.selection_pressure_kpa:.0f} kPa"],
            ["운전 중량 (셀 단독, 추정)",
             f"{g.volume_to_lip_m3 * case.pulp_peak.pulp_density_kg_m3 + 190:.0f} kg"],
        ],
    ))
    add("")
    return "\n".join(lines)
