# -*- coding: utf-8 -*-
"""GI-302 · GI-303 유리 검사 — **볼 수 있는가**를 푸는 모델.

저장소에 이 셀의 값은 둘뿐이었다. `smart` 의 라인스캔 해상도 0.1 mm/px 와
`ai` 의 "장당 350 MB". 둘은 서로 맞는다(2,500/0.1 × 1,400/0.1 = 350 M화소).
하지만 그 둘만으로는 **검사대가 성립하는지**를 말할 수 없다. 라인스캔은 셋이
한 사슬로 묶여 있기 때문이다.

    이송 속도 → 라인레이트 → 노광시간 → 필요 조도

그리고 넷째가 형상이다. `vision` 은 GI-303 을 "CV-102 롤러(Ø90 · 피치 240)
사이 150 mm 틈에 라인조명과 라인스캔을 넣어 통과 중에 밑을 본다" 고 적었고,
통합 설계도는 그 자리에 **550 mm** 를 배정했다. 폭 1,400 을 550 안에서 볼 수
있는가는 렌즈 공식이 답한다 — 그리고 **한 대로는 안 된다**는 것이 이 모듈이
찾은 것이다.

    PYTHONPATH=src python -c "from pv_preprocess import gi_optics; print(gi_optics.summary())"

값의 출처를 갈라 적는다 — 다른 모듈에서 온 것(해상도·패널·이송·배정 공간),
카탈로그 계획값(센서·렌즈·카메라 몸통), 그리고 광학의 정의식.
"""

from __future__ import annotations

import math

from .afr_units import Part, Unit
from . import campaign, handoff, smart, vision

# ── 다른 모듈이 정한 것 ─────────────────────────────────────────────────
#: 라인스캔 해상도 (mm/px) — `smart` 가 정본.
RESOLUTION_MM = float(smart.LINESCAN_RESOLUTION_MM)
#: 패널 폭·길이 (mm) — `smart.PANEL_MAX_MM` 이 정본.
PANEL_W_MM = float(smart.PANEL_MAX_MM[1])
PANEL_L_MM = float(smart.PANEL_MAX_MM[0])

#: CV-102 통과 이송 속도 (mm/s). 반출롤러와 같은 속도로 흐른다 — 유리가
#: SG-301 을 지나 그대로 검사대 밑으로 들어가므로 갈아탈 이유가 없다.
TRANSPORT_MM_S = float(campaign.SG_PASS_MM_S)

# ── 통합 설계도가 배정한 자리 ───────────────────────────────────────────
#: GI-303 이 쓸 수 있는 롤러 **밑** 높이 (mm) — 3D 부품 GI-303 의 y 치수.
BELOW_DECK_MM = 550.0
#: GI-302 가 쓸 수 있는 롤러 **위** 높이 (mm) — 검사대 갠트리 안쪽.
ABOVE_DECK_MM = 1_100.0
#: CV-102 롤러 외경과 피치 (mm) — 그 사이가 밑을 볼 수 있는 창이다.
ROLLER_D_MM, ROLLER_PITCH_MM = 90.0, 240.0

# ── 카탈로그 계획값 ─────────────────────────────────────────────────────
#: 라인스캔 센서 — 16k × 3.52 µm. 폭이 곧 상의 크기다.
SENSOR_PX = 16_384
SENSOR_PITCH_UM = 3.52
#: 렌즈 초점거리 후보 (mm) — 이 상 크기를 덮는 라인스캔 렌즈의 통상 계열.
LENS_F_MM = 35.0
#: 카메라 몸통 + 렌즈 뒷단이 광축 방향으로 먹는 길이 (mm).
CAMERA_BODY_MM = 180.0
#: 조리개와 허용착란원 (mm) — 피사계심도를 정한다.
F_NUMBER = 5.6
CIRCLE_OF_CONFUSION_MM = 2.0 * SENSOR_PITCH_UM / 1_000.0
#: 노광이 라인주기에서 차지하는 몫 — 나머지는 전송·리셋이다.
EXPOSURE_DUTY = 0.8
#: 통과 중 판이 뜨거나 처지는 양 (mm) — 심도가 이것을 덮어야 한다.
PANEL_BOW_MM = 3.0

#: 결함이 **확실히** 잡히려면 몇 화소를 덮어야 하는가 — 검사 관례.
PIXELS_PER_FEATURE = 3


# ── 사슬 ① 이송 → 라인레이트 → 노광 ────────────────────────────────────
def line_rate_hz() -> float:
    """라인레이트 (line/s) — 화소가 정사각이려면 이 속도로 찍어야 한다."""
    return round(TRANSPORT_MM_S / RESOLUTION_MM, 1)


def line_period_us() -> float:
    """라인 주기 (µs)."""
    return round(1e6 / line_rate_hz(), 2)


def exposure_us() -> float:
    """한 줄에 주어지는 노광시간 (µs)."""
    return round(line_period_us() * EXPOSURE_DUTY, 2)


