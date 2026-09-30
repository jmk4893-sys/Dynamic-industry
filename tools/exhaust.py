#!/usr/bin/env python3
"""배기 풍량과 관경 — 경계 덕트 Ø600 은 어떤 풍량에서 나왔는가.

콘솔의 배기 헤더는 지선 Ø400 × 2 · 본관 Ø460 · 경계 플랜지 Ø600 이었다.
셋 다 풍량에서 나온 값이 아니었다 — Ø600 은 REV.20(53 m 라인 · 후처리
포함)의 헤더 치수가 압축 배치로 넘어온 것이다. 사양서 1.4 는 "배기 헤더는
2 셀 유량으로 관경을 정한다" 고 요구하는데, 그 유량을 아무도 세지 않았다.

── 무엇이 배기를 부르는가 ───────────────────────────────────────────
① 가열실 HC-101 — 셔터가 닫혀 있으면 누설만큼(−40 Pa 에서 수십 m³/h)이다.
   그러나 포크가 들어가는 동안 단별 셔터가 열린다 — 투입·배출 쪽 각 한 장
   (PLC IN/OUT_SHUTTER_MUTEX 가 막는 것은 같은 쪽 두 단이다). 그때 140 ℃
   챔버와 25 ℃ 실내 사이의 부력이 개구 위쪽으로 챔버 가스를 밀어낸다
   (airlock.exchange_flow). 그것을 막으려면 개구 전체를 유입으로 돌릴 만큼
   빼야 한다 — 중립면을 개구 위끝까지 올리는 유량이다:

       Q_봉쇄 = Cd·w·(2/3)·√(2g')·h^{3/2} = 2√2 · Q_교환

   그리고 개구 면속도가 국소배기 포집풍속(사양서 5.4 · 0.5 m/s)보다 낮으면
   안 된다. 둘 중 큰 쪽이다.
② 분리 셀 DL-101 — 계단 칼날이 140 ℃ EVA 를 가르는 줄. 슬롯 후드가 칼날
   뒤를 따라가며 칼날 폭 L 전체를 빤다. 가장 먼 발생점은 중앙 칼끝 — 계단
   깊이에 슬롯 물림을 더한 X 앞이다. 드립트레이가 플랜지 구실을 하는 슬롯이므로
   Q = 2.6·L·v·X (ACGIH, 플랜지 슬롯).

── 유량은 일정하게 ─────────────────────────────────────────────────
셔터가 닫혀 있는 동안 챔버는 봉쇄 유량을 낼 수 없다 — 누설면적
1,100 mm² 로 0.8 m³/s 를 빼려면 챔버가 부서질 부압이 든다. 그래서 가열실
지선은 블리드 댐퍼로 유량을 일정하게 둔다: 평소에는 블리드가 실내 공기를
대고, 셔터가 열리면(IN/OUT_SHUTTER_OPEN 선행) 블리드를 닫아 그 몫을 챔버에서
뺀다. 헤더와 경계는 늘 같은 유량을 보고, 발주자 후처리(OI-15)도 일정한
유량을 받는다. 챔버 부압(−30 ± 10 Pa)은 챔버 댐퍼가 잡는다.

── 관경 ────────────────────────────────────────────────────────────
EVA 흄은 식으면 왁스처럼 붙는다. 덕트 속도가 떨어지면 거기서 쌓이고, 쌓인
것은 탄다. 운반 속도 대역 8 ~ 12.5 m/s(연기·흄, ACGIH)를 지키는 가장 작은
표준 관경을 고른다. 헤더 ②와 경계는 사양서 1.4 대로 2 셀 유량으로 정하고,
1 셀 운전에서도 하한을 넘는지 본다 — 넘으면 저유량 제어가 블리드 없이 선다.

**이 검토가 못 보는 것**: 후드의 실제 포집(칼날·누름판·셀모듈 슈트가 흐름을
가른다 — 파일럿 배기·후드 장치가 잰다), 셔터가 열리는 과도구간, 덕트 압손과
팬 정압(경계 너머 발주자 설비), 셀모듈이 CE-201 위에서 내는 흄 · 유리 냉각
랙의 잔류 흄(둘 다 이 헤더에 물려 있지 않다 — OI-10 배출가스 성상이 정한다).
"""

from __future__ import annotations

