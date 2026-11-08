"""Protection against requests from outside (e.g. DNS rebinding or foreign websites in the browser).

The server only listens on 127.0.0.1. In addition every request (HTTP and WebSocket) must
  - come from a loopback address (127.x.x.x / ::1),
  - be addressed to this server: Host header 127.0.0.1:<port>, localhost:<port> or [::1]:<port>,
  - if the browser sends an Origin header: come from one of these addresses.
Anything else is rejected (HTTP 403 / WebSocket closed), written to logs/security.log and reported:
console warning, counter + last events for the page (red warning in the header).
"""
from __future__ import annotations

import collections
import logging
import logging.handlers
import os
import threading
import time
from pathlib import Path

from i18n import L

PORT = int(os.environ.get("PORT", "8000"))
_NAMES = ("127.0.0.1", "localhost", "[::1]")
ALLOWED_HOSTS = {f"{n}:{PORT}" for n in _NAMES} | ({*_NAMES} if PORT == 80 else set())
ALLOWED_ORIGINS = {f"http://{h}" for h in ALLOWED_HOSTS}
LOG_FILE = Path(os.environ.get("KM_SECURITY_LOG") or Path(__file__).parent / "logs" / "security.log")

_lock = threading.Lock()
_blocked = 0
_recent: collections.deque = collections.deque(maxlen=20)
_log: logging.Logger | None = None


def _logger() -> logging.Logger:
    global _log
    if _log is None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _log = logging.getLogger("core-monitor.security")
        _log.setLevel(logging.INFO)
        _log.propagate = False
        h = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        _log.addHandler(h)
    return _log


def problem(client: str | None, host: str | None, origin: str | None) -> str | None:
    """Reason for rejecting a request, or None if it is allowed."""
    if not client or not (client.startswith("127.") or client == "::1"):
        return "client"
    if (host or "").lower() not in ALLOWED_HOSTS:
        return "host"
    if origin is not None and origin.lower() not in ALLOWED_ORIGINS:
        return "origin"
    return None


def record(reason: str, client, host, origin, method: str, path: str, agent) -> dict:
    """Log and remember a rejected request; print a warning in the console window."""
    global _blocked
    ev = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "reason": reason, "client": client, "host": host,
          "origin": origin, "method": method, "path": path, "agent": (agent or "")[:200]}
    with _lock:
        _blocked += 1
        _recent.appendleft(ev)
    try:
        _logger().info("BLOCKED reason=%s client=%s host=%r origin=%r method=%s path=%s agent=%r",
                       reason, client, host, origin, method, path, ev["agent"])
    except OSError:
        pass
    print(L(f"WARNUNG: Anfrage von außen abgewiesen ({reason}): {method} {path}, Host={host!r}, Origin={origin!r}"
            f" – Details in logs/security.log",
            f"WARNING: request from outside rejected ({reason}): {method} {path}, Host={host!r}, Origin={origin!r}"
            f" – details in logs/security.log"), flush=True)
    return ev


def status() -> dict:
    with _lock:
        return {"blocked": _blocked, "recent": list(_recent)}
