# -*- coding: utf-8 -*-
"""JBR-201 제작 패키지 — 정션박스·케이블 제거셀을 **만드는 법**의 단일 출처.

상세도(`tools/build_jbr_detail.py`)가 자리와 시각을, 3D 파생본이 움직임을 보여
준다면 여기는 만드는 법이다. 통합 설계도 부품표의 외형·재질·수량·공차를 그대로
받아, 그 외형 안에서 **무엇으로 얼마나 두껍게 만들고 어디를 뚫어 무엇으로 조이는지**
를 정한다.

투입 구간 제작 패키지(`fabrication.py`)와 **자료형·체결 표준·토크·구멍 지름을
공유한다.** 볼트를 두 셀이 다르게 조이면 현장이 두 표를 들고 다녀야 한다. 다만
JBR 재질은 여기서 따로 갖는다 — 공구강·고력 알루미늄은 투입 구간에 없다.

값의 지위 — 셋으로 갈린다. 도면집이 이 구분을 그대로 싣는다.

* **부품표에서 온 것** — 외형 (L·W·H) · 재질 · 수량 · 공차, 그리고 재질란이 두께를
  적어 둔 10 품목(`RHS 100×100×6` · `STS304 t1.5` 꼴). 여기서 다시 정하지 않는다.
  `tests/test_pv_jbr_fab.py` 가 부품표와 글자 단위로 견준다.
* **하중에서 나온 것** — 칼날 반력 15 kN/헤드(3헤드 45 kN)를 받는 체결부의 볼트
  개수. `check()` 가 전단 용량과 견줘 이용률을 돌려주고, 1.0 을 넘으면 시험이 깨진다.
* **관례로 고른 것** — 나머지 두께와 구멍 배치. 기계 프레임 관례(가장자리 ≥ 1.5 d,
  피치 ≥ 3 d)와 이 셀의 정밀도 요구에서 골랐다. 구조 검증(45 kN 편심·잼 FEA,
  앵커 인발)이 오면 **여기만 고치고 도면집을 다시 찍는다.**

구멍은 부품표에 하나도 없었다. 그것이 이 파일이 있는 이유다 — 외형만으로는 만들 수
없고, 뚫는 자리를 정하지 않으면 조립 순서도 검사 항목도 쓸 수 없다.
"""

from __future__ import annotations

from . import fabrication as fab, fasteners, mounting
from .fabrication import (  # 자료형과 체결 표준은 투입 구간과 같은 것을 쓴다.
    ANCHOR_EMBED_MM, Assembly, Commercial, HOLE_MM, Hole, Joint, Part, Step,
    TORQUE_NM, corners, row,
)

# ── 재질 ────────────────────────────────────────────────────────────────
#: 이 셀에만 있는 재질. 코드 → (이름, KS, 상당 규격, 밀도 kg/mm³, 쓰임)
#: 이름은 **부품표가 쓰는 그대로**다 — 부품표가 'S355' 라 적으면 여기도 S355 다.
JBR_MATERIALS: dict[str, tuple[str, str, str, float, str]] = {
    "S355": ("용접구조용 압연강", "EN 10025-2", "KS SM490A · JIS SM490A", 7.85e-6,
             "베이스 프레임 · X축 빔 · 지지정반 (칼날 반력 45 kN 을 받는다)"),
    "SKD11": ("냉간 합금공구강", "KS D 3753", "JIS SKD11 · EN X153CrMoV12", 7.70e-6,
              "L칼날 카세트 · 케이블 가위날 (HRC 58–60)"),
    "SKD61": ("열간 합금공구강", "KS D 3753", "JIS SKD61 · EN X40CrMoV5-1", 7.80e-6,
              "칼날 캐리어 (질화) — 칼날을 물고 15 kN 을 전달한다"),
    "A7075-T6": ("고력 알루미늄 합금", "KS D 6701", "JIS A7075 · EN AW-7075", 2.81e-6,
                 "승강 플레이트 · 헤드 퀵체인지 (가벼우면서 처지지 않아야 한다)"),
    "SCM415": ("크롬강 (침탄용)", "KS D 3711", "JIS SCM415 · EN 15CrMo5", 7.85e-6,
               "볼스크루 축 · 랙피니언 · 스프로킷 (침탄 후 연삭)"),
    "SCM435": ("크롬몰리브덴강", "KS D 3711", "JIS SCM435 · EN 34CrMo4", 7.85e-6, "방진 풋 조절 나사"),
    "SUJ2": ("고탄소 크롬 베어링강", "KS D 3525", "JIS SUJ2 · EN 100Cr6", 7.83e-6, "승강 가이드로드 (연삭·경질도금)"),
    "POM-C": ("폴리아세탈 코폴리머", "—", "POM-C", 1.41e-6, "기준 슈 · 지지패드 · 포획콤 (유리를 긁지 않는다)"),
    "PU-80A": ("폴리우레탄", "—", "Shore 80A", 1.20e-6, "에지 클램프 패드"),
    "SPCC": ("냉간압연 강판", "KS D 3512", "JIS SPCC · EN DC01", 7.85e-6, "체인커버 · 제어반 판금"),
    "GFRP": ("유리섬유 강화 플라스틱", "—", "GFRP (절연)", 1.90e-6,
             "PV 활전부 구속대 · 기준 지그 — 도체에 닿는 자리는 금속을 쓰지 않는다"),
    "PC-FR": ("난연 폴리카보네이트", "—", "PC · UL94 V-0", 1.20e-6, "안전가드 투명판"),
    "AL-PROFILE": ("알루미늄 구조 프로파일", "—", "EN AW-6063 T6", 2.70e-6, "안전가드 프레임 · 리젝트 버퍼"),
    "SBR": ("스티렌부타디엔 고무", "—", "Shore 60A", 1.10e-6, "방진 풋 · 가드 풋"),
    "PA6": ("폴리아마이드 6", "—", "PA6", 1.14e-6, "수동 노브"),
    "PBT": ("폴리부틸렌 테레프탈레이트", "—", "PBT 브러시모", 1.31e-6, "칼날 세척 브러시"),
}

#: 투입 구간 것에 이 셀 것을 얹은 전체 재질표. 이름이 겹치면 투입 구간 정의를 쓴다.
MATERIALS: dict[str, tuple[str, str, str, float, str]] = {**fab.MATERIALS, **JBR_MATERIALS}


def weight_kg(part: Part) -> float:
    """부품 1 개 중량 kg. `fabrication.Part.weight_kg()` 은 투입 구간 재질표만 보므로
    이 셀 재질(공구강·7075)을 모른다. 형상 계산은 그대로 쓰고 밀도만 여기서 준다."""
    return round(part.volume_mm3() * MATERIALS[part.material][3], 1)


# ── 하중 ────────────────────────────────────────────────────────────────
#: 칼날 1 헤드가 계면에 거는 박리 반력 kN. 통합 설계도 힘 검산의 상한이다.
BLADE_THRUST_KN = 15.0
#: 동시 활성 헤드 상한 (검출 개수가 4 여도 헤드는 3 이다).
HEADS = 3
#: 3 헤드 동시 박리 — 승강 플레이트와 브리지가 함께 받는다.
TOTAL_THRUST_KN = BLADE_THRUST_KN * HEADS
#: 브리지＋헤드 가동부 질량 kg 과 X축 최대 감속 m/s² — 앵커 전단의 출처.
CARRIAGE_MASS_KG = 620.0
X_DECEL_MS2 = 2.5

#: 볼트 등급 → (항복 MPa, 인장강도 MPa).
BOLT_GRADE: dict[str, tuple[float, float]] = {"8.8": (640.0, 800.0), "10.9": (940.0, 1040.0)}

#: 볼트 호칭 → 나사부 유효단면적 mm² (KS B 0201 보통나사).
STRESS_AREA_MM2: dict[str, float] = {
    "M6": 20.1, "M8": 36.6, "M10": 58.0, "M12": 84.3,
    "M16": 157.0, "M20": 245.0, "M24": 353.0, "M30": 561.0,
}

#: 전단 안전율. 기계 프레임 관례값 — 구조 검증이 오면 여기를 고친다.
SHEAR_SAFETY = 2.0


def shear_capacity_kn(bolt: str, cls: str = "8.8") -> float:
    """볼트 1 개의 허용 전단력 kN. 전단항복 0.6·f_y 를 안전율로 나눈다."""
    return round(0.6 * BOLT_GRADE[cls][0] * STRESS_AREA_MM2[bolt] / SHEAR_SAFETY / 1000.0, 1)


def tensile_capacity_kn(bolt: str, cls: str = "8.8") -> float:
    """볼트 1 개의 허용 인장력 kN (항복 기준, 같은 안전율)."""
    return round(BOLT_GRADE[cls][0] * STRESS_AREA_MM2[bolt] / SHEAR_SAFETY / 1000.0, 1)


# ── 하중을 받는 체결부 ───────────────────────────────────────────────────
#: (이름, 볼트, 등급, 개수, 걸리는 힘 kN, 전단인가, 왜 그 힘인가)
LOADED_JOINTS: tuple[tuple[str, str, str, int, float, bool, str], ...] = (
    ("칼날 캐리어 → 헤드 퀵체인지", "M10", "10.9", 4, BLADE_THRUST_KN, True,
     "헤드 1 기의 박리 반력이 캐리어 체결면을 그대로 지나간다"),
    ("헤드 → 공통 승강 플레이트", "M12", "10.9", 6, BLADE_THRUST_KN, True,
     "헤드마다 15 kN — 3 헤드가 각각 제 자리에서 받는다"),
    ("승강 플레이트 → Y 캐리지", "M12", "10.9", 12, TOTAL_THRUST_KN, True,
     "3 헤드 동시 박리 45 kN 이 한 판을 지나 캐리지로 간다"),
    ("X 브리지 → Y 캐리지 레일", "M12", "8.8", 16, TOTAL_THRUST_KN, True,
     "같은 45 kN 이 브리지 웹으로 넘어간다"),
    ("X축 빔 → 베이스 프레임", "M16", "8.8", 20, TOTAL_THRUST_KN, True,
     "빔 2 본이 45 kN 을 나눠 베이스로 내린다"),
    ("베이스 → 기초 앵커", "M16", "앵커", 10, CARRIAGE_MASS_KG * X_DECEL_MS2 / 1000.0, True,
     "박리 반력은 아래로 눌러 앵커를 뽑지 않는다. 앵커가 받는 것은 브리지가 설 때의 수평 관성력이다"),
)


def check(name: str) -> dict[str, float | str | bool]:
    """체결부 하나의 이용률. 1.0 을 넘으면 볼트가 모자란다는 뜻이다."""
    for jn, bolt, cls, n, load_kn, is_shear, why in LOADED_JOINTS:
        if jn != name:
            continue
        grade = "8.8" if cls == "앵커" else cls
        cap1 = shear_capacity_kn(bolt, grade) if is_shear else tensile_capacity_kn(bolt, grade)
        cap = cap1 * n
        return {
            "name": jn, "bolt": bolt, "cls": cls, "n": n, "load_kn": round(load_kn, 1),
            "per_bolt_kn": cap1, "capacity_kn": round(cap, 1),
            "utilisation": round(load_kn / cap, 3), "ok": load_kn <= cap,
            "mode": "전단" if is_shear else "인장", "why": why,
        }
    raise KeyError(name)


def checks() -> tuple[dict[str, float | str | bool], ...]:
    return tuple(check(j[0]) for j in LOADED_JOINTS)


