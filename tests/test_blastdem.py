"""blastdem 검증 테스트.

    python -m pytest tests/ -v        (pytest 있을 때)
    python tests/test_blastdem.py     (없을 때 — 자체 러너)

물리 검증의 핵심은 test_lattice_elastic_constants / test_wave_speed 두 개다.
격자가 이론 탄성파 속도를 재현하지 못하면 나머지 결과는 의미가 없다.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blastdem import (BlastPattern, BlastSimulation, Lattice, get_explosive,
                      get_rock, line_array)
from blastdem.empirical import SD_LAWS, fit_law
from blastdem.rock import LATTICE_POISSON, Rock
from blastdem.simulation import DomainConfig
from blastdem.solver import SolverConfig
from blastdem.source import SourceConfig


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
    from blastdem.solver import DEMSolver

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
    from blastdem.solver import DEMSolver
    from blastdem.pattern import BlastPattern
    from blastdem.source import BlastSource

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
    from blastdem.source import BlastSource
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
    from blastdem.source import BlastSource
    rock, e = get_rock("granite"), get_explosive("emulsion")
    pat = BlastPattern(e, bench_height=8.0, n_rows=1, n_cols=2)
    lat = Lattice(rock, (-12, 14), (-12, 12), 14, 1.0)
    src = BlastSource(lat, pat, e)
    for load in src.hole_load:
        assert np.abs(load.sum(axis=0)).max() < 1e-6 * np.abs(load).max()


def test_elastic_core_protected():
    """폭원 근방 본드는 파괴 금지로 표시된다."""
    from blastdem.source import BlastSource
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
    from blastdem.source import BlastSource
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
