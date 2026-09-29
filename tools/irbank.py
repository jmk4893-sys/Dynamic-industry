"""IR 뱅크 복사 유속 — 면내 온도편차는 여기서 정해진다.

1차원 열해석이 답한 것은 **두께 방향**이다. 적층이 4.62 mm 라 열적으로
얇고, 계면은 덩어리 해보다 1.8 초 늦게 140 ℃ 에 닿는다. 거기까지는 좋다.

그런데 유리를 깨는 것은 두께 방향이 아니라 **면내 편차**다. 중앙이 뜨겁고
가장자리가 차면 가장자리가 인장을 받는다 (σ ≈ ½·Eα·ΔT). 허용 7 MPa 에서
그 한계가 21 K 이고, 1차원 해석은 이 값을 **원리적으로** 못 낸다 —
램프 배치와 반사면이 정하기 때문이다. 그것을 여기서 푼다.

    ① 유한 선원의 조사도            닫힌해가 있다 (아래 유도)
    ② 반사판·벽면 = 거울상          정반사 이미지로 세운다
    ③ 면내 2차원 과도 전도          유속 분포 → 온도장

**핵심은 ③ 이 ① 을 거의 평활화하지 못한다는 것이다.** 면내 유효
확산계수는 α = (k·t)유리 / (ρc·t)적층 = 3.7e-7 m²/s 이고, 소킹 222 초의
확산길이는 √(αt) = 9 mm 다. 램프 피치는 400 mm 대다. **유속 분포가 그대로
온도 분포가 된다** — 전도가 구해 주지 않는다.

셀(실리콘)의 k·t 가 유리의 10 배지만 그것을 쓰지 않는다. 셀은 156 mm
웨이퍼가 2 mm 간격으로 떨어져 있고 탭 리본만 잇는다 — 셀 **안에서는**
평활하지만 셀을 **건너서는** 전도하지 않는다. 연속체로 놓으면 있지도 않은
평활화를 계산에 넣게 된다.

── 유한 선원의 닫힌해 ─────────────────────────────────────────────
길이 L, 총출력 P 인 관형 램프를 등방 선원으로 본다. 축이 y 를 따라
(y₀…y₁), 높이 h, 패널점과의 x 오프셋 dx 일 때 a² = dx² + h² 이고

    E = P/L · h/(4π a²) · [ u / √(u² + a²) ]  (u = y₁−p_y … y₀−p_y)

수치적분을 쓸 이유가 없다. 램프 수 × 격자점마다 도는 계산이라 닫힌해와
적분의 차이가 초 단위로 벌어진다.
"""

from __future__ import annotations

import math
import pathlib
import sys
from typing import NamedTuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from console_consts import const as c  # noqa: E402

# ── 형상 — 콘솔에서 가져온다 ────────────────────────────────────────
PANEL_L, PANEL_W = c("PANEL_L"), c("PANEL_W")       # 2.40 × 1.20 m
DECK_L, DECK_W = c("DECK_L"), c("DECK_W")           # 2.78 × 1.48 m
BANK_GAP = c("CDECK_DZ") / 2                        # 0.31 m 뱅크↔패널
LAMP_LEN = c("LAMP_HEAT")                           # m 발열장 — 콘솔 LAMP_HEAT (카탈로그 P-002-18)
LAMP_KW = 2.5
DECKS, LAMPS = int(c("DECKS")), int(c("LAMPS"))

# 내부 공동 — 4겹 벽(약 130 mm)을 뺀 반사 경계
CAVITY_L = c("DECK_L") + 2 * c("CL_WALL") + c("CL_DOOR") - 0.26   # 3.52 m
CAVITY_W = c("RACK_W") - 0.26                                     # 2.30 m

RHO_REFLECTOR = 0.85        # AL 반사판 (뱅크 캐리어 안쪽)
REFLECTOR_GAP = 0.040       # m 램프 축에서 반사판까지
RHO_WALL = 0.80             # 연마 STS304 #400 — ε 0.2 의 나머지


