# Dynamic-industry

Dynamic industry Development

## 태양광 셀 은(Ag) 회수 부유선별 설비

폐 태양광 모듈(c-Si)에서 박리한 셀 분획으로부터 **은(Ag)** 을 부유선별로 농축하는
설비의 설계와 계산 코드. 셀 분획을 공급하는 상류 분리설비(DG-HK60)는
[3D 운전 콘솔](docs/drawings/pv-delamination-3d.html)로 별도 정리했다.

- 평균 **0.30 t/h**, 최대 **0.50 t/h** (건조 고체 기준)
- **세척수 bias 연속 부선조 1단, Ø350 mm × 라이저 2.4 m** (대안: 기계식 러퍼·스캐빈저·클리너 3단)
- 전처리로 **어트리션 스크러버 팔각조 AF 390 mm × 2단** — 두 안 공통, **EVA 박리 전용**
  (은을 띄우는 것은 뒤의 부선조 몫)
- 떨어진 EVA 는 **ES-1 · ES-2 EVA 부선**(기포제만, 포수제 앞)이 걷어낸다 — 2안 동체
  Ø1.0 m × 2셀 + Ø0.4 m 를 그대로 써서, 부선 급광의 자유 EVA ≤ 0.1 wt%, 은 손실 ≤ 0.3 %
- 박리 성능을 시험으로 정할 **파일럿 시험 셀 PAS-1** (REV C) — 회분 20 kg, AF 260 mm, 1.5 kW 6극 직결,
  AS-1 과 기하 상사, 블랙파우더(31~75 µm) EVA 박리 비에너지 곡선 → AS-1 판정 (플랜트 설비 아님).
  H₂ 벤치·시운전 회분(P-0A·P-0B)을 먼저 하고 인터록을 둔다
- AS-1 박리 목표는 정한 값이 아니라 **정광 품위 여유에서 나온다** — 부착 EVA 잔류 ≤ 0.099 wt%
  (설계 EVA 에서 95.1 %), 판정은 E95
- **ES 앞은 청수, CT-1 부터 공정수** — 회수수의 포수제가 ES 로 들어오면 은이 EVA 산물로 뜬다.
  그 대가로 ES 앞 청수만큼(1안 최대 6.4 m³/h)이 블리드로 나가 처리된다 (대안 W3 · W4)
