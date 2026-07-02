"""
Database layer — SQLAlchemy engine + session management.

This is the modern equivalent of the JDBC/connection-management layer described
on the resume. The `transactional()` context manager guarantees the
commit-on-success / rollback-on-failure semantics that protect data integrity
for reservation records (the "100% data integrity" claim).
"""
from __future__ import annotations

import contextlib
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# `check_same_thread` is only needed for SQLite + a threaded web server.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@contextlib.contextmanager
def transactional() -> Iterator[Session]:
    """
    Provide a transactional scope around a series of operations.

    Commits if the block succeeds, rolls back on any exception, and always
    closes the session. This is the single choke-point that keeps reservation
    writes atomic.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    from . import models  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)
