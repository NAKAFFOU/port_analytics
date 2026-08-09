Ce document fournit des preuves factuelles brutes destinées à alimenter la
rédaction du Chapitre 5 ; il ne constitue pas une revue d'experts et ne
remplace pas l'évaluation qualitative prévue par la méthodologie du
mémoire (Section 3.5).

# Chapter 5 Evaluation Evidence

Source of facts: branch `audit/data-integrity`, same state as
`docs/CHAPTER4_TECHNICAL_DOSSIER.md`. Organised against the Kroop (2025)
validity framework already adopted in the dissertation (Ch. 2.5/2.6/3.5).
Raw evidence only — the author interprets and frames it.

## Technical validity

### Test suite result

Command: `python -m pytest tests -v`.

```text
collected 126 items
124 passed, 2 skipped, 1 warning in 261.29s (0:04:21)
```

- **126 tests collected**, spanning 16 test files.
- **124 passed / 0 failed.**
- **2 skipped**: both in `tests/test_oracle_integration.py`, an opt-in
  check that only runs when `RUN_ORACLE_INTEGRATION_TESTS=true` and a
  reachable Oracle target is configured in `.env` — skipped by design in
  an environment with no live Oracle connection, not a failure.
- **1 warning**: a pandas `FutureWarning` about `.fillna` downcasting
  behaviour in `src/ingestion/oracle_views.py:767` (pre-existing,
  unrelated to this refactor; does not affect current results).
- Run against Python 3.13.3, pytest 9.1.1, on the `audit/data-integrity`
  branch, after the full data-integrity/6-page refactor described in
  `docs/CHAPTER4_TECHNICAL_DOSSIER.md`.

Categories covered by the suite (by file):

| File | Covers |
|---|---|
| `test_allocations.py` | Two-phase allocation math (phase1/phase2) |
| `test_annual_trends.py` | `annual_trend_by_dimension` Top-N + Others logic, year-window/period-suffix filtering |
| `test_dashboard_allocations.py` | End-to-end synthetic pipeline row counts, allocation-result reconciliation |
| `test_dashboard_pages_render.py` | All 6 dashboard pages render without exception (`streamlit.testing.v1.AppTest`); exactly 6 pages exposed in both languages |
| `test_demo_pipeline.py` | Full synthetic pipeline (seed → KPIs → alerts), multi-currency coverage, idempotency |
| `test_jde_dates.py` | JDE Julian-date conversion |
| `test_oracle_adapter_filters.py` | `OraclePBIViewsAdapter` bind-parameter filters |
| `test_oracle_connector.py` | Oracle connector DSN resolution, Thin/Thick mode |
| `test_oracle_integration.py` | Opt-in live-Oracle integration check (skipped unless `RUN_ORACLE_INTEGRATION_TESTS=true`) |
| `test_oracle_mapping.py` | Oracle→internal column mapping |
| `test_oracle_metadata.py` | `ALL_TAB_COLUMNS`/`ALL_VIEWS` metadata inspection |
| `test_oracle_normalisation.py` | `safe_year`/`safe_amount`/`_text` parsing robustness |
| `test_oracle_views_pipeline.py` | Pre-allocated-views ingestion, sign/scale rule, family/subfamily/account hash-collision guard |
| `test_pipeline_runner_cli.py` | `--source`/`--year`/`--object`/`--limit` CLI argument handling |
| `test_revenue_dashboard.py` | Revenue-facts consistency, `service_lines.service_code` primary-key guarantee |
| `test_synthetic_data_integrity.py` | Monthly/annual budget consistency, no-negative-charges, waterfall arithmetic (new, this refactor) |

### Documentary inconsistency detection and correction (concrete case)

Two documentation inconsistencies were identified and corrected as part of
this refactor, both located and fixed by direct inspection of the code
that actually runs (not by inference from prior documentation):

