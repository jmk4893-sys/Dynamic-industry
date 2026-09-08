#!/usr/bin/env python3
"""콘솔 thermalModel 의 파이썬 거울 — 해석 도구가 쓰는 택트·체류·처리량.

에어록·열수지·IR 뱅크·열해석·제작 지침이 저마다 `TAKT = 53.6`, `DWELL =
222.6`, `RATE_THERMAL = 80.9` 를 손으로 들고 있었다. 패널이 2,400 × 1,200
에서 2,500 × 1,400 으로 커지던 날 그 숫자들은 전부 틀린 채로 남았을
것이다 — 콘솔은 식으로 계산하고 도구는 값을 외웠으니까.

여기서 콘솔의 식을 그대로 다시 쓴다. 입력은 콘솔의 MODEL · MODEL_DEFAULT
객체와 뿌리 상수에서 읽고, 결과 이름은 콘솔 thermalModel 의 반환 키를 그대로
쓴다(q · dwell · pitch · knifeLineCycle …). 두 구현이 갈라지면 시험이 잡는다
— tests/test_cycle.py 가 node 로 콘솔 함수 자체를 돌려 대조한다.

    >>> m = model()
    >>> m["knifeLineCycle"]          # s 라인 사이클 (택트)
    >>> m["dwell"]                   # s 5장 소킹 체류
    >>> net()                        # 장/h 순생산 = 명목 × 가동률
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from console_consts import const as c, obj  # noqa: E402

MODEL = obj("MODEL")
DEFAULT = obj("MODEL_DEFAULT")
RANGE = obj("MODEL_RANGE")


def model(v: dict | None = None, **over) -> dict:
    """콘솔 thermalModel(v) — 입력 한 벌에서 열수지·탠덤·나이프 사이클을 낸다."""
    v = {**DEFAULT, **(v or {}), **over}
    m = MODEL
    q = v["panelLength"] * v["panelWidth"] / 1e6 * m["arealCp"] * m["dT"]     # kJ/장
    rated = m["lamps"] * v["lampPower"]
    eta = v["heatEfficiency"] / 100
    useful = rated * eta
    dwell = max(m["decks"] * q / useful, m["fdmDwell"])
    pitch = dwell / m["decks"]
    thermal_rate = 3600 / pitch
    handling = m["rapidDistance"] / v["rapidSpeed"] + v["handlingTime"]
    lead = m["knifePitch"] / v["knifeSpeed"]
    tandem = lead + v["panelLength"] / v["knifeSpeed"] + handling
    line_cycle = max(pitch, tandem)
    ret_dist = m["knifePitch"] + v["panelLength"]
    ret_time = ret_dist / v["knifeReturnSpeed"]
    peel = v["panelLength"] / v["knifeSpeed"]
    knife = lead + peel + max(handling, ret_time)
    target_cycle = 3600 / (m["netTarget"] / m["availability"])
    window = target_cycle - lead - peel
    floor = ret_dist / window if window > 0 else float("inf")
    energy = q / (eta * 3600)                                                  # kWh/장
    kl_cycle = max(pitch, knife)
    return dict(
        q=q, rated=rated, eta=eta, useful=useful, dwell=dwell, pitch=pitch,
        thermalRate=thermal_rate, handling=handling, leadTime=lead, peelTime=peel,
        tandemCycle=tandem, tandemRate=3600 / tandem,
        lineCycle=line_cycle, lineRate=3600 / line_cycle,
        energyPerPanel=energy, returnDistance=ret_dist, returnTime=ret_time,
        knifeCycle=knife, knifeRate=3600 / knife,
        targetCycle=target_cycle, returnSpeedFloor=floor,
        knifeLineCycle=kl_cycle, knifeLineRate=3600 / kl_cycle,
        averagePower=energy * 3600 / line_cycle,
        bottleneck=(f"{m['decks']}단 IR 열공정" if thermal_rate < 3600 / tandem
                    else "고정 탠덤·캐리어 이송"),
    )


def net(v: dict | None = None, **over) -> float:
    """순생산 장/h — 이동 나이프 라인 사이클 × 가동률."""
    return model(v, **over)["knifeLineRate"] * MODEL["availability"]


# ── 도구들이 쓰는 이름 ────────────────────────────────────────────────────
_M = model()
TAKT = _M["knifeLineCycle"]              # s 라인 사이클 — 에어록·IR 뱅크·열해석
DWELL = _M["dwell"]                      # s 5장 소킹 체류
PITCH = _M["pitch"]                      # s 방출 피치
RATE_THERMAL = _M["thermalRate"]         # 장/h 열공정 한계
RATE_NOMINAL = _M["knifeLineRate"]       # 장/h 명목
RATE_NET = net()                         # 장/h 순생산 (가동률 90 %)
NET_TARGET = int(c("NET_TARGET"))        # 장/h 계약
AVAILABILITY = MODEL["availability"]
Q_PANEL_KJ = _M["q"]                     # kJ/장
USEFUL_KW = _M["useful"]                 # kW 유효 IR 출력
AVERAGE_KW = _M["averagePower"]          # kW 평균 소비


def mass_rate(rate: float = RATE_NET) -> float:
    """kg/h — 기준 패널 질량 × 장/h. 발주자 물질수지의 단위."""
    return rate * c("PANEL_MASS")


def report() -> str:
    m = _M
    L = [f"── 사이클 · 기준 패널 {c('PANEL_L')*1000:.0f} × {c('PANEL_W')*1000:.0f} · "
         f"{c('PANEL_MASS'):.1f} kg ──",
         f"  q {m['q']/1000:.3f} MJ/장 · 유효 {m['useful']:.1f} kW · 체류 {m['dwell']:.1f} s · "
         f"피치 {m['pitch']:.2f} s · 열공정 한계 {m['thermalRate']:.1f} 장/h",
         f"  나이프 {m['leadTime']:.2f} + {m['peelTime']:.2f} + max({m['handling']:.1f}, "
         f"{m['returnTime']:.2f}) = {m['knifeCycle']:.2f} s → 명목 {m['knifeLineRate']:.1f} 장/h · "
         f"순생산 {RATE_NET:.1f} 장/h (계약 {NET_TARGET}) · {mass_rate():,.0f} kg/h",
         f"  평균 소비 {m['averagePower']:.1f} kW / 정격 {m['rated']:.0f} kW = "
         f"수용률 {m['averagePower']/m['rated']:.2f}"]
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
