"""열해석 — 열이 어디까지 내려가고, 어디로 새는가.

콘솔의 열모델은 장당 몇 MJ 가 드는지를 답한다. 그런데 이 공정이 파는
것은 열량이 아니라 **계면 온도**다 — EVA/유리 계면이 140 ℃ 에 닿아야
칼날이 들어간다. 덩어리 모델에는 두께가 없어 그 자리가 아예 없다.

여섯 가지를 푼다:

  ① 패널 소킹     계면이 140 ℃ 에 닿는 시각이 덩어리 해와 얼마나 다른가.
                  그때 백시트 표면은 몇 도인가 (PVDF 융점 165 ℃)
  ② 체류시간 하한  백시트 상한이 정하는 유속 상한 → 체류시간 하한.
                  콘솔의 `fdmDwell:113.15` 를 대신할 근거
  ③ 유리 열응력    승온 · 급냉 두 국면의 판두께 방향 응력
  ④ 유리 냉각 랙   140 → 60 ℃ 체류시간과 덩어리 가정의 타당성 (Bi)
  ⑤ 가열실 벽      4겹 벽의 외피 표면온도 · 손실 · 열교가 하는 일
  ⑥ 칼날 카세트    200 → 60 ℃. 사람이 만지기까지 얼마나 기다리는가

해석기는 tools/therm.py — 닫힌해 다섯 건으로 검증했다.

결과는 두 갈래다. **검토(T)** 는 한계가 있어 통과·초과가 나오고,
**요구(R)** 는 이 해석이 만들어 낸 조건이라 아직 지킬 사람이 없다.
요구를 검토표에 억지로 끼워 넣으면 이용률 100 % 짜리 가짜 행이 생긴다 —
따로 낸다.

**이 해석이 못 보는 것**: 3차원 (면내 온도분포는 램프 배치와 반사판
형상이 정하고, 그것은 1차원으로 못 푼다), 대류계수 h (계산이 아니라
가정이다 — 파일럿에서 실측한다), EVA 의 가교 반응열, 유리의 광학 흡수
깊이, 램프의 단파장 복사가 연마 내피에서 반사되는 몫. 여기서 답하는
것은 **두께 방향 거동**이다.
"""

from __future__ import annotations

import functools
import math
import pathlib
import sys
from typing import NamedTuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import therm as T  # noqa: E402
from console_consts import const as c  # noqa: E402


class Result(NamedTuple):
    """한계가 있는 검토 — 통과하거나 초과한다."""

    id: str
    what: str
    value: float
    unit: str
    limit: float
    basis: str
    note: str

    @property
    def util(self) -> float:
        return self.value / self.limit if self.limit else 0.0

    @property
    def ok(self) -> bool:
        return self.util <= 1.0


class Req(NamedTuple):
    """이 해석이 만들어 낸 요구 — 설계·시운전·파일럿이 받아야 한다."""

    id: str
    what: str
    value: str
    owner: str          # 누가 받는가
    why: str


# ── 상수 — 콘솔에서 가져온다 ────────────────────────────────────────
T_AMB = c("T_AMB")                  # 25 ℃
T_TARGET = c("T_TARGET")            # 140 ℃ EVA/유리 계면
DECKS = int(c("DECKS"))             # 5
LAMPS = int(c("LAMPS"))             # 40
PANEL_L, PANEL_W = c("PANEL_L"), c("PANEL_W")
PANEL_A = PANEL_L * PANEL_W         # 2.88 m²
LAMP_KW, ETA = 2.5, 0.65            # 콘솔 기본 입력
USEFUL_KW = LAMPS * LAMP_KW * ETA   # 65 kW
FLUX = (USEFUL_KW * 1000 / DECKS) / PANEL_A     # W/m² 패널 양면 합
DWELL = 222.6                       # s 콘솔 열체류 (5장 소킹)
TAKT = 53.6                         # s 콘솔 라인 사이클

# 백시트 상한. 콘솔 주석: PVDF 165 · PVF 195. **낮은 쪽을 쓴다** —
# 어느 것이 붙어 올지는 폐패널이 정하지 우리가 정하지 않는다.
T_BACK_MAX = 165.0
T_BACK_DESIGN = 155.0               # 설계 여유 10 K

# 유리 — 어닐링 판유리
E_GL, ALPHA_GL, NU_GL = 73_000.0, 9.0e-6, 0.23      # MPa · 1/K · —
# 허용응력은 **사양서 5.5항이 이미 입찰자에게 준 값 7 MPa 을 그대로 쓴다.**
# EN 572-1 특성 휨강도 45 MPa 의 1/6 이라 매우 보수적이지만, 해석이
# 늦게 와서 허용치를 올리면 그것은 해석이 아니라 골대 옮기기다.
SIG_GL = 7.0

