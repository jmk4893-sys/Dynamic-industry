"""플랜트 외장 디자인 체계가 유지되는지 검증.

외형은 규칙 세 가지로 서 있다.

1. **장비는 4단 재질** — T1 트림 / T2 본체 / T3 구동 / T4 제어. 티어 사이는 벌어지고
   티어 안은 좁다. 계열마다 색을 달리 주면 화면에 색상이 12개 떠서 눈이 고정될
   주재질이 사라진다.
2. **서비스 색은 배관이 진다** (ASME A13.1 · KS A 0503). 장비는 지지 않는다.
3. **환경맵이 있어야 금속이 금속으로 보인다.** metalness 0.5–0.9 짜리 표면은
   반사할 것이 없으면 three 가 죽은 회색 확산광으로 그린다.

여기서 실패하면 외형이 종전의 무지개 상태로 되돌아간 것이다.
"""

import pathlib
import re
import unittest

from . import _path  # noqa: F401

MINIAPP = (pathlib.Path(__file__).resolve().parents[1]
           / "docs" / "drawings" / "pv-recycling-miniapp.html")

TOKEN_RE = re.compile(
    r"^\s*(--plant-[a-z-]+):\s*light-dark\(rgb\((\d+) (\d+) (\d+)\),\s*rgb\((\d+) (\d+) (\d+)\)\);",
    re.M)

# 티어 배정. 여기 없는 --plant-* 토큰은 배관·정보색이라 4단 규칙을 받지 않는다.
TIERS = {
    "T1": ["--plant-neutral-metal"],
    "T2": ["--plant-equip-dry", "--plant-equip-wet", "--plant-equip-receiver",
           "--plant-equip-air", "--plant-equip-dewater", "--plant-equip-reagent"],
    "T3": ["--plant-equip-conveyor", "--plant-equip-water",
           "--plant-equip-pump", "--plant-equip-motor"],
    "T4": ["--plant-equip-control"],
}
WITHIN_TIER_MAX = 26.0    # 한 재질로 읽혀야 하므로 좁아야 한다
BETWEEN_TIER_MIN = 30.0   # 4단이 실제로 구분돼야 하므로 벌어져야 한다


def distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


class ExteriorPaletteTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = MINIAPP.read_text(encoding="utf-8")
        cls.light, cls.dark = {}, {}
        for match in TOKEN_RE.finditer(cls.html):
            token = match.group(1)
            cls.light[token] = tuple(int(match.group(i)) for i in (2, 3, 4))
            cls.dark[token] = tuple(int(match.group(i)) for i in (5, 6, 7))

    def theme(self, name):
        return self.dark if name == "dark" else self.light

    def test_every_tier_token_is_defined(self):
        for tier, tokens in TIERS.items():
            for token in tokens:
                self.assertIn(token, self.dark, f"{tier} 토큰 {token} 이 없다")
                self.assertIn(token, self.light, f"{tier} 토큰 {token} 이 없다")

    def test_within_a_tier_the_surfaces_read_as_one_material(self):
        """티어 안이 벌어지면 '한 재질' 이 깨진다 — 계열별 색으로 되돌아간 것이다."""
        for name in ("light", "dark"):
            palette = self.theme(name)
            for tier, tokens in TIERS.items():
                for i, a in enumerate(tokens):
                    for b in tokens[i + 1:]:
                        gap = distance(palette[a], palette[b])
                        self.assertLessEqual(
                            gap, WITHIN_TIER_MAX,
                            f"{name} {tier} 안에서 {a}↔{b} 색차 {gap:.1f} — 한 재질로 읽히지 않는다")

    def test_the_four_tiers_are_actually_distinguishable(self):
        """종전 10계열은 색차 8.9 짜리 쌍이 있어 범례로 성립하지 않았다."""
        for name in ("light", "dark"):
            palette = self.theme(name)
            names = list(TIERS)
            for i, first in enumerate(names):
                for second in names[i + 1:]:
                    gap = min(distance(palette[a], palette[b])
                              for a in TIERS[first] for b in TIERS[second])
                    self.assertGreaterEqual(
                        gap, BETWEEN_TIER_MIN,
                        f"{name} {first}↔{second} 최소 색차 {gap:.1f} — 티어가 구분되지 않는다")

    def test_tiers_descend_in_lightness(self):
        """트림 → 본체 → 구동 → 제어 순으로 밝기가 내려가야 위계가 읽힌다."""
        def lightness(rgb):
            return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        for name in ("light", "dark"):
            palette = self.theme(name)
            means = [sum(lightness(palette[t]) for t in TIERS[k]) / len(TIERS[k])
                     for k in ("T1", "T2", "T3", "T4")]
            for a, b in zip(means, means[1:]):
                self.assertGreater(a, b, f"{name} 티어 밝기 순서가 뒤집혔다: {means}")

    def test_structure_and_belt_are_not_holes(self):
        """구조강·벨트가 순흑이면 화면 아래가 부품이 아니라 배경의 결손으로 읽힌다."""
        for token, floor in (("--plant-structure", 60), ("--plant-belt", 40)):
            for name in ("light", "dark"):
                rgb = self.theme(name)[token]
                self.assertGreaterEqual(
                    max(rgb), floor, f"{name} {token}={rgb} 이 너무 어둡다")
        self.assertNotIn("makeMaterial(0x050505", self.html,
                         "벨트가 순흑 리터럴로 돌아갔다 — --plant-belt 를 써야 한다")

    def test_equipment_does_not_carry_service_colour(self):
        """장비 색은 채도가 낮아야 한다 — 서비스 색은 배관이 진다."""
        for tier in ("T1", "T2", "T3", "T4"):
            for token in TIERS[tier]:
                for name in ("light", "dark"):
                    rgb = self.theme(name)[token]
                    chroma = max(rgb) - min(rgb)
                    self.assertLessEqual(
                        chroma, 30,
                        f"{name} {token}={rgb} 채도 {chroma} — 장비가 서비스 색을 지고 있다")


class ExteriorLightingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = MINIAPP.read_text(encoding="utf-8")

    def test_scene_has_an_environment_map(self):
        """환경맵이 없으면 금속이 죽은 회색 확산광으로 그려진다.

        대입문이 *살아 있는지* 를 본다 — 주석 처리된 줄도 부분문자열로는 걸리므로
        줄머리에 `//` 가 없다는 것까지 확인해야 한다.
        """
        self.assertRegex(
            self.html, r"(?m)^[ \t]*scene\.environment = studioEnvironment\(\);",
            "환경맵이 씬에 연결돼 있지 않다(주석 처리 포함)")
        self.assertRegex(
            self.html, r"(?m)^[ \t]*scene\.environmentIntensity = [\d.]+;",
            "환경맵 세기가 설정돼 있지 않다")
        self.assertIn("PMREMGenerator", self.html)
        self.assertIn("EquirectangularReflectionMapping", self.html)

    def test_the_environment_is_generated_not_fetched(self):
        """외부 파일을 받아 오면 오프라인 동작이 깨진다 — three·cannon 내장과 같은 이유다."""
        body = self.html[self.html.index("function studioEnvironment("):]
        body = body[:body.index("\n    scene.environment")]
        self.assertIn("document.createElement(\"canvas\")", body)
        for forbidden in ("fetch(", "TextureLoader", "http://", "https://", ".hdr", ".exr"):
            self.assertNotIn(forbidden, body,
                             f"환경맵이 외부 자원({forbidden})을 쓴다")

    def test_direct_lights_were_rebalanced_for_ibl(self):
        """IBL 이 확산광을 지므로 종전 세기를 그대로 두면 전부 날아간다."""
        hemisphere = re.search(r"HemisphereLight\(0xffffff, 0x[0-9a-f]+, ([\d.]+)\)", self.html)
        self.assertIsNotNone(hemisphere, "반구광을 찾지 못했다")
        self.assertLess(float(hemisphere.group(1)), 0.6,
                        "반구광이 IBL 이전 세기 그대로다 — 환경맵과 이중으로 밝힌다")
        key = re.search(r"DirectionalLight\(0xffffff, ([\d.]+)\);\s*\n\s*keyLight\.position", self.html)
        self.assertIsNotNone(key, "키라이트를 찾지 못했다")
        self.assertLess(float(key.group(1)), 2.0, "키라이트가 IBL 이전 세기 그대로다")

    def test_finishes_come_from_the_shared_tier_table(self):
        """마감이 부품마다 눈대중이면 같은 티어인데 거칠기가 달라진다."""
        self.assertIn("const FINISH = {", self.html)
        for tier in ("trim", "body", "drive", "control"):
            self.assertRegex(self.html, tier + r":\s*\[[\d.]+, [\d.]+\]",
                             f"FINISH 표에 {tier} 가 없다")
        self.assertGreaterEqual(self.html.count("finish(color."), 18,
                                "장비 재질이 FINISH 표를 거치지 않는다")

    def test_the_floor_falls_away_from_the_plant(self):
        """균일한 바닥은 지평선까지 같은 밝기로 뻗어 설비와 시선을 나눠 갖는다."""
        self.assertIn("createRadialGradient", self.html)
        self.assertIn("map: floorTexture", self.html)


class ExteriorLegendTest(unittest.TestCase):
    """범례가 실제 화면과 같은 것을 말하는지 — 없는 구분을 주장하면 안 된다."""

    @classmethod
    def setUpClass(cls):
        cls.html = MINIAPP.read_text(encoding="utf-8")

    def test_equipment_legend_states_the_four_tiers(self):
        for tier in ("tier-trim", "tier-body", "tier-drive", "tier-control"):
            self.assertEqual(self.html.count('hsg3d-family-swatch ' + tier), 1,
                             f"범례에 {tier} 행이 없다")
            self.assertIn(".hsg3d-family-swatch." + tier + " {", self.html)

    def test_the_retired_per_family_swatches_are_gone(self):
        """계열별 스와치가 남아 있으면 화면에 없는 구분을 범례가 주장한다."""
        for retired in ("dry-unit", "receiver-unit", "motor-unit",
                        "air-unit", "reagent-unit", "water-unit"):
            self.assertNotIn('hsg3d-family-swatch ' + retired, self.html,
                             f"폐지된 범례 항목 {retired} 이 남아 있다")

    def test_pipe_legend_survives(self):
        """배관은 여전히 서비스 색을 진다 — 그쪽 범례까지 지우면 안 된다."""
        for kept in ("dry", "return", "slurry", "water", "air",
                     "ceramic", "reagent", "concentrate", "tailings", "bead"):
            self.assertIn('hsg3d-family-swatch ' + kept + '"', self.html,
                          f"배관 범례 {kept} 가 사라졌다")


if __name__ == "__main__":
    unittest.main()
