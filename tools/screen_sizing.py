#!/usr/bin/env python3
"""다단 경사 진동 스크린 + 단별 에어석션 사이징 계산기.

docs/multi-stage-screen-design.md 의 수치를 재현·재산출한다.
실측치가 확보되면 CONFIG 만 고쳐서 다시 돌리면 된다.

    python3 tools/screen_sizing.py

Rev.1 — 직사각 경사 진동 스크린, 250~350 kg/h 기준.
        (Rev.0 은 원형 자이라토리 Ø1800, 2.0 t/h 기준이었다.)
"""
import math

# ── 설계 전제 (실측치로 치환할 것) ────────────────────────────────
CONFIG = {
    "feed_tph": 0.25,         # 정격 공급량 t/h
    "peak_tph": 0.35,         # 최대 공급량 t/h
    "bulk_density": 1.2,      # t/m3
    "split": {                # 분획별 중량 분율
        "os_12mm": 0.08,
        "f_5_12mm": 0.12,
        "f_06_5mm": 0.35,
        "pan": 0.45,
    },
    # 채택 데크 스택 (개구 mm, 위에서 아래로). B안 = 12 / 0.6 2단 + 팬.
    # A안(3단, 방출구 2계통)을 보려면 [12.0, 5.0, 0.6] 로 바꾼다.
    "deck_stack": [12.0, 0.6],
    # 경사 진동 스크린 기준 처리능력 t/h/m2 (원형 자이라토리보다 미세컷에서 낮다)
    "deck_capacity": {12.0: 6.0, 5.0: 3.0, 0.6: 0.8},
    "deck_width_m": 0.40,     # 데크 폭
    "deck_length_m": 1.40,    # 데크 길이
    "incline_deg": 12.0,      # 경사각
    "travel_speed_mpm": 12.0, # 이송속도 m/min
    # 후드: (태그, 커트 면속도 m/s)  — 개구 폭은 데크 폭 + 여유로 자동 산출
    "hoods": [("AS-01", 2.8), ("AS-02", 3.1)],
    "hood_clearance_m": 0.10,  # 데크 폭 대비 후드 폭 여유 (양쪽 합)
    "hood_height_m": 0.09,     # 낙하 궤적 밴드 높이
    "leak_factor": 1.5,
    "fan_margin": 1.25,
    "duct_velocity": 18.0,     # m/s, 필름 침강 방지 하한
    "fan_dp_mmaq": 300.0,
    "fan_eff": 0.63,
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


def effective_aperture(aperture_mm, incline_deg):
    """경사면 위 메쉬의 유효 개구 [mm]. 수평 투영이므로 cos 만큼 줄어든다."""
    return aperture_mm * math.cos(math.radians(incline_deg))


def bed_depth_mm(tph, bulk_density, width_m, travel_mpm):
    """데크 위 베드 깊이 [mm]. 경사 스크린의 실질 제약."""
    q_m3_min = tph / bulk_density / 60.0
    return q_m3_min / travel_mpm / width_m * 1000.0


def hood_flow(cfg, face_velocity):
    """후드 1개의 (개구폭 m, 개구면적 m2, 풍량 m3/h, 누기포함 m3/h)."""
    w = cfg["deck_width_m"] + cfg["hood_clearance_m"]
    area = w * cfg["hood_height_m"]
    q = area * face_velocity * 3600
    return w, area, q, q * cfg["leak_factor"]


def duct_diameter_mm(q_m3h, velocity):
    return math.sqrt(4 * (q_m3h / 3600) / (math.pi * velocity)) * 1000


def fan_shaft_kw(q_m3h, dp_mmaq, eff):
    return (q_m3h / 60) * dp_mmaq / (6120 * eff)


def report(cfg=CONFIG):
    peak = cfg["peak_tph"]
    s = cfg["split"]

    print("=" * 72)
    print("1. 종말속도 — 커트 속도 결정 근거 (기종과 무관, Rev.0 과 동일)")
    print("=" * 72)
    for name, rho, t in [("백시트 0.2mm", 1400, 0.2e-3),
                         ("백시트 0.3mm", 1400, 0.3e-3),
                         ("EVA 필름 0.45mm", 950, 0.45e-3),
                         ("유리 박편 0.15mm", 2500, 0.15e-3),
                         ("구리 리본 0.15mm", 8900, 0.15e-3),
                         ("구리 리본 0.20mm", 8900, 0.2e-3)]:
        print(f"  {name:18s} rho*t={rho*t:6.3f} kg/m2   vt={vt_plate(rho, t):5.2f} m/s")
    print("  --- 입상 유리 (미분 손실 한계) ---")
    for d_mm in (0.1, 0.2, 0.3, 0.5, 0.6, 1.0):
        print(f"  유리 d={d_mm:4.1f} mm {'':17s}vt={vt_sphere(2500, d_mm/1000):5.2f} m/s")

    print()
    print("=" * 72)
    print(f"2. 데크 소요면적 (최대 {peak*1000:.0f} kg/h 기준)")
    print("=" * 72)
    # 각 데크 통과부하 = 공급량에서 위쪽 데크들이 걷어낸 오버사이즈를 뺀 값
    removed = {12.0: s["os_12mm"], 5.0: s["f_5_12mm"], 0.6: s["f_06_5mm"]}
    loads, carried = [], 1.0
    for ap in cfg["deck_stack"]:
        loads.append((ap, peak * carried))
        carried -= removed[ap]
    need = 0.0
    for ap, load in loads:
        cap = cfg["deck_capacity"][ap]
        area = load / cap
        need = max(need, area)
        print(f"  {ap:5.1f} mm 데크  부하={load*1000:5.0f} kg/h  "
              f"능력={cap:.1f} t/h/m2 -> 소요 {area:.3f} m2")
    w, l = cfg["deck_width_m"], cfg["deck_length_m"]
    have = w * l
    print(f"\n  지배 소요면적 = {need:.3f} m2")
    print(f"  채택 데크 W{w*1000:.0f} x L{l*1000:.0f} mm = {have:.2f} m2 "
          f"(여유 {have/need*100-100:+.0f}%, L/W = {l/w:.1f})")

    print()
    print("=" * 72)
    print("3. 베드 깊이 — 경사 스크린의 진짜 제약")
    print("=" * 72)
    d = bed_depth_mm(peak, cfg["bulk_density"], w, cfg["travel_speed_mpm"])
    print(f"  채택 조건 (W{w*1000:.0f} mm, {cfg['travel_speed_mpm']:.0f} m/min) "
          f"-> 베드깊이 {d:.2f} mm")
    q_m3_min = peak / cfg["bulk_density"] / 60.0
    w_for_4mm = q_m3_min / cfg["travel_speed_mpm"] / 0.004
    print(f"  베드 4 mm 를 만들려면 폭 {w_for_4mm*1000:.0f} mm 필요 -> 실현 불가")
    print("  => 이 기계는 용량이 아니라 '최소 실현 치수'에 지배된다. 사실상 단층 이송.")

    print()
    print("=" * 72)
    print("4. 유효 개구 (경사 보정)")
    print("=" * 72)
    th = cfg["incline_deg"]
    for ap in (12.0, 0.6):
        eff = effective_aperture(ap, th)
        need_mesh = ap / math.cos(math.radians(th))
        print(f"  경사 {th:.0f}° : {ap:5.2f} mm 메쉬 -> 유효개구 {eff:5.3f} mm  "
              f"(실 {ap:.2f} mm 컷을 내려면 메쉬 {need_mesh:.3f} mm)")

    print()
    print("=" * 72)
    print("5. 흡입 풍량 — 처리량이 아니라 '낙하 커튼 폭'이 지배한다")
    print("=" * 72)
    total = 0.0
    v_duct = cfg["duct_velocity"]
    for tag, v in cfg["hoods"]:
        hw, area, q, q_leak = hood_flow(cfg, v)
        total += q_leak
        print(f"  {tag}  후드 {hw*1000:.0f} x {cfg['hood_height_m']*1000:.0f} mm "
              f"({area:.4f} m2)  면속도 {v:.1f} m/s -> {q:4.0f} m3/h "
              f"(누기포함 {q_leak:4.0f})  지관 Ø{duct_diameter_mm(q_leak, v_duct):.0f} mm")
    design_q = round(total * cfg["fan_margin"] / 50) * 50
    kw = fan_shaft_kw(design_q, cfg["fan_dp_mmaq"], cfg["fan_eff"])
    print(f"\n  설계 풍량 = {design_q:.0f} m3/h   "
          f"주관 Ø{duct_diameter_mm(design_q, v_duct):.0f} mm ({v_duct:.0f} m/s)")
    print(f"  팬 축동력 = {kw:.2f} kW  (dP={cfg['fan_dp_mmaq']:.0f} mmAq, "
          f"eta={cfg['fan_eff']})")

    print()
    print("=" * 72)
    print(f"6. 물질수지 (정격 {cfg['feed_tph']*1000:.0f} kg/h)")
    print("=" * 72)
    feed = cfg["feed_tph"] * 1000
    for k, frac in s.items():
        print(f"  {k:12s} {frac*100:5.1f} %  {feed*frac:6.0f} kg/h")


if __name__ == "__main__":
    report()
