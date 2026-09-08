# -*- coding: utf-8 -*-
"""CD-101 포획빔의 **시간 예산** — OI-05.

`dynamics.catch_impact()` 는 겹장이 빔에 떨어질 때의 **반력**을 냈다. 빔이
버티느냐는 거기서 끝났지만, OI-05 가 실제로 막고 있는 것은 그 앞이다 —
**빔이 제때 가 있느냐.**

미결 항목의 문장은 이렇게 적혀 있다: "포획빔은 그 아래에 있지만 전개에 걸리는
시간 안에 떨어지면 못 받는다. 전개 시간은 실물 공압에서만 나온다." 맞는
말이지만 **실물을 기다리기 전에 정해 둘 수 있는 것이 세 가지** 있다.

* **창이 얼마인가.** `kinematics.PATH` 가 대기면 정지를 1.7 s 로 잡아 두었다.
  그 값이 어디서 나온 것이 아니라 **빔이 나오는 데 걸리는 시간이 정해야 할**
  값이다. 지금 부품표의 실린더로 1,450 을 미는 데 얼마가 드는지를 먼저 낸다.
* **무엇이 먼저 걸리는가.** 공압 실린더는 대개 **미는 힘이 아니라 멈추는 힘**에서
  걸린다. 자석식 로드리스는 결합력을 넘으면 캐리지가 **자석에서 미끄러지고**,
  끝단에서는 쿠션이 먹을 수 있는 운동에너지에 상한이 있다. 마찰 롤러가
  위상을 잃는 것과 같은 종류의 한계다.
* **못 지키는 구간이 어디인가.** 빔은 패널 **밑**으로 들어가야 하므로, 패널이
  그 평면을 지나기 전에는 나올 수 없다. 그래서 안전분리 상승 1.3 s 중 앞쪽은
  **원리적으로 무방비다.** 그 구간의 크기는 빔 평면 높이가 정한다 — 낮게 두면
  빔이 일찍 나오지만 남는 낙하가 커지고, 높이 두면 낙하는 0 에 가깝지만 나올
  시간이 없다. 그 맞바꿈을 값으로 낸다.

셋 다 실물 없이 나온다. 실물에서만 나오는 것은 **실린더 실측 속도** 하나이고,
그것이 이 표의 어느 칸에 떨어지는지를 보면 판정이 끝난다 — 그것이 T-시험에
무엇을 재라고 적을 수 있는 형태다.

**여기서 처음 적는 값은 공압 부품의 카탈로그 계수뿐이다.** 질량은 강재 밀도와
제작 도면집 단면에서, 행정과 시각은 `kinematics` 에서, 압력은 `air` 에서 읽는다.
적분기와 프로파일은 `dynamics` 것을 그대로 쓴다 — 같은 가정 위에 서야 두 모듈이
같은 축을 이야기한다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.catch
"""

from __future__ import annotations

import math
import re

from . import afr, air, drives, dynamics, fabrication, kinematics

#: 상용품 이름에서 보어와 행정을 읽는 패턴 — "로드리스 실린더 Ø40 × 1,450".
_BORE = re.compile(r"Ø(\d+(?:\.\d+)?)")
_STROKE = re.compile(r"×\s*([\d,]+)")

# ── 공압 부품의 카탈로그 계수 (여기서 처음 적는 값) ──────────────────────

#: 자석식 로드리스 실린더의 **결합 유지력** 기준 압력 (MPa).
#:
#: 카탈로그는 자석 결합력을 "0.5 MPa 에서의 이론 추력 상당" 으로 적는다 — 즉
#: 사용 압력을 그보다 올려도 캐리지가 따라오는 힘은 이 값에서 멈춘다. 넘으면
#: 실린더가 힘을 못 내는 것이 아니라 **피스톤만 가고 캐리지가 남는다**
#: (`drives.FRICTION_MU` 의 마찰 롤러가 위상을 잃는 것과 같은 종류다).
RODLESS_HOLD_MPA = 0.5