#: `checks()` 를 돌려 보면 이용률이 0.01–0.23 이다. 볼트가 남아도는 것이 아니라,
#: **볼트 개수를 정하는 것이 강도가 아니라는 뜻**이다. 이 셀의 체결부는 헤드 기준
#: ±0.10 · 레일 평행 0.05 를 지켜야 해서 강성과 프레팅으로 개수가 정해지고, 강도는
#: 그 뒤에 따라온다. 그래서 이 표는 「볼트를 하중으로 정했다」가 아니라 「하중이
#: 볼트를 정하지 않는다」를 확인하는 표다 — 이용률이 1 에 가까워지면 그때부터
#: 강도가 지배하므로 시험이 그 경계를 지킨다.
LOAD_IS_NOT_BINDING = True

#: 박리 반력이 바닥에 닿지 않는다는 것 — 이 셀 구조의 뼈대가 되는 사실이다.
#: 칼날이 패널을 아래로 15 kN 눌면 패널은 지지정반을, 정반은 베이스를 누르고,
#: 그 힘은 베이스 → X축 빔 → 브리지 → 헤드 → 칼날로 되돌아온다. **닫힌 고리**라
#: 앵커로 새지 않는다. 그래서 앵커는 45 kN 이 아니라 브리지가 설 때의 수평 관성력
#: 1.6 kN 만 본다. 대신 그 고리를 닫는 베이스 프레임의 강성이 절입 깊이
#: 0.6±0.2 mm 를 지키는 실제 관문이 된다 — 프레임이 벌어지면 칼날이 얕게 든다.
FORCE_LOOP_CLOSES_INSIDE = True


# ── 설계 검토 검산 ───────────────────────────────────────────────────────
# 아래는 이 셀을 기계·물리 쪽에서 다시 본 결과다. 값은 전부 부품표·서보 모델·운동식
# 에서 오고, 여기서는 그것들을 **곱해 보기만** 한다. 곱해서 안 맞는 것이 나오면
# 그것이 소견이다 — 고치는 것은 사람이 정할 일이라 여기서는 재기만 한다.

#: 박리축 구동계. 출처는 부품표 「20 × 5 볼스크루(C≥25 kN, C₀≥45 kN), 1:10 감속기」와
#: `servos.AXIS-JBR-PZ` (0.75 kW).
PEEL_SCREW_LEAD_MM = 5.0
PEEL_GEAR_RATIO = 10.0
PEEL_SERVO_KW = 0.75
BALLSCREW_C_KN = 25.0
BALLSCREW_C0_KN = 45.0

#: 0.75 kW 급 서보의 통상 최대 회전수. 카탈로그 확정 전의 관례값이다.
SERVO_MAX_RPM = 5_000.0
#: 감속기 0.95 × 볼스크루 0.9.
DRIVETRAIN_EFF = 0.855
#: smoothstep 운동의 피크/평균 속도비.
SMOOTHSTEP_PEAK = 1.5

#: **15 kN 은 사양이 아니라 임계다.** 원본이 그렇게 적었다 — 「15 kN 소프트웨어 제한」,
#: 「실제 박리력을 감시하고 15 kN/헤드에서 자동 후퇴합니다」. 기계가 도달하지 않도록
#: 설계된 값이므로 작업 조건이 아니라 보호 조건이다.
JAM_TRIP_KN = BLADE_THRUST_KN

#: 정격 작업 박리력 — **문서 어디에도 없다.** 볼스크루 수명·서보 선정·공정창이
#: 전부 이 값에 매달리는데 비어 있다. 채워지면 여기만 고치면 된다.
WORKING_PEEL_KN: float | None = None


def peel_axis_check(stroke_mm: float, seconds: float) -> dict[str, float | bool]:
    """박리축이 그 행정을 그 시간에 낼 수 있는가 — 힘을 빼고 회전수만 본다."""
    v_mean = stroke_mm / seconds
    v_peak = v_mean * SMOOTHSTEP_PEAK
    screw_rpm = v_peak / PEEL_SCREW_LEAD_MM * 60.0
    motor_rpm = screw_rpm * PEEL_GEAR_RATIO
    f_max_kn = PEEL_SERVO_KW * 1000.0 * DRIVETRAIN_EFF / (v_mean / 1000.0) / 1000.0
    return {
        "stroke_mm": stroke_mm, "seconds": seconds,
        "v_mean_mms": round(v_mean, 1), "v_peak_mms": round(v_peak, 1),
        "screw_rpm": round(screw_rpm), "motor_rpm": round(motor_rpm),
        "motor_max_rpm": SERVO_MAX_RPM, "ok": motor_rpm <= SERVO_MAX_RPM,
        "over": round(motor_rpm / SERVO_MAX_RPM, 2),
        "force_at_speed_kn": round(f_max_kn, 1),
        "trip_reachable": f_max_kn >= JAM_TRIP_KN,
        "lead_needed_mm": round(v_peak * 60.0 / (SERVO_MAX_RPM / PEEL_GEAR_RATIO), 1),
    }


def ballscrew_life(working_kn: float, stroke_mm: float, takt_s: float) -> dict[str, float]:
    """L10 = (C/P)³ × 10⁶ rev. 사이클당 회전수는 행정÷리드다."""
    rev_life = (BALLSCREW_C_KN / working_kn) ** 3 * 1e6
    rev_cycle = stroke_mm / PEEL_SCREW_LEAD_MM
    cycles = rev_life / rev_cycle
    hours = cycles / (3600.0 / takt_s)
    return {"working_kn": working_kn, "rev_life": rev_life, "cycles": round(cycles),
            "hours": round(hours), "years_8000h": round(hours / 8000.0, 2)}


def bridge_mode(section_wh_mm: tuple[float, float], wall_mm: float, span_mm: float,
                moving_kg: float, accel_ms2: float) -> dict[str, float | bool]:
    """브리지를 양단 지지 보로 보고 1 차 고유진동수와 가감속 처짐을 낸다.

    각관 단면 2 차 모멘트는 바깥에서 안쪽을 뺀다. 강축으로 세운 경우다 —
    약축으로 돌려 놓으면 더 나빠지므로 어느 쪽인지 도면이 정해야 한다.
    """
    w, h = section_wh_mm
    t = wall_mm
    inertia = (w * h ** 3 - (w - 2 * t) * (h - 2 * t) ** 3) / 12.0
    k = 48.0 * 206_000.0 * inertia / span_mm ** 3          # N/mm
    f_hz = (k * 1000.0 / moving_kg) ** 0.5 / (2 * 3.14159)
    delta = moving_kg * accel_ms2 / k
    return {"inertia_mm4": inertia, "k_n_mm": round(k), "f_hz": round(f_hz, 1),
            "inertia_force_n": round(moving_kg * accel_ms2),
            "deflection_mm": round(delta, 3), "accel_ms2": accel_ms2}


#: 상용 제거기 칼날의 통상 랜드 두께 하한 (mm). 이보다 얇으면 구리 리본을 받는
#: 순간 말리거나 깨진다.
BLADE_LAND_MIN_MM = 0.5


def blade_geometry_check(tip_mm: float, wedge_deg: float, cut_mm: float,
                         tol_mm: float) -> dict[str, float | bool]:
    """칼날 랜드 두께가 상용 범위에 있는가.

    **여기서 보는 것은 날끝 반경이 아니라 랜드 두께다.** 사양 문장의 「팁 0.8 mm」는
    두께이고(생성기 `blade_spec()` 이 「팁 두께」로 읽는다), 상용 제거기는 0.5 mm
    이상을 쓴다 — 이 칼날은 실리콘만 자르는 것이 아니라 **구리 리본도 끊어야** 해서
    얇게 갈면 버티지 못한다.

    한때 이 값을 날끝 반경으로 잘못 읽고 「절입보다 무디다」고 올렸다가 철회했다.
    지금 이 검산은 반대쪽을 지킨다 — 누가 얇게 바꾸면 여기서 걸린다.
    """
    return {"tip_mm": tip_mm, "wedge_deg": wedge_deg, "min_mm": BLADE_LAND_MIN_MM,
            "cut_mm": cut_mm, "shallow_mm": round(cut_mm - tol_mm, 2),
            "ok": tip_mm >= BLADE_LAND_MIN_MM,
            "edge_prep_stated": False}


def support_check(panel_l_mm: float, panel_w_mm: float, platen_l_mm: float,
                  platen_w_mm: float, head_z_mm: tuple[float, ...]) -> dict[str, object]:
    """패널이 정반 위에 다 올라가는가, 헤드가 정반 안에서 누르는가."""
    half = platen_w_mm / 2.0
    outside = tuple(z for z in head_z_mm if abs(z) > half)
    return {"over_l_mm": round((panel_l_mm - platen_l_mm) / 2.0, 1),
            "over_w_mm": round((panel_w_mm - platen_w_mm) / 2.0, 1),
            "platen_half_w_mm": half, "heads_outside": outside,
            "worst_out_mm": round(max((abs(z) - half for z in outside), default=0.0), 1),
            "ok": not outside and panel_l_mm <= platen_l_mm and panel_w_mm <= platen_w_mm}


#: 공압 대안 — 상용 제거기가 실제로 쓰는 방식이다. 셀에 이미 0.5–0.6 MPa 공압 설비와
#: 밸브 매니폴드가 있고, 가위·승강도 실린더다.
AIR_MPA_MAX = 0.6
CYLINDER_LIFE_KM = (2_000.0, 5_000.0)


def pneumatic_option(bore_mm: float, stroke_mm: float, takt_s: float,
                     heads: int = HEADS) -> dict[str, float | tuple[float, float]]:
    """박리축을 공압 실린더로 바꿨을 때 — 추력 · 수명 · 공기 소모.

    볼스크루 수명은 하중의 **3 제곱**에 걸리지만 실린더 수명은 **주행거리**에 걸린다.
    작업력을 ±30 % 안에서 모르는 상태(노화 폐패널이라 분포다)에서 이 차이가 결정적이다
    — 힘을 몰라도 수명이 정해지고, 힘이 모자라면 압력을 올리면 된다.
    절입 깊이는 POM 기준 슈가 기계적으로 잡으므로 축에 위치 제어가 필요 없다.
    """
    area = 3.14159 / 4 * bore_mm ** 2
    km_per_year = stroke_mm * 2 / 1e6 * (3600.0 / takt_s) * 8_000.0 * heads / heads
    nl = area / 1e6 * (stroke_mm * 2 / 1000.0) * 1000.0 * (AIR_MPA_MIN + 0.1013) / 0.1013
    return {
        "bore_mm": bore_mm,
        "force_kn": (round(area * AIR_MPA_MIN / 1000.0, 2), round(area * AIR_MPA_MAX / 1000.0, 2)),
        "km_per_year": round(km_per_year, 1),
        "years": (round(CYLINDER_LIFE_KM[0] / km_per_year, 1),
                  round(CYLINDER_LIFE_KM[1] / km_per_year, 1)),
        "air_nl_h": round(nl * heads * (3600.0 / takt_s)),
        "speed_ok": True,
    }


def scissor_check(bore_mm: float, air_mpa: float, conductor_mm2: float,
                  shear_mpa: float = 200.0) -> dict[str, float | bool]:
    """가위 실린더가 도체를 자를 힘이 되는가. 레버비가 도면에 없어 1:1 로 본다."""
    force_n = 3.14159 / 4 * bore_mm ** 2 * air_mpa
    need_n = conductor_mm2 * shear_mpa
    return {"bore_mm": bore_mm, "air_mpa": air_mpa, "force_n": round(force_n),
            "need_n": round(need_n), "margin": round(force_n / need_n, 2),
            "ok": force_n >= need_n, "lever_stated": False}


