from __future__ import annotations

import pandas as pd


def get_occ_direct_costs(conn):
    return pd.read_sql_query(
        """
        SELECT a.centre_code,a.period_id,SUM(a.amount_base) AS total_direct_cost
        FROM actual_transactions a
        JOIN cost_centres c ON c.centre_code=a.centre_code
        JOIN account_categories k ON k.category_code=a.category_code
        WHERE c.tier='OCC' AND k.category_type='DIRECT_COST'
        GROUP BY a.centre_code,a.period_id
        """, conn)


def get_ssc_costs(conn):
    return pd.read_sql_query(
        """
        SELECT a.centre_code AS ssc_code,a.period_id,SUM(a.amount_base) AS ssc_total_cost
        FROM actual_transactions a JOIN cost_centres c ON c.centre_code=a.centre_code
        WHERE c.tier='SSC' GROUP BY a.centre_code,a.period_id
        """, conn)


def get_occ_budgets(conn):
    return pd.read_sql_query(
        """
        SELECT b.centre_code,b.period_id,SUM(b.amount_base) AS budget_direct
        FROM budgets b JOIN cost_centres c ON c.centre_code=b.centre_code
        JOIN account_categories k ON k.category_code=b.category_code
        WHERE c.tier='OCC' AND k.category_type='DIRECT_COST'
        GROUP BY b.centre_code,b.period_id
        """, conn)


def get_cost_category_shares(conn):
    category = pd.read_sql_query(
        """
        SELECT a.centre_code,a.period_id,a.category_code,SUM(a.amount_base) AS category_cost
        FROM actual_transactions a JOIN cost_centres c ON c.centre_code=a.centre_code
        WHERE c.tier='OCC' GROUP BY a.centre_code,a.period_id,a.category_code
        """, conn)
    if category.empty:
        return pd.DataFrame(columns=["centre_code", "period_id", "top_cost_category_share"])
    total = category.groupby(["centre_code", "period_id"], as_index=False)["category_cost"].sum().rename(columns={"category_cost": "total"})
    top = category.groupby(["centre_code", "period_id"], as_index=False)["category_cost"].max().rename(columns={"category_cost": "top"})
    result = total.merge(top, on=["centre_code", "period_id"])
    result["top_cost_category_share"] = result["top"] / result["total"].replace(0, pd.NA) * 100
    return result[["centre_code", "period_id", "top_cost_category_share"]]


def get_psl_revenues(conn):
    return pd.read_sql_query("SELECT service_code,period_id,SUM(amount_base) AS actual_revenue FROM revenue_transactions GROUP BY service_code,period_id", conn)


def get_psl_budgets(conn):
    return pd.read_sql_query("SELECT service_code,period_id,SUM(budgeted_revenue_base) AS budgeted_revenue FROM service_budgets GROUP BY service_code,period_id", conn)


def get_activity_volumes(conn):
    return pd.read_sql_query("SELECT service_code,period_id,SUM(volume_units) AS activity_volume FROM activity_volumes GROUP BY service_code,period_id", conn)
