# Dynamic-industry

Dynamic industry Development

## 태양광 셀 은(Ag) 회수 부유선별 설비

폐 태양광 모듈(c-Si)에서 박리한 셀 분획으로부터 **은(Ag)** 을 부유선별로 농축하는
설비의 설계와 계산 코드.

- 평균 **0.30 t/h**, 최대 **0.50 t/h** (건조 고체 기준)
- **세척수 bias 연속 부선조 1단, Ø350 mm × 라이저 2.4 m** (대안: 기계식 러퍼·스캐빈저·클리너 3단)
- Ag 회수율 **99.7 %**, 정광 **6.36 kg/h @ 46.3 wt% Ag** (농축비 78배)
- 기액 체류시간 **1 분**, 설치 전력 **6.52 kW** (탈수 보조설비 포함)
- 황화제·pH 조정제·억제제 없음 — 약제는 포수제·촉진제·기포제 3종뿐

### 설계 근거

실증 논문 두 편의 데이터를 1차 근거로 삼고, 모델이 그 실험값을 재현하도록 보정했다.
`tests/test_references.py` 가 재현성을 검증하므로, 설계 기준을 고쳐 문헌과 어긋나면
테스트가 실패한다.

1. Saffarian, Galvin, Firouzi, *Minerals Engineering* **242** (2026) 110189 — 회분식 실증
2. Saffarian, Galvin, Firouzi, ChemRxiv preprint (2026), doi:10.26434/chemrxiv.15003814/v1 — 연속 실증

> [2] 는 프리프린트이며 저자들이 호주 가출원(No. 2025902821)을 제출한 상태다.
> 상업화 전 실시권 검토가 필요하다.

### 문서

| 문서 | 내용 |
|---|---|
| [docs/flotation-separator-design.md](docs/flotation-separator-design.md) | 설계 사양서 — 근거, 두 안, 계장·안전, 시운전 계획 |
| [docs/design-calculation.md](docs/design-calculation.md) | 설계 계산서 (코드에서 자동 생성) |
| [docs/drawings/ag-flotation-drawings.html](docs/drawings/ag-flotation-drawings.html) | **설계도 7매** — 공정 흐름도(필터프레스 라인 포함), 부선조 상세 단면도, 장치 대안 비교도, 중공축 급기 상세, 셀별 상세 3매 (브라우저로 열 것) |
| [docs/drawings/ag-flotation-3d.html](docs/drawings/ag-flotation-3d.html) | **3D 조립·분해도** — 러퍼·스캐빈저·클리너 3단 스키드 + 농축조·필터프레스, 셀당 20개 부품 분해 (브라우저로 열 것) |
| [docs/drawings/pv-preprocess-plant.html](docs/drawings/pv-preprocess-plant.html) | **전처리 플랜트 통합 설계도** — 상류 공정(투입·반전·정션박스 제거·프레임 분리·유리 검사·레시피 버퍼)의 3D 작동 시뮬레이션과 셀별 2D 제작도·3D 분해도·전체 배치도 (브라우저로 열 것) |

### 사용법

패키지가 `src/` 레이아웃이므로 설치 없이 실행할 때는 `PYTHONPATH=src` 를 붙인다.

```bash
PYTHONPATH=src python -m flotation_design                               # 계산서 출력
PYTHONPATH=src python -m flotation_design -o docs/design-calculation.md # 파일로 저장
PYTHONPATH=src python -m flotation_design --peak-tph 0.6                # 처리량 변경
python -m unittest discover -s tests -t .                               # 테스트 (404건)
```

설치하면 `PYTHONPATH` 없이 쓸 수 있다.

```bash
pip install -e .
flotation-design
```

`--average-tph` / `--peak-tph` 를 바꾸면 RFC와 농축·여과 보조설비는 새 유량으로
재산정한다. 기계식 셀 동체는 `design_basis.py` 의 확정 치수를 유지해 새 처리량에서
성능을 계산하며, 목표에 미달하면 계산서에 경고와 필요 치수를 표시한다.