# ── 앵커 로드 길이 ───────────────────────────────────────────────────────
# 기준 브랜치의 체결 부품 도면집이 규칙을 세웠다 — 로드 길이는 **매입 + 베이스플레이트
# + 그라우트 + 평와셔 + 너트 + 나사산 여유**를 넘어야 한다. 기초 위로 나오는 부속을
# 안 세면 너트가 안 걸린다. 그 검산이 투입 구간에서 10 건을 잡았고, 같은 규칙을
# 이 셀에 대 보니 5 건 중 4 건이 짧았다.
#
# 그래서 여기서는 길이를 **고르지 않고 계산한다.** `fasteners` 의 부속 쌓임과
# 표준 공급 계열을 그대로 쓰므로 두 셀이 다른 답을 낼 수 없다.

def _grout_mm() -> float:
    return float(next(m.grout_mm for m in mounting.MOUNTINGS if m.station == "jbr"))


def anchor_need_mm(size: str, plate_t: float) -> float:
    """앵커 로드가 넘어야 하는 길이 mm."""
    return (fab.ANCHOR_EMBED_MM[size] + plate_t + _grout_mm()
            + fasteners.stack(size, "앵커").consumed_mm)


def anchor(name: str, parts: str, size: str, qty: int, pool: tuple[Part, ...],
           note: str = "") -> Joint:
    """앵커 체결 하나 — 길이는 규칙에서 나온다. 기본 판 두께 20 은 기초 직결일 때."""
    by = {p.tag: p for p in pool}
    named = [by[w].t for w in parts.replace("↔", " ").split() if w in by]
    need = anchor_need_mm(size, named[0] if named else 20.0)
    return Joint(name, parts, f"{size}×{fasteners.anchor_rod_for(size, need)}",
                 "앵커", qty, "앵커", note)


def anchor_check() -> tuple[dict[str, float | str | bool], ...]:
    """앵커 길이가 규칙을 넘는지. `fasteners.anchor_lengths()` 와 같은 계산이다."""
    by = {p.tag: p for p in parts()}
    out = []
    for a in ASSEMBLIES:
        for j in a.joints:
            if j.kind != "앵커":
                continue
            size, length, _ = fasteners._split(j.bolt)
            named = [by[w].t for w in j.parts.replace("↔", " ").split() if w in by]
            need = anchor_need_mm(size, named[0] if named else 20.0)
            out.append({"name": j.name, "bolt": j.bolt, "size": size, "length": length,
                        "need_mm": round(need, 1), "slack_mm": round(length - need, 1),
                        "ok": length >= need})
    return tuple(out)


# ── A01 베이스 용접 프레임 · 방진 풋 ─────────────────────────────────────
_fr_parts = (
    # 부품표는 베이스를 「JB-FR-001 1식」한 줄로 적는다. 1식으로는 만들 수 없어
    # 부재로 편다 — 종부재·횡부재·기둥·가공패드. 합계가 부품표의 외형 안에 든다.
    Part("JB-FR-001A", "베이스 종부재 (RHS 200×100×6)", "shs", (6_800, 100, 200), "S355", 6, 2,
         "각관 절단 · 횡부재 코프 · 완전용입 용접 · 응력제거",
         (row(10, "M16", along="L", edge=250, pitch=650, view="top",
              note="X축 빔 자리 · 가공 뒤 뚫는다"),),
         note="45 kN 고리를 닫는 주부재. 1,360 스팬 처짐 약 0.6 mm — 슈 플로팅 ±8 안이라 "
              "절입에는 닿지 않는다. 이 단면을 정하는 것은 강도와 X/Y 위치 강성이다"),
    Part("JB-FR-001B", "베이스 횡부재 (RHS 150×100×6)", "shs", (2_040, 100, 150), "S355", 6, 6,
         "각관 절단 · 양단 코프 · 종부재에 완전용입", (),
         note="1,360 피치 6 본 — 종부재의 벌어짐을 잡는다"),
    Part("JB-FR-001C", "베이스 기둥 (RHS 150×150×6)", "shs", (700, 150, 150), "S355", 6, 10,
         "각관 절단 · 상하 플레이트 완전용입",
         (corners("M16", edge=45, view="end", note="하단 앵커 플레이트 자리"),),
         note="이송면 950 에서 앵커 플레이트 상면까지 — 방진 풋 조절 ±25 를 뺀 값"),
    Part("JB-FR-001D", "X축 빔 가공 패드", "plate", (250, 140, 12), "S355", 12, 20,
         "레이저 절단 · 종부재 상면 용접 · 응력제거 뒤 한 번 물려 가공",
         (Hole("top", 1, "M16", "pcd", pcd=0, note="X축 빔 체결 관통"),),
         tolerance="가공 뒤 평면도 0.1 · 20 자리 동일 높이 0.05",
         note="용접 뒤에 가공하는 이유는 용접 변형을 가공으로 지우려는 것이다"),
    Part("JB-FR-002", "상부 메인 빔 (RHS 100×100×6)", "shs", (6_550, 100, 100), "S355", 6, 2,
         "각관 절단 · 용접 패드 · 도장",
         (row(11, "M12", along="L", edge=275, pitch=600, view="top", note="컨베이어 프레임 자리"),),
         note="부품표 재질란이 단면과 두께를 적어 두었다 — RHS 100×100×6"),
    Part("JB-FR-003", "횡방향 보강 빔 (RHS 100×100×6)", "shs", (2_160, 100, 100), "S355", 6, 10,
         "각관 절단 · 양단 코프 · 프레임 내부 용접", (),
         note="600 피치 10 본 — 프레임이 벌어지지 않게 하는 것이 이 부재의 일이다"),
    Part("JB-FR-004", "높이조절 방진 풋", "cyl", (120, 120, 170), "SCM435", 0, 10,
         "선삭 · M20 조절 나사 · 아연도금 · SBR 60A 패드 성형 접착",
         (Hole("top", 1, "M20", "pcd", pcd=0, tapped=True, note="조절 나사 · 잠금너트"),),
         finish=fab.MACHINED, tolerance="조절 행정 ±25 · 잠금너트 토크 385 N·m",
         note="레벨을 잡는 것도 이 풋이고 바닥 진동을 끊는 것도 이 풋이다"),
    Part("JB-FR-005", "분할식 체인커버 (SPCC t1.6)", "plate", (995, 240, 1.6), "SPCC", 1.6, 6,
         "레이저 절단 · 절곡 · 분체도장",
         (row(4, "M6", along="L", edge=60, pitch=290, view="top", note="6 분할 · 한 장씩 뗀다"),),
         finish=fab.PAINT_SAFETY, note="분할한 이유는 롤러 1 본을 갈려고 6 m 커버를 통째로 들지 않으려는 것"),
    Part("JB-FR-006", "앵커 플레이트 250×250×16", "plate", (250, 250, 16), "S355", 16, 10,
         "레이저 절단 · 프레임 하면 용접 · 그라우트 30",
         (corners("M16", edge=45, note="케미컬 앵커 · 매입 125"),),
         tolerance="레벨 ±2 · 그라우트 30",
         note="치수·수량은 mounting.MOUNTINGS['jbr'] 의 plate 250×250×16 · 베이스 10×M16 에서 온다"),
)
_fr_commercial = (
    Commercial("JB-AN-16", "케미컬 앵커 M16", f"HAS-U M16 8.8 · 매입 {ANCHOR_EMBED_MM['M16']} · C24 이상", 14,
               "베이스 10 + 독립가드 4"),
    Commercial("JB-GRT-01", "무수축 그라우트", "비수축 · 압축 60 MPa 이상 · 두께 30", 1),
)
_fr_joints = (
    anchor("앵커 플레이트 → 기초", "JB-FR-006 ↔ 기초", "M16", 10, _fr_parts, "베이스 10 (mounting 과 같은 수)"),
    Joint("X축 빔 → 베이스 프레임", "JB-MX-001 ↔ JB-FR-001", "M16×55", "8.8", 20, "관통", "빔 1 본당 10 · 45 kN 전단 이용률 0.07"),
    Joint("컨베이어 프레임 → 메인 빔", "JB-CV-001 ↔ JB-FR-002", "M12×40", "8.8", 22, "관통"),
    Joint("방진 풋 → 프레임", "JB-FR-004 ↔ JB-FR-001C", "M20×90", "8.8", 10, "탭", "높이조절 나사 · 잠금너트 · 레벨 뒤 마킹"),
    Joint("체인커버", "JB-FR-005 ↔ JB-FR-002", "M6×16", "8.8", 24, "탭"),
)
_fr_steps = (
    Step(1, "프레임 용접", "RHS 200×100×8 을 지그 위에서 짜고 완전용입으로 돌린다. 횡보강 10 본을 600 피치로 넣는다.",
         "용접 지그 · UT", "대각 차 ≤ 3/6,800 · 용접 UT 합격"),
    Step(2, "응력제거·가공", "어닐링 뒤 X축 빔 자리와 앵커 플레이트 자리를 한 번 물려 가공한다.",
         "플레이너 · 정반", "X빔 자리 평면도 0.1 · 두 자리 평행 0.05"),
    Step(3, "앵커·레벨", "앵커 플레이트 10 을 그라우트 30 으로 앉히고 케미컬 앵커 M16 을 매입 125 로 심는다. 방진 풋으로 레벨을 잡는다.",
         "레이저 레벨 · 토크렌치", f"레벨 ±2 · 앵커 토크 {TORQUE_NM['M16'][0]} N·m 마킹"),
    Step(4, "상부 빔", "메인 빔 2 본을 얹고 컨베이어 프레임 자리를 600 피치로 맞춘다.", "", "빔 상면 수평 1/6,550"),
)
_fr_inspection = (
    "프레임 대각 차 ≤ 3/6,800", "X축 빔 자리 평면도 0.1 · 좌우 평행 0.05",
    "앵커 10×M16 토크 195 N·m 마킹", "레벨 ±2 · 방진 풋 압축 ≤ 4",
    "45 kN 재하 시 X빔 자리 처짐 ≤ 1.0 (슈 플로팅 ±8 안 · 절입은 슈가 잡는다)",
    "브리지 정지 시 레일면 수평 변위 ≤ 0.10 (헤드 datum ±0.10)",
)


