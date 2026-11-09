#!/bin/sh
# Compiles the C, C++, assembler and GPU (OpenCL) variants on Linux with GCC and NASM.
# -O2 = optimize, -ffp-contract=off = no contracted computation steps (no FMA), so that the images match
# numba, C# and Rust bit for bit. Deliberately WITHOUT -mavx2: the programs check at runtime whether the CPU
# has AVX2 and use the AVX2 kernel only then - so they also run on older processors.
# Missing tools are skipped (the web page then shows the variant as unavailable).
cd "$(dirname "$0")" || exit 1
CC=${CC:-gcc}
CXX=${CXX:-g++}
mkdir -p bin
: > bin/build.log
FLAGS="-O2 -ffp-contract=off -fno-fast-math -Wall -Wno-unused-function -pthread"
# link the C/C++ runtime support statically: the programs then also run on PCs without a compiler (package "Full")
STATIC="-static-libgcc"
STATIC_CXX="-static-libgcc -static-libstdc++"
ok=1
built=""
if command -v "$CC" >/dev/null 2>&1; then
    "$CC" $FLAGS $STATIC -std=gnu11 c/mandel.c -o bin/mandel_c -lm >>bin/build.log 2>&1 && built="$built C" || ok=0
else
    echo "C compiler ($CC) not found - install: sudo apt install build-essential" >&2; ok=0
fi
if command -v "$CXX" >/dev/null 2>&1; then
    "$CXX" $FLAGS $STATIC_CXX -std=c++17 cpp/mandel.cpp -o bin/mandel_cpp >>bin/build.log 2>&1 && built="$built C++" || ok=0
fi
if command -v nasm >/dev/null 2>&1 && command -v "$CC" >/dev/null 2>&1; then
    nasm -f elf64 -o bin/kernel_nasm.o asm/kernel_nasm.asm >>bin/build.log 2>&1 &&
    "$CC" $FLAGS $STATIC -std=gnu11 -DUSE_ASM c/mandel.c bin/kernel_nasm.o -o bin/mandel_asm -lm >>bin/build.log 2>&1 &&
    built="$built assembler" || ok=0
else
    echo "NASM not found - skipping the assembler variant (install: sudo apt install nasm)" >&2
fi
# GPU via OpenCL: needs the OpenCL headers and the loader library (ocl-icd-opencl-dev)
if command -v "$CXX" >/dev/null 2>&1 && [ -f /usr/include/CL/cl.h ]; then
    "$CXX" $FLAGS $STATIC_CXX -std=c++17 gpu/mandel_opencl.cpp -o bin/mandel_gpu -lOpenCL >>bin/build.log 2>&1 &&
    cp gpu/mandel.cl bin/mandel.cl && built="$built GPU(OpenCL)" || ok=0
else
    echo "OpenCL headers not found - skipping the GPU variant (install: sudo apt install ocl-icd-opencl-dev)" >&2
fi
if [ "$ok" = 1 ]; then
    echo "Compiled:$built"
    exit 0
fi
cat bin/build.log >&2
echo "Compiled:$built (with errors, see above)" >&2
exit 1
