"""전처리 라인 → 후단 박리 라인 인계 — 버퍼에서 무엇이 맞고 무엇이 안 맞는가.

전처리 플랜트의 마지막 공정은 알루미늄 프레임 제거(AFR) 뒤의 유리 버퍼다.
그 버퍼가 후단 장치 **DG-HK 2400**(5장 완전적재·60-IR 순차가열·2단 탠덤 박리,
`docs/drawings/pv-delam-tandem.html`)의 투입부로 이어진다.

두 라인을 잇는다는 것은 링크를 거는 일이 아니라 **경계 조건 세 가지가 맞는지
따지는 일**이다. 여기서는 그 셋을 계산해 어긋나는 것을 드러낸다.

* **자세** — 후단은 유리면 ↓·백시트 ↑ 로 받는다. 버퍼도 같은 자세로 세워 두므로
  경계에 반전기가 필요 없다. (이것만 맞는다.)
* **치수** — 전처리는 최대 2,500 × 1,400 을 다루는데 후단 투입 상한은
  2,400 × 1,200 이다. 상한 패널은 후단에 **들어가지 않는다**.
* **처리율** — 정상 유리(R-A) 유입이 후단 능력보다 빠르다. 버퍼가 완충하지만
  유한하므로 몇 시간 만에 찬다.

후단 수치는 DG-HK 2400 Rev.10 앱의 계산 모델을 **그대로 옮긴 것**이다.
다시 유도하지 않았다 — 그 앱이 바뀌면 여기도 같이 고쳐야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import campaign

# ── 전처리 쪽 경계 (버퍼 출구) ────────────────────────────────────────────
#: 버퍼가 세워 두는 자세. 후단 투입 자세와 같아야 반전기가 안 붙는다.
BUFFER_POSE = "유리면 ↓ · 백시트 ↑"

#: R-A(정상 유리) 카세트 25장 × 2기. 후단으로 나가는 것은 이 계통뿐이다.
BUFFER_RA_SLOTS = 50
#: R-B(파손 유리) 카세트 25장 × 2기 — 시트 박리가 불가능해 파편 계통으로 빠진다.
BUFFER_RB_SLOTS = 50
#: 판정 보류 5장.
BUFFER_HOLD_SLOTS = 5

#: 전처리가 다루는 최대 모듈 (mm).
UPSTREAM_MAX_MM = (2500, 1400)

# ── 후단 DG-HK 2400 Rev.10 (앱에서 옮긴 값) ──────────────────────────────
#: 투입 상한 (mm) — 앱의 panelLength/panelWidth max.
DOWNSTREAM_MAX_MM = (2400, 1200)
#: 투입 하한 (mm) — 앱의 min.
DOWNSTREAM_MIN_MM = (1600, 800)
#: 후단 투입 자세.
DOWNSTREAM_POSE = "유리면 ↓ · 백시트 ↑"
#: 가열 시작 전에 5단을 다 채운다 (FULL_LOAD_ACK).
DOWNSTREAM_LOAD_PANELS = 5

#: 앱 기본값 — IR 램프 60개, 1개 정격 kW, 실효 열효율 %.
LAMP_COUNT = 60
LAMP_KW = 2.5
HEAT_EFFICIENCY_PCT = 65.0

#: 업로드된 그대로의 칼날 속도·인계시간 (mm/s, s/장). 이 상태로는 46.5 장/h 라
#: 유입 66.0 을 못 받는다 — B안이 나온 이유이자, 개선 전 기준으로 남겨 둔다.
AS_UPLOADED_KNIFE_MM_S = 40.0
AS_UPLOADED_HANDLING_S = 10.0

#: **채택 구성 (B안)** — 듀얼 진공테이블로 인계를 겹치고 칼날을 상한까지 올린다.
#: 버퍼에 실제로 연결되는 것은 이 구성이다.
ADOPTED_PLAN = "B"
KNIFE_SPEED_MM_S = 60.0
HANDLING_S = 6.0
#: 칼날 속도 상한 (mm/s) — 앱의 knifeSpeed max.
KNIFE_SPEED_MAX_MM_S = 60.0

#: 면적당 열용량 (kJ/m²·K) 과 승온폭 (K), 그리고 열전달 하한 체류시간 (s).
#: 셋 다 DG-HK 앱의 상수다.
AREAL_CP_KJ_M2K = 8.7358962
DELTA_T_K = 175.0
FDM_DWELL_S = 113.15
#: 탠덤 진입 리드 (mm) — 앱의 300/speed 항.
TANDEM_LEAD_MM = 300.0


@dataclass(frozen=True)
class DownstreamRate:
    heat_per_panel_mj: float
    dwell_s: float          # 5단 가열 체류시간
    release_pitch_s: float  # IR 순차 방출간격 = dwell/5
    thermal_per_h: float
    tandem_cycle_s: float
    tandem_per_h: float
    line_per_h: float
    bottleneck: str


def downstream_rate(length_mm: float = DOWNSTREAM_MAX_MM[0],
                    width_mm: float = DOWNSTREAM_MAX_MM[1],
                    knife_speed_mm_s: float = KNIFE_SPEED_MM_S,
                    handling_s: float = HANDLING_S,
                    lamp_kw: float = LAMP_KW,
                    efficiency_pct: float = HEAT_EFFICIENCY_PCT) -> DownstreamRate:
    """DG-HK 2400 의 장/h — 앱의 updateCalculator 를 그대로 옮긴 것."""
    heat_kj = (length_mm * width_mm / 1e6) * AREAL_CP_KJ_M2K * DELTA_T_K
    useful_kw = LAMP_COUNT * lamp_kw * (efficiency_pct / 100.0)
    dwell = max(DOWNSTREAM_LOAD_PANELS * heat_kj / useful_kw, FDM_DWELL_S)
    pitch = dwell / DOWNSTREAM_LOAD_PANELS
    tandem_cycle = TANDEM_LEAD_MM / knife_speed_mm_s + length_mm / knife_speed_mm_s + handling_s
    thermal = 3600.0 / pitch
    tandem = 3600.0 / tandem_cycle
    return DownstreamRate(
        round(heat_kj / 1000.0, 2), round(dwell, 2), round(pitch, 2),
        round(thermal, 1), round(tandem_cycle, 1), round(tandem, 1),
        round(3600.0 / max(pitch, tandem_cycle), 1),
        "IR 열공정" if thermal < tandem else "2단 탠덤 박리")


def as_uploaded_rate() -> DownstreamRate:
    """개선 전(업로드된 그대로) 후단 능력 — B안의 출발점이자 C안의 기준."""
    return downstream_rate(knife_speed_mm_s=AS_UPLOADED_KNIFE_MM_S,
                           handling_s=AS_UPLOADED_HANDLING_S)


def sheet_glass_per_h() -> float:
    """버퍼에서 후단으로 나가는 정상 유리(R-A) 유입률 (장/h).

    파손 유리(R-B)는 시트로 못 벗기므로 후단에 넣지 않는다 — 여기서 빠진다.
    """
    s = campaign.summary()
    return round(s["normal"] / s["run_s"] * 3600.0, 1)


def rate_gap_per_h() -> float:
    """유입 − 처리. 양수면 버퍼가 찬다."""
    return round(sheet_glass_per_h() - downstream_rate().line_per_h, 1)


def buffer_autonomy_h() -> float:
    """R-A 버퍼가 가득 차기까지 (h).

    채택 구성에서는 후단이 유입보다 빠르므로 버퍼가 차지 않는다 — 무한대다.
    그때 버퍼는 '밀린 것을 쌓는 곳'이 아니라 후단 정지를 버티는 완충으로 쓰인다.
    """
    gap = rate_gap_per_h()
    return round(BUFFER_RA_SLOTS / gap, 2) if gap > 0 else float("inf")


def buffer_ride_through_h() -> float:
    """후단이 멈춰도 전처리가 계속 돌 수 있는 시간 (h) — 버퍼가 다 찰 때까지."""
    return round(BUFFER_RA_SLOTS / sheet_glass_per_h(), 2)


def knife_speed_for_balance(handling_s: float = HANDLING_S) -> float:
    """그 인계 시간에서 유입을 그대로 받으려면 필요한 칼날 속도 (mm/s).

    기본값은 채택된 인계 6 s. 업로드 당시의 10 s 를 넣으면 상한 60 을 넘는 값이
    나온다 — 칼날만 올려서는 균형이 잡히지 않고 인계 단축이 전제였다는 근거다.
    """
    target_cycle = 3600.0 / sheet_glass_per_h()
    return round((TANDEM_LEAD_MM + DOWNSTREAM_MAX_MM[0]) / (target_cycle - handling_s), 1)


def balances_at_max_knife_speed(handling_s: float = HANDLING_S) -> bool:
    """칼날을 상한까지 올리면 유입을 받아낼 수 있는가."""
    return downstream_rate(knife_speed_mm_s=KNIFE_SPEED_MAX_MM_S,
                           handling_s=handling_s).line_per_h >= sheet_glass_per_h()


def pose_matches() -> bool:
    """경계에 반전기가 필요 없는가."""
    return BUFFER_POSE == DOWNSTREAM_POSE


def oversize_mm() -> tuple[float, float]:
    """전처리 상한 모듈이 후단 투입 상한을 넘는 양 (길이, 폭). 0 이면 들어간다."""
    return (max(0.0, UPSTREAM_MAX_MM[0] - DOWNSTREAM_MAX_MM[0]),
            max(0.0, UPSTREAM_MAX_MM[1] - DOWNSTREAM_MAX_MM[1]))


def fits_downstream(length_mm: float, width_mm: float) -> bool:
    """그 모듈이 후단에 들어가는가."""
    return (DOWNSTREAM_MIN_MM[0] <= length_mm <= DOWNSTREAM_MAX_MM[0]
            and DOWNSTREAM_MIN_MM[1] <= width_mm <= DOWNSTREAM_MAX_MM[1])


def summary() -> dict[str, object]:
    d = downstream_rate()
    over_l, over_w = oversize_mm()
    return {
        "pose_ok": pose_matches(),
        "oversize_length_mm": over_l,
        "oversize_width_mm": over_w,
        "feed_per_h": sheet_glass_per_h(),
        "downstream_per_h": d.line_per_h,
        "bottleneck": d.bottleneck,
        "gap_per_h": rate_gap_per_h(),
        "buffer_autonomy_h": buffer_autonomy_h(),
        "knife_speed_needed": knife_speed_for_balance(),
        "knife_speed_needed_as_uploaded": knife_speed_for_balance(AS_UPLOADED_HANDLING_S),
        "balances_at_max_knife": balances_at_max_knife_speed(),
    }


# ── 균형 안 두 가지 ────────────────────────────────────────────────────────
# 유입 66.0 대 처리 46.5 장/h 의 격차 19.5 를 어느 쪽에서 흡수할 것인가.
# B안은 후단을 올리고, C안은 전처리를 내린다. 둘 다 성립하지만 잃는 것이 다르다.

#: B안이 곧 채택 구성이다 — 값을 두 벌로 적지 않는다.
PLAN_B_HANDLING_S = HANDLING_S
PLAN_B_KNIFE_MM_S = KNIFE_SPEED_MM_S


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    lever: str            # 무엇을 움직이는가
    feed_per_h: float     # 전처리에서 나오는 정상 유리
    capacity_per_h: float  # 후단이 받는 양
    margin_per_h: float   # 여유 (음수면 여전히 밀린다)
    cost: str             # 무엇을 잃는가


def plan_b() -> Plan:
    """후단을 유입에 맞춘다 — 전처리는 그대로 두고 탠덤 사이클을 줄인다.

    병목이 2단 탠덤 박리이므로 손댈 곳은 칼날 속도와 인계시간 둘뿐이다.
    IR 열공정은 79.7 장/h 로 여유가 있어 증설 대상이 아니다.
    """
    d = downstream_rate(knife_speed_mm_s=PLAN_B_KNIFE_MM_S, handling_s=PLAN_B_HANDLING_S)
    feed = sheet_glass_per_h()
    return Plan(
        "B", "후단 개선",
        f"칼날 {AS_UPLOADED_KNIFE_MM_S:g} → {PLAN_B_KNIFE_MM_S:g} mm/s · "
        f"인계 {AS_UPLOADED_HANDLING_S:g} → {PLAN_B_HANDLING_S:g} s/장",
        feed, d.line_per_h, round(d.line_per_h - feed, 1),
        "듀얼 진공테이블 증설과 칼날 증속 — HKS 추력·장력·유리응력 DOE 가 선행돼야 한다")


def plan_c_hold_s() -> float:
    """C안에서 필요한 방출 보류 (s) — 정상 유리 유입을 후단 능력까지 낮춘다.

    셀 점유시간은 건드리지 않는다. 로봇이 손을 늦게 떼는 것만으로 택트를 늘린다.
    """
    capacity = as_uploaded_rate().line_per_h
    lo, hi = 0.0, 120.0
    for _ in range(60):                      # 이분법 — 보류가 늘면 유입은 단조 감소
        mid = (lo + hi) / 2.0
        s = campaign.summary(mid)
        if s["normal"] / s["run_s"] * 3600.0 > capacity:
            lo = mid
        else:
            hi = mid
    return round(hi, 1)


def plan_c() -> Plan:
    """전처리를 후단에 맞춘다 — 방출 보류로 택트를 늘린다."""
    hold = plan_c_hold_s()
    s = campaign.summary(hold)
    feed = round(s["normal"] / s["run_s"] * 3600.0, 1)
    capacity = as_uploaded_rate().line_per_h
    return Plan(
        "C", "전처리 감속",
        f"방출 보류 +{hold:g} s · 택트 {campaign.summary()['takt_s']:g} → {s['takt_s']:g} s",
        feed, capacity, round(capacity - feed, 1),
        f"전체 처리량 {campaign.summary()['throughput_per_h']:g} → {s['throughput_per_h']:g} 장/h, "
        f"병목 JBR 가동률 {JBR_UTILISATION_BASE:.0%} → {campaign.JBR_S / s['takt_s']:.0%} 로 놀게 된다")


#: 기준 상태에서 병목(JBR)이 실제로 물려 있는 비율 — C안의 손실을 재는 기준.
JBR_UTILISATION_BASE = campaign.JBR_S / campaign.summary()["takt_s"]


def plans() -> tuple[Plan, Plan]:
    return (plan_b(), plan_c())
