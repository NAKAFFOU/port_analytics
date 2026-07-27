from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SYMBOLS = {
    "GBP": "£",
    "EUR": "€",
    "USD": "$",
    "XOF": "CFA ",
}


def compact_number(value: float, currency: str, language: str = "fr") -> str:
    # `value or 0` alone does not catch NaN: bool(float("nan")) is True, so
    # a NaN would fall through every suffix comparison (NaN comparisons are
    # always False) and be formatted literally as the string "nan".
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0.0
    else:
        value = float(value)
    symbol = SYMBOLS.get(currency, f"{currency} ")
    absolute = abs(value)

    if language == "fr":
        suffixes = [
            (1_000_000_000, "Md"),
            (1_000_000, "M"),
            (1_000, "k"),
        ]
        decimal = ","
    else:
        suffixes = [
            (1_000_000_000, "B"),
            (1_000_000, "M"),
            (1_000, "K"),
        ]
        decimal = "."

    for divisor, suffix in suffixes:
        if absolute >= divisor:
            rendered = f"{value / divisor:,.2f}".replace(",", " ")
            if language == "fr":
                rendered = rendered.replace(".", decimal)
            return f"{symbol}{rendered}{suffix}"

    rendered = f"{value:,.0f}"
    if language == "fr":
        rendered = rendered.replace(",", " ")
    return f"{symbol}{rendered}"


