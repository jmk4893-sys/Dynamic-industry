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

# ── 이송 높이 ────────────────────────────────────────────────────────────
#: 라인 이송 높이 (mm) — **이송면(롤러 윗면)** 기준이다.
#:
#: REV.44 까지 이 값이 셀마다 달랐다: robot·jbr 900 / afr·post 950 / buffer·grm 1,050.
#: 그런데 도면은 JBR 저마킹 롤러와 AFR 베드를 잇는 1,800 mm 를 "공용 인계롤러"라고
#: 적고 있었다 — **롤러 하나가 두 높이를 동시에 가질 수 없으므로 성립하지 않는다.**
#: 3D 는 그 단차를 더 크게(1,025 → 1,100, 75 mm) 그리면서 완충 램프도 두지 않았다.
#: 같은 문제를 상류에서는 `JB-201 높이보정 인계 롤러` 13본으로 풀어 놓았는데,
#: 그 램프는 애초에 이 단차가 없었으면 필요 없는 물건이다.
#:
#: 발주처 확정: **robot·jbr·afr·post 네 셀을 950 으로 통일**한다. PT-101 정렬정반
#: 출구부터 GI-302 까지 약 22 m 가 한 높이가 되어 인계롤러 공용이 실제로 성립하고,
#: 높이보정 램프가 필요 없어진다. 남는 단차는 post→buffer 100 mm 하나인데 버퍼는
#: 슬롯 승강(340…2,236)으로 그것을 흡수한다.
LINE_TRANSFER_MM = 950

#: 한 이송면을 나눠 쓰는 셀 — 이 셀들은 전부 LINE_TRANSFER_MM 여야 한다.
SHARED_LINE: tuple[str, ...] = ("robot", "jbr", "afr", "post")

#: 이송 롤러 지름 (mm). 이송면(윗면)에서 롤러 중심을 얻는 데 쓴다 — 3D 는 중심으로
#: 그리고 GA 는 윗면으로 적으므로, 둘을 잇는 값이 하나 있어야 어긋나지 않는다.
ROLLER_D_MM = 90


def roller_axis_mm(transfer_mm: int | None = None) -> float:
    """이송면 높이에서 롤러 중심 높이 (mm)."""
    return (LINE_TRANSFER_MM if transfer_mm is None else transfer_mm) - ROLLER_D_MM / 2


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
#: **REV.45 에서 이 게이트는 없어졌다** — 아래 INTEGRATED_CELL 참조. 값은 통합 전
#: 이격의 근거로 남긴다.
HANDOFF_CLEARANCE_MM = 350


# ── 통합 제거셀 — JBR 과 AFR 을 한 기계로 ────────────────────────────────
#: 베이스·가드·안전존·이송면을 공유하는 스테이션. **택트는 잃지 않는다** — 두
#: 스테이션이 한 베드 위에 5 m 넘게 떨어져 있어 지금처럼 파이프라인으로 돈다
#: (JBR 이 다음 장을 무는 동안 AFR 이 앞 장을 벗긴다).
#:
#: 공유하는 것은 넷이다. ① 한 베이스 프레임 ② 한 가드 인클로저·한 안전존
#: ③ 한 이송면(LINE_TRANSFER_MM) ④ JB/AFR-301 인계 인터페이스가 셀 간 핸드셰이크가
#: 아니라 기계 내부 스텝이 된다 — 데이터 게이트 하드웨어·ACK·CRC 재검증이 없어진다.
#:
#: **공유할 수 없는 것**: 지지 정반과 클램프 포탈. 두 스테이션이 5,375 mm 떨어져
#: 각자 자기 패널을 물고 있으므로 판을 하나로 만들 수 없다. (검토 단계에서 이것을
#: 공유 항목으로 적었던 것은 두 공정이 같은 자리에서 일어난다고 잘못 본 것이다 —
#: 같은 자리에서 하면 직렬 84 s 가 되어 처리량이 41 % 떨어진다.)
INTEGRATED_CELL: tuple[str, ...] = ("jbr", "afr")