- Ag 회수율 **99.7 %** (부선) · **계통 99.64 %** (EVA 산물 손실 포함), 정광 **6.36 kg/h @ 46.3 wt% Ag** (농축비 78배)
- 기액 체류시간 **1 분**, 설치 전력 **6.52 kW** (탈수 보조설비 포함) + 전처리 **15.01 kW**
  (어트리션 4.77 + 떨어진 EVA 분리 10.24)
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
| [docs/drawings/ag-flotation-drawings.html](docs/drawings/ag-flotation-drawings.html) | **설계도 11매** — 공정 흐름도(필터프레스 라인 포함), 부선조 상세 단면도, 장치 대안 비교도, 중공축 급기 상세, 셀별 상세 3매, 전처리 계통도, 어트리션 셀 상세, 파일럿 시험 셀 PAS-1, 떨어진 EVA 분리 계통도 (브라우저로 열 것) |
| [docs/drawings/ag-flotation-3d.html](docs/drawings/ag-flotation-3d.html) | **3D 조립·분해도** — 러퍼·스캐빈저·클리너 3단 스키드 + 농축조·필터프레스, 셀당 20개 부품 분해 (브라우저로 열 것) |
| [docs/drawings/pv-delamination-3d.html](docs/drawings/pv-delamination-3d.html) | **DG-HK60 3D 운전 콘솔** — 부선 공정에 셀 분획을 공급하는 상류 분리설비. 5단 밀폐 IR 캐리지 순환, 이동 계단 칼날(SHK-101) 박리 — 셀모듈과 백시트를 유리에서 한 장으로, 일곱 조각이 따로 떠서 유리를 따라간다(칼날 모듈 추종), 15단계 공정 재생, 컷어웨이·분해도, 전기·PLC·제작도면 15종, **부품도 169장 · 모듈 조립도 13장**, 열수지 계산기 (브라우저로 열 것) |
| [docs/dg-hk60-rfq.html](docs/dg-hk60-rfq.html) | **DG-HK60 상세설계 기술사양서 (RFQ)** — 상세설계 용역 발주용. 요구성능·설계기준·기계/전기/안전 요구사항·납품물·FAT/SAT·입찰자 확인사항 16건 — 열린 15건 · OI-11 해소 (브라우저로 열 것, A4 인쇄 가능) |
| [docs/dg-hk60-fab-spec.html](docs/dg-hk60-fab-spec.html) | **DG-HK60C 제작 지침서 (FAB-001)** — 볼트 등급·체결력·조임토크, 용접 각장, 부재 판두께·재질, 기초 앵커 매입깊이·연단거리를 하중에서 유도한 문서. 접합부 11개소·부재 27종·앵커 6개소·ITP 16단계 (브라우저로 열 것, A4 인쇄 가능) |
| [docs/dg-hk60-assembly.html](docs/dg-hk60-assembly.html) | **DG-HK60C 조립 지침서 (ASM-001)** — 도면을 처음 보는 사람이 조립도·부품도만으로 세울 수 있게 쓴 문서. 안전·공구·도면 읽는 법·볼트 조이는 법·모듈 사이의 순서·모듈별 67단계 (부품 카탈로그에서 생성) |
| [docs/dg-hk60-procurement.html](docs/dg-hk60-procurement.html) | **DG-HK60C 조달 지침서 (PRC-001)** — 자재 발주표(1차원 절단 배치를 푼 정척 본수·시트 매수) · 운반 분할(세우는 순서를 따르는 차수표) · 구매품 사양 60종 (부품 카탈로그에서 생성) |
| [docs/dg-hk60-analysis.html](docs/dg-hk60-analysis.html) | **DG-HK60C 구조·열해석 보고서 (CAL-001)** — 직접강성법 프레임, 1차원 과도 열전도, **IR 뱅크 복사 유속 + 면내 2차원 전도**, **램프 지지·관통 상세**, **정상상태 열수지**, **칼날 모듈 추종**(패드 평면도가 만드는 유리 굴곡 · 몬테카를로). 닫힌해 15건으로 해석기를 검증하고 구조 14건·열 13건·IR 8건·지지 7건·수지 8건·에어록 8건을 푼 뒤, 해석이 만든 요구 26건과 **해석이 못 보는 것**을 적었다 (여섯 해석 모듈에서 생성) |
| [docs/dg-hk60-pilot.html](docs/dg-hk60-pilot.html) | **DG-HK60C 파일럿 시험 계획서 (PIL-001)** — 온도–박리력 곡선·칼날 수명·유리 수율·면내 온도 균일도·열수지. 시료 수를 요구정밀도에서 거꾸로 풀어(t 분위수·Clopper–Pearson) 총 454장·2단계로 잡았다 (계획 모델에서 생성) |
| [docs/dg-hk120-twin-cell.html](docs/dg-hk120-twin-cell.html) | **DG-HK120C 트윈 셀 검토서** — 1챔버·2분리셀(계단 칼날) 수평병렬로 처리량을 배로 올리는 안의 배치·전력·인터록 검토 (브라우저로 열 것) |

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
| [docs/drawings/mp50-part-drawings.html](docs/drawings/mp50-part-drawings.html) | **부품 상세도면 A3 29매** — 제작품 33종을 27장에 담았다 (소물은 합본). 장마다 소재 규격, 완성 치수, 기하공차, 표면, 가공 순서, 검사. 규격·구매품은 도면 대신 명세 한 장 (브라우저로 열 것) |
| [docs/drawings/mp50-3d.html](docs/drawings/mp50-3d.html) | **3D 분해 · 컷어웨이 · 부품 단독 보기 콘솔** — 아세이별 분해, 단면 컷어웨이, 부품 하나만 떼어 보기, 분산→동시 정지→자연 층분리 재생. 입자는 검증 모듈과 같은 Stokes 식으로 움직인다 (브라우저로 열 것) |
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
python tools/mp50_drawings.py                                    # 아세이 제작도면 15매
python tools/mp50_parts.py                                       # 부품 상세도면 29매
```

### 구조

```
src/mp50_separator/
  geometry.py    Z 기준좌표계 · 원뿔 폐합 · 용적 · 노즐 (여기만 고치면 된다)
  components.py  아세이 A~K 부품표 — 질량은 기하에서 계산한다
  conflicts.py   원본 3종의 치수 충돌 8건과 해결 근거
  checks.py      제작성·기능성 검증 14건 (조립 / 기능)
