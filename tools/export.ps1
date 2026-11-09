# Builds a distribution package of Core Monitor as a ZIP in the folder export\.
#   -Variante Full : runs on any Windows 10/11 PC (64 bit) without installation and without internet:
#                    embedded Python with all packages, all computation methods precompiled
#                    (C, C++, assembler, GPU shaders, Rust, C# as a self-contained .exe).
#   -Variante Lite : source code and instructions only (INSTALLATION.txt); the target PC installs what it needs.
#   (Linux packages: tools/export.sh, see export_full.sh / export_lite.sh.)
#   (The German names Komplett / Klein are accepted as aliases.)
# Own measurements (benchmarks), settings (.claude), logs and intermediate files are NOT included.
param([ValidateSet("Full", "Lite", "Komplett", "Klein")][string]$Variante = "Full")
$ErrorActionPreference = "Stop"
if ($Variante -eq "Komplett") { $Variante = "Full" }
if ($Variante -eq "Klein") { $Variante = "Lite" }
$german = @{ Full = "Komplett"; Lite = "Klein" }[$Variante]   # name of the German INSTALLATION template
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyy-MM-dd"
$name = "CoreMonitor_${Variante}_$stamp"
$exportDir = Join-Path $root "export"
$work = Join-Path $exportDir $name
$cache = Join-Path $exportDir "_cache"
$pyVersion = "3.11.9"

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function CopyItem($rel) {
    $src = Join-Path $root $rel
    $dst = Join-Path $work $rel
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Copy-Item $src $dst -Force
}

Step "Preparing package $name"
New-Item -ItemType Directory -Force $exportDir, $cache | Out-Null
if (Test-Path $work) { Remove-Item $work -Recurse -Force }
New-Item -ItemType Directory -Force $work | Out-Null

# ---- Source code (both variants) ----
$files = @("server.py", "app.py", "i18n.py", "security.py", "mandelbrot.py", "pi.py", "hardware.py", "worker_util.py", "lastgen.py",
           "requirements.txt", "start.bat", "start.sh", "README.md", "README.de.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
           "static\index.html", "static\app.js", "static\mandel.js", "static\pi.js", "static\style.css",
           "csharp\MandelBench\Program.cs", "csharp\MandelBench\MandelBench.csproj",
           "rust\mandelbench\Cargo.toml", "rust\mandelbench\src\main.rs", "rust\mandelbench\.cargo\config.toml",
           "native\mandel_core.h", "native\platform.h", "native\build.bat", "native\build.sh",
           "native\c\mandel.c", "native\cpp\mandel.cpp", "native\asm\kernel.asm", "native\asm\kernel_nasm.asm",
           "native\gpu\mandel.hlsl", "native\gpu\mandel_gpu.cpp", "native\gpu\mandel.cl", "native\gpu\mandel_opencl.cpp",
           "tools\export.ps1", "tools\privacy_check.py", "tools\glossar.py", "tools\selftest.py", "tools\collect_licenses.py",
           "tools\INSTALLATION_Full.txt", "tools\INSTALLATION_Lite.txt",
           "tools\INSTALLATION_Komplett.txt", "tools\INSTALLATION_Klein.txt",
           "tools\export.sh", "tools\INSTALLATION_LINUX_Full.txt", "tools\INSTALLATION_LINUX_Lite.txt",
           "tools\INSTALLATION_LINUX_Komplett.txt", "tools\INSTALLATION_LINUX_Klein.txt",
           "export_full.bat", "export_lite.bat", "export_full.sh", "export_lite.sh")
foreach ($f in $files) { CopyItem $f }
foreach ($pdf in "Project_Report_Core_Monitor.pdf", "Projektbericht_Parallelisierung.pdf") {
    if (Test-Path (Join-Path $root $pdf)) { CopyItem $pdf }
}
Copy-Item (Join-Path $PSScriptRoot "INSTALLATION_$Variante.txt") (Join-Path $work "INSTALLATION.txt")
Copy-Item (Join-Path $PSScriptRoot "INSTALLATION_$german.txt") (Join-Path $work "INSTALLATION.de.txt")

