#!/usr/bin/env python3
"""칼날 인서트 날끝 — 쐐기각 · 호닝 · 랜드 · 릴리프 · 코 · 구멍 · 공차 (D-502).

인서트는 지금까지 판재 외형(PL 8 × 60)으로만 적혀 있었다. 몇 도로 깎는지,
랜드 뒤를 얼마나 물리는지, 나사가 어디 드는지가 없으면 제작사는 칼날을
깎을 수 없다. 값은 콘솔 뿌리 상수(KNIFE_*)에 들고, 이 모듈은 그 값이
해석의 한계 안에 드는지 풀어 D-502 도면과 부품 카탈로그에 넘긴다.

쐐기각은 수직 반력비 V/H 의 상한을 정한다. 떼어 낸 층은 레이크면(윗면)을
타고 오르며 칼날을 누른다. 레이크면이 수평에서 α 서 있고 층과의 마찰계수가
μ (마찰각 φ = atan μ) 이면 그 접촉력이 칼날에 주는 수직/수평 비는

    V/H = (cos α − μ sin α) / (sin α + μ cos α) = cot(α + φ)

이다. 칼끝에서 계면을 끊는 힘은 수평이라 V/H 를 줄이기만 하므로 위 값이
상한이다. 층이 닿는 다른 면이 α 보다 가파르면 그 면의 몫은 더 작다 — 그래서
홀더 앞면은 레이크면보다 앞으로 나오지 않는다(코). 이 상한을 두 한계에 댄다.

  · 구조해석이 전제한 포락 V/H ≤ 1 (S10 · S14 의 입력) → α + φ ≥ 45°
  · 유리 한계 S14 — V/H × 랜드 폭 ≤ 2.14 mm. 랜드가 공차 상한일 때도.

마찰은 재지 않았다. 고온 EVA 는 고무상이라 강에 대해 보통 0.3 을 넘지만 V/H 는
마찰이 작을수록 나빠지므로 하한을 0.2 로 잡는다. 0.2 에서 포락 1 을 지키는 가장
작은 5° 눈금이 35° 다. 그 각이면 마찰이 0.031 까지 떨어져도 유리는 S14 안이다.
각을 더 세우면 레이크면이 받는 추력 몫이 늘고 층이 더 급히 꺾이므로 필요한
만큼만 세운다. 파일럿 PT-10 쿠폰이 같은 각으로 V/H 를 재서 이 가정을 닫는다.

모듈 머리에서는 console_consts 만 부른다 — parts.py 가 구멍 배치를 여기서 읽고,
fab_spec → parts 가 이미 해석 쪽에서 불리므로 해석 모듈은 함수 안에서 늦게 부른다.

    python3 tools/knife_edge.py            # 근거 보고
    python3 tools/knife_edge.py --write    # 콘솔의 EDGE-DATA 블록을 바꿔 넣는다
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from console_consts import const as c  # noqa: E402

CONSOLE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "drawings" / "pv-delamination-3d.html"
OPEN = "/* ⟨EDGE-DATA⟩ tools/knife_edge.py 가 찍는다 — 손으로 고치지 않는다 */"
CLOSE = "/* ⟨/EDGE-DATA⟩ */"

# ── 뿌리 상수 (mm · °) ───────────────────────────────────────────────────
T = c("KNIFE_INS_T") * 1000                 # 8   인서트 두께 — 랜드면에서 취부면까지
W = c("KNIFE_INS_W") * 1000                 # 60  인서트 폭 (박리 방향)
ALPHA = c("KNIFE_WEDGE")                    # 35° 쐐기각 — 레이크면과 랜드 사이
NOSE = c("KNIFE_NOSE") * 1000               # 12  홀더 앞면이 칼끝에서 물러난 거리
RELIEF = c("KNIFE_RELIEF") * 1000           # 0.3 랜드 뒤 밑면 물림 (완성)
HONE = c("KNIFE_HONE") * 1000               # 0.02 날끝 호닝 반경
LAND = c("KNIFE_LAND") * 1000               # 1.5 밑면 랜드 (완성)
GAP = c("KM_GAP") * 1000                    # 2   이웃 홀더 옆 틈
LAP = c("KNIFE_LAP") * 1000                 # 15  계단 이음 겹침
CENTER = c("KNIFE_CENTER") * 1000           # 300 중앙 인서트 길이
STEP_W = c("KNIFE_STEP_W") * 1000           # 200 계단 조각 폭
RISE = c("KNIFE_RISE") * 1000               # 80  계단 높이 — 바깥 조각이 뒤로 물러난 거리
CASS_W = c("CASS_W") * 1000                 # 120 조각 단면 (코 + 홀더 몸통)
CASS_H = c("CASS_H") * 1000                 # 90  홀더 높이
TRAVEL = c("KM_TRAVEL") * 1000              # 1.5 모듈 들림 ±
ROLL = c("KM_ROLL")                         # 0.5° 모듈 롤 ±
T_KNIFE = c("T_KNIFE")                      # 200 ℃ 칼날 가동 온도

# ── 이 모듈이 정하는 값 ────────────────────────────────────────────────
MU_MIN = 0.20            # 층(고온 EVA) ↔ 연삭 SKD11 마찰 하한 — 재지 않았다. 작을수록 V/H 가 나쁘다
ALPHA_STEP = 5           # 연삭 각도 눈금 — 공구 지그가 5° 단위다
ALPHAS = (25, 30, 35, 40, 45)
HONE_TOL = 0.01          # 호닝 R 0.02 ± 0.01
DEPTH_BUDGET = 0.15      # mm 칼끝 깊이 예산 (CAL-001 S1 · S10 · S12)
LAND_TOL = 0.10          # 완성 랜드 1.5 ± 0.1
GRIND_STOCK = 0.10       # 랜드면 연삭 여유 — MC-401 에서 일곱 조각을 잠근 채 한 평면으로 연삭한다
LAND_SUPPLY_TOL = 0.02   # 납품 랜드 폭 공차
TIP_PLANE = 0.02         # 일곱 랜드 동일 평면 (MC-401 연삭 직후) — ±0.05 예산의 나머지는 착좌다
EDGE_STRAIGHT = 0.01     # 날끝 진직도 (인서트 한 개)
WEDGE_TOL = 0.5          # 쐐기각 ± °
TEMPER_C = 520           # 고온 뜨임 2회 — 가동 200 ℃ 에서 더 뜨임되지 않게
HRC = "58~60"
CRYO_C = -80             # 심랭 — 잔류 오스테나이트가 가동 중 변태하면 랜드 평면이 틀어진다
# 나사 — ISO 10642 접시머리 육각구멍붙이 · 10.9. 인서트 쪽은 관통 접시구멍, 나사산은 홀더
# 밑판(t6)의 헬리코일에 든다 — SKD11 에 탭을 내지 않는다.
SCREW = "M6"
SCREW_AS = 20.1          # mm² 인장 응력 단면적 (ISO 898-1)
HOLE_D = 6.6             # 관통 구멍 (ISO 273 중급)
CSK_D = 12.4             # 접시 90° 지름 — 머리 dk 12
CSK_K = {"M6": 3.72, "M10": 6.2}   # 접시머리 높이 k (ISO 10642 최대)
RECESS = 0.2             # 머리가 릴리프면보다 묻히는 깊이
HOLE_PITCH = 100.0
HOLE_END = 50.0          # 끝에서 첫 구멍까지
END_MIN = 40.0           # 마지막 구멍에서 홀더 몸통 끝까지의 하한 — 구멍 지름의 6배
MU_SLIP = 0.20           # 연삭 강재 ↔ 무도장 홀더 밑면 미끄럼 계수 (EN 1090-2 D 급)
SLIP_RULE = 2.0          # 이 저장소의 2배 규칙 — 카세트 클램프와 같은 잣대
LAP_STEP = 4.0           # 계단 인서트 겹침 끝 윗면 따냄 깊이


# ── 쐐기각 ─────────────────────────────────────────────────────────────
def up(v: float, n: int) -> float:
    """드는 값(마찰 하한 따위)은 올려 적는다 — 0.0301 을 0.03 이라 적으면 0.03 에서 한계를 넘는다."""
    k = 10 ** n
    return math.ceil(v * k - 1e-9) / k


def vh_bound(alpha: float, mu: float) -> float:
    """레이크면 접촉이 칼날에 주는 V/H 의 상한 — cot(α + atan μ)."""
    return 1 / math.tan(math.radians(alpha) + math.atan(mu))


def mu_for(alpha: float, vh: float) -> float:
    """V/H 상한을 vh 에 묶는 데 드는 최소 마찰계수 (0 이면 마찰이 없어도 된다)."""
    need = math.atan(1 / vh) - math.radians(alpha)
    return max(0.0, math.tan(need))


def thrust_share(alpha: float, mu: float) -> float:
    """레이크면 접촉력 N 한 단위가 만드는 수평 저항 — sin α + μ cos α."""
    a = math.radians(alpha)
    return math.sin(a) + mu * math.cos(a)


def rake_run(alpha: float = ALPHA, t: float = T) -> float:
    """레이크면의 수평 길이 — 인서트 두께를 α 로 오르는 거리."""
    return t / math.tan(math.radians(alpha))


def limits() -> dict:
    """쐐기각이 대는 두 한계 — 해석의 포락과 유리 우력."""
    import analysis_structural as ST
    import glass_follow as GF
    arm_max = GF.SIG_GL * GF.T_GLASS ** 2 / (3 * GF.F_W)      # V/H × 랜드 (mm) 의 상한 — S14
    return dict(vh_env=ST.V_RATIO, arm_max=arm_max, land_max=LAND + LAND_TOL,
                vh_glass=arm_max / (LAND + LAND_TOL))


def choose_alpha(mu_min: float = MU_MIN) -> int:
    """마찰 하한에서 포락 V/H 를 지키는 가장 작은 눈금 각."""
    env = limits()["vh_env"]
    a = ALPHA_STEP
    while vh_bound(a, mu_min) > env + 1e-12:
        a += ALPHA_STEP
    return a


def table() -> list[dict]:
    """후보 각마다 — 레이크 길이 · V/H 상한 · 드는 마찰 · 추력 몫."""
    lim = limits()
    ref = thrust_share(ALPHA, 0.3)
    rows = []
    for a in ALPHAS:
        rows.append(dict(
            a=a, run=rake_run(a), vh=vh_bound(a, MU_MIN),
            mu_env=mu_for(a, lim["vh_env"]), mu_glass=mu_for(a, lim["vh_glass"]),
            share=thrust_share(a, 0.3) / ref))
    return rows


# ── 랜드 · 릴리프 · 호닝 ────────────────────────────────────────────────
def land_supply() -> float:
    """납품 랜드 폭 — 연삭 여유를 반쯤 쓴 자리에서 완성 1.5 가 되게."""
    return round(LAND + GRIND_STOCK / 2 / math.tan(math.radians(ALPHA)), 2)


def land_final() -> tuple[float, float]:
    """MC-401 한 평면 연삭 뒤 랜드 폭의 범위.

    랜드면을 s 만큼 갈면 날끝이 레이크면을 따라 s / tan α 물러나고 랜드 뒤끝
    (릴리프 단) 은 그대로라 랜드가 그만큼 좁아진다. 조각마다 깎이는 양은 착좌
    높이에 따라 0 ~ 여유 사이다.
    """
    lo = land_supply() - LAND_SUPPLY_TOL - GRIND_STOCK / math.tan(math.radians(ALPHA))
    hi = land_supply() + LAND_SUPPLY_TOL
    return lo, hi


def relief_supply() -> float:
    """납품 릴리프 깊이 — 연삭 여유를 다 써도 완성 릴리프가 남게."""
    return RELIEF + GRIND_STOCK


def pitch_max() -> float:
    """뒤 밑면이 잔막에 닿기 전까지 모듈이 기울 수 있는 각 (°)."""
    return math.degrees(math.atan(RELIEF / (W - LAND - LAND_TOL)))


def hone_ratio() -> float:
    """호닝 반경 상한이 깊이 예산에서 차지하는 몫."""
    return (HONE + HONE_TOL) / DEPTH_BUDGET


# ── 구멍 · 나사 ────────────────────────────────────────────────────────
def hole_x() -> float:
    """구멍 줄 — 날끝에서 잰 거리. 홀더 밑판이 인서트를 누르는 띠(코 ~ 인서트 뒤끝)의 가운데."""
    return (NOSE + W) / 2


def _holes(body: float) -> tuple[float, ...]:
    """끝에서 50 부터 100 간격 — 홀더 몸통 끝까지 40 이 남는 데까지."""
    out, x = [], HOLE_END
    while x <= body - END_MIN + 1e-9:
        out.append(x)
        x += HOLE_PITCH
    return tuple(out)


def holes_center() -> tuple[float, ...]:
    """중앙 인서트 — 한 끝에서 잰 구멍 위치. 중앙 홀더 몸통은 인서트와 같은 300 이다."""
    return _holes(CENTER)


def holes_step() -> tuple[float, ...]:
    """계단 인서트 — **바깥 끝**에서 잰 구멍 위치. 안쪽 끝의 겹침 · 옆 틈 자리에는 없다."""
    return _holes(STEP_W - GAP)


def joint() -> dict:
    """인서트 ↔ 홀더 — 마찰만으로 추력을 받는가 (2배 규칙), 나사 전단은 여유로 둔다."""
    import fab_spec as F
    import knife_stepped as KS
    g = F.GRADES["10.9"]
    fp = 0.7 * g["fub"] * SCREW_AS / 1000                      # kN 설계 체결력 Fp,C
    slip = MU_SLIP * fp / F.GAMMA_M3                           # kN/개 미끄럼 내력
    shear = g["av"] * g["fub"] * SCREW_AS / F.GAMMA_M2 / 1000  # kN/개 나사부 전단
    out = dict(fp=fp, slip=slip, shear=shear, f_w=KS.F_W)
    for name, width, n in (("center", CENTER, len(holes_center())), ("step", STEP_W, len(holes_step()))):
        h = KS.F_W * width / 1000                              # kN — 새로 떼는 폭만 (겹침은 이미 떨어졌다)
        out[name] = dict(n=n, thrust=h, ratio=n * slip / h, shear_ratio=n * shear / h)
    return out


def under_head(size: str) -> float:
    """접시머리 밑에 남는 인서트 두께 — 릴리프면에서 머리를 묻은 뒤."""
    return T - RELIEF - RECESS - CSK_K[size]


# ── 이음 · 옆 틈 ───────────────────────────────────────────────────────
def gap_need() -> float:
    """이웃 홀더가 서로 반대로 구를 때 윗모서리가 다가오는 거리."""
    return 2 * CASS_H * math.sin(math.radians(ROLL))


def lap_clear() -> float:
    """겹침 끝 윗면과 안쪽 홀더 밑면 사이 — 두 모듈이 반대로 끝까지 떴을 때."""
    return LAP_STEP - 2 * TRAVEL


def lap_len() -> float:
    """계단 인서트가 제 홀더 밖으로 나간 길이 — 겹침 + 옆 틈."""
    return LAP + GAP


# ── 콘솔 블록 ─────────────────────────────────────────────────────────
def _r(v: float, n: int = 6) -> float:
    """도면이 다시 반올림하는 값은 여섯 자리로 넘긴다 — 두 번 반올림하면 틀린다.

    유리 한계 2.1445 를 셋째 자리에서 2.145 로 찍어 넘기면 도면이 둘째 자리에서
    2.15 로 올린다 (사양서 · 해석서는 2.14). 반올림은 표시하는 쪽에서 한 번만 한다.
    """
    return round(v, n)


def data() -> dict:
    lim = limits()
    j = joint()
    lo, hi = land_final()
    return dict(
        alpha=ALPHA, alpha_tol=WEDGE_TOL, mu_min=MU_MIN, vh_env=lim["vh_env"],
        arm_max=_r(lim["arm_max"]), land_max=_r(lim["land_max"], 2),
        vh=_r(vh_bound(ALPHA, MU_MIN)), mu_env=_r(mu_for(ALPHA, lim["vh_env"])),
        mu_glass=_r(mu_for(ALPHA, lim["vh_glass"])), run=_r(rake_run(), 2),
        rows=[{k: (_r(v) if isinstance(v, float) else v) for k, v in r.items()} for r in table()],
        hone=HONE, hone_tol=HONE_TOL, hone_ratio=_r(hone_ratio(), 2), budget=DEPTH_BUDGET,
        stock=GRIND_STOCK, land_supply=land_supply(), land_supply_tol=LAND_SUPPLY_TOL,
        land_lo=_r(lo, 2), land_hi=_r(hi, 2), land_tol=LAND_TOL,
        relief=RELIEF, relief_supply=_r(relief_supply(), 2), pitch=_r(pitch_max(), 2),
        tip_plane=TIP_PLANE, straight=EDGE_STRAIGHT,
        hole_x=hole_x(), hole_d=HOLE_D, csk_d=CSK_D, recess=RECESS, screw=SCREW,
        holes_center=list(holes_center()), holes_step=list(holes_step()),
        under_m6=_r(under_head("M6"), 2), under_m10=_r(under_head("M10"), 2),
        fp=_r(j["fp"], 2), slip=_r(j["slip"], 2), shear=_r(j["shear"], 2), mu_slip=MU_SLIP,
        center=dict(n=j["center"]["n"], thrust=_r(j["center"]["thrust"], 2), ratio=_r(j["center"]["ratio"], 2)),
        step=dict(n=j["step"]["n"], thrust=_r(j["step"]["thrust"], 2), ratio=_r(j["step"]["ratio"], 2)),
        lap_step=LAP_STEP, lap_len=lap_len(), lap_clear=_r(lap_clear(), 2),
        gap=GAP, gap_need=_r(gap_need(), 2), body=CASS_W - NOSE, step_body=STEP_W - GAP,
        temper=TEMPER_C, cryo=CRYO_C, hrc=HRC, t_knife=T_KNIFE,
    )


def js_block() -> str:
    return f"{OPEN}\n    const EDGE={json.dumps(data(), ensure_ascii=False, separators=(',', ':'))};\n    {CLOSE}"


def write() -> bool:
    s = CONSOLE.read_text(encoding="utf-8")
    i, j = s.index(OPEN), s.index(CLOSE) + len(CLOSE)
    new = s[:i] + js_block() + s[j:]
    if new != s:
        CONSOLE.write_text(new, encoding="utf-8")
    return new != s


def report() -> str:
    lim = limits()
    j = joint()
    lo, hi = land_final()
    L = [f"칼날 인서트 날끝 (D-502) — 쐐기 {ALPHA}° · 호닝 R {HONE:.2f} · 랜드 {LAND:.1f} · 릴리프 {RELIEF:.1f} · 코 {NOSE:.0f}",
         f"  포락 V/H ≤ {lim['vh_env']:.1f} · 유리 S14 V/H × 랜드 ≤ {lim['arm_max']:.3f} mm (랜드 상한 {lim['land_max']:.1f} → V/H ≤ {lim['vh_glass']:.3f})",
         f"  {'각':>4s} {'레이크':>7s} {'V/H(μ0.2)':>10s} {'포락 μ':>7s} {'유리 μ':>7s} {'추력몫':>7s}"]
    for r in table():
        L.append(f"  {r['a']:>3d}° {r['run']:7.1f} {r['vh']:10.3f} {up(r['mu_env'], 3):7.3f} {up(r['mu_glass'], 3):7.3f} {r['share']:7.3f}")
    L += [f"  선택 {choose_alpha()}° (마찰 하한 {MU_MIN}) · 코 {NOSE:.0f} ≥ 레이크 {rake_run():.2f}",
          f"  랜드 납품 {land_supply():.2f} ± {LAND_SUPPLY_TOL} · 연삭 여유 {GRIND_STOCK} → 완성 {lo:.2f} ~ {hi:.2f}",
          f"  릴리프 납품 {relief_supply():.1f} → 완성 ≥ {RELIEF:.1f} · 모듈 기울기 {pitch_max():.2f}° 까지 뒤 밑면이 뜬다",
          f"  구멍 x {hole_x():.0f} · 중앙 {holes_center()} · 계단 {holes_step()} (바깥 끝 기준) · {SCREW} 접시 Ø{CSK_D}",
          f"  접합 Fp,C {j['fp']:.2f} kN · 미끄럼 {j['slip']:.2f} kN/개 → 중앙 {j['center']['ratio']:.2f}배 · 계단 {j['step']['ratio']:.2f}배",
          f"  머리 밑 두께 M6 {under_head('M6'):.2f} · M10 {under_head('M10'):.2f}",
          f"  옆 틈 {GAP:.0f} ≥ {gap_need():.2f} · 겹침 끝 따냄 {LAP_STEP:.0f} → 간극 {lap_clear():.1f}"]
    return "\n".join(L)


if __name__ == "__main__":
    if "--write" in sys.argv:
        print("EDGE-DATA", "바꿈" if write() else "그대로")
    else:
        print(report())
