# -*- coding: utf-8 -*-
"""체결 부품 정본 — 볼트·너트·와셔의 **형상과 치수**, 그리고 길이가 맞는지.

제작 패키지(`fabrication`)는 체결을 **호칭**으로만 적는다: `M20×70 10.9`,
토크 550 N·m, 관통 구멍 22.0. 그것으로 발주는 되지만 **제작은 안 된다.**
현장에서 필요한 것이 셋 더 있다.

1. **형상** — 육각 머리의 대변 거리와 머리 두께를 모르면 스패너 자리(공구
   여유)를 도면에 잡을 수 없다. 너트 높이와 와셔 두께를 모르면 볼트 길이가
   맞는지 알 수 없다.
2. **쌓임** — 관통 체결 하나에 들어가는 것은 볼트만이 아니다. 평와셔 2 ·
   스프링와셔 1 · 너트 1 이고, 그 두께의 합이 볼트 길이를 먹는다.
3. **검산** — 그래서 `M20×250` 앵커가 매입 170 + 베이스 25 + 그라우트 30 을
   지나 너트까지 닿는지는 **계산해 봐야 안다.** 이 모듈이 그 계산을 한다.

값의 성격을 분명히 해 둔다. 치수는 **KS·ISO 규격의 호칭값**이다 — 지어낸
값이 아니라 규격표의 값이고, 실제 조달품은 벤더 시험성적서가 governs 한다.
등급·토크·구멍·매입 깊이는 `fabrication` 에서 그대로 읽어 온다 — 두 곳에
같은 값을 적지 않는다.

    PYTHONPATH=src python tools/build_fasteners.py
"""

from __future__ import annotations

from dataclasses import dataclass

from . import fabrication

#: 이 설계가 쓰는 호칭. `fabrication` 의 토크표와 같은 집합이어야 한다.
SIZES: tuple[str, ...] = ("M6", "M8", "M10", "M12", "M16", "M20", "M24", "M30")


@dataclass(frozen=True)
class HexBolt:
    """육각볼트 KS B 1002 (ISO 4014 반나사 / ISO 4017 온나사).

    `s` 대변 거리 · `k` 머리 두께 · `b` 반나사 볼트의 나사부 길이 (L ≤ 125 일 때).
    """

    d: float
    pitch: float
    s: float
    k: float

    @property
    def b(self) -> float:
        """반나사 나사부 길이 — ISO 4014 는 L ≤ 125 에서 2d + 6."""
        return 2 * self.d + 6

    @property
    def spanner_mm(self) -> float:
        """스패너가 도는 데 필요한 최소 원지름 — 대변 거리의 대각(2/√3)에 여유."""
        return round(self.s * 1.155 + 6, 1)


@dataclass(frozen=True)
class HexNut:
    """육각너트 KS B 1012 (ISO 4032) 1종. `m` 은 너트 높이."""

    d: float
    s: float
    m: float


@dataclass(frozen=True)
class Washer:
    """와셔. `d1` 안지름 · `d2` 바깥지름 · `h` 두께."""

    d1: float
    d2: float
    h: float


#: 육각볼트 — KS B 1002 / ISO 4014 호칭 치수.
HEX_BOLT: dict[str, HexBolt] = {
    "M6": HexBolt(6, 1.00, 10, 4.0),
    "M8": HexBolt(8, 1.25, 13, 5.3),
    "M10": HexBolt(10, 1.50, 16, 6.4),
    "M12": HexBolt(12, 1.75, 18, 7.5),
    "M16": HexBolt(16, 2.00, 24, 10.0),
    "M20": HexBolt(20, 2.50, 30, 12.5),
    "M24": HexBolt(24, 3.00, 36, 15.0),
    "M30": HexBolt(30, 3.50, 46, 18.7),
}

#: 육각너트 — KS B 1012 / ISO 4032 1종.
HEX_NUT: dict[str, HexNut] = {
    "M6": HexNut(6, 10, 5.2),
    "M8": HexNut(8, 13, 6.8),
    "M10": HexNut(10, 16, 8.4),
    "M12": HexNut(12, 18, 10.8),
    "M16": HexNut(16, 24, 14.8),
    "M20": HexNut(20, 30, 18.0),
    "M24": HexNut(24, 36, 21.5),
    "M30": HexNut(30, 46, 25.6),
}

#: 평와셔 — KS B 1326 / ISO 7089 (경도 200 HV).
PLAIN_WASHER: dict[str, Washer] = {
    "M6": Washer(6.4, 12, 1.6),
    "M8": Washer(8.4, 16, 1.6),
    "M10": Washer(10.5, 20, 2.0),
    "M12": Washer(13.0, 24, 2.5),
    "M16": Washer(17.0, 30, 3.0),
    "M20": Washer(21.0, 37, 3.0),
    "M24": Washer(25.0, 44, 4.0),
    "M30": Washer(31.0, 56, 4.0),
}

