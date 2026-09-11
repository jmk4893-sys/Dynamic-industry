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

### 파일럿 검증 설비 — MP-50 염수 밀도분리조 (Rev.B)

31~75 µm 블랙파우더에서 **EVA·백시트** 를 **Silicon-rich 분말** 로부터 갈라내는 회분식
파일럿이다. 부선기가 아니라 **염수 자연 밀도분리조** — 임펠러와 공기는 분산 수단이고,
분산이 끝나면 **동시에 정지**해 중력·부력만으로 FLOAT / SINK 를 진행시킨다.
세 재질의 입경대가 겹치므로 입도가 아니라 **유효밀도** 로 가른다.

- 동체 **ID Ø400 × t3 × 600** · 콘 60° 이론높이 346.4 · 전 용적 89.91 L
- 설계 액면 Z720 → **61.5 L** · 모든 좌표는 **콘 이론 정점 Z0** 기준
- 임펠러 **Ø300 4PBT45° × 2** (Z430 / Z610) · 30~90 rpm VFD · Njs ≈ 80 rpm
- 염도 12 / 15 / 18 wt% NaCl · 분산 링 Ø250 @ Z300 · 60-Ø1.0

기준좌표·공차·릴리즈 판정은 `MP50 염수밀도분리 전체연구문서 Rev.0` 을 승계했고,
문서에 없던 **운동학 검산과 간섭 검사**를 더했다. 그 결과 두 가지가 드러났다.

1. **연구문서의 배플 80 과 임펠러 Ø300 은 같은 탱크에 들어가지 않는다** — 38 mm 간섭.
   임펠러를 유지하고 배플 폭을 25 mm 로 줄여 간극 17 mm 를 확보했다 (재승인 대상).
2. **DOE 의 최대 정치시간 600 s 로는 모자란다** — 제품은 하부 배출과 상부 잔류의 **벌크 분할**이므로
   폴리머는 액면까지 갈 필요가 없고, 배출 8 L (분할면 Z284) 기준으로 밀도차만으로 Top polymer
   recovery **93.6 %** 가 나온다. 대신 지배 변수가 **정치시간**이 된다. Feed 5 kg 의 간섭침강까지
   넣으면 가장 느린 실리콘이 분할면까지 내려오는 데 **700 s**(구간 최소 입경 31 µm 기준 1,050 s)가
   걸려, 600 s 에서는 Top Si loss 가 4.2 % 로 기준(≤ 3 %)을 넘는다. **정치 900 s 이상**을 권고한다.

> **Rev.A → Rev.B 정정.** Rev.A 는 판정 기준을 '액면 도달'로 잡아 회수율을 크게 낮게 보았고,
> 그 간극을 잔류 미세기포로 메우는 논리를 세웠다. 연구문서 §1 은 **"Air 와 Impeller 는 분산수단이며
> 분리수단이 아니다"** 라고 못박고 있으며, 기준을 분할면으로 바로잡으면 그 간극 자체가 없다.
> 정정 내역은 제작도 **부속-A** 에 4건으로 남겼다.

같은 기준으로 돌려 볼 수 있는 화면이 둘 있다. `docs/drawings/mp50-separation-motion.html` 은 정지
t=0 부터 배출까지를 입자 1,000 개로 재생하며 분할면을 파선으로 그린다.
`docs/drawings/mp50-process-console.html` 은 염도·온도·정치시간·배출량·Feed 를 슬라이더로 두고
네 KPI 를 Monte Carlo P10/P90 으로 다시 계산한다.

> **유효밀도 ≠ 실밀도.** 문헌 실밀도는 EVA 봉지재 948, PET 1,380, PVF 1,440~1,700, PVDF 1,760,
> 실리콘 2,329 kg/m³ 다. 백시트 실밀도는 **포화 NaCl 염수의 상한 1,197 로도 뜨지 않는다.**
> 연구문서가 쓴 백시트 1,010~1,110 은 EVA 가 붙은 복합 파편이거나 공기를 문 미습윤 파편의
> **유효밀도**이며 — 복합 파편이 1,200 이라면 공기 **8.3 vol%** 만 물고 있어도 15 % 염수에서 뜬다 —
> 아직 측정된 적이 없다. **T3 의 1순위 측정 항목**이고, 값에 따라 상부 제품이 EVA 뿐인지
> EVA+백시트인지가 갈린다. 백시트를 확실히 회수하려면 **2단 밀도컷**(CaCl₂ ~1,400 ·
> ZnCl₂ ~2,000 kg/m³)이 필요하다.

