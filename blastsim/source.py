"""폭원(발파공) 하중 모델 — 등가공동(equivalent cavity) 방식.

왜 등가공동인가
---------------
천공경은 76 mm 수준인데 진동 전파 해석에 쓰는 격자간격은 1~2 m 이다.
공벽을 직접 이산화하려면 격자간격을 mm 급으로 줄여야 하므로(입자 10^12개) 불가능하다.
표준적 해법은 '탄성 거동이 시작되는 반경'에 등가 압력을 가하는 것이다.

압력 반경감쇠 (2단계)
    파쇄대 (r_h -> r_c) :  P ∝ r^(-a1),  a1 ≈ 2.0,  r_c ≈ 4 * r_h
    탄성역 (r_c -> r_eq):  P ∝ r^(-a2),  a2 ≈ 1.0

    P_eq = eta * P_b * (r_h/r_c)^a1 * (r_c/r_eq)^a2

**격자 무관성**: a2 = 1 이면 등가공동에 작용하는 단위길이당 총 반경력
    F' = P_eq * 2*pi*r_eq = eta * P_b * (r_h/r_c)^a1 * r_c * 2*pi  = const
로 r_eq(=격자간격)에 무관하다. 즉 격자를 바꿔도 폭원 세기가 유지된다.

eta 는 폭발에너지 전달효율(가스 누출, 전색 불량, 파쇄 소산 등)로 실측 진동을
이용해 보정하는 계수이다 (empirical.calibrate_efficiency 참조).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .explosives import Explosive
from .lattice import Lattice
from .pattern import BlastHole, BlastPattern


@dataclass
class SourceConfig:
    """폭원 모델 파라미터."""

    crush_ratio: float = 4.0     # r_c / r_h — 파쇄대 반경비
    alpha_crush: float = 2.0     # 파쇄대 압력 감쇠지수
    alpha_elastic: float = 1.0   # 탄성역 압력 감쇠지수 (1.0 이면 격자무관)
    efficiency: float = 1.0      # 에너지 전달효율 eta (실측 보정 계수)
    cavity_factor: float = 1.0   # 등가공동 반경 r_eq = cavity_factor * 격자간격
    elastic_core: float = 2.5    # 본드파괴 금지 반경 = elastic_core * r_eq


class BlastSource:
    """발파패턴 전체를 격자 위의 시간의존 절점하중으로 변환."""

    def __init__(
        self,
        lattice: Lattice,
        pattern: BlastPattern,
        explosive: Explosive,
        config: SourceConfig | None = None,
    ) -> None:
        self.lat = lattice
        self.pattern = pattern
        self.exp = explosive
        self.cfg = config or SourceConfig()
        self.r_eq = self.cfg.cavity_factor * lattice.d
        self._build()

    # ---- 공별 등가압력 ---------------------------------------------------
    def equivalent_pressure(self, hole: BlastHole) -> float:
        """등가공동 벽면 최대압력 P_eq [Pa]."""
        r_h = hole.hole_dia / 2.0
        r_c = self.cfg.crush_ratio * r_h
        p_b = self.exp.borehole_pressure(hole.charge_dia, hole.hole_dia)
        p = p_b * (r_h / r_c) ** self.cfg.alpha_crush
        if self.r_eq > r_c:
            p *= (r_c / self.r_eq) ** self.cfg.alpha_elastic
        return self.cfg.efficiency * p

    def crush_radius(self, hole: BlastHole) -> float:
        return self.cfg.crush_ratio * hole.hole_dia / 2.0

    # ---- 절점하중 구성 ---------------------------------------------------
    def _build(self) -> None:
        """각 공마다 (입자인덱스, 하중벡터, 기폭시각) 을 미리 계산."""
        self.hole_idx: list[np.ndarray] = []
        self.hole_load: list[np.ndarray] = []   # 최대압력 시 절점력 [N]
        self.hole_delay: list[float] = []
        self.hole_pressure: list[float] = []
        core: list[np.ndarray] = []

        pos = self.lat.pos
        for h in self.pattern.holes:
            if h.charge_length <= 0.0 or h.charge_weight <= 0.0:
                continue
            dx = pos[:, 0] - h.x
            dy = pos[:, 1] - h.y
            r = np.hypot(dx, dy)
            in_col = (pos[:, 2] >= h.z_bottom) & (pos[:, 2] <= h.charge_top)
            sel = in_col & (r > 1e-9) & (r <= self.r_eq * 1.05)
            idx = np.flatnonzero(sel)
            if idx.size == 0:   # 격자가 성기면 가장 가까운 기둥으로 대체
                idx = np.flatnonzero(in_col & (r <= self.lat.d * 1.5))
                if idx.size == 0:
                    continue

            # 반경방향 단위벡터 (수평면 내)
            rr = np.maximum(r[idx], 1e-9)
            e = np.zeros((idx.size, 3))
            e[:, 0] = dx[idx] / rr
            e[:, 1] = dy[idx] / rr

            # 공동 표면적 배분: 총 반경력 = P_eq * 2*pi*r_eq * L_charge
            # 격자에 걸린 절점 수가 아니라 '실제 장약장'을 쓴다. 그래야 격자를
            # 성기게 해도 폭원이 주는 총 임펄스가 보존된다.
            p_eq = self.equivalent_pressure(h)
            f_total = p_eq * 2.0 * math.pi * self.r_eq * h.charge_length

            load = e * (f_total / idx.size)
            # 순 힘(net force) 제거 — 모델 전체가 밀려나는 인위적 강체운동 방지
            load -= load.mean(axis=0, keepdims=True)

            self.hole_idx.append(idx.astype(np.int32))
            self.hole_load.append(load)
            self.hole_delay.append(h.delay)
            self.hole_pressure.append(p_eq)

            # 탄성코어: 폭원 근방 본드는 파괴 금지 (자유비산 방지)
            core.append(self.lat.cylinder_indices(
                h.x, h.y, h.z_bottom - self.lat.d, h.charge_top + self.lat.d,
                self.cfg.elastic_core * self.r_eq))

        if core:
            self.core_idx = np.unique(np.concatenate(core))
            self.lat.protect(self.core_idx)
        else:
            self.core_idx = np.empty(0, dtype=np.int64)

    # ---- 시간별 하중 -----------------------------------------------------
    # 압력이 사실상 0 이 되는 시점 (exp(-12) ~ 6e-6)
    TAIL = 12.0

    def apply(self, force: list, t: float) -> None:
        """시각 t 의 폭원 하중을 force 에 누적.

        force 는 성분별 평탄배열 3개 [(N,), (N,), (N,)] 이다 (솔버 내부 표현).
        """
        for idx, load, t0 in zip(self.hole_idx, self.hole_load, self.hole_delay):
            dt = t - t0
            if dt <= 0.0 or dt > self.TAIL * self.exp.decay_time:
                continue
            f = float(self.exp.pressure_history(np.array([dt]))[0])
            if f <= 1e-6:
                continue
            for c in range(3):
                np.add.at(force[c], idx, load[:, c] * f)

    @property
    def active_window(self) -> tuple[float, float]:
        """폭원이 작동하는 시간 구간 [s]."""
        if not self.hole_delay:
            return (0.0, 0.0)
        return (min(self.hole_delay), max(self.hole_delay) + self.TAIL * self.exp.decay_time)

    def summary(self) -> str:
        h = self.pattern.holes[0]
        p_b = self.exp.borehole_pressure(h.charge_dia, h.hole_dia)
        n_node = sum(i.size for i in self.hole_idx)
        f_lo, f_hi = self.exp.corner_frequencies
        f_grid = self.lat.max_frequency
        lost = self.exp.energy_fraction_above(f_grid)
        note = (f"\n  폭원 평탄대역 {f_lo:.0f}~{f_hi:.0f} Hz,  격자 해상한계 {f_grid:.0f} Hz"
                f"  ->  격자가 버리는 방사에너지 {lost * 100:.0f}%")
        if lost > 0.5:
            note += ("\n  [!] 폭원 에너지의 절반 이상이 격자 상한을 넘습니다. 절대 진폭이 과소평가되며"
                     "\n      보정(eta)이 필수입니다. 격자를 조밀하게 하면 개선됩니다.")
        return (
            f"[폭원] 등가공동 반경 r_eq = {self.r_eq:.2f} m, "
            f"파쇄대 반경 r_c = {self.crush_radius(h) * 100:.1f} cm\n"
            f"  공내압 Pb = {p_b / 1e6:,.0f} MPa  ->  등가압력 P_eq = "
            f"{self.hole_pressure[0] / 1e6:.1f} MPa  (eta = {self.cfg.efficiency:.2f})\n"
            f"  하중 절점 {n_node:,}개 / {len(self.hole_idx)}공, "
            f"탄성코어 {self.core_idx.size:,}입자 (r<{self.cfg.elastic_core * self.r_eq:.1f} m),  "
            f"작동구간 {self.active_window[0] * 1e3:.0f}~{self.active_window[1] * 1e3:.0f} ms"
            + note
        )
