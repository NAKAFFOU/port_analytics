# Streamlit Dashboard Design

The dashboard exposes exactly six pages, kept identical across both
supported languages (English/French — the six names below are used
verbatim in both). The sidebar (language, year, period, display currency)
is built once (`src/dashboard/context.py::sidebar_context`) and shared by
every page; no page duplicates or overrides it.

## Visualisation principle (Few, 2004)

The pie/donut form is used **only** to answer "what share of the whole
does each category represent?", and only for 3-5 categories. Any question
that involves **comparing** values to each other, or **ranking** items,
uses bars instead — length is a far more perceptually reliable encoding
than angle or area for comparison tasks (Few, S. (2004). *Show Me the
Numbers: Designing Tables and Graphs to Enlighten*. Analytics Press). This
rule is centralised in `src/dashboard/viz_theme.py` (see its module
docstring, which this section mirrors) and applied identically on every
page — no page re-derives its own chart-type choice.

Favourable/unfavourable variance is never signalled with red/green colour
alone; every variance indicator pairs colour with a direction cue (▲/▼ or
a +/- sign) in the surrounding text or number formatting.

## Centralised colour mapping

`src/dashboard/viz_theme.py` defines one colour per revenue/cost category
(`CATEGORY_COLOURS`/`CATEGORY_COLOURS_EN`) and one pair for the direct/
indirect cost split (`COST_TYPE_COLOURS`), imported by every page that
charts that dimension — a given category renders in the same colour on
all six pages, which reduces the cognitive load of re-learning a legend
on each page.

## Pages

1. **`01_Vue Exécutive_Synthèse`**
   - KPI ribbon (revenue, direct/indirect/total cost, net result, margin),
     each card with a sparkline of the last 12 available periods.
   - Donut: revenue share by category (a "share of the whole" question,
     4-5 categories).
   - Horizontal bars: top 10 services by revenue (a ranking question).

2. **`02_Résultat_Net`**
   - KPI ribbon.
   - The existing category → product net-result matrix (unchanged).
   - `go.Waterfall`: Revenue → −Direct costs → −Indirect costs → Net
     result, for the current period/selection.

3. **`03_Analyse des recettes`**
   - KPI ribbon.
   - Donut: revenue share by category.
   - 100%-stacked bars: product mix within each category — a comparison
     across products, so bars rather than a second, nested pie.
   - `validate_revenue_dashboard_totals()` still cross-checks the KPI
     card against the category/product breakdown, regardless of which
     chart type is used to render it.

4. **`04_Analyses des charges`**
   - KPI ribbon.
   - Grouped (not stacked) bars: direct vs. indirect charges by cost
     centre.
   - Donut: direct vs. indirect share of total charges (2 categories —
     the one "share of the whole" question this page asks).

5. **`05_Evolution du résultat de 2020 à 2026`**
   - KPI ribbon: total net result over the period, % change over the
     period, best/worst year.
   - Multi-year lines, one per family/category (Top-N + Others, reusing
     `data.py::annual_trend_by_dimension`), with a period-average
     reference line overlaid.

6. **`06_Evolution des charges de 2020 à 2026`**
   - KPI ribbon: total charges over the period, % change over the
     period, lowest/highest-charge year.
   - Stacked areas by family/category (same Top-N + Others logic), with
     a total-charges line overlaid.

### Pages removed from the navigation (backend retained)

Cost Centres, Allocation Analysis, Budget Monitoring and Decision Alerts
(`src/dashboard/views/centres.py`, `allocations.py`, `budgets.py`,
`alerts.py`) are no longer routed in `src/dashboard/app.py`. Their
backend logic — the two-phase allocation pipeline
(`src/pipeline/allocations.py`), the alert engine (`src/rules/alerts.py`)
and budget handling — still runs and is stored on every pipeline run;
only the dedicated Streamlit pages for them were removed from the
navigation.

## Monthly vs. annual granularity

The synthetic demonstration source (`DATA_SOURCE=synthetic`) provides
both annual and monthly granularity across 2020-2026
(`seed-demo --granularity annual|monthly`); the sidebar's PERIOD selector
exposes individual months whenever monthly data is loaded. The live/
sample Oracle PBI_JDE source (`DATA_SOURCE=oracle`,
`run-oracle-views-sample`) is annual-only — the five source views expose
only `ANNEE`, no month or transaction date — and this asymmetry is
deliberate, not an oversight (see `docs/ORACLE_PBI_VIEWS.md`).

## Currency handling

All analytical values are stored in the configured base currency,
normally GBP. The display currency can be changed from the sidebar. The
dashboard uses the latest approved exchange rate on or before the
reporting date.

## Branding

The generic logo and watermark are included in `assets/`. To use an
organisation-specific theme:

1. Replace or add the approved logo.
2. Set `dashboard.theme: organisation`.
3. Change `dashboard.logo_path` in `config/settings.yaml`.
4. Update organisation name and approved colours.

Do not commit confidential logos or credentials to a public repository.
