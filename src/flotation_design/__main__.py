"""CLI: 회로 설계 계산서를 표준출력 또는 파일로 출력.

패키지가 src 레이아웃이므로 설치 없이 쓰려면 PYTHONPATH 를 지정한다.

    PYTHONPATH=src python -m flotation_design               # 표준출력
    PYTHONPATH=src python -m flotation_design -o docs/x.md  # 파일로 저장

`pip install -e .` 로 설치했다면 PYTHONPATH 없이 `flotation-design` 으로
실행할 수 있다.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from .report import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flotation_design", description=__doc__)
    parser.add_argument("-o", "--output", type=pathlib.Path, help="출력 파일 경로 (.md)")
    parser.add_argument(
        "--average-tph",
        type=float,
        default=None,
        help="평균 처리량 재정의 (t/h). RFC와 탈수 보조설비는 새 처리량으로 "
        "재산정하고, 기계식 셀 동체는 design_basis.py의 확정 치수를 사용한다.",
    )
    parser.add_argument(
        "--peak-tph",
        type=float,
        default=None,
        help="최대 처리량 재정의 (t/h). RFC와 탈수 보조설비는 재산정한다. "
        "기계식 확정 셀이 목표 체류시간에 미달하면 계산서에 경고한다.",
    )
    args = parser.parse_args(argv)

    from dataclasses import replace

    from . import design_basis as db

    feed = db.FEED
    if args.average_tph is not None or args.peak_tph is not None:
        feed = replace(
            feed,
            average_tph=args.average_tph if args.average_tph is not None else feed.average_tph,
            peak_tph=args.peak_tph if args.peak_tph is not None else feed.peak_tph,
        )

    from .plant import build_plant

    text = render(build_plant(feed))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"작성 완료: {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
