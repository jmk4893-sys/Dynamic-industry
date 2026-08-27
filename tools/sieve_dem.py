#!/usr/bin/env python3
"""체분리 DEM — 불규칙 형상 입자를 다중구 강체로 푸는 물리엔진.

tools/sieve_sim.py 는 통과 **확률**을 통계적으로 다룬다.
이 모듈은 같은 현상을 **입자 하나하나의 운동방정식**으로 푼다.
두 결과가 맞으면 확률 모델의 파라미터가 물리적으로 뒷받침된다.

물리
- 입자 = 원판 2~3 개를 겹쳐 붙인 강체(clump). 2D 이므로 세장비 하나로
  형상을 표현한다. 강체이므로 회전이 나오고, **배향이 통과를 좌우**한다.
- 접촉 = 선형 스프링-대시팟(법선) + Coulomb 마찰(접선). 원판-원판,
  원판-체선(고정 원판), 원판-측벽.
- 체 = 반경 w/2 인 고정 원판을 피치 (a+w) 로 늘어놓은 것. 개구 통과 여부가
  판정식이 아니라 **기하와 접촉에서 저절로** 나온다.
- 가진 = 데크 좌표계에서 본 관성력. a_z = -Gamma g sin(wt).

    python3 tools/sieve_dem.py --help
"""
import argparse
import json
import math
import os
import numpy as np

# 물질 — (밀도, 2D 세장비, 원판 수, 색)
MATERIAL = {
    "구리":       dict(rho=8960, ar=3.3, n=3, color="#B4652A"),
    "실리콘+은":  dict(rho=2500, ar=2.2, n=2, color="#B0357A"),
    "백시트+EVA": dict(rho=1200, ar=4.1, n=3, color="#0071B0"),
}

DEFAULTS = dict(
    aperture=75e-6, wire=50e-6,
    width=3.0e-3,            # 해석 영역 폭
    n_particles=170,
    gamma=2.2,               # 무차원 가진강도 (peak a / g) — 투척 h≈1 mm 로 시야 유지
    freq=25.0,               # Hz — 1,500 rpm 급. 투척 높이 (Γg/ω)²/2g 를 낮춘다
    # 법선 강성 — 너무 낮으면 개구보다 큰 입자가 눌려 빠져나가는 수치적 관통이
    # 생긴다. kn=8 에서는 실제로 90 µm 입자가 75 µm 개구를 9 % 통과했다.
    # 최대 겹침이 개구의 2 % 이내가 되도록 kn 을 잡고, 그 대가로 dt 가 작아진다.
    kn=300.0,
    restitution=0.35,
    mu=0.45,                 # 마찰계수
    cycles=5.0,
    steps_per_contact=15,
    nb_every=40,             # 이웃리스트 재구축 주기 [스텝]
    d_min=50e-6,             # 최소 입자 폭 — 시간간격을 지배한다
    seed=3,
)
G = 9.81


def build_clumps(rng, cfg):
    """입자를 만든다. 반환은 clump 단위 물성과 body-frame 원판 배치."""
    n = cfg["n_particles"]
    # 75 µm 데크에 실제로 도달하는 것 = -106 µm 분획. 조성은 그 분획 기준.
    names = ["실리콘+은", "구리", "백시트+EVA"]
    probs = np.array([0.72, 0.18, 0.10])
    pick = rng.choice(len(names), size=n, p=probs)

    width_um, discs, rho, colors, ar = [], [], [], [], []
    for k in pick:
        nm = names[k]
        m = MATERIAL[nm]
        if nm == "실리콘+은":
            w = rng.uniform(cfg["d_min"], 105e-6)   # 통과·근접·오버가 모두 섞이도록
        elif nm == "구리":
            w = rng.uniform(75e-6, 106e-6)
        else:
            w = rng.uniform(80e-6, 120e-6)
        width_um.append(w); rho.append(m["rho"]); colors.append(m["color"])
        ar.append(m["ar"]); discs.append(m["n"])
    return (np.array(width_um), np.array(discs), np.array(rho),
            np.array(ar), np.array(colors), np.array([names[k] for k in pick]))


def body_frame(width, ndisc, ar):
    """clump 의 body-frame 원판 중심 [n_max,2] 과 반경. 짧은축 = width."""
    r = width / 2.0
    span = width * (ar - 1.0)                     # 긴축 여유분
    offs = np.linspace(-span / 2.0, span / 2.0, ndisc)
    return offs, r


