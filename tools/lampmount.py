"""램프 지지·관통 상세 — IR 뱅크 검토가 넘긴 RIR4 를 푼다.

발열장을 1,300 → 2,200 으로 늘리고 단자를 측벽 밖으로 뺐다. 그 결정이
남긴 상세가 이것이다. 넘길 때 "처짐 · 실링 · 그림자" 셋을 적었는데,
풀어 보니 **적지 않은 둘이 더 크다**:

    ④ 차등 열팽창   강재 챔버가 석영보다 훨씬 많이 늘어난다. 양단을
                    고정하면 램프가 뜯긴다 — 셋 중 가장 먼저 부러지는 자리
    ⑤ 핀치 온도     단파장(할로겐) 램프는 몰리브덴 박 봉착부가 350 ℃ 를
                    넘으면 산화하고, 250 ℃ 밑이면 할로겐이 봉착부에
                    응축해 사이클이 죽는다. **"밖에 둔다" 가 "실온에
                    노출한다" 로 읽히면 램프가 일찍 검어진다**

── 처짐은 문제가 아니었다 ──────────────────────────────────────────
Ø25 석영관 2.2 m 의 자중 처짐은 탄성으로 1.8 mm 다. 램프–패널 거리가
310 mm 이므로 유속 변화는 0.6 % — IR 검토가 잡은 면내 편차 11 K 옆에서
보이지 않는 값이다. **중간 지지가 필요 없다.** 필요 없으면 그림자도 없다.

셋 중 둘이 서로를 지운 셈이다: 지지를 안 하니 그림자 문제가 사라진다.
남는 것은 관의 처짐이 아니라 **관 안의 필라멘트 처짐**이고, 그것은
램프 안쪽 지지대로 제조사가 푸는 문제다 — 우리가 지정할 것이지 설계할
것이 아니다.

── 관통이 사 오는 대가 ─────────────────────────────────────────────
80 개소를 뚫는다. 열교는 작지만 **침기**가 크다. 챔버를 부압으로 두면
(연기를 잡으려면 그래야 한다) 그 구멍으로 찬 공기가 들어오고, 그것을
140 ℃ 까지 데우는 것이 그대로 손실이다. 실링을 안 하면 벽 손실과 같은
자릿수가 된다 — 효율 65 % 의 나머지를 찾는 일(R5)에 이 항이 들어간다.
"""

from __future__ import annotations

import math
import pathlib
import sys
from typing import NamedTuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import analysis_irbank as AIR  # noqa: E402
import analysis_thermal as TH  # noqa: E402
import irbank as IR  # noqa: E402
from analysis_thermal import Req, Result  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 램프 ─────────────────────────────────────────────────────────────
OD, WALL = 25.0, 1.2                 # mm 석영관 외경 · 관두께
HEAT_L = AIR.NEW_LEN * 1000          # 2,200 mm 발열장
E_Q, RHO_Q = 72_000.0, 2200.0        # MPa · kg/m³ 용융석영
ALPHA_Q, K_Q = 0.55e-6, 1.4          # 1/K · W/(m·K)
M_LAMP = 0.60                        # kg 관+필라멘트 (단자 제외)

# ── 봉착부 (단파장 = 할로겐) ─────────────────────────────────────────
T_PINCH_MIN, T_PINCH_MAX = 250.0, 350.0    # ℃ 할로겐 사이클 · Mo 박 산화
T_TUBE = 700.0                              # ℃ 발광부 관벽
T_BUSH = 100.0                              # ℃ 부시 안쪽 국부 주위
TOL_PINCH = 8.0                             # mm 봉착부 배치에 필요한 공차 창
                                            #    (램프 ±2 · 부시 ±1 · 경계 ±1)
H_PINCH = 10.0                              # W/(m²·K) 부시 안 자연대류

