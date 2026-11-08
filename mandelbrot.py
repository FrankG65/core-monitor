"""Mandelbrot computation as a real, parallel workload.

The image is split into tiles, which are computed by a process pool
(ProcessPoolExecutor). Each tile is coloured in the worker and returned as
RGB bytes. Computation methods: numba (JIT, if installed), otherwise numpy
(vectorised).

This module is also imported in the worker processes and therefore has no
side effects on import.
"""
from __future__ import annotations

import base64
import csv
import ctypes
import json
import multiprocessing
import os
import shutil
import statistics
import subprocess
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np

import worker_util
from i18n import L

try:
    from numba import njit
    HAVE_NUMBA = True
except Exception:  # numba missing or not matching the Python version
    HAVE_NUMBA = False

CSHARP_PROJECT = Path(__file__).parent / "csharp" / "MandelBench"
CSHARP_DLL = Path(__file__).parent / "csharp" / "bin" / "MandelBench.dll"
CSHARP_EXE = Path(__file__).parent / "csharp" / "bin" / "MandelBench.exe"  # self-contained (package "Full"), no .NET needed
DOTNET = shutil.which("dotnet")
HAVE_DOTNET = (DOTNET is not None and CSHARP_PROJECT.exists()) or CSHARP_EXE.exists()
RUST_PROJECT = Path(__file__).parent / "rust" / "mandelbench"
RUST_EXE = RUST_PROJECT / "target" / "release" / ("mandelbench.exe" if os.name == "nt" else "mandelbench")
_cargo_home = Path.home() / ".cargo" / "bin" / ("cargo.exe" if os.name == "nt" else "cargo")
CARGO = shutil.which("cargo") or (str(_cargo_home) if _cargo_home.exists() else None)  # rustup may not update PATH
HAVE_RUST = RUST_PROJECT.exists() and (CARGO is not None or RUST_EXE.exists())
NATIVE_DIR = Path(__file__).parent / "native"
NATIVE_EXE = {"c": NATIVE_DIR / "bin" / "mandel_c.exe", "cpp": NATIVE_DIR / "bin" / "mandel_cpp.exe",
              "asm": NATIVE_DIR / "bin" / "mandel_asm.exe", "gpu": NATIVE_DIR / "bin" / "mandel_gpu.exe"}
_vswhere = Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
HAVE_NATIVE = os.name == "nt" and NATIVE_DIR.exists() and (_vswhere.exists() or any(e.exists() for e in NATIVE_EXE.values()))
# per program: if only one .exe is missing (e.g. quarantine), the others remain usable
_NATIVE_ENGINES = {"c": "c", "c_simd": "c", "cpp": "cpp", "cpp_simd": "cpp", "asm": "asm", "gpu": "gpu", "gpu_float": "gpu"}
ENGINES = ((["numba"] if HAVE_NUMBA else []) + ["numpy"] + (["csharp", "csharp_simd"] if HAVE_DOTNET else [])
           + (["rust", "rust_simd"] if HAVE_RUST else [])
           + [e for e, b in _NATIVE_ENGINES.items() if HAVE_NATIVE and (_vswhere.exists() or NATIVE_EXE[b].exists())])
EXTERNAL = ("csharp", "rust", "c", "cpp", "asm", "gpu")  # computation methods as a separate program (threads or GPU)
ALL_ENGINES = ["numba", "numpy", "csharp", "csharp_simd", "rust", "rust_simd",
               "c", "c_simd", "cpp", "cpp_simd", "asm", "gpu", "gpu_float"]


def missing_reason(engine: str) -> str | None:
    """Why a computation method is not installed on this PC (None = available)."""
    if engine in ENGINES:
        return None
    base = engine_base(engine)
    if base != "numba" and (Path(__file__).parent / "python" / "python.exe").exists():
        # package "Full" ships all programs – if one is missing, an antivirus has usually removed it
        return L("Programm fehlt – vermutlich von einem Virenscanner in Quarantäne verschoben (unbegründet, siehe INSTALLATION.de.txt)",
                 "Program missing – probably moved to quarantine by an antivirus (unfounded, see INSTALLATION.txt)")
    return {"numba": L("numba nicht installiert (pip install numba)", "numba not installed (pip install numba)"),
            "csharp": L(".NET SDK nicht installiert (siehe INSTALLATION.de.txt)", ".NET SDK not installed (see INSTALLATION.txt)"),
            "rust": L("Rust nicht installiert (siehe INSTALLATION.de.txt)", "Rust not installed (see INSTALLATION.txt)")}.get(
        base, L("Visual Studio C++ nicht installiert (siehe INSTALLATION.de.txt)",
                "Visual Studio C++ not installed (see INSTALLATION.txt)"))


