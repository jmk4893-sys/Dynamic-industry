"""3단 회로의 과도응답 수치해석 (기동 시뮬레이션).

정상상태 물질수지(``circuit.solve_circuit``)는 회로가 **이미 수렴한 뒤**
를 계산한다. 이 모듈은 빈 셀에서 급광을 넣기 시작한 순간부터 정상상태에
도달할 때까지를 시간적분한다 — 기동 후 얼마 만에 성능 보증값을 잴 수
있는지, 순환류가 몇 τ 만에 안정되는지가 여기서 나온다.

모델: 각 셀을 완전혼합조(CSTR)로 보고, 성분별 셀 내 재고 M (kg) 에 대해

    dM/dt = F_in − M/τ_residence − k_eff · M

를 4차 Runge-Kutta 로 적분한다. k_eff 는 정상상태 해에서 역산한 성분별
유효 포집 속도상수 k = R / (τ (1−R)) 로, 정상상태에 도달하면 수렴 해와
**정확히 같은** 물질수지가 되도록 만든다 (검증 테스트가 이를 확인한다).
회로 연결(러퍼 정광→클리너, 러퍼 미광→스캐빈저, 스캐빈저 정광·클리너
미광→러퍼)은 정상상태와 동일하다.

표준 라이브러리만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .circuit import CircuitResult, UnitResult


def _effective_rate_1_min(unit: UnitResult, component: str) -> float:
    """정상상태 단 회수율에서 유효 속도상수 k (1/min) 를 역산한다.

    CSTR: R = kτ/(1+kτ)  →  k = R / (τ(1−R))
    """
    r = unit.recovery(component)
    if r >= 1.0:
        return 1e6
    return r / (unit.residence_min * (1.0 - r))


@dataclass(frozen=True)
class TransientResult:
    """기동 시뮬레이션 결과."""

    times_min: tuple[float, ...]
    recovery_ag: tuple[float, ...]          # 순시 회로 Ag 회수율
    circulating_load: tuple[float, ...]     # 순시 순환부하
    concentrate_ag_kg_h: tuple[float, ...]  # 최종 정광 Ag 유량
    steady_recovery_ag: float               # 정상상태 해 (수렴 검증 기준)

    @property
    def time_to_95pct_min(self) -> float:
        """회로 Ag 회수율이 정상상태의 95 % 에 처음 도달하는 시각 (분)."""
        target = 0.95 * self.steady_recovery_ag
        for t, r in zip(self.times_min, self.recovery_ag):
            if r >= target:
                return t
        return float("inf")

    @property
    def time_to_99pct_min(self) -> float:
        target = 0.99 * self.steady_recovery_ag
        for t, r in zip(self.times_min, self.recovery_ag):
            if r >= target:
                return t
        return float("inf")

    @property
    def final_recovery_ag(self) -> float:
        return self.recovery_ag[-1]


def simulate_startup(
    result: CircuitResult,
    duration_min: float = 120.0,
    dt_min: float = 0.02,
    sample_every_min: float = 0.5,
) -> TransientResult:
    """빈 셀 기동부터 duration_min 까지 회로 과도응답을 적분한다.

    Args:
        result: ``solve_circuit`` 의 수렴 해 — 여기서 회로 연결과 유효
            속도상수를 가져온다.
        duration_min: 적분 구간 (분).
        dt_min: RK4 시간 간격 (분).
        sample_every_min: 기록 간격 (분).
    """
    units = {"R": result.rougher, "S": result.scavenger, "C": result.cleaner}
    comps = tuple(result.new_feed.components)
    tau = {u: units[u].residence_min for u in units}
    k = {
        (u, c): _effective_rate_1_min(units[u], c)
        for u in units
        for c in comps
    }
    fresh = {c: result.new_feed.component_tph(c) * 1000.0 / 60.0 for c in comps}  # kg/min

    # 상태: 셀별·성분별 재고 (kg). 기동 시 빈 셀.
    state = {(u, c): 0.0 for u in units for c in comps}

    def derivs(s: dict) -> dict:
        # 셀별 유출 (kg/min)
        out_tail = {(u, c): s[(u, c)] / tau[u] for u in units for c in comps}
        out_conc = {(u, c): k[(u, c)] * s[(u, c)] for u in units for c in comps}
        d = {}
        for c in comps:
            feed_r = fresh[c] + out_conc[("S", c)] + out_tail[("C", c)]
            feed_s = out_tail[("R", c)]
            feed_c = out_conc[("R", c)]
            d[("R", c)] = feed_r - out_tail[("R", c)] - out_conc[("R", c)]
            d[("S", c)] = feed_s - out_tail[("S", c)] - out_conc[("S", c)]
            d[("C", c)] = feed_c - out_tail[("C", c)] - out_conc[("C", c)]
        return d

    def add_scaled(s, d, h):
        return {key: s[key] + h * d[key] for key in s}

    times, rec, circ, conc_ag = [], [], [], []
    steady = result.recovery("Ag")
    t = 0.0
    next_sample = 0.0
    steps = round(duration_min / dt_min)
    for _ in range(steps + 1):
        if t >= next_sample - 1e-9:
            # 순시 회로 성능 — 최종 정광(클리너 정광) / 신급광
            ag_conc = k[("C", "Ag")] * state[("C", "Ag")]
            rec.append(ag_conc / fresh["Ag"] if fresh["Ag"] else 0.0)
            recycle = sum(
                k[("S", c)] * state[("S", c)] + state[("C", c)] / tau["C"]
                for c in comps
            )
            new_feed = sum(fresh.values())
            circ.append(recycle / new_feed if new_feed else 0.0)
            conc_ag.append(ag_conc * 60.0)  # kg/h
            times.append(t)
            next_sample += sample_every_min
        # RK4
        k1 = derivs(state)
        k2 = derivs(add_scaled(state, k1, dt_min / 2.0))
        k3 = derivs(add_scaled(state, k2, dt_min / 2.0))
        k4 = derivs(add_scaled(state, k3, dt_min))
        state = {
            key: state[key]
            + dt_min / 6.0 * (k1[key] + 2.0 * k2[key] + 2.0 * k3[key] + k4[key])
            for key in state
        }
        t += dt_min

    return TransientResult(
        times_min=tuple(times),
        recovery_ag=tuple(rec),
        circulating_load=tuple(circ),
        concentrate_ag_kg_h=tuple(conc_ag),
        steady_recovery_ag=steady,
    )
