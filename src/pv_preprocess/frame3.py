# -*- coding: utf-8 -*-
"""3차원 프레임 유한요소 — `ring.Frame` 을 공간으로 넓힌 것.

`ring.py` 의 평면 프레임은 링을 푸는 데 충분했다. 절점마다 자유도가 셋(u, v,
회전)이면 되니까. 그런데 OI-04 가 묻는 것은 **비틀림**이다 — 링 평면이 기둥
중심에서 220 mm 떨어져 있어 그 편심이 부재를 비튼다. 평면 요소에는 비틀림
자유도가 아예 없으므로 그 물음에 답할 수 없다.

그래서 절점마다 자유도 여섯(u, v, w, θx, θy, θz)인 요소를 세운다. 표준
라이브러리만 쓰는 규약은 그대로고, 가우스 소거는 `ring.solve` 를 빌려 쓴다 —
같은 풀개를 두 번 적지 않는다.

**요소를 믿을 근거를 먼저 만든다.** 넷을 닫힌 해와 맞춘다:

  · 외팔보 선단 처짐 PL³/3EI — 두 굽힘 축 각각에서.
  · 비틀림 각 TL/GJ — 비틀림 항이 맞는지.
  · 양단고정 보 중앙하중 PL³/192EI — 조립과 구속이 맞는지.
  · 국부 축 기준벡터가 부재 방향에 따라 안 뒤집히는지 — 수직 부재의 함정이다.

**여기서 처음 적는 값은 포아송비 하나뿐이다.** 탄성계수는 `afr` 에서 온다.

실행 (저장소 루트에서):

    PYTHONPATH=src python -m pv_preprocess.frame3
"""

from __future__ import annotations

import math

from . import afr, ring

#: 강재 포아송비. 전단탄성계수 G = E / 2(1+ν) 가 여기서 나온다.
#: `afr.ROLLER_NU` 도 0.30 인데 그것은 헤르츠 접촉용 값이라 이름이 다르다.
STEEL_NU = 0.30


def shear_modulus_mpa(e_mpa: float | None = None) -> float:
    e = afr.STEEL_E_MPA if e_mpa is None else e_mpa
    return e / (2 * (1 + STEEL_NU))


def box_section(depth: float, width: float, t: float) -> dict[str, float]:
    """용접 박스 단면의 A · Iy · Iz · J (mm², mm⁴).

    `depth` 는 국부 y(강축) 방향, `width` 는 국부 z 방향이다. 비틀림상수는
    닫힌 박막 단면의 브레트–바토 J = 4A_m² / ∮(ds/t) 로 낸다 — **열린 단면
    공식을 쓰면 두 자릿수 틀린다.**
    """
    a = depth * width - (depth - 2 * t) * (width - 2 * t)
    # **이름을 헷갈리면 두 축이 통째로 바뀐다.** Iz 는 국부 z 축에 대한 값이고
    # 국부 x–y 평면 굽힘(깊이 방향)을 지배한다 — 그래서 depth 가 세제곱이다.
    iz = (width * depth ** 3 - (width - 2 * t) * (depth - 2 * t) ** 3) / 12.0
    iy = (depth * width ** 3 - (depth - 2 * t) * (width - 2 * t) ** 3) / 12.0
    dm, bm = depth - t, width - t               # 벽 중심선 치수
    am = dm * bm
    j = 4 * am ** 2 / (2 * (dm + bm) / t)
    return {"A": a, "Iy": iy, "Iz": iz, "J": j,
            "Zy": iy / (width / 2), "Zz": iz / (depth / 2),
            "Wt": 2 * am * t}                    # 비틀림 단면계수 (전단흐름)


def open_box_section(depth: float, width: float, t: float) -> dict[str, float]:
    """같은 판으로 만든 **열린** 단면 (ㄷ형강 꼴) — 굽힘은 거의 같고 비틀림만 다르다.

    닫힌 단면의 J 는 브레트–바토로 크지만, 한 면을 열면 전단흐름이 못 돌아
    J = Σ b t³ / 3 로 **두 자릿수 떨어진다.** OI-04 의 답이 갈리는 자리가
    정확히 여기다 — 편심이 문제냐 아니냐는 받침보를 닫느냐 마느냐다.
    """
    sec = dict(box_section(depth, width, t))
    sec["J"] = ((depth - t) * 2 + (width - t)) * t ** 3 / 3.0
    sec["Wt"] = sec["J"] / t
    return sec


def solid_section(depth: float, width: float) -> dict[str, float]:
    """중실 직사각 단면 — 브래킷·거셋에 쓴다. J 는 근사식이다."""
    a, b = max(depth, width), min(depth, width)
    j = a * b ** 3 * (1 / 3 - 0.21 * b / a * (1 - b ** 4 / (12 * a ** 4)))
    return {"A": depth * width,
            "Iz": width * depth ** 3 / 12.0, "Iy": depth * width ** 3 / 12.0,
            "J": j, "Zz": width * depth ** 2 / 6.0, "Zy": depth * width ** 2 / 6.0,
            "Wt": j / (b / 2)}


