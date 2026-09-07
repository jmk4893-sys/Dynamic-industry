"""후단 인계 균형 두 안을 각각 반영한 미니앱 두 벌을 만든다.

실행 (저장소 루트에서):
    PYTHONPATH=src python tools/build_handoff_variants.py out/

유입 66.0 대 처리 46.5 장/h 의 격차 19.5 를 어디서 흡수하느냐가 두 안이다.

* **B안 — 후단 개선.** 전처리는 그대로 두고 박리 라인의 칼날을 상한까지,
  인계를 듀얼 진공테이블로 줄인다. 그 앱의 입력 기본값을 바꿔 열자마자
  균형 상태가 보이게 한다. 전처리 도면은 손대지 않는다.
* **C안 — 전처리 감속.** 박리 라인은 그대로 두고 전처리가 방출을 보류해
  택트를 늘린다. 캠페인 스케줄 리터럴을 보류를 넣어 다시 만들어 박아
  넣는다 — 화면의 공정시계·택트·처리량이 전부 따라 움직인다.

두 벌 다 원본을 복사해 고치는 것이라, 도면이 바뀌면 다시 돌리면 된다.
"""

from __future__ import annotations

import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from pv_preprocess import campaign, handoff  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLANT = ROOT / "docs" / "drawings" / "pv-preprocess-plant.html"
DELAM = ROOT / "docs" / "drawings" / "pv-delam-tandem.html"


def _replace_once(text: str, old: str, new: str, what: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{what}: 앵커가 {text.count(old)}개 — 1개여야 한다\n  {old[:80]}")
    return text.replace(old, new)


def build_plan_b(out: pathlib.Path) -> list[pathlib.Path]:
    """박리 라인의 입력 기본값을 균형점으로 바꾼다."""
    text = DELAM.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        f'id="knifeSpeed" type="number" min="20" max="60" step="1" value="{handoff.KNIFE_SPEED_MM_S:g}"',
        f'id="knifeSpeed" type="number" min="20" max="60" step="1" value="{handoff.PLAN_B_KNIFE_MM_S:g}"',
        "B안 칼날 속도")
    text = _replace_once(
        text,
        f'id="handlingTime" type="number" min="5" max="25" step="1" value="{handoff.HANDLING_S:g}"',
        f'id="handlingTime" type="number" min="5" max="25" step="1" value="{handoff.PLAN_B_HANDLING_S:g}"',
        "B안 인계시간")
    delam = out / "DI_Sol_Rec_B안_박리라인.html"
    delam.write_text(text, encoding="utf-8")
    plant = out / "DI_Sol_Rec_B안_전처리.html"
    shutil.copyfile(PLANT, plant)          # 전처리는 B안에서 바뀌지 않는다
    return [plant, delam]


def build_plan_c(out: pathlib.Path) -> list[pathlib.Path]:
    """전처리 캠페인을 방출 보류를 넣어 다시 만든다."""
    hold = handoff.plan_c_hold_s()
    base, held = campaign.summary(), campaign.summary(hold)
    text = PLANT.read_text(encoding="utf-8")

    text = _replace_once(text,
                         "var pvCamT=" + _schedule_literal(campaign.panels()),
                         "var pvCamT=" + _schedule_literal(campaign.panels(hold)),
                         "C안 캠페인 스케줄")
    # 도면의 pvCamTakt·pvCamWrap 은 둘 다 방출 주기다 — 재생 주기와 계산이
    # 어긋나면 공정시계가 스케줄과 따로 논다.
    for name in ("pvCamTakt", "pvCamWrap"):
        text = _replace_once(text,
                             f"{name}={campaign.release_takt_s():g}",
                             f"{name}={campaign.release_takt_s(hold):g}",
                             f"C안 {name}")

    plant = out / "DI_Sol_Rec_C안_전처리.html"
    plant.write_text(text, encoding="utf-8")
    delam = out / "DI_Sol_Rec_C안_박리라인.html"
    shutil.copyfile(DELAM, delam)          # 박리 라인은 C안에서 바뀌지 않는다
    return [plant, delam]


def _schedule_literal(rows) -> str:
    """도면의 pvCamT 와 같은 모양 — 셀별 점유 구간 6개씩."""
    return "[" + ",".join(
        "[%g,%g,%g,%g,%g,%g]" % (p.infeed_start, p.infeed_end, p.jbr_start,
                                 p.jbr_end, p.afr_start, p.afr_end)
        for p in rows) + "]"


def main() -> None:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    out.mkdir(parents=True, exist_ok=True)
    for plan, files in (("B", build_plan_b(out)), ("C", build_plan_c(out))):
        for f in files:
            print(f"{plan}안  {f.name:34} {f.stat().st_size/1024:8.0f} KB")
    b, c = handoff.plans()
    print(f"\nB안 {b.lever} → 유입 {b.feed_per_h} · 처리 {b.capacity_per_h} 장/h (여유 {b.margin_per_h:+})")
    print(f"C안 {c.lever} → 유입 {c.feed_per_h} · 처리 {c.capacity_per_h} 장/h (여유 {c.margin_per_h:+})")


if __name__ == "__main__":
    main()