#: 가드-장비 X 여유 (mm) — 플랜트 표준. AFR 이 REV.22-P01 에서 이 값으로 균등화
#: 했고, JBR 은 125 mm 뿐이었다. 통합하면서 양 끝에 같은 기준을 적용한다.
GUARD_CLEARANCE_X_MM = 475

#: 통합셀 안에서 두 스테이션 구조가 마주보는 최소 이격 (mm). 사이에 가드 벽이
#: 없으므로 앵커 베이스플레이트와 배선 트레이만 지나가면 된다. 250 은 그 둘이
#: 지나는 최소치이면서, 반씩 나눠 가져도 두 스테이션 외형이 정수로 떨어진다 —
#: 200 으로 잡으면 외형이 홀수(7,375·6,125)가 되어 2D 부재 중심이 0.5 mm 로 나온다.
STATION_JUNCTION_MM = 250

#: 각 스테이션의 장비 X 실측 스팬 (mm) — 도면 부품표 실측(가드 제외).
#: jbr −3,400…3,400 · afr −2,325…3,225 (REV.44 에서 단축 실린더가 정반 안으로
#: 들어가며 상류 −2,725 → −2,325 로 400 mm 물러났다).
STATION_HARDWARE_X_MM: dict[str, int] = {"jbr": 6800, "afr": 5550}


def integrated_cell_length_mm() -> int:
    """통합 제거셀 전장 (mm) — 바깥 가드 여유 + 두 스테이션 장비 + 접합부."""
    hardware = sum(STATION_HARDWARE_X_MM[k] for k in INTEGRATED_CELL)
    return (2 * GUARD_CLEARANCE_X_MM + hardware
            + STATION_JUNCTION_MM * (len(INTEGRATED_CELL) - 1))


def integrated_saving_mm() -> int:
    """통합으로 줄어든 길이 (mm) — 통합 전 jbr + gate + afr 대비."""
    before = 7050 + HANDOFF_CLEARANCE_MM + 6900
    return before - integrated_cell_length_mm()


def station_span_mm(key: str) -> int:
    """통합셀 안에서 한 스테이션이 갖는 X (mm). 접합부를 반씩 나눠 갖는다."""
    if key not in INTEGRATED_CELL:
        raise KeyError(key)
    half_junction = STATION_JUNCTION_MM // 2
    edge = GUARD_CLEARANCE_X_MM
    return STATION_HARDWARE_X_MM[key] + edge + half_junction