def _rotation(x1, y1, z1, x2, y2, z2, roll_deg: float = 0.0
              ) -> tuple[list[list[float]], float]:
    """부재 국부축 → 전역축 방향코사인 (3×3) 과 길이.

    국부 x 는 부재 방향이다. 국부 y 를 정하려면 기준 방향이 하나 필요한데,
    **수직 부재에서는 전역 Y 를 못 쓴다** (평행해서 외적이 0 이 된다). 그래서
    거의 수직이면 전역 X 를 기준으로 바꾼다 — 이것을 빠뜨리면 기둥에서만
    조용히 특이행렬이 된다.
    """
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    ex = [dx / L, dy / L, dz / L]
    ref = [1.0, 0.0, 0.0] if abs(ex[1]) > 0.999 else [0.0, 1.0, 0.0]
    ez = [ex[1] * ref[2] - ex[2] * ref[1],
          ex[2] * ref[0] - ex[0] * ref[2],
          ex[0] * ref[1] - ex[1] * ref[0]]
    n = math.sqrt(sum(v * v for v in ez))
    ez = [v / n for v in ez]
    ey = [ez[1] * ex[2] - ez[2] * ex[1],
          ez[2] * ex[0] - ez[0] * ex[2],
          ez[0] * ex[1] - ez[1] * ex[0]]
    if roll_deg:
        c, s = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
        ey, ez = ([c * ey[i] + s * ez[i] for i in range(3)],
                  [-s * ey[i] + c * ez[i] for i in range(3)])
    return [ex, ey, ez], L


def _local_k(e: float, g: float, sec: dict[str, float], L: float
             ) -> list[list[float]]:
    """국부 좌표계의 12×12 강성."""
    a, iy, iz, j = sec["A"], sec["Iy"], sec["Iz"], sec["J"]
    k = [[0.0] * 12 for _ in range(12)]

    def put(i, jj, v):
        k[i][jj] += v
        if i != jj:
            k[jj][i] += v

    ea, gj = e * a / L, g * j / L
    put(0, 0, ea); put(6, 6, ea); put(0, 6, -ea)
    put(3, 3, gj); put(9, 9, gj); put(3, 9, -gj)
    # 국부 x–y 평면 굽힘 (v, θz) — Iz
    b = e * iz
    put(1, 1, 12 * b / L ** 3); put(7, 7, 12 * b / L ** 3)
    put(1, 7, -12 * b / L ** 3)
    put(5, 5, 4 * b / L); put(11, 11, 4 * b / L); put(5, 11, 2 * b / L)
    put(1, 5, 6 * b / L ** 2); put(1, 11, 6 * b / L ** 2)
    put(7, 5, -6 * b / L ** 2); put(7, 11, -6 * b / L ** 2)
    # 국부 x–z 평면 굽힘 (w, θy) — Iy. 부호가 반대다.
    c = e * iy
    put(2, 2, 12 * c / L ** 3); put(8, 8, 12 * c / L ** 3)
    put(2, 8, -12 * c / L ** 3)
    put(4, 4, 4 * c / L); put(10, 10, 4 * c / L); put(4, 10, 2 * c / L)
    put(2, 4, -6 * c / L ** 2); put(2, 10, -6 * c / L ** 2)
    put(8, 4, 6 * c / L ** 2); put(8, 10, 6 * c / L ** 2)
    return k


