"""blastsim 검증 테스트.

    python -m pytest tests/ -v        (pytest 있을 때)
    python tests/test_blastsim.py     (없을 때 — 자체 러너)

물리 검증의 핵심은 test_lattice_elastic_constants / test_wave_speed 두 개다.
격자가 이론 탄성파 속도를 재현하지 못하면 나머지 결과는 의미가 없다.
"""
from __future__ import annotations

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blastsim import (BlastPattern, BlastSimulation, Lattice, get_explosive,
                      get_rock, line_array)
from blastsim.empirical import SD_LAWS, fit_law
from blastsim.rock import LATTICE_POISSON, Rock
from blastsim.simulation import DomainConfig
from blastsim.solver import SolverConfig
from blastsim.source import SourceConfig


# ---------------------------------------------------------------------------
# 1. 격자 탄성상수 — 해석적 검증
# ---------------------------------------------------------------------------
def test_lattice_elastic_constants():
    """k = 0.4*E*d 에서 C11=3k/d, C12=C44=k/d, nu=0.25, E 복원."""
    rock = get_rock("granite")
    d = 1.5
    lat = Lattice(rock, (0, 15), (0, 15), 15, d)
    k = lat.k
    assert abs(k - 0.4 * rock.young * d) < 1e-6 * k

    c11, c12, c44 = 3 * k / d, k / d, k / d
    assert abs(c44 - (c11 - c12) / 2) < 1e-9 * c11, "등방조건 C44=(C11-C12)/2 불만족"

    nu = c12 / (c11 + c12)
    assert abs(nu - LATTICE_POISSON) < 1e-12, f"nu={nu}"

    e_back = c11 - 2 * c12 ** 2 / (c11 + c12)
    assert abs(e_back - rock.young) / rock.young < 1e-12, "E 복원 실패"

    vp = math.sqrt(c11 / rock.density)
    assert abs(vp - rock.p_velocity) / vp < 1e-12
    assert abs(rock.p_velocity / rock.s_velocity - math.sqrt(3)) < 1e-9


def test_lattice_bond_count():
    """내부 입자는 1차 6 + 2차 12 = 18 본드를 가진다."""
    lat = Lattice(get_rock("granite"), (0, 10), (0, 10), 10, 1.0)
    deg = np.zeros(lat.shape, dtype=int)
    for g in lat.bonds:
        deg[g.sa] += 1
        deg[g.sb] += 1
    assert deg.max() == 18
    assert deg[lat.nx // 2, lat.ny // 2, lat.nz // 2] == 18, "내부 배위수 != 18"
    assert deg[0, 0, 0] < 18, "모서리 입자는 본드가 적어야 함"


def dynamical_matrix(lat: Lattice, q: np.ndarray) -> np.ndarray:
    """격자 동역학행렬  D(q) = (1/m) * sum_{18 이웃 R} k (n x n) (1 - cos(q.R)).

    고유값이 omega^2 이므로 omega/|q| 가 위상속도가 된다. 시간영역 도달시간
    픽과 달리 경계반사·모드변환에 오염되지 않는 '정확한' 검증 수단이다.
    """
    d, k, m = lat.d, lat.k, lat.m
    offs = []
    for o in [(1, 0, 0), (0, 1, 0), (0, 0, 1),
              (1, 1, 0), (1, -1, 0), (1, 0, 1), (1, 0, -1), (0, 1, 1), (0, 1, -1)]:
        offs += [o, tuple(-x for x in o)]
    D = np.zeros((3, 3))
    for o in offs:
        R = np.array(o, float) * d
        n = R / np.linalg.norm(R)
        D += k * np.outer(n, n) * (1.0 - np.cos(q @ R))
    return D / m


def test_lattice_dispersion_long_wavelength():
    """장파장 극한에서 격자가 이론 Vp, Vs 를 정확히 재현하는가 (오차 < 0.1%)."""
    rock = get_rock("granite")
    lat = Lattice(rock, (0, 4), (0, 4), 4, 1.0)
    for direction in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 1, 1), (2, 1, 3)]:
        u = np.array(direction, float)
        u /= np.linalg.norm(u)
        q = (2 * math.pi / (1000.0 * lat.d)) * u          # 파장당 1000 요소
        w = np.sqrt(np.sort(np.linalg.eigvalsh(dynamical_matrix(lat, q))))
        v = w / np.linalg.norm(q)
        assert abs(v[2] - rock.p_velocity) / rock.p_velocity < 1e-3, f"{direction} Vp={v[2]:.1f}"
        assert abs(v[0] - rock.s_velocity) / rock.s_velocity < 1e-3, f"{direction} Vs={v[0]:.1f}"
        assert abs(v[0] - v[1]) / v[0] < 1e-6, "두 횡파 모드가 축퇴되지 않음(비등방)"


def test_lattice_isotropy():
    """전파방향에 관계없이 같은 속도 -> 등방성. 중심력 격자의 핵심 성질."""
    lat = Lattice(get_rock("gneiss"), (0, 4), (0, 4), 4, 1.0)
    q0 = 2 * math.pi / (200.0 * lat.d)
    speeds = []
    for direction in [(1, 0, 0), (1, 1, 0), (1, 1, 1), (3, 1, 2)]:
        u = np.array(direction, float)
        u /= np.linalg.norm(u)
        w2 = np.sort(np.linalg.eigvalsh(dynamical_matrix(lat, q0 * u)))
        speeds.append(np.sqrt(w2) / q0)
    speeds = np.array(speeds)
    for col, name in ((2, "종파"), (0, "횡파")):
        spread = float(np.ptp(speeds[:, col])) / speeds[:, col].mean()
        assert spread < 5e-3, f"{name} 방향의존성 {spread:.2%} (등방성 위배)"


def test_lattice_numerical_dispersion():
    """파장당 요소수가 줄면 속도가 느려지고(수치분산), 10요소에서 5% 이내."""
    lat = Lattice(get_rock("granite"), (0, 4), (0, 4), 4, 1.0)
    vp0 = lat.rock.p_velocity
    prev = None
    for npw in (40, 20, 10):
        q = np.array([2 * math.pi / (npw * lat.d), 0.0, 0.0])
        v = math.sqrt(np.linalg.eigvalsh(dynamical_matrix(lat, q)).max()) / q[0]
        assert v < vp0, "수치분산은 속도를 낮춰야 한다"
        if prev is not None:
            assert v < prev, "요소수가 줄수록 더 느려져야 한다"
        prev = v
    assert abs(prev - vp0) / vp0 < 0.05, f"10요소/파장에서 오차 {abs(prev - vp0) / vp0:.1%}"


class _PulseSource:
    """검증 전용 점 충격원 (반주기 사인). BlastSource 와 동일한 apply() 인터페이스."""

    def __init__(self, idx: int, amp: float, duration: float) -> None:
        self.idx, self.amp, self.T = idx, amp, duration

    def apply(self, force: list, t: float) -> None:
        if 0.0 < t < self.T:
            force[0][self.idx] += self.amp * math.sin(math.pi * t / self.T)


