# -*- coding: utf-8 -*-
"""회사 심볼 마크를 원본 아트워크에서 추출하고, 추출 결과를 원본과 화소 대조한다.

    python3 docs/drawings/brand/extract-brand-mark.py            # 추출만
    python3 docs/drawings/brand/extract-brand-mark.py --verify   # 추출 + 화소 대조

`symbol_100x100mm.ai` 는 PDF 1.4 이므로 PDF 로 열어 **채움 패스와 채움색을 파일에서
직접 읽는다.** 눈으로 따라 그린 좌표가 아니다. 결과는 `brand-mark.json` 이고,
미니앱(`pv-recycling-miniapp.html`)의 `BRAND_MARK` 가 그 사본이다. 둘이 어긋나면
`tests/test_brand_mark.py` 가 실패한다.

의존성(개발 전용, 런타임 아님): pymupdf · numpy · pillow · playwright(--verify)
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ARTWORK = HERE / "symbol_100x100mm.ai"
OUT = HERE / "brand-mark.json"


def fmt(value):
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


def extract():
    import pymupdf

    page = pymupdf.open(ARTWORK)[0]
    drawings = page.get_drawings()
    bbox = None
    for group in drawings:
        bbox = group["rect"] if bbox is None else bbox | group["rect"]

    paths = []
    for group in drawings:
        parts, current = [], None
        for item in group["items"]:
            kind = item[0]
            if kind == "l":
                start, end = item[1], item[2]
                if current is None:
                    parts.append(f"M{fmt(start.x - bbox.x0)},{fmt(start.y - bbox.y0)}")
                parts.append(f"L{fmt(end.x - bbox.x0)},{fmt(end.y - bbox.y0)}")
                current = end
            elif kind == "c":
                start, c1, c2, end = item[1], item[2], item[3], item[4]
                if current is None:
                    parts.append(f"M{fmt(start.x - bbox.x0)},{fmt(start.y - bbox.y0)}")
                parts.append("C" + ",".join(fmt(v) for v in (
                    c1.x - bbox.x0, c1.y - bbox.y0, c2.x - bbox.x0, c2.y - bbox.y0,
                    end.x - bbox.x0, end.y - bbox.y0)))
                current = end
            else:                                     # 원본은 M·L·C·Z 만 쓴다
                raise SystemExit("지원하지 않는 세그먼트: " + kind)
        parts.append("Z")
        rgb = tuple(round(c * 255) for c in group["fill"])
        paths.append({"d": "".join(parts), "fill": "#%02X%02X%02X" % rgb})

    return {
        "viewBox": [0, 0, round(bbox.width, 4), round(bbox.height, 4)],
        "pageBBox": [round(bbox.x0, 4), round(bbox.y0, 4), round(bbox.x1, 4), round(bbox.y1, 4)],
        "paths": paths,
    }


def verify(mark, scale=8):
    """추출 벡터를 SVG 로 써서 Chromium 으로 다시 래스터화하고 원본 렌더와 대조.

    렌더러가 서로 다르므로(MuPDF vs Skia) 경계 화소의 안티앨리어싱은 일치하지
    않는다. 그래서 **경계에서 떨어진 곳의 불일치가 0 인지**를 형상 일치의 판정으로
    삼고, 면적 IoU 를 함께 낸다.
    """
    import numpy as np
    import pymupdf
    from PIL import Image, ImageFilter

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="brand-mark-"))
    page = pymupdf.open(ARTWORK)[0]
    x0, y0, x1, y1 = mark["pageBBox"]
    pix = page.get_pixmap(clip=pymupdf.Rect(x0, y0, x1, y1),
                          matrix=pymupdf.Matrix(scale, scale), alpha=False)
    pix.save(tmp / "orig.png")
    ix0, iy0, ix1, iy1 = pix.irect
    view = [ix0 / scale - x0, iy0 / scale - y0, (ix1 - ix0) / scale, (iy1 - iy0) / scale]

    body = "".join(f'<path d="{p["d"]}" fill="{p["fill"]}"/>' for p in mark["paths"])
    (tmp / "svg.html").write_text(
        '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#fff}'
        'svg{display:block}</style>'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{pix.width}" height="{pix.height}" '
        f'viewBox="{" ".join(f"{v:.5f}" for v in view)}">{body}</svg>', encoding="utf-8")

    launch = "{}"
    if os.environ.get("BRAND_VERIFY_CHROMIUM"):
        launch = "{ executablePath: process.env.BRAND_VERIFY_CHROMIUM }"
    # ESM 은 NODE_PATH 를 무시하므로, 스크립트를 node_modules 가 있는 디렉터리에 쓴다.
    modules = os.environ.get("BRAND_VERIFY_NODE_PATH")
    if not modules:
        for base in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]:
            if (base / "node_modules" / "playwright").exists():
                modules = str(base / "node_modules")
                break
    if not modules:
        raise SystemExit("playwright 를 찾지 못했다 — BRAND_VERIFY_NODE_PATH 로 node_modules 경로를 지정하라")
    host = pathlib.Path(modules).parent
    script = host / "_brand-mark-shot.mjs"
    script.write_text(
        "import { chromium } from 'playwright';\n"
        f"const b = await chromium.launch({launch});\n"
        f"const ctx = await b.newContext({{ viewport: {{ width: {pix.width}, height: {pix.height} }}, deviceScaleFactor: 1 }});\n"
        "const p = await ctx.newPage();\n"
        f"await p.goto('file://{tmp / 'svg.html'}', {{ waitUntil: 'load' }});\n"
        "await p.waitForTimeout(500);\n"
        f"await p.screenshot({{ path: '{tmp / 'svg.png'}' }});\n"
        "await b.close();\n", encoding="utf-8")
    subprocess.run(["node", str(script)], check=True, cwd=str(host))  # noqa: S603
    script.unlink(missing_ok=True)

    a = np.asarray(Image.open(tmp / "orig.png").convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(tmp / "svg.png").convert("RGB")).astype(np.int16)
    delta = np.abs(a - b).max(axis=2)
    edges = np.asarray(Image.open(tmp / "orig.png").convert("L")
                       .filter(ImageFilter.FIND_EDGES)) > 8

    def dilate(mask, radius):
        image = Image.fromarray((mask * 255).astype("uint8"))
        return np.asarray(image.filter(ImageFilter.MaxFilter(2 * radius + 1))) > 0

    def area_iou(rgb, tol=40):
        ma = np.abs(a - np.array(rgb)).max(axis=2) <= tol
        mb = np.abs(b - np.array(rgb)).max(axis=2) <= tol
        return float((ma & mb).sum() / (ma | mb).sum())

    ink_a = np.abs(a - 255).max(axis=2) > 24
    ink_b = np.abs(b - 255).max(axis=2) > 24
    bad = delta > 16
    return {
        "raster": [pix.width, pix.height],
        "inkAreaIoU": round(float((ink_a & ink_b).sum() / (ink_a | ink_b).sum()), 5),
        "blueIoU": round(area_iou((35, 140, 202)), 5),
        "amberIoU": round(area_iou((255, 202, 74)), 5),
        "pixelsWithinTolerance2of255": round(float((delta <= 2).sum() / delta.size), 6),
        "meanAbsErrorPerChannel": round(float(np.abs(a - b).mean()), 4),
        "rmse": round(float(np.sqrt(((a - b) ** 2).mean())), 4),
        "mismatchedPixelsBeyond16": int(bad.sum()),
        "mismatchedPixelsAwayFromEdges": int((bad & ~dilate(edges, 1)).sum()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="추출 결과를 원본과 화소 대조")
    args = parser.parse_args()

    mark = extract()
    payload = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    payload["_"] = "회사 심볼 마크 — 유일 정의(single source of truth)."
    payload.setdefault("provenance", {})
    payload["provenance"]["artwork"] = ARTWORK.name + " (PDF 1.4 · 1 page · artbox 100 mm 폭)"
    payload["provenance"]["extraction"] = (
        "PyMuPDF page.get_drawings() 로 채움 패스와 채움색을 파일에서 직접 읽었다. "
        "재현: python3 docs/drawings/brand/extract-brand-mark.py --verify")
    payload["viewBox"] = mark["viewBox"]
    payload["pageBBox"] = mark["pageBBox"]
    payload["paths"] = mark["paths"]
    payload["colors"] = {"blue": mark["paths"][0]["fill"], "amber": mark["paths"][-1]["fill"]}
    if args.verify:
        payload["provenance"]["match"] = verify(mark)
        print(json.dumps(payload["provenance"]["match"], indent=1, ensure_ascii=False))
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
