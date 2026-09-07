"""조밀행렬 선형대수 — 표준 라이브러리만 쓴다.

이 저장소의 시험은 **의존성 없이** 돈다. `python -m unittest discover`
한 줄이 빈 인터프리터에서 그대로 돌아가는 것이 지금까지 지켜 온 성질이고,
numpy 가 필요한 것(flotation_sim)은 `simulation` 부가의존으로 격리해
전용 CI 잡에서만 돌린다.

구조·열해석을 numpy 로 짰다가 그 성질을 깼다 — CI 의 unittest 잡은 아무것도
설치하지 않으므로 세 파이썬 버전에서 전부 import 에서 죽었다. 해석은
`flotation_sim` 같은 선택 도구가 아니라 부품 카탈로그가 바뀔 때마다 다시
풀려야 하는 **핵심 도구**라서, 격리하는 대신 의존성을 없앴다. 설계 검토는
사무실 아무 노트북에서나 `python3 tools/analysis_structural.py` 로 열려야 한다.

필요한 것은 넷뿐이다:

    부분추축 LU        변위 풀이 · Guyan 축약의 다중우변
    삼중대각 Thomas    1차원 열전도 (therm.py 가 직접 쓴다)
    역부분공간 반복    최소 고유치 몇 개 — 고유진동수
    순환 야코비        위에서 나오는 작은 대칭 고유문제

행렬은 **리스트의 리스트**다. 최대 계가 143 자유도라 조밀행렬로 충분하다.
"""

from __future__ import annotations

import math


# ── 기본 ─────────────────────────────────────────────────────────────
def zeros(n: int, m: int | None = None):
    return [0.0] * n if m is None else [[0.0] * m for _ in range(n)]


def eye(n: int):
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def matvec(A, x):
    return [sum(a * b for a, b in zip(row, x)) for row in A]


def matmul(A, B):
    """A(n×k) · B(k×m). B 를 열 단위로 훑지 않도록 전치해서 돈다."""
    Bt = list(zip(*B))
    return [[sum(a * b for a, b in zip(row, col)) for col in Bt] for row in A]


def transpose(A):
    return [list(c) for c in zip(*A)]


def sub_matrix(A, rows, cols):
    return [[A[i][j] for j in cols] for i in rows]


# ── LU 분해 (부분추축) ───────────────────────────────────────────────
def lu_factor(A):
    """제자리 LU. (LU, 추축순열) 을 돌려준다.

    추축을 안 하면 강성행렬의 0 대각(구속 제거 뒤에도 남을 수 있다)에서
    바로 나눗셈 오류가 난다. 대칭 양정치라도 부분추축은 공짜에 가깝다.
    """
    n = len(A)
    LU = [list(row) for row in A]
    piv = list(range(n))
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(LU[i][k]))
        if abs(LU[p][k]) < 1e-300:
            raise ZeroDivisionError(f"특이행렬 — {k} 번 자유도가 구속되지 않았다")
        if p != k:
            LU[k], LU[p] = LU[p], LU[k]
            piv[k], piv[p] = piv[p], piv[k]
        rk, pk = LU[k], LU[k][k]
        for i in range(k + 1, n):
            ri = LU[i]
            f = ri[k] / pk
            if f:
                ri[k] = f
                for j in range(k + 1, n):
                    ri[j] -= f * rk[j]
            else:
                ri[k] = 0.0
    return LU, piv


def lu_solve(fac, b):
    LU, piv = fac
    n = len(LU)
    y = [b[piv[i]] for i in range(n)]
    for i in range(1, n):
        ri, s = LU[i], y[i]
        for j in range(i):
            s -= ri[j] * y[j]
        y[i] = s
    for i in range(n - 1, -1, -1):
        ri, s = LU[i], y[i]
        for j in range(i + 1, n):
            s -= ri[j] * y[j]
        y[i] = s / ri[i]
    return y


def solve(A, b):
    return lu_solve(lu_factor(A), b)


