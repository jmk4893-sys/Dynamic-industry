"""저장소 파일 → 아티팩트 파일. 기계적 변환만 한다.

저장소의 HTML 이 원본이고 아티팩트는 여기서 찍어낸 것이다. 두 벌을 따로
고치면 반드시 갈라지므로, 이 스크립트는 <title>·<style>·<body> 안쪽을
그대로 옮기고 그 밖의 어떤 내용도 만들거나 바꾸지 않는다.

    python3 mkart.py <저장소파일> <아티팩트파일> [표시제목]
"""
import re, sys, pathlib

src_path, out_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
src = src_path.read_text(encoding='utf-8')

style = re.search(r"(<style>.*?</style>)", src, re.S).group(1)
body  = re.search(r"<body[^>]*>(.*)</body>", src, re.S).group(1)
title = sys.argv[3] if len(sys.argv) > 3 else re.search(r"<title>(.*?)</title>", src, re.S).group(1)

out = f"<title>{title}</title>\n{style}\n{body}"
for bad in ('<!doctype', '<html', '</html>', '<head>', '</head>', '<body', '</body>'):
    assert bad not in out.lower(), bad
# 변환이 내용을 만들어내지 않았는지 — 본문은 원본에서 잘라온 그대로여야 한다
assert style in src and body in src, '변환이 원본을 바꿨다'
out_path.write_text(out, encoding='utf-8')
print(f"{src_path.name} → {out_path.name}  {len(out):,} bytes  제목 {title!r}")
