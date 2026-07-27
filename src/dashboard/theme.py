from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from src.common.config import get_settings, project_path


def _data_uri(path: Path) -> str:
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def apply_dashboard_theme() -> None:
    settings = get_settings()["dashboard"]
    primary = settings.get("primary_colour", "#172B9B")
    secondary = settings.get("secondary_colour", "#168FF0")
    accent = settings.get("accent_colour", "#F15A3A")
    watermark_css = ""

    watermark_path = project_path("assets/watermark.svg")
    if settings.get("show_watermark", True) and watermark_path.exists():
        watermark_css = f"""
        .stApp {{
            background-image: url('{_data_uri(watermark_path)}');
            background-repeat: repeat;
            background-size: 150px 150px;
        }}
        """

    st.markdown(
        f"""
        <style>
        :root {{
            --pa-primary: {primary};
            --pa-secondary: {secondary};
            --pa-accent: {accent};
        }}
        {watermark_css}

        [data-testid="stAppViewContainer"] > .main {{
            background: rgba(255,255,255,0.94);
        }}

        .block-container {{
            max-width: 1500px;
            padding-top: 1.1rem;
            padding-bottom: 2rem;
        }}

        .pa-header {{
            position: relative;
            padding: 0.2rem 0 1rem 0;
            margin-bottom: 0.2rem;
        }}

        .pa-title {{
            text-align: center;
            color: var(--pa-primary);
            font-weight: 850;
            font-size: 2.15rem;
            letter-spacing: 0.01em;
            margin: 0;
        }}

        .pa-subtitle {{
            text-align: center;
            color: #536078;
            font-size: 0.94rem;
            margin-top: 0.25rem;
        }}

        .pa-kpi {{
            border: 1px solid #e5e9f2;
            border-radius: 24px;
            padding: 17px 18px;
            background: rgba(255,255,255,0.98);
            box-shadow: 0 4px 14px rgba(23,43,155,0.07);
            min-height: 125px;
        }}

        .pa-kpi-label {{
            color: #242936;
            font-weight: 700;
            text-align: center;
            font-size: 1.02rem;
            min-height: 2.2rem;
        }}

        .pa-kpi-value {{
            color: #252525;
            font-weight: 720;
            text-align: center;
            font-size: 2rem;
            margin-top: 0.5rem;
            white-space: nowrap;
        }}

        .pa-kpi-note {{
            color: #7a8190;
            text-align: center;
            font-size: 0.72rem;
            margin-top: 0.35rem;
        }}

        section[data-testid="stSidebar"] {{
            border-right: 1px solid #dfe4ee;
        }}

        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {{
            color: var(--pa-primary);
        }}

        div[data-testid="stPlotlyChart"] {{
            background: rgba(255,255,255,0.96);
            border-radius: 18px;
            padding: 0.35rem;
        }}

        div[data-testid="stDataFrame"] {{
            background: rgba(255,255,255,0.98);
            border-radius: 12px;
        }}

        .pa-pill {{
            display: inline-block;
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            font-weight: 700;
            font-size: 0.78rem;
            margin-right: 0.35rem;
        }}

        .pa-critical {{background:#fde7e7;color:#a40000;}}
        .pa-priority {{background:#fff0d8;color:#9a5200;}}
        .pa-warning {{background:#fff7c7;color:#735d00;}}
        .pa-info {{background:#e7f2ff;color:#0a4f92;}}

        button[kind="primary"] {{
            background-color: var(--pa-primary);
            border-color: var(--pa-primary);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str | None = None) -> None:
    subtitle_html = (
        f'<div class="pa-subtitle">{subtitle}</div>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div class="pa-header">
          <h1 class="pa-title">{title}</h1>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_logo() -> None:
    settings = get_settings()["dashboard"]
    logo_path = project_path(settings.get("logo_path", "assets/generic_port_logo.svg"))
    if logo_path.exists():
        st.sidebar.image(str(logo_path), use_container_width=True)
