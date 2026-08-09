from __future__ import annotations

from src.common.errors import ConfigurationError
from src.connectors.oracle import OracleConnector


def create_connector(profile: dict):
    adapter = str(profile.get("adapter", "")).lower()
    if adapter in {"jde_oracle", "oracle_pbi_views"}:
        return OracleConnector(profile)
    raise ConfigurationError(f"No connector factory entry for adapter: {adapter}")