class Lamp(NamedTuple):
    """축이 y 를 따라 놓인 관형 램프. x 는 길이방향 위치, z 는 패널 위 높이."""

    x: float
    z: float
    kw: float = LAMP_KW
    length: float = LAMP_LEN
    weight: float = 1.0         # 이미지 램프의 감쇠 (반사율 곱)
    yc: float = 0.0             # 축의 중심 (폭방향 이미지가 여기를 옮긴다)

    def irradiance(self, px: float, py: float) -> float:
        """패널점 (px, py) 의 수평면 조사도 W/m²."""
        h = self.z
        if h <= 0:
            return 0.0
        dx = px - self.x
        a2 = dx * dx + h * h
        u1 = (self.yc - self.length / 2) - py
        u2 = (self.yc + self.length / 2) - py
        f = (u2 / math.sqrt(u2 * u2 + a2)) - (u1 / math.sqrt(u1 * u1 + a2))
        return self.kw * 1000 / self.length * h / (4 * math.pi * a2) * f * self.weight


def images(lamps: list[Lamp], rho_wall: float = RHO_WALL,
           rho_refl: float = RHO_REFLECTOR, order: int = 2) -> list[Lamp]:
    """직접광 + 반사판 + 벽면 거울상.

    반사판은 램프 바로 위에 있으므로 이미지가 거의 겹친다 — 위로 가던
    반이 아래로 돌아온다는 뜻이고, 그것이 반사판이 하는 일 전부다.

    벽면은 정반사로 놓는다. 실제 연마 STS 는 확산이 섞여 있어 이 모델은
    가장자리 보상을 **과대평가**한다. 그래서 rho_wall=0 (반사 없음) 을
    함께 낸다 — 진짜 값은 그 사이에 있고, 파일럿이 어디인지 정한다.
    """
    out = []
    for lp in lamps:
        out.append(lp)
        if rho_refl:
            out.append(lp._replace(z=lp.z + 2 * REFLECTOR_GAP,
                                   weight=lp.weight * rho_refl))
    if not rho_wall:
        return out

    base = list(out)
    half_l, half_w = CAVITY_L / 2, CAVITY_W / 2
    for lp in base:
        for k in range(1, order + 1):
            w = rho_wall ** k
            # 길이방향 두 끝벽 — x 를 접는다
            for s in (+1, -1):
                out.append(lp._replace(x=s * 2 * half_l * k - lp.x if k % 2
                                       else lp.x + s * 2 * half_l * k,
                                       weight=lp.weight * w))
            # 폭방향 두 측벽 — 축의 중심을 접는다
            for s in (+1, -1):
                out.append(lp._replace(yc=s * 2 * half_w * k - lp.yc if k % 2
                                       else lp.yc + s * 2 * half_w * k,
                                       weight=lp.weight * w))
    return out


# ── 유속장 ──────────────────────────────────────────────────────────
class Field(NamedTuple):
    xs: list
    ys: list
    E: list            # [ix][iy] W/m²

    @property
    def flat(self):
        return [v for row in self.E for v in row]

    @property
    def mean(self):
        f = self.flat
        return sum(f) / len(f)

    @property
    def spread(self):
        """(최대−최소)/평균 — 이것이 그대로 온도 편차 비율이 된다."""
        f = self.flat
        return (max(f) - min(f)) / (sum(f) / len(f))

    def scaled(self, total_w: float):
        """면적 적분이 total_w 가 되도록 배율을 건다.

        총량은 1차원 열수지가 이미 정했다 (장당 13 kW). 이 해석이 더하는
        것은 **모양**이지 크기가 아니다 — 두 모델이 같은 에너지를 쓰게
        묶어 두지 않으면 계면 온도가 두 벌이 된다.
        """
        area = PANEL_L * PANEL_W
        s = total_w / (self.mean * area)
        return Field(self.xs, self.ys, [[v * s for v in row] for row in self.E])


def field(lamps: list[Lamp], nx: int = 61, ny: int = 31) -> Field:
    """패널 면적 위의 조사도 격자."""
    xs = [-PANEL_L / 2 + PANEL_L * i / (nx - 1) for i in range(nx)]
    ys = [-PANEL_W / 2 + PANEL_W * j / (ny - 1) for j in range(ny)]
    E = [[sum(lp.irradiance(x, y) for lp in lamps) for y in ys] for x in xs]
    return Field(xs, ys, E)


