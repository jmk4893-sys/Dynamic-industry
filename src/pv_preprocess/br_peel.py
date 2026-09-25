# -*- coding: utf-8 -*-
"""BR-306 백시트 박리 — **약한 면은 덫이었다.**

`br_abrade` 가 백시트를 갈아 없애는 유닛이라면 이쪽은 필름째 떼는 대안이다.
박리를 못 쓴다고 본 이유 하나는 정말로 틀렸고, 하나는 맞았는데 내가 그것을
고쳤다고 착각했다.

  ① **맞게 고친 것 — 「노후 패널은 접착이 세다」는 반대다.** 백시트–EVA
     박리력은 신품 60~100 N/cm 인데 습열 300 h 만에 20 N/cm 로 내려가고 그
     뒤로도 계속 떨어진다. 20 년 된 패널을 받는 것이 **유리하다.**
  ② **틀리게 고친 것 — 「가장 약한 면에서 뜯으면 된다」.** 백시트는 그
     자체가 3층(불소 외피 / PET 심재 / 불소 내피)이고, 외피–심재 접착층이
     백시트–EVA 의 20 분의 1 로 약하다. 거기서 뜯으면 140 N 이면 된다.
     그리고 거기에 불소가 얹혀 있으니 **오염원과 약한 면이 같다**고 적었다.

     ②가 틀린 이유는 `separation` 에 있다. 실리콘을 더럽히는 것은 불소만이
     아니라 **PET 심재도 같다** — 둘 다 물보다 무거워 실리콘과 같은 침강분으로
     간다. 외피만 벗기면 심재가 남아 그대로 따라간다. **약한 면은 문제를
     푸는 것처럼 보이지만 안 푼다.**

그래서 뜯어야 하는 면은 약한 쪽이 아니라 **백시트–EVA** 다. 20 배 비싼 쪽이고,
`the_weak_plane_is_a_trap()` 이 그것을 판정한다. 남는 위안은 ①뿐이다 —
노후가 4 배를 깎아 주고 가열이 다시 절반을 깎는다.

    2,800 N   백시트–EVA · 노후 (설계값)
    1,400 N   거기에 가열까지
   11,200 N   신품이었다면

EVA 는 걱정할 것이 아니다. 물보다 가벼워 선별조에서 스스로 뜬다 — 불순물이지만
**스스로 갈라지는** 불순물이다. 그래서 박리가 EVA 를 조금 물고 나와도 된다.

이 모듈은 값을 정하지 않는다 — 면을 고르고 공법 후보를 같은 잣대로 세운다.
실측이 오면 `INTERFACES` 의 Gc 만 고치면 된다.

    PYTHONPATH=src python -c "from pv_preprocess import br_peel; print(br_peel.summary())"
"""

from __future__ import annotations

from dataclasses import dataclass

from . import campaign, separation, sg_grind

#: 유닛 태그. `br_abrade` (BR-305) 와 **같은 자리**를 두고 겨루는 대안이다.
UNIT_TAG = "BR-306"
UPSTREAM_TAG, DOWNSTREAM_TAG = "AFR-101", "SG-301"


# ── 적층 안의 면들 — 어디가 약하고 어디에 오염원이 있는가 ────────────────
@dataclass(frozen=True)
class Interface:
    """적층 안의 한 계면.

    `gc_fresh_n_mm` · `gc_aged_n_mm` 는 **폭 1 mm 당 박리력**(N/mm)이고
    파괴에너지(J/m²)와 같은 값이다 — 1 N/mm = 1,000 J/m².
    """

    key: str
    name: str
    above: str                  # 이 면 위에 얹혀 있는 것 (떼면 같이 나오는 것)
    gc_fresh_n_mm: float
    gc_aged_n_mm: float
    removes: tuple[str, ...]    # 여기를 떼면 **완전히** 빠지는 `separation` 성분
    basis: str


#: 계면 표. 노후값이 설계값이다 — 우리가 받는 것은 20 년 된 패널이다.
INTERFACES: tuple[Interface, ...] = (
    Interface(
        "fluoro_pet", "불소 외피 ↔ PET 심재 (백시트 내부)", "불소 외피만",
        0.60, 0.10, (),
        "현장 박리 문턱이 100 J/m² = 0.1 N/mm 로 보고돼 있고, PA·PET·PVDF 계 "
        "백시트 다수에서 **외피–심재 접착층이 노출과 함께 약해지는** 것이 "
        "관찰됐다. 가장 약하지만 **아무것도 완전히 안 빼낸다** — PET 심재와 "
        "불소 내피가 그대로 남아 실리콘으로 간다"),
    Interface(
        "backsheet_eva", "백시트 ↔ EVA", "백시트 3층 전부",
        8.00, 2.00, ("fluoro", "pet"),
        "신품 180° 박리 60~100 N/cm(6~10 N/mm), 습열 300 h 에 20 N/cm"
        "(2 N/mm)까지 내려가고 그 뒤로도 계속 떨어진다"),
    Interface(
        "eva_cell", "EVA ↔ 셀", "EVA + 백시트", 12.00, 6.00,
        ("fluoro", "pet", "eva"),
        "여기를 노리면 셀이 따라 나온다 — 전처리 단계에서 할 일이 아니다. "
        "값은 자릿수만 맞춘 계획값이다"),
)

