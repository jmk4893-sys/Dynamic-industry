# Dynamic-industry

Dynamic industry Development

## 태양광 셀 은(Ag) 회수 부유선별 설비

폐 태양광 모듈(c-Si)에서 박리한 셀 분획으로부터 **은(Ag)** 을 부유선별로 농축하는
설비의 설계와 계산 코드. 셀 분획을 공급하는 상류 분리설비(DG-HK60)는
[3D 운전 콘솔](docs/drawings/pv-delamination-3d.html)로 별도 정리했다.

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
| [docs/drawings/pv-delamination-3d.html](docs/drawings/pv-delamination-3d.html) | **DG-HK60 3D 운전 콘솔** — 부선 공정에 셀 분획을 공급하는 상류 분리설비. 5단 밀폐 IR 캐리지 순환, 고정 HKB/HKS 탠덤 박리, 15단계 공정 재생, 컷어웨이·분해도, 전기·PLC·제작도면 13종, 열수지 계산기 (브라우저로 열 것) |

## MP-50 염수 밀도분리 파일럿 장치

폐태양광 후처리 블랙파우더에서 **EVA·백시트를 실리콘 분말로부터 걷어내는** 소형
파일럿. 세 재질의 입경이 31~75 µm 로 겹쳐 체로는 나눌 수 없으므로, 염수(NaCl
0~18 wt%)의 밀도를 세 재질의 유효밀도 사이에 놓고 나눈다. 임펠러와 급기는
**분산 수단이지 분리 수단이 아니다** — 둘을 동시에 정지시킨 뒤의 자연 부상·침강이
분리다.

- 동체 **Ø400 ID × H600**, 원뿔 60° · 전용적 **89.86 L**, 운전 장입 **61.4 L**
- 아세이 A~K **11계통 · 부품 220개**, 건조질량 **146 kg**
- 교반축 Ø25 SUS316L, Ø300 4PBT45° 임펠러 2단, 배플 4매, 콘 급기 분산링

### 원본 도면 그대로는 제작이 되지 않는다

치수가 세 문서에 흩어져 있고 셋이 서로 다르다 — 연구문서 Rev.0, 도면
MP-50-P0-001, 도면 MP50-DR-000. 충돌 8건을 정리했고 그중 **2건은 그대로 두면
조립 자체가 불가능**하다.

| 번호 | 항목 | 원본 | 문제 |
|---|---|---|---|
| **C1** | 원뿔 높이 | H150 + 60° | Ø400 에서 Ø38 로 닫히지 않는다 (313.5 필요) |
| **C2** | 배플 폭 | 80 × 4매 | 안쪽 모서리 R114 가 Ø300 임펠러 팁 R150 과 **36 mm 겹쳐 축이 돌지 않는다** |

해결 근거는 [`conflicts.py`](src/mp50_separator/conflicts.py) 와 제작도면의
'원본 치수 충돌과 해결 근거' 절에 남겼다. C1 은 연구문서의 H346 을 **가상 정점높이**로
읽으면 동체 상단 Z946 · 커버 상면 Z951 · 전용적 89.9 L 가 한 원점에서 동시에
맞아떨어지므로 확정했고, C2 는 임펠러 Ø300 이 세 문서에 모두 같고 DOE·동력·Njs
모델이 그 위에 서 있으므로 배플 쪽을 35 mm 로 줄였다.

### 문서

| 문서 | 내용 |
|---|---|
| [docs/drawings/mp50-fabrication-drawings.html](docs/drawings/mp50-fabrication-drawings.html) | **제작도면 A3 15매** — 기준좌표·공차, 전체 조립도, 아세이 A~K, 동체·원뿔 전개도, 노즐표, 용접·검사 기준. 손으로 적은 치수가 없다 (브라우저로 열 것) |
| [docs/drawings/mp50-3d.html](docs/drawings/mp50-3d.html) | **3D 분해 · 컷어웨이 콘솔** — 아세이별 분해, 단면 컷어웨이, 분산→동시 정지→자연 층분리 재생. 입자는 검증 모듈과 같은 Stokes 식으로 움직인다 (브라우저로 열 것) |
| [docs/mp50-fabrication-spec.md](docs/mp50-fabrication-spec.md) | 제작 기준 요약 (코드에서 자동 생성) |

### 설계 검증에서 나온 것

검증 14건 중 조립 항목은 전부 통과했고, 기능 항목 2건이 WARN 이다. 둘 다
**장치가 아니라 시험계획을 고치라**는 뜻이다.

- **CHK-05** Zwietering Njs 가 135 rpm 인데 감속기 상한이 90 rpm 이라 여유가 없다 →
  최고속도 150 rpm 확보 권고 (축·동력·위험속도는 150 rpm 으로 검증했다)
- **CHK-10** 정치 600 s 로는 31 µm 백시트가 1 % 만 부상한다. Stokes 는 지름의
  제곱으로 가므로 미세분은 시간이 제곱으로 든다 → 정치시간 격자를 600~3600 s 로
  넓히고, 염도 격자에 22/26 wt% 를 넣을 것 (포화까지 올리면 상승속도 2.7 배).
  단 포화 염수까지 갈 경우 동체는 SUS304 가 아니라 SUS316L 이어야 한다.

### 사용법

```bash
PYTHONPATH=src python -m mp50_separator                          # 제작 기준 출력
PYTHONPATH=src python -m mp50_separator -o docs/mp50-fabrication-spec.md
python tools/mp50_drawings.py                                    # 제작도면 15매 생성
```

### 구조

```
src/mp50_separator/
  geometry.py    Z 기준좌표계 · 원뿔 폐합 · 용적 · 노즐 (여기만 고치면 된다)
  components.py  아세이 A~K 부품표 — 질량은 기하에서 계산한다
  conflicts.py   원본 3종의 치수 충돌 8건과 해결 근거
  checks.py      제작성·기능성 검증 14건 (조립 / 기능)
tools/
  mp50_drawings.py   기하에서 제작도면 HTML 을 생성
  _mp50_draft.py     ISO 128 제도 프리미티브
```

### 사용법

패키지가 `src/` 레이아웃이므로 설치 없이 실행할 때는 `PYTHONPATH=src` 를 붙인다.

```bash
PYTHONPATH=src python -m flotation_design                               # 계산서 출력
PYTHONPATH=src python -m flotation_design -o docs/design-calculation.md # 파일로 저장
PYTHONPATH=src python -m flotation_design --peak-tph 0.6                # 처리량 변경
python -m unittest discover -s tests -t .                               # 테스트 (428건)
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
```

### 모델에서 알아둘 두 가지

**정광 품위에는 물리적 상한이 있다.** Ag 는 Si 웨이퍼에 소결된 전극이라 부상할 때
Si 코어를 달고 온다. 부상 Ag 1 kg 당 맥석 1.1 kg 이면 상한은 1/(1+1.1) = 47.6 wt%
이고, 문헌의 두 최고 품위(48.8 / 46.7 wt%)가 모두 여기서 멈췄다. 세척수로 제거되지
않으므로 **클리너를 더 붙여도 넘을 수 없다.**

**연속 부선조에는 반응속도 모델을 쓰지 않는다.** 완전혼합조가 아니므로 기액 체류시간
1분을 CSTR 식에 넣으면 Ag 회수율이 63 % 로 나와 실측(~100 %)과 맞지 않는다.
flux 상사로 스케일업하면 수력학적 조건이 보존되므로 실증 측정값을 이월한다.
