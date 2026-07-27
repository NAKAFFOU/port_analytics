"""Ce module génère exclusivement des données synthétiques à des fins de
démonstration académique. This module exclusively generates synthetic data
for academic demonstration purposes.

No row produced here is copied from, or traceable to, any real
organisation. All codes, department names, amounts and time series are
fabricated by the two generators below, seeded deterministically
(``RANDOM_SEED``) so a given (granularity, year range) always reproduces
the same dataset.

Two independent synthetic datasets are produced:

1. ``seed_demo()`` — the SSC/OCC/PSL two-phase allocation demo (generic
   cost centres, account categories and port service lines), covering
   2020-2026 at annual or monthly granularity (``--granularity``).
2. ``generate_synthetic_oracle_views()`` — a fabricated export in the
   *exact* column layout of the five PBI_JDE analytical views (see
   ``docs/ORACLE_PBI_VIEWS.md``), used by the "pre-allocated Oracle views"
   pipeline (``src/ingestion/oracle_views.py``) instead of a real Oracle
   extract. It shares the same generic service catalogue documented in
   ``docs/SERVICE_CATALOG.md``, plus a fabricated cost-centre and
   chart-of-accounts taxonomy that is not derived from any real
   organisation.

Both generators share the same multi-year trend and seasonality logic
(documented next to ``REVENUE_TREND``/``COST_TREND`` and
``COST_WEIGHTS``/``REVENUE_WEIGHTS`` below): a 2020 traffic downturn,
progressive recovery, and stabilised growth through 2026, with revenue
more seasonally and cyclically volatile than cost — a plausible
public-port pattern (pilotage/towage revenue tracks vessel calls; payroll,
the majority of cost, does not).
"""

from __future__ import annotations

import calendar
import csv
import random
from pathlib import Path
from datetime import date

from src.common.config import base_currency, project_path
from src.currency.converter import CurrencyConverter
from src.currency.repository import FxRate, FxRateRepository
from src.db.schema import connect, create_schema

RANDOM_SEED = 42
YEAR_FROM = 2020
YEAR_TO = 2026
YEARS = tuple(range(YEAR_FROM, YEAR_TO + 1))

COST_CENTRES = [
    ("SSC-ADM", "General Administration", "SSC", "SUPPORT", None),
    ("SSC-IT", "Information Technology & Systems", "SSC", "SUPPORT", None),
    ("SSC-FAC", "Facilities & Maintenance", "SSC", "SUPPORT", None),
    ("OCC-NAV", "Marine & Navigation Operations", "OCC", "OPERATIONAL", None),
    ("OCC-CARGO", "Cargo Handling & Terminal", "OCC", "OPERATIONAL", None),
    ("OCC-INFRA", "Port Infrastructure & Engineering", "OCC", "OPERATIONAL", None),
    ("OCC-SEC", "Port Security & Safety", "OCC", "OPERATIONAL", None),
    ("OCC-COMM", "Commercial & Port Domain", "OCC", "OPERATIONAL", None),
]

ACCOUNT_CATEGORIES = [
    ("AC-PAY", "Payroll & Staff Costs", "DIRECT_COST"),
    ("AC-EQUIP", "Equipment & Assets", "DIRECT_COST"),
    ("AC-ENRG", "Energy & Utilities", "DIRECT_COST"),
    ("AC-OPS", "Operational Supplies", "DIRECT_COST"),
    ("AC-IADM", "Administration Overhead", "INDIRECT_COST"),
    ("AC-IMNT", "Maintenance Overhead", "INDIRECT_COST"),
    ("AC-ISEC", "Security Overhead", "INDIRECT_COST"),
    ("AC-IIT", "IT Overhead", "INDIRECT_COST"),
    ("AC-IFAC", "Facilities Overhead", "INDIRECT_COST"),
    ("RV-DUES", "Port Dues & Vessel Fees", "REVENUE"),
    ("RV-CARGO", "Cargo Handling Fees", "REVENUE"),
    ("RV-MISC", "Ancillary Revenue", "REVENUE"),
]

SERVICE_LINES = [
    ("PSL-PIL", "Pilotage Services", "Maritime Services", "Port dues — pilotage", "Vessel calls"),
    ("PSL-TOW", "Towage Services", "Maritime Services", "Port dues — towage", "Vessel calls"),
    ("PSL-CARGO", "Cargo Handling Services", "Cargo & Logistics", "Cargo handling fees", "Cargo throughput (tonnes)"),
    ("PSL-NACC", "Nautical Access & Channel", "Maritime Services", "Port dues — vessel", "Vessel gross tonnage"),
    ("PSL-STOR", "Storage & Yard Services", "Cargo & Logistics", "Storage fees", "Tonne-days in storage"),
    ("PSL-DOM", "Port Domain Concessions", "Port Estate", "Concession & rental", "Leased area (m²)"),
]

