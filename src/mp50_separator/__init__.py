"""MP-50 폐태양광 블랙파우더 염수 밀도분리 파일럿 장치 — 제작 기준.

31~75 µm 의 EVA·백시트·실리콘은 입도가 겹치므로 체로 나눌 수 없다. MP-50 은
염수(NaCl 0~18 wt%)의 밀도를 세 재질의 유효밀도 사이에 놓고, 임펠러와 급기로
완전분산시킨 뒤 **둘을 동시에 정지**시켜 자연 부상/침강으로 분리한다. 공기와
임펠러는 분산 수단이지 분리 수단이 아니다.

이 패키지는 그 장치의 **제작 기준**을 코드로 고정한다. 수치해석(밀도컷·DOE·
몬테카를로)은 별도 브라우저 아티팩트가 담당하고, 여기서는 도면에 들어갈
치수·용적·공차와 "이 치수로 실제로 만들 수 있는가" 를 검증한다.

원본 3종(2026-09-10 연구문서 Rev.0, ChatGPT 도면 2매)의 치수가 서로 어긋나므로
``conflicts.py`` 에 충돌과 해결 근거를 남기고, 해결된 값만 ``geometry.py`` 에
싣는다. ``checks.py`` 는 그 값이 물리적으로 성립하는지 확인하며, 실패하면
테스트가 깨진다 — 도면이 조용히 틀리는 일을 막기 위해서다.

    from mp50_separator import GEOMETRY, run_checks
    GEOMETRY.total_volume_l        # 89.9
    [c for c in run_checks() if not c.ok]
"""

from __future__ import annotations

from .checks import CheckResult, run_checks
from .components import ASSEMBLIES, Assembly, Part, bill_of_materials
from .conflicts import CONFLICTS, Conflict
from .geometry import GEOMETRY, Geometry, Nozzle

__all__ = [
    "ASSEMBLIES",
    "CONFLICTS",
    "GEOMETRY",
    "Assembly",
    "CheckResult",
    "Conflict",
    "Geometry",
    "Nozzle",
    "Part",
    "bill_of_materials",
    "run_checks",
]
