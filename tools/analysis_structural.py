"""구조해석 — 이 설비가 실제로 견디는가, 그리고 얼마나 움직이는가.

제작 지침서는 **강도**를 봤다 (볼트가 끊어지는가, 용접이 터지는가).
이용률이 전부 0.2 미만이라는 결론이 나왔고, 그것은 이 설비를 강도가
정하지 않는다는 뜻이다. **그러면 무엇이 정하는가** — 그 답이 여기 있다.

다섯 가지를 푼다:

  ① KG-101 갠트리   설계 박리 추력(fab_spec F_PEEL_D)에서 칼끝이 얼마나 밀리는가.
                    칼날 깊이 예산 0.15 가 이 경로의 강성에 달려 있다.
  ② 갠트리 고유진동  1차 모드가 칼날 가감속과 겹치면 채터가 난다.
  ③ HC-101 가열실   자중 + 지진에서 기둥이 좌굴하는가, 베이스가 뜨는가.
  ④ VT-101 상판     진공 −65 kPa 의 면외 압력에서 리브 사이가 얼마나 처지는가.
  ⑤ 계단 칼날       한 자루 칼날의 일곱 칼끝이 하중에서 한 줄로 남는가 — Z축 두
                    조를 어디에 두느냐가 답을 정한다 (베셀점).

해석기는 tools/fea.py — 닫힌해 다섯 건으로 검증했다 (정적 오차 0.00 %,
1차 진동수 0.46 %).

**이 해석이 못 보는 것**: 용접부 국부응력, 볼트 접촉, 판의 국부좌굴,
3차원 응력집중, 잔류응력. 그것은 상세설계에서 상용 FEA 로 확인한다.
여기서 답하는 것은 **전체 거동**이다.
"""

from __future__ import annotations

import math
import pathlib
import sys
from typing import NamedTuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import fab_spec as F  # noqa: E402
import fea  # noqa: E402
import knife_stepped as KS  # noqa: E402
from console_consts import const as c  # noqa: E402


class Result(NamedTuple):
    id: str
    what: str
    value: float
    unit: str
    limit: float
    basis: str          # 한계의 근거
    note: str

    @property
    def util(self) -> float:
        return self.value / self.limit if self.limit else 0.0

    @property
    def ok(self) -> bool:
        return self.util <= 1.0


M = lambda n: c(n) * 1000.0        # m → mm

# 칼날 캐리어 빔 BOX-160×120×8 (parts P-005-14). fea.boxsec(h, b) 의 h 는 y 방향
# 부재에서 전역 x 로 선다 — 약한 120 을 추력 방향에, 160 을 연직에 둔다.
CARRIER = fea.boxsec(120, 160, 8)


# ── ① KG-101 갠트리 — 칼끝 처짐 ────────────────────────────────────────
def _blade_loads():
    """계단 칼날 일곱 조각의 (y, 설계 추력 N) — 패널 안에 든 폭의 가운데에 건다.

    박리 저항은 폭당 힘이므로 조각 몫은 패널 안 폭에 비례한다
    (knife_stepped.segments). 합은 설계 추력 F_PEEL_D 다.
    """
    out = []
    for s in KS.segments():
        lo, hi = max(-KS.PANEL_HALF, s["y0n"]), min(KS.PANEL_HALF, s["y1n"])
        if hi > lo:
            out.append(((lo + hi) / 2, s["R_design"] * 1000))
    return sorted(out)


