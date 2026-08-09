from __future__ import annotations

import sqlite3

from src.common.config import base_currency, database_path

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_systems (
    source_system TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);

CREATE TABLE IF NOT EXISTS cost_centres (
    centre_code TEXT PRIMARY KEY,
    centre_name TEXT NOT NULL,
    centre_name_en TEXT,
    tier TEXT NOT NULL CHECK(tier IN ('SSC','OCC','POOL')),
    centre_type TEXT NOT NULL CHECK(centre_type IN ('SUPPORT','OPERATIONAL','POOL')),
    parent_code TEXT REFERENCES cost_centres(centre_code)
);

CREATE TABLE IF NOT EXISTS account_categories (
    category_code TEXT PRIMARY KEY,
    category_name TEXT NOT NULL,
    category_type TEXT NOT NULL CHECK(category_type IN ('DIRECT_COST','INDIRECT_COST','REVENUE'))
);

CREATE TABLE IF NOT EXISTS service_lines (
    service_code TEXT PRIMARY KEY,
    service_name TEXT NOT NULL,
    service_name_en TEXT,
    service_category TEXT NOT NULL DEFAULT 'Other Services',
    service_category_en TEXT,
    revenue_type TEXT NOT NULL,
    primary_driver TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reporting_periods (
    period_id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER CHECK(month BETWEEN 1 AND 12),
    period_granularity TEXT NOT NULL DEFAULT 'MONTH'
        CHECK(period_granularity IN ('MONTH','YEAR')),
    period_label TEXT NOT NULL,
    period_end_date TEXT NOT NULL,
    is_closed INTEGER NOT NULL DEFAULT 0 CHECK(is_closed IN (0,1)),
    CHECK(
        (period_granularity='MONTH' AND month IS NOT NULL)
        OR
        (period_granularity='YEAR' AND month IS NULL)
    ),
    UNIQUE(year, month, period_granularity)
);

CREATE TABLE IF NOT EXISTS alert_thresholds (
    threshold_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL UNIQUE,
    indicator TEXT NOT NULL,
    threshold_val REAL NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('WARNING','PRIORITY_REVIEW','CRITICAL','DATA_QUALITY')),
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_support_actions (
    rule_name TEXT PRIMARY KEY REFERENCES alert_thresholds(rule_name),
    recommended_action TEXT NOT NULL,
    escalation_path TEXT,
    priority_class TEXT NOT NULL,
    response_timeframe TEXT
);

CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_code TEXT PRIMARY KEY,
    kpi_name TEXT NOT NULL,
    formula TEXT NOT NULL,
    interpretation TEXT,
    management_use TEXT,
    default_threshold TEXT,
    related_alert TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_batches (
    batch_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL REFERENCES source_systems(source_system),
    date_from TEXT,
    date_to TEXT,
    started_at TEXT NOT NULL DEFAULT(datetime('now')),
    completed_at TEXT,
    rows_extracted INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('STARTED','COMPLETED','FAILED')),
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS stg_accounting_transactions (
    staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES ingestion_batches(batch_id),
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    company_code TEXT,
    document_number TEXT,
    document_type TEXT,
    business_unit TEXT,
    object_account TEXT,
    subsidiary TEXT,
    transaction_date TEXT NOT NULL,
    amount_source REAL NOT NULL,
    source_currency TEXT NOT NULL,
    ledger_type TEXT,
    description TEXT,
    loaded_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(source_system, source_row_id, batch_id)
);

CREATE TABLE IF NOT EXISTS stg_budget_lines (
    staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES ingestion_batches(batch_id),
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    company_code TEXT,
    business_unit TEXT,
    object_account TEXT,
    subsidiary TEXT,
    period_id TEXT NOT NULL,
    amount_source REAL NOT NULL,
    source_currency TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(source_system, source_row_id, batch_id)
);

CREATE TABLE IF NOT EXISTS stg_activity_volumes (
    staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES ingestion_batches(batch_id),
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    service_code TEXT NOT NULL,
    period_id TEXT NOT NULL,
    volume_units REAL NOT NULL,
    unit_name TEXT,
    loaded_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(source_system, source_row_id, batch_id)
);

CREATE TABLE IF NOT EXISTS source_cost_centre_mapping (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    company_code TEXT NOT NULL,
    source_business_unit TEXT NOT NULL,
    target_code TEXT NOT NULL REFERENCES cost_centres(centre_code),
    valid_from TEXT,
    valid_to TEXT,
    UNIQUE(source_system, company_code, source_business_unit, valid_from)
);

CREATE TABLE IF NOT EXISTS source_account_mapping (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    company_code TEXT NOT NULL,
    object_account TEXT NOT NULL,
    subsidiary TEXT NOT NULL DEFAULT '*',
    target_category TEXT NOT NULL REFERENCES account_categories(category_code),
    target_nature TEXT NOT NULL CHECK(target_nature IN ('COST','REVENUE')),
    sign_multiplier REAL NOT NULL DEFAULT 1,
    valid_from TEXT,
    valid_to TEXT,
    UNIQUE(source_system, company_code, object_account, subsidiary, valid_from)
);

CREATE TABLE IF NOT EXISTS source_service_mapping (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    company_code TEXT NOT NULL,
    business_unit TEXT NOT NULL DEFAULT '*',
    object_account TEXT NOT NULL,
    subsidiary TEXT NOT NULL DEFAULT '*',
    target_service_code TEXT NOT NULL REFERENCES service_lines(service_code),
    valid_from TEXT,
    valid_to TEXT,
    UNIQUE(source_system, company_code, business_unit, object_account, subsidiary, valid_from)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    fx_rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rate_date TEXT NOT NULL,
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL,
    rate REAL NOT NULL CHECK(rate > 0),
    provider TEXT NOT NULL,
    is_estimated INTEGER NOT NULL DEFAULT 0 CHECK(is_estimated IN (0,1)),
    loaded_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(rate_date, from_currency, to_currency, provider)
);

CREATE TABLE IF NOT EXISTS data_load_runs (
    load_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_schema TEXT,
    source_object TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT(datetime('now')),
    completed_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('STARTED','SUCCESS','PARTIAL_SUCCESS','FAILED')),
    rows_extracted INTEGER NOT NULL DEFAULT 0,
    rows_valid INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    filters_used TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT REFERENCES ingestion_batches(batch_id),
    source_system TEXT,
    source_row_id TEXT,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('WARNING','ERROR')),
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT(datetime('now'))
);