class Sieve2D:
    """데크 좌표계 2D DEM. 데크는 고정, 가진은 관성력으로 준다."""

    def __init__(self, cfg=None, rng=None):
        self.cfg = dict(DEFAULTS, **(cfg or {}))
        c = self.cfg
        self.rng = rng or np.random.default_rng(c["seed"])
        w, nd, rho, ar, col, name = build_clumps(self.rng, c)

        # clump 물성 — 3D 회전타원체로 질량·관성 계산
        L = w * ar
        vol = math.pi / 6.0 * L * w * w
        self.m = vol * rho
        self.Iz = self.m * (L ** 2 + w ** 2) / 16.0
        self.color, self.name, self.width, self.ar = col, name, w, ar

        # body-frame 원판 배치를 평탄화
        owner, off, rad = [], [], []
        for i in range(len(w)):
            o, r = body_frame(w[i], int(nd[i]), ar[i])
            owner += [i] * len(o); off += list(o); rad += [r] * len(o)
        self.owner = np.array(owner)
        self.off = np.array(off)
        self.rad = np.array(rad)

        # 초기 배치 — 데크 위 얕은 베드
        n = len(w)
        self.pos = np.column_stack([
            self.rng.uniform(0.12e-3, c["width"] - 0.12e-3, n),
            self.rng.uniform(0.15e-3, 0.95e-3, n)])
        self.th = self.rng.uniform(0, 2 * math.pi, n)
        self.vel = np.zeros((n, 2))
        self.om = np.zeros(n)
        self.alive = np.ones(n, bool)
        self.t_exit = np.full(n, np.nan)

        # 체선 — 반경 wire/2 인 고정 원판
        pitch = c["aperture"] + c["wire"]
        nw = int(c["width"] / pitch) + 1
        self.wire_x = (np.arange(nw) + 0.5) * pitch
        self.wire_r = c["wire"] / 2.0

        # 수치 파라미터 — 감쇠는 접촉마다 환산질량으로 계산한다.
        # 전역 상수(cn ∝ √m_min)로 두면 반발계수가 질량에 따라 표류한다:
        # 무거운 구리는 설정 0.35 대신 ~0.87 로 튀어 오분류가 커진다.
        kn = c["kn"]
        e = c["restitution"]
        self._damp_coef = -2.0 * math.log(e) / math.sqrt(
            math.pi ** 2 + math.log(e) ** 2)      # cn = coef·√(m_red·kn)
        t_c = math.pi * math.sqrt(self.m.min() / kn)
        self.dt = t_c / c["steps_per_contact"]
        self.t = 0.0
        self.max_overlap = 0.0       # 수치적 관통 진단
        self.n_steps = int(c["cycles"] / c["freq"] / self.dt)
        self.nb_every = c["nb_every"]
        self._nb_age = 10 ** 9          # 첫 스텝에서 즉시 구축
        self.nb_i = np.array([], int)
        self.nb_j = np.array([], int)

    # ── 접촉력 ──────────────────────────────────────────────────
    def _disc_world(self):
        o = self.owner
        cs, sn = np.cos(self.th[o]), np.sin(self.th[o])
        return np.column_stack([self.pos[o, 0] + self.off * cs,
                                self.pos[o, 1] + self.off * sn])

    def _accumulate(self, F, T, idx, f, dp):
        """원판에 걸린 힘을 clump 의 힘·토크로 옮긴다. bincount 가 add.at 보다 빠르다."""
        o = self.owner[idx]
        n = len(F)
        F[:, 0] += np.bincount(o, weights=f[:, 0], minlength=n)
        F[:, 1] += np.bincount(o, weights=f[:, 1], minlength=n)
        T += np.bincount(o, weights=dp[:, 0] * f[:, 1] - dp[:, 1] * f[:, 0],
                         minlength=n)

    def rebuild_neighbours(self, skin=25e-6):
        """Verlet 이웃리스트. 전체 쌍 계산을 주기적으로만 한다."""
        dw = self._disc_world()
        d = dw[:, None, :] - dw[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1))
        cut = self.rad[:, None] + self.rad[None, :] + skin
        ok = (dist < cut) & (self.owner[:, None] != self.owner[None, :])
        self.nb_i, self.nb_j = np.where(np.triu(ok, 1))
        self._nb_age = 0

    def _contact(self, dpos, dvel, overlap, kn, m_red):
        """법선 스프링-대시팟 + Coulomb 마찰. dpos 는 단위법선.

        m_red 는 접촉의 환산질량 — 감쇠 cn = coef·√(m_red·kn) 을 접촉별로
        계산해 반발계수가 입자 질량과 무관하게 설정값을 유지한다.
        """
        if len(overlap):
            self.max_overlap = max(self.max_overlap, float(np.max(overlap)))
        cn = self._damp_coef * np.sqrt(np.asarray(m_red, float) * kn)
        vn = (dvel * dpos).sum(1)
        fn = np.maximum(kn * overlap - cn * vn, 0.0)
        vt = dvel - vn[:, None] * dpos
        vt_mag = np.linalg.norm(vt, axis=1) + 1e-30
        ft = np.minimum(self.cfg["mu"] * fn, cn * vt_mag)
        return fn[:, None] * dpos - ft[:, None] * vt / vt_mag[:, None]

    def step(self):
        c = self.cfg
        kn = c["kn"]
        n = len(self.m)
        F = np.zeros((n, 2))
        T = np.zeros(n)

        dw = self._disc_world()
        live = self.alive[self.owner]

        if self._nb_age >= self.nb_every:
            self.rebuild_neighbours()
        self._nb_age += 1

        # 원판-원판 (이웃리스트 안에서만)
        ii, jj = self.nb_i, self.nb_j
        if len(ii):
            dv = dw[ii] - dw[jj]
            dd = np.sqrt((dv ** 2).sum(1)) + 1e-30
            rs = self.rad[ii] + self.rad[jj]
            m_ = (dd < rs) & live[ii] & live[jj]
            ii, jj, dv, dd, rs = ii[m_], jj[m_], dv[m_], dd[m_], rs[m_]
        if len(ii):
            nrm = dv / dd[:, None]
            ci, cj = self.owner[ii], self.owner[jj]
            ri = dw[ii] - self.pos[ci]
            rj = dw[jj] - self.pos[cj]
            vi = self.vel[ci] + np.column_stack([-self.om[ci] * ri[:, 1],
                                                 self.om[ci] * ri[:, 0]])
            vj = self.vel[cj] + np.column_stack([-self.om[cj] * rj[:, 1],
                                                 self.om[cj] * rj[:, 0]])
            mi, mj = self.m[ci], self.m[cj]
            f = self._contact(nrm, vi - vj, rs - dd, kn, mi * mj / (mi + mj))
            self._accumulate(F, T, ii, f, ri)
            self._accumulate(F, T, jj, -f, rj)

        # 원판-체선
        d2 = dw[:, None, :] - np.column_stack([self.wire_x,
                                               np.zeros_like(self.wire_x)])[None]
        dist2 = np.sqrt((d2 ** 2).sum(-1)) + 1e-30
        rs2 = self.rad[:, None] + self.wire_r          # (M,1) 브로드캐스트
        ok2 = (dist2 < rs2) & live[:, None]
        ii, kk = np.where(ok2)
        if len(ii):
            nrm = d2[ii, kk] / dist2[ii, kk][:, None]
            ci = self.owner[ii]
            ri = dw[ii] - self.pos[ci]
            vi = self.vel[ci] + np.column_stack([-self.om[ci] * ri[:, 1],
                                                 self.om[ci] * ri[:, 0]])
            f = self._contact(nrm, vi, self.rad[ii] + self.wire_r - dist2[ii, kk],
                              kn, self.m[ci])        # 벽·체선은 무한질량
            self._accumulate(F, T, ii, f, ri)

        # 원판-측벽
        for wall, sign in ((0.0, 1.0), (c["width"], -1.0)):
            gap = sign * (dw[:, 0] - wall)
            hit = (gap < self.rad) & live
            ii = np.where(hit)[0]
            if len(ii):
                nrm = np.column_stack([np.full(len(ii), sign),
                                       np.zeros(len(ii))])
                ci = self.owner[ii]
                ri = dw[ii] - self.pos[ci]
                vi = self.vel[ci] + np.column_stack([-self.om[ci] * ri[:, 1],
                                                     self.om[ci] * ri[:, 0]])
                f = self._contact(nrm, vi, self.rad[ii] - gap[ii], kn, self.m[ci])
                self._accumulate(F, T, ii, f, ri)

        # 중력 + 가진 관성력
        a_vib = -c["gamma"] * G * math.sin(2 * math.pi * c["freq"] * self.t)
        F[:, 1] += self.m * (-G + a_vib)

        m = self.m[:, None]
        self.vel += F / m * self.dt
        self.om += T / self.Iz * self.dt
        self.vel[~self.alive] = 0.0
        self.om[~self.alive] = 0.0
        self.pos += self.vel * self.dt
        self.th += self.om * self.dt
        self.t += self.dt

        passed = self.alive & (self.pos[:, 1] < -3.0 * c["aperture"])
        self.t_exit[passed] = self.t
        self.alive[passed] = False
        return int(passed.sum())