ALLOC_PHASE1 = [
    ("SSC-ADM", "OCC-NAV", "DRV-HEAD", 25.0), ("SSC-ADM", "OCC-CARGO", "DRV-HEAD", 30.0),
    ("SSC-ADM", "OCC-INFRA", "DRV-HEAD", 20.0), ("SSC-ADM", "OCC-SEC", "DRV-HEAD", 18.0),
    ("SSC-ADM", "OCC-COMM", "DRV-HEAD", 7.0), ("SSC-IT", "OCC-NAV", "DRV-OPEX", 20.0),
    ("SSC-IT", "OCC-CARGO", "DRV-OPEX", 35.0), ("SSC-IT", "OCC-INFRA", "DRV-OPEX", 22.0),
    ("SSC-IT", "OCC-SEC", "DRV-OPEX", 15.0), ("SSC-IT", "OCC-COMM", "DRV-OPEX", 8.0),
    ("SSC-FAC", "OCC-NAV", "DRV-OPEX", 18.0), ("SSC-FAC", "OCC-CARGO", "DRV-OPEX", 32.0),
    ("SSC-FAC", "OCC-INFRA", "DRV-OPEX", 28.0), ("SSC-FAC", "OCC-SEC", "DRV-OPEX", 16.0),
    ("SSC-FAC", "OCC-COMM", "DRV-OPEX", 6.0),
]

ALLOC_PHASE2 = [
    ("OCC-NAV", "PSL-PIL", "DRV-CALL", 35.0), ("OCC-NAV", "PSL-TOW", "DRV-CALL", 30.0),
    ("OCC-NAV", "PSL-CARGO", "DRV-CALL", 15.0), ("OCC-NAV", "PSL-NACC", "DRV-CALL", 20.0),
    ("OCC-CARGO", "PSL-TOW", "DRV-VOL", 5.0), ("OCC-CARGO", "PSL-CARGO", "DRV-VOL", 60.0),
    ("OCC-CARGO", "PSL-STOR", "DRV-VOL", 30.0), ("OCC-CARGO", "PSL-DOM", "DRV-VOL", 5.0),
    ("OCC-INFRA", "PSL-PIL", "DRV-OPEX", 10.0), ("OCC-INFRA", "PSL-TOW", "DRV-OPEX", 10.0),
    ("OCC-INFRA", "PSL-CARGO", "DRV-OPEX", 20.0), ("OCC-INFRA", "PSL-NACC", "DRV-OPEX", 40.0),
    ("OCC-INFRA", "PSL-STOR", "DRV-OPEX", 15.0), ("OCC-INFRA", "PSL-DOM", "DRV-OPEX", 5.0),
    ("OCC-SEC", "PSL-PIL", "DRV-HEAD", 15.0), ("OCC-SEC", "PSL-TOW", "DRV-HEAD", 10.0),
    ("OCC-SEC", "PSL-CARGO", "DRV-HEAD", 30.0), ("OCC-SEC", "PSL-NACC", "DRV-HEAD", 10.0),
    ("OCC-SEC", "PSL-STOR", "DRV-HEAD", 20.0), ("OCC-SEC", "PSL-DOM", "DRV-HEAD", 15.0),
    ("OCC-COMM", "PSL-CARGO", "DRV-OPEX", 10.0), ("OCC-COMM", "PSL-NACC", "DRV-OPEX", 5.0),
    ("OCC-COMM", "PSL-STOR", "DRV-OPEX", 10.0), ("OCC-COMM", "PSL-DOM", "DRV-OPEX", 75.0),
]

ALERT_THRESHOLDS = [
    ("cost_overrun", "cost_variance_abs", 0.0, "WARNING", "Expenditure above budget"),
    ("material_variance", "cost_variance_pct", 10.0, "PRIORITY_REVIEW", "Cost variance exceeds 10% of budget"),
    ("revenue_shortfall", "revenue_variance_pct", -5.0, "WARNING", "Revenue more than 5% below budget"),
    ("low_cost_recovery", "cost_recovery_ratio", 0.85, "PRIORITY_REVIEW", "Cost recovery ratio below 85%"),
    ("critical_deficit", "cost_recovery_ratio", 0.70, "CRITICAL", "Service in critical deficit"),
    ("budget_ahead", "budget_consumption_ytd", 1.15, "WARNING", "YTD spending is more than 15% ahead of YTD budget"),
    ("high_overhead", "overhead_share_pct", 45.0, "WARNING", "Overhead allocation exceeds 45% of total OCC cost"),
    ("data_quality", "missing_kpi", 0.0, "DATA_QUALITY", "Required KPI value is missing"),
    ("service_deficit", "service_net_position", 0.0, "PRIORITY_REVIEW", "Service net position is negative"),
    ("negative_margin", "analytical_margin_pct", 0.0, "PRIORITY_REVIEW", "Analytical margin is negative"),
    ("high_indirect_share", "indirect_share_pct", 60.0, "WARNING", "Indirect allocations exceed 60% of total allocated cost"),
    ("missing_revenue", "actual_revenue", 0.0, "DATA_QUALITY", "Allocated cost exists but no revenue is recorded"),
]

