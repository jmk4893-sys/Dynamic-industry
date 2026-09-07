"""조달 계산 — 자재 발주표 · 운반 분할 · 구매품 사양.

부품 카탈로그(parts.py)는 "무엇을 만드는가" 를 든다. 이 파일은 그것을
**살 수 있는 것과 실을 수 있는 것**으로 바꾼다.

  ① 자재 발주표 — 부재를 재고 규격으로 묶고, 1차원 절단 배치를 실제로
     풀어 정척 몇 본을 사야 하는지와 남는 토막이 얼마인지를 낸다.
     "총 길이 96 m" 는 발주서가 아니다. "6 m 정척 19본" 이 발주서다.
  ② 운반 분할 — 부재를 차량 적재 단위로 묶는다. 순서는 세우는 순서를
     따른다 — 나중에 세울 것이 먼저 도착하면 현장에 둘 자리가 없다.
  ③ 구매품 사양 — 59 종의 구매 규격을 발주 가능한 수준으로 적는다.

이 계산이 가장 먼저 하는 일은 **재고에 없는 치수를 찾아내는 것**이다.
도면에 그릴 수는 있어도 살 수 없는 판이 있으면 제작이 그 자리에서 멈춘다.
"""

from __future__ import annotations

import math
import pathlib
import sys
from typing import NamedTuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import parts as PT  # noqa: E402

# ── 1. 재고 규격 ───────────────────────────────────────────────────────
# 국내 유통 정척이다. 이 목록 밖의 치수는 살 수 없고, 살 수 없는 치수를
# 도면에 그리면 제작이 그 자리에서 멈춘다 — 그래서 계산이 먼저 이것을 본다.

# 형강·강관·봉 — 정척 길이 (mm). 긴 쪽부터 본다.
BAR_STOCK = (12000, 6000)
BAR_STOCK_SMALL = (6000, 4000)          # 소형 각관·환봉·각봉
CUT_KERF = 5                            # 절단 손실 (톱날 폭 + 단면 정리)
BAR_TRIM = 50                           # 정척 양단 트림

# 판재 — (폭, 길이) mm. 재질별로 유통 형태가 다르다. SKD11 과 동은 시트가
# 아니라 **연삭 플랫바 · 부스바** 로 팔린다 — 시트로 잡으면 살 수 없다고
# 잘못 판정한다. 형태를 틀리게 적으면 계산이 없는 문제를 만들어 낸다.
PLATE_STOCK = {
    "SS400":   ((1524, 3048), (2438, 6096), (1500, 6000), (2000, 6000)),
    "SM490A":  ((1524, 3048), (2438, 6096), (1500, 6000)),
    "STS304":  ((1219, 2438), (1524, 3048)),
    "SM45C":   ((1000, 2000),),
    "SKD11":   ((100, 2000), (200, 1000)),   # 연삭 플랫바 (공구강은 시트가 아니다)
    "A6061-T6": ((1219, 2438), (1524, 3048)),
    "동":       ((100, 4000), (1000, 2000)),  # 부스바 스트립
    "PC":      ((2050, 3050),),
    "GFRP":    ((1220, 2440),),
    "미네랄울":   ((600, 1000), (600, 1200)),  # 보드 — 규격대로 온다
    "AL반사판":  ((1000, 2000),),
    "세라믹파이버": ((610, 7300),),             # 롤재 — 길이는 롤 전장
}
# 유통 두께. 이 목록 밖의 두께는 살 수 없다 — 도면에 t90 을 그려도
# 그 판은 재고에 없고, 후판으로 절단 발주하면 납기와 가격이 달라진다.
PLATE_THICK = {
    "SS400":   (1.6, 2.0, 2.3, 3.2, 4.5, 5, 6, 8, 9, 10, 12, 14, 16, 19, 20, 22, 25, 28, 32),
    "SM490A":  (6, 8, 9, 10, 12, 14, 16, 19, 20, 22, 25, 28, 32, 36, 40),
    "STS304":  (1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 3.2, 4.0, 5.0, 6.0, 8.0, 10.0),
    "SM45C":   (6, 8, 10, 12, 16, 20, 25, 30),
    "SKD11":   (5, 6, 8, 10, 12, 16, 20, 25),
    "A6061-T6": (2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20),
    "동":       (3, 4, 5, 6, 8, 10),
    "PC":      (2, 3, 4, 5, 6, 8, 10, 12),
    "GFRP":    (3, 5, 6, 8, 10, 12, 15, 20),
    "미네랄울":   (25, 50, 75, 100),
    "AL반사판":  (0.3, 0.5, 0.8, 1.0),
    "세라믹파이버": (6, 10, 13, 15, 25),
}
# 무른 재료는 전단이 아니라 칼로 재단하고 규격대로 온다 — 트림 여유가 없다.
NO_TRIM = ("미네랄울", "AL반사판", "세라믹파이버", "GFRP")
PLATE_TRIM = 20                         # 판 재단 여유 (사방)


