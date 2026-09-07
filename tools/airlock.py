#!/usr/bin/env python3
"""에어록을 푼다 — 문의 **높이**가 이 설비의 성립 여부를 정한다 (열수지 RHB2).

열수지가 RHB2 를 남겼다: *에어록이 손실의 절반을 넘고 그 크기를 격리실
부피가 정하니, 한 단 높이로 줄일 수 있는지 확인하라 — 5.9 kW 가 걸려 있다.*

풀어 보니 **질문이 세 군데에서 어긋나 있었고, 답은 격리실이 아니었다.**

── ① 도면이 격리실의 유무를 두 곳에서 다르게 말한다 ────────────────
콘솔의 압축 배치는 챔버 양단에 `AL-101/102 · 이중셔터 에어록` 이라고
적어 두었는데, 같은 콘솔의 R-106 차이표는 REV.21C 를 이렇게 적는다:

    출입    REV.20 에어록 4문 → REV.21C **승강 포크 문형 2기**
    격리실  REV.20 420 × 2   → REV.21C **없음**
    밀폐    문 여는 동안에도 유지 → **포크 진입 중 챔버 열림**

**납품 배치에는 격리실이 없다.** 길이를 줄이면서 내준 것이고 R-106 주기가
그렇게 적어 두었다 — "그 순간의 배기를 배기 설계가 감당한다". 열수지는
그것을 모른 채 *있지도 않은 격리실* 의 부피를 세고 있었다.

── ② 격리실 부피를 문 포켓 깊이로 잡았다 ───────────────────────────
열수지는 격리 깊이를 `CL_DOOR` 0.30 m 로 놓았다. 그 방에는 **패널
2,400 mm 가 통째로 서야** 두 문을 다 닫을 수 있다. 0.30 m 짜리 격리실은
기하학적으로 있을 수 없다.

── ③ 같은 열을 두 번 셌다 ──────────────────────────────────────────
내문으로 챔버를 떠난 열과 외문으로 실온에 나간 열을 더했는데 **그것은 같은
열**이다. 정상 사이클로 물질수지를 세면 계가 들이마시는 것은 실온 공기
한 격리실 분이고 내쉬는 것은 같은 질량의 챔버 공기다:

    사이클당 손실 = V · ρ(실온) · cp · (T챔버 − T실온)      ← ΔT 는 한 번

── 그래서 실제 지배량은 무엇인가 ───────────────────────────────────
막다른 방이 아니면 교환량은 부피가 아니라 **개구를 지나는 부력 교환유동**이
정한다. 수직 개구의 중립면 적분이 닫힌해를 준다:

    v(z) = √(2 g z Δρ/ρ̄)                     중립면에서 z 만큼 떨어진 곳
    Q = Cd·w·∫₀^{h/2} v(z) dz = (1/3)·Cd·w·h^{3/2}·√(g Δρ/ρ̄)

계수 1/3 은 어림이 아니라 **적분에서 그대로 나온다.** 검증 ①이 그것을
수치적분으로 확인한다.

    **Q ∝ h^{3/2}** — 문의 높이가 1.5 제곱으로 들어온다.

그래서 답이 뒤집힌다. 격리실을 한 단 높이로 줄이는 것이 아니라 **개구를
패널이 지나는 포락선까지 줄이는 것**이 레버다. 전고 개구(4.09 m)를 단별
셔터(0.35 m)로 바꾸면 (4.09/0.35)^1.5 = **40 배**가 줄고, 격리실은
필요조차 없어진다 — 라인 길이도 그대로다.

**이 검토가 못 보는 것**: 문이 열리는 과도구간(교환유동이 정상값에
이르기까지 ~1 s), 챔버 부압 −20 Pa 이 만드는 유입 편향(안전측으로 무시),
포크와 패널이 개구를 부분적으로 막는 효과(안전측으로 무시), 실제 셔터
씰의 누설등급. 파일럿 PT-05 가 에어록 항을 분리 계측해 확정한다.
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import parts as PT  # noqa: E402
from analysis_thermal import Req, Result  # noqa: E402
from console_consts import const as c  # noqa: E402

G = 9.80665
CP_AIR = 1005.0
RHO_AIR = lambda t: 353.0 / (273.15 + t)     # kg/m³ 대기압 건공기

T_HOT, T_AMB = c("T_TARGET"), c("T_AMB")     # 140 · 25 ℃
DECKS = int(c("DECKS"))
TAKT = 53.6                                  # s 라인 사이클 (탠덤이 정한다)
N_DOOR = 2                                   # 사이클당 문 통과 — 방출 1 · 투입 1
RATED_KW = int(c("LAMPS")) * 2.5              # 100 kW 설치정격

# ── 개구 ─────────────────────────────────────────────────────────────
OPEN_W = c("DECK_W") + 0.20                  # 1.68 m 셔터 폭 (P-002-20)
FULL_H = c("CDECK_Z0") + c("CDECK_DZ") * (DECKS - 0.5) + 0.40   # 4.09 m 전고
DECK_H = c("CDECK_DZ")                       # 0.62 m 단 피치
CD = 0.62                                    # 큰 개구의 유출계수 (누설과 같은 값)

# 패널 통과 포락선 — 개구가 이보다 작을 수 없는 이유를 치수로 적는다.
FORK_T = 0.090                               # m 포크 두께 (콘솔 TS-101 형상)
PANEL_T = 0.005                              # m 패널
SET_DROP = 0.060                             # m 데크 레일에 내려놓는 하강량
OPEN_CLR = 0.050                             # m 상·하 여유
PASS_H = FORK_T + PANEL_T + SET_DROP + 2 * OPEN_CLR      # 0.255 m
OPEN_H = 0.35                                # m 확정 개구 — 포락선 + 여유

# ── 문이 열려 있는 시간 ──────────────────────────────────────────────
REACH = c("CL_DOOR") + c("CL_WALL") + c("DECK_L") / 2     # 2.04 m 문면 → 데크 중심
V_FORK = 0.50                                # m/s 2단 텔레스코픽 (적재 상태)
V_DOOR = 0.60                                # m/s 공압 셔터
DOOR_LAP = 0.10                              # m 개구 위 겹침 (씰 자리)
T_SET = 1.0                                  # s 내려놓기·위치핀 정합


def stroke(open_h: float = OPEN_H) -> float:
    """셔터 행정 — 개구를 완전히 비우고 겹침만큼 더 든다."""
    return open_h + DOOR_LAP


def open_time(open_h: float = OPEN_H) -> float:
    """문이 열려 있는 시간 = 여닫기 + 포크 왕복 + 내려놓기.

    **포크가 지배한다.** 셔터는 0.35 m 를 0.6 m/s 로 여닫아 1.5 초면 끝나는데
    포크는 2.04 m 를 두 번 간다. 문을 빨리 여는 투자보다 포크를 빨리 넣는
    투자가 손실을 줄인다 — 손실은 이 시간에 **선형**이다.
    """
    return 2 * stroke(open_h) / V_DOOR + 2 * REACH / V_FORK + T_SET


# ── 부력 교환유동 ────────────────────────────────────────────────────
def _buoyancy(t_hot: float = T_HOT, t_cold: float = T_AMB) -> float:
    """g' = g·Δρ/ρ̄ — 환산중력."""
    rh, rc = RHO_AIR(t_hot), RHO_AIR(t_cold)
    return G * (rc - rh) / ((rh + rc) / 2)


