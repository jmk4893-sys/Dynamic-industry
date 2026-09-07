"""열해석기 — 1차원 과도 열전도 유한차분.

콘솔의 열모델은 **덩어리 에너지수지**다.

    q = 면적 × 8.7359 × (140−25)      kJ/장
    t열 = max(5q/유효출력, FDM 113.2초)

이것은 "패널 한 장을 데우는 데 몇 MJ 가 드는가" 는 답한다. 답하지
**못하는** 것이 하나 있다 — 그 열이 EVA/유리 계면까지 실제로 내려가는가.
덩어리 모델에는 두께가 없어서 계면이라는 자리 자체가 없다. 위 식의
`fdmDwell:113.15` 는 그래서 근거 없이 적혀 있던 숫자다. 여기서 그것을
푼다.

푸는 방식은 **절점을 층 경계에 두는 제어체적법**이다. 절점이 경계에
있어야 계면 온도를 보간 없이 읽는다 — 그것이 이 해석의 목적이다.

    ┌──────┬──────┬──────┐
    ●──────●──────●──────●        ● 절점 (경계·내부)
    │  셀  │  셀  │  셀  │        셀 = 전도저항 dx/k
    양단 절점은 반쪽 셀만 가진다 (열용량 ½)

시간적분은 **후진오일러(음해법)** 다. 양해법은 dt < dx²/2α 를 넘기면
발산한다 — 유리 3.2 mm 를 8분할하면 dx=0.4 mm, α=5.3e-7 에서 한계
dt 가 0.15 초다. 222 초를 1,500 스텝 밟아야 한다. 음해법은 그 제약이
없다. 대신 매 스텝 삼중대각 연립을 푼다 (Thomas).

복사 경계는 T⁴ 이라 비선형이다. 스텝 안에서 두 번 반복해 h_r 을
갱신한다 — 한 번만 하면 승온이 빠른 구간에서 표면온도가 뒤처진다.

**검증 없는 해석기는 계산기가 아니라 난수 발생기다.** validate() 가
닫힌해 다섯 건과 맞춘다. 통과하지 않으면 아래 결과를 믿지 않는다.
"""

from __future__ import annotations

import math
from typing import Callable, NamedTuple

import numpy as np

SIGMA = 5.670374419e-8          # W/(m²·K⁴) 슈테판–볼츠만


# ── 층과 격자 ────────────────────────────────────────────────────────
class Layer(NamedTuple):
    """한 겹. k 는 상수이거나 평균온도의 함수 (미네랄울·공기층)."""

    name: str
    t: float                            # m
    k: float | Callable[[float], float]  # W/(m·K)
    rho: float                          # kg/m³
    cp: float                           # J/(kg·K)
    n: int = 4                          # 분할 수

    def kk(self, tm: float) -> float:
        return self.k(tm) if callable(self.k) else self.k

    @property
    def rcp(self) -> float:
        return self.rho * self.cp       # J/(m³·K)


class Stack:
    """층을 쌓고 절점을 만든다. 절점 좌표·열용량·셀 소속을 들고 있다."""

    def __init__(self, *layers: Layer):
        if not layers:
            raise ValueError("층이 없다")
        self.layers = list(layers)
        x, self.cell = [0.0], []        # cell[i] = (층, dx) — 절점 i↔i+1 사이
        for ly in self.layers:
            dx = ly.t / ly.n
            for _ in range(ly.n):
                x.append(x[-1] + dx)
                self.cell.append((ly, dx))
        self.x = np.array(x)
        self.N = len(self.x)

        # 절점 열용량 — 양옆 반쪽 셀의 합. 층이 바뀌는 절점은 두 재질이 섞인다.
        C = np.zeros(self.N)
        for i, (ly, dx) in enumerate(self.cell):
            C[i] += ly.rcp * dx / 2
            C[i + 1] += ly.rcp * dx / 2
        self.C = C                      # J/(m²·K)

    @property
    def thickness(self) -> float:
        return float(self.x[-1])

    @property
    def areal_cp(self) -> float:
        """면적 열용량 kJ/(m²·K) — 콘솔의 arealCp 와 같은 양."""
        return float(self.C.sum()) / 1000.0

    def index(self, name: str, side: str = "front") -> int:
        """층 경계 절점의 번호. side='front' 는 그 층의 입구쪽 면."""
        i = 0
        for ly in self.layers:
            if ly.name == name:
                return i if side == "front" else i + ly.n
            i += ly.n
        raise KeyError(name)

    def conductance(self, T: np.ndarray) -> np.ndarray:
        """셀별 전도 컨덕턴스 W/(m²·K). k(T) 인 층은 셀 평균온도로 잡는다."""
        G = np.empty(len(self.cell))
        for i, (ly, dx) in enumerate(self.cell):
            G[i] = ly.kk((T[i] + T[i + 1]) / 2) / dx
        return G


