from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.components import allocation_sankey, plotly_layout
from src.dashboard.data import LOCALIZABLE_COLUMNS, convert_columns, localize, period_filter
from src.dashboard.theme import render_header


def render(data, context):
    t = context.labels["allocations"]

    render_header(t["title"])

    alloc2_source = localize(data["alloc2"], context.language, LOCALIZABLE_COLUMNS["alloc2"])
    allocation = period_filter(alloc2_source, context.year, context.period_id)

    filters = st.columns(2)
    categories = [context.labels["all"]] + sorted(
        allocation["service_category"].dropna().unique().tolist()
    )
    category = filters[0].selectbox(context.labels["category"], categories)
    if category != context.labels["all"]:
        allocation = allocation[allocation["service_category"] == category]

    services = [context.labels["all"]] + sorted(
        allocation["service_name"].dropna().unique().tolist()
    )
    service = filters[1].selectbox(context.labels["service"], services)
    if service != context.labels["all"]:
        allocation = allocation[allocation["service_name"] == service]

    allocation = convert_columns(
        allocation,
        ["direct_allocated_cost", "indirect_allocated_cost", "total_allocated_cost"],
        context.display_rate,
    )

    service_totals = (
        allocation.groupby(
            ["destination_psl", "service_name", "service_category"], as_index=False
        )[["direct_allocated_cost", "indirect_allocated_cost", "total_allocated_cost"]]
        .sum()
    )
    service_totals[t["direct_pct"]] = (
        service_totals["direct_allocated_cost"]
        / service_totals["total_allocated_cost"].replace(0, pd.NA)
        * 100
    )
    service_totals[t["indirect_pct"]] = (
        service_totals["indirect_allocated_cost"]
        / service_totals["total_allocated_cost"].replace(0, pd.NA)
        * 100
    )

    left, right = st.columns([1.45, 1])
    with left:
        stacked = service_totals.melt(
            id_vars=["service_name"],
            value_vars=[t["direct_pct"], t["indirect_pct"]],
            var_name=t["alloc_type"],
            value_name=t["percentage"],
        )
        fig = px.bar(
            stacked,
            x="service_name",
            y=t["percentage"],
            color=t["alloc_type"],
            barmode="stack",
            title=t["chart_stacked_title"],
            labels={"service_name": t["col_service"]},
        )
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(plotly_layout(fig, 430), use_container_width=True)

    with right:
        matrix = (
            service_totals.pivot_table(
                index=["service_category", "service_name"],
                values=["direct_allocated_cost", "indirect_allocated_cost"],
                aggfunc="sum",
            )
            .reset_index()
            .rename(
                columns={
                    "service_category": t["col_category"],
                    "service_name": t["col_service"],
                    "direct_allocated_cost": t["col_direct"],
                    "indirect_allocated_cost": t["col_indirect"],
                }
            )
        )
        st.markdown(t["matrix_title"])
        st.dataframe(matrix, use_container_width=True, hide_index=True, height=390)

    st.markdown(t["flow_title"])
    st.plotly_chart(allocation_sankey(allocation), use_container_width=True)