> **그 유효밀도는 입도가 정한다.** 후면 EVA(0.50 mm)와 백시트(0.25 mm) 적층을 조각 두께 d 로
> 자르면, d 가 층 두께보다 작을수록 조각이 단일 재질이 된다. **31~75 µm 에서는 순수 백시트
> 조각이 25 % 나 생기고 백시트를 품은 조각의 평균이 1,346 kg/m³ 라, 띄우려면 46 wt% 가 필요해
> 포화 NaCl 밖이다** — 분리 가능한 염도 창이 존재하지 않는다. 반대로 **0.4~0.9 mm 로 굵게
> 남기면** 전부 EVA 를 달고 나와 1,115 로 모이고, 실리콘 쪽 복합(1,189)과의 사이에
> **15.5~25.3 wt% 의 창**이 열린다. 그 안의 **18 wt%** 에서 네 KPI 가 모두 통과한다.
> 즉 **분쇄를 세게 할수록 밀도분리가 어려워진다** — 실리콘 해리도와 맞바꾸는 설계 변수다.

씰은 여전히 **CRITICAL HOLD** 이고, Vendor GA 전에는 mounting PCD · output shaft/key ·
seal gland/sleeve · frame height 를 확정하지 않는다.

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
| [docs/drawings/mp50-pilot-drawings.html](docs/drawings/mp50-pilot-drawings.html) | **MP-50 제작도 11매 (Rev.B)** — 기준좌표·부품표(34점), 분리 원리·운전 시퀀스, 3×3 유효밀도·밀도컷, 층분리 운동학, 탱크 셀·콘, 커버·맨홀·스키머, 교반계·간섭 검사, 분산 링·공기 공급계, 배출·프레임, Release/HOLD·공차, FAT·KPI·DOE·재질 (브라우저로 열 것) |
| [docs/drawings/mp50-pilot-3d.html](docs/drawings/mp50-pilot-3d.html) | **MP-50 3D 조립·분해도 (Rev.A)** — 26개 부품 분해, 동체 컷어웨이, FLOAT/SINK 층을 보이는 「분리 결과」 보기, 보기별 제원 (브라우저로 열 것) |
| [docs/drawings/mp50-separation-motion.html](docs/drawings/mp50-separation-motion.html) | **MP-50 층분리 거동 시뮬레이터** — 분산 정지 t=0 부터 배출까지를 입자 1,000 개로 재생한다. 재생·스크럽·배속, 분할면 기준 배분과 KPI 판정, 염도·배출량 조작 (브라우저로 열 것) |
| [docs/drawings/mp50-process-console.html](docs/drawings/mp50-process-console.html) | **MP-50 운전조건 콘솔** — 염도·온도·분산/정치시간·배출량·Feed 조성을 움직이면 분할면·필요 정치시간·4개 KPI 가 Monte Carlo P10/P90 으로 다시 계산된다. **재질 밀도를 「연구문서 유효밀도 / 문헌 실밀도 / 복합 파편」 으로 바꿔 가며** 비교할 수 있다 (브라우저로 열 것) |
| [docs/drawings/pv-delamination-3d.html](docs/drawings/pv-delamination-3d.html) | **DG-HK60 3D 운전 콘솔** — 부선 공정에 셀 분획을 공급하는 상류 분리설비. 5단 밀폐 IR 캐리지 순환, 고정 HKB/HKS 탠덤 박리, 15단계 공정 재생, 컷어웨이·분해도, 전기·PLC·제작도면 13종, 열수지 계산기 (브라우저로 열 것) |

### 사용법

패키지가 `src/` 레이아웃이므로 설치 없이 실행할 때는 `PYTHONPATH=src` 를 붙인다.

```bash
PYTHONPATH=src python -m flotation_design                               # 계산서 출력
PYTHONPATH=src python -m flotation_design -o docs/design-calculation.md # 파일로 저장
PYTHONPATH=src python -m flotation_design --peak-tph 0.6                # 처리량 변경
python -m unittest discover -s tests -t .                               # 테스트 (446건)
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