# ── A02 롤러 컨베이어 (이송면 950) ───────────────────────────────────────
_cv_parts = (
    Part("JB-CV-001A", "컨베이어 사이드 프레임 (C150×75)", "channel", (6_550, 75, 150), "S355", 6, 2,
         "ㄷ형강 절단 · 롤러 축 구멍 38 (피치 170) · 메인 빔 접합 플랜지",
         (row(38, "M12", along="L", edge=95, pitch=170, view="front",
              note="롤러 축 Ø13.5 · 피치 170 · 축 중심 925"),
          row(11, "M12", along="L", edge=275, pitch=600, view="top", note="메인 빔 자리")),
         note="축 중심 925 · 롤러 Ø50 이라 상면 950. 부품표의 이송면과 같은 값"),
    Part("JB-CV-001B", "컨베이어 크로스 타이 (RHS 80×40×3.2)", "shs", (1_800, 40, 80), "SHS/RHS", 3.2, 8,
         "각관 절단 · 양단 플랜지", (corners("M10", edge=20, view="end"),)),
    Part("JB-CV-002", "저마킹 이송 롤러 Ø50", "tube", (1_800, 50, 2.5), "STS304", 2.5, 38,
         "관 절단 · 축 압입 · 베어링 6202 · PU 70A 라이닝 3 (Ø56)", (),
         finish="—", tolerance="런아웃 0.1 · 상면 950 ±0.30",
         note="유효폭 1,800 · 저마킹 라이닝은 유리면을 긁지 않으려는 것"),
    Part("JB-CV-003A", "구동 스프로킷·탠덤 축받이", "bar", (300, 220, 90), "SCM415", 0, 1,
         "호빙 · 침탄 · 연삭 · 조립", (corners("M10", edge=25),), finish=fab.MACHINED),
    Part("JB-CV-005", "패널 감지센서 브래킷 (STS304 t2)", "plate", (130, 90, 2), "STS304", 2, 3,
         "레이저 절단 · 절곡", (row(2, "M6", along="L", edge=15, pitch=60, view="top"),),
         finish="—", note="진입·중앙·출구 3 자리"),
)
_cv_commercial = (
    Commercial("JB-CV-004", "컨베이어 기어드모터·커플링", "0.75 kW · 4P · 인버터 · 이송 612.5 mm/s", 1),
    Commercial("JB-CV-BRG", "롤러 베어링", "6202 ZZ", 76, "롤러당 2"),
    Commercial("JB-CV-CHN", "구동 체인 RS40 · 스프로킷", "롤러-롤러 탠덤 38", 1),
)
_cv_joints = (
    Joint("사이드 프레임 → 메인 빔", "JB-CV-001A ↔ JB-FR-002", "M12×40", "8.8", 22, "관통"),
    Joint("크로스 타이 → 사이드 프레임", "JB-CV-001B ↔ JB-CV-001A", "M10×30", "8.8", 32, "관통"),
    Joint("롤러 축 고정", "JB-CV-002 ↔ JB-CV-001A", "M12×30", "8.8", 76, "관통", "축 끝 나사 · 스프링와셔"),
    Joint("구동부 → 사이드 프레임", "JB-CV-003A ↔ JB-CV-001A", "M10×35", "8.8", 4, "관통"),
    Joint("센서 브래킷", "JB-CV-005 ↔ JB-CV-001A", "M6×16", "8.8", 6, "탭"),
)
_cv_steps = (
    Step(1, "프레임", "사이드 프레임 2 + 크로스 타이 8 을 짜고 축 구멍 중심 925 를 맞춘다.", "수준기", "축 높이 925 ±0.3 · 좌우 평행 0.5"),
    Step(2, "롤러", "롤러 38 을 피치 170 으로 끼운다. 손으로 돌려 걸림이 없어야 한다.", "", "상면 950 ±0.30 · 전 롤러 동일 0.3"),
    Step(3, "구동", "탠덤 체인을 걸고 612.5 mm/s 를 확인한다.", "회전계", "속도 ±3 %"),
    Step(4, "센서", "진입·중앙·출구 3 자리에 브래킷을 달고 패널 검출을 확인한다.", "", "검출 반복 100 회 누락 0"),
)
_cv_inspection = ("롤러 상면 950 ±0.30", "롤러 런아웃 0.1", "이송 속도 612.5 ±3 %", "유리면 마킹 육안 0")

# ── A03 24구역 지지정반 ──────────────────────────────────────────────────
_sp_parts = (
    Part("JB-SP-001", "1,900 × 1,200 하부 지지정반", "weldment", (1_900, 1_200, 55), "S355", 10, 1,
         "판 절단 · 리브 용접 · 응력제거 · 상면 연삭",
         (Hole("top", 24, "M10", "grid", pitch=300, tapped=True, note="24 구역 패드 자리 · 4×6 격자"),
          row(8, "M12", along="L", edge=120, pitch=240, view="front", note="프레임 체결")),
         tolerance="상면 평면도 0.1 · 높이 1,020 ±0.2",
         note="24 구역은 패널을 나눠 받으려는 것 — 한 점에 몰리면 유리가 깨진다"),
    Part("JB-SP-002", "24구역 스프링 POM 지지패드", "plate", (270, 220, 18), "POM-C", 18, 24,
         "CNC 밀링 · 모서리 R2 · 상면 경면",
         (Hole("top", 1, "M10", "pcd", pcd=0, note="카트리지 체결 · 중앙"),),
         finish="—", tolerance="상면 평면도 0.05 · 모서리 R2",
         note="유리에 닿는 면이라 금속을 쓰지 않는다. R2 는 모서리 자국을 없애려는 것"),
    Part("JB-SP-003", "하중분산 스프링 카트리지", "cyl", (60, 0, 220), "STS304", 0, 24,
         "선삭 · 스프링 조립 · 행정 ±6",
         (Hole("end", 1, "M10", "pcd", pcd=0, tapped=True, note="패드 체결"),),
         finish=fab.MACHINED, tolerance="자유장 ±0.5 · 스프링률 편차 ≤ 5 %",
         note="24 개 스프링률이 갈리면 패널이 기운다 — 편차를 공차로 잡는다"),
)
_sp_commercial = (
    Commercial("JB-SP-004", "24구역 지지 유효 센서·허가 모듈", "로드셀 24 · 안전 I/O · 지지 유효 판정", 1),
)
_sp_joints = (
    Joint("정반 → 베이스 프레임", "JB-SP-001 ↔ JB-FR-001A", "M12×45", "8.8", 8, "관통", "높이 1,020 ±0.2"),
    Joint("카트리지 → 정반", "JB-SP-003 ↔ JB-SP-001", "M10×25", "8.8", 24, "탭"),
    Joint("패드 → 카트리지", "JB-SP-002 ↔ JB-SP-003", "M10×30", "8.8", 24, "탭", "나사고정제 중강도"),
)
_sp_steps = (
    Step(1, "정반", "판을 짜 리브를 넣고 응력제거 뒤 상면을 연삭한다.", "정반 · 다이얼", "평면도 0.1"),
    Step(2, "카트리지", "24 자리에 카트리지를 세우고 자유장을 맞춘다.", "높이 게이지", "자유장 편차 ≤ 0.5"),
    Step(3, "패드", "POM 패드를 얹고 24 점 상면 높이를 한 번에 잰다.", "레이저 변위계", "24 점 높이 편차 ≤ 0.2"),
    Step(4, "허가", "로드셀 24 를 배선하고 지지 유효 판정을 확인한다.", "", "1 점 미접촉에서 허가 차단"),
)
_sp_inspection = ("정반 상면 평면도 0.1", "24 점 패드 높이 편차 ≤ 0.2", "스프링률 편차 ≤ 5 %", "1 점 미접촉 시 박리 허가 차단")


# ── A04 정렬 · 클램프 ────────────────────────────────────────────────────
_al_parts = (
    Part("JB-AL-001", "팝업 스토퍼", "bar", (160, 80, 230), "S45C", 0, 2,
         "밀링 · 고주파 열처리 HRC50 · 우레탄 패드 접착",
         (row(2, "M10", along="L", edge=30, pitch=100, view="front", note="실린더 브래킷 자리"),),
         finish=fab.MACHINED, tolerance="기준면 직각도 0.02 · 팝업 반복 ±0.05",
         note="패널이 부딪는 기준면이라 직각도가 정렬 정밀도를 그대로 정한다"),
    Part("JB-AL-003", "측면 정렬 푸셔", "weldment", (440, 200, 340), "A6061-T6", 10, 2,
         "밀링 · LM 조립", (corners("M8", edge=25, note="패드 자리"),), finish=fab.ALODINE),
    Part("JB-AL-004", "푸셔 우레탄 접촉패드", "plate", (320, 130, 35), "PU-70A", 35, 2,
         "워터젯 절단 · 접착", (row(4, "M8", along="L", edge=30, pitch=80, view="top"),),
         finish="—", note="유리 모서리에 닿는 면 — 70A 는 밀되 자국을 안 내는 굳기"),
    Part("JB-AL-005", "에지 클램프 본체", "weldment", (340, 220, 300), "S45C", 12, 4,
         "밀링 · 아노다이징 (Al 부) · 핀 조립",
         (corners("M12", edge=30, note="정반 체결"),
          row(2, "M10", along="W", edge=35, pitch=110, view="side", note="암 피벗 핀")),
         finish=fab.MACHINED),
    Part("JB-AL-006", "클램프 암", "bar", (240, 80, 55), "SCM440", 0, 4,
         "밀링 · 질화 · 피벗 부시", (Hole("side", 2, "M10", "row", along="L", edge=30, pitch=180,
                                    note="피벗 · 패드"),), finish=fab.MACHINED),
    Part("JB-AL-007", "우레탄 클램프 패드", "plate", (110, 110, 45), "PU-80A", 45, 4,
         "성형 · 접착", (Hole("top", 1, "M8", "pcd", pcd=0, note="암 체결"),), finish="—"),
    Part("JB-AL-008", "수동 위치고정 노브", "cyl", (90, 0, 80), "PA6", 0, 4,
         "사출 · S45C 인서트 나사 조립", (), finish="—", note="레시피가 바뀌면 손으로 옮기는 자리"),
)
_al_commercial = (
    Commercial("JB-AL-002", "스토퍼 실린더·브래킷", "Ø32 복동 · 쿠션 · 자석 · 스피드컨트롤러", 2),
    Commercial("JB-AL-CYL", "클램프 실린더", "Ø40 복동 · 20 kN 쐐기 · 자석", 4),
)
_al_joints = (
    Joint("스토퍼 → 정반", "JB-AL-001 ↔ JB-SP-001", "M10×35", "8.8", 4, "탭"),
    Joint("푸셔 패드", "JB-AL-004 ↔ JB-AL-003", "M8×25", "8.8", 8, "탭"),
    Joint("클램프 본체 → 정반", "JB-AL-005 ↔ JB-SP-001", "M12×45", "8.8", 16, "관통"),
    Joint("클램프 암 피벗", "JB-AL-006 ↔ JB-AL-005", "M10×60", "10.9", 8, "관통", "피벗 핀 겸용 · 부시"),
    Joint("클램프 패드", "JB-AL-007 ↔ JB-AL-006", "M8×30", "8.8", 4, "탭", "나사고정제"),
)
_al_steps = (
    Step(1, "스토퍼", "스토퍼 2 를 기준면 직각도 0.02 로 세우고 실린더를 단다.", "직각자 · 다이얼", "직각도 0.02 · 팝업 반복 ±0.05"),
    Step(2, "푸셔", "푸셔 2 를 양측에 달고 우레탄 패드를 붙인다.", "", "행정 확인 · 패드 접착 박리 0"),
    Step(3, "클램프", "클램프 4 를 정반 모서리에 달고 암·패드를 조립한다.", "", "클램프력 20 kN ±10 %"),
    Step(4, "정렬 시험", "패널을 10 회 넣어 정렬 반복도를 잰다.", "비전", "반복 ±1.0 / yaw ±0.15°"),
)
_al_inspection = ("스토퍼 기준면 직각도 0.02", "정렬 반복 10 회 ±1.0 / ±0.15°", "클램프력 20 kN ±10 %", "유리 모서리 자국 0")

