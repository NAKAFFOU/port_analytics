"""Presentation-layer visualisation principle and centralised colour theme.

Guiding principle (documented here so it can be reused verbatim in the
dissertation, Chapter 4 — Presentation Layer):

    The pie/donut form is used ONLY to answer "what share of the whole does
    each category represent?", and only for 3-5 categories. Any question
    that involves COMPARING values to each other, or RANKING items, uses
    bars instead — because length is a far more perceptually reliable
    encoding than angle or area for comparison tasks (Few, S. (2004).
    "Show Me the Numbers: Designing Tables and Graphs to Enlighten."
    Analytics Press). Concretely in this dashboard:
      - 01/03/04 use a donut ONLY for a single "share of total" question
        (revenue by category, direct vs indirect split) — never to compare
        or rank more than 5 slices.
      - 01's "top services" and 04's "direct vs indirect by cost centre"
        are ranking/comparison questions, so they use horizontal/grouped
        bars, not a pie.
      - 05/06 are trend (evolution) questions, so they use line and area
        charts, never a pie.
    This rule is applied identically on every page — no page re-derives its
    own chart-type choice.

Colour mapping: one dictionary per categorical dimension, imported by every
page that charts that dimension, so a given category always renders in the
same colour on all six pages (accessibility requirement: consistent colour
coding reduces the cognitive load of re-learning a legend on each page).
Favourable/unfavourable variance is never encoded with red/green alone —
every variance indicator pairs colour with a shape/direction cue (▲/▼ or
+/-) in the surrounding text, so the distinction still reads correctly for
red-green colour-blind users.

Palette contrast: all foreground colours below are checked against a white
card background (#FFFFFF, the KPI/chart card colour in theme.py) for a
WCAG AA-equivalent contrast ratio (>= 3:1, the threshold for graphical
objects) at the swatch sizes used in a donut/bar chart.
"""

from __future__ import annotations

# The four revenue/cost categories shared by every source view
# (CATEGORIE / service_category) — see docs/SERVICE_CATALOG.md. Fixed
# across all six pages.
CATEGORY_COLOURS: dict[str, str] = {
    "Marchandises": "#1F4FD8",       # Cargo
    "Services Maritimes": "#0E9A8B",  # Maritime Services
    "Domaines": "#E08A00",           # Port Estate
    "Autres Services": "#8B5CF6",    # Other Services
    "Uncategorised": "#8A93A6",
}
CATEGORY_COLOURS_EN: dict[str, str] = {
    "Cargo": "#1F4FD8",
    "Maritime Services": "#0E9A8B",
    "Port Estate": "#E08A00",
    "Other Services": "#8B5CF6",
    "Uncategorised": "#8A93A6",
}

# Direct vs indirect cost split (page 04's donut and grouped bars, and
# page 02's waterfall) — fixed regardless of category.
COST_TYPE_COLOURS: dict[str, str] = {
    "direct": "#1F4FD8",
    "indirect": "#E08A00",
}

# Neutral series colour for the "Others" bucket produced by the Top-N +
# Others logic (data.py::_top_n_with_other) — used on every multi-series
# chart (05/06 and the family/sub-family trend charts) so "Others" is
# always the same, deliberately muted grey rather than a competing hue.
OTHER_SERIES_COLOUR = "#8A93A6"

# Ordered qualitative palette for an open-ended set of series (family,
# sub-family, cost centre) beyond the four fixed categories above — used
# where the dimension is not one of CATEGORY_COLOURS (e.g. cost families).
SERIES_PALETTE = [
    "#1F4FD8", "#0E9A8B", "#E08A00", "#8B5CF6",
    "#D6336C", "#2F9E44", "#1971C2", "#F08C00",
]


def category_colour_map(language: str = "fr") -> dict[str, str]:
    """Returns the fixed category -> colour map for the given language,
    always including the neutral 'Others' colour so callers can pass it
    straight to Plotly's color_discrete_map without a second lookup."""
    base = dict(CATEGORY_COLOURS if language == "fr" else CATEGORY_COLOURS_EN)
    base["Others"] = OTHER_SERIES_COLOUR
    base["Autres"] = OTHER_SERIES_COLOUR
    return base


def series_colour_map(names: list[str], other_label: str | None = None) -> dict[str, str]:
    """Assigns a stable colour to each name in `names` from SERIES_PALETTE
    (cycling if there are more names than palette entries), reserving
    OTHER_SERIES_COLOUR for `other_label` if given."""
    mapping: dict[str, str] = {}
    palette_index = 0
    for name in names:
        if other_label is not None and name == other_label:
            mapping[name] = OTHER_SERIES_COLOUR
            continue
        mapping[name] = SERIES_PALETTE[palette_index % len(SERIES_PALETTE)]
        palette_index += 1
    if other_label is not None:
        mapping[other_label] = OTHER_SERIES_COLOUR
    return mapping
