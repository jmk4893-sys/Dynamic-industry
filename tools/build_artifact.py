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
    "infeed": (pathlib.Path("docs/drawings/pv-infeed-detail.html"),
               pathlib.Path("out/pv-infeed-detail-artifact.html")),
    "infeed-sim": (pathlib.Path("docs/drawings/pv-infeed-sim.html"),
                   pathlib.Path("out/pv-infeed-sim-artifact.html")),
    "infeed-scene": (pathlib.Path("docs/drawings/pv-infeed-scene.html"),
                     pathlib.Path("out/pv-infeed-scene-artifact.html")),
    "infeed-fab": (pathlib.Path("docs/drawings/pv-infeed-fab.html"),
                   pathlib.Path("out/pv-infeed-fab-artifact.html")),
    "infeed-dyn": (pathlib.Path("docs/drawings/pv-infeed-dyn.html"),
                   pathlib.Path("out/pv-infeed-dyn-artifact.html")),
    "prototype": (pathlib.Path("docs/drawings/pv-bfc-prototype.html"),
                  pathlib.Path("out/pv-bfc-prototype-artifact.html")),
    "decisions": (pathlib.Path("docs/drawings/pv-infeed-decisions.html"),
                  pathlib.Path("out/pv-infeed-decisions-artifact.html")),
    "jbr-scene": (pathlib.Path("docs/drawings/pv-jbr-scene.html"),
                  pathlib.Path("out/pv-jbr-scene-artifact.html")),
    "jbr-detail": (pathlib.Path("docs/drawings/pv-jbr-detail.html"),
                   pathlib.Path("out/pv-jbr-detail-artifact.html")),
    "jbr-closeup": (pathlib.Path("docs/drawings/pv-jbr-closeup.html"),
                    pathlib.Path("out/pv-jbr-closeup-artifact.html")),
    "jbr-fab": (pathlib.Path("docs/drawings/pv-jbr-fab.html"),
                pathlib.Path("out/pv-jbr-fab-artifact.html")),
    "jbr-hub": (pathlib.Path("docs/drawings/pv-jbr-hub.html"),
                pathlib.Path("out/pv-jbr-hub-artifact.html")),
    "jbr-physics": (pathlib.Path("docs/drawings/pv-jbr-physics.html"),
                    pathlib.Path("out/pv-jbr-physics-artifact.html")),
    "afr-scene": (pathlib.Path("docs/drawings/pv-afr-scene.html"),
                  pathlib.Path("out/pv-afr-scene-artifact.html")),
    "afr-closeup": (pathlib.Path("docs/drawings/pv-afr-closeup.html"),
                    pathlib.Path("out/pv-afr-closeup-artifact.html")),
    "sg-closeup": (pathlib.Path("docs/drawings/pv-sg-closeup.html"),
                   pathlib.Path("out/pv-sg-closeup-artifact.html")),
    "gi-closeup": (pathlib.Path("docs/drawings/pv-gi-closeup.html"),
                   pathlib.Path("out/pv-gi-closeup-artifact.html")),
    # 위 넷을 한 장에 담은 후단 도면집 — 링크 하나·판번 하나로 묶는다.
    "afr-hub": (pathlib.Path("docs/drawings/pv-afr-hub.html"),
                pathlib.Path("out/pv-afr-hub-artifact.html")),

    "fasteners": (pathlib.Path("docs/drawings/pv-fastener-book.html"),
                  pathlib.Path("out/pv-fastener-book-artifact.html")),
    "assembly-steps": (pathlib.Path("docs/drawings/pv-assembly-steps.html"),
                       pathlib.Path("out/pv-assembly-steps-artifact.html")),
    # 후단 인계 균형 두 안 — `tools/build_handoff_variants.py` 가 원본을 복사해
    # 고친 것이라 저장소에 커밋되지 않는다(out/ 은 무시된다). 그래도 **아티팩트를
    # 손으로 만들지 않는다**는 규약은 같으므로 여기서 같이 찍는다. 원본이 없으면
    # 조용히 건너뛴다 — 갓 받은 저장소에서는 변형안을 아직 안 돌렸을 뿐이다.
    "plan-b": (pathlib.Path("out/DI_Sol_Rec_B안_전처리.html"),
               pathlib.Path("out/plan-b-plant-artifact.html")),
    "plan-b-delam": (pathlib.Path("out/DI_Sol_Rec_B안_박리라인.html"),
                     pathlib.Path("out/plan-b-delam-artifact.html")),
    "plan-c": (pathlib.Path("out/DI_Sol_Rec_C안_전처리.html"),
               pathlib.Path("out/plan-c-plant-artifact.html")),
    "plan-c-delam": (pathlib.Path("out/DI_Sol_Rec_C안_박리라인.html"),
                     pathlib.Path("out/plan-c-delam-artifact.html")),
}

