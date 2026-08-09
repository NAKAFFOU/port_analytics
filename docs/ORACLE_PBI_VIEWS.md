# Oracle PBI_JDE Views — Technical Design

## Design decision

The source views already contain the outputs of the accounting allocation
process. Reapplying SSC–OCC–PSL percentages in Python would duplicate the
validated accounting logic and could create differences from Power BI and
Oracle. The Oracle-views mode therefore treats the values as authoritative
pre-allocated analytical facts.

## Measure mapping

| Oracle view | Canonical measure |
|---|---|
| ADIRECTE_COUT | DIRECT_ALLOCATION |
| AINDIRECTE_COUT | INDIRECT_ALLOCATION |
| COUT_PAR_FCC | COST_CENTRE_COST |
| CHARGES_REPARTIES | COST_CENTRE_COST (alternate/cross-check source; not wired into the default pipeline) |
| RECETTE_PF | SERVICE_REVENUE |

`CHARGES_REPARTIES` exposes the same distributed cost-centre costs as
`COUT_PAR_FCC` (verified: identical row count and total `MONTANT`) but with
pluralised `FAMILLES`/`SOUS_FAMILLES` columns instead of `FAMILLE`/
`SOUS_FAMILLE`. `OraclePBIViewsAdapter.extract_charges_reparties()` and the
metadata inspector both recognise it; use it to reconcile totals against
`COUT_PAR_FCC` or as a substitute source if `COUT_PAR_FCC` becomes
unavailable. The full Oracle→internal column mapping for all five views,
including `RECETTE_PF.COMPTE`, lives in `src/adapters/oracle_source_mapping.py`.

## Calculated measures

```text
Total allocated cost = Direct allocation + Indirect allocation
Net result = Revenue - Total allocated cost
Analytical margin % = Net result / Revenue × 100
Cost recovery ratio = Revenue / Total allocated cost
Indirect share % = Indirect allocation / Total allocated cost × 100
Centre cost share % = Centre cost / Total centre cost × 100
```

## Annual periods

The view structures contain `ANNEE` but no month or transaction date. Each
source year is represented as an annual period:

```text
2025-ANNUAL
```

`reporting_periods.period_granularity` is set to `YEAR` and the period end is
31 December.

## Additional dimensions: family/subfamily and account

`COUT_PAR_FCC`/`CHARGES_REPARTIES` (`FAMILLE`/`SOUS_FAMILLE` or the plural
`FAMILLES`/`SOUS_FAMILLES`) and `RECETTE_PF.COMPTE` are captured as `family`,
`subfamily` and `account` — nullable columns on `oracle_view_facts`, absent
for `DIRECT_ALLOCATION`/`INDIRECT_ALLOCATION` (ADIRECTE_COUT/AINDIRECTE_COUT
have no such column). They are part of `MEASURE_CONFIG["group"]` for
`COST_CENTRE_COST` and `SERVICE_REVENUE`, so a cost line is no longer
collapsed with another one differing only by family; `source_row_hash`
includes them too, so the `UNIQUE(batch_id, measure_type, source_row_hash)`
constraint cannot silently drop a row that differs only by this dimension.

This does **not** change `occ_indicators`/`psl_indicators`: both are built
by re-aggregating `oracle_view_facts` by `centre_code`/`service_code` and
`period_id`, so the extra upstream granularity sums back to the same totals.
The Cost Centres and Produits Finis / Services dashboard pages add a
breakdown section reading `oracle_view_facts` directly (with its own
family/sub-family or account filter); it is silently omitted when running
in DEMO mode or when a row has no such dimension recorded.

## Currency treatment

The source amount, configured source currency, applied rate, provider, rate
date and GBP amount are stored in `oracle_view_facts`. Annual flows use the
configured annual-average policy by default. The dashboard can convert the
stored GBP values to supported display currencies without altering the
analytical base.

## Semantic codes

Source labels remain available for audit. The prototype creates stable
technical keys for joins and dashboard filtering. Optional CSV mappings can
override the generated codes and labels without changing the amounts.

## Indirect allocation traceability

`AINDIRECTE_COUT` has no `CODE_CC`. The implementation therefore creates a
special `POOL-INDIRECT` source node. This is not a recalculation; it is a
transparent representation of the source limitation.

## Data-quality controls

The ingestion verifies:

- required columns and values;
- numeric years and amounts;
- annual FX-rate availability before loading;
- source labels after trimming NCHAR padding;
- duplicates through dimension-level aggregation;
- allocation arithmetic in the analytical result tables;
- services with allocated cost but no revenue.

## Reconciliation controls

For each year, the following source and SQLite totals should be compared:

```sql
SELECT ANNEE, SUM(MONTANT) FROM PBI_JDE.ADIRECTE_COUT GROUP BY ANNEE;
SELECT ANNEE, SUM(MONTANT) FROM PBI_JDE.AINDIRECTE_COUT GROUP BY ANNEE;
SELECT ANNEE, SUM(MONTANT) FROM PBI_JDE.COUT_PAR_FCC GROUP BY ANNEE;
SELECT ANNEE, SUM(MONTANT) FROM PBI_JDE.RECETTE_PF GROUP BY ANNEE;
```

SQLite keeps both `amount_source` and `amount_base`, enabling reconciliation
before and after currency conversion.

## Metadata inspection

`python -m src.cli inspect-oracle-metadata` queries `ALL_OBJECTS`,
`ALL_TAB_COLUMNS`, `ALL_VIEWS`, `ALL_CONSTRAINTS` and `ALL_CONS_COLUMNS`
(never a `DBA_*` view, so a read-only PBI_JDE grant is enough) for each of
the five views, compares the live database's columns against
`src/adapters/oracle_source_mapping.py`, and reports missing/extra columns,
soft type mismatches, and row presence — writing a JSON report. A failure on
one view (missing grant, invalid view, absent object) is captured on that
view's report and never blocks inspection of the others.

## Load traceability

Each ingestion run writes one row per Oracle view into `data_load_runs`
(rows extracted / valid / loaded / rejected, filters used, duration,
status), in addition to the existing `ingestion_batches` summary row and the
per-row `data_quality_issues` entries.