class Cut(NamedTuple):
    """정척 한 본에 어떻게 배치했는가."""
    stock: float
    pieces: tuple
    used: float

    @property
    def waste(self) -> float:
        return self.stock - self.used


def pack_bars(lengths: list[float], stock: tuple[int, ...]) -> list[Cut]:
    """1차원 절단 배치 — 긴 것부터 넣는 FFD.

    최적해는 아니지만 실무에서 쓰는 방법이고, **실제로 배치를 푼다**는 점이
    중요하다. 총 길이를 정척으로 나누면 잔재를 세지 못하고, 4,550 짜리를
    6 m 정척에 두 개 넣을 수 있다고 착각한다.

    정척은 긴 것부터 시도하되, 조각 하나가 짧은 정척에 들어가면 짧은 쪽을
    쓴다 — 12 m 를 사서 2 m 만 쓰면 나머지는 창고 자리만 차지한다.
    """
    items = sorted((L + CUT_KERF for L in lengths), reverse=True)
    if not items:
        return []
    usable = {s: s - BAR_TRIM for s in stock}
    longest = items[0]
    ok = [s for s in stock if usable[s] >= longest]
    if not ok:
        return []                        # 정척보다 긴 조각 — 호출자가 처리한다
    # 가장 짧은 정척으로도 최장 조각이 들어가면 그것을 기본으로 쓴다
    base = min(ok)
    bins: list[list[float]] = []
    for it in items:
        for b in bins:
            if sum(b) + it <= usable[base]:
                b.append(it)
                break
        else:
            bins.append([it])
    return [Cut(base, tuple(b), sum(b)) for b in bins]


