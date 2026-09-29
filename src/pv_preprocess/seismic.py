"""내진 — 앵커가 지진하중을 받는가.

§30 에서 앵커 190개를 세웠다. 그 개수는 **자중과 운전하중**에서 나온 값이다.
지진은 안 봤다. 국내 설비는 KDS 41 17 00(비구조요소)이 요구하고, 검사원이
가장 먼저 묻는 것도 이것이다.

식은 ASCE 7 제13장과 같은 꼴이다.

    Fp = 0.4 · a_p · S_DS · W_p / (R_p / I_p) · (1 + 2 z/h)

바닥에 놓인 설비는 z = 0 이라 높이항이 1.0 이다. 상·하한(0.3·S_DS·I_p·W_p ≤
Fp ≤ 1.6·S_DS·I_p·W_p)이 걸린다.

**S_DS 는 여기서 못 정한다.** 부지 지반조사와 지역계수가 있어야 나오는
값이고, 없는 값을 골라 적으면 그 순간 이 파일이 거짓이 된다. 그래서 인자로
받고, 기본값은 **가정임을 이름으로 밝힌다**(`ASSUMED_SDS`).

대신 여기서 답할 수 있는 것이 하나 있고 그것이 이 모듈의 값어치다 —
**현 앵커 계획이 S_DS 얼마까지 버티는가.** 지반조사가 오면 그 값과 비교만
하면 되고, 넘으면 앵커를 키우는 것이 아니라 **베이스를 넓히는 쪽**이 먼저다.
전도는 앵커 인장이 아니라 지레비로 정해지기 때문이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import crane, mounting

# ── 계수 ─────────────────────────────────────────────────────────────────
#: 설계스펙트럼 단주기 가속도 (g). **가정값이다** — 부지 지반조사가 대체한다.
#: 0.50 은 국내 지진구역 I·보통 지반에서 흔히 쓰는 크기이며, 이 모듈의 결론은
#: 이 값 자체가 아니라 `governing_sds()` 가 내는 **한계**다.
ASSUMED_SDS = 0.50

#: 요소 증폭계수. 강체는 1.0, 유연체는 2.5. 프레임 위에 높이 선 것은 유연체다.
AP_RIGID = 1.0
AP_FLEXIBLE = 2.5

#: 요소 반응수정계수. 앵커로 고정된 일반 기계류.
RP = 2.5

#: 중요도계수. 인명안전 설비가 아니면 1.0.
IP = 1.0

#: 강체·유연체를 가르는 세장비 (높이 ÷ 베이스 최소폭). 이 위는 유연체로 본다.
SLENDER_RATIO = 2.0

#: 상·하한 계수 (ASCE 7 §13.3.1).
FP_MIN_FACTOR = 0.3
FP_MAX_FACTOR = 1.6

#: 중력가속도 (m/s²).
G = 9.80665

#: 앵커 규격별 인장 허용 (kN/본). 후시공 앵커의 관례적 설계값이며,
#: 실제 값은 콘크리트 강도·연단거리·매입깊이가 정한다 — 벤더 ETA 가 대체한다.
ANCHOR_TENSION_KN: dict[str, float] = {"M16": 22.0, "M20": 35.0, "M24": 50.0}


@dataclass(frozen=True)
class Component:
    """지진하중을 볼 설비 하나.

    질량·높이는 `crane.LIFTS` 에서 온다 — 크레인이 드는 것과 지진이 흔드는 것은
    같은 물건이라 두 번 적을 이유가 없다. 여기서 더하는 것은 **베이스폭** 하나다.

    베이스폭을 셀 외형으로 잡으면 안 된다. 셀은 6 m 인데 그 안의 반전 카세트가
    2.7 m 로 서 있으면, 셀 폭으로 계산한 복원 모멘트가 실제의 두 배가 넘는다 —
    그리고 그 순간 "지진에 아무 문제 없다" 는 거짓 답이 나온다. 그래서 폭은
    3D 실측이거나 기구 도면의 기둥 자리이고, 어디서 왔는지를 근거란에 적는다.
    """

    name: str
    station: str
    mass_kg: int
    height_mm: int
    base_mm: int
    wall_mounted: bool
    basis: str

    @property
    def base_width_mm(self) -> int:
        return self.base_mm

    @property
    def slenderness(self) -> float:
        return round(self.height_mm / self.base_width_mm, 2)

    @property
    def is_flexible(self) -> bool:
        return self.slenderness > SLENDER_RATIO

    @property
    def a_p(self) -> float:
        return AP_FLEXIBLE if self.is_flexible else AP_RIGID


#: 설비별 베이스폭 (mm) 과 그 출처. 이름은 `crane.LIFTS` 의 이름과 같아야 한다 —
#: 어긋나면 시험이 잡는다.
BASE_MM: dict[str, tuple[int, bool, str]] = {
    "BFC 반전 카세트 (Bay 1식)":
        (2_660, False, "3D 실측 — BFC-101A 포탈 기둥·LM가이드 조립체의 Z 폭. "
                       "카세트는 그 안에 있으므로 넘어질 때 버티는 것은 포탈이다"),
    "GRM-401 5단 단열랙 M1-101":
        (1_900, False, "3D 실측 — M1-101 5단 단열랙의 Z 폭"),
    "AFR-101 셀 베이스 프레임":
        (865, False, "3D 실측 — S355 베이스 프레임과 CV-101 가대 다리의 Z 폭. "
                     "X 로는 11.4 m 라 길이 방향 전도는 문제가 아니다"),
    "AFR CL-221 클램프 포탈 1조":
        (2_900, False, "기구 도면 — 기둥 자리 z ±1,450 (kinematics 의 포탈 기둥 위치). "
                       "통과 폭·정렬 셔틀·LM 레일 밖, 안전가드 안쪽에서 정해진 값이다"),
    "VG-101 독립 방진 비전보 조립체":
        (2_130, False, "3D 실측 — 독립 기둥 2본의 X 간격. Z 로는 6.7 m 라 "
                       "짧은 쪽이 지레비를 정한다"),
    "HPU-601 유압 파워유닛":
        (820, False, "3D 실측 — HPU 본체·방진 마운트의 Z 폭"),
    "MDB-101 주 분전반":
        (300, True, "**벽부 D300 이다.** 바닥에 서 있지 않으므로 전도가 아니라 "
                    "벽 앵커의 인장으로 받는다 — 지레비가 깊이 300 뿐이라 "
                    "이 플랜트에서 가장 불리한 자리다"),
    "VAC-101 진공 스키드":
        (860, False, "3D 실측 — 스키드 베이스의 Z 폭"),
}


def components() -> tuple[Component, ...]:
    """crane.LIFTS 에 베이스폭을 얹어 돌려준다."""
    out = []
    for lift in crane.LIFTS:
        base, wall, basis = BASE_MM[lift.name]
        out.append(Component(lift.name, lift.station, lift.mass_kg,
                             lift.height_mm, base, wall, basis))
    return tuple(out)


# ── 지진력 ───────────────────────────────────────────────────────────────
def seismic_ratio(a_p: float, s_ds: float | None = None,
                  z_over_h: float = 0.0) -> float:
    """Fp / W_p — 자중의 몇 배로 옆에서 미는가."""
    sds = ASSUMED_SDS if s_ds is None else s_ds
    raw = 0.4 * a_p * sds / (RP / IP) * (1 + 2 * z_over_h)
    return round(min(max(raw, FP_MIN_FACTOR * sds * IP), FP_MAX_FACTOR * sds * IP), 4)


def seismic_force_kn(component: Component, s_ds: float | None = None) -> float:
    """설비 하나에 걸리는 수평 지진력 (kN)."""
    weight_kn = component.mass_kg * G / 1000
    return round(weight_kn * seismic_ratio(component.a_p, s_ds), 2)


def overturning_moment_knm(component: Component, s_ds: float | None = None) -> float:
    """전도 모멘트 — 지진력이 무게중심(높이의 절반)에 걸린다."""
    return round(seismic_force_kn(component, s_ds) * component.height_mm / 2 / 1000, 2)


def restoring_moment_knm(component: Component) -> float:
    """복원 모멘트 — 자중이 베이스 반폭에서 버틴다."""
    weight_kn = component.mass_kg * G / 1000
    return round(weight_kn * component.base_width_mm / 2 / 1000, 2)


def anchor_tension_kn(component: Component, s_ds: float | None = None) -> float:
    """인장측 앵커 한 본에 걸리는 힘 (kN).

    복원이 전도를 이기면 0 이다 — 그때는 앵커가 미끄럼만 막는다. 이기지
    못하는 만큼을 인장측 앵커가 나눠 받는다. 앵커군이 없으면 나눌 대상이
    없으므로 답이 없다(NaN) — 0 으로 돌려주면 "괜찮다" 로 읽힌다.
    """
    if anchor_group(component) is None:
        return float("nan")
    net = overturning_moment_knm(component, s_ds) - restoring_moment_knm(component)
    if net <= 0:
        return 0.0
    lever_m = component.base_width_mm / 1000
    return round(net / lever_m / tension_anchors(component), 2)


#: 설비 → 그 설비를 잡는 앵커군(`mounting.MOUNTINGS` 의 target). None 은
#: **아직 배정된 앵커군이 없다**는 뜻이고, 그것이 이 모듈이 찾아낸 것이다.
ANCHOR_GROUP: dict[str, tuple[str, str] | None] = {
    "BFC 반전 카세트 (Bay 1식)": ("bfc", "포탈기둥"),
    "GRM-401 5단 단열랙 M1-101": ("grm", "랙"),
    "AFR-101 셀 베이스 프레임": ("afr", "메인셀"),
    "AFR CL-221 클램프 포탈 1조": ("afr", "클램프 포탈"),
    "VG-101 독립 방진 비전보 조립체": None,
    "HPU-601 유압 파워유닛": ("afr", "HPU·FH 독립"),
    "MDB-101 주 분전반": None,
    "VAC-101 진공 스키드": None,
}


def anchor_group(component: Component) -> mounting.Anchor | None:
    """그 설비를 잡는 앵커군. 없으면 None."""
    key = ANCHOR_GROUP[component.name]
    if key is None:
        return None
    station, target = key
    mount = mounting.MOUNTING_OF[station]
    return next(a for a in mount.anchors if a.target == target)


def unanchored() -> tuple[Component, ...]:
    """앵커군이 배정 안 된 설비.

    §30 의 앵커 계획은 셀 단위로 총수를 세웠고 그 자체는 맞다. 다만 지진은
    **설비 하나하나**를 흔들기 때문에, "이 셀에 앵커가 190개 있다" 는
    말로는 "이 물건이 안 넘어진다" 를 못 보인다. 그 차이가 여기서 드러난다.
    """
    return tuple(c for c in components() if anchor_group(c) is None)


def anchored() -> tuple[Component, ...]:
    return tuple(c for c in components() if anchor_group(c) is not None)


def total_anchors(component: Component) -> int:
    group = anchor_group(component)
    if group is None:
        return 0
    return group.count * (group.units if group.per_unit else 1)


def tension_anchors(component: Component) -> int:
    """인장측 열의 앵커 수 — 네 변에 고르게 놓였다고 보고 한 변 몫을 쓴다."""
    return max(2, total_anchors(component) // 4)


def anchor_size(component: Component) -> str:
    """그 앵커군의 규격."""
    group = anchor_group(component)
    return group.bolt if group is not None else "미배정"


def anchor_utilisation(component: Component, s_ds: float | None = None) -> float:
    """앵커 사용률 — 1.0 을 넘으면 그 설비가 지진에 진다."""
    size = anchor_size(component)
    if size not in ANCHOR_TENSION_KN:
        return float("nan")
    return round(anchor_tension_kn(component, s_ds) / ANCHOR_TENSION_KN[size], 3)


def governing_component(s_ds: float | None = None) -> Component:
    """앵커가 배정된 것 중 사용률이 가장 높은 설비 — 여기가 먼저 진다."""
    return max(anchored(), key=lambda c: anchor_utilisation(c, s_ds))


def most_slender() -> Component:
    """세장비가 가장 큰 설비 — 앵커 배정 여부와 무관하게 가장 불리한 형상이다."""
    return max(components(), key=lambda c: c.slenderness)


def holds(s_ds: float | None = None) -> bool:
    """**앵커가 배정된 것만** 본다. 미배정이 남아 있으면 이 답은 부분적이다."""
    return all(anchor_utilisation(c, s_ds) <= 1.0 for c in anchored())


#: S_DS 탐색 상한 (g). 국내 어느 부지도 이 위로 가지 않는다 — 여기까지
#: 버티면 "지진이 지배하지 않는다" 는 뜻이지 특정 값이 나온 것이 아니다.
SDS_SEARCH_LIMIT = 3.0


def governing_sds(step: float = 0.01, limit: float | None = None) -> float:
    """앵커가 배정된 설비가 버티는 S_DS 상한.

    지반조사가 오면 이 값과 비교만 하면 된다. 상한까지 버티면 그 상한을
    돌려주므로, 계산된 한계인지 탐색 끝인지는 `governing_sds_is_capped()` 로
    갈라 본다 — 탐색 끝을 한계로 적으면 없는 정밀도를 파는 셈이 된다.
    """
    top = SDS_SEARCH_LIMIT if limit is None else limit
    sds = step
    while sds <= top:
        if not holds(round(sds, 4)):
            return round(sds - step, 2)
        sds = round(sds + step, 4)
    return top


def governing_sds_is_capped() -> bool:
    """한계를 못 찾고 탐색 상한에서 멈췄는가."""
    return governing_sds() >= SDS_SEARCH_LIMIT


def uplift_sds(component: Component) -> float:
    """이 설비가 들리기 시작하는 S_DS.

    복원이 전도에 지는 지점이다. 앵커가 일을 시작하는 자리이기도 하다 —
    여기까지는 자중만으로 서 있다.
    """
    ratio_needed = component.base_width_mm / component.height_mm
    # ratio = max(0.4·a_p/(Rp/Ip), 0.3) · S_DS 이므로 역산한다
    per_g = max(0.4 * component.a_p / (RP / IP), FP_MIN_FACTOR)
    return round(ratio_needed / per_g, 2)


def required_anchors(component: Component, bolt: str = "M16",
                     s_ds: float | None = None) -> int:
    """앵커군이 없는 설비에 몇 본이 필요한가 — 인장측 한 열 기준.

    답이 "0 본" 으로 나올 수 있다. 자중만으로 안 들리는 설비라는 뜻이고,
    그래도 미끄럼 방지 앵커는 필요하다 — 그래서 하한이 2 다.
    """
    net = overturning_moment_knm(component, s_ds) - restoring_moment_knm(component)
    if net <= 0:
        return 2
    need = net / (component.base_width_mm / 1000) / ANCHOR_TENSION_KN[bolt]
    return max(2, math.ceil(need))


#: 전도가 문제가 될 때 무엇을 먼저 하는가. 앵커를 키우는 것은 세 번째다.
REMEDY_ORDER: tuple[tuple[str, str], ...] = (
    ("베이스를 넓힌다", "복원 모멘트는 베이스 반폭에 **비례**하고 인장은 지레비에 "
                 "반비례한다 — 폭을 1.5배 하면 두 쪽이 같이 좋아진다"),
    ("무게중심을 낮춘다", "전도 모멘트가 높이에 비례한다. 상부 중량물을 내리는 것이 "
                   "앵커를 키우는 것보다 싸다"),
    ("앵커를 키운다", "마지막이다. 굵히면 연단거리·매입깊이가 따라 커져 바닥 슬래브 "
               "두께까지 올라간다"),
    ("횡지지를 건다", "높고 좁은 것(VG-101 같은)은 상부를 건물 철골에 잡아 주는 편이 "
               "바닥에서 버티는 것보다 낫다 — 다만 건축 인터페이스가 된다"),
)


def summary() -> dict[str, object]:
    """도면 리터럴이 받아 가는 값."""
    worst = governing_component()
    slim = most_slender()
    return {
        "assumedSds": ASSUMED_SDS,
        "components": len(components()),
        "anchored": len(anchored()),
        "unanchored": len(unanchored()),
        "flexible": sum(1 for c in components() if c.is_flexible),
        "rp": RP,
        "ip": IP,
        "ratioRigid": seismic_ratio(AP_RIGID),
        "ratioFlexible": seismic_ratio(AP_FLEXIBLE),
        "governing": worst.name,
        "governingStation": worst.station,
        "governingSlenderness": worst.slenderness,
        "governingTensionKn": anchor_tension_kn(worst),
        "governingSize": anchor_size(worst),
        "governingUtilisation": anchor_utilisation(worst),
        "slenderest": slim.name,
        "slenderestRatio": slim.slenderness,
        "holds": holds(),
        "governingSds": governing_sds(),
        "governingSdsCapped": governing_sds_is_capped(),
        "slenderestUpliftSds": uplift_sds(slim),
        "slenderestNeedsM16": required_anchors(slim),
    }
