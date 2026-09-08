# -*- coding: utf-8 -*-
"""통합 설계도에 **손으로 넣은 두 곳**을 다시 얹는다 — 병합 뒤에 쓴다.

이 저장소의 도면은 생성기가 찍지만, 통합 설계도 본체에는 손으로 넣은 자리가
둘 있다. 베이스 브랜치에는 없는 것들이라 병합 때 생성물 충돌을 `--theirs` 로
받으면 **매번 같이 지워진다.** 세 번 연속 손으로 다시 넣었고, 한 번이라도
잊으면 AFR 이 통째로 안 움직이거나 부품 확대도가 형상을 못 그린다 — 둘 다
글자에는 흔적이 없는 종류다.

그래서 절차를 도구로 만든다. 멱등이라 몇 번을 돌려도 같고, 이미 들어 있으면
"이미 있음" 으로 지나간다. 앵커가 사라졌으면 조용히 넘어가지 않고 멈춘다.

    python tools/patch_plant.py          # 얹는다
    python tools/patch_plant.py --check  # 얹혀 있는지 보기만 한다 (CI·시험용)

병합 절차: 충돌한 생성물을 `--theirs` 로 받은 뒤 이것을 돌리고, 그다음
`build_literals` → `build_afr` → `build_casing` → `build_*_scene` 순으로 찍는다.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"

#: ① 구조 레시피 표를 창에 올린다. 이 스크립트는 IIFE 라 `var` 가 전역이 되지
#: 않아 3D 의 `pvStructure()` 가 표를 못 읽었다 (REV.51 결함).
RECIPES_ANCHOR = "var STRUCTURE_RECIPES = ["
RECIPES_END = "\n  ];\n"
RECIPES_PATCH = "  /* 이 표는 3D 모듈도 읽는다 (`pvStructure()`). 이 스크립트는 IIFE 라 `var` 가\n     전역이 되지 않으므로 창에 명시로 올린다 — REV.51 에서 이것이 빠져 있어\n     구조 레시피가 늘 '미등록'으로 읽혔고, 그 탓에 JBR 허가검사의\n     structure_recipe_ok 가 항상 거짓이라 AFR-101 이 한 단계도 움직이지 않았다\n     (JBR 은 pvMode() 가 늘 'recipe' 리젝트로 고정됐다). */\n  window.STRUCTURE_RECIPES = STRUCTURE_RECIPES;\n"

#: ② 파생 도면이 **같은 재질·같은 조명**으로 형상을 더 그릴 수 있게 3D 연장을
#: 내준다. 부품 확대도(AFR·SG)가 이것으로 그린다.
HOOK_TAIL = ",zone:pvZone});"
#: 앵커의 `zone:pvZone` 은 **남겨야 한다** — 파생 도면이 존 범위를 그것으로
#: 읽는다. 처음 이 도구를 쓸 때 앵커째 갈아 끼워 조용히 지웠고, 손으로 하던
#: 결과와 바이트로 견주는 시험이 그것을 잡았다.
HOOK_PATCH = ",zone:pvZone" + ',/* 파생 도면이 **같은 재질·같은 조명**으로 형상을 더 그릴 수 있게 내주는 연장.\n   부품 확대도(tools/build_afr_closeup.py)가 이것으로 실린더 글랜드와 LM 볼\n   순환로까지 그린다 — 플랜트 축척에서는 그릴 이유가 없는 것들이다. */\nkit:Object.freeze({P:P,Ee:Ee,bt:bt,M:M,SC:SC,F:F,Mesh:et,Box:Wn,Cyl:_n,Geo:an,Attr:on,Std:Tt,DoubleSide:bn,pick:Ns})' + "});"


def apply(text: str) -> tuple[str, list[str]]:
    """두 곳을 얹고, 무엇을 했는지 돌려준다. 앵커가 없으면 멈춘다."""
    done: list[str] = []

    if RECIPES_PATCH in text:
        done.append("① 구조 레시피 창 노출 — 이미 있음")
    else:
        i = text.find(RECIPES_ANCHOR)
        if i < 0:
            raise SystemExit(f"✗ ① 앵커가 없다: {RECIPES_ANCHOR}")
        e = text.find(RECIPES_END, i)
        if e < 0:
            raise SystemExit("✗ ① 표의 끝(`\\n  ];`)을 못 찾았다")
        e += len(RECIPES_END)
        text = text[:e] + RECIPES_PATCH + text[e:]
        done.append("① 구조 레시피 창 노출 — 얹음")

    if "kit:Object.freeze" in text:
        done.append("② 파생 도면용 3D 연장 kit — 이미 있음")
    else:
        n = text.count(HOOK_TAIL)
        if n != 1:
            raise SystemExit(f"✗ ② 앵커가 {n}곳 — 1곳이어야 한다: {HOOK_TAIL}")
        text = text.replace(HOOK_TAIL, HOOK_PATCH)
        done.append("② 파생 도면용 3D 연장 kit — 얹음")

    return text, done


def main() -> int:
    check = "--check" in sys.argv
    text = PLANT.read_text(encoding="utf-8")
    out, done = apply(text)
    if check:
        missing = [d for d in done if d.endswith("얹음")]
        for d in done:
            print(("  ✗ " if d.endswith("얹음") else "  ✓ ") + d)
        if missing:
            print("\n✗ 손패치가 빠졌다 — python tools/patch_plant.py 를 돌릴 것")
            return 1
        print("\n✓ 손패치 둘이 다 얹혀 있다")
        return 0
    for d in done:
        print("  " + d)
    if out != text:
        PLANT.write_text(out, encoding="utf-8")
        print(f"{PLANT.relative_to(ROOT)} 갱신")
    else:
        print("변경 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
