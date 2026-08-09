# Port Analytics — Oracle Analytical Views Edition (v3.0)

This edition is designed for an Oracle/JD Edwards environment where the
accounting allocation logic has already been executed in Oracle and exposed
through five prepared views in the `PBI_JDE` schema:

- `ADIRECTE_COUT`
- `AINDIRECTE_COUT`
- `COUT_PAR_FCC`
- `CHARGES_REPARTIES` (same distributed cost-centre costs as `COUT_PAR_FCC`,
  cross-check/alternate source — uses plural `FAMILLES`/`SOUS_FAMILLES`)
- `RECETTE_PF`

**Two data sources coexist and both keep working:** `DATA_SOURCE=synthetic`
(seeded demo data, no external connection — used for tests, demos and
offline development) and `DATA_SOURCE=oracle` (the five views above). Select
one with `--source` on `python -m src.pipeline.runner`, or via the
`DATA_SOURCE` environment variable.

> **Sign/scale rule:** the `PBI_JDE` views already apply sign inversion
> (`* -1`), `/100` scaling and `ROUND()` at the Oracle level. Nothing in this
> codebase repeats that transformation — `MONTANT` is loaded exactly as
> returned by Oracle, in every extraction path (live SQL and CSV).

The Python application **does not recalculate allocation keys or percentages**
for this source. It extracts the pre-allocated results, validates and
standardises the dimensions, converts the source amounts to the analytical
base currency, calculates management indicators, generates alerts and feeds
the Streamlit dashboard.

## 1. Source-to-dashboard flow

```text
JD Edwards tables
      ↓
Validated Oracle allocation logic
      ↓
PBI_JDE analytical views
      ↓
Read-only Oracle connector
      ↓
Annual source-fact staging and semantic standardisation
      ↓
Source currency → GBP conversion
      ↓
Revenue, direct cost, indirect cost, net result and margin KPIs
      ↓
Decision alerts and Streamlit dashboard
```

## 2. Supported Oracle view structures

### `ADIRECTE_COUT`

```text
ANNEE, CODE_CC, CATEGORIE, PRODUIT_FINI, MONTANT
```

### `AINDIRECTE_COUT`

```text
ANNEE, CATEGORIE, PRODUIT_FINI, MONTANT
```

### `COUT_PAR_FCC`

```text
ANNEE, CODE_CC, DESC_CC, FAMILLE, SOUS_FAMILLE, MONTANT
```

### `CHARGES_REPARTIES`

```text
ANNEE, FAMILLES, SOUS_FAMILLES, CODE_CC, DESC_CC, MONTANT
```

Note the **plural** column names here (`FAMILLES`, `SOUS_FAMILLES`), unlike
`COUT_PAR_FCC` (`FAMILLE`, `SOUS_FAMILLE`). Both are harmonised to the same
internal `family`/`subfamily` fields by
`src/adapters/oracle_source_mapping.py`.

### `RECETTE_PF`

```text
ANNEE, CATEGORIE, PRODUIT_FINI, COMPTE, MONTANT
```

Because the views contain only `ANNEE`, this implementation creates annual
periods such as `2025-ANNUAL`. It does not invent monthly data.

The central Oracle → internal-model mapping for all five views lives in
`src/adapters/oracle_source_mapping.py`, reused by the metadata inspector
and by the adapter's optional filters. It is the template to follow when
adding a further source (SAP, Sage) without changing the pipeline or the
dashboard.

## 3. Windows installation in VS Code

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

## 4. Validate the package without Oracle

The existing multi-currency demonstration remains available:

```powershell
python -m src.cli run-demo
```

A second command validates the pre-allocated-view pipeline against a
fabricated CSV export in the exact PBI_JDE column layout, covering
2020-2026 (see `src/db/seed_demo.py::generate_synthetic_oracle_views`) —
there is no real Oracle data anywhere in this repository:

```powershell
python -m src.cli run-oracle-views-sample
python -m streamlit run src\dashboard\app.py
```

> **`run-demo` (and `seed-demo`) resets `data/port_analytics.db` to the
> synthetic multi-currency demonstration**, including FX rates — it deletes
> whatever data a live Oracle connection had loaded. If you want to keep
> seeing data loaded from a live Oracle connection in the dashboard, don't
> run it; reload it afterwards with `python -m src.cli load-fx` followed by
> `ingest-oracle-views`.

## 5. Configure the live Oracle connection

Create the environment file:

```powershell
Copy-Item .env.example .env
```

Complete `.env` (see `.env.example` for the full annotated list). The
`config/sources/oracle_pbi_views.yaml` profile reads `ORACLE_*` variables;
DSN resolution priority is **`ORACLE_DSN` > `ORACLE_HOST`+`ORACLE_PORT`+
`ORACLE_SERVICE` > `ORACLE_HOST`+`ORACLE_PORT`+`ORACLE_SID`**:

```env
DATA_SOURCE=oracle

ORACLE_USER=PBI_JDE
ORACLE_PASSWORD=YOUR_PASSWORD

ORACLE_HOST=192.168.1.200
ORACLE_PORT=1521
ORACLE_SERVICE=
ORACLE_SID=JDEVM
ORACLE_DSN=
ORACLE_SCHEMA=PBI_JDE

ORACLE_THICK_MODE=false
ORACLE_CLIENT_LIB_DIR=

ORACLE_FETCH_SIZE=5000
ORACLE_QUERY_TIMEOUT=120
TRIM_ORACLE_TEXT=true

SOURCE_CURRENCY=XOF
DISPLAY_CURRENCY=GBP
```

The Oracle user requires read-only access to the five views. python-oracledb
runs in **Thin mode by default** (pure Python, no Oracle Client install
needed); set `ORACLE_THICK_MODE=true` and `ORACLE_CLIENT_LIB_DIR` only if
your network/DB combination requires Thick mode.

The legacy `config/sources/jde_oracle.yaml` profile is untouched and keeps
using its own `SOURCE_DB_*` variable names.

## 6. Test and inspect Oracle

`test-connection` checks the connection, prints session diagnostics (DB
name, session user, current schema, Oracle version, Thin/Thick mode — never
the password), and inspects the five views:

```powershell
python -m src.cli test-connection
```

A dedicated command inspects `ALL_OBJECTS` / `ALL_TAB_COLUMNS` / `ALL_VIEWS`
/ `ALL_CONSTRAINTS` / `ALL_CONS_COLUMNS` (no `DBA_*` view is used, so a
read-only PBI_JDE account is enough) and compares the live database
structure against what the pipeline expects, writing a JSON report. One view failing does not
block the inspection of the others; an empty-but-accessible view is reported
as such, not as an error:

```powershell
python -m src.cli inspect-oracle-metadata --out data/export/oracle_metadata_report.json
```

Per-column structure via the legacy inspector:

```powershell
python -m src.cli inspect-source --object ADIRECTE_COUT
python -m src.cli inspect-source --object AINDIRECTE_COUT
python -m src.cli inspect-source --object COUT_PAR_FCC
python -m src.cli inspect-source --object CHARGES_REPARTIES
python -m src.cli inspect-source --object RECETTE_PF
```

Probe a limited sample without loading SQLite:

```powershell
python -m src.cli probe-oracle-views --year 2025 --limit 10
```

## 7. Load approved annual foreign-exchange rates

None of the five Oracle views (including the `CHARGES_REPARTIES` cross-check
source) contain a currency column. The configured source currency therefore
applies to all extracted rows unless the views are later enhanced.

Complete:

```text
config/fx/annual_rates.csv
```

Example structure:

```csv
rate_date,from_currency,to_currency,rate,provider,is_estimated
2025-12-31,XOF,GBP,0.00129,FINANCE_APPROVED,0
```

The `rate` must mean:

```text
1 unit of from_currency = rate units of to_currency
```

Load the approved file:

```powershell
python -m src.cli load-fx --file config\fx\annual_rates.csv
```

The default policy for annual revenue and cost flows is `ANNUAL_AVERAGE`.
Change it to `YEAR_END` in `config/sources/oracle_pbi_views.yaml` only when
that policy has been approved for the intended analysis.

## 8. Run the live Oracle ingestion

```powershell
python -m src.cli ingest-oracle-views --year-from 2025 --year-to 2025
python -m src.cli ingest-oracle-views --year-from 2025 --year-to 2025 --object RECETTE_PF --limit 100
```

Or through the unified pipeline runner, which also selects synthetic vs.
Oracle:

```powershell
python -m src.pipeline.runner --source synthetic
python -m src.pipeline.runner --source oracle
python -m src.pipeline.runner --source oracle --year 2026
python -m src.pipeline.runner --source oracle --object RECETTE_PF
python -m src.pipeline.runner --source oracle --limit 100
```

Both commands:

1. test the Oracle connection first — extraction and KPI recompute are
   skipped if it fails;
2. extract the requested view(s), by bind-parameter filters only (no SQL
   string concatenation of filter values; column/object names come solely
   from the internal mapping, never from free-text input);
3. trim fixed-width `NCHAR` values (`TRIM_ORACLE_TEXT`);
4. robustly parse `ANNEE`/`MONTANT` (`None`, `""`, whitespace, `Decimal` all
   handled explicitly — no bare `int(value)` on unchecked input) **without
   dividing by 100 or re-inverting the sign**, since Oracle already did
   that;
5. aggregate identical analytical dimensions;
6. create stable cost-centre and service codes;
7. convert all source amounts to the base currency;
8. store source amount, source currency, rate, provider and base-currency
   amount;
9. build annual centre and service indicators and generate decision alerts;
10. record one row per Oracle view in `data_load_runs` (rows extracted/
    valid/loaded/rejected, filters used, duration, status) for traceability.

