from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import streamlit as st

LOGGER = logging.getLogger(__name__)

from src.common.config import base_currency, get_settings
from src.currency.converter import CurrencyConverter
from src.db.schema import connect
from src.pipeline.kpi_formulas import (
    analytical_margin_pct,
    cost_efficiency_index,
    cost_recovery_ratio,
    cost_variance_pct,
    overhead_share_pct,
    revenue_variance_pct,
)


@st.cache_data(ttl=int(get_settings()["dashboard"].get("cache_ttl_seconds", 60)))
def load_dashboard_data() -> dict[str, pd.DataFrame]:
    queries = {
        "occ": """
            SELECT oi.*, cc.centre_name, cc.centre_name_en, cc.tier, cc.centre_type
            FROM occ_indicators oi
            JOIN cost_centres cc ON cc.centre_code = oi.centre_code
        """,
        "psl": """
            SELECT pi.*, sl.service_name, sl.service_name_en,
                   sl.service_category, sl.service_category_en,
                   sl.revenue_type, sl.primary_driver
            FROM psl_indicators pi
            JOIN service_lines sl ON sl.service_code = pi.service_code
        """,
        "alloc1": """
            SELECT a.*, s.centre_name AS source_name, s.centre_name_en AS source_name_en,
                   d.centre_name AS destination_name, d.centre_name_en AS destination_name_en
            FROM allocation_results_phase1 a
            JOIN cost_centres s ON s.centre_code = a.source_ssc
            JOIN cost_centres d ON d.centre_code = a.destination_occ
        """,
        "alloc2": """
            SELECT a.*, c.centre_name AS source_name, c.centre_name_en AS source_name_en,
                   s.service_name, s.service_name_en, s.service_category, s.service_category_en
            FROM allocation_results_phase2 a
            JOIN cost_centres c ON c.centre_code = a.source_occ
            JOIN service_lines s ON s.service_code = a.destination_psl
        """,
        "alerts": "SELECT * FROM decision_alerts",
        "actions": "SELECT * FROM decision_support_actions",
        "periods": "SELECT * FROM reporting_periods ORDER BY period_id",
        "batches": """
            SELECT * FROM ingestion_batches
            ORDER BY started_at DESC LIMIT 20
        """,
        "issues": """
            SELECT * FROM data_quality_issues
            ORDER BY created_at DESC LIMIT 100
        """,
        # Raw Oracle PBI_JDE facts, kept at their original granularity
        # (before the OCC/PSL aggregation). Only populated in Oracle-views
        # mode; empty in DEMO mode. Used for the family/subfamily/account
        # breakdowns that occ_indicators/psl_indicators do not carry.
        "oracle_facts": """
            SELECT measure_type, period_id, centre_code, service_code,
                   service_category, service_category_en,
                   account, account_en, family, family_en, subfamily, subfamily_en,
                   amount_base
            FROM oracle_view_facts
        """,
        # Revenue-only facts (SERVICE_REVENUE), joined to service_lines
        # solely for the canonical product name. service_lines.service_code
        # is a primary key (one row per code), so this join is one-to-one
        # and can never duplicate a revenue row — required for the
        # category -> product -> account decomposition on the Revenue page,
        # which oracle_view_facts alone cannot provide (no product name).
        "revenue_facts": """
            SELECT f.period_id, f.reporting_year,
                   f.service_category, f.service_category_en,
                   f.service_code, sl.service_name, sl.service_name_en,
                   f.account, f.account_en,
                   f.amount_base, f.amount_source, f.source_currency
            FROM oracle_view_facts f
            LEFT JOIN service_lines sl ON sl.service_code = f.service_code
            WHERE f.measure_type = 'SERVICE_REVENUE'
        """,
    }
    with connect() as conn:
        return {
            name: pd.read_sql_query(sql, conn)
            for name, sql in queries.items()
        }


