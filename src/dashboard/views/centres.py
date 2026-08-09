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
    t = context.labels["centres"]

    render_header(t["title"])

    occ_source = localize(data["occ"], context.language, LOCALIZABLE_COLUMNS["occ"])
    occ = aggregate_occ(
        period_filter(occ_source, context.year, context.period_id)
    )
    occ = convert_columns(
        occ,
        [
            "total_direct_cost",
            "allocated_ssc_cost",
            "total_occ_cost",
            "budget_direct",
            "cost_variance_abs",
        ],
        context.display_rate,
    )

    total = occ["total_occ_cost"].sum()
    count = occ["centre_code"].nunique()
    average = total / count if count else 0

    columns = st.columns(3)
    for column, label, value in [
        (columns[0], t["kpi_total"], compact_number(total, context.display_currency, context.language)),
        (columns[1], t["kpi_count"], str(count)),
        (columns[2], t["kpi_avg"], compact_number(average, context.display_currency, context.language)),
    ]:
        with column:
            kpi_card(label, value)

    occ["share_pct"] = occ["total_occ_cost"] / total * 100 if total else 0

    left, middle, right = st.columns([0.9, 1.35, 1.1])
    with left:
        fig = px.pie(
            occ,
            values="total_occ_cost",
            names="centre_name",
            title=t["chart_pie"],
            hole=0.18,
        )
        st.plotly_chart(plotly_layout(fig, 470), use_container_width=True)

    with middle:
        table = occ[
            [
                "centre_code",
                "centre_name",
                "total_direct_cost",
                "allocated_ssc_cost",
                "total_occ_cost",
                "share_pct",
            ]
        ].sort_values("total_occ_cost", ascending=False).rename(
            columns={
                "centre_code": t["col_code"],
                "centre_name": t["col_name"],
                "total_direct_cost": t["col_direct"],
                "allocated_ssc_cost": t["col_indirect"],
                "total_occ_cost": t["col_total"],
                "share_pct": t["col_pct"],
            }
        )
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            height=470,
            column_config={
                t["col_pct"]: st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.2f %%",
                ),
            },
        )

    with right:
        fig = px.bar(
            occ.sort_values("total_occ_cost"),
            x="total_occ_cost",
            y="centre_name",
            orientation="h",
            title=t["chart_bar"],
            labels={"total_occ_cost": t["col_total"], "centre_name": t["col_name"]},
        )
        st.plotly_chart(plotly_layout(fig, 470), use_container_width=True)

    _render_family_breakdown(data, context)


def _render_family_breakdown(data, context) -> None:
    """Cost breakdown by FAMILLE/SOUS_FAMILLE (COUT_PAR_FCC) or
    FAMILLES/SOUS_FAMILLES (CHARGES_REPARTIES), harmonised into the same
    `family`/`subfamily` fields at ingestion. Reads oracle_view_facts
    directly since occ_indicators does not carry this dimension. Silently
    omitted when running in DEMO mode or when the source rows have no
    family recorded (e.g. head-office cost lines)."""
    t = context.labels["centres"]
    facts = data.get("oracle_facts")
    if facts is None or facts.empty:
        return
    facts = localize(facts, context.language, LOCALIZABLE_COLUMNS["oracle_facts"])

    cost_facts = facts[facts["measure_type"] == "COST_CENTRE_COST"].copy()
    cost_facts = cost_facts[cost_facts["family"].notna() & (cost_facts["family"] != "")]
    if cost_facts.empty:
        return

    cost_facts = period_filter(cost_facts, context.year, context.period_id)
    if cost_facts.empty:
        return
    cost_facts = convert_columns(cost_facts, ["amount_base"], context.display_rate)
    cost_facts["subfamily"] = cost_facts["subfamily"].fillna(t["col_subfamily"])

    st.markdown(f"#### {t['family_breakdown_title']}")
    filter_cols = st.columns(2)
    families = [context.labels["all"]] + sorted(cost_facts["family"].dropna().unique().tolist())
    family = filter_cols[0].selectbox(t["family_filter"], families, key="centres_family_filter")
    filtered = cost_facts if family == context.labels["all"] else cost_facts[cost_facts["family"] == family]

    subfamilies = [context.labels["all"]] + sorted(filtered["subfamily"].dropna().unique().tolist())
    subfamily = filter_cols[1].selectbox(t["subfamily_filter"], subfamilies, key="centres_subfamily_filter")
    if subfamily != context.labels["all"]:
        filtered = filtered[filtered["subfamily"] == subfamily]

    if filtered.empty:
        return
    grouped = filtered.groupby(["family", "subfamily"], as_index=False)["amount_base"].sum()

    left, right = st.columns([1.3, 1])
    with left:
        fig = px.bar(
            grouped.sort_values("amount_base"),
            x="amount_base",
            y="family",
            color="subfamily",
            orientation="h",
            title=t["chart_family_bar"],
            labels={
                "amount_base": t["col_amount"],
                "family": t["col_family"],
                "subfamily": t["col_subfamily"],
            },
        )
        st.plotly_chart(plotly_layout(fig, 420), use_container_width=True)
    with right:
        table = grouped.sort_values("amount_base", ascending=False).rename(
            columns={
                "family": t["col_family"],
                "subfamily": t["col_subfamily"],
                "amount_base": t["col_amount"],
            }
        )
        st.dataframe(table, use_container_width=True, hide_index=True, height=420)
