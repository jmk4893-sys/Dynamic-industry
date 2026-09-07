"""후단 유리제거기 DG-HK60C — **원본에서 읽는다, 옮겨 적지 않는다.**

REV.53 까지 플랜트의 후단은 GRM-401 이었다. 외부 "DG-HK 2400 Rev.10 앱" 의
계산모델을 `handoff.py` 에 손으로 옮겨 놓은 계획값 셀이었고, 그 모듈 첫머리에
"그 앱이 바뀌면 여기도 같이 고쳐야 한다" 고 적혀 있었다. 옮겨 적은 값은 반드시
갈라진다 — 이 저장소가 존 격자(§49)와 이송면(§48)에서 이미 겪은 일이다.

REV.54 에서 후단은 같은 저장소 안에 사양서·콘솔·부품 카탈로그·PLC 모델을 갖는
**DG-HK60C** 가 됐다. 그러므로 플랜트 모델은 그 기계의 값을 여기서 **읽는다**:

* 처리율·사이클·단수·램프 수·패널 범위·공정선 높이·스테이션 좌표·방책·전력
  분기 — `docs/drawings/pv-delamination-3d.html` 의 상수 (`tools/console_consts.py`
  로 푼다. 콘솔이 곧 그 기계의 단일 출처다).
* 모듈 질량 — `tools/parts.py` 부품 카탈로그.
* 경계 신호 — `tools/plc_model.py` 의 경계 인터페이스반 BJ-101/102 항목.
* 보증·범위 문구 — `docs/dg-hk60-rfq.html` (숫자는 정규식으로 뽑고 시험이 대조).

여기 적힌 리터럴은 **플랜트 안에 설치할 때 정하는 것**뿐이다 — 어느 면을 통로에
두는가, 브리지가 어디서 어디까지 가는가. 기계의 값을 여기 적으면 REV.53 의
handoff.py 로 돌아가는 것이다.

좌표 규약: 기계 좌표 (x 공정방향 · y 좌측 + · z 상향, m) 은 콘솔 그대로이고,
플랜트 좌표로 옮기는 식은 `plant_x_mm()` / `plant_y_mm()` 하나뿐이다.
"""

from __future__ import annotations

import importlib.util
import math
import pathlib
import re
import sys
from dataclasses import dataclass
from functools import lru_cache

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"
RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
ASSEMBLY = ROOT / "docs" / "dg-hk60-assembly.html"
TOOLS = ROOT / "tools"

MODEL = "DG-HK60C"
#: 플랜트 태그 — 존 키는 공정(`grm` · 유리제거)이고, 태그는 그 자리에 선 기계다.
TAG = "DGM-401"


def _tool(name: str):
    """`tools/` 의 모듈을 패키지 밖에서 읽는다 — 그 기계의 단일 출처가 거기 있다."""
    if name in sys.modules:
        return sys.modules[name]
    if str(TOOLS) not in sys.path:          # parts.py 가 fab_spec 을 이웃에서 import 한다
        sys.path.append(str(TOOLS))
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def _console_text() -> str:
    return CONSOLE.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _env() -> dict[str, float]:
    return _tool("console_consts").env(_console_text())


def const(name: str) -> float:
    """콘솔 숫자 상수 하나. 없으면 KeyError — 조용히 0 이 되지 않는다."""
    return _env()[name]


def _obj(name: str) -> dict:
    return _tool("console_consts").obj(name, _console_text())


def _str_field(owner: str, key: str) -> str:
    """`const OWNER={…key:'값'…}` 의 문자열 필드 — console_consts.obj 는 숫자만 편다."""
    body = _console_text()
    m = re.search(r"const %s\s*=\s*\{(.*?)\};" % re.escape(owner), body, re.S)
    if m is None:
        raise KeyError(owner)
    f = re.search(r"\b%s\s*:\s*'([^']*)'" % re.escape(key), m.group(1))
    if f is None:
        raise KeyError(f"{owner}.{key}")
    return f.group(1)


def _rfq_text() -> str:
    return re.sub(r"<[^>]+>", " ", RFQ.read_text(encoding="utf-8"))


# ── 기계 자체 — 콘솔이 정한 값 ────────────────────────────────────────────
_hk = _obj("HK60C")
REV = _str_field("HK60C", "rev")                     # 'REV.21C'
PLAN = _str_field("HK60C", "plan")                   # '압축 배치'

