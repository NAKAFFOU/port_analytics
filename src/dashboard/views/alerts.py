from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.dashboard.data import period_filter
from src.dashboard.theme import render_header


def render(data, context):
    t = context.labels["alerts"]

    render_header(t["title"])

    alerts = period_filter(data["alerts"], context.year, context.period_id)
    merged = alerts.merge(data["actions"], on="rule_name", how="left")

    severity_order = {
        "CRITICAL": 0,
        "PRIORITY_REVIEW": 1,
        "WARNING": 2,
        "DATA_QUALITY": 3,
    }

    if merged.empty:
        st.success(t["no_alerts"])
    else:
        merged["rank"] = merged["severity"].map(severity_order).fillna(9)
        merged = merged.sort_values(["rank", "period_id", "entity_code"])

        summary = (
            merged.groupby("severity", as_index=False)
            .size()
            .rename(columns={"size": t["count"]})
        )
        fig = px.bar(
            summary,
            x="severity",
            y=t["count"],
            title=t["chart_title"],
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            merged[
                [
                    "severity",
                    "entity_type",
                    "entity_code",
                    "period_id",
                    "rule_name",
                    "indicator_value",
                    "threshold_value",
                    "description",
                    "recommended_action",
                    "escalation_path",
                    "response_timeframe",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(t["data_quality_title"])
    if data["issues"].empty:
        st.info(t["no_issues"])
    else:
        st.dataframe(data["issues"], use_container_width=True, hide_index=True)

    st.markdown(t["batches_title"])
    if data["batches"].empty:
        st.info(t["no_batches"])
    else:
        st.dataframe(data["batches"], use_container_width=True, hide_index=True)
