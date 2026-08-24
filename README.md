# Dynamic-industry

Dynamic industry Development

## 부유선별기 (Flotation Separator)

폐 태양광 모듈(c-Si) 재활용 라인에서 **은(Ag)·구리(Cu)** 를 회수하는
**단단(1-stage) 기계식 강제급기 부유선별기**의 설계와 계산 코드.

- 평균 **0.30 t/h**, 최대 **0.50 t/h** (건조 고체 기준)
- 셀 내부 700 × 700 × 810 mm(H), 유효 슬러리 체적 0.281 m³
- 예상 Ag 회수율 79.1 % (평균) / 73.8 % (최대), Cu 89.0 % / 85.3 %

### 문서

| 문서 | 내용 |
|---|---|
| [docs/flotation-separator-design.md](docs/flotation-separator-design.md) | 설계 사양서 — 분리 원리, 기계 사양, 계장·제어, 안전, 시운전 계획 |
| [docs/design-calculation.md](docs/design-calculation.md) | 설계 계산서 (코드에서 자동 생성) |

### 사용법

```bash
python -m flotation_design                                   # 계산서 출력
python -m flotation_design -o docs/design-calculation.md     # 파일로 저장
python -m flotation_design --average-tph 0.4 --peak-tph 0.6  # 처리량 변경
python -m unittest discover -s tests -t .                    # 테스트
```

설치해서 쓰려면:

```bash
pip install -e .
flotation-design
```

### 구조

```
src/flotation_design/
  design_basis.py   설계 전제 — 급광 조성, 체류시간, 약제, 부선 속도상수 (여기만 고치면 됨)
  feed.py           급광 조성 · 슬러리 물성
  sizing.py         셀 체적/형상, 로터, 급기, 정광 배출 부하
  kinetics.py       1차 반응속도 회수율 모델 · 물질수지
  reagents.py       약제 투입량 · 정량펌프 유량
  conditioning.py   조건조 사이징
  report.py         Markdown 계산서 생성
```

부선 속도상수 `k` 와 회수 상한 `r_max` 는 문헌 기반 **가정값**이다.
실제 급광으로 배치 부선시험을 수행해 `design_basis.py` 를 갱신한 뒤 재계산할 것.
