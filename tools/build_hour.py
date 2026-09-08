# -*- coding: utf-8 -*-
"""60분 연속 운전 화면의 값 블록을 파이썬 모델에서 찍는다.

`docs/consoles/pv-preprocess-hour.html` 은 화면 구성만 사람이 쓰고, 장비 시간표와
60분 궤적은 `pv_preprocess.continuous` 가 만든 것을 그대로 받는다. 화면에서 본
병목이 모델의 병목과 다를 수 없어야 하기 때문이다 — 시험이 그 동일성을 강제한다.

실행 (저장소 루트에서):
    PYTHONPATH=src python tools/build_hour.py
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "src")

from pv_preprocess import (brand, campaign, continuous, handoff,  # noqa: E402
                           hk60c, line)

PAGE = pathlib.Path("docs/consoles/pv-preprocess-hour.html")

#: 화면에 그리는 운전 — 계획 정지 하나를 창 한가운데에 넣어 **버퍼가 그것을 덮는지**
#: 눈으로 보이게 한다. 주기는 아직 값이 없다(OI-12)므로 한 번만 넣는다.
SWAP_AT_MIN = 30.0


def equipment() -> list[dict[str, object]]:
    return [{"tag": e.tag, "name": e.name, "hold": round(e.hold_s, 2),
             "share": round(e.share, 4), "perPanel": e.per_panel_s,
             "serial": e.serial, "parent": e.parent, "source": e.source}
            for e in continuous.equipment()]


def values() -> dict[str, object]:
    run = continuous.run(swap_at_min=SWAP_AT_MIN)
    clean = continuous.run()
    b = continuous.bottleneck()
    return {
        "windowMin": run.minutes,
        "taktS": continuous.takt_s(),
        "bottleneck": b.tag,
        "bottleneckName": b.name,
        "bottleneckS": b.per_panel_s,
        "bottleneckUse": continuous.bottleneck_utilisation(),
        "unbroken": bool(continuous.flow_is_unbroken() and run.unbroken),
        "breaks": list(run.breaks),
        "released": run.released,
        "scrapped": run.scrapped,
        "toBuffer": run.to_buffer,
        "glassOut": run.glass_out,
        "glassOutNoStop": clean.glass_out,
        "glassPerH": run.glass_per_h,
        "cellEvaKg": run.cell_eva_kg,
        "cellEvaKgPerSheet": hk60c.CELL_EVA_KG,
        "glassKgPerSheet": hk60c.GLASS_KG,
        "bufferPeak": run.buffer_peak,
        "bufferEnd": run.buffer_end,
        "bufferSlots": handoff.BUFFER_RA_SLOTS,
        "bufferSetpoint": handoff.buffer_stock_target_slots(),
        "swapS": continuous.KNIFE_SWAP_S,
        "swapAbsorbMin": continuous.swap_interval_the_machine_absorbs_min(),
        "swapCover10Min": continuous.buffer_covers_swaps_h(10.0),
        "machineIdleSPerH": continuous.steady_state_machine_idle_s_per_h(),
        "machineCycleS": round(3600.0 / line.downstream_rate().line_per_h, 2),
        "capacityPerH": line.downstream_rate().line_per_h,
        "fedPerH": handoff.sheet_glass_per_h(),
        "panelMm": list(line.LINE_MAX_MM),
        "normalRatio": round(campaign.normal_ratio(), 4),
        "headroom": [[tag, gap] for tag, gap in continuous.headroom_s()],
    }


def slices() -> list[dict[str, object]]:
    run = continuous.run(swap_at_min=SWAP_AT_MIN)
    return [{"tag": s.tag, "name": s.name, "panels": s.panels, "busy": s.busy_s,
             "blocked": s.blocked_s, "starved": s.starved_s, "use": s.utilisation}
            for s in run.slices]


def spans() -> list[list[object]]:
    run = continuous.run(swap_at_min=SWAP_AT_MIN)
    return [[tag, start, end, panel, kind] for tag, start, end, panel, kind in run.spans]


def buffer_trace() -> list[list[float]]:
    run = continuous.run(swap_at_min=SWAP_AT_MIN)
    return [[at, level] for at, level in run.buffer_trace]


def brand_block() -> str:
    """마크 — 도면·콘솔과 **같은 문자열**이다."""
    shapes = [[s.tag, s.colour, s.d] for s in brand.SHAPES]
    return (
        "  window.PV_BRAND = Object.freeze({\n"
        "    source: " + json.dumps(brand.SOURCE_FILE, ensure_ascii=False) + ",\n"
        "    viewW: " + repr(brand.VIEW_W) + ", viewH: " + repr(brand.VIEW_H) + ",\n"
        "    blue: " + json.dumps(brand.BLUE) + ", amber: " + json.dumps(brand.AMBER) + ",\n"
        "    shapes: Object.freeze(" + json.dumps(shapes, ensure_ascii=False)
        + ".map(Object.freeze))\n"
        "  });\n"
    )


def data_block() -> str:
    return (
        "  var HOUR = " + json.dumps(values(), ensure_ascii=False, indent=2)
        .replace("\n", "\n  ") + ";\n"
        "  var EQUIPMENT = " + json.dumps(equipment(), ensure_ascii=False) + ";\n"
        "  var SLICES = " + json.dumps(slices(), ensure_ascii=False) + ";\n"
        "  var SPANS = " + json.dumps(spans(), ensure_ascii=False) + ";\n"
        "  var STOCK = " + json.dumps(buffer_trace(), ensure_ascii=False) + ";\n"
    )


def patch(text: str) -> str:
    for begin, end, block in (
        ("  /* @brand-begin */\n", "  /* @brand-end */\n", brand_block()),
        ("  /* @data-begin */\n", "  /* @data-end */\n", data_block()),
    ):
        i = text.index(begin) + len(begin)
        j = text.index(end)
        text = text[:i] + block + text[j:]
    return text


def main() -> None:
    PAGE.write_text(patch(PAGE.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"{PAGE} — 장비 {len(equipment())} · 구간 {len(spans())} · 재고점 "
          f"{len(buffer_trace())} · 값 {len(values())}")


if __name__ == "__main__":
    main()