#: 원본이 없으면 건너뛰는 대상 — 커밋되지 않는 생성물이다.
OPTIONAL = ("plan-b", "plan-b-delam", "plan-c", "plan-c-delam")

# ── 발행처 ──────────────────────────────────────────────────────────────
#: 아티팩트 주소의 앞부분.
ARTIFACT_BASE = "https://claude.ai/code/artifact/"

#: 대상 → **이미 발행된 아티팩트의 UUID**. 다시 찍으면 여기로 덮는다.
#:
#: 이 표가 없던 동안 저장소 어디에도 발행처가 적혀 있지 않았다 — 코드·문서를
#: 통틀어 `claude.ai/code/artifact` 문자열이 **0 건**이었다. 위 독스트링은
#: 「같은 URL 로 재발행한다」고 적어 두었지만 그 URL 이 어디에도 없었으므로,
#: 다시 찍을 때마다 **같은 도면의 아티팩트가 하나씩 더 생겼다.**
#:
#: 실제로 그렇게 됐다. 물리 시뮬레이션은 head 447269f 에서 한 번(037cf13c),
#: head 3ee9f4a 에서 또 한 번(d5eaa3df) 찍혔다 — 둘 다 이 브랜치 커밋이고
#: 앞의 것은 칸 4.0 s·수거함 안치수 540 인 REV.57 판이다. 다른 브랜치와의
#: 핑퐁이 아니라 **우리가 우리 것을 두 벌 만든 것**이다. JBR 여섯 종이 전부
#: 그렇게 두 벌씩 있다(`SUPERSEDED`).
#:
#: 값은 손으로 적지만 **확인하고 적는다** — 변환기 규약상 저장소 파일의
#: `<title>` 이 그대로 아티팩트 이름이 되므로, 발행 목록에서 그 이름으로
#: 찾으면 대응이 나온다. 이름이 겹치는 자리(JBR 여섯)는 발행본 안의
#: `head` 각인으로 갈랐다.
PUBLISHED: dict[str, str] = {
    "console": "64d5edab-dbe7-4eb5-b8de-389238ad6359",
    "plant": "9e171853-6137-4428-bf65-7009b5eccf7f",
    "infeed": "7db8926e-2083-4517-bd5d-ee8b10440120",
    "infeed-sim": "68a7cfcc-5afc-44bb-9033-6195a7cba5a4",
    "infeed-scene": "f0afbe44-63c8-4a11-8685-d69383b08c92",
    "infeed-fab": "e370a09a-d139-40f6-b292-9d94c98ae336",
    "infeed-dyn": "7c6b28f4-06f4-46c5-b054-4d696c57e30d",
    "prototype": "64149cde-3fd4-4b2c-b320-ae56ec09bb58",
    # 베이스가 REV.62 와 같은 시각에 들여온 도면이다. 발행본은 이미 있는데
    # 변환기 표에는 없었다 — 이 표가 막으려는 바로 그 자리라 같이 채운다.
    # 제목 「투입 구간 결정 등록부」가 발행 목록에 하나뿐이라 대응이 갈렸다.
    "decisions": "2fcf5025-73ba-42c2-bd21-ef1d381e0ada",
    "fasteners": "f292d899-c846-4556-8424-526eb321ad2f",
    "assembly-steps": "cf0ea732-b99a-48fa-abb4-e788fe4819f9",
    "jbr-scene": "12f62610-f43e-4a74-992d-8ed6d5c1c98b",
    "jbr-detail": "02bf159f-d015-49e4-8b45-c647f3238f95",
    "jbr-closeup": "200fb6bc-69b8-45c9-9552-5d8dbcc0f532",
    "jbr-fab": "90ac72e3-34cf-4602-a3ff-207fd4644997",
    "jbr-hub": "4b703023-c217-4d60-a07f-a7bd36e962c9",
    "jbr-physics": "d5eaa3df-fcc9-4e6f-8a32-dc165b75a707",
    # 후단 — 이 브랜치가 발행한 셋. GI 확대도와 후단 도면집은 그것을 만든
    # 브랜치(claude/gi-inspection-cell)가 자기 자리에서 적는다.
    "afr-scene": "6e68bee7-a1f1-495b-a84f-3942f6105c90",
    "afr-closeup": "2070e91e-1012-41db-be9e-9148c2512fd3",
    "sg-closeup": "6bfcba30-c0f3-44e6-b923-c56496c20aa6",
    # 이 브랜치가 더한 둘 — GI 확대도와 그 넷을 담은 후단 도면집.
    "gi-closeup": "43f2ae42-5267-48eb-b83a-52c362ed7650",
    "afr-hub": "4b9ff34d-5236-4a37-b881-991db9774dcf",
}

