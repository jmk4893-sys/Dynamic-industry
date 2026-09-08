"""패널 **구조** 레시피 — 반입 등록에서 오는 구조 플래그와 그에 따른 자동 가공 허가.

REV.51 에서 들어왔다. 계기는 발주처가 검토를 청한 외부 R3 안이 "단면발전이라는
기능과 유리 한 장/두 장이라는 구조는 다르다" 고 갈라 둔 것이다 — 맞는 말이고,
우리 모델은 그때까지 유리·백시트·프레임형 하나를 전제하고 있었다.

원칙은 셋이다.

* 구조는 **비전이 확정하지 않는다.** VS-101 은 외관·파손·유리면 방향을 보지,
  이중유리인지 무프레임인지 화학 조성이 무엇인지는 못 본다. 구조는 반입 등록
  (패널 ID·제조사 자료·반입 서류)에서 오고, 미등록이면 마지막 정상 레시피를
  자동 적용하지 않는다 — **HOLD** 다.
* 허가는 구조마다 다르다. 무프레임은 AFR 인발을 **생략**하고(클램프·정반은
  통과), 단면 이중유리는 상면이 유리라 JBR 헤드·SG 국부의 백시트용 접촉 조건을
  재사용하지 않는다.
* 양면발전형은 사용자 제외 범위다 — 자동 가공 대상이 아니라 **범위 외 리젝트**
  로 빠진다. 전손과 같은 물리 경로(RB-101 → AFU-RJ-101 리젝트 랙)를 쓴다.

3D 영상에서는 이 판정이 JBR 허가(`Pr` 검사표의 `structure_recipe_ok`)에 걸린다 —
미승인 구조는 절단 전에 막히고 화면은 선행 리젝트 경로를 보여 준다. 실제 라인은
등록 시점(투입 전)에 걸러야 하고, 그 자리는 `enforced_at` 에 적는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import hk60c, line


@dataclass(frozen=True)
class Structure:
    """패널 구조 하나와 그 구조의 자동 가공 조건."""

    code: str           # 등록 코드
    ui: str             # 도면 <select> 값
    label: str
    framed: bool        # 알루미늄 프레임이 있는가
    top: str            # 위를 향하는 면(기본 자세 유리 ↓)의 기재 — '백시트' | '유리' | '미확인'
    auto: bool          # 자동 가공 허가
    route: str          # 'PROCESS' | 'PROCESS_NO_AFR' | 'REJECT_OUT_OF_SCOPE' | 'HOLD_UNREGISTERED'
    afr: str            # AFR-101 에서 하는 일
    sg: str             # SG-301 접촉 조건
    action: str         # 허가가 없을 때 무엇을 하는가
    note: str


STRUCTURES: tuple[Structure, ...] = (
    Structure("GLASS_BACKSHEET", "glass-backsheet", "유리·백시트·프레임형 (기본)", True, "백시트",
              True, "PROCESS", "단축 밀기 → 장축 인발",
              "장변·단변 엣지 연마 · 백시트 접촉 압력 기본값", "—",
              "검증한 기본 레시피. JBR → AFR → SG-301 → GI-301/302/303 → GBR-301"),
    Structure("GLASS_GLASS_MONO", "glass-glass-mono", "단면발전 이중유리·프레임형", True, "유리",
              True, "PROCESS", "단축 밀기 → 장축 인발 (프레임 단면 등록값 확인)",
              "상면이 유리 — 백시트용 접촉 압력 재사용 금지 · 유리 접촉 조건 별도 승인",
              "접촉 조건 미승인이면 HOLD",
              "양면발전과 다르다. 발전면은 하나인데 유리가 두 장이라 상면 기재가 다르다"),
    Structure("FRAMELESS", "frameless", "무프레임 (단면·유리·백시트)", False, "백시트",
              True, "PROCESS_NO_AFR", "클램프·정반 통과 — 인발 생략 (프레임 부재를 고장으로 치환하지 않는다)",
              "엣지 연마 — 실란트 대신 라미네이트 가장자리 정리, 접촉압 하한",
              "프레임 존재 센서가 프레임을 보면 등록 불일치 → HOLD",
              "AFR 이 프레임 없음을 정상으로 받는 유일한 레시피 (도면 리터럴은 작은따옴표로 싸므로 문자열 안에 작은따옴표를 쓰지 않는다)"),
    Structure("BIFACIAL", "bifacial", "양면발전형", True, "유리",
              False, "REJECT_OUT_OF_SCOPE", "—", "—",
              "범위 외 리젝트 — RB-101 이 리젝트 랙(AFU-RJ-101)에 놓는다 (전손과 같은 경로)",
              "사용자 제외 범위. 뒷면도 발전면이라 차광·전기 확인 조건이 다르다"),
    Structure("UNREGISTERED", "unregistered", "미등록·구조 미확인", True, "미확인",
              False, "HOLD_UNREGISTERED", "—", "—",
              "투입 보류 — 마지막 정상 레시피를 자동 적용하지 않는다. 등록 후 재투입",
              "외관만으로 구조를 확정하지 않는다 — 비전은 등록값을 검증하는 수단이다"),
)

#: 미승인 구조가 실제로 걸리는 자리와 영상이 보여 주는 자리.
ENFORCED_AT = {
    "plant": "반입 등록 (패널 ID·서류) — 투입 전",
    "drawing": "JBR 허가 검사표 `structure_recipe_ok` — 절단 전 선행 리젝트 경로",
}

DEFAULT = "GLASS_BACKSHEET"

# ── 치수 게이트 (REV.54) ──────────────────────────────────────────────────
# 라인 상한을 후단 DG-HK60C 의 2,400 × 1,200 으로 통일하면서 "받을 수 있는데
# 안 받기로 한 패널" 이 생겼다 — 210 mm 셀 66셀 모듈(2,384 × 1,303)과 182 mm 78셀
# (2,465 × 1,134)이 그것이다. 그 패널은 라인에 들어오기 **전**에 걸러야 한다.
# 구조와 같은 규칙이다: 치수는 반입 등록(제조사 자료)에서 오고, 투입 비전
# VS-101 의 외형 계측이 등록값을 검증한다. 초과·미달은 양면발전형과 같은
# 범위 외 리젝트 경로(RB-101 → AFU-RJ-101)로 빠진다 — HOLD 가 아니다. 다시
# 등록해도 들어갈 수 없기 때문이다.

#: 자동 가공 치수 범위 (mm) — 후단이 갖는 값을 읽는다.
SIZE_MAX_MM: tuple[int, int] = line.LINE_MAX_MM
SIZE_MIN_MM: tuple[int, int] = hk60c.PANEL_MIN_MM

#: 치수 게이트가 걸리는 자리와 검증 수단.
SIZE_GATE = {
    "enforced_at": "반입 등록 (제조사 치수) — 투입 전",
    "verified_by": "VS-101A/B 외형 계측 — 등록값과 ±10 mm 안이어야 투입 허가",
    "route": "REJECT_OUT_OF_SCOPE",
}


def size_route(length_mm: float, width_mm: float) -> str:
    """치수만으로 정하는 경로. 범위 안이면 구조 레시피가 이어받는다."""
    inside = (SIZE_MIN_MM[0] <= length_mm <= SIZE_MAX_MM[0]
              and SIZE_MIN_MM[1] <= width_mm <= SIZE_MAX_MM[1])
    return "PROCESS" if inside else SIZE_GATE["route"]


def route(code: str, length_mm: float, width_mm: float) -> str:
    """구조 + 치수를 함께 본 경로. 치수가 먼저다 — 범위 밖은 구조를 볼 이유가 없다."""
    if size_route(length_mm, width_mm) != "PROCESS":
        return SIZE_GATE["route"]
    return by_code(code).route


#: 게이트가 걸러 내는 대표 모듈 — 왜 상한 통일이 시장 결정인지를 값으로 남긴다.
EXCLUDED_MODULES_MM: tuple[tuple[str, int, int], ...] = (
    ("210 mm 셀 66셀 (2021~)", 2384, 1303),
    ("182 mm 셀 78셀", 2465, 1134),
)


def by_code(code: str) -> Structure:
    return next(s for s in STRUCTURES if s.code == code)


def by_ui(value: str) -> Structure:
    """도면 <select> 값 → 구조. 모르는 값은 미등록으로 본다 — 기본값으로 떨어지지 않는다."""
    return next((s for s in STRUCTURES if s.ui == value), by_code("UNREGISTERED"))


def auto_codes() -> tuple[str, ...]:
    return tuple(s.code for s in STRUCTURES if s.auto)


def permits(code: str) -> dict[str, bool]:
    """구조별 스테이션 허가. 허가가 없으면 그 스테이션은 그 패널을 잡지 않는다."""
    s = by_code(code)
    return {
        "jbr": s.auto,
        "afr_pull": s.auto and s.framed,
        "afr_pass": s.auto,
        "sg": s.auto,
        "gi": s.auto,
    }


def every_unregistered_holds() -> bool:
    """미등록은 언제나 HOLD 다 — 기본 레시피로 떨어지는 길이 없어야 한다."""
    return (by_code("UNREGISTERED").route == "HOLD_UNREGISTERED"
            and not by_code("UNREGISTERED").auto
            and by_ui("").code == "UNREGISTERED")


def literal_rows() -> list[list[object]]:
    """도면 `STRUCTURE_RECIPES` 리터럴 행 — build_literals 가 찍는다."""
    return [[s.code, s.ui, s.label, s.framed, s.top, s.auto, s.route, s.afr, s.sg, s.action, s.note]
            for s in STRUCTURES]
