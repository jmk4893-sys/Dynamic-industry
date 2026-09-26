# -*- coding: utf-8 -*-
"""BR-306 백시트 박리 — **약한 면은 덫이었다.**

`br_abrade` 가 백시트를 갈아 없애는 유닛이라면 이쪽은 필름째 떼는 대안이다.
**다만 한 공정이 아니라 둘이다** — 라미네이트에는 칼날이 들어갈 틈이 애초에
없어서, 1 차로 변에서 30 mm 안쪽에 **폭 전체를 가로질러 한 줄** 긋고(그 띠가
들려 진입구가 된다) **2 차 커팅**이 따른다 (`stages()`). 시작점은 찾는 것이
아니라 **만드는 것**이고, 그 절단선은 **셀 위**를 지난다.

**현장은 그 2 차를 「2 차 커팅」이라 부르는데 그것이 곧 박리다.** 도면 글자만
보고 「절단이 한 번 더 있다」로 읽었다가 고쳤다 — 절단은 1 차 한 번뿐이고
그 다음은 계면을 벗기는 일이다 (`the_word_cutting_names_the_peel()`).
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

    2,800 N   백시트–EVA · 노후 (설계값) — **폭 전체 합**
    1,400 N   거기에 가열까지
   11,200 N   신품이었다면

그리고 그 합을 한 점이 받지 않는다. 백시트는 **길이 방향 7 장**으로 벗겨지고
그 장수가 칼날 수다 — 한 장이 폭 200 mm 띠를 물어 **400 N**(가열 시 200 N)을
받는다. 합은 그대로고 사양을 정하는 값만 7 분의 1 이 된다.

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

# ── 1 차 커팅 — 칼날이 들어갈 틈을 **만든다** ───────────────────────────
#
#   **백시트를 바로 벗겨낼 수 없다.** 계면 박리는 칼날이 들어갈 틈이 있어야
#   시작되는데 라미네이트에는 애초에 틈이 없다 — 백시트가 EVA 에 면으로
#   붙어 변까지 이어져 있어 들어갈 자리가 없다.
#
#   그래서 공정이 **둘로 갈린다.**
#
#       ① 1 차 커팅 — 변에서 **30 mm 안쪽**에, **폭 전체를 가로질러** 한 줄
#                      긋는다. 그 30 mm 띠가 들려 진입구가 된다.
#       ② 2 차 커팅 — **이것이 박리다.** 현장이 박리를 「2 차 커팅」이라
#                      부른다. 칼날이 그 틈으로 들어가 계면을 잡고 필름째
#                      벗겨 낸다 — 절단이 한 번 더 있는 것이 아니다.
#
#   **이 자리에서 두 번 틀렸다.** 처음에는 「JBR 절결을 시작점으로 주워 쓸 수
#   있다」로 적었다 — **있는 구멍을 찾는** 발상이었고, 실제 공정은 틈을
#   **만드는** 공정을 따로 둔다. 다음에는 30 mm 를 **절단 길이**로 읽어 짧은
#   슬릿 하나로 모델링했다. 30 mm 는 **변에서 들어온 거리**이고 절단선은 폭
#   1,400 을 다 지른다 — 46.7 배를 짧게 잡고 있었다. 「한 번에 폭 전체를
#   연다」가 그 뜻이다.
#
#   그리고 절단선이 **셀 위**를 지난다. 셀 없는 여백으로 피할 수 없다는
#   뜻이라 깊이 창이 느슨해지는 구간이 없다 — 1,400 mm 내내 창 안에 있어야 한다.

#: 절단선이 변에서 들어온 거리 (mm) — **절단 길이가 아니다.**
#: 이 값만큼의 띠가 들려 칼날이 물 자리가 된다.
STARTER_CUT_OFFSET_MM = 30.0
#: 그 방향 — 판 폭을 가로지른다.
STARTER_CUT_ORIENTATION = "가로(횡)"
#: 절단선이 셀 위를 지나는가 — 지난다. 여백으로 피할 수 없다.
STARTER_CUT_CROSSES_CELLS = True

#: 박리 칼날 수 — **현장이 든 수다.** 백시트는 길이 방향 **7 장**으로 벗겨지고
#: 그 장수가 곧 칼날 수다. 이 값 하나가 그리퍼·구동 사양을 정한다.
BLADE_COUNT = 7
#: 띠가 나뉘는 방향 — **길이 방향**이다. 1 차 커팅(가로)과 직각이다.
STRIP_ORIENTATION = "세로(길이 방향)"
#: 칼날 배치 — 나란히가 아니라 **진행 방향으로 어긋난 계단식**이다.
#: 앞선 칼날이 먼저 물고 나머지가 차례로 물리는데, 캐리지는 하나라
#: **진행은 다 같이** 한다. 「병렬이냐 순차냐」가 아니라 **둘 다**다.
BLADE_LAYOUT = "계단식(중앙이 먼저, 좌우 쌍이 한 단씩 물러남)"

# ── 실측 형상 — SHK-101 계단형 핫나이프 ─────────────────────────────────
#
#   **이 값들은 내가 정한 것이 아니다.** 같은 저장소의 다른 작업
#   (SHK-101 계단형 핫나이프 · 콘솔 도면의 `KNIFE_*` 뿌리 상수 ·
#   `tools/knife_stepped.py`)이 발주자 스케치에서 확정한 값이고, 그쪽이
#   **정본**이다. 그 브랜치가 이 트리에 아직 없어 값을 **베껴** 두는데,
#   베끼는 것은 갈라질 자리이므로 조건을 하나 붙인다:
#
#       `tools/console_consts.py` 가 이 트리에 생기면 아래 상수를 지우고
#       그쪽에서 읽어 온다. `the_mirror_must_become_a_delegation()` 이
#       그때 실패해서 알려 준다.
#
#   형상은 **대칭 계단**이다 — 중앙 300 이 먼저 물고 양쪽 200 칼날이 한 단에
#   80 씩 물러나며 세 단을 내려간다. 전폭 1,500 은 패널 1,400 에 양쪽 50 을
#   더한 것이고, 바깥 칼날은 안쪽 칼날 **밑으로 15** 겹쳐 덮는 자리를 남기지
#   않는다.
#
#: 중앙 칼날 폭 (mm) — 가장 먼저 물고 **가장 넓다**.
CENTER_BLADE_MM = 300.0
#: 계단 칼날 폭 (mm) — 중앙 양쪽으로 한 단씩.
STEP_BLADE_MM = 200.0
#: 한쪽 단수 — 좌우 합쳐 칼날이 1 + 2×3 = 7 장이 된다.
STAGGER_STEPS = 3
#: 한 단에 뒤로 물러나는 거리 (mm) — **발주자 확정.** 어제 「모른다」고
#: 적어 둔 그 값이다.
STAGGER_RISE_MM = 80.0
#: 이음 겹침 (mm) — **바깥 칼날이 안쪽 밑으로.** 힘을 보태지 않는다:
#: 안쪽 칼날이 이미 떼어 간 줄을 다시 긋는 자리다.
BLADE_LAP_MM = 15.0
#: 칼날 밑면 랜드 (mm) — 추종 중 **유리를 타는** 면. 경면 연마.
BLADE_LAND_MM = 1.5
#: 날끝 쐐기각 (°) — 레이크면과 랜드 사이 (D-502).
BLADE_WEDGE_DEG = 35.0
#: SHK-101 이 재는 박리 저항 (N/mm) — OI-01 밴드 상한 111 N/cm.
#: **내 `INTERFACES` 와 다른 계면의 값이다** — 아래 주의를 읽을 것.
SHK101_PEEL_N_MM = 11.14

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


# ── 그 힘을 몇 장이 나눠 받는가 ─────────────────────────────────────────
#
#   합은 안 바뀌지만 **한 장이 받는 값이 바뀐다.** 그리퍼·구동은 합이 아니라
#   한 장이 받는 값으로 고르므로 이쪽이 사양을 정하는 값이다.

def knife_width_mm() -> float:
    """칼날 전폭 (mm) = 중앙 + 양쪽 계단. 패널보다 넓다."""
    return CENTER_BLADE_MM + 2 * STAGGER_STEPS * STEP_BLADE_MM


def blade_length_sum_mm() -> float:
    """인서트 길이의 합 (mm) — 전폭에 이음 겹침을 더한 값이다."""
    return knife_width_mm() + 2 * STAGGER_STEPS * BLADE_LAP_MM


def overhang_each_side_mm() -> float:
    """칼날이 패널 밖으로 나가는 폭 (mm) — 한쪽."""
    return round((knife_width_mm() - float(campaign.PANEL_WIDTH_MM)) / 2, 1)


@dataclass(frozen=True)
class Segment:
    """칼날 조각 하나 — 명목 구간과 뒤로 물러난 거리."""

    step: int                   # 0 = 중앙, 1..STAGGER_STEPS = 계단
    y0: float                   # 명목 구간 (패널 중심 기준 mm)
    y1: float
    back_mm: float              # 중앙 칼끝에서 뒤로 물러난 거리

    @property
    def nominal_width_mm(self) -> float:
        return round(self.y1 - self.y0, 1)

    @property
    def engaged_mm(self) -> float:
        """패널(±폭/2) 안에 든 폭 — **힘은 이 폭에서만 나온다.**"""
        half = float(campaign.PANEL_WIDTH_MM) / 2
        return round(max(0.0, min(half, self.y1) - max(-half, self.y0)), 1)


def blade_segments() -> tuple[Segment, ...]:
    """칼날 조각 표 — 중앙부터 바깥으로, 좌우 한 쌍씩.

    겹침은 넣지 않는다. 바깥 칼날이 안쪽 **밑으로** 들어가 이미 떼어 간 줄을
    다시 긋는 자리라 힘을 보태지 않기 때문이다.
    """
    half_c = CENTER_BLADE_MM / 2
    out = [Segment(0, -half_c, half_c, 0.0)]
    for k in range(1, STAGGER_STEPS + 1):
        a = half_c + (k - 1) * STEP_BLADE_MM
        b = a + STEP_BLADE_MM
        out += [Segment(k, a, b, k * STAGGER_RISE_MM),
                Segment(k, -b, -a, k * STAGGER_RISE_MM)]
    return tuple(out)


def engaged_width_mm() -> float:
    """조각들이 패널 안에서 무는 폭의 합 (mm) — 패널 폭이어야 한다."""
    return round(sum(s.engaged_mm for s in blade_segments()), 1)


def strip_widths_mm() -> tuple[float, ...]:
    """조각별 패널 안 폭 (mm) — **균일하지 않다.**

    바깥 단은 전폭이 패널보다 넓어 일부가 패널 밖으로 나간다.
    """
    return tuple(s.engaged_mm for s in blade_segments())


def widest_strip_mm() -> float:
    """가장 넓은 조각의 폭 (mm) — **사양을 정하는 조각**이다. 중앙이다."""
    return max(strip_widths_mm())


def peel_travel_mm() -> float:
    """띠 한 장을 끝까지 벗기는 진행 거리 (mm).

    띠가 **길이 방향**이라 진행도 길이 방향이다 — 1 차 커팅(가로)에서
    출발해 판 길이만큼 간다.
    """
    return float(campaign.PANEL_LENGTH_MM)


# ── 계단식이 바꾸는 것과 안 바꾸는 것 ───────────────────────────────────
#
#   칼날 i 는 캐리지가 `(i-1)·p` 갔을 때 물고 거기서 띠 길이 `L` 을 더 간 뒤
#   빠진다. 그러니 **첫 칼날과 마지막 칼날이 겹치느냐**가 전부다.
#
#       (n-1)·p ≤ L  →  한때 전부 물린다  →  최대 합력은 **안 내려간다**
#       (n-1)·p > L  →  다 물리는 순간이 없다 →  그만큼 내려간다
#
#   경계는 `L/(n-1)` 이고 이 판에서 417 mm 다. 머리를 조금이라도 컴팩트하게
#   짜면 반드시 그 아래이므로 **실질적으로 최대 합력은 2,800 N 그대로다.**
#   박리력은 *그 순간 벗겨지는 폭*에 걸리는데, 정상 상태에서는 어긋나 있든
#   나란하든 폭 1,400 이 다 벗겨지고 있기 때문이다.
#
#   **그럼 계단식이 사 주는 것은 최대값이 아니라 기울기다.** 일자로는
#   0 → 2,800 N 이 한 걸음에 서고, 계단식은 일곱 계단을 밟는다 —
#   상승률이 1/n 이다. 구동이 겁내는 것은 최대값보다 이쪽이다.

def stagger_spread_mm(rise_mm: float | None = None) -> float:
    """첫 칼끝에서 마지막 칼끝까지 (mm) = **단수** × 단높이.

    한때 `(n−1)·p` 로 적었는데 그것은 일곱이 **한 줄로** 늘어선 경우다.
    실제는 좌우 쌍이 같은 단을 쓰는 **대칭 계단**이라 퍼짐이 절반이다 —
    6×80 = 480 이 아니라 3×80 = 240.
    """
    return round(STAGGER_STEPS * (STAGGER_RISE_MM if rise_mm is None
                                  else max(rise_mm, 0.0)), 1)


def all_blades_engage_at_once(rise_mm: float | None = None) -> bool:
    """퍼짐이 띠 길이보다 짧은가 — 짧으면 한때 전부 물린다.

    경계는 칼날 수가 아니라 **퍼짐 대 띠 길이**다.
    """
    return stagger_spread_mm(rise_mm) <= peel_travel_mm()


def rise_below_which_all_engage_mm() -> float:
    """이 단높이 **아래**면 한때 전부 물린다 (mm) = 띠 길이 / 단수."""
    return round(peel_travel_mm() / STAGGER_STEPS, 1)


def peak_force_n(rise_mm: float | None = None, **kw) -> float:
    """라인이 한 번은 내야 하는 최대 합력 (N).

    조각 하나는 캐리지가 `back` 갔을 때 물고 거기서 띠 길이를 더 간 뒤
    빠진다. 어느 진행 위치에서 동시에 물린 조각들의 힘 합이 가장 큰가를 본다.
    퍼짐이 띠 길이 안이면 그 값이 폭 전체 값이다.
    """
    r = STAGGER_RISE_MM if rise_mm is None else max(rise_mm, 0.0)
    segs = blade_segments()
    backs = [s.step * r for s in segs]
    L = peel_travel_mm()
    best = 0.0
    for x in backs:                                  # 물림이 늘어나는 순간만 보면 된다
        live = sum(peel_force_on_segment_n(s, **kw)
                   for s, b in zip(segs, backs) if b <= x <= b + L)
        best = max(best, live)
    return round(best, 1)


def carriage_travel_mm(rise_mm: float | None = None) -> float:
    """캐리지가 실제로 가야 하는 거리 (mm) = 퍼짐 + 띠 길이.

    띠 한 장은 여전히 `peel_travel_mm()` 만 벗겨지지만, 바깥 칼끝이 패널
    뒤끝을 벗어나려면 캐리지는 퍼짐만큼 더 간다.
    """
    return round(stagger_spread_mm(rise_mm) + peel_travel_mm(), 1)


def stagger_lowers_the_peak(rise_mm: float | None = None) -> bool:
    """이 단높이가 최대 합력을 실제로 낮추는가 — 경계를 넘어야 낮춘다."""
    return not all_blades_engage_at_once(rise_mm)


def load_rise_is_divided_by() -> int:
    """진입 하중이 몇 걸음에 나눠 서는가 — **단수 + 1** 이다.

    칼날 수(7)가 아니다. 좌우 쌍이 같은 단에서 **같이** 물기 때문에
    걸음이 조각 수보다 적다 — 3 단이면 4 걸음이다.
    """
    return STAGGER_STEPS + 1


def engagement_ramp() -> tuple[tuple[float, float, float], ...]:
    """물림 램프 — (진행 mm, 물린 폭 mm, 그때 합력 N).

    중앙 칼끝이 패널 앞끝에 닿은 뒤 단높이만큼 갈 때마다 한 단씩 더 문다.
    """
    out, prev = [], 0.0
    for k in range(STAGGER_STEPS + 1):
        w = sum(s.engaged_mm for s in blade_segments() if s.step <= k)
        out.append((k * STAGGER_RISE_MM, round(w, 1),
                    round(_gc(None, True, False) * w, 1)))
        prev = w
    return tuple(out)


def what_the_staircase_buys() -> tuple[str, ...]:
    """계단식이 사 주는 것과 **안** 사 주는 것 — 헷갈리기 쉬운 자리다."""
    edge = rise_below_which_all_engage_mm()
    ramp = engagement_ramp()
    return (
        f"**최대 합력은 안 내려간다.** 퍼짐 {stagger_spread_mm():,.0f} mm 가 "
        f"띠 길이 {peel_travel_mm():,.0f} mm 안이라 **한때 조각이 전부 물린다** "
        f"— 그 순간 {peel_force_n():,.0f} N 이다. 박리력은 그 순간 벗겨지는 "
        "**폭**에 걸리는데, 정상 상태의 폭은 배치와 무관하게 패널 폭 "
        f"{float(campaign.PANEL_WIDTH_MM):,.0f} mm 다.",
        f"**대신 진입이 {load_rise_is_divided_by()} 걸음에 나뉜다** — 물린 폭이 "
        + " → ".join(f"{w:,.0f}" for _, w, _ in ramp) + " mm 로 늘고 합력이 "
        + " → ".join(f"{f:,.0f}" for _, _, f in ramp) + " N 로 따라 오른다. "
        f"일자로는 0 → {peel_force_n():,.0f} N 이 한 걸음에 선다. 걸음이 "
        f"조각 수 {BLADE_COUNT} 가 아니라 {load_rise_is_divided_by()} 인 것은 "
        "**좌우 쌍이 같은 단에서 같이 물기** 때문이다.",
        "**그리고 균열을 한 단씩만 틔운다.** 붙은 것을 처음 떼는 힘이 이미 "
        "벌어진 것을 계속 떼는 힘보다 크다. 일자형은 그 기동력이 전폭으로 "
        "한꺼번에 서고, 계단식은 중앙 몫부터 한 단씩이다. 이쪽은 최대값 "
        "자체를 낮추는데, **기동/정상 비를 모르므로 값으로 안 적는다.**",
        f"**합력을 정말 낮추려면 단높이를 {edge:,.0f} mm 넘게 벌려야 하고 "
        f"그러면 행정이 {carriage_travel_mm(edge):,.0f} mm 로 "
        f"{carriage_travel_mm(edge) / peel_travel_mm():.1f} 배가 된다.** "
        f"실제 단높이는 {STAGGER_RISE_MM:g} mm 라 그 십 분의 일도 안 된다 — "
        "애초에 거래가 아니다.",
    )


def the_mirror_must_become_a_delegation() -> bool:
    """베낀 값이 아직 베낀 채로 있어도 되는가 — 정본이 이 트리에 없으면 참.

    `tools/console_consts.py` 가 생기면(SHK-101 쪽이 병합되면) 거짓이 되어
    시험이 깨진다. **그때 위 상수를 지우고 그쪽에서 읽어 와야 한다.**
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    return not (root / "tools" / "console_consts.py").exists()


