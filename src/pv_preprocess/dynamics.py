# -*- coding: utf-8 -*-
"""FL-101 → RB-101 구간의 **시간영역** 동역학.

`drives.py` 는 정격을 낸다 — 사다리꼴 프로파일을 가정하고 필요한 토크를
역산한다. 축을 고르는 데는 그것으로 충분하지만, 그 방식으로는 **답이 안 나오는
물음이 넷** 있다:

* **진공이 언제 놓치는가.** 파지력과 가속의 경쟁이라, 가속이 어떻게 들어오고
  나가는지를 감아야 나온다. 정격 토크로는 안 나온다.
* **마찰 롤러가 언제 미끄러지는가.** 미끄러지면 토크가 모자란 게 아니라
  **위상을 잃는다** — 반전각이 틀어지고 0°/180° 락이 안 물린다.
* **겹장이 떨어지면 포획빔이 무엇을 받는가.** OI-05 에 낙하 에너지 163 J 이
  적혀 있지만, 빔이 견뎌야 하는 것은 에너지가 아니라 **힘**이다.
* **가속을 얼마나 올릴 수 있는가.** 택트를 줄이자는 이야기는 전부 이 값 위에
  선다.

넷 다 시간을 감아야 나온다. 그래서 여기서 감는다.

**표준 라이브러리만 쓴다** — numpy 없이 돈다 (`grade.py`·`acoustics.py` 와 같은
규약이다. 해석기가 설치물을 요구하기 시작하면 CI 에서 조용히 안 돌게 된다).

**적분기는 반음시 오일러다.** 속도를 먼저 갱신하고 **그 새 속도로** 위치를
옮긴다. 스프링–댐퍼 접촉에서 명시 오일러보다 안정적이고(명시식은 접촉 강성이
높아지면 에너지를 만들어 낸다), 이 강성대에서 RK4 를 쓸 만큼 정밀할 이유가
없다. 대신 **간격을 스스로 검사한다** — `converged()` 가 간격을 반으로 줄여도
답이 안 변하는지 본다. 그것이 적분기를 믿을 유일한 근거다.

**여기서 처음 적는 값은 물성과 접촉 계수뿐이다.** 질량·관성은 `drives`, 행정과
시각은 `kinematics`, 형상과 단면은 `fabrication` 에서 읽는다. 두 곳에 같은 값을
두 번 적지 않는다는 규약은 여기서도 같다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.dynamics
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import drives, fabrication, kinematics

# ── 물성 · 접촉 계수 (여기서 처음 적는 값) ──────────────────────────────

#: 중력 가속도 (m/s²).
G = 9.80665

#: 강재 탄성계수 (GPa) — 포획빔 RHS 의 처짐에 쓴다. KS D 3568 일반구조용 각형강관.
STEEL_E_GPA = 200.0

#: 공기 점성계수 (Pa·s, 20 ℃). 적층에서 한 장을 떼는 저항이 여기서 나온다.
#:
#: **정압 흡착이 아니라 점성 저항이다.** 처음에는 「유리면 사이가 음압이 된다」로
#: 잡고 3 kPa 를 패널 면적 전체에 걸었는데, 그러면 요구가 10.5 kN 이 되어 컵
#: 3.1 kN 으로는 어림도 없다. 그 계산은 **틀렸다** — `kinematics` 가 프레임이
#: 유리면보다 4 mm 솟는다고 적어 두었고(`PANEL_FRAME_GLASS_STEP_MM`), 적층은
#: 프레임끼리 맞닿으므로 **유리면 사이에 8 mm 가 뜬다.** 맞닿지 않은 두 판은
#: 정압으로 붙지 않는다.
#:
#: 대신 남는 것이 **스테판 접착**이다 — 벌어지는 틈으로 공기가 빨려 들어오는
#: 동안의 점성 저항이고, 힘이 `속도 / 틈³` 에 비례한다. 틈이 있으면 무시할
#: 만하고 없으면 손쓸 수 없이 커진다. 그 갈림이 `sep_peel()` 이 내는 답이다.
AIR_VISCOSITY_PAS = 1.81e-5

#: 유리면끼리 실제로 맞닿았을 때 남는 틈 (mm) — 표면 거칠기·평탄도 수준.
#: 무프레임 레시피(`recipe` 의 frameless)에서는 이 값이 유효 틈이 된다.
GLASS_CONTACT_GAP_MM = 0.05

#: 작업 진공 (kPa, 절대압 아래 음압). 제작 도면집의 누설 시험이 −60 kPa 유지를
#: 요구하므로(EOAT 조립 검사) 작업점은 그보다 얕은 −55 로 잡는다.
WORKING_VACUUM_KPA = 55.0

#: 진공컵 유효 흡착면적 비율. 벨로우즈 컵은 지름 전체가 아니라 립 안쪽만 문다.
CUP_EFFECTIVE = 0.80

#: 진공 파지 안전율 — 수직 인장 기준. 진공 파단은 곧 유리 파손이라 크게 잡는다.
VACUUM_SAFETY = 2.0

#: 진공컵 고무–유리 마찰계수 (건조). 접선 방향(가로 가속)을 이것으로 받는다.
CUP_MU = 0.70

#: 접촉 감쇠비 — 겹장이 포획빔에 떨어질 때. 강재 구조의 첫 모드 감쇠는 보통
#: 0.01…0.02 인데, 여기서는 알루미늄 프레임이 각관 위에 떨어지는 **국부 접촉**이라
#: 그보다 크다. 0.10 은 보수적으로 **작게** 잡은 값이다 — 감쇠를 크게 잡으면
#: 최대 반력이 줄어들어 빔이 실제보다 안전해 보인다.
CONTACT_DAMPING = 0.10


# ── 적분기 ──────────────────────────────────────────────────────────────
@dataclass
class State:
    """한 자유도의 상태. 직선축이면 m·x·v 가 m·m/s, 회전축이면 kg·m²·rad·rad/s."""

    inertia: float
    x: float = 0.0
    v: float = 0.0
    t: float = 0.0

    def step(self, force: float, dt: float) -> None:
        """반음시 오일러 한 걸음 — 속도를 먼저, **그 속도로** 위치를 옮긴다."""
        self.v += force / self.inertia * dt
        self.x += self.v * dt
        self.t += dt


@dataclass
class Trace:
    """한 번 감은 결과. 최대값만 남기지 않는다 — **언제** 나왔는지가 설계를 정한다."""

    t: list[float] = field(default_factory=list)
    x: list[float] = field(default_factory=list)
    v: list[float] = field(default_factory=list)
    f: list[float] = field(default_factory=list)

    def add(self, t: float, x: float, v: float, f: float) -> None:
        self.t.append(t)
        self.x.append(x)
        self.v.append(v)
        self.f.append(f)

    def peak(self) -> tuple[float, float]:
        """최대 |힘| 과 그때의 시각."""
        i = max(range(len(self.f)), key=lambda k: abs(self.f[k]))
        return self.f[i], self.t[i]

    def peak_speed(self) -> float:
        return max(abs(v) for v in self.v)

    @property
    def travel(self) -> float:
        return self.x[-1] - self.x[0]


def trapezoid(t: float, total: float, distance: float) -> float:
    """사다리꼴 프로파일의 **가속도** (단위/s²) — 가속·정속·감속 1:1:1.

    `drives.PEAK_FACTOR` 가 최고속도 = 평균 × 1.5 라고 적어 둔 바로 그 프로파일이다.
    거기서는 값 하나(피크 토크)를 뽑는 데 썼고, 여기서는 시간을 감는 데 쓴다 —
    같은 가정 위에 서야 두 모듈이 같은 축을 이야기한다.
    """
    if total <= 0:
        return 0.0
    seg = total / 3.0
    a = distance / (seg * (total - seg))          # 사다리꼴 면적 = 거리
    if t < seg:
        return a
    if t < 2 * seg:
        return 0.0
    if t <= total:
        return -a
    return 0.0


def converged(run, dt: float, tol: float = 0.01) -> tuple[float, float, bool]:
    """간격을 반으로 줄여도 답이 안 변하는가 — 적분기를 믿을 유일한 근거.

    `run(dt)` 은 대표값 하나(대개 최대 힘)를 돌려주는 호출가능이어야 한다.
    """
    coarse, fine = run(dt), run(dt / 2)
    if coarse == 0:
        return coarse, fine, fine == 0
    return coarse, fine, abs(fine - coarse) / abs(coarse) <= tol


# ── 진공 파지 ───────────────────────────────────────────────────────────
def cup_force_n(diameter_mm: float, count: int,
                vacuum_kpa: float = WORKING_VACUUM_KPA) -> float:
    """진공컵 무리가 낼 수 있는 수직 파지력 (N)."""
    area = math.pi * (diameter_mm / 2_000.0) ** 2 * CUP_EFFECTIVE
    return vacuum_kpa * 1_000.0 * area * count


def _part(sheet: str, tag: str) -> fabrication.Part:
    """제작 도면집에서 부품 하나를 집는다 — 치수를 여기 다시 적지 않으려고."""
    for part in fabrication.assembly(sheet).parts:
        if part.tag == tag:
            return part
    raise KeyError(f"{sheet} 에 {tag} 이 없다")


def _commercial(sheet: str, tag: str) -> fabrication.Commercial:
    """상용품 하나 — 컵 개수는 도면집이 정본이다."""
    for item in fabrication.assembly(sheet).commercial:
        if item.tag == tag:
            return item
    raise KeyError(f"{sheet} 에 {tag} 이 없다")


#: 이 구간의 조립체 — 카세트 · 포획빔 · 로봇/EOAT.
SHEET_BFC, SHEET_CATCH, SHEET_ROBOT = "PV-FAB-A03", "PV-FAB-A04", "PV-FAB-A05"


def sep_cups() -> tuple[float, int]:
    """SEP-101 분리헤드의 컵 — 제작 도면집에서 읽는다 (Ø150 × 4구역)."""
    return 150.0, _commercial(SHEET_BFC, "BFC-VC-01").qty


def eoat_cups() -> tuple[float, int]:
    """RB-101 EOAT 의 컵 — Ø75 × 4구역 × 4."""
    return 75.0, _commercial(SHEET_ROBOT, "EOAT-VC-01").qty


# ── 1. SEP-101 진공 분리 — 한 장을 적층에서 떼어 낸다 ───────────────────
def stack_gap_mm() -> float:
    """적층에서 **유리면 사이에 뜨는 틈** (mm).

    프레임이 유리면보다 솟은 만큼이 위아래로 두 번 들어간다. 이 값이 0 이면
    유리가 맞닿는다는 뜻이고, 그때 한 장을 곧게 들어 올리는 일은 성립하지 않는다.
    """
    return 2 * kinematics.PANEL_FRAME_GLASS_STEP_MM


def stefan_force_n(gap_mm: float, speed_ms: float) -> float:
    """벌어지는 두 판 사이의 점성 저항 (N) — 스테판 접착.

    원판 근사다: F = 3πμR⁴/(2h³) · dh/dt. 사각 패널은 같은 면적의 원으로 바꿔
    R 을 잡는다(모서리에서 실제보다 약간 작게 나오지만, h³ 이 지배하는 식이라
    그 오차는 틈 하나를 잘못 잡는 것에 비하면 없는 것과 같다).
    """
    area = (kinematics.PANEL_MM[0] / 1_000.0) * (kinematics.PANEL_MM[1] / 1_000.0)
    r = math.sqrt(area / math.pi)
    h = max(gap_mm, 1e-6) / 1_000.0
    return 3 * math.pi * AIR_VISCOSITY_PAS * r ** 4 / (2 * h ** 3) * speed_ms


def sep_peel(gap_mm: float | None = None) -> dict[str, float]:
    """분리헤드가 이겨야 하는 것과 낼 수 있는 것.

    자중 + 가속 + **틈으로 공기가 빨려 드는 점성 저항**이다. 셋째 항이 이
    설비의 성패를 가른다 — 힘이 틈의 세제곱에 반비례하므로 답이 「넉넉하다」와
    「불가능하다」 사이에서 갑자기 갈린다.
    """
    d, n = sep_cups()
    hold = cup_force_n(d, n)
    gap = stack_gap_mm() if gap_mm is None else gap_mm
    weight = drives.PANEL_KG * G
    lift = kinematics.PATH[0]
    total = lift[1] - lift[0]
    a = trapezoid(0.0, total, kinematics.SEPARATION_MM / 1_000.0)
    speed = a * (total / 3.0)                 # 사다리꼴 최고 속도
    inertia = drives.PANEL_KG * a
    stefan = stefan_force_n(gap, speed)
    demand = weight + inertia + stefan
    return {
        "holdN": hold,
        "weightN": weight,
        "inertiaN": inertia,
        "stefanN": stefan,
        "gapMm": gap,
        "peakMs": speed,
        "demandN": demand,
        "margin": hold / demand if demand else math.inf,
        "accelMs2": a,
    }


def sep_peel_is_enough() -> bool:
    """안전율을 넣고도 떼어 낼 수 있는가 — 프레임이 있는 적층에서."""
    return sep_peel()["margin"] >= VACUUM_SAFETY


def frameless_needs_another_way() -> bool:
    """무프레임 패널은 같은 헤드로 곧게 못 뗀다 — 그것이 이 해석의 결론이다.

    `recipe` 에 무프레임(`frameless`)이 등록돼 있고 그 레시피는 AFR 인발만
    건너뛴다. 하지만 **투입부가 먼저 막힌다** — 유리끼리 맞닿으면 스테판 저항이
    컵 파지력을 몇 자릿수로 넘어선다. 곧게 드는 대신 한쪽 모서리부터 젖히거나
    (peel), 적층에 에어나이프를 넣어 틈을 먼저 만들어야 한다.
    """
    return sep_peel(GLASS_CONTACT_GAP_MM)["margin"] < 1.0


# ── 2. BLR-101 승강 — 픽업면에서 반전축까지 ────────────────────────────
def lift_run(dt: float = 0.001, takt_scale: float = 1.0) -> Trace:
    """승강 캐리지를 실제로 감는다.

    `drives.ballscrews()` 가 고른 축(리드 16 직결)이 내야 하는 힘을 시간으로
    본다. 중력은 상시 걸리고 가속은 프로파일에서 온다 — **정지 상태에서도
    무게만큼은 계속 든다**는 것이 사다리꼴 산정에서는 잘 안 보인다.
    """
    stroke_mm = kinematics.FLIP_AXIS_MM - (kinematics.PICK_FACE_MM
                                           + kinematics.SEPARATION_MM)
    seg = kinematics.PATH[2]
    total = (seg[1] - seg[0]) / takt_scale
    m = drives.lift_moving_kg()
    st, tr = State(m), Trace()
    steps = max(1, int(round(total / dt)))
    for i in range(steps + 1):
        t = i * dt
        a = trapezoid(t, total, stroke_mm / 1_000.0)
        f = m * (a + G)                     # 모터가 드는 힘 = 가속 + 중력
        tr.add(t, st.x, st.v, f)
        st.step(f - m * G, dt)              # 자유도에 남는 것은 가속분뿐
    return tr


def lift_torque_nm(takt_scale: float = 1.0) -> float:
    """승강 볼스크루가 받는 최고 토크 (N·m) — 리드와 효율에서 나온다."""
    f, _ = lift_run(takt_scale=takt_scale).peak()
    lead = drives.LIFT_LEAD_MM / 1_000.0
    return f * lead / (2 * math.pi * drives.BALLSCREW_EFFICIENCY)


# ── 3. BFC-101 반전 — 180° · 마찰 롤러 ─────────────────────────────────
def flip_run(dt: float = 0.001, takt_scale: float = 1.0) -> Trace:
    """반전축을 감는다. 힘 자리에는 **링에 걸리는 토크**(N·m)가 들어간다.

    관성만 돈다 — 링 2매·조·패드·캐리어·패널이고, 포탈과 크로스빔은 안 돈다
    (`drives.flip_inertia_kgm2()` 가 그렇게 세어 둔 이유가 여기 있다). 중력은
    축이 무게중심을 지나므로 상쇄된다.
    """
    seg = kinematics.PATH[3]
    total = (seg[1] - seg[0]) / takt_scale
    j = drives.flip_inertia_kgm2()
    st, tr = State(j), Trace()
    steps = max(1, int(round(total / dt)))
    for i in range(steps + 1):
        t = i * dt
        alpha = trapezoid(t, total, math.pi)
        torque = j * alpha
        tr.add(t, st.x, st.v, torque)
        st.step(torque, dt)
    return tr


def flip_slip(takt_scale: float = 1.0) -> dict[str, float]:
    """마찰 롤러가 미끄러지는가 — 압착력이 정하는 전달 한계와 요구를 견준다.

    **미끄러지면 토크가 모자란 것과 다른 일이 벌어진다.** 위상을 잃어 반전각이
    틀어지고, 0°/180° 락이 안 물린다. 그래서 `drives.FRICTION_SAFETY` 2.0 을
    요구로 둔다.
    """
    torque, when = flip_run(takt_scale=takt_scale).peak()
    r_ring = (kinematics.RING_R_MM + kinematics.RING_TUBE_MM) / 1_000.0
    capacity = drives.FLIP_PRELOAD_N * drives.FRICTION_MU * r_ring
    return {
        "demandNm": abs(torque),
        "capacityNm": capacity,
        "margin": capacity / abs(torque) if torque else math.inf,
        "atS": when,
        "ringR": r_ring,
    }


def flip_does_not_slip() -> bool:
    return flip_slip()["margin"] >= drives.FRICTION_SAFETY


def preload_covers_the_trapezoid() -> bool:
    """압착력 사양 400 N 이 **사다리꼴** 요구까지 덮는가.

    `drives` 는 축 둘을 **다른 프로파일**로 잡고 있다 — 볼스크루는 사다리꼴
    1:1:1(`PEAK_FACTOR` 1.5 가 그 뜻이다, 각가속 4.5θ/t²), 마찰 롤러는 삼각
    (`alpha_rad_s2` 가 4θ/t²). 삼각이 「정속이 없는 최악」이라고 적혀 있지만
    **최고 가속도로는 사다리꼴 쪽이 12.5 % 크다.** 그래서 반전 토크가 97 이 아니라
    109.5 N·m 이고, 필요 압착력도 328 → 370 N 이 된다.

    사양 400 N 은 그래도 덮는다 — 여유가 22 % 에서 8 % 로 줄 뿐이다. 값을 바꾸지
    않고 **여기서 더 엄한 쪽으로 확인**하는 이유가 그것이다. 프로파일을 하나로
    합치는 것은 축 선정을 다시 여는 일이라 설계 검토회의 몫이다.
    """
    slip = flip_slip()
    r = (kinematics.RING_R_MM + kinematics.RING_TUBE_MM) / 1_000.0
    needed = slip["demandNm"] / r / drives.FRICTION_MU * drives.FRICTION_SAFETY
    return drives.FLIP_PRELOAD_N >= needed


# ── 4. 겹장 낙하 — 포획빔이 받는 것 (OI-05) ────────────────────────────
def catch_beam_stiffness_n_per_mm() -> float:
    """포획빔 네 본의 합 강성 (N/mm).

    빔은 벽에서 제 길이로 나오는 **외팔보**다(OI-07 이 그린 안). 낙하 하중이
    빔 전 길이에 고르게 걸린다고 보면 등가 선단강성은 점하중의 8/3 배다
    (등분포 외팔보 처짐 wL⁴/8EI 를 같은 전체하중의 선단 처짐 WL³/3EI 와 맞춘 값).

    **외팔보로 보는 것이 보수적이다** — 실제로는 수납 카세트가 뿌리를 물고
    있어 완전 고정단보다 무르고, 대신 빔 중간을 받치는 것이 없다.
    """
    part = _part(SHEET_CATCH, "CD-BM-01")
    length, width, depth = part.size          # 2,900 × 60 × 100 (RHS)
    t = part.t
    outer = width * depth ** 3
    inner = (width - 2 * t) * (depth - 2 * t) ** 3
    i_mm4 = (outer - inner) / 12.0
    e = STEEL_E_GPA * 1_000.0                 # GPa → N/mm²
    tip = 3.0 * e * i_mm4 / length ** 3       # 선단 점하중 강성
    return tip * (8.0 / 3.0) * part.qty


def catch_impact(energy_j: float | None = None,
                 dt: float = 2e-5) -> dict[str, float]:
    """겹장이 포획빔에 떨어질 때의 **반력**을 감는다.

    OI-05 는 에너지 163 J 을 적었다. 빔을 설계하려면 거기서 힘으로 가야 하고,
    힘은 강성과 감쇠가 정한다 — 에너지만으로는 안 나온다. 스프링–댐퍼로 접촉을
    두고 감는다. 접촉은 **한 방향**이다 (빔이 패널을 당기지 않는다).
    """
    if energy_j is None:
        energy_j = double_sheet_energy_j()
    m = drives.PANEL_KG                       # 떨어지는 것은 딸려 온 아랫장 한 장
    v0 = math.sqrt(2 * energy_j / m)
    k = catch_beam_stiffness_n_per_mm() * 1_000.0        # N/m
    c = 2 * CONTACT_DAMPING * math.sqrt(k * m)
    st, tr = State(m, x=0.0, v=-v0), Trace()
    t = 0.0
    # 되튈 때까지 — 접촉이 끊기면(x ≥ 0 이고 위로) 끝난다.
    while t < 1.0:
        pen = -st.x                                       # 파고든 깊이 (m)
        if pen <= 0:
            f = 0.0
            if t > 0 and st.v > 0:
                tr.add(t, st.x, st.v, f)
                break
        else:
            f = k * pen - c * st.v                        # 위로 미는 힘
            f = max(f, 0.0)                               # 당기지 않는다
        tr.add(t, st.x, st.v, f)
        st.step(f - m * G, dt)
        t += dt
    peak, when = tr.peak()
    return {
        "energyJ": energy_j,
        "impactMs": v0,
        "peakN": peak,
        "atS": when,
        "deflectionMm": -min(tr.x) * 1_000.0,
        "stiffnessNmm": catch_beam_stiffness_n_per_mm(),
        "perBeamN": peak / _part(SHEET_CATCH, "CD-BM-01").qty,
    }


def double_sheet_energy_j() -> float:
    """겹장으로 딸려 올라온 아랫장이 떨어질 때의 에너지 (J).

    OI-05 가 문장으로 적은 **163 J 이 어디서 나오는지**를 값으로 되짚는다 —
    한 장(45 kg)이 안전분리 상승(370)만큼 떨어지는 것이다. 문장에만 있으면
    행정이 바뀌어도 안 따라온다. 떨어지는 것이 **한 장**인 이유는 위 장은
    진공컵이 계속 물고 있기 때문이다.
    """
    return drives.PANEL_KG * G * (kinematics.SEPARATION_MM / 1_000.0)


# ── 5. RB-101 인계 — 가속과 진공의 경쟁 ────────────────────────────────
def eoat_limit_ms2() -> dict[str, float]:
    """EOAT 가 패널을 놓치기 전까지 낼 수 있는 가속도.

    두 갈래로 갈린다. **수직**으로 들어 올릴 때는 파지력에서 자중을 뺀 나머지가
    가속에 쓰이고, **가로**로 흔들 때는 컵 고무의 마찰이 받는다. 둘 중 작은 쪽이
    로봇 프로그램의 상한이다 — 안전 핑거(EOAT-CY-01)는 진공을 잃은 **뒤**에
    거는 것이라 이 계산에 넣지 않는다.
    """
    d, n = eoat_cups()
    hold = cup_force_n(d, n)
    m = drives.PANEL_KG
    usable = hold / VACUUM_SAFETY
    vertical = (usable - m * G) / m
    lateral = usable * CUP_MU / m
    return {
        "holdN": hold,
        "usableN": usable,
        "verticalMs2": vertical,
        "lateralMs2": lateral,
        "limitMs2": min(vertical, lateral),
        "limitG": min(vertical, lateral) / G,
    }


def eoat_transfer_demand_ms2() -> float:
    """인계 구간이 실제로 요구하는 가속도 (m/s²) — 사다리꼴 최고값."""
    seg = kinematics.PATH[4]
    total = seg[1] - seg[0]
    stroke = (kinematics.FLIP_AXIS_MM - kinematics.HANDOVER_MM) / 1_000.0
    return trapezoid(0.0, total, stroke)


def eoat_has_headroom() -> bool:
    return eoat_limit_ms2()["limitMs2"] >= eoat_transfer_demand_ms2()


def takt_headroom() -> tuple[float, str]:
    """구간 시간을 몇 배까지 줄일 수 있는가, 그리고 **무엇이 먼저 걸리는가**.

    「빠르게 돌린다」는 가속을 곱하는 것이 아니라 **구간 시간을 줄이는 것**이다.
    가속을 곱하면 같은 시간에 더 멀리 가 버려 180° 를 지나친다 — 도착점이
    달라지므로 비교가 성립하지 않는다. 시간을 1/s 로 줄이면 행정은 그대로이고
    가속이 **s² 로** 오른다. 그래서 여유가 생각보다 빨리 닳는다.

    이름을 돌려주는 것이 값보다 중요하다 — 「1.4 배까지 된다」보다 **「마찰
    롤러가 먼저 걸린다」** 가 다음 설계 결정을 만든다.
    """
    scale, best, who = 1.0, 1.0, "걸리는 것 없음"
    while scale <= 4.0:
        limits = {
            "BFC-101 마찰 롤러 미끄럼": flip_slip(scale)["margin"] >= drives.FRICTION_SAFETY,
            "AXIS-BFC-Z 서보 순시 토크": lift_torque_nm(scale)
            <= drives.rated_torque_nm("AXIS-BFC-Z") * drives.SERVO_PEAK_FACTOR,
            "RB-101 EOAT 진공 파지": eoat_limit_ms2()["limitMs2"]
            >= eoat_transfer_demand_ms2() * scale ** 2,
        }
        failed = [k for k, ok in limits.items() if not ok]
        if failed:
            who = failed[0]
            break
        best = scale
        scale += 0.01
    return round(best, 2), who


# ── 요약 ────────────────────────────────────────────────────────────────
def summary() -> dict[str, object]:
    """도면·검토서에 그대로 넣는 값. 영상의 JS 적분기도 이것과 맞춰야 한다."""
    peel, slip, impact, eoat = sep_peel(), flip_slip(), catch_impact(), eoat_limit_ms2()
    bare = sep_peel(GLASS_CONTACT_GAP_MM)
    lift = lift_run()
    flip = flip_run()
    return {
        "peelHoldN": round(peel["holdN"], 1),
        "peelDemandN": round(peel["demandN"], 1),
        "peelMargin": round(peel["margin"], 2),
        "peelStefanN": round(peel["stefanN"], 1),
        "peelGapMm": round(peel["gapMm"], 1),
        "framelessDemandN": round(bare["demandN"], 0),
        "framelessMargin": round(bare["margin"], 4),
        "liftPeakN": round(lift.peak()[0], 1),
        "liftPeakNm": round(lift_torque_nm(), 2),
        "liftPeakMs": round(lift.peak_speed(), 3),
        "flipPeakNm": round(abs(flip.peak()[0]), 1),
        "flipCapacityNm": round(slip["capacityNm"], 1),
        "flipMargin": round(slip["margin"], 2),
        "flipPeakRadS": round(flip.peak_speed(), 3),
        "impactJ": round(impact["energyJ"], 1),
        "impactMs": round(impact["impactMs"], 2),
        "impactPeakN": round(impact["peakN"], 0),
        "impactPerBeamN": round(impact["perBeamN"], 0),
        "impactDeflectionMm": round(impact["deflectionMm"], 1),
        "beamStiffnessNmm": round(catch_beam_stiffness_n_per_mm(), 1),
        "eoatLimitMs2": round(eoat["limitMs2"], 2),
        "eoatDemandMs2": round(eoat_transfer_demand_ms2(), 3),
        "taktHeadroom": takt_headroom()[0],
        "taktBinding": takt_headroom()[1],
    }


def checks() -> dict[str, tuple[float, float, bool]]:
    """(요구, 능력, 통과) — 화면과 시험이 같이 읽는다."""
    peel, slip, eoat = sep_peel(), flip_slip(), eoat_limit_ms2()
    return {
        "SEP-101 진공 분리": (peel["demandN"] * VACUUM_SAFETY, peel["holdN"],
                          peel["margin"] >= VACUUM_SAFETY),
        "BFC-101 압착력 사양": (flip_slip()["demandNm"] / ((kinematics.RING_R_MM
                                                     + kinematics.RING_TUBE_MM) / 1_000.0)
                           / drives.FRICTION_MU * drives.FRICTION_SAFETY,
                           drives.FLIP_PRELOAD_N,
                           preload_covers_the_trapezoid()),
        "BFC-101 롤러 미끄럼": (slip["demandNm"] * drives.FRICTION_SAFETY,
                            slip["capacityNm"], slip["margin"] >= drives.FRICTION_SAFETY),
        "AXIS-BFC-Z 서보 피크": (lift_torque_nm(),
                             drives.rated_torque_nm("AXIS-BFC-Z") * drives.SERVO_PEAK_FACTOR,
                             lift_torque_nm() <= drives.rated_torque_nm("AXIS-BFC-Z")
                             * drives.SERVO_PEAK_FACTOR),
        "RB-101 EOAT 가속": (eoat_transfer_demand_ms2(), eoat["limitMs2"],
                          eoat_has_headroom()),
    }


def main() -> None:
    print("FL-101 → RB-101 시간영역 동역학\n")
    for key, value in summary().items():
        print(f"  {key:22} {value}")
    print("\n검산")
    for name, (need, have, ok) in checks().items():
        print(f"  {'✓' if ok else '✗'} {name:22} 요구 {need:9.2f}  능력 {have:9.2f}")


if __name__ == "__main__":
    main()