# 판두께 방향 ΔT 가 허용응력을 내는 값 — σ = Eα·ΔT/2(1−ν)
DT_THROUGH = SIG_GL * 2 * (1 - NU_GL) / (E_GL * ALPHA_GL)
# 면내 편차가 만드는 응력. 자유롭게 놓인 판은 완전구속이 아니다 —
# 중앙이 뜨겁고 가장자리가 찬 분포에서 가장자리 인장은 대략 ½·Eα·ΔT 다
# (판유리 열충격 실무의 어닐링 40 K 규칙이 서 있는 모델이 이것이다).
# 완전구속 상한 Eα·ΔT/(1−ν) 도 함께 낸다 — 클램프로 잡으면 그쪽이 된다.
DT_INPLANE = SIG_GL / (0.5 * E_GL * ALPHA_GL)
DT_INPLANE_FIX = SIG_GL * (1 - NU_GL) / (E_GL * ALPHA_GL)


# ── 패널 적층 ────────────────────────────────────────────────────────
# 두께를 값으로 적지 않는다. 콘솔의 면적질량을 밀도로 나눈다 — 그래야
# 이 적층의 면적열용량이 콘솔의 arealCp 와 **같은 값**이 된다. 두께를
# 따로 적으면 두 모델이 서로 다른 패널을 데우게 되고, 그것은 아무도
# 눈치채지 못한 채 갈라진다.
RHO = {"유리": 2500.0, "EVA": 950.0, "셀": 2330.0, "백시트": 1400.0}
KTH = {"유리": 1.00, "EVA": 0.34, "셀": 148.0, "백시트": 0.20}
T_GLASS = c("MASS_GLASS") / RHO["유리"]             # 3.2 mm


def _t(layer: str, mass: float) -> float:
    return mass / RHO[layer]


def panel_stack() -> T.Stack:
    """유리를 아래에 두고 쌓는다 — 진공 캐리어가 유리면을 잡는다.

    유리 / EVA하 / 셀 / EVA상 / 백시트. 목표 계면은 **유리와 EVA하 사이**,
    곧 유리의 뒷면이다. 절점을 층 경계에 두었으므로 보간 없이 읽는다.
    """
    return T.Stack(
        T.Layer("유리", T_GLASS, KTH["유리"], RHO["유리"],
                c("CP_GLASS") * 1000, n=10),
        T.Layer("EVA하", _t("EVA", c("MASS_EVA") / 2), KTH["EVA"],
                RHO["EVA"], c("CP_EVA") * 1000, n=3),
        T.Layer("셀", _t("셀", c("MASS_CELL")), KTH["셀"],
                RHO["셀"], c("CP_CELL") * 1000, n=2),
        T.Layer("EVA상", _t("EVA", c("MASS_EVA") / 2), KTH["EVA"],
                RHO["EVA"], c("CP_EVA") * 1000, n=3),
        T.Layer("백시트", _t("백시트", c("MASS_BACK")), KTH["백시트"],
                RHO["백시트"], c("CP_BACK") * 1000, n=3),
    )


@functools.lru_cache(maxsize=64)
def soak(flux: float, split: float = 0.5, t_end: float = 0.0):
    """양면에 흡수유속을 걸고 데운다. split 은 유리쪽 몫.

    유속을 **규정**하는 것이 이 모델의 경계조건이다. 실효 열효율 65 %
    라는 값이 이미 "램프 정격 중 패널이 실제로 먹는 몫" 이므로, 여기서
    복사·대류 손실을 다시 빼면 두 번 빼는 것이 된다.
    """
    st = panel_stack()
    end = t_end or max(40.0, 2.0 * st.areal_cp * 1000 *
                       (T_TARGET - T_AMB) / flux)
    r = T.solve(st, T.BC(q=flux * split), T.BC(q=flux * (1 - split)),
                T_AMB, min(0.25, end / 800), end, keep=900)
    i_face = st.index("EVA하", "front")
    tf = r.when(i_face, T_TARGET)
    at = r.near(tf) if tf else r.final
    return dict(stack=st, run=r, i_face=i_face, t_face=tf,
                t_back=at[st.N - 1], dt_glass=at[0] - at[i_face])


