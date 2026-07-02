"""
Launch the RPS 2.0 server.

    python run.py

Seeds the database on first run, then starts the API + UI on
http://127.0.0.1:8000 (override host/port with RPS_HOST / RPS_PORT).
"""
from __future__ import annotations

import uvicorn

from rps.config import settings
from rps.database import SessionLocal, init_db
from rps.models import Vehicle


def _seed_if_empty() -> None:
    init_db()
    with SessionLocal() as s:
        if s.query(Vehicle).count() == 0:
            from seed_data import seed
            seed()


if __name__ == "__main__":
    _seed_if_empty()
    mode = "Claude (LLM)" if settings.llm_enabled else "rule-based (offline)"
    print(f"\nRPS 2.0 starting — NLU mode: {mode}")
    print(f"Open http://{settings.host}:{settings.port}\n")
    uvicorn.run("rps.api:app", host=settings.host, port=settings.port, reload=False)
