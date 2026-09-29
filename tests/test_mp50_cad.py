"""CAD 출력 검증 — 절단 DXF, 가공도 DXF, 3D STEP.

CAD 파일은 사람이 넘겨 보지 않는다. 레이저 오퍼레이터가 열어 그대로 자르고,
가공장이 STEP 을 열어 공구를 건다. 그래서 여기서 보는 것은 "예쁘게 나왔나" 가
아니라 **기계가 잘못 읽을 여지가 없는가** 다.

- 윤곽이 닫혔는가. 열려 있으면 CAM 이 경로를 못 만든다.
- 구멍이 시계, 바깥이 반시계인가. 뒤집히면 구멍을 바깥으로 읽는다.
- 잘라낼 형상이 사 오는 소재 안에 드는가. 넘치면 발주부터 틀린다.
- 파일의 범위($EXTMIN·$EXTMAX)가 실제 형상과 같은가.
- STEP 의 모든 모서리가 정확히 두 면에 쓰였는가. 아니면 솔리드가 아니다.
- 다시 잰 질량이 부품표와 맞는가. 다르면 왜 다른지 목록에 있어야 한다.

외부 라이브러리는 쓰지 않는다 — CI 는 아무것도 설치하지 않는다. DXF·STEP 모두
형식이 단순해서 표준 라이브러리로 되읽을 수 있다. (개발 중에는 ezdxf 와
OpenCascade 로 같은 파일을 한 번 더 읽어 확인했고, 33 개 STEP 전부가 유효한
솔리드로, 부피는 해석값과 0.0000 % 차로 들어왔다.)
"""

import math
import pathlib
import re
import subprocess
import sys
import unittest

from . import _path  # noqa: F401

import _mp50_cad as K
import _mp50_dxf as X
import _mp50_step as P
import mp50_cad as C

from mp50_separator import GEOMETRY as G
from mp50_separator.geometry import NOZZLES

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAD = ROOT / "docs" / "cad"


def build():
    if not C.PARTS:
        C.build_all()
    return C.PARTS


class TestProfileMaths(unittest.TestCase):
    """윤곽의 면적·둘레·범위가 해석값과 맞는가 — 여기가 틀리면 전부 틀린다."""

    def test_circle(self):
        loop = K.circle_loop(0.0, 0.0, 50.0)
        self.assertAlmostEqual(K.area(loop), math.pi * 2500.0, places=6)
        self.assertAlmostEqual(K.perimeter(loop), 2 * math.pi * 50.0, places=6)
        self.assertEqual([round(v, 6) for v in K.bounds(loop)], [-50.0, -50.0, 50.0, 50.0])

    def test_hole_is_clockwise(self):
        self.assertLess(K.area(K.hole(0.0, 0.0, 10.0)), 0.0)

    def test_ring(self):
        r = K.ring(0.0, 0.0, 480.0, 406.0)
        self.assertAlmostEqual(r.area_mm2, math.pi / 4 * (480.0 ** 2 - 406.0 ** 2), places=6)
        r.check()

    def test_rounded_rectangle(self):
        loop = K.rect_loop(0.0, 0.0, 100.0, 60.0, 10.0)
        self.assertAlmostEqual(K.area(loop), 100 * 60 - (4 - math.pi) * 100.0, places=6)
        self.assertEqual([round(v, 6) for v in K.bounds(loop)], [0.0, 0.0, 100.0, 60.0])

    def test_fillet_bulges_past_its_tangent_points(self):
        """모서리 R 은 접점보다 바깥으로 부푼다 — 꼭짓점만 보면 범위를 놓친다."""
        tri = K.polygon_loop([(0, 0), (100, 0), (0, 100)], 9.0)
        _x0, _y0, x1, _y1 = K.bounds(tri)
        self.assertGreater(x1, 87.0)
        self.assertLess(x1, 100.0)

    def test_reverse_only_flips_the_sign(self):
        loop = K.rect_loop(0.0, 0.0, 100.0, 60.0, 8.0)
        self.assertAlmostEqual(K.area(K.reverse(loop)), -K.area(loop), places=9)


