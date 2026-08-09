# Port Analytics — Analytical Prototype (v3.0)

An MSc dissertation prototype for port cost/revenue analytics: currency
conversion, KPI computation, decision alerts and a six-page Streamlit
dashboard. It runs entirely on **fabricated synthetic data** — no row in
this repository is copied from, or traceable to, any real organisation
(see `src/db/seed_demo.py`).

The internal data model mirrors a JD Edwards / Oracle analytical-views
source (`PBI_JDE` schema), so the same pipeline can optionally be pointed
at a live Oracle database instead of the synthetic generator — see
[§6](#6-optional-connecting-to-a-live-database).

## 1. Data flow

```text
Synthetic data generator (src/db/seed_demo.py)
      ↓
SQLite analytical store
      ↓
Source currency → base currency conversion
      ↓
Revenue, direct cost, indirect cost, net result and margin KPIs
      ↓
Decision alerts and Streamlit dashboard
```

## 2. Windows installation in VS Code

Open PowerShell from the project root:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The helper script performs the same setup:

```powershell
.\scripts\setup_windows.ps1
```

## 3. Run the prototype

The multi-currency demonstration (SSC/OCC/PSL two-phase allocation,
2020-2026, USD/XOF sources converted to GBP):

```powershell
python -m src.cli run-demo
python -m streamlit run src\dashboard\app.py
```

A second, independent synthetic dataset exercises the same pipeline
shaped like the JD Edwards/Oracle analytical views (`ADIRECTE_COUT`,
`AINDIRECTE_COUT`, `COUT_PAR_FCC`, `CHARGES_REPARTIES`, `RECETTE_PF`),
without any database connection:

```powershell
python -m src.cli run-oracle-views-sample
python -m streamlit run src\dashboard\app.py
```

> `run-demo` (and `seed-demo`) resets `data/port_analytics.db` to the
> synthetic multi-currency demonstration. If you've loaded data from a
> live Oracle connection and want to keep it in the dashboard, don't run
> it — reload afterwards with `ingest-oracle-views`.

Open the dashboard at `http://localhost:8501`.

## 4. Dashboard pages

Six pages (see `docs/DASHBOARD_DESIGN.md` for the chart-type rationale
behind each one):

1. `01_Vue Exécutive_Synthèse` — KPI ribbon with sparklines, revenue-by-category
   donut, top-10 services bar chart.
2. `02_Résultat_Net` — KPI ribbon, category/product net-result matrix, and a
   revenue → net-result waterfall chart.
3. `03_Analyse des recettes` — KPI ribbon, revenue-by-category donut, 100%
   stacked bars for the product mix within each category.
4. `04_Analyses des charges` — KPI ribbon, grouped (not stacked) direct vs.
   indirect bars by cost centre, and a direct/indirect share donut.
5. `05_Evolution du résultat de 2020 à 2026` — multi-year net-result lines by
   family/sub-family with a period-average reference line.
6. `06_Evolution des charges de 2020 à 2026` — multi-year stacked charges
   area by family/sub-family with a total-charges overlay line.

The Cost Centres, Allocation Analysis, Budget Monitoring and Decision Alerts
pages (`src/dashboard/views/centres.py`, `allocations.py`, `budgets.py`,
`alerts.py`) are no longer exposed in the sidebar navigation, but their
backend logic still runs and is stored in every pipeline run — only the
dedicated Streamlit pages for them were removed from `src/dashboard/app.py`'s
routing table.

## 5. Bilingual (FR/EN) labels and semantic mappings

The package works with automatically generated stable codes even with no
mapping at all. Populated mapping files add a business-friendly French
display name and its English translation, used by the dashboard's language
toggle:

```text
config/mappings/oracle_pbi_views/cost_centres.csv
config/mappings/oracle_pbi_views/service_lines.csv
config/mappings/oracle_pbi_views/families.csv
config/mappings/oracle_pbi_views/subfamilies.csv
config/mappings/oracle_pbi_views/accounts.csv
```

These files standardise **labels only** — they never change or recalculate
an amount, and an unmapped value simply falls back to the raw source text in
both languages. All five are pre-populated for the fabricated cost
centres/categories/services/families/sub-families/accounts produced by
`src/db/seed_demo.py::generate_synthetic_oracle_views`. Translation is
applied at **dashboard render time** (`src/dashboard/data.py::localize`);
the underlying tables always keep the raw source value alongside the
translation, for audit.

`docs/SERVICE_CATALOG.md` describes, bilingually, what each of the 5
revenue categories and 10 finished products/services actually represents.

## 6. Optional: connecting to a live database

The pipeline can be pointed at a real JD Edwards/Oracle instance instead of
the synthetic generator, without any change to the dashboard or KPI logic:

```powershell
Copy-Item .env.example .env
# Fill in DATA_SOURCE=oracle and the ORACLE_* variables (see .env.example)
python -m src.cli test-connection
python -m src.cli load-fx --file config\fx\annual_rates.csv
python -m src.cli ingest-oracle-views --year-from 2025 --year-to 2025
```

Full setup, the five expected view structures, connection diagnostics and
known limitations are documented in `docs/ORACLE_PBI_VIEWS.md` and
`docs/JDE_CONFIGURATION.md` — not required to run or evaluate this
prototype.

## 7. Tests

```powershell
python -m pytest tests -v
```

Every test runs against a local SQLite file and mocked Oracle objects —
none of them open a real Oracle connection. A separate, opt-in integration
check exists for a real instance (`tests/test_oracle_integration.py`,
gated behind `RUN_ORACLE_INTEGRATION_TESTS=true`).