#: 순생산 (장/h) 과 라인 사이클 (s). 콘솔 `HK60C.rate / .cycle` 은 REV.21C 까지 리터럴
#: (60.5 / 53.6)이었고, 포락선 2,500×1,400 개정부터 `CYC.knifeLineRate × MODEL.availability`
#: 로 **계산**된다 — 그래서 여기서도 같은 식(`rate()`)으로 낸다. 값은 아래 `RATE_PER_H`
#: 정의 뒤에서 채운다(식이 상수들을 다 읽은 뒤에야 돌 수 있다).
#: 순생산 = 명목(3600/사이클) × 가동률 — 가동률 0.90 은 칼날 카세트 교환·만권
#: 롤 반출 같은 **계획 정지 예산(시간당 360 s)** 이지 고장이 아니다. 고장은
#: 플랜트 신뢰도 모델(`reliability.py` RB-GRM)이 따로 센다.
DECKS: int = int(const("DECKS"))
LAMPS: int = int(const("LAMPS"))

_calc = _obj("MODEL_DEFAULT")
#: 콘솔 계산기의 기본 입력 — 사양서 4.1/5.2 가 같은 값으로 처리량을 유도한다.
LAMP_KW: float = _calc["lampPower"]                  # 2.5
HEAT_EFFICIENCY_PCT: float = _calc["heatEfficiency"]  # 65
KNIFE_SPEED_MM_S: float = _calc["knifeSpeed"]        # 55 — 생산보증 (60 은 FAT 상한)
RAPID_SPEED_MM_S: float = _calc["rapidSpeed"]        # 200
HANDLING_S: float = _calc["handlingTime"]            # 3.0 고정동작
KNIFE_RETURN_MM_S: float = _calc["knifeReturnSpeed"]  # 700

_model = re.search(r"const MODEL\s*=\s*\{(.*?)\};", _console_text(), re.S).group(1)


def _model_field(key: str) -> float:
    m = re.search(r"\b%s\s*:\s*([\d.]+)" % key, _model)
    if m is None:
        raise KeyError(key)
    return float(m.group(1))


AREAL_CP_KJ_M2K: float = _model_field("arealCp")     # 8.7358962
FDM_DWELL_S: float = _model_field("fdmDwell")        # 113.15 — 백시트가 정하는 하한
KNIFE_PITCH_MM: float = _model_field("knifePitch")   # 300 칼끝 간격
RAPID_DISTANCE_MM: float = _model_field("rapidDistance")  # 300
AVAILABILITY: float = _model_field("availability")   # 0.90
#: 계약 순생산 — 포락선 개정부터 콘솔 최상단 `NET_TARGET`(정수)이고, 그 전에는 MODEL.netTarget 이었다.
NET_TARGET_PER_H: float = (const("NET_TARGET") if "NET_TARGET" in _env()
                           else _model_field("netTarget"))   # 58 (2,500×1,400) · 60 (REV.21C)
T_TARGET_C: float = const("T_TARGET")                # 140 계면
T_AMB_C: float = const("T_AMB")                      # 25
IR_INSTALLED_KW: float = LAMPS * LAMP_KW             # 100

# ── 패널 ──────────────────────────────────────────────────────────────────
#: 투입 상한 (mm) — 콘솔 `PANEL_L/W`. 사양서 4.2 의 범위와 같아야 한다.
PANEL_MAX_MM: tuple[int, int] = (round(const("PANEL_L") * 1000), round(const("PANEL_W") * 1000))
#: 투입 하한 — 콘솔 계산기 범위 `panelLength:[1600,…],panelWidth:[800,…]` 의 하한. 상한은
#: 포락선 개정부터 `PANEL_L*1000` 식이라 여기서 안 읽는다(위 PANEL_MAX_MM 이 정본).
_range = re.search(r"panelLength:\[(\d+),[^\]]*\],panelWidth:\[(\d+),[^\]]*\]", _console_text())
PANEL_MIN_MM: tuple[int, int] = (int(_range.group(1)), int(_range.group(2)))
PANEL_MASS_KG: float = round(const("PANEL_MASS"), 2)     # 28.21
GLASS_KG: float = round(const("GLASS_KG"), 2)            # 23.04
CELL_EVA_KG: float = round(const("CE_KG"), 2)            # 3.96
POSE = "유리면 ↓ · 백시트 ↑"                              # 사양서 4.2 '유리면 아래 · 백시트 위'

# ── 기하 — 스테이션·공정선·방책 (기계 좌표 mm) ─────────────────────────────
LINE_EL_MM: int = round(const("CZ") * 1000)              # 1,150 — 다섯 스테이션 공통
CL_CLEAR_MM: int = round(const("CL_CLEAR") * 1000)       # 300
CL_END_MM: int = round(const("CL_END") * 1000)           # 300


