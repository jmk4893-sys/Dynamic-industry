"""MP-50 제작품 CAD 출력 — 절단용 DXF, 가공도 DXF, 3D STEP.

    python tools/mp50_cad.py

HTML 부품도(``mp50_parts.py``)는 사람이 읽는 도면이다. 여기서 나오는 것은
**기계가 읽는 파일**이다. 셋을 나눠 낸다.

``docs/cad/dxf/cut/`` — 절단 윤곽만. 레이저·워터젯 CAM 이 이것을 그대로 먹는다.
  1:1 실치수이고 글자가 한 자도 없다. 원점은 소재 왼쪽 아래.
``docs/cad/dxf/dwg/`` — 가공도. A3 틀·표제란·치수·구멍표·주기가 들어간다.
  현장에서 인쇄해 들고 쓰는 도면이다.
``docs/cad/step/`` — 3D 솔리드. 평면·원통·원뿔 해석면이라 CAM 이 지름과 축을
  읽는다. 메시가 아니다.

모든 좌표는 ``mp50_separator`` 의 확정 기하에서 나온다. 손으로 적은 치수가
없으므로 기준치수를 고치면 세 갈래가 함께 움직인다.

굽힘 부품(F-01 분산링, G-04 손잡이)의 3D 는 **굽히기 전 곧은 소재**다. 자르고
뚫는 것은 곧은 상태에서 하고, 굽힘은 치수로 지시한다 — 굽은 관을 솔리드로
내보내 봐야 현장에서 할 일이 달라지지 않는다.
"""

from __future__ import annotations

import math
import pathlib
import sys
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _mp50_cad as K
import _mp50_dxf as X
import _mp50_step as P
from _mp50_draft import text_width
from _mp50_cad import Profile
from mp50_separator import ASSEMBLIES, GEOMETRY as G
from mp50_separator.components import DENSITY
from mp50_separator.geometry import COVER_NOZZLES, NOZZLES

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "cad"

PART = {p.no: p for a in ASSEMBLIES for p in a.parts}
PART_OF = {p.no: a for a in ASSEMBLIES for p in a.parts}

REV, DATE = "R1", "2026-09-10"

#: 동체 세로이음(용접선)의 원주 위치. 전개도의 왼쪽 끝이 여기다.
#:
#: 0° 에 두면 N1 급광 노즐이 이음선 위에 앉는다 — 구멍이 전개 평판의 끝에
#: 걸쳐 반쪽씩 잘리고, 용접선을 뚫는 것이라 만들 수도 없다. 노즐이 θ 90 과
#: 180 사이에 없으므로 그 가운데인 135° 에 둔다. 가장 가까운 노즐(N3 180°)
#: 까지 45° = 158 mm 떨어진다.
SEAM_THETA = 135.0

#: 표준 축척 사다리. 도면은 임의 배율로 그리지 않는다.
SCALES = (10.0, 5.0, 2.5, 2.0, 1.0, 0.5, 0.4, 0.25, 0.2, 0.1, 0.05, 0.04, 0.025, 0.02)


@dataclass
class CadPart:
    """CAD 로 내보낼 부품 하나.

    Attributes:
        no: 부품번호.
        profile: 잘라낼 평면 윤곽 (판재·관 단면·전개도).
        extrude: 윤곽을 밀어낼 길이 — 판은 판두께, 봉·관은 길이.
        kind: 판재 / 전개 / 관재 / 봉재 / 절곡 / 원뿔.
        note: 이 형상이 무엇인지 한 줄.
        dims: 가공도에 넣을 치수 지시 — (종류, 값…) 목록.
        holes: 구멍표 — (지름, 개수, 설명).
        bends: 절곡표 — (각도, 방향, 안쪽 R, 설명).
        solids: STEP 솔리드. 비우면 profile+extrude 로 만든다.
        step_note: 3D 가 실물과 다른 점 (말기 전·굽히기 전 등).
    """

    no: str
    profile: Profile | None
    extrude: float
    kind: str
    note: str
    holes: list[tuple[float, int, str]] = field(default_factory=list)
    bends: list[tuple[float, str, float, str]] = field(default_factory=list)
    solids: list = field(default_factory=list)
    step_note: str = ""
    #: 윤곽에 그리지 않은 재료 제거율 — 타공판처럼 대표 구간만 그린 경우.
    removed: float = 0.0

    @property
    def part(self):
        return PART[self.no]

    @property
    def material(self) -> str:
        return self.part.material

    @property
    def area_mm2(self) -> float:
        return self.profile.area_mm2 if self.profile else 0.0

    @property
    def cut_length_mm(self) -> float:
        return self.profile.cut_length_mm if self.profile else 0.0

    @property
    def volume_mm3(self) -> float:
        return self.area_mm2 * self.extrude

    @property
    def calc_kg(self) -> float:
        """CAD 형상에서 다시 잰 질량 — 부품표 값과 맞는지 시험이 본다.

        솔리드를 따로 준 부품(임펠러처럼 여러 덩어리)은 그 부피를 센다.
        구멍을 뺀 값이므로 부품표의 외형 기준 추정보다 작게 나올 수 있다.
        """
        if self.solids:
            v = sum(x.volume_analytic for x in self.solids)
        else:
            v = self.volume_mm3
        return v * (1.0 - self.removed) * 1e-9 * DENSITY[self.material]

    def step_solids(self) -> list:
        if self.solids:
            return self.solids
        if self.profile is None:
            return []
        return [P.extrude(self.profile, self.extrude, self.no)]


PARTS: dict[str, CadPart] = {}


def add(part: CadPart) -> CadPart:
    if part.profile is not None:
        part.profile.check()
    PARTS[part.no] = part
    return part


