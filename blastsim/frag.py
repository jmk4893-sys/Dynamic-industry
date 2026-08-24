"""근거리 DEM — 파쇄(fragmentation)와 비산(flyrock) 해석.

FDM(fdm.py)이 원거리 진동을 맡고, 이 모듈이 발파공 주변 수 m 영역의
대변형 거동을 맡는다. 이것이 DEM 을 쓰는 원래 목적이다.

모델
----
* 입자     : 구형, 지름 d. 단순입방 배치 + 무작위 교란(jitter).
             교란은 규칙격자가 만드는 인위적 균열면을 깨뜨린다.
* 본드     : 1차·2차 이웃(거리 <= 1.45 d)을 중심력 본드로 결합.
             k = 0.4 E d 이면 격자가 등방 탄성체가 된다 (lattice.py 유도 참조).
             인장변형률이 sigma_t/E 를 넘으면 파괴 -> 균열.
* 접촉     : 본드가 끊긴 뒤에는 구-구 접촉. 선형 스프링 + 점성(반발계수) +
             Coulomb 마찰. 이것이 파쇄암 이동·적재를 만든다.
* 가스     : 공내 가스가 단열팽창하며 일을 한다. P = P0 (V0/V)^gamma.
             완전 전색이면 공구로 새지 않고, 자유면이 열릴 때만 방출된다.
* 자유면   : 상부면(z=0)과 벤치면(x=face_x) 2자유면. 그 방향으로 파쇄암이 나간다.
* 중력     : 비산 탄도와 적재 형상을 지배한다.

시간적분은 2단계로 나눈다. 본드가 살아 있는 초기 수십 ms 는 본드 강성이
지배해 dt 가 작아야 하지만, 본드가 대부분 끊긴 뒤에는 접촉만 남아 훨씬
무른 계가 되므로 dt 를 크게 잡을 수 있다.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

try:
    from scipy.spatial import cKDTree
except ImportError:                                   # pragma: no cover
    cKDTree = None

from .explosives import Explosive
from .pattern import BlastPattern
from .rock import Rock


@dataclass
class FragConfig:
    """근거리 DEM 설정."""

    particle_size: float = 0.35      # 입자 지름 d [m]
    jitter: float = 0.12             # 위치 교란 (d 대비 비율)
    margin: float = 1.5              # 발파 영역 바깥 여유 [m]
    depth_below_toe: float = 2.0     # 굴착선 아래 추가 두께 [m]

    friction: float = 0.60           # 입자간 마찰계수
    restitution: float = 0.15        # 반발계수(공칭). 인장 클램핑 때문에 실효값은
                                     # 이보다 다소 크다 (0.15 -> 실측 약 0.28).
                                     # 암석 대 암석 실효 반발계수 0.1~0.3 에 맞춘 값.
    contact_softening: float = 50.0  # 접촉강성 = 본드강성 / 이 값

    gas_gamma: float = 1.30          # 폭굉가스 단열지수
    gas_efficiency: float = 0.25     # 가스가 암반 이동에 쓰는 에너지 비율 (0.15~0.30)
    gas_rise_time: float | None = None   # 압력 상승 시정수 [s] (None=폭약값)
    stemming_full: bool = True       # 완전 전색 여부
    vent_time: float = 0.010         # 자유면 개방 후 가스 방출 시정수 [s]

    gravity: float = 9.81            # 중력가속도 [m/s^2] — 비산 탄도와 적재를 지배
    bond_phase: float = 0.10         # 본드 단계 해석시간 [s]
    total_duration: float = 1.20     # 전체 해석시간 [s]
    cfl: float = 0.20
    boundary_damping: float = 0.60   # 고정 경계 점성 (파 반사 저감)
    rebuild_every: int = 25          # 접촉 이웃탐색 갱신 주기 [스텝]
    snapshot_fps: float = 60.0       # 영상용 프레임 저장률
    progress: bool = True
    seed: int = 20260824


class FragModel:
    """입자 배치 · 본드 생성 · 경계 지정."""

    def __init__(self, rock: Rock, pattern: BlastPattern, cfg: FragConfig,
                 face_x: float | None = None) -> None:
        if cKDTree is None:
            raise ImportError("근거리 DEM 에는 scipy 가 필요합니다: pip install scipy")
        self.rock = rock
        self.pattern = pattern
        self.cfg = cfg
        self.d = cfg.particle_size
        self.face_x = (pattern.origin[0] - pattern.burden) if face_x is None else face_x
        self._build_particles()
        self._build_bonds()

    # ---- 입자 --------------------------------------------------------------
    def _build_particles(self) -> None:
        p, c = self.pattern, self.cfg
        d = self.d
        xs_h = [h.x for h in p.holes]
        ys_h = [h.y for h in p.holes]
        self.x_lo = self.face_x
        self.x_hi = max(xs_h) + p.burden + c.margin
        self.y_lo = min(ys_h) - p.spacing / 2 - c.margin
        self.y_hi = max(ys_h) + p.spacing / 2 + c.margin
        self.z_lo = -(p.bench_height + p.subdrill + c.depth_below_toe)
        self.z_hi = 0.0

        nx = max(2, int(round((self.x_hi - self.x_lo) / d)))
        ny = max(2, int(round((self.y_hi - self.y_lo) / d)))
        nz = max(2, int(round((self.z_hi - self.z_lo) / d)))
        gx = self.x_lo + (np.arange(nx) + 0.5) * d
        gy = self.y_lo + (np.arange(ny) + 0.5) * d
        gz = self.z_lo + (np.arange(nz) + 0.5) * d
        X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
        pos = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])

        rng = np.random.default_rng(c.seed)
        if c.jitter > 0:
            pos += (rng.random(pos.shape) - 0.5) * (2.0 * c.jitter * d)

        self.pos0 = pos
        self.n = pos.shape[0]
        self.radius = 0.5 * d
        self.mass = self.rock.density * (d ** 3)      # 셀 부피 기준 (충전율 1)
        self.volume = d ** 3

        # 고정 경계: 뒤쪽(x_hi), 좌우(y), 바닥(z_lo). 자유면(x_lo, z_hi)은 자유.
        t = 1.01 * d
        self.fixed = ((pos[:, 0] > self.x_hi - t) | (pos[:, 1] < self.y_lo + t)
                      | (pos[:, 1] > self.y_hi - t) | (pos[:, 2] < self.z_lo + t))
        # 벤치면은 굴착선(z = -H) 위쪽만 자유면이다. 그 아래는 하부 소단 암반이
        # 이어지므로 구속해야 한다. 안 그러면 근저부가 과도하게 밀려나온다.
        self.toe_z = -p.bench_height
        self.fixed |= (pos[:, 0] < self.x_lo + t) & (pos[:, 2] < self.toe_z)
        self.free_idx = np.flatnonzero(~self.fixed)

    # ---- 본드 --------------------------------------------------------------
    def _build_bonds(self) -> None:
        tree = cKDTree(self.pos0)
        pairs = np.array(sorted(tree.query_pairs(r=1.45 * self.d)), dtype=np.int32)
        if pairs.size == 0:
            raise RuntimeError("본드가 생성되지 않았습니다 — 입자 지름을 확인하세요.")
        self.bi, self.bj = pairs[:, 0], pairs[:, 1]
        vec = self.pos0[self.bj] - self.pos0[self.bi]
        self.blen = np.linalg.norm(vec, axis=1)
        self.bdir = vec / self.blen[:, None]
        self.k_bond = 0.4 * self.rock.young * self.d
        self.bond_alive = np.ones(self.bi.size, dtype=bool)
        self.bond_breakable = np.ones(self.bi.size, dtype=bool)
        self.eps_t = self.rock.tensile / self.rock.young
        # 접촉 탐색에서 '원래 본드였던 쌍'을 걸러내기 위한 정렬 키
        self.bond_key = np.sort(self.bi.astype(np.int64) * self.n
                                + self.bj.astype(np.int64))

    # ---- 수치 파라미터 ------------------------------------------------------
    @property
    def k_contact(self) -> float:
        return self.k_bond / self.cfg.contact_softening

    def dt_bond(self) -> float:
        # 한 입자에 최대 18개 본드가 붙는다고 보고 omega_max ~ 2*sqrt(6k/m)
        return self.cfg.cfl * math.sqrt(self.mass / (6.0 * self.k_bond))

    def dt_contact(self) -> float:
        return self.cfg.cfl * math.sqrt(self.mass / (6.0 * self.k_contact))

    def summary(self) -> str:
        vol = (self.x_hi - self.x_lo) * (self.y_hi - self.y_lo) * (self.z_hi - self.z_lo)
        return (
            f"[근거리 DEM] 입자 {self.n:,}개 (지름 {self.d * 100:.0f} cm), "
            f"본드 {self.bi.size:,}개\n"
            f"  영역 x[{self.x_lo:.1f}, {self.x_hi:.1f}]  y[{self.y_lo:.1f}, {self.y_hi:.1f}]  "
            f"z[{self.z_lo:.1f}, 0] m  =  {vol:,.0f} m^3\n"
            f"  자유면 2면: 상부면 z=0, 벤치면 x={self.face_x:.1f} m "
            f"(굴착선 z={self.toe_z:.1f} m 아래는 하부 소단으로 구속)\n"
            f"  본드강성 {self.k_bond / 1e9:.2f} GN/m, 접촉강성 "
            f"{self.k_contact / 1e6:.0f} MN/m, 입자질량 {self.mass:.1f} kg\n"
            f"  인장 파괴변형률 {self.eps_t * 1e6:.0f} ustrain, "
            f"dt(본드) {self.dt_bond() * 1e6:.1f} us / dt(접촉) {self.dt_contact() * 1e6:.1f} us"
        )


# ---------------------------------------------------------------------------
class BlastLoad:
    """발파 하중 — 충격파와 가스팽창을 분리해 다룬다.

    발파 파괴는 두 단계로 일어난다.

      1) 충격파 (us~ms) : 폭굉 직후의 고압 응력파가 방사균열을 내고, 자유면에서
         반사된 인장파가 박리(spalling)를 일으킨다. **파쇄를 만드는 것은 이쪽**이다.
         진폭은 진동해석과 같은 등가공동 압력감쇠식을 쓴다.

      2) 가스팽창 (ms~10ms) : 폭굉가스가 균열에 침투해 단열팽창하며 파쇄암을
         자유면 쪽으로 밀어낸다. **이동·비산을 만드는 것은 이쪽**이다.

    가스 단계는 반드시 **폭약이 실제로 가진 화학에너지로 정박**해야 한다.
    등가공동 압력을 그대로 써서 P0*V0/(gamma-1) 로 일을 계산하면 폭약 에너지의
    몇 배가 나오는데, 이는 등가공동 반경이 실제 천공경보다 훨씬 크기 때문이다.
    여기서는 거꾸로 간다:

        E_gas = eta_gas * W * Q            (Q = 폭발열 [J/kg])
        P0    = E_gas * (gamma - 1) / V0   (V0 = 초기 공동 부피)

    이렇게 하면 가스가 하는 총 일이 정확히 E_gas 가 되어 에너지 보존이 보장된다.
    eta_gas 는 가스가 암반 이동에 쓰는 비율로 통상 0.15~0.30 이다.
    """

    def __init__(self, model: "FragModel", explosive: Explosive, cfg: FragConfig,
                 source_cfg) -> None:
        self.m = model
        self.exp = explosive
        self.cfg = cfg
        self.scfg = source_cfg
        self.tr = cfg.gas_rise_time or explosive.rise_time
        self._build()

    def _build(self) -> None:
        m, p = self.m, self.m.pattern
        self.cells: list[np.ndarray] = []
        self.normal: list[np.ndarray] = []      # 초기 반경방향 단위벡터 (n,2)
        self.delay: list[float] = []
        self.p_shock: list[float] = []     # 충격파 최대 등가압력 [Pa]
        self.p_gas0: list[float] = []      # 가스 초기압력 [Pa]
        self.r0: list[float] = []
        self.v0: list[float] = []
        self.length: list[float] = []
        self.charge: list[float] = []
        self.vented: list[float] = []
        self.axis: list[tuple[float, float]] = []

        r_gas = 1.0 * m.d
        for h in p.holes:
            if h.charge_length <= 0 or h.charge_weight <= 0:
                continue
            r = np.hypot(m.pos0[:, 0] - h.x, m.pos0[:, 1] - h.y)
            # 축에 너무 가까운 입자는 반경방향이 정의되지 않으므로 제외한다.
            sel = ((r <= r_gas) & (r > 0.25 * m.d)
                   & (m.pos0[:, 2] >= h.z_bottom)
                   & (m.pos0[:, 2] <= h.charge_top) & (~m.fixed))
            idx = np.flatnonzero(sel)
            if idx.size == 0:
                continue
            r_init = max(float(r[idx].mean()), 0.5 * m.d)
            v_init = math.pi * r_init ** 2 * h.charge_length

            e_gas = self.cfg.gas_efficiency * h.charge_weight * self.exp.energy * 1e6
            # 반경방향 단위벡터는 **초기 위치로 고정**한다.
            # 현재 위치로 매번 계산하면, 축 근처 입자가 축을 넘어갈 때 법선이
            # 180도 뒤집혀 Lysmer 감쇠항의 부호가 반전되고 감쇠가 구동으로 바뀐다
            # (실제로 이 때문에 40 ms 부근에서 5,000 m/s 로 발산했다).
            self.cells.append(idx)
            self.normal.append(np.column_stack([
                (m.pos0[idx, 0] - h.x) / r[idx], (m.pos0[idx, 1] - h.y) / r[idx]]))
            self.delay.append(h.delay)
            self.axis.append((h.x, h.y))
            self.r0.append(r_init)
            self.v0.append(v_init)
            self.length.append(h.charge_length)
            self.charge.append(h.charge_weight)
            self.p_shock.append(self._shock_pressure(h, r_init))
            self.p_gas0.append(e_gas * (self.cfg.gas_gamma - 1.0) / v_init)
            self.vented.append(math.inf)

        self.burden = p.burden
        # 진동해석(source.py)에서는 공벽 근방 본드를 파괴 금지로 두지만, 파쇄해석은
        # 목적이 반대다. 근접부는 실제로 파쇄되어야 하고, 보호하면 무한 응력을
        # 견디는 인공 강체 코어가 되어 가스가 그것을 통해 암반 전체를 찢는다.
        # 공벽 속도는 Lysmer 방사감쇠(반음해)가 P/(rho*Vp) 로 묶어 준다.
        m.bond_breakable = np.ones(m.bi.size, dtype=bool)
        # 주변 암반의 방사 임피던스 rho*Vp — 공벽 속도를 P/(rho*Vp) 로 제한한다
        self.impedance = m.rock.density * m.rock.p_velocity

    def _shock_pressure(self, hole, r_eq: float) -> float:
        """등가공동 충격 압력 — 진동해석(source.py)과 동일한 감쇠식."""
        c = self.scfg
        r_h = hole.hole_dia / 2.0
        r_c = c.crush_ratio * r_h
        p_b = self.exp.borehole_pressure(hole.charge_dia, hole.hole_dia)
        p = p_b * (r_h / r_c) ** c.alpha_crush
        if r_eq > r_c:
            p *= (r_c / r_eq) ** c.alpha_elastic
        return c.efficiency * p

    # ---- 전색 판정 ----------------------------------------------------------
    def stemming_check(self) -> tuple[str, dict]:
        """전색 적정성 판정.

        가스 추력과 전색재 마찰을 정적으로 비교하면 항상 '분출'로 나온다
        (추력이 마찰의 수십 배다). 실제로 전색이 기능하는 것은 정적 강도가
        아니라 **관성과 시간** 때문이므로, 판정은 실무에서 검증된 기하 기준
        (T/B, T/천공경)으로 하고 물리량은 참고치로 함께 보인다.
        """
        p = self.m.pattern
        h = p.holes[0]
        T, B, dh = p.stemming, p.burden, h.hole_dia
        thrust = self.exp.borehole_pressure(h.charge_dia, h.hole_dia) * math.pi * (dh / 2) ** 2
        mass = 1600.0 * math.pi * (dh / 2) ** 2 * T
        t_eject = math.sqrt(2.0 * T * mass / max(thrust, 1.0))    # 전 압력 유지 시 분출시간

        if T / B >= 0.7 and T / dh >= 20.0:
            grade = "양호 — 완전 전색 기능"
        elif T / B >= 0.5 and T / dh >= 15.0:
            grade = "보통 — 공구 비산·폭풍압 주의"
        else:
            grade = "불량 — 전색 분출 우려, 전색장 증대 필요"
        return grade, {"T/B": T / B, "T/dh": T / dh, "thrust_MN": thrust / 1e6,
                       "stem_mass_kg": mass, "t_eject_ms": t_eject * 1e3}

    # ---- 시간별 하중 --------------------------------------------------------
    def apply(self, pos: np.ndarray, vel: np.ndarray, force: np.ndarray,
              t: float, dt: float | None = None, mass: float | None = None,
              ) -> list[dict]:
        """가스·충격 압력과 방사감쇠를 입자에 가한다.

        압력만 가하면 공벽 입자가 자유가속해 수천 m/s 로 발산한다. 실제로는
        주변 암반이 임피던스 rho*Vp 로 저항하므로, Lysmer 점성항을 함께 걸어
        정상상태 벽면속도가 v = P/(rho*Vp) 가 되게 한다.

        이 점성항은 매우 뻣뻣하다 (완화시간 m/c 가 dt 의 몇 배밖에 안 된다).
        양해법으로 두면 한 스텝에 속도가 수 m/s 씩 튀어 에너지가 새므로,
        **반음해로 정확히 푼다**. 반경방향 성분에 대해

            v_new = (v + (F_n + P*A) dt/m) / (1 + c dt/m)

        가 되도록 등가 절점력을 역산해 넣는다. 이러면 dt 에 무관하게 안정하다.
        """
        info = []
        implicit = dt is not None and mass is not None
        for n, idx in enumerate(self.cells):
            dt_ = t - self.delay[n]
            if dt_ <= 0.0:
                info.append({"shock": 0.0, "gas": 0.0, "r": self.r0[n]})
                continue
            ax, ay = self.axis[n]
            r = np.hypot(pos[idx, 0] - ax, pos[idx, 1] - ay)
            r_mean = max(float(r.mean()), self.r0[n])
            nrm = self.normal[n]
            nx_, ny_ = nrm[:, 0], nrm[:, 1]

            # (1) 충격파 — 폭원 압력이력 그대로
            ps = self.p_shock[n] * float(self.exp.pressure_history(np.array([dt_]))[0])

            # (2) 가스 — 단열팽창, 상승시정수 tr
            v = math.pi * r_mean ** 2 * self.length[n]
            pg = (self.p_gas0[n] * (1.0 - math.exp(-dt_ / self.tr))
                  * (self.v0[n] / v) ** self.cfg.gas_gamma)

            # 자유면 관통 -> 방출
            if math.isinf(self.vented[n]) and r_mean > 0.7 * self.burden:
                self.vented[n] = t
            if not math.isinf(self.vented[n]):
                pg *= math.exp(-(t - self.vented[n]) / self.cfg.vent_time)
            if not self.cfg.stemming_full:
                pg *= math.exp(-dt_ / (3.0 * self.cfg.vent_time))

            info.append({"shock": ps, "gas": pg, "r": r_mean})
            # 면적 배분 — 충격파와 가스를 다르게 다뤄야 한다.
            #  * 충격파: us~ms 사이 지나가는 과도파다. 그 순간의 공동 형상은
            #    사실상 초기 형상이므로 **고정 면적**을 쓴다. 팽창 면적을 쓰면
            #    입자가 날아갈수록 면적이 커져 힘이 늘어나는 양의 되먹임이 생겨
            #    수천 m/s 로 발산한다.
            #  * 가스: 팽창하며 일을 하므로 현재 면적을 써야 ∫P dV 가 맞는다.
            #    다만 자유면 관통(방출) 지점까지로 제한한다.
            area0 = 2.0 * math.pi * self.r0[n] * self.length[n] / idx.size
            r_work = min(r_mean, 0.7 * self.burden)
            area_g = 2.0 * math.pi * r_work * self.length[n] / idx.size

            f_drive = ps * area0 + pg * area_g
            c_rad = self.impedance * area0
            vr = vel[idx, 0] * nx_ + vel[idx, 1] * ny_

            if implicit:
                # 이미 누적된 다른 힘의 반경방향 성분
                fn = force[idx, 0] * nx_ + force[idx, 1] * ny_
                beta = c_rad * dt / mass
                f = (fn + f_drive - c_rad * vr) / (1.0 + beta) - fn
            else:
                f = f_drive - c_rad * vr

            if not np.any(np.abs(f) > 1.0):
                continue
            force[idx, 0] += f * nx_
            force[idx, 1] += f * ny_
        return info

    def energy_budget(self) -> dict:
        """에너지 수지 [MJ] — 물리적 타당성 자체 점검용.

        가스는 설계상 E = eta*W*Q 로 정박되지만, 충격파는 압력감쇠식이 주는 값을
        그대로 쓰므로 상한이 없다. 공벽 속도가 임피던스로 v = P/(rho*Vp) 에 묶이므로
        충격파가 하는 일은

            W_shock = (A / (rho*Vp)) * integral P(t)^2 dt

        로 추정된다. 이 값과 가스일의 합이 화학에너지를 넘으면 모델이 과대하다.
        """
        w = sum(self.charge)
        chem = w * self.exp.energy
        gas = sum(p * v / (self.cfg.gas_gamma - 1.0) for p, v in
                  zip(self.p_gas0, self.v0)) / 1e6

        dt = self.exp.rise_time / 40.0
        t = np.arange(0.0, 15.0 * self.exp.decay_time, dt)
        f2 = float(np.sum(self.exp.pressure_history(t) ** 2) * dt)
        shock = 0.0
        for n, idx in enumerate(self.cells):
            area = 2.0 * math.pi * self.r0[n] * self.length[n]
            shock += area / self.impedance * self.p_shock[n] ** 2 * f2
        shock /= 1e6
        return {"장약량_kg": w, "화학에너지_MJ": chem, "가스일_MJ": gas,
                "충격파일_MJ": shock, "가스효율": gas / chem if chem else 0.0,
                "총효율": (gas + shock) / chem if chem else 0.0}

    def summary(self) -> str:
        grade, d = self.stemming_check()
        e = self.energy_budget()
        mode = "완전 전색" if self.cfg.stemming_full else "부분 전색"
        warn = "  [!] 화학에너지 초과 — 모델 과대" if e["총효율"] > 1.0 else ""
        return (
            f"[발파하중] {mode},  전색장 {self.m.pattern.stemming:.2f} m "
            f"(T/B = {d['T/B']:.2f}, T/천공경 = {d['T/dh']:.0f})  ->  {grade}\n"
            f"  충격파 등가압력 {self.p_shock[0] / 1e6:,.0f} MPa @ r={self.r0[0]:.2f} m "
            f"(파쇄를 만든다)\n"
            f"  가스 초기압력 {self.p_gas0[0] / 1e6:.1f} MPa, 단열지수 "
            f"{self.cfg.gas_gamma} (이동·비산을 만든다)\n"
            f"  에너지 수지: 화학 {e['화학에너지_MJ']:,.0f} MJ  ->  충격파 "
            f"{e['충격파일_MJ']:,.0f} + 가스 {e['가스일_MJ']:,.0f} MJ = "
            f"{e['총효율']:.0%}{warn}\n"
            f"  참고: 가스추력 {d['thrust_MN']:,.0f} MN, 전색재 {d['stem_mass_kg']:.0f} kg, "
            f"전압력 유지 시 분출까지 {d['t_eject_ms']:.1f} ms\n"
            f"  하중 입자 {sum(i.size for i in self.cells):,}개 / {len(self.cells)}공"
        )


# ---------------------------------------------------------------------------
@dataclass
class FragResult:
    """근거리 DEM 결과."""

    pos0: np.ndarray                     # 초기 위치 (n,3)
    pos: np.ndarray                      # 최종 위치 (n,3)
    frames: list                         # [(t, pos, speed)] 영상용
    fragment_id: np.ndarray              # 입자별 파쇄체 번호
    fragment_size: np.ndarray            # 파쇄체별 등가 입경 [m]
    fragment_mass: np.ndarray            # 파쇄체별 질량 [kg]
    peak_speed: np.ndarray               # 입자별 최대 속도 [m/s]
    broken: int
    total_bonds: int
    radius: float
    wall_time: float = 0.0
    face_x: float = 0.0
    toe_z: float = 0.0
    pressure_log: list = field(default_factory=list)   # (t, shock, gas, r)


class FragSolver:
    """2단계 시간적분 — (1) 본드 파괴 단계, (2) 접촉·비산·적재 단계."""

    def __init__(self, model: FragModel, load: BlastLoad, cfg: FragConfig | None = None):
        self.m = model
        self.load = load
        self.cfg = cfg or model.cfg
        m = model
        # 접촉 감쇠계수 (반발계수 e 로부터)
        e = min(max(self.cfg.restitution, 1e-3), 0.999)
        m_eff = m.mass / 2.0
        self.c_n = -2.0 * math.log(e) * math.sqrt(
            m_eff * m.k_contact / (math.pi ** 2 + math.log(e) ** 2))

    # ---- 힘 계산 ------------------------------------------------------------
    def _bond_forces(self, pos, force) -> int:
        m = self.m
        alive = m.bond_alive
        if not alive.any():
            return 0
        i, j = m.bi[alive], m.bj[alive]
        vec = pos[j] - pos[i]
        dist = np.linalg.norm(vec, axis=1)
        L0 = m.blen[alive]
        strain = (dist - L0) / L0

        broke = (strain > m.eps_t) & m.bond_breakable[alive]
        n_broke = int(broke.sum())
        if n_broke:
            idx = np.flatnonzero(alive)[broke]
            m.bond_alive[idx] = False
            keep = ~broke
            i, j, dist, vec = i[keep], j[keep], dist[keep], vec[keep]
            strain, L0 = strain[keep], L0[keep]
        if i.size == 0:
            return n_broke

        f = (m.k_bond * strain * L0)[:, None] * (vec / dist[:, None])
        np.add.at(force, i, f)
        np.add.at(force, j, -f)
        return n_broke

    def _pair_contact(self, pos, vel, force, i, j, ref) -> None:
        """기준거리 ref 보다 가까워진 쌍에 반발·점성·마찰을 가한다.

        ref 를 쌍마다 다르게 두는 것이 핵심이다. 교란 배치에서는 이웃 간격이
        제각각이라 일률적으로 2r 을 쓰면 초기부터 21% 의 쌍이 '겹친' 상태가 되고,
        본드가 끊기는 순간 수십 MN 의 가짜 반발력이 터져 해석이 발산한다.
          * 원래 본드였던 쌍 -> ref = 초기 본드길이 L0  (초기 반발력 0)
          * 새로 생긴 접촉   -> ref = 2r
        """
        if i.size == 0:
            return
        m = self.m
        vec = pos[j] - pos[i]
        dist = np.linalg.norm(vec, axis=1)
        overlap = ref - dist
        hit = overlap > 0.0
        if not hit.any():
            return
        i, j = i[hit], j[hit]
        n = vec[hit] / np.maximum(dist[hit], 1e-12)[:, None]
        ov = overlap[hit]

        dv = vel[j] - vel[i]
        vn = np.einsum("ij,ij->i", dv, n)
        # n 은 i->j 방향이므로 vn > 0 이면 서로 멀어지는 중이다.
        # 점성항은 상대운동을 거스르는 -c*vn 이라야 한다. +c*vn 로 두면 분리할 때
        # 반발력이 커져 충돌마다 에너지가 주입되고, 결국 해석이 발산한다.
        fn = np.maximum(m.k_contact * ov - self.c_n * vn, 0.0)   # 인장 전달 없음

        vt = dv - vn[:, None] * n
        vt_mag = np.linalg.norm(vt, axis=1)
        ok = vt_mag > 1e-9
        ft = np.zeros_like(vt)
        if ok.any():
            mag = np.minimum(self.cfg.friction * fn[ok], self.c_n * vt_mag[ok])
            ft[ok] = -mag[:, None] * vt[ok] / vt_mag[ok, None]

        # n 은 i->j 방향. 반발은 j 를 +n 으로 민다. ft 는 j 에 작용하는 마찰력.
        f = fn[:, None] * n + ft
        np.add.at(force, i, -f)
        np.add.at(force, j, f)

    def _contact_forces(self, pos, vel, force, pairs) -> None:
        m = self.m
        # (a) 끊어진 본드 쌍
        #     기준거리는 min(L0, 2r) 이다. L0 를 그대로 쓰면 2차 이웃 본드
        #     (L0 ~ 1.41 d > 2r) 가 끊길 때 **닿지도 않은 입자 사이에** 수십 MN 의
        #     유령 반발력이 생겨 연쇄 파괴로 발산한다. 반대로 2r 만 쓰면 교란 배치의
        #     짧은 본드에서 초기 겹침이 생긴다. 둘 중 작은 값이 정답이다.
        dead = ~m.bond_alive
        if dead.any():
            ref = np.minimum(m.blen[dead], 2.0 * m.radius)
            self._pair_contact(pos, vel, force, m.bi[dead], m.bj[dead], ref)
        # (b) 원래 이웃이 아니었던 새 접촉 — 구-구 접촉
        if pairs.size:
            key = pairs[:, 0].astype(np.int64) * m.n + pairs[:, 1].astype(np.int64)
            fresh = pairs[~np.isin(key, m.bond_key)]
            if fresh.size:
                self._pair_contact(pos, vel, force, fresh[:, 0], fresh[:, 1],
                                   2.0 * m.radius)

    def _ground(self, pos, vel, force) -> None:
        """하부 소단 바닥면 (자유면 앞쪽 x < face_x, z = toe_z) 과의 접촉."""
        m = self.m
        pen = (m.toe_z + m.radius) - pos[:, 2]
        hit = (pos[:, 0] < m.face_x) & (pen > 0.0)
        if not hit.any():
            return
        k, c = m.k_contact, self.c_n
        fz = k * pen[hit] - c * vel[hit, 2]
        fz = np.maximum(fz, 0.0)
        force[hit, 2] += fz
        # 바닥 마찰
        vh = vel[hit, :2]
        sp = np.linalg.norm(vh, axis=1)
        ok = sp > 1e-9
        if ok.any():
            mag = np.minimum(self.cfg.friction * fz[ok], c * sp[ok])
            force[np.flatnonzero(hit)[ok], :2] -= mag[:, None] * vh[ok] / sp[ok, None]

    # ---- 실행 ---------------------------------------------------------------
    def run(self) -> FragResult:
        m, cfg = self.m, self.cfg
        n = m.n
        pos = m.pos0.copy()
        vel = np.zeros((n, 3))
        force = np.zeros((n, 3))
        moving = ~m.fixed
        inv_m = np.where(moving, 1.0 / m.mass, 0.0)[:, None]
        g = np.array([0.0, 0.0, -cfg.gravity])

        # 경계 근처 점성 (고정 경계에서의 인위적 반사 저감)
        # 고정 경계는 파를 완전 반사시킨다. 경계에서 3d 이내 입자에 점성을 걸어
        # 반사파를 흡수한다. 계수는 단일 입자-본드 진동자의 임계감쇠 sqrt(m*k) 척도.
        dist_b = np.minimum.reduce([
            m.x_hi - m.pos0[:, 0], m.pos0[:, 1] - m.y_lo,
            m.y_hi - m.pos0[:, 1], m.pos0[:, 2] - m.z_lo])
        band = 3.0 * m.d
        bdamp = (cfg.boundary_damping * math.sqrt(m.mass * m.k_bond)
                 * np.clip(1.0 - dist_b / band, 0.0, 1.0))[:, None]

        peak = np.zeros(n)
        frames: list = []
        plog: list = []
        skin = 0.35 * m.d
        pairs = np.empty((0, 2), dtype=np.int32)
        t = 0.0
        broken = 0
        frame_dt = 1.0 / cfg.snapshot_fps
        next_frame = 0.0
        t0 = time.time()

        stages = ((cfg.bond_phase, m.dt_bond(), "본드"),
                  (cfg.total_duration, m.dt_contact(), "비산"))
        prev_end = 0.0
        for t_end, dt, label in stages:
            if t_end <= prev_end:
                continue
            # 비산 단계의 큰 dt 는 '본드가 대부분 끊겼다'는 전제 위에 있다.
            # 아직 많이 살아 있으면 본드 강성이 지배하므로 작은 dt 를 유지한다.
            alive_frac = float(m.bond_alive.mean())
            if label == "비산" and alive_frac > 0.15:
                dt = m.dt_bond()
                if cfg.progress:
                    print(f"  (본드 {alive_frac:.0%} 생존 -> 비산 단계도 "
                          f"dt={dt * 1e6:.1f} us 유지)")
            n_steps = max(1, int(round((t_end - prev_end) / dt)))
            for step in range(n_steps):
                if step % cfg.rebuild_every == 0:
                    tree = cKDTree(pos)
                    pr = tree.query_pairs(r=2.0 * m.radius + skin, output_type="ndarray")
                    pairs = pr.astype(np.int32) if len(pr) else np.empty((0, 2), np.int32)

                force[:] = m.mass * g
                broken += self._bond_forces(pos, force)
                self._contact_forces(pos, vel, force, pairs)
                self._ground(pos, vel, force)
                info = self.load.apply(pos, vel, force, t, dt=dt, mass=m.mass)
                force -= bdamp * vel

                vel += force * inv_m * dt
                pos += vel * dt
                t += dt

                sp = np.linalg.norm(vel, axis=1)
                np.maximum(peak, sp, out=peak)
                if t >= next_frame:
                    frames.append((t, pos.copy(), sp.copy()))
                    next_frame += frame_dt
                    if info:
                        plog.append((t, info[0]["shock"], info[0]["gas"], info[0]["r"]))

                if not np.isfinite(sp).all() or sp.max() > 5e3:
                    raise RuntimeError(
                        f"근거리 DEM 발산 (t={t * 1e3:.1f} ms, vmax={sp.max():.3g} m/s). "
                        f"cfl 을 낮추세요 (현재 {cfg.cfl}).")
                if cfg.progress and step % max(1, n_steps // 10) == 0:
                    print(f"\r  DEM[{label}] {100.0 * step / n_steps:5.1f}%  "
                          f"t={t * 1e3:7.1f} ms  vmax={sp.max():6.1f} m/s  "
                          f"파괴본드={broken:,}/{m.bi.size:,}", end="", flush=True)
            prev_end = t_end

        if cfg.progress:
            print(f"\r  DEM 완료  ({time.time() - t0:.1f} s)" + " " * 40)

        fid, fsize, fmass = fragment_analysis(m)
        return FragResult(pos0=m.pos0, pos=pos, frames=frames, fragment_id=fid,
                          fragment_size=fsize, fragment_mass=fmass, peak_speed=peak,
                          broken=broken, total_bonds=int(m.bi.size), radius=m.radius,
                          wall_time=time.time() - t0, face_x=m.face_x, toe_z=m.toe_z,
                          pressure_log=plog)

    def summary(self) -> str:
        m = self.m
        return (f"[DEM 솔버] dt 본드단계 {m.dt_bond() * 1e6:.1f} us / "
                f"비산단계 {m.dt_contact() * 1e6:.1f} us,  "
                f"본드 {self.cfg.bond_phase * 1e3:.0f} ms + 비산 "
                f"{(self.cfg.total_duration - self.cfg.bond_phase) * 1e3:.0f} ms\n"
                f"  마찰계수 {self.cfg.friction}, 반발계수 {self.cfg.restitution}, "
                f"중력 {self.cfg.gravity} m/s^2")


# ---------------------------------------------------------------------------
def fragment_analysis(model: FragModel):
    """살아 있는 본드의 연결성분 -> 파쇄체. 등가 입경과 질량을 돌려준다."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = model.n
    alive = model.bond_alive
    i, j = model.bi[alive], model.bj[alive]
    adj = coo_matrix((np.ones(i.size), (i, j)), shape=(n, n))
    n_comp, labels = connected_components(adj, directed=False)
    counts = np.bincount(labels, minlength=n_comp)
    vol = counts * model.volume
    size = vol ** (1.0 / 3.0)               # 등가 정육면체 변 길이
    mass = vol * model.rock.density
    return labels, size, mass