def exchange_flow(h: float, w: float = OPEN_W, t_hot: float = T_HOT,
                  t_cold: float = T_AMB, cd: float = CD) -> float:
    """수직 개구의 부력 교환유동 [m³/s] — 중립면 적분의 닫힌해.

        Q = (1/3)·Cd·w·h^{3/2}·√(g Δρ/ρ̄)

    한쪽 방향의 유량이다. 반대 방향으로 같은 부피가 지나간다.
    """
    return cd * w * h ** 1.5 * math.sqrt(_buoyancy(t_hot, t_cold)) / 3.0


def _flow_quad(h: float, w: float = OPEN_W, t_hot: float = T_HOT,
               t_cold: float = T_AMB, cd: float = CD, n: int = 20000) -> float:
    """같은 것을 수치적분으로 — 닫힌해를 검증하려고만 쓴다."""
    gp, half = _buoyancy(t_hot, t_cold), h / 2
    dz, s = half / n, 0.0
    for i in range(n):                       # 중점법
        z = (i + 0.5) * dz
        s += math.sqrt(2 * gp * z) * dz
    return cd * w * s


# ── 손실 ─────────────────────────────────────────────────────────────
def exchanged(h: float, t_open: float = None, vest: float = None) -> float:
    """한 번 여닫을 때 실제로 교환되는 부피 [m³] — 세 상한 중 가장 작은 것.

    ① 격리실 부피 — 막다른 방은 제 부피보다 많이 못 바꾼다
    ② 내문을 지나는 양 Q·t
    ③ 외문을 지나는 양 Q·t   (격리실이 없으면 문이 하나라 ①②만)

    열수지는 ① 만 보고 "문 크기도 여는 시간도 아니고 부피가 정한다" 고
    적었다. **그것은 격리실이 있고 부피가 작을 때만 참이다.** 격리실이
    없으면 ② 가 유일한 상한이고, 그때는 문 크기와 시간이 전부다.
    """
    t_open = open_time(h) if t_open is None else t_open
    caps = [exchange_flow(h) * t_open]
    if vest is not None:
        caps.append(vest)
    return min(caps)


