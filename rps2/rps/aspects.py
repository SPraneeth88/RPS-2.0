"""
Cross-cutting concerns — the Spring AOP analog.

The resume describes using Spring AOP to modularise logging and security so they
live outside the core business logic. In this Python service the same separation
is achieved with decorators and a FastAPI dependency. Three "aspects" are
provided:

  * @audit_log(action)  -> structured audit trail (the logging aspect)
  * @timed              -> latency metrics (the performance-monitoring aspect)
  * require_admin_key   -> endpoint authorisation (the security aspect)

Audit entries and latency samples are kept in small in-memory ring buffers so
the UI can surface "the AOP layer working" live during a walkthrough. In
production these would forward to a logging pipeline / APM backend.
"""
from __future__ import annotations

import functools
import logging
import time
from collections import deque
from typing import Any, Callable, Deque

from fastapi import Header, HTTPException

from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
)
logger = logging.getLogger("rps.aspect")

# In-memory observability buffers (most-recent-last).
AUDIT_TRAIL: Deque[dict] = deque(maxlen=200)
LATENCY_SAMPLES: Deque[dict] = deque(maxlen=200)


def audit_log(action: str) -> Callable:
    """Decorator that records an audit entry for every invocation of the join point."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            entry = {"action": action, "ts": time.time(), "status": "started"}
            try:
                result = func(*args, **kwargs)
                entry["status"] = "ok"
                return result
            except Exception as exc:  # noqa: BLE001
                entry["status"] = "error"
                entry["error"] = str(exc)
                logger.error("audit[%s] FAILED: %s", action, exc)
                raise
            finally:
                AUDIT_TRAIL.append(entry)
                logger.info("audit[%s] %s", action, entry["status"])

        return wrapper

    return decorator


def timed(func: Callable) -> Callable:
    """Decorator that measures wall-clock latency of the wrapped call."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            LATENCY_SAMPLES.append({"op": func.__name__, "ms": elapsed_ms, "ts": time.time()})

    return wrapper


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """
    FastAPI dependency enforcing the security aspect on mutating endpoints.

    If RPS_ADMIN_KEY is unset (default for local demos) the guard is a no-op so
    the walkthrough stays frictionless. Set the env var to lock down writes.
    """
    if not settings.admin_api_key:
        return
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key.")


def observability_snapshot() -> dict:
    """Return a compact view of the AOP buffers for the dashboard."""
    samples = list(LATENCY_SAMPLES)
    avg = round(sum(s["ms"] for s in samples) / len(samples), 2) if samples else 0.0
    return {
        "audit_trail": list(AUDIT_TRAIL)[-25:][::-1],
        "latency": {
            "samples": samples[-25:][::-1],
            "avg_ms": avg,
            "count": len(samples),
        },
    }
