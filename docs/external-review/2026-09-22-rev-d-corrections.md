# Claude 전달용 — RFC REV C 재검토 및 REV D 수정 지시

## 결론

REV C의 가장 큰 개선점은 상태등급([LITERATURE]/[DESIGN BASIS]/[PILOT VARIABLE]/[PERFORMANCE])과
6/10/12/15/20 mm 교체형 cassette를 도입한 것이다. 이 방향은 유지한다.

다만 외부 문헌을 다시 확인한 결과, **PV Ag 성능 출처와 RFC 구조 근거를 더 엄격히 분리해야 한다.**
따라서 첨부 REV D에서는 성능값과 출처 표기를 추가 수정했다.

## 1. 가장 중요한 수정 — Saffarian et al. 2026의 장치형식

Peer-reviewed 논문:

**Saffarian, H.; Galvin, K.P.; Firouzi, M. (2026),  
“Rethinking silver recovery pathways in end-of-life photo voltaic recycling using froth flotation,”  
Minerals Engineering 242, 110189.**

공개된 논문 초록은 method development가 **0.5 L mechanical cell**, 이후 **1 L tests**로 수행되었다고
명시한다.

검증 가능한 성능은:
- tap-water rougher: **Ag recovery 97.55 ± 0.03%**, upgrade ≈32.2
- rougher-cleaner: **≈47 wt% Ag concentrate at 86.5% recovery**

따라서 이 peer-reviewed 논문을:
- RFC 장치의 직접 성능검증
- Ø350 prototype의 성능 근거
- RFC 구조/geometry의 1차 근거

로 사용하면 안 된다.

REV C에 남아 있던 `Ag 99.7% / 48.8 wt%`는 별도의 ChemRxiv 연속부선 preprint 주장과
peer-reviewed mechanical-cell 논문을 혼동할 위험이 있다. **해당 preprint 원문의 장치 구조와 시험조건을
직접 대조하기 전에는 REV D 도면의 성능값에서 제외**한다. 추적성이 필요하면 별도 “UNVERIFIED EXTERNAL
PREPRINT DATA” 부록에만 남긴다.

## 2. 46.3 wt% 목표값 제거

REV C의 DWG-101/102에 `품위 목표 46.3 wt% (계산)`이 남아 있었다.
이는 `[PERFORMANCE] = 파일럿 검증 필요` 원칙과 시각적으로 충돌한다.

REV D에서는:
> **Ag 품위 — 본 장치 파일럿에서 확정**

으로 변경한다.

내부 계산모델의 46.3 wt%는 설계 계산서에는 보존할 수 있으나, geometry reference drawing의
concentrate label에는 표시하지 않는다.

## 3. Channel spacing 판정

공개 RFC fast-flotation 실험의 명확한 reference geometry:
- vertical chamber: 146 × 146 mm
- height: 960 mm
- six parallel inclined channels
- angle: **70°**
- channel length: **925 mm**
- perpendicular spacing: **20 mm**
- downcomer gaps tested: 2 / 4.5 / 9 mm

따라서:
- 20 mm = **문헌 reference point**
- 12 mm = 내부 후보
- 3–6 mm = RC 결과를 RFC 최적값으로 직접 이월하지 않음
- PV 최종값 = **6/10/12/15/20 mm pilot comparison 후 결정**

REV C의 `10–30 mm = ✓` 판정은 과도하다.
REV D에서는 **△ 조건부**로 수정한다.

## 4. Bubble size

REV C는 `0.5–1.0 mm = 문헌 [2] 실증 범위`라고 연결했는데, peer-reviewed PV Ag 논문은
RFC sparger 성능 근거가 아니다.

REV D:
> 0.5–1.0 mm = **현재 DESIGN TARGET**  
> 실제 bubble-size distribution = sparger/downcomer cold-flow test에서 측정

으로 수정한다.

## 5. 유지할 RFC 구조

다음은 계속 유지한다.

- upper sparger/downcomer
- feed + air contacting in downcomer
- concentrated/flooded bubbly zone
- counter-current wash-water bias
- inclined-channel bubble segregation/reflux
- bubble reflux ↑
- liquid + hydrophilic/gangue ↓
- upper concentrate collection
- lower tailings discharge
- central circular downcomer = **prototype arrangement**, universal standard 아님

## 6. DESIGN BASIS와 LITERATURE를 계속 분리

다음 값은 내부 sizing 값으로 유지 가능하지만 문헌 실증치라고 쓰지 않는다.

- vessel ID Ø350 mm
- riser H 2.40 m
- Jf = 2.0 cm/s
- Jg = 2.0 cm/s
- Jw = 0.81 cm/s
- Jo = 0.56 cm/s
- Jb = 0.25 cm/s
- 0.50 t/h maximum design basis

표 제목도 `확정 사양` 대신:

> **설계기준 요약 — 내부 scaling 기준**

으로 변경한다.

## 7. Claude가 REV E에서 확인할 사항

1. ChemRxiv `Continuous flotation unlocks full recovery of silver from end-of-life solar cells`
   원문에서 99.7% / 48.8 wt%가 실제로 확인되는지.
2. 그 연속장치가 RFC인지, wash-water-biased flotation cell인지, 별도 geometry인지 원문 도면으로 확인.
3. 100×80 mm 단면, 22 kg feed, 42–90 min steady state 주장도 원문 페이지/figure/table 번호를 제시.
4. 해당 장치가 RFC가 아니라면 PV Ag 성능문헌과 RFC hydrodynamic literature를 완전히 별도 source family로 관리.
5. C-20 → C-15 → C-12 → C-10 → C-06 순으로 cold-flow 시험하여 plugging/ΔP/gas hold-up/reflux를 확인.
6. 실제 PV feed(P80 66 µm)는 그 다음 Gate에서 Ag recovery/grade/Si entrainment를 비교.

## 8. 권장 문헌 체계

### Source family A — PV Ag flotation chemistry/performance
Saffarian et al., Minerals Engineering 242 (2026) 110189.
Mechanical flotation cell 결과. RFC 성능으로 전용 금지.

### Source family B — RFC geometry/hydrodynamics
“The kinetics of Fast Flotation using the Reflux Flotation Cell,” Chemical Engineering Science.
70°, 925 mm, 20 mm perpendicular channel spacing의 직접 RFC reference.

### Source family C — 최신 RFC performance/hydrodynamics
Chahardahmasoumi, Firouzi & Galvin,
Minerals Engineering 246 (2026) 110422,
“Promoting fine and coarse particle flotation performance in the REFLUX™ Flotation Cell.”

### Source family D — Internal design calculations
`rfc.py`, 계산서 §5, DWG-002.
Ø350, 2.40 m, flux/bias 등은 DESIGN BASIS.

## 최종 원칙

> **PV flotation literature tells us whether Ag can be floated.**  
> **RFC literature tells us how an RFC behaves and is geometrically configured.**  
> **Internal calculations tell us where to start the prototype.**  
> **Only the PV-RFC pilot can define the final dimensions and guaranteed performance.**

이 네 종류의 근거를 한 표에서 섞지 않는 것이 REV D 이후의 핵심 설계 거버넌스다.