def loss_kw(h: float, t_open: float = None, vest: float = None,
            n_door: int = N_DOOR, t_cold: float = T_AMB) -> float:
    """정상상태 손실 [kW].

        사이클당 = V · ρ(실온) · cp · (T챔버 − T실온) × 문 통과 횟수

    ΔT 가 **한 번만** 들어간다. 내문으로 나간 열과 외문으로 나간 열은 같은
    열이라, 더하면 같은 줄을 두 번 세는 것이다 (검증 ③).
    """
    v = exchanged(h, t_open, vest)
    j = v * RHO_AIR(t_cold) * CP_AIR * (T_HOT - t_cold)
    return j * n_door / TAKT / 1000.0


def height_for(budget_kw: float, t_open: float = None) -> float:
    """손실 예산을 만족하는 최대 개구 높이 [m] — Q ∝ h^{3/2} 를 뒤집는다."""
    t = open_time(OPEN_H) if t_open is None else t_open
    unit = loss_kw(1.0, t_open=t)            # h = 1 m 의 손실 (부피 상한 없음)
    return (budget_kw / unit) ** (2.0 / 3.0)


# ── 격리실 ───────────────────────────────────────────────────────────
VEST_D = c("PANEL_L") + 0.30                 # 2.70 m 두 문 사이 — 패널이 통째로 선다
VEST_ADD = c("PANEL_L")                      # 2.40 m 출력측에 새로 드는 길이


def vestibule(h: float) -> float:
    """격리실 자유부피 [m³] — 개구 높이가 격리실 높이를 정한다."""
    return VEST_D * OPEN_W * h


# ── 안 ───────────────────────────────────────────────────────────────
def options() -> list[dict]:
    """네 가지 안을 같은 식으로 세운다."""
    t_full, t_deck, t_open = open_time(FULL_H), open_time(DECK_H), open_time(OPEN_H)
    return [
        dict(key="A", name="현행 도면 — 전고 개구 · 격리실 없음",
             h=FULL_H, vest=None, t=t_full, add=0.0,
             why="포크가 어느 단에나 닿아야 하니 개구가 랙 전고다"),
        dict(key="B", name="단 피치 개구 · 격리실 없음",
             h=DECK_H, vest=None, t=t_deck, add=0.0,
             why="개구를 단 하나로 줄인다 — 카탈로그 실린더 행정이 가리키던 안"),
        dict(key="C", name="패널 포락선 개구 · 격리실 없음  ← 확정",
             h=OPEN_H, vest=None, t=t_open, add=0.0,
             why="포크와 패널이 지나갈 만큼만 연다. 단별 셔터 5장/단"),
        dict(key="D", name="패널 포락선 개구 + 격리실",
             h=OPEN_H, vest=vestibule(OPEN_H), t=t_open, add=VEST_ADD,
             why="C 에 이중문 격리실을 더한다 — 출력측 라인이 길어진다"),
    ]