@dataclass(frozen=True)
class Station:
    key: str        # 'LD' | 'HC' | 'DL' | 'GC' | 'UL'
    tag: str        # 'LD-101' …
    name: str
    x0_mm: int
    x1_mm: int

    @property
    def cx_mm(self) -> int:
        return (self.x0_mm + self.x1_mm) // 2

    @property
    def length_mm(self) -> int:
        return self.x1_mm - self.x0_mm


def _stations() -> tuple[Station, ...]:
    """콘솔의 COMPACT_STATIONS 를 공정 순서로 이어 붙인다 — 콘솔 `CST` 와 같은 식."""
    cc = _tool("console_consts")
    body = re.search(r"const COMPACT_STATIONS=\[(.*?)\];", _console_text(), re.S).group(1)
    rows = re.findall(r"\['([A-Z]{2}-\d{3})',\s*(?:`[^`]*`|'[^']*'),\s*([^,]+),", body)
    out, cur = [], CL_END_MM
    for tag, expr in rows:
        width = cc.value(expr, _env())
        if width is None:
            raise ValueError(f"{tag} 폭 식을 못 푼다: {expr}")
        w = round(width * 1000)
        name = {"LD": "투입 셔틀", "HC": f"{DECKS}단 밀폐 가열실", "DL": "탠덤 분리 셀",
                "GC": "유리 냉각 랙", "UL": "반출 셔틀"}[tag[:2]]
        out.append(Station(tag[:2], tag, name, cur, cur + w))
        cur += w + CL_CLEAR_MM
    return tuple(out)


STATIONS: tuple[Station, ...] = _stations()
STATION: dict[str, Station] = {s.key: s for s in STATIONS}
#: 기계 전장 (mm) — 콘솔 `compactLength()`: 스테이션 합 + 간격 + 끝벽 2.
LENGTH_MM: int = STATIONS[-1].x1_mm + CL_END_MM      # 18,760

#: 방책 (기계 좌표 mm). 상류 −900 은 팔레트 픽업 스테이션 자리인데 플랜트에서는
#: 브리지가 그 자리를 대신하므로 **플랜트 존은 x 0 부터** 잡는다.
FENCE_X0_MM: int = round(const("CFENCE_X0") * 1000)                  # −900
FENCE_X1_MM: int = LENGTH_MM + round((const("CFENCE_X1") if "CFENCE_X1" in _env()
                                       else 0.84) * 1000) if "CFENCE_X1" in _env() \
    else LENGTH_MM + 840                                              # 19,600
FENCE_YP_MM: int = round(const("CFENCE_Y") * 1000)                   # +3,400
FENCE_YN_MM: int = round(const("CFENCE_YN") * 1000)                  # −4,200 (카트 레인 쪽)
FENCE_WIDTH_MM: int = FENCE_YP_MM + FENCE_YN_MM                      # 7,600
SKIN_Y_MM: int = round(const("CSKIN_Y") * 1000)                      # ±2,350 외장

#: 납품 모듈 외형표(사양서 3.x) 의 최고 높이 — 존 Z. M-017 경계 인터페이스(배기
#: 헤더 포함) 5,400 이 가장 높다.
_modules = re.findall(r"(M-\d{3})\s+([^\n]*?)\s+(\d{3,5})×(\d{3,5})×(\d{3,5})", _rfq_text())
MODULES: dict[str, tuple[str, tuple[int, int, int]]] = {
    m: (name.strip(), (int(L), int(W), int(H))) for m, name, L, W, H in _modules}
HEIGHT_MM: int = max(h for _, (_, _, h) in MODULES.values())         # 5,400

#: 존 외형 (X, Y, Z) — 플랜트 `layout.Station("grm")` 이 그대로 받는다.
ENVELOPE_MM: tuple[int, int, int] = (FENCE_X1_MM, FENCE_WIDTH_MM, HEIGHT_MM)

# ── 플랜트 안에 놓는 방식 — 여기만 플랜트가 정한다 ─────────────────────────
#: 기계의 −y 면(카트 레인·BJ-101/102·인입점·모노레일 반출)을 **통로 쪽**에 둔다.
#: 플랜트 Y 는 벽(0)에서 통로(장비 밴드 끝)로 커지므로 y 부호가 뒤집힌다.
SERVICE_SIDE_TO_AISLE = True


