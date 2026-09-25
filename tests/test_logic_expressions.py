"""논리식 표기를 강제한다.

콘솔은 REV.05 부터 REV.20 까지의 개정을 unshift/splice/filter/map 으로 쌓아
올린 자리였다. 화면은 마지막 상태만 그리므로 중간 개정에서 폐기된 항이
소스에만 남았고, 같은 이름이 서로 다른 항으로 두 번 세 번 정의돼 있었다
(2라인 시절의 LANE_X_START·DISPATCH_A/B·RELEASE_X 가 대표적이다). 읽는
사람은 어느 쪽이 유효한지 소스만 봐서는 알 수 없다.

더 조용한 쪽은 이름이다. 논리식의 좌변이 tools/plc_model.py 가 계산하는
신호가 아니면 그 허가는 화면상 멀쩡히 보이면서 아무것도 걸지 않는다. 실제로
백시트 끝단 비전은 폐기된 REV.05 문장에만 이름이 남아 있어서 장치 대조를
통과하고 있었다 — HKS_Z_PERMIT 과 HKS_PERMIT 이 그것을 읽는데 현장에는
아무것도 서 있지 않았다.

그래서 네 가지를 시험으로 고정한다.

  1. 한 이름은 한 문서에서 한 번만 정의한다.
  2. 두 문서에 같은 이름이 나오면 항까지 같다.
  3. 좌변과 (화살표 왼쪽의) 순수 신호 항은 실행 모델에 있는 이름이다.
  4. 출력은 항으로 읽지 않는다 — HORN_3S·BEACON_AMBER 는 F-DO 다.
"""

import importlib.util
import json
import pathlib
import re
import unittest

from . import _path  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"

# 콘솔 브랜치에는 사양서가 없다. 없는 파일을 읽어 실패하는 대신 건너뛴다.
DOCS = [p for p in (CONSOLE, RFQ) if p.exists()]

# 2라인(A/B 병렬 셀) 시절에만 쓰던 이름. Rev.15 에서 단일 셀로 돌아왔으므로
# 어디에도 남아 있으면 안 된다.
TWO_LANE = [
    "LANE_X_START", "IR_STANDBY_X", "DOOR_MUTEX_X", "RELEASE_X",
    "LANE_FAILOVER", "ACK_SELECTED_LANE", "DISPATCH_A/B", "TRIP_A", "TRIP_B",
    "CENTRAL_INFEED_CLEAR", "TANDEM_X_READY", "OUT_AIRLOCK_X_EMPTY",
]

# 논리식으로 읽지 않는 출력. 적층 신호등·부저를 구동하는 F-DO 다.
OUTPUTS = ["HORN_3S", "BEACON_AMBER"]

BARE = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
DEFN = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9_]{2,})\s*=\s*(.+)")
# 정의를 '세는' 쪽은 우변을 삼키면 안 된다 — DEFN 의 (.+) 는 줄 끝까지
# 먹으므로 한 줄에 둘이 있어도 하나로 세어진다.
LHS = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9_]{2,}\s*=(?![=>])")