def is_external(engine: str) -> bool:
    return engine.startswith(EXTERNAL)


def engine_base(engine: str) -> str:
    return engine.removesuffix("_simd").removesuffix("_float")


def external_command(engine: str) -> list[str]:
    base = engine_base(engine)
    if base == "csharp":
        return [str(CSHARP_EXE)] if CSHARP_EXE.exists() else ["dotnet", str(CSHARP_DLL)]
    if base == "rust":
        return [str(RUST_EXE)]
    return [str(NATIVE_EXE[base])]


def _stale(binary: Path, sources: list[Path]) -> bool:
    """Rebuild needed? Only if the program is missing or a source file is clearly newer.

    The tolerance (1 minute) absorbs timestamp shifts from copying/unpacking.
    """
    if not binary.exists():
        return True
    newest = max((s.stat().st_mtime for s in sources if s.exists()), default=0)
    return newest > binary.stat().st_mtime + 60


def _build_or_use_shipped(name: str, binaries: list[Path], have_tools: bool, build) -> None:
    """Builds if needed and possible. If the tools are missing (e.g. in package "Full"), the shipped
    programs are used; an error occurs only if there are neither tools nor programs."""
    shipped = all(b.exists() for b in binaries)
    if not have_tools:
        if any(b.exists() for b in binaries):   # missing single programs are not selectable at all (ENGINES)
            return
        raise RuntimeError(L(f"{name}: weder Programm noch Werkzeuge zum Übersetzen vorhanden (siehe INSTALLATION)",
                             f"{name}: neither program nor build tools available (see INSTALLATION)"))
    try:
        build()
    except Exception:
        if shipped:   # build failed, but finished programs exist -> use them
            return
        raise


