# Dynamic-industry

Dynamic industry Development

## 부유선별 회로 (Flotation Circuit)

폐 태양광 모듈(c-Si) 재활용 라인에서 **은(Ag)·구리(Cu)** 를 회수하는
**러퍼 – 스캐빈저 – 클리너 3단 부유선별 회로**의 설계와 계산 코드.

- 평균 **0.30 t/h**, 최대 **0.50 t/h** (건조 고체 기준)
- FC-101 러퍼 / FC-102 스캐빈저 (러퍼와 동일 동체) / FC-103 클리너 (450 mm, 세척수)
- 예상 Ag 회수율 **82.4 %** (평균) / **75.7 %** (최대), Cu 93.6 % / 91.3 %
- 정광 Ag 품위 2.79 %, Si 함량 1.2 %, 농축비 6.2배, 순환부하 16 %

### 문서

| 문서 | 내용 |
|---|---|
| [docs/flotation-separator-design.md](docs/flotation-separator-design.md) | 설계 사양서 — 회로 구성, 셀별 설계, 분리 원리, 계장·제어, 안전, 시운전 계획 |
| [docs/design-calculation.md](docs/design-calculation.md) | 설계 계산서 (코드에서 자동 생성) |

### 사용법

패키지가 `src/` 레이아웃이므로 설치 없이 실행할 때는 `PYTHONPATH=src` 를 붙인다.

```bash
PYTHONPATH=src python -m flotation_design                               # 계산서 출력
PYTHONPATH=src python -m flotation_design -o docs/design-calculation.md # 파일로 저장
PYTHONPATH=src python -m flotation_design --peak-tph 0.6                # 처리량 변경
python -m unittest discover -s tests -t .                               # 테스트
```

설치하면 `PYTHONPATH` 없이 쓸 수 있다.

```bash
pip install -e .
flotation-design
```

`--average-tph` / `--peak-tph` 는 **재사이징이 아니라 기존 셀의 성능 계산**이다.
셀 치수는 `design_basis.py` 에 확정값으로 박혀 있어 처리량을 바꿔도 재산정되지
않는다. 확정 셀이 목표 체류시간에 미달하면 계산서 상단에 경고가 붙고, §9 에
그 처리량에 필요한 셀 치수가 표시된다.

### 구조

```
src/flotation_design/
  design_basis.py   설계 전제 — 급광 조성, 셀 형상, 약제, 속도상수, 순환 조건 (여기만 고치면 됨)
  feed.py           급광 조성 · 슬러리 물성
  sizing.py         셀 체적/형상, 로터, 급기, 정광 배출 부하
  kinetics.py       2속도(Kelsall) 반응속도 모델 — 속부선/지연부선/비부선
  circuit.py        흐름 추적 · 단위 셀 분리 · 순환부하 수렴 계산
  circuit_design.py 회로 전체 조립 (셀 3기 사이징 + 물질수지)
  reagents.py       약제 투입량 · 정량펌프 유량
  conditioning.py   조건조 사이징
  report.py         Markdown 계산서 생성
```

성분마다 **속부선 / 지연부선 / 비부선** 3분획으로 나눈 2속도 모델을 쓴다.
단일 속도상수 모델은 러퍼 미광에 남은 물질이 급광과 같은 속도로 부상한다고 가정해
스캐빈저 성능을 과대평가하므로, 회로 설계에는 쓸 수 없다.

분획 비율과 속도상수는 문헌 기반 **가정값**이다. 실제 급광으로 배치 부선시험(시간별
정광 분취)과 록사이클 시험을 수행해 `design_basis.py` 를 갱신한 뒤 재계산할 것.
