from __future__ import annotations

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


def render(data, context):
    t = context.labels["budgets"]

    render_header(t["title"])

    occ_source = localize(data["occ"], context.language, LOCALIZABLE_COLUMNS["occ"])
    occ = aggregate_occ(
        period_filter(occ_source, context.year, context.period_id)
    )
    if occ.empty or "budget_direct" not in occ or occ["budget_direct"].isna().all():
        st.warning(t["no_budget"])
        if not occ.empty:
            st.dataframe(
                occ[["centre_code", "centre_name", "total_occ_cost"]],
                use_container_width=True,
                hide_index=True,
            )
        return

    occ = convert_columns(
        occ,
        ["total_direct_cost", "budget_direct", "cost_variance_abs"],
        context.display_rate,
    )
    actual = occ["total_direct_cost"].sum()
    budget = occ["budget_direct"].sum()
    variance = actual - budget
    consumption = actual / budget if budget else 0

    columns = st.columns(4)
    metrics = [
        (t["kpi_actual"], compact_number(actual, context.display_currency, context.language)),
        (t["kpi_budget"], compact_number(budget, context.display_currency, context.language)),
        (t["kpi_variance"], compact_number(variance, context.display_currency, context.language)),
        (t["kpi_consumption"], f"{consumption:.2%}"),
    ]
    for column, (label, value) in zip(columns, metrics):
        with column:
            kpi_card(label, value)

    comparison = occ.melt(
        id_vars=["centre_name"],
        value_vars=["total_direct_cost", "budget_direct"],
        var_name=t["measure"],
        value_name=t["amount"],
    )
    left, right = st.columns(2)
    with left:
        fig = px.bar(
            comparison,
            x="centre_name",
            y=t["amount"],
            color=t["measure"],
            barmode="group",
            title=t["chart_vs_title"],
        )
        st.plotly_chart(plotly_layout(fig), use_container_width=True)

    with right:
        fig = px.bar(
            occ.sort_values("cost_variance_abs"),
            x="cost_variance_abs",
            y="centre_name",
            orientation="h",
            title=t["chart_variance_title"],
        )
        st.plotly_chart(plotly_layout(fig), use_container_width=True)
