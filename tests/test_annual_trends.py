from __future__ import annotations

import pandas as pd
import pytest

from src.dashboard.components import annual_multi_line, annual_stacked_area
from src.dashboard.data import annual_trend_by_dimension, resolve_trend_scope

OTHER = "Others"
NOT_SPECIFIED = "Not specified"


def _psl_frame(rows: list[tuple[str, str, str, float, float]]) -> pd.DataFrame:
    """rows: (period_id, service_category, service_name, total_attributed_cost, service_net_position)"""
    return pd.DataFrame(
        rows,
        columns=[
            "period_id", "service_category", "service_name",
            "total_attributed_cost", "service_net_position",
        ],
    )


# --- annual_trend_by_dimension: aggregation, year cap, period matching ----

def test_aggregates_by_year_and_dimension_exactly():
    frame = _psl_frame(
        [
            ("2023-ANNUAL", "Marchandises", "PF-A", 100.0, 50.0),
            ("2023-ANNUAL", "Marchandises", "PF-B", 200.0, -20.0),
            ("2024-ANNUAL", "Marchandises", "PF-A", 150.0, 60.0),
        ]
    )
    trend = annual_trend_by_dimension(
        frame, "service_category", "total_attributed_cost",
        year=2024, period_id="ALL", other_label=OTHER, not_specified_label=NOT_SPECIFIED,
    )
    row_2023 = trend[trend["reporting_year"] == 2023].iloc[0]
    row_2024 = trend[trend["reporting_year"] == 2024].iloc[0]
    assert row_2023["total_attributed_cost"] == pytest.approx(300.0)
    assert row_2024["total_attributed_cost"] == pytest.approx(150.0)


def test_year_filter_caps_the_window_it_does_not_isolate_one_year():
    # Selecting year=2024 must show every year up to and including 2024 —
    # a trend restricted to a single year would defeat the point of an
    # "annual evolution" chart.
    frame = _psl_frame(
        [
            ("2022-ANNUAL", "Marchandises", "PF-A", 100.0, 10.0),
            ("2023-ANNUAL", "Marchandises", "PF-A", 100.0, 10.0),
            ("2024-ANNUAL", "Marchandises", "PF-A", 100.0, 10.0),
            ("2025-ANNUAL", "Marchandises", "PF-A", 100.0, 10.0),  # beyond the cap
        ]
    )
    trend = annual_trend_by_dimension(
        frame, "service_category", "total_attributed_cost",
        year=2024, period_id="ALL", other_label=OTHER, not_specified_label=NOT_SPECIFIED,
    )
    assert sorted(trend["reporting_year"].tolist()) == [2022, 2023, 2024]


def test_period_suffix_matches_the_same_period_across_years():
    # Data extracted via a live Oracle connection is annual-only
    # ("YYYY-ANNUAL"): the suffix ("ANNUAL") matches every year, so the
    # trend is untouched.
    frame = _psl_frame(
        [
            ("2023-ANNUAL", "Marchandises", "PF-A", 100.0, 0.0),
            ("2024-ANNUAL", "Marchandises", "PF-A", 200.0, 0.0),
        ]
    )
    trend = annual_trend_by_dimension(
        frame, "service_category", "total_attributed_cost",
        year=2024, period_id="2024-ANNUAL", other_label=OTHER, not_specified_label=NOT_SPECIFIED,
    )
    assert sorted(trend["reporting_year"].tolist()) == [2023, 2024]


def test_period_suffix_isolates_the_same_month_across_years_when_granular():
    # Demo-style monthly data: selecting "2024-03" must compare March across
    # every year, not collapse to a single point.
    frame = _psl_frame(
        [
            ("2023-01", "Marchandises", "PF-A", 100.0, 0.0),
            ("2023-03", "Marchandises", "PF-A", 50.0, 0.0),
            ("2024-03", "Marchandises", "PF-A", 70.0, 0.0),
        ]
    )
    trend = annual_trend_by_dimension(
        frame, "service_category", "total_attributed_cost",
        year=2024, period_id="2024-03", other_label=OTHER, not_specified_label=NOT_SPECIFIED,
    )
    assert sorted(trend["reporting_year"].tolist()) == [2023, 2024]
    assert float(trend[trend["reporting_year"] == 2023]["total_attributed_cost"].iloc[0]) == pytest.approx(50.0)


def test_top_n_set_is_stable_across_the_whole_window_not_per_year():
    # "Petit" is small overall (folded into Others) even though it is the
    # single biggest line in 2023 — the Top-N set must be picked from the
    # WHOLE window's totals, not recomputed year by year, or a series would
    # flicker in and out of "Others" from one year to the next.
    frame = _psl_frame(
        [
            ("2023-ANNUAL", "Gros", "PF-Gros", 10.0, 0.0),
            ("2023-ANNUAL", "Petit", "PF-Petit", 50.0, 0.0),
            ("2024-ANNUAL", "Gros", "PF-Gros", 1000.0, 0.0),
            ("2024-ANNUAL", "Petit", "PF-Petit", 5.0, 0.0),
        ]
    )
    trend = annual_trend_by_dimension(
        frame, "service_category", "total_attributed_cost",
        year=2024, period_id="ALL", other_label=OTHER, not_specified_label=NOT_SPECIFIED, top_n=1,
    )
    names_2023 = set(trend[trend["reporting_year"] == 2023]["service_category"])
    assert names_2023 == {"Gros", OTHER}