def test_wave_speed_time_domain():
    """솔버가 실제로 Vp 근처 속도로 파를 전파시키는가 (통합 smoke test).

    경계·자유면 영향을 피하려고 큰 영역 깊은 곳에 폭원과 측점을 둔다.
    정밀 검증은 test_lattice_dispersion_long_wavelength 가 담당한다.
    """
    from blastsim.solver import DEMSolver

    rock = Rock("t", density=2650, young=60e9, ucs=1e12, tensile=1e12, damping_ratio=0.0)
    lat = Lattice(rock, (-30, 30), (-30, 30), 40, 1.0)
    src = _PulseSource(lat.nearest([[0, 0, -20]])[0], 5e9, 1.0e-3)
    solver = DEMSolver(lat, src, SolverConfig(
        duration=0.004, cfl=0.10, allow_breakage=False, progress=False))

    probes = np.array([5.0, 10.0, 15.0])
    res = solver.run(np.column_stack([probes, np.zeros(3), np.full(3, -20.0)]))
    sig = np.abs(res.velocity[:, :, 0])
    thr = 0.02 * sig[:, 0].max()          # 모든 측점에 동일한 절대 임계값
    t_arr = np.array([res.time[int(np.argmax(sig[:, i] > thr))] for i in range(3)])
    assert np.all(np.diff(t_arr) > 0), f"도달시간이 단조증가하지 않음: {t_arr * 1e3}"
    vp = 1.0 / np.polyfit(probes, t_arr, 1)[0]
    err = abs(vp - rock.p_velocity) / rock.p_velocity
    assert err < 0.10, f"Vp 측정 {vp:.0f} vs 이론 {rock.p_velocity:.0f} (오차 {err:.1%})"


def test_rayleigh_damping_targets():
    """Rayleigh 계수가 목표 감쇠비를 두 기준주파수에서 정확히 만족하는가."""
    from blastsim.solver import DEMSolver
    from blastsim.pattern import BlastPattern
    from blastsim.source import BlastSource

    rock = get_rock("granite")
    e = get_explosive("emulsion")
    lat = Lattice(rock, (-8, 8), (-8, 8), 10, 2.0)
    pat = BlastPattern(e, bench_height=6.0, n_rows=1, n_cols=1)
    cfg = SolverConfig(damping_f1=10.0, damping_f2=120.0, progress=False)
    sv = DEMSolver(lat, BlastSource(lat, pat, e), cfg)
    for f in (cfg.damping_f1, cfg.damping_f2):
        assert abs(sv.damping_ratio_at(f) - rock.damping_ratio) < 1e-9, f"{f} Hz 불일치"
    # 격자 해상한계 고주파는 목표보다 강하게 감쇠되어야 수치잡음이 제거된다
    nyquist = lat.rock.s_velocity / (2.0 * lat.d)      # 격자 Nyquist
    assert sv.damping_ratio_at(nyquist) > 3.0 * rock.damping_ratio, \
        "격자 Nyquist 고주파 잡음이 충분히 감쇠되지 않음"
    assert sv.dt_critical < lat.critical_dt, "강성비례 감쇠는 임계 dt 를 줄여야 함"


# ---------------------------------------------------------------------------
# 2. 폭약 / 패턴
# ---------------------------------------------------------------------------
def test_detonation_pressure():
    """Pd = rho*VOD^2/(1+gamma), 디커플링은 압력을 낮춘다."""
    e = get_explosive("emulsion")
    expect = 1200.0 * 5500 ** 2 / 4.0
    assert abs(e.detonation_pressure - expect) / expect < 1e-9
    full = e.borehole_pressure(0.076, 0.076)
    dec = e.borehole_pressure(0.032, 0.076)
    assert dec < full / 5.0, "디커플링 감압 효과 부족"
    assert abs(full - 0.5 * e.detonation_pressure) / full < 1e-9


def test_pressure_history_peak():
    """정규화 압력이력의 최대값은 1.0, t<=0 에서는 0."""
    e = get_explosive("anfo")
    t = np.linspace(-1e-3, 40e-3, 20000)
    p = e.pressure_history(t)
    assert abs(p.max() - 1.0) < 1e-3
    assert p[t <= 0].max() == 0.0
    assert p[-1] < 0.02


def test_charge_weight_roundtrip():
    e = get_explosive("emulsion")
    w = e.charge_weight(6.0, 0.070)
    assert abs(e.charge_length(w, 0.070) - 6.0) < 1e-9
    # 76mm x 6m 에멀젼(비중 1.20) -> pi/4*0.076^2*6*1200 = 32.7 kg
    assert 30 < e.charge_weight(6.0, 0.076) < 35


def test_pattern_charge_per_delay():
    """동시기폭이면 W = 총장약량, 시차를 주면 공당 장약량."""
    e = get_explosive("emulsion")
    inst = BlastPattern(e, n_rows=2, n_cols=4, delay_hole=0.0, delay_row=0.0)
    assert abs(inst.max_charge_per_delay - inst.total_charge) < 1e-6

    seq = BlastPattern(e, n_rows=2, n_cols=4, delay_hole=0.025, delay_row=0.065)
    assert abs(seq.max_charge_per_delay - seq.charge_per_hole) < 1e-6
    assert seq.total_charge > seq.max_charge_per_delay


def test_pattern_geometry():
    e = get_explosive("emulsion")
    p = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=10.0, n_rows=2, n_cols=5)
    assert p.n_holes == 10
    assert abs(p.subdrill - 0.9) < 1e-9        # 0.3B
    assert abs(p.stemming - 3.0) < 1e-9        # 1.0B
    assert abs(p.holes[0].charge_length - (10.9 - 3.0)) < 1e-9
    assert 0.3 < p.powder_factor < 0.9


# ---------------------------------------------------------------------------
# 3. 폭원 — 격자 무관성
# ---------------------------------------------------------------------------
def test_source_mesh_independence():
    """alpha_elastic=1 이면 폭원이 주는 총 반경력이 격자간격에 무관해야 한다.

    P_eq ∝ 1/r_eq, 공동 표면적 ∝ r_eq 이므로 곱은 상수가 된다.
    """
    from blastsim.source import BlastSource
    rock, e = get_rock("granite"), get_explosive("emulsion")
    pat = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=8.0, n_rows=1, n_cols=1)
    line, node = [], []
    for d in (1.0, 1.25, 1.5, 2.0):
        lat = Lattice(rock, (-12, 12), (-12, 12), 14, d)
        src = BlastSource(lat, pat, e, SourceConfig())
        line.append(src.hole_pressure[0] * 2 * math.pi * src.r_eq)          # 단위길이당 [N/m]
        node.append(sum(np.linalg.norm(l, axis=1).sum() for l in src.hole_load))  # 총 절점력 [N]
    assert max(line) / min(line) < 1.001, f"단위길이당 반경력 격자의존 (비 {max(line) / min(line):.3f})"
    assert max(node) / min(node) < 1.05, f"총 절점력 격자의존 (비 {max(node) / min(node):.3f})"


