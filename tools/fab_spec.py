#!/usr/bin/env python3
"""DG-HK60C 제작 지침서의 계산 근거 — 볼트·용접·부재를 하중에서 낸다.

왜 계산기인가. 제작 지침서가 "M20 8.8, 토크 550 N·m" 이라고만 적으면 그 값이
어디서 왔는지 아무도 모르고, 하중이 바뀌었을 때 무엇을 다시 잡아야 하는지도
모른다. 그래서 값을 적지 않고 식을 적는다. 하중을 바꾸면 표가 따라 움직이고,
시험이 문서와 이 계산기를 대조한다.

설계 기준은 하나로 통일한다:

  구조·접합   EN 1993-1-1 / EN 1993-1-8 (부분계수법)
  볼트        ISO 898-1 (기계적 성질) · ISO 4014/4032/7089 (형상)
  용접        ISO 2553 (기호) · EN 1993-1-8 (내력) · ISO 5817 등급 C
  재료        KS D 3503 (SS400) · KS D 3515 (SM490A) · KS D 3705 (STS304)
  일반공차    ISO 2768-mK · 끼워맞춤 ISO 286

박리 추력은 아직 곡선이 아니라 밴드다 (1.49 ~ 13.37 kN, OI-01). 총괄 판단으로
**상한 13.37 kN 에 동적계수를 얹어 포락 설계**한다. 실측 곡선이 나오면 그것은
최적화이지 재설계가 아니다 — 이 방향으로만 안전하다.
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import console_consts  # noqa: E402

c = console_consts.const

# ── 1. 부분계수와 설계 기준 ────────────────────────────────────────────
GAMMA_G = 1.35      # 자중 (EN 1990)
GAMMA_Q = 1.50      # 적재·공정하중
GAMMA_M0 = 1.00     # 단면 항복
GAMMA_M2 = 1.25     # 볼트·용접 파단
GAMMA_M3 = 1.25     # 마찰접합 미끄러짐
PSI_DYN = 1.30      # 칼날 물림 충격 — 정적 박리력에 얹는다
SEISMIC = 0.30      # 기계 정착부 수평계수 (KDS 41 17 00 간이)
G = 9.80665

# ── 2. 재료 (KS D) ─────────────────────────────────────────────────────
#    fy · fu 는 MPa. rho 는 kg/m³.
MATERIALS = {
    "SS400":     dict(fy=235, fu=400, rho=7850, std="KS D 3503", use="일반 구조·외함·데크"),
    "SM490A":    dict(fy=325, fu=490, rho=7850, std="KS D 3515", use="갠트리·주행레일 문형·고응력 부재"),
    "STS304":    dict(fy=205, fu=520, rho=7930, std="KS D 3705", use="가열실 내피·고온 습부·식품접촉 없음"),
    "SM45C":     dict(fy=343, fu=569, rho=7850, std="KS D 3752", use="축류 (권취축·롤러축)"),
    "A6061-T6":  dict(fy=240, fu=290, rho=2700, std="KS D 6759", use="이동 경량부 (캐리지·포크 암)"),
    "SKD11":     dict(fy=None, fu=None, rho=7700, std="KS D 3753", use="칼날 인서트 (HRC 58~62)"),
}


def f_allow(mat: str) -> float:
    """단면 항복 기준 설계강도 fy/γM0 (MPa)."""
    fy = MATERIALS[mat]["fy"]
    if fy is None:
        raise KeyError(f"{mat} 는 구조 부재로 쓰지 않는다")
    return fy / GAMMA_M0


# ── 3. 볼트 (ISO 898-1 · ISO 4014) ─────────────────────────────────────
#    As 는 인장 응력 단면적 mm², A 는 나사 없는 몸통 단면적 mm².
BOLTS = {
    "M10": dict(As=58.0,  A=78.5,   p=1.50, k=17, s=17),
    "M12": dict(As=84.3,  A=113.1,  p=1.75, k=19, s=19),
    "M16": dict(As=157.0, A=201.1,  p=2.00, k=24, s=24),
    "M20": dict(As=245.0, A=314.2,  p=2.50, k=30, s=30),
    "M24": dict(As=353.0, A=452.4,  p=3.00, k=36, s=36),
    "M30": dict(As=561.0, A=706.9,  p=3.50, k=46, s=46),
    "M36": dict(As=817.0, A=1017.9, p=4.00, k=55, s=55),
}
BOLT_ORDER = ["M10", "M12", "M16", "M20", "M24", "M30", "M36"]

# 등급별 인장강도·항복강도와 전단계수 αv (EN 1993-1-8 Table 3.4).
# αv 는 전단면이 나사부를 지날 때의 값이다 — 제작 지침서는 나사부 전단을
# 기본으로 잡는다. 몸통 전단을 쓰려면 그리프 길이를 도면에서 지정해야 하고,
# 현장에서 그것이 지켜지는지 확인할 방법이 없기 때문이다.
GRADES = {
    "8.8":   dict(fub=800,  fyb=640, av=0.6, note="일반 구조 접합"),
    "10.9":  dict(fub=1000, fyb=900, av=0.5, note="갠트리·마찰접합·고하중"),
    "A2-70": dict(fub=700,  fyb=450, av=0.6, note="가열실 내부·습부 (STS304 볼트)"),
}


def bolt_tension(size: str, grade: str) -> float:
    """인장 내력 Ft,Rd = k2·fub·As/γM2 (kN) — k2 = 0.9."""
    return 0.9 * GRADES[grade]["fub"] * BOLTS[size]["As"] / GAMMA_M2 / 1000


def bolt_shear(size: str, grade: str) -> float:
    """전단면당 전단 내력 Fv,Rd = αv·fub·As/γM2 (kN) — 나사부 전단."""
    g = GRADES[grade]
    return g["av"] * g["fub"] * BOLTS[size]["As"] / GAMMA_M2 / 1000


def preload(size: str, grade: str) -> float:
    """설계 체결력 Fp,C = 0.7·fub·As (kN) — EN 1993-1-8 3.6.1."""
    return 0.7 * GRADES[grade]["fub"] * BOLTS[size]["As"] / 1000


def torque(size: str, grade: str, K: float) -> float:
    """조임 토크 T = K·d·Fp,C (N·m).

    K 는 토크계수이고 마찰이 정한다. 같은 체결력이라도 건조 아연도금과
    윤활은 토크가 40 % 다르다 — 그래서 지침서는 토크가 아니라 **체결력**을
    사양으로 적고, 토크는 마찰 조건과 함께 적는다.
    """
    d = int(size[1:]) / 1000
    return K * d * preload(size, grade) * 1000


K_DRY = 0.20    # 건조 아연도금 (as-received)
K_LUB = 0.14    # 이황화몰리브덴 또는 방청유 도포


def slip_resistance(size: str, grade: str, mu: float = 0.50, n: int = 1) -> float:
    """마찰접합 미끄러짐 내력 Fs,Rd = ks·n·μ·Fp,C/γM3 (kN) — ks=1.0 표준구멍."""
    return 1.0 * n * mu * preload(size, grade) / GAMMA_M3


def combined_ok(N_ed: float, V_ed: float, size: str, grade: str, planes: int = 1) -> float:
    """조합 이용률 V/Fv + N/(1.4·Ft) ≤ 1.0 (EN 1993-1-8 Table 3.4)."""
    return V_ed / (planes * bolt_shear(size, grade)) + N_ed / (1.4 * bolt_tension(size, grade))


def pick_bolt(N_ed: float, V_ed: float, grade: str, planes: int = 1,
              minimum: str = "M12", target: float = 0.70) -> str:
    """이용률이 target 이하가 되는 가장 작은 규격.

    target 을 1.0 이 아니라 0.70 으로 두는 것은 제작 여유다. 현장에서
    구멍이 밀리고 와셔가 빠지고 토크가 덜 들어간다 — 도면상 100 % 인
    접합은 실제로 100 % 가 아니다.
    """
    start = BOLT_ORDER.index(minimum)
    for size in BOLT_ORDER[start:]:
        if combined_ok(N_ed, V_ed, size, grade, planes) <= target:
            return size
    return BOLT_ORDER[-1]


# ── 4. 용접 (EN 1993-1-8 4.5.3.3 단순법) ───────────────────────────────
def fillet_capacity(a: float, mat: str = "SS400") -> float:
    """필릿 용접 목두께 a (mm) 당 단위길이 설계내력 (kN/mm).

    Fw,Rd = fu/(√3·βw·γM2) · a — SS400 은 βw = 0.80 (EN 1993-1-8 Table 4.1
    의 S235 상당).
    """
    fu = MATERIALS[mat]["fu"]
    beta = 0.80 if mat in ("SS400", "STS304") else 0.85
    return fu / (math.sqrt(3) * beta * GAMMA_M2) * a / 1000


# 두꺼운 쪽 판두께에 대한 최소 각장. 얇은 각장을 두꺼운 판에 놓으면
# 용융지가 빨리 식어 균열이 생긴다 — 강도가 남아도 이 표를 밑돌 수 없다.
MIN_LEG = ((6, 4), (12, 5), (19, 6), (25, 8), (10 ** 9, 10))


def min_leg(t_mm: float) -> int:
    for lim, z in MIN_LEG:
        if t_mm <= lim:
            return z
    return 10


def fillet_leg(force_kn: float, length_mm: float, mat: str = "SS400",
               both_sides: bool = True, t_mm: float = 6.0) -> tuple[int, str]:
    """필요 각장 z (mm) 와 그것을 정한 근거.

    강도로 나온 각장과 판두께 최소 각장 중 큰 쪽을 쓴다. 이 설비에서는
    거의 언제나 판두께가 이긴다 — 하중이 작기 때문이다. 그것을 숨기지
    않고 근거로 적는 것이 지침서의 값이다.
    """
    L = length_mm * (2 if both_sides else 1)
    z_str = math.ceil(force_kn / (fillet_capacity(1.0, mat) * L) / 0.7)
    z_min = min_leg(t_mm)
    return (max(z_str, z_min), "강도" if z_str >= z_min else f"판두께 t{t_mm:.0f}")


# ── 5. 설계하중 ────────────────────────────────────────────────────────
PANEL_L, PANEL_W = c("PANEL_L"), c("PANEL_W")
W_PANEL = c("MASS_AREAL") * PANEL_L * PANEL_W * G / 1000          # kN/장
W_GLASS = c("MASS_GLASS") * PANEL_L * PANEL_W * G / 1000
WR_TURN = PANEL_L * c("BACKSHEET_T") / math.pi
ROLL_PANELS = round((c("WR_FULL_R") ** 2 - c("WR_CORE_R") ** 2) / WR_TURN)
W_ROLL = c("MASS_BACK") * PANEL_L * PANEL_W * ROLL_PANELS * G / 1000
W_CASS = c("CASS_MASS") * G / 1000

# 박리 추력 — 밴드의 상한에 동적계수를 얹어 포락한다 (OI-01).
F_PEEL_K = c("F_PEEL")                             # kN 특성값 — OI-01 상한 13.37 @ 폭 1,200 을 포락선 폭으로 환산 (콘솔 F_PEEL)
F_PEEL_D = F_PEEL_K * PSI_DYN * GAMMA_Q            # kN 설계값

# 자중. **개산이 아니라 부품 카탈로그의 형상에서 계산한 값**이다 —
# parts.py 가 부재마다 단면적 × 길이 × 밀도를 더한다. 형상이 바뀌면 여기가
# 따라 움직이고, 아래 접합부·앵커·용접이 전부 따라 움직인다.
#
# 개념단계에는 이 넷을 형상 없이 개산으로 적었다. 카탈로그를 세우고 대조해
# 보니 권취 문형이 +48 %, 진공테이블이 +38 % 빗나가 있었다 (parts.report()).
# 형상 없이 적은 자중으로 앵커를 정하면 그런 크기의 오차를 안고 가는 것이다.
#
# 제작사 중량표가 나오면 여기가 아니라 parts.py 의 형상을 고친다. 카탈로그가
# ±15 % 를 벗어나면 앵커·기초를 다시 본다 — 일곱 개소 전부 콘크리트 콘
# 파괴가 지배하므로 매입깊이가 규격보다 먼저 움직인다.
from parts import mass as _pm

M_CHAMBER = _pm("M_CHAMBER")    # 가열실 일식 (골조·벽체·데크·IR)
M_GANTRY = _pm("M_GANTRY")      # 갠트리 이동부 (주행 문형·레일 제외)
M_TABLE = _pm("M_TABLE")        # VT-101 상판·리브·기둥·진공계통
M_WINDER = _pm("M_WINDER")      # 권취 문형 (RH-201 런웨이 제외)


def kn(mass_kg: float) -> float:
    return mass_kg * G / 1000


# ── 6. 접합부 검토 ─────────────────────────────────────────────────────
# 각 접합은 (인장, 전단) 설계력을 받는다. 힘의 유도는 note 에 적는다.
def _joints():
    J = []

    # ── J1 · VT-101 진공테이블 기둥 베이스 (기초 A8)
    # 박리 추력의 반작용이 흡착패드 → 상판 → 기둥 → 앵커로 내려온다.
    # F-005 는 "테이블은 패널 반력만 받는다" 고 적었지만, 그 패널 반력이
    # 곧 추력이다 — 작용·반작용 쌍이므로 양쪽 기초가 같은 크기를 받는다.
    tbl_span_x, tbl_span_y, tbl_h = c("CARRIER_L") - 0.40, c("CARRIER_W") - 0.32, c("CZ")
    V_tbl = F_PEEL_D / 4                                     # 기둥 4개 분담 전단
    N_tbl = (F_PEEL_D * tbl_h) / tbl_span_x / 2              # 전도 짝힘 → 기둥당 인장
    J.append(dict(id="J1", name="VT-101 기둥 ↔ 베이스플레이트", grade="8.8", n=4,
                  N=N_tbl / 4, V=V_tbl / 4, planes=1, minimum="M16",
                  note=f"추력 반작용 {F_PEEL_D:.1f} kN · 팔길이 {tbl_h:.2f} m · 기둥간격 {tbl_span_x:.2f} m"))

    # ── J2 · KG-101 주행레일 문형 기둥 베이스 (기초 A7)
    # 칼날이 미는 쪽. 같은 추력이 레일 높이에서 걸린다.
    rail_h = c("CRAIL_Z")
    rail_span = c("CRAIL_X1") - c("CRAIL_X0")
    V_g = F_PEEL_D / 4
    N_g = (F_PEEL_D * rail_h) / rail_span / 2
    J.append(dict(id="J2", name="KG-101 주행레일 문형 기둥 ↔ 베이스플레이트", grade="10.9", n=4,
                  N=N_g / 4, V=V_g / 4, planes=1, minimum="M20",
                  note=f"추력 {F_PEEL_D:.1f} kN @ EL {rail_h*1000:.0f} · 문형 스팬 {rail_span:.2f} m"))

    # ── J3 · KG-101 크로스빔 ↔ 주행대차 (마찰접합)
    # 여기서 미끄러지면 칼끝 간격 300±2 가 깨진다. 지압접합이 아니라
    # 마찰접합으로 잡는다 — 미끄러진 뒤 지압으로 버티는 것은 늦다.
    J.append(dict(id="J3", name="KG-101 크로스빔 ↔ 주행대차 (마찰접합)", grade="10.9", n=8,
                  N=0.0, V=F_PEEL_D / 8, planes=1, minimum="M16", slip=True,
                  note="칼끝 간격 300±2 를 지키려면 미끄러지면 안 된다 — 마찰접합 μ=0.50"))

    # ── J4 · HKB/HKS 칼날 빔 ↔ Z축 서보슬라이드
    # 칼날 하나가 받는 추력은 합성추력의 절반이다.
    J.append(dict(id="J4", name="칼날 빔 ↔ Z축 서보슬라이드", grade="10.9", n=6,
                  N=F_PEEL_D / 2 / 6, V=F_PEEL_D / 2 / 6, planes=1, minimum="M12",
                  note=f"칼날 1기 분담 {F_PEEL_D/2:.1f} kN — 인장·전단 동시"))

    # ── J5 · BC-201 카세트 ↔ 슬라이드 (테이퍼 핀 + 쐐기 클램프)
    # 클램프는 밀착만 하고 전단은 테이퍼 로케이팅핀 4개가 받는다.
    # 클램프를 전단재로 세면 15 kN×2 = 30 kN 이 설계추력 대비 1.15 밖에 안 된다.
    J.append(dict(id="J5", name="BC-201 카세트 테이퍼 로케이팅핀", grade="10.9", n=4,
                  N=0.0, V=F_PEEL_D / 2 / 4, planes=2, minimum="M16", pin=True,
                  note=f"쐐기 클램프({c('CASS_CLAMP_KN')} kN×2)는 밀착용 — 전단은 핀 4개가 받는다"))

    # ── J6 · HC-101 가열실 기둥 베이스
    w = kn(M_CHAMBER)
    N_ch = (SEISMIC * w * 2.40) / 2.30 / 2 - GAMMA_G * w / 4   # 지진 인장 − 자중 압축
    J.append(dict(id="J6", name="HC-101 가열실 기둥 ↔ 베이스플레이트", grade="8.8", n=4,
                  N=max(N_ch, 0.0) / 4, V=SEISMIC * w / 4 / 4, planes=1, minimum="M20",
                  note=f"자중 {M_CHAMBER/1000:.1f} t · 지진 {SEISMIC:.2f}W @ 무게중심 EL 2,400"))

    # ── J7 · 가열실 데크 레일 ↔ 기둥 (내부 · 고온)
    deck_w = GAMMA_Q * (W_PANEL + kn(120))
    J.append(dict(id="J7", name="데크 레일 ↔ 기둥 (가열실 내부)", grade="A2-70", n=4,
                  N=deck_w / 4 / 2, V=deck_w / 4, planes=1, minimum="M12",
                  note=f"데크 1단 {W_PANEL+kn(120):.2f} kN · {c('T_TARGET')} °C 환경 — STS304 볼트"))

    # ── J8 · WR-101 권취 지지 문형 기둥 베이스
    w_wr = kn(M_WINDER) + GAMMA_Q * W_ROLL
    J.append(dict(id="J8", name="WR-101 권취 문형 기둥 ↔ 베이스플레이트", grade="8.8", n=4,
                  N=SEISMIC * w_wr * 3.70 / 2.60 / 2 / 4,
                  V=SEISMIC * w_wr / 2 / 4, planes=1, minimum="M16",
                  note=f"만권 롤 {W_ROLL:.2f} kN @ EL 3,700 · 문형 스팬 2.60 m"))

    # ── J9 · RH-201 모노레일 런웨이 ↔ 기둥
    hoist = GAMMA_Q * (W_ROLL + kn(150)) * 1.25       # 호이스트 동적계수 1.25 (ISO 8686 간이)
    J.append(dict(id="J9", name="RH-201 런웨이 빔 ↔ 기둥 두상판", grade="10.9", n=6,
                  N=hoist / 6, V=hoist / 6 / 3, planes=1, minimum="M16",
                  note=f"롤 {W_ROLL:.2f} kN + 호이스트 자중 · 동적계수 1.25"))

    # ── J10 · 승강 포크 문형 볼스크류 지지 (LI·EX·GL·GU 공통)
    fork = GAMMA_Q * (W_PANEL + kn(180)) * 1.20       # 급정지 계수 1.20
    J.append(dict(id="J10", name="승강 포크 볼스크류 지지 ↔ 문형 기둥", grade="8.8", n=4,
                  N=fork / 4, V=fork / 4 / 4, planes=1, minimum="M12",
                  note="포크 + 패널 · 급정지 1.20 — 낙하방지 브레이크와 별개로 정적 지지"))

    # ── J11 · 방책 기둥 ↔ 바닥
    J.append(dict(id="J11", name="안전방책 기둥 ↔ 바닥 앵커", grade="8.8", n=2,
                  N=0.50, V=0.75, planes=1, minimum="M10",
                  note="ISO 14120 — 수평 1,000 N 을 기둥 상단에서 견딘다"))

    # ── J12 · 배기 헤더 플랜지 (Ø600 경계)
    duct = GAMMA_Q * kn(60) + 0.30                    # 덕트 자중 + 부압
    J.append(dict(id="J12", name="배기 헤더 Ø600 플랜지 (M-017 경계)", grade="8.8", n=12,
                  N=duct / 12, V=duct / 12 / 2, planes=1, minimum="M12",
                  note="발주자 설비와의 인계면 — 개스킷 압착과 기밀이 지배"))

    for j in J:
        j.setdefault("slip", False)
        j.setdefault("pin", False)
        j["size"] = pick_bolt(j["N"], j["V"], j["grade"], j["planes"], j["minimum"])
        j["util"] = combined_ok(j["N"], j["V"], j["size"], j["grade"], j["planes"])
        j["Fp"] = preload(j["size"], j["grade"])
        j["T_dry"] = torque(j["size"], j["grade"], K_DRY)
        j["T_lub"] = torque(j["size"], j["grade"], K_LUB)
        if j["slip"]:
            j["Fs"] = slip_resistance(j["size"], j["grade"])
            j["slip_util"] = j["V"] / j["Fs"]
    return J


JOINTS = _joints()


# ── 6b. 피로 (EN 1993-1-9) ─────────────────────────────────────────────
# 이 라인은 60 장/h 로 돌아간다. 20 년이면 박리 추력이 1,000 만 번 걸린다 —
# 정적 강도로는 이용률 0.05 인 접합이 피로로는 지배될 수 있다. 그래서
# 부재 단면은 정적 강도가 아니라 **응력범위**와 **처짐**이 정한다.
NET_TARGET = int(c("NET_TARGET"))   # 계약 순생산 장/h (콘솔 NET_TARGET)
OP_HOURS_Y = 8760 * 0.90    # 가동률 90 %
DESIGN_LIFE_Y = 20

CYCLES_Y = NET_TARGET * OP_HOURS_Y
CYCLES_LIFE = CYCLES_Y * DESIGN_LIFE_Y

# EN 1993-1-9 Table 8.x 상세 등급 (Δσc @ 2×10⁶). 이 설비에서 쓰는 것만.
DETAIL_CATEGORY = {
    "모재 (압연면)":           160,
    "고장력 마찰접합":          112,
    "맞대기 용접 (완전용입·연삭)": 90,
    "필릿 용접 부착물":          71,
    "십자 이음 (하중전달 필릿)":   36,
}


def fatigue_limit(cat: int) -> float:
    """일정진폭 피로한도 Δσ_D = Δσ_C·(2/5)^(1/3) (MPa).

    수명이 5×10⁶ 회를 넘으면 응력범위를 이 값 아래로 두는 것이 가장 확실한
    설계다 — 손상누적을 계산하지 않아도 되고, 실제 하중이 예상보다 커도
    급격히 무너지지 않는다.
    """
    return cat * (2 / 5) ** (1 / 3)


def stress_range(m_knm: float, z_mm3: float) -> float:
    """Δσ = M/Z (MPa) — 박리 추력은 0 ↔ 최대를 오가므로 진폭이 곧 범위다."""
    return m_knm * 1e6 / z_mm3


# 정렬이 걸린 부재의 처짐 한계. 칼끝 간격 300±2 를 지키려면 갠트리
# 크로스빔이 추력 아래에서 0.5 mm 이상 휘면 안 된다 — 공차의 1/4 이다.
E_STEEL = 210_000           # MPa


def beam_deflection(f_kn: float, span_mm: float, i_mm4: float) -> float:
    """중앙집중하중 단순보 처짐 δ = FL³/48EI (mm)."""
    return f_kn * 1000 * span_mm ** 3 / (48 * E_STEEL * i_mm4)


# 정렬·피로가 지배하는 부재의 실제 검토. 단면 제원은 부재표와 같은 값이다.
def _critical():
    C = []

    # KG-101 크로스빔 BOX-300×200×12 — 칼끝 간격을 지키는 부재
    I_beam = (200 * 300 ** 3 - 176 * 276 ** 3) / 12
    Z_beam = I_beam / 150
    span = 2 * c("CGY") * 1000
    C.append(dict(
        id="C1", member="KG-101 크로스빔 BOX-300×200×12", mat="SM490A",
        gov="처짐 (칼끝 간격 300±2)",
        value=beam_deflection(F_PEEL_K, span, I_beam), limit=0.50, unit="mm",
        note=f"스팬 {span:.0f} · 특성 추력 {F_PEEL_K:.2f} kN · 한계는 공차의 1/4"))
    C.append(dict(
        id="C2", member="KG-101 크로스빔 (용접 부착부)", mat="SM490A",
        gov="피로 — 필릿 용접 부착물 (등급 71)",
        value=stress_range(F_PEEL_K / 2 * span / 4000, Z_beam),
        limit=fatigue_limit(DETAIL_CATEGORY["필릿 용접 부착물"]), unit="MPa",
        note=f"{CYCLES_LIFE/1e6:.1f}×10⁶ 회 — 5×10⁶ 초과이므로 피로한도 이하로 둔다"))

    # VT-101 테이블 기둥 □-150×150×6 — 추력 반작용을 받는 캔틸레버
    I_col = (150 ** 4 - 138 ** 4) / 12
    Z_col = I_col / 75
    m_col = F_PEEL_K / 4 * c("CZ")
    C.append(dict(
        id="C3", member="VT-101 테이블 기둥 □-150×150×6", mat="SM490A",
        gov="피로 — 필릿 용접 부착물 (등급 71)",
        value=stress_range(m_col, Z_col),
        limit=fatigue_limit(DETAIL_CATEGORY["필릿 용접 부착물"]), unit="MPa",
        note=f"기둥당 {F_PEEL_K/4:.2f} kN @ EL {c('CZ')*1000:.0f} 캔틸레버"))

    # KG-101 주행레일 문형 기둥 H-250×250×9/14
    Z_g = 867e3
    m_g = F_PEEL_K / 4 * c("CRAIL_Z")
    C.append(dict(
        id="C4", member="KG-101 문형 기둥 H-250×250×9/14", mat="SM490A",
        gov="피로 — 필릿 용접 부착물 (등급 71)",
        value=stress_range(m_g, Z_g),
        limit=fatigue_limit(DETAIL_CATEGORY["필릿 용접 부착물"]), unit="MPa",
        note=f"레일 EL {c('CRAIL_Z')*1000:.0f} 에서의 캔틸레버 휨"))

    # WR-101 권취축 Ø55 — 휨 + 비틀림 합성
    # Ø55 는 피로 이용률 0.89 였다. 기계 축에 두기엔 빡빡해 한 치수 올린다.
    d_shaft = 60
    Z_shaft = math.pi * d_shaft ** 3 / 32
    span_shaft = (c("ROLL_FACE") + 0.28) * 1000
    m_shaft = W_ROLL * span_shaft / 8 / 1000
    t_shaft = 2.0 * c("WR_FULL_R")            # 장력 상한 2 kN × 만권 반경
    me = math.sqrt(m_shaft ** 2 + t_shaft ** 2)
    C.append(dict(
        id="C5", member="WR-101 권취축 Ø60 h6", mat="SM45C",
        gov="피로 — 모재 회전굽힘 (등급 160 · 안전측 90 적용)",
        value=stress_range(me, Z_shaft),
        limit=fatigue_limit(DETAIL_CATEGORY["맞대기 용접 (완전용입·연삭)"]), unit="MPa",
        note=f"휨 {m_shaft:.2f} + 비틀림 {t_shaft:.2f} 합성 {me:.2f} kN·m · 스팬 {span_shaft:.0f}"))

    # RH-201 런웨이 빔 — 이동하중 처짐
    I_run = 1.87e7                            # H-200×100×5.5/8
    run_span = 3000.0                         # 지지 간격
    C.append(dict(
        id="C6", member="RH-201 런웨이 빔 H-200×100×5.5/8", mat="SS400",
        gov="처짐 L/500 (호이스트 주행)",
        value=beam_deflection(W_ROLL + kn(150), run_span, I_run),
        limit=run_span / 500, unit="mm",
        note=f"롤 {W_ROLL:.2f} + 호이스트 {kn(150):.2f} kN · 지지 간격 {run_span:.0f}"))

    for x in C:
        x["util"] = x["value"] / x["limit"]
    return C


CRITICAL = _critical()


# ── 6c. 앵커 (EN 1992-4 · 접착식) ──────────────────────────────────────
# D-602 는 앵커 '위치' 만 정하고 규격·매입깊이·연단거리를 남겨 두었다.
# 총괄 판단으로 여기서 닫는다 — 기초 콘크리트를 C25/30 이상으로 요구하고,
# 강재측이 아니라 **콘크리트측**이 지배한다는 것을 계산으로 보인다.
FCK = 25            # MPa — C25/30 최소
GAMMA_MC = 1.50     # 콘크리트 파괴
TAU_RK = 10.0       # MPa — 균열 콘크리트 접착강도 (제조사 ETA 최소값 가정)


def anchor_cone(hef_mm: float) -> float:
    """단일 접착앵커 콘 파괴 내력 N_Rd,c (kN) — 연단·간격 영향 없음 기준."""
    n_rk = 7.7 * math.sqrt(FCK) * hef_mm ** 1.5 / 1000
    return n_rk / GAMMA_MC


def anchor_bond(d_mm: float, hef_mm: float) -> float:
    """접착 파괴 내력 N_Rd,p (kN)."""
    return math.pi * d_mm * hef_mm * TAU_RK / 1000 / GAMMA_MC


ANCHORS = []
for _aid, _eq, _d, _hef, _grade, _n in (
    ("A2", "HC-101 가열실", 20, 170, "8.8", 4),
    ("A7", "KG-101 주행레일 문형", 24, 210, "10.9", 4),
    ("A8", "VT-101 진공테이블", 24, 210, "10.9", 4),
    ("A9", "WR-101 권취 문형", 20, 170, "8.8", 4),
    ("A10", "RH-201 모노레일 기둥", 20, 170, "8.8", 4),
    ("A11", "CE-201 횡인출", 16, 125, "8.8", 4),
    ("A12", "BS-301 롤 새들", 16, 125, "8.8", 4),
):
    _size = f"M{_d}"
    ANCHORS.append(dict(
        id=_aid, eq=_eq, size=_size, hef=_hef, grade=_grade, n=_n,
        steel=bolt_tension(_size, _grade),
        cone=anchor_cone(_hef), bond=anchor_bond(_d, _hef),
        edge=max(1.5 * _hef, 100), spacing=max(3.0 * _hef, 150),
        # 접착앵커 최소 부재두께 — EN 1992-4 는 hef+30 을 허용하지만 콘이
        # 온전히 발달하려면 그것으로 모자란다. hef+100 과 300 중 큰 값.
        slab=max(_hef + 100, 300),
    ))
for _a in ANCHORS:
    _a["gov"] = min((_a["steel"], "강재"), (_a["cone"], "콘크리트 콘"),
                    (_a["bond"], "접착"))[1]
    _a["Nrd"] = min(_a["steel"], _a["cone"], _a["bond"])


# ── 6d. 체결 부품 규칙 ─────────────────────────────────────────────────
# "M20 8.8" 만 적으면 현장에서 길이·와셔·풀림방지가 제각각이 된다.
# 세 가지를 규칙으로 못 박는다.
def grip_length(t_total_mm: float, size: str, washers: int = 2) -> int:
    """볼트 호칭길이 — 그립 + 와셔 + 너트 + 여유 나사산 2~5.

    나사부가 전단면을 지나는 것을 전제로 설계했으므로(αv), 몸통이 전단면에
    걸리도록 길이를 줄이면 안 된다. 길이는 넉넉한 쪽으로만 반올림한다.
    """
    b = BOLTS[size]
    d = int(size[1:])
    need = t_total_mm + washers * (0.15 * d) + 0.8 * d + 3 * b["p"]
    return int(math.ceil(need / 5) * 5)


WASHER_RULE = [
    ("평와셔", "ISO 7089 200HV", "볼트머리·너트 양쪽 각 1매 — 도장면 보호와 하중분산"),
    ("경화와셔", "ISO 7089 300HV", "10.9 등급과 마찰접합에는 경화와셔 필수"),
    ("스프링와셔", "사용 금지", "체결력 유지에 기여하지 않고 도장을 긁는다 — 풀림방지는 아래로"),
]
LOCKING_RULE = [
    ("정적 구조 접합", "체결력 관리 (Fp,C 70 %)", "토크렌치 + 마킹 — 별도 풀림방지 불요"),
    ("진동·왕복 부위", "쐐기형 풀림방지 와셔", "갠트리 대차·포크 캐리지·권취 베어링"),
    ("고온부 (>120 °C)", "전 나사 고착방지제 + 록너트", "가열실 내부 — 나사 소착 방지"),
    ("정비 중 반복 탈착", "헬리코일 인서트", "카세트 인터페이스·점검도어"),
]
# ── 6e. 용접 접합 목록 (이름, 설계력 kN, 용접장 mm, 재질, 두꺼운쪽 판두께) ─
WELDS = [
    ("가열실 기둥 ↔ 베이스플레이트", GAMMA_G * kn(M_CHAMBER) / 4, 4 * 200, "SS400", 25),
    ("가열실 기둥 ↔ 거싯", GAMMA_G * kn(M_CHAMBER) / 8, 2 * 250, "SS400", 12),
    ("테이블 기둥 ↔ 베이스플레이트", F_PEEL_D / 4, 4 * 150, "SM490A", 28),
    ("테이블 상판 ↔ 리브", F_PEEL_D / 8, 2 * 400, "SS400", 20),
    ("갠트리 문형 기둥 ↔ 베이스플레이트", F_PEEL_D / 4, 4 * 250, "SM490A", 30),
    ("크로스빔 ↔ 대차 브래킷", F_PEEL_D / 2, 2 * 300, "SM490A", 20),
    ("크로스빔 웨브 ↔ 플랜지 (BOX)", F_PEEL_D / 2, 2 * (2 * c("CGY") * 1000), "SM490A", 12),
    ("권취 문형 기둥 ↔ 베이스플레이트", GAMMA_Q * W_ROLL, 4 * 150, "SS400", 20),
    ("RH-201 런웨이 ↔ 기둥 두상판", GAMMA_Q * W_ROLL * 1.25, 2 * 200, "SS400", 16),
    ("데크 프레임 ↔ 레일 (가열실 내부)", GAMMA_Q * W_PANEL, 2 * c("DECK_L") * 1000, "STS304", 6),
    ("방책 기둥 ↔ 베이스", 1.0, 4 * 60, "SS400", 6),
]


# ── 7. 부재표 — 판두께·단면·재질 ───────────────────────────────────────
# governing 은 그 두께를 정한 검토다. 값이 아니라 이유를 적는다.
MEMBERS = [
    # (모듈, 부재, 단면·두께, 재질, 지배 검토)
    ("M-002", "가열실 기둥", "H-200×200×8/12", "SS400", "지진 전도 + 좌굴 (세장비 λ≤120)"),
    ("M-002", "기둥 거싯", "PL 12", "SS400", "기둥 국부 좌굴 보강 · 용접 각장 8"),
    ("M-002", "베이스플레이트", "PL 25 · 400×400", "SS400", "앵커 인장에 대한 판 휨"),
    ("M-002", "외피", "PL 3.2", "SS400", "면외 강성 · 1,200 모듈 리브 간격"),
    ("M-002", "내피", "PL 2.0", "STS304", f"{c('T_TARGET')} °C 복사면 · 내식"),
    ("M-002", "단열재", "미네랄울 100t · 100 kg/m³", "—", "외피 표면 60 °C 이하"),
    ("M-002", "열교 차단 스페이서", "GFRP t12 @600", "GFRP", "관통 열교 차단"),
    ("M-002", "데크 프레임", "L-65×65×6", "SS400", "패널 + 캐리지 집중하중"),
    ("M-002", "데크 레일", "각봉 40×40", "STS304", "마모 · 고온 크리프"),
    ("M-004", "VT-101 상판", "PL 20 (리브 PL 10 @400)", "SS400", "자중 처짐 → 칼날 깊이 예산 0.15"),
    ("M-004", "테이블 기둥", "□-150×150×6 ×6본", "SM490A", "추력 전도 + 상판 처짐 (구조해석)"),
    ("M-004", "베이스플레이트", "PL 28 · 360×360", "SM490A", "앵커 인장 · 추력 전단"),
    ("M-005", "주행레일 문형 기둥", "H-250×250×9/14", "SM490A", "추력 전도 + 갠트리 관성"),
    ("M-005", "주행레일", "프리로드 LM 레일 (사이즈 45)", "베어링강", "정격 수명 20,000 h"),
    ("M-005", "크로스빔", "BOX-300×200×12", "SM490A", "칼날 2기 자중 + 추력 휨"),
    ("M-005", "Z축 서보슬라이드 베이스", "PL 20", "SM490A", "칼날 반력 편심"),
    ("M-005", "칼날 빔", "PL 25 + SKD11 인서트 t8", "SS400/SKD11", "카트리지히터 홀 + 인서트 볼트"),
    ("M-006", "권취 문형 기둥", "H-150×150×7/10", "SS400", "만권 롤 + 지진"),
    ("M-006", "권취축", "Ø60 h6", "SM45C", "휨 + 비틀림 합성 피로 (조질 후 연삭)"),
    ("M-006", "RH-201 런웨이 빔", "H-200×100×5.5/8", "SS400", "호이스트 이동하중 · 처짐 L/500"),
    ("M-007", "냉각 랙 골조", "H-200×200×8/12", "SS400", "F-002 준용 — 지그 공용"),
    ("M-007", "측벽", "폴리카보네이트 t6", "PC", "방호 · 투시 (단열 아님)"),
    ("M-003", "포크 문형 기둥", "□-125×125×6", "SS400", "볼스크류 반력 + 편심"),
    ("M-003", "포크 암", "압출형재 t8", "A6061-T6", "이동 관성 최소화"),
    ("M-013", "방책 기둥", "□-60×60×3.2", "SS400", "ISO 14120 수평 1,000 N"),
    ("M-013", "메시 패널", "Ø4 @40×40", "SS400 아연도금", "ISO 13857 개구 기준"),
    ("M-017", "경계 덕트", "Ø600 t3.0", "SS400", "부압 · 지지 간격 3,000"),
]


# ── 8. 리포트 ──────────────────────────────────────────────────────────
def report() -> str:
    L = []
    add = L.append
    add("=" * 78)
    add("DG-HK60C 제작 지침서 — 계산 근거")
    add("=" * 78)
    add("")
    add("── 설계 기준 ────────────────────────────────────────────")
    add(f"  부분계수   γG {GAMMA_G} · γQ {GAMMA_Q} · γM0 {GAMMA_M0} · γM2 {GAMMA_M2} · γM3 {GAMMA_M3}")
    add(f"  동적계수   박리 물림 ψ {PSI_DYN} · 지진 수평 {SEISMIC}W")
    add(f"  볼트 이용률 상한 0.70 (제작 여유)")
    add("")
    add("── 설계하중 ────────────────────────────────────────────")
    add(f"  패널          {W_PANEL:8.3f} kN/장")
    add(f"  유리          {W_GLASS:8.3f} kN/장")
    add(f"  만권 롤       {W_ROLL:8.3f} kN  ({ROLL_PANELS} 장/롤)")
    add(f"  칼날 카세트   {W_CASS:8.3f} kN/벌")
    add(f"  박리 추력     {F_PEEL_K:8.3f} kN 특성  →  {F_PEEL_D:8.3f} kN 설계 "
        f"(×{PSI_DYN}×{GAMMA_Q})")
    add(f"  가열실 자중   {kn(M_CHAMBER):8.3f} kN  ({M_CHAMBER/1000:.2f} t · 설계 가정)")
    add(f"  갠트리 자중   {kn(M_GANTRY):8.3f} kN  ({M_GANTRY/1000:.2f} t · 설계 가정)")
    add("")
    add("── 볼트 내력표 (EN 1993-1-8) ──────────────────────────")
    add(f"  {'규격':6s}{'등급':7s}{'As':>7s}{'Ft,Rd':>9s}{'Fv,Rd':>9s}{'Fp,C':>9s}"
        f"{'T 건조':>10s}{'T 윤활':>10s}")
    add(f"  {'':6s}{'':7s}{'mm²':>7s}{'kN':>9s}{'kN':>9s}{'kN':>9s}"
        f"{'N·m':>10s}{'N·m':>10s}")
    for grade in ("8.8", "10.9", "A2-70"):
        for size in BOLT_ORDER:
            add(f"  {size:6s}{grade:7s}{BOLTS[size]['As']:7.1f}"
                f"{bolt_tension(size, grade):9.1f}{bolt_shear(size, grade):9.1f}"
                f"{preload(size, grade):9.1f}"
                f"{torque(size, grade, K_DRY):10.0f}{torque(size, grade, K_LUB):10.0f}")
        add("")
    add("── 접합부 검토 ────────────────────────────────────────")
    add(f"  {'ID':5s}{'접합':38s}{'규격':7s}{'등급':7s}{'수':>3s}"
        f"{'N,Ed':>8s}{'V,Ed':>8s}{'이용률':>8s}")
    worst = 0.0
    for j in JOINTS:
        worst = max(worst, j["util"])
        flag = " ‼" if j["util"] > 0.70 else ""
        add(f"  {j['id']:5s}{j['name'][:36]:38s}{j['size']:7s}{j['grade']:7s}"
            f"{j['n']:3d}{j['N']:8.2f}{j['V']:8.2f}{j['util']:8.2f}{flag}")
    add("")
    add(f"  최대 이용률 {worst:.2f}")
    slip = [j for j in JOINTS if j["slip"]]
    for j in slip:
        add(f"  {j['id']} 마찰접합 — Fs,Rd {j['Fs']:.1f} kN · 이용률 {j['slip_util']:.2f}")
    add("")
    add("── 체결력·토크 (접합부별) ─────────────────────────────")
    add(f"  {'ID':5s}{'규격':7s}{'등급':7s}{'Fp,C':>9s}{'T 건조 K=0.20':>15s}{'T 윤활 K=0.14':>15s}")
    for j in JOINTS:
        add(f"  {j['id']:5s}{j['size']:7s}{j['grade']:7s}{j['Fp']:9.1f}"
            f"{j['T_dry']:15.0f}{j['T_lub']:15.0f}")
    add("")
    add("── 용접 각장 예 ────────────────────────────────────────")
    add(f"  {'접합':30s}{'하중':>8s}{'용접장':>8s}{'판두께':>7s}{'각장':>6s}  근거")
    for name, force, length, mat, t in WELDS:
        z, why = fillet_leg(force, length, mat if mat in MATERIALS else "SS400", t_mm=t)
        add(f"  {name:30s}{force:8.1f}{length:8.0f}{t:7.0f}{z:6.0f}  {why}")
    add("  하중 kN · 용접장·판두께·각장 mm — 양면 필릿 기준")
    add("")
    add("── 지배 검토 — 정렬·피로 ──────────────────────────────")
    add(f"  설계수명 {DESIGN_LIFE_Y} 년 · 가동 {OP_HOURS_Y:.0f} h/년 · "
        f"{NET_TARGET} 장/h  →  {CYCLES_LIFE/1e6:.1f}×10⁶ 회")
    add(f"  {'ID':5s}{'부재':36s}{'지배':32s}{'값':>9s}{'한계':>9s}{'이용률':>8s}")
    cworst = 0.0
    for x in CRITICAL:
        cworst = max(cworst, x["util"])
        flag = " ‼" if x["util"] > 1.0 else ""
        add(f"  {x['id']:5s}{x['member'][:34]:36s}{x['gov'][:30]:32s}"
            f"{x['value']:9.2f}{x['limit']:9.2f}{x['util']:8.2f}{flag}")
    add(f"  단위는 부재별 — 처짐 mm · 응력범위 MPa")
    add("")
    add("── 앵커 (EN 1992-4 · 접착식 · C25/30 이상) ────────────")
    add(f"  {'기초':6s}{'설비':26s}{'규격':7s}{'hef':>6s}{'강재':>8s}"
        f"{'콘':>8s}{'접착':>8s}{'지배':>10s}{'연단':>7s}{'간격':>7s}{'기초t':>7s}")
    for a in ANCHORS:
        add(f"  {a['id']:6s}{a['eq'][:24]:26s}{a['size']:7s}{a['hef']:6.0f}"
            f"{a['steel']:8.1f}{a['cone']:8.1f}{a['bond']:8.1f}"
            f"{a['gov']:>10s}{a['edge']:7.0f}{a['spacing']:7.0f}{a['slab']:7.0f}")
    add("  내력 kN · hef·연단·간격·기초두께 mm — 전 앵커에서 콘크리트측이 지배한다")
    add("")
    add("── 부재표 ──────────────────────────────────────────────")
    add(f"  {'모듈':7s}{'부재':22s}{'단면·두께':30s}{'재질':10s}")
    for mod, part, sec, mat, gov in MEMBERS:
        add(f"  {mod:7s}{part:22s}{sec:30s}{mat:10s}")
    add("")
    add("=" * 78)
    ok = worst <= 0.70 and max(x["util"] for x in CRITICAL) <= 1.0
    add(f"볼트 최대 {worst:.2f} (≤0.70) · 정렬·피로 최대 "
        f"{max(x['util'] for x in CRITICAL):.2f} (≤1.00)" if ok
        else f"‼ 초과 항목 있음 — 볼트 {worst:.2f} · 정렬·피로 "
             f"{max(x['util'] for x in CRITICAL):.2f}")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
