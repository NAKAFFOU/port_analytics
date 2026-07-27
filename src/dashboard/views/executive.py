from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.components import (
    compact_number,
    kpi_card,
    plotly_layout,
    sparkline,
)
from src.dashboard.data import (
    LOCALIZABLE_COLUMNS,
    aggregate_psl,
    convert_columns,
    localize,
    period_filter,
)
from src.dashboard.theme import render_header
from src.dashboard.viz_theme import category_colour_map


def _percentage(value: float, language: str) -> str:
    rendered = f"{float(value or 0):,.2f}"
    if language == "fr":
        rendered = rendered.replace(",", " ").replace(".", ",")
    return f"{rendered} %"


def _normalise_numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = frame.copy()
    for column in columns:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0.0)
    return work


def _last_12_periods_series(
    psl_source: pd.DataFrame,
    selected_category: str,
    selected_service: str,
    all_categories_label: str,
    all_services_label: str,
    display_rate: float,
) -> dict[str, list[float]]:
    """Sums each KPI measure per period over the last (up to) 12 available
    periods for the current filter scope, in chronological order — the
    trailing window used by every sparkline under the KPI ribbon."""
    if psl_source.empty or "period_id" not in psl_source.columns:
        return {}
    scoped = psl_source
    if selected_category != all_categories_label:
        scoped = scoped[scoped["service_category"] == selected_category]
    if selected_service != all_services_label:
        scoped = scoped[scoped["service_name"] == selected_service]
    if scoped.empty:
        return {}

    ordered_periods = sorted(scoped["period_id"].dropna().unique())
    last_periods = ordered_periods[-12:]
    scoped = scoped[scoped["period_id"].isin(last_periods)]
    scoped = convert_columns(
        scoped,
        ["direct_allocated_cost", "indirect_allocated_cost", "total_attributed_cost", "actual_revenue"],
        display_rate,
    )
    scoped = _normalise_numeric_columns(
        scoped, ["direct_allocated_cost", "indirect_allocated_cost", "total_attributed_cost", "actual_revenue"]
    )
    by_period = scoped.groupby("period_id")[
        ["direct_allocated_cost", "indirect_allocated_cost", "total_attributed_cost", "actual_revenue"]
    ].sum().reindex(last_periods).fillna(0.0)

    revenue = by_period["actual_revenue"]
    total_cost = by_period["total_attributed_cost"]
    net = revenue - total_cost
    margin = (net / revenue.replace(0, pd.NA) * 100).fillna(0.0)

    return {
        "revenue": revenue.tolist(),
        "direct": by_period["direct_allocated_cost"].tolist(),
        "indirect": by_period["indirect_allocated_cost"].tolist(),
        "total_cost": total_cost.tolist(),
        "net": net.tolist(),
        "margin": margin.tolist(),
    }


