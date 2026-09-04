"""정비성 — MTTR 을 선언하지 않고 설계 기능에서 낸다.

`reliability.py` 는 블록마다 MTTR 을 계획값으로 들고 있었다. 3.0 h 라고 적혀
있을 뿐, **무엇이 그 시간을 만드는지**가 없었다. 그러면 "MTTR 을 줄이겠다" 는
말도 숫자를 고쳐 적는 일이 되어 버린다. 그래서 시간을 네 단계로 쪼개고, 각
단계를 줄이는 **설계 기능**을 붙여 MTTR 이 기능에서 파생되게 한다.

    MTTR = 진단 + 접근 + 교환 + 복귀

## 라인 복귀와 벤치 수리를 가른다

이것이 이 파일의 핵심이다. 유압 클램프 헤드를 현장에서 뜯어 고치면 3 시간이
걸린다. 그러나 **헤드째 갈아 끼우면** 라인은 교환 시간만에 돌아가고, 뜯어
고치는 일은 벤치에서 라인과 무관하게 진행된다. 가용률이 보는 것은 라인이 선
시간이지 수리가 끝난 시간이 아니다.

세계 최상급 설비가 30분 MTTR 을 내는 방법이 이것이다 — 빨리 고치는 것이
아니라 **고치지 않고 바꾼다.** 대신 값을 치른다: 교환 모듈은 예비 한 벌을
사 두어야 하고, 커플러·정렬 핀·무공구 체결이 설계에 들어가야 한다.

## 기능 넷

- ``diag``  온보드 진단 — 고장 코드가 부위를 짚는다. 찾는 시간이 사라진다
- ``access`` 정비 접근 — 공구 없이 열리는 커버, 한 사람이 닿는 자리(36 절)
- ``swap``  무공구 교환 모듈 — 커플러·정렬핀·퀵클램프. 현장 수리를 교환으로
- ``auto``  자동 복귀 — 원점복귀·인터록 리셋·시운전 1주기를 버튼 하나로
- ``dock``  전용 도킹 대차·레일 — 무거운 모듈을 **크레인 없이** 굴려서 뺀다

`dock` 은 계산이 요구해서 생긴 기능이다. 나머지 셋만 넣으면 무거운 블록
셋(BFC·AFR·GRM)이 0.588 h 로 목표를 넘었고, 남은 병목이 크레인 리깅
0.25 h 였다. 크레인을 거는 대신 모듈을 레일 위로 굴려 내면 그 자리가 풀린다 —
공작기계의 팰릿 체인저가 쓰는 방법과 같다. 값은 도킹 레일 3식이다.

곱하는 계수는 **계획값**이다. 벤더 실적이 아니라 이 기능을 넣었을 때 기대하는
단축률이고, run-at-rate 로 확인할 항목이다. 그래서 계수를 여기 한 곳에 모아
두었다 — 실측이 오면 이 줄만 고친다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 세계 최상급 목표 (h). SMRP 정비 우수사례 — 라인 정지 고장 30분 이내.
TARGET_MTTR_H = 0.5

#: 기능별 단축 계수 (계획값). 1.0 은 그 기능이 없을 때다.
FACTORS: dict[str, float] = {
    "diag": 0.15,     # 고장 코드가 부위를 짚으면 찾는 시간이 거의 사라진다
    "access": 0.35,   # 무공구 커버 + 한 사람이 닿는 자리
    "auto": 0.30,     # 원점복귀·인터록 리셋·시운전 1주기 자동
}

#: 교환 모듈이 있을 때의 라인 복귀 교환시간 (h). 무게로 갈린다 —
#: 크레인을 걸어야 하는 모듈은 손으로 드는 것보다 오래 걸린다.
SWAP_H = {"light": 0.12, "heavy": 0.25}

#: 도킹 레일이 있으면 무거운 모듈도 크레인 없이 굴러 나온다 (h).
#: 리깅·인양·정렬이 통째로 빠지므로 가벼운 모듈에 가까워진다.
DOCKED_HEAVY_SWAP_H = 0.15

#: 단계 배분 — 진단·접근·수리·복귀. 합이 1 이다.
#: 수리가 절반을 넘는 것이 요점이고, 교환 모듈이 바로 그 절반을 없앤다.
SHARE = {"diagnose": 0.20, "access": 0.15, "repair": 0.55, "restore": 0.10}


@dataclass(frozen=True)
class Profile:
    """블록 하나의 정비성.

    `base_h` 는 아무 기능도 없을 때의 현장 수리시간이다 — 종전 계획 MTTR 이
    그 값이고, 여기서 출발해야 개선이 추적된다.
    """

    tag: str
    base_h: float
    swap: str | None        # 'light' | 'heavy' | None(교환 모듈 없음)
    features: tuple[str, ...]
    module: str             # 무엇을 통째로 갈아 끼우는가
    basis: str

    def step_h(self, key: str) -> float:
        return self.base_h * SHARE[key]

    def diagnose_h(self) -> float:
        f = FACTORS["diag"] if "diag" in self.features else 1.0
        return round(self.step_h("diagnose") * f, 4)

    def access_h(self) -> float:
        f = FACTORS["access"] if "access" in self.features else 1.0
        return round(self.step_h("access") * f, 4)

    def exchange_h(self) -> float:
        """수리 단계. 교환 모듈이 있으면 현장 수리가 교환으로 바뀐다."""
        if self.swap is None:
            return round(self.step_h("repair"), 4)
        if self.swap == "heavy" and "dock" in self.features:
            return DOCKED_HEAVY_SWAP_H
        return SWAP_H[self.swap]

    def restore_h(self) -> float:
        f = FACTORS["auto"] if "auto" in self.features else 1.0
        return round(self.step_h("restore") * f, 4)

    def mttr_h(self) -> float:
        """라인이 서 있는 시간. 벤치 수리는 여기 안 들어간다."""
        return round(self.diagnose_h() + self.access_h()
                     + self.exchange_h() + self.restore_h(), 3)

    def bench_repair_h(self) -> float:
        """고장 난 모듈을 벤치에서 고치는 시간. 라인과 무관하다."""
        return round(self.step_h("repair"), 3)

    def meets_target(self) -> bool:
        return self.mttr_h() <= TARGET_MTTR_H


#: 블록별 정비성. base_h 는 종전 계획 MTTR 이다 — 개선 폭이 보이게 남긴다.
PROFILES: tuple[Profile, ...] = (
    Profile("RB-AFU", 2.0, "light", ("diag", "access", "auto"),
            "리프트 유압 파워팩 · 도킹 게이트 액추에이터",
            "지게차 인터페이스라 외란이 많다. 유압 파워팩을 카세트로 빼면 현장 수리가 없다"),
    Profile("RB-BFC", 3.0, "heavy", ("diag", "access", "auto", "dock"),
            "반전 드라이브 유닛 (모터·감속기·브레이크 일체)",
            "링 구동부가 무겁다 — 크레인 보조가 필요해 교환도 0.25 h 로 잡는다"),
    Profile("RB-ROBOT", 2.0, "light", ("diag", "access", "auto"),
            "EOAT 그리퍼 어셈블리 (진공 패드·힘센서 포함)",
            "OEM 본체는 견고하다. 마모는 EOAT 쪽이고 그것만 갈면 된다"),
    Profile("RB-JBR", 2.5, "light", ("diag", "access", "auto"),
            "제거 헤드 카트리지 3종 (칼날·가위·에어나이프)",
            "마모부가 가장 많다. 헤드를 카트리지로 만들면 무공구로 빠진다"),
    Profile("RB-AFR", 3.0, "heavy", ("diag", "access", "auto", "dock"),
            "클램프 헤드 유닛 (유압 실린더·힘센서·조 일체)",
            "25 kN 인발 부하부라 무겁다. 퀵커플러로 유압을 끊고 헤드째 교환한다"),
    Profile("RB-POST", 2.0, "light", ("diag", "access", "auto"),
            "연마 스핀들 카트리지 · 라인스캔 조명 모듈",
            "연마휠 교체가 잦다 — 스핀들째 갈면 정렬을 다시 안 잡아도 된다"),
    Profile("RB-GBR", 2.0, "light", ("diag", "access", "auto"),
            "슬롯 로더 콤포크 어셈블리",
            "셔틀·슬롯 로더. 포크 조립체가 마모부이자 정렬부다"),
    Profile("RB-GRM", 3.0, "heavy", ("diag", "access", "auto", "dock"),
            "IR 램프 뱅크 트레이 · 핫나이프 헤드",
            "램프 60개를 트레이 단위로 뺀다. 핫나이프는 열간 작업이라 접근 설계가 크게 듣는다"),
    Profile("RB-UTIL", 1.5, "light", ("diag", "access", "auto"),
            "컴프레서 스키드 · 진공 펌프 유닛",
            "이미 1운전 1예비라 교환 자체가 예비기로의 전환이다"),
)

PROFILE_BY_TAG: dict[str, Profile] = {p.tag: p for p in PROFILES}


def mttr_h(tag: str) -> float:
    return PROFILE_BY_TAG[tag].mttr_h()


def worst() -> Profile:
    return max(PROFILES, key=lambda p: p.mttr_h())


def missing_target() -> tuple[Profile, ...]:
    """목표를 아직 못 맞춘 블록. 있으면 숨기지 않는다."""
    return tuple(p for p in PROFILES if not p.meets_target())


def docked_modules() -> tuple[Profile, ...]:
    """전용 도킹 레일이 필요한 무거운 모듈. 크레인을 안 쓰려면 이것이 있어야 한다."""
    return tuple(p for p in PROFILES if "dock" in p.features)


def swap_modules() -> tuple[Profile, ...]:
    """예비 한 벌을 사 둬야 하는 교환 모듈. 정비성의 대가다."""
    return tuple(p for p in PROFILES if p.swap is not None)


def improvement() -> dict[str, float]:
    before = max(p.base_h for p in PROFILES)
    after = worst().mttr_h()
    return {"beforeH": before, "afterH": after, "ratio": round(before / after, 2)}


def summary() -> dict[str, object]:
    return {
        "targetH": TARGET_MTTR_H,
        "blocks": len(PROFILES),
        "worst": worst().tag,
        "worstH": worst().mttr_h(),
        "missing": tuple(p.tag for p in missing_target()),
        "swapModules": len(swap_modules()),
        "dockRails": len(docked_modules()),
        "improvement": improvement(),
    }