# ── A05 X · Y · Z 구동 ───────────────────────────────────────────────────
_mx_parts = (
    Part("JB-MX-001", "공통 X축 빔", "weldment", (5_300, 180, 180), "S355", 10, 2,
         "각관 용접 · 응력제거 · LM 레일 자리 기계가공",
         (row(10, "M16", along="L", edge=250, pitch=650, view="front", note="베이스 체결 · 45 kN 이용률 0.07"),
          row(27, "M6", along="L", edge=80, pitch=200, view="top", tapped=True, note="LM 레일 자리")),
         tolerance="레일 자리 직진도 0.05/1,000 · 두 빔 평행 0.05",
         note="헤드 datum ±0.10 을 지탱하는 면이 이 레일 자리다"),
    Part("JB-MX-004", "X축 엔드베어링·하드스톱", "weldment", (250, 280, 180), "S45C", 12, 4,
         "밀링 · 하드스톱 우레탄 · 조립", (corners("M12", edge=30),), finish=fab.MACHINED),
    Part("JB-MX-006", "3헤드 공통 X 브리지 (RHS 150×100×8)", "shs", (2_500, 100, 150), "S355", 8, 1,
         "각관 용접 · 응력제거 · Y 레일 자리 가공",
         (row(16, "M12", along="L", edge=150, pitch=145, view="top", note="Y 캐리지 레일 · 45 kN 이용률 0.17"),
          corners("M16", edge=40, view="end", note="X 캐리지 체결")),
         tolerance="Y 레일 자리 직진도 0.05 · 비틀림 0.1/2,500",
         note="부품표 재질란이 단면과 두께를 적어 두었다 — 150×100×8"),
    Part("JB-MY-002", "Y축 리니어 캐리지", "weldment", (1_350, 240, 110), "A6061-T6", 12, 3,
         "밀링 · 아노다이징",
         (row(6, "M12", along="L", edge=90, pitch=230, view="top", note="헤드 체결 · 15 kN 이용률 0.10"),
          row(8, "M8", along="L", edge=70, pitch=170, view="front", tapped=True, note="LM 블록")),
         finish=fab.ALODINE, tolerance="헤드 체결면 평면도 0.05"),
    Part("JB-MZ-001", "공통 승강 플레이트", "weldment", (1_820, 2_180, 100), "A7075-T6", 12, 1,
         "포켓 밀링 (경량화) · 연삭 · 아노다이징",
         (row(12, "M12", along="L", edge=140, pitch=300, view="top", note="Y 캐리지 · 45 kN 이용률 0.16"),
          corners("M16", edge=60, view="top", note="가이드로드 4"),
          Hole("top", 2, "M12", "row", along="W", edge=420, pitch=980, tapped=True, note="승강 실린더 2")),
         finish=fab.ALODINE, tolerance="평면도 0.08 · 두께 편차 0.05",
         note="속을 판 리브 구조다 (겉 100 · 살 12). 통판 100 이면 7075 라도 1.1 t 이라 "
              "Ø63 실린더 2 개로 못 든다 — 그래서 포켓을 판다. 무게가 이 부품의 사양이다"),
    Part("JB-MZ-003", "승강 가이드로드·하드스톱", "cyl", (36, 0, 500), "SUJ2", 0, 4,
         "연삭 · 경질크롬 도금 20 µm", (Hole("end", 1, "M12", "pcd", pcd=0, tapped=True),),
         finish=fab.MACHINED, tolerance="직진도 0.02/500 · 표면 Ra 0.2"),
    Part("JB-MZ-005", "기계식 정비 안전받침", "bar", (430, 55, 45), "SCM440", 0, 2,
         "밀링 · 핀 조립 · 황색 도장",
         (Hole("side", 2, "M10", "row", along="L", edge=40, pitch=350, note="피벗 · 걸림"),),
         finish=fab.PAINT_SAFETY,
         note="무전원 로드락과 별개로 사람이 손으로 거는 것 — 정비 중 승강부 낙하를 막는다"),
)
_mx_commercial = (
    Commercial("JB-MX-002", "X축 LM레일·블록", "폭 45 · 레일 5,080 · 블록 4 · 예압 C1", 2, "빔당 1식"),
    Commercial("JB-MX-003", "X축 벨트·풀리", "AT10 · 폭 50 · 장력조정", 2),
    Commercial("JB-MX-005", "X축 서보·기계 동기축", "0.75 kW · 23 bit 절대 · 동기축 2,400 · 정렬 0.08", 1,
               "servos.AXIS-JBR-X 와 같은 정격"),
    Commercial("JB-MY-001", "헤드별 Y축 LM가이드", "폭 35 · 레일 2,020 · 블록 2", 6, "헤드당 2"),
    Commercial("JB-MY-003", "Y축 서보벨트 모듈", "0.2 kW · 23 bit 절대", 3, "servos.AXIS-JBR-HY"),
    Commercial("JB-MZ-002", "Ø63 가이드 승강실린더", "복동 · 행정 420 · 쿠션", 2),
    Commercial("JB-MZ-004", "무전원 승강 로드락", "안전인증 · 스프링 작동 · 공압 해제", 2),
    Commercial("JB-EL-005", "3축 에너지체인·서비스 트레이", "PA12 · 3,200 · 전력/신호/공압 분리", 1),
)
_mx_joints = (
    Joint("X축 빔 → 베이스", "JB-MX-001 ↔ JB-FR-001A", "M16×55", "8.8", 20, "관통", "45 kN 전단 이용률 0.07"),
    Joint("LM 레일 → X축 빔", "JB-MX-002 ↔ JB-MX-001", "M6×25", "10.9", 54, "탭", "레일 27 자리 ×2"),
    Joint("엔드베어링 → 빔", "JB-MX-004 ↔ JB-MX-001", "M12×40", "8.8", 16, "관통"),
    Joint("브리지 → X 캐리지", "JB-MX-006 ↔ JB-MX-002", "M16×50", "10.9", 8, "관통"),
    Joint("Y 캐리지 레일 → 브리지", "JB-MY-001 ↔ JB-MX-006", "M12×35", "8.8", 16, "관통", "45 kN 이용률 0.17"),
    Joint("승강 플레이트 → Y 캐리지", "JB-MZ-001 ↔ JB-MY-002", "M12×45", "10.9", 12, "관통", "45 kN 이용률 0.16"),
    Joint("가이드로드 → 승강 플레이트", "JB-MZ-003 ↔ JB-MZ-001", "M12×40", "10.9", 4, "탭"),
    Joint("안전받침", "JB-MZ-005 ↔ JB-MX-006", "M10×45", "8.8", 4, "관통"),
)
_mx_steps = (
    Step(1, "X축 빔", "빔 2 본을 베이스 가공면에 얹고 M16 20 으로 조인다. 두 빔 평행 0.05 를 맞춘다.",
         "레이저 간섭계", "직진도 0.05/1,000 · 평행 0.05"),
    Step(2, "레일·구동", "LM 레일을 탭 54 로 깔고 벨트·동기축을 건다. 양측 정렬 0.08 을 맞춘다.",
         "토크렌치 · 다이얼", "레일 직진도 0.05 · 동기 정렬 0.08"),
    Step(3, "브리지", "브리지를 캐리지에 얹고 Y 레일 자리를 맞춘다. 비틀림 0.1/2,500.",
         "수준기", "비틀림 0.1/2,500"),
    Step(4, "승강부", "Y 캐리지 3 → 승강 플레이트 → 가이드로드 4 → 실린더 2 → 로드락 2 순으로 올린다.",
         "", "승강 반복 ±0.1 · 로드락 무전원 유지"),
    Step(5, "안전받침", "정비 안전받침 2 를 걸고 무전원 상태에서 승강부가 내려오지 않는 것을 본다.",
         "", "무전원 낙하 0 · 받침 걸림 확인"),
)
_mx_inspection = (
    "X 레일 직진도 0.05/1,000 · 두 빔 평행 0.05", "동기축 정렬 0.08",
    "브리지 비틀림 0.1/2,500", "승강 반복 ±0.1", "로드락·안전받침 무전원 유지 시험",
    "헤드 datum ±0.10 (조립 뒤 비전으로 확인)",
)


