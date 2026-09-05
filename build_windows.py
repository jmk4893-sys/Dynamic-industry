"""윈도우 실행파일(BlastSim.exe) 빌드 스크립트.

윈도우에서 실행:

    pip install -r requirements.txt pyinstaller
    python build_windows.py

결과: dist\\BlastSim.exe  (단일 실행파일, 파이썬 설치 불필요)

주의
----
* 반드시 **윈도우에서** 돌려야 한다. PyInstaller 는 크로스 빌드를 지원하지 않아
  리눅스에서 만들면 리눅스 실행파일이 나온다.
* matplotlib · scipy · imageio-ffmpeg 가 포함되어 결과물이 300~500 MB 가 된다.
  용량을 줄이려면 --onedir 로 바꾸고 폴더째 배포하는 편이 낫다.
* 첫 실행은 압축 해제 때문에 10~20초 걸린다 (--onedir 는 즉시 뜬다).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

APP = "BlastSim"
ENTRY = "blastsim_main.py"

ENTRY_SRC = '''"""BlastSim 실행 진입점 (PyInstaller 용)."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from blastsim.gui import main
    sys.exit(main())
'''


def _hidden_imports() -> list[str]:
    mods = [
        "blastsim", "blastsim.gui", "blastsim.project", "blastsim.fdm",
        "blastsim.frag", "blastsim.render", "blastsim.plots", "blastsim.rock",
        "blastsim.explosives", "blastsim.pattern", "blastsim.empirical",
        "blastsim.sensors", "blastsim.lattice", "blastsim.solver",
        "blastsim.source", "blastsim.simulation",
        "scipy.spatial", "scipy.sparse.csgraph", "scipy.special",
        "matplotlib.backends.backend_agg", "imageio", "imageio_ffmpeg",
    ]
    out = []
    for m in mods:
        out += ["--hidden-import", m]
    return out


def main() -> int:
    if not sys.platform.startswith("win"):
        print("!! 이 스크립트는 윈도우에서 실행해야 합니다.")
        print("   PyInstaller 는 크로스 빌드를 지원하지 않습니다.")
        print("   (참고: 아래 명령을 윈도우에서 그대로 쓰면 됩니다)\n")

    with open(ENTRY, "w", encoding="utf-8") as f:
        f.write(ENTRY_SRC)

    onefile = "--onedir" not in sys.argv
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--name", APP, "--windowed",
           "--onefile" if onefile else "--onedir"]
    cmd += _hidden_imports()
    # imageio-ffmpeg 가 들고 있는 ffmpeg 바이너리를 함께 넣는다
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd += ["--add-binary", f"{exe}{os.pathsep}imageio_ffmpeg/binaries"]
    except Exception:
        print("   (imageio-ffmpeg 없음 — mp4 대신 gif 로 저장됩니다)")
    cmd += [ENTRY]

    print("빌드 명령:\n  " + " ".join(cmd) + "\n")
    if not sys.platform.startswith("win"):
        return 0

    if shutil.which("pyinstaller") is None:
        try:
            import PyInstaller  # noqa: F401
        except ImportError:
            print("!! PyInstaller 가 없습니다:  pip install pyinstaller")
            return 1
    rc = subprocess.call(cmd)
    if rc == 0:
        print(f"\n완료:  dist\\{APP}.exe")
    return rc


if __name__ == "__main__":
    sys.exit(main())
