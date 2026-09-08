"""단수를 올릴 때 따라오지 않으면 조용히 깨지는 높이들.

가열 랙과 냉각 랙은 단수만큼 높아진다. 그런데 그 위에 서 있는 것들 —
외장 갓돌, 배기 헤더, RH-201 모노레일 — 은 오랫동안 값으로 박혀 있었다.
3단에서는 우연히 다 들어맞았으므로 아무 표시도 나지 않았고, 5단으로
올리자 세 곳이 한꺼번에 어긋났다:

  · 랙 지붕 4,725 가 갓돌 3,680 위로 나와 몸체가 깨졌다
  · 배기 헤더 4,700 이 지붕 아래로 들어가 챔버 분기가 공중에 떴다
  · EX-101 포크 두상보가 모노레일 트롤리를 150 mm 관통했다 —
    만권롤 357 kg 과 200 °C 카세트가 방책 밖으로 나가는 유일한 길이다

그래서 여기서는 두 가지를 함께 본다. 유도식이 소스에 그대로 있는가(형태),
그리고 그 식을 풀었을 때 여유가 실제로 남는가(값). 형태만 보면 식 안에
0을 곱해 놓아도 통과하고, 값만 보면 값을 베껴 적어 두어도 통과한다.
"""

import math
import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"


def _const(src, name):
    """`const A=1,B=2;` 처럼 한 줄에 여럿 선언된 것도 읽는다."""
    m = re.search(rf"\b{name}=([-\d.]+)", src)
    assert m, f"콘솔에 {name} 상수가 없다"
    return float(m.group(1))


class TestTheHeightsAboveTheRackFollowTheDeckCount(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.src = CONSOLE.read_text(encoding="utf-8")
        cls.z0 = _const(cls.src, "CDECK_Z0")
        cls.dz = _const(cls.src, "CDECK_DZ")
        cls.skin = _const(cls.src, "SKIN_TOP")
        cls.cope = _const(cls.src, "COPE_H")
        cls.crown_clr = _const(cls.src, "CROWN_CLR")
        cls.rh_clr = _const(cls.src, "RH_CLR")
        cls.decks = int(re.search(r"const DECKS=(\d+)", cls.src).group(1))
        m = re.search(r"decks:(\d+),lamps:(\d+)", cls.src.replace(" ", ""))
        cls.twin_decks = int(m.group(1)) if m else 7

    # ── 유도식이 소스에 있는가 ───────────────────────────────────────
    def test_every_height_is_derived_not_written(self):
        for pattern, why in (
            # 유도는 단수의 함수여야 한다 — 기초도면(D-602)이 납품 배치 단수로
            # 같은 식을 다시 풀기 때문이다. LC() 안에 갇혀 있으면 도면이
            # 화면에 켜 둔 배치를 따라가고, 그것은 도면이 아니라 화면이다.
            (r"function crownTopOf\(decks\)\{\s*"
             r"const top=cDeckZ\(decks-1\)\+\.86\+\.175\+CROWN_CLR;",
             "크라운이 랙 지붕에서 나오지 않는다"),
            (r"const cCrownTop=\(\)=>crownTopOf\(LC\(\)\.decks\);",
             "활성 배치의 크라운이 그 식을 쓰지 않는다"),
            (r"const ductZOf=decks=>Math\.max\(4\.70,"
             r"Math\.ceil\(\(crownTopOf\(decks\)\+COPE_H\+\.20\)\*20\)/20\);",
             "배기 헤더가 갓돌에서 나오지 않는다"),
            (r"const cDuctZ=\(\)=>ductZOf\(LC\(\)\.decks\);",
             "활성 배치의 배기 헤더가 그 식을 쓰지 않는다"),
            (r"const rhMinZ=decks=>cDeckZ\(decks-1\)\+\.73\+\.09\+\.15\+\.34\+RH_CLR;",
             "모노레일 하한이 포크 두상보에서 나오지 않는다"),
            (r"const RH_Z=Math\.max\(4\.85,Math\.ceil\(rhMinZ\(DECKS\)\*20\)/20\);",
             "모노레일 높이가 그 하한을 받지 않는다"),
        ):
            self.assertRegex(re.sub(r"\s+", " ", self.src), pattern, why)
        self.assertNotIn("const CDUCT_Z=", self.src, "배기 헤더가 아직 값이다")
        self.assertNotIn("const RH_Z=4.85,", self.src, "모노레일이 아직 값이다")

    # ── 그 식을 풀면 여유가 남는가 ───────────────────────────────────
    def _heights(self, decks):
        top_deck = self.z0 + self.dz * (decks - 1 + 0.5)
        rack_roof = top_deck + 0.86 + 0.175
        crown = max(self.skin, math.ceil((rack_roof + self.crown_clr) * 20) / 20)
        duct = max(4.70, math.ceil((crown + self.cope + 0.20) * 20) / 20)
        fork_top = top_deck + 0.73 + 0.09
        rh_min = fork_top + 0.15 + 0.34 + self.rh_clr
        rh = max(4.85, math.ceil(rh_min * 20) / 20)
        return dict(rack_roof=rack_roof, crown=crown, duct=duct,
                    fork_top=fork_top, rh=rh, trolley_bottom=rh - 0.49)

    def test_the_crown_closes_over_the_rack(self):
        """랙 지붕이 갓돌 위로 나오면 기계가 한 몸으로 읽히지 않는다."""
        for decks in (self.decks, self.twin_decks):
            h = self._heights(decks)
            self.assertGreaterEqual(
                h["crown"], h["rack_roof"],
                f"{decks}단에서 크라운 {h['crown']*1000:.0f} 이 "
                f"랙 지붕 {h['rack_roof']*1000:.0f} 을 덮지 못한다")

    def test_the_exhaust_header_stays_above_the_coping(self):
        """헤더가 지붕 아래로 들어가면 챔버 분기가 공중에 뜬다 — 화면에는 표시가 없다."""
        for decks in (self.decks, self.twin_decks):
            h = self._heights(decks)
            self.assertGreaterEqual(
                h["duct"], h["crown"] + self.cope + 0.10,
                f"{decks}단에서 배기 헤더 {h['duct']*1000:.0f} 이 "
                f"갓돌 {(h['crown']+self.cope)*1000:.0f} 위에 서지 못한다")

    def test_the_monorail_clears_the_discharge_fork_portal(self):
        """막히면 357 kg 만권롤과 200 °C 카세트가 방책을 넘을 길이 없다."""
        for decks in (self.decks, self.twin_decks):
            h = self._heights(decks)
            gap = h["trolley_bottom"] - h["fork_top"]
            self.assertGreaterEqual(
                gap, self.rh_clr - 1e-9,
                f"{decks}단에서 호이스트 트롤리 하단 {h['trolley_bottom']*1000:.0f} 과 "
                f"EX-101 두상보 상단 {h['fork_top']*1000:.0f} 사이가 "
                f"{gap*1000:.0f} mm 뿐이다")

    def test_raising_the_deck_count_actually_moves_them(self):
        """단수를 올렸는데 값이 그대로면 그 상수는 파생되고 있지 않다."""
        low, high = self._heights(3), self._heights(self.decks)
        self.assertGreater(high["rack_roof"], low["rack_roof"])
        for k in ("crown", "duct", "rh"):
            self.assertGreater(
                high[k], low[k],
                f"단수를 3 → {self.decks} 로 올렸는데 {k} 가 따라오지 않는다")


if __name__ == "__main__":
    unittest.main()
