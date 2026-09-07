"""테스트에서 src·tools 를 import 경로에 추가."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for d in (ROOT / "src", ROOT / "tools"):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
