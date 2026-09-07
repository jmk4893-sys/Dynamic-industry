"""전처리 라인 → 후단 유리제거기 인계 — 버퍼에서 무엇이 맞고 무엇이 안 맞는가.

전처리 플랜트의 마지막 공정은 알루미늄 프레임 제거(AFR) 뒤의 유리 버퍼 GBR-301
이다. 그 버퍼가 후단 **DG-HK60C** (`hk60c.py` — 5단 밀폐 IR 가열실 · 이동 나이프
탠덤 · 5단 냉각 랙, `docs/dg-hk60-rfq.html`) 의 투입 셔틀 LD-101 로 이어진다.

두 라인을 잇는다는 것은 링크를 거는 일이 아니라 **경계 조건이 맞는지 따지는
일**이다. REV.54 에서 넷을 다시 쟀다.

* **자세** — 후단은 유리면 ↓·백시트 ↑ 로 받는다. 버퍼도 같은 자세다. (맞는다.)
* **치수** — 후단 상한 2,400 × 1,200 이다. REV.53 까지 전처리는 2,500 × 1,400 을
  상한으로 두고 옛 후단의 데크를 넓혀 맞췄는데, 이번에는 **라인 전체를 후단 상한
  으로 통일**했다 (발주처 결정 — README §58). 넓혀도 플랜트 하드웨어에서 되돌려
  받는 절감이 없고, 후단의 IR 뱅크 해석·파일럿·부품도 일습이 그 상한 위에 서
  있기 때문이다. 초과 모듈은 반입 등록에서 범위 외 리젝트로 빠진다 (`recipe.py`).
* **처리율** — 정상 유리(R-A) 유입 66.0 장/h 가 후단 순생산 60.5 장/h 보다
  빠르다. 버퍼가 완충하지만 유한하므로 몇 시간 만에 찬다. 그래서 전처리를
  **후단 능력에서 파생한 택트로 페이싱**한다 (`campaign.RELEASE_HOLD_S`).
* **인계 방식** — 후단은 바닥 팔레트 픽업 스테이션과 발주자 디스태커를 전제
  했다. 플랜트에서는 BX-101 브리지가 그 디스태커 자리를 대신해 GBR 캐리지 슬롯
  에서 유리 한 장을 뽑아 LD-101 롤러베드(EL 1,150)에 놓는다 (`layout.py`).

후단 수치는 **옮겨 적지 않는다** — 전부 `hk60c.py` 가 그 기계의 콘솔·사양서에서
읽고, 여기서는 그 값을 버퍼 쪽 값과 대조할 뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import campaign, hk60c, line

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

#: 전처리가 다루는 최대 모듈 (mm) — **후단 상한과 같다** (REV.54 통일).
#: 한 라인에 상한이 둘이면 반드시 한쪽이 못 받는다. 값은 후단이 갖고, 전처리는
#: 그것을 읽는다 — `campaign.PANEL_LENGTH_MM`·`kinematics.PANEL_MM` 도 같은 값이다.
UPSTREAM_MAX_MM = line.LINE_MAX_MM

# ── 후단 DG-HK60C ──────────────────────────────────────────────────────────
#: 투입 상한·하한 (mm) — 사양서 4.2 의 범위.
DOWNSTREAM_MAX_MM = hk60c.PANEL_MAX_MM
DOWNSTREAM_MIN_MM = hk60c.PANEL_MIN_MM
#: 후단 투입 자세.
DOWNSTREAM_POSE = hk60c.POSE
#: 가열 시작 전에 5단을 다 채운다 (FULL_LOAD_ACK). 그 뒤로는 방출한 단을 곧바로
#: 재장전하는 회전식이라, 시각표로는 롤링과 같다 — `glass_removal_timeline`.
DOWNSTREAM_LOAD_PANELS = hk60c.DECKS

#: IR 뱅크 — 단수+1 = 6 뱅크에 40등, 관당 2.5 kW, 설치 100 kW. 콘솔 값이다.
LAMP_COUNT = hk60c.LAMPS
LAMP_KW = hk60c.LAMP_KW
IR_INSTALLED_KW = hk60c.IR_INSTALLED_KW
HEAT_EFFICIENCY_PCT = hk60c.HEAT_EFFICIENCY_PCT
FDM_DWELL_S = hk60c.FDM_DWELL_S
KNIFE_SPEED_MM_S = hk60c.KNIFE_SPEED_MM_S


@dataclass(frozen=True)
class DownstreamRate:
    heat_per_panel_mj: float
    dwell_s: float          # 5단 소킹
    release_pitch_s: float  # 방출 피치 = 소킹/5
    thermal_per_h: float
    tandem_cycle_s: float
    tandem_per_h: float     # 명목
    line_per_h: float       # 순생산 (계획 정지 예산 10 % 를 뺀 값)
    bottleneck: str


def downstream_rate(lamp_count: int | None = None, lamp_kw: float | None = None) -> DownstreamRate:
    """후단 능력 — `hk60c.rate()` 를 그대로 옮겨 담는다. 값은 콘솔과 같아야 한다.

    램프 수·관 정격은 이 모듈의 값을 **호출 시점에** 읽는다 — ai.envelope_bounds 가
    뱅크를 흔들어 소성시간이 따라오는지를 시험한다(리터럴이면 못 따라온다).
    """
    # 라인 패널 크기에서의 능력 — 벤더 사이클은 패널 길이에 비례하므로 포락선(2,500)이 아니라
    # 실제로 들어가는 패널(line.LINE_MAX_MM)로 낸다. 벤더 계약값(포락선)은 hk60c.RATE_PER_H.
    r = hk60c.rate(UPSTREAM_MAX_MM[0], UPSTREAM_MAX_MM[1],
                   lamps=LAMP_COUNT if lamp_count is None else lamp_count,
                   lamp_kw=LAMP_KW if lamp_kw is None else lamp_kw)
    return DownstreamRate(r.heat_per_panel_mj, r.dwell_s, r.release_pitch_s, r.thermal_per_h,
                          r.tandem_cycle_s, r.tandem_per_h, r.line_per_h, r.bottleneck)


def sheet_glass_per_h(hold_s: float | None = None) -> float:
    """버퍼에서 후단으로 나가는 정상 유리(R-A) 유입률 (장/h).

    파손 유리(R-B)는 시트로 못 벗기므로 후단에 넣지 않는다 — 여기서 빠진다.
    기본값은 **페이싱된** 라인이다. `hold_s=0` 을 주면 제 속도의 유입이 나온다.
    """
    s = campaign.summary(campaign.RELEASE_HOLD_S if hold_s is None else hold_s)
    return round(s["normal"] / s["run_s"] * 3600.0, 1)


def unpaced_sheet_glass_per_h() -> float:
    """페이싱 전 유입 — 라인이 제 속도로 돌 때. 격차의 근거로 남긴다."""
    return sheet_glass_per_h(0.0)


def rate_gap_per_h(hold_s: float | None = None) -> float:
    """유입 − 처리. 양수면 버퍼가 찬다."""
    return round(sheet_glass_per_h(hold_s) - downstream_rate().line_per_h, 1)


def buffer_autonomy_h(hold_s: float | None = None) -> float:
    """R-A 버퍼가 빈 상태에서 가득 차기까지 (h). 유입이 처리보다 느리면 무한대."""
    gap = rate_gap_per_h(hold_s)
    return round(BUFFER_RA_SLOTS / gap, 2) if gap > 0 else float("inf")


# ── 페이싱 — 격차를 전처리가 흡수한다 ──────────────────────────────────────
# 유입 66.0 대 처리 60.5 장/h 의 격차 5.5 를 어느 쪽에서 흡수할 것인가.
# 후단을 올리는 길(칼날 60 mm/s 는 FAT 상한이라 승인 전 사용 금지, 트윈은 두 배
# 설비)은 이 회차의 것이 아니다. 전처리가 방출 보류로 택트를 늘린다 — 셀
# 점유시간은 그대로 두고 로봇이 손을 늦게 떼는 것뿐이라 기구가 안 바뀐다.
# 보류량은 손으로 적지 않는다: `campaign.release_hold_s()` 가 후단 능력에서 낸다.


@dataclass(frozen=True)
class Pacing:
    feed_unpaced_per_h: float   # 제 속도 유입
    capacity_per_h: float       # 후단 순생산
    margin_per_h: float         # 설계 여유 (campaign.HANDOFF_MARGIN_PER_H)
    allowed_per_h: float        # 허용 R-A 유입
    hold_s: float               # 방출 보류
    takt_s: float               # 페이싱된 택트
    feed_per_h: float           # 페이싱된 R-A 유입
    gap_per_h: float            # 페이싱 후 유입 − 처리 (음수여야 한다)
    annual_loss_pct: float      # 연간 처리량 감소


def pacing() -> Pacing:
    hold = campaign.RELEASE_HOLD_S
    base, held = campaign.summary(0.0), campaign.summary(hold)
    return Pacing(
        unpaced_sheet_glass_per_h(), downstream_rate().line_per_h, campaign.HANDOFF_MARGIN_PER_H,
        round(downstream_rate().line_per_h - campaign.HANDOFF_MARGIN_PER_H, 1),
        hold, held["takt_s"], sheet_glass_per_h(), rate_gap_per_h(),
        round((1 - held["throughput_per_h"] / base["throughput_per_h"]) * 100, 1))


def the_line_is_paced() -> bool:
    """페이싱 뒤에는 유입이 처리를 넘지 않고, 보류를 1초 줄이면 다시 넘는가."""
    return (rate_gap_per_h() <= 0
            and rate_gap_per_h(max(0.0, campaign.RELEASE_HOLD_S - 1.0)) > rate_gap_per_h())


# ── 버퍼는 방향이 둘이다 ────────────────────────────────────────────────
#
# 종전 모델은 완충시간을 `R-A 슬롯 ÷ 유입` 하나로만 냈다. 그것은 **버퍼가 비어
# 있다**는 전제이고, 그 전제에서 버퍼가 막는 것은 후단 정지 하나뿐이다 —
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
#
# REV.54: 후단의 계획 정지(칼날 카세트 교환 3.9 분 · 만권 롤 4.9 h 마다)는 순생산
# 60.5 에 이미 평균으로 들어 있고, 낱개 정지는 이 여유공간이 받는다.


#: 적재 컬럼은 셋이다 — R-A 열·HOLD 열·R-B 열이 각자 마스트·승강캐리지·
#: 콤포크를 갖는다. **버퍼가 자기 자신은 못 막으므로** 그 셋이 서로를 받는다:
#: 캐리지는 같은 물건이고 배분이 레시피라, 한 열의 포크가 서면 그 열이 맡던
#: 유리를 다른 열이 받는다. 처음에는 POST→후단 직결 통과 레인을 넣으려 했는데,
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


# ── 유리제거기를 캠페인에 이어 붙이기 ──────────────────────────────────────
# 60장 캠페인은 버퍼에서 끝나지 않고 **유리가 벗겨져 나오는 시각**까지 이어진다.
# DG-HK60C 는 5단 만재(FULL_LOAD_ACK) 뒤 밀폐 가열을 시작하고, 소킹이 끝난 단부터
# 44.5 s 피치로 한 장씩 방출해 **같은 단에 곧바로 재장전**한다 (사양서 3.x).
# 시각표로는 "n 번째 장은 n−5 번째가 나가야 들어간다" 는 롤링과 같다. 계획
# 정지(카세트 교환·롤 반출)는 이 결정적 시각표에 없다 — 순생산 60.5 에 평균으로
# 들어 있고, 낱개 정지는 버퍼 여유공간이 받는다.


@dataclass(frozen=True)
class GlassOut:
    """유리제거기를 빠져나온 유리 한 장."""

    order: int          # R-A 스트림 안 순번 1…53
    panel_index: int    # 캠페인 전체 순번 1…60
    arrive_s: float     # 버퍼(R-A) 도착 = 캠페인의 afr_end
    load_s: float       # 데크 적재 시각
    peel_start_s: float
    peel_end_s: float

    @property
    def wait_s(self) -> float:
        """버퍼에 머문 시간 — 0 이면 유리제거기가 곧바로 받았다."""
        return round(self.load_s - self.arrive_s, 2)


def glass_removal_timeline(hold_s: float | None = None) -> tuple[GlassOut, ...]:
    """R-A 정상 유리가 유리제거기를 통과하는 시각표."""
    hold = campaign.RELEASE_HOLD_S if hold_s is None else hold_s
    d = downstream_rate()
    dwell, cycle = d.dwell_s, d.tandem_cycle_s
    stream = [p for p in campaign.panels(hold) if p.buffer == "R-A"]
    if not stream:
        return ()
    # 첫 배치 5장은 데크가 전부 비어 있으므로 도착 즉시 실린다. 그 5장이 다
    # 실린 순간이 FULL_LOAD_ACK 이고, 거기서부터 가열이 시작된다.
    first_ack = max(p.afr_end for p in stream[:DOWNSTREAM_LOAD_PANELS])
    starts: list[float] = []
    ends: list[float] = []
    rows: list[GlassOut] = []
    for n, panel in enumerate(stream):
        # n−5 번째가 박리로 빠져나가야 그 단이 빈다 — 방출 즉시 재장전
        deck_free = 0.0 if n < DOWNSTREAM_LOAD_PANELS else starts[n - DOWNSTREAM_LOAD_PANELS]
        load = max(panel.afr_end, deck_free)
        heat_from = first_ack if n < DOWNSTREAM_LOAD_PANELS else load
        start = max(heat_from + dwell, ends[-1] if ends else 0.0)
        starts.append(start)
        ends.append(start + cycle)
        rows.append(GlassOut(n + 1, panel.index, round(panel.afr_end, 2),
                             round(load, 2), round(start, 2), round(start + cycle, 2)))
    return tuple(rows)


def glass_removal_summary(hold_s: float | None = None) -> dict[str, float]:
    """유리제거까지 포함한 캠페인 요약 — 플랜트가 유리를 다 벗기는 시각."""
    hold = campaign.RELEASE_HOLD_S if hold_s is None else hold_s
    rows = glass_removal_timeline(hold)
    d = downstream_rate()
    buffer_end = campaign.summary(hold)["run_s"]
    finish = rows[-1].peel_end_s
    busy = len(rows) * d.tandem_cycle_s
    span = finish - rows[0].peel_start_s
    # 동시에 버퍼에 머무는 최대 매수 — R-A 75 슬롯이 실제로 충분한가.
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
    p = pacing()
    return {
        "model": hk60c.MODEL,
        "pose_ok": pose_matches(),
        "oversize_length_mm": over_l,
        "oversize_width_mm": over_w,
        "feed_unpaced_per_h": p.feed_unpaced_per_h,
        "feed_per_h": p.feed_per_h,
        "downstream_per_h": d.line_per_h,
        "downstream_nominal_per_h": d.tandem_per_h,
        "bottleneck": d.bottleneck,
        "gap_unpaced_per_h": rate_gap_per_h(0.0),
        "gap_per_h": p.gap_per_h,
        "autonomy_unpaced_h": buffer_autonomy_h(0.0),
        "buffer_autonomy_h": buffer_autonomy_h(),
        "hold_s": p.hold_s,
        "takt_s": p.takt_s,
        "annual_loss_pct": p.annual_loss_pct,
        "buffer_ra_slots": BUFFER_RA_SLOTS,
        "buffer_rb_slots": BUFFER_RB_SLOTS,
        "buffer_stock_slots": buffer_stock_target_slots(),
        "buffer_headroom_slots": buffer_headroom_slots(),
        "ride_through_h": buffer_ride_through_h(),
        "drain_ride_through_h": buffer_drain_ride_through_h(),
        "buffer_rebuild_h": buffer_rebuild_h(),
        "panel_max_mm": list(DOWNSTREAM_MAX_MM),
        "lamp_count": LAMP_COUNT,
        "lamp_kw": LAMP_KW,
        "ir_installed_kw": IR_INSTALLED_KW,
        "dwell_s": d.dwell_s,
        "release_pitch_s": d.release_pitch_s,
        "tandem_cycle_s": d.tandem_cycle_s,
        "thermal_per_h": d.thermal_per_h,
    }