def exposure_vs_area_camera() -> int:
    """면적 카메라(1/60 s)보다 노광이 몇 배 짧은가.

    같은 밝기를 얻으려면 그만큼 밝은 조명이 필요하다는 뜻이다 — 라인스캔
    검사대에서 먼저 막히는 곳이 대개 렌즈가 아니라 **조명**인 이유다.
    """
    return round((1.0 / 60.0) / (exposure_us() / 1e6))


# ── 사슬 ② 형상 → 카메라 대수 ──────────────────────────────────────────
def sensor_width_mm() -> float:
    """센서 폭 (mm) = 상의 크기."""
    return round(SENSOR_PX * SENSOR_PITCH_UM / 1_000.0, 3)


def pixels_needed() -> int:
    """폭 방향으로 필요한 화소 수."""
    return round(PANEL_W_MM / RESOLUTION_MM)


def sensor_covers_the_width(cameras: int) -> bool:
    """카메라 `cameras` 대로 필요한 화소가 나오는가."""
    return cameras * SENSOR_PX >= pixels_needed()


def magnification(cameras: int) -> float:
    """배율 m = 상 크기 / 물체 크기 (대당)."""
    return round(sensor_width_mm() / (PANEL_W_MM / cameras), 5)


def working_distance_mm(cameras: int) -> float:
    """작동거리 (mm) — 얇은렌즈 WD = f(1 + 1/m)."""
    return round(LENS_F_MM * (1.0 + 1.0 / magnification(cameras)), 1)


def stack_height_mm(cameras: int) -> float:
    """광축 방향으로 실제로 먹는 높이 (mm) — 작동거리 + 카메라 몸통."""
    return round(working_distance_mm(cameras) + CAMERA_BODY_MM, 1)


def fits_below_deck(cameras: int) -> bool:
    """롤러 밑 배정 공간 안에 들어가는가."""
    return stack_height_mm(cameras) <= BELOW_DECK_MM


def cameras_below() -> int:
    """GI-303 에 필요한 최소 카메라 대수 — 공간이 정한다."""
    for n in range(1, 17):
        if fits_below_deck(n) and sensor_covers_the_width(n):
            return n
    raise SystemExit("배정 공간 안에서는 어떤 대수로도 안 된다 — 접이 광학이 필요하다")


def cameras_above() -> int:
    """GI-302 에 필요한 최소 카메라 대수 — 위는 공간이 넉넉하다."""
    for n in range(1, 17):
        if (stack_height_mm(n) <= ABOVE_DECK_MM) and sensor_covers_the_width(n):
            return n
    raise SystemExit("갠트리 안에서도 안 된다")


def one_camera_would_need_mm() -> float:
    """한 대로 하려면 몇 mm 가 있어야 하는가 — 배정과 견주려고."""
    return stack_height_mm(1)


def single_camera_shortfall_mm() -> float:
    """한 대 안이 배정 공간을 얼마나 넘는가 (mm)."""
    return round(one_camera_would_need_mm() - BELOW_DECK_MM, 1)


def single_camera_is_possible() -> bool:
    """GI-303 을 한 대로 할 수 있는가 — 이 모듈이 아니라고 답하는 자리."""
    return fits_below_deck(1)


def seam_overlap_mm(cameras: int, overlap_px: int = 64) -> float:
    """카메라끼리 겹쳐야 하는 폭 (mm) — 이어붙일 때 이음매가 비면 안 된다."""
    return round(overlap_px * RESOLUTION_MM * (cameras - 1), 2)


# ── 사슬 ③ 심도와 롤러 창 ──────────────────────────────────────────────
def depth_of_field_mm(cameras: int) -> float:
    """피사계심도 (mm) — DOF ≈ 2·N·c·(1+m)/m²."""
    m = magnification(cameras)
    return round(2.0 * F_NUMBER * CIRCLE_OF_CONFUSION_MM * (1.0 + m) / (m * m), 2)


def depth_covers_the_bow(cameras: int) -> bool:
    """통과 중 판이 뜨고 처지는 양을 심도가 덮는가."""
    return depth_of_field_mm(cameras) >= PANEL_BOW_MM


def roller_window_mm() -> float:
    """롤러 사이로 밑이 보이는 창 (mm) — 피치에서 외경을 뺀 값."""
    return round(ROLLER_PITCH_MM - ROLLER_D_MM, 1)


def window_matches_vision_note() -> bool:
    """`vision` 이 GI-303 주기에 적어 둔 150 mm 와 같은가."""
    return abs(roller_window_mm() - 150.0) < 1e-6


def scan_line_fits_the_window() -> bool:
    """스캔선 하나가 그 창 안에 드는가 — 선이므로 폭은 화소 하나다."""
    return RESOLUTION_MM < roller_window_mm()


