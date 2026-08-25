"""세척수 bias 방식 연속 부선조(RFC 계열) 사이징.

참고문헌 [2] 의 연속 정상상태 실증은 기계식 셀이 아니라 **세척수(wash water)
로 양(+)의 bias 를 거는 수직 부선조**에서 수행됐다. 이 장치의 설계 변수는
체적이 아니라 **단면적 기준 flux** 다.

    Jf = Q_feed / A     급광 flux      (실증 2.0 cm/s)
    Jg = Q_air  / A     기체 flux      (실증 2.0 cm/s)
    Jw = Q_wash / A     세척수 flux    (실증 0.81 cm/s)
    Jb = Jw - Jo        bias flux      (양수면 거품층을 통과하는 하향류)

거품층을 아래로 지나는 순 하향류가 동반 맥석(entrainment)을 씻어내리므로,
기계식 셀의 러퍼+클리너 2단이 하는 일을 1단에서 해낸다. 실증에서 맥석
회수율은 0.64 % 로 회분식 기계식 셀(2.2 %)의 약 1/3.5 였다.

기액 체류시간은 라이저 체적을 급광+공기 유량으로 나눈 값이며, 실증값은
1 분이다. 즉 필요한 것은 '큰 체적'이 아니라 '충분한 단면적'이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import references as ref
from .sizing import select_motor_kw

#: 제작 표준 동체 내경 계열 (mm).
STANDARD_DIAMETERS_MM = (150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 1000)


def _round_up_diameter(diameter_m: float) -> float:
    for d in STANDARD_DIAMETERS_MM:
        if d / 1000.0 >= diameter_m - 1e-9:
            return d / 1000.0
    raise ValueError("표준 계열을 초과하는 지름 — 다수 병렬 검토 필요")


def slurry_volumetric_flow_m3h(dry_tph: float, solids_sg: float, solids_wt: float) -> float:
    """건조 고체 유량과 고체 농도로부터 슬러리 체적유량 (m3/h)."""
    if not 0.0 < solids_wt < 1.0:
        raise ValueError("solids_wt 는 0~1 사이여야 함")
    water_tph = dry_tph * (1.0 - solids_wt) / solids_wt
    return dry_tph / solids_sg + water_tph


@dataclass(frozen=True)
class RfcDesign:
    """연속 부선조 1기의 확정 사양.

    Attributes:
        tag: 기기 번호.
        diameter_m: 동체 내경 (원형 환산).
        design_solids_wt: 사이징 기준 고체 질량분율.
        riser_height_m: 라이저(기액 접촉부) 높이 — 기액 체류시간에서 역산.
        bias_flux_cm_s: 설계 bias flux (양수 = 거품층 하향 순유량).
    """

    tag: str
    duty: str
    diameter_m: float
    design_solids_wt: float
    design_dry_tph: float
    feed_flux_cm_s: float
    air_flux_cm_s: float
    wash_water_flux_cm_s: float
    bias_flux_cm_s: float
    gas_liquid_residence_min: float
    riser_height_m: float
    inclined_channel_angle_deg: float
    inclined_channel_spacing_mm: float
    solids_sg: float

    @property
    def area_m2(self) -> float:
        return math.pi * self.diameter_m**2 / 4.0

    def _flux_to_m3h(self, cm_s: float) -> float:
        return cm_s / 100.0 * self.area_m2 * 3600.0

    @property
    def feed_m3h(self) -> float:
        return self._flux_to_m3h(self.feed_flux_cm_s)

    @property
    def air_m3h(self) -> float:
        return self._flux_to_m3h(self.air_flux_cm_s)

    @property
    def wash_water_m3h(self) -> float:
        return self._flux_to_m3h(self.wash_water_flux_cm_s)

    @property
    def overflow_water_m3h(self) -> float:
        """정광(거품)과 함께 넘어가는 물 — 세척수에서 bias 만큼 뺀 값."""
        return self._flux_to_m3h(self.wash_water_flux_cm_s - self.bias_flux_cm_s)

    @property
    def riser_volume_m3(self) -> float:
        return self.area_m2 * self.riser_height_m

    @property
    def capacity_tph(self) -> float:
        """설계 flux·고체농도에서의 건조 고체 처리능력 (t/h)."""
        return self.capacity_at_solids(self.design_solids_wt)

    def capacity_at_solids(self, solids_wt: float) -> float:
        """급광 flux 를 유지한 채 고체 농도만 바꿨을 때의 처리능력 (t/h).

        슬러리 체적유량이 고정이므로 ``Q = m/SG + m(1-w)/w`` 를 m 에 대해 푼다.
        """
        if not 0.0 < solids_wt < 1.0:
            raise ValueError("solids_wt 는 0~1 사이여야 함")
        return self.feed_m3h / (1.0 / self.solids_sg + (1.0 - solids_wt) / solids_wt)

    def solids_required_for(self, dry_tph: float) -> float:
        """지정 처리량을 내려면 필요한 고체 농도 (질량분율)."""
        q = self.feed_m3h
        if dry_tph <= 0 or q <= dry_tph / self.solids_sg:
            raise ValueError("이 유량에서는 불가능한 처리량")
        water = q - dry_tph / self.solids_sg
        return dry_tph / (dry_tph + water)

    def operating_point(self, dry_tph: float, solids_wt: float | None = None) -> "RfcOperatingPoint":
        """지정 처리량에서의 운전 조건.

        ``solids_wt`` 를 생략하면 실증 flux와 1분 기액 체류시간을 보존하도록
        슬러리 유량을 고정하고 고체 농도를 조절한다. 고정 높이 장치에서 세 flux를
        함께 낮추면 체류시간은 증가하므로, 이를 '상사 운전'으로 취급하면 안 된다.

        ``solids_wt`` 를 명시한 경우에는 해당 농도에서 실제 flux와 체류시간을
        계산해 반환한다. 이 모드는 파일럿 검증 없이 기준 성능을 보증하지 않는다.
        """
        if solids_wt is None:
            w = self.solids_required_for(dry_tph)
            q = self.feed_m3h
            ratio = 1.0
        else:
            w = solids_wt
            q = slurry_volumetric_flow_m3h(dry_tph, self.solids_sg, w)
            ratio = q / self.feed_m3h
        return RfcOperatingPoint(
            design=self,
            dry_tph=dry_tph,
            solids_wt=w,
            turndown_ratio=ratio,
            feed_m3h=q,
            air_m3h=self.air_m3h * ratio,
            wash_water_m3h=self.wash_water_m3h * ratio,
            overflow_water_m3h=self.overflow_water_m3h * ratio,
        )

    @property
    def blower_rating_kw(self) -> float:
        """송풍기 — 라이저 수두 + 스파저 손실 기준."""
        static_kpa = 1000.0 * 9.80665 * self.riser_height_m / 1000.0
        total_kpa = math.ceil((static_kpa + 20.0) * 1.3 / 5.0) * 5.0
        shaft = (self.air_m3h / 3600.0) * (total_kpa * 1000.0) / 0.55
        return select_motor_kw(shaft, service_factor=1.5)

    @property
    def blower_pressure_kpa(self) -> float:
        static_kpa = 1000.0 * 9.80665 * self.riser_height_m / 1000.0
        return math.ceil((static_kpa + 20.0) * 1.3 / 5.0) * 5.0


@dataclass(frozen=True)
class RfcOperatingPoint:
    """확정 동체를 특정 처리량에서 운전할 때의 조건."""

    design: RfcDesign
    dry_tph: float
    solids_wt: float
    turndown_ratio: float
    feed_m3h: float
    air_m3h: float
    wash_water_m3h: float
    overflow_water_m3h: float

    @property
    def feed_flux_cm_s(self) -> float:
        return self.design.feed_flux_cm_s * self.turndown_ratio

    @property
    def air_flux_cm_s(self) -> float:
        return self.design.air_flux_cm_s * self.turndown_ratio

    @property
    def wash_water_flux_cm_s(self) -> float:
        return self.design.wash_water_flux_cm_s * self.turndown_ratio

    @property
    def water_tph(self) -> float:
        return self.dry_tph * (1.0 - self.solids_wt) / self.solids_wt

    @property
    def within_capacity(self) -> bool:
        return (
            self.turndown_ratio <= 1.0 + 1e-9
            and self.solids_wt <= self.design.design_solids_wt + 1e-9
        )

    @property
    def gas_liquid_residence_min(self) -> float:
        """현재 flux에서의 실제 기액 체류시간."""
        combined_m_s = (self.feed_flux_cm_s + self.air_flux_cm_s) / 100.0
        return self.design.riser_height_m / combined_m_s / 60.0


def size_rfc(
    tag: str,
    duty: str,
    dry_tph: float,
    solids_sg: float,
    solids_wt: float,
    trial: ref.ContinuousTrial = ref.CONTINUOUS_TRIAL,
    bias_flux_cm_s: float = 0.25,
    inclined_channel_angle_deg: float = 70.0,
    inclined_channel_spacing_mm: float = 12.0,
) -> RfcDesign:
    """실증 flux 를 그대로 유지한 채 단면적만 키워 스케일업한다.

    RFC 계열 장치의 스케일업은 flux 상사(flux similarity)로 이루어진다.
    실증에서 확인된 급광·기체·세척수 flux 를 고정하고 단면적을 처리량에
    비례해 키우면, 기액 체류시간과 bias 조건이 그대로 유지된다.

    Args:
        dry_tph: 목표 건조 고체 처리량.
        solids_wt: 설계 고체 질량분율. 실증은 2 wt%, 회분식은 7 wt% 에서
            검증됐고 저자들은 30 wt% 까지 가능하다고 보나 PV 원료로는
            미검증이다. 보수적으로 검증된 값 근처를 쓰는 것이 안전하다.
        bias_flux_cm_s: 양의 bias flux. 클수록 정광 품위가 오르고
            회수율이 약간 떨어진다.
    """
    if bias_flux_cm_s >= trial.wash_water_flux_cm_s:
        raise ValueError("bias flux 는 세척수 flux 보다 작아야 함")
    q = slurry_volumetric_flow_m3h(dry_tph, solids_sg, solids_wt)
    area = q / (trial.feed_flux_cm_s / 100.0 * 3600.0)
    diameter = _round_up_diameter(math.sqrt(4.0 * area / math.pi))

    # 기액 체류시간을 실증값으로 유지하는 라이저 높이
    combined_flux_cm_s = trial.feed_flux_cm_s + trial.air_flux_cm_s
    riser_height = combined_flux_cm_s / 100.0 * 60.0 * trial.gas_liquid_residence_min

    return RfcDesign(
        tag=tag,
        duty=duty,
        diameter_m=diameter,
        design_solids_wt=solids_wt,
        design_dry_tph=dry_tph,
        feed_flux_cm_s=trial.feed_flux_cm_s,
        air_flux_cm_s=trial.air_flux_cm_s,
        wash_water_flux_cm_s=trial.wash_water_flux_cm_s,
        bias_flux_cm_s=bias_flux_cm_s,
        gas_liquid_residence_min=trial.gas_liquid_residence_min,
        riser_height_m=riser_height,
        inclined_channel_angle_deg=inclined_channel_angle_deg,
        inclined_channel_spacing_mm=inclined_channel_spacing_mm,
        solids_sg=solids_sg,
    )


# --------------------------------------------------------------------------
# 성능
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class RfcPerformance:
    """연속 부선조 1단의 물질수지."""

    feed_tph: dict[str, float]
    concentrate_tph: dict[str, float]
    tailings_tph: dict[str, float]
    recoveries: dict[str, float]

    def recovery(self, name: str) -> float:
        """성분 회수율 — :class:`~flotation_design.circuit.CircuitResult` 와 동일 인터페이스."""
        return self.recoveries[name]

    @property
    def feed_dry_tph(self) -> float:
        return sum(self.feed_tph.values())

    @property
    def concentrate_dry_tph(self) -> float:
        return sum(self.concentrate_tph.values())

    @property
    def tailings_dry_tph(self) -> float:
        return sum(self.tailings_tph.values())

    @property
    def mass_yield(self) -> float:
        return self.concentrate_dry_tph / self.feed_dry_tph if self.feed_dry_tph else 0.0

    def feed_grade(self, name: str) -> float:
        return self.feed_tph[name] / self.feed_dry_tph if self.feed_dry_tph else 0.0

    def concentrate_grade(self, name: str) -> float:
        c = self.concentrate_dry_tph
        return self.concentrate_tph[name] / c if c else 0.0

    def tailings_grade(self, name: str) -> float:
        t = self.tailings_dry_tph
        return self.tailings_tph[name] / t if t else 0.0

    def upgrade(self, name: str) -> float:
        f = self.feed_grade(name)
        return self.concentrate_grade(name) / f if f else 0.0

    def mass_balance_error_tph(self) -> float:
        return max(
            abs(self.feed_tph[n] - self.concentrate_tph[n] - self.tailings_tph[n])
            for n in self.feed_tph
        )


def rfc_separation(
    feed_component_tph: dict[str, float],
    kinetics: dict,
    ag_recovery: float,
    composite_carry_ratio: float,
    entrainment_recovery: float = 0.0,
) -> RfcPerformance:
    """연속 부선조의 물질수지.

    **반응속도 모델을 쓰지 않는다.** 이 장치는 완전혼합조가 아니라 스파저와
    유동층, 경사판, 세척수 bias 로 구성된 흐름 장치라, 기액 체류시간 1분을
    CSTR 식에 대입하면 회수율이 63 % 로 나와 실측(~100 %)과 전혀 맞지 않는다.
    flux 상사로 스케일업하면 수력학적 조건이 보존되므로, **실증에서 측정된
    회수율을 그대로 이월**하는 것이 옳다.

    Args:
        ag_recovery: 실증 Ag 회수율.
        composite_carry_ratio: Ag 1 kg당 함께 올라가는 맥석 kg. 잠금 맥석을
            별도 성분으로 주지 않은 구형 입력에만 적용하는 호환용 근사값이다.
        entrainment_recovery: 세척수 bias 를 넘어 남는 수분 동반 혼입.
            양의 bias 에서는 사실상 0 이다.
    """
    ag_kin = kinetics["Ag"]
    if ag_kin.r_max <= 0:
        raise ValueError("Ag 의 부선 가능 분율이 0")
    scale = ag_recovery / ag_kin.r_max

    conc: dict[str, float] = {}
    tail: dict[str, float] = {}
    rec: dict[str, float] = {}
    gangue: list[str] = []
    for name, tph in feed_component_tph.items():
        kin = kinetics[name]
        if kin.r_max > 0.0:
            r = min(1.0, kin.r_max * scale)
        else:
            r = entrainment_recovery
            gangue.append(name)
        rec[name] = r
        conc[name] = tph * r
        tail[name] = tph * (1.0 - r)

    # 신규 설계는 결합 Si 를 Ag_locked_gangue 성분으로 직접 추적한다.
    # 이 성분이 없는 구형 입력에만 Ag 질량 기준 근사를 적용한다.
    valuable = conc.get("Ag", 0.0)
    available = {n: tail[n] for n in gangue}
    total_available = sum(available.values())
    if (
        "Ag_locked_gangue" not in feed_component_tph
        and composite_carry_ratio > 0.0
        and valuable > 0.0
        and total_available > 0.0
    ):
        demand = min(composite_carry_ratio * valuable, total_available)
        for name in gangue:
            moved = demand * available[name] / total_available
            conc[name] += moved
            tail[name] -= moved
            rec[name] = conc[name] / feed_component_tph[name] if feed_component_tph[name] else 0.0

    return RfcPerformance(dict(feed_component_tph), conc, tail, rec)
