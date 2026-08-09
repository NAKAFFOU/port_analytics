from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.common.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    settings_path = _resolve(os.getenv("PORT_ANALYTICS_SETTINGS", "config/settings.yaml"))
    if not settings_path.exists():
        raise ConfigurationError(f"Settings file not found: {settings_path}")
    with settings_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def load_yaml(path_value: str | Path) -> dict[str, Any]:
    path = _resolve(path_value)
    if not path.exists():
        raise ConfigurationError(f"YAML file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def project_path(path_value: str | Path) -> Path:
    return _resolve(path_value)


def env_required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"Required environment variable is missing: {name}")
    return value.strip()


def env_optional(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = env_optional(name)
    return int(value) if value is not None else default


def database_path() -> Path:
    # Lets the test suite (see tests/conftest.py) point at an isolated file
    # instead of the analyst's working database — running pytest must never
    # reset or leave stray rows in the actual data/port_analytics.db.
    override = env_optional("PORT_ANALYTICS_DB_PATH")
    if override:
        return project_path(override)
    settings = get_settings()
    return project_path(settings["application"]["database_path"])


def base_currency() -> str:
    return str(get_settings()["currency"]["base_currency"]).upper()