# ── A06 제거 헤드 (3 식) ─────────────────────────────────────────────────
_hd_parts = (
    Part("JB-HD-001", "헤드 퀵체인지 플레이트", "plate", (320, 180, 45), "A7075-T6", 45, 3,
         "밀링 · 경질 아노다이징 · 기준핀 2",
         (row(6, "M12", along="L", edge=40, pitch=48, view="top", note="캐리지 체결 · 15 kN 이용률 0.10"),
          Hole("top", 2, "M10", "row", along="W", edge=45, pitch=90, tapped=True, note="칼날 캐리어 · 기준핀 Ø10 h7 2")),
         finish=fab.ALODINE, tolerance="기준핀 위치도 0.02 · 체결면 평면도 0.03",
         note="헤드를 통째로 갈아 끼우는 자리 — 기준핀 위치도가 곧 재현성이다"),
    Part("JB-HD-004", "센터링 랙·피니언 세트", "bar", (420, 120, 80), "SCM415", 0, 3,
         "호빙 · 침탄 HRC58 · 연삭", (row(4, "M8", along="L", edge=30, pitch=110, view="top"),),
         finish=fab.MACHINED, tolerance="백래시 ≤ 0.05",
         note="좌우 칼날이 같은 양만큼 들어가게 하는 것 — 한쪽만 깊으면 박스가 기운다"),
    Part("JB-HD-006", "좌측 L칼날 캐리어", "weldment", (250, 200, 100), "SKD61", 14, 3,
         "밀링 · 질화 · 칼날 자리 연삭",
         (row(4, "M10", along="L", edge=30, pitch=60, view="top", note="퀵체인지 체결 · 15 kN 이용률 0.23"),
          row(3, "M8", along="W", edge=25, pitch=75, view="front", tapped=True, note="칼날 카세트")),
         finish=fab.MACHINED, tolerance="칼날 자리 평면도 0.02 · 각도 12° ±0.1°"),
    Part("JB-HD-007", "우측 L칼날 캐리어", "weldment", (250, 200, 100), "SKD61", 14, 3,
         "밀링 · 질화 · 칼날 자리 연삭",
         (row(4, "M10", along="L", edge=30, pitch=60, view="top", note="퀵체인지 체결"),
          row(3, "M8", along="W", edge=25, pitch=75, view="front", tapped=True, note="칼날 카세트")),
         finish=fab.MACHINED, tolerance="칼날 자리 평면도 0.02 · 각도 12° ±0.1°",
         note="좌·우가 거울이다. 두 캐리어 사이 간격이 박스를 떼는 폭을 정한다"),
    Part("JB-HD-008", "SKD11 L칼날 카세트", "plate", (240, 220, 18), "SKD11", 18, 6,
         "와이어컷 · 열처리 HRC58–60 · 날끝 연삭 0.8 · 쐐기 12°",
         (row(3, "M8", along="L", edge=30, pitch=75, view="top", note="캐리어 체결 · 교체품"),),
         finish=fab.MACHINED, tolerance="날끝 0.8 ±0.05 · 쐐기 12° ±0.1° · 직진도 0.02",
         note="닳는 부품이다. 3 점 체결로 손으로 갈아 끼운다 — 수명은 미결(시운전 마모량)"),
    Part("JB-HD-009", "스프링 POM 기준 슈", "plate", (250, 240, 30), "POM-C", 30, 6,
         "밀링 · 스프링 조립 · 접촉면 R2",
         (Hole("top", 2, "M8", "row", along="L", edge=40, pitch=170, tapped=True, note="캐리어 · 스프링 카트리지"),),
         finish="—", tolerance="접촉면 평면도 0.03 · 절입간격 0.6 ±0.2",
         note="백시트 기준면에 닿는 면. **절입 깊이를 정하는 것이 이 슈다** — 프레임이 처져도 "
              "슈가 패널을 따라가므로 칼날은 슈 밑 0.6 mm 를 지킨다"),
    Part("JB-HD-010", "진공·스프링 포획그리퍼", "weldment", (300, 220, 160), "A6061-T6", 8, 3,
         "밀링 · 진공컵·체크밸브 조립",
         (corners("M8", edge=25, note="헤드 체결"),), finish=fab.ALODINE,
         tolerance="포획중심 ±1.0", note="박스가 떨어지는 순간 붙잡는다 — 놓치면 유리 위로 떨어진다"),
    Part("JB-HD-011", "Z 플로팅 컴플라이언스 모듈", "weldment", (280, 240, 120), "A7075-T6", 10, 3,
         "밀링 · 스프링 조립 · 행정 ±8",
         (corners("M10", edge=28),), finish=fab.ALODINE, tolerance="플로팅 ±8 · 마찰 ≤ 15 N",
         note="패널 워페이지와 프레임 처짐을 함께 먹는 자리. 이것이 있어서 절입이 프레임 강성과 무관해진다"),
    Part("JB-HD-012", "국소 파편흡입 노즐 (STS304 t1.2)", "plate", (260, 120, 1.2), "STS304", 1.2, 3,
         "레이저 절단 · 절곡 · TIG 용접",
         (row(2, "M6", along="L", edge=25, pitch=180, view="top"),), finish="—",
         note="칼날 바로 옆에서 유리 가루를 빨아들인다"),
    Part("JB-HD-015", "패시브 요 컴플라이언스 카세트", "plate", (300, 260, 38), "A7075-T6", 38, 3,
         "밀링 · 핀 조립 · 스프링 복원",
         (corners("M10", edge=30),), finish=fab.ALODINE, tolerance="요 ±0.5° · 복원 잔차 ≤ 0.05°"),
    Part("JB-HD-017", "무전원 포획 유지래치", "weldment", (160, 120, 85), "STS304", 6, 3,
         "가공 · 스프링 조립 · 근접센서",
         (row(2, "M6", along="L", edge=20, pitch=110, view="side"),), finish="—",
         note="전원이 나가도 잡은 박스를 놓지 않는다 — 놓으면 유리 위로 떨어진다"),
)
_hd_commercial = (
    Commercial("JB-HD-002", "0.75 kW 박리서보·1:10 감속기", "23 bit 절대 · 브레이크 · 안티백드라이브", 3,
               "servos.AXIS-JBR-PZ · 회전을 직선 추력 15 kN 으로 바꾼다"),
    Commercial("JB-HD-003", "20×5 볼스크루·너트", "정밀급 C5 · 축 SCM415 침탄 · 너트 예압", 3),
    Commercial("JB-HD-005", "20 kN 인라인 로드셀", "STS17-4PH · 교정 성적서 · 15 kN 공정창 감시", 3),
    Commercial("JB-HD-013", "진공컵·체크밸브", "실리콘 벨로즈 Ø90 · 체크밸브", 3),
    Commercial("JB-HD-014", "Z 변위센서", "±8 범위 · 분해능 0.01", 3),
    Commercial("JB-HD-016", "공구 ID·칼날 파손/마모 센서", "RFID · 레이저 · 카세트 이력 추적", 3),
    Commercial("JB-HD-018", "박리축 무전원 유지 브레이크", "스프링 작동 · 최악하중 유지 시험 성적서", 3),
)
_hd_joints = (
    Joint("퀵체인지 → Y 캐리지", "JB-HD-001 ↔ JB-MY-002", "M12×45", "10.9", 18, "관통", "헤드당 6 · 15 kN 이용률 0.10"),
    Joint("칼날 캐리어 → 퀵체인지", "JB-HD-006/007 ↔ JB-HD-001", "M10×40", "10.9", 24, "관통",
          "헤드당 좌우 4+4 · 15 kN 이용률 0.23 — 이 셀에서 가장 빡빡한 체결부"),
    Joint("칼날 카세트 → 캐리어", "JB-HD-008 ↔ JB-HD-006/007", "M8×30", "10.9", 18, "탭", "교체품 · 토크 마킹"),
    Joint("기준 슈 → 캐리어", "JB-HD-009 ↔ JB-HD-006/007", "M8×35", "8.8", 12, "탭", "스프링 카트리지 경유"),
    Joint("그리퍼 → 헤드", "JB-HD-010 ↔ JB-HD-011", "M8×30", "8.8", 12, "관통"),
    Joint("컴플라이언스 → 퀵체인지", "JB-HD-011 ↔ JB-HD-001", "M10×35", "10.9", 12, "관통"),
    Joint("요 카세트", "JB-HD-015 ↔ JB-HD-011", "M10×30", "8.8", 12, "관통"),
    Joint("흡입 노즐·래치", "JB-HD-012/017 ↔ 헤드", "M6×16", "8.8", 12, "탭"),
)
_hd_steps = (
    Step(1, "캐리어", "좌·우 칼날 캐리어를 퀵체인지 플레이트에 기준핀으로 물리고 M10 8 로 조인다.",
         "위치도 게이지", "기준핀 위치도 0.02"),
    Step(2, "칼날", "SKD11 카세트 2 를 각 캐리어에 3 점 체결한다. 날끝 0.8 · 쐐기 12° 를 확인한다.",
         "공구현미경", "날끝 0.8 ±0.05 · 쐐기 12° ±0.1°"),
    Step(3, "기준 슈", "POM 슈를 스프링 카트리지로 달고, **슈 밑면에서 칼날 끝까지 0.6 ±0.2** 를 맞춘다.",
         "하이트 게이지 · 정반", "절입간격 0.6 ±0.2 (전 6 자리)"),
    Step(4, "구동·감지", "볼스크루·서보·로드셀·변위센서를 달고 15 kN 공정창을 확인한다.",
         "로드셀 교정기", "추력 15 kN ±5 % · 변위 분해능 0.01"),
    Step(5, "무전원 시험", "전원을 끊고 브레이크·래치가 헤드와 박스를 놓지 않는 것을 본다.",
         "", "무전원 낙하 0 · 박스 유지"),
)
_hd_inspection = (
    "기준핀 위치도 0.02 · 체결면 평면도 0.03", "날끝 0.8 ±0.05 · 쐐기 12° ±0.1°",
    "절입간격 0.6 ±0.2 — 슈 밑면 기준, 6 자리 전부",
    "플로팅 ±8 · 마찰 ≤ 15 N", "추력 15 kN ±5 %", "무전원 브레이크·래치 유지",
    "공구 ID 판독 · 카세트 이력 기록",
)


# ── A07 케이블 절단 · 회수 · 세척 ────────────────────────────────────────
_cb_parts = (
    Part("JB-CB-001", "비전 연동 케이블 포획콤", "plate", (420, 80, 45), "POM-C", 45, 2,
         "밀링 · STS304 백플레이트 레이저 절단",
         (row(3, "M6", along="L", edge=40, pitch=170, view="top", tapped=True),),
         finish="—", tolerance="V홈 피치 ±0.2",
         note="도체를 홈으로 쓸어 넣는다. 이것이 가위 앞에 가닥을 세워 주는 일을 한다"),
    Part("JB-CB-002", "Ø63 공압 케이블 가위", "weldment", (180, 160, 100), "S45C", 12, 2,
         "밀링 · 실린더 조립 · 날 겹침 조정",
         (corners("M8", edge=22, note="브리지 체결"),), finish=fab.MACHINED,
         tolerance="날 겹침 0.3 ±0.1", note="겹침 0.3 을 못 맞추면 도체가 잘리지 않고 눌린다"),
    Part("JB-CB-003", "교체형 케이블 가위날", "plate", (150, 55, 25), "SKD11", 25, 4,
         "와이어컷 · 열처리 HRC58–60 · 날끝 연삭",
         (row(2, "M6", along="L", edge=20, pitch=100, view="top", note="교체품"),),
         finish=fab.MACHINED, tolerance="날 겹침 0.3 ±0.1 · 날끝 R ≤ 0.05"),
    Part("JB-CB-004", "케이블 배출슈트 (STS304 t1.5)", "weldment", (720, 400, 340), "STS304", 1.5, 1,
         "절단 · 절곡 · TIG 용접 · 내면 버 제거",
         (row(4, "M8", along="L", edge=50, pitch=200, view="top"),), finish="—",
         tolerance="경사 16 ±1°", note="하네스가 걸리지 않게 내면 버를 없앤다"),
    Part("JB-CB-005", "케이블 수거함 (STS304 t1.5)", "weldment", (580, 540, 480), "STS304", 1.5, 1,
         "절단 · 절곡 · 용접 · 손잡이", (), finish="—", note="80 L"),
    Part("JB-CB-006", "절연 도체구속·순차절단 인터록", "weldment", (460, 190, 110), "GFRP", 10, 1,
         "절삭 · 조립 · 절연 시험",
         (row(4, "M8", along="L", edge=35, pitch=130, view="top"),), finish="—",
         tolerance="절연 저항 ≥ 100 MΩ @1 kV",
         note="활전 도체를 구속하는 자리라 금속을 쓰지 않는다. A→B 순차를 강제하는 것도 여기"),
    Part("JB-WH-001", "정션박스 일괄 낙하슈트 (STS304 t1.5)", "weldment", (1_320, 500, 220), "STS304", 1.5, 1,
         "절단 · 절곡 · TIG 용접",
         (row(6, "M8", along="L", edge=60, pitch=240, view="top"),), finish="—",
         tolerance="경사 16 ±1°", note="박스 1–3 개가 폭 1,323 안에 나란히 떨어진다"),
    Part("JB-WH-002", "광폭 정션박스 수거함 (STS304 t1.5)", "weldment", (580, 1_320, 480), "STS304", 1.5, 1,
         "절단 · 절곡 · 용접 · 캐스터 4", (), finish="—",
         tolerance="바닥 상면 105 · 정지 자세 수평",
         note="박스가 눕는 자리. 바닥 상면 105 는 낙하 정지 y 155 에서 박스 반높이 50 을 뺀 값"),
    Part("JB-WH-003", "칼날 건식 세척·교정 스테이션", "weldment", (820, 520, 480), "STS304", 2, 1,
         "용접 · PBT 브러시 · 에어나이프 조립",
         (corners("M10", edge=30),), finish="—", note="칼날에 붙은 접착을 털어 내는 자리"),
    Part("JB-WH-005", "수거함 존재·중량 센서", "plate", (400, 300, 60), "A6061-T6", 60, 2,
         "밀링 · 로드셀 조립 · 교정",
         (corners("M8", edge=25),), finish=fab.ALODINE, tolerance="중량 분해능 0.5 kg",
         note="중량이 늘어야 제거 확인이 성립한다 — JB/AFR-301 합격 조건의 마지막 줄"),
)
_cb_commercial = (
    Commercial("JB-CB-CYL", "가위 실린더 Ø63", "복동 · 쿠션 · 자석 · 순차 인터록", 2),
    Commercial("JB-WH-004", "소형 사이클론·집진기", "350 m³/h · HEPA · 차압 감시", 1),
    Commercial("JB-WH-006", "슈트 통과 확인센서", "광전 · 통과 계수", 2),
    Commercial("JB-WH-007", "집진 필터 차압센서", "0–5 kPa · 경보", 1),
)
_cb_joints = (
    Joint("포획콤 → 브리지", "JB-CB-001 ↔ JB-MX-006", "M6×20", "8.8", 6, "탭"),
    Joint("가위 → 브리지", "JB-CB-002 ↔ JB-MX-006", "M8×30", "8.8", 8, "관통"),
    Joint("가위날 (교체)", "JB-CB-003 ↔ JB-CB-002", "M6×20", "10.9", 8, "탭", "겹침 0.3 조정 뒤 마킹"),
    Joint("배출슈트 → 프레임", "JB-CB-004 ↔ JB-FR-001A", "M8×25", "8.8", 4, "관통"),
    Joint("낙하슈트 → 프레임", "JB-WH-001 ↔ JB-FR-001A", "M8×25", "8.8", 6, "관통"),
    Joint("인터록 구속대", "JB-CB-006 ↔ JB-FR-001A", "M8×30", "8.8", 4, "관통", "절연 부시 · 금속 접촉 없음"),
    Joint("세척 스테이션", "JB-WH-003 ↔ JB-FR-001A", "M10×35", "8.8", 4, "관통"),
    Joint("중량 센서", "JB-WH-005 ↔ JB-FR-001A", "M8×25", "8.8", 8, "관통"),
)
_cb_steps = (
    Step(1, "가위·콤", "가위 2 를 브리지에 달고 날 겹침 0.3 을 맞춘다. 포획콤을 V홈 피치로 세운다.",
         "틈새 게이지", "겹침 0.3 ±0.1"),
    Step(2, "인터록", "절연 구속대를 달고 A→B 순차가 강제되는지, 절연 저항이 나오는지 본다.",
         "절연 저항계", "≥ 100 MΩ @1 kV · 순차 역전 불가"),
    Step(3, "슈트·수거함", "낙하슈트 16° · 케이블슈트 16° 를 세우고 수거함을 넣는다.",
         "각도계", "경사 16 ±1° · 바닥 상면 105"),
    Step(4, "집진·세척", "집진 350 m³/h 를 걸고 세척 스테이션 브러시·에어나이프를 시험한다.",
         "풍량계", "350 m³/h ±10 % · 차압 경보"),
    Step(5, "중량", "빈 수거함 중량을 영점으로 잡고 박스 1 개 투입에서 증가를 확인한다.",
         "", "분해능 0.5 kg · 증가 검출"),
)
_cb_inspection = (
    "가위날 겹침 0.3 ±0.1", "절연 저항 ≥ 100 MΩ @1 kV", "순차 절단 A→B 역전 불가",
    "슈트 경사 16 ±1°", "집진 350 m³/h ±10 %", "수거함 중량 증가 검출",
)