def fit_plate(L: float, W: float, mat: str) -> tuple[tuple | None, int]:
    """한 장의 시트에서 이 판이 몇 개 나오는가. (시트, 개수) — 안 되면 (None, 0).

    직교 격자로만 센다(길로틴 재단). 실제 네스팅은 제작사가 더 잘 뽑지만,
    **몇 장을 사야 하는가**의 하한을 정직하게 내는 데는 이것으로 충분하다.
    """
    trim = 0 if mat in NO_TRIM else PLATE_TRIM
    need_L, need_W = L + 2 * trim, W + 2 * trim
    best, best_n = None, 0
    for sw, sl in PLATE_STOCK.get(mat, ()):
        for a, b in ((need_L, need_W), (need_W, need_L)):
            if a <= sl and b <= sw:
                n = int(sl // a) * int(sw // b)
                if n > best_n:
                    best, best_n = (sw, sl), n
    return best, best_n


# ── 2. 자재 발주표 ─────────────────────────────────────────────────────
class BarLot(NamedTuple):
    mat: str
    kind: str
    section: str
    pieces: tuple          # ((길이, 수량, 품번), …)
    cuts: list             # Cut 목록
    kg_net: float          # 부품 질량 합
    oversize: tuple        # 정척보다 긴 조각의 품번

    @property
    def bars(self) -> int:
        return len(self.cuts)

    @property
    def stock_len(self) -> float:
        return self.cuts[0].stock if self.cuts else 0

    @property
    def bought_mm(self) -> float:
        return sum(c.stock for c in self.cuts)

    @property
    def waste_pct(self) -> float:
        if not self.bought_mm:
            return 0.0
        used = sum(L * q for L, q, _ in self.pieces)
        return (self.bought_mm - used) / self.bought_mm


class PlateLot(NamedTuple):
    mat: str
    t: float
    pieces: tuple          # ((L, W, 수량, 품번), …)
    sheet: tuple | None
    sheets: int
    area_net: float        # m² — 부품 면적 합
    kg_net: float
    unbuyable: tuple       # 어떤 시트에도 안 들어가는 품번


def _section_of(p) -> str:
    return p.shape.label().split(" · L ")[0]


def bar_lots() -> list[BarLot]:
    """선형재를 재질 × 단면으로 묶고 절단 배치를 푼다."""
    groups: dict[tuple, list] = {}
    for p in PT.P:
        if p.buy or p.shape.kind not in ("HB", "BOX", "ANG", "CH", "SQB", "TU", "RB"):
            continue
        g = p.shape.d
        L = g.get("L")
        if p.shape.kind == "RB" and g.get("steps"):
            L = sum(s[1] for s in g["steps"])       # 단차축은 소재 전장으로 산다
        groups.setdefault((p.mat, p.shape.kind, _section_of(p)), []).append((L, p.qty, p))

    out = []
    for (mat, kind, sec), rows in sorted(groups.items()):
        small = kind in ("SQB", "RB") or max(L for L, _, _ in rows) <= 4000
        stock = BAR_STOCK_SMALL if small else BAR_STOCK
        lengths = [L for L, q, _ in rows for _ in range(q)]
        over = tuple(p.pid for L, _, p in rows if L + CUT_KERF > max(stock) - BAR_TRIM)
        cuts = pack_bars([L for L in lengths if L + CUT_KERF <= max(stock) - BAR_TRIM], stock)
        out.append(BarLot(mat, kind, sec,
                          tuple((L, q, p.pid) for L, q, p in rows), cuts,
                          sum(p.kg * q for _, q, p in rows), over))
    return out


def plate_lots() -> list[PlateLot]:
    """판재를 재질 × 두께로 묶고 시트 매수를 낸다."""
    groups: dict[tuple, list] = {}
    for p in PT.P:
        if p.buy or p.shape.kind not in ("PL", "SLAB"):
            continue
        g = p.shape.d
        groups.setdefault((p.mat, g["t"]), []).append((g["L"], g["W"], p.qty, p))

    out = []
    for (mat, t), rows in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        sheets, sheet, bad = 0.0, None, []
        for L, W, q, p in rows:
            sh, per = fit_plate(L, W, mat)
            if per == 0:
                bad.append(p.pid)
                continue
            sheet = sheet or sh
            sheets += q / per
        out.append(PlateLot(mat, t,
                            tuple((L, W, q, p.pid) for L, W, q, p in rows),
                            sheet, math.ceil(sheets),
                            sum(L * W * q for L, W, q, _ in rows) / 1e6,
                            sum(p.kg * q for _, _, q, p in rows), tuple(bad)))
    return out


def unbuyable() -> list[tuple[str, str, str]]:
    """살 수 없는 치수 — (품번, 무엇, 왜). 하나라도 있으면 제작이 멈춘다."""
    out = []
    for lot in bar_lots():
        for pid in lot.oversize:
            out.append((pid, f"{lot.section}", f"정척 {max(BAR_STOCK):,} mm 보다 길다 — 이음 또는 특주"))
    for lot in plate_lots():
        avail = PLATE_THICK.get(lot.mat)
        if avail and lot.t not in avail:
            near = min(avail, key=lambda x: abs(x - lot.t))
            for _L, _W, _q, pid in lot.pieces:
                out.append((pid, f"{lot.mat} t{lot.t:g}",
                            f"유통 두께가 아니다 — 가장 가까운 재고는 t{near:g}"))
        for pid in lot.unbuyable:
            p = [x for x in PT.P if x.pid == pid][0]
            g = p.shape.d
            has = PLATE_STOCK.get(lot.mat)
            biggest = max(has, key=lambda s: s[0] * s[1]) if has else None
            why = (f"{lot.mat} 최대 시트 {biggest[0]:,}×{biggest[1]:,} 을 넘는다"
                   if biggest else f"{lot.mat} 의 유통 시트 규격이 등록되지 않았다")
            out.append((pid, f"PL {g['t']}t · {g['L']:,.0f}×{g['W']:,.0f}", why))
    return out


# ── 3. 운반 분할 ───────────────────────────────────────────────────────
# 세우는 순서가 곧 도착 순서다. 나중에 세울 것이 먼저 오면 현장에 둘 자리가
# 없고, 그것을 옮기느라 크레인을 두 번 부른다.
class Truck(NamedTuple):
    name: str
    L: int
    W: int
    H: int
    kg: int


TRUCKS = (
    Truck("5 t 카고", 4300, 1800, 1900, 5000),
    Truck("11 t 카고", 6200, 2350, 2400, 11000),
    Truck("25 t 트레일러", 12000, 2400, 2600, 25000),
)
# 도로법 제한 — 넘으면 운행 허가와 유도차가 필요하다
ROAD_LIMIT = dict(L=16700, W=2500, H=4000, kg=40000)

# 세우는 순서 (모듈 → 차수). 조립 지침서의 7 단계와 같은 순서다.
ERECT_STAGE = {
    "M-002": 2, "M-007": 2, "M-004": 2, "M-005": 2,
    "M-003": 3,
    "M-006": 4, "M-008": 4, "M-009": 4,
    "M-011": 5, "M-012": 5,
    "M-017": 6,
    "M-013": 7,
    "M-001": 3,
}
STAGE_NAME = {2: "무거운 골조", 3: "이송·투입", 4: "후단 설비",
              5: "유틸리티", 6: "경계", 7: "방책"}


class Load(NamedTuple):
    seq: int
    stage: int
    truck: Truck
    items: tuple           # ((품번, 명칭, 수량, kg, 최장변), …)
    kg: float
    special: str           # 특수운송 사유 — 없으면 ''


def _longest(p) -> float:
    return max(p.shape.bbox())


LOAD_MARGIN = 0.90       # 적재 여유 — 결박·받침목과 계근 오차를 남긴다


def truck_loads() -> list[Load]:
    """차수별로 부재를 차량에 싣는다.

    남은 짐 가운데 **가장 긴 것이 차량을 정하고, 그 차를 채운다.** 길이
    등급으로 먼저 갈라 실으면 7.5 m 빔 하나를 트레일러에 태워 보내면서
    같은 차수의 다른 짐은 카고로 따로 보내게 된다 — 이미 부른 차를 비워
    보내는 것이다.

    적재 한도는 정격의 90 % 다. 정격을 꽉 채워 계획하면 결박구·받침목
    무게와 계근 오차에서 초과가 난다.
    """
    loads: list[Load] = []
    seq = 0
    for stage in sorted(set(ERECT_STAGE.values())):
        mods = [m for m, s in ERECT_STAGE.items() if s == stage]
        rest = [(p.pid, p.name, p.qty, p.total_kg, _longest(p))
                for p in PT.P if p.mod in mods]
        rest.sort(key=lambda r: (-r[4], -r[3]))
        while rest:
            longest = rest[0][4]
            fit = [t for t in TRUCKS if t.L >= longest]
            truck = fit[0] if fit else TRUCKS[-1]
            cap = truck.kg * LOAD_MARGIN
            load, mass = [], 0.0
            for it in list(rest):
                if it[4] <= truck.L and mass + it[3] <= cap:
                    load.append(it)
                    mass += it[3]
                    rest.remove(it)
            if not load:                     # 한 품목이 정격을 넘는다
                load, mass = [rest.pop(0)], rest and 0 or 0
                mass = load[0][3]
            seq += 1
            sp = ""
            if not fit:
                sp = (f"전장 {longest:,.0f} — 운행 허가 (도로법 {ROAD_LIMIT['L']:,} 이내)"
                      if longest <= ROAD_LIMIT["L"] else
                      f"전장 {longest:,.0f} — 도로법 한도 초과, 분할 필요")
            elif mass > truck.kg:
                sp = f"적재 {mass:,.0f} kg 이 정격을 넘는다 — 분할"
            loads.append(Load(seq, stage, truck, tuple(load), mass, sp))
    return loads


# ── 4. 구매품 사양 ─────────────────────────────────────────────────────
# 카탈로그의 구매품은 외형과 한 줄 규격만 든다. 발주하려면 계통·정격·
# 인터페이스·검사가 있어야 하고, 그것이 없으면 구매 담당이 임의로 고른다.
#
# (품번, 계통, 정격·성능, 인터페이스, 승인·검사)
SYS = ("기계", "전기", "공압", "계장", "안전", "구조")

BUY_SPEC: dict[str, tuple[str, str, str, str]] = {
    # ── M-001
    "P-001-06": ("기계", "V홈 캠폴로워 Ø40 · 정격 2.0 kN/개", "M10 볼트 4 · 편심축 조정", "재질 성적서"),
    "P-001-08": ("공압", "복동 Ø40 · 행정 500 · 0.5 MPa", "G1/8 포트 2 · 클레비스 Ø16", "행정·속도 시운전"),
    "P-001-09": ("계장", "2D 코드 리더 · 초점 120 mm · Ethernet/IP", "M12 4핀 · DC24V", "판독률 10/10 실증"),
    "P-001-11": ("계장", "반사형 광전 · 검출 500 mm · PNP", "M8 3핀 · DC24V", "오검출 0 실증"),
    # ── M-002
    "P-002-18": ("전기", "단파장 IR 2.5 kW · 230 V · 석영관", "세라믹 소켓 압입 · 내열 리드",
                 "40등 점등 · 절연저항 ≥ 5 MΩ"),
    "P-002-19": ("전기", "세라믹 소켓 · 250 ℃ · 실리콘 리드 200 ℃", "M4 2 · 압착단자", "내열 성적서"),
    "P-002-25": ("기계", "섬유충전 세라믹 부시 Ø45 · k ≤ 0.9 W/(m·K) · 400 ℃ · "
                 "파이버 로프 패킹 (잔여 누설 ≤ 10 mm²/개소)",
                 "내피–단열–외피 관통 압축 · 한쪽 유동단 행정 10",
                 "내열·기밀 시험 성적서 · 열전도율 성적서"),
    "P-002-22": ("공압", "복동 Ø63 · 행정 900 · 속도제어 양방향", "G1/4 포트 2 · M12 4",
                 "개폐 ≤ 3 s 실증"),
    "P-002-23": ("계장", "K형 시스 열전대 Ø3 · 0~600 ℃ · 등급 1", "압축피팅 M8 · 보상도선",
                 "10점 편차 ≤ 3 ℃"),
    # ── M-003
    "P-003-07": ("기계", "볼스크류 Ø32 리드 10 · C5급 · 예압", "지지베어링 유닛 · 커플링",
                 "흔들림 ≤ 0.05 · 성적서"),
    "P-003-08": ("기계", "지지베어링 유닛 (고정측/지지측)", "M8 4", "예압 확인"),
    "P-003-09": ("전기", "서보 1.5 kW · 무여자 브레이크 · 절대치", "M10 4 · 동력/엔코더 커넥터",
                 "2축 동기 ≤ 0.5 mm 실증"),
    "P-003-10": ("기계", "LM 레일 사이즈 25 · 프리로드 C1", "M6 @80 · 기준면 밀착", "직진도 성적서"),
    "P-003-11": ("기계", "LM 블록 사이즈 25 · 프리로드 C1", "M6 4", "예압 확인"),
    "P-003-14": ("기계", "2단 텔레스코픽 포크 · 인출 2,610 · 적재 200 kg", "M12 8 · 낙하방지 밸브",
                 "인출 ±3 · 처짐 ≤ 3 mm 실증"),
    "P-003-16": ("전기", "다회전 절대치 엔코더 · 배터리리스", "M4 4 · 시리얼", "정전 후 원점 유지 실증"),
    "P-003-17": ("안전", "안전등급 위치스위치 · PL d · 강제개리 접점", "M5 2 · 2채널",
                 "기능시험 · 인증서"),
    # ── M-004
    "P-004-08": ("기계", "NBR 벨로우즈 패드 Ø250 · 내열 120 ℃", "G1/4 니플", "18점 동일 평면 ≤ 0.3"),
    "P-004-10": ("공압", "진공 존 밸브 + 체크밸브 · Cv 1.0", "G1/4", "존별 차단 실증"),
    "P-004-11": ("계장", "진공 압력센서 −100~0 kPa · 아날로그", "G1/8 · M8 4핀",
                 "−65 kPa 판정 · 교정 성적서"),
    "P-004-12": ("공압", "진공 필터 5 µm · 교체형 엘리먼트", "G1/4", "차압 경보 설정"),
    # ── M-005
    "P-005-05": ("기계", "LM 주행레일 사이즈 45 · 프리로드 · 정격수명 20,000 h",
                 "M12 @105 · 연삭 기준면", "직진도 0.1/1,000 성적서"),
    "P-005-06": ("기계", "LM 블록 사이즈 45 · 프리로드", "M12 4 · **마찰접합**",
                 "접합면 Sa 2½ · 도장 금지"),
    "P-005-09": ("기계", "경화 랙 모듈 3 · 백래시 ≤ 0.05", "M10 @100", "백래시 실측"),
    "P-005-10": ("전기", "서보 + 유성감속 · 백래시 ≤ 3′", "M12 4 · 편심 부시 조정",
                 "위치결정 ±0.1 실증"),
    "P-005-12": ("기계", "볼스크류 Ø32 리드 10 · 무여자 브레이크", "지지베어링 유닛", "흔들림 ≤ 0.05"),
    "P-005-13": ("기계", "LM 가이드 사이즈 25 · 프리로드 C1", "M6 @80", "직진도 성적서"),
    "P-005-16": ("전기", "카트리지 히터 Ø12 · 200 W · 400 ℃", "압입 + 세트스크류 · 내열 리드",
                 "12본 승온 · 편차 ≤ 5 ℃"),
    "P-005-19": ("공압", "쐐기 클램프 15 kN · 공압 작동", "M12 4 · G1/8",
                 "**밀착·열전달 전용 — 전단은 핀이 받는다**"),
    "P-005-21": ("기계", "자동조심 볼베어링 필로우블록", "M12 4", "회전 무저항"),
    "P-005-22": ("계장", "로드셀 0~20 kN · 압축형", "M12 · 4선식", "교정 성적서 (OI-01 실측용)"),
    # ── M-006
    "P-006-08": ("기계", "SN-510 상당 자동조심 볼베어링 · 그리스", "M16 4", "축 흔들림 ≤ 0.03"),
    "P-006-09": ("전기", "토크서보 2.2 kW · 장력제어 · 직경 추종", "M12 4 · 커플링",
                 "장력 지령 추종 실증"),
    "P-006-10": ("계장", "레이저 거리센서 100~600 mm · 아날로그", "M5 2 · M12 4핀", "권경 추종 실증"),
    "P-006-14": ("계장", "로드셀 0~2 kN · 인장형", "M10 · 4선식", "0점 조정 · 교정 성적서"),
    "P-006-15": ("계장", "투과형 광전 · 응답 ≤ 1 ms", "M4 2 · M8 3핀", "웹 파단 → 즉시 정지 실증"),
    "P-006-20": ("기계", "수동 트롤리 + 전동 호이스트 정격 1 t · 인양 5 m",
                 "런웨이 하부 플랜지 물림", "**정격 하중시험 · 검사증**"),
    # ── M-007
    "P-007-08": ("기계", "G4 프리필터 600×600×48 · 교체형", "프레임 슬라이드 + 클립", "초기 차압 기록"),
    "P-007-09": ("전기", "축류 팬 Ø520 · 8극 · 0.55 kW", "M10 4 + 방진고무 · 3상 400 V",
                 "풍량 실측 · 진동 ≤ 4.5 mm/s"),
    "P-007-11": ("계장", "비접촉 IR 온도계 0~200 ℃ · 아날로그", "M5 2 · M12 4핀",
                 "흑체 대조 편차 ≤ 3 ℃"),
    # ── M-008
    "P-008-05": ("기계", "롤러 베어링 하우징 · 그리스 봉입", "M8 2", "회전 무저항"),
    "P-008-06": ("전기", "기어모터 0.4 kW · 인버터 구동", "M10 4 · 3상 400 V", "속도 가변 실증"),
    "P-008-07": ("기계", "롤러체인 RS50 + 스프라켓 · 장력 아이들러", "축단 키 고정", "처짐 10~15 mm"),
    "P-008-10": ("기계", "캐스터 Ø150 · 브레이크 2 / 자유 2 · 정격 200 kg/개", "M12 4", "4점 접지 확인"),
    "P-008-11": ("계장", "광전 · 유리 존재·겹침 검출", "M4 2 · M8 3핀", "겹침 판정 10/10"),
    # ── M-009
    "P-009-04": ("계장", "라인스캔 카메라 4K · GigE Vision", "M4 4 · PoE",
                 "잔막 0.2 mm 판독 실증"),
    "P-009-05": ("전기", "LED 라인조명 1,300 mm · 투과/반사 2조", "M6 4 · DC24V 조광",
                 "조도 균일도 ≥ 80 %"),
    "P-009-09": ("계장", "만재 검출 광전", "M4 2 · M8 3핀", "만재 → 정지 실증"),
    # ── M-011
    "P-011-01": ("전기", "MCC IP54 · 주회로 400 AF/400 AT · 3Φ4W 380/220 V",
                 "베이스 채널 M12 4 · 케이블 하부 인입",
                 "**승인도 제출 · 절연내력 · 시퀀스 시험**"),
    "P-011-02": ("전기", "안전 PLC + 원격 I/O · UPS 이중전원 · IP54",
                 "베이스 채널 M12 4 · 광/동 통신",
                 "**승인도 제출 · I/O 도통 · 인터록 기능시험**"),
    "P-011-04": ("전기", "케이블 트레이 300×100 · 아연도금 · 2단(동력/제어)",
                 "행거 M8 2 @1,500", "접지 본딩 도통"),
    # ── M-012
    "P-012-04": ("기계", "드라이 스크류 진공펌프 · 도달 −95 kPa · 2대(1 예비)",
                 "M12 4 + 방진고무 · 3상 400 V",
                 "**1대 운전으로 −65 kPa 도달 실증**"),
    "P-012-09": ("공압", "필터·레귤레이터 0.6 MPa · 자동 드레인", "M8 4 · Rc1/2", "누설 0"),
    "P-012-10": ("공압", "공기 리시버 400 L · 안전밸브 · 압력용기 등록",
                 "M12 4 · Rc1", "**압력용기 검사증**"),
    # ── M-013
    "P-013-06": ("안전", "코드화 인터록 스위치 (텅) · PL d · 2채널",
                 "M5 4 · 안전회로 배선", "**문 열림 → 정지 실증 · 인증서**"),
    "P-013-07": ("안전", "라이트커튼 분해능 30 mm · 보호높이 2,000 · Type 4 · 뮤팅",
                 "전용 브래킷 M6 4 · 안전회로",
                 "**차광 시험 Ø30 · 응답 ≤ 30 ms · 인증서**"),
    "P-013-09": ("안전", "비상정지 버튼 ISO 13850 · 유지형·해제 회전 · 강제개리 2채널", "M6 4",
                 "**인증서 · 4개소 전부 정지 실증 · 복귀 요구 확인**"),
    "P-013-10": ("전기", "적·황·녹 신호탑 + 부저 85 dB · DC24V", "M6 3", "상태별 표시 실증"),
    # ── M-017
    "P-017-04": ("전기", "경계 단자반 IP54 · 단자 번호 도면 일치", "M10 4 · 하부 인입",
                 "**단자 번호 대조 · 도통 시험**"),
    "P-017-05": ("공압", "경계 배관반 · 계통별 차단밸브 · 압력계", "M10 4 · Rc1/2",
                 "**차단밸브 작동 · 기밀 시험**"),
}

# 예비품 — 소모품과 정지시간이 큰 것만 든다. 전부 예비를 두면 창고가 공장이 된다.
SPARES = {
    "P-002-18": "IR 램프 40등의 10 % = 4등",
    "P-005-15": "SKD11 인서트 2벌 (소모품 — 교체 전제)",
    "P-005-16": "카트리지 히터 2본",
    "P-007-08": "G4 프리필터 12매 1회분",
    "P-004-08": "흡착패드 4개",
    "P-012-04": "진공펌프 실 킷 1벌",
    "P-013-07": "라이트커튼 1조 (안전정지가 곧 생산정지다)",
}


def buy_rows():
    """(부품, 계통, 정격, 인터페이스, 검사, 예비품) — 구매품 전 종."""
    out = []
    for p in PT.P:
        if not p.buy:
            continue
        sys_, rating, iface, insp = BUY_SPEC.get(
            p.pid, ("기계", p.note, p.fix, "육안 · 수량 확인"))
        out.append((p, sys_, rating, iface, insp, SPARES.get(p.pid, "")))
    return out


# ── 5. 리포트 ──────────────────────────────────────────────────────────
def report() -> str:
    L, add = [], None
    L = []
    add = L.append
    add("=" * 78)
    add("DG-HK60C 조달 계산 — 자재 · 운반 · 구매")
    add("=" * 78)

    bad = unbuyable()
    add("")
    add("── ① 살 수 없는 치수 ────────────────────────────────────")
    if not bad:
        add("   없음 — 전 부재가 유통 규격 안에 든다")
    else:
        for pid, what, why in bad:
            add(f"   ★ {pid}  {what}")
            add(f"       {why}")

    bl, pl = bar_lots(), plate_lots()
    add("")
    add("── ② 형강·강관·봉 발주 ──────────────────────────────────")
    add(f"   {'재질':9s} {'단면':30s} {'정척':>7s} {'본수':>4s} {'손실':>6s} {'순중량':>8s}")
    for lot in bl:
        add(f"   {lot.mat:9s} {lot.section[:30]:30s} {lot.stock_len:7,.0f} "
            f"{lot.bars:4d} {lot.waste_pct:5.0%} {lot.kg_net:8,.0f}")
    add(f"   합계 정척 {sum(l.bars for l in bl)} 본 · 순중량 {sum(l.kg_net for l in bl):,.0f} kg")

    add("")
    add("── ③ 판재 발주 ─────────────────────────────────────────")
    add(f"   {'재질':9s} {'두께':>6s} {'시트':>13s} {'매수':>4s} {'순면적':>8s} {'순중량':>8s}")
    for lot in pl:
        sh = f"{lot.sheet[0]:,}×{lot.sheet[1]:,}" if lot.sheet else "—"
        add(f"   {lot.mat:9s} {lot.t:5.1f}t {sh:>13s} {lot.sheets:4d} "
            f"{lot.area_net:7.2f}㎡ {lot.kg_net:8,.0f}")
    add(f"   합계 시트 {sum(l.sheets for l in pl)} 매 · 순중량 {sum(l.kg_net for l in pl):,.0f} kg")

    lo = truck_loads()
    add("")
    add("── ④ 운반 분할 ─────────────────────────────────────────")
    add(f"   {'차수':>4s} {'단계':16s} {'차량':12s} {'품목':>4s} {'적재 kg':>9s}  비고")
    for x in lo:
        add(f"   {x.seq:4d} {STAGE_NAME[x.stage]:16s} {x.truck.name:12s} "
            f"{len(x.items):4d} {x.kg:9,.0f}  {x.special}")
    add(f"   합계 {len(lo)} 차 · {sum(x.kg for x in lo):,.0f} kg")

    br = buy_rows()
    add("")
    add("── ⑤ 구매품 ────────────────────────────────────────────")
    by: dict[str, int] = {}
    for _p, s, *_ in br:
        by[s] = by.get(s, 0) + 1
    for s, n in sorted(by.items(), key=lambda kv: -kv[1]):
        add(f"   {s:6s} {n:3d} 종")
    miss = [p.pid for p, *_ in br if p.pid not in BUY_SPEC]
    add(f"   발주 사양 기재 {len(br) - len(miss)} / {len(br)} 종")
    if miss:
        add(f"   ★ 사양 미기재: {', '.join(miss[:12])}{' …' if len(miss) > 12 else ''}")

    add("")
    add("=" * 78)
    add("살 수 없는 치수 없음" if not bad else f"★ 살 수 없는 치수 {len(bad)} 건 — 제작 착수 전에 푼다")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