# ── 경계조건 ─────────────────────────────────────────────────────────
class BC(NamedTuple):
    """한쪽 면의 경계. 셋을 겹쳐 쓸 수 있다 — 흡수유속 + 대류 + 복사.

    fixed 가 있으면 그것만 쓴다 (온도 규정).
    """

    q: float = 0.0          # W/m² 흡수 유속 (양수 = 들어온다)
    h: float = 0.0          # W/(m²·K) 대류
    t_inf: float = 25.0     # °C 주위 유체
    eps: float = 0.0        # 방사율
    t_rad: float = 25.0     # °C 복사 상대면
    fixed: float | None = None   # °C 규정온도

    def flux(self, ts: float) -> tuple[float, float]:
        """(선형화된 유속의 상수항, 계수) — q_net = a − b·Ts.

        복사는 h_r = εσ(Ts²+Tr²)(Ts+Tr) 로 선형화한다. Ts 는 직전 값이고
        스텝 안에서 한 번 갱신한다.
        """
        a = self.q + self.h * self.t_inf
        b = self.h
        if self.eps:
            Ks, Kr = ts + 273.15, self.t_rad + 273.15
            hr = self.eps * SIGMA * (Ks * Ks + Kr * Kr) * (Ks + Kr)
            a += hr * self.t_rad
            b += hr
        return a, b


ADIABATIC = BC()


# ── 풀이 ─────────────────────────────────────────────────────────────
def _thomas(a, b, c, d):
    """삼중대각 연립 — a 하부, b 대각, c 상부, d 우변."""
    n = len(b)
    cp, dp = np.empty(n), np.empty(n)
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = (c[i] / m) if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = np.empty(n)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


class Run(NamedTuple):
    t: np.ndarray               # s
    T: np.ndarray               # [스텝, 절점] °C
    stack: Stack

    def at(self, node: int) -> np.ndarray:
        return self.T[:, node]

    def when(self, node: int, temp: float) -> float | None:
        """그 절점이 temp 에 처음 닿는 시각. 끝까지 못 닿으면 None."""
        v = self.T[:, node]
        for i in range(1, len(v)):
            if (v[i] - temp) * (v[0] - temp) <= 0 and v[i] != v[i - 1]:
                f = (temp - v[i - 1]) / (v[i] - v[i - 1])
                return float(self.t[i - 1] + f * (self.t[i] - self.t[i - 1]))
        return None

    @property
    def final(self) -> np.ndarray:
        return self.T[-1]