#: 표준 에어쿠션이 먹을 수 있는 운동에너지 (J, Ø40 기준). **가정이다** —
#: 카탈로그 등급값이라 벤더 확인이 필요하다. 작게 잡는 쪽이 보수적이다:
#: 크게 잡으면 빔이 실제보다 빨리 나가도 되는 것처럼 보인다.
CUSHION_ALLOW_J = 1.0

#: 유압식 쇼크업소버를 달았을 때 한 본이 먹는 에너지 (J). 소형 (Ø12…16) 등급.
SHOCK_ABSORBER_J = 20.0

#: 슬라이드 마찰계수 — 로드리스 내장 가이드 + 빔 자중. 구름 가이드라 작다.
SLIDE_MU = 0.05

#: 밸브 응답 + 배관 채움 사전시간 (ms). 전개 명령이 떨어지고 캐리지가 실제로
#: 움직이기까지의 죽은 시간이다. 5 포트 밸브를 실린더 곁에 두었을 때의 관례값.
VALVE_DEAD_MS = 60.0

#: 빔 상면과 패널 프레임 하면 사이에 두는 틈 (mm). 이보다 붙이면 상승 중
#: 흔들림으로 빔이 프레임을 친다.
BEAM_CLEARANCE_MM = 20.0

#: 창에 대해 둘 여유. 1.2 면 창의 5/6 안에 전개가 끝난다 — 밸브 응답 산포와
#: 조임 세팅 오차를 받는다. 크게 잡을수록 빨라져 도착 에너지가 제곱으로 는다.
WINDOW_SAFETY = 1.2

#: 캐리지·마운트 플레이트가 빔에 더하는 질량 (kg, 1열당). 로드리스 슬라이더와
#: PL8 마운트다 — 제작 도면집에 단품 무게가 없어 여기서 잡는다.
CARRIAGE_KG = 6.0


#: 이 구간의 조립체 — 포획빔은 A04 다.
SHEET = dynamics.SHEET_CATCH


def _beam() -> fabrication.Part:
    return dynamics._part(SHEET, "CD-BM-01")


def _cylinder() -> fabrication.Commercial:
    return dynamics._commercial(SHEET, "CD-RC-01")


def cylinder_bore_mm() -> float:
    """실린더 안지름 (mm) — 상용품 이름에서 읽는다.

    치수를 여기 다시 적으면 부품표를 바꿔도 안 따라온다. 도면집이 정본이다.
    """
    m = _BORE.search(_cylinder().name)
    if not m:
        raise ValueError(f"{_cylinder().name} 에서 보어를 못 읽었다")
    return float(m.group(1))


def cylinder_stroke_mm() -> float:
    """전개 행정 (mm) — 같은 이름에서 읽는다."""
    m = _STROKE.search(_cylinder().name)
    if not m:
        raise ValueError(f"{_cylinder().name} 에서 행정을 못 읽었다")
    return float(m.group(1).replace(",", ""))



# ── 움직이는 것 ─────────────────────────────────────────────────────────
def beam_mass_kg() -> float:
    """빔 한 본의 질량 (kg) — RHS 단면을 도면집에서 읽어 강재 밀도로 낸다."""
    part = _beam()
    length, width, depth = part.size
    t = part.t
    area_mm2 = width * depth - (width - 2 * t) * (depth - 2 * t)
    volume_m3 = area_mm2 * length / 1_000.0 ** 3
    return volume_m3 * afr.STEEL_DENSITY_KG_M3


def moving_mass_kg() -> float:
    """실린더 한 본이 미는 질량 (kg) — 빔 한 본 + 캐리지."""
    return beam_mass_kg() + CARRIAGE_KG


# ── 실린더가 낼 수 있는 힘 ───────────────────────────────────────────────
def thrust_n(pressure_mpa: float | None = None) -> float:
    """이론 추력 (N). 압력은 `air.USE_BAR` 사용단에서 온다."""
    if pressure_mpa is None:
        pressure_mpa = air.USE_BAR / 10.0            # bar g → MPa
    area_mm2 = math.pi * (cylinder_bore_mm() / 2.0) ** 2
    return pressure_mpa * area_mm2                    # MPa·mm² = N