# ── 관통부 ───────────────────────────────────────────────────────────
N_PEN = int(c("LAMPS")) * 2          # 80 개소
WALL_T = 0.130                       # m 4겹 벽 두께
BUSH_OD, BUSH_BORE = 45.0, 28.0      # mm 세라믹 부시 외경 · 보어
K_BUSH_LOW, K_BUSH_STEEL = 0.9, 16.0  # W/(m·K) 섬유충전 세라믹 · 강재 슬리브
LEAK_RAW = math.pi / 4 * (BUSH_BORE ** 2 - OD ** 2)   # mm²/개소 무실링
SEAL_FACTOR = 0.08                   # 세라믹 파이버 로프 패킹의 잔여 누설
DP = 20.0                            # Pa 챔버 부압 (연기 봉쇄)
CD, RHO_AIR, CP_AIR = 0.62, 1.20, 1005.0

# ── 챔버 ─────────────────────────────────────────────────────────────
CAV_W = IR.CAVITY_W * 1000           # 2,300 mm 관통부 사이 거리
ALPHA_STS = 17.3e-6                  # 1/K STS304 내피 — 강재 중 가장 큰 쪽
T_SKIN, T_COLD = c("T_TARGET"), 20.0
LOSS_BUDGET = 35.0                   # kW 정격 100 − 유효 65


def _section():
    ID = OD - 2 * WALL
    A = math.pi / 4 * (OD ** 2 - ID ** 2)
    I = math.pi / 64 * (OD ** 4 - ID ** 4)
    return A, I


# ── ① 자중 처짐과 그 광학 대가 ──────────────────────────────────────
def sag():
    A, I = _section()
    w = M_LAMP * 9.80665 / HEAT_L            # N/mm 등분포
    d = 5 * w * HEAT_L ** 4 / (384 * E_Q * I)
    # 선원이 패널에 가까워진 만큼 유속이 오른다 (선원은 1/h 로 떨어진다)
    h = IR.BANK_GAP * 1000
    dflux = d / h
    return d, dflux, A, I


# ── ② 차등 열팽창 → 유동 행정 ───────────────────────────────────────
def expansion():
    """강재 챔버와 석영관이 같이 안 늘어난다 — 이것이 첫 파단 자리다."""
    steel = ALPHA_STS * CAV_W * (T_SKIN - T_COLD)
    quartz = ALPHA_Q * HEAT_L * (0.5 * (T_TUBE + T_SKIN) - T_COLD)
    return steel, quartz, steel - quartz


# ── ③ 관통부 열교 ───────────────────────────────────────────────────
def bridge(k_bush: float = K_BUSH_LOW):
    a = (math.pi / 4 * (BUSH_OD ** 2 - BUSH_BORE ** 2)) * 1e-6   # m² 고체 단면
    g = k_bush * a / WALL_T * N_PEN                              # W/K
    _, ex = TH.run()
    w = ex["chamber_wall"]
    base_kw = w["q_gfrp"] * w["area"] / 1000
    add_kw = g * (T_SKIN - w["t_gfrp"]) / 1000
    return g, base_kw, add_kw


# ── ④ 침기 — 부압 운전의 대가 ───────────────────────────────────────
def leakage(seal: float = SEAL_FACTOR):
    area = LEAK_RAW * N_PEN * seal * 1e-6        # m²
    v = math.sqrt(2 * DP / RHO_AIR)
    q = CD * area * v                            # m³/s
    kw = q * RHO_AIR * CP_AIR * (T_SKIN - c("T_AMB")) / 1000
    return area, q * 3600, kw


# ── ⑤ 봉착부 온도 — 어디에 두어야 하는가 ────────────────────────────
def pinch():
    """관을 핀으로 본다. 석영은 열을 거의 안 나르므로 열길이가 짧다.

        m = √(hP/kA),  T(x) = T주위 + (T관 − T주위)·e^(−mx)

    창(250~350 ℃)이 몇 mm 폭인지가 답이다. 좁으면 그것 자체가 결론이다 —
    "밖에 둔다" 로는 못 짓고 제조사와 봉착 위치를 확정해야 한다.
    """
    A, _ = _section()
    P = math.pi * OD
    m = math.sqrt(H_PINCH * 1e-6 * P / (K_Q * 1e-3 * A))     # 1/mm
    def x_at(T):
        return math.log((T_TUBE - T_BUSH) / (T - T_BUSH)) / m
    return m, x_at(T_PINCH_MAX), x_at(T_PINCH_MIN)


