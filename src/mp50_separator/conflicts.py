"""원본 3종의 치수 충돌과 그 해결 근거.

MP-50 의 치수는 세 문서에 흩어져 있고, 셋이 서로 다르다.

* **[R]** 연구문서 Rev.0 (2026-09-10) — 가장 최근이고 유일하게 근거가 붙어 있다.
* **[D1]** 도면 MP-50-P0-001 Rev.P0 (2026-09-09) — 제작도 형식.
* **[D2]** 도면 MP50-DR-000 Rev.0 (2025-07-05) — 아세이 분해도 형식.

셋 중 하나를 골라 옮겨 적으면 제작이 안 되는 도면이 나온다. C2 는 임펠러가
배플에 부딪혀 아예 돌지 않고, C1 은 원뿔이 닫히지 않으며, C3 은 문서가 하라는
시험을 못 한다. 그래서 충돌마다 무엇을 왜 택했는지를 여기 남기고, 해결된 값만
``geometry.py`` 에 싣는다.

``severity``
    ``BLOCKING``  그대로 두면 제작·조립이 불가능하다.
    ``MAJOR``     제작은 되지만 문서가 요구하는 시험/계측을 못 한다.
    ``MINOR``     표기 차이 — 어느 쪽을 써도 물건은 나온다.

``approval``
    ``RESOLVED``  기하·물리로 답이 하나뿐이라 확정했다.
    ``PROPOSED``  공학적 판단이 들어갔다. 발주 전 승인이 필요하다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Conflict:
    """원본 간 치수 충돌 하나.

    Attributes:
        ref: 충돌 번호 (C1 …).
        item: 대상 부품.
        severity: BLOCKING / MAJOR / MINOR.
        sources: 출처별 원본 값.
        resolution: 채택한 값.
        rationale: 그 값을 택한 이유.
        approval: RESOLVED / PROPOSED.
    """

    ref: str
    item: str
    severity: str
    sources: tuple[tuple[str, str], ...]
    resolution: str
    rationale: str
    approval: str

    @property
    def blocking(self) -> bool:
        return self.severity == "BLOCKING"


CONFLICTS: tuple[Conflict, ...] = (
    Conflict(
        ref="C1",
        item="원뿔 높이",
        severity="BLOCKING",
        sources=(
            ("[D1]", "H150, 60°, Ø400 → Ø38"),
            ("[R]", "Cone H346, wall 60°"),
            ("[D2]", "H346, 60°, Ø400 → Ø50.8"),
        ),
        resolution="가상 정점높이 346.41 · 실제 원뿔대 높이 294.88 (Ø400 → Ø59.5)",
        rationale=(
            "60° 원뿔이 Ø400 에서 Ø38 까지 좁아지는 데 필요한 높이는 "
            "(400-38)/2 / tan30° = 313.5 mm 다. [D1] 의 H150 으로는 원뿔이 닫히지 "
            "않는다. [R] 의 346 은 Ø400 이 한 점으로 모이는 가상 정점높이 "
            "200/tan30° = 346.41 이며, 이 값을 Z 원점으로 잡아야 동체 상단 Z946 · "
            "커버 상면 Z951 · 전용적 89.9 L 가 동시에 맞는다. 셋이 함께 맞는 해석은 "
            "이것뿐이므로 확정한다."
        ),
        approval="RESOLVED",
    ),
    Conflict(
        ref="C2",
        item="배플 폭",
        severity="BLOCKING",
        sources=(
            ("[R]", "80 × 200 × t2 × 4매, Z390~690"),
            ("[D2]", "50 × 500 × t3 × 3매"),
            ("[D1]", "4매 (폭 미상)"),
        ),
        resolution="35 W × 300 L × t3 × 4매, 벽 이격 6, Z390~690",
        rationale=(
            "폭 80 에 벽 이격 6 이면 배플 안쪽 모서리가 R114 에 온다. Ø300 임펠러의 "
            "팁은 R150 이므로 **36 mm 겹친다 — 축이 돌지 않는다.** 임펠러 Ø300 은 "
            "[R][D1][D2] 가 모두 같고 DOE·동력·Njs 모델이 전부 그 위에 서 있으므로, "
            "고칠 쪽은 배플이다. 폭 35 (T/11.4) 로 줄이면 팁 간극 9 mm 를 얻는다. "
            "축 편심 0.5 + 임펠러 TIR 1.0 을 다 빼도 7.5 mm 가 남는다. "
            "길이는 [R] 이 지정한 설치 표고 Z390~690 에서 그대로 유도했다 — "
            "같은 줄의 '200' 은 이 구간(300)과 맞지 않는 옛 값으로 본다."
        ),
        approval="PROPOSED",
    ),
    Conflict(
        ref="C3",
        item="콘 배출 스터브",
        severity="MAJOR",
        sources=(
            ("[R]", "1.5 in 기본 / 2 in TEST"),
            ("[D2]", "Ø50.8 (= 1.5 in 튜브)"),
            ("[D1]", 'Ø38 / 1.5" (40A) 볼밸브'),
        ),
        resolution='2 in 위생튜브 Ø63.5 × t2.0 (ID 59.5) + 2" 페룰',
        rationale=(
            "스터브를 Ø50.8 로 붙이면 하류에 2 in 밸브를 달아도 목이 1.5 in 이라 "
            "[R] §16 이 요구한 '1.5 vs 2 in 배출시험' 이 성립하지 않는다. 큰 쪽으로 "
            "붙이고 기본형은 2→1.5 in 리듀싱 클램프로 조이면 재용접 없이 두 조건을 "
            "다 돌린다. 전용적은 89.86 L 로 [R] 의 89.9 L 와 그대로다."
        ),
        approval="PROPOSED",
    ),
    Conflict(
        ref="C4",
        item="분산링 지름 · 노즐",
        severity="MINOR",
        sources=(
            ("[R]", "Ring Ø250, Z300±20"),
            ("[D2]", "Ø280, 노즐 Ø1.0~2.0 × 12"),
            ("[D1]", "Ø250, 분사홀 Ø2 × 60"),
        ),
        resolution="PCD Ø250 · Ø12 × t1.5 튜브 · Ø1.5 홀 12개 (하향)",
        rationale=(
            "지름은 [R] 을 따른다. 홀은 12 × Ø1.5 가 급기 10 L/min 에서 오리피스 "
            "유속 7.9 m/s 를 준다 — 링 내부 유속의 6 배라 12 개에 고르게 갈린다. "
            "[D1] 의 60 × Ø2 는 같은 유량에서 0.9 m/s 로 링 유속과 비슷해져 "
            "먼 쪽 홀로는 공기가 가지 않고, 정지 중 분말이 역류해 막힌다. "
            "홀은 아래로 뚫어 콘 바닥을 향해 분다."
        ),
        approval="PROPOSED",
    ),
    Conflict(
        ref="C5",
        item="분산링 명칭",
        severity="MINOR",
        sources=(("[D1][D2]", "미세기포 분산링"), ("[R]", "Ring (급기)")),
        resolution="급기 분산링 (Air sparger ring)",
        rationale=(
            "Ø1.5 홀에서 나오는 기포는 계산상 약 3.9 mm 로 미세기포가 아니다. "
            "그리고 이 장치에서 미세기포는 오히려 방해가 된다 — 폴리머에 붙어 "
            "부선(flotation)으로 띄우면 [R] 이 재려는 밀도차 분리가 아니게 된다. "
            "공기는 분산 중에만 켜고 분리 중에는 꺼지므로 굵은 기포로 gas lift 만 "
            "얻으면 된다. 소결 스파저는 불필요하고 분말에 막히기만 한다."
        ),
        approval="PROPOSED",
    ),
    Conflict(
        ref="C6",
        item="운전 장입량",
        severity="MAJOR",
        sources=(
            ("[R]", "액면 Z720 · 총용적 89.9 L"),
            ("[D1]", '"50 L PILOT" 명판'),
        ),
        resolution="운전 장입 61.4 L (Z720) · 하한 50.0 L (Z629)",
        rationale=(
            "Z720 까지 채우면 61.4 L 다. 50 L 이 되는 액면은 Z629 인데, 그러면 "
            "스키머(Z725±20)와 N2 오버플로(Z735)가 액면보다 76 mm 이상 위에 떠서 "
            "부상층에 닿지 않는다. 즉 50 L 은 명칭이고 실제 운전 장입은 61.4 L 다. "
            "배치 질량수지를 61.4 L 로 잡지 않으면 고체농도가 23 % 틀린다."
        ),
        approval="RESOLVED",
    ),
    Conflict(
        ref="C7",
        item="계측 구성",
        severity="MAJOR",
        sources=(
            ("[D2]", "pH · 수위 · 온도 · 유량"),
            ("[R] §15", "실제 염수밀도·온도 · 시간별 층 높이"),
        ),
        resolution="전도도(염도) · 온도 RTD · 공기 로타미터 · 시료 사다리 5단",
        rationale=(
            "제어하는 변수는 염수 밀도지 pH 가 아니다. NaCl 은 pH 를 움직이지 "
            "않으므로 pH 센서는 이 장치에서 아무것도 알려주지 않는다. 대신 "
            "[R] 이 실제로 요구하는 두 값을 잰다 — 염도(전도도)와 온도다 "
            "(염수 밀도는 약 -0.3 kg/m³·K 로 온도에 끌린다). "
            "'시간별 층 높이' 는 불투명한 SUS 동체에 채취구가 한 곳뿐이면 잴 수 "
            "없으므로, [R] 의 N4 를 Z400~720 5 단 사다리로 늘렸다."
        ),
        approval="PROPOSED",
    ),
    Conflict(
        ref="C8",
        item="상부 커버 체결",
        severity="MINOR",
        sources=(
            ("[D1]", "Ø400 커버 · P.C.D 360 · 6-Ø9"),
            ("[D2]", "Ø400 커버 · P.C.D 150 · M12 × 8"),
            ("[R]", "Cover top Z951 (= t5)"),
        ),
        resolution="플랜지 OD Ø480 · PCD Ø450 · M12 × 12 · 면 홈에 EPDM O-링",
        rationale=(
            "[D1] 의 PCD 360 은 동체 안지름 Ø400 안쪽이라 볼트가 탱크 내부를 "
            "지난다. [D2] 의 PCD 150 은 Ø400 개구를 물지 못한다. 둘 다 성립하지 "
            "않으므로 동체 OD Ø406 바깥에 플랜지를 두른다. 가스켓을 플랜지 면에 "
            "판 홈에 넣으면 커버가 금속면에 직접 앉으므로 [R] 의 Z946/Z951 "
            "(= 커버 t5) 스택이 그대로 유지된다."
        ),
        approval="PROPOSED",
    ),
)

#: 발주 전 승인이 필요한 항목.
OPEN_FOR_APPROVAL: tuple[Conflict, ...] = tuple(c for c in CONFLICTS if c.approval == "PROPOSED")