def gantry():
    """주행 문형 4기둥 + 주행레일 빔 2본 + 갠트리 프레임 + 크로스빔
    + Z축 서보슬라이드 좌·우 2조 + 칼날 캐리어 빔.

    박리 추력은 일곱 칼날 조각에서 x 방향으로 들어와 캐리어 빔 → Z축 좌·우 →
    크로스빔 → 측면 프레임 → 주행대차 → 레일 빔 → 기둥 → 기초로 내려간다.
    칼끝이 밀리는 양은 이 경로 전체의 강성이 정한다 — 크로스빔만 봐서는 답이
    안 나온다.

    모델: 기둥 4 (H-250×250×9/14, 바닥 고정) · 레일 빔 2 (□-220×220×9) ·
    크로스빔 1 (□-300×200×12) · 측면 프레임은 강체에 가까운 상자(PL 16t 용접
    조립) · Z축 2조 (y = ±CZS_Y, 베셀점) · 캐리어 빔 BOX-160×120×8 (약한 120 을
    추력 방향으로 — 보수). 추력은 조각 몫을 각 조각 가운데에 건다.
    """
    x0, x1 = M("CRAIL_X0"), M("CRAIL_X1")
    zr = M("CRAIL_Z")                     # 레일 높이 EL 1,950
    y = 1420.0                            # 문형 반폭
    zc = 1150.0                           # 칼끝 높이 (테이블 상면 EL)
    cx = (x0 + x1) / 2                    # 갠트리가 행정 중앙에 있을 때 — 최악
    zs = M("CZS_Y")                       # Z축 좌·우 y ±390

    col = fea.hsec(250, 250, 9, 14)
    rail = fea.boxsec(220, 220, 9)
    cross = fea.boxsec(300, 200, 12)
    side = fea.boxsec(700, 400, 16)       # 측면 프레임 (PL 16t 용접 상자)

    f = fea.Frame()
    # 기둥 4본 — 바닥과 레일 높이
    base, top = {}, {}
    for xx in (x0, x1):
        for yy in (-y, y):
            base[(xx, yy)] = f.node(xx, yy, 0)
            top[(xx, yy)] = f.node(xx, yy, zr)
            f.beam(base[(xx, yy)], top[(xx, yy)], col)
            f.support(base[(xx, yy)])
    # 레일 빔 2본 — 갠트리 위치에 절점을 하나 넣는다
    mid = {}
    for yy in (-y, y):
        mid[yy] = f.node(cx, yy, zr)
        f.beam(top[(x0, yy)], mid[yy], rail)
        f.beam(mid[yy], top[(x1, yy)], rail)
    # 갠트리 — 측면 프레임 2 + 크로스빔 (Z축 두 조가 붙는 자리에 절점)
    zb = zr + 350.0                       # 크로스빔 중심
    cb = {}
    for yy in (-y, y):
        cb[yy] = f.node(cx, yy, zb)
        f.beam(mid[yy], cb[yy], side)
    for yy in (-zs, 0.0, zs):
        cb[yy] = f.node(cx, yy, zb)
    ys_cb = sorted(cb)
    for a, b in zip(ys_cb, ys_cb[1:]):
        f.beam(cb[a], cb[b], cross)
    # 칼날 캐리어 빔 — Z축 좌·우 아래, 칼끝 높이. 조각 가운데마다 절점
    loads = _blade_loads()
    ys_k = sorted({yy for yy, _ in loads} | {-zs, zs})
    kn = {yy: f.node(cx, yy, zc) for yy in ys_k}
    for a, b in zip(ys_k, ys_k[1:]):
        f.beam(kn[a], kn[b], CARRIER)
    # Z축 서보슬라이드 좌·우 — 크로스빔에서 캐리어 빔까지 내려온다
    zslide = fea.boxsec(400, 300, 20)
    for yy in (-zs, zs):
        f.beam(cb[yy], kn[yy], zslide)

    # 하중: 박리 추력 (설계값) 을 조각마다 x 방향으로
    for yy, p in loads:
        f.force(kn[yy], fx=p)
    u = f.solve()
    tips = [kn[yy] for yy, _ in loads]
    dx = max(abs(u[t][0]) for t in tips)
    dz = max(abs(u[t][2]) for t in tips)

    # 고유진동 — 갠트리 이동부 질량을 크로스빔 가운데와 Z축 두 조 아래에 얹는다
    fr = f.modes(extra_mass={cb[0.0]: F.M_GANTRY * 0.6,
                             kn[-zs]: F.M_GANTRY * 0.2, kn[zs]: F.M_GANTRY * 0.2}, n=3)

    # 두 방향은 성격이 전혀 다르다.
    #
    #   x (추력 방향)  — 추력이 일정한 동안은 **일정한 오프셋**이다. 서보가
    #     모터측 엔코더로 위치를 잡으므로 공구는 그만큼 뒤처지지만, 박리
    #     자체는 상대운동이라 위치가 밀려도 떼는 일은 그대로 된다.
    #     문제가 되는 것은 물림·해제의 과도구간뿐이므로 한계를 느슨하게
    #     (행정의 0.2 % = 7 mm) 잡는다.
    #   z (칼날 깊이) — 이것이 진짜다. 칼날은 EVA 계면에 있어야 하고
    #     EVA 층은 0.45 mm 다. 깊이가 흔들리면 유리를 긁거나 셀을 남긴다.
    #     **총괄 결정 — 한계 0.15 mm (EVA 두께의 1/3).**
    return [
        Result("S1", f"갠트리 칼끝 깊이 변화 (추력 {F.F_PEEL_D:.2f} kN)", dz, "mm", 0.15,
               "EVA 층 0.45 mm 의 1/3 — 깊이가 흔들리면 유리를 긁거나 셀을 남긴다",
               f"일곱 칼끝 중 최대 z {dz:.3f} · 행정 중앙 · 기둥 H-250×250 4본 · Z축 2조 y ±{zs:.0f}"),
        Result("S2", "갠트리 칼끝 추력방향 처짐", dx, "mm", 7.0,
               "행정 3,500 의 0.2 % — 일정 오프셋이라 서보가 흡수한다",
               "물림·해제 과도구간에서만 문제가 된다 — 계단 칼날은 그 과도를 네 번에 나눈다"),
        Result("S3", "갠트리 1차 고유진동수 (역수 기준)", 6.0 / max(fr[0], 1e-9),
               "—", 1.0,
               "fn ≥ 6 Hz — 칼날 가감속 기본주파수의 3배 이상",
               f"fn = {fr[0]:.1f} Hz · 2차 {fr[1]:.1f} · 3차 {fr[2]:.1f}"),
    ], dict(dx=dx, dz=dz, fn=fr, knife=tips, span=(x1 - x0))