축약차수 입자 애니메이션은 선택 의존성을 설치해 만든다. 이는 CFD/DEM 검증이 아니라
기포 상승·입자 침강·부착/탈착을 보여주는 교육용 모델이다.

```bash
pip install -e '.[simulation]'
python tools/flotation_sim.py fc201-simulation.mp4
```

### 구조

```
src/flotation_design/
  references.py     문헌 실증값 — 설계의 1차 근거 (여기 수치는 논문에서 온 것)
  design_basis.py   설계 전제 — 급광 조성, 속도상수, 셀 사양, 약제 (여기만 고치면 됨)
  feed.py           급광 조성 · 슬러리 물성
  kinetics.py       2속도(Kelsall) 반응속도 — 속부선/지연부선/비부선, 회분식·연속
  circuit.py        흐름 추적 · 복합입자 동반 · 순환부하 수렴 (2안)
  rfc.py            flux 상사 스케일업 · bias · 연속 부선조 성능 (1안)
  sizing.py         기계식 셀 체적/형상, 로터, 급기, 정광 배출 부하
  reagents.py       약제 투입량 (고체 기준 g/t · 물 기준 ppm)
  conditioning.py   조건조 사이징
  plant.py          두 안 조립 + 농축조
  report.py         Markdown 계산서 생성
src/pv_preprocess/
  layout.py         전처리 플랜트 배치 — 셀 외형에서 존·전체 포락선 파생
  electrical.py     전기 인입 부하 집계 · 차단기·계약전력 산정
  wiring.py         분전반 위치·트레이 경로·실제 케이블 길이 산정
  servos.py         전동기·서보 축 일람 — 피더 예산·브레이크 불변식
  acoustics.py      소음·진동 예측 모델과 저감 설계 근거
  thermal.py        열수지·냉각 계통 — 오일쿨러·반내 냉각·환기 사이징
  materials.py      내구 재질 기준 — 환경별 규칙과 부품 단위 적용
  vision.py         비전 센서 최소화 검토 결과 (안전 채널은 보호 대상)
```

### 모델에서 알아둘 두 가지

**정광 품위에는 물리적 상한이 있다.** Ag 는 Si 웨이퍼에 소결된 전극이라 부상할 때
Si 코어를 달고 온다. 부상 Ag 1 kg 당 맥석 1.1 kg 이면 상한은 1/(1+1.1) = 47.6 wt%
이고, 문헌의 두 최고 품위(48.8 / 46.7 wt%)가 모두 여기서 멈췄다. 세척수로 제거되지
않으므로 **클리너를 더 붙여도 넘을 수 없다.**

**연속 부선조에는 반응속도 모델을 쓰지 않는다.** 완전혼합조가 아니므로 기액 체류시간
1분을 CSTR 식에 넣으면 Ag 회수율이 63 % 로 나와 실측(~100 %)과 맞지 않는다.
flux 상사로 스케일업하면 수력학적 조건이 보존되므로 실증 측정값을 이월한다.

## 태양광 패널 전처리 플랜트 (상류 공정)

부유선별 앞단에서 폐 모듈을 받아 정션박스·케이블·알루미늄 프레임을 떼어내고 유리를
분리·검사해 레시피별로 적재하는 통합 라인. 설계도는
[docs/drawings/pv-preprocess-plant.html](docs/drawings/pv-preprocess-plant.html) 한 장에
3D 작동 시뮬레이션과 도면 프로그램(2D 제작도·3D 분해도·전체 배치도·도면 목록·부품표)이
모두 들어 있다.

