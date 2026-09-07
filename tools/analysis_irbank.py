"""IR 뱅크 배치 검토 — 면내 온도편차 R1 을 닫는다.

열해석(CAL-001)이 요구 R1 을 만들어 놓고 스스로 못 닫았다. 1 차원은
두께 방향만 보므로 **면내** 편차를 원리적으로 낼 수 없고, 그 편차는 램프
배치와 반사면이 정한다. 여기서 그것을 푼다.

푸는 이유는 유리 열응력만이 아니다. 실제 운전 규칙이 **가장 찬 점이
140 ℃ 에 닿을 때까지 소킹한다** 이기 때문에, 면내 편차는 두 곳을 동시에
친다:

    ① 체류시간이 늘어난다      → 처리량이 깎인다 (계약 60 장/h)
    ② 중앙이 넘친다            → 백시트가 녹는다 (PVDF 165 ℃)

②가 창을 정한다. 165 − 140 − 7(두께방향 오프셋) = **18 K** 밖에 없다.
유리 열응력이 주는 21 K 보다 **더 좁다** — 유리보다 백시트가 먼저 진다.

── 현행 설계로는 닫히지 않는다 ────────────────────────────────────
카탈로그의 램프는 **1,300 mm** 이고 패널 폭은 1,200 mm 다. 끝단 여유가
50 mm 뿐이라 유한 선원의 끝에서 유속이 급락한다 — 폭 가장자리가 중앙의
69 % 다. 균등 배치의 길이 방향 결손(끝단)까지 더하면 면내 편차가
**87 K** 이고, 냉점을 140 에 올리면 백시트가 **235 ℃** 로 사라진다.
체류는 327 초로 늘어 처리량이 49.5 장/h 로 떨어진다 — 계약이 깨진다.

── 무엇이 듣고 무엇이 안 듣는가 ──────────────────────────────────
· **램프 발열장**  가장 크게 듣는다. 결손이 램프 축을 따라 있기 때문이다
· **길이방향 배치**  듣는다. 끝을 바깥으로 밀어 ±1,340 까지 쓴다
· **내피 반사율**  크게 듣는다. 연마 STS 가 하는 일이 장식이 아니었다
· **인접 뱅크 반피치 엇갈림**  **안 듣는다.** 오히려 나빠진다 — 편차의
  정체가 램프 사이 맥놀이가 아니라 가장자리 결손이라, 엇갈리면 끝쪽
  램프가 가장자리에서 멀어진다. 처음에 듣는다고 봤고 모델이 아니라고 했다
· **존 출력 제어**  거의 안 듣는다. SSR 로 램프별 듀티를 잡아도 결손이
  **램프 축 방향**에 있어서 자기 축을 따라서는 못 고친다. 산업용 IR 로의
  표준 해법이 여기서는 표준이 아니다

해석기는 tools/irbank.py — 유한 선원 조사도의 닫힌해 + 정반사 이미지 +
면내 2 차원 과도 전도.

**이 검토가 못 보는 것**: 램프의 방향성 복사(반사판 형상이 만드는 배광),
석영관 자체의 재복사, 패널 표면의 파장별 흡수율, 셔터가 열릴 때의 과도.
그것은 파일럿 PT-04 가 열화상으로 실측한다.
"""

from __future__ import annotations

import pathlib
import sys
from typing import NamedTuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import cycle as CY  # noqa: E402
import irbank as IR  # noqa: E402
from analysis_thermal import Result  # noqa: E402
from console_consts import const as c  # noqa: E402