def hold_force_n() -> float:
    """자석 결합이 캐리지에 전할 수 있는 최대 힘 (N).

    **이것이 실제 상한이다.** 압력을 6 bar 로 올려도 캐리지가 받는 힘은 여기서
    멈추고, 넘으면 미끄러진다.
    """
    return thrust_n(RODLESS_HOLD_MPA)


def friction_n() -> float:
    """가이드 마찰 (N) — 빔이 수평으로 누워 있으므로 자중이 그대로 수직하중이다."""
    return moving_mass_kg() * dynamics.G * SLIDE_MU


# ── 전개를 시간으로 감는다 ───────────────────────────────────────────────
#
# **여기서는 사다리꼴을 쓰지 않는다.** 승강·반전은 서보라 프로파일을 만들 수
# 있지만, 공압 실린더는 밸브를 한 번 열면 미터아웃 조임이 정한 속도로 **거의
# 등속으로** 가고 끝단에서 쿠션이 멈춘다. 감속을 프로파일로 못 만든다는 것이
# 이 축의 성질이고, 그래서 **도착 에너지가 설계를 정한다.**
def deploy_run(speed_ms: float, dt: float = 0.0005) -> dynamics.Trace:
    """포획빔 한 본을 `speed_ms` 로 1,450 mm 내보낼 때를 감는다.

    자석 결합이 허락하는 힘으로 가속하고, 조임이 정한 속도에 닿으면 등속으로
    간다. 힘 자리에는 **캐리지가 자석에서 받아야 하는 힘**이 들어간다.
    """
    m = moving_mass_kg()
    stroke = cylinder_stroke_mm() / 1_000.0
    a = (hold_force_n() - friction_n()) / m           # 결합이 허락하는 최대 가속
    st, tr = dynamics.State(m), dynamics.Trace()
    t = 0.0
    while st.x < stroke and t < 60.0:
        accel = a if st.v < speed_ms else 0.0
        f = m * accel + friction_n()
        tr.add(t, st.x, st.v, f)
        st.step(m * accel, dt)
        if st.v > speed_ms:
            st.v = speed_ms
        t += dt
    tr.add(t, st.x, st.v, friction_n())
    return tr


def deploy_time_s(speed_ms: float, dt: float = 0.0005) -> float:
    """전개 완료까지 걸리는 시간 (s) — 밸브 사전시간을 포함한다."""
    return deploy_run(speed_ms, dt).t[-1] + VALVE_DEAD_MS / 1_000.0


def arrival_energy_j(speed_ms: float) -> float:
    """끝단에서 쿠션·업소버가 먹어야 하는 운동에너지 (J).

    등속으로 와서 끝단에서 멈추므로 **정속 속도의 운동에너지가 그대로** 온다.
    이 값이 표준 에어쿠션 등급을 넘으면 답은 압력이 아니라 완충이다.
    """
    return 0.5 * moving_mass_kg() * speed_ms ** 2


def speed_for_energy_ms(energy_j: float) -> float:
    """완충 등급 `energy_j` 이 허락하는 최고 전개 속도 (m/s)."""
    return math.sqrt(2 * energy_j / moving_mass_kg())


def speed_for_window_ms(window_s: float, tol: float = 1e-5) -> float:
    """창 `window_s` 안에 전개를 끝내려면 내야 하는 속도 (m/s).

    시간이 속도에 단조감소이므로 이분법으로 푼다 — 가속 구간이 있어 단순한
    행정/시간 나눗셈보다 조금 빠른 속도가 필요하다.
    """
    lo, hi = 1e-3, 10.0
    if deploy_time_s(hi) > window_s:
        raise ValueError("10 m/s 로도 창 안에 못 끝낸다")
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if deploy_time_s(mid) > window_s:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return hi


# ── 창 — 언제부터 언제까지 나올 수 있는가 ────────────────────────────────
def rise_seconds() -> float:
    """픽업면에서 대기면까지 안전분리 상승에 걸리는 시간 (s)."""
    seg = kinematics.PATH[0]
    return seg[1] - seg[0]