def _model_signals():
    spec = importlib.util.spec_from_file_location("plc_model", ROOT / "tools" / "plc_model.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return {leaf.name for leaf in m.LEAVES} | {d.name for d in m.DERIVED}


STRING = re.compile(r"'((?:[^'\\\\\n]|\\\\.)*)'|\"((?:[^\"\\\\\n]|\\\\.)*)\"|`([^`]*)`")


def _text(path):
    """사람이 읽는 줄만 남긴다.

    콘솔은 스크립트가 본문이라 태그만 걷으면 자바스크립트 코드까지 딸려
    온다. 코드의 대입문(MAT_DEFAULT = ...)은 논리식이 아니므로, 스크립트
    안에서는 따옴표 안의 문자열만 — 즉 화면에 나가는 글만 — 본다."""
    raw = path.read_text(encoding="utf-8")
    lines = []
    for i, chunk in enumerate(re.split(r"<script[^>]*>|</script>", raw, flags=re.I)):
        if i % 2:                                   # <script> 안쪽
            for m in STRING.finditer(chunk):
                lit = next(g for g in m.groups() if g is not None)
                lines.append(lit.replace("\\'", "'").strip())
        else:
            lines += [ln.strip() for ln in re.sub(r"<[^>]+>", "\n", chunk).split("\n")]
    return lines


def _definitions(path):
    """(이름, 항) 목록. 항은 공백을 지워 비교한다 — 사양서는 연산자 둘레에
    공백을 넣고 콘솔은 붙여 쓰지만 같은 식이다."""
    out = []
    for ln in _text(path):
        for m in DEFN.finditer(ln):
            out.append((m.group(1), re.sub(r"\s+", "", m.group(2)).rstrip(",'\"")))
    return out


def _terms(expr):
    """항 중에서 '순수 신호명'만 골라낸다.

    ' → ' 오른쪽은 결과·명령이지 읽는 신호가 아니므로 잘라낸다(X_DECEL,
    ST_TOWER_CMD 따위). 남은 것을 ∧ ∨ 로 쪼개고, 단위·괄호·한글이 섞이지
    않은 순수 대문자 토큰만 신호로 본다."""
    left = expr.split("→")[0]
    for part in re.split(r"[∧∨]", left):
        part = part.strip().strip("¬()").strip()
        if BARE.match(part):
            yield part


class TestOneDefinitionPerName(unittest.TestCase):
    def test_console_defines_each_name_once(self):
        seen = {}
        for name, expr in _definitions(CONSOLE):
            self.assertNotIn(
                name, seen,
                f"콘솔이 {name} 을 두 번 정의한다:\n  {seen.get(name)}\n  {expr}\n"
                "개정 이력을 남겨 두면 폐기된 항이 유효한 항처럼 읽힌다.")
            seen[name] = expr
        self.assertGreater(len(seen), 25, "콘솔에서 논리식을 찾지 못했다")

    def test_rfq_defines_each_name_once(self):
        if not RFQ.exists():
            self.skipTest("이 브랜치에는 사양서가 없다")
        seen = {}
        for name, expr in _definitions(RFQ):
            self.assertNotIn(name, seen, f"사양서가 {name} 을 두 번 정의한다")
            seen[name] = expr
        self.assertGreater(len(seen), 8, "사양서에서 논리식을 찾지 못했다")

    def test_console_and_rfq_agree(self):
        if not RFQ.exists():
            self.skipTest("이 브랜치에는 사양서가 없다")
        con = dict(_definitions(CONSOLE))
        rfq = dict(_definitions(RFQ))
        shared = sorted(set(con) & set(rfq))
        self.assertGreaterEqual(len(shared), 8, "두 문서가 공유하는 논리식이 너무 적다")
        for name in shared:
            self.assertEqual(
                con[name], rfq[name],
                f"{name} 의 항이 콘솔과 사양서에서 다르다:\n"
                f"  콘솔  {con[name]}\n  사양서 {rfq[name]}")


class TestNamesAreModelSignals(unittest.TestCase):
    """논리식의 이름이 실행 모델에 없으면 그 허가는 아무것도 걸지 않는다."""

    def setUp(self):
        self.known = _model_signals()

    def test_left_hand_sides_exist_in_model(self):
        for path in DOCS:
            for name, _ in _definitions(path):
                self.assertIn(
                    name, self.known,
                    f"{path.name} 의 {name} 은 tools/plc_model.py 에 없다. "
                    "모델에 없는 좌변은 화면에만 보이는 허가다 — 모델에 넣든지, "
                    "논리식이 아니면 '=' 을 쓰지 말아야 한다.")

    def test_referenced_terms_exist_in_model(self):
        for path in DOCS:
            for name, expr in _definitions(path):
                for term in _terms(expr):
                    self.assertIn(
                        term, self.known,
                        f"{path.name} 의 {name} 이 모델에 없는 {term} 을 읽는다")


class TestNoSupersededRemnants(unittest.TestCase):
    def test_two_lane_names_are_gone(self):
        """화면에 나가는 글에서만 본다 — 왜 접었는지 적어 둔 주석은 남겨야 한다."""
        for path in DOCS:
            for ln in _text(path):
                for name in TWO_LANE:
                    if name in ln:
                        self.fail(f"{path.name} 에 2라인 시절 이름 {name} 이 "
                                  f"살아 있는 글로 남아 있다: {ln[:120]}")

    def test_outputs_are_not_read_as_terms(self):
        for path in DOCS:
            for name, expr in _definitions(path):
                left = re.split(r"→", expr)[0]
                for out in OUTPUTS:
                    self.assertNotIn(
                        out, left,
                        f"{path.name} 의 {name} 이 F-DO 출력 {out} 을 항으로 읽는다")

    def test_no_line_carries_two_definitions(self):
        for path in DOCS:
            for ln in _text(path):
                if len(LHS.findall(ln)) > 1:
                    self.fail(f"{path.name} 의 한 줄에 정의가 둘이다: {ln[:120]}")

    def test_revision_trail_is_collapsed(self):
        """개정 이력을 배열 조작으로 쌓아 올리면 폐기된 항이 소스에 남는다."""
        body = CONSOLE.read_text(encoding="utf-8")
        for op in ("unshift", "splice"):
            self.assertNotIn(
                f"details.equipment.{op}", body, f"details 에 {op} 이력이 남아 있다")
        for key in ("equipment", "spec", "interlock", "support"):
            for op in ("unshift", "splice", "filter", "map"):
                for sec in ("hardware", "control", "verify"):
                    self.assertNotIn(
                        f"details.{key}.{sec}.{op}(", body,
                        f"details.{key}.{sec} 에 {op} 이력이 남아 있다")
        self.assertEqual(
            body.count("const details={"), 1, "details 는 한 번만 정의한다")
        self.assertEqual(
            len(re.findall(r"details\.(?:equipment|spec|interlock|support)\s*=", body)), 0,
            "details 의 절을 나중에 통째로 갈아치우면 앞의 정의가 죽은 채 남는다")


if __name__ == "__main__":
    unittest.main()
