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

import airlock as AIR  # noqa: E402
import analysis_thermal as TH  # noqa: E402
import lampmount as LM  # noqa: E402
import parts as PT  # noqa: E402
from analysis_thermal import Req, Result  # noqa: E402
import cycle as CY  # noqa: E402
import irbank as IR  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 운전점 ───────────────────────────────────────────────────────────
RATE_CONTRACT = float(CY.NET_TARGET) # 장/h 계약 순생산 (콘솔 NET_TARGET)
RATE_THERMAL = CY.RATE_THERMAL       # 장/h 열공정 한계 (콘솔 thermalModel)
TAKT = CY.TAKT                       # s 라인 사이클 — 에어록이 이 주기로 열린다
RATED_KW = c("LAMPS") * 2.5          # 100 kW 설치정격
ETA_ASSUMED = 0.65                   # 콘솔 MODEL 기본값
T_HOT, T_AMB = c("T_TARGET"), c("T_AMB")

# 장당 열량 — 콘솔과 같은 식
Q_PANEL_KJ = CY.Q_PANEL_KJ                   # kJ/장 — 콘솔 thermalModel 의 q (arealCp 8.7359)

# ── 공기 ─────────────────────────────────────────────────────────────
CP_AIR = 1005.0                      # J/(kg·K)
RHO_AIR = lambda t: 353.0 / (273.15 + t)     # kg/m³ 대기압 건공기

# ── 챔버·에어록 ──────────────────────────────────────────────────────
CAV_L, CAV_W, CAV_H = IR.CAVITY_L, IR.CAVITY_W, 3.60   # m 내부 공동 — 평면은 IR 뱅크 모델과 같은 값
SEAL_SPEC = 3.0                              # mm²/m 압착 씰의 등가 누설면적


def chamber_volume() -> float:
    return CAV_L * CAV_W * CAV_H


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
def airlock() -> tuple[float, float]:
    """문이 열려 있는 동안 개구를 지나는 부력 교환유동. `tools/airlock.py` 가 푼다.

    **처음에는 이 항을 통째로 잘못 세웠다.** 있지도 않은 격리실의 부피를
    문 포켓 깊이(0.30 m)로 잡고, 내문으로 나간 열과 외문으로 나간 열을
    더했다 — 같은 열인데. 도면을 다시 보니 납품 배치(REV.21C)에는 격리실이
    아예 없다(R-106 차이표: "격리실 없음 · 포크 진입 중 챔버 열림").

    격리실이 없으면 교환량을 막는 것은 부피가 아니라 **개구를 지나는
    유동**이고, 그것은 개구 높이의 1.5 제곱에 비례한다. 그래서 이 항의
    크기를 정하는 것은 **문의 높이와 열려 있는 시간**이다.
    """
    j = AIR.kw() * TAKT * 1000.0
    return j / 1000.0, AIR.kw()                          # kJ/사이클 · kW
# ── OUT ④ 침기 ──────────────────────────────────────────────────────
def infiltration() -> tuple[float, float, float]:
    """부압 운전이 부르는 찬 공기. 관통부 + 셔터 씰.

    챔버는 연기를 잡으려고 −20 Pa 로 돈다 (램프 지지 검토 RLM3). 배기가
    빼내는 만큼이 그대로 새 구멍으로 들어오므로, **배기 엔탈피 손실 =
    누설 유량 엔탈피**다. 둘을 따로 세면 두 번 센다.
    """
    a_pen = LM.LEAK_RAW * LM.N_PEN * LM.SEAL_FACTOR          # mm² 관통부
    perim = AIR.shutters()["perim"]                          # m 단별 셔터 전 둘레
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
FORK_H = 12.0            # W/(m²·K) 복사(ε 0.5) + 자연대류
FORK_EXPOSE = 2 * AIR.REACH / AIR.V_FORK        # s 챔버 체류 = 포크 왕복


