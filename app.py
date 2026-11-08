"""Core Monitor: prototype for loading and monitoring all CPU cores.

Web server and control. Started via server.py (small start file, see there why).
"""
from __future__ import annotations

import asyncio
import ctypes
import math
import multiprocessing as mp
import os
import platform
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import hardware
import lastgen
import mandelbrot
import pi
import security
from i18n import L, get_lang, set_lang, LANGS

HOST = "127.0.0.1"     # fixed on purpose: the server is reachable only on this computer
BOOT_ID = f"{os.getpid()}-{time.time():.0f}"  # changes on every server start -> open pages reload


def assets_stamp() -> str:
    """Fingerprint of the page files: if one of them changes, open pages reload (even without a server restart)."""
    try:
        return str(max(int(f.stat().st_mtime) for f in (Path(__file__).parent / "static").iterdir()))
    except (OSError, ValueError):
        return ""
SAMPLE_INTERVAL = 1.0  # seconds between two measurements
STATIC = Path(__file__).parent / "static"

# ---- Hardware detection: everything else is based on these values (see hardware.py) ----
CPU = hardware.detect_cpu()
LOGICAL, PHYSICAL = CPU["logical"], CPU["physical"]
TOPOLOGY, L3_GROUPS, TOPOLOGY_SOURCE = CPU["cores"], CPU["l3"], CPU["topology_source"]
BENCH_STEPS = hardware.scaling_steps(LOGICAL, PHYSICAL)
GPUS: list[dict] = []          # determined in the background at server start (helper program), not in worker processes
GPU_DEFAULT: int | None = None


def topology_source_text(source: str) -> str:
    """Source of the core assignment as text in the current language (hardware.py returns an ID)."""
    return {"assumed": L("Annahme", "assumption"), "simulated": L("simuliert", "simulated")}.get(source, source)


def engine_status() -> dict:
    """Which computation methods are usable on this computer – and why others are not."""
    isa = CPU["isa"]
    gpu = next((g for g in GPUS if g["index"] == GPU_DEFAULT), None)
    out = {}
    for e in mandelbrot.ALL_ENGINES:
        reason = mandelbrot.missing_reason(e)   # tool/package missing?
        if reason:
            pass
        elif (e.endswith("_simd") or e == "asm") and not isa["avx2"]:
            reason = L("CPU hat kein AVX2", "CPU has no AVX2")
        elif e.startswith("gpu"):
            if not hardware.GPU_PROBE.exists():
                reason = L("GPU-Programm nicht übersetzt (Visual Studio fehlt?)",
                           "GPU program not built (Visual Studio missing?)")
            elif gpu is None:
                reason = L("keine Grafikkarte mit Direct3D-11-Compute gefunden",
                           "no graphics card with Direct3D 11 compute found")
            elif e == "gpu" and not gpu.get("double"):
                reason = L("Grafikkarte kann kein double im Shader", "graphics card cannot do double in shaders")
        out[e] = reason
    return out


def available_engines() -> list[str]:
    return [e for e, reason in engine_status().items() if reason is None]


def placements() -> dict:
    """Placements; "kompakt" (both SMT threads of a core) exists only with SMT. Above 64 threads only Windows."""
    labels = mandelbrot.placement_labels()
    if CPU["processor_groups"] > 1:
        return {"windows": labels["windows"]}
    return {k: v for k, v in labels.items() if k != "kompakt" or CPU["smt"]}
mandel = mandelbrot.MandelManager(LOGICAL, TOPOLOGY, L3_GROUPS)
pim = pi.PiManager(TOPOLOGY, L3_GROUPS)


