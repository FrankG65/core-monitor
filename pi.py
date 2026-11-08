"""Pi to many decimal places: Chudnovsky formula with binary splitting, distributed across several processes.

Flow and phases (measured separately, because only the first one really runs in parallel):
  1. Series (parallel):  the terms 0..N are split into blocks; each worker computes the triple (P, Q, T)
                         for its block by binary splitting.
  2. Merge:              the triples are combined pairwise (tree). The lower levels run in parallel;
                         the higher up, the fewer pairs – at the end only one process is working.
  3. Final step (serial): square root of 10005 and one big division.
  4. Decimal conversion (serial): turn the binary number into a digit string.

Big integers are computed by GMP (gmpy2); without gmpy2 it works with Python int, but much slower.
"""
from __future__ import annotations

import csv
import json
import math
import multiprocessing
import os
import statistics
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    import gmpy2
    from gmpy2 import mpz, isqrt
    HAVE_GMPY = True
except ImportError:  # fallback: much slower, but same result
    HAVE_GMPY = False
    mpz = int
    isqrt = math.isqrt

import worker_util  # lightweight module: Pi workers load neither the web server nor numba
from i18n import L, get_lang

C = 640320
C3_OVER_24 = C ** 3 // 24
DIGITS_PER_TERM = math.log10(C3_OVER_24 / 72)  # ≈ 14.18 new digits per term
GUARD = 20                                      # guard digits against rounding in the last digits
BENCH_DIR = Path(__file__).parent / "benchmarks"
RESULT_FILE = BENCH_DIR / "pi_ergebnis.txt"
REFERENCE_FILE = BENCH_DIR / "pi_referenz_mpmath.txt"
REFERENCE_DIGITS = 1_000_000


# --------------------------------------------------------------------------
# Computation part (runs in the worker processes)
# --------------------------------------------------------------------------
def _bs(a: int, b: int):
    """Binary splitting over the terms a..b-1 -> (P, Q, T)."""
    if b - a == 1:
        if a == 0:
            p = q = mpz(1)
        else:
            p = mpz(6 * a - 5) * (2 * a - 1) * (6 * a - 1)
            q = mpz(a) * a * a * C3_OVER_24
        t = p * (13591409 + 545140134 * a)
        return p, q, (-t if a & 1 else t)
    m = (a + b) // 2
    p1, q1, t1 = _bs(a, m)
    p2, q2, t2 = _bs(m, b)
    return p1 * p2, q1 * q2, q2 * t1 + p1 * t2


def series_block(block: tuple[int, int, int]):
    """Worker: one block of the series. Returns (block number, P, Q, T, seconds, PID)."""
    k, a, b = block
    t0 = time.perf_counter()
    p, q, t = _bs(a, b)
    return k, p, q, t, time.perf_counter() - t0, os.getpid()


def combine(pair, need_p: bool = True):
    """Combine two adjacent triples into one (like the inner step of _bs).

    At the very top of the tree P is no longer needed – that saves one of the largest multiplications.
    """
    (p1, q1, t1), (p2, q2, t2) = pair
    return (p1 * p2 if need_p else None), q1 * q2, q2 * t1 + p1 * t2


def _init_worker(counter=None, order=None):
    worker_util.init_worker(counter, order)  # priority, affinity, parent watch as for Mandelbrot


def _ping(_):
    time.sleep(0.15)
    return os.getpid()


def final_value(q, t, digits: int):
    """Serial: pi = 426880·√10005·Q / T, as the integer pi · 10^(digits+GUARD)."""
    one = mpz(10) ** (digits + GUARD)
    sqrt_c = isqrt(10005 * one * one)
    return (q * 426880 * sqrt_c) // t


def to_text(value, digits: int) -> str:
    """Serial: binary -> decimal, cut off the guard digits."""
    s = str(value)[: digits + 1]
    return s[0] + "." + s[1:]