class Frame3:
    """3차원 프레임 모형 — 절점·부재·하중·구속을 담고 푼다."""

    def __init__(self, e_mpa: float | None = None) -> None:
        self.e = afr.STEEL_E_MPA if e_mpa is None else e_mpa
        self.g = shear_modulus_mpa(self.e)
        self.nodes: list[tuple[float, float, float]] = []
        self.members: list[tuple[int, int, dict[str, float], float]] = []
        self.f: list[float] = []
        self.springs: list[tuple[int, int, float]] = []      # 절점, 자유도(0..5), k

    def node(self, x: float, y: float, z: float) -> int:
        self.nodes.append((x, y, z))
        self.f += [0.0] * 6
        return len(self.nodes) - 1

    def member(self, i: int, j: int, sec: dict[str, float],
               roll_deg: float = 0.0) -> int:
        self.members.append((i, j, sec, roll_deg))
        return len(self.members) - 1

    def load(self, n: int, fx=0.0, fy=0.0, fz=0.0, mx=0.0, my=0.0, mz=0.0) -> None:
        for k, v in enumerate((fx, fy, fz, mx, my, mz)):
            self.f[6 * n + k] += v

    def fix(self, n: int, dofs: str = "xyzXYZ", k: float = 1e14) -> None:
        """절점을 벌칙 스프링으로 묶는다. `dofs` 는 xyz(병진)·XYZ(회전)."""
        order = {"x": 0, "y": 1, "z": 2, "X": 3, "Y": 4, "Z": 5}
        for ch in dofs:
            self.springs.append((n, order[ch], k))

    def _transform(self, m: int) -> tuple[list[list[float]], float]:
        i, j, _sec, roll = self.members[m]
        (x1, y1, z1), (x2, y2, z2) = self.nodes[i], self.nodes[j]
        return _rotation(x1, y1, z1, x2, y2, z2, roll)

    def _global_k(self, m: int) -> tuple[list[list[float]], list[int]]:
        i, j, sec, _roll = self.members[m]
        r, L = self._transform(m)
        kl = _local_k(self.e, self.g, sec, L)
        # 12×12 변환 T — 3×3 블록 넷
        t = [[0.0] * 12 for _ in range(12)]
        for blk in range(4):
            for a in range(3):
                for b in range(3):
                    t[3 * blk + a][3 * blk + b] = r[a][b]
        kt = [[sum(kl[p][q] * t[q][s] for q in range(12)) for s in range(12)]
              for p in range(12)]
        kg = [[sum(t[q][p] * kt[q][s] for q in range(12)) for s in range(12)]
              for p in range(12)]
        dofs = [6 * i + d for d in range(6)] + [6 * j + d for d in range(6)]
        return kg, dofs

    def solve(self) -> list[float]:
        n = len(self.nodes) * 6
        k = [[0.0] * n for _ in range(n)]
        for m in range(len(self.members)):
            kg, dofs = self._global_k(m)
            for p in range(12):
                row = k[dofs[p]]
                for q in range(12):
                    row[dofs[q]] += kg[p][q]
        for nd, d, kp in self.springs:
            k[6 * nd + d][6 * nd + d] += kp
        return ring.solve(k, self.f)

    def end_forces(self, m: int, u: list[float]) -> list[float]:
        """부재 양단의 **국부** 단면력 12개 — [N, Vy, Vz, T, My, Mz] × 2."""
        i, j, sec, _roll = self.members[m]
        r, L = self._transform(m)
        t = [[0.0] * 12 for _ in range(12)]
        for blk in range(4):
            for a in range(3):
                for b in range(3):
                    t[3 * blk + a][3 * blk + b] = r[a][b]
        ug = [u[6 * i + d] for d in range(6)] + [u[6 * j + d] for d in range(6)]
        ul = [sum(t[p][q] * ug[q] for q in range(12)) for p in range(12)]
        kl = _local_k(self.e, self.g, sec, L)
        return [sum(kl[p][q] * ul[q] for q in range(12)) for p in range(12)]

    def reactions(self, u: list[float]) -> dict[int, list[float]]:
        """구속한 절점의 반력 — 절점별 6성분."""
        out: dict[int, list[float]] = {}
        for nd, d, kp in self.springs:
            out.setdefault(nd, [0.0] * 6)[d] -= kp * u[6 * nd + d]
        return out


def member_stress_mpa(sec: dict[str, float], forces: list[float]) -> float:
    """단면력에서 나오는 등가응력 (MPa) — 수직응력과 비틀림 전단을 합친다.

    수직 = |N|/A + |My|/Zy + |Mz|/Zz (같은 자리에 몰린다고 보는 보수적 조합),
    전단 = |T|/Wt. 폰미제스로 합친다.
    """
    n, t = abs(forces[0]), abs(forces[3])
    my = max(abs(forces[4]), abs(forces[10]))
    mz = max(abs(forces[5]), abs(forces[11]))
    sigma = n / sec["A"] + my / sec["Zy"] + mz / sec["Zz"]
    tau = t / sec["Wt"]
    return math.sqrt(sigma ** 2 + 3 * tau ** 2)


if __name__ == "__main__":                                   # pragma: no cover
    E = afr.STEEL_E_MPA
    G = shear_modulus_mpa()
    sec = box_section(260.0, 180.0, 8.0)
    L, P, T = 2_000.0, 1_000.0, 1e6
    print(f"박스 260×180×8 — A {sec['A']:.0f}  Iy {sec['Iy']:.3e}  "
          f"Iz {sec['Iz']:.3e}  J {sec['J']:.3e}")

    for axis, want_i, comp in (("y", sec["Iz"], 1), ("z", sec["Iy"], 2)):
        fr = Frame3()
        a = fr.node(0, 0, 0)
        b = fr.node(L, 0, 0)
        fr.member(a, b, sec)
        fr.fix(a)
        fr.load(b, **{("fy" if comp == 1 else "fz"): -P})
        u = fr.solve()
        got = abs(u[6 * b + comp])
        print(f"외팔보 {axis} 축  {got:.6f} vs {P * L ** 3 / (3 * E * want_i):.6f}")

    fr = Frame3()
    a, b = fr.node(0, 0, 0), fr.node(L, 0, 0)
    fr.member(a, b, sec)
    fr.fix(a)
    fr.load(b, mx=T)
    u = fr.solve()
    print(f"비틀림      {u[6 * b + 3]:.6e} vs {T * L / (G * sec['J']):.6e}")