ACTIONS = [
    ("cost_overrun", "Review expenditure commitments and prepare a variance explanation.", "Finance Controller", "Monitor", "5 working days"),
    ("material_variance", "Investigate the account category driving the variance and update the year-end forecast.", "Finance Director and Operational Manager", "Investigate", "3 working days"),
    ("revenue_shortfall", "Assess demand, pricing and source-data completeness.", "Commercial Manager", "Monitor", "5 working days"),
    ("low_cost_recovery", "Review pricing, allocation rules and public-service justification.", "Finance Director", "Review", "10 working days"),
    ("critical_deficit", "Escalate immediately and prepare tariff, cost-reduction and explicit-subsidy options.", "Port Director and Finance Director", "Escalate", "Same day"),
    ("budget_ahead", "Project full-year expenditure and initiate a budget review.", "Finance Controller", "Monitor", "5 working days"),
    ("high_overhead", "Review shared-service efficiency and allocation percentages.", "Finance Director", "Review", "Quarterly review"),
    ("data_quality", "Correct the missing source or mapping data and re-run the pipeline.", "Data owner and Finance Controller", "Fix", "2 working days"),
    ("service_deficit", "Review tariff, cost structure and public-service justification for the service deficit.", "Finance Director", "Review", "5 working days"),
    ("negative_margin", "Investigate the drivers of the negative analytical margin and prepare corrective options.", "Finance and Service Manager", "Investigate", "5 working days"),
    ("high_indirect_share", "Review the composition and attribution of indirect costs affecting the service.", "Finance Controller", "Review", "10 working days"),
    ("missing_revenue", "Verify revenue completeness and service-to-revenue mapping before management interpretation.", "Revenue Owner and Finance Controller", "Fix", "2 working days"),
]

KPI_DEFINITIONS = [
    ("KPI-01", "Service Net Position", "Revenue - Attributed Cost", "Positive is surplus", "Assess service viability", "< 0", "critical_deficit"),
    ("KPI-02", "Cost Recovery Ratio", "Revenue / Attributed Cost", "1.0 is full recovery", "Assess pricing and subsidy", "< 0.85", "low_cost_recovery"),
    ("KPI-03", "Cost Variance", "Actual - Budget", "Positive is overrun", "Monitor expenditure", "> 0", "cost_overrun"),
    ("KPI-04", "Cost Variance Percentage", "(Actual-Budget)/Budget*100", "Normalised variance", "Prioritise investigation", "> 10%", "material_variance"),
    ("KPI-05", "Revenue Variance Percentage", "(Actual-Budget)/Budget*100", "Negative is shortfall", "Monitor revenue", "< -5%", "revenue_shortfall"),
    ("KPI-06", "YTD Budget Consumption", "Actual YTD/Budget YTD", "Above 1.0 is ahead", "Detect budget drift", "> 1.15", "budget_ahead"),
    ("KPI-07", "Overhead Share", "Allocated SSC/Total OCC Cost*100", "Measures overhead burden", "Review SSC efficiency", "> 45%", "high_overhead"),
    ("KPI-08", "Top Cost Category Share", "Largest category/Total direct cost*100", "Measures concentration", "Assess cost flexibility", "> 60%", None),
    ("KPI-09", "Cost Efficiency Index", "Attributed Cost/Activity Volume", "Unit cost", "Monitor productivity", "Trend", None),
]

BASE_BUDGETS = {
    "SSC-ADM": {"AC-PAY": 185000, "AC-EQUIP": 12000, "AC-ENRG": 8000, "AC-OPS": 22000},
    "SSC-IT": {"AC-PAY": 120000, "AC-EQUIP": 45000, "AC-ENRG": 18000, "AC-OPS": 15000},
    "SSC-FAC": {"AC-PAY": 95000, "AC-EQUIP": 38000, "AC-ENRG": 28000, "AC-OPS": 12000},
    "OCC-NAV": {"AC-PAY": 310000, "AC-EQUIP": 85000, "AC-ENRG": 92000, "AC-OPS": 45000},
    "OCC-CARGO": {"AC-PAY": 420000, "AC-EQUIP": 180000, "AC-ENRG": 145000, "AC-OPS": 88000},
    "OCC-INFRA": {"AC-PAY": 195000, "AC-EQUIP": 95000, "AC-ENRG": 48000, "AC-OPS": 35000},
    "OCC-SEC": {"AC-PAY": 245000, "AC-EQUIP": 32000, "AC-ENRG": 22000, "AC-OPS": 28000},
    "OCC-COMM": {"AC-PAY": 88000, "AC-EQUIP": 18000, "AC-ENRG": 9000, "AC-OPS": 32000},
}

