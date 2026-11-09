#!/bin/sh
# Builds the Linux "Full" package (runs without installation and without internet) as
# export/CoreMonitor_Full_Linux_<date>.tar.gz
# Requires on THIS PC: internet (once, for the Python download), python3, build-essential, nasm, ocl-icd-opencl-dev,
# .NET SDK 10, Rust. Best built on the OLDEST supported system (e.g. Ubuntu 22.04), so the programs run everywhere.
exec sh "$(dirname "$0")/tools/export.sh" Full
