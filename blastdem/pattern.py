"""발파 패턴(천공 배치) 설계 — 저항선, 공간격, 지발시차, 지발당 장약량.

국내 발파진동 규제는 '지발당 최대장약량 W'를 기준으로 하므로, 이 모듈이
계산하는 max_charge_per_delay 가 경험식/규제 검토의 핵심 입력이 된다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .explosives import Explosive


@dataclass
class BlastHole:
    """개별 발파공.

    좌표계: x = 저항선 방향(자유면에서 멀어지는 쪽 +), y = 공간격 방향,
            z = 연직 상방(+), 벤치 상단면이 z = 0.
    """

    x: float
    y: float
    z_collar: float          # 공구(collar) 표고 [m]
    depth: float             # 천공장 [m]
    hole_dia: float          # 천공경 [m]
    charge_dia: float        # 장약경 [m]
    charge_weight: float     # 장약량 [kg]
    stemming: float          # 전색장 [m]
    delay: float             # 기폭시차 [s]
    row: int = 0
    col: int = 0
    label: str = ""

    @property
    def z_bottom(self) -> float:
        return self.z_collar - self.depth

    @property
    def charge_top(self) -> float:
        """장약 상단 표고 [m] = 공구 - 전색장."""
        return self.z_collar - self.stemming

    @property
    def charge_length(self) -> float:
        return max(0.0, self.charge_top - self.z_bottom)

    @property
    def axis_xy(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class BlastPattern:
    """벤치발파 패턴 설계.

    Parameters
    ----------
    burden        : 저항선 B [m]  (열 간 거리 = 자유면까지 거리)
    spacing       : 공간격 S [m]  (동일 열 내 공 간 거리)
    bench_height  : 벤치고 H [m]
    hole_dia      : 천공경 [m]
    charge_dia    : 장약경 [m] (None 이면 천공경과 동일 = 완전결합)
    n_rows        : 열 수
    n_cols        : 열당 공 수
    subdrill      : 하부천공장 [m] (None 이면 0.3*B)
    stemming      : 전색장 [m] (None 이면 1.0*B)
    delay_hole    : 동일 열 내 공간 시차 [s]
    delay_row     : 열 간 시차 [s]
    origin        : 첫 공의 (x, y) 위치 [m]
    free_face_x   : 자유면의 x 좌표 [m] (진동 전파 방향 판단용)
    """

    explosive: Explosive
    burden: float = 3.0
    spacing: float = 3.5
    bench_height: float = 10.0
    hole_dia: float = 0.076
    charge_dia: float | None = None
    n_rows: int = 2
    n_cols: int = 5
    subdrill: float | None = None
    stemming: float | None = None
    delay_hole: float = 0.025
    delay_row: float = 0.065
    origin: tuple[float, float] = (0.0, 0.0)
    free_face_x: float = -1.5
    holes: list[BlastHole] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if self.charge_dia is None:
            self.charge_dia = self.hole_dia
        if self.subdrill is None:
            self.subdrill = 0.30 * self.burden
        if self.stemming is None:
            self.stemming = 1.00 * self.burden
        self.holes = self._build()

    # ---- 패턴 생성 -------------------------------------------------------
    def _build(self) -> list[BlastHole]:
        holes: list[BlastHole] = []
        depth = self.bench_height + self.subdrill
        x0, y0 = self.origin
        # y 방향으로 패턴 중심이 0 이 되도록 정렬
        y_span = (self.n_cols - 1) * self.spacing
        for r in range(self.n_rows):
            for c in range(self.n_cols):
                x = x0 + r * self.burden
                y = y0 + c * self.spacing - y_span / 2.0
                # 열 내부는 중앙에서 바깥으로 번지는 V 패턴 대신 단순 순차 기폭
                t = r * self.delay_row + c * self.delay_hole
                h = BlastHole(
                    x=x, y=y, z_collar=0.0, depth=depth,
                    hole_dia=self.hole_dia, charge_dia=self.charge_dia,
                    charge_weight=0.0,
                    stemming=self.stemming, delay=t, row=r, col=c,
                    label=f"R{r + 1}C{c + 1}",
                )
                h.charge_weight = self.explosive.charge_weight(h.charge_length, self.charge_dia)
                holes.append(h)
        return holes

    # ---- 설계 지표 -------------------------------------------------------
    @property
    def n_holes(self) -> int:
        return len(self.holes)

    @property
    def total_charge(self) -> float:
        """총 장약량 [kg]."""
        return sum(h.charge_weight for h in self.holes)

    @property
    def charge_per_hole(self) -> float:
        return self.holes[0].charge_weight if self.holes else 0.0

    @property
    def rock_volume(self) -> float:
        """발파 대상 암반 체적 [m^3] = B * S * H * 공수."""
        return self.burden * self.spacing * self.bench_height * self.n_holes

    @property
    def powder_factor(self) -> float:
        """비장약량 [kg/m^3]."""
        return self.total_charge / self.rock_volume if self.rock_volume else 0.0

    @property
    def specific_drilling(self) -> float:
        """천공장비 [m/m^3]."""
        return self.n_holes * (self.bench_height + self.subdrill) / self.rock_volume

    def charge_per_delay(self, window: float = 0.008) -> dict[float, float]:
        """시차 window[s] 이내 동시 기폭으로 간주해 묶은 지발당 장약량.

        국내 실무는 8ms 이내 기폭을 동시로 본다 (미국 OSM 기준과 동일).
        """
        groups: dict[float, float] = {}
        for h in sorted(self.holes, key=lambda z: z.delay):
            key = next((k for k in groups if abs(k - h.delay) <= window), None)
            if key is None:
                groups[h.delay] = h.charge_weight
            else:
                groups[key] += h.charge_weight
        return groups

    @property
    def max_charge_per_delay(self) -> float:
        """지발당 최대장약량 W [kg] — 발파진동 경험식의 W."""
        g = self.charge_per_delay()
        return max(g.values()) if g else 0.0

    @property
    def total_duration(self) -> float:
        return max((h.delay for h in self.holes), default=0.0)

    def positions(self) -> np.ndarray:
        return np.array([[h.x, h.y, h.z_collar] for h in self.holes])

    # ---- 설계 검토 -------------------------------------------------------
    def design_checks(self) -> list[tuple[str, str, bool]]:
        """(항목, 결과, 적합여부) 목록. 벤치발파 통상 설계기준과 비교."""
        out: list[tuple[str, str, bool]] = []
        b, s, h = self.burden, self.spacing, self.bench_height
        d_mm = self.hole_dia * 1000.0

        ratio_bd = b / self.hole_dia
        out.append(("저항선/천공경 B/D", f"{ratio_bd:.0f}  (권장 25~40)", 25 <= ratio_bd <= 40))
        out.append(("공간격/저항선 S/B", f"{s / b:.2f}  (권장 1.15~1.50)", 1.10 <= s / b <= 1.55))
        out.append(("벤치고/저항선 H/B", f"{h / b:.2f}  (권장 ≥ 2.0)", h / b >= 2.0))
        out.append(("전색장/저항선 T/B", f"{self.stemming / b:.2f}  (권장 0.7~1.3)",
                    0.7 <= self.stemming / b <= 1.3))
        out.append(("하부천공/저항선 J/B", f"{self.subdrill / b:.2f}  (권장 0.2~0.4)",
                    0.2 <= self.subdrill / b <= 0.4))
        pf = self.powder_factor
        out.append(("비장약량", f"{pf:.2f} kg/m^3  (통상 0.3~0.8)", 0.25 <= pf <= 0.9))
        out.append(("천공경", f"{d_mm:.0f} mm", True))
        return out

    def summary(self) -> str:
        lines = [
            f"[발파패턴] {self.n_rows}열 x {self.n_cols}공 = {self.n_holes}공",
            f"  저항선 B = {self.burden:.2f} m,  공간격 S = {self.spacing:.2f} m,  "
            f"벤치고 H = {self.bench_height:.1f} m",
            f"  천공경 = {self.hole_dia * 1000:.0f} mm,  장약경 = {self.charge_dia * 1000:.0f} mm,  "
            f"천공장 = {self.bench_height + self.subdrill:.2f} m",
            f"  전색장 = {self.stemming:.2f} m,  하부천공 = {self.subdrill:.2f} m,  "
            f"장약장 = {self.holes[0].charge_length:.2f} m",
            f"  공당 장약량 = {self.charge_per_hole:.1f} kg,  총 장약량 = {self.total_charge:.1f} kg",
            f"  ** 지발당 최대장약량 W = {self.max_charge_per_delay:.1f} kg **",
            f"  비장약량 = {self.powder_factor:.3f} kg/m^3,  총 기폭시간 = {self.total_duration * 1000:.0f} ms",
            f"  시차: 공간 {self.delay_hole * 1000:.0f} ms / 열간 {self.delay_row * 1000:.0f} ms",
            "  --- 설계 검토 ---",
        ]
        for item, val, ok in self.design_checks():
            lines.append(f"   {'OK ' if ok else '!! '} {item:<20s} {val}")
        return "\n".join(lines)
