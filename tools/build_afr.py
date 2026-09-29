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

from pv_preprocess import afr, afr_peel, frames, kinematics, layout  # noqa: E402

DRAWING = pathlib.Path(__file__).resolve().parent.parent / "docs/drawings/pv-preprocess-plant.html"

# ── 3D 좌표계 (AFR 셀 로컬, m) ───────────────────────────────────────────
# 패널 높이는 **이송면 하나**에서 나온다. REV.44 까지는 1.145 라는 리터럴이었고,
# 그 탓에 3D 의 AFR 이송면은 1,095 mm, JBR 은 1,025 mm, 모델은 950 mm 로 셋이 다
# 달랐다. 이제 값은 layout.LINE_TRANSFER_MM 한 곳에만 있다.
#
# 틀 프레임은 유리 아래로 20 mm 더 내려오므로 롤러에 닿는 것은 **프레임 하면**이다.
# 거기에 렌더 간섭을 피할 만큼만 띄운다 (JBR 셀도 같은 2.5 mm 를 쓴다).
RIDE_CLEAR = 0.0025
PANEL_T = 0.055
FRAME_T = afr.FRAME_H_MM / 1000.0          # 0.075
PANEL_BOTTOM_Y = layout.LINE_TRANSFER_MM / 1000.0 + RIDE_CLEAR   # .9525 프레임 하면
PANEL_TOP = PANEL_BOTTOM_Y + FRAME_T       # 1.0275
PANEL_Y = PANEL_TOP - PANEL_T / 2          # 1.0    유리 적층체 중심
PANEL_BOT = PANEL_Y - PANEL_T / 2          # .9725
FRAME_Y = PANEL_TOP - FRAME_T / 2          # .99    윗면이 유리면과 같은 높이다

# 이송면을 따라 움직여야 하는 것들의 **상대** 위치. 절대값으로 두면 이송면을
# 바꿀 때마다 조용히 어긋난다 — REV.44 까지 여섯 곳이 그랬다.
CLAMP_BODY_DY = 0.4775                     # 정반 중심 → 클램프 몸통
CLAMP_ARM_DY = (0.6275, 0.2975)            # 정반 중심 → 클램프 팔 (올림, 내림)
CLAMP_PAD_DY = (0.3575, 0.0475)            # 정반 중심 → 클램프 패드 (올림, 내림)
LM_RAIL_DY, LM_CARR_DY = -0.135, 0.145     # 장변 프레임 중심 → LM 레일·캐리지
STOPPER_DY = -0.005                        # 장변 프레임 중심 → 정렬 스토퍼 중심
BASE_TOP_Y = 0.45                          # AFR 베이스 프레임 상면 (씬에 손으로 그린 값)

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


# ── 연속체 프레임 — 실물 압출재 단면을 스윕하고 XPBD 로 휘게 한다 ────────
#: 파티클 수. 장변은 β⁻¹(352 mm) 안에 여러 마디가 들어가야 휨이 곡선으로 보인다.
NODES_LONG = 33
NODES_SHORT = 21
#: 한 프레임의 물리 서브스텝 수 — XPBD 는 반복이 아니라 서브스텝으로 수렴한다.
SUBSTEPS = 8
#: 캐리지 롤러가 홈을 무는 유효 반경 (m)·그 밖에서 남는 마찰 몫.
GRIP_R_M = 0.14
GRIP_TAIL = 0.0


