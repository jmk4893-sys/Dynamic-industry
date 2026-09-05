"""DX-601 집진 — 분진폭발 평가와 그 결과가 배치에 미치는 것.

집진기는 REV.1 부터 있었다. 풍량도 차압 감시도 인터록도 도면에 있다. 없던
것은 **그 안에 도는 것이 터질 수 있는가**라는 물음이다. 폐 PV 모듈을 다루는
설비에서 이 물음이 비어 있으면 소방·산업안전 인허가가 거기서 멈춘다.

답을 지어낼 수는 없다. 분진의 폭발 특성(Kst·Pmax·MIE·LEL)은 **시험으로만**
나온다(EN 14034-1/2/3). 그래서 이 모듈이 하는 일은 셋이다.

* 무엇이 들어오는지 흐름별로 적고 **가연분과 불연분을 가른다**
* 지금 확실히 말할 수 있는 것을 값으로 못 박는다 — 알루미늄 미분이 안
  생긴다는 것, 점화원이 셋이라는 것, 집진기가 실내에 있어 옥내로 벤트를
  못 연다는 것
* 시험 결과가 St-1 이냐 St-2 냐에 따라 **무엇이 달라지는지**를 미리 적는다.
  방폭벤트는 벽을 뚫는 일이라 건축과 같이 정해야 하고, 그것은 시험 결과가
  나온 뒤에 시작하면 늦다

**유리분이 불연이라는 것이 이 설비를 구해 주지는 않는다.** 불활성분은
희석할 뿐이고, 얼마나 섞여야 불활성화되는지는 물질쌍마다 다르다. "대부분
유리니까 안 터진다" 는 시험 없이는 문장일 뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import air


# ── 흐름 ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Stream:
    """집진 흐름 하나."""

    tag: str
    source: str
    flow_m3h: int | None        # None = 도면에 이름만 있고 풍량이 없다
    material: str
    combustible: bool
    basis: str


STREAMS: tuple[Stream, ...] = (
    Stream("DS-01", "SG-301 엣지 연마 (스핀들 3,000 rpm)", 1_000,
           "소다석회 유리분 + 연마휠 마모분", False,
           "SiO₂ 기반이라 그 자체로는 불연이다. 다만 **불활성분이 있다는 것과 "
           "혼합물이 불활성화된다는 것은 다른 말이다**"),
    Stream("DS-02", "JBR-201 국소집진", 350,
           "백시트(PVF/PET)·EVA·케이블 피복 절삭분 · 접착제", True,
           "폴리머 절삭분은 가연성이다. 이 흐름이 혼합물의 가연분을 만든다"),
    Stream("DS-03", "CV-301 슈레더 투입부 집진", None,
           "EVA·백시트 파쇄분", True,
           "**도면에 이름은 있는데 풍량이 없다.** 파쇄분은 절삭분보다 곱고 "
           "가연성이라 폭발 평가에서 가장 무거운 흐름인데, DX-601 집계"
           "(1,350 m³/h)에도 안 들어가 있다"),
)


def listed_streams() -> tuple[Stream, ...]:
    """풍량이 잡힌 흐름."""
    return tuple(s for s in STREAMS if s.flow_m3h is not None)


def unquantified_streams() -> tuple[Stream, ...]:
    """이름만 있고 풍량이 없는 흐름 — 집진기 용량 밖에 있다는 뜻이다."""
    return tuple(s for s in STREAMS if s.flow_m3h is None)


def counted_flow_m3h() -> int:
    """집계된 풍량 — air.DUST_FLOW_M3H 와 같아야 한다."""
    return sum(s.flow_m3h for s in listed_streams())


def flow_is_consistent() -> bool:
    """집진 모델과 공압 모델이 같은 풍량을 보고 있는가."""
    return counted_flow_m3h() == air.DUST_FLOW_M3H


def combustible_flow_fraction() -> float:
    """가연 흐름이 차지하는 풍량 비율.

    **질량 비율의 대용값이다.** 폭발 평가가 필요로 하는 것은 질량 농도이지
    풍량이 아니다 — 유리분은 무겁고 폴리머분은 가벼워서 같은 풍량이라도
    질량은 크게 다르다. 이 값은 "가연분이 미량인가 주성분인가" 를 가르는
    1차 판단에만 쓰고, DHA(분진위험성평가)가 실측 질량률로 대체한다.
    """
    listed = listed_streams()
    total = sum(s.flow_m3h for s in listed)
    burnable = sum(s.flow_m3h for s in listed if s.combustible)
    return round(burnable / total, 3)


# ── 지금 확실한 것 ───────────────────────────────────────────────────────
#: 알루미늄 프레임은 **인발**로 뗀다 — 톱질도 연삭도 없다. 알루미늄 미분이
#: 안 생긴다는 뜻이고, 그것이 이 설비가 St-3(Kst > 300) 을 피하는 이유다.
#: 프레임을 절단하는 공정으로 바꾸면 집진 설계 전체가 달라진다 — 습식 집진은
#: 알루미늄과 물이 수소를 내므로 아예 못 쓴다.
FRAME_IS_PULLED_NOT_CUT = True

#: 점화원. 분진폭발은 가연분·산소·분산·밀폐·점화 다섯이 겹쳐야 일어나고,
#: 앞의 넷은 집진기 안에서 늘 갖춰져 있다. 그래서 관리 대상은 점화원이다.
IGNITION_SOURCES: tuple[tuple[str, str], ...] = (
    ("SG-301 연마 스파크", "스핀들 3,000 rpm 의 유리·휠 마찰 스파크가 덕트로 빨려 든다. "
                        "프리세퍼레이터와 스파크 트랩이 그래서 필요하다"),
    ("GRM-401 IR 뱅크", "표면이 발화온도를 넘는 유일한 상시 열원이다. 다만 IR 배기는 "
                      "DX-601 이 아니라 GRM-EX-401 로 빠진다 — 두 계통을 합치면 "
                      "가연 분진과 고온 오프가스가 한 덕트에 든다"),
    ("정전기", "폴리머 분진은 이송 중에 대전한다. 덕트·집진기·백케이지 전 구간 "
             "등전위 본딩과 도전성 백(백 표면저항 10⁹ Ω 이하)이 대책이다"),
)


# ── 실내라는 것이 정하는 것 ──────────────────────────────────────────────
#: 집진기는 라인 옆 실내에 있다. 방폭벤트를 옥내로 열 수 없다 —
#: 화구가 통로로 나온다. 셋 중 하나를 골라야 하고 셋 다 배치가 바뀐다.
INDOOR_VENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("벤트 덕트로 옥외", "가장 싸지만 덕트가 벽을 뚫는다 — 건축 인터페이스다. "
                    "덕트가 길어질수록 Pred 가 올라가 벤트 면적이 커진다(EN 14491)"),
    ("무염 벤트 (flameless)", "화염을 실내에서 끈다. 옥외 덕트가 없어 배치가 자유롭지만 "
                          "장치가 비싸고 정기 교체품이다"),
    ("집진기를 옥외로", "폭발 보호가 가장 단순해진다. 대신 덕트가 길어져 압손·"
                   "블로워 동력이 오르고, 겨울철 결로·동파가 새 문제로 온다"),
)

#: 역화 차단 (EN 15089). 집진기에서 점화되면 화염이 덕트를 타고 JBR·SG 로
#: 되돌아간다. 이 플랜트는 흡입구가 **사람이 있는 셀 안**이라 특히 그렇다.
ISOLATION_REQUIRED = True


# ── 시험이 정하는 것 ─────────────────────────────────────────────────────
#: 시험 항목과, 그 결과가 없으면 무엇을 못 하는가.
REQUIRED_TESTS: tuple[tuple[str, str], ...] = (
    ("EN 14034-1/2 — Pmax · (dP/dt)max → Kst", "벤트 면적 계산(EN 14491)의 입력. "
                                            "없으면 방폭벤트 크기를 못 정한다"),
    ("EN 14034-3 — 하한폭발농도 LEL", "덕트 내 농도를 LEL 밑으로 유지할 수 있는지 판단"),
    ("EN 13821 — 최소착화에너지 MIE", "정전기 대책 수준(본딩만인가 도전성 백까지인가)을 정한다"),
    ("EN ISO/IEC 80079-20-2 — 층·운 발화온도", "IR·베어링 표면온도 한계"),
    ("혼합 시료 채취", "**시험은 실제 혼합 분진으로 해야 한다.** 유리분과 폴리머분을 "
                 "따로 시험하면 희석 효과가 안 보인다"),
)

#: Kst 구간별 St 등급 (EN 14034 관례). 시험값이 어디 떨어지느냐로 보호 방식이 갈린다.
ST_CLASSES: tuple[tuple[str, int, int, str], ...] = (
    ("St-0", 0, 0, "폭발하지 않음 — 방폭 보호 불요. 다만 시험이 그렇게 나와야 한다"),
    ("St-1", 1, 200, "벤트 또는 억제. 통상 유기 분진이 여기 든다"),
    ("St-2", 201, 300, "벤트 면적이 크게 늘어난다. 억제가 현실적인 대안이 된다"),
    ("St-3", 301, 10_000, "알루미늄·마그네슘급. **이 설비는 프레임을 인발로 떼므로 "
                          "여기 해당하지 않는다** — 절단 공정으로 바꾸면 달라진다"),
)


def st_class(kst_bar_m_s: int) -> str:
    """시험으로 나온 Kst 를 등급으로. 시험 전에는 부를 일이 없다."""
    if kst_bar_m_s <= 0:
        return "St-0"
    for name, lo, hi, _ in ST_CLASSES[1:]:
        if lo <= kst_bar_m_s <= hi:
            return name
    raise ValueError("Kst 가 표 밖이다")


def protection_for(kst_bar_m_s: int) -> str:
    """등급에 따라 무엇이 붙는가 — 시험 결과가 오면 바로 읽을 수 있게."""
    return next(note for name, _, _, note in ST_CLASSES if name == st_class(kst_bar_m_s))


# ── 집진기 자신의 값 ─────────────────────────────────────────────────────
def filter_area_m2() -> float:
    """여과 면적 — 공압 모델과 같은 출처를 쓴다."""
    return air.filter_area_m2()


def pulse_valves() -> int:
    return air.pulse_valves()


def missing_flow_consequences() -> tuple[str, ...]:
    """CV-301 풍량이 들어오면 무엇이 따라 움직이는가.

    풍량 하나가 없는 것이 아니라, 그 하나가 여과면적 → 펄스밸브 → 압축공기
    소비 → F16 까지 이어지는 사슬의 첫 항이다.
    """
    return (
        f"여과 면적 {filter_area_m2():g} m² 는 {air.DUST_FLOW_M3H:,} m³/h ÷ "
        f"A/C {air.AIR_TO_CLOTH_M3_H_M2:g} 에서 나온다 — 풍량이 늘면 같이 는다",
        f"밸브 {pulse_valves()}개는 여과 면적 ÷ {air.AREA_PER_VALVE_M2:g} m² 다",
        f"탈진 소비 {air.pulse_average_nl_min():g} NL/min 은 밸브 수에 비례한다",
        "그 소비가 F16 LP-AIR 로 올라가고, 컴프레서 선정까지 간다",
        "폭발 평가 쪽에서는 **가장 가연성 높은 흐름이 집계 밖에 있다**는 것이 더 무겁다",
    )


def summary() -> dict[str, object]:
    """도면 리터럴이 받아 가는 값."""
    return {
        "streams": len(STREAMS),
        "countedFlowM3h": counted_flow_m3h(),
        "unquantified": len(unquantified_streams()),
        "combustibleFraction": combustible_flow_fraction(),
        "framePulledNotCut": FRAME_IS_PULLED_NOT_CUT,
        "ignitionSources": len(IGNITION_SOURCES),
        "isolationRequired": ISOLATION_REQUIRED,
        "tests": len(REQUIRED_TESTS),
        "filterAreaM2": filter_area_m2(),
        "pulseValves": pulse_valves(),
    }
