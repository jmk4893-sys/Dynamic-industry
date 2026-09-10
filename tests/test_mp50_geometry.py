"""MP-50 확정 기하 — 원본 문서와 물리적 성립 여부를 함께 검증.

원본 3종의 치수가 서로 어긋나므로 ``geometry.py`` 는 그중 하나를 고른 것이
아니라 **셋을 동시에 만족하는 해석**을 택했다. 그 해석이 맞다는 근거는
연구문서 Rev.0 이 따로 적어 둔 세 값 — 동체 상단 Z946, 커버 상면 Z951,
전용적 89.9 L — 이 한 원점에서 동시에 맞아떨어진다는 것뿐이다.
그 일치가 깨지면 기하 해석이 틀린 것이므로 여기서 잡는다.
"""

import math
import unittest

from . import _path  # noqa: F401

from mp50_separator import GEOMETRY as G
from mp50_separator.components import ASSEMBLIES, BY_CODE, dry_mass_kg, wet_mass_kg
from mp50_separator.conflicts import CONFLICTS
from mp50_separator.geometry import COVER_NOZZLES, NOZZLES


class TestDatumMatchesSourceDocument(unittest.TestCase):
    """[R] 연구문서 Rev.0 §2 가 직접 적은 값과 맞는가."""

    def test_cone_apex_height(self):
        # 200 / tan30° — [R] 의 "Cone H346" 은 이 가상 정점높이다.
        self.assertAlmostEqual(G.cone_apex_height_mm, 346.41, places=2)

    def test_shell_top_elevation(self):
        self.assertAlmostEqual(G.shell_top_z, 946.41, places=2)

    def test_cover_top_elevation(self):
        self.assertAlmostEqual(G.cover_top_z, 951.41, places=2)

    def test_total_volume(self):
        # [R] "총용적 약 89.9 L". 위 세 표고와 같은 원점에서 나와야 한다.
        self.assertAlmostEqual(G.total_volume_l, 89.9, delta=0.1)

    def test_three_figures_share_one_origin(self):
        """세 값이 우연히 맞은 게 아님을 보인다 — 원점을 흔들면 모두 깨진다."""
        from mp50_separator.geometry import Geometry

        wrong = Geometry(cone_included_deg=50.0)   # 다른 원뿔각 = 다른 원점
        self.assertNotAlmostEqual(wrong.shell_top_z, 946.41, places=1)
        self.assertNotAlmostEqual(wrong.total_volume_l, 89.9, places=1)


class TestConeClosure(unittest.TestCase):
    """원뿔이 실제로 닫히는가 — [D1] 이 걸린 항목 (C1)."""

    def test_truncated_height(self):
        expected = G.cone_apex_height_mm * (1 - G.cone_outlet_id_mm / G.tank_id_mm)
        self.assertAlmostEqual(G.cone_truncated_height_mm, expected, places=6)

    def test_diameter_is_linear_in_z(self):
        for z in (G.cone_outlet_z, 150.0, 250.0, G.shell_bottom_z):
            self.assertAlmostEqual(
                G.cone_id_at(z), G.tank_id_mm * z / G.cone_apex_height_mm, places=6)

    def test_outlet_and_top_diameters(self):
        self.assertAlmostEqual(G.cone_id_at(G.cone_outlet_z), G.cone_outlet_id_mm, places=6)
        self.assertAlmostEqual(G.cone_id_at(G.shell_bottom_z), G.tank_id_mm, places=6)

    def test_original_h150_does_not_close(self):
        """[D1] 의 H150 + 60° 로는 Ø400 → Ø38 이 되지 않는다."""
        needed = (400 - 38) / 2 / math.tan(math.radians(30))
        self.assertGreater(needed, 300)     # 150 이 아니라 313.5 가 필요하다

    def test_development_is_a_half_circle(self):
        # 60° 원뿔의 전개 사잇각 = 360 × sin30° = 180°. 절단 원도의 근거다.
        self.assertAlmostEqual(G.cone_development_angle_deg, 180.0, places=6)
        self.assertAlmostEqual(G.cone_development_outer_r_mm, 400.0, places=6)