#: 가열 보조 온도 (°C) — KR101936925B1 의 흡착 가열 범위.
HEAT_ASSIST_C = (50.0, 300.0)
#: 가열이 박리력을 깎는 몫 — **계획값**이다. 온도별 실측 곡선을 못 찾았다.
#: 박리력이 온도·박리각·속도에 함께 걸린다는 것까지는 문헌이 말하지만
#: 이 적층의 곡선은 시험으로만 나온다.
HEAT_DERATE = 0.5


def interfaces_by_ease() -> tuple[Interface, ...]:
    """노후 상태 기준으로 약한 순서 — 위가 뜯기 쉬운 면이다."""
    return tuple(sorted(INTERFACES, key=lambda i: i.gc_aged_n_mm))


def weakest_interface() -> Interface:
    """가장 약한 면."""
    return interfaces_by_ease()[0]


def must_remove() -> frozenset[str]:
    """이 유닛이 맡은 관문에서 빠져야 하는 성분 — `separation` 이 정본이다.

    네 관문 중 **백시트** 하나다. 유리·구리·EVA 는 다른 유닛 몫이다.
    """
    return separation.gate_component_keys("backsheet")


def is_sufficient(iface: Interface) -> bool:
    """이 면에서 뜯으면 실리콘을 더럽힐 것이 다 빠지는가."""
    return must_remove() <= frozenset(iface.removes)


def required_interface() -> Interface:
    """충분한 면 중 **가장 얕은** 것 — 실제로 뜯어야 하는 면이다.

    깊이 갈수록 딸려 나오는 것이 많아지므로, 오염원이 다 빠지면 멈춘다.
    """
    for iface in INTERFACES:
        if is_sufficient(iface):
            return iface
    raise AssertionError("충분한 면이 하나도 없다 — 표가 틀렸다")


def the_weak_plane_is_a_trap() -> bool:
    """**이 모듈의 요지** — 가장 약한 면이 문제를 푸는 것처럼 보이지만 안 푼다.

    참이다. 외피–심재 면은 20 배 싸고 불소가 거기 얹혀 있어 답처럼 보이는데,
    **PET 심재가 남는다.** 심재도 물보다 무거워 실리콘과 같은 침강분으로 가니
    오염이 그대로다. 그래서 비싼 면으로 가야 한다.
    """
    return not is_sufficient(weakest_interface())


def cost_of_going_to_the_right_plane() -> float:
    """약한 면 대신 옳은 면으로 갈 때 힘이 몇 배가 되는가."""
    return round(peel_force_n(required_interface()) / peel_force_n(weakest_interface()), 1)


def aging_helps() -> bool:
    """세월이 박리를 **돕는가** — 처음에 반대로 알고 있던 것이다."""
    return all(i.gc_aged_n_mm < i.gc_fresh_n_mm for i in INTERFACES)


# ── 그 면을 뜯는 데 드는 힘 ─────────────────────────────────────────────
def peel_force_n(iface: Interface | None = None, *,
                 aged: bool = True, heated: bool = False) -> float:
    """한 면을 폭 전체에서 뜯는 힘 (N) = Gc × 패널 폭.

    두께가 안 들어간다 — 계면 일이라 백시트가 얼마나 두껍든 같다.
    """
    iface = iface or required_interface()
    gc = iface.gc_aged_n_mm if aged else iface.gc_fresh_n_mm
    if heated:
        gc *= HEAT_DERATE
    return round(gc * float(campaign.PANEL_WIDTH_MM), 1)


def peel_energy_j(iface: Interface | None = None, **kw) -> float:
    """그 면을 끝까지 뜯는 일 (J/장) = 힘 × 패널 길이."""
    return round(peel_force_n(iface, **kw)
                 * float(campaign.PANEL_LENGTH_MM) / 1_000.0, 1)