# ── ② HC-101 가열실 — 기둥 좌굴과 베이스 인장 ──────────────────────────
def chamber():
    """6기둥 랙. 자중 + 지진 수평 0.30W 에서 기둥이 견디는가.

    데크는 단마다 패널 5장(각 28.2 kg)을 받는다. 지진은 무게중심에
    수평으로 걸고, 그 전도모멘트를 기둥 축력으로 본다.
    """
    L = M("DECK_L") + 2 * M("CL_WALL") + M("CL_DOOR")     # 3,780
    W = M("RACK_W")                                        # 2,560
    H = c("CDECK_Z0") * 1000 + c("CDECK_DZ") * 1000 * (c("DECKS") - 0.5) + 860
    col = fea.hsec(200, 200, 8, 12)
    tie = fea.boxsec(150, 100, 6)
    ang = fea.ANG if hasattr(fea, "ANG") else None        # 데크는 강성에 안 넣는다

    f = fea.Frame()
    xs = (0.0, L / 2, L)
    ys = (-W / 2 + 200, W / 2 - 200)
    base, top = {}, {}
    for xx in xs:
        for yy in ys:
            base[(xx, yy)] = f.node(xx, yy, 0)
            top[(xx, yy)] = f.node(xx, yy, H)
            f.beam(base[(xx, yy)], top[(xx, yy)], col)
            f.support(base[(xx, yy)])
    for yy in ys:                                          # 종방향 타이빔
        f.beam(top[(xs[0], yy)], top[(xs[1], yy)], tie)
        f.beam(top[(xs[1], yy)], top[(xs[2], yy)], tie)
    for xx in xs:                                          # 횡방향 타이빔
        f.beam(top[(xx, ys[0])], top[(xx, ys[1])], tie)

    W_tot = F.kn(F.M_CHAMBER) * 1000                       # N
    seis = F.SEISMIC * W_tot
    for k in top:
        f.force(top[k], fz=-W_tot / 6, fx=seis / 6)
    u = f.solve()
    drift = max(abs(u[n][0]) for n in top.values())

    mf = f.member_forces()
    axial = max(abs(m[0]) for m in mf[:6])                 # 기둥 축력 N
    Pcr = fea.euler_buckling(col, H, k=0.7)                # 하단고정·상단핀
    lam = fea.slenderness(col, H, k=0.7)

    return [
        Result("S4", "가열실 기둥 최대 축력 / 오일러 좌굴하중",
               axial / 1000, "kN", Pcr / 1000,
               "탄성 좌굴하중 (유효길이계수 0.7)",
               f"λ = {lam:.0f} · 한계 120 · 기둥 H-200×200 6본"),
        Result("S5", "가열실 지진 층간변위 (0.30W)", drift, "mm", H / 200,
               "H/200 — 외피 이음과 셔터 궤도가 견디는 한계",
               f"H = {H:,.0f} mm · 자중 {F.M_CHAMBER/1000:.2f} t"),
        Result("S6", "가열실 기둥 세장비", lam, "—", 120.0,
               "KDS 압축재 세장비 상한 120",
               "좌굴이 강도보다 먼저 온다 — 그래서 단면이 이 크기다"),
    ], dict(H=H, axial=axial, Pcr=Pcr, drift=drift)


