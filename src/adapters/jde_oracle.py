from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from src.adapters.base import AccountingSourceAdapter
from src.common.config import env_optional, load_yaml, project_path
from src.common.identifiers import safe_oracle_identifier
from src.connectors.factory import create_connector

CANONICAL_COLUMNS = [
    "source_row_id",    "company_code",    "document_number",    "document_type",    "business_unit",    "object_account",
    "subsidiary",    "transaction_date",    "amount_source",    "source_currency",    "ledger_type",    "description",
]


def jde_cyyddd_to_date(value: int | float | str) -> date:
    raw = int(float(value))
    if raw <= 0:
        raise ValueError(f"Invalid JDE Julian date: {value}")
    century = raw // 100000
    yy = (raw // 1000) % 100
    day_of_year = raw % 1000
    year = 1900 + (century * 100) + yy
    return date(year, 1, 1) + timedelta(days=day_of_year - 1)


def date_to_jde_cyyddd(value: date) -> int:
    century = (value.year - 1900) // 100
    yy = value.year % 100
    day_of_year = value.timetuple().tm_yday
    return century * 100000 + yy * 1000 + day_of_year


class JDEOracleAdapter(AccountingSourceAdapter):
    def __init__(self, profile_path: str | Path):
        self.profile = load_yaml(profile_path)
        self.connector = create_connector(self.profile)
        self.source_system = self.profile["source_system"]
        self.jde = self.profile.get("jde", {})

    def test_connection(self) -> bool:
        return self.connector.test_connection()

    def _render_sql(self, sql_file: str) -> str:
        sql_path = project_path(sql_file)
        sql = sql_path.read_text(encoding="utf-8")
        schema_env = self.jde["data_schema_env"]
        schema = safe_oracle_identifier(env_optional(schema_env, "PRODDTA") or "PRODDTA", "schema")
        return sql.replace("{{DATA_SCHEMA}}", schema)

    def extract_accounting_transactions(self, date_from: date, date_to: date) -> pd.DataFrame:
        dataset = self.profile["datasets"]["accounting_transactions"]
        if not dataset.get("enabled", True):
            return pd.DataFrame(columns=CANONICAL_COLUMNS)

        sql = self._render_sql(dataset["sql_file"])
        frame = self.connector.query_dataframe(
            sql,
            {
                "start_jde_date": date_to_jde_cyyddd(date_from),
                "end_jde_date": date_to_jde_cyyddd(date_to),
                "ledger_type": self.jde.get("ledger_type", "AA"),
            },
        )

        if frame.empty:
            return pd.DataFrame(columns=CANONICAL_COLUMNS)

        default_currency_env = self.jde.get("default_currency_env", "SOURCE_DB_DEFAULT_CURRENCY")
        default_currency = (env_optional(default_currency_env, "GBP") or "GBP").upper()
        divisor = float(self.jde.get("amount_divisor", 1.0))
        multiplier = float(self.jde.get("amount_multiplier", 1.0))

        frame["transaction_date"] = frame["transaction_jde_date"].apply(jde_cyyddd_to_date).astype(str)
        frame["amount_source"] = pd.to_numeric(frame["amount_source"], errors="raise") / divisor * multiplier
        frame["source_currency"] = frame["source_currency"].fillna(default_currency).replace("", default_currency).str.upper()

        for column in ["company_code", "business_unit", "object_account", "subsidiary", "ledger_type"]:
            frame[column] = frame[column].fillna("").astype(str).str.strip()
        frame["source_row_id"] = frame["source_row_id"].astype(str).str.strip()
        frame["document_number"] = frame["document_number"].fillna("").astype(str).str.strip()
        frame["document_type"] = frame["document_type"].fillna("").astype(str).str.strip()
        frame["description"] = frame["description"].fillna("").astype(str).str.strip()
        return frame[CANONICAL_COLUMNS]
