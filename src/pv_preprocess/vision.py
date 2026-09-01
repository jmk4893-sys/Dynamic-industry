"""전처리 플랜트 비전 센서 구성 — 최소화 검토 결과.

최소화의 근거는 하나다. PT-101 이 3-2-1 정렬로 좌표시드를 만든 뒤에는 패널 위치가
이미 기계적으로 확정돼 있으므로, 하류 비전은 전면 재취득이 아니라 시드 주변 ROI
검증만 하면 된다.

검토 5건 중 2건(V-2·V-3)을 적용했다. 안전 관련 센서(라이트커튼·뮤팅·가드 인터록·
존재 검출)는 하나도 줄이지 않았다 — PLr·PFHd 재계산 없이 손댈 수 없는 채널이다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisionHead:
    """영상 헤드 하나. `kept` 가 False 면 최소화안에서 뺀 것."""

    tag: str
    cell: str
    role: str
    kept: bool
    note: str


#: 현행(REV.21) 영상 헤드 7대와 최소화안에서의 존치 여부.
HEADS: tuple[VisionHead, ...] = (
    VisionHead("VS-101A", "AFU-101", "칸 A 최상단 패널 상면·외곽·겹장 판정", True,
               "칸 A/B 가 동시에 계측되지 않지만, 공용 트래버스가 ±0.20 mm 를 유지하려면 "
               "정밀 스테이지가 필요해 카메라 1대값을 넘을 수 있다 (V-1 미적용)"),
    VisionHead("VS-101B", "AFU-101", "칸 B 최상단 패널 판정", True, "위와 같음"),
    VisionHead("VS-201A", "JBR-201", "정션박스 ROI 검증 · 박리 후 후검증", True,
               "X 브리지에 얹어 헤드 배치 이동과 촬영을 겹친다 (V-2). VS-301 의 후검증도 흡수 (V-3)"),
    VisionHead("VS-201B", "JBR-201", "중첩시야 보강", False,
               "PT-101 좌표시드가 있으면 전면 스캔이 불필요하다 — 브리지 탑재 1대가 ROI 를 순차 촬영 (V-2)"),
    VisionHead("VS-301", "JB/AFR 게이트", "박리 후 검증 · 공유맵 생성", False,
               "검증이 이미 JBR 45 s 창 안에서 직렬로 돌고 패널도 JBR 정반 위에 있다 — "
               "같은 자리에서 브리지 카메라가 재촬영 (V-3). 인계 롤러·데이터 게이트는 존치"),
    VisionHead("GI-301", "유리 후단", "연마 전 잔사 라인스캔 검사", True,
               "GI-302 와 통합하면 연마 전/후 비교가 사라진다 — 연마 공정창 고정 실증이 먼저 (V-4 보류)"),
    VisionHead("GI-302", "유리 후단", "연마 후 다크필드·레이저 레시피 판정", True, "위와 같음"),
)

#: 최소화안에서 부품표에서 빠지는 품번과 수량 변경.
RETIRED_PART_NUMBERS: tuple[str, ...] = ("JB-VS-004", "JB-VS-009")

#: 3D 장면에서 같이 내려야 하는 메시 라벨. 인계 롤러·데이터 게이트는 여기 없다.
RETIRED_MESH_LABELS: tuple[str, ...] = (
    "JBR-VS-201B 중첩시야 카메라",
    "JB/AFR-301 통합 2D＋3D 검증헤드",
    "JB/AFR-301 편광 2D 렌즈",
    "JB/AFR-301 3D 라인프로파일 발광부",
)

#: 감축 대상이 아닌 안전 채널. 줄이려면 SISTEMA 재계산과 위험성평가 재승인이 필요하다.
PROTECTED_SAFETY_PARTS: tuple[str, ...] = (
    "JB-SF-005",    # Type 4 라이트커튼
    "JB-SF-009",    # 안전 뮤팅 센서쌍
    "AFU-SE-101",   # 리프트 높이·기울기 (V-5 미적용)
    "AFR-SF-701",   # AFR·유리후단 가드·라이트커튼·안전PLC
)


def kept_heads() -> tuple[VisionHead, ...]:
    return tuple(head for head in HEADS if head.kept)


def retired_heads() -> tuple[VisionHead, ...]:
    return tuple(head for head in HEADS if not head.kept)


def head_reduction() -> tuple[int, int]:
    """(현행, 최소화안) 영상 헤드 수."""
    return len(HEADS), len(kept_heads())