def build_continuum_frames() -> str:
    """네 변을 **연속체**로 만든다 — 토막 32 개 대신 스윕 메시 4 벌.

    형상: `afr_peel.section_outline_m()` 의 단면 다각형(도심 기준)을 절점마다
    세워 스윕한다. 같은 다각형에서 면적·단면 2차 모멘트가 나오므로, 화면이
    그리는 단면과 계산이 쓴 단면이 어긋날 수 없다.

    운동: 브라우저에서 XPBD(확장 위치기반동역학)를 돌린다. 늘어남 구속은 EA/L,
    굽힘 구속은 EI/L³, 접착 구속은 실란트 강성에서 컴플라이언스를 받는다 —
    상수는 전부 `afr_peel.physics_si()` 에서 오고 화면에 리터럴이 없다.
    접착 전선의 위치만은 유한요소가 낸 `front_curve()` 를 쓴다: 되감아도 같은
    자리에서 같은 값이 나와야 스크럽이 어긋나지 않기 때문이다.
    """
    q = _f
    q6 = lambda v: _f(v, 6)                    # noqa: E731  단면점은 mm 이하까지 쓴다
    sec = afr_peel.section_outline_m()
    cap = afr_peel.section_cap_indices()
    phy = afr_peel.physics_si()
    prof = frames.profile()
    front = afr_peel.front_curve()
    pk = afr_peel
    short_clear = (kinematics.PANEL_MM[1] - 2 * afr.FRAME_W_MM) / 1000.0
    base_y = PANEL_TOP - FRAME_T            # 프레임 밑면 — 단면 v=0 자리
    cy = base_y + prof["cv_mm"] / 1000.0    # 도심 높이
    cu = prof["cu_mm"] / 1000.0             # 바깥면에서 도심까지

    js: list[str] = []
    A = js.append
    A("var pvAfrSec=[" + ",".join("[%s,%s]" % (q6(u), q6(v)) for u, v in sec) + "];")
    A("var pvAfrCap=[" + ",".join(str(i) for i in cap) + "];")
    A("var pvAfrPhy={" + ",".join("%s:%g" % (k, v) for k, v in phy.items()) + "};")
    A("var pvAfrFront=[" + ",".join("[%s,%s]" % (q(a_), q(b_)) for a_, b_ in front) + "];")
    # 쇠막대의 4차 처짐 형상 — 단변 강제변위의 **모양**이다 (중앙이 뒤처진다).
    sp = afr_peel.short_edge_profile(NODES_SHORT - 1)
    push = float(afr.push_travel_mm())
    A("var pvAfrShort=[" + ",".join(_f(v / push, 6) for v in sp) + "];")
    A("var pvAfrAlu=Xo.clone();pvAfrAlu.side=bn;")
    # 모양은 물리가 낸다. 크기만 이 배율로 키운다 — 실제 처짐이 mm 단위라
    # 플랜트 축척에서는 보이지 않기 때문이고, 배율은 화면 주기에 적어 둔다.
    A("var pvAfrExag=%s,pvAfrExagCap=.12;" % q(frames.DISPLAY_EXAGGERATION))

    A("function pvAfrBuildEdge(o){"
      "var S=pvAfrSec.length,n=o.nodes,pos=new Float32Array((n*S+2*S)*3),ix=[];"
      "for(let i=0;i<n-1;i+=1)for(let j=0;j<S;j+=1){let k=(j+1)%S,a=i*S+j,b=i*S+k,c=(i+1)*S+k,d=(i+1)*S+j;"
      "ix.push(a,b,c,a,c,d)}"
      "let ca=n*S,cb=n*S+S;"
      "for(let t=0;t<pvAfrCap.length;t+=3){ix.push(ca+pvAfrCap[t+2],ca+pvAfrCap[t+1],ca+pvAfrCap[t]);"
      "ix.push(cb+pvAfrCap[t],cb+pvAfrCap[t+1],cb+pvAfrCap[t+2])}"
      "let g=new an();g.setAttribute('position',new on(pos,3));g.setIndex(ix);"
      "let m=new et(g,pvAfrAlu);m.castShadow=!0;m.receiveShadow=!0;"
      "if(o.label){m.userData.label=o.label;m.userData.note=o.note;"
      "m.userData.partNo=Fr.get(o.label)?.no||null;Ns.push(m)}Cs.add(m);"
      "let e={mesh:m,geo:g,pos:pos,n:n,S:S,axis:o.axis,lat:o.lat,sign:o.sign,len:o.len,"
      "seg:o.len/(n-1),restLat:o.restLat,restY:o.restY,"
      "p:new Float64Array(n*3),v:new Float64Array(n*3),q:new Float64Array(n*3),"
      "anc:new Float64Array(n*3),bond:new Float64Array(n),rg:new Float64Array(n*3),"
      "dv:new Float64Array(n*3),sm:new Float64Array(n*3),"
      "pin:new Float64Array(n),"
      "mass:pvAfrPhy.rhoA*(o.len/(n-1))};"
      "pvAfrRest(e);return e}")

    A("function pvAfrRest(e){"
      "for(let i=0;i<e.n;i+=1){let s=-e.len/2+i*e.seg,x=i*3;"
      "if(e.axis===0){e.p[x]=s;e.p[x+2]=e.restLat}else{e.p[x]=e.restLat;e.p[x+2]=s}"
      "e.p[x+1]=e.restY;e.anc[x]=e.p[x];e.anc[x+1]=e.p[x+1];e.anc[x+2]=e.p[x+2];"
      "e.v[x]=e.v[x+1]=e.v[x+2]=0;e.bond[i]=1}}")

    A("function pvAfrSolve(e,h,out,drop,grip){"
      "var n=e.n,p=e.p,v=e.v,qq=e.q,L=e.seg,li=e.lat,im=1/e.mass,"
      "aS=(L/pvAfrPhy.ea)/(h*h),aB=(L*L*L/pvAfrPhy.ei)/(h*h),"
      "aBond=(1/(pvAfrPhy.bondK*L))/(h*h),"
      "fBond=pvAfrPhy.bondQ*L*h*h,brk=pvAfrPhy.bondBreak,sep=pvAfrPhy.bondSep;"
      # ① 예측 — 중력을 먹이고 한 걸음 나아간다
      "for(let i=0;i<n;i+=1){let x=i*3;v[x+1]+=-9.81*h;"
      "qq[x]=p[x];qq[x+1]=p[x+1];qq[x+2]=p[x+2];"
      "p[x]+=v[x]*h;p[x+1]+=v[x+1]*h;p[x+2]+=v[x+2]*h}"
      # ② 구동 — 강체 자세를 적어 두고, 롤러·쇠막대가 무는 마디를 운동학으로 붙잡는다
      "for(let i=0;i<n;i+=1){let x=i*3,s=-e.len/2+i*e.seg,"
      "ty=e.restY-drop(i),tl=e.restLat+e.sign*out(i);"
      "e.rg[x]=e.axis===0?s:tl;e.rg[x+1]=ty;e.rg[x+2]=e.axis===0?tl:s;"
      "e.pin[i]=0;if(e.bond[i]>0)continue;"
      "if(grip(i)>0){e.pin[i]=1;p[x+li]=tl}else{p[x+li]+=(tl-p[x+li])*.06}"
      "p[x+1]+=(ty-p[x+1])*.22}"
      # ③ 접착 — 이중선형 응집영역. 끊어진 마디는 다시 붙지 않는다
      "for(let i=0;i<n;i+=1){if(e.bond[i]<=0)continue;let x=i*3,"
      "dx=p[x]-e.anc[x],dy=p[x+1]-e.anc[x+1],dz=p[x+2]-e.anc[x+2],"
      "d=Math.sqrt(dx*dx+dy*dy+dz*dz);if(d<1e-12)continue;"
      "if(d>sep){e.bond[i]=0;continue}"
      "let soft=d<=brk?1:(sep-d)/(sep-brk),"
      "dl=-d/(im+aBond/Math.max(soft,.02));"
      "if(-dl>fBond*soft)dl=-fBond*soft;"
      "let s=dl*im/d;p[x]+=dx*s;p[x+1]+=dy*s;p[x+2]+=dz*s}"
      # ④ 늘어남(EA/L)·굽힘(EI/L³) — 33 마디까지 정보가 가도록 여러 번 쓴다
      "for(let it=0;it<4;it+=1){"
      "for(let i=0;i<n-1;i+=1){let a=i*3,b=a+3,"
      "dx=p[b]-p[a],dy=p[b+1]-p[a+1],dz=p[b+2]-p[a+2],"
      "d=Math.sqrt(dx*dx+dy*dy+dz*dz);if(d<1e-12)continue;"
      "let wa=(e.bond[i]>0||e.pin[i])?0:im,wb=(e.bond[i+1]>0||e.pin[i+1])?0:im,"
      "W=wa+wb;if(W<=0)continue;"
      "let dl=-(d-L)/(W+aS),s=dl/d;"
      "p[a]-=dx*s*wa;p[a+1]-=dy*s*wa;p[a+2]-=dz*s*wa;"
      "p[b]+=dx*s*wb;p[b+1]+=dy*s*wb;p[b+2]+=dz*s*wb}"
      "for(let i=1;i<n-1;i+=1){let a=(i-1)*3,b=i*3,c=(i+1)*3,"
      "dx=p[a]-2*p[b]+p[c],dy=p[a+1]-2*p[b+1]+p[c+1],dz=p[a+2]-2*p[b+2]+p[c+2],"
      "d=Math.sqrt(dx*dx+dy*dy+dz*dz);if(d<1e-12)continue;"
      "let wa=(e.bond[i-1]>0||e.pin[i-1])?0:im,wb=(e.bond[i]>0||e.pin[i])?0:im,"
      "wc=(e.bond[i+1]>0||e.pin[i+1])?0:im,W=wa+4*wb+wc;if(W<=0)continue;"
      "let dl=-d/(W+aB),s=dl/d;"
      "p[a]+=dx*s*wa;p[a+1]+=dy*s*wa;p[a+2]+=dz*s*wa;"
      "p[b]-=2*dx*s*wb;p[b+1]-=2*dy*s*wb;p[b+2]-=2*dz*s*wb;"
      "p[c]+=dx*s*wc;p[c+1]+=dy*s*wc;p[c+2]+=dz*s*wc}}"
      # ⑤ 속도 — 위치 차분에서 낸다 (XPBD). 0.994 는 재료·공기 감쇠 몫이다
      "for(let i=0;i<n;i+=1){let x=i*3;"
      "v[x]=(p[x]-qq[x])/h*.93;v[x+1]=(p[x+1]-qq[x+1])/h*.93;"
      "v[x+2]=(p[x+2]-qq[x+2])/h*.93}}")

    A("var pvAfrT=new C,pvAfrU=new C,pvAfrUp=new C(0,1,0),pvAfrIn=new C;"
      # 강체 자세에서의 편차를 매끄럽게 한 뒤 키운다. 보의 변형은 C1 이므로
      # 마디마다 튀는 것은 물리가 아니라 XPBD 잔차다 — 그것까지 배로 키우면
      # 곡선이 톱니가 된다. 라플라시안 두 번이면 잔차만 지워진다.
      "function pvAfrSmooth(e){var n=e.n,d=e.dv,s=e.sm;"
      "for(let i=0;i<n*3;i+=1)d[i]=e.p[i]-e.rg[i];"
      "for(let k=0;k<2;k+=1){for(let i=0;i<n;i+=1){let a=Math.max(0,i-1)*3,"
      "b=i*3,c=Math.min(n-1,i+1)*3;"
      "s[b]=(d[a]+2*d[b]+d[c])/4;s[b+1]=(d[a+1]+2*d[b+1]+d[c+1])/4;"
      "s[b+2]=(d[a+2]+2*d[b+2]+d[c+2])/4}"
      "for(let i=0;i<n*3;i+=1)d[i]=s[i]}"
      "for(let i=0;i<n*3;i+=1){let z=d[i]*pvAfrExag;"
      "d[i]=(z>pvAfrExagCap?pvAfrExagCap:z<-pvAfrExagCap?-pvAfrExagCap:z)/pvAfrExag}}"
      "function pvAfrSkin(e){var n=e.n,S=e.S,p=e.p,pos=e.pos,d=e.dv;pvAfrSmooth(e);"
      "for(let i=0;i<n;i+=1){let a=Math.max(0,i-1)*3,b=Math.min(n-1,i+1)*3,x=i*3;"
      "pvAfrT.set(e.rg[b]+d[b]*pvAfrExag-e.rg[a]-d[a]*pvAfrExag,"
      "e.rg[b+1]+d[b+1]*pvAfrExag-e.rg[a+1]-d[a+1]*pvAfrExag,"
      "e.rg[b+2]+d[b+2]*pvAfrExag-e.rg[a+2]-d[a+2]*pvAfrExag);"
      "if(pvAfrT.lengthSq()<1e-16)pvAfrT.set(e.axis===0?1:0,0,e.axis===0?0:1);"
      "pvAfrT.normalize();pvAfrU.copy(pvAfrUp).cross(pvAfrT);"
      "if(pvAfrU.lengthSq()<1e-16)pvAfrU.set(1,0,0);pvAfrU.normalize();"
      "pvAfrIn.set(0,0,0);pvAfrIn.setComponent(e.lat,-e.sign);"
      "if(pvAfrU.dot(pvAfrIn)<0)pvAfrU.negate();"
      "let cx=e.rg[x]+d[x]*pvAfrExag,cy=e.rg[x+1]+d[x+1]*pvAfrExag,"
      "cz=e.rg[x+2]+d[x+2]*pvAfrExag;"
      "for(let j=0;j<S;j+=1){let s=pvAfrSec[j],o=(i*S+j)*3;"
      "pos[o]=cx+pvAfrU.x*s[0];pos[o+1]=cy+s[1];pos[o+2]=cz+pvAfrU.z*s[0]}"
      "if(i===0||i===n-1){let base=(n*S+(i===0?0:S))*3;"
      "for(let j=0;j<S;j+=1){let o=(i*S+j)*3;pos[base+j*3]=pos[o];"
      "pos[base+j*3+1]=pos[o+1];pos[base+j*3+2]=pos[o+2]}}}"
      "e.geo.attributes.position.needsUpdate=!0;e.geo.computeVertexNormals();"
      "e.geo.computeBoundingSphere()}")

    long_note = ('"바깥면 홈(%d×%d mm)에 롤러가 들어가 걸치고 %d mm 바깥으로 당깁니다. '
                 '압출재를 토막이 아니라 **연속체**로 풉니다 — 단면 %.0f mm² · '
                 'I %s mm⁴ · %s kg/m 를 화면에서 XPBD 로 실시간 적분합니다. '
                 '접착 위의 보라 휨이 잦아드는 특성길이가 β⁻¹ = %s mm 이고, 그 크기의 '
                 '곡선이 인발 중에 보입니다. 설계 인발력 %d N 은 정상박리력 %s N 의 '
                 '%s 배라 균열이 캐리지를 앞질러 달립니다 — 유한요소 결과이며 실란트 '
                 '실측이 오면 바뀔 수 있습니다. 화면의 휨은 **모양은 물리 그대로**이고 '
                 '크기만 %d배 과장했습니다 — 실제 처짐이 mm 단위라 플랜트 축척에서는 '
                 '보이지 않기 때문입니다."'
                 % (afr.GROOVE_H_MM, afr.GROOVE_D_MM, afr.pull_travel_mm(),
                    prof["area_mm2"], format(prof["i_lateral_mm4"], ",.0f"),
                    frames.profile_mass_kg_m(), pk.decay_length_mm(),
                    int(frames.PEEL_FORCE_N), pk.steady_peel_force_n(), pk.stability(),
                    int(frames.DISPLAY_EXAGGERATION)))
    short_note = ('"정반 안의 실린더 %d 본이 쇠막대를 통해 이 변 전체를 한 번에 %d mm '
                  '밀어냅니다. 막대가 강체가 아니라 스팬 중앙이 %s mm 처지고, 그 4차 '
                  '처짐 형상이 그대로 알루미늄의 강제변위가 됩니다 — 유한요소가 낸 중앙 '
                  '지연은 %.3f mm 입니다. 과장하지 않은 실제 값이라 화면에서는 거의 '
                  '직선입니다."'
                  % (afr.CYL_PER_PLATEN, afr.push_travel_mm(), afr.bar_sag_mm(),
                     pk.short_edge_lag_mm()))

    A("var pvAfrEdges=["
      "pvAfrBuildEdge({nodes:%d,axis:0,lat:2,sign:1,len:%s,restLat:%s,restY:%s,"
      "label:'AFR 장축 알루미늄 프레임',note:%s}),"
      "pvAfrBuildEdge({nodes:%d,axis:0,lat:2,sign:-1,len:%s,restLat:%s,restY:%s,label:null}),"
      "pvAfrBuildEdge({nodes:%d,axis:2,lat:0,sign:1,len:%s,restLat:%s,restY:%s,"
      "label:'AFR 단축 알루미늄 프레임',note:%s}),"
      "pvAfrBuildEdge({nodes:%d,axis:2,lat:0,sign:-1,len:%s,restLat:%s,restY:%s,label:null})];"
      % (NODES_LONG, q(2 * HALF_X), q(HALF_Z - cu), q(cy), long_note,
         NODES_LONG, q(2 * HALF_X), q(-(HALF_Z - cu)), q(cy),
         NODES_SHORT, q(short_clear), q(HALF_X - cu), q(cy), short_note,
         NODES_SHORT, q(short_clear), q(-(HALF_X - cu)), q(cy)))

    A("function pvAfrFrontAt(f){var t=pvAfrFront;if(f<=t[0][0])return t[0][1];"
      "for(let i=1;i<t.length;i+=1)if(f<=t[i][0]){let a=t[i-1],b=t[i];"
      "return a[1]+(b[1]-a[1])*(f-a[0])/Math.max(1e-9,b[0]-a[0])}"
      "return t[t.length-1][1]}")

    A("var pvAfrClock=-1;"
      "function pvAfrStep(sc){"
      "var back=sc.t<pvAfrClock-1e-6||sc.reset;pvAfrClock=sc.t;"
      "if(back)pvAfrEdges.forEach(pvAfrRest);"
      "var h=1/(60*%d),lf=pvAfrFrontAt(sc.longFrac);"
      "for(let k=0;k<%d;k+=1)for(let m=0;m<pvAfrEdges.length;m+=1){"
      "var e=pvAfrEdges[m],isLong=e.axis===0;"
      "for(let i=0;i<e.n;i+=1){if(e.bond[i]<=0)continue;"
      "var s=Math.abs(-e.len/2+i*e.seg);"
      "if(isLong?(lf>0&&e.len/2-s<=lf):(sc.shortFrac>0))e.bond[i]=0}"
      "pvAfrSolve(e,h,"
      "isLong?function(){return sc.longOut}:function(i){return sc.shortOut*sc.shortShape(i)},"
      "isLong?function(){return sc.longDrop}:function(){return sc.shortDrop},"
      "isLong?function(i){var x=-e.len/2+i*e.seg;"
      "return Math.min(Math.abs(x-sc.carA),Math.abs(x-sc.carB))<%s?1:%s}"
      ":function(){return 1})}"
      "for(let m=0;m<pvAfrEdges.length;m+=1)pvAfrSkin(pvAfrEdges[m]);"
      "pvAfrEdges[0].mesh.visible=pvAfrEdges[1].mesh.visible=sc.longVis;"
      "pvAfrEdges[2].mesh.visible=pvAfrEdges[3].mesh.visible=sc.shortVis}"
      % (SUBSTEPS, SUBSTEPS, q(GRIP_R_M), q(GRIP_TAIL)))
    return "".join(js)


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
      f'.forEach(([sx,cz],t)=>p0.push(P(ot,[.12,.34,.14],[sx*{q(stop_face + 0.08)},{q(FRAME_Y + STOPPER_DY)},cz],M.orange,'
      f't===0?"AFR 양방향 포지티브 스토퍼":null,'
      f'"패널 모서리를 물어 위치·직각도를 확정하고, 단변을 밀기 전에 밀려날 프레임 자리 밖으로 물러납니다.")));')

    # ── 프레임 스토퍼 — 밀려난 단변이 여기 걸려 선다 ─────────────────────
    A(f'[-1,1].forEach(function(sx){{'
      f'P(ot,[{q(2 * bar_w / 3)},{q(bed_t * 2)},2.42],[sx*{q(beam_x)},{q(bed_y + 0.03)},0],M.frame,'
      f'sx<0?"AFR ST-241 스토퍼 지지빔":null,"프레임 스토퍼와 정렬 스토퍼를 함께 받는 빔 — '
      f'베이스 프레임 위에 기둥 둘로 섭니다.");'
      f'[-1.18,1.18].forEach(function(cz){{P(ot,[.09,{q(bed_y - 0.03 - BASE_TOP_Y)},.16],[sx*{q(beam_x)},{q((BASE_TOP_Y + bed_y - 0.03) / 2)},cz],M.frame,null)}});'
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
      f'P(n,[.18,.5,.18],[0,{q(platen_dy + CLAMP_BODY_DY)},0],Qt,t===0?"AFR CL-221 상부 클램프":null,'
      f'"로드셀 폐루프로 각 {kinematics.AFR_CLAMP_KN:.0f} kN 을 인가합니다. 정반 1매 {a.platen_mass_kg():.0f} kg '
      f'({a.platen_weight_kn():.2f} kN) 를 클램프 둘이 매달므로 패널에 남는 순 압착력은 '
      f'{a.clamp_net_kn():.2f} kN 입니다 — 통짜 정반이면 {a.platen_solid_mass_kg():.0f} kg 이라 '
      f'클램프가 자기 무게도 못 듭니다. 리브 웰드먼트로 강재 점유율 {a.platen_steel_fraction() * 100:.0f} % 입니다.");'
      f'let s=P(n,[.42,.12,.18],[.13,{q(platen_dy + CLAMP_ARM_DY[0])},0],M.orange),r=P(n,[.28,.08,.22],[.28,{q(platen_dy + CLAMP_PAD_DY[0])},0],M.rubber);'
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
    A('var Cs=pvTransit(new ce);ot.add(Cs);')
    A(f'var iM=P(Cs,[{q(2 * HALF_X)},{q(PANEL_T)},{q(2 * HALF_Z)}],[0,{q(PANEL_Y)},0],h0,'
      f'"JBR 완료 패널 · JBOX 제거상태",'
      f'"{kinematics.PANEL_MM[0]:,}×{kinematics.PANEL_MM[1]:,} mm 최대규격이며 유리면 아래·백시트 위, '
      f'정션박스와 케이블 제거 완료 상태로만 AFR 에 진입합니다.");')
    A(build_continuum_frames())

    # ── LM 인발 캐리지 — 롤러가 홈에 들어가 바깥으로 당긴다 ──────────────
    A(f'var Du=[],pvAfrHead=[];[-1,1].forEach(i=>{{'
      f'P(ot,[2.9,.08,.12],[0,{q(FRAME_Y + LM_RAIL_DY)},i*{q(rail_z)}],M.steel,i<0?"AFR LA-401 35급 듀얼 LM레일":null,'
      f'"장변 한 변에 캐리지 {a.CARRIAGE_PER_SIDE} 대가 양끝에서 중앙으로 {a.LM_STROKE_MM:,} mm 를 '
      f'{a.LM_SPEED_MM_S:.0f} mm/s 로 주행하며 계속 당깁니다.");'
      f'[-1,1].forEach(e=>{{let t=new ce;t.position.set(e*{q(lm_start)},{q(FRAME_Y + LM_CARR_DY)},i*{q(rail_z)});ot.add(t);'
      f'P(t,[.32,.18,.26],[0,0,0],M.orange,i<0&&e<0?"AFR LA-401 장축 인발 캐리지":null,'
      f'"롤러가 장변 압출재 홈으로 들어가 걸친 뒤 {a.pull_travel_mm()} mm 바깥으로 당기고, 그 상태로 '
      f'LM 가이드를 타고 이동하며 계속 당깁니다. 양쪽에서 같이 당기므로 프레임이 휘지 않습니다.");'
      f'P(t,[.34,.06,.3],[0,-.1,0],M.dark,null);'
      f'let hd=new ce;hd.position.set(0,{q(-LM_CARR_DY)},{q(park_z - rail_z)}*i),t.add(hd);'
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
      f'V.position.y=le({q(platen_dy + CLAMP_ARM_DY[0])},{q(platen_dy + CLAMP_ARM_DY[1])},K)+De,'
      f'ae.position.y=le({q(platen_dy + CLAMP_PAD_DY[0])},{q(platen_dy + CLAMP_PAD_DY[1])},K)+De}}),')
    A(f'pvAfrPlaten.forEach(V=>{{V.position.y=le({q(platen_dy + lift)},{q(platen_dy)},PD)+{q(lift)}*PU}}),')
    A(f'p0.forEach((V,ae)=>{{let ie=me(Se(l,4.8,7.2))*(1-me(Se(l,9.4,9.9)));'
      f'V.position.x=(ae<2?-1:1)*le({q(stop_open)},{q(stop_shut)},ie)}}),')
    A('Pu.forEach(({pad:V,phase:ae})=>{let ie=K*(.003+Math.sin(ae*1.47)*.0014);'
      f'V.position.y={q(PANEL_BOT - M(a.SUPPORT_PAD_T_MM) / 2)}+ie}}),')
    A(f'pvAfrBar.forEach(({{group:V,sign:ae}})=>{{'
      f'V.position.x=ae*({q(bar_local)}+{q(push)}*(PS-PR))}}),')

    A(f'Qh.visible=a&&l>=19.5,Qh.scale.y=le(.2,1,p),')
    A(f'pvAfrHead.forEach(({{head:V,zSign:ae}})=>{{'
      f'let pz=le({q(park_z)},{q(groove_z)},PJ*(1-PB))+{q(pull)}*EN*(1-PB);'
      f'V.position.z=ae*(pz-{q(rail_z)})}}),')
    # 프레임은 이제 강체 토막이 아니라 연속체다 — 시계가 자세를 정하고, 휨은
    # 화면에서 도는 XPBD 가 낸다 (tools/build_afr.py: build_continuum_frames).
    A(f'pvAfrStep({{t:l,reset:!te,'
      f'longFrac:EN*(1-PB),longOut:{q(pull)}*EN*(1-PB),longDrop:.72*PF,'
      f'carA:-le({q(lm_start)},{q(lm_end)},PW*(1-PB)),'
      f'carB:le({q(lm_start)},{q(lm_end)},PW*(1-PB)),'
      f'shortFrac:PS,shortOut:{q(push)}*PS,shortDrop:.72*p,'
      f'shortShape:function(i){{return pvAfrShort[i]}},'
      f'longVis:te&&(o||l<{q(t_drop + 0.2, 3)}),shortVis:te&&(o||l<20.4)}}),')
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
    # AFR 판은 상류 빈자리에 있었다. REV.48 부터 자리를 **존 중심**에서 낸다:
    # 리터럴(6.1 · 11)로 박아 두면 셀이 격자 위로 올 때 판만 옛 자리에 남는다
    # (실제로 8.4 m · 5.8 m 어긋나 있었다). 생성기가 존 식을 다시 써 넣는다.
    # REV.50: 후단 셀의 기계는 GI-301/302 다 — SG-301 은 AFR 반출롤러 위로 갔다.
    for var, cell, name in (("pdAfr", "afr", "AFR-101"), ("pdPos", "post", "GI-302")):
        pat = re.compile(r"window\." + var + r"=pvNamePlate\(g,([\d.]+),"
                         r"\[[^,]+,([\d.]+),([\d.]+)\],0,'" + name + r"'")
        assert len(pat.findall(text)) == 1, f"명판 앵커 {name}"
        text = pat.sub(lambda m, c=cell, v=var, n=name:
                       f"window.{v}=pvNamePlate(g,{m.group(1)},"
                       f"[(pvZone.{c}[0]+pvZone.{c}[1])/2,{m.group(2)},{m.group(3)}],0,'{n}'",
                       text, count=1)

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

    # 앵커는 파일 전체에서 찾는다. 종전에는 "AFR-101 이 든 가장 긴 줄" 하나를
    # 골라 그 안에서 잘랐는데, 주석 한 줄이 들어가 번들 줄이 갈리자 형상 블록과
    # 애니메이션이 서로 다른 줄로 나뉘어 생성기가 자기 자리를 못 찾았다.
    # 각 구간은 그 자체로 유일한 문자열 사이에 있다.
    def span(start: str, end: str, *, keep_end: bool) -> tuple[int, int]:
        assert text.count(start) == 1, f"앵커 {text.count(start)}곳: {start}"
        assert text.count(end) == 1, f"앵커 {text.count(end)}곳: {end}"
        i = text.index(start)
        j = text.index(end) + (len(end) if keep_end else 0)
        assert i < j, (start, end)
        return i, j

    a0, a1 = span("w0(r);", "eu.visible=a&&l>=31.2,eu.scale.y=le(.2,1,x);", keep_end=True)
    text = text[:a0] + build_anim() + text[a1:]
    b0, b1 = span("var Pu=[];", "/* @afr-block-end", keep_end=False)
    text = text[:b0] + build_block() + text[b1:]

    # 시험 훅도 모델값으로 맞춘다.
    assert text.count(HOOK_OLD) + text.count(build_hook()) == 1, "시험 훅 앵커"
    text = text.replace(HOOK_OLD, build_hook())

    text = patch_prose(text)
    DRAWING.write_text(text, encoding="utf-8")
    print(f"AFR 3D 블록 재생성 — 빌드 {len(build_block()):,} 자 · "
          f"애니 {len(build_anim()):,} 자")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
