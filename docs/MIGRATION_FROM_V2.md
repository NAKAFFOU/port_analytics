# Migration from v2 to v3

Version 3 changes the primary Oracle source from direct JD Edwards tables to
prepared views in `PBI_JDE`.

## Required action

Use the v3 folder as a separate project or remove the old SQLite database:

```powershell
Remove-Item data\port_analytics.db* -Force -ErrorAction SilentlyContinue
```

Do not copy an old v2 database into v3 because the period model now supports
both monthly and annual granularities.

## Unchanged components

- multi-currency base and display conversion;
- Streamlit visual design;
- synthetic demonstration mode;
- decision-alert framework;
- optional legacy F0911 adapter.

## Changed components

- default Oracle profile is `oracle_pbi_views.yaml`;
- annual reporting periods are supported;
- Oracle facts are stored in `oracle_view_facts`;
- ingestion via a live Oracle connection does not use allocation-rule tables;
- the budget page is conditional on budget availability.
