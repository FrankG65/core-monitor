"""Automatic self-test of Core Monitor (used by the GitHub Actions workflow, also runs locally).

Starts the server on a free port (127.0.0.1), then checks:
  - /api/info and the language switch (German / English)
  - every available computation method renders an image; all CPU methods are bit-identical to numba
    (GPU methods may differ slightly or be unavailable, e.g. on a machine without a graphics card)
  - a short scaling test and Pi with 10,000 digits verified against mpmath
  - requests from outside (foreign Host / Origin) are rejected, logged and counted
  - the privacy check on all files tracked by git (if git is available)
Files the test creates in benchmarks/ are removed again afterwards.

    python tools\\selftest.py [--require numba,numpy,csharp,...]

--require: methods that must be available (SIMD/assembler are dropped automatically if the CPU has no AVX2).
Exit code 0 = all checks passed.
"""
from __future__ import annotations

import argparse, base64, hashlib, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmarks"
failures: list[str] = []
results: list[tuple[str, bool, str]] = []   # (section, ok, text) for the summary
notes: list[str] = []
_section = ""


def section(name: str):
    global _section
    _section = name
    print("\n" + name, flush=True)


def check(ok: bool, text: str):
    print(("  OK    " if ok else "  FAIL  ") + text, flush=True)
    results.append((_section, ok, text))
    if not ok:
        failures.append(text)


