"""설계 계산 결과를 Markdown 리포트로 출력."""

from __future__ import annotations

from dataclasses import dataclass

from . import design_basis as db
from .circuit_design import CircuitDesign, build_circuit, sizing_check
from .conditioning import ConditionerDesign, conditioner_train
from .feed import FeedSpec, PulpProperties, pulp_at
from .kinetics import SeparationResult, simulate
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




#: 셀별 목표 체류시간 (최대 처리량 기준, 분).
TARGET_RESIDENCE_MIN = {"FC-101": 8.0, "FC-102": 10.0, "FC-103": 8.0}


def _dimension_checks(d: CircuitDesign) -> list[dict]:
    """확정 셀이 최대 처리량에서 목표 체류시간을 만족하는지 검증한다.

    미달이면 그 처리량에 필요한 셀 치수를 함께 돌려주어, 확정 치수를
    그대로 쓸 수 없다는 사실이 계산서에 드러나게 한다.
    """
    out: list[dict] = []
    for tag, target in TARGET_RESIDENCE_MIN.items():
        geom = d.cell(tag).geometry
        unit = {
            "FC-101": d.result_peak.rougher,
            "FC-102": d.result_peak.scavenger,
            "FC-103": d.result_peak.cleaner,
        }[tag]
        required = sizing_check(d.result_peak, tag, target)
        needed = cell_geometry(
            required,
            gas_holdup=geom.gas_holdup,
            froth_depth_m=geom.froth_depth_m,
            freeboard_m=geom.shell_height_m - geom.lip_height_m,
            height_to_width=geom.shell_height_m / geom.width_m,
        )
        out.append(
            {
                "tag": tag,
                "target": target,
                "required_m3": required,
                "actual_m3": geom.effective_slurry_volume_m3,
                "residence": unit.residence_min,
                "required_width_mm": needed.width_m * 1000,
                "required_height_mm": needed.shell_height_m * 1000,
                "actual_width_mm": geom.width_m * 1000,
                "actual_height_mm": geom.shell_height_m * 1000,
                "ok": geom.effective_slurry_volume_m3 >= required * 0.98,
            }
        )
    return out


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}"


def _kgh(x: float, digits: int = 2) -> str:
    return f"{x * 1000:.{digits}f}"


