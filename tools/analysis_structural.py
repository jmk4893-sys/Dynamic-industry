"""구조해석 — 이 설비가 실제로 견디는가, 그리고 얼마나 움직이는가.

제작 지침서는 **강도**를 봤다 (볼트가 끊어지는가, 용접이 터지는가).
이용률이 전부 0.1 미만이라는 결론이 나왔고, 그것은 이 설비를 강도가
정하지 않는다는 뜻이다. **그러면 무엇이 정하는가** — 그 답이 여기 있다.

네 가지를 푼다:

  ① KG-101 갠트리   박리 추력 26.07 kN 에서 칼끝이 얼마나 밀리는가.
                    칼끝 간격 300±2 가 이 값 하나에 달려 있다.
  ② 갠트리 고유진동  1차 모드가 칼날 가감속과 겹치면 채터가 난다.
  ③ HC-101 가열실   자중 + 지진에서 기둥이 좌굴하는가, 베이스가 뜨는가.
  ④ VT-101 상판     진공 −65 kPa 의 면외 압력에서 리브 사이가 얼마나 처지는가.

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


# ── ① KG-101 갠트리 — 칼끝 처짐 ────────────────────────────────────────
def gantry():
    """주행 문형 4기둥 + 주행레일 빔 2본 + 갠트리 프레임 + 크로스빔.

    박리 추력은 칼날에서 x 방향으로 들어와 크로스빔 → 측면 프레임 →
    주행대차 → 레일 빔 → 기둥 → 기초로 내려간다. 칼끝이 밀리는 양은
    이 경로 전체의 강성이 정한다 — 크로스빔만 봐서는 답이 안 나온다.

    모델: 기둥 4 (H-250×250×9/14, 바닥 고정) · 레일 빔 2 (□-220×220×9) ·
    크로스빔 1 (□-300×200×12) · 측면 프레임은 강체 연결로 본다(PL 16t
    용접 조립이라 빔보다 훨씬 뻣뻣하다).
    """
    x0, x1 = M("CRAIL_X0"), M("CRAIL_X1")
    zr = M("CRAIL_Z")                     # 레일 높이 EL 1,950
    y = 1420.0                            # 문형 반폭
    zc = 1150.0                           # 칼끝 높이 (테이블 상면 EL)
    cx = (x0 + x1) / 2                    # 갠트리가 행정 중앙에 있을 때 — 최악

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
    # 갠트리 — 측면 프레임 2 + 크로스빔 1
    cb = {}
    zb = zr + 350.0                       # 크로스빔 중심
    for yy in (-y, y):
        cb[yy] = f.node(cx, yy, zb)
        f.beam(mid[yy], cb[yy], side)
    knife_up = f.node(cx, 0, zb)
    f.beam(cb[-y], knife_up, cross)
    f.beam(knife_up, cb[y], cross)
    # 칼날 Z축 슬라이드 — 크로스빔에서 칼끝까지 내려온다
    zslide = fea.boxsec(400, 300, 20)
    tip = f.node(cx, 0, zc)
    f.beam(knife_up, tip, zslide)

    # 하중: 박리 추력 (설계값) 을 칼끝에 x 방향으로
    P = F.F_PEEL_D * 1000                 # kN → N
    f.force(tip, fx=P)
    u = f.solve()
    dx, dz = abs(u[tip][0]), abs(u[tip][2])

    # 고유진동 — 갠트리 이동부 질량을 크로스빔·칼끝에 얹는다
    fr = f.modes(extra_mass={knife_up: F.M_GANTRY * 0.6,
                             tip: F.M_GANTRY * 0.4}, n=3)

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
        Result("S1", "갠트리 칼끝 깊이 변화 (추력 26.07 kN)", dz, "mm", 0.15,
               "EVA 층 0.45 mm 의 1/3 — 깊이가 흔들리면 유리를 긁거나 셀을 남긴다",
               f"z 처짐 {dz:.3f} · 행정 중앙 · 기둥 H-250×250 4본"),
        Result("S2", "갠트리 칼끝 추력방향 처짐", dx, "mm", 7.0,
               "행정 3,500 의 0.2 % — 일정 오프셋이라 서보가 흡수한다",
               "물림·해제 과도구간에서만 문제가 된다"),
        Result("S3", "갠트리 1차 고유진동수 (역수 기준)", 6.0 / max(fr[0], 1e-9),
               "—", 1.0,
               "fn ≥ 6 Hz — 칼날 가감속 기본주파수의 3배 이상",
               f"fn = {fr[0]:.1f} Hz · 2차 {fr[1]:.1f} · 3차 {fr[2]:.1f}"),
    ], dict(dx=dx, dz=dz, fn=fr, knife=tip, span=(x1 - x0))


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
    패널을 잡고 있으므로 26.07 kN 이 상판을 수평으로 밀고, 그것이 기둥으로
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
        Result("S7", "상판 수평 변위 (박리 추력 26.07 kN)", dx, "mm", 2.0,
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


# ── ④ WR-101 권취축 — 클램프 위치가 답을 정한다 ──────────────────────
def shaft():
    """권취축 Ø60 + 코어 Ø300×8t. 만권 롤 3.50 kN.

    코어의 단면2차모멘트는 축의 **123 배**다. 그래서 답은 하중이 아니라
    **분할클램프를 어디에 두는가**가 정한다.

      클램프가 가운데 모여 있으면 → 코어가 일을 못 하고 축이 면폭을 건넌다
      클램프가 양단 가까이 있으면 → 코어가 면폭을 건너고 축은 짧게만 휜다

    두 경우를 다 풀어 보고, 되는 쪽을 **요구사항으로 확정한다**.
    도면이 클램프 위치를 안 정하면 제작사가 편한 데 붙이고, 그러면 이
    설계는 운에 맡겨진다.
    """
    d, span, face = 60.0, M("ROLL_FACE") + 300, M("ROLL_FACE")
    sh, core = fea.circsec(d), fea.Sec(
        math.pi / 4 * (300 ** 2 - 284 ** 2),
        math.pi * (300 ** 4 - 284 ** 4) / 64,
        math.pi * (300 ** 4 - 284 ** 4) / 64,
        math.pi * (300 ** 4 - 284 ** 4) / 32)
    Wr = 3.499e3

    def solve(clamp_span):
        """clamp_span: 양 끝 클램프 사이 거리. 그 밖은 축만 있다."""
        f = fea.Frame()
        n = 24
        ns = [f.node(span * i / n, 0, 0) for i in range(n + 1)]
        c0, c1 = (span - clamp_span) / 2, (span + clamp_span) / 2
        for i in range(n):
            xm = span * (i + 0.5) / n
            f.beam(ns[i], ns[i + 1], core if c0 <= xm <= c1 else sh)
        f.support(ns[0], ux=True, uy=True, uz=True, rx=True, ry=False, rz=False)
        f.support(ns[-1], ux=False, uy=True, uz=True, rx=True, ry=False, rz=False)
        x0, x1 = (span - face) / 2, (span + face) / 2
        ins = [i for i in range(n + 1) if x0 <= span * i / n <= x1]
        for i in ins:
            f.force(ns[i], fz=-Wr / len(ins))
        u = f.solve()
        return max(abs(u[nd][2]) for nd in ns), f

    d_bare, _ = solve(0.0)                    # 코어가 일을 안 할 때 (보수)
    d_wide, fw = solve(face - 100)            # 클램프를 면폭 끝에 둘 때
    mf = fw.member_forces()
    sigma = max(abs(m[10]) for m in mf) / (math.pi * d ** 3 / 32)

    return [
        Result("S10", "권취축 처짐 — 클램프 양단 배치", d_wide, "mm", span / 1000,
               "스팬/1,000 — 베어링 정렬과 권취 균일도",
               f"클램프 간격 {face-100:,.0f} · 코어 Ø300×8t 가 면폭을 건넌다"),
        Result("S11", "권취축 처짐 — 클램프 중앙 집중 (되는가 확인)",
               d_bare, "mm", span / 1000,
               "같은 한계. 이 경우가 넘으면 **클램프 위치를 도면에 못 박아야 한다**",
               f"코어가 일을 못 하고 축 Ø{d:.0f} 이 스팬 {span:,.0f} 을 홀로 건넌다"),
        Result("S12", "권취축 휨응력", sigma, "MPa", F.f_allow("SM45C"),
               "SM45C 설계강도",
               "피로는 지침서가 따로 본다 (이용률 0.69 · Ø55 → Ø60 결정 근거)"),
    ], dict(d_bare=d_bare, d_wide=d_wide, sigma=sigma)


def run():
    rs, extra = [], {}
    for fn in (gantry, chamber, table, shaft):
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
