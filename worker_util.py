"""Lightweight helpers for worker processes (Mandelbrot, Pi, load generator).

Deliberately without heavy dependencies: on Windows every worker starts as a new Python process and loads only
what it needs. If every worker loaded the whole web server and numba, 48 workers would need several GB of memory
(measured: with many simultaneous workers "paging file too small").
"""
from __future__ import annotations

import os
import threading
import time


def watch_parent(interval: float = 2.0):
    """Ends this child process as soon as the parent process (web server) no longer exists.

    Otherwise, on Windows, pool workers are left behind as orphans when the server is killed.
    """
    ppid = os.getppid()

    def loop():
        while True:
            time.sleep(interval)
            try:
                import psutil
                if not psutil.pid_exists(ppid):
                    os._exit(0)
            except ImportError:
                return
    threading.Thread(target=loop, daemon=True).start()


def init_worker(counter=None, order=None):
    """Slightly lower priority (browser and web server stay smooth), optional fixed thread, parent watch."""
    try:
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 5)
        if order:
            with counter.get_lock():  # every worker takes the next number -> fixed thread
                k = counter.value
                counter.value += 1
            me.cpu_affinity([order[k % len(order)]])
    except Exception:
        pass
    watch_parent()


def retry_access_denied(start, tries: int = 10, wait: float = 1.0):
    """Starts a program via start(); on "access denied" waits briefly and tries again.

    Antivirus programs often lock freshly unpacked .exe files for a few seconds on first start
    (observed: individual computation methods and GPU detection failed right after unpacking).
    Runs in the server process (not in workers), so the message follows the current language.
    """
    for i in range(tries):
        try:
            return start()
        except PermissionError as e:
            if i == tries - 1:
                from i18n import L
                raise PermissionError(L(f"{e} – vermutlich blockiert ein Virenscanner das Programm "
                                        "(unbegründet, siehe INSTALLATION.de.txt: „Virenscanner“)",
                                        f"{e} – probably an antivirus is blocking the program "
                                        "(unfounded, see INSTALLATION.txt: \"Antivirus\")")) from e
            time.sleep(wait)


def ping(_):
    time.sleep(0.15)  # keeps the worker busy briefly so that the pool starts all processes
    return os.getpid()