# ── ① 패널 소킹 ─────────────────────────────────────────────────────
def panel():
    s = soak(FLUX)
    st = s["stack"]
    t_lump = st.areal_cp * 1000 * (T_TARGET - T_AMB) / FLUX
    lag = s["t_face"] - t_lump
    al = KTH["유리"] / (RHO["유리"] * c("CP_GLASS") * 1000)
    fo = al * s["t_face"] / T_GLASS ** 2

    return [
        Result("T1", "계면 도달 지연 (FDM − 덩어리)", lag, "s", 0.05 * DWELL,
               "설계 체류 222.6 s 의 5 % — 이보다 작아야 덩어리 모델을 쓴다",
               f"FDM {s['t_face']:.1f} s · 덩어리 {t_lump:.1f} s. 적층 "
               f"{st.thickness*1000:.2f} mm 는 열적으로 얇다 (Fo {fo:.0f} ≫ 1). "
               f"**덩어리 모델이 옳았다** — 이 해석의 첫 몫은 그것을 확인한 것이다"),
        Result("T2", "계면 140 ℃ 시점의 백시트 표면", s["t_back"], "℃", T_BACK_MAX,
               "PVDF 백시트 융점 165 ℃ (PVF 는 195 — 낮은 쪽을 쓴다)",
               f"계면보다 {s['t_back']-T_TARGET:.1f} K 높다. 여유 "
               f"{T_BACK_MAX-s['t_back']:.0f} K 가 유속을 얼마나 올릴 수 있는지를 "
               f"정한다 (T4). 백시트는 감아서 파는 물건이라 녹으면 제품이 사라진다"),
        Result("T3", "승온 중 유리 두께방향 온도차", s["dt_glass"], "K", DT_THROUGH,
               f"σ {SIG_GL:.0f} MPa 를 내는 판두께 방향 ΔT {DT_THROUGH:.0f} K",
               f"유속 {FLUX:,.0f} W/m² · 유리 {T_GLASS*1000:.1f} mm. "
               f"두께가 얇아 기울기가 서지 않는다"),
    ], dict(t_lump=t_lump, lag=lag, fo=fo, **s)


# ── ② 체류시간 하한 — 백시트가 정한다 ────────────────────────────────
def _flux_cap(t_back_limit: float) -> tuple[float, float]:
    """백시트가 그 온도에 닿는 유속 상한과 그때의 체류시간. 이분법."""
    lo, hi = FLUX, FLUX * 40
    for _ in range(20):
        mid = round((lo + hi) / 2, 3)
        s = soak(mid)
        if s["t_face"] is None or s["t_back"] > t_back_limit:
            hi = mid
        else:
            lo = mid
    return lo, soak(round(lo, 3))["t_face"]


def dwell_floor():
    """콘솔은 `dwell = max(5Q/P유효, 113.15)` 로 하한을 걸어 두었고, 그
    113.15 는 "1D-FDM 계면 도달시간 하한" 이라고만 적혀 있었다. 푼 적이
    없는 숫자다. 여기서 실제로 푼다.
    """
    q_cap, t_cap = _flux_cap(T_BACK_MAX)          # 융점 그대로
    q_des, t_des = _flux_cap(T_BACK_DESIGN)       # 여유 10 K

    # 콘솔 입력구간의 모서리 — 최소 패널 · 최대 램프 · 최대 효율
    q_worst = (LAMPS * 3.0 * 0.80 * 1000 / DECKS) / (1.6 * 0.8)
    w = soak(round(q_worst, 3))

    return [
        Result("T4", "체류시간 하한 (백시트 설계한계)", t_des, "s", DWELL,
               "설계 체류 222.6 s — 하한이 이보다 짧아야 설계가 성립한다",
               f"백시트 {T_BACK_DESIGN:.0f} ℃ (융점 −10 K) 에서 유속 상한 "
               f"{q_des:,.0f} W/m² = 설계의 {q_des/FLUX:.1f} 배. 융점 그대로면 "
               f"{t_cap:.0f} s. 콘솔의 `fdmDwell:113.15` 는 **유도된 적 없는 "
               f"값**이었다 — 근거는 이제 이것이다"),
        Result("T5", "입력구간 모서리의 백시트 온도", w["t_back"], "℃", T_BACK_MAX,
               "PVDF 융점 165 ℃",
               f"1600×800 · 램프 3 kW · 효율 80 % — 콘솔 입력구간의 모서리. "
               f"유속 {q_worst:,.0f} W/m² 에서 계면 도달 {w['t_face']:.0f} s, "
               f"백시트 여유 {T_BACK_MAX-w['t_back']:.1f} K 뿐이다. **하한을 "
               f"{t_des:.0f} s 로 두면 이 모서리가 막힌다** — 하한은 살려 둔다"),
    ], dict(q_cap=q_cap, t_cap=t_cap, q_des=q_des, t_des=t_des,
            q_worst=q_worst, worst=w)


