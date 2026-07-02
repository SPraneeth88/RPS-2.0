"""
Shared test configuration.

Sets a throwaway SQLite database and disables the LLM NLU *before* any `rps`
module is imported, so the whole suite runs deterministically and offline. An
autouse fixture truncates the tables between tests for isolation.
"""
import os
import tempfile

# Must run at import time, before `rps.config` reads the environment.
_DB = os.path.join(tempfile.mkdtemp(prefix="rps_test_"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402

from rps.database import SessionLocal, init_db  # noqa: E402
from rps import models  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    with SessionLocal() as s:
        s.query(models.Reservation).delete()
        s.query(models.Vehicle).delete()
        s.commit()
    yield
