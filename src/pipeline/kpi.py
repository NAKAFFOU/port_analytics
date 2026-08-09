from __future__ import annotations

import pandas as pd

from src.common.config import base_currency
from src.db.schema import connect
from src.pipeline.aggregate import (
    get_activity_volumes,
    get_cost_category_shares,
    get_occ_budgets,
    get_occ_direct_costs,
    get_psl_budgets,
    get_psl_revenues,
)
from src.pipeline.allocations import (
    phase1,
    phase1_detailed,
    phase2,
    phase2_detailed,
    store_allocation_results,
    validate_allocation_rules,
)
from src.pipeline.kpi_formulas import (
    analytical_margin_pct,
    cost_efficiency_index,
    cost_recovery_ratio,
    cost_variance_pct,
    overhead_share_pct,
    revenue_variance_pct,
)


def compute_and_store_kpis() -> tuple[int, int]:
    with connect() as conn:
        errors = validate_allocation_rules(conn)
        if errors:
            raise ValueError("; ".join(errors))

        direct = get_occ_direct_costs(conn)
        budgets = get_occ_budgets(conn)
        allocated = phase1(conn)
        concentration = get_cost_category_shares(conn)

        occ = direct.merge(budgets, on=["centre_code", "period_id"], how="outer")
        occ = occ.merge(allocated, on=["centre_code", "period_id"], how="left")
        occ = occ.merge(
            concentration, on=["centre_code", "period_id"], how="left"
        ).fillna(0)

        occ["total_occ_cost"] = (
            occ["total_direct_cost"] + occ["allocated_ssc_cost"]
        )
        occ["cost_variance_abs"] = (
            occ["total_direct_cost"] - occ["budget_direct"]
        )
        occ["cost_variance_pct"] = cost_variance_pct(
            occ["cost_variance_abs"], occ["budget_direct"]
        )
        occ["overhead_share_pct"] = overhead_share_pct(
            occ["allocated_ssc_cost"], occ["total_occ_cost"]
        )
        occ = occ.sort_values(["centre_code", "period_id"])
        # YTD must reset every calendar year once multiple years coexist in
        # the same table — group by (centre_code, year) rather than just
        # centre_code, or a multi-year dataset would cumsum continuously
        # across year boundaries instead of resetting each January.
        occ_year = occ["period_id"].str[:4]
        occ["actual_ytd"] = occ.groupby([occ["centre_code"], occ_year])[
            "total_direct_cost"
        ].cumsum()
        occ["budget_ytd"] = occ.groupby([occ["centre_code"], occ_year])[
            "budget_direct"
        ].cumsum()
        occ["budget_consumption_ytd"] = (
            occ["actual_ytd"] / occ["budget_ytd"].replace(0, pd.NA)
        )
        occ["currency_code"] = base_currency()

        phase1_detail = phase1_detailed(conn)
        phase2_detail = phase2_detailed(conn, occ)
        store_allocation_results(conn, phase1_detail, phase2_detail)

        psl_cost = phase2(conn, occ)
        revenues = get_psl_revenues(conn)
        revenue_budgets = get_psl_budgets(conn)
        volumes = get_activity_volumes(conn)

        psl = psl_cost.merge(
            revenues, on=["service_code", "period_id"], how="outer"
        )
        psl = psl.merge(
            revenue_budgets,
            on=["service_code", "period_id"],
            how="left",
        )
        psl = psl.merge(
            volumes,
            on=["service_code", "period_id"],
            how="left",
        ).fillna(0)

        psl["service_net_position"] = (
            psl["actual_revenue"] - psl["total_attributed_cost"]
        )
        psl["analytical_margin_pct"] = analytical_margin_pct(
            psl["service_net_position"], psl["actual_revenue"]
        )
        psl["cost_recovery_ratio"] = cost_recovery_ratio(
            psl["actual_revenue"], psl["total_attributed_cost"]
        )
        psl["revenue_variance_pct"] = revenue_variance_pct(
            psl["actual_revenue"], psl["budgeted_revenue"]
        )
        psl["cost_efficiency_index"] = cost_efficiency_index(
            psl["total_attributed_cost"], psl["activity_volume"]
        )
        psl = psl.sort_values(["service_code", "period_id"])
        psl_year = psl["period_id"].str[:4]
        psl["actual_revenue_ytd"] = psl.groupby([psl["service_code"], psl_year])[
            "actual_revenue"
        ].cumsum()
        psl["budget_revenue_ytd"] = psl.groupby([psl["service_code"], psl_year])[
            "budgeted_revenue"
        ].cumsum()
        psl["revenue_budget_achievement_ytd"] = (
            psl["actual_revenue_ytd"]
            / psl["budget_revenue_ytd"].replace(0, pd.NA)
        )
        psl["currency_code"] = base_currency()

        conn.execute("DELETE FROM occ_indicators")
        conn.execute("DELETE FROM psl_indicators")

        occ[
            [
                "centre_code",
                "period_id",
                "total_direct_cost",
                "allocated_ssc_cost",
                "total_occ_cost",
                "budget_direct",
                "cost_variance_abs",
                "cost_variance_pct",
                "overhead_share_pct",
                "budget_consumption_ytd",
                "top_cost_category_share",
                "currency_code",
            ]
        ].to_sql(
            "occ_indicators",
            conn,
            if_exists="append",
            index=False,
        )

        psl[
            [
                "service_code",
                "period_id",
                "direct_allocated_cost",
                "indirect_allocated_cost",
                "total_attributed_cost",
                "actual_revenue",
                "budgeted_revenue",
                "activity_volume",
                "service_net_position",
                "analytical_margin_pct",
                "cost_recovery_ratio",
                "revenue_variance_pct",
                "cost_efficiency_index",
                "revenue_budget_achievement_ytd",
                "currency_code",
            ]
        ].to_sql(
            "psl_indicators",
            conn,
            if_exists="append",
            index=False,
        )
        conn.commit()

    return len(occ), len(psl)