def dwell_seconds() -> float:
    """대기면 정지 — 지금 경로가 포획빔 전개에 내어 준 시간 (s)."""
    seg = kinematics.PATH[1]
    return seg[1] - seg[0]


def rise_position_mm(t: float, dt: float = 0.0005) -> float:
    """상승 시작 t 초 뒤 패널 하면이 픽업면에서 올라간 높이 (mm).

    같은 사다리꼴로 감는다 — 상승 프로파일을 여기서 따로 가정하면 두 모듈이
    다른 축을 이야기하게 된다.
    """
    total = rise_seconds()
    st = dynamics.State(1.0)
    steps = max(1, int(round(min(t, total) / dt)))
    for i in range(steps):
        st.step(dynamics.trapezoid(i * dt, total,
                                   kinematics.SEPARATION_MM / 1_000.0), dt)
    return st.x * 1_000.0


def clear_time_s(plane_mm: float, dt: float = 0.0005) -> float:
    """패널 하면이 빔 평면(+틈)을 지나는 시각 (s, 상승 시작 기준).

    이 시각 전에는 빔이 나올 수 없다 — 나오면 올라오는 패널을 친다.
    """
    need = plane_mm + BEAM_CLEARANCE_MM
    total = rise_seconds()
    st = dynamics.State(1.0)
    t = 0.0
    while t < total:
        if st.x * 1_000.0 >= need:
            return t
        st.step(dynamics.trapezoid(t, total,
                                   kinematics.SEPARATION_MM / 1_000.0), dt)
        t += dt
    # 끝까지 못 지났다 — 빔이 대기면보다 높아 **아예 못 들어간다.**
    return math.inf


def max_plane_mm() -> float:
    """빔 상면을 올릴 수 있는 한계 (mm) — 대기 중인 패널 밑에 틈만큼 남긴다."""
    return kinematics.SEPARATION_MM - BEAM_CLEARANCE_MM


def window_s(plane_mm: float) -> float:
    """빔 평면 `plane_mm` 에서 실제로 쓸 수 있는 전개 시간 (s).

    패널 하면이 그 평면을 지난 뒤부터 대기면 정지가 끝날 때까지. 평면이 너무
    높아 패널이 끝내 안 지나가면 창이 없다(음의 무한).
    """
    clear = clear_time_s(plane_mm)
    if clear == math.inf:
        return -math.inf
    return rise_seconds() - clear + dwell_seconds()


def residual_drop_mm(plane_mm: float) -> float:
    """대기면에서 빔 상면까지 남는 낙하 (mm) — 빔이 제때 가 있을 때."""
    return kinematics.SEPARATION_MM - plane_mm


def residual_energy_j(plane_mm: float) -> float:
    """그 낙하의 에너지 (J). 평면을 대기면 가까이 올릴수록 작아진다."""
    return drives.PANEL_KG * dynamics.G * residual_drop_mm(plane_mm) / 1_000.0


def unprotected_energy_j() -> float:
    """빔이 아예 못 가 있는 동안 떨어지면 받는 에너지 (J).

    `dynamics.double_sheet_energy_j()` 와 같은 값이어야 한다 — 그것이 OI-05 가
    적어 둔 163 J 이고, 이 모듈은 그 값을 **줄이는 방법**을 찾는 것이지 다시
    세는 것이 아니다.
    """
    return dynamics.double_sheet_energy_j()


# ── 언제 자리를 잡는가 — 창에 든다고 끝이 아니다 ────────────────────────
def in_place_s(plane_mm: float, speed_ms: float) -> float:
    """빔이 완전히 나가 있는 시각 (s, 상승 시작 기준).

    창 안에 든다는 것과 **일찍 든다**는 것은 다르다. 창은 대기면 정지가 끝날
    때까지고, 겹장은 그 전에 놓을 수 있다.
    """
    return clear_time_s(plane_mm) + deploy_time_s(speed_ms)


