from __future__ import annotations

import pandas as pd

"""Shared KPI ratio formulas.

Both the synthetic SSC/OCC/PSL allocation pipeline (src/pipeline/kpi.py) and
the Oracle pre-allocated-views pipeline
(src/ingestion/oracle_views.py::build_analytics_from_preallocated_views) need
the same handful of ratios. They used to be duplicated inline in both places;
this module is the single definition each one calls, so the KPI meaning
cannot drift between the two data sources.
"""


def analytical_margin_pct(net_position: pd.Series, revenue: pd.Series) -> pd.Series:
    """Net position as a percentage of revenue. NA when revenue is zero."""
    return net_position / revenue.replace(0, pd.NA) * 100


def cost_recovery_ratio(revenue: pd.Series, total_cost: pd.Series) -> pd.Series:
    """Revenue divided by total attributed cost. NA when cost is zero."""
    return revenue / total_cost.replace(0, pd.NA)


def revenue_variance_pct(actual_revenue: pd.Series, budgeted_revenue: pd.Series) -> pd.Series:
    """Actual vs. budgeted revenue, as a percentage of budget."""
    return (actual_revenue - budgeted_revenue) / budgeted_revenue.replace(0, pd.NA) * 100


def cost_efficiency_index(total_cost: pd.Series, activity_volume: pd.Series) -> pd.Series:
    """Unit cost: total attributed cost per unit of activity volume."""
    return total_cost / activity_volume.replace(0, pd.NA)


def overhead_share_pct(allocated_ssc_cost: pd.Series, total_occ_cost: pd.Series) -> pd.Series:
    """Allocated shared-service cost as a percentage of total centre cost."""
    return allocated_ssc_cost / total_occ_cost.replace(0, pd.NA) * 100


def cost_variance_pct(cost_variance_abs: pd.Series, budget: pd.Series) -> pd.Series:
    """Cost variance (actual - budget) as a percentage of budget."""
    return cost_variance_abs / budget.replace(0, pd.NA) * 100