def solve() -> list[dict]:
    out = []
    for o in options():
        d = dict(o)
        d["Q"] = exchange_flow(o["h"])
        d["V"] = exchanged(o["h"], o["t"], o["vest"])
        d["kw"] = loss_kw(o["h"], o["t"], o["vest"])
        d["cap"] = ("격리실 부피" if o["vest"] is not None
                    and o["vest"] <= exchange_flow(o["h"]) * o["t"] else "교환유동")
        out.append(d)
    return out


# ── 열수지가 쓰는 값 ─────────────────────────────────────────────────
def chosen() -> dict:
    """확정안 C — 열수지 OUT③ 이 이 값을 가져간다."""
    return [d for d in solve() if d["key"] == "C"][0]


def kw() -> float:
    return chosen()["kw"]


# ── 셔터 ─────────────────────────────────────────────────────────────
def shutters() -> dict:
    """단별 셔터 — 수량·판 크기·행정·씰 둘레.

    전고 셔터 2 장이 단별 셔터 `DECKS`×2 장이 된다. 장수는 늘지만 **총
    질량은 준다** — 판이 4,090 에서 0.45 로 짧아지기 때문이다.
    """
    plate_h = OPEN_H + 2 * DOOR_LAP
    n = DECKS * 2
    m_new = n * OPEN_W * plate_h * 0.0045 * 7850
    m_old = 2 * OPEN_W * FULL_H * 0.0045 * 7850
    return dict(n=n, plate_h=plate_h, stroke=stroke(), mass=m_new, mass_old=m_old,
                perim=n * 2 * (OPEN_W + plate_h),
                perim_old=2 * 2 * (OPEN_W + FULL_H))


# ── 검증 — 닫힌해 5 건 ───────────────────────────────────────────────
def _neutral_plane(h: float) -> float:
    """유입과 유출이 같아지는 중립면 높이를 이분법으로 찾는다.

    닫힌해는 중립면이 개구 중앙에 선다고 **가정**한다. 그 가정을 쓰지 않고
    "두 방향 부피유량이 같다" 만으로 풀어 h/2 가 나오는지 본다.
    """
    gp = _buoyancy()

    def flow(a, b):                          # a→b 구간의 부피유량 (부호 무시)
        n, dz, s = 4000, (b - a) / 4000, 0.0
        for i in range(n):
            s += math.sqrt(2 * gp * abs((a + (i + 0.5) * dz))) * dz
        return abs(s)

    lo, hi = 1e-6, h - 1e-6
    for _ in range(200):
        zn = (lo + hi) / 2
        up = flow(0.0, h - zn)               # 중립면 위 — 나가는 쪽
        dn = flow(0.0, zn)                   # 중립면 아래 — 들어오는 쪽
        if up > dn:
            lo = zn
        else:
            hi = zn
    return (lo + hi) / 2