def run(out_npz, cfg=None, sample_every=2000, verbose=True):
    """해석을 돌리고 궤적을 저장한다. 렌더링은 분리해 두어 재실행이 싸다."""
    s = Sieve2D(cfg)
    frames_pos, frames_th, frames_alive, times = [], [], [], []
    for k in range(s.n_steps):
        s.step()
        if k % sample_every == 0:
            frames_pos.append(s.pos.copy())
            frames_th.append(s.th.copy())
            frames_alive.append(s.alive.copy())
            times.append(s.t)
            if verbose and k % (sample_every * 50) == 0:
                print(f"  {k/s.n_steps*100:5.1f} %  t={s.t*1e3:6.1f} ms  "
                      f"통과 {int((~s.alive).sum()):3d}/{len(s.m)}", flush=True)
    np.savez_compressed(
        out_npz,
        pos=np.array(frames_pos), th=np.array(frames_th),
        alive=np.array(frames_alive), times=np.array(times),
        width=s.width, ar=s.ar, owner=s.owner, off=s.off, rad=s.rad,
        max_overlap=s.max_overlap,
        color=s.color, name=s.name, wire_x=s.wire_x, wire_r=s.wire_r,
        t_exit=s.t_exit, cfg=json.dumps({k: v for k, v in s.cfg.items()}),
        dt=s.dt, n_steps=s.n_steps)
    return s


