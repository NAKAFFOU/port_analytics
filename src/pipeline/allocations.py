from __future__ import annotations

import pandas as pd

from src.common.config import base_currency
from src.pipeline.aggregate import get_ssc_costs


def validate_allocation_rules(conn) -> list[str]:
    errors: list[str] = []
    for table, source in [
        ("allocation_rules_phase1", "source_ssc"),
        ("allocation_rules_phase2", "source_occ"),
    ]:
        rows = conn.execute(
            f"""
            SELECT {source}, SUM(allocation_pct)
            FROM {table}
            GROUP BY {source}
            HAVING ABS(SUM(allocation_pct) - 100) > 0.001
            """
        ).fetchall()
        errors.extend(
            [f"{table}: {row[0]} sums to {row[1]}" for row in rows]
        )
    return errors


def phase1_detailed(conn) -> pd.DataFrame:
    """Allocate Shared Service Centre costs to Operational Cost Centres."""
    ssc = get_ssc_costs(conn)
    rules = pd.read_sql_query(
        """
        SELECT source_ssc, destination_occ, driver_code, allocation_pct
        FROM allocation_rules_phase1
        """,
        conn,
    )
    merged = ssc.merge(
        rules,
        left_on="ssc_code",
        right_on="source_ssc",
        how="inner",
    )
    merged["allocated_indirect_cost"] = (
        merged["ssc_total_cost"] * merged["allocation_pct"] / 100
    )
    merged["currency_code"] = base_currency()
    return merged[
        [
            "source_ssc",
            "destination_occ",
            "period_id",
            "driver_code",
            "allocation_pct",
            "ssc_total_cost",
            "allocated_indirect_cost",
            "currency_code",
        ]
    ].rename(columns={"ssc_total_cost": "source_ssc_cost"})


def phase1(conn) -> pd.DataFrame:
    detailed = phase1_detailed(conn)
    result = detailed.groupby(
        ["destination_occ", "period_id"], as_index=False
    )["allocated_indirect_cost"].sum()
    return result.rename(
        columns={
            "destination_occ": "centre_code",
            "allocated_indirect_cost": "allocated_ssc_cost",
        }
    )


def phase2_detailed(conn, occ: pd.DataFrame) -> pd.DataFrame:
    """Attribute OCC direct and allocated indirect costs to service lines."""
    rules = pd.read_sql_query(
        """
        SELECT source_occ, destination_psl, driver_code, allocation_pct
        FROM allocation_rules_phase2
        """,
        conn,
    )
    merged = occ[
        [
            "centre_code",
            "period_id",
            "total_direct_cost",
            "allocated_ssc_cost",
            "total_occ_cost",
        ]
    ].merge(
        rules,
        left_on="centre_code",
        right_on="source_occ",
        how="inner",
    )
    factor = merged["allocation_pct"] / 100
    merged["direct_allocated_cost"] = merged["total_direct_cost"] * factor
    merged["indirect_allocated_cost"] = merged["allocated_ssc_cost"] * factor
    merged["total_allocated_cost"] = (
        merged["direct_allocated_cost"] + merged["indirect_allocated_cost"]
    )
    merged["currency_code"] = base_currency()
    return merged[
        [
            "source_occ",
            "destination_psl",
            "period_id",
            "driver_code",
            "allocation_pct",
            "direct_allocated_cost",
            "indirect_allocated_cost",
            "total_allocated_cost",
            "currency_code",
        ]
    ]


def phase2(conn, occ: pd.DataFrame) -> pd.DataFrame:
    detailed = phase2_detailed(conn, occ)
    return (
        detailed.groupby(["destination_psl", "period_id"], as_index=False)[
            [
                "direct_allocated_cost",
                "indirect_allocated_cost",
                "total_allocated_cost",
            ]
        ]
        .sum()
        .rename(
            columns={
                "destination_psl": "service_code",
                "total_allocated_cost": "total_attributed_cost",
            }
        )
    )


def store_allocation_results(
    conn,
    phase1_detail: pd.DataFrame,
    phase2_detail: pd.DataFrame,
) -> None:
    conn.execute("DELETE FROM allocation_results_phase1")
    conn.execute("DELETE FROM allocation_results_phase2")

    phase1_detail.to_sql(
        "allocation_results_phase1",
        conn,
        if_exists="append",
        index=False,
    )
    phase2_detail.to_sql(
        "allocation_results_phase2",
        conn,
        if_exists="append",
        index=False,
    )