def _mix_cycle(v: float, cycles: int = 200) -> tuple[float, float]:
    """두 단계 혼합을 실제로 돌려 사이클당 계 밖으로 나가는 열을 센다 [J].

    **이것이 ③ 의 요점이다.** 열수지는 내문 교환과 외문 교환을 더했다.
    여기서는 공기 덩어리를 따라가며 *계를 실제로 떠나는 것* 만 센다:

        A 내문 개방 — 격리실(T_v)이 챔버 공기(T챔버)로 통째 바뀐다.
          챔버는 질량이 늘어난 만큼을 배기로 밀어낸다 → 계를 떠난다.
        B 외문 개방 — 격리실(T챔버)이 실온 공기로 통째 바뀐다.
          나간 것이 계를 떠난다.

    두 몫을 합치면 `V·ρ(실온)·cp·ΔT` 하나가 되고, 열수지가 적은
    `V·ρ·cp·[(T챔버−T격리) + (T챔버−T실온)]` 는 그것을 넘는다.
    """
    t_v, e_out, naive = T_AMB, 0.0, 0.0
    dt = T_HOT - T_AMB
    for _ in range(cycles):
        # A 내문 — 격리실이 챔버 공기로 바뀐다. 챔버가 배기로 밀어내는 몫.
        e_out += v * (RHO_AIR(t_v) - RHO_AIR(T_HOT)) * CP_AIR * dt
        naive += v * RHO_AIR(T_HOT) * CP_AIR * (T_HOT - t_v)      # 열수지의 내문 항
        t_v = T_HOT
        # B 외문 — 격리실이 실온 공기로 바뀐다. 나간 것이 계를 떠난다.
        e_out += v * RHO_AIR(t_v) * CP_AIR * (t_v - T_AMB)
        naive += v * RHO_AIR(T_HOT) * CP_AIR * dt                 # 열수지의 외문 항
        t_v = T_AMB
    return e_out / cycles, naive / cycles


def _crossover(h: float, vest: float) -> float:
    """부피 상한이 걸리기 시작하는 문 열림 시간 — 이분법으로 찾는다."""
    lo, hi, q = 0.0, 1e4, exchange_flow(h)
    for _ in range(200):
        mid = (lo + hi) / 2
        if q * mid < vest:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def validate() -> list[tuple[str, float, float, float]]:
    rows = []

    def add(name, got, want):
        rows.append((name, got, want, abs(got - want) / abs(want) if want else 0.0))

    # ① 중립면 적분의 닫힌해 vs 수치적분 — 계수 1/3 이 적분에서 나오는가
    add("① 교환유동 닫힌해 vs 수치적분 [m³/s]",
        exchange_flow(FULL_H), _flow_quad(FULL_H))

    # ② 중립면 위치 — 가정하지 않고 유량 균형만으로 풀면 개구 중앙인가
    add("② 중립면 높이 [m] (유량균형으로 역산)",
        _neutral_plane(FULL_H), FULL_H / 2)

    # ③ 두 단계 혼합 시뮬레이션 — 계를 떠나는 열만 세면 닫힌해와 같은가
    v = 2.0
    add("③ 2 단계 혼합 시뮬레이션 vs 닫힌해 [kJ/회]",
        _mix_cycle(v)[0] / 1000.0,
        v * RHO_AIR(T_AMB) * CP_AIR * (T_HOT - T_AMB) / 1000.0)

    # ④ 이상기체 항등식 — ρ = 353/T 이면 Δρ/ρ̄ = ΔT/T̄ 가 **정확히** 성립한다
    tbar = (T_HOT + T_AMB) / 2 + 273.15
    add("④ Δρ/ρ̄ = ΔT/T̄ 항등식 [m³/s]", exchange_flow(FULL_H),
        CD * OPEN_W * FULL_H ** 1.5 * math.sqrt(G * (T_HOT - T_AMB) / tbar) / 3.0)

    # ⑤ 부피 상한과 유동 상한의 교차 시각 t* = v/Q
    h = OPEN_H
    q, vv = exchange_flow(h), vestibule(h)
    add("⑤ 상한 교차 시각 t* [s]", _crossover(h, vv), vv / q)
    return rows


# ── 검토 ─────────────────────────────────────────────────────────────
def budget(other_loss_kw: float, panel_kw: float, eta: float = 0.65) -> float:
    """에어록이 써도 되는 몫 — η 가정을 지키는 손실 예산에서 나머지를 뺀다."""
    return panel_kw * (1.0 / eta - 1.0) - other_loss_kw


