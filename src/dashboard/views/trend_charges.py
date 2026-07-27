from __future__ import annotations

import streamlit as st

from src.dashboard.components import annual_stacked_area_with_total, kpi_card, compact_number
from src.dashboard.data import (
    LOCALIZABLE_COLUMNS,
    annual_trend_by_dimension,
    convert_columns,
    localize,
    resolve_trend_scope,
)
from src.dashboard.theme import render_header
from src.dashboard.viz_theme import series_colour_map


def render(data, context):
    """06_Evolution des charges de 2020 à 2026 — stacked areas by family
    (or sub-family once a family is selected), Top-N + Others, with a
    total-charges line overlaid. Reuses the exact multi-year trend logic
    already used elsewhere in the dashboard
    (data.py::annual_trend_by_dimension)."""
    t = context.labels["trend_charges"]

    render_header(t["title"])

    psl_source = localize(data["psl"], context.language, LOCALIZABLE_COLUMNS["psl"])

    filter_cols = st.columns(2)
    families = [context.labels["all"]] + sorted(
        psl_source["service_category"].dropna().unique().tolist()
    )
    family = filter_cols[0].selectbox(t["family_filter"], families, key="trend_charges_family_filter")
    scoped = psl_source if family == context.labels["all"] else psl_source[
        psl_source["service_category"] == family
    ]
    subfamilies = [context.labels["all"]] + sorted(
        scoped["service_name"].dropna().unique().tolist()
    )
    subfamily = filter_cols[1].selectbox(t["subfamily_filter"], subfamilies, key="trend_charges_subfamily_filter")

    trend_source, dimension_column = resolve_trend_scope(
        psl_source, family, subfamily, context.labels["all"]
    )

    if trend_source.empty:
        st.warning(t["no_data"])
        return

    yearly = trend_source.copy()
    yearly["reporting_year"] = yearly["period_id"].str.slice(0, 4).astype(int)
    yearly = convert_columns(yearly, ["total_attributed_cost"], context.display_rate)
    by_year = yearly.groupby("reporting_year")["total_attributed_cost"].sum().sort_index()

    if by_year.empty:
        st.warning(t["no_data"])
        return

    total_period = float(by_year.sum())
    first_value, last_value = float(by_year.iloc[0]), float(by_year.iloc[-1])
    variation_pct = ((last_value - first_value) / abs(first_value) * 100) if first_value else 0.0
    # Charges: "best" reads as the lowest-charge year, "worst" as the
    # highest-charge year (see i18n.py trend_charges section).
    best_year = int(by_year.idxmin())
    worst_year = int(by_year.idxmax())

    columns = st.columns(4)
    metrics = [
        (t["kpi_total_period"], compact_number(total_period, context.display_currency, context.language)),
        (t["kpi_variation_pct"], f"{variation_pct:+.1f} %"),
        (t["kpi_best_year"], str(best_year)),
        (t["kpi_worst_year"], str(worst_year)),
    ]
    for column, (label, value) in zip(columns, metrics):
        with column:
            kpi_card(label, value)

    trend = annual_trend_by_dimension(
        trend_source,
        dimension_column=dimension_column,
        value_column="total_attributed_cost",
        year=context.year,
        period_id=context.period_id,
        other_label=t["other_label"],
        not_specified_label=t["not_specified"],
    )
    if trend.empty:
        st.info(t["no_data"])
        return

    trend = convert_columns(trend, ["total_attributed_cost"], context.display_rate)
    series_names = [name for name in trend[dimension_column].unique().tolist() if name != t["other_label"]]
    colour_map = series_colour_map(series_names, other_label=t["other_label"])

    fig = annual_stacked_area_with_total(
        trend,
        dimension_column=dimension_column,
        value_column="total_attributed_cost",
        x_title=t["axis_year"],
        y_title=f"{t['axis_charges']} ({context.display_currency})",
        legend_title=t["family_filter"] if dimension_column == "service_category" else t["subfamily_filter"],
        total_label=t["total_label"],
        language=context.language,
        height=460,
        color_map=colour_map,
    )
    st.markdown(f"#### {t['chart_title']}")
    st.plotly_chart(fig, use_container_width=True)