# ── ③ 유리 열응력 — 승온과 급냉 ─────────────────────────────────────
def _sigma(dt: float) -> float:
    return E_GL * ALPHA_GL * dt / (2 * (1 - NU_GL))


def rfq_bound(decks: int) -> tuple[float, float, float]:
    """사양서 5.5항이 쓴 보수 모델 — (유리 표면 플럭스 kW/m², ΔT, σ).

    그 모델은 이렇게 짜여 있다: IR 유효출력 중 **유리가 면적열용량에서
    차지하는 몫**만큼이 유리로 들어가고, 그 유속이 유리 두께를 **통과**
    한다고 보아 ΔT = q·t/k 를 쓴다.

    통과 모델은 이 상황에 맞지 않는다 — 유리는 열을 지나 보내는 벽이
    아니라 열을 **머금는** 판이고, 아래 뱅크에서 직접 받는 데다 위쪽
    적층에서도 받는다. 흡수하는 판이면 같은 유속에서도 기울기가 절반
    (q·t/2k) 이고, 양면에서 받으면 더 줄어든다. 그래서 이 값은 상한이다.

    그래도 지우지 않는다. 이 숫자는 이미 입찰자에게 나갔고, **상한으로서
    맞다**. 과도해석이 그 아래로 얼마나 내려가는지를 보이는 것이 여기서
    할 일이지, 발행된 숫자를 조용히 바꾸는 것이 아니다.
    """
    share = c("MASS_GLASS") * c("CP_GLASS") / c("AREAL_CP")
    q = (USEFUL_KW * share / decks) / PANEL_A          # kW/m²
    dt = q * 1000 * T_GLASS / KTH["유리"]
    return q, dt, _sigma(dt)


