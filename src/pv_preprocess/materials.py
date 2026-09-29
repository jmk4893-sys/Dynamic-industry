"""전처리 플랜트 내구 재질 기준 — 환경별 재질 규칙과 적용 결과.

재질 조사 요지 (도면의 MATERIAL_RULES 리터럴과 같은 값이어야 한다):

* 유리 파쇄분은 Mohs 6–7 의 연마재다. STS304 는 15–25 HRC 로 마모에
  약해 **부식 용도**로만 쓰고, 분진이 고속으로 스치는 면은 경화강·내마모강
  (58–65 HRC) 라이너나 고무 라이닝을 덧댄다.
* 실내 건조 환경의 구조 프레임은 S355 + 분체도장이 경제적이다. 단 도막이
  깨지면 그 자리부터 녹슬므로 도막 사양(80 µm)과 보수 점검을 명문화한다.
* 유압 발열·소음 대책과 마찬가지로, 규칙이 아니라 **적용된 부품**이 답이다 —
  APPLICATIONS 가 부품번호 단위의 전→후 재질 변경을 기록하고, 카탈로그
  재질 문자열과 어긋나면 테스트가 잡는다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialRule:
    env: str          # 사용 환경
    need: str         # 요구 성능
    material: str     # 선정 재질
    reason: str


@dataclass(frozen=True)
class Application:
    part_no: str      # 카탈로그 부품번호 ('SPEC' 은 사양서 항목)
    where: str
    before: str
    after: str        # 카탈로그 재질 문자열에 그대로 들어가야 하는 값


RULES: tuple[MaterialRule, ...] = (
    MaterialRule("구조 프레임 (실내 건조)", "강성·비용", "S355 + 분체도장 80 µm",
                 "건조 실내엔 도장 탄소강이 경제적 — 도막 손상부 보수 주기를 사양화"),
    MaterialRule("유리 분진 고속 접촉면 (후드·프리세퍼레이터·엘보)", "내마모",
                 "AR400 t4 교체식 라이너 (58 HRC 급)",
                 "유리분 Mohs 6–7 — STS304(15–25 HRC)는 마모에 약함, 경도로 받는다"),
    MaterialRule("분진 저속 접촉·청소 구역 (슈트·수거함)", "부식·청소성",
                 "STS304 t1.5 (기존 유지)",
                 "저속 낙하 구간은 마모보다 세척·방청이 지배"),
    MaterialRule("박리 칼날", "인성 + 경도", "SKD11 58–60 HRC (기존 유지)",
                 "공구강 열처리 — 원주 런아웃 관리 병행"),
    MaterialRule("유리 접촉 패드·진공컵", "저마킹·내마모", "실리콘 HTV / PU 70–80A (기존 유지)",
                 "유리면 흠집 방지가 우선 — 소모품으로 교체 주기 관리"),
    MaterialRule("방진·절연 요소", "내유·내후", "EPDM (유압 주변은 NBR)",
                 "오일 미스트 접촉부는 내유 고무가 필요"),
    MaterialRule("습식 세척 예비 구역", "내식", "STS316L (확장 대비 사양만)",
                 "현행 건식 공정엔 불요 — 습식 옵션 추가 시 적용"),
    # ── 외장 케이싱 (§46) ──────────────────────────────────────────────
    MaterialRule("외장 케이싱 판 (분진 비접촉·상시 접촉)", "마감 내구·경량",
                 "알루미늄 t1.5 아노다이징 (AA20 이상)",
                 "구조가 아니라 껍질이라 강도가 아니라 **마감 수명**이 지배한다. "
                 "분체도장은 사람이 매일 스치는 모서리부터 깎여 나가는데 아노다이징은 "
                 "산화막이 소재 자체라 그 자리가 생기지 않는다. 가벼워 기존 베이스 "
                 "빔에 매달 수 있어 바닥 앵커가 안 는다"),
    MaterialRule("관찰창", "충격·비산 방지", "폴리카보네이트 t6",
                 "유리는 깨지면 그 자체가 위험원이다 — 파쇄 유리를 다루는 라인에서 "
                 "창까지 유리로 둘 이유가 없다"),
)

APPLICATIONS: tuple[Application, ...] = (
    Application("AFR-DX-601", "집진 슬롯후드·프리세퍼레이터 내면",
                "슬롯후드/프리세퍼레이터/필터",
                "STS304+AR400 라이너 t4/프리세퍼레이터/필터"),
    Application("AFR-SG-301", "연마 헤드 분진 커버",
                "서보축/연마휠/컴플라이언스",
                "서보축/연마휠/컴플라이언스/AR 분진커버"),
    Application("SPEC", "구조 프레임 전체 (S355)",
                "S355 (도장 사양 불명)", "S355 + 분체도장 80 µm·보수도장 사양"),
    Application("SPEC", "집진 덕트 엘보 (마모 집중부)",
                "아연도금 강관", "엘보 STS304 t2 + 내마모 고무 라이닝"),
)


def applied_materials() -> dict[str, str]:
    """카탈로그에 실제로 반영돼야 하는 부품번호 → 재질 문자열."""
    return {app.part_no: app.after
            for app in APPLICATIONS if app.part_no != "SPEC"}