def where_shk101_and_this_unit_disagree() -> tuple[str, ...]:
    """**형상은 같고 계면이 다르다** — 값을 베끼며 드러난 것이라 적어 둔다.

    SHK-101 의 형상(칼날 7 · 계단 · 단높이 80 · 겹침 15)은 현장이 나에게
    말해 준 것과 같다. 그런데 **그 칼날이 무는 계면이 내 모델과 다르다.**
    어느 쪽이 맞는지는 내가 정할 일이 아니라서 판정을 안 만든다.
    """
    mine = required_interface()
    return (
        f"**SHK-101 은 유리 계면을 문다.** 랜드 {BLADE_LAND_MM:g} mm 가 "
        f"추종 중 **유리를 타고**(경면 연마) 칼끝이 그 위 층 밑으로 들어가 "
        "**셀모듈과 백시트를 함께** 들어 올린다. 칼날 온도 200 ℃ 주석도 "
        "「유리 계면만 문다」고 적혀 있다.",
        f"**이 모듈은 백시트–EVA 를 뜯는다.** `{mine.key}` · 노후 Gc "
        f"{mine.gc_aged_n_mm:g} N/mm. 백시트만 떼고 셀은 남기는 공정이다.",
        f"**그래서 폭당 힘이 {SHK101_PEEL_N_MM / mine.gc_aged_n_mm:.2f} 배 "
        f"차이난다** — SHK-101 {SHK101_PEEL_N_MM:g} N/mm(OI-01 상한 111 N/cm · "
        f"폭 1,400 에서 {SHK101_PEEL_N_MM * campaign.PANEL_WIDTH_MM / 1000:.2f} kN) "
        f"대 이쪽 {mine.gc_aged_n_mm:g} N/mm({peel_force_n():,.0f} N).",
        "**둘 중 무엇이 실제 공정인지 안 들었다.** 유리 계면에서 한 번에 다 "
        "들면 백시트를 따로 뜯는 공정이 없어도 되고, 따로 뜯으면 SHK-101 "
        "뒤에 이 유닛이 선다. 형상 값은 어느 쪽이든 같으므로 받아 썼고, "
        "**계면과 힘은 안 바꿨다** — 그것은 유닛이 있느냐를 정하는 물음이다.",
        "그리고 SHK-101 쪽도 그 힘을 잠정으로 든다 — OI-01 밴드는 **탠덤 시절 "
        "두 계면의 합**을 잰 값이고 계단 칼날로 파일럿 PT-01 이 다시 잰다고 "
        "적혀 있다.",
    )