def stations_are_one_machine() -> bool:
    """두 스테이션 외형의 합이 통합셀 전장과 같은가."""
    return (sum(station_span_mm(k) for k in INTEGRATED_CELL)
            == integrated_cell_length_mm())


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
                # REV.27: 선언 5,050 이 3D 실측(VG-101 비전보 상단 5,150)보다 100 낮았다.
                # 기둥 0…4,950 + 보 200 이라 조립체가 5,150 이다 — 형상을 따라간다.
                (6800, 7100, 5150), 1880),
        # REV.22-P01: 3D 모델 실측으로 상세 전개하면서 분리헤드·셔틀·포획빔이 들어왔다.
        # 부품 실측 span X 4,940 · Y(깊이) 2,360 · Z(상하) 4,290 — 셔틀이 픽업면까지 나가고
        # 포획빔 수납 카세트가 중앙벽 쪽으로 물리므로 (3,600, 2,900, 3,500) 으로는 못 담는다.
        # bfc 는 ZONE_SEED 에 없는 부품 조립도라 전장에는 영향이 없다.
        # REV.22-P02: 승강기둥을 포탈(문형)로 재배치 — 종전 기둥·LM가이드가 반전축 선상에
        # 서서 셔틀·승강 패널을 관통했다(3D 스윕 실측 t 7.5–12.4 s). 기둥이 통과대역 밖
        # (z −1,290/+950)으로 나가며 외형 (5,000, 2,400) → (5,100, 2,900).
        # REV.27: 반전축을 3,300 → 3,430 으로 올렸다. 캐리지 상단(2,180)과 링 하단
        # 사이가 130 mm 뿐이라 이송면이 링에 22 mm 까지 붙어 있었고, 그 대각 진입이
        # 엔드링 단면을 88 mm 파고들었다(실측). 링 상단이 4,290 → 4,420 이 되어
        # 외형 높이도 4,350 → 4,500 으로 따라 올라간다 (여유 80).
        Station("bfc", "PV-BFC-101-ASM-2201", "BFC-101A/B · 단장 분리·셔틀·승강·180° 반전카세트",
                (5100, 2900, 4500), 2100),
        Station("robot", "PV-RBPT-101-GA-2301", "RB-101 · EOAT · PT-101 정렬정반",
                (5200, 3900, 4150), LINE_TRANSFER_MM),
        # REV.45 통합 제거셀 — AFR 과 한 베이스·한 가드다. 외형이 7,050 → 7,375 로
        # **늘어난다**: 종전 가드 여유가 상·하류 125 mm 뿐이라 플랜트 표준 475 에
        # 한참 못 미쳤고, 통합하면서 상류에 그 기준을 적용했기 때문이다. 하류는
        # 가드 벽이 없어져 접합부 125 만 갖는다 (475 + 6,800 + 125).
        Station("jbr", "PV-JBR-201-GA-3101", "JBR-201 · 케이블·정션박스 제거 스테이션",
                (7400, 3050, 2800), LINE_TRANSFER_MM),
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
        #
        # REV.44: 단축 유압을 정반 **안**에 넣으면서 상류면이 −2,725 → −2,325 로
        # 400 mm 물러났다 (장비 5,550).
        # REV.45 통합 제거셀 — JBR 과 한 베이스·한 가드다. 상류는 가드 벽이
        # 없어져 접합부 125 만 갖고, 하류만 표준 475 를 쓴다 (125 + 5,550 + 475).
        Station("afr", "PV-AFR-101-GA-4101", "AFR-101 · 알루미늄 프레임 분리 스테이션",
                (6150, 5600, 2800), LINE_TRANSFER_MM),
        # V-4 적용: 잔사 검사와 레시피 판정을 연마 후 한 광학 스테이션으로 통합.
        # CV-102 는 광학을 떼고 이송만 3,700→2,800, 통합 검사대는 2,000→2,400. 순 −500 mm.
        Station("post", "PV-GLASS-301-GA-5101", "CV-102 · SG-301 · GI-301/302 통합 유리 후단",
                (8900, 4900, 2800), LINE_TRANSFER_MM),
        # X 7,000 → 8,700: R-A/R-B 캐리지 2열의 부품 실측 span 이 8,675 라 외형을 넘었다.
        # REV.22-P01 에서 두 가지가 더 나왔다. 이건 단축이 아니라 결함 수정이라 +850 이다.
        #  * 2열 캐리지가 같은 Z(−2,350 / +2,350)에서 X 로 250 mm 겹쳐 있었다. 피치 2,500 이
        #    모듈 길이 2,750 보다 짧다 — 3D 실측 피치 2,900 으로 맞췄다.
        #  * 안전가드(−2,000…5,000)가 캐리지 뒤끝(5,975)보다 975 앞에서 끝나 위험원을 감싸지
        #    못했다. 다른 셀과 같은 X 여유 475 로 6,450 까지 늘렸다.
        # 결과 X: GBR 셔틀 −3,100 … 가드 6,450 = 9,550.
        Station("buffer", "PV-GBR-301-GA-5201", "GBR-301 · R-A/R-B/HOLD 레시피 버퍼",
                (9550, 7100, 2800), 1050),
        # REV.23: 유리제거(박리) 라인을 별도 앱이 아니라 플랜트의 한 존으로 들여왔다.
        # 종전에는 버퍼에서 하이퍼링크만 걸어 뒀는데, 그러면 전처리 플랜트가 유리를
        # 벗기지 못한 채 끝난다 — 배치·포락선·전력·소음 어디에도 잡히지 않았다.
        #
        # X 는 후단 앱의 하드웨어 목록에서 공정 순서대로 이어 붙여 파생한다.
        #   M0 투입 정렬·6존 진공테이블      2,750 (패널 2,500 + 그립 여유 125×2)
        #   M1 5단 단열랙 + IR + LI/TS/IDX   3,300 (랙 2,800 + 양주 마스트 250×2)
        #   TDM-201 2단 탠덤 박리            3,400 (칼날 행정 300+2,500 + 헤드 300×2)
        #   GR-201 단거리 저충격 롤러          900
        #   DS-301 하강식 유리 직접적재대     2,750 (패널 2,500 + 125×2)
        #   장비 합계 13,100 + 가드 여유 475×2 = 14,050
        # EX-101 방출셔틀과 RT-101 빈 캐리지 복귀는 랙 **하부**를 되돌아가므로 X 를
        # 늘리지 않는다. WR-101 백시트 권취와 CB-201/CV-301 셀 계통은 측면 배출이라
        # Y 로 나간다.
        #
        # Y 6,100 = 주 흐름 2,100 (패널 1,400 + 베드 구조 350×2)
        #         + 백시트 격리배출 1,400 + 셀/슈레더 2,000 + 정비 접근 600.
        # Z 3,600 = 하부 복귀 600 + 5단 랙 2,100 + 상부 IR·배기 500, 마스트 상단까지.
        #
        # 이 외형은 **계획값**이다 — 후단 앱은 설치 풋프린트를 공표하지 않아 자기
        # 하드웨어 목록에서 파생했다. 벤더 GA 가 오면 이 한 줄만 고치면 존·포락선·
        # 배치도·전력이 전부 따라온다.
        Station("grm", "PV-GRM-401-GA-6101",
                "GRM-401 · 5단 적재·60-IR 순차가열·2단 탠덤 유리제거셀",
                (14050, 6100, 3600), 1050),
    )
}