# --------------------------------------------------------------------------
# Load generator: one process per selected core, optionally pinned
# --------------------------------------------------------------------------
class LoadManager:
    """Start/stop run in web server threads, status() in the sampling loop -> everything under one lock."""

    def __init__(self):
        self.lock = threading.RLock()
        self.procs: list[mp.Process] = []
        self.stop_event: mp.Event | None = None
        self.info: dict = {}

    def running(self) -> bool:
        return any(p.is_alive() for p in list(self.procs))

    def start(self, cores: list[int], intensity: float, seconds: int, pin: bool):
        with self.lock:
            self.stop()
            self.stop_event = mp.Event()
            deadline = time.time() + seconds
            # set info first: status() may be queried while the processes are still starting (approx. 2 s)
            self.info = {"cores": cores, "intensity": intensity, "seconds": seconds,
                         "pin": pin, "until": deadline, "starting": True}
            for c in cores:
                p = mp.Process(target=lastgen.burn, args=(c if pin else None, intensity, self.stop_event, deadline),
                               daemon=True)
                p.start()
                self.procs.append(p)
            self.info["starting"] = False

    def stop(self):
        with self.lock:
            if self.stop_event:
                self.stop_event.set()
            deadline = time.time() + 2
            for p in self.procs:
                p.join(timeout=max(0, deadline - time.time()))
                if p.is_alive():
                    p.terminate()
            self.procs = []
            self.info = {}

    def status(self) -> dict:
        info = dict(self.info)
        if not info or not (info.get("starting") or self.running()):
            return {"running": False}
        return {"running": True, **info, "started": len(self.procs),
                "remaining": max(0, round(info["until"] - time.time()))}


load = LoadManager()


# --------------------------------------------------------------------------
# Benchmark: real work (counting primes) serial vs. parallel
# --------------------------------------------------------------------------
def _count_primes(rng: tuple[int, int]) -> int:
    lo, hi = rng
    count = 0
    for n in range(max(lo, 2), hi):
        if n % 2 == 0:
            count += n == 2
            continue
        r = int(n ** 0.5)
        for d in range(3, r + 1, 2):
            if n % d == 0:
                break
        else:
            count += 1
    return count


def _chunks(limit: int, parts: int) -> list[tuple[int, int]]:
    step = math.ceil(limit / parts)
    return [(i, min(i + step, limit)) for i in range(0, limit, step)]


def _warmup(_):
    time.sleep(0.05)
    return os.getpid()


def _timed_run(chunks, workers: int) -> tuple[int, float, float]:
    """Returns (result, pool startup time, pure computation time).

    On Windows processes are started fresh via 'spawn', which takes noticeable time per
    process. This startup time is measured separately.
    """
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        list(ex.map(_warmup, range(workers * 2)))
        t_start = time.perf_counter() - t0
        t1 = time.perf_counter()
        result = sum(ex.map(_count_primes, chunks))
        t_calc = time.perf_counter() - t1
    return result, t_start, t_calc


def run_benchmark(limit: int, workers: int) -> dict:
    chunks = _chunks(limit, workers * 8)  # more chunks than workers -> better load balancing
    serial, _, t_serial = _timed_run(chunks, 1)
    parallel, t_start, t_parallel = _timed_run(chunks, workers)
    return {"limit": limit, "workers": workers, "primes": parallel, "ok": serial == parallel,
            "t_serial": round(t_serial, 3), "t_parallel": round(t_parallel, 3),
            "t_startup": round(t_start, 3),
            "speedup": round(t_serial / t_parallel, 2),
            "efficiency": round(t_serial / t_parallel / workers * 100, 1)}


bench_state: dict = {"running": False, "result": None}


# --------------------------------------------------------------------------
# Measurement + distribution to all browsers via WebSocket
# --------------------------------------------------------------------------
clients: set[WebSocket] = set()


async def sampler():
    psutil.cpu_percent(percpu=True)
    while True:
        await asyncio.sleep(SAMPLE_INTERVAL)
        try:
            await _sample_once()
        except Exception as e:  # an error must never stop the sampling loop permanently
            print(L(f"Messung fehlgeschlagen: {e!r}", f"Measurement failed: {e!r}"))


async def _sample_once():
    per_core = psutil.cpu_percent(percpu=True)[:LOGICAL]  # (on a simulated computer only that many threads)
    freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    msg = {
        "boot": BOOT_ID,
        "assets": assets_stamp(),
        "t": time.time(),
        "cores": per_core,
        "total": round(sum(per_core) / len(per_core), 1),
        "freq": round(freq.current) if freq else None,
        "mem": mem.percent,
        "mem_used": round(mem.used / 2**30, 1),
        "mem_total": round(mem.total / 2**30, 1),
        "load": load.status(),
        "bench": bench_state,
        "mandel": mandel.status(),
        "pi": pim.status(),
        "security": security.status(),
    }
    for ws in list(clients):  # copy: browsers may join or leave during await
        try:
            await ws.send_json(msg)
        except Exception:
            clients.discard(ws)


