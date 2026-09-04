"""AFR-101 프레임 제거 기구의 3D 블록을 afr.py 에서 생성한다.

발주처가 설명한 기구 — 위에서 내려오는 정반, 정반 **안**의 실린더, 실린더 둘을
묶는 쇠막대, 밀려난 프레임을 세우는 스토퍼, 정반의 긴 홈으로 올라오는 톱니
컨베이어, 장변 홈에 걸려 바깥으로 당기며 LM 을 타는 롤러 — 를 그린다.

치수는 하나도 여기서 정하지 않는다. 전부 `pv_preprocess.afr` 에서 읽는다.
도면을 고치려면 모델을 고치고 이 도구를 다시 돌린다.

    PYTHONPATH=src python tools/build_afr.py
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pv_preprocess import afr, frames, kinematics  # noqa: E402

DRAWING = pathlib.Path(__file__).resolve().parent.parent / "docs/drawings/pv-preprocess-plant.html"

# ── 3D 좌표계 (AFR 셀 로컬, m) ───────────────────────────────────────────
# 패널 상면·하면은 기존 씬에 이미 있는 값이다. 여기에 기구를 맞춘다.
PANEL_Y = 1.145
PANEL_T = 0.055
PANEL_TOP = PANEL_Y + PANEL_T / 2          # 1.1725
PANEL_BOT = PANEL_Y - PANEL_T / 2          # 1.1175
FRAME_T = afr.FRAME_H_MM / 1000.0          # 0.075
FRAME_Y = PANEL_TOP - FRAME_T / 2          # 윗면이 유리면과 같은 높이다

HALF_X = kinematics.PANEL_MM[0] / 2000.0   # 1.25
HALF_Z = kinematics.PANEL_MM[1] / 2000.0   # 0.70
FW = afr.FRAME_W_MM / 1000.0               # 0.075

M = lambda v: v / 1000.0                   # noqa: E731  mm → m


def _f(v: float, nd: int = 4) -> str:
    """JS 리터럴 — 불필요한 0 을 지운다."""
    t = f"{round(v, nd):.{nd}f}".rstrip("0").rstrip(".")
    if t in ("", "-"):
        return "0"
    return t.replace("0.", ".").replace("-0.", "-.") if t.startswith(("0.", "-0.")) else t


def build_block() -> str:
    a = afr
    platen_x = M(a.PLATEN_X_MM)             # .6
    platen_t = M(a.PLATEN_T_MM)             # .1
    platen_z = M(a.PLATEN_Z_MM)             # 1.4
    bar_w = M(a.BAR_W_MM)                   # .06
    bar_h = M(a.bar_h_mm())                 # .125

    frame_in = HALF_X - FW                  # 1.175  단변 프레임 안쪽면
    bar_cx = frame_in - bar_w / 2           # 1.145  쇠막대 중심
    platen_out = bar_cx - bar_w / 2         # 1.115  정반 바깥면
    platen_cx = platen_out - platen_x / 2   # .815   정반 중심
    platen_dy = PANEL_TOP + platen_t / 2    # 1.2225 정반 중심(내림)
    lift = M(a.platen_lift_mm())            # .1

    cyl_r = M(a.barrel_od_mm()) / 2         # .0395
    rod_r = M(a.rod_mm()) / 2               # .018
    cyl_len = 0.30
    cyl_cx = platen_cx - platen_x / 2 + cyl_len / 2
    cyl_z = M(a.cylinder_span_mm()) / 2     # .65
    rod_len = 0.45
    push = M(a.push_travel_mm())            # .12

    stop_face = M(a.stopper_face_mm())      # 1.37
    stop_t = M(a.STOPPER_T_MM)              # .06
    stop_z = M(a.STOPPER_Z_MM)              # .25
    lip = M(a.STOPPER_LIP_MM)               # .025
    beam_x = 1.37

    pad_t = M(a.SUPPORT_PAD_T_MM)
    pad_y = PANEL_BOT - pad_t / 2           # 1.0825
    pad_x = M(a.SUPPORT_PAD_X_MM)
    half_pad = M(a.split_pad_depth_mm())
    pad_off = M(a.split_pad_z_mm())
    rows = [M(z) for z in a.support_rows_z_mm()]
    cols = [M(x) for x in a.SUPPORT_COLS_X_MM]

    bed_t = 0.06
    bed_y = pad_y - pad_t / 2 - bed_t / 2   # 0.9875 …
    bed_x = 2.6
    bed_half = 0.90
    slot_h = M(a.SLOT_W_MM) / 2
    edges = [-bed_half]
    for z in rows:
        edges += [z - slot_h, z + slot_h]
    edges += [bed_half]
    bands = [(edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2)]

    spr_r = M(a.sprocket_pitch_d_mm()) / 2  # .0346
    chain_top = PANEL_BOT - M(a.CHAIN_PARK_MM)
    spr_y = chain_top - spr_r
    rise = M(a.chain_rise_mm())
    slot_l = M(a.SLOT_L_MM)

    groove_d = M(a.GROOVE_D_MM)
    groove_h = M(a.GROOVE_H_MM)
    roll_r = M(a.roller_d_mm()) / 2
    roll_h = M(a.roller_h_mm())
    n_roll = a.rollers_per_carriage()
    rail_z = M(a.LM_RAIL_Z_MM)              # .98
    groove_z = M(a.roller_axis_z_mm())      # 롤러 축 — 홈 바닥에 닿은 자리
    park_z = HALF_Z + M(a.pull_travel_mm())  # 당김 종료면 밖에서 대기
    pull = M(a.pull_travel_mm())            # .12

    long_cz = HALF_Z - FW / 2               # .6625
    short_cx = HALF_X - FW / 2              # 1.2125
    n_short, n_long = 6, 10
    short_seg = (2 * HALF_Z) / n_short
    long_seg = (2 * HALF_X) / n_long

    bow_long = M(a.display_bow_mm())
    bow_short = M(a.short_edge_display_bow_mm())

    lm_end = 0.16 + 0.02                    # 캐리지 반길이 + 두 대가 만나는 틈
    lm_start = lm_end + M(a.LM_STROKE_MM)

    q = _f
    out: list[str] = []
    A = out.append

    # ── 12구역 지지 — 홈이 패드를 앞뒤로 가른다 ──────────────────────────
    A(f'var Pu=[];for(let i=0;i<{len(rows)};i+=1)for(let e=0;e<{len(cols)};e+=1){{'
      f'let rz=[{",".join(q(z) for z in rows)}][i],cx=[{",".join(q(x) for x in cols)}][e],'
      f'lab=i===0&&e===0?"AFR SU-211 {a.support_zones()}구역 지지":null,'
      f'tip="{a.support_zones()}구역이 2,500×1,400 접촉맵을 물리 지지하고 인출 반력을 분산합니다. '
      f'구역마다 긴 홈이 지나가 패드를 앞뒤로 가르고, 그 홈으로 톱니 컨베이어가 올라옵니다.",'
      f'pa=P(ot,[{q(pad_x)},{q(pad_t)},{q(half_pad)}],[cx,{q(pad_y)},rz-{q(pad_off)}],M.dark,lab,tip),'
      f'pb=P(ot,[{q(pad_x)},{q(pad_t)},{q(half_pad)}],[cx,{q(pad_y)},rz+{q(pad_off)}],M.dark);'
      f'Pu.push({{pad:pa,phase:i*{len(cols)}+e}}),Pu.push({{pad:pb,phase:i*{len(cols)}+e}})}}')

    # ── 지지 정반 — 긴 홈이 관통한 판 ────────────────────────────────────
    A(f'[{",".join("[" + q((lo + hi) / 2) + "," + q(hi - lo) + "]" for lo, hi in bands)}]'
      f'.forEach(function(b,k){{P(ot,[{q(bed_x)},{q(bed_t)},b[1]],[0,{q(bed_y)},b[0]],Qt,'
      f'k===0?"AFR SU-211 지지 정반 (긴 홈 {a.chain_runs()}열)":null,'
      f'"{a.SLOT_W_MM} mm 폭 × {a.SLOT_L_MM:,} mm 길이의 홈 {a.chain_runs()}열이 판을 관통합니다 — '
      f'프레임이 다 빠지면 이 홈으로 톱니 컨베이어가 아래에서 올라와 패널을 받아 나갑니다.")}});')

    # ── 톱니 컨베이어 — 홈 아래에서 올라온다 ─────────────────────────────
    A('var pvAfrChain=new ce;ot.add(pvAfrChain);var pvAfrSpr=[];')
    A(f'[{",".join(q(z) for z in rows)}].forEach(function(cz,k){{'
      f'[-{q(slot_l / 2)},{q(slot_l / 2)}].forEach(function(sx){{'
      f'pvAfrSpr.push(Ee(pvAfrChain,{q(spr_r)},{q(2 * roll_h)},[sx,{q(spr_y)},cz],M.steel,'
      f'k===0&&sx<0?"AFR TC-231 톱니 컨베이어 스프로킷":null,'
      f'"ISO 08B-1 피치 {a.CHAIN_PITCH_MM} mm · {a.SPROCKET_TEETH} 잇 · 피치원 Ø{a.sprocket_pitch_d_mm()} mm. '
      f'{a.chain_runs()} 열이 동일 축에 물려 패널을 {a.CHAIN_LIFT_MM} mm 들어 올린 뒤 '
      f'{a.CHAIN_SPEED_MM_S:.0f} mm/s 로 반출합니다.",[Math.PI/2,0,0]))}});'
      f'P(pvAfrChain,[{q(slot_l)},{q(2 * roll_r)},{q(2 * roll_h)}],[0,{q(chain_top - roll_r)},cz],M.dark,null);'
      f'for(let t=0;t<12;t+=1)P(pvAfrChain,[.03,.03,{q(2 * roll_h + 0.01)}],'
      f'[-{q(slot_l / 2)}+t*{q(slot_l / 11)},{q(chain_top + 0.012)},cz],M.orange,null)}});')
    A(f'P(pvAfrChain,[.22,.3,.26],[{q(slot_l / 2 + 0.18)},{q(spr_y - 0.02)},{q(rows[-1])}],M.dark,'
      f'"AFR TC-231 체인 구동·승강 유닛","3 열 공통 축을 한 모터가 돌리고, 승강 실린더가 홈 밑에서 '
      f'{a.chain_rise_mm()} mm 올려 패널을 지지패드에서 넘겨받습니다.");')

    # ── 정렬 스토퍼 (기존) ────────────────────────────────────────────────
    A(f'var p0=[];[[-1,-{q(0.66)}],[-1,{q(0.66)}],[1,-{q(0.66)}],[1,{q(0.66)}]]'
      f'.forEach(([sx,cz],t)=>p0.push(P(ot,[.12,.34,.14],[sx*{q(stop_face + 0.08)},1.13,cz],M.orange,'
      f't===0?"AFR 양방향 포지티브 스토퍼":null,'
      f'"패널 모서리를 물어 위치·직각도를 확정하고, 단변을 밀기 전에 밀려날 프레임 자리 밖으로 물러납니다.")));')

    # ── 프레임 스토퍼 — 밀려난 단변이 여기 걸려 선다 ─────────────────────
    A(f'[-1,1].forEach(function(sx){{'
      f'P(ot,[{q(2 * bar_w / 3)},{q(bed_t * 2)},2.42],[sx*{q(beam_x)},{q(bed_y + 0.03)},0],M.frame,'
      f'sx<0?"AFR ST-241 스토퍼 지지빔":null,"프레임 스토퍼와 정렬 스토퍼를 함께 받는 빔 — '
      f'베이스 프레임 위에 기둥 둘로 섭니다.");'
      f'[-1.18,1.18].forEach(function(cz){{P(ot,[.09,.52,.16],[sx*{q(beam_x)},.71,cz],M.frame,null)}});'
      f'[-{q(stop_z)},{q(stop_z)}].forEach(function(cz,k){{'
      f'P(ot,[{q(stop_t)},{q(FRAME_T + 0.02)},.18],[sx*{q(stop_face + stop_t / 2)},{q(FRAME_Y)},cz],M.orange,'
      f'k===0&&sx<0?"AFR ST-241 프레임 스토퍼":null,'
      f'"실린더가 쇠막대로 밀어낸 단변 알루미늄이 {a.push_travel_mm()} mm 나와 이 면에 걸려 섭니다 — '
      f'행정 {a.CYL_STROKE_MM} mm 중 {a.stroke_spare_mm()} mm 가 남아 스토퍼가 하드스톱이 아니라 정지면입니다. '
      f'위 립 {a.STOPPER_LIP_MM} mm 가 프레임이 타고 넘는 것을 막습니다.");'
      f'P(ot,[{q(stop_t * 0.8)},{q(lip)},.18],[sx*{q(stop_face + stop_t / 2 - 0.006)},'
      f'{q(FRAME_Y + FRAME_T / 2 + lip / 2)},cz],M.orange,null);'
      f'P(ot,[.1,{q(FRAME_Y - bed_y - 0.09)},.16],[sx*{q(stop_face + stop_t / 2)},'
      f'{q((FRAME_Y + bed_y + 0.09) / 2)},cz],M.steel,null)}})}});')

    # ── 4점 클램프 — 정반을 매달고 누른다 ────────────────────────────────
    A(f'var Lu=[],pvAfrPlaten=[],pvAfrBar=[],pvAfrRod=[];')
    A(f'[[-.92,-.58],[-.92,.58],[.92,-.58],[.92,.58]]'
      f'.forEach(([cx,cz],t)=>{{let n=new ce;n.position.set(cx,0,cz),ot.add(n);'
      f'P(n,[.18,.5,.18],[0,1.7,0],Qt,t===0?"AFR CL-221 상부 클램프":null,'
      f'"로드셀 폐루프로 각 {kinematics.AFR_CLAMP_KN:.0f} kN 을 인가합니다. 정반 1매 {a.platen_mass_kg():.0f} kg '
      f'({a.platen_weight_kn():.2f} kN) 를 클램프 둘이 매달므로 패널에 남는 순 압착력은 '
      f'{a.clamp_net_kn():.2f} kN 입니다 — 통짜 정반이면 {a.platen_solid_mass_kg():.0f} kg 이라 '
      f'클램프가 자기 무게도 못 듭니다. 리브 웰드먼트로 강재 점유율 {a.platen_steel_fraction() * 100:.0f} % 입니다.");'
      f'let s=P(n,[.42,.12,.18],[.13,1.85,0],M.orange),r=P(n,[.28,.08,.22],[.28,1.58,0],M.rubber);'
      f'Lu.push({{group:n,arm:s,pad:r}})}});')

    # ── 정반 · 실린더 · 쇠막대 ───────────────────────────────────────────
    A(f'[-1,1].forEach(function(sx){{var pl=new ce;pl.position.set(sx*{q(platen_cx)},{q(platen_dy)},0);'
      f'ot.add(pl),pvAfrPlaten.push(pl);'
      f'P(pl,[{q(platen_x)},{q(platen_t)},{q(platen_z)}],[0,0,0],M.steel,'
      f'sx<0?"AFR PL-251 패널 고정 정반":null,'
      f'"{a.PLATEN_X_MM} × {a.PLATEN_Z_MM} × 두께 {a.PLATEN_T_MM} mm 리브 웰드먼트가 위에서 내려와 패널을 고정합니다. '
      f'행정 {a.platen_lift_mm()} mm · {a.PLATEN_SPEED_MM_S:.0f} mm/s · 1매 {a.platen_mass_kg():.0f} kg. '
      f'실린더 {a.CYL_PER_PLATEN} 본이 이 판 **안**에 들어갑니다.");'
      f'[-1,1].forEach(function(k){{'
      f'P(pl,[{q(platen_x - 0.06)},{q(platen_t - 2 * M(a.PLATEN_SKIN_T_MM))},{q(M(a.PLATEN_RIB_T_MM))}],'
      f'[0,0,k*{q(platen_z / 4)}],M.steel,null)}});'
      f'[-.58,.58].forEach(function(cz){{P(pl,[.09,.4,.09],'
      f'[sx*{q(0.92 - platen_cx)},{q(0.2 + platen_t / 2)},cz],M.steel,null)}});'
      f'[-{q(cyl_z)},{q(cyl_z)}].forEach(function(cz,k){{'
      f'Ee(pl,{q(cyl_r)},{q(cyl_len)},[{q(cyl_cx - platen_cx)},0,cz],M.dark,'
      f'k===0&&sx<0?"AFR SA-301 단축 인출 실린더":null,'
      f'"{a.cylinder_spec()}. 정반 두께 {a.PLATEN_T_MM} mm 가 보어를 정합니다 — 배럴 Ø{a.barrel_od_mm()} 에 '
      f'포켓 여유를 더하면 위아래 살이 {a.platen_wall_mm()} mm 남습니다 (최소 {a.MIN_PLATEN_WALL_MM}). '
      f'릴리프 {a.HPU_RELIEF_BAR:.0f} bar 에서 정반당 {a.relief_capacity_kn()} kN 이 나오고, '
      f'필요한 {a.required_push_kn():.0f} kN 은 {a.working_pressure_bar():.0f} bar 로 냅니다. '
      f'정반 끝에서 안쪽 {a.CYL_INSET_MM} mm 자리이며, 두 본이 하나의 쇠막대에 물립니다.",'
      f'[0,0,Math.PI/2])}});'
      f'var bg=new ce;bg.position.set(sx*{q(bar_cx - platen_cx)},0,0);pl.add(bg);'
      f'pvAfrBar.push({{group:bg,sign:sx}});'
      f'P(bg,[{q(bar_w)},{q(bar_h)},{q(platen_z)}],[0,{q(FRAME_Y - FRAME_T / 2 + bar_h / 2 - platen_dy)},0],M.orange,'
      f'sx<0?"AFR PB-261 쇠막대":null,'
      f'"{a.BAR_W_MM} × {a.bar_h_mm()} × {a.bar_length_mm():,} mm S355 · {a.bar_mass_kg()} kg. '
      f'실린더 두 본이 양끝에서 {a.CYL_INSET_MM} mm 들어온 자리를 밀고, 막대 전체가 단변 알루미늄을 '
      f'한 몸으로 밀어냅니다. 스팬 {a.cylinder_span_mm():,} mm 등분포에서 굽힘 {a.bar_stress_mpa()} MPa '
      f'(허용 {a.STEEL_ALLOW_MPA:.0f}) · 중앙 처짐 {a.bar_sag_mm()} mm (한도 {a.bar_sag_limit_mm()}) — '
      f'이 처짐이 그대로 단변 가운데가 뒤처지는 양입니다.");'
      f'[-{q(cyl_z)},{q(cyl_z)}].forEach(function(cz){{'
      f'pvAfrRod.push(Ee(bg,{q(rod_r)},{q(rod_len)},'
      f'[-sx*{q(bar_w / 2 + rod_len / 2)},0,cz],M.orange,null,null,[0,0,Math.PI/2]))}});}});')
    # ── 패널과 프레임 ────────────────────────────────────────────────────
    A('var Cs=new ce;ot.add(Cs);')
    A(f'var iM=P(Cs,[{q(2 * HALF_X)},{q(PANEL_T)},{q(2 * HALF_Z)}],[0,{q(PANEL_Y)},0],h0,'
      f'"JBR 완료 패널 · JBOX 제거상태",'
      f'"{kinematics.PANEL_MM[0]:,}×{kinematics.PANEL_MM[1]:,} mm 최대규격이며 유리면 아래·백시트 위, '
      f'정션박스와 케이블 제거 완료 상태로만 AFR 에 진입합니다."),m0=[];')
    A(f'[-1,1].forEach(i=>{{for(let k=0;k<{n_short};k+=1){{'
      f'let z=-{q(HALF_Z - short_seg / 2)}+k*{q(short_seg)},'
      f'e=P(Cs,[{q(FW)},{q(FRAME_T)},{q(short_seg)}],[i*{q(short_cx)},{q(FRAME_Y)},z],Xo,'
      f'i<0&&k===0?"AFR 단축 알루미늄 프레임":null,'
      f'"정반 안의 실린더 {a.CYL_PER_PLATEN} 본이 쇠막대를 통해 이 변 전체를 한 번에 '
      f'{a.push_travel_mm()} mm 밀어내고, 스토퍼가 받아 세웁니다. 막대 중앙 처짐 {a.bar_sag_mm()} mm 만큼 '
      f'가운데가 뒤처지며(화면에서는 {frames.DISPLAY_EXAGGERATION:.0f}배 과장), 떨어지면 복원합니다.");'
      f'e.userData.baseX=i*{q(short_cx)},e.userData.sign=i,'
      f'e.userData.bowT=1-Math.pow(z/{q(HALF_Z - short_seg / 2)},2),m0.push(e)}}}});')
    A(f'var g0=[];[-1,1].forEach(i=>{{for(let e=0;e<{n_long};e+=1){{'
      f'let t=-{q(HALF_X - long_seg / 2)}+e*{q(long_seg)},'
      f'n=P(Cs,[{q(long_seg)},{q(FRAME_T)},{q(FW)}],[t,{q(FRAME_Y)},i*{q(long_cz)}],Xo,'
      f'i<0&&e===0?"AFR 장축 알루미늄 프레임":null,'
      f'"바깥면 홈({a.GROOVE_H_MM}×{a.GROOVE_D_MM} mm)에 롤러가 들어가 걸치고 {a.pull_travel_mm()} mm 바깥으로 '
      f'당기면서 LM 가이드를 {a.LM_STROKE_MM:,} mm 탑니다. 롤러가 접착 전선과 같이 가므로 자유 길이가 '
      f'롤러 반경 {a.roller_free_length_mm()} mm 뿐이고, 남는 것은 이미 떨어진 {a.released_length_mm():.0f} mm 의 '
      f'자중 처짐 {a.self_weight_sag_mm()} mm 입니다 — 휘지 않고 직선으로 떨어집니다.");'
      f'P(n,[{q(long_seg)},{q(groove_h)},{q(groove_d)}],[0,0,i*{q(HALF_Z - groove_d / 2 - long_cz)}],M.dark,'
      f'i<0&&e===0?"AFR 장축 압출재 인발 홈":null,'
      f'"롤러 Ø{a.roller_d_mm()} × 높이 {a.roller_h_mm()} mm 가 여기 들어가 걸칩니다. '
      f'캐리지당 {n_roll} 개로 나눠 받아 접촉압 {a.roller_contact_mpa()} MPa — '
      f'구름 항복 {a.rolling_yield_mpa()} MPa 에 설계계수 {a.ROLLER_DESIGN_FACTOR} 를 얹은 '
      f'{a.roller_allow_mpa()} MPa 아래라 홈에 압흔이 남지 않습니다.");'
      f'n.userData.baseX=t,n.userData.baseZ=i*{q(long_cz)},n.userData.sign=i,'
      f'n.userData.pullAt=Math.min(({q(lm_start)}-Math.abs(t))/{q(M(a.LM_STROKE_MM))},.96),'
      f'n.userData.edgeOrder=1-Math.abs(t)/{q(HALF_X - long_seg / 2)},g0.push(n)}}}});')

    # ── LM 인발 캐리지 — 롤러가 홈에 들어가 바깥으로 당긴다 ──────────────
    A(f'var Du=[],pvAfrHead=[];[-1,1].forEach(i=>{{'
      f'P(ot,[2.9,.08,.12],[0,1,i*{q(rail_z)}],M.steel,i<0?"AFR LA-401 35급 듀얼 LM레일":null,'
      f'"장변 한 변에 캐리지 {a.CARRIAGE_PER_SIDE} 대가 양끝에서 중앙으로 {a.LM_STROKE_MM:,} mm 를 '
      f'{a.LM_SPEED_MM_S:.0f} mm/s 로 주행하며 계속 당깁니다.");'
      f'[-1,1].forEach(e=>{{let t=new ce;t.position.set(e*{q(lm_start)},1.28,i*{q(rail_z)});ot.add(t);'
      f'P(t,[.32,.18,.26],[0,0,0],M.orange,i<0&&e<0?"AFR LA-401 장축 인발 캐리지":null,'
      f'"롤러가 장변 압출재 홈으로 들어가 걸친 뒤 {a.pull_travel_mm()} mm 바깥으로 당기고, 그 상태로 '
      f'LM 가이드를 타고 이동하며 계속 당깁니다. 양쪽에서 같이 당기므로 프레임이 휘지 않습니다.");'
      f'P(t,[.34,.06,.3],[0,-.1,0],M.dark,null);'
      f'let hd=new ce;hd.position.set(0,{q(FRAME_Y - 1.28)},{q(park_z - rail_z)}*i),t.add(hd);'
      f'P(hd,[.09,.09,.3],[0,0,i*.16],M.steel,null);'
      f'P(hd,[{q(2 * roll_r * n_roll + 0.06)},{q(roll_h - 0.004)},.05],[0,0,i*.03],M.dark,null);'
      f'for(let r=0;r<{n_roll};r+=1)Ee(hd,{q(roll_r)},{q(roll_h)},'
      f'[(r-{q((n_roll - 1) / 2)})*{q(2 * roll_r + 0.012)},0,0],M.orange,'
      f'r===0&&i<0&&e<0?"AFR LA-401 홈 인발 롤러 ×{n_roll}":null,'
      f'"Ø{a.roller_d_mm()} × {a.roller_h_mm()} mm 경화강 롤러 {n_roll} 개가 홈 벽을 굴러 '
      f'{frames.PEEL_FORCE_N:.0f} N 을 나눠 받습니다 — 하나로 받으면 알루미늄에 압흔이 남습니다.");'
      f'pvAfrHead.push({{head:hd,zSign:i}}),Du.push({{carriage:t,xSign:e,zSign:i}})}})}});')

    return "".join(out)


def build_anim() -> str:
    a = afr
    push = M(a.push_travel_mm())
    pull = M(a.pull_travel_mm())
    lift = M(a.platen_lift_mm())
    rise = M(a.chain_rise_mm())
    bow_long = M(a.display_bow_mm())
    bow_short = M(a.short_edge_display_bow_mm())
    platen_dy = PANEL_TOP + M(a.PLATEN_T_MM) / 2
    bar_local = (HALF_X - FW - M(a.BAR_W_MM) / 2) - (
        HALF_X - FW - M(a.BAR_W_MM) - M(a.PLATEN_X_MM) / 2)
    rail_z = M(a.LM_RAIL_Z_MM)
    groove_z = M(a.roller_axis_z_mm())
    park_z = HALF_Z + M(a.pull_travel_mm())
    stop_open = M(a.stopper_face_mm()) + 0.08
    stop_shut = HALF_X + 0.06
    lm_end = 0.16 + 0.02
    lm_start = lm_end + M(a.LM_STROKE_MM)

    # 각 동작이 자기 사양속도로 끝나고 창 안에서 대기한다 — 택트는 안 건드린다.
    t_push = 10.3 + a.push_time_s()
    t_lm = 21.2 + a.lm_travel_time_s()
    t_drop = t_lm + 1.0            # 장변이 슈트로 떨어지는 시간
    t_up = t_drop + a.platen_descent_time_s()
    t_rise = t_up + a.chain_rise_time_s()

    q = _f
    o: list[str] = []
    A = o.append
    A('w0(r);')
    A(f'let PD=me(Se(l,7.5,9.5)),PS=me(Se(l,10.3,{q(t_push, 3)})),'
      f'PU=me(Se(l,{q(t_drop, 3)},{q(t_up, 3)})),CH=me(Se(l,{q(t_up, 3)},{q(t_rise, 3)})),'
      f'PJ=me(Se(l,20.4,21.2)),PW=me(Se(l,21.2,{q(t_lm, 3)})),PF=me(Se(l,{q(t_lm, 3)},{q(t_drop, 3)})),'
      f'EN=$t((PW*{q(M(a.LM_STROKE_MM))}-{q(lm_start - HALF_X)})/.1),'
      f'PR=me(Se(l,20.4,{q(20.4 + a.retract_time_s(), 3)})),'
      f'PB=me(Se(l,{q(t_drop, 3)},{q(t_up, 3)}));')
    A('let K=g*(1-N);')
    A('Lu.forEach(({arm:V,pad:ae},ie)=>{let De=K>.95?Math.sin(l*8+ie)*.003:0;'
      'V.position.y=le(1.85,1.52,K)+De,ae.position.y=le(1.58,1.27,K)+De}),')
    A(f'pvAfrPlaten.forEach(V=>{{V.position.y=le({q(platen_dy + lift)},{q(platen_dy)},PD)+{q(lift)}*PU}}),')
    A(f'p0.forEach((V,ae)=>{{let ie=me(Se(l,4.8,7.2))*(1-me(Se(l,9.4,9.9)));'
      f'V.position.x=(ae<2?-1:1)*le({q(stop_open)},{q(stop_shut)},ie)}}),')
    A('Pu.forEach(({pad:V,phase:ae})=>{let ie=K*(.003+Math.sin(ae*1.47)*.0014);'
      f'V.position.y={q(PANEL_BOT - M(a.SUPPORT_PAD_T_MM) / 2)}+ie}}),')
    A(f'pvAfrBar.forEach(({{group:V,sign:ae}})=>{{'
      f'V.position.x=ae*({q(bar_local)}+{q(push)}*(PS-PR))}}),')

    A(f'm0.forEach(V=>{{V.visible=te&&(o||l<20.4);'
      f'V.position.x=V.userData.baseX+V.userData.sign*({q(push)}*PS-{q(bow_short)}*V.userData.bowT*4*PS*(1-PS));'
      f'V.position.y={q(FRAME_Y)}-.72*p,V.rotation.z=V.userData.sign*p*.16}}),')
    A(f'Qh.visible=a&&l>=19.5,Qh.scale.y=le(.2,1,p),')
    A(f'pvAfrHead.forEach(({{head:V,zSign:ae}})=>{{'
      f'let pz=le({q(park_z)},{q(groove_z)},PJ*(1-PB))+{q(pull)}*EN*(1-PB);'
      f'V.position.z=ae*(pz-{q(rail_z)})}}),')
    A(f'g0.forEach(V=>{{let ae=me($t((PW-V.userData.pullAt)/.08)),bw={q(bow_long)}*4*ae*(1-ae);'
      f'V.visible=te&&(o||l<{q(t_drop + 0.2, 3)});'
      f'V.position.z=V.userData.baseZ+V.userData.sign*({q(pull)}*ae+bw);'
      f'V.position.y={q(FRAME_Y)}-.72*PF*ae+bw*.35;'
      f'V.rotation.x=V.userData.sign*(PF*ae*.12+bw*1.6)}}),')
    A(f'Du.forEach(({{carriage:V,xSign:ae,zSign:ie}})=>{{'
      f'V.position.x=ae*le({q(lm_start)},{q(lm_end)},PW*(1-PB));V.visible=a}}),')
    A(f'Cs.position.y={q(M(a.CHAIN_LIFT_MM))}*$t((CH-{q(a.CHAIN_PARK_MM / a.chain_rise_mm())})'
      f'/{q(a.CHAIN_LIFT_MM / a.chain_rise_mm())}),'
      f'pvAfrChain.position.y={q(rise)}*CH,pvAfrChain.visible=a||o,'
      f'pvAfrSpr.forEach(V=>{{V.rotation.z=CH>=1?-l*4:0}}),')
    A('eu.visible=a&&l>=31.2,eu.scale.y=le(.2,1,x);')
    return "".join(o)


#: 씬이 밖으로 내보내는 시험 훅 — 여기 값도 모델에서 나온다.
HOOK_OLD = ("afrSupportZoneCount:Pu.length,afrClampCount:Lu.length,"
            "afrShortAxisCount:Iu.length,afrLongCarriageCount:Du.length,")


def build_hook() -> str:
    a = afr
    return (f"afrSupportZoneCount:Pu.length/2,afrClampCount:Lu.length,"
            f"afrShortAxisCount:pvAfrPlaten.length,afrLongCarriageCount:Du.length,"
            f"afrPlatenMm:[{a.PLATEN_X_MM},{a.PLATEN_Z_MM},{a.PLATEN_T_MM}],"
            f"afrPlatenCount:pvAfrPlaten.length,"
            f"afrShortCylinderCount:pvAfrRod.length,afrShortCylinderBoreMm:{a.bore_mm()},"
            f"afrCylinderInsetMm:{a.CYL_INSET_MM},afrPushBarCount:pvAfrBar.length,"
            f"afrPushTravelMm:{a.push_travel_mm()},afrStopperFaceMm:{a.stopper_face_mm():.0f},"
            f"afrChainRunCount:{a.chain_runs()},afrSlotWidthMm:{a.SLOT_W_MM},"
            f"afrChainLiftMm:{a.CHAIN_LIFT_MM},"
            f"afrGrooveMm:[{a.GROOVE_H_MM},{a.GROOVE_D_MM}],"
            f"afrRollersPerCarriage:{a.rollers_per_carriage()},"
            f"afrPullTravelMm:{a.pull_travel_mm()},")


# ── 도면 본문 문구 — 기구 설명도 모델에서 나온다 ────────────────────────
def phase_names() -> tuple[tuple[str, str], ...]:
    """(시간 앵커, 새 이름). 시간 앵커는 택트라 안 건드린다."""
    a = afr
    return (
        ("7.5,end:9.5",
         f"12구역 지지·정반 하강 {a.platen_lift_mm()} mm·4점 클램프"),
        ("9.5,end:17.8",
         f"정반 내장 실린더 {a.CYL_PER_PLATEN * a.PLATEN_COUNT}본 → 쇠막대 · "
         f"단변 {a.push_travel_mm()} mm 밀어내기"),
        ("17.8,end:20.4", "스토퍼 정지·단축 프레임 회수·쇠막대 복귀"),
        ("20.4,end:28.7319148936",
         f"롤러 홈 진입 · 바깥으로 {a.pull_travel_mm()} mm 당김 · "
         f"LM {a.LM_STROKE_MM:,} mm 주행"),
        ("28.7319148936,end:Lr",
         f"정반 상승·톱니 컨베이어 {a.CHAIN_LIFT_MM} mm 상승 반출"
         "→SG-301→GI-301/302→GBR-301"),
    )


def spec_sentence() -> str:
    a = afr
    return (f"12구역 지지, 4×{kinematics.AFR_CLAMP_KN:.0f} kN 상부클램프"
            f"(정반 {a.PLATEN_COUNT}매 매달림), 단축 정반 "
            f"{a.PLATEN_X_MM}×{a.PLATEN_Z_MM:,}×t{a.PLATEN_T_MM} 안에 {a.cylinder_spec()}, "
            f"쇠막대 {a.BAR_W_MM}×{a.bar_h_mm()}×{a.bar_length_mm():,} mm 로 "
            f"{a.push_travel_mm()} mm 밀어내고 스토퍼 정지, 장축 홈 인발 롤러 "
            f"Ø{a.roller_d_mm()}×{a.roller_h_mm()} ×{a.rollers_per_carriage()}개/캐리지·"
            f"{a.CARRIAGE_PER_SIDE * 2} LM 캐리지·{a.pull_travel_mm()} mm 당김·"
            f"{a.LM_STROKE_MM:,} mm·{a.LM_SPEED_MM_S:.0f} mm/s, 톱니 컨베이어 "
            f"{a.chain_runs()}열 {a.CHAIN_LIFT_MM} mm 상승 반출")


def bom_rows() -> str:
    """부품표(BOM) 의 AFR 기구 행 — 치수·수량·공차가 전부 모델에서 나온다."""
    a = afr
    n_cyl = a.CYL_PER_PLATEN * a.PLATEN_COUNT
    return "".join((
        f'["AFR-SU-211","AFR 지지·클램프","{a.support_zones()}구역 순응 지지대'
        f'(긴 홈 {a.chain_runs()}열 관통)","{a.support_zones()}EA",'
        f'[{a.SUPPORT_PAD_X_MM},{a.SUPPORT_PAD_Z_MM},{a.SUPPORT_PAD_T_MM}],'
        f'"POM-C/STS304/스프링","CNC·조립·하중교정",'
        f'"{a.support_zones()}/{a.support_zones()} 접촉·높이 ±0.10 mm","support",'
        f'"패널 워페이지를 추종하며 인출 반력을 분산한다. 폭 {a.SLOT_W_MM} mm 의 긴 홈이 '
        f'열마다 패드를 앞뒤로 가르고, 프레임이 다 빠지면 그 홈으로 톱니 컨베이어가 올라온다. '
        f'바깥 열은 장변 프레임 안쪽으로 {a.PAD_EDGE_CLEAR_MM} mm 물러나 z ±'
        f'{max(a.support_rows_z_mm())} 에 선다 — 프레임 밑에 깔리면 프레임이 안 빠진다",'
        f'["AFR SU-211 {a.support_zones()}구역 지지","AFR SU-211 지지 정반 (긴 홈 '
        f'{a.chain_runs()}열)"]],'),
    ) + "".join((
        f'["AFR-PL-251","AFR 지지·클램프","패널 고정 정반 (실린더 내장 리브 웰드먼트)",'
        f'"{a.PLATEN_COUNT}EA",[{a.PLATEN_X_MM},{a.PLATEN_Z_MM},{a.PLATEN_T_MM}],'
        f'"S355 리브 웰드먼트 (상하판 t{a.PLATEN_SKIN_T_MM}·리브 t{a.PLATEN_RIB_T_MM}'
        f'@{a.PLATEN_RIB_PITCH_MM})","용접·응력제거·평면가공·포켓보링",'
        f'"승강 {a.platen_lift_mm()} mm·{a.PLATEN_SPEED_MM_S:.0f} mm/s·1매 '
        f'{a.platen_mass_kg():.0f} kg","clamp",'
        f'"위에서 내려와 단변마다 패널을 고정한다. 인출 실린더 {a.CYL_PER_PLATEN} 본이 이 판 '
        f'**안**에 들어가므로 두께 {a.PLATEN_T_MM} 이 보어를 정한다. 통짜로 만들면 '
        f'{a.platen_solid_mass_kg():.0f} kg 이라 4점 클램프({a.clamp_capacity_kn():.1f} kN/정반)가 '
        f'자기 무게도 못 든다 — 리브로 {a.platen_mass_kg():.0f} kg 까지 내려 순 압착력 '
        f'{a.clamp_net_kn():.2f} kN 을 남긴다",["AFR PL-251 패널 고정 정반"]],'
        f'["AFR-CL-221","AFR 지지·클램프","4점 {kinematics.AFR_CLAMP_KN:.0f} kN 상부 클램프",'
        f'"{kinematics.AFR_CLAMP_UNITS}EA",[420,260,520],"S355/PU/로드셀","가공·조립·힘교정",'
        f'"각 {kinematics.AFR_CLAMP_KN:.0f} kN·동기 ±5%","clamp",'
        f'"정반 {a.PLATEN_COUNT} 매를 {kinematics.AFR_CLAMP_UNITS // a.PLATEN_COUNT} 기씩 매달아 '
        f'내리고, 자중을 뺀 {a.clamp_net_kn():.2f} kN 으로 패널을 누른다",'
        f'["AFR CL-221 상부 클램프"]],'
        f'["AFR-SA-301","AFR 단축제거","정반 내장 단축 인출 실린더","{n_cyl}EA",'
        f'[{a.CYL_STROKE_MM + 300},{a.barrel_od_mm()},{a.barrel_od_mm()}],'
        f'"Ø{a.bore_mm()}/{a.rod_mm()}×{a.CYL_STROKE_MM} 유압실린더/S355",'
        f'"구매·포켓보링·배관·힘교정",'
        f'"{a.required_push_kn():.0f} kN/정반·{a.CYL_SPEED_MM_S:.0f} mm/s·작동 '
        f'{a.working_pressure_bar():.0f} bar (릴리프 {a.HPU_RELIEF_BAR:.0f})","cylinder",'
        f'"정반 양끝에서 {a.CYL_INSET_MM} mm 안쪽(스팬 {a.cylinder_span_mm():,})에 {a.CYL_PER_PLATEN} 본이 '
        f'묻히고, 로드가 단변쪽으로 나오며 쇠막대를 민다. 보어는 정반 두께가 정한다 — '
        f'배럴 Ø{a.barrel_od_mm()} 에 포켓 여유를 더하면 위아래 살이 {a.platen_wall_mm()} mm 남는다",'
        f'["AFR SA-301 단축 인출 실린더"]],'
        f'["AFR-PB-261","AFR 단축제거","단변 일괄 인출 쇠막대","{a.PLATEN_COUNT}EA",'
        f'[{a.BAR_W_MM},{a.bar_length_mm()},{a.bar_h_mm()}],"S355 평강 (기계가공)",'
        f'"가공·직진도교정·로드체결","직진도 0.2/{a.bar_length_mm():,}·중앙 처짐 '
        f'{a.bar_sag_mm()} mm (한도 {a.bar_sag_limit_mm()})","cylinder",'
        f'"실린더 {a.CYL_PER_PLATEN} 본을 하나로 묶어 단변 알루미늄을 점이 아니라 **변 전체**로 '
        f'{a.push_travel_mm()} mm 밀어낸다. 등분포 {a.bar_line_load_n_per_mm()} N/mm 에서 굽힘 '
        f'{a.bar_stress_mpa()} MPa (허용 {a.STEEL_ALLOW_MPA:.0f}) — 이 처짐이 그대로 단변 가운데가 '
        f'뒤처지는 양이 된다",["AFR PB-261 쇠막대"]],'
        f'["AFR-ST-241","AFR 단축제거","밀려난 프레임 정지 스토퍼",'
        f'"{a.STOPPER_PER_EDGE * 2}EA",[{a.STOPPER_T_MM},180,{a.bar_h_mm()}],'
        f'"S355/PU 완충패드","가공·조립·위치교정",'
        f'"캐치면 x ±{a.stopper_face_mm():.0f}·립 {a.STOPPER_LIP_MM} mm","clamp",'
        f'"쇠막대가 밀어낸 단변이 여기 걸려 선다. 행정 {a.CYL_STROKE_MM} 중 '
        f'{a.stroke_spare_mm()} mm 가 남아 스토퍼가 하드스톱이 아니라 정지면이고, 위 립이 '
        f'프레임이 타고 넘는 것을 막는다",'
        f'["AFR ST-241 프레임 스토퍼","AFR ST-241 스토퍼 지지빔"]],'
        f'["AFR-TC-231","AFR 반출·이송","정반 홈 관통 톱니 컨베이어","1식",'
        f'[{a.SLOT_L_MM},{2 * max(a.slot_z_mm())},240],'
        f'"ISO 08B-1 체인/{a.SPROCKET_TEETH}T 스프로킷/S355","조립·장력조정·승강교정",'
        f'"승상 {a.chain_rise_mm()} mm·{a.CHAIN_SPEED_MM_S:.0f} mm/s·런 {a.chain_runs()}열","roller",'
        f'"프레임이 다 제거되면 정반의 긴 홈 {a.chain_runs()}열로 아래에서 올라와 무프레임 유리를 '
        f'지지패드에서 넘겨받아 {a.CHAIN_LIFT_MM} mm 들고 반출한다. 바깥 런에서 유리 가장자리까지 '
        f'{a.laminate_overhang_mm():.0f} mm 외팔보에 처짐 {a.laminate_overhang_sag_mm()} mm · 응력 '
        f'{a.laminate_stress_mpa()} MPa (허용 {a.GLASS_ALLOW_MPA:.0f})",'
        f'["AFR TC-231 톱니 컨베이어 스프로킷","AFR TC-231 체인 구동·승강 유닛"]],'
        f'["AFR-LA-401","AFR 장축제거","LM가이드 홈 인발 캐리지",'
        f'"{a.CARRIAGE_PER_SIDE * 2}EA",[{a.LM_STROKE_MM},420,360],'
        f'"35급 LM레일/SKD11 트랙롤러 Ø{a.roller_d_mm()}×{a.roller_h_mm()}",'
        f'"가공·조립·레이저정렬",'
        f'"주행 {a.LM_STROKE_MM:,} mm·{a.LM_SPEED_MM_S:.0f} mm/s·접촉압 '
        f'{a.roller_contact_mpa()} MPa (허용 {a.roller_allow_mpa()})","rail",'
        f'"롤러 {a.rollers_per_carriage()} 개가 장변 압출재 홈({a.GROOVE_H_MM}×{a.GROOVE_D_MM})으로 '
        f'들어가 바닥에 걸치고 {a.pull_travel_mm()} mm 바깥으로 당긴 뒤, 그 상태로 LM 가이드를 타고 '
        f'끝에서 중앙으로 이동하며 계속 당긴다. 롤러가 접착 전선과 같이 가므로 자유 길이가 롤러 반경 '
        f'{a.roller_free_length_mm()} mm 뿐이고, 남는 처짐은 이미 떨어진 부분의 자중 '
        f'{a.self_weight_sag_mm()} mm — 휘지 않고 직선으로 떨어진다. 한 개로 '
        f'{frames.PEEL_FORCE_N:.0f} N 을 받으면 홈에 압흔이 남아 나눠 받는다",'
        f'["AFR LA-401 35급 듀얼 LM레일","AFR LA-401 장축 인발 캐리지",'
        f'"AFR LA-401 홈 인발 롤러 ×{a.rollers_per_carriage()}"]],'))


def station_parts() -> str:
    """2D GA 시트의 AFR 부품 — 3D 와 같은 기구를 그린다 (2D 원점은 3D +400)."""
    a = afr
    ox = -400
    platen_x = int(kinematics.PANEL_MM[0] / 2 - a.FRAME_W_MM - a.BAR_W_MM
                   - a.PLATEN_X_MM / 2)
    bar_x = int(kinematics.PANEL_MM[0] / 2 - a.FRAME_W_MM - a.BAR_W_MM / 2)
    platen_y = 1173 + a.PLATEN_T_MM // 2
    bar_y = 1173 - a.FRAME_H_MM + a.bar_h_mm() // 2
    stop_x = int(a.stopper_face_mm() + a.STOPPER_T_MM / 2)
    stop_z = 2 * a.STOPPER_Z_MM + 180
    rows = [
        f"part('CLAMP', '4점 상부클램프', [3100, 620, 1550], "
        f"[{ox}, 1700, 0], [0, 800, 0], 'primary')",
        f"part('PL-L', '고정 정반 L (실린더 {a.CYL_PER_PLATEN}본 내장)', "
        f"[{a.PLATEN_X_MM}, {a.PLATEN_T_MM}, {a.PLATEN_Z_MM}], "
        f"[{ox - platen_x}, {platen_y}, 0], [-700, 620, 0], 'primary', 'cylinder')",
        f"part('PL-R', '고정 정반 R (실린더 {a.CYL_PER_PLATEN}본 내장)', "
        f"[{a.PLATEN_X_MM}, {a.PLATEN_T_MM}, {a.PLATEN_Z_MM}], "
        f"[{ox + platen_x}, {platen_y}, 0], [700, 620, 0], 'primary', 'cylinder')",
        f"part('PB-L', '쇠막대 L', "
        f"[{a.BAR_W_MM}, {a.bar_h_mm()}, {a.bar_length_mm()}], "
        f"[{ox - bar_x}, {bar_y}, 0], [-1080, 340, 0], 'secondary')",
        f"part('PB-R', '쇠막대 R', "
        f"[{a.BAR_W_MM}, {a.bar_h_mm()}, {a.bar_length_mm()}], "
        f"[{ox + bar_x}, {bar_y}, 0], [1080, 340, 0], 'secondary')",
        f"part('ST-L', '프레임 스토퍼 L', "
        f"[{a.STOPPER_T_MM}, {a.bar_h_mm()}, {stop_z}], "
        f"[{ox - stop_x}, {bar_y}, 0], [-1320, 340, 0], 'secondary')",
        f"part('ST-R', '프레임 스토퍼 R', "
        f"[{a.STOPPER_T_MM}, {a.bar_h_mm()}, {stop_z}], "
        f"[{ox + stop_x}, {bar_y}, 0], [1320, 340, 0], 'secondary')",
        f"part('TC-231', '톱니 컨베이어 ({a.chain_runs()}열 · 홈 관통)', "
        f"[{a.SLOT_L_MM}, 240, {2 * max(a.slot_z_mm())}], "
        f"[{ox}, 1000, 0], [0, -420, 0], 'base')",
        f"part('LA-1/2', '장축 LM 1/2', [{a.LM_STROKE_MM}, 360, 420], "
        f"[{ox}, 1280, -{a.LM_RAIL_Z_MM}], [-400, 800, -900], 'secondary')",
        f"part('LA-3/4', '장축 LM 3/4', [{a.LM_STROKE_MM}, 360, 420], "
        f"[{ox}, 1280, {a.LM_RAIL_Z_MM}], [400, 800, 900], 'secondary')",
    ]
    return "".join("        " + r + ",\n" for r in rows)


def station_flow() -> str:
    a = afr
    down = 1173 + a.PLATEN_T_MM // 2
    bar = int(kinematics.PANEL_MM[0] / 2 - a.FRAME_W_MM - a.BAR_W_MM / 2) + 400
    steps = [
        f"step('2', '{a.support_zones()}구역 지지·정반 하강 {a.platen_lift_mm()}·4점 클램프', "
        f"[-400, {down + a.platen_lift_mm()}, 0], [-400, {down}, 0])",
        f"step('3', '단축 — 정반 내장 실린더 → 쇠막대가 단변 {a.push_travel_mm()} 밀어냄·스토퍼 정지', "
        f"[{-bar}, 1160, 0], [{-bar - a.push_travel_mm()}, 1160, 0])",
        f"step('4', '장축 — 롤러 홈 진입·바깥 {a.pull_travel_mm()} 당김·LM {a.LM_STROKE_MM:,} 주행', "
        f"[275, 1280, -{a.LM_RAIL_Z_MM}], [{275 - a.LM_STROKE_MM}, 1280, "
        f"-{a.LM_RAIL_Z_MM + a.pull_travel_mm()}])",
    ]
    return "".join("        " + t + ",\n" for t in steps)


def patch_prose(text: str) -> str:
    for anchor, name in phase_names():
        pat = re.compile(r'\{name:"[^"]*",start:' + re.escape(anchor) + r"\}")
        hit = pat.findall(text)
        assert len(hit) == 1, f"시퀀스 앵커 {anchor} {len(hit)}"
        text = pat.sub(lambda _m: '{name:"' + name + '",start:' + anchor + "}", text, count=1)

    pat = re.compile(r"(저마킹 롤러, 공유 3D 맵 검증, ).*?(, HPU 7\.5 kW)")
    hit = pat.findall(text)
    assert len(hit) == 1, f"사양 문장 앵커 {len(hit)}"
    text = pat.sub(lambda m: m.group(1) + spec_sentence() + m.group(2), text, count=1)

    pat = re.compile(r"(<b>AFR-101</b><span>)[^<]*(</span>)")
    hit = pat.findall(text)
    assert len(hit) == 1, f"공정흐름 라벨 앵커 {len(hit)}"
    text = pat.sub(lambda m: m.group(1) + "정반·쇠막대 단축 → 홈롤러 장축" + m.group(2),
                   text, count=1)

    # 부품표 — AFR 기구 행
    pat = re.compile(r'\["AFR-SU-211".*?(?=\["AFR-AE-401")', re.S)
    assert len(pat.findall(text)) == 1, "부품표 앵커"
    text = pat.sub(lambda _m: bom_rows(), text, count=1)

    # 2D GA 시트 — 같은 기구를 2D 로
    pat = re.compile(r"( *part\('CLAMP'.*?)(?= *part\('HPU')", re.S)
    assert len(pat.findall(text)) == 1, "GA 부품 앵커"
    text = pat.sub(lambda _m: station_parts(), text, count=1)

    pat = re.compile(r"( *step\('2', '(?:12|\d+)구역.*?)(?= *step\('5', '프레임 동력)", re.S)
    assert len(pat.findall(text)) == 1, "GA 흐름 앵커"
    text = pat.sub(lambda _m: station_flow(), text, count=1)

    # 시점 프리셋 — 발주처가 누르는 두 버튼이 기구를 실제로 비춰야 한다.
    # 단축은 정반·쇠막대·스토퍼가 있는 −x 끝을, 장축은 홈에 들어간 롤러를 본다.
    plx = _f(-(kinematics.PANEL_MM[0] / 2000.0 - FW - M(afr.BAR_W_MM)
               - M(afr.PLATEN_X_MM) / 2))
    grz = _f(M(afr.roller_axis_z_mm()))
    for name, body in (
        # 카메라는 안전가드(z ±2.38) **밖**에 둔다 — 안에 들어가면 가드 살이
        # 화면을 가로지른다. 대신 표적을 기구로 당겨 화면 가운데에 놓는다.
        ("afrshort", f"{{position:new C(qt{plx}-1.4,2.7,-4.2),"
                     f"target:new C(qt{plx},{_f(PANEL_TOP)},0)}}"),
        # 장축은 명판(y 2.1) 아래로 눈높이를 낮춰야 판이 기구를 가리지 않는다
        ("afrlong", f"{{position:new C(qt+1.6,1.72,3.35),"
                    f"target:new C(qt+.5,{_f(FRAME_Y)},{grz})}}"),
    ):
        pat = re.compile(re.escape(name) + r":\{position:new C\([^}]*\}")
        assert len(pat.findall(text)) == 1, f"시점 앵커 {name}"
        text = pat.sub(lambda _m, b=body: name + ":" + b, text, count=1)

    # 명판이 엉뚱한 기계 위에 떠 있었다 — AFR 기구 바로 위에 'SG-301' 판이,
    # AFR 판은 6 m 상류 빈자리에 있었다. 3D 실측 위치로 옮긴다 (기구 4.85…7.35,
    # SG-301 연마휠 10.79…11.15).
    for name, x in (("AFR-101", "6.1"), ("SG-301", "11")):
        pat = re.compile(r"^pvNamePlate\(g,([\d.]+),\[[-\d.]+,([\d.]+),([\d.]+)\],0,'"
                         + name + r"'", re.M)
        assert len(pat.findall(text)) == 1, f"명판 앵커 {name}"
        text = pat.sub(lambda m, x=x, n=name: f"pvNamePlate(g,{m.group(1)},"
                       f"[{x},{m.group(2)},{m.group(3)}],0,'{n}'", text, count=1)

    # 옛 단일 휨 상수는 죽었다 — 두 변의 휨이 서로 다른 데서 나온다
    text = text.replace("var pvBow=.059;", "")
    assert "pvBow" not in text, "옛 휨 상수가 아직 쓰이고 있다"

    # 품목 수 — 부품표를 늘렸으면 화면 문구도 따라와야 한다
    total = len(re.findall(r"part\('[^']*', '[^']*', \[", text)) - len(
        re.findall(r"part\('[^']*', '[^']*', \[[^\]]*\], \[[^\]]*\], \[[^\]]*\], '[^']*', 'sweep'\)", text))
    pat = re.compile(r"(목록이 길어\(현재 )\d+(품목\))")
    assert len(pat.findall(text)) == 1, "품목 수 앵커"
    return pat.sub(lambda m: m.group(1) + str(total) + m.group(2), text, count=1)


def main() -> int:
    text = DRAWING.read_text(encoding="utf-8")
    lines = text.split("\n")
    idx = max(range(len(lines)), key=lambda i: len(lines[i]) if "AFR-101" in lines[i] else 0)
    line = lines[idx]

    b0 = line.index("var Pu=[];")
    b1 = line.index("var Wr=4.55;")
    a0 = line.index("w0(r);")
    a1 = line.index("eu.visible=a&&l>=31.2,eu.scale.y=le(.2,1,x);") + len(
        "eu.visible=a&&l>=31.2,eu.scale.y=le(.2,1,x);")

    assert b0 < b1 < a0 < a1, (b0, b1, a0, a1)
    line = line[:a0] + build_anim() + line[a1:]
    line = line[:b0] + build_block() + line[b1:]
    lines[idx] = line

    # 시험 훅은 다른 줄에 있다 — 거기도 모델값으로 맞춘다.
    hits = [i for i, ln in enumerate(lines) if HOOK_OLD in ln or build_hook() in ln]
    assert len(hits) == 1, f"시험 훅 앵커 {len(hits)}"
    lines[hits[0]] = lines[hits[0]].replace(HOOK_OLD, build_hook())

    text = patch_prose("\n".join(lines))
    DRAWING.write_text(text, encoding="utf-8")
    print(f"AFR 3D 블록 재생성 — 빌드 {b1 - b0} → {len(build_block())} 자, "
          f"애니 {a1 - a0} → {len(build_anim())} 자")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