def test_source_zero_net_force():
    """폭원 하중의 합력은 0 이어야 한다(강체 이동 방지)."""
    from blastsim.source import BlastSource
    rock, e = get_rock("granite"), get_explosive("emulsion")
    pat = BlastPattern(e, bench_height=8.0, n_rows=1, n_cols=2)
    lat = Lattice(rock, (-12, 14), (-12, 12), 14, 1.0)
    src = BlastSource(lat, pat, e)
    for load in src.hole_load:
        assert np.abs(load.sum(axis=0)).max() < 1e-6 * np.abs(load).max()


def test_elastic_core_protected():
    """폭원 근방 본드는 파괴 금지로 표시된다."""
    from blastsim.source import BlastSource
    rock, e = get_rock("granite"), get_explosive("emulsion")
    pat = BlastPattern(e, bench_height=8.0, n_rows=1, n_cols=1)
    lat = Lattice(rock, (-12, 12), (-12, 12), 14, 1.0)
    BlastSource(lat, pat, e)
    assert lat.protected.any()
    assert not lat.protected.all()
    assert any((~g.breakable).any() for g in lat.bonds)


# ---------------------------------------------------------------------------
# 4. 경험식
# ---------------------------------------------------------------------------
def test_scaled_distance_roundtrip():
    law = SD_LAWS["kr_mean"]
    D, W = 80.0, 25.0
    v = float(law.ppv(D, W))
    assert abs(law.safe_distance(W, v) - D) / D < 1e-9
    assert abs(law.allowable_charge(D, v) - W) / W < 1e-9


def test_fit_law_recovers_constants():
    """알려진 K, n 으로 만든 데이터를 회귀하면 원래 값이 복원된다."""
    law = SD_LAWS["usbm"]
    W = 30.0
    d = np.array([20, 40, 60, 100, 150], float)
    v = law.ppv(d, W)
    got = fit_law(d, v, W)
    assert abs(got.K - law.K) / law.K < 1e-6
    assert abs(got.n - law.n) < 1e-6


# ---------------------------------------------------------------------------
# 5. 통합 — 소형 해석이 물리적으로 타당한 결과를 내는가
# ---------------------------------------------------------------------------
def test_end_to_end_small():
    """소형 모델 완주 + PPV 가 거리에 따라 단조 감소."""
    e = get_explosive("emulsion")
    pat = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=6.0, n_rows=1, n_cols=1)
    pts, names = line_array((0, 0), (1, 0), [15, 25, 40])
    sim = BlastSimulation(
        rock=get_rock("granite"), explosive=e, pattern=pat,
        sensor_points=pts, sensor_names=names,
        domain=DomainConfig(spacing=2.0, max_particles=200_000),
        solver_cfg=SolverConfig(duration=0.05, progress=False),
    ).run()
    ppv = [r.ppv for r in sim.records]
    assert all(np.isfinite(ppv)), "비정상 값"
    assert ppv[0] > ppv[1] > ppv[2], f"거리에 따라 감소하지 않음: {ppv}"
    assert 0.01 < ppv[0] < 5000, f"PPV 크기 비현실적: {ppv[0]}"
    assert sim.result.peak_domain_velocity < 50.0, "탄성코어 밖 속도 발산"


def test_calibration_linearity():
    """PPV 가 폭원 효율 eta 에 정확히 선형인가.

    apply_calibration() 이 '배수를 곱하는 것'으로 재해석을 대신할 수 있는 근거다.
    본드 파괴가 없어야 성립하므로 allow_breakage=False 로 확인한다.
    """
    e = get_explosive("emulsion")
    pat = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=6.0, n_rows=1, n_cols=1)
    pts, names = line_array((0, 0), (1, 0), [15, 25])

    def run(eta):
        return BlastSimulation(
            rock=get_rock("granite"), explosive=e, pattern=pat,
            sensor_points=pts, sensor_names=names,
            domain=DomainConfig(spacing=2.0, max_particles=200_000),
            source_cfg=SourceConfig(efficiency=eta),
            solver_cfg=SolverConfig(duration=0.04, allow_breakage=False, progress=False),
        ).run()

    a, b = run(1.0), run(3.0)
    assert a.result.broken_bonds == 0 and b.result.broken_bonds == 0
    for ra, rb in zip(a.records, b.records):
        ratio = rb.ppv / ra.ppv
        assert abs(ratio - 3.0) < 1e-6, f"{ra.name}: 비 {ratio:.6f} != 3 (비선형)"

    # apply_calibration 이 같은 결과를 주는가
    c = run(1.0)
    c.apply_calibration(factor=3.0)
    for rc, rb in zip(c.records, b.records):
        assert abs(rc.ppv - rb.ppv) / rb.ppv < 1e-9, "apply_calibration 과 재해석 불일치"
    assert abs(c.calibration - 3.0) < 1e-12


def test_source_scales_with_charge_and_explosive():
    """장약량·폭약 위력이 커지면 폭원 세기도 커져야 한다 (단조성)."""
    from blastsim.source import BlastSource
    rock = get_rock("granite")
    lat = Lattice(rock, (-12, 12), (-12, 12), 14, 1.5)
    strengths = {}
    for key in ("low_vod", "anfo", "emulsion", "dynamite"):
        e = get_explosive(key)
        pat = BlastPattern(e, bench_height=8.0, n_rows=1, n_cols=1)
        src = BlastSource(lat, pat, e)
        strengths[key] = src.hole_pressure[0]
    assert strengths["low_vod"] < strengths["anfo"] < strengths["emulsion"] < strengths["dynamite"]

    # 디커플링(장약경 축소)은 폭원을 약화시켜야 한다
    e = get_explosive("precision")
    full = BlastPattern(e, bench_height=8.0, hole_dia=0.076, charge_dia=0.076, n_rows=1, n_cols=1)
    dec = BlastPattern(e, bench_height=8.0, hole_dia=0.076, charge_dia=0.032, n_rows=1, n_cols=1)
    assert (BlastSource(lat, dec, e).hole_pressure[0]
            < 0.2 * BlastSource(lat, full, e).hole_pressure[0])


def test_degenerate_run_does_not_crash(tmpdir: str = None):
    """진동이 계측점에 도달하지 못하는 짧은 해석에서도 보고서/그림이 안전해야 한다.

    빈 스펙트럼 대역, 0 진폭, 계측점 1개 회귀 등 퇴화 입력에서 예외가 났었다.
    """
    import shutil
    import tempfile

    e = get_explosive("low_vod")
    pat = BlastPattern(e, burden=2.0, spacing=2.4, bench_height=5.0, n_rows=1, n_cols=1)
    pts, names = line_array((0, 0), (1, 0), [30])
    sim = BlastSimulation(
        rock=get_rock("weathered"), explosive=e, pattern=pat,
        sensor_points=pts, sensor_names=names,
        domain=DomainConfig(spacing=3.0, max_particles=100_000),
        solver_cfg=SolverConfig(duration=0.002, progress=False),
    ).run()

    r = sim.records[0]
    assert r.ppv == 0.0 and r.dominant_frequency == 0.0
    assert r.peak_displacement == 0.0 and r.peak_acceleration == 0.0
    assert math.isnan(sim.fitted_law().n)          # 계측점 1개 -> 회귀 불가
    assert len(sim.report()) > 100                 # 보고서는 그래도 나와야 한다

    out = tempfile.mkdtemp()
    try:
        sim.save_figures(out)                      # 예외 없이 통과해야 한다
        sim.save_csv(out + "/s.csv")
    finally:
        shutil.rmtree(out, ignore_errors=True)


