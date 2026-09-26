"""후단 도면집 — 네 벌을 **합치지 않고** 한 장에 담았는가.

담는 화면은 파이썬 시험이 못 보는 실패 방식이 있어(액자가 나란히 늘어서는 것)
`tools/check_afr_hub.mjs` 가 브라우저에서 따로 본다. 여기서 붙드는 것은 넷이다.

  ① 담은 것이 그 도면 파일 **바이트 그대로**이고 한 벌씩인가
  ② 액자가 도면 마크업을 풀어 붙이지 않았는가
  ③ 탭 글과 점유 초가 **모델·도면**에서 왔는가 (손으로 쓴 수가 없는가)
  ④ 띠가 구간이 아니라 점유인가 — 없는 오프셋을 지어내지 않았는가
"""

from __future__ import annotations

import base64
import importlib.util
import pathlib
import re
import unittest

from tests import _path  # noqa: F401

from pv_preprocess import campaign, gi_optics, sg_grind

ROOT = pathlib.Path(__file__).resolve().parents[1]
HUB = ROOT / "docs/drawings/pv-afr-hub.html"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAfrHub(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.builder = _load("build_afr_hub")
        cls.html = HUB.read_text(encoding="utf-8")
        # base64 로 실린 도면 본문을 걷어 낸 「액자만」의 마크업.
        cls.frame = re.sub(r'<script type="text/plain" id="doc-[a-z]+">[^<]*</script>',
                           "", cls.html)

    def test_the_committed_file_is_what_the_builder_makes(self):
        self.assertEqual(self.html, self.builder.build(),
                         "docs/drawings/pv-afr-hub.html 이 생성기 출력과 다르다 — "
                         "PYTHONPATH=src python tools/build_afr_hub.py 를 돌리고 커밋한다")

    def test_each_sheet_is_carried_once_and_byte_exact(self):
        """담은 것이 그 도면 파일 그대로여야 한다 — 한 벌씩, 바이트 하나까지."""
        for key, rel, _role, _label in self.builder.SHEETS:
            with self.subTest(sheet=key):
                marker = f'<script type="text/plain" id="doc-{key}">'
                self.assertEqual(self.html.count(marker), 1, "같은 도면이 두 번 실렸다")
                b64 = re.search(re.escape(marker) + r"([^<]*)</script>", self.html).group(1)
                self.assertEqual(base64.b64decode(b64), (ROOT / rel).read_bytes())

    def test_it_carries_the_four_downstream_sheets(self):
        self.assertEqual([k for k, _r, _o, _l in self.builder.SHEETS],
                         ["scene", "closeup", "grind", "inspect"])
        for _key, rel, _role, _label in self.builder.SHEETS:
            with self.subTest(rel):
                self.assertTrue((ROOT / rel).exists())

    def test_the_frame_does_not_paste_sheet_markup(self):
        """도면을 풀어서 붙이면 서식이 섞이고 같은 표가 두 번 나온다."""
        for tag in ("<table", "<canvas", "<svg", "<h2"):
            with self.subTest(tag=tag):
                self.assertNotIn(tag, self.frame)

    def test_the_tab_labels_come_from_the_sheets_themselves(self):
        for _key, rel, _role, _label in self.builder.SHEETS:
            title, desc = self.builder.sheet_meta(ROOT / rel)
            with self.subTest(rel):
                self.assertIn(title, self.frame)
                self.assertIn(desc, self.frame)

    def test_the_clock_band_comes_from_the_campaign_model(self):
        infeed, jbr, afr = campaign.INFEED_S, campaign.JBR_S, campaign.AFR_S
        n = self.builder.num
        for w in (infeed, jbr, afr):
            self.assertIn(f'style="flex:{w:g}"', self.frame)
        # 이 도면집이 다루는 것은 세 번째 칸이다 — 거기만 짚혀 있어야 한다.
        self.assertEqual(self.frame.count('class="seg here"'), 1)
        self.assertIn(f'class="seg here" style="flex:{afr:g}"', self.frame)
        self.assertIn(f"후단 점유 <b>{n(afr)} s</b>", self.frame)
        self.assertIn(f"종단 체류 <b>{n(campaign.total_dwell_s())} s</b>", self.frame)

    def test_the_occupancies_are_the_models_not_typed_in(self):
        """점유 초는 세 모듈이 정본을 쥔다 — 생성기가 새로 정하는 수가 없다."""
        want = {"scene": float(campaign.AFR_S), "closeup": float(campaign.AFR_S),
                "grind": sg_grind.occupancy_s(), "inspect": gi_optics.scan_time_s()}
        self.assertEqual(self.builder.scopes(), want)
        for key, secs in want.items():
            with self.subTest(key):
                self.assertIn(f'"secs":{secs:g}', self.html)

    def test_every_sheet_fits_inside_the_cell_occupancy(self):
        for key, secs in self.builder.scopes().items():
            with self.subTest(key):
                self.assertLessEqual(secs, campaign.AFR_S)

    def test_the_band_is_occupancy_not_an_invented_span(self):
        """모델은 길이만 주고 시작 시각은 안 준다 — 화면이 더 아는 척하면 안 된다.

        구간이라고 적으면 「95–120 s」 같은 수를 지어내야 하고, 그것은 이 저장소가
        막는 부류다. 그래서 막대는 칸 왼쪽에 붙고 라벨이 「… s / AFR … s」 다.
        """
        self.assertIn("점유", self.frame)
        self.assertIn("' s / AFR ' + AFR + ' s'", self.html)
        self.assertNotIn("meta.from", self.html)
        self.assertNotIn("meta.to", self.html)

    def test_the_frame_is_the_jbr_hub_frame(self):
        """액자를 두 벌로 두면 같은 라인의 도면집 둘이 다른 물건처럼 보인다.

        값이 같은지만 보면 복사해 붙여도 통과한다 — 그러면 한쪽만 고쳐도 시험이
        조용하다. 그래서 **가져다 쓰는지**를 원문에서 확인한다.
        """
        jbr = _load("build_jbr_hub")
        self.assertEqual(self.builder.CSS, jbr.CSS)
        src = (ROOT / "tools/build_afr_hub.py").read_text(encoding="utf-8")
        self.assertIn("from build_jbr_hub import CSS", src)
        self.assertNotIn("--brand-dim", src)          # CSS 를 제 것으로 안 갖는다
        self.assertNotIn("def sheet_meta", src)       # 헬퍼도 다시 안 쓴다
        self.assertNotIn("def payload", src)

    def test_a_sheet_without_its_own_description_fails_the_build(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8",
                                         delete=False) as fh:
            fh.write("<html><head><title>이름만 있다</title></head><body></body></html>")
            bare = pathlib.Path(fh.name)
        try:
            with self.assertRaises(SystemExit):
                self.builder.sheet_meta(bare)
        finally:
            bare.unlink()

    def test_the_artifact_converter_accepts_it(self):
        conv = _load("build_artifact")
        self.assertIn("afr-hub", conv.TARGETS)
        body = conv.convert(self.html, HUB)
        self.assertIn("<title>AFR-101 · SG-301 · GI 후단 도면집</title>", body)
        # 담은 도면은 base64 라 변환기의 골격 벗기기에 닿지 않는다.
        for key, _rel, _role, _label in self.builder.SHEETS:
            self.assertIn(f'id="doc-{key}"', body)

    def test_the_readme_and_render_check_list_the_sheet(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-afr-hub.html", readme)
        self.assertIn("tools/build_afr_hub.py", readme)
        check = (ROOT / "tools/check_afr_hub.mjs").read_text(encoding="utf-8")
        self.assertIn("docs/drawings/pv-afr-hub.html", check)
        for key, _rel, _role, _label in self.builder.SHEETS:
            self.assertIn(f"{key}:", check)


if __name__ == "__main__":
    unittest.main()
