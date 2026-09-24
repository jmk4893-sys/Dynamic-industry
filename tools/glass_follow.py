#!/usr/bin/env python3
"""유리면 추종 — 곧은 칼날은 곧은 유리를 전제한다. 유리는 곧지 않다.

칼끝 깊이 예산은 0.15 mm (EVA 0.45 의 1/3 · CAL-001 S1) 이고, 구조해석 S10 이
그중 칼 쪽 — 연삭 ±0.05 · Z축 좌우 기울기 · 캐리어 휨 — 을 0.105 로 셌다.
유리 쪽은 아무도 세지 않았다. 패널은 흡착패드 위에 앉고 패드 상면은 동일
평면 PAD_FLAT (0.3 mm) 안에서 흩어진다. 3.2 mm 유리는 진공에 붙어 패드를
따라가므로 유리면은 폭 방향으로 곧지 않다.

여기서 세 가지를 판다.

  ① 칼끝과 유리면의 어긋남. 테이블 한 대의 패드 높이를 밴드 안에서 고르게
     흩뜨린다(폭 방향 패드 네 줄). 유리는 패드 사이를 매끄럽게 잇는다 — 자연
     3차 스플라인, 바깥 줄 밖은 직선. 패드 높이는 테이블이 정하므로 한 번의
     추첨이 한 대의 테이블이고, 그 테이블은 모든 패널에 같은 굴곡을 준다.
       · 곧은 한 자루 — 테이블마다 가장 좋은 높이·기울기로 교정해도 남는 반폭
         (체비쇼프 직선). 이것이 S10 의 칼 쪽에 더해진다.
       · 일곱 모듈 (들림 + 롤) — 모듈마다 제 폭 안의 윗볼록껍질에 얹힌다.
         랜드가 높은 점을 타고 낮은 점에서 뜬다. 뜬 만큼이 잔막이다.
       · 대조 — 들림만 준 일곱 모듈, 세 조각 (들림 + 롤).
  ② 추종 중 패드 사이 유리의 굽힘. 모듈이 유리에 남기는 예압(KM_NET)과, 누름판이
     층을 칼날에 붙드는 힘(CHD_PRELOAD × CHD_POSTS)이 폭 방향 선하중으로 패드 열
     사이를 건넌다 — 칼날이 떠 있으니 누름판의 반력도 유리가 받는다. 단순지지
     상한으로 본다.
  ③ 박리 전선의 국부 우력. 칼날이 층을 들어 올리면 층은 전선에서 유리를 같은
     힘으로 들어 올린다. 유리는 곧바로 밑면 랜드에 닿고 — 랜드는 제가 남긴 잔막
     위에 얹혀 있다 — 랜드가 그 힘을 되받는다. 두 힘이 랜드 폭만큼 떨어져 선다.
     크기는 수직 반력 V 이고 팔이 짧다. 잠금이든 추종이든 같다.
  ④ V 가 경간을 건너지 않는 이유. V 를 패드 사이 유리가 휨으로 받으려면 유리가
     그만큼 떠야 한다. V/H 1 이면 수십 mm — EVA 두께보다 두 자릿수 크다. 랜드가
     그 전에 받는다.

잠금(Z축이 곧은 칼날을 잡는다)과 추종을 가르는 것은 그래서 힘이 아니라 기하다.
곧은 칼날은 ① 의 반폭만큼 유리면에서 어긋난다. 유리가 낮은 자리에는 잔막이 남고,
높은 자리에서는 칼날이 유리를 누른다. 그 자리가 패드 위면 유리가 비킬 데가 없어
누르는 힘은 V 가 아니라 캐리어·Z축의 강성이 정한다. 추종은 그 힘을 V + 예압에서
자른다.

값은 하나도 새로 정하지 않는다. 패드·패널·칼날은 콘솔 뿌리 상수, 유리 두께와
허용응력은 열해석(analysis_thermal), 폭당 박리 저항은 knife_stepped 에서 온다.
난수는 씨앗을 고정해 같은 저장소에서 같은 숫자가 나온다.

    python3 tools/glass_follow.py
"""