# ── 배치 ────────────────────────────────────────────────────────────
def even(n: int, span: float, z: float = BANK_GAP, kw: float = LAMP_KW,
         length: float = LAMP_LEN):
    """현재 설계 — 지정 폭에 균등 배치. 콘솔 도면이 이렇게 그린다."""
    if n == 1:
        return [Lamp(0.0, z, kw, length)]
    return [Lamp(-span / 2 + span * i / (n - 1), z, kw, length)
            for i in range(n)]


def from_positions(xs: list, z: float = BANK_GAP, kw: float = LAMP_KW,
                   length: float = LAMP_LEN):
    return [Lamp(x, z, kw, length) for x in xs]


def two_banks(n_lo: int, n_hi: int, span: float, stagger: bool = False):
    """패널은 아래 뱅크와 위 뱅크를 함께 본다. 둘 다 310 mm 다.

    stagger 면 위 뱅크를 반피치 옮긴다 — 두 뱅크가 같은 자리에 있으면
    맥놀이가 서로를 **키우고**, 어긋나면 서로를 지운다. 돈이 들지 않는
    유일한 개선책이라 반드시 확인한다.
    """
    lo = even(n_lo, span)
    off = (span / (n_hi - 1) / 2) if (stagger and n_hi > 1) else 0.0
    hi = [lp._replace(x=lp.x + off) for lp in even(n_hi, span)]
    return lo + hi


# ── 면내 과도 전도 ──────────────────────────────────────────────────
K_GLASS, RHO_GLASS = 1.00, 2500.0
T_GLASS = c("MASS_GLASS") / RHO_GLASS               # 3.2 mm
KT_PLATE = K_GLASS * T_GLASS                        # W/K 면내 전도 (유리만)
CP_AREAL = c("AREAL_CP") * 1000                     # J/(m²·K)


def temperature(f: Field, dwell: float, t0: float = None, dt: float = 1.0):
    """유속장을 면내 2차원 과도 전도로 풀어 온도장을 낸다.

    (ρc·t) ∂T/∂t = (k·t) ∇²T + E.  양해법으로 충분하다 — 안정한계
    dt < dx²/(4α) 가 α 3.7e-7 · dx 40 mm 에서 1,080 초라 소킹 전체보다
    길다. 이 사실 자체가 **전도가 평활화를 못 한다**는 뜻이다.
    """
    t0 = c("T_AMB") if t0 is None else t0
    nx, ny = len(f.xs), len(f.ys)
    dx = f.xs[1] - f.xs[0]
    dy = f.ys[1] - f.ys[0]
    T = [[float(t0)] * ny for _ in range(nx)]
    steps = max(1, int(round(dwell / dt)))
    cx = KT_PLATE / (dx * dx) / CP_AREAL * dt
    cy = KT_PLATE / (dy * dy) / CP_AREAL * dt
    src = [[f.E[i][j] / CP_AREAL * dt for j in range(ny)] for i in range(nx)]
    for _ in range(steps):
        N = [row[:] for row in T]
        for i in range(nx):
            im, ip = max(i - 1, 0), min(i + 1, nx - 1)
            Ti, Tm, Tp = T[i], T[im], T[ip]
            Ni, si = N[i], src[i]
            for j in range(ny):
                jm, jp = max(j - 1, 0), min(j + 1, ny - 1)
                Ni[j] = (Ti[j] + cx * (Tm[j] - 2 * Ti[j] + Tp[j])
                         + cy * (Ti[jm] - 2 * Ti[j] + Ti[jp]) + si[j])
        T = N
    return T


