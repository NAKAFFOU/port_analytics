# Oracle/JD Edwards Configuration Checklist

1. Confirm the Oracle service name and network access from Ubuntu.
2. Create a dedicated read-only Oracle account.
3. Confirm the data schema, normally an environment-specific schema such as PRODDTA.
4. Inspect F0911 columns with `inspect-source`.
5. Validate the configured columns in the SQL template.
6. Confirm the correct ledger type, posting filters and date field.
7. Confirm whether the amount field needs a divisor or sign multiplier.
8. Confirm the currency field and the domestic-currency fallback.
9. Replace example cost-centre, account and service mappings.
10. Reconcile a small extracted period to a trusted JDE report before widening the extraction range.
11. Load budgets and operational volumes from approved sources.
12. Review data-quality issues and rejected rows after every pilot run.
