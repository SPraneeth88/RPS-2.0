"""
Central configuration for RPS 2.0.

Everything is driven by environment variables so the same code runs locally on
SQLite (zero setup) or against MySQL in an enterprise environment by changing a
single connection string. See README for the MySQL migration note.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # ---- Database -------------------------------------------------------
    # Default: local SQLite file (no server needed).
    # Enterprise: set DATABASE_URL=mysql+pymysql://user:pass@host/rps
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///rps2.db")

    # ---- LLM / NLU ------------------------------------------------------
    # If an Anthropic key is present, the NLU layer uses Claude for intent +
    # entity extraction. If absent, a deterministic rule-based parser is used
    # so the system still runs fully offline for demos and CI.
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    llm_model: str = os.getenv("RPS_LLM_MODEL", "claude-sonnet-4-6")

    # ---- Security aspect ------------------------------------------------
    # Optional API key that protects mutating admin endpoints. Empty = open
    # (convenient for a local walkthrough).
    admin_api_key: str = os.getenv("RPS_ADMIN_KEY", "")

    # ---- Server ---------------------------------------------------------
    host: str = os.getenv("RPS_HOST", "127.0.0.1")
    port: int = int(os.getenv("RPS_PORT", "8000"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
