#!/bin/sh
# Start Core Monitor (Kern-Monitor) on Linux (Debian / Ubuntu).
#  - Package "Full": bundled Python and finished programs are included -> nothing to install or build.
#  - Package "Lite" / source folder: installed Python 3.10+; packages go into a private environment (.venv) next to
#    this file, comparison programs are built as far as the tools are available (missing tools -> these
#    computation methods are only greyed out in the list). See INSTALLATION_LINUX.txt.
cd "$(dirname "$0")" || exit 1
: "${PORT:=8000}"
export PORT

if [ -x python/bin/python3 ]; then
    echo 'Package "Full": using bundled Python and finished programs.'
    PY=python/bin/python3
else
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Python not found. Please install it:  sudo apt install python3 python3-venv  (see INSTALLATION_LINUX.txt)"
        echo "(Python wurde nicht gefunden. Bitte installieren:  sudo apt install python3 python3-venv)"
        exit 1
    fi
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
        echo "Python is too old. Version 3.10 or newer is required (see INSTALLATION_LINUX.txt)."
        echo "(Python ist zu alt. Benoetigt wird Version 3.10 oder neuer.)"
        exit 1
    fi
    # private environment: changes nothing in the system's Python
    if [ ! -x .venv/bin/python ]; then
        echo "Creating the Python environment .venv (once) ..."
        if ! python3 -m venv .venv; then
            rm -rf .venv
            echo "Could not create the Python environment. Please install:  sudo apt install python3-venv"
            echo "(Python-Umgebung konnte nicht angelegt werden. Bitte installieren:  sudo apt install python3-venv)"
            exit 1
        fi
    fi
    PY=.venv/bin/python
    # keep pip itself current (quietly) and suppress pip's "new release available" notice
    export PIP_DISABLE_PIP_VERSION_CHECK=1
    "$PY" -m pip install -q --upgrade pip
    if ! "$PY" -m pip install -q -r requirements.txt; then
        echo "The Python packages could not be installed (internet connection?). See INSTALLATION_LINUX.txt."
        echo "(Die Python-Pakete konnten nicht installiert werden - Internetverbindung?)"
        exit 1
    fi
    # numba is optional (faster computation method); without numba numpy is used
    "$PY" -m pip install -q numba || echo "numba not installed - Mandelbrot runs with numpy (numba nicht installiert)"
    # comparison programs only if the tools are present (see INSTALLATION_LINUX.txt)
    if command -v dotnet >/dev/null 2>&1; then
        dotnet build csharp/MandelBench -c Release -o csharp/bin --nologo -v q >/dev/null || echo "C# build failed (C#-Build fehlgeschlagen)"
    fi
    CARGO=$(command -v cargo || echo "$HOME/.cargo/bin/cargo")
    if [ -x "$CARGO" ]; then
        (cd rust/mandelbench && "$CARGO" build --release --quiet) || echo "Rust build failed (Rust-Build fehlgeschlagen)"
    fi
    sh native/build.sh
fi

# No fixed browser call: the server opens a tab only if no page is open.
export OPEN_BROWSER=1
exec "$PY" server.py
