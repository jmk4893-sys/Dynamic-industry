"""전처리 라인 → 후단 박리 라인 인계 — 버퍼에서 무엇이 맞고 무엇이 안 맞는가.

전처리 플랜트의 마지막 공정은 알루미늄 프레임 제거(AFR) 뒤의 유리 버퍼다.
그 버퍼가 후단 장치 **DG-HK 2400**(5장 완전적재·60-IR 순차가열·2단 탠덤 박리,
`docs/drawings/pv-delam-tandem.html`)의 투입부로 이어진다.

두 라인을 잇는다는 것은 링크를 거는 일이 아니라 **경계 조건 세 가지가 맞는지
따지는 일**이다. 여기서는 그 셋을 계산해 어긋나는 것을 드러낸다.

* **자세** — 후단은 유리면 ↓·백시트 ↑ 로 받는다. 버퍼도 같은 자세로 세워 두므로
  경계에 반전기가 필요 없다. (이것만 맞는다.)
* **치수** — 전처리는 최대 2,500 × 1,400 을 다루는데 후단 투입 상한이
  2,400 × 1,200 이라 상한 패널이 들어가지 않았다. **데크를 2,500 × 1,400 으로
  넓혀 해소했다** — 램프는 데크 폭을 가로지르는 관이라 관 정격도 선출력을 유지해
  2.5 → 2.92 kW(뱅크 150 → 175 kW)로 같이 올렸다. 올리지 않으면 면적이 21.5 %
  커진 만큼 열이 모자라 IR 이 병목이 되고 유입을 못 받는다.
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

#: 캐리지 한 기의 슬롯 수. R-A·R-B 캐리지는 같은 물건이고 **레시피로 갈린다** —
#: 그래서 몇 기를 어느 쪽에 줄지가 설계 결정이다.
SLOTS_PER_CARRIAGE = 25

#: 캐리지 배분 (R-A, R-B). 총 4기는 그대로다 — 하드웨어도 전장도 안 늘어난다.
#:
#: 종전 2:2 는 유입량을 안 보고 나눈 값이었다. R-B(파손 유리)는 유입이 6.2 장/h
#: 라 50 슬롯이면 8 h 어치인데, R-A 는 66 장/h 라 50 슬롯이 0.76 h 밖에 안 된다.
#: 정지 완충이 필요한 쪽은 R-A 인데 여유는 R-B 에 쌓여 있었다. 3:1 로 옮기면
#: R-A 75 슬롯, R-B 25 슬롯(4.0 h)이 되고 둘 다 제 몫을 한다 — 파편 계통은
#: 지게차가 비우므로 4 h 면 충분하다.
BUFFER_CARRIAGES: tuple[int, int] = (3, 1)

BUFFER_RA_SLOTS = BUFFER_CARRIAGES[0] * SLOTS_PER_CARRIAGE
BUFFER_RB_SLOTS = BUFFER_CARRIAGES[1] * SLOTS_PER_CARRIAGE
#: 판정 보류 5장.
BUFFER_HOLD_SLOTS = 5

#: 전처리가 다루는 최대 모듈 (mm).
UPSTREAM_MAX_MM = (2500, 1400)

# ── 후단 DG-HK 2500 (DG-HK 2400 Rev.10 을 데크 확장한 것) ────────────────
#: 업로드된 그대로의 투입 상한 (mm) — 전처리 상한 2,500×1,400 을 못 받았다.
AS_UPLOADED_MAX_MM = (2400, 1200)

#: **데크 확장 후 투입 상한 (mm)** — 전처리 상한을 그대로 받는다.
#: 이 값이 UPSTREAM_MAX_MM 과 같아야 상한 모듈이 후단으로 들어간다.
DOWNSTREAM_MAX_MM = (2500, 1400)
#: 투입 하한 (mm) — 앱의 min. 데크를 넓혀도 하한은 그대로다.
DOWNSTREAM_MIN_MM = (1600, 800)
#: 후단 투입 자세.
DOWNSTREAM_POSE = "유리면 ↓ · 백시트 ↑"
#: 가열 시작 전에 5단을 다 채운다 (FULL_LOAD_ACK).
DOWNSTREAM_LOAD_PANELS = 5

#: IR 뱅크는 **6 라인 × 라인당 10등**이다 (앱의 3D 라벨 '6 라인 × 10 = 60 IR').
#: 라인은 5단 랙의 수평면이다 — 상부 1 + 단간 4 + 하부 1 = 6. 즉 라인 수는
#: **단수에서 나오지 폭에서 나오지 않는다**. 데크를 넓혀도 램프 '개수'는 60 그대로다.
#:
#: 대신 램프는 데크 폭을 가로지르는 **관**이라, 폭을 넓히면 관이 길어지고 정격도
#: 같이 올라간다. 선출력(폭 1 m 당 kW)을 유지하는 것이 확장의 조건이다.
#: 유지하지 않으면 면적이 21.5 % 커진 만큼 열이 모자라 IR 이 병목으로 넘어온다.
IR_LINES = 6
LAMPS_PER_LINE = 10
LAMP_COUNT = IR_LINES * LAMPS_PER_LINE
#: 램프 선출력 (kW/m) — 업로드된 1,200 mm 데크 · 관당 2.5 kW 에서 역산했다.
LAMP_KW_PER_M = 2.5 / 1.2
#: 업로드 당시 관당 정격 (kW) 과 뱅크 설치 용량 (kW).
AS_UPLOADED_LAMP_KW = 2.5
AS_UPLOADED_IR_KW = LAMP_COUNT * AS_UPLOADED_LAMP_KW
HEAT_EFFICIENCY_PCT = 65.0


def lamp_kw(width_mm: float = DOWNSTREAM_MAX_MM[1]) -> float:
    """데크 폭에서 파생한 램프 1관 정격 (kW) — 선출력을 유지한다."""
    return LAMP_KW_PER_M * width_mm / 1000.0


#: 데크 확장 후 관당 정격 (1,400 mm → 2.92 kW) 과 뱅크 설치 용량 (150 → 175 kW).
LAMP_KW = lamp_kw()
IR_INSTALLED_KW = LAMP_COUNT * LAMP_KW
#: 램프 피치 (mm) — 라인당 10등을 데크 길이에 고르게 편다.
#: 2,400 ÷ 10 = 240 이었고 확장 후 2,500 ÷ 10 = 250 이다. 4 % 늘어난 이 피치가
#: 길이방향 조도 균일도 안에 드는지는 계측캐리지 열전대로 확인해야 한다.
LAMP_PITCH_MM = DOWNSTREAM_MAX_MM[0] / LAMPS_PER_LINE

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
                    lamp_kw_override: float | None = None,
                    efficiency_pct: float = HEAT_EFFICIENCY_PCT) -> DownstreamRate:
    """DG-HK 2400 의 장/h — 앱의 updateCalculator 를 그대로 옮긴 것."""
    heat_kj = (length_mm * width_mm / 1e6) * AREAL_CP_KJ_M2K * DELTA_T_K
    # 관당 정격은 데크 폭에서 파생한다 — 폭만 넓히고 램프를 그대로 두면 열이 모자란다.
    kw = lamp_kw(width_mm) if lamp_kw_override is None else lamp_kw_override
    useful_kw = LAMP_COUNT * kw * (efficiency_pct / 100.0)
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
    """개선 전(업로드된 그대로) 후단 능력 — B안의 출발점이자 C안의 기준.

    데크·램프까지 업로드 당시 값으로 고정한다. 확장한 데크로 재면 '개선 전'이
    아니게 되고, 46.5 장/h 라는 출발점이 기록에서 사라진다.
    """
    return downstream_rate(length_mm=AS_UPLOADED_MAX_MM[0],
                           width_mm=AS_UPLOADED_MAX_MM[1],
                           knife_speed_mm_s=AS_UPLOADED_KNIFE_MM_S,
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


# ── 버퍼는 방향이 둘이다 ────────────────────────────────────────────────
#
# 종전 모델은 완충시간을 `R-A 슬롯 ÷ 유입` 하나로만 냈다. 그것은 **버퍼가 비어
# 있다**는 전제이고, 그 전제에서 버퍼가 막는 것은 후단(GRM) 정지 하나뿐이다 —
# 빈 버퍼는 상류가 서면 곧바로 후단을 굶긴다. 그런데 §44 는 CV·SG·GI 후단
# 계통을 "버퍼가 흡수한다" 고 적어 두었다. 그 계통은 버퍼 **상류**에 있으므로
# 재고가 있어야 흡수되는데, 모델에 재고가 없었다. OEE 가 품질률 1.0 위에
# 서 있던 것과 같은 종류의 공백이다.
#
# 그래서 버퍼를 **설정점 운전**으로 바꾼다. 슬롯을 재고와 여유공간으로 나누면
#   · 재고  → 상류가 서도 후단이 계속 돈다 (배출 방향)
#   · 여유  → 후단이 서도 전단이 계속 돈다 (충전 방향)
# 두 방향은 같은 슬롯을 나눠 쓰므로 한쪽을 키우면 한쪽이 준다. 나누는 지점은
# 두 방향의 완충시간이 같아지는 곳이다 — 어느 쪽도 먼저 무너지지 않는다.


#: 적재 컬럼은 셋이다 — R-A 열·HOLD 열·R-B 열이 각자 마스트·승강캐리지·
#: 콤포크를 갖는다. **버퍼가 자기 자신은 못 막으므로** 그 셋이 서로를 받는다:
#: 캐리지는 같은 물건이고 배분이 레시피라, 한 열의 포크가 서면 그 열이 맡던
#: 유리를 다른 열이 받는다. 처음에는 POST→GRM 직결 통과 레인을 넣으려 했는데,
#: 3D 를 재 보니 그 레인이 지날 Z 통로가 없다 — 마스트·타이빔·안전 스캐너가
#: 열 사이를 다 쓰고 있다. 없는 통로를 도면에 그리는 대신 이미 있는 3열을 쓴다.
LOADER_COLUMNS = ("R-A", "HOLD", "R-B")

#: 3열로도 못 막는 자리. 주행이 서면 어느 열에도 못 간다. 그래서 같은 레일에
#: 구동을 둘 걸었다(AXIS-GBR-X ×2) — 한쪽이 죽으면 감속 주행한다.
#: **그래도 공통으로 남는 것**은 레일과 셔틀 데크 구조다. 숨기지 않고 적는다 —
#: BFC 의 "완전정지는 공통부(포탈·유압)뿐" 과 같은 취급이다.
COMMON_MODE = "주행 레일과 셔틀 데크 구조 — 구동 이중화로도 안 덮인다"


def buffer_stock_target_slots() -> int:
    """정상 운전에서 유지하는 재고 (슬롯).

    배출률과 유입률의 비로 나눈다. 재고는 배출률로, 여유공간은 유입률로
    소비되므로 이 비율에서 두 방향 완충시간이 같아진다 — 임의 상수가 없다.
    """
    draw = downstream_rate().line_per_h
    return round(BUFFER_RA_SLOTS * draw / (draw + sheet_glass_per_h()))


def buffer_headroom_slots() -> int:
    """설정점 위로 남는 빈 슬롯 — 충전 방향이 쓰는 몫."""
    return BUFFER_RA_SLOTS - buffer_stock_target_slots()


def buffer_ride_through_h() -> float:
    """**후단**이 멈춰도 전처리가 계속 돌 수 있는 시간 (h).

    설정점 위의 여유공간이 다 찰 때까지다. 재고를 들고 있으므로 종전의
    "빈 버퍼" 값보다 짧다 — 배출 방향을 얻는 대가다.
    """
    return round(buffer_headroom_slots() / sheet_glass_per_h(), 2)


def buffer_drain_ride_through_h() -> float:
    """**상류**가 멈춰도 후단이 계속 돌 수 있는 시간 (h) — 재고가 바닥날 때까지."""
    return round(buffer_stock_target_slots() / downstream_rate().line_per_h, 2)


def buffer_rebuild_h() -> float:
    """재고를 다시 채우는 데 걸리는 시간 (h).

    정상 운전에서는 후단 능력이 유입보다 빠르므로 버퍼가 안 쌓인다. 재고는
    후단을 유입보다 느리게 돌려야 쌓이고, 그 여유가 `−rate_gap_per_h()` 다.
    출력을 잃는 것이 아니라 미루는 것이다 — 쌓아 둔 장은 나중에 처리된다.
    계획 정지에 후단만 세우면 유입 속도로 채워지므로 훨씬 빠르다.
    """
    surplus = -rate_gap_per_h()
    if surplus <= 0:
        return float("inf")
    return round(buffer_stock_target_slots() / surplus, 1)


def buffer_startup_fill_h() -> float:
    """가동 시작에서 후단을 잡고 전단만 돌려 재고를 만드는 시간 (h)."""
    return round(buffer_stock_target_slots() / sheet_glass_per_h(), 2)


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


# ── 유리제거셀을 캠페인에 이어 붙이기 ──────────────────────────────────────
# REV.23 에서 유리제거(박리) 라인이 플랜트의 한 존(GRM-401)이 되면서, 60장
# 캠페인도 버퍼에서 끝나지 않고 **유리가 벗겨져 나오는 시각**까지 이어진다.
# 여기 모델은 후단 앱의 10장 모델(rolling 5-deck)을 그대로 옮긴 것이다.


@dataclass(frozen=True)
class GlassOut:
    """유리제거셀을 빠져나온 유리 한 장."""

    order: int          # R-A 스트림 안 순번 1…53
    panel_index: int    # 캠페인 전체 순번 1…60
    arrive_s: float     # 버퍼(R-A) 도착 = 캠페인의 afr_end
    load_s: float       # 데크 적재 시각
    peel_start_s: float
    peel_end_s: float

    @property
    def wait_s(self) -> float:
        """버퍼에 머문 시간 — 0 이면 유리제거셀이 곧바로 받았다."""
        return round(self.load_s - self.arrive_s, 2)


def glass_removal_timeline(hold_s: float = campaign.RELEASE_HOLD_S) -> tuple[GlassOut, ...]:
    """R-A 정상 유리가 유리제거셀을 통과하는 시각표.

    5단 랙은 롤링이다 — n 번째 장은 n−5 번째 장이 **박리로 빠져나가야** 그
    데크에 들어간다. 첫 배치만 FULL_LOAD_ACK 이라 5장이 다 실린 뒤에 가열이
    시작되고, 그 뒤로는 실린 순간부터 가열된다.
    """
    d = downstream_rate()
    dwell, cycle = d.dwell_s, d.tandem_cycle_s
    stream = [p for p in campaign.panels(hold_s) if p.buffer == "R-A"]
    if not stream:
        return ()
    # 첫 배치 5장은 데크가 전부 비어 있으므로 도착 즉시 실린다. 그 5장이 다
    # 실린 순간이 FULL_LOAD_ACK 이고, 거기서부터 가열이 시작된다.
    first_ack = max(p.afr_end for p in stream[:DOWNSTREAM_LOAD_PANELS])
    starts: list[float] = []
    ends: list[float] = []
    rows: list[GlassOut] = []
    for n, panel in enumerate(stream):
        # n−5 번째가 박리로 빠져나가야 그 데크가 빈다
        deck_free = 0.0 if n < DOWNSTREAM_LOAD_PANELS else starts[n - DOWNSTREAM_LOAD_PANELS]
        load = max(panel.afr_end, deck_free)
        heat_from = first_ack if n < DOWNSTREAM_LOAD_PANELS else load
        start = max(heat_from + dwell, ends[-1] if ends else 0.0)
        starts.append(start)
        ends.append(start + cycle)
        rows.append(GlassOut(n + 1, panel.index, round(panel.afr_end, 2),
                             round(load, 2), round(start, 2), round(start + cycle, 2)))
    return tuple(rows)


def glass_removal_summary(hold_s: float = campaign.RELEASE_HOLD_S) -> dict[str, float]:
    """유리제거까지 포함한 캠페인 요약 — 플랜트가 유리를 다 벗기는 시각."""
    rows = glass_removal_timeline(hold_s)
    d = downstream_rate()
    buffer_end = campaign.summary(hold_s)["run_s"]
    finish = rows[-1].peel_end_s
    busy = len(rows) * d.tandem_cycle_s
    span = finish - rows[0].peel_start_s
    # 동시에 버퍼에 머무는 최대 매수 — R-A 50 슬롯이 실제로 충분한가.
    events = [(r.arrive_s, 1) for r in rows] + [(r.load_s, -1) for r in rows]
    events.sort(key=lambda e: (e[0], e[1]))
    held = peak = 0
    for _, delta in events:
        held += delta
        peak = max(peak, held)
    return {
        "sheets": float(len(rows)),
        "buffer_run_s": round(buffer_end, 2),
        "glass_finish_s": round(finish, 2),
        "glass_finish_min": round(finish / 60.0, 1),
        "tail_s": round(finish - buffer_end, 2),
        "max_buffer_wait_s": round(max(r.wait_s for r in rows), 2),
        "peak_buffer_sheets": float(peak),
        "grm_utilisation": round(busy / span, 3) if span > 0 else 0.0,
        "glass_per_h": round(len(rows) / finish * 3600.0, 1),
    }


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
        "buffer_ra_slots": BUFFER_RA_SLOTS,
        "buffer_rb_slots": BUFFER_RB_SLOTS,
        "buffer_stock_slots": buffer_stock_target_slots(),
        "buffer_headroom_slots": buffer_headroom_slots(),
        "ride_through_h": buffer_ride_through_h(),
        "drain_ride_through_h": buffer_drain_ride_through_h(),
        "buffer_rebuild_h": buffer_rebuild_h(),
        "deck_widened_to_mm": list(DOWNSTREAM_MAX_MM),
        "lamp_count": LAMP_COUNT,
        "lamp_kw": round(LAMP_KW, 2),
        "ir_installed_kw": IR_INSTALLED_KW,
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
    데크 확장은 처리율을 올리려는 것이 아니라 상한 모듈을 받으려는 것이고,
    오히려 사이클을 51.0 → 52.7 s 로 늘려 여유를 +4.6 에서 +2.4 로 줄인다.
    IR 은 관 정격을 폭에 맞춰 올려(2.5 → 2.92 kW) 병목으로 넘어오지 않게 했다.
    """
    d = downstream_rate(knife_speed_mm_s=PLAN_B_KNIFE_MM_S, handling_s=PLAN_B_HANDLING_S)
    feed = sheet_glass_per_h()
    return Plan(
        "B", "후단 개선",
        f"데크 {AS_UPLOADED_MAX_MM[0]:,} × {AS_UPLOADED_MAX_MM[1]:,} → "
        f"{DOWNSTREAM_MAX_MM[0]:,} × {DOWNSTREAM_MAX_MM[1]:,} · "
        f"칼날 {AS_UPLOADED_KNIFE_MM_S:g} → {PLAN_B_KNIFE_MM_S:g} mm/s · "
        f"인계 {AS_UPLOADED_HANDLING_S:g} → {PLAN_B_HANDLING_S:g} s/장 · "
        f"IR 관 {AS_UPLOADED_LAMP_KW:g} → {LAMP_KW:.2f} kW ({LAMP_COUNT}등 · 뱅크 "
        f"{AS_UPLOADED_IR_KW:g} → {IR_INSTALLED_KW:g} kW)",
        feed, d.line_per_h, round(d.line_per_h - feed, 1),
        "듀얼 진공테이블 증설·칼날 증속·데크 확장·IR 뱅크 +25 kW — "
        "HKS 추력·장력·유리응력 DOE 가 선행돼야 한다")


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
