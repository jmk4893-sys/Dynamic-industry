# -*- coding: utf-8 -*-
"""원본 아트워크를 대조용 PNG 로 래스터화한다.

`check_brand_fidelity.mjs` 가 이 그림을 기준으로 삼는다. ArtBox 만 잘라 내므로
여백이 끼지 않고, 추출 벡터의 viewBox 와 같은 틀이 된다.

실행:
    python tools/render_brand_reference.py <아트워크.ai|pdf> [출력.png] [폭px]
"""
import sys

import pymupdf

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "out/brand-reference.png"
width = int(sys.argv[3]) if len(sys.argv) > 3 else 1200

doc = pymupdf.open(src)
page = doc[0]
art = [float(v) for v in doc.xref_get_key(page.xref, "ArtBox")[1].strip("[] ").split()]
clip = pymupdf.Rect(*art)
zoom = width / (art[2] - art[0])
pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)
pix.save(out)
print(f"{out}  {pix.width} × {pix.height} px  (ArtBox {clip})", file=sys.stderr)