def unsupported_span_mm() -> float:
    """유리가 받쳐지지 않는 거리 (mm) — 창이 아니라 **피치**다.

    평평한 판은 롤러 **꼭대기 한 줄**에만 닿는다. 그러니 받침과 받침 사이는
    롤러 표면 사이 틈(창 150)이 아니라 접촉선 사이, 곧 피치 240 이다. 카메라가
    보는 것은 창이고 구조가 버티는 것은 피치다 — 처음에 창으로 적었다가
    `gi_plate` 가 처짐을 풀면서 잡았다.
    """
    return float(ROLLER_PITCH_MM)


# ── 사슬 ④ 무엇이 보이는가 ─────────────────────────────────────────────
def smallest_reliable_feature_mm() -> float:
    """확실히 잡히는 최소 결함 크기 (mm) — 화소 하나로는 못 믿는다."""
    return round(PIXELS_PER_FEATURE * RESOLUTION_MM, 3)


def sealant_band_is_visible() -> bool:
    """면에 남는 실란트 띠가 이 해상도에서 보이는가."""
    from . import sg_grind
    return sg_grind.SEALANT_BAND_MM >= smallest_reliable_feature_mm()


def sealant_band_in_pixels() -> int:
    """그 띠가 몇 화소를 덮는가."""
    from . import sg_grind
    return round(sg_grind.SEALANT_BAND_MM / RESOLUTION_MM)


def arris_in_pixels() -> float:
    """아리스 다리가 몇 화소인가 — 1 을 밑돌면 폭으로는 못 잰다."""
    from . import sg_grind
    return round(sg_grind.ARRIS_MM / RESOLUTION_MM, 2)


def arris_is_measurable() -> bool:
    """아리스 폭을 이 해상도로 잴 수 있는가."""
    return arris_in_pixels() >= PIXELS_PER_FEATURE


# ── 사슬 ⑤ 자료량과 시간 ───────────────────────────────────────────────
def pixels_per_panel() -> int:
    """한 장의 화소 수 — `smart` 의 스트림 크기와 같아야 한다."""
    return round(PANEL_L_MM / RESOLUTION_MM) * pixels_needed()


def mb_per_panel() -> float:
    """한 장 (MB, 8 bit)."""
    return round(pixels_per_panel() / 1e6, 1)


def agrees_with_the_ai_note() -> bool:
    """`ai` 가 적어 둔 '장당 350 MB' 와 맞는가."""
    return abs(mb_per_panel() - 350.0) < 1.0


def pixel_rate_mpx_s() -> float:
    """화소율 (Mpx/s) — 카메라 인터페이스가 감당해야 하는 값."""
    return round(pixels_needed() * line_rate_hz() / 1e6, 1)


def scan_time_s() -> float:
    """한 장이 스캔선을 지나는 데 걸리는 시간 (s)."""
    return round(PANEL_L_MM / TRANSPORT_MM_S, 3)


def glass_per_h() -> float:
    """검사대를 지나는 정상 유리 (장/h) — `handoff` 가 정본."""
    return handoff.sheet_glass_per_h()


def duty() -> float:
    """검사대가 실제로 찍고 있는 시간 비율."""
    return round(scan_time_s() * glass_per_h() / 3600.0, 4)


def fits_the_takt() -> bool:
    """스캔이 택트 안에 드는가."""
    return scan_time_s() <= float(campaign.summary()["takt_s"])


# ── 어느 헤드가 살아 있는가 ────────────────────────────────────────────
def kept_heads() -> tuple[str, ...]:
    """존치된 GI 헤드 — `vision` 이 정본. GI-301 은 V-4 에서 은퇴했다."""
    return tuple(h.tag for h in vision.HEADS if h.kept and h.tag.startswith("GI-"))


def there_is_no_pre_grind_check() -> bool:
    """연마 **전** 검사가 없는가 — 없으면 공정창이 고정이어야 한다."""
    return "GI-301" not in kept_heads()