SERVICE_BUDGETS = {"PSL-PIL": 480000, "PSL-TOW": 360000, "PSL-CARGO": 1200000, "PSL-NACC": 650000, "PSL-STOR": 420000, "PSL-DOM": 280000}
SERVICE_VOLUMES = {"PSL-PIL": 2400, "PSL-TOW": 1800, "PSL-CARGO": 3600000, "PSL-NACC": 12000000, "PSL-STOR": 1200000, "PSL-DOM": 250000}
CENTRE_CURRENCIES = {"SSC-ADM": "GBP", "SSC-IT": "EUR", "SSC-FAC": "USD", "OCC-NAV": "GBP", "OCC-CARGO": "XOF", "OCC-INFRA": "EUR", "OCC-SEC": "USD", "OCC-COMM": "GBP"}
SERVICE_CURRENCIES = {"PSL-PIL": "GBP", "PSL-TOW": "EUR", "PSL-CARGO": "USD", "PSL-NACC": "XOF", "PSL-STOR": "EUR", "PSL-DOM": "GBP"}

# Multi-year trend index (baseline = 2022 = 1.0). Reflects a plausible
# public-port pattern: a 2020 traffic downturn, a 2021 partial recovery,
# and stabilised growth through 2026. Revenue (traffic-driven: vessel
# calls, cargo throughput) swings further than cost (payroll-dominated,
# structurally sticky) — the amplitude gap below is deliberate, not
# accidental, and is what "charges plus stables que les recettes" means
# operationally: a service can lose revenue in a downturn far faster than
# its largely-fixed cost base can be cut.
REVENUE_TREND = {2020: 0.80, 2021: 0.90, 2022: 1.00, 2023: 1.07, 2024: 1.13, 2025: 1.18, 2026: 1.22}
COST_TREND = {2020: 0.90, 2021: 0.94, 2022: 1.00, 2023: 1.04, 2024: 1.08, 2025: 1.11, 2026: 1.14}


def _normalised(raw):
    scale = 12 / sum(raw)
    return [x * scale for x in raw]


# Monthly seasonality (weights normalised so sum(weights) == 12, i.e.
# monthly_amount = annual_amount / 12 * weight[m] and sum(monthly) ==
# annual_amount exactly). Costs use a nearly flat curve (small Q3 bump for
# energy/overtime); revenue follows a documented vessel-traffic pattern —
# a Q2/Q3 peak (higher call frequency in the dry season) and a trough in
# Q4/Q1 (fewer calls, weather-driven slowdown, year-end port closures).
COST_WEIGHTS = _normalised([1.15, 1.15, 1, 0.9, 0.9, 0.9, 1.15, 1.15, 1, 1, 1, 1])
REVENUE_WEIGHTS = _normalised([1.2, 1.2, 1, 0.88, 0.88, 0.88, 1.2, 1.2, 1, 1, 1, 1])


def reset_demo_data() -> None:
    tables = [
        "decision_alerts", "psl_indicators", "occ_indicators", "allocation_results_phase2", "allocation_results_phase1", "oracle_view_facts", "activity_volumes", "service_budgets",
        "revenue_transactions", "actual_transactions", "budgets", "allocation_rules_phase2",
        "allocation_rules_phase1", "decision_support_actions", "kpi_definitions", "alert_thresholds",
        "data_quality_issues", "data_load_runs", "ingestion_batches", "reporting_periods", "service_lines", "account_categories", "cost_centres", "fx_rates",
    ]
    with connect() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("PRAGMA foreign_keys=ON")


def _period_end(year: int, month: int) -> str:
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def _periods(granularity: str, year: int) -> list[tuple[str, int | None, float]]:
    """Returns [(period_id, month_or_None, weight)] for one year. Weights
    sum to 12 for "monthly" (12 rows) and equal 12 for the single "annual"
    row, so `annual_base / 12 * weight` yields the exact annual total either
    way — granularity changes row count, never the yearly sum."""
    if granularity == "annual":
        return [(f"{year}-ANNUAL", None, 12.0)]
    if granularity == "monthly":
        return [(f"{year}-{m:02d}", m, COST_WEIGHTS[m - 1]) for m in range(1, 13)]
    raise ValueError(f"Unknown granularity: {granularity!r} (expected 'annual' or 'monthly')")


