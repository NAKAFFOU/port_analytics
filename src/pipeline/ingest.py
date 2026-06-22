# src/pipeline/ingest.py
import sqlite3
from pathlib import Path
DB_PATH = Path('data/port_analytics.db')

def validate_referential_integrity():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    errors = []
    # Phase 1: sums must equal 100% per source SSC
    for row in conn.execute('''SELECT source_ssc, SUM(allocation_pct) as t FROM allocation_rules_phase1
        GROUP BY source_ssc HAVING ABS(t-100.0)>0.01''').fetchall():
        errors.append(f'Phase1: {row[0]} sums to {row[1]:.2f}% (expected 100%)')
    # Phase 2: sums must equal 100% per source OCC
    for row in conn.execute('''SELECT source_occ, SUM(allocation_pct) as t FROM allocation_rules_phase2
        GROUP BY source_occ HAVING ABS(t-100.0)>0.01''').fetchall():
        errors.append(f'Phase2: {row[0]} sums to {row[1]:.2f}% (expected 100%)')
    neg = conn.execute('SELECT COUNT(*) FROM actual_transactions WHERE amount < 0').fetchone()[0]
    if neg: errors.append(f'{neg} negative transactions detected')
    conn.close()
    if errors:
        for e in errors: print('VALIDATION ERROR:', e)
        return False
    print('Validation passed.')
    return True
