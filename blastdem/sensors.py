"""계측점(지오폰) 배치 및 진동 신호 처리.

발파진동 계측 실무와 동일하게 3성분(방사/접선/연직) 속도 이력에서
PPV(최대입자속도), PVS(벡터합 최대), 탁월주파수, 변위/가속도를 산출한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def line_array(
    start: tuple[float, float], direction: tuple[float, float],
    distances: list[float] | np.ndarray, z: float = 0.0,
) -> tuple[np.ndarray, list[str]]:
    """기준점에서 특정 방향으로 일정 거리마다 배치되는 측선."""
    d = np.array(direction, dtype=float)
    d /= np.linalg.norm(d)
    pts = np.array([[start[0] + d[0] * r, start[1] + d[1] * r, z] for r in distances])
    names = [f"D{r:.0f}m" for r in distances]
    return pts, names


def radial_array(
    center: tuple[float, float], radius: float, n_azimuth: int = 8, z: float = 0.0,
) -> tuple[np.ndarray, list[str]]:
    """동일 거리에서 방위각을 달리한 배치 — 지발 시차의 방향성 확인용."""
    ang = np.linspace(0, 2 * np.pi, n_azimuth, endpoint=False)
    pts = np.column_stack([
        center[0] + radius * np.cos(ang),
        center[1] + radius * np.sin(ang),
        np.full(n_azimuth, z),
    ])
    names = [f"A{np.degrees(a):.0f}deg" for a in ang]
    return pts, names


@dataclass
class SensorRecord:
    """단일 계측점 해석 결과."""

    name: str
    position: np.ndarray
    distance: float          # 폭원 중심까지 수평거리 [m]
    time: np.ndarray         # [s]
    velocity: np.ndarray     # (nt, 3) [m/s]

    # ---- 최대치 ----------------------------------------------------------
    @property
    def ppv_components(self) -> np.ndarray:
        """성분별 최대속도 [mm/s] (x, y, z)."""
        return np.abs(self.velocity).max(axis=0) * 1000.0

    @property
    def ppv(self) -> float:
        """PPV — 3성분 중 최대 [mm/s] (국내 규제 기준값)."""
        return float(self.ppv_components.max())

    @property
    def pvs(self) -> float:
        """PVS — 벡터합 최대 [mm/s]."""
        return float(np.linalg.norm(self.velocity, axis=1).max() * 1000.0)

    # ---- 주파수 ----------------------------------------------------------
    @property
    def dominant_component(self) -> int:
        """PPV 가 가장 큰 성분 인덱스."""
        return int(np.argmax(self.ppv_components))

    def spectrum(self, comp: int | None = None) -> tuple[np.ndarray, np.ndarray]:
        """진폭 스펙트럼 (freq[Hz], amp).

        벡터 크기 |v| 는 항상 양수인 정류(rectified) 신호라 FFT 하면 직류/저주파가
        과대평가된다. 계측 실무와 동일하게 '성분 신호'로 스펙트럼을 구한다.
        """
        sig = self.velocity[:, self.dominant_component if comp is None else comp]
        if sig.size < 4:
            return np.zeros(0), np.zeros(0)
        sig = sig - sig.mean()
        dt = float(self.time[1] - self.time[0])
        amp = np.abs(np.fft.rfft(sig * np.hanning(sig.size)))
        freq = np.fft.rfftfreq(sig.size, dt)
        return freq, amp

    @property
    def dominant_frequency(self) -> float:
        """탁월주파수 [Hz]."""
        f, a = self.spectrum()
        m = (f > 2.0) & (f < 500.0)
        if not m.any() or a[m].max() <= 0:
            return 0.0
        return float(f[m][np.argmax(a[m])])

    @property
    def peak_displacement(self) -> float:
        """최대변위 [mm] — 속도 적분."""
        if self.time.size < 2:
            return 0.0
        dt = float(self.time[1] - self.time[0])
        u = np.cumsum(self.velocity, axis=0) * dt
        u -= np.linspace(0, 1, u.shape[0])[:, None] * u[-1]   # 선형 드리프트 제거
        return float(np.linalg.norm(u, axis=1).max() * 1000.0)

    @property
    def peak_acceleration(self) -> float:
        """최대가속도 [g]."""
        if self.time.size < 2:
            return 0.0
        dt = float(self.time[1] - self.time[0])
        a = np.gradient(self.velocity, dt, axis=0)
        return float(np.linalg.norm(a, axis=1).max() / 9.81)

    def line(self) -> str:
        c = self.ppv_components
        return (f"{self.name:>10s} {self.distance:7.1f} {self.ppv:10.2f} {self.pvs:9.2f} "
                f"{c[0]:8.2f} {c[1]:8.2f} {c[2]:8.2f} {self.dominant_frequency:8.1f} "
                f"{self.peak_displacement:9.3f} {self.peak_acceleration:8.3f}")


def build_records(result, source_center: tuple[float, float]) -> list[SensorRecord]:
    """Result -> SensorRecord 목록."""
    recs = []
    for i, name in enumerate(result.sensor_names):
        p = result.sensor_pos[i]
        r = float(np.hypot(p[0] - source_center[0], p[1] - source_center[1]))
        recs.append(SensorRecord(name, p, r, result.time, result.velocity[:, i, :]))
    return recs


def table(records: list[SensorRecord]) -> str:
    head = (f"{'계측점':>10s} {'거리[m]':>7s} {'PPV[mm/s]':>10s} {'PVS':>9s} "
            f"{'Vx':>8s} {'Vy':>8s} {'Vz':>8s} {'f[Hz]':>8s} {'변위[mm]':>9s} {'가속[g]':>8s}")
    return "\n".join([head, "-" * len(head) * 1] + [r.line() for r in records])