tools/
  mp50_drawings.py   기하에서 아세이 제작도면 HTML 을 생성
  mp50_parts.py      제작품마다 부품 상세도면 HTML 을 생성
  _mp50_draft.py     ISO 128 제도 프리미티브 (두 생성기 공용)
```

도면은 둘 다 **코드에서 생성**한다. 손으로 고치면 `tests/test_mp50_drawings.py`
와 `tests/test_mp50_parts.py` 의 재생성 검사가 깨진다. 부품도는 `components.py`
의 조달 구분(제작/규격/구매/가공)을 그대로 따르므로, 제작품을 하나 추가하고
도면을 잊으면 생성 자체가 실패한다.

### 사용법

패키지가 `src/` 레이아웃이므로 설치 없이 실행할 때는 `PYTHONPATH=src` 를 붙인다.

```bash
PYTHONPATH=src python -m flotation_design                               # 계산서 출력
PYTHONPATH=src python -m flotation_design -o docs/design-calculation.md # 파일로 저장
PYTHONPATH=src python -m flotation_design --peak-tph 0.6                # 처리량 변경
python -m unittest discover -s tests -t .                               # 테스트 (1,438건)

# 부품 카탈로그 — 형상·치수·재질에서 질량과 자중을 계산한다
python3 tools/parts.py                     # 카탈로그 리포트 (품목·질량·자중 검증)
python3 tools/fab_spec.py                  # 제작 지침서 계산 근거
python3 tools/gen_parts_js.py --write      # 카탈로그 → 콘솔의 부품도·조립도 데이터
python3 tools/gen_assembly_doc.py --write  # 카탈로그 → 조립 지침서 HTML
python3 tools/procure.py                   # 조달 계산 (자재·운반·구매)
python3 tools/gen_procure_doc.py --write   # 카탈로그 → 조달 지침서 HTML

# 해석 — 형상이 바뀌면 결과가 따라 움직인다
python3 tools/fea.py                       # 구조 해석기 검증 (닫힌해 5건)
python3 tools/therm.py                     # 열 해석기 검증 (닫힌해 5건)
python3 tools/analysis_structural.py       # 구조해석 S1~S14 (S10 계단 칼날 칼끝 예산 · S12~S14 칼날 모듈 추종)
python3 tools/glass_follow.py              # 유리면 추종 — 패드 평면도 몬테카를로 · 곧은 칼날 vs 일곱 모듈 · 유리 굽힘
python3 tools/analysis_thermal.py          # 열해석 T1~T13 + 요구 R1~R6
python3 tools/analysis_irbank.py           # IR 뱅크 배치 IR1~IR8 + 요구 RIR1~RIR5
python3 tools/lampmount.py                 # 램프 지지·관통 LM1~LM7 + 요구 RLM1~RLM5
python3 tools/heatbalance.py               # 정상상태 열수지 HB1~HB8 + 요구 RHB1~RHB5
python3 tools/gen_analysis_doc.py --write  # 해석 → 보고서 HTML
python3 tools/pilot_plan.py                # 파일럿 시료 수·규모·일정
python3 tools/gen_pilot_doc.py --write     # 계획 → 시험 계획서 HTML
python3 tools/sync_fab_doc.py --write      # 제작 지침서의 파생 숫자를 계산기와 맞춤
python3 tools/knife_stepped.py             # 계단형 핫나이프 — 조각별 힘 · 물림 램프 · 사이클 · 계단 높이의 창
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
  attrition.py      어트리션 스크러버 · 희석박스 (EVA 박리, 공통 전처리)
  attrition_pilot.py 파일럿 시험 셀 PAS-1 · 방식 선정 · 직결 모터 극수 · 회분→연속 환산 · 수소 배기 · 시험 결과 정리(E·X·E_X)
  eva_separation.py 떨어진 EVA 분리 — 잔막 모델 · 기포 충돌 속도상수 · 품위 여유 배분 · 요구 제거율 · S-1 판정선
  kinetics.py       2속도(Kelsall) 반응속도 — 속부선/지연부선/비부선, 회분식·연속
  circuit.py        흐름 추적 · 복합입자 동반 · 순환부하 수렴 (2안)
  rfc.py            flux 상사 스케일업 · bias · 연속 부선조 성능 (1안)
  sizing.py         기계식 셀 체적/형상, 로터, 급기, 정광 배출 부하
  reagents.py       약제 투입량 (고체 기준 g/t · 물 기준 ppm)
  conditioning.py   조건조 사이징
  plant.py          두 안 조립 + 농축조 · 계통 물수지(청수 / 공정수 · W1 · W3 · W4) · AS-1 박리 목표
  report.py         Markdown 계산서 생성
