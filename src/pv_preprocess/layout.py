"""전처리 플랜트 배치 — 셀 외형에서 존과 전체 포락선을 파생한다.

좌표 규약: X=공정방향, Y=진행방향 좌측, Z=FFL 상향 (단위 mm).
`Station.envelope` 는 도면 관례대로 ``(L, W, H) = (X, Y, Z)`` 다.

REV.21 에서는 배치표의 X 스팬을 손으로 적어 넣어 afu(−1,800)·robot(−1,200)·
afr(−4,400)·post(−2,600), 합계 10,000 mm 만큼 존이 자기 장비보다 짧았다. Y·H 는
외형에서 옮겨 적어 전부 일치했으므로, 여기서는 셋 다 외형에서 파생한다.

보행·정비 통로도 REV.21 에서는 Y 5,900–7,100 에 그렸는데 afu·post·buffer 존이
그 위를 덮어 전장의 절반 가까이에서 통로가 사라졌다. 통로는 장비 밴드 **밖**에 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 장비가 점유할 수 있는 Y 밴드 (mm). 모든 존의 Y 구간은 이 안에 들어와야 한다.
MACHINE_BAND_Y_MM = 7100

#: 보행·정비 통로 폭 (mm). 장비 밴드 바깥에 별도로 확보한다.
AISLE_WIDTH_MM = 1200

#: JBR–AFR 인계 게이트 길이 (mm).
#:
#: REV.21 은 1,250 mm 로 잡혀 있었는데 그 구간에 자기 하드웨어가 하나도 없었다.
#: 3D 모델 실측으로 확인한 것:
#:
#: * JBR 셀 구조 하류 끝(가드 상부 횡빔)  x = −25 mm
#: * AFR 셀 구조 상류 시작(SF-701 가드)   x = +300 mm  → 가드-가드 이격 325 mm
#: * JB/AFR-301 인계 롤러(+641…+731)와 데이터 게이트(+1,220…+1,320)는
#:   둘 다 AFR 베이스(550…11,950) **안쪽**에 붙어 있다.
#: * 제거한 VS-301 검증헤드(−2,832…−2,548)는 JBR 셀 **안쪽**이었다 —
#:   즉 비전 감축으로 라인 길이가 줄어든 것은 아니다.
#:
#: 그래서 게이트는 실측 이격 325 mm 에 앵커·심 여유를 얹은 값으로 잡는다.
HANDOFF_CLEARANCE_MM = 350


@dataclass(frozen=True)
class Station:
    """설비 셀 하나. `envelope` 는 (X, Y, Z) 외형 mm."""

    key: str
    sheet: str
    name: str
    envelope: tuple[int, int, int]
    transfer_height_mm: int

    @property
    def length_mm(self) -> int:
        return self.envelope[0]

    @property
    def width_mm(self) -> int:
        return self.envelope[1]

    @property
    def height_mm(self) -> int:
        return self.envelope[2]


@dataclass(frozen=True)
class Zone:
    """배치도 위의 한 구간. X 는 상류부터 이어 붙이고, Y·H 는 셀 외형에서 온다."""

    key: str
    label: str
    x0_mm: int
    x1_mm: int
    y0_mm: int
    y1_mm: int
    height_mm: int
    note: str

    @property
    def length_mm(self) -> int:
        return self.x1_mm - self.x0_mm

    @property
    def width_mm(self) -> int:
        return self.y1_mm - self.y0_mm


#: 셀별 GA 외형. 도면의 `stations` 객체와 같은 값이어야 한다.
STATIONS: dict[str, Station] = {
    s.key: s
    for s in (
        Station("afu", "PV-AFU-101-GA-2101", "AFU-101 · 투입·비전·듀얼 리프트 셀",
                (6800, 7100, 5050), 1880),
        # REV.22-P01: 3D 모델 실측으로 상세 전개하면서 분리헤드·셔틀·포획빔이 들어왔다.
        # 부품 실측 span X 4,940 · Y(깊이) 2,360 · Z(상하) 4,290 — 셔틀이 픽업면까지 나가고
        # 포획빔 수납 카세트가 중앙벽 쪽으로 물리므로 (3,600, 2,900, 3,500) 으로는 못 담는다.
        # bfc 는 ZONE_SEED 에 없는 부품 조립도라 전장에는 영향이 없다.
        # REV.22-P02: 승강기둥을 포탈(문형)로 재배치 — 종전 기둥·LM가이드가 반전축 선상에
        # 서서 셔틀·승강 패널을 관통했다(3D 스윕 실측 t 7.5–12.4 s). 기둥이 통과대역 밖
        # (z −1,290/+950)으로 나가며 외형 (5,000, 2,400) → (5,100, 2,900).
        Station("bfc", "PV-BFC-101-ASM-2201", "BFC-101A/B · 단장 분리·셔틀·승강·180° 반전카세트",
                (5100, 2900, 4350), 2100),
        Station("robot", "PV-RBPT-101-GA-2301", "RB-101 · EOAT · PT-101 정렬정반",
                (5200, 3900, 4150), 900),
        Station("jbr", "PV-JBR-201-GA-3101", "JBR-201 · 케이블·정션박스 3헤드 제거셀",
                (7050, 3050, 2800), 900),
        # REV.22-P01 장비 단축 3건. 근거는 전부 도면 부품표 실측이다.
        #
        # 1. 가드 여유 균등화. 가드는 ±5,750 대칭인데 장비는 −5,550…+4,300 이라 상류 200 ·
        #    하류 1,450 이었다 — 하류 1,450 을 설명하는 정비 치수가 없다. 플랜트에서 가장
        #    넉넉한 X 가드 여유(유리 후단 475)를 양쪽에 적용해 상류는 오히려 넓어진다.
        # 2. B안 — 인계롤러 공용. AFR 이 자기 투입롤러(3,700)를 따로 갖는 대신, JBR 저마킹
        #    롤러 끝단과 AFR 12구역 베드를 1,800 짜리 공용 인계롤러로 직결한다. JBR 롤러는
        #    정반 하류로 이미 2,175 남아 있어 늘릴 필요가 없다. 셀 상류면이 −4,650 → −2,725
        #    (SA-L)로 올라와 −1,925.
        # 3. A안 — 프레임 회수함 횡배치. 3,200×2,100 을 90° 돌려 2,100×3,200 으로 놓으면
        #    셀 길이가 1,100 줄고 대신 폭이 4,700 → 5,600 늘어난다 (회수함 Z ±1,600 +
        #    프레임함 횡인출 1,200 MIN). 장비 밴드 7,100 안이라 존은 y 1,200…6,800 이다.
        #
        # 장비 −2,725…+3,225 (5,950) + 475×2 = 6,900.
        Station("afr", "PV-AFR-101-GA-4101", "AFR-101 · 알루미늄 프레임 분리셀",
                (6900, 5600, 2800), 950),
        # V-4 적용: 잔사 검사와 레시피 판정을 연마 후 한 광학 스테이션으로 통합.
        # CV-102 는 광학을 떼고 이송만 3,700→2,800, 통합 검사대는 2,000→2,400. 순 −500 mm.
        Station("post", "PV-GLASS-301-GA-5101", "CV-102 · SG-301 · GI-301/302 통합 유리 후단",
                (8900, 4900, 2800), 950),
        # X 7,000 → 8,700: R-A/R-B 캐리지 2열의 부품 실측 span 이 8,675 라 외형을 넘었다.
        # REV.22-P01 에서 두 가지가 더 나왔다. 이건 단축이 아니라 결함 수정이라 +850 이다.
        #  * 2열 캐리지가 같은 Z(−2,350 / +2,350)에서 X 로 250 mm 겹쳐 있었다. 피치 2,500 이
        #    모듈 길이 2,750 보다 짧다 — 3D 실측 피치 2,900 으로 맞췄다.
        #  * 안전가드(−2,000…5,000)가 캐리지 뒤끝(5,975)보다 975 앞에서 끝나 위험원을 감싸지
        #    못했다. 다른 셀과 같은 X 여유 475 로 6,450 까지 늘렸다.
        # 결과 X: GBR 셔틀 −3,100 … 가드 6,450 = 9,550.
        Station("buffer", "PV-GBR-301-GA-5201", "GBR-301 · R-A/R-B/HOLD 레시피 버퍼",
                (9550, 7100, 2800), 1050),
    )
}

#: 존 시드 — (키, 표기, Y 시작, 주기, 장비 없는 존의 (X, Y, H) 폴백).
#: 'gate' 는 JB/AFR 인계 맵 구간이라 대응하는 설비 셀이 없다.
ZONE_SEED: tuple[tuple[str, str, int, str, tuple[int, int, int] | None], ...] = (
    ("afu", "LFT-A/B · BFC", 0, "2 Bay·비전·반전", None),
    ("robot", "RB-101 · PT", 1600, "직접픽업·정렬", None),
    ("jbr", "JBR-201", 2025, "케이블·JBOX", None),
    ("gate", "JB/AFR", 2450, "MAP", (HANDOFF_CLEARANCE_MM, 2200, 2800)),
    ("afr", "AFR-101", 1200, "단축→장축", None),
    ("post", "CV · SG · GI", 1100, "이송·연마·통합검사", None),
    ("buffer", "GBR · BUFFER", 0, "R-A/R-B/HOLD", None),
)


def build_zones() -> list[Zone]:
    """존을 상류부터 이어 붙인다. 폭·높이는 대응하는 셀 외형에서 파생한다."""
    zones: list[Zone] = []
    cursor = 0
    for key, label, y0, note, fallback in ZONE_SEED:
        station = STATIONS.get(key)
        if station is not None:
            span_x, span_y, height = station.envelope
        elif fallback is not None:
            span_x, span_y, height = fallback
        else:  # pragma: no cover - 시드 자체가 잘못된 경우
            raise ValueError(f"{key} 존에 설비도 폴백 치수도 없다")
        zones.append(Zone(key, label, cursor, cursor + span_x, y0, y0 + span_y, height, note))
        cursor += span_x
    return zones


def plant_envelope_mm() -> tuple[int, int, int]:
    """영구설비 전체 포락선 (X, Y, Z). Y 는 장비 밴드 + 통로."""
    zones = build_zones()
    return (
        zones[-1].x1_mm,
        MACHINE_BAND_Y_MM + AISLE_WIDTH_MM,
        max(zone.height_mm for zone in zones),
    )


def aisle_band_mm() -> tuple[int, int]:
    """보행·정비 통로의 Y 구간. 어떤 존과도 겹치지 않아야 한다."""
    return MACHINE_BAND_Y_MM, MACHINE_BAND_Y_MM + AISLE_WIDTH_MM