The allocation-rule tables remain empty in this mode. The pre-allocated
Oracle values are copied into detailed analytical allocation results with the
marker `PREALLOCATED_VIEW` and no percentage-based recalculation.

Data extraction happens in batches (`arraysize`/`prefetchrows`/`fetchmany`,
sized by `ORACLE_FETCH_SIZE`) — a full view is never pulled into a single
Python list before being turned into a DataFrame.

## 9. Launch Streamlit

```powershell
python -m streamlit run src\dashboard\app.py
```

Open:

```text
http://localhost:8501
```

The dashboard exposes exactly six pages (see `docs/DASHBOARD_DESIGN.md` for
the chart-type rationale behind each one):

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
backend logic (two-phase allocation, the alert engine, budget handling)
still runs and is stored in every pipeline run — only the dedicated
Streamlit pages for them were removed from `src/dashboard/app.py`'s routing
table.

## 10. Bilingual (FR/EN) labels and semantic mappings

The package works with automatically generated stable codes even with no
mapping at all. Populated mapping files add a business-friendly French
display name and its English translation, used by the dashboard's language
toggle:

```text
config/mappings/oracle_pbi_views/cost_centres.csv    (source_code, source_name, target_code, target_name, target_name_en)
config/mappings/oracle_pbi_views/service_lines.csv   (source_category, source_product, ..., target_service_name_en, target_category_name_en)
config/mappings/oracle_pbi_views/families.csv        (source_family, label_fr, label_en)
config/mappings/oracle_pbi_views/subfamilies.csv     (source_subfamily, label_fr, label_en)
config/mappings/oracle_pbi_views/accounts.csv        (source_account, label_fr, label_en)
```

These files standardise **labels only** — they never change or recalculate
an amount, and an unmapped value simply falls back to the raw JDE source
text in both languages. All five are pre-populated for the fabricated cost
centres/categories/services/families/sub-families/accounts produced by
`src/db/seed_demo.py::generate_synthetic_oracle_views` (there is no real
organisation's data anywhere in this repository); correct entries here
rather than in code if a translation needs fixing. The translation is
applied at **dashboard render time**
(`src/dashboard/data.py::localize`) — `oracle_view_facts`,
`cost_centres` and `service_lines` always keep the raw source value
alongside the translation, for audit.

`docs/SERVICE_CATALOG.md` describes, bilingually, what each of the 5
revenue categories and 10 finished products/services actually represents
(not just their translated label) — a starting point for the business
owner to confirm or correct.

## 11. Important limitations of the current five views

This section is scoped to the **live/sample Oracle PBI_JDE source**
specifically (`DATA_SOURCE=oracle`, and its synthetic stand-in
`run-oracle-views-sample`) — the synthetic multi-currency demonstration
(`DATA_SOURCE=synthetic`, `seed-demo`/`run-demo`) already provides monthly
granularity across 2020-2026 (`--granularity monthly|annual`); this is a
deliberate, documented asymmetry between the two sources, not an
oversight. See `docs/DASHBOARD_DESIGN.md`.

The current Oracle source supports:

- centre costs, broken down by family/sub-family;
- direct allocations;
- indirect allocations;
- service revenue, broken down by account;
- total allocated cost;
- service net position;
- analytical margin;
- cost-recovery ratio;
- indirect-cost share;
- decision alerts.

It does not currently provide:

- monthly analysis;
- budgets;
- operational volumes;
- source currency by row;
- indirect source-centre traceability.

For indirect costs, the dashboard uses a transparent `Indirect Cost Pool`
node because `AINDIRECTE_COUT` does not include a source cost centre.

`COUT_PAR_FCC`/`CHARGES_REPARTIES` family/subfamily and `RECETTE_PF.COMPTE`
are carried all the way through: extracted by the adapter, normalised
(`account`/`family`/`subfamily`), stored as extra dimensions on
`oracle_view_facts` (nullable — absent for the two allocation measures,
which have no such column), and folded into `source_row_hash` so that rows
differing only by family/subfamily/account are never merged or dropped by
the uniqueness constraint. `occ_indicators`/`psl_indicators` keep their
existing shape and totals (they re-aggregate by centre/service, so the
extra granularity upstream does not change them). The Cost Centres and
Produits Finis / Services dashboard pages read `oracle_view_facts` directly
for a family/sub-family and account breakdown, with their own filters —
silently omitted in DEMO mode or when a view exposes no such column.

## 12. Tests

```powershell
python -m pytest tests -v
```

Every test here runs against a local SQLite file and mocked Oracle objects —
none of them open a real Oracle connection. A separate, opt-in integration
check exists for a real instance:

```powershell
# .env must be filled in with a reachable ORACLE_* target first.
$env:RUN_ORACLE_INTEGRATION_TESTS = "true"
python -m pytest tests/test_oracle_integration.py -v
```

See `docs/ORACLE_PBI_VIEWS.md` for the detailed design and control logic.