# ── ⑥ 중간 지지를 썼다면 ────────────────────────────────────────────
def shadow():
    """지지대를 **아래에서** 잡았을 때의 그림자 — 안 쓰는 이유를 센다.

    처음에 '가려지는 면적비 × 115 K' 로 셌다가 1.9 K 가 나왔다. 그것은
    그림자가 아니라 평균 감소다. 지지대는 **가장 가까운 램프의 직달**을
    그 줄에서 통째로 지운다 — 나머지 램프와 반사분만 남는다. 그 몫이
    얼마인지를 모델에서 직접 센다.
    """
    lam = IR.from_positions(list(AIR.NEW_X), length=AIR.NEW_LEN) * 2
    full = IR.field(IR.images(lam, IR.RHO_WALL), 41, 21)
    nx, ny = len(full.xs), len(full.ys)
    i, j = nx // 2, ny // 2                       # 중앙 램프 바로 아래
    total = full.E[i][j]
    # 그 자리를 비추는 중앙 램프 두 개(아래·위 뱅크)의 직달분
    direct = sum(lp.irradiance(full.xs[i], full.ys[j])
                 for lp in lam if abs(lp.x) < 1e-9)
    frac = direct / total
    return frac, frac * (TH.T_TARGET - c("T_AMB"))


def run():
    d, dflux, A, I = sag()
    steel, quartz, diff = expansion()
    g_low, base_kw, add_low = bridge(K_BUSH_LOW)
    g_st, _, add_st = bridge(K_BUSH_STEEL)
    a_seal, m3h, kw_seal = leakage(SEAL_FACTOR)
    a_raw, m3h_raw, kw_raw = leakage(1.0)
    m, x_hot, x_cold = pinch()
    blocked, dT_shadow = shadow()
    float_req = diff + 4.0                        # 램프 길이 공차 ±2

    return [
        Result("LM1", "석영관 자중 처짐 (2,200 스팬)", d, "mm", 5.0,
               "유속 1.6 % 를 내는 처짐 — 면내 편차 예산 11 K 의 1/6",
               f"Ø{OD:.0f}×{WALL:.1f}t · I {I:,.0f} mm⁴ · 관+필라멘트 "
               f"{M_LAMP:.2f} kg. **중간 지지가 필요 없다** — 필요 없으면 "
               f"그림자도 없다. 넘길 때 걱정한 셋 중 둘이 서로를 지웠다"),
        Result("LM2", "처짐이 유속에 주는 변화", dflux * 100, "%", 2.0,
               "면내 편차 11 K 대비 무시할 수준의 상한",
               f"선원은 1/h 로 떨어지므로 {d:.1f} mm 가 "
               f"{IR.BANK_GAP*1000:.0f} mm 거리에서 {dflux:.2%} 다. "
               f"남는 것은 관이 아니라 **관 안 필라멘트의 처짐**이고, 그것은 "
               f"램프 안쪽 지지대로 제조사가 푼다 (RLM4)"),
        Result("LM3", "차등 열팽창이 요구하는 유동 행정", float_req, "mm", 10.0,
               "설계 행정 10 mm — 한쪽 고정 · 한쪽 유동",
               f"강재 {CAV_W:,.0f} mm 가 {steel:.2f} mm 늘 때 석영은 "
               f"{quartz:.2f} mm 만 는다 (α {ALPHA_STS*1e6:.1f} vs "
               f"{ALPHA_Q*1e6:.2f}). 차이 {diff:.2f} + 길이공차 4. "
               f"**양단을 고정하면 램프가 뜯긴다** — 처짐보다 이쪽이 먼저 "
               f"부러지는 자리인데 넘길 때 적지 않았다"),
        Result("LM4", "관통부 열교 (세라믹 부시)", add_low, "kW", base_kw,
               f"열교 포함 벽 손실 {base_kw:.2f} kW — 그보다 작아야 한다",
               f"{N_PEN} 개소 · k {K_BUSH_LOW:.1f} W/(m·K) · 고체 단면 "
               f"Ø{BUSH_OD:.0f}/Ø{BUSH_BORE:.0f}. 강재 슬리브로 바꾸면 "
               f"{add_st:.2f} kW 로 {add_st/add_low:.0f} 배다 — **부시 재질이 "
               f"사양이지 선택이 아니다**"),
        Result("LM5", "관통부 침기 손실 (실링 후)", kw_seal, "kW",
               LOSS_BUDGET - base_kw,
               f"손실 예산 {LOSS_BUDGET:.0f} kW − 벽 {base_kw:.2f} kW",
               f"챔버를 −{DP:.0f} Pa 부압으로 둬야 연기를 잡는다. 그러면 "
               f"구멍으로 찬 공기가 들어오고 그것을 데우는 것이 손실이다. "
               f"**실링을 안 하면 {kw_raw:.1f} kW** ({m3h_raw:,.0f} m³/h) 로 "
               f"벽 손실의 {kw_raw/base_kw:.1f} 배다 — 파이버 로프 패킹으로 "
               f"{kw_seal:.2f} kW ({m3h:,.0f} m³/h) 까지 내린다"),
        Result("LM6", "봉착부 배치에 필요한 공차 창", TOL_PINCH, "mm",
               x_cold - x_hot,
               f"물리가 주는 창 {x_cold-x_hot:.1f} mm (250~350 ℃ 사이 구간)",
               f"석영은 열을 거의 안 나른다 — 열길이 1/m = {1/m:.1f} mm 라 "
               f"발광부 경계에서 {x_hot:.1f} mm 면 350 ℃, {x_cold:.1f} mm 면 "
               f"250 ℃ 다. 램프 길이공차 ±2 · 부시 위치 ±1 · 발광부 경계 정의 "
               f"±1 을 더하면 **필요 공차가 물리가 주는 창보다 넓다.** "
               f"'밖에 둔다' 를 '실온에 노출한다' 로 지으면 250 ℃ 밑으로 떨어져 "
               f"할로겐이 봉착부에 응축하고 램프가 검어진다. **우리가 위치를 "
               f"잡을 문제가 아니다** — 제조사가 봉착부 온도를 보증하는 형식으로 "
               f"발주한다 (RLM4)"),
        Result("LM7", "아래 지지대를 썼다면 (쓰지 않는다)", dT_shadow, "K",
               AIR.DT_GLASS,
               "유리 허용 면내 편차 21 K",
               f"지지대는 가장 가까운 램프의 **직달을 통째로 지운다.** 그 자리 "
               f"유속의 {blocked:.0%} 가 직달이므로 그 줄만 {dT_shadow:.0f} K "
               f"낮아진다 — IR 검토가 만든 11 K 를 지지대 하나가 넘긴다. "
               f"LM1 이 지지를 없앴으므로 이 항은 **쓰지 않는 이유의 값**이다"),
    ], dict(sag=d, dflux=dflux, steel=steel, quartz=quartz, diff=diff,
            float_req=float_req, g_low=g_low, g_st=g_st, base_kw=base_kw,
            add_low=add_low, add_st=add_st, kw_seal=kw_seal, kw_raw=kw_raw,
            m3h=m3h, m3h_raw=m3h_raw, x_hot=x_hot, x_cold=x_cold,
            mlen=1 / m, blocked=blocked, dT_shadow=dT_shadow)