def open_questions() -> tuple[tuple[str, str], ...]:
    """이 모델이 못 닫는 것 — 계산에서 나온다."""
    out: list[tuple[str, str]] = []
    if not single_camera_is_possible():
        out.append((
            "GI-303 은 한 대로 안 된다",
            f"폭 {PANEL_W_MM:,.0f} 을 0.1 mm/px 로 보려면 한 대짜리 광학계가 "
            f"**{one_camera_would_need_mm():,.0f} mm** 를 먹는데 롤러 밑에 배정된 것은 "
            f"{BELOW_DECK_MM:.0f} mm 다 — **{single_camera_shortfall_mm():,.0f} mm 초과.** "
            f"f{LENS_F_MM:.0f} 렌즈로는 **{cameras_below()} 대**를 나란히 놓아야 들어가고"
            f"(대당 시야 {PANEL_W_MM / cameras_below():,.0f} mm · WD "
            f"{working_distance_mm(cameras_below()):.0f} mm), 이음매마다 겹침이 필요하다. "
            "접이 거울로 광로를 접는 대안이 있지만 그것은 배치가 정할 일이다."))
    if not depth_covers_the_bow(cameras_below()):
        out.append((
            "심도가 판 휨을 못 덮는다",
            f"심도 {depth_of_field_mm(cameras_below())} mm 가 통과 중 휨 "
            f"{PANEL_BOW_MM} mm 보다 얕다. 조리개를 조이면 조도가 더 필요하다."))
    if not arris_is_measurable():
        out.append((
            "아리스 폭은 이 해상도로 못 잰다",
            f"아리스 다리가 {arris_in_pixels()} 화소라 확실한 판정에 필요한 "
            f"{PIXELS_PER_FEATURE} 화소에 못 미친다. **있고 없음**은 보이지만 "
            f"**{smallest_reliable_feature_mm()} mm** 아래의 폭 치수는 이 검사대의 "
            "일이 아니다 — 공정창 고정과 표본 계측으로 받아야 한다."))
    if there_is_no_pre_grind_check():
        out.append((
            "연마 전 검사가 없다",
            "GI-301 이 V-4 에서 은퇴해 전/후 비교가 없다. `vision` 이 적어 둔 대로 "
            "**연마 공정창 고정이 전제**이고, 그 전제는 인발 뒤 면에 남는 실란트 몫이 "
            "실측돼야 선다 (`sg_grind` 미결 2)."))
    out.append((
        "조명 밝기가 아직 값이 아니다",
        f"노광이 {exposure_us():.0f} µs 로 면적 카메라(1/60 s)의 "
        f"**1/{exposure_vs_area_camera():,}** 이다. 그만큼 밝은 라인조명이 필요하고, "
        "그 값은 대상 반사율과 조리개가 정해져야 나온다 — 유리 하부는 정반사라 "
        "명시야로 볼지 암시야로 볼지가 먼저다."))
    return tuple(out)


# ── 형상 ───────────────────────────────────────────────────────────────
#: 렌즈 경통이 광축으로 먹는 길이 (mm). 나머지가 카메라 몸통이다 —
#: 둘의 합이 `CAMERA_BODY_MM` 이라 스택 높이는 여기서 새로 안 생긴다.
LENS_BODY_MM = 60.0
#: 카메라·조명을 다는 브래킷 판 두께 (mm).
BRACKET_T_MM = 12.0
#: 라인조명 바 단면 (mm) — 폭 × 높이. 길이는 시야에서 나온다.
LIGHT_BAR_MM = (70.0, 45.0)
#: 광학을 유리가루에서 막는 보호창 두께 (mm). 창은 스캔 창 안에 들어가야 한다.
COVER_GLASS_T_MM = 6.0
#: 판 밑면에서 보호창 윗면까지 (mm) — 판이 이보다 처지면 보호창을 친다.
COVER_GAP_MM = 8.0
#: GI-302 갠트리 보 단면 (mm).
GANTRY_MM = (200.0, 160.0)
#: 롤러 창 접촉부를 세울 때의 배율 — 창 150 mm 는 셀 전체 옆에서 안 보인다.
WINDOW_MAG = 6.0
#: 접촉부 확대도가 잘라 보는 이송방향 길이 (mm).
WINDOW_SPAN_MM = 3.0 * ROLLER_PITCH_MM


def lens_housing_mm() -> float:
    """카메라 몸통에서 렌즈를 뺀 길이 (mm) — 센서와 전자부가 있는 쪽."""
    return round(CAMERA_BODY_MM - LENS_BODY_MM, 3)


def field_width_mm(cameras: int) -> float:
    """대당 담당 폭 (mm) — 겹침 전의 몫."""
    return round(PANEL_W_MM / cameras, 3)


def seam_overlap_each_mm(cameras: int, overlap_px: int = 64) -> float:
    """이음매 **하나당** 겹침 (mm). 이음매는 대수보다 하나 적다."""
    if cameras < 2:
        return 0.0
    return round(seam_overlap_mm(cameras, overlap_px) / (cameras - 1), 3)


def seam_map(cameras: int | None = None) -> tuple[dict[str, float], ...]:
    """폭을 대수로 나눈 자리표 — 어느 카메라가 어디를 보는가.

    폭을 같은 크기의 몫으로 자르고, 안쪽 이음매마다 겹침의 절반씩을 양쪽이
    더 본다. 그래야 이웃끼리 정확히 `seam_overlap_each_mm` 만큼 겹치고,
    합집합이 폭을 빈틈없이 덮는다 — 이음매가 비면 거기 있는 균열을 못 본다.
    """
    n = cameras or cameras_below()
    half = seam_overlap_each_mm(n) / 2.0
    # 몫의 경계는 **반올림 전** 값으로 잡는다 — 반올림한 몫을 n 번 더하면
    # 폭을 넘겨(1,400.001) 자리표가 판 밖을 가리킨다.
    edge = lambda i: -PANEL_W_MM / 2.0 + PANEL_W_MM * i / n
    out = []
    for i in range(n):
        lo = edge(i) - (half if i else 0.0)
        hi = edge(i + 1) + (half if i < n - 1 else 0.0)
        out.append({"index": i, "from": round(lo, 3), "to": round(hi, 3),
                    "centre": round((lo + hi) / 2.0, 3),
                    "width": round(hi - lo, 3)})
    return tuple(out)


