"""Load generator: work function of the load processes (separate, lightweight module – see worker_util.py)."""
from __future__ import annotations

import math
import os
import time

import psutil

from worker_util import watch_parent


def burn(core: int | None, intensity: float, stop, deadline: float):
    """Generates load with duty cycle `intensity` (0..1) in 100 ms periods."""
    me = psutil.Process()
    try:
        # lower priority: browser and web server stay usable despite 100 % load
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
        if core is not None:
            me.cpu_affinity([core])
    except Exception:
        pass
    watch_parent()
    period = 0.1
    x = 0.0001
    while not stop.is_set() and time.time() < deadline:
        start = time.perf_counter()
        busy_until = start + period * intensity
        while time.perf_counter() < busy_until:
            x = math.sqrt(x * x + 1.234)  # pure computation
        rest = period - (time.perf_counter() - start)
        if rest > 0:
            stop.wait(rest)
