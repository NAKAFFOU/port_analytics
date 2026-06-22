# src/db/schema.py
import sqlite3
from pathlib import Path

DB_PATH = Path('data/port_analytics.db')

SCHEMA_SQL = '''
-- ============================================================
-- TABLES DE RÉFÉRENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS cost_centres (
    centre_code   TEXT PRIMARY KEY,
    centre_name   TEXT NOT NULL,
    centre_type   TEXT NOT NULL CHECK(centre_type IN ('OPERATIONAL','SUPPORT')),
    parent_code   TEXT REFERENCES cost_centres(centre_code)
);
CREATE TABLE IF NOT EXISTS account_categories (
    category_code TEXT PRIMARY KEY,
    category_name TEXT NOT NULL,
    category_type TEXT NOT NULL
        CHECK(category_type IN ('DIRECT_COST','INDIRECT_COST','REVENUE'))
);

CREATE TABLE IF NOT EXISTS reporting_periods (
    period_id     TEXT PRIMARY KEY,   -- ex: '2025-01'
    year          INTEGER NOT NULL,
    month         INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    period_label  TEXT NOT NULL,
    is_closed     INTEGER NOT NULL DEFAULT 0
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
-- TABLES SOURCE (données brutes)
-- ============================================================

CREATE TABLE IF NOT EXISTS budgets (
    budget_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code    TEXT NOT NULL REFERENCES cost_centres(centre_code),
    category_code  TEXT NOT NULL REFERENCES account_categories(category_code),
    period_id      TEXT NOT NULL REFERENCES reporting_periods(period_id),
    amount         REAL NOT NULL CHECK(amount >= 0),
    UNIQUE(centre_code, category_code, period_id)
);

CREATE TABLE IF NOT EXISTS actual_transactions (
    transaction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code     TEXT NOT NULL REFERENCES cost_centres(centre_code),
    category_code   TEXT NOT NULL REFERENCES account_categories(category_code),
    period_id       TEXT NOT NULL REFERENCES reporting_periods(period_id),
    amount          REAL NOT NULL CHECK(amount >= 0),
    description     TEXT
);

CREATE TABLE IF NOT EXISTS revenue_transactions (
    transaction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code     TEXT NOT NULL REFERENCES cost_centres(centre_code),
    period_id       TEXT NOT NULL REFERENCES reporting_periods(period_id),
    amount          REAL NOT NULL CHECK(amount >= 0),
    description     TEXT
);

CREATE TABLE IF NOT EXISTS allocation_rules (
    rule_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_centre      TEXT NOT NULL REFERENCES cost_centres(centre_code),
    destination_centre TEXT NOT NULL REFERENCES cost_centres(centre_code),
    category_code      TEXT NOT NULL REFERENCES account_categories(category_code),
    allocation_pct     REAL NOT NULL CHECK(allocation_pct > 0 AND allocation_pct <= 100)
);

-- ============================================================
-- TABLE DÉRIVÉE (résultats du pipeline)
-- ============================================================

CREATE TABLE IF NOT EXISTS calculated_indicators (
    indicator_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_code        TEXT NOT NULL REFERENCES cost_centres(centre_code),
    period_id          TEXT NOT NULL REFERENCES reporting_periods(period_id),
    total_direct_cost  REAL,
    allocated_indirect REAL,
    total_cost         REAL,
    total_revenue      REAL,
    contribution_margin REAL,
    cost_variance_abs  REAL,
    cost_variance_pct  REAL,
    revenue_variance_abs REAL,
    revenue_variance_pct REAL,
    cost_concentration_pct REAL,
    calculated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(centre_code, period_id)
);
'''

def create_schema():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print('Schema created at', DB_PATH)

if __name__ == '__main__':
    create_schema()