def write_summary():
    """Markdown summary for the run page (GitHub Actions sets GITHUB_STEP_SUMMARY)."""
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    system = "Windows" if os.name == "nt" else "Linux"
    lines = [f"## Core Monitor self-test ({system}): " + ("all checks passed ✅" if not failures else f"{len(failures)} check(s) failed ❌"), ""]
    lines += [f"- {n}" for n in notes] + ["", "| Section | Check | Result |", "|---|---|---|"]
    lines += [f"| {s} | {txt.replace('|', '/')} | {'✅' if ok else '❌'} |" for s, ok, txt in results]
    with open(target, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self):
        self.base = f"http://127.0.0.1:{free_port()}"
        self.seclog = Path(tempfile.mkdtemp()) / "security.log"   # keep test entries out of logs/security.log
        env = dict(os.environ, PORT=self.base.rsplit(":", 1)[1], KM_LANG="en", PYTHONUNBUFFERED="1",
                   KM_SECURITY_LOG=str(self.seclog))
        env.pop("OPEN_BROWSER", None)
        self.log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        for _ in range(240):
            try:
                self.info = self.get("/api/info")
                return
            except Exception:
                if self.proc.poll() is not None:
                    break
                time.sleep(0.5)
        self.log.seek(0)
        raise SystemExit("server did not start:\n" + self.log.read()[-3000:])

    def get(self, path):
        return json.loads(urllib.request.urlopen(self.base + path, timeout=120).read())

    def post(self, path, body):
        r = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(r, timeout=300).read())

    def status_of(self, path, data=None, headers=None) -> int:
        """HTTP status of a request with custom headers (e.g. a foreign Host or Origin)."""
        r = urllib.request.Request(self.base + path, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
        try:
            return urllib.request.urlopen(r, timeout=30).status
        except urllib.error.HTTPError as e:
            return e.code

    def wait(self, path, bench=False, limit=600):
        t0 = time.time()
        time.sleep(0.5)
        while time.time() - t0 < limit:
            s = self.get(path)
            if not ((s.get("bench") or {}).get("running") if bench else s.get("running")):
                return s
            time.sleep(0.3)
        raise TimeoutError(path)

    def stop(self):
        try:   # end the worker processes too (they would otherwise exit on their own a few seconds later)
            import psutil
            for child in psutil.Process(self.proc.pid).children(recursive=True):
                child.kill()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def image(srv: Server, engine: str):
    """Render a small image; returns (status, pixel hash)."""
    srv.post("/api/mandel/start", {"width": 400, "height": 640, "maxiter": 1000, "engine": engine})
    s = srv.wait("/api/mandel/status")
    tiles, since = [], 0
    while True:
        r = srv.get(f"/api/mandel/tiles?job={s['job']}&since={since}")
        tiles += r["tiles"]
        if r["next"] == since:
            break
        since = r["next"]
    h = hashlib.sha256()
    for t in sorted(tiles, key=lambda t: (t["y"], t["x"])):
        h.update(base64.b64decode(t["data"]))
    return s, h.hexdigest()


def privacy():
    """Privacy check on the files tracked by git (same checker as the export)."""
    try:
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        print("  SKIP  privacy check (git not available)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for f in filter(None, files):
            dst = Path(tmp) / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / f, dst)
        if os.name == "nt":
            patterns = [os.environ.get("USERPROFILE"), os.environ.get("COMPUTERNAME") and os.environ["COMPUTERNAME"] + ".",
                        os.environ.get("USERNAME") and "\\Users\\" + os.environ["USERNAME"] + "\\"]
        else:   # Linux: home folder, user name in paths, computer name (only if distinctive enough)
            host = socket.gethostname()
            patterns = [os.environ.get("HOME") if os.environ.get("HOME") not in ("/", "/root") else None,
                        os.environ.get("USER") and "/home/" + os.environ["USER"] + "/", host if len(host) >= 6 else None]
        patterns = [p for p in (*patterns, str(ROOT)) if p]
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "privacy_check.py"), tmp, *patterns], capture_output=True, text=True)
        print("        " + (r.stdout.strip().splitlines() or [""])[-1])
        check(r.returncode == 0, f"privacy check on {len([f for f in files if f])} tracked files")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--require", default="", help="comma-separated methods that must be available")
    args = ap.parse_args()

    before = set(BENCH.glob("*")) if BENCH.exists() else set()
    saved = {p: p.read_bytes() for p in before if p.suffix in (".csv", ".txt")}   # files the test may change
    srv = Server()
    try:
        info = srv.info
        cpu = info["system"]["cpu"]
        notes.append(f"System: {cpu['name']} – {cpu['physical']} cores / {cpu['logical']} threads, AVX2={cpu['isa']['avx2']}")
        notes.append(f"Available ({len(info['engines'])}): {', '.join(info['engines'])}")
        notes.extend(f"Greyed out: {e} – {why}" for e, why in info["engines_off"].items())
        print("\n".join(notes))

        section("Language")
        check(info.get("lang") == "en", "server starts in English (KM_LANG=en)")
        de = srv.post("/api/lang", {"lang": "de"})
        check(de.get("lang") == "de" and "zeilenweise" in json.dumps(srv.get("/api/info"), ensure_ascii=False), "switch to German")
        srv.post("/api/lang", {"lang": "en"})
        check("row by row" in json.dumps(srv.get("/api/info")), "switch back to English")

        section("Protection against requests from outside")
        port = srv.base.rsplit(":", 1)[1]
        check(srv.status_of("/api/info", headers={"Host": f"evil.example:{port}"}) == 403, "foreign Host header (DNS rebinding) rejected with 403")
        check(srv.status_of("/api/load/start", json.dumps({"seconds": 1, "intensity": 0.05}).encode(),
                            {"Content-Type": "application/json", "Origin": "https://evil.example"}) == 403,
              "POST from a foreign website (Origin) rejected with 403")
        check(srv.status_of("/api/info", headers={"Host": f"localhost:{port}", "Origin": f"http://localhost:{port}"}) == 200,
              "own page via localhost still allowed")
        sec = srv.get("/api/security")
        check(sec.get("blocked") == 2 and sec["recent"][0]["reason"] == "origin", "rejections counted for the warning on the page")
        logged = srv.seclog.read_text(encoding="utf-8") if srv.seclog.exists() else ""
        check(logged.count("BLOCKED") == 2, "rejections written to the security log")

        section("Availability")
        required = [e for e in args.require.split(",") if e]
        if not cpu["isa"]["avx2"]:
            required = [e for e in required if not (e.endswith("_simd") or e == "asm")]
            notes.append("CPU without AVX2: SIMD and assembler methods are not required")
        for e in required:
            check(e in info["engines"], f"{e} available")
        for e in ("gpu", "gpu_float"):
            if e not in info["engines"]:
                check(bool(info["engines_off"].get(e)), f"{e} not available here, greyed out with a reason")

        section("Mandelbrot (400 x 640, 1,000 iterations)")
        ref = None
        for e in info["engines"]:
            s, h = image(srv, e)
            ok = not s.get("error") and s.get("done") == s.get("total", -1) > 0
            if e == "numba" or ref is None:
                ref = ref or h
            # GPU may differ slightly - except GPU double on POCL (OpenCL on the CPU, Linux test): bit-identical there
            gpu = e.startswith("gpu") and not (e == "gpu" and os.environ.get("KM_OPENCL_CPU") == "1")
            same = h == ref
            check(ok and (same or gpu), f"{e}: {s.get('done')}/{s.get('total')} tiles, "
                  + ("bit-identical to numba" if same else "differs slightly (GPU, expected)" if gpu else "DIFFERS from numba")
                  + (f" – {s['error']}" if s.get("error") else ""))

        section("Scaling test (1 and 2 workers)")
        srv.post("/api/mandel/bench", {"width": 400, "height": 640, "maxiter": 500, "engine": info["engines"][0],
                                       "worker_list": [1, 2], "repeats": 1})
        b = srv.wait("/api/mandel/status", bench=True)["bench"]
        check(not b.get("error") and [r["workers"] for r in b["results"]] == [1, 2], f"results {[(r['workers'], r['seconds']) for r in b['results']]}")

        section("Pi (10,000 digits)")
        srv.post("/api/pi/start", {"digits": 10000, "workers": min(4, info["logical"])})
        s = srv.wait("/api/pi/status")
        check(bool((s.get("check") or {}).get("ok")) and not s.get("error"), (s.get("check") or {}).get("info") or str(s.get("error")))
    finally:
        srv.stop()
        time.sleep(1)
        # remove what the test created, restore what it changed
        if BENCH.exists():
            for p in set(BENCH.glob("*")) - before:
                p.unlink()
            for p, data in saved.items():
                p.write_bytes(data)

    section("Privacy")
    privacy()

    write_summary()
    print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED:\n  - " + "\n  - ".join(failures)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