def aging_saves_us() -> float:
    """노후가 힘을 몇 배 깎아 주는가 — 남은 위안 하나다."""
    return round(peel_force_n(aged=False) / peel_force_n(aged=True), 1)


def heat_saves_us() -> float:
    """가열이 그 위에서 다시 몇 배를 깎는가."""
    return round(peel_force_n() / peel_force_n(heated=True), 1)


def heat_brings_it_to_n() -> float:
    """가열까지 얹으면 힘이 얼마가 되는가 (N)."""
    return peel_force_n(heated=True)


def force_the_face_allows_n() -> float:
    """면이 견디는 압착력 (N) — `sg_grind` 가 정본이다.

    박리는 판을 **당기는** 일이라 이 값이 직접 걸리지는 않지만, 그리퍼가
    면을 무는 힘이 여기 들어야 한다. 자릿수 비교용으로 둔다.
    """
    return float(sg_grind.FACE_PAD_LEN_MM) * float(sg_grind.FACE_SAFE_MPA) \
        * float(sg_grind.SEALANT_BAND_MM)


# ── 공법 후보 — 같은 잣대로 세운다 ──────────────────────────────────────
@dataclass(frozen=True)
class Method:
    """박리를 쉽게 만드는 수단 하나."""

    key: str
    name: str
    principle: str
    parameters: str
    seconds_per_panel: float | None   # None = 문헌에 장당 값이 없다
    blocker: str
    solvent_free: bool


METHODS: tuple[Method, ...] = (
    Method(
        "heat_vacuum", "가열 흡착 박리",
        "흡착 패드가 면을 물고 데운 채로 당긴다. 온도가 오르면 접착이 무른다.",
        f"{HEAT_ASSIST_C[0]:.0f}~{HEAT_ASSIST_C[1]:.0f} °C 흡착 가열 (KR101936925B1)",
        None,
        "온도별 박리력 곡선이 없다. 다만 설비가 가장 단순하고 라인에 그대로 "
        "붙는다 — 후보 중 유일하게 소모품도 압력용기도 안 든다.",
        True),
    Method(
        "ir_laser", "연속파 적외선 레이저",
        "**유리 쪽에서** 1070 nm 를 쏘면 유리를 지나 실리콘이 먹고, 그 자리가 "
        "데워져 EVA 가 무른다. 유리도 웨이퍼도 안 다친다.",
        "28 W/cm² (23~33 범위) · 수 cm² 를 8~12 s",
        None,
        "**면적 속도가 벽이다.** 4 cm²/10 s 로 보면 3.5 m² 에 24 시간이 "
        "걸린다 — 라인 택트 48 s 의 1,800 배다. 같은 면적속도를 유지한 채 "
        "택트에 맞추려면 200 kW 급 레이저가 필요해 성립하지 않는다. "
        "체류시간 자체가 물리라 병렬화로 못 줄인다.",
        True),
    Method(
        "dmac_soak", "DMAc 침지",
        "N,N-디메틸아세트아미드에 담그면 **불소 코팅이 분리된다.** "
        "우리가 빼야 하는 바로 그 층이다.",
        "25 °C · 5 분 (그 뒤 160 °C 10 분 → 초음파 800 W/20 kHz 10 분)",
        300.0,
        "DMAc 가 생식독성 물질(REACH SVHC · 국내 특별관리물질)이다. 상온 "
        "5 분이라 속도는 좋지만 라인에 습식조와 용제 회수·배기가 따라붙고 "
        "취급 규제가 설계를 지배한다.",
        False),
    Method(
        "sc_co2", "초임계 CO₂ 발포",
        "CO₂ 가 EVA 에 녹아든 뒤 급감압하면 EVA 가 부풀고, 그 팽창 응력이 "
        "계면을 벌린다. EVA·POE·아이오노머에 다 듣는다.",
        "≥150 bar · EVA 융점 이상 · 감압속도가 빠를수록 변형이 크다",
        None,
        "2.5 m 패널이 들어가는 150 bar 압력용기는 라인 설비가 아니라 "
        "배치 설비다. 용제가 없고 CO₂ 를 회수해 쓴다는 점은 후보 중 가장 깨끗하다.",
        True),
    Method(
        "ultrasonic", "초음파 보조",
        "용제·열로 무르게 한 뒤 초음파로 계면을 흔들어 떼어 낸다.",
        "800 W · 20 kHz · 10 분 (선행 처리 필요)",
        600.0,
        "혼자 못 쓴다 — 위의 용제나 열이 먼저 와야 한다. 습식조가 전제다.",
        False),
)


def line_takt_s() -> float:
    """라인 택트 (s) — 공법이 여기 들어야 인라인이다."""
    return campaign.ideal_takt_s()


