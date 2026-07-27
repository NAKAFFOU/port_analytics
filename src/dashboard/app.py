from __future__ import annotations

import streamlit as st

from src.common.config import get_settings
from src.dashboard.context import sidebar_context
from src.dashboard.data import load_dashboard_data
from src.dashboard.theme import apply_dashboard_theme
from src.dashboard.views import (
    charges,
    executive,
    revenue,
    services,
    trend_charges,
    trend_result,
)

settings = get_settings()
st.set_page_config(
    page_title=settings["dashboard"]["page_title"],
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_dashboard_theme()

data = load_dashboard_data()
if data["periods"].empty or data["occ"].empty or data["psl"].empty:
    st.error(
        "Aucun résultat analytique. Exécutez : "
        "`python -m src.cli run-demo`"
    )
    st.stop()

context = sidebar_context(data["periods"])
page_names = context.labels["pages"]

page = st.sidebar.radio(
    "Pages",
    [
        page_names["executive"],
        page_names["services"],
        page_names["revenue"],
        page_names["charges"],
        page_names["trend_result"],
        page_names["trend_charges"],
    ],
)

# Exactly six pages exposed in the navigation (see docs/DASHBOARD_DESIGN.md).
# Cost Centres, Allocation Analysis, Budget Monitoring and Decision Alerts
# were removed from this routing table on purpose — their backend logic
# (two-phase allocation, alert engine, budget handling) is still computed
# and stored every pipeline run; only the dedicated Streamlit pages for
# them (src/dashboard/views/centres.py, allocations.py, budgets.py,
# alerts.py — still present, just unrouted) were dropped from the UI.
routes = {
    page_names["executive"]: executive.render,
    page_names["services"]: services.render,
    page_names["revenue"]: revenue.render,
    page_names["charges"]: charges.render,
    page_names["trend_result"]: trend_result.render,
    page_names["trend_charges"]: trend_charges.render,
}
routes[page](data, context)