# ── ③ VT-101 상판 — 진공은 외력이 아니다 ─────────────────────────────
def table():
    """상판 PL 20 + 리브 PL 10 @400, 기둥 □-150×150×6 4본.

    **이 절은 두 번 틀린 뒤에 나왔다.** 기록해 둔다 — 같은 착각이 흔하다.

      1차: −65 kPa 를 상판 전면에 등분포로 걸었다. 294 kN 이 나왔다.
      2차: 패드 18점의 하향 집중하중으로 바꿨다. 57 kN 이 나왔다.
      정답: **둘 다 아니다.** 진공은 패드와 패널 사이에 있다. 제어체적으로
            세어 보면 상판이 받는 상향 압력차(57.4 kN)와 패드 립 반력의
            하향 성분이 상쇄되고, 남는 것은 **패널 자중 0.28 kN** 뿐이다.
            진공은 패널과 상판을 서로 당기는 **내력 쌍**이다.

    그래서 상판의 실제 지배하중은 진공이 아니라 **박리 추력**이다. 패드가
    패널을 잡고 있으므로 설계 추력 F_PEEL_D 가 상판을 수평으로 밀고, 그것이 기둥으로
    내려간다. 상판이 밀리면 박리선이 그만큼 움직인다 — 갠트리 처짐과
    **같은 방향으로 더해지는지 반대인지**가 이 해석의 요점이다.
    """
    Lx, Wy = M("CARRIER_L"), M("CARRIER_W")
    zt = M("CZ")                                    # 상판 상면 EL 1,150
    col = fea.boxsec(150, 150, 6)
    # 상판 + 리브를 유효 T 단면 격자로
    tw, hw, bf, tf = 10.0, 120.0, 400.0, 20.0
    A = tw * hw + bf * tf
    yb = (tw * hw * hw / 2 + bf * tf * (hw + tf / 2)) / A
    I = (tw * hw ** 3 / 12 + tw * hw * (yb - hw / 2) ** 2
         + bf * tf ** 3 / 12 + bf * tf * (hw + tf / 2 - yb) ** 2)
    top = fea.Sec(A, I / 4, I, (bf * tf ** 3 + hw * tw ** 3) / 3)

    f = fea.Frame()
    xs, ys = (0.0, Lx / 2, Lx), (-Wy / 2 + 180, 0.0, Wy / 2 - 180)
    # 기둥은 6본이다 — 4본에서 자중 처짐 0.378 이 나와 칼날 깊이 예산을 넘었다
    g = {(x, y): f.node(x, y, zt) for x in xs for y in ys}
    for y in ys:
        for i in range(len(xs) - 1):
            f.beam(g[(xs[i], y)], g[(xs[i + 1], y)], top)
    for x in xs:
        for i in range(len(ys) - 1):
            f.beam(g[(x, ys[i])], g[(x, ys[i + 1])], top)
    for x in xs:                                    # 기둥 6본 (0 · 중앙 · 끝)
        for y in (ys[0], ys[-1]):
            b = f.node(x, y, 0.0)
            f.beam(b, g[(x, y)], col)
            f.support(b)

    # 하중 ① 박리 추력 — 패드가 패널을 잡고 있으므로 상판이 수평으로 밀린다
    P = F.F_PEEL_D * 1000
    for k in g:
        f.force(g[k], fx=P / len(g))
    # 하중 ② 자중 (상판·리브·패널). 패널 질량은 콘솔 면적질량에서 나온다 —
    # 28.2 로 적어 두었더니 그것이 어디서 온 값인지 아무도 모르게 됐다.
    m_panel = c("MASS_AREAL") * c("PANEL_L") * c("PANEL_W")      # 28.21 kg
    Wd = (F.M_TABLE * 0.5 + m_panel) * 9.80665
    for k in g:
        f.force(g[k], fz=-Wd / len(g))
    u = f.solve()
    dx = max(abs(u[n][0]) for n in g.values())
    dz = max(abs(u[n][2]) for n in g.values())

    # 국부 — 패드 하나 주변의 판 휨. 압력차가 작용하는 자국과 립 반력이
    # 걸리는 원이 어긋나 생기는 국부 굽힘이다. 작지만 0 은 아니다.
    Fpad = 65e-3 * math.pi / 4 * (2 * M("PAD_R")) ** 2
    dloc = fea.plate_deflection(400.0, 400.0, 20.0, Fpad / (400.0 * 400.0))

    return [
        Result("S7", f"상판 수평 변위 (박리 추력 {F.F_PEEL_D:.2f} kN)", dx, "mm", 2.0,
               "갠트리 처짐과 합해 추력 경로 강성을 정한다 — 합계로 루프 고유진동수를 본다",
               f"기둥 □-150×150×6 6본 · 상판 T단면 I={I/1e6:.1f}×10⁶ mm⁴"),
        Result("S8", "상판 연직 처짐 (자중)", dz, "mm", 0.15,
               "칼날 깊이 예산 0.15 — 진공에 붙은 패널이 상판을 따라 처진다",
               f"자중 {Wd/1000:.2f} kN (그중 패널 {m_panel*9.80665/1000:.2f} kN) · "
               f"진공은 내력이라 외력이 아니다 · 기둥 6본"),
        Result("S9", "패드 주변 판 국부 처짐", dloc, "mm", 0.10,
               "전체 평면도의 절반 — 패드 자국과 립 원의 어긋남에서 온다",
               f"패드당 {Fpad/1000:.2f} kN · 판 t20 · 리브 격자 400×400"),
    ], dict(dx=dx, dz=dz, dloc=dloc, I=I, Wd=Wd,
            w_panel=m_panel * 9.80665 / 1000)


