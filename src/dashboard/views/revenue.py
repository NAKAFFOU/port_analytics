from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.components import compact_number, kpi_card, plotly_layout
from src.dashboard.data import (
    LOCALIZABLE_COLUMNS,
    aggregate_psl,
    clean_text_column,
    convert_columns,
    localize,
    period_filter,
    validate_revenue_dashboard_totals,
)
from src.dashboard.theme import render_header
from src.dashboard.viz_theme import category_colour_map


def render(data, context) -> None:
    t = context.labels["revenue"]

    render_header(t["title"])

    # --- Base data. revenue_facts is the single source of truth for every
    # revenue figure on this page (KPI card, filters, charts) — it is
    # never blended with psl at the row level. psl is read only for costs
    # (direct/indirect/total); it is filtered to the same set of products
    # by service_code (a set-membership filter, not a row-level join, so
    # it cannot duplicate or drop a revenue amount). ---
    revenue_source = localize(
        data["revenue_facts"], context.language, LOCALIZABLE_COLUMNS["revenue_facts"]
    )
    revenue_facts = period_filter(revenue_source, context.year, context.period_id)

    psl_source = localize(data["psl"], context.language, LOCALIZABLE_COLUMNS["psl"])
    psl = aggregate_psl(period_filter(psl_source, context.year, context.period_id))

    if revenue_facts.empty:
        st.warning(t["no_data"])
        return

    # --- Page-local filters: FAMILIES / SUB-FAMILIES (= category / product),
    # options and filtering both driven by revenue_facts alone. YEAR/PERIOD/
    # currency/language are global (sidebar) and are not duplicated here. ---
    filter_cols = st.columns(2)
    families = [context.labels["all"]] + sorted(
        revenue_facts["service_category"].dropna().unique().tolist()
    )
    family = filter_cols[0].selectbox(
        t["family_filter"], families, key="revenue_family_filter"
    )
    revenue_filtered = revenue_facts if family == context.labels["all"] else revenue_facts[
        revenue_facts["service_category"] == family
    ]

    subfamilies = [context.labels["all"]] + sorted(
        revenue_filtered["service_name"].dropna().unique().tolist()
    )
    subfamily = filter_cols[1].selectbox(
        t["subfamily_filter"], subfamilies, key="revenue_subfamily_filter"
    )
    if subfamily != context.labels["all"]:
        revenue_filtered = revenue_filtered[revenue_filtered["service_name"] == subfamily]

    if revenue_filtered.empty:
        st.warning(t["no_data"])
        return

    # Costs follow the same product scope as the revenue selection, matched
    # by the stable service_code — never by re-filtering psl independently
    # on localized category/product text.
    in_scope_codes = set(revenue_filtered["service_code"].dropna().unique())
    psl_filtered = psl[psl["service_code"].isin(in_scope_codes)] if not psl.empty else psl

    # --- Currency: convert_columns()/context.display_rate, applied exactly
    # once per column, on the two independent frames — never on a merged
    # or already-converted column. ---
    revenue_filtered = convert_columns(revenue_filtered, ["amount_base"], context.display_rate)
    psl_filtered = convert_columns(
        psl_filtered,
        ["direct_allocated_cost", "indirect_allocated_cost", "total_attributed_cost"],
        context.display_rate,
    )

    kpi_revenue = float(revenue_filtered["amount_base"].sum())
    kpi_allocations = float(psl_filtered["total_attributed_cost"].sum()) if not psl_filtered.empty else 0.0
    kpi_net = kpi_revenue - kpi_allocations
    kpi_count = int(revenue_filtered["service_code"].nunique())

    columns = st.columns(4)
    metrics = [
        (t["kpi_revenue"], compact_number(kpi_revenue, context.display_currency, context.language)),
        (t["kpi_allocations"], compact_number(kpi_allocations, context.display_currency, context.language)),
        (t["kpi_net"], compact_number(kpi_net, context.display_currency, context.language)),
        (t["kpi_count"], str(kpi_count)),
    ]
    for column, (label, value) in zip(columns, metrics):
        with column:
            kpi_card(label, value)

    # --- Category / product breakdown: built once from revenue facts alone
    # (no join to another fact table at detail level -> no duplication
    # risk), then cross-checked against the KPI card (section 3/17
    # control), exactly as the previous tree-based page did. ---
    work = revenue_filtered.copy()
    work["service_category"] = clean_text_column(work["service_category"], t["not_specified"])
    work["service_name"] = clean_text_column(work["service_name"], t["not_specified"])
    category_totals = work.groupby("service_category", as_index=False)["amount_base"].sum()

    if not validate_revenue_dashboard_totals(kpi_revenue, float(category_totals["amount_base"].sum())):
        st.warning(t["consistency_warning"])

    left, right = st.columns([1, 1.3])

    # Donut: "what share of total revenue does each category represent?"
    # (<=5 categories) — see viz_theme.py for why a donut is used here and
    # nowhere a comparison/ranking question is being asked instead.
    with left:
        pie_data = category_totals[category_totals["amount_base"] > 0]
        if pie_data.empty:
            st.info(t["no_data"])
        else:
            fig = px.pie(
                pie_data,
                names="service_category",
                values="amount_base",
                title=t["chart_donut_title"],
                hole=0.45,
                color="service_category",
                color_discrete_map=category_colour_map(context.language),
            )
            st.plotly_chart(plotly_layout(fig, height=430), use_container_width=True)

    # 100%-stacked bars: product mix *within* each category — a
    # comparison across products, so bars (length) rather than a second
    # pie (angle) per Few (2004).
    with right:
        product_totals = work.groupby(["service_category", "service_name"], as_index=False)["amount_base"].sum()
        product_totals["category_total"] = product_totals.groupby("service_category")["amount_base"].transform("sum")
        product_totals[t["axis_share"]] = (
            product_totals["amount_base"] / product_totals["category_total"].replace(0, pd.NA) * 100
        )
        fig = px.bar(
            product_totals,
            x="service_category",
            y=t["axis_share"],
            color="service_name",
            barmode="stack",
            title=t["chart_stacked100_title"],
            labels={"service_category": t["col_category"], "service_name": t["col_product"]},
        )
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(plotly_layout(fig, height=430), use_container_width=True)