def plant_x_mm(zone_x0_mm: int, machine_x_mm: float) -> int:
    """기계 x (mm) → 플랜트 X (mm). 기계 x 0 = 존 시작."""
    return round(zone_x0_mm + machine_x_mm)


def plant_y_mm(zone_y0_mm: int, machine_y_mm: float) -> int:
    """기계 y (mm) → 플랜트 Y (mm). +y 방책선이 존 시작(벽쪽)에 붙는다."""
    return round(zone_y0_mm + FENCE_YP_MM - machine_y_mm)


#: 투입 셔틀 LD-101 의 인계면 — 브리지가 유리를 내려놓는 자리 (기계 x mm, EL).
INFEED_X0_MM: int = STATION["LD"].x0_mm                 # 300
INFEED_CX_MM: int = STATION["LD"].cx_mm                 # 1,800
INFEED_EL_MM: int = LINE_EL_MM                          # 1,150

#: 유리 반출 팔레트 픽업 스테이션 — 콘솔 `compactLength()+.34` (기계 x mm).
GLASS_PICKUP_X_MM: int = LENGTH_MM + 340                # 19,100

#: 셀/EVA 카트 CS-201 과 횡인출 CE-201 (기계 좌표 mm).
CE_X_MM: tuple[int, int] = (round(const("CE_X0") * 1000), round(const("CE_X1") * 1000))
CE_EL_MM: int = round(const("CE_Z") * 1000)             # 1,050
_cart = _tool("console_consts")._split_top(
    re.search(r"const CSCART=V\((.*?)\);", _console_text()).group(1))
CART_X_MM: int = (CE_X_MM[0] + CE_X_MM[1]) // 2         # (CE_X0+CE_X1)/2
#: 포락선 개정부터 `V((CE_X0+CE_X1)/2,CSCART_Y,.55)` 처럼 이름·식이라 값으로 푼다.
_cc = _tool("console_consts")
CART_Y_MM: int = round(_cc.value(_cart[1], _env()) * 1000)   # −3,200 (CSCART_Y = CE_Y1 − .30)
CART_L_MM: int = round(const("CSCART_L") * 1000)        # 2,600
CART_W_MM: int = round(const("CSCART_W") * 1000)        # 1,300

#: 백시트 만권 롤·칼날 카세트 반출 — RH-201 모노레일 (기계 좌표).
WINDER_X_MM: int = round(const("CRAIL_X0") * 1000)      # 8,050 드럼·모노레일 x
RH_Y_MM: tuple[int, int] = (round(const("RH_Y0") * 1000), round(const("RH_Y1") * 1000))  # +550 → −7,000
_saddle = _cc._split_top(re.search(r"const BS_SADDLE=V\((.*?)\);", _console_text()).group(1))
ROLL_SADDLE_Y_MM: int = round(_cc.value(_saddle[1], _env()) * 1000)  # −5,200 — 방책 밖
CASSETTE_SADDLE_Y_MM: int = round(const("CKC_RACK_Y") * 1000)  # −7,000


def _deck_z(k: int) -> float:
    return const("CDECK_Z0") + const("CDECK_DZ") * (k + 0.5)


def monorail_el_mm() -> int:
    """RH-201 레일면 EL (mm) — 콘솔 `RH_Z` 식: 두상보 상단 + 트롤리 + 여유, 0.05 올림."""
    need = _deck_z(DECKS - 1) + .73 + .09 + .15 + .34 + const("RH_CLR")
    return round(max(4.85, math.ceil(need * 20) / 20) * 1000)     # 5,100


ROLL_MASS_KG: int = round(const("ROLL_MASS")) if "ROLL_MASS" in _env() else 357
ROLL_PERIOD_H: float = 4.9                                       # 사양서 6.x — OI-11

#: 경계 인터페이스반 BJ-101/102 과 경계 덕트 플랜지 (기계 좌표).
BJ_X_MM: int = STATION["UL"].x1_mm - 1000               # CBJ_X = CST.UL.x1 − 1.0
BJ_Y_MM: int = -2620
DUCT_Y_MM: int = round(const("CDUCT_Y") * 1000)          # +1,880
_flange = re.search(r"덕트 플랜지 EL ([\d,]+)", _rfq_text())
DUCT_FLANGE_EL_MM: int = int(_flange.group(1).replace(",", ""))   # 5,100
DUCT_FLANGE_X_MM: int = FENCE_X1_MM - 520                        # CFENCE_X1 − .52
DUCT_FLANGE_DN_MM: int = 600

