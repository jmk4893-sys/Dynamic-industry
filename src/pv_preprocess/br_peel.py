# -*- coding: utf-8 -*-
"""BR-306 백시트 박리 — **어느 면에서 뜯을지가 설계다.**

`br_abrade` 는 백시트를 갈아서 없앤다. 그 유닛을 짓고 나서 드러난 것이,
부유선별이 목적이면 연마에 **되돌아오는 칼**이 있다는 것이었다 — 없애는 게
아니라 더 고운 가루로 바꾸고, 안 잡힌 가루는 자기가 대신한 필름보다 해롭다.
필름째 떼면 미분이 아예 안 생긴다. 그래서 박리를 다시 본다.

박리를 못 쓴다고 본 이유는 「오래된 패널은 접착이 세고 백시트가 부스러져
잡을 데가 없다」였다. **앞은 반만 맞고 뒤는 면을 잘못 골라서 생긴 말이다.**

  ① **접착은 세월이 갈수록 약해진다.** 백시트–EVA 박리력은 신품 60~100 N/cm
     인데 습열 300 h 만에 20 N/cm 로 내려가고, 그 뒤로도 계속 떨어진다.
     노후 패널이 박리에 **불리한 게 아니라 유리하다.**
  ② **그런데 거기가 뜯을 면이 아니다.** 백시트는 그 자체가 3층 적층이다 —
     불소 외피 / PET 심재 / 불소 내피. 야외 노출된 모듈에서 실제로 벌어지는
     곳은 EVA 계면이 아니라 **외피와 심재 사이 접착층**이고, 현장 박리가
     일어나는 문턱이 100 J/m² = 0.1 N/mm 다. 백시트–EVA 의 **20 분의 1** 이다.

그리고 이것이 우연이 아니다. 부유선별을 망치는 것은 **불소 외피**다 —
표면에너지가 낮아 시약 없이 저절로 뜨고 억제도 안 된다. PET 은 밀도 1.38 로
가라앉고 극성이 있어 억제제로 눌린다(리그닌설포네이트·알칼리 전처리 등
선별 문헌에 방법이 있다). 즉

    **가장 약한 면과, 오염원이 얹혀 있는 면이 같은 면이다.**

그러니 백시트를 통째로 EVA 에서 뜯을 이유가 없다. 불소 외피만 그 약한 면에서
벗기면 오염원이 빠지고, 남는 PET·EVA 는 하류가 이미 다룰 수 있는 물건이 된다.
`the_weak_plane_is_the_dirty_plane()` 이 그것을 판정한다.

이 모듈은 값을 정하지 않는다 — **면을 고르고, 공법 후보를 같은 잣대로 세운다.**
실측이 오면 `INTERFACES` 의 Gc 만 고치면 된다.

    PYTHONPATH=src python -c "from pv_preprocess import br_peel; print(br_peel.summary())"
"""

from __future__ import annotations

from dataclasses import dataclass

from . import campaign, sg_grind

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
    carries_fluoropolymer: bool  # 여기를 떼면 불소가 빠지는가
    basis: str


#: 계면 표. 노후값이 설계값이다 — 우리가 받는 것은 20 년 된 패널이다.
INTERFACES: tuple[Interface, ...] = (
    Interface(
        "fluoro_pet", "불소 외피 ↔ PET 심재 (백시트 내부)", "불소 외피만",
        0.60, 0.10, True,
        "현장 박리가 일어나는 문턱이 100 J/m² = 0.1 N/mm 로 보고돼 있고, "
        "PA·PET·PVDF 계 백시트 다수에서 **외피–심재 접착층이 노출과 함께 "
        "약해지는** 것이 관찰됐다. 신품값은 계획값이다"),
    Interface(
        "backsheet_eva", "백시트 ↔ EVA", "백시트 3층 전부",
        8.00, 2.00, True,
        "신품 180° 박리 60~100 N/cm(6~10 N/mm), 습열 300 h 에 20 N/cm"
        "(2 N/mm)까지 내려가고 그 뒤로도 계속 떨어진다"),
    Interface(
        "eva_cell", "EVA ↔ 셀", "EVA + 백시트", 12.00, 6.00, True,
        "여기를 노리면 셀이 따라 나온다 — 전처리 단계에서 할 일이 아니다. "
        "값은 자릿수만 맞춘 계획값이다"),
)

#: 부유선별을 망치는 성분 — 이것이 어느 면 위에 있는지가 설계를 정한다.
CONTAMINANT = "불소 폴리머 (PVF/PVDF 외피)"
#: 그 아래 PET 심재의 밀도 (g/cm³). 물보다 무거워 가라앉고, 극성이 있어
#: 억제제가 듣는다 — 불소와 달리 하류가 **다룰 수 있는** 물건이다.
PET_DENSITY_G_CM3 = 1.38

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


def shallowest_interface_that_removes_the_contaminant() -> Interface:
    """오염원을 걷어내는 면 중 **가장 얕은** 것.

    깊이 갈수록 딸려 나오는 것이 많아지므로, 오염원만 빠지면 거기서 멈춘다.
    """
    for iface in INTERFACES:
        if iface.carries_fluoropolymer:
            return iface
    raise AssertionError("불소를 지고 있는 면이 하나도 없다 — 표가 틀렸다")