def seam_map_covers_the_width() -> bool:
    """자리표가 폭을 빈틈없이 덮는가 — 그림이 아니라 수가 답한다."""
    m = seam_map()
    return (abs(m[0]["from"] + PANEL_W_MM / 2.0) < 1e-6
            and abs(m[-1]["to"] - PANEL_W_MM / 2.0) < 1e-6
            and all(m[i + 1]["from"] < m[i]["to"] for i in range(len(m) - 1)))


def _camera_parts(prefix: str, sign: int, cameras: int,
                  catalog: str) -> list[Part]:
    """라인스캔 한 벌 — 보호창·조명·렌즈·카메라. 위아래가 같은 것을 쓴다.

    `sign` 이 +1 이면 유리 **위**, −1 이면 **밑**이다. 유리면이 y = 0 이고
    광축이 그 부호 방향으로 뻗는다 — 작동거리와 몸통 길이가 모두 모델값이라
    화면의 높이가 곧 스택 높이다.
    """
    wd = working_distance_mm(cameras)
    fov = field_width_mm(cameras) + seam_overlap_each_mm(cameras)
    lens_y = sign * (wd + LENS_BODY_MM / 2.0)
    body_y = sign * (wd + LENS_BODY_MM + lens_housing_mm() / 2.0)
    out: list[Part] = []
    for i, seat in enumerate(seam_map(cameras)):
        cx = float(seat["centre"])
        out.append(Part(
            f"{prefix}lens{i}", "라인스캔 렌즈", 1, "cyl",
            (72.0, LENS_BODY_MM, 72.0), (cx, lens_y, 0.0),
            f"f{LENS_F_MM:.0f} · F{F_NUMBER}", axis="y",
            role=f"작동거리 {wd:.0f} mm 에서 폭 {fov:.0f} mm 를 센서 "
                 f"{sensor_width_mm():.1f} mm 에 맺는다 — 배율 "
                 f"{magnification(cameras):.4f}. 심도가 "
                 f"{depth_of_field_mm(cameras)} mm 라 통과 중 판 휨 "
                 f"{PANEL_BOW_MM} mm 를 덮는다.",
            color="chrome", explode=(0.0, sign * 90.0, 0.0),
            spec=f"f{LENS_F_MM:.0f} · F{F_NUMBER} · WD {wd:.0f} mm",
            catalog=f"{catalog}-LN"))
        out.append(Part(
            f"{prefix}cam{i}", "라인스캔 카메라", 1, "box",
            (96.0, lens_housing_mm(), 96.0), (cx, body_y, 0.0),
            f"{SENSOR_PX // 1024}k × {SENSOR_PITCH_UM} µm", axis="y",
            role=f"{line_rate_hz():,.0f} line/s 로 읽는다. 노광 "
                 f"{exposure_us():.0f} µs 는 면적 카메라의 "
                 f"1/{exposure_vs_area_camera():,} 이다 — 라인스캔에서 먼저 "
                 f"막히는 것은 렌즈가 아니라 조명이다.",
            color="dark", explode=(0.0, sign * 200.0, 0.0),
            spec=f"{SENSOR_PX:,} px · {line_rate_hz():,.0f} line/s · "
                 f"{pixel_rate_mpx_s() / cameras:.0f} Mpx/s",
            catalog=f"{catalog}-CAM"))
    out.append(Part(
        f"{prefix}light", "라인조명 바", 2, "box",
        (PANEL_W_MM, LIGHT_BAR_MM[1], LIGHT_BAR_MM[0]),
        (0.0, sign * (LIGHT_BAR_MM[1] / 2.0 + COVER_GLASS_T_MM + 20.0),
         float(roller_window_mm()) / 4.0),
        "고휘도 LED 라인", mirror=("z",),
        role=f"스캔선 한 줄만 밝히면 된다. 밝기는 **아직 값이 아니다** — "
             f"노광 {exposure_us():.0f} µs 에 맞추려면 대상 반사율과 조리개가 "
             f"먼저 정해져야 한다.",
        color="amber", explode=(0.0, sign * 40.0, 0.0),
        spec=f"길이 {PANEL_W_MM:.0f} · 단면 {LIGHT_BAR_MM[0]:.0f}×"
             f"{LIGHT_BAR_MM[1]:.0f}",
        catalog=f"{catalog}-LT"))
    out.append(Part(
        f"{prefix}cover", "보호창", 1, "box",
        (PANEL_W_MM, COVER_GLASS_T_MM, float(roller_window_mm()) - 20.0),
        (0.0, sign * (COVER_GLASS_T_MM / 2.0 + COVER_GAP_MM), 0.0),
        "강화유리 / 반사방지",
        role=f"유리가루에서 광학을 막는다. 폭 "
             f"{roller_window_mm() - 20.0:.0f} mm 라 스캔 창 "
             f"{roller_window_mm():.0f} mm 안에 든다.",
        color="glass", explode=(0.0, sign * 20.0, 0.0),
        spec=f"t{COVER_GLASS_T_MM:.0f} · 창 {roller_window_mm():.0f} 안",
        catalog=f"{catalog}-WD"))
    out.append(Part(
        f"{prefix}brk", "광학 브래킷", cameras, "box",
        (140.0, BRACKET_T_MM, 260.0),
        (0.0, sign * (wd + CAMERA_BODY_MM - BRACKET_T_MM), 0.0),
        "SS275 판재", mirror=(),
        role=f"카메라 {cameras} 대를 같은 평면에 세운다. 대수가 화소가 아니라 "
             f"**자리** 때문임을 여기가 보여 준다.",
        color="frame", explode=(0.0, sign * 260.0, 0.0),
        spec=f"t{BRACKET_T_MM:.0f} · {cameras} 자리",
        catalog=f"{catalog}-BR"))
    return out


