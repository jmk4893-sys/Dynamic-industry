# Claude 전달용 — PV Recycling RFC 기술검토 및 REV B 수정 통합본

## 문서 목적

이 문서는 Claude가 작성한 `ag-flotation-rfc-reference.html` 및 `rfc-diagram-correction-brief.md`를 검토한 결과와, 그 검토를 반영해 작성한 **REV B 설계기준**을 하나로 통합한 전달용 문서다.

목표는 Claude의 작업을 폐기하는 것이 아니라, **구조적으로 타당한 부분은 유지하고, 문헌 검증값·내부 계산값·PV Pilot 검증이 필요한 값을 명확히 분리하여 다음 REV를 작성하는 것**이다.

---

# PART A. Claude REV A 검토 결과

## A-1. 총평

Claude가 작성한 REV A는 기존 생성형 RFC 이미지보다 구조적으로 크게 개선되었다.

특히 다음 기본 hydrodynamics는 유지하는 것이 타당하다.

**Feed + Air → Sparger/Downcomer → Concentrated Bubbly Zone → Wash-water Bias → Inclined Channels → Bubble Reflux / Tailings**

그리고:

- Feed와 air를 상부 sparger/downcomer에서 접촉
- conventional flotation froth가 아닌 flooded concentrated bubbly zone
- wash water의 counter-current/downward bias
- inclined channels에서 bubble–liquid segregation
- bubble reflux
- concentrate의 상부 배출
- tailings의 하부 배출

이라는 기본 구조는 RFC 문헌의 설명과 잘 부합한다.

---

## A-2. 유지할 부분

### 1. Sparger / Downcomer

Claude의 다음 방향은 유지한다.

- Feed → 상부 downcomer
- Air → high-shear sparger
- Downcomer 내부에서 bubble–particle contact
- 별도의 vessel-bottom air sparger는 사용하지 않음

단, **중앙 원형 downcomer를 모든 RFC의 보편적 표준 구조라고 표현하지 않는다.**

중앙 배치는 본 prototype의 설계 선택으로 사용할 수 있지만 RFC 연구에는 rectangular downcomer 등 다른 geometry도 존재한다.

따라서 표기는 다음처럼 한다.

> Central downcomer — prototype design arrangement

---

### 2. Flooded Bubbly Zone

Claude의 conventional froth 제거는 유지한다.

RFC에서는 일반적인 flotation cell처럼 두꺼운 froth layer를 기본 구조로 그리지 않는다.

도면에서는:

> Concentrated Bubbly Zone  
> Reverse-Fluidized Bubbly Zone  
> Flooded Operation

으로 표현한다.

---

### 3. Wash-Water Bias

Claude의 하향 wash-water bias 개념은 유지한다.

현재 설계 계산값:

- Jw = 0.81 cm/s
- Jo = 0.56 cm/s
- Jb = Jw − Jo = 0.25 cm/s

단, 이 값은 **PV-RFC 실증 확정값이 아니라 현재 DESIGN BASIS**다.

---

### 4. Concentrate / Tailings 방향

유지한다.

**Concentrate → Upper outlet / annular collection**

**Tailings → Lower underflow**

단, 실제 상업 장치의 상세 outlet geometry를 그대로 복제했다고 표현하지 않는다.

---

### 5. Inclined-Channel Bubble Reflux

Claude의 다음 표현은 유지한다.

**Bubble reflux ↑**

**Liquid + hydrophilic/gangue particles ↓**

inclined channels의 핵심 설명은 Ag 입자가 plate 위를 미끄러져 올라가는 것이 아니라, 하향 liquid에 entrain된 bubble이 liquid에서 segregate되어 다시 upper bubbly zone으로 reflux하는 것이다.

따라서 도면의 상향 화살표에는 우선적으로:

> BUBBLE REFLUX

라고 표기한다.

---

# PART B. Claude REV A에서 수정해야 할 부분

## B-1. Ag 99.7% / 46.3 wt%를 RFC 성능으로 사용하지 않는다