def ensure_native_built():
    """Builds C, C++, assembler and GPU with Visual Studio (native/build.bat), if needed."""
    sources = [p for p in NATIVE_DIR.rglob("*") if p.suffix in (".c", ".cpp", ".h", ".asm", ".hlsl", ".bat")]
    if not any(_stale(e, sources) for e in NATIVE_EXE.values()):
        return

    def build():
        r = subprocess.run(["cmd.exe", "/c", "call", "build.bat"], cwd=NATIVE_DIR, capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError(L("C/C++/Assembler-Build fehlgeschlagen: ", "C/C++/assembler build failed: ")
                               + (r.stdout + r.stderr)[-500:])
    _build_or_use_shipped("C/C++/Assembler/GPU", list(NATIVE_EXE.values()), _vswhere.exists(), build)


ORDER_IDS = ("zeilen", "teuer")   # ID "teuer" stays (old benchmark files)


def orders() -> dict:
    """Tile orders: ID -> label in the current language."""
    return {"zeilen": L("zeilenweise", "row by row"), "teuer": L("aufwendige Kacheln zuerst", "demanding tiles first")}


ORDER_FILE = {"zeilen": "zeilenweise", "teuer": "aufwendige_zuerst"}     # as written in CSV/JSON
ORDER_FROM_FILE = {"zeilen": "zeilen", "zeilenweise": "zeilen", "teuer": "teuer", "aufwendige_zuerst": "teuer"}
BENCH_DIR = Path(__file__).parent / "benchmarks"
ESCAPE2 = 256.0  # large escape radius (16²) for smooth colour gradients

# Predefined regions: centre (x, y) and width in the complex plane
REGIONS = {
    "gesamt": (-0.6, 0.0, 3.4),
    "seepferdchen": (-0.7453, 0.1127, 0.0065),
    "spirale": (-0.761574, -0.0847596, 0.0045),
    "elefanten": (0.2925, 0.0161, 0.012),
}
# With 90° rotation (portrait) the real axis runs vertically, so the width measures the imaginary axis
REGIONS_ROT = {**REGIONS, "gesamt": (-0.75, 0.0, 2.8)}


# --------------------------------------------------------------------------
# Computation parts: return a smoothed iteration value per pixel, -1 = in the set
# --------------------------------------------------------------------------
def in_main_bulbs(cr, ci):
    """Is c certainly in the set? Main cardioid or the bulb to its left (period-2 bulb).

    Cardioid: q = (x − 1/4)² + y²,  q·(q + x − 1/4) ≤ y²/4      Bulb: (x + 1)² + y² ≤ 1/16
    These points would otherwise run up to the max. iteration count – they are the most demanding in the image.
    Works with numbers and numpy arrays (same formula in all other languages).
    """
    xm = cr - 0.25
    y2 = ci * ci
    q = xm * xm + y2
    return (q * (q + xm) <= 0.25 * y2) | ((cr + 1.0) * (cr + 1.0) + y2 <= 0.0625)


def _escape_numpy(cr: np.ndarray, ci: np.ndarray, maxiter: int, skip: bool = False) -> np.ndarray:
    shape = cr.shape
    cr, ci = cr.ravel().copy(), ci.ravel().copy()
    out = np.full(cr.size, -1.0)
    idx = np.arange(cr.size)
    if skip:  # do not iterate points in cardioid/bulb at all (stay -1 = in the set)
        keep = ~in_main_bulbs(cr, ci)
        idx, cr, ci = idx[keep], cr[keep], ci[keep]
    zr, zi = np.zeros_like(cr), np.zeros_like(ci)
    for it in range(maxiter):
        zr2, zi2 = zr * zr, zi * zi
        r2 = zr2 + zi2
        esc = r2 > ESCAPE2
        if esc.any():
            out[idx[esc]] = it + 1 - np.log2(0.5 * np.log(r2[esc]))
            keep = ~esc
            idx, zr, zi, cr, ci = idx[keep], zr[keep], zi[keep], cr[keep], ci[keep]
            zr2, zi2 = zr2[keep], zi2[keep]
            if idx.size == 0:
                break
        zi = 2 * zr * zi + ci
        zr = zr2 - zi2 + cr
    return out.reshape(shape)


if HAVE_NUMBA:
    @njit(cache=True, nogil=True)
    def _escape_numba(cr, ci, maxiter, skip):
        h, w = cr.shape
        out = np.empty((h, w))
        for y in range(h):
            for x in range(w):
                c_r, c_i = cr[y, x], ci[y, x]
                zr = zi = 0.0
                val = -1.0
                if skip:  # cardioid / bulb: certainly in the set, do not iterate
                    xm = c_r - 0.25
                    y2 = c_i * c_i
                    q = xm * xm + y2
                    if q * (q + xm) <= 0.25 * y2 or (c_r + 1.0) * (c_r + 1.0) + y2 <= 0.0625:
                        out[y, x] = -1.0
                        continue
                for it in range(maxiter):
                    zr2, zi2 = zr * zr, zi * zi
                    if zr2 + zi2 > 256.0:
                        val = it + 1 - np.log2(0.5 * np.log(zr2 + zi2))
                        break
                    zi = 2.0 * zr * zi + c_i
                    zr = zr2 - zi2 + c_r
                out[y, x] = val
        return out


def _palette(n: int = 1024) -> np.ndarray:
    """Cyclic colour gradient (dark blue - white - orange - dark)."""
    stops = np.array([0.0, 0.16, 0.42, 0.6425, 0.8575, 1.0])
    cols = np.array([[0, 7, 100], [32, 107, 203], [237, 255, 255],
                     [255, 170, 0], [0, 2, 0], [0, 7, 100]], dtype=float)
    t = np.linspace(0, 1, n, endpoint=False)
    return np.stack([np.interp(t, stops, cols[:, k]) for k in range(3)], axis=1).astype(np.uint8)


PALETTE = _palette()


def _colorize(nu: np.ndarray) -> np.ndarray:
    rgb = np.zeros(nu.shape + (3,), dtype=np.uint8)
    outside = nu >= 0
    idx = (np.sqrt(nu[outside]) * 64).astype(np.int64) % len(PALETTE)
    rgb[outside] = PALETTE[idx]
    return rgb


def _current_cpu() -> int:
    try:
        return ctypes.windll.kernel32.GetCurrentProcessorNumber()
    except Exception:
        return -1


def render_tile(job: tuple) -> tuple:
    """Worker function: computes one tile.

    job = (index, px, py, w, h, img_w, img_h, cx, cy, width, maxiter, engine, rot90, skip)
    Returns (index, pid, cpu, seconds, rgb_bytes)
    rot90 = True: image rotated 90° clockwise (right = +Im, down = +Re).
    skip = True: count points in cardioid/bulb directly as "in the set".
    """
    i, px, py, w, h, img_w, img_h, cx, cy, width, maxiter, engine, rot90, skip = job
    t0 = time.perf_counter()
    scale = width / img_w
    sx = (np.arange(px, px + w) - img_w / 2 + 0.5) * scale
    sy = (np.arange(py, py + h) - img_h / 2 + 0.5) * scale
    if rot90:
        ci, cr = np.meshgrid(cy + sx, cx + sy)
    else:
        cr, ci = np.meshgrid(cx + sx, cy - sy)
    if engine == "numba" and HAVE_NUMBA:
        nu = _escape_numba(cr, ci, maxiter, skip)
    else:
        nu = _escape_numpy(cr, ci, maxiter, skip)
    rgb = _colorize(nu)
    return i, os.getpid(), _current_cpu(), time.perf_counter() - t0, rgb.tobytes()


def warmup():
    """Compiles the numba kernel (or loads it from the cache)."""
    if HAVE_NUMBA:
        z = np.zeros((2, 2))
        _escape_numba(z, z, 10, False)


def estimate_costs(jobs: list[tuple], samples: int = 8, cap: int = 500) -> np.ndarray:
    """Rough effort estimate per tile: 8×8 samples with at most `cap` iterations.

    Points in the set run up to the cap and count fully; outside, most stop after a few steps.
    That is enough to tell demanding tiles (much black) from fast ones, and takes only milliseconds.
    """
    crs, cis = [], []
    for (_, px, py, w, h, img_w, img_h, cx, cy, width, maxiter, _, rot90, _) in jobs:
        scale = width / img_w
        sx = (px + (np.arange(samples) + 0.5) * w / samples - img_w / 2) * scale
        sy = (py + (np.arange(samples) + 0.5) * h / samples - img_h / 2) * scale
        if rot90:
            ci, cr = np.meshgrid(cy + sx, cx + sy)
        else:
            cr, ci = np.meshgrid(cx + sx, cy - sy)
        crs.append(cr); cis.append(ci)
    cr, ci = np.vstack(crs), np.vstack(cis)
    limit = min(cap, jobs[0][10])
    skip = jobs[0][13]  # with the cardioid test, points inside are cheap -> also in the estimate
    nu = _escape_numba(cr, ci, limit, skip) if HAVE_NUMBA else _escape_numpy(cr, ci, limit, skip)
    if skip:
        nu = np.where(in_main_bulbs(cr, ci), 0.0, nu)
    return np.where(nu < 0, limit, nu).reshape(len(jobs), -1).sum(axis=1)


def tile_order(jobs: list[tuple], mode: str) -> list[int]:
    """Order in which tiles are distributed. "teuer" (demanding first): descending by estimated effort (LPT)."""
    if mode != "teuer":
        return list(range(len(jobs)))
    return [int(k) for k in np.argsort(-estimate_costs(jobs), kind="stable")]


def ensure_rust_built():
    """Builds the Rust program (release) if it is missing or the source is newer."""
    sources = list((RUST_PROJECT / "src").glob("*.rs")) + [RUST_PROJECT / "Cargo.toml"]
    if not _stale(RUST_EXE, sources):
        return

    def build():
        r = subprocess.run([CARGO, "build", "--release", "--quiet"], cwd=RUST_PROJECT, capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError(L("Rust-Build fehlgeschlagen: ", "Rust build failed: ") + (r.stdout + r.stderr)[-500:])
    _build_or_use_shipped("Rust", [RUST_EXE], CARGO is not None, build)


def ensure_csharp_built():
    """Builds the C# program (Release) if it is missing or the source is newer."""
    if CSHARP_EXE.exists():   # self-contained .exe (package "Full") needs neither .NET nor building
        return
    sources = list(CSHARP_PROJECT.glob("*.cs")) + list(CSHARP_PROJECT.glob("*.csproj"))
    if not _stale(CSHARP_DLL, sources):
        return

    def build():
        r = subprocess.run([DOTNET, "build", str(CSHARP_PROJECT), "-c", "Release", "-o", str(CSHARP_DLL.parent),
                            "--nologo", "-v", "q"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError(L("C#-Build fehlgeschlagen: ", "C# build failed: ") + (r.stdout + r.stderr)[-500:])
    _build_or_use_shipped("C#", [CSHARP_DLL], DOTNET is not None, build)


PLACEMENT_IDS = ("windows", "verteilt", "kompakt")


def placement_labels() -> dict:
    """Placements: ID -> label in the current language."""
    return {
        "windows": L("Windows entscheidet", "Windows decides"),
        "verteilt": L("1 Thread je Kern zuerst (über alle CCX verteilt)",
                      "1 thread per core first (spread across all CCX)"),
        "kompakt": L("kompakt: beide Threads eines Kerns, CCX für CCX",
                     "compact: both threads of a core, CCX by CCX"),
    }


def placement_order(mode: str, cores: list[list[int]], l3: list[list[int]]) -> list[int] | None:
    """Order of the logical processors to which workers 0, 1, 2, … are bound.

    verteilt: first the 1st thread of every core, round robin across the CCX (CCX0-core0, CCX1-core3, …),
              then the 2nd threads in the same order.
    kompakt:  core by core with both threads, CCX by CCX (0, 1, 2, 3, …).
    windows:  no binding (None).
    """
    if mode == "kompakt":
        return [lp for c in cores for lp in c]
    if mode != "verteilt":
        return None
    groups = [[c for c in cores if c[0] in g] for g in l3] if l3 else [cores]
    groups = [g for g in groups if g]
    round_robin = [g[i] for i in range(max(map(len, groups))) for g in groups if i < len(g)]
    width = max(map(len, cores))
    return [c[t] for t in range(width) for c in round_robin if t < len(c)]


def _init_worker(counter=None, order=None):
    worker_util.init_worker(counter, order)  # priority, fixed thread, parent watch
    warmup()


_ping = worker_util.ping
watch_parent = worker_util.watch_parent


# --------------------------------------------------------------------------
# Control in the main process
# --------------------------------------------------------------------------
class MandelManager:
    def __init__(self, max_workers: int, cores: list[list[int]] | None = None, l3: list[list[int]] | None = None):
        self.max_workers = max_workers
        self.cores = cores or [[i] for i in range(max_workers)]
        self.l3 = l3 or []
        self.lock = threading.Lock()
        self.pool: ProcessPoolExecutor | None = None
        self.pool_key: tuple | None = None
        self.stop_flag = threading.Event()
        self.job = 0
        self.tiles: list[dict] = []
        self.st: dict = {"running": False}
        self.bench: dict = {"running": False, "results": [], "file": None}
        self._load_last_bench()

    # ---- Pool ----
    def _get_pool(self, workers: int, placement: str = "windows") -> float:
        """Provides a pool with `workers` processes and placement, returns the startup time."""
        if self.pool and self.pool_key == (workers, placement):
            return 0.0
        self.shutdown()
        t0 = time.perf_counter()
        warmup()  # fills the numba cache before many processes compile at the same time
        order = placement_order(placement, self.cores, self.l3)
        self.pool = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                                        initargs=(multiprocessing.Value("i", 0), order))
        self.pool_key = (workers, placement)
        # Continue only once every process has started, initialised and answered
        seen: set[int] = set()
        while len(seen) < workers and time.perf_counter() - t0 < 120:
            seen |= set(self.pool.map(_ping, range(workers * 2)))
        return time.perf_counter() - t0

    def shutdown(self):
        if self.pool:
            self.pool.shutdown(wait=True, cancel_futures=True)
        self.pool, self.pool_key = None, None

    def busy(self) -> bool:
        return self.st.get("running") or self.bench["running"]

    # ---- Rendering ----
    def _render(self, p: dict) -> dict | None:
        """Computes an image with the current pool. Runs in a background thread."""
        w, h, ts = p["width"], p["height"], p["tile"]
        cx, cy, cw = p["cx"], p["cy"], p["cw"]
        jobs = [(k, x, y, min(ts, w - x), min(ts, h - y), w, h, cx, cy, cw, p["maxiter"], p["engine"],
                 p.get("rot90", False), p.get("cardioid", False))
                for k, (y, x) in enumerate((y, x) for y in range(0, h, ts) for x in range(0, w, ts))]
        with self.lock:
            self.job += 1
            self.tiles = []
            self.st = {"running": True, "job": self.job, "params": p, "total": len(jobs), "done": 0,
                       "t_start": time.perf_counter(), "elapsed": 0.0, "workers_seen": 0,
                       "startup": p.get("startup", 0.0), "label": p.get("label", "")}
        t0 = time.perf_counter()
        order = tile_order(jobs, p.get("order", "zeilen"))  # the estimate honestly counts toward the measured time
        t_est = time.perf_counter() - t0
        with self.lock:
            self.st["estimate_ms"] = round(t_est * 1000, 1)
        if is_external(p["engine"]):
            return self._render_external(p, jobs, order, t_est)
        pids: dict[int, int] = {}
        futures = [self.pool.submit(render_tile, jobs[k]) for k in order]
        cpu_time = 0.0
        for f in as_completed(futures):
            if self.stop_flag.is_set():
                for g in futures:
                    g.cancel()
                break
            try:
                i, pid, cpu, sec, data = f.result()
            except Exception as e:  # error in the worker: cancel the rest, do not leave the status on "running"
                for g in futures:
                    g.cancel()
                with self.lock:
                    self.st.update(running=False, error=str(e))
                raise
            cpu_time += sec
            worker = pids.setdefault(pid, len(pids))
            j = jobs[i]
            with self.lock:
                self.tiles.append({"i": i, "x": j[1], "y": j[2], "w": j[3], "h": j[4],
                                   "worker": worker, "cpu": cpu, "ms": round(sec * 1000, 1),
                                   "data": data})
                self.st["done"] += 1
                self.st["workers_seen"] = len(pids)
        elapsed = time.perf_counter() - t0
        stopped = self.stop_flag.is_set()
        with self.lock:
            self.st.update(running=False, elapsed=elapsed, stopped=stopped, cpu_time=round(cpu_time, 3))
        return None if stopped else {"elapsed": elapsed, "cpu_time": cpu_time, "workers_seen": len(pids)}

    def _render_external(self, p: dict, jobs: list[tuple], order: list[int], t_est: float) -> dict | None:
        """Computes the same image in an external program (real threads or GPU) and takes over the streamed tiles."""
        cfg = {"width": p["width"], "height": p["height"], "maxIter": p["maxiter"], "tile": p["tile"],
               "cx": p["cx"], "cy": p["cy"], "cw": p["cw"], "rot90": p.get("rot90", False),
               "threads": p["workers"], "order": order, "emitTiles": True,
               "affinity": placement_order(p.get("placement", "windows"), self.cores, self.l3),
               # for the GPU program "simd" means the float variant
               "simd": p["engine"].endswith("_simd") or p["engine"] in ("asm", "gpu_float"),
               "cardioid": bool(p.get("cardioid", False)),
               "adapter": p.get("gpu_adapter")}  # graphics card detected by the server (GPU program only)
        cmd = external_command(p["engine"])
        t_spawn = time.perf_counter()
        proc = worker_util.retry_access_denied(lambda: subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1 << 20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        proc.stdin.write(json.dumps(cfg).encode())
        proc.stdin.close()
        result, workers = None, set()
        while line := proc.stdout.readline():
            if self.stop_flag.is_set():
                proc.kill()
                break
            if line.startswith(b"B "):  # header line, followed by the raw RGB bytes of the tile
                _, i, worker, cpu, ms, size = line.split()
                i, worker = int(i), int(worker)
                data = proc.stdout.read(int(size))
                j = jobs[i]
                workers.add(worker)
                with self.lock:
                    self.tiles.append({"i": i, "x": j[1], "y": j[2], "w": j[3], "h": j[4],
                                       "worker": worker, "cpu": int(cpu), "ms": float(ms), "data": data})
                    self.st["done"] += 1
                    self.st["workers_seen"] = len(workers)
            elif line.startswith(b"I "):  # device info (GPU name, precision)
                with self.lock:
                    self.st["device"] = json.loads(line[2:])
            elif line.startswith(b"READY"):  # program started and warmed up: this is the "process startup"
                with self.lock:
                    self.st["startup"] = round(time.perf_counter() - t_spawn, 3)
            elif line.startswith(b"R "):
                result = json.loads(line[2:])
        err = proc.stderr.read().decode(errors="replace")
        proc.wait()
        stopped = self.stop_flag.is_set()
        if result is None and not stopped:
            msg = L(f"Programm ({p['engine']}) ohne Ergebnis: ", f"Program ({p['engine']}) returned no result: ") + err[-300:]
            with self.lock:
                self.st.update(running=False, error=msg)
            raise RuntimeError(msg)
        elapsed = (result["seconds"] if result else 0) + t_est
        with self.lock:
            self.st.update(running=False, elapsed=elapsed, stopped=stopped,
                           cpu_time=round(result["cpu_time"], 3) if result else 0)
        if stopped:
            return None
        return {"elapsed": elapsed, "cpu_time": result["cpu_time"], "workers_seen": result["threads_seen"],
                "startup": self.st.get("startup", 0.0)}

    def _prepare(self, p: dict) -> float:
        """Python: provide the process pool (returns startup time). External programs: only ensure they are built."""
        if is_external(p["engine"]):
            base = engine_base(p["engine"])
            ensure_rust_built() if base == "rust" else ensure_csharp_built() if base == "csharp" else ensure_native_built()
            warmup()  # load numba in the main process, otherwise the first effort estimate includes the JIT time
            return 0.0
        return self._get_pool(p["workers"], p.get("placement", "windows"))

    def start(self, p: dict):
        if self.busy():
            raise RuntimeError(L("Es läuft bereits eine Berechnung", "A computation is already running"))
        self.stop_flag.clear()
        self.st = {"running": True, "job": self.job, "done": 0, "total": 0, "params": p,
                   "t_start": time.perf_counter(), "preparing": True}

        def run():
            try:
                p["startup"] = round(self._prepare(p), 3)
                if self.stop_flag.is_set():
                    self.st = {**self.st, "running": False, "stopped": True, "preparing": False}
                    return
                self._render(p)
            except Exception as e:
                self.st = {"running": False, "error": str(e)}
        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        self.stop_flag.set()

    def status(self) -> dict:
        with self.lock:
            s = {k: v for k, v in self.st.items() if k != "t_start"}
            if self.st.get("running") and "t_start" in self.st:
                s["elapsed"] = time.perf_counter() - self.st["t_start"]
        s["bench"] = self.bench
        return s

    def tiles_since(self, job: int, since: int, limit: int = 400) -> dict:
        with self.lock:
            if job != self.job:
                since = 0
            part = self.tiles[since:since + limit]
            next_idx = since + len(part)
        return {"job": self.job, "next": next_idx, "status": self.status(),
                "tiles": [{**{k: v for k, v in t.items() if k != "data"},
                           "data": base64.b64encode(t["data"]).decode()} for t in part]}

    # ---- Scaling benchmark ----
    def start_bench(self, p: dict, worker_list: list[int], repeats: int = 1):
        if self.busy():
            raise RuntimeError(L("Es läuft bereits eine Berechnung", "A computation is already running"))
        self.stop_flag.clear()
        placement = p.get("placement", "windows")
        self.bench = {"running": True, "results": [], "file": None, "params": {**p, "repeats": repeats},
                      "plan": worker_list, "current": None}

        def run():
            try:
                for n in worker_list:
                    if self.stop_flag.is_set():
                        break
                    self.bench["current"] = n
                    startup = self._prepare({**p, "workers": n})
                    runs = []
                    for k in range(repeats):  # several runs, the median counts
                        r = self._render({**p, "workers": n, "startup": round(startup, 3),
                                          "label": L(f"Benchmark: {n} Worker, Lauf {k + 1}/{repeats}",
                                                     f"Benchmark: {n} workers, run {k + 1}/{repeats}")})
                        if r is None:
                            break
                        runs.append(r)
                    if len(runs) < repeats:
                        break
                    sec = statistics.median(r["elapsed"] for r in runs)
                    if is_external(p["engine"]):  # program startup occurs on every run
                        startup = statistics.median(r["startup"] for r in runs)
                    t1 = self.bench["results"][0]["seconds"] if self.bench["results"] else sec
                    self.bench["results"].append({
                        "workers": n, "seconds": round(sec, 3), "startup": round(startup, 3),
                        "cpu_time": round(statistics.median(r["cpu_time"] for r in runs), 3),
                        "speedup": round(t1 / sec, 2),
                        "efficiency": round(t1 / sec / n * 100, 1),
                        "runs": [round(r["elapsed"], 3) for r in runs]})
                if self.bench["results"]:
                    self.bench["file"] = self._save_bench(p)
            except Exception as e:
                self.bench["error"] = str(e)
            finally:
                self.bench["running"] = False
                self.bench["current"] = None
        threading.Thread(target=run, daemon=True).start()

    def _save_bench(self, p: dict) -> str:
        BENCH_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        meta = {"zeit": stamp, "breite": p["width"], "hoehe": p["height"], "max_iter": p["maxiter"],
                "ausschnitt": p.get("region", ""), "kachel": p["tile"], "rechenverfahren": p["engine"],
                "gedreht": bool(p.get("rot90", False)), "platzierung": p.get("placement", "windows"),
                "wiederholungen": self.bench["params"].get("repeats", 1),
                "reihenfolge": ORDER_FILE[p.get("order", "zeilen")], "kardioide": bool(p.get("cardioid", False))}
        path = BENCH_DIR / f"mandelbrot_{stamp}.json"
        path.write_text(json.dumps({**meta, "ergebnisse": self.bench["results"]}, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        header = list(meta) + ["worker", "sekunden", "prozessstart_s", "cpu_zeit_s",
                               "beschleunigung", "effizienz_prozent"]
        csv_path = BENCH_DIR / "mandelbrot_benchmarks.csv"
        self._migrate_csv(csv_path, header)
        new = not csv_path.exists()
        with csv_path.open("a", newline="", encoding="utf-8") as f:
            wr = csv.writer(f, delimiter=";")
            if new:
                wr.writerow(header)
            de = lambda v: str(v).replace(".", ",")  # decimal comma for German Excel
            for r in self.bench["results"]:
                wr.writerow(list(meta.values()) + [r["workers"]] + [de(r[k]) for k in
                            ("seconds", "startup", "cpu_time", "speedup", "efficiency")])
        return path.name

    @staticmethod
    def _migrate_csv(path: Path, header: list[str]):
        """Bring older CSV files to the current columns (add new columns, carry over renamed ones)."""
        if not path.exists():
            return
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f, delimiter=";"))
        if not rows or rows[0] == header:
            return
        old = rows[0]
        defaults = {"gedreht": "", "platzierung": "windows", "wiederholungen": "1", "reihenfolge": "zeilen",
                    "kardioide": "False"}
        renamed = {"rechenverfahren": "rechenkern"}   # new column name -> former one

        def value(row: dict, col: str) -> str:
            v = row.get(col, row.get(renamed.get(col, ""), defaults.get(col, "")))
            return ORDER_FILE.get(v, v) if col == "reihenfolge" else v
        out = [header] + [[value(dict(zip(old, r)), col) for col in header] for r in rows[1:]]
        with path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, delimiter=";").writerows(out)

    @staticmethod
    def _read_bench_file(path: Path) -> dict:
        d = json.loads(path.read_text(encoding="utf-8"))
        return {"running": False, "results": d["ergebnisse"], "file": path.name,
                "params": {"width": d["breite"], "height": d["hoehe"], "maxiter": d["max_iter"],
                           "region": d["ausschnitt"], "engine": d.get("rechenverfahren", d.get("rechenkern")),
                           "tile": d["kachel"], "rot90": d.get("gedreht", False),
                           "placement": d.get("platzierung", "windows"), "repeats": d.get("wiederholungen", 1),
                           "order": ORDER_FROM_FILE.get(d.get("reihenfolge", "zeilen"), "zeilen"),
                           "cardioid": d.get("kardioide", False)}}

    def history(self) -> list[dict]:
        """All saved scaling tests, oldest first (for the comparison chart)."""
        out = []
        for path in sorted(BENCH_DIR.glob("mandelbrot_*.json")) if BENCH_DIR.exists() else []:
            try:
                out.append(self._read_bench_file(path))
            except Exception:
                pass
        return out

    def _load_last_bench(self):
        files = sorted(BENCH_DIR.glob("mandelbrot_*.json")) if BENCH_DIR.exists() else []
        if files:
            try:
                self.bench = self._read_bench_file(files[-1])
            except Exception:
                pass