def fork(t_rest: float = T_AMB, takt: float = TAKT) -> float:
    """TS-101 텔레스코픽 포크가 퍼올려 나가는 열.

    **처음에 200 배 틀렸다.** 포크 42 kg 이 매 사이클 (140−40)/3 만큼
    통째로 오르내린다고 놓아 13 kW 가 나왔고, 그 값이 수지를 η 64.3 % 로
    "너무 잘" 닫았다 — 가정 65 % 와 소수점까지 맞은 것이 오히려 신호였다.
    되짚어 보니 그 온도변화는 699 kJ 을 5 초에 넣는 것이고 **140 kW** 가
    필요하다. IR 설치정격이 100 kW 다. 챔버가 줄 수 없는 열이었다.

    실제로는 **전열률이 정한다.** 노출 시간 동안 복사+대류로 들어가는
    만큼만 포크가 싣고 나간다:

        Q = h·A·(T챔버 − T포크)·t노출

    질량은 이 항에 안 들어온다. 들어오는 것은 **대기 온도와 노출 시간**이고,
    노출 시간은 에어록이 문을 열어 두는 시간과 **같은 시간**이다 — 포크가
    들어가 있는 동안 문이 열려 있으니까. 그래서 포크를 빠르게 하면 이 항과
    에어록 항이 **함께** 준다 (RHB3).
    """
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
    full = AIR.solve()[0]["kw"]                 # 전고 개구였다면

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
               f"회당 {per_cycle:.0f} kJ · 택트 {TAKT:.1f} s · 손실의 "
               f"{al/b['loss']:.0%}. 납품 배치에는 격리실이 없어(R-106 차이표) "
               f"교환을 막는 것은 부피가 아니라 **개구를 지나는 부력유동**이고, "
               f"그것은 개구 높이의 **1.5 제곱**에 비례한다. 문의 크기와 열려 "
               f"있는 시간이 이 항의 전부다 (에어록 검토 AL1~AL8)"),
        Result("HB5", "개구 높이가 사 오는 손실", full, "kW", b["assumed_loss"],
               f"η {ETA_ASSUMED:.2f} 가 허용하는 손실 전액 {b['assumed_loss']:.1f} kW — "
               f"한 항이 이것을 넘으면 설계가 성립하지 않는다",
               f"카탈로그의 전고 셔터({AIR.FULL_H:.2f} m)를 그대로 열면 이 항 "
               f"하나가 **{full:,.0f} kW** 로 설치정격 {RATED_KW:.0f} kW 를 "
               f"{full/RATED_KW:.0f} 배 넘는다. 단별 셔터로 나눠 패널 통과 "
               f"포락선({AIR.OPEN_H*1e3:.0f} mm)만 열면 {al:.2f} kW 다 — "
               f"**{full/al:.0f} 배.** RHB2 는 격리실을 줄이라고 물었는데 "
               f"답은 격리실이 아니라 **문**이었다 (RAL1)"),
        Result("HB6", "침기 (관통 + 셔터 씰)", inf, "kW", 2.0,
               "손실 항으로 유의미해지는 문턱",
               f"등가 누설면적 {area:,.0f} mm² ({m3h:.1f} m³/h) — 관통부 "
               f"{LM.LEAK_RAW*LM.N_PEN*LM.SEAL_FACTOR:,.0f} + 셔터 씰 "
               f"{AIR.shutters()['perim']*SEAL_SPEC:,.0f} (단별 셔터 "
               f"{AIR.shutters()['n']} 장). **배기 엔탈피와 같은 "
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
               f"노출 {FORK_EXPOSE:.1f} s. **처음에 포크가 통째로 열화한다고 "
               f"놓아 13 kW 가 나왔고 수지가 η 64.3 % 로 너무 잘 닫혔다** — "
               f"그 온도변화는 5 초에 140 kW 를 요구하는데 정격이 100 kW 다. "
               f"질량이 아니라 **노출 시간**이 정하는 항이고, 그 시간은 포크 "
               f"왕복 {2*AIR.REACH:.1f} m ÷ {AIR.V_FORK:.2f} m/s 로 **에어록이 "
               f"문을 열어 두는 시간과 같다** — 포크를 빠르게 하면 두 항이 "
               f"함께 준다 (RHB3)"),
    ], dict(b=b, bt=bt, startup=su, per_cycle=per_cycle, full=full,
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
        Req("RHB2", "격리실이 아니라 문을 줄인다",
            f"단별 셔터 {AIR.shutters()['n']} 장 · 개구 "
            f"{AIR.OPEN_W*1e3:,.0f} × {AIR.OPEN_H*1e3:.0f} — 격리실 미채용",
            "상세설계 · M-002 · 에어록 검토 RAL1~RAL5",
            f"이 요구는 '격리실을 한 단 높이로 줄일 수 있는가' 로 나갔고, "
            f"답은 **격리실이 아니었다.** 납품 배치에는 격리실이 애초에 없고"
            f"(R-106 차이표), 격리실이 없으면 교환을 막는 것은 부피가 아니라 "
            f"개구를 지나는 부력유동이며 그것은 **높이의 1.5 제곱**이다. "
            f"전고 개구 {ex['full']:,.0f} kW → 단별 개구 {b['airlock']:.2f} kW. "
            f"거꾸로 개구를 줄이고 나면 격리실을 더해도 아끼는 것이 "
            f"**0.00 kW** 라 사지 않는다 (AL4)"),
        Req("RHB3", "포크 왕복이 두 항을 동시에 정한다",
            f"노출 {FORK_EXPOSE:.1f} s = 문 열림 시간 · 포크 "
            f"{AIR.V_FORK:.2f} m/s 를 사양으로 적는다",
            "상세설계 · TS-101 · 운전 시퀀스 · FAT",
            f"포크가 챔버에 들어가 있는 동안 문이 열려 있다 — **같은 시간**이다. "
            f"그래서 포크 속도가 절반이 되면 에어록 {b['airlock']:.2f} kW 와 포크 "
            f"{b['fork']:.3f} kW 가 **함께 두 배**가 된다. 이 커플링은 도면에 "
            f"안 보이고 시퀀스에만 있다 — 속도를 사양으로 적고 FAT 에서 "
            f"실측한다"),
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