def render(data, context):
    t = context.labels["executive"]

    render_header(t["title"], t["subtitle"])

    psl_source = localize(data["psl"], context.language, LOCALIZABLE_COLUMNS["psl"])
    psl = aggregate_psl(
        period_filter(psl_source, context.year, context.period_id)
    )

    if psl.empty:
        st.warning(t["no_data"])
        return

    monetary_columns = [
        "direct_allocated_cost",
        "indirect_allocated_cost",
        "total_attributed_cost",
        "actual_revenue",
        "budgeted_revenue",
        "service_net_position",
        "cost_efficiency_index",
    ]
    psl = convert_columns(psl, monetary_columns, context.display_rate)
    psl = _normalise_numeric_columns(
        psl,
        [
            "direct_allocated_cost",
            "indirect_allocated_cost",
            "total_attributed_cost",
            "actual_revenue",
        ],
    )
    psl["dashboard_net_position"] = (
        psl["actual_revenue"] - psl["total_attributed_cost"]
    )
    psl["dashboard_margin_pct"] = (
        psl["dashboard_net_position"]
        / psl["actual_revenue"].replace(0, pd.NA)
        * 100
    )

    # ------------------------------------------------------------------
    # Page-level filters
    # ------------------------------------------------------------------
    filter_category, filter_service = st.columns(2)

    category_options = sorted(
        psl["service_category"].dropna().astype(str).unique().tolist()
    )
    with filter_category:
        selected_category = st.selectbox(
            t["filter_category"],
            [t["all_categories"]] + category_options,
            key="executive_category_filter",
        )

    service_source = psl.copy()
    if selected_category != t["all_categories"]:
        service_source = service_source[
            service_source["service_category"] == selected_category
        ]

    service_options = sorted(
        service_source["service_name"].dropna().astype(str).unique().tolist()
    )
    with filter_service:
        selected_service = st.selectbox(
            t["filter_service"],
            [t["all_services"]] + service_options,
            key="executive_service_filter",
        )

    filtered_psl = service_source.copy()
    if selected_service != t["all_services"]:
        filtered_psl = filtered_psl[filtered_psl["service_name"] == selected_service]

    if filtered_psl.empty:
        st.warning(t["no_match"])
        return

    # ------------------------------------------------------------------
    # Data-quality control
    # ------------------------------------------------------------------
    negative_cost_columns = [
        "direct_allocated_cost",
        "indirect_allocated_cost",
        "total_attributed_cost",
    ]
    if (filtered_psl[negative_cost_columns] < 0).any().any():
        st.error(t["negative_costs"])

    # ------------------------------------------------------------------
    # KPI cards, each with a sparkline of the last 12 available periods
    # (see src/dashboard/viz_theme.py — a sparkline is a trend, not a
    # comparison, so a line is the appropriate form here).
    # ------------------------------------------------------------------
    revenue = filtered_psl["actual_revenue"].sum()
    direct = filtered_psl["direct_allocated_cost"].sum()
    indirect = filtered_psl["indirect_allocated_cost"].sum()
    total_cost = filtered_psl["total_attributed_cost"].sum()
    net = revenue - total_cost
    margin = net / revenue * 100 if revenue else 0.0

    spark = _last_12_periods_series(
        psl_source, selected_category, selected_service,
        t["all_categories"], t["all_services"], context.display_rate,
    )

    columns = st.columns(6)
    metrics = [
        (t["kpi_revenue"], compact_number(revenue, context.display_currency, context.language), spark.get("revenue"), "#1F4FD8"),
        (t["kpi_direct"], compact_number(direct, context.display_currency, context.language), spark.get("direct"), "#1F4FD8"),
        (t["kpi_indirect"], compact_number(indirect, context.display_currency, context.language), spark.get("indirect"), "#E08A00"),
        (t["kpi_total_cost"], compact_number(total_cost, context.display_currency, context.language), spark.get("total_cost"), "#E08A00"),
        (t["kpi_net"], compact_number(net, context.display_currency, context.language), spark.get("net"), "#0E9A8B"),
        (t["kpi_margin"], _percentage(margin, context.language), spark.get("margin"), "#0E9A8B"),
    ]
    for column, (label, value, series, colour) in zip(columns, metrics):
        with column:
            kpi_card(label, value)
            if series and len(series) > 1:
                st.plotly_chart(
                    sparkline(series, colour=colour), use_container_width=True,
                    config={"displayModeBar": False}, key=f"spark_{label}",
                )

    # ------------------------------------------------------------------
    # Category share (donut — 4-5 categories, a "share of the whole"
    # question) and top-10 services (horizontal bars — a ranking
    # question). See viz_theme.py for why these two forms and not one
    # chart type for both.
    # ------------------------------------------------------------------
    category = (
        filtered_psl.groupby("service_category", as_index=False, dropna=False)["actual_revenue"]
        .sum()
    )

    left, right = st.columns([1, 1])

    with left:
        pie_data = category[category["actual_revenue"] > 0].copy()
        if pie_data.empty:
            st.info(t["chart_no_revenue"])
        else:
            fig = px.pie(
                pie_data,
                names="service_category",
                values="actual_revenue",
                title=t["chart_revenue_share"],
                hole=0.45,
                color="service_category",
                color_discrete_map=category_colour_map(context.language),
            )
            st.plotly_chart(plotly_layout(fig, height=420), use_container_width=True)

    with right:
        services = (
            filtered_psl.groupby(["service_code", "service_name"], as_index=False)["actual_revenue"]
            .sum()
            .nlargest(10, "actual_revenue")
            .sort_values("actual_revenue")
        )
        fig = px.bar(
            services,
            x="actual_revenue",
            y="service_name",
            orientation="h",
            title=t["chart_top_services"],
            labels={
                "actual_revenue": f"{t['col_revenue']} ({context.display_currency})",
                "service_name": t["col_service"],
            },
            color_discrete_sequence=["#1F4FD8"],
        )
        st.plotly_chart(plotly_layout(fig, height=420), use_container_width=True)