TAKT = round(CY.TAKT, 1)          # s 라인 사이클 (콘솔 thermalModel) — 피치가 이보다 짧아야 한다
DWELL_MAX = TAKT * IR.DECKS       # s 체류 상한 = 택트 × 단수
T_TARGET = c("T_TARGET")          # 140 ℃ 냉점 목표
T_BACK_MAX = 165.0                # PVDF 융점
DT_GLASS = 21.0                   # K 유리 허용 면내 편차 (CAL-001 R1)
Q_PANEL = CY.USEFUL_KW * 1000 / IR.DECKS   # W/장 — 유효 IR 출력 ÷ 단수 (1D 열수지)
DWELL_1D = round(CY.DWELL, 1)     # s 콘솔 1D 열수지의 체류 — 냉점 기준과 비교한다

# ── 관습 배치와 확정 배치 ────────────────────────────────────────────────
# '관습' 은 2,400 × 1,200 시절 도면이 하던 대로를 포락선에 옮긴 것이다 —
# 균등 간격, 발열장은 패널 폭 + 끝단 여유 2×50. 포락선이 커져도 그 관습이
# 왜 안 되는지는 같은 이유로 같은 자리에서 드러난다.
NOW_N = IR.LAMPS // (IR.DECKS + 1)               # 뱅크당 램프 — 6뱅크 × 8
NOW_SPAN = IR.DECK_L - 0.30                      # 균등 배치 스팬 — 데크 안쪽 150
NOW_LEN = c("PANEL_W") + 0.10                    # 관습 발열장 — 패널 폭 + 2×50
NEW_LEN = IR.LAMP_LEN                            # 발열장 — 공동 폭 −100 · 단자는 벽 밖 (콘솔 LAMP_HEAT)
# IR.optimize(8, length=NEW_LEN) — 면내 편차 최소 · 인접 뱅크 동일 위치 (엇갈림은 나빠진다)
NEW_X = (-1.390, -1.062, -0.637, -0.213, 0.213, 0.637, 1.062, 1.390)
RHO_SPEC = 0.40         # 내피 반사율 **하한** — 사양·검사·정비 항목
RHO_POLISHED = 0.80     # 연마 STS304 #400 (ε 0.2) 의 실제값