class TestVolumes(unittest.TestCase):
    def test_volume_at_level_is_monotone(self):
        prev = -1.0
        for z in range(60, 947, 20):
            v = G.volume_at_l(float(z))
            self.assertGreater(v, prev)
            prev = v

    def test_operating_charge(self):
        # 액면 Z720 은 스키머·오버플로 표고에 구속된다 (C6).
        self.assertAlmostEqual(G.operating_volume_l, 61.4, delta=0.1)

    def test_nominal_level_round_trips(self):
        self.assertAlmostEqual(
            G.volume_at_l(G.nominal_level_z), G.nominal_charge_l, places=6)

    def test_named_50_l_is_below_skimmer(self):
        """명칭 50 L 액면에서는 스키머가 층에 닿지 않는다 — C6 의 근거."""
        self.assertLess(G.nominal_level_z, G.skimmer_z - G.skimmer_z_tolerance_mm)

    def test_shell_volume(self):
        expected = math.pi / 4 * (G.tank_id_mm / 1000) ** 2 * (G.shell_height_mm / 1000) * 1000
        self.assertAlmostEqual(G.shell_volume_l, expected, places=6)


class TestInternalClearances(unittest.TestCase):
    """부품끼리 부딪히지 않는가."""

    def test_impeller_clears_baffle(self):
        self.assertGreater(G.impeller_tip_clearance_mm, 0)
        # 축 편심 0.5 + 임펠러 TIR 1.0 을 다 써도 남아야 한다.
        self.assertGreater(G.impeller_tip_clearance_mm - 1.5, 3.0)

    def test_original_80mm_baffle_would_interfere(self):
        """원본 폭 80 은 36 mm 겹친다 — C2 가 BLOCKING 인 이유."""
        inner_r = G.tank_id_mm / 2 - G.baffle_wall_gap_mm - 80.0
        self.assertLess(inner_r - G.impeller_od_mm / 2, -30.0)

    def test_sparger_fits_inside_cone(self):
        self.assertGreater(G.sparger_wall_clearance_mm, 10.0)
        ring_outer = G.sparger_pcd_mm + G.sparger_tube_od_mm
        self.assertLess(ring_outer, G.cone_id_at(G.sparger_z))

    def test_sparger_clears_lower_impeller(self):
        gap = G.lower_impeller_z - G.sparger_z
        self.assertGreater(gap, G.impeller_blade_width_mm)

    def test_skimmer_passes_through_opening(self):
        self.assertGreater(G.skimmer_clearance_mm, 20.0)

    def test_baffle_length_follows_installed_span(self):
        self.assertAlmostEqual(G.baffle_length_mm, G.baffle_top_z - G.baffle_bottom_z)

    def test_baffles_cover_both_impellers(self):
        self.assertLess(G.baffle_bottom_z, G.lower_impeller_z)
        self.assertGreater(G.baffle_top_z, G.upper_impeller_z)


class TestDevelopments(unittest.TestCase):
    """판금 전개 — 여기가 틀리면 롤링 후 치수가 안 나온다."""

    def test_shell_development_uses_neutral_axis(self):
        self.assertAlmostEqual(
            G.shell_development_length_mm,
            math.pi * (G.tank_id_mm + G.shell_thickness_mm), places=6)

    def test_inner_diameter_would_be_short(self):
        inner = math.pi * G.tank_id_mm
        self.assertGreater(G.shell_development_length_mm - inner, 9.0)

    def test_cone_slant_length(self):
        self.assertAlmostEqual(
            G.cone_slant_length_mm,
            G.cone_development_outer_r_mm - G.cone_development_inner_r_mm, places=6)


class TestInstallation(unittest.TestCase):
    def test_frame_height_gives_discharge_clearance(self):
        self.assertGreaterEqual(G.discharge_clearance_mm, G.DISCHARGE_CATCH_MM)

    def test_floor_offset_puts_support_ring_on_rail(self):
        self.assertAlmostEqual(
            G.elevation_mm(G.support_ring_z - G.support_ring_thickness_mm),
            G.frame_height_mm, places=6)

    def test_freeboard(self):
        self.assertGreater(G.freeboard_mm, 150.0)


