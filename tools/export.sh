#!/bin/sh
# Builds a Linux distribution package of Core Monitor as a .tar.gz in the folder export/ (counterpart to export.ps1).
#   Full : runs on Debian 12+ / Ubuntu 22.04+ (x86-64) without installation and without internet:
#          own Python with all packages, all computation methods precompiled
#          (C, C++, assembler, GPU/OpenCL, Rust, C# as a self-contained program).
#   Lite : source code and instructions only (INSTALLATION.txt); the target PC installs what it needs.
# Own measurements (benchmarks), settings (.claude), logs, .venv and intermediate files are NOT included.
# tar.gz instead of ZIP: keeps the "executable" flag of start.sh and the programs.
set -e
VARIANT=${1:-Full}
case "$VARIANT" in
    Full|Komplett) VARIANT=Full; GERMAN=Komplett ;;
    Lite|Klein) VARIANT=Lite; GERMAN=Klein ;;
    *) echo "Usage: tools/export.sh Full|Lite" >&2; exit 2 ;;
esac
ROOT=$(cd "$(dirname "$0")/.." && pwd)
STAMP=$(date +%Y-%m-%d)
NAME="CoreMonitor_${VARIANT}_Linux_$STAMP"
EXPORT="$ROOT/export"
WORK="$EXPORT/$NAME"
CACHE="$EXPORT/_cache"
# Python for the Full package: python-build-standalone (relocatable Python, also used by uv), checked via SHA-256
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260718/cpython-3.11.15%2B20260718-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PY_SHA256="23ccae6f1ff73e8aa8378436f869da003b8eb7d6c95f2bc706f494115ba1447d"
PY_TGZ="$CACHE/cpython-3.11.15-linux-x86_64.tar.gz"

step() { printf '\n== %s\n' "$1"; }
copy() { mkdir -p "$WORK/$(dirname "$1")"; cp -p "$ROOT/$1" "$WORK/$1"; }

step "Preparing package $NAME"
mkdir -p "$EXPORT" "$CACHE"
rm -rf "$WORK"
mkdir -p "$WORK"

# ---- Source code (both variants; the sources for Windows are included as well) ----
for f in server.py app.py i18n.py security.py mandelbrot.py pi.py hardware.py worker_util.py lastgen.py \
         requirements.txt start.sh start.bat README.md README.de.md LICENSE THIRD_PARTY_NOTICES.md \
         static/index.html static/app.js static/mandel.js static/pi.js static/style.css \
         csharp/MandelBench/Program.cs csharp/MandelBench/MandelBench.csproj \
         rust/mandelbench/Cargo.toml rust/mandelbench/src/main.rs rust/mandelbench/.cargo/config.toml \
         native/mandel_core.h native/platform.h native/build.sh native/build.bat native/c/mandel.c native/cpp/mandel.cpp \
         native/asm/kernel.asm native/asm/kernel_nasm.asm native/gpu/mandel.hlsl native/gpu/mandel_gpu.cpp \
         native/gpu/mandel.cl native/gpu/mandel_opencl.cpp \
         tools/export.sh tools/export.ps1 tools/privacy_check.py tools/glossar.py tools/selftest.py tools/collect_licenses.py \
         tools/INSTALLATION_LINUX_Full.txt tools/INSTALLATION_LINUX_Lite.txt \
         tools/INSTALLATION_LINUX_Komplett.txt tools/INSTALLATION_LINUX_Klein.txt \
         export_full.sh export_lite.sh export_full.bat export_lite.bat; do
    copy "$f"
done
for pdf in Project_Report_Core_Monitor.pdf Projektbericht_Parallelisierung.pdf; do
    [ -f "$ROOT/$pdf" ] && copy "$pdf"
done
cp "$ROOT/tools/INSTALLATION_LINUX_$VARIANT.txt" "$WORK/INSTALLATION.txt"
cp "$ROOT/tools/INSTALLATION_LINUX_$GERMAN.txt" "$WORK/INSTALLATION.de.txt"

