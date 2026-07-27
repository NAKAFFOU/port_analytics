from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import streamlit as st

from src.common.config import base_currency, get_settings
from src.dashboard.data import get_display_rate
from src.dashboard.i18n import tr
from src.dashboard.theme import render_logo


@dataclass(frozen=True)
class DashboardContext:
    language: str
    year: int
    period_id: str
    display_currency: str
    display_rate: float
    rate_date: date
    labels: dict


def sidebar_context(periods):
    settings = get_settings()
    dashboard_settings = settings["dashboard"]

    render_logo()
    st.sidebar.markdown("### Port Analytics")

    default_language = dashboard_settings.get("language", "en")
    lang_options = ["English", "Français"]
    default_index = 1 if default_language == "fr" else 0
    lang_choice = st.sidebar.radio(
        "🌐",
        lang_options,
        index=default_index,
        horizontal=True,
        key="language_toggle",
    )
    language = "fr" if lang_choice == "Français" else "en"
    labels = tr(language)

    years = sorted(periods["year"].astype(int).unique().tolist())
    year = st.sidebar.selectbox(labels["year"], years, index=len(years) - 1)
    year_periods = periods[
        periods["year"].astype(int) == int(year)
    ].copy()

    annual_only = (
        len(year_periods) == 1
        and "period_granularity" in year_periods.columns
        and year_periods.iloc[0]["period_granularity"] == "YEAR"
    )
    options = (
        year_periods["period_id"].tolist()
        if annual_only
        else ["ALL"] + year_periods["period_id"].tolist()
    )
    period_id = st.sidebar.selectbox(
        labels["period"],
        options,
        format_func=lambda value: (
            labels["all_year"]
            if value == "ALL"
            else year_periods.loc[
                year_periods["period_id"] == value, "period_label"
            ].iloc[0]
        ),
    )

    allowed = settings["currency"].get(
        "allowed_display_currencies", [base_currency()]
    )
    default = settings["currency"].get(
        "default_display_currency", base_currency()
    )
    display_currency = st.sidebar.selectbox(
        labels["currency"], allowed, index=allowed.index(default)
    )

    if period_id == "ALL":
        rate_date = date(int(year), 12, 31)
    else:
        row = year_periods[year_periods["period_id"] == period_id].iloc[0]
        rate_date = date.fromisoformat(row["period_end_date"])

    try:
        display_rate = get_display_rate(display_currency, rate_date)
    except Exception as exc:
        st.sidebar.error(f"FX: {exc}")
        display_currency = base_currency()
        display_rate = 1.0

    st.sidebar.caption(
        labels["base_info"].format(
            base_currency(), display_currency, rate_date.isoformat()
        )
    )
    return DashboardContext(
        language=language,
        year=int(year),
        period_id=period_id,
        display_currency=display_currency,
        display_rate=display_rate,
        rate_date=rate_date,
        labels=labels,
    )