# ---------------------------------------------------------------------------
# 6. FDM 원거리 진동 (fdm.py)
# ---------------------------------------------------------------------------
def _rayleigh_exact(nu: float) -> float:
    """Rayleigh 방정식 x^6-8x^4+(24-16k2)x^2+16(k2-1)=0 의 근 (VR/Vs)."""
    k2 = (1 - 2 * nu) / (2 * (1 - nu))
    f = lambda x: x ** 6 - 8 * x ** 4 + (24 - 16 * k2) * x ** 2 + 16 * (k2 - 1)
    lo, hi = 0.5, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def test_fdm_elastic_moduli():
    """FDM 은 DEM 격자와 달리 포아송비를 자유롭게 쓴다."""
    from blastsim.fdm import BenchGeometry, FDMModel
    rock = get_rock("granite")
    for nu in (0.15, 0.25, 0.35):
        m = FDMModel(rock, (0, 20), (0, 20), 20, 2.0,
                     geometry=BenchGeometry(two_free_face=False), poisson=nu)
        mu = rock.young / (2 * (1 + nu))
        lam = rock.young * nu / ((1 + nu) * (1 - 2 * nu))
        assert abs(m.mu - mu) / mu < 1e-12
        assert abs(m.lam - lam) / lam < 1e-12
        assert abs(m.vp - math.sqrt((lam + 2 * mu) / rock.density)) < 1e-9
        # Vp/Vs 는 nu 에 따라 달라져야 한다 (격자 DEM 은 sqrt(3) 고정)
        assert abs(m.vp / m.vs - math.sqrt(2 * (1 - nu) / (1 - 2 * nu))) < 1e-9


def test_fdm_free_surface_and_two_faces():
    """진공 정식화: 지표 위는 진공, 전단계수 0 (= 자유면). 2자유면 형상 확인."""
    from blastsim.fdm import BenchGeometry, FDMModel
    geom = BenchGeometry(bench_height=10.0, face_x=0.0, two_free_face=True)
    m = FDMModel(get_rock("granite"), (-20, 40), (-20, 20), 30, 2.0, geometry=geom)

    ks, j = m.k_surface, m.ny // 2
    assert abs(m.zs[ks]) < 1e-9, "k_surface 가 z=0 이 아니다"
    assert m.n_air >= 4, "자유면 성립에 필요한 진공층이 부족"

    i_bench = int((10 - m.x0) / m.h)
    assert m.solid[i_bench, j, ks], "벤치 상부는 암반"
    assert not m.solid[i_bench, j, ks + 1], "지표 위는 진공"
    assert m.lam2mu[i_bench, j, ks + 2] == 0.0, "진공 셀의 탄성계수는 0"
    # 자유면 전단응력점의 전단계수는 0 (조화평균에 진공이 섞이므로)
    assert m.mu_xz[i_bench, j, ks] == 0.0
    assert m.mu_yz[i_bench, j, ks] == 0.0

    # 제2자유면(벤치면): 면 앞쪽은 굴착선 위가 비어 있어야 한다
    i_front = int((-8 - m.x0) / m.h)
    assert not m.solid[i_front, j, ks], "벤치면 앞 상부는 굴착된 공간"
    k_toe = int((-10 + m.depth) / m.h)
    assert m.solid[i_front, j, k_toe], "굴착선 아래는 하부 소단 암반"

    # 1자유면으로 바꾸면 벤치면이 사라진다
    m1 = FDMModel(get_rock("granite"), (-20, 40), (-20, 20), 30, 2.0,
                  geometry=BenchGeometry(two_free_face=False))
    assert m1.solid[int((-8 - m1.x0) / m1.h), j, m1.k_surface]


def test_fdm_timestep_stability_margin():
    """점성(Kelvin-Voigt)은 임계 dt 를 줄이며, 실제 dt 는 그보다 작아야 한다."""
    from blastsim.fdm import BenchGeometry, CavitySource, FDMConfig, FDMModel, FDMSolver
    rock, e = get_rock("granite"), get_explosive("emulsion")
    pat = BlastPattern(e, bench_height=8.0, n_rows=1, n_cols=1)
    m = FDMModel(rock, (-20, 20), (-20, 20), 25, 2.0,
                 geometry=BenchGeometry(two_free_face=False))
    sv = FDMSolver(m, CavitySource(m, pat.holes, e, SourceConfig()), FDMConfig())
    assert sv.dt_max_damped < m.dt_max, "점성항이 임계 dt 를 줄여야 한다"
    assert sv.dt < sv.dt_max_damped
    # 저주파는 거의 감쇠되지 않고 고주파일수록 강하게 감쇠되어야 한다
    z = lambda f: math.pi * f * sv.beta
    assert z(10) < z(60) < z(300)
    assert abs(z(sv.cfg.damping_freq) - rock.damping_ratio) < 1e-12


def test_fdm_sensors_outside_sponge():
    """계측점이 흡수층(스펀지) 안에 들어가면 안 된다.

    흡수층 안의 기록은 인위적으로 감쇠된 값이라, 감쇠지수 n 이 실제보다 크게
    나오고 경험식 보정계수 eta 까지 함께 틀어진다. 예전 격자산정은 흡수층
    두께를 여유로 잡지 않아서 80 m 계측점이 층 안(가중치 0.45)에 들어갔다.
    """
    from blastsim.project import ProjectConfig, BlastProject, QUALITY_PRESETS

    for quality in QUALITY_PRESETS:
        for dists in ([30.0, 50.0, 80.0], [30.0, 50.0, 80.0, 120.0], [15.0, 200.0]):
            pr = BlastProject(ProjectConfig(quality=quality, distances=list(dists)))
            model, pts, names = pr.vibration_model()
            w = model.sponge_weight(pts)
            assert w.min() > 0.999, (
                f"{quality} {dists}: 계측점이 흡수층 안 "
                f"(최소 가중치 {w.min():.3f}, h={model.h:.2f} m)")
            assert model.n <= QUALITY_PRESETS[quality]["fdm_max_cells"] * 1.02, (
                f"{quality} {dists}: 셀 예산 초과 {model.n:,}")

    # 시험이 헛돌지 않는지 — 스펀지는 실제로 감쇠해야 한다
    assert model.sponge.min() < 0.95, "스펀지가 실제로 감쇠하지 않는다"