def solve(stack: Stack, left: BC, right: BC, t0, dt: float, t_end: float,
          gen: np.ndarray | None = None, keep: int = 400) -> Run:
    """후진오일러로 적분한다.

    t0  초기온도 — 스칼라 또는 절점 배열
    gen 절점당 내부발열 W/m² (선택)
    keep 저장할 스텝 수 상한 — 그 이상이면 솎아 담는다
    """
    N = stack.N
    T = np.full(N, float(t0)) if np.isscalar(t0) else np.array(t0, float)
    steps = max(1, int(round(t_end / dt)))
    every = max(1, steps // keep)
    ts, hist = [0.0], [T.copy()]
    q = np.zeros(N) if gen is None else np.array(gen, float)

    for s in range(steps):
        Tn = T
        Tg = T.copy()                       # 비선형(복사·k(T)) 갱신용 추정치
        for _ in range(2):
            G = stack.conductance(Tg)
            a = np.zeros(N); b = np.zeros(N); c = np.zeros(N)
            d = stack.C / dt * Tn + q
            b += stack.C / dt
            for i in range(N - 1):
                b[i] += G[i]; c[i] = -G[i]
                b[i + 1] += G[i]; a[i + 1] = -G[i]
            for node, bc in ((0, left), (N - 1, right)):
                if bc.fixed is not None:
                    a[node] = c[node] = 0.0
                    b[node] = 1.0
                    d[node] = bc.fixed
                else:
                    ca, cb = bc.flux(Tg[node])
                    d[node] += ca
                    b[node] += cb
            Tg = _thomas(a, b, c, d)
        T = Tg
        if (s + 1) % every == 0 or s == steps - 1:
            ts.append((s + 1) * dt)
            hist.append(T.copy())
    return Run(np.array(ts), np.array(hist), stack)


def steady(stack: Stack, left: BC, right: BC, t0=25.0,
           tol: float = 1e-5, chunks: int = 60) -> np.ndarray:
    """정상상태 — 큰 dt 로 변화가 멎을 때까지 돌린다.

    시상수를 미리 어림해 "그 몇 배만 돌리자" 로 짰다가 틀렸다. 전도만
    보고 잡은 시상수가 13 초였는데 실제 시상수는 표면저항 1/h 가 지배해
    2,700 초였다 — 정상해의 36 %에서 멈춘 값을 정상상태라고 답했다.
    검증 ⑤ 가 그것을 64 % 오차로 잡았다. 그래서 어림하지 않고 **멎을
    때까지** 돌린다.
    """
    T = np.full(stack.N, float(t0)) if np.isscalar(t0) else np.array(t0, float)
    dt = stack.C.sum() / max(stack.conductance(T).min(), 1e-9)
    for _ in range(chunks):
        r = solve(stack, left, right, T, dt, dt * 20, keep=2)
        move = float(np.abs(r.final - T).max())
        T = r.final
        if move < tol:
            break
        dt *= 2.0
    return T


# ── 재료 ─────────────────────────────────────────────────────────────
def air_gap(t: float, eps_hot: float = 0.05, eps_cold: float = 0.90,
            name: str = "공기층") -> Layer:
    """수직 공기층 — 전도 + 복사를 등가 k 로 묶는다.

    복사가 지배하므로 방사율이 전부다. 저방사 AL 반사판(ε 0.05)과 도장
    강판(ε 0.90) 이 마주보면 등가 방사율은 1/(1/0.05+1/0.90−1)=0.0497 —
    양쪽 다 도장강판일 때(0.82)의 **1/16** 이다. 반사판이 일하는 자리가
    여기다. 대신 공기층이 없으면 반사판은 단열재에 눌려 아무 일도 못 한다.

    자연대류는 Ra 로 판단한다 — 25 mm 폭에서는 Nu≈1 (전도) 근처라
    보수적으로 Nu 1.3 을 곱한다.
    """
    ee = 1.0 / (1.0 / eps_hot + 1.0 / eps_cold - 1.0)

    def k_eff(tm: float) -> float:
        K = tm + 273.15
        k_air = 0.0242 * (K / 273.15) ** 0.8            # 공기 전도도
        hr = ee * SIGMA * 4 * K ** 3                     # dT 가 작을 때의 접선
        return k_air * 1.3 + hr * t

    return Layer(name, t, k_eff, 1.2, 1005.0, 1)


def wool(t: float, rho: float = 100.0, n: int = 6, name: str = "미네랄울") -> Layer:
    """미네랄울 — k 가 온도를 심하게 탄다. 상온 값으로 잡으면 손실을 낮게 본다.

    100 kg/m³ 급: k ≈ 0.036 + 0.00016·(T−20) W/(m·K) — 300 ℃ 에서 상온의
    2.2 배다. 벽 안쪽이 140 ℃ 이므로 이 기울기를 빼면 안 된다.
    """
    return Layer(name, t, lambda tm: 0.036 + 0.00016 * max(tm - 20.0, 0.0),
                 rho, 840.0, n)


# ── 검증 ─────────────────────────────────────────────────────────────
def validate() -> list[tuple[str, float, float, float]]:
    """닫힌해가 있는 문제로 해석기를 검증한다. (이름, 해석값, 닫힌해, 오차)"""
    out = []

    # ① 반무한체 표면온도 계단 — T(x,t) = Ts + (Ti−Ts)·erf(x/2√(αt))
    k, rho, cp = 50.0, 7850.0, 460.0
    al = k / (rho * cp)
    L, x, t = 0.5, 0.020, 100.0
    st = Stack(Layer("강", L, k, rho, cp, n=500))
    r = solve(st, BC(fixed=400.0), ADIABATIC, 0.0, 0.05, t, keep=2)
    got = float(np.interp(x, st.x, r.final))
    want = 400.0 + (0.0 - 400.0) * math.erf(x / (2 * math.sqrt(al * t)))
    out.append(("반무한체 계단응답 (erf)", got, want, abs(got - want) / want))

    # ② 다층벽 정상상태 — q = ΔT/ΣR, 계면온도까지
    lys = (Layer("A", 0.010, 50.0, 7850, 460, 2),
           Layer("B", 0.100, 0.040, 100, 840, 8),
           Layer("C", 0.003, 16.0, 7900, 500, 2))
    st = Stack(*lys)
    hi, ho, ti, to = 10.0, 25.0, 200.0, 20.0
    Tf = steady(st, BC(h=hi, t_inf=ti), BC(h=ho, t_inf=to), t0=100.0)
    R = 1 / hi + sum(ly.t / ly.k for ly in lys) + 1 / ho
    qw = (ti - to) / R
    got = float(Tf[st.index("B", "back")])              # B/C 계면
    want = to + qw * (1 / ho + lys[2].t / lys[2].k)
    out.append(("다층벽 정상 계면온도", got, want, abs(got - want) / want))

    # ③ 덩어리 냉각 (Bi≪0.1) — T = T∞ + (T0−T∞)e^(−hA t/ρVc)
    th, kk, rr, cc, h = 0.004, 200.0, 2700.0, 900.0, 20.0
    st = Stack(Layer("판", th, kk, rr, cc, 4))
    r = solve(st, BC(h=h, t_inf=20.0), BC(h=h, t_inf=20.0), 300.0, 1.0, 600.0)
    got = float(r.final.mean())
    want = 20.0 + (300.0 - 20.0) * math.exp(-2 * h * 600.0 / (rr * cc * th))
    out.append(("덩어리 냉각 지수해", got, want, abs(got - want) / want))

    # ④ 평판 급냉 1항 급수해 — Bi=1 → ζ₁=0.860334, C₁=1.11913
    half, kk, al2 = 0.05, 40.0, 1.0e-5
    rr = 8000.0
    cc = kk / (al2 * rr)
    h = 1.0 * kk / half                                  # Bi = hL/k = 1
    fo = 0.5
    tend = fo * half * half / al2
    st = Stack(Layer("판", 2 * half, kk, rr, cc, 40))
    r = solve(st, BC(h=h, t_inf=0.0), BC(h=h, t_inf=0.0), 500.0, tend / 400, tend)
    got = float(r.final[st.N // 2])
    want = 500.0 * 1.11913 * math.exp(-0.860334 ** 2 * fo)
    out.append(("평판 급냉 1항 급수해", got, want, abs(got - want) / want))

    # ⑤ 규정유속 + 대류 — Ts = T∞ + q(1/h + t/k)
    th, kk, h, qf = 0.02, 15.0, 30.0, 5000.0
    st = Stack(Layer("판", th, kk, 7800, 500, 8))
    Tf = steady(st, BC(q=qf), BC(h=h, t_inf=25.0), t0=25.0)
    got = float(Tf[0])
    want = 25.0 + qf * (1 / h + th / kk)
    out.append(("규정유속 표면온도", got, want, abs(got - want) / want))

    return out


if __name__ == "__main__":
    print(f"{'검증':28s} {'해석':>12s} {'닫힌해':>12s} {'오차':>8s}")
    for name, got, want, err in validate():
        print(f"{name:28s} {got:12.4f} {want:12.4f} {err:7.2%}"
              f"  {'OK' if err < 0.02 else '★'}")