def requirements() -> list[Req]:
    _, ex = run()
    return [
        Req("RLM1", "한쪽 고정 · 한쪽 유동",
            f"유동단 행정 ≥ {ex['float_req']:.0f} mm (설계 10)",
            "F-002 제작도 · 상세설계",
            f"강재 챔버가 {ex['steel']:.2f} mm 늘 때 석영은 "
            f"{ex['quartz']:.2f} mm 만 는다. 양단 고정은 **첫 승온에서 램프를 "
            f"뜯는다.** 유동단은 스프링 하중으로 눌러 전기 접촉은 유지하되 "
            f"축방향으로는 미끄러지게 한다"),
        Req("RLM2", "관통 부시 재질", f"k ≤ {K_BUSH_LOW:.1f} W/(m·K) · 섬유충전 세라믹",
            "부품 카탈로그 P-002-25 · 구매 사양",
            f"강재 슬리브로 바꾸면 열교가 {ex['add_st']/ex['add_low']:.0f} 배가 "
            f"되어 벽 손실을 혼자 {ex['add_st']:.1f} kW 올린다. 치수가 같으니 "
            f"도면으로는 구분이 안 된다 — **재질을 사양으로 적지 않으면 "
            f"싸고 튼튼한 것이 온다**"),
        Req("RLM3", "관통부 실링과 챔버 부압",
            f"개소당 잔여 누설 ≤ {AIR.IR.LAMPS and (LEAK_RAW*SEAL_FACTOR):.0f} mm² · "
            f"챔버 −{DP:.0f} Pa",
            "상세설계 · 배기 계통 · 시운전 검사",
            f"실링 없이는 침기가 {ex['kw_raw']:.1f} kW 로 벽 손실의 "
            f"{ex['kw_raw']/ex['base_kw']:.1f} 배다. 부압은 **연기를 잡기 위해 "
            f"필요하고**(EVA 초산·불화물), 그 대가가 침기다. 두 요구가 서로를 "
            f"부르므로 실링이 유일한 출구다. 시운전에서 부압과 누설을 실측한다"),
        Req("RLM4", "램프 제조사 확인 항목",
            "수평 정격 · 내부 필라멘트 지지 · 봉착부 위치와 허용온도",
            "구매 사양 · 승인도",
            f"관의 처짐은 {ex['sag']:.1f} mm 로 문제가 아니지만 **관 안 "
            f"필라멘트**는 다르다 — 2.2 m 수평은 내부 지지 없이는 못 간다. "
            f"봉착부는 발광부에서 {ex['x_hot']:.0f}~{ex['x_cold']:.0f} mm 창에 "
            f"들어와야 하는데 폭이 {ex['x_cold']-ex['x_hot']:.0f} mm 뿐이라 "
            f"우리가 위치를 잡을 문제가 아니다. **제조사가 봉착부 온도를 "
            f"보증하는 형식으로 발주한다**"),
        Req("RLM5", "중간 지지 금지", "발광부 구간에 지지대를 두지 않는다",
            "F-002 제작도 주기 · 조립 지침서",
            f"폭 20 mm 지지대 하나가 그 줄에 {ex['dT_shadow']:.0f} K 차를 만든다 — "
            f"IR 검토가 만든 11 K 를 혼자 깬다. 처짐이 {ex['sag']:.1f} mm 뿐이라 "
            f"필요도 없다. **도면에 '지지 금지' 를 적지 않으면 현장이 좋은 뜻으로 "
            f"받쳐 놓는다** — 처지는 것이 보이면 사람은 받치고 싶어진다"),
    ]


def report() -> str:
    L = []
    add = L.append
    add("=" * 78)
    add("DG-HK60C 램프 지지·관통 상세 — IR 뱅크 검토가 넘긴 RIR4")
    add("=" * 78)
    add("")
    add("── 검토 ────────────────────────────────────────────────")
    add(f"   {'ID':4s} {'항목':34s} {'값':>9s} {'한계':>9s} {'이용률':>7s}  판정")
    rs, ex = run()
    bad = 0
    for r in rs:
        add(f"   {r.id:4s} {r.what[:34]:34s} {r.value:9.2f} {r.limit:9.2f} "
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
    add("전 항목 만족" if not bad else f"★ {bad} 항목 초과")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