def _revenue_periods(granularity: str, year: int) -> list[tuple[str, int | None, float]]:
    if granularity == "annual":
        return [(f"{year}-ANNUAL", None, 12.0)]
    return [(f"{year}-{m:02d}", m, REVENUE_WEIGHTS[m - 1]) for m in range(1, 13)]


def seed_demo(granularity: str = "monthly", year_from: int = YEAR_FROM, year_to: int = YEAR_TO) -> None:
    if granularity not in ("annual", "monthly"):
        raise ValueError(f"Unknown granularity: {granularity!r} (expected 'annual' or 'monthly')")
    years = list(range(year_from, year_to + 1))

    create_schema()
    reset_demo_data()
    random.seed(RANDOM_SEED)

    with connect() as conn:
        # This demo dataset is already English-only, so centre_name_en /
        # service_name_en / service_category_en are left NULL — the
        # dashboard's FR/EN lookup falls back to the base (English) name.
        conn.executemany(
            "INSERT INTO cost_centres(centre_code,centre_name,tier,centre_type,parent_code) VALUES(?,?,?,?,?)",
            COST_CENTRES,
        )
        conn.executemany("INSERT INTO account_categories VALUES(?,?,?)", ACCOUNT_CATEGORIES)
        conn.executemany(
            "INSERT INTO service_lines(service_code,service_name,service_category,revenue_type,primary_driver) VALUES(?,?,?,?,?)",
            SERVICE_LINES,
        )
        period_rows = []
        for year in years:
            for period_id, month, _weight in _periods(granularity, year):
                granularity_tag = "MONTH" if month else "YEAR"
                label = f"{calendar.month_abbr[month]} {year}" if month else f"Annual {year}"
                end_date = _period_end(year, month) if month else date(year, 12, 31).isoformat()
                is_closed = 1 if year < YEAR_TO else int((month or 12) <= 6)
                period_rows.append((period_id, year, month, granularity_tag, label, end_date, is_closed))
        conn.executemany(
            """INSERT INTO reporting_periods
            (period_id,year,month,period_granularity,period_label,period_end_date,is_closed)
            VALUES(?,?,?,?,?,?,?)""",
            period_rows,
        )
        conn.executemany("INSERT INTO alert_thresholds(rule_name,indicator,threshold_val,severity,description) VALUES(?,?,?,?,?)", ALERT_THRESHOLDS)
        conn.executemany("INSERT INTO decision_support_actions VALUES(?,?,?,?,?)", ACTIONS)
        conn.executemany("INSERT INTO kpi_definitions VALUES(?,?,?,?,?,?,?)", KPI_DEFINITIONS)
        conn.executemany("INSERT INTO allocation_rules_phase1(source_ssc,destination_occ,driver_code,allocation_pct) VALUES(?,?,?,?)", ALLOC_PHASE1)
        conn.executemany("INSERT INTO allocation_rules_phase2(source_occ,destination_psl,driver_code,allocation_pct) VALUES(?,?,?,?)", ALLOC_PHASE2)

    fx_repository = FxRateRepository()
    for year in years:
        for period_id, month, _weight in _periods(granularity, year):
            rate_date = date(year, month or 12, 1 if month else 31)
            year_drift = (year - 2022) * 0.004
            month_drift = ((month or 6) - 6) * 0.001
            # Illustrative rates used only by DEMO mode. Database mode should
            # load approved historical rates from ECB, treasury or a
            # controlled CSV.
            demo_rates = {
                "GBP": 1.0,
                "EUR": 0.84 + month_drift + year_drift,
                "USD": 0.79 + month_drift * 1.5 + year_drift,
                "XOF": 0.00128 + year_drift * 0.0006,
            }
            for source_currency, rate_to_gbp in demo_rates.items():
                fx_repository.upsert(FxRate(rate_date, source_currency, base_currency(), rate_to_gbp, "DEMO", True))
    converter = CurrencyConverter()

    with connect() as conn:
        for centre, categories in BASE_BUDGETS.items():
            currency = CENTRE_CURRENCIES[centre]
            for year in years:
                cost_trend = COST_TREND[year]
                for pid, month, weight in _periods(granularity, year):
                    tx_date = date(year, month or 12, 15 if month else 31)
                    for category, annual_base in categories.items():
                        budget_base = round(annual_base * cost_trend / 12 * weight, 2)
                        base_to_source = converter.convert(budget_base, base_currency(), currency, tx_date)
                        source_budget = round(base_to_source.amount, 2)
                        source_to_base = converter.convert(source_budget, currency, base_currency(), tx_date)
                        source_id = f"DEMO-BUD-{centre}-{category}-{pid}"
                        conn.execute(
                            """INSERT INTO budgets(source_system,source_row_id,centre_code,category_code,period_id,
                            amount_source,source_currency,fx_rate_to_base,fx_rate_date,amount_base,base_currency)
                            VALUES('DEMO',?,?,?,?,?,?,?,?,?,?)""",
                            (source_id, centre, category, pid, source_budget, currency, source_to_base.rate, source_to_base.rate_date.isoformat(), source_to_base.amount, base_currency()),
                        )

                        factor = random.uniform(0.95, 1.08)
                        month_num = month or 7
                        if centre == "OCC-CARGO" and category == "AC-ENRG" and month_num in (7, 8):
                            factor = 1.28
                        if centre == "OCC-SEC":
                            factor = random.uniform(1.04, 1.09)
                        actual_source = round(source_budget * factor, 2)
                        actual_base = converter.convert(actual_source, currency, base_currency(), tx_date)
                        conn.execute(
                            """INSERT INTO actual_transactions(source_system,source_row_id,centre_code,category_code,period_id,
                            transaction_date,amount_source,source_currency,fx_rate_to_base,fx_rate_date,amount_base,base_currency,description)
                            VALUES('DEMO',?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (f"DEMO-ACT-{centre}-{category}-{pid}", centre, category, pid, tx_date.isoformat(), actual_source, currency, actual_base.rate, actual_base.rate_date.isoformat(), actual_base.amount, base_currency(), "Synthetic multi-currency actual"),
                        )

        service_category = {"PSL-CARGO": "RV-CARGO", "PSL-STOR": "RV-MISC", "PSL-DOM": "RV-MISC"}
        for service, annual_base in SERVICE_BUDGETS.items():
            currency = SERVICE_CURRENCIES[service]
            for year in years:
                revenue_trend = REVENUE_TREND[year]
                for pid, month, weight in _revenue_periods(granularity, year):
                    tx_date = date(year, month or 12, 15 if month else 31)
                    budget_base = round(annual_base * revenue_trend / 12 * weight, 2)
                    budget_source = converter.convert(budget_base, base_currency(), currency, tx_date).amount
                    converted_budget = converter.convert(budget_source, currency, base_currency(), tx_date)
                    budget_volume = SERVICE_VOLUMES[service] * revenue_trend / 12 * weight
                    conn.execute(
                        """INSERT INTO service_budgets(source_system,source_row_id,service_code,period_id,budgeted_revenue_source,
                        source_currency,fx_rate_to_base,fx_rate_date,budgeted_revenue_base,base_currency,budgeted_volume)
                        VALUES('DEMO',?,?,?,?,?,?,?,?,?,?)""",
                        (f"DEMO-SBUD-{service}-{pid}", service, pid, budget_source, currency, converted_budget.rate, converted_budget.rate_date.isoformat(), converted_budget.amount, base_currency(), budget_volume),
                    )

                    revenue_factor = random.uniform(0.94, 1.06)
                    volume_factor = random.uniform(0.93, 1.07)
                    month_num = month or 11
                    # Recurring seasonal edge cases (same month every year):
                    # a March channel-access dip, a November pilotage
                    # slowdown severe enough to trip the critical-deficit
                    # alert, and a September storage disruption — kept as
                    # annual recurrences rather than one-off events so the
                    # 2020-2026 evolution pages show a stable, explainable
                    # pattern rather than unexplained yearly noise.
                    if service == "PSL-NACC" and month_num == 3:
                        revenue_factor, volume_factor = 0.87, 0.86
                    if service == "PSL-PIL" and month_num == 11:
                        revenue_factor, volume_factor = 0.30, 0.70
                    if service == "PSL-STOR" and month_num == 9:
                        revenue_factor, volume_factor = 0.65, 0.72
                    actual_source = budget_source * revenue_factor
                    actual_base = converter.convert(actual_source, currency, base_currency(), tx_date)
                    category = service_category.get(service, "RV-DUES")
                    conn.execute(
                        """INSERT INTO revenue_transactions(source_system,source_row_id,service_code,category_code,period_id,
                        transaction_date,amount_source,source_currency,fx_rate_to_base,fx_rate_date,amount_base,base_currency,description)
                        VALUES('DEMO',?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (f"DEMO-REV-{service}-{pid}", service, category, pid, tx_date.isoformat(), actual_source, currency, actual_base.rate, actual_base.rate_date.isoformat(), actual_base.amount, base_currency(), "Synthetic multi-currency revenue"),
                    )
                    conn.execute(
                        """INSERT INTO activity_volumes(source_system,source_row_id,service_code,period_id,volume_units,unit_name)
                        VALUES('DEMO',?,?,?,?,?)""",
                        (f"DEMO-VOL-{service}-{pid}", service, pid, budget_volume * volume_factor, "service-specific unit"),
                    )
        conn.commit()

    print(
        f"Demo data seeded ({granularity}, {year_from}-{year_to}) with GBP, EUR, "
        f"USD and XOF source currencies; analytical base is {base_currency()}"
    )


# ---------------------------------------------------------------------------
# Synthetic Oracle PBI_JDE views export — fabricated data in the exact
# column layout of the five real analytical views, used by the
# "pre-allocated Oracle views" pipeline (src/ingestion/oracle_views.py) as
# a stand-in for a live Oracle extract. The service catalogue (CATEGORIE /
# PRODUIT_FINI) matches docs/SERVICE_CATALOG.md; the cost-centre and
# chart-of-accounts taxonomy below (SYN_COST_CENTRES / SYN_FAMILIES) is
# fabricated for this project and is not derived from any real
# organisation's structure.
# ---------------------------------------------------------------------------

SYN_COST_CENTRES = [
    ("2010", "Port Operations Department"),
    ("2020", "Engineering & Infrastructure Department"),
    ("2030", "Commercial & Estate Department"),
    ("2040", "Corporate Services Department"),
    ("2050", "Safety & Security Department"),
    ("2060", "Finance Department"),
]

# category -> [(product_code, revenue_weight_within_category)]
SYN_CATEGORY_PRODUCTS = {
    "Marchandises": [("PF-Acces Nautique", 1.0)],
    "Services Maritimes": [
        ("PF-Pilotage", 0.42), ("PF-Remorquage", 0.40), ("PF-Lamenage", 0.18),
    ],
    "Domaines": [("PF-Expl Domaniale Port", 1.0)],
    "Autres Services": [
        ("PF-Acces Portuaire", 0.22), ("PF-Autres", 0.18), ("PF-ISPS", 0.24),
        ("PF-Livraisons d'eau & électric", 0.20), ("PF-Pont Bascule", 0.16),
    ],
}
CATEGORY_REVENUE_SHARE = {"Marchandises": 0.45, "Services Maritimes": 0.30, "Domaines": 0.12, "Autres Services": 0.13}

REVENUE_ACCOUNTS = {
    "PF-Acces Nautique": "Redevance accès nautique",
    "PF-Pilotage": "Redevance de pilotage",
    "PF-Remorquage": "Redevance de remorquage",
    "PF-Lamenage": "Redevance de lamanage",
    "PF-Expl Domaniale Port": "Redevance domaniale",
    "PF-Acces Portuaire": "Redevance accès portuaire",
    "PF-Autres": "Produits accessoires",
    "PF-ISPS": "Redevance sûreté portuaire",
    "PF-Livraisons d'eau & électric": "Cession eau et électricité",
    "PF-Pont Bascule": "Redevance pont bascule",
}

# family -> [subfamily, ...]
SYN_FAMILIES = {
    "Charges de personnel et social": ["Salaires du personnel permanent", "Charges sociales", "Primes et indemnités"],
    "Achats, matières et consommables": ["Consommables de bureau", "Pièces détachées", "Carburants et lubrifiants"],
    "Maintenance, infrastructures et équipements": ["Entretien des infrastructures portuaires", "Entretien du matériel naval", "Entretien des bâtiments"],
    "Énergie, eau et fluides": ["Électricité", "Eau", "Autres énergies"],
    "Prestations externes et frais": ["Sous-traitance générale", "Honoraires et conseils", "Assurances"],
    "Transport, déplacements et logistique": ["Transport du personnel", "Missions et déplacements"],
    "Charges financières et amortissements": ["Amortissements des immobilisations", "Intérêts sur emprunts"],
    "Impôts, risques et autres charges": ["Impôts et taxes directs", "Pénalités et amendes"],
}
FAMILY_COST_SHARE = {
    "Charges de personnel et social": 0.42,
    "Achats, matières et consommables": 0.10,
    "Maintenance, infrastructures et équipements": 0.16,
    "Énergie, eau et fluides": 0.10,
    "Prestations externes et frais": 0.10,
    "Transport, déplacements et logistique": 0.04,
    "Charges financières et amortissements": 0.05,
    "Impôts, risques et autres charges": 0.03,
}

REVENUE_BASE_ANNUAL_XOF = 20_000_000_000  # baseline (2022, trend index 1.0)
COST_BASE_ANNUAL_XOF = 14_500_000_000  # baseline (2022, trend index 1.0)
DIRECT_COST_SHARE = 0.58  # remainder (0.42) is indirect, pooled (no source cost centre)


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def generate_synthetic_oracle_views(
    output_dir: str | Path = "data/import/oracle_views_sample",
    year_from: int = YEAR_FROM,
    year_to: int = YEAR_TO,
    granularity: str = "annual",
) -> dict[str, Path]:
    """Writes four CSV files reproducing the exact column layout of the
    real ADIRECTE_COUT / AINDIRECTE_COUT / COUT_PAR_FCC / RECETTE_PF
    Oracle views (see docs/ORACLE_PBI_VIEWS.md) with entirely fabricated
    amounts and labels. The real views expose no currency column and no
    sub-annual period column — both constraints are preserved here, so
    ``granularity="monthly"`` widens ANNEE-adjacent rows across 12 rows
    per year (one MONTANT per month) rather than adding a period column
    the real source does not have.
    """
    if granularity not in ("annual", "monthly"):
        raise ValueError(f"Unknown granularity: {granularity!r} (expected 'annual' or 'monthly')")
    rng = random.Random(RANDOM_SEED)
    directory = project_path(output_dir)
    years = list(range(year_from, year_to + 1))

    direct_rows, indirect_rows, cost_centre_rows, revenue_rows = [], [], [], []

    for year in years:
        cost_trend = COST_TREND[year]
        revenue_trend = REVENUE_TREND[year]
        periods = _periods(granularity, year)
        n_periods = len(periods)

        annual_cost = COST_BASE_ANNUAL_XOF * cost_trend
        annual_revenue = REVENUE_BASE_ANNUAL_XOF * revenue_trend

        for pid, month, weight in periods:
            period_cost = annual_cost / 12 * weight
            period_revenue = annual_revenue / 12 * weight
            direct_pool = period_cost * DIRECT_COST_SHARE
            indirect_pool = period_cost * (1 - DIRECT_COST_SHARE)

            for category, products in SYN_CATEGORY_PRODUCTS.items():
                category_direct = direct_pool * CATEGORY_REVENUE_SHARE[category]
                category_indirect = indirect_pool * CATEGORY_REVENUE_SHARE[category]
                category_revenue = period_revenue * CATEGORY_REVENUE_SHARE[category]
                for product, product_weight in products:
                    noise = rng.uniform(0.94, 1.06)
                    cc_code, _ = SYN_COST_CENTRES[hash((category, product)) % len(SYN_COST_CENTRES)]
                    direct_amount = round(category_direct * product_weight * noise, 0)
                    direct_rows.append([year, cc_code, category, product, -direct_amount])
                    indirect_amount = round(category_indirect * product_weight * noise, 0)
                    indirect_rows.append([year, category, product, -indirect_amount])
                    revenue_amount = round(category_revenue * product_weight * (2 - noise), 0)
                    revenue_rows.append(
                        [year, category, product, REVENUE_ACCOUNTS[product], revenue_amount]
                    )

            for cc_code, cc_desc in SYN_COST_CENTRES:
                for family, subfamilies in SYN_FAMILIES.items():
                    family_cost = period_cost * FAMILY_COST_SHARE[family] / len(SYN_COST_CENTRES)
                    for subfamily in subfamilies:
                        noise = rng.uniform(0.93, 1.07)
                        amount = round(family_cost / len(subfamilies) * noise, 0)
                        cost_centre_rows.append([year, cc_code, cc_desc, family, subfamily, -amount])

    directory_paths = {
        "DIRECT_ALLOCATION": directory / "adirecte_cout.csv",
        "INDIRECT_ALLOCATION": directory / "aindirecte_cout.csv",
        "COST_CENTRE_COST": directory / "cout_par_fcc.csv",
        "SERVICE_REVENUE": directory / "recette_pf.csv",
    }
    _write_csv(directory_paths["DIRECT_ALLOCATION"], ["ANNEE", "CODE_CC", "CATEGORIE", "PRODUIT_FINI", "MONTANT"], direct_rows)
    _write_csv(directory_paths["INDIRECT_ALLOCATION"], ["ANNEE", "CATEGORIE", "PRODUIT_FINI", "MONTANT"], indirect_rows)
    _write_csv(directory_paths["COST_CENTRE_COST"], ["ANNEE", "CODE_CC", "DESC_CC", "FAMILLE", "SOUS_FAMILLE", "MONTANT"], cost_centre_rows)
    _write_csv(directory_paths["SERVICE_REVENUE"], ["ANNEE", "CATEGORIE", "PRODUIT_FINI", "COMPTE", "MONTANT"], revenue_rows)
    return directory_paths


if __name__ == "__main__":
    seed_demo()
    generate_synthetic_oracle_views()
