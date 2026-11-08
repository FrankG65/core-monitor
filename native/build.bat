@echo off
rem Compiles the C, C++ and assembler variants with Visual Studio (MSVC).
rem /O2 = optimize, /fp:precise = no contracted computation steps (no FMA), so that the images match numba,
rem C# and Rust bit for bit. Deliberately WITHOUT /arch:AVX2: the programs check at runtime whether the
rem CPU has AVX2 and use the AVX2 kernel only then - so they also run on older processors.
setlocal
cd /d "%~dp0"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto novs
set VSDIR=
rem read the result via a file: "for /f" cannot cope with the parentheses in "Program Files (x86)"
"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath > "%TEMP%\km_vsdir.txt"
set /p VSDIR=<"%TEMP%\km_vsdir.txt"
del "%TEMP%\km_vsdir.txt" >nul 2>&1
if not defined VSDIR goto novs
echo Visual Studio: %VSDIR%
rem vcvars64 harmlessly reports that vswhere is not in PATH - suppress output
call "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
where cl >nul 2>&1 || goto novs
if not exist bin mkdir bin
rem /MT = link the runtime library statically: also runs on PCs without the "Visual C++ Redistributable"
set FLAGS=/nologo /O2 /fp:precise /MT /W3 /D_CRT_SECURE_NO_WARNINGS
cl %FLAGS% c\mandel.c /Fo:bin\mandel_c.obj /Fe:bin\mandel_c.exe >bin\build.log || goto fail
cl %FLAGS% /EHsc /std:c++17 cpp\mandel.cpp /Fo:bin\mandel_cpp.obj /Fe:bin\mandel_cpp.exe >>bin\build.log || goto fail
ml64 /nologo /c /Fo bin\kernel.obj asm\kernel.asm >>bin\build.log || goto fail
cl %FLAGS% /DUSE_ASM c\mandel.c bin\kernel.obj /Fo:bin\mandel_asm_host.obj /Fe:bin\mandel_asm.exe >>bin\build.log || goto fail
rem GPU (Direct3D 11 compute shader): compile the host program, put the shader file next to it (compiled at runtime)
cl %FLAGS% /EHsc /std:c++17 /openmp gpu\mandel_gpu.cpp /Fo:bin\mandel_gpu.obj /Fe:bin\mandel_gpu.exe >>bin\build.log || goto fail
copy /y gpu\mandel.hlsl bin\mandel.hlsl >nul
rem precompile the shaders (double and float): then the target PC needs no shader compiler
rem /Gis = strict IEEE rules, /O3 = optimize
fxc /nologo /T cs_5_0 /E main /O3 /Gis /Fo bin\mandel_double.cso gpu\mandel.hlsl >>bin\build.log || goto fail
fxc /nologo /T cs_5_0 /E main /O3 /Gis /D REAL=float /D USE_FLOAT=1 /Fo bin\mandel_float.cso gpu\mandel.hlsl >>bin\build.log || goto fail
rem put the OpenMP runtime (redistributable) next to the GPU program
for /d %%d in ("%VCToolsRedistDir%x64\Microsoft.VC*.OpenMP") do copy /y "%%d\vcomp140.dll" bin\ >nul
echo C, C++, assembler and GPU compiled.
exit /b 0
:novs
echo Visual Studio with C++ tools not found - skipping C/C++/assembler.
exit /b 1
:fail
type bin\build.log
exit /b 1