def methods_that_fit_inline() -> tuple[Method, ...]:
    """장당 시간이 알려져 있고 택트 안에 드는 공법."""
    return tuple(m for m in METHODS
                 if m.seconds_per_panel is not None
                 and m.seconds_per_panel <= line_takt_s())


def solvent_free_methods() -> tuple[Method, ...]:
    """용제를 안 쓰는 공법 — 습식조·회수·배기가 안 붙는다."""
    return tuple(m for m in METHODS if m.solvent_free)


def recommended() -> Method:
    """지금 근거로 먼저 시험할 것.

    가열 흡착이다 — 후보 중 유일하게 용제도 압력용기도 소모품도 없고,
    라인에 그대로 붙으며, 국내 특허에 장치 구성까지 나와 있다. 남은 것은
    **온도별 박리력 곡선 한 장**이고 그것은 시험으로 나온다.
    """
    return next(m for m in METHODS if m.key == "heat_vacuum")


def why_not_abrading() -> tuple[str, ...]:
    """왜 `br_abrade` 대신 이쪽을 보는가 — 그리고 어디가 더 비싼가."""
    weak = weakest_interface()
    return (
        "박리는 **필름째 떼어 라인 밖으로 내보낸다.** 연마는 가루로 바꿀 뿐이라 "
        "안 잡힌 몫이 그대로 파쇄를 거쳐 급광에 들어가고, 거기서 실리콘·은과 "
        "같은 침강분에 섞인다. 그래서 연마는 포집률이 품질 사양이 되고 박리는 "
        "그럴 일이 없다 — 이것이 두 공법의 성격 차이다.",
        f"집진도 통째로 안 든다. `br_abrade` 는 "
        f"{sg_grind.backsheet_dust_kg_per_h():,.1f} kg/h 의 가연성 분진과 "
        "그것을 받는 별도 계통이 전제였다.",
        f"**대신 힘이 비싸다.** 뜯어야 하는 면이 {required_interface().name} 이고 "
        f"{peel_force_n():,.0f} N 이다. 약한 면({weak.name})은 "
        f"{peel_force_n(weak):,.0f} N 이지만 PET 심재를 못 빼내 쓸 수 없다 — "
        f"옳은 면으로 가는 값이 {cost_of_going_to_the_right_plane()} 배다.",
        f"그나마 노후가 {aging_saves_us()} 배, 가열이 다시 {heat_saves_us()} 배를 "
        f"깎아 {heat_brings_it_to_n():,.0f} N 까지 내려온다. EVA 를 조금 물고 "
        "나와도 되는데, 그것이 **EVA 가 무해해서가 아니라**(EVA 는 뜨는 쪽 "
        "은정광으로 간다) 판 안에 원래 있던 것을 앞당겨 걷는 것뿐이기 때문이다.",
    )


# ── 상류가 이미 걸어 둔 조건 ────────────────────────────────────────────
#
#   이 유닛을 짓기 전부터 저장소가 박리를 알고 있었다. `handoff` 의 JBR-201
#   출력 조건이 「튀어나온 리본 단부가 **박리 중 백시트를 걸어 찢는다**」고
#   적고 그 한도를 들고 있다. 다시 유도하지 않고 받아 온다.

def upstream_conditions() -> tuple[tuple[str, str], ...]:
    """박리가 성립하려면 상류가 지켜야 하는 것 — `handoff` 가 정본이다."""
    from . import handoff
    return (
        ("리본 단부 돌출",
         f"백시트 면 위 ≤ {handoff.RIBBON_STUB_MAX_MM:g} mm — 넘으면 박리 중 "
         "백시트를 걸어 찢는다"),
        ("리본 단부 자세",
         "눕혀 굽히지 않는다" if not handoff.RIBBON_MAY_BE_LAID_OVER
         else "눕힘 허용",
         ),
        ("접착 실리콘 잔여",
         f"백시트 면 위 ≤ {handoff.SILICONE_RESIDUE_MAX_MM:g} mm"),
    )


def tear_risk_is_already_specified() -> bool:
    """찢김 위험이 이미 상류 사양으로 잡혀 있는가 — 새로 만들 것이 없다."""
    from . import handoff
    return handoff.RIBBON_STUB_MAX_MM > 0 and not handoff.RIBBON_MAY_BE_LAID_OVER


