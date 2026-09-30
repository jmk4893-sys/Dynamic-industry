#!/usr/bin/env python3
"""기초도 D-602 의 앵커군을 콘솔 상수로 다시 세운다 — 판끼리 겹치는지 세려고.

D-602 는 콘솔 안에서 3D 가 기둥을 세운 함수(rackColXs · tblColXs · CMAST_* …)로
앵커 좌표를 낸다. 그 좌표와 카탈로그 판 크기를 여기서 같은 식으로 다시 세우면
시험이 도면을 띄우지 않고도 두 가지를 물을 수 있다.

  * 판끼리 떨어져 있는가 — 스테이션 경계 일곱 곳에서 이웃 장비의 판이 서로
    겹쳐 있었다 (GL-101 포크 ↔ GC-101 첫 기둥 200 · EX/GL 포크 ↔ KG-101 문형 120 …).
    판은 카탈로그 품번 그대로이고, 길이(L)가 라인 방향(x) · 폭(W)이 y 다.
  * 판 수가 카탈로그 수량과 같은가 — 기초도가 RH-201 안쪽 기둥을 KG-101 문형과
    '같은 기둥' 이라며 하나만 세는 동안 카탈로그는 기둥 둘 · 판 둘을 샀다.

좌표식은 D-602 의 GROUPS 와 한 줄씩 대응한다. 식이 갈라지면
tests/test_foundation.py 가 콘솔 원문과 대조해 걸린다. 납품 배치(DG-HK60C)만
센다 — 기초도가 그 배치의 도면이다.
"""

from __future__ import annotations

import math

import console_consts as CC
import parts as PT
from console_consts import const as c

GAP_MIN = 0.030     # m — 이웃 판 사이 최소 틈. 그라우트 거푸집과 앵커 천공 지그가 들어갈 자리


def plate(pid):
    """카탈로그 판 (L, W) m — L 이 라인 방향(x)."""
    d = next(p for p in PT.P if p.pid == pid).shape.d
    return d["L"] / 1000.0, d["W"] / 1000.0


def _grid(xs, ys):
    return [(x, y) for x in xs for y in ys]


def _rack_cols(cx, w, inset=0.0):
    n = round(c("RACK_COLS_X"))
    return [cx - w / 2 + inset + i * (w - 2 * inset) / (n - 1) for i in range(n)]


def _fence_posts(gx0, gx1):
    """방책 기둥 — D-602 fencePts · 3D fenceSegment 와 같은 구간 · 피치 · 끝 공유."""
    x0, x1 = c("CFENCE_X0"), PT.LINE_LEN / 1000.0 + 0.84
    yn, yp, pitch = c("CFENCE_YN"), c("CFENCE_Y"), c("FENCE_PITCH")
    runs = [(x0, -yn, gx0, -yn), (gx1, -yn, x1, -yn), (x0, yp, x1, yp)]
    for x in (x0, x1):
        runs += [(x, -yn, x, -1.05), (x, 1.05, x, yp)]
    seen = {}
    for a, b, e, f in runs:
        n = max(1, math.ceil(math.hypot(e - a, f - b) / pitch - 1e-9))
        for i in range(n + 1):
            x, y = a + (e - a) * i / n, b + (f - b) * i / n
            seen[(round(x * 1e3), round(y * 1e3))] = (x, y)
    return [(x, y) for x, y in seen.values()
            if not (abs(y + yn) < 1e-6 and (abs(x - gx0) < 1e-6 or abs(x - gx1) < 1e-6))]


def groups():
    """[(기호, 판 품번, (L, W), [(x, y), …])] — D-602 GROUPS 와 같은 순서."""
    with CC.layout("compact"):
        cst = c("CST")
        half = c("FORK_HALF_STD")
        tbl_n, tcx, cl, cw = round(c("TBL_COLS_X")), c("CTBL_CX"), c("CARRIER_L"), c("CARRIER_W")
        tix, tiy = c("TBL_INSET_X"), c("TBL_INSET_Y")
        tbl_x = [tcx - cl / 2 + tix + i * (cl - 2 * tix) / (tbl_n - 1) for i in range(tbl_n)]
        tbl_y = [-(cw / 2 - tiy), cw / 2 - tiy]
        ry = c("RACK_COL_Y")
        gate_x = (c("CE_X0") + c("CE_X1")) / 2
        gx0, gx1 = gate_x - c("GATE_W") / 2, gate_x + c("GATE_W") / 2
        pts = {
            "A1": _grid(_rack_cols(cst.HC.cx, cst.HC.w), (-ry, ry)),
            "A2": _grid(_rack_cols(cst.GC.cx, cst.GC.w, c("GC_COL_INSET")), (-ry, ry)),
            "A3": _grid((c("CMAST_IN"),), (-half, half)),
            "A4": _grid((c("CMAST_OUT"),), (-half, half)),
            "A5": _grid((c("CMAST_GL"),), (-half, half)),
            "A6": _grid((c("CMAST_GU"),), (-half, half)),
            "A7": _grid((c("CRAIL_X0"), c("CRAIL_X1")), (-c("CGY"), c("CGY"))),
            "A8": _grid(tbl_x, tbl_y),
            "A10": _grid((c("CRAIL_X0"),), (-(c("CFENCE_YN") + 0.10), c("RH_POST_IN"))),
            "A11": _grid((c("CE_LEG_X0"), c("CE_LEG_X1")), (c("CE_LEG_Y0"), c("CE_LEG_Y1"))),
            "A13": [(c("CKC_X"), c("CKC_RACK_Y"))],
            "A14": _grid((c("QI_X"),), (-1.02, 1.02)),
            "A15": _fence_posts(gx0, gx1),
            "A16": _grid((gx0, gx1), (-c("CFENCE_YN"),)),
        }
    return [(aid, pid, plate(pid), pts[aid]) for aid, _eq, pid, *_ in PT.ANCHOR_GROUPS]


def gap(a, b):
    """두 판 사이 틈 m — 음수면 겹친다. a · b = (x, y, L, W)."""
    gx = abs(a[0] - b[0]) - (a[2] + b[2]) / 2
    gy = abs(a[1] - b[1]) - (a[3] + b[3]) / 2
    return max(gx, gy)


def clashes(limit=GAP_MIN):
    """틈이 limit 보다 작은 판 쌍 [(기호 a, 기호 b, 틈 m)] — 같은 군끼리도 센다."""
    flat = [(aid, (x, y, L, W)) for aid, _pid, (L, W), pts in groups() for x, y in pts]
    out = []
    for i, (ia, a) in enumerate(flat):
        for ib, b in flat[i + 1:]:
            g = gap(a, b)
            if g < limit - 1e-9:
                out.append((ia, ib, g))
    return out


def min_gap():
    flat = [(x, y, L, W) for _aid, _pid, (L, W), pts in groups() for x, y in pts]
    return min(gap(a, b) for i, a in enumerate(flat) for b in flat[i + 1:])


if __name__ == "__main__":
    tot_pl = tot_an = 0
    for aid, pid, (L, W), pts in groups():
        n = len(next(p for p in PT.P if p.pid == pid).shape.d["holes"])
        tot_pl, tot_an = tot_pl + len(pts), tot_an + n * len(pts)
        print(f"{aid:4s} {pid}  {L*1000:5.0f} × {W*1000:5.0f}  판 {len(pts):3d}  앵커 {n} × {len(pts)}")
    print(f"판 {tot_pl} · 앵커 {tot_an} · 최소 틈 {min_gap()*1000:.0f} mm · 겹침 {len(clashes())}")