def test_blank_dimension_values_fold_into_not_specified():
    frame = _psl_frame([("2024-ANNUAL", "   ", "PF-A", 100.0, 0.0)])
    trend = annual_trend_by_dimension(
        frame, "service_category", "total_attributed_cost",
        year=2024, period_id="ALL", other_label=OTHER, not_specified_label=NOT_SPECIFIED,
    )
    assert trend["service_category"].tolist() == [NOT_SPECIFIED]


def test_net_result_negative_values_are_preserved_not_dropped():
    frame = _psl_frame([("2024-ANNUAL", "Marchandises", "PF-A", 100.0, -75.0)])
    trend = annual_trend_by_dimension(
        frame, "service_category", "service_net_position",
        year=2024, period_id="ALL", other_label=OTHER, not_specified_label=NOT_SPECIFIED,
    )
    assert trend["service_net_position"].iloc[0] == pytest.approx(-75.0)


def test_empty_input_returns_empty_frame_without_crash():
    trend = annual_trend_by_dimension(
        pd.DataFrame(columns=["period_id", "service_category", "total_attributed_cost"]),
        "service_category", "total_attributed_cost",
        year=2024, period_id="ALL", other_label=OTHER, not_specified_label=NOT_SPECIFIED,
    )
    assert trend.empty


# --- resolve_trend_scope: drill from family to sub-family -----------------

def test_resolve_trend_scope_groups_by_family_when_nothing_selected():
    frame = pd.DataFrame({"service_category": ["A", "B"], "service_name": ["PF-A", "PF-B"]})
    scoped, dimension = resolve_trend_scope(frame, "Toutes", "Toutes", "Toutes")
    assert dimension == "service_category"
    assert len(scoped) == 2


def test_resolve_trend_scope_switches_to_subfamily_once_family_chosen():
    frame = pd.DataFrame(
        {
            "service_category": ["A", "A", "B"],
            "service_name": ["PF-A1", "PF-A2", "PF-B1"],
        }
    )
    scoped, dimension = resolve_trend_scope(frame, "A", "Toutes", "Toutes")
    assert dimension == "service_name"
    assert sorted(scoped["service_name"]) == ["PF-A1", "PF-A2"]


def test_resolve_trend_scope_narrows_further_when_subfamily_chosen():
    frame = pd.DataFrame(
        {
            "service_category": ["A", "A"],
            "service_name": ["PF-A1", "PF-A2"],
        }
    )
    scoped, dimension = resolve_trend_scope(frame, "A", "PF-A1", "Toutes")
    assert dimension == "service_name"
    assert scoped["service_name"].tolist() == ["PF-A1"]


# --- chart builders: shape, sign handling, empty-input safety --------------

def test_annual_stacked_area_has_one_trace_per_dimension_value_and_is_stacked():
    trend = pd.DataFrame(
        {
            "reporting_year": [2023, 2023, 2024],
            "service_category": ["A", "B", "A"],
            "total_attributed_cost": [100.0, 50.0, 120.0],
        }
    )
    fig = annual_stacked_area(
        trend, "service_category", "total_attributed_cost",
        "Year", "Charges", "Family", language="en",
    )
    assert len(fig.data) == 2
    assert all(trace.stackgroup == "one" for trace in fig.data)


def test_annual_stacked_area_floors_negative_values_for_display_only():
    trend = pd.DataFrame(
        {"reporting_year": [2024], "service_category": ["A"], "total_attributed_cost": [-30.0]}
    )
    fig = annual_stacked_area(trend, "service_category", "total_attributed_cost", "Year", "Charges", "Family")
    assert fig.data[0].y[0] == 0.0
    assert fig.data[0].customdata[0] == -30.0


def test_annual_stacked_area_empty_input_returns_empty_figure():
    fig = annual_stacked_area(pd.DataFrame(), "service_category", "total_attributed_cost", "Year", "Charges", "Family")
    assert len(fig.data) == 0


def test_annual_multi_line_preserves_negative_net_result():
    trend = pd.DataFrame(
        {"reporting_year": [2023, 2024], "service_category": ["A", "A"], "service_net_position": [-40.0, 60.0]}
    )
    fig = annual_multi_line(trend, "service_category", "service_net_position", "Year", "Net result", "Category")
    assert list(fig.data[0].y) == [-40.0, 60.0]


def test_annual_multi_line_empty_input_returns_empty_figure():
    fig = annual_multi_line(pd.DataFrame(), "service_category", "service_net_position", "Year", "Net result", "Category")
    assert len(fig.data) == 0


def test_french_locale_uses_comma_decimal_space_thousand_separators():
    trend = pd.DataFrame(
        {"reporting_year": [2024], "service_category": ["A"], "total_attributed_cost": [100.0]}
    )
    fig = annual_stacked_area(
        trend, "service_category", "total_attributed_cost", "Année", "Charges", "Famille", language="fr",
    )
    assert fig.layout.separators == ", "


def test_english_locale_keeps_default_separators():
    trend = pd.DataFrame(
        {"reporting_year": [2024], "service_category": ["A"], "total_attributed_cost": [100.0]}
    )
    fig = annual_stacked_area(
        trend, "service_category", "total_attributed_cost", "Year", "Charges", "Family", language="en",
    )
    assert fig.layout.separators is None