def jbr_notch_as_a_start_point() -> tuple[str, ...]:
    """시작점 문제 — JBR 이 이미 백시트에 구멍을 낸다.

    계면 박리는 균열을 시작할 자리가 있어야 한다. 그런데 JBR-201 절입이
    백시트를 뚫는 것이 **허용 조건**으로 이미 들어와 있다 — 정션박스 발자국
    안에서 깊이 상한 `BACKSHEET_NOTCH_MAX_MM` 까지. 그 절결이 그리퍼가
    물 자리가 될 수 있다.
    """
    from . import handoff
    return (
        f"JBR-201 이 정션박스 발자국 안에 깊이 ≤ "
        f"{handoff.BACKSHEET_NOTCH_MAX_MM:g} mm 의 절결을 남기는 것이 발주처 "
        "승인 사항이다. 없애려던 결함이 아니라 **받아들인 조건**이다.",
        "계면 박리에 필요한 것이 시작점이므로, 그 절결이 그리퍼 자리로 쓰일 수 "
        "있다 — 따로 긋는 수단을 안 만들어도 된다는 뜻이다.",
        "다만 그 자리는 판 **가운데**(정션박스 자리)이지 변이 아니다. 가운데서 "
        "시작하는 박리는 전선이 사방으로 퍼져 변에서 당기는 것과 다르다. "
        "쓸 수 있는지는 시편으로 봐야 한다.",
        f"그리고 같은 문서가 리본 단부를 ≤ {handoff.RIBBON_STUB_MAX_MM:g} mm 로 "
        "묶어 둔 이유가 바로 **박리 중 찢김**이다. 상류가 이미 이 유닛을 "
        "염두에 두고 서 있었다.",
    )


def open_questions() -> tuple[str, ...]:
    """실측이 와야 닫히는 것."""
    return (
        "**온도별 박리력 곡선이 없다.** 이 모듈에서 유일하게 설계를 막는 값이고, "
        f"가열 감쇄 {HEAT_DERATE} 는 계획값이다. 시편 몇 장으로 "
        f"{HEAT_ASSIST_C[0]:.0f}~{HEAT_ASSIST_C[1]:.0f} °C 를 훑으면 나온다.",
        "**유입 패널의 열화 정도를 모른다.** 노후값을 설계값으로 썼는데, 그 "
        "전제가 맞는지는 입고품 시편으로 확인해야 한다. 신품에 가까우면 힘이 "
        f"{peel_force_n(aged=False):,.0f} N 으로 여섯 배가 된다.",
        "**백시트가 한 장으로 벗겨지는지 모른다.** 20 년 된 PET 은 가수분해로 "
        "물러져 있어 뜯다가 찢어질 수 있다. 조각나면 박리의 장점(미분 없음)이 "
        "반쯤 사라진다 — 이것이 연마 대비 우위를 정하는 값이다. 그리고 여기서는 "
        "**약한 외피–심재 면이 오히려 해롭다** — 거기서 먼저 갈라지면 심재만 "
        "남는다.",
        "**시작점은 후보가 생겼지만 확인이 필요하다.** JBR-201 절결이 이미 "
        "백시트를 뚫어 두므로 그리퍼 자리로 쓸 수 있다 "
        "(`jbr_notch_as_a_start_point()`). 다만 그 자리가 판 가운데라 변에서 "
        "당기는 것과 전선 모양이 다르고, 쓸 수 있는지는 시편으로만 안다.",
    )


def summary() -> dict[str, object]:
    """한 눈에 — 시험과 도면 리터럴이 같은 값을 본다."""
    return {
        "tag": UNIT_TAG,
        "between": f"{UPSTREAM_TAG} → {DOWNSTREAM_TAG}",
        "weakestInterface": weakest_interface().key,
        "requiredInterface": required_interface().key,
        "theWeakPlaneIsATrap": the_weak_plane_is_a_trap(),
        "costOfGoingToTheRightPlane": cost_of_going_to_the_right_plane(),
        "mustRemove": sorted(must_remove()),
        "gate": "backsheet",
        "agingHelps": aging_helps(),
        "agingSavesUs": aging_saves_us(),
        "heatSavesUs": heat_saves_us(),
        "peelForceN": peel_force_n(),
        "peelForceFreshN": peel_force_n(aged=False),
        "peelForceHeatedN": heat_brings_it_to_n(),
        "weakPlaneForceN": peel_force_n(weakest_interface()),
        "peelEnergyJ": peel_energy_j(),
        "lineTaktS": line_takt_s(),
        "methodCount": len(METHODS),
        "solventFreeCount": len(solvent_free_methods()),
        "recommended": recommended().key,
        "tearRiskIsAlreadySpecified": tear_risk_is_already_specified(),
        "upstreamConditionCount": len(upstream_conditions()),
    }
