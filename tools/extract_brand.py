# -*- coding: utf-8 -*-
"""symbol_100x100mm.ai 에서 도형과 색을 직접 뽑는다 — 눈으로 따라 그리지 않는다.

AI 파일은 PDF 1.4 컨테이너라 콘텐츠 스트림을 그대로 읽을 수 있다. 연산자를
해석해 절대좌표 경로를 만들고, PDF 좌표계(y 위)를 SVG 좌표계(y 아래)로 뒤집고,
ArtBox 를 기준으로 0…100 정규화한다.

실행:
    python -m pip install pymupdf
    python tools/extract_brand.py <아트워크.ai|pdf> [출력.json]

출력 JSON 이 `src/pv_preprocess/brand.py` 의 `d` 문자열과 색의 출처다. 아트워크가
바뀌면 이것을 다시 돌리고, brand.py 를 손으로 고치지 않는다.
"""
import json, os, re, sys

import pymupdf

AI = sys.argv[1] if len(sys.argv) > 1 else os.environ["AI"]
OUT_JSON = sys.argv[2] if len(sys.argv) > 2 else "brand-extracted.json"

doc = pymupdf.open(AI)
page = doc[0]
art = [float(v) for v in doc.xref_get_key(page.xref, "ArtBox")[1].strip('[] ').split()]
ax0, ay0, ax1, ay1 = art
W, H = ax1 - ax0, ay1 - ay0

stream = page.read_contents().decode('latin-1')
tok = re.findall(r'-?\d+\.?\d*|/[A-Za-z0-9]+|[a-zA-Z*]+', stream)

paths, stack, ctm = [], [], (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
cur, start, seq, colour = None, None, [], None
nums = []


def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


i = 0
while i < len(tok):
    t = tok[i]
    if re.fullmatch(r'-?\d+\.?\d*', t):
        nums.append(float(t))
        i += 1
        continue
    if t == 'q':
        stack.append(ctm)
    elif t == 'Q':
        ctm = stack.pop() if stack else (1, 0, 0, 1, 0, 0)
    elif t == 'cm':
        a, b, c, d, e, f = nums[-6:]
        A, B, C, D, E, F = ctm
        ctm = (a * A + b * C, a * B + b * D, c * A + d * C,
               c * B + d * D, e * A + f * C + E, e * B + f * D + F)
    elif t == 'scn':
        colour = tuple(nums[-4:]) if len(nums) >= 4 else tuple(nums)
    elif t == 'm':
        cur = apply(ctm, nums[-2], nums[-1])
        start = cur
        seq.append(('M', cur))
    elif t == 'l':
        cur = apply(ctm, nums[-2], nums[-1])
        seq.append(('L', cur))
    elif t == 'c':
        p1 = apply(ctm, nums[-6], nums[-5])
        p2 = apply(ctm, nums[-4], nums[-3])
        p3 = apply(ctm, nums[-2], nums[-1])
        seq.append(('C', p1, p2, p3))
        cur = p3
    elif t == 'h':
        seq.append(('Z',))
        cur = start
    elif t in ('f', 'f*', 'F'):
        if seq:
            paths.append({'cmyk': colour, 'seq': seq, 'rule': 'evenodd' if t == 'f*' else 'nonzero'})
        seq = []
    elif t == 're':
        pass  # 클립용 사각형 — 도형이 아니다
    if t not in ('W', 'n'):
        nums = []
    i += 1

# PDF(y 위) → SVG(y 아래), ArtBox 기준 0…100 정규화
S = 100.0 / W


def nx(x):
    return round((x - ax0) * S, 4)


def ny(y):
    return round((ay1 - y) * S, 4)


def to_d(seq):
    out = []
    for it in seq:
        if it[0] == 'M':
            out.append(f"M{nx(it[1][0])} {ny(it[1][1])}")
        elif it[0] == 'L':
            out.append(f"L{nx(it[1][0])} {ny(it[1][1])}")
        elif it[0] == 'C':
            out.append("C{} {} {} {} {} {}".format(
                nx(it[1][0]), ny(it[1][1]), nx(it[2][0]), ny(it[2][1]),
                nx(it[3][0]), ny(it[3][1])))
        elif it[0] == 'Z':
            out.append("Z")
    d = "".join(out)
    return d if d.endswith("Z") else d + "Z"


result = {
    'artbox_pt': art,
    'width_mm': round(W / 72 * 25.4, 4),
    'height_mm': round(H / 72 * 25.4, 4),
    'view_w': 100.0,
    'view_h': round(H * S, 4),
    'paths': [{'cmyk': p['cmyk'], 'rule': p['rule'], 'd': to_d(p['seq'])} for p in paths],
}
print(json.dumps(result, ensure_ascii=False, indent=1))
with open(OUT_JSON, "w") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=1)
print(f"→ {OUT_JSON}", file=sys.stderr)