def soak_to_cold(f: Field, target: float = 140.0, dt: float = 2.0,
                 t0: float = None, t_max: float = 900.0):
    """**냉점**이 target 에 닿을 때까지 데우고 그 시각과 온도장을 낸다.

    운전 규칙이 이것이다. 평균이 140 이면 되는 것이 아니라 **가장 찬
    곳**이 140 에 닿아야 거기서도 칼날이 들어간다. 그래서 면내 편차는
    두 곳을 동시에 친다 — 체류시간이 늘고(처리량), 중앙이 넘친다(백시트).

    이분법으로 26 번 다시 풀다가 한 번에 끝내도록 고쳤다. 어차피
    한 방향으로만 데워지므로 지나가는 길에 시각을 읽으면 된다.
    """
    t0 = c("T_AMB") if t0 is None else t0
    nx, ny = len(f.xs), len(f.ys)
    dx, dy = f.xs[1] - f.xs[0], f.ys[1] - f.ys[0]
    T = [[float(t0)] * ny for _ in range(nx)]
    cx = KT_PLATE / (dx * dx) / CP_AREAL * dt
    cy = KT_PLATE / (dy * dy) / CP_AREAL * dt
    src = [[f.E[i][j] / CP_AREAL * dt for j in range(ny)] for i in range(nx)]
    prev_min, t, P = t0, 0.0, T
    for _ in range(int(t_max / dt)):
        P = T
        N = [row[:] for row in T]
        for i in range(nx):
            im, ip = max(i - 1, 0), min(i + 1, nx - 1)
            Ti, Tm, Tp, Ni, si = T[i], T[im], T[ip], N[i], src[i]
            for j in range(ny):
                jm, jp = max(j - 1, 0), min(j + 1, ny - 1)
                Ni[j] = (Ti[j] + cx * (Tm[j] - 2 * Ti[j] + Tp[j])
                         + cy * (Ti[jm] - 2 * Ti[j] + Ti[jp]) + si[j])
        T = N
        t += dt
        cur = min(min(r) for r in T)
        if cur >= target:
            frac = (target - prev_min) / (cur - prev_min) if cur > prev_min else 1.0
            # 시각만 보간하고 온도장은 한 스텝 뒤의 것을 주면 냉점이 target 을
            # 넘어 있다 — 유속이 높을수록 더. 장도 같은 비율로 보간한다.
            Ti = [[P[a][b] + frac * (T[a][b] - P[a][b]) for b in range(ny)] for a in range(nx)]
            return t - dt * (1 - frac), Ti
        prev_min = cur
    return t, T


