"""Hardware detection at startup: CPU (cores, threads, cache groups, instruction sets) and graphics cards.

Everything else in the program is based on these values (worker counts, benchmark steps, offered
computation methods, heatmap, texts). That way it also runs on other computers.

For testing, a different computer can be simulated, e.g.:
    set KM_SIMULATE=logical=8,physical=8,avx2=0,fma=0,gpu=0          (Windows)
    KM_SIMULATE=logical=8,physical=8,avx2=0,fma=0,gpu=0 ./start.sh     (Linux)
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
from pathlib import Path

import psutil

from worker_util import retry_access_denied

ROOT = Path(__file__).parent
GPU_PROBE = ROOT / "native" / "bin" / ("mandel_gpu.exe" if os.name == "nt" else "mandel_gpu")


def _simulation() -> dict:
    out = {}
    for part in os.environ.get("KM_SIMULATE", "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


SIM = _simulation()


# --------------------------------------------------------------------------
# Topology: cores (SMT siblings), L3 groups (CCX), NUMA nodes, processor groups
# --------------------------------------------------------------------------
def _affinity(raw: bytes, base: int) -> list[int]:
    """GROUP_AFFINITY: Mask (8 bytes), Group (2 bytes), Reserved -> logical processors."""
    mask = int.from_bytes(raw[base:base + 8], "little")
    group = int.from_bytes(raw[base + 8:base + 10], "little")
    return [group * 64 + b for b in range(64) if mask >> b & 1]


def _topology_windows() -> dict:
    """GetLogicalProcessorInformationEx (RelationAll): cores, L3 groups, NUMA nodes, processor groups."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(0xFFFF, None, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not k32.GetLogicalProcessorInformationEx(0xFFFF, buf, ctypes.byref(size)):
        raise OSError(ctypes.get_last_error())
    raw, off = buf.raw, 0
    cores, l3, numa, groups, l3_size = [], [], 0, 1, 0
    while off < size.value:
        rel = int.from_bytes(raw[off:off + 4], "little")
        rec = int.from_bytes(raw[off + 4:off + 8], "little")
        if rel == 0:    # RelationProcessorCore: Flags, EfficiencyClass, Reserved[20], GroupCount, GroupMask[]
            group_count = int.from_bytes(raw[off + 30:off + 32], "little")
            cores.append(sorted(lp for g in range(group_count) for lp in _affinity(raw, off + 32 + g * 16)))
        elif rel == 1:  # RelationNumaNode
            numa += 1
        elif rel == 2 and raw[off + 8] == 3:  # RelationCache, level 3: size at offset 12, GroupMask at offset 40
            l3.append(_affinity(raw, off + 40))
            l3_size = int.from_bytes(raw[off + 12:off + 16], "little")
        elif rel == 4:  # RelationGroup: MaximumGroupCount, ActiveGroupCount
            groups = int.from_bytes(raw[off + 10:off + 12], "little")
        off += rec
    return {"cores": sorted(cores), "l3": sorted(l3), "numa_nodes": max(numa, 1), "processor_groups": groups,
            "l3_kb": l3_size // 1024}


def _cpu_list(text: str) -> list[int]:
    """Linux CPU list such as "0-3,8,10-11" -> [0, 1, 2, 3, 8, 10, 11]."""
    out = []
    for part in text.strip().split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def _topology_linux() -> dict:
    """/sys/devices/system/cpu: cores (thread_siblings_list), L3 groups (cache/index*/shared_cpu_list), NUMA nodes."""
    base = Path("/sys/devices/system/cpu")
    online = _cpu_list((base / "online").read_text())
    cores, l3, l3_kb = set(), set(), 0
    for cpu in online:
        d = base / f"cpu{cpu}"
        cores.add(tuple(_cpu_list((d / "topology" / "thread_siblings_list").read_text())))
        for idx in sorted((d / "cache").glob("index*")):
            try:
                if (idx / "level").read_text().strip() == "3":
                    l3.add(tuple(_cpu_list((idx / "shared_cpu_list").read_text())))
                    size = (idx / "size").read_text().strip().upper()   # e.g. "16384K"
                    l3_kb = int(size[:-1]) * (1024 if size.endswith("M") else 1) if size[-1] in "KM" else int(size) // 1024
            except (OSError, ValueError):
                pass
    numa = len(list(Path("/sys/devices/system/node").glob("node[0-9]*")))
    return {"cores": sorted(list(c) for c in cores), "l3": sorted(list(g) for g in l3), "numa_nodes": max(numa, 1),
            "processor_groups": 1, "l3_kb": l3_kb}


def _cpu_name_vendor() -> tuple[str, str]:
    if os.name != "nt":   # Linux: /proc/cpuinfo ("model name", "vendor_id")
        name = vendor = ""
        try:
            for line in Path("/proc/cpuinfo").read_text(errors="replace").splitlines():
                key, _, val = line.partition(":")
                key = key.strip()
                if key == "model name" and not name:
                    name = val.strip()
                elif key == "vendor_id" and not vendor:
                    vendor = val.strip()
                if name and vendor:
                    break
        except OSError:
            pass
        return name or platform.processor(), vendor
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        vendor = winreg.QueryValueEx(key, "VendorIdentifier")[0].strip()
        return name, vendor
    except Exception:
        return platform.processor(), ""


def _isa() -> dict:
    """Instruction sets reported by the CPU (via numpy, which determines them with cpuid)."""
    try:
        from numpy._core._multiarray_umath import __cpu_features__ as f
    except ImportError:
        try:
            from numpy.core._multiarray_umath import __cpu_features__ as f
        except ImportError:
            f = {}
    return {"sse2": bool(f.get("SSE2", True)), "avx": bool(f.get("AVX")), "avx2": bool(f.get("AVX2")),
            "fma": bool(f.get("FMA3")), "avx512f": bool(f.get("AVX512F"))}


def cpu_freq():
    """psutil.cpu_freq(), or None if the system does not report it. WSL 1, for example, lacks
    /sys/.../cpufreq/scaling_min_freq, and psutil then raises FileNotFoundError."""
    try:
        return psutil.cpu_freq()
    except (OSError, NotImplementedError, ValueError):
        return None


def detect_cpu() -> dict:
    logical = psutil.cpu_count(logical=True) or 1
    physical = psutil.cpu_count(logical=False) or logical
    name, vendor = _cpu_name_vendor()
    topo, source = None, "assumed"   # source ID; app.py turns it into text (topology_source_text)
    try:
        if os.name == "nt":
            t, src = _topology_windows(), "GetLogicalProcessorInformationEx"
        else:
            t, src = _topology_linux(), "/sys/devices/system/cpu"
        if sorted(lp for c in t["cores"] for lp in c) == list(range(logical)):
            topo, source = t, src
    except Exception:
        pass
    if "logical" in SIM or "physical" in SIM:   # test: different computer
        logical = int(SIM.get("logical", logical))
        physical = int(SIM.get("physical", min(physical, logical)))
        topo, source = None, "simulated"
    if topo is None:
        per = max(1, logical // max(1, physical))
        cores = [list(range(i, min(i + per, logical))) for i in range(0, logical, per)]
        topo = {"cores": cores, "l3": [], "numa_nodes": 1, "processor_groups": (logical + 63) // 64, "l3_kb": 0}
    isa = _isa()
    for k in ("avx", "avx2", "fma", "avx512f"):
        if k in SIM:
            isa[k] = SIM[k] == "1"
    freq = cpu_freq()
    return {"name": name, "vendor": vendor, "logical": logical, "physical": physical, "smt": logical > physical,
            "threads_per_core": max(len(c) for c in topo["cores"]), "cores": topo["cores"], "l3": topo["l3"],
            "l3_kb": topo["l3_kb"], "numa_nodes": topo["numa_nodes"], "processor_groups": topo["processor_groups"],
            "max_mhz": round(freq.max) if freq and freq.max else None, "isa": isa,
            "ram_gb": round(psutil.virtual_memory().total / 2**30, 1), "topology_source": source,
            "simulated": bool(SIM)}


def detect_gpus() -> list[dict]:
    """All graphics cards via the helper program (mandel_gpu --probe): name, memory, compute, double.
    Windows: DXGI/Direct3D 11. Linux: OpenCL (every installed OpenCL driver, e.g. NVIDIA, AMD ROCm, Intel, POCL)."""
    if SIM.get("gpu") == "0":
        return []
    if not GPU_PROBE.exists():
        return []
    try:
        r = retry_access_denied(lambda: subprocess.run(
            [str(GPU_PROBE), "--probe"], capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        return json.loads(r.stdout).get("adapters", [])
    except Exception:
        return []


def best_gpu(gpus: list[dict]) -> int | None:
    """Default: the card with compute shaders and the most dedicated memory (no software adapter)."""
    usable = [g for g in gpus if g.get("compute") and not g.get("software")]
    if not usable:
        return None
    return max(usable, key=lambda g: (g.get("vram_mb", 0), g.get("double", False)))["index"]


def scaling_steps(logical: int, physical: int) -> list[int]:
    """Worker steps for scaling tests: powers of two, half/full core count, middle of the SMT range, all threads."""
    steps = {1, logical, physical, max(1, physical // 2)}
    p = 2
    while p < logical:
        steps.add(p)
        p *= 2
    if logical > physical:
        steps.add((physical + logical) // 2)
    return sorted(s for s in steps if 1 <= s <= logical)