1. **Sign-inversion location.** `Port_Analytics_v3_Guide.docx` (deleted in
   this refactor — see the data-integrity audit below) stated: *"Python
   inverts costs to positive for analytical display."* This contradicts
   `config/sources/oracle_pbi_views.yaml` (comment: *"PBI_JDE views
   already apply sign inversion (* -1) ... amount_multiplier must stay 1
   ... MONTANT is loaded exactly as returned by Oracle"*),
   `README.md` ("Sign/scale rule"), and the code itself
   (`src/ingestion/oracle_views.py::safe_amount`, docstring: *"this
   function only parses the value — it never rescales or flips the
   sign"*; the `force_absolute` flag applies `abs()` for display, which
   is not the same operation as a sign inversion in this codebase's own
   vocabulary). Verified by reading `MEASURE_CONFIG["force_absolute"]`
   and `safe_amount` directly. The erroneous `.docx` no longer exists in
   the repository post-refactor (removed for containing real
   organisational data), which also removes the inconsistency; the
   surviving documentation is internally consistent on this point.
2. **Oracle view count.** `README.md` section "7. Load approved annual
   foreign-exchange rates" stated *"The four Oracle views..."* while
   every other section of the same file, and `docs/ORACLE_PBI_VIEWS.md`,
   consistently refer to **five** views (`ADIRECTE_COUT`,
   `AINDIRECTE_COUT`, `COUT_PAR_FCC`, `CHARGES_REPARTIES`, `RECETTE_PF`).
   Verified against `config/sources/oracle_pbi_views.yaml`'s `datasets:`
   block (5 entries) and `MEASURE_CONFIG` in
   `src/ingestion/oracle_views.py` (4 entries — `CHARGES_REPARTIES` is a
   cross-check source, not wired into the default pipeline). Corrected to
   state five views, with the four-vs-five distinction now made explicit.

## Design validity

Chart-type choice by page (raw material — see
`docs/CHAPTER4_TECHNICAL_DOSSIER.md` §4.7 for the full table and
`src/dashboard/viz_theme.py` for the underlying rule):

| Page | Chart(s) | Question being asked | Why this form |
|---|---|---|---|
| 01 | Donut | Share of revenue by category (≤5 categories) | Few (2004): angle/area comparison is unreliable beyond a simple share-of-whole read |
| 01 | Horizontal bars | Which services rank highest by revenue? | Ranking/comparison — length is the reliable encoding |
| 02 | `go.Waterfall` | How does revenue decompose into net result? | Additive decomposition to a total, in chart form |
| 03 | Donut | Share of revenue by category | Same share-of-whole justification as page 01 |
| 03 | 100%-stacked bars | How does the product mix differ across categories? | Comparison across categories/products — bars, not nested pies |
| 04 | Grouped (unstacked) bars | How do direct/indirect charges compare per cost centre? | Per-item comparison across two series — grouped bars keep both values individually readable |
| 04 | Donut (2 categories) | What global share is direct vs. indirect? | The one single-number share question on this page |
| 05 | Multi-line + reference line | How has net result evolved by family, 2020-2026? | Trend over time — line chart, with a period-average anchor |
| 06 | Stacked area + total overlay | How have charges evolved by family, 2020-2026? | Trend + composition simultaneously — stacked area, with a total line for the aggregate read |

## Purpose validity

Raw mapping of each page to the managerial question it is meant to
inform:

| Page | Managerial question |
|---|---|
| `01_Vue Exécutive_Synthèse` | What is our overall financial position right now, and which services drive revenue? |
| `02_Résultat_Net` | How does revenue break down into direct and indirect cost to produce the net result, by category/product? |
| `03_Analyse des recettes` | Where does revenue come from, by category and by product within category? |
| `04_Analyses des charges` | Where do charges concentrate — which cost centres, and how much of it is indirect? |
| `05_Evolution du résultat de 2020 à 2026` | Is financial performance improving or deteriorating over the medium term, and for which families? |
| `06_Evolution des charges de 2020 à 2026` | Is the cost base growing faster or slower than expected, and which cost families are driving it? |

## Context validity

Port-authority-specific adaptations already present in the system:

- **Service catalogue** (`docs/SERVICE_CATALOG.md`): four revenue
  categories (Marchandises/Cargo, Services Maritimes/Maritime Services,
  Domaines/Port Estate, Autres Services/Other Services) and ten finished
  products (Pilotage, Remorquage/Towage, Lamanage/Mooring, ISPS security
  fee, weighbridge, nautical/port access, water & electricity supply,
  port-estate operations, ancillary revenue) — standard port-industry
  terminology, not derived from any single real organisation.
- **Traffic seasonality**: revenue seasonality modelled on vessel-call
  frequency (Q2/Q3 peak, Q4/Q1 trough) rather than a generic retail/
  calendar pattern; three recurring service-specific disruptions
  (pilotage slowdown, channel-access dip, storage disruption) documented
  in `src/db/seed_demo.py`.
- **Multi-currency**: GBP (analytical base), EUR, USD, XOF — XOF
  reflecting a West-African-franc-zone port context, alongside the major
  reference currencies a port authority would also transact in
  (equipment/fuel in USD, regional trade in EUR).
- **Two-tier public-sector cost model**: Shared Service Centres →
  Operational Cost Centres → Port Service Lines, an allocation shape
  suited to a public port authority with both shared administrative
  functions and clearly metered operational service lines (pilotage,
  towage, cargo handling), rather than a generic corporate P&L structure.
- **Decision-alert vocabulary**: rule names/actions
  (`critical_deficit` → "Escalate immediately and prepare tariff,
  cost-reduction and explicit-subsidy options", `src/db/seed_demo.py`
  `ACTIONS`) reflect a public-service body that may legitimately run a
  subsidised deficit on some service lines, rather than a purely
  profit-maximising private firm.

## Traceability matrix (draft — requirements → features → status)

One row per Design Requirement listed in
`docs/CHAPTER4_TECHNICAL_DOSSIER.md` §4.2. Status is `implemented` /
`partial` / `not covered`, verified against the code, not inferred.

| Requirement | Feature | Status |
|---|---|---|
| Multi-source ingestion (Oracle pre-allocated views + JDE raw tables) | `src/adapters/oracle_pbi_views.py`, `src/adapters/jde_oracle.py`, common `src/adapters/base.py` interface | Implemented |
| Preserve source amount/currency/rate/provider for audit | `amount_source`/`amount_base`/`fx_rate_*` columns, populated on every insert | Implemented |
| Multi-currency (GBP/EUR/USD/XOF), single base currency | `src/currency/converter.py`, `config/settings.yaml::currency` | Implemented |
| Annual and monthly reporting granularity | `reporting_periods.period_granularity`; `seed-demo --granularity annual\|monthly` | Implemented (synthetic source); annual-only for the live/sample Oracle source (source limitation, documented) |
| No data traceable to a real organisation | Full removal of `data/*.csv` and the two real-org-derived mapping/docx files (data-integrity audit, Étape 1-2); `src/db/seed_demo.py` module docstring | Implemented |
| Two-phase cost allocation (synthetic source) | `src/pipeline/allocations.py` | Implemented |
| Pre-allocated-views pass-through, no re-allocation (Oracle source) | `pipeline.oracle_views_are_preallocated: true`; `ingest_frames()` never recomputes allocation percentages | Implemented |
| Shared KPI-formula definitions across both sources | `src/pipeline/kpi_formulas.py`, imported by both `src/pipeline/kpi.py` and `src/ingestion/oracle_views.py` | Implemented |
| No re-inversion of a sign already applied by Oracle | `safe_amount()` never rescales/flips sign; `force_absolute` applies `abs()` for display only | Implemented |
| Extraction traceability (rows extracted/valid/loaded/rejected) | `data_load_runs` table, populated per Oracle view per run | Implemented |
| Rule-based decision alerts | `src/rules/alerts.py::generate_alerts`, 12 rules in `alert_thresholds` | Implemented (backend); not exposed in the current 6-page navigation (deliberate, see §4.6) |
| No credentials in tracked files | `.env.example` placeholders only; `.env` gitignored | Implemented |
| Bind-parameter-only SQL access | `src/adapters/oracle_source_mapping.py`; no string-concatenated filter values | Implemented |
| Test isolation from the working database | `tests/conftest.py::PORT_ANALYTICS_DB_PATH` override | Implemented |
| Bilingual dashboard (EN default, FR toggle) | `src/dashboard/i18n.py`, `src/dashboard/context.py::sidebar_context` | Implemented |
| Single shared sidebar across all pages | `src/dashboard/context.py::sidebar_context`, called once in `src/dashboard/app.py` | Implemented |
| Consistent cross-page colour coding | `src/dashboard/viz_theme.py`, imported by pages 01/03/04/05/06 | Implemented |
| Pie/donut restricted to share-of-whole, ≤5 categories | `src/dashboard/viz_theme.py` module docstring; applied on pages 01/03/04 only, bars/lines/areas elsewhere | Implemented |
| Exactly six dashboard pages, four legacy pages backend-only | `src/dashboard/app.py` routing table (6 entries); `centres.py`/`allocations.py`/`budgets.py`/`alerts.py` retained, unrouted | Implemented |
