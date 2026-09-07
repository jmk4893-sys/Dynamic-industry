"""라인 상한 — 이 플랜트가 받는 패널의 최대 치수. **플랜트의 결정**이다.

REV.54(B안)는 벤더 상한 2,400×1,200 에 맞춰 라인을 통일했다. 그 뒤 벤더가 포락선을
2,500×1,400 으로 올렸으므로(DG-HK60 콘솔 개정 · 48등 120 kW · 계약 58 장/h) '벤더
상한'이라는 근거는 사라졌다 — 그래도 2,400×1,200 을 두는 것은 **발주처 선택**이다
(C안). 벤더 포락선을 그대로 쓰면 A안이다: ``LINE_MAX_MM = hk60c.PANEL_MAX_MM``.

패널 크기에서 파생하는 것(캠페인 패널 · 등록 관문 · 축적런 · JBR 조 물림 · 버퍼 슬롯 ·
브리지 개구 · 후단 사이클)은 전부 여기서 읽는다. 벤더 기계의 **능력**(받을 수 있는
상한 · 데크 · 램프)은 `hk60c` 가 정본이고 여기서 다시 정하지 않는다.
"""
from __future__ import annotations

from . import hk60c

#: 라인 상한 (길이, 폭) mm.
LINE_MAX_MM: tuple[int, int] = (2400, 1200)


def basis() -> str:
    """상한의 근거 — 벤더 상한과 같으면 '벤더 상한', 더 작으면 '발주처 선택'."""
    return "벤더 상한" if LINE_MAX_MM == hk60c.PANEL_MAX_MM else "발주처 선택"


def fits_the_vendor() -> bool:
    """라인 상한이 벤더 투입 범위 안인가 — 아니면 브리지가 넘긴 유리를 후단이 못 받는다."""
    lo, hi = hk60c.PANEL_MIN_MM, hk60c.PANEL_MAX_MM
    return all(lo[i] <= LINE_MAX_MM[i] <= hi[i] for i in range(2))


def downstream_rate():
    """라인 패널 크기에서의 후단 순생산 — 벤더 사이클 식은 패널 길이에 비례한다."""
    return hk60c.rate(LINE_MAX_MM[0], LINE_MAX_MM[1])
