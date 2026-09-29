# -*- coding: utf-8 -*-
"""통합 설계도(3D 영상 콘솔)에서 **GBR-301 레시피 버퍼만 남긴** 파생본을 만든다.

투입 파생본(`tools/build_infeed_scene.py`)이 라인 앞머리를, JBR 파생본
(`tools/build_jbr_scene.py`)이 그 다음 셀을, AFR 파생본(`tools/build_afr_scene.py`)이
프레임 제거셀을 떼어 냈다면, 이것은 **라인의 마지막 셀**을 떼어 낸다. GI-301/302 가
레시피를 판정해 넘긴 무프레임 유리를 수평셔틀 데크가 받아, 데크 롤러가 목표 행
(R-A · HOLD · R-B)으로 횡분기하고, 그 행의 트윈마스트가 콤포크를 슬롯 높이로 올려
캐리지 안에 밀어 넣는 것을 처음부터 끝까지 보는 화면이다.

발주처 요청 셋을 이 파생본에서도 그대로 반영한다 — **그림자·외장 케이싱·천장크레인을
뺀다.** 셋 다 GBR-301 의 부재가 아니라 화면을 덮는 것들이다. 바닥 그림자는 캐리지
밑과 마스트 사이를 어둡게 덮고, 외장 케이싱은 껍질로 셔틀과 적재기를 가리며,
CRN-901 천장크레인은 이 셀 위를 가로지르는 **건물 측** 부재다 (설치·정비 인양용이라
운전 중에는 급전조차 차단된다).

* **장면** — buffer 셀만 남긴다. 셔틀 데크·Z 분기 롤러·ML-811 트윈마스트·TF-810
  콤포크·TG-813 선단받이·A/B/HOLD 캐리지·BS-801 센서팩이 전부 `ft` 아래에 있어 셀
  귀속이 buffer 이므로 자동으로 남는다. afu·robot·jbr·afr·post·grm 셀과 셀에 매이지
  않는 시설·주행로·주관은 끈다. 형상을 지우지 않고 `visible=false` 로 끈다 — 원본
  3D 는 손대지 않는다.
* **시계** — 이 셀의 일은 원본 필름의 마지막 구간이다. AFR 이후 단계(`_l`)의 끝
  칸이 `Cr`(28.73 s)에서 `Lr`(39.03 s)까지 10.3 s 인데, 그 안에서 유리가 GI 를 떠나
  데크에 오르는 것이 진도 0.88 이다 — GA 시트 `PV-GBR-301-GA-5201` 의 흐름 1 번
  「GI-302 인계·데크 진입」이 그 자리다. 그래서 창을 [그 시각, 필름의 끝] 으로 낸다.
  **창이 1.23 s 로 짧다.** 원본 필름이 후단 10.3 s 를 연마·이송·검사·적재에 나눠
  주면서 적재에 12 % 를 준 결과이고, 여기서 늘리면 그것은 다른 영상이 된다. 대신
  재생 배속 기본값을 0.25× 로 낮춰 창을 천천히 연다 — 콘솔이 이미 갖고 있는 배속이다.
* **시점** — 이 셀을 보는 시점이 원본에는 `afrbuffer` 하나뿐이고, 그것도 AFR 에서
  버퍼까지 함께 보는 거리다. 셀 하나를 보는 화면이므로 **전체·적재부·캐리지** 셋을
  새로 세우고 상부·초기화만 남긴다.
* **화면** — 흐름표는 GBR-301 한 칸, 도면 모듈은 버퍼 한 장. 상류 전용 조작(상부
  비전 판정·리프트 운전·정션박스 검출·JBR 검증·반입 구조 레시피)은 숨기고, **이
  셀에서 결과가 갈리는 조작**(레시피 시나리오 — 목표 캐리지가 R-A/R-B1/R-B2/HOLD
  중 어디가 되는지, 그리고 만재 HOLD)은 남겨 앞으로 낸다.
* **배치도** — 원본의 초점(`focusBox`)은 **뷰박스만** 옮기므로 존 밖 장비가 SVG 에
  그대로 남아 축소하면 플랜트 50 m 가 다 나온다. `renderLayout` 안에서만 존을
  buffer 하나로 가려 **이 셀 장비만** 그리고, 전체 X·Y 치수도 셀 값으로 바꾸며,
  패널 맨 위에 **장비 전체 스펙(가로·세로·높이)** 을 세운다. 값은 배치 모델의 존
  폭에서 내고 GA 시트의 `envelope` 과 맞는지 확인한다 — 갈라지면 멈춘다.
* **부품 목록** — 이 셀 부품은 카탈로그에서 품번이 아니라 **분류**로 묶여 있다
  (`레시피 버퍼` 9 품목, 품번은 AFR- 접두어를 쓴다). 그래서 검색이 분류 제목도
  보게 하고 검색창을 그 분류로 채운다. 목록 자체는 줄이지 않는다.

원본 파일을 **문자열로 고친다.** 앵커가 정확히 한 곳이어야 하고 아니면 멈춘다 —
원본이 바뀌어 앵커가 사라지면 파생본이 조용히 옛 모습으로 남는 대신 생성이
실패한다. 값(시각 창, 셀 외형)은 캠페인·배치 모델과 원본 필름에서 온다.

    PYTHONPATH=src python tools/build_gbr_scene.py

멱등이다. `tests/test_pv_gbr.py` 가 커밋된 파일과 생성 결과를 견준다.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import campaign, layout  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANT = ROOT / "docs/drawings/pv-preprocess-plant.html"
OUT = ROOT / "docs/drawings/pv-gbr-scene.html"

#: 3D 원점 — build_literals.SCENE_ORIGIN_X_MM 과 같은 규약 (world x = (plant x − 원점)/1000).
SCENE_ORIGIN_X_MM = 24_750

#: 이 파생본이 다루는 셀.
CELL = "buffer"

#: 후단 마지막 칸 안에서 이 셀이 유리를 받는 진도. 원본 애니메이션이 `v` 로 쓰는 값이고,
#: `v>=.88` 에서 유리가 GI(`Do`)를 떠나 셔틀 데크(`Ri`)로 옮겨진다. GA 시트
#: `PV-GBR-301-GA-5201` 의 흐름 1 번 「GI-302 인계·데크 진입」이 이 자리다.
#: 그 앞(`v` .80….88)은 GI-301/302 검사 — 적재 허가를 내주는 **후단 셀**의 일이다.
HANDOVER_V = 0.88

#: 재생 배속 — 창이 1.23 s 라 원본 기본값 0.5× 로는 한 번에 지나간다.
SPEED = "0.25"

#: 남기는 시점 버튼. 앞의 셋은 이 파생본이 새로 세우는 버퍼 시점이고, `top`·`reset` 은
#: 어느 화면에나 있는 일반 시점이다. 자동추적이 고르는 시점이 모두 이 안에 있어야 한다.
KEEP_VIEWS: tuple[str, ...] = ("gbr", "gbrdock", "gbrcar", "top", "reset")

#: 새로 세우는 시점. 좌표는 `qt`(AFR 셀 원점) 상대다 — 버퍼 형상이 `ot` 아래에 있어
#: 원본이 이 셀 좌표를 전부 그렇게 쓴다.
#:
#: 셋 다 **셀을 앞(+z)이나 뒤(−z) 어느 쪽에서 보느냐**로 갈린다. 전체와 적재부는
#: +z 에서 본다 — 그쪽에서 보면 유리가 데크(왼쪽)에서 캐리지(오른쪽)로 가는 순서가
#: 화면에서도 왼→오른쪽이고, GBR-301 명판이 정면에 선다. 캐리지는 −z 에서 본다 —
#: 필름의 기본 경로 R-A 가 z −2,100 행이라 그쪽에서 봐야 유리가 들어가는 칸이 앞이다.
VIEWS_OLD = "afrbuffer:{position:new C(qt+13.9,7.2,-9.5),target:new C(qt+10.3,1.35,.2)},top:"
VIEWS_NEW = ("gbr:{position:new C(qt+6.2,5.4,7.6),target:new C(qt+11.2,1.2,0)},"
             "gbrdock:{position:new C(qt+6.7,3.2,5.2),target:new C(qt+10.3,1.2,-.6)},"
             "gbrcar:{position:new C(qt+16.5,3.4,-6.6),target:new C(qt+13.1,1.2,-1)},top:")

#: 시점이 겨누는 자리가 배치 모델에서 얼마나 벗어나도 되는가 (m). 화면 구도 때문에
#: 조금씩 밀지만, 존이 움직이면 시점도 따라 움직여야 하므로 벌어지면 멈춘다.
VIEW_TOLERANCE_M = 0.6

#: 자동추적이 AFR 이후 6 단계에 배정하는 시점. 창이 마지막 칸 안에 있으므로 실제로
#: 고르는 것은 끝의 하나뿐이지만, 스크럽이 창 안에 갇혀 있어도 목록 전체가 이 셀을
#: 보게 둔다 — 꺼진 셀을 비추는 자리를 남기지 않는다.
AUTO_VIEWS_OLD = '["afr","afr","afrshort","afrshort","afrlong","afrpost"]'
AUTO_VIEWS_NEW = '["gbr","gbr","gbr","gbr","gbr","gbr"]'
AUTO_VIEWS: tuple[str, ...] = ("gbr",) * 6

#: 도면 모듈에서 지우는 것 — 버퍼만 남긴다.
DROP_STATIONS: tuple[str, ...] = ("afu", "bfc", "robot", "jbr", "afr", "post")

#: 흐름표에서 남기는 칸 (1부터 센다) — GBR-301 · BUFFER 한 칸.
FLOW_FIRST, FLOW_LAST = 11, 11

#: 도면 팝업에서 숨기는 탭 — 합계가 플랜트 값이라 이 셀로 좁힐 수 없는 계통 자료다.
PLANT_TABS: tuple[str, ...] = ("electrical", "smart", "safety", "ops")

#: 「설계·PLC·검증」 안의 플랜트 계통 절 — 서보 38축·플랜트 소음·플랜트 열수지다.
PLANT_SECTIONS: tuple[str, ...] = ("jb-servo-axes", "jb-noise-vibration", "jb-thermal")

#: 숨기는 상류 전용 조작. 상부 비전 판정·리프트 운전은 투입셀 것이고, 정션박스 검출과
#: 안전·품질 검증 시나리오는 JBR 것이다 (리젝트가 나면 유리가 아예 이 셀에 오지 않아
#: 창 안이 빈다). 반입 구조 레시피도 상류다 — `bifacial`·`unregistered` 는 투입에서
#: 걸러지고 `frameless` 는 AFR 인발만 건너뛰므로 이 셀의 결과를 바꾸지 않는다.
#: 배치 초점도 여기 든다 — 배치도에 이 셀만 그리므로 다른 초점은 빈 자리를 확대한다.
HIDDEN_CONTROLS: tuple[str, ...] = ("pv-face-in", "pv-lift-mode", "jb-box-mode",
                                    "jb-validation-mode", "pv-panel-structure",
                                    "pv-layout-focus")

#: 꺼진 셀에 속하는 셀 키.
OFF_CELLS: tuple[str, ...] = ("afu", "robot", "jbr", "afr", "post", "grm")

#: **공정 중인 물건**이 들어와도 되는 상류 여유 (m). 이 셀 하드웨어는 존 시작
#: (셔틀 데크 상류면)에서 시작하지만, 유리는 GI 검사대(존 시작에서 상류로 1.675)에서
#: 출발해 데크로 건너온다. 인계를 처음부터 보려면 그 출발점이 창 안에 들어야 한다.
UPSTREAM_MARGIN_M = 1.9
#: 하류 여유 (m) — 유리는 존 안에서 멈춘다. 경계 판정 여유만 준다.
DOWNSTREAM_MARGIN_M = 0.4

#: **설비**가 서도 되는 여유 (m). 물건과 달리 셀에 매이지 않은 설비는 존 밖에 있으면
#: 남의 것이다 — 상류 여유를 물건과 같이 주면 후단 셀의 EC-POS 엣지 캐비닛과 주관이
#: 이 화면에 남는다. 경계 판정과 접합부 절반(125)만 덮는 값으로 따로 잡는다.
FIXTURE_MARGIN_M = 0.4

#: 부품 카탈로그에서 이 셀 품목이 묶여 있는 분류.
PARTS_GROUP = "레시피 버퍼"


def _once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"✗ {what}: 앵커가 {n}곳 — 1곳이어야 한다\n  {old[:90]}")
    return text.replace(old, new)


def _split_select(text: str, select_id: str) -> tuple[str, str, str]:
    """`id` 로 지목한 `<select>` 하나를 앞·본문·뒤로 가른다."""
    opens = [m for m in re.finditer(rf'<select[^>]*id="{select_id}"[^>]*>', text)]
    if len(opens) != 1:
        raise SystemExit(f"✗ select#{select_id}: {len(opens)}곳 — 1곳이어야 한다")
    start = opens[0].end()
    end = text.index("</select>", start)
    return text[:start], text[start:end], text[end:]


def film(plant: str) -> tuple[float, float]:
    """원본 필름의 마지막 칸 — (시작 시각 `nt+Cr`, 칸 길이) (s).

    두 값 다 **원본에서 읽는다.** 여기 28.73·10.3 이라고 적어 두면 후단 시각표가
    바뀌는 날 파생본만 옛 자리를 가리키고, 그런데도 화면은 멀쩡해 보인다.
    """
    m = re.search(r"Cr=([0-9.]+),pl=Wr", plant)
    if not m:
        raise SystemExit("✗ 원본에서 후단 마지막 칸의 시작(Cr)을 못 읽었다")
    span = re.search(r"\$t\(\(l-Cr\)/([0-9.]+)\)", plant)
    if not span:
        raise SystemExit("✗ 원본에서 후단 마지막 칸의 길이를 못 읽었다")
    return campaign.INFEED_S + campaign.JBR_S + float(m.group(1)), float(span.group(1))


def window(plant: str) -> tuple[float, float]:
    """GBR-301 이 유리를 쥐고 있는 시각 창 (s).

    끝은 필름의 끝이다 — 이 셀이 유리를 슬롯에 놓는 순간이 곧 영상의 끝이라 자를
    것이 없다. 시작은 후단 마지막 칸의 진도 `HANDOVER_V` 이고, 그 진도는 원본
    애니메이션이 유리를 GI 에서 데크로 옮기기 시작하는 자리다.
    """
    start, span = film(plant)
    return round(start + HANDOVER_V * span, 2), campaign.total_dwell_s()


def zone_world_x() -> tuple[float, float]:
    """buffer 존의 world x 범위 (m)."""
    zone = next(z for z in layout.build_zones() if z.key == CELL)
    return ((zone.x0_mm - SCENE_ORIGIN_X_MM) / 1000.0,
            (zone.x1_mm - SCENE_ORIGIN_X_MM) / 1000.0)


def cell_envelope(plant: str) -> tuple[int, int, int]:
    """GBR-301 셀의 가로 × 세로 × 높이 (mm).

    배치 모델의 존 폭에서 내고, 통합 설계도 GA 시트가 적어 둔 `envelope` 과
    맞는지 확인한다. 두 곳이 갈라지면 어느 쪽이 맞는지 화면이 알 수 없으므로
    여기서 멈춘다 — 조용히 한쪽을 고르지 않는다.
    """
    zone = next(z for z in layout.build_zones() if z.key == CELL)
    got = (zone.x1_mm - zone.x0_mm, zone.y1_mm - zone.y0_mm, zone.height_mm)
    m = re.search(rf"{CELL}: \{{.*?envelope: \[(\d+), (\d+), (\d+)\]", plant, re.S)
    if not m:
        raise SystemExit(f"✗ GA 시트에서 {CELL} 의 envelope 을 못 읽었다")
    want = tuple(int(v) for v in m.groups())
    if tuple(int(v) for v in got) != want:
        raise SystemExit(f"✗ 셀 외형이 갈렸다 — 배치 모델 {got} vs GA 시트 {want}")
    return want


def view_anchors() -> dict[str, float]:
    """새 시점이 겨누어야 할 자리 — `qt` 상대 x (m).

    `qt` 는 AFR 셀 원점이고 원본이 `pvZone.afr[0]+2.45-.4` 로 정의한다. 버퍼 형상이
    전부 그 상대 좌표로 서 있으므로 시점도 같은 기준에서 낸다 — 존이 움직이면
    시점도 같이 움직여야 하기 때문이다.
    """
    zones = {z.key: z for z in layout.build_zones()}
    qt = (zones["afr"].x0_mm - SCENE_ORIGIN_X_MM) / 1000.0 + 2.45 - 0.4
    low, high = zone_world_x()
    deck, gap, car, pitch = 3.2, 0.225, 2.75, 2.9      # 원본 bDeck·bGap·bCar·bPitch
    return {
        # 셀 한가운데
        "gbr": round((low + high) / 2 - qt, 3),
        # 데크–도크 틈에 선 ML-811 마스트
        "gbrdock": round(low + deck + gap / 2 - qt, 3),
        # 도크 캐리지와 스테이지 캐리지 사이
        "gbrcar": round(low + deck + gap + car / 2 + pitch / 2 - qt, 3),
    }


def view_targets() -> dict[str, float]:
    """`VIEWS_NEW` 리터럴이 실제로 겨누는 `qt` 상대 x (m) — 글자에서 되읽는다."""
    return {name: float(x) for name, x in re.findall(
        r"(\w+):\{position:new C\([^)]*\),target:new C\(qt\+([0-9.]+),", VIEWS_NEW)}


def check_views() -> None:
    """시점이 겨누는 자리가 배치 모델에서 온 값인지 — 벌어지면 멈춘다."""
    want, got = view_anchors(), view_targets()
    if set(got) != set(want):
        raise SystemExit(f"✗ 시점 목록이 갈렸다 — 리터럴 {sorted(got)} vs 모델 {sorted(want)}")
    off = {k: (got[k], want[k]) for k in want if abs(got[k] - want[k]) > VIEW_TOLERANCE_M}
    if off:
        raise SystemExit(f"✗ 시점이 겨누는 자리가 배치 모델과 갈렸다 — {off}")


def spec_block(plant: str) -> str:
    """배치도 패널 맨 위에 세우는 「장비 전체 스펙」 — 가로·세로·높이."""
    L, W, H = cell_envelope(plant)
    zone = next(z for z in layout.build_zones() if z.key == CELL)
    rows = (
        ("가로 (X · 공정방향)", L, f"존 {zone.x0_mm:,} → {zone.x1_mm:,} mm · "
                                  "셔틀 데크 3,200 + 순틈 225 + 캐리지 2 열 피치 2,900"),
        ("세로 (Y · 진행방향 좌측)", W,
         f"존 {zone.y0_mm:,} → {zone.y1_mm:,} mm · R-A(−2,100) · HOLD(0) · R-B(+2,100) 3 행"),
        ("높이 (Z · FFL 상향)", H,
         "이송면·데크 H=950 · SLOT-1 340 · SLOT-25 2,236 · 캐리어 2,450 · 가드 2,800"),
    )
    body = "".join(
        f"<tr><td>{label}</td><td>{value:,} mm</td><td>{note}</td></tr>"
        for label, value, note in rows)
    return (
        '      <div class="pv-gbr-spec">\n'
        '        <h4 class="text-small" style="margin:0 0 6px">장비 전체 스펙 '
        f'<span class="viz-badge">{L:,} × {W:,} × {H:,} mm</span></h4>\n'
        '        <div class="table-responsive"><table class="table table-sm">\n'
        "          <thead><tr><th>항목</th><th>값</th><th>기준</th></tr></thead>\n"
        f"          <tbody>{body}</tbody>\n"
        "        </table></div>\n"
        '        <p class="text-small text-muted">셀 외형 포락선이다. 아래 배치도는 '
        "이 파생본에서 <b>GBR-301 셀 장비만</b> 그린다 — 상류 존(AFR·후단 검사)은 "
        "통합 설계도에 그대로 있고 여기서만 뺐다.</p>\n"
        "      </div>\n")


def scene_script(low: float, high: float, t0: float, t1: float) -> str:
    """장면을 좁히는 모듈 — 원본 모듈이 `window.__pvScene` 으로 내놓은 장면을 쓴다."""
    cells = ", ".join(f"'{c}'" for c in OFF_CELLS)
    return f"""<script type="module">