# ==========================================================================
# A 탱크
# ==========================================================================
def build_a() -> None:
    # A-01 동체 — 롤링 전이라 평판이다. 중립축 둘레 × 높이.
    dev = G.shell_development_length_mm
    h = G.shell_height_mm
    shell = Profile(K.rect_loop(0.0, 0.0, dev, h))
    holes: list[tuple[float, int, str]] = []
    for n in NOZZLES:
        # 원주 위치 θ 를 전개 길이로 편다. 표고는 동체 하단 기준.
        x = dev * ((n.theta_deg - SEAM_THETA) % 360.0) / 360.0
        y = n.z_mm - G.shell_bottom_z
        d = n.tube_od_mm + 1.0                  # set-through 전용입 — 관 외경 + 여유
        shell.holes.append(K.hole(x, y, d))
        holes.append((d, 1, f"{n.tag} {n.service} · θ{n.theta_deg:.0f}° Z{n.z_mm:.0f}"))
    add(CadPart("A-01", shell, G.shell_thickness_mm, "전개",
                f"Ø{G.tank_id_mm:.0f} ID × H{h:.0f} 롤링 전 평판 — 중립축 전개 "
                f"{dev:.1f} · 좌우 끝이 세로이음 (원주 θ{SEAM_THETA:.0f}°)",
                holes=holes,
                solids=[P.extrude(K.ring(0.0, 0.0, G.shell_od_mm, G.tank_id_mm), h, "A-01")],
                step_note="3D 는 말고 난 원통이다. 노즐 구멍은 평판에서 뚫으므로 "
                          "DXF 전개도에만 있다."))

    # A-02 원뿔 — 부채꼴 전개. 각도 180° 라 반원 고리다.
    ro, ri = G.cone_development_outer_r_mm, G.cone_development_inner_r_mm
    ang = math.radians(G.cone_development_angle_deg)
    b = math.tan(ang / 4.0)
    sector = Profile([
        (ro, 0.0, b), (ro * math.cos(ang), ro * math.sin(ang), 0.0),
        (ri * math.cos(ang), ri * math.sin(ang), -math.tan(ang / 4.0)), (ri, 0.0, 0.0),
    ])
    add(CadPart("A-02", sector, G.cone_thickness_mm, "전개",
                f"Ø{G.tank_id_mm:.0f} → Ø{G.cone_outlet_id_mm:.1f} "
                f"{G.cone_included_deg:.0f}° 원뿔의 부채꼴 전개 — "
                f"R{ro:.1f} / R{ri:.1f} × {G.cone_development_angle_deg:.0f}°",
                solids=[P.cone_shell(G.tank_id_mm / 2 + G.cone_thickness_mm,
                                     G.cone_outlet_id_mm / 2 + G.cone_thickness_mm,
                                     G.cone_truncated_height_mm, G.cone_thickness_mm, "A-02")],
                step_note="3D 는 말고 난 원뿔이다. 자르는 것은 왼쪽 부채꼴이다."))

    # A-03 배출 스터브 — 2 in 위생관.
    add(CadPart("A-03", K.ring(0.0, 0.0, 63.5, 59.5), 40.0, "관재",
                "Ø63.5 × t2.0 위생튜브 L40 + 2\" 페룰"))

    # A-04 동체 노즐 — 9 종. 대표로 가장 많은 ½" 를 그리고 나머지는 표로 준다.
    rep = next(n for n in NOZZLES if n.tag == "N4A")
    add(CadPart("A-04", K.ring(0.0, 0.0, rep.tube_od_mm, rep.tube_od_mm - 2 * 1.65),
                rep.projection_mm, "관재",
                "위생튜브 9 본 — 호칭·돌출장은 노즐표. 그린 것은 ½\" 대표 단면",
                step_note="3D 는 대표 1 본이다. 나머지는 노즐표의 호칭으로 같은 방식."))

    # A-05 상단 플랜지.
    fl = K.ring(0.0, 0.0, G.top_flange_od_mm, G.shell_od_mm)
    for hl in K.bolt_circle(0.0, 0.0, G.top_flange_pcd_mm, G.top_flange_bolts, 14.0, 15.0):
        fl.holes.append(hl)
    add(CadPart("A-05", fl, G.top_flange_thickness_mm, "판재",
                f"OD Ø{G.top_flange_od_mm:.0f} × ID Ø{G.shell_od_mm:.0f} "
                f"× t{G.top_flange_thickness_mm:.0f}",
                holes=[(14.0, G.top_flange_bolts,
                        f"M12 볼트 · PCD Ø{G.top_flange_pcd_mm:.0f} · 15° 시작")]))

    # A-06 지지링 — 브래킷 볼트 4 개소.
    ring6 = K.ring(0.0, 0.0, G.support_ring_od_mm, G.shell_od_mm)
    for hl in K.bolt_circle(0.0, 0.0, 450.0, 4, 14.0, 45.0):
        ring6.holes.append(hl)
    add(CadPart("A-06", ring6, G.support_ring_thickness_mm, "판재",
                f"OD Ø{G.support_ring_od_mm:.0f} × ID Ø{G.shell_od_mm:.0f} "
                f"× t{G.support_ring_thickness_mm:.0f} — 프레임 크로스레일에 앉는다",
                holes=[(14.0, 4, "지지 브래킷 H-07 · M12 · PCD Ø450")]))

    # A-07 보강 거싯 — 직각삼각형.
    add(CadPart("A-07", Profile(K.polygon_loop([(0, 0), (100, 0), (0, 100)], 2.0)), 5.0,
                "판재", "직각 100 × 100 × t5 — 지지링 하면 ↔ 콘 외면 4 개소"))

    # A-08 양중 러그 — 한쪽 모서리를 18 모따기하고 Ø20 샤클 구멍.
    w, hgt, cut = 70.0, 50.0, 18.0
    lug = Profile(K.polygon_loop(
        [(0, 0), (w, 0), (w, hgt - cut), (w - cut, hgt), (0, hgt)], 2.0))
    lug.holes.append(K.hole(w - 26.0, hgt - 24.0, 20.0))
    add(CadPart("A-08", lug, 6.0, "판재",
                "70 × 50 × t6 · 모따기 18 · 3 개소 120° 등분",
                holes=[(20.0, 1, "샤클 구멍 · C1 모따기 · 버 제거")]))