def summary(npz_path):
    """통과 성적을 물질별로 집계 — sieve_sim 의 확률 모델과 대조하기 위한 것."""
    z = np.load(npz_path, allow_pickle=True)
    name, width, t_exit = z["name"], z["width"], z["t_exit"]
    ar = z["ar"]
    vol = math.pi / 6.0 * (width * ar) * width ** 2
    rho = np.array([MATERIAL[n]["rho"] for n in name])
    mass = vol * rho
    passed = ~np.isnan(t_exit)
    out = {}
    for nm in sorted(set(name.tolist())):
        sel = name == nm
        out[nm] = dict(
            n=int(sel.sum()),
            passed_n=int((sel & passed).sum()),
            passed_mass=float(mass[sel & passed].sum() / mass[sel].sum()),
        )
    ap = float(json.loads(str(z["cfg"]))["aperture"])
    fine, over = width < ap, width > ap
    out["_진단"] = dict(
        max_overlap_um=round(float(z["max_overlap"]) * 1e6, 3),
        overlap_vs_aperture_pct=round(float(z["max_overlap"]) / ap * 100, 2),
        oversize_passed_pct=round(float(passed[over].mean() * 100), 2) if over.sum() else 0.0,
    )
    out["_전체"] = dict(
        n=int(len(name)), passed_n=int(passed.sum()),
        passed_mass=float(mass[passed].sum() / mass.sum()),
        fine_passed=float((passed & fine).sum() / max(fine.sum(), 1)),
    )
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="체분리 DEM")
    ap.add_argument("-o", "--out", default="sim_out/sieve_dem.npz")
    ap.add_argument("--cycles", type=float, default=DEFAULTS["cycles"])
    ap.add_argument("--particles", type=int, default=DEFAULTS["n_particles"])
    ap.add_argument("--sample-every", type=int, default=2000)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    run(a.out, cfg=dict(cycles=a.cycles, n_particles=a.particles),
        sample_every=a.sample_every)
    for k, v in summary(a.out).items():
        print(f"  {k:12s} {v}")