import math
import pathlib
import sys
from typing import NamedTuple

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import airlock as AIR  # noqa: E402
import heatbalance as HB  # noqa: E402
import lampmount as LM  # noqa: E402
from analysis_thermal import Req  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 설계 기준 ──────────────────────────────────────────────────────────
CAPTURE_V = 0.50          # m/s 국소배기 포집풍속 — 사양서 5.4 (SAT 실측)
SLOT_K = 2.6              # 플랜지 슬롯 (ACGIH) — 플랜지가 없으면 3.7
HOOD_SETBACK = 0.05       # m 슬롯 면이 마지막 칼끝에서 물러선 거리 — 카세트 홀더 두께
DP_MAX = 40.0             # Pa 챔버 부압 상한 — 사양서 5.4 −30 ± 10
N_OPEN = 2                # 동시에 열릴 수 있는 셔터 — 투입·배출 쪽 각 한 장 (PLC)
V_MIN, V_MAX = 8.0, 12.5  # m/s 운반 속도 대역 — 연기·흄
SERIES = (200, 250, 315, 355, 400, 450, 500, 560, 630)   # mm 스파이럴 덕트 표준 관경

# 콘솔이 쥔 관경 — 3D · 도면 · 카탈로그가 이것을 그린다. 시험이 이 모델의 선택과 댄다.
D_HC, D_CELL = c("DUCT_D_HC") * 1000, c("DUCT_D_CELL") * 1000
D_HDR1, D_HDR = c("DUCT_D_HDR1") * 1000, c("DUCT_D_HDR") * 1000


def area(d_mm: float) -> float:
    return math.pi / 4 * (d_mm / 1000) ** 2


def velocity(q: float, d_mm: float) -> float:
    return q / area(d_mm)


# ── ① 가열실 ─────────────────────────────────────────────────────────
def shutter() -> dict:
    """단별 셔터 한 장이 열렸을 때 챔버 가스를 가두는 유량."""
    q_ex = AIR.exchange_flow(AIR.OPEN_H)                  # 한쪽 교환유량
    q_buoy = 2 * math.sqrt(2) * q_ex                      # 중립면 → 개구 위끝
    q_face = CAPTURE_V * AIR.OPEN_W * AIR.OPEN_H          # 면속도 하한
    return dict(q_ex=q_ex, q_buoy=q_buoy, q_face=q_face, q=max(q_buoy, q_face),
                w=AIR.OPEN_W, h=AIR.OPEN_H)


def leak() -> float:
    """셔터가 다 닫혔을 때의 누설 — 부압 상한에서 (열수지의 누설면적)."""
    _area, m3h, _kw = HB.infiltration()                  # LM.DP 에서
    return m3h / 3600 * math.sqrt(DP_MAX / LM.DP)


def chamber() -> float:
    """가열실 지선 유량 — 일정 (블리드 댐퍼)."""
    return N_OPEN * shutter()["q"] + leak()


# ── ② 분리 셀 ───────────────────────────────────────────────────────
def hood() -> dict:
    L = c("KNIFE_W")
    X = c("KNIFE_DEPTH") + HOOD_SETBACK
    return dict(L=L, X=X, q=SLOT_K * L * CAPTURE_V * X)


# ── 합계 ─────────────────────────────────────────────────────────────
def total(cells: int) -> float:
    return chamber() + cells * hood()["q"]


def pick(q_design: float, q_low: float | None = None) -> float | None:
    """상한을 넘지 않는 가장 작은 표준 관경 — 낮은 유량에서 하한을 못 지키면 None."""
    for d in SERIES:
        if velocity(q_design, d) <= V_MAX:
            lo = q_design if q_low is None else q_low
            return d if velocity(lo, d) >= V_MIN else None
    return None


class Band(NamedTuple):
    """운반 속도 대역 검토 — 하한과 상한 사이에 있어야 한다."""

    id: str
    what: str
    d: float            # mm 관경
    q: float            # m³/s
    v: float            # m/s
    note: str

    @property
    def ok(self) -> bool:
        return V_MIN <= self.v <= V_MAX


def segments(max_cells: int = 2) -> list[dict]:
    """구간 — (이름, 관경, 설계 유량, 낮은 유량)."""
    ch, hq = chamber(), hood()["q"]
    return [
        dict(key="HC", name="가열실 지선", d=D_HC, q=ch, lo=ch),
        dict(key="CELL", name="셀 지선 (셀마다)", d=D_CELL, q=hq, lo=hq),
        dict(key="HDR1", name="헤더 ① 가열실 → 셀", d=D_HDR1, q=ch, lo=ch),
        dict(key="HDR", name=f"헤더 ② · 경계 ({max_cells} 셀 설계)", d=D_HDR,
             q=total(max_cells), lo=total(1)),
    ]