- 영구설비 **44,750 × 8,300 × 5,050 mm** — 셀별 GA 외형에서 파생
- JBR–AFR 인계 게이트는 3D 실측 가드-가드 이격(325 mm)에 앵커·심 여유를 얹은 350 mm
- AFR-101 11,500 → 6,900 mm — ±5,750 대칭이던 가드에 여유 475 균등 적용, JBR 출구 롤러와 AFR 베드를 1,800 공용 인계롤러로 직결(셀별 투입 컨베이어 폐지), 프레임 회수함을 90° 횡배치(길이 −1,100 / 폭 +900)
- GBR 버퍼 8,700 → 9,550 mm — 2열 캐리지 X 250 mm 겹침(피치 2,500 < 모듈 2,750)과 위험원을 못 감싸던 안전가드를 3D 실측 피치 2,900 · 여유 475 로 수정
- 스택 → 반전카세트 투입 경로(분리헤드·포획빔·셔틀·승강)를 도면에 전개하고 여섯 단계 시퀀스를 뷰에 표시
- 캐리지 슬롯 적재기 설계 — 데크-도크 순틈(225 mm) 트윈마스트 + 2단 텔레스코픽 콤포크(스트로크 3,200)·선단받이 레일·크로스샤프트 동기. 독립 설계 3안을 기하·운영 렌즈로 적대 심사한 조합안이며 셀 외형 증가 0
- 정션박스 제거(7단계)·프레임 분리(6단계)·슬롯 적재(6단계) 시퀀스를 각 시트 뷰와 표제란에 표시, 3D 적재 애니메이션도 분기→승강→삽입으로 단계화
- AFR 베드-CV-102 사이 2,950 mm 무지지 공백(패널 2,500 초과)을 반출롤러 2,000 으로 폐쇄
- 장비 밴드 Y 0–7,100, 보행·정비 통로 Y 7,100–8,300 (장비 포락선 **밖**)
- 설비 셀 7개 + JB/AFR 인계 게이트 1개, 부품 160품목
- 전기 인입 3Φ 4W 380 V · 설치 68.0 kW · 수요 50.2 kW · 주 차단기 125 AF/100 AT · 계약 75.4 kVA
- 배선 MDB-101 벽부 x=20,000(부하중심) · 전력 케이블 133.1 m + 인입 26.5 m · EtherCAT 체인/FSoE 링 (EL-1005~1008)
- 전동기 서보 29축 21.1 kW + 인버터·기어드 — 축 일람·라이브 동작 확인 (설계·PLC·검증 탭)
- 소음·진동 근접 88 → 70 dBA·통로 최악 59.9 dBA — 저감 장치 4종 반영 (NV-1009)
- 열수지 실내 37.4 kW·환기 22,500 m³/h — HPU 오일쿨러 2기·반 열교환기 3면 (TH-1010)
- 내구 재질 유리분 Mohs 6–7 대응 AR400 라이너·S355 분체도장 사양 (MT-1011)
- 3D 장면 색·조명은 테마와 무관한 고정 팔레트 — 배경·안개·바닥만 라이트/다크를 따른다
- 비전 최소화 검토 반영 — 영상 헤드 7 → 4 (안전 센서는 감축 없음)
- 컷어웨이(단면)·분해를 메인 3D 영상과 도면 3D 분해도 양쪽에서 조작 — 절단축 5종(X 상/하류, Y 앞/뒤, Z 위), 절단 위치와 분해 거리는 슬라이더로 조정

배치 수치는 `src/pv_preprocess/layout.py`, 전기 부하는 `electrical.py`, 배선 길이는 `wiring.py`, 비전 구성은
`vision.py` 가 각각 단일 출처다. 존 X·Y·높이는 셀 외형에서 파생한다. `tests/test_pv_preprocess.py` 가 도면 안의 리터럴과 이 모델을 대조하므로
한쪽만 고치면 테스트가 실패한다. 존이 자기 장비보다 짧아지는 것, 통로가 장비에 덮이는 것,
부품이 자기 외형을 넘는 것은 불변식 테스트로 막는다.