class TestNozzles(unittest.TestCase):
    def test_all_shell_nozzles_are_on_the_shell(self):
        for n in NOZZLES:
            self.assertGreaterEqual(n.z_mm, G.shell_bottom_z, n.tag)
            self.assertLessEqual(n.z_mm, G.shell_top_z, n.tag)

    def test_sample_ladder_covers_the_column(self):
        zs = sorted(n.z_mm for n in NOZZLES if n.tag.startswith("N4"))
        self.assertGreaterEqual(len(zs), 5)
        column = G.operating_level_z - G.shell_bottom_z
        self.assertGreaterEqual((zs[-1] - zs[0]) / column, 0.80)

    def test_overflow_and_skimmer_sit_above_the_level(self):
        n2 = next(n for n in NOZZLES if n.tag == "N2")
        self.assertGreater(n2.z_mm, G.operating_level_z)
        self.assertGreater(G.skimmer_z, G.operating_level_z)

    def test_feed_enters_above_the_level(self):
        n1 = next(n for n in NOZZLES if n.tag == "N1")
        self.assertGreater(n1.z_mm, G.operating_level_z)

    def test_air_nozzle_is_below_the_level(self):
        n3 = next(n for n in NOZZLES if n.tag == "N3")
        self.assertLess(n3.z_mm, G.operating_level_z)

    def test_tags_are_unique(self):
        tags = [n.tag for n in NOZZLES] + [n.tag for n in COVER_NOZZLES]
        self.assertEqual(len(tags), len(set(tags)))


class TestBillOfMaterials(unittest.TestCase):
    def test_every_assembly_has_parts(self):
        for a in ASSEMBLIES:
            self.assertTrue(a.parts, a.code)
            self.assertTrue(a.purpose, a.code)

    def test_part_numbers_are_unique(self):
        nos = [p.no for a in ASSEMBLIES for p in a.parts]
        self.assertEqual(len(nos), len(set(nos)))

    def test_status_values_are_known(self):
        allowed = {"RELEASE", "PROPOSED", "HOLD", "VENDOR"}
        for a in ASSEMBLIES:
            for p in a.parts:
                self.assertIn(p.status, allowed, p.no)

    def test_masses_are_derived_not_typed(self):
        """치수를 바꾸면 질량도 따라 움직여야 한다."""
        from mp50_separator.components import _tank
        from mp50_separator.geometry import Geometry

        thicker = _tank(Geometry(shell_thickness_mm=5.0))
        base = next(p for p in BY_CODE["A"].parts if p.no == "A-01")
        grown = next(p for p in thicker.parts if p.no == "A-01")
        self.assertGreater(grown.unit_kg, base.unit_kg * 1.5)

    def test_total_masses_are_plausible(self):
        self.assertGreater(dry_mass_kg(), 80)
        self.assertLess(dry_mass_kg(), 260)
        self.assertGreater(wet_mass_kg(), dry_mass_kg() + 60)

    def test_drive_assembly_is_held(self):
        self.assertTrue(BY_CODE["C"].held, "구동부 인터페이스는 HOLD 여야 한다")
        self.assertTrue(BY_CODE["C"].vendor_scope)


class TestConflictRegister(unittest.TestCase):
    def test_every_conflict_is_documented(self):
        for c in CONFLICTS:
            self.assertTrue(c.resolution, c.ref)
            self.assertGreater(len(c.rationale), 80, c.ref)
            self.assertGreaterEqual(len(c.sources), 2, c.ref)
            self.assertIn(c.severity, {"BLOCKING", "MAJOR", "MINOR"}, c.ref)
            self.assertIn(c.approval, {"RESOLVED", "PROPOSED"}, c.ref)

    def test_refs_are_unique(self):
        refs = [c.ref for c in CONFLICTS]
        self.assertEqual(len(refs), len(set(refs)))

    def test_blocking_conflicts_are_the_two_we_found(self):
        blocking = {c.ref for c in CONFLICTS if c.blocking}
        self.assertEqual(blocking, {"C1", "C2"})


if __name__ == "__main__":
    unittest.main()
