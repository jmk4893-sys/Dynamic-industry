# Claude 전달용 — REV.B 도면 수정 요청 6건 반영본

## 적용 상태
요청 6건을 REV.B2 도면에 반영했다. 단, 문헌 데이터는 **peer-reviewed mechanical-cell 결과**와
**2026 ChemRxiv 연속시험 preprint**를 분리해 표기한다.

## 1. 패널 4 — 유동 화살표
- 리플럭스 기포: **노랑 ↑**
- 슬러리·미광 하강류: **갈색 ↓**
- 파랑: **세척수 전용**
- 표기:
  - `BUBBLE REFLUX ↑`
  - `SLURRY + TAILINGS ↓`

## 2. 패널 2 — 다운커머 토출단
기존처럼 라이저 하부까지 길게 내려오지 않도록 수정.
**다운커머 토출단은 라이저 상부에서 종료**하도록 단면 형상을 단축하고 토출 화살표를 추가했다.

## 3. 패널 10 — 성능 데이터
다음 두 source family를 분리한다.

### A. 2026 ChemRxiv 연속시험
`Continuous flotation unlocks full recovery of silver from end-of-life solar cells`
- Ag recovery: **99.7%**
- concentrate: **48.8 wt% Ag**
- 표기: **본 장치 미검증 참고값**
- 주의: 이 값은 본 REV.B2 RFC prototype의 보증성능이 아니다. 원문 장치형식과 운전조건을 별도 확인한다.

### B. Peer-reviewed mechanical-cell PV Ag flotation
Saffarian, Galvin & Firouzi, Minerals Engineering 242 (2026) 110189
- tap-water rougher: **97.6% Ag recovery** (원문 97.55 ± 0.03%, 도면에서는 97.6으로 반올림)
- rougher-cleaner: **≈47 wt% Ag at 86.5% recovery**
- 장치: 0.5 L method development, 1 L tests
- **RFC 성능값이 아님**

## 4. 경사각
`65–70° 권장` 표현 삭제.

REV.B2:
> **70° (문헌 기준)**

PV 최종 geometry 동결 전까지 별도 “권장범위”를 만들지 않는다.

## 5. ≈20 mm 채널 서지
20 mm perpendicular inclined-channel spacing을 직접 사용한 명확한 출처:

**Jiang, K.; Dickinson, J.E.; Galvin, K.P. (2019).  
“The kinetics of Fast Flotation using the Reflux Flotation Cell.”  
Chemical Engineering Science 196, 463–477.  
DOI: 10.1016/j.ces.2018.11.012.**

실험 RFC:
- vertical chamber: 146 × 146 mm
- chamber height: 960 mm
- inclined channels: 6
- angle: **70°**
- channel length: **925 mm**
- perpendicular spacing: **20 mm**
- downcomer gaps: 2 / 4.5 / 9 mm

따라서 도면의 C-20 reference는:
> **Jiang, Dickinson & Galvin (2019): 20 mm**

로 표기한다.

Dickinson & Galvin (2014)은 drift-flux/RFC hydrodynamic development의 중요한 선행문헌이지만,
본 도면에서 **20 mm geometry의 직접 출처는 Jiang, Dickinson & Galvin (2019)** 로 지정하는 것이 명확하다.

## 6. 날짜
모든 legacy `2025.09` 표기를:
> **2026.09**
로 수정.

## 설계 거버넌스 유지
- 20 mm = literature reference point
- 6 / 10 / 12 / 15 / 20 mm = pilot cassette variables
- 12 mm = 내부 후보값, 확정값 아님
- Ø350 / 2.40 m / Jf / Jg / Jw / Jb = DESIGN BASIS
- Ag grade/recovery = 본 장치 pilot 전에는 PERFORMANCE GUARANTEE 금지

## Claude 다음 작업 지시
이 REV.B2를 기준으로 시각 레이아웃을 유지하면서 다음 버전에 동일하게 반영할 것.
특히 색상 의미를 모든 패널에서 고정한다.

- **노랑 = bubble / hydrophobic valuable aggregate upward**
- **파랑 = wash water downward**
- **갈색 = slurry / hydrophilic gangue / tailings downward**

성능표에서는 ChemRxiv 연속시험과 Minerals Engineering mechanical-cell 논문을 절대 한 실험으로 합치지 않는다.
