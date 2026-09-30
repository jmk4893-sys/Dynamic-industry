"""발행처 대응표 — 같은 도면의 아티팩트가 두 벌 되지 않게.

`build_artifact` 의 독스트링은 처음부터 「고칠 때는 저장소 파일을 고치고 이것을
다시 돌린 뒤 **같은 URL 로 재발행**한다」고 적어 두었다. 그런데 그 URL 이 저장소
어디에도 없었다 — 코드·문서를 통틀어 `claude.ai/code/artifact` 문자열이 **0 건**
이었다. 그래서 다시 찍을 때마다 같은 도면의 아티팩트가 하나씩 더 생겼다.

실제로 JBR 여섯 종이 전부 두 벌이 됐다. 물리 시뮬레이션은 head 447269f 에서
한 번, head 3ee9f4a 에서 또 한 번 찍혔고 **둘 다 이 브랜치 커밋**이다 — 다른
브랜치와의 핑퐁이 아니라 우리가 우리 것을 두 벌 만든 것이다.

여기서 지키는 것은 대응표의 **성립 조건**이다. 살아 있는 발행 서비스에 묻지
않는다 — 시험은 망 없이 CI 에서 돌아야 한다.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _module():
    spec = importlib.util.spec_from_file_location("build_artifact", ROOT / "tools/build_artifact.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class TestArtifactRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ba = _module()

    def test_every_target_either_has_a_home_or_says_why_not(self):
        """빈칸을 「발행본이 없다」로 읽으면 또 하나가 생긴다 — 이유를 적게 한다."""
        for name in self.ba.TARGETS:
            with self.subTest(name):
                self.assertTrue(name in self.ba.PUBLISHED or name in self.ba.UNRECORDED,
                                f"{name}: PUBLISHED 에 넣거나 UNRECORDED 에 이유를 적는다")
                self.assertFalse(name in self.ba.PUBLISHED and name in self.ba.UNRECORDED,
                                 f"{name}: 양쪽에 다 있다")
        for name in list(self.ba.PUBLISHED) + list(self.ba.UNRECORDED):
            self.assertIn(name, self.ba.TARGETS, f"{name}: 발행 대상이 아니다")

    def test_the_uuids_are_well_formed_and_never_shared(self):
        """한 UUID 가 두 도면을 가리키면 다음 발행이 남의 것을 덮는다."""
        seen: dict[str, str] = {}
        rows = [(n, u) for n, u in self.ba.PUBLISHED.items()]
        rows += [(n, u) for n, us in self.ba.SUPERSEDED.items() for u in us]
        for name, uuid in rows:
            with self.subTest(f"{name} {uuid}"):
                self.assertRegex(uuid, UUID)
                self.assertNotIn(uuid, seen, f"{uuid}: {seen.get(uuid)} 와 겹친다")
                seen[uuid] = name

    def test_the_superseded_ones_are_kept_not_deleted(self):
        """지우면 다음에 목록에서 보고 같은 자리를 다시 밟는다."""
        for name in self.ba.SUPERSEDED:
            with self.subTest(name):
                self.assertIn(name, self.ba.PUBLISHED,
                              f"{name}: 정본이 없는데 중복만 적혀 있다")
        # 이 일이 실제로 일어났다는 사실 자체를 붙든다 — 다 지우면 교훈이 사라진다.
        self.assertGreaterEqual(len(self.ba.SUPERSEDED), 6,
                                "JBR 여섯 종이 두 벌이 된 기록이다 — 줄이려면 근거가 필요하다")

    def test_the_url_helper_matches_the_table(self):
        for name, uuid in self.ba.PUBLISHED.items():
            self.assertEqual(self.ba.artifact_url(name), self.ba.ARTIFACT_BASE + uuid)
        for name in self.ba.UNRECORDED:
            self.assertIsNone(self.ba.artifact_url(name))

    def test_the_converter_stamps_the_home_into_the_body(self):
        """발행본을 열면 어디 것인지 스스로 말해야 한다 — 그것이 두 벌을 막는다."""
        src = ROOT / "docs/drawings/pv-jbr-physics.html"
        url = self.ba.artifact_url("jbr-physics")
        out = self.ba.convert(src.read_text(encoding="utf-8"), src, url)
        self.assertIn(f"발행처: {url}", out)
        self.assertIn("위 발행처에** 재발행한다", out)
        # 발행처를 모르면 그 사실을 적어야지, 조용히 비우면 안 된다.
        blank = self.ba.convert(src.read_text(encoding="utf-8"), src, None)
        self.assertIn("아직 없다", blank)

    def test_the_repository_records_the_homes_somewhere(self):
        """이 시험이 존재하는 이유 — 한때 저장소 전체에 0 건이었다."""
        hits = 0
        for path in list(ROOT.glob("tools/*.py")) + [ROOT / "README.md"]:
            hits += len(re.findall(r"claude\.ai/code/artifact", path.read_text(encoding="utf-8")))
        self.assertGreater(hits, 0, "발행처가 저장소 어디에도 없다 — 다시 두 벌이 된다")

    def test_the_jbr_homes_match_what_the_pull_request_links(self):
        """PR 본문이 링크하는 것과 표가 갈라지면 어느 쪽이 정본인지 또 모르게 된다."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in ("jbr-hub", "jbr-scene", "jbr-detail", "jbr-closeup", "jbr-fab", "jbr-physics"):
            with self.subTest(name):
                self.assertIn(self.ba.PUBLISHED[name], readme,
                              f"{name}: README 의 발행처 표에 없다")


if __name__ == "__main__":
    unittest.main()