def glass_stress():
    heat = soak(FLUX)["dt_glass"]

    # 급냉 — 140 ℃ 유리를 25 ℃ 강제공랭에 넣는 순간이 가장 심하다
    q = glass_cool_run()
    st, r = q["stack"], q["run"]
    dt_q = r.peak(st.N // 2, 0)

    # 단수를 줄이면 같은 열량을 짧은 시간에 넣어야 한다 → 유속이 오른다
    rows = []
    for n in (3, 5, 7):
        s = soak(round((USEFUL_KW * 1000 / n) / PANEL_A, 3))
        rows.append((n, (USEFUL_KW * 1000 / n) / PANEL_A, s["t_face"],
                     s["dt_glass"], _sigma(s["dt_glass"]), s["t_back"]))

    b3, b5 = rfq_bound(3), rfq_bound(5)
    return [
        Result("T6", "승온 중 유리 열응력 (과도해석)", _sigma(heat), "MPa", SIG_GL,
               "사양서 5.5항 설계허용 7 MPa — 발행된 값을 그대로 쓴다",
               f"3단이면 {rows[0][4]:.2f} · 7단이면 {rows[2][4]:.2f} MPa. "
               f"**단수를 열응력이 정한 것이 아니다** — 3단에서도 여유가 "
               f"{SIG_GL/rows[0][4]:.0f} 배다. 사양서는 3단이 7.05 로 허용치를 "
               f"넘는다고 썼는데, 그것은 통과 모델의 상한이다 (T7)"),
        Result("T7", "사양서 5.5항 보수 모델 재현 (5단)", b5[2], "MPa", SIG_GL,
               "같은 허용 7 MPa — 사양서에 인쇄된 4.23 MPa 와 대조한다",
               f"플럭스 {b5[0]:.2f} kW/m² · ΔT {b5[1]:.1f} K → {b5[2]:.2f} MPa. "
               f"3단은 {b3[0]:.2f} kW/m² · {b3[1]:.1f} K → {b3[2]:.2f} MPa. "
               f"**사양서 숫자가 그대로 재현된다** — 두 모델이 다른 것이지 "
               f"어느 쪽이 계산을 틀린 것이 아니다. 과도해석은 이 상한의 "
               f"{_sigma(heat)/b5[2]:.0%} 다: 유리는 열을 통과시키는 벽이 아니라 "
               f"양면에서 받아 머금는 판이기 때문이다"),
        Result("T8", "급냉 중 유리 열응력 (냉각 랙 투입 순간)", _sigma(dt_q),
               "MPa", SIG_GL,
               "같은 허용응력. 급냉은 표면이 인장이라 승온보다 위험하다",
               f"140 ℃ 유리가 h {c('GCOOL_H'):.0f} W/(m²·K) 강제공랭을 만나는 "
               f"순간 중심–표면 {dt_q:.2f} K. Bi {c('GCOOL_H')*T_GLASS/2/KTH['유리']:.3f} "
               f"가 작아 충격이 서지 않는다 — 팬을 세게 돌려도 되는 근거다"),
    ], dict(rows=rows, dt_quench=dt_q, heat=heat)


# ── ④ 유리 냉각 랙 ──────────────────────────────────────────────────
@functools.lru_cache(maxsize=4)
def glass_cool_run():
    h = c("GCOOL_H")
    st = T.Stack(T.Layer("유리", T_GLASS, KTH["유리"], RHO["유리"],
                         c("CP_GLASS") * 1000, n=12))
    bc = T.BC(h=h, t_inf=T_AMB)
    r = T.solve(st, bc, bc, c("GCOOL_T_IN"), 0.25, 600.0, keep=900)
    return dict(stack=st, run=r, h=h)


def glass_cool():
    q = glass_cool_run()
    st, r, h = q["stack"], q["run"], q["h"]
    t_in, t_out = c("GCOOL_T_IN"), c("GCOOL_T_OUT")
    t_cool = r.when(st.N // 2, t_out)
    bi = h * (T_GLASS / 2) / KTH["유리"]
    lump = (RHO["유리"] * c("CP_GLASS") * 1000 * T_GLASS) / (2 * h) * \
        math.log((t_in - T_AMB) / (t_out - T_AMB))
    need = math.ceil(t_cool / TAKT)

    return [
        Result("T9", f"유리 {t_in:.0f} → {t_out:.0f} ℃ 냉각", t_cool, "s",
               DECKS * TAKT,
               f"랙 {DECKS}단 × 택트 {TAKT} s = {DECKS*TAKT:.0f} s 체류 가능",
               f"콘솔 LMTD 덩어리 해 {lump:.1f} s 와 "
               f"{abs(t_cool-lump)/lump:.1%} 차이. 필요 {need}단 < 설치 "
               f"{DECKS}단 — 여유 {DECKS-need}단. 단수는 가열실과 맞춘 것이지 "
               f"냉각이 요구한 것이 아니다"),
        Result("T10", "냉각 랙 비오 수", bi, "—", 0.10,
               "Bi < 0.1 이면 덩어리 가정이 성립한다",
               f"h {h:.0f} W/(m²·K) · 유리 {T_GLASS*1000:.1f} mm. 콘솔이 쓴 "
               f"LMTD 식이 **타당하다**. h 는 계산이 아니라 가정이므로 "
               f"파일럿에서 실측한다 (PT-06)"),
    ], dict(t_cool=t_cool, lump=lump, bi=bi, need=need)


# ── ⑤ 가열실 벽 — 4겹과 열교 ────────────────────────────────────────
WALL_IN = T.BC(h=5.0, t_inf=T_TARGET, eps=0.20, t_rad=T_TARGET)
WALL_OUT = T.BC(h=4.0, t_inf=T_AMB, eps=0.90, t_rad=T_AMB)


def wall_stack() -> T.Stack:
    """안에서 밖으로. 부품 카탈로그 P-002-12 ~ 16 그대로."""
    return T.Stack(
        T.Layer("내피", 0.0020, 16.0, 7900.0, 500.0, 1),      # STS304 2.0
        T.wool(0.100, 100.0, n=8),                            # 미네랄울 100t
        T.Layer("반사판", 0.0005, 200.0, 2700.0, 900.0, 1),   # AL 0.5
        T.air_gap(0.025, 0.05, 0.90),                         # 공기층 25
        T.Layer("외피", 0.0032, 50.0, 7850.0, 460.0, 1),      # SS400 3.2
    )


def _series_skin(r_wall: float, u_bridge: float):
    """내피–벽체–외피 직렬망. 필름이 온도를 타므로 반복해 푼다.

    처음에는 `외피온도 = 주위 + U·ΔT·R외피` 로 선형 외삽했다. 열교가
    작을 때는 맞지만 크게 넣으면 무너진다 — 금속 스페이서에서 유속
    2,053 W/m², 외피 240 ℃ 가 나왔다. 안쪽이 140 ℃ 인데 바깥이 240 ℃ 다.
    벽 저항이 0 으로 가도 필름 저항 두 장이 남는다는 것을 외삽이 못 본
    것이다. 직렬망은 그럴 수 없다.
    """
    u = 1.0 / r_wall + u_bridge
    tsi, tso = 100.0, 40.0
    for _ in range(300):
        ai, bi = WALL_IN.flux(tsi)          # q_in  = ai − bi·Tsi
        ao, bo = WALL_OUT.flux(tso)         # q_out = bo·Tso − ao
        det = (bi + u) * (u + bo) - u * u
        nsi = (ai * (u + bo) + u * ao) / det
        nso = ((bi + u) * ao + u * ai) / det
        done = abs(nsi - tsi) < 1e-10 and abs(nso - tso) < 1e-10
        tsi, tso = nsi, nso
        if done:
            break
    return tsi, tso, u * (tsi - tso)


def chamber_wall():
    st = wall_stack()
    Tf = T.steady(st, WALL_IN, WALL_OUT, t0=80.0)
    ao, bo = WALL_OUT.flux(float(Tf[-1]))
    q_field = bo * float(Tf[-1]) - ao                  # W/m²
    r_wall = (float(Tf[0]) - float(Tf[-1])) / q_field  # m²·K/W 벽 자체

    import parts as P
    A = (2 * P.CHAMBER_L * 3860 + 2 * P.RACK_W * 3860
         + P.CHAMBER_L * P.RACK_W) / 1e6               # m² 측·단·지붕

    # 열교 — GFRP 스페이서 60×60×12 @600 격자 210개 (P-002-16) 와
    # 그것을 관통하는 M6. 다리 길이는 스페이서 두께 12 mm 다: 양쪽
    # 강재는 열적으로 등온이라 저항이 스페이서에만 걸린다.
    n_sp, a_sp, l_sp = 210, 0.060 * 0.060, 0.012
    g_gfrp = 0.30 * a_sp / l_sp * n_sp                 # W/K  GFRP k 0.30
    g_bolt = 50.0 * 20e-6 / l_sp * n_sp                # M6 유효단면 20 mm²
    g_steel = 16.0 * a_sp / l_sp * n_sp                # 스페이서를 STS 로

    _, t_field, _ = _series_skin(r_wall, 0.0)
    _, t_gfrp, q_gfrp = _series_skin(r_wall, (g_gfrp + g_bolt) / A)
    _, t_nobolt, q_nobolt = _series_skin(r_wall, g_gfrp / A)
    _, t_steel, q_steel = _series_skin(r_wall, (g_steel + g_bolt) / A)

    return [
        Result("T11", "가열실 외피 표면온도", t_gfrp, "℃", 60.0,
               "EN ISO 13732-1 금속 접촉 화상 문턱 · 부품 P-002-16 주석의 60 ℃",
               f"열교 없는 필드는 {t_field:.1f} ℃. 스페이서를 STS 로 바꾸면 "
               f"{t_steel:.0f} ℃ 로 **60 ℃ 를 넘는다** — 카탈로그가 GFRP 를 "
               f"고른 이유가 확인된다. 다만 M6 관통볼트 210개가 스페이서를 "
               f"단락시켜 손실을 {q_gfrp/q_nobolt:.1f} 배로 만든다 (R4)"),
        Result("T12", "가열실 벽 손실", q_gfrp * A / 1000, "kW", 35.0,
               "정격 100 kW − 유효 65 kW = 손실 예산 35 kW",
               f"벽 {A:.1f} m² · 필드 {q_field:.1f} → 열교 포함 {q_gfrp:.1f} W/m². "
               f"손실 예산의 {q_gfrp*A/1000/35:.0%} 만 벽이다. 나머지 "
               f"{35-q_gfrp*A/1000:.1f} kW 는 배기·데크 열용량·반사손실인데 "
               f"**아직 아무도 세지 않았다** — 효율 65 % 는 가정이지 결과가 "
               f"아니다 (PT-05)"),
    ], dict(area=A, r_wall=r_wall, q_field=q_field, t_field=t_field,
            t_gfrp=t_gfrp, t_steel=t_steel, t_nobolt=t_nobolt,
            q_gfrp=q_gfrp, q_nobolt=q_nobolt, q_steel=q_steel,
            g_gfrp=g_gfrp, g_bolt=g_bolt, g_steel=g_steel)


# ── ⑥ 칼날 카세트 ───────────────────────────────────────────────────
def cassette():
    m, cp, h = c("CASS_MASS"), c("CASS_CP") * 1000, c("CASS_HCONV")
    area = 2 * (c("CASS_L") * c("CASS_W") + c("CASS_L") * c("CASS_H")
                + c("CASS_W") * c("CASS_H"))
    t_hot, t_touch = c("CASS_T_HOT"), c("CASS_T_TOUCH")

    lc = (m / 7850.0) / area                      # 등가 반두께 = V/A
    st = T.Stack(T.Layer("공구강", 2 * lc, 25.0, 7850.0, cp, n=8))
    bc = T.BC(h=h, t_inf=T_AMB)
    r = T.solve(st, bc, bc, t_hot, 1.0, 1800.0, keep=900)
    t_cool = r.when(st.N // 2, t_touch)
    bi = h * lc / 25.0
    lump = m * cp / (h * area) * math.log((t_hot - T_AMB) / (t_touch - T_AMB))

    # 정지 예산 — 가동률 90 % 는 시간당 360 초를 준다
    budget = 3600 * (1 - 0.90)
    stop = t_cool + c("CASS_SWAP_MANUAL") + c("CASS_VERIFY") + \
        m * cp * (t_hot - T_AMB) / (c("CASS_HEAT_KW") * 1000 * c("CASS_HEAT_ETA"))
    panels_needed = stop / budget * 60            # 이 정지를 흡수하려면

    return [
        Result("T13", "카세트 200 → 60 ℃ 냉각", t_cool, "s", budget,
               "가동률 90 % 가 주는 시간당 정지 예산 360 s",
               f"콘솔 LMTD 해 {lump:.0f} s 와 {abs(t_cool-lump)/lump:.1%} 차이 "
               f"(Bi {bi:.3f} ≪ 0.1 — 덩어리가 맞다). 냉각만으로 예산을 "
               f"{t_cool/budget:.1f} 배 먹는다. 수동 교환 한 번의 총 정지는 "
               f"{stop:.0f} s 이고, 이것이 가동률을 깎지 않으려면 칼날이 "
               f"**{panels_needed:.0f} 장마다 한 번보다 드물게** 바뀌어야 한다 — "
               f"칼날 수명은 아직 아무도 모른다 (PT-02)"),
    ], dict(t_cool=t_cool, lump=lump, bi=bi, area=area, lc=lc,
            stop=stop, budget=budget, panels=panels_needed)


# ── 이 해석이 만든 요구 ──────────────────────────────────────────────
def requirements() -> list[Req]:
    _, gs = glass_stress()
    _, df = dwell_floor()
    _, cw = chamber_wall()
    _, ca = cassette()
    return [
        Req("R1", "패널 면내 온도편차",
            f"≤ 18 K (백시트) · ≤ {DT_INPLANE:.0f} K (유리) — IR 뱅크 검토가 닫았다",
            "IR 뱅크 배치 검토 · 파일럿 PT-04",
            f"두께 방향은 여유가 {SIG_GL/_sigma(soak(FLUX)['dt_glass']):.0f} 배지만 "
            f"**면내 편차는 아무도 보지 않았다.** 유리는 가장자리 인장 "
            f"½·Eα·ΔT 에서 {DT_INPLANE:.0f} K 를 준다. 그런데 실제 운전은 "
            f"**냉점이 140 ℃ 에 닿을 때까지** 소킹하므로 중앙이 그만큼 넘치고, "
            f"백시트 융점 165 ℃ 가 165−140−7 = **18 K** 라는 더 좁은 창을 "
            f"준다 — 유리보다 백시트가 먼저 진다. 1 차원은 이 편차를 못 내므로 "
            f"별도 검토로 풀었다 (tools/analysis_irbank.py): 현행 배치는 "
            f"87 K 로 4 배 넘겼고, 램프 발열장을 1,300 → 2,200 으로 늘리고 "
            f"위치를 ±1,340 까지 밀어 11 K 로 내렸다. 실측은 PT-04 가 한다"),
        Req("R2", "체류시간 하한 fdmDwell",
            f"{df['t_des']:.0f} s (백시트 {T_BACK_DESIGN:.0f} ℃ 기준)",
            "콘솔 MODEL.fdmDwell · 제어 레시피",
            f"콘솔의 113.15 s 는 유도된 적 없는 값이다. 물리가 정하는 하한은 "
            f"백시트 융점이고, 여유 10 K 를 두면 {df['t_des']:.0f} s 다. "
            f"입력구간 모서리(1600×800·3 kW·80 %)가 {df['worst']['t_face']:.0f} s "
            f"이므로 하한은 실제로 일한다 — 지우면 안 된다"),
        Req("R3", "CASSETTE_HANDLING_SAFE 조건",
            f"실측 60 ℃ 이하 · 냉각 하한 {ca['t_cool']:.0f} s",
            "PLC 인터록 · 안전 검토서",
            f"시간으로만 걸면 h 가정이 틀렸을 때 뜨거운 것을 사람에게 준다. "
            f"카세트 표면 열전대를 인터록 입력으로 쓰고, 시간은 하한으로만 "
            f"둔다. 35 kg 은 인력 취급 한계를 넘으므로 지그가 먼저다"),
        Req("R4", "열교 스페이서 관통볼트",
            "M6 에 GFRP 부시 + 절연 와셔, 또는 볼트가 양 껍데기를 잇지 않을 것",
            "상세설계 · P-002-16 주석",
            f"GFRP 스페이서는 제 몫을 한다 (금속이면 외피가 "
            f"{cw['t_steel']:.0f} ℃). 그런데 그것을 관통하는 M6 210개가 "
            f"스페이서를 단락시켜 손실을 {cw['q_gfrp']/cw['q_nobolt']:.1f} 배로 "
            f"올린다 — 스페이서만 있으면 {cw['q_nobolt']*cw['area']/1000:.1f} kW "
            f"인 것이 볼트까지 세면 {cw['q_gfrp']*cw['area']/1000:.1f} kW 다. "
            f"외피 온도는 여전히 안전하므로 **손실 문제이지 안전 문제는 아니다**"),
        Req("R5", "실효 열효율 65 % 의 근거",
            "파일럿에서 전력량계 · 배기 엔탈피 · 벽 열류계로 수지를 닫을 것",
            "파일럿 PT-05",
            f"벽 손실은 {cw['q_gfrp']*cw['area']/1000:.1f} kW 로 손실 예산 35 kW "
            f"의 {cw['q_gfrp']*cw['area']/1000/35:.0%} 뿐이다. 나머지 "
            f"{35-cw['q_gfrp']*cw['area']/1000:.0f} kW 가 어디로 가는지 아무도 "
            f"세지 않았다. 65 % 가 실제로 55 % 이면 체류시간이 "
            f"{DWELL*65/55-DWELL:.0f} s 늘고 처리량이 무너진다"),
        Req("R6", "대류계수 h 실측",
            "유리 랙 25 · 카세트 60 W/(m²·K) 를 실측으로 확정",
            "파일럿 PT-06 · FAT",
            "두 개 다 가정이다. 냉각 랙 단수와 카세트 인터록 시간이 이 "
            "숫자에 달려 있다 — 랙은 여유가 2단 있어 견디지만, 카세트는 "
            "여유가 없다"),
    ]


# ── 종합 ─────────────────────────────────────────────────────────────
def run():
    rs, extra = [], {}
    for fn in (panel, dwell_floor, glass_stress, glass_cool,
               chamber_wall, cassette):
        r, e = fn()
        rs += r
        extra[fn.__name__] = e
    return rs, extra


def report() -> str:
    L = []
    add = L.append
    add("=" * 78)
    add("DG-HK60C 열해석 — tools/therm.py (1차원 과도 유한차분)")
    add("=" * 78)
    add("")
    add("── 해석기 검증 ─────────────────────────────────────────")
    for name, got, want, err in T.validate():
        add(f"   {name:26s} 오차 {err:6.2%}  {'OK' if err < 0.02 else '★'}")
    add("")
    st = panel_stack()
    add("── 패널 적층 (콘솔 면적질량 ÷ 밀도) ────────────────────")
    x = 0.0
    for ly in st.layers:
        add(f"   {ly.name:6s} {ly.t*1000:6.3f} mm  k {ly.kk(80):7.2f}  "
            f"ρcp {ly.rcp/1000:7.1f} kJ/(m³·K)  경계 {x*1000:6.3f} mm")
        x += ly.t
    add(f"   합계   {st.thickness*1000:6.3f} mm  면적열용량 "
        f"{st.areal_cp:.4f} kJ/(m²·K)   (콘솔 AREAL_CP {c('AREAL_CP'):.4f})")
    add("")
    add("── 검토 ────────────────────────────────────────────────")
    add(f"   {'ID':4s} {'항목':34s} {'값':>10s} {'한계':>10s} {'이용률':>7s}  판정")
    rs, _ = run()
    bad = 0
    for r in rs:
        add(f"   {r.id:4s} {r.what[:34]:34s} {r.value:10.3f} {r.limit:10.3f} "
            f"{r.util:6.0%}  {'OK' if r.ok else '★ 초과'}")
        bad += 0 if r.ok else 1
    add("")
    add("── 근거 ────────────────────────────────────────────────")
    for r in rs:
        add(f"   {r.id}  {r.basis}")
        add(f"       {r.note}")
    add("")
    add("── 이 해석이 만든 요구 ─────────────────────────────────")
    for q in requirements():
        add(f"   {q.id}  {q.what} — {q.value}")
        add(f"       받는 곳: {q.owner}")
        add(f"       {q.why}")
    add("")
    add("=" * 78)
    add("검토 전 항목 만족" if not bad else f"★ {bad} 항목 초과")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
