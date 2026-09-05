"""부품 지지·장착 — 무엇이 무엇을 받치는가의 단일 출처.

REV.25 까지 이 플랜트의 앵커 계획은 셀 표제란에 **문장 한 줄**로만 있었다.
`grm` 은 "랙 8×M20 · 마스트 4×M20/기 · 탠덤 빔 12×M16 · 후드 독립지지" 라고
정확히 적고 있었는데, 정작 3D 에는 그 앵커가 받칠 것이 하나도 없었다 —
5단 랙 24메시가 바닥에서 600 mm 뜬 채 서 있었다. **사양은 글로 있고 형상이
없었다.** 글은 검사할 수 없고, 검사할 수 없는 사양은 지켜지지 않는다.

그래서 두 가지를 한다.

1. 앵커 계획을 구조화해 여기로 옮긴다. 개수·볼트 규격·베이스플레이트가 값이
   되면 합계도 나오고 기초도면에 넘길 수 있다.
2. 그 앵커가 받치는 **지지 부재**를 목록으로 못 박는다. 3D 에 그 부재가 없으면
   테스트가 실패한다 — "랙 8×M20" 이라고 적었으면 받칠 랙 다리가 있어야 한다.

하중 경로 자체(모든 부품이 바닥까지 이어지는가)는 기하로만 확인할 수 있어
헤드리스 검사(`scratchpad/support.mjs`)가 맡는다. 여기서는 **무엇이 예외인지**를
정의한다 — 공정 중 물체와 투영선은 받칠 대상이 아니다.

볼트 규격은 계획값이다. 하중도(반력·전도모멘트)가 확정되면 개수와 규격이
바뀌며, 그때 이 파일만 고치면 도면·집계가 따라온다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import kinematics
from .layout import STATIONS

# ── 지지 등급 ────────────────────────────────────────────────────────────
#: 부품이 하중을 넘기는 방식. 3D 의 지지 부재는 전부 이 중 하나다.
SUPPORT_CLASSES: dict[str, str] = {
    "floor": "바닥 앵커 — 기초에 베이스플레이트와 앵커볼트로 고정",
    "frame": "셀 프레임 볼트 — 셀 구조 프레임에 브래킷으로 체결",
    "gantry": "갠트리 현수 — 상부 빔에서 매단다",
    "wall": "통로 외곽벽 벽부 — 깊이 300, 보행 유효폭 900 유지",
    "carried": "공정 중 물체 — 받칠 대상이 아니다",
}


@dataclass(frozen=True)
class Anchor:
    """앵커 한 군(群). '/기' 는 개소마다 이만큼이라는 뜻이다."""

    target: str          # 무엇을 고정하는가
    count: int           # 개소당(per_unit) 또는 전체
    bolt: str            # 'M16' | 'M20' | 'M24'
    units: int = 1       # 개소 수
    per_unit: bool = False

    @property
    def total(self) -> int:
        return self.count * self.units if self.per_unit else self.count


@dataclass(frozen=True)
class Mounting:
    """셀 하나의 장착 사양."""

    station: str
    anchors: tuple[Anchor, ...]
    plate: str           # 베이스플레이트 사양
    grout_mm: int        # 무수축 그라우트 두께
    level: str           # 레벨링 방식
    note: str

    @property
    def total_anchors(self) -> int:
        return sum(a.total for a in self.anchors)


#: 셀별 장착 사양. 도면 표제란의 '앵커 계획' 문장과 같은 내용이며,
#: `anchor_text()` 가 그 문장을 이 데이터에서 다시 만든다 — 둘이 어긋날 수 없다.
MOUNTINGS: tuple[Mounting, ...] = (
    Mounting("afu", (Anchor("예비", 12, "M20"),),
             "300×300×20", 30, "심 ±10",
             "지게차 진입측이라 앵커를 여유 있게 잡는다"),
    Mounting("bfc", (Anchor("포탈기둥", 4, "M20", units=4, per_unit=True),),
             "레벨링 풋 500×400", 30, "X 조정 장공만",
             "반전축 직각도가 걸려 X 조정 장공만 허용한다"),
    Mounting("robot", (Anchor("로봇", 8, "M24"), Anchor("PT-101", 8, "M16")),
             "로봇 400×400×25 · PT 250×250×16", 40, "독립 grout",
             "로봇 반력이 정렬정반에 넘어가면 3-2-1 좌표가 흔들린다 — 기초를 나눈다"),
    Mounting("jbr", (Anchor("베이스", 10, "M16"), Anchor("독립가드", 4, "M16")),
             "250×250×16", 30, "풋 ±25",
             "15 kN 칼날 반력을 베이스가 받고 가드는 따로 선다"),
    Mounting("afr", (Anchor("메인셀", 16, "M20"), Anchor("HPU·FH 독립", 8, "M16"),
                     Anchor("클램프 포탈", 4, "M20", units=4, per_unit=True)),
             "300×300×20 · 포탈 320□", 30, "rail shim",
             "장축 LM 레일은 심으로 직진도를 잡는다. 클램프 포탈은 상부 클램프 "
             "4×3 kN 과 단축 인출 25 kN/축의 반작용을 받는 부재라 따로 앵커한다"),
    Mounting("post", (Anchor("라인", 12, "M16"), Anchor("DX-601", 4, "M16")),
             "250×250×16", 30, "심 ±10",
             "덕트는 셀에 얹지 않고 독립지지한다 — 진동이 광학으로 간다"),
    Mounting("buffer", (Anchor("셔틀", 12, "M20"), Anchor("도크", 20, "M16"),
                        Anchor("마스트", 4, "M16", units=2, per_unit=True)),
             "300×300×20", 30, "바닥 proof-load",
             "캐리지 만재 하중이라 바닥 내력을 실증해야 한다"),
    Mounting("grm", (Anchor("랙", 8, "M20"), Anchor("마스트", 4, "M20", units=2, per_unit=True),
                     Anchor("탠덤 빔", 12, "M16"), Anchor("후드 독립지지", 8, "M16")),
             "300×300×20 · 랙 240□", 30, "심 ±10",
             "후드는 탠덤 빔에 얹지 않는다 — 빔은 칼날 반력을 받는 부재다"),
)

MOUNTING_OF: dict[str, Mounting] = {m.station: m for m in MOUNTINGS}


# ── 지지 부재 — 앵커가 실제로 받치는 것 ──────────────────────────────────


@dataclass(frozen=True)
class Member:
    """3D 에 반드시 존재해야 하는 지지 부재."""

    label: str           # 3D userData.label 과 정확히 같아야 한다
    station: str
    support: str         # SUPPORT_CLASSES 의 키
    carries: str


#: REV.26 에서 세운 지지 부재. 라벨이 3D 에 없으면 테스트가 실패한다 —
#: 앵커 계획에 적힌 대상은 받칠 형상이 있어야 한다.
MEMBERS: tuple[Member, ...] = (
    Member("M1-101 랙 지지다리 4본 (베이스 8×M20)", "grm", "floor",
           "5단 단열랙 · IR 뱅크 · 적재 패널 5장"),
    Member("M1-101 랙 베이스 프레임", "grm", "floor", "랙 다리 4본을 묶는다"),
    Member("TDM-201 갠트리 기둥 4본 (12×M16)", "grm", "floor",
           "탠덤 공통 X축 빔 · 핫나이프 2"),
    Member("TDM-201 갠트리 크로스헤드", "grm", "floor", "기둥 4본과 X축 빔을 잇는다"),
    Member("HKB-101 Z축 슬라이드", "grm", "gantry", "백시트 개방 핫나이프"),
    Member("HKS-201 Z축 슬라이드", "grm", "gantry", "셀/EVA 분리 핫나이프"),
    Member("GRM-EX-401 덕트 스탠션 4", "grm", "frame", "IR 배기 덕트"),
    Member("GRM-CD-401 후드 독립지지 기둥 4본", "grm", "floor", "냉각 후드"),
    Member("AFR CV-101 컨베이어 사이드 프레임 2본", "afr", "floor", "투입 롤러 12본"),
    Member("AFR CV-101 가대 다리 8본 (베이스플레이트 240□)", "afr", "floor",
           "컨베이어 사이드 프레임"),
    Member("CMP-701 컴프레서 방진 마운트 2조", "post", "floor",
           "스크류 2대 × 5.5 kW — 회전기라 방진 마운트로 받는다"),
    Member("CMP-701 리시버 300 L 새들 2본", "post", "floor",
           "압력용기 수직 거치 — 전도모멘트를 바닥이 받는다"),
    Member("AFR CL-221 클램프 포탈 기둥 4본", "afr", "floor",
           "상부 클램프 4기 × 3 kN · 단축 인출 25 kN/축 반작용"),
    Member("AFR CL-221 포탈 크로스헤드 2본", "afr", "floor",
           f"상부 클램프 실린더 4기 — 하면 {kinematics.AFR_CROSSHEAD_SOFFIT_MM:,} 이 "
           f"실린더 상단을 직접 받는다"),
    Member("AFR 클램프 포탈 종방향 타이빔 2본", "afr", "floor",
           "두 포탈을 한 틀로 묶어 인출 반력의 X 성분을 받는다"),
    Member("AFR TG-813 도크 선단받이 가이드레일 2본", "buffer", "frame",
           "신장한 텔레스코픽 콤포크의 선단 — 2.9 m 외팔보를 단순지지로 바꾼다"),
    Member("VAC-101 진공 스키드 베이스", "afu", "floor",
           "진공 리시버 2기 · 진공발생기·필터 유닛"),
    Member("VG-101 천장보 독립 기둥 2본", "afu", "floor",
           "천장 비전보 · VS-101A/B 통합 헤드"),
    Member("MCR-901 콘솔 다리 12본", "smart", "floor", "운전 콘솔 3대"),
)

#: 생성 브래킷의 태그 접두. 각 부유 부재와 가장 가까운 접지 부재 사이의
#: **실측 간격**에서 나왔다 — 임의로 세운 것이 아니라 잰 것이다.
BRACKET_PREFIX = "MB-"

#: 브래킷 본수 — `tools/build_brackets.mjs` 의 출력이다. 손으로 정하지 않는다.
#:
#: REV.47 까지 51본이 씬에 **월드 좌표 리터럴**로 박혀 있었고 만든 도구가
#: 저장소에 없었다. 그래서 셀을 하나라도 옮기면 브래킷이 옛 자리에 남아 하중
#: 경로가 끊겼다 — A-2b 첫 시도에서 12본이 실제로 그렇게 떴다. 형상을 옮길 수
#: 없는 도면은 고칠 수 없는 도면이므로, 재생성기를 세우고 이 값을 그 출력으로
#: 바꾼다. 형상이 바뀌면 도구를 다시 돌리고 이 한 줄을 같이 고친다.
#:
#: 폐번 대장(MB-021·022)은 없앴다 — 번호가 생성물이면 지킬 것이 없다. 대신
#: **그 번호들이 가르쳐 준 것**을 규칙으로 옮겼다 (`BRACKET_KEEP_OUT`).
BRACKET_COUNT = 50

#: 브래킷이 들어가면 안 되는 부피 — (이름, (x0, x1, y0, y1), 사유). 단위 m, 씬 월드.
#:
#: "가장 가까운 접지 부재에 매단다" 는 규칙은 **움직이는 것 옆에서 틀린다.**
#: 그 자리에 부재가 있다는 것과 그 자리가 늘 비어 있다는 것은 다른 말이다.
#: 팔레트는 발자국 그대로 픽업면 1,880 까지 올라가므로, 막아야 할 것은 바닥
#: 자리가 아니라 **쓸고 지나가는 부피**다 — 그래서 높이까지 적는다.
BRACKET_KEEP_OUT: tuple[tuple[str, tuple[float, float, float, float], str], ...] = (
    ("LFT-101A 팔레트 승강 경로", (-22.45, -18.85, 0.20, 1.95),
     "팔레트 발자국(2,760)이 픽업면 1,880 까지 그대로 올라간다. 지게차 인계 "
     "자리(−22.43)부터 리프트 발자국 하류끝(−18.83)까지가 한 팔레트가 쓸고 "
     "지나가는 X 다 — 실측."),
    ("LFT-101B 팔레트 승강 경로", (-21.85, -18.85, 0.20, 1.95),
     "BFC 셔틀 레일을 최근접 부재에 물리려던 브래킷 2본이 바로 여기 섰다가 "
     "간섭 스윕에 팔레트와의 겹침으로 잡혔다(옛 MB-021·022). 팔레트 발자국 "
     "밖의 지지 포스트로 대체했고, 이 부피에는 세우지 않는다. REV.48 에서 "
     "AFU 무리가 상류로 3,700 물러나며 이 부피도 같이 왔다 — 리터럴이면 "
     "브래킷이 다시 팔레트 밑으로 들어갔을 자리다. REV.49 에서 셔틀 자체가 "
     "없어져 포스트도 갔지만, 팔레트가 쓸고 지나가는 부피라는 사실은 그대로라 "
     "이 규칙은 남는다 — 이제는 반전 드럼이 이 부피 **바로 위**에 선다."),
)


def bracket_tags() -> tuple[str, ...]:
    """도면에 있는 브래킷 태그 — 생성기가 001 부터 빈 번호 없이 매긴다."""
    return tuple(f"{BRACKET_PREFIX}{i:03d}" for i in range(1, BRACKET_COUNT + 1))


# ── 받칠 대상이 아닌 것 ──────────────────────────────────────────────────
#: 하중 경로가 없어도 되는 것. 늘리려면 근거가 있어야 한다.
UNSUPPORTED_BY_DESIGN: tuple[tuple[str, str], ...] = (
    ("이송 중 태양광 패널", "로봇·셔틀이 들고 있는 공정 중 물체다"),
    ("VS-101 검출 정션박스 형상", "위 패널에 붙어 같이 옮겨진다"),
    ("VS-101A/B-FUSED 고정면 스캔선", "레이저 투영선이라 물체가 아니다"),
    ("CMP-701 압축공기 주관", "통로 상부를 51 m 지나는 DN20 강관이다. 바닥에서 "
     "기둥을 세우면 통로 유효폭 900 을 먹고, 3D 에 케이블 트레이가 없어 매달 "
     "것도 없다 — **건물 벽·기둥이 받는 부재**이며 건축 grid 가 확정되면 "
     "트레이와 같은 브래킷에 얹는다. 건물 측 요구값은 행거 간격 3,000 · "
     "행거당 3.9 kg 이다"),
    ("CRN-901", "천장크레인은 **건물 철골**이 받는다. 이 플랜트의 공급 범위가 "
     "아니라 기둥을 지어내지 않고, 건물 측에 요구값(주행레일 상면 10,750 · "
     "스팬 8,800 · 주행 반력)을 도면으로 넘긴다"),
)


def anchor_text(station: str) -> str:
    """도면 표제란에 들어가는 '앵커 계획' 문장 — 데이터에서 만든다."""
    m = MOUNTING_OF[station]
    parts = []
    for a in m.anchors:
        if a.per_unit:
            parts.append(f"{a.target} {a.count}×{a.bolt}/기")
        else:
            parts.append(f"{a.target} {a.count}×{a.bolt}")
    parts.append(m.plate)
    parts.append(f"grout {m.grout_mm}")
    parts.append(m.level)
    return " · ".join(parts)


def total_anchors() -> int:
    """플랜트 전체 앵커 수 — 기초도면(FD-1002)으로 넘기는 값."""
    return sum(m.total_anchors for m in MOUNTINGS)


def anchors_by_bolt() -> dict[str, int]:
    """볼트 규격별 수량 — 발주 단위."""
    out: dict[str, int] = {}
    for m in MOUNTINGS:
        for a in m.anchors:
            out[a.bolt] = out.get(a.bolt, 0) + a.total
    return dict(sorted(out.items()))


def members_of(station: str) -> tuple[Member, ...]:
    return tuple(m for m in MEMBERS if m.station == station)


def members_by_class() -> dict[str, int]:
    out = {key: 0 for key in SUPPORT_CLASSES}
    for m in MEMBERS:
        out[m.support] += 1
    return out


def stations_are_covered(stations: set[str] | None = None) -> bool:
    """모든 공정 셀에 장착 사양이 있는가.

    `stations` 를 받는 것은 시험을 위해서다. 지금 8개가 이미 다 덮여 있으면
    이 검사를 `return True` 로 바꿔도 아무 테스트가 실패하지 않는다 — 셀을
    하나 더 넣어 보고 실제로 걸리는지까지 확인한다.
    """
    return set(MOUNTING_OF) == (set(STATIONS) if stations is None else stations)


def summary() -> dict[str, object]:
    """도면(MT-1015)이 그대로 쓰는 요약."""
    return {
        "stations": len(MOUNTINGS),
        "anchors": total_anchors(),
        "by_bolt": anchors_by_bolt(),
        "members": len(MEMBERS),
        "brackets": BRACKET_COUNT,
        "keepOut": len(BRACKET_KEEP_OUT),
        "by_class": members_by_class(),
        "exempt": len(UNSUPPORTED_BY_DESIGN),
    }
