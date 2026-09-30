#!/usr/bin/env python3
"""GC-101 유리 냉각 — 필요한 h 에서 공기 계통을 세운다.

콘솔은 냉각 랙 단수를 GCOOL_H = 25 W/(m²·K) 한 숫자에서 낸다. 그 h 를 무엇이
내는지는 아무도 세지 않았다. 랙 −y 벽에 축류 팬 한 줄(Ø520 × 단수 + 1)을 그렸는데
팬 여섯이 476 피치로 서로 · 가운데 기둥과 겹쳤고, 카탈로그는 그 팬을 '지붕 프레임'
에 달았다. 겹침보다 큰 문제는 풍량이다 — 여기서 센다.

── 무엇이 필요한가 ─────────────────────────────────────────────────
유리는 얇아서(Bi ≈ 0.04) 한 덩어리로 식는다. 양면이 같은 h 를 받으면

    t = m''·c / (2h) · ln((T_in − T∞) / (T_out − T∞))

이고, 랙이 유리를 쥐고 있을 수 있는 시간은 단수 × 택트다. 그 시간 안에 끝내는
최소 h 가 h_req 이고, 콘솔의 GCOOL_H 는 그보다 커야 한다 (열해석 T9).

── 옆에서 불면 (축류 팬 벽 · 교차류) ───────────────────────────────
공기가 단 사이 통로를 +y → −y 로 지나며 유리 윗면 · 아랫면을 핥는다. 유리 폭
L = 1.4 m 를 지나는 평판 경계층이다. 급기 필터 · 데크 레일이 경계층을 흔든다고 보고
전 길이 난류 식 Nu = 0.037·Re^0.8·Pr^⅓ 을 써도 h 25 에 유리 위 7 m/s — 통로
(단수 + 1) × 데크 길이 × 틈 전체를 그 속도로 밀어야 하므로 60 m³/s 가 넘는다.
h_req 만 내려 해도 28 m³/s 다. 급기 필터 면(+y · G4 24 장)이 정격으로 받는 것은
21 m³/s 이고, 경계층이 층류로 남으면(Re < 5×10⁵) 같은 속도에서 h 가 절반 아래다.
팬 크기를 바꿔도 이 계산은 바뀌지 않는다 — 두 배치를 셌다:

    A  칸마다 3 단 × 2 칸 — 칸에 드는 가장 큰 축류 팬 (Ø1000 · 6극)
    B  칸마다 Ø450 3 대 한 줄 (4극)

A 는 필터 면속도가 정격을 넘고 방책선 소음이 80 dBA 를 훨씬 넘는다. B 는 풍량이
모자라 h 가 필요의 절반도 안 된다. 둘 다 버린다.

── 위아래에서 뿜으면 (냉각 뱅크 · 충돌 분류) ──────────────────────
가열실은 단 사이 뱅크 자리(단수 + 1)에 IR 뱅크를 둔다. 냉각 랙은 같은 자리에
분사 상자 — 냉각 뱅크 — 를 둔다. 노즐판이 유리 한 면을 s × s 칸으로 덮고 칸마다
Ø D 노즐 하나가 v 로 뿜는다. 분류가 경계층을 뚫고 직접 닿으므로 h 가 통로 전체의
속도가 아니라 분사 속도로 정해진다 — Martin (1977) 원형 노즐 배열:

    Nu = Pr^0.42 · K(H/D, f) · G(H/D, f) · ½·Re^⅔
    K = [1 + ((H/D)/(0.6/√f))⁶]^(−0.05)
    G = 2√f · (1 − 2.2√f) / (1 + 0.2·(H/D − 6)·√f)
    f = (π/4)·(D/s)²       범위 2,000 ≤ Re ≤ 100,000 · 0.004 ≤ f ≤ 0.04 · 2 ≤ H/D ≤ 12

H 는 노즐판에서 유리까지 — 뱅크가 단 사이 한가운데 서므로 단 피치의 절반에서 뱅크
반 두께를 뺀 값이다. 콘솔 GCOOL_JET_D · S · V · BANK_T 가 이 식의 입력이고, 그
h 가 GCOOL_H × 1.2 이상이어야 한다 (상관식 ±15 % · 뱅크 사이 배분 ±5 %).
급기량은 노즐 수 × 노즐 면적 × 분사 속도다 — 표준 3.3 m³/s. 옆바람의 10 분의 1 이다.

── 급기 유닛 · 압력 · 소음 ──────────────────────────────────────────
팬은 하나다 — +y 바닥, 외장 안에 선 급기 유닛(플러그 팬 · 인버터 · G4 + F7 · 흡입 ·
토출 소음기). 분류가 유리에 직접 닿으므로 먼지가 곧 검사 불량이다 — F7 까지 거른다.
압력은 필터(중간 수명) + 분배(매니폴드 · 분기 · 댐퍼) + 노즐 유출 + 케이싱이고,
동력은 Q·Δp/η 에서 한 등급 위 전동기를 고른다. 소음은 VDI 2081 의 추정식

    Lw = Lws + 10·lg(Q / 1 m³/s) + 20·lg(Δp / 1 Pa)          [dB(A)]

으로 원음을 잡고, 사람이 운전 중 설 수 있는 가장 가까운 자리(+y 방책선 · −y 외장
밖)에서 사양서 80 dBA 에 다른 소음원 몫 3 dB 를 뺀 77 을 넘지 않게 흡입 · 토출
소음기의 삽입손실을 정한다. 구매 사양은 그 값을 적는다.

**이 모델이 못 보는 것** — 뱅크 사이 풍량 배분(밸런싱 댐퍼로 맞추고 FAT 에서 잰다),
노즐 칸 무늬가 유리 면내에 남기는 온도차(s/H ≤ 1 로 분류가 닿기 전에 섞이게 두었다 —
열화상으로 본다), 사용한 공기가 실내에 내놓는 유리 현열(건물 환기가 받는다). 실측은
파일럿 PT-06 이 노즐판 한 칸으로 한다.
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cycle as CY  # noqa: E402
from console_consts import const as c  # noqa: E402

# ── 공기 물성 — 막온도 60 ℃ (유리 평균 100 ℃ 와 급기 25 ℃ 사이)
NU_AIR = 1.90e-5          # m²/s
K_AIR = 0.0287            # W/(m·K)
PR_AIR = 0.70
RHO_AIR = 1.18            # kg/m³ — 팬이 다루는 급기 (25 ℃)

# ── 설계 기준 (총괄 결정)
H_MARGIN = 1.20           # 분사 h ≥ GCOOL_H × 1.2 — Martin ±15 % · 뱅크 배분 ±5 %
MARTIN_RE = (2_000, 100_000)
MARTIN_F = (0.004, 0.04)
MARTIN_HD = (2.0, 12.0)
SH_MAX = 1.0              # 노즐 피치 / 거리 — 분류가 유리에 닿기 전에 이웃과 섞이게
CD_NOZZLE = 0.65          # 펀칭 구멍 유출계수
PLENUM_RATIO = 0.40       # 뱅크 안 흐름 / 분사 속도 — 넘으면 노즐마다 풍량이 갈린다
MANIFOLD_V = 8.0          # m/s 매니폴드 설계 속도
MANIFOLD_W = 1.0          # m 매니폴드 폭 (x) — 한 칸(1,240)에 선다
ZETA_DIST = 2.5           # 분배 손실 — 매니폴드 분기 · 밸런싱 댐퍼 · 뱅크 입구 (동압 배수)
DP_FILTER_G4 = 100.0      # Pa G4 중간 수명 (초기 45 → 교체 150)
DP_FILTER_F7 = 175.0      # Pa F7 백필터 중간 수명 (초기 100 → 교체 250)
DP_CASING = 50.0          # Pa 케이싱 · 소음기 · 토출 이음
FILTER_Q = 3400 / 3600       # m³/s 592 × 592 필터 한 장의 정격 (3,400 m³/h)
FILTER_FACE = 0.592       # m
ETA_FAN = 0.60            # 플러그 팬 · 전동기 · 인버터 종합
MOTOR_MARGIN = 1.10
MOTORS = (0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5, 11.0, 15.0, 18.5, 22.0, 30.0)   # kW IEC
AHU_DEPTH = 1.0           # m 급기 유닛 깊이 (y) — 기둥 판과 외장 사이에 선다
AHU_W = 1.4               # m 급기 유닛 길이 (x) — 필터 두 장 폭 + 케이싱
AHU_BASE = 0.7            # m 팬 · 소음기 칸 높이 — 필터 칸은 그 위에 줄 수만큼
COL_CLEAR = 0.25          # m 기둥 중심선에서 유닛 −y 면까지 — 판 반폭 200 + 틈 50

# ── 소음 (VDI 2081 추정 · 사양서 작업위치 ≤ 80 dBA)
LWS_CENTRIFUGAL = 37.0    # dB(A) 비음향파워 — 후향 원심 (보수측)
LWS_AXIAL = 40.0          # dB(A) 비음향파워 — 축류 벽 팬
LP_LIMIT = 80.0           # dB(A) 사양서 작업위치
LP_OTHER = 3.0            # dB 다른 소음원 몫
AISLE = 0.5               # m 외장 밖 −y 통로에 사람이 서는 거리

# ── 교차류 후보 (A · B) — 축류 팬의 무차원 곡선
FAN_PHI = 0.215           # 자유 토출 유량계수 Q = φ·(π/4)D²·u
FAN_PSI0 = 0.25           # 체절 압력계수 p0 = ψ0·ρu²/2
ETA_AXIAL = 0.45
RPM = {4: 1440, 6: 960, 8: 720}
AXIAL_SIZES = (0.45, 0.50, 0.56, 0.63, 0.71, 0.80, 0.90, 1.00)   # m
AXIAL_HOUSING = 0.10      # m 팬 지름 + 하우징
DECK_T = 0.105            # m 데크 두께 (종재 65 + 레일 40) — 통로 높이에서 뺀다
BYPASS = 0.15             # 교차류가 유리 밖(데크 끝 · 포크 개구)으로 새는 몫
ZETA_RACK = 1.5           # 랙 통로 입출구 손실 (동압 배수)
FACE_Z0 = 0.65            # m 급기 필터 면 하단
RE_TRANSITION = 5e5


# ── 콘솔 상수 (배치 핀을 따른다 — variant.load('twin', 'glass_cool'))
DECKS = round(c("DECKS"))
TAKT = CY.TAKT
PANEL_L, PANEL_W = c("PANEL_L"), c("PANEL_W")
M_GLASS, CP_GLASS = c("MASS_GLASS"), c("CP_GLASS") * 1000
T_IN, T_OUT, T_AMB = c("GCOOL_T_IN"), c("GCOOL_T_OUT"), c("GCOOL_T_AMB")
H_DESIGN = c("GCOOL_H")
JET_D, JET_S, JET_V, BANK_T = c("GCOOL_JET_D"), c("GCOOL_JET_S"), c("GCOOL_JET_V"), c("GCOOL_BANK_T")
BANK_L, BANK_W = c("GCOOL_BANK_L"), c("GCOOL_BANK_W")    # 뱅크 · 노즐판 외형
DZ, DZ0 = c("CDECK_DZ"), c("CDECK_Z0")
DECK_L = c("DECK_L")
RACK_COL_Y, RACK_W = c("RACK_COL_Y"), c("RACK_W")
CSKIN_Y, CFENCE_Y = c("CSKIN_Y"), c("CFENCE_Y")
_GC = c("CST").GC
GC_W, GC_INSET = _GC.w, c("GC_COL_INSET")
RACK_TOP = DZ0 + DZ * (DECKS - 1 + 0.5) + 0.66          # 콘솔 cGlassRack top
BANKS = DECKS + 1                                        # IR 뱅크 자리 그대로
BAY = (GC_W - 2 * GC_INSET) / (round(c("RACK_COLS_X")) - 1) - 0.20   # 칸 순폭 — H-200 기둥 사이


# ── 필요한 h ──────────────────────────────────────────────────────────
def _log_ratio():
    return math.log((T_IN - T_AMB) / (T_OUT - T_AMB))


def h_required(decks: int = DECKS, takt: float = TAKT) -> float:
    """랙이 유리를 쥐는 시간(단수 × 택트) 안에 T_out 까지 식히는 최소 h."""
    return M_GLASS * CP_GLASS * _log_ratio() / (2 * decks * takt)


def cool_time(h: float) -> float:
    """양면 h 로 T_in → T_out 까지 — 콘솔 glassCoolSec() 와 같은 식."""
    return M_GLASS * CP_GLASS * _log_ratio() / (2 * h)


# ── 옆바람 (교차류 평판) ───────────────────────────────────────────────
def h_crossflow(v: float, laminar: bool = False) -> float:
    """유리 폭 PANEL_W 를 지나는 평판 평균 h. laminar=True 면 천이 전 층류 · 혼합."""
    re = v * PANEL_W / NU_AIR
    if laminar:
        nu = (0.664 * re ** 0.5 if re < RE_TRANSITION else 0.037 * re ** 0.8 - 871) * PR_AIR ** (1 / 3)
    else:
        nu = 0.037 * re ** 0.8 * PR_AIR ** (1 / 3)
    return nu * K_AIR / PANEL_W


def v_crossflow(h: float) -> float:
    """전 길이 난류로 h 를 내는 유리 위 풍속."""
    re = (h * PANEL_W / K_AIR / (0.037 * PR_AIR ** (1 / 3))) ** 1.25
    return re * NU_AIR / PANEL_W


def channel_area(decks: int = DECKS) -> float:
    """교차류가 지나는 통로 — 유리 위아래 (단수 + 1) × 데크 길이 × 틈."""
    return (decks + 1) * DECK_L * (DZ - DECK_T)


def filter_face() -> tuple[int, float]:
    """+y 급기 필터 면에 드는 592 필터 장수와 면적 — 옛 배치의 벽 전체."""
    w = GC_W - 0.7
    hgt = (RACK_TOP - 0.06) - FACE_Z0
    n = math.floor(w / 0.6) * math.floor(hgt / 0.6)
    return n, n * FILTER_FACE ** 2


def crossflow_q(h: float, decks: int = DECKS) -> float:
    """교차류로 h 를 내는 총풍량 — 새는 몫을 얹는다."""
    return v_crossflow(h) * channel_area(decks) / (1 - BYPASS)


def _axial(d: float, poles: int):
    u = math.pi * d * RPM[poles] / 60
    return FAN_PHI * math.pi / 4 * d * d * u, FAN_PSI0 * RHO_AIR * u * u / 2


def crossflow(label: str, d: float, poles: int, n: int, decks: int = DECKS) -> dict:
    """축류 팬 n 대가 필터 벽 · 랙 통로를 지나 내는 운전점과 그때의 h · 소음."""
    qf1, p0 = _axial(d, poles)
    qf = n * qf1
    nf, af = filter_face()
    ach = channel_area(decks)
    v_rated = FILTER_Q / FILTER_FACE ** 2

    def dp_sys(q):
        vf = q / af
        return DP_FILTER_G4 * (vf / v_rated) ** 1.5 + ZETA_RACK * RHO_AIR * (q / ach) ** 2 / 2

    lo, hi = 0.0, qf
    for _ in range(80):
        mid = (lo + hi) / 2
        if p0 * (1 - (mid / qf) ** 2) > dp_sys(mid):
            lo = mid
        else:
            hi = mid
    q = lo
    dp = dp_sys(q)
    v = q * (1 - BYPASS) / ach
    h = h_crossflow(v)
    lw = LWS_AXIAL + 10 * math.log10(q) + 20 * math.log10(dp)
    r = CSKIN_Y + AISLE - RACK_W / 2
    return dict(label=label, fans=n, d=d, poles=poles, q=q, dp=dp, v=v,
                h=h, h_lam=h_crossflow(v, laminar=True), t=cool_time(h),
                decks_needed=math.ceil(cool_time(h) / TAKT - 1e-9),
                v_face=q / af, v_face_rated=v_rated, filters=nf,
                kw=q * dp / ETA_AXIAL / 1000, lw=lw, r=r, lp=lw - 10 * math.log10(2 * math.pi * r * r))


def candidate_a(decks: int = DECKS) -> dict:
    """칸마다 3 단 × 2 칸 — 칸에 드는 가장 큰 축류 팬."""
    wall = (RACK_TOP - 0.06) - FACE_Z0
    fit = min(BAY, wall / 3) - AXIAL_HOUSING
    d = max(s for s in AXIAL_SIZES if s <= fit + 1e-9)
    return crossflow(f"A · 3 단 × 2 칸 · Ø{d * 1000:.0f} 6극", d, 6, 6, decks)


def candidate_b(decks: int = DECKS) -> dict:
    """칸마다 Ø450 3 대 한 줄."""
    return crossflow("B · 칸마다 Ø450 × 3 · 4극", 0.45, 4, 6, decks)


# ── 위아래 분사 (냉각 뱅크) ────────────────────────────────────────────
def jet_gap() -> float:
    """노즐판에서 유리까지 — 뱅크는 단 사이 한가운데."""
    return DZ / 2 - BANK_T / 2


def jets_per_face() -> tuple[int, int]:
    """유리 한 면을 s × s 칸으로 덮는 노즐 수 (x, y) — 콘솔 gcoolJets() 와 같은 식."""
    return math.floor(PANEL_L / JET_S + 1e-9), math.floor(PANEL_W / JET_S + 1e-9)


def martin(d: float = JET_D, s: float = JET_S, h_gap: float | None = None, v: float = JET_V) -> dict:
    """원형 노즐 정방 배열의 면평균 h (Martin 1977 · VDI 열전달 도감 G10)."""
    h_gap = jet_gap() if h_gap is None else h_gap
    f = math.pi / 4 * (d / s) ** 2
    sf = math.sqrt(f)
    hd = h_gap / d
    k = (1 + (hd / (0.6 / sf)) ** 6) ** -0.05
    g = 2 * sf * (1 - 2.2 * sf) / (1 + 0.2 * (hd - 6) * sf)
    re = v * d / NU_AIR
    nu = PR_AIR ** 0.42 * k * g * 0.5 * re ** (2 / 3)
    ok = (MARTIN_RE[0] <= re <= MARTIN_RE[1] and MARTIN_F[0] <= f <= MARTIN_F[1]
          and MARTIN_HD[0] <= hd <= MARTIN_HD[1])
    return dict(h=nu * K_AIR / d, nu=nu, re=re, f=f, hd=hd, s_h=s / h_gap, valid=ok)


def air_flow(decks: int = DECKS) -> float:
    """급기량 — 유리 면마다 노즐판 한 장 · 노즐 수 × 면적 × 분사 속도 (콘솔 gcoolAirQ)."""
    nx, ny = jets_per_face()
    return 2 * decks * nx * ny * math.pi / 4 * JET_D ** 2 * JET_V


def bank_flows(decks: int = DECKS) -> list[float]:
    """뱅크마다 풍량 — 맨 아래 · 맨 위는 한 면, 사이는 두 면."""
    one = air_flow(decks) / (2 * decks)
    return [one if b in (0, decks) else 2 * one for b in range(decks + 1)]


def bank_inlet() -> dict:
    """뱅크 한 개의 입구 · 안 흐름 — 두 면을 받는 뱅크가 기준이다.

    분기는 뱅크 +y 장변으로 들어간다. 입구 폭은 매니폴드 폭 · 높이는 뱅크 두께다.
    뱅크 안에서 공기는 −y 로 퍼지며 노즐로 빠진다 — 그 흐름이 분사 속도에 비해 빠르면
    입구 쪽 노즐과 먼 노즐의 풍량이 갈린다."""
    q = max(bank_flows())
    a_in = MANIFOLD_W * BANK_T * 0.8                     # 뱅크 판 두께 · 테두리를 뺀 순높이
    a_cross = BANK_L * BANK_T                            # 뱅크를 가로지르는 단면
    return dict(q=q, v_in=q / a_in, v_cross=q / a_cross, ratio=q / a_cross / JET_V)


def manifold(decks: int = DECKS) -> dict:
    q = air_flow(decks)
    depth = math.ceil(q / MANIFOLD_V / MANIFOLD_W * 20 - 1e-9) / 20
    return dict(w=MANIFOLD_W, depth=depth, v=q / (MANIFOLD_W * depth),
                z0=0.20, z1=DZ0 + DZ * decks + BANK_T)


def pressure(decks: int = DECKS) -> dict:
    """팬이 이겨야 하는 압력 — 필터(중간 수명) · 분배 · 노즐 유출 · 케이싱."""
    mf = manifold(decks)
    dist = ZETA_DIST * RHO_AIR * mf["v"] ** 2 / 2
    nozzle = RHO_AIR * JET_V ** 2 / (2 * CD_NOZZLE ** 2)
    parts = dict(filters=DP_FILTER_G4 + DP_FILTER_F7, dist=dist, nozzle=nozzle, casing=DP_CASING)
    parts["total"] = sum(parts.values())
    return parts


def filters(decks: int = DECKS) -> int:
    """G4 · F7 각 장수 — 정격 풍량 이하로."""
    return math.ceil(air_flow(decks) / FILTER_Q - 1e-9)


def ahu(decks: int = DECKS) -> dict:
    """급기 유닛 외형 — 필터 두 장 폭 × 줄 수 높이 + 팬 · 소음기 칸."""
    rows = math.ceil(filters(decks) / 2)
    y0 = RACK_COL_Y + COL_CLEAR
    return dict(L=AHU_W, W=AHU_DEPTH, H=AHU_BASE + 0.6 * rows, rows=rows,
                y0=y0, y1=y0 + AHU_DEPTH)


def motor(decks: int = DECKS) -> dict:
    q, dp = air_flow(decks), pressure(decks)["total"]
    shaft = q * dp / ETA_FAN / 1000
    return dict(kw_shaft=shaft, kw=min(m for m in MOTORS if m >= shaft * MOTOR_MARGIN - 1e-9))


def noise(decks: int = DECKS) -> dict:
    """원음 · 자리마다 허용 음향파워 · 흡입 · 토출 소음기 삽입손실."""
    q, dp = air_flow(decks), pressure(decks)["total"]
    lw = LWS_CENTRIFUGAL + 10 * math.log10(q) + 20 * math.log10(dp)
    a = ahu(decks)
    lp_target = LP_LIMIT - LP_OTHER
    r_in = CFENCE_Y - (a["y0"] + a["y1"]) / 2                # 흡입 → +y 방책선
    r_out = CSKIN_Y + AISLE - RACK_W / 2                     # 토출(노즐 · 랙) → −y 통로
    lwmax = lambda r: lp_target + 10 * math.log10(2 * math.pi * r * r)
    per_path = lw - 3                                        # 흡입 · 토출이 반씩
    il_in = per_path - (lwmax(r_in) - 3)
    il_out = per_path - (lwmax(r_out) - 3)
    il = math.ceil(max(il_in, il_out, 0.0) - 1e-9)
    lp_in = per_path - il - 10 * math.log10(2 * math.pi * r_in * r_in)
    lp_out = per_path - il - 10 * math.log10(2 * math.pi * r_out * r_out)
    lp = 10 * math.log10(10 ** (lp_in / 10) + 10 ** (lp_out / 10))
    return dict(lw=lw, r_in=r_in, r_out=r_out, lw_max_in=lwmax(r_in), lw_max_out=lwmax(r_out),
                il=il, lp_in=lp_in, lp_out=lp_out, lp=lp, lp_target=lp_target)


def design(decks: int = DECKS) -> dict:
    """냉각 뱅크 설계 한 벌 — 문서 · 카탈로그 · 조달이 이 값을 쓴다."""
    m = martin()
    q = air_flow(decks)
    return dict(
        decks=decks, banks=decks + 1, takt=TAKT, h_req=h_required(decks), h_design=H_DESIGN,
        h_jet=m["h"], martin=m, jets=jets_per_face(), gap=jet_gap(),
        q=q, q_h=q * 3600, bank_q=bank_flows(decks), inlet=bank_inlet(), manifold=manifold(decks),
        dp=pressure(decks), filters=filters(decks), ahu=ahu(decks), motor=motor(decks),
        noise=noise(decks), t_design=cool_time(H_DESIGN), t_jet=cool_time(m["h"]),
        heat_kw=M_GLASS * PANEL_L * PANEL_W * CP_GLASS * (T_IN - T_OUT) / TAKT / 1000,
        cross_q_req=crossflow_q(h_required(decks), decks),
        cross_q_design=crossflow_q(H_DESIGN, decks),
        filter_face_q=filter_face()[0] * FILTER_Q,
    )


def candidates(decks: int = DECKS) -> list[dict]:
    """두 팬 배치(A · B)와 냉각 뱅크(C) — 같은 기준으로 센 한 줄씩."""
    d = design(decks)
    c_row = dict(label=f"C · 냉각 뱅크 {d['banks']} · Ø{JET_D * 1000:.0f} @{JET_S * 1000:.0f} · {JET_V:g} m/s",
                 q=d["q"], dp=d["dp"]["total"], h=d["h_jet"], h_lam=d["h_jet"], t=d["t_jet"],
                 decks_needed=math.ceil(d["t_jet"] / TAKT - 1e-9), kw=d["motor"]["kw_shaft"],
                 lp=d["noise"]["lp"], v=JET_V, v_face=d["q"] / (d["filters"] * FILTER_FACE ** 2),
                 v_face_rated=FILTER_Q / FILTER_FACE ** 2)
    return [candidate_a(decks), candidate_b(decks), c_row]


def verdict(row: dict, decks: int = DECKS) -> list[str]:
    """한 후보가 어디서 떨어지는가 — 빈 목록이면 통과."""
    bad = []
    if row["h"] < H_MARGIN * H_DESIGN:
        bad.append(f"h {row['h']:.1f} < {H_MARGIN * H_DESIGN:.0f}")
    if row["h_lam"] < h_required(decks):
        bad.append(f"층류면 h {row['h_lam']:.1f} < 필요 {h_required(decks):.1f}")
    if row["v_face"] > row["v_face_rated"] + 1e-9:
        bad.append(f"필터 면속도 {row['v_face']:.1f} > 정격 {row['v_face_rated']:.1f} m/s")
    if row["lp"] > LP_LIMIT - LP_OTHER + 1e-9:
        bad.append(f"소음 {row['lp']:.0f} > {LP_LIMIT - LP_OTHER:.0f} dB(A)")
    return bad


def report() -> str:
    d = design()
    m, n = d["martin"], d["noise"]
    L = [
        "=" * 78,
        f"GC-101 유리 냉각 — {d['decks']} 단 · 택트 {TAKT:.1f} s · {T_IN:.0f} → {T_OUT:.0f} ℃",
        "=" * 78,
        f"필요 h        {d['h_req']:.2f} W/(m²·K)   (단수 × 택트 = {d['decks'] * TAKT:.0f} s)",
        f"설계 h        {H_DESIGN:.0f}  → 냉각 {d['t_design']:.0f} s · 필요 "
        f"{math.ceil(d['t_design'] / TAKT - 1e-9)} 단",
        f"옆바람으로    h_req {d['cross_q_req']:.1f} m³/s · 설계 h {d['cross_q_design']:.1f} m³/s "
        f"(필터 면 정격 {d['filter_face_q']:.1f})",
        "",
        f"{'후보':34s}{'Q m³/s':>8s}{'Δp Pa':>8s}{'h':>7s}{'층류':>7s}{'냉각 s':>8s}{'kW':>7s}{'Lp':>6s}  판정",
    ]
    for r in candidates():
        bad = verdict(r)
        L.append(f"{r['label'][:32]:34s}{r['q']:8.1f}{r['dp']:8.0f}{r['h']:7.1f}{r['h_lam']:7.1f}"
                 f"{r['t']:8.0f}{r['kw']:7.1f}{r['lp']:6.0f}  {'통과' if not bad else ' · '.join(bad)}")
    L += [
        "",
        f"냉각 뱅크     {d['banks']} 개 · 노즐 {d['jets'][0]} × {d['jets'][1]} / 면 · H {d['gap'] * 1000:.0f} mm "
        f"(H/D {m['hd']:.1f} · f {m['f'] * 100:.2f} % · Re {m['re']:,.0f} · s/H {m['s_h']:.2f})",
        f"분사 h        {d['h_jet']:.1f} W/(m²·K) ≥ 설계 {H_DESIGN:.0f} × {H_MARGIN} = {H_DESIGN * H_MARGIN:.0f}"
        f"   → 냉각 {d['t_jet']:.0f} s",
        f"급기          {d['q']:.2f} m³/s ({d['q_h']:,.0f} m³/h) · 뱅크 안 흐름/분사 "
        f"{d['inlet']['ratio']:.2f} · 매니폴드 {d['manifold']['w'] * 1000:.0f} × "
        f"{d['manifold']['depth'] * 1000:.0f} ({d['manifold']['v']:.1f} m/s)",
        "압력          " + " · ".join(f"{k} {v:.0f}" for k, v in d["dp"].items()) + " Pa",
        f"급기 유닛     필터 G4 · F7 각 {d['filters']} 장 · {d['ahu']['L'] * 1000:.0f} × "
        f"{d['ahu']['W'] * 1000:.0f} × {d['ahu']['H'] * 1000:.0f} · 축동력 {d['motor']['kw_shaft']:.2f} kW → "
        f"{d['motor']['kw']:g} kW",
        f"소음          원음 {n['lw']:.1f} dB(A) · 흡입 · 토출 소음기 IL ≥ {n['il']} dB → "
        f"+y 방책 {n['lp_in']:.0f} · −y 통로 {n['lp_out']:.0f} · 합 {n['lp']:.0f} ≤ {n['lp_target']:.0f}",
        f"실내로        유리 현열 {d['heat_kw']:.1f} kW (건물 환기)",
    ]
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
