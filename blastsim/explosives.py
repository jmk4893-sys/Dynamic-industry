"""폭약 물성 데이터베이스 및 공내압(borehole pressure) 산정.

이론 배경
---------
1) 폭굉압 (Chapman-Jouguet)
       Pd = rho_e * VOD^2 / (1 + gamma)
   gamma 는 폭굉가스의 단열지수(2.5~3.0), 상용폭약은 gamma≈3 -> Pd ≈ rho*VOD^2/4

2) 완전결합(fully coupled) 공내압
       Pb ≈ 0.5 * Pd        (가스가 공극을 채우며 팽창하는 과정 반영)

3) 디커플링(decoupling) 보정 — 장약경 dc < 천공경 dh 인 경우
       Pb = 0.5 * Pd * (dc/dh)^(2*gamma_exp),  gamma_exp ≈ 1.3  (지수 2.6)
   조절발파(프리스플리팅, 스무스블라스팅)의 진동저감 효과를 재현한다.

4) 압력-시간 이력 : 이중지수 함수
       P(t) = Pb * xi * (exp(-t/td) - exp(-t/tr))
   tr(상승시간), td(감쇠시간)가 폭원의 탁월주파수를 결정한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Explosive:
    """폭약 물성.

    Attributes
    ----------
    name        : 제품/종류 이름
    density     : 비중(장약밀도) [g/cm^3]
    vod         : 폭속 VOD [m/s]
    rws         : 상대중량위력 (ANFO=100)
    rbs         : 상대용적위력 (ANFO=100)
    energy      : 폭발열 [MJ/kg]
    gamma       : 폭굉가스 단열지수
    rise_time   : 공내압 상승시간 [s]
    decay_time  : 공내압 감쇠시간 [s]
    note        : 용도 메모
    """

    name: str
    density: float
    vod: float
    rws: float = 100.0
    rbs: float = 100.0
    energy: float = 3.7
    gamma: float = 3.0
    rise_time: float = 0.30e-3
    decay_time: float = 4.0e-3
    note: str = ""

    # ---- 압력 ------------------------------------------------------------
    @property
    def density_si(self) -> float:
        """장약밀도 [kg/m^3]."""
        return self.density * 1000.0

    @property
    def detonation_pressure(self) -> float:
        """폭굉압 Pd [Pa]."""
        return self.density_si * self.vod ** 2 / (1.0 + self.gamma)

    def borehole_pressure(self, charge_dia: float, hole_dia: float) -> float:
        """공내압 Pb [Pa]. 디커플링 지수 2*1.3 = 2.6 적용."""
        coupling = min(1.0, charge_dia / hole_dia)
        return 0.5 * self.detonation_pressure * coupling ** 2.6

    def decoupling_index(self, charge_dia: float, hole_dia: float) -> float:
        """디커플링 지수 DI = dh/dc (1.0 = 완전결합)."""
        return hole_dia / charge_dia

    # ---- 시간 이력 -------------------------------------------------------
    def pressure_history(self, t: np.ndarray) -> np.ndarray:
        """정규화 압력 이력 f(t) (최대값 1.0). t<0 이면 0."""
        tr, td = self.rise_time, self.decay_time
        t = np.asarray(t, dtype=float)
        # 최대값이 1이 되도록 정규화 계수 xi 계산
        t_peak = math.log(td / tr) / (1.0 / tr - 1.0 / td)
        xi = 1.0 / (math.exp(-t_peak / td) - math.exp(-t_peak / tr))
        f = xi * (np.exp(-np.clip(t, 0, None) / td) - np.exp(-np.clip(t, 0, None) / tr))
        return np.where(t > 0.0, f, 0.0)

    @property
    def dominant_frequency(self) -> float:
        """폭원 탁월주파수 근사 [Hz] — 상승시간 기반."""
        return 1.0 / (4.0 * self.rise_time)

    @property
    def corner_frequencies(self) -> tuple[float, float]:
        """방사 속도 스펙트럼이 평탄한 구간 [Hz].

        P(w) ∝ (b-a)/((a+iw)(b+iw)),  a=1/td, b=1/tr 이고 원방 입자속도는
        dP/dt 에 비례하므로 속도 스펙트럼 w*P(w) 는 a~b 구간에서 평탄하다.
        """
        return (1.0 / (2.0 * math.pi * self.decay_time),
                1.0 / (2.0 * math.pi * self.rise_time))

    def energy_fraction_above(self, freq: float) -> float:
        """폭원 방사에너지 중 주파수 freq 를 넘는 비율 (0~1).

        격자가 해상할 수 있는 상한을 넘는 에너지는 수치분산·감쇠로 사라지므로,
        이 값이 크면 해석이 폭원 에너지의 상당 부분을 버리고 있다는 뜻이다.
        """
        dt = self.rise_time / 40.0
        t = np.arange(0.0, 30.0 * self.decay_time, dt)
        p = self.pressure_history(t)
        vel = np.gradient(p, dt)                 # 원방 속도 ∝ dP/dt
        amp = np.abs(np.fft.rfft(vel)) ** 2
        f = np.fft.rfftfreq(t.size, dt)
        total = amp.sum()
        return float(amp[f > freq].sum() / total) if total > 0 else 0.0

    # ---- 장약량 ----------------------------------------------------------
    def charge_length(self, weight: float, charge_dia: float) -> float:
        """장약량 W[kg] 을 장약경 dc[m] 의 기둥으로 환산한 장약장 [m]."""
        area = math.pi * charge_dia ** 2 / 4.0
        return weight / (self.density_si * area)

    def charge_weight(self, length: float, charge_dia: float) -> float:
        """장약장 [m] -> 장약량 [kg]."""
        area = math.pi * charge_dia ** 2 / 4.0
        return self.density_si * area * length

    def anfo_equivalent(self, weight: float) -> float:
        """ANFO 환산 장약량 [kg] — 경험식 비교 시 사용."""
        return weight * self.rws / 100.0

    def summary(self, charge_dia: float = 0.070, hole_dia: float = 0.076) -> str:
        pb = self.borehole_pressure(charge_dia, hole_dia)
        return (
            f"[폭약] {self.name}\n"
            f"  비중 = {self.density:.2f} g/cc,  VOD = {self.vod:,.0f} m/s,  "
            f"RWS = {self.rws:.0f}, RBS = {self.rbs:.0f}\n"
            f"  폭굉압 Pd = {self.detonation_pressure / 1e9:.2f} GPa,  "
            f"공내압 Pb = {pb / 1e9:.2f} GPa (DI={hole_dia / charge_dia:.2f})\n"
            f"  상승시간 = {self.rise_time * 1e3:.2f} ms, 탁월주파수 ≈ {self.dominant_frequency:.0f} Hz"
            + (f"\n  용도: {self.note}" if self.note else "")
        )


# ---------------------------------------------------------------------------
# 폭약 데이터베이스 (국내 유통 상용폭약 대표값)
# ---------------------------------------------------------------------------
EXPLOSIVE_DB: dict[str, Explosive] = {
    "anfo": Explosive(
        "초유폭약 ANFO", density=0.85, vod=3200, rws=100, rbs=100, energy=3.7,
        rise_time=0.50e-3, decay_time=6.0e-3,
        note="벌크 대량발파, 저비용. 내수성 없음 — 함수공 사용 불가"),
    "heavy_anfo": Explosive(
        "중유폭약 Heavy ANFO", density=1.25, vod=4500, rws=95, rbs=140, energy=3.5,
        rise_time=0.40e-3, decay_time=5.0e-3,
        note="ANFO+에멀젼 혼합, 벤치발파 주력"),
    "emulsion": Explosive(
        "에멀젼폭약 (뉴마이트 등)", density=1.20, vod=5500, rws=88, rbs=125, energy=3.2,
        rise_time=0.30e-3, decay_time=4.0e-3,
        note="내수성 우수, 터널·벤치 범용"),
    "dynamite": Explosive(
        "함수폭약/다이너마이트", density=1.45, vod=6200, rws=115, rbs=165, energy=4.3,
        rise_time=0.20e-3, decay_time=3.0e-3,
        note="고위력, 심발공·경암 적용"),
    "precision": Explosive(
        "정밀폭약 (조절발파용)", density=1.10, vod=4000, rws=80, rbs=95, energy=2.9,
        rise_time=0.60e-3, decay_time=6.0e-3,
        note="스무스블라스팅·프리스플리팅. 디커플링 장약 전제"),
    "low_vod": Explosive(
        "미진동 파쇄약 (저폭속)", density=1.00, vod=2000, rws=55, rbs=60, energy=2.0,
        rise_time=1.20e-3, decay_time=10.0e-3,
        note="보안물건 근접구간, 진동 저감 최우선"),
    "slurry": Explosive(
        "함수폭약 슬러리", density=1.15, vod=4200, rws=92, rbs=115, energy=3.3,
        rise_time=0.45e-3, decay_time=5.5e-3,
        note="내수성, 중간위력"),
}


def get_explosive(key: str) -> Explosive:
    if key not in EXPLOSIVE_DB:
        raise KeyError(f"알 수 없는 폭약 '{key}'. 사용 가능: {list(EXPLOSIVE_DB)}")
    e = EXPLOSIVE_DB[key]
    return Explosive(**{**e.__dict__})