REV A에는 다음 값이 RFC 성능처럼 보일 수 있게 들어가 있다.

- Ag recovery = 99.7%
- Ag concentrate = 46.3 wt%
- Mass yield = 1.27%

이 값들은 본 PV-RFC prototype에서 직접 검증된 성능값으로 사용하지 않는다.

따라서 REV B에서는 다음처럼 바꾼다.

> **PV-RFC Ag performance: PILOT VALIDATION REQUIRED**

외부 PV Ag flotation 연구 결과를 참고값으로 사용할 경우 반드시:

> External flotation reference — NOT validated in this RFC

라고 별도로 표시한다.

---

# PART C. 가장 중요한 설계변경 — Inclined Channel Spacing

## C-1. Gemini의 3–6 mm 확정도 사용하지 않는다

`3–6 mm = PV용 RFC 최적 간격`

이라고 확정할 직접적인 PV-RFC 근거는 현재 확보되지 않았다.

3 mm 및 6 mm의 좁은 inclined-channel spacing과 laminar shear / shear-induced lift 논리는 주로 REFLUX Classifier(RC)의 중력·밀도 선별 연구에서 확인된다.

RC와 RFC의 핵심 물리는 동일하지 않다.

### RC

- particle settling
- density separation
- fluidisation
- shear-induced inertial lift

### RFC

- bubble–particle attachment
- concentrated bubbly zone
- counter-current washing
- bubble–liquid segregation
- bubble reflux

따라서 RC의 3–6 mm 결과를 그대로 PV-RFC 최적값으로 가져오면 안 된다.

---

## C-2. Claude의 12 mm 확정도 사용하지 않는다

Claude REV A는:

> 70° / 12 mm / 1.0 m

를 본 설계의 확정값처럼 사용했다.

그러나 Claude 자료 자체에서도 공개 RFC reference가 약 **20 mm**임을 인정하고 있다.

따라서 12 mm는:

> PV용 확정값

이 아니라:

> Prototype candidate

로 취급한다.

---

## C-3. REV B 채널 설계

### Literature Reference

- Angle: approximately 70°
- Channel length: approximately 0.925–1.0 m
- Perpendicular spacing: approximately 20 mm

### PV Prototype Design Variables

교체형 cassette를 사용한다.

**6 / 10 / 12 / 15 / 20 mm**

따라서 REV B 표기는 다음과 같이 한다.

> Inclined Channel Spacing  
> **DESIGN VARIABLE — 6 / 10 / 12 / 15 / 20 mm**  
> Literature RFC reference ≈ 20 mm  
> Final PV specification requires pilot validation.

---

# PART D. REV B 설계 상태 분류

모든 수치는 다음 네 등급으로 구분한다.

## [LITERATURE]

RFC 문헌으로 직접 지지되는 구조/원리.

- upper sparger/downcomer
- concentrated bubbly zone
- flooded operation
- wash-water bias
- inclined-channel bubble segregation
- bubble reflux
- upper concentrate discharge
- lower tailings discharge
- approximately 70° inclined-channel reference
- approximately 20 mm RFC experimental channel-spacing reference

---

## [DESIGN BASIS]

현재 sizing/scaling을 위해 사용하는 내부 설계값.

- Vessel ID: Ø350 mm
- Riser height: 2.40 m
- Jf = 2.0 cm/s
- Jg = 2.0 cm/s
- Jw = 0.81 cm/s
- Jo = 0.56 cm/s
- Jb = 0.25 cm/s
- Bubble size target = 0.5–1.0 mm

이 값들은 도면에 사용할 수 있지만:

> **PV-RFC validated value**

라고 표현하지 않는다.

---

## [PILOT VARIABLE]

실험으로 확정해야 할 값.

- Channel spacing
- Channel angle fine optimisation
- Downcomer geometry
- Gas flux
- Feed flux
- Wash-water flux
- Bubble size distribution
- Solids concentration
- Collector dosage
- pH
- Residence time

---

## [PERFORMANCE]

Pilot test 전에는 확정하지 않는다.