# ── 전력 — 콘솔 부하표 4 분기 ─────────────────────────────────────────────


@dataclass(frozen=True)
class Branch:
    tag: str
    load: str
    kw: float
    pf: float
    df: float           # 수용률
    mccb: str

    @property
    def demand_kw(self) -> float:
        return round(self.kw * self.df, 2)


def _branches() -> tuple[Branch, ...]:
    cc = _tool("console_consts")
    out = []
    for m in re.finditer(r"id:'([A-Z0-9-]+)',\s*load:(?:`([^`]*)`|'([^']*)'),\s*kW:([^,]+),\s*"
                         r"pf:([\d.]+),\s*df:([\d.]+),\s*mccb:'([^']*)'", _console_text()):
        tag, l1, l2, kw_expr, pf, df, mccb = m.groups()
        kw = cc.value(kw_expr, _env())
        if kw is None:
            raise ValueError(f"{tag} kW 식을 못 푼다: {kw_expr}")
        load = (l1 or l2).replace("${LAMPS}", str(LAMPS))
        out.append(Branch(tag, load, float(kw), float(pf), float(df), mccb))
    return tuple(out)


BRANCHES: tuple[Branch, ...] = _branches()
CONNECTED_KW: float = round(sum(b.kw for b in BRANCHES), 1)          # 193
EXPECTED_DEMAND_KW: float = round(sum(b.demand_kw for b in BRANCHES), 1)  # 137.9
SUPPLY = "3Φ4W AC 380/220 V 60 Hz"


def diversity() -> float:
    """플랜트 피더에 쓰는 수용률 — 기계 자신의 예상 최대수요 / 연결부하."""
    return round(EXPECTED_DEMAND_KW / CONNECTED_KW, 3)


# ── 열 — 콘솔 계산기(사양서 5.1/5.2)를 재현한다 ─────────────────────────────


@dataclass(frozen=True)
class Rate:
    heat_per_panel_mj: float
    dwell_s: float          # 소킹 (5단 만재)
    release_pitch_s: float  # 방출 피치 = 소킹/단수
    thermal_per_h: float
    tandem_cycle_s: float
    tandem_per_h: float     # 명목
    line_per_h: float       # 순생산 = 명목 × 가동률
    bottleneck: str


def rate(length_mm: float | None = None, width_mm: float | None = None,
         knife_speed_mm_s: float | None = None, lamps: int | None = None,
         lamp_kw: float | None = None) -> Rate:
    """사양서 5.1/5.2 의 식. 기본 인자에서 콘솔 `HK60C.rate/cycle` 이 그대로 나와야
    한다 — 시험이 대조한다. 재유도가 아니라 **재현**이다."""
    L = PANEL_MAX_MM[0] if length_mm is None else length_mm
    W = PANEL_MAX_MM[1] if width_mm is None else width_mm
    v = KNIFE_SPEED_MM_S if knife_speed_mm_s is None else knife_speed_mm_s
    heat_kj = (L * W / 1e6) * AREAL_CP_KJ_M2K * (T_TARGET_C - T_AMB_C)
    n_lamp = LAMPS if lamps is None else lamps
    p_lamp = LAMP_KW if lamp_kw is None else lamp_kw
    useful_kw = n_lamp * p_lamp * HEAT_EFFICIENCY_PCT / 100.0
    dwell = max(DECKS * heat_kj / useful_kw, FDM_DWELL_S)
    pitch = dwell / DECKS
    tandem = (KNIFE_PITCH_MM + L) / v + RAPID_DISTANCE_MM / RAPID_SPEED_MM_S + HANDLING_S
    nominal = 3600.0 / max(pitch, tandem)
    return Rate(round(heat_kj / 1000.0, 2), round(dwell, 1), round(pitch, 1),
                round(3600.0 / pitch, 1), round(tandem, 1), round(3600.0 / tandem, 1),
                round(nominal * AVAILABILITY, 1),
                "IR 열공정" if pitch > tandem else "탠덤 박리")


#: 콘솔이 계산하는 값을 같은 식으로 낸다 — 콘솔 `HK60C.rate/cycle` 과 대조하는 것은
#: `reproduces_the_console()` 이고, 계약 순생산(`NET_TARGET_PER_H`)은 그 아래 정수다.
RATE_PER_H: float = rate().line_per_h
CYCLE_S: float = rate().tandem_cycle_s
CELL_EVA_KG_PER_H: float = round(CELL_EVA_KG * RATE_PER_H, 1)    # 셀/EVA 반출 질량률 (kg/h)


