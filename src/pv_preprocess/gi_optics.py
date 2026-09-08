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
    """스캔 창 위에서 유리가 받쳐지지 않는 거리 (mm)."""
    return roller_window_mm()


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
