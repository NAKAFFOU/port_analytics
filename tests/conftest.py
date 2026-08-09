from __future__ import annotations

import os
from pathlib import Path

# Must run before any src module calls database_path()/get_settings(), so
# this env var is set at import time (conftest.py is imported before test
# modules) rather than inside a fixture. The test suite must never touch
# the analyst's working data/port_analytics.db — that file is shared with a
# running dashboard and, before this fix, pytest silently reset it and left
# stray test rows behind.
_TEST_DB_NAME = "test_port_analytics.db"
_TEST_DB_PATH = Path(__file__).resolve().parents[1] / "data" / _TEST_DB_NAME
os.environ.setdefault("PORT_ANALYTICS_DB_PATH", str(_TEST_DB_PATH))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def clean_database():
    root = Path(__file__).resolve().parents[1]
    for suffix in ["", "-wal", "-shm"]:
        path = root / "data" / f"{_TEST_DB_NAME}{suffix}"
        if path.exists():
            path.unlink()
    yield