def reproduces_the_console() -> bool:
    """재현한 순생산·사이클이 콘솔 값과 같은가 — 콘솔은 `+(CYC.knifeLineRate*availability).toFixed(1)`.

    콘솔 식: 사이클 = (칼끝 간격 + 패널 길이)/칼날속도 + 급속거리/급속속도 + 고정동작,
    명목 = 3600/사이클, 순생산 = 명목 × 가동률. 계약 순생산(NET_TARGET)은 그 값을
    내림한 정수라 순생산이 계약을 넘어야 한다.
    """
    r = rate()
    tandem = (KNIFE_PITCH_MM + PANEL_MAX_MM[0]) / KNIFE_SPEED_MM_S + RAPID_DISTANCE_MM / RAPID_SPEED_MM_S + HANDLING_S
    console_rate = round(3600.0 / tandem * AVAILABILITY, 1)
    return (abs(r.line_per_h - console_rate) < 0.06 and abs(r.tandem_cycle_s - round(tandem, 1)) < 0.06
            and r.line_per_h >= NET_TARGET_PER_H)


def ir_average_kw(length_mm: float | None = None, width_mm: float | None = None) -> float:
    """IR 평균 소비 (kW) = 장당 열량 / 효율 / 라인 사이클. 기본은 포락선, 라인 패널을 주면 그 값."""
    L = PANEL_MAX_MM[0] if length_mm is None else length_mm
    W = PANEL_MAX_MM[1] if width_mm is None else width_mm
    heat_kj = (L * W / 1e6) * AREAL_CP_KJ_M2K * (T_TARGET_C - T_AMB_C)
    return round(heat_kj / (HEAT_EFFICIENCY_PCT / 100.0) / rate(L, W).tandem_cycle_s, 2)


# ── 질량 — 부품 카탈로그 ──────────────────────────────────────────────────


def module_kg() -> dict[str, float]:
    parts = _tool("parts")
    return {m: round(parts.module_kg(m), 1) for m in parts.MODULES}


def heaviest_part() -> tuple[str, str, float]:
    """현장 조립이므로 크레인이 드는 것은 모듈이 아니라 **단품**이다."""
    parts = _tool("parts")
    p = max(parts.P, key=lambda q: q.kg)
    return p.pid, p.name, round(p.kg, 1)


def machine_kg() -> float:
    return round(sum(module_kg().values()), 1)


_anchor = re.search(r"앵커 (\d+)점", ASSEMBLY.read_text(encoding="utf-8"))
ANCHOR_COUNT: int = int(_anchor.group(1))                     # 41 — D-602 A1~A14

# ── 경계 신호 — PLC 모델 ───────────────────────────────────────────────────


def boundary_signals() -> tuple[tuple[str, str, str], ...]:
    """경계 인터페이스반이 만드는 신호 (이름, I/O, 장치)."""
    plc = _tool("plc_model")
    return tuple((leaf.name, leaf.io, leaf.device) for leaf in plc.LEAVES
                 if leaf.device.startswith("경계"))


def upstream_signals() -> tuple[str, ...]:
    """상류 플랜트가 채워야 하는 신호 — 플랜트 PLC 가 BJ-101 에 주는 것."""
    return tuple(name for name, _, dev in boundary_signals()
                 if name.startswith("UP_") or name == "PL_IN_STACK_PRESENT")


def vendor_drive_count() -> int:
    """기계 자신의 구동부 수 — 벤더 MCC-1 안이라 플랜트 서보 일람에 **안 들어간다**."""
    return len(_tool("plc_model").DRIVES)


def summary() -> dict[str, object]:
    r = rate()
    return {
        "model": MODEL, "rev": REV, "tag": TAG,
        "ratePerH": RATE_PER_H, "cycleS": CYCLE_S, "availability": AVAILABILITY,
        "decks": DECKS, "lamps": LAMPS, "irKw": IR_INSTALLED_KW,
        "dwellS": r.dwell_s, "pitchS": r.release_pitch_s, "thermalPerH": r.thermal_per_h,
        "tandemPerH": r.tandem_per_h,
        "panelMax": list(PANEL_MAX_MM), "panelMin": list(PANEL_MIN_MM),
        "lineEl": LINE_EL_MM, "lengthMm": LENGTH_MM, "envelope": list(ENVELOPE_MM),
        "connectedKw": CONNECTED_KW, "demandKw": EXPECTED_DEMAND_KW,
        "machineKg": machine_kg(), "anchors": ANCHOR_COUNT,
    }
