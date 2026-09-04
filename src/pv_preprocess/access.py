"""고소 정비 접근 — EN ISO 14122 / 산업안전보건기준.

이 플랜트는 사람 키보다 높은 곳에 정비 대상을 여럿 두고 있다. VG-101 비전보
5,150, 갠트리 크로스헤드, IR 뱅크, 공압 주관 2,590, 크레인 주행레일 10,750.
그런데 **거기 어떻게 올라가는지가 도면에 없었다.** 사다리도 플랫폼도 난간도
부품표에 없고, 추락방지 고정점도 없다.

값으로 만들 것은 두 가지다.

* **높이가 접근 수단을 정한다** — 2 m 를 넘으면 추락 방호가 법적 요구이고,
  3 m 를 넘는 고정사다리는 등받이나 레일이 붙는다(EN ISO 14122-4).
* **그 수단을 세울 자리가 있는가** — 여기서 이 플랜트의 제약이 드러난다.
  통로 유효폭이 900 mm 다. 고정 플랫폼은 폭 600(제한 시 500)에 난간까지
  붙으므로, 세우는 순간 사람이 못 지나간다. §34 의 공압 주관이 통로에
  기둥을 못 세운 것과 같은 벽이다.

그래서 결론이 "이동식" 으로 간다. 다만 이동식이라고 아무것도 안 남는 것은
아니다 — **추락방지 고정점은 고정이어야 하고**, 그것은 건물 철골이나 장비
프레임에 붙는 인터페이스다. 크레인 주행레일처럼 우리가 값만 넘기는 것이 있고,
장비 프레임처럼 우리가 만들어야 하는 것이 있다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import air, crane, wiring

# ── 기준값 ───────────────────────────────────────────────────────────────
#: 추락 방호가 요구되는 높이 (mm). 산업안전보건기준 규칙과 EN ISO 14122 가
#: 같은 2 m 를 쓴다.
FALL_PROTECTION_MM = 2_000

#: 발판(스텝)으로 닿는 한계. 이 아래는 상시 수단이 필요 없다.
STEP_REACH_MM = 1_000

#: 이동식 작업대로 닿는 한계. 그 위는 고정 수단이나 고소작업대가 든다.
MOBILE_PLATFORM_MM = 4_000

#: 고정사다리에 등받이·레일이 붙는 높이 (EN ISO 14122-4).
LADDER_GUARD_MM = 3_000

#: 작업 플랫폼 최소 유효폭 (mm). 제한 조건에서 500 까지 줄일 수 있다.
PLATFORM_WIDTH_MM = 600
PLATFORM_WIDTH_RESTRICTED_MM = 500

#: 난간 높이 · 발끝막이 (EN ISO 14122-3).
GUARDRAIL_MM = 1_100
TOE_BOARD_MM = 100

#: 통로 **유효**폭 (mm). 통로 밴드는 1,200 이지만 벽부 분전반 D300 을 빼면
#: 사람이 지나는 폭은 그만큼 좁다 — 플랫폼이 들어갈 자리를 따질 때 봐야 하는
#: 것은 밴드가 아니라 이쪽이다.
AISLE_CLEAR_MM = wiring.aisle_clear_width_mm()


# ── 접근 지점 ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Point:
    """정비 접근이 필요한 자리 하나."""

    tag: str
    equipment: str
    station: str
    height_mm: int
    task: str
    per_year: int           # 연간 접근 횟수 — 수단 선택의 근거다
    ours: bool              # 우리 공급 범위인가 (아니면 값만 넘긴다)
    basis: str

    @property
    def needs_fall_protection(self) -> bool:
        return self.height_mm >= FALL_PROTECTION_MM

    @property
    def means(self) -> str:
        return means_for(self.height_mm)


def means_for(height_mm: int) -> str:
    """높이 하나가 수단을 정한다."""
    if height_mm < STEP_REACH_MM:
        return "상시 수단 불요"
    if height_mm < FALL_PROTECTION_MM:
        return "발판 (추락 방호 불요)"
    if height_mm <= MOBILE_PLATFORM_MM:
        return "이동식 작업대 + 안전대"
    if height_mm <= LADDER_GUARD_MM * 3:
        return "고정사다리(등받이) 또는 고소작업대 + 안전대"
    return "고소작업대 전용 + 안전대 (건물 측 협의)"


POINTS: tuple[Point, ...] = (
    Point("AC-01", "VG-101 비전보 상단 헤드·조명", "afu", crane.tallest_lift().height_mm,
          "카메라·조명 청소, 교정 타깃 확인", 12, True,
          "이 플랜트의 최고 고정점이다. 크레인 후크 여유 1,330 을 정한 바로 그 높이"),
    Point("AC-02", "TDM-201 갠트리 크로스헤드·X축 빔", "grm", 3_100,
          "핫나이프 교체, LM 가이드 급유", 26, True,
          "칼날은 마모품이라 접근이 잦다 — 2주에 한 번꼴"),
    Point("AC-03", "GRM-401 5단 랙 상단 IR 뱅크", "grm", 3_000,
          "IR 램프 교체, 반사판 청소", 6, True,
          "램프는 수명품이다. 고온부라 냉각 지연 인터록(SF-09)과 같이 묶인다"),
    Point("AC-04", "AFR CL-221 클램프 포탈 크로스헤드", "afr", 2_130,
          "실린더 점검, 힘 센서 교정", 4, True,
          "포탈 기둥 z ±1,450 사이라 이동식 작업대가 들어갈 폭이 있다"),
    Point("AC-05", "CMP-701 압축공기 주관·행거", "post", 2_590,
          "누설 점검, 드레인 트랩", 12, True,
          f"**통로 위를 {air.HEADER_RUN_MM / 1000:.0f} m 지난다** — 한 자리가 아니라 "
          f"선이라 이동식이 사실상 유일하다. 행거 {air.hangers()}개소가 전부 점검 대상이다"),
    Point("AC-06", "가드 상부 횡빔·카메라 배선 레일", "jbr", 2_790,
          "배선 점검, 상부 카메라 정렬", 4, True,
          "가드 위라 아래에 사람이 없다는 확인이 먼저다"),
    Point("AC-07", "DX-601 집진기 백 교체구", "post", 2_400,
          "필터백 교체 (차압 상승 시)", 2, True,
          "분진 노출 작업이라 국소배기와 보호구가 같이 온다 — §43 분진 항목과 겹친다"),
    Point("AC-08", "CRN-901 주행레일·엔드트럭", "afu", crane.rail_top_mm(),
          "레일 마모·볼트 점검, 호이스트 정비", 2, False,
          f"**건물 측이다.** 우리는 TOR {crane.rail_top_mm():,} 과 정비 접근이 필요하다는 "
          "것만 넘긴다 — "
          "캣워크를 세울지 고소작업대로 갈지는 건축이 정한다"),
)


def ours() -> tuple[Point, ...]:
    return tuple(p for p in POINTS if p.ours)


def handed_to_building() -> tuple[Point, ...]:
    return tuple(p for p in POINTS if not p.ours)


def needing_fall_protection() -> tuple[Point, ...]:
    return tuple(p for p in POINTS if p.needs_fall_protection)


def highest() -> Point:
    return max(POINTS, key=lambda p: p.height_mm)


def most_frequent() -> Point:
    return max(POINTS, key=lambda p: p.per_year)


def annual_exposures() -> int:
    """연간 고소 접근 횟수 합 — 안전대 고정점이 몇 번 쓰이는지."""
    return sum(p.per_year for p in needing_fall_protection())


# ── 자리가 있는가 ────────────────────────────────────────────────────────
def fixed_platform_footprint_mm(restricted: bool = False) -> int:
    """고정 플랫폼이 먹는 폭 — 발판 + 난간 기둥·발끝막이 여유."""
    deck = PLATFORM_WIDTH_RESTRICTED_MM if restricted else PLATFORM_WIDTH_MM
    return deck + 2 * 60      # 양측 난간 기둥·발끝막이


def fixed_platform_fits_aisle(restricted: bool = False) -> bool:
    """고정 플랫폼을 통로에 세우고도 사람이 지나갈 수 있는가."""
    return AISLE_CLEAR_MM - fixed_platform_footprint_mm(restricted) >= 550


def aisle_left_after_platform_mm(restricted: bool = False) -> int:
    return AISLE_CLEAR_MM - fixed_platform_footprint_mm(restricted)


#: 그래서 이동식으로 간다. 다만 이동식이 지우지 못하는 것이 하나 있다.
MOBILE_IS_THE_ANSWER = True

#: 추락방지 고정점 — 이동식 작업대를 써도 안전대는 어딘가에 걸어야 한다.
#: 고정점은 1인당 15 kN(EN 795) 을 받아야 하므로 아무 데나 못 건다.
ANCHOR_POINT_KN = 15.0


def anchor_points() -> tuple[tuple[str, str], ...]:
    """고정점을 어디에 두는가 — 그리고 그것이 누구 일인가."""
    return (
        ("장비 프레임 (AC-02·03·04·06)",
         "갠트리 기둥·포탈 기둥·가드 프레임은 이미 바닥에 앵커돼 있다. "
         f"고정점 {ANCHOR_POINT_KN:g} kN 을 그 부재에 얹는다 — **우리 일이다**"),
        ("건물 철골 (AC-01·05·08)",
         "비전보 상단·통로 상부·크레인 레일은 받칠 우리 부재가 없다. "
         "크레인 주행거더·공압 주관과 같은 자리다 — **건물이 받는다**"),
        ("DX-601 백 교체구 (AC-07)",
         "집진기 자체 구조에 붙이되, 분진 노출 작업이라 고정점보다 "
         "국소배기·보호구가 먼저다"),
    )


def summary() -> dict[str, object]:
    """도면 리터럴이 받아 가는 값."""
    return {
        "points": len(POINTS),
        "ours": len(ours()),
        "building": len(handed_to_building()),
        "fallProtection": len(needing_fall_protection()),
        "highestTag": highest().tag,
        "highestMm": highest().height_mm,
        "mostFrequentTag": most_frequent().tag,
        "annualExposures": annual_exposures(),
        "aisleClearMm": AISLE_CLEAR_MM,
        "platformFootprintMm": fixed_platform_footprint_mm(),
        "platformRestrictedMm": fixed_platform_footprint_mm(True),
        "aisleLeftMm": aisle_left_after_platform_mm(),
        "fixedFits": fixed_platform_fits_aisle(),
        "anchorKn": ANCHOR_POINT_KN,
        "guardrailMm": GUARDRAIL_MM,
        "fallProtectionMm": FALL_PROTECTION_MM,
    }
