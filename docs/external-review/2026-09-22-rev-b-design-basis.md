# PV Recycling RFC — REV B 설계 검토 기준

## 상태
Claude의 REV A 도면을 베이스로 유지하되, 문헌 검증값과 내부 설계값을 분리했다.

### 1. LITERATURE — 도면에 고정
- Feed + air: 상부 sparger/downcomer
- Conventional froth가 아닌 flooded concentrated bubbly zone
- Wash water: 상부에서 하향 bias
- Inclined channels: 하향 액체에 동반된 bubble의 segregation/reflux
- Concentrate: 상부 배출
- Tailings: 하부 배출
- 경사각 70°: RFC 문헌 기준점
- 채널 간격 약 20 mm: 공개 RFC 실험의 기준점

### 2. DESIGN BASIS — 아직 PV 실증 확정값 아님
- Vessel ID Ø350 mm
- Riser H 2.40 m
- Jf = 2.0 cm/s
- Jg = 2.0 cm/s
- Jw = 0.81 cm/s
- Jb = 0.25 cm/s
- Bubble size 0.5–1.0 mm
이 값들은 현재 sizing/scaling 기준으로 유지하되 FAT/Pilot 전에는 '확정 성능값'으로 취급하지 않는다.

### 3. PILOT VARIABLE — 교체형 cassette
- Inclined-channel spacing: **6 / 10 / 12 / 15 / 20 mm**
- 기본 reference cassette: **20 mm**
- 비교항목: Ag recovery, Ag grade, Si entrainment, Cu distribution, water recovery,
  pressure drop, gas hold-up/reflux stability, plugging/fouling, mass pull.

### 4. 성능 표기
Claude REV A의 `Ag 99.7% / 46.3 wt%`는 본 RFC의 검증성능으로 사용하지 않는다.
본 장치의 Ag 회수율·품위는 PV feed pilot test 후 확정한다.

## 다음 설계 Gate
**Gate B1:** 20 mm reference cassette 수리학 검증  
**Gate B2:** 6/10/12/15/20 mm CFD 또는 cold-flow 비교  
**Gate B3:** 실제 25–75 µm PV feed flotation test  
**Gate B4:** 최적 cassette 선정 후 상세 제작도/FEED 동결