def the_weak_plane_is_the_dirty_plane() -> bool:
    """**이 모듈의 요지** — 가장 약한 면과 오염원이 얹힌 면이 같은가.

    같다. 그래서 「세게 뜯어야 한다」와 「오염원을 빼야 한다」가 서로
    싸우지 않는다. 백시트를 통째로 EVA 에서 뜯을 이유가 없다.
    """
    return weakest_interface().key == shallowest_interface_that_removes_the_contaminant().key


def aging_helps() -> bool:
    """세월이 박리를 **돕는가** — 처음에 반대로 알고 있던 것이다."""
    return all(i.gc_aged_n_mm < i.gc_fresh_n_mm for i in INTERFACES)


# ── 그 면을 뜯는 데 드는 힘 ─────────────────────────────────────────────
def peel_force_n(iface: Interface | None = None, *,
                 aged: bool = True, heated: bool = False) -> float:
    """한 면을 폭 전체에서 뜯는 힘 (N) = Gc × 패널 폭.

    두께가 안 들어간다 — 계면 일이라 백시트가 얼마나 두껍든 같다.
    """
    iface = iface or weakest_interface()
    gc = iface.gc_aged_n_mm if aged else iface.gc_fresh_n_mm
    if heated:
        gc *= HEAT_DERATE
    return round(gc * float(campaign.PANEL_WIDTH_MM), 1)


def peel_energy_j(iface: Interface | None = None, **kw) -> float:
    """그 면을 끝까지 뜯는 일 (J/장) = 힘 × 패널 길이."""
    return round(peel_force_n(iface, **kw)
                 * float(campaign.PANEL_LENGTH_MM) / 1_000.0, 1)


def easier_than_full_backsheet_by() -> float:
    """약한 면을 고르면 몇 배 쉬운가 — 백시트를 통째로 뜯는 것과 견준다."""
    full = next(i for i in INTERFACES if i.key == "backsheet_eva")
    return round(peel_force_n(full) / peel_force_n(), 1)


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
    """왜 `br_abrade` 대신 이쪽을 먼저 보는가 — 부유선별이 목적일 때."""
    return (
        "연마는 백시트를 없애는 게 아니라 **더 고운 가루로 바꾼다.** 박리는 "
        "필름째 떼므로 미분이 아예 안 생긴다 — 포집률이 품질 사양이 될 일도 없다.",
        f"뜯을 면을 잘 고르면 힘이 {peel_force_n():,.0f} N 이다. 백시트를 통째로 "
        f"EVA 에서 뜯는 {peel_force_n(next(i for i in INTERFACES if i.key=='backsheet_eva')):,.0f} N "
        f"의 {easier_than_full_backsheet_by()} 분의 일이고, 가열까지 얹으면 "
        f"{heat_brings_it_to_n():,.0f} N 까지 내려간다.",
        f"남는 PET 은 밀도 {PET_DENSITY_G_CM3} 로 가라앉고 극성이 있어 억제제가 "
        "듣는다. 불소와 달리 **하류가 이미 다룰 수 있는** 물건이라, 오염 문제가 "
        "사라지는 게 아니라 **풀리는 문제로 바뀐다.**",
        f"집진도 통째로 안 든다. `br_abrade` 는 {sg_grind.backsheet_dust_kg_per_h():,.1f} kg/h "
        "의 가연성 불소 분진과 그것을 받는 별도 계통이 전제였다.",
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
        "**불소 외피가 한 장으로 벗겨지는지 모른다.** 문헌의 100 J/m² 는 현장 "
        "박리 문턱이지 「깨끗하게 한 장으로 떨어진다」는 뜻이 아니다. 찢어져 "
        "조각나면 박리의 장점(미분 없음)이 반쯤 사라진다 — 이것이 연마 대비 "
        "우위를 정하는 값이다.",
        "**그리퍼가 시작점을 어떻게 만드는지가 안 정해졌다.** 계면 박리는 "
        "균열을 시작할 자리가 있어야 한다. 모서리를 한 줄 긋는 것으로 될지, "
        "별도 수단이 필요할지는 시편을 봐야 안다.",
    )


def summary() -> dict[str, object]:
    """한 눈에 — 시험과 도면 리터럴이 같은 값을 본다."""
    full = next(i for i in INTERFACES if i.key == "backsheet_eva")
    return {
        "tag": UNIT_TAG,
        "between": f"{UPSTREAM_TAG} → {DOWNSTREAM_TAG}",
        "weakestInterface": weakest_interface().key,
        "contaminantInterface": shallowest_interface_that_removes_the_contaminant().key,
        "theWeakPlaneIsTheDirtyPlane": the_weak_plane_is_the_dirty_plane(),
        "agingHelps": aging_helps(),
        "peelForceN": peel_force_n(),
        "peelForceFreshN": peel_force_n(aged=False),
        "peelForceHeatedN": heat_brings_it_to_n(),
        "fullBacksheetForceN": peel_force_n(full),
        "easierThanFullBacksheetBy": easier_than_full_backsheet_by(),
        "peelEnergyJ": peel_energy_j(),
        "lineTaktS": line_takt_s(),
        "methodCount": len(METHODS),
        "solventFreeCount": len(solvent_free_methods()),
        "recommended": recommended().key,
    }
