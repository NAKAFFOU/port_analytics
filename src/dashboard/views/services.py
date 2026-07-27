from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.components import (
    compact_number,
    kpi_card,
    waterfall_chart,
)
from src.dashboard.data import (
    LOCALIZABLE_COLUMNS,
    aggregate_psl,
    convert_columns,
    localize,
    period_filter,
)
from src.dashboard.theme import render_header

_INDENT = "    "  # non-breaking spaces: a plain " " prefix is trimmed on render


def render(data, context):
    t = context.labels["services"]

    render_header(t["title"])

    psl_source = localize(data["psl"], context.language, LOCALIZABLE_COLUMNS["psl"])
    psl = aggregate_psl(
        period_filter(psl_source, context.year, context.period_id)
    )

    # "Family" / "sub-family" filters use the service category / product
    # hierarchy already produced by the allocation pipeline
    # (service_category, service_name) — RECETTE_PF has no separate
    # family/sub-family column of its own (unlike COUT_PAR_FCC).
    filter_cols = st.columns(2)
    families = [context.labels["all"]] + sorted(
        psl["service_category"].dropna().unique().tolist()
    )
    family = filter_cols[0].selectbox(t["family_filter"], families, key="services_family_filter")
    filtered = psl if family == context.labels["all"] else psl[
        psl["service_category"] == family
    ]

    subfamilies = [context.labels["all"]] + sorted(
        filtered["service_name"].dropna().unique().tolist()
    )
    subfamily = filter_cols[1].selectbox(
        t["subfamily_filter"], subfamilies, key="services_subfamily_filter"
    )
    if subfamily != context.labels["all"]:
        filtered = filtered[filtered["service_name"] == subfamily]

    if filtered.empty:
        st.warning(t["no_data"])
        return

    filtered = convert_columns(
        filtered,
        [
            "direct_allocated_cost",
            "indirect_allocated_cost",
            "total_attributed_cost",
            "actual_revenue",
            "budgeted_revenue",
            "service_net_position",
            "cost_efficiency_index",
        ],
        context.display_rate,
    )

    revenue = filtered["actual_revenue"].sum()
    direct = filtered["direct_allocated_cost"].sum()
    indirect = filtered["indirect_allocated_cost"].sum()
    total = filtered["total_attributed_cost"].sum()
    net = filtered["service_net_position"].sum()

    columns = st.columns(4)
    metrics = [
        (t["kpi_revenue"], compact_number(revenue, context.display_currency, context.language)),
        (t["kpi_total_alloc"], compact_number(total, context.display_currency, context.language)),
        (t["kpi_net"], compact_number(net, context.display_currency, context.language)),
        (t["kpi_count"], f"{filtered['service_code'].nunique()}"),
    ]
    for column, (label, value) in zip(columns, metrics):
        with column:
            kpi_card(label, value)

    st.markdown(f"#### {t['matrix_title']}")
    _render_matrix(filtered, t, revenue)

    st.markdown(f"#### {t['waterfall_title']}")
    fig = waterfall_chart(
        labels=[t["waterfall_revenue"], t["waterfall_direct"], t["waterfall_indirect"], t["waterfall_net"]],
        values=[revenue, -direct, -indirect, net],
        measures=["relative", "relative", "relative", "total"],
        title="",
        y_title=f"{context.display_currency}",
        language=context.language,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_matrix(filtered: pd.DataFrame, t: dict, max_revenue: float) -> None:
    """Category subtotal rows, indented product detail rows and a grand
    total — the same shape as a BI matrix visual with row groups, built
    with plain indentation since Streamlit has no native expand/collapse
    table."""
    rows: list[dict] = []
    for category, group in filtered.groupby("service_category", sort=True):
        cat_revenue = group["actual_revenue"].sum()
        cat_direct = group["direct_allocated_cost"].sum()
        cat_indirect = group["indirect_allocated_cost"].sum()
        cat_net = group["service_net_position"].sum()
        cat_margin = (cat_net / cat_revenue * 100) if cat_revenue else 0.0
        rows.append(
            {
                t["col_category"]: category,
                t["col_revenue"]: cat_revenue,
                t["col_direct"]: cat_direct,
                t["col_indirect"]: cat_indirect,
                t["col_net"]: cat_net,
                t["col_margin"]: cat_margin,
            }
        )
        for _, row in group.sort_values("service_net_position", ascending=False).iterrows():
            rows.append(
                {
                    t["col_category"]: _INDENT + str(row["service_name"]),
                    t["col_revenue"]: row["actual_revenue"],
                    t["col_direct"]: row["direct_allocated_cost"],
                    t["col_indirect"]: row["indirect_allocated_cost"],
                    t["col_net"]: row["service_net_position"],
                    t["col_margin"]: row["analytical_margin_pct"],
                }
            )

    total_revenue = filtered["actual_revenue"].sum()
    total_net = filtered["service_net_position"].sum()
    rows.append(
        {
            t["col_category"]: t["total_row"],
            t["col_revenue"]: total_revenue,
            t["col_direct"]: filtered["direct_allocated_cost"].sum(),
            t["col_indirect"]: filtered["indirect_allocated_cost"].sum(),
            t["col_net"]: total_net,
            t["col_margin"]: (total_net / total_revenue * 100) if total_revenue else 0.0,
        }
    )

    table = pd.DataFrame(rows)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            t["col_revenue"]: st.column_config.ProgressColumn(
                t["col_revenue"],
                min_value=0,
                max_value=max(max_revenue, 1.0),
                format="%.0f",
            ),
            t["col_direct"]: st.column_config.NumberColumn(format="%.0f"),
            t["col_indirect"]: st.column_config.NumberColumn(format="%.0f"),
            t["col_net"]: st.column_config.NumberColumn(format="%.0f"),
            t["col_margin"]: st.column_config.NumberColumn(format="%.2f %%"),
        },
    )
