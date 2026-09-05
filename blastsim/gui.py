"""BlastSim 테스트버전 — 윈도우 GUI.

tkinter 만 쓰므로 윈도우 기본 파이썬에서 별도 설치 없이 뜬다.
해석은 작업 스레드에서 돌리고, 솔버가 찍는 진행률(stdout)을 큐로 받아
로그창에 흘린다. 그래야 해석 중에도 창이 얼지 않는다.

    python -m blastsim.gui          (또는 빌드된 BlastSim.exe)
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .empirical import SD_LAWS
from .explosives import EXPLOSIVE_DB
from .project import QUALITY_PRESETS, BlastProject, ProjectConfig
from .rock import ROCK_DB

APP_TITLE = "BlastSim  —  발파 진동·파쇄·비산 통합 해석  [테스트버전]"


class _QueueWriter:
    """솔버의 print 출력을 큐로 보낸다 ('\\r' 진행률 포함)."""

    def __init__(self, q: queue.Queue) -> None:
        self.q = q

    def write(self, s: str) -> int:
        if s:
            self.q.put(("log", s))
        return len(s)

    def flush(self) -> None:
        pass


def _open_folder(path: str) -> None:
    path = os.path.abspath(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)                     # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class BlastSimApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1020x760")
        self.minsize(900, 640)
        self.q: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.project: BlastProject | None = None
        self.vars: dict[str, tk.Variable] = {}
        self._build()
        self.after(80, self._poll)

    # ---- 위젯 --------------------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="both", expand=True)

        banner = ttk.Label(
            top, text="테스트버전 — 절대 진동값은 시험발파 실측으로 보정한 뒤 사용하십시오.",
            foreground="#a03000")
        banner.pack(anchor="w", pady=(0, 6))

        body = ttk.Frame(top)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 8))
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self._build_inputs(left)
        self._build_run(left)
        self._build_log(right)

    def _row(self, parent, r, label, key, default, width=9, unit=""):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=1)
        v = tk.StringVar(value=str(default))
        self.vars[key] = v
        ttk.Entry(parent, textvariable=v, width=width).grid(row=r, column=1,
                                                            sticky="w", padx=4)
        if unit:
            ttk.Label(parent, text=unit).grid(row=r, column=2, sticky="w")
        return v

    def _combo(self, parent, r, label, key, values, default, width=16):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=1)
        v = tk.StringVar(value=default)
        self.vars[key] = v
        ttk.Combobox(parent, textvariable=v, values=values, width=width,
                     state="readonly").grid(row=r, column=1, columnspan=2,
                                            sticky="w", padx=4)
        return v

    def _build_inputs(self, parent) -> None:
        f = ttk.LabelFrame(parent, text=" 암반 ", padding=6)
        f.pack(fill="x", pady=3)
        self._combo(f, 0, "암종", "rock", list(ROCK_DB), "granite")
        self._row(f, 1, "Vp (선택)", "vp", "", unit="m/s")
        self._row(f, 2, "포아송비", "poisson", 0.25)
        self._row(f, 3, "감쇠비 (선택)", "damping", "")

        f = ttk.LabelFrame(parent, text=" 폭약 · 천공 ", padding=6)
        f.pack(fill="x", pady=3)
        self._combo(f, 0, "폭약", "explosive", list(EXPLOSIVE_DB), "emulsion")
        self._row(f, 1, "천공경", "hole_dia", 76, unit="mm")
        self._row(f, 2, "장약경 (선택)", "charge_dia", "", unit="mm")
        self._row(f, 3, "공당 장약량 (선택)", "charge_kg", "", unit="kg")

        f = ttk.LabelFrame(parent, text=" 발파 패턴 ", padding=6)
        f.pack(fill="x", pady=3)
        self._row(f, 0, "저항선 B", "burden", 3.0, unit="m")
        self._row(f, 1, "공간격 S", "spacing", 3.5, unit="m")
        self._row(f, 2, "벤치고 H", "bench", 10.0, unit="m")
        self._row(f, 3, "열 수", "rows", 2)
        self._row(f, 4, "열당 공 수", "cols", 5)
        self._row(f, 5, "전색장 (선택)", "stemming", "", unit="m")
        self._row(f, 6, "공간 시차", "delay_hole", 25, unit="ms")
        self._row(f, 7, "열간 시차", "delay_row", 65, unit="ms")

        f = ttk.LabelFrame(parent, text=" 조건 ", padding=6)
        f.pack(fill="x", pady=3)
        self.vars["full_stem"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="완전 전색", variable=self.vars["full_stem"]).grid(
            row=0, column=0, columnspan=3, sticky="w")
        self.vars["two_face"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="2자유면 (상부면 + 벤치면)",
                        variable=self.vars["two_face"]).grid(
            row=1, column=0, columnspan=3, sticky="w")
        self._row(f, 2, "계측거리", "distances", "30 50 80 120", width=18, unit="m")

    def _build_run(self, parent) -> None:
        f = ttk.LabelFrame(parent, text=" 해석 ", padding=6)
        f.pack(fill="x", pady=3)
        self.vars["do_vib"] = tk.BooleanVar(value=True)
        self.vars["do_frag"] = tk.BooleanVar(value=True)
        self.vars["do_video"] = tk.BooleanVar(value=True)
        self.vars["do_cal"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="FDM 원거리 진동", variable=self.vars["do_vib"]).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(f, text="DEM 근거리 파쇄·비산",
                        variable=self.vars["do_frag"]).grid(row=1, column=0,
                                                            columnspan=3, sticky="w")
        ttk.Checkbutton(f, text="영상 생성 (mp4)", variable=self.vars["do_video"]).grid(
            row=2, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(f, text="경험식으로 폭원 보정",
                        variable=self.vars["do_cal"]).grid(row=3, column=0,
                                                           columnspan=3, sticky="w")
        self._combo(f, 4, "품질", "quality", list(QUALITY_PRESETS), "빠름", width=10)
        self._combo(f, 5, "비교 경험식", "law", list(SD_LAWS), "kr_mean", width=12)

        of = ttk.Frame(f)
        of.grid(row=6, column=0, columnspan=3, sticky="we", pady=(6, 0))
        self.vars["outdir"] = tk.StringVar(value=os.path.abspath("output"))
        ttk.Entry(of, textvariable=self.vars["outdir"], width=24).pack(side="left")
        ttk.Button(of, text="…", width=3, command=self._pick_dir).pack(side="left")

        bf = ttk.Frame(parent)
        bf.pack(fill="x", pady=6)
        self.btn_run = ttk.Button(bf, text="해석 실행", command=self._start)
        self.btn_run.pack(side="left")
        self.btn_open = ttk.Button(bf, text="결과 폴더", command=self._open_out,
                                   state="disabled")
        self.btn_open.pack(side="left", padx=4)
        self.progress = ttk.Progressbar(parent, mode="indeterminate")
        self.progress.pack(fill="x")

    def _build_log(self, parent) -> None:
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)
        lf = ttk.Frame(nb)
        nb.add(lf, text=" 진행 로그 ")
        self.log = tk.Text(lf, wrap="none", font=("Consolas", 9), bg="#101418",
                           fg="#d8dee4", insertbackground="#d8dee4")
        sb = ttk.Scrollbar(lf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        rf = ttk.Frame(nb)
        nb.add(rf, text=" 결과 보고 ")
        self.report = tk.Text(rf, wrap="none", font=("Consolas", 9))
        sb2 = ttk.Scrollbar(rf, command=self.report.yview)
        self.report.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y")
        self.report.pack(fill="both", expand=True)
        self.nb = nb

    # ---- 입력 수집 ---------------------------------------------------------
    def _pick_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.vars["outdir"].get() or ".")
        if d:
            self.vars["outdir"].set(d)

    def _f(self, key, default=None):
        s = self.vars[key].get().strip()
        if not s:
            return default
        try:
            return float(s)
        except ValueError:
            raise ValueError(f"'{key}' 값을 숫자로 읽을 수 없습니다: {s}")

    def _config(self) -> ProjectConfig:
        dist = [float(x) for x in self.vars["distances"].get().replace(",", " ").split()]
        if not dist:
            raise ValueError("계측거리를 하나 이상 입력하세요.")
        return ProjectConfig(
            rock_key=self.vars["rock"].get(),
            vp=self._f("vp"), poisson=self._f("poisson", 0.25),
            damping_ratio=self._f("damping"),
            explosive_key=self.vars["explosive"].get(),
            hole_dia_mm=self._f("hole_dia", 76.0),
            charge_dia_mm=self._f("charge_dia"),
            charge_kg=self._f("charge_kg"),
            burden=self._f("burden", 3.0), spacing=self._f("spacing", 3.5),
            bench_height=self._f("bench", 10.0),
            n_rows=int(self._f("rows", 2)), n_cols=int(self._f("cols", 5)),
            stemming=self._f("stemming"),
            delay_hole_ms=self._f("delay_hole", 25.0),
            delay_row_ms=self._f("delay_row", 65.0),
            full_stemming=bool(self.vars["full_stem"].get()),
            two_free_face=bool(self.vars["two_face"].get()),
            distances=dist,
            quality=self.vars["quality"].get(),
            run_vibration=bool(self.vars["do_vib"].get()),
            run_fragmentation=bool(self.vars["do_frag"].get()),
            make_video=bool(self.vars["do_video"].get()),
            calibrate=bool(self.vars["do_cal"].get()),
            law=self.vars["law"].get(),
            outdir=self.vars["outdir"].get() or "output",
        )

    # ---- 실행 --------------------------------------------------------------
    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "이미 해석이 진행 중입니다.")
            return
        try:
            cfg = self._config()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"입력 오류\n\n{exc}")
            return
        self.log.delete("1.0", "end")
        self.report.delete("1.0", "end")
        self.btn_run.configure(state="disabled")
        self.btn_open.configure(state="disabled")
        self.progress.start(12)
        self.nb.select(0)
        self.worker = threading.Thread(target=self._work, args=(cfg,), daemon=True)
        self.worker.start()

    def _work(self, cfg: ProjectConfig) -> None:
        old = sys.stdout
        sys.stdout = _QueueWriter(self.q)
        try:
            proj = BlastProject(cfg)
            proj.run_all(log=lambda m="": print(m))
            self.q.put(("done", proj))
        except Exception:
            self.q.put(("error", traceback.format_exc()))
        finally:
            sys.stdout = old

    # ---- 큐 처리 -----------------------------------------------------------
    def _append(self, s: str) -> None:
        # 솔버 진행률은 '\r' 로 같은 줄을 덮어쓴다
        for part in s.split("\r"):
            if part is s.split("\r")[0] and "\r" not in s:
                self.log.insert("end", part)
            else:
                self.log.delete("end-1l linestart", "end-1c")
                self.log.insert("end", part)
        self.log.see("end")

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._append(payload)
                elif kind == "done":
                    self.project = payload
                    self.progress.stop()
                    self.btn_run.configure(state="normal")
                    self.btn_open.configure(state="normal")
                    self.report.delete("1.0", "end")
                    self.report.insert("1.0", payload.report())
                    self.nb.select(1)
                elif kind == "error":
                    self.progress.stop()
                    self.btn_run.configure(state="normal")
                    self._append("\n" + payload)
                    messagebox.showerror(APP_TITLE, "해석 중 오류가 발생했습니다.\n"
                                                    "진행 로그를 확인하세요.")
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _open_out(self) -> None:
        _open_folder(self.vars["outdir"].get())


def main() -> int:
    app = BlastSimApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