def test_fdm_rayleigh_wave_speed():
    """자유면 위 Rayleigh 파 속도가 이론값과 맞는가 (탄성 + 자유면 동시 검증).

    두 측점 간 연직속도 상호상관으로 위상속도를 재고, 이론 VR = xi(nu)*Vs 와
    비교한다. 이 검증이 통과하면 탄성계수·자유면·시간적분이 모두 맞는 것이다.
    """
    from blastsim.fdm import BenchGeometry, FDMConfig, FDMModel, FDMSolver

    class _PointPressure:
        def __init__(self, model, ijk, amp, fc):
            self.idx = int(np.ravel_multi_index(ijk, model.shape))
            self.amp, self.fc, self.prev = amp, fc, 0.0

        def apply(self, sxx, syy, szz, t):
            a = (math.pi * self.fc * (t - 1.5 / self.fc)) ** 2
            p = self.amp * (1 - 2 * a) * math.exp(-a)
            dp, self.prev = p - self.prev, p
            for arr in (sxx, syy, szz):
                arr[self.idx] -= dp

    def lag(a, b, dt):
        a, b = a - a.mean(), b - b.mean()
        c = np.correlate(b, a, "full")
        k = int(np.argmax(c))
        dk = 0.0
        if 0 < k < len(c) - 1:
            y0, y1, y2 = c[k - 1], c[k], c[k + 1]
            den = y0 - 2 * y1 + y2
            if den:
                dk = 0.5 * (y0 - y2) / den
        return (k - (len(a) - 1) + dk) * dt

    nu = 0.25
    rock = Rock("t", density=2650, young=60e9, poisson=nu, damping_ratio=0.0)
    h, fc, x1, x2 = 2.0, 120.0, 100.0, 180.0
    m = FDMModel(rock, (-30, 260), (-40, 40), 40, h,
                 geometry=BenchGeometry(two_free_face=False), poisson=nu)
    vr_th = _rayleigh_exact(nu) * m.vs
    src = _PointPressure(m, (int((0 - m.x0) / h), m.ny // 2, m.k_surface - 3), 5e9, fc)
    dur = 1.5 / fc + x2 / vr_th + 5.0 / fc
    sv = FDMSolver(m, src, FDMConfig(duration=dur, cfl=0.75, progress=False))
    res = sv.run(np.array([[x1, 0, 0], [x2, 0, 0]]))

    dl = lag(res.velocity[:, 0, 2], res.velocity[:, 1, 2], res.dt)
    assert dl > 0, "두 번째 측점이 더 늦게 도달해야 한다"
    vr = (x2 - x1) / dl
    err = abs(vr - vr_th) / vr_th
    assert err < 0.05, f"VR 측정 {vr:.0f} vs 이론 {vr_th:.0f} (오차 {err:.1%})"


# ---------------------------------------------------------------------------
# 7. DEM 근거리 파쇄·비산 (frag.py)
# ---------------------------------------------------------------------------
def _frag_setup(particle=0.5, **kw):
    from blastsim.frag import BlastLoad, FragConfig, FragModel, FragSolver
    e = get_explosive("emulsion")
    pat = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=10.0,
                       n_rows=1, n_cols=2)
    cfg = FragConfig(particle_size=particle, progress=False, **kw)
    m = FragModel(get_rock("granite"), pat, cfg)
    load = BlastLoad(m, e, cfg, SourceConfig())
    return m, load, FragSolver(m, load, cfg), cfg


def test_frag_initial_equilibrium():
    """t=0 에서 본드력·접촉력이 정확히 0 이어야 한다.

    교란 배치에서 접촉 기준거리를 일률적으로 2r 로 두면 초기부터 20% 넘는 쌍이
    '겹친' 상태가 되어, 본드가 끊기는 순간 수십 MN 의 가짜 반발력이 터진다.
    쌍별 기준거리(원래 본드는 자기 L0)를 쓰면 이 문제가 사라진다.
    """
    m, _, sv, _ = _frag_setup()
    pos = m.pos0.copy()
    vel = np.zeros((m.n, 3))
    force = np.zeros((m.n, 3))
    sv._contact_forces(pos, vel, force, np.empty((0, 2), np.int32))
    assert np.abs(force).max() == 0.0, "초기 접촉력이 0 이 아니다"
    sv._bond_forces(pos, force)
    assert np.abs(force).max() < 1e-6, "초기 본드력이 0 이 아니다"
    assert m.bond_alive.all(), "초기에 파괴된 본드가 있다"


def test_ground_contact_cannot_launch():
    """바닥 접촉이 입자를 쏘아 올려서는 안 된다.

    저항선(x > face_x)에는 바닥이 없다 — 굴착선 아래로도 암반이 이어지기
    때문이다. 자유면 앞(x < face_x)에만 바닥이 있다. 저항선 입자가 자유면
    앞으로 넘어오는 순간 그동안의 겹침이 한꺼번에 '켜지는데', penalty 를 그대로
    쓰면 k*pen = 3.7e7 N (a = 1.5e5 m/s^2) 이 되어 입자를 쏘아 올린다.
    실제로 이것 때문에 45 cm 입자 해석에서 145 m/s 짜리 비산체와 398 m 짜리
    비산거리가 나왔다(60 cm 에서는 격자가 우연히 어긋나 있어 멀쩡했다).
    """
    from blastsim.frag import BlastLoad, FragConfig, FragModel, FragSolver

    rock, e = get_rock("granite"), get_explosive("emulsion")
    pat = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=10.0,
                       n_rows=1, n_cols=1)
    cfg = FragConfig(particle_size=0.45, progress=False)
    m = FragModel(rock, pat, cfg, face_x=-3.0)
    sv = FragSolver(m, BlastLoad(m, e, cfg, SourceConfig()), cfg)

    # (1) z 격자가 굴착선에 정렬되어야 한다 — 계통적 겹침이 없어야 한다
    gz = m.z_lo + (np.arange(int(round((m.z_hi - m.z_lo) / m.d))) + 0.5) * m.d
    first = gz[gz > m.toe_z][0]
    assert abs(first - (m.toe_z + m.radius)) < 1e-9, (
        f"굴착선 위 첫 입자열 {first:.4f} != 기준면 {m.toe_z + m.radius:.4f}")

    # (2) 그래도 깊이 겹친 입자가 생겼을 때 쏘아 올려지면 안 된다
    dt = m.dt_bond()
    pos = np.array([[-3.01, 0.0, m.toe_z + m.radius - 0.20]])   # 0.20 m 겹침
    vel = np.zeros((1, 3))
    force = np.array([[0.0, 0.0, -m.mass * cfg.gravity]])
    sv._ground(pos, vel, force, dt)
    dv = force[0, 2] / m.mass * dt
    assert dv < 0.05, f"바닥이 정지한 입자를 {dv:.2f} m/s 로 밀어 올린다"

    # (3) 그러면서도 낙하하는 입자는 제대로 멈춰야 한다 (구속 기능 유지)
    vel = np.array([[0.0, 0.0, -8.0]])
    force = np.array([[0.0, 0.0, -m.mass * cfg.gravity]])
    sv._ground(pos, vel, force, dt)
    vz_new = vel[0, 2] + force[0, 2] / m.mass * dt
    assert vz_new > -8.0, "바닥이 하강을 전혀 막지 못한다"
    assert vz_new <= 0.05, f"바닥이 반발로 되튀긴다 (vz={vz_new:.2f} m/s)"


