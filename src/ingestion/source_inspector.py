from __future__ import annotations

from src.adapters.jde_oracle import JDEOracleAdapter
from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter
from src.common.config import get_settings, load_yaml
from src.common.identifiers import safe_oracle_identifier


def inspect_source_object(object_name: str):
    profile_path = get_settings()["source"]["active_profile"]
    profile = load_yaml(profile_path)
    if profile.get("adapter") == "oracle_pbi_views":
        return OraclePBIViewsAdapter(profile_path).inspect_view(object_name)

    adapter = JDEOracleAdapter(profile_path)
    import os
    schema_env = adapter.jde["data_schema_env"]
    owner = safe_oracle_identifier(
        os.getenv(schema_env, "PRODDTA"), "schema"
    )
    table = safe_oracle_identifier(object_name, "table")
    return adapter.connector.inspect_table(owner, table)


def inspect_jde_table(table_name: str):
    return inspect_source_object(table_name)