#: 같은 도면으로 **잘못 하나 더 생긴** 아티팩트 — 재발행하지 말 것.
#:
#: 지우지 않고 적어 둔다. 지우면 다음에 목록에서 보고 「이게 그건가」 하며
#: 같은 자리를 다시 밟는다. 어느 쪽이 정본인지는 `PUBLISHED` 가 정한다.
SUPERSEDED: dict[str, tuple[str, ...]] = {
    "jbr-scene": ("cfd3f9e8-3f43-47bc-bb05-4a46b4f3e897",),
    "jbr-detail": ("a14f01c2-7789-4919-ae30-71e5d098b761",),
    "jbr-closeup": ("4559a80a-f13b-49b3-a44d-c954ef1faf82",),
    "jbr-fab": ("66a5be4e-d013-4e5c-858d-da783d09be38",),
    "jbr-hub": ("f3b1f4b0-009d-4df4-a68d-2f0c13d17589",),
    "jbr-physics": ("037cf13c-6417-4b77-99fd-9e265b8d857f",),
}

#: 발행처를 아직 못 적은 대상과 그 이유. **빈칸을 「발행본이 없다」로 읽지 않게**
#: 이유를 같이 적는다 — 그 혼동이 이 표를 만들게 한 원인이다.
UNRECORDED: dict[str, str] = {
    "plan-b": "제목이 본 플랜트와 같아 발행 목록에서 못 가른다 (out/ 전용 변형안)",
    "plan-b-delam": "제목이 C안과 같아 못 가른다 (out/ 전용 변형안)",
    "plan-c": "제목이 본 플랜트와 같아 발행 목록에서 못 가른다 (out/ 전용 변형안)",
    "plan-c-delam": "제목이 B안과 같아 못 가른다 (out/ 전용 변형안)",
}


def artifact_url(name: str) -> str | None:
    """대상의 발행처. 아직 못 적은 것은 None 이다 — 그때는 새로 찍는다."""
    uuid = PUBLISHED.get(name)
    return ARTIFACT_BASE + uuid if uuid else None

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


def convert(text: str, src: pathlib.Path, url: str | None = None) -> str:
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
        f"     발행처: {url or '아직 없다 — 새로 찍고 build_artifact.PUBLISHED 에 적는다'}\n"
        "     고칠 때는 원본을 고치고 이것을 다시 돌린 뒤 **위 발행처에** 재발행한다. -->\n"
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
    url = artifact_url(name)
    out = convert(src.read_text(encoding="utf-8"), src, url)
    dest.write_text(out, encoding="utf-8")
    kb = len(out.encode("utf-8")) / 1024
    size = f"{kb / 1024:.2f} MB" if kb > 1024 else f"{kb:.1f} kB"
    print(f"{dest}  {size}  (원본 {src}, head {head_commit()})")
    print(f"    발행처 {url}" if url else
          f"    발행처 미기록 — {UNRECORDED.get(name, '새로 찍고 PUBLISHED 에 적을 것')}")
    return dest


def main() -> None:
    names = sys.argv[1:] or list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        raise SystemExit(f"✗ 모르는 대상: {unknown} — 아는 것은 {list(TARGETS)}")
    for name in names:
        if name in OPTIONAL and not TARGETS[name][0].exists():
            print(f"{TARGETS[name][0]}  없음 — 건너뛴다 "
                  f"(PYTHONPATH=src python tools/build_handoff_variants.py out/ 을 먼저 돌린다)")
            continue
        build(name)


if __name__ == "__main__":
    main()