def the_staircase_splits_the_supports_for_us() -> bool:
    """계단식이 「지지도 나뉘어야 한다」는 조건을 저절로 지키는가 — 지킨다.

    칼날이 진행 방향으로 서로 다른 자리에 있으니 **애초에 크로스빔 하나에
    못 건다.** `the_split_needs_split_supports()` 가 경고한 위험을 배치가
    구조적으로 막아 준다 — 조건을 지키려고 애쓸 필요가 없다.
    """
    return "계단식" in BLADE_LAYOUT


def _gc(iface: Interface | None, aged: bool, heated: bool) -> float:
    iface = iface or required_interface()
    gc = iface.gc_aged_n_mm if aged else iface.gc_fresh_n_mm
    return gc * HEAT_DERATE if heated else gc


def peel_force_on_segment_n(seg: Segment, iface: Interface | None = None, *,
                            aged: bool = True, heated: bool = False) -> float:
    """조각 하나가 받는 힘 (N) = Gc × 그 조각이 패널 안에서 무는 폭."""
    return round(_gc(iface, aged, heated) * seg.engaged_mm, 1)


def peel_force_per_blade_n(iface: Interface | None = None, *,
                           aged: bool = True, heated: bool = False) -> float:
    """**가장 무거운** 조각이 받는 힘 (N) = Gc × 가장 넓은 조각.

    사양은 평균이 아니라 최악 조각으로 고른다. 한때 판 폭을 칼날 수로 그냥
    나눠 200 mm·400 N 으로 적었는데, 실제 형상은 중앙이 300 mm 라 **1.5 배**
    무겁다. 균일하다고 가정한 것이 틀렸다.
    """
    return round(_gc(iface, aged, heated) * widest_strip_mm(), 1)