#: 스프링와셔 — KS B 1324 (DIN 127 B 상당). 두께는 자유 높이가 아니라 판두께다.
SPRING_WASHER: dict[str, Washer] = {
    "M6": Washer(6.1, 11.8, 1.6),
    "M8": Washer(8.1, 14.8, 2.0),
    "M10": Washer(10.2, 18.1, 2.2),
    "M12": Washer(12.2, 21.1, 2.5),
    "M16": Washer(16.2, 27.4, 3.5),
    "M20": Washer(20.2, 33.6, 4.0),
    "M24": Washer(24.5, 40.0, 5.0),
    "M30": Washer(30.5, 49.0, 6.0),
}

#: 등급별 재질·표면처리와 짝 부품 등급.
GRADES: tuple[tuple[str, str, str, str, str], ...] = (
    ("8.8", "탄소강 담금질·뜨임", "항복 640 N/mm² · 인장 800 N/mm²", "너트 등급 8", "아연도금 KS D 8304 (Fe/Zn 8c)"),
    ("10.9", "합금강 담금질·뜨임", "항복 940 N/mm² · 인장 1,040 N/mm²", "너트 등급 10", "아연도금 또는 다크로 — 지연파괴 주의"),
    ("앵커", "HAS-U 8.8 앵커 로드", "케미컬 주입식 (HIT-HY 200 상당)", "너트 등급 8", "아연도금 · 콘크리트 C24 이상"),
)

#: 너트 밖으로 나와야 하는 최소 나사산 수 — 조여졌는지 눈으로 보는 기준이다.
PROTRUSION_THREADS = 2

#: 나사 물림 배수 (모재 기준). `fabrication.FASTENER_STANDARDS` 의 '나사 물림' 과 같다.
ENGAGEMENT: tuple[tuple[str, float, str], ...] = (
    ("강 (SS400 · S355 · SM490A · S45C)", 1.0, "KS 관례 최소 1.0 d — 반복하중부는 1.5 d 로 잡는다"),
    ("알루미늄 (A6061-T6)", 2.0, "모재가 물러 나사산이 먼저 진다"),
    ("스테인리스 (STS304)", 1.5, "소착 방지 컴파운드 병용"),
)

#: 풀림 방지 — 어디에 무엇을 쓰는가.
LOCKING: tuple[tuple[str, str, str], ...] = (
    ("관통 체결 (일반)", "평와셔 2 + 스프링와셔 1 (너트측)",
     "볼트 머리·너트 양쪽에 평와셔, 너트 밑에 스프링와셔. 도장면을 파고들지 않게 한다"),
    ("탭 체결 (진동 있음)", "나사고정제 중강도 (Loctite 243 상당)",
     "서보·감속기·구동 롤러·LM 레일처럼 회전·왕복이 걸리는 자리"),
    ("탭 체결 (진동 없음)", "평와셔 1 + 스프링와셔 1", "브래킷·커버·센서 자리"),
    ("반전 하중부 (엔드링·조·크로스빔)", "10.9 볼트 + 토크 마킹 + 재점검",
     "정격 토크로 조인 뒤 마킹하고, 무부하 시운전 뒤와 100 사이클 뒤에 다시 본다"),
    ("앵커", "너트 + 평와셔 · 그라우트 양생 후 규정 토크",
     "양생 전에 토크를 걸면 케미컬이 파괴된다"),
)


# ── 쌓임과 길이 ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Stack:
    """체결 하나의 쌓임. 길이가 맞는지 보려면 이 두께 합이 필요하다."""

    kind: str
    items: tuple[tuple[str, float], ...]      # (이름, 두께 mm)

    @property
    def consumed_mm(self) -> float:
        """볼트 길이 중 판(그립)이 아닌 것이 먹는 길이."""
        return round(sum(t for _, t in self.items), 2)


def stack(size: str, kind: str) -> Stack:
    """호칭과 체결 종류에서 부속 쌓임을 낸다 — 그립(판 두께)은 빼고."""
    pw, sw, nut = PLAIN_WASHER[size], SPRING_WASHER[size], HEX_NUT[size]
    thread = PROTRUSION_THREADS * HEX_BOLT[size].pitch
    if kind == "관통":
        return Stack(kind, (("평와셔 (머리측)", pw.h), ("평와셔 (너트측)", pw.h),
                            ("스프링와셔", sw.h), ("너트", nut.m), ("나사산 여유", thread)))
    if kind == "탭":
        return Stack(kind, (("평와셔", pw.h), ("스프링와셔", sw.h)))
    if kind == "앵커":
        return Stack(kind, (("평와셔", pw.h), ("너트", nut.m), ("나사산 여유", thread)))
    raise KeyError(kind)