# ==========================================================================
# B 커버
# ==========================================================================
def build_b() -> None:
    # 구멍 배치는 부품도 MP50-P-B01 과 같아야 한다 — 두 도면이 어긋나면
    # 커버와 플랜지가 안 맞는다. PCD·각도를 그 시트에서 그대로 가져왔다.
    inst_pcd = 330.0
    cover = Profile(K.circle_loop(0.0, 0.0, G.top_flange_od_mm / 2))
    cover.holes.append(K.hole(0.0, 0.0, 60.0))
    holes = [(60.0, 1, "중앙 보어 — HOLD. 씰 슬리브 확정 전 가공 금지 (B1)")]
    for hl in K.bolt_circle(0.0, 0.0, G.top_flange_pcd_mm, G.top_flange_bolts, 14.0, 15.0):
        cover.holes.append(hl)
    holes.append((14.0, G.top_flange_bolts,
                  f"M12 · PCD Ø{G.top_flange_pcd_mm:.0f} — A-05 와 같은 지그로 뚫는다"))
    for hl in K.bolt_circle(0.0, 0.0, inst_pcd, 3, 16.7, 60.0):
        cover.holes.append(hl)
    holes.append((16.7, 3, f"계측 노즐 B2·B3·B4 · PCD Ø{inst_pcd:.0f} · θ 60/180/300"))
    for hl in K.bolt_circle(0.0, 0.0, inst_pcd, 3, 20.0, 0.0):
        cover.holes.append(hl)
    holes.append((20.0, 3, f"B-07 조절봉 부싱 · PCD Ø{inst_pcd:.0f} · θ 0/120/240"))
    add(CadPart("B-01", cover, G.cover_thickness_mm, "판재",
                f"Ø{G.top_flange_od_mm:.0f} × t{G.cover_thickness_mm:.0f}",
                holes=holes))

    add(CadPart("B-02", K.ring(0.0, 0.0, G.cover_hub_od_mm, 60.0),
                G.cover_hub_thickness_mm, "판재",
                f"Ø{G.cover_hub_od_mm:.0f} × t{G.cover_hub_thickness_mm:.0f} · "
                "보어 Ø60 — 볼트 PCD 는 벤더 GA (HOLD)",
                holes=[(60.0, 1, "축 통과 보어 — 씰 자리는 벤더 GA 로 확정")]))

    add(CadPart("B-03", Profile(K.polygon_loop([(0, 0), (80, 0), (0, 60)], 2.0)), 5.0,
                "판재", "직각 80 × 60 × t5 — 커버 허브 ↔ 커버판 4 개소"))

    rep = next(n for n in COVER_NOZZLES if n.tag == "B2")
    add(CadPart("B-04", K.ring(0.0, 0.0, rep.tube_od_mm, rep.tube_od_mm - 2 * 1.65),
                60.0, "관재",
                "Ø12.7 × t1.65 위생튜브 3 본 (B2 · B3 · B4) + 페룰"))

    add(CadPart("B-07", K.ring(0.0, 0.0, 20.0, 8.4), 30.0, "봉재",
                "Ø20 환봉 L30 · M8 관통 · O-링 홈 — 3 개소",
                holes=[(8.4, 1, "M8 관통 하공 · 탭 M8")]))


# ==========================================================================
# C 구동부 · D 교반축
# ==========================================================================
def build_cd() -> None:
    add(CadPart("C-05", K.ring(0.0, 0.0, 180.0, 60.0), 6.0, "판재",
                "커버 허브 ↔ 씰 ↔ 감속기 플랜지 어댑터 — **HOLD**. "
                "볼트 PCD·씰 자리는 벤더 GA 로 확정된다",
                step_note="HOLD 형상이다. 벤더 GA 가 나오기 전에는 발주하지 않는다."))

    # C-06 보호 커버 — 커플링을 감싸는 Ø180 원통. 말기 전 띠로 자른다.
    guard_r, guard_h = 90.0, 160.0
    dev = 2.0 * math.pi * guard_r
    add(CadPart("C-06", Profile(K.rect_loop(0.0, 0.0, dev, guard_h)), 1.5, "전개",
                f"Ø{2 * guard_r:.0f} × H{guard_h:.0f} × t1.5 원통 가드 — "
                f"중립축 전개 {dev:.1f} × {guard_h:.0f}",
                solids=[P.extrude(K.ring(0.0, 0.0, 2 * guard_r + 1.5, 2 * guard_r - 1.5),
                                  guard_h, "C-06")],
                step_note="3D 는 말고 난 원통이다. 공구 없이 열리는 개방식이라 "
                          "인터록은 걸지 않는다."))

    add(CadPart("D-01", Profile(K.circle_loop(0.0, 0.0, G.shaft_od_mm / 2)), 760.0, "봉재",
                f"Ø{G.shaft_od_mm:.0f} h7 × L760 · 직진도 0.5/600 · "
                "키홈 6P9 2 개소"))

    # D-02 임펠러 — 허브와 날개를 따로 낸다. 날개는 판재, 허브는 봉재.
    blade = Profile(K.rect_loop(0.0, 0.0, G.impeller_blade_radial_mm,
                                G.impeller_blade_width_mm, 2.0))
    hub = K.ring(0.0, 0.0, G.impeller_hub_od_mm, G.shaft_od_mm)
    hub.holes.append(K.slot(0.0, G.shaft_od_mm / 2 + 1.4, 6.0, 2.8))
    solids = [P.extrude(hub, G.impeller_hub_length_mm, "D-02 허브")]
    for i in range(G.impeller_blades):
        solids.append(P.extrude(
            blade.translated(G.impeller_hub_od_mm / 2, -G.impeller_blade_width_mm / 2),
            G.impeller_blade_thickness_mm, f"D-02 날개 {i + 1}"))
    add(CadPart("D-02", blade, G.impeller_blade_thickness_mm, "판재",
                f"Ø{G.impeller_od_mm:.0f} {G.impeller_blades}PBT"
                f"{G.impeller_pitch_deg:.0f}° — 날개 전개 "
                f"{G.impeller_blade_radial_mm:.0f} × {G.impeller_blade_width_mm:.0f} "
                f"× t{G.impeller_blade_thickness_mm:.0f} 4 매",
                solids=solids,
                step_note=f"3D 는 허브와 날개 {G.impeller_blades} 매를 "
                          "따로 담았다. 날개는 취부각 45° 로 세워 용접한다."))

    d02 = PARTS["D-02"]
    add(CadPart("D-03", d02.profile, d02.extrude, "판재",
                "D-02 와 같은 형상 — 같은 도면으로 2 개 제작 (하부 Z430 · 상부 Z610)",
                solids=d02.solids, step_note=d02.step_note))

    add(CadPart("D-06", K.ring(0.0, 0.0, 50.0, G.shaft_od_mm), 25.0, "봉재",
                f"Ø50 × L25 · 보어 Ø{G.shaft_od_mm:.0f} · "
                "M8 세트스크류 2 개소",
                holes=[(6.8, 2, "M8 세트스크류 하공 · 90° 배치")]))