def per_blade_relief() -> float:
    """최악 조각이 합보다 몇 배 가벼운가 — **칼날 수가 아니다.**

    폭이 균일하면 칼날 수가 되겠지만 중앙이 넓어 그보다 작다.
    """
    return round(peel_force_n() / peel_force_per_blade_n(), 2)


def total_force_is_conserved() -> bool:
    """조각으로 나눠도 **합은 그대로인가** — 그대로다.

    나뉘는 것은 한 조각이 받는 값이지 일의 총량이 아니다. 조각별 힘을 다
    더하면 폭 전체 값이 나온다 — 겹침은 힘을 안 보태므로 세지 않는다.
    """
    each = sum(peel_force_on_segment_n(s) for s in blade_segments())
    return abs(each - peel_force_n()) <= 1.0


def the_load_is_carried_by_seven_not_one() -> bool:
    """**이 절의 요지** — 합을 한 점이 받는 것으로 잡으면 과설계가 된다.

    한때 「폭을 나누는 절단이 없으니 2,800 N 을 한 번에 간다」고 적었다.
    절단이 나누지 않는 것은 맞았지만 **칼날이 나눈다** — 7 장이 각각
    띠 하나를 문다.
    """
    return BLADE_COUNT > 1 and total_force_is_conserved()


# ── 왜 일곱으로 나누는가 — 힘이 아니라 **굽힘**이 이유다 ────────────────
#
#   칼날은 보(beam)다. 폭 방향으로 박리력이 고르게 걸리므로 등분포하중을
#   받는 보이고, 모멘트는 `wL²/8`, 처짐은 `5wL⁴/384EI` 로 간다.
#   **길이를 1/7 로 자르면 힘은 7 배, 모멘트는 7² = 49 배, 처짐은
#   7⁴ = 2,401 배 가벼워진다.** 박리에서 정작 무너지는 것은 힘이 아니라
#   **날이 휘어 깊이가 흐트러지는 것**이므로 이 2,401 이 진짜 이유다.
#
#   **다만 지지도 같이 나뉘어야 한다.** 일곱 장을 크로스빔 하나에 매달면
#   그 빔이 여전히 1,400 을 건너지르며 합을 다 받는다 — 날끝 힘만 1/7 이
#   되고 강성 이득은 0 이다. `the_split_needs_split_supports()`.