def _roller_parts(prefix: str, count: int, mag: float = 1.0) -> list[Part]:
    """CV-102 롤러 — 그 사이가 곧 스캔 창이다."""
    pitch, d = ROLLER_PITCH_MM * mag, ROLLER_D_MM * mag
    out = []
    for i in range(count):
        z = (i - (count - 1) / 2.0) * pitch
        out.append(Part(
            f"{prefix}rl{i}", "CV-102 이송롤러", 1, "cyl",
            (d, PANEL_W_MM, d), (0.0, -d / 2.0, z),
            "우레탄 피복 강관", axis="x",
            role=f"피치 {ROLLER_PITCH_MM:.0f} − 외경 {ROLLER_D_MM:.0f} = 창 "
                 f"**{roller_window_mm():.0f} mm**. `vision` 이 GI-303 주기에 "
                 f"적어 둔 값과 같다.",
            color="dark", explode=(0.0, -140.0, 0.0),
            spec=f"Ø{ROLLER_D_MM:.0f} · 피치 {ROLLER_PITCH_MM:.0f}",
            catalog="CV-102-RL"))
    return out


def below_unit() -> Unit:
    """GI-303 하부 라인스캔 — **자리가 모자라 여러 대**인 유닛."""
    n = cameras_below()
    parts = _camera_parts("lo", -1, n, "GI-303") + _roller_parts("lo", 4)
    parts.append(Part(
        "loglass", "패널 (통과 중)", 1, "box",
        (PANEL_W_MM, float(smart.LINESCAN_RESOLUTION_MM) * 32.0, 900.0),
        (0.0, 3.0, 0.0), "유리 + EVA + 백시트",
        role=f"{TRANSPORT_MM_S:.0f} mm/s 로 지나간다. 길이 {PANEL_L_MM:.0f} mm 를 "
             f"{scan_time_s()} s 에 훑는다.",
        color="glass", explode=(0.0, 260.0, 0.0),
        spec=f"{PANEL_L_MM:.0f} × {PANEL_W_MM:.0f} · {TRANSPORT_MM_S:.0f} mm/s"))
    return Unit(
        key="below", name="GI-303 하부 라인스캔",
        sheet="PV-GI-303-OPT-5101",
        envelope_mm=(PANEL_W_MM + 200.0, BELOW_DECK_MM, 900.0),
        view_r_mm=900.0,
        principle=(
            ("① 창은 롤러가 만든다",
             f"피치 {ROLLER_PITCH_MM:.0f} 에서 외경 {ROLLER_D_MM:.0f} 을 빼면 "
             f"**{roller_window_mm():.0f} mm** 가 남는다. 스캔선은 폭이 화소 "
             f"하나({RESOLUTION_MM} mm)라 그 안에 넉넉히 든다."),
            ("② 폭을 보려면 자리가 든다",
             f"폭 {PANEL_W_MM:.0f} 을 {RESOLUTION_MM} mm/px 로 보려면 한 대짜리 "
             f"광학계가 **{one_camera_would_need_mm():.0f} mm** 를 먹는다. "
             f"배정된 것은 {BELOW_DECK_MM:.0f} mm — "
             f"**{single_camera_shortfall_mm():.0f} mm 초과**다."),
            ("③ 그래서 여러 대다 — 화소 때문이 아니다",
             f"센서 한 장이면 화소는 {SENSOR_PX:,} 로 필요한 "
             f"{pixels_needed():,} 에 대해 남는다. **{n} 대**로 나눠야 스택이 "
             f"{stack_height_mm(n):.0f} mm 로 줄어 {BELOW_DECK_MM:.0f} 안에 든다."),
            ("④ 나눈 자리는 겹쳐야 한다",
             f"대당 시야 {field_width_mm(n):.0f} mm 에 이음매마다 "
             f"{seam_overlap_each_mm(n)} mm 씩 겹친다. 비면 거기 있는 균열을 "
             f"못 본다."),
            ("⑤ 판이 떠도 초점은 산다",
             f"심도 {depth_of_field_mm(n)} mm 가 통과 중 휨 {PANEL_BOW_MM} mm 를 "
             f"덮는다. 받침은 롤러 꼭대기 한 줄씩이라 받쳐지지 않는 거리는 "
             f"피치 {unsupported_span_mm():.0f} mm 다 — 그 처짐은 `gi_plate` 가 푼다."),
        ),
        parts=tuple(parts))