def exposure_s(plane_mm: float, speed_ms: float) -> float:
    """대기면에 서 있는 동안 **빔이 아직 없는** 시간 (s).

    이 값이 겹장 판정에 주는 조건이다 — 판정이 이 시간 안에 겹장을 놓게 하면
    빔이 없는 자리로 떨어진다. `fabrication` 의 OI-05 가 묻던 "검출 문턱값" 이
    실은 이 시간과의 경쟁이다.
    """
    return max(0.0, in_place_s(plane_mm, speed_ms) - rise_seconds())


def protected_dwell_s(plane_mm: float, speed_ms: float) -> float:
    """대기면 정지 중 빔이 받쳐 주는 시간 (s)."""
    return max(0.0, dwell_seconds() - exposure_s(plane_mm, speed_ms))


def _lift() -> fabrication.Commercial:
    """카세트 승강축 — 빔을 옆으로 낸 뒤 **올릴 수 있다**는 것이 부품표에 있다."""
    return dynamics._commercial(SHEET, "CD-Z-01")


def two_stage(low_mm: float | None = None,
              speed_ms: float | None = None) -> dict[str, float]:
    """**낮게 일찍 내고 나서 올린다** — 노출 시간을 줄이는 다른 길.

    한 평면에서 푸는 한 맞바꿈은 안 풀린다: 높이 두면 늦게 나오고 낮게 두면
    낙하가 안 준다. 그런데 부품표에는 카세트 승강축(CD-Z-01, 랙 m2 L=800)이
    이미 있다. 상승 초반에 **낮은 자리로** 빔을 내보내고, 패널이 대기면에 서면
    그 빔을 들어 올리면 둘 다 된다.

    `low_mm` 은 내보내는 자리(빔 상면), 기본값은 새 적층 최상단 위로 틈만큼이다.
    """
    if low_mm is None:
        low_mm = BEAM_CLEARANCE_MM
    if speed_ms is None:
        speed_ms = design_speed_ms()
    out = in_place_s(low_mm, speed_ms)
    rise = rise_seconds()
    top = design_plane_mm()
    # 올릴 수 있는 시각은 빔이 다 나온 뒤이면서 패널이 대기면에 선 뒤다.
    lift_start = max(out, rise)
    lift_travel = (top - low_mm) / 1_000.0
    lift_span = rise + dwell_seconds() - lift_start
    peak = 1.5 * lift_travel / lift_span if lift_span > 0 else math.inf
    return {
        "lowMm": low_mm,
        "worstJ": round(residual_energy_j(low_mm), 1),
        "clearS": round(clear_time_s(low_mm), 3),
        "outS": round(out, 3),
        "liftStartS": round(lift_start, 3),
        "liftMm": round(top - low_mm, 0),
        "liftSpanS": round(lift_span, 3),
        "liftPeakMs": round(peak, 3),
        "exposureS": round(max(0.0, out - rise), 3),
        "residualJ": round(residual_energy_j(top), 1),
    }


def two_stage_is_worth_it() -> bool:
    """2단이 한 평면짜리보다 노출을 실제로 줄이는가 — 아니면 복잡하기만 하다.

    **덜어 주는 것은 시간이지 에너지가 아니다.** 빔이 낮은 자리에서 나온
    직후에는 남는 낙하가 아직 크고(`worstJ`), 올라가는 동안 그것이 준다. 대신
    「빔이 아예 없는 시간」이 크게 줄어 겹장 판정이 쓸 수 있는 창이 열린다.
    """
    plane, v = design_plane_mm(), design_speed_ms()
    return two_stage()["exposureS"] < round(exposure_s(plane, v), 3)


