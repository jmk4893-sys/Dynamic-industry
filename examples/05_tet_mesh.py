"""예제 5 — 천공홀을 포함한 3D 사면체 메쉬 생성.

20 x 20 x 20 m 직육면체 암반을 불규칙 사면체로 채우고, 그 안에
Ø75 mm x 12 m 원통형 천공홀을 형상 그대로 표현한다.

출력
----
    output/05_mesh/mesh.vtk   ParaView / VisIt 용 (region, quality 포함)
    output/05_mesh/mesh.msh   Gmsh 2.2 (물리그룹 rock / borehole)
    output/05_mesh/wall.vtk   공벽 재하면(삼각형)만 추출한 표면
    output/05_mesh/mesh.png   단면 · 확대 · 크기장 · 품질 진단도
    output/05_mesh/mesh3d.png 3D 사분절개 · 공벽 반절개 · 재하면
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from blastsim.mesh import Borehole, BoxDomain, MeshConfig, build_tet_mesh
from blastsim.plots import plot_tet_mesh, plot_tet_mesh_3d

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "05_mesh")
os.makedirs(OUT, exist_ok=True)

domain = BoxDomain.from_size(20.0, 20.0, 20.0)     # 폭 x 세로 x 깊이 [m]
hole = Borehole(collar=(0.0, 0.0, 0.0), axis=(0.0, 0.0, -1.0),
                length=12.0, diameter=0.075)       # Ø75 mm x 12 m 연직공

# h_far/growth 를 낮추면 조밀해진다. MESH_PRESETS 의 "빠름"/"보통"/"정밀" 도 가능.
mesh = build_tet_mesh(domain, hole, MeshConfig(h_far=1.0, growth=0.6, n_theta=12))

print(mesh.summary())

mesh.write_vtk(os.path.join(OUT, "mesh.vtk"))
mesh.write_msh(os.path.join(OUT, "mesh.msh"))
plot_tet_mesh(mesh, os.path.join(OUT, "mesh.png"))
plot_tet_mesh_3d(mesh, os.path.join(OUT, "mesh3d.png"))

# 공벽(재하면)만 따로 저장 — 폭굉 가스압을 걸 표면이다.
wall = mesh.hole_wall_facets()
with open(os.path.join(OUT, "wall.vtk"), "w", encoding="ascii") as f:
    f.write("# vtk DataFile Version 3.0\nborehole wall\nASCII\n"
            "DATASET UNSTRUCTURED_GRID\n")
    f.write(f"POINTS {mesh.n_points} double\n")
    np.savetxt(f, mesh.points, fmt="%.9g")
    f.write(f"\nCELLS {len(wall)} {4 * len(wall)}\n")
    np.savetxt(f, np.hstack([np.full((len(wall), 1), 3), wall]), fmt="%d")
    f.write(f"\nCELL_TYPES {len(wall)}\n")
    np.savetxt(f, np.full(len(wall), 5), fmt="%d")

print(f"\n출력 폴더: {os.path.abspath(OUT)}")