def kpi_card(
    label: str,
    value: str,
    note: str | None = None,
) -> None:
    note_html = (
        f'<div class="pa-kpi-note">{note}</div>'
        if note
        else ""
    )
    st.markdown(
        f"""
        <div class="pa-kpi">
          <div class="pa-kpi-label">{label}</div>
          <div class="pa-kpi-value">{value}</div>
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def plotly_layout(fig, height: int = 390):
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=55, b=30),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(family="Arial", color="#303642"),
        title_font=dict(size=17),
        legend_title_text="",
    )
    return fig


def allocation_sankey(
    allocation: pd.DataFrame,
    amount_column: str = "total_allocated_cost",
):
    if allocation.empty:
        return go.Figure()

    grouped = (
        allocation.groupby(
            ["source_name", "service_category", "service_name"],
            as_index=False,
        )[amount_column]
        .sum()
    )

    root = "Total Allocated Cost"
    occ_nodes = sorted(grouped["source_name"].unique())
    category_nodes = sorted(grouped["service_category"].unique())
    service_nodes = sorted(grouped["service_name"].unique())
    labels = [root] + occ_nodes + category_nodes + service_nodes
    index = {label: position for position, label in enumerate(labels)}

    sources: list[int] = []
    targets: list[int] = []
    values: list[float] = []

    occ_totals = grouped.groupby("source_name")[amount_column].sum()
    for occ, value in occ_totals.items():
        sources.append(index[root])
        targets.append(index[occ])
        values.append(float(value))

    occ_cat = grouped.groupby(
        ["source_name", "service_category"]
    )[amount_column].sum()
    for (occ, category), value in occ_cat.items():
        sources.append(index[occ])
        targets.append(index[category])
        values.append(float(value))

    cat_service = grouped.groupby(
        ["service_category", "service_name"]
    )[amount_column].sum()
    for (category, service), value in cat_service.items():
        sources.append(index[category])
        targets.append(index[service])
        values.append(float(value))

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=15,
                thickness=15,
                line=dict(color="#d4d9e4", width=0.5),
                label=labels,
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
            ),
        )
    )
    return plotly_layout(fig, height=520)


def decomposition_sankey(
    frame: pd.DataFrame,
    level1_column: str,
    level2_column: str,
    value_column: str,
    root_label: str,
    height: int = 420,
):
    """Two-level decomposition flow (root -> level1 -> level2), in the
    spirit of a BI "decomposition tree": every node's width reflects its
    share of the metric. Sankey link values cannot be negative, so a
    node contributing a net deficit is floored at 0 for the flow width
    only — its true (signed) value is still shown on hover."""
    if frame.empty:
        return go.Figure()

    grouped = frame.groupby([level1_column, level2_column], as_index=False)[value_column].sum()

    level1_nodes = sorted(grouped[level1_column].unique())
    level2_nodes = sorted(grouped[level2_column].unique())
    labels = [root_label] + level1_nodes + level2_nodes
    index = {label: position for position, label in enumerate(labels)}

    sources: list[int] = []
    targets: list[int] = []
    values: list[float] = []
    hover: list[str] = []

    level1_totals = grouped.groupby(level1_column)[value_column].sum()
    for name, value in level1_totals.items():
        sources.append(index[root_label])
        targets.append(index[name])
        values.append(max(float(value), 0.0))
        hover.append(f"{name}: {value:,.0f}")

    for _, row in grouped.iterrows():
        sources.append(index[row[level1_column]])
        targets.append(index[row[level2_column]])
        values.append(max(float(row[value_column]), 0.0))
        hover.append(f"{row[level2_column]}: {row[value_column]:,.0f}")

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=15,
                thickness=15,
                line=dict(color="#d4d9e4", width=0.5),
                label=labels,
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
            ),
        )
    )
    return plotly_layout(fig, height=height)


# streamlit-echarts (the library asked for in the original brief for a
# "decomposition tree") registers itself with Streamlit's legacy v1
# component API. It hard-crashes at import time under the Streamlit
# version this project runs (1.58, components-v2 only) with
# `StreamlitAPIException: ... must be declared in pyproject.toml with
# asset_dir`. Rather than depend on a package that cannot even be
# imported, this uses go.Icicle — a left-to-right hierarchical
# decomposition chart built into Plotly (already a project dependency),
# driven by Streamlit's native `st.plotly_chart(..., on_select="rerun")`
# click events. No extra dependency, no external JS runtime.
ACTIVE_BRANCH_COLOR = "#1495F5"
INACTIVE_BRANCH_COLOR = "#AFCBEE"
ROOT_COLOR = "#142B9B"


def revenue_decomposition_icicle(
    flattened: pd.DataFrame,
    active_id: str | None = None,
    height: int = 560,
):
    """flattened must have columns id/label/parent/value/signed_value, as
    produced by data.py::flatten_hierarchy_for_icicle. `branchvalues="total"`
    requires each parent's value to equal the sum of its children's — true
    here because every level is built with an exact-remainder "Others"
    node (see data.py::_top_n_with_other)."""
    if flattened.empty:
        return go.Figure()

    def _is_active(node_id: str) -> bool:
        if not active_id:
            return False
        return node_id == active_id or active_id.startswith(f"{node_id} / ") or node_id.startswith(f"{active_id} / ")

    colors = [
        ACTIVE_BRANCH_COLOR if _is_active(node_id) else INACTIVE_BRANCH_COLOR
        for node_id in flattened["id"]
    ]
    # The root (depth 0) keeps a distinct colour regardless of selection.
    colors = [
        ROOT_COLOR if depth == 0 else colour
        for depth, colour in zip(flattened["depth"], colors)
    ]

    fig = go.Figure(
        go.Icicle(
            ids=flattened["id"].tolist(),
            labels=flattened["label"].tolist(),
            parents=flattened["parent"].tolist(),
            values=flattened["value"].tolist(),
            branchvalues="total",
            tiling=dict(orientation="h"),
            marker=dict(colors=colors, line=dict(width=1, color="white")),
            customdata=flattened["signed_value"].tolist(),
            hovertemplate="<b>%{label}</b><br>%{customdata:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=height)
    return fig


def _apply_locale_numbers(fig, language: str):
    """Plotly's `layout.separators` is a 2-char "[decimal][thousands]"
    string (d3-format); French convention is comma-decimal + space-
    thousands, English is the library default (".," ) so it is left
    untouched."""
    if language == "fr":
        fig.update_layout(separators=", ")
    return fig


def annual_stacked_area(
    trend: pd.DataFrame,
    dimension_column: str,
    value_column: str,
    x_title: str,
    y_title: str,
    legend_title: str,
    language: str = "fr",
    height: int = 380,
):
    """Annual evolution of a cost/amount measure, stacked by
    `dimension_column` (family, or sub-family once a family filter narrows
    the page). Built from the long-format output of
    data.py::annual_trend_by_dimension. Values are floored at 0 for the
    stack's visual height only (costs are already stored non-negative by
    the ingestion pipeline; this is a defensive guard, not a sign
    correction) — the true value is still shown on hover."""
    if trend.empty:
        return go.Figure()

    pivot = trend.pivot_table(
        index="reporting_year",
        columns=dimension_column,
        values=value_column,
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()

    fig = go.Figure()
    for column in pivot.columns:
        series = pivot[column]
        fig.add_trace(
            go.Scatter(
                x=series.index.tolist(),
                y=[max(float(v), 0.0) for v in series.tolist()],
                customdata=series.tolist(),
                name=str(column),
                mode="lines",
                stackgroup="one",
                hovertemplate=f"<b>{column}</b><br>%{{x}}: %{{customdata:,.0f}}<extra></extra>",
            )
        )
    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
        legend_title_text=legend_title,
    )
    fig.update_xaxes(dtick=1, tickformat="d")
    fig = _apply_locale_numbers(fig, language)
    return plotly_layout(fig, height=height)


def sparkline(values: list[float], colour: str = "#1F4FD8", height: int = 46):
    """Minimal trend line for a KPI card: no axes, no gridlines, no
    ticks — just the shape of the last 12 available periods. Used by
    01_Vue Exécutive_Synthèse under each KPI card (see
    src/dashboard/viz_theme.py for the "why bars vs line" principle; a
    sparkline is a trend, not a comparison, so a line is appropriate)."""
    fig = go.Figure(
        go.Scatter(
            x=list(range(len(values))),
            y=values,
            mode="lines",
            line=dict(width=2, color=colour),
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(l=2, r=2, t=2, b=2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    fig.update_yaxes(visible=False, showgrid=False, zeroline=False)
    return fig


def waterfall_chart(
    labels: list[str],
    values: list[float],
    measures: list[str],
    title: str,
    y_title: str,
    language: str = "fr",
    height: int = 420,
):
    """Revenue -> -Direct costs -> -Indirect costs -> Net result, using
    Plotly's native go.Waterfall (`measure` is "relative" for each step
    and "total" for the final net-result bar)."""
    fig = go.Figure(
        go.Waterfall(
            x=labels,
            y=values,
            measure=measures,
            connector=dict(line=dict(color="#B0B0B0", width=1)),
            increasing=dict(marker=dict(color="#0E9A8B")),
            decreasing=dict(marker=dict(color="#E08A00")),
            totals=dict(marker=dict(color="#1F4FD8")),
        )
    )
    fig.update_layout(title=title, yaxis_title=y_title, showlegend=False)
    fig = _apply_locale_numbers(fig, language)
    return plotly_layout(fig, height=height)


def annual_stacked_area_with_total(
    trend: pd.DataFrame,
    dimension_column: str,
    value_column: str,
    x_title: str,
    y_title: str,
    legend_title: str,
    total_label: str,
    language: str = "fr",
    height: int = 400,
    color_map: dict[str, str] | None = None,
):
    """Same stacked-area evolution as annual_stacked_area, with a total
    line overlaid on top (sum across every series for that year) so the
    overall trend is readable at a glance without summing the stack
    visually."""
    if trend.empty:
        return go.Figure()

    pivot = trend.pivot_table(
        index="reporting_year",
        columns=dimension_column,
        values=value_column,
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()

    fig = go.Figure()
    for column in pivot.columns:
        series = pivot[column]
        colour = (color_map or {}).get(str(column))
        fig.add_trace(
            go.Scatter(
                x=series.index.tolist(),
                y=[max(float(v), 0.0) for v in series.tolist()],
                customdata=series.tolist(),
                name=str(column),
                mode="lines",
                stackgroup="one",
                line=dict(color=colour) if colour else None,
                hovertemplate=f"<b>{column}</b><br>%{{x}}: %{{customdata:,.0f}}<extra></extra>",
            )
        )
    totals = pivot.sum(axis=1)
    fig.add_trace(
        go.Scatter(
            x=totals.index.tolist(),
            y=totals.tolist(),
            name=total_label,
            mode="lines+markers",
            line=dict(color="#142B9B", width=3, dash="dot"),
            hovertemplate=f"<b>{total_label}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title=x_title, yaxis_title=y_title, legend_title_text=legend_title)
    fig.update_xaxes(dtick=1, tickformat="d")
    fig = _apply_locale_numbers(fig, language)
    return plotly_layout(fig, height=height)


def annual_multi_line(
    trend: pd.DataFrame,
    dimension_column: str,
    value_column: str,
    x_title: str,
    y_title: str,
    legend_title: str,
    language: str = "fr",
    height: int = 380,
):
    """Annual evolution of net result (which, unlike costs, may legitimately
    be negative), one line per `dimension_column` value — built from the
    same long-format trend shape as annual_stacked_area. Signs are never
    altered here."""
    if trend.empty:
        return go.Figure()

    pivot = trend.pivot_table(
        index="reporting_year",
        columns=dimension_column,
        values=value_column,
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()

    fig = go.Figure()
    for column in pivot.columns:
        series = pivot[column]
        fig.add_trace(
            go.Scatter(
                x=series.index.tolist(),
                y=series.tolist(),
                name=str(column),
                mode="lines+markers",
                hovertemplate=f"<b>{column}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>",
            )
        )
    fig.add_hline(y=0, line_width=1, line_color="#B0B0B0")
    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
        legend_title_text=legend_title,
    )
    fig.update_xaxes(dtick=1, tickformat="d")
    fig = _apply_locale_numbers(fig, language)
    return plotly_layout(fig, height=height)