# --------------------------------------------------------------------------
# 회로 계산서
# --------------------------------------------------------------------------
def render(design: CircuitDesign | None = None) -> str:
    """러퍼-스캐빈저-클리너 회로 설계 계산서 (Markdown)."""
    d = design if design is not None else build_circuit()
    f = d.feed
    lines: list[str] = []
    add = lines.append

    add("# 부유선별 회로 설계 계산서 (러퍼 – 스캐빈저 – 클리너)")
    add("")
    add("> `PYTHONPATH=src python -m flotation_design` 로 자동 생성됨. "
        "설계 기준은 `src/flotation_design/design_basis.py` 참조.")
    add("")
    undersized = [c for c in _dimension_checks(d) if not c["ok"]]
    if undersized:
        add("> [!WARNING]")
        add(f"> **확정 셀이 이 처리량({f.peak_tph:.2f} t/h)에 미달한다** — "
            + ", ".join(
                f"{c['tag']} {c['residence']:.1f} min (목표 {c['target']:.0f} min)"
                for c in undersized
            )
            + ". 셀 치수는 `design_basis.py` 에 확정값으로 박혀 있어 처리량을 바꿔도 "
            "재산정되지 않는다. 본 계산서는 **기존 셀의 성능 계산**으로만 유효하며, "
            "§3 의 로터·급기 선정과 §4 의 성능 예측은 이 처리량에 사용할 수 없다. "
            "필요한 셀 치수는 §9 참조.")
        add("")

    # 1. 급광 -------------------------------------------------------------
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
            ["러퍼 급광 고체 농도 (순환류 포함)", f"{db.ROUGHER_FEED_SOLIDS * 100:.0f} wt%"],
            ["신급광 슬러리 체적유량",
             f"{d.pulp_avg.volumetric_flow_m3h:.3f} / "
             f"{d.pulp_peak.volumetric_flow_m3h:.3f} m3/h (평균/최대)"],
            ["설계 기준 처리량 (design_basis)",
             f"{db.FEED.average_tph:.2f} / {db.FEED.peak_tph:.2f} t/h"],
        ],
    ))
    add("")
    add(_table(
        ["성분", "질량분율 (wt%)", "품위 (g/t)", "비중", "속부선", "지연부선", "비부선",
         "k_fast (1/min)", "k_slow (1/min)"],
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
            ]
            for c in f.components
        ],
    ))
    add("")
    add("속부선/지연부선/비부선 분획은 백분율이다. Ag 의 비부선 12 % 는 Si 내부에 "
        "완전히 갇혀 표면에 노출되지 않은 분획으로, 부선으로는 원리적으로 회수할 수 없다.")
    add("")

    # 2. 회로 구성 ---------------------------------------------------------
    add("## 2. 회로 구성")
    add("")
    add("```")
    add("  신급광 ─┐")
    add("          ├─→ FC-101 러퍼 ─정광→ (희석) → FC-103 클리너 ─정광→ 최종 정광")
    add("  순환류 ─┘        │                          │")
    add("     ↑             미광                       미광")
    add("     │              ↓                          │")
    add("     │        FC-102 스캐빈저 ─정광─────────────┤")
    add("     │              │                          │")
    add("     └──────────────┼──────────────────────────┘")
    add("                   미광")
    add("                    ↓")
    add("                 최종 미광")
    add("```")
    add("")
    add(_table(
        ["기기", "역할", "내부 치수 (mm)", "거품층 (mm)", "기공률", "유효 슬러리 체적 (m3)"],
        [
            [
                c.tag, c.duty,
                f"{c.geometry.width_m * 1000:.0f} x {c.geometry.width_m * 1000:.0f} x "
                f"{c.geometry.shell_height_m * 1000:.0f}(H)",
                f"{c.geometry.froth_depth_m * 1000:.0f}",
                f"{c.geometry.gas_holdup * 100:.0f} %",
                f"{c.geometry.effective_slurry_volume_m3:.4f}",
            ]
            for c in d.cells
        ],
    ))
    add("")
    add("스캐빈저는 러퍼와 **동일 동체**다 (예비품·구동부 공용화). 회수 위주 duty 이므로 "
        "거품층을 얕게(50 mm) 가져가 유효 체적이 오히려 러퍼보다 크다. 반대로 클리너는 "
        "품위 위주라 거품층을 깊게(150 mm) 가져가 배수를 유도한다.")
    add("")

    # 3. 셀별 기계 사양 -----------------------------------------------------
    add("## 3. 셀별 기계 사양")
    add("")
    add(_table(
        ["항목"] + [c.tag for c in d.cells],
        [
            ["로터 지름 (mm)"] + [f"{c.impeller.diameter_m * 1000:.0f}" for c in d.cells],
            ["스테이터 외경 (mm)"] + [f"{c.impeller.stator_od_m * 1000:.0f}" for c in d.cells],
            ["회전수 (rpm)"] + [f"{c.impeller.speed_rpm:.0f}" for c in d.cells],
            ["주속 (m/s)"] + [f"{c.impeller.tip_speed_m_s:.2f}" for c in d.cells],
            ["축동력 무급기 (kW)"]
            + [f"{c.impeller.ungassed_power_w / 1000:.2f}" for c in d.cells],
            ["단위체적 동력 (kW/m3)"]
            + [f"{c.impeller.specific_power_kw_m3:.2f}" for c in d.cells],
            ["**모터 (kW)**"] + [f"**{c.impeller.motor_rating_kw:.2f}**" for c in d.cells],
            ["설계 Jg (cm/s)"]
            + [f"{c.aeration.superficial_gas_velocity_cm_s:.1f}" for c in d.cells],
            ["급기량 (m3/h)"] + [f"{c.aeration.air_flow_m3h:.1f}" for c in d.cells],
            ["급기 제어범위 (m3/h)"]
            + [f"{c.aeration.air_flow_min_m3h:.1f}~{c.aeration.air_flow_max_m3h:.1f}"
               for c in d.cells],
            ["기포 표면적 플럭스 Sb (1/s)"]
            + [f"{c.aeration.bubble_surface_area_flux_1_s:.0f}" for c in d.cells],
            ["급광 슬러리 밀도 (kg/m3)"] + [f"{c.pulp_density_kg_m3:.0f}" for c in d.cells],
        ],
    ))
    add("")
    add(f"**송풍기는 3기 공용 1대**로 선정한다 — "
        f"셀별 최대 급기량 합계 {d.blower_flow_m3h:.0f} m3/h x "
        f"{d.blower_pressure_kpa:.0f} kPa, **{d.blower_rating_kw:.2f} kW** 측류형. "
        f"분기마다 열식 질량유량계와 제어밸브를 두어 셀별 Jg 를 독립 제어한다.")
    add("")

    # 4. 물질수지 ----------------------------------------------------------
    add("## 4. 회로 물질수지")
    add("")
    peak_label = f"최대 {f.peak_tph:.2f} t/h"
    avg_label = f"평균 {f.average_tph:.2f} t/h"
    for label, res in ((peak_label, d.result_peak), (avg_label, d.result_avg)):
        add(f"### {label}")
        add("")
        add(_table(
            ["셀", "체류시간 (min)", "급광 (kg/h)", "급광 (m3/h)", "고체농도",
             "정광 (kg/h)", "mass pull", "Ag 회수율", "Cu 회수율"],
            [
                [
                    u.unit.tag, f"{u.residence_min:.2f}", _kgh(u.feed.dry_tph, 1),
                    f"{u.feed_volume_m3h:.3f}", f"{_pct(u.feed.solids_mass_fraction)} %",
                    _kgh(u.concentrate.dry_tph, 1), f"{_pct(u.mass_pull)} %",
                    f"{_pct(u.recovery('Ag'))} %", f"{_pct(u.recovery('Cu'))} %",
                ]
                for u in (res.rougher, res.scavenger, res.cleaner)
            ],
        ))
        add("")
        add(_table(
            ["성분", "신급광 (kg/h)", "최종 정광 (kg/h)", "최종 미광 (kg/h)",
             "회로 회수율 (%)", "정광 품위 (%)", "미광 품위 (g/t)"],
            [
                [
                    name,
                    _kgh(res.new_feed.component_tph(name)),
                    _kgh(res.concentrate.component_tph(name)),
                    _kgh(res.tailings.component_tph(name)),
                    _pct(res.recovery(name)),
                    f"{res.concentrate.grade_fraction(name) * 100:.2f}",
                    f"{res.tailings.grade_fraction(name) * 1e6:,.0f}",
                ]
                for name in res.new_feed.components
            ]
            + [
                [
                    "**합계**",
                    f"**{_kgh(res.new_feed.dry_tph, 1)}**",
                    f"**{_kgh(res.concentrate.dry_tph, 1)}**",
                    f"**{_kgh(res.tailings.dry_tph, 1)}**",
                    f"**{_pct(res.mass_pull)}** (mass pull)",
                    "**100.00**",
                    "—",
                ]
            ],
        ))
        add("")
        fl_r = d.froth_loading("FC-101", res)
        fl_s = d.froth_loading("FC-102", res)
        fl_c = d.froth_loading("FC-103", res)
        add(_table(
            ["지표", "값"],
            [
                ["**Ag 회로 회수율**", f"**{_pct(res.recovery('Ag'))} %**"],
                ["Ag 정광 품위",
                 f"{res.concentrate.grade_fraction('Ag') * 1e6:,.0f} g/t "
                 f"({res.concentrate.grade_fraction('Ag') * 100:.2f} %)"],
                ["Ag 농축비", f"{res.enrichment_ratio('Ag'):.2f} 배"],
                ["Ag 선별효율 (Newton)", f"{_pct(res.separation_efficiency('Ag'))} %"],
                ["Ag 미광 손실", f"{_kgh(res.tailings.component_tph('Ag'))} kg/h "
                 f"({res.tailings.grade_fraction('Ag') * 1e6:,.0f} g/t)"],
                ["**Cu 회로 회수율**", f"**{_pct(res.recovery('Cu'))} %**"],
                ["Cu 정광 품위", f"{res.concentrate.grade_fraction('Cu') * 100:.1f} %"],
                ["정광 질량 회수율", f"{_pct(res.mass_pull)} %"],
                ["정광 고체 농도", f"{_pct(res.concentrate.solids_mass_fraction)} wt%"],
                ["**순환부하**", f"**{_pct(res.circulating_load)} %** "
                 f"({_kgh(res.recycle.dry_tph, 1)} kg/h)"],
                ["신수 소요량", f"{res.fresh_water_m3h:.2f} m3/h"],
                ["Froth carry rate (R/S/C)",
                 f"{fl_r.carry_rate_tph_m2:.3f} / {fl_s.carry_rate_tph_m2:.3f} / "
                 f"{fl_c.carry_rate_tph_m2:.3f} t/h/m2 (한계 1.5) — "
                 f"{'OK' if all((fl_r.carry_rate_ok, fl_s.carry_rate_ok, fl_c.carry_rate_ok)) else 'NG'}"],
                ["Lip loading (R/S/C)",
                 f"{fl_r.lip_loading_tph_m:.3f} / {fl_s.lip_loading_tph_m:.3f} / "
                 f"{fl_c.lip_loading_tph_m:.3f} t/h/m (한계 1.5) — "
                 f"{'OK' if all((fl_r.lip_loading_ok, fl_s.lip_loading_ok, fl_c.lip_loading_ok)) else 'NG'}"],
                ["물질수지 폐합 오차", f"{res.mass_balance_error_tph() * 1e6:.2e} g/h "
                 f"(반복 {res.iterations} 회)"],
            ],
        ))
        add("")

    # 5. 러퍼 단독 대비 ------------------------------------------------------
    add("## 5. 러퍼 단독(Phase 1) 대비 효과")
    add("")
    base = build_design(f)
    peak = d.result_peak
    add(_table(
        ["지표", "러퍼 단독", "러퍼+스캐빈저+클리너", "차이"],
        [
            ["Ag 회수율", f"{_pct(base.result_peak.recovery['Ag'])} %",
             f"{_pct(peak.recovery('Ag'))} %",
             f"{(peak.recovery('Ag') - base.result_peak.recovery['Ag']) * 100:+.1f} %p"],
            ["Cu 회수율", f"{_pct(base.result_peak.recovery['Cu'])} %",
             f"{_pct(peak.recovery('Cu'))} %",
             f"{(peak.recovery('Cu') - base.result_peak.recovery['Cu']) * 100:+.1f} %p"],
            ["정광 Ag 품위",
             f"{base.result_peak.concentrate.grade_fraction('Ag') * 100:.2f} %",
             f"{peak.concentrate.grade_fraction('Ag') * 100:.2f} %",
             f"{peak.enrichment_ratio('Ag') / base.result_peak.enrichment_ratio('Ag'):.2f} 배"],
            ["정광 Si 함량",
             f"{base.result_peak.concentrate.grade_fraction('Si') * 100:.1f} %",
             f"{peak.concentrate.grade_fraction('Si') * 100:.1f} %",
             f"{(peak.concentrate.grade_fraction('Si') - base.result_peak.concentrate.grade_fraction('Si')) * 100:+.1f} %p"],
            ["정광량 (후단 침출 부하)",
             f"{_kgh(base.result_peak.concentrate.dry_tph, 1)} kg/h",
             f"{_kgh(peak.concentrate.dry_tph, 1)} kg/h",
             f"{(peak.concentrate.dry_tph / base.result_peak.concentrate.dry_tph - 1) * 100:+.0f} %"],
            ["Ag 선별효율 (Newton)",
             f"{_pct(base.result_peak.separation_efficiency('Ag'))} %",
             f"{_pct(peak.separation_efficiency('Ag'))} %",
             f"{(peak.separation_efficiency('Ag') - base.result_peak.separation_efficiency('Ag')) * 100:+.1f} %p"],
        ],
    ))
    add("")
    add(f"{peak_label} 기준. 회수율 이득보다 **품위 이득이 훨씬 크다** — 정광의 Si 가 "
        "대부분 제거되어 후단 침출 물량이 줄고, 같은 Ag 를 훨씬 작은 반응조에서 "
        "처리할 수 있게 된다.")
    add("")

    # 6. 조건조 ------------------------------------------------------------
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
            for c in d.conditioners
        ],
    ))
    add("")
    add("조건조는 **순환류를 포함한 러퍼 급광 유량** 기준으로 산정했다 "
        f"(최대 {d.result_peak.rougher.feed_volume_m3h:.3f} m3/h).")
    add("")

    # 7. 약제 --------------------------------------------------------------
    add("## 7. 약제 계통")
    add("")
    add("투입량은 **신급광 건조 고체 1 t 당** 유효성분 g 수다 (순환류 제외).")
    add("")
    for tph, label in ((f.average_tph, avg_label), (f.peak_tph, peak_label)):
        add(f"### {label}")
        add("")
        add(_table(
            ["약제", "역할", "투입량 (g/t)", "유효성분 (kg/h)", "조제농도",
             "펌프 유량 (L/h)", "펌프 선정 (L/h)", "투입 지점"],
            [
                [
                    dose.reagent.name, dose.reagent.role, f"{dose.reagent.dose_g_per_t:.0f}",
                    f"{dose.active_kg_h:.3f}",
                    f"{dose.reagent.solution_strength * 100:.0f}%"
                    if dose.reagent.solution_strength < 1 else "원액",
                    f"{dose.solution_l_h:.2f}", f"{dose.pump_rating_l_h():.1f}",
                    dose.reagent.addition_point,
                ]
                for dose in reagent_schedule(db.REAGENTS, tph)
            ],
        ))
        add("")
    add("**관리 포인트**")
    add("")
    for r in db.REAGENTS:
        if r.note:
            add(f"- **{r.name}** — {r.note}")
    add("")

    # 8. 유틸리티 ----------------------------------------------------------
    add("## 8. 유틸리티 집계")
    add("")
    rotor_kw = sum(c.impeller.motor_rating_kw for c in d.cells)
    agitator_kw = sum(c.agitator_kw for c in d.conditioners)
    pump_kw = 0.75 + 0.75 + 0.55  # 급광 + 순환 + 정광 이송
    installed = rotor_kw + d.blower_rating_kw + agitator_kw + pump_kw + 0.5
    running = (
        sum(c.impeller.gassed_power_w for c in d.cells) / 1000.0
        + (d.blower_flow_m3h / 3600.0) * (d.blower_pressure_kpa * 1000.0) / 0.55 / 1000.0 * 0.7
        + sum(c.working_volume_m3 * c.specific_power_kw_m3 for c in d.conditioners)
        + pump_kw * 0.7
        + 0.3
    )
    add(_table(
        ["항목", "값"],
        [
            ["로터 구동 (3기 합계)", f"{rotor_kw:.2f} kW"],
            ["송풍기 (공용 1대)", f"{d.blower_rating_kw:.2f} kW"],
            ["조건조 교반기", f"{agitator_kw:.2f} kW"],
            ["펌프 (급광·순환·정광)", f"{pump_kw:.2f} kW"],
            ["약제 정량펌프 (10대)", "0.50 kW"],
            ["**설치 전력 합계**", f"**{installed:.2f} kW**"],
            ["상시 소비 전력 (최대 운전시 추정)", f"{running:.2f} kW"],
            ["신수 소요량 (최대)", f"{d.result_peak.fresh_water_m3h:.2f} m3/h "
             f"(거품 세척수 {db.CLEANER_WASH_WATER_M3H:.2f} 포함)"],
            ["급기", f"{d.blower_flow_m3h:.0f} m3/h @ {d.blower_pressure_kpa:.0f} kPa"],
            ["최종 정광", f"{_kgh(d.result_peak.concentrate.dry_tph, 1)} kg/h @ "
             f"{_pct(d.result_peak.concentrate.solids_mass_fraction)} wt%"],
            ["최종 미광", f"{_kgh(d.result_peak.tailings.dry_tph, 1)} kg/h @ "
             f"{_pct(d.result_peak.tailings.solids_mass_fraction)} wt%"],
        ],
    ))
    add("")

    # 9. 확정 치수 검증 ----------------------------------------------------
    add("## 9. 확정 치수 검증")
    add("")
    add("셀 3기는 **확정된 제작 치수**이며, 본 계산서는 그 셀을 주어진 처리량에서 "
        "운전했을 때의 성능 계산이다. 처리량을 바꿔 계산하면 셀은 그대로인 채 "
        "체류시간이 변하므로, 아래 표에서 목표 체류시간을 만족하는지 반드시 확인해야 한다. "
        "NG 가 나오면 §3 의 로터·급기 선정도 그 처리량에는 유효하지 않다.")
    add("")
    checks = _dimension_checks(d)
    add(_table(
        ["셀", "목표 체류시간", "필요 유효 체적", "확정 유효 체적", "실제 체류시간",
         "필요 치수 (재계산)", "확정 치수", "판정"],
        [
            [
                c["tag"], f"{c['target']:.1f} min", f"{c['required_m3']:.4f} m3",
                f"{c['actual_m3']:.4f} m3", f"{c['residence']:.2f} min",
                f"{c['required_width_mm']:.0f} x {c['required_height_mm']:.0f} mm",
                f"{c['actual_width_mm']:.0f} x {c['actual_height_mm']:.0f} mm",
                "OK" if c["ok"] else "**NG**",
            ]
            for c in checks
        ],
    ))
    add("")
    add(f"{peak_label} 기준. 러퍼는 Phase 1 에서 확정한 셀을 그대로 쓰므로 "
        "순환부하가 실린 뒤에도 8분 이상을 확보하는지가 검증 항목이다.")
    add("")
    return "\n".join(lines)