# ==========================================================================
# E 배플 · F 급기 · G 스키머
# ==========================================================================
def build_efg() -> None:
    add(CadPart("E-01", Profile(K.rect_loop(0.0, 0.0, G.baffle_width_mm,
                                            G.baffle_length_mm, 2.0)),
                G.baffle_thickness_mm, "판재",
                f"W{G.baffle_width_mm:.0f} × L{G.baffle_length_mm:.0f} × "
                f"t{G.baffle_thickness_mm:.0f} · 벽 이격 {G.baffle_wall_gap_mm:.0f} · 4 매"))

    add(CadPart("E-02", Profile(K.rect_loop(0.0, 0.0, 25.0, 6.0, 1.5)), 3.0, "판재",
                "25 × 6 × t3 스탠드오프 탭 — 배플 1 매당 3 개 · 모두 12 개"))

    # F-01 분산링 — 굽히기 전 곧은 관. 구멍은 곧은 상태에서 뚫는다.
    ring_len = math.pi * G.sparger_pcd_mm
    add(CadPart("F-01", K.ring(0.0, 0.0, G.sparger_tube_od_mm, G.sparger_tube_id_mm),
                ring_len, "관재",
                f"Ø{G.sparger_tube_od_mm:.0f} × t{G.sparger_tube_thickness_mm:.1f} "
                f"관재 L{ring_len:.0f} — 굽혀 PCD Ø{G.sparger_pcd_mm:.0f} 링",
                holes=[(G.sparger_hole_dia_mm, G.sparger_holes,
                        f"하향 · 등간격 {ring_len / G.sparger_holes:.1f} · 굽히기 전 뚫는다")],
                step_note="3D 는 굽히기 전 곧은 관이다. 굽힘 후 PCD 와 평면도는 "
                          "가공도의 치수로 잡는다."))

    add(CadPart("F-03", K.ring(0.0, 0.0, G.sparger_tube_od_mm, G.sparger_tube_id_mm),
                220.0, "관재",
                f"Ø{G.sparger_tube_od_mm:.0f} × "
                f"t{G.sparger_tube_thickness_mm:.1f} × L220 강하관"))

    brk = Profile(K.rect_loop(0.0, 0.0, 60.0, 30.0, 2.0))
    brk.bends = [((26.0, 0.0), (26.0, 30.0), 60.0, "up")]
    brk.holes.append(K.hole(43.0, 15.0, 13.0))
    add(CadPart("F-04", brk, 3.0, "절곡",
                "t3 · 1 회 굽힘 · 콘 내면 60° 에 맞춘다 · 3 개소",
                holes=[(13.0, 1, "Ø12 관 자리 — 끼우고 필릿 용접")],
                bends=[(60.0, "위로", 1.5, "콘 반각 30° 의 보각 · 안쪽 R1.5")],
                step_note="3D 는 굽히기 전 평판이다."))

    # G-01 스키머 링 — 롤링 전 띠.
    g1_dev = math.pi * (G.skimmer_od_mm - 2.0)
    add(CadPart("G-01", Profile(K.rect_loop(0.0, 0.0, g1_dev, G.skimmer_height_mm)),
                2.0, "전개",
                f"Ø{G.skimmer_od_mm:.0f} × H{G.skimmer_height_mm:.0f} × t2 "
                f"— 중립축 전개 {g1_dev:.1f}",
                solids=[P.extrude(K.ring(0.0, 0.0, G.skimmer_od_mm, G.skimmer_od_mm - 4.0),
                                  G.skimmer_height_mm, "G-01")],
                step_note="3D 는 말고 난 링이다."))

    # G-02 타공 바닥판 — 타공판을 사 와 원형으로 딴다. 대표 구간만 그린다.
    disc = Profile(K.circle_loop(0.0, 0.0, G.skimmer_od_mm / 2))
    pitch, hole_d = 3.5, 2.0
    rows = int(52 / (pitch * math.sqrt(3) / 2))
    for r in range(-rows, rows + 1):
        yy = r * pitch * math.sqrt(3) / 2
        off = (pitch / 2) if r % 2 else 0.0
        for k in range(-9, 10):
            xx = k * pitch + off
            if math.hypot(xx, yy) < 46.0:
                disc.holes.append(K.hole(xx, yy, hole_d))
    drawn = sum(abs(K.area(h)) for h in disc.holes)
    full = math.pi / 4.0 * G.skimmer_od_mm ** 2
    add(CadPart("G-02", disc, 1.5, "판재",
                f"Ø{G.skimmer_od_mm:.0f} × t1.5 · "
                f"Ø{hole_d:.0f} 피치 {pitch} 60° 엇갈림 · 개공률 30 %",
                holes=[(hole_d, 6000, "완제 타공판을 사 와 원형으로 딴다 — "
                                      "도면의 구멍은 대표 구간만")],
                removed=max(0.0, (0.30 * full - drawn) / (full - drawn)),
                step_note="구멍은 대표 구간만 담았다. 실제는 전면 타공이라 "
                          "6 천 개를 솔리드로 담으면 열리지 않는다."))

    add(CadPart("G-04", Profile(K.circle_loop(0.0, 0.0, 4.0)), 340.0, "봉재",
                "Ø8 환봉 L340 — 굽혀 손잡이. 굽힘 전 곧은 길이",
                bends=[(90.0, "양단", 20.0, "양 끝 2 개소 · 안쪽 R20")],
                step_note="3D 는 굽히기 전 곧은 봉이다."))