# (base_column, english_column) pairs used by localize() for each frame
# returned by load_dashboard_data(). One shared table so every view applies
# the same convention instead of each re-deciding which columns translate.
LOCALIZABLE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "occ": [("centre_name", "centre_name_en")],
    "psl": [("service_name", "service_name_en"), ("service_category", "service_category_en")],
    "alloc1": [("source_name", "source_name_en"), ("destination_name", "destination_name_en")],
    "alloc2": [
        ("source_name", "source_name_en"),
        ("service_name", "service_name_en"),
        ("service_category", "service_category_en"),
    ],
    "oracle_facts": [
        ("service_category", "service_category_en"),
        ("account", "account_en"),
        ("family", "family_en"),
        ("subfamily", "subfamily_en"),
    ],
    "revenue_facts": [
        ("service_category", "service_category_en"),
        ("service_name", "service_name_en"),
        ("account", "account_en"),
    ],
}


def localize(frame: pd.DataFrame, language: str, column_pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """Overwrites each base column with its English counterpart when
    `language == "en"` (falling back to the base/French value where no
    translation exists); a no-op otherwise. Source tables always keep the
    raw JDE value — this only reshapes the render-time copy handed to a
    view. See LOCALIZABLE_COLUMNS for the pairs used per dataset."""
    if language != "en":
        return frame
    work = frame.copy()
    for base_column, en_column in column_pairs:
        if base_column in work.columns and en_column in work.columns:
            translated = work[en_column]
            work[base_column] = translated.where(
                translated.notna() & (translated != ""), work[base_column]
            )
    return work


def period_filter(
    frame: pd.DataFrame,
    year: int,
    period_id: str | None,
) -> pd.DataFrame:
    work = frame.copy()
    if "period_id" not in work.columns:
        return work
    work = work[work["period_id"].str.startswith(f"{year}-")]
    if period_id and period_id != "ALL":
        work = work[work["period_id"] == period_id]
    return work


def aggregate_psl(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    group_cols = [
        "service_code",
        "service_name",
        "service_category",
        "revenue_type",
        "primary_driver",
    ]
    sum_cols = [
        "direct_allocated_cost",
        "indirect_allocated_cost",
        "total_attributed_cost",
        "actual_revenue",
        "budgeted_revenue",
        "activity_volume",
        "service_net_position",
    ]
    result = frame.groupby(group_cols, as_index=False)[sum_cols].sum(min_count=1)
    result["analytical_margin_pct"] = analytical_margin_pct(
        result["service_net_position"], result["actual_revenue"]
    )
    result["cost_recovery_ratio"] = cost_recovery_ratio(
        result["actual_revenue"], result["total_attributed_cost"]
    )
    result["revenue_variance_pct"] = revenue_variance_pct(
        result["actual_revenue"], result["budgeted_revenue"]
    )
    result["cost_efficiency_index"] = cost_efficiency_index(
        result["total_attributed_cost"], result["activity_volume"]
    )
    return result


def aggregate_occ(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    group_cols = [
        "centre_code",
        "centre_name",
        "tier",
        "centre_type",
    ]
    sum_cols = [
        "total_direct_cost",
        "allocated_ssc_cost",
        "total_occ_cost",
        "budget_direct",
        "cost_variance_abs",
    ]
    result = frame.groupby(group_cols, as_index=False)[sum_cols].sum(min_count=1)
    result["cost_variance_pct"] = cost_variance_pct(
        result["cost_variance_abs"], result["budget_direct"]
    )
    result["overhead_share_pct"] = overhead_share_pct(
        result["allocated_ssc_cost"], result["total_occ_cost"]
    )
    result["budget_consumption_ytd"] = (
        result["total_direct_cost"]
        / result["budget_direct"].replace(0, pd.NA)
    )
    return result


def get_display_rate(display_currency: str, rate_date: date) -> float:
    if display_currency == base_currency():
        return 1.0
    return CurrencyConverter().convert(
        1.0,
        base_currency(),
        display_currency,
        rate_date,
    ).amount


def convert_columns(
    frame: pd.DataFrame,
    columns: list[str],
    rate: float,
) -> pd.DataFrame:
    work = frame.copy()
    for column in columns:
        if column in work.columns:
            work[column] = (
                pd.to_numeric(work[column], errors="coerce") * rate
            )
    return work


def clean_text_column(series: pd.Series, not_specified_label: str) -> pd.Series:
    """Strips whitespace and collapses blank/whitespace-only values to a
    single "not specified" label. Guards against JDE NCHAR padding (or a
    genuinely missing value) silently creating spurious distinct
    categories in a groupby."""
    cleaned = series.astype("string").str.strip()
    cleaned = cleaned.replace("", pd.NA)
    return cleaned.fillna(not_specified_label)


def _top_n_with_other(
    totals: pd.Series, top_n: int, other_label: str
) -> list[tuple[str, float]]:
    """Returns the largest `top_n` (name, value) pairs plus one trailing
    ("Others", remainder_sum) entry when there is a remainder. The visible
    entries always sum back exactly to `totals.sum()` — nothing is ever
    silently dropped."""
    ordered = totals.sort_values(ascending=False)
    top = ordered.head(top_n)
    rest = ordered.iloc[top_n:]
    items = [(str(name), float(value)) for name, value in top.items()]
    if not rest.empty:
        items.append((other_label, float(rest.sum())))
    return items


def build_revenue_hierarchy(
    frame: pd.DataFrame,
    root_label: str,
    other_label: str,
    not_specified_label: str,
    top_n: int = 5,
) -> dict:
    """Builds a Revenue -> category -> product -> account tree from revenue
    facts alone (no join to another fact table at the detail level, so no
    amount can be duplicated). Every level is capped at `top_n` children
    plus an "Others" node covering the exact remainder.

    Every node that has children gets its value from `sum()` of those
    *exact* child values, computed bottom-up — never from an independent
    groupby total. Plotly's Icicle/Treemap with branchvalues="total"
    requires parent == sum(children) exactly; two independently computed
    pandas sums over the same rows can differ by a float-rounding epsilon
    (order of summation differs), which is enough for plotly.js to reject
    the whole figure and render nothing, with no error surfaced to Python.

    `frame` must already reflect every filter that should apply (year,
    period, family/sub-family). The root value this returns may differ
    from `frame["amount_base"].sum()` by a similar float epsilon — well
    within validate_revenue_dashboard_totals' tolerance — but is exactly
    self-consistent for rendering.
    """
    if frame.empty:
        return {"name": root_label, "value": 0.0, "children": []}

    work = frame.copy()
    work["service_category"] = clean_text_column(work["service_category"], not_specified_label)
    work["service_name"] = clean_text_column(work["service_name"], not_specified_label)
    work["account"] = clean_text_column(work["account"], not_specified_label)

    category_totals = work.groupby("service_category")["amount_base"].sum()

    root_children = []
    for category, cat_reference_total in _top_n_with_other(category_totals, top_n, other_label):
        if category == other_label:
            root_children.append({"name": category, "value": cat_reference_total, "children": []})
            continue
        cat_frame = work[work["service_category"] == category]
        product_totals = cat_frame.groupby("service_name")["amount_base"].sum()

        category_children = []
        for product, prod_reference_total in _top_n_with_other(product_totals, top_n, other_label):
            if product == other_label:
                category_children.append(
                    {"name": product, "value": prod_reference_total, "children": []}
                )
                continue
            prod_frame = cat_frame[cat_frame["service_name"] == product]
            account_totals = prod_frame.groupby("account")["amount_base"].sum()
            account_children = [
                {"name": account, "value": value}
                for account, value in _top_n_with_other(account_totals, top_n, other_label)
            ]
            # Bottom-up: this product's value is the exact sum of the
            # account children just built, not a second, independent sum.
            prod_total = sum(child["value"] for child in account_children)
            category_children.append(
                {"name": product, "value": prod_total, "children": account_children}
            )
        cat_total = sum(child["value"] for child in category_children)
        root_children.append(
            {"name": category, "value": cat_total, "children": category_children}
        )

    root_total = sum(child["value"] for child in root_children)
    return {"name": root_label, "value": root_total, "children": root_children}


def flatten_hierarchy_for_icicle(hierarchy: dict) -> pd.DataFrame:
    """Flattens the nested tree from build_revenue_hierarchy into the
    ids/labels/parents/values arrays a Plotly go.Icicle/go.Treemap needs.
    Each id encodes its full path so a click event can be traced back to
    the exact (category, product, account) that was selected, even when
    two branches share a leaf name (e.g. the same account name under two
    different products)."""
    rows: list[dict] = []

    def _walk(node: dict, parent_id: str, path: tuple[str, ...]) -> None:
        node_path = path + (node["name"],)
        node_id = " / ".join(node_path)
        rows.append(
            {
                "id": node_id,
                "label": node["name"],
                "parent": parent_id,
                "value": max(node["value"], 0.0),
                "signed_value": node["value"],
                "depth": len(path),
            }
        )
        for child in node.get("children", []):
            _walk(child, node_id, node_path)

    _walk(hierarchy, "", ())
    return pd.DataFrame(rows)


def resolve_trend_scope(
    frame: pd.DataFrame,
    family: str,
    subfamily: str,
    all_label: str,
) -> tuple[pd.DataFrame, str]:
    """Applies a page's existing Family/Sub-family selection to a raw,
    multi-year psl frame ahead of an annual trend chart, and picks which
    column to group the trend by: service_category (family) while nothing
    is drilled into yet, service_name (sub-family) the moment a family is
    chosen — mirroring whatever drill-down behaviour the page's own
    matrix/tree already uses, so the two stay in sync without a second,
    independent filtering rule. Returns (scoped_frame, dimension_column).
    """
    work = frame
    if family != all_label:
        work = work[work["service_category"] == family]
        dimension_column = "service_name"
    else:
        dimension_column = "service_category"
    if subfamily != all_label:
        work = work[work["service_name"] == subfamily]
    return work, dimension_column


def annual_trend_by_dimension(
    frame: pd.DataFrame,
    dimension_column: str,
    value_column: str,
    year: int,
    period_id: str,
    other_label: str,
    not_specified_label: str,
    top_n: int = 6,
) -> pd.DataFrame:
    """Long-format (reporting_year, dimension_column, value_column) trend,
    built directly from a raw psl frame (one row per service_code/period_id
    already — no aggregate_psl re-grouping, so no year information is lost).

    Global filters are applied without contradicting the point of a
    multi-year trend: `year` caps the window at "up to and including the
    selected sidebar year" (never restricted to that single year alone),
    and `period_id` — annual-only when sourced from a live Oracle
    connection, potentially monthly in synthetic demo data — is matched
    by its suffix (the part after the
    first "-") across every year, so e.g. selecting a given month compares
    that same month year over year instead of collapsing to one point.

    The Top-N set is chosen once from the *whole* window's totals so the
    same dimension values are stacked/plotted every year; folding a
    smaller, per-year Top-N would make series pop in and out as "Others"
    from one year to the next.
    """
    columns = ["reporting_year", dimension_column, value_column]
    if frame.empty or "period_id" not in frame.columns:
        return pd.DataFrame(columns=columns)

    work = frame.copy()
    work["reporting_year"] = work["period_id"].str.slice(0, 4).astype(int)
    work = work[work["reporting_year"] <= int(year)]
    if period_id and period_id != "ALL":
        suffix = period_id.split("-", 1)[1] if "-" in period_id else period_id
        work = work[work["period_id"].str.endswith(f"-{suffix}")]

    if work.empty:
        return pd.DataFrame(columns=columns)

    work[dimension_column] = clean_text_column(work[dimension_column], not_specified_label)
    totals = work.groupby(dimension_column)[value_column].sum()
    top_names = {
        name for name, _ in _top_n_with_other(totals, top_n, other_label)
        if name != other_label
    }
    work[dimension_column] = work[dimension_column].where(
        work[dimension_column].isin(top_names), other_label
    )

    grouped = work.groupby(["reporting_year", dimension_column], as_index=False)[value_column].sum()
    return grouped


def validate_revenue_dashboard_totals(
    kpi_revenue: float, tree_root_revenue: float, tolerance: float = 0.01
) -> bool:
    """Section 3/17 control: the KPI card and the tree root are computed
    from two independent aggregations of the same filtered revenue facts —
    this checks they still agree. A mismatch means a filter was applied
    inconsistently between the two, not a rounding artefact, so it is
    logged loudly rather than silently swallowed. Never raises: a
    dashboard must still render while the underlying issue is fixed."""
    diff = abs(float(kpi_revenue) - float(tree_root_revenue))
    if diff > tolerance:
        LOGGER.warning(
            "Revenue dashboard inconsistency: KPI revenue=%.4f vs tree root=%.4f (diff=%.4f)",
            kpi_revenue, tree_root_revenue, diff,
        )
        return False
    return True
