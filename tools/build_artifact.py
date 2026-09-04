# -*- coding: utf-8 -*-
"""저장소의 HTML 산출물을 아티팩트 본문으로 **기계 변환**한다.

두 벌을 따로 관리하면 반드시 갈라진다. 그래서 아티팩트는 손으로 쓰지 않고
저장소 파일에서 찍어 낸다 — 고칠 일이 생기면 **저장소 파일을 고치고 이것을
다시 돌린 뒤 같은 URL 로 재발행**하는 순서다.

아티팩트 호스트는 본문을 `<!doctype html><head>…</head><body>` 로 감싸므로
문서 골격 태그를 벗겨야 한다. `<title>` 과 `<style>` 은 본문 맨 앞에 남긴다.
이름은 **저장소 파일의 `<title>` 이 그대로 아티팩트 이름**이 된다 — 변환기가
새 이름을 지어내면 그것이 또 하나의 관리 대상이 된다.

실행 (저장소 루트에서):
    python tools/build_artifact.py            # 전부
    python tools/build_artifact.py console    # 하나만
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

#: 변환 대상 — 저장소 원본 → 아티팩트 본문.
TARGETS: dict[str, tuple[pathlib.Path, pathlib.Path]] = {
    "console": (pathlib.Path("docs/consoles/pv-preprocess-console.html"),
                pathlib.Path("out/pv-preprocess-console-artifact.html")),
    "plant": (pathlib.Path("docs/drawings/pv-preprocess-plant.html"),
              pathlib.Path("out/pv-preprocess-plant-artifact.html")),
}

#: 태그 이름 **뒤에 경계가 와야** 지운다. `[^>]*` 만 쓰면 이름으로 시작하는 다른
#: 것까지 먹는다 — 실제로 three.js 셰이더의 `#include <metalnessmap_fragment>` 두
#: 줄이 `<meta…>` 로 잡혀 지워졌고, 표준 재질이 컴파일되지 않아 발행본에서 3D 가
#: 통째로 안 나왔다. `<header>` 도 `<head…>` 로 잡혀 사라졌다.
_BOUND = r"(?=[\s/>])"
STRIP_HEAD_TAGS = (
    re.compile(r"<!doctype\s+html\s*>\s*", re.I),
    re.compile(r"</?html" + _BOUND + r"[^>]*>\s*", re.I),
    re.compile(r"</?head" + _BOUND + r"[^>]*>\s*", re.I),
    re.compile(r"</?body" + _BOUND + r"[^>]*>\s*", re.I),
    # charset·viewport·CSP·referrer 는 호스트 head 가 갖는다 — 본문에 두면 무시되거나 충돌한다
    re.compile(r"<meta" + _BOUND + r"[^>]*>\s*", re.I),
)

#: 벗겨졌는지 스스로 확인하는 안전망. 여기서도 같은 경계를 요구해야 `<header>` 를
#: 골격 태그로 오인하지 않는다.
FORBIDDEN = (
    re.compile(r"<!doctype\s+html", re.I),
    re.compile(r"</?html" + _BOUND, re.I),
    re.compile(r"</?head" + _BOUND, re.I),
    re.compile(r"</?body" + _BOUND, re.I),
)

#: 실제로 무언가를 **받아 오는 자리**만 본다. 주소처럼 생긴 글자를 전부 잡으면
#: 주석에 적어 둔 근거 링크나 라이브러리의 안내 문장에 걸려 넘어진다 — 그것은
#: 요청이 아니라 사람이 읽는 문장이다. XML 네임스페이스(`http://www.w3.org/2000/svg`)
#: 도 식별자일 뿐이라 애초에 이 자리들에 나타나지 않는다.
FETCHING = (
    re.compile(r"""\b(?:src|href)\s*=\s*["']?\s*(https?:)?//""", re.I),   # <script>·<link>·<img>
    re.compile(r"""url\(\s*["']?\s*(https?:)?//""", re.I),                # CSS url()
    re.compile(r"""@import\s+["']?\s*(https?:)?//""", re.I),              # CSS @import
    re.compile(r"""\b(?:fetch|importScripts|Worker)\s*\(\s*["'`]\s*(https?:)?//""", re.I),
)


def head_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def convert(text: str, src: pathlib.Path) -> str:
    out = text
    for pat in STRIP_HEAD_TAGS:
        out = pat.sub("", out)
    out = out.lstrip()

    if not re.search(r"<title>(.*?)</title>", out, re.S):
        raise SystemExit(f"✗ {src}: <title> 이 없다 — 아티팩트 이름이 파일명으로 떨어진다")

    out = (
        "<!-- 이 파일은 손으로 쓰지 않는다.\n"
        f"     원본  : {src}\n"
        f"     변환  : tools/build_artifact.py (head {head_commit()})\n"
        "     고칠 때는 원본을 고치고 이것을 다시 돌린 뒤 같은 URL 로 재발행한다. -->\n"
    ) + out

    for bad in FORBIDDEN:
        hit = bad.search(out)
        if hit:
            raise SystemExit(f"✗ {src}: 골격 태그가 남았다 — {hit.group(0)!r}")
    for pat in FETCHING:
        hit = pat.search(out)
        if hit:
            where = out[max(0, hit.start() - 40):hit.end() + 60].replace("\n", " ")
            raise SystemExit(f"✗ {src}: 외부에서 받아 오는 자리가 있다 — …{where}…")

    # 벗기기는 **골격만** 벗겨야 한다. 태그 이름으로 시작하는 다른 것까지 먹으면
    # (셰이더 include·`<header>`) 본문이 조용히 망가진 채 발행된다. 그래서 남은
    # 태그와 셰이더 지시자의 개수가 원본 그대로인지 센다.
    for name, pat in (("<header>", r"<header[\s/>]"), ("</header>", r"</header\s*>"),
                      ("#include", r"#include\s*<")):
        before = len(re.findall(pat, text, re.I))
        after = len(re.findall(pat, out, re.I))
        if before != after:
            raise SystemExit(
                f"✗ {src}: 골격이 아닌 것을 지웠다 — {name} {before} → {after}")
    return out


def build(name: str) -> pathlib.Path:
    src, dest = TARGETS[name]
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = convert(src.read_text(encoding="utf-8"), src)
    dest.write_text(out, encoding="utf-8")
    kb = len(out.encode("utf-8")) / 1024
    size = f"{kb / 1024:.2f} MB" if kb > 1024 else f"{kb:.1f} kB"
    print(f"{dest}  {size}  (원본 {src}, head {head_commit()})")
    return dest


def main() -> None:
    names = sys.argv[1:] or list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        raise SystemExit(f"✗ 모르는 대상: {unknown} — 아는 것은 {list(TARGETS)}")
    for name in names:
        build(name)


if __name__ == "__main__":
    main()
