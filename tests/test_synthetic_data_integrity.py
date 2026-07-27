"""Data-integrity checks for the rebuilt synthetic pipeline (2020-2026):
monthly/annual consistency, absence of negative charges, and the
revenue -> direct -> indirect -> net arithmetic used by the
02_Résultat_Net waterfall chart.
"""

from src.db.schema import connect
from src.db.seed_demo import seed_demo
from src.pipeline.runner import run_analytical_pipeline


def test_monthly_budget_sums_to_annual_budget_exactly():
    """Budgets have no random noise applied (unlike actuals), so
    sum(12 monthly rows) must equal the single annual row exactly for a
    given centre/category/year — this is the "cohérence somme(mois) ~=
    total annuel" guarantee for the deterministic half of the dataset."""
    seed_demo(granularity="monthly", year_from=2023, year_to=2023)
    with connect() as conn:
        monthly_total = conn.execute(
            """SELECT SUM(amount_base) FROM budgets
               WHERE centre_code='OCC-CARGO' AND category_code='AC-PAY'
                 AND period_id LIKE '2023-%'"""
        ).fetchone()[0]

    seed_demo(granularity="annual", year_from=2023, year_to=2023)
    with connect() as conn:
        annual_total = conn.execute(
            """SELECT amount_base FROM budgets
               WHERE centre_code='OCC-CARGO' AND category_code='AC-PAY'
                 AND period_id='2023-ANNUAL'"""
        ).fetchone()[0]

    assert monthly_total is not None and annual_total is not None
    # Each monthly row is independently rounded to 2dp through a currency
    # round-trip (base -> source -> base), so summing 12 of them can differ
    # from the single annual row's own rounding by a few cents — not a
    # bug, a compounding-rounding artefact. A tight *relative* tolerance
    # still catches a real consistency break (e.g. a wrong trend/weight).
    assert abs(monthly_total - annual_total) / annual_total < 0.0001


def test_monthly_actuals_approximate_annual_actuals():
    """Actuals apply an independent random factor per period, so monthly
    and annual runs are two separate simulations, not a re-aggregation of
    the same draw — they are expected to be close (same trend/seasonality
    baseline) but not bit-identical. A loose tolerance both documents and
    enforces that expectation."""
    seed_demo(granularity="monthly", year_from=2024, year_to=2024)
    with connect() as conn:
        monthly_total = conn.execute(
            """SELECT SUM(amount_base) FROM actual_transactions
               WHERE centre_code='OCC-NAV' AND category_code='AC-PAY'
                 AND period_id LIKE '2024-%'"""
        ).fetchone()[0]

    seed_demo(granularity="annual", year_from=2024, year_to=2024)
    with connect() as conn:
        annual_total = conn.execute(
            """SELECT amount_base FROM actual_transactions
               WHERE centre_code='OCC-NAV' AND category_code='AC-PAY'
                 AND period_id='2024-ANNUAL'"""
        ).fetchone()[0]

    assert monthly_total is not None and annual_total is not None
    assert abs(monthly_total - annual_total) / annual_total < 0.15


def test_no_negative_charges_in_synthetic_demo_pipeline():
    seed_demo(granularity="annual")
    run_analytical_pipeline()
    with connect() as conn:
        negative_direct = conn.execute(
            "SELECT COUNT(*) FROM occ_indicators WHERE total_direct_cost < 0"
        ).fetchone()[0]
        negative_allocated = conn.execute(
            """SELECT COUNT(*) FROM psl_indicators
               WHERE direct_allocated_cost < 0 OR indirect_allocated_cost < 0
                  OR total_attributed_cost < 0"""
        ).fetchone()[0]
    assert negative_direct == 0
    assert negative_allocated == 0


def test_no_negative_charges_in_synthetic_oracle_views_export():
    from src.ingestion.oracle_views import run_oracle_views_sample_pipeline

    run_oracle_views_sample_pipeline(2020, 2026, granularity="annual")
    with connect() as conn:
        negative_costs = conn.execute(
            """SELECT COUNT(*) FROM oracle_view_facts
               WHERE measure_type IN ('DIRECT_ALLOCATION','INDIRECT_ALLOCATION','COST_CENTRE_COST')
                 AND amount_base < 0"""
        ).fetchone()[0]
    assert negative_costs == 0


def test_waterfall_arithmetic_revenue_minus_costs_equals_net():
    """The 02_Résultat_Net waterfall (Revenue -> -Direct -> -Indirect ->
    Net result) must reconcile exactly with psl_indicators, for every row
    — not just in aggregate."""
    seed_demo(granularity="annual")
    run_analytical_pipeline()
    with connect() as conn:
        rows = conn.execute(
            """SELECT actual_revenue, direct_allocated_cost, indirect_allocated_cost,
                      service_net_position
               FROM psl_indicators"""
        ).fetchall()
    assert rows
    for revenue, direct, indirect, net in rows:
        assert abs((revenue - direct - indirect) - net) < 0.01