특히:

- Ag recovery
- Ag concentrate grade
- Cu recovery/distribution
- Si recovery/purity
- mass pull
- water recovery

를 보증성능처럼 표시하지 않는다.

---

# PART E. REV B 기본 설계안

## Vessel

Current DESIGN BASIS:

**Ø350 mm**

이 값은 내부 flux scaling 기준으로 유지하되 pilot sizing에서 다시 검증한다.

---

## Riser

Current DESIGN BASIS:

**H = 2.40 m**

목표:

- concentrated bubbly zone 안정화
- wash-water contact
- sufficient bubble–particle residence

---

## Feed

Current DESIGN BASIS:

**Jf = 2.0 cm/s**

---

## Gas

Current DESIGN BASIS:

**Jg = 2.0 cm/s**

따라서 초기:

**Jg / Jf ≈ 1**

을 pilot starting point로 사용한다.

---

## Wash Water

Current DESIGN BASIS:

**Jw = 0.81 cm/s**

---

## Bias

Current DESIGN BASIS:

**Jb = 0.25 cm/s**

with:

**Jb = Jw − Jo**

---

## Bubble Size

Target DESIGN BASIS:

**0.5–1.0 mm**

실제 bubble-size distribution은 sparger/downcomer test에서 측정한다.

---

# PART F. PV Feed 기준

대상:

**PV recycling black powder**

입도 기준:

**25–75 μm**

주요 성분:

- Ag-bearing particles
- Cu-bearing particles
- Si
- residual glass/frit
- residual EVA/backsheet contaminants

기본 separation philosophy:

**Hydrophobic valuable fraction → bubble attachment → concentrate**

**Hydrophilic Si-rich fraction → tailings**

단, Ag/Cu/Si의 실제 분배는 reagent chemistry와 liberation 상태에 따라 Pilot에서 결정한다.

---

# PART G. 교체형 Lamella Cassette

Prototype은 fixed lamella spacing으로 제작하지 않는다.

다음 cassette를 제작한다.

| Cassette | Perpendicular spacing |
|---|---:|
| C-06 | 6 mm |
| C-10 | 10 mm |
| C-12 | 12 mm |
| C-15 | 15 mm |
| C-20 | 20 mm |

**C-20을 literature-reference cassette로 사용한다.**

---

# PART H. Cassette별 평가 항목

각 cassette에서 동일한 feed 조건으로 다음을 측정한다.

1. Ag recovery
2. Ag concentrate grade
3. Si entrainment
4. Cu distribution
5. concentrate mass pull
6. water recovery
7. pressure drop
8. gas hold-up
9. bubble reflux stability
10. channel plugging
11. fouling
12. solids accumulation
13. tailings bubble loss
14. concentrate stability

---

# PART I. 다음 Engineering Gate

## Gate B1 — Hydraulic Baseline

20 mm reference cassette로 cold-flow/hydraulic baseline을 확보한다.

측정:

- ΔP
- liquid velocity
- gas hold-up
- bubble reflux
- bias stability

---

## Gate B2 — Cassette Comparison

다음 간격을 비교한다.

**6 / 10 / 12 / 15 / 20 mm**

가능하면 CFD + cold-flow를 병행한다.

---

## Gate B3 — Real PV Feed

25–75 μm PV feed를 사용한다.

측정:

- Ag recovery
- Ag grade
- Si entrainment
- Cu distribution
- mass pull
- water recovery

---

## Gate B4 — Geometry Freeze

시험 결과로 최종:

- channel spacing
- angle
- channel length
- number of channels
- downcomer geometry
- vessel diameter
- riser height

를 동결한다.

그 후에만:

> Detailed Fabrication Drawing / FEED Freeze

단계로 이동한다.

---

# PART J. Claude에게 요청하는 REV C 작업

기존 REV A의 SVG/HTML 구조와 시각적 완성도는 최대한 유지한다.

다만 다음을 수정하여 **REV C**를 작성해 달라.

### 반드시 수정

