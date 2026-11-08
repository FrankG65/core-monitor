English | [Deutsch](README.de.md)

# Core Monitor – Feasibility Study

A web interface for monitoring all CPU cores and putting a targeted load on them – with the Mandelbrot set as a real,
parallel computation and a scaling test.

**Status:** feasibility study, experimental. Runs on Windows 10/11 x64 only.

## Getting started

    start.bat

or manually:

    python -m pip install -r requirements.txt
    python -m pip install numba        (optional, roughly 3–4× faster computation method)
    python server.py

Then open http://127.0.0.1:8000 in your browser (start.bat opens the page itself if it is not already open).

**Language:** The **DE | EN** switch in the page header toggles between German and English. The browser remembers the
choice; without a choice, the page starts in English. Server messages follow the chosen language. The server's start
language can be set with `set KM_LANG=de` or `set KM_LANG=en` (default: English).

**Security:** The server is bound to `127.0.0.1` and can therefore only be reached from this computer, not from the LAN
or the internet. The port can be changed with `set PORT=8001`.

## Note on antivirus software (unfounded warnings)

Antivirus software (e.g. Microsoft Defender, Trend Micro) and Windows SmartScreen may raise an alarm about this program
or block parts of it – this is a **false positive**, the program is harmless. Scanners judge by behaviour patterns, and
Core Monitor shows several that malware shows too:

- self-compiled `.exe` files without a digital signature and without a "reputation" (C#, Rust, C, C++, assembler, GPU),
- freshly extracted, unknown files from a ZIP,
- many processes started at once (up to 48 Python workers) and 100 % load on all cores (similar to a crypto miner).

**Symptoms:** "Access is denied" or a slow first start of a computation method; an `.exe` is moved to quarantine (the
computation method appears greyed out with "Program missing – probably removed by antivirus software …"); the SmartScreen
warning "Windows protected your PC". Observed on the reference machine: right after extracting, individual starts failed
with "Access is denied"; a few seconds later everything ran.

**What to do:**

1. Wait a few seconds or restart `start.bat` – the monitor itself retries a blocked start for up to 10 s.
2. Before extracting: right-click the ZIP file → Properties → "Unblock". SmartScreen: "More info" → "Run anyway".
3. Check the antivirus quarantine and restore the file.
4. Add the folder as an exclusion – **only if it comes from a trustworthy source** (built yourself or obtained directly from the author).
5. To double-check, have individual `.exe` files scanned at [VirusTotal](https://www.virustotal.com), or use the "Lite" package and compile everything yourself.

Please do **not** turn off your antivirus software. numba, numpy and Pi still work when all `.exe` files are blocked.

## Security: requests from outside are rejected

The server listens only on `127.0.0.1` (this PC). In addition, every request – HTTP and the live connection
(WebSocket) – must come from this PC **and** be addressed to `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>`;
if the browser names the requesting page (Origin), it must be this page as well. This blocks attacks such as
**DNS rebinding** and foreign websites in the browser trying to control the monitor.
Rejected requests get HTTP 403, are written to `logs/security.log` (time, reason, method, path, Host, Origin,
user agent; at most 4 × 1 MB) and are **reported**: a warning in the console window and a red notice in the page
header with the latest events. The automatic self-test checks this on every push.

## Distributing to other PCs (export)

| Package | Build with | Size | Target PC needs |
|---|---|---|---|
| **Full** | `export_full.bat` | ZIP ≈ 104 MB, extracted ≈ 281 MB | only Windows 10/11 (64-bit) – no Python, no internet, no admin rights |
| **Lite** | `export_lite.bat` | ZIP ≈ 0.1 MB | Python 3.11+ and internet on first start; optionally .NET SDK, Rust, Visual Studio C++ (see INSTALLATION.txt) |

- Both batch files call `tools\export.ps1 -Variante Full` or `-Variante Lite`.
- Output: `export\CoreMonitor_Full_<date>.zip` or `export\CoreMonitor_Lite_<date>.zip`.
- Both packages contain the installation guide in English (`INSTALLATION.txt`) and German (`INSTALLATION.de.txt`;
  templates in `tools\`: `INSTALLATION_Full.txt`, `INSTALLATION_Lite.txt`, `INSTALLATION_Komplett.txt`, `INSTALLATION_Klein.txt`),
  this description as `README.md` (English) and `README.de.md` (German), and both project reports as PDF:
  `Project_Report_Core_Monitor.pdf` (English) and `Projektbericht_Parallelisierung.pdf` (German).
- **Full** contains an embedded Python 3.11.9 with all packages, all computation methods precompiled (C/C++/assembler/GPU
  with the static runtime library, GPU shaders precompiled, `vcomp140.dll`; Rust statically linked; C# as a self-contained
  .exe) and the source code. `start.bat` detects the embedded Python and then installs/compiles nothing.
- **Lite** contains only source code; `start.bat` installs the Python packages and compiles whatever the available tools
  allow. If a tool is missing, the affected computation methods appear greyed out with a hint.
- **Privacy check** (`tools\privacy_check.py`, runs automatically on every export): all files of the package – text and
  binary files (ASCII and UTF-16) as well as the text of the PDFs – are searched for information about the PC that built
  it: user profile/user name, project path, computer name, LAN addresses, MAC addresses, OneDrive path. The patterns are
  determined at run time; if anything matches, no ZIP is created. To make this pass: C# without debug information and
  with neutral paths (`MandelBench.csproj`), pip launcher programs (`site-packages\bin`, which contain the PC's Python
  path) are left out, `__pycache__` is left out, C/C++/assembler/Rust contain no debug paths.
- Your own measurement data (`benchmarks\`), local tool settings, logs and intermediate files are not included; the
  mpmath reference for Pi is included in the "Full" package (in the "Lite" package it is generated on the first Pi run).
- If the tools are missing at start-up, the server uses the bundled programs; it only recompiles when a source file is
  noticeably (> 1 minute) newer and the tools are available.
- Tested: both packages in unfamiliar folders; "Full" with an empty PATH (all 13 computation methods, Pi, scaling test)
  and on a simulated small PC; "Lite" with all tools (everything compiled, 13 computation methods) and with Python only.

## Automatic tests and releases (GitHub Actions)

- **CI** (`.github/workflows/ci.yml`): on every push to `main` and every pull request, a Windows runner builds all
  computation methods from source (C#, Rust, C/C++/assembler/GPU host) and runs `tools/selftest.py`: every method
  renders, all CPU methods are bit-identical to numba, scaling test, Pi with 10,000 digits verified against mpmath,
  language switch, privacy check of all tracked files. The runner has no graphics card, so the GPU methods must be
  greyed out with a reason. Result: green tick / red cross next to the commit and under **Actions**.
- **Release** (`.github/workflows/release.yml`, started by hand: Actions → Release → Run workflow → tag, e.g. `v1.1`):
  builds and tests the "Full" package on the runner and attaches `CoreMonitor_Full_<date>.zip` to the release
  (created with `docs/release_notes.md` if it does not exist yet).
- Locally: `python tools\selftest.py` (files it creates in `benchmarks\` are removed again).

## Hardware detection

At start-up, `hardware.py` detects the machine, and everything else adapts to it. This way the program also runs on
other PCs.
- **CPU:** name, vendor, cores and threads, SMT, core/thread mapping, L3 groups (CCX), NUMA nodes, processor groups,
  clock speed, instruction sets (SSE2, AVX, AVX2, FMA, AVX-512F), memory
- **Graphics cards:** all of them via DXGI (`native/bin/mandel_gpu.exe --probe`) with name, memory, driver, feature level,
  compute shader and double support. The card with the most dedicated memory is used automatically (no software adapter).
- **Derived from this:** worker/thread sliders (maximum and default = number of threads), the steps of the scaling tests
  (powers of two, half/full core count, middle of the SMT range, all threads), core view and heatmap (by L3 group and
  SMT, otherwise simple groups), placements ("compact" only with SMT; above 64 threads only "Windows"), offered
  computation methods (SIMD and assembler only with AVX2, GPU only with Direct3D 11 compute, "GPU double" only with
  double support; unusable ones appear greyed out with the reason), chart axes and the numbers in the explanatory texts.
  Measurements in the explanations are marked as values from the reference machine.
- C, C++ and assembler are compiled **without** `/arch:AVX2` and check at run time whether AVX2 is available; this way
  they also run on older CPUs (same image, same speed as measured before).
- The detected values are shown in the "System" box at the top of the page and by `GET /api/system`.
- Testing a different machine: `set KM_SIMULATE=logical=8,physical=8,avx2=0,fma=0,gpu=0` before starting.

## Features

- **Load per core**: all 48 threads, grouped by the 24 physical cores (2 SMT threads each) and the 8 L3 groups (CCX,
  3 cores each). Updated every second via WebSocket, with a 60 s history per thread. Plus total CPU, clock speed and RAM.
  On Windows the core ↔ thread mapping comes from `GetLogicalProcessorInformationEx` (via ctypes); otherwise the
  assumption "threads 2n and 2n+1 = core n" applies.
- **Mandelbrot set** (next to the core view, so that the load distribution is visible):
  - the image is split into tiles, which a process pool (`ProcessPoolExecutor`) with 1–48 workers computes
  - computation methods (13, see the table below): Python + numba (JIT-compiled), Python + numpy (vectorised), C# / .NET
    with real threads or C# + SIMD (AVX2, 4 pixels per thread)
    (only if the .NET SDK is installed; start.bat compiles the C# program, otherwise this happens on first use)
  - tile order: row by row or "demanding tiles first" (a rough cost estimate up front; the time it takes is included in
    the measurement)
  - resolution, max. iterations, region and tile size are selectable; start/stop; progress and time
  - tiles appear live as soon as they are finished; optionally coloured by worker, with a bar per worker below showing
    the number of its tiles
  - by default the image is rotated 90° clockwise (portrait, real axis vertical, tip at the top); can be switched off
    with "rotated 90°". The resolution then counts as portrait (e.g. 1200 × 1920).
  - clicking into the image zooms in 4×, right-click zooms out
  - the pool persists after a computation; process start-up is measured separately and not counted
  - worker placement: "Windows decides", "1 thread per core first" (spread across all CCXs) or "compact" (both threads of
    a core, CCX by CCX), implemented via CPU affinity per worker process
- **Scaling test**: the same image computed in turn with 1, 2, 4, 8, 12, 16, 24, 32 and 48 workers; optionally 1, 3 or
  5 runs per step (median). Table and chart (measured vs. ideal speedup, one line per placement for comparison). Results
  are saved to `benchmarks/mandelbrot_<timestamp>.json` and appended to `benchmarks/mandelbrot_benchmarks.csv`
  (semicolon, decimal comma – readable directly in a German Excel).
- **Computing Pi**: 1,000 to 100 million decimal places, Chudnovsky formula with binary splitting, big numbers with GMP
  (`gmpy2`). The series is split into one block per worker (parallel), then merged pairwise (less and less parallel
  towards the top), and finally square root, division and decimal conversion (serial). The four phases are measured
  separately and shown as bars. The first 100 and last 50 digits are shown on the page, all digits are available as a
  download (`benchmarks/pi_ergebnis.txt`). Verified against *mpmath* (an independent implementation, up to 1 million
  digits; reference in `benchmarks/pi_referenz_mpmath.txt`). Scaling test with a breakdown by phase, results in
  `benchmarks/pi_<timestamp>.json` and `benchmarks/pi_benchmarks.csv`.
- **Activity indicator**: every running computation (Mandelbrot, both scaling tests, Pi, load generator, prime benchmark)
  shows a spinner with the current phase and time. In addition there is a real heartbeat: if no data arrives from the
  server for more than 5 s, the indicator turns red ("no response for … s"). With "reduce motion" enabled in the
  operating system, the spinner stands still.
- **Automatic reload**: the server sends a start ID and a fingerprint of the page files. If the server restarts or a
  file in `static/` changes, every open page reloads itself immediately (measured: after 0.7–0.8 s). After a brief
  connection glitch with an unchanged ID, the page is not reloaded and running displays are kept.
- **No extra browser tab**: start.bat no longer opens a tab unconditionally. After starting, the server waits 3.5 s; if
  an open page has reconnected by then, only that page reloads. If no page is open, it opens exactly one tab
  (controlled by `OPEN_BROWSER=1`, which start.bat sets; with `python server.py` run by hand, nothing is opened).
- **Bilingual (DE | EN)**: switch in the header, choice saved in the browser, default = English; server
  messages in the chosen language (`POST /api/lang`), start language via `KM_LANG=de|en`.
- **Heatmap** of all threads over the last 2 minutes
- **Load generator**: one process per thread, intensity 5–100 %, selectable duration, optionally pinned to the thread
  (CPU affinity). Threads can be selected by clicking.
- **Prime benchmark**: serial vs. distributed across all cores

## The 13 computation methods (Mandelbrot)

| Computation method | Kind | Description |
|---|---|---|
| Python + numba | processes, 1 pixel per step | Python, compiled to machine code by numba; one process per core because of the GIL |
| Python + numpy | processes, array computation | pure Python with numpy, computes whole tiles as arrays; the slowest variant |
| C# / .NET | threads, 1 pixel per step | C# (.NET 10) with real threads in one process |
| C# / .NET + SIMD | threads, 4 pixels at once | like C#, 4 pixels at once per thread (AVX2, `Vector256<double>`) |
| Rust | threads, 1 pixel per step | Rust with real threads and a shared tile queue |
| Rust + SIMD | threads, 4 pixels at once | Rust with AVX2 instructions |
| C | threads, 1 pixel per step | C with Windows threads (`CreateThread`) |
| C + SIMD | threads, 4 pixels at once | C with AVX2 intrinsics |
| C++ | threads, 1 pixel per step | C++ with `std::thread` and `std::atomic` |
| C++ + SIMD | threads, 4 pixels at once | C++ with AVX2 intrinsics |
| Assembler | threads, 4 pixels at once | hand-written x64 assembler (AVX2) for the inner loop, threads in C |
| GPU (double) | graphics card, double precision | Direct3D compute shader, one GPU execution unit per pixel; double precision like the CPU, yet a few pixels still differ (driver) |
| GPU (float) | graphics card, single precision | like GPU (double), much faster, image differs slightly |

Internal IDs (API, measurement files): `numba`, `numpy`, `csharp`, `csharp_simd`, `rust`, `rust_simd`, `c`, `c_simd`,
`cpp`, `cpp_simd`, `asm`, `gpu`, `gpu_float`. The order "demanding tiles first" is called `teuer` internally and
`aufwendige_zuerst` in CSV/JSON.

**Note:** The keys and values in the benchmark files (CSV/JSON in `benchmarks/`) and some API parameter values
(e.g. `gesamt`, `verteilt`, `kompakt`, `zeilen`) are German and were deliberately kept, so that existing measurement
files and scripts remain compatible.

## Structure

| File | Contents |
|---|---|
| `hardware.py` | hardware detection (CPU, topology, instruction sets, graphics cards), scaling steps, simulation for tests |
| `server.py` | small launcher (sets up the environment, starts `app.py`) – deliberately tiny, because worker processes reload it |
| `app.py` | FastAPI backend: measurement (psutil), WebSocket, hardware integration, load generator, prime benchmark, API |
| `worker_util.py`, `lastgen.py` | lightweight modules for worker and load processes (no web server, no numba in the worker) |
| `tools/export.ps1`, `export_full.bat`, `export_lite.bat` | build the distribution packages (`-Variante Full` or `Lite`, see "Distributing") |
| `tools/glossar.py` | glossary list – the single source for "Glossary" in README.md, "Begriffe kurz erklärt" in README.de.md, the web page and the report (`python tools\glossar.py` regenerates, `… check` checks the links) |
| `mandelbrot.py` | Mandelbrot computation methods (numba/numpy), colouring, process pool, scaling test, CSV/JSON |
| `static/index.html`, `app.js`, `style.css` | user interface and core view, without external libraries |
| `static/mandel.js` | Mandelbrot controls, live tiles, scaling chart (SVG) |
| `pi.py` | Pi computation (Chudnovsky, binary splitting, gmpy2), process pool, phase timing, verification, scaling test |
| `static/pi.js` | Pi controls, phase bars, digit display, scaling chart |
| `native/` | C (`c/mandel.c`), C++ (`cpp/mandel.cpp`), assembler (`asm/kernel.asm`), GPU (`gpu/mandel.hlsl`, `gpu/mandel_gpu.cpp`), shared kernel `mandel_core.h`, `build.bat` |
| `rust/mandelbench/` | Rust counterpart (real threads, scalar and AVX2 SIMD), same protocol as C#; computation methods "Rust" and "Rust SIMD" |
| `csharp/MandelBench/` | C# counterpart (.NET 10, real threads): same tiles, formula and colours; launched by the server as computation method "C#" |
| `benchmarks/` | saved scaling test results |

## API

- `GET /api/info` – CPU data, topology (`topology`, `l3`), available computation methods, current language (`lang`)
- `POST /api/lang` – `{"lang":"de"}` or `{"lang":"en"}`: language of the server messages
- `POST /api/mandel/start` – `{"workers":48, "width":1200, "height":1920, "maxiter":1000, "tile":128, "region":"gesamt", "engine":"numba", "rot90":true}`
  (optionally `cx`, `cy`, `cw` for a custom region)
- `POST /api/mandel/stop`
- `GET /api/mandel/status`
- `GET /api/mandel/tiles?job=1&since=0` – finished tiles (RGB, base64)
- `POST /api/mandel/bench` – like `start`, without `workers`; optionally `worker_list`, `repeats` (median)
- `GET /api/mandel/bench/history` – all saved scaling tests
- parameter `placement` (for `start` and `bench`): `windows` | `verteilt` (1 thread per core first) | `kompakt` (compact);
  `order`: `zeilen` (row by row) | `teuer` (demanding tiles first); `engine`: `numba` | `numpy` | `csharp` | `csharp_simd` | `rust` | `rust_simd` | `c` | `c_simd` | `cpp` | `cpp_simd` | `asm` | `gpu` | `gpu_float`; `cardioid`: `true` | `false`
- `POST /api/pi/start` – `{"digits":1000000, "workers":48}`; `POST /api/pi/stop`; `GET /api/pi/status`
- `POST /api/pi/bench` – `{"digits":10000000, "repeats":3}` (optionally `worker_list`); `GET /api/pi/download` – all digits as .txt
- `POST /api/load/start` – `{"cores":[0,1], "intensity":0.8, "seconds":30, "pin":true}` (omit `cores` = all)
- `POST /api/load/stop`
- `POST /api/bench` – `{"limit":3000000}` (primes)
- `WS /ws` – measurements every second

## Findings (Threadripper 3960X, 24 cores / 48 threads)

Reference machine: AMD Threadripper 3960X (24 cores / 48 threads), NVIDIA GeForce RTX 3090.

- Python uses multiple cores only through **multiple processes** (because of the GIL), not through threads.
- On Windows, starting the processes takes noticeable time (48 workers with numba: about 2–8 s). That is why the pool
  persists and start-up is reported separately.
- Primes up to 3 million: 7.0 s serial, 0.7 s parallel, i.e. about 10× faster.
- **Mandelbrot scaling test** (2560 × 1600, 5000 iterations, full view, numba, 128 px tiles):

  | Workers | 1 | 2 | 4 | 8 | 12 | 16 | 24 | 32 | 48 |
  |---|---|---|---|---|---|---|---|---|---|
  | Time (s) | 10.41 | 5.43 | 2.78 | 1.42 | 1.00 | 0.81 | 0.63 | 0.53 | 0.43 |
  | Speedup | 1.0 | 1.9 | 3.8 | 7.4 | 10.4 | 12.9 | 16.4 | 19.5 | 24.5 |

  Almost linear up to 8 workers, then the curve flattens. The first guess ("SMT threads add little") was **not**
  confirmed by the placement measurements, see below: the main cause is the short run time with many workers.
- For this task, numba is about 3–4× faster than vectorised numpy.
- **Rust comparison** (2026-11-08, same parameters: 1600 × 2560 rotated, 5000 iterations, row by row, placement
  "Windows", median of 3; time in s, speedup):

  | Workers/threads | numba | C# | Rust | C# SIMD | Rust SIMD |
  |---|---|---|---|---|---|
  | 1 | 6.18 (1.0×) | 6.09 (1.0×) | 6.21 (1.0×) | 1.65 (1.0×) | 1.63 (1.0×) |
  | 8 | 0.93 (6.6×) | 0.83 (7.3×) | 0.85 (7.3×) | 0.23 (7.3×) | 0.22 (7.5×) |
  | 24 | 0.51 (12.1×) | 0.40 (15.4×) | 0.40 (15.6×) | 0.11 (15.0×) | 0.10 (15.8×) |
  | 48 | 0.34 (18.4×) | 0.23 (26.9×) | 0.22 (27.8×) | 0.070 (23.6×) | **0.062 (26.3×)** |
  | Start | 1.7–5.8 s (pool) | 0.14 s | 0.04 s | 0.14 s | 0.04 s |

  - Rust (`rust/mandelbench`, no external crates) uses the same protocol as C#: same tiles, formula and colours, real
    threads with a shared tile queue, optional affinity, SIMD with AVX2 intrinsics without FMA.
    **Bit-identical image** to numba and C# (verified, including leftover columns).
  - Rust and C# are equally fast: both generate nearly the same machine code. Rust starts faster and was a good 10 %
    ahead with 48 SIMD threads. What matters are real threads (versus Python processes) and SIMD, not the language.
  - Rust is installed per user via rustup (`%USERPROFILE%\.cargo`, without changing PATH); start.bat and the server find
    cargo there too. Without Rust, the two entries are simply missing from the selection.
  - Pi in Rust was not built: fast big-number libraries for Rust (`rug`) require GMP, which is tedious to compile on
    Windows/MSVC; pure Rust libraries (`num-bigint`) are many times slower at millions of digits. The comparison would
    then measure the library, not the parallelisation.
- **C, C++ and assembler** (2026-11-08, Visual Studio 2026 / MSVC 14.51, `/O2 /arch:AVX2 /fp:precise`, same parameters,
  row by row, placement "Windows", median of 3; time in s):

  | Threads | numba | C# | Rust | C | C++ | C# SIMD | Rust SIMD | C SIMD | C++ SIMD | Assembler (AVX2) |
  |---|---|---|---|---|---|---|---|---|---|---|
  | 1 | 6.18 | 6.09 | 6.21 | 6.08 | 6.06 | 1.65 | 1.63 | 1.66 | 1.67 | 1.69 |
  | 8 | 0.93 | 0.83 | 0.85 | 0.81 | 0.80 | 0.23 | 0.22 | 0.22 | 0.23 | 0.23 |
  | 24 | 0.51 | 0.40 | 0.40 | 0.39 | 0.39 | 0.11 | 0.10 | 0.11 | 0.11 | 0.11 |
  | 48 | 0.34 | 0.23 | 0.22 | 0.23 | 0.24 | 0.070 | 0.062 | 0.070 | 0.071 | 0.072 |
  | Start | 1.7–5.8 | 0.14 | 0.04 | 0.10 | 0.10 | 0.14 | 0.04 | 0.10 | 0.10 | 0.10 |

  - `native/`: C with Win32 threads (`CreateThread`, `InterlockedIncrement`), C++ with `std::thread`/`std::atomic`,
    shared computation part `mandel_core.h` (scalar and AVX2 intrinsics), hand-written MASM kernel `asm/kernel.asm`
    (AVX2, 4 pixels in ymm registers, without FMA, extensively commented) with a C host program.
    `native/build.bat` finds Visual Studio via vswhere; start.bat calls it and skips it if Visual Studio is not installed.
  - All five produce a **bit-identical image** (0 pixels different). This requires `/fp:precise` (no FMA) and
    `#pragma loop(no_vector)` on the colour computation, so that the compiler does not switch to vector math functions.
  - **Result:** all compiled languages are within a few percent of each other; the assembler kernel is no faster than
    the compiler. The loop is limited by the latency between dependent computation steps, not by the language. What
    really counts: SIMD (≈ 3.7×) and real threads instead of processes.
- **Smarter algorithm: skipping the cardioid/bulb** (an option in all computation methods, including SIMD and
  assembler; with 4 pixels at once, points inside the cardioid start as "done"). Formula: q = (x − ¼)² + y², inside the
  set if q·(q + x − ¼) ≤ y²/4 or (x + 1)² + y² ≤ 1/16. The image stays **exactly the same** (0 pixels different in all
  11 CPU computation methods, verified in the full view and directly at the edges of the cardioid and the period-2 bulb).
  Measurement with Rust and Rust SIMD (1600 × 2560, 5000 it.; time without → with the test):

  | View | Rust, 1 thread | Rust, 48 threads | Rust SIMD, 1 thread | Rust SIMD, 48 threads |
  |---|---|---|---|---|
  | Full view | 6.38 → 0.73 s (8.7×) | 0.24 → 0.11 s (2.3×) | 1.67 → 0.29 s (5.7×) | 0.068 → 0.032 s (2.1×) |
  | Edge of the cardioid | 27.7 → 2.0 s (13.6×) | 0.80 → 0.21 s (3.7×) | 6.9 → 0.64 s (10.8×) | 0.21 → 0.053 s (3.9×) |
  | Seahorse Valley | 1.76 → 1.77 s (1.0×) | 0.13 → 0.13 s | 0.73 → 0.73 s | 0.040 → 0.039 s |

  A better algorithm beats more cores: 1 thread with the test is faster than 8 threads without it. With 48 threads the
  gain is smaller, because the remaining work is unevenly distributed and the run time is down to hundredths of a second.
- **GPU** (NVIDIA GeForce RTX 3090, driver 610.88): Direct3D 11 compute shader `native/gpu/mandel.hlsl`, compiled by
  Windows at run time (no CUDA toolkit needed); the C++ host program `native/gpu/mandel_gpu.cpp` computes in strips of
  128 rows (Windows aborts GPU jobs > 2 s), colours on the CPU (OpenMP) and delivers tiles like the others.
  Pure computation time without image transfer, median of 3:

  | Setting | Cardioid | Rust SIMD (48 thr.) | GPU double | GPU float |
  |---|---|---|---|---|
  | 1600 × 2560, 5000 it. | no | 0.067 s | 0.173 s (0.4×) | 0.028 s (2.4×) |
  | 1600 × 2560, 5000 it. | yes | 0.031 s | 0.101 s (0.3×) | 0.027 s (1.2×) |
  | 1600 × 2560, 20,000 it. | no | 0.238 s | 0.575 s (0.4×) | 0.046 s (5.2×) |
  | 1600 × 2560, 20,000 it. | yes | 0.109 s | 0.311 s (0.4×) | 0.039 s (2.8×) |
  | 3840 × 6144, 5000 it. | no | 0.288 s | 0.846 s (0.3×) | 0.109 s (2.6×) |
  | 3840 × 6144, 5000 it. | yes | 0.078 s | 0.388 s (0.2×) | 0.087 s (0.9×) |

  - GPU start-up (opening the device, compiling the shader) ≈ 0.45 s, reported separately. The pure GPU computation time
    in float is 0.01–0.03 s; the rest is copying back and colouring on the CPU. Through the server with live tiles ≈ 0.08 s.
  - **On this graphics card, double is slower than the CPU:** the RTX 3090 computes double at only 1/64 of its float
    speed. Compute cards (e.g. NVIDIA A100/H100) have much more double performance.
  - **Accuracy:** in the full view, float differs in 0.3 % of the pixels, in deep zooms in 4–17 % (visibly different
    structures; at strong zoom levels float is no longer sufficient at all). Double also differs in 0.01–0.5 % of the
    pixels. FMA is not the explanation (C with FMA differs in other ways); the graphics driver compiles the shader in its
    own way.
  - The GPU load does not appear in the CPU heatmap.
- **Worker memory usage** (found during package testing: "The paging file is too small" with many simultaneous workers):
  numpy ships with OpenBLAS, which allocates buffers for all 48 CPU threads in every process – ≈ 800 MB per Mandelbrot
  worker, 37.6 GB for 48 workers; in addition, every worker loaded the entire web server. Solution:
  `OPENBLAS_NUM_THREADS=1` etc. in `server.py` before numpy is first loaded, and `server.py` as a tiny launcher
  (application in `app.py`, worker helpers in `worker_util.py`/`lastgen.py`). Result: 62 MB per Mandelbrot worker
  (2.9 GB for 48), Pi worker 19 MB, web server 88 instead of 834 MB, pool start-up 5.7 instead of 10.2 s; computation
  speed unchanged.
- **Pi scaling test** (2026-11-08, 10 million digits, gmpy2 2.3, median of 3; times in s):

  | Workers | 1 | 2 | 4 | 8 | 12 | 16 | 24 | 32 | 48 |
  |---|---|---|---|---|---|---|---|---|---|
  | Total | 8.33 | 6.41 | 5.31 | 4.84 | 4.62 | 4.57 | 3.95 | 3.97 | 4.72 |
  | Speedup | 1.0 | 1.3 | 1.6 | 1.7 | 1.8 | 1.8 | 2.1 | 2.1 | 1.8 |
  | Series (parallel) | 5.56 | 3.10 | 1.47 | 0.73 | 0.46 | 0.36 | 0.18 | 0.16 | 0.17 |
  | Merging | – | 0.55 | 1.12 | 1.42 | 1.46 | 1.52 | 1.38 | 1.38 | 1.80 |
  | Square root + division | 1.57 | 1.59 | 1.56 | 1.52 | 1.55 | 1.56 | 1.36 | 1.40 | 1.58 |
  | Decimal conversion | 1.20 | 1.16 | 1.16 | 1.16 | 1.15 | 1.14 | 1.03 | 1.03 | 1.16 |

  - **Amdahl's law** in its purest form: the parallel series shrinks from 5.6 s to 0.2 s (≈ 33×), but square root,
    division and decimal conversion (together ≈ 2.7 s) always run on a single core, and so do the top-level
    multiplications during merging. At most ≈ 2.1×; with 48 workers it gets slower again (more merging and more data
    transfer between the processes).
  - Variants measured (10 million digits, 48 workers): 1 block per worker is better than 2 or 4 (4.6 s instead of
    5.2–5.4 s); distributing the merging across the workers is better than doing it all in the main process (4.6 s
    instead of 5.8 s).
  - 1 million digits: 0.46 s with 1 worker, 0.28 s with 8 workers. All runs match mpmath.
  - The serial steps (last multiplication, square root, division, conversion) run in a worker process, not in the
    server: GMP does not release the GIL, so the server would otherwise be unresponsive for seconds. Measured at
    50 million digits (32.8 s, of which 17 s were a single serial step): the server responded within at most 0.22 s
    throughout.
  - A C# counterpart was deliberately not built: `System.Numerics.BigInteger` lacks algorithms for huge numbers as fast
    as GMP's and would be many times slower at millions of digits. The comparison would then measure the library, not
    the parallelisation.
- Load processes and Mandelbrot workers run at "below normal" priority, so that the browser and web server remain
  usable even at 100 % load. Workers exit by themselves if the server goes away.
- Fixed bug (2026-11-08): clicking "Start" in the load generator could permanently stop the measurement clock (live view
  frozen), because the status was incomplete while the processes were starting.
- Windows often packs a few workers closely together: in three tests, 4 Mandelbrot workers ran on threads 24–27(28),
  i.e. on 2 cores using both SMT threads each, although 22 cores were idle.
- **Worker placement** ("Placement" setting, CPU affinity per worker). Measured on 2026-11-08, 1600 × 2560 (rotated),
  5000 iterations, numba, 128 px tiles, median of 3 runs:

  | Workers | 1 | 2 | 4 | 8 | 12 | 16 | 24 | 32 | 48 |
  |---|---|---|---|---|---|---|---|---|---|
  | Windows decides (s) | 6.18 | 3.27 | 1.72 | 0.93 | 0.72 | 0.56 | 0.51 | 0.40 | 0.34 |
  | 1 thread per core first (s) | 6.23 | 3.14 | 1.64 | 0.90 | 0.66 | 0.55 | 0.49 | 0.39 | 0.34 |
  | compact (s) | 6.24 | 3.39 | 1.76 | 0.96 | 0.71 | 0.58 | 0.49 | 0.39 | 0.35 |
  | Speedup "1 thread per core first" | 1.0 | 2.0 | 3.8 | 7.0 | 9.5 | 11.3 | 12.8 | 16.0 | 18.2 |

  - Placement makes little difference: "1 thread per core first" is 3–10 % faster than "Windows decides" with 2–16
    workers; with 48 workers they are all the same.
  - **SMT hardly slows Mandelbrot down**: 2 workers on both threads of *one* core are only 8 % slower than on 2 cores;
    24 workers on 12 cores only ≈ 5 % slower than on 24 cores. Reason: each computation step waits for the previous
    one, a single thread does not saturate the execution units, and the second thread fills the gaps.
  - **The main brake with many workers is the short run time** (0.3–0.5 s): idle time at the end (the last tiles) and
    overhead. Cross-check with 4× the work (20,000 iterations, "1 thread per core first"): 1 worker 24.4 s, 24 workers
    1.58 s (15.4×), 48 workers 0.98 s (**24.8×**). The CPU time of all workers stays at ≈ 24 s; what is lost is pure
    waiting time.
- **Demanding tiles first + C# comparison** (2026-11-08, 1600 × 2560 rotated, 5000 iterations, 128 px tiles, placement
  "Windows", median of 3 runs; time in s, speedup in brackets):

  | Workers | numba row by row | numba demanding first | C# row by row | C# demanding first |
  |---|---|---|---|---|
  | 1 | 6.18 (1.0×) | 6.22 (1.0×) | 6.13 (1.0×) | 6.13 (1.0×) |
  | 8 | 0.93 (6.6×) | 0.94 (6.6×) | 0.86 (7.1×) | 0.85 (7.2×) |
  | 16 | 0.56 (11.0×) | 0.54 (11.5×) | 0.52 (11.9×) | 0.47 (13.1×) |
  | 24 | 0.51 (12.1×) | 0.40 (15.5×) | 0.43 (14.2×) | 0.36 (17.1×) |
  | 32 | 0.40 (15.5×) | 0.36 (17.2×) | 0.33 (18.9×) | 0.28 (21.6×) |
  | 48 | 0.34 (18.4×) | 0.29 (21.8×) | 0.27 (22.8×) | **0.24 (25.1×)** |
  | Start | 1.7–5.8 s (pool) | 1.7–5.8 s | 0.14 s (.NET) | 0.14 s |

  - **"Demanding first"** (cost estimate with 8×8 samples per tile, ≈ 15 ms, included in the time) cuts the run time by
    10–22 % with 24–48 workers, and does nothing with few workers (there is hardly any idle time at the end there).
  - **With 1 thread, C# is just as fast as numba** (6.13 vs. 6.18 s): both generate almost the same machine code. C#'s
    advantage lies in everything around it: real threads in one process, start-up in 0.14 s instead of several seconds,
    no data transfer between processes. This makes C# about 20 % faster at 48 threads.
  - C# produces a **bit-identical image** to numba (cross-check: 0 of 256,000 pixels different, same number of points
    in the set).
- **C# + SIMD (AVX2)** and binary tile transfer (2026-11-08, same parameters, median of 3; time in s, speedup):

  | Workers | numba demanding first | C# row by row | C# demanding first | C# SIMD row by row | C# SIMD demanding first |
  |---|---|---|---|---|---|
  | 1 | 6.22 (1.0×) | 6.09 (1.0×) | 6.12 (1.0×) | 1.65 (1.0×) | 1.66 (1.0×) |
  | 8 | 0.94 (6.6×) | 0.83 (7.3×) | 0.80 (7.7×) | 0.23 (7.3×) | 0.23 (7.2×) |
  | 24 | 0.40 (15.5×) | 0.40 (15.4×) | 0.36 (17.2×) | 0.11 (15.0×) | 0.11 (15.3×) |
  | 48 | 0.29 (21.8×) | 0.23 (26.9×) | 0.23 (26.2×) | **0.070 (23.6×)** | 0.077 (21.6×) |

  - SIMD: 4 pixels per thread with `Vector256<double>` (AVX2; the 3960X does not have AVX-512). No FMA, hence a
    **bit-identical image** (verified, including image widths not divisible by 4). With 1 thread **3.7× faster**.
  - Overall result at 48 threads: **C# SIMD 0.070 s versus 0.29 s with numba (≈ 4×)** and 6.2 s with a single Python
    process (≈ 89×).
  - SIMD scales slightly worse in relative terms (23.6× instead of 26.9×): the run time is so short that overhead
    matters, and SMT helps less (measured: 2 SIMD threads on 1 core 11 % slower than on 2 cores, scalar only 5 %).
    Without tile transfer and with 20,000 iterations, SIMD also scales to ≈ 27×.
  - "Demanding first" no longer pays off with SIMD: the estimate (≈ 13 ms) takes too long for a total time of 70 ms.
  - Tile transfer from C# to the server was initially base64 JSON. That noticeably slowed C# down at short run times
    (0.116 s instead of 0.070 s with SIMD). It is now binary: a short header plus raw RGB bytes.
  - Chart: toggle "Speedup" / "Run time (s, logarithmic)" (direct link: `http://127.0.0.1:8000/#zeit`).
  - Further ideas: smaller tiles only at the end; let the numba kernel compute several pixels at once as well.
- The website explains the heatmap, worker colouring and scaling chart in collapsible sections ("What am I seeing here?").
- Very small tiles (64 px and less) cause noticeable overhead in the main process; 128 px is a good default.
- All explanations on the page are collapsed on load and can be expanded when needed.

## License

Core Monitor is licensed under the [MIT License](LICENSE). The "Full" package bundles third-party software
(Python, numpy, numba, gmpy2/GMP, FastAPI, the .NET runtime, Microsoft C/C++ runtime libraries, …) under their own
licenses – see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); the full license texts are in the package's
`licenses\` folder.

## Development

This project – code, documentation and reports – was developed with **Claude (Anthropic) using Claude Code**,
in close collaboration with and directed by the repository owner, as a feasibility study on parallel computing.

## Glossary

Alphabetical, with a link to further reading.

- **0.0.0.0:** Server setting "reachable on all network adapters". The monitor deliberately does not use it, only 127.0.0.1.
- **127.0.0.1 (localhost):** Address of your own PC. The server listens only there and is therefore not reachable from other computers. <https://en.wikipedia.org/wiki/Localhost>
- **Amdahl's law:** The part of a program that cannot run in parallel limits the possible speedup, no matter how many cores are used (see Pi). <https://en.wikipedia.org/wiki/Amdahl%27s_law>
- **API:** Interface through which the page (or a script) controls the server, e.g. /api/mandel/start. <https://en.wikipedia.org/wiki/API>
- **Assembler (MASM):** Processor instructions in readable form, written by hand. MASM is the Microsoft Macro Assembler. <https://learn.microsoft.com/en-us/cpp/assembler/masm/microsoft-macro-assembler-reference>
- **AVX-512:** Successor of AVX2 with 512-bit registers (8 doubles at once). The Threadripper 3960X does not have it; some newer processors do. <https://en.wikipedia.org/wiki/AVX-512>
- **AVX2:** SIMD instruction set of current x86 processors; 256-bit registers hold 4 floating-point numbers (double), i.e. 4 pixels per instruction. <https://en.wikipedia.org/wiki/Advanced_Vector_Extensions>
- **base64:** Method to send binary data (here image tiles) as plain text; about one third larger than the original. <https://en.wikipedia.org/wiki/Base64>
- **Binary splitting:** Technique that combines the series terms pairwise into large fractions; the parts can be computed in parallel, the final division cannot. <https://en.wikipedia.org/wiki/Binary_splitting>
- **Bit-identical:** Every byte of the result is identical – here: 0 pixels difference between the computation methods.
- **C / C++:** Classic languages close to the hardware. Compiled here with the Microsoft compiler (MSVC) from Visual Studio. <https://learn.microsoft.com/en-us/cpp/>
- **C# / .NET:** Programming language and runtime from Microsoft; real threads, compiled to machine code at run time. <https://learn.microsoft.com/en-us/dotnet/csharp/>
- **Cache (L1/L2/L3):** Fast buffer memory inside the processor. L1/L2 belong to one core, L3 is shared by the cores of a CCX. <https://en.wikipedia.org/wiki/CPU_cache>
- **Cardioid and period-2 bulb:** The heart-shaped main area and the large disc to its left certainly belong to the Mandelbrot set. A short formula detects these points without iterating them up to the maximum. <https://en.wikipedia.org/wiki/Mandelbrot_set#Main_cardioid_and_period_bulbs>
- **CCX (Core Complex):** On AMD Zen processors a group of cores sharing one L3 cache; the 3960X has 8 CCXs with 3 cores each. Called "L3 group" in the monitor. <https://en.wikipedia.org/wiki/Zen_2>
- **Chudnovsky formula:** Very fast converging series for Pi: about 14 new digits per term. <https://en.wikipedia.org/wiki/Chudnovsky_algorithm>
- **Compiler switches /O2, /arch:AVX2, /fp:precise, /MT:** Optimise, allow AVX2 instructions, compute exactly as written (no FMA), link the runtime library statically (no extra DLLs needed). <https://learn.microsoft.com/en-us/cpp/build/reference/compiler-options-listed-by-category>
- **Core (processor core):** Independent execution unit inside the processor. The Threadripper 3960X has 24 cores. <https://en.wikipedia.org/wiki/Multi-core_processor>
- **CPU affinity (placement):** Defines on which threads a process may run. The monitor uses it to compare "1 thread per core first" with "compact". <https://en.wikipedia.org/wiki/Processor_affinity>
- **"Demanding tiles first":** Order in which a rough up-front estimate puts the most compute-intensive tiles first, so that no long tile is left running alone at the end.
- **Digital signature (code signing):** Electronic signature of a publisher on an .exe; signed, widely used programs trigger warnings less often. The programs of Core Monitor are not signed. <https://en.wikipedia.org/wiki/Code_signing>
- **Direct3D 11 compute shader / HLSL:** Program that runs on the graphics card; written in HLSL, launched via Direct3D 11 (works with any current graphics card on Windows). <https://learn.microsoft.com/en-us/windows/win32/direct3d11/direct3d-11-advanced-stages-compute-shader>
- **DNS rebinding:** Attack in which a foreign website points its name to 127.0.0.1 to control local services from the browser. The monitor therefore checks Host and origin of every request and rejects anything foreign. <https://en.wikipedia.org/wiki/DNS_rebinding>
- **double / float:** Floating-point numbers with double (≈ 16 digits) or single precision (≈ 7 digits) according to IEEE 754. Gaming graphics cards are much faster with float. <https://en.wikipedia.org/wiki/IEEE_754>
- **DXGI:** Windows interface the monitor uses to detect the installed graphics cards and their memory. <https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/dx-graphics-dxgi>
- **Embedded Python:** Official, lean Python distribution that can be shipped in a folder without installation. Included in the "Full" package. <https://docs.python.org/3/using/windows.html#the-embeddable-package>
- **False positive:** Antivirus software considers a harmless program dangerous because it behaves similarly to malware (e.g. unsigned .exe, full load on all cores). See "Note on antivirus software". <https://en.wikipedia.org/wiki/False_positives_and_false_negatives>
- **FastAPI / uvicorn:** Python building blocks of the web server: FastAPI describes the interfaces, uvicorn serves them. <https://fastapi.tiangolo.com/>
- **FMA (fused multiply-add):** Multiplication and addition in one step with a single rounding. Faster, but changes the last digit – and thus individual pixels. <https://en.wikipedia.org/wiki/Multiply%E2%80%93accumulate_operation>
- **GIL (Global Interpreter Lock):** Lock in standard Python: only one thread executes Python code at a time. That is why the monitor uses processes instead of threads for Python. <https://docs.python.org/3/glossary.html#term-global-interpreter-lock>
- **gmpy2 / GMP:** Library for very large numbers with any number of digits; the basis of the Pi computation. <https://gmpy2.readthedocs.io/>
- **GPU (graphics card):** Processor with thousands of simple execution units; ideal when a huge number of identical calculations is needed (e.g. one per pixel). <https://en.wikipedia.org/wiki/Graphics_processing_unit>
- **Heat map:** Coloured tile view: one field per thread, colour = current load. <https://en.wikipedia.org/wiki/Heat_map>
- **Intrinsics:** Functions in C/C++/Rust that map directly to one processor instruction (e.g. AVX2); SIMD without assembler. <https://learn.microsoft.com/en-us/cpp/intrinsics/compiler-intrinsics>
- **Iterations (max_iter):** The maximum number of times z → z² + c is repeated. More iterations = finer edges, but more computing time (especially in the black interior).
- **JIT (just-in-time compilation):** Code is compiled to machine code only while the program runs; the first call therefore takes longer. <https://en.wikipedia.org/wiki/Just-in-time_compilation>
- **JSON / CSV:** Text formats for measurements: JSON for structured data (one file per measurement), CSV as a table that e.g. Excel can open. <https://en.wikipedia.org/wiki/JSON>
- **Load balancing (dynamic):** Whoever finishes a tile fetches the next one. No core sits idle even though tiles take different amounts of time. <https://en.wikipedia.org/wiki/Load_balancing_(computing)>
- **Mandelbrot set:** Famous fractal: for every pixel z → z² + c is repeated until the value "escapes" or the maximum count is reached. Every point is independent – ideal for parallelisation. <https://en.wikipedia.org/wiki/Mandelbrot_set>
- **Median:** Middle value of a sorted series of measurements; less sensitive to outliers than the average. Used when several runs are made. <https://en.wikipedia.org/wiki/Median>
- **mpmath:** Python library for arbitrary-precision arithmetic; serves as an independent cross-check of the Pi digits. <https://mpmath.org/>
- **NUMA:** Non-Uniform Memory Access: on large systems memory is reached at different speeds depending on the core. The 3960X has one NUMA node. <https://en.wikipedia.org/wiki/Non-uniform_memory_access>
- **numba:** Compiles selected Python functions to machine code on first call (JIT), making them about as fast as C. <https://numba.pydata.org/>
- **numpy:** Python library for computing with whole arrays of numbers. Fast for simple array operations, but not ideal for Mandelbrot. <https://numpy.org/>
- **OpenBLAS:** Math library inside numpy that starts its own threads. Limited to 1 thread per process in the monitor, otherwise every worker needs ~800 MB. <https://www.openblas.net/>
- **pip:** Python's package manager; installs extensions such as numba or FastAPI. <https://pip.pypa.io/>
- **Process:** A running program with its own memory. Processes run independently but can exchange data only indirectly. <https://en.wikipedia.org/wiki/Process_(computing)>
- **Processor group:** Windows combines at most 64 threads into one group. Processors with more threads have several groups; a process normally runs in only one. <https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups>
- **ProcessPoolExecutor:** Python building block that manages a pool of worker processes and distributes tasks to them. <https://docs.python.org/3/library/concurrent.futures.html>
- **psutil:** Python library that queries load, memory and processes; supplies the values for the core display. <https://psutil.readthedocs.io/>
- **Python:** Widely used scripting language; used here for the web server, control logic and two computation methods. <https://www.python.org/>
- **Quarantine:** Isolated area of the antivirus software for suspicious files; they can be restored from there. <https://en.wikipedia.org/wiki/Antivirus_software>
- **Rust:** Modern systems language with C-like speed; its compiler prevents typical mistakes when working with threads. <https://www.rust-lang.org/>
- **rustup / cargo:** rustup installs and updates Rust; cargo builds Rust programs and downloads the libraries they need. <https://rustup.rs/>
- **Scaling, speedup, efficiency:** Speedup = time with 1 worker ÷ time with n workers. Efficiency = speedup ÷ n (100 % = perfect). <https://en.wikipedia.org/wiki/Speedup>
- **Scheduler:** Part of Windows that decides which thread runs on which core and when (placement "Windows decides"). <https://en.wikipedia.org/wiki/Scheduling_(computing)>
- **Seahorse valley:** Well-known region of the Mandelbrot set between the main cardioid and the period-2 bulb; very finely branched and therefore compute-intensive. <https://en.wikipedia.org/wiki/Mandelbrot_set>
- **Self-contained single file:** .NET program that carries the runtime inside a single .exe; runs without an installed .NET. <https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview>
- **SIMD:** Single Instruction, Multiple Data: one instruction processes several numbers at once. <https://en.wikipedia.org/wiki/Single_instruction,_multiple_data>
- **SmartScreen:** Windows protection that warns about unknown, unsigned programs ("Windows protected your PC"). <https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/>
- **SMT (simultaneous multithreading, Intel: "Hyper-Threading"):** One core runs two instruction streams at once and fills gaps in its execution units. Usually gains 0–30 %, not 100 %. <https://en.wikipedia.org/wiki/Simultaneous_multithreading>
- **Thread (hardware thread, logical processor):** What Windows counts as a "CPU". With SMT every core offers 2 threads, i.e. 48 on the 3960X. <https://en.wikipedia.org/wiki/Thread_(computing)>
- **Thread (software):** Execution path inside a process; all threads share the memory and start much faster than processes. <https://en.wikipedia.org/wiki/Thread_(computing)>
- **Tile:** Rectangular part of the image (default 128 × 128 pixels), the smallest unit of work for a worker.
- **vcomp140.dll / OpenMP:** OpenMP is a standard that lets C/C++ programs distribute loops across threads; vcomp140.dll is Microsoft's runtime library for it and is included in the package. <https://learn.microsoft.com/en-us/cpp/parallel/openmp/openmp-in-visual-cpp>
- **Vector256:** .NET data type for a 256-bit register (4 doubles); this is how C# uses AVX2. <https://learn.microsoft.com/en-us/dotnet/api/system.runtime.intrinsics.vector256>
- **VirusTotal:** Free service that checks a file with about 70 antivirus engines at once. <https://www.virustotal.com/>
- **Visual Studio Build Tools:** Microsoft's compilers for C, C++ and assembler without the full development environment; free of charge. <https://visualstudio.microsoft.com/downloads/>
- **WebSocket:** Permanent connection between browser and server; the load values arrive through it every second without reloading. <https://en.wikipedia.org/wiki/WebSocket>
- **winget:** Windows package manager; installs programs such as Python, .NET or Rust from the command line. <https://learn.microsoft.com/en-us/windows/package-manager/winget/>
- **Worker:** A process or thread that works through tiles. The number of workers is set in the monitor (1–48).
- **x64:** 64-bit instruction set of today's Intel and AMD processors (also called x86-64 or AMD64). <https://en.wikipedia.org/wiki/X86-64>