if ($Variante -eq "Full") {
    Step "Compiling C, C++, assembler and GPU (Visual Studio)"
    & cmd.exe /c "call `"$root\native\build.bat`""
    if ($LASTEXITCODE) { throw "native\build.bat failed" }
    foreach ($f in "mandel_c.exe", "mandel_cpp.exe", "mandel_asm.exe", "mandel_gpu.exe", "mandel.hlsl",
                   "mandel_double.cso", "mandel_float.cso", "vcomp140.dll") { CopyItem "native\bin\$f" }

    Step "Compiling Rust"
    $cargo = (Get-Command cargo -ErrorAction SilentlyContinue).Source
    if (-not $cargo) { $cargo = "$env:USERPROFILE\.cargo\bin\cargo.exe" }
    Push-Location "$root\rust\mandelbench"; & $cargo build --release --quiet; $rc = $LASTEXITCODE; Pop-Location
    if ($rc) { throw "Rust build failed" }
    CopyItem "rust\mandelbench\target\release\mandelbench.exe"

    Step "Publishing C# as a self-contained .exe (runs without a .NET installation)"
    & dotnet publish "$root\csharp\MandelBench" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true `
        -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=none -o "$work\csharp\bin" --nologo -v q
    if ($LASTEXITCODE) { throw "dotnet publish failed" }

    Step "Python $pyVersion (embedded version) with all packages"
    $zip = Join-Path $cache "python-$pyVersion-embed-amd64.zip"
    if (-not (Test-Path $zip)) {
        Invoke-WebRequest "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-embed-amd64.zip" -OutFile $zip -UseBasicParsing
    }
    Expand-Archive $zip -DestinationPath "$work\python" -Force
    # Search paths: standard library, bundled packages, program folder; "import site" for the packages' .pth files
    $pth = Get-ChildItem "$work\python" -Filter "python*._pth" | Select-Object -First 1
    Set-Content $pth.FullName -Encoding ascii -Value @("python311.zip", ".", "Lib\site-packages", "..", "import site")
    $env:PIP_USER = "0"   # otherwise a Store Python installs "per user", which conflicts with --target
    & python -m pip install --quiet --disable-pip-version-check --no-warn-script-location `
        --target "$work\python\Lib\site-packages" --python-version 3.11 --platform win_amd64 --only-binary=:all: `
        -r "$root\requirements.txt" numba
    if ($LASTEXITCODE) { throw "pip install failed" }

    Step "Collecting the license texts of all bundled components (licenses\)"
    & python "$PSScriptRoot\collect_licenses.py" $work
    if ($LASTEXITCODE) { throw "collecting license texts failed" }

    Step "Adding the Pi reference (mpmath, 1 million digits)"
    if (Test-Path "$root\benchmarks\pi_referenz_mpmath.txt") { CopyItem "benchmarks\pi_referenz_mpmath.txt" }
}

Step "Cleaning up (intermediate files)"
Get-ChildItem $work -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
# pip creates launchers containing the Python path of THIS PC (e.g. C:\Users\<name>\...) – not needed in the package
if (Test-Path "$work\python\Lib\site-packages\bin") { Remove-Item "$work\python\Lib\site-packages\bin" -Recurse -Force }

Step "Privacy check (no information about this PC and its user in the package)"
$patterns = @($env:USERPROFILE, "\Users\$env:USERNAME\", "/Users/$env:USERNAME/", $root, ($root -replace '\\', '/'),
              $env:OneDrive, "\\$env:COMPUTERNAME\", "$env:COMPUTERNAME.", "$env:USERNAME@")
$patterns += (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
              Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }).IPAddress
foreach ($mac in (Get-NetAdapter -ErrorAction SilentlyContinue).MacAddress) { if ($mac) { $patterns += $mac; $patterns += ($mac -replace "-", ":") } }
& python "$PSScriptRoot\privacy_check.py" $work @($patterns | Where-Object { $_ })
if ($LASTEXITCODE) { throw "Privacy check: personal information found - package will NOT be created (see list above)" }

Step "Creating ZIP"
$zipOut = Join-Path $exportDir "$name.zip"
if (Test-Path $zipOut) { Remove-Item $zipOut -Force }
& tar.exe -a -c -f $zipOut -C $exportDir $name
if ($LASTEXITCODE) { throw "creating ZIP failed" }
$hash = (Get-FileHash $zipOut -Algorithm SHA256).Hash.ToLower()
Set-Content "$zipOut.sha256" -Encoding ascii -Value "$hash  $name.zip"   # check with: Get-FileHash <zip> -Algorithm SHA256
$size = (Get-ChildItem $work -Recurse -File | Measure-Object Length -Sum).Sum
Remove-Item $work -Recurse -Force   # only the ZIP remains; the Python download stays in export\_cache for the next run
Write-Host ("`nDone: {0}  (ZIP {1:N1} MB, unpacked {2:N1} MB)" -f $zipOut, ((Get-Item $zipOut).Length / 1MB), ($size / 1MB)) -ForegroundColor Green
Write-Host "SHA-256: $hash  ($name.zip.sha256)"