#: 존 시드 — (키, 표기, Y 시작, 주기, 장비 없는 존의 (X, Y, H) 폴백).
#: 'gate' 는 JB/AFR 인계 맵 구간이라 대응하는 설비 셀이 없다.
ZONE_SEED: tuple[tuple[str, str, int, str, tuple[int, int, int] | None], ...] = (
    ("afu", "LFT-A/B · BFC", 0, "2 Bay·비전·반전", None),
    ("robot", "RB-101 · PT", 1600, "직접픽업·정렬", None),
    # REV.45 — jbr·afr 은 한 기계의 두 스테이션이다 (INTEGRATED_CELL). 사이에 있던
    # 'gate' 존 350 은 두 가드 벽 사이의 이격이었는데, 벽이 하나로 합쳐지며 없어졌다.
    ("jbr", "JBR-201", 2025, "케이블·JBOX (통합셀 상류 스테이션)", None),
    ("afr", "AFR-101", 1200, "단축→장축 (통합셀 하류 스테이션)", None),
    ("post", "CV · SG · GI", 1100, "이송·연마·통합검사", None),
    ("buffer", "GBR · BUFFER", 0, "R-A/R-B/HOLD", None),
    # 통로측(Y 7,100)에 붙여 셀 컨테이너·백시트 회수를 통로에서 빼낸다.
    ("grm", "GRM-401 유리제거", 1000, "적재·가열·박리·3계통", None),
)


def transfer_steps_mm() -> tuple[tuple[str, str, int], ...]:
    """이웃한 존 사이의 이송면 단차 (상류, 하류, mm). 0 이면 롤러를 공용할 수 있다."""
    zones = [z for z in build_zones() if z.key in STATIONS]
    out = []
    for up, down in zip(zones, zones[1:]):
        step = (STATIONS[down.key].transfer_height_mm
                - STATIONS[up.key].transfer_height_mm)
        out.append((up.key, down.key, step))
    return tuple(out)


