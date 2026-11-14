"""SolidCraft 레이아웃(.sc) → 단독 실행 3D 뷰어 HTML 변환기.

.sc 파일은 zip 컨테이너다.

    document.json   부품(component)·배치(occurrence)·피처(box/cylinder/cut/remove/import)·외관색
    blobs/*.step    import 피처가 참조하는 STEP 원본 (AP242, mm)
    blobs/*.mesh    mesh_import 피처가 참조하는 삼각망 (SCMESH01)

이 스크립트는 피처 이력을 재생해 각 부품의 솔리드를 만들고(OpenCascade), 삼각망으로
분할해 양자화·gzip 한 뒤 HTML 하나에 base64 로 심는다. 같은 부품을 여러 번 배치한
경우(로봇 2대, 가공기 2대, 대기 테이블 2대) 형상은 한 번만 저장하고 배치 변환만 둔다.

필요 패키지:  pip install cadquery-ocp numpy

    python tools/sc_layout_to_3d.py layout.sc docs/layout/new-line-layout-3d.html
"""

from __future__ import annotations

import argparse
import base64
import gzip
import io
import json
import math
import pathlib
import re
import struct
import sys
import time
import zipfile

import numpy as np

from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder

DEFAULT_RGB = (0.62, 0.66, 0.70)
LIN_DEFLECTION = 0.6      # mm
ANG_DEFLECTION = 0.45     # rad


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, file=sys.stderr, flush=True)


# ── 수식 파라미터 ("(20 mm) / 2" 같은 값) ───────────────────────────────────────
_EXPR_OK = re.compile(r"^[0-9.eE+\-*/() ]+$")