def one_piece_blade_span_mm() -> float:
    """일자형 한 장이 건너질러야 하는 거리 (mm) — **칼날 전폭**이다.

    판 폭이 아니다. 칼날은 양쪽으로 나가 있으므로 건너지를 거리는 1,500 이다.
    """
    return knife_width_mm()


def span_ratio() -> float:
    """일자형 span 이 **가장 넓은 조각**의 몇 배인가 — 여기서 n² · n⁴ 가 나온다.

    조각 폭이 균일하지 않으므로 칼날 수(7)가 아니다. 사양은 최악 조각으로
    고르니 분모도 가장 넓은 조각이어야 한다 — 1,500 / 300 = 5.
    """
    return round(one_piece_blade_span_mm() / widest_strip_mm(), 3)


def bending_moment_ratio() -> float:
    """일자형 대비 분할이 굽힘모멘트를 몇 배 덜 받는가 = span 비².

    `M = wL²/8` 에서 w 가 같고 L 만 1/k 이 되므로 k² 이다. 한때 칼날 수를
    그대로 썼는데(49), 조각 폭이 균일하지 않아 실제 비는 그보다 작다.
    """
    return round(span_ratio() ** 2, 1)


def deflection_ratio() -> float:
    """같은 단면일 때 처짐이 몇 배 줄어드는가 = span 비⁴.

    `δ ∝ wL⁴/EI`. **이 값이 분할의 진짜 이유다** — 힘보다 훨씬 크게 준다.
    """
    return round(span_ratio() ** 4, 1)


