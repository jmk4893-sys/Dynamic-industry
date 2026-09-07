"""제작 지침서 문서의 파생 숫자를 계산기와 다시 맞춘다.

지침서(docs/dg-hk60-fab-spec.html)는 손으로 쓴 문서지만, 표의 숫자는 전부
계산기(fab_spec.py)에서 나온 값이다. 형상이 바뀌면 자중이 바뀌고, 자중이
바뀌면 접합부 설계력과 용접 설계력이 따라 움직인다 — 그때마다 표를 손으로
고치면 반드시 한 칸이 남는다. 이 파일이 그 칸들을 기계적으로 다시 쓴다.

    python3 tools/sync_fab_doc.py            # 무엇이 다른지만 본다
    python3 tools/sync_fab_doc.py --write    # 문서를 맞춘다

시험(tests/test_fab_spec.py)이 문서와 계산기를 대조하므로, 이것을 안 돌리면
시험이 먼저 실패한다. 여기서 고치는 것은 **숫자뿐**이다 — 문장은 사람이 쓴다.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import fab_spec as F  # noqa: E402
import parts as PT  # noqa: E402

DOC = pathlib.Path(__file__).resolve().parents[1] / "docs" / "dg-hk60-fab-spec.html"

# 하중표의 자중 행 — (표제란 문구, 계산기 기호)
MASS_ROWS = (
    ("HC-101 가열실 자중", "M_CHAMBER"),
    ("KG-101 갠트리 자중", "M_GANTRY"),
    ("VT-101 테이블 자중", "M_TABLE"),
    ("WR-101 권취부 자중", "M_WINDER"),
)


def sync(text: str) -> tuple[str, list[str]]:
    """(고친 문서, 무엇을 고쳤는지)."""
    log: list[str] = []
    dev = {s: d for s, _w, _a, _g, d, _ok in PT.mass_check()}

    # ── 자중 행: 특성값 · 설계값 · 질량 · 개산 대비 편차
    for th, sym in MASS_ROWS:
        m = getattr(F, sym)
        pat = re.compile(
            r"(<tr><th>" + re.escape(th) + r"</th><td class=\"num\">)[\d.,]+( kN</td>"
            r"<td class=\"num\">)[\d.,]+( kN</td>.*?부품 카탈로그 계산 )[\d.]+( t</strong>\s*"
            r"\(개념 개산 대비 )[-+]?\d+(%\))", re.S)
        new = pat.sub(
            lambda g: (f"{g.group(1)}{F.kn(m):.1f}{g.group(2)}{F.GAMMA_G * F.kn(m):.1f}"
                       f"{g.group(3)}{m / 1000:.2f}{g.group(4)}{dev[sym]:+.0%}"[:-1] + g.group(5)),
            text)
        if new != text:
            log.append(f"{th} → {F.kn(m):.1f} kN · {m/1000:.2f} t")
            text = new

    # ── 접합부 표: N,Ed · V,Ed · 이용률
    lines = text.split("\n")
    byid = {j["id"]: j for j in F.JOINTS}
    for i, ln in enumerate(lines):
        mm = re.match(r'<tr><td class="k">(J\d+)</td>', ln)
        if not mm or mm.group(1) not in byid:
            continue
        j = byid[mm.group(1)]
        parts_ = re.split(r'(<td[^>]*>.*?</td>)', ln)
        tds = [k for k, x in enumerate(parts_) if x.startswith("<td")]
        if len(tds) < 10:
            continue
        for idx, val in ((5, f"{j['N']:.2f}"), (6, f"{j['V']:.2f}"), (7, f"{j['util']:.2f}")):
            cur = re.search(r"<td[^>]*>(.*?)</td>", parts_[tds[idx]]).group(1)
            if cur != val:
                parts_[tds[idx]] = parts_[tds[idx]].replace(">" + cur + "<", ">" + val + "<")
                log.append(f"{j['id']} 열{idx} {cur} → {val}")
        lines[i] = "".join(parts_)

    # ── 부재 표: 단면·재질·지배 검토
    # 형상이 바뀌면 지배 검토가 바뀐다 — VT-101 상판이 그랬다. 진공이
    # 지배한다고 적혀 있었는데 구조해석이 자중이라고 답했고, 표는 그대로
    # 남아 시험이 잡았다. 손으로 안 고치도록 여기서 같이 쓴다.
    grp = None
    byname = {(m[0], m[1]): m for m in F.MEMBERS}
    for i, ln in enumerate(lines):
        g = re.match(r'<tr><th colspan="4" class="grp">(M-\d+)</th></tr>', ln)
        if g:
            grp = g.group(1)
            continue
        mm = re.match(r"<tr><td>(.*?)</td>", ln)
        if not (grp and mm and (grp, mm.group(1)) in byname):
            continue
        _mod, name, sec, mat, gov = byname[(grp, mm.group(1))]
        cells = re.findall(r"<td[^>]*>(.*?)</td>", ln)
        if len(cells) < 4:
            continue
        for cur, want in zip(cells[1:4], (sec, mat, gov)):
            if cur != want:
                ln = ln.replace(">" + cur + "<", ">" + want + "<", 1)
                log.append(f"부재 {grp} {name} {cur} → {want}")
        lines[i] = ln

    # ── 용접 표: 설계력
    for name, force, _len, _mat, _t in F.WELDS:
        for i, ln in enumerate(lines):
            if not ln.startswith("<tr><td>" + name + "</td>"):
                continue
            cur = re.findall(r"<td[^>]*>(.*?)</td>", ln)[1]
            if abs(float(cur) - force) > 0.005:
                lines[i] = ln.replace(">" + cur + "<", f">{force:.2f}<", 1)
                log.append(f"용접 {name} {cur} → {force:.2f}")
            break
    return "\n".join(lines), log


if __name__ == "__main__":
    src = DOC.read_text(encoding="utf-8")
    out, log = sync(src)
    if not log:
        print("이미 같다 — 바꿀 것이 없다")
    elif "--write" in sys.argv:
        DOC.write_text(out, encoding="utf-8")
        print(f"{len(log)} 곳 갱신")
        for x in log:
            print("  " + x)
    else:
        print(f"{len(log)} 곳이 계산기와 다르다 (--write 로 맞춘다)")
        for x in log:
            print("  " + x)
