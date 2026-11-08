"""Collects the license texts of all bundled third-party components into <package>/licenses/ (used by export.ps1).

    python tools\\collect_licenses.py <package folder>

- Python packages: every license file from python/Lib/site-packages/*.dist-info -> licenses/python-packages/<name>-<version>/
- Python itself: python/LICENSE.txt -> licenses/python/
- .NET runtime (inside csharp/bin/MandelBench.exe): LICENSE.txt and ThirdPartyNotices.txt of the local .NET installation
- Rust standard library (inside mandelbench.exe): COPYRIGHT and the MIT / Apache-2.0 texts of the Rust toolchain
Missing sources are reported but do not stop the export (see THIRD_PARTY_NOTICES.md for links).
"""
from __future__ import annotations

import email
import shutil
import subprocess
import sys
from pathlib import Path

pkg = Path(sys.argv[1])
out = pkg / "licenses"
if out.exists():
    shutil.rmtree(out)
out.mkdir()
count = 0


def copy(src: Path, dst: Path):
    global count
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    count += 1


# Python packages
for d in sorted((pkg / "python" / "Lib" / "site-packages").glob("*.dist-info")):
    m = email.message_from_string((d / "METADATA").read_text(encoding="utf-8", errors="replace"))
    target = out / "python-packages" / f"{m['Name']}-{m['Version']}"
    for f in d.rglob("*"):
        if f.is_file() and any(k in f.name.upper() for k in ("LICEN", "COPYING", "NOTICE")):
            copy(f, target / f.relative_to(d))

# Python itself
if (pkg / "python" / "LICENSE.txt").exists():
    copy(pkg / "python" / "LICENSE.txt", out / "python" / "LICENSE.txt")

# .NET runtime
dotnet = shutil.which("dotnet")
if dotnet:
    root = Path(dotnet).resolve().parent
    for name in ("LICENSE.txt", "ThirdPartyNotices.txt"):
        if (root / name).exists():
            copy(root / name, out / "dotnet" / name)
else:
    print("collect_licenses: .NET not found - license text not copied")

# Rust standard library
rustc = shutil.which("rustc") or str(Path.home() / ".cargo" / "bin" / "rustc.exe")
try:
    sysroot = Path(subprocess.run([rustc, "--print", "sysroot"], capture_output=True, text=True, check=True).stdout.strip())
    doc = sysroot / "share" / "doc" / "rust"
    for f in [doc / "COPYRIGHT.html", doc / "COPYRIGHT-library.html", doc / "licenses" / "MIT.txt", doc / "licenses" / "Apache-2.0.txt"]:
        if f.exists():
            copy(f, out / "rust" / f.name)
except (OSError, subprocess.CalledProcessError):
    print("collect_licenses: Rust toolchain not found - license text not copied")

print(f"collect_licenses: {count} license files in {out}")