class TestPartsAreComplete(unittest.TestCase):
    def setUp(self):
        self.parts = build()

    def test_every_fabricated_part_has_cad(self):
        made = [p.no for a in C.ASSEMBLIES for p in a.parts if p.made == "제작"]
        self.assertEqual(sorted(self.parts), sorted(made))

    def test_sign_convention_holds(self):
        for no, c in self.parts.items():
            with self.subTest(no):
                c.profile.check()

    def test_blank_fits_the_stock(self):
        """자를 형상이 사 오는 소재 안에 드는가 — 넘치면 발주부터 틀린다."""
        bad = []
        for no, c in self.parts.items():
            blank = plate_blank(c.part.stock)
            if blank is None:
                continue
            w, h = c.profile.size
            bw, bh = blank
            if not ((w <= bw + 1e-6 and h <= bh + 1e-6)
                    or (h <= bw + 1e-6 and w <= bh + 1e-6)):
                bad.append(f"{no}: 형상 {w:.1f}×{h:.1f} > 소재 {bw:.1f}×{bh:.1f}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_mass_matches_the_bill_of_materials(self):
        bad = []
        for no, c in self.parts.items():
            if no in C.MASS_NOTES:
                continue
            want = c.part.unit_kg
            tol = max(0.02, want * 0.12)
            if abs(c.calc_kg - want) > tol:
                bad.append(f"{no}: CAD {c.calc_kg:.3f} vs 부품표 {want:.3f}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_documented_mass_gaps_are_real(self):
        """설명해 둔 차이가 실제로 남아 있는가 — 고쳐졌으면 목록에서 빼야 한다."""
        stale = []
        for no in C.MASS_NOTES:
            c = self.parts[no]
            want = c.part.unit_kg
            if abs(c.calc_kg - want) <= max(0.02, want * 0.12):
                stale.append(no)
        self.assertEqual(stale, [], f"차이가 사라진 항목이 MASS_NOTES 에 남아 있다: {stale}")


def plate_blank(stock: str) -> tuple[float, float] | None:
    """소재 규격에서 판재 크기를 읽는다. 판재가 아니면 None."""
    if "판재" not in stock and "타공판" not in stock:
        return None
    m = re.search(r"([\d.]+)\s*[×x]\s*([\d.]+)", stock)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"Ø([\d.]+)", stock)
    if m:
        return float(m.group(1)), float(m.group(1))
    return None


class TestGeometryComesFromTheModel(unittest.TestCase):
    """CAD 의 숫자가 기하 모듈에서 나왔는가 — 손으로 적으면 드리프트한다."""

    def setUp(self):
        self.parts = build()

    def test_shell_development(self):
        w, h = self.parts["A-01"].profile.size
        self.assertAlmostEqual(w, G.shell_development_length_mm, places=6)
        self.assertAlmostEqual(h, G.shell_height_mm, places=6)

    def test_shell_has_one_hole_per_nozzle(self):
        self.assertEqual(len(self.parts["A-01"].profile.holes), len(NOZZLES))

    def test_the_weld_seam_does_not_cut_a_nozzle(self):
        """세로이음 위에 구멍이 앉으면 전개 평판 끝에서 반쪽씩 잘린다."""
        c = self.parts["A-01"]
        dev = G.shell_development_length_mm
        for x, _y, dia in C.hole_positions(c):
            with self.subTest(x=x):
                self.assertGreater(x - dia / 2, 0.0)
                self.assertLess(x + dia / 2, dev)

    def test_cone_development(self):
        c = self.parts["A-02"]
        r = max(math.hypot(v[0], v[1]) for v in c.profile.outer)
        self.assertAlmostEqual(r, G.cone_development_outer_r_mm, places=6)

    def test_flange_bolt_pattern(self):
        holes = [h for h in C.hole_positions(self.parts["A-05"]) if abs(h[2] - 14.0) < 1e-6]
        self.assertEqual(len(holes), G.top_flange_bolts)
        w, h = self.parts["A-05"].profile.size
        for x, y, _d in holes:
            self.assertAlmostEqual(math.hypot(x - w / 2, y - h / 2),
                                   G.top_flange_pcd_mm / 2, places=6)

    def test_cover_bolts_match_the_flange(self):
        """커버와 플랜지는 같은 지그로 뚫는다 — 배치가 다르면 안 들어간다."""
        def bolts(no):
            w, h = self.parts[no].profile.size
            return sorted(round(math.degrees(math.atan2(y - h / 2, x - w / 2)) % 360.0, 4)
                          for x, y, d in C.hole_positions(self.parts[no])
                          if abs(d - 14.0) < 1e-6)
        self.assertEqual(bolts("B-01"), bolts("A-05"))


class TestCutFiles(unittest.TestCase):
    """CAM 이 그대로 먹는 파일 — 여기 실수는 잘린 판으로 돌아온다."""

    def setUp(self):
        self.parts = build()

    def files(self):
        for no, c in self.parts.items():
            path = CAD / "dxf" / "cut" / f"MP50-C-{no}-CUT.dxf"
            yield no, c, path

    def test_every_part_has_a_cut_file(self):
        for no, _c, path in self.files():
            with self.subTest(no):
                self.assertTrue(path.exists(), f"{path} 가 없다 — mp50_cad.py 를 돌릴 것")

    def test_cut_files_carry_no_text(self):
        """글자가 섞이면 오퍼레이터가 그것까지 자를 수 있다."""
        for no, _c, path in self.files():
            with self.subTest(no):
                ents = X.entities(X.parse(X.read(path)))
                kinds = {e["type"] for e in ents}
                self.assertNotIn("TEXT", kinds)
                self.assertNotIn("MTEXT", kinds)

    def test_every_contour_is_closed(self):
        for no, c, path in self.files():
            with self.subTest(no):
                text = X.read(path)
                ents = X.entities(X.parse(text))
                polys = [e for e in ents if e["type"] == "POLYLINE"]
                self.assertEqual(len(polys), 1 + len(c.profile.holes))
                for pl in polys:
                    self.assertEqual(pl.get(70, ["0"])[0], "1", "닫히지 않은 윤곽")

    def test_extents_match_the_shape(self):
        """파일이 적은 범위와 실제 형상이 달라지면 화면 맞춤이 어긋난다."""
        for no, c, path in self.files():
            with self.subTest(no):
                text = X.read(path)
                lo, hi = header_point(text, "$EXTMIN"), header_point(text, "$EXTMAX")
                w, h = c.profile.size
                self.assertAlmostEqual(lo[0], 0.0, places=5)
                self.assertAlmostEqual(lo[1], 0.0, places=5)
                self.assertAlmostEqual(hi[0] - lo[0], w, places=3)
                self.assertAlmostEqual(hi[1] - lo[1], h, places=3)

    def test_written_in_cp949_for_korean_cad(self):
        path = CAD / "dxf" / "dwg" / "MP50-C-A-05.dxf"
        raw = path.read_bytes()
        self.assertIn(b"ANSI_949", raw)
        self.assertIn("상단 플랜지", raw.decode("cp949"))


def header_point(text: str, name: str) -> tuple[float, float]:
    pairs = X.parse(text)
    for i, (code, value) in enumerate(pairs):
        if code == 9 and value == name:
            return float(pairs[i + 1][1]), float(pairs[i + 2][1])
    raise AssertionError(f"{name} 이 없다")


class TestDrawingFiles(unittest.TestCase):
    def setUp(self):
        self.parts = build()

    def test_every_part_has_a_drawing(self):
        for no in self.parts:
            with self.subTest(no):
                self.assertTrue((CAD / "dxf" / "dwg" / f"MP50-C-{no}.dxf").exists())

    def test_title_block_carries_the_part(self):
        for no, c in self.parts.items():
            with self.subTest(no):
                text = X.read(CAD / "dxf" / "dwg" / f"MP50-C-{no}.dxf")
                self.assertIn(f"MP50-C-{no}", text)
                self.assertIn(f"{no} {c.part.name}", text)
                self.assertIn(c.part.material, text)

    def test_scale_comes_from_the_standard_ladder(self):
        allowed = {C.scale_text(s) for s in C.SCALES}
        for no, c in self.parts.items():
            with self.subTest(no):
                text = X.read(CAD / "dxf" / "dwg" / f"MP50-C-{no}.dxf")
                found = set(re.findall(r"척도 (\S+)", text))
                self.assertTrue(found)
                self.assertTrue(found <= allowed, f"사다리 밖 축척 {found - allowed}")

    def test_hole_table_lists_every_hole_group(self):
        for no, c in self.parts.items():
            if not c.holes:
                continue
            with self.subTest(no):
                text = X.read(CAD / "dxf" / "dwg" / f"MP50-C-{no}.dxf")
                for dia, _qty, _why in c.holes:
                    self.assertIn(f"Ø{dia:g}", text)


class TestStepFiles(unittest.TestCase):
    """3D 솔리드 — 위상이 닫혀야 CAD 가 솔리드로 읽는다."""

    def setUp(self):
        self.parts = build()

    def step(self, no: str) -> str:
        return (CAD / "step" / f"MP50-{no}.stp").read_text(encoding="ascii")

    def test_every_part_has_a_solid(self):
        for no, c in self.parts.items():
            with self.subTest(no):
                self.assertTrue(c.step_solids())
                self.assertTrue((CAD / "step" / f"MP50-{no}.stp").exists())

    def test_header_declares_ap214_and_millimetres(self):
        text = self.step("A-05")
        self.assertIn("ISO-10303-21;", text)
        self.assertIn("AUTOMOTIVE_DESIGN", text)
        self.assertIn("SI_UNIT(.MILLI.,.METRE.)", text)
        self.assertTrue(text.rstrip().endswith("END-ISO-10303-21;"))

    def test_every_edge_is_used_by_exactly_two_faces(self):
        """닫힌 다양체의 조건이다. 하나라도 어긋나면 껍질이지 솔리드가 아니다."""
        for no in self.parts:
            with self.subTest(no):
                ents = P.parse_entities(self.step(no))
                used: dict[int, int] = {}
                for name, args in ents.values():
                    if name != "ORIENTED_EDGE":
                        continue
                    ref = int(args.rsplit("#", 1)[1].split(",")[0])
                    used[ref] = used.get(ref, 0) + 1
                curves = [r for r, (n, _) in ents.items() if n == "EDGE_CURVE"]
                self.assertTrue(curves)
                odd = [r for r in curves if used.get(r, 0) != 2]
                self.assertEqual(odd, [], f"{len(odd)} 개 모서리가 두 번 쓰이지 않았다")

    def test_every_reference_resolves(self):
        for no in self.parts:
            with self.subTest(no):
                text = self.step(no)
                ents = P.parse_entities(text)
                for ref, (_name, args) in ents.items():
                    for target in re.findall(r"#(\d+)", args):
                        self.assertIn(int(target), ents,
                                      f"#{ref} 가 없는 #{target} 을 가리킨다")

    def test_solid_count_matches(self):
        for no, c in self.parts.items():
            with self.subTest(no):
                ents = P.parse_entities(self.step(no))
                breps = [1 for n, _ in ents.values() if n == "MANIFOLD_SOLID_BREP"]
                self.assertEqual(len(breps), len(c.step_solids()))

    def test_volume_by_divergence_matches_the_analytic_value(self):
        """면 방향이 하나라도 뒤집히면 부피가 어긋난다.

        발산정리 쪽은 호를 직선으로 펴므로 1 % 안쪽에서 어긋난다. 면이 뒤집히면
        그 면의 기여가 부호를 바꿔 값이 통째로 달라지므로 이 폭으로 충분하다.
        정확한 값은 해석식이 갖고 있고, 개발 중 OpenCascade 로 33 개 전부가
        0.0000 % 차로 들어오는 것을 확인했다.
        """
        for no, c in self.parts.items():
            with self.subTest(no):
                for s in c.step_solids():
                    self.assertGreater(s.volume_mm3, 0.0, "부피가 음수 — 면이 뒤집혔다")
                    self.assertLessEqual(s.volume_mm3, s.volume_analytic * 1.01)
                    self.assertGreater(s.volume_mm3, s.volume_analytic * 0.99)

    def test_korean_names_are_escaped(self):
        """STEP 본문은 아스키다. 한글은 \\X2\\ 표기로 들어가야 한다."""
        text = self.step("D-02")
        self.assertTrue(all(ord(ch) < 128 for ch in text))
        self.assertIn("\\X2\\", text)


class TestCadIsGenerated(unittest.TestCase):
    """CAD 파일은 손으로 고치는 것이 아니다 — 다시 돌리면 같은 것이 나와야 한다."""

    def test_regenerating_is_a_no_op(self):
        before = {p: p.read_bytes() for p in sorted(CAD.rglob("*")) if p.is_file()}
        subprocess.run([sys.executable, str(ROOT / "tools" / "mp50_cad.py")],
                       check=True, capture_output=True, cwd=ROOT)
        after = {p: p.read_bytes() for p in sorted(CAD.rglob("*")) if p.is_file()}
        self.assertEqual(sorted(before), sorted(after), "파일 목록이 달라졌다")
        changed = [str(p.relative_to(ROOT)) for p in before if before[p] != after[p]]
        self.assertEqual(changed, [], "python tools/mp50_cad.py 를 돌리고 커밋할 것")

    def test_index_lists_every_part(self):
        text = (CAD / "README.md").read_text(encoding="utf-8")
        for no in build():
            self.assertIn(f"`{no}`", text)


if __name__ == "__main__":
    unittest.main()
