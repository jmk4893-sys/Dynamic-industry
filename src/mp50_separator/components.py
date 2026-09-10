"""아세이별 부품표 (BOM).

부품 분류는 [D2] MP50-DR-000 의 A~K 아세이 체계를 유지했다. 그 분류가 제작
발주 단위와 맞기 때문이다 — 탱크는 판금 업체, 구동부는 교반기 벤더, 프레임은
파이프 업체로 각각 나간다.

**질량은 적지 않고 계산한다.** ``geometry.py`` 의 치수와 재질 밀도에서
유도하므로 치수를 고치면 질량도 따라 움직인다. 손으로 적은 표는 치수가 바뀐
뒤에도 옛 숫자로 남아 있다가 운반·양중 계획을 틀리게 만든다.

``status``
    ``RELEASE``      제작 착수 가능.
    ``PROPOSED``     충돌 해결안이 들어간 부품 — 발주 전 승인 필요.
    ``HOLD``         벤더 GA 전에는 치수를 확정하지 않는다.
    ``VENDOR``       구매품 — 치수는 벤더 표준을 따른다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import COVER_NOZZLES, GEOMETRY, NOZZLES, Geometry

#: 재질별 밀도 (kg/m³).
DENSITY = {
    "SUS304": 7930.0,
    "SUS316L": 8000.0,
    "EPDM": 1200.0,
    "PTFE": 2200.0,
    "PC": 1200.0,
    "붕규산유리": 2230.0,
}


def plate_kg(area_mm2: float, thickness_mm: float, material: str) -> float:
    """판재 질량."""
    return area_mm2 * thickness_mm * 1e-9 * DENSITY[material]


def tube_kg(od_mm: float, wall_mm: float, length_mm: float, material: str) -> float:
    """관재 질량."""
    id_mm = od_mm - 2.0 * wall_mm
    return math.pi / 4.0 * (od_mm ** 2 - id_mm ** 2) * length_mm * 1e-9 * DENSITY[material]


def bar_kg(od_mm: float, length_mm: float, material: str) -> float:
    """환봉 질량."""
    return math.pi / 4.0 * od_mm ** 2 * length_mm * 1e-9 * DENSITY[material]


def annulus_mm2(od_mm: float, id_mm: float) -> float:
    return math.pi / 4.0 * (od_mm ** 2 - id_mm ** 2)


@dataclass(frozen=True)
class Part:
    """부품 하나.

    Attributes:
        no: 부품번호 (A-01 …).
        name: 품명.
        spec: 규격 — 도면 부품표에 그대로 들어간다.
        material: 재질. 구매품은 '-'.
        qty: 수량.
        unit_kg: 1개 질량. 0 이면 도면에 '-' 로 적는다 (미확정 구매품).
        status: RELEASE / PROPOSED / HOLD / VENDOR.
        note: 가공·검사 지시.
    """

    no: str
    name: str
    spec: str
    material: str
    qty: int
    unit_kg: float = 0.0
    status: str = "RELEASE"
    note: str = ""

    @property
    def total_kg(self) -> float:
        return self.unit_kg * self.qty


@dataclass(frozen=True)
class Assembly:
    """아세이 하나 — 도면 1매에 대응한다.

    Attributes:
        code: 아세이 부호 (A~K).
        drawing: 도면번호.
        name: 아세이명.
        purpose: 이 아세이가 하는 일. 도면 표제란 부제로 들어간다.
        parts: 부품 목록.
        vendor_scope: 벤더 공급 범위 (있으면).
    """

    code: str
    drawing: str
    name: str
    purpose: str
    parts: tuple[Part, ...]
    vendor_scope: str = ""

    @property
    def total_kg(self) -> float:
        return sum(p.total_kg for p in self.parts)

    @property
    def piece_count(self) -> int:
        return sum(p.qty for p in self.parts)

    @property
    def held(self) -> tuple[Part, ...]:
        return tuple(p for p in self.parts if p.status == "HOLD")


def _tank(g: Geometry) -> Assembly:
    """A — 탱크 아세이. 판금 업체 발주 단위."""
    shell_mid = g.tank_id_mm + g.shell_thickness_mm
    cone_lateral = math.pi * (g.tank_id_mm + g.cone_outlet_id_mm) / 2.0 * g.cone_slant_length_mm
    nozzle_kg = sum(
        tube_kg(n.tube_od_mm + 4.0, 2.0, n.projection_mm, "SUS304") + 0.18 for n in NOZZLES
    ) / len(NOZZLES)
    return Assembly(
        code="A",
        drawing="MP50-A",
        name="탱크 아세이",
        purpose="염수·분말을 담고 분산·정치·층분리가 일어나는 본체",
        parts=(
            Part("A-01", "동체 (Shell)", f"Ø{g.tank_id_mm:.0f} ID × H{g.shell_height_mm:.0f} × t{g.shell_thickness_mm:.0f}",
                 "SUS304", 1, plate_kg(math.pi * shell_mid * g.shell_height_mm, g.shell_thickness_mm, "SUS304"),
                 "RELEASE", f"전개 {g.shell_development_length_mm:.1f} × {g.shell_height_mm:.0f} · 세로이음 맞대기 전용입 · 내면 평활 연삭"),
            Part("A-02", "원뿔 (Cone)", f"Ø{g.tank_id_mm:.0f} → Ø{g.cone_outlet_id_mm:.1f}, 60°, H{g.cone_truncated_height_mm:.1f}",
                 "SUS304", 1, plate_kg(cone_lateral, g.cone_thickness_mm, "SUS304"),
                 "PROPOSED", f"전개 부채꼴 R{g.cone_development_outer_r_mm:.0f}/R{g.cone_development_inner_r_mm:.1f} × {g.cone_development_angle_deg:.0f}° (C1·C3)"),
            Part("A-03", "배출 스터브", 'Ø63.5 × t2.0 × L40 + 2" 페룰', "SUS316L", 1,
                 tube_kg(63.5, 2.0, 40.0, "SUS316L") + 0.22, "PROPOSED", "C3 — 2 in 으로 붙이고 기본형은 리듀싱 클램프"),
            Part("A-04", "동체 노즐", f"{len(NOZZLES)}종 · 노즐표 참조", "SUS304", len(NOZZLES),
                 nozzle_kg, "RELEASE", "전용입 set-through · 내면 평활 연삭 · 잔여 크레비스 없을 것"),
            Part("A-05", "상단 플랜지", f"OD Ø{g.top_flange_od_mm:.0f} × ID Ø{g.shell_od_mm:.0f} × t{g.top_flange_thickness_mm:.0f}",
                 "SUS304", 1, plate_kg(annulus_mm2(g.top_flange_od_mm, g.shell_od_mm), g.top_flange_thickness_mm, "SUS304"),
                 "PROPOSED", f"PCD Ø{g.top_flange_pcd_mm:.0f} · {g.top_flange_bolts}-Ø14 · O-링 홈 Ø430 W5 D3 (C8)"),
            Part("A-06", "지지링", f"OD Ø{g.support_ring_od_mm:.0f} × ID Ø{g.shell_od_mm:.0f} × t{g.support_ring_thickness_mm:.0f}",
                 "SUS304", 1, plate_kg(annulus_mm2(g.support_ring_od_mm, g.shell_od_mm), g.support_ring_thickness_mm, "SUS304"),
                 "RELEASE", f"Z{g.support_ring_z:.0f} — 동체/콘 용접선 위 {g.support_ring_z - g.shell_bottom_z:.0f} mm 에 붙인다"),
            Part("A-07", "보강 거싯", "100 × 100 × t5, 90° 등분", "SUS304", 4,
                 plate_kg(100.0 * 100.0 / 2.0, 5.0, "SUS304"), "RELEASE", "지지링 하면 ↔ 콘 외면"),
            Part("A-08", "양중 러그", "t6, Ø20 홀", "SUS304", 3,
                 plate_kg(70.0 * 50.0, 6.0, "SUS304"), "RELEASE", "Z900, 120° 등분 · 공차 총질량 기준"),
        ),
    )


def _cover(g: Geometry) -> Assembly:
    """B — 상부 커버 아세이."""
    return Assembly(
        code="B",
        drawing="MP50-B",
        name="상부 커버 아세이",
        purpose="구동부·씰·계측을 얹고 분산 중 튀어오름을 막는 뚜껑",
        parts=(
            Part("B-01", "커버판", f"Ø{g.top_flange_od_mm:.0f} × t{g.cover_thickness_mm:.0f}", "SUS304", 1,
                 plate_kg(math.pi / 4.0 * g.top_flange_od_mm ** 2, g.cover_thickness_mm, "SUS304"),
                 "PROPOSED", f"PCD Ø{g.top_flange_pcd_mm:.0f} · {g.top_flange_bolts}-Ø14 · 평면도 0.5"),
            Part("B-02", "중앙 보강 허브", f"Ø{g.cover_hub_od_mm:.0f} × t{g.cover_hub_thickness_mm:.0f}, 보어 Ø60",
                 "SUS304", 1, plate_kg(annulus_mm2(g.cover_hub_od_mm, 60.0), g.cover_hub_thickness_mm, "SUS304"),
                 "HOLD", "볼트 PCD·보어는 교반기 벤더 GA 확정 후 가공 (B1 인터페이스)"),
            Part("B-03", "허브 거싯", "80 × 60 × t5", "SUS304", 4,
                 plate_kg(80.0 * 60.0 / 2.0, 5.0, "SUS304"), "HOLD", "허브 ↔ 커버판 · 벤더 하중 확정 후"),
            Part("B-04", "커버 노즐", f"{len(COVER_NOZZLES)}종 · 노즐표 참조", "SUS304", len(COVER_NOZZLES),
                 tube_kg(16.7, 2.0, 60.0, "SUS304") + 0.16, "RELEASE", "계측은 전부 커버에서 내린다"),
            Part("B-05", "가스켓 O-링", "Ø430 코드 Ø5", "EPDM", 1,
                 math.pi * 430.0 * (math.pi / 4.0 * 25.0) * 1e-9 * DENSITY["EPDM"],
                 "RELEASE", "플랜지 면 홈에 삽입 — 커버는 금속면 착좌 (Z951 유지)"),
            Part("B-06", "체결 볼트 세트", f"{g.top_flange_bolt} × 35 육각 + 너트 + 평·스프링와셔", "SUS304",
                 g.top_flange_bolts, 0.055, "RELEASE", "조임 40 N·m · 대각 2 회전 조임"),
            Part("B-07", "스키머 조절봉 부싱", "M8 관통 부싱 + O-링", "SUS304", 3,
                 0.04, "RELEASE", "PCD Ø330 — 허브 Ø220 바깥"),
        ),
    )


def _drive(g: Geometry) -> Assembly:
    """C — 구동부 아세이. 전량 벤더 스코프이며 인터페이스는 HOLD."""
    return Assembly(
        code="C",
        drawing="MP50-C",
        name="구동부 아세이",
        purpose="교반축을 30~90 rpm 으로 돌리고 축 관통부를 밀봉한다",
        vendor_scope="모터·감속기·씰·커플링·베이스 일체 — GA 승인 전 커버 중앙 가공 금지",
        parts=(
            Part("C-01", "기어드 모터", "0.55 kW, 3φ 220/380 V, IP55, VFD 구동", "-", 1, 28.0,
                 "PROPOSED", "CHK-06 — 정상 소요는 90 W 지만 정착층 재기동 토크가 0.37 kW 를 넘는다"),
            Part("C-02", "감속기", "출력 30~150 rpm, 정토크 VFD", "-", 1, 0.0,
                 "PROPOSED", "CHK-05 — [R] 의 90 rpm 상한으로는 Njs 135 rpm 에 못 미친다 · C-01 일체형 가능"),
            Part("C-03", "축 씰", "고형분용 더블 카트리지 메커니컬 씰", "-", 1, 3.5,
                 "HOLD", "[R] §3 CRITICAL HOLD — 일반 싱글 씰 확정 금지 · 고형분 wt% 제시 후 RFQ"),
            Part("C-04", "커플링", f"Ø{g.shaft_od_mm:.0f} × 벤더 출력축", "-", 1, 1.2,
                 "HOLD", "벤더 출력축 지름·키 확정 후"),
            Part("C-05", "구동 램턴 / 어댑터", "커버 허브 ↔ 씰 ↔ 감속기 플랜지", "SUS304", 1, 4.0,
                 "HOLD", "설치 envelope Z951~Z1420 (H469) 예약"),
            Part("C-06", "보호 커버", "커플링 노출부 차폐, t1.5 절곡", "SUS304", 1,
                 plate_kg(2.0 * math.pi * 90.0 * 160.0, 1.5, "SUS304"), "RELEASE", "회전부 접촉방지 — 인터록 불요, 공구 개방식"),
        ),
    )


def _shaft(g: Geometry) -> Assembly:
    """D — 교반축·임펠러 아세이."""
    shaft_len = 760.0
    blade = plate_kg(g.impeller_blade_radial_mm * g.impeller_blade_width_mm,
                     g.impeller_blade_thickness_mm, "SUS316L")
    hub = tube_kg(g.impeller_hub_od_mm, (g.impeller_hub_od_mm - g.shaft_od_mm) / 2.0,
                  g.impeller_hub_length_mm, "SUS316L")
    return Assembly(
        code="D",
        drawing="MP50-D",
        name="교반축 · 임펠러 아세이",
        purpose="분말을 염수 전체에 고르게 흩는다 — 분리 수단이 아니라 분산 수단",
        parts=(
            Part("D-01", "교반축", f"Ø{g.shaft_od_mm:.0f} h7 × L{shaft_len:.0f}", "SUS316L", 1,
                 bar_kg(g.shaft_od_mm, shaft_len, "SUS316L"), "PROPOSED",
                 "직진도 0.5/600 · 1 차 위험속도는 CHK-07 참조 (운전영역의 9 배 이상)"),
            Part("D-02", "임펠러 (하부)", f"Ø{g.impeller_od_mm:.0f} {g.impeller_blades}PBT{g.impeller_pitch_deg:.0f}° W{g.impeller_blade_width_mm:.0f} t{g.impeller_blade_thickness_mm:.0f}",
                 "SUS316L", 1, hub + g.impeller_blades * blade, "RELEASE",
                 f"Z{g.lower_impeller_z:.0f}±{g.impeller_z_tolerance_mm:.0f} · 조립 후 TIR ≤1.0"),
            Part("D-03", "임펠러 (상부)", f"Ø{g.impeller_od_mm:.0f} {g.impeller_blades}PBT{g.impeller_pitch_deg:.0f}° W{g.impeller_blade_width_mm:.0f} t{g.impeller_blade_thickness_mm:.0f}",
                 "SUS316L", 1, hub + g.impeller_blades * blade, "RELEASE",
                 f"Z{g.upper_impeller_z:.0f}±{g.impeller_z_tolerance_mm:.0f} · 하부와 동일품"),
            Part("D-04", "평행키", "6 × 6 × L50", "SUS316L", 2, bar_kg(6.8, 50.0, "SUS316L"),
                 "RELEASE", "축 키홈 6P9 · 허브 키홈 6JS9"),
            Part("D-05", "세트스크류", "M8 × 8 육각홀 (컵포인트)", "SUS304", 4, 0.004,
                 "RELEASE", "임펠러당 2 개 · 90° 배치 · 키 반대편 가압"),
            Part("D-06", "스러스터 칼라", f"Ø50 × L25, 보어 Ø{g.shaft_od_mm:.0f}", "SUS316L", 2,
                 tube_kg(50.0, 12.5, 25.0, "SUS316L"), "RELEASE", "임펠러 축방향 위치 고정 — Z 공차 소진 방지"),
        ),
    )


def _baffle(g: Geometry) -> Assembly:
    """E — 배플 아세이. C2 로 폭이 바뀐 아세이다."""
    return Assembly(
        code="E",
        drawing="MP50-E",
        name="배플 아세이",
        purpose="선회류를 끊어 축방향 순환을 만든다 — 없으면 표면 소용돌이만 생긴다",
        parts=(
            Part("E-01", "배플판", f"W{g.baffle_width_mm:.0f} × L{g.baffle_length_mm:.0f} × t{g.baffle_thickness_mm:.0f}",
                 "SUS316L", g.baffle_count,
                 plate_kg(g.baffle_width_mm * g.baffle_length_mm, g.baffle_thickness_mm, "SUS316L"),
                 "PROPOSED", f"C2 — 원본 W80 은 임펠러와 36 mm 간섭 · 팁 간극 {g.impeller_tip_clearance_mm:.0f} mm 확보 · 모서리 R2"),
            Part("E-02", "스탠드오프 탭", f"25 × {g.baffle_wall_gap_mm:.0f} × t{g.baffle_thickness_mm:.0f}",
                 "SUS316L", g.baffle_count * 3,
                 plate_kg(25.0 * g.baffle_wall_gap_mm, g.baffle_thickness_mm, "SUS316L"),
                 "RELEASE", f"배플당 3 개 · 벽 이격 {g.baffle_wall_gap_mm:.0f} — 뒤에 분말이 쌓이지 않게 띄운다"),
        ),
    )


def _sparger(g: Geometry) -> Assembly:
    """F — 급기 분산링 아세이."""
    ring_len = math.pi * g.sparger_pcd_mm
    return Assembly(
        code="F",
        drawing="MP50-F",
        name="급기 분산링 아세이",
        purpose="콘 바닥에 공기를 넣어 정착층을 들어올린다 (분산 보조, 부선 아님)",
        parts=(
            Part("F-01", "분산링", f"PCD Ø{g.sparger_pcd_mm:.0f}, Ø{g.sparger_tube_od_mm:.0f} × t{g.sparger_tube_thickness_mm:.1f}",
                 "SUS316L", 1, tube_kg(g.sparger_tube_od_mm, g.sparger_tube_thickness_mm, ring_len, "SUS316L"),
                 "PROPOSED", f"Z{g.sparger_z:.0f}±{g.sparger_z_tolerance_mm:.0f} · 롤벤딩 후 맞대기 1 개소 (C4)"),
            Part("F-02", "분사홀", f"Ø{g.sparger_hole_dia_mm:.1f} × {g.sparger_holes}개, 하향",
                 "-", g.sparger_holes, 0.0, "PROPOSED",
                 f"30° 등분 · 급기 {g.air_max_lpm:.0f} L/min 에서 오리피스 7.9 m/s · 버 제거 필수"),
            Part("F-03", "강하관", f"Ø{g.sparger_tube_od_mm:.0f} × t{g.sparger_tube_thickness_mm:.1f} × L{g.nozzles[2].z_mm - g.sparger_z:.0f}",
                 "SUS316L", 1, tube_kg(g.sparger_tube_od_mm, g.sparger_tube_thickness_mm,
                                       g.nozzles[2].z_mm - g.sparger_z, "SUS316L"),
                 "RELEASE", "N3(Z520) → 링(Z300) · 배플 뒤로 배선해 임펠러 회전면 침범 금지"),
            Part("F-04", "고정 브래킷", "t3 절곡, 콘 내면 용접", "SUS316L", 3,
                 plate_kg(60.0 * 30.0, 3.0, "SUS316L"), "RELEASE", "120° 등분 · 링 편심 ≤3"),
            Part("F-05", "체크밸브", '½" 위생형, 크래킹 20 kPa', "-", 1, 0.25, "VENDOR",
                 "N3 직전 설치 — 급기 정지 시 분말 역류로 홀이 막힌다"),
        ),
    )


def _skimmer(g: Geometry) -> Assembly:
    """G — 스키머 아세이."""
    return Assembly(
        code="G",
        drawing="MP50-G",
        name="스키머 아세이",
        purpose="부상한 폴리머층을 액면에서 걷어낸다",
        parts=(
            Part("G-01", "스키머 링 (위어)", f"Ø{g.skimmer_od_mm:.0f} × H{g.skimmer_height_mm:.0f} × t2",
                 "SUS316L", 1, plate_kg(math.pi * g.skimmer_od_mm * g.skimmer_height_mm, 2.0, "SUS316L"),
                 "RELEASE", f"Z{g.skimmer_z:.0f}±{g.skimmer_z_tolerance_mm:.0f} 조절 · 상단 위어 수평도 1.0"),
            Part("G-02", "타공 바닥판", f"Ø{g.skimmer_od_mm:.0f} × t1.5, Ø2 천공 개공률 30 %",
                 "SUS316L", 1, plate_kg(math.pi / 4.0 * g.skimmer_od_mm ** 2 * 0.7, 1.5, "SUS316L"),
                 "RELEASE", "염수는 빠지고 폴리머는 남는다 — 걸러낸 채로 들어올린다"),
            Part("G-03", "조절봉", "M8 × L250 전산볼트", "SUS316L", 3, bar_kg(8.0, 250.0, "SUS316L"),
                 "RELEASE", "커버 관통 (B-07) · 상하 조절 ±20"),
            Part("G-04", "인양 손잡이", "Ø8 환봉 굽힘", "SUS316L", 1, bar_kg(8.0, 320.0, "SUS316L"),
                 "RELEASE", f"바스켓 외경 Ø{g.skimmer_od_mm:.0f} < 개구 Ø{g.tank_id_mm:.0f} — 통째로 빠진다"),
        ),
    )


def _frame(g: Geometry) -> Assembly:
    """H — 프레임 아세이."""
    tube = g.frame_tube_mm
    wall = g.frame_tube_thickness_mm
    per_m = tube_kg(tube, wall, 1000.0, "SUS304")
    columns = 4 * g.frame_height_mm
    perimeter = 2 * 4 * (g.frame_width_mm - tube)
    cross = 2 * (g.frame_width_mm - 2 * tube)
    mid = 4 * (g.frame_width_mm - tube)
    return Assembly(
        code="H",
        drawing="MP50-H",
        name="프레임 아세이",
        purpose=f"용기를 바닥 +{g.frame_height_mm:.0f} 에 받쳐 배출부 아래 공간을 만든다",
        parts=(
            Part("H-01", "기둥", f"□{tube:.0f} × {tube:.0f} × t{wall:.0f} × L{g.frame_height_mm:.0f}",
                 "SUS304", 4, per_m * g.frame_height_mm / 1000.0, "RELEASE",
                 f"높이는 배출 여유에서 역산 — 배출면 {g.discharge_elevation_mm:.0f}, 밸브 아래 {g.discharge_clearance_mm:.0f} mm"),
            Part("H-02", "상·하부 둘레재", f"□{tube:.0f} × t{wall:.0f} × L{g.frame_width_mm - tube:.0f}",
                 "SUS304", 8, per_m * (g.frame_width_mm - tube) / 1000.0, "RELEASE", "상부 4 + 하부 4"),
            Part("H-03", "상부 크로스레일", f"□{tube:.0f} × t{wall:.0f} × L{g.frame_width_mm - 2 * tube:.0f}",
                 "SUS304", 2, per_m * (g.frame_width_mm - 2 * tube) / 1000.0, "PROPOSED",
                 "Y=±150 — 지지링 Ø480 이 둘레재에 5 mm 밖에 안 걸려 크로스레일이 받는다"),
            Part("H-04", "중간 보강재", f"□{tube:.0f} × t{wall:.0f} × L{g.frame_width_mm - tube:.0f}",
                 "SUS304", 4, per_m * (g.frame_width_mm - tube) / 1000.0, "RELEASE", "Z 중단 — 좌굴·비틀림 억제"),
            Part("H-05", "레벨링 풋", "M16 × 100, 방진 패드 Ø60 일체", "-", 4, 0.35, "VENDOR",
                 "조절 ±25 · 커버 상면 수평도 0.5 를 여기서 잡는다"),
            Part("H-06", "베이스 플레이트", "100 × 100 × t6, Ø14 앵커홀", "SUS304", 4,
                 plate_kg(100.0 * 100.0, 6.0, "SUS304"), "RELEASE",
                 "밑변 550 대 높이 1.7 m — 앵커 없이 세울 수 있으나 시험 중 고정 권장"),
            Part("H-07", "지지 브래킷", "t6, 지지링 볼트 M12", "SUS304", 4,
                 plate_kg(80.0 * 60.0, 6.0, "SUS304"), "RELEASE", "크로스레일 ↔ 지지링 A-06"),
        ),
    )


def _piping(g: Geometry) -> Assembly:
    """I — 노즐·배관·밸브 아세이."""
    ladder = tuple(n for n in NOZZLES if n.tag.startswith("N4"))
    return Assembly(
        code="I",
        drawing="MP50-I",
        name="노즐 · 배관 · 밸브 아세이",
        purpose="장입·배출·급기·시료채취 계통",
        parts=(
            Part("I-01", "배출 볼밸브 (기본)", '1½" 위생 3-pc 볼밸브 + 2→1½ 리듀싱 클램프', "SUS316L", 1,
                 1.4, "PROPOSED", "C3 — 2 in 스터브에 리듀서로 접속"),
            Part("I-02", "배출 볼밸브 (시험)", '2" 위생 3-pc 볼밸브', "SUS316L", 1, 2.1, "PROPOSED",
                 "[R] §16 의 1.5 vs 2 in 배출시험용 — 리듀서만 빼고 교체"),
            Part("I-03", "시료 밸브", '½" 위생 볼밸브', "SUS316L", len(ladder), 0.35, "PROPOSED",
                 f"C7 — Z{ladder[1].z_mm:.0f}/{ladder[2].z_mm:.0f}/{ladder[0].z_mm:.0f}/{ladder[3].z_mm:.0f}/{ladder[4].z_mm:.0f} 사다리 · 데드렉 최소화"),
            Part("I-04", "부상물 배출 밸브", '1½" 위생 볼밸브', "SUS316L", 1, 1.2, "RELEASE", "N2 오버플로"),
            Part("I-05", "급기 밸브 + 니들", '½" 볼밸브 + 미세조절 니들밸브', "SUS316L", 1, 0.45,
                 "RELEASE", "로타미터 상류 — DOE 의 0/3/5/8/10 L/min 을 여기서 맞춘다"),
            Part("I-06", "배관·피팅", "위생 클램프·페룰·가스켓 일식", "SUS316L / EPDM", 1, 3.0,
                 "RELEASE", "가스켓은 EPDM — NaCl 18 wt% 상온에서 문제 없다"),
            Part("I-07", "배출 호스", "Ø50 위생 실리콘 호스 × L1000", "-", 1, 0.9, "VENDOR",
                 f"밸브 아래 {g.discharge_clearance_mm:.0f} mm — 통을 옆에 두고 호스로 받는다"),
        ),
    )


def _instruments(g: Geometry) -> Assembly:
    """J — 계측·센서 아세이. C7 로 구성이 바뀐 아세이다."""
    return Assembly(
        code="J",
        drawing="MP50-J",
        name="계측 · 센서 아세이",
        purpose="[R] §15 가 요구한 실측값 — 염도·온도·급기량·층 높이",
        parts=(
            Part("J-01", "전도도 / 염도 센서", "0~200 mS/cm, 삽입장 425, 위생 ½\" 접속", "-", 1, 0.4,
                 "PROPOSED", "C7 — 제어변수는 염수 밀도지 pH 가 아니다 · B2 에서 삽입, 선단 Z526"),
            Part("J-02", "온도센서", "Pt100 3-wire, 삽입장 225, 위생 ½\" 접속", "-", 1, 0.3,
                 "RELEASE", "B3 · 염수밀도 온도보정 (약 -0.3 kg/m³·K)"),
            Part("J-03", "공기 유량계", "로타미터 0~20 L/min + 압력계 0~2 bar", "-", 1, 0.5,
                 "RELEASE", "DOE 급기 조건 재현용"),
            Part("J-04", "사이트글라스", "Ø100 위생형, 붕규산유리", "붕규산유리", 1, 1.1,
                 "PROPOSED", f"N5 (Z{[n for n in NOZZLES if n.tag == 'N5'][0].z_mm:.0f}) — 부상층 형성 육안 확인"),
            Part("J-05", "액면 눈금", "동체 외면 각인 + 시료 사다리 표고 표기", "-", 1, 0.0,
                 "RELEASE", f"Z{g.nominal_level_z:.0f}(50 L) · Z{g.operating_level_z:.0f}({g.operating_volume_l:.1f} L) 각인"),
            Part("J-06", "제어반", "VFD, 타이머, 급기 SOL, 동시 OFF 버튼", "-", 1, 12.0,
                 "PROPOSED", "임펠러·급기 **동시** 차단이 이 장치의 핵심 동작 — 단일 접점으로 묶는다"),
            Part("J-07", "전류·진동 로깅", "VFD 전류 출력 + 휴대형 진동계", "-", 1, 0.0,
                 "RELEASE", "[R] §15 필수 데이터"),
        ),
    )


def _fasteners(g: Geometry) -> Assembly:
    """K — 볼트·체결품."""
    return Assembly(
        code="K",
        drawing="MP50-K",
        name="볼트 · 체결품",
        purpose="아세이 간 체결 — 조임 토크와 재질을 한 곳에서 관리",
        parts=(
            Part("K-01", "커버 볼트", f"{g.top_flange_bolt} × 35 육각 (A2-70)", "SUS304", g.top_flange_bolts,
                 0.038, "RELEASE", "40 N·m · 대각 순서 2 회전"),
            Part("K-02", "지지링 볼트", "M12 × 40 육각 (A2-70)", "SUS304", 4, 0.042, "RELEASE", "40 N·m"),
            Part("K-03", "프레임 앵커", "M12 케미컬 앵커", "-", 4, 0.09, "VENDOR", "시험 중 고정 권장"),
            Part("K-04", "너트 · 와셔", "M12 너트 / 평 / 스프링와셔", "SUS304", 32, 0.017, "RELEASE", "-"),
            Part("K-05", "임펠러 세트스크류", "M8 × 8 (D-05 재게)", "SUS304", 4, 0.004, "RELEASE", "20 N·m"),
            Part("K-06", "스키머 조절 너트", "M8 너트 + 평와셔", "SUS304", 12, 0.006, "RELEASE", "상하 이중너트로 고정"),
        ),
    )


ASSEMBLIES: tuple[Assembly, ...] = (
    _tank(GEOMETRY),
    _cover(GEOMETRY),
    _drive(GEOMETRY),
    _shaft(GEOMETRY),
    _baffle(GEOMETRY),
    _sparger(GEOMETRY),
    _skimmer(GEOMETRY),
    _frame(GEOMETRY),
    _piping(GEOMETRY),
    _instruments(GEOMETRY),
    _fasteners(GEOMETRY),
)

BY_CODE = {a.code: a for a in ASSEMBLIES}


def bill_of_materials() -> tuple[Part, ...]:
    """전 아세이의 부품을 하나로 편다."""
    return tuple(p for a in ASSEMBLIES for p in a.parts)


def dry_mass_kg() -> float:
    """건조 총질량 — 양중·운반 계획용."""
    return sum(a.total_kg for a in ASSEMBLIES)


def wet_mass_kg(brine_density: float = 1130.0) -> float:
    """운전 총질량 — 프레임·바닥 하중 검토용.

    18 wt% NaCl 염수 1130 kg/m³ 를 운전 액면까지 채운 상태.
    """
    return dry_mass_kg() + GEOMETRY.operating_volume_l / 1000.0 * brine_density
