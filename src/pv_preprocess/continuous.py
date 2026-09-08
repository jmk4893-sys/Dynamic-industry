"""60분 연속 운전 — 장비마다 한 장을 붙잡는 시간을 재고, 가장 긴 자리를 병목으로
잡고, 그 병목이 흐름을 끊는지 60분을 실제로 흘려 본다.

`campaign` 은 팔레트 두 개(60장 · 54.6분)를 흘려 셀 점유를 보여 준다. 그것으로는
**연속 운전에서 무엇이 무엇을 기다리는지**가 안 보인다 — 한 캠페인은 시작할 때
비어 있고 끝날 때 마르므로, 자원이 놀았던 시간이 정상 운전의 여유인지 캠페인
가장자리인지 구분되지 않는다. 이 모듈은 그 경계를 없앤다: 팔레트가 끊기지 않고
들어오는 60분을 흘리고, 자원마다 **일한 시간·막힌 시간·굶은 시간**을 따로 센다.

병목은 계산이 아니라 **비교**다 — 장비별 장당 점유를 한 줄에 세우면 가장 긴 것이
병목이고, 나머지의 여유가 그 차이다. 다만 두 가지를 맞춰 놓아야 비교가 성립한다.

* **환산.** 어떤 장비는 모든 장을 보지 않는다. 유리제거기는 정상 유리(R-A)만
  받고(88.3 %), JBR·AFR 은 전손(3.3 %)을 안 본다. 그래서 장비 사이클을 그대로
  견주면 안 되고 **라인 한 장당**으로 환산해야 한다 — `Equipment.share` 가 그 몫이다.
* **직렬·병렬.** 라인을 붙잡는 것은 직렬 자원뿐이다. 지게차는 대기 리프트가
  받으므로 택트에 안 들고, SG-301·HC-101·DL-101 은 상위 자원(AFR·유리제거기)의
  점유 안에서 돈다. 이것들을 병목 후보에 넣으면 라인이 아니라 부품을 본 것이 된다.

**끊어지지 않는다는 것**은 두 가지를 뜻한다. 직렬 자원의 장당 점유가 모두 택트보다
짧아야 하고(그래야 상류가 막히지 않는다), 병목이 굶지 않아야 한다(그래야 처리량이
병목 능력만큼 나온다). 앞은 `flow_is_unbroken()` 이 장비표에서 바로 답하고, 뒤는
60분 운전 `run()` 의 굶은 시간이 답한다. 계획 정지(칼날 카세트 자동교환)는
`run(swap_at_min=…)` 으로 넣어 **버퍼가 그것을 덮는지**까지 본다.

시간의 출처는 전부 모델이다 — 투입·JBR·AFR 은 `campaign`, 후단은
`line.downstream_rate()`(= 벤더 식에 라인 패널 크기를 넣은 값), 카세트 교환은 벤더
콘솔 상수 `CASS_SWAP_AUTO`. 이 모듈이 새로 정하는 시간은 하나도 없다.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import campaign, handoff, hk60c, line

#: 연속 운전을 보는 창 (분).
WINDOW_MIN = 60.0

#: KC-101 칼날 카세트 **자동** 교환 정지 (s) — 벤더 콘솔 `CASS_SWAP_AUTO`.
#: 사람이 바꾸는 값(`CASS_SWAP_MANUAL` 480 s)이 아니라 매거진 2조가 스스로 바꾸는
#: 시간이다. 교환 **주기**는 칼날 수명에 달렸고 그것은 벤더 확인사항 OI-12 라
#: 아직 값이 없다 — 그래서 주기를 상수로 박지 않고 `run(swap_at_min=…)` 인자로
#: 받아 "몇 분마다여도 견디는가"를 묻는다.
KNIFE_SWAP_S: float = hk60c.const("CASS_SWAP_AUTO")


@dataclass(frozen=True)
class Equipment:
    """장비 하나가 한 장을 붙잡는 시간."""

    tag: str
    name: str
    hold_s: float       # 그 장비가 자기 장 하나를 쥐고 있는 시간
    share: float        # 라인 한 장 중 이 장비를 지나는 몫 (0…1)
    serial: bool        # 라인 흐름을 막는 직렬 자원인가
    source: str         # 어느 모델 값에서 왔는가
    parent: str = ""    # 병렬 자원이면 어느 직렬 자원 안에서 도는가

    @property
    def per_panel_s(self) -> float:
        """라인 한 장당 환산 점유 (s) — 병목 비교는 이 값으로 한다."""
        return round(self.hold_s * self.share, 2)


def _scrap_share() -> float:
    """전손 비율 — JBR·AFR 은 이 몫을 안 본다."""
    counts = campaign.condition_counts()
    return counts["전손"] / sum(counts.values())


def equipment() -> tuple[Equipment, ...]:
    """장비별 장당 점유 — 투입 팔레트에서 유리·셀 반출까지 한 줄로 세운다."""
    r = line.downstream_rate()
    normal = campaign.normal_ratio()
    processed = 1.0 - _scrap_share()
    machine_s = round(3600.0 / r.line_per_h, 2)
    return (
        Equipment("FL-101", "지게차 팔레트 급전",
                  campaign.PALLET_SWAP_S / campaign.PALLET_PANELS, 1.0, False,
                  "campaign.PALLET_SWAP_S / PALLET_PANELS", parent="AFU-101"),
        Equipment("AFU-101", "투입부 — 리프트·비전·반전·로봇·정렬",
                  campaign.INFEED_S, 1.0, True, "campaign.INFEED_S"),
        Equipment("JB-201", "축적 컨베이어 통과",
                  campaign.accumulator_clear_s(), processed, False,
                  "campaign.accumulator_clear_s()", parent="JBR-201"),
        Equipment("JBR-201", "정션박스·케이블 제거",
                  campaign.JBR_S, processed, True, "campaign.JBR_S"),
        Equipment("AFR-101", "프레임 분리 이후 후단 — 연마·검사·버퍼 적재",
                  campaign.AFR_S, processed, True, "campaign.AFR_S"),
        Equipment("SG-301", "반출롤러 위 3헤드 연마",
                  campaign.sg_occupancy_s(), processed, False,
                  "campaign.sg_occupancy_s()", parent="AFR-101"),
        Equipment("HC-101", "IR 밀폐 가열 — 방출 피치",
                  r.release_pitch_s, normal, False,
                  "line.downstream_rate().release_pitch_s", parent="DGM-401"),
        Equipment("DL-101", "탠덤 박리 — 칼날 왕복",
                  r.tandem_cycle_s, normal, False,
                  "line.downstream_rate().tandem_cycle_s", parent="DGM-401"),
        Equipment("DGM-401", f"{hk60c.MODEL} 유리제거 (가동률 {hk60c.AVAILABILITY:g} 포함)",
                  machine_s, normal, True, "3600 / line.downstream_rate().line_per_h"),
    )


def serial_equipment() -> tuple[Equipment, ...]:
    """라인을 붙잡는 직렬 자원만 — 병목은 이 중에서 나온다."""
    return tuple(e for e in equipment() if e.serial)


def takt_s() -> float:
    """투입 주기 (s) — 페이싱이 정한 값. 모든 직렬 자원이 이보다 짧아야 한다."""
    return round(campaign.release_takt_s(), 2)


def bottleneck() -> Equipment:
    """장당 점유가 가장 긴 직렬 자원."""
    return max(serial_equipment(), key=lambda e: e.per_panel_s)


def headroom_s() -> tuple[tuple[str, float], ...]:
    """직렬 자원마다 택트까지 남는 시간 (s) — 음수면 그 자리에서 흐름이 끊긴다."""
    takt = takt_s()
    return tuple((e.tag, round(takt - e.per_panel_s, 2)) for e in serial_equipment())


def flow_is_unbroken() -> bool:
    """직렬 자원이 모두 택트 안에 드는가 — 하나라도 넘으면 상류가 막힌다."""
    return all(gap >= 0 for _, gap in headroom_s())


def bottleneck_utilisation() -> float:
    """병목이 택트 중 실제로 일하는 비율 — 1.0 에 가까울수록 라인이 병목에 붙어 있다."""
    return round(bottleneck().per_panel_s / takt_s(), 4)


@dataclass(frozen=True)
class Slice:
    """자원 하나의 60분 — 일한 시간·막힌 시간·굶은 시간은 창 길이로 합해진다."""

    tag: str
    name: str
    panels: int
    busy_s: float
    blocked_s: float
    starved_s: float

    @property
    def utilisation(self) -> float:
        span = self.busy_s + self.blocked_s + self.starved_s
        return round(self.busy_s / span, 4) if span else 0.0


@dataclass(frozen=True)
class Run:
    """60분 연속 운전 결과."""

    minutes: float
    released: int          # 투입한 장수
    scrapped: int          # 전손 리젝트 (라인에 안 들어간다)
    to_buffer: int         # 버퍼까지 간 장수 (정상 + 유리 깨짐)
    glass_out: int         # 유리제거기가 내보낸 유리 장수
    cell_eva_kg: float     # 같은 장수에서 나온 셀·EVA 질량
    buffer_peak: int       # R-A 재고 최고
    buffer_end: int        # 60분 끝 R-A 재고
    slices: tuple[Slice, ...]
    stops: tuple[tuple[float, float, str], ...]   # (시각 s, 길이 s, 사유)
    breaks: tuple[str, ...]                        # 흐름이 끊긴 자리
    #: 자원이 무엇을 언제 붙잡았나 — (자원, 시작 s, 끝 s, 장 번호, 무엇)
    spans: tuple[tuple[str, float, float, int, str], ...] = ()
    #: R-A 재고 궤적 — (시각 s, 슬롯)
    buffer_trace: tuple[tuple[float, int], ...] = ()

    @property
    def unbroken(self) -> bool:
        return not self.breaks

    @property
    def glass_per_h(self) -> float:
        return round(self.glass_out / (self.minutes / 60.0), 1)


def _marks() -> tuple[str, ...]:
    """번들 패턴을 이어 붙인 무한 투입열의 한 주기 (60장)."""
    return tuple(mark for _, _, pattern in campaign.BUNDLE_PATTERNS for mark in pattern)


def run(minutes: float = WINDOW_MIN, swap_at_min: float | None = None,
        warm: bool = True) -> Run:
    """연속 투입 `minutes` 분을 흘린다.

    투입 규칙은 `campaign.panels()` 와 같다 — 앞 장이 JBR 스토퍼를 물고 방출 보류가
    지나면 다음 장을 내려놓는다. 다른 것은 팔레트가 안 끊긴다는 것과, 유리제거기가
    **버퍼에서** 당겨 간다는 것이다. 그래서 상류는 택트로 돌고 후단은 제 사이클로
    도는, 실제 운전과 같은 두 박자가 된다.

    `warm` 이면 R-A 재고를 정상 운전 설정점(`handoff.buffer_stock_target_slots()`)
    에서 시작한다 — 60분은 이미 돌고 있는 라인의 **한 토막**이지 기동이 아니다.
    빈 버퍼로 시작하면 후단이 첫 장을 기다리며 굶고, 그 굶음이 정상 운전의 여유로
    잘못 읽힌다. `swap_at_min` 을 주면 그 시각에 칼날 카세트 자동교환 정지를 넣는다.
    """
    window = minutes * 60.0
    marks = _marks()
    r = line.downstream_rate()
    machine_cycle = 3600.0 / r.line_per_h

    infeed_free = jbr_free = afr_free = 0.0
    infeed_busy = jbr_busy = afr_busy = 0.0
    infeed_blocked = jbr_blocked = 0.0
    infeed_n = jbr_n = afr_n = 0
    release_gate = 0.0
    released = scrapped = to_buffer = 0

    arrivals: list[float] = []          # 정상 유리가 버퍼에 놓이는 시각
    spans: list[tuple[str, float, float, int, str]] = []
    i = 0
    while True:
        mark = marks[i % len(marks)]
        i += 1
        start = max(infeed_free, release_gate)
        if start >= window:
            break
        released += 1
        if mark == "X":
            end = start + campaign.INFEED_REJECT_S
            infeed_free = end
            infeed_busy += min(end, window) - start
            infeed_n += 1
            scrapped += 1
            spans.append(("AFU-101", round(start, 1), round(end, 1), released, "전손 배출"))
            continue
        end = start + campaign.INFEED_S
        infeed_busy += min(end, window) - start
        infeed_n += 1
        spans.append(("AFU-101", round(start, 1), round(end, 1), released, "일"))
        jbr_start = max(end, jbr_free)
        infeed_blocked += max(0.0, min(jbr_start, window) - min(end, window))
        infeed_free = jbr_start          # 자리를 비우는 것은 다음 자원이 받을 때다
        jbr_end = jbr_start + campaign.JBR_S
        jbr_free = jbr_end
        jbr_busy += max(0.0, min(jbr_end, window) - min(jbr_start, window))
        jbr_n += 1
        if jbr_start > end:
            spans.append(("AFU-101", round(end, 1), round(jbr_start, 1), released, "막힘"))
        spans.append(("JBR-201", round(jbr_start, 1), round(jbr_end, 1), released, "일"))
        release_gate = jbr_start + campaign.JBR_STOPPER_OFFSET_S + campaign.RELEASE_HOLD_S
        afr_start = max(jbr_end, afr_free)
        jbr_blocked += max(0.0, min(afr_start, window) - min(jbr_end, window))
        afr_end = afr_start + campaign.AFR_S
        afr_free = afr_end
        afr_busy += max(0.0, min(afr_end, window) - min(afr_start, window))
        afr_n += 1
        if afr_start > jbr_end:
            spans.append(("JBR-201", round(jbr_end, 1), round(afr_start, 1), released, "막힘"))
        spans.append(("AFR-101", round(afr_start, 1), round(afr_end, 1), released, "일"))
        if afr_end <= window:
            to_buffer += 1
            if mark.isupper():           # 정상만 R-A → 유리제거기
                arrivals.append(afr_end)

    # 유리제거기 — 버퍼에서 당겨 간다. 재고가 없으면 굶고, 있으면 제 사이클로 돈다.
    # 계획 정지는 **돌던 장을 끝낸 뒤** 시작한다. 칼날 카세트는 박리 중에 못 바꾼다.
    stops: list[tuple[float, float, str]] = []
    pending = None if swap_at_min is None else swap_at_min * 60.0
    machine_busy = machine_stop = machine_starved = 0.0
    now = 0.0
    glass_out = 0
    opening = handoff.buffer_stock_target_slots() if warm else 0
    stock = opening
    peak = opening
    served = 0
    trace: list[tuple[float, int]] = [(0.0, opening)]
    while now < window:
        if pending is not None and now >= pending:
            span = min(KNIFE_SWAP_S, window - now)
            stops.append((round(now, 1), KNIFE_SWAP_S, "KC-101 칼날 카세트 자동교환"))
            machine_stop += span
            spans.append(("DGM-401", round(now, 1), round(now + span, 1), 0, "정지"))
            now += span
            pending = None
            continue
        stock = opening + sum(1 for t in arrivals if t <= now) - served
        peak = max(peak, stock)
        trace.append((round(now, 1), stock))
        if stock <= 0:
            nxt = next((t for t in arrivals if t > now), window)
            step = min(nxt, window) - now
            machine_starved += step
            spans.append(("DGM-401", round(now, 1), round(now + step, 1), 0, "굶음"))
            now += step
            continue
        step = min(machine_cycle, window - now)
        machine_busy += step
        spans.append(("DGM-401", round(now, 1), round(now + step, 1), served + 1, "일"))
        now += step
        if step >= machine_cycle - 1e-9:
            served += 1
            glass_out += 1
    stock = opening + sum(1 for t in arrivals if t <= window) - served
    peak = max(peak, stock)
    trace.append((round(window, 1), stock))

    slices = (
        Slice("AFU-101", "투입부", infeed_n, round(infeed_busy, 1), round(infeed_blocked, 1),
              round(window - infeed_busy - infeed_blocked, 1)),
        Slice("JBR-201", "정션박스 제거", jbr_n, round(jbr_busy, 1), round(jbr_blocked, 1),
              round(window - jbr_busy - jbr_blocked, 1)),
        Slice("AFR-101", "프레임 분리 후단", afr_n, round(afr_busy, 1), 0.0,
              round(window - afr_busy, 1)),
        Slice("DGM-401", f"{hk60c.MODEL} 유리제거", glass_out, round(machine_busy, 1),
              round(machine_stop, 1), round(machine_starved, 1)),
    )
    breaks = [f"{tag} 장당 {-gap:.2f} s 초과" for tag, gap in headroom_s() if gap < 0]
    if stock <= 0 < len(arrivals):
        breaks.append("R-A 재고 고갈 — 후단이 상류를 기다린다")
    return Run(minutes, released, scrapped, to_buffer, glass_out,
               round(glass_out * hk60c.CELL_EVA_KG, 1), peak, stock, slices,
               tuple(stops), tuple(breaks), tuple(spans), tuple(trace))


def swap_interval_the_machine_absorbs_min() -> float:
    """유리제거기가 **버퍼를 쓰지 않고** 스스로 삼킬 수 있는 카세트 교환 주기 (분).

    페이싱 때문에 기계는 장당 여유를 갖는다(택트 환산 − 기계 사이클). 교환 정지가
    그 여유 안에 들어가는 주기라면 버퍼 재고가 줄지 않는다 — 그보다 잦으면 버퍼가
    받아 내야 하고, 그때는 `buffer_covers_swaps_h()` 가 몇 시간까지 견디는지 말한다.
    """
    per_sheet_slack = round(3600.0 / handoff.sheet_glass_per_h()
                            - 3600.0 / line.downstream_rate().line_per_h, 4)
    if per_sheet_slack <= 0:
        return 0.0
    sheets = KNIFE_SWAP_S / per_sheet_slack
    return round(sheets * 3600.0 / handoff.sheet_glass_per_h() / 60.0, 1)


def steady_state_machine_idle_s_per_h() -> float:
    """정상 운전에서 유리제거기가 노는 시간 (s/h) — **이것이 인계 안전여유다**.

    라인은 후단 능력(60.5 장/h)이 아니라 페이싱된 유입(58.3 장/h)으로 돈다. 차이
    2.2 장/h 만큼 기계가 논다. 60분 창을 재고 38장에서 시작하면 그 노는 시간이 재고
    감소(−2장)로 나타나고 굶음으로는 안 잡힌다 — 둘은 같은 여유의 다른 얼굴이다.
    """
    capacity = line.downstream_rate().line_per_h
    fed = handoff.sheet_glass_per_h()
    return round(3600.0 * (1.0 - fed / capacity), 1)


def buffer_covers_swaps_h(swap_interval_min: float) -> float:
    """그보다 잦은 주기로 교환이 들어올 때 R-A 재고가 버티는 시간 (h).

    교환 한 번이 여유보다 길면 그 초과분만큼 재고가 준다. 재고가 다 빠지면 라인이
    후단을 기다리게 되고, 그때가 흐름이 끊기는 순간이다.
    """
    absorbs = swap_interval_the_machine_absorbs_min()
    if swap_interval_min >= absorbs:
        return float("inf")
    per_swap_debt = KNIFE_SWAP_S * (1.0 - swap_interval_min / absorbs)
    swaps_per_h = 60.0 / swap_interval_min
    debt_per_h = per_swap_debt * swaps_per_h
    stock_s = handoff.BUFFER_RA_SLOTS * 3600.0 / handoff.sheet_glass_per_h()
    return round(stock_s / debt_per_h, 1) if debt_per_h > 0 else float("inf")


def summary() -> dict[str, object]:
    b = bottleneck()
    result = run()
    return {
        "taktS": takt_s(),
        "bottleneck": b.tag,
        "bottleneckName": b.name,
        "bottleneckS": b.per_panel_s,
        "bottleneckUse": bottleneck_utilisation(),
        "unbroken": flow_is_unbroken() and result.unbroken,
        "released": result.released,
        "glassOut": result.glass_out,
        "glassPerH": result.glass_per_h,
        "cellEvaKg": result.cell_eva_kg,
        "bufferPeak": result.buffer_peak,
        "swapAbsorbMin": swap_interval_the_machine_absorbs_min(),
        "machineIdleSPerH": steady_state_machine_idle_s_per_h(),
    }
