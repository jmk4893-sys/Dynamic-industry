# -*- coding: utf-8 -*-
"""구동계 검산 — 모터가 그 속도로 돌 수 있는가, 그 토크가 전달되는가.

`servos` 는 축의 **정격**을 적고 `kinematics` 는 **행정과 시각**을 적는다.
그런데 둘을 잇는 것 — 볼스크루 리드, 감속비, 마찰 롤러 지름 — 은 제작
패키지의 상용품 설명 문자열에만 있었다. 문자열은 검산되지 않는다.

그래서 **행정 ÷ 시각 = 속도**를 기구에서 내고, 그 속도를 전동기 회전수로
환산해 정격 안에 드는지 본다. 이 검산을 처음 돌렸을 때 나온 것:

* 승강축은 1,180 mm 를 2.8 s 에 간다 → 421 mm/s. 리드 10 볼스크루면
  스크루가 2,529 rpm 이고, 여기에 i=10 감속기를 물리면 **모터가 25,000 rpm**
  이어야 했다. 서보는 3,000 rpm 급이다. 감속기를 빼고 리드를 16 으로 올려
  직결한다 — 애초에 감속이 필요 없었다.
* 반전축은 마찰 롤러가 링을 미는 구조다. 정격 700 N·m 를 링에 주려면
  접선력 707 N, μ=0.6 이면 압착력 1.2 kN 이 필요한데 그 값이 어디에도
  없었다. 실제 필요 토크는 관성에서 96 N·m 라 압착력도 0.2 kN 이면 된다 —
  **압착력을 사양으로 못 박고**, 정격의 근거는 인양 무게가 아니라 관성으로
  바꾼다.

여기 있는 값은 전동기 정격이 아니라 **전동기와 기구 사이의 것**이다. 정격은
`servos`, 행정·시각은 `kinematics`, 부품 중량은 `fabrication` 이 정본이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import fabrication, kinematics, servos

#: 서보 정격 회전수 (rpm). 이보다 위는 최대회전수 영역이라 연속 정격이 안 나온다.
SERVO_RATED_RPM = 3_000
#: 서보 최대 회전수 (rpm). 이걸 넘으면 그 조합은 성립하지 않는다.
SERVO_MAX_RPM = 5_000

#: 사다리꼴 속도 프로파일에서 평균 대비 최고 속도 배수.
#: 가속·정속·감속을 1:1:1 로 잡으면 최고속도 = 평균 × 1.5 다.
PEAK_FACTOR = 1.5

#: 볼스크루 효율 (예압 볼너트, 윤활 정상).
BALLSCREW_EFFICIENCY = 0.90

#: PU 롤러–강 링 마찰계수 (건조). 벤더 자료가 오면 바꾼다.
FRICTION_MU = 0.60

#: 마찰 구동 압착력 안전율 — 미끄러지면 위상을 잃는다.
FRICTION_SAFETY = 2.0

#: 서보의 순시 최대 토크 배수 — 정격의 3배까지 수 초 동안 낸다.
SERVO_PEAK_FACTOR = 3.0

#: 패널 1장 질량 (kg) — 인터페이스 표의 최대 패널.
PANEL_KG = 45.0


@dataclass(frozen=True)
class Ballscrew:
    """볼스크루 축. `ratio` 는 모터→스크루 감속비 (1.0 이면 직결)."""

    axis: str
    lead_mm: float
    ratio: float
    screws: int
    stroke_mm: float
    seconds: float
    moving_kg: float

    @property
    def mean_mm_s(self) -> float:
        return self.stroke_mm / self.seconds

    @property
    def peak_mm_s(self) -> float:
        return self.mean_mm_s * PEAK_FACTOR

    @property
    def screw_rpm(self) -> float:
        return self.peak_mm_s / self.lead_mm * 60

    @property
    def motor_rpm(self) -> float:
        return self.screw_rpm * self.ratio

    @property
    def torque_nm(self) -> float:
        """스크루 1본이 받는 토크 — 자중을 스크루 수로 나눈다."""
        force = self.moving_kg * 9.81 / self.screws
        return force * (self.lead_mm / 1000) / (2 * math.pi * BALLSCREW_EFFICIENCY)

    @property
    def motor_torque_nm(self) -> float:
        """정속 구간에서 모터가 내는 토크 — 스크루 전부를 한 모터가 돌린다."""
        return self.torque_nm * self.screws / self.ratio

    @property
    def peak_torque_nm(self) -> float:
        """가속 구간 — 자중에 관성력이 더해진다."""
        a = self.peak_mm_s / 1000 / (self.seconds / 3)
        force = self.moving_kg * (9.81 + a)
        return (force * (self.lead_mm / 1000) / (2 * math.pi * BALLSCREW_EFFICIENCY)
                / self.ratio)

    def rms_torque_nm(self, cycle_s: float, moves_per_cycle: int = 2) -> float:
        """한 주기 안에서의 실효 토크.

        중력축은 멈춰 있을 때 브레이크가 잡으므로 토크가 0 이다. 움직이는
        시간만 듀티에 든다 — 이걸 안 보고 정격과 정속 토크를 바로 견주면
        멀쩡한 서보가 미달로 나온다.
        """
        duty = self.seconds * moves_per_cycle / cycle_s
        return self.motor_torque_nm * math.sqrt(min(1.0, duty))


@dataclass(frozen=True)
class FrictionDrive:
    """마찰 롤러가 링을 미는 축. 압착력이 사양이 아니면 토크가 정해지지 않는다."""

    axis: str
    ring_od_mm: float
    roller_od_mm: float
    ratio: float                 # 모터 → 롤러 감속비
    turns: float                 # 이 동작이 도는 회전수 (180° = 0.5)
    seconds: float
    inertia_kgm2: float
    preload_n: float             # 롤러를 링에 누르는 힘

    @property
    def ring_rpm(self) -> float:
        return self.turns / self.seconds * 60

    @property
    def roller_rpm(self) -> float:
        return self.ring_rpm * self.ring_od_mm / self.roller_od_mm

    @property
    def motor_rpm(self) -> float:
        return self.roller_rpm * self.ratio

    @property
    def alpha_rad_s2(self) -> float:
        """삼각 속도 프로파일의 각가속 — 가속·감속만 있고 정속이 없는 최악."""
        return 4 * (2 * math.pi * self.turns) / self.seconds ** 2

    @property
    def torque_nm(self) -> float:
        return self.inertia_kgm2 * self.alpha_rad_s2

    @property
    def tangential_n(self) -> float:
        return self.torque_nm / (self.ring_od_mm / 2 / 1000)

    @property
    def preload_needed_n(self) -> float:
        return self.tangential_n / FRICTION_MU * FRICTION_SAFETY

    def torque_limit_nm(self) -> float:
        """지금 압착력으로 전달할 수 있는 링 토크의 상한."""
        return self.preload_n * FRICTION_MU * (self.ring_od_mm / 2 / 1000)


# ── 회전 관성 ───────────────────────────────────────────────────────────
def flip_inertia_kgm2() -> float:
    """반전축이 실제로 돌리는 관성 — 링 2 + 조·패드·캐리어 + 패널.

    **포탈·크로스빔·캐리지는 돌지 않는다.** 크레인 모델의 인양 하한
    2,500 kg 은 조립체를 통째로 드는 무게이지 회전 관성의 근거가 아니다.
    """
    a = fabrication.assembly("PV-FAB-A03")
    by = {p.tag: p.weight_kg() for p in a.parts}
    r_ring = kinematics.RING_R_MM / 1000
    r_jaw = kinematics.JAW_CLOSED_Z_MM / 1000
    rings = 2 * by["BFC-RNG-01"] * r_ring ** 2
    jaws = (2 * by["BFC-CLP-01"] + 4 * by["BFC-PAD-01"] + 4 * by["BFC-JCR-01"]
            + 4 * by["BFC-JGP-01"]) * r_jaw ** 2
    panel = PANEL_KG * (kinematics.PANEL_MM[1] / 1000) ** 2 / 12
    return rings + jaws + panel


def flip_rotating_kg() -> float:
    """반전축이 돌리는 질량 (kg)."""
    a = fabrication.assembly("PV-FAB-A03")
    by = {p.tag: p.weight_kg() for p in a.parts}
    return (2 * by["BFC-RNG-01"] + 2 * by["BFC-CLP-01"] + 4 * by["BFC-PAD-01"]
            + 4 * by["BFC-JCR-01"] + 4 * by["BFC-JGP-01"] + PANEL_KG)


def lift_moving_kg() -> float:
    """승강 캐리지가 움직이는 질량 (kg) — 레일빔·엔드빔·LM 블록·분리헤드·패널."""
    a = fabrication.assembly("PV-FAB-A03")
    by = {p.tag: p.weight_kg() for p in a.parts}
    return (2 * by["BFC-CAR-01"] + 2 * by["BFC-CAR-02"] + 2 * by["BFC-CAR-03"]
            + 4 * by["BFC-CAR-04"] + 2 * by["BFC-CAR-05"]
            + by["BFC-SEP-01"] + 4 * by["BFC-SEP-02"] + 2 * by["BFC-SEP-04"]
            + 40.0 + PANEL_KG)          # 40 = LM 블록 8 · 볼너트 2 · 진공컵 4 (상용품 개략)


# ── 축 ──────────────────────────────────────────────────────────────────
def _lift_segment() -> tuple[float, float]:
    """가장 빠른 승강 구간 (행정 mm, 시각 s) — 승강과 하강 중 빠른 쪽."""
    up = (kinematics.FLIP_AXIS_MM - (kinematics.PICK_FACE_MM + kinematics.SEPARATION_MM),
          kinematics.PATH[2][1] - kinematics.PATH[2][0])
    down = (kinematics.FLIP_AXIS_MM - kinematics.HANDOVER_MM,
            kinematics.PATH[4][1] - kinematics.PATH[4][0])
    return up if up[0] / up[1] >= down[0] / down[1] else down


#: 승강 볼스크루 리드 (mm). **16 이다** (표준 계열 5·10·16·20·25·32 중).
#:
#: 리드 10 + i=10 감속기로는 모터가 25,000 rpm 이어야 했다 — 서보는 3,000 rpm
#: 급이다. 감속기를 빼고 직결하면 리드가 회전수와 토크를 동시에 정한다:
#:
#: * 리드 10 직결 — 3,793 rpm. 정격을 넘어 연속 토크가 안 나온다.
#: * 리드 20 직결 — 1,896 rpm 은 좋은데 피크 토크 10.6 N·m 가 1.1 kW 서보의
#:   순시 한계(3 × 3.5 = 10.5)를 1 % 넘는다. 여유가 없다.
#: * **리드 16 직결 — 2,370 rpm · 실효 2.8 · 피크 8.5.** 둘 다 안에 든다.
#:
#: 자립 제동은 리드와 무관하게 브레이크가 한다 — 볼스크루는 어느 리드에서도
#: 자립하지 않는다.
LIFT_LEAD_MM = 16.0

#: 반전 구동 롤러 지름 (mm) — 제작 패키지 BFC-DRV-01.
FLIP_ROLLER_OD_MM = 160.0

#: 반전 감속비. 롤러 rpm × 이 값이 모터 rpm 이다.
#:
#: **100 이 아니라 50 이다.** i=100 이면 모터가 4,950 rpm 으로 정격(3,000)을
#: 한참 넘어 최대회전수에 붙는다. 필요 토크는 관성에서 97 N·m 뿐이라 감속을
#: 줄여도 남는다 — 50 이면 2,475 rpm 으로 정격 안에 들어온다.
FLIP_RATIO = 50.0

#: 마찰 롤러 압착력 (N). **사양이다** — 이 값이 없으면 전달 토크가 정해지지 않는다.
#: 필요 압착력(관성 토크 ÷ 링 반지름 ÷ μ × 안전율)을 표준 스프링·실린더로 올린 값.
FLIP_PRELOAD_N = 400.0


def ballscrews() -> tuple[Ballscrew, ...]:
    stroke, seconds = _lift_segment()
    return (Ballscrew("AXIS-BFC-Z", LIFT_LEAD_MM, 1.0, 2, stroke, seconds, lift_moving_kg()),)


def friction_drives() -> tuple[FrictionDrive, ...]:
    ring_od = 2 * (kinematics.RING_R_MM + kinematics.RING_TUBE_MM)
    flip = kinematics.PATH[3]
    return (FrictionDrive("AXIS-BFC-R", ring_od, FLIP_ROLLER_OD_MM, FLIP_RATIO,
                          0.5, flip[1] - flip[0], flip_inertia_kgm2(), FLIP_PRELOAD_N),)


# ── 검산 ────────────────────────────────────────────────────────────────
def speed_checks() -> dict[str, tuple[float, bool]]:
    """축마다 (모터 최고 rpm, 최대회전수 안인가)."""
    out: dict[str, tuple[float, bool]] = {}
    for b in ballscrews():
        out[b.axis] = (round(b.motor_rpm), b.motor_rpm <= SERVO_MAX_RPM)
    for f in friction_drives():
        out[f.axis] = (round(f.motor_rpm), f.motor_rpm <= SERVO_MAX_RPM)
    return out


def rated_torque_nm(axis: str) -> float:
    """서보 정격 토크 (정격 회전수까지 일정)."""
    kw = {a.tag: a.rated_kw for a in servos.SERVO_AXES}[axis]
    return kw * 1000 / (2 * math.pi * SERVO_RATED_RPM / 60)


def _cycle_s() -> float:
    """한 주기의 길이 (s) — 듀티를 여기서 낸다. 정본은 `campaign` 이다."""
    from . import campaign
    return campaign.release_takt_s()


def torque_checks() -> dict[str, tuple[float, float, float, bool]]:
    """축마다 (실효 토크, 피크 토크, 정격 토크, 만족하는가).

    판정은 **실효 ≤ 정격** 이고 **피크 ≤ 정격 × 3** 이다. 정속 토크를 정격과
    바로 견주면 안 된다 — 중력축은 듀티가 낮다.
    """
    out: dict[str, tuple[float, float, float, bool]] = {}
    cycle = _cycle_s()
    for b in ballscrews():
        rated = rated_torque_nm(b.axis)
        rms, peak = b.rms_torque_nm(cycle), b.peak_torque_nm
        out[b.axis] = (round(rms, 2), round(peak, 2), round(rated, 2),
                       rms <= rated and peak <= rated * SERVO_PEAK_FACTOR)
    for f in friction_drives():
        rated = rated_torque_nm(f.axis)
        need_motor = f.torque_nm / (f.ratio * (f.ring_od_mm / f.roller_od_mm) * 0.9)
        out[f.axis] = (round(need_motor, 2), round(need_motor, 2), round(rated, 2),
                       need_motor <= rated and f.torque_nm <= f.torque_limit_nm())
    return out


def preload_is_specified() -> dict[str, tuple[float, float, bool]]:
    """마찰 구동마다 (지정 압착력, 필요 압착력, 충분한가)."""
    return {f.axis: (f.preload_n, round(f.preload_needed_n), f.preload_n >= f.preload_needed_n)
            for f in friction_drives()}


def summary() -> dict[str, object]:
    b = ballscrews()[0]
    f = friction_drives()[0]
    return {
        "lift_mm_s": round(b.mean_mm_s),
        "lift_screw_rpm": round(b.screw_rpm),
        "lift_motor_rpm": round(b.motor_rpm),
        "lift_torque_nm": round(b.motor_torque_nm, 2),
        "lift_rms_nm": round(b.rms_torque_nm(_cycle_s()), 2),
        "lift_peak_nm": round(b.peak_torque_nm, 2),
        "lift_rated_nm": round(rated_torque_nm(b.axis), 2),
        "flip_inertia": round(f.inertia_kgm2, 1),
        "flip_rotating_kg": round(flip_rotating_kg()),
        "flip_torque_nm": round(f.torque_nm),
        "flip_motor_rpm": round(f.motor_rpm),
        "flip_preload_n": f.preload_n,
        "flip_preload_needed_n": round(f.preload_needed_n),
    }
