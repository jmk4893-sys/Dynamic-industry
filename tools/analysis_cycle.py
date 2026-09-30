"""사이클 검토 — 택트 안에 드는가 (CY1~CY9).

열해석은 가열실이 패널을 제때 데우는지를, 칼날 사이클은 박리가 제때 끝나는지를 본다.
그 사이를 잇는 것은 **승강 포크**다. LI·EX·GL·GU 네 문형이 한 택트에 한 번 패널을
공정 높이와 데크 사이로 옮긴다 — 가장 긴 경우 공정 높이 ↔ 최상단을 오르내린다.

카탈로그는 처음에 Ø32 리드 10 볼스크류를 서보로 **돌리게** 적었다. 긴 스크류를
돌리면 휨 진동의 공진 — **위험속도** — 가 회전수를 막는다. 고정-지지로 3 m 를 넘기면
500 rpm 아래이고 리드 10 이면 70 mm/s 대라, 최상단 왕복만으로 표준 택트를 넘는다
(CY5). 그래서 너트를 돌린다 (회전 너트식 · 스크류는 양끝 고정): 스크류가 돌지 않으니
공진이 없고, 속도는 너트 회전과 볼너트의 d·n 이 정한다 (CY4 · CY6). 이 검토는 표준을
위해 쓴 것이지만, 옵션은 택트가 반이고 행정이 길어 같은 문제가 두 배로 온다.

옵션(DG-HK120C)에서는 셋을 더 본다 — 가열실이 두 셀을 먹이는가(CY1), 한 셀이 서도
계약을 지키는가(CY3), EX·GL 의 횡이송이 제 셀의 사이클 안에 드는가(CY8 · CY9).

같은 코드가 두 설비를 푼다 — 옵션은 variant 가 핀을 박고 이 모듈을 다시 부른다.
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cycle as CY  # noqa: E402
import fab_spec as F  # noqa: E402
import parts as PT  # noqa: E402
from analysis_thermal import Req, Result  # noqa: E402

# ── 볼스크류 위험속도 — 종전 설계(스크류를 돌린다)를 되짚는 데 쓴다 ────────
E_SCREW = 206000.0      # MPa
RHO_SCREW = 7850.0      # kg/m³
D_ROOT = 26.4           # mm Ø32 리드 10 의 골지름 (제작사 표준 치수)
LAM_FS = 3.927          # 고정-지지 위험속도 계수 λ (고정-고정이면 4.730)
N_FACTOR = 0.80         # 허용 회전수 = 위험속도 × 0.8
OLD_LEAD = 10.0         # mm 종전 카탈로그의 리드
BEARING_END = 60.0      # mm 스크류 양끝에서 지지 유닛 중심까지

# ── 서보 출력 ──────────────────────────────────────────────────────────
ETA_DRIVE = 0.85        # 볼너트 0.90 × 타이밍 벨트 0.95
ACCEL = 0.5             # m/s² 승강 가감속
SERVO_KW = 1.5          # P-003-09 정격


def critical_rpm(span_mm: float, d_root: float = D_ROOT, lam: float = LAM_FS) -> float:
    """스크류를 돌릴 때의 위험속도 rpm — 휨 진동 1차 공진."""
    d = d_root / 1000
    i_ = math.pi * d ** 4 / 64
    a_ = math.pi * d ** 2 / 4
    omega = lam ** 2 / (span_mm / 1000) ** 2 * math.sqrt(E_SCREW * 1e6 * i_ / (RHO_SCREW * a_))
    return omega * 60 / (2 * math.pi)


def _by_id():
    return {p.pid: p for p in PT.P}


def screw_span() -> float:
    return _by_id()["P-003-07"].shape.d["L"] - 2 * BEARING_END


def moving_kg() -> float:
    """문형 하나가 드는 것 — 캐리지 · 리브 · 포크 · 티인 + 패널."""
    b = _by_id()
    per = {"P-003-12": 1, "P-003-13": 4, "P-003-14": 1, "P-003-15": 2}
    return sum(b[k].kg * n for k, n in per.items()) + F.W_PANEL * 1000 / 9.81


def lift_cycle(v: float) -> float:
    """가장 긴 승강 왕복 + 포크 출입 (s)."""
    return 2 * PT.LIFT_MAX / 1000 / v + PT.FORK_IO


def run():
    m = CY.model()
    takt = CY.TAKT
    rs, ex = [], {}

    # CY1 · CY2 · CY3 — 가열실과 칼날이 계약을 내는가
    cells = int(CY.MODEL["cells"])
    rs.append(Result(
        "CY1", "가열실 방출 피치 ≤ 라인 택트", m["pitch"], "s", takt,
        f"라인 택트 {takt:.2f} s — 피치가 더 길면 가열실이 처리량을 정한다",
        f"{PT.DECKS}단 · {PT.LAMPS}등 · 유효 {m['useful']:.0f} kW 에서 체류 {m['dwell']:.1f} s ÷ "
        f"{PT.DECKS} = {m['pitch']:.2f} s. "
        + (f"칼날 셀 {cells}개가 사이클 {m['knifeCycle']:.2f} s 를 반씩 나눠 택트가 "
           f"{takt:.2f} s 다 — 가열실이 따라온다" if cells > 1 else
           f"칼날 사이클 {m['knifeCycle']:.2f} s 가 택트를 정하고 가열실은 여유가 있다")))
    net = CY.RATE_NET
    rs.append(Result(
        "CY2", "계약 순생산 대비 모델 순생산", float(CY.NET_TARGET), "장/h", net,
        f"모델 순생산 {net:.1f} 장/h (명목 × 가동률 {CY.AVAILABILITY:.0%}) — 계약이 이 안이어야 판다",
        f"계약 {CY.NET_TARGET} 장/h" + (f" = 셀 {cells} × 표준 계약 {CY.NET_TARGET // cells}" if cells > 1 else "")
        + f". 여유 {net - CY.NET_TARGET:.1f} 장/h 는 박리력(OI-01)이 높게 나와 박리속도를 내릴 몫이다"))
    if cells > 1:
        one = 3600 / m["knifeCycle"] * CY.AVAILABILITY
        base = CY.NET_TARGET // cells
        rs.append(Result(
            "CY3", "한 셀이 서도 표준 계약을 지키는가", float(base), "장/h", one,
            f"남은 셀 하나의 순생산 {one:.1f} 장/h — 표준 계약 {base} 장/h 가 이 안이어야 한다",
            f"칼날 사이클 {m['knifeCycle']:.2f} s 는 셀 하나의 것이다 — 한 셀이 정비·교환으로 서면 라인은 "
            f"표준과 같은 설비가 된다. 이것이 처리량 2 배와 함께 파는 것이다 (검토서 6장)"))

    # CY4 · CY5 · CY6 · CY7 — 승강축
    span = screw_span()
    n_c = critical_rpm(span)
    v_old = N_FACTOR * n_c * OLD_LEAD / 60 / 1000
    t_new, t_old = lift_cycle(PT.FORK_LIFT_V), lift_cycle(v_old)
    rs.append(Result(
        "CY4", "승강 포크 사이클 — 회전 너트식 (확정)", t_new, "s", takt,
        f"라인 택트 {takt:.2f} s — 한 택트에 한 번 가장 긴 승강을 왕복한다",
        f"공정 높이 ↔ 최상단 {PT.LIFT_MAX:,.0f} 왕복을 {PT.FORK_LIFT_V:.2f} m/s 로 "
        f"{2 * PT.LIFT_MAX / 1000 / PT.FORK_LIFT_V:.1f} s + 포크 출입 {PT.FORK_IO:.1f} s "
        f"({PT.FORK_REACH:,.0f} 을 {PT.FORK_V:.2f} m/s 로 왕복 + 확인 2 s). 속도는 택트의 85 % 에서 "
        f"거꾸로 푼 등급이다 — 너트 {PT.FORK_NUT_RPM:,.0f} rpm · 리드 {PT.FORK_LEAD:.0f}"))
    rs.append(Result(
        "CY5", "스크류를 돌렸다면 (쓰지 않는다)", t_old, "s", takt,
        f"같은 택트 {takt:.2f} s — 종전 카탈로그(Ø32 리드 {OLD_LEAD:.0f} · 스크류 회전)의 값",
        f"지지 간격 {span:,.0f} 의 위험속도 {n_c:,.0f} rpm (고정-지지 · 골지름 {D_ROOT}) × {N_FACTOR:.1f} "
        f"→ {v_old * 1000:.0f} mm/s. 이 속도로는 최상단 왕복만 {2 * PT.LIFT_MAX / 1000 / v_old:.0f} s 다 — "
        f"**서보를 키워도 안 풀린다.** 막는 것은 출력이 아니라 공진이기 때문이다. 그래서 너트를 돌린다"))
    dn = PT.FORK_SCREW_D * PT.FORK_NUT_RPM
    rs.append(Result(
        "CY6", "회전 너트 d·n", dn, "mm·rpm", PT.FORK_DN_MAX,
        f"순환식 볼너트 d·n 상한 {PT.FORK_DN_MAX:,.0f} — 넘으면 볼 순환이 무너진다",
        f"Ø{PT.FORK_SCREW_D:.0f} × {PT.FORK_NUT_RPM:,.0f} rpm. 리드는 이 상한 안에 드는 가장 작은 "
        f"유통 리드({PT.FORK_LEAD:.0f})로 골랐다 — 작을수록 같은 서보로 힘이 세고 위치가 곱다"))
    kg = moving_kg()
    half = kg / 2
    p_kw = half * (9.81 + ACCEL) * PT.FORK_LIFT_V / ETA_DRIVE / 1000
    rs.append(Result(
        "CY7", "승강 서보 소요 출력 (스크류 한 조)", p_kw, "kW", SERVO_KW,
        f"P-003-09 정격 {SERVO_KW:.1f} kW — 두 조가 전자 동기로 나눠 든다",
        f"캐리지·포크·티인·패널 {kg:.0f} kg 의 절반을 {PT.FORK_LIFT_V:.2f} m/s · 가속 {ACCEL} m/s² 로 — "
        f"구동효율 {ETA_DRIVE:.2f} (볼너트 × 벨트)"))

    # CY8 · CY9 — 옵션 횡이송 (EX·GL)
    if PT.TWIN:
        cell_cycle = m["knifeCycle"]
        t_tr = (2 * PT.TR_REACH / 1000 / PT.FORK_V + 2 * PT.TR_TRAVEL / 1000 / PT.TR_V
                + 2 * PT.TR_STROKE / 1000 / PT.TR_VZ + 2 * 1.0)
        rs.append(Result(
            "CY8", "횡이송 캐리지 사이클 ≤ 제 셀의 사이클", t_tr, "s", cell_cycle,
            f"셀 하나의 칼날 사이클 {cell_cycle:.2f} s — 캐리지는 제 셀만 먹인다",
            f"인계 인출 {PT.TR_REACH:,.0f} 왕복 · 이송 {PT.TR_TRAVEL:,.0f} 왕복 ({PT.TR_V:.1f} m/s) · "
            f"강하 {PT.TR_STROKE:,.0f} 왕복 ({PT.TR_VZ:.1f} m/s) · 핀 체결·확인 2 s. 가정 속도의 계산이다 — "
            f"실측은 검토서 OI-T2 가 FAT 에서 한다"))
        hand = PT.TR_C - 260                            # 접힌 포크 하단 — 인계 높이
        travel = max(PT.deck_z(PT.DECKS - 1) - hand, hand - PT.deck_z(0))
        t_ex = 2 * travel / 1000 / PT.FORK_LIFT_V + PT.FORK_IO + 2.0
        rs.append(Result(
            "CY9", "EX·GL 문형 사이클 (데크 ↔ 인계 높이) ≤ 택트", t_ex, "s", takt,
            f"라인 택트 {takt:.2f} s — EX 는 A/B 를 번갈아 한 택트에 한 장씩 낸다",
            f"데크와 인계 높이 EL {hand:,.0f} 사이 최장 {travel:,.0f} 왕복 + 포크 출입 {PT.FORK_IO:.1f} s + "
            f"인계 2 s. 공정 높이까지 내려가지 않으므로 LI·GU(CY4)보다 짧다"))
        ex.update(t_tr=t_tr, t_ex=t_ex, cell_cycle=cell_cycle)

    ex.update(span=span, n_c=n_c, v_old=v_old, t_new=t_new, t_old=t_old, dn=dn, kg=kg, p_kw=p_kw)
    return rs, ex


def requirements() -> list[Req]:
    rs, ex = run()
    return [
        Req("RCY1", "승강축은 너트를 돌린다",
            f"회전 너트식 Ø{PT.FORK_SCREW_D:.0f} 리드 {PT.FORK_LEAD:.0f} · {PT.FORK_LIFT_V:.2f} m/s · 스크류 양끝 고정",
            "상세설계 · M-003 (P-003-07 · 08 · 09) · 구매 사양",
            f"스크류를 돌리면 지지 간격 {ex['span']:,.0f} 에서 위험속도가 {ex['n_c']:,.0f} rpm 이라 "
            f"{ex['v_old'] * 1000:.0f} mm/s 를 못 넘고, 최장 왕복만으로 택트를 넘는다 (CY5 {ex['t_old']:.0f} s). "
            f"서보를 키워도 공진은 그대로다 — 너트를 돌리면 스크류에는 인장만 걸리고 공진이 사라진다. "
            f"서보는 캐리지에 실려 오르내리므로 케이블 캐리어가 붙는다"),
    ]


def report() -> str:
    rs, _ = run()
    L = [f"{PT.MODEL} 사이클 검토"]
    for r in rs:
        L.append(f"  {r.id:4s} {r.what[:34]:34s} {r.value:10.2f} {r.unit:7s} / {r.limit:10.2f}  "
                 f"{r.util:5.0%} {'OK' if r.ok else '★'}")
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
