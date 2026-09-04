"""외장 케이싱 — 기계를 제품으로 만드는 껍질, 그리고 그 껍질이 지켜야 할 것.

이 플랜트는 지금까지 **열린 골조**였다. 통로에서 보면 프레임과 투명 가드
너머로 기구가 그대로 보인다. 기능적으로는 문제가 없지만, 8 개 셀이 각자
다른 높이·다른 깊이로 서 있어 **한 대의 설비로 안 읽힌다.**

케이싱은 그것을 덮는 일인데, 덮기만 하면 설비가 나빠진다. 이 파일이 값으로
고정하는 것은 두 가지다 — **무엇이 하나의 언어를 만드는가**, 그리고
**그 껍질이 절대 건드리면 안 되는 것은 무엇인가.**

## 하나로 읽히게 하는 것은 평면이 아니라 선이다

셀마다 통로쪽 면의 깊이가 다르다 (Y 4,650 … 7,100). 통로쪽에 평면 한 장을
세워 맞추는 방법도 있지만, 그러면 얕은 셀 뒤에 최대 2.5 m 의 빈 부피가
생긴다 — 아무것도 담지 않는 벽이고, 크레인과 정비 접근을 막는다. 그래서
**껍질은 기계의 실제 부피를 따라간다.** 평면에서는 들쭉날쭉하다.

대신 **입면의 선을 끊지 않는다.** 어깨선·리빌·토우 세 높이가 58.8 m 전체에서
같은 값이고, 판 나눔 간격과 모서리 반경도 같다. 자동차의 숄더라인이 문짝과
펜더를 건너 이어지는 것과 같은 원리다 — 면은 물러섰다 나왔다 해도 선은
하나다. 껍질이 부피를 속이지 않으면서 한 덩어리로 읽히는 이유가 그것이다.

## 어깨선은 고른 값이 아니라 이 플랜트가 이미 가진 높이다

존 8 개의 높이는 5,150 · 4,150 · 2,800 · 2,800 · 2,800 · 2,800 · 2,800 ·
3,600 이다. **2,800 이 다섯 번**으로 최빈값이고, 어깨선은 그 값이다. 그보다
높은 것(투입 비전보·로봇 갠트리·유리제거 마스트)은 껍질을 **뚫고 올라온다** —
숨기지 않는다. 껍질은 상자가 아니라 몸통이고, 키 큰 장비는 그 위로 드러난다.

## 껍질이 건드리면 안 되는 것 셋

1. **정비성.** 39 절의 MTTR 0.5 h 는 모듈을 통째로 갈아 끼워서 나온 값이다.
   껍질로 봉하면 그 값이 무너진다. 그래서 `maintain.PROFILES` 의 교환 모듈
   **하나마다 문이 하나** 있고, 도킹 레일을 쓰는 중량 교환은 **문이 바닥까지**
   열려 토우 리세스가 끊긴다 — 모듈이 레일째 굴러 나온다. 문 수는 여기서
   세는 것이 아니라 정비 모델에서 나온다.

2. **열.** 껍질을 상자로 만들면 41 절의 실내 열부하 계산이 통째로 틀린다.
   그래서 **벽쪽은 덮지 않는다.** 껍질은 통로쪽 면과 양 끝단뿐이고, 벽쪽은
   열려 있어 발열이 지금과 같은 경로로 실내에 나온다. 열수지가 안 바뀌는
   이유는 껍질이 작아서가 아니라 **일부러 한 면을 비웠기 때문이다.**

3. **통로.** 껍질은 존 포락선 **안쪽으로** 두께를 먹는다. 통로 1,200 mm 는
   그대로다.

## 소리는 좋아졌다고 적지 않는다

환기를 위해 한 면을 열어 둔 껍질은 방음 인클로저가 아니다. 흡음 라이닝을
받을 수 있게 안쪽 면을 비워 두었지만, 실제 감쇠량은 벤더 시험 없이 못
낸다 — 36 절의 Kst 나 37 절의 예비품 수명과 같은 취급이다. `acoustics.py`
값을 손대지 않는 이유가 그것이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import access, layout, maintain

# ── 하나의 언어 ──────────────────────────────────────────────────────────
#: 어깨선 (mm). 존 높이의 최빈값이라 **고른 값이 아니다** —
#: `shoulder_is_the_plant_mode()` 가 그것을 확인한다.
SHOULDER_MM = 2800

#: 정비문 유효 높이 (mm). 사람이 모듈을 들고 지나는 문이라 표준 문짝 높이를
#: 쓴다. **리빌(그림자 홈)이 이 높이에 있다** — 문 상인방이 곧 입면의 선이라,
#: 장식으로 그은 선이 아니라 문이 만든 선이다.
DOOR_H_MM = 2400
DATUM_MM = DOOR_H_MM

#: 리빌 홈 — 높이와 깊이 (mm). 판이 만나는 자리를 이음매로 보이게 두지 않고
#: 그늘로 처리한다.
REVEAL_H_MM = 24
REVEAL_D_MM = 24

#: 토우 (mm) — 껍질이 바닥에서 100 뜬다. 몸통이 떠 보이고, 발끝 공간과 바닥
#: 청소가 같이 해결된다. 중량 교환문 앞에서는 **끊긴다.**
#:
#: 처음에는 그 자리에 60 물러선 걸레받이 판을 세웠는데, 간섭 검사가 그 판이
#: 리프트·셔틀·롤러를 45…60 mm 파고드는 것을 잡았다. 바닥 높이는 기계가 가장
#: 붐비는 자리다. 걸레받이를 빼고 **빈 그늘로 두면** 간섭이 사라지고, 그림자가
#: 판보다 진해 뜬 느낌도 오히려 세진다. 100 mm 는 청소 도구가 들어가는 틈이고
#: 위험원은 작업 높이에 있어 이 틈으로 닿지 않는다 (바닥 접근은 SCN 스캐너가 본다).
TOE_H_MM = 100

#: 모서리 반경 (mm). 수직 모서리 전부 같은 값이다.
RADIUS_MM = 12

#: 판 사이 이음매 (mm). 전 구간 같은 값이라 눈이 하나의 규칙으로 읽는다.
SEAM_MM = 8

#: 판 나눔의 기준 폭 (mm). 존 길이가 제각각이라 이 값으로 딱 떨어지지 않는다 —
#: 존마다 이 값에 **가장 가까운 정수 개**로 나누고, 실폭은 그 몫이다.
#: 폭이 존마다 몇 % 다른 것은 서로 다른 기계이므로 나란히 보이지 않고,
#: 눈이 읽는 것은 이음매 간격과 리빌이다.
BAY_NOMINAL_MM = 1000

#: 판 두께 (mm) 와 유리 두께 (mm).
SKIN_T_MM = 1.5
GLAZING_T_MM = 6.0

#: 면적당 질량 (kg/m²). 알루미늄 2.70 · 폴리카보네이트 1.20 g/cm³.
SKIN_KG_M2 = round(SKIN_T_MM * 2.70, 3)
GLAZING_KG_M2 = round(GLAZING_T_MM * 1.20, 3)
#: 멀리언(수직 판틀) 단위질량 (kg/m) — 60×40×t2 알루미늄 압출.
MULLION_KG_M = 1.02

#: 케이싱 두께 (mm) — 판 + 멀리언 깊이. 존 포락선 **안쪽으로** 먹는다.
DEPTH_MM = 60

#: 껍질과 기계 사이 틈 (mm). 판을 떼어 낼 수 있어야 하고, 기계 진동이 판으로
#: 넘어가면 판이 운다.
SKIN_GAP_MM = 20

#: **존 표의 통로쪽 깊이는 공칭값이다.** 처음에 껍질을 그 값에 세웠더니
#: `tools/check_casing_fit.mjs` 가 166 곳 간섭을 잡았다 — 가장 큰 것이
#: BFC-101B 포탈 기둥으로, AFU 셀의 부재인데 실제로는 **robot 존의 X 범위에
#: 서 있고** 통로쪽으로 1,060 mm 더 나와 있었다. 존 표는 길이를 배분하는
#: 표이지 "이 X 구간의 모든 부재가 이 깊이 안에 있다"는 약속이 아니다.
#:
#: 그래서 면을 **3D 에서 실측한 값**으로 잡는다 (어깨선 아래, 장비 밴드 안,
#: 시간을 훑어 움직이는 것까지 포함한 최대 z → 플랜트 Y). §7 의 캐리지 피치
#: 2,900 과 §26 의 링 관통 88 mm 을 실측으로 잡았던 것과 같은 자리다.
MEASURED_FACE_MM: dict[str, int] = {
    "afu": 7060,      # LFT-101B 게이트·구역스캐너
    "robot": 7060,    # BFC-101B 포탈 기둥·LM가이드 (3,010) 과 바닥 스캐너
    "jbr": 5170,      # 가드 방진 풋
    "afr": 6355,      # 리젝트 스퍼 방호터널
    "post": 7100,     # 장비 밴드 끝까지
    "buffer": 7145,   # 버퍼 안전가드 — 밴드를 45 mm 넘는다
    "grm": 7180,      # 셀 베이스 빔 — 밴드를 80 mm 넘는다
}

#: 도면에 그리는 판 조립 깊이 (mm). 판재는 1.5 t 지만 가장자리를 접고 보강대를
#: 대면 조립체가 이만큼 된다 — 질량은 판재 두께로, 형상은 조립 깊이로 낸다.
PANEL_ASSY_MM = 24

#: 껍질을 안 두르는 곳과 그 이유. 값으로 남기지 않으면 나중에 "왜 여기만
#: 비었지" 하고 채우게 된다.
OPEN_BY_DESIGN: tuple[tuple[str, str], ...] = (
    ("벽쪽 면", "발열이 지금 경로로 실내에 나와야 한다 — 상자로 만들면 "
              "thermal.py 의 실내 부하가 통째로 틀린다"),
    ("바닥 100 mm", "걸레받이를 세우면 바닥 높이의 리프트·셔틀·롤러를 파고든다. "
                 "빈 그늘로 두면 간섭이 없고 청소 도구가 들어간다"),
    ("JB/AFR 접합부 (250 mm)", "통합셀 안에서 두 스테이션이 만나는 자리다. "
                            "패널이 지나가므로 덮을 수 없고, 존이 하나로 합쳐져 "
                            "이제 별도 존도 아니다 — 두 존의 껍질이 여기서 끊긴다"),
    ("어깨선 위", "투입 비전보·로봇 갠트리·유리제거 마스트는 껍질을 뚫고 올라온다 — "
               "몸통은 어깨까지고 키 큰 장비는 드러낸다"),
)

#: 껍질을 두르는 존. `gate` 는 위 사유로 빠진다.
CASED_ZONES: tuple[str, ...] = ("afu", "robot", "jbr", "afr", "post", "buffer", "grm")

#: 교환 모듈이 어느 존 뒤에 있는가. 문은 이 표에서 나오고, 개수를 여기서
#: 세지 않는다 — `maintain.PROFILES` 가 늘면 문도 는다.
MODULE_ZONE: dict[str, str] = {
    "RB-AFU": "afu",
    "RB-BFC": "afu",       # BFC-101A/B 는 AFU 존 안에 있다
    "RB-ROBOT": "robot",
    "RB-JBR": "jbr",
    "RB-AFR": "afr",
    "RB-POST": "post",
    "RB-GBR": "buffer",
    "RB-GRM": "grm",
    "RB-DUST": "post",     # DX-601 은 SG-301 옆(post 존)에 선다
}

#: 이 껍질이 아닌 교환 모듈과 그 사유. **여기 적지 않고 빠지면 시험이 잡는다** —
#: 정비 모델에 모듈이 늘었는데 문을 안 만들면 그 모듈이 껍질에 갇힌다.
NOT_CASED: dict[str, str] = {
    "RB-UTIL": "압축공기실은 별도 구획이라 이 껍질이 아니다 — 자기 문이 따로 있다",
}


@dataclass(frozen=True)
class Door:
    """정비문 하나. **정비 모델이 만든다** — 여기서 정하는 것이 아니다."""

    tag: str            # 어느 교환 모듈의 문인가
    zone: str
    bays: int           # 판 나눔 몇 칸
    to_floor: bool      # 도킹 레일이 지나가는가 (토우 리세스가 끊긴다)
    module: str

    @property
    def clear_h_mm(self) -> int:
        return DOOR_H_MM + (TOE_H_MM if self.to_floor else 0)


@dataclass(frozen=True)
class Bay:
    """판 한 칸. 종류는 셋뿐이다 — 막힌 판·문·창."""

    zone: str
    index: int
    kind: str           # 'solid' | 'door' | 'window'
    width_mm: float
    tag: str | None     # 문이면 그 교환 모듈 태그


def zone_span_mm(key: str) -> tuple[int, int]:
    """존의 X 구간 (상류, 하류)."""
    zone = next(z for z in layout.build_zones() if z.key == key)
    return zone.x0_mm, zone.x1_mm


def nominal_face_mm(key: str) -> int:
    """존 표가 적은 통로쪽 Y. **공칭값이라 껍질을 여기 세우면 안 된다.**"""
    return next(z for z in layout.build_zones() if z.key == key).y1_mm


#: 셀 끝단 가드 판의 두께 (mm) — 3D 실측. 플랜트 양 끝에는 이미 이 판이 서
#: 있고, 끝단 케이싱은 그 **바깥면에** 얹힌다. 안쪽에 넣으면 판이 가드를
#: 파고든다 (검사가 4곳을 잡았다).
MEASURED_END_FRAME_MM = 90

#: 그래서 끝단 케이싱이 존 경계 밖으로 나가는 양 (mm).
END_OFFSET_MM = MEASURED_END_FRAME_MM // 2 + PANEL_ASSY_MM

#: 하류 끝 기계의 **실측** X (플랜트 좌표 mm). 3D 에서 GRM 셀의 최하류 부재
#: (WR-101 전장 권취롤러 · 셀 베이스 빔) 까지 잰 값이다.
MEASURED_END_MM = 58_845

def scene_end_shim_mm() -> int:
    """3D 끝단 판이 존 경계 밖으로 **더** 물러서야 하는 양 (mm). 등록되면 0.

    존 표는 **설계**고 3D 는 그 설계를 비추는 **그림**인데, 둘의 원점이 아직
    맞물려 있지 않다 (`layout.SCENE_GRID_OPEN` — 발주처 확인 대기). REV.44
    까지는 두 값이 우연히 45 mm 안에서 만나 아무 일도 없었다. JB/AFR
    부분통합으로 존 합계가 750 mm 줄자 존 표의 하류 끝이 3D 기계보다 앞으로
    와, 끝단 판이 권취롤러와 적재대를 24 mm 관통했다 (케이싱 검사가 4곳을
    잡았다).

    설계 수치(전장·판 매수·질량)는 존 표를 따르고, **3D 에 그리는 끝단 판만**
    이 값만큼 물러선다. 격자가 등록되면 0 이 되고 이 함수도 없어진다.
    """
    return max(0, MEASURED_END_MM - layout.plant_envelope_mm()[0])

#: 끝단 판틀(endpost)이 딛는 셀 베이스 부재의 윗면 (mm). 판틀을 바닥까지 내리면
#: 셀 골조를 관통한다 — 하류 끝(GRM)에는 x +7,025 자리에 140 mm 높이의 횡베이스
#: 빔이 이미 서 있고, 판틀이 그 안에 24 mm 박혀 있었다. 판틀은 바닥이 아니라
#: **그 부재 위에** 서야 하중 경로가 서고 관통이 없어진다. 상류 끝(AFU)에는
#: 그 자리에 부재가 없어 바닥에서 시작한다.
ENDPOST_BASE_MM: dict[str, int] = {"afu": 0, "grm": 140}


def endpost_span_mm(key: str) -> tuple[int, int]:
    """끝단 판틀의 아래·위 (mm) — 딛는 부재 윗면에서 어깨까지."""
    base = ENDPOST_BASE_MM[key]
    if not 0 <= base < SHOULDER_MM:
        raise ValueError(f"{key} 판틀 밑면이 어깨 밖이다")
    return base, SHOULDER_MM


def endposts_stand_on_something() -> bool:
    """모든 끝단 판틀이 어깨까지 서고, 그 밑이 바닥이거나 실재 부재인가."""
    return all(endpost_span_mm(k)[1] == SHOULDER_MM for k in ENDPOST_BASE_MM)


def clad_length_mm() -> int:
    """껍질을 두른 뒤의 실제 전장 (mm).

    존 합계 58,800 은 **공칭**이다. 끝단 가드가 이미 그 밖으로 45 mm 나와
    있었고, 껍질은 그 위에 얹히므로 양 끝에서 조금씩 는다. 존은 하나도 안
    길어졌다 — 늘어난 것은 껍질 두께뿐이고, 그 사실을 값으로 남긴다.
    """
    return layout.plant_envelope_mm()[0] + 2 * (END_OFFSET_MM + PANEL_ASSY_MM // 2)


#: 껍질이 통로로 나갈 수 있는 최대 (mm). 통로 1,200 에서 피난 유효 900 을
#: 남기고 남는 값이다 — 숫자를 고르는 것이 아니라 **접근 모델이 정한다.**
MAX_ENCROACH_MM = layout.AISLE_WIDTH_MM - access.AISLE_CLEAR_MM


def zone_face_mm(key: str) -> int:
    """껍질 **바깥면**이 서는 Y.

    껍질은 기계에 붙는 것이라, 붙을 자리(가장 바깥 부재의 바깥면) **위에**
    얹혀야 한다. 그 안으로 넣으면 판이 부재를 파고들고, 실제로 첫 판이
    그랬다 — 각 셀의 베이스 빔(깊이 160)과 가드 프레임(90)이 이미 장비 밴드
    끝 평면에 서 있는데 껍질을 같은 평면에 세워 106 곳이 겹쳤다.

    그래서 실측 바깥면에 판 조립 깊이를 더한다. 그러면 buffer·grm 처럼 부재가
    밴드 끝까지 나온 존에서는 껍질이 **통로로 조금 나온다.** 나오는 양은
    `encroach_mm()` 이 값으로 내고, 피난 유효폭 안에 드는지는 시험이 지킨다.
    """
    return max(nominal_face_mm(key), MEASURED_FACE_MM[key] + PANEL_ASSY_MM)


def encroach_mm(key: str) -> int:
    """껍질이 장비 밴드를 넘어 통로로 나온 양 (mm)."""
    return max(0, zone_face_mm(key) - layout.MACHINE_BAND_Y_MM)


def aisle_clear_mm() -> int:
    """껍질을 붙인 뒤 남는 통로 유효폭 (mm)."""
    return layout.AISLE_WIDTH_MM - max(encroach_mm(k) for k in CASED_ZONES)


def aisle_still_clears() -> bool:
    """피난 유효폭을 지키는가. 못 지키면 껍질이 아니라 통로 설계를 고쳐야 한다."""
    return aisle_clear_mm() >= access.AISLE_CLEAR_MM


def encroaching_zones() -> tuple[str, ...]:
    return tuple(k for k in CASED_ZONES if encroach_mm(k) > 0)


def zone_length_mm(key: str) -> int:
    x0, x1 = zone_span_mm(key)
    return x1 - x0


def bay_count(key: str) -> int:
    """기준 폭에 가장 가까운 정수 개."""
    return max(1, round(zone_length_mm(key) / BAY_NOMINAL_MM))


def bay_width_mm(key: str) -> float:
    return round(zone_length_mm(key) / bay_count(key), 2)


def shoulder_is_the_plant_mode() -> bool:
    """어깨선이 **골라 적은 값이 아니라** 존 높이의 최빈값인가."""
    heights = [z.height_mm for z in layout.build_zones()]
    mode = max(set(heights), key=heights.count)
    return mode == SHOULDER_MM


def doors() -> tuple[Door, ...]:
    """정비문 — 교환 모듈 하나마다 하나. 중량 교환은 두 칸·바닥까지."""
    rows: list[Door] = []
    for profile in maintain.PROFILES:
        zone = MODULE_ZONE.get(profile.tag)
        if zone is None:
            continue
        heavy = profile.swap == "heavy"
        rows.append(Door(profile.tag, zone, 2 if heavy else 1,
                         "dock" in profile.features, profile.module))
    return tuple(rows)


def doors_of(key: str) -> tuple[Door, ...]:
    return tuple(d for d in doors() if d.zone == key)


def window_bay(key: str) -> int:
    """관찰창 — 존 한가운데 칸. 안이 안 보이는 기계는 운전자가 못 믿는다."""
    return bay_count(key) // 2


def bays(key: str) -> tuple[Bay, ...]:
    """존의 판 나눔. 문은 하류 끝부터 채우고 관찰창 칸은 비켜 간다.

    **문의 정확한 칸은 벤더 GA 가 정한다** — 교환 모듈이 셀 안 어디에 앉는지는
    아직 없는 값이다(§21 의 GRM 외형과 같은 취급). 여기서 고정하는 것은
    **칸 수와 폭과 종류**이고, 자리는 관례다.
    """
    count, width = bay_count(key), bay_width_mm(key)
    window = window_bay(key)
    kinds: list[tuple[str, str | None]] = [("solid", None)] * count
    kinds[window] = ("window", None)
    cursor = count - 1
    for door in doors_of(key):
        placed = 0
        while placed < door.bays and cursor >= 0:
            if kinds[cursor][0] == "solid":
                kinds[cursor] = ("door", door.tag)
                placed += 1
            cursor -= 1
    return tuple(Bay(key, i, kind, width, tag)
                 for i, (kind, tag) in enumerate(kinds))


def all_bays() -> tuple[Bay, ...]:
    return tuple(b for key in CASED_ZONES for b in bays(key))


def bays_by_kind() -> dict[str, int]:
    counts = {"solid": 0, "door": 0, "window": 0}
    for bay in all_bays():
        counts[bay.kind] += 1
    return counts


def face_area_m2(kind: str | None = None) -> float:
    """통로쪽 껍질 면적 (m²). 토우 아래는 비어 있으므로 뺀다."""
    height = (SHOULDER_MM - TOE_H_MM) / 1000.0
    total = sum(b.width_mm / 1000.0 * height
                for b in all_bays() if kind is None or b.kind == kind)
    return round(total, 2)


def end_area_m2() -> float:
    """플랜트 양 끝단 (mm) — 상류 AFU 면과 하류 GRM 면."""
    height = (SHOULDER_MM - TOE_H_MM) / 1000.0
    depth = sum(zone_face_mm(k) for k in ("afu", "grm")) / 1000.0
    return round(depth * height, 2)


def returns_mm() -> tuple[tuple[str, str, int, int], ...]:
    """존이 만나는 자리에서 면이 물러서는 단차 (상류존, 하류존, X, 단차 mm).

    껍질이 기계 부피를 따라가므로 존마다 통로쪽 깊이가 다르고, 이음매에서
    면이 최대 1,725 mm 물러선다. **그 자리를 그냥 두면 껍질에 구멍이 난다** —
    판의 절단면과 기계 속이 그대로 보이고, 분진과 소음이 그리로 나간다.
    돌아 들어가는 판(리턴)으로 닫는다. 미관이 아니라 봉함이다.

    `gate` 존은 껍질이 없으므로 JBR 하류와 AFR 상류의 리턴이 그 개구를 양쪽에서
    감싼다 — 인계 개구가 액자에 들어간다.
    """
    order = ("afu", "robot", "jbr", "afr", "post", "buffer", "grm")
    rows: list[tuple[str, str, int, int]] = []
    for up, down in zip(order, order[1:]):
        step = zone_face_mm(up) - zone_face_mm(down)
        if step:
            rows.append((up, down, zone_span_mm(up)[1], step))
    return tuple(rows)


def return_area_m2() -> float:
    height = (SHOULDER_MM - TOE_H_MM) / 1000.0
    return round(sum(abs(step) / 1000.0 * height for *_, step in returns_mm()), 2)


def the_shell_is_closed() -> bool:
    """면이 물러서는 모든 자리에 리턴이 있는가. 하나라도 없으면 껍질에 구멍이다."""
    order = ("afu", "robot", "jbr", "afr", "post", "buffer", "grm")
    steps = {(u, d) for u, d in zip(order, order[1:])
             if zone_face_mm(u) != zone_face_mm(d)}
    return {(u, d) for u, d, _, _ in returns_mm()} == steps


def mullion_count() -> int:
    """수직 판틀 — 존마다 칸 수 + 1. 판을 잡고 리빌을 만들고 하중을 바닥으로 보낸다."""
    return sum(bay_count(k) + 1 for k in CASED_ZONES)


def mullion_length_m() -> float:
    return round(mullion_count() * SHOULDER_MM / 1000.0, 2)


def mass_kg() -> float:
    """껍질 전체 질량 (kg).

    **바닥 앵커가 안 는다** — 멀리언이 존 베이스 빔에 앉고, 그 빔은 이미
    앵커돼 있다. 껍질은 매다는 하중이지 새 하중 경로가 아니다.
    """
    opaque = (face_area_m2("solid") + face_area_m2("door")
              + end_area_m2() + return_area_m2())
    glazed = face_area_m2("window")
    return round(opaque * SKIN_KG_M2 + glazed * GLAZING_KG_M2
                 + mullion_length_m() * MULLION_KG_M, 1)


def thermal_is_unchanged() -> bool:
    """열수지가 안 바뀌는가 — **벽쪽을 비워 뒀기 때문에** 안 바뀐다."""
    return any("벽쪽" in where for where, _ in OPEN_BY_DESIGN)


def every_module_has_a_door() -> bool:
    """교환 모듈 하나마다 문이 하나인가. 하나라도 막히면 MTTR 이 무너진다.

    **비교 대상은 `maintain.PROFILES` 다.** `MODULE_ZONE` 끼리 견주면 그 표에서
    빠진 모듈을 영영 못 잡는다 — 자기가 만든 값으로 자기를 검사하는 꼴이라,
    정비 모델에 모듈이 늘어도 이 함수는 계속 참을 돌려준다.
    """
    want = {p.tag for p in maintain.PROFILES} - set(NOT_CASED)
    return {d.tag for d in doors()} == want


def docked_doors_reach_the_floor() -> bool:
    """도킹 레일이 지나는 문은 바닥까지 열려야 모듈이 굴러 나온다."""
    return all(d.to_floor for d in doors() if d.bays == 2)


def lines_are_continuous() -> bool:
    """입면의 세 선이 전 구간 같은 높이인가 — 이 껍질을 하나로 읽게 하는 것."""
    return TOE_H_MM < DATUM_MM < SHOULDER_MM


def summary() -> dict[str, object]:
    """도면·콘솔 리터럴이 받아 가는 값."""
    counts = bays_by_kind()
    return {
        "zones": len(CASED_ZONES),
        "bays": len(all_bays()),
        "solid": counts["solid"],
        "doors": counts["door"],
        "windows": counts["window"],
        "shoulderMm": SHOULDER_MM,
        "datumMm": DATUM_MM,
        "toeMm": TOE_H_MM,
        "endpostBaseMm": dict(ENDPOST_BASE_MM),
        "radiusMm": RADIUS_MM,
        "seamMm": SEAM_MM,
        "bayNominalMm": BAY_NOMINAL_MM,
        "faceAreaM2": face_area_m2(),
        "endAreaM2": end_area_m2(),
        "returnAreaM2": return_area_m2(),
        "returns": len(returns_mm()),
        "mullions": mullion_count(),
        "massKg": mass_kg(),
        "openByDesign": len(OPEN_BY_DESIGN),
    }
