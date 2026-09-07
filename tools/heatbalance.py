"""열수지를 닫는다 — 손실 35 kW 의 행방 (열해석 R5).

열해석이 요구 R5 를 남겼다: **벽 손실은 5.5 kW 로 손실 예산 35 kW 의
16 % 뿐이고, 나머지 30 kW 의 행방을 아무도 세지 않았다.**

세어 보니 **질문 자체가 틀려 있었다.** 두 군데가 어긋난다.

── ① 65 kW 는 계약 처리량의 값이 아니다 ────────────────────────────
콘솔은 `유효 = 정격 100 kW × η 0.65 = 65 kW` 를 쓰고, 그 65 kW 를
"패널이 받는 열" 로 놓는다. 그런데 65 kW 는 **열공정 한계 80.9 장/h**
에서 패널이 받는 값이다. 라인은 탠덤이 정하는 **60 장/h** 로 돈다 —
그때 패널이 가져가는 것은 장당 2.869 MJ × 60 = **47.8 kW** 다.

    100 kW − 65 kW = 35 kW      ← 정격과 열공정 한계를 뺀 값
    73.5 kW − 47.8 kW = 25.7 kW ← 계약 처리량에서 η 0.65 가 뜻하는 손실

"35 kW" 는 서로 다른 두 운전점에서 하나씩 가져온 숫자였다.

── ② 빗나간 복사는 손실이 아니다 ───────────────────────────────────
더 큰 어긋남은 이것이다. η 0.65 는 **결합효율** — 지금 이 순간 복사 중
얼마가 패널에 흡수되는가 — 이고, 그것이 승온 속도를 정한다. 그런데
챔버는 **닫힌 공동**이고 내피는 연마 STS(ρ 0.8) 다. 패널을 빗나간 복사는
사라지지 않는다. 벽에 부딪혀 되튀고, 결국 패널에 흡수되거나 · 벽으로
전도돼 나가거나 · 기체와 함께 배기로 나간다.

**정상상태에서 실제로 계를 떠나는 것만이 손실이다.** 그것을 제어체적으로
세면 아래 표가 되고, 남는 항은 없다. 30 kW 는 새는 것이 아니라 **돌고
있었다.**

    IN   IR 전기 (평균)
    OUT  패널 엔탈피 · 벽 전도 · 에어록 교환 · 침기 · 단자 전도

이 구분을 흐리면 두 가지를 잘못한다. 결합효율로 체류시간을 잡는 것은
**보수측이라 옳고**(그대로 둔다), 그 차액을 "어디로 새는가" 로 찾는 것은
**있지도 않은 구멍을 찾는 일**이다.

**이 수지가 못 보는 것**: 램프 배광과 파장별 흡수율(백시트는 근적외를
많이 반사한다), 기동 후 준정상 구간, 셔터 씰의 실제 누설등급. 파일럿
PT-05 가 전력량계·배기 엔탈피·벽 열류계로 실측해 확정한다.
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import analysis_thermal as TH  # noqa: E402
import lampmount as LM  # noqa: E402
import parts as PT  # noqa: E402
from analysis_thermal import Req, Result  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 운전점 ───────────────────────────────────────────────────────────
RATE_CONTRACT = 60.0                 # 장/h 계약 순생산
RATE_THERMAL = 80.9                  # 장/h 열공정 한계 (콘솔)
TAKT = 53.6                          # s 라인 사이클 — 에어록이 이 주기로 열린다
RATED_KW = c("LAMPS") * 2.5          # 100 kW 설치정격
ETA_ASSUMED = 0.65                   # 콘솔 MODEL 기본값
T_HOT, T_AMB = c("T_TARGET"), c("T_AMB")

# 장당 열량 — 콘솔과 같은 식
Q_PANEL_KJ = (c("AREAL_CP") * c("PANEL_L") * c("PANEL_W") * (T_HOT - T_AMB))

# ── 공기 ─────────────────────────────────────────────────────────────
CP_AIR = 1005.0                      # J/(kg·K)
RHO_AIR = lambda t: 353.0 / (273.15 + t)     # kg/m³ 대기압 건공기

# ── 챔버·에어록 ──────────────────────────────────────────────────────
CAV_L, CAV_W, CAV_H = 3.52, 2.30, 3.60       # m 내부 공동
SHUT_W, SHUT_H = 1.680, 4.090                # m 에어록 셔터판 (P-002-20)
AIRLOCK_D = c("CL_DOOR")                     # 0.30 m 이중 셔터 사이 격리 깊이
T_AIRLOCK = 40.0                             # ℃ 격리실 정상 온도 (보수측)
SEAL_SPEC = 3.0                              # mm²/m 압착 씰의 등가 누설면적


def chamber_volume() -> float:
    return CAV_L * CAV_W * CAV_H


def airlock_volume() -> float:
    return SHUT_W * SHUT_H * AIRLOCK_D


# ── OUT ① 패널 엔탈피 ───────────────────────────────────────────────
def panel(rate: float = RATE_CONTRACT) -> float:
    """장당 열량 × 처리량. 이것이 이 설비가 하는 일 전부다."""
    return Q_PANEL_KJ * rate / 3600.0            # kW


# ── OUT ② 벽 전도 ───────────────────────────────────────────────────
def wall() -> float:
    _, ex = TH.run()
    w = ex["chamber_wall"]
    return w["q_gfrp"] * w["area"] / 1000.0


# ── OUT ③ 에어록 교환 ───────────────────────────────────────────────
def airlock(v: float = None, takt: float = TAKT) -> tuple[float, float]:
    """이중 셔터가 한 번 여닫을 때 나가는 열.

    내문이 열리면 챔버(140)와 격리실이 섞이고, 외문이 열리면 그 격리실이
    실온과 섞인다. **격리실이 막다른 방이므로 교환량은 그 부피로 막힌다** —
    부력이 아무리 세도 그보다 많이 못 바꾼다. 그래서 이 항의 크기를 정하는
    것은 문의 크기도 여는 시간도 아니고 **격리실 부피**다.

    격리실 부피는 셔터가 랙 전고(4.09 m)인 데서 온다. 한 번에 한 단만
    쓰는데 전고를 여는 구조라 그렇다 — 그것이 이 항의 값이다.
    """
    v = airlock_volume() if v is None else v
    rho = RHO_AIR(T_HOT)
    inner = v * rho * CP_AIR * (T_HOT - T_AIRLOCK)      # J 내문: 챔버 → 격리
    outer = v * rho * CP_AIR * (T_HOT - T_AMB)          # J 외문: 격리 → 실온
    per_cycle = inner + outer
    return per_cycle / 1000.0, per_cycle / takt / 1000.0     # kJ/회 · kW


# ── OUT ④ 침기 ──────────────────────────────────────────────────────
def infiltration() -> tuple[float, float, float]:
    """부압 운전이 부르는 찬 공기. 관통부 + 셔터 씰.

    챔버는 연기를 잡으려고 −20 Pa 로 돈다 (램프 지지 검토 RLM3). 배기가
    빼내는 만큼이 그대로 새 구멍으로 들어오므로, **배기 엔탈피 손실 =
    누설 유량 엔탈피**다. 둘을 따로 세면 두 번 센다.
    """
    a_pen = LM.LEAK_RAW * LM.N_PEN * LM.SEAL_FACTOR          # mm² 관통부
    perim = 2 * (SHUT_W + SHUT_H) * 2                        # m 셔터 2장
    a_seal = perim * SEAL_SPEC                               # mm² 씰
    area = (a_pen + a_seal) * 1e-6                           # m²
    q = LM.CD * area * math.sqrt(2 * LM.DP / LM.RHO_AIR)     # m³/s
    kw = q * RHO_AIR(T_AMB) * CP_AIR * (T_HOT - T_AMB) / 1000.0
    return a_pen + a_seal, q * 3600, kw


# ── OUT ⑤ 램프 단자 전도 ────────────────────────────────────────────
def terminal() -> float:
    """석영관이 관통부로 빼내는 열 — 핀 해석의 뿌리 열류.

        q = √(hPkA)·θ = kA·m·θ
    """
    m, _, _ = LM.pinch()
    A, _ = LM._section()
    kA = LM.K_Q * 1e-3 * A                       # W·mm/K
    q = kA * m * (LM.T_TUBE - LM.T_BUSH)         # W/단
    return q * LM.N_PEN / 1000.0


# ── OUT ⑥ 포크 반출 ─────────────────────────────────────────────────
FORK_AREA = 1.5          # m² 챔버 안으로 들어가는 포크 표면
FORK_EXPOSE = 5.0        # s 사이클당 챔버 체류
FORK_H = 12.0            # W/(m²·K) 복사(ε 0.5) + 자연대류


def fork(t_rest: float = None, takt: float = TAKT) -> float:
    """TS-101 텔레스코픽 포크가 퍼올려 나가는 열.

    **처음에 200 배 틀렸다.** 포크 42 kg 이 매 사이클 (140−40)/3 만큼
    통째로 오르내린다고 놓아 13 kW 가 나왔고, 그 값이 수지를 η 64.3 % 로
    "너무 잘" 닫았다 — 가정 65 % 와 소수점까지 맞은 것이 오히려 신호였다.
    되짚어 보니 그 온도변화는 699 kJ 을 5 초에 넣는 것이고 **140 kW** 가
    필요하다. IR 설치정격이 100 kW 다. 챔버가 줄 수 없는 열이었다.

    실제로는 **전열률이 정한다.** 노출 시간 동안 복사+대류로 들어가는
    만큼만 포크가 싣고 나간다:

        Q = h·A·(T챔버 − T포크)·t노출

    질량은 이 항에 안 들어온다 — 들어오는 것은 **대기 위치의 온도**다.
    """
    t_rest = T_AIRLOCK if t_rest is None else t_rest
    q = FORK_H * FORK_AREA * (T_HOT - t_rest) * FORK_EXPOSE     # J/회
    return q / takt / 1000.0


# ── 수지 ────────────────────────────────────────────────────────────
def balance(rate: float = RATE_CONTRACT) -> dict:
    p = panel(rate)
    w = wall()
    _, _, inf = infiltration()
    _, al = airlock()
    t = terminal()
    f = fork()
    loss = w + inf + al + t + f
    p_ir = p + loss
    return dict(panel=p, wall=w, infil=inf, airlock=al, terminal=t, fork=f,
                loss=loss, p_ir=p_ir, eta=p / p_ir,
                assumed_ir=p / ETA_ASSUMED,
                assumed_loss=p / ETA_ASSUMED - p)


# ── 기동 축열 ───────────────────────────────────────────────────────
INNER = {"P-002-06", "P-002-07", "P-002-08", "P-002-12", "P-002-13",
         "P-002-15", "P-002-17", "P-002-18", "P-002-19", "P-002-20",
         "P-002-21"}
INSUL = {"P-002-14"}


def startup() -> dict:
    """냉간 기동 — 첫 패널을 넣기 전에 챔버를 데우는 데 드는 것.

    정상상태 수지에는 안 나오지만 **교대 첫 시간의 처리량이 여기 걸린다.**
    """
    e_in = e_ins = e_out = 0.0
    for p in PT.P:
        if p.mod != "M-002":
            continue
        cp = 500.0 if p.mat in ("STS304", "SS400", "SM490A") else 840.0
        if p.pid in INNER:
            e_in += p.total_kg * cp * (T_HOT - T_AMB)
        elif p.pid in INSUL:
            e_ins += p.total_kg * 840.0 * (T_HOT - T_AMB) / 2      # 벽 안 기울기
        else:
            e_out += p.total_kg * cp * 15.0                        # 외피측 상승
    gas = chamber_volume() * RHO_AIR(T_HOT) * CP_AIR * (T_HOT - T_AMB)
    total = e_in + e_ins + e_out + gas
    net = RATED_KW * 1000 - wall() * 1000 / 2          # 승온 중 평균 손실
    return dict(inner=e_in, insul=e_ins, outer=e_out, gas=gas, total=total,
                minutes=total / net / 60, kwh=total / 3.6e6)


def run():
    b = balance()
    bt = balance(RATE_THERMAL)
    per_cycle, al = airlock()
    area, m3h, inf = infiltration()
    su = startup()
    small = airlock(v=SHUT_W * 0.70 * AIRLOCK_D)[1]     # 한 단 높이 격리실

    return [
        Result("HB1", "계약 처리량의 패널 엔탈피", b["panel"], "kW",
               RATED_KW * ETA_ASSUMED,
               f"콘솔이 '유효' 로 쓰는 {RATED_KW*ETA_ASSUMED:.0f} kW",
               f"{RATE_CONTRACT:.0f} 장/h × {Q_PANEL_KJ/1000:.3f} MJ. "
               f"{RATED_KW*ETA_ASSUMED:.0f} kW 는 **열공정 한계 "
               f"{RATE_THERMAL:.1f} 장/h** 의 값이다 ({bt['panel']:.1f} kW). "
               f"라인은 탠덤이 정하는 {RATE_CONTRACT:.0f} 장/h 로 도는데 "
               f"'100 − 65 = 35 kW' 는 **두 운전점에서 하나씩 가져온 뺄셈**이었다"),
        Result("HB2", "세어 낸 손실 합계", b["loss"], "kW", b["assumed_loss"],
               f"η {ETA_ASSUMED:.2f} 가 계약 처리량에서 뜻하는 손실 "
               f"{b['assumed_loss']:.1f} kW",
               f"벽 {b['wall']:.2f} · 에어록 {b['airlock']:.2f} · 침기 "
               f"{b['infil']:.2f} · 단자 {b['terminal']:.2f} · 포크 "
               f"{b['fork']:.2f}. **남는 항이 없다** — 30 kW 는 새는 것이 "
               f"아니라 공동 안에서 돌고 있었다. 빗나간 복사는 연마 내피"
               f"(ρ 0.8)에 되튀어 결국 패널·벽·배기 중 하나로 간다"),
        Result("HB3", "정상상태 효율", ETA_ASSUMED, "—", b["eta"],
               f"수지가 내는 효율 {b['eta']:.0%} — 가정이 이보다 낮아야 보수측이다",
               f"결합효율(지금 이 순간 패널이 먹는 몫)과 정상상태 효율(평균 "
               f"전력 중 패널이 가져가는 몫)은 다른 양이다. 체류시간은 "
               f"**결합효율로 잡는 것이 맞고**, {ETA_ASSUMED:.2f} 는 수지가 "
               f"내는 {b['eta']:.2f} 보다 낮아 여유 {b['assumed_loss']-b['loss']:.1f} kW "
               f"를 들고 있다 — 그대로 둔다"),
        Result("HB4", "에어록 교환 — 최대 손실 항", al, "kW", b["loss"],
               "세어 낸 손실 합계 — 이 항이 그 절반을 넘으면 여기가 설계 레버다",
               f"회당 {per_cycle:.0f} kJ · 택트 {TAKT:.1f} s. 손실의 "
               f"{al/b['loss']:.0%} 다. 내문이 챔버와 격리실을 섞고 외문이 "
               f"격리실과 실온을 섞는다 — **막다른 방이라 교환량이 격리실 "
               f"부피로 막힌다**. 문 크기도 여는 시간도 아니고 부피가 정한다"),
        Result("HB5", "격리실 부피가 사 오는 손실", al - small, "kW", 2.0,
               "한 단 높이(0.70 m) 격리실로 줄였을 때 아끼는 몫 — 2 kW 를 "
               "넘으면 구조를 다시 볼 값이다",
               f"셔터가 랙 전고 {SHUT_H:.2f} m 라 격리실이 "
               f"{airlock_volume():.2f} m³ 다. 한 번에 한 단만 쓰는데 전고를 "
               f"연다. 한 단 높이면 {small:.2f} kW 로 **{al-small:.1f} kW 를 "
               f"아낀다** — 포크가 챔버 안에서 층을 고를 수 있다면 격리실은 "
               f"전고일 이유가 없다 (RHB2)"),
        Result("HB6", "침기 (관통 + 셔터 씰)", inf, "kW", 2.0,
               "손실 항으로 유의미해지는 문턱",
               f"등가 누설면적 {area:,.0f} mm² ({m3h:.1f} m³/h) — 관통부 "
               f"{LM.LEAK_RAW*LM.N_PEN*LM.SEAL_FACTOR:,.0f} + 셔터 씰 "
               f"{2*(SHUT_W+SHUT_H)*2*SEAL_SPEC:,.0f}. **배기 엔탈피와 같은 "
               f"항이다** — 부압이 빼내는 만큼 새 구멍으로 들어오므로 따로 "
               f"세면 두 번 센다"),
        Result("HB7", "냉간 기동 시간", su["minutes"], "min", 45.0,
               "교대 준비 시간 — 이보다 길면 첫 시간 처리량이 계약을 못 맞춘다",
               f"내부 강재 {su['inner']/1e6:.0f} + 단열재 {su['insul']/1e6:.0f} + "
               f"외피측 {su['outer']/1e6:.0f} + 기체 {su['gas']/1e6:.1f} = "
               f"**{su['total']/1e6:.0f} MJ** ({su['kwh']:.0f} kWh). "
               f"정상상태 수지에는 안 나오지만 **교대 첫 시간의 처리량이 여기 "
               f"걸린다** — 예열을 교대 전에 시작하는 것이 운전 규칙이 된다"),
        Result("HB8", "포크가 퍼올려 나가는 열", b["fork"], "kW", 2.0,
               "손실 항으로 유의미해지는 문턱",
               f"전열률이 정한다 — h {FORK_H:.0f} W/(m²·K) · A {FORK_AREA:.1f} m² · "
               f"노출 {FORK_EXPOSE:.0f} s. **처음에 포크가 통째로 열화한다고 "
               f"놓아 13 kW 가 나왔고 수지가 η 64.3 % 로 너무 잘 닫혔다** — "
               f"그 온도변화는 5 초에 140 kW 를 요구하는데 정격이 100 kW 다. "
               f"질량이 아니라 **대기 위치**가 정하는 항이라, 실온으로 물러나면 "
               f"{fork(t_rest=T_AMB):.3f} kW 로 {fork(t_rest=T_AMB)/b['fork']:.1f} 배가 "
               f"된다 (RHB3)"),
    ], dict(b=b, bt=bt, startup=su, per_cycle=per_cycle, small=small,
            area=area, m3h=m3h)


def requirements() -> list[Req]:
    _, ex = run()
    b, su = ex["b"], ex["startup"]
    return [
        Req("RHB1", "손실 예산의 정의를 바꾼다",
            f"계약 {RATE_CONTRACT:.0f} 장/h 에서 손실 {b['loss']:.1f} kW · "
            f"평균 IR {b['p_ir']:.1f} kW",
            "사양서 5.1항 · 콘솔 열수지 서술 · 전기부하 검토",
            f"'정격 100 − 유효 65 = 손실 35 kW' 는 두 운전점을 뺀 값이라 "
            f"물리적 의미가 없다. 정상상태에서 계를 떠나는 것은 "
            f"{b['loss']:.1f} kW 이고, 평균 IR 소요는 {b['p_ir']:.1f} kW 다. "
            f"**설치정격 100 kW 는 승온 속도가 정하지 정상 소비가 정하지 "
            f"않는다** — 두 값을 같은 표에 나란히 적어야 오해가 안 생긴다"),
        Req("RHB2", "격리실 높이", "한 단 높이로 줄일 수 있는지 확인",
            "상세설계 · M-002 에어록",
            f"에어록이 손실의 {ex['b']['airlock']/b['loss']:.0%} 이고 그 크기를 "
            f"정하는 것은 격리실 부피다. 전고 셔터를 한 단 높이로 줄이면 "
            f"**{b['airlock']-ex['small']:.1f} kW** 를 아낀다. 포크가 챔버 안에서 "
            f"층을 고르는 구조라면 격리실이 전고일 이유가 없다 — 못 줄인다면 "
            f"그 이유를 도면 주기에 남긴다"),
        Req("RHB3", "포크 대기 위치", "격리실 안 (실온 노출 금지)",
            "상세설계 · 운전 시퀀스",
            f"포크가 실온으로 물러나면 {fork(t_rest=T_AMB):.3f} kW, 격리실에서 "
            f"기다리면 {b['fork']:.3f} kW 다 — {fork(t_rest=T_AMB)/b['fork']:.1f} 배. "
            f"작은 항이지만 **질량이 아니라 대기 위치가 정한다**는 점이 중요하다. "
            f"시퀀스로 지켜야 하고 도면만으로는 안 지켜진다"),
        Req("RHB4", "예열을 교대 전에 시작한다",
            f"냉간 기동 {su['minutes']:.0f} 분 · {su['kwh']:.0f} kWh",
            "운전 지침 · PLC 스케줄",
            f"챔버 축열 {su['total']/1e6:.0f} MJ 는 정상상태 수지에 안 나오지만 "
            f"**교대 첫 시간의 처리량이 여기 걸린다.** 예열을 근무 시작에 "
            f"맞추면 첫 시간이 통째로 빈다 — 타이머 기동을 시퀀스에 넣는다"),
        Req("RHB5", "실측으로 닫는다",
            "IR 회로 전력량계 · 배기 유량·엔탈피 · 벽 열류계 3점 · 계면 이력",
            "파일럿 PT-05",
            f"이 수지는 램프 배광과 파장별 흡수율을 못 본다 — 백시트는 "
            f"근적외를 많이 반사하고, 그 몫이 어디로 가는지는 공동 안에서만 "
            f"돌다가 결국 위 항 중 하나로 나간다. **어느 항인지는 실측이 "
            f"정한다.** 수지 오차 10 % 안에서 닫히면 이 검토를 확정으로 본다"),
    ]


def report() -> str:
    L = []
    add = L.append
    rs, ex = run()
    b = ex["b"]
    add("=" * 78)
    add("DG-HK60C 열수지 — 손실 35 kW 의 행방 (R5)")
    add("=" * 78)
    add("")
    add(f"── 제어체적: 챔버 내부 · 정상상태 · {RATE_CONTRACT:.0f} 장/h ────")
    add(f"   {'IN  IR 전기 (평균, 역산)':38s} {b['p_ir']:8.2f} kW")
    add("")
    for name, key in (("패널 엔탈피 (하는 일)", "panel"),
                      ("에어록 교환", "airlock"),
                      ("벽 전도", "wall"),
                      ("침기 = 배기 엔탈피", "infil"),
                      ("포크 반출", "fork"),
                      ("램프 단자 전도", "terminal")):
        add(f"   {'OUT ' + name:38s} {b[key]:8.2f} kW  {b[key]/b['p_ir']:6.1%}")
    add(f"   {'    손실 소계':38s} {b['loss']:8.2f} kW  {b['loss']/b['p_ir']:6.1%}")
    add(f"   {'    정상상태 효율':38s} {b['eta']:8.1%}"
        f"   (가정 {ETA_ASSUMED:.0%} · 여유 {b['assumed_loss']-b['loss']:.1f} kW)")
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
    add("전 항목 만족" if not bad else f"★ {bad} 항목 초과")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