1. `12 mm = 확정값` 표현 삭제.
2. `6/10/12/15/20 mm interchangeable cassette`로 변경.
3. `20 mm = literature RFC reference`라고 표시.
4. `Ag 99.7% / 46.3 wt%`를 RFC 검증성능에서 삭제.
5. Ø350 / 2.40 m / Jf / Jg / Jw / Jb에는 `[DESIGN BASIS]` 태그 추가.
6. 문헌으로 직접 검증된 구조에는 `[LITERATURE]` 태그 추가.
7. 시험 전 확정할 수 없는 값에는 `[PILOT VARIABLE]` 태그 추가.
8. Ag recovery/grade에는 `[PILOT VALIDATION REQUIRED]` 표시.
9. Inclined channel의 상향 화살표는 `BUBBLE REFLUX ↑`로 명확히 표시.
10. 하향 유동은 `LIQUID + HYDROPHILIC/GANGUE ↓`로 표시.
11. 중앙 downcomer는 `Prototype arrangement`라고 명시하고 universal RFC standard라고 표현하지 않는다.
12. Conventional froth layer를 추가하지 않는다.

---

# PART K. Claude에게 확인을 요청할 핵심 질문

REV C를 작성하기 전에 아래 사항을 다시 검증해 달라.

### Q1
공개 RFC 논문 또는 FLS 자료 중 **inclined-channel spacing 12 mm**를 PV 또는 fine-mineral RFC에서 직접 검증한 자료가 있는가?

있다면 DOI/페이지/도면번호를 제시할 것.

### Q2
`Ag recovery 99.7% / concentrate 46.3 wt%`가 실제 **RFC 장치**에서 얻어진 결과인가?

아니라면 RFC 성능표에서 제거할 것.

### Q3
Ø350 × 2.40 m가 문헌 실증장치 치수인가, 아니면 내부 flux scaling 결과인가?

후자라면 `[DESIGN BASIS]`로 표시할 것.

### Q4
중앙 원형 downcomer가 상업용 RFC의 필수 geometry라는 직접 근거가 있는가?

없다면 prototype configuration으로만 표현할 것.

### Q5
PV 25–75 μm feed에서 6/10/12/15/20 mm channel spacing을 비교할 경우 예상되는:

- pressure drop
- bubble reflux
- plugging
- Ag recovery
- Si entrainment

변화를 계산 또는 CFD로 비교할 수 있는가?

---

# PART L. 최종 설계 원칙

현재 단계에서는:

**3–6 mm도 확정하지 않는다.**

**12 mm도 확정하지 않는다.**

**20 mm도 최적값이라고 단정하지 않는다.**

20 mm는 **공개 RFC literature reference**로 사용하고,

**6 / 10 / 12 / 15 / 20 mm**

를 PV feed에서 비교하여 최종 spacing을 결정한다.

즉 다음 설계철학을 적용한다.

> **Literature defines the reference geometry.  
> Engineering calculations define the prototype starting point.  
> PV pilot testing defines the final geometry.**

---

## 참고 문헌

- Dickinson & Galvin, *Chemical Engineering Science* 108 (2014), 283–298.
- RFC fast-flotation 연구: 70° inclined channels, 약 925 mm length, 약 20 mm perpendicular spacing.
- Cole et al., *Minerals Engineering* 179 (2022), 107464.
- Jiang et al., *Minerals Engineering* 181 (2022), 107537.
- Saffarian, Galvin, Firouzi, *Minerals Engineering* 242 (2026), 110189 — PV Ag flotation reference. 본 RFC prototype의 직접 성능검증값으로 사용하지 않는다.
- *Minerals Engineering* (2026), 110422 — RFC concentrated bubbly zone / bubble reflux 관련 최신 연구.

---

**Document:** Claude Handoff — RFC Technical Review + REV B Design Basis  
**Status:** For REV C redesign and engineering verification  
**Application:** PV Recycling / Ag–Cu–Si separation  
**Important:** Concept/Pre-FEED 단계. Pilot 검증 전 제작 성능보증값으로 사용하지 않는다.