# ── 판정 ────────────────────────────────────────────────────────────────
def plane_options(step_mm: float = 50.0) -> list[dict[str, float]]:
    """빔 평면 높이를 훑어 **창·필요 속도·완충 에너지**를 표로 낸다.

    낮게 두면 빔이 일찍 나올 수 있어 천천히 가도 되지만 남는 낙하가 크고,
    높이 두면 낙하는 줄지만 창이 좁아져 빨라져야 하고 끝단에서 먹어야 할
    에너지가 **속도의 제곱으로** 는다. 그 맞바꿈이 이 표다.
    """
    rows: list[dict[str, float]] = []
    plane = 0.0
    top = max_plane_mm()
    while plane <= top + 1e-9:
        w = window_s(plane)
        row: dict[str, float] = {
            "planeMm": plane,
            "windowS": round(w, 3),
            "residualMm": residual_drop_mm(plane),
            "residualJ": round(residual_energy_j(plane), 1),
        }
        try:
            v = speed_for_window_ms(w) * WINDOW_SAFETY
            row["speedMs"] = round(v, 2)
            row["arrivalJ"] = round(arrival_energy_j(v), 1)
            row["accelMm"] = round(accel_distance_mm(v), 1)
        except ValueError:
            row["speedMs"] = math.inf
            row["arrivalJ"] = math.inf
            row["accelMm"] = math.inf
        rows.append(row)
        plane += step_mm
    # 마지막 칸이 한계 평면이 아니면 한계를 하나 더 얹는다 — 설계점이 거기 있다.
    if rows and rows[-1]["planeMm"] < top - 1e-9:
        w = window_s(top)
        v = speed_for_window_ms(w) * WINDOW_SAFETY
        rows.append({
            "planeMm": top, "windowS": round(w, 3),
            "residualMm": residual_drop_mm(top),
            "residualJ": round(residual_energy_j(top), 1),
            "speedMs": round(v, 2), "arrivalJ": round(arrival_energy_j(v), 1),
            "accelMm": round(accel_distance_mm(v), 1),
        })
    return rows


def design_plane_mm() -> float:
    """설계점 — 남는 낙하가 가장 작은 자리, 즉 한계 평면이다.

    창이 좁을수록 빨라져야 하지만 **결합력이 그것을 못 견디는 자리는 없다**
    (`checks()` 가 그것을 확인한다). 그러면 남는 낙하를 줄이는 쪽이 항상 옳다.
    """
    return max_plane_mm()


def design_speed_ms() -> float:
    """설계점에서 **지정할** 전개 속도 (m/s) — 창에 딱 맞추지 않고 여유를 둔다.

    창에 정확히 맞추면 밸브 응답이 조금만 늦어도 대기면 정지가 끝나 버린다.
    `WINDOW_SAFETY` 만큼 빠르게 잡고, 그만큼 커진 도착 에너지를 완충이 받는지를
    `shock_absorber_is_enough()` 가 확인한다.
    """
    return speed_for_window_ms(window_s(design_plane_mm())) * WINDOW_SAFETY


def standard_cushion_is_enough() -> bool:
    """부품표 그대로(표준 에어쿠션)로 설계점 속도를 멈출 수 있는가."""
    return arrival_energy_j(design_speed_ms()) <= CUSHION_ALLOW_J


def shock_absorber_is_enough() -> bool:
    """쇼크업소버를 달면 멈출 수 있는가 — 못 멈추면 빔을 가볍게 하는 수밖에 없다."""
    return arrival_energy_j(design_speed_ms()) <= SHOCK_ABSORBER_J


def cushion_is_the_binding_limit() -> bool:
    """**미는 힘이 아니라 멈추는 힘이 먼저 걸리는가.**

    결합력이 허락하는 속도(행정 전체를 가속만 해서 닿는 값)보다 완충이 허락하는
    속도가 낮으면, 이 축의 한계는 추력이 아니라 완충이다 — 답은 압력을 올리는
    것이 아니라 업소버를 다는 것이다.
    """
    return speed_for_energy_ms(SHOCK_ABSORBER_J) < coupling_speed_ms()


def coupling_speed_ms() -> float:
    """결합력만 보면 낼 수 있는 속도 (m/s) — 행정 내내 가속만 했을 때의 끝속도.

    가속은 `(유지력 − 마찰) / 질량` 이다. 실제로는 완충이 이보다 훨씬 낮게 묶는다.
    """
    a = (hold_force_n() - friction_n()) / moving_mass_kg()
    return math.sqrt(2 * a * cylinder_stroke_mm() / 1_000.0)