def shared_conveyor_pairs() -> tuple[tuple[str, str], ...]:
    """롤러를 공용할 수 있는 이웃 쌍 — 이송면이 같은 곳만."""
    return tuple((a, b) for a, b, step in transfer_steps_mm() if step == 0)


def the_shared_line_is_one_height() -> bool:
    """한 이송면을 쓰기로 한 셀들이 실제로 같은 높이인가."""
    return all(STATIONS[k].transfer_height_mm == LINE_TRANSFER_MM
               for k in SHARED_LINE)


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


# ── 미해결 — 3D 씬 격자와 존 표가 어긋난다 ──────────────────────────────
#: 존 표는 셀 GA 포락선을 상류부터 이어 붙여 만든다. 3D 씬은 그와 **별도로** 각 셀
#: 그룹의 x 를 직접 박아 두었고, 나중에 붙인 것들(GRM-401 셀·외장 케이싱·EC 명판)
#: 만 이 표를 따랐다. 헤드리스 실측으로 두 격자가 AFR 아래에서 갈라지는 것을 확인
#: 했다 (world m 기준):
#:
#:   셀       존 표              3D 실측                      판정
#:   jbr      -12.75 … -5.70    PT-101   -11.91 … -9.29      맞음
#:   afr       -5.38 …  0.75    베이스 프레임 0.55 … 11.95   하류면이 존을 넘음
#:   post       0.75 …  9.65    SG-301   10.79 … 11.15       존 밖으로 나감
#:   buffer     9.65 … 19.20    GBR 셔틀 12.12 … 15.32       안쪽
#:   grm       20.00 … 34.05    셀 베이스 20.00 … 34.05      맞음
#:
#: 존 표는 AFR→버퍼에 24,600 mm 를 주는데 3D 는 같은 구간을 20,000 mm 로 그린다.
#: 어느 쪽이 맞는지는 **발주처 확인 사항**이다 — 3D 가 맞으면 전장을 그만큼 줄일 수
#: 있고, 존 표가 맞으면 3D 가 설비를 빠뜨리고 있다. 고치는 길은 셋뿐이고 전부
#: 한 개정의 범위를 넘는다: ① 3D 셀 그룹을 존 격자로 옮긴다(하류 좌표가 전부 따라
#: 움직인다), ② 존 표를 실측으로 줄인다(전장·케이싱·배선이 따라온다), ③ 빠진
#: 설비를 3D 에 채운다. 그때까지 이 값을 여기 남겨 둔다 — 지워지면 검사가 잡는다.
SCENE_GRID_OPEN = "AFR→버퍼 구간에서 3D 셀 원점과 존 표가 어긋난다 (발주처 확인)"

#: 존 표가 AFR→버퍼에 주는 길이와 3D 가 실제로 그리는 길이의 차 (mm).
#: REV.45 통합으로 존이 750 짧아지며 5,350 → 4,600 으로 줄었다
#: (gate 350 이 빠지고 jbr +350 · afr −750 이라 순 −750 이다).
SCENE_GRID_GAP_MM = 4600

#: 3D 가 그 구간을 실제로 그리는 길이 (mm) — 실측.
SCENE_AFR_TO_BUFFER_MM = 20_000


def afr_to_buffer_zone_mm() -> int:
    """존 표가 AFR 상류면부터 버퍼 하류면까지 주는 길이 (mm)."""
    zones = {z.key: z for z in build_zones()}
    return zones["buffer"].x1_mm - zones["afr"].x0_mm


def scene_grid_gap_mm() -> int:
    """존 표와 3D 실측의 차 — 이 값이 0 이 되면 격자가 맞은 것이다."""
    return afr_to_buffer_zone_mm() - SCENE_AFR_TO_BUFFER_MM


def scene_grid_is_registered() -> bool:
    return scene_grid_gap_mm() == 0


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