def run(other_loss_kw: float = None, panel_kw: float = None):
    import heatbalance as HB
    if other_loss_kw is None or panel_kw is None:
        b = HB.balance()
        panel_kw = b["panel"]
        other_loss_kw = b["loss"] - b["airlock"]
    allow = budget(other_loss_kw, panel_kw)
    opts = solve()
    A, B, C, D = opts
    sh = shutters()
    h_max = height_for(allow)
    t_open = open_time(OPEN_H)

    return [
        Result("AL1", "현행 도면 — 전고 개구의 에어록 손실", A["kw"], "kW", allow,
               f"η {0.65:.2f} 를 지키는 에어록 몫 {allow:.1f} kW "
               f"(패널 {panel_kw:.1f} · 나머지 손실 {other_loss_kw:.1f})",
               f"개구 {FULL_H:.2f} m × {OPEN_W:.2f} m 가 {A['t']:.0f} s 열린다. "
               f"교환유동 {A['Q']:.2f} m³/s — **설치정격 {RATED_KW:.0f} kW 의 "
               f"{A['kw']/RATED_KW:.1f} 배다.** 격리실이 없으니 부피 상한도 "
               f"없다. R-106 차이표가 적은 '포크 진입 중 챔버 열림' 은 배기 "
               f"설계 문제가 아니라 **열수지가 닫히지 않는 문제**였다"),
        Result("AL2", "단 피치 개구 · 격리실 없음", B["kw"], "kW", allow,
               "같은 예산", 
               f"개구를 {DECK_H:.2f} m 로 줄이면 {A['kw']/B['kw']:.0f} 배가 준다 — "
               f"Q ∝ h^1.5 라 높이가 1.5 제곱으로 들어오기 때문이다. **그래도 "
               f"모자란다.** 카탈로그의 셔터 실린더 행정 900 이 가리키던 안이 "
               f"이것인데, 판은 4,090 으로 그려져 있어 둘이 서로를 부정하고 있었다"),
        Result("AL3", "패널 포락선 개구 (확정안 C)", C["kw"], "kW", allow,
               "같은 예산",
               f"포크 {FORK_T*1e3:.0f} + 패널 {PANEL_T*1e3:.0f} + 내려놓기 "
               f"{SET_DROP*1e3:.0f} + 여유 2×{OPEN_CLR*1e3:.0f} = "
               f"**{PASS_H*1e3:.0f} mm** 가 지나갈 것의 전부다. 개구 "
               f"{OPEN_H*1e3:.0f} mm 로 잡으면 {C['kw']:.2f} kW — 전고 대비 "
               f"**{A['kw']/C['kw']:.0f} 배**. 단마다 1 장씩 양단에 두어 "
               f"{DECKS*2} 장이고, **선택된 단만 열린다**"),
        Result("AL4", "격리실을 더했을 때의 이득 (안 D)", C["kw"] - D["kw"], "kW", 2.0,
               "라인을 2,400 mm 늘릴 값 — 2 kW 를 넘어야 검토할 가치가 있다",
               f"격리실 {VEST_D:.2f} × {OPEN_W:.2f} × {OPEN_H:.2f} = "
               f"{vestibule(OPEN_H):.2f} m³ 를 두어도 손실은 {D['kw']:.2f} kW 로 "
               f"**한 푼도 안 준다.** 한 번 여닫는 동안 지나가는 것이 "
               f"{C['V']:.2f} m³ 뿐이라 **격리실을 채우지도 못하기** 때문이다 — "
               f"개구를 줄이는 순간 상한이 부피에서 유동으로 넘어갔다. 그런데 "
               f"출력측은 탠덤과 붙어 있어 {VEST_ADD*1e3:,.0f} mm 가 새로 든다 "
               f"— **사지 않는다** (RAL3)"),
        Result("AL5", "확정안이 허용하는 최대 개구 높이", OPEN_H, "m", h_max,
               f"예산 {allow:.1f} kW 를 다 쓰는 높이 {h_max*1e3:.0f} mm",
               f"손실은 h^1.5 · t 에 비례한다. 열림 {t_open:.1f} s 에서 예산을 "
               f"다 쓰는 높이가 {h_max*1e3:.0f} mm 이고 확정 {OPEN_H*1e3:.0f} mm 는 "
               f"그 {OPEN_H/h_max:.0%} 다. **개구와 열림 시간은 한 쌍이다** — "
               f"포크가 느려지면 개구를 더 줄여야 한다"),
        Result("AL6", "문 통과가 택트에 들어가는가", N_DOOR * t_open, "s", TAKT,
               f"라인 택트 {TAKT:.1f} s",
               f"방출·투입 각 {t_open:.1f} s. 포크 왕복 "
               f"{2*REACH/V_FORK:.1f} s 가 그 대부분이고 셔터 여닫기는 "
               f"{2*stroke()/V_DOOR:.1f} s 뿐이다 — **손실을 줄이려면 문이 아니라 "
               f"포크를 빠르게 한다.** 손실은 이 시간에 선형이다"),
        Result("AL7", "셔터 실린더 행정 — 해석 vs 카탈로그",
               stroke(), "m", PT.SHUT_STROKE / 1000.0,
               f"부품 카탈로그 P-002-22 의 행정 {PT.SHUT_STROKE:.0f} mm",
               f"개구 {OPEN_H*1e3:.0f} + 겹침 {DOOR_LAP*1e3:.0f} = "
               f"{stroke()*1e3:.0f} mm. 종전 카탈로그는 판 {FULL_H*1e3:,.0f} mm 에 "
               f"행정 900 이라 **든 판이 개구의 {0.9/FULL_H:.0%} 밖에 안 "
               f"비웠다** — 실린더가 이미 단별 개구를 가리키고 있었는데 판만 "
               f"전고로 남아 있었다"),
        Result("AL8", "단별 셔터 강재량 — 전고 셔터 대비", sh["mass"], "kg",
               sh["mass_old"],
               f"전고 셔터 2 장 {sh['mass_old']:,.0f} kg",
               f"{sh['n']} 장 × {OPEN_W*1e3:,.0f} × {sh['plate_h']*1e3:.0f} × 4.5t = "
               f"{sh['mass']:,.0f} kg. **장수는 {sh['n']//2} 배인데 무게는 "
               f"{sh['mass']/sh['mass_old']:.0%} 다** — 판이 짧아진 몫이 장수보다 "
               f"크다. 대신 씰 둘레가 {sh['perim_old']:.1f} → {sh['perim']:.1f} m 로 "
               f"늘어 침기 항이 따라 오른다 (열수지 HB6 가 받는다)"),
    ], dict(opts={d["key"]: d for d in solve()}, sh=sh, allow=allow,
            h_max=h_max, t_open=t_open, panel=panel_kw, other=other_loss_kw)