def accel_distance_mm(speed_ms: float) -> float:
    """그 속도에 닿기까지 쓰는 행정 (mm).

    결합력에 비해 움직이는 질량이 가벼워 이 값이 행정의 한 줌밖에 안 된다 —
    그래서 창을 정하는 것은 **가속이 아니라 등속 속도**다.
    """
    a = (hold_force_n() - friction_n()) / moving_mass_kg()
    return speed_ms ** 2 / (2 * a) * 1_000.0


def summary() -> dict[str, object]:
    """한 눈에 보는 값들 — 도면·문서가 이 함수만 읽는다."""
    plane = design_plane_mm()
    v = design_speed_ms()
    return {
        "beamKg": round(beam_mass_kg(), 1),
        "movingKg": round(moving_mass_kg(), 1),
        "boreMm": cylinder_bore_mm(),
        "strokeMm": cylinder_stroke_mm(),
        "thrustN": round(thrust_n(), 0),
        "holdN": round(hold_force_n(), 0),
        "frictionN": round(friction_n(), 1),
        "riseS": round(rise_seconds(), 2),
        "dwellS": round(dwell_seconds(), 2),
        "planeMm": round(plane, 0),
        "windowS": round(window_s(plane), 3),
        "clearS": round(clear_time_s(plane), 3),
        "speedMs": round(v, 2),
        "deployS": round(deploy_time_s(v), 3),
        "windowSafety": WINDOW_SAFETY,
        "couplingSpeedMs": round(coupling_speed_ms(), 1),
        "accelMm": round(accel_distance_mm(v), 1),
        "arrivalJ": round(arrival_energy_j(v), 1),
        "cushionAllowJ": CUSHION_ALLOW_J,
        "cushionEnough": standard_cushion_is_enough(),
        "absorberJ": SHOCK_ABSORBER_J,
        "absorberEnough": shock_absorber_is_enough(),
        "cushionBinds": cushion_is_the_binding_limit(),
        "inPlaceS": round(in_place_s(plane, v), 3),
        "exposureS": round(exposure_s(plane, v), 3),
        "protectedDwellS": round(protected_dwell_s(plane, v), 3),
        "twoStage": two_stage(),
        "twoStageWins": two_stage_is_worth_it(),
        "residualMm": round(residual_drop_mm(plane), 0),
        "residualJ": round(residual_energy_j(plane), 1),
        "unprotectedJ": round(unprotected_energy_j(), 1),
        "protectedRatio": round(1 - residual_energy_j(plane)
                                / unprotected_energy_j(), 3),
    }


def checks() -> list[tuple[str, bool, str]]:
    """스스로 확인하는 것들 — (이름, 통과, 한 줄 근거)."""
    s = summary()
    v = design_speed_ms()
    coarse, fine, ok = dynamics.converged(lambda dt: deploy_time_s(v, dt), 0.001)
    return [
        ("전개 적분이 수렴한다", ok,
         f"Δt 0.001 → 0.0005 에서 {coarse:.4f} → {fine:.4f} s"),
        ("결합력이 추력보다 먼저 걸린다", s["holdN"] < s["thrustN"],
         f"유지 {s['holdN']:.0f} N < 추력 {s['thrustN']:.0f} N — "
         "압력을 올려도 캐리지가 받는 힘은 안 는다"),
        ("창을 정하는 것은 가속이 아니라 등속 속도다",
         s["accelMm"] < cylinder_stroke_mm() * 0.05,
         f"가속에 쓰는 행정이 {s['accelMm']} mm — 전체 "
         f"{cylinder_stroke_mm():.0f} 의 {s['accelMm'] / cylinder_stroke_mm() * 100:.1f} %"),
        ("멈추는 힘이 먼저 걸린다", s["cushionBinds"],
         f"완충이 허락하는 속도가 결합력이 허락하는 {s['couplingSpeedMs']} m/s "
         "보다 낮다 — 이 축의 한계는 추력이 아니다"),
        ("표준 에어쿠션으로는 못 멈춘다", not s["cushionEnough"],
         f"도착 {s['arrivalJ']} J > 쿠션 등급 {s['cushionAllowJ']} J — "
         "부품표에 업소버가 빠져 있다"),
        ("쇼크업소버를 달면 멈춘다", s["absorberEnough"],
         f"도착 {s['arrivalJ']} J ≤ 업소버 {s['absorberJ']:.0f} J"),
        ("무방비 에너지가 OI-05 의 163 J 과 같다",
         abs(s["unprotectedJ"] - dynamics.double_sheet_energy_j()) < 0.05,
         f"{s['unprotectedJ']} J — dynamics 와 같은 값이어야 한다"),
    ]


