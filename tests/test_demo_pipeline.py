from datetime import date

from src.common.config import base_currency
from src.currency.converter import CurrencyConverter
from src.db.schema import connect, list_user_tables
from src.db.seed_demo import seed_demo
from src.pipeline.runner import run_analytical_pipeline


def test_complete_demo_pipeline_and_fx():
    seed_demo()
    occ, psl, alerts = run_analytical_pipeline()
    assert len(list_user_tables()) >= 27
    # 2020-2026 (7 years) at monthly granularity: 5 OCC-tier centres / 6
    # service lines x 12 months x 7 years.
    assert occ == 5 * 12 * 7
    assert psl == 6 * 12 * 7
    assert alerts > 0

    converter = CurrencyConverter()
    converted = converter.convert(100.0, "EUR", base_currency(), date(2025, 7, 15))
    assert converted.amount > 0
    assert converted.rate > 0

    with connect() as conn:
        currencies = {row[0] for row in conn.execute("SELECT DISTINCT source_currency FROM actual_transactions")}
        critical = conn.execute(
            """SELECT COUNT(*) FROM decision_alerts
               WHERE entity_code='PSL-PIL' AND period_id='2025-11' AND severity='CRITICAL'"""
        ).fetchone()[0]
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert {"GBP", "EUR", "USD", "XOF"}.issubset(currencies)
    assert critical >= 1
    assert not fk_issues


def test_demo_seed_is_idempotent():
    seed_demo()
    with connect() as conn:
        first = conn.execute("SELECT COUNT(*) FROM actual_transactions").fetchone()[0]
    seed_demo()
    with connect() as conn:
        second = conn.execute("SELECT COUNT(*) FROM actual_transactions").fetchone()[0]
    # 8 centres x 4 categories x 12 months x 7 years (2020-2026).
    assert first == second == 8 * 4 * 12 * 7