if [ "$VARIANT" = Full ]; then
    step "Compiling C, C++, assembler (NASM) and GPU (OpenCL)"
    rm -rf "$ROOT/native/bin"
    sh "$ROOT/native/build.sh"
    for f in mandel_c mandel_cpp mandel_asm mandel_gpu mandel.cl; do copy "native/bin/$f"; done

    step "Compiling Rust"
    CARGO=$(command -v cargo || echo "$HOME/.cargo/bin/cargo")
    (cd "$ROOT/rust/mandelbench" && "$CARGO" build --release --quiet)
    copy rust/mandelbench/target/release/mandelbench

    step "Publishing C# as a self-contained program (runs without a .NET installation)"
    dotnet publish "$ROOT/csharp/MandelBench" -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true \
        -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=none -o "$WORK/csharp/bin" --nologo -v q

    step "Python 3.11 (python-build-standalone) with all packages"
    if [ ! -f "$PY_TGZ" ]; then
        curl -sSLf -o "$PY_TGZ.part" "$PY_URL"
        mv "$PY_TGZ.part" "$PY_TGZ"
    fi
    echo "$PY_SHA256  $PY_TGZ" | sha256sum -c --quiet - || { rm -f "$PY_TGZ"; echo "Python download damaged (SHA-256)"; exit 1; }
    tar xzf "$PY_TGZ" -C "$WORK"          # creates $WORK/python
    # --no-compile: no .pyc files with the path of THIS PC; Python creates them on the target PC itself
    PIP_DISABLE_PIP_VERSION_CHECK=1 "$WORK/python/bin/python3" -m pip install --quiet --no-compile --no-warn-script-location \
        -r "$ROOT/requirements.txt" numba

    step "Collecting the license texts of all bundled components (licenses/)"
    "$WORK/python/bin/python3" "$ROOT/tools/collect_licenses.py" "$WORK"

    step "Adding the Pi reference (mpmath, 1 million digits)"
    [ -f "$ROOT/benchmarks/pi_referenz_mpmath.txt" ] && copy benchmarks/pi_referenz_mpmath.txt
fi

step "Cleaning up (intermediate files)"
find "$WORK" -name __pycache__ -type d -prune -exec rm -rf {} +
if [ -d "$WORK/python/bin" ]; then
    # pip creates launchers containing the path of THIS PC (#!/home/<name>/...) - not needed in the package
    grep -l -F "$WORK" "$WORK"/python/bin/* 2>/dev/null | xargs -r rm -f
fi

step "Privacy check (no information about this PC and its user in the package)"
set -- "$ROOT" "$WORK"
[ -n "$HOME" ] && [ "$HOME" != / ] && [ "$HOME" != /root ] && set -- "$@" "$HOME"
[ -n "$USER" ] && [ "$USER" != root ] && set -- "$@" "/home/$USER/" "$USER@"
HOSTNAME_=$(hostname 2>/dev/null || cat /etc/hostname 2>/dev/null || true)
[ ${#HOSTNAME_} -ge 6 ] && set -- "$@" "$HOSTNAME_"
for ip in $(hostname -I 2>/dev/null); do
    # skip loopback, link-local, IPv6 and the documentation ranges (RFC 5737; they appear in Python's ipaddress.py)
    case "$ip" in 127.*|169.254.*|*:*|192.0.2.*|198.51.100.*|203.0.113.*) ;; *) set -- "$@" "$ip" ;; esac
done
for mac in $(cat /sys/class/net/*/address 2>/dev/null); do
    [ "$mac" != "00:00:00:00:00:00" ] && set -- "$@" "$mac"
done
PYCHECK=$(command -v python3 || echo "$WORK/python/bin/python3")
"$PYCHECK" "$ROOT/tools/privacy_check.py" "$WORK" "$@" ||
    { echo "Privacy check: personal information found - package will NOT be created (see list above)"; exit 1; }

step "Creating the archive"
OUT="$EXPORT/$NAME.tar.gz"
rm -f "$OUT"
tar czf "$OUT" -C "$EXPORT" "$NAME"
(cd "$EXPORT" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256")   # check with: sha256sum -c <file>.sha256
SIZE=$(du -sm "$WORK" | cut -f1)
rm -rf "$WORK"   # only the archive remains; the Python download stays in export/_cache for the next run
printf '\nDone: %s  (archive %s MB, unpacked %s MB)\n' "$OUT" "$(( $(stat -c %s "$OUT") / 1048576 ))" "$SIZE"
echo "SHA-256: $(cut -d' ' -f1 "$OUT.sha256")  ($NAME.tar.gz.sha256)"