def annotations() -> tuple[str, ...]:
    """도면·문서에 그대로 실리는 문장들."""
    s = summary()
    t = s["twoStage"]
    lines = [
        f"CD-101 포획빔 전개 — Ø{s['boreMm']:.0f} 로드리스 × {s['strokeMm']:.0f} 행정, "
        f"움직이는 질량 {s['movingKg']} kg/열",
        f"빔 상면은 대기면 아래 {s['residualMm']:.0f} mm (평면 {s['planeMm']:.0f}) 에 "
        f"둔다 — 그보다 올리면 올라오는 패널을 친다",
        f"창 {s['windowS']} s (패널이 평면을 지나는 {s['clearS']} s 부터 대기면 정지 "
        f"끝까지) 에 {s['speedMs']} m/s 로 나가면 {s['deployS']} s 에 끝난다",
        f"끝단 도착 에너지 {s['arrivalJ']} J — 표준 에어쿠션 {s['cushionAllowJ']} J "
        f"로는 못 멈춘다. 열마다 쇼크업소버 {s['absorberJ']:.0f} J 급을 단다",
        f"자석 결합은 {s['couplingSpeedMs']} m/s 까지 견딘다 — 이 축을 묶는 것은 "
        f"추력이 아니라 **멈추는 힘**이다",
        f"빔이 자리를 잡으면 낙하가 {s['unprotectedJ']} → {s['residualJ']} J 로 "
        f"준다 ({s['protectedRatio'] * 100:.0f} % 감)",
        f"다만 한 평면으로 두면 빔이 대기면 정지 {s['dwellS']} s 중 "
        f"{s['exposureS']} s 가 지나서야 자리를 잡는다 — 받쳐 주는 것은 마지막 "
        f"{s['protectedDwellS']} s 뿐이다. 겹장 판정이 그 안에서 끝나야 한다",
        f"카세트 승강축(CD-Z-01)을 쓰면 낮은 자리 {t['lowMm']:.0f} mm 로 먼저 내보내고"
        f"({t['outS']} s) {t['liftMm']:.0f} 를 {t['liftSpanS']} s 에 올려 노출이 "
        f"{t['exposureS']} s 로 준다 — 올린 직후까지는 남는 낙하가 {t['worstJ']} J 다",
        f"상승 {s['riseS']} s 동안은 어느 평면에서도 무방비다 — 빔이 패널 밑으로 "
        f"들어가야 하는데 패널이 그 자리를 지나는 중이다 (OI-05)",
    ]
    return tuple(lines)


if __name__ == "__main__":                                   # pragma: no cover
    import json

    print(json.dumps(summary(), ensure_ascii=False, indent=1))
    print()
    for name, ok, why in checks():
        print(f"{'✓' if ok else '✗'} {name} — {why}")
    print()
    print(f"{'평면 mm':>8} {'창 s':>7} {'속도 m/s':>9} {'도착 J':>8} "
          f"{'가속 mm':>8} {'남는 낙하 mm':>12} {'J':>7}")
    for row in plane_options():
        print(f"{row['planeMm']:8.0f} {row['windowS']:7.3f} {row['speedMs']:9.2f} "
              f"{row['arrivalJ']:8.1f} {row['accelMm']:8.1f} "
              f"{row['residualMm']:12.0f} {row['residualJ']:7.1f}")
    print()
    for line in annotations():
        print("·", line)
