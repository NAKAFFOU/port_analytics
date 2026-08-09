from __future__ import annotations

import pandas as pd
import pytest

from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter
from src.common.errors import ConfigurationError


class FakeConnector:
    def __init__(self):
        self.last_sql: str | None = None
        self.last_params: dict | None = None

    def query_dataframe(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params or {}
        return pd.DataFrame(columns=["reporting_year", "source_service_name", "amount_source"])


def _make_adapter(fake_connector: FakeConnector) -> OraclePBIViewsAdapter:
    # Bypass __init__ (which opens a real Oracle connector via env vars) to
    # unit-test _query's bind-parameter handling in isolation.
    adapter = object.__new__(OraclePBIViewsAdapter)
    adapter.profile = {
        "datasets": {
            "indirect_allocations": {
                "view": "AINDIRECTE_COUT",
                "year_column": "ANNEE",
                "category_column": "CATEGORIE",
                "service_column": "PRODUIT_FINI",
                "amount_column": "MONTANT",
                "amount_multiplier": 1,
            },
        },
    }
    adapter.connector = fake_connector
    adapter.schema = "PBI_JDE"
    adapter.default_currency = "XOF"
    return adapter


def test_filter_values_are_bound_not_concatenated_into_sql():
    connector = FakeConnector()
    adapter = _make_adapter(connector)

    adapter.extract_indirect_allocations(2022, 2026, category="Marchandises")

    assert ":filter_category_column" in connector.last_sql
    assert "Marchandises" not in connector.last_sql
    assert connector.last_params["filter_category_column"] == "Marchandises"


def test_unknown_filter_key_is_rejected():
    connector = FakeConnector()
    adapter = _make_adapter(connector)

    with pytest.raises(ConfigurationError):
        adapter._query(
            "indirect_allocations",
            [("year_column", "reporting_year", False)],
            2022,
            2026,
            filters={"not_a_real_column": "x"},
        )


def test_amount_multiplier_of_one_does_not_alter_montant():
    connector = FakeConnector()

    def fake_query(sql, params=None):
        return pd.DataFrame(
            {
                "reporting_year": [2024],
                "service_category": ["Marchandises"],
                "source_service_name": ["PF-Acces Nautique"],
                "amount_source": [-14025684364],
            }
        )

    connector.query_dataframe = fake_query
    adapter = _make_adapter(connector)

    frame = adapter.extract_indirect_allocations(2022, 2026)

    assert frame.iloc[0]["amount_source"] == -14025684364