def above_unit() -> Unit:
    """GI-302 상부 라인스캔 — 위는 자리가 넉넉해 한 대로 끝난다."""
    n = cameras_above()
    parts = _camera_parts("up", +1, n, "GI-302") + _roller_parts("up", 4)
    parts.append(Part(
        "upgantry", "검사대 갠트리 보", 2, "box",
        (PANEL_W_MM + 400.0, GANTRY_MM[1], GANTRY_MM[0]),
        (0.0, stack_height_mm(n) + GANTRY_MM[1] / 2.0, 0.0),
        "SS275 각관", mirror=("z",),
        role=f"위쪽 배정 {ABOVE_DECK_MM:.0f} mm 안에서 광학을 매단다. "
             f"스택이 {stack_height_mm(n):.0f} mm 라 한 대로 끝난다 — "
             f"밑과 같은 광학인데 답이 다른 이유는 **자리뿐**이다.",
        color="frame", explode=(0.0, 260.0, 0.0),
        spec=f"{GANTRY_MM[0]:.0f}×{GANTRY_MM[1]:.0f} 각관",
        catalog="GI-302-GT"))
    parts.append(Part(
        "upglass", "패널 (통과 중)", 1, "box",
        (PANEL_W_MM, float(smart.LINESCAN_RESOLUTION_MM) * 32.0, 900.0),
        (0.0, -3.0, 0.0), "유리 + EVA + 백시트",
        role=f"윗면을 본다 — SG-301 이 지나간 유리면이다. 밑과 같은 판인데 "
             f"위에서는 롤러가 안 가리므로 창이 필요 없다.",
        color="glass", explode=(0.0, -260.0, 0.0),
        spec=f"{PANEL_L_MM:.0f} × {PANEL_W_MM:.0f}"))
    return Unit(
        key="above", name="GI-302 상부 라인스캔",
        sheet="PV-GI-302-OPT-5201",
        envelope_mm=(PANEL_W_MM + 400.0, ABOVE_DECK_MM, 900.0),
        view_r_mm=900.0,
        principle=(
            ("① 같은 광학, 다른 답",
             f"밑과 똑같은 f{LENS_F_MM:.0f} · {SENSOR_PX:,} px 인데 여기는 "
             f"**{n} 대**로 끝난다. 스택 {stack_height_mm(n):.0f} mm 가 위쪽 배정 "
             f"{ABOVE_DECK_MM:.0f} mm 안에 들기 때문이다."),
            ("② 위는 창이 필요 없다",
             "롤러가 밑에 있으므로 윗면은 통째로 보인다 — 밑을 어렵게 만든 것은 "
             "광학이 아니라 이송이었다."),
            ("③ 보는 것은 연마면이다",
             f"SG-301 이 지난 유리 변과 면이다. 아리스 {arris_in_pixels():.0f} 화소, "
             f"남은 실란트 띠 {sealant_band_in_pixels():,} 화소 — "
             f"둘 다 {PIXELS_PER_FEATURE} 화소 기준 위다."),
        ),
        parts=tuple(parts))