from __future__ import annotations

import bisect
import functools
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import analysis_thermal as TH  # noqa: E402
import knife_stepped as KS  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 뿌리 상수 (mm · N) ───────────────────────────────────────────────────
PAD_FLAT = c("PAD_FLAT") * 1000                 # 0.3 패드 상면 동일 평면 밴드
PAD_ROWS, PAD_COLS = int(c("PAD_ROWS")), int(c("PAD_COLS"))
PANEL_W, PANEL_L = c("PANEL_W") * 1000, c("PANEL_L") * 1000
HALF = PANEL_W / 2                              # 700 — 유리가 있는 폭의 절반
ROW_Y = tuple((i - (PAD_ROWS - 1) / 2) * PANEL_W / PAD_ROWS
              for i in range(PAD_ROWS))         # ±175 · ±525 — 콘솔 padYs() 와 같은 식
SPAN_X = PANEL_L / PAD_COLS                     # 416.7 패드 열 간격 — 추종 선하중이 건너는 경간
T_GLASS = TH.T_GLASS * 1000                     # 3.2 — 면적질량 ÷ 밀도
SIG_GL = TH.SIG_GL                              # 7 MPa — 사양서 5.5 설계허용 (열응력과 같은 값)
E_GL = TH.E_GL                                  # 73,000 MPa 유리 탄성계수 (열응력과 같은 값)
EVA_T = c("MASS_EVA") / 2 / TH.RHO["EVA"] * 1000  # 0.45 칼끝이 서는 EVA 층 — 깊이 예산 0.15 의 세 배
KM_NET = c("KM_NET")                            # N/mm 유리에 남는 순 예압
HD_PRELOAD = c("CHD_PRELOAD") * c("CHD_POSTS")  # N 누름판 예압 합 — 층을 칼날에 붙들고, 추종 중에는 모듈을 거쳐 유리로 간다
KNIFE_W = c("KNIFE_W") * 1000                   # 1,500 누름판이 덮는 폭
LAND = c("KNIFE_LAND") * 1000                   # 1.5 칼날 밑면 랜드 — 국부 우력의 팔
F_W = KS.F_W                                    # N/mm 폭당 박리 저항 11.14 (특성)

TRIALS = 4000                                   # 테이블 수 — P95 가 셋째 자리에서 흔들리지 않는 수
SEED = 20260924                                 # 발주자 승인일 — 같은 저장소에서 같은 숫자
STEP = 5.0                                      # mm 단면 표본 간격


# ── 유리 단면 ────────────────────────────────────────────────────────────
def spline(xs, ys):
    """자연 3차 스플라인. 바깥 매듭 밖은 끝 기울기로 곧게 뻗는다 — 유리 가장자리는
    패드가 없으니 휘지 않고 기울기를 이어 간다."""
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    a, b, cc, d = [0.0] * n, [1.0] * n, [0.0] * n, [0.0] * n
    for i in range(1, n - 1):
        a[i], b[i], cc[i] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        d[i] = 6 * ((ys[i + 1] - ys[i]) / h[i] - (ys[i] - ys[i - 1]) / h[i - 1])
    for i in range(1, n):                       # 삼중대각 전진 소거 (끝 행은 M = 0)
        w = a[i] / b[i - 1]
        b[i] -= w * cc[i - 1]
        d[i] -= w * d[i - 1]
    m = [0.0] * n
    for i in range(n - 2, 0, -1):
        m[i] = (d[i] - cc[i] * m[i + 1]) / b[i]
    m[0] = m[-1] = 0.0
    s0 = (ys[1] - ys[0]) / h[0] - h[0] * (2 * m[0] + m[1]) / 6
    s1 = (ys[-1] - ys[-2]) / h[-1] + h[-1] * (2 * m[-1] + m[-2]) / 6

    def f(x):
        if x <= xs[0]:
            return ys[0] + s0 * (x - xs[0])
        if x >= xs[-1]:
            return ys[-1] + s1 * (x - xs[-1])
        i = min(bisect.bisect_right(xs, x) - 1, n - 2)
        t, hi = x - xs[i], h[i]
        u = xs[i + 1] - x
        return (m[i] * u ** 3 / (6 * hi) + m[i + 1] * t ** 3 / (6 * hi)
                + (ys[i] / hi - m[i] * hi / 6) * u + (ys[i + 1] / hi - m[i + 1] * hi / 6) * t)
    return f