# ── ④ 계단 칼날 캐리어 빔 — 일곱 칼끝이 한 줄로 남는가 ─────────────────
# 칼날은 한 자루이고 Z축 두 조가 그 캐리어 빔을 든다. 캐리어 빔은 Z축 좌·우의
# 스프링 컴플라이언스·로드셀 위에 얹혀 있어 모멘트를 전하지 않는다 — 그래서
# 두 점 **단순지지**로 푼다 (LM 블록의 모멘트 강성을 믿지 않는 보수).
TIP_GRIND = 0.05     # mm 일곱 칼끝 연삭·착좌 공차 ± (지침서 12항 · MC-401 한 평면 연삭)
LEVEL_TOL = 0.05     # mm KNIFE_LEVEL_OK — Z축 좌·우 높이차 한계
V_RATIO = 1.0        # 칼날 수직 반력 / 추력 — 실측 전 포락 (파일럿 PT-10 이 대체)


def _carrier(zs, fz_ratio=0.0, fx_ratio=0.0):
    """캐리어 빔만 떼어 두 Z축 위 단순지지로 푼다 → 조각 가운데의 (dx, dz)."""
    loads = _blade_loads()
    f = fea.Frame()
    ys = sorted({yy for yy, _ in loads} | {-zs, zs})
    n = {yy: f.node(0.0, yy, 0.0) for yy in ys}
    for a, b in zip(ys, ys[1:]):
        f.beam(n[a], n[b], CARRIER)
    f.support(n[-zs], ux=True, uy=True, uz=True, rx=False, ry=True, rz=False)
    f.support(n[zs], ux=True, uy=False, uz=True, rx=False, ry=False, rz=False)
    for yy, p in loads:
        f.force(n[yy], fx=p * fx_ratio, fz=-p * fz_ratio)
    u = f.solve()
    return [u[n[yy]][0] for yy, _ in loads], [u[n[yy]][2] for yy, _ in loads]


