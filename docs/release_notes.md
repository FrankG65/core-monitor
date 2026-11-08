## Core Monitor

A local web app for Windows that monitors all CPU cores live and shows how well different
computation methods use them in parallel – a feasibility study.

**Download:** `CoreMonitor_Full_<date>.zip` below – runs on any Windows 10/11 PC (64 bit)
**without installation, without internet and without admin rights**. Unpack it, double-click
`start.bat`, and the page opens at http://127.0.0.1:8000 (reachable only from this PC).

### What's inside
- Live load per core and thread, grouped by L3 cache (CCX), with a heat map of the last 2 minutes
- Mandelbrot set with **13 computation methods** – Python (numba, numpy), C#, Rust, C, C++ and
  hand-written assembler, each with and without AVX2 SIMD, plus a Direct3D 11 GPU shader (double and float).
  All CPU methods produce bit-identical images.
- Scaling test with 1 … all workers, placement / SMT experiments, "demanding tiles first", cardioid check
- Pi with up to 100 million digits (Chudnovsky, binary splitting) – Amdahl's law in practice
- Automatic hardware detection, English / German user interface (switch DE | EN)
- Project report as PDF (English and German) with all measurements and a glossary

### Requirements
- Windows 10 or 11, 64 bit
- GPU methods: graphics card with Direct3D 11 (otherwise greyed out); SIMD and assembler: CPU with AVX2

### Note on antivirus software
The included programs are not digitally signed. Antivirus software or SmartScreen may raise an
**unfounded** warning or briefly block a program on first start – see "Note on antivirus software" in
INSTALLATION.txt / README.md. All source code is included in the package and in this repository.

### Security
The server listens only on 127.0.0.1 and additionally rejects every request that does not come from its own page on
this PC (checks client, Host and Origin – protection against DNS rebinding and foreign websites). Rejected requests are
logged in `logs\security.log` and shown as a red notice in the page header.

### Verify the download
Each ZIP has a `.sha256` file. In PowerShell: `Get-FileHash CoreMonitor_Full_<date>.zip -Algorithm SHA256` –
the value must match the one in the `.sha256` file.

### License
MIT (see `LICENSE`). The Full package bundles third-party software under its own licenses – see
`THIRD_PARTY_NOTICES.md`; the complete license texts are in the package's `licenses\` folder.

### Development
Developed with Claude (Anthropic) using Claude Code, directed by the repository owner.

The "Lite" variant (source code only, builds on your PC) is simply this repository:
**Code → Download ZIP**, then `start.bat` (needs Python 3.11+).