def requirements() -> list[Req]:
    rs, ex = run()
    C = ex["opts"]["C"]
    A = ex["opts"]["A"]
    sh = ex["sh"]
    return [
        Req("RAL1", "개구를 단별로 나눈다",
            f"단별 셔터 {sh['n']} 장 · 개구 {OPEN_W*1e3:,.0f} × {OPEN_H*1e3:.0f} · "
            f"선택된 단만 개방",
            "상세설계 · M-002 · PLC 인터록",
            f"전고 개구는 {A['kw']:,.0f} kW 를 내보내 열수지가 닫히지 않는다. "
            f"단별로 나누면 {C['kw']:.2f} kW 다. **DECK_SHUTTER_MUTEX — 두 장이 "
            f"동시에 열리면 안 된다**: 그 순간 개구가 두 배가 되고 손실도 두 "
            f"배가 된다. 도어 위치센서를 단별로 두 채널 둔다"),
        Req("RAL2", "포크 왕복 시간이 손실을 정한다",
            f"문 열림 {ex['t_open']:.1f} s (포크 {2*REACH/V_FORK:.1f} · 셔터 "
            f"{2*stroke()/V_DOOR:.1f} · 정합 {T_SET:.1f})",
            "상세설계 · TS-101 · 운전 시퀀스",
            f"손실은 문 열림 시간에 **선형**이다. 포크 속도 {V_FORK:.2f} m/s 가 "
            f"절반이 되면 에어록 손실이 두 배가 된다. **셔터를 빨리 여는 투자는 "
            f"거의 안 듣는다** — 셔터는 이미 {2*stroke()/V_DOOR/ex['t_open']:.0%} "
            f"뿐이다. 포크 속도를 사양으로 적고 FAT 에서 실측한다"),
        Req("RAL3", "격리실은 두지 않는다", "이중문 격리실 미채용 — 근거를 남긴다",
            "상세설계 · 도면 주기",
            f"개구를 포락선까지 줄이고 나면 격리실이 아끼는 것은 "
            f"{C['kw']-ex['opts']['D']['kw']:.2f} kW 뿐이고, 출력측은 탠덤과 붙어 "
            f"있어 {VEST_ADD*1e3:,.0f} mm 가 새로 든다. **안 사는 것이 결론이지만 "
            f"'검토하지 않았다' 와 '검토하고 안 샀다' 는 다르다** — 도면 주기에 "
            f"이 숫자를 남긴다. 전고 개구로 되돌아가는 순간 격리실은 다시 "
            f"필수가 된다"),
        Req("RAL4", "도면이 격리실 유무를 한 목소리로 말하게 한다",
            "압축 배치 3D 라벨 · R-106 차이표 · 부품 카탈로그",
            "상세설계 · 콘솔 · tools/parts.py",
            "콘솔의 압축 배치는 양단을 '이중셔터 에어록' 이라 적고 R-106 "
            "차이표는 '격리실 없음' 이라 적는다. **열수지가 그 틈에서 있지도 "
            "않은 방의 부피를 셌다.** 도면이 두 목소리를 내면 해석은 반드시 "
            "둘 중 하나를 잘못 고른다"),
        Req("RAL5", "실측으로 닫는다",
            "문 열림 중 개구 유속 (열선 3점) · 개폐 이력 · 챔버 차압",
            "파일럿 PT-05",
            f"교환유동은 정상 부력유동을 가정한다 — 문이 열리는 첫 1 초의 "
            f"과도구간과 챔버 부압 −20 Pa 의 유입 편향을 안 본다. 둘 다 "
            f"안전측이지만 크기를 모른다. **에어록 항만 따로 계측한다**: 문을 "
            f"안 여는 정상 운전과 여는 운전의 IR 전력 차이가 이 항이다"),
    ]


