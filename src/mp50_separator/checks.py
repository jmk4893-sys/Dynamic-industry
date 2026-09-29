"""제작성·기능성 검증.

도면이 "제작 가능" 하다는 말에는 두 가지가 있다.

1. **조립이 되는가** — 부품끼리 부딪히지 않고, 원뿔이 닫히고, 빼낼 것이 개구를
   통과하는가. 여기서 걸리면 도면이 아니라 그림이다.
2. **만들면 목적을 달성하는가** — 분말이 실제로 분산되고, 정해둔 시간 안에
   층이 갈리고, 재려는 값을 잴 수 있는가.

두 종류를 같은 표에 놓는다. 1번은 전부 통과해야 발주할 수 있고, 2번의 WARN 은
장치를 고치라는 뜻이 아니라 **운전조건·시험계획을 고치라**는 뜻이다.

물성 상관식은 20 °C 기준의 실용 근사다 (밀도 ±0.5 %, 점도 ±5 %). 본 검증의
결론은 어느 것도 그 오차에 뒤집히지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import GEOMETRY, Geometry

# --------------------------------------------------------------------------
# 물성
# --------------------------------------------------------------------------
#: 실리콘 입자 밀도 (kg/m³) — [R] §7 의 3×3 유효밀도 표에서 전 구간 2330.
SILICON_DENSITY = 2330.0
#: [R] §7 의 EVA·백시트 유효밀도 (31-45 / 45-60 / 60-75 µm).
EVA_DENSITY = (980.0, 950.0, 920.0)
BACKSHEET_DENSITY = (1110.0, 1060.0, 1010.0)
SIZE_BINS_UM = (31.0, 45.0, 60.0, 75.0)
#: DOE 중심 염도 (wt%).
DOE_SALINITY_WT = (12.0, 15.0, 18.0)
#: DOE 정치시간 상한 (s).
DOE_SETTLING_MAX_S = 600.0
#: 감속기 최고 출력속도 (rpm) — [R] §2.
GEARBOX_MAX_RPM = 90.0
#: 배치 장입 상한 (kg) — [R] §4 T6.
BATCH_MAX_KG = 3.0
#: SUS316L 탄성계수 (Pa).
E_SUS316L = 193e9
#: 4PBT45° W/D=0.2 의 동력수 (배플 완비, 난류역).
POWER_NUMBER_4PBT45 = 1.27
#: 이단 임펠러 동력 합산계수 — 간격 0.6 D 에서는 서로 간섭해 2 배가 안 된다.
DUAL_IMPELLER_FACTOR = 1.6
#: Zwietering S — 4PBT, C/T ≈ 1/4. 문헌값 5~6 중 보수측.
ZWIETERING_S = 6.0
#: 설계 최고 회전수 (rpm) — CHK-05 의 권고값. [R] 의 90 rpm 이 아니다.
DESIGN_MAX_RPM = 150.0
#: 웜 감속기 효율.
GEARBOX_EFFICIENCY = 0.70
#: 정착층 재기동 토크계수. 5 wt% 정도의 갓 가라앉은 층 기준.
RESTART_FACTOR = 3.0


def brine_density(salt_wt: float, temp_c: float = 20.0) -> float:
    """NaCl 수용액 밀도 (kg/m³). 0~26 wt%, 20 °C 기준 ±0.5 %.

    온도항은 약 -0.35 kg/m³·K — 이 값 때문에 온도계(J-02)가 필요하다.
    """
    return 998.0 + 7.15 * salt_wt + 0.026 * salt_wt ** 2 - 0.35 * (temp_c - 20.0)


def brine_viscosity(salt_wt: float) -> float:
    """NaCl 수용액 점도 (Pa·s). 20 °C 기준 ±5 %."""
    return 1.002e-3 * (1.0 + 0.0123 * salt_wt + 0.00126 * salt_wt ** 2)


def stokes_velocity(particle_density: float, dp_um: float, salt_wt: float) -> float:
    """Stokes 종말속도 (m/s). 양수면 침강, 음수면 부상.

    31~75 µm 에서 Re < 1 이므로 Stokes 가 그대로 성립한다 (CHK-11 에서 확인).
    """
    rho_f = brine_density(salt_wt)
    mu = brine_viscosity(salt_wt)
    return (particle_density - rho_f) * 9.81 * (dp_um * 1e-6) ** 2 / (18.0 * mu)


def travel_fraction(velocity_ms: float, seconds: float, column_m: float) -> float:
    """정치 ``seconds`` 후 목적층에 도달한 입자의 질량분율.

    분산 직후 입자가 컬럼에 균일하게 퍼져 있다고 보면, 표면(또는 바닥)에서
    ``v·t`` 안에 있던 것만 도달한다. 그 비율이 곧 회수율의 상한이다.
    """
    return min(1.0, abs(velocity_ms) * seconds / column_m)


@dataclass(frozen=True)
class CheckResult:
    """검증 항목 하나.

    Attributes:
        ref: 항목번호 (CHK-01 …).
        kind: ``조립`` (부딪히는가) 또는 ``기능`` (목적을 달성하는가).
        item: 대상.
        criterion: 판정 기준.
        value: 계산 결과.
        verdict: PASS / WARN / FAIL.
        detail: 근거와 조치.
    """

    ref: str
    kind: str
    item: str
    criterion: str
    value: str
    verdict: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.verdict == "PASS"

    @property
    def blocking(self) -> bool:
        return self.verdict == "FAIL"


# --------------------------------------------------------------------------
# 개별 검증
# --------------------------------------------------------------------------
def _cone_closure(g: Geometry) -> CheckResult:
    """콘이 실제로 닫히는가 + 전용적이 원문과 맞는가."""
    # 도면대로 잘랐을 때 지름이 선형으로 줄어드는지를 두 표고에서 확인한다.
    mid_z = (g.cone_outlet_z + g.shell_bottom_z) / 2.0
    expected = (g.cone_outlet_id_mm + g.tank_id_mm) / 2.0
    err = abs(g.cone_id_at(mid_z) - expected)
    return CheckResult(
        "CHK-01", "조립", "원뿔 폐합 · 전용적",
        "60° 로 Ø400 → Ø59.5 가 닫히고 전용적이 [R] 의 89.9 L 와 일치할 것",
        f"높이 {g.cone_truncated_height_mm:.2f} · 전용적 {g.total_volume_l:.2f} L",
        "PASS" if err < 0.01 and abs(g.total_volume_l - 89.9) < 0.2 else "FAIL",
        f"정점높이 200/tan30° = {g.cone_apex_height_mm:.2f} 을 Z 원점으로 잡으면 "
        f"동체 상단 Z{g.shell_top_z:.1f}·커버 상면 Z{g.cover_top_z:.1f}·전용적 "
        f"{g.total_volume_l:.2f} L 이 [R] 의 Z946·Z951·89.9 L 와 동시에 맞는다. "
        f"[D1] 의 H150 은 이 조건을 하나도 만족하지 못한다 (C1).",
    )


def _baffle_clearance(g: Geometry) -> CheckResult:
    """임펠러가 배플을 치지 않는가 — 원본이 걸린 항목."""
    stack = 0.5 + 1.0  # 축 편심 + 임펠러 TIR ([R] §2 공차표)
    worst = g.impeller_tip_clearance_mm - stack
    original = g.tank_id_mm / 2.0 - g.baffle_wall_gap_mm - 80.0 - g.impeller_od_mm / 2.0
    return CheckResult(
        "CHK-02", "조립", "임펠러 ↔ 배플 간극",
        "공차 소진 후에도 반지름 간극 > 0",
        f"공칭 {g.impeller_tip_clearance_mm:.1f} · 최악 {worst:.1f} mm",
        "PASS" if worst > 3.0 else ("WARN" if worst > 0 else "FAIL"),
        f"원본 배플폭 80 으로는 {original:+.0f} mm — 즉 {abs(original):.0f} mm 겹쳐 "
        f"축이 돌지 않는다. 폭을 {g.baffle_width_mm:.0f} (T/{g.tank_id_mm / g.baffle_width_mm:.1f}) 로 "
        f"줄여 공칭 {g.impeller_tip_clearance_mm:.0f} mm 를 얻었고, 축 편심 0.5 와 "
        f"임펠러 TIR 1.0 을 다 써도 {worst:.1f} mm 가 남는다 (C2).",
    )


def _sparger_fit(g: Geometry) -> CheckResult:
    """분산링이 콘 안에 들어가는가."""
    clear = g.sparger_wall_clearance_mm
    worst = clear - 3.0  # 링 편심 공차 ([R] §2)
    return CheckResult(
        "CHK-03", "조립", "분산링 ↔ 콘 벽",
        "링 편심 3 mm 를 쓰고도 벽에 닿지 않을 것",
        f"공칭 {clear:.1f} · 최악 {worst:.1f} mm",
        "PASS" if worst > 10.0 else ("WARN" if worst > 0 else "FAIL"),
        f"Z{g.sparger_z:.0f} 의 콘 안지름은 Ø{g.cone_id_at(g.sparger_z):.1f} 이고 "
        f"링 바깥은 Ø{g.sparger_pcd_mm + g.sparger_tube_od_mm:.0f} 다. "
        f"하부 임펠러(Z{g.lower_impeller_z:.0f})와는 {g.lower_impeller_z - g.sparger_z:.0f} mm 떨어져 "
        f"회전면과도 겹치지 않는다.",
    )


def _skimmer_removal(g: Geometry) -> CheckResult:
    """스키머 바스켓을 개구로 빼낼 수 있는가."""
    return CheckResult(
        "CHK-04", "조립", "스키머 반출",
        f"바스켓 외경 < 동체 개구 Ø{g.tank_id_mm:.0f}",
        f"편측 간극 {g.skimmer_clearance_mm:.0f} mm",
        "PASS" if g.skimmer_clearance_mm > 20.0 else "FAIL",
        f"Ø{g.skimmer_od_mm:.0f} 바스켓이 Ø{g.tank_id_mm:.0f} 개구를 통과한다. "
        f"걷어낸 폴리머를 담은 채로 통째로 들어올려 그대로 칭량·건조로 보낸다 — "
        f"[R] §4 의 Top 회수 질량을 옮겨 담지 않고 잰다.",
    )


def _suspension(g: Geometry) -> CheckResult:
    """감속기 최고속도로 완전분산이 되는가 (Zwietering)."""
    salt = max(DOE_SALINITY_WT)
    rho_f = brine_density(salt)
    mu = brine_viscosity(salt)
    nu = mu / rho_f
    liquid_kg = g.operating_volume_l / 1000.0 * rho_f
    x = 100.0 * BATCH_MAX_KG / liquid_kg
    dp = max(SIZE_BINS_UM) * 1e-6
    njs = (
        ZWIETERING_S
        * nu ** 0.1
        * (9.81 * (SILICON_DENSITY - rho_f) / rho_f) ** 0.45
        * x ** 0.13
        * dp ** 0.2
        / (g.impeller_od_mm / 1000.0) ** 0.85
    )
    njs_rpm = njs * 60.0
    return CheckResult(
        "CHK-05", "기능", "완전분산 회전수 (Njs)",
        f"감속기 최고 {GEARBOX_MAX_RPM:.0f} rpm ≥ Njs",
        f"Njs {njs_rpm:.0f} rpm (최대배치 {BATCH_MAX_KG:.0f} kg · NaCl {salt:.0f} wt% · {max(SIZE_BINS_UM):.0f} µm)",
        "PASS" if njs_rpm <= GEARBOX_MAX_RPM else "WARN",
        f"Zwietering 상관식이 {njs_rpm:.0f} rpm 을 요구하는데 감속기 상한은 "
        f"{GEARBOX_MAX_RPM:.0f} rpm 이라 여유가 없다. 다만 이 상관식은 무기포·평저 "
        f"기준이고 D/T {g.impeller_diameter_ratio:.2f} 는 검증범위(0.2~0.5) 밖이므로 "
        f"{njs_rpm:.0f} 을 정확한 값으로 읽으면 안 된다. **조치 — 감속기 최고속도를 "
        f"{DESIGN_MAX_RPM:.0f} rpm 까지 확보한다.** 축·동력·위험속도는 CHK-06/07 에서 150 rpm 으로 "
        f"검증했다. 실측 후 낮추는 것은 언제든 되지만, "
        f"납품 후 올리는 것은 감속기 교체다. 콘 정착층은 분산링(F)의 gas lift 가 "
        f"함께 받는다.",
    )


def _drive_power(g: Geometry) -> CheckResult:
    """모터가 충분한가 — 정상운전이 아니라 정착층 재기동이 정한다.

    **동력이 아니라 토크로 본다.** VFD 정토크 운전에서 모터 토크는 주파수와
    무관하게 일정하므로 감속기 출력토크도 일정하고, 재기동은 저속에서 일어나
    그때의 소요동력은 작다. 동력으로 비교하면 저속 재기동을 통과시켜 버린다.
    """
    salt = max(DOE_SALINITY_WT)
    rho = brine_density(salt) + BATCH_MAX_KG / (g.operating_volume_l / 1000.0) * (
        1.0 - brine_density(salt) / SILICON_DENSITY
    )
    n = DESIGN_MAX_RPM / 60.0
    d = g.impeller_od_mm / 1000.0
    power = POWER_NUMBER_4PBT45 * rho * n ** 3 * d ** 5 * DUAL_IMPELLER_FACTOR
    torque = power / (2.0 * math.pi * n)
    need = torque * RESTART_FACTOR
    have_037 = 370.0 * GEARBOX_EFFICIENCY / (2.0 * math.pi * n)
    have_055 = 550.0 * GEARBOX_EFFICIENCY / (2.0 * math.pi * n)
    shear = 16.0 * need / (math.pi * (g.shaft_od_mm / 1000.0) ** 3) / 1e6
    return CheckResult(
        "CHK-06", "기능", "구동 토크",
        f"정착층 재기동 토크(계수 {RESTART_FACTOR:.0f}) ≤ 감속기 출력토크",
        f"소요 {need:.1f} N·m · 0.37 kW → {have_037:.1f} · 0.55 kW → {have_055:.1f} N·m",
        "PASS" if need <= have_055 else "WARN",
        f"{DESIGN_MAX_RPM:.0f} rpm·슬러리 {rho:.0f} kg/m³ 의 정상 소요는 {power:.0f} W / "
        f"{torque:.1f} N·m 로 아주 가볍다. 모터를 정하는 것은 정상운전이 아니라 "
        f"밤새 가라앉은 층을 다시 띄우는 재기동이며, 계수 {RESTART_FACTOR:.0f} 를 쓰면 "
        f"{need:.1f} N·m 가 필요하다. **0.37 kW 로는 {have_037:.1f} N·m 뿐이라 "
        f"{need / have_037:.2f} 배 모자란다 — 0.55 kW 를 택한다** ({have_055:.1f} N·m, "
        f"여유 {have_055 / need:.1f} 배). [D2] 가 이미 0.37~0.75 kW 를 적어 두었으므로 "
        f"사양 변경이 아니라 그 범위 안에서 고르는 일이다. 축 전단응력은 "
        f"{shear:.1f} MPa 로 SUS316L 허용(약 68 MPa)의 {68.0 / shear:.0f} 분의 1 이다 — "
        f"축 지름은 토크가 아니라 CHK-07 의 위험속도가 정한다.",
    )


#: 씰·커버 허브를 축의 최하단 지지점으로 본다. 벤더 GA 에서 지지점이 올라가면
#: 돌출장이 늘어 위험속도가 떨어지므로 재계산 대상이다 (C-03 HOLD).
SHAFT_SUPPORT_Z = 951.0


def critical_speed(g: Geometry = GEOMETRY) -> tuple[float, float, float]:
    """축 1 차 위험속도 (rpm) · 돌출장 (m) · 환산질량 (kg).

    도면 주석과 검증이 같은 값을 쓰도록 여기 한 곳에서만 계산한다. 손으로 적어
    두면 임펠러 질량이나 표고를 고친 뒤에도 옛 숫자가 도면에 남는다.
    """
    from .components import BY_CODE as _BY

    imp_kg = next(p.unit_kg for p in _BY["D"].parts if p.no == "D-02")
    span = (SHAFT_SUPPORT_Z - g.lower_impeller_z) / 1000.0
    upper = (SHAFT_SUPPORT_Z - g.upper_impeller_z) / 1000.0
    d = g.shaft_od_mm / 1000.0
    inertia = math.pi * d ** 4 / 64.0
    shaft_kg = math.pi / 4.0 * d ** 2 * span * 8000.0
    # 상부 임펠러는 (거리비)³ 로 환산하고, 축은 Rayleigh 계수 0.24 를 쓴다.
    m_eff = (imp_kg + imp_kg * (upper / span) ** 3 + 0.24 * shaft_kg) * 1.30  # 액체 부가질량
    fn = math.sqrt(3.0 * E_SUS316L * inertia / (span ** 3 * m_eff)) / (2.0 * math.pi)
    return fn * 60.0, span, m_eff


def _critical_speed(g: Geometry) -> CheckResult:
    """축 1차 위험속도가 운전영역 위에 있는가."""
    seal_z = SHAFT_SUPPORT_Z
    rpm, span, m_eff = critical_speed(g)
    ratio = rpm / DESIGN_MAX_RPM
    return CheckResult(
        "CHK-07", "조립", "축 1 차 위험속도",
        "운전 최고속도의 1.5 배 이상",
        f"{rpm:.0f} rpm (운전 {DESIGN_MAX_RPM:.0f} rpm 의 {ratio:.1f} 배)",
        "PASS" if ratio >= 1.5 else "FAIL",
        f"커버 허브(Z{seal_z:.0f})를 최하단 지지점으로 본 외팔보 모델이다. "
        f"돌출장 {span * 1000:.0f} mm, 환산질량 {m_eff:.2f} kg(액체 부가질량 30 % 포함). "
        f"Ø{g.shaft_od_mm:.0f} 로 이만큼 여유가 나오므로 CHK-05 의 {DESIGN_MAX_RPM:.0f} rpm 권고를 "
        f"받아들여도 축은 그대로 쓴다. 단 이 값은 씰이 하부 베어링 역할을 한다는 "
        f"전제이며, 벤더 GA 에서 지지점이 더 올라가면 재계산해야 한다 (C-03 HOLD).",
    )


def _sparger_distribution(g: Geometry) -> CheckResult:
    """급기가 12 개 홀에 고르게 갈리는가 + 기포가 얼마나 굵은가."""
    q = g.air_max_lpm / 1000.0 / 60.0
    v_hole = q / (g.sparger_hole_area_mm2 * 1e-6)
    ring_area = math.pi / 4.0 * (g.sparger_tube_id_mm * 1e-3) ** 2
    v_ring = q / 2.0 / ring_area  # 강하관에서 좌우로 갈린다
    sigma = 0.074
    rho_f = brine_density(max(DOE_SALINITY_WT))
    db = (6.0 * g.sparger_hole_dia_mm * 1e-3 * sigma / (9.81 * (rho_f - 1.2))) ** (1.0 / 3.0)
    weber = 1.2 * v_hole ** 2 * g.sparger_hole_dia_mm * 1e-3 / sigma
    ratio = v_hole / v_ring
    original = q / (60.0 * math.pi / 4.0 * (2.0e-3) ** 2)
    return CheckResult(
        "CHK-08", "기능", "급기 분배 · 기포 지름",
        "오리피스 유속 / 링 유속 ≥ 3 (고른 분배)",
        f"오리피스 {v_hole:.1f} m/s · 링 {v_ring:.2f} m/s · 비 {ratio:.1f} · 기포 Ø{db * 1000:.1f} mm",
        "PASS" if ratio >= 3.0 else "WARN",
        f"급기 {g.air_max_lpm:.0f} L/min 에서 오리피스 유속이 링 유속의 {ratio:.0f} 배라 "
        f"12 개 홀로 고르게 갈린다. [D1] 의 60 × Ø2 였다면 오리피스가 "
        f"{original:.1f} m/s 로 링 유속과 비슷해져 먼 홀에는 공기가 가지 않는다 (C4). "
        f"We {weber:.1f} < 2 이므로 준정적 기포생성역이고 기포는 Ø{db * 1000:.1f} mm — "
        f"'미세기포' 가 아니다. 이 장치에서는 그게 맞다: 미세기포는 폴리머에 붙어 "
        f"부선으로 띄워 밀도차 측정을 오염시킨다 (C5). 공기는 분산 중에만 켠다.",
    )


def _discharge(g: Geometry) -> CheckResult:
    """배출밸브 아래 그릇이 들어가는가."""
    return CheckResult(
        "CHK-09", "조립", "배출부 여유",
        f"밸브 출구 아래 ≥ {g.DISCHARGE_CATCH_MM:.0f} mm",
        f"{g.discharge_clearance_mm:.0f} mm (배출면 {g.discharge_elevation_mm:.0f})",
        "PASS" if g.discharge_clearance_mm >= g.DISCHARGE_CATCH_MM else "WARN",
        f"프레임 높이 {g.frame_height_mm:.0f} 은 임의로 고른 값이 아니라 이 여유에서 "
        f"역산했다. 콘 배출면이 바닥 +{g.discharge_elevation_mm:.0f}, 2 in 밸브·클램프가 "
        f"{g.DISCHARGE_VALVE_STACK_MM:.0f} 을 먹으므로 아래에 {g.discharge_clearance_mm:.0f} mm 가 "
        f"남는다. 깊은 통은 호스(I-07)로 옆에 두고 받는다.",
    )


def _settling_time(g: Geometry) -> CheckResult:
    """DOE 정치시간 안에 층이 갈리는가 — 이 장치 최대의 쟁점."""
    column = (g.operating_level_z - g.shell_bottom_z) / 1000.0
    salt = max(DOE_SALINITY_WT)
    rows = []
    for label, rho, dp in (
        ("Si 75 µm", SILICON_DENSITY, 75.0),
        ("Si 31 µm", SILICON_DENSITY, 31.0),
        ("EVA 75 µm", EVA_DENSITY[2], 75.0),
        ("EVA 31 µm", EVA_DENSITY[0], 31.0),
        ("백시트 31 µm", BACKSHEET_DENSITY[0], 31.0),
    ):
        v = stokes_velocity(rho, dp, salt)
        rows.append((label, v, travel_fraction(v, DOE_SETTLING_MAX_S, column)))
    worst = min(rows, key=lambda r: r[2])
    fine_eva = next(r for r in rows if r[0] == "EVA 31 µm")
    # 포화 염수로 올렸을 때 미세 백시트가 얼마나 빨라지는지
    bs_18 = abs(stokes_velocity(BACKSHEET_DENSITY[0], 31.0, 18.0))
    bs_26 = abs(stokes_velocity(BACKSHEET_DENSITY[0], 31.0, 26.0))
    detail = " · ".join(f"{n} {v * 1000:+.3f} mm/s → {f * 100:.0f} %" for n, v, f in rows)
    return CheckResult(
        "CHK-10", "기능", f"정치 {DOE_SETTLING_MAX_S:.0f} s 도달률",
        "전 성분이 정치시간 안에 목적층에 도달할 것",
        f"최저 {worst[0]} {worst[2] * 100:.0f} %",
        "WARN",
        f"컬럼 {column * 1000:.0f} mm, NaCl {salt:.0f} wt% 기준 — {detail}. "
        f"Si 는 문제가 없지만 **미세 폴리머가 뜨지 않는다**: 31 µm EVA 는 "
        f"{DOE_SETTLING_MAX_S:.0f} s 에 {fine_eva[2] * 100:.0f} % 만 표면에 닿고, "
        f"31 µm 백시트는 Δρ 가 {BACKSHEET_DENSITY[0] - brine_density(salt):+.0f} kg/m³ 뿐이라 "
        f"사실상 움직이지 않는다. Stokes 는 d² 로 가므로 미세분은 시간이 제곱으로 든다. "
        f"이건 장치 결함이 아니라 시험계획 문제이며, **장치를 고치지 말고 두 가지를 "
        f"바꾼다** — (1) [R] §11 의 정치시간 격자 60~600 s 를 600~3600 s 로 넓힌다. "
        f"(2) 염도 격자에 22/26 wt% 를 넣는다: 포화까지 올리면 31 µm 백시트의 "
        f"상승속도가 {bs_18 * 1000:.4f} → {bs_26 * 1000:.3f} mm/s 로 {bs_26 / bs_18:.1f} 배가 된다 "
        f"(밀도차는 3.6 배지만 점도도 함께 올라 이득이 그만큼은 아니다). "
        f"단 포화 염수까지 갈 경우 동체 재질은 SUS304 가 아니라 SUS316L 이어야 한다.",
    )


def _stokes_validity(g: Geometry) -> CheckResult:
    """CHK-10 이 쓴 Stokes 가 이 입도에서 성립하는가."""
    salt = max(DOE_SALINITY_WT)
    v = stokes_velocity(SILICON_DENSITY, 75.0, salt)
    re = brine_density(salt) * v * 75e-6 / brine_viscosity(salt)
    return CheckResult(
        "CHK-11", "기능", "Stokes 적용 타당성",
        "가장 빠른 입자에서도 Re < 1",
        f"Re {re:.3f} (Si 75 µm, {v * 1000:.2f} mm/s)",
        "PASS" if re < 1.0 else "WARN",
        f"전 성분·전 입도에서 Re < 1 이므로 CHK-10 의 종말속도는 Stokes 로 "
        f"충분하다. 난류 감쇠(정지 후 0~5 s)와 입자 간 방해침강은 여기 없다 — "
        f"둘 다 실제 속도를 낮추는 쪽이므로 CHK-10 의 도달률은 **낙관적 상한**이다.",
    )


def _freeboard(g: Geometry) -> CheckResult:
    """분산 중 튀어오름을 받을 여유가 있는가."""
    return CheckResult(
        "CHK-12", "조립", "프리보드",
        "운전 액면 위 ≥ 150 mm",
        f"{g.freeboard_mm:.0f} mm (액면 Z{g.operating_level_z:.0f} → 동체 상단 Z{g.shell_top_z:.0f})",
        "PASS" if g.freeboard_mm >= 150.0 else "WARN",
        f"장입 {g.operating_volume_l:.1f} L 에 대해 {g.freeboard_mm:.0f} mm 가 남는다. "
        f"급기 {g.air_max_lpm:.0f} L/min 의 겉보기 가스속도는 "
        f"{g.air_max_lpm / 1000.0 / 60.0 / (math.pi / 4.0 * (g.tank_id_mm / 1000.0) ** 2) * 1000:.2f} mm/s 로 "
        f"기포체적률이 1 % 미만이라 액면 상승은 무시할 수준이고, 프리보드는 "
        f"임펠러가 만드는 표면 요동과 급기 배출(B4)이 쓴다.",
    )


def _frame_stability(g: Geometry) -> CheckResult:
    """운전 중량을 받고 넘어지지 않는가."""
    from .components import dry_mass_kg, wet_mass_kg

    rho = brine_density(max(DOE_SALINITY_WT))
    wet = wet_mass_kg(rho)
    # 무게중심 — 액체가 지배하므로 액체 중심 표고로 근사한다.
    liquid_cg = g.elevation_mm((g.shell_bottom_z + g.operating_level_z) / 2.0)
    ratio = (g.frame_width_mm / 2.0) / liquid_cg
    return CheckResult(
        "CHK-13", "조립", "프레임 하중 · 전도",
        "밑변 반폭 / 무게중심 높이 ≥ 0.25",
        f"운전질량 {wet:.0f} kg (건조 {dry_mass_kg():.0f} kg) · 비 {ratio:.2f}",
        "PASS" if ratio >= 0.25 else "WARN",
        f"액체 {g.operating_volume_l:.1f} L × {rho:.0f} kg/m³ 가 질량의 대부분이라 "
        f"무게중심은 바닥 +{liquid_cg:.0f} mm 다. 다리 4 개에 걸리는 정하중은 "
        f"약 {wet / 4.0:.0f} kg/각 으로 M16 레벨링 풋(H-05) 정격 안이다. "
        f"정적으로는 앵커 없이 서지만, 배출 호스를 당기거나 스키머를 들어올릴 때 "
        f"수평 하중이 걸리므로 시험 중에는 앵커(K-03) 고정을 권한다.",
    )


def _sample_ladder(g: Geometry) -> CheckResult:
    """시료 사다리가 층 전체를 덮는가."""
    zs = sorted(n.z_mm for n in g.nozzles if n.tag.startswith("N4"))
    gaps = [b - a for a, b in zip(zs, zs[1:])]
    span = zs[-1] - zs[0]
    column = g.operating_level_z - g.shell_bottom_z
    return CheckResult(
        "CHK-14", "기능", "시료 사다리 피복",
        "채취구가 액체 컬럼의 80 % 이상을 균등하게 덮을 것",
        f"{len(zs)} 단 Z{zs[0]:.0f}~Z{zs[-1]:.0f} · 간격 {min(gaps):.0f}~{max(gaps):.0f} mm · 피복 {span / column * 100:.0f} %",
        "PASS" if span / column >= 0.80 else "WARN",
        f"[R] §8 은 'Mean Z-position' 과 '시간별 층 높이' 를 KPI 로 잡아 두었는데, "
        f"불투명한 SUS 동체에 [R] §2 의 채취구는 Z560 한 곳뿐이라 그 값을 잴 방법이 "
        f"없었다. 같은 규격을 {len(zs)} 단으로 늘려 컬럼의 {span / column * 100:.0f} % 를 덮으면 "
        f"각 시각의 조성 분포를 직접 뜬다. 사이트글라스(J-04)는 부상층이 생겼는지 "
        f"눈으로 보는 용도이고, 정량값은 사다리에서 나온다 (C7).",
    )


def run_checks(g: Geometry = GEOMETRY) -> tuple[CheckResult, ...]:
    """전 검증 실행. 도면·테스트·3D 콘솔이 모두 이 결과를 쓴다."""
    return (
        _cone_closure(g),
        _baffle_clearance(g),
        _sparger_fit(g),
        _skimmer_removal(g),
        _suspension(g),
        _drive_power(g),
        _critical_speed(g),
        _sparger_distribution(g),
        _discharge(g),
        _settling_time(g),
        _stokes_validity(g),
        _freeboard(g),
        _frame_stability(g),
        _sample_ladder(g),
    )