def stiffness_beats_force_as_the_reason() -> bool:
    """분할의 이유가 힘이 아니라 강성인가 — 그렇다.

    힘 이득은 n 배뿐인데 처짐 이득은 n⁴ 배다. 「한 장이 2,800 N 을 못
    버텨서」로 읽으면 이유를 가장 작은 것으로 잡는 셈이다.
    """
    return deflection_ratio() > per_blade_relief()


def the_split_needs_split_supports() -> tuple[str, ...]:
    """분할이 헛되지 않으려면 붙는 조건 — 지지도 같이 나뉘어야 한다."""
    return (
        f"위의 {bending_moment_ratio():.0f} 배·{deflection_ratio():,.0f} 배는 "
        "**칼날마다 지지가 따로일 때만** 나온다. 날을 잘라도 그것을 매단 "
        f"부재가 폭 {one_piece_blade_span_mm():,.0f} mm 를 그대로 건너지르면 "
        "L 이 안 줄어 모멘트도 처짐도 그대로다.",
        f"일곱 장을 크로스빔 하나에 매달면 그 빔이 합 {peel_force_n():,.0f} N "
        f"을 다 받는다 — 날끝 힘만 {peel_force_per_blade_n():,.0f} N 으로 "
        "내려가고 **강성 이득은 0** 이다.",
        "그래서 각 날이 **자기 스프링·자기 액추에이터**로 뜨고 가라앉아야 "
        "판의 휨을 따라간다. `sg_grind` 의 SR-302 가 「깊이를 기계가 아니라 "
        "**면**에서 잡는다」고 한 것과 같은 답이고, 여기서는 그것을 일곱 번 한다.",
        f"**합은 어느 쪽이든 {peel_force_n():,.0f} N 이다.** 프레임과 구동은 "
        "그 값을 견뎌야 하니, 분할이 덜어 주는 것은 **한 부재가 받는 몫**이지 "
        "라인이 내야 하는 힘이 아니다.",
    )


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


def starter_cut_length_mm() -> float:
    """절단선의 길이 (mm) — **판 폭 전체**다. 한 줄로 폭을 다 연다."""
    return float(campaign.PANEL_WIDTH_MM)


def released_tab_mm2() -> float:
    """들려서 칼날이 물 띠의 넓이 (mm²) = 들어온 거리 × 폭."""
    return round(STARTER_CUT_OFFSET_MM * starter_cut_length_mm(), 1)


def one_cut_opens_the_full_width() -> bool:
    """한 줄로 폭 전체가 열리는가 — 열린다. 여러 번 긋지 않는다."""
    return starter_cut_length_mm() >= float(campaign.PANEL_WIDTH_MM)


def cut_must_hold_the_window_over_cells() -> bool:
    """절단선이 셀 위를 지나므로 창을 1,400 mm 내내 지켜야 하는가.

    그렇다. 셀 없는 여백으로 피할 수 없으니 깊이 창이 느슨해지는 구간이
    없다 — 연마가 면 전체에서 겪는 것과 같은 문제를 **선 하나**에서 겪는다.
    """
    return STARTER_CUT_CROSSES_CELLS


def stages() -> tuple[tuple[str, str], ...]:
    """이 유닛이 도는 차례 — **둘이다.**"""
    lo, hi = starter_cut_window_mm()
    return (
        ("① 1 차 커팅",
         f"변에서 {STARTER_CUT_OFFSET_MM:.0f} mm 안쪽에 "
         f"{STARTER_CUT_ORIENTATION}으로 **폭 {starter_cut_length_mm():,.0f} mm "
         f"전체를 한 줄** 긋는다. 그 띠({released_tab_mm2():,.0f} mm²)가 들려 "
         f"칼날 진입구가 된다. 깊이는 {lo}~{hi} mm 사이여야 하고, 절단선이 "
         "**셀 위**를 지나므로 그 창이 1,400 mm 내내 지켜져야 한다."),
        ("② 2 차 커팅 (= 박리)",
         f"**현장이 박리를 이렇게 부른다.** 칼날 {BLADE_COUNT} 장이 그 틈으로 "
         f"**{BLADE_LAYOUT}으로** 차례로 들어가 계면을 잡고 백시트를 "
         f"필름째 벗긴다(캐리지는 하나라 진행은 다 같이 한다) — 나오는 것은 한 장이 "
         f"아니라 {STRIP_ORIENTATION} 띠 {BLADE_COUNT} 장이고, 한 장이 폭 "
         f"{CENTER_BLADE_MM:,.0f}(중앙)~{STEP_BLADE_MM:,.0f} mm · 길이 "
         f"{peel_travel_mm():,.0f} mm 다. "
         f"계면 일이라 두께에 안 걸린다. **한 장이 받는 힘 "
         f"{peel_force_per_blade_n():,.0f} N**(가열 시 "
         f"{peel_force_per_blade_n(heated=True):,.0f} N), 합 "
         f"{peel_force_n():,.0f} N — 노후가 {aging_saves_us()} 배, 가열이 "
         f"{heat_saves_us()} 배를 깎는다."),
    )