def grip_max_mm(size: str, length: float, kind: str = "관통") -> float:
    """이 길이의 볼트가 물 수 있는 **최대 판 두께 합** (mm)."""
    return round(length - stack(size, kind).consumed_mm, 2)


def thread_reaches(size: str, length: float) -> bool:
    """반나사(ISO 4014) 볼트의 나사부가 너트를 지나는가.

    거짓이면 그 자리는 **온나사(ISO 4017)** 를 써야 한다 — 매끈한 몸통이
    너트에 물리면 조여지지 않는다.
    """
    del length                                   # 나사부 길이는 L 에 무관하다 (L ≤ 125)
    need = stack(size, "관통").consumed_mm - PLAIN_WASHER[size].h   # 머리측 와셔는 나사부가 아니다
    return HEX_BOLT[size].b >= need


def tapped_depth_mm(size: str, engagement_mm: float) -> float:
    """탭 깊이 = 물림 + 불완전 나사부 2 피치."""
    return round(engagement_mm + 2 * HEX_BOLT[size].pitch, 1)


# ── 설계에 실제로 쓰인 체결 ─────────────────────────────────────────────
@dataclass(frozen=True)
class Use:
    """조립체 하나의 체결 한 줄 — 호칭을 형상까지 풀어 놓은 것."""

    sheet: str
    assembly: str
    joint: str
    parts: str
    size: str
    length: float
    cls: str
    kind: str
    qty: int
    torque_nm: int
    hole_mm: float
    note: str

    @property
    def grip_max_mm(self) -> float | None:
        if self.kind == "용접":
            return None
        return grip_max_mm(self.size, self.length, self.kind)


def _split(bolt: str) -> tuple[str, float, str] | None:
    """'M20×70 10.9' · 'M20×250 앵커' → (호칭, 길이, 등급). 용접이면 None."""
    text = bolt.replace("×", "x")
    if "x" not in text:
        return None
    head, rest = text.split("x", 1)
    size = head.strip()
    parts = rest.split()
    if not parts:
        return None
    try:
        length = float(parts[0])
    except ValueError:
        return None
    return size, length, (parts[1] if len(parts) > 1 else "8.8")


def uses() -> list[Use]:
    """제작 패키지의 모든 체결을 형상까지 풀어 놓는다 (용접 제외)."""
    out: list[Use] = []
    for a in fabrication.ASSEMBLIES:
        for j in a.joints:
            got = _split(j.bolt)
            if got is None:
                continue
            size, length, cls = got
            torque = j.torque_nm or 0
            out.append(Use(a.sheet, a.tag, j.name, j.parts, size, length, cls, j.kind,
                           j.qty * a.qty, torque, fabrication.HOLE_MM.get(size, 0.0), j.note))
    return out


def sizes_used() -> list[str]:
    return sorted({u.size for u in uses()}, key=lambda s: HEX_BOLT[s].d)