def solve_mat(A, B):
    """A·X = B 를 X 에 대해 푼다. B 는 n×m — 분해는 한 번만 한다."""
    fac = lu_factor(A)
    cols = list(zip(*B))
    X = [lu_solve(fac, list(c)) for c in cols]
    return transpose(X)


# ── 삼중대각 (Thomas) ────────────────────────────────────────────────
def thomas(a, b, c, d):
    """a 하부 · b 대각 · c 상부 · d 우변. 리스트를 받아 리스트를 낸다."""
    n = len(b)
    cp = [0.0] * n
    dp = [0.0] * n
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = [0.0] * n
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


# ── 대칭 고유문제 ────────────────────────────────────────────────────
def jacobi_eig(A, sweeps: int = 60, tol: float = 1e-14):
    """작은 대칭행렬의 전 고유쌍. (고유치 오름차순, 고유벡터 열) 을 낸다.

    순환 야코비 — m ≤ 10 정도에서만 쓴다. 큰 계는 아래 부분공간 반복이
    이것을 투영행렬에만 부른다.
    """
    n = len(A)
    a = [list(r) for r in A]
    V = eye(n)
    for _ in range(sweeps):
        off = math.sqrt(sum(a[i][j] ** 2
                            for i in range(n) for j in range(n) if i != j))
        if off < tol:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-300:
                    continue
                th = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1 if th >= 0 else -1) / (abs(th) + math.sqrt(th * th + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = V[k][p], V[k][q]
                    V[k][p] = c * vkp - s * vkq
                    V[k][q] = s * vkp + c * vkq
    vals = [a[i][i] for i in range(n)]
    order = sorted(range(n), key=lambda i: vals[i])
    return [vals[i] for i in order], [[V[r][i] for i in order] for r in range(n)]


def _orthonormalize(X):
    """수정 그람–슈미트. 열이 선형종속이면 그 열을 버린다."""
    n, m = len(X), len(X[0])
    cols = []
    for j in range(m):
        v = [X[i][j] for i in range(n)]
        for u in cols:
            d = sum(a * b for a, b in zip(u, v))
            for i in range(n):
                v[i] -= d * u[i]
        nrm = math.sqrt(sum(t * t for t in v))
        if nrm > 1e-10:
            cols.append([t / nrm for t in v])
    return [[c[i] for c in cols] for i in range(n)]


def eig_smallest(A, k: int = 3, iters: int = 300, tol: float = 1e-11):
    """대칭 양정치 A 의 **가장 작은** 고유치 k 개.

    역부분공간 반복이다. A 를 한 번 분해해 두고 X ← A⁻¹X 를 반복하면
    작은 고유치 쪽으로 수렴한다 — 고유진동수는 언제나 낮은 쪽이 관심사다.
    매 회 레일리–리츠로 투영해 회전시키면 부분공간 안에서 모드가 갈린다.

    출발 부분공간은 **결정적으로** 잡는다. 난수를 쓰면 같은 입력에서 같은
    답이 안 나오고, 그러면 생성된 문서가 실행할 때마다 달라진다.
    """
    n = len(A)
    m = min(n, max(k + 4, 2 * k))
    fac = lu_factor(A)
    X = [[1.0 if (i % m) == j else 0.0 for j in range(m)] for i in range(n)]
    X = _orthonormalize(X)
    prev = None
    for _ in range(iters):
        Z = transpose([lu_solve(fac, [X[i][j] for i in range(n)])
                       for j in range(len(X[0]))])
        X = _orthonormalize(Z)
        AX = matmul(A, X)
        Ar = matmul(transpose(X), AX)
        Ar = [[(Ar[i][j] + Ar[j][i]) / 2 for j in range(len(Ar))]
              for i in range(len(Ar))]
        vals, vecs = jacobi_eig(Ar)
        X = matmul(X, vecs)
        cur = vals[:k]
        if prev is not None and all(
                abs(a - b) <= tol * max(1.0, abs(b)) for a, b in zip(cur, prev)):
            return cur
        prev = cur
    return prev or []