def finish_in_worker(args):
    """Worker: square root, division, decimal conversion and writing the file.

    Deliberately not run in the server process: GMP does not release Python's GIL during the computation, so the
    web server would otherwise be blocked for seconds with large digit counts (page seems to hang).
    Returns (seconds final step, seconds conversion, first 1 million + 2 characters, last 50 characters)
    """
    q, t, digits, path = args
    t0 = time.perf_counter()
    value = final_value(q, t, digits)
    t1 = time.perf_counter()
    text = to_text(value, digits)
    t2 = time.perf_counter()
    if path:
        Path(path).write_text(text, encoding="ascii")
    return t1 - t0, t2 - t1, text[: REFERENCE_DIGITS + 2], text[-50:]


def terms_for(digits: int) -> int:
    return int((digits + GUARD) / DIGITS_PER_TERM) + 2


def make_blocks(n_terms: int, n_blocks: int) -> list[tuple[int, int, int]]:
    """Equal number of terms per block. Later blocks are more demanding (bigger numbers) – they are handed out first."""
    n_blocks = max(1, min(n_blocks, n_terms))
    edges = [round(i * n_terms / n_blocks) for i in range(n_blocks + 1)]
    return [(k, edges[k], edges[k + 1]) for k in range(n_blocks)]


# --------------------------------------------------------------------------
# Reference for checking: mpmath is an independent implementation
# --------------------------------------------------------------------------
def reference(digits: int) -> str | None:
    """First min(digits, 1 million) digits from mpmath (computed once, then read from file)."""
    n = min(digits, REFERENCE_DIGITS)
    if REFERENCE_FILE.exists():
        ref = REFERENCE_FILE.read_text(encoding="ascii")
        if len(ref) >= n + 2:
            return ref[: n + 2]
    try:
        import mpmath
    except ImportError:
        return None
    mpmath.mp.dps = REFERENCE_DIGITS + 10
    ref = mpmath.nstr(mpmath.pi, REFERENCE_DIGITS + 5, strip_zeros=False)[: REFERENCE_DIGITS + 2]
    BENCH_DIR.mkdir(exist_ok=True)
    REFERENCE_FILE.write_text(ref, encoding="ascii")
    return ref[: n + 2]