def demand(spare: float = 0.10) -> list[tuple[str, str, int, int, int, int, int]]:
    """소요량 — (호칭, 등급, 볼트, 너트, 평와셔, 스프링와셔, 예비 포함 볼트).

    너트·와셔 수는 체결 종류에서 나온다. 탭 체결은 너트가 없다.
    """
    acc: dict[tuple[str, str], list[int]] = {}
    for u in uses():
        key = (u.size, u.cls)
        row = acc.setdefault(key, [0, 0, 0, 0])
        row[0] += u.qty
        if u.kind == "관통":
            row[1] += u.qty
            row[2] += 2 * u.qty
            row[3] += u.qty
        elif u.kind == "앵커":
            row[1] += u.qty
            row[2] += u.qty
        else:                                    # 탭
            row[2] += u.qty
            row[3] += u.qty
    out = []
    for (size, cls), (b, nut, pw, sw) in sorted(acc.items(), key=lambda kv: (HEX_BOLT[kv[0][0]].d, kv[0][1])):
        out.append((size, cls, b, nut, pw, sw, int(-(-b * (1 + spare) // 1))))
    return out


# ── 검산 ────────────────────────────────────────────────────────────────
def geometry_covers_the_design() -> dict[str, bool]:
    """설계가 쓰는 호칭이 전부 형상표에 있는가."""
    return {s: s in HEX_BOLT and s in HEX_NUT and s in PLAIN_WASHER and s in SPRING_WASHER
            for s in sizes_used()}


def holes_clear_the_bolts() -> dict[str, bool]:
    """관통 구멍이 볼트보다 큰가 — 같거나 작으면 안 들어간다."""
    return {s: fabrication.HOLE_MM[s] > HEX_BOLT[s].d for s in sizes_used()}


def washers_cover_the_holes() -> dict[str, bool]:
    """평와셔 바깥지름이 관통 구멍을 덮는가 — 안 덮으면 와셔가 구멍으로 들어간다."""
    return {s: PLAIN_WASHER[s].d2 > fabrication.HOLE_MM[s] + 4 for s in sizes_used()}


def threads_reach_the_nuts() -> dict[str, bool]:
    """반나사 볼트로 성립하는가. 거짓이면 온나사를 써야 한다."""
    return {s: thread_reaches(s, 0) for s in sizes_used()}


def lengths_are_long_enough() -> list[tuple[Use, float, str]]:
    """**길이 검산.** 그립이 음수이거나 너무 얇으면 그 볼트는 성립하지 않는다.

    돌려주는 것은 (체결, 남는 그립, 판정). 그립이 0 이하면 부속만으로 볼트를
    다 먹는다는 뜻이라 조여지지 않는다.
    """
    out = []
    for u in uses():
        g = u.grip_max_mm
        if g is None:
            continue
        if g <= 0:
            verdict = "불가 — 부속이 볼트를 다 먹는다"
        elif g < HEX_BOLT[u.size].d * 0.5:
            verdict = "빠듯 — 실측 확인"
        else:
            verdict = "여유"
        out.append((u, g, verdict))
    return out


def anchor_lengths() -> list[tuple[str, str, float, float, float, bool]]:
    """앵커 길이 검산 — (조립체, 호칭, 지정 길이, 필요 길이, 여유, 판정).

    필요 길이 = 매입 + 베이스플레이트 + 그라우트 + 평와셔 + 너트 + 나사산 여유.

    베이스플레이트는 **그 체결이 지목한 부품**에서 읽는다 — 조립체에서 가장
    두꺼운 판을 고르면 클램프 패드 같은 것을 베이스플레이트로 착각한다.
    그라우트는 `mounting` 의 셀별 값이다.
    """
    from . import mounting
    grout = {m.station: m.grout_mm for m in mounting.MOUNTINGS}
    out = []
    for a in fabrication.ASSEMBLIES:
        by_tag = {p.tag: p for p in a.parts}
        for j in a.joints:
            if j.kind != "앵커":
                continue
            got = _split(j.bolt)
            if got is None:
                continue
            size, length, _ = got
            embed = fabrication.ANCHOR_EMBED_MM.get(size, 0)
            named = [by_tag[w].t for w in j.parts.replace("↔", " ").split() if w in by_tag]
            plate = named[0] if named else 20
            g = grout.get(ANCHOR_CELL[a.tag], 30)
            need = embed + plate + g + stack(size, "앵커").consumed_mm
            out.append((a.tag, size, length, round(need, 1), round(length - need, 1), length >= need))
    return out


#: 케미컬 앵커 로드 표준 공급 길이 (mm). 임의 길이는 안 나온다 — 이 계열에서 고른다.
ANCHOR_ROD_LENGTHS: dict[str, tuple[int, ...]] = {
    "M12": (110, 160, 190, 220, 260),
    "M16": (125, 190, 220, 260, 300),
    "M20": (170, 210, 250, 260, 300, 350),
    "M24": (210, 260, 300, 350, 400),
}


def anchor_rod_for(size: str, need_mm: float) -> int:
    """필요 길이를 만족하는 가장 짧은 표준 로드 길이."""
    for length in ANCHOR_ROD_LENGTHS[size]:
        if length >= need_mm:
            return length
    raise ValueError(f"{size} 표준 계열에 {need_mm} mm 를 넘는 길이가 없다")


#: 조립체가 어느 셀 기초에 앉는가 — 그라우트 두께가 셀마다 다르다.
ANCHOR_CELL: dict[str, str] = {
    "AFU-BW-101": "afu", "AFU-VG-101": "afu", "AFU-BFC-101": "bfc", "AFU-CD-101": "bfc",
    "AFU-RB-101 · EOAT-101": "robot", "AFU-PT-101 · AL-101": "robot", "AFU-RJ-101": "robot",
    "JB-201": "robot", "AFU-LFT-101 · SE-101": "afu", "AFU-VAC-101 · HPU-101": "afu",
    "AFU-SF-101": "afu", "MB-0xx": "robot",
}


def summary() -> dict[str, object]:
    d = demand()
    return {
        "sizes": len(sizes_used()),
        "joints": len(uses()),
        "bolts": sum(r[2] for r in d),
        "nuts": sum(r[3] for r in d),
        "plain_washers": sum(r[4] for r in d),
        "spring_washers": sum(r[5] for r in d),
        "bolts_with_spare": sum(r[6] for r in d),
        "short_bolts": sum(1 for _, _, v in lengths_are_long_enough() if v.startswith("불가")),
        "tight_bolts": sum(1 for _, _, v in lengths_are_long_enough() if v.startswith("빠듯")),
        "short_anchors": sum(1 for r in anchor_lengths() if not r[5]),
    }
