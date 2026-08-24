"""발파진동 경험식(환산거리식)과 국내 규제기준 대비 검토.

환산거리식
    V = K * (D / W^b)^(-n)          V[cm/s], D[m], W[kg]
    b = 1/2 : 자승근 환산거리 (SRSD) — 벤치/노천 발파 표준
    b = 1/3 : 삼승근 환산거리 (CRSD) — 집중장약

DEM 해석은 이 경험식을 대체하는 것이 아니라, 현장 고유의 K, n 을
'수치실험'으로 추정하고 패턴 변경 효과를 사전 평가하는 데 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ScaledDistanceLaw:
    """환산거리 회귀식."""

    K: float
    n: float
    b: float = 0.5
    name: str = ""

    def scaled_distance(self, distance, charge) -> np.ndarray:
        return np.asarray(distance, float) / np.asarray(charge, float) ** self.b

    def ppv(self, distance, charge) -> np.ndarray:
        """PPV [mm/s]."""
        sd = np.maximum(self.scaled_distance(distance, charge), 1e-6)
        return 10.0 * self.K * sd ** (-self.n)   # cm/s -> mm/s

    def allowable_charge(self, distance: float, ppv_limit_mm: float) -> float:
        """거리 D 에서 허용 PPV 를 만족하는 지발당 최대장약량 [kg]."""
        sd_req = (10.0 * self.K / ppv_limit_mm) ** (1.0 / self.n)
        return (distance / sd_req) ** (1.0 / self.b)

    def safe_distance(self, charge: float, ppv_limit_mm: float) -> float:
        """장약량 W 에서 허용 PPV 를 만족하는 최소 이격거리 [m]."""
        sd_req = (10.0 * self.K / ppv_limit_mm) ** (1.0 / self.n)
        return sd_req * charge ** self.b

    def __str__(self) -> str:
        root = "자승근" if abs(self.b - 0.5) < 1e-9 else ("삼승근" if abs(self.b - 1 / 3) < 1e-3 else f"W^{self.b}")
        return f"{self.name or '회귀식'}: V = {self.K:.0f}(D/W^{self.b:g})^-{self.n:.2f} [cm/s], {root}"


# 대표 회귀식 — 모두 설계/검토용 참고값이며 현장 시험발파로 재추정해야 한다.
SD_LAWS: dict[str, ScaledDistanceLaw] = {
    "kr_mean": ScaledDistanceLaw(200, 1.60, 0.5, "국내 설계 평균 (K=200)"),
    "kr_upper": ScaledDistanceLaw(400, 1.60, 0.5, "국내 설계 상한 (K=400, 안전측)"),
    "usbm": ScaledDistanceLaw(116, 1.60, 0.5, "USBM RI-8507 평균 회귀"),
    "tunnel": ScaledDistanceLaw(250, 1.55, 0.5, "터널 발파 참고"),
}


# 국내 발파진동 허용기준 (국토교통부/한국도로공사 계열, PPV 기준)
REGULATION: list[tuple[str, float]] = [
    ("가축 (조류·양계)", 1.0),
    ("문화재·정밀기기", 2.0),
    ("주택·아파트", 5.0),
    ("상가 (미장·마감 있음)", 10.0),
    ("철근콘크리트 빌딩·공장", 40.0),
]


def evaluate(ppv_mm: float) -> str:
    """PPV[mm/s] 에 대해 어느 등급까지 만족하는지 판정."""
    ok = [name for name, lim in REGULATION if ppv_mm <= lim]
    if not ok:
        return "모든 기준 초과 — 장약량 저감 필수"
    return f"만족: {', '.join(ok)}"


def regulation_table(ppv_mm: float) -> str:
    lines = [f"{'보안물건':<22s} {'허용[mm/s]':>10s} {'해석 PPV':>10s} {'판정':>8s}"]
    lines.append("-" * 56)
    for name, lim in REGULATION:
        mark = "적합" if ppv_mm <= lim else "초과"
        lines.append(f"{name:<22s} {lim:10.1f} {ppv_mm:10.2f} {mark:>8s}")
    return "\n".join(lines)


def fit_law(distances, ppv_mm, charge: float, b: float = 0.5) -> ScaledDistanceLaw:
    """DEM 해석 결과로부터 현장 K, n 회귀 추정 (log-log 최소자승)."""
    d = np.asarray(distances, float)
    v = np.asarray(ppv_mm, float)
    m = (d > 0) & (v > 0)
    if m.sum() < 2:
        return ScaledDistanceLaw(K=float("nan"), n=float("nan"), b=b,
                                 name="회귀 불가 (유효 계측점 2개 미만)")
    sd = d[m] / charge ** b
    slope, intercept = np.polyfit(np.log10(sd), np.log10(v[m] / 10.0), 1)
    return ScaledDistanceLaw(K=10.0 ** intercept, n=-slope, b=b, name="DEM 해석 회귀")


def calibrate_efficiency(
    distances, ppv_mm, charge: float, target: ScaledDistanceLaw,
) -> float:
    """해석 PPV 를 목표 경험식에 맞추기 위한 폭원 효율계수 eta 보정배수.

    PPV 는 폭원 세기에 선형 비례하므로 비율의 기하평균을 그대로 쓴다.
    """
    d = np.asarray(distances, float)
    v = np.asarray(ppv_mm, float)
    m = (d > 0) & (v > 0)
    if not m.any():
        return 1.0
    ratio = target.ppv(d[m], charge) / v[m]
    return float(np.exp(np.mean(np.log(ratio))))
