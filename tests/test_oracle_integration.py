from __future__ import annotations

import os

import pytest

# Opt-in only: these tests open a real Oracle connection and must never run
# automatically in CI. Set RUN_ORACLE_INTEGRATION_TESTS=true and fill in the
# ORACLE_* variables in .env with a reachable instance before running:
#   python -m pytest tests/test_oracle_integration.py -v
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_ORACLE_INTEGRATION_TESTS", "false").strip().lower()
    not in {"1", "true", "yes", "on"},
    reason=(
        "Set RUN_ORACLE_INTEGRATION_TESTS=true and a reachable ORACLE_* "
        "target in .env to run this."
    ),
)


def test_real_oracle_connection_and_five_views():
    from src.adapters.oracle_metadata import inspect_all_views
    from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter

    adapter = OraclePBIViewsAdapter("config/sources/oracle_pbi_views.yaml")
    assert adapter.test_connection()

    reports = inspect_all_views(adapter.connector, adapter.schema)
    assert len(reports) == 5
    for report in reports:
        assert report.exists, f"{report.view} not found in ALL_OBJECTS"
        assert report.accessible, f"{report.view} not accessible: {report.error}"


def test_real_extraction_respects_row_limit_and_does_not_rescale_amount():
    from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter

    adapter = OraclePBIViewsAdapter("config/sources/oracle_pbi_views.yaml")
    for extractor in [
        adapter.extract_direct_allocations,
        adapter.extract_indirect_allocations,
        adapter.extract_cost_centre_costs,
        adapter.extract_service_revenues,
    ]:
        frame = extractor(2022, 2026, limit=10)
        assert len(frame) <= 10
        if not frame.empty:
            # amount_multiplier must stay 1: Oracle already inverted,
            # scaled and rounded MONTANT — confirm no fractional /100
            # remainder was reintroduced by this extraction path.
            assert (frame["amount_source"] == frame["amount_source"].round(0)).all()
