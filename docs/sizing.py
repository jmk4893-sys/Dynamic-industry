#!/usr/bin/env python3
"""다단 원형 스크린 + 에어석션 사이징 계산기.

docs/원형스크린-다단-설계.md 의 수치를 재현·재산출한다.
실측치가 확보되면 CONFIG 만 고쳐서 다시 돌리면 된다.

    python3 docs/sizing.py
"""
import math

# ── 설계 전제 (실측치로 치환할 것) ────────────────────────────────
CONFIG = {
    "feed_tph": 2.0,          # 정격 공급량 t/h
    "peak_factor": 1.5,       # 피크 배수
    "split": {                # 분획별 중량 분율
        "os_12mm": 0.08,
        "f_5_12mm": 0.12,
        "f_06_5mm": 0.35,
        "pan": 0.45,
    },
    # 데크: (명칭, 개구 mm, 기준 처리능력 t/h/m2)
    #   0.6mm 는 슬롯 메쉬 + 초음파 적용 기준 1.4, 각공이면 1.0
    "decks": [("Deck1", 12.0, 4.0), ("Deck2", 5.0, 2.5), ("Deck3", 0.6, 1.4)],
    # 후드: (태그, 개구 W m, 개구 H m, 면속도 m/s)
    "hoods": [("AS-01", 0.35, 0.15, 2.8),
              ("AS-02", 0.30, 0.13, 3.0),
              ("AS-03", 0.30, 0.13, 3.2)],
    "leak_factor": 1.5,       # 슈트/후드 누기
    "fan_margin": 1.25,       # 팬 여유
    "duct_velocity": 18.0,    # m/s, 필름 침강 방지 하한
    "fan_dp_mmaq": 300.0,
    "fan_eff": 0.65,
    "screen_area_factor": 0.90,  # 유효 스크린 면적 계수
}

RHO_AIR, G, MU = 1.2, 9.81, 1.8e-5


def vt_plate(rho_s, t_m, cd=1.3):
    """판상 입자 종말속도 [m/s]. 두께x밀도로만 결정되며 조각 크기에 무관."""
    return math.sqrt(2 * rho_s * t_m * G / (RHO_AIR * cd))


def vt_sphere(rho_s, d_m, iters=200):
    """구형 입자 종말속도 [m/s]. Cd 를 Re 에 대해 반복 수렴."""
    v = 1.0
    for _ in range(iters):
        re = max(RHO_AIR * v * d_m / MU, 1e-6)
        cd = 24 / re if re < 0.1 else (
            24 / re * (1 + 0.15 * re ** 0.687) + 0.42 / (1 + 42500 * re ** -1.16))
        v = math.sqrt(4 * G * d_m * (rho_s - RHO_AIR) / (3 * cd * RHO_AIR))
    return v


def deck_loads(cfg):
    """각 데크를 통과하는 피크 부하 [t/h]."""
    peak = cfg["feed_tph"] * cfg["peak_factor"]
    s = cfg["split"]
    return [peak,
            peak * (1 - s["os_12mm"]),
            peak * (1 - s["os_12mm"] - s["f_5_12mm"])]


def report(cfg=CONFIG):
    print("=" * 68)
    print("1. 종말속도 — 커트 속도 결정 근거")
    print("=" * 68)
    for name, rho, t in [("백시트 0.2mm", 1400, 0.2e-3),
                         ("백시트 0.3mm", 1400, 0.3e-3),
                         ("EVA 필름 0.45mm", 950, 0.45e-3),
                         ("유리 박편 0.15mm", 2500, 0.15e-3),
                         ("구리 리본 0.15mm", 8900, 0.15e-3),
                         ("구리 리본 0.20mm", 8900, 0.2e-3)]:
        print(f"  {name:18s} rho*t={rho*t:6.3f} kg/m2   vt={vt_plate(rho, t):5.2f} m/s")
    print("  --- 입상 유리 (미분 손실 한계) ---")
    for d_mm in (0.1, 0.2, 0.3, 0.5, 0.6, 1.0, 2.0):
        print(f"  유리 d={d_mm:4.1f} mm      {'':18s}vt={vt_sphere(2500, d_mm/1000):5.2f} m/s")

    print()
    print("=" * 68)
    print("2. 스크린 직경")
    print("=" * 68)
    need = 0.0
    for (name, ap, cap), load in zip(cfg["decks"], deck_loads(cfg)):
        area = load / cap
        need = max(need, area)
        print(f"  {name} ({ap} mm)  통과부하={load*1000:6.0f} kg/h  "
              f"능력={cap:.1f} t/h/m2 -> 소요 {area:.2f} m2")
    print(f"\n  지배 데크 소요면적 = {need:.2f} m2")
    for d_mm in (1200, 1500, 1800, 2000):
        area = math.pi / 4 * (d_mm / 1000) ** 2 * cfg["screen_area_factor"]
        print(f"    Ø{d_mm} mm -> 유효 {area:.2f} m2  (여유율 {area/need*100-100:+.0f}%)")

    print()
    print("=" * 68)
    print("3. 흡입 풍량 / 덕트 / 팬")
    print("=" * 68)
    total = 0.0
    v_duct = cfg["duct_velocity"]
    for tag, w, h, v in cfg["hoods"]:
        q = w * h * v * 3600
        q_leak = q * cfg["leak_factor"]
        total += q_leak
        d = math.sqrt(4 * (q_leak / 3600) / (math.pi * v_duct)) * 1000
        print(f"  {tag}  {w*1000:.0f}x{h*1000:.0f} mm  면속도={v:.1f} m/s  "
              f"Q={q:5.0f} -> 누기포함 {q_leak:5.0f} m3/h  지관 Ø{d:.0f} mm")
    design_q = round(total * cfg["fan_margin"] / 100) * 100
    d_main = math.sqrt(4 * (design_q / 3600) / (math.pi * v_duct)) * 1000
    kw = (design_q / 60) * cfg["fan_dp_mmaq"] / (6120 * cfg["fan_eff"])
    print(f"\n  흡입 소요 합계 = {total:.0f} m3/h")
    print(f"  설계 풍량      = {design_q:.0f} m3/h   주관 Ø{d_main:.0f} mm ({v_duct:.0f} m/s)")
    print(f"  팬 축동력      = {kw:.2f} kW  (dP={cfg['fan_dp_mmaq']:.0f} mmAq, "
          f"eta={cfg['fan_eff']}) -> 모터 5.5 kW")

    print()
    print("=" * 68)
    print(f"4. 물질수지 (정격 {cfg['feed_tph']:.1f} t/h)")
    print("=" * 68)
    feed = cfg["feed_tph"] * 1000
    for k, frac in cfg["split"].items():
        print(f"  {k:12s} {frac*100:5.1f} %  {feed*frac:7.0f} kg/h")


if __name__ == "__main__":
    report()