def _case(lamps, rho):
    f = IR.field(IR.images(lamps, rho), 61, 31).scaled(Q_PANEL)
    dwell, T = IR.soak_to_cold(f, T_TARGET)
    s = IR.stats(T)
    nx, ny = len(f.xs), len(f.ys)
    # 백시트는 계면보다 두께 방향으로 앞선다. 설계유속 4,514 W/m² 에서
    # 7.0 K 였으므로(CAL-001 T2) 국부 유속에 비례해 늘린다.
    back = s["centre"] + 7.0 * f.E[nx // 2][ny // 2] / 4514.0
    return dict(field=f, dwell=dwell, back=back, pitch=dwell / IR.DECKS,
                rate=3600 / max(dwell / IR.DECKS, TAKT) * 0.90, **s)


def now(rho=RHO_POLISHED):
    return _case(IR.even(NOW_N, NOW_SPAN, length=NOW_LEN) * 2, rho)


def new(rho=RHO_POLISHED):
    return _case(IR.from_positions(list(NEW_X), length=NEW_LEN) * 2, rho)


def run():
    a, b, bs = now(), new(), new(RHO_SPEC)
    fn = IR.field(IR.images(IR.from_positions(list(NEW_X), length=NEW_LEN) * 2,
                            RHO_POLISHED), 61, 31)
    nx, ny = len(fn.xs), len(fn.ys)
    rx = [fn.E[i][ny // 2] for i in range(nx)]
    ry = [fn.E[nx // 2][j] for j in range(ny)]
    dx = (max(rx) - min(rx)) / (sum(rx) / len(rx))
    dy = (max(ry) - min(ry)) / (sum(ry) / len(ry))
    clear = (IR.CAVITY_W - NEW_LEN) / 2 * 1000
    # 관습 배치의 같은 두 비율과, 폭 가장자리 유속의 중앙 대비
    fa = IR.field(IR.images(IR.even(NOW_N, NOW_SPAN, length=NOW_LEN) * 2,
                            RHO_POLISHED), 61, 31)
    arx = [fa.E[i][ny // 2] for i in range(nx)]
    ary = [fa.E[nx // 2][j] for j in range(ny)]
    ax = (max(arx) - min(arx)) / (sum(arx) / len(arx))
    ay = (max(ary) - min(ary)) / (sum(ary) / len(ary))
    ex_edge = min(ary[0], ary[-1]) / ary[ny // 2]
    pos_txt = "·".join(f"{x*1000:.0f}" for x in NEW_X if x > 0)

    return [
        Result("IR1", "현행 배치의 면내 온도편차", a["spread"], "K", DT_GLASS,
               "유리 허용 면내 편차 21 K (CAL-001 R1 · σ ≈ ½Eα·ΔT)",
               f"램프 {NOW_LEN*1000:.0f} mm 에 패널 폭 {c('PANEL_W')*1000:.0f} mm — "
               f"끝단 여유가 50 mm 뿐이라 폭 가장자리가 중앙의 {ex_edge:.0%} 다. "
               f"**유리가 깨진다**"),
        Result("IR2", "현행 배치 · 냉점 140 ℃ 시점의 백시트", a["back"], "℃",
               T_BACK_MAX, "PVDF 백시트 융점 165 ℃",
               f"냉점을 목표에 올리는 순간 중앙은 {a['centre']:.0f} ℃ 다. "
               f"**감아서 팔 물건이 그 자리에서 없어진다** — 이 설비가 파는 "
               f"세 가지 중 하나가 공정 안에서 사라진다"),
        Result("IR3", "현행 배치의 소요 체류시간", a["dwell"], "s", DWELL_MAX,
               f"택트 {TAKT} s × {IR.DECKS} 단 = {DWELL_MAX:.0f} s",
               f"평균이 아니라 **냉점**이 140 에 닿아야 하므로 설계 {DWELL_1D} s "
               f"로는 안 된다. 피치 {a['pitch']:.0f} s → {a['rate']:.1f} 장/h. "
               f"**계약 {CY.NET_TARGET} 장/h 가 깨진다**"),
        Result("IR4", "개선 배치의 면내 온도편차", b["spread"], "K", DT_GLASS,
               "유리 허용 면내 편차 21 K — 다만 실제 창은 백시트가 정한다 (IR5)",
               f"발열장 {NEW_LEN*1000:.0f} · 위치 ±{{{pos_txt}}} · "
               f"내피 ρ {RHO_POLISHED:.1f}. 길이방향 {dx:.1%} · 폭방향 {dy:.1%} 로 "
               f"두 방향이 균형을 이룬다 (관습 배치는 {ax:.0%} : {ay:.0%})"),
        Result("IR5", "개선 배치 · 냉점 140 ℃ 시점의 백시트", b["back"], "℃",
               T_BACK_MAX, "PVDF 융점 165 ℃ — 유리(21 K)보다 이쪽이 먼저 좁다",
               f"여유 {T_BACK_MAX-b['back']:.1f} K. 내피가 오손되어 반사율이 "
               f"**절반으로 떨어져도**({RHO_SPEC:.1f}) {bs['back']:.1f} ℃ 로 "
               f"여유 {T_BACK_MAX-bs['back']:.1f} K 가 남는다 (IR7)"),
        Result("IR6", "개선 배치의 소요 체류시간", b["dwell"], "s", DWELL_MAX,
               f"택트 {TAKT} s × {IR.DECKS} 단",
               f"피치 {b['pitch']:.0f} s < 택트 {TAKT} s 이므로 **처리량을 "
               f"탠덤이 정한다** — {b['rate']:.1f} 장/h 로 계약이 유지된다. "
               f"설계 {DWELL_1D} s 보다 {b['dwell']-DWELL_1D:.0f} s 길어진 것은 "
               f"평균이 아니라 냉점을 목표에 올리기 때문이다"),
        Result("IR7", "내피 반사율 요구 하한", RHO_SPEC, "—", RHO_POLISHED,
               "연마 STS304 #400 (ε 0.2) 이 주는 실측 기대값 0.75~0.85",
               f"ρ {RHO_SPEC:.1f} 에서 백시트 {bs['back']:.1f} ℃ · 편차 "
               f"{bs['spread']:.1f} K 로 통과한다. 요구는 실제값의 절반이므로 "
               f"**오손 여유가 2 배**다. 다만 이것은 이제 미관이 아니라 "
               f"**검사·정비 항목**이다 — 내피가 그을면 유리가 깨진다"),
        Result("IR8", "램프 발열장 vs 공동 폭", NEW_LEN * 1000, "mm",
               IR.CAVITY_W * 1000,
               f"내부 공동 폭 {IR.CAVITY_W*1000:.0f} mm",
               f"양측 여유 {clear:.0f} mm. **단자는 측벽을 관통해 밖에 둔다** — "
               f"길이를 벌기 위해서만이 아니라 석영램프 단자는 고온부 밖에 "
               f"있어야 수명이 산다. 램프 교체도 챔버를 열지 않고 한다. "
               f"대가는 뱅크당 {2*len(NEW_X)} · 총 {2*IR.LAMPS} 개소의 관통 실링이다"),
    ], dict(now=a, new=b, new_soiled=bs, dx=dx, dy=dy, clear=clear,
            ax=ax, ay=ay, edge=ex_edge)


class Req(NamedTuple):
    id: str
    what: str
    value: str
    owner: str
    why: str


def requirements() -> list[Req]:
    """이 검토가 확정한 것과, 확정하지 못하고 넘기는 것."""
    _, ex = run()
    return [
        Req("RIR1", "IR 램프 발열장",
            f"{NEW_LEN*1000:.0f} mm (관습 {NOW_LEN*1000:,.0f})",
            "부품 카탈로그 P-002-18 · 구매 사양",
            f"면내 결손의 정체가 램프 축 방향이라 **길이가 유일하게 크게 듣는 "
            f"기하 변수**다. {NOW_LEN*1000:,.0f} 은 패널 폭 {c('PANEL_W')*1000:,.0f} 에 "
            f"끝단 여유 50 mm 뿐이고, 그 상태로는 어떤 배치·어떤 출력제어로도 "
            f"창이 닫히지 않는다"),
        Req("RIR2", "뱅크 램프 x 위치",
            "±" + "·".join(f"{x*1000:.0f}" for x in NEW_X if x >= 0) + " mm",
            "콘솔 도면 · F-002 제작도",
            f"균등 배치가 아니다. 끝을 바깥으로 밀어 패널 끝단(±{c('PANEL_L')*500:,.0f})을 "
            f"넘긴다 — 끝 램프가 패널 안쪽에 있으면 그 바깥은 아무도 데우지 "
            f"않는다. 인접 뱅크는 **같은 위치**를 쓴다 (엇갈리면 나빠진다)"),
        Req("RIR3", "내피 반사율",
            f"ρ ≥ {RHO_SPEC:.1f} — 사양 6.3 · 제작 11.1 · ITP 8 · FAT · 정비 매뉴얼 (반영 완료)",
            "사양서 6.3 · 제작 지침서 11.1 / ITP 8 · FAT 항목 · 정비 매뉴얼",
            f"연마 STS304 #400 이 {RHO_POLISHED:.1f} 를 주므로 요구는 그 절반이다. "
            f"그러나 **오손되면 유리가 깨진다** — 지금까지 내피는 내식·복사면으로만 "
            f"적혀 있었고 반사율은 아무도 요구하지 않았다. 이제 네 곳에 들어갔다: "
            f"발주 사양(6.3), 표면처리 사양(11.1 · 연마 #400), **ITP 8 — 램프 장착 "
            f"전에 9 점 측정**(붙이고 나면 잴 자리가 없다), 정비 매뉴얼(연 1 회 · "
            f"미달 시 재연마). **치수가 같아 도면으로는 2B 소지와 구분이 안 되므로 "
            f"검사 항목이 아니면 지켜지지 않는다**"),
        Req("RIR4", f"{NEW_LEN*1000:,.0f} mm 램프의 지지·관통 상세",
            "별도 검토로 해소 — tools/lampmount.py (LM1~LM7 · RLM1~RLM5)",
            "상세설계 · 구매 사양",
            f"넘길 때 '처짐 · 실링 · 그림자' 셋을 적었는데 풀어 보니 **적지 "
            f"않은 둘이 더 컸다** — 강재·석영 차등 열팽창(양단 고정하면 첫 "
            f"승온에서 램프가 뜯긴다)과 봉착부 온도 창(물리가 주는 창이 제작 "
            f"공차보다 좁다). 처짐은 1.8 mm 로 문제가 아니었고, 지지가 필요 "
            f"없으니 그림자도 사라졌다 — 걱정한 셋 중 둘이 서로를 지웠다"),
        Req("RIR5", "이 배치의 실측 검증", "파일럿 PT-04 · 열화상 전폭",
            "파일럿 시험 계획 PIL-001",
            f"이 검토는 램프를 등방 선원으로, 벽을 정반사로 놓았다. 실제 "
            f"반사판은 배광을 만들고 연마면은 확산이 섞인다. 예측 면내 편차 "
            f"{ex['new']['spread']:.0f} K 를 열화상으로 확인하고, 어긋나면 "
            f"위치가 아니라 **반사판 형상**부터 본다"),
    ]


def report() -> str:
    L, add = [], None
    L = []
    add = L.append
    add("=" * 78)
    add("DG-HK60C IR 뱅크 배치 검토 — 면내 온도편차")
    add("=" * 78)
    add("")
    add("── 검토 ────────────────────────────────────────────────")
    add(f"   {'ID':4s} {'항목':34s} {'값':>9s} {'한계':>9s} {'이용률':>7s}  판정")
    rs, ex = run()
    bad = 0
    for r in rs:
        add(f"   {r.id:4s} {r.what[:34]:34s} {r.value:9.2f} {r.limit:9.2f} "
            f"{r.util:6.0%}  {'OK' if r.ok else '★ 초과'}")
        bad += 0 if r.ok else 1
    add("")
    add("── 근거 ────────────────────────────────────────────────")
    for r in rs:
        add(f"   {r.id}  {r.basis}")
        add(f"       {r.note}")
    add("")
    add("── 확정 배치 ───────────────────────────────────────────")
    add(f"   램프        발열장 {NEW_LEN*1000:.0f} mm · 2.5 kW · 뱅크당 "
        f"{len(NEW_X)} 등 (총 {IR.LAMPS} 등)")
    add(f"   위치        x = " + " · ".join(f"{x*1000:+.0f}" for x in NEW_X) + " mm")
    add(f"   단자        측벽 관통 · 챔버 밖 소켓 (뱅크당 {2*len(NEW_X)} · 총 {2*IR.LAMPS} 개소)")
    add(f"   내피        연마 STS304 #400 · 반사율 ρ ≥ {RHO_SPEC:.1f} (검사·정비)")
    add(f"   엇갈림      쓰지 않는다 — 인접 뱅크는 같은 x 위치")
    add("")
    add("── 이 검토가 만든 요구 ─────────────────────────────────")
    for q in requirements():
        add(f"   {q.id}  {q.what} — {q.value}")
        add(f"       받는 곳: {q.owner}")
    add("")
    add("=" * 78)
    add("전 항목 만족" if not bad else f"★ {bad} 항목 초과 (관습 배치 IR1~IR3)")
    add("=" * 78)
    return "\n".join(L)


if __name__ == "__main__":
    print(report())
