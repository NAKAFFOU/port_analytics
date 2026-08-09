from pathlib import Path

import pandas as pd

from src.common.config import load_yaml
from src.currency.repository import FxRate, FxRateRepository
from src.db.schema import connect
from src.ingestion.oracle_views import ingest_frames, run_oracle_views_sample_pipeline


def test_preallocated_oracle_views_pipeline():
    # Uses one year (2025) of the fabricated PBI_JDE-format CSV export
    # (src.db.seed_demo.generate_synthetic_oracle_views) — entirely
    # synthetic, generated fresh on each call.
    result = run_oracle_views_sample_pipeline(2025, 2025, granularity="annual")
    assert result.facts_rejected == 0
    assert result.facts_loaded > 0
    assert result.occ_rows > 0
    assert result.psl_rows > 0

    with connect() as conn:
        annual = conn.execute(
            """SELECT period_granularity, month FROM reporting_periods
            WHERE period_id='2025-ANNUAL'"""
        ).fetchone()
        rules1 = conn.execute(
            "SELECT COUNT(*) FROM allocation_rules_phase1"
        ).fetchone()[0]
        rules2 = conn.execute(
            "SELECT COUNT(*) FROM allocation_rules_phase2"
        ).fetchone()[0]
        direct_source = conn.execute(
            """SELECT SUM(amount_source), SUM(amount_base)
            FROM oracle_view_facts
            WHERE measure_type='DIRECT_ALLOCATION'"""
        ).fetchone()
        # "PF-Remorquage" is mapped to a clean display name via
        # config/mappings/oracle_pbi_views/service_lines.csv ("Remorquage" /
        # "Towage") rather than kept as the raw JDE product code.
        remorquage = conn.execute(
            """SELECT pi.actual_revenue,pi.direct_allocated_cost,
                      pi.indirect_allocated_cost,pi.service_net_position,
                      pi.currency_code,sl.service_name,sl.service_name_en
            FROM psl_indicators pi
            JOIN service_lines sl ON sl.service_code=pi.service_code
            WHERE sl.service_name='Remorquage'"""
        ).fetchone()
        allocation_errors = conn.execute(
            """SELECT COUNT(*) FROM allocation_results_phase2
            WHERE ABS(direct_allocated_cost+indirect_allocated_cost-total_allocated_cost)>0.01"""
        ).fetchone()[0]

    assert annual[0] == "YEAR"
    assert annual[1] is None
    assert rules1 == 0
    assert rules2 == 0
    # XOF -> GBP shrinks magnitude regardless of sign (real costs are
    # negative); compare absolute values rather than assuming a sign.
    assert abs(direct_source[1]) < abs(direct_source[0])
    assert remorquage is not None
    assert abs(
        remorquage[3]
        - (remorquage[0] - remorquage[1] - remorquage[2])
    ) < 0.01
    assert remorquage[4] == "GBP"
    assert remorquage[5] == "Remorquage"
    assert remorquage[6] == "Towage"
    assert allocation_errors == 0


def test_family_subfamily_and_account_are_captured_without_hash_collisions():
    # Two COST_CENTRE_COST rows share every dimension except family/subfamily.
    # Before family/subfamily were folded into source_row_hash, this would
    # violate the UNIQUE(batch_id, measure_type, source_row_hash) constraint
    # and silently reject the second row.
    from datetime import date

    FxRateRepository().upsert(
        FxRate(date(2024, 12, 31), "XOF", "GBP", 0.0013, "TEST_ONLY", True)
    )
    profile = load_yaml("config/sources/oracle_pbi_views.yaml")
    frames = {
        "COST_CENTRE_COST": pd.DataFrame(
            {
                "reporting_year": ["2024", "2024"],
                "source_cost_centre_code": ["9999", "9999"],
                "source_cost_centre_name": ["TEST CENTRE", "TEST CENTRE"],
                "family": ["Charges de personnel", "Prestations externes"],
                "subfamily": ["Salaires", "Autres prestataires"],
                "amount_source": ["-1000", "-2000"],
                "source_currency": ["XOF", "XOF"],
            }
        ),
        "SERVICE_REVENUE": pd.DataFrame(
            {
                "reporting_year": ["2024", "2024"],
                "service_category": ["Marchandises", "Marchandises"],
                "source_service_name": ["PF-Test", "PF-Test"],
                "account": ["Compte A", "Compte B"],
                "amount_source": ["500", "700"],
                "source_currency": ["XOF", "XOF"],
            }
        ),
    }
    result = ingest_frames(frames, profile, 2024, 2024, "PBI_JDE", replace=True)
    assert result.facts_rejected == 0
    assert result.facts_loaded == 4

    with connect() as conn:
        rows = conn.execute(
            """SELECT family, subfamily FROM oracle_view_facts
            WHERE measure_type='COST_CENTRE_COST' ORDER BY family"""
        ).fetchall()
        accounts = conn.execute(
            """SELECT account FROM oracle_view_facts
            WHERE measure_type='SERVICE_REVENUE' ORDER BY account"""
        ).fetchall()
    assert [tuple(r) for r in rows] == [
        ("Charges de personnel", "Salaires"),
        ("Prestations externes", "Autres prestataires"),
    ]
    assert [r[0] for r in accounts] == ["Compte A", "Compte B"]