def window_unit() -> Unit:
    """롤러 창 · 스캔선 — 실제 단면 그대로, 배율만 키운다."""
    mag = WINDOW_MAG
    parts = _roller_parts("wn", 3, mag)
    win = roller_window_mm() * mag
    parts.append(Part(
        "wnglass", "패널 하면", 1, "box",
        (PANEL_W_MM / 3.0, 3.2 * mag, WINDOW_SPAN_MM * mag),
        (0.0, 3.2 * mag / 2.0, 0.0), "유리 3.2 + EVA + 백시트",
        role=f"롤러 두 개의 꼭대기에 걸쳐 있다 — 받침 사이는 피치 "
             f"{unsupported_span_mm():.0f} mm 이고, 그중 창으로 보이는 것이 "
             f"{roller_window_mm():.0f} mm 다.",
        color="glass", explode=(0.0, 400.0, 0.0),
        spec=f"받침 없는 거리 {unsupported_span_mm():.0f} mm"))
    parts.append(Part(
        "wnline", "스캔선", 1, "box",
        (PANEL_W_MM / 3.0, 2.0, RESOLUTION_MM * mag),
        (0.0, -1.0, 0.0), "—",
        role=f"폭이 화소 하나 {RESOLUTION_MM} mm 다. 창 "
             f"{roller_window_mm():.0f} mm 의 "
             f"{RESOLUTION_MM / roller_window_mm() * 100:.2f} % 라 "
             f"자리를 다투지 않는다 — 창이 좁아서 막히는 것이 아니다.",
        color="amber", explode=(0.0, -120.0, 0.0),
        spec=f"폭 {RESOLUTION_MM} mm ({RESOLUTION_MM * 1000:.0f} µm)"))
    parts.append(Part(
        "wndof", "심도 포락선", 1, "box",
        (PANEL_W_MM / 3.0, depth_of_field_mm(cameras_below()) * mag,
         RESOLUTION_MM * mag * 8.0),
        (0.0, -depth_of_field_mm(cameras_below()) * mag / 2.0, 0.0), "—",
        role=f"이 두께 안이면 초점이 산다 — "
             f"{depth_of_field_mm(cameras_below())} mm. 통과 중 판이 뜨고 처지는 "
             f"{PANEL_BOW_MM} mm 가 그 안이다.",
        color="cyan", explode=(0.0, -260.0, 0.0),
        spec=f"DOF {depth_of_field_mm(cameras_below())} mm ≥ 휨 {PANEL_BOW_MM} mm"))
    return Unit(
        key="window", name=f"롤러 창 · 스캔선 ({mag:.0f} 배)",
        sheet="PV-GI-303-DTL-5301",
        envelope_mm=(PANEL_W_MM / 3.0, 400.0 * mag, WINDOW_SPAN_MM * mag),
        view_r_mm=WINDOW_SPAN_MM * mag,
        principle=(
            ("① 창 150 은 넉넉하다",
             f"스캔선 폭이 {RESOLUTION_MM} mm 라 창의 "
             f"{RESOLUTION_MM / roller_window_mm() * 100:.2f} % 다. "
             f"**막는 것은 창의 폭이 아니라 밑의 높이다.**"),
            ("② 받침 사이는 창보다 넓다",
             f"판은 롤러 꼭대기 한 줄에만 닿으므로 받침 사이가 피치 "
             f"{unsupported_span_mm():.0f} mm 다 — 창 {roller_window_mm():.0f} 보다 "
             f"넓다. 그 처짐이 심도 안인지는 `gi_plate` 가 답한다."),
            ("③ 배율은 그림에만 있다",
             f"단면은 실제 값 그대로이고 화면에서만 {mag:.0f} 배로 세운다 — "
             f"창 {roller_window_mm():.0f} mm 와 화소 {RESOLUTION_MM} mm 는 "
             f"{PANEL_W_MM:.0f} 옆에서 안 보이기 때문이다."),
        ),
        parts=tuple(parts))


def units() -> tuple[Unit, ...]:
    return (below_unit(), above_unit(), window_unit())


#: 유닛별 기본 시점 — 무엇을 보여 주려는 그림인가가 정한다.
VIEW_DIR: dict[str, tuple[float, float, float]] = {
    "below": (0.55, -0.45, 1.0),     # 밑에서 올려다본다 — 스택이 보여야 한다
    "above": (0.55, 0.42, 1.0),
    "window": (0.25, 0.16, 1.0),     # 창을 옆에서 — 스캔선이 선으로 보이게
}


def summary() -> dict[str, object]:
    n = cameras_below()
    return {
        "keptHeads": list(kept_heads()),
        "resolutionMm": RESOLUTION_MM,
        "transportMmS": TRANSPORT_MM_S,
        "lineRateHz": line_rate_hz(),
        "linePeriodUs": line_period_us(),
        "exposureUs": exposure_us(),
        "exposureVsAreaCamera": exposure_vs_area_camera(),
        "pixelsNeeded": pixels_needed(),
        "sensorWidthMm": sensor_width_mm(),
        "camerasBelow": n,
        "camerasAbove": cameras_above(),
        "singleCameraPossible": single_camera_is_possible(),
        "oneCameraNeedsMm": one_camera_would_need_mm(),
        "shortfallMm": single_camera_shortfall_mm(),
        "workingDistanceMm": working_distance_mm(n),
        "stackHeightMm": stack_height_mm(n),
        "belowDeckMm": BELOW_DECK_MM,
        "depthOfFieldMm": depth_of_field_mm(n),
        "coversBow": depth_covers_the_bow(n),
        "rollerWindowMm": roller_window_mm(),
        "fieldWidthMm": field_width_mm(n),
        "seamOverlapEachMm": seam_overlap_each_mm(n),
        "seamOverlapTotalMm": seam_overlap_mm(n),
        "smallestFeatureMm": smallest_reliable_feature_mm(),
        "sealantBandPx": sealant_band_in_pixels(),
        "arrisPx": arris_in_pixels(),
        "arrisMeasurable": arris_is_measurable(),
        "mbPerPanel": mb_per_panel(),
        "pixelRateMpxS": pixel_rate_mpx_s(),
        "scanTimeS": scan_time_s(),
        "duty": duty(),
        "fitsTakt": fits_the_takt(),
        "openQuestions": [list(q) for q in open_questions()],
    }
