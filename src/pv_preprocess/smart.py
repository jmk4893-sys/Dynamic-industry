"""스마트 팩토리 계층 — 계측·식별·네트워크·데이터의 단일 출처.

이 플랜트는 이미 서보 36축·전동기 17대·비전 4헤드·안전 PLC 를 갖고 있다.
스마트 팩토리는 **없던 설비를 새로 세우는 일이 아니라, 이미 돌고 있는 것이
무엇을 하고 있는지 읽어 내는 계층을 얹는 일**이다. 그래서 이 파일의 데이터량은
전부 `servos.py`·`vision.py`·`campaign.py` 에서 파생한다 — 축을 하나 늘리면
회선 용량과 저장 용량이 같이 늘어나고, 도면과 테스트가 그것을 따라온다.

계층은 ISA-95 를 따른다.

* **L0 현장** — 센서·구동기. 서보 드라이브·인버터·계측기.
* **L1 제어** — 안전 PLC·모션 PLC (EtherCAT · FSoE). **이미 있다.**
* **L2 감시** — SCADA·HMI. 존별 엣지 캐비닛이 여기서 데이터를 모은다.
* **L3 운영** — MES·히스토리안·OEE. 랙실 SVR-902.
* **L4 기업** — ERP. 이 플랜트 밖이다.

**L1 과 L3 사이는 단방향이 원칙이다.** 히스토리안·MES 는 읽기만 하고, 생산
지령을 제외한 쓰기는 하지 않는다. AI 추론 결과도 마찬가지로 PLC 에 직접
쓰지 않고 **판정 보조 신호**로만 내려간다 — 안전 관련 채널(PLr·PFHd)은
계산이 다시 서기 전에는 어떤 경우에도 건드리지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import campaign, handoff, servos, vision
from .layout import build_zones

# ── 운전 전제 ────────────────────────────────────────────────────────────
#: 연간 가동시간 (h). 1교대 8 h × 250 일 기준의 **계획값**이다.
#: 라벨 공급량·저장 용량이 전부 여기서 나오므로 교대 계획이 확정되면
#: 이 한 줄만 고치면 된다. 2교대면 4,000, 3교대면 6,000 이다.
OPERATING_HOURS_PER_YEAR = 2_000.0

#: 히스토리안 보존 연수 — 저장 용량 산정 기준.
RETENTION_YEARS = 3.0


# ── L0 계측 — 드라이브가 이미 내보내는 것 ────────────────────────────────
# 새 센서를 달기 전에, **이미 붙어 있는 드라이브가 무엇을 말하고 있는지**부터
# 센다. 서보 드라이브는 지령/실위치/추종오차/토크/전류/온도를 PDO 로 내보내고
# 있고, 지금은 아무도 그것을 저장하지 않는다.

#: 서보 드라이브 1축이 내보내는 신호 수와 히스토리안 표본율.
#: 추종오차는 기구 마찰이 늘 때 가장 먼저 움직이는 신호라 100 Hz 가 필요하다.
SERVO_SIGNALS = 6
SERVO_SAMPLE_HZ = 100.0

#: 인버터 1대 — 전류·주파수·토크추정·방열판온도. 추세만 보면 되므로 10 Hz.
INVERTER_SIGNALS = 4
INVERTER_SAMPLE_HZ = 10.0

#: 직입·소프트스타터 — 접점상태와 CT 전류뿐이다. 1 Hz.
DOL_SIGNALS = 2
DOL_SAMPLE_HZ = 1.0

#: 아날로그 표본 1개 크기 (byte). float32.
SAMPLE_BYTES = 4


def drive_counts() -> dict[str, int]:
    """구동 방식별 대수 — `servos.py` 에서 센다. 축을 늘리면 여기가 따라온다."""
    counts = {"서보": 0, "인버터": 0, "소프트스타터": 0, "직입": 0}
    for axis in servos.SERVO_AXES + servos.MOTORS:
        counts[axis.drive] = counts.get(axis.drive, 0) + axis.qty
    return counts


def drive_stream_bytes_per_s() -> float:
    """드라이브 텔레메트리 전체 대역 (B/s)."""
    counts = drive_counts()
    return (
        counts["서보"] * SERVO_SIGNALS * SERVO_SAMPLE_HZ
        + counts["인버터"] * INVERTER_SIGNALS * INVERTER_SAMPLE_HZ
        + counts["소프트스타터"] * INVERTER_SIGNALS * INVERTER_SAMPLE_HZ
        + counts["직입"] * DOL_SIGNALS * DOL_SAMPLE_HZ
    ) * SAMPLE_BYTES


# ── L0 계측 — 새로 다는 것 ───────────────────────────────────────────────


@dataclass(frozen=True)
class Instrument:
    """신규 계측·식별 기기 한 종류."""

    tag: str
    zone: str              # 설치 존 (layout 의 zone key) 또는 'plant' = 전역
    name: str
    qty: int
    signals: int           # 한 대가 내보내는 신호 수
    sample_hz: float
    panel: str             # 급전 분전반
    watts: float           # 1대 소비전력 (W)
    purpose: str
    unlocks: str           # 이 기기가 없으면 못 하는 AI 과제 (ai.py 의 태그)

    @property
    def bytes_per_s(self) -> float:
        return self.qty * self.signals * self.sample_hz * SAMPLE_BYTES

    @property
    def group_w(self) -> float:
        return round(self.qty * self.watts, 1)


#: 신규 계측·식별 기기.
#:
#: 넣는 기준은 하나다 — **그 신호로 무엇을 결정할 것인지가 있어야 넣는다.**
#: "있으면 좋다"는 이유로 붙인 센서는 데이터만 늘리고 판단을 못 바꾼다.
#: 그래서 각 행에 그 기기가 열어 주는 AI 과제 태그(`unlocks`)를 적는다.
INSTRUMENTS: tuple[Instrument, ...] = (
    # 진동 — 회전기 베어링·불평형. 센서 안에서 FFT 를 돌려 특징만 올린다.
    # 원파형 10 kHz × 3축을 그대로 올리면 센서 1대가 240 kB/s 인데, 특징
    # 16개를 1 Hz 로 올리면 64 B/s 다. 3,750배 차이라 회선 설계가 달라진다.
    Instrument("VIB-901", "afu", "HPU-101 유압펌프 3축 진동", 1, 16, 1.0,
               "LP-INST", 6.0, "펌프·전동기 베어링 열화 추세", "AI-05"),
    Instrument("VIB-902", "afr", "HPU-601 유압펌프 3축 진동", 1, 16, 1.0,
               "LP-INST", 6.0, "7.5 kW 펌프 — 라인 최대 유압원", "AI-05"),
    Instrument("VIB-903", "post", "SG-301 연마 스핀들 3축 진동", 2, 16, 1.0,
               "LP-INST", 6.0, "휠 마모·불평형 — 유리 흠집의 선행지표", "AI-05"),
    Instrument("VIB-904", "post", "DX-601 집진 블로워 3축 진동", 2, 16, 1.0,
               "LP-INST", 6.0, "임펠러 분진 부착 불평형", "AI-05"),
    Instrument("VIB-905", "grm", "GRM 배기·냉각 블로워 3축 진동", 2, 16, 1.0,
               "LP-INST", 6.0, "배기가 서면 실내 열부하가 1.5배가 된다", "AI-05"),
    Instrument("VIB-906", "grm", "CV-301 슈레더 3축 진동", 1, 16, 1.0,
               "LP-INST", 6.0, "이물 유입·칼날 결손", "AI-05"),
    # 전력 — 피더별. 부하 분해(load disaggregation)의 입력이자 역률·THD 실측.
    Instrument("PM-901", "plant", "피더별 스마트 전력량계 (V·I·P·Q·PF·THD)",
               12, 8, 1.0, "LP-INST", 10.0,
               "역률 0.90·고조파 가정을 실측으로 대체", "AI-03"),
    # 온도 — IR 계면. 지금은 체류시간 226 s 를 고정으로 쓰는데,
    # 계면이 실제로 몇 °C 인지 아무도 모른다. 이 센서가 없으면 AI-06 은 못 한다.
    Instrument("PY-901", "grm", "5단 랙 데크별 계면 방사온도계", 5, 2, 5.0,
               "LP-INST", 8.0, "박리 계면 200 °C 도달 판정", "AI-06"),
    Instrument("RTD-901", "plant", "존별 실내 온습도", 7, 2, 0.2,
               "LP-INST", 2.0, "열수지 33,000 m³/h 검증", "AI-03"),
    # 배기 — EVA 는 200 °C 에서 초산을 낸다. 그 농도가 계면 연화의 지표다.
    Instrument("VOC-901", "grm", "IR 배기덕트 VOC (초산·알데하이드)", 1, 3, 1.0,
               "LP-INST", 15.0, "가열 종점 판정 + 배출 관리", "AI-08"),
    Instrument("DP-901", "plant", "집진 필터 차압", 2, 1, 1.0,
               "LP-INST", 3.0, "필터 막힘 — 탈진 주기 최적화", "AI-05"),
    Instrument("PM25-901", "plant", "실내 분진 PM2.5/PM10", 3, 2, 0.2,
               "LP-INST", 5.0, "유리분 비산 — 연마·슈레더 구간", "AI-03"),
    # 유량 — 공압. 누설은 스마트 팩토리에서 가장 회수가 빠른 항목이다.
    Instrument("FL-901", "plant", "압축공기 주관 유량·압력", 1, 3, 1.0,
               "LP-INST", 6.0, "무부하 시간대 누설량 산출", "AI-03"),
    # 품질 — 박리 완전도. GRM 출구에 카메라가 없으면 AI-07 은 못 한다.
    Instrument("VS-401", "grm", "박리 완전도 검사 카메라 (12 MP · 확산조명)",
               1, 0, 0.0, "LP-INST", 120.0,
               "백시트/EVA 잔막 판정 — 데이터량은 비전 항목에서 센다", "AI-07"),
    # 식별 — 패널 ID 는 **JB-VS-005 로 이미 있다**. 새로 다는 것은 캐리지 쪽이다.
    Instrument("RF-901", "buffer", "버퍼 캐리지 RFID 리더", 2, 1, 0.2,
               "LP-INST", 8.0, "패널 ID ↔ 캐리지 슬롯 결속", "AI-01"),
    Instrument("RF-902", "grm", "GRM 5단 랙 캐리지 RFID 리더", 1, 1, 0.2,
               "LP-INST", 8.0, "가열 이력을 장 단위로 잇는다", "AI-06"),
    Instrument("WI-901", "afu", "투입 리프트 중량계", 2, 1, 5.0,
               "LP-INST", 12.0, "장당 질량 — 유리 두께·구성 추정", "AI-01"),
)


def instrument_stream_bytes_per_s() -> float:
    """신규 계측기 전체 대역 (B/s). 비전은 별도로 센다."""
    return sum(item.bytes_per_s for item in INSTRUMENTS)


def instrument_watts() -> float:
    return round(sum(item.group_w for item in INSTRUMENTS), 1)


# ── L0 계측 — 비전. 데이터량의 지배항이다 ────────────────────────────────
#
# 라인스캔 1대가 드라이브 53대를 합친 것보다 70배 넘는 데이터를 낸다.
# 스마트 팩토리 회선·저장 설계는 사실상 비전 설계다.


@dataclass(frozen=True)
class ImageStream:
    """영상 헤드 1대가 패널 1장마다 만드는 이미지."""

    head: str
    zone: str
    pixels: int            # 장당 총 화소
    bytes_per_px: int
    per_hour: float        # 이 헤드를 통과하는 장/h

    @property
    def bytes_per_panel(self) -> int:
        return self.pixels * self.bytes_per_px

    @property
    def bytes_per_s(self) -> float:
        return self.bytes_per_panel * self.per_hour / 3600.0


#: 라인스캔 해상도 (mm/px). 유리 잔사는 0.1 mm 급을 봐야 판정이 선다.
LINESCAN_RESOLUTION_MM = 0.1

#: 후단 데크 상한 모듈 (mm) — handoff 의 데크 확장과 같은 값이어야 한다.
PANEL_MAX_MM = (2_500, 1_400)


def panels_per_h() -> float:
    """투입 비전을 통과하는 장/h — **전손까지 포함한 전량**.

    전손은 판정으로 걸러지는 것이지 안 찍히는 것이 아니다. 오히려 전손 영상이
    AI-01 의 가장 귀한 학습 표본이다 (연간 공급이 가장 적은 클래스).
    """
    s = campaign.summary()
    return round(s["panels"] / s["run_s"] * 3600.0, 1)


def line_panels_per_h() -> float:
    """라인에 실제로 들어가는 장/h — 전손 배출을 뺀 값. campaign 의 정본."""
    return campaign.summary()["throughput_per_h"]


def image_streams() -> tuple[ImageStream, ...]:
    """영상 스트림 — 존치 헤드(`vision.HEADS`)와 신규 VS-401 에서 파생.

    통과 물량이 헤드마다 다르다. 세 값을 구분하지 않으면 대역이 틀린다.

    * 투입 VS-101A/B — 전손까지 **전량** 찍는다 (판정을 하려면 찍어야 한다).
    * JBR VS-201A — 라인에 들어간 것만. 전손은 여기까지 안 온다.
    * 유리 검사 GI-302·VS-401 — R-A 정상 유리만. `handoff` 의 정본을 쓴다.
    """
    total_per_h = panels_per_h()
    entered_per_h = line_panels_per_h()
    normal_per_h = handoff.sheet_glass_per_h()
    line_px = (round(PANEL_MAX_MM[0] / LINESCAN_RESOLUTION_MM)
               * round(PANEL_MAX_MM[1] / LINESCAN_RESOLUTION_MM))
    kept = {head.tag for head in vision.HEADS if head.kept}
    rows = []
    if "VS-101A" in kept:
        # 투입 판정 — 5 MP 면적 카메라 2대, 장당 1프레임씩.
        rows.append(ImageStream("VS-101A", "afu", 5_000_000, 1, total_per_h))
    if "VS-101B" in kept:
        rows.append(ImageStream("VS-101B", "afu", 5_000_000, 1, total_per_h))
    if "VS-201A" in kept:
        # ROI 6곳 크롭 — 전면 재취득이 아니라 좌표시드 주변만 본다 (V-2 근거).
        rows.append(ImageStream("VS-201A", "jbr", 6 * 500_000, 1, entered_per_h))
    if "GI-302" in kept:
        # 연마 후 통합 검사 — 라인스캔. 정상 유리만 통과한다.
        rows.append(ImageStream("GI-302", "post", line_px, 1, normal_per_h))
    # 신규 박리 완전도 — 면적 12 MP, 장당 1프레임. 정상 유리 흐름을 탄다.
    rows.append(ImageStream("VS-401", "grm", 12_000_000, 1, normal_per_h))
    return tuple(rows)


def vision_raw_bytes_per_s() -> float:
    return sum(stream.bytes_per_s for stream in image_streams())


#: 무작위 표본 보존율 — 정상품도 이만큼은 남겨야 분포 이동(drift)을 본다.
SAMPLE_RETENTION = 0.02


def flagged_ratio() -> float:
    """이미지를 통째로 남겨야 하는 장의 비율.

    투입 판정에서 정상이 아닌 것(유리 깨짐·전손)은 전부 남긴다. 실제 검사
    NG 율은 시운전 전에는 모르므로, **캠페인의 실측 구성비를 계획 대용값**으로
    쓴다. run-at-rate 로 확정해야 하는 값이다.
    """
    counts = campaign.condition_counts()
    total = sum(counts.values())
    return round((total - counts["정상"]) / total, 4)


def vision_retention() -> float:
    """영상 보존율 — 불량 전량 + 정상 표본."""
    return round(flagged_ratio() + SAMPLE_RETENTION, 4)


def vision_retained_bytes_per_s() -> float:
    return vision_raw_bytes_per_s() * vision_retention()


# ── L2 데이터 — 공정 태그 ────────────────────────────────────────────────
#: 서보 1축이 PLC 수준에서 갖는 상태 태그 수 (지령·상태·알람·인터록 등).
PLC_TAGS_PER_AXIS = 8
#: 존 1곳의 공용 태그 (모드·인터록·가드·조명·집진 등).
PLC_TAGS_PER_ZONE = 24
#: 공정 태그 표본율 (Hz) — 상태값이라 1 Hz 면 충분하다.
PLC_SAMPLE_HZ = 1.0


def plc_tag_count() -> int:
    """SCADA 가 수집하는 공정 태그 수 — 축과 존에서 파생."""
    axes = sum(axis.qty for axis in servos.SERVO_AXES + servos.MOTORS)
    zones = len([zone for zone in build_zones() if zone.key != "gate"])
    return axes * PLC_TAGS_PER_AXIS + zones * PLC_TAGS_PER_ZONE


def plc_stream_bytes_per_s() -> float:
    return plc_tag_count() * PLC_SAMPLE_HZ * SAMPLE_BYTES


# ── 대역·저장 ────────────────────────────────────────────────────────────
#: 시계열 히스토리안 압축비 — 편차·스윙도어 압축의 통상값.
HISTORIAN_COMPRESSION = 8.0

#: 회선 설계 여유율 — 피크·재전송·성장 여유.
NETWORK_MARGIN = 2.0

#: 표준 이더넷 등급 (Mbps). 요구 대역 위의 등급을 고른다.
ETHERNET_GRADES_MBPS = (100, 1_000, 10_000, 25_000)


def timeseries_bytes_per_s() -> float:
    """비전을 뺀 시계열 전체 (B/s)."""
    return (drive_stream_bytes_per_s() + instrument_stream_bytes_per_s()
            + plc_stream_bytes_per_s())


def peak_bytes_per_s() -> float:
    """회선이 받아야 하는 순간 최대 (B/s) — 비전은 압축 전 원본으로 센다."""
    return timeseries_bytes_per_s() + vision_raw_bytes_per_s()


def required_mbps() -> float:
    """백본 요구 대역 (Mbps) — 여유율 포함."""
    return round(peak_bytes_per_s() * 8 / 1e6 * NETWORK_MARGIN, 1)


def backbone_grade_mbps() -> int:
    """백본 등급 (Mbps) — 요구 대역 위의 표준 등급."""
    for grade in ETHERNET_GRADES_MBPS:
        if grade >= required_mbps():
            return grade
    raise ValueError("요구 대역이 표준 등급을 넘는다 — 비전 스트림 재검토")


def annual_storage_tb() -> float:
    """연간 저장 증가 (TB) — 압축 시계열 + 보존 영상."""
    seconds = OPERATING_HOURS_PER_YEAR * 3600.0
    series = timeseries_bytes_per_s() / HISTORIAN_COMPRESSION * seconds
    images = vision_retained_bytes_per_s() * seconds
    return round((series + images) / 1e12, 2)


#: 저장 이중화 계수 — RAID6 + 스냅샷 여유.
STORAGE_REDUNDANCY = 1.5


def storage_capacity_tb() -> float:
    """설치해야 하는 실용량 (TB) — 보존연수 × 연간 × 이중화."""
    return round(annual_storage_tb() * RETENTION_YEARS * STORAGE_REDUNDANCY, 1)


# ── L3 시설 — 랙실·관제실 ────────────────────────────────────────────────


@dataclass(frozen=True)
class RackItem:
    """19인치 랙 탑재물 한 종류."""

    name: str
    units: int
    qty: int
    watts: float
    note: str
    redundant: bool = False   # 쌍을 이뤄 서로 다른 랙에 들어가야 하는가

    @property
    def group_u(self) -> int:
        return self.units * self.qty

    @property
    def group_w(self) -> float:
        return round(self.watts * self.qty, 1)


#: 랙 탑재물. 이중화하는 것은 qty 2 다.
RACK_ITEMS: tuple[RackItem, ...] = (
    RackItem("코어 스위치 (백본 링 종단)", 1, 2, 250.0,
             "이중화 — 한 대가 죽어도 링이 산다", redundant=True),
    RackItem("OT/IT 경계 방화벽", 1, 2, 120.0,
             "L1↔L3 단방향 원칙의 물리적 근거", redundant=True),
    RackItem("PTP(IEEE 1588) 그랜드마스터", 1, 1, 40.0,
             "서보 파형과 영상 프레임을 같은 시각으로 묶는다 — 없으면 상관분석이 안 된다"),
    RackItem("히스토리안 서버", 2, 1, 600.0, "시계열 압축 저장"),
    RackItem("MES·SCADA 서버", 2, 2, 600.0, "이중화", redundant=True),
    RackItem("엣지 추론 서버 (GPU 1장)", 4, 1, 2_500.0,
             "비전 추론은 현장에서 끝낸다 — 라인 판정을 외부망에 걸 수 없다"),
    RackItem("스토리지 (NVMe RAID)", 2, 1, 500.0, "보존 영상·시계열"),
    RackItem("UPS", 3, 2, 200.0,
             "랙마다 1대 — 한 랙의 배전이 죽어도 다른 랙이 산다", redundant=True),
    RackItem("패치패널·KVM", 1, 5, 10.0, "배선 정리"),
)

#: 표준 랙 규격 — 높이 U, 폭·깊이 (mm).
RACK_HEIGHT_U = 42
RACK_MM = (600, 1_100)
#: 랙 앞뒤 작업 이격 (mm) — 앞 1,200(서버 인출), 뒤 900(배선).
RACK_FRONT_CLEARANCE_MM = 1_200
RACK_REAR_CLEARANCE_MM = 900
#: 랙 점유율 상한 — 열·성장 여유로 이 이상 채우지 않는다.
RACK_FILL_LIMIT = 0.70


def rack_units_used() -> int:
    return sum(item.group_u for item in RACK_ITEMS)


def redundant_pairs() -> tuple[RackItem, ...]:
    """쌍을 이루는 품목 — 같은 랙에 들어가면 안 되는 것들."""
    return tuple(item for item in RACK_ITEMS if item.redundant)


def rack_count() -> int:
    """필요한 랙 대수 — 두 기준 중 큰 쪽.

    ① **U 공간** — 점유율 상한(70 %)을 넘지 않을 것.
    ② **이중화** — 쌍을 이루는 품목은 서로 다른 랙에 있을 것. 28U 는 42U 랙
       하나에 들어가지만, 코어 스위치 2대를 같은 랙에 넣으면 그 랙의 배전이나
       냉각이 죽는 순간 둘이 같이 죽는다. 이중화라고 적어 놓고 이중화가 아닌
       구성이 된다 — 공간이 남아도 랙을 나눈다.
    """
    usable = RACK_HEIGHT_U * RACK_FILL_LIMIT
    by_space = 1
    while rack_units_used() > usable * by_space:
        by_space += 1
    by_redundancy = 2 if redundant_pairs() else 1
    return max(by_space, by_redundancy)


def rack_heat_kw() -> float:
    """랙 발열 (kW) — 전부 열로 나온다."""
    return round(sum(item.group_w for item in RACK_ITEMS) / 1000.0, 2)


#: 랙실 냉방 성능계수 (COP) — 항온항습기 통상값.
RACK_COOLING_COP = 3.0


def rack_cooling_kw() -> float:
    """랙실 냉방 입력 (kW)."""
    return round(rack_heat_kw() / RACK_COOLING_COP, 2)


def server_room_mm() -> tuple[int, int, int]:
    """엣지·서버 랙실 SVR-902 (폭, 깊이, 높이 mm).

    랙을 한 줄로 세우고 앞뒤 이격을 붙인다. 공정 존이 아니라 **구획실**이라
    장비 밴드 안에 넣지 않는다 — 전기실과 같은 취급이다.
    """
    width = rack_count() * RACK_MM[0] + 600  # 양옆 300 씩 작업 여유
    depth = RACK_MM[1] + RACK_FRONT_CLEARANCE_MM + RACK_REAR_CLEARANCE_MM
    return (width, depth, 2_700)


#: 관제실 근무 인원과 1인 점유 면적 (mm²). 소방·피난 기준의 통상값.
CONTROL_ROOM_OPERATORS = 3
CONTROL_ROOM_AREA_PER_OPERATOR_MM2 = 4_500_000  # 4.5 m²/인
#: 관제실 깊이 (mm) — 콘솔 800 + 통행 1,000 + 비디오월 이격 1,600.
CONTROL_ROOM_DEPTH_MM = 3_400


def control_room_mm() -> tuple[int, int, int]:
    """통합 관제실 MCR-901 (폭, 깊이, 높이 mm).

    랙실과 **따로** 세운다. 랙 팬이 1 m 에서 65 dBA 급인데 관제실은 사무
    환경(45 dBA)이라, 같은 방에 넣으면 상주 근무가 성립하지 않는다.
    사이는 관측창으로 잇는다.
    """
    area = CONTROL_ROOM_OPERATORS * CONTROL_ROOM_AREA_PER_OPERATOR_MM2
    width = round(area / CONTROL_ROOM_DEPTH_MM / 100) * 100
    return (width, CONTROL_ROOM_DEPTH_MM, 2_700)


def facility_footprint_mm() -> tuple[int, int]:
    """두 방을 나란히 놓았을 때의 외곽 (폭, 깊이 mm). 사이벽 200 포함."""
    server = server_room_mm()
    control = control_room_mm()
    return (server[0] + 200 + control[0], max(server[1], control[1]))


# ── L2 시설 — 존별 엣지 캐비닛 ───────────────────────────────────────────
#: 엣지 캐비닛 외형 (폭, 깊이, 높이 mm). 통로 외곽벽 벽부라 깊이 300 이다 —
#: LP 분전반과 같은 규약이라 통로 유효폭 900 을 그대로 지킨다.
EDGE_CABINET_MM = (600, 300, 1_400)
#: 엣지 캐비닛 1면 소비전력 (W) — 관리형 스위치·I/O 집중기·PoE 급전.
EDGE_CABINET_W = 350.0
#: 무선 AP 1대와 커버 반경 (mm) — 작업자 단말·점검 태블릿용.
WIFI_AP_W = 30.0
WIFI_AP_RADIUS_MM = 6_000


def edge_zones() -> tuple[str, ...]:
    """엣지 캐비닛을 세우는 존 — 설비가 있는 존 전부. 게이트는 뺀다."""
    return tuple(zone.key for zone in build_zones() if zone.key != "gate")


def edge_cabinet_count() -> int:
    return len(edge_zones())


def wifi_ap_count() -> int:
    """AP 대수 — 전장을 커버 지름으로 나눈다."""
    zones = build_zones()
    length = zones[-1].x1_mm - zones[0].x0_mm
    return -(-length // (2 * WIFI_AP_RADIUS_MM))  # 올림


# ── 전력 ─────────────────────────────────────────────────────────────────
#: 관제실 워크스테이션·조명·공조 (kW) — 3인 상주 기준.
CONTROL_ROOM_KW = 1.8
#: 라인스캔 조명 등 비전 부대설비 (kW). 카메라보다 조명이 크다.
VISION_LIGHTING_KW = 1.5
#: 성장 예비 (kW) — 랙 증설·센서 추가 여유.
IT_SPARE_KW = 0.5


def it_installed_kw() -> float:
    """LP-IT (관제실·랙실) 설치 전력 (kW)."""
    return round(rack_heat_kw() + rack_cooling_kw() + CONTROL_ROOM_KW + IT_SPARE_KW, 1)


def instrument_installed_kw() -> float:
    """LP-INST (엣지·계측·네트워크) 설치 전력 (kW)."""
    edge = edge_cabinet_count() * EDGE_CABINET_W
    aps = wifi_ap_count() * WIFI_AP_W
    return round((edge + aps + instrument_watts()) / 1000.0 + VISION_LIGHTING_KW, 1)


def smart_installed_kw() -> float:
    return round(it_installed_kw() + instrument_installed_kw(), 1)


def summary() -> dict[str, object]:
    """도면(SM-1012)이 그대로 쓰는 요약."""
    return {
        "drive_counts": drive_counts(),
        "plc_tags": plc_tag_count(),
        "instruments": sum(item.qty for item in INSTRUMENTS),
        "timeseries_kb_s": round(timeseries_bytes_per_s() / 1000.0, 1),
        "vision_raw_mb_s": round(vision_raw_bytes_per_s() / 1e6, 2),
        "vision_retention_pct": round(vision_retention() * 100, 1),
        "vision_kept_mb_s": round(vision_retained_bytes_per_s() / 1e6, 2),
        "required_mbps": required_mbps(),
        "backbone_mbps": backbone_grade_mbps(),
        "annual_tb": annual_storage_tb(),
        "storage_tb": storage_capacity_tb(),
        "rack_u": rack_units_used(),
        "racks": rack_count(),
        "rack_heat_kw": rack_heat_kw(),
        "server_room_mm": list(server_room_mm()),
        "control_room_mm": list(control_room_mm()),
        "edge_cabinets": edge_cabinet_count(),
        "wifi_aps": wifi_ap_count(),
        "it_kw": it_installed_kw(),
        "inst_kw": instrument_installed_kw(),
        "smart_kw": smart_installed_kw(),
        "hours_per_year": OPERATING_HOURS_PER_YEAR,
    }