def grid() -> list[float]:
    """유리 폭 전체의 표본점 — 한 번 계산한 단면을 모듈마다 잘라 쓴다."""
    n = int(round(PANEL_W / STEP)) + 1
    return [-HALF + k * STEP for k in range(n)]


@functools.lru_cache(maxsize=None)
def weights() -> tuple[tuple[float, ...], ...]:
    """격자점마다 패드 줄 높이에 곱할 가중치.

    자연 스플라인은 매듭 높이에 대해 선형이다. 줄마다 1 을 준 스플라인을 한 번씩
    그려 두면 어느 테이블의 단면이든 가중합 하나로 나온다 — 시행마다 스플라인을
    다시 풀 까닭이 없다.
    """
    cols = []
    for j in range(len(ROW_Y)):
        f = spline(ROW_Y, [1.0 if i == j else 0.0 for i in range(len(ROW_Y))])
        cols.append([f(y) for y in grid()])
    return tuple(zip(*cols))


def _index(y: float) -> int:
    k = round((y + HALF) / STEP)
    if abs(-HALF + k * STEP - y) > 1e-6:
        raise ValueError(f"y {y} 가 표본 격자({STEP} mm)에 있지 않다")
    return k


def _upper(ys, zs):
    """윗볼록껍질 (왼쪽부터) — 단조 사슬."""
    hull = []
    for p in zip(ys, zs):
        while len(hull) >= 2:
            (x1, z1), (x2, z2) = hull[-2], hull[-1]
            if (x2 - x1) * (p[1] - z1) - (z2 - z1) * (p[0] - x1) >= 0:
                hull.pop()
            else:
                break
        hull.append(p)
    return hull


def rest_gap(ys, zs) -> float:
    """들림 + 롤 모듈이 한 구간에 얹혔을 때 남는 가장 큰 틈 (mm).

    예압은 모듈 가운데에 걸린다. 모듈은 윗볼록껍질 가운데 모듈 중심을 가로지르는
    변에 얹힌다 — 두 높은 점에 걸쳐 눕는다. 틈 = 그 변 − 유리면.
    """
    hull = _upper(ys, zs)
    mid = (ys[0] + ys[-1]) / 2
    for (x1, z1), (x2, z2) in zip(hull, hull[1:]):
        if x1 <= mid <= x2:
            k = (z2 - z1) / (x2 - x1)
            return max(z1 + k * (y - x1) - z for y, z in zip(ys, zs))
    return 0.0


def heave_gap(ys, zs) -> float:
    """들림만 있는 모듈 — 가장 높은 점에 수평으로 얹힌다."""
    top = max(zs)
    return max(top - z for z in zs)


