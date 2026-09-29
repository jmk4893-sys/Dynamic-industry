"""제작 기준 요약 출력.

    PYTHONPATH=src python -m mp50_separator              # 화면에 출력
    PYTHONPATH=src python -m mp50_separator -o spec.md   # 파일로 저장

도면은 브라우저로 봐야 하지만, 발주 협의에서는 숫자만 빠르게 확인할 일이
많다. 그리고 텍스트로 뽑아 두면 기준치수를 고쳤을 때 무엇이 따라 움직였는지
diff 로 보인다.
"""

from __future__ import annotations

import argparse
import sys

from . import ASSEMBLIES, CONFLICTS, GEOMETRY as G, run_checks
from .components import dry_mass_kg, wet_mass_kg
from .geometry import COVER_NOZZLES, NOZZLES


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def report() -> str:
    L: list[str] = []
    L.append("# MP-50 제작 기준")
    L.append("")
    L.append("폐태양광 블랙파우더(31~75 µm)에서 EVA·백시트를 염수 밀도차로 걷어내는 "
             "소형 파일럿 장치. 이 문서는 `mp50_separator` 에서 자동 생성된다.")
    L.append("")
    L.append("## 기준좌표")
    L.append("")
    L.append("Z 원점은 원뿔의 가상 정점, θ 원점은 N1. 연구문서 Rev.0 이 따로 적어 둔 "
             "동체 상단 Z946 · 커버 상면 Z951 · 전용적 89.9 L 가 이 한 원점에서 "
             "동시에 맞는다.")
    L.append("")
    L += _table(["항목", "값"], [
        ["원뿔 가상 정점높이", f"{G.cone_apex_height_mm:.2f} mm"],
        ["원뿔대 높이", f"{G.cone_truncated_height_mm:.2f} mm (Ø{G.tank_id_mm:.0f} → Ø{G.cone_outlet_id_mm:.1f})"],
        ["동체", f"Z{G.shell_bottom_z:.2f} ~ Z{G.shell_top_z:.2f} · Ø{G.tank_id_mm:.0f} ID × t{G.shell_thickness_mm:.0f}"],
        ["커버 상면", f"Z{G.cover_top_z:.2f}"],
        ["전용적", f"{G.total_volume_l:.2f} L"],
        ["운전 액면", f"Z{G.operating_level_z:.0f} = {G.operating_volume_l:.1f} L"],
        ["운전 하한", f"Z{G.nominal_level_z:.1f} = {G.nominal_charge_l:.0f} L (스키머 도달 한계)"],
        ["프리보드", f"{G.freeboard_mm:.0f} mm"],
        ["동체 전개 길이", f"{G.shell_development_length_mm:.2f} mm (중립축)"],
        ["원뿔 전개", f"R{G.cone_development_outer_r_mm:.0f} / R{G.cone_development_inner_r_mm:.1f} × {G.cone_development_angle_deg:.0f}°"],
        ["설치 높이", f"프레임 H{G.frame_height_mm:.0f} · 배출면 {G.discharge_elevation_mm:.0f} · 전체 {G.overall_height_mm:.0f}"],
        ["질량", f"건조 {dry_mass_kg():.0f} kg · 운전 {wet_mass_kg():.0f} kg"],
    ])
    L.append("")
    L.append("## 아세이")
    L.append("")
    L += _table(["부호", "도면", "아세이", "품목", "개수", "질량 kg", "HOLD"],
                [[a.code, a.drawing, a.name, str(len(a.parts)), str(a.piece_count),
                  f"{a.total_kg:.1f}", str(len(a.held)) if a.held else "-"]
                 for a in ASSEMBLIES])
    L.append("")
    L.append("## 노즐")
    L.append("")
    L += _table(["번호", "용도", "규격", "θ", "표고 Z"],
                [[n.tag, n.service, n.size, f"{n.theta_deg:.0f}°", f"{n.z_mm:.0f}"]
                 for n in NOZZLES]
                + [[n.tag, n.service, n.size, f"{n.theta_deg:.0f}°", "커버면"]
                   for n in COVER_NOZZLES])
    L.append("")
    L.append("## 원본 치수 충돌")
    L.append("")
    L.append("[R] 연구문서 Rev.0 · [D1] MP-50-P0-001 · [D2] MP50-DR-000 의 치수가 "
             "서로 어긋난다. BLOCKING 은 그대로 두면 조립이 되지 않는 항목이다.")
    L.append("")
    L += _table(["번호", "항목", "등급", "채택값", "상태"],
                [[c.ref, c.item, c.severity, c.resolution,
                  "승인 필요" if c.approval == "PROPOSED" else "확정"] for c in CONFLICTS])
    L.append("")
    L.append("## 설계 검증")
    L.append("")
    L.append("**조립** 항목은 부품끼리 부딪히지 않는지를 본다 — 하나라도 FAIL 이면 "
             "발주할 수 없다. **기능** 항목의 WARN 은 장치가 아니라 운전조건·시험계획을 "
             "고치라는 뜻이다.")
    L.append("")
    L += _table(["번호", "구분", "항목", "결과", "판정"],
                [[c.ref, c.kind, c.item, c.value, c.verdict] for c in run_checks()])
    L.append("")
    for c in run_checks():
        if c.verdict != "PASS":
            L.append(f"### {c.ref} {c.item} — {c.verdict}")
            L.append("")
            L.append(c.detail)
            L.append("")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mp50-spec", description="MP-50 제작 기준 출력")
    ap.add_argument("-o", "--output", help="Markdown 저장 경로 (없으면 표준출력)")
    args = ap.parse_args(argv)
    text = report()
    if args.output:
        import pathlib

        path = pathlib.Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"작성 완료: {path}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