# ── A08 안전가드 · 차광 터널 · 리젝트 ────────────────────────────────────
_sf_parts = (
    Part("JB-SF-001", "안전가드 프로파일 프레임", "weldment", (7_050, 3_050, 2_750), "AL-PROFILE", 3, 1,
         "프로파일 절단 · 브래킷 조립 · 독립 기초",
         (row(4, "M16", along="L", edge=400, pitch=2_100, view="front",
              note="독립가드 앵커 4×M16 — mounting 과 같은 수. 셀 베이스와 따로 선다"),),
         finish="—", tolerance="수직도 2/2,750",
         note="가드는 셀 베이스에 얹지 않는다. 얹으면 사람이 기댈 때 헤드 datum 이 흔들린다"),
    Part("JB-SF-002", "투명 폴리카보네이트 패널", "plate", (1_400, 2_520, 6), "PC-FR", 6, 12,
         "재단 · 천공 · 모서리 마감",
         (row(8, "M6", along="L", edge=25, pitch=350, view="top", note="프로파일 홈 체결"),),
         finish="—", tolerance="UL94 V-0 · 두께 6"),
    Part("JB-SF-003", "인터록 정비도어", "weldment", (1_550, 2_500, 80), "AL-PROFILE", 3, 1,
         "프로파일 조립 · 힌지 · 가드락 자리",
         (row(4, "M8", along="W", edge=200, pitch=700, view="side", note="힌지 3 + 가드락 1"),),
         finish="—", note="헤드 인출 750 이 나오는 폭"),
    Part("JB-SF-007", "가드 방진 풋", "cyl", (240, 0, 120), "SBR", 0, 4,
         "성형 · S45C 인서트 선삭", (Hole("top", 1, "M16", "pcd", pcd=0, tapped=True),), finish="—"),
    Part("JB-PV-001", "차광 투입 터널", "weldment", (1_200, 2_100, 900), "SPCC", 1.6, 1,
         "난연 복합패널 판금 · EPDM 커튼 · 조도 검증",
         (row(6, "M8", along="L", edge=100, pitch=200, view="top"),),
         finish=fab.PAINT_STEEL, tolerance="내부 조도 — 실물 위험성평가 확정",
         note="패널이 빛을 받으면 전압이 산다. 어둡게 해 놓고 자르려는 것 — 허용 조도는 미결"),
    Part("JB-PV-003", "절연 프로브·커넥터 구속대", "weldment", (280, 180, 120), "GFRP", 8, 2,
         "절삭 · 조립 · 절연 시험", (corners("M8", edge=25),), finish="—",
         tolerance="절연 저항 ≥ 100 MΩ @1 kV"),
    Part("JB-PV-006", "레시피 교환형 커넥터·케이블 기준 지그", "weldment", (520, 240, 160), "GFRP", 10, 1,
         "가공 · 핀 조립 · 레시피 교정",
         (row(4, "M8", along="L", edge=40, pitch=140, view="top", note="레시피별 교환"),),
         finish="—", note="토폴로지(3분할형·1개형)가 바뀌면 이 지그를 갈아 끼운다"),
    Part("JB-RJ-001", "횡이송 리젝트 스퍼 컨베이어", "weldment", (2_400, 1_800, 900), "S355", 6, 1,
         "용접 · PU 롤러 조립 · 레벨링",
         (row(8, "M12", along="L", edge=150, pitch=300, view="top"),),
         tolerance="상면 950 ±0.5", note="후검증에서 떨어진 패널이 정상 출구로 못 가게 옆으로 뺀다"),
    Part("JB-RJ-002", "인터록 리젝트 게이트", "weldment", (720, 220, 620), "S45C", 8, 1,
         "가공 · 조립 · 안전센서 배선", (corners("M10", edge=28),), finish=fab.PAINT_SAFETY),
    Part("JB-RJ-003", "잠금 리젝트 버퍼", "weldment", (2_800, 1_900, 1_450), "AL-PROFILE", 3, 1,
         "프로파일 조립 · PC 판 · 인터록 배선",
         (row(4, "M10", along="L", edge=200, pitch=800, view="top"),), finish="—",
         note="잠가 두는 이유는 불합격 패널이 사람 손으로 다시 라인에 들어가지 않게 하려는 것"),
)
_sf_commercial = (
    Commercial("JB-SF-004", "가드락 안전인터록", "안전인증 · 이중채널 · 기계식 잠금", 1),
    Commercial("JB-SF-005", "Type 4 라이트커튼", "분해능 30 · 높이 2,100 · 이중채널", 4),
    Commercial("JB-SF-006", "비상정지·3색 표시등", "안전인증 · 하드와이어", 2),
    Commercial("JB-SF-008", "정지시간 시험포트", "안전 커넥터 · 봉인", 1),
    Commercial("JB-SF-009", "안전 뮤팅 센서쌍", "안전인증 광전 · 4 식", 4),
    Commercial("JB-SF-010", "뮤팅 컨트롤러·표시등", "안전인증 · 이중채널", 1),
    Commercial("JB-PV-002", "2극 PV 전압·스트링 분리 확인 모듈", "CAT 등급 계측부 · 절연함 — 허용전압 미결", 1),
    Commercial("JB-PV-004", "프로브 자기진단·절연 감시회로", "안전계측 I/O", 1),
    Commercial("JB-PV-005", "PV Safe-to-Cut 이중채널 허가 모듈", "안전계측 I/O · 절연함", 1),
    Commercial("JB-RJ-004", "리젝트 버퍼 존재·만재 센서", "안전센서 · 만재 경보", 2),
)
_sf_joints = (
    anchor("가드 → 독립 기초", "JB-SF-001 ↔ 기초", "M16", 4, _sf_parts, "셀 베이스와 분리"),
    Joint("PC 패널 → 프로파일", "JB-SF-002 ↔ JB-SF-001", "M6×16", "8.8", 96, "탭", "패널당 8"),
    Joint("정비도어 힌지·가드락", "JB-SF-003 ↔ JB-SF-001", "M8×25", "8.8", 4, "관통"),
    Joint("가드 방진 풋", "JB-SF-007 ↔ JB-SF-001", "M16×50", "8.8", 4, "탭"),
    Joint("차광 터널 → 프레임", "JB-PV-001 ↔ JB-FR-001A", "M8×25", "8.8", 6, "관통"),
    Joint("절연 구속대·지그", "JB-PV-003/006 ↔ JB-FR-001A", "M8×30", "8.8", 12, "관통", "절연 부시"),
    anchor("리젝트 스퍼 → 기초", "JB-RJ-001 ↔ 기초", "M12", 8, _sf_parts),
    Joint("리젝트 게이트", "JB-RJ-002 ↔ JB-RJ-001", "M10×35", "8.8", 4, "관통"),
    anchor("리젝트 버퍼", "JB-RJ-003 ↔ 기초", "M12", 4, _sf_parts),
)
_sf_steps = (
    Step(1, "가드 기초", "가드 프레임을 셀 베이스와 **떨어뜨려** 독립 기초에 앵커 4×M16 으로 세운다.",
         "레이저 레벨", "수직도 2/2,750 · 셀 베이스와 접촉 0"),
    Step(2, "판·도어", "PC 판 12 를 끼우고 정비도어에 가드락을 단다. 헤드 인출 750 을 확인한다.",
         "", "가드락 이중채널 · 인출 750 확보"),
    Step(3, "안전장치", "라이트커튼 4 · 뮤팅 4 · 비상정지 2 를 달고 정지시간을 실측한다.",
         "정지시간 측정기", "실측 정지시간 승인값 이하 · 뮤팅 논리 검증"),
    Step(4, "차광·PV", "차광 터널을 세우고 내부 조도를 잰다. PV 허가 모듈과 절연 구속대를 배선한다.",
         "조도계 · 절연 저항계", "조도 — 위험성평가 확정 · 절연 ≥ 100 MΩ"),
    Step(5, "리젝트", "스퍼 컨베이어·게이트·버퍼를 세우고 인터록을 건다.",
         "", "불합격 패널이 정상 출구로 못 감 · 버퍼 잠금"),
)
_sf_inspection = (
    "가드가 셀 베이스에 닿지 않는다 (접촉 0)", "라이트커튼 Type 4 · 이중채널 검증",
    "실측 정지시간 ≤ 승인값", "가드락 잠금 전 기동 불가", "절연 저항 ≥ 100 MΩ @1 kV",
    "차광 터널 내부 조도 — 실물 위험성평가 확정 (미결)", "리젝트 경로 인터록 · 버퍼 잠금",
)

