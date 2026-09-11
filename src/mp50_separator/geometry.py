"""MP-50 확정 기하 — 기준좌표계와 그로부터 유도되는 모든 치수.

**기준좌표계.** Z 는 원뿔의 가상 정점(apex)을 0 으로 하고 위를 양으로 잡는다.
연구문서 Rev.0 의 "Cone H346 / Shell H600 / Shell top Z946" 이 그대로 맞아
떨어지는 유일한 원점이기 때문이다 — 346.4 + 600 = 946.4 ≈ Z946.
θ 는 N1(급광구)을 0° 로 하고 위에서 볼 때 반시계방향을 양으로 잡는다.

**원뿔은 가상 정점까지의 높이로 정의한다.** 60° 원뿔이 Ø400 에서 한 점으로
모이는 높이가 200/tan30° = 346.4 mm 다. 실제로는 배출 스터브에서 잘리므로
동체 몸통의 실제 높이는 이보다 짧다. 원본 도면 중 하나가 "H150 + 60°" 로
적혀 있었는데, 그 조합은 Ø400 에서 Ø38 로 닫히지 않는다 (``conflicts.py`` C1).

이 파일의 값은 전부 하나의 ``Geometry`` 인스턴스에서 유도된다. 치수를 하나
고치면 용적·액면·전개도·간섭검사가 함께 움직이므로, 도면과 계산이 서로 다른
장치를 가리키는 일이 생기지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: 대기압 상태의 개방형 용기다. 두께는 강도가 아니라 용접 변형과 롤링
#: 가공성으로 정해진다 — Ø400 동체를 t3 미만으로 말면 진원도를 못 잡는다.
SHELL_THICKNESS_MM = 3.0


@dataclass(frozen=True)
class Nozzle:
    """동체·커버에 붙는 노즐 하나.

    Attributes:
        tag: 노즐 번호 (N1, B2 …).
        service: 용도.
        size: 호칭 (위생배관 Tri-clamp 기준).
        tube_od_mm: 접속 튜브 바깥지름.
        theta_deg: 방위각 — N1 을 0°, 위에서 볼 때 반시계 양.
        z_mm: 노즐 중심 표고.
        tolerance_mm: 표고 공차 (0 이면 잠금 치수).
        note: 시공 참고.
    """

    tag: str
    service: str
    size: str
    tube_od_mm: float
    theta_deg: float
    z_mm: float
    tolerance_mm: float = 0.0
    note: str = ""

    @property
    def projection_mm(self) -> float:
        """동체 바깥면에서 클램프 접합면까지 돌출 길이.

        렌치와 클램프를 돌릴 공간이 필요하다. 위생배관 클램프는 나비너트를
        한 바퀴 돌릴 수 있어야 하므로 최소 60 mm, 여기서는 75 mm 로 통일한다.
        """
        return 75.0


@dataclass(frozen=True)
class Geometry:
    """MP-50 용기·내부물의 확정 기하 (단위 mm, 용적 L).

    생성자 인자는 **원본 문서가 직접 지정한 값**뿐이다. 나머지는 전부
    property 로 유도한다.
    """

    # --- 용기 ---
    tank_id_mm: float = 400.0
    shell_height_mm: float = 600.0
    shell_thickness_mm: float = SHELL_THICKNESS_MM
    cone_included_deg: float = 60.0
    #: 배출 스터브 안지름. 2 in 위생튜브(Ø63.5 × t2.0)의 안지름이다.
    #: 원본은 Ø50.8(1.5 in)이었으나 1.5 in/2 in 배출시험을 재용접 없이
    #: 모두 하려면 스터브가 큰 쪽이어야 한다 (``conflicts.py`` C3).
    cone_outlet_id_mm: float = 59.5
    cone_thickness_mm: float = SHELL_THICKNESS_MM

    # --- 액면 ---
    #: 운전 액면. 스키머(Z725)와 N2 오버플로(Z735) 표고에 구속된다.
    operating_level_z: float = 720.0
    #: 명칭상의 50 L 이 되는 액면. 이 아래로 내리면 스키머가 층에 닿지 않는다.
    nominal_charge_l: float = 50.0

    # --- 커버 ---
    cover_thickness_mm: float = 5.0
    #: 중앙 보강 허브 — 구동부·씰 하중을 받는 자리. 벤더 GA 전까지 HOLD.
    cover_hub_od_mm: float = 220.0
    cover_hub_thickness_mm: float = 10.0
    #: 동체 상단 플랜지 (커버 체결). 가스켓은 플랜지 면에 판 홈에 들어가므로
    #: 커버 상면은 Z951 (= 동체 상단 + 커버 t5) 을 유지한다.
    top_flange_od_mm: float = 480.0
    top_flange_pcd_mm: float = 450.0
    top_flange_thickness_mm: float = 10.0
    top_flange_bolts: int = 12
    top_flange_bolt: str = "M12"

    # --- 교반축 · 임펠러 ---
    shaft_od_mm: float = 25.0
    impeller_od_mm: float = 300.0
    impeller_blades: int = 4
    impeller_pitch_deg: float = 45.0
    #: 블레이드 현 길이. 4PBT 표준인 D/5 다.
    impeller_blade_width_mm: float = 60.0
    impeller_blade_thickness_mm: float = 3.0
    impeller_hub_od_mm: float = 60.0
    impeller_hub_length_mm: float = 60.0
    lower_impeller_z: float = 430.0
    upper_impeller_z: float = 610.0
    impeller_z_tolerance_mm: float = 30.0

    # --- 배플 ---
    #: 원본의 80 mm 는 Ø300 임펠러와 36 mm 간섭한다 (``conflicts.py`` C2).
    #: T/11.4 로 줄여 팁 간극 10 mm 를 확보했다.
    baffle_width_mm: float = 35.0
    baffle_thickness_mm: float = 3.0
    baffle_count: int = 4
    baffle_bottom_z: float = 390.0
    baffle_top_z: float = 690.0
    #: 벽면 이격 — 벽과 배플 사이 사각지대에 분말이 쌓이지 않게 띄운다.
    baffle_wall_gap_mm: float = 6.0

    # --- 급기 분산링 ---
    sparger_pcd_mm: float = 250.0
    sparger_tube_od_mm: float = 12.0
    sparger_tube_thickness_mm: float = 1.5
    sparger_z: float = 300.0
    sparger_z_tolerance_mm: float = 20.0
    sparger_holes: int = 12
    sparger_hole_dia_mm: float = 1.5
    #: DOE 최대 급기량 (L/min, 상온상압 환산).
    air_max_lpm: float = 10.0

    # --- 스키머 ---
    skimmer_od_mm: float = 300.0
    skimmer_height_mm: float = 50.0
    skimmer_z: float = 725.0
    skimmer_z_tolerance_mm: float = 20.0

    # --- 프레임 ---
    frame_width_mm: float = 550.0
    #: 바닥에서 상부 레일 윗면까지. 임의로 정한 값이 아니라 배출부에서
    #: 역산했다 — ``discharge_clearance_mm`` 주석 참조.
    frame_height_mm: float = 750.0
    frame_tube_mm: float = 40.0
    frame_tube_thickness_mm: float = 2.0
    #: 용기를 받는 지지링. 동체/콘 용접선을 피해 그 위에 붙인다.
    support_ring_od_mm: float = 480.0
    support_ring_thickness_mm: float = 8.0
    support_ring_z: float = 400.0

    nozzles: tuple[Nozzle, ...] = field(default_factory=lambda: NOZZLES)

    # ------------------------------------------------------------------
    # 원뿔
    # ------------------------------------------------------------------
    @property
    def cone_half_angle_deg(self) -> float:
        return self.cone_included_deg / 2.0

    @property
    def cone_apex_height_mm(self) -> float:
        """Ø400 에서 한 점으로 모이기까지의 높이 = 동체 하단 표고."""
        return (self.tank_id_mm / 2.0) / math.tan(math.radians(self.cone_half_angle_deg))

    @property
    def cone_truncated_height_mm(self) -> float:
        """실제로 제작하는 원뿔대의 높이 (배출 스터브에서 잘린 뒤)."""
        return self.cone_apex_height_mm * (1.0 - self.cone_outlet_id_mm / self.tank_id_mm)

    @property
    def cone_outlet_z(self) -> float:
        """콘 배출면(스터브 용접선) 표고."""
        return self.cone_apex_height_mm - self.cone_truncated_height_mm

    @property
    def cone_slant_length_mm(self) -> float:
        """콘 모선 길이 — 전개도 반지름 차이가 된다."""
        return self.cone_truncated_height_mm / math.cos(math.radians(self.cone_half_angle_deg))

    def cone_id_at(self, z: float) -> float:
        """표고 z 에서의 콘 안지름. 콘 구간 밖이면 ValueError."""
        if not (self.cone_outlet_z - 1e-9 <= z <= self.shell_bottom_z + 1e-9):
            raise ValueError(f"Z{z:.1f} 은 콘 구간(Z{self.cone_outlet_z:.1f}~Z{self.shell_bottom_z:.1f}) 밖")
        return self.tank_id_mm * z / self.cone_apex_height_mm

    # --- 콘 전개도 ---
    @property
    def cone_development_outer_r_mm(self) -> float:
        """전개도 바깥 반지름 = Ø400 쪽 모선 길이."""
        return (self.tank_id_mm / 2.0) / math.sin(math.radians(self.cone_half_angle_deg))

    @property
    def cone_development_inner_r_mm(self) -> float:
        return (self.cone_outlet_id_mm / 2.0) / math.sin(math.radians(self.cone_half_angle_deg))

    @property
    def cone_development_angle_deg(self) -> float:
        """전개 부채꼴의 사잇각 = 360° × sin(반각)."""
        return 360.0 * math.sin(math.radians(self.cone_half_angle_deg))

    # ------------------------------------------------------------------
    # 동체
    # ------------------------------------------------------------------
    @property
    def shell_bottom_z(self) -> float:
        return self.cone_apex_height_mm

    @property
    def shell_top_z(self) -> float:
        return self.shell_bottom_z + self.shell_height_mm

    @property
    def cover_top_z(self) -> float:
        return self.shell_top_z + self.cover_thickness_mm

    @property
    def shell_od_mm(self) -> float:
        return self.tank_id_mm + 2.0 * self.shell_thickness_mm

    @property
    def shell_development_length_mm(self) -> float:
        """동체 전개 길이 — **중립축(판 두께 중앙)** 둘레다.

        안지름이나 바깥지름으로 자르면 롤링 후 Ø400 이 안 나온다.
        """
        return math.pi * (self.tank_id_mm + self.shell_thickness_mm)

    # ------------------------------------------------------------------
    # 용적
    # ------------------------------------------------------------------
    @staticmethod
    def _frustum_l(d_lower_mm: float, d_upper_mm: float, height_mm: float) -> float:
        """원뿔대 용적 (L). V = πh/12 · (D² + Dd + d²)."""
        d, du, h = d_lower_mm / 1000.0, d_upper_mm / 1000.0, height_mm / 1000.0
        return math.pi * h / 12.0 * (du * du + du * d + d * d) * 1000.0

    @property
    def cone_volume_l(self) -> float:
        return self._frustum_l(self.cone_outlet_id_mm, self.tank_id_mm, self.cone_truncated_height_mm)

    @property
    def shell_volume_l(self) -> float:
        return self._frustum_l(self.tank_id_mm, self.tank_id_mm, self.shell_height_mm)

    @property
    def total_volume_l(self) -> float:
        """동체 상단(Z946)까지 채웠을 때의 전용적."""
        return self.cone_volume_l + self.shell_volume_l

    def volume_at_l(self, z: float) -> float:
        """액면 z 까지의 용적 (L)."""
        if z <= self.cone_outlet_z:
            return 0.0
        if z <= self.shell_bottom_z:
            return self._frustum_l(self.cone_outlet_id_mm, self.cone_id_at(z), z - self.cone_outlet_z)
        return self.cone_volume_l + self._frustum_l(self.tank_id_mm, self.tank_id_mm, z - self.shell_bottom_z)

    def level_for_l(self, volume_l: float) -> float:
        """용적 (L) 을 담는 액면 표고. 동체 구간만 역산한다."""
        if volume_l < self.cone_volume_l:
            raise ValueError("콘 구간 액면은 역산하지 않는다 — 운전영역이 아니다")
        rise_m = (volume_l - self.cone_volume_l) / 1000.0 / (math.pi / 4.0 * (self.tank_id_mm / 1000.0) ** 2)
        return self.shell_bottom_z + rise_m * 1000.0

    @property
    def operating_volume_l(self) -> float:
        """운전 액면 Z720 에서의 실제 장입량."""
        return self.volume_at_l(self.operating_level_z)

    @property
    def nominal_level_z(self) -> float:
        """명칭 50 L 이 되는 액면 — 운전 하한이다."""
        return self.level_for_l(self.nominal_charge_l)

    @property
    def freeboard_mm(self) -> float:
        """운전 액면에서 동체 상단까지 — 분산 중 튀어오름을 받는 여유."""
        return self.shell_top_z - self.operating_level_z

    # ------------------------------------------------------------------
    # 내부물
    # ------------------------------------------------------------------
    @property
    def baffle_length_mm(self) -> float:
        """배플 길이는 설치 표고 범위에서 유도한다 (Z390~690)."""
        return self.baffle_top_z - self.baffle_bottom_z

    @property
    def baffle_inner_radius_mm(self) -> float:
        """배플 안쪽 모서리 반지름 — 임펠러가 지나갈 자리를 남겨야 한다."""
        return self.tank_id_mm / 2.0 - self.baffle_wall_gap_mm - self.baffle_width_mm

    @property
    def impeller_tip_clearance_mm(self) -> float:
        """임펠러 팁과 배플 안쪽 모서리 사이 반지름 간극. 음수면 간섭이다."""
        return self.baffle_inner_radius_mm - self.impeller_od_mm / 2.0

    @property
    def baffle_area_ratio(self) -> float:
        """총 배플폭 / 탱크 지름. 완전 배플 관행은 0.4 (4매 × 0.1 T)."""
        return self.baffle_count * self.baffle_width_mm / self.tank_id_mm

    @property
    def impeller_diameter_ratio(self) -> float:
        """D/T. 통상 0.33~0.5, MP-50 은 분산 목적의 근접 임펠러라 크다."""
        return self.impeller_od_mm / self.tank_id_mm

    @property
    def impeller_spacing_mm(self) -> float:
        return self.upper_impeller_z - self.lower_impeller_z

    @property
    def impeller_blade_radial_mm(self) -> float:
        """블레이드 한 장의 반지름 방향 길이 (허브 바깥면 → 팁)."""
        return (self.impeller_od_mm - self.impeller_hub_od_mm) / 2.0

    @property
    def lower_impeller_clearance_mm(self) -> float:
        """하부 임펠러 중심에서 동체/콘 접선(Z346)까지. C/D 판정용."""
        return self.lower_impeller_z - self.shell_bottom_z

    @property
    def sparger_wall_clearance_mm(self) -> float:
        """분산링 바깥면에서 콘 벽까지 — 링이 콘 안에 들어가는지 본다."""
        cone_id = self.cone_id_at(self.sparger_z)
        ring_outer = self.sparger_pcd_mm + self.sparger_tube_od_mm
        return (cone_id - ring_outer) / 2.0

    @property
    def sparger_hole_area_mm2(self) -> float:
        return self.sparger_holes * math.pi / 4.0 * self.sparger_hole_dia_mm ** 2

    @property
    def sparger_tube_id_mm(self) -> float:
        return self.sparger_tube_od_mm - 2.0 * self.sparger_tube_thickness_mm

    @property
    def skimmer_clearance_mm(self) -> float:
        """스키머 바스켓과 동체 안지름 사이 — Ø400 개구로 빼낼 수 있어야 한다."""
        return (self.tank_id_mm - self.skimmer_od_mm) / 2.0

    # ------------------------------------------------------------------
    # 설치 표고 (바닥 기준)
    # ------------------------------------------------------------------
    @property
    def floor_offset_mm(self) -> float:
        """Z 좌표에 더하면 바닥 기준 높이가 되는 값.

        지지링 밑면이 프레임 상부 레일 윗면에 얹힌다.
        """
        return self.frame_height_mm - (self.support_ring_z - self.support_ring_thickness_mm)

    def elevation_mm(self, z: float) -> float:
        """표고 z 의 바닥 기준 높이."""
        return z + self.floor_offset_mm

    #: 2 in 위생 볼밸브 + 클램프가 콘 배출면 아래로 차지하는 길이.
    DISCHARGE_VALVE_STACK_MM = 150.0
    #: 밸브 출구 아래에 있어야 할 시료받이 공간.
    DISCHARGE_CATCH_MM = 250.0

    @property
    def discharge_elevation_mm(self) -> float:
        """콘 배출면 높이 — 여기에 밸브가 매달린다."""
        return self.elevation_mm(self.cone_outlet_z)

    @property
    def discharge_clearance_mm(self) -> float:
        """밸브 출구 아래에 남는 공간. 프레임 높이는 이 값에서 역산했다.

        배출면 높이 - 밸브 스택. 이것이 시료받이 높이보다 작으면 받을 그릇이
        안 들어가고, 파일럿에서 그건 매 배치마다 겪는 고통이 된다.
        """
        return self.discharge_elevation_mm - self.DISCHARGE_VALVE_STACK_MM

    @property
    def overall_height_mm(self) -> float:
        """커버 상면까지의 전체 높이 (구동부 제외)."""
        return self.elevation_mm(self.cover_top_z)


#: 동체 노즐. 표고·방위각은 연구문서 Rev.0 §2 의 노즐표를 그대로 옮겼고,
#: 시료 사다리(N4A~N4E)만 새로 넣었다 — "시간별 층 높이" 를 KPI 로 잡아두고
#: 불투명한 SUS 동체에 채취구가 한 곳뿐이면 그 값을 잴 방법이 없다.
NOZZLES: tuple[Nozzle, ...] = (
    Nozzle("N1", "급광 투입", '1" TC', 25.4, 0.0, 760.0, 30.0, "액면 위 — 분말+염수 슬러리"),
    Nozzle("N2", "부상물 배출", '1½" TC', 38.1, 90.0, 735.0, 30.0, "오버플로 — 폴리머층 경사분리"),
    Nozzle("N3", "급기", '½" TC', 12.7, 180.0, 520.0, 0.0, "내부 Ø12 강하관으로 분산링 접속 · 체크밸브 필수"),
    Nozzle("N4C", "시료 채취 (중단)", '½" TC', 12.7, 270.0, 560.0, 0.0, "원본 N4 — 사다리의 기준단"),
    Nozzle("N4A", "시료 채취 (최하단)", '½" TC', 12.7, 270.0, 400.0, 0.0, "층 높이 사다리"),
    Nozzle("N4B", "시료 채취 (하단)", '½" TC', 12.7, 270.0, 480.0, 0.0, "층 높이 사다리"),
    Nozzle("N4D", "시료 채취 (상단)", '½" TC', 12.7, 270.0, 640.0, 0.0, "층 높이 사다리"),
    Nozzle("N4E", "시료 채취 (최상단)", '½" TC', 12.7, 270.0, 720.0, 0.0, "층 높이 사다리 · 운전 액면"),
    Nozzle("N5", "사이트글라스", 'Ø100 TC', 104.0, 315.0, 690.0, 0.0, "부상층 형성 육안 확인"),
)

#: 커버 노즐. 계측은 전부 커버에서 내린다 — 동체에 구멍을 더 뚫지 않는다.
COVER_NOZZLES: tuple[Nozzle, ...] = (
    Nozzle("B1", "구동·씰 인터페이스", "Ø220 보스", 220.0, 0.0, 951.0, 0.0, "HOLD — 벤더 GA 확정 전 가공 금지"),
    Nozzle("B2", "전도도/염도 센서", '½" TC', 12.7, 60.0, 951.0, 0.0, "삽입장 425 — 선단 Z526"),
    Nozzle("B3", "온도 RTD Pt100", '½" TC', 12.7, 180.0, 951.0, 0.0, "삽입장 225 — 선단 Z726 · 염수밀도 온도보정용"),
    Nozzle("B4", "예비 / 배기", '½" TC', 12.7, 300.0, 951.0, 0.0, "급기 배출구 — 막으면 가압된다"),
)

#: 확정 기하 — 도면·3D·검증이 모두 이 하나를 본다.
GEOMETRY = Geometry()