def test_frag_two_free_face_boundary():
    """2자유면: 상부면과 벤치면은 자유, 굴착선 아래 면쪽은 하부 소단으로 구속."""
    m, _, _, _ = _frag_setup()
    p = m.pos0
    t = 1.01 * m.d
    # y 경계 입자는 별도로 구속되므로 판정에서 뺀다
    mid_y = (p[:, 1] > m.y_lo + t) & (p[:, 1] < m.y_hi - t)
    # 벤치면(x_lo) 쪽 굴착선 위 -> 자유
    upper = (p[:, 0] < m.x_lo + t) & (p[:, 2] > m.toe_z) & mid_y
    assert upper.any() and not m.fixed[upper].any(), "벤치면 상부는 자유면이어야 한다"
    # 벤치면 쪽 굴착선 아래 -> 구속
    lower = (p[:, 0] < m.x_lo + t) & (p[:, 2] < m.toe_z) & mid_y
    assert lower.any() and m.fixed[lower].all(), "굴착선 아래는 구속되어야 한다"
    # 상부면(z=0) 은 자유 (x, y 경계 제외)
    top = (p[:, 2] > -t) & mid_y & (p[:, 0] > m.x_lo + t) & (p[:, 0] < m.x_hi - t)
    assert top.any() and not m.fixed[top].any(), "상부면은 자유면이어야 한다"


def test_blast_load_energy_budget():
    """가스가 하는 총 일이 폭약 화학에너지를 넘으면 안 된다.

    등가공동 압력으로 P0*V0/(gamma-1) 을 계산하면 화학에너지의 몇 배가 나온다.
    그래서 거꾸로 E = eta*W*Q 에서 P0 를 역산한다.
    """
    _, load, _, cfg = _frag_setup()
    e = load.energy_budget()
    assert e["가스일_MJ"] < e["화학에너지_MJ"], "가스일이 화학에너지를 초과"
    assert abs(e["가스효율"] - cfg.gas_efficiency) < 1e-6

    # 이 에너지가 전부 운동에너지가 될 때의 저항선 속도가 실무 범위(10~30 m/s)
    pat = load.m.pattern
    mass = pat.burden * pat.spacing * pat.bench_height * load.m.rock.density * len(load.cells)
    v = math.sqrt(2.0 * e["가스일_MJ"] * 1e6 / mass)
    assert 5.0 < v < 40.0, f"저항선 이동속도 {v:.1f} m/s 가 비현실적"


def test_blast_load_wall_velocity_bounded():
    """공벽 속도가 임피던스 한계 v = P/(rho*Vp) 근처로 묶이는가.

    압력만 가하고 방사감쇠가 없으면 공벽 입자가 자유가속해 수천 m/s 로 발산한다.
    완화시간 m/c 가 dt 의 4~5 배뿐이라 반음해로 풀어야 한다.
    """
    m, load, _, _ = _frag_setup()
    dt = m.dt_bond()
    idx = load.cells[0]
    pos = m.pos0.copy()
    vel = np.zeros((m.n, 3))
    force = np.zeros((m.n, 3))
    for k in range(400):
        force[:] = 0.0
        load.apply(pos, vel, force, k * dt, dt=dt, mass=m.mass)
        vel += force / m.mass * dt
    nrm = load.normal[0]
    vr = vel[idx, 0] * nrm[:, 0] + vel[idx, 1] * nrm[:, 1]
    ps = load.p_shock[0] * float(load.exp.pressure_history(np.array([400 * dt]))[0])
    v_limit = ps / load.impedance
    assert 0.0 < vr.mean() < 4.0 * max(v_limit, 0.5), \
        f"공벽속도 {vr.mean():.1f} m/s 가 임피던스 한계 {v_limit:.1f} m/s 대비 과대"


def test_stemming_criterion():
    """전색 판정은 T/B 와 T/천공경 기하기준을 따른다."""
    from blastsim.frag import BlastLoad, FragConfig, FragModel
    e = get_explosive("emulsion")
    grades = {}
    for stem in (0.6, 1.6, 3.0):
        pat = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=10.0,
                           n_rows=1, n_cols=1, stemming=stem)
        cfg = FragConfig(particle_size=0.6, progress=False)
        m = FragModel(get_rock("granite"), pat, cfg)
        grades[stem] = BlastLoad(m, e, cfg, SourceConfig()).stemming_check()[0]
    assert "불량" in grades[0.6], grades[0.6]
    assert "양호" in grades[3.0], grades[3.0]


def test_kuz_ram_realistic_and_monotonic():
    """Kuz-Ram 파쇄입도가 실무 범위이고 비장약량에 대해 단조여야 한다.

    DEM 본드망 연결성분은 퍼콜레이션 때문에 입도를 못 준다(90% 넘게 끊어야
    쪼개진다). 그래서 입도는 이 경험모델이 담당한다.
    """
    from blastsim.project import kuz_ram
    e = get_explosive("emulsion")
    rock = get_rock("granite")

    prev_x50, prev_pf = None, None
    for B, S, H in ((2.5, 3.0, 8.0), (3.0, 3.5, 10.0), (4.0, 4.6, 12.0)):
        pat = BlastPattern(e, burden=B, spacing=S, bench_height=H, n_rows=2, n_cols=5)
        k = kuz_ram(pat, rock, e)
        assert 0.05 < k["X50"] < 2.0, f"X50 {k['X50']:.2f} m 가 비현실적"
        assert k["X80"] > k["X50"], "X80 은 X50 보다 커야 한다"
        assert 0.7 <= k["n"] <= 2.2
        assert 7.0 <= k["A"] <= 13.0
        # 비장약량이 낮을수록 굵게 나와야 한다
        if prev_x50 is not None:
            assert (pat.powder_factor < prev_pf) == (k["X50"] > prev_x50), \
                "비장약량과 입도의 관계가 뒤집혔다"
        prev_x50, prev_pf = k["X50"], pat.powder_factor

    # 연암이 경암보다 잘게 부서진다
    hard = kuz_ram(BlastPattern(e, burden=3.0, spacing=3.5, bench_height=10.0,
                                n_rows=2, n_cols=5), get_rock("granite"), e)
    soft = kuz_ram(BlastPattern(e, burden=3.0, spacing=3.5, bench_height=10.0,
                                n_rows=2, n_cols=5), get_rock("shale"), e)
    assert soft["X50"] < hard["X50"], "연암이 더 잘게 부서져야 한다"