def num(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("mm", "")
    if not _EXPR_OK.match(s):
        raise ValueError(f"지원하지 않는 수식: {v!r}")
    return float(eval(s, {"__builtins__": {}}, {}))  # 숫자·사칙연산만 통과


# ── STEP 색상 (STYLED_ITEM → … → COLOUR_RGB) ──────────────────────────────────
_ENT = re.compile(r"^#(\d+)=(.*);\s*$")
_REF = re.compile(r"#(\d+)")


def step_solid_colours(text: str) -> dict[str, tuple]:
    """솔리드 이름 → RGB. STEP 엔티티 참조를 따라가 첫 COLOUR_RGB 를 쓴다."""
    ents = {}
    for line in text.split("\n"):
        m = _ENT.match(line)
        if m:
            ents[int(m.group(1))] = m.group(2)
    solid_name = {}
    for k, body in ents.items():
        if body.startswith("MANIFOLD_SOLID_BREP("):
            solid_name[k] = re.match(r"MANIFOLD_SOLID_BREP\('((?:[^']|'')*)'", body).group(1)

    def colour_of(eid, depth=0):
        body = ents.get(eid, "")
        if body.startswith("COLOUR_RGB("):
            vals = body[body.index(",") + 1:-1].split(",")
            return tuple(float(x) for x in vals)
        if depth > 8:
            return None
        for r in _REF.findall(body):
            c = colour_of(int(r), depth + 1)
            if c:
                return c
        return None

    out = {}
    for body in ents.values():
        if body.startswith("STYLED_ITEM("):
            refs = [int(r) for r in _REF.findall(body)]
            target = refs[-1]
            if target in solid_name:
                c = colour_of(refs[0])
                if c:
                    out.setdefault(solid_name[target], c)
    return out


def decode_step_name(s: str) -> str:
    """STEP \\X2\\hhhh\\X0\\ 인코딩 해제."""
    def rep(m):
        h = m.group(1)
        return "".join(chr(int(h[i:i + 4], 16)) for i in range(0, len(h), 4))
    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", rep, s)


def read_step_solids(path: pathlib.Path) -> list:
    """STEP → 솔리드 목록. 읽기가 느리므로(큰 파일은 수 분) 결과를 .brep 으로 캐시한다."""
    cache = path.with_suffix(".brep")
    if cache.exists():
        shape = TopoDS_Shape()
        BRepTools.Read_s(shape, str(cache), BRep_Builder())
        return _solids(shape)
    Interface_Static.SetIVal_s("read.step.product.mode", 1)
    r = STEPControl_Reader()
    if r.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP 읽기 실패: {path}")
    r.TransferRoots()
    shape = r.OneShape()
    BRepTools.Write_s(shape, str(cache))
    return _solids(shape)


def _solids(shape) -> list:
    solids = []
    e = TopExp_Explorer(shape, TopAbs_SOLID)
    while e.More():
        solids.append(TopoDS.Solid(e.Current()))
        e.Next()
    return solids


# ── 삼각망 ──────────────────────────────────────────────────────────────────
def tessellate(shape):
    """솔리드 → (positions[N,3], normals[N,3], tris[M,3]) float64/int."""
    BRepMesh_IncrementalMesh(shape, LIN_DEFLECTION, False, ANG_DEFLECTION, True)
    P, N, T = [], [], []
    base = 0
    e = TopExp_Explorer(shape, TopAbs_FACE)
    while e.More():
        face = TopoDS.Face(e.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        e.Next()
        if tri is None or tri.NbTriangles() == 0:
            continue
        trsf = loc.Transformation()
        nn = tri.NbNodes()
        pts = np.empty((nn, 3))
        for i in range(1, nn + 1):
            p = tri.Node(i).Transformed(trsf)
            pts[i - 1] = (p.X(), p.Y(), p.Z())
        nt = tri.NbTriangles()
        tt = np.empty((nt, 3), dtype=np.int64)
        for i in range(1, nt + 1):
            a, b, c = tri.Triangle(i).Get()
            tt[i - 1] = (a - 1, b - 1, c - 1)
        if face.Orientation() == TopAbs_REVERSED:
            tt = tt[:, [0, 2, 1]]
        # 면 내부 평균 법선 (면 경계에서는 꺾임 유지)
        fn = np.cross(pts[tt[:, 1]] - pts[tt[:, 0]], pts[tt[:, 2]] - pts[tt[:, 0]])
        vn = np.zeros_like(pts)
        for k in range(3):
            np.add.at(vn, tt[:, k], fn)
        ln = np.linalg.norm(vn, axis=1, keepdims=True)
        ln[ln == 0] = 1
        P.append(pts)
        N.append(vn / ln)
        T.append(tt + base)
        base += nn
    if not P:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    return np.vstack(P), np.vstack(N), np.vstack(T)


def read_scmesh(raw: bytes):
    assert raw[:8] == b"SCMESH01", "SCMESH01 아님"
    ncoord, nidx = struct.unpack_from("<QQ", raw, 8)
    pos = np.frombuffer(raw, dtype="<f8", count=ncoord, offset=24).reshape(-1, 3)
    idx = np.frombuffer(raw, dtype="<u4", count=nidx, offset=24 + 8 * ncoord).reshape(-1, 3)
    fn = np.cross(pos[idx[:, 1]] - pos[idx[:, 0]], pos[idx[:, 2]] - pos[idx[:, 0]])
    # 평탄 음영(정점 공유 해제) — 원본 glb 가 하드 엣지 기반이라 스무딩하면 번진다
    P = pos[idx.reshape(-1)]
    ln = np.linalg.norm(fn, axis=1, keepdims=True)
    ln[ln == 0] = 1
    Nn = np.repeat(fn / ln, 3, axis=0)
    T = np.arange(len(P)).reshape(-1, 3)
    return P, Nn, T


# ── 패킹 ────────────────────────────────────────────────────────────────────
def oct_encode(n):
    n = n / np.maximum(np.abs(n).sum(axis=1, keepdims=True), 1e-12)
    x, y, z = n[:, 0], n[:, 1], n[:, 2]
    ox = np.where(z >= 0, x, (1 - np.abs(y)) * np.sign(x + 1e-30))
    oy = np.where(z >= 0, y, (1 - np.abs(x)) * np.sign(y + 1e-30))
    return np.clip(np.round(np.stack([ox, oy], 1) * 127), -127, 127).astype(np.int8)


def pack_component(bodies):
    """bodies: [(name, rgb, P, N, T)] → (bytes, meta)."""
    P = np.vstack([b[2] for b in bodies])
    lo, hi = P.min(0), P.max(0)
    span = np.maximum(hi - lo, 1e-6)
    pos, nrm, bid, idx = [], [], [], []
    base = 0
    for i, (_, _, p, n, t) in enumerate(bodies):
        pos.append(np.round((p - lo) / span * 65535).astype(np.uint16))
        nrm.append(oct_encode(n))
        bid.append(np.full(len(p), i, np.uint16))
        idx.append((t + base).astype(np.uint32))
        base += len(p)
    pos, nrm, bid, idx = map(np.concatenate, (pos, nrm, bid, idx))
    buf = io.BytesIO()
    for arr in (pos, nrm, bid, idx):
        b = arr.tobytes()
        buf.write(b)
        buf.write(b"\0" * (-len(b) % 4))
    meta = {
        "nv": int(len(pos)), "nt": int(len(idx)),
        "lo": [round(float(v), 3) for v in lo], "span": [round(float(v), 4) for v in span],
        "names": [b[0] for b in bodies],
        "colors": [[round(float(c), 3) for c in b[1]] for b in bodies],
    }
    return buf.getvalue(), meta


# ── 메인 ────────────────────────────────────────────────────────────────────
def build(sc_path: pathlib.Path, workdir: pathlib.Path):
    z = zipfile.ZipFile(sc_path)
    doc = json.loads(z.read("document.json"))
    appear = doc["appearances"]["bodies"]
    user_mats = {m["name"]: m["appearance"]["color"] for m in doc.get("user_materials", [])}
    materials = doc.get("materials", {})

    def doc_colour(name, fallback=None):
        if name in appear:
            return tuple(c / 255 for c in appear[name]["color"])
        m = materials.get(name)
        if m in user_mats:
            return tuple(c / 255 for c in user_mats[m])
        return fallback or DEFAULT_RGB

    comps = {c["id"]: c for c in doc["components"]}
    # 부품별 바디: name → [shape|mesh, rgb]
    shapes: dict[int, dict[str, list]] = {cid: {} for cid in comps}

    for f in doc["features"]:
        if f.get("suppressed"):
            continue
        t = f["type"]
        if t == "import":
            blob = workdir / f["step_blob"]
            if not blob.exists():
                blob.parent.mkdir(parents=True, exist_ok=True)
                blob.write_bytes(z.read(f["step_blob"]))
            log("STEP 읽기", f["name"], blob.stat().st_size // 1024, "KB")
            text = blob.read_text(encoding="latin-1")
            colours = step_solid_colours(text)
            solids = read_step_solids(blob)
            names = f["body_names"]
            assert len(solids) == len(names), (f["name"], len(solids), len(names))
            for s, n in zip(solids, names):
                shapes[f["component"]][n] = [s, doc_colour(n, colours.get(n))]
        elif t == "mesh_import":
            for m in f["meshes"]:
                owner = doc["body_components"].get(m["name"], f["component"])
                P, N, T = read_scmesh(z.read(m["mesh_blob"]))
                shapes[owner][m["name"]] = [("mesh", P, N, T), tuple(m["color"])]
        elif t in ("box", "cylinder"):
            if t == "box":
                c = f["corner"]
                s = BRepPrimAPI_MakeBox(gp_Pnt(*c), num(f["length"]), num(f["width"]),
                                        num(f["height"])).Shape()
            else:
                ax = gp_Ax2(gp_Pnt(*f["base"]), gp_Dir(*f["axis"]))
                s = BRepPrimAPI_MakeCylinder(ax, num(f["radius"]), num(f["height"])).Shape()
            if f["operation"] == "new_body":
                n = f["body_names"][0]
                shapes[f["component"]][n] = [s, doc_colour(n)]
            elif f["operation"] == "cut":
                for n in f["participants"]:
                    ent = shapes[f["component"]][n]
                    ent[0] = BRepAlgoAPI_Cut(ent[0], s).Shape()
            else:
                raise ValueError(f["operation"])
        elif t == "remove":
            for n in f["bodies"]:
                for d in shapes.values():
                    d.pop(n, None)
        else:
            raise ValueError(f"미지원 피처 {t}")

    hidden = set(doc["visibility"].get("hidden_bodies", []))
    packed, comp_meta = [], {}
    for cid, d in shapes.items():
        if not d:
            continue
        log("삼각망", comps[cid]["name"], len(d), "bodies")
        bodies = []
        for n, (s, rgb) in d.items():
            if n in hidden:
                continue
            if isinstance(s, tuple) and s[0] == "mesh":
                P, N, T = s[1:]
            else:
                P, N, T = tessellate(s)
            if len(T):
                bodies.append((n, rgb, P, N, T))
        data, meta = pack_component(bodies)
        meta["offset"] = sum(len(p) for p in packed)
        meta["bytes"] = len(data)
        meta["name"] = comps[cid]["name"]
        meta["desc"] = (comps[cid].get("metadata") or {}).get("description", "")
        meta["bom"] = (comps[cid].get("metadata") or {}).get("bom_type", "")
        packed.append(data)
        comp_meta[cid] = meta
        log("  ", meta["nv"], "verts", meta["nt"] // 3, "tris", len(data) // 1024, "KB")

    # 배치: 최상위 occurrence + 부품 내부 하위 occurrence 를 전개해 월드 행렬로
    occs = doc["occurrences"]

    def mat(o):  # 행 벡터 규약: p' = p·R + t  → 열 기준 4x4 로 변환
        return np.array(o["transform"], float).T

    def expand(parent_comp, M, label):
        out = []
        for o in occs:
            if o["parent"] != parent_comp:
                continue
            W = M @ mat(o)
            cid = o["component"]
            if cid in comp_meta:
                out.append({"c": cid, "m": [round(float(v), 4) for v in W.T.reshape(-1)],
                            "label": label or o["name"]})
            out += expand(cid, W, label or o["name"])
        return out

    instances = expand(0, np.eye(4), None)
    blob = gzip.compress(b"".join(packed), 9)
    meta = {
        "name": doc.get("name"),
        "layout": (doc.get("metadata") or {}).get("com.openai.layout", {}),
        "components": {str(k): v for k, v in comp_meta.items()},
        "instances": instances,
        "occurrences": [{"name": o["name"], "c": o["component"], "parent": o["parent"]}
                        for o in occs],
    }
    return meta, blob


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sc", type=pathlib.Path)
    ap.add_argument("out", type=pathlib.Path)
    ap.add_argument("--template", type=pathlib.Path,
                    default=pathlib.Path(__file__).with_name("sc_layout_viewer.html"))
    ap.add_argument("--work", type=pathlib.Path, default=pathlib.Path(".sc_work"))
    ap.add_argument("--reuse", action="store_true", help="작업 폴더의 이전 변환 결과로 HTML 만 다시 생성")
    a = ap.parse_args(argv)
    cache_m, cache_b = a.work / "meta.json", a.work / "geometry.bin.gz"
    if a.reuse and cache_m.exists() and cache_b.exists():
        meta, blob = json.loads(cache_m.read_text(encoding="utf-8")), cache_b.read_bytes()
    else:
        meta, blob = build(a.sc, a.work)
        a.work.mkdir(parents=True, exist_ok=True)
        cache_m.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        cache_b.write_bytes(blob)
    html = a.template.read_text(encoding="utf-8")
    html = html.replace("/*__META__*/null", json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__GEOMETRY_B64__", base64.b64encode(blob).decode())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(html, encoding="utf-8")
    log("완료", a.out, len(html) // 1024, "KB")


if __name__ == "__main__":
    main()