# ==========================================================================
# H 프레임
# ==========================================================================
def build_h() -> None:
    tube = K.square_tube(G.frame_tube_mm, G.frame_tube_thickness_mm)
    ft, fw, fh = G.frame_tube_mm, G.frame_width_mm, G.frame_height_mm
    for no, length, what in (("H-01", fh, "기둥 4 본"),
                             ("H-02", fw - ft, "상·하부 둘레재 8 본"),
                             ("H-03", fw - 2 * ft, "상부 크로스레일 2 본"),
                             ("H-04", fw - ft, "중간 보강재 4 본")):
        add(CadPart(no, tube, length, "관재",
                    f"□{ft:.0f} × {ft:.0f} × t{G.frame_tube_thickness_mm:.0f} "
                    f"× L{length:.0f} — {what}"))

    base = Profile(K.rect_loop(0.0, 0.0, 100.0, 100.0, 2.0))
    for x, y in ((18.0, 18.0), (82.0, 18.0), (82.0, 82.0), (18.0, 82.0)):
        base.holes.append(K.hole(x, y, 14.0))
    add(CadPart("H-06", base, 6.0, "판재",
                "100 × 100 × t6 · Ø14 앵커홀 4 개 · 4 개소",
                holes=[(14.0, 4, "M12 앵커 · 64 각 배치")]))

    brk = Profile(K.polygon_loop([(0, 0), (90, 0), (90, 40), (40, 70), (0, 70)], 2.0))
    brk.holes.append(K.hole(20.0, 35.0, 14.0))
    brk.holes.append(K.hole(65.0, 20.0, 14.0))
    add(CadPart("H-07", brk, 6.0, "판재",
                "t6 · 지지링 ↔ 크로스레일 · M12 2 개소 · 4 개소",
                holes=[(14.0, 2, "M12 · 지지링 A-06 과 크로스레일 H-03")]))


def build_all() -> None:
    PARTS.clear()
    build_a()
    build_b()
    build_cd()
    build_efg()
    build_h()


# ==========================================================================
# 출력 — 절단 DXF
# ==========================================================================
def cut_dxf(part: CadPart) -> X.Drawing:
    """CAM 이 그대로 먹는 파일. 1:1 실치수, 글자 없음, 원점은 왼쪽 아래.

    치수도 표제란도 넣지 않는다. 레이저 오퍼레이터가 이 파일을 열어 윤곽만
    집어가는데, 도면 요소가 섞여 있으면 그것까지 자를 위험이 있다.
    """
    d = X.Drawing()
    prof = part.profile
    if prof is None:
        return d
    x0, y0, _x1, _y1 = prof.bounds
    d.profile(prof.translated(-x0, -y0))
    return d


# ==========================================================================
# 출력 — 가공도 DXF
# ==========================================================================
SHEET_W, SHEET_H = 420.0, 297.0
MARGIN_L, MARGIN = 10.0, 5.0
TB_W, TB_H = 178.0, 30.0
VIEW = (14.0, 46.0, 230.0, 268.0)        # 도형부 x0, y0, x1, y1
COL_X = 240.0


def pick_scale(w: float, h: float, box_w: float, box_h: float) -> float:
    """표준 축척 사다리에서 들어가는 가장 큰 배율을 고른다."""
    for s in SCALES:
        if w * s <= box_w and h * s <= box_h:
            return s
    return SCALES[-1]


def scale_text(s: float) -> str:
    if s >= 1.0:
        return f"{s:.0f}:1" if s == int(s) else f"{s:g}:1"
    inv = 1.0 / s
    return f"1:{inv:.0f}" if abs(inv - round(inv)) < 1e-9 else f"1:{inv:g}"