def the_word_cutting_names_the_peel() -> tuple[str, ...]:
    """현장 말과 물리 이름이 어긋난 자리 — 한 번 틀렸으므로 적어 둔다.

    도면이 ②를 「2 차 커팅」이라 적어서 **또 한 번의 절단**으로 읽었다.
    실제로는 그것이 **박리**다. 공정이 둘이라는 것도, 힘이 계면 일이라는
    것도 처음 모델과 같고, 틀린 것은 **말을 물리로 옮긴 자리**뿐이었다.
    """
    return (
        "현장은 백시트를 떼는 이 단계를 **「2 차 커팅」**이라 부른다. "
        "도면에 그렇게 적혀 있고, 나는 그것을 절단 공정이 하나 더 있는 것으로 "
        "읽어 「무엇을 가르는지 모른다」고 적었다.",
        "**공정은 둘이다** — 1 차 커팅(틈 만들기)과 2 차 커팅(= 박리). "
        "절단은 한 번뿐이고, 그 다음은 계면을 벗기는 일이다.",
        f"그래서 박리력 **합** {peel_force_n():,.0f} N 은 잠정이 아니라 "
        "확정이다 — 폭을 나누는 **절단**이 없으므로 떼어야 할 면이 그대로다. "
        f"다만 그 합을 한 점이 받는 것은 아니다: 칼날 {BLADE_COUNT} 장이 "
        f"각각 자기 띠를 물어 **가장 넓은 조각**({widest_strip_mm():,.0f} mm)이 "
        "받는 값은 "
        f"{peel_force_per_blade_n():,.0f} N 이다. 「절단이 안 나눈다」에서 "
        "「아무것도 안 나눈다」로 건너뛰었던 자리다.",
        "**말이 공정을 가리키지 물리를 가리키지 않는다.** 현장 용어를 물리 "
        "이름으로 그대로 옮기면 이렇게 어긋난다 — 다음에도 같은 자리를 조심한다.",
    )


def a_gap_must_be_made_not_found() -> bool:
    """틈을 **만들어야** 하는가 — 그렇다. 주워 쓸 구멍이 없다.

    이 한 줄이 박리 유닛을 1 공정이 아니라 **2 공정**으로 만든다.
    """
    return STARTER_CUT_OFFSET_MM > 0.0


def starter_cut_window_mm() -> tuple[float, float]:
    """1 차 커팅이 들어가도 되는 깊이 (mm) — 라미네이트가 정하는 창이다.

    연마 절입과 **같은 창**이다. 백시트를 끊을 만큼 깊어야 하고 셀에 닿지
    않을 만큼 얕아야 한다. 정본은 `br_abrade` 가 든다 — 두 곳에 적으면 갈라진다.
    """
    from . import br_abrade
    return br_abrade.depth_window_mm()


def starter_cut_is_the_same_depth_problem() -> bool:
    """1 차 커팅이 연마와 같은 깊이 문제를 안는가 — 안는다.

    그래서 답도 같다: 깊이를 기계가 아니라 **면에서** 잡아야 한다.
    공법이 달라도 창은 라미네이트가 정한다.
    """
    from . import br_abrade
    return starter_cut_window_mm() == br_abrade.depth_window_mm()