def straight_half(ys, zs) -> float:
    """곧은 칼날을 가장 좋게 교정했을 때의 반폭 (mm) — 체비쇼프 직선.

    기울기 s 의 띠 폭 max(z − s·y) − min(z − s·y) 은 s 에 대해 볼록한 꺾은선이고
    최소는 윗껍질이나 아랫껍질의 어느 변 기울기에서 난다. 그 기울기들만 대 본다.
    칼날은 띠의 한가운데에 선다 — 위로도 아래로도 반폭까지 벗어난다.
    """
    up = _upper(ys, zs)
    lo = [(y, -z) for y, z in _upper(ys, [-z for z in zs])]
    slopes = sorted({(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(up, up[1:])}
                    | {(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(lo, lo[1:])})

    def width(s):
        return max(z - s * y for y, z in up) - min(z - s * y for y, z in lo)

    i, j = 0, len(slopes) - 1                   # 볼록한 수열 — 삼분 탐색
    while j - i > 2:
        m1, m2 = i + (j - i) // 3, j - (j - i) // 3
        if width(slopes[m1]) <= width(slopes[m2]):
            j = m2
        else:
            i = m1
    return min(width(slopes[k]) for k in range(i, j + 1)) / 2


# ── 칼날이 유리를 만나는 구간 ─────────────────────────────────────────────
def module_spans() -> list[tuple[float, float]]:
    """일곱 모듈의 날 구간 (겹침 포함) 중 유리 위에 있는 부분 — knife_stepped 와 같은 표."""
    out = []
    for s in KS.segments():
        lo, hi = max(-HALF, s["y0"]), min(HALF, s["y1"])
        if hi > lo:
            out.append((lo, hi))
    return out


def third_spans() -> list[tuple[float, float]]:
    """대조 — 유리 폭을 셋으로 나눈 조각 (경계는 표본 격자에 맞춘다)."""
    cut = [-HALF + round(k * PANEL_W / 3 / STEP) * STEP for k in range(4)]
    return list(zip(cut, cut[1:]))


# ── 몬테카를로 ─────────────────────────────────────────────────────────────
def _stats(v: list[float]) -> dict:
    v = sorted(v)
    n = len(v)
    return dict(p50=v[n // 2], p95=v[int(0.95 * n)], max=v[-1])


@functools.lru_cache(maxsize=None)
def monte_carlo(band: float = PAD_FLAT, trials: int = TRIALS, seed: int = SEED) -> dict:
    """테이블 trials 대 — 곧은 한 자루 · 일곱 모듈 · 들림만 · 세 조각."""
    rng = random.Random(seed)
    ys = grid()
    mods = [(_index(lo), _index(hi) + 1) for lo, hi in module_spans()]
    thirds = [(_index(lo), _index(hi) + 1) for lo, hi in third_spans()]
    w = weights()
    acc = dict(straight=[], modules=[], heave=[], thirds=[])
    for _ in range(trials):
        h = [rng.uniform(-band / 2, band / 2) for _y in ROW_Y]
        zs = [sum(a * b for a, b in zip(row, h)) for row in w]
        acc["straight"].append(straight_half(ys[::2], zs[::2]))   # 폭 전체라 10 mm 면 된다
        acc["modules"].append(max(rest_gap(ys[a:b], zs[a:b]) for a, b in mods))
        acc["heave"].append(max(heave_gap(ys[a:b], zs[a:b]) for a, b in mods))
        acc["thirds"].append(max(rest_gap(ys[a:b], zs[a:b]) for a, b in thirds))
    return {k: _stats(v) for k, v in acc.items()}


# ── 유리 굽힘 ──────────────────────────────────────────────────────────────
def span_stress(q: float) -> float:
    """폭 방향 선하중 q (N/mm) 가 패드 열 사이를 건널 때 — 단순지지 경간 가운데.

    σ = 6·M/t², M = q·L/4 (폭당). 패드가 유리를 진공으로 물고 있어 실제 끝은
    고정에 가깝다 — 단순지지는 상한이다.
    """
    return 1.5 * q * SPAN_X / T_GLASS ** 2


def span_lift(q: float) -> float:
    """같은 선하중이 경간 가운데를 들어 올리는 높이 (mm) — 단순지지, 폭당.

    w = q·L³ / (48·E·I), I = t³/12. V 가 휨으로 패드까지 가려면 유리가 이만큼
    떠야 한다. 랜드는 잔막 위에 얹혀 0 mm 떨어져 있다.
    """
    return q * SPAN_X ** 3 / (48 * E_GL * T_GLASS ** 3 / 12)


def couple_stress(q: float, arm: float) -> float:
    """박리 전선의 우력 — 칼날이 누르는 힘과 층이 드는 힘 q (N/mm) 가 arm 만큼 떨어져 선다.

    우력 q·arm 이 판을 건너며 모멘트가 그 크기만큼 뛴다. 양쪽이 절반씩 받는다.
    σ = 6·(q·arm/2)/t².
    """
    return 3 * q * arm / T_GLASS ** 2


def summary() -> dict:
    """문서·해석·시험이 읽는 값."""
    mc = monte_carlo()
    lift_per_vh = span_lift(F_W)                # V 를 경간이 받으려면 유리가 뜰 높이 — 랜드가 먼저 받는다
    couple_per_vh = couple_stress(F_W, LAND)
    q_hd = HD_PRELOAD / KNIFE_W
    q_allow = SIG_GL * T_GLASS ** 2 / (1.5 * SPAN_X)
    return dict(
        mc=mc, band=PAD_FLAT, trials=TRIALS, rows=ROW_Y, span=SPAN_X, t=T_GLASS,
        modules=len(module_spans()),
        q_net=KM_NET, q_hd=q_hd, q_follow=KM_NET + q_hd,
        follow_span=span_stress(KM_NET + q_hd),
        lift_per_vh=lift_per_vh, eva=EVA_T, lift_over_eva=lift_per_vh / EVA_T,
        hd_post_max=(q_allow - KM_NET) * KNIFE_W / c("CHD_POSTS"),   # 추종에서 허용에 드는 포스트당 예압
        couple_per_vh=couple_per_vh, follow_vh_max=SIG_GL / couple_per_vh,
        vh_arm_max=SIG_GL * T_GLASS ** 2 / (3 * F_W),     # V/H × 팔 (mm) 의 상한
    )


def band_for(target: float, key: str = "straight") -> float:
    """P95 가 target 에 드는 패드 밴드 (mm). 모델이 높이에 선형이라 비례로 풀린다."""
    return PAD_FLAT * target / monte_carlo()[key]["p95"]


def report() -> str:
    s = summary()
    mc = s["mc"]
    L = [f"── 유리면 추종 · 패드 {PAD_COLS}×{PAD_ROWS} · 평면도 밴드 {PAD_FLAT:.2f} mm · "
         f"테이블 {TRIALS:,} 대 (씨앗 {SEED}) ──",
         f"  패드 줄 y = {' · '.join(f'{y:+.0f}' for y in ROW_Y)} · 표본 간격 {STEP:.0f} mm",
         "",
         "                                  P50      P95      최대   (mm)"]
    rows = (("straight", "곧은 한 자루 (가장 좋은 교정 · ±반폭)"),
            ("modules", f"일곱 모듈 (들림 + 롤 · 얹힌 틈)"),
            ("heave", "일곱 모듈 (들림만)"),
            ("thirds", "세 조각 (들림 + 롤)"))
    for k, name in rows:
        m = mc[k]
        L.append(f"  {name:30s} {m['p50']:7.3f}  {m['p95']:7.3f}  {m['max']:7.3f}")
    L += ["",
          f"  곧은 칼날이 P95 로 0.045 에 들려면 패드 밴드 {band_for(0.045):.3f} mm 이하",
          "",
          f"  추종 중 패드 사이 굽힘 — 예압 {KM_NET:.2f} + 누름판 {s['q_hd']:.3f} N/mm · 경간 {SPAN_X:.0f} · "
          f"t {T_GLASS:.1f} → {s['follow_span']:.2f} MPa (허용 {SIG_GL:.0f}) · "
          f"누름판은 포스트당 {s['hd_post_max']:.0f} N 까지",
          f"  V 는 랜드가 되받는다 (잠금·추종 모두) — 경간이 받으려면 유리가 V/H 1 에서 "
          f"{s['lift_per_vh']:.0f} mm 떠야 한다 (EVA {EVA_T:.2f} 의 {s['lift_over_eva']:.0f} 배)",
          f"  박리 전선 우력 — 팔 = 랜드 {LAND:.1f} mm · V/H 1 에서 {s['couple_per_vh']:.2f} MPa · "
          f"허용에 드는 V/H {s['follow_vh_max']:.2f} (V/H × 랜드 ≤ {s['vh_arm_max']:.2f} mm)"]
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