async def open_browser_if_needed():
    """Open a browser tab only if no page is open (start.bat sets OPEN_BROWSER=1).

    Open pages reconnect within ~1 s after a restart and reload themselves –
    an additional tab would then be superfluous.
    """
    if os.environ.get("OPEN_BROWSER") != "1":
        return
    await asyncio.sleep(3.5)
    url = f"http://{HOST}:{os.environ.get('PORT', '8000')}/"
    if clients:
        print(L(f"Offene Seite gefunden ({len(clients)}) – sie lädt sich selbst neu, kein neuer Tab.",
                f"Open page found ({len(clients)}) – it reloads itself, no new tab."))
    elif os.environ.get("OPEN_BROWSER_DRYRUN") == "1":  # tests only: open nothing, just report
        print(L("Keine offene Seite – würde jetzt einen Tab öffnen:", "No open page – would now open a tab:"), url)
    else:
        import webbrowser
        print(L("Keine offene Seite – öffne", "No open page – opening"), url)
        webbrowser.open(url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global GPUS, GPU_DEFAULT
    # detect graphics cards only in the server process (starts a helper program, ~0.5 s)
    GPUS = await asyncio.to_thread(hardware.detect_gpus)
    GPU_DEFAULT = hardware.best_gpu(GPUS)
    print_system()
    task = asyncio.create_task(sampler())
    asyncio.create_task(open_browser_if_needed())
    yield
    task.cancel()
    load.stop()
    mandel.stop()
    mandel.shutdown()
    pim.stop()
    pim.shutdown()


app = FastAPI(title="Core Monitor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def no_stale_pages(request, call_next):
    """Have the page and scripts revalidated on every load so that old files are never mixed in after changes."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def only_this_pc(request, call_next):
    """Reject requests from outside (foreign client, Host or Origin – see security.py): 403, log, warning."""
    client, host, origin = request.client.host if request.client else None, request.headers.get("host"), request.headers.get("origin")
    reason = security.problem(client, host, origin)
    if reason:
        security.record(reason, client, host, origin, request.method, request.url.path, request.headers.get("user-agent"))
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return await call_next(request)


@app.get("/api/security")
def security_status():
    return security.status()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


def system_info() -> dict:
    """Detected hardware for the page and /api/system (CPU without the long topology lists)."""
    cpu = {k: v for k, v in CPU.items() if k not in ("cores", "l3")}
    cpu["l3_groups"] = len(L3_GROUPS)
    cpu["topology_source"] = topology_source_text(TOPOLOGY_SOURCE)
    return {"cpu": cpu, "gpus": GPUS, "gpu_default": GPU_DEFAULT, "engines": engine_status(),
            "bench_steps": BENCH_STEPS}


def print_system():
    c, isa = CPU, CPU["isa"]
    feats = ", ".join(k.upper() for k in ("avx2", "fma", "avx512f") if isa[k]) or L("kein AVX2", "no AVX2")
    gpu = next((g for g in GPUS if g["index"] == GPU_DEFAULT), None)
    print(L(f"CPU: {c['name']} - {c['physical']} Kerne / {c['logical']} Threads, {len(L3_GROUPS)} L3-Gruppen, {feats}",
            f"CPU: {c['name']} - {c['physical']} cores / {c['logical']} threads, {len(L3_GROUPS)} L3 groups, {feats}")
          + (L(" (simuliert)", " (simulated)") if c['simulated'] else ""))
    if gpu:
        print(f"GPU: {gpu['name']}" + (" (double)" if gpu['double'] else L(" (nur float)", " (float only)")))
    else:
        print("GPU: " + L("keine nutzbare gefunden", "no usable one found"))
    off = {e: r for e, r in engine_status().items() if r}
    if off:
        print(L("Nicht verfügbar:", "Not available:"), "; ".join(f"{e}: {r}" for e, r in off.items()))


@app.get("/api/system")
def system():
    return system_info()


@app.get("/api/info")
def info():
    return {"logical": LOGICAL, "physical": PHYSICAL, "cpu": CPU["name"],
            "freq_max": CPU["max_mhz"], "interval": SAMPLE_INTERVAL, "boot": BOOT_ID, "assets": assets_stamp(),
            "topology": TOPOLOGY, "l3": L3_GROUPS, "topology_source": topology_source_text(TOPOLOGY_SOURCE),
            "smt": CPU["smt"],
            "engines": available_engines(), "engines_off": {e: r for e, r in engine_status().items() if r},
            "regions": mandelbrot.REGIONS, "bench_workers": BENCH_STEPS,
            "placements": placements(), "orders": mandelbrot.orders(), "system": system_info(),
            "lang": get_lang()}


class LangRequest(BaseModel):
    lang: str


@app.post("/api/lang")
def lang(req: LangRequest):
    """Sets the language of server messages (server-wide); unknown values leave it unchanged."""
    if req.lang not in LANGS:
        return {"lang": get_lang(), "error": L(f"unbekannte Sprache: {req.lang}", f"unknown language: {req.lang}")}
    return {"lang": set_lang(req.lang)}


class LoadRequest(BaseModel):
    cores: list[int] | None = None          # None = all cores
    intensity: float = Field(1.0, ge=0.05, le=1.0)
    seconds: int = Field(30, ge=1, le=3600)
    pin: bool = True                        # bind process to a fixed core


@app.post("/api/load/start")
def load_start(req: LoadRequest):
    cores = req.cores if req.cores else list(range(LOGICAL))
    cores = [c for c in cores if 0 <= c < LOGICAL]
    load.start(cores, req.intensity, req.seconds, req.pin)
    return load.status()


@app.post("/api/load/stop")
def load_stop():
    load.stop()
    return load.status()


class BenchRequest(BaseModel):
    limit: int = Field(3_000_000, ge=10_000, le=50_000_000)
    workers: int | None = None


@app.post("/api/bench")
async def bench(req: BenchRequest):
    if bench_state["running"]:
        return {"error": L("Benchmark läuft bereits", "Benchmark is already running")}
    workers = req.workers or LOGICAL
    bench_state.update(running=True, result=None)
    try:
        res = await asyncio.to_thread(run_benchmark, req.limit, workers)
        bench_state["result"] = res
        return res
    finally:
        bench_state["running"] = False


class MandelRequest(BaseModel):
    workers: int = Field(LOGICAL, ge=1, le=LOGICAL)
    width: int = Field(1200, ge=64, le=7680)    # portrait, matching the 90° rotation
    height: int = Field(1920, ge=64, le=7680)
    maxiter: int = Field(1000, ge=16, le=100_000)
    tile: int = Field(128, ge=16, le=1024)
    region: str = "gesamt"
    cx: float | None = None     # custom region (e.g. after click zoom)
    cy: float | None = None
    cw: float | None = Field(None, gt=0)
    engine: str = mandelbrot.ENGINES[0]
    rot90: bool = True          # display rotated 90° clockwise
    placement: str = "windows"  # bind workers to threads: windows | verteilt | kompakt
    order: str = "zeilen"       # tile order: zeilen | teuer (demanding first)
    cardioid: bool = False      # count points in cardioid/bulb immediately as "in the set"


def _mandel_params(req: MandelRequest) -> dict:
    regions = mandelbrot.REGIONS_ROT if req.rot90 else mandelbrot.REGIONS
    cx, cy, cw = regions.get(req.region, regions["gesamt"])
    if req.cx is not None and req.cy is not None and req.cw:
        cx, cy, cw = req.cx, req.cy, req.cw
    usable = available_engines()
    engine = req.engine if req.engine in usable else usable[0]
    return {"workers": req.workers, "width": req.width, "height": req.height, "maxiter": req.maxiter,
            "tile": req.tile, "region": req.region, "cx": cx, "cy": cy, "cw": cw, "engine": engine,
            "rot90": req.rot90,
            "placement": req.placement if req.placement in placements() else "windows",
            "order": req.order if req.order in mandelbrot.ORDER_IDS else "zeilen", "cardioid": req.cardioid,
            "gpu_adapter": GPU_DEFAULT}


@app.post("/api/mandel/start")
def mandel_start(req: MandelRequest):
    try:
        mandel.start(_mandel_params(req))
    except RuntimeError as e:
        return {"error": str(e)}
    return mandel.status()


class PiRequest(BaseModel):
    digits: int = Field(1_000_000, ge=10, le=100_000_000)
    workers: int = Field(LOGICAL, ge=1, le=LOGICAL)
    placement: str = "windows"


class PiBenchRequest(PiRequest):
    digits: int = Field(10_000_000, ge=1000, le=100_000_000)
    worker_list: list[int] | None = None
    repeats: int = Field(3, ge=1, le=9)


def _pi_params(req: PiRequest) -> dict:
    return {"digits": req.digits, "workers": req.workers,
            "placement": req.placement if req.placement in placements() else "windows"}


@app.post("/api/pi/start")
def pi_start(req: PiRequest):
    try:
        pim.start(_pi_params(req))
    except RuntimeError as e:
        return {"error": str(e)}
    return pim.status()


@app.post("/api/pi/stop")
def pi_stop():
    pim.stop()
    return {"ok": True}


@app.get("/api/pi/status")
def pi_status():
    return pim.status()


@app.post("/api/pi/bench")
def pi_bench(req: PiBenchRequest):
    plan = sorted({1} | {n for n in (req.worker_list or BENCH_STEPS) if 1 <= n <= LOGICAL})
    try:
        pim.start_bench(_pi_params(req), plan, req.repeats)
    except RuntimeError as e:
        return {"error": str(e)}
    return pim.status()


@app.get("/api/pi/download")
def pi_download():
    if not pi.RESULT_FILE.exists():
        return {"error": L("noch kein Ergebnis", "no result yet")}
    digits = pi.RESULT_FILE.stat().st_size - 2
    return FileResponse(pi.RESULT_FILE, media_type="text/plain",
                        filename=L(f"pi_{digits}_stellen.txt", f"pi_{digits}_digits.txt"))


@app.post("/api/mandel/stop")
def mandel_stop():
    mandel.stop()
    return {"ok": True}


@app.get("/api/mandel/status")
def mandel_status():
    return mandel.status()


@app.get("/api/mandel/tiles")
def mandel_tiles(job: int = 0, since: int = 0):
    return mandel.tiles_since(job, since)


@app.get("/api/mandel/bench/history")
def mandel_bench_history():
    return mandel.history()


class MandelBenchRequest(MandelRequest):
    width: int = Field(1600, ge=64, le=7680)
    height: int = Field(2560, ge=64, le=7680)
    maxiter: int = Field(5000, ge=16, le=100_000)
    worker_list: list[int] | None = None
    repeats: int = Field(1, ge=1, le=9)   # runs per worker count, the median counts


@app.post("/api/mandel/bench")
def mandel_bench(req: MandelBenchRequest):
    plan = req.worker_list or BENCH_STEPS
    plan = sorted({1} | {n for n in plan if 1 <= n <= LOGICAL})  # 1 worker is the reference for the speedup
    try:
        mandel.start_bench(_mandel_params(req), plan, req.repeats)
    except RuntimeError as e:
        return {"error": str(e)}
    return mandel.status()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    client, host, origin = ws.client.host if ws.client else None, ws.headers.get("host"), ws.headers.get("origin")
    reason = security.problem(client, host, origin)
    if reason:
        security.record(reason, client, host, origin, "WS", "/ws", ws.headers.get("user-agent"))
        await ws.close(code=1008)   # policy violation; before accept() this rejects the handshake (HTTP 403)
        return
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    print(L(f"Kern-Monitor: http://{HOST}:{port}  (erkannte Hardware und nutzbare Rechenverfahren folgen nach dem Start)",
            f"Core Monitor: http://{HOST}:{port}  (detected hardware and usable computation methods follow after startup)"))
    uvicorn.run(app, host=HOST, port=port, log_level="warning")