/* GBR-301 파생본 — tools/build_gbr_scene.py 가 붙인다. 원본 3D 형상은 그대로 두고
   보이기만 끈다. 남기는 것은 셀 귀속이 'buffer' 인 것 전부다 — 셔틀 데크와 Z 분기
   롤러, ML-811 트윈마스트, TF-810 콤포크, TG-813 선단받이, A/B/HOLD 캐리지, BS-801
   센서팩이 모두 `ft` 아래에 있어 여기에 든다. 발주 요청으로 외장 케이싱(pvCase)과
   CRN-901 천장크레인(pvCrn)은 이름으로 찾아 끈다 — 둘 다 셀에 매이지 않는 `pvSpans`
   묶음이라 위치 판정만으로는 셀 위를 지나는 조각이 남는다. 그림자는 렌더러
   섀도맵에서 이미 껐다. */
(function () {{
  const root = document.getElementById('jb-removal-operation');
  const S = (root && root.__pvScene) || window.__pvScene; if (!S) return;
  const LOW = {low:g};    // world m — buffer 존 상류 끝. 셔틀 데크 상류면이 여기에 붙는다
  const HIGH = {high:g};  // world m — buffer 존 하류 끝. 가드가 여기서 GRM 셀과 갈린다
  /* 문턱이 둘이다. 공정 중인 물건(transit)은 상류에서 **들어오는** 것이라 넉넉히
     받아 GI 인계부터 보이게 하고, 셀에 매이지 않은 설비는 존 밖이면 남의 것이라
     좁게 자른다 — 한 값으로 묶으면 후단 셀의 엣지 캐비닛이 이 화면에 남는다. */
  const IN = LOW - {UPSTREAM_MARGIN_M:g}, OUT = HIGH + {DOWNSTREAM_MARGIN_M:g};
  const FIT_IN = LOW - {FIXTURE_MARGIN_M:g}, FIT_OUT = HIGH + {FIXTURE_MARGIN_M:g};
  const OFF = new Set([{cells}]);
  const v = new S.Vector3();
  function cellOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.cell) return p.userData.cell; }} return null; }}
  function transitOf(o) {{ for (let p = o; p; p = p.parent) {{ if (p.userData && p.userData.transit) return p; }} return null; }}
  /* 껍질과 크레인은 묶음째 끈다 — 위치로 거르면 이 셀 위에 걸친 조각이 남는다. */
  const shells = ['pvCase', 'pvCrn'].map(function (n) {{ return S.scene.getObjectByName(n); }})
    .filter(Boolean);
  const transit = new Set(), hidden = [], seen = new WeakSet();
  function classify(o) {{
    if (!o.isMesh && !o.isSprite && !o.isLine) return;
    if (seen.has(o)) return; seen.add(o);
    const tr = transitOf(o); if (tr) {{ transit.add(tr); return; }}
    const cell = cellOf(o);
    if (cell === '{CELL}') return;
    if (OFF.has(cell)) {{ hidden.push(o); return; }}
    o.getWorldPosition(v);
    let minX = v.x, maxX = v.x;
    if (o.geometry) {{
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      const bb = o.geometry.boundingBox, sx = Math.abs(o.matrixWorld.elements[0]) || 1;
      minX = v.x + bb.min.x * sx; maxX = v.x + bb.max.x * sx;
    }}
    // 라인 전장을 지나는 부재 중 바닥면만 남긴다 — 60 m 바닥 격자는 이 셀 밑에도 있지만
    // 크레인 주행로·공압 주관처럼 양쪽으로 20 m 씩 뻗는 건물 측 부재는 이 셀 밖이다.
    const floor = o.geometry && o.geometry.type === 'PlaneGeometry';
    const spans = minX < FIT_IN && maxX > FIT_OUT;
    if (spans ? !floor : (v.x < FIT_IN || v.x > FIT_OUT)) hidden.push(o);
  }}
  // 원본은 일부 부품을 나중에 만들고(레시피·구조 선택) 자기 단계에서 visible 을 매 프레임
  // 다시 켠다 — 그래서 주기적으로 다시 훑고 매 프레임 끈다.
  let frame = 0;
  function scan() {{ S.scene.updateMatrixWorld(true); S.scene.traverse(classify); }}
  function tick() {{
    if (frame++ % 30 === 0) scan();
    for (const o of hidden) o.visible = false;
    for (const s of shells) s.visible = false;
    for (const tr of transit) {{ tr.getWorldPosition(v); if (v.x < IN || v.x > OUT) tr.visible = false; }}
    requestAnimationFrame(tick);
  }}
  tick();
  window.__pvGbrScene = {{ low: LOW, high: HIGH, from: {t0:g}, to: {t1:g},
    get hidden() {{ return hidden.length; }}, get transit() {{ return transit.size; }},
    get shells() {{ return shells.length; }} }};
}})();
</script>
"""


def build() -> str:
    text = PLANT.read_text(encoding="utf-8")
    t0, t1 = window(text)
    low, high = zone_world_x()
    L, W, H = cell_envelope(text)
    check_views()
    _, span = film(text)
    hold_s = round(t1 - t0, 2)

    t = text
    # ── 표제·표식 ────────────────────────────────────────────────────────────
    # 이 제목이 그대로 아티팩트 이름이 된다 (tools/build_artifact.py).
    t = _once(t, "<title>태양광 전처리 통합 플랜트</title>",
              "<title>GBR-301 R-A/R-B/HOLD 레시피 버퍼</title>\n"
              '<meta name="description" content="폐 태양광 패널 전처리 라인의 GBR-301 '
              '레시피 버퍼 셀만 남긴 3D 운전 콘솔 — GI-301/302 가 판정해 넘긴 무프레임 '
              '유리를 수평셔틀 데크가 받아 R-A·HOLD·R-B 행으로 횡분기하고, 트윈마스트가 '
              '콤포크를 슬롯 높이로 올려 캐리지에 밀어 넣는 것을 플랜트 '
              f'{t0:g}–{t1:g} s 창에서 반복 재생한다. 그림자·외장 케이싱·천장크레인은 뺐다.">',
              "제목")
    t = _once(t, f'<span class="viz-badge">{campaign.total_dwell_s():g} s TRACE</span>',
              f'<span class="viz-badge">{hold_s:g} s TRACE · GBR-301</span>', "배지")
    t = _once(t, '<h2 id="pv-v22-title">태양광 패널 전처리 통합 플랜트</h2>',
              '<h2 id="pv-v22-title">GBR-301 레시피 버퍼 '
              f'(GI-302 인계 {t0:g} s → 슬롯 적재 {t1:g} s)</h2>', "표제")
    rev = re.search(r"DRAWING_REVISION = '([^']+)'", t).group(1)
    t = _once(t, "DYNAMIC INDUSTRY · REV.22 VIDEO-FIRST · ENGINEERING BASE REV.22",
              f"DYNAMIC INDUSTRY · GBR-301 단독 파생본 · ENGINEERING BASE {rev}", "머리글")
    t = _once(t, '<div class="text-small"><code>Rev.22 · 비전 2헤드·듀얼 반전카세트·JBR·AFR 통합 시뮬레이션</code></div>',
              f'<div class="text-small"><code>{rev} · GBR-301 — 수평셔틀 데크·Z 분기 롤러·'
              'ML-811 트윈마스트·TF-810 콤포크·R-A/R-B/HOLD 캐리지</code></div>', "상태 칩")

    t = _once(t, '<div class="card jb-detail" id="jb-detail" aria-live="polite">세 벽체 사이의 '
              'BFC-101A/B가 고정 픽업면의 한 장을 상승·반전하고, 650 mm 고상 로봇이 반전 완료품을 '
              '직접 픽업합니다. 적재부·반전기·로봇 사이에는 컨베이어가 없습니다.</div>',
              '<div class="card jb-detail" id="jb-detail" aria-live="polite">GI-301/302 가 '
              '레시피를 판정해 넘긴 무프레임 유리를 수평셔틀 데크가 나이프 간극 30 mm 를 '
              '건너 받고, 데크 롤러가 목표 행(R-A −2,100 · HOLD 0 · R-B +2,100)으로 '
              '횡분기합니다. 그 행의 ML-811 트윈마스트가 TF-810 콤포크를 슬롯 높이'
              '(340…2,236, 25 단)로 올린 뒤 X 로 3,200 신장해 캐리지 안에 넣고, 12 mm '
              '소하강으로 레일에 얹은 다음 복귀합니다. 목표 캐리지가 만재이면 유리를 '
              '데크에 쥔 채 상류를 HOLD 합니다. 형상을 클릭하면 그 부품의 품번과 역할이 '
              '여기에 나옵니다.</div>', "기본 설명문")

    # ── 단계 이름 ────────────────────────────────────────────────────────────
    # 창이 놓인 칸은 원본에서 「AFR-101 · 정반 상승·톱니 컨베이어 40 mm 상승 반출→
    # SG-301→GI-301/302→GBR-301」이다. 그 칸 전체는 정말로 그 사슬을 다 덮지만,
    # **이 창(진도 0.88…1.0)에서 화면에 있는 것은 GBR-301 뿐**이라 그대로 두면
    # 안 보이는 설비의 이름이 현재 단계로 서 있게 된다. 칸 이름을 이 창의 일로
    # 바꾸고, 셀 접두어도 그 칸에서만 뗀다 — 나머지 다섯 칸은 AFR 것이라 그대로 둔다.
    t = _once(t, "정반 상승·톱니 컨베이어 40 mm 상승 반출→SG-301→GI-301/302→GBR-301",
              "GBR-301 데크 인계 → Z 분기 → 콤포크 승강·슬롯 적재 "
              "(창 앞은 SG-301 연마·GI 검사)", "후단 마지막 칸 이름")
    t = _once(t, "name:`AFR-101 · ${i.name}`",
              'name:i.name.indexOf("GBR-301")===0?i.name:`AFR-101 · ${i.name}`',
              "단계 목록 접두어")
    t = _once(t, "`AFR-101 · ${u.phase.name}`",
              '(u.phase.name.indexOf("GBR-301")===0?u.phase.name:`AFR-101 · ${u.phase.name}`)',
              "현재 단계 접두어")

    # ── 시계: [t0, t1] 창 ────────────────────────────────────────────────────
    # 창의 **끝**은 원본 필름의 끝(`ci=nt+Lr`)이다 — 이 셀이 유리를 슬롯에 놓는
    # 순간이 곧 영상의 끝이라 자를 것이 없다. 시작만 셀 진입 시각으로 올린다.
    t = _once(t, f'<div class="text-small tabular-nums" id="jb-time">0.00 / {campaign.total_dwell_s():g} s</div>',
              f'<div class="text-small tabular-nums" id="jb-time">{t0:.2f} / {t1:.2f} s</div>', "시계 표시")
    t = _once(t, '<span class="tabular-nums" id="jb-scrub-value">0.0 s</span>',
              f'<span class="tabular-nums" id="jb-scrub-value">{t0:.1f} s</span>', "스크럽 표시")
    t = _once(t, f'id="jb-scrub" type="range" min="0" max="{campaign.total_dwell_s():g}" step="0.05" value="0"',
              # 창이 1.23 s 라 0.05 눈금은 24 칸뿐이다 — 한 칸이 5 % 다. 0.01 로 잘게 썬다.
              f'id="jb-scrub" type="range" min="{t0:g}" max="{t1:g}" step="0.01" value="{t0:g}"', "스크럽")
    t = _once(t, ",Ve=0,ai=0", f",Ve={t0:g},ai=0", "시작 시각")
    t = _once(t, "Ve%=ci", f"Ve={t0:g}+(Ve-{t0:g})%(ci-{t0:g})", "반복 구간")
    t = _once(t, "Ve=s?ci:0", f"Ve=s?ci:{t0:g}", "만재 복귀 시각")
    t = _once(t, "let pe=Math.round(i/ci*100)",
              f"let pe=Math.round((i-{t0:g})/(ci-{t0:g})*100)", "진행률")
    t = _once(t, "Ve=i>0?Fs[i-1].start+.02:0",
              f"Ve=Math.max({t0:g},i>0?Fs[i-1].start+.02:{t0:g})", "이전 단계 클램프")
    t = _once(t, "Ve=i<Fs.length-1?Fs[i+1].start+.02:ci",
              "Ve=Math.min(ci,i<Fs.length-1?Fs[i+1].start+.02:ci)", "다음 단계 클램프")
    # 조작을 바꾸면 원본은 시계를 0 으로 되감는다 (검출 시나리오·검증 시나리오·구조
    # 레시피·리프트·버퍼 레시피·캠페인 장 선택). 여기서 0 은 창 밖이라 화면이 빈 셀을
    # 비추게 되므로 창의 시작으로 되감는다.
    rewinds = len(re.findall(r"\bVe=0\b", t))
    if rewinds != 6:
        raise SystemExit(f"✗ 시계 되감기: {rewinds}곳 — 6곳이어야 한다")
    t = re.sub(r"\bVe=0\b", f"Ve={t0:g}", t)
    # 배속 — 창이 짧아 0.5× 로는 한 번에 지나간다. 기본값만 낮춘다 (목록은 그대로).
    t = _once(t, "b0=.5,", f"b0={SPEED.lstrip('0')},", "기본 배속 변수")
    t = _once(t, '<option value="0.5" selected>0.5×</option>',
              '<option value="0.5">0.5×</option>', "배속 기본값 해제")
    t = _once(t, f'<option value="{SPEED}">{SPEED}×</option>',
              f'<option value="{SPEED}" selected>{SPEED}×</option>', "배속 기본값")

    # ── 시점 ────────────────────────────────────────────────────────────────
    t = _once(t, ',xl="line"', ',xl="gbr"', "기본 시점")
    t = _once(t, 'xl=i==="reset"?"line":i', 'xl=i==="reset"?"gbr":i', "초기화 시점")
    t = _once(t, 'let t=i==="reset"?fp.line:fp[i];', 'let t=i==="reset"?fp.gbr:fp[i];', "초기화 카메라")
    # 원본의 버퍼 시점(`afrbuffer`)은 AFR 에서 버퍼까지 함께 보는 거리라 셀 하나만
    # 남으면 화면에서 작다. 그 자리에 이 셀 시점 셋을 세운다 — 전체(셀 중심),
    # 적재부(데크–도크 틈의 마스트·콤포크), 캐리지(도크·스테이지 두 열).
    t = _once(t, VIEWS_OLD, VIEWS_NEW, "버퍼 시점 셋")
    t = _once(t, AUTO_VIEWS_OLD, AUTO_VIEWS_NEW, "자동추적 시점")
    # 버튼도 셋으로 바꾼다 — 아래 걸러내기가 KEEP_VIEWS 밖의 버튼을 지운다.
    t = _once(t, '<button class="btn" data-jb-view="afrbuffer" type="button">GBR 레시피 버퍼</button>',
              '<button class="btn btn-primary" data-jb-view="gbr" type="button">GBR-301 전체</button>\n'
              '    <button class="btn" data-jb-view="gbrdock" type="button">적재부 (마스트·콤포크)</button>\n'
              '    <button class="btn" data-jb-view="gbrcar" type="button">R-A/R-B/HOLD 캐리지</button>',
              "버퍼 시점 버튼")
    # 콘솔 상단 카메라 바는 통합 화면용 목록이라 이 파생본에는 남는 버튼이 넷뿐이다.
    t = _once(t, "['line', 'turner', 'tool', 'afr', 'afrbuffer', '#jb-pan-toggle', 'reset']",
              "['gbr', 'gbrdock', 'gbrcar', 'top', '#jb-pan-toggle', 'reset']",
              "카메라 바 목록")
    button = r'\s*<button class="btn(?: btn-primary)?" data-jb-view="([a-z]+)" type="button">[^<]*</button>'
    t = re.sub(button, lambda m: m.group(0) if m.group(1) in KEEP_VIEWS else "", t)
    left = re.findall(button, t)
    if sorted(left) != sorted(KEEP_VIEWS):
        raise SystemExit(f"✗ 시점 버튼: 남은 것이 {left} — KEEP_VIEWS 와 다르다")
    missing = [v for v in AUTO_VIEWS if v not in KEEP_VIEWS]
    if missing:
        raise SystemExit(f"✗ 자동추적이 고르는 시점 {missing} 이 버튼에 없다")

    # ── 도면·배치도 ─────────────────────────────────────────────────────────
    # `afr`·`post` 같은 값은 배치도 초점 select 에도 있다 — 도면 모듈 select 안에서만 지운다.
    head, select, tail = _split_select(t, "pv-drawing-station")
    for key in DROP_STATIONS:
        pattern = re.compile(rf'[ ]*<option value="{key}"[^>]*>[^<]*</option>\n')
        found = pattern.findall(select)
        if len(found) != 1:
            raise SystemExit(f"✗ 도면 모듈 {key}: 앵커가 {len(found)}곳 — 1곳이어야 한다")
        select = pattern.sub("", select)
    t = head + select + tail
    t = _once(t, '<option value="buffer">GBR-301 · R-A/R-B/HOLD 버퍼</option>',
              '<option value="buffer" selected>GBR-301 · R-A/R-B/HOLD 버퍼</option>',
              "도면 모듈 기본값")
    t = _once(t, "station: 'afu', explode:", "station: 'buffer', explode:", "도면 기본 스테이션")
    # 배치 초점에는 buffer 항목이 없었다 — 이 셀만 그리는 화면이므로 만들어 준다.
    t = _once(t, "var LAYOUT_FOCUS = { all: null, upstream: ['afu', 'robot'], "
                 "jbr: ['jbr'], afr: ['afr', 'post'] };",
              "var LAYOUT_FOCUS = { all: null, upstream: ['afu', 'robot'], "
              "jbr: ['jbr'], afr: ['afr', 'post'], buffer: ['buffer'] };",
              "배치 초점 목록")
    t = _once(t, "focus: 'all', clearance: true", "focus: 'buffer', clearance: true", "배치도 초점")
    t = _once(t, '<option value="all" selected>전체 배치</option>',
              '<option value="all">전체 배치</option>\n'
              '            <option value="buffer" selected>GBR-301 버퍼</option>',
              "배치 초점 기본값")

    # ── 배치도를 이 셀 것으로 좁힌다 ────────────────────────────────────────
    # 초점(`focusBox`)은 **뷰박스만** 옮긴다 — 존 밖 장비도 SVG 에 그대로 그려져
    # 있어서 축소하면 플랜트 50 m 가 다 나온다. 이 파생본은 셀 하나를 보는 화면이라
    # 그리는 단계에서 존을 거른다. `renderLayout` 안에서만 `layoutZones` 를 가리므로
    # 바깥의 `zoneByKey`(초점 계산)는 여전히 모든 존을 본다.
    t = _once(t, "function renderLayout() {\n"
                 "    var ox = LAYOUT_ORIGIN_X, oy = LAYOUT_ORIGIN_Y, "
                 "scale = LAYOUT_SCALE, floorY = LAYOUT_FLOOR_Y;",
              "function renderLayout() {\n"
              "    /* GBR-301 파생본: 이 함수 안에서만 존을 셀 하나로 가린다. */\n"
              "    var layoutZones = window.__pvLayoutZones\n"
              "      || (window.__pvLayoutZones = pvAllZones.filter(function (zone) "
              "{ return zone[0] === 'buffer'; }));\n"
              "    var ox = LAYOUT_ORIGIN_X, oy = LAYOUT_ORIGIN_Y, "
              "scale = LAYOUT_SCALE, floorY = LAYOUT_FLOOR_Y;",
              "배치도 존 거르기")
    # 가린 이름 너머의 원본 목록을 붙잡아 둔다 — 위 filter 가 읽는 것이 이것이다.
    t = _once(t, "  // [키, 표기, X0, X1, Y0, Y1, 높이, 주기]\n  var layoutZones = ",
              "  // [키, 표기, X0, X1, Y0, Y1, 높이, 주기]\n  var pvAllZones, layoutZones = pvAllZones = ",
              "원본 존 목록 별칭")
    # 안전구역은 존 묶음 셋을 도는데, 거르고 나면 나머지 둘은 빈 묶음이라 높이가
    # 음수인 사각형이 나온다. 이 셀 하나만 돈다.
    t = _once(t, "[['afu', 'robot'], ['jbr', 'afr'], ['post', 'buffer']].forEach(function (pair) {",
              "[['buffer', 'buffer']].forEach(function (pair) {", "안전구역 묶음")
    # 도면 이름·설명도 셀 것으로.
    t = _once(t, "out.push('<title>태양광 패널 전처리 플랜트 전체 상세 장비배치도</title><desc>듀얼 "
                 "리프트부터 반전 로봇 정션박스 제거 프레임 분리 검사 연마 레시피 버퍼까지 ' +",
              "out.push('<title>GBR-301 레시피 버퍼셀 장비배치도</title><desc>이 셀 하나의 "
              "평면과 종단 배치 — 상류 존은 통합 설계도에 있다. 설비 전체는 ' +",
              "배치도 제목")
    t = _once(t, "'PV-PLANT-GA-1001 · 전체 플랜트 상세 배치 · REV.22-P01'",
              "'PV-GBR-301-GA-5201 · GBR-301 셀 배치 · ' + DRAWING_REVISION",
              "배치도 시트번호")
    # 탭·버튼 이름과 모듈 제목.
    t = _once(t, '<button class="nav-link" id="pv-tab-layout" role="tab" '
                 'aria-controls="pv-panel-layout" aria-selected="false" type="button">'
                 "전체 장비배치도</button>",
              '<button class="nav-link" id="pv-tab-layout" role="tab" '
              'aria-controls="pv-panel-layout" aria-selected="false" type="button">'
              "장비 스펙·셀 배치</button>", "배치도 탭 이름")
    t = _once(t, "<span>상세 장비배치도</span>", "<span>장비 스펙·셀 배치</span>",
              "배치도 버튼 이름")
    t = _once(t, '<h3 id="pv-drawing-title">Rev.22 2D·3D 상세 제작도면 및 전체 장비배치</h3>',
              '<h3 id="pv-drawing-title">GBR-301 2D·3D 제작도면 및 장비 스펙</h3>',
              "도면 모듈 제목")
    # 전체 치수는 이제 뜻이 없다 — 셀 하나만 그리는데 옆에 「전체 X = 50,075」가
    # 서 있으면 그 폭이 이 장비의 것으로 읽힌다. 셋 다 셀 값으로 바꾼다.
    t = _once(t, "out.push(text(40, 72, 'X=공정방향 · Y=진행방향 좌측 · Z=FFL 상향 · 영구설비 ' +\n"
                 "      [PLANT_X, PLANT_Y, PLANT_Z].map(n).join(' × ') + ' mm', 'pv-layout-small'));",
              "out.push(text(40, 72, 'X=공정방향 · Y=진행방향 좌측 · Z=FFL 상향 · 셀 외형 ' +\n"
              "      [layoutZones[0][3] - layoutZones[0][2], layoutZones[0][5] - layoutZones[0][4],\n"
              "       layoutZones[0][6]].map(n).join(' × ') + ' mm', 'pv-layout-small'));",
              "배치도 기준 문구")
    t = _once(t, "out.push(dimension(mapX(0), 100, mapX(PLANT_X), 100, "
                 "'전체 X = ' + n(PLANT_X) + ' mm', false, 'layout'));",
              "out.push(dimension(mapX(layoutZones[0][2]), 100, mapX(layoutZones[0][3]), 100,\n"
              "      '셀 X = ' + n(layoutZones[0][3] - layoutZones[0][2]) + ' mm', false, 'layout'));",
              "배치도 X 전체치수")
    t = _once(t, "out.push(dimension(mapX(PLANT_X) + 28, mapY(0), mapX(PLANT_X) + 28, mapY(PLANT_Y), "
                 "'전체 Y = ' + n(PLANT_Y) + ' mm', true, 'layout'));",
              # 오른쪽에 세우면 존 주기 글자를 밟는다 — 비어 있는 왼쪽에 세운다.
              "out.push(dimension(mapX(layoutZones[0][2]) - 34, mapY(layoutZones[0][4]),\n"
              "      mapX(layoutZones[0][2]) - 34, mapY(layoutZones[0][5]),\n"
              "      '셀 Y = ' + n(layoutZones[0][5] - layoutZones[0][4]) + ' mm', true, 'layout'));",
              "배치도 Y 전체치수")
    # 팝업 머리글도 셀 것으로.
    t = _once(t, "    layout: '전체 장비 상세 배치도',",
              "    layout: 'GBR-301 장비 스펙 · 셀 배치',", "배치도 팝업 제목")

    # ── 도면 팝업의 나머지 탭 ───────────────────────────────────────────────
    # ① **셀 단위 자료** — 지지·장착의 셀 선택과 도면 목록은 이 셀로 좁히면 맞는다.
    t = _once(t, "mtStationSel.innerHTML = MOUNTINGS.map(function (m) {",
              "mtStationSel.innerHTML = MOUNTINGS.filter(function (m) "
              "{ return m[0] === 'buffer'; }).map(function (m) {", "지지·장착 셀 목록")
    t = _once(t, "mtStation: 'grm',", "mtStation: 'buffer',", "지지·장착 기본 셀")
    t = _once(t, "registerBody.innerHTML = register.map(function (row) {",
              "registerBody.innerHTML = register.filter(function (row) "
              "{ return row.join(' ').indexOf('GBR') >= 0; }).map(function (row) {",
              "도면 목록")
    # ② 플랜트 계통 탭과 그 자리로 가는 사이드바 버튼, 그리고 플랜트 집계인 「지지
    #    부재」 표를 숨긴다. 요소는 남는다 — 원본 렌더러가 첫 렌더에서 채우기 때문이다.
    plant_only = ", ".join(["#pv-panel-mount .table-responsive"]
                           + [f"#{k}" for k in PLANT_SECTIONS])
    plant_tabs = ", ".join(f"#pv-tab-{k}" for k in PLANT_TABS)
    plant_btns = ", ".join(f'[data-pv-drawing-tab="{k}"]' for k in PLANT_TABS)
    t = _once(t, "</head>",
              f"<style>{plant_tabs}, {plant_btns}, {plant_only} "
              f"{{ display: none !important; }}</style>\n</head>",
              "플랜트 계통 탭 CSS")

    # 스펙은 배치도 패널 맨 위에 세운다.
    t = _once(t, '    <div id="pv-panel-layout" role="tabpanel" '
                 'aria-labelledby="pv-tab-layout" hidden>\n',
              '    <div id="pv-panel-layout" role="tabpanel" '
              'aria-labelledby="pv-tab-layout" hidden>\n' + spec_block(text),
              "장비 전체 스펙")

    # ── 흐름표 ──────────────────────────────────────────────────────────────
    t = _once(t, '<h3 id="pv-flow-title">전체 공정 흐름</h3>',
              '<h3 id="pv-flow-title">GBR-301 공정 흐름 '
              '<span class="text-small text-muted">투입·JBR·AFR 과 SG 연마·GI 검사는 범위 밖</span></h3>',
              "흐름표 제목")
    t = _once(t, "</head>",
              f"<style>.pv-flow-track > li:nth-child(-n+{FLOW_FIRST - 1}),"
              f" .pv-flow-track > li:nth-child(n+{FLOW_LAST + 1}) {{ display: none; }}</style>\n</head>",
              "흐름표 CSS")

    # ── 발주 요청 셋: 그림자 · 외장 케이싱 · 천장크레인 ─────────────────────
    # ① 그림자 — 렌더러 섀도맵을 첫 렌더 전에 끈다. 캐리지 밑과 마스트 사이를
    #    어둡게 덮기만 한다. 재질 재컴파일이 필요 없는 자리다.
    t = _once(t, "Dt.shadowMap.enabled=!0;", "Dt.shadowMap.enabled=!1;", "3D 그림자")
    # ② 외장 케이싱 — 껍질이 셔틀과 적재기를 가린다. 토글 기본값을 끄고, 장면 모듈이
    #    묶음째 끈다 (토글은 남으니 외형이 필요하면 켤 수 있다).
    t = _once(t, '<input class="form-check-input" id="pv-case" type="checkbox" checked>',
              '<input class="form-check-input" id="pv-case" type="checkbox">', "외장 케이싱 기본값")
    # ③ CRN-901 천장크레인 — 셀에 매이지 않는 `pvSpans` 묶음이라 이름을 붙여야
    #    장면 모듈이 통째로 끌 수 있다. `pvCase` 가 이미 쓰는 방식과 같다.
    t = _once(t, "var pvCrn=new ce;pt.add(pvSpans(pvCrn));",
              "var pvCrn=new ce;pvCrn.name='pvCrn';pt.add(pvSpans(pvCrn));", "천장크레인 이름")

    # ── 부품 2D·3D 검색 ─────────────────────────────────────────────────────
    # 이 셀 부품은 품번이 AFR- 접두어를 쓰고(3D 라벨도 「AFR GBR-301 …」이다) 카탈로그
    # 에서는 **분류**로 묶여 있다. 그래서 접두어로는 못 좁힌다 — 검색이 분류 제목도
    # 보게 하고 검색창을 그 분류로 채운다. 목록 자체는 줄이지 않는다.
    t = _once(t, 'placeholder="예: AFU-LFT, 승강, EOAT"',
              f'value="{PARTS_GROUP}" placeholder="예: 레시피 버퍼, 콤포크, 캐리지"',
              "부품 검색 기본값")
    t = _once(t, "    if (name === 'parts' && partsCatalog) partsCatalog.open = true;",
              "    if (name === 'parts' && partsCatalog) { partsCatalog.open = true; applyPartsFilter(); }",
              "부품 검색 최초 적용")
    t = _once(t, "      var hit = !needle || row.textContent.toLowerCase().indexOf(needle) >= 0;",
              "      /* 분류 제목도 본다 — 이 셀 부품은 품번이 아니라 분류로 묶여 있다.\n"
              "         제목과 행을 **따로** 견준다 (이어 붙이면 경계에서 헛맞는다). */\n"
              "      var section = row.closest('.jb-part-group');\n"
              "      var heading = section && section.querySelector('h3');\n"
              "      var head = heading ? heading.textContent.toLowerCase() : '';\n"
              "      var hit = !needle || head.indexOf(needle) >= 0\n"
              "        || row.textContent.toLowerCase().indexOf(needle) >= 0;",
              "부품 검색 분류 포함")

    # ── 상류 전용 조작 ──────────────────────────────────────────────────────
    for key in HIDDEN_CONTROLS:
        if f'<label class="form-label" for="{key}">' not in t:
            raise SystemExit(f"✗ 범위 밖 조작 {key} 의 라벨이 없다")
    # `!important` 없이는 못 이긴다 — 배치 초점 라벨은 `.pv-layout-toolbar .form-label`
    # (클래스 둘)이 잡고 있어서 `label[for=…]`(클래스 하나) 보다 우선순위가 높다.
    hidden = ", ".join(f'label[for="{k}"]' for k in HIDDEN_CONTROLS)
    t = _once(t, "</head>", f"<style>{hidden} {{ display: none !important; }}</style>\n</head>",
              "범위 밖 조작 CSS")
    # 이 셀의 조작은 이름부터 이 셀 것으로 바꾼다 — 원본에서 「AFR 가상 레시피」로
    # 불리던 것이 실은 **버퍼**의 목표 캐리지를 고르는 조작이다.
    t = _once(t, '<label class="form-label" for="afr-route-mode">AFR 가상 레시피 시나리오',
              '<label class="form-label" for="afr-route-mode">GBR 레시피 시나리오 (목표 캐리지)',
              "버퍼 레시피 조작 이름")

    # ── 장면을 좁히는 모듈 — 원본 모듈 뒤에 선다 ────────────────────────────
    t = _once(t, "</body>", scene_script(low, high, t0, t1) + "</body>", "장면 모듈")
    t = _once(t, "<!doctype html>\n",
              "<!doctype html>\n<!-- GBR-301 파생본: tools/build_gbr_scene.py 가 통합 "
              "설계도(pv-preprocess-plant.html)에서 만든다. 손으로 고치지 않는다.\n"
              f"     셀 외형 {L:,} × {W:,} × {H:,} mm · 창 [{t0:g}, {t1:g}] s "
              f"(후단 마지막 칸 {span:g} s 의 진도 {HANDOVER_V:g} 부터) · "
              "그림자·외장 케이싱·CRN-901 천장크레인 제외. -->\n",
              "파생본 표식")
    return t


def main() -> None:
    out = build()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == out:
        print(f"{OUT.relative_to(ROOT)}  변경 없음")
        return
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(out.encode('utf-8')) / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