def checks(max_cells: int = 2) -> list[Band]:
    out = []
    for i, s in enumerate(segments(max_cells), 1):
        out.append(Band(f"EX{2 * i - 1}", f"{s['name']} — 설계 유량", s["d"], s["q"],
                        velocity(s["q"], s["d"]), "상한 12.5 — 압손 · 소음"))
        if s["lo"] != s["q"]:
            out.append(Band(f"EX{2 * i}", f"{s['name']} — 1 셀 운전", s["d"], s["lo"],
                            velocity(s["lo"], s["d"]), "하한 8 — 흄 퇴적. 블리드 없이 선다"))
    return out


def legacy() -> dict:
    """종전 관경(Ø400 지선 · Ø460 본관 · Ø600 경계)이 이 유량에서 내던 속도."""
    return dict(branch_hc=velocity(chamber(), 400), branch_cell=velocity(hood()["q"], 400),
                header=velocity(chamber(), 460),
                bound_1=velocity(total(1), 600), bound_2=velocity(total(2), 600))


def requirements() -> list[Req]:
    sh, hd = shutter(), hood()
    return [
        Req("REX1", "가열실 지선은 일정 유량 — 블리드 댐퍼",
            f"{chamber():.2f} m³/s 일정 · 셔터 개방 신호로 블리드를 닫는다 · 챔버 부압은 "
            f"챔버 댐퍼가 −30 ± 10 Pa",
            "상세설계 · M-017 · PLC",
            f"셔터 한 장({sh['w'] * 1e3:,.0f} × {sh['h'] * 1e3:.0f})을 가두는 데 "
            f"{sh['q']:.3f} m³/s 가 든다 — 부력 교환유량 {sh['q_ex']:.3f} 의 2√2 배. 투입·배출이 "
            f"겹치면 두 장이다. 닫힌 챔버로 이 유량을 빼면 챔버가 부서지므로 평소에는 블리드가 "
            f"댄다. **겹침을 막는 교차 인터록을 두면 봉쇄 유량이 절반이 된다** — 사이클이 허락하면 "
            f"입찰자가 택한다"),
        Req("REX2", "슬롯 후드는 칼날 뒤에서 폭 전체를 빤다",
            f"슬롯 {hd['L'] * 1e3:,.0f} · 포집 거리 ≤ {hd['X'] * 1e3:,.0f} · "
            f"{hd['q']:.3f} m³/s/셀 · 포집풍속 ≥ {CAPTURE_V:.1f} m/s",
            "상세설계 · M-005 · 파일럿 배기·후드",
            "가장 먼 발생점은 중앙 칼끝이다 — 계단 깊이만큼 앞선다. 드립트레이를 플랜지로 "
            "쓰지 않으면 계수가 2.6 → 3.7 로 42 % 늘어 셀 지선 관경이 한 단 오른다. "
            "누름판·셀모듈 슈트가 흐름을 가르는 것은 파일럿 후드가 잰다"),
        Req("REX3", "경계 풍량을 발주자에게 넘긴다 (OI-15)",
            f"표준 {total(1):.2f} m³/s ({total(1) * 3600:,.0f} m³/h) · 옵션 "
            f"{total(2):.2f} m³/s ({total(2) * 3600:,.0f} m³/h) · 일정",
            "발주자 · 사양서 OI-15",
            "후처리 설비가 받을 유량이다. 블리드로 일정하게 두므로 셔터가 열리고 닫혀도 "
            "후처리가 흔들리지 않는다"),
    ]


def report() -> str:
    L = []
    add = L.append
    sh, hd = shutter(), hood()
    add("=" * 78)
    add("배기 풍량과 관경 — tools/exhaust.py")
    add("=" * 78)
    add(f"가열실 셔터 한 장 {sh['w'] * 1e3:,.0f} × {sh['h'] * 1e3:.0f}: 교환 {sh['q_ex']:.3f} · "
        f"봉쇄 {sh['q_buoy']:.3f} · 면속도 {sh['q_face']:.3f} m³/s")
    add(f"가열실 지선 {chamber():.3f} m³/s (셔터 {N_OPEN} 장 + 누설 {leak():.4f})")
    add(f"셀 후드 L {hd['L']:.2f} · X {hd['X']:.2f} → {hd['q']:.3f} m³/s/셀")
    add(f"경계 표준 {total(1):.3f} · 옵션 {total(2):.3f} m³/s")
    for s in segments():
        add(f"  {s['name']:24s} Ø{s['d']:.0f}  모델 선택 Ø{pick(s['q'], s['lo'])}  "
            f"{velocity(s['q'], s['d']):5.1f} / {velocity(s['lo'], s['d']):5.1f} m/s")
    old = legacy()
    add(f"종전 Ø600 경계: 1 셀 {old['bound_1']:.1f} · 2 셀 {old['bound_2']:.1f} m/s")
    bad = [b.id for b in checks() if not b.ok]
    add("전 구간 대역 안" if not bad else f"대역 밖: {bad}")
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
