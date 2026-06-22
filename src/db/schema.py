# src/db/schema.py
import sqlite3
from pathlib import Path

DB_PATH = Path('data/port_analytics.db')

SCHEMA_SQL = '''
-- ============================================================
-- GROUP 1: REFERENCE TABLES (5)
-- ============================================================
CREATE TABLE IF NOT EXISTS cost_centres (
    centre_code  TEXT PRIMARY KEY,
    centre_name  TEXT NOT NULL,
    tier         TEXT NOT NULL CHECK(tier IN ('SSC','OCC')),
    centre_type  TEXT NOT NULL CHECK(centre_type IN ('SUPPORT','OPERATIONAL')),
    parent_code  TEXT REFERENCES cost_centres(centre_code)
);
CREATE TABLE IF NOT EXISTS account_categories (
    category_code TEXT PRIMARY KEY,
    category_name TEXT NOT NULL,
    category_type TEXT NOT NULL
        CHECK(category_type IN ('DIRECT_COST','INDIRECT_COST','REVENUE'))
);
CREATE TABLE IF NOT EXISTS service_lines (
    service_code   TEXT PRIMARY KEY,
    service_name   TEXT NOT NULL,
    revenue_type   TEXT NOT NULL,
    primary_driver TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reporting_periods (
    period_id    TEXT PRIMARY KEY,
    year         INTEGER NOT NULL,
    month        INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    period_label TEXT NOT NULL,
    is_closed    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alert_thresholds (
    threshold_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name     TEXT NOT NULL UNIQUE,
    indicator     TEXT NOT NULL,
    threshold_val REAL NOT NULL,
    severity      TEXT NOT NULL
        CHECK(severity IN ('WARNING','PRIORITY_REVIEW','CRITICAL','DATA_QUALITY')),
    description   TEXT
);
-- ============================================================
-- GROUP 2: SOURCE TRANSACTION TABLES (4)
-- ============================================================
CREATE TABLE IF NOT EXISTS budgets (
    budget_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code   TEXT NOT NULL REFERENCES cost_centres(centre_code),
    category_code TEXT NOT NULL REFERENCES account_categories(category_code),
    period_id     TEXT NOT NULL REFERENCES reporting_periods(period_id),
    amount        REAL NOT NULL CHECK(amount >= 0),
    UNIQUE(centre_code, category_code, period_id)
);
CREATE TABLE IF NOT EXISTS actual_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code    TEXT NOT NULL REFERENCES cost_centres(centre_code),
    category_code  TEXT NOT NULL REFERENCES account_categories(category_code),
    period_id      TEXT NOT NULL REFERENCES reporting_periods(period_id),
    amount         REAL NOT NULL CHECK(amount >= 0),
    description    TEXT
);
-- Revenue recorded at PSL level — not at cost centre level
CREATE TABLE IF NOT EXISTS revenue_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_code   TEXT NOT NULL REFERENCES service_lines(service_code),
    period_id      TEXT NOT NULL REFERENCES reporting_periods(period_id),
    amount         REAL NOT NULL CHECK(amount >= 0),
    volume_units   REAL,
    description    TEXT
);
CREATE TABLE IF NOT EXISTS service_budgets (
    budget_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    service_code     TEXT NOT NULL REFERENCES service_lines(service_code),
    period_id        TEXT NOT NULL REFERENCES reporting_periods(period_id),
    budgeted_revenue REAL NOT NULL CHECK(budgeted_revenue >= 0),
    budgeted_volume  REAL,
    UNIQUE(service_code, period_id)
);
-- ============================================================
-- GROUP 3: ALLOCATION CONFIGURATION (2 — one per phase)
-- ============================================================
CREATE TABLE IF NOT EXISTS allocation_rules_phase1 (
    rule_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ssc      TEXT NOT NULL REFERENCES cost_centres(centre_code),
    destination_occ TEXT NOT NULL REFERENCES cost_centres(centre_code),
    driver_code     TEXT NOT NULL,
    allocation_pct  REAL NOT NULL CHECK(allocation_pct > 0 AND allocation_pct <= 100)
);
CREATE TABLE IF NOT EXISTS allocation_rules_phase2 (
    rule_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_occ      TEXT NOT NULL REFERENCES cost_centres(centre_code),
    destination_psl TEXT NOT NULL REFERENCES service_lines(service_code),
    driver_code     TEXT NOT NULL,
    allocation_pct  REAL NOT NULL CHECK(allocation_pct > 0 AND allocation_pct <= 100)
);
-- ============================================================
-- GROUP 4: DERIVED OUTPUT TABLES (3)
-- ============================================================
CREATE TABLE IF NOT EXISTS occ_indicators (
    indicator_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code        TEXT NOT NULL REFERENCES cost_centres(centre_code),
    period_id          TEXT NOT NULL REFERENCES reporting_periods(period_id),
    total_direct_cost  REAL,
    allocated_ssc_cost REAL,
    total_occ_cost     REAL,
    budget_direct      REAL,
    cost_variance_abs  REAL,
    cost_variance_pct  REAL,
    overhead_share_pct REAL,
    budget_consumption REAL,
    calculated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(centre_code, period_id)
);
CREATE TABLE IF NOT EXISTS psl_indicators (
    indicator_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    service_code          TEXT NOT NULL REFERENCES service_lines(service_code),
    period_id             TEXT NOT NULL REFERENCES reporting_periods(period_id),
    total_attributed_cost REAL,
    actual_revenue        REAL,
    budgeted_revenue      REAL,
    service_net_position  REAL,
    cost_recovery_ratio   REAL,
    revenue_variance_pct  REAL,
    cost_efficiency_index REAL,
    budget_consumption    REAL,
    calculated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(service_code, period_id)
);
CREATE TABLE IF NOT EXISTS decision_alerts (
    alert_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT NOT NULL CHECK(entity_type IN ('OCC','PSL')),
    entity_code     TEXT NOT NULL,
    period_id       TEXT NOT NULL,
    rule_name       TEXT NOT NULL,
    indicator_value REAL,
    threshold_value REAL,
    severity        TEXT NOT NULL,
    description     TEXT,
    generated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
-- ============================================================
-- GROUP 5: DECISION SUPPORT TABLES (2 — NEW)
-- ============================================================
CREATE TABLE IF NOT EXISTS decision_support_actions (
    rule_name          TEXT PRIMARY KEY,
    recommended_action TEXT NOT NULL,
    escalation_path    TEXT,
    priority_class     TEXT NOT NULL,
    response_timeframe TEXT
);
CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_code        TEXT PRIMARY KEY,
    kpi_name        TEXT NOT NULL,
    formula         TEXT NOT NULL,
    interpretation  TEXT,
    management_use  TEXT,
    default_threshold TEXT,
    related_alert   TEXT
);
'''

def create_schema():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print(f'Schema created: {DB_PATH}')

if __name__ == '__main__':
    create_schema()