```

### 모델에서 알아둘 두 가지

**정광 품위에는 물리적 상한이 있다.** Ag 는 Si 웨이퍼에 소결된 전극이라 부상할 때
Si 코어를 달고 온다. 부상 Ag 1 kg 당 맥석 1.1 kg 이면 상한은 1/(1+1.1) = 47.6 wt%
이고, 문헌의 두 최고 품위(48.8 / 46.7 wt%)가 모두 여기서 멈췄다. 세척수로 제거되지
않으므로 **클리너를 더 붙여도 넘을 수 없다.**

**어트리션 스크러버는 EVA 박리만 맡는다.** 은을 띄우는 것은 뒤의 부선조가 한다.
그래서 이 설비는 부선 성적이 아니라 **부착 EVA 제거율**과 **미립 생성량**으로만
판정하고, 부선 계산에는 EVA 를 뗀 효과를 넣지 않았다. 이 원료(31~75 µm 미분)에서
EVA 가 떨어진다는 시험 근거가 아직 없어서, **전량 바이패스 배관과 시험 계획(T-1~T-4)**
을 설계에 넣었다. 시험은 파일럿 셀 PAS-1 이 맡는다 — 박리 목표(95.1 %)에 드는 회분
비에너지(E95)가 2.70 kWh/t 이하면 AS-1 그대로, 4.35 이하면 모터만 교체한다. 목표는 1안
정광이 보증 품위(40 wt%)까지 받아들일 수 있는 EVA 에서 자유 EVA 한도를 뺀 나머지다.
박리가 확인되지 않으면 바이패스로 두거나 열분해로 간다 — 이 설비는 계통 전력의 22 % 를 쓴다.

**떨어진 EVA 는 따로 걷어낸다.** EVA 는 비중 0.95 의 소수성 박편이라 그대로 두면
부선조에서 정광으로 간다. 중력으로는 수면적이 173 m² 나 들어 못 가르고, 포수제 앞에서
**기포제만 쓰는 EVA 부선(ES-1 · ES-2)** 으로 걷어낸다 — 포수제가 없으면 은은 젖어서
펄프에 남는다. 성능은 떨어진 박편의 **크기**가 정한다 (20 µm 95 %, 10 µm 60 %). 대가는
전력이다 — ES 가 10.24 kW 로 계통의 48 % 를 쓴다. ES 앞에는 **청수만** 쓴다 — 회수
공정수의 포수제가 들어오면 정상 부선 속도의 0.17 % 만으로 EVA 산물 Ag 가 한도(0.3 %)에
닿는다. ES 가 서면 AS-1 급광을 멈춘다 (부선을 계속 돌리면 정광이 18 wt% 로 떨어진다).
세 단계를 회수수로 잇는 연쇄 시험 C-1 이 부착 EVA 가 뜨는지와 물 계통을 확정한다.

**연속 부선조에는 반응속도 모델을 쓰지 않는다.** 완전혼합조가 아니므로 기액 체류시간
1분을 CSTR 식에 넣으면 Ag 회수율이 63 % 로 나와 실측(~100 %)과 맞지 않는다.
flux 상사로 스케일업하면 수력학적 조건이 보존되므로 실증 측정값을 이월한다.
