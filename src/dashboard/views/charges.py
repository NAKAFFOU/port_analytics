from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.components import compact_number, kpi_card, plotly_layout
from src.dashboard.data import (
    LOCALIZABLE_COLUMNS,
    aggregate_occ,
    convert_columns,
    localize,
    period_filter,
)
from src.dashboard.theme import render_header
from src.dashboard.viz_theme import COST_TYPE_COLOURS


def render(data, context):
    """04_Analyses des charges — direct vs indirect cost, by cost centre.
    Backed by occ_indicators (already computed by the allocation
    pipeline); this page only reads and charts it, it never recomputes
    an allocation."""
    t = context.labels["charges"]

    render_header(t["title"])

    occ_source = localize(data["occ"], context.language, LOCALIZABLE_COLUMNS["occ"])
    occ = aggregate_occ(
        period_filter(occ_source, context.year, context.period_id)
    )
    if occ.empty:
        st.warning(t["no_data"])
        return

    occ = convert_columns(
        occ,
        ["total_direct_cost", "allocated_ssc_cost", "total_occ_cost"],
        context.display_rate,
    )

    total_direct = occ["total_direct_cost"].sum()
    total_indirect = occ["allocated_ssc_cost"].sum()
    total = total_direct + total_indirect
    count = occ["centre_code"].nunique()

    columns = st.columns(4)
    metrics = [
        (t["kpi_total"], compact_number(total, context.display_currency, context.language)),
        (t["kpi_direct"], compact_number(total_direct, context.display_currency, context.language)),
        (t["kpi_indirect"], compact_number(total_indirect, context.display_currency, context.language)),
        (t["kpi_count"], str(count)),
    ]
    for column, (label, value) in zip(columns, metrics):
        with column:
            kpi_card(label, value)

    left, right = st.columns([1.4, 1])

    # Grouped (not stacked) bars: comparing direct vs indirect *per
    # centre* is a comparison-across-items question, so bars — never a
    # pie per centre (see viz_theme.py).
    with left:
        grouped = occ[["centre_name", "total_direct_cost", "allocated_ssc_cost"]].melt(
            id_vars="centre_name",
            value_vars=["total_direct_cost", "allocated_ssc_cost"],
            var_name="cost_type",
            value_name="amount",
        )
        grouped["cost_type"] = grouped["cost_type"].map(
            {"total_direct_cost": t["direct"], "allocated_ssc_cost": t["indirect"]}
        )
        colour_map = {t["direct"]: COST_TYPE_COLOURS["direct"], t["indirect"]: COST_TYPE_COLOURS["indirect"]}
        fig = px.bar(
            grouped.sort_values("centre_name"),
            x="centre_name",
            y="amount",
            color="cost_type",
            barmode="group",
            title=t["chart_grouped_title"],
            labels={"centre_name": t["col_centre"], "amount": t["col_amount"], "cost_type": t["cost_type"]},
            color_discrete_map=colour_map,
        )
        st.plotly_chart(plotly_layout(fig, height=440), use_container_width=True)

    # Donut: the single "what share of total charges is direct vs
    # indirect?" question, 2 categories — the one case this page uses a
    # pie form for.
    with right:
        share = pd.DataFrame(
            {"cost_type": [t["direct"], t["indirect"]], "amount": [total_direct, total_indirect]}
        )
        share = share[share["amount"] > 0]
        if share.empty:
            st.info(t["no_data"])
        else:
            colour_map = {t["direct"]: COST_TYPE_COLOURS["direct"], t["indirect"]: COST_TYPE_COLOURS["indirect"]}
            fig = px.pie(
                share,
                names="cost_type",
                values="amount",
                title=t["chart_donut_title"],
                hole=0.45,
                color="cost_type",
                color_discrete_map=colour_map,
            )
            st.plotly_chart(plotly_layout(fig, height=440), use_container_width=True)