def test_bond_network_percolation_limit():
    """본드망 연결성분은 90% 넘게 끊기 전에는 한 덩어리로 남는다.

    이 성질 때문에 DEM 연결성분으로 파쇄입도를 뽑으면 과대평가된다.
    fragmentation_stats 가 이를 size_reliable 로 표시하는지 확인한다.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    n = 12
    g = np.mgrid[0:n, 0:n, 0:n].reshape(3, -1).T.astype(float)
    pairs = np.array(sorted(cKDTree(g).query_pairs(r=1.45)))
    N, M = len(g), len(pairs)
    rng = np.random.default_rng(0)

    def largest(frac):
        keep = rng.random(M) > frac
        i, j = pairs[keep, 0], pairs[keep, 1]
        adj = coo_matrix((np.ones(i.size), (i, j)), shape=(N, N))
        _, lab = connected_components(adj, directed=False)
        return np.bincount(lab).max() / N

    assert largest(0.50) > 0.95, "50% 파괴에서는 아직 한 덩어리여야 한다"
    assert largest(0.95) < 0.30, "95% 파괴에서는 잘게 쪼개져야 한다"


def test_contact_restitution_dissipates():
    """접촉이 반드시 에너지를 소산해야 한다 (분리속도 < 접근속도).

    법선 점성항 부호가 반대이면(+c*vn) 분리할 때 반발력이 커져 충돌마다 에너지가
    주입되고 해석이 발산한다. 이 테스트가 그 회귀를 막는다.
    """
    from blastsim.frag import BlastLoad, FragConfig, FragModel, FragSolver
    e = get_explosive("emulsion")
    pat = BlastPattern(e, burden=3.0, spacing=3.5, bench_height=10.0,
                       n_rows=1, n_cols=1)
    prev = 0.0
    for rest in (0.1, 0.3, 0.6, 0.9):
        cfg = FragConfig(particle_size=0.5, restitution=rest, progress=False)
        m = FragModel(get_rock("granite"), pat, cfg)
        sv = FragSolver(m, BlastLoad(m, e, cfg, SourceConfig()), cfg)
        r = m.radius
        pos = np.array([[0.0, 0.0, 0.0], [2 * r + 1e-3, 0.0, 0.0]])
        vel = np.array([[5.0, 0.0, 0.0], [-5.0, 0.0, 0.0]])
        force = np.zeros((2, 3))
        dt = m.dt_contact() * 0.2
        i, j = np.array([0]), np.array([1])
        v_in = vel[0, 0] - vel[1, 0]
        for k in range(200_000):
            force[:] = 0.0
            sv._pair_contact(pos, vel, force, i, j, 2 * r)
            vel += force / m.mass * dt
            pos += vel * dt
            if pos[1, 0] - pos[0, 0] > 2 * r and k > 10:
                break
        e_meas = (vel[1, 0] - vel[0, 0]) / v_in
        assert 0.0 < e_meas < 1.0, f"반발계수 {e_meas:.3f} 가 물리적 범위 밖"
        assert e_meas > prev, "설정 반발계수가 커지면 실측도 커져야 한다"
        prev = e_meas
    assert prev > 0.7, f"e=0.9 에서 실측 {prev:.2f} — 감쇠가 과도"


def test_fragment_analysis_connectivity():
    """본드 연결성분이 파쇄체가 된다 — 전부 살아 있으면 한 덩어리."""
    from blastsim.frag import fragment_analysis
    m, _, _, _ = _frag_setup(particle=0.7)
    _, size, mass = fragment_analysis(m)
    assert size.size == 1, "초기에는 하나의 덩어리여야 한다"
    total = m.n * m.volume * m.rock.density
    assert abs(mass.sum() - total) / total < 1e-9, "질량 보존 위배"

    # 본드를 전부 끊으면 입자 수만큼의 파쇄체
    m.bond_alive[:] = False
    _, size2, mass2 = fragment_analysis(m)
    assert size2.size == m.n
    assert abs(mass2.sum() - total) / total < 1e-9


# ---------------------------------------------------------------------------
# 8. 사면체 메쉬 (mesh.py)
#
# 메쉬 생성기는 눈으로 보면 그럴듯한데 틀린 경우가 많아서, 해석적으로 값을 아는
# 불변량만 골라 검증한다: (1) 볼록 영역을 빈틈없이 채웠는가(체적·표면적),
# (2) 원통 구멍이 이론 체적/면적을 재현하는가, (3) 크기장을 따라가는가.
# ---------------------------------------------------------------------------
_MESH_CACHE: dict = {}


def _mesh(preset="빠름"):
    """생성 비용이 있으므로 테스트 간 재사용 (기본 = 사용자 요구 사양)."""
    from blastsim.mesh import build_tet_mesh
    if preset not in _MESH_CACHE:
        _MESH_CACHE[preset] = build_tet_mesh(config=preset)
    return _MESH_CACHE[preset]


def test_borehole_distance_field():
    """원통 부호거리 — 축/공벽/측면/공저 방향의 해석해와 일치."""
    from blastsim.mesh import Borehole
    h = Borehole(collar=(0, 0, 0), axis=(0, 0, -1), length=12.0, diameter=0.075)
    r = h.radius
    p = np.array([
        [0.0, 0.0, -6.0],      # 축 위 중앙        -> -r
        [r, 0.0, -6.0],        # 공벽              ->  0
        [1.0, 0.0, -6.0],      # 측면 1 m          ->  1 - r
        [0.0, 0.0, -14.0],     # 공저에서 2 m 아래 ->  2
        [0.0, 0.0, 3.0],       # 공구에서 3 m 위   ->  3
    ])
    expect = np.array([-r, 0.0, 1.0 - r, 2.0, 3.0])
    assert np.allclose(h.distance(p), expect, atol=1e-12), h.distance(p)
    assert abs(h.volume - math.pi * r ** 2 * 12.0) < 1e-15
    assert np.allclose(h.toe, [0, 0, -12.0])


def test_mesh_fills_box():
    """사면체 체적 합 = 직육면체 체적, 외부 경계면적 = 6면 합, 경계는 닫힌 곡면."""
    m = _mesh()
    assert m.domain.volume == 20.0 ** 3
    v = m.volumes().sum()
    assert abs(v / m.domain.volume - 1) < 1e-9, f"체적 {v}"
    assert m.volumes().min() > 0.0, "영부피 사면체가 남아 있다"

    facets = m.boundary_facets()
    area = m.facet_areas(facets).sum()
    assert abs(area / (6 * 400.0) - 1) < 1e-9, f"표면적 {area}"

    # 닫힘: 경계 삼각형의 모든 모서리가 정확히 2번 쓰인다
    e = np.sort(np.concatenate([facets[:, [0, 1]], facets[:, [1, 2]],
                                facets[:, [0, 2]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    assert set(cnt.tolist()) == {2}, f"경계가 닫히지 않음: {set(cnt.tolist())}"


def test_mesh_hole_geometry():
    """천공홀 체적/공벽 면적이 내접다각형 이론값을 재현."""
    from blastsim.mesh import REGION_HOLE
    m = _mesh()
    n = m.config.n_theta
    # 원에 내접한 정n각형 면적비 = (n/2pi) sin(2pi/n)
    inscribed = n / (2 * math.pi) * math.sin(2 * math.pi / n)
    ratio = m.volumes()[m.region == REGION_HOLE].sum() / m.hole.volume
    assert inscribed - 0.03 < ratio < 1.02, f"홀 체적비 {ratio:.3f} (내접 {inscribed:.3f})"

    wall = m.hole_wall_facets()
    assert len(wall) > 4 * n, f"공벽 삼각형 {len(wall)}개"
    a = m.facet_areas(wall).sum() / m.hole.wall_area
    assert 0.93 < a < 1.07, f"공벽 면적비 {a:.3f}"


def test_mesh_sizing_field():
    """요소 크기가 설계 크기장 h(d)=min(h_far, h_near+growth*d) 를 따른다."""
    m = _mesh()
    cfg = m.config
    h_near = cfg.h_near or math.pi * m.hole.diameter / cfg.n_theta
    c = m.centroids()
    d = np.maximum(m.hole.distance(c), 0.0)
    size = m.edge_lengths().mean(axis=1)

    # d_sat 밖에서는 h 가 h_far 로 포화한다. 점 간격 h 인 Delaunay 의 평균
    # 모서리는 h 보다 3할쯤 길어지므로 상·하한을 넉넉히 둔다.
    d_sat = (cfg.h_far - h_near) / cfg.growth
    near = size[d < 2 * h_near]
    far = size[d > 2 * d_sat]
    assert len(near) > 100 and len(far) > 100, (len(near), len(far))
    assert 0.5 * h_near < np.median(near) < 3 * h_near, np.median(near)
    assert 0.5 * cfg.h_far < np.median(far) < 2 * cfg.h_far, np.median(far)

    # 단조 성장 — 거리 구간별 중앙 크기가 감소하지 않아야 한다
    edges = np.logspace(-2, 1, 8)
    med = [np.median(size[(d >= a) & (d < b)])
           for a, b in zip(edges[:-1], edges[1:]) if ((d >= a) & (d < b)).sum() > 30]
    assert all(y >= x * 0.9 for x, y in zip(med, med[1:])), med


def test_mesh_quality():
    """퇴화 요소 제거 후 품질 — 99% 이상이 q>0.1, 중앙값 0.5 이상."""
    m = _mesh()
    q = m.quality()
    assert q.min() > 0.0
    assert (q > 0.1).mean() > 0.99, f"q>0.1 비율 {(q > 0.1).mean():.4f}"
    assert np.median(q) > 0.5, f"중앙 품질 {np.median(q):.3f}"
    assert m.n_dropped > 0, "면 위 공면점의 퇴화 사면체가 하나도 안 걸러졌다"

    ang = m.dihedral_angles()
    assert ang.shape == (m.n_tets, 6)
    assert 0.0 < ang.min() and ang.max() < 180.0
    # 정사면체 이면각 70.53도 주변에 최빈값이 있어야 한다
    assert 55.0 < np.median(ang) < 90.0, np.median(ang)


def test_mesh_cut_section():
    """평면 절단 단면적 = 직육면체 단면적."""
    m = _mesh()
    polys, reg = m.cut_polygons(axis=1, value=0.0)
    assert len(polys) > 1000 and len(polys) == len(reg)

    def shoelace(p):
        x, y = p[:, 0], p[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    total = sum(shoelace(p) for p in polys)
    assert abs(total / (20.0 * 20.0) - 1) < 1e-9, f"단면적 {total}"
    assert all(len(p) in (3, 4) for p in polys)


def test_mesh_inclined_hole():
    """경사공(15도)에서도 체적·홀 체적이 유지된다."""
    from blastsim.mesh import REGION_HOLE, Borehole, BoxDomain, MeshConfig, build_tet_mesh
    th = math.radians(15.0)
    hole = Borehole(collar=(0, 0, 0), axis=(math.sin(th), 0, -math.cos(th)),
                    length=8.0, diameter=0.09)
    m = build_tet_mesh(BoxDomain.from_size(12, 12, 12), hole,
                       MeshConfig(h_far=2.0, growth=1.0, n_theta=8))
    assert abs(m.volumes().sum() / m.domain.volume - 1) < 1e-9
    ratio = m.volumes()[m.region == REGION_HOLE].sum() / hole.volume
    assert 0.85 < ratio < 1.05, f"경사공 체적비 {ratio:.3f}"


def test_mesh_subset_and_export(tmpdir=None):
    """영역 분리와 VTK 왕복 — 파일에서 되읽은 체적이 원본과 같다."""
    import tempfile

    from blastsim.mesh import REGION_HOLE, REGION_ROCK
    m = _mesh()
    rock, hole = m.subset(REGION_ROCK), m.subset(REGION_HOLE)
    assert rock.n_tets + hole.n_tets == m.n_tets
    assert abs(rock.volumes().sum() + hole.volumes().sum()
               - m.volumes().sum()) < 1e-6
    assert rock.tets.max() < rock.n_points, "절점 재번호 실패"

    with tempfile.TemporaryDirectory() as d:
        path = hole.write_vtk(os.path.join(d, "hole.vtk"))
        lines = open(path).read().split("\n")
        i = next(k for k, l in enumerate(lines) if l.startswith("POINTS"))
        pts = np.array([l.split() for l in lines[i + 1:i + 1 + hole.n_points]], float)
        j = next(k for k, l in enumerate(lines) if l.startswith("CELLS"))
        tets = np.array([l.split()[1:] for l in lines[j + 1:j + 1 + hole.n_tets]], int)
        c = pts[tets]
        v = np.abs(np.linalg.det(c[:, 1:] - c[:, :1])).sum() / 6
        assert abs(v - hole.volumes().sum()) < 1e-9 * max(v, 1e-9)
        assert hole.write_msh(os.path.join(d, "hole.msh"))


def test_mesh_reproducible():
    """같은 시드는 같은 메쉬, 다른 시드는 다른 점군 (그러나 같은 체적)."""
    from blastsim.mesh import BoxDomain, MeshConfig, build_tet_mesh
    dom = BoxDomain.from_size(8, 8, 8)
    cfg = MeshConfig(h_far=2.0, growth=1.0, n_theta=8)
    a = build_tet_mesh(dom, config=cfg)
    b = build_tet_mesh(dom, config=cfg)
    assert a.n_points == b.n_points and np.array_equal(a.points, b.points)

    c = build_tet_mesh(dom, config=MeshConfig(h_far=2.0, growth=1.0, n_theta=8, seed=7))
    assert not (c.n_points == a.n_points and np.array_equal(c.points, a.points))
    assert abs(c.volumes().sum() / dom.volume - 1) < 1e-9


# ---------------------------------------------------------------------------
# unittest 연동
#
# 위 검증은 전부 평범한 함수로 썼다 — 물리식 옆에 assert 를 두는 편이 읽기 쉽고,
# 아래 _run_all 로 의존성 없이 그냥 돌려볼 수 있기 때문이다. 다만 저장소 CI 는
# `python -m unittest discover` 로 tests/ 전체를 훑으므로, 그대로 두면 이 파일은
# import 만 되고 한 건도 실행되지 않는다. 그래서 함수들을 TestCase 메서드로
# 옮겨 담아 discover 가 집어가게 한다.
def _as_test_case() -> type:
    ns: dict = {}
    for name, fn in sorted(globals().items()):
        if not (name.startswith("test_") and callable(fn)):
            continue
        method = (lambda f: lambda self: f())(fn)
        method.__name__, method.__doc__ = name, fn.__doc__
        ns[name] = method
    return type("BlastSimTests", (unittest.TestCase,), ns)


BlastSimTests = _as_test_case()


# ---------------------------------------------------------------------------
def _run_all() -> int:
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    fails = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as ex:
            fails += 1
            print(f"  FAIL  {name}: {ex}")
        except Exception as ex:                      # noqa: BLE001
            fails += 1
            print(f"  ERROR {name}: {type(ex).__name__}: {ex}")
    print(f"\n{len(fns) - fails}/{len(fns)} 통과")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_run_all())
