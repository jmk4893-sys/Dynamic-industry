"""CLI: 설계 계산서를 표준출력 또는 파일로 출력.

    python -m flotation_design                 # 표준출력
    python -m flotation_design -o docs/x.md    # 파일로 저장
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from .report import build_design, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flotation_design", description=__doc__)
    parser.add_argument("-o", "--output", type=pathlib.Path, help="출력 파일 경로 (.md)")
    parser.add_argument(
        "--average-tph", type=float, default=None, help="평균 처리량 재정의 (t/h)"
    )
    parser.add_argument("--peak-tph", type=float, default=None, help="최대 처리량 재정의 (t/h)")
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

    text = render(build_design(feed))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"작성 완료: {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