CREATE TABLE IF NOT EXISTS budgets (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    centre_code TEXT NOT NULL REFERENCES cost_centres(centre_code),
    category_code TEXT NOT NULL REFERENCES account_categories(category_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    amount_source REAL NOT NULL,
    source_currency TEXT NOT NULL,
    fx_rate_to_base REAL NOT NULL,
    fx_rate_date TEXT NOT NULL,
    amount_base REAL NOT NULL,
    base_currency TEXT NOT NULL,
    UNIQUE(source_system, source_row_id)
);

CREATE TABLE IF NOT EXISTS actual_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    centre_code TEXT NOT NULL REFERENCES cost_centres(centre_code),
    category_code TEXT NOT NULL REFERENCES account_categories(category_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    transaction_date TEXT NOT NULL,
    amount_source REAL NOT NULL,
    source_currency TEXT NOT NULL,
    fx_rate_to_base REAL NOT NULL,
    fx_rate_date TEXT NOT NULL,
    amount_base REAL NOT NULL,
    base_currency TEXT NOT NULL,
    description TEXT,
    UNIQUE(source_system, source_row_id, centre_code, category_code)
);

CREATE TABLE IF NOT EXISTS revenue_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    service_code TEXT NOT NULL REFERENCES service_lines(service_code),
    category_code TEXT NOT NULL REFERENCES account_categories(category_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    transaction_date TEXT NOT NULL,
    amount_source REAL NOT NULL,
    source_currency TEXT NOT NULL,
    fx_rate_to_base REAL NOT NULL,
    fx_rate_date TEXT NOT NULL,
    amount_base REAL NOT NULL,
    base_currency TEXT NOT NULL,
    description TEXT,
    UNIQUE(source_system, source_row_id, service_code, category_code)
);

CREATE TABLE IF NOT EXISTS service_budgets (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    service_code TEXT NOT NULL REFERENCES service_lines(service_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    budgeted_revenue_source REAL NOT NULL,
    source_currency TEXT NOT NULL,
    fx_rate_to_base REAL NOT NULL,
    fx_rate_date TEXT NOT NULL,
    budgeted_revenue_base REAL NOT NULL,
    base_currency TEXT NOT NULL,
    budgeted_volume REAL,
    UNIQUE(source_system, source_row_id)
);

CREATE TABLE IF NOT EXISTS activity_volumes (
    volume_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    service_code TEXT NOT NULL REFERENCES service_lines(service_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    volume_units REAL NOT NULL CHECK(volume_units >= 0),
    unit_name TEXT,
    UNIQUE(source_system, source_row_id)
);

CREATE TABLE IF NOT EXISTS allocation_rules_phase1 (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ssc TEXT NOT NULL REFERENCES cost_centres(centre_code),
    destination_occ TEXT NOT NULL REFERENCES cost_centres(centre_code),
    driver_code TEXT NOT NULL,
    allocation_pct REAL NOT NULL CHECK(allocation_pct > 0 AND allocation_pct <= 100),
    UNIQUE(source_ssc, destination_occ)
);

CREATE TABLE IF NOT EXISTS allocation_rules_phase2 (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_occ TEXT NOT NULL REFERENCES cost_centres(centre_code),
    destination_psl TEXT NOT NULL REFERENCES service_lines(service_code),
    driver_code TEXT NOT NULL,
    allocation_pct REAL NOT NULL CHECK(allocation_pct > 0 AND allocation_pct <= 100),
    UNIQUE(source_occ, destination_psl)
);

CREATE TABLE IF NOT EXISTS allocation_results_phase1 (
    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ssc TEXT NOT NULL REFERENCES cost_centres(centre_code),
    destination_occ TEXT NOT NULL REFERENCES cost_centres(centre_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    driver_code TEXT NOT NULL,
    allocation_pct REAL NOT NULL,
    source_ssc_cost REAL NOT NULL,
    allocated_indirect_cost REAL NOT NULL,
    currency_code TEXT NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(source_ssc, destination_occ, period_id)
);

CREATE TABLE IF NOT EXISTS allocation_results_phase2 (
    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_occ TEXT NOT NULL REFERENCES cost_centres(centre_code),
    destination_psl TEXT NOT NULL REFERENCES service_lines(service_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    driver_code TEXT NOT NULL,
    allocation_pct REAL NOT NULL,
    direct_allocated_cost REAL NOT NULL,
    indirect_allocated_cost REAL NOT NULL,
    total_allocated_cost REAL NOT NULL,
    currency_code TEXT NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(source_occ, destination_psl, period_id)
);

CREATE TABLE IF NOT EXISTS oracle_view_facts (
    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES ingestion_batches(batch_id),
    source_system TEXT NOT NULL,
    source_schema TEXT NOT NULL,
    source_view TEXT NOT NULL,
    measure_type TEXT NOT NULL CHECK(measure_type IN (
        'DIRECT_ALLOCATION','INDIRECT_ALLOCATION',
        'COST_CENTRE_COST','SERVICE_REVENUE'
    )),
    reporting_year INTEGER NOT NULL,
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    source_cost_centre_code TEXT,
    source_cost_centre_name TEXT,
    centre_code TEXT REFERENCES cost_centres(centre_code),
    service_category TEXT,
    service_category_en TEXT,
    source_service_name TEXT,
    service_code TEXT REFERENCES service_lines(service_code),
    account TEXT,
    account_en TEXT,
    family TEXT,
    family_en TEXT,
    subfamily TEXT,
    subfamily_en TEXT,
    amount_source REAL NOT NULL,
    source_currency TEXT NOT NULL,
    fx_rate_to_base REAL NOT NULL,
    fx_rate_date TEXT NOT NULL,
    fx_provider TEXT NOT NULL,
    amount_base REAL NOT NULL,
    base_currency TEXT NOT NULL,
    source_row_hash TEXT NOT NULL,
    extracted_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(batch_id, measure_type, source_row_hash)
);

CREATE TABLE IF NOT EXISTS occ_indicators (
    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code TEXT NOT NULL REFERENCES cost_centres(centre_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    total_direct_cost REAL,
    allocated_ssc_cost REAL,
    total_occ_cost REAL,
    budget_direct REAL,
    cost_variance_abs REAL,
    cost_variance_pct REAL,
    overhead_share_pct REAL,
    budget_consumption_ytd REAL,
    top_cost_category_share REAL,
    currency_code TEXT NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(centre_code, period_id)
);

CREATE TABLE IF NOT EXISTS psl_indicators (
    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_code TEXT NOT NULL REFERENCES service_lines(service_code),
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    direct_allocated_cost REAL,
    indirect_allocated_cost REAL,
    total_attributed_cost REAL,
    actual_revenue REAL,
    budgeted_revenue REAL,
    activity_volume REAL,
    service_net_position REAL,
    analytical_margin_pct REAL,
    cost_recovery_ratio REAL,
    revenue_variance_pct REAL,
    cost_efficiency_index REAL,
    revenue_budget_achievement_ytd REAL,
    currency_code TEXT NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT(datetime('now')),
    UNIQUE(service_code, period_id)
);

CREATE TABLE IF NOT EXISTS decision_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('OCC','PSL')),
    entity_code TEXT NOT NULL,
    period_id TEXT NOT NULL REFERENCES reporting_periods(period_id),
    rule_name TEXT NOT NULL REFERENCES alert_thresholds(rule_name),
    indicator_value REAL,
    threshold_value REAL,
    severity TEXT NOT NULL CHECK(severity IN ('WARNING','PRIORITY_REVIEW','CRITICAL','DATA_QUALITY')),
    description TEXT,
    generated_at TEXT NOT NULL DEFAULT(datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_data_load_runs_object ON data_load_runs(source_object, started_at);
CREATE INDEX IF NOT EXISTS idx_stg_batch ON stg_accounting_transactions(batch_id);
CREATE INDEX IF NOT EXISTS idx_actual_period ON actual_transactions(period_id, centre_code);
CREATE INDEX IF NOT EXISTS idx_revenue_period ON revenue_transactions(period_id, service_code);
CREATE INDEX IF NOT EXISTS idx_fx_lookup ON fx_rates(from_currency, to_currency, rate_date);
CREATE INDEX IF NOT EXISTS idx_alloc1_period ON allocation_results_phase1(period_id, destination_occ);
CREATE INDEX IF NOT EXISTS idx_alloc2_period ON allocation_results_phase2(period_id, destination_psl);
CREATE INDEX IF NOT EXISTS idx_alert_period ON decision_alerts(period_id, severity);
CREATE INDEX IF NOT EXISTS idx_oracle_facts_period ON oracle_view_facts(period_id, measure_type);
CREATE INDEX IF NOT EXISTS idx_oracle_facts_service ON oracle_view_facts(service_code, period_id);
CREATE INDEX IF NOT EXISTS idx_oracle_facts_centre ON oracle_view_facts(centre_code, period_id);
"""


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate_existing_database(conn: sqlite3.Connection) -> None:
    service_columns = _column_names(conn, "service_lines")
    if "service_category" not in service_columns:
        conn.execute(
            "ALTER TABLE service_lines ADD COLUMN service_category TEXT NOT NULL DEFAULT 'Other Services'"
        )
    for column in ["service_name_en", "service_category_en"]:
        if column not in service_columns:
            conn.execute(f"ALTER TABLE service_lines ADD COLUMN {column} TEXT")

    centre_columns = _column_names(conn, "cost_centres")
    if "centre_name_en" not in centre_columns:
        conn.execute("ALTER TABLE cost_centres ADD COLUMN centre_name_en TEXT")

    psl_columns = _column_names(conn, "psl_indicators")
    additions = {
        "direct_allocated_cost": "REAL",
        "indirect_allocated_cost": "REAL",
        "analytical_margin_pct": "REAL",
    }
    for column, sql_type in additions.items():
        if column not in psl_columns:
            conn.execute(f"ALTER TABLE psl_indicators ADD COLUMN {column} {sql_type}")

    facts_columns = _column_names(conn, "oracle_view_facts")
    for column in [
        "account", "family", "subfamily",
        "account_en", "family_en", "subfamily_en", "service_category_en",
    ]:
        if column not in facts_columns:
            conn.execute(f"ALTER TABLE oracle_view_facts ADD COLUMN {column} TEXT")


def create_schema() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_existing_database(conn)
        conn.execute(
            "INSERT OR IGNORE INTO source_systems VALUES (?,?,?,1)",
            ("DEMO", "Synthetic multi-currency demonstration", "DEMO"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO source_systems VALUES (?,?,?,1)",
            ("JDE_ORACLE", "JD Edwards EnterpriseOne on Oracle (legacy table adapter)", "DATABASE"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO source_systems VALUES (?,?,?,1)",
            ("ORACLE_PBI_VIEWS", "Pre-allocated analytical views in PBI_JDE", "DATABASE"),
        )
    print(f"Schema ready: {database_path()} | Base currency: {base_currency()}")


def list_user_tables() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [row[0] for row in rows]


if __name__ == "__main__":
    create_schema()
    tables = list_user_tables()
    print(f"{len(tables)} user tables")
    for name in tables:
        print(f" - {name}")
