from src.db.schema import connect
from src.db.seed_demo import seed_demo
from src.pipeline.runner import run_analytical_pipeline


def test_detailed_allocation_results_and_margin():
    seed_demo()
    run_analytical_pipeline()

    with connect() as conn:
        phase1_count = conn.execute(
            "SELECT COUNT(*) FROM allocation_results_phase1"
        ).fetchone()[0]
        phase2_count = conn.execute(
            "SELECT COUNT(*) FROM allocation_results_phase2"
        ).fetchone()[0]
        mismatches = conn.execute(
            """
            SELECT COUNT(*)
            FROM allocation_results_phase2
            WHERE ABS(
                direct_allocated_cost
                + indirect_allocated_cost
                - total_allocated_cost
            ) > 0.01
            """
        ).fetchone()[0]
        margin_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM psl_indicators
            WHERE analytical_margin_pct IS NOT NULL
              AND direct_allocated_cost IS NOT NULL
              AND indirect_allocated_cost IS NOT NULL
            """
        ).fetchone()[0]

    # 2020-2026 (7 years) at monthly granularity: 15 phase1 rules and
    # 24 phase2 rules x 12 months x 7 years.
    assert phase1_count == 15 * 12 * 7
    assert phase2_count == 24 * 12 * 7
    assert mismatches == 0
    assert margin_rows == 6 * 12 * 7
