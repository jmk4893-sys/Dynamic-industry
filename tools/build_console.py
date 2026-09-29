# -*- coding: utf-8 -*-
"""운전 콘솔의 값 블록을 파이썬 모델에서 찍는다.

콘솔 화면에 뜨는 숫자를 손으로 적으면 도면이 REV.38 인데 콘솔이 REV.30 을
보여 주는 날이 온다. 그래서 `docs/consoles/pv-preprocess-console.html` 안의
`CONSOLE` 리터럴과 `PV_BRAND` 블록은 이 스크립트가 만든다 — 콘솔 파일에서
사람이 쓰는 것은 화면 구성이고, 값과 마크는 여기서 온다.

실행 (저장소 루트에서):
    PYTHONPATH=src python tools/build_console.py
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "src")

from pv_preprocess import (acceptance, acoustics, air, brand, campaign, casing,  # noqa: E402
                           dust, electrical, grade, handoff, reliability, safety,
                           seismic, smart, thermal)

CONSOLE = pathlib.Path("docs/consoles/pv-preprocess-console.html")


def values() -> dict[str, object]:
    """콘솔이 띄우는 값. 전부 파생이고, 여기서 새로 만드는 숫자는 없다."""
    camp = campaign.summary()
    hand = handoff.summary()
    return {
        # 공정
        "taktS": camp["takt_s"],
        "throughputPerH": camp["throughput_per_h"],
        "peakWip": camp["peak_wip"],
        "campaignPanels": camp["panels"],
        "campaignMin": camp["run_min"],
        "downstreamPerH": hand["downstream_per_h"],
        "rideThroughH": handoff.buffer_ride_through_h(),
        "drainRideThroughH": handoff.buffer_drain_ride_through_h(),
        "bufferStockSlots": handoff.buffer_stock_target_slots(),
        "bufferHeadroomSlots": handoff.buffer_headroom_slots(),
        "bottleneck": campaign.bottleneck(),
        "idealTaktS": campaign.ideal_takt_s(),
        "singlePointBlocks": len(grade.single_point_blocks()),
        "achievableAvailability": reliability.achievable_availability(),
        "casingBays": len(casing.all_bays()),
        "casingDoors": casing.bays_by_kind()["door"],
        "casingWindows": casing.bays_by_kind()["window"],
        "casingMassKg": casing.mass_kg(),
        "casingShoulderMm": casing.SHOULDER_MM,
        # 전기
        "installedKw": electrical.installed_kw(),
        "demandKw": electrical.demand_kw(),
        "contractKw": electrical.contract_kw(),
        "breakerAt": electrical.main_breaker_at(),
        "siteSharePct": electrical.site_utilisation_pct(),
        # 유틸리티
        "airFadNlMin": air.compressor_fad_nl_min(),
        "airNeedNlMin": air.required_fad_nl_min(),
        "airDemandKw": air.demand_kw(),
        "receiverL": air.receiver_l(),
        "dustFlowM3h": dust.counted_flow_m3h(),
        "airflowM3h": thermal.required_airflow_m3h(),
        "roomLoadKw": thermal.room_load_kw(),
        # 안전
        "hazards": len(safety.HAZARDS),
        "safetyFunctions": len(safety.SAFETY_FUNCTIONS),
        "plantPlr": safety.plant_plr(),
        "stopChainMs": safety.stop_chain_ms(),
        "stopBudgetMs": safety.tightest_opening().budget_ms,
        "safetyInputs": safety.summary()["inputs"],
        "fsoeNodes": safety.summary()["fsoeNodes"],
        # 소음
        "aisleDba": acoustics.worst_aisle_dba()[1],
        "nearDba": acoustics.worst_near_field_dba(),
        # 가동·검수
        "targetAvailability": reliability.TARGET_AVAILABILITY,
        "downtimeBudgetH": reliability.downtime_budget_h(),
        "annualPanels": reliability.annual_panels(),
        "nominalPanels": reliability.nominal_annual_panels(),
        "operatingHours": smart.OPERATING_HOURS_PER_YEAR,
        "acceptanceItems": len(acceptance.items()),
        "openAtHandover": len(acceptance.open_at_handover()),
        "unanchored": len(seismic.unanchored()),
    }


def cells() -> list[list[object]]:
    """셀 카드 — 3D 표지주와 같은 존 목록에서 나온다."""
    from pv_preprocess import layout
    out = []
    for zone in layout.build_zones():
        if zone.key == "gate":
            continue
        out.append([zone.key.upper(), zone.label,
                    round((zone.x1_mm - zone.x0_mm) / 1000, 2), zone.note])
    return out


def brand_block() -> str:
    """마크 — 도면과 **같은 문자열**을 쓴다. 시험이 그 동일성을 강제한다."""
    shapes = [[s.tag, s.colour, s.d] for s in brand.SHAPES]
    return (
        "  window.PV_BRAND = Object.freeze({\n"
        "    source: " + json.dumps(brand.SOURCE_FILE, ensure_ascii=False) + ",\n"
        "    viewW: " + repr(brand.VIEW_W) + ", viewH: " + repr(brand.VIEW_H) + ",\n"
        "    widthMm: " + repr(brand.WIDTH_MM) + ",\n"
        "    blue: " + json.dumps(brand.BLUE) + ", amber: " + json.dumps(brand.AMBER) + ",\n"
        "    shapes: Object.freeze(" + json.dumps(shapes, ensure_ascii=False)
        + ".map(Object.freeze))\n"
        "  });\n"
    )


def data_block() -> str:
    return (
        "  var CONSOLE = " + json.dumps(values(), ensure_ascii=False, indent=2)
        .replace("\n", "\n  ") + ";\n"
        "  var CELLS = " + json.dumps(cells(), ensure_ascii=False) + ";\n"
    )


def patch(text: str) -> str:
    """콘솔 파일의 두 블록을 갈아 끼운다. 두 번 돌려도 한 벌만 남는다."""
    for begin, end, block in (
        ("  /* @brand-begin */\n", "  /* @brand-end */\n", brand_block()),
        ("  /* @data-begin */\n", "  /* @data-end */\n", data_block()),
    ):
        i = text.index(begin) + len(begin)
        j = text.index(end)
        text = text[:i] + block + text[j:]
    return text


def main() -> None:
    src = CONSOLE.read_text(encoding="utf-8")
    out = patch(src)
    CONSOLE.write_text(out, encoding="utf-8")
    print(f"{CONSOLE} — 값 {len(values())}개 · 셀 {len(cells())}개 · 마크 {len(brand.SHAPES)}도형")


if __name__ == "__main__":
    main()