def _frame(d: X.Drawing, part: CadPart, sheet_no: str, total: int,
           scale: str = "-") -> None:
    """도면 틀과 표제란 — HTML 부품도와 같은 칸을 쓴다."""
    p = part.part
    asm = PART_OF[part.no]
    x0, y0 = MARGIN_L, MARGIN
    w, h = SHEET_W - MARGIN_L - MARGIN, SHEET_H - 2 * MARGIN
    d.polyline(K.rect_loop(x0, y0, w, h), "FRAME")
    tx, ty = x0 + w - TB_W, y0
    d.polyline(K.rect_loop(tx, ty, TB_W, TB_H), "FRAME")
    d.line(tx, ty + TB_H - 13.0, tx + TB_W, ty + TB_H - 13.0, "FRAME")
    d.line(tx + 118.0, ty, tx + 118.0, ty + TB_H, "FRAME")
    d.text(tx + 3.0, ty + 23.0, f"{part.no} {p.name}", 6.0, "FRAME")
    d.text(tx + 3.0, ty + 18.6, p.spec, 2.4, "TEXT")
    cells = (("도면번호", f"MP50-C-{part.no}"), ("축척", scale), ("단위", "mm"),
             ("Rev", REV), ("날짜", DATE), ("시트", f"{sheet_no}/{total}"))
    for i, (k, v) in enumerate(cells):
        cx = tx + 3.0 + (i % 3) * 39.0
        cy = ty + 11.0 - (i // 3) * 7.6
        d.text(cx, cy + 2.6, k, 1.9, "TEXT")
        d.text(cx, cy - 1.4, v, 2.7, "TEXT")
    d.text(tx + 121.0, ty + TB_H - 6.0, "DYNAMIC INDUSTRY", 2.7, "FRAME")
    d.text(tx + 121.0, ty + TB_H - 10.4, "MP-50 염수 밀도분리 파일럿", 2.0, "TEXT")
    d.text(tx + 121.0, ty + 10.0, f"아세이 {asm.code} · {asm.name}", 2.0, "TEXT")
    d.text(tx + 121.0, ty + 5.4, "설계 계산 자동생성 · 제3각법", 2.0, "TEXT")


def _head(d: X.Drawing, chips: list[tuple[str, str]]) -> None:
    """상단 정보 띠 — 재질·소재·수량 같은 공통 지시."""
    x = MARGIN_L + 2.0
    y = SHEET_H - MARGIN - 11.0
    for label, value in chips:
        w = max(text_width(value, 2.7, bold=True), text_width(label, 1.9)) + 4.4
        d.polyline(K.rect_loop(x, y, w, 9.0), "FRAME")
        d.text(x + 2.0, y + 5.6, label, 1.9, "TEXT")
        d.text(x + 2.0, y + 1.6, value, 2.7, "FRAME")
        x += w + 1.6


def _table(d: X.Drawing, x: float, y: float, widths: list[float],
           rows: list[list[str]], row_h: float = 5.4, size: float = 2.3) -> float:
    """표 — 맨 윗줄이 머리. 아래로 자란다. 마지막 y 를 돌려준다."""
    total = sum(widths)
    cy = y
    for r, row in enumerate(rows):
        cy -= row_h
        d.polyline(K.rect_loop(x, cy, total, row_h), "FRAME")
        cx = x
        for wcol, cell in zip(widths, row):
            if cx > x:
                d.line(cx, cy, cx, cy + row_h, "FRAME")
            fit = cell
            while fit and text_width(fit, size) > wcol - 2.4:
                fit = fit[:-1]
            if fit != cell:
                fit = fit[:-1] + "…"
            d.text(cx + 1.2, cy + row_h / 2 - size * 0.35, fit, size,
                   "FRAME" if r == 0 else "TEXT")
            cx += wcol
    return cy


def _wrap(text: str, mm: float, size: float = 2.2) -> list[str]:
    """실측 글자폭으로 접는다 — 글자 수로 세면 한글 줄이 칸 밖으로 나간다."""
    out, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and text_width(trial, size) > mm:
            out.append(line)
            line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out


def drawing_dxf(part: CadPart, sheet_no: int, total: int) -> X.Drawing:
    """A3 가공도 — 도형부, 두께 뷰, 구멍표, 절곡표, 주기, 표제란."""
    d = X.Drawing()
    p = part.part
    prof = part.profile
    _head(d, [("재질", p.material), ("수량", f"{p.qty} 개"), ("형상", part.kind),
              ("두께·길이" if part.kind in ("판재", "전개", "절곡") else "길이",
               f"{part.extrude:g} mm"),
              ("일반공차", "ISO 2768-mK"), ("설계확정도", p.status)])

    vx0, vy0, vx1, vy1 = VIEW
    bw, bh = prof.size
    sc = pick_scale(bw, bh, (vx1 - vx0) * 0.80, (vy1 - vy0) * 0.62)
    x0, y0, _, _ = prof.bounds
    cx = (vx0 + vx1) / 2 - bw * sc / 2
    cy = vy1 - 26.0 - bh * sc
    placed = _scaled(prof, sc, cx - x0 * sc, cy - y0 * sc)
    d.profile(placed)
    for hl in placed.holes:
        hx = sum(v[0] for v in hl) / len(hl)
        hy = sum(v[1] for v in hl) / len(hl)
        r = max(math.hypot(v[0] - hx, v[1] - hy) for v in hl)
        if r * 2 >= 3.0:
            d.centre_mark(hx, hy, r + 2.5)
    _frame(d, part, str(sheet_no), total, scale_text(sc))
    d.text(vx0, vy1 - 6.0, "전개 평면" if part.kind == "전개" else "평면", 4.6, "FRAME")
    d.text(vx0 + 26.0, vy1 - 6.0, f"척도 {scale_text(sc)}", 2.4, "TEXT")

    # 전체 치수
    d.dim_linear(cx, cy, cx + bw * sc, cy, -9.0, f"{bw:.1f}".rstrip("0").rstrip("."))
    d.dim_linear(cx, cy, cx, cy + bh * sc, -9.0,
                 f"{bh:.1f}".rstrip("0").rstrip("."), vertical=True)

    # 바깥 윤곽의 호 — 지름이나 반지름을 적는다. 전체 치수만으로는 부채꼴이나
    # 원판을 자를 수 없다.
    _arc_dims(d, prof, placed, sc, cx, cy, bw, bh)

    # 두께 뷰
    tv_y = cy - 34.0
    tw = min(bw * sc, 120.0)
    ts = min(6.0, max(1.2, part.extrude * sc))
    d.polyline(K.rect_loop(cx, tv_y - ts, tw, ts), "CUT")
    d.text(vx0, tv_y + 6.0, "두께" if part.kind in ("판재", "전개", "절곡") else "길이",
           4.6, "FRAME")
    d.dim_linear(cx + tw, tv_y - ts, cx + tw, tv_y, 9.0,
                 f"{'t' if part.kind in ('판재', '전개', '절곡') else 'L'}"
                 f"{part.extrude:g}", vertical=True)

    # 오른쪽 기둥
    y = vy1
    d.text(COL_X, y, "소재 · 마감", 4.6, "FRAME")
    y = _table(d, COL_X, y - 3.0, [24.0, 148.0], [
        ["항목", "값"],
        ["재질", p.material],
        ["소재", p.stock or "-"],
        ["형상", part.kind],
        ["일반공차", "ISO 2768-mK · 기입 치수 우선"],
        ["모서리", "액체에 닿는 모서리 R2 이상"],
        ["내면", "Ra ≤ 0.8 · 용접부 평활 연삭"],
        ["후처리", "산세 · 부동태화 (페록실 청색 반응 없을 것)"],
    ])

    if part.holes:
        y -= 9.0
        d.text(COL_X, y, "구멍표", 4.6, "FRAME")
        rows = [["Ø", "수", "설명"]]
        for dia, qty, why in part.holes:
            rows.append([f"Ø{dia:g}", str(qty), why])
        y = _table(d, COL_X, y - 3.0, [16.0, 10.0, 146.0], rows, 5.0, 2.2)

    spots = hole_positions(part)
    if spots and len(spots) <= 10:
        y -= 9.0
        d.text(COL_X, y, "구멍 좌표", 4.6, "FRAME")
        rows = [["번호", "X", "Y", "Ø"]]
        for i, (hx, hy, dia) in enumerate(spots, 1):
            rows.append([f"H{i}", f"{hx:.1f}", f"{hy:.1f}", f"Ø{dia:g}"])
        y = _table(d, COL_X, y - 3.0, [16.0, 26.0, 26.0, 20.0], rows, 5.0, 2.2)
        d.text(COL_X, y - 4.0, "원점은 소재 왼쪽 아래 — 절단 DXF 의 원점과 같다",
               2.1, "NOTE")
        y -= 8.0

    if part.bends:
        y -= 9.0
        d.text(COL_X, y, "절곡표", 4.6, "FRAME")
        rows = [["각도", "방향", "안쪽 R", "설명"]]
        for ang, side, rad, why in part.bends:
            rows.append([f"{ang:g}°", side, f"R{rad:g}", why])
        y = _table(d, COL_X, y - 3.0, [14.0, 16.0, 14.0, 128.0], rows, 5.0, 2.1)

    y -= 9.0
    d.text(COL_X, y, "주기", 4.6, "FRAME")
    y -= 5.0
    notes = [part.note]
    if p.note and p.note != "-":
        notes.append(p.note)
    if part.step_note:
        notes.append(f"3D — {part.step_note}")
    notes.append(f"절단 길이 약 {part.cut_length_mm:.0f} mm · 실면적 "
                 f"{part.area_mm2:.0f} mm² · 질량 {part.calc_kg:.3f} kg/개")
    notes.append("이 도면은 설계 계산에서 생성된다. 손으로 고치지 말 것 — "
                 "다시 생성하면 덮어쓴다.")
    for n in notes:
        for line in _wrap("· " + n, 170.0):
            d.text(COL_X, y, line, 2.2, "NOTE")
            y -= 3.6
        y -= 1.2
    return d


def _arc_dims(d: X.Drawing, prof: Profile, placed: Profile, sc: float,
              cx: float, cy: float, bw: float, bh: float) -> None:
    """바깥 윤곽의 호에 지름·반지름 치수를 단다.

    온전한 원이면 지름, 아니면 반지름이다. 같은 반지름이 여러 번 나오면 한
    번만 적는다 — 모서리 R2 가 여덟 군데라고 여덟 번 쓰지 않는다.
    """
    seen: list[float] = []
    m = len(prof.outer)
    full_circle = m == 2 and all(abs(v[2] - 1.0) < 1e-9 for v in prof.outer)
    if full_circle:
        _, _, r, _, _ = K.arc_geometry(prof.outer[0], prof.outer[1])
        d.dim_diameter(cx + bw * sc / 2, cy + bh * sc / 2, r * sc,
                       cx + bw * sc + 16.0, cy + bh * sc * 0.75, f"Ø{2 * r:g}")
        return
    shown = 0
    for i, p1 in enumerate(prof.outer):
        if not p1[2] or shown >= 3:
            continue
        _, _, r, _, _ = K.arc_geometry(p1, prof.outer[(i + 1) % m])
        if r < 3.0 or any(abs(r - q) < 1e-6 for q in seen):
            continue
        seen.append(r)
        q1, q2 = placed.outer[i], placed.outer[(i + 1) % m]
        acx, acy, ar, start, theta = K.arc_geometry(q1, q2)
        mid = start + theta / 2.0
        mx, my = acx + ar * math.cos(mid), acy + ar * math.sin(mid)
        out = 14.0 + shown * 8.0
        d.leader(mx, my, mx + math.copysign(out, math.cos(mid) or 1.0),
                 my + math.copysign(out, math.sin(mid) or 1.0), [f"R{r:g}"])
        shown += 1


def hole_positions(part: CadPart) -> list[tuple[float, float, float]]:
    """구멍 중심과 지름 — 소재 왼쪽 아래를 원점으로 한다.

    절단 DXF 가 같은 원점을 쓰므로 도면의 좌표를 그대로 CAM 에 넣어 확인할 수
    있다. 구멍이 많은 부품(볼트 원주·타공판)은 표 대신 배치 설명으로 준다.
    """
    prof = part.profile
    if prof is None:
        return []
    x0, y0, _, _ = prof.bounds
    out = []
    for hl in prof.holes:
        hx = sum(v[0] for v in hl) / len(hl)
        hy = sum(v[1] for v in hl) / len(hl)
        r = max(math.hypot(v[0] - hx, v[1] - hy) for v in hl)
        out.append((hx - x0, hy - y0, round(2 * r, 2)))
    return out


def _scaled(prof: Profile, s: float, dx: float, dy: float) -> Profile:
    """윤곽을 배율 ``s`` 로 줄여 옮긴다. bulge 는 배율에 영향받지 않는다."""
    def go(loop):
        return [(x * s + dx, y * s + dy, b) for x, y, b in loop]
    out = Profile(go(prof.outer), [go(h) for h in prof.holes])
    out.bends = [((a[0] * s + dx, a[1] * s + dy), (b[0] * s + dx, b[1] * s + dy), ang, side)
                 for a, b, ang, side in prof.bends]
    out.marks = [go(m) for m in prof.marks]
    return out


# ==========================================================================
# 출력 — 파일 쓰기
# ==========================================================================
def order() -> list[str]:
    """부품표 순서 그대로 — 아세이 A 부터."""
    return [p.no for a in ASSEMBLIES for p in a.parts if p.no in PARTS]


def write_all() -> dict[str, int]:
    """세 갈래를 모두 쓴다. {경로: 바이트} 를 돌려준다."""
    written: dict[str, int] = {}
    seq = order()
    total = len(seq)
    for i, no in enumerate(seq, 1):
        c = PARTS[no]
        cut = OUT / "dxf" / "cut" / f"MP50-C-{no}-CUT.dxf"
        written[str(cut)] = X.write(cut, cut_dxf(c))
        dwg = OUT / "dxf" / "dwg" / f"MP50-C-{no}.dxf"
        written[str(dwg)] = X.write(dwg, drawing_dxf(c, i, total))
        solids = c.step_solids()
        if solids:
            stp = OUT / "step" / f"MP50-{no}.stp"
            written[str(stp)] = P.write(stp, solids, no)
    written[str(OUT / "README.md")] = write_index(seq)
    return written


def write_index(seq: list[str]) -> int:
    """CAD 폴더 목차 — 현장이 무엇을 받았는지 한 장으로 본다."""
    L: list[str] = []
    L.append("# MP-50 CAD 파일")
    L.append("")
    L.append("`python tools/mp50_cad.py` 가 만든다. 손으로 고치지 말 것 — "
             "다시 생성하면 덮어쓴다. 좌표는 모두 `mp50_separator` 의 확정 기하에서 나온다.")
    L.append("")
    L.append("| 폴더 | 무엇 | 쓰는 곳 |")
    L.append("|---|---|---|")
    L.append("| `dxf/cut/` | 절단 윤곽만. 1:1, 글자 없음, 원점은 소재 왼쪽 아래 | "
             "레이저·워터젯 CAM |")
    L.append("| `dxf/dwg/` | A3 가공도. 틀·표제란·치수·구멍표·주기 | 현장 인쇄 |")
    L.append("| `step/` | 3D 솔리드 (AP214). 평면·원통·원뿔 해석면 | 기계가공·간섭 확인 |")
    L.append("")
    L.append("DXF 는 R12(AC1009) 이고 글자는 cp949 다 — 한국 현장 CAD 가 그대로 읽는다. "
             "STEP 은 AP214 이며 OpenCascade 로 부피와 다양체를 확인했다.")
    L.append("")
    L.append("## 부품")
    L.append("")
    L.append("| 부품 | 품명 | 재질 | 수 | 형상 | 소재 | 윤곽 mm | 절단 mm | 면적 mm² | "
             "질량 kg | 3D |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for no in seq:
        c = PARTS[no]
        p = c.part
        w, h = c.profile.size
        has3d = "O" if c.step_solids() else "-"
        L.append(f"| `{no}` | {p.name} | {p.material} | {p.qty} | {c.kind} | "
                 f"{p.stock or '-'} | {w:.1f} × {h:.1f} | {c.cut_length_mm:.0f} | "
                 f"{c.area_mm2:.0f} | {c.calc_kg:.3f} | {has3d} |")
    L.append("")
    total_cut = sum(PARTS[n].cut_length_mm * PARTS[n].part.qty for n in seq)
    L.append(f"절단 길이 합계 약 **{total_cut / 1000.0:.1f} m** (수량 반영). "
             "레이저 견적의 1 차 근거다.")
    L.append("")
    L.append("## 3D 가 실물과 다른 곳")
    L.append("")
    L.append("말거나 굽히는 부품은 **자르는 형상**과 **완성 형상**이 다르다. "
             "자르는 것은 DXF 에, 완성은 STEP 에 있다.")
    L.append("")
    L.append("| 부품 | 다른 점 |")
    L.append("|---|---|")
    for no in seq:
        if PARTS[no].step_note:
            L.append(f"| `{no}` | {PARTS[no].step_note} |")
    L.append("")
    L.append("## 질량이 부품표와 다른 곳")
    L.append("")
    L.append("CAD 질량은 구멍을 뺀 실형상이고, 부품표는 외형 기준 추정이거나 "
             "사 오는 부속(페룰 등)을 포함한다. 아래가 그 차이다.")
    L.append("")
    L.append("| 부품 | CAD kg | 부품표 kg | 왜 |")
    L.append("|---|---|---|---|")
    for no, why in MASS_NOTES.items():
        c = PARTS[no]
        L.append(f"| `{no}` | {c.calc_kg:.3f} | {c.part.unit_kg:.3f} | {why} |")
    L.append("")
    text = "\n".join(L) + "\n"
    path = OUT / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


#: CAD 질량과 부품표가 다른 부품과 그 이유. 시험이 이 목록만 봐준다.
MASS_NOTES: dict[str, str] = {
    "A-03": "부품표는 2\" 페룰(0.22 kg)을 포함한다. CAD 는 만드는 관만 센다",
    "A-04": "부품표는 9 본 평균에 페룰 0.18 kg 을 더한 값. CAD 는 ½\" 대표 관 1 본",
    "A-08": "부품표는 70 × 50 외형으로 셌다. CAD 는 모따기 18 과 Ø20 구멍을 뺀다",
    "B-04": "부품표는 페룰 포함 평균. CAD 는 관만",
    "C-05": "구동부 HOLD — 부품표 4.0 kg 은 어댑터 일체의 개략값이고 "
            "CAD 는 판 한 장이다. 벤더 GA 로 확정된다",
}


def main() -> None:
    build_all()
    written = write_all()
    by_kind: dict[str, list[int]] = {}
    for path, size in written.items():
        key = "README" if path.endswith("README.md") else pathlib.Path(path).suffix
        by_kind.setdefault(key, []).append(size)
    for key in sorted(by_kind):
        sizes = by_kind[key]
        print(f"{key:8s} {len(sizes):3d} 개 · {sum(sizes) / 1024:8.1f} KB")
    print(f"{OUT} — 부품 {len(PARTS)} 종")


if __name__ == "__main__":
    main()
