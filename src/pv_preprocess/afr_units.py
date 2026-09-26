# -*- coding: utf-8 -*-
"""AFR-101 두 핵심 유닛의 **부품 구성** — 단축 인출 유닛과 장축 인발 LM 유닛.

플랜트 3D 는 축척이 50 m 다. 거기서 실린더는 원기둥 하나, LM 캐리지는 상자
하나여야 한다 — 그 축척에서 글랜드와 볼 순환로를 그리면 화면만 무거워지고
아무것도 안 보인다. 그래서 "실제로 어떻게 생겼고 어떻게 움직이는가" 는 늘
부품표 글자에만 있었다.

이 모듈은 그 두 유닛을 **부품 단위로** 편다. 치수는 새로 정하지 않는다 —
보어·로드·행정·작동압은 `afr.py` 가 정반 두께에서 유도한 값이고, 롤러 Ø26×12 와
홈 20×14 는 규격 트랙롤러 선정에서 나온 값이며, 재질·공차·수량은 통합 설계도
부품표(`AFR-SA-301` 등)에 있는 것 그대로다. 여기서 더하는 것은 **구성**이다:
배럴 안에 무엇이 있고, 로드가 쇠막대에 어떻게 물리고, LM 블록이 레일 어디를
잡는가. 카탈로그 값(35급 레일 단면, 캠팔로워 스터드)은 계획값으로 밝혀 둔다.

    PYTHONPATH=src python -c "from pv_preprocess import afr_units; print(afr_units.summary())"
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import afr, frames, kinematics

# ── 35급 프로파일 레일 — 카탈로그 계획값 ────────────────────────────────
#: 레일 폭·높이 (mm). 35 급 표준 단면.
RAIL_W_MM, RAIL_H_MM = 34.0, 28.0
#: 레일 볼트 피치와 통구멍 (mm).
RAIL_PITCH_MM, RAIL_BOLT_MM = 80.0, 9.0
#: LM 블록 — 폭 × 길이 × 높이 (mm). 35 급 표준 블록.
BLOCK_W_MM, BLOCK_L_MM, BLOCK_H_MM = 100.0, 106.0, 48.0
#: 엔드캡(볼 순환로 반환부) 두께와 그리스 니플 (mm).
BLOCK_CAP_MM, NIPPLE_MM = 14.0, 8.0
#: 한 캐리지에 쓰는 블록 수 — 모멘트를 받으려면 둘이다.
BLOCKS_PER_CARRIAGE = 2
#: 블록 두 개의 중심 거리 (mm) — 캐리지 모멘트 강성을 정한다.
BLOCK_SPAN_MM = 160.0

# ── 캠팔로워(트랙롤러) 스터드 — 카탈로그 계획값 ─────────────────────────
#: 스터드 나사와 길이 (mm).
STUD_THREAD_MM, STUD_LEN_MM = 12.0, 30.0
#: 스터드 플랜지(칼라) 지름·두께 (mm).
STUD_FLANGE_D_MM, STUD_FLANGE_T_MM = 20.0, 6.0
#: 롤러 피치 (mm) — 캐리지 폭 안에서 4 개가 홈 벽을 나눠 문다.
ROLLER_PITCH_MM = 38.0

# ── 유압 실린더 구성 — ISO 6020-2 통상 비율의 계획값 ────────────────────
#: 헤드측·캡측 엔드캡 두께 (mm).
CYL_CAP_T_MM = 32.0
#: 글랜드(로드 부시) 돌출 길이 (mm).
GLAND_LEN_MM = 26.0
#: 포트 호칭 외경과 길이 (mm) — G3/8 상당.
PORT_D_MM, PORT_LEN_MM = 20.0, 26.0
#: 로드 끝 나사부 길이와 조임 너트 대변 (mm).
ROD_THREAD_MM, ROD_NUT_AF_MM = 40.0, 41.0
#: 로드가 쇠막대에 물리는 클레비스 지름·길이 (mm).
CLEVIS_D_MM, CLEVIS_L_MM = 56.0, 45.0

#: 스토퍼 완충 패드 두께 (mm) — PU 70A.
STOPPER_PAD_MM = 12.0


@dataclass(frozen=True)
class Part:
    """유닛 안의 한 부품 — 형상·자리·역할이 한 줄에 있다.

    `shape` 는 3D 가 그리는 원형이다: box · cyl(축 x/y/z) · tube · rail(스윕).
    `size` 와 `pos` 는 유닛 로컬 좌표 (mm).
    """

    key: str
    name: str
    qty: int
    shape: str
    size: tuple[float, float, float]
    pos: tuple[float, float, float]
    material: str
    role: str                       # 이 부품이 하는 일 (한 문장)
    axis: str = "x"                 # cyl·tube 의 축
    mirror: tuple[str, ...] = ()    # 이 축들로 거울상을 만든다
    color: str = "steel"
    spec: str = ""
    explode: tuple[float, float, float] = (0.0, 0.0, 0.0)
    catalog: str = ""               # 통합 설계도 부품표 번호
    flip: bool = False              # 압출재 단면의 u 축을 뒤집는다 (바깥면이 어느 쪽인가)


@dataclass(frozen=True)
class Unit:
    key: str
    name: str
    sheet: str
    envelope_mm: tuple[float, float, float]
    #: 기본 시점이 담아야 하는 반경 (mm) — 레일처럼 긴 부재가 있어도 볼 것은 유닛이다.
    view_r_mm: float
    principle: tuple[tuple[str, str], ...]     # (단계, 무슨 일이 일어나는가)
    parts: tuple[Part, ...] = field(default_factory=tuple)


def _f(v: float) -> float:
    return round(v, 3)


# ── ① 단축 인출 유닛 ────────────────────────────────────────────────────
def short_unit() -> Unit:
    """정반 · 내장 실린더 · 쇠막대 · 스토퍼 — 단변을 변 전체로 밀어낸다."""
    a = afr
    px, pz, pt = float(a.PLATEN_X_MM), float(a.PLATEN_Z_MM), float(a.PLATEN_T_MM)
    skin, rib, pitch = a.PLATEN_SKIN_T_MM, a.PLATEN_RIB_T_MM, a.PLATEN_RIB_PITCH_MM
    bore, rod, stroke = float(a.bore_mm()), float(a.rod_mm()), float(a.CYL_STROKE_MM)
    barrel = float(a.barrel_od_mm())
    cyl_z = a.cylinder_z_mm()[1]
    body = stroke + 2 * CYL_CAP_T_MM + GLAND_LEN_MM
    bar_w, bar_h = float(a.BAR_W_MM), float(a.bar_h_mm())
    bar_x = px / 2 + bar_w / 2                       # 정반 바깥면에 붙는다
    rod_out = px / 2 - body / 2 + body / 2           # 배럴 바깥 끝
    n_rib_z = int(pz // pitch) - 1
    n_rib_x = int(px // pitch) - 1

    parts = [
        Part("skin", "PL-251 정반 상·하판", 2, "box", (px, skin, pz),
             (0.0, (pt - skin) / 2, 0.0), "S355 t12", "리브를 덮어 굽힘을 받는 면판이다.",
             mirror=("y",), color="steel", explode=(0, 90, 0),
             spec=f"{px:.0f} × {pz:.0f} × t{skin}", catalog="AFR-PL-251"),
        Part("ribz", "PL-251 세로 리브", n_rib_z, "box", (px, pt - 2 * skin, rib),
             (0.0, 0.0, 0.0), "S355 t12",
             f"피치 {pitch} 로 서서 통짜 대비 강재를 {(1 - a.platen_steel_fraction()) * 100:.0f} % 덜어 낸다.",
             color="dark", spec=f"t{rib} @{pitch}", catalog="AFR-PL-251"),
        Part("ribx", "PL-251 가로 리브", n_rib_x, "box", (rib, pt - 2 * skin, pz),
             (0.0, 0.0, 0.0), "S355 t12", "세로 리브와 격자를 이뤄 포켓 주변을 보강한다.",
             color="dark", spec=f"t{rib} @{pitch}", catalog="AFR-PL-251"),
        Part("endplate", "PL-251 마구리판", 2, "box", (rib, pt - 2 * skin, pz),
             (px / 2 - rib / 2, 0.0, 0.0), "S355 t12",
             "리브 격자를 닫아 상자 단면을 만든다 — 비틀림을 여기서 받는다.",
             mirror=("x",), color="steel", explode=(150, 0, 0),
             spec=f"t{rib}", catalog="AFR-PL-251"),
        Part("pocket", "PL-251 실린더 포켓", 2, "cyl", (float(a.pocket_od_mm()), px, 0.0),
             (0.0, 0.0, cyl_z), "보링면",
             f"배럴 Ø{barrel:.0f} 에 편측 {a.POCKET_CLEAR_MM} 여유. 위아래 살이 "
             f"{a.platen_wall_mm()} mm 남아 최소 {a.MIN_PLATEN_WALL_MM} 을 넘는다.",
             axis="x", mirror=("z",), color="cut", spec=f"Ø{a.pocket_od_mm()} 보링",
             catalog="AFR-PL-251"),
        Part("barrel", "SA-301 실린더 배럴", 2, "cyl", (barrel, body, 0.0),
             (0.0, 0.0, cyl_z), "인발강관 / 크롬도금 내면",
             "정반 **안**에 묻힌다 — 두께 100 이 보어를 정하는 자리다.",
             axis="x", mirror=("z",), color="steel", explode=(0, 0, 260),
             spec=a.cylinder_spec(), catalog="AFR-SA-301"),
        Part("cap", "SA-301 캡측 엔드캡", 2, "cyl", (barrel + 8, CYL_CAP_T_MM, 0.0),
             (-body / 2 - CYL_CAP_T_MM / 2, 0.0, cyl_z), "S45C",
             "밀어내는 쪽 압력을 받는 면이다.", axis="x", mirror=("z",),
             color="dark", explode=(-140, 0, 260), spec=f"t{CYL_CAP_T_MM:.0f}",
             catalog="AFR-SA-301"),
        Part("gland", "SA-301 글랜드·로드 실", 2, "cyl", (barrel + 8, GLAND_LEN_MM, 0.0),
             (body / 2 + GLAND_LEN_MM / 2, 0.0, cyl_z), "S45C / NBR 실",
             "로드를 안내하고 유리 분진을 막는다 — 이 셀은 분진 환경이다.",
             axis="x", mirror=("z",), color="dark", explode=(140, 0, 260),
             spec=f"Ø{rod:.0f} 로드 실", catalog="AFR-SA-301"),
        Part("rod", "SA-301 피스톤 로드", 2, "cyl", (rod, stroke + 120, 0.0),
             (body / 2 + (stroke + 120) / 2, 0.0, cyl_z), "경질크롬 도금 S45C",
             f"행정 {stroke:.0f} 중 {a.push_travel_mm()} 를 쓰고 "
             f"{a.stroke_spare_mm()} 가 남는다 — 스토퍼가 하드스톱이 아닌 이유다.",
             axis="x", mirror=("z",), color="chrome", explode=(300, 0, 260),
             spec=f"Ø{rod:.0f} × {stroke:.0f}", catalog="AFR-SA-301"),
        Part("port", "SA-301 유압 포트 (P/T)", 4, "cyl", (PORT_D_MM, PORT_LEN_MM, 0.0),
             (0.0, pt / 2 + PORT_LEN_MM / 2, cyl_z), "G3/8 / 강관",
             f"HPU-601 {a.HPU_RELIEF_BAR:.0f} bar 릴리프에서 작동 "
             f"{a.working_pressure_bar():.0f} bar 로 쓴다.",
             axis="y", mirror=("z", "x"), color="orange", explode=(0, 120, 0),
             spec=f"작동 {a.working_pressure_bar():.0f} bar", catalog="AFR-SA-301"),
        Part("clevis", "로드 끝 클레비스", 2, "cyl", (CLEVIS_D_MM, CLEVIS_L_MM, 0.0),
             (bar_x - bar_w / 2 - CLEVIS_L_MM / 2, 0.0, cyl_z), "S45C",
             "로드 둘을 쇠막대 하나에 묶어 점하중을 선하중으로 바꾼다.",
             axis="x", mirror=("z",), color="steel", explode=(200, 0, 260),
             spec=f"Ø{CLEVIS_D_MM:.0f} × {CLEVIS_L_MM:.0f}", catalog="AFR-PB-261"),
        Part("nut", "로드 조임 너트", 2, "cyl", (ROD_NUT_AF_MM, 18.0, 0.0),
             (bar_x - bar_w / 2 - CLEVIS_L_MM - 9.0, 0.0, cyl_z), "S45C",
             "인출 반력이 진동으로 풀리지 않게 막는다.", axis="x", mirror=("z",),
             color="dark", explode=(240, 0, 260), spec=f"대변 {ROD_NUT_AF_MM:.0f}",
             catalog="AFR-PB-261"),
        Part("bar", "PB-261 쇠막대", 1, "box", (bar_w, bar_h, float(a.bar_length_mm())),
             (bar_x, -(bar_h - pt) / 2, 0.0), "S355 평강",
             f"변 전체를 한 몸으로 {a.push_travel_mm()} mm 민다. 등분포 "
             f"{a.bar_line_load_n_per_mm()} N/mm 에서 굽힘 {a.bar_stress_mpa()} MPa · "
             f"중앙 처짐 {a.bar_sag_mm()} mm — 그만큼 가운데가 뒤처진다.",
             color="orange", explode=(360, 0, 0),
             spec=f"{bar_w:.0f} × {bar_h:.0f} × {a.bar_length_mm():,} · {a.bar_mass_kg()} kg",
             catalog="AFR-PB-261"),
        Part("work", "단변 알루미늄 프레임 (참고)", 1, "frame", (0.0, 0.0, 1250.0),
             (bar_x + bar_w / 2 + (frames.PROFILE_W_MM - frames.profile()["cu_mm"]),
              -(bar_h - pt) / 2 + 8.0, 0.0),
             "6063-T5 압출재",
             f"쇠막대가 미는 대상이다. 변 전체가 한 번에 {a.push_travel_mm()} mm 나가 "
             "스토퍼에 걸린다 — 점이 아니라 선으로 민다.",
             axis="z", color="ghost", explode=(300, 0, 0), flip=True,
             spec="단면 75 × 75 · 참고 표시", catalog="—"),
        Part("stopface", "ST-241 프레임 스토퍼", 2, "box", (60.0, 95.0, 180.0),
             (bar_x + 150.0, 0.0, float(a.STOPPER_Z_MM)), "S355",
             f"밀려난 단변이 이 면에 걸려 선다. 위 립 {a.STOPPER_LIP_MM} mm 가 "
             "프레임이 타고 넘는 것을 막는다.",
             mirror=("z",), color="orange", explode=(140, 0, 0),
             spec=f"립 {a.STOPPER_LIP_MM} mm", catalog="AFR-ST-241"),
        Part("stoppad", "ST-241 완충 패드", 2, "box", (STOPPER_PAD_MM, 60.0, 160.0),
             (bar_x + 150.0 - 30.0 - STOPPER_PAD_MM / 2, 0.0, float(a.STOPPER_Z_MM)),
             "PU 70A", "알루미늄 모서리가 찍히지 않게 받는다.",
             mirror=("z",), color="rubber", explode=(90, 0, 0),
             spec=f"t{STOPPER_PAD_MM:.0f}", catalog="AFR-ST-241"),
        Part("stopbeam", "ST-241 스토퍼 지지빔", 1, "box", (40.0, 120.0, 2420.0),
             (bar_x + 150.0 + 50.0, -90.0, 0.0), "S355",
             "스토퍼 넷을 함께 받아 베이스 프레임으로 반력을 보낸다.",
             color="frame", explode=(200, -60, 0), spec="40 × 120 × 2,420",
             catalog="AFR-ST-241"),
    ]
    return Unit(
        key="short", name="단축 인출 유닛 (정반 내장 실린더 · 쇠막대 · 스토퍼)",
        sheet="PV-AFR-101-ASM-4201",
        envelope_mm=(px + bar_w + 260.0, float(a.bar_h_mm()) + pt, pz),
        view_r_mm=900.0,
        principle=(
            ("① 정반 하강", f"CL-221 4점 클램프가 정반 2 매를 {a.platen_lift_mm()} mm "
                          f"내려 {a.PLATEN_SPEED_MM_S:.0f} mm/s 로 패널을 누른다. "
                          f"자중 {a.platen_weight_kn()} kN 을 뺀 순 압착력 {a.clamp_net_kn()} kN."),
            ("② 가압", f"HPU-601 이 {a.working_pressure_bar():.0f} bar 를 정반당 2 본에 "
                     f"넣는다 (릴리프 {a.HPU_RELIEF_BAR:.0f}). 피스톤 면적 "
                     f"{a.piston_area_mm2():,.0f} mm² × 2 → {a.required_push_kn()} kN."),
            ("③ 쇠막대 전진", f"로드 둘이 클레비스로 묶인 막대를 {a.CYL_SPEED_MM_S:.0f} mm/s 로 "
                          f"민다. 막대가 단변 **전체**를 동시에 밀어 점하중이 아니라 "
                          f"{a.bar_line_load_n_per_mm()} N/mm 선하중이 된다."),
            ("④ 스토퍼 정지", f"{a.push_travel_mm()} mm 나온 프레임이 스토퍼 면에 걸려 선다. "
                          f"행정 {stroke:.0f} 중 {a.stroke_spare_mm()} 가 남아 실린더가 "
                          f"하드스톱을 때리지 않는다."),
            ("⑤ 복귀·회수", "로드가 되돌아가고 FH-501 슈트가 단변 프레임을 수거함에 넣는다. "
                        "두 정반이 **동시에** 밀어야 반력이 크로스헤드 안에서 상쇄된다."),
        ),
        parts=tuple(parts))


# ── ② 장축 인발 LM 유닛 ─────────────────────────────────────────────────
def long_unit() -> Unit:
    """레일 · LM 블록 · 캐리지 · 롤러 헤드 — 홈에 걸어 당기며 주행한다."""
    a = afr
    rd, rh = float(a.roller_d_mm()), float(a.roller_h_mm())
    n_roll = a.rollers_per_carriage()
    reach = float(a.roller_reach_mm())
    span = (n_roll - 1) * ROLLER_PITCH_MM
    plate = (320.0, 180.0, 260.0)
    head = (span + 60.0, 90.0, 100.0)

    parts = [
        Part("rail", "LA-401 35급 LM 레일", 2, "rail", (RAIL_W_MM, RAIL_H_MM, 2900.0),
             (0.0, -BLOCK_H_MM / 2 - RAIL_H_MM / 2, 0.0), "고탄소강 유도경화",
             f"직진도를 심으로 잡는다 — 레일 평행도 0.10 이 인발 정밀도를 정한다. "
             f"볼트 피치 {RAIL_PITCH_MM:.0f} · 통구멍 Ø{RAIL_BOLT_MM:.0f}.",
             color="chrome", explode=(0, -160, 0),
             spec=f"{RAIL_W_MM:.0f} × {RAIL_H_MM:.0f} × 2,900", catalog="AFR-LA-401"),
        Part("block", "LA-401 LM 블록", BLOCKS_PER_CARRIAGE, "box",
             (BLOCK_L_MM, BLOCK_H_MM, BLOCK_W_MM), (BLOCK_SPAN_MM / 2, 0.0, 0.0),
             "블록강 / 볼 순환", f"블록 {BLOCKS_PER_CARRIAGE} 개가 피치 "
             f"{BLOCK_SPAN_MM:.0f} 로 앉아 인발 반력의 **모멘트**를 받는다 — "
             "하나면 캐리지가 홈에서 비틀린다.",
             mirror=("x",), color="steel", explode=(0, -90, 0),
             spec=f"{BLOCK_L_MM:.0f} × {BLOCK_W_MM:.0f} × {BLOCK_H_MM:.0f}",
             catalog="AFR-LA-401"),
        Part("endcap", "LM 블록 엔드캡 (볼 반환부)", 4, "box",
             (BLOCK_CAP_MM, BLOCK_H_MM - 4, BLOCK_W_MM),
             (BLOCK_SPAN_MM / 2 + BLOCK_L_MM / 2 - BLOCK_CAP_MM / 2, 0.0, 0.0),
             "수지 성형", "볼을 부하권에서 무부하권으로 돌려보내는 U 턴이다.",
             mirror=("x2",), color="dark", explode=(0, -90, 0),
             spec=f"t{BLOCK_CAP_MM:.0f}", catalog="AFR-LA-401"),
        Part("nipple", "그리스 니플", 2, "cyl", (NIPPLE_MM, 16.0, 0.0),
             (BLOCK_SPAN_MM / 2, BLOCK_H_MM / 2 + 8.0, BLOCK_W_MM / 2 - 12.0),
             "황동", "유리 분진 환경이라 급지 주기가 수명을 정한다.",
             axis="y", mirror=("x",), color="orange", explode=(0, 60, 0),
             spec=f"Ø{NIPPLE_MM:.0f}", catalog="AFR-LA-401"),
        Part("plate", "LA-401 캐리지 베이스판", 1, "box", (plate[0], 40.0, plate[2]),
             (0.0, BLOCK_H_MM / 2 + 20.0, 0.0), "S355 가공",
             f"블록 둘을 한 몸으로 묶는다. 주행 {a.LM_STROKE_MM:,} mm 를 "
             f"{a.LM_SPEED_MM_S:.0f} mm/s 로 간다.",
             color="orange", explode=(0, 120, 0),
             spec=f"{plate[0]:.0f} × {plate[2]:.0f} × t40", catalog="AFR-LA-401"),
        Part("platerib", "캐리지 측 리브", 2, "box", (plate[0], plate[1] - 40.0, 22.0),
             (0.0, BLOCK_H_MM / 2 + 40.0 + (plate[1] - 40.0) / 2, plate[2] / 2 - 11.0),
             "S355 가공", "롤러 헤드가 받는 인발 모멘트를 베이스판으로 넘긴다.",
             mirror=("z",), color="orange", explode=(0, 170, 0),
             spec=f"t22 × {plate[1] - 40.0:.0f}", catalog="AFR-LA-401"),
        Part("slide", "헤드 진입 슬라이드", 1, "box", (140.0, 60.0, reach + 60.0),
             (0.0, BLOCK_H_MM / 2 + plate[1] + 30.0, reach / 2),
             "S355 / 소형 LM", f"롤러 헤드를 홈 쪽으로 {reach:.0f} mm 넣고 "
             f"인발 {a.pull_travel_mm()} mm 를 그대로 유지한 채 주행한다.",
             color="steel", explode=(0, 190, 0), spec=f"진입 {reach:.0f} mm",
             catalog="AFR-LA-401"),
        Part("head", "LA-401 롤러 헤드", 1, "box", head,
             (0.0, BLOCK_H_MM / 2 + plate[1] + 30.0, reach),
             "S355 가공", f"롤러 {n_roll} 개를 피치 {ROLLER_PITCH_MM:.0f} 로 달아 "
             f"홈 벽에 하중을 나눈다.",
             color="dark", explode=(0, 250, 90), spec=f"롤러 {n_roll} 개",
             catalog="AFR-LA-401"),
        Part("roller", "LA-401 홈 인발 롤러 (캠팔로워)", n_roll, "cyl", (rd, rh, 0.0),
             (0.0, BLOCK_H_MM / 2 + plate[1] + 30.0, reach + head[2] / 2 + rd / 2),
             "SKD11 경화 / 니들베어링",
             f"홈({a.GROOVE_H_MM}×{a.GROOVE_D_MM})에 들어가 바닥에 걸친다. "
             f"{frames.PEEL_FORCE_N:.0f} N 을 {n_roll} 개로 나눠 접촉압 "
             f"{a.roller_contact_mpa()} MPa — 허용 {a.roller_allow_mpa()} MPa 아래라 "
             "홈에 압흔이 남지 않는다.",
             axis="y", mirror=("row",), color="chrome", explode=(0, 320, 190),
             spec=f"Ø{rd:.0f} × {rh:.0f} × {n_roll} 개", catalog="AFR-LA-401"),
        Part("stud", "캠팔로워 스터드", n_roll, "cyl", (STUD_THREAD_MM, STUD_LEN_MM, 0.0),
             (0.0, BLOCK_H_MM / 2 + plate[1] + 30.0 - STUD_LEN_MM / 2 - rh / 2,
              reach + head[2] / 2 + rd / 2),
             "SCM435", "헤드에 나사로 물려 롤러의 편심 조정을 받는다.",
             axis="y", mirror=("row",), color="dark", explode=(0, 260, 190),
             spec=f"M{STUD_THREAD_MM:.0f} × {STUD_LEN_MM:.0f}", catalog="AFR-LA-401"),
        Part("flange", "스터드 칼라", n_roll, "cyl",
             (STUD_FLANGE_D_MM, STUD_FLANGE_T_MM, 0.0),
             (0.0, BLOCK_H_MM / 2 + plate[1] + 30.0 - rh / 2 - STUD_FLANGE_T_MM / 2,
              reach + head[2] / 2 + rd / 2),
             "SCM435", "롤러 축방향 위치를 잡는다.", axis="y", mirror=("row",),
             color="steel", explode=(0, 290, 190), spec=f"Ø{STUD_FLANGE_D_MM:.0f}",
             catalog="AFR-LA-401"),
        Part("work", "장변 알루미늄 프레임 (참고)", 1, "frame", (0.0, 0.0, 560.0),
             (0.0,
              # 홈(단면 v 30…50, 도심 v 29.97)의 한가운데가 롤러 축과 만나야 한다
              BLOCK_H_MM / 2 + plate[1] + 30.0
              - (float(frames.GROOVE_V0_MM) + float(frames.GROOVE_H_MM) / 2
                 - frames.profile()["cv_mm"]),
              # 롤러 바깥면이 홈 바닥에 닿는 자리에서 도심을 역산한다
              reach + head[2] / 2 + rd - float(a.GROOVE_D_MM)
              + frames.profile()["cu_mm"]),
             "6063-T5 압출재",
             f"실제로 무는 대상이다. 롤러가 바깥면 홈({a.GROOVE_H_MM}×{a.GROOVE_D_MM})으로 "
             f"들어가 바닥에 걸치고 {a.pull_travel_mm()} mm 바깥으로 당긴다.",
             color="ghost", explode=(0, 0, 260), spec="단면 75 × 75 · 참고 표시",
             catalog="—"),
        Part("drive", "장축 5.0 kW 구동 인터페이스", 1, "box", (180.0, 160.0, 160.0),
             (-plate[0] / 2 - 90.0, BLOCK_H_MM / 2 + plate[1] / 2, 0.0),
             "서보 / 감속기", "양쪽 캐리지를 동기 구동한다 — 한쪽만 당기면 프레임이 비틀린다.",
             color="frame", explode=(-260, 0, 0), spec="5.0 kW · 3.0 kN·m",
             catalog="AFR-LA-401"),
    ]
    return Unit(
        key="long", name="장축 인발 LM 유닛 (레일 · 블록 · 캐리지 · 롤러 헤드)",
        sheet="PV-AFR-LA-4301",
        envelope_mm=(2900.0, BLOCK_H_MM + plate[1] + 260.0, BLOCK_W_MM + reach + 200.0),
        view_r_mm=560.0,
        principle=(
            ("① 헤드 진입", f"슬라이드가 롤러 헤드를 홈 쪽으로 {reach:.0f} mm 넣는다. "
                         f"롤러 Ø{rd:.0f} 가 깊이 {a.GROOVE_D_MM} 홈에 들어가 "
                         f"{a.roller_protrusion_mm()} mm 만 밖에 남는다."),
            ("② 홈 걸침", f"롤러 {n_roll} 개가 홈 바닥에 닿아 걸친다. 하중선이 압출재 면에서 "
                       f"멀어지지 않아야 프로파일이 비틀리지 않는다 — 그래서 외경이 "
                       f"홈 깊이의 {a.ROLLER_PROTRUSION_RATIO} 배를 넘지 않는다."),
            ("③ 끝단 벌림", f"캐리지가 제자리에서 {a.pull_travel_mm()} mm 바깥으로 당겨 "
                         f"접착을 연다. 접착 위의 보라 휨이 β⁻¹ 만큼의 구간에 퍼진다."),
            ("④ 주행 인발", f"LM 을 타고 끝에서 중앙으로 {a.LM_STROKE_MM:,} mm 를 "
                         f"{a.LM_SPEED_MM_S:.0f} mm/s 로 간다 ({a.lm_travel_time_s()} s). "
                         f"롤러가 접착 전선과 **같이** 가므로 자유 길이가 롤러 반경 "
                         f"{a.roller_free_length_mm()} mm 뿐이다."),
            ("⑤ 양측 동기", f"한 변에 캐리지 {a.CARRIAGE_PER_SIDE} 대, 두 변에 4 대가 같이 당긴다. "
                         "동기가 깨지면 프레임이 비틀려 홈에서 롤러가 빠진다."),
        ),
        parts=tuple(parts))


def units() -> tuple[Unit, ...]:
    return (short_unit(), long_unit())


def rail_outline() -> tuple[tuple[float, float], ...]:
    """35급 프로파일 레일 단면 (mm) — 허리가 잘록한 표준 꼴.

    3D 가 이 다각형을 스윕한다. 볼 홈 두 줄이 허리에 나 있고, 위쪽이 볼트
    자리다. 카탈로그 계획값이며 실물 레일 도면이 오면 여기만 고친다.
    """
    w, h = RAIL_W_MM / 2.0, RAIL_H_MM
    return (
        (-w, 0.0), (w, 0.0), (w, h * 0.28),
        (w * 0.74, h * 0.42), (w * 0.74, h * 0.58),      # 아래 볼 홈
        (w, h * 0.72), (w, h), (w * 0.62, h),
        (w * 0.62, h * 0.86), (-w * 0.62, h * 0.86), (-w * 0.62, h),
        (-w, h), (-w, h * 0.72),
        (-w * 0.74, h * 0.58), (-w * 0.74, h * 0.42),    # 위 볼 홈
        (-w, h * 0.28),
    )


def summary() -> dict[str, object]:
    return {
        "units": [
            {"key": u.key, "name": u.name, "sheet": u.sheet,
             "envelopeMm": list(u.envelope_mm),
             "partKinds": len(u.parts),
             "partCount": sum(p.qty for p in u.parts),
             "steps": len(u.principle)}
            for u in units()
        ],
        "railOutlinePoints": len(rail_outline()),
        "cylinderSpec": afr.cylinder_spec(),
        "rollerSpec": f"Ø{afr.roller_d_mm()} × {afr.roller_h_mm()} × "
                      f"{afr.rollers_per_carriage()} 개",
    }
