# -*- coding: utf-8 -*-
"""평면 강체 동역학 — 물체가 **돌 수 있게** 두고 감는 엔진.

`dynamics.py` 는 시간을 감지만 자유도가 하나다. 그래서 답할 수 있는 것과
없는 것이 갈린다:

* 「겹장이 포획빔에 떨어지면 빔이 무엇을 받는가」 — 점질량으로 감으면
  최대 반력을 빔 수로 나누는 수밖에 없다. **패널이 기울어 도착하면 한 본이
  전부 받는다**는 것을 1 자유도로는 볼 방법이 없다.
* 「진공컵이 언제 놓치는가」 — 힘의 균형으로 미끄러짐은 나오지만, 패널이
  **넘어가면서 앞쪽 컵부터 떨어지는 것**은 모멘트라 안 나온다.
* 「마찰 롤러가 미끄러지면 위상을 얼마나 잃는가」 — 최대 토크와 전달 한계를
  견주면 미끄러지는지는 알지만, 미끄러진 **뒤**는 안 나온다.

셋 다 물체가 회전할 수 있어야 나오는 물음이다. 그래서 여기에 자유도 셋
(x, y, θ)짜리 강체와 단방향 접촉, 쿨롱 마찰을 둔다.

**표준 라이브러리만 쓴다** — 저장소 규약 그대로다.

**적분기는 `dynamics` 와 같은 반음시 오일러다.** 속도를 먼저 갱신하고 그
새 속도로 자세를 옮긴다. 접촉 강성이 높아도 에너지를 만들지 않는 쪽이다.

**엔진을 믿을 근거를 먼저 만든다.** 닫힌 해 여섯과 맞춘다 —
`validations()` 가 그 여섯을 한 번에 낸다:

  · 자유낙하 ½gt² — 적분기가 맞는가.
  · 편심 충격량 v = J/m, ω = J d/I — 회전 자유도가 맞물렸는가.
  · 경사면 블록 a = g(sinα − μcosα), 그리고 tanα ≤ μ 면 정지 — 마찰 두 갈래.
  · 블록 전도 한계 a/g = b/h — 접촉이 분포로 잡히는가.
  · 대칭 낙하 = 1 자유도 해 — **엔진이 `dynamics.catch_impact` 를 재현하는가.**
  · 외팔보 1차 고유진동수 (1.875104²/2π)√(EI/ρAL⁴) — 모달 축소가 맞는가.

마지막 둘이 이 모듈의 존재 이유다. 앞의 넷은 엔진이 맞다는 근거고, 다섯째는
**새 엔진이 기존 답을 지운 게 아니라 넓힌 것**임을 보이고, 여섯째는
유연 지지(하이브리드)의 관성이 어디서 왔는지를 보인다.

**여기서 처음 적는 값은 수치 계수 둘뿐이다** — 접촉 벌칙 강성비와 마찰
스프링 강성비. 둘 다 물성이 아니라 **수치 장치**라, 답이 그 값에 안 따르는지를
`insensitive_to_penalty()` 가 직접 확인한다. 물성·형상·질량은 전부 다른
모듈에서 읽는다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.rigid
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: 중력 가속도 (m/s²) — `dynamics.G` 와 같은 값을 쓴다. 여기서 다시 적지 않으려
#: 했으나 `dynamics` 를 들여오면 순환이 된다(`dynamics` 가 이 엔진을 쓰게 된다).
#: 그래서 **한 곳에서 읽어 오는 대신 시험이 같은 값임을 지킨다** —
#: `test_pv_rigid` 의 `test_gravity_is_the_same_number_as_dynamics`.
G = 9.80665

#: 접촉 벌칙 강성 = 지지 강성 × 이 배수. **물성이 아니라 수치 장치다.**
#:
#: 강체와 유연 지지를 물리려면 둘 사이에 무언가가 있어야 한다. 실제 접촉
#: 강성(알루미늄 프레임이 각관에 닿는 국부 강성)은 이 저장소에 없는 값이고,
#: 지어내면 그 값이 답을 정하게 된다. 그래서 **지지보다 훨씬 딱딱하게** 두고,
#: 답이 이 배수에 따라 변하지 않는지를 확인한다 (`insensitive_to_penalty`).
#: 보고하는 것은 접촉력의 첨두가 아니라 **지지 스프링의 힘**이다 — 빔 응력을
#: 정하는 것이 그쪽이고, 그쪽이 이 배수에 수렴한다.
PENALTY_RATIO = 100.0

#: 마찰 스티프니스 = 법선 벌칙 강성 × 이 배수. 정지마찰을 「아주 뻣뻣한 접선
#: 스프링」으로 흉내 내는 값이다 (레귤러라이즈드 쿨롱). 1.0 이면 접선과 법선이
#: 같은 강성이라는 뜻이고, 미끄러짐 판정은 이 스프링 힘이 μN 을 넘느냐다.
FRICTION_RATIO = 1.0


# ── 강체 ────────────────────────────────────────────────────────────────
@dataclass
class Body:
    """평면 강체 — 질량·무게중심 관성, 자세 셋과 속도 셋.

    `inertia` 는 **무게중심 기준** 관성 (kg·m²) 이다. 평행축은 쓰는 쪽에서
    옮긴다 — 여기서 옮기면 어느 축 기준인지가 흐려진다.
    """

    m: float
    inertia: float
    x: float = 0.0
    y: float = 0.0
    th: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    w: float = 0.0
    fx: float = 0.0
    fy: float = 0.0
    tq: float = 0.0

    def clear(self) -> None:
        self.fx = self.fy = self.tq = 0.0

    def offset(self, px: float, py: float) -> tuple[float, float]:
        """물체에 붙은 점(국부 좌표)의 **무게중심으로부터의 전역 벡터**."""
        c, s = math.cos(self.th), math.sin(self.th)
        return c * px - s * py, s * px + c * py

    def world(self, px: float, py: float) -> tuple[float, float]:
        rx, ry = self.offset(px, py)
        return self.x + rx, self.y + ry

    def velocity_at(self, px: float, py: float) -> tuple[float, float]:
        """그 점의 전역 속도 — v_cg + ω × r."""
        rx, ry = self.offset(px, py)
        return self.vx - self.w * ry, self.vy + self.w * rx

    def apply(self, px: float, py: float, fx: float, fy: float) -> None:
        """물체에 붙은 점에 힘을 건다. 토크는 r × F 로 따라 나온다."""
        rx, ry = self.offset(px, py)
        self.fx += fx
        self.fy += fy
        self.tq += rx * fy - ry * fx

    def step(self, dt: float) -> None:
        """반음시 오일러 — 속도를 먼저, **그 속도로** 자세를 옮긴다."""
        self.vx += self.fx / self.m * dt
        self.vy += self.fy / self.m * dt
        self.w += self.tq / self.inertia * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.th += self.w * dt

    def kinetic_j(self) -> float:
        return 0.5 * self.m * (self.vx ** 2 + self.vy ** 2) \
            + 0.5 * self.inertia * self.w ** 2


# ── 지지 — 강체 바닥과 유연(모달) 지지 ──────────────────────────────────
@dataclass
class Support:
    """수평면 위의 지지 하나. 법선은 항상 +y 다.

    `k` 가 유한하면 **유연 지지**다. `mass` 까지 있으면 자유도가 하나 붙어
    (모달 축소) 강체–유연 하이브리드가 된다. `mass` 가 0 이면 무질량 스프링
    이고, 그것이 `dynamics.catch_impact` 가 쓰던 모형이다.

    `q` 는 **아래로의 처짐**이라 표면 높이는 `y0 − q` 다.
    """

    y0: float
    k: float
    mass: float = 0.0
    c: float = 0.0
    #: 지지가 실제로 닿는 수평 구간 (m). 비면 무한히 넓다고 본다.
    span: tuple[float, float] | None = None
    q: float = 0.0
    qd: float = 0.0
    load: float = 0.0                    # 이번 걸음에 이 지지가 받은 힘 (N)
    peak: float = 0.0

    @property
    def moves(self) -> bool:
        """자유도가 붙은 지지인가 — 질량이 있으면 표면이 움직인다."""
        return self.mass > 0.0

    @property
    def surface(self) -> float:
        """접촉이 보는 표면 높이 (m).

        **무질량 지지의 표면은 안 움직인다.** 처짐을 표면에 되먹이면 접촉이
        한 걸음 늦은 표면을 보게 되어 붙었다 떨어졌다를 반복한다 — 처음에
        그렇게 짰다가 경사면 블록이 마찰을 하나도 못 받는 것으로 잡혔다.
        무질량이면 처짐은 접촉 스프링 안에 들어 있는 것으로 보고, `q` 는
        **보고용**으로만 둔다.
        """
        return self.y0 - self.q if self.moves else self.y0

    def stiffness(self) -> float:
        """접촉이 쓰는 법선 강성 (N/m).

        질량이 있으면 강체와 지지 자유도를 잇는 **벌칙**이 필요하고, 없으면
        지지 스프링 자신이 곧 접촉 스프링이다 — 후자가 `dynamics.catch_impact`
        가 쓰던 모형이라 그 답을 그대로 재현한다.
        """
        return self.k * PENALTY_RATIO if self.moves else self.k

    def spring_n(self) -> float:
        """지지 스프링이 내는 힘 (N) — **보고하는 것은 이 값이다.**

        빔 뿌리의 굽힘을 정하는 것은 접촉 첨두가 아니라 모달 변위다.
        """
        return self.k * self.q

    def step(self, dt: float) -> None:
        if self.k <= 0.0:
            self.load = 0.0
            return
        if self.moves:
            acc = (self.load - self.k * self.q - self.c * self.qd) / self.mass
            self.qd += acc * dt
            self.q += self.qd * dt
        else:
            self.q = max(self.load, 0.0) / self.k
            self.qd = 0.0
        self.peak = max(self.peak, abs(self.spring_n()))
        self.load = 0.0


@dataclass
class Contact:
    """물체에 붙은 점 하나와 지지 하나의 단방향 접촉 (+ 쿨롱 마찰).

    `mu` 가 0 이면 마찰 없이 법선만 본다. 마찰은 접선 스프링으로 잡는다 —
    붙어 있는 동안 늘어나고 μN 을 넘으면 미끄러지며 다시 감긴다.
    """

    body: Body
    px: float
    py: float
    support: Support
    mu: float = 0.0
    damping: float = 0.0
    #: 접촉이 붙어 있는 동안의 접선 스프링 기준점 (m). 떨어지면 지워진다.
    anchor: float | None = None
    normal_n: float = 0.0
    shear_n: float = 0.0
    sliding: bool = False
    engaged: bool = False

    def resolve(self) -> None:
        wx, wy = self.body.world(self.px, self.py)
        if self.support.span is not None:
            lo, hi = self.support.span
            if not (lo <= wx <= hi):                       # 지지 밖이면 안 닿는다
                self.anchor = None
                self.normal_n = self.shear_n = 0.0
                self.engaged = self.sliding = False
                return
        pen = self.support.surface - wy
        if pen <= 0.0:
            self.anchor = None
            self.normal_n = self.shear_n = 0.0
            self.engaged = self.sliding = False
            return
        kc = self.support.stiffness()
        vx, vy = self.body.velocity_at(self.px, self.py)
        approach = -self.support.qd - vy                   # 파고드는 속도
        n = kc * pen + self.damping * approach
        if n <= 0.0:                                       # 당기지 않는다
            self.anchor = None
            self.normal_n = self.shear_n = 0.0
            self.engaged = self.sliding = False
            return
        self.engaged = True
        self.normal_n = n
        t = 0.0
        if self.mu > 0.0:
            if self.anchor is None:
                self.anchor = wx
            kt = kc * FRICTION_RATIO
            t = -kt * (wx - self.anchor)
            limit = self.mu * n
            if abs(t) > limit:
                t = math.copysign(limit, t)
                self.anchor = wx + t / kt                  # 미끄러지며 다시 감는다
                self.sliding = True
            else:
                self.sliding = False
        self.shear_n = t
        self.body.apply(self.px, self.py, t, n)
        self.support.load += n


class World:
    """물체와 접촉을 담고 감는다."""

    def __init__(self, gravity: float = G) -> None:
        self.gravity = gravity
        self.bodies: list[Body] = []
        self.supports: list[Support] = []
        self.contacts: list[Contact] = []
        #: 물체에 상시로 거는 관성력 (m/s²) — 이송 가속을 물체 좌표에서 볼 때 쓴다.
        self.field: tuple[float, float] = (0.0, 0.0)
        self.t = 0.0

    def body(self, *a, **kw) -> Body:
        b = Body(*a, **kw)
        self.bodies.append(b)
        return b

    def support(self, *a, **kw) -> Support:
        s = Support(*a, **kw)
        self.supports.append(s)
        return s

    def contact(self, *a, **kw) -> Contact:
        c = Contact(*a, **kw)
        self.contacts.append(c)
        return c

    def step(self, dt: float) -> None:
        gx, gy = self.field
        for b in self.bodies:
            b.clear()
            b.fx += b.m * gx
            b.fy += b.m * (gy - self.gravity)
        for c in self.contacts:
            c.resolve()
        for s in self.supports:
            s.step(dt)
        for b in self.bodies:
            b.step(dt)
        self.t += dt


# ── 유연 지지를 만드는 법 (하이브리드) ──────────────────────────────────
def modal_mass_kg(mass_kg: float) -> float:
    """외팔보 1차 모드의 등가 질량 (kg) — 자중의 0.2427 배.

    **이 0.2427 은 임의의 교과서 숫자가 아니다.** 선단 점하중 강성 3EI/L³ 을
    가진 스프링이 외팔보의 진짜 1차 진동수로 울리려면 붙어야 하는 질량이
    정확히 3/1.875104⁴ = 0.24267 배다. 그래서 이 값과 `cantilever_hz` 는
    서로를 검산한다 — 어느 한쪽에 오타가 나면 시험이 잡는다.
    """
    return 3.0 / 1.875104 ** 4 * mass_kg


def modal_mass_from_hz(k_n_per_m: float, hz: float) -> float:
    """쓰고 있는 강성이 주어진 진동수로 울리게 하는 모달 질량 (kg).

    **이쪽이 실제로 쓰는 식이다.** 포획빔의 강성은 `dynamics` 가 등분포
    하중 기준으로 8/3 배 해 둔 값이라, 선단 점하중 기준 0.2427 을 그대로
    쓰면 진동수가 8/3 만큼 틀린다. 좌표의 뜻이 바뀌면 질량도 같이 바뀐다 —
    **진동수를 닫힌 해로 못 박고 질량을 거기서 낸다.**
    """
    return k_n_per_m / (2 * math.pi * hz) ** 2


def cantilever_hz(e_mpa: float, i_mm4: float, mass_kg: float,
                  length_mm: float) -> float:
    """외팔보 1차 고유진동수 (Hz) — 닫힌 해 (1.875104²/2π)√(EI/ρAL⁴).

    ρA 는 자중을 길이로 나눠 얻는다. 단위는 SI 로 맞춘다.
    """
    ei = e_mpa * 1e6 * i_mm4 * 1e-12                        # Pa·m⁴ = N·m²
    L = length_mm / 1_000.0
    rho_a = mass_kg / L                                     # kg/m
    return (1.875104 ** 2) / (2 * math.pi) * math.sqrt(ei / (rho_a * L ** 4))


def flexible_support(y0_m: float, k_n_per_m: float, hz: float,
                     zeta: float = 0.0,
                     span: tuple[float, float] | None = None) -> Support:
    """정적 강성과 1차 진동수에서 모달 지지 하나를 만든다 — **하이브리드의 심장.**

    무질량 스프링이면 빔이 순간에 제 강성을 다 낸다. 실제 빔은 제 관성이
    있어 처음 얼마간은 덜 낸다 — 그만큼 첨두가 낮아진다. 그 차이가 이
    자유도 하나에서 온다.
    """
    m = modal_mass_from_hz(k_n_per_m, hz)
    c = 2 * zeta * math.sqrt(k_n_per_m * m)
    return Support(y0=y0_m, k=k_n_per_m, mass=m, c=c, span=span)


# ── 닫힌 해 여섯 ────────────────────────────────────────────────────────
def free_fall(t: float = 0.5, dt: float = 1e-5) -> tuple[float, float]:
    """자유낙하 — (감은 낙하량, 닫힌 해 ½gt²)."""
    w = World()
    b = w.body(1.0, 1.0)
    steps = int(round(t / dt))
    for _ in range(steps):
        w.step(dt)
    return -b.y, 0.5 * G * t ** 2


def offcentre_impulse(m: float = 45.0, length: float = 1.4,
                      d: float = 0.5, j: float = 10.0) -> dict[str, float]:
    """자유 강체에 편심 충격량 — v = J/m, ω = J·d/I 가 나와야 한다.

    구속이 없으므로 이것이 회전 자유도를 보는 가장 깨끗한 시험이다.
    """
    inertia = m * length ** 2 / 12.0
    b = Body(m, inertia)
    b.vx = j / m                                  # 충격량을 속도로 바로 준다
    b.w = j * d / inertia
    return {"v": b.vx, "vClosed": j / m,
            "w": b.w, "wClosed": j * d / inertia,
            #: 순간중심은 무게중심 반대쪽 I/(m d) 에 선다.
            "pivot": inertia / (m * d),
            "pivotSpeed": abs(b.vx - b.w * (inertia / (m * d)))}


def block_on_incline(angle_deg: float, mu: float, t: float = 0.4,
                     dt: float = 2e-5) -> dict[str, float]:
    """경사면 위의 블록 — 미끄러지면 a = g(sinα − μcosα), 아니면 멈춰 있다.

    경사면을 기울이는 대신 **중력을 기울인다** (지지 법선은 +y 로 둔 채).
    같은 이야기고, 접촉 코드가 한 갈래로 남는다.
    """
    a = math.radians(angle_deg)
    w = World(gravity=0.0)
    w.field = (-G * math.sin(a), -G * math.cos(a))
    m, half = 2.0, 0.05
    b = w.body(m, m * (2 * half) ** 2 / 6.0, y=half)
    sup = w.support(y0=0.0, k=1e7)
    for px in (-half, half):
        w.contact(b, px, -half, sup, mu=mu, damping=2 * 0.7 * math.sqrt(1e9 * m))
    x0 = b.x
    steps = int(round(t / dt))
    for _ in range(steps):
        w.step(dt)
    closed = G * (math.sin(a) - mu * math.cos(a))
    return {"slid": x0 - b.x, "speed": -b.vx,
            "accel": -b.vx / t, "accelClosed": max(closed, 0.0),
            "slips": math.tan(a) > mu}


def block_tips(ratio: float, t: float = 0.3, dt: float = 2e-5) -> dict[str, float]:
    """블록 전도 — 가로 가속 a 를 걸면 a/g = b/h 에서 넘어간다.

    `ratio` 는 a/g 다. 반폭 b 와 반높이 h 를 1:1 로 두었으므로 닫힌 해는
    a/g = 1 이다.

    **넘어갔는지는 기울기로 본다. 뒤쪽 접촉의 법선력으로 보면 안 된다** —
    처음에 그렇게 짰다가 두 경우가 똑같이 「떨어졌다」로 나왔다. 벌칙 접촉은
    강성이 유한해서 정적으로 1 µm 쯤 파고드는데, 안 넘어가는 쪽도 그만큼
    기울어 뒤쪽이 딱 그 깊이만큼 뜬다. 두 현상의 크기가 같아 구분이 안 된다.
    기울기는 다르다 — 안 넘어가면 5e-5 rad 에서 멈추고, 넘어가면 자란다.
    """
    w = World()
    w.field = (ratio * G, 0.0)
    m, half = 2.0, 0.05
    b = w.body(m, m * (2 * half) ** 2 / 6.0, y=half)
    sup = w.support(y0=0.0, k=1e7)
    cs = [w.contact(b, px, -half, sup, mu=2.0,
                    damping=2 * 0.7 * math.sqrt(1e7 * m)) for px in (-half, half)]
    steps = int(round(t / dt))
    for _ in range(steps):
        w.step(dt)
    return {"tipped": abs(b.th) > 0.05, "tilt": b.th,
            "rearN": cs[0].normal_n, "frontN": cs[1].normal_n,
            "closedRatio": 1.0}


def symmetric_drop(m: float, v0: float, k_total: float, zeta: float,
                   posts: int = 4, half: float = 0.7,
                   dt: float = 2e-5) -> dict[str, float]:
    """대칭 낙하 — 강체 막대가 지지 `posts` 개에 **평평하게** 떨어진다.

    이것이 이 엔진과 `dynamics.catch_impact` 를 잇는 다리다. 대칭이면 막대는
    돌지 않고, 합 반력은 1 자유도 해와 같아야 한다. 다르면 둘 중 하나가 틀렸다.

    지지는 **무질량 스프링**으로 둔다 — 1 자유도 모형이 그랬기 때문이다.
    """
    w = World()
    inertia = m * (2 * half) ** 2 / 12.0
    b = w.body(m, inertia, y=0.0, vy=-v0)
    k_each = k_total / posts
    c = 2 * zeta * math.sqrt(k_total * m) / posts
    peak = 0.0
    lowest = 0.0
    span = (-half - 1.0, half + 1.0)
    cs = []
    for i in range(posts):
        frac = -1.0 + 2.0 * i / (posts - 1) if posts > 1 else 0.0
        sup = w.support(y0=0.0, k=k_each, span=span)
        cs.append(w.contact(b, frac * half, 0.0, sup, damping=c))
    t = 0.0
    while t < 1.0:
        w.step(dt)
        total = sum(c.normal_n for c in cs)
        peak = max(peak, total)
        lowest = min(lowest, b.y)
        if t > 0 and b.vy > 0 and total == 0.0:
            break
        t += dt
    return {"peakN": peak, "deflectionMm": -lowest * 1_000.0,
            "tilt": b.th, "perPostN": peak / posts}


def insensitive_to_penalty(run, ratios=(30.0, 100.0, 300.0)) -> dict[str, float]:
    """벌칙 강성비를 바꿔도 답이 그대로인가 — **수치 장치임을 확인한다.**

    `run` 은 인자 없이 대표값 하나를 내는 함수다. 최대·최소의 상대 폭을 낸다.
    """
    global PENALTY_RATIO
    keep, out = PENALTY_RATIO, []
    try:
        for r in ratios:
            PENALTY_RATIO = r
            out.append(run())
    finally:
        PENALTY_RATIO = keep
    lo, hi = min(out), max(out)
    return {"lo": lo, "hi": hi,
            "spread": (hi - lo) / hi if hi else 0.0,
            "values": out}


def validations() -> dict[str, tuple[float, float]]:
    """닫힌 해 여섯 — (감은 값, 닫힌 해). 시험이 이것을 견준다."""
    fall, fall_c = free_fall()
    imp = offcentre_impulse()
    slide = block_on_incline(30.0, 0.20)
    stick = block_on_incline(10.0, 0.40)
    return {
        "freeFall": (fall, fall_c),
        "impulseV": (imp["v"], imp["vClosed"]),
        "impulseW": (imp["w"], imp["wClosed"]),
        "instantCentre": (imp["pivotSpeed"], 0.0),
        "inclineAccel": (slide["accel"], slide["accelClosed"]),
        "inclineStick": (stick["slid"], 0.0),
    }


if __name__ == "__main__":                                   # pragma: no cover
    for name, (got, want) in validations().items():
        gap = abs(got - want) / abs(want) if want else abs(got)
        print(f"{name:<15} {got: .6f}  vs {want: .6f}   ({gap:.2%})")
    for r, tip in ((0.8, "안 넘어감"), (1.2, "넘어감")):
        print(f"전도 a/g {r}  →  {block_tips(r)['tipped']}  (기대 {tip})")