# ── A09 전장 · 공압 ─────────────────────────────────────────────────────
_el_parts = (
    Part("JB-EL-001", "PLC·서보 제어반", "weldment", (720, 680, 260), "SPCC", 2, 1,
         "판금 · 분체도장 · DIN 레일 · 배선",
         (row(4, "M8", along="L", edge=60, pitch=200, view="side", note="벽·스탠드 체결"),),
         finish=fab.PAINT_STEEL, tolerance="IP54 · 내부 온도 ≤ 40 ℃"),
    Part("JB-EL-004", "HMI 조작 스탠드", "weldment", (340, 300, 1_470), "S355", 4, 1,
         "각관 용접 · 판금 · 배선",
         (corners("M10", edge=30, view="end", note="바닥 앵커"),), finish=fab.PAINT_STEEL,
         tolerance="화면 높이 1,400 ±20"),
)
_el_commercial = (
    Commercial("JB-EL-002", "모션 PLC·Safety PLC 팩", "FSoE · 축 동기 · 안전 로직", 1),
    Commercial("JB-EL-003", "서보드라이브·24 V 전원 팩", "X 0.75 · Y 0.2×3 · Z 0.75×3 · 24 V", 1),
    Commercial("JB-EL-006", "제어반 필터팬·열교환기", "IP54 유지 · 내부 40 ℃ 이하", 1),
    Commercial("JB-EL-007", "산업용 추적성 데이터 로거", "IPC · SSD · panel_id 이력", 1),
    Commercial("JB-PN-001", "잠금형 FRL·메인 차단밸브", "LOTO 잠금 · 0.5–0.6 MPa", 1),
    Commercial("JB-PN-002", "솔레노이드 밸브 매니폴드", "이중채널 안전밸브 포함", 1),
    Commercial("JB-PN-003", "다단 진공발생기·탱크", "420 NL/min peak", 1),
    Commercial("JB-PN-004", "안전 잔압배출 밸브", "안전인증 · 이중채널", 1),
    Commercial("JB-PN-005", "공압호스·원터치피팅 키트", "PU Ø16 · 6,000", 1),
    Commercial("JB-PN-006", "공압·진공 유량/누설 모니터", "열식 유량계 · 진공 센서", 1),
    Commercial("JB-STD-001", "구조 체결품 키트", "10.9 급 · STS304 · 토크 마킹", 1),
    Commercial("JB-STD-002", "중앙집중 급유블록", "LM·볼스크루 계통", 1),
    Commercial("JB-STD-003", "칼날 교환·교정 공구 키트", "공구강 · 교정 게이지", 1),
    Commercial("JB-STD-004", "전장 단자·케이블 표찰 키트", "표찰 · 마킹", 1),
    Commercial("JB-STD-005", "잔류에너지 LOTO·트랩키 키트", "키 코딩 · 검증", 1),
)
_el_joints = (
    Joint("제어반 → 스탠드", "JB-EL-001 ↔ JB-EL-004", "M8×25", "8.8", 4, "관통"),
    anchor("HMI 스탠드 → 바닥", "JB-EL-004 ↔ 기초", "M12", 4, _el_parts),
)
_el_steps = (
    Step(1, "반 제작", "판금·도장 뒤 DIN 레일에 PLC·드라이브·전원을 얹고 배선한다.", "", "IP54 · 절연 시험"),
    Step(2, "공압", "FRL·매니폴드·진공발생기를 배관하고 누설을 잰다.", "누설 측정기", "0.5–0.6 MPa · 누설 기준 이내"),
    Step(3, "LOTO", "잔류에너지 LOTO·트랩키를 코딩하고 방출 순서를 검증한다.", "", "잔압 방출 확인 · 키 코딩"),
    Step(4, "통신", "FSoE 노드와 데이터 로거를 붙이고 panel_id 이력이 남는지 본다.", "", "이력 기록 · 통신 오류 0"),
)
_el_inspection = ("제어반 IP54 · 내부 ≤ 40 ℃", "공압 누설 기준 이내", "LOTO 키 코딩 검증", "FSoE 노드 정상 · 이력 기록")


# ── 조립체 ───────────────────────────────────────────────────────────────
ASSEMBLIES: tuple[Assembly, ...] = (
    Assembly("PV-JBR-FAB-A01", "JB-FR", "베이스 용접 프레임 · 방진 풋 · 앵커", 1,
             "45 kN 박리 반력이 닫히는 고리. 종부재 2 · 횡부재 6 · 기둥 10 · 가공 패드 20 · 앵커 플레이트 10.",
             _fr_parts, _fr_commercial, _fr_joints, _fr_steps, _fr_inspection),
    Assembly("PV-JBR-FAB-A02", "JB-CV", "저마킹 롤러 컨베이어 (이송면 950)", 1,
             "JB-201 에서 받아 셀 안으로 넣고, 끝나면 AFR-101 로 내보내는 38 본 롤러.",
             _cv_parts, _cv_commercial, _cv_joints, _cv_steps, _cv_inspection),
    Assembly("PV-JBR-FAB-A03", "JB-SP", "24구역 지지정반 · 스프링 패드", 1,
             "패널을 24 구역으로 나눠 받는다. 한 점에 몰리면 유리가 깨진다.",
             _sp_parts, _sp_commercial, _sp_joints, _sp_steps, _sp_inspection),
    Assembly("PV-JBR-FAB-A04", "JB-AL", "정렬 스토퍼 · 푸셔 · 에지 클램프", 1,
             "패널을 기준면에 끌어당겨 좌표를 만들고 박리 중 움직이지 않게 문다.",
             _al_parts, _al_commercial, _al_joints, _al_steps, _al_inspection),
    Assembly("PV-JBR-FAB-A05", "JB-MX/MY/MZ", "X 브리지 · Y 캐리지 3 · 공통 Z 승강", 1,
             "헤드 3 기를 패널 어느 자리로든 데려가는 갠트리. 헤드 datum ±0.10 이 여기서 정해진다.",
             _mx_parts, _mx_commercial, _mx_joints, _mx_steps, _mx_inspection),
    Assembly("PV-JBR-FAB-A06", "JB-HD", "정션박스 제거헤드 (3 기)", 3,
             "L칼날 2 · 기준 슈 2 · 포획 그리퍼 · Z 플로팅. 절입 0.6±0.2 를 만드는 것이 이 조립체다.",
             _hd_parts, _hd_commercial, _hd_joints, _hd_steps, _hd_inspection),
    Assembly("PV-JBR-FAB-A07", "JB-CB/WH", "케이블 절단 · 회수 · 세척 · 집진", 1,
             "콤으로 쓸어 가위 A→B 로 끊고 슈트로 흘려 수거함에 떨군다. 칼날 세척과 집진도 여기.",
             _cb_parts, _cb_commercial, _cb_joints, _cb_steps, _cb_inspection),
    Assembly("PV-JBR-FAB-A08", "JB-SF/PV/RJ", "안전가드 · 차광 투입 터널 · 리젝트 경로", 1,
             "가드는 셀과 따로 선다. 차광 터널은 패널 전압을 죽이고, 리젝트 경로는 불합격을 격리한다.",
             _sf_parts, _sf_commercial, _sf_joints, _sf_steps, _sf_inspection),
    Assembly("PV-JBR-FAB-A09", "JB-EL/PN/STD", "제어반 · HMI 스탠드 · 공압 · 표준품", 1,
             "제작품은 반 판금과 스탠드뿐이다. 나머지는 사서 붙인다.",
             _el_parts, _el_commercial, _el_joints, _el_steps, _el_inspection),
)


def parts() -> tuple[Part, ...]:
    return tuple(p for a in ASSEMBLIES for p in a.parts)


def commercial() -> tuple[Commercial, ...]:
    return tuple(c for a in ASSEMBLIES for c in a.commercial)


def joints() -> tuple[Joint, ...]:
    return tuple(j for a in ASSEMBLIES for j in a.joints)


def assembly_weight_kg(a: Assembly) -> float:
    """조립체 1 벌의 제작품 중량 kg."""
    return round(sum(weight_kg(p) * p.qty for p in a.parts), 1)


def fabricated_weight_kg() -> float:
    """셀 1 대의 제작품 총중량 kg. 조립체가 여러 벌이면 그만큼 곱한다.

    `qty` 는 「플랜트에 몇 벌」이고 헤드는 3 기다 — 그런데 `_hd_parts` 의 부품 수량이
    이미 3 기분(예: 칼날 카세트 6 = 3 기 × 2)이라 여기서 다시 곱하지 않는다.
    """
    return round(sum(assembly_weight_kg(a) for a in ASSEMBLIES), 1)


def bolt_tally() -> dict[str, int]:
    """호칭별 볼트 개수. 조달과 토크 마킹 계획이 이 표에서 나온다."""
    out: dict[str, int] = {}
    for j in joints():
        out[j.size] = out.get(j.size, 0) + j.qty
    return dict(sorted(out.items(), key=lambda kv: int(kv[0][1:])))


def hole_tally() -> int:
    return sum(h.n * p.qty for p in parts() for h in p.holes)


# ── 도면집이 스스로 재는 것 ──────────────────────────────────────────────
#: 통합 설계도가 적은 셀 총중량 (kg). 부품표에 중량 열이 없어 이 한 줄이 전부다.
PLANT_CELL_MASS_KG = 2_200.0

#: Z 승강을 드는 실린더 — 부품표 JB-MZ-002 Ø63 2 개, 공급 압력 0.5–0.6 MPa.
LIFT_BORE_MM = 63.0
LIFT_COUNT = 2
AIR_MPA_MIN = 0.5


def moving_mass_kg() -> float:
    """Z 로 함께 오르내리는 것 — 승강 플레이트 + Y 캐리지 3 + 헤드 3 기 + 가이드로드."""
    z_tags = {"JB-MZ-001", "JB-MZ-003", "JB-MY-002"}
    z = sum(weight_kg(p) * p.qty for p in _mx_parts if p.tag in z_tags)
    return round(z + assembly_weight_kg(ASSEMBLIES[5]), 1)


def lift_check() -> dict[str, float | bool]:
    """실린더가 승강부를 들 수 있는가. 부품표 값끼리 견주는 것이라 새로 정한 값이 없다."""
    area = 3.14159 / 4 * LIFT_BORE_MM ** 2
    force_kn = round(area * AIR_MPA_MIN * LIFT_COUNT / 1000.0, 2)
    need_kn = round(moving_mass_kg() * 9.81 / 1000.0, 2)
    bore = (need_kn * 1000.0 / (AIR_MPA_MIN * LIFT_COUNT) * 4 / 3.14159) ** 0.5
    return {
        "moving_kg": moving_mass_kg(), "force_kn": force_kn, "need_kn": need_kn,
        "utilisation": round(need_kn / force_kn, 2), "ok": need_kn <= force_kn,
        "bore_needed_mm": round(bore, 0),
    }


def mass_check() -> dict[str, float | bool]:
    """제작품 총중량 대 통합 설계도의 「약 2.2 t」.

    도면은 「JBR **본체** 약 2.2 t」라 적었다. 가드(A08)는 셀 베이스에 얹지 않고
    제 기초에 따로 서므로 본체에서 뺀 값도 같이 낸다 — 그래야 같은 것끼리 견준다.
    """
    total = fabricated_weight_kg()
    guard = assembly_weight_kg(ASSEMBLIES[7])
    body = round(total - guard, 1)
    return {
        "fabricated_kg": total, "guard_kg": guard, "body_kg": body,
        "plant_kg": PLANT_CELL_MASS_KG,
        "ratio": round(body / PLANT_CELL_MASS_KG, 2),
        "over_kg": round(body - PLANT_CELL_MASS_KG, 1),
        "ok": body <= PLANT_CELL_MASS_KG,
    }