# --------------------------------------------------------------------------
# Control in the main process
# --------------------------------------------------------------------------
class PiManager:
    def __init__(self, cores, l3):
        self.cores, self.l3 = cores, l3
        self.pool: ProcessPoolExecutor | None = None
        self.pool_key = None
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.st: dict = {"running": False}
        self.bench: dict = {"running": False, "results": [], "file": None}
        self._load_last_bench()

    # ---- Pool (as for Mandelbrot) ----
    def _get_pool(self, workers: int, placement: str) -> float:
        if self.pool and self.pool_key == (workers, placement):
            return 0.0
        self.shutdown()
        t0 = time.perf_counter()
        from mandelbrot import placement_order  # main process only
        order = placement_order(placement, self.cores, self.l3)
        self.pool = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                                        initargs=(multiprocessing.Value("i", 0), order))
        self.pool_key = (workers, placement)
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

    def _set(self, **kw):
        with self.lock:
            self.st.update(kw)

    # ---- one computation ----
    def _compute(self, p: dict, keep_text: bool = True) -> dict | None:
        digits, workers = p["digits"], p["workers"]
        n_terms = terms_for(digits)
        # one block per worker (measured fastest: more blocks = more merging); demanding (late) blocks first
        blocks = make_blocks(n_terms, workers * p.get("block_factor", 1) if workers > 1 else 1)
        phases = {}
        # "phase" is the text shown on the page; "phase_id" is a stable, language-neutral ID
        self._set(running=True, phase=L("Reihe (parallel)", "Series (parallel)"), phase_id="series", done=0,
                  total=len(blocks), digits=digits,
                  workers=workers, t_start=time.perf_counter(), phases=phases, label=p.get("label", ""),
                  terms=n_terms, error=None, check=None)
        t0 = time.perf_counter()

        # 1. Series: blocks in parallel
        futures = [self.pool.submit(series_block, b) for b in reversed(blocks)]
        parts: dict[int, tuple] = {}
        pids = set()
        for f in as_completed(futures):
            if self.stop_flag.is_set():
                for g in futures:
                    g.cancel()
                self._set(running=False, stopped=True, phase=L("abgebrochen", "stopped"), phase_id="stopped")
                return None
            k, pp, qq, tt, _, pid = f.result()
            parts[k] = (pp, qq, tt)
            pids.add(pid)
            with self.lock:
                self.st["done"] += 1
                self.st["workers_seen"] = len(pids)
        phases["reihe"] = time.perf_counter() - t0

        # 2. Merge: level by level; in parallel as long as there are several pairs
        t1 = time.perf_counter()
        level = [parts[k] for k in range(len(blocks))]
        self._set(phase=L("Zusammenführen", "Merge"), phase_id="merge")
        min_parallel = p.get("merge_parallel_from", 2)  # from this many pairs on, sending them to the workers pays off
        while len(level) > 1:
            pairs = [(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
            rest = [level[-1]] if len(level) % 2 else []
            # always via the pool, even the last pair: big GMP multiplications in the server process would block it
            need_p = len(level) > 2
            self._set(phase=L(f"Zusammenführen: {len(pairs)} Paare parallel", f"Merge: {len(pairs)} pairs in parallel")
                            if len(pairs) > 1 else L("Zusammenführen: letztes Paar – Einzelschritt auf 1 Kern",
                                                     "Merge: last pair – single step on 1 core"))
            merged = list(self.pool.map(combine, pairs, [need_p] * len(pairs)))
            level = merged + rest
        _, q, t = level[0]
        phases["zusammenfuehren"] = time.perf_counter() - t1

        # 3.+4. Square root, division, decimal conversion (serial, in one worker – the server stays responsive)
        t2 = time.perf_counter()
        self._set(phase=L("Wurzel, Division, Dezimalumwandlung – Einzelschritt auf 1 Kern, keine Zwischenstände möglich",
                          "Square root, division, decimal conversion – single step on 1 core, no progress updates possible"),
                  phase_id="finish")
        BENCH_DIR.mkdir(exist_ok=True)
        fut = self.pool.submit(finish_in_worker, (q, t, digits, str(RESULT_FILE) if keep_text else None))
        while not fut.done():  # stopping is not possible here (one single computation), but the status stays current
            time.sleep(0.1)
        t_abschluss, t_umwandlung, prefix, tail = fut.result()
        phases["abschluss"], phases["umwandlung"] = t_abschluss, t_umwandlung
        phases["uebergabe"] = max(0.0, time.perf_counter() - t2 - t_abschluss - t_umwandlung)
        elapsed = time.perf_counter() - t0

        check = self._check(prefix, digits)
        self._set(running=False, phase=L("fertig", "done"), phase_id="done", elapsed=elapsed, phases={k: round(v, 4) for k, v in phases.items()},
                  head=prefix[:102], tail=tail, check=check, workers_seen=len(pids))
        return {"elapsed": elapsed, "phases": phases, "check": check}

    @staticmethod
    def _check(prefix: str, digits: int) -> dict:
        """Compares the beginning of the result (up to 1 million digits) with the mpmath reference."""
        ref = reference(digits)
        if ref is None:
            return {"ok": None, "info": L("keine Referenz (mpmath fehlt)", "no reference (mpmath missing)")}
        n = len(ref) - 2
        ok = prefix[: n + 2] == ref
        if get_lang() == "de":
            info = (f"alle {digits:,} Stellen" if n == digits else f"erste {n:,} Stellen").replace(",", ".")
            return {"ok": ok, "info": f"{info} stimmen mit mpmath überein" if ok else f"Abweichung zu mpmath ({info})"}
        info = f"all {digits:,} digits" if n == digits else f"first {n:,} digits"
        return {"ok": ok, "info": f"{info} match mpmath" if ok else f"mismatch with mpmath ({info})"}

    def start(self, p: dict):
        if self.busy():
            raise RuntimeError(L("Es läuft bereits eine Pi-Berechnung", "A Pi computation is already running"))
        self.stop_flag.clear()
        self.st = {"running": True, "phase": L("starte Worker-Prozesse …", "starting worker processes …"),
                   "phase_id": "starting", "digits": p["digits"],
                   "workers": p["workers"], "done": 0, "total": 0, "t_start": time.perf_counter()}

        def run():
            try:
                startup = self._get_pool(p["workers"], p.get("placement", "windows"))
                self._set(startup=round(startup, 3))
                self._compute(p)
            except Exception as e:
                self._set(running=False, phase=L("Fehler", "Error"), phase_id="error", error=str(e))
        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        self.stop_flag.set()

    def status(self) -> dict:
        with self.lock:
            s = {k: v for k, v in self.st.items() if k != "t_start"}
            if self.st.get("running") and "t_start" in self.st:
                s["elapsed"] = time.perf_counter() - self.st["t_start"]
        s["bench"] = self.bench
        s["have_gmpy"] = HAVE_GMPY
        s["download"] = RESULT_FILE.exists()
        return s

    # ---- Scaling test ----
    def start_bench(self, p: dict, worker_list: list[int], repeats: int):
        if self.busy():
            raise RuntimeError(L("Es läuft bereits eine Pi-Berechnung", "A Pi computation is already running"))
        self.stop_flag.clear()
        self.bench = {"running": True, "results": [], "file": None, "params": {**p, "repeats": repeats},
                      "plan": worker_list, "current": None}

        def run():
            try:
                for n in worker_list:
                    if self.stop_flag.is_set():
                        break
                    self.bench["current"] = n
                    startup = self._get_pool(n, p.get("placement", "windows"))
                    runs = []
                    for k in range(repeats):
                        label = L(f"Skalierungstest: {n} Worker, Lauf {k + 1}/{repeats}",
                                  f"Scaling test: {n} workers, run {k + 1}/{repeats}")
                        r = self._compute({**p, "workers": n, "label": label}, keep_text=(k == repeats - 1))
                        if r is None:
                            break
                        runs.append(r)
                    if len(runs) < repeats:
                        break
                    best = sorted(runs, key=lambda r: r["elapsed"])[len(runs) // 2]  # median run with its phases
                    sec = best["elapsed"]
                    t1 = self.bench["results"][0]["seconds"] if self.bench["results"] else sec
                    self.bench["results"].append({
                        "workers": n, "seconds": round(sec, 3), "startup": round(startup, 3),
                        "speedup": round(t1 / sec, 2), "efficiency": round(t1 / sec / n * 100, 1),
                        "phases": {k: round(v, 3) for k, v in best["phases"].items()},
                        "ok": best["check"]["ok"], "runs": [round(r["elapsed"], 3) for r in runs]})
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
        meta = {"zeit": stamp, "stellen": p["digits"], "platzierung": p.get("placement", "windows"),
                "wiederholungen": self.bench["params"]["repeats"], "gmpy2": HAVE_GMPY}
        path = BENCH_DIR / f"pi_{stamp}.json"
        path.write_text(json.dumps({**meta, "ergebnisse": self.bench["results"]}, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        csv_path = BENCH_DIR / "pi_benchmarks.csv"
        new = not csv_path.exists()
        de = lambda v: str(v).replace(".", ",")
        with csv_path.open("a", newline="", encoding="utf-8") as f:
            wr = csv.writer(f, delimiter=";")
            if new:
                wr.writerow(list(meta) + ["worker", "sekunden", "prozessstart_s", "beschleunigung", "effizienz_prozent",
                                          "reihe_s", "zusammenfuehren_s", "abschluss_s", "umwandlung_s", "korrekt"])
            for r in self.bench["results"]:
                ph = r["phases"]
                wr.writerow(list(meta.values()) + [r["workers"]] + [de(r[k]) for k in
                            ("seconds", "startup", "speedup", "efficiency")] +
                            [de(ph[k]) for k in ("reihe", "zusammenfuehren", "abschluss", "umwandlung")] + [r["ok"]])
        return path.name

    def _load_last_bench(self):
        files = sorted(BENCH_DIR.glob("pi_2*.json")) if BENCH_DIR.exists() else []
        if not files:
            return
        try:
            d = json.loads(files[-1].read_text(encoding="utf-8"))
            self.bench = {"running": False, "results": d["ergebnisse"], "file": files[-1].name,
                          "params": {"digits": d["stellen"], "placement": d["platzierung"],
                                     "repeats": d["wiederholungen"]}}
        except Exception:
            pass