def report() -> str:
    L = []
    add = L.append
    rs, ex = run()
    add("=" * 78)
    add("DG-HK60C 에어록 — 문의 높이가 정한다 (RHB2)")
    add("=" * 78)
    add("")
    add("── 검증 (닫힌해) ───────────────────────────────────────")
    for n, got, want, err in validate():
        add(f"   {n:44s} {got:11.4f} {want:11.4f} {err:7.2%}")
    add("")
    add("── 안 ──────────────────────────────────────────────────")
    add(f"   {'':2s} {'안':34s} {'개구':>7s} {'Q':>8s} {'교환':>8s} {'손실':>8s} {'상한':>10s}")
    for d in solve():
        add(f"   {d['key']:2s} {d['name'][:34]:34s} {d['h']:7.2f} {d['Q']:8.3f} "
            f"{d['V']:8.2f} {d['kw']:8.2f} {d['cap']:>10s}")
    add("")
    add("── 검토 ────────────────────────────────────────────────")
    add(f"   {'ID':4s} {'항목':32s} {'값':>9s} {'한계':>9s} {'이용률':>7s}  판정")
    bad = 0
    for r in rs:
        add(f"   {r.id:4s} {r.what[:32]:32s} {r.value:9.2f} {r.limit:9.2f} "
            f"{r.util:6.0%}  {'OK' if r.ok else '★ 초과'}")
        bad += 0 if r.ok else 1
    add("")
    add("── 근거 ────────────────────────────────────────────────")
    for r in rs:
        add(f"   {r.id}  {r.basis}")
        add(f"       {r.note}")
    add("")
    add("── 이 검토가 만든 요구 ─────────────────────────────────")
    for q in requirements():
        add(f"   {q.id}  {q.what} — {q.value}")
        add(f"       받는 곳: {q.owner}")
    add("")
    add("=" * 78)
    add("전 항목 만족" if not bad else f"★ {bad} 항목 초과 — 그것이 이 검토의 결론이다")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