def knife():
    """계단 칼날 SHK-101 — 한 자루 칼날의 칼끝 줄이 하중에서 곧게 남는가.

    일곱 칼끝은 카세트째 한 평면으로 연삭한다(±0.05). 하중이 걸리면 그 평면이
    셋에서 흐트러진다 — 연삭 공차, Z축 좌·우 높이차에서 오는 기울기, 캐리어 빔의
    휨. 셋이 한 칼끝에 겹쳐도 칼날 깊이 예산(S1 과 같은 0.15)에 들어야 한다.

    휨은 **어디서 드느냐**가 정한다. 수직 반력은 패널 폭에 고르게 걸리므로
    양끝(±570)에서 들면 가운데가 처진다. 폭의 베셀점(0.2203 안쪽)에서 들면 두
    지점 사이의 처짐과 바깥 캔틸레버의 처짐이 같아져 칼끝 줄이 곧다. 대신
    지점이 가까울수록 좌·우 높이차가 바깥 칼끝에서 커진다 — 그 몫까지 더해서 본다.

    수직 반력의 크기는 아직 모른다 (OI-01 은 추력만 쟀다). 추력과 같게 포락하고,
    예산을 다 쓰는 수직 반력비를 거꾸로 풀어 파일럿의 합격선으로 넘긴다.
    """
    zs = M("CZS_Y")
    ends = M("KNIFE_W") / 2 - 180.0                   # 양끝 지지 (종전안 ±570)
    edge = KS.PANEL_HALF                               # 가장 바깥 물린 칼끝 700

    def budget(z_sup, vr):
        _, dz = _carrier(z_sup, fz_ratio=vr)
        bend = max(dz) - min(dz)
        tilt = LEVEL_TOL * edge / (2 * z_sup)
        return TIP_GRIND + tilt + bend, bend, tilt

    total, bend, tilt = budget(zs, V_RATIO)
    total_ends, bend_ends, _ = budget(ends, V_RATIO)
    per_vr = budget(zs, 1.0)[1]                        # 휨은 반력에 비례
    vr_max = (0.15 - TIP_GRIND - tilt) / per_vr

    dx, _ = _carrier(zs, fx_ratio=1.0)
    step = max(dx) - min(dx)
    rise = M("KNIFE_RISE")

    return [
        Result("S10", "일곱 칼끝 깊이 예산 (연삭 + 좌우 기울기 + 캐리어 휨)", total, "mm", 0.15,
               "S1 과 같은 예산 — EVA 0.45 의 1/3. 한 칼끝에 셋이 겹친다",
               f"연삭 ±{TIP_GRIND:.2f} + 기울기 {tilt:.3f} (좌우차 {LEVEL_TOL:.2f} × {edge:.0f}/{2*zs:.0f}) "
               f"+ 휨 {bend:.3f} (수직 반력 = 추력 × {V_RATIO:.1f} 포락 · 단순지지 y ±{zs:.0f}) · "
               f"양끝 ±{ends:.0f} 에서 들면 휨 {bend_ends:.3f} 로 합 {total_ends:.3f} · "
               f"예산을 다 쓰는 수직 반력비 {vr_max:.1f}"),
        Result("S11", "계단 변화 — 조각 사이 추력방향 처짐 차", step, "mm", 0.5,
               f"계단 공차 {rise:.0f} ± 0.5 — 휨이 계단을 바꾸면 물림 순서가 흐트러진다",
               f"설계 추력 {F.F_PEEL_D:.2f} kN · 캐리어 빔 BOX-160×120×8 · 약한 120 을 추력 방향으로 · "
               f"단순지지 y ±{zs:.0f}"),
    ], dict(total=total, bend=bend, tilt=tilt, total_ends=total_ends, bend_ends=bend_ends,
            vr_max=vr_max, step=step, zs=zs, ends=ends)


def run():
    rs, extra = [], {}
    for fn in (gantry, chamber, table, knife):
        r, e = fn()
        rs += r
        extra[fn.__name__] = e
    return rs, extra


def report() -> str:
    L, add = [], None
    L = []
    add = L.append
    add("=" * 78)
    add("DG-HK60C 구조해석 — tools/fea.py (직접강성법)")
    add("=" * 78)
    add("")
    add("── 해석기 검증 ─────────────────────────────────────────")
    for name, got, want, err in fea.validate():
        add(f"   {name:24s} 오차 {err:6.2%}  {'OK' if err < 0.03 else '★'}")
    add("")
    add("── 결과 ────────────────────────────────────────────────")
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
    add("=" * 78)
    add("전 항목 만족" if not bad else f"★ {bad} 항목 초과 — 단면을 다시 잡는다")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
