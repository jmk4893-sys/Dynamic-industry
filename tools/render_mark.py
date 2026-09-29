#!/usr/bin/env python3
"""docs/brand/dg-mark.json 하나에서 마크 SVG 를 찍어 정적 문서에 심는다.

콘솔은 런타임에 같은 정의로 마크를 만들지만, 사양서는 스크립트가 없는 정적
문서라 도형이 마크업에 들어가야 한다. 손으로 옮겨 적으면 갈라지므로 여기서
기계적으로 생성하고, 시험이 원본과의 일치를 강제한다.

    python3 tools/render_mark.py            # 심어 넣기
    python3 tools/render_mark.py --check    # 갈라졌는지만 확인 (CI 용)
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARK = json.loads((ROOT / "docs" / "brand" / "dg-mark.json").read_text(encoding="utf-8"))
BEGIN, END = "<!--mark-->", "<!--/mark-->"

TARGETS = [(ROOT / "docs" / "dg-hk60-rfq.html", "      ")]


def body(indent):
    return "\n".join(f'{indent}<path d="{p["d"]}" fill="{p["fill"]}"/>' for p in MARK["paths"])


def block(indent):
    vw, vh = MARK["viewBox"][2], MARK["viewBox"][3]
    return (f'{indent}{BEGIN}\n{body(indent)}\n{indent}{END}',
            f'viewBox="0 0 {vw} {vh}"')


def apply(check=False):
    bad = []
    for path, indent in TARGETS:
        if not path.exists():
            continue          # 이 브랜치에는 해당 문서가 없다
        html = path.read_text(encoding="utf-8")
        want_block, want_vb = block(indent)
        m = re.search(r'<svg ([^>]*?)aria-label="DYNAMIC INDUSTRY"[^>]*>(.*?)</svg>', html, re.S)
        if m is None:
            bad.append(f"{path.name}: 마크 SVG 를 찾지 못했다")
            continue
        new_svg = f'<svg {want_vb} aria-label="DYNAMIC INDUSTRY" role="img">\n{want_block}\n    </svg>'
        out = html[:m.start()] + new_svg + html[m.end():]
        if out != html:
            if check:
                bad.append(f"{path.name}: 마크가 docs/brand/dg-mark.json 과 다르다")
            else:
                path.write_text(out, encoding="utf-8")
                print(f"갱신 {path.relative_to(ROOT)}")
        elif not check:
            print(f"동일 {path.relative_to(ROOT)}")
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(apply(check="--check" in sys.argv))