def what_the_first_cut_settles() -> tuple[str, ...]:
    """1 차 커팅이 닫는 물음과, 그 대신 여는 물음."""
    lo, hi = starter_cut_window_mm()
    return (
        "**시작점 물음이 닫혔다.** 「그리퍼가 균열을 어디서 시작하나」를 열어 "
        "두고 JBR 절결을 후보로 적었는데, 실제 공정은 **틈을 만드는 공정을 "
        "따로 둔다.** 있는 구멍을 찾는 문제가 아니었다.",
        f"**대신 공정이 둘이 된다.** 1 차 커팅(변에서 "
        f"{STARTER_CUT_OFFSET_MM:.0f} mm · {STARTER_CUT_ORIENTATION} · "
        f"길이 {starter_cut_length_mm():,.0f} mm)이 점유와 부품표에 들어오고, "
        "그 칼날이 백시트 유닛의 별도 부품이 된다.",
        f"**그리고 깊이 문제가 하나 더 생긴다.** 커팅 깊이가 {lo}~{hi} mm 창 "
        "안에 들어야 한다 — 연마가 쓰는 것과 **같은 창**이다. 얕으면 틈이 안 "
        "생기고 깊으면 셀을 긋는다. 답도 같다: 깊이를 면에서 잡는다.",
        f"**자리도 정해졌다 — 셀 위다.** 여백으로 피할 수 없으니 깊이 창이 "
        f"느슨해지는 구간이 없다. 연마가 면 {float(campaign.PANEL_LENGTH_MM) * float(campaign.PANEL_WIDTH_MM) / 1e6:.1f} m² "
        f"에서 겪는 깊이 문제를 커팅은 **선 {starter_cut_length_mm():,.0f} mm** "
        "에서 겪는다 — 면적이 작을 뿐 문제의 성격은 같고, 답도 같다.",
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
        f"**띠 한 장이 {peel_travel_mm():,.0f} mm 를 온전히 가는지 모른다.** "
        f"「한 장으로 벗겨지나」라고 물었었는데 그 물음은 닫혔다 — 한 장이 "
        f"아니라 {BLADE_COUNT} 장이고, 그것이 설계다. 남은 것은 그 띠가 진행 "
        "중에 끊기지 않느냐다. 20 년 된 PET 은 가수분해로 물러져 있어 뜯다가 "
        "찢어질 수 있고, 조각나면 박리의 장점(미분 없음)이 반쯤 사라진다 — "
        "이것이 연마 대비 우위를 정하는 값이다. 그리고 여기서는 **약한 "
        "외피–심재 면이 오히려 해롭다** — 거기서 먼저 갈라지면 심재만 남는다.",
        f"~~칼날 어긋남 p~~ **닫혔다** — 단높이 {STAGGER_RISE_MM:g} mm · "
        f"{STAGGER_STEPS} 단 · 퍼짐 {stagger_spread_mm():,.0f} mm (발주자 확정). "
        f"경계 {rise_below_which_all_engage_mm():,.0f} mm 보다 한참 아래라 "
        f"한때 전부 물리고 **최대 합력은 {peel_force_n():,.0f} N 그대로**다. "
        f"행정만 {carriage_travel_mm():,.0f} mm 로 늘어난다.",
        "**어느 계면을 무는 유닛인지가 갈려 있다.** "
        "`where_shk101_and_this_unit_disagree()` 가 그 자리를 든다 — 형상은 "
        "같은데 SHK-101 은 유리 계면에서 셀모듈까지 함께 들고 이 모듈은 "
        "백시트만 뜯는다. **폭당 힘이 다섯 배 넘게 차이나므로 한쪽이 틀렸거나 "
        "둘이 다른 공정이다.** 이것이 지금 가장 큰 열린 물음이다.",
        "**기동 박리력과 정상 박리력의 비를 모른다.** 계단식이 최대값을 "
        "낮추는 유일한 경로가 이것인데(기동 하나 + 정상 나머지), 비를 모르니 "
        "얼마나 낮추는지 못 적는다. 시편 시험에서 같이 나올 값이다 — "
        "**추측해서 값으로 넣지 않는다.**",
        f"~~무엇이 필름을 {BLADE_COUNT} 장으로 가르는지~~ **닫혔다** — "
        f"조각 자체가 가르고, 이음에서 **바깥 칼날이 안쪽 밑으로 "
        f"{BLADE_LAP_MM:g} mm** 겹쳐 덮이지 않는 자리를 남기지 않는다. "
        "옆날이 째는 것도, 사이에서 찢어지는 것도 아니었다. 겹침은 힘을 "
        "안 보탠다 — 안쪽이 이미 떼어 간 줄을 다시 긋는 자리다.",
        f"**절단 깊이를 무엇으로 잡는지가 안 정해졌다.** 1 차의 자리와 길이는 닫혔다 "
        f"(변에서 {STARTER_CUT_OFFSET_MM:.0f} mm · 폭 전체 한 줄 · 셀 위). "
        f"남은 것은 그 창({starter_cut_window_mm()[0]}~"
        f"{starter_cut_window_mm()[1]} mm)을 1,400 mm 내내 지키는 수단이다 — "
        "연마와 같은 답(면 기준)일 것 같지만 칼날은 슈를 못 얹는 자리도 있다.",
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
        "bladeCount": BLADE_COUNT,
        "stripOrientation": STRIP_ORIENTATION,
        "peelTravelMm": peel_travel_mm(),
        "peelForcePerBladeN": peel_force_per_blade_n(),
        "peelForcePerBladeHeatedN": peel_force_per_blade_n(heated=True),
        "perBladeRelief": per_blade_relief(),
        "totalForceIsConserved": total_force_is_conserved(),
        "bendingMomentRatio": bending_moment_ratio(),
        "deflectionRatio": deflection_ratio(),
        "stiffnessBeatsForce": stiffness_beats_force_as_the_reason(),
        "bladeLayout": BLADE_LAYOUT,
        "knifeWidthMm": knife_width_mm(),
        "bladeLengthSumMm": blade_length_sum_mm(),
        "overhangEachSideMm": overhang_each_side_mm(),
        "centerBladeMm": CENTER_BLADE_MM,
        "stepBladeMm": STEP_BLADE_MM,
        "staggerSteps": STAGGER_STEPS,
        "staggerRiseMm": STAGGER_RISE_MM,
        "staggerSpreadMm": stagger_spread_mm(),
        "bladeLapMm": BLADE_LAP_MM,
        "bladeLandMm": BLADE_LAND_MM,
        "bladeWedgeDeg": BLADE_WEDGE_DEG,
        "stripWidthsMm": list(strip_widths_mm()),
        "widestStripMm": widest_strip_mm(),
        "engagedWidthMm": engaged_width_mm(),
        "riseBelowWhichAllEngageMm": rise_below_which_all_engage_mm(),
        "allBladesEngageAtOnce": all_blades_engage_at_once(),
        "spanRatio": span_ratio(),
        "loadRiseIsDividedBy": load_rise_is_divided_by(),
        "staircaseSplitsTheSupports": the_staircase_splits_the_supports_for_us(),
        "mirrorIsStillAMirror": the_mirror_must_become_a_delegation(),
        "peelForceFreshN": peel_force_n(aged=False),
        "peelForceHeatedN": heat_brings_it_to_n(),
        "weakPlaneForceN": peel_force_n(weakest_interface()),
        "peelEnergyJ": peel_energy_j(),
        "lineTaktS": line_takt_s(),
        "methodCount": len(METHODS),
        "solventFreeCount": len(solvent_free_methods()),
        "recommended": recommended().key,
        "starterCutOffsetMm": STARTER_CUT_OFFSET_MM,
        "starterCutLengthMm": starter_cut_length_mm(),
        "oneCutOpensTheFullWidth": one_cut_opens_the_full_width(),
        "cutCrossesCells": cut_must_hold_the_window_over_cells(),
        "releasedTabMm2": released_tab_mm2(),
        "gapMustBeMade": a_gap_must_be_made_not_found(),
        "starterCutWindowMm": list(starter_cut_window_mm()),
        "stageCount": len(stages()),
        "tearRiskIsAlreadySpecified": tear_risk_is_already_specified(),
        "upstreamConditionCount": len(upstream_conditions()),
    }
