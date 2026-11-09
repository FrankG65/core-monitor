# Third-party notices

Core Monitor itself is licensed under the MIT License (see [LICENSE](LICENSE)).

The **source code** in this repository and the **"Lite"** package contain no third-party code; the components
below are installed on the target PC by `start.bat` / `start.sh` (pip) or used as build tools.

The **"Full"** package (`CoreMonitor_Full_<date>.zip`) additionally **bundles** the following third-party
software so that it runs without installation. Each component remains under its own license.
**The complete license texts are included in the package in the folder `licenses\`** (collected by
`tools/collect_licenses.py` during the export) and, for the Python packages, also in
`python\Lib\site-packages\<name>.dist-info\`.

## Python runtime

| Component | Version | License | Source |
|---|---|---|---|
| Python (embeddable package, incl. OpenSSL, libffi, SQLite, bzip2, xz, zlib) | 3.11.9 | PSF License 2.0 (bundled parts: Apache-2.0, MIT, public domain, …) – see `python\LICENSE.txt` | https://www.python.org/ |

## Python packages (in `python\Lib\site-packages`)

| Package | Version | License | Source |
|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | https://github.com/fastapi/annotated-doc |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.16.0 | MIT | https://github.com/agronholm/anyio |
| click | 8.5.1 | BSD-3-Clause | https://github.com/pallets/click |
| fastapi | 0.162.2 | MIT | https://github.com/fastapi/fastapi |
| gmpy2 | 2.3.2 | LGPL-3.0-or-later (see below) | https://github.com/gmpy2/gmpy2 |
| h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 |
| httptools | 0.9.0 | MIT (incl. llhttp, http-parser: MIT) | https://github.com/MagicStack/httptools |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| llvmlite | 0.50.0 | BSD-2-Clause (bundles LLVM: Apache-2.0 with LLVM exception; see `LICENSE.thirdparty`) | https://github.com/numba/llvmlite |
| mpmath | 1.4.1 | BSD-3-Clause | https://mpmath.org/ |
| numba | 0.68.1 | BSD-2-Clause (third-party parts: `LICENSES.third-party`) | https://numba.pydata.org |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (bundles OpenBLAS: BSD-3-Clause) | https://numpy.org |
| opentelemetry-api | 1.45.2 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python |
| psutil | 7.2.2 | BSD-3-Clause | https://github.com/giampaolo/psutil |
| pydantic | 2.14.3 | MIT | https://github.com/pydantic/pydantic |
| pydantic_core | 2.50.4 | MIT | https://github.com/pydantic/pydantic |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| PyYAML | 6.0.3 | MIT | https://pyyaml.org/ |
| starlette | 1.10.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| typing-inspection | 0.4.5 | MIT | https://github.com/pydantic/typing-inspection |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| watchfiles | 1.3.0 | MIT | https://github.com/samuelcolvin/watchfiles |
| websockets | 17.4 | BSD-3-Clause | https://github.com/python-websockets/websockets |

Versions are those of the 1.0 release; a later export lists its exact versions in `licenses\python-packages\`.

### LGPL components (gmpy2, GMP, MPFR, MPC)

gmpy2 and the libraries it uses are licensed under the GNU Lesser General Public License (LGPL-3.0-or-later;
GMP is dual-licensed LGPL-3.0-or-later / GPL-2.0-or-later). They are shipped **unmodified, as separate dynamic
libraries** in `python\Lib\site-packages\gmpy2.libs\` (`libgmp-10.dll`, `libmpfr-6.dll`, `libmpc-3.dll`, together with
the MinGW runtime `libgcc_s_seh-1.dll` – GPL-3.0 with GCC Runtime Library Exception – and `libwinpthread-1.dll` – MIT/BSD)
and in `python\Lib\site-packages\gmpy2\`. You may replace them with other (e.g. self-built) compatible versions.
The license texts are in `licenses\python-packages\gmpy2-*\`. Source code: https://github.com/gmpy2/gmpy2 ,
https://gmplib.org/ , https://www.mpfr.org/ , https://www.multiprecision.org/mpc/ .

## Programs compiled from this repository

| Component | Contains | License | Source |
|---|---|---|---|
| `csharp\bin\MandelBench.exe` (self-contained single file) | .NET runtime | MIT (third-party parts: `licenses\dotnet\ThirdPartyNotices.txt`) | https://github.com/dotnet/runtime |
| `rust\…\mandelbench.exe` | Rust standard library (statically linked) | MIT OR Apache-2.0 | https://www.rust-lang.org/ |
| `native\bin\*.exe` | Microsoft C/C++ runtime (statically linked, `/MT`) | Visual Studio license terms ("Distributable Code") | https://visualstudio.microsoft.com/license-terms/ |
| `native\bin\vcomp140.dll` | Microsoft OpenMP runtime | Visual Studio license terms ("Distributable Code") | https://visualstudio.microsoft.com/license-terms/ |
| `python\vcruntime140*.dll`, `…\msvcp140-*.dll` | Microsoft C/C++ runtime (shipped by Python / numpy / llvmlite) | Visual Studio license terms ("Distributable Code") | https://visualstudio.microsoft.com/license-terms/ |

The Microsoft runtime libraries are redistributed unmodified as part of this application, as permitted for
"Distributable Code" by the Microsoft Visual Studio license terms.

## Linux "Full" package (`CoreMonitor_Full_Linux_<date>.tar.gz`)

The Linux package bundles the same Python packages as listed above (Linux builds of the same versions, in
`python/lib/python3.11/site-packages/`), plus the following differences. The complete license texts are again in the
folder `licenses/` of the package.

| Component | License | Source |
|---|---|---|
| Python 3.11 from python-build-standalone (incl. OpenSSL, libffi, SQLite, bzip2, xz, zlib and further libraries) | PSF License 2.0 (bundled parts under their own licenses, see `python/lib/python3.11/LICENSE.txt`); build scripts: MPL-2.0 | https://github.com/astral-sh/python-build-standalone |
| uvloop (Linux only; bundles libuv) | MIT OR Apache-2.0 (libuv: MIT) | https://github.com/MagicStack/uvloop |
| pip, setuptools | MIT | https://pip.pypa.io/ , https://github.com/pypa/setuptools |
| numpy: `numpy.libs/` (OpenBLAS; libgfortran and libquadmath from GCC) | OpenBLAS: BSD-3-Clause; libgfortran / libquadmath: GPL-3.0 with GCC Runtime Library Exception / LGPL-2.1 | https://numpy.org |
| gmpy2: `gmpy2.libs/` (libgmp, libmpfr, libmpc as separate shared libraries) | LGPL-3.0-or-later (as above; replaceable) | https://github.com/gmpy2/gmpy2 |
| `csharp/bin/MandelBench` (self-contained single file) | .NET runtime: MIT (third-party parts: `licenses/dotnet/ThirdPartyNotices.txt`) | https://github.com/dotnet/runtime |
| `rust/…/mandelbench` | Rust standard library: MIT OR Apache-2.0 | https://www.rust-lang.org/ |
| `native/bin/mandel_*` | GCC runtime (libgcc, libstdc++), statically linked: GPL-3.0 with GCC Runtime Library Exception (no obligations for the compiled program) | https://gcc.gnu.org/ |
| `native/bin/mandel_gpu` | compiled against the Khronos OpenCL headers (Apache-2.0); uses the system's OpenCL loader `libOpenCL.so.1` (not bundled) | https://github.com/KhronosGroup/OpenCL-Headers |