def stats(T):
    f = [v for row in T for v in row]
    nx, ny = len(T), len(T[0])
    return dict(
        tmax=max(f), tmin=min(f), tmean=sum(f) / len(f),
        spread=max(f) - min(f),
        centre=T[nx // 2][ny // 2],
        edge=min(min(T[0]), min(T[-1]), min(r[0] for r in T),
                 min(r[-1] for r in T)),
    )


# ── 배치 최적화 ─────────────────────────────────────────────────────
def _nelder_mead(fn, x0, step=0.05, iters=400, tol=1e-7):
    """네이더–미드. 배치 변수가 서너 개라 이걸로 충분하다."""
    n = len(x0)
    pts = [list(x0)]
    for i in range(n):
        p = list(x0)
        p[i] += step
        pts.append(p)
    vals = [fn(p) for p in pts]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: vals[i])
        pts = [pts[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) < tol:
            break
        cen = [sum(p[i] for p in pts[:-1]) / n for i in range(n)]
        ref = [cen[i] + (cen[i] - pts[-1][i]) for i in range(n)]
        fr = fn(ref)
        if fr < vals[0]:
            exp = [cen[i] + 2 * (cen[i] - pts[-1][i]) for i in range(n)]
            fe = fn(exp)
            pts[-1], vals[-1] = (exp, fe) if fe < fr else (ref, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = ref, fr
        else:
            con = [cen[i] + 0.5 * (pts[-1][i] - cen[i]) for i in range(n)]
            fc = fn(con)
            if fc < vals[-1]:
                pts[-1], vals[-1] = con, fc
            else:
                for k in range(1, n + 1):
                    pts[k] = [pts[0][i] + 0.5 * (pts[k][i] - pts[0][i])
                              for i in range(n)]
                    vals[k] = fn(pts[k])
    i = min(range(n + 1), key=lambda k: vals[k])
    return pts[i], vals[i]


def optimize(n: int, rho_wall: float = RHO_WALL, span_max: float = None,
             length: float = LAMP_LEN, stagger: bool = False):
    """램프 n 개의 위치를 면내 편차가 최소가 되게 잡는다.

    중앙 대칭으로 놓고 절반만 변수로 쓴다. 홀수면 가운데 하나는 x=0 에
    고정 — 대칭을 깨면 최적점이 두 벌이 되어 수렴이 흔들린다.

    변수는 **간격의 누적**이다. 위치를 직접 변수로 쓰면 최적화 중에 두
    램프가 자리를 바꿔 버리고, 그러면 도면으로 못 옮긴다.
    """
    span_max = span_max or (DECK_L - 0.10)
    half = n // 2
    def build(v):
        d = [abs(t) + 0.02 for t in v]                 # 간격은 양수 · 최소 20 mm
        pos, acc = [], 0.0
        for gap in d:
            acc += gap
            pos.append(acc)
        lim = span_max / 2
        if pos and pos[-1] > lim:                      # 공동 밖으로 못 나간다
            pos = [p * lim / pos[-1] for p in pos]
        xs = sorted([-p for p in pos] + ([0.0] if n % 2 else []) + pos)
        return xs

    def cost(v):
        xs = build(v)
        lam = from_positions(xs, length=length)
        if stagger:                       # 위 뱅크를 반피치 옮긴 것까지 함께 본다
            gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
            off = (sum(gaps) / len(gaps) / 2) if gaps else 0.0
            lam = lam + [lp._replace(x=lp.x + off) for lp in lam]
        return field(images(lam, rho_wall), 41, 21).spread

    x0 = [span_max / 2 / max(half, 1)] * half
    best, val = _nelder_mead(cost, x0, step=0.03)
    return build(best), val


def optimize_power(xs: list, rho_wall: float = RHO_WALL,
                   length: float = LAMP_LEN, floor: float = 0.35):
    """**존 출력 제어** — 위치를 고정하고 램프별 듀티를 잡는다.

    배치만으로는 창이 안 닫힌다. 냉점을 140 ℃ 에 올리는 순간 중앙이
    백시트 융점을 넘고, 그 창은 165−140−7 = 18 K 뿐이다. 유속으로
    ±6 % 를 지키라는 뜻인데, 이산 선원 일곱 개로는 무리다.

    산업용 IR 로가 이 문제를 푸는 방법은 기하가 아니라 **제어**다.
    SSR 위상제어는 정격에서 **내릴** 수만 있으므로 가장자리를 올리는 것이
    아니라 가운데를 내린다 — 총출력이 줄고 체류가 늘어난다. 그 대가가
    택트 안에 들어가는지가 이 함수가 답할 것이다.

    콘솔이 이미 '램프 라인별 CT·SSR 피드백' 을 들고 있다. 없던 장치를
    새로 넣는 것이 아니라, 있는 장치가 **무엇을 해야 하는지**를 정한다.
    """
    n = len(xs)
    half = (n + 1) // 2

    def duties(v):
        """대칭 듀티. 홀수면 가운데를 한 번만 쓴다.

        처음에 `d[::-1][:n//2]` 로 접었다가 양 끝이 서로 다른 듀티를
        받았다 — 대칭이라고 부르면서 대칭이 아니었고, 최적화는 그
        비대칭을 없애느라 전부 1.0 으로 돌아갔다. 접는 자리를 틀리면
        최적화가 아무 일도 안 한 것처럼 보인다.
        """
        d = [floor + (1 - floor) / (1 + math.exp(-t)) for t in v]
        return d + (d[-2::-1] if n % 2 else d[::-1])

    def build(v):
        d = duties(v)
        return [Lamp(x, BANK_GAP, LAMP_KW * du, length)
                for x, du in zip(xs, d)]

    def cost(v):
        f = field(images(build(v), rho_wall), 41, 21)
        # 균일도가 목적이지만 총출력이 떨어지면 체류가 늘어난다 —
        # 듀티 평균을 약하게 끌어올려 '전부 꺼서 균일하게' 를 막는다.
        duty = sum(duties(v)) / n
        return f.spread + 0.15 * (1 - duty)

    best, _ = _nelder_mead(cost, [1.0] * half, step=0.6, iters=600)
    d = duties(best)
    return build(best), d, sum(d) / n
